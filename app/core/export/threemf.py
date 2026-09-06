"""3MF mit Farbgruppen (Bauplan §20, §29).

trimesh schreibt 3MF, aber nicht die Materialgruppen je Dreieck, die ein
mehrfarbiger Druck braucht. Also wird der Container hier geschrieben: das
Format ist ein ZIP mit einem XML darin, und der Teil, auf den es ankommt, sind
fünfzehn Zeilen davon.

Die Zuordnung ist die aus §20: ein Materialslot des Objekts wird ein Eintrag
in einer ``basematerials``-Gruppe, und jedes Dreieck trägt den Index seines
Slots. Genau das liest ein Slicer, um zu wissen, zu welchem Filament eine
Fläche gehört.

Das Zurücklesen stand bis zum 02.09.2026 ebenfalls hier und liegt jetzt in
:mod:`app.core.ingest.threemf` — ``ingest`` liest, ``export`` schreibt, und
``geom`` kennt kein Dateiformat mehr. Die Konstanten des Containers, die beide
brauchen, stehen beim Leser; dieses Modul holt sie sich von dort.

Von Hand geschrieben statt mit einer Bibliothek, weil es keine gibt, die nur
das tut — und ein 3MF-Schreiber, der alles andere auch kann, wäre eine
Abhängigkeit für fünfzehn Zeilen.
"""

from __future__ import annotations

import dataclasses
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from io import BytesIO
from xml.etree import ElementTree as ET

from app.branding import APP_NAME, APP_VERSION
from app.core.geom.mesh import MeshData
from app.core.ingest.threemf import CORE_NAMESPACE, DEFAULT_COLOUR, MODEL_PATH, SETTINGS_PATH
from app.core.log import get_logger
from app.core.types import MaterialSlot
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
MODEL_RELATIONSHIP = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"

#: Wo die Orca-Familie die Einstellungen einer *Projektdatei* führt — was in
#: der Oberfläche Prozess, Filament und Drucker sind, in einer JSON-Abbildung.
#:
#: Ohne sie ist eine 3MF nur Geometrie: der Slicer öffnet sie mit dem Profil,
#: das gerade eingestellt ist, und alles, was Solidon über Temperatur, Tempo
#: und Kühlung dieses Teils weiß, ist beim Öffnen weg. Genau das trennt eine
#: Datei, die man druckt, von einer, die man erst noch einrichtet.
PROJECT_SETTINGS_PATH = "Metadata/project_settings.config"

#: Wo PrusaSlicer dasselbe führt — dieselbe Sache, ein anderes Format: eine
#: Zeile ``; schlüssel = wert`` je Einstellung statt einer JSON-Abbildung.
#:
#: Er schreibt sie beim Konsolenexport selbst nicht mit, **liest** sie aber:
#: eine 3MF mit dieser Beilage, ohne ``--load`` geslict, ergab Solidons Werte
#: bis in die Wandzahl und die Fülldichte hinein. Ohne sie war eine
#: exportierte Datei für PrusaSlicer bloß Geometrie.
PRUSA_CONFIG_PATH = "Metadata/Slic3r_PE.config"

#: Die erste Zeile jener Beilage. PrusaSlicer überspringt sie — bei ihm steht
#: dort seine eigene Kennung —, und was ohne sie an erster Stelle stünde, wäre
#: verloren, ohne dass es jemand merkt.
PRUSA_CONFIG_HEADER = "; von Solidon geschrieben"


def write(mesh: MeshData, slots: list[MaterialSlot] | None = None, name: str = "") -> bytes:
    """Ein Körper als 3MF-Container, mit einem Material je Slot."""
    entries = _slots_for(mesh, slots)
    model = _model_xml(mesh, entries, name)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr("[Content_Types].xml", _content_types())
        container.writestr("_rels/.rels", _relationships())
        container.writestr(MODEL_PATH, model)
    _log.info("wrote 3MF with %d material(s)", len(entries))
    return buffer.getvalue()


@dataclass(frozen=True, slots=True)
class AssemblyPart:
    """Ein Teil einer Baugruppe, für :func:`write_assembly` (§20, §29)."""

    mesh: MeshData
    name: str = ""
    slots: tuple[MaterialSlot, ...] = ()
    settings: Mapping[str, str] = field(default_factory=dict)
    """Was nur für dieses Teil gilt, in der Schreibweise des Slicers.

    Eine Platte hat einen Satz Einstellungen, aber nicht jedes Teil darauf
    braucht dasselbe: eine Streuscheibe steht auf drei 1,1-mm-Federarmen und
    will einen Brim, die zwölf Behälter daneben stehen auf Ø 40 und wollen
    keinen. Leer heißt: es gilt, was für die Platte gilt.
    """
    plate: int = 0
    """Auf welche Druckplatte dieses Teil gehört, von null an gezählt."""


