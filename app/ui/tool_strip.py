"""Die Werkzeugzeile unter dem Viewport (Bauplan §2.4, §2.5).

Vorher lagen sieben Leisten dauerhaft unter dem Modell — Schnitt, Messen,
Bewegen, Analyse, Schichten, Explosion und das Bemalen, das es seit dem
Filament-Umbau (26.08.2026) nicht mehr gibt —, zusammen gut vierzig
Steuerelemente in vier Reihen. Keines davon tat etwas, solange niemand es
anfasste; sie kosteten nur Platz und Aufmerksamkeit. Wer die Anwendung zum
ersten Mal öffnete, las *Bemalen · Slot · Radius · Kantenwinkel*, bevor er
wusste, was eine Operation ist. Die Zeile trägt heute sieben Umschalter, und
gefärbt wird über das Kontextmenü an der Fläche.

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
from dataclasses import dataclass, replace

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, Signal
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
from app.ui.style import NORMAL, TIGHT, set_level


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
    # **Bündig mit der Unterkante des Feldes, nicht darüber.** Verschoben wird
    # erst, nachdem Qt die Liste geöffnet hat — und wer sie öffnet, hält die
    # Maustaste über dem Feld. Endete die Liste an der *Oberkante*, läge der
    # Zeiger beim Loslassen außerhalb, und Qt schließt eine Aufklappliste, die
    # ihren Zeiger verloren hat: Sie ging auf und sofort wieder zu (Roberts
    # Fehlerbericht, 30.08.2026; gerechnet an seiner Fenstergröße lag der
    # Zeiger bei 777 und die Liste endete bei 767).
    #
    # Das Feld zu überdecken ist dabei kein Verlust: Was dort steht, steht auch
    # in der Liste, und zwar als der gewählte Eintrag.
    above = field.bottom() - height
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
    start: Callable[[], None] | None = None
    """Was passiert, wenn das Werkzeug geöffnet wird.

    Es gab nur ``reset``, und darum stand jede Leiste beim Aufklappen auf dem
    Wert, den ihr Konstruktor gesetzt hatte — bei vier von acht war das „aus":
    *Schnitt* zeigte „Kein Schnitt" mit gesperrtem Regler, *Messen* „Nicht
    messen", *Bewegen* keinen Griff im Bild. Der Hinweis darüber sagte
    unterdessen „Ziehen Sie den Regler durch das Teil" und „Zwei Punkte im Bild
    anklicken". Ein Werkzeug, das man nach dem Öffnen erst einschalten muss,
    ist eine Bedienstufe zu viel — und eine, die niemand erwartet, weil der
    Knopf schon gedrückt ist.

    *Analyse* bekommt bewusst keinen: eine Analysekarte kostet Rechenzeit, und
    ihr Hinweis sagt „Karte wählen" — dort ist die leere Vorgabe die ehrliche."""
    shortcut: str = ""
    """Die Tastenfolge, die dieses Werkzeug holt.

    Gesetzt wird sie vom Fenster (``set_shortcut``) und nicht hier
    hineingeschrieben: Wer eine Taste vergibt, muss wissen, welche schon
    vergeben sind, und das weiß das Fenster."""


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
        # Aufrecht statt kursiv (B19). Die Erklärsätze der Werkzeugkarten waren
        # zusammen mit dem Schichthinweis der Skizze die einzigen kursiven Texte
        # der Anwendung — zwei bis drei Zeilen schräg auf dunklem Grund. Die
        # Absicht war „das ist Nebentext", und dafür gibt es die Stufe
        # „caption": kleiner und gedämpft, wie überall sonst im Haus.
        set_level(self._hint, "caption")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addLayout(self._row)
        self._layout.addWidget(self._hint)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        """So breit, dass der Hinweis in **eine** Zeile passt.

        **Ein umbrechender Text verlangt von sich aus zu wenig.** ``QLabel``
        meldet mit ``setWordWrap(True)`` eine bescheidene bevorzugte Breite —
        es kommt ja auch schmal zurecht, nur eben zweizeilig. Die Karte unten
        bekommt genau diesen Wunsch (``overlay._move``: „so breit, wie sie sein
        muss"), und deshalb stand der Hinweis in zwei Zeilen, obwohl im Fenster
        Platz für zwanzig war.

        Bezahlt wurde das in der Höhe: Gemessen am 30.08.2026 über sechs
        Fensterbreiten von 600 bis 1920 war die Kartenhöhe **konstant** — aber
        je Werkzeug verschieden, von 90 Punkten bei *Explosion* bis 130 bei
        *Trennen*. Der Unterschied ist genau die zweite Hinweiszeile. Ein
        Panel, das beim Werkzeugwechsel um vierzig Punkte springt, verdeckt mal
        mehr und mal weniger vom Modell, und niemand weiß, warum.

        Robert hat die Richtung entschieden (30.08.2026): „Wir können das ganze
        Panel ruhig noch breiter machen, damit es in manchen Fällen nicht zu
        hoch wird." Also verlangt der Streifen hier, was der Hinweis für eine
        Zeile braucht. Reicht das Fenster nicht, kürzt ``overlay`` auf die
        verfügbare Breite und der Text bricht wieder um — das ist der richtige
        Rückweg und kein Fehler.

        Dieselbe Regel wie bei der Bewegen-Leiste (``transform_bar.sizeHint``):
        Wer bei Enge nachgibt, muss trotzdem das Volle verlangen, sonst bekommt
        er es nie wieder.
        """
        hint = super().sizeHint()
        text = self._hint.text()
        if text and self._hint.isVisibleTo(self):
            inner = self._hint.contentsMargins()
            one_line = (
                self._hint.fontMetrics().horizontalAdvance(text) + inner.left() + inner.right()
            )
            outer = self.contentsMargins()
            hint.setWidth(max(hint.width(), one_line + outer.left() + outer.right()))
        return hint

    def add(
        self,
        key: str,
        title: TranslatableText | str,
        bar: QWidget,
        reset: Callable[[], None] | None = None,
        symbol: str = "",
        hint: TranslatableText | str = "",
        start: Callable[[], None] | None = None,
    ) -> None:
        """Ein Werkzeug anmelden. Seine Leiste startet verborgen."""
        tool = Tool(
            key=key, title=title, bar=bar, hint=hint, symbol=symbol, reset=reset, start=start
        )
        self._tools[key] = tool

        button = QToolButton(self)
        # Beschriftet, nicht nur eingefärbt: welches Werkzeug offen ist, darf
        # nicht allein an einer Farbe hängen (Regel 18). Der gedrückte Zustand
        # ist die zweite Kodierung.
        button.setText(str(title))
        if symbol:
            # **Eine Farbe, gedrückt wie ungedrückt.** Solange der aktive Knopf
            # die volle Akzentfläche trug, setzte das Stylesheet darauf die
            # dunkle Schrift der Auswahl, und das Symbol daneben kam weiter
            # hell aus dem Thema: 1,58 Kontrast, zwei Zeichen derselben Aussage
            # in entgegengesetzten Farben. Eine eigene Umfärbung hielt das
            # zusammen (``QIcon.Mode.Selected`` gilt der markierten Zeile einer
            # Liste, Qt fragt für einen gedrückten Knopf keinen Modus ab).
            # Seit die Fläche gedämpft ist (``style.active_fill``), behält der
            # Knopf die Schrift des Themas — und dieselbe Farbe trägt dann auch
            # das Symbol, mit 4,93 im dunklen Thema statt 2,72.
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

    def set_shortcut(self, key: str, sequence: str) -> None:
        """Merkt sich die Tastenfolge und schreibt sie in den Tooltip.

        Die Taste selbst installiert das Fenster; hier steht nur, wie sie
        heißt. Sichtbar muss sie sein — ein Kürzel, das nirgends steht, lernt
        niemand, und die Werkzeugzeile hat keinen Platz für eine zweite Zeile
        neben jedem Knopf.
        """
        tool = self._tools.get(key)
        if tool is None:
            return
        self._tools[key] = replace(tool, shortcut=sequence)
        self._buttons[key].setToolTip(f"{tool.title}  ({sequence})")

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
            # Nach dem Sichtbarmachen, nicht davor: was hier geschaltet wird,
            # löst Signale aus, und die treffen eine Leiste, die schon im Bild
            # steht. Und nach ``_active``, damit ein Rückruf, der auf das aktive
            # Werkzeug sieht, sich selbst findet.
            if tool.start is not None:
                tool.start()
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
        # **jedes** Werkzeug der Zeile — Schnitt, Messen, Bewegen, Analyse,
        # Schichten, Explosion, Trennen.
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

    def set_usable(self, usable: bool, reason: str = "") -> None:
        """Alle Werkzeuge anbieten oder ausgrauen — mit dem Grund im Hinweis.

        Ausgegraut und nicht ausgeblendet: Ein Werkzeug, das verschwindet,
        wenn nichts da ist, lässt den Nutzer suchen, wo nichts fehlt; das
        macht ``set_available`` nur für die Explosionsansicht, die bei einem
        einzigen Körper nichts zu zeigen *hätte*.

        Gebraucht wird das für die leere Szene. Die Menüs graut ``_update_actions``
        vorbildlich aus — im selben Zustand sind alle vierunddreißig Einträge
        unter *Ändern* stumpf —, und diese Zeile bot weiter Messen, Bewegen,
        Analyse, Schichten und Trennen an. Ein Werkzeug auf einer leeren
        Szene ist ein Griff ins Nichts.

        Ein offenes Werkzeug wird dabei geschlossen: Was nicht mehr geht,
        bleibt nicht offen stehen.
        """
        for key, button in self._buttons.items():
            tool = self._tools[key]
            button.setEnabled(usable)
            # Der Tooltip trägt im Normalfall das Kürzel; ihn beim Ausgrauen
            # gegen den Grund zu tauschen ist richtig, ihn danach ohne Kürzel
            # zurückzugeben wäre es nicht.
            label = f"{tool.title}  ({tool.shortcut})" if tool.shortcut else str(tool.title)
            button.setToolTip(label if usable else reason)
        if not usable and self._active is not None:
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
