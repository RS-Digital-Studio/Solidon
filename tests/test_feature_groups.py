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
    params_for_members,
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


def test_fit_diagnostics_do_not_split_geometrically_equal_action_groups(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """Eine neu gemessene Unsicherheit ist kein zusätzliches Formmaß eines Lochs."""
    mesh, features = garden_pattern
    outside = sorted(
        (
            feature
            for feature in features.values()
            if feature.kind == "hole" and feature.params["diameter"] < 3
        ),
        key=lambda feature: feature.id,
    )
    selected = outside[0]
    baseline = set(_targets(alike_for_action("move_feature", selected.id, features, mesh)))
    assert len(baseline) == 8
    changed = {
        name: replace(
            feature,
            params={
                key: value
                for key, value in feature.params.items()
                if key not in {"fit_error", "radial_min", "radial_max"}
            },
        )
        for name, feature in features.items()
    }
    candidate = changed[outside[1].id]
    changed[candidate.id] = replace(
        candidate,
        params={**candidate.params, "fit_error": 0.002, "radial_min": 0.99, "radial_max": 1.0},
    )
    assert set(_targets(alike_for_action("move_feature", selected.id, changed, mesh))) == baseline


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


def test_rounding_resize_groups_by_radius_instead_of_missing_diameter() -> None:
    """Gleiche Kehlenradien bilden die Größenhandlung; Außenrundungen bleiben ausgenommen."""
    mesh = MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 10.0)))
    features = {
        f"fillet_{index}": Feature(
            id=f"fillet_{index}",
            kind="fillet",
            provenance="detected",
            params={
                "radius": radius,
                "centre": (float(index * 10), 0.0, 0.0),
                "axis": (0.0, 0.0, 1.0),
                "recess": recess,
            },
        )
        for index, (radius, recess) in enumerate(
            ((3.0, True), (3.0, True), (6.0, True), (3.0, False)), start=1
        )
    }
    group = alike_for_action("resize_feature", "fillet_1", features, mesh)
    assert set(_targets(group)) == {"fillet_1", "fillet_2"}
    assert "same_target_dimensions" in group.evidence


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