SlotKey = tuple[TranslatableText | str, tuple[float, float, float] | None, str | None, str | None]
"""Woran zwei Slots als **dasselbe Filament** erkannt werden: Name, Farbe,
Herstellerprofil und Materialart."""


def slot_identity(slot: MaterialSlot) -> SlotKey:
    """Die Identität eines Slots für das Zusammenlegen (§20).

    Name und Farbe allein reichten nicht: Zwei Teile mit je einem Slot
    „Schwarz" in Schwarz, eines PLA und eines PETG, wurden **eine** Düse —
    die Baugruppe trug einen Materialeintrag, jedes Dreieck ``p1="0"``, und
    das PETG-Profil war aus der Liste verschwunden, je nachdem, welches Teil
    zuerst kam (Gesamtreview 05.09.2026, CORE-21). Gleicher Name und gleiche
    Farbe dürfen zusammenfallen, wenn auch Profil und Materialart gleich sind.
    """
    return (slot.name, slot.colour, slot.material, slot.material_type)


def merge_slots(
    parts: Sequence[AssemblyPart], across: Sequence[AssemblyPart] | None = None
) -> list[MaterialSlot]:
    """Eine Materialliste über alle Teile — das ist die Extruderzuordnung
    (§20).

    Ein Slot ist ein Filament, kein Objektmerkmal: zwei Teile in derselben
    Farbe sollen aus derselben Düse kommen und nicht aus zweien. Zusammengelegt
    wird deshalb über :func:`slot_identity` — Name, Farbe, Profil **und**
    Materialart (CORE-21: gleichfarbiges PLA und PETG sind zwei Spulen) —, und
    die Reihenfolge des Ergebnisses ist die Reihenfolge der Extruder.

    Ohne diese Zusammenlegung bekäme eine Baugruppe aus drei einfarbigen Teilen
    drei Materialien — und der Slicer fragte nach drei Filamenten für einen
    einfarbigen Druck.

    **``across`` ist der Auftrag, ``parts`` die Platte** (Fund von 3d-druck-de,
    26.08.2026). Nummeriert wird nach dem ersten Auftreten — und weil der
    Export je Platte aufruft, lag dieselbe Farbe in einem Auftrag an
    verschiedenen Düsen: Platte 1 nur Rot (Extruder 0), Platte 2 Weiß und Rot
    (Rot dann Extruder 1). Wer den Auftrag am Stück druckt, müsste mittendrin
    umstecken. Wer alle Platten kennt, gibt sie hier mit; die Nummern kommen
    dann für alle aus derselben Zählung. Ohne Angabe bleibt es bei ``parts``,
    denn eine einzeln exportierte Platte *ist* der Auftrag.
    """
    order: list[MaterialSlot] = []
    # Der Name darf ein ``TranslatableText`` sein (:attr:`MaterialSlot.name`).
    # Zusammengelegt wird trotzdem richtig: Ein solcher Text vergleicht und
    # hasht wie seine Message-ID, auch gegen eine schlichte Zeichenkette.
    seen: dict[SlotKey, int] = {}
    for part in across if across is not None else parts:
        for slot in part.slots or (MaterialSlot(index=0, name=""),):
            key = slot_identity(slot)
            if key in seen:
                continue
            seen[key] = len(order)
            order.append(dataclasses.replace(slot, index=len(order)))
    if across is None:
        return order
    # Die Belegung des Auftrags, beschränkt auf das, was diese Platte braucht —
    # mit den Nummern des Auftrags. Ein Slicer, der eine Platte allein bekommt,
    # soll nicht nach Filamenten fragen, die auf ihr nicht vorkommen.
    here = {
        slot_identity(slot)
        for part in parts
        for slot in part.slots or (MaterialSlot(index=0, name=""),)
    }
    return [slot for slot in order if slot_identity(slot) in here]


