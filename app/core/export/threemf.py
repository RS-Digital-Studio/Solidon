"""3MF mit Farbgruppen (Bauplan §20, §29).

trimesh schreibt 3MF, aber nicht die Materialgruppen je Dreieck, die ein
mehrfarbiger Druck braucht. Also wird der Container hier geschrieben: das
Format ist ein ZIP mit einem XML darin, und der Teil, auf den es ankommt, sind
fünfzehn Zeilen davon.

Die Zuordnung ist die aus §20: ein Materialslot des Objekts wird ein Eintrag
in einer ``basematerials``-Gruppe, und jedes Dreieck trägt den Index seines
Slots. Genau das liest ein Slicer, um zu wissen, zu welchem Filament eine
Fläche gehört.

Das Zurücklesen steht ebenfalls hier, aus demselben Grund: trimesh parst die
Geometrie einer 3MF, gibt sie aber einheitlich grau zurück. Eine von hier
exportierte und wieder geöffnete Datei verlöre genau das, wofür dieses Modul
geschrieben wurde.

Die Geometrie wird inzwischen auch hier gelesen, und das war nicht der Plan.
Eine 3MF aus einem Slicer hält ihre Objekte in getrennten Dateien unter
``3D/Objects/`` und verweist aus dem Build darauf — die Production-Erweiterung.
trimesh löst eine Komponente, die in so eine Datei zeigt, zur *ganzen Datei*
auf statt zu dem einen Objekt, das sie benennt: eine Datei mit siebzehn Teilen
in einer Objektdatei kam siebzehnmal heraus, jeder Körper auf einer Kopie
seiner selbst gestapelt. Am Modellkorpus gemessen: eine Düse aus zwei Körpern
und 290 120 Dreiecken kam als vier Körper und 580 240 an, mit doppeltem Volumen
— und damit doppelter Materialschätzung und doppelter Druckzeit. Das ist kein
Tempoproblem, also wird es nicht mit einem schnelleren Parser behoben, sondern
mit dem richtigen.

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

import numpy as np
import trimesh

from app.branding import APP_NAME, APP_VERSION
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import MaterialSlot
from app.i18n import _

_log = get_logger(__name__)

CORE_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
MODEL_RELATIONSHIP = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"

MODEL_PATH = "3D/3dmodel.model"

#: Wo ein Slicer die Namen der Teile hinschreibt. Nicht Teil des Formats —
#: der Standard hat ein ``name``-Attribut, und diese Dateien lassen es leer —
#: aber es ist der einzige Ort, an dem „Wasserfall_4_TPU-Liner" notiert steht,
#: und eine Szene aus Körpern namens „object 7" ist eine Szene, in der niemand
#: arbeiten kann. Gelesen, wenn da; achselzuckend übergangen, wenn nicht.
SETTINGS_PATH = "Metadata/model_settings.config"

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

#: Endungen, die ein Slicer in einem Teilnamen stehen lässt, weil das Teil aus
#: einer Datei kam.
NAME_SUFFIXES = (".stl", ".3mf", ".obj", ".step", ".stp")

#: Platzhalter fürs Zählen, wo nur die Namen zählen.
_EMPTY = MeshData.of(trimesh.Trimesh())

#: Farbe, die ein Slot ohne eigene bekommt. Grau, damit niemand sie für eine
#: Wahl hält.
DEFAULT_COLOUR = (0.72, 0.72, 0.72)

#: Wie tief eine Komponente andere Komponenten referenzieren darf. Das Format
#: erlaubt einen Baum, und eine Datei, die so tief verschachtelt, ist kaputt
#: statt raffiniert.
#:
#: Eine Tiefengrenze allein reicht gegen einen Zyklus nicht, und das war eine
#: Messung wert: zwei Objekte, die sich gegenseitig mit je zwei Komponenten
#: referenzieren, haben 2^32 Pfade hindurch, alle 32 tief und keiner
#: wiederholt — die Grenze hält also, und der Import kehrt nie zurück.
#: Fünfhundert Byte Datei. Was es wirklich stoppt, ist die Weigerung, ein
#: Objekt zu betreten, das schon auf dem Weg dorthin liegt (§32: eine Grenze
#: sagt etwas, sie hängt nicht).
MAX_DEPTH = 32


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


def merge_slots(parts: Sequence[AssemblyPart]) -> list[MaterialSlot]:
    """Eine Materialliste über alle Teile — das ist die Extruderzuordnung
    (§20).

    Ein Slot ist ein Filament, kein Objektmerkmal: zwei Teile in derselben
    Farbe sollen aus derselben Düse kommen und nicht aus zweien. Zusammengelegt
    wird deshalb über Name und Farbe, und die Reihenfolge des Ergebnisses ist
    die Reihenfolge der Extruder.

    Ohne diese Zusammenlegung bekäme eine Baugruppe aus drei einfarbigen Teilen
    drei Materialien — und der Slicer fragte nach drei Filamenten für einen
    einfarbigen Druck.
    """
    merged: list[MaterialSlot] = []
    seen: dict[tuple[str, tuple[float, float, float] | None], int] = {}
    for part in parts:
        for slot in part.slots or (MaterialSlot(index=0, name=""),):
            key = (slot.name, slot.colour)
            if key in seen:
                continue
            seen[key] = len(merged)
            merged.append(dataclasses.replace(slot, index=len(merged)))
    return merged


def write_assembly(
    parts: Sequence[AssemblyPart],
    name: str = "",
    bed: tuple[float, float] | None = None,
    project_settings: Mapping[str, object] | None = None,
    stride: float = 0.0,
    prusa_config: Mapping[str, str] | None = None,
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

    materials = merge_slots(parts)
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


@dataclass(frozen=True, slots=True)
class Groups:
    """Die Farbgruppen, die eine 3MF-Datei trägt (§20, Import)."""

    slots: tuple[int, ...]
    """Ein Slot-Index je Dreieck, in der Reihenfolge der Datei."""
    materials: tuple[MaterialSlot, ...]


def read(payload: bytes, faces: int) -> Groups | None:
    """Liest die Materialgruppen aus einer 3MF zurück — oder ``None``, wenn
    sie keine hat.

    Gelesen wird nur eine Datei mit einem einzigen Mesh-Objekt: bei mehreren
    werden die Dreiecke auf dem Weg hinein aneinandergehängt, und die
    Reihenfolge zu raten, in der sie gelandet sind, wäre schlechter, als nichts
    zu sagen. ``faces`` ist das, was der geladene Körper wirklich hat — eine
    Abweichung heißt genau dieser Fall.

    Die Slotnummern kommen als 0..n-1 heraus. 3MF kennt Positionen in einer
    Gruppe, nicht unsere Nummerierung — ein Körper, dessen einzige Farbe Slot 3
    war, kommt also als Slot 0 zurück, mit Namen und Farbe unversehrt.
    """
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            model = ET.fromstring(container.read(MODEL_PATH))
    except (KeyError, zipfile.BadZipFile, ET.ParseError):
        return None

    materials = _materials_in(model)
    if not materials:
        return None

    objects = model.findall(f".//{{{CORE_NAMESPACE}}}object")
    meshes = [entry for entry in objects if entry.find(f"{{{CORE_NAMESPACE}}}mesh") is not None]
    if len(meshes) != 1:
        return None

    group, names = next(iter(materials.items()))
    default = int(meshes[0].get("pindex") or 0)
    triangles = meshes[0].findall(f".//{{{CORE_NAMESPACE}}}triangle")
    if len(triangles) != faces:
        _log.info(
            "3MF has %d triangles, the loaded body %d — no groups read", len(triangles), faces
        )
        return None

    assignment = tuple(
        int(entry.get("p1") or default) if (entry.get("pid") or group) == group else default
        for entry in triangles
    )
    used = sorted(set(assignment))
    if len(used) < 2:
        return None  # ein Material für den ganzen Körper ist keine Gruppe, die sich lohnt
    order = {position: index for index, position in enumerate(used)}
    return Groups(
        slots=tuple(order[entry] for entry in assignment),
        materials=tuple(
            MaterialSlot(index=index, name=names[position][0], colour=names[position][1])
            for index, position in enumerate(used)
            if position < len(names)
        ),
    )


@dataclass(frozen=True, slots=True)
class Part:
    """Ein Körper eines 3MF-Builds, mit dem Ort, an den die Datei ihn setzt."""

    name: str
    mesh: MeshData
    slots: tuple[MaterialSlot, ...] = field(default_factory=tuple)


def read_objects(payload: bytes) -> list[Part]:
    """Jeder Körper, den der Build platziert, jeder dort, wohin die Datei ihn
    setzt.

    Eine leere Liste heißt: das ist keine 3MF, die sich hier lesen lässt — der
    Aufrufer fällt auf den allgemeinen Loader zurück, statt für eine Datei eine
    Ausnahme zu bekommen, die ein anderer Leser durchaus schaffen mag.

    Ein Körper je Blatt-Mesh, nicht einer je Build-Element. Ein Slicer packt
    eine Baugruppe als ein Element aus Komponenten, und diese Komponenten
    *sind* die einzelnen Teile: Gehäuse, Deckel, Tülle, Liner. Sie als einen
    verschweißten Körper zu übergeben würfe genau die Teilung weg, die sie
    einzeln druckbar macht — und es ist die Teilung, die das Projekt ohnehin
    braucht, für sein eigenes Material je Körper (§12) und seine eigene
    Platte (§25).
    """
    parts: list[Part] = []
    for leaf in _leaves(payload):
        body = _mesh_from(leaf.node)
        if body is None:
            continue
        moved = body.raw.copy()
        moved.apply_transform(leaf.transform)

        groups = _groups_of(leaf.node, leaf.palette)
        mesh = (
            MeshData(raw=moved, slots=groups.slots) if groups is not None else body.replacing(moved)
        )
        parts.append(
            Part(name=leaf.name, mesh=mesh, slots=tuple(groups.materials) if groups else ())
        )

    _log.info("read %d part(s) from a 3MF build", len(parts))
    return _numbered(parts)


def count_objects(payload: bytes) -> int:
    """Wie viele Körper :func:`read_objects` zurückgäbe.

    Der Stapel vergibt Objekt-IDs, bevor irgendetwas gerechnet ist (§11) — die
    Anzahl muss also bekannt sein, bevor es die Geometrie ist. Es läuft
    denselben Baum ab, ohne ein einziges Dreieck in eine Zahl zu verwandeln:
    die Koordinaten sind das, was kostet, nicht die Feststellung, dass es sie
    gibt.
    """
    return len(_numbered([Part(name=leaf.name, mesh=_EMPTY) for leaf in _leaves(payload)]))


@dataclass(frozen=True, slots=True)
class _Leaf:
    """Ein Mesh, das der Build erreicht, und alles, was unterwegs über es
    bekannt wurde.
    """

    name: str
    node: ET.Element
    transform: np.ndarray
    palette: dict[str, list[tuple[str, tuple[float, float, float]]]]


def _leaves(payload: bytes) -> list[_Leaf]:
    """Läuft den Build ab und sammelt jedes Mesh, das er erreicht, der Reihe
    nach.
    """
    try:
        with zipfile.ZipFile(BytesIO(payload)) as container:
            names = set(container.namelist())
            if MODEL_PATH not in names:
                return []
            models = {MODEL_PATH: ET.fromstring(container.read(MODEL_PATH))}
            for entry in sorted(names):
                if entry.startswith("3D/Objects/") and entry.endswith(".model"):
                    models[entry] = ET.fromstring(container.read(entry))
            titles = _titles(container.read(SETTINGS_PATH)) if SETTINGS_PATH in names else {}
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as problem:
        _log.info("3MF could not be read as an assembly: %s", problem)
        return []

    catalog = {path: _objects_in(model) for path, model in models.items()}
    materials = {path: _materials_in(model) for path, model in models.items()}

    found: list[_Leaf] = []
    for item in models[MODEL_PATH].findall(f"{{{CORE_NAMESPACE}}}build/{{{CORE_NAMESPACE}}}item"):
        identifier = item.get("objectid")
        if identifier is None:
            continue
        found.extend(
            _parts_of(
                identifier,
                _inside(item.get(f"{{{PRODUCTION_NAMESPACE}}}path")),
                _matrix(item.get("transform")),
                catalog,
                materials,
                titles,
                item.get("name") or titles.get(identifier, ""),
                0,
            )
        )
    return found


def _numbered(parts: list[Part]) -> list[Part]:
    """Hält Körper auseinander, die mit demselben Namen herauskamen.

    Siebzehn Teile einer Objektdatei teilen sich, wie auch immer das Objekt
    hieß, und ein Objektbaum mit siebzehn identischen Einträgen ist eine Liste,
    kein Baum.
    """
    seen: dict[str, int] = {}
    result: list[Part] = []
    counts = {part.name: 0 for part in parts}
    for part in parts:
        counts[part.name] += 1
    for part in parts:
        if counts[part.name] == 1:
            result.append(part)
            continue
        seen[part.name] = seen.get(part.name, 0) + 1
        result.append(dataclasses.replace(part, name=f"{part.name} {seen[part.name]}"))
    return result


def _titles(payload: bytes) -> dict[str, str]:
    """Namen, die der Slicer notiert hat, nach Objekt und nach Part-ID.

    Eine Part-ID ist das, was eine Komponente benennt — das Blatt bekommt also
    den Namen der Datei, die es einmal war, und das ist der Name, den jemand
    gewählt hat.
    """
    try:
        config = ET.fromstring(payload)
    except ET.ParseError:
        return {}

    found: dict[str, str] = {}
    for node in [*config.findall(".//object"), *config.findall(".//part")]:
        identifier = node.get("id")
        if identifier is None:
            continue
        for entry in node.findall("metadata"):
            if entry.get("key") == "name" and entry.get("value"):
                found[identifier] = _without_suffix(str(entry.get("value")))
                break
    return found


def _without_suffix(name: str) -> str:
    """``Wasserfall_4_TPU-Liner.stl`` ist ein Teil namens
    Wasserfall_4_TPU-Liner.
    """
    lowered = name.lower()
    for suffix in NAME_SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _parts_of(
    identifier: str,
    path: str,
    transform: np.ndarray,
    catalog: dict[str, dict[str, ET.Element]],
    materials: dict[str, dict[str, list[tuple[str, tuple[float, float, float]]]]],
    titles: dict[str, str],
    inherited: str,
    depth: int,
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> list[_Leaf]:
    """Die Meshes, die ein Objekt beiträgt, mit den Transformationen darüber
    angewandt.
    """
    if depth > MAX_DEPTH:
        _log.warning("3MF component nesting deeper than %d — stopped", MAX_DEPTH)
        return []
    if (path, identifier) in seen:
        _log.warning("3MF object %s in %s refers back to itself — stopped", identifier, path)
        return []

    entry = catalog.get(path, {}).get(identifier)
    if entry is None:
        # Eine Komponente, die ein Objekt benennt, das niemand notiert hat. Die
        # ganze Datei darüber still fallenzulassen wäre schlimmer, als den
        # einen Körper fallenzulassen.
        _log.info("3MF references object %s in %s, which is not there", identifier, path)
        return []

    name = (
        entry.get("name")
        or titles.get(identifier)
        or inherited
        or f"{_('Körper').translate()} {identifier}"
    )
    mesh_node = entry.find(f"{{{CORE_NAMESPACE}}}mesh")
    if mesh_node is not None:
        return [
            _Leaf(
                name=name,
                node=mesh_node,
                transform=transform,
                palette=materials.get(path, {}),
            )
        ]

    found: list[_Leaf] = []
    for component in entry.findall(f"{{{CORE_NAMESPACE}}}components/{{{CORE_NAMESPACE}}}component"):
        child = component.get("objectid")
        if child is None:
            continue
        # Der Pfad einer Komponente ist der Ort, an dem *ihr* Objekt lebt. Ohne
        # diese Zeile löst jede Komponente einer externen Datei zur ganzen Datei
        # auf — und das ist die Vervielfachung, für die es diesen Leser gibt.
        stated = component.get(f"{{{PRODUCTION_NAMESPACE}}}path")
        child_path = _inside(stated) if stated else path
        found.extend(
            _parts_of(
                child,
                child_path,
                transform @ _matrix(component.get("transform")),
                catalog,
                materials,
                titles,
                name,
                depth + 1,
                seen | {(path, identifier)},
            )
        )
    return found


def _inside(path: str | None) -> str:
    """Ein Teilpfad, wie der Container ihn schreibt.

    Das Format schreibt sie absolut — ``/3D/Objects/lid.model`` — und ein ZIP
    hat keine Wurzel: der führende Schrägstrich muss also weg, sonst geht jede
    Suche daneben.
    """
    return (path or MODEL_PATH).lstrip("/")


def _objects_in(model: ET.Element) -> dict[str, ET.Element]:
    """Jedes Objekt einer Modelldatei, nach ID."""
    found: dict[str, ET.Element] = {}
    for entry in model.findall(f".//{{{CORE_NAMESPACE}}}object"):
        identifier = entry.get("id")
        if identifier is not None:
            found[identifier] = entry
    return found


def _mesh_from(node: ET.Element) -> MeshData | None:
    """Die Dreiecke eines ``mesh``-Knotens."""
    vertices = node.find(f"{{{CORE_NAMESPACE}}}vertices")
    triangles = node.find(f"{{{CORE_NAMESPACE}}}triangles")
    if vertices is None or triangles is None or not len(triangles):
        return None
    try:
        points, faces = _numbers_from(vertices, triangles)
    except (TypeError, ValueError) as problem:
        _log.info("3MF mesh has unreadable coordinates: %s", problem)
        return None
    # Ein Körper, der hier ausfällt, verschwindet aus der Baugruppe — und das
    # ist genau die Sorte Verlust, die niemandem auffällt: siebzehn Teile
    # kommen als sechzehn zurück, und keine Zeile sagt warum. Er wird deshalb
    # nicht bloß übersprungen, sondern benannt.
    if not len(points) or not len(faces):
        _log.warning("3MF mesh is empty: %d point(s), %d triangle(s)", len(points), len(faces))
        return None
    if int(faces.max()) >= len(points):
        _log.warning(
            "3MF mesh points past its own vertices: highest index %d of %d point(s)",
            int(faces.max()),
            len(points),
        )
        return None
    return MeshData.of(trimesh.Trimesh(vertices=points, faces=faces, process=False))


def _numbers_from(vertices: ET.Element, triangles: ET.Element) -> tuple[np.ndarray, np.ndarray]:
    """Punkte und Dreiecke als Zahlenfelder — und einmal wiederholt, wenn nicht.

    Dieselbe Wunde wie bei :func:`app.core.geom.mesh.on_surface`, an der
    zweiten Stelle: Wer diese Datei dreißigmal im selben Prozess liest, bekommt
    sporadisch ``OverflowError``, ``SystemError`` oder — am hässlichsten — ein
    ``ValueError`` über eine Zeichenkette, die eine völlig gültige Zahl ist.
    Gemessen und eingegrenzt: es liegt weder am XML-Leser (``lxml`` verhält
    sich gleich) noch an der Art der Umwandlung, sondern am geladenen
    ``rtree`` — ohne es fällt die Rate von sechs auf eins von dreißig, mit
    seiner Version 1.4 stirbt der Prozess ganz.

    Ein zweiter Anlauf trägt fast immer. Er ist kein Verschlucken: was zweimal
    scheitert, fliegt weiter, und der Aufrufer verwirft den Körper dann mit
    einer Zeile im Protokoll statt schweigend.

    Seit dem 24.08.2026 ruft die Anwendung ``rtree`` nicht mehr auf
    (:func:`app.core.geom.mesh.on_surface` fragt einen eigenen Baum,
    ``ingest.outline`` verschachtelt über shapely) — die Rate sollte damit auf
    das Eins-von-Dreißig ohne ``rtree`` fallen. Der zweite Anlauf bleibt
    trotzdem: Er kostet nichts, solange nichts scheitert, und die Messung,
    dass ohne ``rtree`` *gar* nichts scheitert, gibt es nicht.
    """
    try:
        return _read_numbers(vertices, triangles)
    except (OverflowError, SystemError, ValueError) as stumble:
        _log.warning("3MF numbers came back damaged, reading them again: %s", stumble)
        return _read_numbers(vertices, triangles)


def _read_numbers(vertices: ET.Element, triangles: ET.Element) -> tuple[np.ndarray, np.ndarray]:
    points = np.array(
        [(entry.get("x"), entry.get("y"), entry.get("z")) for entry in vertices],
        dtype=np.float64,
    )
    faces = np.array(
        [(entry.get("v1"), entry.get("v2"), entry.get("v3")) for entry in triangles],
        dtype=np.int64,
    )
    return points, faces


def _groups_of(
    node: ET.Element, materials: dict[str, list[tuple[str, tuple[float, float, float]]]]
) -> Groups | None:
    """Die Farbgruppen eines Meshes — seine eigenen, nicht die der
    Datei (§20).

    Je Mesh statt je Datei, und genau das konnte der ältere Leser nicht: er gab
    auf, sobald eine 3MF mehr als einen Körper hielt — eine zweifarbige
    Baugruppe verlor also jede Farbe, die sie hatte.
    """
    if not materials:
        return None
    group, names = next(iter(materials.items()))
    triangles = node.findall(f"{{{CORE_NAMESPACE}}}triangles/{{{CORE_NAMESPACE}}}triangle")
    if not triangles:
        return None

    default = 0
    assignment = tuple(
        int(entry.get("p1") or default) if (entry.get("pid") or group) == group else default
        for entry in triangles
    )
    used = sorted(set(assignment))
    if len(used) < 2:
        return None  # ein Material für den ganzen Körper ist keine Gruppe, die sich lohnt
    order = {position: index for index, position in enumerate(used)}
    return Groups(
        slots=tuple(order[entry] for entry in assignment),
        materials=tuple(
            MaterialSlot(index=index, name=names[position][0], colour=names[position][1])
            for index, position in enumerate(used)
            if position < len(names)
        ),
    )


def _matrix(text: str | None) -> np.ndarray:
    """Eine 3MF-Transformation — zwölf Zahlen, spaltenweise 4x3 — als
    4x4-Matrix.
    """
    if not text:
        return np.eye(4)
    parts = text.replace(",", " ").split()
    if len(parts) != 12:
        return np.eye(4)
    try:
        values = [float(entry) for entry in parts]
    except ValueError:
        return np.eye(4)
    matrix = np.eye(4)
    matrix[:3, :3] = np.array(values[:9], dtype=float).reshape(3, 3).T
    matrix[:3, 3] = values[9:]
    return matrix


def _materials_in(model: ET.Element) -> dict[str, list[tuple[str, tuple[float, float, float]]]]:
    """Jede ``basematerials``-Gruppe, nach ID, in Dokumentreihenfolge."""
    found: dict[str, list[tuple[str, tuple[float, float, float]]]] = {}
    for group in model.findall(f".//{{{CORE_NAMESPACE}}}basematerials"):
        identifier = group.get("id")
        if identifier is None:
            continue
        found[identifier] = [
            (entry.get("name") or "", _rgb(entry.get("displaycolor")))
            for entry in group.findall(f"{{{CORE_NAMESPACE}}}base")
        ]
    return {key: value for key, value in found.items() if value}


def _rgb(text: str | None) -> tuple[float, float, float]:
    """``#RRGGBB`` oder ``#RRGGBBAA`` als drei Zahlen; Alpha druckt nicht."""
    digits = (text or "").lstrip("#")
    if len(digits) not in (6, 8):
        return DEFAULT_COLOUR
    try:
        values = [int(digits[start : start + 2], 16) / 255.0 for start in (0, 2, 4)]
    except ValueError:
        return DEFAULT_COLOUR
    return (values[0], values[1], values[2])


