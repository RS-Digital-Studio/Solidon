"""Inhaltsbreite der eingebetteten Auswahlkarte, in logischen Punkten (§2.5)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QBoxLayout,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QScrollArea,
    QStyle,
    QTabWidget,
    QWidget,
)

from app.ui.layout_lifetime import borrowed_items, layout_parts

#: Öffentliche Größenangabe am Raster; die Anordnung bleibt beim Panel.
PAIRING = "cardWidthPairing"
NATURAL_ROW = "cardWidthNaturalRow"
FIELD_WIDTH = "cardWidthFieldMeasure"


def prefer_pairs(layout: QGridLayout, *, quick: bool = False) -> None:
    """Das Raster meldet, welche Zweierzeilen es bei genügend Platz anbietet."""
    layout.setProperty(PAIRING, "quick" if quick else "group")


def prefer_row(layout: QGridLayout, field_width: Callable[[QAbstractSpinBox], int]) -> None:
    """Das Raster bietet eine natürliche Querzeile unabhängig von seiner Anordnung."""
    layout.setProperty(NATURAL_ROW, True)
    layout.setProperty(FIELD_WIDTH, field_width)


def row_width(layout: QGridLayout) -> int:
    """Querbedarf aus Beschriftungen, kompakten Feldminima und Zwischenräumen.

    Derselbe Wert entscheidet über die Anordnung der Koordinaten und ihre
    angebotene Kartenbreite. Die aktuellen Rasterpositionen zählen nicht.
    """
    widgets = [widget for widget, _inner in layout_parts(layout) if widget is not None]
    measure = layout.property(FIELD_WIDTH)
    widths = sum(
        widget.sizeHint().width()
        if isinstance(widget, QLabel)
        else int(measure(widget))
        if isinstance(widget, QAbstractSpinBox) and callable(measure)
        else widget.minimumWidth() or widget.minimumSizeHint().width()
        for widget in widgets
    )
    return widths + max(layout.horizontalSpacing(), 0) * max(len(widgets) - 1, 0)


def button_width(button: QAbstractButton) -> int:
    """Ungebrochener Handlungstitel mit demselben Symbol-/Stilrand wie gezeigt."""
    title = button.property("operationTitle")
    if not isinstance(title, str) or title == button.text():
        return max(button.minimumWidth(), button.sizeHint().width())
    metrics = button.fontMetrics()
    shown = max((metrics.horizontalAdvance(line) for line in button.text().splitlines()), default=0)
    chrome = max(button.sizeHint().width() - shown, 0)
    return max(button.minimumWidth(), metrics.horizontalAdvance(title) + chrome)


def selection_card_width(zone: QWidget, reference: int) -> int | None:
    """Kleinere Auswahl ohne neue Umbrüche; andere Reiter behalten ihre Vorgabe.

    ``reference`` ist die bisher verfügbare Kartenbreite. Sie ist nur der
    Vergleich für Zeilenumbrüche und sinnvolle Zweierzeilen, kein Zielwert.
    Eigene Reiterfenster stehen nicht in der Zone und werden nie vermessen.
    Die Messung verändert weder Texte noch Layouts oder Widgetgeometrien.
    """
    tabs = [zone] if isinstance(zone, QTabWidget) else zone.findChildren(QTabWidget)
    if not any(
        tab.isVisibleTo(zone)
        and (page := tab.currentWidget()) is not None
        and page.isVisibleTo(tab)
        and page.window() is tab.window()
        and page.objectName() == "selectionPage"
        for tab in tabs
    ):
        return None
    return _widget_width(zone, reference)


def _wrapped_width(label: QLabel, reference: int) -> int:
    """Kleinste Breite mit höchstens der Zeilenhöhe an der bisherigen Breite."""
    low = max(label.minimumWidth(), label.minimumSizeHint().width(), 1)
    high = max(reference, low)
    height = label.heightForWidth(high)
    while low < high:
        middle = (low + high) // 2
        if label.heightForWidth(middle) <= height:
            high = middle
        else:
            low = middle + 1
    return low


def _widget_width(widget: QWidget, reference: int) -> int:
    least = max(widget.minimumWidth(), widget.minimumSizeHint().width(), 0)
    if isinstance(widget, QTabWidget):
        if widget.currentIndex() < 0:
            return least
        page = QTabWidget.currentWidget(widget)
        frame = 2 * widget.style().pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth, None, widget
        )
        corners = sum(
            corner.sizeHint().width()
            for side in (Qt.Corner.TopLeftCorner, Qt.Corner.TopRightCorner)
            if (corner := widget.cornerWidget(side)) is not None and not corner.isHidden()
        )
        bar_width = (
            0 if widget.tabBar().isHidden() else widget.tabBar().sizeHint().width() + corners
        )
        return max(least, max(bar_width, _widget_width(page, max(reference - frame, 1))) + frame)
    if isinstance(widget, QScrollArea):
        content = widget.widget()
        if content is None:
            return least
        # Der mögliche Balken gehört zum natürlichen Querbedarf, auch während
        # einer Höhenanimation ohne Überlauf. Seine Sichtbarkeit als Eingang
        # ließe das Breitenziel selbst pendeln und die XYZ-Zeile umklappen.
        chrome = 2 * widget.frameWidth()
        reserve = (
            widget.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent, None, widget)
            if widget.verticalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            else 0
        )
        # Die Vergleichsbreite bleibt ohne Reserve, damit ihre bisherigen
        # Textzeilen und Handlungspaare weiterhin angeboten werden.
        return max(least, _widget_width(content, max(reference - chrome, 1)) + chrome + reserve)
    if isinstance(widget, QLabel) and widget.wordWrap():
        return max(least, _wrapped_width(widget, reference))
    if isinstance(widget, QAbstractButton):
        return max(least, button_width(widget))
    if isinstance(widget, QAbstractSpinBox):
        # Koordinatenfelder setzen ihre stil-/schriftabhängige knappe Breite
        # selbst. Der Wunsch für den äußersten Wertebereich zählt nicht noch einmal.
        return widget.minimumWidth() or least
    layout = widget.layout()
    if layout is not None:
        margins = widget.contentsMargins()
        chrome = margins.left() + margins.right()
        return max(least, _layout_width(layout, max(reference - chrome, 1)) + chrome)
    return max(least, widget.sizeHint().width())


def _item_width(item: QLayoutItem | None, reference: int) -> int:
    if item is None or item.isEmpty():
        return 0
    widget = item.widget()
    if widget is not None:
        return _widget_width(widget, reference)
    layout = item.layout()
    if layout is not None:
        return _layout_width(layout, reference)
    return max(item.minimumSize().width(), 0)


def _pair_width(grid: QGridLayout, reference: int) -> int:
    with borrowed_items(grid) as items:
        widths = [_item_width(item, reference) for _index, item in items if not item.isEmpty()]
    if not widths:
        return 0
    gap = max(grid.horizontalSpacing(), 0)
    if grid.property(PAIRING) == "group":
        paired = 2 * max(widths) + gap
        return paired if len(widths) > 1 and paired <= reference else max(widths)
    first = 2 * max(widths[:2]) + gap
    if len(widths) < 2 or first > reference:
        return max(widths)
    rows = [first]
    for index in range(2, len(widths), 2):
        pair = widths[index : index + 2]
        wanted = 2 * max(pair) + gap
        rows.append(wanted if len(pair) == 2 and wanted <= reference else max(pair))
    return max(rows)


def _layout_width(layout: QLayout, reference: int) -> int:
    margins = layout.contentsMargins()
    chrome = margins.left() + margins.right()
    room = max(reference - chrome, 1)
    gap = max(layout.spacing(), 0)
    if isinstance(layout, QGridLayout) and layout.property(NATURAL_ROW):
        return chrome + row_width(layout)
    if isinstance(layout, QGridLayout) and layout.property(PAIRING):
        return chrome + _pair_width(layout, room)
    if isinstance(layout, QFormLayout):
        labels = [
            layout.itemAt(row, QFormLayout.ItemRole.LabelRole) for row in range(layout.rowCount())
        ]
        label = max((_item_width(item, room) for item in labels), default=0)
        gap = max(layout.horizontalSpacing(), 0)
        fields = [
            _item_width(
                layout.itemAt(row, QFormLayout.ItemRole.FieldRole), max(room - label - gap, 1)
            )
            for row in range(layout.rowCount())
        ]
        spans = [
            _item_width(layout.itemAt(row, QFormLayout.ItemRole.SpanningRole), room)
            for row in range(layout.rowCount())
        ]
        return chrome + max(label + (gap if label else 0) + max(fields, default=0), *spans, 0)
    if isinstance(layout, QGridLayout):
        columns = [0] * layout.columnCount()
        spans = []
        with borrowed_items(layout) as cells:
            for index, item in cells:
                if item.isEmpty():
                    continue
                position = layout.getItemPosition(index)
                assert isinstance(position, tuple)
                _row, column, _height, span = position
                assert isinstance(column, int) and isinstance(span, int)
                width = _item_width(item, room)
                if span == 1:
                    columns[column] = max(columns[column], width)
                else:
                    spans.append(width)
        active = [width for width in columns if width]
        gap = max(layout.horizontalSpacing(), 0)
        return chrome + max(sum(active) + max(len(active) - 1, 0) * gap, *spans, 0)
    with borrowed_items(layout) as borrowed:
        items = [item for _index, item in borrowed if not item.isEmpty()]
        if isinstance(layout, QBoxLayout) and layout.direction() in (
            QBoxLayout.Direction.LeftToRight,
            QBoxLayout.Direction.RightToLeft,
        ):
            fixed = sum(item.sizeHint().width() for item in items if not item.expandingDirections())
            stretch = sum(
                bool(item.expandingDirections() & Qt.Orientation.Horizontal) for item in items
            )
            share = max((room - fixed - gap * max(len(items) - 1, 0)) // max(stretch, 1), 1)
            widths = [
                _item_width(
                    item, share if item.expandingDirections() & Qt.Orientation.Horizontal else room
                )
                for item in items
            ]
            return chrome + sum(widths) + gap * max(len(widths) - 1, 0)
        return chrome + max((_item_width(item, room) for item in items), default=0)
