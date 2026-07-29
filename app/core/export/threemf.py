"""3MF with colour groups (Bauplan §20, §29).

trimesh writes 3MF, but not the per-triangle material groups a multi-colour
print needs. So the container is written here: the format is a ZIP with one XML
inside, and the part that matters is fifteen lines of it.

The mapping is the one from §20: one material slot of the object becomes one
entry in a ``basematerials`` group, and every triangle carries the index of its
slot. That is what a slicer reads to know which filament a face belongs to.

Reading them back is here too, and for the same reason: trimesh parses the
geometry of a 3MF but hands back a uniform grey. A file exported from here and
opened again would lose exactly the thing this module was written for.

The geometry is read here as well now, and that was not the plan. A 3MF from a
slicer keeps its objects in separate files under ``3D/Objects/`` and references
them from the build — the production extension. trimesh resolves a component
that points into such a file to the *whole file* instead of to the one object it
names, so a file with seventeen parts in one object file came out seventeen times
over, every body stacked on a copy of itself. Measured on the model corpus: a
nozzle of two bodies and 290 120 triangles arrived as four bodies and 580 240,
with twice the volume — and so twice the material estimate and twice the print
time. That is not a speed problem, so it is not fixed with a faster parser but
with the right one.

Written by hand rather than with a library because there is no library that
does only this — and a 3MF writer that does everything else too would be a
dependency for fifteen lines.
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

#: Where a slicer writes the names of the parts. Not part of the format — the
#: standard has a ``name`` attribute and these files leave it empty — but it is
#: the only place "Wasserfall_4_TPU-Liner" is written down, and a scene of
#: bodies called "object 7" is a scene nobody can work in. Read if present,
#: shrugged off if not.
SETTINGS_PATH = "Metadata/model_settings.config"

#: Suffixes a slicer leaves in a part name because the part came from a file.
NAME_SUFFIXES = (".stl", ".3mf", ".obj", ".step", ".stp")

#: Stand-in for counting, where only the names matter.
_EMPTY = MeshData.of(trimesh.Trimesh())

#: Colour a slot gets that has none. Grey, so nobody mistakes it for a choice.
DEFAULT_COLOUR = (0.72, 0.72, 0.72)

#: How deep a component may reference other components. The format allows a
#: tree, and a file that nests this far is broken rather than clever.
#:
#: A depth limit alone is not enough against a cycle, which was worth measuring:
#: two objects referencing each other with two components each have 2^32 paths
#: through them, all of them 32 deep and none of them repeated — so the limit
#: holds and the import never returns. Five hundred bytes of file. What actually
#: stops it is refusing to enter an object that is already on the way there
#: (§32: a limit says something, it does not hang).
MAX_DEPTH = 32


def write(mesh: MeshData, slots: list[MaterialSlot] | None = None, name: str = "") -> bytes:
    """One body as a 3MF container, with one material per slot."""
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
    """The colour groups a 3MF file carries (§20, import)."""

    slots: tuple[int, ...]
    """One slot index per triangle, in the order the file lists them."""
    materials: tuple[MaterialSlot, ...]


def read(payload: bytes, faces: int) -> Groups | None:
    """Read the material groups back out of a 3MF, or ``None`` when it has none.

    Only a file with a single mesh object is read: with several of them the
    triangles are concatenated on the way in, and guessing the order they ended
    up in would be worse than saying nothing. ``faces`` is what the loaded body
    actually has — a mismatch means exactly that case.

    The slot numbers come out as 0..n-1. 3MF knows positions in a group, not our
    numbering, so a body whose only colour was slot 3 comes back as slot 0 with
    its name and colour intact.
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
        return None  # one material for the whole body is not a group worth keeping
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
    """One body of a 3MF build, with the place the file put it."""

    name: str
    mesh: MeshData
    slots: tuple[MaterialSlot, ...] = field(default_factory=tuple)


