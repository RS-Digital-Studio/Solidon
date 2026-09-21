"""Angeschnittene Bohrungen heißen an beiden Kernen gleich (§21, P1.5).

Zwei überlappende Bohrungen lassen je einen Mantel von 315 Grad stehen. Am
exakten Körper war das eine Verrundung (die Naht teilte einen Mantel sogar in
zwei), am Netz eine ganze Bohrung — und beide Antworten waren falsch: Es ist
eine **angeschnittene** Bohrung, die an einer fremden Höhlung endet, ohne Kette
und ohne eigenen Körper. Der Winkel entscheidet den Namen, die Nachbarschaft
die Handlung.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData
from app.core.geom.prepare_ops import NO_OWN_BODY
from app.core.perceive import features as mesh_features
from app.core.perceive.actions import actions_for
from app.core.perceive.features import detect, span_about
from app.core.perceive.relations import CavityState, cavity_chain_state_at
from app.core.types import Feature, FeatureId
from tests.helpers import exact_kernel

RADIUS = 3.0
#: Achsabstand, bei dem jeder Mantel genau 45 Grad an den anderen verliert.
DISTANCE = 2.0 * RADIUS * math.cos(math.pi / 8.0)
BODY_OPS = ("move_feature", "duplicate_feature", "rotate_feature", "remove_feature")


def _overlapping_bores() -> Any:
    edit = exact_kernel()
    body = edit.box(40.0, 30.0, 10.0)
    for x in (-DISTANCE / 2.0, DISTANCE / 2.0):
        body = edit.cut_bore(
            body, position=(x, 0.0, 5.0), direction=(0.0, 0.0, 1.0), diameter=6.0, depth=10.0
        )
    expected = 12000.0 - 315.0 * math.pi / 2.0 - 45.0 * math.sqrt(2.0)
    assert body.volume == pytest.approx(expected, rel=1e-9)
    return body


def _both_readings(body: Any) -> dict[str, tuple[dict[FeatureId, Feature], MeshData]]:
    from app.core.brep.features import features_of

    mesh = body.to_mesh(deflection=0.05)
    return {"nativ": (features_of(body), body.mesh), "netz": (detect(mesh), mesh)}


def _holes(found: dict[FeatureId, Feature]) -> list[Feature]:
    return sorted(
        (entry for entry in found.values() if entry.kind == "hole"),
        key=lambda entry: float(entry.params["centre"][0]),
    )


def test_the_two_thresholds_are_one_number() -> None:
    """Die Umfangsschwelle steht einmal — am Netz in Grad, am exakten Körper als Anteil."""
    from app.core.brep import features as exact_features

    assert pytest.approx(mesh_features.FULL_TURN_SPAN) == exact_features.FULL_TURN * 360.0


@pytest.mark.parametrize("reading", ["nativ", "netz"])
def test_two_overlapping_bores_are_two_cut_open_bores_on_both_cores(reading: str) -> None:
    """Je 315 Grad Restmantel: eine Bohrung mit ``partial``, durchgehend, Ø 6 — nicht
    drei Verrundungen und nicht zwei ganze Bohrungen."""
    body = _overlapping_bores()
    found, mesh = _both_readings(body)[reading]

    kinds = sorted(entry.kind for entry in found.values())
    assert kinds == ["face"] * 6 + ["hole", "hole"], (reading, kinds)
    holes = _holes(found)
    for hole, x in zip(holes, (-DISTANCE / 2.0, DISTANCE / 2.0), strict=True):
        assert hole.params["partial"] is True
        assert hole.params["through"] is True
        assert float(hole.params["diameter"]) == pytest.approx(6.0, abs=1e-6)
        assert np.allclose(np.abs(np.asarray(hole.params["axis"], dtype=float)), (0, 0, 1))
        assert float(hole.params["centre"][0]) == pytest.approx(x, abs=1e-6)
        assert float(hole.params["centre"][1]) == pytest.approx(0.0, abs=1e-6)
        span = span_about(
            mesh.raw,
            np.asarray(hole.params["axis"], dtype=float),
            np.asarray(hole.params["centre"], dtype=float),
            hole.face_indices,
        )
        assert span == pytest.approx(315.0, abs=1.0), (reading, span)
        assert all(patch.kind == "cylinder" for patch in hole.surface_patches)
        covered = {index for patch in hole.surface_patches for index in patch.face_indices}
        assert covered == set(hole.face_indices), "der ganze Mantel trägt seinen Zylinder"
        assert mesh.raw.area_faces[list(hole.face_indices)].sum() == pytest.approx(
            RADIUS * 10.0 * 7.0 * math.pi / 4.0, rel=0.01
        )
    assert set(holes[0].face_indices).isdisjoint(holes[1].face_indices)


@pytest.mark.parametrize("reading", ["nativ", "netz"])
def test_a_cut_open_bore_touches_its_neighbour_and_has_no_own_body(reading: str) -> None:
    """Keine Kette, aber berührt: Versetzen, Verdoppeln, Drehen und Entfernen sagen
    mit dem Satz der Operation ab — an beiden Kernen, im Panel wie im Werkzeugbau."""
    load_operations()
    body = _overlapping_bores()
    found, mesh = _both_readings(body)[reading]
    for hole in _holes(found):
        state = cavity_chain_state_at(hole, found, mesh)
        assert state == CavityState(None, True, "ambiguous_cavity_chain"), (reading, hole.id)
        actions = actions_for(hole, found, mesh=mesh)
        refused = {action.title: action.reason for action in actions if action.op is None}
        offered = {action.op for action in actions if action.op is not None}
        assert not offered & set(BODY_OPS), (reading, offered)
        assert NO_OWN_BODY in refused.values(), (reading, refused)


def test_a_single_full_bore_is_neither_cut_open_nor_touched() -> None:
    """Die Gegenkontrolle: eine ganze Bohrung bleibt eine, mit ihren Handlungen."""
    load_operations()
    edit = exact_kernel()
    body = edit.cut_bore(
        edit.box(40.0, 30.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
    )
    for reading, (found, mesh) in _both_readings(body).items():
        (hole,) = _holes(found)
        assert "partial" not in hole.params, reading
        assert cavity_chain_state_at(hole, found, mesh) == CavityState(None, False, None), reading
        offered = {action.op for action in actions_for(hole, found, mesh=mesh)}
        assert "move_feature" in offered, reading


def test_a_bore_with_a_cross_hole_is_still_a_whole_bore() -> None:
    """Ein Querloch durch die Wand ist kein Anschnitt: Der Rand darum ist eine
    Schleife, keine zwei geraden Linien längs der Achse."""
    edit = exact_kernel()
    body = edit.cut_bore(
        edit.box(40.0, 30.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
    )
    body = edit.cut_bore(
        body, position=(0.0, 0.0, 5.0), direction=(1.0, 0.0, 0.0), diameter=2.0, depth=40.0
    )
    for reading, (found, _mesh) in _both_readings(body).items():
        big = [
            entry
            for entry in _holes(found)
            if float(entry.params["diameter"]) == pytest.approx(6.0, abs=1e-6)
        ]
        assert len(big) == 1, (reading, [entry.params for entry in _holes(found)])
        assert "partial" not in big[0].params, reading


def test_a_mesh_bore_cut_open_by_a_flat_side_is_partial_but_not_touched() -> None:
    """Am Rand geöffnet ohne Nachbarhöhlung: angeschnitten, aber niemand berührt sie —
    was daraus wird, sagt der Randweg (``open_slots_instead_of_fillets``), nicht
    diese Auskunft."""
    import trimesh

    plate = trimesh.creation.box(extents=(40.0, 30.0, 10.0))
    plate.apply_translation((0.0, 0.0, 5.0))
    # Ein Zylinder Ø 6, dessen Achse 2,8 mm vor der Seitenfläche y = 15 steht:
    # Es fehlt der Bogen 2·acos(2,8/3) = 42 Grad, 318 bleiben — über der Schwelle,
    # also eine Bohrung, und ihre zwei Schnittlinien laufen durch die Seitenfläche.
    cutter = trimesh.creation.cylinder(radius=RADIUS, height=40.0, sections=64)
    cutter.apply_translation((0.0, 15.0 - 2.8, 5.0))
    body = MeshData.of(trimesh.boolean.difference([plate, cutter]))
    found = detect(body)
    holes = _holes(found)
    assert len(holes) == 1, sorted(entry.kind for entry in found.values())
    (hole,) = holes
    span = span_about(
        body.raw,
        np.asarray(hole.params["axis"], dtype=float),
        np.asarray(hole.params["centre"], dtype=float),
        hole.face_indices,
    )
    assert 300.0 < span < 330.0, span
    assert hole.params.get("partial") is True
    assert cavity_chain_state_at(hole, found, body) == CavityState(None, False, None)
