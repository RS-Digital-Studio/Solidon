"""Aufnahme vor Wirkung und vor dem Aufräumen des zweiten nativen Probelaufs."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.bench_fakes import FakeClick, FakePorts, FakeTimer, FakeWidget, run_machine
from tools import function_bench, function_capture, function_judges, function_surface
from tools.function_machine import Step
from tools.function_samples import sample_context
from tools.function_setup import Variant
from tools.function_walk import Walk


@pytest.mark.parametrize("kind", ["sperrgrund", "grenzablehnung"])
@pytest.mark.parametrize("way_out", [True, False])
def test_dead_ends_respect_a_measured_way_out(kind: str, way_out: bool) -> None:
    """E7 und V5 unterscheiden denselben gemessenen Ausweg von einer Sackgasse."""
    protocol = {
        "matrix": {},
        "empty_states": [],
        "messages": [
            {"kind": kind, "text": "Warten bis fertig", "actions": [], "way_out": way_out}
        ],
    }
    for key in ("E7", "V5"):
        outcome = function_judges.CRITERION_JUDGES[key](protocol, sample_context())
        assert outcome is not None
        assert bool(outcome.issues) is not way_out


def test_an_actual_message_without_an_action_stays_a_dead_end() -> None:
    """Ein beliebiges way_out darf eine echte Meldung nicht grün machen."""
    protocol = {
        "matrix": {},
        "empty_states": [],
        "messages": [{"kind": "meldung", "text": "Fehler", "actions": [], "way_out": True}],
    }
    for key in ("E7", "V5"):
        assert function_judges.CRITERION_JUDGES[key](protocol, sample_context()).issues


def test_a_finding_surface_is_measured_before_its_action(monkeypatch) -> None:
    """Echter Wegautomat: zuerst messen, danach muss auch die Soforthandlung wirken."""
    timer = FakeTimer()
    target = "finding.action:place_on_bed"
    widgets = [FakeWidget(name) for name in ("Reiter", "Befund", "Handlung")]
    ports = FakePorts(
        timer,
        {
            target: [
                FakeClick((0, 0, 20, 20), "left", why, widget)
                for why, widget in zip(("reiter", "klappe", "ziel"), widgets, strict=True)
            ]
        },
    )
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": target, "target": target, "source": "befundhandlung"}
    flow.variant = Variant.of({"set": "dunkel"})
    flow.data = {}
    flow.window = object()
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: None)
    flow.walker = Walk(ports, [], 0)
    flow.surface = lambda: widgets[-1]
    flow.claim_surface = lambda root: None
    captured = []
    flow.capture_surface = lambda root: captured.append([name for name, _, _ in ports.pressed])
    flow.picture = lambda name: None
    flow.still_step = lambda name, root: Step(name, lambda machine: None)
    flow.run_steps = lambda label, steps: run_machine(timer, steps).error is None
    flow.phase_surface()
    assert captured == [["Reiter", "Befund"]]
    assert [name for name, _, _ in ports.pressed] == ["Reiter", "Befund", "Handlung"]
    assert flow.walker.steps[-1]["button"] == "left"


@pytest.mark.parametrize("stop", [True, False])
@pytest.mark.parametrize("covered", [True, False])
def test_stopping_before_the_target_keeps_the_hit_test(stop: bool, covered: bool) -> None:
    """Ein verdecktes Ziel bleibt rot; ohne Aufnahmehalt fällt der normale Zielklick."""
    timer = FakeTimer()
    target, cover = FakeWidget("Ziel"), FakeWidget("Deckung")
    ports = FakePorts(
        timer,
        {"target": [FakeClick((0, 0, 20, 20), "left", "ziel", target)]},
        under=lambda click: cover if covered else target,
    )
    walker = Walk(ports, [], 0)
    machine = run_machine(timer, [walker.step("target", stop_before_target=stop)])
    assert bool(machine.finding) is covered
    assert bool(ports.pressed) is (not covered and not stop)


def test_fault_picture_is_taken_while_its_message_is_still_visible(monkeypatch) -> None:
    """Die echte Fehlphase liest und fotografiert vor dem modalen Escape des Automaten."""
    visible = {"value": True}
    flow = object.__new__(function_bench.FunctionFlow)
    flow.spec = {"fault_case": {"expected": "meldung"}}
    flow.row = {"target": "menu:parameter"}
    flow.apply_target = None
    flow.session = SimpleNamespace(last_result=None)
    flow.window = object()
    flow.data = {"messages": None, "images": []}
    # Ohne graues Ziel nimmt der Fehlfall kein Bild des Sperrgrunds auf (FD-149).
    flow.widget = lambda name: None
    flow.folder = flow.out = Path("cases")
    flow.fault_scene = lambda key: True
    flow.path_steps = list
    flow.input_steps = lambda inputs: []
    flow.until_step = lambda name, condition: Step(name, lambda machine: None)
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: None)
    monkeypatch.setattr(
        function_surface,
        "fault_messages",
        lambda window, targets: (
            [{"kind": "meldung", "text": "Ungültiger Name", "actions": []}]
            if visible["value"]
            else []
        ),
    )
    monkeypatch.setattr(function_capture, "visible_texts", lambda root: [])
    pictures = []
    flow.picture = lambda name: pictures.append((name, visible["value"]))

    def run(label, steps):
        for step in steps:
            step.act(None)
        visible["value"] = False
        return True

    flow.run_steps = run
    flow.phase_fault()
    assert pictures == [("04-fehlfall", True)]
    assert flow.data["messages"][0]["text"] == "Ungültiger Name"


def test_the_reason_of_a_grey_target_is_pictured_in_the_fault_phase(monkeypatch, tmp_path) -> None:
    """FD-149: Neben ``04-fehlfall`` steht der Sperrgrund jedes grauen Ziels als eigenes Bild.

    Vorher gab es ``function_tooltips.reason_pictures``, aber der Fehlfall rief es
    nicht: Lauf 002 zeigte unter dem grauen *Auf das Bett setzen* nur den Knopf.
    """
    from tools import function_tooltips

    folder = tmp_path / "cases" / "002"
    flow = object.__new__(function_bench.FunctionFlow)
    flow.spec = {"fault_case": {"expected": "sperrgrund"}}
    flow.row = {"target": "finding.action:place_on_bed"}
    flow.apply_target = None
    flow.session = SimpleNamespace(last_result=None)
    flow.window = object()
    flow.folder, flow.out = folder, tmp_path
    flow.data = {"messages": None, "images": []}
    flow.fault_scene = lambda key: True
    flow.path_steps = list
    flow.input_steps = lambda inputs: []
    flow.until_step = lambda name, condition: Step(name, lambda machine: None)
    flow.widget = lambda name: f"Widget {name}"
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: None)
    monkeypatch.setattr(
        function_surface,
        "fault_messages",
        lambda window, targets: [{"kind": "sperrgrund", "text": "Grund", "actions": []}],
    )
    monkeypatch.setattr(function_capture, "visible_texts", lambda root: [])
    asked = []

    def reason_pictures(find, targets, where, out):
        asked.append(([find(name) for name in targets], where, out))
        return ["cases/002/04-fehlfall-grund-1.png"]

    monkeypatch.setattr(function_tooltips, "reason_pictures", reason_pictures)
    flow.picture = lambda name: flow.data["images"].append(f"cases/002/{name}.png")

    def run(label, steps):
        for step in steps:
            step.act(None)
        return True

    flow.run_steps = run
    flow.phase_fault()
    assert asked == [(["Widget finding.action:place_on_bed"], folder, tmp_path)]
    assert flow.data["images"] == [
        "cases/002/04-fehlfall.png",
        "cases/002/04-fehlfall-grund-1.png",
    ]
