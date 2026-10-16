"""Beide Wege des Prüfstands warten nach dem Klick ins Feld auf dessen Fokus (Review 1, RCI-4).

Der Helfer ``function_walk.focus_arrived`` ist in ``test_function_bench.py``
geprüft; hier hängt er an den Einsatzstellen: *alles markieren* im
Funktionsweg (``FunctionFlow.mark_all_step``) und in der Einzeldateiabnahme
(``WindowFlow._typing``). Ohne Fenster: Der Fokus ist nachgestellt.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.bench_fakes import FakePorts, FakeTimer
from tools import file_acceptance, function_bench, function_walk


@pytest.fixture
def focus(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    """Der nachgestellte Fokus: ``inside`` sagt, ob er im Feld liegt."""
    state = {"inside": False}
    monkeypatch.setattr(function_walk, "focus_inside", lambda field: state["inside"])
    monkeypatch.setattr(function_walk, "focus_inside", lambda field: state["inside"])
    return state


def _marking_of_the_function_way() -> Any:
    flow = object.__new__(function_bench.FunctionFlow)
    flow.widget = lambda name: None  # type: ignore[method-assign]
    return flow.mark_all_step("measure.field:diameter")


def _marking_of_the_file_way(monkeypatch: pytest.MonkeyPatch) -> Any:
    from app.ui import guide_targets

    monkeypatch.setattr(guide_targets, "widget_for", lambda window, target: None)
    flow = object.__new__(file_acceptance.WindowFlow)
    flow.window = None
    flow.walker = function_walk.Walk(FakePorts(FakeTimer(), {}), [], 0.0)
    steps = flow._typing("measure.field:diameter", 8.0)
    assert steps[1].name == "alles markieren"
    return steps[1]


@pytest.mark.parametrize("way", ["funktion", "datei"])
def test_marking_waits_until_the_click_has_handed_the_focus_over(
    way: str, focus: dict[str, bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nicht bereit, solange der Fokus fehlt; bereit, sobald er im Feld liegt."""
    step = (
        _marking_of_the_function_way()
        if way == "funktion"
        else _marking_of_the_file_way(monkeypatch)
    )
    assert step.ready is not None, "der Schritt wartet auf den Fokus"
    assert step.ready() is False
    focus["inside"] = True
    assert step.ready() is True


@pytest.mark.parametrize("way", ["funktion", "datei"])
def test_marking_acts_after_the_grace_so_the_check_can_name_the_holder(
    way: str, focus: dict[str, bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kommt der Fokus nie, wird der Schritt nach der Frist trotzdem bereit."""
    monkeypatch.setattr(function_walk, "FOCUS_GRACE_S", -1.0)
    step = (
        _marking_of_the_function_way()
        if way == "funktion"
        else _marking_of_the_file_way(monkeypatch)
    )
    assert step.ready is not None
    assert step.ready() is True
