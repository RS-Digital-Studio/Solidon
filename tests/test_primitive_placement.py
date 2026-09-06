"""Freie Position und Richtung der fünf analytischen Grundkörper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.geom.mesh import as_mesh_data
from app.core.geom.primitive_ops import primitive_local_tool
from app.core.geom.transform import apply
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.sketch.planes import frame_of
from app.core.types import OpContext, OpResult, Profile, Quality, Scene

load_operations()

CASES: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "create_box",
        {"width": 12.0, "depth": 8.0, "height": 5.0, "anchor": "centre", "name": ""},
    ),
    (
        "create_cylinder",
        {"diameter": 10.0, "height": 7.0, "segments": 32, "name": ""},
    ),
    (
        "create_cone",
        {
            "bottom_diameter": 12.0,
            "top_diameter": 6.0,
            "height": 9.0,
            "segments": 32,
            "name": "",
        },
    ),
    ("create_sphere", {"diameter": 10.0, "segments": 24, "name": ""}),
    (
        "create_torus",
        {"outer_diameter": 20.0, "tube_diameter": 4.0, "segments": 32, "name": ""},
    ),
)


def _run(
    name: str,
    values: Mapping[str, Any],
    profile: Profile,
    quality: Quality = "fine",
) -> OpResult:
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(),
            inputs=[],
            params=spec.params(**values),
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda _fraction, _text: None,
            ask=lambda _question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


@pytest.mark.parametrize(("name", "values"), CASES)
def test_mesh_primitives_offer_one_advanced_position_and_normal(
    name: str, values: dict[str, Any]
) -> None:
    schema = {entry.name: entry for entry in REGISTRY.get(name).params.spec()}

    for field in ("x", "y", "z", "nx", "ny", "nz"):
        assert schema[field].default == 0.0
        assert schema[field].placement == "advanced"


@pytest.mark.parametrize(("name", "values"), CASES)
def test_zero_placement_keeps_the_previous_primitive_geometry(
    name: str, values: dict[str, Any], profile: Profile
) -> None:
    spec = REGISTRY.get(name)
    params = spec.params(**values)
    local = primitive_local_tool(name, params.as_dict(), "fine")
    actual = as_mesh_data(_run(name, values, profile).outputs[0].mesh)

    assert np.asarray(actual.raw.vertices) == pytest.approx(
        np.asarray(local.raw.vertices), abs=1e-12
    )
    assert np.array_equal(actual.raw.faces, local.raw.faces)


@pytest.mark.parametrize(("name", "values"), CASES)
def test_zero_normal_translates_the_existing_local_anchor(
    name: str, values: dict[str, Any], profile: Profile
) -> None:
    position = np.asarray((7.25, -3.5, 11.0))
    spec = REGISTRY.get(name)
    params = spec.params(**values)
    local = primitive_local_tool(name, params.as_dict(), "fine")
    actual = as_mesh_data(
        _run(
            name,
            {**values, "x": position[0], "y": position[1], "z": position[2]},
            profile,
        )
        .outputs[0]
        .mesh
    )

    assert np.asarray(actual.raw.vertices) == pytest.approx(
        np.asarray(local.raw.vertices) + position, abs=1e-12
    )
    assert np.array_equal(actual.raw.faces, local.raw.faces)


@pytest.mark.parametrize(("name", "values"), CASES)
def test_slanted_operation_and_surface_ghost_share_the_same_local_basis(
    name: str, values: dict[str, Any], profile: Profile
) -> None:
    position = (7.25, -3.5, 11.0)
    normal = (2.0, -3.0, 6.0)
    spec = REGISTRY.get(name)
    params = spec.params(**values)
    local = primitive_local_tool(name, params.as_dict(), "fine")
    frame = frame_of(normal, position)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    matrix[:3, 3] = position
    shown = apply(local, matrix)
    actual = _run(
        name,
        {
            **values,
            "x": position[0],
            "y": position[1],
            "z": position[2],
            "nx": normal[0],
            "ny": normal[1],
            "nz": normal[2],
        },
        profile,
    ).outputs[0]
    actual_mesh = as_mesh_data(actual.mesh)

    assert np.asarray(actual_mesh.raw.vertices) == pytest.approx(
        np.asarray(shown.raw.vertices), abs=1e-12
    )
    assert np.array_equal(actual_mesh.raw.faces, shown.raw.faces)
    if "face_top" in actual.features:
        assert actual.features["face_top"].params["normal"] == pytest.approx(frame.normal)
        expected_centre = matrix @ np.asarray((0.0, 0.0, float(values["height"]), 1.0))
        assert actual.features["face_top"].params["centre"] == pytest.approx(expected_centre[:3])


def test_box_corner_remains_the_local_anchor_when_it_is_moved(profile: Profile) -> None:
    position = np.asarray((4.0, 5.0, 6.0))
    result = _run(
        "create_box",
        {
            "width": 12.0,
            "depth": 8.0,
            "height": 5.0,
            "anchor": "corner",
            "name": "",
            "x": position[0],
            "y": position[1],
            "z": position[2],
        },
        profile,
    )

    assert as_mesh_data(result.outputs[0].mesh).bounds.minimum == pytest.approx(position)
