"""Ein eigener Baustein als Rezept — Daten statt Programm (§24.5, Konzept
Befestigungssysteme §16 bis §19, Pakete E2 und E5).

Ein Rezept ist ein **Ausschnitt aus dem Op-Stapel plus die Beschreibung
seiner Parameter**: eine Liste registrierter Operationen mit Werten, die
Parameter, die der Kunde nach außen geben will, und die Merkmale, die der
fertige Baustein verspricht. Kein Python, keine Funktion, nichts, was
ausgeführt wird — seine Sicherheitslage ist die einer Projektdatei, nicht die
einer fremden ``.py`` (Regel 13, Entscheidung vom 24.08.2026).

**Und seit dem 26.08.2026 kann es auch keinen Quelltext mehr tragen.** Regel 13
nannte dafür einen Fall: ``create_from_scad`` führte seinen Parameter ``source``
als OpenSCAD-Programm aus, ein Rezept konnte diesen Schritt aufnehmen, und dann
hing an ihm die Quelltextprüfung aus §32. Mit dem OpenSCAD-Ausbau ist die
Operation entfallen; ein Rezept ist damit genau das, was der Absatz darüber
verspricht, ohne Nebensatz. Die Ansage bleibt trotzdem eingebaut — warum, steht
in :data:`app.core.scene.foreign.SCRIPTED_OPS`.

**Der Dokument-Ausschnitt reist als Dokument.** Serialisiert wird er über
``scene.serialise`` — dieselben Funktionen, die die Projektdatei schreiben.
Damit erbt ein Rezept den Migrationsweg des Dokumentformats, statt einen
zweiten zu brauchen: Öffnet eine spätere Version ein altes Rezept, laufen
dieselben Migrationen wie für eine alte Projektdatei. Die Hülle darum trägt
ihre eigene ``FORMAT_VERSION`` für das, was nur das Rezept kennt.

**Die Version ist der Hash** (§24.4, Konzept §18f): :func:`fingerprint`
rechnet über die kanonischen Daten, und ein geändertes Rezept ist damit per
Bauart ein anderes — niemand muss einen Änderungsverlauf pflegen, den es bei
eigenen Bausteinen erfahrungsgemäß nie gibt.

**Ausgewertet wird mit dem Auswerter der Szene** (:func:`build`): Parameter
hinein, ein Körper mit benannten Merkmalen heraus — der ``PartFn``-Ersatz aus
Paket E5. Ein Rezept, dessen Ausschnitt nicht auf genau einen Körper
hinausläuft, wird beim Anlegen abgewiesen und nicht später halb gebaut
(Konzept §18a).

``to_scad()`` gibt es für Rezepte nicht, und das ist benannt statt umgangen
(Konzept §18e): Für beliebige Operationen lässt sich kein OpenSCAD-Modul
bilden. Das gilt unverändert — ``to_scad`` ist ein *Ausgabeformat* für
Bausteine (:mod:`app.core.knowledge.parts.scad`) und war nie an das Programm
OpenSCAD gebunden.
"""

from __future__ import annotations

import base64
import dataclasses
import errno
import hashlib
import json
import os
import re
import stat
import tempfile
import threading
import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from app.core.errors import (
    CANCEL,
    CORRECT_INPUT,
    USE_SUGGESTED_NAME,
    GeometryError,
    ValidationError,
)
from app.core.knowledge.parts.registry import PartRegistry, PartSpec
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_parts_dir
from app.core.registry import Registry, op_params, param
from app.core.scene.migrations import migrate
from app.core.scene.serialise import document_from_data, document_to_data, has_lone_surrogate
from app.core.types import (
    BaseParams,
    Document,
    Feature,
    Finding,
    PartResult,
    Profile,
    Quality,
)
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

_FILE_LOCK = threading.RLock()
_TEMP_NAMESPACE: Final = ".solidon-recipe-"
_TEMP_SUFFIX: Final = ".atomic-tmp"
_TEMP_OWNER: Final = f"{os.getpid()}-{uuid.uuid4().hex}"
_STALE_TEMP_SECONDS: Final = 24 * 60 * 60
_TEMP_REMOVE_ATTEMPTS: Final = 3
_REMOVE_NAMESPACE: Final = ".solidon-remove-"
_REMOVE_PENDING_SUFFIX: Final = ".pending"
_REMOVE_COMMITTED_SUFFIX: Final = ".committed"
_UNSUPPORTED_DIRECTORY_SYNC: Final = frozenset(
    code
    for code in (
        errno.EINVAL,
        getattr(errno, "ENOTSUP", None),
        getattr(errno, "EOPNOTSUPP", None),
        getattr(errno, "ENOSYS", None),
    )
    if code is not None
)

#: Version der Rezept-Hülle. Der Dokument-Ausschnitt darin trägt seine eigene
#: (``document.format_version``) und reist über deren Migrationen.
FORMAT_VERSION = 1

#: Wo eigene Rezepte liegen: neben den ``.py``-Bausteinen, als eigener
#: Unterordner — eine Datei je Rezept, der Dateiname ist der Name.
RECIPES_DIRNAME = "recipes"

#: Unter welchen Lizenzen ein Rezept weitergegeben werden darf.
#:
#: **Die Quelle steht hier und nicht im Dateiprüfer.** Eine feste Wertemenge an
#: einem Rezeptfeld ist Rezept-Domäne. ``shared.rules()`` liest diese Konstante,
#: damit Import und Export dieselbe Liste prüfen.
#:
#: Alle drei erlauben die Weitergabe und die kommerzielle Nutzung — was ein
#: Kunde herunterlädt, darf er drucken und verkaufen. Was sie unterscheiden,
#: ist die Nennung des Autors und die Frage, ob eine Abwandlung wieder unter
#: dieselbe Lizenz muss.
#:
#: **Der Satz steht neben der Kennung, nicht in der Oberfläche.** „CC-BY-SA-4.0"
#: sagt einem Kunden ohne CAD-Vergangenheit nichts; was er wissen muss, ist,
#: was ein anderer mit seinem Teil tun darf. Die Kennung reist in der Datei,
#: der Satz steht im Dialog — und weil beides hier zusammenliegt, kann die
#: Liste der erlaubten Werte nicht von der Liste der erklärten abweichen.
LICENCE_LABELS: Final[dict[str, TranslatableText]] = {
    "CC0-1.0": _("Gemeinfrei — jeder darf alles, ohne Bedingung"),
    "CC-BY-4.0": _("Namensnennung — mein Name muss dabeistehen"),
    "CC-BY-SA-4.0": _("Namensnennung, und Abwandlungen unter derselben Lizenz"),
}

#: Die zulässigen Werte — abgeleitet, nicht aufgezählt. Wer eine Lizenz
#: hinzufügt, ändert diese Liste, ohne sie anzufassen.
RECIPE_LICENSES: Final = tuple(LICENCE_LABELS)

_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP_PATTERN: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

#: Kennzeichnung im Katalog (§24.5): ein Rezept ist weder ``shipped`` noch
#: eine ``user``-``.py``. Der Unterschied trägt: ``travelling_parts`` warnt
#: vor ``.py``-Bausteinen, die nie mitreisen — ein Rezept reist als Daten und
#: gehört darum ausdrücklich **nicht** in diese Warnung.
RECIPE_SOURCE = "recipe"

#: Herkunft eines Rezepts, das mit einer Projektdatei angekommen ist.
#: „Lokal schlägt mitgereist, immer" (Konzept §17.1): Es wird registriert und
#: im Katalog gekennzeichnet, aber nie in den Nutzerordner geschrieben — es
#: gehört der Datei, mit der es kam, nicht dieser Maschine.
TRAVELLED_SOURCE = "travelled"

#: Herkunft eines Rezepts, das als Datei in den lokalen Katalog übernommen
#: wurde. Diese Reise trägt nur den Abdruck der Eingangsbytes und den Zeitpunkt.
#: Der lokale Pfad gehört ausdrücklich nie in die Rezeptdatei.
IMPORTED_SOURCE = "imported"

#: Wo Rezepte in einer Projektdatei liegen (Konzept §17.1).
CONTAINER_PREFIX = "recipes/"


def container_entry(name: str) -> str:
    """Der Pfad eines Rezepts im Projektcontainer."""
    return f"{CONTAINER_PREFIX}{name}.json"


@dataclass(frozen=True, slots=True)
class ExposedParam:
    """Ein Parameter, den das Rezept nach außen gibt.

    Genau die Angaben, die ``param()`` für einen eingebauten Baustein
    verlangt (Konzept §16, Schritt 4): Titel, Einheit, Grenzen, Vorgabe,
    vorn oder hinten im Dialog, ein Satz Beschreibung. ``name`` muss ein
    Projektparameter des Ausschnitts sein — er ist die Stelle, an der der
    Wert in die Operationen fließt (``@name`` in Ausdrücken, §13).
    """

    name: str
    title: str
    default: float
    unit: str = "mm"
    minimum: float | None = None
    maximum: float | None = None
    placement: str = "front"
    """``front`` oder ``advanced`` — vorn im Dialog oder unter „Weitere Einstellungen“."""
    doc: str = ""


