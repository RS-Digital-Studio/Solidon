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
from app.core.geom.mesh import READABLE_SUFFIXES, MeshData, read_mesh
from app.core.geom.texture import face_colours
from app.core.ingest import loader
from app.core.ingest.loader import normalise, read_local_payload
from app.core.ingest.outline import OUTLINE_SUFFIXES, extrude
from app.core.ingest.plan import MODEL_SUFFIXES


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
        mesh = read_mesh(payload, suffix)
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
    mesh = read_mesh(payload, ".gltf")
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
        read_mesh(external, ".gltf")

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
    imported = read_mesh(_pbr_glb(), ".glb")
    result = normalise(imported, "mm")

    colours = face_colours(result.mesh.raw)
    assert colours is not None
    assert len(colours) == result.mesh.triangle_count
    assert len(np.unique(np.rint(colours * 255.0).astype(np.uint8), axis=0)) >= 2


def test_imported_colours_survive_the_evaluation_cache() -> None:
    imported = read_mesh(_pbr_glb(), ".glb")
    normalised = normalise(imported, "mm").mesh

    restored = MeshData.from_bytes(normalised.to_bytes())

    colours = face_colours(restored.raw)
    assert colours is not None
    assert len(np.unique(np.rint(colours * 255.0).astype(np.uint8), axis=0)) >= 2
