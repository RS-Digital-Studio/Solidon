"""Jedes angebotene Eingabeformat mit echter Geometrie (§17.1, §20, §30).

Die Formate standen bisher als Endungen in Dateidialog und Ablagefeld, aber
nur STL und 3MF liefen gemeinsam durch einen vollständigen Satz. Diese Datei
hält die Zusage von beiden Seiten: Jede Endung hat eine Probe, und jede Probe
steht in der einen Liste, die auch die Oberfläche liest.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import numpy as np
import pytest
import trimesh
from PIL import Image

from app.core.brep import edit, step
from app.core.brep.kernel import available as brep_available
from app.core.errors import ValidationError
from app.core.export import threemf
from app.core.geom.mesh import MeshData
from app.core.geom.texture import face_colours
from app.core.ingest import loader
from app.core.ingest.loader import READABLE_SUFFIXES, normalise, read_local_payload, read_model
from app.core.ingest.outline import OUTLINE_SUFFIXES, extrude
from app.core.ingest.plan import MODEL_SUFFIXES, import_plan
from app.core.scene import History, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Profile, Source


def _box() -> trimesh.Trimesh:
    """Ein Körper mit geschlossenen, von Hand prüfbaren Maßen."""
    return trimesh.creation.box(extents=(20.0, 16.0, 12.0))


def _bytes(value: bytes | str) -> bytes:
    return value if isinstance(value, bytes) else value.encode("utf-8")


def _gltf_bundle() -> dict[str, bytes]:
    return trimesh.exchange.gltf.export_gltf(trimesh.Scene(_box()), merge_buffers=True)


def _self_contained_gltf() -> bytes:
    bundle = _gltf_bundle()
    document = json.loads(bundle["model.gltf"])
    for entry in document["buffers"]:
        data = bundle[entry["uri"]]
        entry["uri"] = "data:application/octet-stream;base64," + base64.b64encode(data).decode(
            "ascii"
        )
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


def _mesh_payloads() -> dict[str, bytes]:
    body = _box()
    return {
        ".stl": _bytes(body.export(file_type="stl")),
        ".3mf": threemf.write(MeshData.of(body), name="Prüfkörper"),
        ".obj": _bytes(body.export(file_type="obj")),
        ".ply": _bytes(body.export(file_type="ply")),
        ".off": _bytes(body.export(file_type="off")),
        ".glb": _bytes(trimesh.Scene({"Prüfkörper": body}).export(file_type="glb")),
        ".gltf": _self_contained_gltf(),
    }


def test_every_readable_mesh_format_contains_the_same_body() -> None:
    payloads = _mesh_payloads()
    assert set(payloads) == set(READABLE_SUFFIXES), "eine angebotene Endung hat keine Probe"

    for suffix, payload in payloads.items():
        mesh = read_model(payload, suffix)
        assert mesh.triangle_count == 12, suffix
        assert mesh.bounds.size == pytest.approx((20.0, 16.0, 12.0)), suffix
        assert abs(mesh.volume) == pytest.approx(20.0 * 16.0 * 12.0), suffix


def _outline_payloads() -> dict[str, bytes]:
    svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">
    <path d="M0 0 H40 V20 H0 Z M10 5 H30 V15 H10 Z" fill-rule="evenodd"/>
    </svg>"""
    drawing = trimesh.load_path(io.BytesIO(svg), file_type="svg")
    return {".svg": svg, ".dxf": _bytes(drawing.export(file_type="dxf"))}


def test_every_outline_format_keeps_the_hole_and_height() -> None:
    payloads = _outline_payloads()
    assert set(payloads) == set(OUTLINE_SUFFIXES), "eine angebotene Zeichnung hat keine Probe"

    for suffix, payload in payloads.items():
        result = extrude(payload, suffix, height=3.0)
        assert result.mesh.bounds.size == pytest.approx((40.0, 20.0, 3.0)), suffix
        assert result.mesh.volume == pytest.approx((40.0 * 20.0 - 20.0 * 10.0) * 3.0), suffix
        assert result.mesh.is_watertight, suffix


