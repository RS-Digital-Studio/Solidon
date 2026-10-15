"""Welche Handlung am Merkmal beim heutigen Stand angeboten wird (FD-31, FD-99).

Übernommen ohne Änderung bliebe bei ihr alles, wie es ist: Die Felder tragen,
was das Merkmal heute misst, ein Weg beginnt bei null, oder ein Schritt kommt
mit seinen gespeicherten Werten. An ihr wartet *Übernehmen* auf die erste
Änderung. Eine Handlung, deren Vorgabe selbst etwas tut — drehen um 90°, eine
Kopie daneben, ein Langloch aus einer runden Bohrung —, bleibt sofort
übernehmbar. Ohne Fenster: Gefragt werden die Felder, die der Kern anbietet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.geom.mesh import read_mesh
from app.core.perceive import features
from app.ui.first_change import offered_unchanged
from app.ui.panels import feature_answers

MESHES = Path(__file__).parent / "data" / "meshes"


def _offers(name: str, kind: str) -> dict[str, bool]:
    load_operations()
    mesh = read_mesh((MESHES / name).read_bytes(), ".stl")
    found = features.detect(mesh)
    key, feature = next((key, value) for key, value in found.items() if value.kind == kind)
    answers = feature_answers(key, feature, found, mesh)
    return {str(action.op): offered_unchanged(action) for action in answers.actions if action.op}


@pytest.mark.parametrize(
    ("mesh", "kind", "expected"),
    [
        (
            "plate_holes.stl",
            "hole",
            {
                "move_feature": True,
                "resize_hole": True,
                "slot_hole": False,
                "rotate_feature": False,
                "duplicate_feature": False,
                "remove_feature": False,
            },
        ),
        ("plate_holes.stl", "face", {"push_face": True}),
        (
            "post_with_fillet.stl",
            "pin",
            {
                "move_feature": True,
                "resize_feature": True,
                "rotate_feature": False,
                "duplicate_feature": False,
                "remove_feature": False,
            },
        ),
        ("plate_coarse_slots.stl", "slot", {"slot_hole": True, "resize_hole": True}),
    ],
)
def test_an_offer_at_todays_state_waits_for_a_change(
    mesh: str, kind: str, expected: dict[str, bool]
) -> None:
    offers = _offers(mesh, kind)
    assert {op: offers[op] for op in expected} == expected, offers


def test_a_pin_whose_size_is_not_certain_still_starts_at_its_size() -> None:
    """Die Messherkunft fehlt dort (``measurement`` leer), der Wert ist trotzdem der heutige."""
    assert _offers("pocket_with_pin.stl", "pin")["resize_feature"] is True
