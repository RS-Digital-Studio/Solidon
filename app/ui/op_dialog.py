"""Operationsdialoge, erzeugt aus dem Parameterschema (Bauplan §10, §2.4).

Gestufte Tiefe: die zwei bis drei Werte, die Leute wirklich ändern, stehen
vorn; Toleranzen und Auflösungen sitzen hinter „Weitere Einstellungen". Was
wohin gehört, kommt aus ``placement`` im Schema — ein Dialog kann also nicht
von der Operation abdriften, zu der er gehört.

Der Dialog lässt sich auf Werten statt auf den Vorgaben öffnen, und diese eine
Ergänzung bedient zwei Dinge, die verschieden aussehen und dasselbe sind: eine
angeklickte Fläche, die einträgt, wohin die Operation gehört (§18.5), und eine
Operation des Stapels, die zum Korrigieren wieder geöffnet wird (§15.4). Beides
ist „hier sind die Werte, frag danach" — ein zweiter Dialog für den zweiten
Fall wäre ein zweiter Ort, an dem sich ein Parameter vergessen lässt.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core import expressions
from app.core.errors import AppError
from app.core.registry import OperationSpec, caveat_line, inactive_dependency
from app.core.types import ParamSpec
from app.core.units import DEGREE_UNIT, LengthUnit, decimals_for, from_mm, to_mm
from app.i18n import tr
from app.ui.labels import NumberSpin, choice_label, display_unit, explain_choices
from app.ui.leash import weak_slot
from app.ui.style import TIGHT, make_primary, set_level

#: Werte unterhalb dieser Größenordnung werden feiner angezeigt. Eine Toleranz
#: von 0,075 mm wurde bei zwei Nachkommastellen beim Öffnen des Dialogs zu 0,08
#: — eine stille Änderung an einer Zahl, die jemand gemessen hat.
_FINE_BELOW = 1.0

#: Abstand des Dialogs zu Rand und Oberkante des Viewports. Weit genug, dass er
#: als eigenes Fenster erkennbar bleibt, nah genug, dass er zur Ansicht gehört.
DIALOG_MARGIN = 16


def shown_unit(entry: ParamSpec) -> LengthUnit | None:
    """Die Einheit, in der dieses Feld angezeigt wird — oder ``None``.

    ``None`` heißt: hier wird nicht umgerechnet. Das gilt für alles, was keine
    Länge ist — 26 Parameter tragen „grad", vier ein „°", und ein Winkel in Zoll
    wäre Unsinn. Umgerechnet wird ausschließlich ``unit="mm"`` (§19.3), und der
    Kern bekommt in jedem Fall Millimeter zurück (§11.1).
    """
    return display_unit() if entry.unit == "mm" else None


def _decimals_for(entry: ParamSpec, unit: LengthUnit | None = None) -> int:
    """Wie fein ein Feld sein muss, damit sein Wertebereich hineinpasst (§11.2).

    Zwei Stellen genügen für Längen und Winkel; Toleranzen und Spiele leben
    unter einem Millimeter, und dort ist die zweite Stelle die letzte, die noch
    etwas unterscheidet.

    In Zoll sind es mehr, und zwar nicht aus Genauigkeitsliebe: Ein
    Hundertstelmillimeter ist ein Vierteltausendstel Zoll, und mit zwei Stellen
    wäre die Toleranz eines Materialprofils nicht eintippbar. Die Stellenzahl
    je Einheit steht im Kern (``units.decimals_for``), die Feinheitsregel hier —
    beides zusammen, sonst verliert ein feines Feld in Zoll genau die Stelle,
    für die es fein ist.
    """
    base = decimals_for(unit) if unit else 2
    bounds = [abs(value) for value in (entry.minimum, entry.maximum) if value]
    if bounds and max(bounds) <= _FINE_BELOW:
        return base + 1
    return base


#: Wie viel Luft ein Zahlenfeld über seinen Wunsch hinaus bekommt.
#:
#: Zwei Ziffern breit, damit eine getippte Zahl nicht an der Kante klebt, wenn
#: sie länger ist als das größte, was der Wertebereich hergibt.
NUMBER_AIR = 24

#: Wie viele Parameternamen der Hinweis unter einem leeren Ausdrucksfeld nennt.
#:
#: Eine Zeile soll eine Zeile bleiben — wer zwanzig Parameter führt, bekommt
#: die ersten vier und die Vervollständigung im Feld, die alle kennt.
_HINT_NAMES = 4


class ValueField(QWidget):
    """Ein Zahlenfeld, das auch einen Parameterausdruck tragen kann (§13).

    Der Kern kennt Ausdrücke in Operationsparametern seit je — das
    Weg-2-Beispiel bindet ``create_box`` an ``=@breite``, und die Auswertung
    löst sie bei jedem Lauf auf. Der Dialog kannte sie nicht: sein Feld war
    eine ``QDoubleSpinBox``, und ``float("=@breite")`` beendete den Aufbau des
    Dialogs mit einer Ausnahme, die niemand fing. Wer im Verlauf auf eine
    gebundene Operation doppelklickte, sah deshalb gar nichts — kein Dialog,
    keine Meldung, nichts.

    Damit fehlte zugleich der Weg *hin* zu einer Bindung: anlegen ließ sich ein
    Parameter, ihn an ein Maß zu hängen aber nur über den Agenten oder von Hand
    in der Datei. Weg 2 aus §2.2 endete im Fenster auf halber Strecke.

    Der Umschalter macht beides gehbar. Aus steht eine Zahl mit Grenzen und
    Drehknöpfen — der häufige Fall bleibt der bequeme. An steht der Ausdruck
    wörtlich da, so wie ihn der Skizzeneditor an einer Bemaßung zeigt: ihn
    auszurechnen würde verbergen, dass hier ein Parameter hängt. Was daraus
    gerade wird, sagt der Hinweis daneben.
    """

    changed = Signal()

    #: Was auf dem Umschalter steht. Kein Emoji (Sprachregelung), kein Symbol
    #: aus dem Icon-Satz: „fx" ist in jedem CAD dasselbe Zeichen für „hier
    #: rechnet eine Formel", und es braucht keine Übersetzung.
    TOGGLE_TEXT = "fx"

    def __init__(
        self,
        entry: ParamSpec,
        start: Any = None,
        parameter_values: Mapping[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entry = entry
        self._parameter_values = dict(parameter_values or {})
        self._shown = shown_unit(entry)
        """In welcher Einheit dieses Feld spricht — ``None`` heißt Millimeter
        wie der Kern, also ohne Umrechnung."""
        self._core: float | None = None
        """Der Wert, wie er hereinkam — genauer als seine eigene Anzeige.

        40 mm sind 1,5748 Zoll, und aus 1,5748 Zoll werden 39,99992 mm. Ohne
        dieses Feld verschöbe ein Dialog, den man in Zoll nur *ansieht*, jedes
        Maß um den Rundungsfehler seiner Anzeige."""

        self.spin = NumberSpin(self)
        self.spin.setDecimals(_decimals_for(entry, self._shown))
        self.spin.setMinimum(
            self._as_shown(entry.minimum) if entry.minimum is not None else -1_000_000.0
        )
        self.spin.setMaximum(
            self._as_shown(entry.maximum) if entry.maximum is not None else 1_000_000.0
        )
        if self._shown is not None:
            # Der Drehknopf bewegt sich um denselben **physischen** Betrag wie
            # in Millimetern. Qts Vorgabe ist 1.0, und ein ganzer Zoll je Klick
            # wäre ein Sprung über den ganzen Wertebereich einer Wandstärke.
            self.spin.setSingleStep(from_mm(1.0, self._shown))

        # Auch hier der Deckel: Das Drehfeld hat die Größenrichtlinie
        # ``Expanding`` und wuchs deshalb mit dem Dialog — 270 Pixel für einen
        # Wunsch von 156, gemessen an *Kopien in Reihe oder Kreis*. Der
        # Umschalter bleibt rechts stehen, damit die Felder untereinander eine
        # Kante haben; gewachsen wäre allein die leere Fläche vor ihm.
        self.spin.setMaximumWidth(self.spin.sizeHint().width() + NUMBER_AIR)

        self.text = QLineEdit(self)
        # Dieselbe Schreibweise wie im Handbuch — dort steht „@breite/2" ohne
        # Leerzeichen. Zwei Kundentexte, die dieselbe Sache verschieden
        # schreiben, lassen den Leser nach dem Unterschied suchen.
        self.text.setPlaceholderText(tr("zum Beispiel =@breite/2"))
        self.text.setVisible(False)
        # **Was hier erlaubt ist, steht nicht im Feld.** Wer umschaltet, sah ein
        # leeres Textfeld und ein Beispiel — welche Parameter es gibt und welche
        # Funktionen die Grammatik kennt, stand nirgends. Beides kommt aus der
        # Sache selbst: die Namen aus dem Projekt, die Funktionen aus dem
        # Auswerter (Regel: eine Wahrheit, nicht zwei Listen).
        self.text.setToolTip(self._grammar_help())
        self.text.setStatusTip(str(tr("Ein Ausdruck rechnet mit Projektparametern.")))
        self.text.setAccessibleDescription(self._grammar_help())

        #: Vervollständigt ``@name`` beim Tippen. Ohne sie muss der Kunde die
        #: Namen seiner Parameter auswendig wissen — und ein Tippfehler wird
        #: erst beim Übernehmen zum Fehler.
        self._completer = QCompleter(
            sorted(f"{expressions.REFERENCE_PREFIX}{name}" for name in self._parameter_values),
            self,
        )
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setWidget(self.text)
        self._completer.activated.connect(self._insert_reference)

        self.parameter_button = QToolButton(self)
        self.parameter_button.setText(expressions.REFERENCE_PREFIX)
        self.parameter_button.setAutoRaise(True)
        self.parameter_button.setToolTip(tr("@name setzt einen Projektparameter ein."))
        self.parameter_button.setAccessibleName(tr("Parameter"))
        parameter_menu = QMenu(self.parameter_button)
        for name in sorted(self._parameter_values):
            action = parameter_menu.addAction(f"{expressions.REFERENCE_PREFIX}{name}")
            action.setData(name)
        parameter_menu.triggered.connect(weak_slot(self, ValueField._take_reference, forward=True))
        self.parameter_button.setMenu(parameter_menu)
        self.parameter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.parameter_button.setEnabled(not parameter_menu.isEmpty())
        self.parameter_button.setVisible(False)

        self.toggle = QToolButton(self)
        self.toggle.setText(self.TOGGLE_TEXT)
        self.toggle.setCheckable(True)
        self.toggle.setAutoRaise(True)
        self.toggle.setToolTip(tr("Statt einer Zahl einen Parameterausdruck eintragen."))
        # Ein Umschalter, der nur anders aussieht, wäre Bedeutung allein über
        # Farbe (Regel 18). Der gedrückte Zustand *und* das sichtbar andere
        # Feld sagen dasselbe, und der Hinweis darunter sagt es ein drittes Mal.
        self.toggle.setAccessibleName(tr("Parameterausdruck"))

        self.hint = QLabel("", self)
        self.hint.setVisible(False)
        set_level(self.hint, "caption")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TIGHT)
        row.addWidget(self.spin, 1)
        row.addWidget(self.text, 1)
        row.addWidget(self.parameter_button)
        row.addWidget(self.toggle)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(row)
        layout.addWidget(self.hint)

        self.set_value(entry.default if start is None else start)

        self.toggle.toggled.connect(self._switch)
        self.spin.valueChanged.connect(self.changed)
        self.text.textChanged.connect(self._on_text)
        # Ohne diese Zeile läuft ``eventFilter`` nie — und damit bliebe der
        # Weg zu, den Handbuch und Parameterdialog beschreiben.
        self.spin.installEventFilter(self)

    # --- Wert -------------------------------------------------------------------

    def _as_shown(self, value_mm: float) -> float:
        """Ein Kernwert, wie das Feld ihn zeigt."""
        return from_mm(value_mm, self._shown) if self._shown else value_mm

    def _as_core(self, shown: float) -> float:
        """Was im Feld steht, wie der Kern es bekommt — immer Millimeter."""
        return to_mm(shown, self._shown) if self._shown else shown

    def set_value(self, value: Any) -> None:
        """Trägt Zahl oder Ausdruck ein und stellt das Feld passend."""
        if expressions.is_expression(value):
            self.text.setText(str(value))
            self.toggle.setChecked(True)
            self._switch(True)
            return
        if value is not None:
            try:
                self._core = float(value)
                self.spin.setValue(self._as_shown(float(value)))
            except (TypeError, ValueError):
                # Ein Wert, der weder Zahl noch Ausdruck ist, gehört trotzdem
                # gezeigt statt verschluckt — sonst stünde im Dialog etwas
                # anderes, als im Dokument steht.
                self.text.setText(str(value))
                self.toggle.setChecked(True)
                self._switch(True)

    def value(self) -> float | str:
        """Die Zahl, oder der Ausdruck wörtlich.

        Ein leer geräumtes Ausdrucksfeld gibt die Zahl zurück, die daneben
        stand. Ein leerer Text wäre weder das eine noch das andere, und der
        Stapel bekäme einen Parameter, den keine Auswertung lesen kann.
        """
        if self.toggle.isChecked() and (entered := self.text.text().strip()):
            # Ein Ausdruck bleibt wörtlich. Ihn umzurechnen hieße, „=@breite/2"
            # in eine Zahl zu verwandeln — die Bindung wäre weg, und §13 rechnet
            # ohnehin in Millimetern.
            return entered
        return self._number()

    def _number(self) -> float:
        """Die Zahl des Feldes in Millimetern, gleich was gerade sichtbar ist.

        Eine eigene Methode, weil zwei Stellen sie brauchen: ``value()`` und
        das Umschalten in den Ausdrucksmodus. Letzteres las die Zahl vorher
        direkt aus dem Drehfeld, also **als Anzeigewert** — in Zoll wurde aus
        40 mm der Ausdruck „=1.5748", und weil §13 in Millimetern rechnet, war
        das ein Datenfehler und kein Anzeigefehler.
        """
        shown = float(self.spin.value())
        if self._core is not None and self._unchanged(shown):
            # Angesehen, nicht angefasst: Dann gilt der Wert, der hereinkam.
            # Die Rückrechnung würde hier nur die Rundung der Anzeige
            # festschreiben — bei 40 mm in Zoll wären das 39,99992.
            return self._core
        return self._as_core(shown)

    def _unchanged(self, shown: float) -> bool:
        """Ob die Anzeige noch den Wert zeigt, der hereinkam.

        Verglichen wird auf **Anzeigegenauigkeit** und nicht mit ``==``
        (Regel 6): Der gemerkte Wert ist feiner als das Feld, und genau darum
        geht es. Eine halbe letzte Stelle ist die Grenze — darüber hat jemand
        gedreht.
        """
        assert self._core is not None
        step = 10.0 ** -self.spin.decimals()
        return abs(self._as_shown(self._core) - shown) < step / 2.0

    # --- Umschalten -------------------------------------------------------------

    def _switch(self, to_expression: bool) -> None:
        self.spin.setVisible(not to_expression)
        self.text.setVisible(to_expression)
        self.parameter_button.setVisible(to_expression)
        self.hint.setVisible(to_expression)
        if to_expression and not self.text.text().strip():
            # Aus der stehenden Zahl wird der Anfang des Ausdrucks: wer
            # umschaltet, will meist dieselbe Größe anders ausdrücken. Also die
            # Größe und nicht ihre Anzeige — ein Ausdruck rechnet in
            # Millimetern (§13), und der Hinweis darunter beschriftet ihn auch
            # so. „= 1.5748 mm" unter einem Feld, in dem 40 mm gemeint waren,
            # war die Anzeige, die ihren eigenen Fehler bezeugt.
            self.text.setText(f"={self._number():g}")
        if to_expression:
            # **Der Fokus geht mit.** Ohne diese Zeile bleibt er auf dem
            # Umschalter, und das Textfeld liegt in der Tab-Reihenfolge davor
            # (Spin, Text, Umschalter) — der Kunde muss Umschalt+Tab drücken,
            # um in das Feld zu kommen, das er gerade aufgemacht hat.
            self.text.setFocus()
            self.text.setCursorPosition(len(self.text.text()))
        self._describe()
        self.changed.emit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Fängt ``=`` und ``@`` im Zahlenfeld ab und macht daraus einen
        Ausdruck.

        Am Filter und nicht in :class:`NumberSpin`: Die Klasse steht auch dort,
        wo es gar keine Ausdrücke gibt (Druckeinstellungen, Skizzenmaße), und
        dort wäre ein Zeichen, das plötzlich ein Textfeld aufmacht, ein
        Rätsel. Hier gehört es zur Sache — neben dem Feld steht der fx-Knopf.
        """
        if watched is self.spin and event.type() == QEvent.Type.KeyPress:
            typed = getattr(event, "text", lambda: "")()
            if typed in (expressions.EXPRESSION_PREFIX, expressions.REFERENCE_PREFIX):
                self.start_expression(typed)
                return True
        return super().eventFilter(watched, event)

    def start_expression(self, first: str) -> None:
        """Schaltet auf den Ausdruck um und beginnt ihn mit ``first``.

        **Weil drei Texte des Programms genau das versprechen.** Das Handbuch
        schreibt „Im Feld einer Operation schreiben Sie dann ``=@breite``
        statt einer Zahl", der Parameterdialog sagt „Operationen und Skizzen
        verweisen mit @name darauf", und die Werkzeugbeschreibung des Agenten
        setzt dieselbe Schreibweise. Wer dem folgte und in das Zahlenfeld
        tippte, bekam **nichts**: :class:`NumberSpin` weist ``=`` und ``@``
        ab — kein Ton, kein Zeichen, keine Meldung.

        Damit war der fx-Knopf nicht die Anzeige eines Zustands, sondern die
        Voraussetzung, ihn überhaupt zu erreichen — und die kannte nur, wer
        ihn schon gefunden hatte. Jetzt ist das getippte Zeichen selbst der
        Weg, und der Knopf zeigt bloß, wo man gelandet ist.
        """
        self.toggle.setChecked(True)
        self.text.setText(first)
        self.text.setFocus()
        self.text.setCursorPosition(len(first))
        self._describe()
        self._offer_references()

    def _on_text(self) -> None:
        self._describe()
        self._offer_references()
        self.changed.emit()

    def _grammar_help(self) -> str:
        """Was ein Ausdruck darf, in vier Zeilen.

        Die Funktionsnamen holt :func:`app.core.expressions.function_names` aus
        der Tabelle des Auswerters — hier aufgezählt wären sie eine zweite
        Wahrheit, die beim nächsten Zuwachs still veraltet.
        """
        return "\n".join(
            (
                str(tr("Ein Ausdruck beginnt mit = und rechnet in Millimetern.")),
                str(tr("@name setzt einen Projektparameter ein.")),
                # **Der Tastatur-Bindestrich, nicht das typografische Minus.**
                # Der Auswerter nimmt nur die vier ASCII-Zeichen; das lange
                # Minus aus dem Schriftsatz lehnt er ab (gemessen). Eine Hilfe,
                # die ein Zeichen zeigt, das danach nicht funktioniert, ist
                # schlimmer als keine.
                str(tr("Erlaubt: + - * / und Klammern.")),
                # Und die Falle daneben: Das Zahlenfeld nebenan liest „12,5",
                # der Auswerter nicht — dort trennt das Komma die Argumente von
                # min und max. Wer das nicht weiß, tippt sein gewohntes Komma.
                str(tr("Zahlen mit Punkt: 10.5 statt 10,5.")),
                f"{tr('Funktionen:', 'Ausdruck')} {', '.join(expressions.function_names())}",
            )
        )

    def _reference_prefix(self) -> tuple[int, str] | None:
        """Der angefangene ``@name`` links vom Cursor — Startstelle und Text.

        ``None``, wenn dort keiner steht. Gesucht wird nur bis zum letzten
        Zeichen, das in einem Namen nicht vorkommen darf: Ein ``@`` weiter
        vorne im Ausdruck gehört einem anderen Verweis.
        """
        cursor = self.text.cursorPosition()
        head = self.text.text()[:cursor]
        start = head.rfind(expressions.REFERENCE_PREFIX)
        if start < 0:
            return None
        word = head[start + 1 :]
        if word and not word.replace("_", "").isalnum():
            return None
        return start, head[start:]

    def _offer_references(self) -> None:
        """Zeigt die passenden Parameternamen, sobald ein ``@`` getippt ist."""
        popup = self._completer.popup()
        if popup is None:
            # Offscreen gibt es keins — dann gibt es auch nichts anzubieten.
            return
        found = self._reference_prefix()
        if found is None or not self.text.isVisible():
            popup.hide()
            return
        _, typed = found
        self._completer.setCompletionPrefix(typed)
        if not self._completer.completionCount():
            popup.hide()
            return
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        self._completer.complete()

    def _insert_reference(self, chosen: str) -> None:
        """Ersetzt den angefangenen ``@name`` durch den gewählten."""
        found = self._reference_prefix()
        if found is None:
            return
        start, typed = found
        text = self.text.text()
        self.text.setText(f"{text[:start]}{chosen}{text[start + len(typed) :]}")
        self.text.setCursorPosition(start + len(chosen))

    def _take_reference(self, action: Any) -> None:
        """Bindet den im sichtbaren @-Menü gewählten Projektparameter."""
        name = str(action.data() or "")
        if not name:
            return
        chosen = f"{expressions.REFERENCE_PREFIX}{name}"
        entered = self.text.text().strip()
        # ``fx`` beginnt mit der bisherigen Zahl. Die erste @-Auswahl meint in
        # diesem einfachen Zustand fast immer „an dieses Maß binden" und nicht
        # „die Zahl ohne Rechenzeichen vor einen Namen schreiben".
        try:
            if entered.startswith("="):
                float(entered[1:].strip())
                plain_number = True
            else:
                plain_number = False
        except ValueError:
            plain_number = False
        if not entered or plain_number:
            self.text.setText(f"={chosen}")
            self.text.setCursorPosition(len(self.text.text()))
            return
        found = self._reference_prefix()
        if found is not None:
            self._insert_reference(chosen)
            return
        self.text.insert(chosen)

    def _describe(self) -> None:
        """Sagt unter dem Feld, was der Ausdruck gerade ergibt — oder woran er
        hängt.

        Ohne das wäre der Ausdruck eine Behauptung bis zum Übernehmen. §2.7
        will Fehler als Vorschlag, und der billigste Vorschlag ist der, der
        kommt, bevor etwas schiefgeht.
        """
        if not self.toggle.isChecked():
            return
        entered = self.text.text().strip()
        if not entered:
            # Der Satz bleibt, wie er ist — er ist sein eigener Katalogschlüssel.
            # Was die Namen angeht, kommt als eigenständiger Zusatz dahinter:
            # Ein leeres Feld, das „beginnt mit =" sagt, verschweigt genau das,
            # was der Kunde als Nächstes braucht — womit er rechnen kann.
            waiting = str(tr("Noch kein Ausdruck — er beginnt mit ="))
            names = sorted(self._parameter_values)
            if names:
                shown = ", ".join(
                    f"{expressions.REFERENCE_PREFIX}{name}" for name in names[:_HINT_NAMES]
                )
                if len(names) > _HINT_NAMES:
                    shown = f"{shown} …"
                waiting = f"{waiting}  ·  {tr('Parameter:', 'Ausdruck')} {shown}"
            self.hint.setText(waiting)
            return
        try:
            expressions.check(entered)
            value = expressions.evaluate(entered, self._parameter_values)
        except AppError as problem:
            self.hint.setText(str(problem.detail or problem.title))
            return
        unit = f" {self._entry.unit}" if self._entry.unit else ""
        self.hint.setText(f"= {value:g}{unit}")


