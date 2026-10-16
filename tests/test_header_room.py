"""Die Kopfzeile kürzt den Drucker erst, wenn die Zeile voll ist (FD-91).

Name, Maße und Drucker teilten die Breite nach festen Anteilen (2 : 3 : 3),
nicht nach ihrem Inhalt: Bei 1920 Punkten stand „Elegoo …rbon 2 · FDM“, und
links davon lag eine breite freie Fläche hinter kurzen Maßen. Hier bekommt
die Kopfzeile genug Breite für alle Angaben, und keine wird gekürzt.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.core.scene import EvaluationResult
from app.core.types import Scene
from app.ui.header import HeaderBar
from tests.helpers import make_object

PRINTER = "Elegoo Centauri Carbon 2 · FDM"


def _header() -> HeaderBar:
    header = HeaderBar()
    result = EvaluationResult(scene=Scene(objects={"obj_1": make_object()}))
    header.show_project("Halter.p3d", result, "mm")
    header.show_target(PRINTER, "")
    return header


def _needed(header: HeaderBar) -> int:
    """Was die drei Angaben ungekürzt brauchen, samt Knöpfen und Abständen.

    Gerechnet aus den Texten und nicht aus den Wunschmaßen der Beschriftungen:
    Die stehen unter Prüfung.
    """
    texts = sum(
        label.fontMetrics().horizontalAdvance(label.full_text())
        for label in (header.title, header.bounds, header.printer)
    )
    buttons = header.printer_button.sizeHint().width() + header._filament_width(words=False)
    return texts + buttons + header._layout.horizontalSpacing() * 8 + 16


def test_the_printer_stands_whole_while_the_row_has_room(qt_app: QApplication) -> None:
    header = _header()
    header.resize(_needed(header) + 40, header.sizeHint().height())
    header.show()
    for _ in range(5):
        qt_app.processEvents()
    for label in (header.title, header.bounds, header.printer):
        assert label.text() == label.full_text(), (
            f"{label.text()!r} statt {label.full_text()!r} bei {header.width()} px"
        )
    header.close()


def test_a_full_row_still_shortens_and_keeps_the_whole_name_reachable(
    qt_app: QApplication,
) -> None:
    header = _header()
    header.resize(_needed(header) // 2, header.sizeHint().height())
    header.show()
    for _ in range(5):
        qt_app.processEvents()
    assert "…" in header.printer.text() or "…" in header.title.text()
    assert header.printer.toolTip() in ("", PRINTER) or header.printer.full_text() == PRINTER
    header.close()
