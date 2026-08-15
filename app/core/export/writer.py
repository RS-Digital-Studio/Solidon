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
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import trimesh

from app.core import activation
from app.core.errors import NeedsSolidError, ValidationError
from app.core.export import threemf
from app.core.export.slicer_keys import SlicerFlavour, wants_bed_coordinates
from app.core.geom.mesh import MeshData, as_mesh_data, concatenated
from app.core.geom.prepare import check_build_volume
from app.core.log import get_logger
from app.core.types import (
    BoundingBox,
    BRepBody,
    Finding,
    MaterialSlot,
    Mesh,
    PrintSettings,
    Profile,
    SceneObject,
    Source,
)
from app.core.units import EPS_GEOM, format_length
from app.i18n import _, tr

if TYPE_CHECKING:
    # Nur für die Signatur: zur Laufzeit zieht ``handover`` die
    # G-Code-Auswertung mit, und ein Export soll nicht davon abhängen, dass
    # ein Slicer im Spiel ist.
    from app.core.export.handover import SlicerSetup

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

_UNSAFE = re.compile(r"[^\w\-. ]+", re.UNICODE)

#: Höhe über dem Boden, in der die Standfläche eines Teils gemessen wird. Nicht
#: bei null: dort liegt die Grundfläche selbst, und ein Schnitt genau in einer
#: Fläche liefert je nach Netz alles oder nichts.
FOOTPRINT_HEIGHT = 0.2


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
    """The object as it is in the scene. STEP needs the exact body, not the
    triangles it was tessellated into (§30)."""
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
) -> ExportPlan:
    """Ermittelt die Dateinamen und führt die Prüfung vor dem Export aus."""
    if not objects:
        raise ValidationError(
            field="objects",
            detail=_("Es ist nichts zum Exportieren ausgewählt."),
            constraint="empty",
        )

    count = len(objects)
    plates = len({entry.plate for entry in objects})
    if scheme is not None:
        pattern = scheme
    elif plates > 1:
        pattern = PLATE_SCHEME
    else:
        pattern = DEFAULT_SCHEME if count > 1 else SINGLE_SCHEME
    suffix = FORMAT_SUFFIX[export_format]

    entries = tuple(
        ExportEntry(
            object_id=entry.id,
            filename=safe_name(
                pattern.format(
                    project=safe_name(project_name, "projekt"),
                    object=safe_name(entry.name),
                    index=index,
                    count=count,
                    plate=entry.plate + 1,
                )
            )
            + suffix,
            mesh=as_mesh_data(entry.mesh),
            slots=tuple(entry.material_slots),
            name=entry.name,
            body=entry.mesh,
            plate=entry.plate,
        )
        for index, entry in enumerate(objects, start=1)
    )
    return ExportPlan(
        entries=entries,
        findings=tuple(check_before_export(objects, profile, sources or {})),
    )


def adhesion_margin(settings: PrintSettings) -> float:
    """Wie weit die Plattenhaftung über den Körper hinausreicht.

    Der Wert entscheidet, wie eng zwei Teile nebeneinander stehen dürfen — und
    er wurde beim Gewürzset zuerst vergessen: die Deckelplatte sah in der
    Rechnung frei aus und war es nicht, weil zwölf Streuscheiben je 3 mm Brim
    tragen und der zwischen zwei Nachbarn zweimal zählt.
    """
    kind = settings.adhesion.kind
    if kind == "brim":
        return settings.adhesion.brim_width
    if kind == "skirt":
        return settings.adhesion.skirt_distance
    if kind == "raft":
        # Ein Raft läuft ungefähr eine Brimbreite über den Körper hinaus; der
        # genaue Wert steht im Slicer und ist keine Solidon-Einstellung.
        return settings.adhesion.brim_width
    return 0.0


