"""In der Teilenleiste klebt „Stifte“ nicht am Haken davor (FD-120).

„Zum Zusammenstecken vorbereiten Stifte [2]“ las sich als ein Satz: Haken und
Feldbeschriftung standen mit Qts Vorgabeabstand nebeneinander. Die Zahl der
Stifte gehört zu ihrem Feld; zwischen Haken und Feldgruppe steht jetzt ein
deutlich größerer Abstand als zwischen Beschriftung und Feld, und die
Beschriftung ist dem Feld zugeordnet.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.ui.split_bar import SplitBar
from app.ui.style import ROOMY


def test_the_pin_label_stands_apart_from_the_check_box(qt_app: QApplication) -> None:
    bar = SplitBar()
    try:
        bar.resize(900, bar.sizeHint().height())
        bar.show()
        QApplication.processEvents()
        box = bar.connect_halves.geometry()
        label = bar.count_label.geometry()
        field = bar.count.geometry()
        apart = label.left() - box.right()
        together = field.left() - label.right()
        assert apart >= ROOMY, f"Haken und „Stifte“ nur {apart} Punkte auseinander"
        assert apart > together, (apart, together)
        assert bar.count_label.buddy() is bar.count, "die Beschriftung gehört zu ihrem Feld"
    finally:
        bar.deleteLater()