@pytest.mark.parametrize("position", ["", 'x="0"', 'y="0"'])
def test_svg_rectangles_use_zero_for_missing_position(position: str) -> None:
    payload = (
        f'<svg xmlns="http://www.w3.org/2000/svg"><rect {position} width="20" height="10"/></svg>'
    ).encode()
    result = extrude(payload, ".svg", height=3.0)
    assert result.mesh.bounds.size == pytest.approx((20.0, 10.0, 3.0))
    assert result.mesh.volume == pytest.approx(600.0)
    assert result.mesh.is_watertight


def test_svg_defaults_preserve_transforms_and_an_explicit_position() -> None:
    payload = b"""<svg xmlns="http://www.w3.org/2000/svg">
    <g transform="translate(12, 15) scale(2, 3)">
      <rect x="4" width="20" height="10"/>
      <rect x="6" y="2" width="16" height="6"/>
    </g></svg>"""
    result = extrude(payload, ".svg", height=3.0)
    assert result.mesh.bounds.size == pytest.approx((40.0, 30.0, 3.0))
    assert result.mesh.volume == pytest.approx((1200.0 - 576.0) * 3.0)
    assert result.mesh.is_watertight


def test_svg_defaults_do_not_resolve_external_entities(tmp_path: Path) -> None:
    secret = tmp_path / "outside.txt"
    secret.write_text("20", encoding="utf-8")
    payload = (
        f'<!DOCTYPE svg [<!ENTITY outside SYSTEM "{secret.as_uri()}">]>'
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect width="&outside;" height="10"/></svg>'
    ).encode()
    with pytest.raises(ValidationError) as refused:
        extrude(payload, ".svg", height=3.0)
    assert refused.value.constraint == "unreadable"
    assert refused.value.suggestions


@pytest.mark.skipif(not brep_available(), reason="OpenCASCADE ist optional")
def test_both_step_endings_read_the_same_exact_body() -> None:
    solid = edit.box(20.0, 16.0, 12.0)
    payload = step.write(solid, "Prüfkörper")

    for suffix in step.SUFFIXES:
        assert step.is_step(suffix)
        restored = step.read(payload)
        assert restored.bounds.size == pytest.approx((20.0, 16.0, 12.0)), suffix
        assert restored.volume == pytest.approx(20.0 * 16.0 * 12.0), suffix


def test_the_one_format_list_is_exactly_what_the_decoders_cover() -> None:
    expected = (*READABLE_SUFFIXES, *step.SUFFIXES, *OUTLINE_SUFFIXES)
    assert tuple(dict.fromkeys(expected)) == MODEL_SUFFIXES


def _write_gltf_bundle(folder: Path) -> Path:
    bundle = _gltf_bundle()
    for name, payload in bundle.items():
        (folder / name).write_bytes(payload)
    return folder / "model.gltf"


def test_a_local_gltf_embeds_its_companion_file(tmp_path: Path) -> None:
    path = _write_gltf_bundle(tmp_path)

    payload = read_local_payload(path)
    for companion in tmp_path.glob("*.bin"):
        companion.unlink()

    assert b"data:application/octet-stream;base64," in payload
    mesh = read_model(payload, ".gltf")
    assert mesh.bounds.size == pytest.approx((20.0, 16.0, 12.0))


def test_a_missing_gltf_companion_is_a_useful_user_error(tmp_path: Path) -> None:
    path = _write_gltf_bundle(tmp_path)
    next(tmp_path.glob("*.bin")).unlink()

    with pytest.raises(ValidationError) as caught:
        read_local_payload(path)

    assert caught.value.constraint == "missing_file"
    assert "GLB" in str(caught.value.detail)
    assert caught.value.suggestions


def test_an_in_memory_gltf_never_leaks_the_parsers_type_error() -> None:
    external = _gltf_bundle()["model.gltf"]

    with pytest.raises(ValidationError) as caught:
        read_model(external, ".gltf")

    assert caught.value.constraint == "missing_file"
    assert "GLB" in str(caught.value.detail)


def test_a_gltf_cannot_embed_a_file_above_its_own_folder(tmp_path: Path) -> None:
    folder = tmp_path / "model"
    folder.mkdir()
    path = _write_gltf_bundle(folder)
    document = json.loads(path.read_bytes())
    document["buffers"][0]["uri"] = "../secret.bin"
    path.write_text(json.dumps(document), encoding="utf-8")
    (tmp_path / "secret.bin").write_bytes(b"not part of the model")

    with pytest.raises(ValidationError) as caught:
        read_local_payload(path)

    assert caught.value.constraint == "absolute_path"


