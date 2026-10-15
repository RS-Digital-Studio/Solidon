"""Die Felder von Analyse- und Teilenleiste sagen, was sie tun, auch dem Bildschirmleser (FD-78).

Die Wahl der Analysekarte trug den Satz nur an ihren Einträgen, nicht am Feld;
Stiftzahl, Verbinderform und der Haken *Zum Zusammenstecken vorbereiten* hatten
eine Kurzhilfe, aber keine zugängliche Beschreibung (``oberflaeche.md``: der
Satz hängt als Kurzhilfe **und** als Beschreibung).
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.ui.analysis_bar import AnalysisBar
from app.ui.split_bar import SplitBar


def test_the_map_choice_says_what_it_does(qt_app: QApplication) -> None:
    bar = AnalysisBar(None)
    try:
        field = bar.selector
        assert field.toolTip(), "ohne Satz am Feld"
        assert field.accessibleDescription() == field.toolTip()
    finally:
        bar.deleteLater()


def test_the_split_fields_describe_themselves(qt_app: QApplication) -> None:
    bar = SplitBar()
    try:
        for field in (bar.connect_halves, bar.count, bar.shape):
            assert field.toolTip(), type(field).__name__
            assert field.accessibleDescription() == field.toolTip(), type(field).__name__
    finally:
        bar.deleteLater()
