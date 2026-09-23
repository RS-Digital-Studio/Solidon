"""Ein Modell aus einem ZIP-Archiv (Bauplan §16.3, §17.1, §32).

Modellseiten geben ihre Dateien oft als ZIP heraus — alle Teile eines
Projekts in einer Sendung, dazu ein Bild und eine Anleitung. Bis zum
22.09.2026 kam ein solches Archiv nicht herein: Das Ablegen zeigte ein
Verbotszeichen, der Dateidialog blendete es aus, und wer es über eine
Adresse holte, las „Aus der Adresse geht nicht hervor, welches Format die
Datei hat". Der Kunde musste entpacken, suchen und erneut ablegen.

Jetzt wird das Archiv **vor** dem Einbetten aufgelöst: Ins Projekt kommt die
eine Modelldatei, nicht das ZIP mit Bildern und Anleitung. Liegen mehrere
Modelle darin, wird gefragt (Regel 21) — über denselben Rückruf wie jede
andere Frage des Kerns (§9), also im Fenster als Auswahldialog und auf der
Kommandozeile als nummerierte Frage.

**Was hier nicht passiert.** Nichts wird auf die Platte entpackt: Gelesen
wird der eine Eintrag in den Speicher, begrenzt wie jede andere Datei. Damit
gibt es keinen Pfad, den ein Eintrag wie ``../../autostart`` erreichen könnte;
solche Einträge werden trotzdem übergangen, denn ihr Name ist schon die
Auskunft, dass jemand etwas anderes vorhatte als ein Modell zu teilen. Die
Grenzen gegen Zip-Bomben — Zahl der Einträge, entpackte Größe, Packverhältnis
— sind dieselben wie beim 3MF (:func:`app.core.ingest.loader.check_unpacked`).
"""

from __future__ import annotations

import posixpath
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Final
from urllib.parse import unquote, urlsplit

from app.core.errors import CANCEL, CHOOSE_ANOTHER_FILE, ValidationError
from app.core.ingest.loader import (
    MAX_FILE_BYTES,
    GltfReference,
    check_limits,
    check_unpacked,
    embed_gltf_dependencies,
)
from app.core.ingest.plan import MODEL_SUFFIXES
from app.core.log import get_logger
from app.i18n import _

_log = get_logger(__name__)

#: Die Endungen eines Archivs, das Modelle trägt. Kein ``.3mf`` — das ist
#: selbst ein ZIP, aber eine Baugruppe und kein Umschlag.
ARCHIVE_SUFFIXES: Final[tuple[str, ...]] = (".zip",)

#: Was sich einlesen lässt: jedes Modellformat und das Archiv darum.
#: Dateidialog, Ablagefeld, Netzimport und Kommandozeile lesen diese Liste;
#: :data:`~app.core.ingest.plan.MODEL_SUFFIXES` bleibt die Liste dessen, was
#: eine Operation liest — ein ZIP wird nie eine Projektquelle.
IMPORT_SUFFIXES: Final[tuple[str, ...]] = (*MODEL_SUFFIXES, *ARCHIVE_SUFFIXES)

#: Ordner, die ein Packprogramm neben die Dateien legt und die nie ein Modell
#: tragen: macOS schreibt Ressourcengabeln nach ``__MACOSX`` und je Datei ein
#: ``._name``, das dieselbe Endung trägt wie das Modell daneben.
_PACKER_FOLDERS: Final = frozenset({"__MACOSX"})

AskFn = Callable[[str, list[str]], str]


@dataclass(frozen=True, slots=True)
class ArchiveModel:
    """Ein Modell im Archiv: wo es liegt und was der Kunde sieht."""

    entry: str
    """Der Name im Archiv, wie er dort steht."""
    label: str
    """Der Pfad im Archiv mit Schrägstrichen — eindeutig, anders als der bloße
    Dateiname: ``links/deckel.stl`` und ``rechts/deckel.stl`` gibt es."""
    size: int

    @property
    def name(self) -> str:
        """Der Dateiname, unter dem das Modell ins Projekt kommt."""
        return PurePosixPath(self.label).name


def is_archive(name: str) -> bool:
    """Ob diese Datei ein Archiv mit Modellen ist — entschieden an der Endung."""
    return PurePosixPath(name).suffix.lower() in ARCHIVE_SUFFIXES