def test_a_group_builds_each_surface_index_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acht gleiche Kugeln teilen ihre Suchbäume — und ein zweiter Klick baut keinen neu.

    Bis zum 22.09.2026 lebten die Ausschnitte nur für einen Aufruf, und jeder
    Klick im Merkmalfenster baute sie neu (0,47 s an der Lochplatte mit
    360 000 Dreiecken). Jetzt hängen sie am Körper und an den Dreiecken,
    Achsen und Mitten der Merkmale; ein anderer Körper bekommt seine eigenen.
    """
    bodies = []
    features = {}
    offset = 0
    for index in range(8):
        centre = (20.0 * index, 0.0, 0.0)
        body = trimesh.creation.icosphere(subdivisions=2, radius=5.0)
        body.apply_translation(centre)
        bodies.append(body)
        identifier = f"sphere_{index + 1}"
        features[identifier] = Feature(
            id=identifier,
            kind="sphere",
            provenance="detected",
            params={"diameter": 10.0, "centre": centre, "recess": False},
            face_indices=tuple(range(offset, offset + len(body.faces))),
        )
        offset += len(body.faces)
    mesh = MeshData.of(trimesh.util.concatenate(bodies))
    original = relations.cKDTree
    built = 0

    def counted(*args: object, **kwargs: object):
        nonlocal built
        built += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(relations, "cKDTree", counted)
    actions = ("move_feature", "duplicate_feature", "remove_feature")
    grouped = alike_for_actions(actions, "sphere_1", features, mesh)

    assert all(_targets(group) == tuple(features) for group in grouped), {
        group.action: (_targets(group), group.uncertain) for group in grouped
    }
    assert built == len(features), f"{built} surface indexes for {len(features)} patches"
    assert alike_for_actions(actions, "sphere_1", features, mesh) == grouped
    assert built == len(features), "the same body reads its surface indexes, it does not rebuild"
    copy = MeshData.of(mesh.raw.copy())
    assert alike_for_actions(actions, "sphere_1", features, copy) == grouped
    assert built == 2 * len(features), "another body gets its own surface indexes"


def test_a_finer_subdivided_copy_is_still_the_same_complete_shape(
    garden_pattern: tuple[MeshData, dict[str, Feature]],
) -> None:
    """Dieselbe Fläche, anders vernetzt, gehört zur Ganzkörpergruppe (P1.5).

    Am Gartenmuster werden die Dreiecke **einer** der acht Außenbohrungen in
    vier geteilt — die Fläche ändert sich nicht, die Ecken und Kantenlängen
    schon. Bis zum 20.09.2026 verglich ``_same_surface_patch`` genau die und
    ließ die Bohrung aus der Gruppe fallen; jetzt zählt der Abstand zur
    Fläche, und die Kalottengegenprobe daneben trennt weiter.
    """
    mesh, features = garden_pattern
    small = sorted(
        (feature for feature in features.values() if feature.kind == "hole"),
        key=lambda feature: (float(feature.params["diameter"]), feature.id),
    )[:8]
    assert len({round(float(f.params["diameter"]), 3) for f in small}) == 1, "acht Ø 2"
    chosen, other = small[0], small[1]
    before = alike_for_action("move_feature", chosen.id, features, mesh)
    assert other.id in _targets(before) and "complete_surface_patch" in before.evidence

    body = mesh.raw
    vertices, faces, split = trimesh.remesh.subdivide(
        body.vertices, body.faces, face_index=np.asarray(other.face_indices), return_index=True
    )
    # trimesh stellt die unveränderten Dreiecke in ihrer Reihenfolge nach vorn
    # und hängt die geteilten an; ``split`` nennt nur die geteilten.
    untouched = np.setdiff1d(np.arange(len(body.faces)), np.asarray(other.face_indices))
    new_index = {int(old): (int(new),) for new, old in enumerate(untouched)}
    new_index.update({int(old): tuple(int(i) for i in new) for old, new in split.items()})
    remeshed = MeshData.of(trimesh.Trimesh(vertices, faces, process=False))
    renumbered = {
        identifier: replace(
            feature,
            face_indices=tuple(
                index for old in feature.face_indices for index in new_index[int(old)]
            ),
        )
        for identifier, feature in features.items()
    }
    assert len(renumbered[other.id].face_indices) == 4 * len(other.face_indices)
    # Gegenprobe der Umnummerierung: dieselben Dreiecksmitten am unveränderten Merkmal.
    assert np.allclose(
        np.sort(remeshed.raw.triangles_center[list(renumbered[chosen.id].face_indices)], axis=0),
        np.sort(body.triangles_center[list(chosen.face_indices)], axis=0),
    )

    after = alike_for_action("move_feature", chosen.id, renumbered, remeshed)
    assert other.id in _targets(after), (_targets(after), after.uncertain)
    assert "complete_surface_patch" in after.evidence
    assert _targets(after) == _targets(before)


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


def test_the_values_for_each_member_keep_every_place_where_it_is() -> None:
    """Sechs Bohrungen auf ein Maß bringen legte sie übereinander (Robert, 16.09.2026).

    Das Merkmalfenster trägt beim Ändern auch die Stelle x, y, z mit, und die
    ging als derselbe Ort an jede Geschwisterbohrung. Die Stelle gehört jedem
    Merkmal selbst: Jedes bekommt seine eigene Mitte, ein Versatz am gewählten
    geht als Versatz mit, und eine ungenannte Achse bleibt ungenannt.
    """
    features = {
        "hole_1": Feature(
            id="hole_1",
            kind="hole",
            provenance="detected",
            params={"diameter": 5.0, "centre": (10.0, 0.0, 0.0)},
        ),
        "hole_2": Feature(
            id="hole_2",
            kind="hole",
            provenance="detected",
            params={"diameter": 5.0, "centre": (30.0, 0.0, 0.0)},
        ),
        "hole_3": Feature(
            id="hole_3", kind="hole", provenance="detected", params={"diameter": 5.0}
        ),
    }
    members = ("hole_1", "hole_2", "hole_3")

    # Nur das Maß geändert, die Stelle steht wie gemessen: jede bleibt, wo sie ist.
    same_place = {"at_feature": "hole_1", "diameter": 6.5, "x": 10.0, "y": 0.0, "z": 0.0}
    each = params_for_members(same_place, "hole_1", members, features)
    assert each["hole_1"] == same_place, "das gewählte Merkmal bekommt seine Werte unverändert"
    assert each["hole_2"] == {
        "at_feature": "hole_2",
        "diameter": 6.5,
        "x": 30.0,
        "y": 0.0,
        "z": 0.0,
    }
    assert each["hole_3"] == {"at_feature": "hole_3", "diameter": 6.5}, (
        "ohne gemessene Mitte reist keine Stelle"
    )

    # Das gewählte um fünf nach x geschoben, y und z ungenannt: alle um dasselbe.
    each = params_for_members(
        {"at_feature": "hole_1", "x": 15.0, "y": None, "z": None}, "hole_1", members, features
    )
    assert each["hole_2"] == {"at_feature": "hole_2", "x": 35.0}
    assert each["hole_3"] == {"at_feature": "hole_3"}

    # Ohne Stelle in den Werten reist auch keine.
    each = params_for_members(
        {"at_feature": "hole_1", "diameter": 6.5}, "hole_1", members, features
    )
    assert each["hole_2"] == {"at_feature": "hole_2", "diameter": 6.5}


def test_an_unchanged_depth_stays_with_each_hole_of_a_group() -> None:
    """Die Tiefe reist nur, wenn sie am gewählten Loch geändert wurde (23.09.2026).

    Seit *Bohrung ändern* die Tiefe als Feld trägt, steht dort der gemessene
    Wert des gewählten Lochs. Wer an einer Gruppe nur den Durchmesser ändert,
    darf die anderen Löcher nicht auf diese Tiefe setzen — und die Gruppe darf
    nicht an unterschiedlichen Tiefen zerfallen.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    features = {
        name: Feature(
            id=name,
            kind="hole",
            provenance="detected",
            params={"diameter": 5.0, "depth": depth, "centre": (x, 0.0, 0.0)},
        )
        for name, depth, x in (("hole_1", 6.0, 0.0), ("hole_2", 9.0, 20.0))
    }
    members = ("hole_1", "hole_2")

    kept = params_for_members(
        {"at_feature": "hole_1", "diameter": 6.5, "depth": 6.004},
        "hole_1",
        members,
        features,
        op="resize_hole",
    )
    assert kept["hole_1"]["depth"] == pytest.approx(6.004)
    assert kept["hole_2"]["depth"] is None, "jede Bohrung behält ihre eigene Tiefe"

    changed = params_for_members(
        {"at_feature": "hole_1", "diameter": 6.5, "depth": 8.0},
        "hole_1",
        members,
        features,
        op="resize_hole",
    )
    assert changed["hole_2"]["depth"] == pytest.approx(8.0), "geändert gilt sie allen"