def check_adhesion_clearance(
    meshes: Sequence[MeshData],
    settings: PrintSettings,
    plates: Sequence[int] | None = None,
) -> list[Finding]:
    """Passen die Haftungsränder zwischen zwei Teilen noch nebeneinander?

    Die Körper selbst können reichlich Luft haben und der Druck trotzdem
    scheitern: Brim und Skirt stehen über den Körper hinaus, und zwischen zwei
    Nachbarn zählt der Rand zweimal. Gemessen wird in der Aufsicht, denn dort
    liegt die Haftung — was sich in der Höhe überlappt, ist eine andere Frage
    (:func:`app.core.geom.prepare.check_collisions`).
    """
    margin = adhesion_margin(settings)
    if margin <= 0.0:
        return []

    findings: list[Finding] = []
    needed = 2.0 * margin
    for first in range(len(meshes)):
        for second in range(first + 1, len(meshes)):
            if plates is not None and plates[first] != plates[second]:
                continue
            gap = _plane_gap(meshes[first].bounds, meshes[second].bounds)
            if gap >= needed - EPS_GEOM:
                continue
            findings.append(
                Finding(
                    code="arrange.adhesion_too_close",
                    severity="warning",
                    message=_(
                        "Zwei Teile stehen so dicht, dass ihre Plattenhaftung ineinanderläuft."
                    ),
                    values={
                        "a": first,
                        "b": second,
                        "gap": format_length(gap),
                        "needed": format_length(needed),
                    },
                )
            )
    return findings


def arrangement_holds(meshes: Sequence[MeshData], profile: Profile) -> bool:
    """Ist die Anordnung dieser Teile eine, die der Slicer übernehmen darf?

    Solidons Anordnung geht nur dann mit (§29), wenn sie überhaupt eine ist:
    kein Teil über dem anderen und keines außerhalb des Betts. Sonst bleibt es
    beim Anordnen des Slicers — der druckte sie sonst übereinander, und das ist
    schlimmer als eine verworfene Anordnung.

    Geprüft wird in der Aufsicht und großzügig: die Ränder der Platte bleiben
    frei, weil dort Rand, Düse und Reinigungsstelle liegen, und ein Teil, das
    genau auf der Kante endet, ist kein Fall für eine Zusage.
    """
    if not meshes:
        return False
    width, depth, height = profile.printer.build_volume
    half_width, half_depth = width / 2.0, depth / 2.0
    for mesh in meshes:
        box = mesh.bounds
        if box.minimum[0] < -half_width or box.maximum[0] > half_width:
            return False
        if box.minimum[1] < -half_depth or box.maximum[1] > half_depth:
            return False
        if box.maximum[2] > height:
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
    chosen = [entry for entry in objects if plate is None or entry.plate == plate]
    slots_of = {entry.id: {slot.name for slot in entry.material_slots} or {""} for entry in chosen}
    if len({name for names in slots_of.values() for name in names}) < 2:
        return []

    layer = settings.layers.layer_height
    if layer <= 0.0:
        return []
    tallest = max((float(entry.mesh.bounds.maximum[2]) for entry in chosen), default=0.0)
    shared = 0
    for index in range(int(tallest / layer) + 1):
        height = (index + 0.5) * layer
        present = {
            name
            for entry in chosen
            if float(entry.mesh.bounds.maximum[2]) >= height
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
    order: list[str] = []
    chosen: dict[str, int] = {}
    for entry in objects:
        names = [slot.name for slot in entry.material_slots] or [""]
        first = names[0]
        if first not in order:
            order.append(first)
        chosen[entry.id] = order.index(first)
    return chosen


def check_before_export(
    objects: list[SceneObject], profile: Profile, sources: dict[str, Source]
) -> list[Finding]:
    """Ein Bericht vor dem Schreiben, keine Sperre (§29)."""
    findings: list[Finding] = []
    meshes = [as_mesh_data(entry.mesh) for entry in objects]

    for entry, mesh in zip(objects, meshes, strict=True):
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
                )
            )

    findings.extend(check_build_volume(meshes, profile, [entry.plate for entry in objects]))
    findings.extend(_licence_findings(sources))
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
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for entry in plan.entries:
        target = directory / entry.filename
        target.write_bytes(
            export_bytes(entry.mesh, export_format, list(entry.slots), entry.name, entry.body)
        )
        written.append(target)
    _log.info("exported %d file(s) to %s", len(written), directory)
    return written