def _slots_for(mesh: MeshData, slots: list[MaterialSlot] | None) -> list[MaterialSlot]:
    """Jeder Slot, den das Mesh wirklich benutzt, mit Namen und Farbe."""
    from app.core.geom.attributes import used_slots

    known = {entry.index: entry for entry in (slots or [])}
    return [
        known.get(index, MaterialSlot(index=index, name=f"Slot {index}"))
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
    """
    geometry = ET.SubElement(parent, "mesh")
    vertices = ET.SubElement(geometry, "vertices")
    for point in mesh.raw.vertices:
        ET.SubElement(
            vertices,
            "vertex",
            {"x": f"{point[0]:.5f}", "y": f"{point[1]:.5f}", "z": f"{point[2]:.5f}"},
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
    for entry in materials:
        ET.SubElement(
            group,
            "base",
            {"name": entry.name or f"Slot {entry.index}", "displaycolor": _colour(entry)},
        )

    # Wohin ein objekteigener Slot in der gemeinsamen Liste zeigt. Ohne diese
    # Übersetzung trüge Teil zwei die Farben von Teil eins.
    positions = {(entry.name, entry.colour): index for index, entry in enumerate(materials)}

    build = ET.SubElement(root, "build")
    for number, part in enumerate(parts, start=2):
        order = {
            slot.index: positions.get((slot.name, slot.colour), 0)
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
            {"name": entry.name or f"Slot {entry.index}", "displaycolor": _colour(entry)},
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