def by_extruder(slots: Sequence[MaterialSlot]) -> list[MaterialSlot | None]:
    """Dieselben Slots an ihrem Extruderplatz, mit ``None`` in den Lücken (§20).

    :func:`merge_slots` rechnet die Nummer des **Auftrags** aus und gibt für
    eine einzelne Platte nur die Filamente zurück, die dort vorkommen. Wer
    diese Liste danach durchnummeriert, wirft die Rechnung weg: Lässt Platte 2
    die Farbe von Platte 1 aus, rutscht die verbliebene auf Extruder 0, und
    derselbe Auftrag bräuchte mittendrin ein Umstecken.

    Der freie Platz bleibt deshalb frei. Was ein Aufrufer daraus macht — ein
    Platzhalter in der Materialliste, ein Filamentprofil mit den Projektwerten
    — hängt an seiner Datei; die Reihenfolge ist an allen Stellen dieselbe.
    """
    if not slots:
        return []
    placed: list[MaterialSlot | None] = [None] * (max(entry.index for entry in slots) + 1)
    for entry in slots:
        placed[entry.index] = entry
    return placed


def write_assembly(
    parts: Sequence[AssemblyPart],
    name: str = "",
    bed: tuple[float, float] | None = None,
    project_settings: Mapping[str, object] | None = None,
    stride: float = 0.0,
    prusa_config: Mapping[str, str] | None = None,
    across: Sequence[AssemblyPart] | None = None,
) -> bytes:
    """Mehrere Körper als eine 3MF-Baugruppe (§20, §29).

    Das ist der Unterschied zwischen „eine Datei je Teil" und „ein
    Druckauftrag": ein Slicer, der eine Baugruppe bekommt, ordnet sie als
    Ganzes an und schreibt eine Druckdatei. Bekommt er einzelne Dateien,
    entscheidet er über die Zusammengehörigkeit selbst — und was Solidon über
    die Platte weiß, ist verloren.

    Die Materialien sind über alle Teile zusammengelegt (:func:`merge_slots`),
    denn genau diese Liste liest der Slicer als seine Extruderbelegung.

    ``bed`` ist die Breite und Tiefe des Bauraums. Mit dieser Angabe bekommt
    jedes Teil eine Platzierung auf der Platte — Solidon rechnet um den
    Nullpunkt, ein Slicer misst von der Ecke. Ohne die Umrechnung liegt die
    ganze Szene im negativen Bereich, also außerhalb des Betts, und der Slicer
    ordnet notgedrungen selbst an: was `arrange_bed` errechnet hat, ist dann
    weg, samt Haftungsrand und Plattenzuordnung.

    Verschoben wird über die Platzierungsmatrix des Standards, nicht über die
    Punkte. Die Geometrie bleibt damit die, die im Dokument steht — dieselbe
    Datei taugt weiter als Modell und nicht nur als Druckauftrag.

    ``project_settings`` sind die Druckeinstellungen der Platte, wie die
    Orca-Familie sie in einer Projektdatei führt (:data:`PROJECT_SETTINGS_PATH`).
    Ohne sie öffnet der Slicer die Datei mit dem Profil, das gerade eingestellt
    ist — die Geometrie stimmt dann, und alles andere ist Zufall. Gebaut wird
    die Abbildung nicht hier, sondern in ``handover``: sie zu kennen heißt, den
    Slicer zu kennen, und dieses Modul kennt nur das Format.

    ``prusa_config`` ist dieselbe Sache für PrusaSlicer, der sie als
    Textzeilen führt (:data:`PRUSA_CONFIG_PATH`). Zwei Parameter für einen
    Zweck, weil es zwei Formate sind — und Formate sind das, was dieses Modul
    kennt.
    """
    if not parts:
        raise ValueError("an assembly needs at least one part")

    materials = merge_slots(parts, across=across)
    model = _assembly_xml(parts, materials, name, bed, stride)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr("[Content_Types].xml", _content_types())
        container.writestr("_rels/.rels", _relationships())
        container.writestr(MODEL_PATH, model)
        container.writestr(SETTINGS_PATH, _settings_xml(parts))
        if project_settings:
            container.writestr(
                PROJECT_SETTINGS_PATH,
                json.dumps(dict(project_settings), indent=4, ensure_ascii=False),
            )
        if prusa_config:
            # Die Kopfzeile ist kein Schmuck: PrusaSlicer überspringt die
            # erste Zeile dieser Beilage — dort steht bei ihm selbst „generated
            # by PrusaSlicer". Ohne sie fiel der alphabetisch erste Schlüssel
            # heraus, und zwar lautlos: gemessen war es
            # ``avoid_crossing_perimeters``, das als 1 in der Datei stand und
            # als 0 im G-Code ankam.
            lines = [PRUSA_CONFIG_HEADER]
            lines += [f"; {key} = {value}" for key, value in sorted(prusa_config.items())]
            container.writestr(PRUSA_CONFIG_PATH, "\n".join(lines) + "\n")
    _log.info(
        "wrote 3MF assembly: %d part(s), %d material(s), settings: %s",
        len(parts),
        len(materials),
        "yes" if project_settings or prusa_config else "no",
    )
    return buffer.getvalue()


