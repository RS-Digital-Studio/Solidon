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


def test_at_the_bottom_edge_the_dialog_rises_only_as_far_as_it_grew(
    qt_app: QApplication, request: pytest.FixtureRequest
) -> None:
    """Am unteren Rand rückt ein Dialog nach einem Schriftwechsel nur so weit hinauf, wie er
    gewachsen ist (Nachprüfung L-2): Die Unterkante bleibt am Rand, und nichts rollt, wo
    darüber Platz ist. Der erste Durchgang von ``fit`` setzte mehr Höhe, als der zweite
    behielt, und den Dialog dafür höher — unter *Tasche ausschneiden* blieben 44 Punkte frei.
    Am Anker gehalten, wie vorher, rollte er stattdessen (Fensterauswahl 39035816730).

    Mit der Ersatzschrift ohne Bildschirm, nicht der Prüfschrift: Die Zusage ist eine Lage,
    keine Schriftmetrik, und nur dort verlangt der erste Durchgang mehr (506 statt 466).
    """
    from PySide6.QtGui import QFont

    from app.core.errors import ValidationError
    from app.ui.style import NORMAL

    load_operations()
    original = QFont(qt_app.font())
    font = QFont(original)
    font.setPointSize(11)
    qt_app.setFont(font)
    try:
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        dialog = OperationDialog(REGISTRY.get("sketch_pocket"), {"body": "Körper"})
        close_after(request, dialog)
        dialog.show()
        _rounds(qt_app)
        screen = dialog.screen()
        assert screen is not None
        room = screen.availableGeometry().adjusted(NORMAL, NORMAL, -NORMAL, -NORMAL)
        frame = dialog.frameGeometry()
        dialog.move(frame.left(), room.bottom() - frame.height() + 1)
        _rounds(qt_app)
        dialog.show_refusal(ValidationError("plane", "Absage"))
        _rounds(qt_app)
        top = dialog.frameGeometry().top()
        assert dialog.frameGeometry().bottom() == room.bottom(), "Voraussetzung: am Rand"

        font.setPointSize(18)
        qt_app.setFont(font)
        _rounds(qt_app, 80)

        frame = dialog.frameGeometry()
        assert frame.top() < top, "Voraussetzung: gewachsen und hinaufgerückt"
        assert frame.height() <= room.height(), "Voraussetzung: passt auf den Bildschirm"
        assert frame.bottom() == room.bottom(), (frame.top(), frame.bottom(), room.bottom())
        assert dialog._scroll.verticalScrollBar().maximum() == 0, "rollt, obwohl Platz war"
    finally:
        qt_app.setFont(original)
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
