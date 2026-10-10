"""Dichtbausteine haben reale Auswahlflächen und einen gemeinsamen Exportweg."""

import numpy as np
import pytest

from app.core.knowledge.parts import seals
from app.core.knowledge.parts.registry import PARTS
from app.core.knowledge.parts.scad import to_scad
from app.core.types import Feature


@pytest.mark.parametrize("name", ["seal_groove", "seal_gasket"])
def test_seal_part_has_one_closed_body_and_geometrically_bound_feature_faces(name):
    spec = PARTS.get(name)
    built = spec.fn(spec.params())
    assert built.mesh.is_watertight and built.mesh.component_count == 1
    assert set(spec.features) <= set(built.features)
    for feature in built.features.values():
        assert isinstance(feature, Feature)
        assert feature.provenance == "generated" and feature.face_indices
        selected = built.mesh.raw.triangles[list(feature.face_indices)]
        assert np.isfinite(selected).all()
        assert feature.params["area"] > 0
        if feature.kind == "face":
            assert len(feature.surface_patches) == 1
            surface = feature.surface_patches[0]
            assert surface.kind == "plane" and surface.source == "facets"
            assert surface.face_indices == feature.face_indices
            distance = (selected - surface.params["centre"]) @ np.asarray(surface.params["axis"])
            assert distance == pytest.approx(0.0, abs=1e-10)
    exported = to_scad(spec)
    assert "polyhedron(" in exported and f"{name}();" in exported


def test_groove_part_starts_at_the_clicked_mouth_and_extends_down():
    from app.core.geom.boolean import BOOLEAN_OVERLAP

    built = seals.seal_groove(seals.GrooveParams(depth=4))
    assert built.mesh.bounds.minimum[2] == pytest.approx(-4)
    # Wie jedes abtragende Werkzeug ein Hundertstel über die Mündung hinaus (§39).
    assert built.mesh.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP)
    floor = built.features["groove_floor"]
    assert built.mesh.raw.triangles[list(floor.face_indices)][:, :, 2] == pytest.approx(-4)


@pytest.mark.parametrize("section", ["rectangle", "round"])
def test_separate_gasket_stands_on_its_base_and_does_not_claim_a_flat_round_contact(section):
    built = seals.seal_gasket(seals.GasketParams(height=3, width=4, section=section))
    assert built.mesh.bounds.minimum[2] == pytest.approx(0)
    assert built.mesh.bounds.maximum[2] == pytest.approx(3)
    assert built.features["gasket_contact"].kind == (
        "face" if section == "rectangle" else "curved_face"
    )
    assert built.features["gasket_bottom"].kind == (
        "face" if section == "rectangle" else "curved_face"
    )
    if section == "round":
        assert not built.features["gasket_contact"].surface_patches
        assert not built.features["gasket_bottom"].surface_patches


def test_a_flat_seal_face_has_its_axis_normal_whichever_triangle_comes_first():
    """Die Normale einer ebenen Dichtfläche hängt nicht an der Dreiecksfolge.

    Die Vernetzung des exakten Körpers ordnet ihre Dreiecke auf macOS Intel
    anders; ``trimesh`` normiert über den Kehrwert der Länge, und je nach
    erstem Dreieck kam ``-0.9999999999999999`` oder ``-0.0`` heraus.
    """
    import math

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.sketch import shapes as sketch_shapes
    from app.core.sketch.serialize import sketch_to_text

    path = sketch_to_text(sketch_shapes.rectangle(20.0, 12.0))
    built = seals.seal_gasket(seals.GasketParams(path_sketch=path, width=2.6, height=2.4))
    raw = built.mesh.raw
    for name, sign in (("gasket_contact", 1.0), ("gasket_bottom", -1.0)):
        indices = built.features[name].face_indices
        uneven = [index for index in indices if raw.face_normals[index][2] != sign]
        # Ohne ein solches Dreieck prüfte der Test nichts.
        assert uneven
        for first in uneven:
            order = [first, *(index for index in range(len(raw.faces)) if index != first)]
            mesh = MeshData.of(trimesh.Trimesh(raw.vertices, raw.faces[order], process=False))
            normal = seals.seal_features(mesh, gasket=True)[name].params["normal"]
            assert normal == (0.0, 0.0, sign)
            assert all(math.copysign(1.0, value) == 1.0 for value in normal[:2])


def test_part_dimensions_rebuild_the_actual_gasket_cross_section():
    small = seals.seal_gasket(seals.GasketParams(height=2, width=2))
    large = seals.seal_gasket(seals.GasketParams(height=4, width=3))
    assert large.mesh.bounds.size[2] == pytest.approx(2 * small.mesh.bounds.size[2])
    assert large.mesh.volume == pytest.approx(3 * small.mesh.volume, rel=0.001)