def _settings_xml(parts: Sequence[AssemblyPart]) -> bytes:
    """Die Beilage, in der die Orca-Familie Namen und Objektwerte führt.

    Zwei Dinge stehen hier, die sonst verloren gingen. Zum einen die **Namen**:
    der Standard hat ein ``name``-Attribut am Objekt, und Solidon schreibt es
    auch — aber diese Slicer schreiben es selbst nie und lesen die Namen von
    hier. Eine Baugruppe kam deshalb als „Object 1, Object 2" an, obwohl die
    Namen in der Datei standen.

    Zum anderen die **Einstellungen je Teil**. Eine Platte hat einen Satz
    Werte, aber nicht jedes Teil darauf braucht dasselbe — und ohne diesen Ort
    gäbe es nur die Wahl zwischen „alle bekommen es" und „keiner".

    Für PrusaSlicer und CuraEngine hat die Datei keine Bedeutung; sie stört
    dort auch nicht, denn was ein Programm nicht kennt, liest es nicht.
    """
    config = ET.Element("config")
    for number, part in enumerate(parts, start=2):
        node = ET.SubElement(config, "object", {"id": str(number)})
        if part.name:
            ET.SubElement(node, "metadata", {"key": "name", "value": part.name})
        for key, value in part.settings.items():
            ET.SubElement(node, "metadata", {"key": key, "value": value})

    # Und die Platten. Ohne sie ist eine Datei mit mehreren Platten für den
    # Slicer eine einzige, auf der alles nebeneinander steht — die Teile
    # lägen weit außerhalb des Betts, und er ordnete notgedrungen neu an.
    #
    # Aufbau aus einer echten Slicer-Datei gelesen (siehe :data:`PLATE_STRIDE`):
    # je Platte ein ``plate``-Block mit ``plater_id`` von eins an und je Teil
    # ein ``model_instance``, das auf die Objektnummer zeigt. Die
    # Vorschaubilder, die der Slicer daneben führt, entstehen bei ihm — was
    # hier fehlt, rechnet er beim Öffnen nach.
    for plate in sorted({part.plate for part in parts}):
        block = ET.SubElement(config, "plate")
        ET.SubElement(block, "metadata", {"key": "plater_id", "value": str(plate + 1)})
        ET.SubElement(block, "metadata", {"key": "plater_name", "value": ""})
        ET.SubElement(block, "metadata", {"key": "locked", "value": "false"})
        for number, part in enumerate(parts, start=2):
            if part.plate != plate:
                continue
            instance = ET.SubElement(block, "model_instance")
            ET.SubElement(instance, "metadata", {"key": "object_id", "value": str(number)})
            ET.SubElement(instance, "metadata", {"key": "instance_id", "value": "0"})

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + bytes(
        ET.tostring(config, encoding="utf-8")
    )


def _slots_for(mesh: MeshData, slots: list[MaterialSlot] | None) -> list[MaterialSlot]:
    """Jeder Slot, den das Mesh wirklich benutzt, mit Namen und Farbe."""
    from app.core.geom.attributes import used_slots

    known = {entry.index: entry for entry in (slots or [])}
    return [
        known.get(index, MaterialSlot(index=index, name=_("Slot {number}", number=index)))
        for index in used_slots(mesh)
    ]


