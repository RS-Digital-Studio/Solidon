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

Written by hand rather than with a library because there is no library that
does only this — and a 3MF writer that does everything else too would be a
dependency for fifteen lines.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from io import BytesIO
from xml.etree import ElementTree as ET

from app.branding import APP_NAME, APP_VERSION
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import MaterialSlot

_log = get_logger(__name__)

CORE_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
MODEL_RELATIONSHIP = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"

MODEL_PATH = "3D/3dmodel.model"

#: Colour a slot gets that has none. Grey, so nobody mistakes it for a choice.
DEFAULT_COLOUR = (0.72, 0.72, 0.72)


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
