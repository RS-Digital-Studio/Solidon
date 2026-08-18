"""Die Leiste des Skeletteditors (Bauplan §25, Konzept P16 §7.5).

Sie steht neben der Werkzeugzeile wie die Skizzen- und die Formleiste, und aus
demselben Grund: Ein Skelett zu setzen ist kein Ansichtswerkzeug, das sich mit
Schnitt und Messen ablöst.

**Was hier passiert, sind Gesten; was danach passiert, sind Zahlen.** Der
Editor setzt die Knochen — zwei Klicks je Knochen, Kopf und Fuß. Die
*Stellung* setzt niemand mit der Maus: Sie sind drei Winkel je Knochen und
gehören in den Dialog der Operation, wo auch ein Projektparameter stehen darf
(``=@arm_angle``). Das ist der Punkt, an dem Posing hierher gehört und nicht
zu einem Animationsprogramm.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from app.i18n import tr
from app.ui.style import NORMAL, TIGHT, make_primary


class PoseBar(QWidget):
    """Knochen setzen, benennen, Ketten beginnen."""

    finished = Signal()
    chainBroken = Signal()
    lastRemoved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.name = QLineEdit(self)
        self.name.setAccessibleName(tr("Name der Pose"))
        self.name.setPlaceholderText(tr("Name des nächsten Knochens"))
        self.name.setToolTip(
            tr("Leer heißt: durchnummeriert. Ein Name macht die Stellung später lesbar.")
        )

        self.state = QLabel("", self)

        self.chain = QPushButton(tr("Neue Kette"), self)
        self.chain.setToolTip(
            tr(
                "Der nächste Knochen hängt an nichts. Für den zweiten Arm oder das zweite "
                "Bein — sonst wächst alles an einer Kette weiter."
            )
        )
        self.chain.clicked.connect(self.chainBroken)

        self.remove = QPushButton(tr("Letzten zurück"), self)
        self.remove.clicked.connect(self.lastRemoved)

        self.done = QPushButton(tr("Fertig"), self)
        make_primary(self.done)
        self.done.clicked.connect(self.finished)

        self.hint = QLabel(tr("Erst das Gelenk anklicken, dann das Ende des Knochens."), self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addWidget(QLabel(tr("Knochen"), self))
        layout.addWidget(self.name)
        layout.addWidget(self.chain)
        layout.addWidget(self.remove)
        layout.addWidget(self.state)
        layout.addWidget(self.hint, stretch=1)
        layout.addWidget(self.done)

    def next_name(self) -> str:
        """Wie der nächste Knochen heißen soll — leer heißt durchnummeriert."""
        return self.name.text().strip()

    def clear_name(self) -> None:
        """Nach einem gesetzten Knochen ist das Feld wieder leer.

        Ein stehen gebliebener Name wäre der Name des nächsten Knochens, und
        zwei Knochen mit demselben Namen sind ein Skelett, dessen Stellung
        niemand mehr zuordnet.
        """
        self.name.clear()

    def show_state(self, bones: int, pending: bool, chain: bool) -> None:
        """Wie viele Knochen stehen und was der nächste Klick tut."""
        if pending:
            self.state.setText(tr("Ende des Knochens setzen …"))
            return
        if not bones:
            self.state.setText(tr("Noch kein Knochen."))
            return
        self.state.setText(
            tr("{zahl} Knochen").replace("{zahl}", str(bones))
            + ("" if chain else f" · {tr('neue Kette')}")
        )
