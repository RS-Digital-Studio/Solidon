"""Die Leiste der Formsitzung (Bauplan §25, Konzept P16 §8, RM-561).

Sie steht neben der Werkzeugzeile, nicht darin — wie die Skizzenleiste und aus
demselben Grund: Die Umschalter dort sind Ansichtswerkzeuge, die sich
gegenseitig ablösen. Formen ist keines davon; man geht hinein, macht die
Sache, geht heraus (Entscheidung J).

Acht Bedienelemente, nicht mehr: vier Werkzeugknöpfe als eine Gruppe, Radius,
Stärke, *Spiegeln*, Zustand, Warnung, Kartenwahl und *Fertig*. Die Grenze
steht in ``tests/test_interface_limits.py`` und wird hier eingehalten, nicht
angehoben. Was wegfiel (RM-561): die Werkzeugliste (ein Klick statt zwei),
*Neu ansetzen* (jede Geste ist eine Etappe), die Liste der acht
Symmetrieebenen (die übrigen stehen im Schrittdialog) und *Dreiecke jetzt
angleichen* (die Sitzung gleicht selbst an).
"""

from __future__ import annotations

from typing import Any, TypedDict

from PySide6.QtCore import QSignalBlocker, QSize, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.geom.sculpt import BRUSH, LEVEL_DEFAULT, LEVEL_RANGE
from app.i18n import TranslatableText, _, tr
from app.ui.analysis_bar import GestureAnalysis
from app.ui.labels import LengthSpin
from app.ui.style import NORMAL, TIGHT, make_primary


class StrokeValues(TypedDict):
    """Was ein Zug an :func:`app.core.geom.sculpt.stroke_at` mitbekommt.

    Benannt und nicht ``dict[str, object]``, denn die Schlüssel sind ein
    Vertrag mit der Operation und kein Wörterbuch. Ohne die Namen im Typ nimmt
    mypy das Auspacken hin — und dann fällt nicht auf, wenn ein Aufrufer die
    Werte daneben neu zusammenstellt. Genau so kam der Pinselradius als
    Anzeigewert in die Geometrie: 0,2 mm, wo 5 mm eingestellt waren.
    """

    tool: str
    radius: float
    strength: float
    brush: int


#: Die vier Werkzeuge, die die Leiste zeigt, in der Reihenfolge, in der man
#: sie braucht, mit dem Satz, der sagt, was sie tun. *Aufblasen* und
#: *Kneifen* rechnet der Kern für alte Schritte weiter; Aufblasen ähnelt
#: Auftragen, und Kneifen faltete bei hoher Stärke (H3, RM-561).
#:
#: Als ``_()``-Literale und nicht als nackte Zeichenketten mit ``tr()``
#: darüber: Der Einsammler liest den Quelltext, und ``tr(variable)`` sieht er
#: nicht.
TOOLS: tuple[tuple[str, TranslatableText, TranslatableText], ...] = (
    ("draw", _("Auftragen"), _("Trägt Material auf, wo der Pinsel streicht.")),
    ("carve", _("Abtragen"), _("Trägt Material ab, wo der Pinsel streicht.")),
    ("smooth", _("Glätten"), _("Gleicht Unebenheiten unter dem Pinsel aus.")),
    ("flatten", _("Flachziehen"), _("Zieht die Fläche unter dem Pinsel eben.")),
)

#: Die Ebene, an der *Spiegeln* spiegelt: links und rechts, X durch die Mitte
#: des Körpers.
MIRROR_PLANE = "x"


