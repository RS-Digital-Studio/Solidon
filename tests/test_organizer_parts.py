"""Eigenständige Organizer-Bausteine gegen analytische Körpermaße prüfen."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.geom.mesh import as_mesh_data
from app.core.knowledge.parts import PARTS
from app.core.knowledge.parts.containers import (
    DividerParams,
    FootParams,
    RimParams,
    TrayParams,
    organizer_divider,
    organizer_foot,
    organizer_rim,
    organizer_tray,
)
from app.core.knowledge.parts.preview import render
from app.core.knowledge.parts.scad import to_scad


def test_square_tray_has_exact_outer_dimensions_floor_and_walls():
    built = organizer_tray(TrayParams(width=100, depth=80, height=40, wall=3, floor=4, radius=0))
    mesh = as_mesh_data(built.mesh)
    assert mesh.is_watertight and mesh.component_count == 1
    assert np.allclose(mesh.bounds.size, (100, 80, 40))
    assert mesh.volume == pytest.approx(100 * 80 * 40 - 94 * 74 * 36)
    assert built.features["floor"].params["centre"] == pytest.approx((0, 0, 4))


def test_divider_and_rim_are_true_printable_bodies():
    divider = as_mesh_data(organizer_divider(DividerParams(length=60, height=25, thickness=3)).mesh)
    assert divider.volume == pytest.approx(60 * 25 * 3)
    rim = as_mesh_data(
        organizer_rim(RimParams(width=100, depth=80, height=4, thickness=3, radius=0)).mesh
    )
    assert rim.volume == pytest.approx((100 * 80 - 94 * 74) * 4)
    assert rim.is_watertight and rim.component_count == 1


@pytest.mark.parametrize(
    "factory,params",
    [(organizer_tray, TrayParams()), (organizer_rim, RimParams()), (organizer_foot, FootParams())],
)
def test_named_plane_areas_equal_the_real_triangles(factory, params):
    built = factory(params)
    raw = as_mesh_data(built.mesh).raw
    for feature in built.features.values():
        if feature.kind != "face":
            continue
        normal = np.asarray(feature.params["normal"])
        center = np.asarray(feature.params["centre"])
        mask = (np.linalg.norm(raw.face_normals - normal, axis=1) < 1e-6) & (
            np.abs((raw.triangles_center - center) @ normal) < 1e-6
        )
        assert feature.params["area"] == pytest.approx(float(raw.area_faces[mask].sum()), abs=5e-5)


def test_stepped_foot_keeps_nominal_pin_and_separate_flange_dimensions():
    built = organizer_foot(FootParams(diameter=18, height=11, pin_diameter=13, pin_length=8))
    mesh = as_mesh_data(built.mesh)
    assert mesh.is_watertight and mesh.component_count == 1
    assert np.allclose(mesh.bounds.size, (18, 18, 19))
    pin = built.features["pin"]
    assert pin.params["diameter"] == pytest.approx(13)
    assert pin.params["centre"] == pytest.approx((0, 0, 15))
    assert mesh.volume == pytest.approx(np.pi * (9**2 * 11 + 6.5**2 * 8), rel=0.004)


@pytest.mark.parametrize(
    "name", ["organizer_tray", "organizer_divider", "organizer_rim", "organizer_foot"]
)
def test_new_parts_have_registered_features_generated_preview_and_scad(name):
    spec = PARTS.get(name)
    built = spec.fn(spec.params())
    assert set(spec.features) <= set(built.features)
    assert render(spec, size=100).svg.startswith("<svg")
    assert "polyhedron(" in to_scad(spec)
