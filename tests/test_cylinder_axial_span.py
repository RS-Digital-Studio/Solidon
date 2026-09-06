"""Zylinderlagen bleiben unabhängig von der Dreiecksverteilung."""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.perceive.matching import cost, match
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, OpContext, Profile, Scene, SceneObject


def _tube(levels: tuple[float, ...]) -> MeshData:
    """Ein Ringkörper mit frei verteilter Unterteilung entlang seiner Achse."""
    sections = 192
    radii = (5.0, 10.0)
    vertices: list[tuple[float, float, float]] = []

    def vertex(radius: int, level: int, section: int) -> int:
        return (radius * len(levels) + level) * sections + section % sections

    for radius in radii:
        for height in levels:
            for section in range(sections):
                angle = math.tau * section / sections
                vertices.append((radius * math.cos(angle), radius * math.sin(angle), height))

    faces: list[tuple[int, int, int]] = []
    for radius in range(2):
        for level in range(len(levels) - 1):
            for section in range(sections):
                following = section + 1
                lower = vertex(radius, level, section)
                lower_next = vertex(radius, level, following)
                upper_next = vertex(radius, level + 1, following)
                upper = vertex(radius, level + 1, section)
                if radius:
                    faces.extend(((lower, lower_next, upper_next), (lower, upper_next, upper)))
                else:
                    faces.extend(((lower, upper_next, lower_next), (lower, upper, upper_next)))

    lower, upper = 0, len(levels) - 1
    for section in range(sections):
        following = section + 1
        inner = vertex(0, upper, section)
        inner_next = vertex(0, upper, following)
        outer = vertex(1, upper, section)
        outer_next = vertex(1, upper, following)
        faces.extend(((inner, outer, outer_next), (inner, outer_next, inner_next)))

        inner = vertex(0, lower, section)
        inner_next = vertex(0, lower, following)
        outer = vertex(1, lower, section)
        outer_next = vertex(1, lower, following)
        faces.extend(((inner, outer_next, outer), (inner, inner_next, outer_next)))

    body = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=float),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    assert body.is_watertight
    return MeshData.of(body)


def _hole(mesh: MeshData) -> Feature:
    holes = [feature for feature in detect(mesh).values() if feature.kind == "hole"]
    assert len(holes) == 1
    return holes[0]


def _axial_face_span(mesh: MeshData, feature: Feature) -> tuple[float, float]:
    axis = np.asarray(feature.params["axis"], dtype=float)
    axis /= np.linalg.norm(axis)
    faces = np.asarray(mesh.raw.faces)[np.asarray(feature.face_indices, dtype=np.int64)]
    vertices = np.asarray(mesh.raw.vertices)[np.unique(faces)]
    positions = vertices @ axis
    return float(positions.min()), float(positions.max())


def test_cylinder_centre_is_independent_of_axial_tessellation() -> None:
    """Zusätzliche Dreiecksringe verschieben dasselbe erkannte Loch nicht."""
    even_mesh = _tube((-5.0, 5.0))
    uneven_mesh = _tube((-5.0, 2.0, 3.0, 4.0, 5.0))
    even = _hole(even_mesh)
    uneven = _hole(uneven_mesh)

    lower, upper = _axial_face_span(uneven_mesh, uneven)
    axis = np.asarray(uneven.params["axis"], dtype=float)
    measured = float(np.asarray(uneven.params["centre"], dtype=float) @ axis)

    assert upper - lower == pytest.approx(10.0, abs=1e-9)
    assert measured == pytest.approx((lower + upper) / 2.0, abs=1e-9)
    assert uneven.params["centre"] == pytest.approx(even.params["centre"], abs=1e-9)

    diagonal = uneven_mesh.bounds.diagonal
    result = match(
        {even.id: even},
        {uneven.id: uneven},
        uneven_mesh.bounds.centre,
        diagonal,
    )
    assert result.mapping == {even.id: uneven.id}
    assert cost(even, uneven, even_mesh.bounds.centre, uneven_mesh.bounds.centre, diagonal) == (
        pytest.approx(0.0, abs=1e-9)
    )


def test_cylinder_centre_uses_the_rotated_face_span() -> None:
    """Der Mittelpunkt kommt auch bei einer freien Achse aus beiden Endringen."""
    mesh = _tube((-5.0, 2.0, 3.0, 4.0, 5.0))
    transform = trimesh.transformations.rotation_matrix(math.radians(37.0), (1.0, 2.0, 0.5))
    transform[:3, 3] = (17.0, -8.0, 23.0)
    body = mesh.raw.copy()
    body.apply_transform(transform)
    turned = mesh.replacing(body)

    feature = _hole(turned)
    lower, upper = _axial_face_span(turned, feature)
    axis = np.asarray(feature.params["axis"], dtype=float)
    measured = float(np.asarray(feature.params["centre"], dtype=float) @ axis)

    assert measured == pytest.approx((lower + upper) / 2.0, abs=1e-9)
    assert feature.params["centre"] == pytest.approx(transform[:3, 3], abs=1e-9)


def test_a_stored_triangle_weighted_centre_still_matches() -> None:
    """Alte Projekte behalten ihre Bohrungsreferenz nach der Korrektur."""
    mesh = _tube((-5.0, 2.0, 3.0, 4.0, 5.0))
    corrected = _hole(mesh)
    stored = dataclasses.replace(
        corrected,
        params={**corrected.params, "centre": (0.0, 0.0, 2.25)},
    )

    result = match(
        {stored.id: stored},
        {corrected.id: corrected},
        mesh.bounds.centre,
        mesh.bounds.diagonal,
    )

    assert result.mapping == {stored.id: corrected.id}
    assert not result.ambiguous
    assert not result.orphaned


def test_resize_hole_covers_the_whole_uneven_cylinder(profile: Profile) -> None:
    """Der Dialogweg ändert beide Enden einer ungleich triangulierten Bohrung."""
    mesh = _tube((-5.0, 2.0, 3.0, 4.0, 5.0))
    feature = _hole(mesh)
    source = SceneObject(id="obj_1", name="Ring", mesh=mesh, features={feature.id: feature})
    spec = REGISTRY.get("resize_hole")

    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=feature.id, diameter=8.0, compensate=False),
            profile=profile,
            quality="fine",
            seed=11,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    output = result.outputs[0]
    recognised = output.features[feature.id]
    assert output.mesh.is_watertight
    assert result.solver is not None and result.solver.strategy == "direct"
    assert recognised.params["diameter"] == pytest.approx(8.0, abs=0.03)
    assert not [
        finding for finding in result.findings if finding.code == "resize_hole.feature_lost"
    ]