@pytest.fixture(scope="module")
def four_slots() -> tuple[MeshData, dict[str, Feature], dict[str, str]]:
    """Vier Langlöcher Ø 6 in einer Platte: zwei gleiche, ein längeres, ein quer liegendes.

    Alle vier haben dieselbe Breite und dieselbe Achse — das ist alles, was
    *Zum Langloch ziehen* bis zum 22.09.2026 verglich.
    """
    from app.core.geom.prepare import drill
    from app.core.knowledge import profiles

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    mesh = MeshData.of(trimesh.creation.box(extents=(160.0, 120.0, 10.0)))
    layout = {
        "reference": ((-45.0, -30.0), 20.0, 0.0),
        "twin": ((0.0, -30.0), 20.0, 0.0),
        "longer": ((45.0, -30.0), 30.0, 0.0),
        "across": ((-45.0, 30.0), 20.0, 90.0),
    }
    for (x, y), length, angle in layout.values():
        mesh = drill(
            mesh,
            profile=profile,
            position=(x, y, 5.0),
            axis="z",
            diameter=6.0,
            compensate=False,
            slot_length=length,
            slot_angle=angle,
        ).mesh
    features = detect(mesh)
    slots = [feature for feature in features.values() if feature.kind == "slot"]
    assert len(slots) == 4, sorted(feature.kind for feature in features.values())
    names = {
        role: min(
            slots,
            key=lambda feature: float(
                np.hypot(feature.params["centre"][0] - x, feature.params["centre"][1] - y)
            ),
        ).id
        for role, ((x, y), _length, _angle) in layout.items()
    }
    return mesh, features, names


