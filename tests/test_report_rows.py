"""Eine Befundzeile, die knapp in eine Zeile passt, bekommt ihre zweite Zeile Höhe (FD-109).

Am echten Fenster bei 125 % stand „Überstand: 10,00 …“: Gemessen passte die
Zeile gerade in eine Zeile, gezeichnet brauchte sie zwei, und Qt kürzte die
letzte. Die Liste des Berichts misst jetzt mit einer Zeichenbreite Reserve
(``report_rows.WrappedRowDelegate``). Offscreen runden Messen und Zeichnen
gleich; geprüft wird deshalb die Reserve an der Grenze, wo eine Zeile mit der
gewöhnlichen Messung eben noch in eine Zeile passt.

Im Schlusslauf L4 endeten trotzdem Zeilen auf „…“ (pt „… mais a …“, it
„— Parallelepipedo · …“): Qt misst eine Zelle unter einem Stylesheet mit der
ganzen Breite und zeichnet den Text erst nach Innenrand und Auswahlkante —
acht und drei Punkte schmaler, mehr als die Reserve.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPointF, QRect
from PySide6.QtGui import QTextLayout, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from app.core.types import Finding
from app.ui.report_rows import WrappedRowDelegate
from tests.bundled_fonts import bundled_font

LINE = "Ein Objekt steckt unter dem Druckbett. — cube_clean · Überstand: 10,00 mm"


def _height(listing: QListWidget, delegate: QStyledItemDelegate, width: int) -> int:
    option = QStyleOptionViewItem()
    listing.initViewItemOption(option)
    option.rect = QRect(0, 0, width, 100)
    return delegate.sizeHint(option, listing.indexFromItem(listing.item(0))).height()


def test_a_row_that_just_fits_reserves_its_second_line(qt_app: QApplication) -> None:
    listing = QListWidget()
    listing.setWordWrap(True)
    listing.addItem(QListWidgetItem(LINE))
    plain = QStyledItemDelegate(listing)
    one_line = _height(listing, plain, 2000)
    width = 2000
    while _height(listing, plain, width - 1) == one_line:
        width -= 1
    assert _height(listing, plain, width) == one_line, "an der Grenze passt die Zeile eben noch"
    reserved = WrappedRowDelegate(listing)
    assert _height(listing, reserved, width) > one_line, "knapp heißt: eine Zeile mehr Höhe"
    assert _height(listing, reserved, 2000) == one_line, "mit Platz bleibt es eine Zeile"
    listing.deleteLater()


def test_the_report_measures_its_rows_with_the_reserve(qt_app: QApplication) -> None:
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    try:
        panel.add_findings(
            [
                Finding(
                    code="arrange.below_bed",
                    severity="warning",
                    message="Ein Objekt steckt unter dem Druckbett.",
                    values={"excess": "10,00 mm"},
                )
            ]
        )
        assert isinstance(panel.list.itemDelegate(), WrappedRowDelegate)
    finally:
        panel.deleteLater()


#: Die Sätze der Belege aus L4, wie der Bericht sie zeigt.
SENTENCES = (
    "Alterado em Pino de posicionamento e furo de ajuste: Em «Furo» abre-se agora um "
    "orifício abaixo da boca onde antes sobressaía um pino do círculo circunscrito mais a folga.",
    "«Dividi lungo un piano» ha convertito «Parallelepipedo» in un modello a triangoli: le "
    "curve sono segmenti rettilinei, facce e spigoli restano modificabili.",
)


def _cut_rows(listing: QListWidget) -> list[str]:
    """Die Zeilen, deren Text nicht in die Fläche passt, in die Qt ihn zeichnet.

    Gezeichnet wird in ``SE_ItemViewItemText`` (mit Innenrand und Kante aus dem
    Stylesheet), umbrochen auf dessen Breite ohne den Textrand
    (``QCommonStylePrivate::viewItemDrawText``); passt die Höhe nicht, kürzt Qt
    die letzte Zeile. Gewählt, weil die Auswahl die Höhe nicht neu legt und
    ihre Kante den Text einrückt.
    """
    style = listing.style()
    margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, None, listing) + 1
    delegate = listing.itemDelegate()
    assert isinstance(delegate, QStyledItemDelegate)
    cut = []
    for row in range(listing.count()):
        index = listing.indexFromItem(listing.item(row))
        option = QStyleOptionViewItem()
        listing.initViewItemOption(option)
        delegate.initStyleOption(option, index)
        option.rect = listing.visualRect(index)
        option.state |= QStyle.StateFlag.State_Selected
        room = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, listing)
        layout = QTextLayout(option.text, option.font)
        wrapping = QTextOption()
        wrapping.setWrapMode(QTextOption.WrapMode.WordWrap)
        layout.setTextOption(wrapping)
        height = 0.0
        layout.beginLayout()
        while (line := layout.createLine()).isValid():
            line.setLineWidth(room.width() - 2 * margin)
            line.setPosition(QPointF(0.0, height))
            height += line.height()
        layout.endLayout()
        if height > room.height():
            cut.append(f"Zeile {row}: {height:.0f} von {room.height()} Punkten")
    return cut


@pytest.fixture
def styled(qt_app: QApplication) -> Iterator[None]:
    """Prüfschrift und das Stylesheet der Anwendung — ihr Innenrand ist der Fall."""
    from app.ui.style import apply_style

    with bundled_font(qt_app, 9):
        apply_style(qt_app, "light")
        yield


@pytest.mark.parametrize("sentence", SENTENCES, ids=["pt", "it"])
def test_no_report_row_is_cut_at_any_width(
    qt_app: QApplication, styled: None, sentence: str
) -> None:
    """Die Liste des Berichts, wie ``ReportPanel`` sie einrichtet, über viele Breiten."""
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    try:
        panel.add_findings([Finding(code="settings.info", severity="info", message=sentence)])
        source = panel.list
        listing = QListWidget()
        listing.setObjectName(source.objectName())
        listing.setWordWrap(source.wordWrap())
        listing.setTextElideMode(source.textElideMode())
        listing.setHorizontalScrollBarPolicy(source.horizontalScrollBarPolicy())
        listing.setResizeMode(source.resizeMode())
        listing.setItemDelegate(WrappedRowDelegate(listing))
        listing.addItem(source.item(0).clone())
        assert listing.item(0).text() and not listing.item(0).icon().isNull(), "wie im Bericht"
        listing.show()
        found: dict[int, list[str]] = {}
        for width in range(300, 600, 3):
            listing.resize(width, 400)
            for _round in range(3):
                qt_app.processEvents()
            if cut := _cut_rows(listing):
                found[width] = cut
        listing.deleteLater()
        assert not found, f"gekürzt bei {len(found)} Breiten, etwa {next(iter(found.items()))}"
    finally:
        panel.deleteLater()


@pytest.mark.parametrize("where", ["chat", "sketch"])
def test_the_other_wrapped_lists_measure_like_the_report(qt_app: QApplication, where: str) -> None:
    """Zwillinge: Gesprächsverlauf und Bedingungsliste brechen unter demselben Stylesheet um."""
    from PySide6.QtWidgets import QListView

    if where == "chat":
        from app.ui.chat import ChatPanel

        owner = ChatPanel()
        listing = owner.turns
    else:
        from app.ui.sketch_editor import SketchPanel

        owner = SketchPanel()
        listing = owner.constraint_list
    try:
        assert listing.wordWrap()
        assert isinstance(listing.itemDelegate(), WrappedRowDelegate)
        assert listing.resizeMode() == QListView.ResizeMode.Adjust
    finally:
        owner.deleteLater()
