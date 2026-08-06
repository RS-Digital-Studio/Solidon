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

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import TranslatableText, tr
from app.ui.icons import icon
from app.ui.style import NORMAL, TIGHT


def list_top(field: QRect, height: int, window: QRect) -> int:
    """Wo eine aufgeklappte Liste anfangen soll, damit sie im Fenster bleibt.

    Alle Angaben in Bildschirmkoordinaten. Qt hält eine Aufklappliste am
    *Bildschirm*, nicht am Fenster — eine Liste in der untersten Leiste klappt
    deshalb über die Anwendung hinaus auf den Schreibtisch und verdeckt, was
    dort liegt. Für eine Zeile ganz unten heißt „unten kein Platz" also nicht
    „gar kein Platz", sondern „nach oben".
    """
    if field.bottom() + height <= window.bottom():
        return field.bottom()
    above = field.top() - height
    if above >= window.top():
        return above
    # Weder darüber noch darunter: dann bündig an die Unterkante. Oben
    # abgeschnitten und scrollbar ist besser als über den Rand hinaus.
    return max(window.bottom() - height, window.top())


class BarComboBox(QComboBox):
    """Eine Aufklappliste, die im Fenster bleibt.

    Die Leisten unter dem Viewport sitzen an der Unterkante der Anwendung; ihre
    Listen sind der einzige Ort, an dem das auffällt. Deshalb hier und nicht
    überall: eine Liste im Objektbaum hat das Problem nicht.
    """

    def showPopup(self) -> None:  # noqa: N802 — Qt-Name
        super().showPopup()
        popup = self.view().window()
        window = self.window()
        field = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        frame = QRect(window.mapToGlobal(QPoint(0, 0)), window.size())
        top = list_top(field, popup.height(), frame)
        if top != popup.y():
            popup.move(popup.x(), top)