def test_pulling_slots_together_takes_only_slots_of_the_same_length_and_direction(
    four_slots: tuple[MeshData, dict[str, Feature], dict[str, str]],
) -> None:
    """*Zum Langloch ziehen* setzt Länge und Richtung — gleich ist nur, was schon so liegt.

    Die Handlung trägt die Länge und die Richtung des gewählten Langlochs in
    ihre Felder, und *Auf alle anwenden* schickt dieselben Werte an jedes
    Mitglied (``params_for_members``). Bis zum 22.09.2026 verglich die Gruppe
    nur die Breite: Ein 30 mm langes und ein quer liegendes Langloch standen
    als „gleich" daneben und wären beim Übernehmen still auf 20 mm gekürzt
    beziehungsweise um 90 Grad gedreht worden — obwohl der Nachweis „Gleiches
    Ausgangsmaß für diese Änderung" versprach.
    """
    mesh, features, names = four_slots

    group = alike_for_action("slot_hole", names["reference"], features, mesh)

    assert set(_targets(group)) == {names["reference"], names["twin"]}
    assert "same_target_dimensions" in group.evidence


def test_the_slot_field_reads_its_length_where_the_group_compares_it(
    four_slots: tuple[MeshData, dict[str, Feature], dict[str, str]],
) -> None:
    """Feld und Gruppe lesen dieselbe Kennzahl: am Langloch die Länge, nicht die Breite."""
    from app.core.perceive.actions import feature_value_source

    _mesh, features, names = four_slots
    slot = features[names["reference"]]

    assert feature_value_source("slot_length", slot) == ("length", None)
    assert feature_value_source("slot_angle", slot) == ("direction", None)
    hole = Feature(id="hole_1", kind="hole", provenance="detected", params={"diameter": 5.0})
    assert feature_value_source("slot_length", hole) == ("diameter", None), (
        "an einer runden Bohrung gibt es keine Länge; das Feld liest ihren Durchmesser"
    )


def test_a_different_extent_is_different_without_measuring_a_triangle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zwei Ausschnitte mit verschiedenen Hüllquadern sind verschieden — ohne Dreiecksmessung.

    Eine notwendige Bedingung der Flächengleichheit: Liegt jede Ecke des einen
    höchstens um die Sehnenhöhe neben den Dreiecken des anderen, stimmen die
    Hüllquader bis auf die Sehnenhöhe überein. An den 20 Wülsten von
    ``build_tray_v3.step`` kosteten die Vergleiche, die am Ende „verschieden"
    sagten, 180 ms je Klick (RM-181).
    """
    whole = trimesh.creation.icosphere(subdivisions=2, radius=5.0)
    cap = whole.slice_plane((0.0, 0.0, 2.0), (0.0, 0.0, 1.0))

    def patch_of(body: trimesh.Trimesh) -> object:
        points = np.asarray(body.vertices, dtype=float)
        corners = np.asarray(body.faces, dtype=np.int64)
        return relations._SurfacePatch(points=points, triangles=points[corners], corners=corners)

    measured: list[int] = []
    original = relations._distance_to_surface

    def counted(*args: object, **kwargs: object) -> object:
        measured.append(1)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(relations, "_distance_to_surface", counted)

    assert not relations._same_surface_patch(patch_of(whole), patch_of(cap))  # type: ignore[arg-type]
    assert measured == [], "verschieden schon an den Hüllquadern"
    assert relations._same_surface_patch(patch_of(whole), patch_of(whole.copy()))  # type: ignore[arg-type]