def _label(entry: str) -> str | None:
    """Der sichtbare Pfad eines Eintrags, oder ``None`` für einen, der keiner ist.

    Übergangen werden Ordner, die Beigaben eines Packprogramms und jeder Name,
    der aus dem Archiv hinauszeigen will — absolut, mit Laufwerk oder mit
    ``..``. Entpackt wird hier zwar nichts, aber ein Name, der so gebaut ist,
    stammt nicht von jemandem, der ein Modell teilen wollte.
    """
    if not entry or "\x00" in entry or entry.endswith(("/", "\\")):
        return None
    name = entry.replace("\\", "/")
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        return None
    parts = [part for part in name.split("/") if part not in ("", ".")]
    if not parts or ".." in parts or _PACKER_FOLDERS.intersection(parts):
        return None
    if parts[-1].startswith("._"):
        return None
    return "/".join(parts)


def models_in(payload: bytes) -> tuple[ArchiveModel, ...]:
    """Die Modelle in einem Archiv, nach ihrem Pfad sortiert.

    Die Grenzen stehen **vor** dem ersten Entpacken: Größe der Sendung, Zahl
    der Einträge, entpackte Größe und Packverhältnis prüft
    :func:`~app.core.ingest.loader.check_unpacked` am zentralen Verzeichnis.
    """
    check_limits(len(payload), 0)
    check_unpacked(payload, model_archive=True)
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            infos = container.infolist()
    except (zipfile.BadZipFile, OSError, ValueError) as problem:
        raise _unreadable() from problem
    found: dict[str, ArchiveModel] = {}
    locked: list[str] = []
    for info in infos:
        label = _label(info.filename)
        if label is None:
            if not info.is_dir():
                _log.info("archive entry skipped: %r", info.filename[:120])
            continue
        if PurePosixPath(label).suffix.lower() not in MODEL_SUFFIXES:
            continue
        if info.flag_bits & 0x1:
            # Verschlüsselt: Ein Kennwort fragt Solidon nicht ab, und ohne
            # lässt sich der Eintrag nicht lesen.
            locked.append(label)
            continue
        # Doppelte Namen hat ``check_unpacked`` schon auf gleichen Inhalt
        # geprüft; der erste Eintrag steht für alle.
        found.setdefault(label, ArchiveModel(info.filename, label, int(info.file_size)))
    if not found and locked:
        raise ValidationError(
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            field="file",
            detail=_(
                "Die Modelle in diesem Archiv sind mit einem Kennwort verschlüsselt. "
                "Entpacken Sie das Archiv mit dem Kennwort und legen Sie die Datei hier ab."
            ),
            constraint="encrypted",
            values={"files": ", ".join(locked[:5])},
        )
    return tuple(found[key] for key in sorted(found, key=str.casefold))


def read_model(payload: bytes, model: ArchiveModel) -> bytes:
    """Liest genau ein Modell aus dem Archiv, begrenzt wie eine Datei von der Platte.

    ``file_size`` im Verzeichnis ist eine Angabe des Archivs, kein Beweis:
    Gelesen wird höchstens ein Byte darüber hinaus, und ein Eintrag, der mehr
    entpackt, als er ankündigt, wird abgewiesen. Die Prüfsumme prüft
    ``zipfile`` beim vollständigen Lesen selbst.

    Eine GLTF bekommt ihre Begleitdateien aus demselben Archiv eingebettet —
    dieselbe Grenze wie im Ordner: kein Verweis nach außen, keiner aus ihrem
    Ordner heraus.
    """
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            data = _read_entry(container, model.entry, model.size)
            if PurePosixPath(model.label).suffix.lower() != ".gltf":
                return data
            folder = posixpath.dirname(model.label)
            entries = _entries_by_label(container)
            packed = embed_gltf_dependencies(
                model.name,
                data,
                lambda entry, uri: _archived_reference(container, entries, folder, entry, uri),
            )
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError) as problem:
        raise _unreadable(model.label) from problem
    check_limits(len(packed), 0)
    return packed


