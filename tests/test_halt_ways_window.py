"""Hinter einem Halt gehen im Bericht genau die Wege des Halts (RA-3, FD-104).

Was hinter dem Halt geht, beantwortete eine eigene Liste von Kennungen
(``change_lock.CHAIN_WAYS``, entfallen); die Sitzung entscheidet nach dem Befund. Am Halt
„braucht einen ausgeschalteten Schritt“ standen *Schritt einschalten* und
*Diesen Schritt ausschalten* grau mit dem Satz „Der Weg weiter steht im
Prüfbericht.“ — im Prüfbericht. Jetzt fragt die Anzeige dieselbe Quelle wie die
Sitzung (``revision.halt_finding``): Die Wege am haltenden Befund gehen, und
hinter einem fremden Halt bleibt ein Weg grau.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QMenu, QPushButton

from app.core.errors import REACTIVATE_STEP, SUPPRESS_STEP
from app.core.scene import OperationDraft
from app.core.scene.project import save
from app.core.types import Suppression
from app.ui import main_window as main_window_module
from app.ui import panels
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture
def said(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    shown: list[Any] = []
    monkeypatch.setattr(
        main_window_module, "show_error", lambda error, _parent: shown.append(error)
    )
    return shown


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    built = MainWindow(Session(), UiSettings())
    built._show_start_screen(False)
    yield built
    assert built.session.wait_for_idle(60_000)
    built.release()
    built.deleteLater()
    qt_app.processEvents()


def _settle(qt_app: QApplication, window: MainWindow) -> None:
    assert window.session.wait_for_idle(60_000)
    for _round in range(10):
        qt_app.processEvents()
    assert window.session.wait_for_idle(60_000)


def _offer(window: MainWindow, qt_app: QApplication, text: str, label: str) -> QPushButton:
    report = window.report
    rows = [report.list.item(row) for row in range(report.list.count())]
    target = next(item for item in rows if text in item.text())
    report.list.setCurrentItem(target)
    target.setSelected(True)
    for _round in range(5):
        qt_app.processEvents()
    return next(
        button
        for button in report._offers.findChildren(QPushButton)
        if not button.isHidden() and button.text() == label
    )


def test_a_way_behind_another_halt_stays_grey(
    qt_app: QApplication, window: MainWindow, said: list[Any]
) -> None:
    session = window.session
    assert session.apply("Quader", [OperationDraft(op="create_box")])
    _settle(qt_app, window)
    assert session.apply("Zweiter Quader", [OperationDraft(op="create_box")])
    _settle(qt_app, window)
    second = session.project.document.ops[-1].id
    session.revise_history("suppress", [second])
    _settle(qt_app, window)
    session.apply(
        "Zerlegen", [OperationDraft(op="split_bodies", inputs=("obj_1",), params={"count": 3})]
    )
    _settle(qt_app, window)
    assert session.halted_step() is not None, "Voraussetzung: die Kette hält an der Zerlegung"

    button = _offer(window, qt_app, "ausgeschaltet", str(REACTIVATE_STEP.label))

    assert not button.isEnabled(), "der Befund ist nicht der Halt"
    assert "hält an Schritt" in button.toolTip(), button.toolTip()


def test_the_ways_of_the_resting_step_halt_are_open(
    qt_app: QApplication, window: MainWindow, said: list[Any], tmp_path: Path
) -> None:
    builder = MainWindow(Session(), UiSettings())
    try:
        assert builder.session.apply("Quader", [OperationDraft(op="create_box")])
        _settle(qt_app, builder)
        assert builder.session.apply(
            "Verschieben",
            [
                OperationDraft(
                    op="translate_object", inputs=("obj_1",), params={"x": 10.0, "y": 0.0, "z": 0.0}
                )
            ],
        )
        _settle(qt_app, builder)
        project = builder.session.project
        first = project.document.ops[0]
        project.document.ops[0] = dataclasses.replace(first, suppressed=Suppression(chosen=True))
        path = tmp_path / "ruhend.p3d"
        save(project, path)
    finally:
        assert builder.session.wait_for_idle(60_000)
        builder.release()
        builder.deleteLater()

    window.open_path(path)
    _settle(qt_app, window)
    halted = window.session.halted_step()
    assert halted is not None, "Voraussetzung: die Kette hält am Schritt mit ruhendem Körper"

    for action in (REACTIVATE_STEP, SUPPRESS_STEP):
        button = _offer(window, qt_app, "ausgeschalteten Schritt", str(action.label))
        assert button.isEnabled(), (action.id, button.toolTip())

    # **Dasselbe im Kontextmenü am haltenden Befund** (Review 2 Restpaket A,
    # L3a): Es fragt ``action_refusal(…, at_halt=)`` an eigener Stelle.
    # ``QMenu.exec`` wartet offscreen; das Menü liest seine Einträge und wählt nichts.
    entries: dict[str, bool] = {}

    class ReadingMenu(QMenu):
        def exec(self, *_args: Any) -> None:  # type: ignore[override]
            entries.update({entry.text(): entry.isEnabled() for entry in self.actions()})

    report = window.report
    target = report.list.currentItem()
    assert target is not None and "ausgeschalteten Schritt" in target.text()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(panels, "QMenu", ReadingMenu)
        report._on_menu(report.list.visualItemRect(target).center())
    for action in (REACTIVATE_STEP, SUPPRESS_STEP):
        assert entries.get(str(action.label)) is True, entries

    button = _offer(window, qt_app, "ausgeschalteten Schritt", str(SUPPRESS_STEP.label))
    button.click()
    _settle(qt_app, window)
    assert window.session.halted_step() is None, "die Sitzung nimmt den Weg an"
    assert not said, [str(error.title) for error in said]
