"""Die Zeilen des Prüfberichts messen sich, wie sie gezeichnet werden (FD-109).

Eine umbrechende Befundzeile, die beim Messen gerade noch in eine Zeile
passte, brauchte beim Zeichnen am echten Fenster eine zweite — bei 125 %
Skalierung runden Messen und Zeichnen die Glyphenbreiten verschieden. Qt
gab ihr eine Zeile Höhe und kürzte sie: „Überstand: 10,00 …“, die Zahl, um
die es ging, ohne Einheit. Gemessen wird deshalb um eine Zeichenbreite
schmaler, als gezeichnet wird.

**Und in der Fläche, in die gezeichnet wird.** Unter dem Stylesheet misst Qt
eine Zelle mit ihrer ganzen Breite, zeichnet den Text aber erst nach dem
Innenrand der Zeile und — gewählt — nach ihrer Akzentkante: acht und drei
Punkte schmaler, mehr als die Reserve. Im Schlusslauf L4 endeten so Zeilen auf
„… mais a …“ und „— Parallelepipedo · …“. Die Höhe folgt jetzt dem Text, wie er
in ``SE_ItemViewItemText`` umbricht, gewählt gerechnet: Die Auswahl legt die
Zeilen nicht neu.
"""

from __future__ import annotations

import math
from typing import override

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QPointF, QRect, QSize
from PySide6.QtGui import QTextLayout, QTextOption
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem


def drawn_text_room(option: QStyleOptionViewItem) -> tuple[QRect, int]:
    """Wo Qt den Text einer Zelle zeichnet, und welchen Rand er darin je Seite hält.

    ``SE_ItemViewItemText`` trägt unter dem Stylesheet Innenrand und Kante der
    Zeile; der Rand ist der des Fokusrahmens (``viewItemDrawText``). Eine Quelle
    für die Höhe der Berichtszeilen und für die Textmessung des Prüfstands.
    """
    widget = option.widget
    style = widget.style() if widget is not None else QApplication.style()
    room = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, widget)
    margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, option, widget) + 1
    return room, margin


class WrappedRowDelegate(QStyledItemDelegate):
    """Gibt umbrechenden Zeilen die Höhe, die ihr Text beim Zeichnen braucht."""

    @override
    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        hint = super().sizeHint(option, index)
        width = option.rect.width()
        if width <= 0:
            return hint
        drawn = QStyleOptionViewItem(option)
        self.initStyleOption(drawn, index)
        drawn.rect = QRect(0, 0, width, hint.height())
        drawn.state |= QStyle.StateFlag.State_Selected
        # Wie ``QCommonStylePrivate::viewItemDrawText``: Der Text hält zu beiden
        # Seiten den Rand des Fokusrahmens, dazu die Reserve fürs Runden.
        room, margin = drawn_text_room(drawn)
        line_width = room.width() - 2 * margin - drawn.fontMetrics.averageCharWidth()
        if line_width <= 0:
            return QSize(width, hint.height())
        layout = QTextLayout(drawn.text, drawn.font)
        wrapping = QTextOption()
        wrapping.setWrapMode(QTextOption.WrapMode.WordWrap)
        layout.setTextOption(wrapping)
        text_height = 0.0
        layout.beginLayout()
        while (line := layout.createLine()).isValid():
            line.setLineWidth(line_width)
            line.setPosition(QPointF(0.0, text_height))
            text_height += line.height()
        layout.endLayout()
        # Was die Zelle um ihren Text herum trägt — Innenrand oben und unten.
        frame = drawn.rect.height() - room.height()
        return QSize(width, max(hint.height(), math.ceil(text_height) + frame))
