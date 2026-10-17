"""Ein Weg aus dem Prüfbericht in den Skizzenmodus setzt die Tastatur ins Ziel (FD-190).

*Eine andere Ebene wählen* öffnete den Schritt im Skizzenmodus, die unlesbare
Ebene stand in der Ebenenwahl — und die Tastatur auf dem Kartengriff, weil der
gedrückte Knopf des Berichts verschwand und Qt den Fokus weiterreichte. Der
Zwilling ist *Eingabe korrigieren* an einer kaputten Zeichnung: Dort ist das
Ziel die Zeichnung in der Ansicht. Geprüft am Klickweg: Befund im Bericht
wählen, den angebotenen Knopf drücken.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from app.core.bootstrap import load_operations
from app.core.errors import CORRECT_INPUT, PICK_PLANE
from app.core.scene import OperationDraft
from app.core.sketch.serialize import sketch_to_text
from app.core.types import Sketch, SketchElement
from app.i18n import set_language
from app.i18n.catalog import install_language
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.plane_refusals import UNREADABLE_PLANE, square_on


def _rounds(qt_app: QApplication, count: int = 40) -> None:
    for _ in range(count):
        qt_app.processEvents()
        time.sleep(0.005)


def _inside(widget: QWidget | None, target: QWidget) -> bool:
    while widget is not None:
        if widget is target:
            return True
        widget = widget.parentWidget()
    return False


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    load_operations()
    install_language("de")
    set_language("de")
    window = MainWindow(Session(), UiSettings())
    window.resize(1600, 900)
    window.show()
    window._show_start_screen(False)
    yield window
    if window._sketch_panel is not None:
        window.finish_sketch(keep=False)
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def _press_in_the_report(qt_app: QApplication, window: MainWindow, sketch: str, label: str) -> None:
    """Den Schritt anlegen, seinen Befund im Bericht wählen und den Knopf drücken."""
    window.session.apply(
        "Skizze",
        [OperationDraft(op="sketch_extrude", inputs=(), params={"sketch": sketch, "height": 4.0})],
    )
    assert window.session.wait_for_idle(60_000)
    _rounds(qt_app)
    window._focus_report(force=True)
    _rounds(qt_app)
    listing = window.report.list
    item = next(
        listing.item(row)
        for row in range(listing.count())
        if (found := listing.item(row).data(Qt.ItemDataRole.UserRole)) is not None
        and found.op_id is not None
        and found.suggestions
    )
    listing.setCurrentItem(item)
    item.setSelected(True)
    _rounds(qt_app)
    button = next(
        entry
        for entry in window.report._offers.findChildren(QPushButton)
        if entry.isVisibleTo(window.report) and entry.text() == label
    )
    button.setFocus(Qt.FocusReason.MouseFocusReason)
    button.click()
    _rounds(qt_app)


def test_another_plane_puts_the_keyboard_into_the_plane_choice(
    qt_app: QApplication, window: MainWindow
) -> None:
    _press_in_the_report(qt_app, window, square_on(UNREADABLE_PLANE), str(PICK_PLANE.label))
    panel = window._sketch_panel
    assert panel is not None, "der Schritt geht im Skizzenmodus auf"
    assert panel.plane_choice.currentData() == UNREADABLE_PLANE
    focused = QApplication.focusWidget()
    assert _inside(focused, panel.plane_choice), type(focused).__name__


def test_correcting_a_broken_drawing_puts_the_keyboard_into_the_view(
    qt_app: QApplication, window: MainWindow
) -> None:
    broken = sketch_to_text(
        Sketch(
            plane="xy",
            elements=(SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),),
            constraints=(),
        )
    )
    _press_in_the_report(qt_app, window, broken, str(CORRECT_INPUT.label))
    assert window._sketch_panel is not None, "die Zeichnung geht im Skizzenmodus auf"
    focused = QApplication.focusWidget()
    assert _inside(focused, window.viewport), type(focused).__name__
