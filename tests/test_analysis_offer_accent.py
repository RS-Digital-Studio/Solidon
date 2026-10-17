"""Der Ausweg der Analyseleiste trägt keinen zweiten Akzent (FD-107).

„Dreiecke verringern“ stand orange im Prüfbericht und noch einmal orange in
der Analyseleiste — zwei Hauptknöpfe in einem Fenster, und der Kunde musste
lesen, welcher gemeint ist. Höchstens ein Akzentknopf je Fenster
(``fenster.md``, „Der Hauptknopf“): Ein Ausweg neben einem Satz ist eine
Hinweishandlung und ein gewöhnlicher Knopf. Der Hauptknopf bleibt der des
Berichts.
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.ui.analysis_bar import AnalysisBar


def test_the_way_out_of_the_bar_is_an_ordinary_button(qt_app: QApplication) -> None:
    bar = AnalysisBar(None)
    try:
        bar.show_problem("zu groß", "Dreiecke verringern", lambda: None)
        button = bar.legend.action
        assert button is not None, "der Ausweg fehlt"
        assert not button.isDefault(), "ein zweiter Akzent neben dem Hauptknopf des Berichts"
        assert button.font().weight() == QFont.Weight.Normal, "halbfett ohne Akzent"
    finally:
        bar.deleteLater()
