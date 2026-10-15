"""Die Zeilen des Prüfberichts messen sich mit Reserve (FD-109).

Eine umbrechende Befundzeile, die beim Messen gerade noch in eine Zeile
passte, brauchte beim Zeichnen am echten Fenster eine zweite — bei 125 %
Skalierung runden Messen und Zeichnen die Glyphenbreiten verschieden. Qt
gab ihr eine Zeile Höhe und kürzte sie: „Überstand: 10,00 …“, die Zahl, um
die es ging, ohne Einheit. Gemessen wird deshalb um eine Zeichenbreite
schmaler, als gezeichnet wird; gezeichnet wird mit der vollen Breite. Eine
Zeile, die knapp passt, bekommt so ihre zweite Zeile Höhe, statt gekürzt zu
werden.
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSize
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem


class WrappedRowDelegate(QStyledItemDelegate):
    """Misst umbrechende Zeilen eine Zeichenbreite schmaler, als sie gezeichnet werden."""

    @override
    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        narrower = QStyleOptionViewItem(option)
        reserve = narrower.fontMetrics.averageCharWidth()
        if narrower.rect.width() > reserve:
            narrower.rect.setWidth(narrower.rect.width() - reserve)
        hint = super().sizeHint(narrower, index)
        return QSize(
            option.rect.width() if option.rect.width() > 0 else hint.width(), hint.height()
        )
