"""Die Leiste der Formsitzung (Bauplan §25, Konzept P16 §8).

Sie steht neben der Werkzeugzeile, nicht darin — wie die Skizzenleiste und aus
demselben Grund: Die Umschalter dort sind Ansichtswerkzeuge, die sich
gegenseitig ablösen. Formen ist keines davon; man geht hinein, macht die
Sache, geht heraus (Entscheidung J).

Acht Bedienelemente, nicht mehr: Werkzeug, Radius, Stärke, Symmetrie, ein
Schalter für die erzwungene Etappe, zwei Hinweisfelder und *Fertig*. Die
Grenze steht in ``tests/test_interface_limits.py`` und wird hier eingehalten,
nicht angehoben.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.core.units import DISPLAY_UNITS
from app.i18n import TranslatableText, _, tr
from app.ui.labels import choice_label
from app.ui.style import NORMAL, TIGHT, make_primary

#: Die sechs Werkzeuge in der Reihenfolge, in der man sie braucht: erst
#: auftragen und abtragen, dann die drei, die eine Form beruhigen, zuletzt das
#: eine, das sie schärft.
#:
#: Als ``_()``-Literale und nicht als nackte Zeichenketten mit ``tr()``
#: darüber: Der Einsammler liest den Quelltext, und ``tr(variable)`` sieht er
#: nicht. Sechs Namen wären stumm ins Englische durchgereicht worden — derselbe
#: Fund wie bei den Seitennamen in ``labels.py``.
TOOLS: tuple[tuple[str, TranslatableText], ...] = (
    ("draw", _("Auftragen")),
    ("carve", _("Abtragen")),
    ("smooth", _("Glätten")),
    ("inflate", _("Aufblasen")),
    ("flatten", _("Flachziehen")),
    ("pinch", _("Kneifen")),
)

#: Die Symmetrieebenen, wie die Operation sie kennt.
PLANES: tuple[str, ...] = ("none", "x", "y", "z", "xy", "xz", "yz", "xyz")


class SculptBar(QWidget):
    """Werkzeug, Pinsel und Symmetrie für die laufende Formsitzung."""

    finished = Signal()

    refineRequested = Signal()
    """Der Knopf an der Warnung: das Netz jetzt fein genug machen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.tool = QComboBox(self)
        self.tool.setAccessibleName(tr("Formwerkzeug"))
        for value, title in TOOLS:
            self.tool.addItem(str(title), value)
        self.tool.setToolTip(
            tr(
                "Glätten, Aufblasen und Flachziehen lesen, was vor ihnen liegt — sie kosten "
                "je einen zusätzlichen Durchgang."
            )
        )

        self.radius = QDoubleSpinBox(self)
        self.radius.setRange(0.1, 100.0)
        self.radius.setValue(6.0)
        self.radius.setSuffix(f" {DISPLAY_UNITS[0]}")
        self.radius.setToolTip(tr("Wie weit der Pinsel greift."))

        self.strength = QDoubleSpinBox(self)
        self.strength.setRange(0.05, 10.0)
        self.strength.setSingleStep(0.1)
        self.strength.setValue(1.0)
        self.strength.setSuffix(f" {DISPLAY_UNITS[0]}")
        self.strength.setToolTip(tr("Wie weit ein einzelner Zug die Fläche verschiebt."))

        self.symmetry = QComboBox(self)
        self.symmetry.setAccessibleName(tr("Symmetrie"))
        for value in PLANES:
            self.symmetry.addItem(choice_label(value), value)
        self.symmetry.setToolTip(
            tr("Gespiegelt wird am Objektursprung — nicht am Schwerpunkt, der beim Formen wandert.")
        )

        # Die erzwungene Etappe aus Entscheidung C. Als Schalter und nicht als
        # eigenes Werkzeug: Sie gilt für den *nächsten* Zug, unabhängig davon,
        # womit er gemacht wird.
        self.cut = QCheckBox(tr("Neu ansetzen"), self)
        self.cut.setToolTip(
            tr(
                "Der nächste Zug sitzt auf dem Ergebnis der vorigen, statt sich mit ihnen zu "
                "addieren. Kostet einen Durchgang."
            )
        )

        #: Was die Sitzung über sich weiß: Zahl der Züge und Etappen.
        self.state = QLabel("", self)

        #: Was ihr im Weg steht — zu grobes Netz, zu dünne Wand. Leer, solange
        #: nichts im Weg steht: eine Warnung, die immer dasteht, ist keine.
        self.warning = QLabel("", self)

        #: Die Handlung zur Warnung. Sie stand als Satz da — „erst gleichmäßig
        #: vernetzen" — und ließ den Nutzer allein damit: Sitzung verlassen,
        #: im Menü suchen, eine Kantenlänge raten, neu anfangen. Die Zahl, die
        #: er dabei raten müsste, folgt aus dem Pinselradius und steht dem
        #: Fenster zur Verfügung (§2.7: ein Hinweis endet nicht mit sich
        #: selbst). Sichtbar nur mit der Warnung, zu der er gehört.
        self.refine = QPushButton(tr("Jetzt vernetzen"), self)
        self.refine.setVisible(False)
        self.refine.clicked.connect(self.refineRequested)

        # Kein „Verwerfen" daneben, anders als bei der Skizze: Eine Sitzung
        # ohne Züge hinterlässt nichts, und eine mit Zügen ist eine
        # Transaktion, die ein Undo vollständig zurücknimmt (Regel 19). Ein
        # Knopf, der dasselbe tut wie Strg+Z, wäre ein neunter.
        self.done = QPushButton(tr("Fertig"), self)
        make_primary(self.done)
        self.done.clicked.connect(self.finished)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addWidget(QLabel(tr("Werkzeug"), self))
        layout.addWidget(self.tool)
        layout.addWidget(QLabel(tr("Radius"), self))
        layout.addWidget(self.radius)
        layout.addWidget(QLabel(tr("Stärke"), self))
        layout.addWidget(self.strength)
        layout.addWidget(QLabel(tr("Symmetrie"), self))
        layout.addWidget(self.symmetry)
        layout.addWidget(self.cut)
        layout.addWidget(self.state)
        layout.addWidget(self.warning, stretch=1)
        layout.addWidget(self.refine)
        layout.addWidget(self.done)

    # --- Ablesen ---------------------------------------------------------------

    def values(self) -> dict[str, object]:
        """Was der nächste Zug mitbekommt."""
        return {
            "tool": str(self.tool.currentData()),
            "radius": float(self.radius.value()),
            "strength": float(self.strength.value()),
            "cut": bool(self.cut.isChecked()),
        }

    def plane(self) -> str:
        """Die gewählte Symmetrie, wie die Operation sie schreibt."""
        return str(self.symmetry.currentData())

    def show_count(self, strokes: int, stages: int) -> None:
        """Züge und Etappen — die Etappenzahl ist der Preis aus Entscheidung C
        und gehört sichtbar."""
        if not strokes:
            self.state.setText(tr("Noch kein Zug."))
            return
        self.state.setText(
            tr("{striche} Züge, {etappen} Etappen")
            .replace("{striche}", str(strokes))
            .replace("{etappen}", str(stages))
        )

    def show_warning(self, text: str, refinable: bool = False) -> None:
        """Was im Weg steht — und, wo es sich beheben lässt, der Knopf dazu.

        ``refinable`` ist nicht aus dem Text abzuleiten: Die Warnung über zu
        dünne Wände sieht genauso aus und hat keine Handlung, die von hier aus
        richtig wäre.
        """
        self.warning.setText(text)
        self.refine.setVisible(bool(text) and refinable)