def _read_entry(container: zipfile.ZipFile, entry: str, size: int) -> bytes:
    """Ein Eintrag, höchstens ``size`` Bytes und nie mehr als eine Datei darf."""
    check_limits(size, 0)
    with container.open(entry) as stream:
        data = stream.read(min(size, MAX_FILE_BYTES) + 1)
    if len(data) > size:
        raise ValidationError(
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            field="file",
            detail=_("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
            constraint="file_too_large",
            values={"entry": entry, "announced": size},
        )
    return data


def _entries_by_label(container: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Die lesbaren Einträge nach ihrem sichtbaren Pfad."""
    entries: dict[str, zipfile.ZipInfo] = {}
    for info in container.infolist():
        label = _label(info.filename)
        if label is not None:
            entries.setdefault(label, info)
    return entries


def _archived_reference(
    container: zipfile.ZipFile,
    entries: dict[str, zipfile.ZipInfo],
    folder: str,
    entry: dict[str, Any],
    uri: str,
) -> GltfReference:
    """Eine Begleitdatei der GLTF im selben Archiv — geprüft wie im Ordner."""
    import mimetypes

    parts = urlsplit(uri)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ValidationError(
            field="file",
            detail=_(
                "Die GLTF-Datei verweist nach außen. Speichern Sie Modell und Begleitdateien "
                "in demselben Ordner oder exportieren Sie als GLB."
            ),
            constraint="scheme",
            values={"dependency": uri},
        )
    relative = unquote(parts.path).replace("\\", "/")
    joined = posixpath.normpath(posixpath.join(folder, relative)) if relative else ""
    inside = folder == "" or joined == folder or joined.startswith(f"{folder}/")
    if relative.startswith("/") or not joined or joined.startswith("..") or not inside:
        raise ValidationError(
            field="file",
            detail=_(
                "Die GLTF-Datei verweist aus ihrem Ordner heraus. Legen Sie die Begleitdatei "
                "neben das Modell oder exportieren Sie als GLB."
            ),
            constraint="absolute_path",
            values={"dependency": uri},
        )
    info = entries.get(joined)
    if info is None or info.flag_bits & 0x1:
        raise ValidationError(
            field="file",
            detail=_(
                "Zur GLTF-Datei fehlt eine Begleitdatei. Legen Sie sie neben das Modell oder "
                "exportieren Sie als GLB."
            ),
            constraint="missing_file",
            values={"dependency": uri},
        )
    media_type = mimetypes.guess_type(joined)[0] or "application/octet-stream"

    def read(limit: int) -> bytes:
        with container.open(info) as stream:
            return stream.read(limit)

    return GltfReference(entry, uri, joined, media_type, int(info.file_size), read)


def _unreadable(entry: str = "") -> ValidationError:
    """Ein Archiv oder Eintrag, den ``zipfile`` nicht entpacken kann."""
    return ValidationError(
        suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
        field="file",
        detail=_(
            "Das Archiv ließ sich nicht entpacken. Entpacken Sie es selbst und legen "
            "Sie die Modelldatei hier ab."
        ),
        constraint="unreadable",
        values={"entry": entry} if entry else {},
    )


def model_from_archive(name: str, payload: bytes, ask: AskFn | None) -> tuple[str, bytes]:
    """Das Modell aus einem Archiv: ``(dateiname, inhalt)``.

    Ein Modell darin wird genommen; bei mehreren entscheidet der Kunde
    (Regel 21), nicht die Reihenfolge im Archiv. Ohne Modell sagt die Absage,
    welche Formate Solidon liest — denn meist liegt dann eine Anleitung oder
    ein Slicer-Projekt in einem Format darin, das er selbst umwandeln kann.

    ``ask`` ist ``None``, wo niemand gefragt werden kann: Dann sind mehrere
    Modelle eine Absage mit ihren Namen, keine stille Wahl des ersten.
    """
    models = models_in(payload)
    if not models:
        raise ValidationError(
            suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            field="file",
            detail=_("In diesem Archiv liegt keine Modelldatei, die Solidon lesen kann."),
            constraint="no_model",
            values={
                "file": name,
                "formats": ", ".join(entry.lstrip(".").upper() for entry in MODEL_SUFFIXES),
            },
        )
    chosen = models[0]
    if len(models) > 1:
        labels = [model.label for model in models]
        if ask is None:
            raise ValidationError(
                suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
                field="file",
                detail=_(
                    "In diesem Archiv liegen mehrere Modelle. Entpacken Sie es und wählen "
                    "Sie die Datei, die hinein soll."
                ),
                constraint="choices",
                values={"files": ", ".join(labels[:8])},
            )
        answer = ask(str(_("Welches Modell aus dem Archiv soll hinein?")), labels)
        picked = next((model for model in models if model.label == answer), None)
        if picked is None:
            raise ValidationError(
                field="file",
                detail=_("Diese Datei steht nicht zur Auswahl."),
                value=answer,
                constraint="choices",
                values={"choices": labels},
            )
        chosen = picked
    return chosen.name, read_model(payload, chosen)
