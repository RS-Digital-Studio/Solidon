"""Der Projektcontainer (Bauplan §16.1).

::

    projekt.p3d           (ZIP)
      project.json        # Stapel, Parameter, Passungen, Transaktionen
      sources/            # eingebettete Quellnetze
      report.json         # letzter Prüfbericht
      thumb.png           # Vorschau für Dateidialoge

Drei Regeln, die der Container erzwingt statt annimmt:

* **Keine absoluten Pfade** (§32). Ein Projekt reist zwischen Rechnern und
  Leuten; ein Pfad aus dem Container hinaus wird beim Schreiben wie beim
  Lesen abgelehnt.
* **Prüfsummen auf jeder Quelle**, verifiziert beim Laden (§16.1).
* **Atomar geschrieben.** Ein Absturz beim Speichern darf nicht die Datei
  kosten, die vorher da war — darum liegt auch der Autosave-Container (§38)
  daneben.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any, Final

from app.branding import APP_VERSION, PROJECT_SUFFIX
from app.core import examples
from app.core.errors import ValidationError
from app.core.knowledge.parts import check as part_check
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_data_dir
from app.core.scene.gathered import externalise, gathered_path, inline, references
from app.core.scene.migrations import FORMAT_VERSION, migrate
from app.core.scene.serialise import (
    document_from_data,
    document_to_data,
    report_from_data,
    report_to_data,
)
from app.core.types import Document, Report, Source, SourceId
from app.i18n import _

_log = get_logger(__name__)

PROJECT_ENTRY: Final = "project.json"
REPORT_ENTRY: Final = "report.json"
THUMBNAIL_ENTRY: Final = "thumb.png"
SOURCE_FOLDER: Final = "sources"
AUTOSAVE_SUFFIX: Final = ".autosave"


@dataclass(slots=True)
class Project:
    """Was eine ``.p3d``-Datei hält."""

    document: Document
    sources: dict[SourceId, bytes] = field(default_factory=dict)
    """Inhalt der eingebetteten Quellen, gleich geschlüsselt wie
    ``document.sources``."""
    report: Report = field(default_factory=Report)
    thumbnail: bytes | None = None


@dataclass(slots=True)
class ProjectSources:
    """Lesezugriff auf die Quellen eines Projekts, für die ``load``-Operation.

    Eingebettete Quellen kommen aus dem Container, verknüpfte über einen Pfad
    relativ zum Projektordner — nie über einen absoluten (§32).
    """

    project: Project
    base_dir: Path | None = None
    _identities: dict[SourceId, str] = field(default_factory=dict)
    """Gemerkte Inhaltsprüfsummen für Quellen, die noch keine haben."""

    def identity(self, source_id: SourceId) -> str:
        """Die Inhaltsprüfsumme dieser Quelle (§15, Cache-Schlüssel).

        **Warum nicht einfach ``source.sha256``:** Das Feld wird beim Speichern
        gefüllt, nicht beim Import. Ein Projekt, das noch nie gespeichert wurde,
        trägt dort einen leeren Text — und genau dort wäre der Schlüssel wieder
        blind. Also wird sie gerechnet, wo sie fehlt, und gemerkt: Ein
        eingebetteter Inhalt ändert sich innerhalb einer Sitzung nicht.

        Eine **verknüpfte** Quelle ohne Prüfsumme wird jedes Mal gelesen, und
        das ist Absicht: Sie liegt als Datei draußen und kann sich zwischen zwei
        Auswertungen geändert haben. Ein gemerkter Wert wäre dann die falsche
        Antwort auf die einzige Frage, die diese Funktion hat.
        """
        source = self.describe(source_id)
        if source.sha256:
            return source.sha256
        if not source.embedded:
            return checksum(self.read(source_id))
        known = self._identities.get(source_id)
        if known is None:
            known = checksum(self.read(source_id))
            self._identities[source_id] = known
        return known

    def describe(self, source_id: SourceId) -> Source:
        source = self.project.document.sources.get(source_id)
        if source is None:
            raise ValidationError(
                field="source",
                detail=_("Diese Quelle gibt es im Projekt nicht."),
                constraint="unknown_source",
                values={"source": source_id},
            )
        return source

    def read(self, source_id: SourceId) -> bytes:
        source = self.describe(source_id)
        if source.embedded:
            payload = self.project.sources.get(source_id)
            if payload is None:
                raise ValidationError(
                    field="source",
                    detail=_("Der Inhalt dieser Quelle fehlt im Projekt."),
                    constraint="missing_payload",
                    values={"source": source_id},
                )
            return payload

        _check_relative(source.path, "source.path")
        if self.base_dir is None:
            raise ValidationError(
                field="source",
                detail=_("Verknüpfte Quellen brauchen einen gespeicherten Projektordner."),
                constraint="no_base_dir",
                values={"source": source_id},
            )
        linked = self.base_dir / source.path
        if not linked.is_file():
            raise ValidationError(
                field="source",
                detail=_("Die verknüpfte Datei wurde nicht gefunden."),
                constraint="missing_link",
                values={"source": source_id, "path": source.path},
            )
        return linked.read_bytes()


def new_project(printer: str = "", material: str = "") -> Project:
    """Ein leeres Projekt auf der aktuellen Formatversion."""
    return Project(
        document=Document(
            format_version=FORMAT_VERSION,
            app_version=APP_VERSION,
            printer=printer,
            material=material,
        )
    )


def checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def embedded_source_path(filename: str) -> str:
    """Wo eine eingebettete Quelle im Container liegt — immer relativ."""
    return f"{SOURCE_FOLDER}/{Path(filename).name}"


def _check_relative(path: str, where: str) -> None:
    # Geurteilt wird über beide Konventionen zugleich: eine Projektdatei reist
    # zwischen Plattformen, und „C:/…" muss auch dort abgelehnt werden, wo es
    # für Path nur ein Ordnername ist (Regel 12). PureWindowsPath kennt beide
    # Trennzeichen, also sieht sie auch „..\…" — der Plattform-Path auf POSIX
    # nicht.
    candidate = PureWindowsPath(path)
    if (
        candidate.drive
        or candidate.is_absolute()
        or ".." in candidate.parts
        or path.startswith(("/", "\\"))
    ):
        raise ValidationError(
            field=where,
            detail=_("In Projektdateien stehen keine absoluten Pfade."),
            constraint="absolute_path",
            values={"path": path},
        )


# --- Schreiben -------------------------------------------------------------------


def _next_gathered(document: Document) -> int:
    """Die nächste freie Nummer für einen ausgelagerten Wert.

    Aus den vorhandenen Quellen abgeleitet und nicht mitgezählt: Ein Zähler im
    Dokument wäre ein Zustand, der beim Rückgängigmachen falsch wird.
    """
    used = [
        int(source_id.rsplit("_", 1)[-1])
        for source_id in document.sources
        if source_id.startswith("gathered_") and source_id.rsplit("_", 1)[-1].isdigit()
    ]
    return max(used, default=0) + 1


def save(project: Project, path: Path) -> Path:
    """Schreibt den Container, atomar. Gibt den geschriebenen Pfad zurück."""
    document = project.document
    document.format_version = FORMAT_VERSION
    document.app_version = APP_VERSION
    # §24.4: der Stand der Bausteinbibliothek gehört zu der Art, wie das
    # gerechnet wurde. Für die **eigenen** Bausteine reicht die Version nicht —
    # sie bewegt sich nicht, wenn der Nutzer seine Datei ändert (§24.5). Darum
    # nicht mehr die Zeile von Hand, sondern der Weg, der zusätzlich je
    # benutztem eigenen Baustein einen Abdruck seiner Datei mitschreibt.
    part_check.stamp(document)

    for source_id, source in list(document.sources.items()):
        _check_relative(source.path, f"sources.{source_id}.path")
        if not source.embedded:
            continue
        payload = project.sources.get(source_id)
        if payload is None:
            raise ValidationError(
                field=f"sources.{source_id}",
                detail=_("Eine eingebettete Quelle hat keinen Inhalt."),
                constraint="missing_payload",
                values={"source": source_id},
            )
        # Die Prüfsumme ist Teil des Dokuments, also füllt das Speichern sie
        # ein (§16.1).
        document.sources[source_id] = dataclasses.replace(source, sha256=checksum(payload))

    # §9: Was ein Editor gesammelt hat, kann groß werden — eine
    # Sculpting-Sitzung mit viertausend Zügen ist ein halbes Megabyte Zahlen in
    # einer Zeile. Ab der Grenze wandert der Wert in eine eigene Datei im
    # Container, und im Dokument steht ein Verweis. Gearbeitet wird auf der
    # frisch serialisierten Kopie: Das Dokument im Speicher bleibt, was es ist.
    data = document_to_data(document)
    gathered_payloads = externalise(data, _next_gathered(document))

    ensure_dir(path.parent)
    temporary = path.with_name(path.name + ".part")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr(PROJECT_ENTRY, json.dumps(data, indent=2, ensure_ascii=False))
        for source_id, payload in gathered_payloads.items():
            container.writestr(gathered_path(source_id), payload)
        for source_id, source in document.sources.items():
            if source.embedded:
                container.writestr(source.path, project.sources[source_id])
        container.writestr(
            REPORT_ENTRY, json.dumps(report_to_data(project.report), indent=2, ensure_ascii=False)
        )
        if project.thumbnail is not None:
            container.writestr(THUMBNAIL_ENTRY, project.thumbnail)
    # Derselbe atomare Wechsel wie ``os.replace`` — ``Path.replace`` ruft ihn
    # auf. Eine halb geschriebene Projektdatei darf es nie geben.
    temporary.replace(path)
    _log.info("saved project %s", path.name)
    return path


# --- Lesen ---------------------------------------------------------------------


def load(path: Path) -> Project:
    """Liest einen Container — migriert und verifiziert unterwegs (§16.2)."""
    if not path.is_file():
        raise ValidationError(
            field="path",
            detail=_("Diese Projektdatei gibt es nicht."),
            constraint="missing_file",
            values={"path": path.name},
        )
    try:
        with zipfile.ZipFile(path) as container:
            names = set(container.namelist())
            if PROJECT_ENTRY not in names:
                raise ValidationError(
                    field="container",
                    detail=_("Der Datei fehlt der Projektinhalt."),
                    constraint="not_a_project",
                    values={"path": path.name},
                )
            for name in names:
                _check_relative(name, "container")

            data = migrate(json.loads(container.read(PROJECT_ENTRY)))
            # Die ausgelagerten Sammelwerte zurück ins Dokument, bevor daraus
            # eines wird: Ein Verweis, den niemand auflöst, wäre für jede
            # Operation dahinter ein Text ohne Inhalt und ein leeres Ergebnis
            # ohne Fehlermeldung.
            inline(
                data,
                {
                    source_id: container.read(gathered_path(source_id))
                    for source_id in references(data)
                    if gathered_path(source_id) in names
                },
            )
            document = document_from_data(data)

            payloads: dict[SourceId, bytes] = {}
            for source_id, source in document.sources.items():
                if not source.embedded:
                    continue
                if source.path not in names:
                    raise ValidationError(
                        field=f"sources.{source_id}",
                        detail=_("Eine eingebettete Quelle fehlt im Container."),
                        constraint="missing_payload",
                        values={"source": source_id, "path": source.path},
                    )
                payload = container.read(source.path)
                if source.sha256 and checksum(payload) != source.sha256:
                    raise ValidationError(
                        field=f"sources.{source_id}",
                        detail=_("Eine Quelle stimmt nicht mit ihrer Prüfsumme überein."),
                        constraint="checksum",
                        values={"source": source_id},
                    )
                payloads[source_id] = payload

            report = (
                report_from_data(json.loads(container.read(REPORT_ENTRY)))
                if REPORT_ENTRY in names
                else Report()
            )
            thumbnail = container.read(THUMBNAIL_ENTRY) if THUMBNAIL_ENTRY in names else None
    except zipfile.BadZipFile as problem:
        raise ValidationError(
            field="container",
            detail=_("Die Datei lässt sich nicht öffnen; sie ist beschädigt."),
            constraint="damaged",
            values={"path": path.name},
        ) from problem
    except json.JSONDecodeError as problem:
        raise ValidationError(
            field="container",
            detail=_("Der Projektinhalt ist beschädigt."),
            constraint="damaged",
            values={"path": path.name},
        ) from problem

    _log.info("opened project %s", path.name)
    return Project(document=document, sources=payloads, report=report, thumbnail=thumbnail)


# --- Autosave und Absturz-Wiederherstellung (§38) --------------------------------


def _recovery_dir() -> Path:
    return ensure_dir(user_data_dir() / "recovery")


def autosave_path(path: Path | None) -> Path:
    """Neben dem Projekt — oder im Nutzerverzeichnis, solange es noch keinen
    Namen hat.

    **Ein Beispiel bekommt seines nie daneben.** Beispiele liegen in der
    Installation (§37.2); dort zu schreiben ist unter „Programme" schlicht
    nicht erlaubt und im Entwicklerbaum eine Verschmutzung, die niemand sucht.
    Genau das war der Fall: zwei Sicherungen neben zwei Beispielen ließen den
    Tour-Test in einem Wiederherstellungsdialog hängen, und ein Test, der
    hängt, sagt nicht, warum.
    """
    if path is None:
        return _recovery_dir() / f"unsaved{PROJECT_SUFFIX}{AUTOSAVE_SUFFIX}"
    if path.parent == examples.directory():
        return _recovery_dir() / f"{path.name}{AUTOSAVE_SUFFIX}"
    return path.with_name(path.name + AUTOSAVE_SUFFIX)


def write_autosave(project: Project, path: Path | None) -> Path:
    return save(project, autosave_path(path))


def find_recovery(path: Path | None) -> Path | None:
    """Ein Autosave, das sein Projekt überlebt hat, wird beim nächsten Start
    angeboten.

    **Bei Gleichstand wird angeboten.** Die Dateizeit hat auf dieser Plattform
    eine Auflösung von rund 16 Millisekunden, und ein Projekt zu speichern und
    danach zu sichern dauert weniger — beide Dateien tragen dann dieselbe Zeit,
    bis aufs letzte Bit. Wer daraus „das Autosave ist nicht neuer" schließt,
    hat nicht gemessen, sondern die Auflösung der Uhr abgelesen.

    Entschieden wird deshalb zur sicheren Seite: Ein Angebot, das der Nutzer
    ablehnt, kostet einen Klick; ein Autosave, das nicht angeboten wird, kostet
    seine Arbeit. Ausgeschlossen bleibt nur, was **nachweislich** älter ist —
    dort hat jemand nach der Sicherung gespeichert, und dann gilt das
    Gespeicherte.
    """
    candidate = autosave_path(path)
    if not candidate.is_file():
        return None
    if path is not None and path.is_file() and candidate.stat().st_mtime < path.stat().st_mtime:
        return None
    return candidate


def clear_autosave(path: Path | None) -> None:
    """Die Sicherung ist erledigt — nach dem Speichern und nach dem Verwerfen.

    Der Docstring nannte lange nur den ersten Fall, und dabei blieb es nicht:
    Seit „Verworfen heißt verworfen" räumt auch der Weg über ``_may_discard``
    hier auf, und der läuft im ``closeEvent``.

    **Deshalb wirft die Funktion nicht.** Eine ``.autosave``, die im selben
    Augenblick von einem Virenscanner gehalten wird, ist auf Windows kein
    seltener Fall — und ein ``PermissionError`` mitten im Schließen wäre ein
    Fenster, das sich nicht schließen lässt, wegen einer Datei, die niemanden
    mehr interessiert. Bleibt sie liegen, kostet das eine überflüssige Frage
    beim nächsten Öffnen; das ist die kleinere Störung, und sie steht im
    Protokoll.
    """
    candidate = autosave_path(path)
    if not candidate.is_file():
        return
    try:
        candidate.unlink()
    except OSError as problem:
        _log.warning("could not remove the autosave %s: %s", candidate.name, problem)


def project_data(path: Path) -> dict[str, Any]:
    """Das rohe ``project.json`` eines Containers — für Diagnose und
    Migrationstests."""
    with zipfile.ZipFile(path) as container:
        result: dict[str, Any] = json.loads(container.read(PROJECT_ENTRY))
        return result
