"""Die Quittung liegt nie über einer Karte und geht mit dem nächsten Schritt (FD-108, FD-162).

Im Funktionsdurchgang stand „Die Kette hält an — siehe Prüfbericht.“ acht
Sekunden über Hauptknopf und Befundzeilen des Berichts, die Rücknahme-Quittung
über der Sammelzeile der Maßkarte, und nach der nächsten Übernahme meldete
die Statuszeile weiter „zurückgenommen“.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication, QFrame

from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tools.function_checks import SMALLEST_WINDOW


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    built = MainWindow(Session(), UiSettings())
    built.resize(*SMALLEST_WINDOW)
    built.show()
    built._show_start_screen(False)
    for _ in range(5):
        qt_app.processEvents()
    yield built
    built.release()
    built.close()
    built.deleteLater()
    qt_app.processEvents()


def _in_overlay(window: MainWindow, widget: QFrame) -> QRect:
    corner = window.overlay.mapFromGlobal(widget.mapToGlobal(QPoint(0, 0)))
    return QRect(corner, widget.size())


def test_a_reply_at_the_report_stands_beside_it(window: MainWindow, qt_app: QApplication) -> None:
    column = window.right_column
    assert column.isVisibleTo(window.overlay), "die rechte Karte steht"
    card = _in_overlay(window, column)
    notice = window._action_notice
    notice.show_message("Die Kette hält an — siehe Prüfbericht.", card.center())
    qt_app.processEvents()
    assert notice.isVisibleTo(window.overlay), "es gibt Platz in der Ansicht"
    assert not notice.geometry().intersects(card), (
        f"die Quittung {notice.geometry()} liegt über dem Bericht {card}"
    )
    assert window.overlay.rect().contains(notice.geometry())


def test_a_card_in_the_view_pushes_the_reply_aside_also_when_it_comes_later(
    window: MainWindow, qt_app: QApplication
) -> None:
    card = QFrame(window.viewport)
    card.setGeometry(500, 250, 420, 260)
    card.show()
    qt_app.processEvents()
    notice = window._action_notice
    inside = _in_overlay(window, card).center()
    notice.show_message("Zurückgenommen: Bohrung ändern. Strg+Y stellt es wieder her.", inside)
    qt_app.processEvents()
    assert notice.isVisibleTo(window.overlay)
    assert not notice.geometry().intersects(_in_overlay(window, card))

    # Die Karte wandert dorthin, wo die Quittung jetzt steht: Sie rückt nach.
    target = window.viewport.mapFrom(window.overlay, notice.geometry().topLeft())
    card.move(target)
    qt_app.processEvents()
    assert notice.isHidden() or not notice.geometry().intersects(_in_overlay(window, card))
    card.deleteLater()


def test_the_next_step_takes_the_reply_along(window: MainWindow, qt_app: QApplication) -> None:
    session = window.session
    assert session.apply("Quader", [OperationDraft(op="create_box")])
    assert session.wait_for_idle(60_000)
    window.announce("Zurückgenommen: Quader. Strg+Y stellt es wieder her.")
    for _ in range(3):
        qt_app.processEvents()
    assert window.status_message.text()

    assert session.apply("Zylinder", [OperationDraft(op="create_cylinder")])
    assert session.wait_for_idle(60_000)
    for _ in range(3):
        qt_app.processEvents()
    assert window.status_message.text() == "", "die Statuszeile folgt dem letzten Schritt"
    assert window._action_notice.isHidden()


def test_a_reply_said_with_its_step_stays(window: MainWindow, qt_app: QApplication) -> None:
    """Wer ansagt und im selben Zug den Schritt anlegt, spricht über diesen Schritt."""
    session = window.session
    said = "Quader angelegt."
    window.announce(said)
    assert session.apply("Quader", [OperationDraft(op="create_box")])
    assert session.wait_for_idle(60_000)
    for _ in range(3):
        qt_app.processEvents()
    assert window.status_message.text() == said