@dataclass(frozen=True, slots=True)
class ImportedOrigin:
    """Unmittelbare Herkunft aus einer lokalen Austauschdatei.

    Der Abdruck gilt den exakten Eingangsbytes. Der Zeitpunkt belegt die
    Aufnahme in diesen Katalog. Mehr reist absichtlich nicht mit: kein Pfad,
    kein Dateiname, keine Kontaktadresse und kein frei erweiterbares Feld.
    """

    source_sha256: str
    imported_at: str

    def __post_init__(self) -> None:
        if type(self.source_sha256) is not str or not _SHA256_PATTERN.fullmatch(self.source_sha256):
            raise ValueError("imported_origin.source_sha256")
        _require_utc_timestamp(self.imported_at, "imported_origin.imported_at")


def _require_utc_timestamp(value: object, field_name: str) -> None:
    """Verlangt die eine gespeicherte UTC-Schreibweise ohne weiche Parserfälle."""

    if type(value) is not str:
        raise TypeError(field_name)
    if not _UTC_TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError(field_name)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as problem:
        raise ValueError(field_name) from problem
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError(field_name)


@dataclass(frozen=True, slots=True)
class Recipe:
    """Ein eigener Baustein als Daten (Konzept §16)."""

    name: str
    title: str
    group: str
    document: Document
    """Der Ausschnitt: Ops, Parameter und Quellen-Metadaten, als gewöhnliches
    Dokument — die Auswertung ist dieselbe wie für ein Projekt."""
    payloads: dict[str, bytes] = field(default_factory=dict)
    """Inhalte eingebetteter Quellen des Ausschnitts. Ein Rezept aus einem
    eingelesenen Modell trägt sein Netz mit — Daten, kein Code."""
    exposed: tuple[ExposedParam, ...] = ()
    features: dict[str, str] = field(default_factory=dict)
    """Öffentlicher Merkmalsname → Merkmals-ID im ausgewerteten Körper
    (Konzept §18d): Der Dialog benennt, was nach außen sichtbar ist, sonst
    wäre die Provenienzkette an der Naht unterbrochen."""
    doc: str = ""
    license: str = ""
    """Unter welcher Lizenz das Rezept weitergegeben werden darf, oder leer.

    **Leer ist kein Fehler, sondern „nicht angegeben".** Eine Pflichtangabe
    würde jedes bestehende Rezept ungültig machen — genau die Migration, die
    zwei optionale Felder sich sparen. Der Export fragt danach, der Import
    weist fremde Herkunft aus (§32), und wo nichts steht, steht nichts.

    Der Feldname trägt die **US-Schreibung**, obwohl der Bestand sonst
    ``licence`` schreibt: ``shared.rules()`` leitet die erlaubten
    Rezeptschlüssel aus ``dataclasses.fields(Recipe)`` ab, der Feldname **ist**
    also der Schlüssel in der Regeldatei und in der Datei selbst. Eine zweite
    Schreibung wäre damit keine Geschmacksfrage, sondern eine zweite
    Übersetzungsstelle im Dateiformat. ``serialise.py`` schreibt das
    Dokumentformat aus demselben Grund schon so."""
    author: str = ""
    """Wer das Rezept gebaut hat, oder leer. Freitext — ein Name, ein
    Kürzel oder eine Adresse; der Dateivertrag prüft Länge und Typ."""
    imported_origin: ImportedOrigin | None = None
    """Woher eine lokale Austauschdatei unmittelbar kam.

    Beim Einlesen einer weiteren Datei wird diese Quittung am Import-Grenzpfad
    durch den Abdruck der neuen Eingangsbytes ersetzt. Sie beschreibt die Reise,
    nicht die Geometrie, und liegt deshalb außerhalb des Fingerabdrucks.
    """
    format_version: int = FORMAT_VERSION
    range_report: Any = None
    """Der letzte Bereichstest (:mod:`range_check`), oder ``None``.

    Am Rezept, **nicht im Hash**: Der Hash ist die Version (§24.4), und das
    Prüfen darf aus dem Rezept kein anderes machen. ``to_data`` lässt den
    Bericht deshalb aus, ``save`` schreibt ihn als eigenes Feld daneben.

    **``license`` und ``author`` liegen aus demselben Grund daneben**, und mit
    derselben Folge: Wer eine Lizenz korrigiert, ändert eine Angabe *über* das
    Teil und nicht das Teil — ein Rezept, dessen Hash dabei spränge, wäre für
    jeden, der es eingebunden hat, plötzlich ein anderes. Die Kehrseite gehört
    dazu und ist gewollt: Beide Felder liegen damit **außerhalb dessen, was die
    Version deckt**, und lassen sich ändern, ohne dass die Version es zeigt."""

    def __post_init__(self) -> None:
        if self.imported_origin is not None and not isinstance(
            self.imported_origin, ImportedOrigin
        ):
            raise TypeError("imported_origin")


def to_data(recipe: Recipe) -> dict[str, Any]:
    """Das Rezept als reine Daten, bereit für JSON."""
    return {
        "format_version": recipe.format_version,
        "name": recipe.name,
        "title": recipe.title,
        "group": recipe.group,
        "doc": recipe.doc,
        "document": document_to_data(recipe.document),
        "payloads": {
            key: base64.b64encode(value).decode("ascii")
            for key, value in sorted(recipe.payloads.items())
        },
        "exposed": [dataclasses.asdict(entry) for entry in recipe.exposed],
        "features": dict(sorted(recipe.features.items())),
    }


#: Die Unicode-Kategorien, die in einem Rezepttext nichts zu suchen haben:
#: Steuerzeichen (``Cc``) sowie Zeilen- und Absatztrenner (``Zl``, ``Zp``).
#: Für ``doc`` gilt es abgeschwächt — ein Beschreibungstext darf Absätze haben.
_TEXT_BAN: Final = frozenset({"Cc", "Zl", "Zp"})


def _checked_text(value: str, limit: int, field: str, *, paragraphs: bool = False) -> str:
    """Ein Textfeld eines Rezepts, auf Länge und Zeichen geprüft.

    Beide Prüfungen fehlten auf dem **Adopt-Weg** vollständig: ``adopt`` und
    ``adopt_payload`` rufen :func:`from_data` unmittelbar auf, und die strengen
    Prüfungen aus ``part_file.PartFileIO._strict_shape`` — samt
    ``MAX_TITLE_CHARS`` und ``MAX_DOC_CHARS`` — gelten nur für den lokalen
    ``.solidon-part``-Import. Ein Rezept aus einer fremden Projektdatei trug
    damit einen Titel beliebiger Länge und beliebigen Inhalts, und der reist
    weit: ins Handbuch, in den Katalog, in die Menüs und in die Befehlspalette
    (Sicherheitsdurchsicht 04.09.2026).

    **Markdown bleibt erlaubt**, und zwar bewusst: ``doc`` wird als
    Markdown-Absatz ins Handbuch gesetzt, das ist sein Zweck. Wohin ein Link
    darin führen darf, entscheidet die Anzeige — bei
    ``ui.manual_window.ManualWindow._open_link`` eine Positivliste, bei
    ``ui.catalog`` das Maskieren, im Website-Handbuch ``core.markup``. Die
    Entscheidung gehört dorthin, weil dieselben Texte in der Kommandozeile
    schlicht Text sind und dort nichts zu maskieren ist.
    """
    if len(value) > limit:
        raise ValueError(f"recipe_text:{field}")
    for char in value:
        # Die zwei üblichen Zeilenenden bleiben in einem Absatztext erlaubt.
        # Sie einzuschließen ist keine Nachlässigkeit: Eine von Hand
        # geschriebene Rezeptdatei trägt unter Windows ``\r\n``, und sie
        # deshalb abzuweisen wäre eine Grenze gegen den eigenen Nutzer. Die
        # abwegigen Trenner (``\v``, ``\x85``, LINE und PARAGRAPH SEPARATOR)
        # fallen weiter durch — sie stehen in keinem geschriebenen Text.
        if paragraphs and char in "\n\r":
            continue
        if unicodedata.category(char) in _TEXT_BAN:
            raise ValueError(f"recipe_text:{field}")
    return value


def from_data(data: dict[str, Any]) -> Recipe:
    """Ein Rezept aus seinen Daten. Der Dokument-Teil läuft durch die
    Migrationen des Dokumentformats — ein altes Rezept öffnet wie eine alte
    Projektdatei.

    Die Textfelder gehen durch :func:`_checked_text`. Das gilt für **beide**
    Wege hierher: den lokalen Bausteinimport, der ohnehin streng prüft, und
    das mitgereiste Rezept einer fremden Projektdatei, das es nicht tat.
    """
    # Träge, weil ``shared`` aus diesem Modul importiert — auf Modulebene wäre
    # es ein Zirkelbezug. Dasselbe Muster wie bei ``part_ops`` weiter unten.
    from app.core.knowledge.parts import shared

    if has_lone_surrogate(data):
        raise ValueError("unicode_scalar")
    return Recipe(
        name=str(data["name"]),
        title=_checked_text(
            str(data.get("title") or data["name"]), shared.MAX_TITLE_CHARS, "title"
        ),
        group=_checked_text(str(data.get("group", "structure")), 120, "group"),
        doc=_checked_text(str(data.get("doc", "")), shared.MAX_DOC_CHARS, "doc", paragraphs=True),
        # Durch die Migrationen, wie eine Projektdatei: Der Dokumentteil
        # eines Rezepts altert mit dem Dokumentformat, und eine Datei aus
        # der Zukunft wird abgewiesen statt falsch gelesen (``too_new``).
        document=document_from_data(migrate(dict(data["document"]))),
        payloads={
            key: base64.b64decode(value) for key, value in dict(data.get("payloads", {})).items()
        },
        exposed=tuple(ExposedParam(**entry) for entry in data.get("exposed", ())),
        features=dict(data.get("features", {})),
        format_version=int(data.get("format_version", 1)),
        license=str(data.get("license", "")),
        author=str(data.get("author", "")),
        imported_origin=_imported_origin_from(data.get("imported_origin")),
        range_report=_report_from(data.get("range_report")),
    )


