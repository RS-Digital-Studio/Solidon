"""Bei dünnen Zylinderwänden bleibt die Radiusänderung an der gewählten Haut."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.core.geom.mesh import as_mesh_data
from app.core.perceive.features import detect
from app.core.types import Profile, SceneObject, is_a_cavity
from tests.test_mesh_edges import run


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("mirrored", [False, True])
def test_a_thin_clip_changes_its_outer_radius_without_touching_the_inner(
    kind: str, mirrored: bool, profile: Profile
) -> None:
    """R12,4 außen wird R12,2; die nahe Innenwand bleibt auf R12."""
    pytest.importorskip("OCP")
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    sweep = math.radians(184.0)
    outside = Solid(BRepPrimAPI_MakeCylinder(12.4, 17.0, sweep).Shape())
    inside = Solid(BRepPrimAPI_MakeCylinder(12.0, 17.0, sweep).Shape())
    exact = edit.boolean("difference", [outside, inside])
    if mirrored:
        # Die Spiegelung erzeugt einen linkshändigen Zylinderrahmen.
        exact = edit.transformed(exact, np.diag([1.0, 1.0, -1.0, 1.0]))
    body = exact if kind == "brep" else as_mesh_data(exact)
    features = features_of(exact) if kind == "brep" else detect(body)
    roundings = sorted(
        (feature for feature in features.values() if feature.kind == "fillet"),
        key=lambda feature: float(feature.params["radius"]),
    )
    assert [feature.params["radius"] for feature in roundings] == pytest.approx([12.0, 12.4])
    assert is_a_cavity(roundings[0])
    assert not is_a_cavity(roundings[1])
    source = SceneObject(id="clip", name="Klemme", kind=kind, mesh=body, features=features)
    original_vertices = np.array(as_mesh_data(body).raw.vertices, copy=True)
    original_volume = body.volume

    changed = run(
        "resize_feature", source, profile, at_feature=roundings[1].id, diameter=24.4
    ).outputs[0]

    assert changed.kind == kind
    assert changed.mesh.is_watertight and changed.mesh.component_count == 1
    after = features_of(changed.mesh) if kind == "brep" else detect(as_mesh_data(changed.mesh))
    rounded = sorted(
        (feature for feature in after.values() if feature.kind == "fillet"),
        key=lambda feature: float(feature.params["radius"]),
    )
    assert [feature.params["radius"] for feature in rounded] == pytest.approx([12.0, 12.2])
    assert is_a_cavity(rounded[0])
    assert not is_a_cavity(rounded[1])
    assert changed.mesh.bounds.maximum[0] == pytest.approx(12.2, abs=0.000001)
    assert changed.mesh.bounds.size[2] == pytest.approx(17.0, abs=0.000001)
    if kind == "brep":
        assert changed.mesh.volume == pytest.approx(sweep * 17.0 * (12.2**2 - 12.0**2) / 2.0)
    assert body.volume == pytest.approx(original_volume, abs=0.000001)
    assert np.array_equal(as_mesh_data(body).raw.vertices, original_vertices)
