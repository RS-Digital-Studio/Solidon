"""Befundhandlungen hinter einem Halt stehen grau mit dem Halt als Grund (FD-104, Teil Bericht).

Für F4 (panels.py): Prüffall zum Patch ``fd104-panels.patch``. Hält die Kette
an, bot der Bericht *In Einzelteile aufteilen* bedienbar an, und erst nach dem
Klick kam die Absage über den Haltdialog. Jetzt ist der Knopf grau und nennt
den Halt; die Wege des Halts bleiben frei.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from app.core.errors import SPLIT_BODIES
from app.core.scene import OperationDraft
from app.core.types import Finding
from app.ui.change_lock import halt_line
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
    assert session.halted_step() is not None
    yield window
    window.release()


def test_an_action_behind_the_halt_is_grey_with_the_halt_as_reason(
    halted: MainWindow, qt_app: QApplication
) -> None:
    report = halted.report
    finding = Finding(
        code="mesh.loose_parts",
        severity="warning",
        message="Das Modell besteht aus zwei Teilen.",
        object_id="obj_1",
        values={"components": 2},
        suggestions=(SPLIT_BODIES,),
    )
    report.add_findings([finding])
    qt_app.processEvents()
    rows = [report.list.item(row) for row in range(report.list.count())]
    target = next(item for item in rows if "zwei Teilen" in item.text())
    report.list.setCurrentItem(target)
    target.setSelected(True)
    qt_app.processEvents()
    buttons = [
        button
        for button in report._offers.findChildren(QPushButton)
        if not button.isHidden() and button.text() == str(SPLIT_BODIES.label)
    ]
    assert buttons, "die Handlung steht da"
    line = halt_line(halted.session.project.document, halted.session.last_result.stopped_at)
    assert not buttons[0].isEnabled(), "grau, bevor jemand klickt"
    assert buttons[0].toolTip() == line and buttons[0].accessibleDescription() == line
