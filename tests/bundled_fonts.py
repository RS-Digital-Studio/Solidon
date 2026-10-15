"""Die gebündelte Prüfschrift für Fenstertests, deren Messung an der Schriftmetrik hängt.

Offscreen hat Qt unter Windows keine Schrift (``QFontInfo.pointSize()`` ist −1,
jede Familie misst gleich); die DejaVu-Dateien aus ``app/core/geom/data/fonts``
sind die Schrift der Linux-CI und geben jeder Plattform dieselbe echte Metrik
(``tests.md``, „Offscreen gibt es keine Schrift“). Eine Stelle für Laden,
Prüfen und Entfernen; Schrift und Thema der Anwendung gibt ``conftest.py``
nach jedem Fall zurück.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QFontMetrics
from PySide6.QtWidgets import QApplication

FONTS = Path(__file__).parents[1] / "app" / "core" / "geom" / "data" / "fonts"
#: Normal und fett: Hauptknöpfe und Überschriften sind fett gesetzt.
SANS = ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")


@contextmanager
def bundled_font(
    application: QApplication, points: int, files: Iterable[str] = SANS
) -> Iterator[QFont]:
    """DejaVu Sans in ``points`` als Anwendungsschrift, solange der Block läuft.

    Zugesichert wird, dass die Dateien laden, die Familie wirkt und die Metrik
    echt ist (``WWW`` breiter als ``iii``) — sonst misst der Fall die
    synthetische Schrift und bleibt mit falschen Zahlen grün. Danach sind die
    Dateien wieder aus der Schriftdatenbank.
    """
    font_ids = [QFontDatabase.addApplicationFont(str(FONTS / name)) for name in files]
    try:
        assert font_ids and min(font_ids) >= 0, "Die gebündelte Prüfschrift wurde nicht geladen"
        font = QFont("DejaVu Sans", points)
        application.setFont(font)
        assert QFontInfo(application.font()).family() == "DejaVu Sans"
        metrics = QFontMetrics(application.font())
        assert metrics.horizontalAdvance("WWW") > metrics.horizontalAdvance("iii")
        yield font
    finally:
        for font_id in font_ids:
            if font_id >= 0:
                QFontDatabase.removeApplicationFont(font_id)
