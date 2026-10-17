"""Der Satz der leeren Parameterleiste misst sich an seiner echten Breite (FD-126).

„Noch keine Parameter. …“ maß seine Höhe einmal beim Bau, an der Grundbreite
der Karte und mit der Schrift von damals (``panels.fit_wrapped``). Mit der
echten Schrift und Spaltenbreite brauchte er mehr, und *Parameter anlegen …*
stand über seiner letzten Zeile. Jetzt ist er ein ``style.WrappedNote``, das
bei jeder Breite neu misst und die Leiste nachziehen lässt.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.core.types import Document
from app.ui.style import WrappedNote, apply_style
from app.ui.theme import apply_theme
from tests.bundled_fonts import bundled_font


def _settle(qt_app: QApplication) -> None:
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        qt_app.processEvents()
        time.sleep(0.005)


def test_the_empty_sentence_claims_its_height_at_every_width(qt_app: QApplication) -> None:
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    try:
        panel.show_document(Document(format_version=1, app_version="0.0.1"))
        panel.show()
        for width in (180, 240, 320):
            panel.resize(width, 400)
            for _round in range(5):
                qt_app.processEvents()
            note = panel._empty
            assert note.minimumHeight() >= note.heightForWidth(note.width()), (
                f"bei {width} Punkten {note.minimumHeight()} statt "
                f"{note.heightForWidth(note.width())}"
            )
            bottom = note.mapTo(panel, note.rect().bottomLeft()).y()
            top = panel.add_button.mapTo(panel, panel.add_button.rect().topLeft()).y()
            assert top >= bottom, f"der Knopf steht über dem Satz ({top} < {bottom})"
            assert isinstance(note, WrappedNote), type(note).__name__
    finally:
        panel.deleteLater()


def _needed(note: WrappedNote) -> int:
    """Was der Satz in seiner Breite braucht, ohne gepinnte Höhen."""
    least, most = note.minimumHeight(), note.maximumHeight()
    note.setMinimumHeight(0)
    note.setMaximumHeight(16_777_215)
    try:
        return max(note.heightForWidth(note.width()), 0)
    finally:
        note.setMinimumHeight(least)
        note.setMaximumHeight(most)


@pytest.mark.parametrize("width", (240, 320))
def test_the_empty_sentence_follows_a_font_change_at_the_same_width(
    qt_app: QApplication, width: int
) -> None:
    """Nach 9 → 14 → 9 pt steht der Satz ganz da und nicht höher als nötig (M1, P4).

    Seit D1 pinnte der Folger auch die Höchsthöhe, und ``WrappedNote`` antwortete
    auf keinen Schriftwechsel: Nach 14 pt waren 48 von 101 Punkten zu sehen, bis
    die Leiste neu gebaut wurde; nach 14 → 9 blieb er 101 hoch für 32 Bedarf.
    """
    from app.ui.panels import ParameterPanel

    with bundled_font(qt_app, 9):
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        panel = ParameterPanel()
        try:
            panel.show_document(Document(format_version=1, app_version="0.0.1"))
            panel.resize(width, 600)
            panel.show()
            found = []
            for points in (9, 14, 9):
                qt_app.setFont(QFont("DejaVu Sans", points))
                _settle(qt_app)
                note = panel._empty
                needed = _needed(note)
                if abs(note.height() - needed) > 1:
                    found.append(f"{points} pt: {note.height()} hoch, der Text braucht {needed}")
                bottom = note.mapTo(panel, note.rect().bottomLeft()).y()
                top = panel.add_button.mapTo(panel, panel.add_button.rect().topLeft()).y()
                if top < bottom:
                    found.append(f"{points} pt: Knopf über dem Satz ({top} < {bottom})")
            assert not found, found
        finally:
            panel.hide()
            panel.deleteLater()
            qt_app.processEvents()
    apply_style(qt_app, "light")