def test_a_local_file_is_rejected_before_an_oversized_payload_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "oversized.stl"
    path.write_bytes(bytes(101))
    monkeypatch.setattr(loader, "MAX_FILE_BYTES", 100)

    def must_not_open(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("the file size must be rejected before reading")

    monkeypatch.setattr(Path, "open", must_not_open)

    with pytest.raises(ValidationError) as caught:
        read_local_payload(path)

    assert caught.value.constraint == "file_too_large"


def test_gltf_companions_are_rejected_before_base64_exceeds_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = {
        "asset": {"version": "2.0"},
        "buffers": [
            {"byteLength": 100, "uri": "first.bin"},
            {"byteLength": 100, "uri": "second.bin"},
        ],
    }
    path = tmp_path / "model.gltf"
    path.write_text(json.dumps(document), encoding="utf-8")
    (tmp_path / "first.bin").write_bytes(bytes(100))
    (tmp_path / "second.bin").write_bytes(bytes(100))
    monkeypatch.setattr(loader, "MAX_FILE_BYTES", len(path.read_bytes()) + 200)

    def must_not_encode(_payload: bytes) -> bytes:
        raise AssertionError("the projected size must be rejected before encoding")

    monkeypatch.setattr(loader.base64, "b64encode", must_not_encode)

    with pytest.raises(ValidationError) as caught:
        read_local_payload(path)

    assert caught.value.constraint == "file_too_large"
    assert caught.value.suggestions


def _pbr_glb() -> bytes:
    body = _box()
    span = np.ptp(body.vertices[:, :2], axis=0)
    uv = (body.vertices[:, :2] - body.vertices[:, :2].min(axis=0)) / span
    image = Image.new("RGB", (2, 2))
    image.putdata([(255, 0, 0), (0, 0, 255), (255, 0, 0), (0, 0, 255)])
    material = trimesh.visual.material.PBRMaterial(name="Rot und Blau", baseColorTexture=image)
    body.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
    return _bytes(trimesh.Scene({"Farbig": body}).export(file_type="glb"))


def test_a_gltf_pbr_texture_survives_import_and_normalisation() -> None:
    imported = read_model(_pbr_glb(), ".glb")
    result = normalise(imported, "mm")

    colours = face_colours(result.mesh.raw)
    assert colours is not None
    assert len(colours) == result.mesh.triangle_count
    assert len(np.unique(np.rint(colours * 255.0).astype(np.uint8), axis=0)) >= 2


def test_imported_colours_survive_the_evaluation_cache() -> None:
    imported = read_model(_pbr_glb(), ".glb")
    normalised = normalise(imported, "mm").mesh

    restored = MeshData.from_bytes(normalised.to_bytes())

    colours = face_colours(restored.raw)
    assert colours is not None
    assert len(np.unique(np.rint(colours * 255.0).astype(np.uint8), axis=0)) >= 2


def _evaluated_import(payload: bytes, suffix: str, profile: Profile, unit: str = "auto"):
    """Der gemeinsame Importplan und seine tatsächliche Operation."""
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/body{suffix}", sha256=""
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", f"body{suffix}", payload, unit=unit)
    assert not plan.asks_unit, "glTF states metres, unless the user overrides them"
    History(project.document).apply(plan.title, [plan.draft])

    def must_not_ask(*_args: object) -> str:
        raise AssertionError("glTF import must not guess its declared unit")

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=must_not_ask)
    assert result.complete, result.scene.report.findings
    return project, result.scene.objects["obj_1"].mesh


