"""Die Leiste des Aufziehens: Rechteck oder Kreis, ein Satz, *Freie Form …* (RM-559).

Schmal wie die Trennleiste (``split_bar.py``): Sie zeigt, was der nächste Klick
tut, und bietet die zwei Formen und den Weg zum freien Umriss. Sie rechnet
nichts und legt keinen Schritt an — das tut der dritte Klick über
``draw_flow.py``. Ein Knopf, eine Bedeutung; die Formen tragen ihre Taste im
Tooltip, damit man sie nebenbei lernt (R und C wie im Skizzeneditor).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.errors import REPAIR_AND_RETRY, SHOW_LOCATIONS
from app.i18n import tr
from app.ui.draw_tool import DRAW_SHAPES
from app.ui.style import NORMAL, TIGHT


class DrawBar(QWidget):
    """Formwahl und Satz des Werkzeugs *Zeichnen*."""

    shapeChosen = Signal(str)
    """Rechteck oder Kreis — gewählt per Klick; die Tasten gehen über die Ansicht."""
    freeRequested = Signal()
    """*Freie Form …*: Der nächste Klick öffnet den Skizzeneditor auf seiner Fläche."""
    recognitionRequested = Signal()
    """*Merkmale an dieser Stelle erkennen* an einer Stelle ohne erkannte Fläche (F-b)."""
    repairRequested = Signal()
    """*Reparieren und erneut versuchen* nach einer gescheiterten Rechnung (F-i)."""
    placesRequested = Signal()
    """*Stellen zeigen* nach einer gescheiterten Rechnung (F-i)."""
    closeRequested = Signal()
    """*Schließen*: der sichtbare Ausgang neben Escape, für eine Maus ohne Tastatur (G10)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = QLabel("", self)
        self.state.setWordWrap(True)

        self.rectangle = QPushButton(tr("Rechteck"), self)
        self.circle = QPushButton(tr("Kreis"), self)
        self.shapes = QButtonGroup(self)
        self.shapes.setExclusive(True)
        for number, (button, key, hint) in enumerate(
            (
                (self.rectangle, "R", tr("Einen Quader aufziehen: Ecke, Gegenecke, Höhe.")),
                (self.circle, "C", tr("Einen Zylinder aufziehen: Mitte, Rand, Höhe.")),
            )
        ):
            button.setCheckable(True)
            # Ein Mausklick nimmt der Ansicht nicht den Fokus — die Ziffern
            # und Tasten des Entwurfs gehören ihr. Mit der Tabulatortaste
            # bleiben die Knöpfe erreichbar.
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            text = f"{hint} ({key})"
            button.setToolTip(text)
            button.setAccessibleDescription(text)
            self.shapes.addButton(button, number)
        self.rectangle.setChecked(True)
        self.shapes.idClicked.connect(self._chosen)

        self.free = QPushButton(tr("Freie Form …"), self)
        self.free.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        hint = tr(
            "Einen eigenen Umriss im Skizzeneditor zeichnen. Fertig bringt ihn zurück, "
            "dann fehlt nur die Höhe."
        )
        self.free.setToolTip(hint)
        self.free.setAccessibleDescription(hint)
        self.free.clicked.connect(self.freeRequested)

        self.recognise = QPushButton(tr("Merkmale an dieser Stelle erkennen"), self)
        self.recognise.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.recognise.setVisible(False)
        self.recognise.clicked.connect(self.recognitionRequested)

        # Die zwei Auswege nach einer gescheiterten Rechnung (F-i), mit den
        # Wörtern der Handlungen aus dem Kern — derselbe Text wie im Prüfbericht.
        self.repair = QPushButton(str(REPAIR_AND_RETRY.label), self)
        self.repair.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.repair.setVisible(False)
        self.repair.clicked.connect(self.repairRequested)
        self.places = QPushButton(str(SHOW_LOCATIONS.label), self)
        self.places.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.places.setVisible(False)
        self.places.clicked.connect(self.placesRequested)

        self.close_button = QPushButton(tr("Schließen"), self)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        # Der Tastenname aus Qt, nicht von Hand: Im Französischen heißt die
        # Taste „Échap“ (Regel 20, N8).
        key = QKeySequence(Qt.Key.Key_Escape).toString(QKeySequence.SequenceFormat.NativeText)
        leave = f"{tr('Das Werkzeug schließen, ohne einen Körper anzulegen.')} ({key})"
        self.close_button.setToolTip(leave)
        self.close_button.setAccessibleDescription(leave)
        self.close_button.clicked.connect(self.closeRequested)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(TIGHT)
        controls.addWidget(self.rectangle)
        controls.addWidget(self.circle)
        controls.addStretch(1)
        controls.addWidget(self.recognise)
        controls.addWidget(self.repair)
        controls.addWidget(self.places)
        controls.addWidget(self.free)
        controls.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.setSpacing(TIGHT)
        layout.addWidget(self.state)
        layout.addLayout(controls)

    def _chosen(self, number: int) -> None:
        self.shapeChosen.emit(DRAW_SHAPES[number])

    def show_state(self, text: str, shape: str, *, shaping: bool, recognise: bool = False) -> None:
        """Satz, gewählte Form und ob die Form noch wählbar ist."""
        self.state.setText(text)
        (self.circle if shape == "circle" else self.rectangle).setChecked(True)
        self.rectangle.setEnabled(shaping)
        self.circle.setEnabled(shaping)
        self.free.setEnabled(True)
        self.recognise.setVisible(recognise)
        self.repair.setVisible(False)
        self.places.setVisible(False)

    def show_failure(self, text: str, *, repair: bool, places: bool) -> None:
        """Die Rechnung des neuen Schritts ist gescheitert (F-i): Ursache und Auswege."""
        self.state.setText(text)
        self.rectangle.setEnabled(False)
        self.circle.setEnabled(False)
        self.free.setEnabled(False)
        self.recognise.setVisible(False)
        self.repair.setVisible(repair)
        self.places.setVisible(places)
