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

from collections.abc import Hashable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from app.core.slice.estimate import Estimate
from app.i18n import tr
from app.ui.labels import localised
from app.ui.style import NORMAL, TIGHT, set_level


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
        self._state: Hashable | None = None
        """Der Dokumentstand der gezeigten Zahl — derselbe Stand vergleicht nicht neu."""
        self._basis: object = None
        """Die Rechengrundlage der gezeigten Zahl — nur bei gleicher wird verglichen."""
        self._change = ""
        """Was der letzte Schritt gekostet hat, solange er der letzte ist."""

        self.summary = QLabel("", self)
        self.delta = QLabel("", self)
        set_level(self.delta, "caption")

        row = QHBoxLayout(self)
        # Innen ein Abstand zur Kante des flachen Knopfs: ohne ihn stand die
        # Zahl auf seinem Rahmen, und „12 g“ las sich als „2 g“ (FD-90).
        row.setContentsMargins(TIGHT, 0, TIGHT, 0)
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
            "Haftungshilfe. Die Gegenprobe aus dem G-Code liefert Werte für den "
            "geplanten Druck."
        )
        way = tr("Klicken öffnet die Druckeinstellungen.")
        self._said = f"{hint} {way}"
        self.setToolTip(self._said)
        self.setAccessibleName(tr("Materialverbrauch und Druckdauer"))
        self.setAccessibleDescription(self._said)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Die beiden Textzeilen bestimmen die Breite des flachen Knopfs."""

        hint = super().sizeHint()
        layout = self.layout()
        if layout is None:
            return hint
        content = layout.sizeHint()
        return QSize(max(hint.width(), content.width()), max(hint.height(), content.height()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Nie schmaler als beide Zeilen (FD-90): In der Statusleiste kürzt die Meldung.

        Neben einem langen Satz stand sonst „14 g ·“, und die Differenz endete
        in „Schrit…“ — Material und Dauer sind die Auskunft, die immer dasteht.
        """
        return self.sizeHint()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt-Name
        """Eingabe aktiviert dieselbe Handlung wie Leertaste und Klick."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def show_estimate(
        self,
        current: Estimate | None,
        project: str = "",
        *,
        state: Hashable | None = None,
        basis: object = None,
        provisional: bool = False,
    ) -> None:
        """Die neue Schätzung zeigen und die vorige als Vergleich behalten.

        Ohne Körper steht dort nichts — nicht „0 g". Eine Null behauptet, es
        gäbe etwas zu messen, und es ist nichts da.

        ``project`` sorgt dafür, dass der Vergleich beim Projektwechsel
        vergessen wird. Über den Namen und nicht über einen Aufruf an drei
        Stellen: Öffnen, Neu und die Wiederherstellung sind drei Wege, und wer
        einen davon vergisst, bekommt eine Ersparnis gegenüber einem Projekt
        gemeldet, das nichts mit dem offenen zu tun hat.

        **Verglichen wird nur, was ein Schritt geändert hat** (FD-89). Die Zahl
        entsteht auch neu, wenn nur die Rechengrundlage wechselt — die
        Grundlage des Slicerprofils kommt aus einem Arbeiter nach der ersten
        Auswertung, ein anderer Drucker oder eine andere Stufe rechnet anders.
        Dann gab es „2,2 g weniger“ ohne Schritt. ``basis``
        ist die Grundlage, ``state`` der Dokumentstand der Zahl: Eine andere
        Grundlage setzt den Vergleich still neu, derselbe Stand (das Bild vor
        dem fertigen Ergebnis, die Einheit, die Kopfzeile) behält die gesagte
        Änderung. ``provisional`` sagt, dass die Grundlage noch gelesen wird;
        die Zahl steht dann als vorläufig da und vergleicht nicht.
        """
        if project != self._project:
            self._project = project
            self._forget()

        if current is None or current.material_mm3 <= 0.0:
            self.summary.setText("")
            self._forget()
            self._say("")
            return

        self.summary.setText(f"{mass(current.grams)} · {duration(current.seconds)}")
        if self._previous is None or basis != self._basis:
            self._change = ""
        elif state is None or state != self._state:
            self._change = change(self._previous, current)
        self._previous = current
        self._state = state
        self._basis = basis
        self._say(tr("vorläufig") if provisional else self._change, provisional=provisional)

    def _forget(self) -> None:
        """Kein Vergleich mehr: neues Projekt oder nichts zu messen."""
        self._previous = None
        self._state = None
        self._basis = None
        self._change = ""

    def _say(self, delta: str, *, provisional: bool = False) -> None:
        """Die zweite Zeile — und warum eine vorläufige Zahl vorläufig ist."""
        self.delta.setText(delta)
        said = self._said
        if provisional:
            said = " ".join(
                (tr("Vorläufig: Die Werte des gewählten Slicerprofils werden noch gelesen."), said)
            )
        self.setToolTip(said)
        self.setAccessibleDescription(said)

    def state(self) -> tuple[str, str]:
        """Was dasteht — die Tests lesen das."""
        return self.summary.text(), self.delta.text()
