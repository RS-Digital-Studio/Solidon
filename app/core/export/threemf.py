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
import zipfile
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
class Groups:
    """Die Farbgruppen, die eine 3MF-Datei trägt (§20, Import)."""

    slots: tuple[int, ...]
    """One slot index per triangle, in the order the file lists them."""
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
        points = np.array(
            [(entry.get("x"), entry.get("y"), entry.get("z")) for entry in vertices],
            dtype=np.float64,
        )
        faces = np.array(
            [(entry.get("v1"), entry.get("v2"), entry.get("v3")) for entry in triangles],
            dtype=np.int64,
        )
    except (TypeError, ValueError) as problem:
        _log.info("3MF mesh has unreadable coordinates: %s", problem)
        return None
    if not len(points) or not len(faces) or int(faces.max()) >= len(points):
        return None
    return MeshData.of(trimesh.Trimesh(vertices=points, faces=faces, process=False))


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
    geometry = ET.SubElement(body, "mesh")
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