class MaterialField(QComboBox):
    """Welches Material ein Teil ist — gewählt, nicht getippt.

    Hier stand ein Textfeld, und der Kunde musste die **Kennung** erraten: Wer
    „PETG" tippte — so steht es in der Kopfzeile, im Druckdialog und auf jeder
    Spule — bekam „Dieses Materialprofil ist nicht bekannt.", denn intern heißt
    es ``petg``. Ein Feld, das nur eine von sechs Zeichenketten annimmt und
    keine davon nennt, ist eine Ratefrage (Robert, 27.08.2026).

    **Gefüllt wird zur Laufzeit, nicht aus einer festen Liste.** Der Katalog
    wächst: ``profiles.reload()`` trägt ausdrücklich „verwirft den Cache, etwa
    nachdem der Nutzer ein Profil bearbeitet hat". Eine ``enum``-Aufzählung im
    Schema wäre am Tag richtig, an dem sie geschrieben wird, und stumm falsch,
    sobald jemand ein eigenes Material anlegt.

    Sichtbar ist der Titel (PETG), Wert ist die Kennung (``petg``) — dieselbe
    Trennung wie im Filamentwähler nebenan.
    """

    def __init__(self, start: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.core.knowledge import profiles

        # „Wie das Projekt" zuerst: Das ist die Vorgabe des Parameters (leer)
        # und der häufigste Fall — ein Teil, das nicht abweicht.
        self.addItem(tr("Wie das Projekt"), "")
        for key, profile in sorted(
            profiles.material_profiles().items(), key=lambda item: str(item[1].title)
        ):
            self.addItem(str(profile.title), key)
        found = self.findData(start or "")
        self.setCurrentIndex(max(found, 0))

    def value(self) -> str:
        """Die Kennung, nie der Titel — der ist übersetzt und wechselt."""
        chosen = self.currentData()
        return str(chosen) if chosen else ""


class ImageSourceField(QWidget):
    """Eine Quelle wählen — oder eine neue von der Platte holen (§25, P16.7).

    Ein ``source``-Feld bot an, was das Projekt an Quellen hat, und dorthin
    führte kein Bildformat: Wer „Relief auflegen" wählte, sah eine STL in einem
    Feld namens „Bild", und der Befund danach schlug „Ein Bild wählen." vor —
    eine Handlung, die die Oberfläche nicht anbot. Der Knopf ist dieser
    fehlende Weg.

    **Und er fehlte am Quellenfeld genauso, nur ohne dass es jemand meldete.**
    *Modell laden*, *STEP laden* und *Zeichnung extrudieren* zeigen dort die
    Quellen, die das Projekt schon hat — in einem frischen Projekt also nichts.
    Die Liste klappte auf und war leer; das liest sich nicht als „hier fehlt
    etwas", sondern als kaputt, und getroffen hat es ausgerechnet die drei
    Einstiegsdialoge (Regel 19: keine Sackgassen). Deshalb trägt die Klasse
    beide Fälle und ihr Knopf seine Beschriftung als Parameter — der Name
    stammt aus dem Bildfall, die Sache tut es nicht mehr.
    """

    changed = Signal()

    def __init__(
        self,
        images: Mapping[str, str],
        pick: Callable[[], tuple[str, str] | None] | None,
        start: str = "",
        parent: QWidget | None = None,
        button_text: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.combo = QComboBox(self)
        for identifier, name in images.items():
            self.combo.addItem(name, identifier)
        if start:
            index = self.combo.findData(str(start))
            if index < 0:
                # Ein Wert, den die Liste nicht kennt, wird gezeigt statt
                # ersetzt — wie beim Quellenwähler darunter.
                self.combo.addItem(str(start), str(start))
                index = self.combo.count() - 1
            self.combo.setCurrentIndex(index)
        self.button = QPushButton(button_text or tr("Bild wählen …"), self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.button)
        self.combo.currentIndexChanged.connect(self.changed)
        self._pick = pick
        if pick is None:
            # Ohne Rückruf — etwa im Wiederöffnen aus dem Verlauf eines
            # fremden Aufrufers — bleibt die Liste, was sie ist.
            self.button.setVisible(False)
        else:
            self.button.clicked.connect(self._choose)

    def _choose(self) -> None:
        if self._pick is None:
            return
        chosen = self._pick()
        if chosen is None:
            return
        identifier, name = chosen
        index = self.combo.findData(identifier)
        if index < 0:
            self.combo.addItem(name, identifier)
            index = self.combo.count() - 1
        self.combo.setCurrentIndex(index)

    def value(self) -> str:
        data = self.combo.currentData()
        return str(data) if data is not None else self.combo.currentText()


def sketch_extent(text: str, values: Mapping[str, float]) -> tuple[float, float] | None:
    """Breite und Höhe einer gezeichneten Skizze, in Millimetern.

    ``None``, wenn sich der Text nicht lösen lässt — ein Dialog ist kein Ort,
    an dem eine halbfertige Zeichnung einen Fehler wirft. Hilfsgeometrie zählt
    nicht mit: Eine Mittellinie, an der etwas symmetrisch hängt, gehört nicht
    zum Umriss und würde ihn größer erscheinen lassen, als er ist.
    """
    if not text.strip():
        return None
    try:
        from app.core.errors import AppError
        from app.core.sketch.profile import bounds_of, regions_of
        from app.core.sketch.serialize import sketch_from_text
        from app.core.sketch.solver import solve_sketch

        # Über die **Regionen**, nicht über die rohen Stützpunkte: Ein Kreis
        # trägt Mitte und einen Randpunkt, ein Bogen drei Punkte — aus den
        # Punkten gerechnet maß ein Kreis Ø 50 hier „25", und die Zahl stand
        # schreibgeschützt im Feld. ``regions_of``/``bounds_of`` ist dieselbe
        # Kette, die ``_regions_for`` für den echten Körper fährt; freie
        # Hilfspunkte, die kein Profil bilden, zählen damit von selbst nicht.
        regions = regions_of(solve_sketch(sketch_from_text(text), dict(values)))
    except AppError:
        # Eng gefangen wie in ``SketchField._describe`` nebenan: Ein Dialog
        # ist kein Ort, an dem eine halbfertige Zeichnung einen Fehler wirft —
        # aber ein Programmierfehler darf nicht still zu „Felder bleiben,
        # wie sie sind" werden.
        return None
    if not regions:
        return None
    corners = [bounds_of(region) for region in regions]
    xs = [x for low, high in corners for x in (low[0], high[0])]
    ys = [y for low, high in corners for y in (low[1], high[1])]
    return (max(xs) - min(xs), max(ys) - min(ys))


def _explain(editor: QWidget, caption: QWidget | None, sentence: str) -> None:
    """Ein Satz an das Feld, an seine Beschriftung und an den Bildschirmleser.

    Drei Wege für eine Auskunft: Der Tooltip erscheint, wo die Maus steht, der
    ``statusTip`` in der Statuszeile ohne Wartezeit, und
    ``accessibleDescription`` liest ein Vorleser vor (Regel 18 — nicht nur eine
    Kodierung).

    ``caption`` darf ``None`` sein, weil ``QFormLayout.labelForField`` das
    zurückgibt, sobald eine Zeile über beide Spalten geht (``addRow`` mit einem
    Argument). Nachgemessen ist der Fall hier keiner: Alle 457 Zeilen des
    Registers haben eine Beschriftung. Der Zweig steht für die erste Zeile, die
    keine hat, und nicht für eine, die es schon gibt.
    """
    editor.setToolTip(sentence)
    editor.setStatusTip(sentence)
    editor.setAccessibleDescription(sentence)
    if caption is not None:
        caption.setToolTip(sentence)
        caption.setStatusTip(sentence)


def _why_inactive(field: str, wanted: str | bool) -> str:
    """Warum dieses Feld gerade nichts tut — als Satz, nicht als Wert.

    Ein Haken hat keinen Auswahlwert, den man nennen könnte: „Wirkt nur, wenn
    „Gründlich suchen" auf „True" steht" wäre die Bauart der Anwendung und
    nicht ihre Bedienung. Beide Richtungen stehen hier, weil ein Feld genauso
    gut am *ausgeschalteten* Haken hängen kann — eine Verzweigung über einen
    Wahrheitswert mit nur einem Ausgang ist eine Falle für den Nächsten.
    """
    if isinstance(wanted, bool):
        if wanted:
            return str(tr("Wirkt nur, wenn „{field}“ angehakt ist.")).format(field=field)
        return str(tr("Wirkt nur, wenn „{field}“ nicht angehakt ist.")).format(field=field)
    return str(tr("Wirkt nur, wenn „{field}“ auf „{value}“ steht.")).format(
        field=field, value=choice_label(wanted)
    )


#: Die drei Achsen einer Knochenstellung, in der Reihenfolge, in der
#: :func:`app.core.geom.pose.pose_to_text` sie schreibt. Beschriftungen, keine
#: Schlüssel — deshalb stehen sie hier und nicht im Kern.
POSE_AXES: Sequence[str] = ("X", "Y", "Z")

#: Grenzen eines Stellungswinkels. Eine volle Umdrehung in beide Richtungen:
#: darüber hinaus beschreibt eine Zahl dieselbe Stellung noch einmal.
POSE_LIMIT = 360.0


class ArmatureField(QWidget):
    """Die Stellung eines Skeletts: je Knochen eine Zeile mit drei Winkeln.

    Der ``pose``-Parameter ist ein JSON-Text — ein Speicherformat, wie der
    Skizzentext daneben (§30.1, Sammelparameter). Getippt wurde er trotzdem:
    ``kind="armature"`` fiel im Dialog auf ein ``QLineEdit`` durch, und wer
    einen Arm beugen wollte, schrieb ``{"bone_1":[0,30,0]}`` von Hand. Die
    Knochennamen dazu standen im Nachbarfeld, ebenfalls als JSON.

    Die Namen kennt der Dialog aber: Sie kommen aus dem Skelett, das der
    Editor gerade gesetzt hat (oder aus dem Wert der Operation, wenn sie aus
    dem Verlauf wieder geöffnet wird). Daraus wird ein Raster mit einer Zeile
    je Knochen — der Text entsteht erst beim Übernehmen.

    Die Felder sind :class:`ValueField` und keine nackten Drehknöpfe: ein Maß
    darf an einem Projektparameter hängen (§13), und das gilt für einen Winkel
    wie für eine Länge. **Der Kern löst einen Ausdruck *innerhalb* dieses
    Textes heute noch nicht auf** — er steht hier, damit er nicht verloren
    geht, nicht weil er schon rechnet.
    """

    changed = Signal()

    def __init__(
        self,
        bones: Sequence[str],
        start: str = "",
        parameter_values: Mapping[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._bones = [str(name) for name in bones]
        self._fields: dict[str, list[ValueField]] = {}

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(TIGHT)
        for column, axis in enumerate(POSE_AXES):
            # Die Achse steht einmal über der Spalte statt dreimal je Zeile.
            # Den Namen trägt jedes Feld trotzdem: eine Spaltenüberschrift
            # liest kein Screenreader mit, der auf einem Eingabefeld steht.
            head = QLabel(f"{axis} [°]", self)
            set_level(head, "caption")
            grid.addWidget(head, 0, column + 1)

        entered = _angles_from(start)
        for row, bone in enumerate(self._bones, start=1):
            grid.addWidget(QLabel(bone, self), row, 0)
            angles: tuple[float | str, ...] = entered.get(bone, (0.0, 0.0, 0.0))
            fields: list[ValueField] = []
            for column, axis in enumerate(POSE_AXES):
                spec = ParamSpec(
                    name=f"{bone}.{axis.lower()}",
                    kind="float",
                    title=axis,
                    default=0.0,
                    unit=DEGREE_UNIT,
                    minimum=-POSE_LIMIT,
                    maximum=POSE_LIMIT,
                )
                field = ValueField(spec, angles[column], parameter_values, self)
                field.setAccessibleName(f"{bone} {axis}")
                field.changed.connect(self.changed)
                grid.addWidget(field, row, column + 1)
                fields.append(field)
            self._fields[bone] = fields

    def value(self) -> str:
        """Die Stellung als Text, wie ihn der Kern liest.

        Geschrieben wird über :func:`app.core.geom.pose.pose_text` — es gibt
        genau einen Schreiber für dieses Format, und der steht im Kern.
        Trägt ein Feld einen Ausdruck statt einer Zahl, bleibt er wörtlich
        stehen; die Bindung hier aufzulösen hieße, sie beim ersten Öffnen des
        Dialogs zu verlieren, ohne dass es jemand sähe.

        Der Vorsatz stand hier schon, und gehalten hat ihn diese Methode
        trotzdem nicht: Sobald ein Feld einen Ausdruck trug, fiel sie auf ein
        eigenes ``json.dumps`` zurück — ein zweiter Schreiber für dasselbe
        Format, weil der im Kern nur ``Pose`` nahm und ``Pose.angles`` drei
        Zahlen sind. ``pose_text`` nimmt beides, und damit gibt es wieder
        einen.
        """
        from app.core.geom.pose import pose_text

        return pose_text(
            {bone: [field.value() for field in row] for bone, row in self._fields.items()}
        )


def _angles_from(text: str) -> dict[str, tuple[float | str, ...]]:
    """Die eingetragene Stellung je Knochen — leer, wenn der Text nichts hergibt.

    **Roh gelesen**, also Zahl oder Ausdruck, wie es dasteht. Vorher lief das
    über ``pose_from_text``, und die gibt drei *Zahlen*: Ein Ausdruck liess sie
    scheitern, der Fang machte daraus ein leeres Raster, und alle drei Winkel
    des Knochens standen auf null. Der Dialog verlor beim Öffnen genau die
    Bindung, die sein eigener Docstring beim Schreiben zu erhalten versprach.

    Ein unlesbarer Text bleibt kein Fehler, sondern ein leeres Raster: Der
    Dialog soll aufgehen, und was nicht zu lesen war, wird beim Übernehmen
    ohnehin überschrieben — das erledigt jetzt ``pose_angles`` selbst.
    """
    from app.core.geom.pose import pose_angles

    return pose_angles(text)


class ArmatureSummary(QLabel):
    """Was das Skelett ist, in einem Satz — und der Text reist unverändert mit.

    Das Skelett wird gesetzt, nicht getippt (so steht es in seinem eigenen
    ``doc``-Satz). Ein Feld, in dem die Punktliste als JSON steht, lädt
    trotzdem zum Tippen ein und ist die kürzeste Strecke zu einem Skelett, das
    niemand mehr lesen kann. Gezeigt wird deshalb die Zahl, weitergegeben der
    ursprüngliche Text.
    """

    def __init__(self, text: str, bones: Sequence[str], parent: QWidget | None = None) -> None:
        count = len(bones)
        super().__init__(
            str(tr("Ein Knochen"))
            if count == 1
            else str(tr("{count} Knochen")).format(count=count),
            parent,
        )
        self._text = text
        self.setAccessibleName(str(tr("Skelett")))

    def value(self) -> str:
        return self._text


def armature_bones(text: str) -> list[str]:
    """Die Knochennamen eines Skeletttextes, oder nichts.

    Ohne Knochen gibt es keine Zeilen, und der Dialog bleibt beim
    Textfeld — ein leeres Raster wäre eine Zusage ohne Inhalt.
    """
    from app.core.geom.pose import armature_from_text

    try:
        return [bone.name for bone in armature_from_text(text)]
    except AppError:
        return []


def _kept_narrow(editor: QWidget) -> QWidget:
    """Ein Zahlenfeld bleibt so breit, wie eine Zahl ist.

    ``QFormLayout`` wächst nach Vorgabe mit (``AllNonFixedFieldsGrow``), und die
    Breite des Dialogs kommt vom umgebrochenen Beschreibungssatz — 490 bis 624
    Pixel. Gemessen am gezeigten Dialog: ``decimate_mesh.triangles`` bekam 366
    Pixel für einen Wunsch von 120, ``slots_from_texture.filaments`` 366 für 48.
    Die Zahl klebte links, die Drehknöpfe saßen dreihundert Pixel weiter rechts,
    dazwischen leere Fläche — in jedem Operationsdialog.

    Gedeckelt wird **nur die Zahl**. Aufklappmenüs, Textfelder und die
    Objektauswahl wachsen weiter: Dort ist die Breite der Inhalt („Bohrung 1 ·
    Ø5,2 mm"), und ein Deckel darauf würde abschneiden. Deshalb kein
    ``FieldsStayAtSizeHint`` für das ganze Formular.

    Gefragt wird die Wunschbreite und nicht die aktuelle: Vor dem ersten Legen
    hat ein Widget seine Vorgabegröße, und ein Deckel daraus wäre eine andere
    Zahl bei jedem Öffnen.
    """
    editor.setMaximumWidth(editor.sizeHint().width() + NUMBER_AIR)
    return editor


class OperationDialog(QDialog):
    """Ein Dialog für eine Operation, gebaut aus ihrem Schema."""

    valuesChanged = Signal()
    """Ein Wert hat sich geändert — die Live-Vorschau (§18.7) hört zu."""

    def __init__(
        self,
        spec: OperationSpec,
        objects: Mapping[str, str] | Sequence[str],
        parent: QWidget | None = None,
        values: Mapping[str, Any] | None = None,
        sources: Mapping[str, str] | None = None,
        parameter_values: Mapping[str, float] | None = None,
        features: Mapping[str, str] | None = None,
        extra: QWidget | None = None,
        extra_label: str = "",
        surroundings: Any = None,
        images: Mapping[str, str] | None = None,
        pick_image: Callable[[], tuple[str, str] | None] | None = None,
        pick_source: Callable[[], tuple[str, str] | None] | None = None,
        note: str = "",
        slots: Sequence[Any] = (),
    ) -> None:
        """``extra`` hängt ein Widget des Aufrufers unter „Weitere
        Einstellungen" — die zusammengelegten Menü-Zwillinge tragen dort
        ihren „Exakt"-Umschalter, ohne dass der Dialog seine Generik aus
        dem Schema verliert.

        ``extra_label`` beschriftet es. Leer für einen Haken: Der trägt
        seinen Text selbst, und eine Beschriftung daneben stünde zweimal
        dasselbe. Eine **Auswahlliste** braucht sie dagegen — sie zeigt nur
        ihren aktuellen Wert, und „Extrudieren" allein in einer Zeile sagt
        nicht, dass man dort die Art wählt. So tragen es die
        Variantengruppen (``VARIANT_GROUPS``), deren ``choice`` genau dieser
        Text ist.

        ``surroundings`` reicht die Szene an ein Skizzenfeld weiter
        (:class:`app.ui.sketch_editor.Surroundings`) — Bauraum, Zeichenebenen
        und Projektionsvorlagen. Ohne sie war der Editor auf diesem Weg ärmer
        als derselbe Editor im Skizzenmodus. Als ``Any`` gehalten, damit der
        Dialog nichts aus dem Skizzenmodul importieren muss, das er nur
        durchreicht."""
        super().__init__(parent)
        self.spec = spec
        self.setWindowTitle(str(spec.title))
        self.setMinimumWidth(380)
        self._editors: dict[str, QWidget] = {}
        self._parameter_values = dict(parameter_values or {})
        """Aufgelöste Projektparameter — der Skizzeneditor rechnet
        Maßausdrücke damit (§13, §30.1)."""
        self._surroundings = surroundings
        """Bauraum, Zeichenebenen und Projektionsvorlagen für ein
        Skizzenfeld — durchgereicht, nicht benutzt."""
        self._slots = list(slots or ())
        """Die Materialslots des gewählten Körpers — der Filamentwähler
        beantwortet damit „welche Farbe hat Slot 1?", ohne dass jemand erst
        malen muss."""
        given = dict(values or {})
        # Der Dialog spricht in Namen, das Dokument in Kennungen. Wer nur eine
        # Liste übergibt, bekommt die Kennungen zu sehen.
        names = dict(objects) if isinstance(objects, Mapping) else {key: key for key in objects}
        # Quellen sind keine Objekte. Sie standen hier trotzdem in derselben
        # Liste — wer „Modell laden" im Verlauf wieder öffnete, bekam eine
        # Auswahl aus Körpern angeboten, wo eine Datei gemeint war.
        self._sources = dict(sources or {})
        self._features = dict(features or {})
        """Die erkannten Merkmale des gewählten Körpers, Kennung auf
        Beschriftung — dieselbe, die im Objektbaum und über dem Modell steht."""
        self._images = dict(images or {})
        """Nur die Bildquellen des Projekts — das Feld „Bild" listet keine
        Netze (§25, ``displace_image``)."""
        self._pick_image = pick_image
        """Holt ein Bild von der Platte ins Projekt und gibt (Kennung, Name)
        zurück — der Weg, den ein leeres Projekt braucht."""
        self._pick_source = pick_source
        """Dasselbe für eine Modelldatei. Ohne ihn ist das Quellenfeld in
        *Modell laden*, *STEP laden* und *Zeichnung extrudieren* eine leere
        Liste, aus der kein Weg führt."""
        self._bones = armature_bones(str(given.get("armature") or ""))
        """Die Knochen, an denen die Stellung hängt — aus dem Skelett, das der
        Editor gerade gesetzt hat, oder aus dem Wert einer wieder geöffneten
        Operation. Ohne sie hat ein Stellungsraster keine Zeilen."""

        front = QFormLayout()
        advanced = QFormLayout()
        self._rows: dict[str, QFormLayout] = {}
        """In welchem der beiden Formulare ein Feld steht — ``switch_variant``
        blendet Zeilen darüber aus."""
        for entry in spec.params.spec():
            editor = self._editor_for(entry, names, given.get(entry.name))
            self._editors[entry.name] = editor
            self._watch(editor)
            label = f"{entry.title}"
            if entry.unit:
                # Die Einheit, in der das Feld wirklich spricht: Bei „mm" ist
                # das die eingestellte Anzeigeeinheit, sonst der Wert aus dem
                # Schema. Ein Feld, das Zoll nimmt und „[mm]" darüber trägt,
                # wäre die Umschaltung mit einer Lüge darin.
                label = f"{label} [{shown_unit(entry) or entry.unit}]"
            # Ein eingetragener Wert gehört vor den Nutzer, auch wenn das Schema
            # ihn nach hinten legt: er ist der, der gerade entschieden wurde —
            # die angeklickte Fläche, die vorgewählte Position (§18.5).
            #
            # **Aber nur, wenn er wirklich entschieden wurde.** Wer eine
            # Operation aus dem Verlauf öffnet, bekommt ihr *ganzes* Schema
            # übergeben; mit ``entry.name in given`` allein landete damit jedes
            # Feld vorn, und die Klappe „Weitere Einstellungen" verschwand
            # genau dann, wenn jemand einen Wert nachbessern will (§2.4). Ein
            # Wert, der auf seiner Vorgabe steht, ist keine Entscheidung.
            #
            # Ein Sammelwert bleibt dabei nicht draußen: Wer eine Skizze oder
            # ein Skelett übergibt, tut das, weil der Dialog ihretwegen aufgeht
            # — und das Stellungsraster gehört neben das Skelett, aus dem es
            # entsteht (``test_the_pose_grid_stands_in_front``). Ein erster
            # Versuch schob rohe Sammelwerte pauschal nach hinten und trennte
            # damit genau diese zwei.
            decided = entry.name in given and given[entry.name] != entry.default
            target = (
                front
                if entry.placement == "front" or isinstance(editor, ArmatureField) or decided
                else advanced
            )
            target.addRow(label, editor)
            self._rows[entry.name] = target
            if entry.doc:
                # **Der Satz gehört an beide Hälften der Zeile.** Er stand nur
                # am Eingabefeld — und wer eine Zeile nicht versteht, zeigt auf
                # das unverständliche Wort, nicht auf den Kasten daneben. Bei
                # 457 Parametern in 86 Operationen war das die Erklärung, die
                # es gab und die niemand fand. ``labelForField`` holt das Label,
                # das ``addRow`` aus der Zeichenkette gebaut hat.
                _explain(editor, target.labelForField(editor), str(entry.doc))

        layout = QVBoxLayout(self)
        self._caveat: QLabel | None = None
        self._description: QLabel | None = None
        if spec.doc:
            description = QLabel(str(spec.doc), self)
            description.setWordWrap(True)
            # So hoch wie sein Text, nicht so hoch wie der übrige Platz.
            #
            # Ohne das teilt das senkrechte Layout die freie Höhe unter seinen
            # Einträgen auf, und der erste ist dieser Satz: Im Bohrungsdialog
            # bekam er 189 Pixel für zwei Zeilen und stand vertikal zentriert
            # darin. Was im Bild wie ein Gestaltungsfehler aussah — ein
            # Beschreibungstext, der ohne Grund in der Mitte schwebt —, war
            # eine fehlende Größenrichtlinie.
            description.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            description.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            layout.addWidget(description)
            self._description = description

        # **Die Grenze stand nur im Handbuch.** Zwölf Operationen tragen einen
        # ``caveat``, und gelesen hat ihn allein die Handbuchreferenz — nicht
        # der Dialog, in dem gerade jemand die Operation anwendet. Als eigenes
        # Label und nicht an den ``doc``-Satz gehängt: Die Deklaration des
        # Feldes begründet das selbst — in einen Satz gepackt liest sich die
        # Einschränkung wie ein Nachtrag und wird überlesen.
        #
        # Das Wort „Wann nicht" davor ist die zweite Kodierung (Regel 18): Der
        # Satz steht halbfett, aber die Aussage hängt nicht daran.
        # Immer gebaut, sichtbar nur mit Inhalt: Ein Variantenwechsel *zu*
        # einer Grenze hin hätte sonst nichts, woran er sie schreiben könnte.
        warning = caveat_line(spec)
        caveat = QLabel(warning, self)
        caveat.setWordWrap(True)
        set_level(caveat, "caption")
        font = caveat.font()
        font.setBold(True)
        caveat.setFont(font)
        caveat.setVisible(bool(warning))
        self._caveat = caveat
        layout.addWidget(caveat)

        # **Woran gearbeitet wird, wenn mehr gewählt ist als gebraucht.** Eine
        # Operation nimmt so viele Körper, wie sie deklariert, und zwar in
        # Klickreihenfolge (``inputs_for``). Bei zwei gewählten Würfeln und
        # *Bohrung setzen* bekam einer ein Loch und der andere nicht — im
        # Dialog stand kein Wort dazu, und der Fenstertitel ist beim Klicken
        # nicht im Blick. Das ist kein Raten (Regel 21), die Regel steht nur
        # nirgends, wo jemand sie liest.
        #
        # Eigenes Label wie die Grenze darüber, sichtbar nur mit Inhalt: Der
        # Normalfall ist ein gewählter Körper, und dann gibt es nichts zu
        # sagen.
        applies = QLabel(note, self)
        applies.setWordWrap(True)
        set_level(applies, "caption")
        applies.setVisible(bool(note))
        self._note = applies
        layout.addWidget(applies)
        layout.addLayout(front)
        # Der freie Platz sammelt sich hier, zwischen Feldern und Knöpfen, und
        # nicht mehr verteilt über alles.
        layout.addStretch(1)

        if extra is not None:
            # **Vorn, nicht hinten.** Der Haken stand unter „Weitere
            # Einstellungen", und dort findet ihn niemand, der nicht schon
            # weiß, dass es ihn gibt. Er ist aber keine Feineinstellung: an
            # ihm hängt, ob sieben Werkzeuge später überhaupt anklickbar sind
            # — Fase, Verrundung, Formschräge, Fläche versetzen, exakt
            # Aushöhlen, Tasche schneiden und die Umwandlung ins Netz. Wer den
            # Quader ohne ihn anlegt, findet sie später alle grau, und der
            # einzige Weg zurück ist, von vorn anzufangen.
            #
            # §2.4 stellt vorn hin, „was man ändert", und hinten „Toleranzen,
            # Auflösungen, Rückfallverhalten". Eine Entscheidung darüber, was
            # man mit dem Ergebnis noch tun kann, ist keins von beidem — sie
            # gehört dorthin, wo sie getroffen wird.
            front.addRow(extra_label, extra)
        if advanced.rowCount():
            # Eine ankreuzbare Gruppe graut ihre Felder aus, statt sie
            # wegzuklappen — die gestufte Tiefe aus §2.4 war damit gedacht und
            # nicht gebaut: die hinteren Werte standen weiter da, nur grau, und
            # das Häkchen las sich wie ein Schalter, der etwas bewirkt.
            inner = QWidget(self)
            inner.setLayout(advanced)
            inner.setVisible(False)
            self.advanced = QToolButton(self)
            self.advanced.setText(tr("Weitere Einstellungen"))
            self.advanced.setCheckable(True)
            self.advanced.setAutoRaise(True)
            self.advanced.setArrowType(Qt.ArrowType.RightArrow)
            self.advanced.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

            # **Keine geschachtelte Funktion, die ``self`` fängt.** Sie ist
            # dasselbe wie ein Lambda: ihre Zelle hält den Dialog, der Sender
            # ist sein eigener Knopf, und der Ring über die C++-Grenze steht.
            # Gemessen am 23.08.2026: zehn losgelassene ``OperationDialog``
            # überlebten alle zehn, und ``gc.get_referrers`` nannte genau diese
            # Zelle.
            self.advanced.toggled.connect(
                weak_slot(self, OperationDialog._unfold_advanced, inner, forward=True)
            )
            layout.addWidget(self.advanced)
            layout.addWidget(inner)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        # Der Knopf benennt die Handlung: „Bohrung setzen" statt „OK". Was
        # gleich passiert, steht damit dort, wo entschieden wird — der
        # Fenstertitel ist beim Klicken nicht mehr im Blick. Für die
        # Bausteine gilt das nicht wörtlich: Ihre Titel sind Substantive,
        # und ein Knopf namens „Lochwand-Einhänger" sagt nicht, was der
        # Klick tut. Dort heißt die Handlung „Einsetzen" — den Baustein
        # nennt der Fenstertitel (Robert, 25.08.2026, über 3d-druck-ce).
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(str(tr("Einsetzen")) if spec.category == "parts" else str(spec.title))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._couple_dependent_fields()

    def _couple_dependent_fields(self) -> None:
        """Ein Feld ohne Wirkung steht nicht bedienbar da (§2.6).

        „Relief auflegen" ist der Fall: *Fläche* wirkt nur, solange *Auflegen*
        auf „Auf eine Fläche" steht — bei „Von oben" bleibt ein ausgefülltes
        Feld stehen und verspricht etwas, das die Operation wortlos übergeht.
        Dasselbe Versprechen, das ``switch_variant`` bei den Zwillingen
        einlöst, nur eine Nummer kleiner: dort verschwindet die Zeile, weil die
        andere Variante sie gar nicht kennt; hier gehört sie zur Operation und
        ist nur gerade wirkungslos. Sie wird deshalb grau und sagt, woran es
        liegt, statt zu verschwinden — wer sie verschwinden sähe, suchte sie.
        """
        # **Aus dem Schema, nicht aus einer Tabelle daneben.** Die Angabe stand
        # als ``DEPENDENT_FIELDS`` hier im Modul und war mit einem Eintrag
        # angelegt, während elf Parameter sie brauchten. Ihr eigener Kopf nannte
        # die Schwelle: über eine Handvoll hinaus gehört die Abhängigkeit an den
        # Parameter — dort steht sie jetzt (``ParamSpec.depends_on``), und
        # Handbuch und Agent lesen dieselbe Quelle.
        schema = self.spec.params.spec()
        rules = [
            entry
            for entry in schema
            if entry.depends_on is not None
            and entry.name in self._editors
            and entry.depends_on[0] in self._editors
        ]
        if not rules:
            return
        titles = {entry.name: str(entry.title) for entry in self.spec.params.spec()}
        docs = {entry.name: str(entry.doc or "") for entry in self.spec.params.spec()}

        def follow() -> None:
            entered = self.values()
            for entry in rules:
                editor = self._editors[entry.name]
                inactive = inactive_dependency(entry, schema, entered)
                active = inactive is None
                editor.setEnabled(active)
                label = self._rows[entry.name].labelForField(editor)
                if label is not None:
                    label.setEnabled(active)
                # Beide Hälften sagen dasselbe — bei einer ausgegrauten Zeile
                # ist der Grund die Auskunft, die zählt, und ausgerechnet dort
                # zeigt man eher auf die Beschriftung als in das gesperrte Feld.
                _explain(
                    editor,
                    label,
                    docs[entry.name]
                    if active
                    else _why_inactive(titles[inactive[0]], inactive[1][0]),
                )

        self.valuesChanged.connect(follow)
        follow()
        self._couple_sketch_measures()

    def _couple_sketch_measures(self) -> None:
        """Wo eine Zeichnung liegt, tragen die Maßfelder ihre Maße — und nur lesend.

        Der Kern nimmt bei gesetzter Skizze **weder** Grundform **noch** Länge,
        Breite oder Ecken (``_regions_for``: ``if not sketch_text``). Die Felder
        standen trotzdem da, mit den Vorgaben der Operation: 40 mal 20 neben
        einer Zeichnung von 50 mal 30. Wer den Schritt später aufmacht, um
        nachzusehen, wie groß sein Teil ist, liest dort die falsche Zahl.

        Also beides: Die Zahlen kommen aus der Zeichnung, und die Zeile sagt,
        woher — grau und begründet, wie jedes Feld ohne Wirkung (§2.5). Ändern
        lässt sich das Maß über *Zeichnen …*, wo es hingehört.
        """
        declared = {entry.name: entry for entry in self.spec.params.spec()}
        sketch_field = next((name for name, e in declared.items() if e.kind == "sketch"), "")
        if not sketch_field or sketch_field not in self._editors:
            return

        reason = tr("Die Maße kommen aus der Zeichnung — über „Zeichnen …“ zu ändern.")
        axis_of = {"length": 0, "width": 1}
        docs = {name: str(entry.doc or "") for name, entry in declared.items()}
        seen_text: dict[str, str] = {}
        seen_extent: dict[str, tuple[float, float] | None] = {}

        def follow_sketch() -> None:
            text = str(self.values().get(sketch_field, "") or "")
            # ``valuesChanged`` feuert an **jedem** Feld, und ``sketch_extent``
            # löst die ganze Zeichnung — mit einer SVD über die volle
            # Bedingungsmatrix, im Qt-Hauptthread (§2.8). Wer im Feld daneben
            # eine Höhe tippte, rechnete je Taste einmal den Löser. Gemerkt
            # wird nur die **Rechnung**, nicht der ganze Durchlauf: Die
            # Sperren darunter müssen weiterlaufen, sonst bliebe ein Feld
            # frei, das der Nachbarzweig gerade freigegeben hat.
            if seen_text.get("value") == text:
                extent = seen_extent.get("value")
            else:
                extent = sketch_extent(text, self._parameter_values)
                seen_text["value"] = text
                seen_extent["value"] = extent
            for name in ("shape", "length", "width", "corners", *axis_of):
                editor = self._editors.get(name)
                if editor is None or name not in declared:
                    continue
                label = self._rows[name].labelForField(editor)
                if extent is None:
                    # Zweigleisig wie ``_couple_dependent_fields.follow``: Wer
                    # die Zeichnung löscht, bekommt seine Felder zurück. Die
                    # Sperre war einseitig, und ein Dialog mit gelöschter
                    # Skizze blieb zugemauert — samt einer Begründung („Die
                    # Maße kommen aus der Zeichnung"), die nicht mehr stimmte,
                    # während der Kern die Felder längst wieder nahm.
                    #
                    # Zurückgenommen wird nur die **eigene** Sperre, erkannt
                    # an ihrer Begründung: Ein Feld, das ``depends_on`` über
                    # denselben Signalweg ausgegraut hat, muss grau bleiben —
                    # blind freigegeben überschrieb dieser Zweig die Sperre
                    # des Nachbarn, je nachdem, wer zuletzt lief.
                    if editor.toolTip() == reason:
                        editor.setEnabled(True)
                        if label is not None:
                            label.setEnabled(True)
                        _explain(editor, label, docs[name])
                    continue
                if name in axis_of and isinstance(editor, ValueField):
                    # Ohne ``blockSignals`` löst das Setzen ``valuesChanged``
                    # aus, und diese Funktion riefe sich selbst.
                    blocked = editor.blockSignals(True)
                    editor.set_value(extent[axis_of[name]])
                    editor.blockSignals(blocked)
                editor.setEnabled(False)
                if label is not None:
                    label.setEnabled(False)
                _explain(editor, label, reason)

        self.valuesChanged.connect(follow_sketch)
        follow_sketch()

    def _watch(self, editor: QWidget) -> None:
        """Verbindet das Änderungssignal des Editors mit ``valuesChanged``.

        Je Editorsorte eines — die Vorschau will von jedem Feld wissen, nicht
        nur von den Zahlen.
        """
        from app.ui.sketch_editor import SketchField

        if isinstance(editor, ValueField | SketchField | ImageSourceField | ArmatureField):
            editor.changed.connect(self.valuesChanged)
        elif isinstance(editor, QCheckBox):
            editor.toggled.connect(self.valuesChanged)
        elif isinstance(editor, QSpinBox | QDoubleSpinBox):
            editor.valueChanged.connect(self.valuesChanged)
        elif isinstance(editor, QComboBox):
            editor.currentIndexChanged.connect(self.valuesChanged)
        elif isinstance(editor, QLineEdit):
            editor.textChanged.connect(self.valuesChanged)

    def _editor_for(
        self, entry: ParamSpec, objects: Mapping[str, str], given: Any = None
    ) -> QWidget:
        """Ein Editor. ``given`` schlägt die Vorgabe des Schemas, wo es gesetzt
        ist.
        """
        start = entry.default if given is None else given
        if entry.kind == "bool":
            editor = QCheckBox(self)
            editor.setChecked(bool(start))
            return editor
        if entry.kind == "material":
            return MaterialField(str(start or ""), self)
        if entry.kind == "filament":
            # Die Slotnummer bleibt der Wert (``currentData``), gewählt wird
            # aber ein Filament mit Farbe und Namen. Name und Farbe wandern
            # in ihre eigenen Felder, sichtbar und weiter änderbar — der
            # Wähler füllt sie aus, er ersetzt sie nicht.
            from app.ui.filament_picker import FilamentField

            picker = FilamentField(int(start or 0), self._slots, self)
            picker.filamentChosen.connect(self._fill_filament_fields)
            return picker
        if entry.kind == "int":
            spin = QSpinBox(self)
            spin.setMinimum(int(entry.minimum) if entry.minimum is not None else -1_000_000)
            spin.setMaximum(int(entry.maximum) if entry.maximum is not None else 1_000_000)
            if start is not None:
                spin.setValue(int(start))
            return _kept_narrow(spin)
        if entry.kind == "float":
            # Kein nacktes ``QDoubleSpinBox`` mehr: ein Maß darf an einem
            # Projektparameter hängen (§13), und ``float("=@breite")`` war der
            # Grund, warum sich eine gebundene Operation nicht öffnen ließ.
            return ValueField(entry, start, self._parameter_values, self)
        if entry.kind == "enum" or entry.choices:
            # Der Wert bleibt der Schlüssel, gezeigt wird der Name: „cable-5"
            # stand als Beschriftung im Dialog, und das erkennt niemand ohne die
            # Normteiltabelle daneben. Was schon ein Name ist — „M4", „PLA" —
            # bleibt unverändert.
            combo = QComboBox(self)
            for choice in entry.choices:
                combo.addItem(choice_label(str(choice)), choice)
            # **Der Name sagt, wie der Wert heißt — nicht, was er tut.**
            # „Würfelgitter" benennt ``cubic`` und erklärt es nicht, und wo
            # der Slicer-Begriff absichtlich stehen bleibt („arachne",
            # „gyroid"), steht ein Wort da, das der Kunde nachschlagen müsste.
            # Der Satz je Wert liegt in ``labels`` neben der Namenstabelle
            # (3d-druck-43) und wird hier nur angehängt — er gilt in jedem
            # Dialog gleich, und zwei Tabellen liefen auseinander.
            explain_choices(combo)
            _show_patterns(combo, entry.choices)
            if start is not None and start in entry.choices:
                combo.setCurrentIndex(combo.findData(start))
            return combo
        if entry.kind == "sketch":
            # §30.1 Stufe zwei: der Text ist ein Speicherformat, keine
            # Eingabe — gezeichnet wird im Editor, das Feld fasst zusammen.
            from app.ui.sketch_editor import SketchField

            return SketchField(str(start or ""), self._parameter_values, self, self._surroundings)
        if entry.kind == "feature":
            # Aus demselben Grund wie unten eine Liste, nur mit dem schärferen
            # Fall: „face_2" tippt niemand, der es nicht vorher irgendwo
            # abgelesen hat — und abzulesen war es nur im Objektbaum, wo die
            # Namen bei Standardbreite abgeschnitten sind. Der doc-Satz dieses
            # Parameters versprach das Anklicken im Fenster; das Feld daneben
            # war leer und blieb es.
            combo = QComboBox(self)
            # Der leere Eintrag nur, wo leer auch gilt. Bei einer
            # Operation, die ohne Merkmal ablehnt, stand er vorne und war
            # damit **vorausgewählt**: Der Kunde las „— keines —" als „das
            # ganze Teil", klickte Übernehmen und bekam „Zum Färben gehört
            # eine Fläche." — eine Vorauswahl, die sicher scheitert
            # (Robert, 27.08.2026). Von achtundzwanzig Merkmalsfeldern
            # betrifft das drei; die übrigen kommen ohne Merkmal aus und
            # behalten den Eintrag.
            if not entry.required:
                combo.addItem(tr("— keines —"), "")
            for identifier, label in self._features.items():
                combo.addItem(label, identifier)
            if start:
                index = combo.findData(str(start))
                if index < 0:
                    combo.addItem(str(start), str(start))
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            return combo
        if entry.kind == "armature":
            # Zwei Felder derselben Art und zwei verschiedene Aufgaben: Das
            # Skelett kommt aus dem Editor und wird nur gezeigt, die Stellung
            # ist das, was hier entschieden wird. Ohne Knochen bleibt beides
            # das Textfeld von vorher — ein Raster ohne Zeilen wäre eine
            # Zusage ohne Inhalt.
            if not self._bones:
                line = QLineEdit(self)
                if start:
                    line.setText(str(start))
                return line
            if entry.name == "pose":
                return ArmatureField(self._bones, str(start or ""), self._parameter_values, self)
            return ArmatureSummary(str(start or ""), self._bones, self)
        if entry.kind == "image":
            return ImageSourceField(self._images, self._pick_image, str(start or ""), self)
        if entry.kind == "source" and self._pick_source is not None:
            # **Das Quellenfeld bekommt denselben Wähler wie das Bildfeld.**
            # Ohne ihn ist ein frisches Projekt eine Sackgasse: Die Liste kennt
            # nur, was schon eingebettet ist, und in *Modell laden* ist das
            # nichts. Wer die Operation aus dem Menü ruft statt über Drag & Drop
            # zu kommen, klickte ins Leere.
            return ImageSourceField(
                self._sources,
                self._pick_source,
                str(start or ""),
                self,
                button_text=tr("Datei wählen …"),
            )
        if entry.kind in ("object", "source"):
            # Der Name steht da, die Kennung reist mit. Ein frei beschreibbares
            # Feld war hier ein Weg, „obj_12" falsch zu tippen — und der Baum
            # nebenan zeigt ohnehin Namen, keine Nummern.
            choices = self._sources if entry.kind == "source" else objects
            combo = QComboBox(self)
            for identifier, name in choices.items():
                combo.addItem(name, identifier)
            if start:
                index = combo.findData(str(start))
                if index < 0:
                    # Ein Wert, den die Liste nicht kennt, wird gezeigt statt
                    # ersetzt: eine Datei aus einem Projekt, dessen Quellen
                    # hier gerade nicht vorliegen, darf nicht stillschweigend
                    # zu einer anderen werden.
                    combo.addItem(str(start), str(start))
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            return combo
        line = QLineEdit(self)
        if start:
            line.setText(str(start))
        return line

    def take_feature(self, feature_id: str, label: str) -> bool:
        """Trägt ein angeklicktes Merkmal ein, wenn der Dialog eines erwartet.

        Der ``doc``-Satz dieses Parameters versprach das seit je — „wird beim
        Anklicken im Fenster eingetragen" —, und einzulösen war es nicht: der
        Dialog sperrte das Fenster, es gab also kein Anklicken, solange er
        offen war. Seit er das nicht mehr tut, ist der kürzeste Weg zu einer
        Fläche wieder der, auf sie zu zeigen.

        Gibt zurück, ob etwas gesetzt wurde — der Aufrufer weiß sonst nicht, ob
        sein Klick angekommen ist.
        """
        taken = False
        for entry in self.spec.params.spec():
            if entry.kind != "feature":
                continue
            editor = self._editors.get(entry.name)
            if not isinstance(editor, QComboBox):
                continue
            index = editor.findData(feature_id)
            if index < 0:
                editor.addItem(label or feature_id, feature_id)
                index = editor.count() - 1
            editor.setCurrentIndex(index)
            taken = True
        return taken

    def focus_field(self, name: str) -> bool:
        """Den Cursor in ein bestimmtes Feld setzen — und es aufklappen, wenn es
        hinten liegt.

        Für den Weg zurück aus einem Befund: Ein Schritt, dessen Wert nicht
        ging, wird über *Eingabe korrigieren* wieder geöffnet, und der Kern
        nennt dabei das Feld. Ohne diesen Sprung sieht der Kunde einen Dialog
        mit acht Zeilen und muss selbst suchen, welche gemeint war — die
        Auskunft war da und wurde nicht benutzt.

        Ein Feld hinter „Weitere Einstellungen" wird mitgeöffnet: Fokus in
        etwas Zugeklapptem ist kein Fokus, sondern ein Cursor, den niemand
        findet (§2.4).
        """
        editor = self._editors.get(name)
        if editor is None:
            return False
        entry = next((item for item in self.spec.params.spec() if item.name == name), None)
        klappe = getattr(self, "advanced", None)
        if entry is not None and entry.placement != "front" and klappe is not None:
            klappe.setChecked(True)
        editor.setFocus(Qt.FocusReason.OtherFocusReason)
        # Ein ``ValueField`` ist ein Verbund; der Cursor gehört in sein Drehfeld,
        # und der Wert darin wird ausgewählt, damit Tippen ihn ersetzt.
        inner = editor.findChild(QDoubleSpinBox)
        if inner is not None:
            inner.setFocus(Qt.FocusReason.OtherFocusReason)
            inner.selectAll()
        return True

    def take_point(self, point: tuple[float, float, float]) -> bool:
        """Trägt einen angeklickten Punkt in die Positionsfelder ein.

        Dieselbe Sache wie oben für die Koordinaten: ein Dialog, der nach
        Position X, Y und Z fragt, öffnete auf 0,00 — und der Ursprung liegt
        bei einer geladenen Platte an einer Ecke. Wer dort bohrte, kratzte
        einen Span von der Kante, und niemand sagte etwas dazu.

        §11 bleibt gewahrt: die Zahl ist die Wahrheit, das Zeigen nur die
        bequeme Eingabe. Was der Klick einträgt, steht danach lesbar da und
        lässt sich ändern.
        """
        fields = {entry.name for entry in self.spec.params.spec()}
        if not {"x", "y", "z"} <= fields:
            return False
        for name, value in zip(("x", "y", "z"), point, strict=True):
            editor = self._editors.get(name)
            if isinstance(editor, ValueField):
                editor.set_value(float(value))
        return True

    def switch_variant(self, spec: OperationSpec) -> None:
        """Der Dialog gehört jetzt einer anderen Variante derselben Handlung.

        Die zusammengelegten Zwillinge (``MENU_TWINS``) rechnen je nach
        Umschalter im Mesh- oder im exakten Kern, und die beiden Schemata sind
        nicht dieselben. Bis hierher wurden die überzähligen Werte **beim
        Anwenden** weggefiltert — im Dialog standen sie weiter da: wer „Exakt"
        ankreuzte und den Bezugspunkt auf „Ecke" stellte, bekam einen mittigen
        Quader und keinen Ton dazu. Ein Feld ohne Wirkung ist ein Versprechen,
        das niemand hält; es verschwindet, statt zu lügen.

        Die Beschreibung wechselt mit: die des Mesh-Quaders nennt eine Wahl
        („mittig auf Z = 0 oder auf einer Ecke"), die es im exakten Kern nicht
        gibt.
        """
        allowed = {entry.name for entry in spec.params.spec()}
        for name, form in self._rows.items():
            editor = self._editors.get(name)
            if editor is not None:
                form.setRowVisible(editor, name in allowed)
        if self._description is not None and spec.doc:
            self._description.setText(str(spec.doc))
        if self._caveat is not None:
            # Ein Zwilling hat seine eigene Grenze — oder keine. Stehen bleibt
            # sonst die des anderen Rechenkerns, und das ist schlechter als
            # keine Angabe.
            warning = caveat_line(spec)
            self._caveat.setText(warning)
            self._caveat.setVisible(bool(warning))
        self.adjustSize()

    def place_beside(self, anchor: QWidget | None) -> None:
        """Setzt den Dialog an den Rand statt in die Bildmitte.

        Ein Operationsdialog trägt eine Live-Vorschau (§18.7): was er zeigt,
        entsteht während des Tippens im Viewport. Qt setzt Dialoge mittig zum
        Elternfenster — und die Mitte des Fensters ist genau die Stelle, an der
        die Kamera das Modell zeigt. Die Vorschau entstand hinter dem Dialog,
        der sie ausgelöst hat.

        Angelegt wird oben rechts im übergebenen Bereich, mit demselben Abstand
        zu Rand und Kante. Passt der Dialog dort nicht, bleibt er, wo Qt ihn
        hingesetzt hat — ein Dialog außerhalb des Bildschirms wäre schlimmer
        als einer in der Mitte.

        **Gerechnet wird mit der Breite, die er wirklich bekommt.** ``sizeHint``
        allein war zu klein: Der Dialog hat eine Mindestbreite von 380, und
        seine Wunschbreite liegt je Operation zwischen 249 und 318 Bildpunkten
        (gemessen). Um genau diese Differenz — 62 bis 131 Punkte — schob ihn
        die Rechnung über die rechte Kante hinaus, also über den Rand des
        Viewports, für den die ganze Methode da ist.

        ``width()`` gilt nur, wenn er schon steht: vor dem Anzeigen trägt ein
        Qt-Widget die Vorgabe 640 und nicht seine eigene Breite — damit läge der
        Dialog plötzlich links der Bildmitte, also wieder über dem Modell.
        """
        if anchor is None:
            return
        area = anchor.rect()
        width = (
            self.width() if self.isVisible() else max(self.sizeHint().width(), self.minimumWidth())
        )
        if width + 2 * DIALOG_MARGIN > area.width():
            return
        corner = anchor.mapToGlobal(area.topRight())
        self.move(corner.x() - width - DIALOG_MARGIN, corner.y() + DIALOG_MARGIN)

    def _unfold_advanced(self, inner: QWidget, open_now: bool) -> None:
        """„Weitere Einstellungen" auf- und zuklappen.

        Als Methode und nicht als geschachtelte Funktion: Der Abschluss fing
        ``self``, hing am eigenen Knopf und hielt den Dialog fest. Der Rahmen
        kommt gebunden mit, der Zustand vom Signal.
        """
        inner.setVisible(open_now)
        self.advanced.setArrowType(Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow)
        if not open_now:
            self.adjustSize()
            return

        # ``adjustSize`` deckelt Dialoge bei zwei Dritteln der Bildschirmhöhe.
        # Bei einem Gewinde blieben deshalb die hinteren Felder unter den
        # Aktionsknöpfen liegen. Der geöffnete Bereich bekommt seine echte
        # Inhaltshöhe, bis höchstens an den sichtbaren Bildschirmrand.
        layout = self.layout()
        if layout is None:
            return
        layout.activate()
        wanted = max(self.height(), layout.sizeHint().height())
        screen = self.screen()
        if screen is not None:
            wanted = min(wanted, screen.availableGeometry().height() - 48)
        self.resize(self.width(), wanted)

    def _fill_filament_fields(self, name: str, colour: str) -> None:
        """Name und Farbe des gewählten Filaments in ihre eigenen Felder.

        Der Wähler kennt beide, die Operation hat je ein Feld dafür
        (``name``, ``colour``) — und ohne diesen Weg hätte der Kunde die
        Spule zwar ausgewählt und müsste ihren Namen daneben trotzdem
        abtippen.

        **Gefüllt, nicht ersetzt:** Die Felder bleiben sichtbar und
        änderbar. Wer für dieses eine Teil „Deckel rot" statt „PETG Rot"
        schreiben will, kann es; die Vorwahl ist ein Vorschlag (§2.4).

        Wo es ein Feld nicht gibt, passiert nichts: ``label_text`` hat einen
        Slot, aber keinen Namen dazu, und ein Griff ins Leere wäre ein
        Absturz an einer Stelle, an der nur ein Komfort fehlt.
        """
        for key, value in (("name", name), ("colour", colour)):
            editor = self._editors.get(key)
            if isinstance(editor, QLineEdit) and value:
                editor.setText(value)

    def values(self) -> dict[str, Any]:
        """Was der Nutzer eingetragen hat, fertig für die Operationsparameter."""
        from app.ui.filament_picker import FilamentField
        from app.ui.sketch_editor import SketchField

        collected: dict[str, Any] = {}
        for entry in self.spec.params.spec():
            editor = self._editors[entry.name]
            if isinstance(editor, MaterialField):
                # Vor dem Combo-Zweig: Der macht ``str(currentData())``
                # aus allem. Bei einer Kennung ginge das zufällig gut,
                # und genau solche Zufälle brechen beim nächsten Feld.
                collected[entry.name] = editor.value()
            elif isinstance(editor, FilamentField):
                # **Vor dem Combo-Zweig, und als Zahl.** Der Wähler ist eine
                # ``QComboBox``, und der Zweig darunter macht aus jedem
                # ``currentData`` einen Text — eine Slotnummer als „3" hätte
                # das Schema (``int``) beim ersten Anwenden abgelehnt.
                chosen = editor.currentData()
                collected[entry.name] = int(chosen) if isinstance(chosen, int) else 0
            elif isinstance(editor, ValueField):
                # Zahl oder Ausdruck — und der Ausdruck bleibt wörtlich. Ihn
                # hier aufzulösen hieße, die Bindung beim ersten Öffnen des
                # Dialogs zu verlieren, ohne dass es jemand sähe.
                collected[entry.name] = editor.value()
            elif isinstance(editor, ImageSourceField | ArmatureField | ArmatureSummary):
                collected[entry.name] = editor.value()
            elif isinstance(editor, SketchField):
                collected[entry.name] = editor.text()
            elif isinstance(editor, QCheckBox):
                collected[entry.name] = editor.isChecked()
            elif isinstance(editor, QSpinBox):
                collected[entry.name] = editor.value()
            elif isinstance(editor, QDoubleSpinBox):
                collected[entry.name] = float(editor.value())
            elif isinstance(editor, QComboBox):
                # Objekt- und Quellenwähler tragen die Kennung als Daten, die
                # übrigen Aufklappmenüs sind ihr eigener Wert.
                data = editor.currentData()
                collected[entry.name] = editor.currentText() if data is None else str(data)
            elif isinstance(editor, QLineEdit):
                collected[entry.name] = editor.text()
        return collected


#: Wie groß eine Musterkachel in der Auswahl steht. Klein genug für eine
#: Zeile, groß genug, dass sich Voronoi und Rauschen unterscheiden lassen —
#: bei 16 Pixeln sehen beide aus wie Grau.
PATTERN_ICON = 44


def _show_patterns(combo: QComboBox, choices: Sequence[Any]) -> None:
    """Zeigt jedes Texturmuster als Bild neben seinem Namen (§2.6).

    Acht Muster als Wort in einem Aufklappmenü sind acht Wörter; wer sie nicht
    kennt, probiert sie durch. Erkannt wird das Feld an seinen Werten und
    nicht an seinem Namen: eine zweite Operation mit denselben Mustern bekommt
    die Bilder damit von selbst.
    """
    from PySide6.QtCore import QByteArray, QSize
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    from app.core import figures
    from app.core.drawing import Theme
    from app.core.geom.texture_ops import PATTERNS
    from app.ui.start_screen import current_theme

    wanted = [str(entry) for entry in choices]
    if not wanted or not set(wanted) <= set(PATTERNS):
        return

    theme: Theme = "light" if current_theme() == "light" else "dark"
    ratio = combo.devicePixelRatioF()
    for index, pattern in enumerate(wanted):
        pixmap = QPixmap(QSize(PATTERN_ICON, PATTERN_ICON) * ratio)
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(figures.texture_tile(pattern, theme).encode("utf-8")))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        combo.setItemIcon(index, QIcon(pixmap))
    combo.setIconSize(QSize(PATTERN_ICON, PATTERN_ICON))


#: Was vorausgewählt ist, wenn die Skizze fertig ist.
#:
#: **Nicht die erste Zeile.** Die Liste kommt alphabetisch nach Titel aus dem
#: Register, und damit stand „Entlang eines Bogens führen" ganz oben — ein
#: Rohrbogen, also der seltenste der fünf Fälle. Wer nach dem Zeichnen auf
#: „Weiter" drückt, ohne die Liste zu lesen, bekam ihn.
#:
#: Aus einer gezeichneten Fläche wird im Normalfall ein Körper, indem man sie
#: aufzieht. Steht der Eintrag einmal nicht im Register, bleibt es bei der
#: ersten Zeile — eine Vorauswahl, die ins Leere zeigt, wäre schlimmer als
#: eine unpassende.
DEFAULT_SKETCH_USE = "sketch_extrude"


class SketchUseDialog(QDialog):
    """Was soll aus der gezeichneten Skizze werden? (§2.2, Weg 2)

    Der Zeichnen-Knopf der Werkzeugzeile startet den Skizzenmodus ohne
    festgelegte Operation — die Entscheidung fällt hier, mit der fertigen
    Zeichnung vor Augen, statt vorab aus fünf Menüeinträgen. Die Liste kommt
    aus dem Register: eine neue Skizzen-Op taucht von selbst auf.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        from app.core.registry import REGISTRY, menu_tree

        super().__init__(parent)
        self.setWindowTitle(tr("Was soll daraus werden?"))
        # **Höhe, nicht nur Breite.** Ohne sie nahm das Layout seine kleinste:
        # 246 Bildpunkte, und darin standen zwei der fünf Erzeugungsarten — die
        # dritte mitten im Satz abgeschnitten, ohne sichtbare Bildlaufleiste.
        # Das ist der Dialog, in dem Weg 2 entschieden wird; wer hier scrollen
        # muss, um überhaupt zu erfahren, dass es fünf gibt, entscheidet
        # zwischen zwei.
        #
        # Jeder Eintrag ist zwei Zeilen hoch (Titel und Beschreibung), und die
        # Beschreibung bricht um — 440 tragen alle fünf, am Bild geprüft.
        self.setMinimumSize(380, 440)

        self._list = QListWidget(self)
        self._list.setWordWrap(True)
        section = next((entry for entry in menu_tree(REGISTRY) if entry.category == "sketch"), None)
        # **Der Normalfall steht oben.** Die Reihenfolge kam aus dem Menübaum,
        # und dort stand „Entlang eines Bogens führen" zuerst: Wer den Dialog
        # öffnet, liest als Erstes die exotischste der fünf Arten, während die
        # übliche darunter vorgewählt ist. Das Vorwählen allein genügt nicht —
        # gelesen wird von oben.
        entries = list(section.entries) if section else []
        entries.sort(key=lambda spec: (spec.name != DEFAULT_SKETCH_USE, str(spec.title)))
        for spec in entries:
            item = QListWidgetItem(f"{spec.title}\n    {spec.doc}")
            item.setData(Qt.ItemDataRole.UserRole, spec.name)
            self._list.addItem(item)
        self._preselect(DEFAULT_SKETCH_USE)
        # Ohne gebundenen Wert und trotzdem ein Ring: ``self`` steckt in der
        # Zelle des Abschlusses. ``weak_slot`` verwirft dabei das ``item``, das
        # das Signal schickt und ``accept`` nicht will.
        self._list.itemDoubleClicked.connect(weak_slot(self, SketchUseDialog.accept))

        buttons = QDialogButtonBox(self)
        use = buttons.addButton(tr("Weiter"), QDialogButtonBox.ButtonRole.AcceptRole)
        make_primary(use)
        # Kein „Abbrechen", das Arbeit vernichtet: der Weg zurück führt in
        # den Skizzenmodus, die Zeichnung bleibt (§2.1, keine Sackgassen).
        buttons.addButton(tr("Zurück zum Zeichnen"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(buttons)

    def _preselect(self, name: str) -> None:
        """Den Normalfall markieren, nicht den ersten Eintrag."""
        if not self._list.count():
            return
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole) == name:
                self._list.setCurrentRow(row)
                return
        self._list.setCurrentRow(0)

    def chosen(self) -> str:
        """Der Name der gewählten Skizzen-Operation, oder leer."""
        item = self._list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else ""
