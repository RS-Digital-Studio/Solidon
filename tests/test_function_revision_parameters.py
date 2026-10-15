"""Prüfpunkt 12 an einer Zeile, die einen Projektparameter anlegt (Paket F8, FD-127).

*Parameter anlegen* legt einen Eintrag im Verlauf an („Parameter Breite“),
aber keine Operation. Der Prüfstand verglich nur die Zahl der Operationen,
sah „keinen Schritt im Verlauf“ und maß Prüfpunkt 12 nie (Lauf 003). Jetzt
geht er den Weg des Parameters: *Ändern …* an seiner Zeile der
Parameterleiste und der Doppelklick auf seinen Eintrag im Verlauf; die
Verlaufslänge ist die Zahl der Projektparameter. Ohne Fenster an einer
nachgebauten Phase, das Urteil an ``function_points``.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.types import Parameter
from tools import function_bench, function_capture, function_surface
from tools.function_machine import Step
from tools.function_points import judge_case
from tools.function_revision import HISTORY_ENTRY, PARAMETER_ROW
from tools.function_samples import sample_context, sample_protocol


class _Machine:
    def __init__(self) -> None:
        self.inserted: list[Step] = []

    def insert(self, steps: list[Step]) -> None:
        self.inserted.extend(steps)


def _flow(monkeypatch: pytest.MonkeyPatch, *, opens: bool) -> tuple[Any, list[str]]:
    """Eine Phase ``revise`` mit nachgebauter Sitzung: Anlegen legt ``breite`` an.

    ``opens`` sagt, ob der Weg einen Dialog öffnet; geklickt wird nichts, die
    Ziele der Wege stehen in der zurückgegebenen Liste.
    """
    document = SimpleNamespace(parameters={}, ops=[object()])
    flow = object.__new__(function_bench.FunctionFlow)
    flow.session = SimpleNamespace(project=SimpleNamespace(document=document), last_result=None)
    flow.window = SimpleNamespace(
        history_panel=SimpleNamespace(list=SimpleNamespace(count=lambda: 3))
    )
    flow.spec = {"inputs": {"field:name": "breite", "field:value": 20.0}}
    flow.apply_target = "dialog.accept"
    flow.data = {
        "states": {
            "before": {"ops": ["a"], "project_params": "leer"},
            "applied": {"ops": ["a"], "project_params": "breite"},
        },
        "unmeasured": {},
        "errors": [],
    }
    targets: list[str] = []
    marker = Step("marke", lambda machine: None)

    def reset() -> bool:
        # Zurück an die Startszene: Sie trägt noch keinen Parameter.
        document.parameters = {}
        return True

    flow.reset = reset  # type: ignore[method-assign]
    flow.idle = lambda: True  # type: ignore[method-assign]
    flow.path_steps = list  # type: ignore[method-assign]
    flow.input_steps = lambda inputs: [marker]  # type: ignore[method-assign]
    flow.preview_steps = lambda steps=(): list(steps)  # type: ignore[method-assign]
    flow.apply_step = lambda: marker  # type: ignore[method-assign]
    flow.wait_step = lambda name, ready, timeout_s=0: marker  # type: ignore[method-assign]
    flow.until_step = lambda name, condition, at_most_s=0: marker  # type: ignore[method-assign]
    flow.still_step = lambda name, root, at_most_s=0: marker  # type: ignore[method-assign]
    flow.picture = lambda label: None  # type: ignore[method-assign]

    def step(target: str, button: str = "left") -> Step:
        targets.append(f"{target} {button}")
        return marker

    flow.walker = SimpleNamespace(step=step)

    def run_steps(label: str, steps: list[Step], timeout_s: float = 0) -> bool:
        if label.startswith("anlegen"):
            document.parameters = {"breite": Parameter(name="breite", value=20.0, title="Breite")}
            return True
        reading = next(step for step in steps if step.name == "felder lesen")
        machine = _Machine()
        reading.act(machine)  # type: ignore[arg-type]
        if machine.inserted:
            typed = next(step for step in machine.inserted if step.name == "getippt")
            typed.act(machine)  # type: ignore[arg-type]
            document.parameters = {"breite": Parameter(name="breite", value=22.0, title="Breite")}
            accepted = next(s for s in machine.inserted if s.name == "übernommene werte lesen")
            accepted.act(machine)  # type: ignore[arg-type]
        return True

    flow.run_steps = run_steps  # type: ignore[method-assign]
    dialog = object() if opens else None
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: dialog)
    monkeypatch.setattr(
        function_capture,
        "field_values",
        lambda root: {"name": "breite", "value": 20.0, "unit": "mm", "expression": ""},
    )
    monkeypatch.setattr("tools.file_acceptance.changed_value", lambda value: 22.0)
    return flow, targets


def _judged_revise(entries: list[dict[str, Any]]) -> Any:
    protocol = copy.deepcopy(sample_protocol())
    protocol["revise"] = entries
    return judge_case(protocol, sample_context()).points[12]


def test_a_parameter_row_is_revised_through_its_own_two_ways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lauf 003: „die Zeile legt keinen Schritt im Verlauf an“ — jetzt gemessen."""
    flow, targets = _flow(monkeypatch, opens=True)
    flow.phase_revise()
    assert "revise" not in flow.data["unmeasured"]
    assert targets == [
        f"{PARAMETER_ROW.format(1)} right",
        "menu:parameters.edit left",
        "dialog.accept left",
        f"{HISTORY_ENTRY.format(3)} double",
        "dialog.accept left",
    ], targets
    entries = flow.data["revise"]
    assert [entry["way"] for entry in entries] == ["menue", "doppelklick"]
    for entry in entries:
        assert entry["opened"] is True
        assert entry["history_before"] == entry["history_after"] == 1
        assert entry["typed_values"] == {"value": 22.0}
        assert entry["params_after"]["value"] == 22.0
    assert _judged_revise(entries).verdict == "erfuellt"


def test_a_way_that_opens_nothing_is_a_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bleibt der Doppelklick auf den Parametereintrag stumm, ist das ein Fund an P12."""
    flow, _targets = _flow(monkeypatch, opens=False)
    flow.phase_revise()
    outcome = _judged_revise(flow.data["revise"])
    assert outcome.verdict == "fund"
    assert any("öffnet nicht" in issue.text for issue in outcome.issues)