def _part_settings(
    mesh: MeshData, settings: PrintSettings | None, flavour: SlicerFlavour
) -> dict[str, str]:
    """Was dieses Teil anders braucht als die Platte (§29).

    Die Grundfläche kommt aus einem Schnitt knapp über dem Boden, nicht aus
    der Bounding-Box: ein Teil, das auf drei schmalen Armen steht, hat eine
    große Grundfläche und trotzdem kaum Halt. Genau dieser Fall ist der Grund
    für die Unterscheidung.
    """
    if settings is None:
        return {}
    # Beide erst hier: `handover` zieht die G-Code-Auswertung mit, und ein
    # Export soll nicht davon abhängen, dass ein Slicer im Spiel ist.
    from app.core.export import handover
    from app.core.slice import advise
    from app.core.slice.analysis import cross_section

    lowest = float(mesh.bounds.minimum[2])
    section = cross_section(mesh, lowest + FOOTPRINT_HEIGHT)
    footprint = 0.0 if section is None or section.is_empty else float(section.area)
    advice = advise.for_part(settings, mesh.bounds, footprint)
    return handover.object_keys(settings, advice, flavour)


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
) -> tuple[Path, list[Finding]]:
    """Alles auf einer Platte in *eine* 3MF-Datei (§20, §29).

    Der Unterschied zu :func:`write_plan` ist nicht das Format, sondern die
    Zahl der Dateien: ein Slicer, der eine Baugruppe bekommt, ordnet sie als
    Ganzes an und schreibt eine Druckdatei. Bekommt er fünf Dateien,
    entscheidet er über ihre Zusammengehörigkeit selbst — und was Solidon
    über die Platte weiß, ist verloren.

    ``plate`` schränkt auf eine Druckplatte ein; ohne Angabe geht alles hinein,
    was übergeben wurde.

    ``place_on_bed`` legt die Teile in Bettkoordinaten — für die Übergabe an
    den Slicer, die sie mit ``--arrange 0`` auch durchsetzt. Beim Export einer
    Datei bleibt es aus, und zwar aus zwei Gründen: ein Slicer, den jemand von
    Hand öffnet, ordnet ohnehin neu an, und eine zurückgelesene Platte läge
    sonst um den halben Bauraum verschoben im nächsten Dokument.

    Und es gilt nur für die Orca-Familie: sie misst von der Ecke der Platte.
    Cura und PrusaSlicer bekommen von Solidon eine Maschine, die um den
    Ursprung rechnet (``machine_center_is_zero`` beim einen, eine Bettform von
    ``-128`` bis ``128`` beim anderen) — verschoben landeten die Teile dort um
    den halben Bauraum daneben. Gemessen: ein Würfel, den das Dokument bei
    -10 bis 10 hat, lag in Curas G-Code bei 110,9 bis 137,8, und PrusaSlicer
    lehnte ihn mit „All objects are outside of the print volume" ganz ab.
    """
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

    findings = check_before_export(chosen, profile, sources or {})
    if settings is not None:
        # Was erst auf der Platte auffiele: Haftungsränder, die ineinander
        # laufen, und der Preis zweier Filamente in einem Auftrag.
        meshes = [as_mesh_data(entry.mesh) for entry in chosen]
        findings += check_adhesion_clearance(meshes, settings, [entry.plate for entry in chosen])
        findings += check_filament_changes(chosen, settings, plate)
    directory.mkdir(parents=True, exist_ok=True)
    width, depth, _height = profile.printer.build_volume
    bed = (width, depth) if place_on_bed and wants_bed_coordinates(flavour) else None

    if flavour == "cura":
        target = directory / (safe_name(project_name, "projekt") + ".stl")
        target.write_bytes(_cura_assembly(chosen, bed))
        _log.info("exported %d object(s) as one STL to %s", len(chosen), target.name)
        return target, findings

    parts = [
        threemf.AssemblyPart(
            mesh=as_mesh_data(entry.mesh),
            name=entry.name,
            slots=tuple(entry.material_slots),
            settings=_part_settings(as_mesh_data(entry.mesh), settings, flavour),
            # Die Platte reist mit. Ohne Einschränkung auf eine gehen alle in
            # dieselbe Datei — und dann muss dort stehen, welches Teil auf
            # welche gehört, sonst legt der Slicer sie übereinander.
            plate=entry.plate - min(other.plate for other in chosen),
        )
        for entry in chosen
    ]
    target = directory / (safe_name(project_name, "projekt") + ".3mf")
    target.write_bytes(
        threemf.write_assembly(
            parts,
            project_name,
            bed=bed,
            project_settings=_plate_settings(settings, profile, flavour, setup),
            # Nur wo es mehrere Platten gibt. Ein Versatz auf einer einzelnen
            # wäre eine Verschiebung ohne Grund, und die Datei trüge eine
            # Matrix, die nichts sagt.
            stride=width * threemf.PLATE_STRIDE if len({p.plate for p in parts}) > 1 else 0.0,
        )
    )
    _log.info("exported %d object(s) as one assembly to %s", len(parts), target.name)
    return target, findings


