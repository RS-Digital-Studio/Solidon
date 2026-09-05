"""Was das Teil kostet, während man daran baut (Bauplan §22, §29).

Material und Druckdauer standen bisher hinter ``Strg+P``: ein Dialog, ein
Formular, ein Slicer-Lauf. Wer während des Konstruierens wissen wollte, was
eine Wandstärke kostet, musste ihn öffnen, lesen und wieder schließen — und
tat es deshalb nicht.

Hier steht dieselbe Auskunft als eine Zeile, die immer dasteht, und **was der
letzte Schritt daran geändert hat**. Der zweite Teil ist der eigentliche
Gewinn: eine absolute Zahl beantwortet „wie teuer", die Differenz beantwortet
„hat sich das gelohnt", und das ist die Frage, die man beim Konstruieren
wirklich stellt.

**Die Zahlen sind geschätzt und sagen das.** Sie kommen aus
``core/slice/estimate.py`` — Volumen und Oberfläche, ohne Schnitt — und werden
mit gemessenen Werten aus dem G-Code nie vermischt (Regel 14, §22.5). Die
Herkunft steht im Hinweis, nicht im Kleingedruckten.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from app.core.slice.estimate import Estimate
from app.i18n import tr
from app.ui.labels import localised
from app.ui.style import NORMAL, set_level


def duration(seconds: float) -> str:
    """Eine Dauer, wie ein Mensch sie sagt.

    Unter einer Stunde in Minuten, darüber in Stunden und Minuten. Keine
    Sekunden: eine Schätzung, die auf die Sekunde genau auftritt, behauptet
    eine Genauigkeit, die sie nicht hat.
    """
    minutes = round(seconds / 60.0)
    if minutes < 60:
        return tr("{minutes} min").format(minutes=minutes)
    return tr("{hours} h {minutes} min").format(hours=minutes // 60, minutes=minutes % 60)


def mass(grams: float) -> str:
    """Masse in Gramm, ohne Nachkommastelle über zehn Gramm.

    „18,4 g" und „18 g" sind bei einer Schätzung dieselbe Aussage, und die
    kürzere liest sich im Vorbeigehen.
    """
    if grams < 10.0:
        return tr("{grams} g").format(grams=localised(f"{grams:.1f}"))
    return tr("{grams} g").format(grams=f"{grams:.0f}")


def change(before: Estimate | None, after: Estimate) -> str:
    """Was der letzte Schritt gekostet oder gespart hat.

    Leer, solange es kein Vorher gibt, und leer bei einer Änderung unter einem
    Gramm: eine Zeile, die nach jedem Klick „±0 g" meldet, wird nach dem
    dritten Mal nicht mehr gelesen.
    """
    if before is None:
        return ""
    delta = after.grams - before.grams
    if abs(delta) < 1.0:
        return ""
    sign = "+" if delta > 0 else "−"
    return tr("{sign}{grams} seit dem letzten Schritt").format(sign=sign, grams=mass(abs(delta)))


class PrintFacts(QToolButton):
    """Material, Dauer und die Änderung — eine Zeile in der Statusleiste."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._previous: Estimate | None = None
        self._project = ""

        self.summary = QLabel("", self)
        self.delta = QLabel("", self)
        set_level(self.delta, "caption")

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(NORMAL)
        row.addWidget(self.summary)
        row.addWidget(self.delta)

        # Der Zeiger ist die erste Auskunft darüber, dass hier etwas passiert —
        # eine Zeile, die auf Klicks reagiert und wie Text aussieht, ist eine
        # versteckte Funktion. Der Satz dahinter ist die zweite (Regel 18), und
        # ``accessibleDescription`` die dritte, für den, der nichts sieht.
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        hint = tr(
            "Geschätzt aus Volumen und Oberfläche, ohne Stützen und ohne "
            "Haftungshilfe. Gemessene Werte liefert die Gegenprobe aus dem G-Code."
        )
        way = tr("Klicken öffnet die Druckeinstellungen.")
        self.setToolTip(f"{hint} {way}")
        self.setStatusTip(way)
        self.setAccessibleName(tr("Materialverbrauch und Druckdauer"))
        self.setAccessibleDescription(f"{hint} {way}")

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Die beiden Textzeilen bestimmen die Breite des flachen Knopfs."""

        hint = super().sizeHint()
        layout = self.layout()
        if layout is None:
            return hint
        content = layout.sizeHint()
        return QSize(max(hint.width(), content.width()), max(hint.height(), content.height()))

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt-Name
        """Eingabe aktiviert dieselbe Handlung wie Leertaste und Klick."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def show_estimate(self, current: Estimate | None, project: str = "") -> None:
        """Die neue Schätzung zeigen und die vorige als Vergleich behalten.

        Ohne Körper steht dort nichts — nicht „0 g". Eine Null behauptet, es
        gäbe etwas zu messen, und es ist nichts da.

        ``project`` sorgt dafür, dass der Vergleich beim Projektwechsel
        vergessen wird. Über den Namen und nicht über einen Aufruf an drei
        Stellen: Öffnen, Neu und die Wiederherstellung sind drei Wege, und wer
        einen davon vergisst, bekommt eine Ersparnis gegenüber einem Projekt
        gemeldet, das nichts mit dem offenen zu tun hat.
        """
        if project != self._project:
            self._project = project
            self._previous = None

        if current is None or current.material_mm3 <= 0.0:
            self.summary.setText("")
            self.delta.setText("")
            self._previous = None
            return

        self.summary.setText(f"{mass(current.grams)} · {duration(current.seconds)}")
        self.delta.setText(change(self._previous, current))
        self._previous = current

    def state(self) -> tuple[str, str]:
        """Was dasteht — die Tests lesen das."""
        return self.summary.text(), self.delta.text()
