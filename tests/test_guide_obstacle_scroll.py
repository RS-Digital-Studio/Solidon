"""Ein Hindernis unter dem Rand rollt erst heran (FD-131, RM-737).

Die Klappe *Filament und Druck* steht an einem gewählten Körper unter dem
sichtbaren Teil der Auswahlkarte. ``guide_targets.next_click`` nannte sie als
Klick, ohne zu rollen: Der Klick fiel unter das Fenster, die Probe fand dort
nichts („verdeckt“), und der Kundenweg zu *Filament zuweisen* lief in keiner
Sprache. Die Karte selbst reicht nicht über den Fensterrand; ihr Rollbereich
kann die Klappe heranholen. Gerollt wird über der Karte: Die Liste der
Handlungen darin rollt nicht selbst und reicht das Rad weiter, wie Qt es tut.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtCore import QPoint, QRect, Qt


def _settle(qt_app: Any, rounds: int = 30) -> None:
    for _ in range(rounds):
        qt_app.processEvents()


@pytest.fixture
def chosen_box(qt_app: Any) -> Iterator[Any]:
    """Das kleinste gemessene Fenster mit einem gewählten Quader, wie der Sprachfall ihn sieht."""
    from app.core.scene.history import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tools.function_checks import SMALLEST_WINDOW

    window = MainWindow(Session(), UiSettings())
    window.resize(*SMALLEST_WINDOW)
    window.show()
    window._show_start_screen(False)
    assert window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    window.object_tree.select_object("obj_1")
    _settle(qt_app)
    try:
        yield window
    finally:
        window.hide()
        window.release()


def _window_rect(window: Any) -> QRect:
    return QRect(window.mapToGlobal(QPoint(0, 0)), window.size())


def test_a_flap_below_the_edge_is_rolled_into_view_before_it_is_clicked(
    qt_app: Any, chosen_box: Any
) -> None:
    """Jeder genannte Klick liegt im Fenster; über Rollen und Klappe kommt der Wähler ins Bild."""
    from PySide6.QtTest import QTest

    from app.ui import guide_targets
    from tools.function_walk import QtPorts

    window = chosen_box
    heading = guide_targets.widget_for(window, "filament.section")
    # Voraussetzung, nicht Annahme: Die Klappe ist zu und steht unter dem Rand.
    assert heading.isVisible() and not heading.isChecked()
    centre = heading.mapToGlobal(heading.rect().center())
    assert not guide_targets.unclipped(window.selection_operations).contains(centre)
    ports = QtPorts(window, 0.0)
    reasons: list[str] = []
    for _step in range(60):
        click = guide_targets.next_click(window, "filament.picker")
        reasons.append(str(click.why))
        point = click.rect.center()
        assert _window_rect(window).contains(point), (click.why, click.rect, reasons)
        if click.why == "ziel":
            break
        under = guide_targets.widget_under(point)
        assert under is not None, (click.why, click.rect)
        if click.why == "rollen":
            wheel = "wheel_down" if click.direction > 0 else "wheel_up"
            ports.press(under, point, wheel, wheel_angle=click.wheel_angle)
        else:
            assert click.why == "klappe", reasons
            QTest.mouseClick(under, Qt.MouseButton.LeftButton, pos=under.mapFromGlobal(point))
        _settle(qt_app)
    assert reasons[-1] == "ziel", reasons
    assert reasons[0] == "rollen" and "klappe" in reasons, reasons
    picker = guide_targets.widget_for(window, "filament.picker")
    assert picker.isVisible()


def test_the_heading_itself_is_reached_through_the_card_not_refused(
    qt_app: Any, chosen_box: Any
) -> None:
    """Die Klappe als Ziel: Rollen über der Karte, nicht „Rollanschlag“.

    Unter der Mitte der Karte liegt die Liste der Handlungen. Sie rollt nicht
    (ihr Bereich steht am Anschlag) und reicht das Rad an die Karte weiter; die
    Navigation verlangte vorher, dass unter der Mitte unmittelbar die Karte
    liegt, und gab auf.
    """
    from app.ui import guide_targets

    click = guide_targets.next_click(chosen_box, "filament.section")
    assert click.why == "rollen" and click.direction == 1, click


def test_an_inner_area_that_still_rolls_keeps_the_wheel(qt_app: Any) -> None:
    """Ein innerer Bereich, der selbst noch rollt, nähme das Rad: Gedreht wird über der
    Leiste des Bereichs, der das Ziel trägt (FD-159), nie über dem inneren.

    Und am Anschlag reicht er es weiter: Dann rollt die Navigation über ihm.
    """
    from PySide6.QtWidgets import QPushButton, QScrollArea, QVBoxLayout, QWidget

    from app.ui import guide_targets

    outer = QScrollArea()
    outer.setWidgetResizable(True)
    content = QWidget()
    stack = QVBoxLayout(content)
    inner = QScrollArea()
    inner.setFixedHeight(180)
    filling = QWidget()
    inner.setWidget(filling)
    stack.addWidget(inner)
    stack.addSpacing(900)
    target = QPushButton("Ziel")
    stack.addWidget(target)
    outer.setWidget(content)
    outer.resize(320, 220)
    outer.show()
    try:
        for height, rolls_itself in ((1200, True), (60, False)):
            filling.setFixedSize(200, height)
            _settle(qt_app)
            inner_bar = inner.verticalScrollBar()
            assert (inner_bar.maximum() > 0) is rolls_itself
            centre = outer.viewport().mapToGlobal(outer.viewport().rect().center())
            assert inner.isAncestorOf(guide_targets.widget_under(centre))
            try:
                click = guide_targets._scroll_needed(target, "probe")
            except guide_targets.MissingTargetError:
                click = None
            over_inner = click is not None and QRect(
                inner.mapToGlobal(QPoint(0, 0)), inner.size()
            ).contains(click.rect.center())
            if rolls_itself:
                assert click is not None and not over_inner, click
                bar = outer.verticalScrollBar()
                assert QRect(bar.mapToGlobal(QPoint(0, 0)), bar.size()).contains(
                    click.rect.center()
                ), click
            else:
                assert click is not None and click.why == "rollen" and click.direction == 1
    finally:
        outer.hide()
        outer.deleteLater()
        _settle(qt_app)
