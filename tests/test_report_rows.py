"""Eine Befundzeile, die knapp in eine Zeile passt, bekommt ihre zweite Zeile Höhe (FD-109).

Am echten Fenster bei 125 % stand „Überstand: 10,00 …“: Gemessen passte die
Zeile gerade in eine Zeile, gezeichnet brauchte sie zwei, und Qt kürzte die
letzte. Die Liste des Berichts misst jetzt mit einer Zeichenbreite Reserve
(``report_rows.WrappedRowDelegate``). Offscreen runden Messen und Zeichnen
gleich; geprüft wird deshalb die Reserve an der Grenze, wo eine Zeile mit der
gewöhnlichen Messung eben noch in eine Zeile passt.
"""

from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtWidgets import (
    QApplication,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from app.core.types import Finding
from app.ui.report_rows import WrappedRowDelegate

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
