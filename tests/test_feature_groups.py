"""Sammelhandlungen folgen Maßen, Ausrichtung und belegten Hohlraumketten."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive import relations
from app.core.perceive.features import EPS_ANGLE, detect
from app.core.perceive.matching import moved_features
from app.core.perceive.relations import (
    FeatureActionGroup,
    alike_for_action,
    alike_for_actions,
    cavity_chains,
)
from app.core.types import Feature


@pytest.fixture(scope="module")
def garden_pattern() -> tuple[MeshData, dict[str, Feature]]:
    """Vier Senkbohrungen und acht Außenlöcher wie am Gartenhalter.

    Zwei Aufweitungen sind 1,5 mm, zwei 8,5 mm tief. Zusammen entstehen
    dieselben 16 zylindrischen Hohlraumabschnitte, die das alte Panel allein
    wegen ``kind == "hole"`` in eine Sammelhandlung legte.
    """
    bodies = []
    for x, counterbore_depth in ((0.0, 1.5), (30.0, 1.5), (60.0, 8.5), (90.0, 8.5)):
        height = 8.5 + counterbore_depth
        profile = [
            [12.0, 0.0],
            [12.0, height],
            [5.5, height],
            [5.5, 8.5],
            [3.0, 6.0],
            [3.0, 0.0],
            [12.0, 0.0],
        ]
        body = trimesh.creation.revolve(profile, sections=48)
        body.apply_translation([x, 0.0, 0.0])
        bodies.append(body)

    for x in range(0, 80, 10):
        profile = [[4.0, 0.0], [4.0, 9.0], [1.0, 9.0], [1.0, 0.0], [4.0, 0.0]]
        body = trimesh.creation.revolve(profile, sections=48)
        body.apply_translation([float(x), 30.0, 0.0])
        bodies.append(body)

    mesh = MeshData.of(trimesh.util.concatenate(bodies))
    features = detect(mesh)
    holes = [feature for feature in features.values() if feature.kind == "hole"]
    assert len(holes) == 16
    assert len(cavity_chains(features, mesh)) == 4
    return mesh, features


def _targets(group: FeatureActionGroup) -> tuple[str, ...]:
    return tuple(member.target for member in group.members)


def test_resize_groups_the_measured_role_instead_of_every_hole(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """Ø2, Ø6 und Ø11 sind drei Handlungen, auch wenn alle ``hole`` heißen."""
    mesh, features = garden_pattern
    chains = cavity_chains(features, mesh)
    narrow = tuple(chain[0] for chain in chains)
    wide = tuple(chain[-1] for chain in chains)
    chained = {feature.id for chain in chains for feature in chain}
    outside = tuple(
        feature
        for feature in features.values()
        if feature.kind == "hole" and feature.id not in chained
    )

    narrow_group = alike_for_action("resize_hole", narrow[0].id, features, mesh)
    wide_group = alike_for_action("resize_hole", wide[0].id, features, mesh)
    outside_group = alike_for_action("resize_hole", outside[0].id, features, mesh)

    assert set(_targets(narrow_group)) == {feature.id for feature in narrow}
    assert set(_targets(wide_group)) == {feature.id for feature in wide}
    assert set(_targets(outside_group)) == {feature.id for feature in outside}
    assert "same_target_dimensions" in narrow_group.evidence
    assert "shared_boundary_role" in narrow_group.evidence
    assert all(len(member.scope) == 3 for member in narrow_group.members)
    assert all(len(member.scope) == 1 for member in outside_group.members)


def test_whole_feature_actions_require_the_complete_repeated_shape(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """Versetzen nimmt die ganze Kette mit und trennt daher zwei Tiefen."""
    mesh, features = garden_pattern
    chains = cavity_chains(features, mesh)
    shallow = tuple(chain for chain in chains if float(chain[-1].params["depth"]) < 2.0)
    deep = tuple(chain for chain in chains if float(chain[-1].params["depth"]) > 8.0)

    shallow_group = alike_for_action("move_feature", shallow[0][0].id, features, mesh)
    deep_group = alike_for_action("remove_feature", deep[0][0].id, features, mesh)

    assert set(_targets(shallow_group)) == {chain[0].id for chain in shallow}
    assert set(_targets(deep_group)) == {chain[0].id for chain in deep}
    assert "complete_surface_patch" in shallow_group.evidence
    assert "translation_consistent" in shallow_group.evidence
    assert {member.scope for member in shallow_group.members} == {
        tuple(feature.id for feature in chain) for chain in shallow
    }


def test_group_identity_survives_mapping_order_and_a_rigid_transform(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """IDs und Reihenfolge hängen weder am Wörterbuch noch an Weltkoordinaten."""
    mesh, features = garden_pattern
    selected = cavity_chains(features, mesh)[0][0].id
    expected = alike_for_action("resize_hole", selected, features, mesh)
    reversed_group = alike_for_action(
        "resize_hole", selected, dict(reversed(list(features.items()))), mesh
    )

    matrix = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1.0, 0.0, 0.0])
    matrix[:3, 3] = [7.0, -11.0, 19.0]
    body = mesh.raw.copy()
    body.apply_transform(matrix)
    transformed_mesh = MeshData.of(body)
    transformed_features = moved_features(dict(features), matrix)
    transformed = alike_for_action("resize_hole", selected, transformed_features, transformed_mesh)

    assert reversed_group == expected
    assert transformed == expected
    assert expected.id.startswith("resize_hole:")
    assert _targets(expected) == tuple(sorted(_targets(expected)))


def test_an_ambiguous_boundary_chain_is_reported_instead_of_grouped(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """Drei Besitzer eines Randrings liefern einen Grund und keine Vermutung."""
    mesh, features = garden_pattern
    chain = cavity_chains(features, mesh)[0]
    duplicate = replace(chain[1], id="ambiguous_cone")
    ambiguous = {**features, duplicate.id: duplicate}

    group = alike_for_action("resize_hole", chain[0].id, ambiguous, mesh)

    assert group.members == ()
    assert group.uncertain
    assert {uncertainty.reason for uncertainty in group.uncertain} == {"ambiguous_cavity_chain"}
    assert chain[0].id in {
        identifier for item in group.uncertain for identifier in item.feature_ids
    }


def test_a_missing_axis_is_an_explained_uncertainty(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """Ohne Richtung lässt sich Parallelität nicht still behaupten."""
    mesh, features = garden_pattern
    chained = {feature.id for chain in cavity_chains(features, mesh) for feature in chain}
    outside = [
        feature
        for feature in features.values()
        if feature.kind == "hole" and feature.id not in chained
    ]
    without_axis = replace(
        outside[-1],
        params={key: value for key, value in outside[-1].params.items() if key != "axis"},
    )
    altered = {**features, without_axis.id: without_axis}

    group = alike_for_action("resize_hole", outside[0].id, altered, mesh)

    assert without_axis.id not in _targets(group)
    assert any(
        item.reason == "orientation_unavailable" and item.feature_ids == (without_axis.id,)
        for item in group.uncertain
    )


def test_the_register_rejects_an_action_that_does_not_fit_the_selected_kind(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """Die Sammelgruppe erfindet keine Eignung neben ``applies_to``."""
    mesh, features = garden_pattern
    cone = cavity_chains(features, mesh)[0][1]

    group = alike_for_action("resize_hole", cone.id, features, mesh)

    assert group.members == ()
    assert group.uncertain[0].reason == "action_not_applicable"
    assert group.uncertain[0].feature_ids == (cone.id,)


@pytest.mark.parametrize(
    "action",
    ("move_feature", "rotate_feature", "duplicate_feature", "remove_feature"),
)
def test_only_resize_uses_the_registered_measured_shape_dimension(
    garden_pattern: tuple[MeshData, dict[str, Feature]], action: str
) -> None:
    """Position und Drehwinkel werden nicht mit dem Durchmesser verwechselt."""
    mesh, features = garden_pattern
    chained = {feature.id for chain in cavity_chains(features, mesh) for feature in chain}
    outside = next(
        feature
        for feature in features.values()
        if feature.kind == "hole" and feature.id not in chained
    )

    resized = alike_for_action("resize_hole", outside.id, features, mesh)
    whole = alike_for_action(action, outside.id, features, mesh)
    cone = cavity_chains(features, mesh)[0][1]
    cone_resized = alike_for_action("resize_feature", cone.id, features, mesh)

    assert "same_target_dimensions" in resized.evidence
    assert "same_target_dimensions" in cone_resized.evidence
    assert "complete_surface_patch" in whole.evidence
    assert "same_target_dimensions" not in whole.evidence


def test_cone_angles_use_the_existing_angular_measurement_resolution(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """Fit-Rauschen darf Gegenstücke verbinden, ein messbarer Winkel nicht."""
    mesh, features = garden_pattern
    shallow = sorted(
        (
            chain
            for chain in cavity_chains(features, mesh)
            if float(chain[-1].params["depth"]) < 2.0
        ),
        key=lambda chain: float(chain[0].params["centre"][0]),
    )
    selected, candidate = shallow
    cone = candidate[1]

    near = {
        **features,
        cone.id: replace(
            cone,
            params={**cone.params, "angle": float(cone.params["angle"]) + EPS_ANGLE / 2.0},
        ),
    }
    far = {
        **features,
        cone.id: replace(
            cone,
            params={**cone.params, "angle": float(cone.params["angle"]) + EPS_ANGLE * 2.0},
        ),
    }

    assert candidate[0].id in _targets(alike_for_action("move_feature", selected[0].id, near, mesh))
    assert candidate[0].id not in _targets(
        alike_for_action("move_feature", selected[0].id, far, mesh)
    )


def test_complete_surface_shape_uses_the_actual_patch_not_only_sphere_radius() -> None:
    """Gleicher Kugelradius macht verschieden große Abdeckungen nicht gleich."""
    bodies = []
    for x in (0.0, 20.0, 40.0):
        body = trimesh.creation.icosphere(subdivisions=2, radius=5.0)
        if x == 20.0:
            body.vertices *= 1.0005
        body.apply_translation([x, 0.0, 0.0])
        bodies.append(body)
    faces_per_body = len(bodies[0].faces)
    mesh = MeshData.of(trimesh.util.concatenate(bodies))
    cap_faces = tuple(
        2 * faces_per_body + index
        for index, centre in enumerate(bodies[2].triangles_center)
        if centre[2] >= 0.0
    )
    common = {"diameter": 10.0, "recess": False}
    features = {
        "sphere_1": Feature(
            id="sphere_1",
            kind="sphere",
            provenance="detected",
            params={**common, "centre": (0.0, 0.0, 0.0)},
            face_indices=tuple(range(faces_per_body)),
        ),
        "sphere_2": Feature(
            id="sphere_2",
            kind="sphere",
            provenance="detected",
            params={**common, "centre": (20.0, 0.0, 0.0)},
            face_indices=tuple(range(faces_per_body, 2 * faces_per_body)),
        ),
        "sphere_cap": Feature(
            id="sphere_cap",
            kind="sphere",
            provenance="detected",
            params={**common, "centre": (40.0, 0.0, 0.0)},
            face_indices=cap_faces,
        ),
    }

    group = alike_for_action("move_feature", "sphere_1", features, mesh)

    assert _targets(group) == ("sphere_1", "sphere_2")
    assert "complete_surface_patch" in group.evidence
    assert "sphere_cap" not in _targets(group)


def test_a_whole_shape_without_surface_evidence_is_reported() -> None:
    """Ohne Flächen darf der Kern aus gleichen Kennzahlen keine Form erfinden."""
    feature = Feature(
        id="pin_1",
        kind="pin",
        provenance="generated",
        params={
            "diameter": 6.0,
            "depth": 10.0,
            "axis": (0.0, 0.0, 1.0),
            "centre": (0.0, 0.0, 0.0),
        },
    )
    mesh = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 10.0)))

    group = alike_for_action("move_feature", feature.id, {feature.id: feature}, mesh)

    assert group.members == ()
    assert group.uncertain[0].reason == "complete_shape_unavailable"


def test_the_action_batch_builds_cavity_topology_once(
    garden_pattern: tuple[MeshData, dict[str, Feature]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fünf Panelzeilen lesen für dieselbe Auswahl denselben Randgraphen."""
    mesh, features = garden_pattern
    selected = cavity_chains(features, mesh)[0][0].id
    actions = (
        "move_feature",
        "resize_hole",
        "rotate_feature",
        "duplicate_feature",
        "remove_feature",
    )
    original = relations._feature_group_topology
    calls = 0

    def counted(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(relations, "_feature_group_topology", counted)
        grouped = alike_for_actions(actions, selected, features, mesh)

    expected = tuple(alike_for_action(action, selected, features, mesh) for action in actions)
    assert grouped == expected
    assert tuple(group.action for group in grouped) == actions
    assert calls == 1
