"""Die Knopfzeile bleibt im Bild, ohne den Kopf der Karte hinauszurollen (FD-136).

``feature_footer.keep_in_sight`` holt *Übernehmen* nach dem Wechsel der
Handlung ins Sichtfeld. Die Karte wächst danach aber erst auf ihre Höhe (ihre
Öffnungsbewegung): Im Fenster maß das Sichtfeld beim Holen 94 Punkte, danach
896. Der Rollbereich blieb an seinem Anschlag stehen, und Name und Maß der
gewählten Bohrung lagen über dem Rand, obwohl jetzt alles Platz hatte.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QScrollArea, QVBoxLayout, QWidget

from app.ui.feature_footer import keep_in_sight


def _card() -> tuple[QScrollArea, QWidget]:
    """Ein Rollbereich: Kopf 300 Punkte, Knopfzeile 60, darunter 600 weitere."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    content = QWidget()
    rows = QVBoxLayout(content)
    rows.setContentsMargins(0, 0, 0, 0)
    rows.setSpacing(0)
    for height in (300, 60, 600):
        block = QWidget(content)
        block.setFixedHeight(height)
        rows.addWidget(block)
    area.setWidget(content)
    footer = rows.itemAt(1).widget()
    assert footer is not None
    return area, footer


def _rounds() -> None:
    for _round in range(5):
        QApplication.processEvents()


def test_the_footer_comes_into_sight_with_the_least_scroll(qt_app: QApplication) -> None:
    area, footer = _card()
    try:
        area.resize(300, 200)
        area.show()
        _rounds()
        keep_in_sight(footer)
        _rounds()
        top = footer.mapTo(area.viewport(), footer.rect().topLeft()).y()
        assert top >= 0 and top + footer.height() <= area.viewport().height()
    finally:
        area.deleteLater()


def test_a_card_that_grows_afterwards_shows_its_head_again(qt_app: QApplication) -> None:
    area, footer = _card()
    try:
        area.resize(300, 94)
        area.show()
        _rounds()
        keep_in_sight(footer)
        _rounds()
        assert area.verticalScrollBar().value() > 0, "klein muss gerollt werden"
        # Eine Wahl wechselt die Handlung oft mehrmals; jeder Wechsel holt neu.
        keep_in_sight(footer)
        _rounds()

        area.resize(300, 900)
        _rounds()

        assert area.verticalScrollBar().value() == 0, (
            "die Karte hat jetzt Platz für Kopf und Knopfzeile"
        )
    finally:
        area.deleteLater()


def test_a_scroll_by_hand_ends_the_following(qt_app: QApplication) -> None:
    area, footer = _card()
    try:
        area.resize(300, 94)
        area.show()
        _rounds()
        keep_in_sight(footer)
        _rounds()
        bar = area.verticalScrollBar()
        bar.triggerAction(bar.SliderAction.SliderToMaximum)
        _rounds()
        mine = bar.value()

        area.resize(300, 120)
        _rounds()

        assert bar.value() == min(mine, bar.maximum()), "wer selbst rollt, behält seine Lage"
    finally:
        area.deleteLater()
