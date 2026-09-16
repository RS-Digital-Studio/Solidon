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
    exported = to_scad(spec)
    assert "polyhedron(" in exported and f"{name}();" in exported


def test_groove_part_starts_at_the_clicked_mouth_and_extends_down():
    built = seals.seal_groove(seals.GrooveParams(depth=4))
    assert built.mesh.bounds.minimum[2] == pytest.approx(-4)
    assert built.mesh.bounds.maximum[2] == pytest.approx(0)
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


def test_part_dimensions_rebuild_the_actual_gasket_cross_section():
    small = seals.seal_gasket(seals.GasketParams(height=2, width=2))
    large = seals.seal_gasket(seals.GasketParams(height=4, width=3))
    assert large.mesh.bounds.size[2] == pytest.approx(2 * small.mesh.bounds.size[2])
    assert large.mesh.volume == pytest.approx(3 * small.mesh.volume, rel=0.001)