def _imported_origin_from(data: Any) -> ImportedOrigin | None:
    """Liest die optionale Dateiherkunft ohne lokale Pfade oder freie Felder."""

    if data is None:
        return None
    if not isinstance(data, dict):
        raise TypeError("imported_origin")
    expected = {"source_sha256", "imported_at"}
    if set(data) != expected:
        raise ValueError("imported_origin")
    for key in expected:
        if type(data[key]) is not str:
            raise TypeError(f"imported_origin.{key}")
    return ImportedOrigin(
        source_sha256=data["source_sha256"],
        imported_at=data["imported_at"],
    )


def _report_from(data: Any) -> Any:
    """Der gespeicherte Bericht, oder ``None`` — er ist Zugabe, kein Muss."""
    if not data:
        return None
    from app.core.knowledge.parts.range_check import RangeFailure, RangeReport

    return RangeReport(
        checked=int(data.get("checked", 0)),
        failures=tuple(
            RangeFailure(values=dict(entry["values"]), reason=str(entry["reason"]))
            for entry in data.get("failures", ())
        ),
    )


def fingerprint(recipe: Recipe) -> str:
    """Der Hash über die kanonischen Daten — er **ist** die Version (§24.4).

    Kanonisch heißt: sortierte Schlüssel, keine Zeitstempel, nichts
    Maschinenabhängiges. Zwei gleiche Rezepte geben denselben Wert, jede
    Änderung einen anderen — und der Vergleich beim Öffnen eines Projekts ist
    damit derselbe wie für jeden anderen Baustein.
    """
    canon = json.dumps(to_data(recipe), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# --- Auswertung (E5): der PartFn-Ersatz ------------------------------------------


def build(
    recipe: Recipe,
    values: dict[str, float] | None = None,
    *,
    profile: Profile,
    quality: Quality = "fine",
    registry: Registry | None = None,
) -> PartResult:
    """Parameter hinein, ein Körper mit benannten Merkmalen heraus.

    Der Ausschnitt wird mit dem **Auswerter der Szene** gerechnet — derselbe
    Weg, denselben Regeln: Rückfallkette, ``auto:``-Toleranzen aus dem
    Profil, Prüfungen nach jedem Schritt. Ein zweiter Auswerter nur für
    Rezepte wäre eine zweite Wahrheit.

    Läuft der Ausschnitt nicht auf **genau einen** Körper hinaus, hält das
    hier an (Konzept §18a): Ein Baustein ist eine Funktion, ein Stapel ein
    Ablauf, und aufnehmbar ist nur, was sich wie eine Funktion verhält.
    """
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import Project, ProjectSources

    document = _with_values(recipe.document, recipe, values or {})
    project = Project(document=document, sources=dict(recipe.payloads))
    result = evaluate(
        document,
        profile,
        quality=quality,
        registry=registry,
        sources=ProjectSources(project),
    )
    if result.stopped_at is not None:
        # ``evaluate`` wirft bei einem gescheiterten Schritt nicht — es setzt
        # ``stopped_at`` und behält, was bis dahin entstand. Für ein Projekt
        # ist das richtig (der Verlauf zeigt den Riss); für einen Baustein
        # wäre es ein halber Körper, der wie ein ganzer aussieht: Ein Rezept
        # aus Quader und Bohrung gäbe bei gescheiterter Differenz den Klotz
        # ohne Loch zurück, und der Bereichstest hielte ihn für bestanden.
        cause = next((str(entry.message) for entry in result.scene.report.findings), "")
        raise GeometryError(
            title=_("Das Rezept ließ sich nicht bis zum Ende rechnen."),
            detail=cause or _("Ein Schritt des Rezepts scheiterte an dieser Parameterkombination."),
            values={"recipe": recipe.name, "stopped_at": result.stopped_at},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    bodies = list(result.scene.objects.values())
    if len(bodies) != 1:
        raise ValidationError(
            field="recipe",
            # Ohne Platzhalter: ``show_details`` zeigt den Satz wörtlich und
            # hängt die ``values`` als eigene Zeilen darunter — ein ``{count}``
            # bliebe als geschweifte Klammer stehen (tests/test_errors.py).
            detail=_(
                "Dieses Rezept ergibt nicht genau einen Körper. Ein Baustein "
                "ist genau ein Teil — teilen Sie den Ausschnitt oder vereinen "
                "Sie die Körper, bevor Sie speichern."
            ),
            values={"count": len(bodies), "recipe": recipe.name},
            constraint="one_body",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    body = bodies[0]
    features: dict[str, Feature] = {}
    for public, internal in recipe.features.items():
        found = body.features.get(internal)
        if found is None:
            raise ValidationError(
                field="features",
                detail=_(
                    "Ein benanntes Merkmal gibt es im Ergebnis nicht mehr. "
                    "Benennen Sie die Merkmale des Rezepts neu, oder entfernen "
                    "Sie den Eintrag."
                ),
                values={"name": public, "missing": internal, "recipe": recipe.name},
                constraint="unknown_feature",
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        # **Mit dem Namen wechselt die Provenienz.** Das Rezept hat diesem
        # Merkmal einen Namen gegeben — ab jetzt ist es ein *erzeugtes*, wie
        # bei jedem eingebauten Baustein: Eine Passung darf darauf zeigen, der
        # Agent darf darauf verweisen (§21.3, Leitprinzip 5). Als ``detected``
        # weitergereicht verwaiste es still bei der nächsten Wiedererkennung —
        # gemessen am E6-Durchlauf: Der Deckel eines Rezepts aus einem
        # eingelesenen Netz verschwand nach dem Einsetzen als
        # ``perceive.orphaned``, während derselbe Deckel aus ``create_box``
        # (dort von Haus aus erzeugt) blieb. Genau das ist die Naht, von der
        # Konzept §18d spricht.
        features[public] = dataclasses.replace(found, id=public, provenance="generated")
    return PartResult(
        mesh=body.mesh, features=features, findings=list(result.scene.report.findings)
    )


def _with_values(document: Document, recipe: Recipe, values: dict[str, float]) -> Document:
    """Der Ausschnitt mit den eingesetzten Parameterwerten — als Kopie.

    Nur freigegebene Parameter sind setzbar; alles andere wäre ein Weg, am
    Dialog vorbei in ein fremdes Rezept zu greifen. Der Wert ersetzt Wert
    **und** Ausdruck des Projektparameters: Ein Ausdruck bliebe sonst die
    stärkere Quelle, und der Dialogwert täte nichts.

    **Und das Wegschneiden bleibt, obwohl es einmal Arbeit gekostet hat.**
    Ein Weg-2-Projekt mit ``breite = 40`` und ``hoehe = =@breite/2`` wurde als
    Baustein gespeichert und hatte darin zwei unabhängige Felder: „Breite" auf
    60 ließ „Höhe" auf 20 stehen statt auf 30. Die Frage war, ob hier ein
    Befund fällig ist — die Antwort ist nein, und zwar aus dem Verhalten
    heraus:

    * **Hier ist der Schnitt richtig.** Wer einen Wert von außen hereingibt,
      meint ihn; ein überlebender Ausdruck machte aus dem Feld im
      Bausteindialog eine Attrappe, die nichts bewirkt (§13 — der Ausdruck
      besitzt den Wert, also muss einer von beiden weichen).
    * **Und der Schnitt ist nicht die Stelle, an der jemand entscheidet.**
      Entschieden wird beim *Freigeben*, also einmal in :func:`capture`, und
      nicht bei jedem Bauen. Ein Befund an dieser Stelle stünde in jedem
      Prüfbericht jedes Projekts, das den Baustein benutzt — für eine
      Entscheidung, die längst gefallen ist.
    * **Ein Befund braucht einen Leser.** :func:`capture` hat genau einen
      Aufrufer, den Rezeptdialog, und der fragt jetzt vorher: Eine Zeile mit
      Ausdruck geht **ohne** Haken auf und sagt daneben, was ein Haken dort
      bedeutet (``app/ui/recipe_dialog.py``). Ein zweiter Befund daneben, den
      niemand abholt, wäre eine Kette, die vor ihrem letzten Glied endet.

    Kommt ein zweiter Aufrufer dazu — ein Agentenwerkzeug, die
    Kommandozeile —, gehört die Frage nach :func:`capture` und nicht hierher.
    """
    exposed = {entry.name for entry in recipe.exposed}
    unknown = sorted(set(values) - exposed)
    if unknown:
        raise ValidationError(
            field="values",
            detail=_("Diesen Parameter gibt das Rezept nicht nach außen."),
            values={"unknown": ", ".join(unknown), "recipe": recipe.name},
            constraint="unknown",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    parameters = dict(document.parameters)
    for name, value in values.items():
        current = parameters.get(name)
        if current is None:
            raise ValidationError(
                field="exposed",
                detail=_(
                    "Ein freigegebener Parameter steht nicht im "
                    "Ausschnitt. Legen Sie ihn im Projekt an, bevor Sie ihn "
                    "freigeben."
                ),
                values={"name": name, "recipe": recipe.name},
                constraint="unknown_parameter",
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        parameters[name] = dataclasses.replace(current, value=float(value), expression="")
    return dataclasses.replace(document, parameters=parameters)


# --- Anschluss an Katalog und Register (E1/E5) -----------------------------------


def _params_class(recipe: Recipe) -> type[BaseParams]:
    """Die Parameterklasse des Rezepts — aus Daten, denselben Weg entlang.

    Eine **rohe** Klasse, kein fertiges Dataclass: ``op_params`` friert
    selbst ein und leitet das Schema ab — wie bei jeder deklarierten
    Parameterklasse, nur dass Annotationen und ``param()``-Felder hier aus
    Daten entstehen. Registrierung und Bereichstest teilen sich diese eine
    Fassung; zwei drifteten auseinander.
    """
    namespace: dict[str, Any] = {
        "__annotations__": {entry.name: float for entry in recipe.exposed},
        "__module__": __name__,
    }
    for entry in recipe.exposed:
        namespace[entry.name] = param(
            title=entry.title,
            default=float(entry.default),
            unit=entry.unit,
            minimum=entry.minimum,
            maximum=entry.maximum,
            placement="front" if entry.placement == "front" else "advanced",
            doc=entry.doc or entry.title,
        )
    return op_params(type(f"Recipe_{recipe.name}_Params", (BaseParams,), namespace))


def range_check(
    recipe: Recipe,
    profile: Profile,
    *,
    progress: Any = None,
    cancelled: Any = None,
) -> Recipe:
    """Der Bereichstest über die freigegebenen Grenzen (§24.5, Konzept E3).

    Fährt die Ecken mit der **echten Auswertung** und gibt das Rezept mit
    Bericht zurück — der Hash bleibt derselbe, denn der Bericht steht
    außerhalb (siehe ``Recipe.range_report``). Der Aufrufer entscheidet, ob
    ein gebrochener Bericht das Speichern verhindert; §24.5 verlangt den
    Warnhinweis im Katalog, kein Verbot.
    """
    from app.core.knowledge.parts.range_check import check

    params_cls = _params_class(recipe)

    def built(values: BaseParams) -> PartResult:
        raw = {entry.name: float(getattr(values, entry.name)) for entry in recipe.exposed}
        return build(recipe, raw, profile=profile)

    report = check(params_cls, built, profile, progress=progress, cancelled=cancelled)
    return dataclasses.replace(recipe, range_report=report)


def register(
    recipe: Recipe,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    *,
    source: str = RECIPE_SOURCE,
) -> None:
    """Macht aus dem Rezept einen Baustein wie jeden anderen.

    Das Parameterschema entsteht aus den freigegebenen Parametern — dieselbe
    Deklaration, die ein eingebauter Baustein über ``param()`` trägt, nur aus
    Daten gebaut. Registriert wird über denselben Weg wie jede ``.py``
    (``ops.register_all``-Mechanik), damit Katalog, Palette, Dialog und
    Provenienz nichts Neues lernen müssen.

    ``fn`` wertet mit dem **Standardprofil** aus — das trifft Vorschaubild
    und Bereichstest. Beim echten Einsetzen läuft stattdessen
    ``build_with_profile`` mit dem Profil des Dokuments (``ops.insert``
    bevorzugt es): Eine ``auto:``-Toleranz im Rezept rechnet dann mit dem
    Material des Kunden, nicht mit unserem.

    **Und mit der Qualitätsstufe des Aufrufers.** Ein Rezept ist der teuerste
    Baustein, den es gibt: Es rechnet keinen Körper, sondern einen ganzen
    Stapel durch denselben Auswerter, mitsamt Rückfallkette je Schritt. Genau
    dort muss ``draft`` durchkommen, sonst rechnet die Iteration in Feinheit
    (Checkliste „neuer Baustein", Punkt 5). ``quality`` steht deshalb als
    dritter, vorbelegter Parameter — ein Aufrufer, der nur zwei kennt (der
    Typ ``BuildWithProfile``), ruft weiter wie bisher und bekommt ``fine``.
    """
    from app.core.knowledge.parts import ops as part_ops
    from app.core.knowledge.parts.registry import PARTS

    params_cls = _params_class(recipe)

    def build_with_profile(
        params: BaseParams, profile: Profile | None, quality: Quality = "fine"
    ) -> PartResult:
        chosen = profile or _default_profile()
        values = {entry.name: float(getattr(params, entry.name)) for entry in recipe.exposed}
        return build(recipe, values, profile=chosen, quality=quality)

    def fn(params: BaseParams) -> PartResult:
        return build_with_profile(params, None)

    spec = PartSpec(
        name=recipe.name,
        title=recipe.title,
        group=recipe.group,
        params=params_cls,
        fn=fn,
        build_with_profile=build_with_profile,
        version=fingerprint(recipe),
        features=tuple(recipe.features),
        doc=recipe.doc or recipe.title,
        source=source,
        range_passed=(recipe.range_report.passed if recipe.range_report is not None else None),
        # Für die Reise: Das Speichern eines Projekts, das diesen Baustein
        # benutzt, bettet genau diese Daten in den Container ein — ohne die
        # Datei im Nutzerordner erneut zu lesen, die ein mitgereistes Rezept
        # gar nicht hat.
        recipe_data=file_data(recipe),
    )
    target = parts or PARTS
    target.register(spec)
    try:
        part_ops.register_one(spec, registry)
    except Exception:
        # Halb registriert ist schlimmer als gar nicht: Ein Katalogeintrag
        # ohne Operation ist ein Knopf, dessen Klick in einem
        # ``InternalError`` endet. Der Eintrag geht zurück, der Fehler weiter.
        target.remove(spec.name)
        raise


def _default_profile() -> Profile:
    """Das Profil für Vorschau und Bereichstest, wo keines mitkommt.

    ``make_profile()`` ohne Argumente — also die **Vorgaben** der Anwendung,
    nicht das erste Paar der Titelsortierung: Die nahm ABS statt PLA, und
    damit rechneten Vorschaubild und Bereichstest jedes Rezepts mit
    ABS-Toleranzen (Fund des Gesamtreviews vom 25.08.2026).
    """
    from app.core.knowledge import profiles

    return profiles.make_profile()


# --- Ablage im Nutzerordner -------------------------------------------------------


def recipes_dir(base: Path | None = None) -> Path:
    """Wo die Rezepte liegen: ein Unterordner des Bausteinordners."""
    return (base or user_parts_dir()) / RECIPES_DIRNAME


def _encoded_file(recipe: Recipe) -> bytes:
    """Die kanonischen Rezeptbytes für die dauerhafte Ablage."""

    return (
        json.dumps(file_data(recipe), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_all(descriptor: int, payload: bytes) -> None:
    """Schreibt alle Bytes oder lässt den Dateinamen weiterhin unsichtbar."""

    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("recipe_write_stopped")
        remaining = remaining[written:]
    os.fsync(descriptor)


def _sync_directory(directory: Path) -> None:
    """Sichert den Verzeichniseintrag, wo das Betriebssystem das unterstützt."""

    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError as problem:
        if problem.errno in _UNSUPPORTED_DIRECTORY_SYNC:
            return
        raise
    try:
        os.fsync(descriptor)
    except OSError as problem:
        if problem.errno not in _UNSUPPORTED_DIRECTORY_SYNC:
            raise
    finally:
        os.close(descriptor)


class _PublishedFileError(BaseException):
    """Bewahrt den Commitstatus, wenn nach der Veröffentlichung etwas abbricht."""

    def __init__(self, problem: BaseException) -> None:
        super().__init__(str(problem))
        self.problem = problem


@dataclass(frozen=True, slots=True)
class StoredFileMetadata:
    """Die wiederherstellbaren Metadaten einer lokalen Rezeptdatei."""

    mode: int
    atime_ns: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class RemovedRecipeFile:
    """Der pfadfreie, bytegenaue Stand eines entfernten lokalen Rezepts."""

    name: str
    source: str
    payload: bytes
    metadata: StoredFileMetadata
    recipe: Recipe


def _temporary_pattern(target_name: str | None = None) -> str:
    """Der exklusive Namensraum für atomare Rezeptdateien dieses Ziels."""

    if target_name is None:
        return f"{_TEMP_NAMESPACE}*{_TEMP_SUFFIX}"
    return f"{_TEMP_NAMESPACE}*.{target_name}.*{_TEMP_SUFFIX}"


def _owned_by_current_user(info: os.stat_result) -> bool:
    """Ob der portable Besitzervergleich das Aufräumen erlaubt."""

    get_effective_user = getattr(os, "geteuid", None)
    if get_effective_user is None:
        return True
    effective_user = int(get_effective_user())
    return info.st_uid == effective_user


def _remove_temporary(path: Path) -> OSError | None:
    """Versucht eine eigene Tempdatei erneut und sichert ihre Entfernung."""

    last_problem: OSError | None = None
    for _attempt in range(_TEMP_REMOVE_ATTEMPTS):
        try:
            path.unlink()
        except FileNotFoundError:
            return None
        except OSError as problem:
            last_problem = problem
            continue
        _sync_directory(path.parent)
        return None
    return last_problem


def _cleanup_stale_temporaries(
    directory: Path,
    *,
    target_name: str | None = None,
    now: float | None = None,
) -> None:
    """Räumt nur alte, reguläre Solidon-Tempdateien desselben Besitzers."""

    cutoff = (time.time() if now is None else now) - _STALE_TEMP_SECONDS
    for candidate in directory.glob(_temporary_pattern(target_name)):
        try:
            info = candidate.lstat()
            belongs_to_process = candidate.name.startswith(f"{_TEMP_NAMESPACE}{_TEMP_OWNER}.")
            if (
                not stat.S_ISREG(info.st_mode)
                or not _owned_by_current_user(info)
                or (not belongs_to_process and info.st_mtime > cutoff)
            ):
                continue
            problem = _remove_temporary(candidate)
            if problem is not None:
                _log.warning(
                    "stale recipe temporary file %s could not be removed: %s",
                    candidate.name,
                    problem,
                )
        except FileNotFoundError:
            continue
        except OSError as problem:
            _log.warning(
                "stale recipe temporary file %s could not be inspected: %s",
                candidate.name,
                problem,
            )


def _publish_file(
    target: Path,
    payload: bytes,
    *,
    overwrite: bool,
    on_published: Callable[[], None] | None = None,
    prepare_file: Callable[[int, Path], None] | None = None,
) -> None:
    """Veröffentlicht vollständige Bytes atomar und meldet den Commitstatus."""

    with _FILE_LOCK:
        _cleanup_stale_temporaries(target.parent, target_name=target.name)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f"{_TEMP_NAMESPACE}{_TEMP_OWNER}.{target.name}.",
            suffix=_TEMP_SUFFIX,
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        closed = False
        published = False
        failure: BaseException | None = None
        try:
            _write_all(descriptor, payload)
            if prepare_file is not None:
                prepare_file(descriptor, temporary)
                os.fsync(descriptor)
            os.close(descriptor)
            closed = True
            if overwrite:
                temporary.replace(target)
            else:
                # Der harte Link ist im selben Verzeichnis atomar und ersetzt nie
                # eine vorhandene Kundendatei. Ein vorheriges ``exists()`` hätte
                # zwischen Prüfung und Veröffentlichung ein Zeitfenster gelassen.
                os.link(temporary, target)
            published = True
            if on_published is not None:
                on_published()
            _sync_directory(target.parent)
        except BaseException as problem:
            failure = problem

        if not closed:
            try:
                os.close(descriptor)
            except BaseException as problem:
                if failure is None:
                    failure = problem

        try:
            cleanup_problem = _remove_temporary(temporary)
        except BaseException as problem:
            if failure is None:
                failure = problem
        else:
            if cleanup_problem is not None:
                if published:
                    _log.warning(
                        "recipe temporary file %s remains after publication: %s",
                        temporary.name,
                        cleanup_problem,
                    )
                elif failure is None:
                    failure = cleanup_problem
                else:
                    _log.warning(
                        "recipe temporary file %s remains after failed publication: %s",
                        temporary.name,
                        cleanup_problem,
                    )

        if failure is not None:
            if published:
                raise _PublishedFileError(failure) from failure
            raise failure


def _save(
    recipe: Recipe,
    directory: Path | None = None,
    *,
    overwrite: bool = False,
    on_published: Callable[[], None] | None = None,
) -> Path:
    """Interner Speicherweg, der einen bereits erfolgten Commit kennzeichnet."""

    folder = ensure_dir(recipes_dir() if directory is None else directory)
    target = folder / f"{recipe.name}.json"
    payload = _encoded_file(recipe)
    try:
        _publish_file(target, payload, overwrite=overwrite, on_published=on_published)
    except FileExistsError as problem:
        raise _existing_recipe_error(recipe.name, target.name) from problem
    return target


def publish_payload(target: Path, payload: bytes) -> Path:
    """Schreibt eine bereits geprüfte Bausteindatei atomar an ein Nutzerziel."""

    ensure_dir(target.parent)
    try:
        _publish_file(target, payload, overwrite=True)
    except _PublishedFileError as problem:
        _log.warning(
            "published recipe payload completed after %s",
            type(problem.problem).__name__,
        )
    return target


def save(recipe: Recipe, directory: Path | None = None, *, overwrite: bool = False) -> Path:
    """Schreibt das Rezept als eine Datei; der Dateiname ist der Name.

    Eine vorhandene Datei ist Kundenarbeit: Ersetzt wird nur mit
    ``overwrite=True`` — „Ändern heißt neu speichern" ist der gewollte Fall,
    und den sagt der Aufrufer ausdrücklich. Ohne diese Absicht hält die
    Funktion an, statt still zu tauschen. Der Dialog lief am 25.08.2026 in
    genau diese Falle: ``register()`` lehnte den doppelten Namen ab, nachdem
    ``save()`` die alte Datei bereits überschrieben hatte — die Meldung sprach
    von einem Fehlschlag, die Platte trug längst den Verlust.
    """
    try:
        return _save(recipe, directory, overwrite=overwrite)
    except _PublishedFileError as problem:
        _log.warning(
            "published recipe save completed after %s",
            type(problem.problem).__name__,
        )
        folder = recipes_dir() if directory is None else directory
        return folder / f"{recipe.name}.json"


def _existing_recipe_error(name: str, filename: str, *, suggested: str = "") -> ValidationError:
    """Der gemeinsame, handlungsfähige Befund für eine Namenskollision."""

    values = {"recipe": name, "file": filename}
    if suggested:
        values["suggested_name"] = suggested
    suggestions = (USE_SUGGESTED_NAME, CANCEL) if suggested else (CORRECT_INPUT, CANCEL)
    return ValidationError(
        field="title",
        detail=_(
            "Unter diesem Namen liegt schon ein Baustein. Behalten Sie den vorhandenen "
            "und übernehmen Sie die Datei unter dem vorgeschlagenen anderen Namen."
        ),
        values=values,
        constraint="exists",
        suggestions=suggestions,
    )


def available_name(
    name: str,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    directory: Path | None = None,
) -> str:
    """Der erste freie Importname in Datei, Katalog und Operationsregister."""

    from app.core.knowledge.parts import ops as part_ops
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    source = parts or PARTS
    operations = registry or REGISTRY
    folder = recipes_dir() if directory is None else directory

    def free(candidate: str) -> bool:
        return (
            not source.has(candidate)
            and not operations.has(part_ops.op_name(candidate))
            and not (folder / f"{candidate}.json").exists()
        )

    if free(name):
        return name
    stem = name[:110].rstrip("_") or "imported_part"
    candidate = f"{stem}_imported"
    number = 2
    while not free(candidate):
        suffix = f"_imported_{number}"
        candidate = f"{stem[: 120 - len(suffix)].rstrip('_')}{suffix}"
        number += 1
    return candidate


@dataclass(frozen=True)
class _PreparedBinding:
    """Der vollständig geprüfte Katalog- und Operationsstand nach dem Commit."""

    parts: PartRegistry
    operations: Registry


def _prepare_binding(
    recipe: Recipe,
    parts: PartRegistry,
    operations: Registry,
    *,
    replace_existing: bool,
) -> _PreparedBinding:
    """Baut den ganzen Folgezustand, ohne die laufende Sitzung zu verändern."""

    from app.core.knowledge.parts import ops as part_ops

    operation_name = part_ops.op_name(recipe.name)
    prepared_parts = PartRegistry()
    prepared_operations = Registry()
    for part_spec in parts.all():
        if replace_existing and part_spec.name == recipe.name:
            continue
        prepared_parts.register(part_spec)
    for operation_spec in operations.all():
        if replace_existing and operation_spec.name == operation_name:
            continue
        prepared_operations.register(operation_spec)
    register(
        recipe,
        prepared_parts,
        prepared_operations,
        source=_catalog_source(recipe),
    )
    return _PreparedBinding(prepared_parts, prepared_operations)


def _prepare_removal(
    name: str,
    parts: PartRegistry,
    operations: Registry,
) -> _PreparedBinding:
    """Baut den vollständigen Registerstand ohne ein lokales Rezept."""

    from app.core.knowledge.parts import ops as part_ops

    operation_name = part_ops.op_name(name)
    if not parts.has(name) or not operations.has(operation_name):
        raise ValueError("recipe_binding_missing")
    prepared_parts = PartRegistry()
    prepared_operations = Registry()
    for part_spec in parts.all():
        if part_spec.name != name:
            prepared_parts.register(part_spec)
    for operation_spec in operations.all():
        if operation_spec.name != operation_name:
            prepared_operations.register(operation_spec)
    return _PreparedBinding(prepared_parts, prepared_operations)


def _activate_prepared(
    parts: PartRegistry,
    operations: Registry,
    prepared: _PreparedBinding,
) -> None:
    """Aktiviert nach dem Platten-Commit beide vorgeprüften Registerstände."""

    try:
        parts.replace_state(prepared.parts)
        operations.replace_state(prepared.operations)
    except BaseException as problem:
        # Eine asynchrone Unterbrechung zwischen den beiden Referenzwechseln
        # darf keinen halben Zustand hinterlassen. Die Zuweisungen selbst
        # validieren und allokieren nichts mehr und können wiederholt werden.
        # Gelingt die Reparatur, ist die sichtbare Handlung erfolgreich und
        # darf nicht mit einem unbrauchbaren Retry beantwortet werden.
        try:
            parts.replace_state(prepared.parts)
            operations.replace_state(prepared.operations)
        except BaseException as retry_problem:
            raise retry_problem from problem
        _log.warning(
            "recipe registry activation recovered after %s",
            type(problem).__name__,
        )


def _save_and_activate(
    recipe: Recipe,
    parts: PartRegistry,
    operations: Registry,
    prepared: _PreparedBinding,
    directory: Path | None,
    *,
    overwrite: bool,
) -> Path:
    """Veröffentlicht die Datei und rollt danach ausschließlich vorwärts."""

    def activate() -> None:
        _activate_prepared(parts, operations, prepared)

    try:
        return _save(
            recipe,
            directory,
            overwrite=overwrite,
            on_published=activate,
        )
    except _PublishedFileError as problem:
        # Rename/Link ist bereits geschehen. Selbst ein Fehler im ersten
        # Aktivierungsversuch oder beim Verzeichnis-fsync wird deshalb durch
        # denselben vorbereiteten Zustand aufgelöst, nie durch Plattenrollback.
        _activate_prepared(parts, operations, prepared)
        _log.warning(
            "published recipe binding completed after %s",
            type(problem.problem).__name__,
        )
        folder = recipes_dir() if directory is None else directory
        return folder / f"{recipe.name}.json"


def _read_stored_file(target: Path) -> tuple[bytes, StoredFileMetadata]:
    """Liest Bytes und wiederherstellbare Dateimetadaten aus derselben Datei."""

    before = target.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise OSError(errno.EINVAL, "recipe_not_regular")
    with target.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise OSError(errno.EBUSY, "recipe_changed_during_read")
        payload = stream.read()
        after = os.fstat(stream.fileno())
    if (
        (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
        or after.st_size != opened.st_size
        or after.st_mtime_ns != opened.st_mtime_ns
    ):
        raise OSError(errno.EBUSY, "recipe_changed_during_read")
    return payload, StoredFileMetadata(
        mode=stat.S_IMODE(before.st_mode),
        atime_ns=before.st_atime_ns,
        mtime_ns=before.st_mtime_ns,
    )


def _removal_paths(target: Path) -> tuple[Path, Path]:
    """Zwei exklusive Namen für Vorbereitung und Commit einer Entfernung."""

    identity = uuid.uuid4().hex
    stem = f"{_REMOVE_NAMESPACE}{_TEMP_OWNER}.{target.name}.{identity}"
    return (
        target.parent / f"{stem}{_REMOVE_PENDING_SUFFIX}",
        target.parent / f"{stem}{_REMOVE_COMMITTED_SUFFIX}",
    )


def _removal_target(candidate: Path, suffix: str) -> Path | None:
    """Liest nur eigene, vollständig geformte Quarantänenamen."""

    pattern = re.compile(
        rf"^{re.escape(_REMOVE_NAMESPACE)}"
        rf"(?P<owner>\d+-[0-9a-f]+)\."
        rf"(?P<target>[a-z][a-z0-9_]*\.json)\."
        rf"[0-9a-f]{{32}}{re.escape(suffix)}$"
    )
    match = pattern.fullmatch(candidate.name)
    if match is None:
        return None
    return candidate.parent / match.group("target")


def _restore_pending_removal(pending: Path, target: Path) -> None:
    """Legt eine nicht festgeschriebene Entfernung ohne Überschreiben zurück."""

    os.link(pending, target)
    pending.unlink()
    _sync_directory(target.parent)


def _recover_interrupted_removals(directory: Path) -> None:
    """Stellt Vorbereitungen zurück und räumt festgeschriebene Entfernungen auf."""

    for pending in directory.glob(f"{_REMOVE_NAMESPACE}*{_REMOVE_PENDING_SUFFIX}"):
        try:
            if not stat.S_ISREG(pending.lstat().st_mode):
                continue
            target = _removal_target(pending, _REMOVE_PENDING_SUFFIX)
            if target is None:
                continue
            if target.exists():
                _log.warning(
                    "pending recipe removal %s conflicts with an existing target",
                    pending.name,
                )
                continue
            _restore_pending_removal(pending, target)
        except (FileExistsError, FileNotFoundError):
            continue
        except OSError as problem:
            _log.warning(
                "pending recipe removal %s could not be restored: %s",
                pending.name,
                problem,
            )
    for committed in directory.glob(f"{_REMOVE_NAMESPACE}*{_REMOVE_COMMITTED_SUFFIX}"):
        try:
            if not stat.S_ISREG(committed.lstat().st_mode):
                continue
            target = _removal_target(committed, _REMOVE_COMMITTED_SUFFIX)
            if target is None:
                continue
            committed.unlink()
            _sync_directory(directory)
        except FileNotFoundError:
            continue
        except OSError as problem:
            _log.warning(
                "committed recipe removal %s could not be cleaned: %s",
                committed.name,
                problem,
            )


def _commit_removal_and_activate(
    pending: Path,
    committed: Path,
    parts: PartRegistry,
    operations: Registry,
    prepared: _PreparedBinding,
) -> None:
    """Schreibt die Entfernung fest und rollt danach nur noch vorwärts."""

    published = False
    try:
        pending.replace(committed)
        published = True
        _activate_prepared(parts, operations, prepared)
        _sync_directory(committed.parent)
    except BaseException as problem:
        if published:
            _activate_prepared(parts, operations, prepared)
            raise _PublishedFileError(problem) from problem
        raise
    try:
        committed.unlink()
        _sync_directory(committed.parent)
    except OSError as problem:
        _log.warning(
            "committed recipe removal %s could not be cleaned: %s",
            committed.name,
            problem,
        )


def _clean_committed_removal(committed: Path) -> None:
    """Räumt eine festgeschriebene Quarantäne bestmöglich sofort auf."""

    try:
        committed.unlink()
        _sync_directory(committed.parent)
    except OSError as problem:
        _log.warning(
            "committed recipe removal %s could not be cleaned: %s",
            committed.name,
            problem,
        )


def remove_installed(
    name: str,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    directory: Path | None = None,
    *,
    allowed_sources: frozenset[str] = frozenset((RECIPE_SOURCE, IMPORTED_SOURCE)),
    expected_sha256: str | None = None,
    validate_payload: Callable[[bytes], Recipe] | None = None,
) -> RemovedRecipeFile:
    """Entfernt ein dateibasiertes Rezept samt beiden Registerbindungen.

    Der Rückgabewert enthält absichtlich keinen Pfad. Er hält die exakten
    Bytes und die Dateimetadaten, die eine unmittelbare Wiederherstellung
    braucht. Ein offenes Dokument oder dessen Verlauf gehört nicht zu dieser
    lokalen Bibliotheksaktion.
    """

    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    source = parts or PARTS
    operations = registry or REGISTRY
    folder = recipes_dir() if directory is None else directory
    target = folder / f"{name}.json"
    with _FILE_LOCK:
        _recover_interrupted_removals(folder)
        if not source.has(name):
            raise ValueError("recipe_binding_missing")
        part_spec = source.get(name)
        if part_spec.source not in allowed_sources:
            raise ValueError("recipe_source_not_removable")
        pending, committed = _removal_paths(target)
        target.rename(pending)
        try:
            _sync_directory(folder)
            payload, metadata = _read_stored_file(pending)
            if (
                expected_sha256 is not None
                and hashlib.sha256(payload).hexdigest() != expected_sha256
            ):
                raise ValueError("recipe_file_changed")
            try:
                stored = (
                    validate_payload(payload)
                    if validate_payload is not None
                    else from_data(json.loads(payload))
                )
            except (
                AttributeError,
                KeyError,
                OverflowError,
                TypeError,
                UnicodeDecodeError,
                ValueError,
            ) as problem:
                raise ValueError("recipe_file_invalid") from problem
            if (
                stored.name != name
                or _catalog_source(stored) != part_spec.source
                or part_spec.recipe_data != file_data(stored)
            ):
                raise ValueError("recipe_file_mismatch")
            prepared = _prepare_removal(name, source, operations)
        except BaseException:
            _restore_pending_removal(pending, target)
            raise
        try:
            _commit_removal_and_activate(
                pending,
                committed,
                source,
                operations,
                prepared,
            )
        except _PublishedFileError as problem:
            _activate_prepared(source, operations, prepared)
            _log.warning(
                "committed recipe removal completed after %s",
                type(problem.problem).__name__,
            )
            _clean_committed_removal(committed)
        return RemovedRecipeFile(
            name=name,
            source=part_spec.source,
            payload=payload,
            metadata=metadata,
            recipe=stored,
        )


def _restore_file_metadata(
    descriptor: int,
    temporary: Path,
    metadata: StoredFileMetadata,
) -> None:
    """Setzt den gesicherten Dateistand vor seiner Veröffentlichung."""

    chmod_descriptor = getattr(os, "fchmod", None)
    if chmod_descriptor is None:
        temporary.chmod(metadata.mode)
    else:
        chmod_descriptor(descriptor, metadata.mode)
    os.utime(temporary, ns=(metadata.atime_ns, metadata.mtime_ns))


def restore_installed(
    removed: RemovedRecipeFile,
    restored: Recipe,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    directory: Path | None = None,
) -> Path:
    """Stellt exakte Rezeptbytes und ihre beiden Bindungen atomar wieder her."""

    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    source = parts or PARTS
    operations = registry or REGISTRY
    if restored.name != removed.name or _catalog_source(restored) != removed.source:
        raise ValueError("recipe_restore_mismatch")
    with _FILE_LOCK:
        from app.core.knowledge.parts import ops as part_ops

        if source.has(removed.name) or operations.has(part_ops.op_name(removed.name)):
            raise _existing_recipe_error(removed.name, f"{removed.name}.json")
        prepared = _prepare_binding(
            restored,
            source,
            operations,
            replace_existing=False,
        )
        folder = ensure_dir(recipes_dir() if directory is None else directory)
        target = folder / f"{removed.name}.json"

        def activate() -> None:
            _activate_prepared(source, operations, prepared)

        def prepare_file(descriptor: int, temporary: Path) -> None:
            _restore_file_metadata(descriptor, temporary, removed.metadata)

        try:
            _publish_file(
                target,
                removed.payload,
                overwrite=False,
                on_published=activate,
                prepare_file=prepare_file,
            )
        except _PublishedFileError as problem:
            _activate_prepared(source, operations, prepared)
            _log.warning(
                "published recipe restore completed after %s",
                type(problem.problem).__name__,
            )
        except FileExistsError as problem:
            raise _existing_recipe_error(removed.name, target.name) from problem
        return target


def install(
    recipe: Recipe,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    directory: Path | None = None,
) -> Path:
    """Legt einen importierten Baustein an, aber ersetzt niemals einen vorhandenen.

    Datei, Katalogeintrag und Operation bilden wie bei :func:`replace` eine
    Einheit. Der Unterschied ist die Konfliktregel: Import ist immer
    fail-closed; ein anderer Name muss vom Aufrufer ausdrücklich kommen.
    """

    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    source = parts or PARTS
    operations = registry or REGISTRY
    with _FILE_LOCK:
        suggested = available_name(recipe.name, source, operations, directory)
        if suggested != recipe.name:
            raise _existing_recipe_error(
                recipe.name,
                f"{recipe.name}.json",
                suggested=suggested,
            )
        prepared = _prepare_binding(
            recipe,
            source,
            operations,
            replace_existing=False,
        )
        return _save_and_activate(
            recipe,
            source,
            operations,
            prepared,
            directory,
            overwrite=False,
        )


def file_data(recipe: Recipe) -> dict[str, Any]:
    """Die Daten samt Bereichstest-Bericht — was eine Rezeptdatei trägt.

    Dieselbe Gestalt für die Datei im Nutzerordner und für die Reise in einer
    Projektdatei: Bericht, Lizenz und Autor hängen **neben** den Daten, nicht
    darin (siehe ``Recipe.range_report``) — Prüfen macht aus dem Rezept kein anderes, aber
    der Empfänger soll die Warnung aus §24.5 sehen, ohne selbst zu prüfen.
    """
    data = to_data(recipe)
    # Neben den Daten, nicht darin — wie der Bericht, und aus demselben Grund
    # (siehe ``Recipe.range_report``): Sie gehören in die Datei, aber nicht in
    # den Hash.
    if recipe.license:
        data["license"] = recipe.license
    if recipe.author:
        data["author"] = recipe.author
    if recipe.imported_origin is not None:
        data["imported_origin"] = dataclasses.asdict(recipe.imported_origin)
    if recipe.range_report is not None:
        data["range_report"] = {
            "checked": recipe.range_report.checked,
            "failures": [
                {"values": entry.values, "reason": entry.reason}
                for entry in recipe.range_report.failures
            ],
        }
    return data


@dataclass(slots=True)
class LoadResult:
    """Was aus dem Rezeptordner herausgekommen ist — wie bei den ``.py``s."""

    loaded: tuple[str, ...] = ()
    findings: list[Finding] = field(default_factory=list)


def load_all(
    directory: Path | None = None,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
) -> LoadResult:
    """Liest jedes Rezept des Ordners und registriert es.

    Eine kaputte Datei hält den Start nicht an, sondern wird ein Befund —
    dieselbe Haltung wie bei den ``.py``-Bausteinen (Regel 17): Der Rest des
    Katalogs bleibt benutzbar, und der Befund nennt Datei und Grund.
    """
    folder = recipes_dir() if directory is None else directory
    if not folder.is_dir():
        return LoadResult()
    with _FILE_LOCK:
        _recover_interrupted_removals(folder)
        _cleanup_stale_temporaries(folder)
    loaded: list[str] = []
    findings: list[Any] = []
    for path in sorted(folder.glob("*.json")):
        try:
            recipe = from_data(json.loads(path.read_text(encoding="utf-8")))
            register(recipe, parts, registry, source=_catalog_source(recipe))
            loaded.append(recipe.name)
            # Regel 13 hält nur mit Regel 11 zusammen: Ein Rezept durfte
            # Quelltext tragen (``create_from_scad``), und dann musste der
            # Nutzer es erfahren, **bevor** er den Baustein rechnen ließ —
            # dieselbe Auskunft, die ``foreign.findings_for`` einer geöffneten
            # Projektdatei gibt. Seit dem OpenSCAD-Ausbau antwortet sie
            # überall mit „nichts"; die Frage bleibt gestellt, weil eine
            # Datei im eigenen Ordner keine Entwarnung ist — Rezepte werden
            # weitergegeben, und was heute nichts ausführt, kann es morgen.
            from app.core.scene.foreign import findings_for

            for warning in findings_for(recipe.document):
                findings.append(
                    dataclasses.replace(
                        warning, values={**dict(warning.values), "recipe": recipe.name}
                    )
                )
        except Exception as problem:  # Regel 17: Befund statt Abbruch
            _log.warning("recipe %s failed to load: %s", path.name, problem)
            findings.append(
                Finding(
                    code="parts.recipe_failed",
                    severity="warning",
                    message=_("Ein eigenes Rezept ließ sich nicht laden."),
                    values={"file": path.name, "reason": str(problem)[:200]},
                )
            )
    return LoadResult(loaded=tuple(loaded), findings=findings)


def _catalog_source(recipe: Recipe) -> str:
    """Leitet die sichtbare Katalogherkunft aus der dauerhaften Quittung ab."""

    if recipe.imported_origin is not None:
        return IMPORTED_SOURCE
    return RECIPE_SOURCE


# --- Der Ausschnitt (die Naht zu E4) ---------------------------------------------


def capture(
    document: Document,
    payloads: dict[str, bytes],
    *,
    name: str,
    title: str,
    group: str,
    op_ids: tuple[int, ...],
    exposed: tuple[ExposedParam, ...],
    features: dict[str, str],
    doc: str = "",
    licence: str = "",
    author: str = "",
    profile: Profile,
) -> Recipe:
    """Aus einem echten Dokument den Ausschnitt herausschneiden.

    Die Naht zu Paket E4: Der Dialog sammelt Name, Titel, Gruppe, die
    gewählten Schritte, die freigegebenen Parameter samt ihren Angaben, die
    benannten Merkmale sowie Lizenz und Autor. Hier entsteht
    daraus das Rezept, und die **Probe läuft sofort**: einmal auswerten, genau
    ein Körper, jedes benannte Merkmal vorhanden (Konzept §18a und §18d). Was
    hier durchgeht, steht danach im Katalog; was nicht, sagt beim Speichern
    warum, nicht später beim Benutzen.

    **Das Argument heißt ``licence``, das Feld ``license``**, und beides ist
    Absicht: ``license`` ist ein Python-Builtin und darf kein Parametername
    sein (ruff A002), während der *Feldname* der Dateischlüssel ist und dem
    Dokumentformat folgen muss (siehe :attr:`Recipe.license`). Damit trägt der
    Code die britische Schreibung wie der übrige Bestand und die Datei die
    amerikanische wie ``serialise.py``.

    Mitgenommen werden alle Projektparameter des Dokuments — sie sind kleine
    Daten, und welche der Ausschnitt wirklich liest, entscheiden seine
    Ausdrücke — und nur die Quellen, auf die der Ausschnitt sich bezieht.

    **Ein freigegebener Parameter mit Ausdruck verliert seine Formel**
    (:func:`_with_values` sagt, warum das dort richtig ist). Abgewiesen wird
    er deshalb nicht: Die Bindung zu lösen ist ein zulässiger Wunsch — im
    Projekt hing die Höhe an der Breite, im Baustein soll sie ein eigenes Maß
    sein. Gefragt wird stattdessen, und zwar dort, wo jemand antworten kann:
    Der Rezeptdialog legt eine solche Zeile **ohne** Haken an und schreibt
    daneben, was ein Haken dort bedeutet. Wer :func:`capture` als zweiter
    Aufrufer benutzt, übernimmt diese Frage — hier weiß niemand, wen er fragen
    soll (Regel 21: nie stillschweigend raten, aber auch kein Dialog aus dem
    Kern heraus).
    """
    if not features:
        # §24.1 verlangt es ohnehin beim Registrieren — aber dort hieße der
        # Fehler „beim Laden", und der Kunde stünde vor einem gespeicherten
        # Rezept, das nie auftaucht. Die Regel gehört an die Stelle, an der
        # sie behebbar ist: hier, beim Speichern (Konzept §18d).
        raise ValidationError(
            field="features",
            detail=_(
                "Ein Baustein verspricht benannte Merkmale — geben Sie "
                "mindestens einem Merkmal des Ergebnisses einen Namen."
            ),
            constraint="empty",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    wanted = set(op_ids)
    ops = [entry for entry in document.ops if entry.id in wanted]
    if not ops:
        raise ValidationError(
            field="op_ids",
            detail=_("Der Ausschnitt ist leer — wählen Sie mindestens einen Schritt."),
            constraint="empty",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    used_sources = {key: source for key, source in document.sources.items() if _mentions(ops, key)}
    slice_document = dataclasses.replace(
        document,
        ops=ops,
        sources=used_sources,
        transactions=[],
        chat=[],
        fits=[],
    )
    recipe = Recipe(
        name=name,
        title=title,
        group=group,
        document=slice_document,
        payloads={key: payloads[key] for key in used_sources if key in payloads},
        exposed=exposed,
        features=dict(features),
        doc=doc,
        # **Durchgereicht, nicht nur vorhanden.** Ein Feld an der Dataclass,
        # das der einzige Weg zu einem Rezept nicht kennt, wäre da und immer
        # leer — der Dialog könnte es setzen wollen und käme nicht an.
        license=licence,
        author=author,
    )
    build(recipe, profile=profile)  # die Probe — wirft mit Handlungsvorschlag
    return recipe


def _mentions(ops: list[Any], source_id: str) -> bool:
    """Ob ein Schritt des Ausschnitts diese Quelle nennt — irgendwo in seinen
    Werten, denn der Parametername dafür gehört der jeweiligen Operation."""
    for entry in ops:
        for value in entry.params.values():
            if value == source_id:
                return True
    return False


# --- Die Reise in der Projektdatei (Konzept §17.1) --------------------------------


def for_container(document: Document, parts: PartRegistry | None = None) -> dict[str, str]:
    """Was mit diesem Projekt reisen muss: je benutztem Rezept sein JSON-Text.

    Entscheidung Robert, 24.08.2026: Ein Rezept darf mitreisen — es nennt
    Namen registrierter Operationen und Zahlen, seine Sicherheitslage ist die
    einer ``project.json``. Mitgereiste reisen weiter: Wer eine Datei
    bekommt und weitergibt, gibt den Baustein mit, sonst endet die Kette beim
    zweiten Empfänger mit ``parts.missing``.
    """
    from app.core.knowledge.parts.registry import PARTS, used_parts

    source = parts or PARTS
    travelling: dict[str, str] = {}
    for name in sorted(set(used_parts(document.ops))):
        if not source.has(name):
            continue
        spec = source.get(name)
        if spec.recipe_data is None:
            continue
        travelling[name] = json.dumps(
            dict(spec.recipe_data), ensure_ascii=False, indent=2, sort_keys=True
        )
    return travelling


def adopt(
    data: dict[str, Any],
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    *,
    catalog_source: str = TRAVELLED_SOURCE,
) -> list[Finding]:
    """Nimmt ein mitgereistes Rezept auf — „lokal schlägt mitgereist, immer".

    **``catalog_source`` sagt, woher die Datei kam.** Die Vorgabe ist der
    mitgereiste Weg, für den diese Funktion gebaut wurde. Ein dauerhafter
    Dateiimport nutzt stattdessen :func:`replace`, damit Datei, Katalog und
    Operation atomar zusammen wechseln. Das Argument heißt nicht ``source``,
    weil das hier schon das Register ist.

    Drei Lagen, unabhängig davon (Konzept §17.1):

    * Der Name ist frei: registrieren, mit dieser Kennzeichnung.
      In den Nutzerordner geschrieben wird nichts — das Rezept gehört der
      Datei, mit der es kam, und reist mit ihr weiter.
    * Es gibt lokal denselben Stand (gleicher Abdruck): nichts zu tun.
    * Es gibt lokal einen **anderen** Stand: Der lokale gewinnt — alles
      andere wäre eine Datei, die von außen den Werkzeugkasten des Kunden
      umschreibt. Der mitgereiste bekommt einen abgeleiteten Namen und steht
      daneben im Katalog; dass das Projekt mit dem lokalen anders rechnet,
      meldet der §24.4-Abdruckvergleich beim Öffnen ohnehin.

    Eine kaputte Datei ist ein Befund, kein Abbruch (Regel 17) — der Rest
    des Projekts öffnet.

    **Und was mitkommt, wird angesagt.** Trüge der Ausschnitt einen Schritt,
    der fremden Quelltext ausführt, gäbe diese Funktion dieselbe Auskunft, die
    ``load_all`` für den eigenen Ordner gibt (§32, Regel 11 und 13 zusammen).
    Seit dem OpenSCAD-Ausbau gibt es keinen solchen Schritt mehr.
    Sie fehlte hier, und damit war der eine Weg blind, auf dem ein fremdes
    Rezept wirklich ankommt: Eine gemailte Projektdatei meldete
    ``parts.travelled`` und kein Wort über den Quelltext. Gemeldet wird in
    jeder der drei Lagen — auch wo nichts zu registrieren ist, denn gerechnet
    wird dann mit dem lokalen Stand desselben Rezepts, und der trägt denselben
    Quelltext.
    """
    from app.core.knowledge.parts.registry import PARTS

    source = parts or PARTS
    try:
        arrived = from_data(data)
        announced = _announced(arrived)
        mark = fingerprint(arrived)
        name = arrived.name
        if source.has(name):
            local = source.get(name)
            if local.version == mark:
                return announced
            name = f"{arrived.name}_travelled"
            # Verglichen wird der Abdruck der **umbenannten** Fassung: Der
            # Name gehört zu den kanonischen Daten, und ein Vergleich gegen
            # den unumbenannten Abdruck wäre nie gleich — jedes erneute
            # Öffnen tauschte dann ein identisches Rezept gegen sich selbst.
            arrived = dataclasses.replace(arrived, name=name)
            mark = fingerprint(arrived)
            if source.has(name):
                # Noch einmal geöffnet in derselben Sitzung — oder zwei
                # Projekte mit demselben fremden Rezept: derselbe Abdruck
                # heißt dasselbe Rezept, nichts zu tun. Ein **anderer**
                # Abdruck tauscht den mitgereisten Eintrag aus, samt seiner
                # Operation: Die zuletzt geöffnete Datei gilt. Vorher stand
                # hier eine Absage mit dem Rat, das andere Projekt zu
                # schließen — ein Mittel ohne Wirkung, denn Schließen meldet
                # nichts ab (Fund des Gesamtreviews vom 25.08.2026).
                if source.get(name).version == mark:
                    return announced
                from app.core.knowledge.parts import ops as part_ops
                from app.core.registry import REGISTRY

                source.remove(name)
                (registry or REGISTRY).remove(part_ops.op_name(name))
        register(arrived, source, registry, source=catalog_source)
        return announced
    except Exception as problem:  # Regel 17: Befund statt Abbruch
        _log.warning("travelled recipe failed to adopt: %s", problem)
        return [_not_adopted(problem)]


def adopt_payload(
    raw: bytes,
    entry: str,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
) -> list[Finding]:
    """Dasselbe, solange das Rezept noch als Text im Container liegt.

    Der Grund für diese zweite Tür: Das ``json.loads`` stand beim Aufrufer,
    also **außerhalb** des ``try`` in :func:`adopt`. Eine abgeschnittene
    ``recipes/foo.json`` ließ damit das ganze Projekt mit „Der Projektinhalt
    ist beschädigt" abbrechen, obwohl das Dokument heil war — und der
    Kommentar zwei Zeilen über der Aufrufstelle sagte längst, eine kaputte
    Beilage sei ein Befund und kein Abbruch (Regel 17). Lesen gehört zum
    Aufnehmen, also gehört es in dasselbe ``try``.
    """
    try:
        data = json.loads(raw)
    except Exception as problem:  # Regel 17: Befund statt Abbruch
        _log.warning("travelled recipe %s is unreadable: %s", entry, problem)
        return [_not_adopted(problem, entry)]
    return adopt(data, parts, registry)


def _announced(arrived: Recipe) -> list[Finding]:
    """Was an einem mitgereisten Rezept erklärt gehört, bevor es rechnet (§32).

    Dieselben Zeilen wie in :func:`load_all` — mit dem Rezeptnamen
    angereichert, denn der Befund kommt aus einem Dokument, das der Kunde
    nirgends aufgeschlagen sieht.
    """
    from app.core.scene.foreign import findings_for

    return [
        dataclasses.replace(warning, values={**dict(warning.values), "recipe": arrived.name})
        for warning in findings_for(arrived.document)
    ]


def _not_adopted(problem: Exception, entry: str = "") -> Finding:
    """Der Befund für eine Beilage, die nicht ankam — mit Grund und, wo
    bekannt, dem Namen der Datei im Container."""
    values = {"reason": str(problem)[:200]}
    if entry:
        values["file"] = entry
    return Finding(
        code="parts.recipe_failed",
        severity="warning",
        message=_("Ein mitgereistes Rezept ließ sich nicht aufnehmen."),
        values=values,
    )


def replace(
    recipe: Recipe,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
    directory: Path | None = None,
) -> Path:
    """Legt ein Rezept an **oder** ersetzt seinen vorhandenen Stand — Datei,
    Katalogeintrag und Operation zusammen.

    Ein Weg für beide Fälle (Absprache mit der Dialogseite, 26.08.2026):
    Ist der Name frei, wirkt es wie ``save`` plus ``register``; ist er
    vergeben, werden alle drei Seiten getauscht. „Ersetzen oder anlegen"
    bleibt damit eine Frage der Knopfbeschriftung, nicht des Ablaufs.

    **Die Operation wird wirklich neu gebunden.** ``register_one`` hält den
    ``PartSpec`` als Vorgabewert seiner ``run``-Funktion fest — ein neuer
    Katalogeintrag allein ändert die Rechnung nicht (b0s Messung vom
    26.08.2026). Deshalb entsteht der gesamte neue Registerstand zuerst
    isoliert. Nach der Dateiveröffentlichung werden beide fertigen Abbildungen
    nur noch aktiviert; es gibt keinen erneut fehlbaren Aufbau und keinen
    Plattenrollback in einen womöglich widersprüchlichen Stand.
    """
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    source = parts or PARTS
    operations = registry or REGISTRY
    with _FILE_LOCK:
        prepared = _prepare_binding(
            recipe,
            source,
            operations,
            replace_existing=True,
        )
        return _save_and_activate(
            recipe,
            source,
            operations,
            prepared,
            directory,
            overwrite=True,
        )
