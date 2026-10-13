"""Merkmalsflächen und Verlaufwerte stammen aus der tatsächlich bedienten Handlung."""

from types import SimpleNamespace

import pytest

from tools import function_bench, function_capture, function_surface
from tools.function_machine import Step


@pytest.mark.parametrize("active", ["resize_hole", "move_feature", None])
def test_feature_surface_selects_its_own_visible_group(monkeypatch, active):
    """Eine fremde Maßgruppe und die Nachbarkarte sind keine Fläche dieser Zeile."""
    own_row, measured, selection = object(), object(), object()
    shown = {
        "feature:resize_hole": SimpleNamespace(parentWidget=lambda: own_row),
        "measure.apply": SimpleNamespace(parentWidget=lambda: measured),
        "selection": selection,
    }
    window = SimpleNamespace(feature_panel=SimpleNamespace(measure_op=active))
    monkeypatch.setattr(function_surface, "_shown", lambda window, name: shown.get(name))
    expected = measured if active == "resize_hole" else own_row
    assert function_surface.surface_for(window, "feature:resize_hole") is expected


def test_language_surface_recognizes_its_measure_group_without_typed_inputs(monkeypatch):
    """Sprachzeilen ohne Eingabespezifikation öffnen keine verborgene Nachbarzeile."""
    flow = object.__new__(function_bench.FunctionFlow)
    flow.spec = {}
    flow.window = SimpleNamespace(feature_panel=SimpleNamespace(measure_op="resize_hole"))
    accept = SimpleNamespace(isVisible=lambda: True)
    flow.widget = lambda target: accept if target == "measure.apply" else None
    monkeypatch.setattr(function_surface, "_shown", lambda window, target: flow.widget(target))
    inserted, recorded = [], []
    flow.walker = SimpleNamespace(
        step=lambda target, **kwargs: target,
        before_target=None,
        record=recorded.append,
    )
    flow.action_step("feature:resize_hole").act(SimpleNamespace(insert=inserted.extend))
    assert inserted == []
    assert recorded[0]["zone"] == "ansicht"


@pytest.mark.parametrize("checkable", [True, False])
def test_immediate_feature_is_distinguished_from_an_expandable_heading(monkeypatch, checkable):
    """Eine aufklappbare Zeile wird geöffnet, der sofortige Knopf vor Wirkung gemessen."""
    button = SimpleNamespace(isCheckable=lambda: checkable)
    monkeypatch.setattr(function_surface, "_shown", lambda window, target: button)
    assert function_surface.immediate_feature(object(), "feature:remove_feature") is not checkable


@pytest.mark.parametrize("label", ["Bohrung ändern", "Andere Zeile", ""])
@pytest.mark.parametrize("visible", [True, False])
def test_disclosure_arrow_needs_its_own_visible_label(monkeypatch, label, visible):
    """Ein Pfeil mit eigener Beschriftung ist kein unbeschrifteter Symbolknopf."""
    from PySide6 import QtWidgets
    from PySide6.QtCore import Qt

    text = SimpleNamespace(text=lambda: label, isVisible=lambda: visible)
    parent = SimpleNamespace(findChildren=lambda kind: [text])
    text.parentWidget = lambda: parent

    class Heading:
        """Öffentliche Eigenschaften eines beschrifteten Qt-Zeilenkopfes."""

        def __init__(self):
            self.findChildren = lambda kind: []
            self.isCheckable = lambda: True
            self.arrowType = lambda: Qt.ArrowType.RightArrow
            self.accessibleName = lambda: "Bohrung ändern"
            self.parentWidget = lambda: parent
            self.icon = lambda: SimpleNamespace(isNull=lambda: True)

    monkeypatch.setattr(QtWidgets, "QToolButton", Heading)
    monkeypatch.setattr(function_capture, "_visible", lambda widget: widget.isVisible())
    monkeypatch.setattr(function_capture, "_text_of", lambda widget: widget.text())
    assert function_capture._shows_itself(Heading()) is (visible and label == "Bohrung ändern")


@pytest.mark.parametrize("accepted", [True, False])
def test_revision_never_reads_the_old_import_before_the_new_operation(monkeypatch, accepted):
    """Alte Leerlaufmeldung ist kein Nachweis eines übernommenen zweiten Schritts."""
    from app.core.scene import serialise
    from tools.function_protocol import empty_protocol

    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": "resize_hole", "target": "feature:resize_hole"}
    flow.data = empty_protocol(flow.row, {}, {})
    flow.data["states"] = {"before": {"ops": [1]}, "applied": {"ops": [1, 2]}}
    flow.spec = {}
    flow.apply_target = "measure.apply"
    document = SimpleNamespace(ops=["import"])
    flow.session = SimpleNamespace(project=SimpleNamespace(document=document), last_result=object())
    flow.window = object()
    flow.idle = lambda: True
    steps = []

    def reset():
        document.ops = ["import"]
        flow.session.last_result = object()
        return True

    def wait(name, ready):
        def act(machine):
            if not ready() and accepted:
                document.ops.append("resize")
                flow.session.last_result = object()
            if not ready():
                raise TimeoutError(name)

        return Step(name, act)

    def run(name, sequence):
        for step in sequence:
            steps.append(step.name)
            try:
                step.act(None)
            except TimeoutError:
                return False
        return True

    flow.reset = reset
    flow.run_steps = run
    flow.path_steps = list
    flow.input_steps = lambda values: []
    flow.preview_steps = lambda triggering=(): [*triggering, Step("preview", lambda machine: None)]
    flow.apply_step = lambda: Step("apply", lambda machine: None)
    flow.wait_step = wait
    flow.until_step = lambda name, ready: Step(name, lambda machine: None)
    flow.still_step = lambda name, surface: Step(name, lambda machine: None)
    flow.walker = SimpleNamespace(step=lambda name, button: Step(name, lambda machine: None))
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: None)
    read = []

    def values(operation):
        read.append(operation)
        return {"params": {"diameter": 8} if operation == "resize" else {"source": "src1"}}

    monkeypatch.setattr(serialise, "operation_to_data", values)
    flow.phase_revise()
    assert read == (["resize", "resize"] if accepted else [])
    assert steps.index("preview") < steps.index("apply")
    if accepted:
        assert all(entry["history_before"] == 2 for entry in flow.data["revise"])
    else:
        assert flow.data["errors"]