@pytest.mark.parametrize("suffix", [".glb", ".gltf"])
def test_new_gltf_imports_apply_metres_and_y_up_once(suffix: str, profile: Profile) -> None:
    body = trimesh.creation.box(extents=(0.02, 0.016, 0.012))
    node = np.array(
        [[0.0, -3.0, 0.0, 0.04], [2.0, 0.0, 0.0, 0.05], [0.0, 0.0, 4.0, 0.06], [0.0, 0.0, 0.0, 1.0]]
    )
    scene = trimesh.Scene()
    scene.add_geometry(body, transform=node)
    if suffix == ".glb":
        payload = _bytes(scene.export(file_type="glb"))
    else:
        bundle = trimesh.exchange.gltf.export_gltf(scene, merge_buffers=True)
        document = json.loads(bundle["model.gltf"])
        for entry in document["buffers"]:
            entry["uri"] = "data:application/octet-stream;base64," + base64.b64encode(
                bundle[entry["uri"]]
            ).decode("ascii")
        payload = json.dumps(document).encode()
    project, mesh = _evaluated_import(payload, suffix, profile)
    assert project.document.ops[0].params["coordinates"] == "gltf"
    assert mesh.bounds.size == pytest.approx((48.0, 48.0, 40.0))
    assert mesh.bounds.centre == pytest.approx((40.0, -60.0, 50.0))
    assert mesh.is_watertight


@pytest.mark.parametrize(("unit", "factor"), [("mm", 1.0), ("cm", 10.0), ("in", 25.4)])
def test_explicit_gltf_units_keep_precedence(unit: str, factor: float, profile: Profile) -> None:
    payload = _bytes(trimesh.Scene(_box()).export(file_type="glb"))
    project, mesh = _evaluated_import(payload, ".glb", profile, unit=unit)
    assert project.document.ops[0].params["unit"] == unit
    assert mesh.bounds.size == pytest.approx(np.array((20.0, 12.0, 16.0)) * factor)


def test_own_glb_export_round_trips_dimensions_and_upright(
    profile: Profile, tmp_path: Path
) -> None:
    from app.core.export.writer import _glb_bytes
    from app.core.scene.project import load, save

    body = _box()
    body.apply_translation((3.0, 7.0, 11.0))
    project, imported = _evaluated_import(_glb_bytes(MeshData.of(body), None), ".glb", profile)
    assert imported.bounds.size == pytest.approx((20.0, 16.0, 12.0))
    assert imported.bounds.centre == pytest.approx((3.0, 7.0, 11.0))
    assert imported.volume == pytest.approx(body.volume)
    save(project, tmp_path / "gltf.p3d")
    reopened = load(tmp_path / "gltf.p3d")
    assert reopened.document.ops[0].params["coordinates"] == "gltf"
    result = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert result.complete
    restored = result.scene.objects["obj_1"].mesh
    assert np.array_equal(restored.raw.vertices, imported.raw.vertices)
    assert np.array_equal(restored.raw.faces, imported.raw.faces)


def test_generated_glb_keeps_raw_axes_and_one_working_size(profile: Profile) -> None:
    from app.core.backends.mesh import ScriptedMeshBackend
    from app.core.generate import WORKING_SIZE_MM, from_text

    body = trimesh.creation.box(extents=(1.0, 2.0, 3.0))
    payload = _bytes(trimesh.Scene(body).export(file_type="glb"))
    project = new_project("centauri-carbon-2", "petg")
    from_text(project, ScriptedMeshBackend(fallback=payload, suffix=".glb"), "Quader")
    assert project.document.ops[0].params["coordinates"] == "legacy_raw"
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    mesh = next(iter(result.scene.objects.values())).mesh
    assert mesh.bounds.size == pytest.approx(np.array((1.0, 2.0, 3.0)) * WORKING_SIZE_MM / 3.0)


def test_v24_generator_glb_keeps_its_geometry_after_migration(profile: Profile) -> None:
    from app.core.scene.project import load

    project = load(Path(__file__).parent / "data/projects/generated_glb_v24.p3d")
    assert project.document.ops[0].params["coordinates"] == "legacy_raw"
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    mesh = next(iter(result.scene.objects.values())).mesh
    assert mesh.bounds.size == pytest.approx((100.0 / 3.0, 200.0 / 3.0, 100.0))
    # Vor der Umrechnung kommt dieselbe Rohgeometrie wie im alten Projekt.
    History(project.document).undo()
    raw_result = evaluate(project.document, profile, sources=ProjectSources(project))
    raw_mesh = next(iter(raw_result.scene.objects.values())).mesh
    old_raw = read_model(project.sources["src_1"], ".glb")
    assert np.array_equal(raw_mesh.raw.vertices, old_raw.raw.vertices)
    assert np.array_equal(raw_mesh.raw.faces, old_raw.raw.faces)
