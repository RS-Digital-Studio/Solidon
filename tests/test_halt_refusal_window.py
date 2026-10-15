"""Befundhandlungen hinter einem Halt sagen ihn, bevor etwas aufgeht (FD-104).

Hält die Kette an, legt eine Handlung wie *In Flächen und Kanten umwandeln*
oder *Für den Druck ausrichten* ihren Schritt hinten an — dorthin, wo nichts
gerechnet wird. Ihr Dialog ging auf, und sein Hauptknopf blieb grau, ohne
Grund. Jetzt sagt das Fenster den Halt mit seinen Wegen, bevor ein Dialog
aufgeht; und ``change_lock.action_refusal`` gibt jedem Zugang denselben Satz.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture
def halted(qt_app: QApplication) -> Iterator[MainWindow]:
    window = MainWindow(Session(), UiSettings())
    session = window.session
    assert session.apply("Quader", [OperationDraft(op="create_box")])
    assert session.wait_for_idle(60_000)
    session.apply(
        "Zerlegen",
        [OperationDraft(op="split_bodies", inputs=("obj_1",), params={"count": 3})],
    )
    assert session.wait_for_idle(60_000)
    qt_app.processEvents()
    assert session.halted_step() is not None, "die Kette hält an der Zerlegung"
    yield window
    window.release()


@pytest.mark.parametrize("name", ["mesh_to_exact", "orient_for_print"])
def test_a_step_behind_the_halt_is_refused_before_its_dialog(
    halted: MainWindow, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    said: list[Any] = []
    monkeypatch.setattr(halted, "_on_error", said.append)
    halted.run_operation(REGISTRY.get(name))
    assert halted._op_dialog is None, "kein Dialog, dessen Knopf grau bliebe"
    assert said, "der Halt wird gesagt"
    assert said[-1].suggestions, "mit den Wegen des Halts"


def test_the_report_and_the_menu_say_the_same_halt(halted: MainWindow) -> None:
    from app.ui.change_lock import action_refusal, halt_line

    result = halted.session.last_result
    assert result is not None
    line = halt_line(halted.session.project.document, result.stopped_at)
    assert line and line == halted._halt_reason(), "eine Quelle für beide Zugänge"
    assert action_refusal("split_bodies", halt=line) == line, "hängt einen Schritt an"
    assert action_refusal("orient_for_print", halt=line) == line
    assert action_refusal("recount_and_retry", halt=line) == "", "ein Weg des Halts"
    assert action_refusal("show_details", halt=line) == "", "lesend"
    assert action_refusal("split_bodies") == "", "ohne Halt frei"
