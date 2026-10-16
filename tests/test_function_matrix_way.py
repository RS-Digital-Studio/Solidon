"""Die Auswahlmatrix geht denselben Weg wie der Hauptweg (FD-100, RM-737, Prüfpunkt 13).

``phase_matrix`` klickte je Stufe nur die Auswahl und fragte dann das Ziel ab.
*Auf das Bett setzen* hieß so an allen Stufen „kein Bedienelement trägt dieses
Kennzeichen“: Der Befund, an dem die Handlung steht, war nie gewählt (Lauf
002). *Bohrung ändern* hieß am Merkmal „QToolButton steht nicht da“, obwohl die
Handlung in der Maßgruppe im Bild stand (Lauf 001). Jetzt folgt nach der
Auswahl der Weg der Zeile, und die Maßgruppe im Bild ist der Ort der Handlung;
der Gegenfall „fehlt“ bleibt.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.bench_fakes import FakePorts, FakeTimer
from tools import function_bench, function_surface, function_walk
from tools.function_protocol import empty_protocol


def _flow(row: dict[str, Any], features: dict[str, str]) -> Any:
    """Ein Fall ohne Fenster für die Matrix: zwei Körper, die Merkmale am ersten."""
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = row
    flow.spec = dict(row.get("spec") or {})
    flow.data = empty_protocol(row, {}, {})
    first = SimpleNamespace(
        features={name: SimpleNamespace(kind=kind) for name, kind in features.items()}
    )
    second = SimpleNamespace(features={})
    flow.session = SimpleNamespace(
        last_result=SimpleNamespace(
            scene=SimpleNamespace(objects={"obj_1": first, "obj_2": second})
        )
    )
    flow.walker = function_walk.Walk(FakePorts(FakeTimer(), {}), [], 0.0)
    flow.ports = flow.walker.ports
    flow.reset = lambda: True
    flow.offer_state = lambda target, label: {"state": "angeboten", "reason": "", "effective": True}
    return flow


def _walked(flow: Any) -> dict[str, list[str]]:
    walked: dict[str, list[str]] = {}

    def run_steps(label: str, steps: list[Any]) -> bool:
        walked[label] = [step.name for step in steps]
        return True

    flow.run_steps = run_steps
    flow.phase_matrix()
    return walked


def test_every_stage_walks_to_the_finding_before_it_asks_for_its_action() -> None:
    """Nach jeder Auswahlstufe der Befund, dann die Befundhandlung — wie auf dem Hauptweg."""
    target = "finding.action:place_on_bed"
    row = {
        "id": target,
        "target": target,
        "route": [{"target": "finding:arrange.below_bed", "button": "left", "modifier": ""}],
        "spec": {},
    }
    walked = _walked(_flow(row, {"face_1": "face", "face_2": "face"}))
    assert walked["matrix ohne auswahl"] == [
        "taste auswahl leeren",
        "weg zu finding:arrange.below_bed",
        f"{target} steht",
    ], walked
    assert walked["matrix mehrere_koerper auswahl"] == [
        "weg zu tree.row:obj_1",
        "weg zu tree.row:obj_2",
        "weg zu finding:arrange.below_bed",
        f"{target} steht",
    ], walked


def test_the_feature_stages_choose_the_feature_of_the_row_and_its_kind() -> None:
    """„Ein Merkmal“ ist die Bohrung der Zeile, „mehrere“ dazu eine zweite Bohrung.

    Vorher wählte die Matrix das erste Merkmal der Szene, gleich welcher Art,
    und die Auswahl der Zeile (``Row.route``) zählte nicht; ein Zielklick der
    Zeile gehört nicht zum Weg der Stufe.
    """
    row = {
        "id": "resize_hole",
        "target": "feature:resize_hole",
        "route": [{"target": "tree.row:obj_1.hole_2", "button": "left", "modifier": ""}],
        "spec": {"inputs": {"feature.field:resize_hole.diameter": 8.0}},
    }
    walked = _walked(_flow(row, {"face_1": "face", "hole_1": "hole", "hole_2": "hole"}))
    assert walked["matrix ein_merkmal auswahl"] == [
        "weg zu tree.row:obj_1.hole_2",
        "feature:resize_hole steht",
    ], walked
    assert walked["matrix mehrere_merkmale auswahl"] == [
        "weg zu tree.row:obj_1.hole_2",
        "weg zu tree.row:obj_1.hole_1",
        "feature:resize_hole steht",
    ], walked


@pytest.mark.parametrize("in_view", [True, False])
def test_an_action_in_the_view_is_offered_there_and_a_missing_one_stays_missing(
    monkeypatch: Any, in_view: bool
) -> None:
    """Die Maßgruppe im Bild trägt die Handlung: angeboten, ohne Klick, Ort Ansicht.

    Gegenprobe: Steht sie weder im Bild noch im Merkmalfenster, fehlt sie — der
    Gegenfall der Stufen, an denen *Bohrung ändern* nicht gilt.
    """
    row = {
        "id": "resize_hole",
        "target": "feature:resize_hole",
        "route": [{"target": "tree.row:obj_1.hole_1", "button": "left", "modifier": ""}],
        "spec": {"inputs": {"feature.field:resize_hole.diameter": 8.0}},
    }
    flow = _flow(row, {"hole_1": "hole"})
    del flow.offer_state
    flow.window = SimpleNamespace(feature_panel=SimpleNamespace(measure_op="resize_hole"))
    monkeypatch.setattr(function_surface, "feature_in_view", lambda window, target: in_view)
    monkeypatch.setattr(
        function_surface,
        "_shown",
        lambda window, name: object() if in_view and name.startswith("measure.") else None,
    )
    monkeypatch.setattr(function_surface, "grey_reason", lambda window, name: None)
    state = flow.offer_state("feature:resize_hole", "matrix ein_merkmal")
    if in_view:
        assert state == {"state": "angeboten", "reason": "", "effective": True, "place": "ansicht"}
    else:
        assert state["state"] == "fehlt", state
