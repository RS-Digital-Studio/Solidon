"""Explosionsansicht (Bauplan §18.8, §25).

Der Schieber erscheint ab zwei Körpern, denn darunter gibt es nichts
auseinanderzuziehen. Ein Element, das immer sichtbar ist und meistens nichts
tut, bringt Leuten bei, es zu ignorieren.

**Der Plattenwähler stand hier und steht jetzt in der Kopfzeile.** Er gehörte
nie hierher: Wer eine einzelne Platte ansehen wollte, suchte ihn unter einem
Werkzeug, das Teile auseinanderzieht — und fand ihn nur, wenn dort auch der
Schieber etwas zu tun hatte. Siehe :class:`app.ui.header.HeaderBar`.

Der Schieber ändert das Bild und sonst nichts — Stapel, Export und Prüfbericht
sehen jedes Teil dort, wo es ist, auf der Platte, auf die es gehört.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app.i18n import tr
from app.ui.labels import TrackSlider
from app.ui.leash import weak_slot
from app.ui.section_bar import SETTLE_MS
from app.ui.style import NORMAL, TIGHT

#: Der Schieber zählt in Zehnteln, 20 heißt also „doppelter Abstand zur
#: Mitte".
MAX_STEPS = 20

#: Der erste Abstand nach einer Teilung. Sieben Zehntel legen bei zwei
#: gleich großen Hälften genug von der Naht frei, um Stifte und Löcher zu
#: erkennen, ohne die Teile aus dem Zusammenhang zu reißen.
REVEAL_STEPS = 7


class ExplodeBar(QWidget):
    """Zieht die Teile einer Teilung auseinander."""

    factorChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pending = QTimer(self)
        self._pending.setSingleShot(True)
        self._pending.timeout.connect(self._settled)

        self.slider = TrackSlider(Qt.Orientation.Horizontal, self)
        self.slider.setAccessibleName(tr("Abstand der Explosion"))
        self.slider.setRange(0, MAX_STEPS)
        self.slider.setValue(0)
        self.slider.setToolTip(tr("Zieht geteilte Objekte zum Ansehen auseinander."))
        self.slider.valueChanged.connect(self._on_moved)

        self.reset = QPushButton(tr("Zusammen"), self)
        self.reset.clicked.connect(weak_slot(self, lambda bar: bar.slider.setValue(0)))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addWidget(QLabel(tr("Explosionsansicht"), self))
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.reset)
        self.setVisible(False)

    @property
    def factor(self) -> float:
        return self.slider.value() / 10.0

    def show_for(self, objects: int) -> bool:
        """Bereitet die Leiste vor und sagt, ob sie überhaupt etwas zu bieten
        hat.

        Ab zwei Körpern gibt es etwas auseinanderzuziehen, darunter nicht.

        Die Leiste macht sich dabei **nicht** selbst sichtbar. Das tut die
        Werkzeugzeile, der sie gehört — sonst steuern zwei Stellen dieselbe
        Sichtbarkeit, und die eine öffnet, was die andere zugeklappt hält. Der
        Aufrufer gibt die Antwort an ``ToolStrip.set_available`` weiter.
        """
        wanted = objects > 1
        if not wanted and self.slider.value():
            self.slider.setValue(0)
        return wanted

    def reveal(self) -> None:
        """Zieht ein frisch geteiltes Ergebnis sofort zum Prüfen auseinander.

        Der gewöhnliche Schieber ist entprellt, weil ein Zug viele
        Zwischenstände durchläuft. Hier gibt es nur einen fertigen Stand: Auf
        ihn zu warten ließe die Hälften nach der Auswertung erst wie einen
        unveränderten Körper erscheinen — genau dann, wenn der Nutzer nach den
        Stiften sucht.
        """
        self.slider.setValue(REVEAL_STEPS)
        self._pending.stop()
        self.factorChanged.emit(self.factor)

    def _on_moved(self, value: int) -> None:
        """Entprellt wie der Schnitt: jede Stufe baut die ganze Ansicht neu."""
        del value
        self._pending.start(SETTLE_MS)

    def _settled(self) -> None:
        self.factorChanged.emit(self.factor)