def _plate_settings(
    settings: PrintSettings | None,
    profile: Profile,
    flavour: SlicerFlavour,
    setup: SlicerSetup | None,
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
    return handover.project_settings(settings, profile, known)


def _cura_assembly(objects: Sequence[SceneObject], bed: tuple[float, float] | None) -> bytes:
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

    ``bed`` bleibt bei Cura leer (siehe :func:`wants_bed_coordinates`) — steht
    doch einmal etwas darin, wird über die Punkte verschoben, denn ein STL hat
    keine Platzierungsmatrix.
    """
    bodies = []
    for entry in objects:
        body = as_mesh_data(entry.mesh).raw.copy()
        if bed is not None:
            body.apply_translation((bed[0] / 2.0, bed[1] / 2.0, 0.0))
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
        return _step_bytes(body, name)
    if export_format == "stl":
        return mesh.to_stl()
    if export_format == "3mf":
        return threemf.write(mesh, slots, name)
    if export_format == "glb":
        return _glb_bytes(mesh, slots, name)
    data = trimesh.exchange.export.export_mesh(mesh.raw, None, file_type=export_format)
    return data if isinstance(data, bytes) else str(data).encode("utf-8")


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
    """
    stem = safe_name(name, "teil")
    parts = _parts_by_slot(mesh, slots)
    if parts is None:
        bodies = {stem: mesh.raw.copy()}
    else:
        bodies = {
            f"{stem}_{safe_name(label, f'slot{index}')}": part for index, (label, part) in parts
        }
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
        parts.append((index, (known[index].name, part)))
    return parts


def _step_bytes(body: Mesh | None, name: str = "") -> bytes:
    """STEP eines exakten Körpers — und ein klares Nein, wenn es keinen
    gibt (§30).

    Der Name reist mit: ohne ihn hieß das Teil in Fusion „Körper1", während
    er im Dokument die ganze Zeit dastand.
    """
    from app.core.brep import step as brep_step

    if body is None or not isinstance(body, BRepBody):
        # Kein ``ValidationError``: dessen Titel lautet „Ein Wert liegt
        # außerhalb des zulässigen Bereichs", und im Dialog stand er über der
        # richtigen Erklärung — hier ist kein Wert außerhalb eines Bereichs,
        # hier hat der Körper die falsche Art. Denselben Weg ist
        # ``NeedsSolidError`` schon einmal gegangen (siehe dort).
        raise NeedsSolidError(
            detail=_(
                "STEP hält Flächen und Kanten fest. Ein Netz hat keine — dafür bleiben STL und 3MF."
            ),
            values={"field": "format", "constraint": "needs_brep"},
        )
    return brep_step.write(body, name)  # type: ignore[arg-type]


def describe_plan(plan: ExportPlan) -> str:
    """Eine kurze Zusammenfassung für Statusleiste und Kommandozeile."""
    total = sum(entry.mesh.volume for entry in plan.entries) / 1000.0
    return (
        f"{len(plan.entries)} {tr('Dateien')} · "
        f"{format_length(sum(entry.mesh.bounds.size[2] for entry in plan.entries))} · "
        f"{total:.1f} cm³"
    )
