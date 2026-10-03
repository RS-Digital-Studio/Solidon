"""Export und die Prüfung, die davor läuft (Bauplan §29, §16.3).

Die Prüfung ist ein Bericht, keine Sperre: Wasserdichtheit, Bauraum,
Wandstärke und die Lizenz der Quellen werden genannt, und wer trotzdem
exportieren will, kann das — er weiß dann nur, was er tut.

Das Namensschema zählt mehr, als es aussieht. Wer drei Teile druckt, will auf
der Platte sehen, welches welches ist — also ist
``projekt_halterung_1von3.stl`` die Vorgabe, und Objektnamen werden
dateisystemtauglich gemacht, ohne unlesbar zu werden.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import numpy as np

from app.core import activation, build_area
from app.core.deferred import trimesh
from app.core.errors import (
    ARRANGE_ON_BED,
    CANCEL,
    CHANGE_SELECTION,
    CHOOSE_PRINTER,
    CONVERT_TO_EXACT,
    EXPORT_AS_MESH,
    SHOW_HISTORY,
    ExternalToolError,
    FileWriteError,
    NeedsSolidError,
    ValidationError,
)
from app.core.export import slicer_keys, threemf
from app.core.export.slicer_keys import (
    CURA_SUPPORT_BLOCKER,
    SlicerFlavour,
    helpers_as_parts,
    needs_bed_translation,
    reads_assembly_file,
    takes_mesh_settings,
)
from app.core.geom import transform
from app.core.geom.mesh import MeshData, as_mesh_data, concatenated
from app.core.geom.prepare import arrange_on_bed, check_build_volume
from app.core.knowledge.print_settings import read_path, same_value
from app.core.log import get_logger
from app.core.types import (
    BoundingBox,
    BRepBody,
    CancelToken,
    Document,
    Finding,
    MaterialSlot,
    Mesh,
    ObjectId,
    PrintSettings,
    Profile,
    Scene,
    SceneObject,
    SettingAdvice,
    SliceResult,
    Source,
    kind_of,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM, format_length
from app.i18n import TranslatableText, _, source_text

if TYPE_CHECKING:
    # Nur für die Signatur: zur Laufzeit zieht ``handover`` die
    # G-Code-Auswertung mit, und ein Export soll nicht davon abhängen, dass
    # ein Slicer im Spiel ist.
    from app.core.brep.kernel import Solid
    from app.core.export.handover import PartSplit, SlicerSetup
    from app.core.knowledge.parts.registry import PartSpec
    from app.core.types import BaseParams

_log = get_logger(__name__)

ExportFormat = Literal["stl", "3mf", "obj", "ply", "glb", "step"]

#: Als was jedes Format geschrieben wird. STL bleibt binär — ASCII wäre für
#: dieselben Dreiecke fünfmal so groß.
FORMAT_SUFFIX: dict[ExportFormat, str] = {
    "stl": ".stl",
    "3mf": ".3mf",
    "obj": ".obj",
    "ply": ".ply",
    # GLB ist das einzige Format hier, das nicht zum Drucken gedacht ist,
    # sondern zum Zeigen: eine Datei, die jeder Betrachter und jedes
    # Nachrichtenprogramm öffnet, ohne dass der Empfänger ein CAD-Programm
    # hat. Gelesen wurde es längst (``READABLE_SUFFIXES``) — hinaus ging es
    # nicht.
    "glb": ".glb",
    # §30: nur ein B-Rep-Objekt hat etwas, das in eine STEP-Datei gehört. Ein
    # als STEP exportiertes Netz wäre eine STEP-Datei voller Dreiecke — legal,
    # und eine Lüge über ihren Inhalt.
    "step": ".step",
}

#: Vorgabe-Namensschema (§29). ``{index}`` und ``{count}`` erscheinen nur,
#: wenn es mehr als ein Teil gibt.
DEFAULT_SCHEME = "{project}_{object}_{index}von{count}"
SINGLE_SCHEME = "{project}_{object}"

#: Bei mehr als einer Druckplatte kommt die Platte in den Namen (§25). Wer
#: die Dateien zum Drucker trägt, muss wissen, welche zusammengehören.
PLATE_SCHEME = "{project}_platte{plate}_{object}_{index}von{count}"

#: Was ein eigenes Namensschema einsetzen darf. Steht im Fehler, wenn etwas
#: anderes darin steht — eine Liste im Kopf des Nutzers ist keine.
SCHEME_FIELDS: Final[tuple[str, ...]] = ("project", "object", "index", "count", "plate")
_KNOWN_FIELDS: Final = ", ".join("{" + name + "}" for name in SCHEME_FIELDS)

_UNSAFE = re.compile(r"[^\w\-. ]+", re.UNICODE)

#: Was kein Dateisystem trägt — die Windows-Liste, sie ist die engste der drei.
#: Anders als :data:`_UNSAFE` zählt hier auf, was **weg muss**, statt was
#: bleiben darf: Für einen getippten Namen ist alles erlaubt, was möglich ist
#: (siehe :func:`given_name`).
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')

#: Höhe über dem Boden, in der die Standfläche eines Teils gemessen wird. Nicht
#: bei null: dort liegt die Grundfläche selbst, und ein Schnitt genau in einer
#: Fläche liefert je nach Netz alles oder nichts.
FOOTPRINT_HEIGHT = 0.2


def export_part_scad(spec: PartSpec, params: BaseParams | None = None) -> str:
    """Gibt einen Baustein nach Prüfung der Exportfreigabe als OpenSCAD-Text aus.

    CLI und Katalog benutzen dieselbe signierte Grenze. Die MIT-Bibliothek
    darunter bleibt unabhängig vom Aktivierungszustand verwendbar.
    """
    activation.require(activation.EXPORT)
    from app.core.knowledge.parts.scad import to_scad

    return to_scad(spec, params)


def safe_name(text: str, fallback: str = "teil") -> str:
    """Dateisystemtauglich, ohne unkenntlich zu werden.

    Deutsche Umlaute werden transliteriert statt weggeworfen: ``Gehäuse`` wird
    ``Gehaeuse``, nicht ``Gehuse``. Das ist eine bewusste Konvention für
    deutsche Dateinamen, und sie wurde früher durchgesetzt, indem der ganze Name
    durch ASCII gezwungen wurde — und genau dort fing „unkenntlich" an, statt
    aufzuhören: ein heruntergeladenes ``埃菲尔铁塔18cm`` kam als ``18cm`` heraus,
    ein ``Соединитель`` als ``teil``. Ein Dateiname ist nicht der Ort, an dem
    entschieden wird, welche Alphabete es gibt.

    Wirklich unsicher ist eine kurze Liste — Pfadtrenner, Doppelpunkte, die
    Zeichen, die Windows sich vorbehält — und :data:`_UNSAFE` hält sich bereits
    daran: ``\\w`` deckt jeden Buchstaben ab, den Unicode kennt.
    """
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
    for character, replacement in replacements.items():
        text = text.replace(character, replacement)
    text = unicodedata.normalize("NFC", text)
    text = _UNSAFE.sub("", text).strip().replace(" ", "_")
    return text or fallback


def given_name(text: str, fallback: str = "teil") -> str:
    """Ein Name, den der Kunde selbst getippt hat — es fällt nur das Unmögliche.

    :func:`safe_name` darüber gilt Namen, die **entstehen**: aus einem
    Objektnamen, einem Variantentitel, einem Muster. Dort ist die
    Transliteration eine Konvention und richtig. Für einen Namen, den jemand im
    Speichern-Dialog eingegeben hat, ist sie es nicht: Er hat entschieden, und
    NTFS wie ext4 können Umlaute seit je.

    Gemessen am 03.09.2026 über den Weg der Oberfläche: Wer „Gehäuse Deckel"
    tippte, bekam ``Gehaeuse_Deckel``; ein „Halter V2+" verlor sein Plus. Der
    ``_ExportWorker`` reicht den Stem des gewählten Zielpfads durch, und der
    ging durch dieselbe Bereinigung wie ein erzeugter Name. Die Statuszeile
    nannte danach ehrlich die geschriebene Datei — nur hatte der Kunde eine
    andere gemeint (Entscheidung Robert, 03.09.2026).

    Weg muss trotzdem, was ein Dateisystem nicht trägt: Pfadtrenner, die
    Zeichen, die Windows sich vorbehält, und Steuerzeichen. Ein leerer Name
    fällt auf den Rückfall zurück — sonst entstünde eine Datei, die nur ihre
    Endung ist.
    """
    text = unicodedata.normalize("NFC", text)
    return _FORBIDDEN.sub("", text).strip().rstrip(".") or fallback


@dataclass(frozen=True, slots=True)
class ExportEntry:
    """Eine Datei, die gleich geschrieben wird."""

    object_id: str
    filename: str
    mesh: MeshData
    slots: tuple[MaterialSlot, ...] = ()
    """Die Materialslots des Objekts — 3MF trägt sie als Farbgruppen (§20)."""
    name: str = ""
    body: Mesh | None = None
    """Das Objekt, wie es in der Szene steht. STEP braucht den exakten Körper,
    nicht die Dreiecke, in die er vernetzt wurde (§30)."""
    plate: int = 0
    """Zu welcher Druckplatte diese Datei gehört (§25)."""


@dataclass(frozen=True, slots=True)
class ExportPlan:
    """Was geschrieben würde, und was die Prüfung vorher gefunden hat."""

    entries: tuple[ExportEntry, ...] = ()
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def blocked(self) -> bool:
        """Nie wahr — die Prüfung berichtet, sie blockiert nicht (§29)."""
        return False


def plan_export(
    objects: list[SceneObject],
    *,
    project_name: str,
    profile: Profile,
    export_format: ExportFormat = "stl",
    scheme: str | None = None,
    sources: dict[str, Source] | None = None,
    scene: Scene | None = None,
    document: Document | None = None,
    checked: Sequence[Finding] | None = None,
    evaluated: Sequence[Finding] = (),
) -> ExportPlan:
    """Ermittelt die Dateinamen und führt die Prüfung vor dem Export aus.

    ``checked`` übernimmt einen Bericht, den jemand schon erhoben hat, statt
    ihn ein zweites Mal zu rechnen (RM-140): Das Fenster prüft zuerst, zeigt
    die Befunde und schreibt erst nach der Antwort — und die Prüfung ist der
    teure Teil. Eine leere Liste ist dabei eine Antwort und kein fehlender
    Wert; deshalb wird auf ``None`` geprüft.
    """
    if not objects:
        raise ValidationError(
            field="objects",
            detail=_("Es ist nichts zum Exportieren ausgewählt."),
            constraint="empty",
        )

    count = len(objects)
    pattern = scheme if scheme is not None else default_scheme(objects)
    suffix = FORMAT_SUFFIX[export_format]

    try:
        entries = _entries_for(objects, pattern, project_name, count, suffix, profile)
    except KeyError as problem:
        # **Ein Schema ist eine Eingabe des Nutzers**, in der Kommandozeile
        # getippt und im Dialog eintragbar — ``{name}`` statt ``{object}`` ist
        # der naheliegende Fehlgriff. Ein roher ``KeyError`` nennt weder den
        # richtigen Namen noch die Tatsache, dass man ihn ändern kann.
        raise ValidationError(
            field="scheme",
            detail=_("Das Namensschema nennt einen Platzhalter, den es nicht gibt."),
            value=pattern,
            constraint="unknown_placeholder",
            values={"requested": "{" + str(problem.args[0]) + "}", "known": _KNOWN_FIELDS},
        ) from problem
    except (IndexError, ValueError) as problem:
        # Eine Klammer, die nicht zugeht, oder ``{0}``: dieselbe Sorte Tippfehler,
        # eine andere Ausnahme — und ohne diesen Zweig ebenso ein Stapelabzug.
        raise ValidationError(
            field="scheme",
            detail=_("Das Namensschema lässt sich nicht lesen; eine Klammer steht falsch."),
            value=pattern,
            constraint="broken_scheme",
            values={"known": _KNOWN_FIELDS},
        ) from problem
    findings = (
        list(checked)
        if checked is not None
        else check_before_export(
            objects,
            profile,
            sources or {},
            export_format,
            scene=scene,
            document=document,
            evaluated=evaluated,
        )
    )
    if export_format != "step":
        findings += _tessellation_finding(objects, profile)
    return ExportPlan(entries=entries, findings=tuple(findings))


def default_scheme(objects: Sequence[SceneObject]) -> str:
    """Das Namensschema, das ohne eigene Angabe gilt (§29).

    Eine Funktion und kein Ausdruck in :func:`plan_export`, weil das Fenster
    dieselbe Frage stellt (RM-141): Es zeigt das Muster im Namensfeld des
    Dateidialogs, damit der Kunde es ändern kann. Zwei Stellen, die es
    ausrechnen, wären zwei Antworten.
    """
    plates = len({entry.plate for entry in objects})
    if plates > 1:
        return PLATE_SCHEME
    return DEFAULT_SCHEME if len(objects) > 1 else SINGLE_SCHEME


def _entries_for(
    objects: list[SceneObject],
    pattern: str,
    project_name: str,
    count: int,
    suffix: str,
    profile: Profile,
) -> tuple[ExportEntry, ...]:
    """Die geplanten Dateien. Ausgelagert, weil das Schema scheitern darf und
    der Aufrufer den Fehlgriff benennen soll.
    """
    entries = tuple(
        ExportEntry(
            object_id=entry.id,
            # Der Projektteil ist der Name, den der Kunde gewählt hat, der
            # Objektteil entsteht — deshalb zwei verschiedene Prüfungen.
            filename=given_name(
                pattern.format(
                    project=given_name(project_name, "projekt"),
                    # **Quellsprache, nicht Anzeigesprache** (§16.2, entschieden
                    # am 22.08.2026). Ein Dateiname, der mit der eingestellten
                    # Sprache wandert, macht aus demselben Klick verschiedene
                    # Dateien — dieselbe Sorte Fehler wie ein Cache-Schlüssel,
                    # der es tut. Der Exportdialog zeigt den Namen zum Ändern;
                    # eine sichtbare Vorgabe, die stabil ist, schlägt eine
                    # unsichtbare, die wandert.
                    object=safe_name(source_text(entry.name)),
                    index=index,
                    count=count,
                    plate=entry.plate + 1,
                )
            )
            + suffix,
            mesh=mesh_for_export(entry.mesh, profile),
            slots=threemf.slots_for_object(entry),
            # Steht als Objektname **in** der 3MF-Datei, ist also Dateiinhalt
            # und keine Anzeige — dieselbe Regel wie beim Dateinamen darüber.
            name=source_text(entry.name),
            body=entry.mesh,
            plate=entry.plate,
        )
        for index, entry in enumerate(objects, start=1)
    )
    return _without_name_clashes(entries)


def _without_name_clashes(entries: tuple[ExportEntry, ...]) -> tuple[ExportEntry, ...]:
    """Zwei Objekte, die auf denselben Dateinamen fallen, bekommen eine laufende
    Nummer vor der Endung.

    Ein Schema ohne unterscheidendes Feld (``{project}`` allein) oder schlicht
    zwei gleichnamige Körper ergaben sonst zweimal denselben Namen. Geschrieben
    wurde der Reihe nach mit ``write_bytes``: Der zweite überschrieb den ersten,
    und beide wurden als „geschrieben" gemeldet — eine Datei, zwei
    Erfolgsmeldungen, das erste Teil weg. Nummeriert wird wie beim Einlesen
    einer Baugruppe (:func:`app.core.export.threemf` nummeriert dort dieselbe
    Kollision).
    """
    # **Groß und klein sind ein Name.** Das übliche Windows-Dateisystem und
    # macOS unterscheiden ``A.stl`` und ``a.stl`` nicht — gemessen unter
    # Windows: zwei gemeldete Dateien, eine auf der Platte, der erste Körper
    # weg. Verglichen wird deshalb überall gefaltet, gleich auf welcher
    # Plattform der Export läuft (Gesamtreview 05.09.2026, CORE-18).
    totals: dict[str, int] = {}
    for entry in entries:
        totals[entry.filename.casefold()] = totals.get(entry.filename.casefold(), 0) + 1
    if all(total == 1 for total in totals.values()):
        return entries
    # Was für sich allein steht, behält seinen Namen und ist damit **vergeben**:
    # ``A``, ``A`` und ``A-1`` wurden ``A-1``, ``A-2``, ``A-1`` — die Nummer
    # wurde nie gegen die geplanten Namen geprüft, und das erste Teil
    # verschwand unter dem dritten. Nummeriert wird jetzt so lange weiter,
    # bis der Name gegen alle vergebenen eindeutig ist.
    taken = {key for key, total in totals.items() if total == 1}
    seen: dict[str, int] = {}
    result: list[ExportEntry] = []
    for entry in entries:
        key = entry.filename.casefold()
        if totals[key] == 1:
            result.append(entry)
            continue
        stem, dot, extension = entry.filename.rpartition(".")
        number = seen.get(key, 0)
        while True:
            number += 1
            numbered = f"{stem}-{number}{dot}{extension}" if dot else f"{entry.filename}-{number}"
            if numbered.casefold() not in taken:
                break
        seen[key] = number
        taken.add(numbered.casefold())
        result.append(replace(entry, filename=numbered))
    return tuple(result)


def adhesion_margin(settings: PrintSettings) -> float:
    """Wie weit die Druckbetthaftung über den Körper hinausreicht.

    Der Wert entscheidet, wie eng zwei Teile nebeneinander stehen dürfen — und
    er wurde beim Gewürzset zuerst vergessen: die Deckelplatte sah in der
    Rechnung frei aus und war es nicht, weil zwölf Streuscheiben je 3 mm Brim
    tragen und der zwischen zwei Nachbarn zweimal zählt.
    """
    kind = settings.adhesion.kind
    # Der Auto-Brim des Slicers legt höchstens die Brimbreite seines Profils —
    # ob er es tut, weiß erst der Slicer. Der Abstand rechnet mit dem Fall,
    # in dem er es tut (Entscheidung J, 27.09.2026).
    if kind in ("brim", "auto"):
        return settings.adhesion.brim_width
    if kind == "skirt":
        return settings.adhesion.skirt_distance
    if kind == "raft":
        # Ein Raft läuft ungefähr eine Brimbreite über den Körper hinaus; der
        # genaue Wert steht im Slicer und ist keine Solidon-Einstellung.
        return settings.adhesion.brim_width
    return 0.0


def support_margin(settings: PrintSettings) -> float:
    """Wie weit die Stützstruktur über den Körper hinausreicht.

    Sie steht unter dem Überhang, also überwiegend in der Aufsicht des Körpers
    selbst — aber an einer senkrechten Wand hält sie ``xy_gap`` Abstand und
    liegt damit außerhalb. Zwischen zwei Nachbarn zählt dieser Rand zweimal,
    genau wie der Brim (Robert, 09.09.2026: „abstände und nötige stützen
    beachten").

    **Nötig heißt eingeschaltet.** Wo kein Stützstil gewählt ist, entsteht auch
    keine Struktur, und ein Rand für etwas, das es nicht gibt, verschenkte
    Bettfläche. Ob die Geometrie welche *braucht*, ist eine andere Frage — sie
    beantwortet die Schichtanalyse und nicht die Anordnung.
    """
    if settings.support.style == "none":
        return 0.0
    return max(0.0, settings.support.xy_gap)


def clearance_margin(settings: PrintSettings) -> float:
    """Der Rand, den ein Teil um sich herum braucht — Haftung und Stützen.

    Die eine Auskunft für alle, die den Abstand zwischen zwei Teilen brauchen:
    die Vorbelegung im Anordnungsdialog (``MainWindow._spacing_for``) und die
    Prüfung vor dem Export. Zwei Rechnungen für dieselbe Frage liefen
    auseinander, sobald eine davon einen Anteil dazubekam.
    """
    return adhesion_margin(settings) + support_margin(settings)


def check_adhesion_clearance(
    meshes: Sequence[MeshData],
    settings: PrintSettings,
    plates: Sequence[int] | None = None,
    *,
    per_part: Sequence[PrintSettings] | None = None,
) -> list[Finding]:
    """Passen die Ränder zwischen zwei Teilen noch nebeneinander?

    Die Körper selbst können reichlich Luft haben und der Druck trotzdem
    scheitern: Brim, Skirt und Stützstruktur stehen über den Körper hinaus, und
    zwischen zwei Nachbarn zählen beide Ränder. Gemessen wird in der
    Aufsicht, denn dort liegen sie — was sich in der Höhe überlappt, ist eine
    andere Frage (:func:`app.core.geom.prepare.check_collisions`).

    ``per_part`` sind die Einstellungen, mit denen jedes Teil gedruckt wird —
    ein Brim je Teil liegt nur um das eine (Entscheidung G).
    """
    margins = [
        clearance_margin(per_part[index] if per_part is not None else settings)
        for index in range(len(meshes))
    ]
    if all(margin <= 0.0 for margin in margins):
        return []

    findings: list[Finding] = []
    for first in range(len(meshes)):
        for second in range(first + 1, len(meshes)):
            if plates is not None and plates[first] != plates[second]:
                continue
            needed = margins[first] + margins[second]
            if needed <= 0.0:
                continue
            gap = _plane_gap(meshes[first].bounds, meshes[second].bounds)
            if gap >= needed - EPS_GEOM:
                continue
            findings.append(
                Finding(
                    code="arrange.adhesion_too_close",
                    severity="warning",
                    message=_("Zwei Teile stehen so dicht, dass ihre Ränder ineinanderlaufen."),
                    values={
                        "a": first,
                        "b": second,
                        "gap": format_length(gap),
                        "needed": format_length(needed),
                    },
                    # Regel 17: Anordnen legt die Teile mit dem Abstand der Plattenhaftung.
                    suggestions=(ARRANGE_ON_BED,),
                )
            )
    return findings


def rim_reach(settings: PrintSettings) -> float:
    """Wie weit Brim, Skirt oder Raft über den Rand des äußersten Teils reichen.

    Anders als :func:`adhesion_margin` zählt beim Skirt auch seine Breite:
    Zwischen zwei Teilen läuft er nicht, am Bettrand liegt er ganz außen —
    ``skirt_distance`` weit weg und so viele Bahnen breit, wie er Runden hat.
    """
    adhesion = settings.adhesion
    if adhesion.kind == "skirt":
        return (
            adhesion.skirt_distance + adhesion.skirt_loops * settings.layers.first_layer_line_width
        )
    return adhesion_margin(settings)


def check_adhesion_on_bed(
    meshes: Sequence[MeshData],
    settings: PrintSettings,
    profile: Profile,
    object_ids: Sequence[str] = (),
    *,
    per_part: Sequence[PrintSettings] | None = None,
) -> list[Finding]:
    """Liegt der Rand um jedes Teil noch auf dem Bett?

    Zwischen zwei Teilen fragt :func:`check_adhesion_clearance`, nach den
    Körpern selbst die Prüfung des Bauraums. Der Rand zum Bettrand blieb
    ungefragt: Am Minigolf-Auftrag für den Centauri Carbon 2 fuhr der Auto-Brim
    des ElegooSlicers am Neptune 4 210 Züge neben das Bett, PrusaSlicers Skirt
    am SV06 24 (27.09.2026). Kein Slicer widersprach, die Druckdatei verließ
    den Bauraum. Ein Teil, das selbst neben dem Bett liegt, meldet die Prüfung
    des Bauraums; hier geht es nur um den Rand.
    """
    reaches = [
        rim_reach(per_part[index] if per_part is not None else settings)
        for index in range(len(meshes))
    ]
    width, depth, _height = profile.printer.build_volume
    half = (width / 2.0, depth / 2.0)
    findings: list[Finding] = []
    for index, mesh in enumerate(meshes):
        reach = reaches[index]
        if reach <= 0.0:
            continue
        box = mesh.bounds
        if any(
            box.minimum[axis] < -half[axis] - EPS_GEOM or box.maximum[axis] > half[axis] + EPS_GEOM
            for axis in (0, 1)
        ):
            continue
        over = max(
            max(-half[axis] - (box.minimum[axis] - reach), box.maximum[axis] + reach - half[axis])
            for axis in (0, 1)
        )
        if over <= EPS_GEOM:
            continue
        findings.append(
            Finding(
                code="arrange.adhesion_off_bed",
                severity="warning",
                message=_("Der Rand um ein Teil reicht über das Bett hinaus."),
                object_id=object_ids[index] if index < len(object_ids) else None,
                values={"distance": format_length(over)},
                # Regel 17: Anordnen hält zum Bettrand den Abstand der Haftung
                # (``split.bed_margin``).
                suggestions=(ARRANGE_ON_BED,),
            )
        )
    return findings


def arrangement_holds(meshes: Sequence[MeshData], profile: Profile) -> bool:
    """Darf der Slicer diese Lage unverändert übernehmen?

    Druckkontur und freigegebene Höhe kommen aus demselben Vertrag wie die
    Platzierung. Dazu müssen alle Teile auf dem Bett stehen und sich in der
    Aufsicht trennen. Die bestehenden Grenzen EPS_GEOM und EPS_DISPLAY
    stimmen mit Bauraumprüfung und Schwebebefund überein.
    """
    if not meshes:
        return False
    for mesh in meshes:
        if not build_area.fits_on_bed(mesh, profile.printer):
            return False
        if mesh.bounds.minimum[2] > EPS_DISPLAY:
            return False
    for first in range(len(meshes)):
        for second in range(first + 1, len(meshes)):
            if _plane_gap(meshes[first].bounds, meshes[second].bounds) <= EPS_GEOM:
                return False
    return True


def _plane_gap(first: BoundingBox, second: BoundingBox) -> float:
    """Der Abstand zweier Grundrisse. Null heißt: sie überlappen bereits."""
    along = [
        max(first.minimum[axis] - second.maximum[axis], second.minimum[axis] - first.maximum[axis])
        for axis in (0, 1)
    ]
    # Getrennt sind sie, sobald es *eine* Achse gibt, die sie trennt — und der
    # Abstand ist dann der dieser Achse.
    return max(max(along), 0.0)


def check_filament_changes(
    objects: Sequence[SceneObject], settings: PrintSettings, plate: int | None = None
) -> list[Finding]:
    """Was es kostet, zwei Filamente auf eine Platte zu legen (§29).

    Ein Wechsel ist nicht der Griff zur zweiten Spule, sondern ein Spülvorgang
    je Schicht, in der beide Filamente vorkommen. Beim Gewürzset waren das
    hundertzehn Schichten — der Behälter ist 68 mm hoch, der Deckel 22 —, also
    rund zweihundertzwanzig Wechsel, und das Spülmaterial wog mehr als die
    Deckel selbst.

    Gemeldet wird die Zahl der Wechsel, weil sie sich aus den Höhen exakt
    ergibt. Was ein einzelner davon an Material kostet, steht im Profil des
    Slicers und nicht hier — die Größenordnung nennt der Bericht, die Zahl der
    Slicer.
    """
    # ``None`` heißt beim mehrplattigen 3MF-Export „der ganze Auftrag", nicht
    # „alle Körper liegen auf derselben Platte". Platten werden nacheinander
    # gedruckt; Weiß auf Platte 1 und Schwarz auf Platte 2 verursachen keinen
    # einzigen Wechsel. Ohne die Trennung meldete die fertige CC2-Werkzeugbox
    # 230 Wechsel, obwohl jede ihrer Platten materialrein ist.
    if plate is None:
        findings: list[Finding] = []
        for current in dict.fromkeys(entry.plate for entry in objects):
            findings.extend(check_filament_changes(objects, settings, current))
        return findings

    chosen = [entry for entry in objects if entry.plate == plate]
    slots_of = {entry.id: {slot.name for slot in entry.material_slots} or {""} for entry in chosen}
    if len({name for names in slots_of.values() for name in names}) < 2:
        return []

    layer = settings.layers.layer_height
    if layer <= 0.0:
        return []
    tallest = max((float(entry.mesh.bounds.maximum[2]) for entry in chosen), default=0.0)
    # **Beide Kanten, nicht nur die obere.** Ein Teil, das erst weiter oben
    # beginnt — auf einem anderen stehend, in einer Vorrichtung, angehoben —
    # war in jeder Schicht darunter mitgezählt, und die Meldung nannte Wechsel
    # für Schichten, in denen sein Filament gar nicht vorkommt.
    span = {
        entry.id: (float(entry.mesh.bounds.minimum[2]), float(entry.mesh.bounds.maximum[2]))
        for entry in chosen
    }
    shared = 0
    for index in range(int(tallest / layer) + 1):
        height = (index + 0.5) * layer
        present = {
            name
            for entry in chosen
            if span[entry.id][0] <= height <= span[entry.id][1]
            for name in slots_of[entry.id]
        }
        if len(present) > 1:
            shared += 1
    if shared == 0:
        return []

    return [
        Finding(
            code="arrange.filament_changes",
            severity="info",
            message=_(
                "Auf dieser Platte liegen mehrere Filamente übereinander. Jede "
                "gemeinsame Schicht kostet einen Wechsel samt Spülgang."
            ),
            values={"layers": shared, "changes": shared * 2},
        )
    ]


def plates_by_material(objects: Sequence[SceneObject]) -> dict[str, int]:
    """Schlägt vor, welches Teil auf welche Platte gehört (§25, §29).

    Ein Filament je Platte, denn zwei kosten je gemeinsamer Schicht einen
    Spülgang (:func:`check_filament_changes`). Die Reihenfolge folgt dem ersten
    Auftreten, damit derselbe Entwurf zweimal dieselbe Zuordnung ergibt —
    eine Vorgabe, die zwischen zwei Aufrufen springt, ist keine.

    Was mehrere Filamente in **einem** Teil trägt, bleibt zusammen: ein
    zweifarbiges Schild ist ein Objekt und lässt sich nicht auf zwei Platten
    legen. Es kommt zur Gruppe seines ersten Slots.

    Zurück kommt ein Vorschlag, keine Änderung: die Platte eines Objekts ist
    Teil des Dokuments und wird über eine Transaktion gesetzt, nicht hier.
    """
    # Der Slotname darf ein ``TranslatableText`` sein (:attr:`MaterialSlot.name`).
    # Gruppiert wird trotzdem richtig: Ein solcher Text vergleicht wie seine
    # Message-ID, auch gegen eine schlichte Zeichenkette. Angezeigt oder
    # geschrieben wird hier nichts — der Name ist nur der Schlüssel.
    order: list[tuple[TranslatableText | str, str]] = []
    chosen: dict[str, int] = {}
    for entry in objects:
        names = [slot.name for slot in entry.material_slots] or [""]
        # **Das Paar, nicht eines von beiden** — und welches von beiden es wäre,
        # ist die Frage, an der dieser Fix beinahe schiefgegangen wäre.
        #
        # Am Teil kann ein Material ausdrücklich stehen (``SceneObject.material``,
        # etwa die TPU-Dichtung im PETG-Gehäuse). Bis zum 03.09.2026 zählte
        # allein der Spulenname, und wo keine Spule zugewiesen war, trugen alle
        # denselben leeren Schlüssel: Gehäuse und Dichtung landeten auf einer
        # Platte, ``check_filament_changes`` schwieg, und die Datei ging so an
        # den Slicer.
        #
        # **Dieselbe Rangfolge ist an einer Stelle richtig und an der anderen
        # falsch.** :func:`app.core.knowledge.profiles.for_object` lässt das
        # Material die Spule schlagen, und dort stimmt es — es wird gerechnet,
        # und wer ein Material am Teil wählt, hat sich entschieden. Auf der
        # Platte zählt dagegen, was physisch im Drucker steckt: Zwei Spulen mit
        # demselben Material — grau und weiß PETG — sind zwei Filamente und
        # kämen mit „Material vor Spule" auf **eine** Platte. Gemessen an vier
        # Lagen; die Rangfolge aus dem einen Modul hierher zu tragen, weil sie
        # „die Rangfolge" ist, baut genau diesen Fehler.
        key = (names[0], entry.material or "")
        if key not in order:
            order.append(key)
        chosen[entry.id] = order.index(key)
    return chosen


#: Formate, die einen exakten Körper verlangen. STEP hält Flächen und Kanten
#: fest, und ein Netz hat keine — das ist keine Einstellung, sondern die
#: Eigenschaft des Formats.
SOLID_ONLY_FORMATS: Final[frozenset[str]] = frozenset({"step"})


def check_before_export(
    objects: list[SceneObject],
    profile: Profile,
    sources: dict[str, Source],
    export_format: ExportFormat = "stl",
    *,
    scene: Scene | None = None,
    document: Document | None = None,
    cancelled: CancelToken | None = None,
    evaluated: Sequence[Finding] = (),
) -> list[Finding]:
    """Ein Bericht vor dem Schreiben, keine Sperre (§29).

    **Das Format gehört dazu, und es fehlte.** Wer ``teil.step`` tippte, bekam
    einen Plan ohne einen einzigen Befund — der Fehler kam erst beim Schreiben,
    nach dem Klick auf Speichern. Die Auskunft war die ganze Zeit verfügbar:
    Der Körper weiß, ob er exakt ist, und das Format weiß, ob es das braucht.

    **Und die Szene gehört ebenfalls dazu** (RM-140). §29 zählt fünf Fragen
    auf; zwei davon stellt kein Körper für sich allein, sondern nur im
    Verhältnis zu anderen: eine verletzte Passung und eine Wand unter der
    Mindeststärke. Ohne ``scene`` bleiben sie ungestellt — ein Aufrufer, der
    keine Szene hat, bekommt den Bericht, den er belegen kann, und keinen
    erfundenen (Regel 21).

    **Und was die Auswertung schon weiß, sagt der Export noch einmal**
    (``evaluated``, :data:`CARRIED_TO_EXPORT`): Ein Formzug, der die Wand
    durchstochen hat, stand im Prüfbericht, der Export lief trotzdem ohne
    Hinweis (RM-419). Nachmessen hieße, jeden Körper ganz auf
    Selbstdurchdringung zu prüfen — die Auswertung hat es um die bewegten
    Stellen schon getan, und was ein späterer Schritt behoben hat, steht dort
    nicht mehr.
    """
    from app.core.scene.cancel import NeverCancelled

    token = cancelled if cancelled is not None else NeverCancelled()
    token.raise_if_cancelled()
    findings: list[Finding] = []
    meshes = []
    for entry in objects:
        token.raise_if_cancelled()
        meshes.append(as_mesh_data(entry.mesh))
    token.raise_if_cancelled()

    if export_format in SOLID_ONLY_FORMATS:
        # Gemeldet wird je Objekt, nicht einmal für alles: Bei gemischter
        # Auswahl schreibt der Export die exakten Körper und lässt die Netze
        # aus, und dann will der Nutzer wissen, welche.
        for entry in objects:
            # ``kind_of`` und kein zweites ``isinstance``: Welche Sorte ein
            # Körper ist, entscheidet eine Regel an einem Ort (siehe dort).
            if kind_of(entry.mesh) != "brep":
                findings.append(
                    Finding(
                        code="export.needs_solid",
                        severity="error",
                        message=_(
                            "STEP speichert einzeln bearbeitbare Flächen und Kanten, der Körper "
                            "besteht aus festen Dreiecken. „In Flächen und Kanten umwandeln“ "
                            "macht sie daraus; STL und 3MF nehmen ihn, wie er ist."
                        ),
                        object_id=entry.id,
                        values={"format": export_format},
                    )
                )

    for entry, mesh in zip(objects, meshes, strict=True):
        token.raise_if_cancelled()
        if not mesh.is_watertight:
            findings.append(
                Finding(
                    code="export.not_watertight",
                    severity="warning",
                    message=_("Das Objekt ist nicht geschlossen — der Slicer wird raten müssen."),
                    object_id=entry.id,
                )
            )
        if mesh.triangle_count == 0:
            findings.append(
                Finding(
                    code="export.empty",
                    severity="error",
                    message=_("Das Objekt hat keine Geometrie."),
                    object_id=entry.id,
                    # **Der schwerste Befund des Exports endete mit „hat keine
                    # Geometrie".** Ein ``error`` ist das Stärkste, was der
                    # Prüfbericht sagen kann, und dieser bot nichts an — weder
                    # hier noch über ``panels.FINDING_ACTIONS``. Das ist „geht
                    # nicht" an einem anderen Ort, und Regel 17 gilt im Bericht
                    # so gut wie im Dialog.
                    #
                    # Zwei Auswege, beide wahr: Ein Objekt ohne Dreiecke ist
                    # entweder das falsche in der Auswahl, oder das Ergebnis
                    # eines Schritts, der nichts übrig gelassen hat — dann
                    # steht im Verlauf, welcher. Ein dritter wäre geraten.
                    suggestions=(CHANGE_SELECTION, SHOW_HISTORY),
                )
            )

    findings.extend(
        check_build_volume(
            meshes,
            profile,
            [entry.plate for entry in objects],
            [entry.id for entry in objects],
            # Hier entsteht die Datei. Eine falsche Lage ist damit keine Frage
            # mehr, die ein Klick beantwortet — CuraEngine schreibt eine
            # Druckdatei, die neben der Platte druckt, und prüft nichts.
            about_to_write=True,
        )
    )
    findings.extend(_licence_findings(sources))
    findings.extend(_fits_and_walls(objects, profile, scene, document, token))
    exported = {entry.id for entry in objects}
    findings.extend(
        finding
        for finding in evaluated
        if finding.code in CARRIED_TO_EXPORT and finding.object_id in exported
    )
    token.raise_if_cancelled()
    return findings


#: Befunde der Auswertung, die die Prüfung vor dem Export weitersagt: was am
#: Körper kaputt ist und sich nicht ohne Weiteres nachmessen lässt.
CARRIED_TO_EXPORT: Final = frozenset({"sculpt.pierced"})


def _fits_and_walls(
    objects: list[SceneObject],
    profile: Profile,
    scene: Scene | None,
    document: Document | None,
    cancelled: CancelToken,
) -> list[Finding]:
    """Die zwei Fragen aus §29, die ein einzelner Körper nicht beantwortet.

    Eine Passung steht **zwischen** zwei Merkmalen, eine Wand zwischen einer
    Bohrung und dem Mantel um sie herum — beides steht in keinem der Körper,
    die gerade geschrieben werden, sondern in der Szene, aus der sie kommen.
    Deshalb lagen die zwei Zeilen von §29 seit je brach: Die Prüfung sah nur
    die Auswahl.

    **Gefragt wird an der Szene, geantwortet wird über die Auswahl.** Die
    Passungen laufen gegen die ganze Szene — eine Passung, deren zweite Hälfte
    nicht mit exportiert wird, lässt sich sonst gar nicht auflösen und käme als
    „Merkmal verloren" zurück, was sie nicht ist. Gemeldet wird davon, was
    einen der geschriebenen Körper betrifft. Die Wandstärke braucht diese
    Vorsicht nicht: Sie gehört einem Körper, also rechnet sie auf der
    eingeschränkten Szene.

    Träge importiert, damit die Exportschicht das Szenenpaket nicht beim Laden
    mitzieht — dieselbe Bauart wie bei ``handover`` und ``brep`` darüber.
    """
    if scene is None:
        return []
    from app.core.scene.evaluate import check_thin_walls
    from app.core.scene.fits import check as check_fits

    wanted = {entry.id for entry in objects}
    related = {fit.name for fit in scene.fits if {fit.a.object_id, fit.b.object_id} & wanted}
    findings = [
        finding
        for finding in check_fits(scene, profile, document=document, cancelled=cancelled)
        if (
            finding.object_id is None
            or finding.object_id in wanted
            or finding.values.get("fit") in related
        )
    ]
    findings.extend(
        check_thin_walls(
            replace(
                scene,
                objects={key: value for key, value in scene.objects.items() if key in wanted},
                profile=profile,
            )
        )
    )
    return findings


def _licence_findings(sources: dict[str, Source]) -> list[Finding]:
    """§16.3: ein sachlicher Hinweis, wenn eine Quelle eine Einschränkung
    trägt. Keine Belehrung.
    """
    restricted = [
        source for source in sources.values() if source.origin is not None and source.origin.licence
    ]
    if not restricted:
        return []
    return [
        Finding(
            code="export.source_licence",
            severity="info",
            message=_("Beteiligte Quellen stehen unter einer Lizenz."),
            values={
                "sources": ", ".join(
                    f"{source.origin.title or source.id}: {source.origin.licence}"
                    for source in restricted
                    if source.origin is not None
                )
            },
        )
    ]


def write_plan(
    plan: ExportPlan, directory: Path, export_format: ExportFormat = "stl"
) -> list[Path]:
    """Schreibt die geplanten Dateien und gibt zurück, was geschrieben wurde."""
    # §2 C: Planen und Prüfen sind Lesen, das Herausgeben einer Datei nicht.
    activation.require(activation.EXPORT)
    written: list[Path] = []
    # **Jeder Schreibfehler wird ein AppError.** Vorher lief hier jeder
    # ``OSError`` weiter: In der Kommandozeile endete ein Export in ein Ziel,
    # das schon eine Datei ist, mit einem Stapelabzug — im Nutzerdialog
    # verboten (§2.7). Im Fenster war es stiller und schlimmer: Der
    # Export-Arbeiter fängt ``AppError``, ein ``OSError`` riss den Thread ab,
    # und danach geschah gar nichts mehr.
    #
    # Der Grund kommt vom Betriebssystem und bleibt unübersetzt: „Zugriff
    # verweigert" gegen „Datei nicht gefunden" ist die eigentliche Auskunft.
    # **Was das Format nicht tragen kann, wird ausgelassen — nicht abgebrochen.**
    # ``check_before_export`` sagt es je Objekt und begründet es damit, dass
    # „der Export die exakten Körper schreibt und die Netze auslässt". Getan
    # hat er das nie: Beim ersten Netz flog die Ausnahme, mitten im Schreiben.
    # War ein exakter Körper davor, lag seine Datei schon da — ein halber
    # Export mit einer Fehlermeldung darüber (§30, §29).
    # Ausgelassen wird nach **Objekt-ID**, nicht nach Dateiname: fielen ein
    # exakter Körper und ein Netz auf denselben Namen, nahm der Vergleich per
    # Name den exakten mit heraus, obwohl gerade er geschrieben werden sollte.
    skipped = {
        entry.object_id
        for entry in plan.entries
        if export_format in SOLID_ONLY_FORMATS and not _is_exact(entry.body)
    }
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for entry in plan.entries:
            if entry.object_id in skipped:
                continue
            target = directory / entry.filename
            target.write_bytes(
                export_bytes(entry.mesh, export_format, list(entry.slots), entry.name, entry.body)
            )
            written.append(target)
    except OSError as problem:
        raise FileWriteError(
            target=str(problem.filename or directory),
            detail=str(problem.strerror or problem),
        ) from problem
    if skipped and not written:
        # Nichts blieb übrig. Ein Aufruf, der leise null Dateien schreibt und
        # Erfolg meldet, ist schlimmer als der Fehler davor.
        raise _needs_solid()
    if skipped:
        _log.info("left out %d body/bodies without exact geometry: %s", len(skipped), skipped)
    _log.info("exported %d file(s) to %s", len(written), directory)
    return written


def _is_exact(body: Mesh | None) -> bool:
    """Hat dieses Objekt Flächen und Kanten — oder nur Dreiecke (§30)?

    ``kind_of`` und kein zweites ``isinstance``, aus demselben Grund wie in
    :func:`check_before_export`: Welche Sorte ein Körper ist, entscheidet eine
    Regel an einem Ort. Die beiden Stellen müssen dasselbe sagen, sonst meldet
    der Bericht etwas anderes, als der Schreiber tut.
    """
    return body is not None and kind_of(body) == "brep"


def mesh_for_export(body: Mesh, profile: Profile) -> MeshData:
    """Die Dreiecke, die in die Datei gehen — bei einem exakten Körper so fein,
    wie das Verfahren des Druckers sie braucht (§29, §30).

    Ein exakter Körper trägt seine eigene Vernetzung, gerechnet mit der Zahl
    des Kerns (``units.MAX_FACET_SAG``, 0,05 mm). Für eine 0,4er Düse ist das
    fein genug; ein Resin-Drucker mit 50 µm Pixeln bildet eine Facette von
    fünf Hundertsteln als Stufe ab. Der Export vernetzt deshalb neu, wenn das
    Profil eine feinere Abweichung verlangt als die, die der Körper hat
    (:attr:`Profile.export_deflection`) — und nur dann: Gröber als der Körper
    wird keine Datei, und ein Netz bleibt, was es ist.

    Die Anzeige und die Erkennung bleiben bei der Vernetzung des Körpers;
    das hier ist die Datei, und die geht in den Slicer.
    """
    if not isinstance(body, BRepBody):
        return as_mesh_data(body)
    wanted = profile.export_deflection
    if wanted >= body.deflection - EPS_GEOM:
        return as_mesh_data(body)
    tessellated = body.to_mesh(deflection=wanted)
    if not isinstance(tessellated, MeshData):
        return as_mesh_data(body)
    _log.info(
        "tessellated an exact body for export at %.4f mm instead of %.4f mm",
        wanted,
        body.deflection,
    )
    return tessellated


def _tessellation_finding(objects: Sequence[SceneObject], profile: Profile) -> list[Finding]:
    """Sagt, mit welcher Abweichung die exakten Körper in die Datei gegangen sind.

    Nur wo es einen Unterschied gibt: Ein Netz wird nicht neu vernetzt, und
    ein exakter Körper, dessen eigene Vernetzung schon fein genug ist, auch
    nicht. Eine Zeile für alle, nicht je Körper — zwölf gleiche Sätze verdrängen
    andere (§26.1).
    """
    wanted = profile.export_deflection
    finer = [
        entry
        for entry in objects
        if isinstance(entry.mesh, BRepBody) and wanted < entry.mesh.deflection - EPS_GEOM
    ]
    if not finer:
        return []
    return [
        Finding(
            code="export.tessellated",
            severity="info",
            message=_(
                "Die exakten Körper wurden für diesen Drucker feiner vernetzt: Die "
                "Dreiecke weichen höchstens {deflection} von den Flächen ab.",
                deflection=format_length(wanted),
            ),
            values={"deflection_mm": wanted, "objects": len(finer)},
        )
    ]


def _written(target: Path, payload: bytes) -> Path:
    """Schreibt eine Datei und macht aus einem ``OSError`` einen ``AppError``.

    Denselben Grund wie in :func:`write_plan`, und dieselbe Wunde: Das Ziel
    ist schreibgeschützt, liegt im Slicer offen oder ist gar kein Ordner. Ohne
    diese Umwandlung endet die Kommandozeile in einem Stapelabzug (§2.7
    verbietet ihn im Nutzerdialog), und im Fenster geschieht etwas Stilleres
    und Schlimmeres: Der Export-Arbeiter fängt ``AppError``, ein ``OSError``
    reißt den Thread ab, und danach passiert gar nichts mehr.

    Der Grund kommt vom Betriebssystem und bleibt unübersetzt: „Zugriff
    verweigert" gegen „Datei nicht gefunden" ist die eigentliche Auskunft.
    """
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    except OSError as problem:
        raise FileWriteError(
            target=str(problem.filename or target),
            detail=str(problem.strerror or problem),
        ) from problem
    return target


@dataclass(frozen=True, slots=True)
class _PartValues:
    """Was ein Teil anders bekommt als die Platte, und warum."""

    keys: dict[str, str]
    """Die Objektwerte in der Sprache des Slicers."""
    applied: list[SettingAdvice]
    """Der Rat, den die Werte tragen."""
    unavailable: list[SettingAdvice]
    """Der Rat, den dieser Slicer je Teil nicht annimmt."""
    effective: PrintSettings | None
    """Womit dieses Teil gedruckt wird — für seine Stützsperre."""
    asked: tuple[SettingAdvice, ...] = ()
    """Der Rat dieses Teils zu Pfaden, die der Slicer nur plattenweit annimmt —
    gleich ob die Platte ihn schon trägt (:func:`_plate_wide_findings`)."""


@dataclass(frozen=True, slots=True)
class _PartAdviceMemo:
    """Der letzte Rat am Netz, samt allen Eingaben und der gelesenen Analyse."""

    inputs: tuple[object, ...]
    result: SliceResult | None
    advice: tuple[SettingAdvice, ...]


def part_advice(
    entry: SceneObject,
    mesh: MeshData,
    settings: PrintSettings,
    profile: Profile,
    setup: SlicerSetup | None,
    slot_profiles: Mapping[threemf.SlotKey, str],
    *,
    result: SliceResult | None,
    fit_kinds: Sequence[str],
    flavour: SlicerFlavour | None = None,
    accepted: Mapping[str, object] | None = None,
) -> list[SettingAdvice]:
    """Was dieses Teil anders braucht als die Platte (§29, Entscheidung G).

    Der Rat je Körper (:func:`advise.for_part`), gefragt für jede Spule, die
    der Körper benutzt, mit deren Einstellungen und Material
    (:func:`handover.slot_processes`), und zusammengeführt wie der Rat im
    Druckdialog (:func:`advise.combine`). Der Export schreibt daraus die
    Objektwerte, der Druckdialog nennt damit die Teile einer Zeile — beide
    fragen diese Funktion, damit die Zeile kein Teil nennt, das die Datei nicht
    bekommt.

    Die Grundfläche kommt aus einem Schnitt knapp über dem Boden, nicht aus dem
    Hüllquader: Ein Teil auf drei schmalen Armen hat eine große Grundfläche und
    kaum Halt. Passungen (``fit_kinds``) und Zapfen zählen nur, wenn dieses
    Teil sie trägt. ``flavour`` sagt, ob der Slicer unter „automatisch“ seinen
    Brim selbst rechnet (:data:`advise.AUTO_BRIM_FLAVOURS`).

    **Eine Regel kann einen Wert je Teil voraussetzen** (``accepted``, die
    übernommenen Werte je Teil aus :meth:`handover.PartSplit.accepted_per_part`):
    „Außenwand zuerst“ folgt am Keil erst auf Arachne, und ``settings`` trägt
    für beide die Grundlage. Verlangt dieses Teil einen übernommenen Wert,
    wird er angewandt und erneut gefragt, bis nichts dazukommt — höchstens
    einmal je übernommenem Pfad. In die Kette geht nur, was übernommen ist, und
    nur mit dem übernommenen Wert; ``was`` bleibt der Wert von ``settings``.

    Der letzte Rat je Objekt bleibt am Netz für weitere Platten desselben Auftrags.
    Vor dem Vergleich werden die Spulenprofile erneut aufgelöst; Passungen,
    Verbinder, Übernahmen und die gelesene Analyse gehören zum Schlüssel.
    """
    # Erst hier: ``handover`` zieht die G-Code-Auswertung mit, und ein Export
    # soll nicht davon abhängen, dass ein Slicer im Spiel ist.
    from app.core.export import handover
    from app.core.slice import advise
    from app.core.slice.analysis import cross_section

    connectors = advise.connector_diameters([entry])
    processes = handover.slot_processes(entry, settings, profile, setup, slot_profiles)
    program = slicer_keys.program_of(setup.executable) if setup is not None else ""
    inputs = (
        settings,
        processes,
        tuple(fit_kinds),
        connectors,
        flavour,
        program,
        dict(accepted or {}),
    )
    cache = getattr(mesh.raw, "_cache", None)
    name = f"solidon_export_advice|{entry.id}"
    stored = cache[name] if cache is not None else None
    if isinstance(stored, _PartAdviceMemo) and stored.inputs == inputs and stored.result is result:
        return list(stored.advice)
    lowest = float(mesh.bounds.minimum[2])
    section = cross_section(mesh, lowest + FOOTPRINT_HEIGHT)
    footprint = 0.0 if section is None or section.is_empty else float(section.area)

    def remember(advice: list[SettingAdvice]) -> list[SettingAdvice]:
        if cache is not None:
            cache[name] = _PartAdviceMemo(inputs, result, tuple(advice))
        return advice

    def asked(current: PrintSettings) -> list[SettingAdvice]:
        groups = [
            (
                process.settings,
                advise.for_part(
                    process.settings,
                    mesh.bounds,
                    footprint,
                    profile=process.profile,
                    result=result,
                    fit_kinds=fit_kinds,
                    connectors=connectors,
                    flavour=flavour,
                ),
            )
            for process in (
                processes
                if current is settings
                else handover.slot_processes(entry, current, profile, setup, slot_profiles)
            )
        ]
        return advise.combine(current, groups)

    # Was das Programm seiner Familie nicht kennt, schlägt der Rat nicht vor:
    # SuperSlicer stürzte an der Schrägnaht als Objektwert ab (RM-459). Eine
    # Wahl, die es nicht kennt, schlägt er als ihren Ersatz vor (RM-480).
    unknown = slicer_keys.NOT_TAKEN_BY_PROGRAM.get(program, frozenset())

    def asked_here(current: PrintSettings) -> list[SettingAdvice]:
        return slicer_keys.offered(
            [item for item in asked(current) if item.path not in unknown], program
        )

    advice = asked_here(settings)
    chain = dict(accepted or {})
    served: dict[str, SettingAdvice] = {}
    current = settings
    for _round in range(len(chain)):
        follows = [
            item
            for item in advice
            if item.path in chain
            and item.path not in served
            and same_value(item.value, chain[item.path])
        ]
        if not follows:
            break
        served.update((item.path, item) for item in follows)
        current = advise.apply(current, follows)
        advice = asked_here(current)
    if not served:
        return remember(advice)
    # Was eine spätere Runde zu einem schon angewandten Pfad sagt, hat den
    # Stand der früheren gesehen und gewinnt; ``was`` gilt ``settings``.
    merged = dict(served)
    merged.update((item.path, item) for item in advice)
    return remember(
        [
            replace(item, was=read_path(settings, item.path))
            for item in merged.values()
            if not same_value(item.value, read_path(settings, item.path))
        ]
    )


def _part_values(
    entry: SceneObject,
    mesh: MeshData,
    split: PartSplit | None,
    profile: Profile,
    flavour: SlicerFlavour,
    setup: SlicerSetup | None,
    slot_profiles: Mapping[threemf.SlotKey, str],
    document: Document | None,
    cancelled: CancelToken | None,
) -> _PartValues:
    """Was dieses Teil anders braucht als die Platte (§29, Entscheidung G) — und warum.

    Gefragt wird der Rat je Körper (:func:`part_advice`) für die Pfade, die
    der Split je Teil führt: Stützen nur am Körper, der sie braucht, ein Brim
    nur unter dem, der schlank ist oder auf wenig Fläche steht, die Werte einer
    Passung nur am Teil, das sie trägt.

    **Der Rat reist mit heraus**: ein Wert ohne Begründung ist im Zweifel
    schlechter als die Vorgabe, weil niemand ihn nachprüfen kann.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if split is None:
        return _PartValues({}, [], [], None)
    wanted = split.per_part | split.unavailable
    if not wanted:
        return _PartValues({}, [], [], split.plate)
    from app.core.knowledge import profiles as profile_table
    from app.core.scene.fits import fit_kinds_for
    from app.core.slice import advise

    # Geschnitten wird nur, wenn der Rat je Teil den Schnitt braucht; Passung
    # und Verbinder kommen ohne aus (:data:`advise.SLICED_PATHS`).
    result = (
        _body_analysis(
            entry,
            mesh,
            split.base,
            profile_table.for_process(
                profile_table.for_object(profile, entry), split.base, effective=True
            ),
            cancelled,
        )
        if wanted & advise.SLICED_PATHS
        else None
    )
    advice = part_advice(
        entry,
        mesh,
        split.base,
        profile,
        setup,
        slot_profiles,
        result=result,
        fit_kinds=fit_kinds_for(document, {entry.id}) if document is not None else (),
        flavour=flavour,
        accepted=split.accepted_per_part(),
    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    applied = [item for item in advice if item.path in split.per_part]
    asked = tuple(item for item in advice if item.path in split.unavailable)
    # Was die Platte schon mit diesem Wert trägt, bekommt das Teil auch —
    # nicht erfüllt ist nur ein anderer Wert.
    unavailable = [
        item for item in asked if not same_value(item.value, read_path(split.plate, item.path))
    ]
    program = slicer_keys.program_of(setup.executable) if setup is not None else ""
    return replace(
        _values_for(split, applied, unavailable, flavour, program=program, profile=profile),
        asked=asked,
    )


def _values_for(
    split: PartSplit,
    applied: Sequence[SettingAdvice],
    unavailable: Sequence[SettingAdvice],
    flavour: SlicerFlavour,
    everywhere: Sequence[SettingAdvice] = (),
    *,
    program: str = "",
    profile: Profile | None = None,
) -> _PartValues:
    """Objektwerte und wirksame Einstellungen eines Teils aus seinem Rat.

    ``everywhere`` sind übernommene Vorschläge, die beim Export kein Teil für
    sich verlangt hat (:func:`_unserved`). Sie stehen an diesem Teil wie sein
    eigener Rat, tragen aber keinen Befund *dieses* Teils. ``program`` ist
    die Marke des Slicers (``slicer_keys.program_of``, RM-480).
    """
    from app.core.export import handover
    from app.core.slice import advise

    if not split.revert:
        carried = [*applied, *everywhere]
        return _PartValues(
            handover.object_keys(
                split.plate,
                carried,
                flavour,
                program=program,
                profile=profile,
                native=split.native,
                brim_foot_offset=split.brim_foot_offset,
            ),
            list(applied),
            list(unavailable),
            advise.apply(split.plate, carried),
        )
    # **Cura umgekehrt**: Die Platte trägt die Übernahme. Was dieses Teil nicht
    # braucht, bekommt es je Netz als Grundlage zurück; was es braucht, mit dem
    # eigenen Wert, wo Cura den ganzen Pfad je Netz annimmt, sonst mit dem der
    # Platte. Die Rücknahme ist kein Rat an den Kunden und trägt keinen Grund.

    def as_cura_takes_it(item: SettingAdvice) -> SettingAdvice:
        if handover.cura_takes_whole(item.path):
            return item
        if item.path == "support.style":
            # Ein/aus geht je Netz. Ein eingeschaltetes Netz bekommt die
            # Stützart der Platte; „aus“ bleibt auch unter Bäumen aus.
            if item.value == "none":
                return item
            actual = "tree" if split.plate.support.style == "tree" else "grid"
            return replace(item, value=actual)
        return replace(item, value=read_path(split.plate, item.path))

    missing = list(unavailable)
    own = []
    for item in applied:
        actual = as_cura_takes_it(item)
        if same_value(item.value, actual.value) or (
            item.path == "support.style" and item.value == "auto"
        ):
            own.append(actual)
        elif item not in missing:
            missing.append(item)
    # Unerfüllte Stützarten müssen beim erneuten Schreiben (``everywhere``)
    # ihre Ein/aus-Wirkung behalten, auch ohne falschen Übernahmebefund.
    received = [*applied, *(item for item in unavailable if item.path in split.per_part)]
    carried = [as_cura_takes_it(item) for item in [*received, *everywhere]]
    needed = {item.path for item in carried}
    changes = carried + [
        SettingAdvice(
            path=path,
            value=read_path(split.base, path),
            was=read_path(split.plate, path),
            reason="",
        )
        for path in sorted(split.per_part - needed)
    ]
    keys = {
        key: value
        for key, value in handover.object_keys(
            split.plate, changes, flavour, program=program, profile=profile
        ).items()
        if key in handover.CURA_PER_MESH
    }
    return _PartValues(keys, own, missing, advise.apply(split.plate, changes))


def _unserved(
    split: PartSplit | None, accepted: PrintSettings | None, values: Iterable[_PartValues]
) -> list[SettingAdvice]:
    """Übernommene Vorschläge je Teil, die beim Export kein Teil bekommt.

    **Ein übernommener Vorschlag verschwindet nie still** (Durchsicht 0.5.1,
    B2). Der Split setzt einen übernommenen Pfad auf der Platte auf die
    Grundlage zurück, und der Rat je Teil wird dort gefragt. Schweigt er dort
    für jedes Teil, landete der Wert nirgends: Am Centauri Carbon 2 wählte der
    Kunde „Skirt", der Dialog bot dem schlanken Turm „Brim" an, und nach dem
    Übernehmen hielt Elegoos Auto-Brim der Grundlage den Rat je Teil still —
    in der Datei stand weder ein Brim am Turm noch einer auf der Platte, und
    kein Befund sagte es. Dasselbe, wenn Dialog und Export den Rat je Teil
    verschieden beantworten (Anzeige- gegen Exportnetz).

    Solche Werte gehen deshalb an **jedes** Teil, als Objektwert. Die Platte
    bleibt, wie der Split sie schreibt: So rechnet der Konsolenlauf
    (``handover.slice_model``), der den Split ohne die Teile fragt, mit
    derselben Platte wie die Datei. Was schon die Grundlage trägt, fehlt nicht.
    """
    if split is None or accepted is None:
        return []
    served = {item.path for entry in values for item in (*entry.applied, *entry.unavailable)}
    return [
        SettingAdvice(
            path=path,
            value=read_path(accepted, path),
            was=read_path(split.base, path),
            reason="",
        )
        for path in sorted(split.per_part - served)
        if not same_value(read_path(accepted, path), read_path(split.base, path))
    ]


def _served_elsewhere(
    others: Sequence[SceneObject],
    paths: frozenset[str],
    split: PartSplit,
    profile: Profile,
    flavour: SlicerFlavour,
    setup: SlicerSetup | None,
    slot_profiles: Mapping[threemf.SlotKey, str],
    document: Document | None,
    cancelled: CancelToken | None,
) -> frozenset[str]:
    """Welche dieser Pfade ein Teil des Auftrags auf einer anderen Platte verlangt.

    Durchsicht 0.5.1, N1: *Slicen* schreibt je Platte eine Datei, und
    :func:`_unserved` sah nur die eigene. Lag der Pilz, der Stützen verlangt,
    auf Platte 1, bekam auf Platte 2 jeder Klotz Stützen — der Ausgangsfehler
    von Entscheidung G, auf den übrigen Platten zurück. Gefragt wird derselbe
    Rat je Teil wie beim Schreiben (:func:`_part_values`), und nur, solange
    ein Pfad noch offen ist.
    """
    open_paths = set(paths)
    served: set[str] = set()
    for entry in others:
        if not open_paths:
            break
        values = _part_values(
            entry,
            mesh_for_export(entry.mesh, profile),
            split,
            profile,
            flavour,
            setup,
            slot_profiles,
            document,
            cancelled,
        )
        hit = {item.path for item in (*values.applied, *values.unavailable)} & open_paths
        served |= hit
        open_paths -= hit
    return frozenset(served)


def _finding_value(value: object) -> float | str:
    """Ein Einstellungswert, wie ihn ein Befund trägt: Zahl, Wahrheitswert oder Wort."""
    return value if isinstance(value, int | float | str) else str(value)


@dataclass(frozen=True, slots=True)
class _BodyAnalysisMemo:
    """Der letzte Exportschnitt einer Detailstufe, mit Raster, Winkel und Brückenbreite."""

    inputs: tuple[float, float, float, float]
    result: SliceResult


def _body_analysis(
    entry: SceneObject,
    mesh: MeshData,
    settings: PrintSettings,
    profile: Profile,
    cancelled: CancelToken | None,
    *,
    detail: Literal["full", "support"] = "full",
) -> SliceResult:
    """Die Schichten dieses Körpers mit dem Raster und der Stützschwelle, die
    hinausgehen — die des Prüfberichts, wenn er sie schon hat.

    **Mit der Schwelle, mit der der Slicer stützt** (Konzept Herstellerprofil,
    Entscheidung L): ``settings`` ist, was hinausgeht, samt der Grundlage des
    Herstellers. Mit dem Profil allein sperrte Solidon Kanäle nach seiner
    Tabelle, während der Slicer nach dem gewählten Prozess stützt.

    **Erst die Schichten des Prüfberichts** (DRUCK-14, Durchsicht 0.5.1): Er
    hat dasselbe Netz mit demselben Raster, Winkel und derselben Brückenbreite
    schon geschnitten; am Eiffelturm aus dem Korpus kostete der zweite Schnitt
    vor dem Start des Slicers den größten Teil von 17 s.
    """
    from app.core.knowledge import profiles as profile_table
    from app.core.slice.analysis import slice_body
    from app.core.slice.findings import remembered_analysis

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    wall, angle = profile_table.analysis_limits(
        profile_table.for_process(profile, settings, effective=True), entry
    )
    result = remembered_analysis(mesh, settings, angle, wall)
    if result is not None:
        return result
    # Ein Exportschnitt ist ohne Stützvolumen kein vollständiger Bericht.
    # Er bleibt deshalb separat; seine volle Detailstufe genügt auch der Sperre.
    cache = getattr(mesh.raw, "_cache", None)
    key = (settings.layers.layer_height, settings.layers.first_layer_height, angle, wall)
    name = "solidon_export_slice"
    if cache is not None:
        for candidate in ("full", detail):
            stored = cache[f"{name}|{candidate}"]
            if isinstance(stored, _BodyAnalysisMemo) and stored.inputs == key:
                return stored.result
    result = slice_body(
        mesh,
        settings.layers.layer_height,
        first_layer_height=settings.layers.first_layer_height,
        overhang_angle=angle,
        bridge_from=wall,
        detail=detail,
        support_volume=False,
        cancelled=cancelled,
    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if cache is not None:
        cache[f"{name}|{detail}"] = _BodyAnalysisMemo(key, result)
    return result


#: Die Befunde, mit denen der Export sagt, was ein Teil anders bekommt als die
#: Platte. ``setting`` trägt den Punktpfad; Feldname und Wert in Worten setzt
#: die Oberfläche dazu (``panels``), denn beide kennt nur der Druckdialog.
PART_SETTING_CODES: Final = frozenset(
    {"export.part_setting", "export.part_setting_unavailable", "export.part_setting_all"}
)


def _part_setting_findings(
    advice: Sequence[tuple[ObjectId, SettingAdvice]], *, applied: bool = True
) -> list[Finding]:
    """Was der Export je Teil selbst entschieden hat — ein Befund je Teil und Einstellung.

    **Je Teil, mit dessen Kennung**, damit ein Klick im Prüfbericht die Teile
    wählt, für die es gilt, und der Tooltip sie beim Namen nennt. Gleiche Sätze
    bündelt der Bericht zu einer Zeile mit ihrer Zahl davor (``panels._bundled``)
    — zwölf Behälter auf zu kleiner Fläche verdrängen dort nichts (§26.1). Der
    Satz ist der Grund des Rats; bis zur Durchsicht 0.5.1 (B4) stand für alle
    vierzehn Pfade derselbe, ohne Teil, und im Tooltip Punktpfad und ``True``.

    Bei übernommenen Werten kommt die Schwere vom Rat selbst. ``for_part`` gibt
    ``info``, und das ist richtig: Hier hat die Anwendung etwas getan, das
    der Kunde wissen soll — ein Brim kostet Material und muss abgeschnitten
    werden. Kann die Ausgabe die Werte nicht tragen, wird daraus eine Warnung.
    """
    return [
        Finding(
            code="export.part_setting" if applied else "export.part_setting_unavailable",
            severity=entry.severity if applied else "warning",
            message=(
                _("Nur für dieses Teil: {reason}", reason=entry.reason)
                if applied
                else _(
                    "Dieser Slicer übernimmt den genannten Vorschlag nicht für dieses Teil. "
                    "Prüfen Sie die Einstellung für die ganze Platte oder wählen Sie einen "
                    "Slicer, der diesen Wert je Teil übernimmt."
                )
            ),
            # Beim übernommenen Wert steht der Grund im Satz; wo der Slicer ihn
            # nicht trägt, bleibt er im Tooltip, damit der Rat nachprüfbar bleibt.
            values={
                "setting": entry.path,
                "value": _finding_value(entry.value),
                **({} if applied else {"reason": entry.reason}),
            },
            object_id=part,
        )
        for part, entry in advice
    ]


def _plate_wide_findings(
    chosen: Sequence[SceneObject],
    asked: Mapping[ObjectId, Sequence[SettingAdvice]],
    split: PartSplit | None,
) -> list[Finding]:
    """Wer eine Übernahme mitbekommt, die nur ein anderes Teil verlangt (RM-430).

    Nimmt der Slicer einen Pfad nicht je Teil an — etwa Curas Haftungsart
    oder Bambus Beschleunigung —, bleibt die Übernahme plattenweit. Das Teil, das
    sie verlangt, ist bedient; die übrigen bekommen sie trotzdem, und das
    sagt dieser Befund an ihnen, mit dem Grund des verlangenden Teils. Verlangt
    hier kein Teil den Wert, bleibt es still wie bisher.
    """
    if split is None or not split.unavailable:
        return []
    findings: list[Finding] = []
    for path in sorted(split.unavailable):
        value = read_path(split.plate, path)
        if same_value(value, read_path(split.base, path)):
            continue
        askers = {
            entry.id: item
            for entry in chosen
            for item in asked.get(entry.id, ())
            if item.path == path
        }
        if not askers:
            continue
        reason = next(iter(askers.values())).reason
        findings += [
            Finding(
                code="export.part_setting_unavailable",
                severity="warning",
                message=_(
                    "Gilt auch für dieses Teil: Dieser Slicer übernimmt die Einstellung nur "
                    "für die ganze Platte, nicht für einzelne Teile."
                ),
                values={
                    "setting": path,
                    "value": _finding_value(value),
                    "reason": reason,
                },
                object_id=entry.id,
            )
            for entry in chosen
            if entry.id not in askers
        ]
    return findings


#: Um so viel greift die Stützsperre über den Grundriss einer Kanaldecke
#: hinaus, in mm: eine Bahnbreite der 0,4er Düse, damit auch der Rand, den der
#: Slicer mit seinem eigenen Winkel noch als Überhang liest, darunter liegt.
#: Nach außen schadet der Zuschlag nicht — dort ist Wand.
BLOCKER_MARGIN: Final = 0.5

#: Um so viel darf der Umriss einer Kanalscheibe vereinfacht werden, bevor sie
#: zum Sperrkörper wird, in mm — ein Fünfundzwanzigstel von
#: :data:`BLOCKER_MARGIN`, der den Umriss danach ohnehin nach außen schiebt.
#: Die Scheiben sind Vereinigungen von Kreisen zu je 64 Ecken und von
#: Schnittkonturen; unvereinfacht hatte die Sperre am Eiffelturm aus dem
#: Korpus 404 464 Dreiecke und kostete 12,6 s, vereinfacht 177 454 und 1,4 s,
#: bei 27 von 129 985 mm³ weniger vor dem Zuschlag (26.09.2026, unter Last).
BLOCKER_SIMPLIFY: Final = 0.02


def _support_blocker(
    entry: SceneObject,
    mesh: MeshData,
    settings: PrintSettings,
    profile: Profile,
    cancelled: CancelToken | None = None,
    *,
    result: SliceResult | None = None,
) -> tuple[MeshData | None, list[Finding]]:
    """Die Stützsperre für die Kanäle dieses Teils (§22.2, §29).

    Solidon weiß aus der Schichtanalyse, wo eine Decke in einem schmalen
    Kanal liegt und sich selbst schließt (:func:`analysis.model_support`);
    der Slicer weiß es nicht. Ohne Sperre füllt er den Kanal, sobald er auf
    dem Modell stützen darf — und Orcas organische Bäume tun es auch „nur vom
    Bett", mit Stämmen durch die Wand (Waschschüssel, 25.09.2026). Die Sperre
    füllt den freien Kanalraum in Scheiben von einem Millimeter
    (:func:`analysis.channel_space`).

    Abbrechbar zwischen den Schritten und im Schnitt selbst: Am Eiffelturm aus
    dem Korpus dauert das alles zusammen eine Viertelminute (26.09.2026).
    """
    import manifold3d
    import shapely

    from app.core.slice.analysis import channel_space, model_support

    # **Die Schichten des Prüfberichts, sonst ein eigener Schnitt**
    # (:func:`_body_analysis`, DRUCK-14): mit dem Raster und der Stützschwelle,
    # die hinausgehen (Entscheidung L). ``detail="support"`` spart Breiten und
    # Brücken; hat der Rat je Teil den Körper schon geschnitten, gilt dessen
    # Ergebnis.
    if result is None:
        result = _body_analysis(entry, mesh, settings, profile, cancelled, detail="support")
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    model = model_support(result)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    slabs = channel_space(result, model)
    if not slabs:
        return None, []
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    prisms = []
    for bottom, top, flat in slabs:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        region = shapely.simplify(flat, BLOCKER_SIMPLIFY, preserve_topology=True)
        rings: list[np.ndarray] = []
        for part in getattr(region, "geoms", [region]):
            rings.append(np.asarray(part.exterior.coords)[:-1])
            rings += [np.asarray(hole.coords)[:-1] for hole in part.interiors]
        section = manifold3d.CrossSection(rings, manifold3d.FillRule.EvenOdd).offset(
            BLOCKER_MARGIN, manifold3d.JoinType.Miter
        )
        prisms.append(
            manifold3d.Manifold.extrude(section, top - bottom).translate((0.0, 0.0, bottom))
        )
    solid = manifold3d.Manifold.batch_boolean(prisms, manifold3d.OpType.Add).to_mesh()
    blocker = MeshData(
        trimesh.Trimesh(
            np.asarray(solid.vert_properties)[:, :3], np.asarray(solid.tri_verts), process=False
        )
    )
    finding = Finding(
        code="export.support_blocker",
        severity="info",
        message=_(
            "In „{name}“ liegen Decken in schmalen Kanälen. Die gewählte Kanalsperre hält dort "
            "Stützen fern, die sich nach dem Druck schlecht entfernen ließen. Prüfen Sie im "
            "Slicer, ob die Decken ohne Stützen gedruckt werden können.",
            name=source_text(entry.name),
        ),
        values={
            "name": source_text(entry.name),
            "area_mm2": round(model.channel_area, 1),
        },
        location=model.channel_at,
        object_id=entry.id,
    )
    return blocker, [finding]


def prepare_slicer_meshes(
    chosen: Sequence[SceneObject],
    profile: Profile,
    setup: SlicerSetup,
    *,
    for_window: bool = False,
    cancelled: CancelToken | None = None,
) -> tuple[dict[str, MeshData], bool]:
    """Ein Exportnetzsatz für Vorprüfung, Platzierung und Schreiben."""
    from app.core.export import handover

    exported: dict[str, MeshData] = {}
    for entry in chosen:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        exported[entry.id] = mesh_for_export(entry.mesh, profile)
    if for_window or profile.printer.is_resin or setup.flavour == "other":
        return exported, False
    # Der bestehende Größenbeweis wird je Körper gefragt, bevor die Platte
    # gepackt wird. Seine Handlung gehört schon hier dem richtigen Objekt.
    for index, entry in enumerate(chosen):
        try:
            handover._check_plate([exported[entry.id]], profile, setup, cancelled)
        except ExternalToolError as problem:
            if problem.values.get("constraint") == "slicer_build_volume":
                problem.object_id = entry.id
                problem.values["part_index"] = index
            raise
    program = slicer_keys.program_of(setup.executable)
    if slicer_keys.arranges_on_cli(setup.flavour, program):
        return exported, False
    return _arrange_for_cli(chosen, exported, profile, setup, cancelled)


def _cli_turns(mesh: MeshData) -> Iterable[np.ndarray]:
    """Deterministische Z-Kandidaten: gültige Lage zuerst, dann Kanten und Raster."""
    import math
    from itertools import pairwise

    from shapely.geometry import MultiPoint

    from app.core.geom.orient import extreme_points

    yield np.eye(4)
    for degrees in (90.0, 180.0, 270.0):
        yield transform.rotation("z", degrees)
    hull = MultiPoint(extreme_points(mesh)[:, :2]).convex_hull
    if hull.geom_type == "Polygon":
        points = list(hull.exterior.coords)
        edges = sorted(
            (float(second[0] - first[0]), float(second[1] - first[1]))
            for first, second in pairwise(points)
        )
        for x, y in edges:
            length = math.hypot(x, y)
            if length <= EPS_GEOM:
                continue
            # Reine XY-Basis, ohne atan2 oder Plattformtrigonometrie; auch
            # bei Gegenrichtung bleibt Z aufrecht. hypotenuse: kern.md.
            turn = np.eye(4)
            turn[:2, :2] = ((x / length, y / length), (-y / length, x / length))
            for degrees in (0.0, 90.0, 180.0, 270.0):
                yield transform.composed(transform.rotation("z", degrees), turn)
    for degrees in range(0, 360, build_area.SIZE_ANGLE_STEP_DEGREES):
        yield transform.rotation("z", float(degrees))


def _fit_cli_mesh(
    mesh: MeshData, profile: Profile, cancelled: CancelToken | None
) -> MeshData | None:
    """Eine belegte Bettlage finden; die vollständige Kopie entsteht zuletzt."""
    from app.core.geom.orient import _Placed, extreme_points, turned_extents

    if build_area.fits_on_bed(mesh, profile.printer) and mesh.bounds.minimum[2] <= EPS_DISPLAY:
        return mesh
    points = extreme_points(mesh)
    for turn in _cli_turns(mesh):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        low, high = turned_extents(points, turn)
        bounds = BoundingBox(
            (float(low[0]), float(low[1]), float(low[2])),
            (float(high[0]), float(high[1]), float(high[2])),
        )
        placed = _Placed(mesh, turn, bounds)

        def outline(matrix: np.ndarray = turn) -> np.ndarray:
            return transform.moved_points(points, matrix)[:, :2]

        offset = build_area.placement_offset(placed, profile.printer, outline=outline)
        if offset is None:
            continue
        result = transform.apply(mesh, transform.composed(transform.translation(offset), turn))
        if build_area.fits_on_bed(result, profile.printer):
            return result
    return None


def _arrange_for_cli(
    chosen: Sequence[SceneObject],
    exported: dict[str, MeshData],
    profile: Profile,
    setup: SlicerSetup,
    cancelled: CancelToken | None,
) -> tuple[dict[str, MeshData], bool]:
    """Nur Ausgabenetze ihrer Platte bewegen; die Szene bleibt unverändert."""
    from app.core.export import handover

    arranged = dict(exported)
    changed = False
    for plate in sorted({entry.plate for entry in chosen}):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        entries = [entry for entry in chosen if entry.plate == plate]
        meshes = [exported[entry.id] for entry in entries]
        if arrangement_holds(meshes, profile):
            continue
        fitted = [_fit_cli_mesh(mesh, profile, cancelled) for mesh in meshes]
        ready = [mesh for mesh in fitted if mesh is not None]
        if len(ready) == len(meshes) and not arrangement_holds(ready, profile):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            ready = arrange_on_bed(
                ready, profile, plates=1, object_ids=[entry.id for entry in entries]
            ).meshes
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if len(ready) != len(meshes) or not arrangement_holds(ready, profile):
            raise ExternalToolError(
                tool=setup.name,
                title=handover.SLICER_FAILED,
                detail=_(
                    "Für diese Teile wurde keine Anordnung auf einer Druckplatte gefunden. "
                    "Sie können alle Teile des Projekts neu auf Platten anordnen "
                    "oder einen größeren Drucker wählen."
                ),
                values={
                    "constraint": "slicer_build_volume",
                    "plate": plate,
                    "object_ids": tuple(entry.id for entry in entries),
                },
                suggestions=(ARRANGE_ON_BED, CHOOSE_PRINTER, CANCEL),
            )
        arranged.update((entry.id, mesh) for entry, mesh in zip(entries, ready, strict=True))
        changed = True
    return arranged, changed


def write_assembly(
    objects: list[SceneObject],
    directory: Path,
    *,
    project_name: str,
    profile: Profile,
    plate: int | None = None,
    sources: dict[str, Source] | None = None,
    settings: PrintSettings | None = None,
    flavour: SlicerFlavour = "orca",
    place_on_bed: bool = False,
    setup: SlicerSetup | None = None,
    for_slicer: bool = True,
    scene: Scene | None = None,
    document: Document | None = None,
    checked: Sequence[Finding] | None = None,
    cancelled: CancelToken | None = None,
    for_window: bool = False,
    job: Sequence[SceneObject] | None = None,
    mesh_plan: tuple[dict[str, MeshData], bool] | None = None,
    before_write: Callable[[], None] | None = None,
    comparison: Callable[[Sequence[tuple[SceneObject, MeshData, PrintSettings | None]]], None]
    | None = None,
) -> tuple[Path, list[Finding]]:
    """Alles auf einer Platte in eine Baugruppendatei (§20, §29).

    ``cancelled`` erreicht Prüfung, Rat und Stützsperre für Kanäle
    (:func:`_support_blocker`); ein Abbruch wirft ``OperationCancelled``.

    Beim Dateiexport meldet ``before_write`` die Grenze nach der Vorbereitung:
    Erst dann sperrt der Aufrufer den Abbruch für das Schreiben der fertigen 3MF.

    Ein ausdrücklicher Dateiexport (`for_slicer=False`) bleibt 3MF.
    Bei direkter Übergabe erhält CuraEngine sein unterstütztes STL-Format,
    Curas Fenster (``for_window``) eine 3MF in seiner Schreibweise
    (:func:`_cura_window`).

    Der Unterschied zu :func:`write_plan` ist nicht das Format, sondern die
    Zahl der Dateien: ein Slicer, der eine Baugruppe bekommt, ordnet sie als
    Ganzes an und schreibt eine Druckdatei. Bekommt er fünf Dateien,
    entscheidet er über ihre Zusammengehörigkeit selbst — und was Solidon
    über die Platte weiß, ist verloren.

    ``plate`` schränkt auf eine Druckplatte ein; ohne Angabe geht alles hinein,
    was übergeben wurde.

    ``job`` nennt den ganzen Auftrag, wenn diese Datei nur einen Teil davon
    trägt — *Slicen* schreibt je Platte eine. Ob ein übernommener Vorschlag je
    Teil von keinem Teil verlangt wird (:func:`_unserved`), entscheidet dann
    der ganze Auftrag, nicht diese Platte. Ohne Angabe ist die Datei der
    Auftrag.

    ``place_on_bed`` legt die Teile in Bettkoordinaten — für die Übergabe an
    den Slicer, die sie mit ``--arrange 0`` auch durchsetzt. Beim Export einer
    Datei bleibt es aus, und zwar aus zwei Gründen: ein Slicer, den jemand von
    Hand öffnet, ordnet ohnehin neu an, und eine zurückgelesene Platte läge
    sonst um den halben Bauraum verschoben im nächsten Dokument.

    Und es gilt für jede Familie — ob, sagt :func:`needs_bed_translation`,
    und dort steht auch, warum Cura und PrusaSlicer die Teile lange
    unverschoben bekamen und was das auf der Maschine bedeutete
    (Gesamtreview 05.09.2026, CORE-17). Ein Würfel, den das Dokument bei
    -10 bis 10 hat, liegt im G-Code bei 118 bis 138: Das ist die Bettmitte
    eines Druckers, der von der Ecke misst, und die Bettform, die die
    Übergabe daneben schreibt, sagt dasselbe.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # §2 C: auch die Baugruppe ist ein Export — dieselbe Grenze wie write_plan.
    activation.require(activation.EXPORT)
    chosen = objects if plate is None else [entry for entry in objects if entry.plate == plate]
    if not chosen:
        raise ValidationError(
            field="objects",
            detail=_("Auf dieser Platte liegt nichts."),
            values={"plate": plate},
            constraint="empty",
        )

    # Diese Funktion schreibt immer 3MF — das steht in ihrem Namen und in
    # ihrem Docstring, also gibt es hier nichts zu wählen.
    findings = (
        list(checked)
        if checked is not None
        else check_before_export(
            chosen,
            profile,
            sources or {},
            "3mf",
            scene=scene,
            document=document,
            cancelled=cancelled,
        )
    )
    if profile.printer.is_resin:
        # Ein Resin-Slicer liest keine FDM-Werte, und die Befunde dazu —
        # Haftungsränder, Filamentwechsel, ein Brim je Teil — haben dort
        # keinen Gegenstand. Die Datei geht als reine Geometrie hinaus
        # (Resin-Konzept §4, B4).
        settings = None
    if settings is not None:
        from app.core.export import handover

        settings = handover.bind_object_profiles(settings, objects if job is None else job)
    # Einmal je Körper vernetzt, für Prüfung, STL und 3MF dieselben Dreiecke
    # — ein exakter Körper so fein, wie der Drucker es braucht.
    if mesh_plan is None:
        if for_slicer:
            from app.core.export import handover

            known = setup if setup is not None else handover.SlicerSetup(Path(flavour), flavour)
            mesh_plan = prepare_slicer_meshes(
                chosen, profile, known, for_window=for_window, cancelled=cancelled
            )
        else:
            mesh_plan = (
                {entry.id: mesh_for_export(entry.mesh, profile) for entry in chosen},
                False,
            )
    exported, arranged_for_cli = mesh_plan
    program = slicer_keys.program_of(setup.executable) if setup is not None else ""
    if (
        for_slicer
        and not for_window
        and not profile.printer.is_resin
        and flavour != "other"
        and not slicer_keys.arranges_on_cli(flavour, program)
    ):
        place_on_bed = True
    if arranged_for_cli:
        # Nur die überholte Platzierungsprüfung wird durch den neuen Stand ersetzt.
        replaced_codes = {
            "arrange.narrow_margin",
            "arrange.off_the_plate",
            "arrange.out_of_build_volume",
            "arrange.above_bed",
            "arrange.below_bed",
            "arrange.needs_more_plates",
            "arrange.collision",
        }
        findings = [finding for finding in findings if finding.code not in replaced_codes]
        findings.extend(
            check_build_volume(
                [exported[entry.id] for entry in chosen],
                profile,
                [entry.plate for entry in chosen],
                [entry.id for entry in chosen],
                about_to_write=True,
            )
        )
        findings.append(
            Finding(
                code="export.arranged_for_slicer",
                severity="info",
                message=_("Die Teile wurden für diesen Slicer auf der Druckplatte angeordnet."),
            )
        )
    findings += _tessellation_finding(chosen, profile)
    split: PartSplit | None = None
    # Was der Kunde übernommen hat, bevor der Split die Platte zurücksetzt —
    # daran misst :func:`_unserved`, was sonst verloren ginge.
    accepted = settings
    slot_profiles: dict[threemf.SlotKey, str] = {}
    if settings is not None:
        from app.core.export import handover

        # **Was nur einzelne Teile brauchen, steht an ihnen** (Konzept
        # Herstellerprofil, Entscheidung G): Die Platte bekommt dort die
        # Grundlage, bei Cura die Übernahme mit Rücknahme je Netz.
        split = handover.split_for_parts(settings, profile, setup, flavour)
        settings = split.plate
        slot_profiles = handover.chosen_slot_profiles(objects, settings)
    # Einmal je Körper gerechnet: Der Schnitt knapp über dem Boden kostet, und
    # die Schlüssel wie der Grund kommen aus demselben Aufruf. Auch was der
    # Slicer je Teil nicht annimmt, wird benannt.
    part_values = {
        entry.id: _part_values(
            entry,
            exported[entry.id],
            split,
            profile,
            flavour,
            setup,
            slot_profiles,
            document,
            cancelled,
        )
        for entry in chosen
    }
    asked = {key: values.asked for key, values in part_values.items()}
    # **Was kein Teil für sich verlangt, gilt allen** (:func:`_unserved`) —
    # als Objektwert an jedem Teil, und der Bericht sagt es. „Kein Teil" heißt
    # keines des ganzen Auftrags: Verlangt es ein Teil auf einer anderen
    # Platte, bleibt es auf dieser still (:func:`_served_elsewhere`).
    everywhere = _unserved(split, accepted, part_values.values())
    if split is not None and everywhere and job is not None:
        from app.core.export import handover

        here = {entry.id for entry in chosen}
        served = _served_elsewhere(
            [entry for entry in job if entry.id not in here],
            frozenset(item.path for item in everywhere),
            split,
            profile,
            flavour,
            setup,
            handover.chosen_slot_profiles(job, split.plate),
            document,
            cancelled,
        )
        everywhere = [item for item in everywhere if item.path not in served]
    if split is not None and everywhere:
        part_values = {
            key: _values_for(
                split,
                values.applied,
                values.unavailable,
                flavour,
                everywhere,
                program=slicer_keys.program_of(setup.executable) if setup is not None else "",
                profile=profile,
            )
            for key, values in part_values.items()
        }
        findings += [
            Finding(
                code="export.part_setting_all",
                severity="info",
                message=_(
                    "Gilt für alle Teile: Beim Export brauchte kein Teil diesen übernommenen "
                    "Vorschlag für sich allein."
                ),
                values={"setting": item.path, "value": _finding_value(item.value)},
            )
            for item in everywhere
        ]
    # Die Gegenprobe liest genau diese Vernetzung und diese endgültigen
    # Teilwerte, einschließlich der auf alle Teile verteilten Empfehlungen.
    # Der Aufrufer arbeitet bereits neben Qt; kein zweiter Empfehlungsdurchgang.
    if comparison is not None:
        comparison(
            tuple((entry, exported[entry.id], part_values[entry.id].effective) for entry in chosen)
        )
    # Die Sperre nennt sich selbst, mit dem Namen des Teils
    # (``export.support_blocker``); ein zweiter Satz dazu wäre derselbe.
    findings += _part_setting_findings(
        [
            (entry.id, advice)
            for entry in chosen
            for advice in part_values[entry.id].applied
            if advice.path != "support.block_channels"
        ]
    )
    findings += _part_setting_findings(
        [(entry.id, advice) for entry in chosen for advice in part_values[entry.id].unavailable],
        applied=False,
    )
    findings += _plate_wide_findings(chosen, asked, split)
    if settings is not None:
        # Was erst auf der Platte auffiele: Haftungsränder, die ineinander
        # laufen, und der Preis zweier Filamente in einem Auftrag — je Teil mit
        # der Haftung, die es wirklich bekommt.
        meshes = [exported[entry.id] for entry in chosen]
        own = [part_values[entry.id].effective or settings for entry in chosen]
        from app.core.export import handover

        findings += handover.setting_limitations(flavour, settings)
        # Vor der Trennung gefragt, damit auch ein Wert je Teil zählt (RM-480).
        findings += handover.substituted_choices(
            accepted or settings,
            slicer_keys.program_of(setup.executable) if setup is not None else "",
        )
        findings += check_adhesion_clearance(
            meshes, settings, [entry.plate for entry in chosen], per_part=own
        )
        findings += check_adhesion_on_bed(
            meshes, settings, profile, [entry.id for entry in chosen], per_part=own
        )
        findings += check_filament_changes(chosen, settings, plate)
    width, depth, _height = profile.printer.build_volume
    # Solidons Bettmitte in den Koordinaten der Maschine — nicht immer das
    # halbe Bett: Am Dremel 3D45 und an jedem Delta liegt der Nullpunkt
    # woanders (``build_area.machine_shift``, RM-424).
    bed_centre = (
        build_area.machine_shift(profile.printer)
        if place_on_bed and needs_bed_translation(flavour)
        else None
    )

    as_stl = for_slicer and not reads_assembly_file(flavour)

    if as_stl:
        if settings is not None or (for_window and takes_mesh_settings(flavour)):
            from app.core.export import handover

        if settings is not None:
            slots = threemf.merge_slots(
                [
                    threemf.AssemblyPart(
                        as_mesh_data(entry.mesh), slots=threemf.slots_for_object(entry)
                    )
                    for entry in chosen
                ]
            )
            configured = handover.configured_slots(slots, settings)
            known = setup if setup is not None else handover.SlicerSetup(Path(flavour), flavour)
            findings += handover.unreachable_overrides(settings, known, configured, profile=profile)
            if setup is not None:
                findings += handover.cura_acceleration_findings(
                    settings,
                    profile,
                    setup,
                    {entry.id: part_values[entry.id].keys for entry in chosen},
                    for_window=for_window,
                )
        if for_window and takes_mesh_settings(flavour):
            if setup is not None and setup.flavour == "cura":
                mismatch = handover.cura_active_printer_mismatch(
                    setup,
                    profile,
                    solidon_settings_included=settings is not None,
                )
                if mismatch is not None:
                    findings.append(mismatch)
            target, noted = _cura_window(
                chosen,
                exported,
                directory / (given_name(project_name, "projekt") + ".3mf"),
                project_name,
                part_values,
                profile,
                setup,
                cancelled,
            )
            return target, findings + noted
        target = _written(
            directory / (given_name(project_name, "projekt") + ".stl"),
            _cura_assembly([exported[entry.id] for entry in chosen], bed_centre),
        )
        if takes_mesh_settings(flavour):
            findings += _cura_meshes(
                chosen, exported, target, part_values, profile, bed_centre, cancelled
            )
        _log.info("exported %d object(s) as one STL to %s", len(chosen), target.name)
        return target, findings

    # **Die Stützsperre nur für die direkte Übergabe.** Eine gespeicherte 3MF
    # liest auch Solidon selbst wieder, und sein Leser nähme den Bereich als
    # Material des Körpers (``ingest.foreign_volume``). Nur, wenn gestützt
    # wird — ohne Stützen gibt es nichts zu sperren —, und nur, wenn der
    # Vorschlag übernommen ist (``support.block_channels``): Ohne ihn gehen die
    # Standardeinstellungen hinaus (Entscheidung Robert, 26.09.2026).
    # Je Teil mit dessen Einstellungen: Stützt nur ein Teil, sperrt auch nur
    # dieses seine Kanäle (Entscheidung G).
    blockers: dict[str, MeshData | None] = {}
    if for_slicer:
        for entry in chosen:
            own_settings = part_values[entry.id].effective
            if (
                own_settings is None
                or own_settings.support.style == "none"
                or not own_settings.support.block_channels
            ):
                continue
            blockers[entry.id], noted = _support_blocker(
                entry, exported[entry.id], own_settings, profile, cancelled
            )
            findings += noted
    parts = [
        threemf.AssemblyPart(
            mesh=exported[entry.id],
            name=source_text(entry.name),
            slots=threemf.slots_for_object(entry),
            settings=part_values[entry.id].keys,
            support_blocker=blockers.get(entry.id),
            # Die Platte reist mit. Ohne Einschränkung auf eine gehen alle in
            # dieselbe Datei — und dann muss dort stehen, welches Teil auf
            # welche gehört, sonst legt der Slicer sie übereinander.
            plate=entry.plate - min(other.plate for other in chosen),
        )
        for entry in chosen
    ]
    # **Die Extruderbelegung gehört dem Auftrag, nicht der Platte.** Ohne diese
    # Liste nummeriert jede Platte für sich, und dieselbe Farbe liegt auf
    # Platte 1 an einer anderen Düse als auf Platte 2 — Umstecken mitten im
    # Auftrag (Fund von 3d-druck-de, 26.08.2026). Gebaut wird sie aus
    # ``objects`` und nicht aus ``chosen``: Letzteres *ist* die Platte.
    whole_job = [
        threemf.AssemblyPart(
            mesh=as_mesh_data(entry.mesh),
            name=source_text(entry.name),
            slots=threemf.slots_for_object(entry),
        )
        for entry in objects
    ]
    merged_slots = threemf.merge_slots(parts, across=whole_job)
    configured_slots: Sequence[MaterialSlot] = merged_slots
    if settings is not None:
        from app.core.export import handover

        configured_slots = handover.configured_slots(merged_slots, settings)
        known_setup = setup if setup is not None else handover.SlicerSetup(Path(flavour), flavour)
        findings += handover.unreachable_overrides(
            settings, known_setup, configured_slots, profile=profile
        )
        if setup is not None:
            # **Nur mit echtem Slicer.** ``known_setup`` oben ist ein Platzhalter
            # aus dem Familiennamen; ihn nach seiner eingestellten Maschine zu
            # fragen hieße, jemandem etwas über einen Slicer zu sagen, den er
            # gerade nicht benutzt. Wer bloß eine 3MF speichert, will von der
            # Einstellung eines fremden Programms nichts hören.
            findings += handover.machine_missing(setup, profile)
            if settings is not None:
                findings += handover.foundation_findings(
                    settings, profile, setup, slots=configured_slots
                )
    payload = threemf.write_assembly(
        parts,
        project_name,
        across=whole_job,
        bed_centre=bed_centre,
        project_settings=_plate_settings(
            settings,
            profile,
            flavour,
            setup,
            configured_slots,
        ),
        prusa_config=_plate_config(
            settings,
            profile,
            flavour,
            configured_slots,
            setup,
        ),
        # Das Bettmaß, an dem die Platten ins Raster rücken — nur wo es
        # mehrere gibt. Ein Versatz auf einer einzelnen wäre eine
        # Verschiebung ohne Grund, und die Datei trüge eine Matrix, die
        # nichts sagt.
        layout=(width, depth) if len({p.plate for p in parts}) > 1 else None,
        blocker_as_part=helpers_as_parts(flavour),
    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if before_write is not None:
        before_write()
    target = _written(directory / (given_name(project_name, "projekt") + ".3mf"), payload)
    _log.info("exported %d object(s) as one assembly to %s", len(parts), target.name)
    if for_window and setup is not None:
        from app.core.export import handover

        findings += handover.window_findings(setup)
    return target, findings


def _plate_settings(
    settings: PrintSettings | None,
    profile: Profile,
    flavour: SlicerFlavour,
    setup: SlicerSetup | None,
    slots: Sequence[MaterialSlot] = (),
) -> dict[str, object]:
    """Die Druckeinstellungen, die mit der Datei reisen (§29).

    Ohne sie ist eine exportierte 3MF nur Geometrie, und der Slicer öffnet sie
    mit dem Profil, das gerade eingestellt ist. Mit ihnen trägt die Datei
    Temperatur, Tempo und Kühlung selbst — der Unterschied zwischen einer
    Datei, die man druckt, und einer, die man erst einrichtet.

    Ist kein Slicer bekannt, werden trotzdem Solidons Werte geschrieben, nur
    ohne das Systemprofil darunter: die Maschine kennt Solidon aus dem eigenen
    Profil, und ein Wert, der dasteht, ist mehr als einer, der fehlt.
    """
    if settings is None:
        return {}
    from app.core.export import handover

    known = setup if setup is not None else handover.SlicerSetup(Path(flavour), flavour)
    return handover.project_settings(settings, profile, known, slots=slots)


def _plate_config(
    settings: PrintSettings | None,
    profile: Profile,
    flavour: SlicerFlavour,
    slots: Sequence[MaterialSlot] = (),
    setup: SlicerSetup | None = None,
) -> dict[str, str]:
    """Dasselbe für PrusaSlicer, der es als Textzeilen führt (§29).

    Die Orca-Familie liest ihre Einstellungen aus einer JSON-Beilage, Prusa
    aus ``Metadata/Slic3r_PE.config`` — dieselbe Sache, ein anderes Format.
    Solange nur die eine geschrieben wurde, trug eine exportierte 3MF für
    PrusaSlicer bloß Geometrie: geöffnet wurde sie mit dem Profil, das gerade
    eingestellt war, und was Solidon über das Teil weiß, war weg.

    Gemessen, nicht vermutet: eine 3MF mit dieser Beilage, ohne ``--load``
    geslict, ergab sieben Wände und 15 Prozent Füllung — Solidons Werte.

    Seit Stufe C des Konzepts Herstellerprofil trägt sie dieselbe Kette wie
    der Konsolenlauf (:func:`handover.prusa_values`), mit den Namen der drei
    Profile: Das Fenster wählt dann das installierte Profil und zeigt nur
    Solidons Abweichung als „geändert". Das binäre Format des Herstellers
    bleibt — das Fenster schreibt die Druckdatei, nicht Solidon.
    """
    if settings is None or flavour != "prusa":
        return {}
    from app.core.export import handover

    values, _expected = handover.prusa_values(settings, profile, setup, slots, console=False)
    return values


def _cura_meshes(
    chosen: Sequence[SceneObject],
    exported: dict[str, MeshData],
    target: Path,
    part_values: Mapping[str, _PartValues],
    profile: Profile,
    bed_centre: tuple[float, float] | None,
    cancelled: CancelToken | None,
) -> list[Finding]:
    """Für CuraEngine je Teil ein Netz und jede Stützsperre als eigenes (§29).

    Bis zum 27.09.2026 bekam Cura alle Teile als ein STL, und die Sperre fiel
    dabei weg (``NOT_TAKEN_BY``). Als eigenes Netz mit ``anti_overhang_mesh``
    wirkt sie — gemessen im Prüfbericht Cura (Abschnitt 1.5): 18 476 Stützbewegungen
    wurden 0, die Modellbahn blieb gleich. Die Netze und ihre Liste
    (``handover.write_cura_meshes``) liest die Kommandozeile; Curas Fenster
    bekommt dieselben Netze mit denselben Werten als 3MF (:func:`_cura_window`).

    **Je Netz, was nur diesem Teil gilt** (Entscheidung G): Die Platte trägt
    die Übernahme, ein Teil, das sie nicht braucht, bekommt die Grundlage
    zurück (:class:`handover.PartSplit`, ``revert``) — so stützt Cura nur das
    Teil, das es braucht, und sperrt nur dessen Kanäle.
    """
    from app.core.export import handover

    blockers, findings = _cura_blockers(chosen, exported, part_values, profile, cancelled)
    meshes: list[handover.CuraMesh] = []
    for number, entry in enumerate(chosen, start=1):
        part = _written(
            target.with_name(f"{target.stem}-part-{number}.stl"),
            _cura_assembly([exported[entry.id]], bed_centre),
        )
        meshes.append(handover.CuraMesh(part, part_values[entry.id].keys))
        blocker = blockers.get(entry.id)
        if blocker is not None:
            barrier = _written(
                target.with_name(f"{target.stem}-blocker-{number}.stl"),
                _cura_assembly([blocker], bed_centre),
            )
            meshes.append(handover.CuraMesh(barrier, {CURA_SUPPORT_BLOCKER: "true"}))
    handover.write_cura_meshes(target, meshes)
    return findings


def _cura_blockers(
    chosen: Sequence[SceneObject],
    exported: Mapping[str, MeshData],
    part_values: Mapping[str, _PartValues],
    profile: Profile,
    cancelled: CancelToken | None,
) -> tuple[dict[str, MeshData | None], list[Finding]]:
    """Die Stützsperre je Teil, das gestützt wird und die Sperre übernommen
    hat — mit dessen eigenen Einstellungen (Entscheidung G), für die
    Kommandozeile und das Fenster dieselbe."""
    findings: list[Finding] = []
    blockers: dict[str, MeshData | None] = {}
    for entry in chosen:
        own = part_values[entry.id].effective
        if own is None or own.support.style == "none" or not own.support.block_channels:
            continue
        blockers[entry.id], noted = _support_blocker(
            entry, exported[entry.id], own, profile, cancelled
        )
        findings += noted
    return blockers, findings


def _cura_window(
    chosen: Sequence[SceneObject],
    exported: Mapping[str, MeshData],
    target: Path,
    project_name: str,
    part_values: Mapping[str, _PartValues],
    profile: Profile,
    setup: SlicerSetup | None,
    cancelled: CancelToken | None,
) -> tuple[Path, list[Finding]]:
    """Was Curas Fenster öffnet: dieselben Netze mit denselben Werten wie die
    Kommandozeile (:func:`_cura_meshes`), als 3MF in Curas Schreibweise (RM-257).

    Das Fenster bekam bis dahin das zusammengelegte STL: ohne Stützsperre, und
    ohne die Werte je Teil — die Übernahme der Platte stützte dort jedes Teil.
    Eine 3MF liest es mit Werten je Objekt (``cura:``-Metadaten,
    :func:`threemf.write_assembly`), die Sperre als Komponente neben ihrem
    Körper, damit sie beim Anordnen mitwandert.

    **Mittig auf dem Bett der Maschine, die in Cura aktiv ist**: Cura ordnet
    eine 3MF beim Laden nicht an und zieht die halbe Bettgröße *dieser*
    Maschine ab; Solidon rechnet um die Bettmitte. Mit dem Bett des Druckers
    in Solidon lag ein Auftrag an einer anderen Maschine um die halbe
    Differenz daneben (B5, Durchsicht 0.5.1). Dieselbe Maschine bekommt auch
    das Profil daneben (:func:`handover.cura_profile_beside`); ist keine
    bekannt, gilt das Bett des Druckers.
    """
    from app.core.export import handover, slicer_profiles

    blockers, findings = _cura_blockers(chosen, exported, part_values, profile, cancelled)
    width, depth, _height = profile.printer.build_volume
    active = slicer_profiles.cura_active_machine(setup.executable) if setup is not None else None
    bed = active.bed if active is not None and active.bed is not None else (width, depth)
    motion = (
        handover.cura_window_motion(setup, profile)
        if setup is not None and any(part.keys for part in part_values.values())
        else {}
    )
    parts = [
        threemf.AssemblyPart(
            mesh=exported[entry.id],
            name=source_text(entry.name),
            slots=threemf.slots_for_object(entry),
            settings=handover.for_the_cura_window(part_values[entry.id].keys, machine=motion),
            support_blocker=blockers.get(entry.id),
        )
        for entry in chosen
    ]
    # Curas Leser zieht beim Öffnen das halbe Bett ab, gleich wo die Maschine
    # ihren Nullpunkt hat (``ThreeMFReader.py``): Die 3MF misst von der Ecke.
    centre = (bed[0] / 2.0, bed[1] / 2.0)
    written = _written(
        target, threemf.write_assembly(parts, project_name, bed_centre=centre, cura=True)
    )
    _log.info("exported %d object(s) as a 3MF for Cura's window to %s", len(chosen), target.name)
    return written, findings


def _cura_assembly(meshes: Sequence[MeshData], bed_centre: tuple[float, float] | None) -> bytes:
    """Dieselbe Platte als ein STL — der einzige Weg zu ``CuraEngine``.

    Die 3MF-Seite von Cura sitzt in seiner Oberfläche, nicht in der Maschine
    dahinter: ``CuraEngine`` liest STL und OBJ, und eine 3MF-Baugruppe lehnt es
    mit einer Meldung ab, die den Dateinamen nennt und sonst nichts. Jeder
    Slicen-Lauf mit Cura endete deshalb in „Der Slicer hat keine Druckdatei
    geschrieben".

    Ein STL kennt keine Baugruppe, also werden die Körper zu einem
    zusammengelegt. Verloren geht dabei nichts, was auf diesem Weg ankäme:
    Namen und Materialslots liest ``CuraEngine`` ohnehin nicht, und die
    Einstellungen kommen bei ihm über die Kommandozeile.

    ``bed_centre`` ist Solidons Bettmitte in Maschinenkoordinaten, wenn die
    Teile darin gehen (:func:`needs_bed_translation`): Verschoben wird über
    die Punkte, denn ein STL hat keine Platzierungsmatrix. Der aktuelle
    Cura-Weg übergibt jedoch ``None``, weil CuraEngine die mittig gelieferten
    Teile selbst auf dem Bett platziert (``machine_center_is_zero``,
    ``mesh_position_*`` aus ``handover._machine_keys``);
    ``needs_bed_translation("cura")`` ist daher falsch.
    """
    bodies = []
    for entry in meshes:
        body = entry.raw.copy()
        if bed_centre is not None:
            body.apply_translation((bed_centre[0], bed_centre[1], 0.0))
        bodies.append(body)
    joined = concatenated(bodies) if len(bodies) > 1 else bodies[0]
    return MeshData.of(joined).to_stl()


def export_bytes(
    mesh: MeshData,
    export_format: ExportFormat = "stl",
    slots: list[MaterialSlot] | None = None,
    name: str = "",
    body: Mesh | None = None,
) -> bytes:
    """Ein Körper in einem Format.

    3MF wird hier geschrieben statt von trimesh: es ist das eine Format, das
    die Materialgruppen aus §20 trägt, und trimesh schreibt sie nicht. STEP
    wird aus dem exakten Körper geschrieben und gibt es nur, wenn es einen
    gibt (§30).
    """
    if export_format == "step":
        return _step_bytes(body, name, slots)
    if export_format == "stl":
        return mesh.to_stl()
    if export_format == "3mf":
        return threemf.write(mesh, slots, name)
    if export_format == "glb":
        return _glb_bytes(mesh, slots, name)
    data = trimesh.exchange.export.export_mesh(mesh.raw, None, file_type=export_format)
    return data if isinstance(data, bytes) else str(data).encode("utf-8")


#: glTF rechnet in Metern (Spezifikation 2.0, Abschnitt 3.4), Solidon in
#: Millimetern — der Faktor beim Schreiben eines GLB.
GLB_METRES_PER_MM: Final = 0.001


def _glb_bytes(mesh: MeshData, slots: list[MaterialSlot] | None, name: str = "") -> bytes:
    """GLB mit Namen und Farben — die Datei zum Herzeigen.

    Zwei Dinge macht sie besser als ein OBJ derselben Dreiecke, und beide sind
    der Grund, warum es dieses Format hier gibt. Der Name reist mit, sonst
    heißt das Teil im Betrachter des Empfängers ``geometry_0``. Und die
    Materialslots werden zu Dreiecksfarben: ein zweifarbiges Schild, das grau
    ankommt, zeigt genau das nicht, wofür man es verschickt hat.

    Der Rest bleibt bewusst schlicht — keine Texturen, kein PBR-Feinwerk. Was
    hier hinausgeht, ist eine Vorschau, kein Renderauftrag.

    Zweifarbig wird **je Slot ein eigenes Teilnetz**, und das ist kein Umweg:
    glTF kennt Farben nur an Ecken, nicht an Dreiecken. Zwei benachbarte
    Dreiecke teilen sich ihre Ecken, und eine scharfe Grenze zwischen roter
    Grundplatte und blauer Schrift kam damit als Farbverlauf über das halbe
    Teil an. Getrennte Netze haben getrennte Ecken — und nebenbei heißen sie
    im Betrachter so, wie die Slots im Dokument heißen.

    **Gedreht wird beim Schreiben, und zwar hier.** Der glTF-2.0-Standard legt
    in seinem Abschnitt 3.5 (nicht dem des Bauplans) +Y als oben fest, Solidon
    rechnet Z-oben, und ``trimesh`` dreht nichts: Gemessen
    an einem Quader 10 auf 20 auf 40 standen die Punktgrenzen der Datei bei
    ``[-5, -10, -20] … [5, 10, 20]``, ohne Knotenmatrix daneben. Beim Empfänger
    — Windows-3D-Viewer, three.js, Blender — lag das Teil damit auf dem Rücken,
    und genau dorthin geht dieses Format.

    ``read_mesh`` liest weiterhin rohe Achsen und Einheiten. Beim erneuten
    Import übernimmt ``load`` mit ``coordinates="gltf"`` die Gegenrichtung
    und mit ``unit="m"`` die Millimeterumrechnung. Migrierte Projekte und
    Generatorquellen behalten ihren ausdrücklich gespeicherten Rohweg.
    """
    stem = safe_name(name, "teil")
    parts = _parts_by_slot(mesh, slots)
    if parts is None:
        bodies = {stem: mesh.raw.copy()}
    else:
        # Der Schlüssel ist ein Name im Betrachter, die Slotnummer ist die
        # Identität: Zwei Slots, deren Anzeigenamen gleich sind oder nach der
        # Bereinigung zusammenfallen (``A/B`` und ``AB``), ersetzten sich hier
        # — sechs statt zwölf Dreiecke, eine ganze Farbregion fehlte
        # (Gesamtreview 05.09.2026, CORE-19). Der zweite bekommt seine Nummer
        # angehängt, das Netz bleibt vollständig.
        bodies = {}
        for index, (label, part) in parts:
            key = f"{stem}_{safe_name(label, f'slot{index}')}"
            while key in bodies:
                key = f"{key}_{index}"
            bodies[key] = part
    # Alle Teilnetze mit derselben Matrix, sonst steckt eines quer im anderen.
    # Kopien sind es ohnehin — ``copy()`` oben, ``submesh`` in _parts_by_slot.
    #
    # **Und in Metern.** glTF 2.0 legt die Einheit fest (Abschnitt 3.4): Eine
    # Koordinate ist ein Meter. Bis zum 05.09.2026 gingen die Millimeter
    # unverändert hinaus — ein Quader 10 x 20 x 40 mm kam als 10 x 40 x 20 m
    # an, und nur ein Betrachter mit automatischem Einpassen verbarg das
    # (Gesamtreview, CORE-33). Beim neuen Import übernimmt die load-Operation
    # die gespeicherte Einheit; der Rohleser skaliert selbst weiterhin nicht.
    upright = trimesh.transformations.rotation_matrix(-np.pi / 2.0, (1.0, 0.0, 0.0))
    for body in bodies.values():
        transform.moved(body, upright)
        body.apply_scale(GLB_METRES_PER_MM)
    scene = trimesh.Scene(bodies)  # type: ignore[arg-type]
    data = scene.export(file_type="glb")
    return data if isinstance(data, bytes) else str(data).encode("utf-8")


def _parts_by_slot(
    mesh: MeshData, slots: list[MaterialSlot] | None
) -> list[tuple[int, tuple[str, trimesh.Trimesh]]] | None:
    """Ein eingefärbtes Teilnetz je benutztem Materialslot, oder ``None``.

    ``None`` heißt: hier ist nichts zu trennen — ein einfarbiges Teil bleibt
    ein Netz und bekommt keine erfundene Farbe, sondern die Vorgabe des
    Betrachters.
    """
    known = {entry.index: entry for entry in (slots or []) if entry.colour is not None}
    if not known or not mesh.slots:
        return None
    picked = np.asarray(mesh.slots)
    used = [index for index in dict.fromkeys(picked.tolist()) if index in known]
    if len(used) < 2:
        return None

    parts = []
    for index in used:
        faces = np.flatnonzero(picked == index)
        # ``append=True`` gibt genau ein Netz zurück, keine Liste.
        part: trimesh.Trimesh = mesh.raw.submesh([faces], append=True)  # type: ignore[assignment]
        colour = known[index].colour or (0.0, 0.0, 0.0)
        part.visual = trimesh.visual.ColorVisuals(
            mesh=part,
            face_colors=np.tile(
                [*(round(channel * 255.0) for channel in colour), 255], (len(faces), 1)
            ).astype(np.uint8),
        )
        # ``str``, weil der Name in die GLB reist: Ein Slotname darf ein
        # ``TranslatableText`` sein, und dort steht Text, den ein fremdes
        # Programm liest.
        parts.append((index, (str(known[index].name), part)))
    return parts


def _step_bytes(
    body: Mesh | None, name: str = "", slots: Sequence[MaterialSlot] | None = None
) -> bytes:
    """STEP eines exakten Körpers — und ein klares Nein, wenn es keinen
    gibt (§30).

    Der Name reist mit: ohne ihn hieß das Teil in Fusion „Körper1", während
    er im Dokument die ganze Zeit dastand. **Und die Filamentfarben reisen
    mit** (P7.4): Jede Fläche trägt die Farbe ihres Slots, so wie sie beim
    Einlesen einer STEP-Baugruppe aus der Datei kam — die Rundreise gibt
    dieselben Farben zurück. Ein Slot ohne Farbe schreibt keine.
    """
    from app.core.brep import step as brep_step
    from app.core.brep.kernel import Solid as ExactSolid

    if body is None or not isinstance(body, BRepBody) or not isinstance(body, ExactSolid):
        raise _needs_solid()
    return brep_step.write(body, name, _face_colours(body, slots or ()))


def _face_colours(body: Solid, slots: Sequence[MaterialSlot]) -> tuple[str | None, ...]:
    """``#rrggbb`` je Fläche eines exakten Körpers aus seinen Filamentslots."""
    from app.core.brep.step import hex_colour

    colours = {slot.index: slot.colour for slot in slots if slot.colour is not None}
    if not colours:
        return ()
    face_slots = body.face_slots or (0,) * body.face_count
    return tuple(hex_colour(*colours[slot]) if slot in colours else None for slot in face_slots)


def _needs_solid() -> NeedsSolidError:
    """Der Satz für „dieses Format braucht einen exakten Körper" — einmal.

    Kein ``ValidationError``: dessen Titel lautet „Ein Wert liegt außerhalb des
    zulässigen Bereichs", und im Dialog stand er über der richtigen Erklärung —
    hier ist kein Wert außerhalb eines Bereichs, hier hat der Körper die
    falsche Art. Denselben Weg ist ``NeedsSolidError`` schon einmal gegangen
    (siehe dort).

    Zwei Stellen werfen ihn: der Schreiber eines einzelnen Körpers und der
    Plan, aus dem am Ende keine einzige Datei übrig blieb. Zwei Fassungen
    desselben Satzes wären zwei Einträge im Katalog und einer davon veraltet.

    **Und der Ausweg ist ein Knopf, nicht nur ein Satz.** Derselbe Fall
    erreicht den Kunden auf zwei Wegen: als Befund im Prüfbericht und als
    geworfener Fehler, wenn er ``teil.step`` tippt. Der Befund bot *Als 3MF
    speichern* an, die Ausnahme nur *Abbrechen* — gemessen am 03.09.2026
    ``['cancel']`` gegen ``['export_as_mesh', 'show_details']``. Formal
    genügte das Regel 17; praktisch endete der häufigere der beiden Wege mit
    „geht nicht, brich ab", während die Handlung dazu im Fenster fertig lag
    (``_export_as_mesh_after_error`` trägt den Fall im Namen).

    Seit P4.0 führen zwei Wege weiter: der zum Körper — *In Flächen und
    Kanten umwandeln*, danach trägt STEP — und der zu einer Datei, die
    Dreiecke kennt.
    """
    return NeedsSolidError(
        detail=_(
            "STEP speichert echte Flächen und Kanten, dieses Modell besteht aus festen "
            "Dreiecken. „In Flächen und Kanten umwandeln“ macht sie daraus; STL und 3MF "
            "nehmen es, wie es ist."
        ),
        values={"field": "format", "constraint": "needs_brep"},
        suggestions=(CONVERT_TO_EXACT, EXPORT_AS_MESH, CANCEL),
    )
