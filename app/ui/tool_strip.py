"""Die Werkzeugzeile unter dem Viewport (Bauplan §2.4, §2.5).

Vorher lagen sieben Leisten dauerhaft unter dem Modell — Schnitt, Messen,
Bewegen, Analyse, Schichten, Explosion, Bemalen —, zusammen gut vierzig
Steuerelemente in vier Reihen. Keines davon tat etwas, solange niemand es
anfasste; sie kosteten nur Platz und Aufmerksamkeit. Wer die Anwendung zum
ersten Mal öffnete, las *Bemalen · Slot · Radius · Kantenwinkel*, bevor er
wusste, was eine Operation ist.

Jetzt eine Zeile Umschalter, und darunter erscheint genau die Leiste des
Werkzeugs, das gerade gewählt ist. Im Ruhezustand ist keines gewählt: dann
bleiben zwei Zeilen statt fünf, und der Viewport wird entsprechend größer.

**Das ist keine Betriebsart** im Sinne von §2.5. Verboten ist dort das
Umschalten zwischen „Bearbeiten" und „Konstruieren" — zwischen Zuständen der
Szene. Hier bleibt der Zustand die Szene; gewählt wird nur, welches
Ansichtswerkzeug gerade eine Leiste bekommt.

**Schließen nimmt zurück.** Ein Werkzeug abzuwählen hebt seine
Ansichtsänderung auf — der Schnitt verschwindet, die Analysekarte geht aus.
Damit braucht es keinen Eintrag „Kein Schnitt" mehr in einem Aufklappmenü, den
man vergisst zurückzustellen. Wie zurückgenommen wird, sagt der Aufrufer beim
Anmelden: das Wissen darüber liegt dort, wo die Leisten ohnehin verdrahtet
werden, statt verstreut in sieben Widgets.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import TranslatableText, tr
from app.ui.icons import icon


@dataclass(frozen=True, slots=True)
class Tool:
    """Ein Werkzeug: sein Umschalter, seine Leiste, seine Rücknahme."""

    key: str
    title: TranslatableText | str
    bar: QWidget
    symbol: str = ""
    """Name des Symbols neben der Beschriftung. Neben, nicht statt: ein
    unbeschriftetes Zeichen wird geraten (Regel 18)."""
    reset: Callable[[], None] | None = None
    """Was passiert, wenn das Werkzeug geschlossen wird. Ohne das bleibt die
    Ansichtsänderung stehen — richtig für alles, was nicht nur die Ansicht
    ändert."""


class ToolStrip(QWidget):
    """Umschalterzeile plus die Leiste des aktiven Werkzeugs."""

    toolChanged = Signal(object)
    """Der Schlüssel des aktiven Werkzeugs, oder ``None``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tools: dict[str, Tool] = {}
        self._buttons: dict[str, QToolButton] = {}
        self._active: str | None = None

        self._row = QHBoxLayout()
        self._row.setContentsMargins(6, 3, 6, 3)
        self._row.setSpacing(4)
        self._row.addStretch(1)

        # Eine Gruppe ohne Zwang: der aktive Knopf lässt sich abwählen, und
        # genau das schließt das Werkzeug wieder.
        self._group = QButtonGroup(self)
        self._group.setExclusive(False)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addLayout(self._row)

    def add(
        self,
        key: str,
        title: TranslatableText | str,
        bar: QWidget,
        reset: Callable[[], None] | None = None,
        symbol: str = "",
    ) -> None:
        """Ein Werkzeug anmelden. Seine Leiste startet verborgen."""
        tool = Tool(key=key, title=title, bar=bar, symbol=symbol, reset=reset)
        self._tools[key] = tool

        button = QToolButton(self)
        # Beschriftet, nicht nur eingefärbt: welches Werkzeug offen ist, darf
        # nicht allein an einer Farbe hängen (Regel 18). Der gedrückte Zustand
        # ist die zweite Kodierung.
        button.setText(str(title))
        if symbol:
            button.setIcon(icon(symbol, button))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setCheckable(True)
        button.setAutoRaise(True)
        button.setToolTip(str(title))
        button.clicked.connect(lambda _checked, name=key: self.toggle(name))
        self._group.addButton(button)
        self._buttons[key] = button
        self._row.insertWidget(self._row.count() - 1, button)

        bar.setVisible(False)
        self._layout.addWidget(bar)

    def toggle(self, key: str) -> None:
        """Ein Werkzeug öffnen — oder schließen, wenn es schon offen war."""
        self.activate(None if self._active == key else key)

    def activate(self, key: str | None) -> None:
        """Genau ein Werkzeug offen, oder keines.

        Zwei gleichzeitig braucht niemand, und zwei gleichzeitig wären wieder
        der Zustand, aus dem diese Zeile herausführen soll.
        """
        if key is not None and key not in self._tools:
            return
        if self._active == key:
            return

        previous = self._active
        self._active = key
        if previous is not None:
            tool = self._tools[previous]
            tool.bar.setVisible(False)
            self._buttons[previous].setChecked(False)
            if tool.reset is not None:
                tool.reset()
        if key is not None:
            self._tools[key].bar.setVisible(True)
            self._buttons[key].setChecked(True)
        self.toolChanged.emit(key)

    def active(self) -> str | None:
        return self._active

    def close_tool(self) -> None:
        """Was gerade offen ist, schließen. Für Escape und die Befehlspalette."""
        self.activate(None)

    def tool_titles(self) -> dict[str, str]:
        """Schlüssel und Beschriftung — die Befehlspalette liest das."""
        return {key: str(tool.title) for key, tool in self._tools.items()}


def strip_title() -> str:
    """Was in der Befehlspalette über den Werkzeugen steht."""
    return tr("Ansicht")
