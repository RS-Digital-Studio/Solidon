"""Mauszeiger des Viewports (§19.3, Regel 18).

Ein Zeiger ist Beiwerk — er darf die Anwendung nie aufhalten und nie
verschwinden. Beides wird hier festgehalten, dazu die zwei Eigenschaften, die
man ihm nicht ansieht: der Saum, ohne den er über einem gewählten Körper
unsichtbar wäre, und der Griffpunkt, der beim Messen den Unterschied macht.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from app.ui import cursors
from app.ui.theme import THEMES


def test_every_role_yields_a_cursor(qt_app: QApplication) -> None:
    """Jede Rolle liefert einen Zeiger — keine leere Grafik, kein Fehler."""
    widget = QWidget()
    for role in cursors.known():
        found = cursors.cursor(role, widget)
        assert found is not None
        if role in cursors.SHAPES:
            assert not found.pixmap().isNull(), role


def test_an_unknown_role_falls_back_instead_of_failing(qt_app: QApplication) -> None:
    """Ein Zeiger hält die Anwendung nie an. Wer eine Rolle falsch schreibt,
    bekommt den gewöhnlichen Pfeil und keine Ausnahme."""
    widget = QWidget()
    assert cursors.cursor("gibtesnicht", widget).shape() == Qt.CursorShape.ArrowCursor


def test_drawn_shapes_carry_the_accent_and_a_dark_edge() -> None:
    """Der Akzent allein genügt nicht: über einem gewählten Körper liegt er auf
    sich selbst. Jede eigene Zeichnung führt deshalb beide Farben."""
    accent = THEMES["dark"]["highlight"]
    edge = THEMES["dark"]["highlight_text"]
    for role in cursors.SHAPES:
        source = cursors.svg_source(role)
        assert accent in source, role
        assert edge in source, role


def test_the_edge_is_drawn_wider_than_the_accent(qt_app: QApplication) -> None:
    """Der Saum entsteht dadurch, dass er *unter* dem Akzent liegt und breiter
    ist. Wäre er dünner, gäbe es ihn nur auf dem Papier."""
    source = cursors.svg_source("measure")
    edge_width = float(source.split('stroke-width="')[1].split('"')[0])
    accent_width = float(source.split('stroke-width="')[2].split('"')[0])
    assert edge_width > accent_width


def test_the_hotspot_sits_where_the_shape_points(qt_app: QApplication) -> None:
    """Beim Fadenkreuz ist der gemeinte Punkt die Mitte, beim Pfeil die Spitze
    oben links. Ein Zeiger, der danebenliegt, misst falsch."""
    widget = QWidget()
    measure = cursors.cursor("measure", widget)
    select = cursors.cursor("select", widget)

    size = measure.pixmap().deviceIndependentSize()
    middle = measure.hotSpot()
    assert abs(middle.x() - size.width() / 2) <= 1.5
    assert abs(middle.y() - size.height() / 2) <= 1.5

    tip = select.hotSpot()
    assert tip.x() < size.width() / 2
    assert tip.y() < size.height() / 2


def test_the_same_role_is_built_once(qt_app: QApplication) -> None:
    """Der Zeiger wird bei jeder Mausbewegung gesetzt. Ihn dabei neu zu rastern
    wäre die teuerste Zeile der Anwendung."""
    widget = QWidget()
    cursors.forget()
    first = cursors.cursor("rotate", widget)
    second = cursors.cursor("rotate", widget)
    assert first is second


def test_forget_lets_a_theme_change_through(qt_app: QApplication) -> None:
    widget = QWidget()
    before = cursors.cursor("zoom", widget)
    cursors.forget()
    assert cursors.cursor("zoom", widget) is not before


def test_system_shapes_stay_system_shapes(qt_app: QApplication) -> None:
    """Wo das System eine bekannte Form hat, wird sie benutzt: Sie folgt der
    eingestellten Zeigergröße, unsere täte das nicht."""
    widget = QWidget()
    assert cursors.cursor("panning", widget).shape() == Qt.CursorShape.ClosedHandCursor
    assert cursors.cursor("move", widget).shape() == Qt.CursorShape.SizeAllCursor
    for role in cursors.SYSTEM:
        assert role not in cursors.SHAPES, f"{role} wäre zweimal beschrieben"
