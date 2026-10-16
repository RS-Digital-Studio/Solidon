"""Die Nachprüfung erhält echte Vorschauzeitlagen und ausgefallene Pixelquellen."""

from types import SimpleNamespace

import pytest

from tests.bench_fakes import FakeTimer, run_machine
from tools import function_bench, function_capture, function_judges, function_surface
from tools.function_machine import Step
from tools.function_protocol import empty_protocol
from tools.function_samples import sample_context


@pytest.mark.parametrize(
    "mode,delay", [("default", 0), ("default", 300), ("input", 0), ("input", 60), ("input", 180)]
)
def test_revision_keeps_an_already_completed_requested_preview(monkeypatch, mode, delay):
    """Echte Vorschauwartephase und echter Automat, nur Uhr und Oberfläche nachgestellt."""
    from app.core.scene import serialise

    timer = FakeTimer()
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": "drill_hole", "target": "operation:drill_hole", "kind": "operation"}
    flow.data = empty_protocol(flow.row, {}, {})
    flow.data["states"] = {"before": {"ops": [1]}, "applied": {"ops": [1, 2]}}
    flow.spec = {"inputs": {"field:diameter": 8}} if mode == "input" else {}
    flow.apply_target = "dialog.accept"
    document = SimpleNamespace(ops=["import"])
    flow.session = SimpleNamespace(project=SimpleNamespace(document=document), last_result=object())
    flow.window = SimpleNamespace(viewport=SimpleNamespace(difference=None))
    flow.idle = lambda: True
    visible = SimpleNamespace(isVisible=lambda: True)
    banner = SimpleNamespace(isVisible=lambda: True, legend=visible)
    accept = SimpleNamespace(isEnabled=lambda: True)
    flow.widget = lambda target: banner if target == "preview.banner" else accept
    applied = []

    def reset():
        document.ops = ["import"]
        flow.session.last_result = object()
        flow.window.viewport.difference = None
        return True

    def request(machine):
        timer.schedule(delay, lambda: setattr(flow.window.viewport, "difference", object()))

    def apply(machine):
        applied.append(timer.now)
        document.ops.append("resize")
        flow.session.last_result = object()

    def run(name, sequence):
        machine = run_machine(timer, sequence)
        return machine.error is None and machine.finding is None

    flow.reset = reset
    flow.run_steps = run
    flow.path_steps = list if mode == "input" else lambda: [Step("öffnen", request, settle_ms=120)]
    flow.input_steps = (
        (lambda values: [Step("tippen", request, settle_ms=120)])
        if mode == "input"
        else lambda values: []
    )
    flow.apply_step = lambda: Step("apply", apply)
    flow.until_step = lambda name, condition: Step(name, lambda machine: None)
    flow.still_step = lambda name, root: Step(name, lambda machine: None)
    flow.walker = SimpleNamespace(step=lambda name, button: Step(name, lambda machine: None))
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: None)
    monkeypatch.setattr(
        serialise, "operation_to_data", lambda operation: {"params": {"diameter": 8}}
    )
    flow.phase_revise()
    assert len(applied) == 2
    assert not flow.data["errors"]
    assert timer.now < 5