@dataclass(frozen=True, slots=True)
class Tool:
    """Ein Werkzeug: sein Umschalter, seine Leiste, seine Rücknahme."""

    key: str
    title: TranslatableText | str
    bar: QWidget
    hint: TranslatableText | str = ""
    """Ein Satz, der sagt, was das Werkzeug jetzt erwartet.

    Nicht was es *ist* — das steht auf dem Knopf — sondern was der nächste
    Handgriff wäre: „Ziehen Sie den Regler, oder tippen Sie einen Wert."
    Eine Leiste mit vier Feldern sagt nicht, welches man zuerst anfasst, und
    ein Werkzeug, dessen erster Schritt geraten werden muss, ist eines zu
    viel (Konzept P15 §4, E2)."""
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
        self._row.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        self._row.setSpacing(TIGHT)
        self._row.addStretch(1)

        # Eine Gruppe ohne Zwang: der aktive Knopf lässt sich abwählen, und
        # genau das schließt das Werkzeug wieder.
        self._group = QButtonGroup(self)
        self._group.setExclusive(False)

        # Der Hinweis steht über der Leiste, nicht in der Statuszeile: dort
        # unten liest ihn niemand, der gerade in die Mitte des Bildes schaut,
        # und die Statuszeile trägt schon Maße und Fortschritt. Hier steht er
        # zwischen dem Knopf, den man gerade gedrückt hat, und den Feldern,
        # die er erklärt.
        self._hint = QLabel(self)
        self._hint.setWordWrap(True)
        self._hint.setVisible(False)
        self._hint.setContentsMargins(NORMAL, 0, NORMAL, TIGHT)
        font = self._hint.font()
        font.setItalic(True)
        self._hint.setFont(font)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addLayout(self._row)
        self._layout.addWidget(self._hint)

    def add(
        self,
        key: str,
        title: TranslatableText | str,
        bar: QWidget,
        reset: Callable[[], None] | None = None,
        symbol: str = "",
        hint: TranslatableText | str = "",
    ) -> None:
        """Ein Werkzeug anmelden. Seine Leiste startet verborgen."""
        tool = Tool(key=key, title=title, bar=bar, hint=hint, symbol=symbol, reset=reset)
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
            tool = self._tools[key]
            tool.bar.setVisible(True)
            self._buttons[key].setChecked(True)
            self._hint.setText(str(tool.hint))
            self._hint.setVisible(bool(str(tool.hint)))
        else:
            self._hint.clear()
            self._hint.setVisible(False)

        # Die Zeile sagt an, dass sie jetzt anders hoch sein will.
        #
        # Sie steckt in einer Überlagerung: der Container um sie herum bekommt
        # seine Geometrie gesetzt und rechnet sie nicht selbst aus. Wer sie
        # setzt, muss also erfahren, dass sich die Wunschhöhe geändert hat —
        # und er hört am **Container**, nicht an dieser Zeile. Ohne die
        # Meldung blieb unten alles auf den einunddreißig Pixeln der
        # Knopfreihe stehen, während die Leiste darunter neunzig verlangte:
        # Regler, Felder und Knöpfe lagen über den Umschaltern. Betroffen war
        # **jedes** der sieben Werkzeuge — Schnitt, Messen, Bewegen, Analyse,
        # Schichten, Explosion, Bemalen.
        # Erst rechnen, dann melden: ``sizeHint`` liefert sonst noch den Wert
        # von vorhin, und wer daraufhin platziert, setzt die alte Höhe. Genau
        # das war zu sehen — beim ersten Öffnen eines Werkzeugs bekam die
        # Zeile neununddreißig Pixel statt siebenundneunzig, und erst das
        # nächste Ereignis rückte sie zurecht.
        own = self.layout()
        if own is not None:
            own.activate()
        self.updateGeometry()

        parent = self.parentWidget()
        if parent is not None:
            box = parent.layout()
            if box is not None:
                box.activate()
            parent.updateGeometry()
            QApplication.sendEvent(parent, QEvent(QEvent.Type.LayoutRequest))

        self.toolChanged.emit(key)

    def set_available(self, key: str, available: bool) -> None:
        """Ein Werkzeug anbieten oder verbergen.

        Nicht jedes Werkzeug ist immer sinnvoll: die Explosionsansicht braucht
        zwei Körper, sonst zieht sie nichts auseinander. Der Umschalter
        verschwindet dann — und mit ihm, falls es gerade offen war, seine
        Leiste.

        Der Weg führt bewusst hierher und nicht an der Leiste vorbei: Wer sie
        selbst sichtbar macht, hat zwei Stellen, die dasselbe steuern, und die
        gewinnen abwechselnd. Genau daran lag die Leiste über den Umschaltern.
        """
        if key not in self._tools:
            return
        self._buttons[key].setVisible(available)
        if not available and self._active == key:
            self.activate(None)

    def active(self) -> str | None:
        return self._active

    def close_tool(self) -> None:
        """Was gerade offen ist, schließen. Für Escape und die Befehlspalette."""
        self.activate(None)

    def tool_titles(self) -> dict[str, str]:
        """Schlüssel und Beschriftung — die Befehlspalette liest das."""
        return {key: str(tool.title) for key, tool in self._tools.items()}

    def tools(self) -> dict[str, Tool]:
        """Alles Angemeldete. Der Test über die Hinweissätze liest das."""
        return dict(self._tools)

    def hint_text(self) -> str:
        """Was gerade als Hinweis dasteht — leer, wenn kein Werkzeug offen ist.

        Über den Text und nicht über ``isVisible``: ein Kind-Widget eines
        Fensters, das nie ``show()`` gesehen hat, ist niemals sichtbar, und die
        Suite zeigt keines. Die Sichtbarkeit hängt hier ohnehin am Text — beide
        werden in derselben Zeile gesetzt.
        """
        return self._hint.text()


def strip_title() -> str:
    """Was in der Befehlspalette über den Werkzeugen steht."""
    return tr("Ansicht")