class SculptBar(QWidget):
    """Werkzeug, Pinsel und Spiegeln für die laufende Formsitzung."""

    finished = Signal()

    mirrorChanged = Signal()
    """*Spiegeln* ein- oder ausgeschaltet — die Vorschau gilt allen Zügen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.tools = QButtonGroup(self)
        self.tools.setExclusive(True)
        self.tool_buttons: dict[str, QToolButton] = {}
        tool_row = QHBoxLayout()
        tool_row.setContentsMargins(0, 0, 0, 0)
        tool_row.setSpacing(TIGHT)
        for index, (key, title, hint) in enumerate(TOOLS):
            button = QToolButton(self)
            button.setCheckable(True)
            button.setText(str(title))
            button.setToolTip(str(hint))
            button.setAccessibleDescription(str(hint))
            self.tools.addButton(button, index)
            self.tool_buttons[key] = button
            tool_row.addWidget(button)
        self.tool_buttons["draw"].setChecked(True)

        # Radius ist eine Länge und folgt der Anzeigeeinheit (§19.3); was der
        # Kern bekommt, sind Millimeter. Den Startwert setzt das Fenster aus
        # der Körpergröße (``sculpt.brush_radius_for``, H8).
        self.radius = LengthSpin(self)
        self.radius.set_range_mm(0.1, 100.0)
        self.radius.set_value_mm(5.0)
        self.radius.setToolTip(tr("Wie weit der Pinsel greift."))
        # Die Beschriftung links steht im Layout, nicht im Barrierefreiheitsbaum
        # — ohne eigenen Namen wäre das Feld für einen Bildschirmleser ein
        # leeres Kästchen (``oberflaeche.md``).
        self.radius.setAccessibleName(tr("Radius"))

        # **Eine Stufe, keine Länge** (H3): In Millimetern hieß dieselbe Zahl
        # je Werkzeug etwas anderes, und Glätten schoss ab 2 über. Die Stufe
        # bildet der Kern je Werkzeug auf eine Wirkung ab, die nie überschießt.
        self.strength = QSpinBox(self)
        self.strength.setRange(*LEVEL_RANGE)
        self.strength.setValue(LEVEL_DEFAULT)
        self.strength.setToolTip(tr("Wie stark ein Zug wirkt, von 1 bis 10."))
        self.strength.setAccessibleName(tr("Stärke", context="Pinsel"))

        self.mirror = QCheckBox(tr("Spiegeln"), self)
        self.mirror.setToolTip(
            tr(
                "Jeder Zug wirkt auch auf der anderen Seite des Körpers, links und rechts "
                "gespiegelt. Weitere Ebenen über „Diesen Schritt ändern“."
            )
        )
        self._plane = "none"
        """Die Symmetrie der Sitzung, wie die Operation sie schreibt. Ein
        wieder geöffneter Schritt kann eine andere Ebene tragen als X; sie
        bleibt, bis jemand *Spiegeln* umschaltet."""
        self.mirror.toggled.connect(self._mirror_toggled)

        #: Was die Sitzung über sich weiß: die Zahl der Züge.
        self.state = QLabel("", self)

        #: Was ihr im Weg steht — zu grobes Netz, zu dünne Wand. Leer, solange
        #: nichts im Weg steht: eine Warnung, die immer dasteht, ist keine.
        self.warning = QLabel("", self)
        self.warning.setWordWrap(True)

        # Kein „Verwerfen" daneben, anders als bei der Skizze: Eine Sitzung
        # ohne Züge hinterlässt nichts, und eine mit Zügen ist eine
        # Transaktion, die ein Undo vollständig zurücknimmt (Regel 19).
        self.done = QPushButton(tr("Fertig"), self)
        self.done.setToolTip(
            tr("Schließt die Sitzung und legt alle Züge als einen Schritt in den Verlauf.")
        )
        make_primary(self.done)
        self.done.clicked.connect(self.finished)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout = QHBoxLayout()
        outer.addLayout(layout)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addLayout(tool_row)
        layout.addWidget(QLabel(tr("Radius"), self))
        layout.addWidget(self.radius)
        layout.addWidget(QLabel(tr("Stärke", context="Pinsel"), self))
        layout.addWidget(self.strength)
        layout.addWidget(self.mirror)
        self._row = layout
        #: Die zweite Zeile für Zustand und Abschluss, solange die erste nicht
        #: passt (:meth:`_fit`). Leer, wo Platz ist.
        self._tail = QHBoxLayout()
        self._tail.setContentsMargins(NORMAL, 0, NORMAL, 0)
        outer.addLayout(self._tail)
        #: Wie breit die Leiste in einer Zeile sein will — gemerkt, solange sie
        #: eine Zeile ist, wie ``TransformBar._roomy_width``.
        self._roomy_width = 0
        self._wrapped = False
        self._place_tail(self._row)
        self.analysis = GestureAnalysis(self)
        outer.addWidget(self.analysis)

    # --- Breite ------------------------------------------------------------------

    def _place_tail(self, row: QHBoxLayout) -> None:
        """Zustand, Warnung und *Fertig* in diese Zeile."""
        for widget in (self.state, self.warning, self.done):
            self._row.removeWidget(widget)
            self._tail.removeWidget(widget)
        row.addWidget(self.state)
        row.addWidget(self.warning, stretch=1)
        row.addWidget(self.done)

    def _fit(self) -> None:
        """Passt die Leiste nicht in eine Zeile, rückt ihr Ende in eine zweite.

        Am echten Fenster (1 100 Punkte breit, Fensterabnahme 04.10.2026)
        kürzte die eine Zeile jedes Wort. Gemessen wird gegen die im
        einzeiligen Zustand gemerkte Breite, nicht gegen die aktuelle: Sonst
        flackert die Leiste an der Grenze (dieselbe Regel wie
        ``TransformBar._fit_roles``).
        """
        if not self._wrapped:
            self._roomy_width = super().sizeHint().width()
            if self.width() < self._roomy_width:
                self._wrapped = True
                self._place_tail(self._tail)
        elif self.width() >= self._roomy_width:
            self._wrapped = False
            self._place_tail(self._row)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        """Immer der Platz für eine Zeile — sonst wüchse die Leiste nie zurück."""
        hint = super().sizeHint()
        if self._roomy_width:
            hint.setWidth(max(hint.width(), self._roomy_width))
        return hint

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Name
        """Wird es eng, rückt das Ende in die zweite Zeile."""
        super().resizeEvent(event)
        self._fit()

    # --- Ablesen und Setzen -------------------------------------------------------

    def values(self) -> StrokeValues:
        """Was der nächste Zug mitbekommt.

        **Die einzige Lesestelle.** Sie war lange keine — die Methode stand
        hier ohne Aufrufer, während das Fenster dieselben Werte aus den
        Widgets neu zusammenstellte. Zwei Wege zu derselben Auskunft, und der
        benutzte war der falsche.
        """
        return {
            "tool": self.tool(),
            "radius": self.radius.value_mm(),
            "strength": float(self.strength.value()),
            "brush": BRUSH,
        }

    def tool(self) -> str:
        """Das gewählte Werkzeug, wie der Kern es nennt."""
        return next(key for key, button in self.tool_buttons.items() if button.isChecked())

    def set_tool(self, key: str) -> None:
        """Ein Werkzeug wählen — wie ein Klick auf seinen Knopf."""
        self.tool_buttons[key].setChecked(True)

    def plane(self) -> str:
        """Die Symmetrie der Sitzung, wie die Operation sie schreibt."""
        return self._plane

    def set_plane(self, plane: str) -> None:
        """Die Symmetrie eines geöffneten Schritts übernehmen, ohne Meldung."""
        self._plane = plane or "none"
        with QSignalBlocker(self.mirror):
            self.mirror.setChecked(self._plane != "none")

    def _mirror_toggled(self, on: bool) -> None:
        self._plane = MIRROR_PLANE if on else "none"
        self.mirrorChanged.emit()

    def show_count(self, strokes: int) -> None:
        """Wie viele Züge die Sitzung trägt. Etappen gehören dem Kern (RM-561)."""
        if not strokes:
            self.state.setText(tr("Noch kein Zug."))
            return
        # Die Einzahl steht daneben, sie wird nicht gebildet (P0.1).
        self.state.setText(
            tr("Ein Zug") if strokes == 1 else tr("{strokes} Züge").format(strokes=strokes)
        )

    def show_warning(self, text: str) -> None:
        """Was im Weg steht — leer, solange nichts im Weg steht."""
        self.warning.setText(text)
