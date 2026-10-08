"""Die Leiste des Skelettwerkzeugs (Bauplan §25, Konzept P16 §7.5, RM-561).

Sie steht neben der Werkzeugzeile wie die Skizzen- und die Formleiste, und aus
demselben Grund: Ein Skelett zu setzen ist kein Ansichtswerkzeug, das sich mit
Schnitt und Messen ablöst.

**Gesetzt und gebeugt wird im Bild.** Der erste Klick setzt ein Gelenk, jeder
weitere einen Knochen am Fuß des vorigen; Enter beendet die Kette, ein Klick
auf ein Gelenk setzt dort fort. Ziehen an einem Gelenk beugt den Knochen, der
dort endet. Was in der Leiste bleibt, ist Zustand, Hinweis, Kartenwahl und
*Fertig* — Namen, Winkel als Zahlen und ihre Bindung an Projektparameter
stehen im Schrittdialog (*Diesen Schritt ändern*). *Neue Kette*, *Letzten
zurück* und das Namensfeld sind entfallen: Enter und Strg+Z tun dasselbe, und
Namen braucht nur, wer Winkel bindet.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.i18n import format_decimal, tr
from app.ui.analysis_bar import GestureAnalysis
from app.ui.style import NORMAL, TIGHT, make_primary


class PoseBar(QWidget):
    """Zustand und Abschluss des Skelettwerkzeugs."""

    finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.state = QLabel("", self)

        self.done = QPushButton(tr("Fertig"), self)
        # **Was nach „Fertig" passiert, stand nirgends.** Der Knopf ist das
        # Ende der Sitzung *und* der Anfang eines Verlaufsschritts; wer das
        # nicht weiß, sucht das Skelett anschließend im Bild statt im Verlauf.
        self.done.setToolTip(
            tr("Schließt das Werkzeug und legt Skelett und Stellung als einen Schritt ab.")
        )
        make_primary(self.done)
        self.done.clicked.connect(self.finished)

        self.hint = QLabel(
            tr(
                "Erster Klick ein Gelenk, jeder weitere ein Knochen. Enter beendet die Kette, "
                "Ziehen an einem Gelenk beugt."
            ),
            self,
        )
        self.hint.setWordWrap(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout = QHBoxLayout()
        outer.addLayout(layout)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        self.caption = QLabel(tr("Skelett"), self)
        layout.addWidget(self.caption)
        layout.addWidget(self.state)
        layout.addWidget(self.hint, stretch=1)
        layout.addWidget(self.done)
        self.analysis = GestureAnalysis(self)
        outer.addWidget(self.analysis)

    def set_editing(self, editing: bool) -> None:
        """Nach Fertig bleiben Druckbefund, Kartenwahl und der Rückweg sichtbar."""
        for widget in (self.caption, self.state, self.hint):
            widget.setVisible(editing)
        self.done.setText(tr("Fertig") if editing else tr("Schließen"))

    def show_state(self, bones: int, half: bool) -> None:
        """Wie viele Knochen stehen und ob eine Kette auf ihren ersten Knochen wartet."""
        if half:
            self.state.setText(tr("Ende des Knochens setzen …"))
            return
        if not bones:
            self.state.setText(tr("Noch kein Knochen."))
            return
        # Die Einzahl steht daneben (P0.1): „{count} Knochen" ist im Deutschen
        # auch für einen richtig, im Englischen hieß es „1 bones".
        self.state.setText(
            tr("Ein Knochen") if bones == 1 else tr("{count} Knochen").format(count=bones)
        )

    def show_angle(self, degrees: float) -> None:
        """Während des Ziehens: um wie viel der Knochen gerade gebeugt wird."""
        self.state.setText(
            tr("Gebeugt um {angle}°").format(angle=format_decimal(round(degrees), 0))
        )
