"""Wird ein losgelassenes Widget wirklich freigegeben? (Regel 18 nicht, aber §35)

**Die Abnahme für den Umbau der Referenzringe, und sie zählt keine Stellen.**
Ein Rückruf, der `self` fängt, an einem Sender, der ein Kind von `self` ist,
schließt einen Ring über die C++-Grenze: `self` → Sender → Rückruf → `self`.
Pythons Speicherbereiniger sieht die mittlere Kante nicht und kann ihn nicht
brechen — das Widget lebt bis zum Prozessende, und in der Suite sind das
siebenhundert Fenster nacheinander.

Dagegen hilft keine Zählung: Dreiunddreißig richtig umgebaute Stellen plus eine
neue falsche ergeben denselben Zustand wie vorher. Was hilft, ist diese Frage,
je Widget-Klasse gestellt — sie wird rot, sobald irgendwo ein Lambda dazukommt,
und sie muss dafür nicht wissen, wo.

Die Formen, gemessen am 22.08.2026 (je zehn Objekte losgelassen):

    connect(self.tue)                       0 von 10 überleben   frei
    connect(lambda: self.tue())            10 von 10             Ring
    connect(partial(self.tue, 1))          10 von 10             Ring
    connect(lambda x=1: self.tue(x))       10 von 10             Ring

`functools.partial` ist die Überraschung darin: Es sieht aus wie die saubere
Fassung eines Lambdas und hält den Besitzer genauso fest.
"""

from __future__ import annotations

import gc
import weakref
from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget

#: Wer hier **nicht** steht, und warum.
#:
#: ``InstallDialog`` und ``KeyDialog`` starten beim Aufbau einen Arbeiter, und
#: ``leash._alive`` hält ihn, solange er läuft — gemessen: ein Arbeiter in der
#: Menge, Dialog gehalten. Das ist die Halteleine bei der Arbeit und kein Ring;
#: ein Test darauf prüfte die Ereignisschleife, nicht die Rückrufe.
#: ``PartCatalog`` hängt an einem ``QTimer.singleShot``, der ohne echte
#: Ereignisschleife nicht feuert. Alle drei gehören hier hinein, sobald es
#: einen verlässlichen Weg gibt, ihre laufende Arbeit abzuwarten.

#: Wie viele je Klasse gebaut und losgelassen werden.
#:
#: Zehn und nicht eines: Ein einzelnes Widget kann aus Gründen überleben, die
#: mit dem Ring nichts zu tun haben — ein Zwischenergebnis in einem Rahmen, ein
#: Verweis in einer Ausnahme, die noch im Traceback hängt. Bleiben alle zehn,
#: ist es kein Zufall.
HOW_MANY = 10


def _builders() -> list[tuple[str, Callable[[], QWidget]]]:
    """Die Widget-Klassen, die auf ihre Freigabe geprüft werden.

    Als Funktionen und nicht als Klassen: Die Einfuhr gehört in den Test und
    nicht in den Kopf der Datei, sonst braucht diese Datei Qt schon beim
    Einsammeln der Tests.
    """
    from app.ui.analysis_bar import AnalysisBar, LayerBar
    from app.ui.command_palette import CommandPalette
    from app.ui.explode_bar import ExplodeBar
    from app.ui.main_window import MainWindow
    from app.ui.panels import HistoryPanel, ObjectTree, ParameterPanel, ReportPanel
    from app.ui.section_bar import MeasureBar, SectionBar
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.sketch_editor import SketchPanel
    from app.ui.tool_strip import ToolStrip
    from app.ui.viewport import Viewport

    return [
        ("Viewport", Viewport),
        ("SketchPanel", SketchPanel),
        # Das Fenster wiegt am schwersten: Die Suite baut über siebenhundert
        # davon nacheinander auf, und jedes ließ rund 7 MB stehen.
        ("MainWindow", lambda: MainWindow(Session(), UiSettings())),
        ("AnalysisBar", AnalysisBar),
        ("LayerBar", LayerBar),
        ("SectionBar", SectionBar),
        ("MeasureBar", MeasureBar),
        ("ExplodeBar", ExplodeBar),
        ("ToolStrip", ToolStrip),
        ("CommandPalette", CommandPalette),
        ("ObjectTree", ObjectTree),
        ("ParameterPanel", ParameterPanel),
        ("HistoryPanel", HistoryPanel),
        ("ReportPanel", ReportPanel),
    ]


@pytest.mark.parametrize("name,build", _builders())
def test_a_released_widget_is_actually_released(
    name: str, build: Callable[[], QWidget], qt_app: QApplication
) -> None:
    """Zehn bauen, zehn loslassen, zählen, wie viele bleiben.

    Bleibt auch nur eines, hält es etwas fest, das es nicht sollte — und der
    Weg dorthin ist immer derselbe: ``gc.get_referrers`` auf das überlebende
    Objekt, und unter den Haltern die Zellen ansehen. So ist der erste Ring
    gefunden worden (ein Lambda am eigenen Schichtzeitgeber des Viewports),
    und so wird der nächste gefunden.
    """
    watchers = []
    for _ in range(HOW_MANY):
        widget = build()
        watchers.append(weakref.ref(widget))
        del widget
    gc.collect()

    alive = [watch for watch in watchers if watch() is not None]
    assert not alive, f"{len(alive)} von {HOW_MANY} {name} überlebten ihr Loslassen"