def _write_geometry(
    parent: ET.Element,
    mesh: MeshData,
    group_id: str,
    order: dict[int, int],
) -> None:
    """Ecken und Dreiecke eines Körpers, mit ihrer Materialzuordnung.

    Eine Stelle für beide Wege: eine Baugruppe schreibt dieselben Dreiecke wie
    ein einzelner Körper, nur mehrfach. Zwei Versionen davon wären zwei Orte,
    an denen sich eine Materialzuordnung verlieren kann.

    **Sechs Nachkommastellen, nicht fünf.** Der Kern rechnet auf
    :data:`app.core.units.EPS_GEOM` genau (§11.2, ein Nanometer), und fünf
    Stellen rundeten gröber, als zwei Punkte auseinanderliegen dürfen, um
    verschiedene zu sein. Was die Stelle kostet, ist gemessen: an einer Kugel
    mit 5 120 Dreiecken sechs Prozent mehr XML, gepackt weniger.
    """
    geometry = ET.SubElement(parent, "mesh")
    vertices = ET.SubElement(geometry, "vertices")
    for point in mesh.raw.vertices:
        ET.SubElement(
            vertices,
            "vertex",
            {"x": f"{point[0]:.6f}", "y": f"{point[1]:.6f}", "z": f"{point[2]:.6f}"},
        )

    triangles = ET.SubElement(geometry, "triangles")
    assignment = mesh.slots or ((0,) * len(mesh.raw.faces))
    for face, slot in zip(mesh.raw.faces, assignment, strict=True):
        ET.SubElement(
            triangles,
            "triangle",
            {
                "v1": str(int(face[0])),
                "v2": str(int(face[1])),
                "v3": str(int(face[2])),
                "pid": group_id,
                "p1": str(order.get(int(slot), 0)),
            },
        )


def _assembly_xml(
    parts: Sequence[AssemblyPart],
    materials: list[MaterialSlot],
    name: str,
    bed: tuple[float, float] | None = None,
    stride: float = 0.0,
) -> bytes:
    """Das Modell-XML einer Baugruppe: ein ``object`` je Teil, ein ``item`` je
    Teil im Build.
    """
    root = ET.Element(
        "model",
        {"unit": "millimeter", "xml:lang": "de-DE", "xmlns": CORE_NAMESPACE},
    )
    ET.SubElement(root, "metadata", {"name": "Application"}).text = f"{APP_NAME} {APP_VERSION}"
    if name:
        ET.SubElement(root, "metadata", {"name": "Title"}).text = name

    resources = ET.SubElement(root, "resources")
    group_id = "1"
    group = ET.SubElement(resources, "basematerials", {"id": group_id})
    # **Ein Eintrag je Extruder, auch für die freien Plätze.** Die Nummer eines
    # Slots gehört dem Auftrag (:func:`merge_slots`), und ein Dreieck zeigt mit
    # ``p1`` auf die *Stelle* in dieser Gruppe — beides passt nur zusammen,
    # wenn die Lücken der Platte hier stehen bleiben (:func:`by_extruder`).
    for position, found in enumerate(by_extruder(materials)):
        # Ein freier Platz bekommt einen namenlosen Slot: Der Name daraus ist
        # „Slot N", die Farbe die graue Vorgabe — sichtbar als Platzhalter und
        # nicht als Wahl.
        entry = found if found is not None else MaterialSlot(index=position, name="")
        ET.SubElement(
            group,
            "base",
            # ``str`` ist hier keine Höflichkeit, sondern Pflicht: Ein Slotname
            # darf ein ``TranslatableText`` sein, und ``ElementTree`` schreibt
            # nur Zeichenketten — roh übergeben brach der ganze Export mit
            # ``cannot serialize`` (gemessen am Beispiel „Schild zweifarbig",
            # 26.08.2026). In die Datei gehört ohnehin die Übersetzung: Sie
            # wird von einem Slicer gelesen, nicht von Solidon.
            {
                "name": str(entry.name) or str(_("Slot {number}", number=position)),
                "displaycolor": _colour(entry),
            },
        )

    # Wohin ein objekteigener Slot in der gemeinsamen Liste zeigt. Ohne diese
    # Übersetzung trüge Teil zwei die Farben von Teil eins.
    positions = {slot_identity(entry): entry.index for entry in materials}

    build = ET.SubElement(root, "build")
    for number, part in enumerate(parts, start=2):
        order = {
            slot.index: positions.get(slot_identity(slot), 0)
            for slot in part.slots or (MaterialSlot(index=0, name=""),)
        }
        body = ET.SubElement(
            resources,
            "object",
            {
                "id": str(number),
                "type": "model",
                "pid": group_id,
                "pindex": "0",
                **({"name": part.name} if part.name else {}),
            },
        )
        _write_geometry(body, part.mesh, group_id, order)
        item = {"objectid": str(number)}
        placement = _placement(bed, part.plate, stride)
        if placement is not None:
            item["transform"] = placement
        ET.SubElement(build, "item", item)

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + bytes(ET.tostring(root, encoding="utf-8"))


