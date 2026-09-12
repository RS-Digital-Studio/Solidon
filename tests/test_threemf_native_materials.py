"""Native Slicer-Werkzeuge sind eine andere Zuordnung als Standard-3MF-Farben."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.export import threemf as writer
from app.core.geom.mesh import MeshData
from app.core.ingest import threemf as reader
from app.core.types import MaterialSlot
from app.i18n import TranslatableText


def _parts() -> list[writer.AssemblyPart]:
    return [
        writer.AssemblyPart(
            MeshData(trimesh.creation.box(), (0,) * 12),
            str(index),
            (MaterialSlot(0, name, colour=colour),),
        )
        for index, (name, colour) in enumerate(
            [("Rot", (1.0, 0.0, 0.0)), ("Blau", (0.0, 0.0, 1.0))]
        )
    ]


def test_export_object_extruders_follow_global_slot_order_and_keep_gaps() -> None:
    parts = _parts()
    payload = writer.write_assembly(parts[1:], across=parts, prusa_config={"layer_height": "0.2"})
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        for file in (writer.SETTINGS_PATH, writer.PRUSA_MODEL_CONFIG_PATH):
            config = ET.fromstring(archive.read(file))
            assert config.find("object/metadata[@key='extruder']").get("value") == "2"


def test_export_face_paint_uses_native_whole_triangle_states() -> None:
    slots = tuple(MaterialSlot(i, f"F{i}") for i in range(4))
    part = writer.AssemblyPart(MeshData(trimesh.creation.box(), tuple(range(4)) * 3), slots=slots)
    with zipfile.ZipFile(BytesIO(writer.write_assembly([part]))) as archive:
        model = ET.fromstring(archive.read(writer.MODEL_PATH))
        faces = model.findall(f".//{{{writer.CORE_NAMESPACE}}}triangle")
        assert [f.get("paint_color") for f in faces[:4]] == ["4", "8", "0C", "1C"]
        assert [
            f.get("{http://schemas.slic3r.org/3mf/2017/06}mmu_segmentation") for f in faces[:4]
        ] == ["4", "8", "0C", "1C"]


def _native(*, paint: str = "", prusa: bool = False, part_override: bool = True) -> bytes:
    ns = reader.CORE_NAMESPACE
    body = trimesh.creation.box()
    root = ET.Element("model", {"xmlns": ns, "unit": "millimeter"})
    resources = ET.SubElement(root, "resources")
    parent = ET.SubElement(resources, "object", {"id": "20"})
    components = ET.SubElement(parent, "components")
    ET.SubElement(components, "component", {"objectid": "2"})
    obj = ET.SubElement(resources, "object", {"id": "2", "type": "model"})
    mesh = ET.SubElement(obj, "mesh")
    vertices = ET.SubElement(mesh, "vertices")
    for x, y, z in body.vertices:
        ET.SubElement(vertices, "vertex", {"x": str(x), "y": str(y), "z": str(z)})
    triangles = ET.SubElement(mesh, "triangles")
    for index, (a, b, c) in enumerate(body.faces):
        attrs = {"v1": str(a), "v2": str(b), "v3": str(c)}
        if paint and index < 6:
            attrs[
                "{http://schemas.slic3r.org/3mf/2017/06}mmu_segmentation"
                if prusa
                else "paint_color"
            ] = paint
        ET.SubElement(triangles, "triangle", attrs)
    ET.SubElement(ET.SubElement(root, "build"), "item", {"objectid": "20"})
    metadata = '<config><object id="20"><metadata key="extruder" value="1"/>'
    if part_override:
        metadata += '<part id="2" subtype="normal_part"><metadata key="extruder" value="3"/></part>'
    metadata += "</object></config>"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(writer.MODEL_PATH, ET.tostring(root))
        archive.writestr(writer.SETTINGS_PATH, metadata)
        if prusa:
            archive.writestr(
                writer.PRUSA_CONFIG_PATH, "; config\n; filament_colour = #FF0000;#0000FF;#00FF00\n"
            )
        else:
            archive.writestr(
                writer.PROJECT_SETTINGS_PATH,
                json.dumps(
                    {
                        "filament_colour": ["#FF0000", "#0000FF", "#00FF00"],
                        "filament_type": ["PLA", "PETG", "TPU"],
                    }
                ),
            )
    return buffer.getvalue()


def test_native_part_tool_overrides_parent_and_keeps_its_palette() -> None:
    part = reader.read_objects(_native())[0]
    assert part.mesh.slots == (0,) * 12
    assert len(part.slots) == 1
    assert part.slots[0].colour == (0.0, 1.0, 0.0)
    assert part.slots[0].material_type == "TPU"


@pytest.mark.parametrize("prusa", [False, True])
def test_native_face_paint_overrides_object_tool(prusa: bool) -> None:
    part = reader.read_objects(_native(paint="8", prusa=prusa, part_override=False))[0]
    assert part.mesh.slots == (1,) * 6 + (0,) * 6
    assert [slot.colour for slot in part.slots] == [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]


@pytest.mark.parametrize(
    ("paint", "reason"),
    [
        ("841", "Teilflächenbemalung oder nicht unterstützte Flächenzuordnung"),
        ("ZZ", "Ungültige Flächenbemalung"),
        ("9C", "Werkzeugnummer außerhalb der Filamentpalette"),
    ],
)
def test_unrepresentable_native_paint_stops_before_losing_colours(paint: str, reason: str) -> None:
    with pytest.raises(ValidationError) as caught:
        reader.read_objects(_native(paint=paint))
    assert caught.value.constraint == "unsupported_material_semantics"
    assert caught.value.suggestions
    detail = caught.value.values["reason"]
    assert isinstance(detail, TranslatableText), "eigene Fehlergründe bleiben übersetzbar"
    assert detail.translate("de") == reason


def _changed(payload: bytes, replacements: dict[str, bytes]) -> bytes:
    """Unabhängige native Metadaten in dieselbe Testgeometrie einsetzen."""
    buffer = BytesIO()
    with zipfile.ZipFile(BytesIO(payload)) as source, zipfile.ZipFile(buffer, "w") as target:
        for path in source.namelist():
            target.writestr(path, replacements.pop(path, source.read(path)))
        for path, content in replacements.items():
            target.writestr(path, content)
    return buffer.getvalue()


def test_reused_part_ids_keep_each_parent_object_tool() -> None:
    payload = _native()
    with zipfile.ZipFile(BytesIO(payload)) as source:
        model = ET.fromstring(source.read(writer.MODEL_PATH))
    ns = reader.CORE_NAMESPACE
    parent = ET.SubElement(model.find(f"{{{ns}}}resources"), f"{{{ns}}}object", {"id": "21"})
    components = ET.SubElement(parent, f"{{{ns}}}components")
    ET.SubElement(components, f"{{{ns}}}component", {"objectid": "2"})
    ET.SubElement(model.find(f"{{{ns}}}build"), f"{{{ns}}}item", {"objectid": "21"})
    config = (
        b'<config><object id="20"><part id="2"><metadata key="extruder" value="2"/>'
        b'</part></object><object id="21"><part id="2">'
        b'<metadata key="extruder" value="3"/></part></object></config>'
    )
    parts = reader.read_objects(
        _changed(
            payload,
            {
                writer.MODEL_PATH: ET.tostring(model),
                writer.SETTINGS_PATH: config,
            },
        )
    )
    assert [part.slots[0].colour for part in parts] == [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0)]


def test_prusa_volume_ranges_and_single_mesh_reader_keep_native_tools() -> None:
    config = (
        b'<config><object id="2"><volume firstid="0" lastid="5">'
        b'<metadata key="extruder" value="2"/></volume><volume firstid="6" lastid="11">'
        b'<metadata key="extruder" value="3"/></volume></object></config>'
    )
    payload = _changed(
        _native(prusa=True, part_override=False),
        {
            writer.PRUSA_MODEL_CONFIG_PATH: config,
        },
    )
    part = reader.read_objects(payload)[0]
    assert part.mesh.slots == (0,) * 6 + (1,) * 6
    groups = reader.read(payload, 12)
    assert groups is not None
    assert groups.slots == part.mesh.slots
    assert [slot.colour for slot in groups.materials] == [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0)]


@pytest.mark.parametrize(
    ("code", "tool"),
    [
        ("0", None),
        ("4", 0),
        ("8", 1),
        ("0C", 2),
        ("EC", 16),
        ("0FC", 17),
        ("7FC", 24),
        ("9FC", 26),
        ("EFC", 31),
    ],
)
def test_extended_native_leaf_codes(code: str, tool: int | None) -> None:
    assert reader._paint_tool(code) == tool
    if tool is not None:
        assert writer._paint_code(tool) == code


@pytest.mark.parametrize("code", ["FC", "FFC", "09FC", "18C", "84C1", "8FC1"])
def test_incomplete_or_split_native_leaf_is_not_a_whole_face(code: str) -> None:
    with pytest.raises(ValidationError):
        reader._paint_tool(code)


def test_real_extended_leaf_keeps_count_geometry_and_colour() -> None:
    """9FC aus der Taschentuchbox bedeutet Farbe 27, keine Dreiecksteilung."""
    colours = ["#F2F2F2"] * 27
    colours[26] = "#F07316"
    payload = _changed(
        _native(paint="9FC", part_override=False),
        {writer.PROJECT_SETTINGS_PATH: json.dumps({"filament_colour": colours}).encode()},
    )
    parts = reader.read_objects(payload)
    assert reader.count_objects(payload) == len(parts) == 1
    assert parts[0].mesh.triangle_count == 12
    assert parts[0].mesh.slots == (1,) * 6 + (0,) * 6
    assert parts[0].slots[1].colour == pytest.approx((240 / 255, 115 / 255, 22 / 255))
    groups = reader.read(payload, 12)
    assert groups is not None
    assert groups.slots == parts[0].mesh.slots


@pytest.mark.parametrize("tool", [-1, 32])
def test_native_writer_rejects_unrepresentable_colour_number(tool: int) -> None:
    with pytest.raises(ValidationError) as caught:
        writer._paint_code(tool)
    assert caught.value.suggestions
