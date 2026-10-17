"""Ein offener Dialog folgt einer kleineren Schrift auch in der Höhe (FD-195).

Nach 9 → 14 → 9 pt behielt ein Dialog die Höhe der großen Schrift, unten
blieb ein leerer Streifen: ``ContentHeight`` lässt passive Änderungen nur
wachsen, und ein Schriftwechsel zählte als passiv. Jetzt misst ein
Schriftwechsel wie das Aufklappen (Absicht ``font``) — eine Größe, die der
Kunde selbst aufgezogen hat, bleibt.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.ui.op_dialog import OperationDialog
from app.ui.parameter_dialog import ParameterDialog
from app.ui.style import apply_style
from app.ui.theme import apply_theme
from tests.bundled_fonts import bundled_font
from tests.window_leftovers import close_after


def _rounds(qt_app: QApplication, count: int = 60) -> None:
    for _ in range(count):
        qt_app.processEvents()
        time.sleep(0.005)


def _operation() -> OperationDialog:
    return OperationDialog(REGISTRY.get("create_box"), {})


def _parameter() -> ParameterDialog:
    return ParameterDialog({})


@pytest.mark.parametrize("make", [_operation, _parameter], ids=["operation", "parameter"])
def test_the_height_goes_back_with_the_font(
    qt_app: QApplication, request: pytest.FixtureRequest, make
) -> None:
    load_operations()
    with bundled_font(qt_app, 9) as font:
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        dialog = make()
        close_after(request, dialog)
        dialog.show()
        _rounds(qt_app)
        start = dialog.height()
        font.setPointSize(14)
        qt_app.setFont(font)
        _rounds(qt_app)
        assert dialog.height() > start, "Voraussetzung: die große Schrift braucht mehr Höhe"
        font.setPointSize(9)
        qt_app.setFont(font)
        _rounds(qt_app)
        assert dialog.height() == start, "zurück bei derselben Schrift, dieselbe Höhe"
    apply_style(qt_app, "light")


def test_a_height_the_customer_chose_stays(
    qt_app: QApplication, request: pytest.FixtureRequest
) -> None:
    load_operations()
    with bundled_font(qt_app, 9) as font:
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        dialog = _operation()
        close_after(request, dialog)
        dialog.show()
        _rounds(qt_app)
        dialog.resize(dialog.width(), dialog.height() + 60)
        _rounds(qt_app)
        chosen = dialog.height()
        font.setPointSize(14)
        qt_app.setFont(font)
        _rounds(qt_app)
        font.setPointSize(9)
        qt_app.setFont(font)
        _rounds(qt_app)
        assert dialog.height() == chosen, "aufgezogen bleibt aufgezogen"
    apply_style(qt_app, "light")