def _placement(bed: tuple[float, float] | None, plate: int, stride: float) -> str | None:
    """Die Platzierungsmatrix des Standards: neun Werte Drehung, drei
    Verschiebung. ``None``, wenn nichts zu verschieben ist.

    Gedreht wird nichts. Verschoben wird aus zwei voneinander unabhängigen
    Gründen, und beide landen in derselben Matrix:

    ``bed`` verschiebt um den halben Bauraum, denn dort liegt Solidons
    Nullpunkt und ein Slicer misst von der Ecke. Das gilt nur für die Übergabe
    an den Slicer und nur für die Orca-Familie. Dass diese Matrix dort wirklich
    gelesen wird, ist gemessen: mit ihr und ``--arrange 0`` stehen die Teile im
    G-Code auf ein Zehntel dort, wo das Dokument sie hat.

    ``stride`` verschiebt auf die eigene Druckplatte. Die Orca-Familie legt
    ihre Platten in **einem** Koordinatenraum nebeneinander; welche Platte
    gemeint ist, steht in der Beilage, aber wo das Teil liegt, steht hier. Das
    gilt **immer**, wenn es mehr als eine Platte gibt — auch beim Export ohne
    Bettkoordinaten. Sonst stünde die zweite Platte auf der ersten.
    """
    across = (bed[0] / 2.0 if bed else 0.0) + plate * stride
    along = bed[1] / 2.0 if bed else 0.0
    if not across and not along:
        return None
    return f"1 0 0 0 1 0 0 0 1 {across:g} {along:g} 0"


#: Wie weit die nächste Druckplatte nach rechts rückt, als Vielfaches der
#: Bettbreite.
#:
#: **Nachgemessen, nicht angenommen.** In ``BowlingGame.3mf`` — vom
#: ElegooSlicer für denselben Drucker geschrieben, Bett 256 auf 256 — steht das
#: Objekt der ersten Platte bei x = 127,82 und das der zweiten bei x = 416,14.
#: Die Differenz von 288,3 mm ist 256 plus ein Achtel davon, und plattenlokal
#: stehen beide an derselben Stelle. Ein geratener Abstand legte die Teile
#: neben ihre Platte, und angesehen hätte man es der Datei nicht.
PLATE_STRIDE = 1.125


def _model_xml(mesh: MeshData, slots: list[MaterialSlot], name: str) -> bytes:
    root = ET.Element(
        "model",
        {
            "unit": "millimeter",
            "xml:lang": "de-DE",
            "xmlns": CORE_NAMESPACE,
        },
    )
    ET.SubElement(root, "metadata", {"name": "Application"}).text = f"{APP_NAME} {APP_VERSION}"
    if name:
        ET.SubElement(root, "metadata", {"name": "Title"}).text = name

    resources = ET.SubElement(root, "resources")

    group_id = "1"
    materials = ET.SubElement(resources, "basematerials", {"id": group_id})
    order = {entry.index: position for position, entry in enumerate(slots)}
    for entry in slots:
        ET.SubElement(
            materials,
            "base",
            # ``str`` aus demselben Grund wie in :func:`write_assembly` — ein
            # übersetzbarer Slotname brachte ``ElementTree`` zu Fall.
            {
                "name": str(entry.name) or str(_("Slot {number}", number=entry.index)),
                "displaycolor": _colour(entry),
            },
        )

    body = ET.SubElement(
        resources,
        "object",
        {"id": "2", "type": "model", "pid": group_id, "pindex": "0"},
    )
    _write_geometry(body, mesh, group_id, order)

    build = ET.SubElement(root, "build")
    ET.SubElement(build, "item", {"objectid": "2"})

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + bytes(ET.tostring(root, encoding="utf-8"))


def _colour(slot: MaterialSlot) -> str:
    values = (round(max(0.0, min(1.0, part)) * 255) for part in slot.colour or DEFAULT_COLOUR)
    return "#" + "".join(f"{value:02X}" for value in values)


def _content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml" />'
        '<Default Extension="model" '
        'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />'
        "</Types>"
    )


def _relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Relationships xmlns="{RELATIONSHIP_NAMESPACE}">'
        f'<Relationship Target="/{MODEL_PATH}" Id="rel0" Type="{MODEL_RELATIONSHIP}" />'
        "</Relationships>"
    )
