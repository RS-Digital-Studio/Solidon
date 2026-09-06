"""Fein vernetzte Senkbohrungen behalten ihre Übergänge und bewegen sich ganz."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive.features import _curved_faces, _large_facet_faces, detect
from app.core.perceive.relations import (
    bore_and_widening_at,
    cavity_chain_at,
    cavity_chain_state_at,
    cavity_chains,
)
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject


def _stepped_bore(*, rings: int = 9, counterbore_depth: float = 8.5) -> MeshData:
    """Ø6 × 6, 90°-Übergang auf Ø11 und eine Zylindersenkung darüber.

    Neun Höhenstreifen mit je 180 Segmenten ergeben dieselben 3240
    Übergangsdreiecke wie die vier Schraublöcher des Gartenhalters. Die
    Flächen ändern sich bei weiterer Unterteilung geometrisch nicht.
    """
    height = 8.5 + counterbore_depth
    profile = [[12.0, 0.0], [12.0, height], [5.5, height], [5.5, 8.5]]
    profile.extend(
        [float(radius), float(z)]
        for radius, z in zip(
            np.linspace(5.5, 3.0, rings + 1)[1:],
            np.linspace(8.5, 6.0, rings + 1)[1:],
            strict=True,
        )
    )
    profile.extend([[3.0, 0.0], profile[0]])
    return MeshData.of(trimesh.creation.revolve(profile, sections=180))


def _shouldered_bore(*, conical: bool = True, curved_shoulder: bool = False) -> MeshData:
    """Eine größere Aufweitung lässt eine echte Ringstufe zur Senkung stehen."""
    profile = [[12.0, 0.0], [12.0, 17.0], [5.75, 17.0], [5.75, 8.5]]
    if curved_shoulder:
        profile.append([5.625, 8.6])
    profile.append([5.5 if conical else 3.0, 8.5])
    if conical:
        profile.append([3.0, 6.0])
    profile.extend([[3.0, 0.0], profile[0]])
    return MeshData.of(trimesh.creation.revolve(profile, sections=64))


@pytest.mark.parametrize("conical", [False, True])
@pytest.mark.parametrize("rotated", [False, True])
def test_a_flat_annular_shoulder_keeps_the_complete_cavity(conical: bool, rotated: bool) -> None:
    """Eine belegte Ringstufe verbindet dieselbe Bohrung auch nach Drehung."""
    mesh = _shouldered_bore(conical=conical)
    if rotated:
        body = mesh.raw.copy()
        body.apply_transform(trimesh.transformations.rotation_matrix(0.71, [1.0, 2.0, 3.0]))
        body.apply_translation([27.0, -41.0, 13.0])
        mesh = MeshData.of(body)
    assert mesh.is_watertight
    features = detect(mesh)
    cavities = {
        key: feature for key, feature in features.items() if feature.kind in {"hole", "cone"}
    }
    assert len(cavities) == (3 if conical else 2)
    chains = cavity_chains(features, mesh)
    assert len(chains) == 1
    assert {feature.id for feature in chains[0]} == set(cavities)
    for feature in cavities.values():
        assert cavity_chain_state_at(feature, features, mesh) == (chains[0], True)
        assert cavity_chain_at(feature, dict(reversed(list(features.items()))), mesh) == chains[0]


def test_an_ambiguous_owner_at_a_shoulder_never_becomes_a_single_bore() -> None:
    """Doppelte Ringbelegung bleibt auch über eine ebene Schulter mehrdeutig."""
    mesh = _shouldered_bore()
    features = detect(mesh)
    narrow = min(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    wide = max(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    duplicate = replace(wide, id="duplicate")
    ambiguous = {**features, duplicate.id: duplicate}
    assert cavity_chain_state_at(narrow, ambiguous, mesh) == (None, True)
    assert cavity_chain_state_at(wide, ambiguous, mesh) == (None, True)


@pytest.mark.parametrize("damaged", [False, True])
def test_only_a_complete_flat_annulus_connects_the_sections(damaged: bool) -> None:
    """Ein Buckel oder ein offener Ring wird nicht als ebene Schulter überbrückt."""
    from app.core.perceive.relations import _cavity_links

    mesh = _shouldered_bore(curved_shoulder=not damaged)
    body = mesh.raw.copy()
    if damaged:
        shoulder = np.flatnonzero(np.isclose(body.triangles[:, :, 2], 8.5).all(axis=1))
        keep = np.ones(len(body.faces), dtype=bool)
        keep[shoulder[0]] = False
        body.update_faces(keep)
        mesh = MeshData.of(body)
    features = detect(mesh)
    holes = {key: feature for key, feature in features.items() if feature.kind == "hole"}
    assert len(holes) == 2
    graph, _invalid, _touching = _cavity_links(holes, mesh)
    assert all(not adjacent for adjacent in graph.values())


def test_moving_a_shouldered_cavity_preserves_all_sections(profile: Profile) -> None:
    """Der neue Zusammenhang wird auch vom geometrischen Bearbeitungsweg erfüllt."""
    mesh = _shouldered_bore()
    features = detect(mesh)
    cavity = next(iter(cavity_chains(features, mesh)))
    selected = cavity[-1]
    centre = np.asarray(selected.params["centre"], dtype=float)
    source = SceneObject(id="part", name="Stufenbohrung", mesh=mesh, features=features)
    spec = REGISTRY.get("move_feature")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=selected.id, x=centre[0] + 1.0, y=centre[1], z=centre[2]),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda _value, _message: None,
            ask=lambda _question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    moved = result.outputs[0]
    assert moved.mesh.is_watertight
    assert moved.mesh.volume == pytest.approx(mesh.volume, abs=0.01)
    fresh = detect(moved.mesh)
    chain = next(iter(cavity_chains(fresh, moved.mesh)))
    assert len(chain) == 3
    assert [f.params["centre"][0] for f in chain] == pytest.approx([1.0] * 3, abs=0.01)


@pytest.mark.parametrize("rings", [1, 9])
def test_subdivision_preserves_the_conical_transition(rings: int) -> None:
    """Zusätzliche Dreiecke dürfen die unveränderte Senkung nicht entfernen."""
    mesh = _stepped_bore(rings=rings)
    assert mesh.raw.is_watertight
    features = detect(mesh)
    cones = [feature for feature in features.values() if feature.kind == "cone"]
    holes = [feature for feature in features.values() if feature.kind == "hole"]
    assert len(holes) == 2
    assert len(cones) == 1, "the complete conical transition must remain recognised"
    assert len(cones[0].face_indices) == 360 * rings
    assert float(cones[0].params["diameter"]) == pytest.approx(11.0, abs=0.01)
    assert float(cones[0].params["angle"]) == pytest.approx(90.0, abs=0.02)


@pytest.mark.parametrize("selected_part", [0, 1, 2])
@pytest.mark.parametrize("counterbore_depth", [1.5, 8.5])
def test_every_part_moves_the_whole_cavity(
    profile: Profile, selected_part: int, counterbore_depth: float
) -> None:
    """Bohrung, Übergang und Zylindersenkung gehören zu einem Hohlraum."""
    mesh = _stepped_bore(counterbore_depth=counterbore_depth)
    features = detect(mesh)
    cavity = sorted(
        (feature for feature in features.values() if feature.kind in {"hole", "cone"}),
        key=lambda feature: float(feature.params["centre"][2]),
    )
    assert len(cavity) == 3
    selected = cavity[selected_part]
    centre = np.asarray(selected.params["centre"], dtype=float)
    source = SceneObject(id="part", name="Senkbohrung", mesh=mesh, features=features)
    spec = REGISTRY.get("move_feature")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=selected.id, x=centre[0] + 1.0, y=centre[1], z=centre[2]),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda _value, _message: None,
            ask=lambda _question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    moved = result.outputs[0]
    assert moved.mesh.raw.is_watertight
    assert moved.mesh.volume == pytest.approx(mesh.volume, abs=0.01)
    for feature in cavity:
        expected = np.asarray(feature.params["centre"], dtype=float) + np.array([1.0, 0.0, 0.0])
        assert moved.features[feature.id].params["centre"] == pytest.approx(expected)
    fresh = detect(moved.mesh)
    fresh_cavity = [feature for feature in fresh.values() if feature.kind in {"hole", "cone"}]
    assert len(fresh_cavity) == 3
    assert [float(feature.params["centre"][0]) for feature in fresh_cavity] == pytest.approx(
        [1.0] * 3, abs=0.01
    )


def test_the_chain_is_independent_of_selection_and_mapping_order() -> None:
    """Jede Auswahl liefert dieselbe komplette Kette, nicht ein zufälliges Paar."""
    mesh = _stepped_bore()
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    assert len(chain) == 3
    assert [feature.kind for feature in chain] == ["hole", "cone", "hole"]
    for ordering in (features, dict(reversed(list(features.items())))):
        assert cavity_chains(ordering, mesh) == (chain,)
        for feature in chain:
            assert cavity_chain_at(feature, ordering, mesh) == chain
            assert bore_and_widening_at(feature, ordering, mesh=mesh) is None


def test_pairwise_axis_tolerance_never_truncates_a_chain() -> None:
    """Paarweise zulässige Fitfehler ergeben keine andere Gruppe je Auswahlseite."""
    mesh = _stepped_bore()
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    altered = dict(features)
    for feature, angle in zip(chain, (0.0, 1.9, 3.8), strict=True):
        tilt = math.radians(angle)
        altered[feature.id] = replace(
            feature, params={**feature.params, "axis": (math.sin(tilt), 0.0, math.cos(tilt))}
        )
    expected = next(iter(cavity_chains(altered, mesh)))
    assert len(expected) == 3
    for ordering in (altered, dict(reversed(list(altered.items())))):
        assert cavity_chains(ordering, mesh) == (expected,)
        for feature in expected:
            assert cavity_chain_at(feature, ordering, mesh) == expected


def test_axis_fit_tolerance_is_independent_of_mapping_order() -> None:
    """Beide Achslinien müssen denselben Randverbund gleich beurteilen."""
    mesh = _stepped_bore(rings=1)
    features = detect(mesh)
    bore, transition = next(iter(cavity_chains(features, mesh)))[:2]
    bore = replace(
        bore,
        params={
            **bore.params,
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 6.0,
        },
    )
    tilt = math.radians(-1.9)
    transition = replace(
        transition,
        params={
            **transition.params,
            "centre": (0.7, 0.0, 5.0),
            "axis": (math.sin(tilt), 0.0, math.cos(tilt)),
        },
    )

    forward = cavity_chains({bore.id: bore, transition.id: transition}, mesh)
    backward = cavity_chains({transition.id: transition, bore.id: bore}, mesh)

    assert forward == backward == ()


def test_separate_coaxial_blind_bores_do_not_form_a_chain() -> None:
    """Ein Millimeter Material trennt zwei Sacklöcher trotz passender Mitten."""
    profile = [
        [12.0, 0.0],
        [12.0, 8.5],
        [5.5, 8.5],
        [5.5, 7.0],
        [0.0, 7.0],
        [0.0, 6.0],
        [3.0, 6.0],
        [3.0, 0.0],
        [12.0, 0.0],
    ]
    mesh = MeshData.of(trimesh.creation.revolve(profile, sections=180))
    assert mesh.raw.is_watertight
    features = detect(mesh)
    holes = [feature for feature in features.values() if feature.kind == "hole"]
    assert len(holes) == 2
    assert cavity_chains(features, mesh) == ()
    for feature in holes:
        assert cavity_chain_at(feature, features, mesh) is None
        assert cavity_chain_state_at(feature, features, mesh) == (None, False)
        assert bore_and_widening_at(feature, features, mesh=mesh) is None


def test_duplicate_candidates_at_a_ring_are_ambiguous() -> None:
    """Zwei Flächenbehauptungen am selben Rand werden nicht nach ID gewählt."""
    mesh = _stepped_bore()
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    duplicate = replace(chain[1], id="duplicate")
    ambiguous = {**features, duplicate.id: duplicate}
    assert cavity_chains(ambiguous, mesh) == ()
    for feature in chain:
        assert cavity_chain_at(feature, ambiguous, mesh) is None
        assert cavity_chain_state_at(feature, ambiguous, mesh) == (None, True)


def test_unindexed_triangles_use_the_same_topology_as_detection() -> None:
    """Ein STL ohne geteilte Eckindizes verliert seine gemeinsamen Randringe nicht."""
    body = _stepped_bore().raw.copy()
    body.unmerge_vertices()
    mesh = MeshData.of(body)
    features = detect(mesh)
    chains = cavity_chains(features, mesh)
    assert len(chains) == 1
    assert len(chains[0]) == 3


def test_invalid_face_indices_do_not_connect_a_cavity() -> None:
    """Veraltete Netzausschnitte erzeugen weder eine Kette noch einen Indexfehler."""
    mesh = _stepped_bore()
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    invalid = replace(chain[1], face_indices=(len(mesh.raw.faces),))
    stale = {**features, invalid.id: invalid}
    assert cavity_chains(stale, mesh) == ()
    for feature in stale.values():
        assert cavity_chain_at(feature, stale, mesh) is None


def test_a_thread_cap_stays_planar_despite_its_curved_neighbours() -> None:
    """Die echte Bolzen-Deckfläche darf nicht mit den Mantelstreifen verschwinden."""
    from app.core.knowledge.parts.fasteners import ThreadParams, printed_thread

    mesh = as_mesh_data(printed_thread(ThreadParams(size="M5", length=12.0, play=0.0)).mesh)
    body = mesh.raw
    top = np.flatnonzero(
        np.isclose(body.triangles[:, :, 2], body.bounds[1, 2]).all(axis=1)
        & np.isclose(body.face_normals[:, 2], 1.0)
    )
    assert len(top) >= 8
    assert set(top) & _curved_faces(body), "the cap must touch a curved neighbour"
    assert set(top) <= _large_facet_faces(body)


def test_resizing_a_chain_does_not_offer_an_incomplete_single_widening() -> None:
    """Die Folge wird mit allen Abschnitten genannt, ohne falschen Einzel-Mitzugknopf."""
    from app.core.geom.prepare_ops import _widening_findings

    mesh = _stepped_bore()
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    source = SceneObject(id="part", name="Senkbohrung", mesh=mesh, features=features)
    findings = _widening_findings(source, chain[0], 6.2)
    assert len(findings) == 1
    assert set(findings[0].feature_ids) == {feature.id for feature in chain}
    assert {action.id for action in findings[0].suggestions} == {"correct_input"}
    swallowed = _widening_findings(source, chain[0], 12.0)
    assert swallowed[0].severity == "warning"
    assert _widening_findings(source, chain[1], 10.8)[0].severity == "info"
    assert _widening_findings(source, chain[2], 11.2)[0].severity == "info"


def test_an_ambiguous_cavity_is_not_moved_in_parts(profile: Profile) -> None:
    """Eine doppelte Randbelegung darf nicht auf Einzelbewegung zurückfallen."""
    mesh = _stepped_bore()
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    duplicate = replace(chain[1], id="duplicate")
    ambiguous = {**features, duplicate.id: duplicate}
    source = SceneObject(id="part", name="Senkbohrung", mesh=mesh, features=ambiguous)
    selected = chain[0]
    centre = np.asarray(selected.params["centre"], dtype=float)
    spec = REGISTRY.get("move_feature")

    with pytest.raises(ValidationError) as refused:
        spec.fn(
            OpContext(
                scene=Scene(objects={source.id: source}),
                inputs=[source],
                params=spec.params(
                    at_feature=selected.id,
                    x=centre[0] + 1.0,
                    y=centre[1],
                    z=centre[2],
                ),
                profile=profile,
                quality="fine",
                seed=7,
                progress=lambda _value, _message: None,
                ask=lambda _question, choices: choices[0],
                cancelled=NeverCancelled(),
            )
        )

    assert refused.value.field == "at_feature"
    assert refused.value.constraint == "not_movable"
    assert {action.id for action in refused.value.suggestions} == {"correct_input", "cancel"}