@pytest.mark.parametrize(
    "background,verdict", [(None, "offen"), ("#000000", "fund"), ("#ffffff", "erfuellt")]
)
def test_missing_pixels_cannot_be_replaced_by_a_good_palette(monkeypatch, background, verdict):
    """Vom ausgefallenen Abtasten bis zum Urteil; gleichbleibende weiße Palette."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QLabel

    monkeypatch.setattr(QApplication, "platformName", lambda: "windows")
    palette = SimpleNamespace(
        color=lambda role: QColor("#000000" if role == "front" else "#ffffff")
    )
    font = SimpleNamespace(pointSizeF=lambda: 10, bold=lambda: False)
    label = SimpleNamespace(
        isEnabled=lambda: True,
        palette=lambda: palette,
        font=lambda: font,
        backgroundRole=lambda: "back",
        foregroundRole=lambda: "front",
    )
    top = SimpleNamespace(
        winId=lambda: 42,
        screen=lambda: SimpleNamespace(
            grabWindow=lambda handle: SimpleNamespace(toImage=lambda: object())
        ),
    )
    root = SimpleNamespace(
        window=lambda: top, findChildren=lambda kind: [label] if kind is QLabel else []
    )
    monkeypatch.setattr(function_capture, "_visible", lambda widget: True)
    monkeypatch.setattr(function_capture, "_text_of", lambda widget: "Text")
    monkeypatch.setattr(function_capture, "name_of", lambda widget: "Text")
    monkeypatch.setattr(function_capture, "_shown_background", lambda *args: background)
    pairs = function_capture.contrast_entries(root, "light")
    outcome = function_judges.CRITERION_JUDGES["G6"]({"contrast": pairs}, sample_context())
    if background is None:
        assert pairs[0]["background"] is None
        assert outcome.verdict != "erfuellt" and not outcome.issues
    else:
        assert outcome.verdict == verdict


@pytest.mark.parametrize("checked,measure", [(True, False), (False, False), (True, True)])
def test_feature_capture_contains_only_its_row_and_its_visible_footer(
    monkeypatch, checked, measure
):
    """Eigene Footertexte werden gemessen, bei fremder Zeile oder Maßgruppe nicht doppelt."""
    row = SimpleNamespace(isAncestorOf=lambda widget: False)
    group, footer = object(), object()
    heading = SimpleNamespace(
        parentWidget=lambda: row, isCheckable=lambda: True, isChecked=lambda: checked
    )
    shown = {
        "feature:move_feature": heading,
        "feature.apply": SimpleNamespace(parentWidget=lambda: footer),
    }
    monkeypatch.setattr(function_surface, "_shown", lambda window, target: shown.get(target))
    window = object()
    root = group if measure else row
    expected = (root, footer) if checked and not measure else (root,)
    assert function_surface.surface_parts(window, "feature:move_feature", root) == expected


@pytest.mark.parametrize("dialog_kind", ["modal", "nonmodal", None])
def test_finding_click_opens_and_measures_its_dialog_separately(monkeypatch, tmp_path, dialog_kind):
    """Echter Wegautomat: modale Schleife bleibt bis zur Folgeaufnahme aktiv."""
    import json

    from tests.bench_fakes import FakeClick, FakePorts, FakeWidget
    from tools.function_setup import Variant
    from tools.function_walk import Walk

    timer = FakeTimer()
    target = "finding.action:calibrate_material"
    action, dialog = FakeWidget("Befundhandlung"), FakeWidget("Dialog")
    visible = []

    def press(widget, button):
        if dialog_kind:
            visible.append(dialog)
        if dialog_kind == "modal":
            timer.loop_until(lambda: not visible)

    ports = FakePorts(
        timer, {target: [FakeClick((0, 0, 20, 20), "left", "ziel", action)]}, on_press=press
    )
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": target, "target": target, "source": "befundhandlung"}
    flow.data = empty_protocol(flow.row, {}, {})
    flow.folder = tmp_path
    flow.variant = Variant.of({"set": "dunkel"})
    flow.window = object()
    flow.walker = Walk(ports, flow.data["steps"], 0)
    flow.surface = lambda: dialog if visible else action
    flow.claim_surface = lambda root: None
    flow.capture_surface = lambda root: flow.data.update(texts=[{"text": root.name}])
    flow.widget = lambda name: None  # kein Hauptknopf der Fläche (FD-99)
    flow.picture = lambda name: flow.data["images"].append(name)
    flow.still_step = lambda name, root: Step(name, lambda machine: None)
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: dialog if visible else None)

    def run(label, steps):
        from tools.function_machine import StepMachine

        machine = StepMachine(timer.schedule, timer.clock, unstick=visible.clear)
        machine.start(steps)
        timer.loop_until(lambda: machine.done)
        return machine.error is None

    flow.run_steps = run
    flow.phase_surface()
    assert [name for name, _, _ in ports.pressed] == ["Befundhandlung"]
    if dialog_kind:
        files = list((tmp_path / "surfaces").glob("*.json"))
        assert len(files) == 1
        assert json.loads(files[0].read_text(encoding="utf-8"))["texts"] == [
            {"text": "Befundhandlung"}
        ]
        assert flow.data["texts"] == [{"text": "Dialog"}]
    else:
        assert flow.data["texts"] == [{"text": "Befundhandlung"}]


@pytest.mark.parametrize(
    "mode", ["good", "old", "not_typed", "not_applied", "wrong_field", "unchanged"]
)
def test_revision_requires_the_typed_change_in_the_same_step(mode):
    """Alte Protokolle bleiben offen; fehlende und falsche Übernahmen werden nicht grün."""
    from copy import deepcopy

    from tools.function_points import POINT_JUDGES

    entry = {
        "opened": True,
        "fields": {"diameter": 8.0},
        "params": {"diameter": 8.0},
        "history_before": 2,
        "history_after": 2,
        "typed_values": {"diameter": 9.0},
        "params_after": {"diameter": 9.0},
    }
    if mode == "old":
        entry.pop("typed_values")
        entry.pop("params_after")
    elif mode == "not_typed":
        entry["typed_values"] = {}
    elif mode == "not_applied":
        entry["params_after"] = {"diameter": 8.0}
    elif mode == "wrong_field":
        entry["typed_values"] = {"depth": 9.0}
        entry["params_after"] = {"diameter": 8.0, "depth": 9.0}
    elif mode == "unchanged":
        entry["typed_values"] = {"diameter": 8.0}
        entry["params_after"] = {"diameter": 8.0}
    protocol = {"revise": [dict(deepcopy(entry), way=way) for way in ("menue", "doppelklick")]}
    outcome = POINT_JUDGES[12](protocol, sample_context(), {})
    assert (outcome.verdict == "erfuellt") is (mode == "good")
    assert bool(outcome.issues) is (mode in ("not_applied", "wrong_field"))


def test_both_finding_surfaces_reach_the_report_without_mixing_their_fields(tmp_path):
    """Vorher und Dialog bleiben reguläre Protokolle und getrennte E5-Messflächen."""
    from tools.file_acceptance import write_json
    from tools.function_report import read_protocols
    from tools.function_samples import sample_protocol

    before, dialog = sample_protocol(), sample_protocol()
    before["fields"] = [{"label": "Vorher", "front": True}] * 3
    dialog["fields"] = [{"label": "Dialog", "front": True}] * 3
    write_json(tmp_path / "cases/001/surfaces/handlung-vorher.json", before)
    write_json(tmp_path / "cases/001/function.json", dialog)
    protocols, problems = read_protocols(tmp_path)
    assert not problems
    assert len(protocols) == 2
    assert all(len(protocol["fields"]) == 3 for path, protocol in protocols)


def test_revision_types_and_accepts_before_the_modal_read_run_finishes(monkeypatch):
    """Beide Wege behalten den Dialog bis nach Eingabe, Vorschau und Übernahme offen."""
    from app.core.scene import serialise
    from tools.function_points import POINT_JUDGES

    timer = FakeTimer()
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": "drill_hole", "target": "operation:drill_hole", "kind": "operation"}
    flow.data = empty_protocol(flow.row, {}, {})
    flow.data["states"] = {"before": {"ops": [1]}, "applied": {"ops": [1, 2]}}
    flow.spec = {}
    flow.apply_target = "dialog.accept"
    document = SimpleNamespace(ops=[])
    flow.session = SimpleNamespace(project=SimpleNamespace(document=document), last_result=object())
    flow.window = SimpleNamespace(viewport=SimpleNamespace(difference=None))
    flow.idle = lambda: True
    state = {"visible": False, "entered": 8.0}
    dialog = object()
    banner = SimpleNamespace(isVisible=lambda: True, legend=SimpleNamespace(isVisible=lambda: True))
    accept = SimpleNamespace(isEnabled=lambda: True)
    typed, photos = [], []

    def widget(target):
        if target == "preview.banner":
            return banner
        if target == "dialog":
            return dialog if state["visible"] else None
        return accept

    def reset():
        document.ops = [{"source": "src1"}]
        state.update(visible=False, entered=8.0)
        flow.window.viewport.difference = None
        flow.session.last_result = object()
        return True

    def open_(machine):
        state["visible"] = True
        flow.window.viewport.difference = object()

    def create(machine):
        document.ops.append({"diameter": 8.0})
        flow.session.last_result = object()

    def input_(values):
        if not values:
            return []

        def enter(machine):
            assert state["visible"], "Eingabe nach geschlossenem Dialog"
            state["entered"] = values["field:diameter"]
            typed.append(state["entered"])
            flow.window.viewport.difference = object()

        return [Step("tippen", enter)]

    def step(target, button="left"):
        def click(machine):
            if target == "dialog.accept":
                assert state["visible"]
                document.ops[-1] = {"diameter": state["entered"]}
                flow.session.last_result = object()
                state["visible"] = False
            else:
                open_(machine)

        return Step(target, click)

    def run(label, steps):
        machine = run_machine(timer, steps)
        state["visible"] = False  # Nach dem Leselauf würde der modale Automat Escape drücken.
        return machine.error is None and machine.finding is None

    flow.widget = widget
    flow.reset = reset
    flow.run_steps = run
    flow.path_steps = lambda: [Step("öffnen", open_)]
    flow.input_steps = input_
    flow.apply_step = lambda: Step("anlegen", create)
    flow.still_step = lambda name, root: Step(name, lambda machine: None)
    flow.walker = SimpleNamespace(step=step)
    flow.picture = photos.append
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: widget("dialog"))
    monkeypatch.setattr(function_capture, "field_values", lambda root: {"diameter": 8.0})
    monkeypatch.setattr(serialise, "operation_to_data", lambda operation: {"params": operation})
    flow.phase_revise()
    assert typed == [8.8, 8.8]
    assert len(photos) == 2
    assert POINT_JUDGES[12](flow.data, sample_context(), {}).verdict == "erfuellt"


def test_nonmodal_generator_is_a_surface_without_an_operation_dialog(monkeypatch):
    """Der Wortschatz kennt nur Operationsdialog/modal; der Generator ist trotzdem sichtbar."""
    from PySide6.QtWidgets import QApplication

    generator = object()
    monkeypatch.setattr(function_surface, "_shown", lambda *args: None)
    monkeypatch.setattr(function_surface, "windows_to_picture", lambda window: [generator])
    monkeypatch.setattr(QApplication, "activeWindow", lambda: None)
    assert function_surface.open_dialog(object()) is generator


@pytest.mark.parametrize("active_index", [0, 1, None])
def test_nonmodal_surface_selection_requires_an_unambiguous_window(monkeypatch, active_index):
    """Bei mehreren Fenstern entscheidet die aktive Fläche; ohne sie wird nicht geraten."""
    from PySide6.QtWidgets import QApplication

    opened = [object(), object()]
    monkeypatch.setattr(function_surface, "_shown", lambda *args: None)
    monkeypatch.setattr(function_surface, "windows_to_picture", lambda window: opened)
    active = None if active_index is None else opened[active_index]
    monkeypatch.setattr(QApplication, "activeWindow", lambda: active)
    if active_index is None:
        with pytest.raises(RuntimeError, match="Mehrere offene Bedienflächen"):
            function_surface.open_dialog(object())
    else:
        assert function_surface.open_dialog(object()) is active