def read_objects(payload: bytes) -> list[Part]:
    """Every body the build places, each where the file puts it.

    An empty list means this is not a 3MF that can be read — the caller falls
    back to the general loader rather than being handed an exception for a file
    that another reader may well manage.

    One body per leaf mesh, not one per build item. A slicer packs an assembly
    as one item made of components, and those components *are* the separate
    parts: housing, lid, spout, liner. Handing them over as a single welded body
    would throw away exactly the division that makes them printable one at a
    time — and it is the division the project needs anyway, for its own material
    per body (§12) and its own plate (§25).
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
    """How many bodies :func:`read_objects` would hand back.

    The stack hands out object ids before anything is computed (§11), so the
    count has to be known before the geometry is. It walks the same tree without
    turning a single triangle into a number — the coordinates are what costs, not
    finding out that they are there.
    """
    return len(_numbered([Part(name=leaf.name, mesh=_EMPTY) for leaf in _leaves(payload)]))


@dataclass(frozen=True, slots=True)
class _Leaf:
    """One mesh the build reaches, and everything known about it on the way."""

    name: str
    node: ET.Element
    transform: np.ndarray
    palette: dict[str, list[tuple[str, tuple[float, float, float]]]]


def _leaves(payload: bytes) -> list[_Leaf]:
    """Walk the build and collect every mesh it reaches, in order."""
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
    """Tell apart bodies that came out with the same name.

    Seventeen parts of one object file share whatever the object was called, and
    an object tree with seventeen identical entries is a list, not a tree.
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
    """Names the slicer wrote down, by object and by part id.

    A part id is what a component names, so the leaf gets the name of the file
    it once was — which is the name somebody chose.
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
    """``Wasserfall_4_TPU-Liner.stl`` is a part called Wasserfall_4_TPU-Liner."""
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
    """The meshes one object contributes, with the transforms above it applied."""
    if depth > MAX_DEPTH:
        _log.warning("3MF component nesting deeper than %d — stopped", MAX_DEPTH)
        return []
    if (path, identifier) in seen:
        _log.warning("3MF object %s in %s refers back to itself — stopped", identifier, path)
        return []

    entry = catalog.get(path, {}).get(identifier)
    if entry is None:
        # A component that names an object nobody wrote down. Silently dropping
        # the whole file over it would be worse than dropping the one body.
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
        # The path of a component is where *its* object lives. Without this line
        # every component of an external file resolves to the whole file, which
        # is the multiplication this reader exists for.
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
    """A part path as the container spells it.

    The format writes them absolute — ``/3D/Objects/lid.model`` — and a ZIP has
    no root, so the leading slash has to go or every lookup misses.
    """
    return (path or MODEL_PATH).lstrip("/")


def _objects_in(model: ET.Element) -> dict[str, ET.Element]:
    """Every object of one model file, by id."""
    found: dict[str, ET.Element] = {}
    for entry in model.findall(f".//{{{CORE_NAMESPACE}}}object"):
        identifier = entry.get("id")
        if identifier is not None:
            found[identifier] = entry
    return found


def _mesh_from(node: ET.Element) -> MeshData | None:
    """The triangles of one ``mesh`` node."""
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
    """The colour groups of one mesh — its own, not the file's (§20).

    Per mesh rather than per file, which is what the older reader could not do:
    it gave up as soon as a 3MF held more than one body, so a two-colour
    assembly lost every colour it had.
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
        return None  # one material for the whole body is not a group worth keeping
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
    """A 3MF transform — twelve numbers, column-major 4x3 — as a 4x4 matrix."""
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
    """Every ``basematerials`` group, by id, in document order."""
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
    """``#RRGGBB`` or ``#RRGGBBAA`` as three numbers; alpha does not print."""
    digits = (text or "").lstrip("#")
    if len(digits) not in (6, 8):
        return DEFAULT_COLOUR
    try:
        values = [int(digits[start : start + 2], 16) / 255.0 for start in (0, 2, 4)]
    except ValueError:
        return DEFAULT_COLOUR
    return (values[0], values[1], values[2])


def _slots_for(mesh: MeshData, slots: list[MaterialSlot] | None) -> list[MaterialSlot]:
    """Every slot the mesh actually uses, with a name and a colour."""
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
