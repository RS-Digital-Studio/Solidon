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

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
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

from app.core import expressions, manual
from app.core.errors import AppError
from app.core.registry import OperationSpec, inactive_dependency
from app.core.registry.surfaces import chooses_a_centre, first_sentence, normal_fields_of
from app.core.types import ParamSpec
from app.core.units import (
    DEGREE_UNIT,
    EPS_DISPLAY,
    EPS_GEOM,
    LengthUnit,
    decimals_for,
    from_mm,
    to_mm,
)
from app.i18n import tr
from app.ui.dialogs import ErrorNotice, align_to_the_front
from app.ui.labels import (
    BoundedSpin,
    LengthSpin,
    RowCheckBox,
    caption_toggles,
    choice_label,
    circle_measure,
    display_unit,
    explain_choices,
    feature_label,
    length,
    limit_sentence,
    localised,
    set_circle_measure,
    wheel_needs_focus,
)
from app.ui.leash import stop_watching_the_dying, weak_slot
from app.ui.organizer_dialog import OrganizerLayoutField
from app.ui.outline_dialog import ContourField
from app.ui.panels import collapsible
from app.ui.seal_dialog import SealPathField
from app.ui.style import (
    NORMAL,
    SPACE,
    TIGHT,
    WIDE,
    ContentFitIntent,
    ContentHeight,
    DialogScrollArea,
    expanded_width,
    make_primary,
    set_level,
)

if TYPE_CHECKING:
    from app.core.types import SceneObject
    from app.ui.placement_flow import PlacementFlow
    from app.ui.seal_flow import SealFlow


_SEAL_PATH_COMPANIONS = frozenset({"support_feature", "opening_signature", "counterface"})

#: Höchstens so viele Felder stehen vorn zugleich (Bauplan §2.4: zwei bis drei;
#: Entscheidung Robert, RM-513: vier als harte Grenze, neun von zehn
#: Operationen mit höchstens drei).
#:
#: Dieselbe Zahl wie ``MAX_FRONT_PARAMS`` in ``tests/test_interface_limits.py``,
#: und der Test hält beide zusammen (Muster ``OPEN_UP_TO``): Wer hier fünf
#: erlaubt, während die Prüfung vier verlangt, hat zwei Grenzen für dieselbe
#: Frage — und die Oberfläche wächst an der Stelle mit, die niemand misst.
#: Der Dialog hält sie auch beim Vorholen entschiedener Werte (``_promoted_fields``).
MAX_FRONT_FIELDS: Final = 4

#: Wie viele Feldnamen die zugeklappten „Weitere Einstellungen“ nennen.
ADVANCED_NAMES_SHOWN: Final = 3

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

    **Gefragt wird die Obergrenze, nicht die größere der beiden Grenzen.**
    Bis zum 30.08.2026 stand hier ``max(minimum, maximum)``, und wo eine
    Obergrenze fehlt, entschied damit die Untergrenze allein: „Breite der
    Textur, mindestens 0,5 mm, nach oben offen" galt als fein, und im Dialog
    stand **40,000** mm neben einer Bohrung mit **4,20** (Befund B36). Ein
    Feld ohne Obergrenze ist nach oben offen und gerade deshalb nicht fein;
    betroffen waren sechs von 360 Zahlenfeldern.
    """
    base = decimals_for(unit) if unit else 2
    if entry.maximum is not None and abs(entry.maximum) <= _FINE_BELOW:
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


def expression_hint(value: float, unit: str) -> str:
    """Was ein Ausdruck im Feld ergibt, geschrieben wie jede andere Zahl.

    Eine Länge über :func:`labels.length` (Anzeigeeinheit, Dezimalzeichen,
    keine negative Null), alles andere auf sechs Stellen gerundet. Mit ``:g``
    stand unter einer nachgebauten Lage „= -4.81259e-17 mm“ (Fensterabnahme
    RM-022): Rechenrauschen als Exponent, mit Punkt.
    """
    if unit == "mm":
        return f"= {length(value)}"
    tidy = round(float(value), 6) + 0.0
    shown = localised(f"{tidy:g}")
    return f"= {shown} {unit}" if unit else f"= {shown}"


def lead_sentence(spec: OperationSpec) -> str:
    """Der eine Satz über den Feldern: der erste der Beschreibung (RM-513).

    Vor dem ersten Feld standen bis zu 118 Wörter — die ganze Beschreibung und
    die Grenze dazu. Den Rest trägt der Tooltip derselben Zeile, die Grenze
    die zugeklappte Klappe „Wann nicht?“. Gekürzt wird wie in der
    Befehlspalette (:func:`app.core.registry.surfaces.first_sentence`), damit
    beide Orte denselben Satz zeigen.
    """
    return first_sentence(str(spec.doc or "")).strip()


def placement_hint() -> str:
    """Was der Dialog sagt, solange im Bild gezielt wird — seine erste Zeile."""
    return tr("Stelle im Bild anklicken.")


def lead_texts(spec: OperationSpec, *, placing: bool) -> tuple[str, ...]:
    """Was über dem ersten Feld steht, in der Reihenfolge des Dialogs.

    ``placing``: ob der Dialog gerade zum Zielen auffordert. Gezählt wird die
    Überschrift der Grenze, nicht ihr Inhalt — der steht zugeklappt. Die
    Wortgrenze dazu hält ``tests/test_interface_limits.py`` über das Register.
    """
    texts: list[str] = []
    if placing:
        texts.append(placement_hint())
    lead = lead_sentence(spec)
    if lead:
        texts.append(lead)
    if spec.caveat:
        texts.append(tr("Wann nicht?"))
    return tuple(texts)


def advanced_summary(titles: Sequence[str]) -> str:
    """Was die zugeklappten „Weitere Einstellungen“ enthalten (RM-513).

    Die ersten Feldnamen und ein „…“, wenn es mehr sind — die Klappe nannte
    ihren Inhalt nicht, und wer *Befestigung* suchte, fand sie nicht.
    """
    shown = ", ".join(titles[:ADVANCED_NAMES_SHOWN])
    return f"{shown} …" if len(titles) > ADVANCED_NAMES_SHOWN else shown


def place_text(face: str, point: Sequence[float]) -> str:
    """Die gewählte Stelle als eine Zeile: „Oberseite · 12,00 / 8,50 / 20,00 mm“.

    Statt dreier Koordinatenfelder vorn (Entscheidung Robert, RM-513); die
    Zahlen bleiben hinter „Weitere Einstellungen“ bearbeitbar.
    """
    numbers = " / ".join(
        (
            length(float(point[0]), with_unit=False),
            length(float(point[1]), with_unit=False),
            length(float(point[2])),
        )
    )
    return tr("{face} · {point}", face=face, point=numbers) if face else numbers


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
    captionChanged = Signal(str)
    """Die Beschriftung der Zeile hat sich geändert — „Radius" statt „Durchmesser"."""

    #: Was auf dem Umschalter steht. Kein Emoji (Sprachregelung), kein Symbol
    #: aus dem Icon-Satz: „fx" ist in jedem CAD dasselbe Zeichen für „hier
    #: rechnet eine Formel", und es braucht keine Übersetzung.
    TOGGLE_TEXT = "fx"

    #: Wie viele Zeichen das Ausdrucksfeld höchstens von sich aus zeigen will.
    #: „=max(@breite, 2000)“ hat neunzehn; was länger ist, rollt im Feld, und
    #: der Tooltip nennt es ganz (RM-457).
    EXPRESSION_CHARS = 40

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
        self._circle = entry.name.endswith("diameter") and entry.unit == "mm"
        """Ob dieses Feld ein Kreismaß ist — dann darf es auch als Radius sprechen."""
        self._half = self._circle and circle_measure() == "radius"
        """Ob gerade der halbe Wert gezeigt wird. Der Kern bekommt immer den ganzen."""
        self._core: float | None = None
        """Der Wert, wie er hereinkam — genauer als seine eigene Anzeige.

        40 mm sind 1,5748 Zoll, und aus 1,5748 Zoll werden 39,99992 mm. Ohne
        dieses Feld verschöbe ein Dialog, den man in Zoll nur *ansieht*, jedes
        Maß um den Rundungsfehler seiner Anzeige."""

        self._optional = entry.optional
        """Ob dieses Feld „nicht gesagt" kennt (RM-154).

        Der leere Zustand sitzt **einen Schritt unter** dem Mindestwert und
        trägt dort einen Sondertext — Qts eigenes Mittel dafür
        (``setSpecialValueText``). Ein Drehfeld hat immer eine Zahl; ohne diesen
        Platz gäbe es keinen Wert, der „habe ich nicht gesagt" bedeutet, und
        eine Bestätigung im Dialog schöbe jedes Loch in den Ursprung."""

        self.spin = BoundedSpin(self)
        self.spin.setDecimals(0 if entry.kind == "int" else _decimals_for(entry, self._shown))
        self.spin.setMinimum(
            self._as_shown(entry.minimum) if entry.minimum is not None else -1_000_000.0
        )
        if self._optional:
            self.spin.setMinimum(self.spin.minimum() - 10.0 ** -self.spin.decimals())
            self.spin.setSpecialValueText(tr("wie gemessen"))
        elif self.names_its_zero():
            # **Die Null sagt, was sie bedeutet** (RM-513): „automatisch“ statt
            # „0,00 mm“. Qt zeigt den Sondertext am Mindestwert, und der ist
            # hier null — ``ParamSpec.zero_text`` steht nur an solchen Feldern.
            self.spin.setSpecialValueText(str(entry.zero_text))
        self.spin.setMaximum(
            self._as_shown(entry.maximum) if entry.maximum is not None else 1_000_000.0
        )
        self._name_limits()
        if self._shown is not None:
            # Der Drehknopf bewegt sich um denselben **physischen** Betrag wie
            # in Millimetern. Qts Vorgabe ist 1.0, und ein ganzer Zoll je Klick
            # wäre ein Sprung über den ganzen Wertebereich einer Wandstärke.
            self.spin.setSingleStep(from_mm(1.0, self._shown))

        # **Die Einheit steht am Wert, nicht über ihm** (§19.3, Befund B12).
        # „Durchmesser [mm]" über einem Feld mit „4,20" ist die Schreibweise,
        # die das Haus überall sonst abgelegt hat — und die Klammer wanderte
        # bei der Umschaltung auf Zoll nicht mit, stand also über einem Feld,
        # das Zoll annahm. Am Suffix geht sie mit.
        shown = self._shown or entry.unit
        if shown:
            self.spin.setSuffix(f" {shown}")

        # **Gedeckelt wird nur die Zahl.** ``QFormLayout`` lässt Felder nach
        # Vorgabe mitwachsen (``AllNonFixedFieldsGrow``), und die Breite des
        # Dialogs kommt vom umgebrochenen Beschreibungssatz: gemessen bekam
        # ``decimate_mesh.triangles`` 366 Pixel für einen Wunsch von 120.
        # Aufklappmenüs, Textfelder und die Objektauswahl wachsen weiter — dort
        # ist die Breite der Inhalt —, deshalb kein ``FieldsStayAtSizeHint`` für
        # das ganze Formular. Gefragt wird die Wunschbreite, nicht die aktuelle:
        # Vor dem ersten Legen hat ein Widget seine Vorgabegröße.
        # Das Drehfeld hat die Größenrichtlinie
        # ``Expanding`` und wuchs deshalb mit dem Dialog — 270 Pixel für einen
        # Wunsch von 156, gemessen an *Kopien in Reihe oder Kreis*. Der
        # Umschalter bleibt rechts stehen, damit die Felder untereinander eine
        # Kante haben; gewachsen wäre allein die leere Fläche vor ihm.
        # **Und ein Boden dazu.** Der Deckel allein ließ die Zeile entscheiden,
        # wie schmal es wird: Im Bohrdialog blieben den Positionsfeldern
        # gemessene 65 Punkte Textraum, während „1234,56 mm" 64 braucht — ein
        # Zeichen mehr, und der Wert stand abgeschnitten da, ohne dass etwas
        # rot wird (Robert, 30.08.2026: „die eingabefelder sind jetzt manchmal
        # zu klein"). Der Wunsch des Feldes ist genau das Maß, das seinen Wert
        # zeigt; darunter darf es nicht.
        self.spin.setMinimumWidth(self.spin.sizeHint().width())
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
        self.text.installEventFilter(self)
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
        self.parameter_button.setToolTip(
            tr("Ein benanntes Maß des Projekts einsetzen — änderbar an einer Stelle.")
        )
        self.parameter_button.setAccessibleDescription(self.parameter_button.toolTip())
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
        # **Der Satz sagt, was der Knopf tut, nicht wie die Sache heißt.**
        # „fx" kennt, wer aus einem CAD kommt; für alle anderen ist es ein
        # abgeschnittenes Etikett (Befund B13). Was hier steht, muss deshalb
        # ohne das Wort „Parameterausdruck" auskommen — es erklärt einen
        # Fachbegriff mit einem zweiten.
        self.toggle.setToolTip(
            tr("Statt einer festen Zahl rechnen lassen — zum Beispiel die halbe Breite.")
        )
        self.toggle.setAccessibleDescription(self.toggle.toolTip())
        # Ein Umschalter, der nur anders aussieht, wäre Bedeutung allein über
        # Farbe (Regel 18). Der gedrückte Zustand *und* das sichtbar andere
        # Feld sagen dasselbe, und der Hinweis darunter sagt es ein drittes Mal.
        self.toggle.setAccessibleName(tr("Parameterausdruck"))
        # **„fx“ nur, wo es etwas zu rechnen gibt** (RM-513): ohne
        # Projektparameter stand es neben jedem Zahlenfeld und lud zu nichts
        # ein. „=“ und „@“ im Feld führen weiter in den Ausdruck
        # (:meth:`eventFilter`); dann erscheint der Knopf, der zurückführt.
        self.toggle.setVisible(self._offers_expressions())

        self.hint = QLabel("", self)
        self.hint.setVisible(False)
        set_level(self.hint, "caption")

        # Robert, 02.09.2026: „ein Umschalten zwischen Radius und Durchmesser
        # bei den jeweiligen Eingaben". Ein Knopf am Feld, der sagt, was die
        # Zahl gerade bedeutet; die Wahl gilt in jedem Kreisfeld und bleibt.
        self.circle_toggle: QToolButton | None = None
        if self._circle:
            self.circle_toggle = QToolButton(self)
            self.circle_toggle.setCheckable(True)
            self.circle_toggle.setChecked(self._half)
            self.circle_toggle.setAutoRaise(True)
            self.circle_toggle.setToolTip(
                tr(
                    "Als Radius oder als Durchmesser eingeben — die Zahl wird "
                    "umgerechnet, das Teil bleibt gleich."
                )
            )
            self.circle_toggle.setAccessibleDescription(self.circle_toggle.toolTip())
            self.circle_toggle.setAccessibleName(tr("Durchmesser oder Radius"))
            self._name_circle_toggle()
            self.circle_toggle.toggled.connect(self._switch_circle)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TIGHT)
        row.addWidget(self.spin)
        row.addWidget(self.text, 1)
        row.addWidget(self.parameter_button)
        if self.circle_toggle is not None:
            row.addWidget(self.circle_toggle)
        row.addWidget(self.toggle)
        self._row = row
        # **Der Rest der Zeile gehört dem Leerraum hinter den Knöpfen.** Ohne
        # ihn verteilte Qt ihn zwischen die Teile, sobald das Zahlenfeld an
        # seiner Höchstbreite stand: Das Feld rückte zur Mitte, *fx* an den
        # rechten Rand — je Zeile an eine andere Stelle, weil jedes Feld so
        # breit ist wie sein Wertebereich. Steht ein Ausdruck da, gehört der
        # Rest ihm (:meth:`_switch`).
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(row)
        layout.addWidget(self.hint)

        self.set_value(entry.default if start is None else start)

        self.toggle.toggled.connect(self._switch)
        self.spin.valueChanged.connect(self.changed)
        # **Eine Zahl jenseits der Grenzen wird abgelehnt, nicht gekürzt**
        # (:class:`BoundedSpin`): Der Satz steht unter dem Feld, sobald sie
        # getippt ist, und der Dialog sperrt *Übernehmen* mit demselben Satz.
        self._refused_shown = False
        self.spin.valueRefused.connect(lambda _number: self._show_refusal())
        self.spin.lineEdit().textEdited.connect(lambda _text: self._show_refusal())
        self.text.textChanged.connect(self._on_text)
        # Ohne diese Zeile läuft ``eventFilter`` nie — und damit bliebe der
        # Weg zu, den Handbuch und Parameterdialog beschreiben.
        self.spin.installEventFilter(self)

    # --- Wert -------------------------------------------------------------------

    def _as_shown(self, value_mm: float) -> float:
        """Ein Kernwert, wie das Feld ihn zeigt — in der Einheit, und halbiert,
        wenn das Feld gerade als Radius spricht."""
        shown = from_mm(value_mm, self._shown) if self._shown else value_mm
        return shown / 2.0 if self._half else shown

    def _as_core(self, shown: float) -> float:
        """Was im Feld steht, wie der Kern es bekommt — immer Millimeter und
        immer der Durchmesser."""
        whole = shown * 2.0 if self._half else shown
        return to_mm(whole, self._shown) if self._shown else whole

    def _offers_expressions(self) -> bool:
        """Ob „fx“ neben der Zahl steht: nur, wenn das Projekt Parameter hat."""
        return bool(self._parameter_values)

    def names_its_zero(self) -> bool:
        """Ob die Null dieses Feldes einen Namen trägt (``ParamSpec.zero_text``)."""
        entry = self._entry
        return (
            bool(entry.zero_text)
            and not entry.optional
            and entry.minimum is not None
            and abs(float(entry.minimum)) <= EPS_GEOM
        )

    def caption(self) -> str:
        """Wie die Zeile heißt — der Titel des Schemas, oder „Radius"."""
        return str(tr("Radius")) if self._half else str(self._entry.title)

    def _name_circle_toggle(self) -> None:
        assert self.circle_toggle is not None
        self.circle_toggle.setText("R" if self._half else "Ø")

    def _switch_circle(self, to_radius: bool) -> None:
        """Dieselbe Zahl, anders gelesen: der Kernwert bleibt, die Anzeige halbiert."""
        core = self._number()
        self._half = bool(to_radius)
        set_circle_measure("radius" if to_radius else "diameter")
        self._name_circle_toggle()
        entry = self._entry
        # ``QSignalBlocker`` und nicht das Paar von Hand: ``_as_shown`` rechnet
        # viermal um, und wirft eine dieser Umrechnungen, bliebe das Feld für
        # immer stumm — es nähme weiter Eingaben an und meldete keine weiter.
        with QSignalBlocker(self.spin):
            self.spin.setMinimum(
                self._as_shown(entry.minimum) if entry.minimum is not None else -1_000_000.0
            )
            self.spin.setMaximum(
                self._as_shown(entry.maximum) if entry.maximum is not None else 1_000_000.0
            )
            self._name_limits()
            self._core = core
            self.spin.setValue(self._as_shown(core))
        self.captionChanged.emit(self.caption())

    def _name_limits(self) -> None:
        """Der Satz einer abgelehnten Zahl nennt die Grenzen des Schemas.

        Das Drehfeld eines Feldes mit „wie gemessen“ reicht eine Stufe unter den
        Mindestwert (dort steht der Sonderwert); der Satz sagte deshalb
        „Untergrenze -0,01 mm“, wo 0 gilt (Code-Review 0.5.1, U-3).
        """
        entry = self._entry
        self.spin.name_limits(
            self._as_shown(entry.minimum) if entry.minimum is not None else None,
            self._as_shown(entry.maximum) if entry.maximum is not None else None,
        )

    def set_value(self, value: Any) -> None:
        """Trägt Zahl oder Ausdruck ein und stellt das Feld passend."""
        if expressions.is_expression(value):
            self.text.setText(str(value))
            self.toggle.setChecked(True)
            self._switch(True)
            # Ein gespeicherter Ausdruck wird gelesen, nicht weitergetippt:
            # Der Anfang mit dem Funktionsnamen steht im Bild (RM-457).
            self.text.setCursorPosition(0)
            return
        if value is None and self._optional:
            # **Leer heißt hier etwas**, und zwar „nicht gesagt" (RM-154). Ohne
            # diese Zeile stünde die Null da, und die ist an einer Koordinate
            # die Mitte des Teils.
            self._core = None
            self.spin.setValue(self.spin.minimum())
            return
        if value is not None:
            try:
                self._core = float(value)
                self.spin.setValue(self._as_shown(float(value)))
            except TypeError, ValueError:
                # Ein Wert, der weder Zahl noch Ausdruck ist, gehört trotzdem
                # gezeigt statt verschluckt — sonst stünde im Dialog etwas
                # anderes, als im Dokument steht.
                self.text.setText(str(value))
                self.toggle.setChecked(True)
                self._switch(True)

    def value(self) -> float | int | str | None:
        """Die Zahl, der Ausdruck wörtlich — oder nichts.

        Ein leer geräumtes Ausdrucksfeld gibt die Zahl zurück, die daneben
        stand. Ein leerer Text wäre weder das eine noch das andere, und der
        Stapel bekäme einen Parameter, den keine Auswertung lesen kann.

        ``None`` gibt allein ein ``optional``-Feld zurück, und nur auf seinem
        Sonderwert: „nicht gesagt" (RM-154).
        """
        if self.toggle.isChecked() and (entered := self.text.text().strip()):
            # Ein Ausdruck bleibt wörtlich. Ihn umzurechnen hieße, „=@breite/2"
            # in eine Zahl zu verwandeln — die Bindung wäre weg, und §13 rechnet
            # ohnehin in Millimetern. Ergänzt werden nur ``=`` und ``@``, wo
            # der Kunde sie weggelassen hat (``expressions.canonical``); ist
            # ein Name mehrdeutig, bleibt der Text, und ``_describe`` sagt es.
            try:
                return expressions.canonical(entered, self._parameter_values)
            except AppError:
                return entered
        if self._optional and self.spin.value() <= self.spin.minimum():
            return None
        number = self._number()
        return int(number) if self._entry.kind == "int" and number.is_integer() else number

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
        # Auch exakt eine halbe Stelle ist unverändert; Qt rundet sie auf.
        # ulp deckt nur die binäre Darstellung der Subtraktion ab.
        return abs(self._as_shown(self._core) - shown) <= step / 2.0 + math.ulp(shown)

    # --- Umschalten -------------------------------------------------------------

    def refusal(self) -> str:
        """Warum dieses Feld gerade nichts übernimmt — leer, wenn es trägt.

        Im Zahlenmodus die getippte Zahl jenseits der Grenzen
        (:meth:`BoundedSpin.refusal`), im Ausdrucksmodus ein Ausdruck, der
        jenseits der Grenzen des Schemas landet: „=@breite*100“ ergab 1500 mm
        bei einer Obergrenze von 1000, und der Hinweis sagte nur „= 1500 mm“.
        """
        if not self.toggle.isChecked():
            return self.spin.refusal()
        value = self._expression_value()
        if value is None:
            return ""
        low, high = self._entry.minimum, self._entry.maximum
        unit = f" {self._entry.unit}" if self._entry.unit else ""
        if high is not None and value > high + EPS_DISPLAY:
            return limit_sentence(
                localised(f"{value:g}") + unit, localised(f"{high:g}") + unit, above=True
            )
        if low is not None and value < low - EPS_DISPLAY:
            return limit_sentence(
                localised(f"{value:g}") + unit, localised(f"{low:g}") + unit, above=False
            )
        return ""

    def _expression_value(self) -> float | None:
        """Was der Ausdruck im Feld ergibt — ``None``, wenn er nichts ergibt."""
        entered = self.text.text().strip()
        if not entered:
            return None
        try:
            written = expressions.canonical(entered, self._parameter_values)
            expressions.check(written)
            return float(expressions.evaluate(written, self._parameter_values))
        except AppError, TypeError, ValueError:
            return None

    def _show_refusal(self, *, notify: bool = True) -> None:
        """Zeigt oder räumt den Satz einer abgelehnten Zahl unter dem Zahlenfeld."""
        if self.toggle.isChecked():
            return
        said = self.spin.refusal()
        if said:
            self.hint.setText(said)
            self.hint.setVisible(True)
            self.spin.setAccessibleDescription(said)
        elif self._refused_shown:
            self.hint.setText("")
            self.hint.setVisible(False)
            self.spin.setAccessibleDescription("")
        if bool(said) != self._refused_shown:
            self._refused_shown = bool(said)
            # Der Dialog fragt den Knopf neu (``_follow_source_pending``).
            if notify:
                self.changed.emit()

    def _switch(self, to_expression: bool) -> None:
        if not to_expression:
            # **Zurück zur Zahl heißt: die Zahl, die der Ausdruck ergab.** Das
            # Drehfeld stand sonst auf seinem Anfangswert — an einem gebundenen
            # Quader auf dem Mindestmaß 0,1 mm statt der 40 mm der Breite.
            value = self._expression_value()
            if value is not None:
                shown = self._as_shown(value)
                with QSignalBlocker(self.spin):
                    self._core = value
                    self.spin.lineEdit().setText(self.spin.textFromValue(shown))
                    if self.spin.refused_value() is None:
                        self.spin.setValue(shown)
        self.spin.setVisible(not to_expression)
        self.text.setVisible(to_expression)
        self.toggle.setVisible(to_expression or self._offers_expressions())
        # Der Leerraum hinter den Knöpfen weicht dem Ausdruck.
        self._row.setStretch(self._row.count() - 1, 0 if to_expression else 1)
        self.parameter_button.setVisible(to_expression)
        self.hint.setVisible(to_expression)
        if self.circle_toggle is not None:
            # Ein Ausdruck meint immer die Größe des Schemas, den Durchmesser.
            self.circle_toggle.setEnabled(not to_expression)
        if to_expression and not self.text.text().strip():
            # Aus der stehenden Zahl wird der Anfang des Ausdrucks: wer
            # umschaltet, will meist dieselbe Größe anders ausdrücken. Also die
            # Größe und nicht ihre Anzeige — ein Ausdruck rechnet in
            # Millimetern (§13), und der Hinweis darunter beschriftet ihn auch
            # so. „= 1.5748 mm" unter einem Feld, in dem 40 mm gemeint waren,
            # war die Anzeige, die ihren eigenen Fehler bezeugt.
            self.text.setText(f"={self._number():g}")
        if to_expression:
            self._fit_expression()
            self._name_expression()
            # **Der Fokus geht mit.** Ohne diese Zeile bleibt er auf dem
            # Umschalter, und das Textfeld liegt in der Tab-Reihenfolge davor
            # (Spin, Text, Umschalter) — der Kunde muss Umschalt+Tab drücken,
            # um in das Feld zu kommen, das er gerade aufgemacht hat.
            self.text.setFocus()
            self.text.setCursorPosition(len(self.text.text()))
        self._describe()
        if not to_expression:
            self._show_refusal(notify=False)
        self.changed.emit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Fängt ``=`` und ``@`` im Zahlenfeld ab und macht daraus einen
        Ausdruck.

        Am Filter und nicht in :class:`NumberSpin`: Die Klasse steht auch dort,
        wo es gar keine Ausdrücke gibt (Druckeinstellungen, Skizzenmaße), und
        dort wäre ein Zeichen, das plötzlich ein Textfeld aufmacht, ein
        Rätsel. Hier gehört es zur Sache — neben dem Feld steht der fx-Knopf.
        """
        if stop_watching_the_dying(self, watched, event):
            return False
        if watched is self.text and event.type() == QEvent.Type.FocusOut:
            # Wer das Feld verlässt, liest den Ausdruck wieder von vorn; Qt
            # ließe ihn dort stehen, wo zuletzt getippt wurde (RM-457).
            self.text.setCursorPosition(0)
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

    def _fit_expression(self) -> None:
        """Das Ausdrucksfeld so breit wie sein Ausdruck, mindestens wie das Beispiel.

        Vorher bekam es, was die Zeile übrig ließ, und das war im Schrittdialog
        weniger als „=max(@breite, 2000)“ (RM-457). Gedeckelt bei
        :attr:`EXPRESSION_CHARS` Zeichen; nie schmaler als die Zahl, an deren
        Stelle es steht.
        """
        metrics = self.text.fontMetrics()
        letter = metrics.horizontalAdvance("x")
        # Rahmen und Innenrand des Felds: was Qts Wunschbreite über ihre
        # siebzehn Zeichen hinaus rechnet.
        chrome = max(0, self.text.sizeHint().width() - 17 * letter)
        wanted = max(
            metrics.horizontalAdvance(self.text.text()),
            metrics.horizontalAdvance(self.text.placeholderText()),
        )
        wanted = min(wanted, self.EXPRESSION_CHARS * letter)
        self.text.setMinimumWidth(max(self.spin.minimumWidth(), wanted + chrome + letter))

    def _name_expression(self) -> None:
        """Der Tooltip nennt den ganzen Ausdruck, darunter, was erlaubt ist."""
        written = self.text.text().strip()
        help_text = self._grammar_help()
        self.text.setToolTip(f"{written}\n\n{help_text}" if written else help_text)

    def _on_text(self) -> None:
        self._name_expression()
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
            written = expressions.canonical(entered, self._parameter_values)
            expressions.check(written)
            value = expressions.evaluate(written, self._parameter_values)
        except AppError as problem:
            self.hint.setText(str(problem.detail or problem.title))
            return
        if self._entry.kind == "int" and not float(value).is_integer():
            self.hint.setText(tr("Der Ausdruck muss eine ganze Zahl ergeben. Passen Sie ihn an."))
            return
        self.hint.setText(self.refusal() or expression_hint(value, self._entry.unit or ""))


class CountField(ValueField):
    """Die Stückzahl einer Operation — mit fx, aufgelöst beim Übernehmen.

    Hier stand ein nacktes ``QSpinBox``: Hinter jedem anderen Zahlenfeld steht
    ein fx, und genau die Stückzahl — *Objekt duplizieren*, *Kopien in Reihe
    oder Kreis* — hatte keines. Wer sechs Dome für ``@reihen * @spalten``
    wollte, rechnete im Kopf.

    **Der Ausdruck wird zur Zahl, bevor er den Stapel erreicht.** Die
    Kennungen der Kopien vergibt der Stapel beim Anlegen, und die Stückzahl
    steht dort als Zahl (``History._stated``, Registertext von *Objekt
    duplizieren*); ein Ausdruck, der sich später ändert, hieße neue Objekte ohne
    Schritt. Der Hinweis unter dem Feld sagt das, bevor jemand übernimmt — und
    was nicht ganzzahlig im erlaubten Bereich landet, sperrt den Knopf mit
    Grund, statt beim Kern als „kein Ausdruck" zu enden.
    """

    def resolved(self) -> int | None:
        """Die Stückzahl, die übernommen wird — oder ``None``, wenn sie nicht trägt."""
        entered = super().value()
        try:
            number = (
                expressions.evaluate(entered, self._parameter_values)
                if isinstance(entered, str)
                else entered
            )
        except AppError:
            return None
        if number is None or not float(number).is_integer():
            return None
        count = int(number)
        low, high = self._entry.minimum, self._entry.maximum
        if (low is not None and count < low) or (high is not None and count > high):
            return None
        return count

    @property
    def valid(self) -> bool:
        """Ob die Eingabe eine Stückzahl ergibt, die der Kern annimmt."""
        return self.resolved() is not None

    def value(self) -> float | int | str | None:
        """Die Zahl, nie der Ausdruck — siehe Klassentext."""
        count = self.resolved()
        return count if count is not None else super().value()

    def problem(self) -> str:
        """Warum die Eingabe keine Stückzahl ist — für Knopf und Hinweis."""
        low, high = self._entry.minimum, self._entry.maximum
        if low is not None and high is not None:
            return str(
                tr("Die Stückzahl muss eine ganze Zahl von {low} bis {high} ergeben.")
            ).format(low=int(low), high=int(high))
        return str(tr("Der Ausdruck muss eine ganze Zahl ergeben. Passen Sie ihn an."))

    def _describe(self) -> None:
        super()._describe()
        entered = self.text.text().strip()
        if not self.toggle.isChecked() or not entered:
            return
        count = self.resolved()
        if count is None:
            try:
                expressions.check(entered)
                expressions.evaluate(entered, self._parameter_values)
            except AppError:
                # Den Satz des Auswerters behält ``ValueField`` — er sagt,
                # welcher Name fehlt oder welche Klammer.
                return
            self.hint.setText(self.problem())
            return
        self.hint.setText(
            str(tr("= {count} — steht danach als feste Stückzahl im Schritt.")).format(count=count)
        )


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

    def __init__(
        self, start: str, parent: QWidget | None = None, *, required: bool = False
    ) -> None:
        super().__init__(parent)
        from app.core.knowledge import profiles

        # Eine ausdrücklich verlangte Materialrolle darf kein Projektprofil
        # versprechen. Der leere Eintrag ist dort eine noch offene Auswahl.
        self.addItem(tr("Materialprofil wählen …") if required else tr("Wie das Projekt"), "")
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


class DeferredSourcePicker:
    """Startet eine Dateiaufnahme und liefert ihre Wahl später zurück."""

    def __init__(
        self,
        start: Callable[[Callable[[tuple[str, str] | None], None]], None],
        cancel: Callable[[], None] | None = None,
    ) -> None:
        self.start = start
        self.cancel = cancel


class ImageSourceField(QWidget):
    """Eine Quelle wählen — oder eine neue von der Platte holen (§25, P16.7).

    Ein ``source``-Feld bot an, was das Projekt an Quellen hat, und dorthin
    führte kein Bildformat: Wer „Relief auflegen" wählte, sah eine STL in einem
    Feld namens „Bild", und der Befund danach schlug „Ein Bild wählen." vor —
    eine Handlung, die die Oberfläche nicht anbot. Der Knopf ist dieser
    fehlende Weg.

    **Und er fehlte am Quellenfeld genauso, nur ohne dass es jemand meldete.**
    *Modell laden*, *STEP laden* und *Zeichnung hochziehen* zeigen dort die
    Quellen, die das Projekt schon hat — in einem frischen Projekt also nichts.
    Die Liste klappte auf und war leer; das liest sich nicht als „hier fehlt
    etwas", sondern als kaputt, und getroffen hat es ausgerechnet die drei
    Einstiegsdialoge (Regel 19: keine Sackgassen). Deshalb trägt die Klasse
    beide Fälle und ihr Knopf seine Beschriftung als Parameter — der Name
    stammt aus dem Bildfall, die Sache tut es nicht mehr.
    """

    changed = Signal()
    pendingChanged = Signal(bool)

    def __init__(
        self,
        images: Mapping[str, str],
        pick: Callable[[], tuple[str, str] | None] | DeferredSourcePicker | None,
        start: str = "",
        parent: QWidget | None = None,
        button_text: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._pending = False
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
        self._button_text = self.button.text()
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
        if isinstance(self._pick, DeferredSourcePicker):
            self._set_pending(True)
            self._pick.start(weak_slot(self, ImageSourceField._picked, forward=True))
            return
        self._picked(self._pick())

    def _picked(self, chosen: tuple[str, str] | None) -> None:
        """Eine synchrone oder nachgereichte Wahl in das Feld übernehmen."""

        self._set_pending(False)
        if chosen is None:
            return
        identifier, name = chosen
        index = self.combo.findData(identifier)
        if index < 0:
            self.combo.addItem(name, identifier)
            index = self.combo.count() - 1
        self.combo.setCurrentIndex(index)

    @property
    def pending(self) -> bool:
        """Ob dieser Wähler noch auf die gelesene Datei wartet."""

        return self._pending

    def cancel_pending(self) -> None:
        """Die zu diesem Feld gehörende Dateiaufnahme logisch abbrechen."""

        if (
            self._pending
            and isinstance(self._pick, DeferredSourcePicker)
            and self._pick.cancel is not None
        ):
            self._pick.cancel()

    def _set_pending(self, pending: bool) -> None:
        """Feld und Umgebung über den Wartezustand auf demselben Stand halten."""

        if self._pending == pending:
            return
        self._pending = pending
        self.button.setText(tr("Datei wird gelesen …") if pending else self._button_text)
        self.button.setEnabled(not pending)
        self.combo.setEnabled(not pending)
        self.pendingChanged.emit(pending)

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
        # ``AppError`` wird hier **nicht** geholt, obwohl der Fang unten ihn
        # braucht: Ein Import im Rumpf macht den Namen zur lokalen Variablen
        # und verdeckt damit den modulweiten aus dem Kopf dieser Datei.
        # Scheiterte ausgerechnet diese Zeile, wertete Python beim Behandeln
        # einen ungebundenen Namen aus — aus dem ImportError würde ein
        # ``NameError``, und der verließe eine Funktion, die im Docstring
        # zusagt, im Dialog keinen Fehler zu werfen.
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

    Zwei Wege für eine Auskunft: Der Tooltip erscheint, wo die Maus steht, und
    ``accessibleDescription`` liest ein Vorleser vor (Regel 18 — nicht nur eine
    Kodierung). Statustipps stehen nur an Menüaktionen (RM-509).

    ``caption`` darf ``None`` sein, weil ``QFormLayout.labelForField`` das
    zurückgibt, sobald eine Zeile über beide Spalten geht (``addRow`` mit einem
    Argument). Nachgemessen ist der Fall hier keiner: Alle 457 Zeilen des
    Registers haben eine Beschriftung. Der Zweig steht für die erste Zeile, die
    keine hat, und nicht für eine, die es schon gibt.
    """
    editor.setToolTip(sentence)
    editor.setAccessibleDescription(sentence)
    if caption is not None:
        caption.setToolTip(sentence)


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

        # Ein Gelenkwinkel ist nie optional — null Grad heißt null Grad, und
        # ein Knochen ohne Winkel wäre keine Stellung. ``or 0.0`` ist deshalb
        # kein Rückfall, sondern die Zusage, dass hier eine Zahl steht.
        return pose_text(
            {bone: [field.value() or 0.0 for field in row] for bone, row in self._fields.items()}
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


class StrokeSummary(QLabel):
    """Die gemalten Züge bleiben Daten; im Dialog steht ihre Anzahl."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        from app.core.geom.sculpt import stroke_count, strokes_from_text

        self._text = text
        try:
            count = stroke_count(strokes_from_text(text))
            summary = tr("Ein Zug") if count == 1 else tr("{count} Züge").format(count=count)
        except AppError:
            summary = tr("Diese Pinselzüge lassen sich nicht lesen.")
        super().__init__(summary, parent)
        self.setAccessibleName(tr("Striche"))

    def value(self) -> str:
        """Den gespeicherten Text unverändert an die Operation geben."""
        return self._text


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


class EdgeSetField(QWidget):
    """Einzelne Kanten wählen — die Antwort auf „diese eine Ecke" (E4, RM-147).

    Bis hierher gab es nur Gruppen: alle senkrechten, alle waagerechten, oben,
    unten, alle. Wer **eine** Kante brechen wollte, bekam vier.

    Der Wert ist ein Text aus Schlüsseln mit Leerzeichen dazwischen — was der
    Kern als ``kind="edges"`` ablegt. Was der Kunde sieht, ist etwas anderes:
    die Lage der Kante und ihre Länge, denn ein Schlüssel wie
    ``e:-20.00,-15.00,10.00:0.000,0.000,1.000`` ist eine Kennung und keine
    Beschriftung (§2.4, „ein Sammelparameter bekommt seinen Editor").
    """

    changed = Signal()
    validityChanged = Signal()

    def __init__(
        self, choices: Mapping[str, str], selected: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        chosen = tuple(part for part in str(selected or "").split() if part)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Kanten auswählen"))
        self.list.setMinimumHeight(96)
        self.list.setMaximumHeight(210)
        # Auch eine Kante, die es nicht mehr gibt, steht in der Liste: Sonst
        # verschwände die Wahl eines gespeicherten Schritts beim Öffnen, ohne
        # dass jemand sie zurückgenommen hätte (§15.4).
        for identifier in dict.fromkeys((*choices, *chosen)):
            item = QListWidgetItem(choices.get(identifier, identifier), self.list)
            item.setData(Qt.ItemDataRole.UserRole, identifier)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if identifier in chosen else Qt.CheckState.Unchecked
            )
        layout.addWidget(self.list)
        self.hint = QLabel(
            tr("Die Kanten stehen in der Reihenfolge, in der sie am Körper liegen."), self
        )
        self.hint.setWordWrap(True)
        set_level(self.hint, "caption")
        layout.addWidget(self.hint)
        self.setFocusProxy(self.list)
        self.list.itemChanged.connect(self._changed)

    def value(self) -> str:
        return " ".join(
            str(self.list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.list.count())
            if self.list.item(row).checkState() == Qt.CheckState.Checked
        )

    @property
    def valid(self) -> bool:
        """Ohne angekreuzte Kante trägt die Wahl nicht — solange sie gilt.

        **Ein ausgegrautes Feld hat keine Meinung**: Steht der Umschalter auf
        einer Gruppe, wirkt diese Liste nicht, und leer zu sein ist dann kein
        Mangel. Ohne diese Hälfte sperrte das leere Feld den Knopf auch dort,
        wo es gar nicht gefragt ist.
        """
        return not self.isEnabled() or bool(self.value())

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt gibt den Namen
        """Ein- und Ausschalten ändert, ob die leere Wahl zählt."""
        super().setEnabled(enabled)
        self.validityChanged.emit()

    def _changed(self, *_args: object) -> None:
        self.changed.emit()
        self.validityChanged.emit()


def _three_points(text: str) -> list[list[float]]:
    """Drei Punkte aus ``x,y,z;x,y,z;x,y,z`` — oder dreimal der Ursprung, wo nichts lesbar ist."""
    rows: list[list[float]] = []
    for part in str(text or "").split(";")[:3]:
        try:
            values = [float(value) for value in part.split(",")]
        except ValueError:
            values = []
        rows.append(values if len(values) == 3 else [0.0, 0.0, 0.0])
    while len(rows) < 3:
        rows.append([0.0, 0.0, 0.0])
    return rows


class PointsField(QWidget):
    """Drei Punkte einer Ebene — eingetragen oder im Bild angeklickt (RM-400).

    Der Wert ist der Text ``x,y,z;x,y,z;x,y,z``, wie ihn der Kern als
    ``kind="points"`` ablegt; was der Kunde sieht, sind drei Zeilen mit je
    drei Längenfeldern in seiner Einheit. *Im Bild wählen* bittet das Fenster,
    die nächsten drei Klicks auf den Körper anzunehmen (:meth:`take_point`):
    Jeder füllt den nächsten Punkt, wie die Bohrung ihre Position aus einem
    Klick bekommt. Die Zahl bleibt die Wahrheit, der Klick die bequeme Eingabe.
    """

    changed = Signal()
    pickRequested = Signal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        self.spins: list[tuple[LengthSpin, LengthSpin, LengthSpin]] = []
        for number, values in enumerate(_three_points(text), start=1):
            line = QHBoxLayout()
            line.setSpacing(TIGHT)
            caption = QLabel(tr("Punkt {number}").format(number=number), self)
            line.addWidget(caption)
            row: list[LengthSpin] = []
            for axis_name, value in zip(("X", "Y", "Z"), values, strict=True):
                spin = LengthSpin(self)
                spin.set_range_mm(-10_000.0, 10_000.0)
                spin.set_value_mm(value)
                # Ein Name je Feld für den Bildschirmleser — „Punkt 2, Y“ und
                # nicht neunmal „Drehfeld“, wie im Dialog *Neue Ebene*.
                spin.setAccessibleName(
                    tr("Punkt {number}, {axis}").format(number=number, axis=axis_name)
                )
                spin.valueChanged.connect(self._edited)
                line.addWidget(spin)
                row.append(spin)
            self.spins.append((row[0], row[1], row[2]))
            layout.addLayout(line)
        self.pick = QPushButton(tr("Im Bild wählen"), self)
        self.pick.setToolTip(
            tr("Danach füllen drei Klicks auf den Körper die drei Punkte, der Reihe nach.")
        )
        self.pick.clicked.connect(self._start_pick)
        layout.addWidget(self.pick)
        self._next = 0

    def value(self) -> str:
        """Die drei Punkte als ``x,y,z;x,y,z;x,y,z`` in Millimetern."""
        return ";".join(
            ",".join(repr(float(spin.value_mm())) for spin in row) for row in self.spins
        )

    def take_point(self, point: Sequence[float]) -> int:
        """Den nächsten Punkt setzen — gibt seine Nummer zurück, 1 bis 3."""
        row = self.spins[self._next]
        for spin, value in zip(row, point, strict=True):
            with QSignalBlocker(spin):
                spin.set_value_mm(float(value))
        number = self._next + 1
        self._next = number % 3
        self.changed.emit()
        return number

    def _start_pick(self) -> None:
        self._next = 0
        self.pickRequested.emit()

    def _edited(self, *_args: object) -> None:
        self.changed.emit()


class FeatureSetField(QWidget):
    """Benannte Flächen wählen; eine leere Zwischenwahl erweitert niemals den Auftrag.

    ``empty`` sagt, was eine leere Wahl bedeutet, und beschriftet den Haken
    dafür: am Filament der ganze Körper (die Vorgabe), an den Öffnungen des
    Aushöhlens keine Öffnung. ``None`` heißt, leer gibt es nicht — eine
    Pflichtliste wie die Quellen eines Merkmalsmusters (P6.7) hat keinen
    Haken, und gültig ist sie erst mit einem markierten Merkmal. Ein Haken
    „Ganzer Körper" an einer Liste, deren Leere etwas anderes heißt, wäre ein
    Versprechen, das die Operation nicht hält.
    """

    changed = Signal()
    validityChanged = Signal()

    def __init__(
        self,
        choices: Mapping[str, str],
        selected: Sequence[str],
        parent: QWidget | None = None,
        *,
        empty: str | None = "",
        hint: str = "",
    ) -> None:
        super().__init__(parent)
        self._last_value = tuple(dict.fromkeys(selected))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        self.whole = QCheckBox(empty or tr("Ganzer Körper"), self)
        self.whole.setChecked(not selected and empty is not None)
        self.whole.setVisible(empty is not None)
        layout.addWidget(self.whole)
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Flächen auswählen"))
        self.list.setMinimumHeight(96)
        self.list.setMaximumHeight(210)
        for identifier in dict.fromkeys((*choices, *selected)):
            item = QListWidgetItem(choices.get(identifier, identifier), self.list)
            item.setData(Qt.ItemDataRole.UserRole, identifier)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if identifier in selected else Qt.CheckState.Unchecked
            )
        layout.addWidget(self.list)
        self.hint = QLabel(hint or tr("Flächen markieren oder den ganzen Körper wählen."), self)
        self.hint.setWordWrap(True)
        set_level(self.hint, "caption")
        layout.addWidget(self.hint)
        self.list.setEnabled(not self.whole.isChecked())
        self.setFocusProxy(self.list)
        self.whole.toggled.connect(self._changed)
        self.list.itemChanged.connect(self._changed)

    def _selected(self) -> tuple[str, ...]:
        return tuple(
            str(self.list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.list.count())
            if self.list.item(row).checkState() == Qt.CheckState.Checked
        )

    @property
    def valid(self) -> bool:
        """Keine markierte Fläche bedeutet nur mit ausdrücklichem Haken den ganzen Körper."""
        return self.whole.isChecked() or bool(self._selected())

    def value(self) -> list[str]:
        """Während einer unvollständigen Wahl bleibt die letzte gültige Vorschau erhalten."""
        return list(self._last_value)

    def _changed(self, *_args: object) -> None:
        self.list.setEnabled(not self.whole.isChecked())
        self.validityChanged.emit()
        if self.valid:
            self._last_value = () if self.whole.isChecked() else self._selected()
            self.changed.emit()

    def add_feature(self, identifier: str, label: str) -> None:
        """Ein Klick im Modell ergänzt die Auswahl statt die vorige Fläche zu ersetzen."""
        with QSignalBlocker(self.list), QSignalBlocker(self.whole):
            item = next(
                (
                    self.list.item(row)
                    for row in range(self.list.count())
                    if self.list.item(row).data(Qt.ItemDataRole.UserRole) == identifier
                ),
                None,
            )
            if item is None:
                item = QListWidgetItem(label or identifier, self.list)
                item.setData(Qt.ItemDataRole.UserRole, identifier)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            self.whole.setChecked(False)
            item.setCheckState(Qt.CheckState.Checked)
        self._changed()


def direction_fields(spec: OperationSpec) -> frozenset[str]:
    """Die Felder, die die Richtung des Werkzeugs tragen: Normale und Achse.

    Die Namen der Normalen kennt das Register (:func:`normal_fields_of` — ein
    Rezept mit eigenem ``nx`` nennt sie ``surface_nx`` …); ``axis`` ist der
    Rückfall, den die Operation nimmt, solange die drei null sind. Auch sie
    kann bei einem Rezept umbenannt sein. Der Dialog fragt hier, welche
    vorbelegten Werte er **nicht** nach vorn holt.
    """
    from app.core.knowledge.parts.ops import placement_fields

    return frozenset(normal_fields_of(spec)) | {placement_fields(spec.params)["axis"]}


def place_fields(spec: OperationSpec) -> tuple[str, str, str] | None:
    """Die drei Felder der Stelle, wenn der Dialog sie als Lesezeile zeigt — sonst ``None``.

    Eine Operation, die an einem Körper ansetzt und ihre Stelle hinten führt
    (Bohrung, Beschriftung, Bausteine), nennt die gewählte Stelle vorn in einer
    Zeile; die Koordinaten bleiben hinten bearbeitbar (Entscheidung Robert,
    RM-513). Wo die Koordinaten selbst die Eingabe sind (*Merkmal
    verschieben*), stehen sie als Felder vorn, und ein Erzeuger sagt seine
    Fläche im Sitzsatz (:meth:`OperationDialog.show_seat`).
    """
    from app.core.knowledge.parts.ops import placement_fields

    if spec.consumes == 0:
        return None
    placed = placement_fields(spec.params)
    axes = tuple(placed.get(axis, axis) for axis in ("x", "y", "z"))
    entries = {entry.name: entry for entry in spec.params.spec()}
    if not all(axis in entries and entries[axis].placement == "advanced" for axis in axes):
        return None
    return axes[0], axes[1], axes[2]


def _promoted_fields(spec: OperationSpec, given: Mapping[str, Any]) -> frozenset[str]:
    """Entschiedene Werte nach vorn holen — so viele, wie die Vorderseite fasst.

    Die angeklickte Fläche, ein gemessener Durchmesser, eine übergebene
    Zeichnung (§18.5) gehören vor den Nutzer. Nicht dazu gehören Richtungen
    (:func:`direction_fields`), Kantenabstände der Flächenbindung und die
    Stelle selbst, wo die Lesezeile sie nennt (:func:`place_fields`) — samt
    dem Merkmal, an dem sie hängt. Dazu ein Deckel: Vorn stehen nie mehr als
    :data:`MAX_FRONT_FIELDS` Felder zugleich; was keinen Platz findet, bleibt
    hinten, in der Reihenfolge des Schemas.
    """
    from app.core.knowledge.parts.ops import placement_fields

    entries = spec.params.spec()
    direction = direction_fields(spec)
    placed = placement_fields(spec.params)
    kept_back = {placed.get(name, name) for name in ("surface_distance_1", "surface_distance_2")}
    place = place_fields(spec)
    if place is not None:
        kept_back.update(place)
        kept_back.add(placed.get("at_feature", "at_feature"))
    if spec.name in {"pattern", "pattern_feature", "mirror_object"}:
        # Die Drehmitte wählt die Zeile *Drehmitte* vorn; ihre Zahlen bleiben hinten.
        kept_back.update({"cx", "cy", "cz"})
    candidates = [
        entry
        for entry in entries
        if entry.name in given
        and given[entry.name] != entry.default
        and entry.name not in direction
        and entry.name not in kept_back
        and not entry.internal
        and entry.placement != "front"
    ]
    values = {entry.name: entry.default for entry in entries} | dict(given)
    room = MAX_FRONT_FIELDS - sum(
        1
        for entry in entries
        if entry.placement == "front"
        and not entry.internal
        and inactive_dependency(entry, entries, values) is None
    )
    promoted: set[str] = set()
    for entry in candidates:
        if room <= 0:
            break
        if inactive_dependency(entry, entries, values) is not None:
            continue
        promoted.add(entry.name)
        room -= 1
    return frozenset(promoted)


def even_value_fields(fields: Iterable[ValueField]) -> None:
    """Zahlenfelder, die untereinander stehen, so breit wie das breiteste.

    Jedes Feld ist so breit wie sein Wertebereich — *Position X* für eine
    Million, *Richtung X* für eins —, und damit standen die *fx*-Knöpfe
    daneben in jeder Zeile an einer anderen Stelle. Gleich breit bilden
    Felder und Knöpfe je eine Kante; breiter als der größte Wert darunter
    wird dabei keines (``panels.even_fields`` ist dieselbe Abwägung für die
    Druckeinstellungen). Operationsdialog und Organizer fragen hier.
    """
    spins = [field.spin for field in fields]
    if len(spins) < 2:
        return
    common = max(spin.minimumWidth() for spin in spins)
    for spin in spins:
        spin.setMinimumWidth(common)
        spin.setMaximumWidth(common + NUMBER_AIR)


class OperationDialog(QDialog):
    """Ein Dialog für eine Operation, gebaut aus ihrem Schema."""

    valuesChanged = Signal()
    """Ein Wert hat sich geändert — die Live-Vorschau (§18.7) hört zu."""

    schemaChanged = Signal()
    """Ein Variantenwechsel hat auch die Skizzen- und Quelleneditoren erneuert."""

    surfaceRequested = Signal()
    """Die Werte bleiben im Dialog, die Position wird auf dem Modell gewählt."""

    attachmentRequested = Signal(bool)
    """Freie Lage oder die ausdrücklich angebotene Fläche wählen."""

    values_stand_elsewhere = False
    """Sie stehen hier — deshalb trägt die Platzierung ihre eigene Leiste.

    Der Gegenpart ist `placement_flow.QuietHost`: Am gewählten Merkmal stehen
    die Werte rechts im Merkmalfenster, und die Leiste unten wäre die zweite
    Stelle mit demselben Übernehmen."""

    spoolChosen = Signal(object)
    """Eine örtliche Spulenwahl reist separat, niemals als Operationsparameter."""

    manualRequested = Signal(str, str)
    """F1: Seite und Stelle des Handbuchs, die diese Operation erklären
    (``manual.help_for``). Das Fenster, das den Dialog öffnet, schlägt sie auf."""

    pointsPickRequested = Signal()
    """*Im Bild wählen* an den drei Punkten: Das Fenster nimmt die nächsten Klicks an."""

    placement_flow: PlacementFlow | None = None
    seal_flow: SealFlow | None = None
    preview_required = False
    requires_displayed_preview = False
    preview_order: Callable[[], Any] | None = None
    preview_check: Callable[[], bool] | None = None
    preview_defer: Callable[[], None] | None = None
    """Ein Klick vor der Vorschau wartet auf sie — das Fenster hängt ihn hier ein.

    ``preview_check`` fragt nur; dieser Haken bindet. Getrennt, weil die Frage
    an vielen Stellen gestellt wird und nur ein Klick auf *Übernehmen* ein
    Klick ist (Entscheidung Robert, 21.09.2026: der Klick verfällt nicht)."""

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
        pick_image: Callable[[], tuple[str, str] | None] | DeferredSourcePicker | None = None,
        pick_source: Callable[[], tuple[str, str] | None] | DeferredSourcePicker | None = None,
        note: str = "",
        slots: Sequence[Any] = (),
        target_features: Mapping[str, str] | None = None,
        source_objects: Sequence[str] = (),
        edges: Mapping[str, str] | None = None,
        offer_naming: bool = False,
        naming_default: bool = False,
        centre_objects: Sequence[SceneObject] = (),
        promote_values: bool = True,
    ) -> None:
        """``extra`` hängt ein Widget des Aufrufers unter „Weitere
        Einstellungen" — die zusammengelegten Menü-Zwillinge tragen dort
        ihren „Exakt"-Umschalter, ohne dass der Dialog seine Generik aus
        dem Schema verliert.

        ``offer_naming`` hängt vorn den Haken *Maße als Parameter anlegen* an (§13):
        Gesetzt, legt das Fenster jedes Millimetermaß der Vorderseite als
        Projektparameter an und lässt den Schritt darauf verweisen.
        :meth:`names_dimensions` liest ihn. Der Dialog bietet ihn nur an, wo
        das Fenster es verlangt — bei den Grundkörpern, deren Maße eine
        Vorlage ausmachen, nicht bei einer Bohrung, die ein Maß *am* Körper
        ist. ``naming_default`` ist sein Anfangszustand — das Fenster reicht
        die letzte Wahl des Kunden durch (RM-369).

        ``promote_values=False`` behält beim Wiederöffnen die Schemaplätze:
        gespeicherte Werte und Ausdrücke sind keine neue Vorbelegung.

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
        self._promote_values = promote_values
        self._height = ContentHeight()
        self.setWindowTitle(str(spec.title))
        self.setMinimumWidth(380)
        # Das F1 des Hauptfensters kommt in einem eigenen Fenster nicht an:
        # Gemessen löste es im offenen Dialog nichts aus (Konzept Handbuch §1.2).
        QShortcut(QKeySequence(QKeySequence.StandardKey.HelpContents), self, self._ask_manual)
        self._editors: dict[str, QWidget] = {}
        self._feature_focus = ""
        self._first_focus_given = False
        self.source_objects = tuple(source_objects)
        self._centre_objects = tuple(centre_objects)
        self._centre_row: QWidget | None = None
        self.centre_mode: QComboBox | None = None
        self.centre_target: QComboBox | None = None
        self._target_features = dict(target_features or {})
        self._couplings: list[Callable[[], None]] = []
        self._variant_values: dict[str, dict[str, Any]] = {}
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
        # **Umgeleitet wird nur dort, wo die Liste das führende Feld ist.**
        # Erkennbar an ihrer Seite im Dialog: Bei ``clear_filament`` steht
        # ``at_features`` vorn und ``at_feature`` ist der alte, nur noch
        # lesbare Einzelwert — dort gehört er in die Liste. Seit die Bausteine
        # ``at_features`` als Erweiterung tragen (E7, 09.09.2026), steht sie
        # dort hinten, und das Einzelfeld ist der übliche Weg: Wer eine Bohrung
        # anklickt, bekam sonst ein leeres *An Merkmal* und mit ihm die
        # Größenberatung nicht, die daran hängt.
        if any(
            entry.kind == "features" and entry.name == "at_features" and entry.placement == "front"
            for entry in spec.params.spec()
        ):
            selected = list(given.get("at_features") or ())
            if given.get("at_feature"):
                selected.append(given["at_feature"])
            given["at_features"] = list(dict.fromkeys(selected))
            given["at_feature"] = ""
        # Der Dialog spricht in Namen, das Dokument in Kennungen. Wer nur eine
        # Liste übergibt, bekommt die Kennungen zu sehen.
        names = dict(objects) if isinstance(objects, Mapping) else {key: key for key in objects}
        self._object_names = names
        # Quellen sind keine Objekte. Sie standen hier trotzdem in derselben
        # Liste — wer „Modell laden" im Verlauf wieder öffnete, bekam eine
        # Auswahl aus Körpern angeboten, wo eine Datei gemeint war.
        self._sources = dict(sources or {})
        self._features = dict(features or {})
        """Die erkannten Merkmale des gewählten Körpers, Kennung auf
        Beschriftung — dieselbe, die im Objektbaum und über dem Modell steht."""
        self._edges = dict(edges or {})
        """Die einzeln wählbaren Kanten eines exakten Körpers (E4): Schlüssel
        auf Beschriftung. Leer bei einem Netz — dort gibt es keine Kanten, die
        eine zweite Auswertung überlebten."""
        self._images = dict(images or {})
        """Nur die Bildquellen des Projekts — das Feld „Bild" listet keine
        Netze (§25, ``displace_image``)."""
        self._pick_image = pick_image
        """Holt ein Bild von der Platte ins Projekt und gibt (Kennung, Name)
        zurück — der Weg, den ein leeres Projekt braucht."""
        self._pick_source = pick_source
        """Dasselbe für eine Modelldatei. Ohne ihn ist das Quellenfeld in
        *Modell laden*, *STEP laden* und *Zeichnung hochziehen* eine leere
        Liste, aus der kein Weg führt."""
        self._bones = armature_bones(str(given.get("armature") or ""))
        """Die Knochen, an denen die Stellung hängt — aus dem Skelett, das der
        Editor gerade gesetzt hat, oder aus dem Wert einer wieder geöffneten
        Operation. Ohne sie hat ein Stellungsraster keine Zeilen."""

        front = QFormLayout()
        advanced = QFormLayout()
        # **Eine Beschriftungsspalte, keine Zeile darüber.** Mit
        # ``WrapLongRows`` entschied jede Zeile selbst, ob ihr Feld neben oder
        # unter die Beschriftung kommt: Im Bohrdialog standen *Position X* bis
        # *Z* über ihren Feldern, *Richtung X* bis *Z* daneben — derselbe
        # Dialog in zwei Formen. Nicht umbrechen, und das Fenster so breit wie
        # sein breitestes Formular (``_resize_to_content``).
        #
        # Die Rückseite ohne eigenen Rand: Qts Vorgabe rückte sie um neun
        # Punkte ein, und ihre Felder begannen neben denen der Vorderseite
        # an einer zweiten Kante, obwohl ``align_forms`` die Beschriftungen
        # gleich breit macht.
        for form in (front, advanced):
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        advanced.setContentsMargins(0, 0, 0, 0)
        self._front = front
        self._advanced_form = advanced
        self._rows: dict[str, QFormLayout] = {}
        """Welches Formular das Feld trägt; ein Variantenwechsel ersetzt sein Schema."""
        promoted = _promoted_fields(spec, given) if self._promote_values else frozenset()
        for entry in spec.params.spec():
            if spec.name == "create_seal" and entry.name in _SEAL_PATH_COMPANIONS:
                continue
            editor = self._editor_for(entry, names, given.get(entry.name))
            if isinstance(editor, SealPathField):
                editor.set_selection(given)
            self._editors[entry.name] = editor
            self._watch(editor)
            if entry.kind in ("feature", "features") or entry.targets_feature:
                editor.installEventFilter(self)
            # **Ohne Einheit in der Klammer** (B12): Sie steht am Wert, wo sie
            # mit der Umschaltung geht — ``ValueField`` setzt sie als Suffix.
            label = f"{entry.title}"
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
            #
            # **Und eine Richtung ist keine Entscheidung, die man nachbessert.**
            # Der Klick auf eine Fläche trägt ihre Normale ein — drei Zahlen,
            # von denen nur die ungleich null „entschieden" aussah: An der
            # Oberseite stand *Normale Z* vorn, an der linken Seite *Achse*
            # und *Normale X*, und der meistbenutzte Dialog sah bei jeder
            # Bohrung anders aus (Durchsicht 14.09.2026). Eine Komponente
            # eines Vektors tippt niemand von Hand, und ihre zwei Geschwister
            # blieben hinten. Richtung und Achse bleiben, wo das Schema sie
            # hinlegt; der Wert gilt trotzdem.
            decided = entry.name in promoted
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
            if isinstance(editor, RowCheckBox):
                caption_toggles(target.labelForField(editor), editor)
            if isinstance(editor, ValueField) and editor.circle_toggle is not None:
                caption = target.labelForField(editor)
                if isinstance(caption, QLabel):
                    caption.setText(editor.caption())
                    editor.captionChanged.connect(caption.setText)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        outer.setSpacing(NORMAL)
        self._scroll = DialogScrollArea(self)
        contents = QWidget(self._scroll)
        layout = QVBoxLayout(contents)
        layout.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(contents)
        outer.addWidget(self._scroll, 1)
        # **Wer im Bild zielen muss, erfährt es im Dialog — als erste Zeile**
        # (Befund Robert, 18.09.2026: „keine Info dass es über den Viewport
        # geht"; RM-513: sie war die blasseste Zeile, unter allem anderen).
        # Die Platzierung startet bei diesen Operationen von selbst und
        # schreibt ihren Satz in eine Leiste am Viewport; der Dialog bleibt
        # daneben stehen. In normaler Schrift, denn sie ist die Anweisung.
        #
        # **Sichtbar erst, wenn die Platzierung wirklich läuft.** Ob sie das
        # tut, weiß allein der Fluss (:meth:`show_placement_hint`): Er startet
        # nicht beim **Ändern** eines Schritts und nicht ohne setzbaren Körper,
        # und ein Dialog, der zum Klicken auffordert, während nichts zu klicken
        # ist, ist schlechter als keiner (gemessen 18.09.2026).
        placed = QLabel(placement_hint(), self)
        placed.setWordWrap(True)
        placed.setVisible(False)
        self._placement_hint = placed
        layout.addWidget(placed)

        self._description: QLabel | None = None
        if spec.doc:
            description = QLabel(lead_sentence(spec), self)
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
            self._describe_fully(spec)

        # **Die Grenze steht zugeklappt unter dem Satz** (RM-513). Offen trug
        # sie bis zu sechzig Wörter vor das erste Feld; das Handbuch und die
        # Kurzhilfe der Überschrift nennen sie ganz. Die Überschrift „Wann
        # nicht?“ ist die Kodierung, die vorher die halbfette Schrift trug
        # (Regel 18), und ``remember`` hält, ob der Kunde sie offen haben will.
        # Immer gebaut, sichtbar nur mit Inhalt: Ein Variantenwechsel *zu*
        # einer Grenze hin hätte sonst nichts, woran er sie schreiben könnte.
        caveat = QLabel(str(spec.caveat or ""), self)
        caveat.setWordWrap(True)
        self._caveat = caveat
        self._caveat_section = collapsible(
            tr("Wann nicht?"), caveat, open_now=False, remember="op_dialog.caveat"
        )
        self._caveat_section.setParent(self)
        layout.addWidget(self._caveat_section)
        self._show_caveat(spec)

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
        # **Wohin ein neuer Körper kommt, steht vorn** (RM-390). Ein Erzeuger
        # setzt sich auf eine ausdrücklich gewählte Fläche; ihre Lage steht
        # in Position und Richtung hinter der Klappe, und ohne diesen Satz
        # entstand er an einer Stelle, die der Kunde nicht gewählt zu haben
        # glaubte. *Auf das Bett* nimmt die Vorbelegung zurück. Sichtbar nur,
        # wenn das Fenster es sagt (:meth:`show_seat`).
        self._seat_note = QLabel("", self)
        self._seat_note.setWordWrap(True)
        set_level(self._seat_note, "caption")
        self._seat_note.setVisible(False)
        layout.addWidget(self._seat_note)
        self._seat_back: dict[str, Any] | None = None
        self.attachment_mode: QComboBox | None = None
        self.join_attachment: RowCheckBox | None = None
        self.to_the_bed = QPushButton(tr("Auf das Bett"), self)
        bed_note = tr("Nimmt die gewählte Fläche zurück — der Körper entsteht auf dem Bett.")
        self.to_the_bed.setToolTip(bed_note)
        self.to_the_bed.setAccessibleDescription(bed_note)
        self.to_the_bed.setAutoDefault(False)
        self.to_the_bed.setVisible(False)
        self.to_the_bed.clicked.connect(weak_slot(self, OperationDialog._to_the_bed))
        bed_row = QHBoxLayout()
        bed_row.setContentsMargins(0, 0, 0, 0)
        bed_row.addWidget(self.to_the_bed)
        bed_row.addStretch(1)
        layout.addLayout(bed_row)
        self._attachment_row = bed_row
        # **Und der Weg zurück ins Bild** (RM-205). Escape in der Platzierung
        # bringt den Dialog zurück und behält die Werte — aber von hier
        # führte nichts mehr zurück in die erste Stufe: ``surfaceRequested``
        # hatte keinen Sender, seit der Knopf *Im Modell platzieren* am
        # 11.09.2026 fiel. Wer nach dem Nachbessern des Durchmessers neu
        # zielen wollte, musste den Dialog schließen und von vorn beginnen.
        # Der Knopf erscheint nur, wo schon gezielt wurde: Dann ist die
        # Platzierung für diese Operation möglich, und der Kunde kennt sie.
        # Mit der Maus geht es auch ohne ihn — ein Klick ins Modell holt die
        # Platzierung zurück und setzt dort die Stelle
        # (``PlacementFlow._resume``); der Knopf ist der Weg für die Tastatur.
        self.aim_again = QPushButton(tr("Stelle im Bild wählen"), self)
        aim_note = tr("Zurück ins Bild und die Stelle am Modell neu wählen. Die Werte bleiben.")
        self.aim_again.setToolTip(aim_note)
        self.aim_again.setAccessibleDescription(aim_note)
        self.aim_again.setVisible(False)
        self.aim_again.clicked.connect(self.surfaceRequested)
        # **Die gewählte Stelle als Lesezeile vorn** (Entscheidung Robert,
        # RM-513): „Stelle: Oberseite · 12,00 / 8,50 / 20,00 mm“ statt dreier
        # Koordinatenfelder. Die Zahlen bleiben hinten bearbeitbar; der Knopf
        # zurück ins Bild steht in derselben Zeile. Wo die Operation keine
        # solche Stelle führt, steht er allein wie bisher.
        self._place = place_fields(spec)
        self._place_known = self._place is not None and any(name in given for name in self._place)
        self._aligned = False
        """Ob die Beschriftungskante schon steht — vorher richtet die Stelle nichts neu aus."""
        self._place_row = QWidget(self)
        place_layout = QHBoxLayout(self._place_row)
        place_layout.setContentsMargins(0, 0, 0, 0)
        place_layout.setSpacing(SPACE)
        self._place_label = QLabel("", self._place_row)
        self._place_label.setWordWrap(True)
        self._place_label.setAccessibleName(tr("Stelle"))
        place_layout.addWidget(self._place_label, 1)
        place_layout.addWidget(self.aim_again)
        front.insertRow(0, tr("Stelle"), self._place_row)
        place_caption = front.labelForField(self._place_row)
        place_note = tr(
            "Wo die Operation ansetzt. Die Zahlen stehen unter „Weitere Einstellungen“."
        )
        self._place_label.setToolTip(place_note)
        if place_caption is not None:
            place_caption.setToolTip(place_note)
        self._filament_notice = ErrorNotice(self)
        self._filament_notice.hide()
        layout.addWidget(self._filament_notice)
        layout.addLayout(front)
        # **Die Absage der Vorschau mit ihren Knöpfen, direkt unter den Feldern**
        # (RESTVERLAUF-04). Das Band über dem Bild trägt den Satz, aber es nimmt
        # keinen Klick an; die Handlung, die hilft — die kleinste Kantenlänge,
        # die noch geht, oder erst verringern —, stand bis zur Durchsicht 0.5.1
        # erst drei Klicks später im Prüfbericht, nach einem angehaltenen
        # Schritt. Sichtbar nur mit einer Handlung, die dieser Dialog einlöst
        # (:meth:`show_refusal`).
        self._refusal = ErrorNotice(self)
        self._refusal.hide()
        layout.addWidget(self._refusal)
        self._naming: RowCheckBox | None = None
        if offer_naming:
            # **Weg 2 legt Maße an, keine Zahlen** (§13): Ein Quader, dessen
            # Breite ein Projektparameter ist, bleibt eine Vorlage — die
            # Parameterleiste dreht das Maß, ohne den Schritt zu öffnen. Bis
            # hierher konnte das nur der Agent; der Kunde musste den Parameter
            # in der Leiste anlegen und danach „=@breite" in das Feld tippen,
            # zwei Dinge, von denen ein Neuling keines kennt. Der Haken steht
            # vorn, direkt unter den Maßen, die er benennt (Entscheidung
            # Robert, 14.09.2026).
            naming = RowCheckBox(self)
            naming.setChecked(naming_default)
            front.addRow(str(tr("Maße als Parameter anlegen")), naming)
            caption = front.labelForField(naming)
            caption_toggles(caption, naming)
            _explain(
                naming,
                caption,
                str(
                    tr(
                        "Legt jedes Maß von vorn als Projektparameter an. Danach ändert die "
                        "Parameterleiste die Zahl, und weitere Schritte können sich auf sie "
                        "beziehen."
                    )
                ),
            )
            self._naming = naming
            naming.toggled.connect(self.valuesChanged)

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
        self._hidden_expression_controller = ""
        self._hidden_expression_notice = QLabel(self)
        self._hidden_expression_notice.setWordWrap(True)
        set_level(self._hidden_expression_notice, "caption")
        self._hidden_expression_notice.setVisible(False)
        self._hidden_expression_open = QPushButton(tr("Einstellung anzeigen"), self)
        self._hidden_expression_open.setAutoDefault(False)
        self._hidden_expression_open.setVisible(False)
        self._hidden_expression_open.clicked.connect(
            weak_slot(self, OperationDialog._open_hidden_expression_controller)
        )
        hidden_expression_row = QHBoxLayout()
        hidden_expression_row.setContentsMargins(0, 0, 0, 0)
        hidden_expression_row.addWidget(self._hidden_expression_notice, 1)
        hidden_expression_row.addWidget(self._hidden_expression_open)
        layout.addLayout(hidden_expression_row)
        self._advanced_summary: QLabel | None = None
        self._advanced_section: QWidget | None = None
        if advanced.rowCount() or extra is not None:
            # **Dieselbe Klappe wie in jedem anderen Dialog** (``panels.collapsible``,
            # RM-513): flache Überschrift mit Linie, und zugeklappt nennt sie die
            # ersten Felder dahinter. Die eigene Bauart davor sagte nicht, was
            # hinter ihr liegt, und wer *Befestigung* suchte, fand sie nicht.
            inner = QWidget(self)
            inner.setLayout(advanced)
            section = collapsible(
                tr("Weitere Einstellungen"),
                inner,
                open_now=False,
                contents=advanced_summary(self._advanced_titles()),
            )
            section.setParent(self)
            self._advanced_section = section
            heading = next(
                child
                for child in section.findChildren(QToolButton)
                if child.objectName() == "sectionHeading"
            )
            self.advanced = heading
            self._advanced_summary = next(
                (
                    child
                    for child in section.findChildren(QLabel)
                    if child.objectName() == "sectionSummary"
                ),
                None,
            )
            # **Keine geschachtelte Funktion, die ``self`` fängt.** Sie ist
            # dasselbe wie ein Lambda: ihre Zelle hält den Dialog, der Sender
            # ist sein eigener Knopf, und der Ring über die C++-Grenze steht.
            # Gemessen am 23.08.2026: zehn losgelassene ``OperationDialog``
            # überlebten alle zehn, und ``gc.get_referrers`` nannte genau diese
            # Zelle.
            #
            # ``pressed`` kommt vor dem Zuklappen: Steht der Fokus in einem Feld
            # dahinter, geht er an die Überschrift statt an den nächsten Knopf.
            heading.pressed.connect(
                weak_slot(self, OperationDialog._before_folding, inner, forward=False)
            )
            heading.toggled.connect(
                weak_slot(self, OperationDialog._advanced_toggled, forward=True)
            )
            layout.addWidget(section)

        # Überschuss erst nach allen Feldern, nicht vor der aufklappbaren Tiefe.
        layout.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        # Der Knopf benennt die Handlung: „Bohrung setzen" statt „OK". Was
        # gleich passiert, steht damit dort, wo entschieden wird — der
        # Fenstertitel ist beim Klicken nicht mehr im Blick. Für die
        # Bausteine gilt das nicht wörtlich: Ihre Titel sind Substantive,
        # und ein Knopf namens „Lochwand-Einhänger" sagt nicht, was der
        # Klick tut. Dort heißt die Handlung „Einsetzen" — den Baustein
        # nennt der Fenstertitel (Robert, 25.08.2026, über 3d-druck-ce).
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._accept_button = ok
        if ok is not None:
            ok.setText(str(tr("Einsetzen")) if spec.category == "parts" else str(spec.title))
            make_primary(ok)
        self._source_fields = tuple(
            editor for editor in self._editors.values() if isinstance(editor, ImageSourceField)
        )
        from app.ui.filament_picker import FilamentField

        self._filament_fields = tuple(
            editor for editor in self._editors.values() if isinstance(editor, FilamentField)
        )
        for field in self._source_fields:
            field.pendingChanged.connect(self._follow_source_pending)
        for filament in self._filament_fields:
            filament.pendingChanged.connect(self._follow_source_pending)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._blocked_reason: str | None = None
        self._attachment_problem: str | None = None
        """Ein Sperrgrund von außen — siehe :meth:`block_apply`."""
        self._refit = QTimer(self)
        """Zieht die Höhe nach, wenn eine Zeile mit ihrer Bedingung kommt oder
        geht — einen Ereignisumlauf später, siehe ``_resize_to_content``."""
        self._refit.setSingleShot(True)
        self._refit_intent: ContentFitIntent = "passive"
        self._refit.timeout.connect(self._run_queued_refit)
        self._couple_dependent_fields()
        self._couple_surface_binding()
        self._install_rotation_centre(given)
        self._link_sketch_planes()
        self._hide_legacy_feature_field()
        self._hide_internal_fields()
        # Auch eine Zeichnung, die erst eine Wahl verlangt (``depends_on``,
        # siehe :meth:`_missing_sketch`): Der Knopf folgt ihr, sobald die Wahl
        # sie zur Eingabe macht. Und ein Pflicht-Ziel: Der Knopf gibt frei,
        # sobald es gewählt ist, nicht erst mit dem nächsten Vorschaubild.
        if self.spec.name == "apply_texture" or any(
            (entry.kind == "material" and entry.required)
            or (entry.targets_feature and entry.required)
            or (entry.kind == "sketch" and (entry.required or entry.depends_on is not None))
            for entry in self.spec.params.spec()
        ):
            self.valuesChanged.connect(self._follow_source_pending)
        self._follow_source_pending()
        # Erst steht fest, ob die Lesezeile *Stelle* dasteht — die Spalte
        # bemisst sich an den Zeilen, die dastehen (RM-518).
        self.valuesChanged.connect(self._refresh_place)
        self._refresh_place()
        # Vorderseite und „Weitere Einstellungen" sind zwei Formulare, und
        # jedes rechnete seine Beschriftungsspalte für sich: Im Bohrdialog
        # begannen die Felder bei 0 und bei 150 Punkten, untereinander im
        # selben Blickfeld (Befund B8).
        self._align_to_the_front()
        self._even_number_fields()
        self._refresh_advanced_summary()

    def _ask_manual(self) -> None:
        """F1: die Stelle im Handbuch zu dieser Operation melden.

        Zur Zeit des Drucks gefragt und nicht beim Bau des Dialogs: Ein
        Variantenwechsel tauscht ``spec`` aus, und die Hilfe gilt der Operation,
        die gerade dasteht.
        """
        page, spot = manual.help_for(self.spec.name)
        self.manualRequested.emit(page, spot)

    def _follow_source_pending(self, _pending: bool = False) -> None:
        """Während des Lesens keine Operation mit einem alten Leerwert anwenden."""

        source_pending = any(field.pending for field in self._source_fields)
        filament_pending = any(field.pending for field in self._filament_fields)
        pending = source_pending or filament_pending
        button = self._accept_button
        incomplete = any(
            isinstance(editor, FeatureSetField) and not editor.valid
            for editor in self._editors.values()
        )
        # Und dieselbe Frage an die Kantenliste (E4): „Einzeln gewählt" ohne
        # ein Kreuz ist ein Knopf, der sicher scheitert — der Kern sagt dann
        # „für diese Auswahl ist noch keine Kante benannt", und das ist ein
        # Satz zu spät.
        no_edge = any(
            isinstance(editor, EdgeSetField) and not editor.valid
            for editor in self._editors.values()
        )
        no_contour = any(
            isinstance(editor, ContourField) and not editor.valid
            for editor in self._editors.values()
        )
        no_layout = any(
            isinstance(editor, OrganizerLayoutField) and not editor.valid
            for editor in self._editors.values()
        )
        no_seal = any(
            isinstance(editor, SealPathField) and not editor.valid
            for editor in self._editors.values()
        )
        no_count, hidden_controller = self._field_refusal_details()
        self._hidden_expression_controller = hidden_controller
        self._hidden_expression_notice.setText(no_count if hidden_controller else "")
        self._hidden_expression_notice.setVisible(bool(hidden_controller))
        self._hidden_expression_open.setVisible(bool(hidden_controller))
        if hidden_controller:
            controller = next(
                entry for entry in self.spec.params.spec() if entry.name == hidden_controller
            )
            access = str(tr("Zum Feld „{name}“ gehen, das den Ausdruck einblendet.")).format(
                name=controller.title
            )
            self._hidden_expression_open.setToolTip(access)
            self._hidden_expression_open.setAccessibleDescription(access)
        else:
            self._hidden_expression_open.setToolTip("")
            self._hidden_expression_open.setAccessibleDescription("")
        missing_sketch = self._missing_sketch()
        missing_material = self._missing_material()
        # Und ein Pflicht-Ziel ohne Eintrag (Bedienweg-Durchsicht 14.09.2026):
        # *An Merkmal ausrichten* am einzigen Körper hat keinen zweiten, dessen
        # Merkmal es anpeilen könnte — die Liste ist leer, und „Übernehmen"
        # führte sicher in den Formatfehler des Kerns („obj_2:hole_1"). Das
        # Fenster sagt es vorher am Knopf (``_NEEDS_TARGET``); hier steht
        # dieselbe Auskunft für den Weg über Palette und Kürzel.
        no_target = self._target_missing()
        no_texture_face = self._texture_face_missing()
        # Und was das Fenster von außen sperrt: Ein Grund aus dem Band, der
        # eine Handlung trägt („Erst reparieren, dann aushöhlen"), sperrt den
        # Knopf, statt drei Schritte später im Prüfbericht zu enden
        # (:meth:`block_apply`, gerufen aus ``MainWindow._preview_explained``).
        blocked = self._attachment_problem or self._blocked_reason
        reason = (
            tr("Datei wird gelesen …")
            if source_pending
            else (
                tr("Das Filamentlager wird gespeichert …")
                if filament_pending
                else (tr("Flächen markieren oder den ganzen Körper wählen.") if incomplete else "")
            )
            or (tr("Kreuzen Sie mindestens eine Kante an.") if no_edge else "")
            or (tr("Wählen Sie mindestens eine gültige Kontur.") if no_contour else "")
            or (tr("Öffnen Sie die Fachaufteilung und prüfen Sie ihre Maße.") if no_layout else "")
            or (tr("Wählen oder zeichnen Sie einen geschlossenen Dichtweg.") if no_seal else "")
            or no_count
            or missing_sketch
            or missing_material
            or (self._target_reason() if no_target else "")
            or (tr("Wählen Sie eine ebene Fläche für das Muster.") if no_texture_face else "")
            or (blocked or "")
        )
        incomplete = (
            incomplete
            or no_edge
            or no_contour
            or no_layout
            or no_seal
            or bool(no_count)
            or bool(missing_sketch)
            or bool(missing_material)
            or no_target
            or no_texture_face
            or blocked is not None
        )
        button.setEnabled(not pending and not incomplete)
        button.setToolTip(reason)
        button.setAccessibleDescription(reason)

    def _field_refusal(self) -> str:
        """Warum ein Zahlenfeld gerade nichts übernimmt — die eine Quelle für Knopf und Klick.

        Eine Stückzahl, die keine ganze Zahl im Bereich ergibt, und jede Zahl
        oder jeder Ausdruck jenseits der Grenzen (:meth:`ValueField.refusal`),
        auch an der Stückzahl. Knopfzustand (:meth:`_follow_source_pending`)
        und :meth:`can_accept` fragten das getrennt: Eine Stückzahl über der
        Grenze ließ den Knopf aktiv, und der Klick bewirkte nichts
        (Code-Review 0.5.1, U-2).

        Eine ausgeblendete abgelehnte Zahl zählt nicht: ``value()`` liefert
        weiter den letzten gültigen Modellwert, und beim Einblenden bleibt der
        Tipp stehen (``labels._BoundedBehavior.hideEvent``). Ein fx-Ausdruck
        zählt auch im ausgeblendeten Feld: ``values()`` reicht ihn an den Kern,
        der seine Grenze weiter prüft. Der Dialog hält ihn deshalb fest und
        zeigt den Weg zu der Wahl, die das Feld einblendet.
        """
        return self._field_refusal_details()[0]

    def _field_refusal_details(self) -> tuple[str, str]:
        """Liefert Ablehnung und sichtbaren Rückweg für ein verborgenes fx-Feld."""
        schema = self.spec.params.spec()
        entries = {entry.name: entry for entry in schema}
        entered: Mapping[str, Any] | None = None
        for name, editor in self._editors.items():
            if not isinstance(editor, ValueField):
                continue
            hidden = editor.isHidden()
            if hidden and not editor.toggle.isChecked():
                continue
            said = editor.refusal()
            if not said and isinstance(editor, CountField) and not editor.valid:
                said = editor.problem()
            if said:
                if (
                    hidden
                    and editor.toggle.isChecked()
                    and (entry := entries.get(name)) is not None
                ):
                    if entered is None:
                        entered = self.values()
                    inactive = inactive_dependency(entry, schema, entered)
                    seen_controllers: set[str] = set()
                    while inactive is not None:
                        controller_name, wanted = inactive
                        if controller_name in seen_controllers:
                            break
                        seen_controllers.add(controller_name)
                        controller = entries.get(controller_name)
                        controller_editor = self._editors.get(controller_name)
                        if controller is not None and controller_editor is not None:
                            if controller_editor.isHidden():
                                inactive = inactive_dependency(controller, schema, entered)
                                continue
                            condition = _why_inactive(str(controller.title), wanted[0])
                            notice = str(
                                tr(
                                    "{name}: {problem} {condition} Ändern Sie die genannte "
                                    "Einstellung, um den Ausdruck zu korrigieren."
                                )
                            ).format(name=entry.title, problem=said, condition=condition)
                            return notice, controller_name
                        break
                # Mit dem Feld davor, wie am Knopf *Slicen* (RM-342, D-N2): Der
                # Satz steht am Übernehmen-Knopf, weit weg vom Feld.
                title = entry.title if (entry := entries.get(name)) is not None else name
                return str(tr("{name}: {value}", name=str(title), value=said)), ""
        return "", ""

    def _open_hidden_expression_controller(self) -> None:
        """Bringt den Fokus zur sichtbaren Wahl, die das fx-Feld einblendet."""
        if self._hidden_expression_controller:
            self.focus_field(self._hidden_expression_controller)

    def can_accept(self) -> bool:
        """Alle Eingaben und die Freigabe derselben Vorschau erneut prüfen."""
        if self._attachment_problem is not None:
            return False
        for editor in (*self.findChildren(QSpinBox), *self.findChildren(QDoubleSpinBox)):
            editor.interpretText()
        if any(field.pending for field in self._source_fields) or any(
            filament.pending for filament in self._filament_fields
        ):
            return False
        if any(
            isinstance(
                editor,
                (
                    FeatureSetField,
                    EdgeSetField,
                    ContourField,
                    OrganizerLayoutField,
                    SealPathField,
                    CountField,
                ),
            )
            and not editor.valid
            for editor in self._editors.values()
        ):
            return False
        if self._field_refusal():
            return False
        preview_ready = self.preview_check is None or self.preview_check()
        return not (
            self._target_missing()
            or self._missing_sketch()
            or self._missing_material()
            or self._texture_face_missing()
            or self._blocked_reason is not None
            or not preview_ready
        )

    def accept(self) -> None:
        """Erst anwenden, wenn jede nachgereichte Quelle wirklich feststeht.

        Steht die Vorschau noch aus, verfällt der Klick nicht: ``preview_defer``
        hängt ihn an die erwartete Freigabe, und er läuft, sobald das Bild
        steht (``MainWindow._apply_when_previewed``).
        """
        if not self.can_accept():
            if self.preview_defer is not None:
                self.preview_defer()
            return
        super().accept()

    def _missing_sketch(self) -> str:
        """Den Pflichtbereich nennen, bevor eine leere Zeichnung übernommen wird.

        **Auch eine Zeichnung, die eine Wahl erst verlangt** (RM-183): Die Bahn
        eines Sweeps ist nicht immer Pflicht, aber sobald „gezeichnete Bahn"
        gewählt ist, ist sie die Eingabe (``depends_on``). Leer ließ sich der
        Dialog trotzdem übernehmen, und die Absage kam als Befund im
        Prüfbericht, nachdem alles fertig war. Jetzt nennt der gesperrte Knopf,
        was fehlt.
        """
        from app.ui.sketch_editor import SketchField

        schema = self.spec.params.spec()
        wanted = [
            entry
            for entry in schema
            if entry.kind == "sketch" and (entry.required or entry.depends_on is not None)
        ]
        if not wanted:
            return ""
        values = self.values()
        for entry in wanted:
            if inactive_dependency(entry, schema, values) is not None:
                continue
            editor = self._editors.get(entry.name)
            if not isinstance(editor, SketchField):
                continue
            if not (editor.ready if entry.required else editor.has_drawing):
                return tr("{name}: {value}", name=entry.title, value=editor.summary.text())
        return ""

    def _missing_material(self) -> str:
        """Zusätzliche Materialrollen brauchen ihre eigene ausdrückliche Wahl."""
        schema = self.spec.params.spec()
        required = [entry for entry in schema if entry.kind == "material" and entry.required]
        if not required:
            return ""
        values = self.values()
        for entry in required:
            if inactive_dependency(entry, schema, values) is not None:
                continue
            if not values.get(entry.name):
                return tr("{name}: {value}", name=entry.title, value=tr("Materialprofil wählen …"))
        return ""

    def _texture_face_missing(self) -> bool:
        """Ein Ganzflächenmuster braucht eine ausdrücklich gewählte Fläche."""
        if self.spec.name != "apply_texture":
            return False
        entered = self.values()
        return entered.get("coverage") == "whole_face" and not entered.get("face")

    def show_placement_hint(self, on: bool, *, paused: bool = False) -> None:
        """Den Satz „Stelle im Bild anklicken.“ zeigen oder wegnehmen.

        Gerufen vom :class:`~app.ui.placement_flow.PlacementFlow`, wenn er
        anfängt und wenn er aufhört. Er ist die einzige Stelle, die es weiß:
        Das Register sagt, ob eine Operation platziert *werden kann*, nicht ob
        sie es gerade *tut*.

        Der Fluss meldet eine Pause ausdrücklich: Dann bleibt der Tastaturweg
        zurück ins Bild sichtbar (RM-205), zusammen mit dem Hinweis, wenn
        auch ein Modellklick zurückführt. Beim aktiven Zielen und nach dem
        endgültigen Ende gibt es keinen Rückkehrknopf.
        """
        self._placement_hint.setVisible(bool(on))
        self.aim_again.setVisible(paused)
        self._refresh_place()

    def _refresh_place(self) -> None:
        """Die Lesezeile *Stelle* nach den Werten, die gerade gelten.

        Sichtbar, sobald eine Stelle gewählt ist — oder solange der Knopf
        zurück ins Bild in ihr steht. Leere Koordinaten (``optional``: „bleibt,
        wo sie ist“) nennen nur das Merkmal.
        """
        aiming_back = not self.aim_again.isHidden()
        text = ""
        if self._place is not None and self._place_known:
            values = self.values()
            point = [
                float(coordinate)
                for name in self._place
                if isinstance(coordinate := values.get(name), int | float)
            ]
            face = self._place_face(values)
            if len(point) < len(self._place):
                text = face or tr("wie gemessen")
            else:
                text = place_text(face, point)
        elif self._place is not None and aiming_back:
            text = tr("noch nicht gewählt")
        if text != self._place_label.text():
            self._place_label.setText(text)
            self._place_label.setAccessibleDescription(text)
        self._place_label.setVisible(bool(text))
        shown = bool(text) or aiming_back
        if shown != self._front.isRowVisible(self._place_row):
            self._front.setRowVisible(self._place_row, shown)
            # Die Lesezeile ist keine bedingte Eingabe, die umbrechen soll:
            # Erscheint sie, gehört ihre Beschriftung zur Spalte („Emplacement“
            # ist breiter als „Nom“), verschwindet sie, gibt sie die Breite frei.
            if self._aligned:
                self._align_to_the_front()
            if self.isVisible():
                self._queue_refit("passive")

    def _place_face(self, values: Mapping[str, Any]) -> str:
        """Woran die Stelle liegt: das gewählte Merkmal, sonst die Seite ihrer Richtung."""
        from app.core.knowledge.parts.ops import placement_fields
        from app.core.scene.placement import side_of

        placed = placement_fields(self.spec.params)
        for name in (placed.get("at_feature", "at_feature"), "at_feature"):
            chosen = values.get(name)
            if isinstance(chosen, str) and chosen:
                return self._features.get(chosen, chosen)
        normal = [
            float(part)
            for name in normal_fields_of(self.spec)
            if isinstance(part := values.get(name), int | float)
        ]
        if len(normal) == 3 and any(abs(part) > EPS_GEOM for part in normal):
            _key, side = side_of((normal[0], normal[1], normal[2]))
            return str(side)
        return ""

    def _describe_fully(self, spec: OperationSpec) -> None:
        """Die ganze Beschreibung an die eine Zeile: Kurzhilfe und Vorleser."""
        if self._description is None:
            return
        whole = str(spec.doc or "")
        self._description.setToolTip(whole if whole.strip() != lead_sentence(spec) else "")
        self._description.setAccessibleDescription(whole)

    def _show_caveat(self, spec: OperationSpec) -> None:
        """Die Grenze dieser Operation in ihre Klappe — oder die Klappe weg."""
        said = str(spec.caveat or "")
        self._caveat.setText(said)
        self._caveat_section.setVisible(bool(said))
        heading = next(
            (
                child
                for child in self._caveat_section.findChildren(QToolButton)
                if child.objectName() == "sectionHeading"
            ),
            None,
        )
        if heading is not None:
            heading.setToolTip(said)
            heading.setAccessibleDescription(said)

    def offer_attachment(self, target: str) -> None:
        """Die gewählte Fläche und freie Bettlage sind vorn erreichbar."""
        if self.attachment_mode is not None:
            return
        choice = QComboBox(self)
        choice.setAccessibleName(tr("Ansatzpunkt"))
        choice.addItem(tr("Frei auf dem Bett"), False)
        choice.addItem(tr("An {face} ansetzen", face=target), True)
        choice.setCurrentIndex(1)
        choice.setToolTip(tr("Setzt den neuen Körper bündig auf die Mitte der gewählten Fläche."))
        join = RowCheckBox(self)
        join.setText(tr("Verbinden"))
        join.setChecked(True)
        join.setToolTip(
            tr("Fügt den neuen Körper und seinen Träger in einem rücknehmbaren Schritt zusammen.")
        )
        self.attachment_mode = choice
        self.join_attachment = join
        self._attachment_row.insertWidget(0, choice, 1)
        self._attachment_row.insertWidget(1, join)
        self.to_the_bed.hide()
        choice.currentIndexChanged.connect(weak_slot(self, OperationDialog._attachment_changed))
        join.toggled.connect(self.valuesChanged)

    def _attachment_changed(self) -> None:
        active = self.attached_to_surface()
        if self.join_attachment is not None:
            self.join_attachment.setVisible(active)
        self.attachmentRequested.emit(active)
        self.valuesChanged.emit()

    def attached_to_surface(self) -> bool:
        """Ob die vordere Auswahl gerade das Ansetzen verlangt."""
        return self.attachment_mode is not None and bool(self.attachment_mode.currentData())

    def block_attachment(self, reason: str | None) -> None:
        """Eine ausstehende Flächenwahl überlebt die Freigabe einer älteren Vorschau."""
        self._attachment_problem = reason
        self._follow_source_pending()

    def joins_attachment(self) -> bool:
        """Die Vereinigung wird gemeinsam mit dem Erzeuger übernommen."""
        return (
            self.attached_to_surface()
            and self.join_attachment is not None
            and self.join_attachment.isChecked()
        )

    def show_seat(self, sentence: str, back: Mapping[str, Any] | None) -> None:
        """Sagen, auf welche Fläche ein neuer Körper kommt (RM-390).

        ``back`` sind die Werte, die *Auf das Bett* zurückschreibt — die
        Vorgaben der Felder, die die Fläche belegt hat. ``None`` heißt: Der
        Satz erklärt, warum der Körper trotz gewählter Fläche auf dem Bett
        entsteht, und es gibt nichts zurückzunehmen.
        """
        self._seat_back = dict(back) if back is not None else None
        self._seat_note.setText(sentence)
        self._seat_note.setVisible(bool(sentence))
        self.to_the_bed.setVisible(back is not None and self.attachment_mode is None)

    def seated(self) -> bool:
        """Ob der Körper gerade auf der gewählten Fläche steht."""
        return self._seat_back is not None

    def release_seat(self) -> None:
        """Satz und Knopf weg — die Werte bleiben, wie sie stehen.

        Wer Position oder Richtung selbst ändert, hat die Stelle übernommen;
        „Wird auf … gesetzt“ stimmte danach nicht mehr.
        """
        self._seat_back = None
        self._seat_note.setVisible(False)
        self.to_the_bed.setVisible(False)

    def _to_the_bed(self) -> None:
        """*Auf das Bett*: die Vorbelegung der Fläche zurücknehmen."""
        back = self._seat_back
        if back is None:
            return
        self.release_seat()
        self.take_placement(back)

    def show_refusal(
        self,
        problem: object | None,
        handlers: Mapping[str, Callable[[AppError], None]] | None = None,
    ) -> None:
        """Die Absage steht bei den Eingaben, auch ohne örtlichen Zusatzknopf.

        ``handlers`` nennt die Handlungen, die der offene Dialog einlöst.
        Der Rat bleibt auch ohne solche Handlungen sichtbar (§2.7).
        ``None`` nimmt ihn mit der nächsten Vorschau wieder weg.
        """
        if problem is None:
            self._refusal.clear()
            self._refusal.hide()
            return
        self._refusal.set_error(problem, handlers)
        self._refusal.setVisible(bool(self._refusal.text()))

    def take_value(self, name: str, value: Any) -> bool:
        """Einen Wert in ein Zahlenfeld schreiben, als hätte der Kunde ihn getippt.

        Für *Die kleinste Kantenlänge nehmen, die noch geht.*: Die Zahl kommt
        aus der Absage, das Feld meldet die Änderung wie jede Eingabe, und die
        Vorschau rechnet neu. Falsch, wenn das Feld keines für Zahlen ist.
        """
        editor = self._editors.get(name)
        if not isinstance(editor, ValueField):
            return False
        editor.set_value(value)
        return True

    def block_apply(self, reason: str | None) -> None:
        """Den Übernehmen-Knopf von außen sperren — mit Grund — oder freigeben.

        Für das Band über dem Bild: Trägt der Grund einer ausgebliebenen
        Vorschau eine Handlung („Der Körper ist nicht geschlossen — erst
        reparieren, dann aushöhlen"), bleibt der Knopf grau mit diesem Satz
        in Kurzhilfe und zugänglicher Beschreibung (Regel 18),
        bis das nächste Bild ``None`` bringt. Bis zum 14.09.2026 blieb er
        anklickbar; wer klickte, bekam einen angehaltenen Schritt im Verlauf
        und den Knopf drei Klicks später im Prüfbericht (Bedienweg-
        Durchsicht, Absprache mit 3d-druck-66).
        """
        self._blocked_reason = reason
        self._follow_source_pending()

    def _target_missing(self) -> bool:
        """Ob ein Pflicht-Ziel (``targets_feature``) keinen Eintrag hat."""
        for entry in self.spec.params.spec():
            if not (entry.targets_feature and entry.required):
                continue
            editor = self._editors.get(entry.name)
            if isinstance(editor, QComboBox) and not editor.currentData():
                return True
        return False

    def _target_reason(self) -> str:
        """Warum ein leeres Pflicht-Ziel *Übernehmen* sperrt (RM-416).

        Gibt es keinen zweiten Körper mit Merkmalen, fehlt das Ziel wirklich.
        Gibt es ihn, fehlt nur der Klick — dann sagt der Satz, wohin.
        """
        offered = any(
            isinstance(editor, QComboBox)
            and any(editor.itemData(index) for index in range(editor.count()))
            for entry in self.spec.params.spec()
            if entry.targets_feature and entry.required
            for editor in (self._editors.get(entry.name),)
        )
        if not offered:
            return tr("Dafür braucht es ein Merkmal an einem zweiten Körper.")
        names = {self._object_names.get(source, "") for source in self.source_objects}
        if len(names) == 1 and (name := names.pop()):
            return tr("Klicken Sie im Bild auf die Fläche, an die {name} soll.", name=name)
        return tr("Klicken Sie im Bild auf die Fläche, an die der Körper soll.")

    def _focus_first_empty_feature(self) -> None:
        """Der Erstfokus gehört dem ersten leeren Pflichtfeld für ein Merkmal.

        Ohne das gibt Qt beim Anzeigen dem ersten Feld der Kette den Fokus —
        bei *An Merkmal ausrichten* dem schon gefüllten Quellmerkmal —, und
        der erste Bildklick überschrieb dieses statt das leere Ziel zu füllen
        (RM-416). Gilt erst am gezeigten Dialog; ungezeigt füllt
        :meth:`take_feature` ohnehin das erste leere Pflichtfeld.
        """
        for entry in self.spec.params.spec():
            if not entry.required or not (
                entry.kind in ("feature", "features") or entry.targets_feature
            ):
                continue
            editor = self._editors.get(entry.name)
            if editor is None or editor.isHidden() or not self._feature_field_empty(entry.name):
                continue
            editor.setFocus(Qt.FocusReason.OtherFocusReason)
            self._feature_focus = entry.name
            return

    def _hide_internal_fields(self) -> None:
        """Ein Migrationsmarker reist mit dem Schritt, steht aber nicht im
        Dialog (:attr:`app.core.types.ParamSpec.internal`, RM-332 N5)."""
        for entry in self.spec.params.spec():
            editor = self._editors.get(entry.name)
            form = self._rows.get(entry.name)
            if entry.internal and editor is not None and form is not None:
                form.setRowVisible(editor, False)

    def _hide_legacy_feature_field(self) -> None:
        """Alte Einzelwerte reisen über denselben sichtbaren Mehrfachwähler weiter."""
        if isinstance(self._editors.get("at_features"), FeatureSetField):
            legacy = self._editors.get("at_feature")
            if legacy is not None:
                self._rows["at_feature"].setRowVisible(legacy, False)

    def reject(self) -> None:
        """Eine verworfene Operation verwirft auch ihre laufende Dateiaufnahme."""

        for field in self._source_fields:
            field.cancel_pending()
        super().reject()

    def _couple_surface_binding(self) -> None:
        """Kantenabstände gehören zum Flächenbezug; eigene Weltwerte lösen ihn."""
        from app.core.knowledge.parts.ops import placement_fields

        fields = placement_fields(self.spec.params)
        if fields.get("surface_anchor") not in self._editors:
            return
        for name in ("x", "y", "z", "nx", "ny", "nz"):
            editor = self._editors.get(fields[name])
            if isinstance(editor, ValueField):
                editor.changed.connect(weak_slot(self, OperationDialog._release_surface_binding))

        def follow() -> None:
            active = bool(self.values().get(fields["surface_anchor"]))
            for name in ("surface_distance_1", "surface_distance_2"):
                editor = self._editors.get(fields[name])
                if editor is not None:
                    self._rows[fields[name]].setRowVisible(editor, active)
                    editor.setEnabled(active)

        self.valuesChanged.connect(follow)
        self._couplings.append(follow)
        follow()

    def _centre_in_use(self) -> bool:
        """Ob die Drehmitte gerade gilt — die Bedingung ihres Feldes, nicht ein Name.

        Ein lineares Muster und ein gerader Fügeweg drehen nicht; Spiegeln
        braucht seine Mitte immer. Gefragt wird ``cx``, wie das Schema es sagt
        (``ParamSpec.depends_on``).
        """
        from app.core.registry import inactive_dependency

        schema = self.spec.params.spec()
        entry = next(item for item in schema if item.name == "cx")
        return inactive_dependency(entry, schema, self.values()) is None

    def _install_rotation_centre(self, given: Mapping[str, Any]) -> None:
        """Körper, Merkmal und Ursprung werden zu einem gespeicherten Punkt (RM-402)."""
        from app.core.geom.transform import reference_point
        from app.core.perceive.features import centre_of

        if self._centre_row is not None:
            self._front.removeRow(self._centre_row)
            self._centre_row = None
            self.centre_mode = None
            self.centre_target = None
        if not chooses_a_centre(self.spec) or not all(
            name in self._editors for name in ("cx", "cy", "cz")
        ):
            return
        points: dict[str, list[tuple[str, str, tuple[float, float, float]]]] = {
            "body": [],
            "feature": [],
        }
        for body in self._centre_objects:
            points["body"].append((body.id, str(body.name), reference_point([body], "centre")))
            for key, feature in body.features.items():
                if centre_of(feature) is not None:
                    points["feature"].append(
                        (
                            f"{body.id}:{key}",
                            # Auswahlzeile: ohne Maßquelle (RM-513, C16).
                            f"{body.name} · {feature_label(key, feature, compact=True)}",
                            reference_point([body], "feature", key),
                        )
                    )
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        mode = QComboBox(row)
        target = QComboBox(row)
        self._centre_row, self.centre_mode, self.centre_target = row, mode, target
        for title, key in (
            (tr("Körper"), "body"),
            (tr("Merkmal"), "feature"),
            (tr("Punkt"), "point"),
            (tr("Ursprung"), "origin"),
        ):
            if key not in points or points[key]:
                mode.addItem(title, key)
        if given.get("follow_anchor") and not any(
            given.get(name) not in (None, "") for name in ("cx", "cy", "cz")
        ):
            anchor_label = choice_label(str(given.get("about", "centre")))
            label = f"{tr('Bisheriger Bezugspunkt')} · {anchor_label}"
            mode.addItem(label, userData="legacy")
        mode.setAccessibleName(tr("Drehmitte"))
        target.setAccessibleName(tr("Bezug der Drehmitte"))
        note = tr("Die gewählte Mitte wird als fester Punkt gespeichert.")
        for widget in (mode, target):
            widget.setToolTip(note)
            widget.setAccessibleDescription(note)
            wheel_needs_focus(widget)
        layout.addWidget(mode)
        layout.addWidget(target, 1)
        self._front.addRow(tr("Drehmitte"), row)
        # Gespeicherte Ausdrücke und alte Spiegelanker bleiben beim Öffnen unangetastet.
        stored = any(given.get(name) not in (None, "") for name in ("cx", "cy", "cz"))
        default = "point" if stored else "legacy" if given.get("follow_anchor") else "body"
        if default == "body" and not points["body"]:
            default = "point"
        mode.setCurrentIndex(mode.findData(default))

        def follow() -> None:
            active = self._centre_in_use()
            self._front.setRowVisible(row, active)
            for name in ("cx", "cy", "cz"):
                editor = self._editors[name]
                visible = active and mode.currentData() == "point"
                self._rows[name].setRowVisible(editor, visible)
                editor.setEnabled(visible)
            target.setVisible(mode.currentData() in points)
            # Der alte Anker steht lesbar in der Auswahl; sein internes Feld bleibt verborgen.
            legacy = self._editors.get("about")
            if legacy is not None:
                self._rows["about"].setRowVisible(legacy, False)
            self._queue_refit("passive")

        def apply_choice() -> None:
            point = (0.0, 0.0, 0.0) if mode.currentData() == "origin" else target.currentData()
            if mode.currentData() in {"body", "feature", "origin"} and point is not None:
                values = dict(zip(("cx", "cy", "cz"), point, strict=True))
                if "follow_anchor" in self._editors:
                    values["follow_anchor"] = False
                self.take_placement(values)
            elif mode.currentData() == "legacy":
                self.take_placement(
                    {
                        "about": given.get("about", "centre"),
                        "follow_anchor": True,
                        "cx": None,
                        "cy": None,
                        "cz": None,
                    }
                )
            elif mode.currentData() == "point" and "follow_anchor" in self._editors:
                self.take_placement({"follow_anchor": False})
            else:
                self.valuesChanged.emit()

        def choose() -> None:
            with QSignalBlocker(target):
                target.clear()
                selected = False
                for key, title, point in points.get(mode.currentData(), []):
                    target.addItem(title, point)
                    if (
                        not selected
                        and self.source_objects
                        and key.split(":", 1)[0] == self.source_objects[0]
                    ):
                        target.setCurrentIndex(target.count() - 1)
                        selected = True
            apply_choice()
            if mode.currentData() == "point" and not row.isHidden():
                if hasattr(self, "advanced"):
                    self.advanced.setChecked(True)
                self.focus_field("cx")

        mode.currentIndexChanged.connect(choose)
        target.currentIndexChanged.connect(apply_choice)
        self.valuesChanged.connect(follow)
        self._couplings.append(follow)
        choose()
        follow()

    def _release_surface_binding(self) -> None:
        """Nur eine eigene Koordinateneingabe ersetzt den gespeicherten Bezug."""
        if self.signalsBlocked():
            return
        from app.core.scene.placement import clear_surface_binding

        cleared = clear_surface_binding(self.spec)
        if any(self.values().get(name) for name in cleared):
            self.take_placement(cleared)

    def _couple_dependent_fields(self) -> None:
        """Ein Feld ohne Wirkung steht nicht da (§2.4, §2.6).

        „Relief auflegen" ist der Fall: *Fläche* wirkt nur, solange *Auflegen*
        auf „Auf eine Fläche" steht — bei „Von oben" bleibt ein ausgefülltes
        Feld stehen und verspricht etwas, das die Operation wortlos übergeht.
        Dasselbe Versprechen, das ``switch_variant`` bei den Zwillingen
        einlöst, nur eine Nummer kleiner: dort verschwindet die Zeile, weil die
        andere Variante sie gar nicht kennt; hier gehört sie zur Operation und
        ist nur gerade wirkungslos.

        **Sie verschwindet — Entscheidung Robert, 14.09.2026 (RM-171).** Bis
        dahin blieb sie grau stehen und sagte, woran es liegt, mit dem
        Argument „wer sie verschwinden sähe, suchte sie". Der Preis stand in
        der Sonde vom 13.09.: *Grundform hochziehen* trug bei einem Rechteck
        vier tote Zeilen vorn (Löcher, Spalten, Zeilen, Loch-Ø), also die
        Hälfte seiner Vorderseite. Die Zeile erscheint mit der Grundform, die
        sie braucht, und nicht heimlich — gesucht wird sie also dort, wo sie
        entsteht. Gesperrt bleibt sie zusätzlich, damit ein verborgenes Feld
        nie den Fokus bekommt. Der Satz, warum sie fehlt, steht an ihr, aber
        solange sie fort ist, sieht ihn niemand; mit der Bedingung kommt der
        eigene Satz des Feldes zurück.
        """
        # **Aus dem Schema, nicht aus einer Tabelle daneben.** Die Angabe stand
        # als ``DEPENDENT_FIELDS`` hier im Modul und war mit einem Eintrag
        # angelegt, während elf Parameter sie brauchten. Ihr eigener Kopf nannte
        # die Schwelle: über eine Handvoll hinaus gehört die Abhängigkeit an den
        # Parameter — dort steht sie jetzt (``ParamSpec.depends_on``), und
        # Handbuch und Agent lesen dieselbe Quelle.
        schema = self.spec.params.spec()
        # Das Altfeld ``at_feature`` neben einem Mehrfachwähler blendet
        # ``_hide_legacy_feature_field`` für immer aus — eine zweite Stelle,
        # die dieselbe Sichtbarkeit setzt, holte es mit seiner Bedingung
        # zurück. Heute trägt keines der Altfelder ein ``depends_on``; die
        # Ausnahme steht hier, damit das so bleiben darf.
        legacy = (
            "at_feature" if isinstance(self._editors.get("at_features"), FeatureSetField) else ""
        )
        rules = [
            entry
            for entry in schema
            if entry.depends_on is not None
            and entry.name in self._editors
            and entry.name != legacy
            and entry.depends_on[0] in self._editors
        ]
        if not rules:
            return
        titles = {entry.name: str(entry.title) for entry in self.spec.params.spec()}
        docs = {entry.name: str(entry.doc or "") for entry in self.spec.params.spec()}

        shown: dict[str, bool] = {}
        #: Werte, die ein Feld beim Verschwinden gegen seine benannte Null
        #: getauscht hat — sie kommen mit der Zeile zurück.
        parked: dict[str, Any] = {}

        def follow() -> None:
            entered = self.values()
            changed = False
            for entry in rules:
                editor = self._editors[entry.name]
                inactive = inactive_dependency(entry, schema, entered)
                active = inactive is None
                editor.setEnabled(active)
                label = self._rows[entry.name].labelForField(editor)
                if label is not None:
                    label.setEnabled(active)
                if (
                    isinstance(editor, ValueField)
                    and editor.names_its_zero()
                    and shown.get(entry.name) is not None
                    and shown.get(entry.name) is not active
                ):
                    # **Was verschwindet, sagt nichts mehr** (RM-513): Ein Feld,
                    # dessen Null „ohne“ heißt, geht beim Verschwinden auf
                    # seine Null und kommt mit seinem Wert zurück. Sonst zählte
                    # das Unsichtbare weiter — *Aushöhlen* mit „Oben öffnen“
                    # behielt eine Entlüftung, und die hielt den exakten Weg zu.
                    if not active and not editor.toggle.isChecked():
                        parked[entry.name] = editor.value()
                        with QSignalBlocker(editor.spin):
                            editor.set_value(0.0)
                        entered = self.values()
                    elif active and entry.name in parked:
                        with QSignalBlocker(editor.spin):
                            editor.set_value(parked.pop(entry.name))
                        entered = self.values()
                if shown.get(entry.name) is not active:
                    # Ein Migrationsmarker bleibt auch aktiv unsichtbar (RM-332).
                    self._rows[entry.name].setRowVisible(editor, active and not entry.internal)
                    shown[entry.name] = active
                    changed = True
                # Beide Hälften sagen dasselbe — bei einer ausgegrauten Zeile
                # ist der Grund die Auskunft, die zählt, und ausgerechnet dort
                # zeigt man eher auf die Beschriftung als in das gesperrte Feld.
                if inactive is None:
                    explanation = docs[entry.name]
                else:
                    explanation = _why_inactive(titles[inactive[0]], inactive[1][0])
                _explain(editor, label, explanation)
            if self.spec.name == "apply_texture" and "angle" in self._editors:
                # Ganzfläche dreht das Muster innerhalb ihrer festen Kontur;
                # ein aufgewickelter Zylinder ignoriert diesen Winkel.
                active = (
                    entered.get("coverage") == "whole_face" or entered.get("wrap") != "cylinder"
                )
                editor = self._editors["angle"]
                editor.setEnabled(active)
                if shown.get("angle") is not active:
                    self._rows["angle"].setRowVisible(editor, active)
                    shown["angle"] = active
                    changed = True
            # Eine Zeile weniger ist ein kürzerer Dialog, eine mehr ein
            # längerer. Nur wenn sich etwas bewegt hat: ``follow`` läuft bei
            # jedem Tastendruck. Und nicht über ``adjustSize`` — das deckelt
            # bei zwei Dritteln der Bildschirmhöhe und kappte eine aufgeklappte
            # Rückseite (gemessen 14.09.2026, *Bohrung setzen* offscreen bei
            # 800 Punkten Höhe: aufgeklappt 552, *Langloch* an 582, wieder
            # aus 533 — neunzehn Punkte unter dem Inhalt). Und einen
            # Ereignisumlauf später, nicht sofort: siehe ``_resize_to_content``.
            if changed:
                self._refresh_advanced_summary()
            if changed and self.isVisible():
                self._queue_refit("passive")
            self._follow_source_pending()

        self.valuesChanged.connect(follow)
        self._couplings.append(follow)
        follow()
        self._couple_sketch_measures()
        self._release_the_drawing_face()

    def _release_the_drawing_face(self) -> None:
        """Die Fläche, auf der gezeichnet wird, ist nie „Bis zur Fläche"
        (Bedienabnahme Zeichnen, F1).

        Die Auswahl trägt eine angeklickte Fläche als Ziel ein, und wer danach
        im Dialog auf genau dieser Fläche zeichnet, hat ein Ziel, von dem aus
        es kein Vorwärts gibt — die Auswertung hielt an. Sobald die Zeichnung
        auf der Zielfläche liegt, wird das Ziel geleert; die Höhe gilt wieder.
        """
        target = next(
            (entry.name for entry in self.spec.params.spec() if entry.targets_feature), ""
        )
        drawing = next(
            (entry.name for entry in self.spec.params.spec() if entry.kind == "sketch"), ""
        )
        if not target or not drawing:
            return
        from app.core.sketch.planes import feature_plane_parts, is_feature_plane
        from app.core.sketch.serialize import sketch_from_text

        def release() -> None:
            editor = self._editors.get(target)
            if not isinstance(editor, QComboBox):
                return
            chosen = str(editor.currentData() or "")
            text = str(self.values().get(drawing, "") or "")
            if not chosen or not text.strip():
                return
            try:
                plane = sketch_from_text(text).plane
            except AppError:
                return
            if not is_feature_plane(plane):
                return
            drawn_on, drawn_face = feature_plane_parts(plane)
            aimed_at, aimed_face = feature_plane_parts(f"feature:{chosen}")
            same_body = not drawn_on or not aimed_at or drawn_on == aimed_at
            if drawn_face == aimed_face and same_body:
                empty = editor.findData("")
                if empty >= 0:
                    editor.setCurrentIndex(empty)

        self.valuesChanged.connect(release)
        self._couplings.append(release)
        release()

    def _link_sketch_planes(self) -> None:
        """Eine zweite Zeichnung beginnt auf der Ebene der ersten (RM-183).

        Der obere Umriss eines Übergangs und die Bahn eines Sweeps hatten
        keinen Bezug zur Hauptzeichnung: Ihr Editor öffnete immer auf der
        Draufsicht. Beim Übergang muss die obere auf derselben Ebene liegen wie
        die untere, sonst lehnt die Operation ab; die Bahn nimmt ohnehin nur
        ihre eigenen Ebenen (``sketch_planes``) und fällt dann auf die erste.
        """
        from app.ui.sketch_editor import SketchField

        main = self._editors.get("sketch")
        if not isinstance(main, SketchField):
            return
        for name, editor in self._editors.items():
            if name != "sketch" and isinstance(editor, SketchField):
                editor.follow_plane_of(main)

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
        # Nur die Grundkontur von ``_regions_for`` ersetzt Länge und Breite.
        # Ein Führungsweg oder Gegenprofil ist ein anderer geometrischer Bezug.
        sketch_field = "sketch"
        if sketch_field not in declared or sketch_field not in self._editors:
            return
        from app.ui.sketch_editor import SketchField

        if not isinstance(self._editors[sketch_field], SketchField):
            return

        reason = tr("Die Maße kommen aus der Zeichnung — über „Zeichnen …“ zu ändern.")
        follows = tr("Die Zeichnung folgt dieser Zahl: sie wird darauf gestreckt.")
        clamped = tr("Die Zeichnung ist hier kleiner, als dieses Feld zeigen kann.")
        axis_of = {"length": 0, "width": 1}
        # **Nach einer Zeichnung heißen die Maße nach der Zeichnung** (RM-391).
        # „Länge“ und „Breite“ meinen X und Y — auf einer Seitenebene aber
        # liegt die Zeichnung in Y und Z, und „Breite 40“ machte das Teil 40
        # hoch. Waagerecht und senkrecht gelten auf jeder Ebene so, wie die
        # Zeichnung im Editor steht.
        drawn_titles = {"length": tr("Zeichnung waagerecht"), "width": tr("Zeichnung senkrecht")}
        docs = {name: str(entry.doc or "") for name, entry in declared.items()}
        seen_text: dict[str, str] = {}
        seen_extent: dict[str, tuple[float, float] | None] = {}

        #: Läuft gerade eine Streckung? Als Wörterbuch und nicht als lokale
        #: Variable, weil ``stretch`` und ``follow_sketch`` einander rufen und
        #: ein ``nonlocal`` über zwei Ebenen schlechter zu lesen wäre.
        stretching = {"now": False}
        #: Hat der erste Durchlauf die Felder schon aus der Zeichnung belegt?
        #:
        #: **Der Aufbau schreibt, danach liest der Dialog.** Beim Öffnen steht
        #: in ``length`` die Vorgabe des Schemas — 40, während die Zeichnung 50
        #: misst. Ohne diese Unterscheidung hielte der erste Durchlauf die 40
        #: für eine Ansage und schrumpfte die Zeichnung darauf: Wer einen
        #: Dialog nur öffnet und wieder schließt, hätte seine Zeichnung
        #: verkleinert. Der Test hat genau das gefangen.
        primed = {"done": False}
        held: dict[str, tuple[str, ...]] = {}
        #: Ist die letzte Streckung in beide Richtungen gegangen?
        evenly: dict[str, bool] = {}
        #: Die Zeilen, die dieser Zweig ausgeblendet hat — nur sie kommen zurück.
        hidden: set[str] = set()

        def evenly_note() -> str:
            """Warum das andere Maß mitgewachsen ist — oder nichts.

            Eine Zeichnung mit Kreis, Bogen oder Winkel lässt sich nicht in
            einer Richtung strecken, ohne ihre Form zu ändern
            (``sketch.edit.stretched``). Dass dann beide Felder springen, muss
            dort stehen, wo der Kunde getippt hat.
            """
            if not evenly.get("value"):
                return ""
            return str(
                tr(
                    "Die Zeichnung hat Rundungen oder Winkel und wächst deshalb "
                    "in beiden Richtungen."
                )
            )

        def held_note() -> str:
            """Was beim Strecken **nicht** mitkam — oder nichts.

            Ein Maß an einem Projektparameter bleibt stehen (Regel 8), und die
            Zeichnung erreicht das getippte Maß dann nicht ganz. Das gehört an
            das Feld, in dem die Zahl steht: Eine Abweichung, die niemand
            erklärt, sieht aus wie ein Rechenfehler.
            """
            kept = held.get("value") or ()
            if not kept:
                return ""
            return str(
                tr(
                    "{count} Maß der Zeichnung hängt an einem Projektparameter "
                    "und bleibt — sie folgt nur so weit."
                )
            ).format(count=len(kept))

        def stretch(text: str, factor: float, axis: int) -> None:
            """Die Zeichnung auf das getippte Maß bringen — in seiner Richtung.

            Die Punkte allein zu strecken genügt nicht — ein ``distance`` von
            50 zöge der Löser wieder auf 50 zusammen, und das Feld zeigte nach
            dem Schließen die alte Zahl. ``sketch.edit.stretched`` nimmt die
            Maße mit, lässt stehen, was an einem Parameter hängt, und streckt
            nur die Richtung des Feldes, wo die Zeichnung es zulässt (RM-391).
            """
            from app.core.errors import AppError
            from app.core.sketch.edit import stretched
            from app.core.sketch.serialize import sketch_from_text, sketch_to_text
            from app.ui.sketch_editor import SketchField

            field = self._editors.get(sketch_field)
            if not isinstance(field, SketchField):
                return
            try:
                result = stretched(sketch_from_text(text), factor, axis, self._parameter_values)
            except AppError:
                # Eine halbfertige Zeichnung ist im Dialog kein Fehlerfall —
                # dieselbe Haltung wie in ``sketch_extent``.
                return

            with QSignalBlocker(field):
                field.set_text(sketch_to_text(result.sketch))
            seen_text.pop("value", None)
            seen_extent.pop("value", None)
            held["value"] = result.kept
            evenly["value"] = result.evenly
            # **Ein Wächter, kein Vertrauen auf Genauigkeit.** Der Löser trifft
            # das Maß auf seine Toleranz genau, nicht exakt; bliebe ein Rest
            # über der Schwelle, streckte der nächste Durchlauf erneut, und der
            # Dialog liefe im Kreis, während der Nutzer tippt.
            stretching["now"] = True
            try:
                follow_sketch()
            finally:
                stretching["now"] = False

        def follow_sketch() -> None:
            entered = self.values()
            schema = tuple(declared.values())
            if inactive_dependency(declared[sketch_field], schema, entered) is not None:
                return
            text = str(entered.get(sketch_field, "") or "")
            # ``valuesChanged`` feuert an **jedem** Feld, und ``sketch_extent``
            # löst die ganze Zeichnung — mit einer SVD über die volle
            # Bedingungsmatrix, im Qt-Hauptthread (§2.8). Wer im Feld daneben
            # eine Höhe tippte, rechnete je Taste einmal den Löser. Gemerkt
            # wird nur die **Rechnung**, nicht der ganze Durchlauf: Die
            # Sperren darunter müssen weiterlaufen, sonst bliebe ein Feld
            # frei, das der Nachbarzweig gerade freigegeben hat.
            # **Eine neue Zeichnung ist die Ansage, nicht die Zahl im Feld.**
            # Ob der Nutzer ein Maß getippt hat, lässt sich nur fragen, solange
            # die Zeichnung dieselbe ist wie beim letzten Durchlauf. Hier stand
            # allein ``primed``, und das war nach dem ersten Durchlauf für
            # immer gesetzt: Wer den Dialog **ohne** Zeichnung öffnete und dann
            # über „Zeichnen …" einen Kreis Ø 30 zog, bekam ihn auf die Vorgabe
            # des Schemas gestreckt — Ø 40, und der Körper stand neben seiner
            # Zeichnung (gemessen am 22.09.2026 am Fenster, *Zwischen zwei
            # Umrissen aufspannen*, RM-183).
            drawing_changed = seen_text.get("value") != text
            if not drawing_changed:
                extent = seen_extent.get("value")
            else:
                extent = sketch_extent(text, self._parameter_values)
                seen_text["value"] = text
                seen_extent["value"] = extent
            for name in ("shape", "length", "width", "corners", *axis_of):
                editor = self._editors.get(name)
                if editor is None or name not in declared:
                    continue
                # Ein Maß eines anderen Formularzweigs ist keine Vorgabe für
                # die Zeichnung und behält seine bestehende Sperre und Zahl.
                if inactive_dependency(declared[name], schema, entered) is not None:
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
                    # **Auch der Hinweis am freigegebenen Maßfeld ist unsere
                    # Marke.** Erkannt wird die eigene Zeile an ihrer
                    # Begründung; seit die Maßfelder bedienbar sind, tragen sie
                    # `follows` statt `reason`, und ohne diese Zeile bliebe
                    # nach dem Löschen ein Satz stehen, der sich auf eine
                    # Zeichnung beruft, die es nicht mehr gibt.
                    # Name und Zeile kommen zurück, woran sie zu erkennen sind —
                    # nicht am Tooltip: Den überschreibt ``depends_on`` am
                    # Breitenfeld, bevor dieser Zweig läuft.
                    if (
                        isinstance(label, QLabel)
                        and name in drawn_titles
                        and label.text() == str(drawn_titles[name])
                    ):
                        label.setText(str(declared[name].title))
                    if name in hidden:
                        hidden.discard(name)
                        self._rows[name].setRowVisible(editor, True)
                    if editor.toolTip() in (reason, follows, held_note(), evenly_note()):
                        editor.setEnabled(True)
                        if label is not None:
                            label.setEnabled(True)
                        _explain(editor, label, docs[name])
                    continue
                if name in axis_of and isinstance(editor, ValueField):
                    drawn = extent[axis_of[name]]
                    typed = editor.value()
                    # **Eine getippte Zahl ist eine Ansage, keine Anzeige.**
                    # Weicht sie von dem ab, was die Zeichnung misst, hat der
                    # Nutzer gerade ein Maß gesetzt — und die Zeichnung folgt
                    # ihm, statt seinen Wert beim nächsten Durchlauf zu
                    # überschreiben (Robert, 03.09.2026).
                    #
                    # Nur Zahlen: Ein Ausdruck im Feld (``=@breite``) meint
                    # eine Bindung an einen Projektparameter, und die gehört
                    # in die Zeichnung, nicht in eine einmalige Streckung.
                    # **Ein geklemmter Wert ist keine Ansage.** Die Felder
                    # tragen ein Schema-Minimum von 0,1 mm; wird die Zeichnung
                    # kleiner, kann das Feld sie nicht mehr zeigen und klemmt.
                    # Ohne diese Bedingung las der nächste Durchlauf die
                    # geklemmte Zahl als Eingabe und streckte zurück:
                    # 0,1 getippt, Zeichnung 0,1 auf 0,06 — das Breitenfeld
                    # zeigte 0,1 statt 0,06, Faktor 0,1/0,06, und heraus kam
                    # 0,166667. Gemessen am 03.09.2026, mein eigener Fehler
                    # vom selben Tag.
                    least = declared[name].minimum
                    darstellbar = least is None or drawn >= float(least)
                    if (
                        isinstance(typed, float)
                        and drawn > _SKETCH_EPS
                        and abs(typed - drawn) > _SKETCH_EPS
                        and not stretching["now"]
                        and primed["done"]
                        and not drawing_changed
                        and darstellbar
                    ):
                        stretch(text, typed / drawn, axis_of[name])
                        return
                    # Ohne ``blockSignals`` löst das Setzen ``valuesChanged``
                    # aus, und diese Funktion riefe sich selbst.
                    with QSignalBlocker(editor):
                        editor.set_value(drawn)
                    editor.setEnabled(True)
                    if label is not None:
                        label.setEnabled(True)
                    if isinstance(label, QLabel):
                        label.setText(str(drawn_titles[name]))
                    # **Ein geklemmtes Feld sagt, dass es klemmt.** Sonst
                    # steht dort 0,1, während die Zeichnung 0,06 misst — eine
                    # stille Ungenauigkeit ist schlimmer als eine genannte,
                    # weil der Kunde die Zahl für sein Maß hält.
                    _explain(
                        editor,
                        label,
                        (not darstellbar and clamped) or held_note() or evenly_note() or follows,
                    )
                    continue
                # Grundform und Eckenzahl bleiben gesperrt, und das ist keine
                # halbe Sache: Eine gezeichnete Kontur **ist** keine Grundform.
                # Ein Feld, das sie in „Rechteck" umdeutet, verspräche, die
                # Zeichnung zu ersetzen — das tut „Zeichnen …", und nur dort.
                editor.setEnabled(False)
                if label is not None:
                    label.setEnabled(False)
                _explain(editor, label, reason)
                # **Die Grundform verschwindet, solange gezeichnet ist** (RM-391).
                # Gesperrt stand dort weiter „Rechteck“ neben einem Linienzug
                # mit Schräge — eine Angabe, die nicht stimmt, ist schlimmer
                # als keine. Wer die Zeichnung löscht, bekommt die Zeile zurück.
                if name == "shape" and name not in hidden:
                    hidden.add(name)
                    self._rows[name].setRowVisible(editor, False)

        self.valuesChanged.connect(follow_sketch)
        self._couplings.append(follow_sketch)
        follow_sketch()
        primed["done"] = True

    def _watch(self, editor: QWidget) -> None:
        """Verbindet das Änderungssignal des Editors mit ``valuesChanged``.

        Je Editorsorte eines — die Vorschau will von jedem Feld wissen, nicht
        nur von den Zahlen.
        """
        from app.ui.sketch_editor import SketchField

        for control in (editor, *editor.findChildren(QWidget)):
            if isinstance(control, (QComboBox, QSpinBox, QDoubleSpinBox)):
                wheel_needs_focus(control)

        if isinstance(editor, FeatureSetField | EdgeSetField):
            editor.changed.connect(self.valuesChanged)
            editor.validityChanged.connect(self._follow_source_pending)
        elif isinstance(editor, PointsField):
            editor.changed.connect(self.valuesChanged)
        elif isinstance(editor, ContourField | OrganizerLayoutField | SealPathField):
            editor.valueChanged.connect(self.valuesChanged)
            editor.validityChanged.connect(self._follow_source_pending)
        elif isinstance(editor, ValueField | SketchField | ImageSourceField | ArmatureField):
            editor.changed.connect(self.valuesChanged)
            if isinstance(editor, ValueField):
                # Ob die Stückzahl trägt und ob eine Zahl innerhalb ihrer
                # Grenzen liegt, entscheidet der Knopf mit — bei jeder
                # Eingabe, nicht erst beim Klick.
                editor.changed.connect(self._follow_source_pending)
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
        if entry.kind == "step_bodies":
            from app.ui.step_dialog import StepBodiesField

            return StepBodiesField(start, self)
        if entry.kind == "contours":
            return ContourField(start, self)
        if entry.kind == "organizer":
            return OrganizerLayoutField(start, self)
        if entry.kind == "features":
            if entry.required:
                return FeatureSetField(
                    self._features,
                    tuple(start or ()),
                    self,
                    empty=None,
                    hint=tr("Mindestens ein Merkmal markieren."),
                )
            if entry.feature_kinds:
                # Eine Liste bestimmter Arten, die leer bleiben darf — die
                # Öffnungen des Aushöhlens (P6.3): leer heißt „keine gewählte
                # Fläche", nicht „der ganze Körper".
                return FeatureSetField(
                    self._features,
                    tuple(start or ()),
                    self,
                    empty=tr("Keine"),
                    hint=tr("Flächen markieren oder „Keine“ wählen."),
                )
            return FeatureSetField(self._features, tuple(start or ()), self)
        if entry.kind == "edges":
            return EdgeSetField(self._edges, str(start or ""), self)
        if entry.kind == "points":
            points = PointsField(str(start or ""), self)
            points.pickRequested.connect(self.pointsPickRequested)
            return points
        if entry.kind == "bool":
            # Die ganze Zeile antwortet, nicht nur das Kästchen (``RowCheckBox``).
            editor = RowCheckBox(self)
            editor.setChecked(bool(start))
            return editor
        if entry.kind == "material":
            return MaterialField(str(start or ""), self, required=entry.required)
        if entry.kind == "filament":
            # Die Slotnummer bleibt der Wert (``currentData``), gewählt wird
            # aber ein Filament mit Farbe und Namen. Name und Farbe wandern
            # in ihre eigenen Felder, sichtbar und weiter änderbar — der
            # Wähler füllt sie aus, er ersetzt sie nicht.
            from app.ui.filament_picker import FilamentField

            picker = FilamentField(
                int(start or 0), self._slots, self, whole_body=self.spec.name == "assign_slot"
            )
            picker.filamentChosen.connect(self._fill_filament_fields)
            picker.spoolChosen.connect(self._filament_spool_chosen)
            picker.choiceNotice.connect(self._filament_choice_notice)
            picker.choiceProblem.connect(self._filament_choice_problem)
            return picker
        if entry.kind == "int" and entry.name == self.spec.produces_from:
            # Die Stückzahl bekommt ihr fx wie jedes andere Zahlenfeld — und
            # löst es beim Übernehmen zur Zahl auf (:class:`CountField`).
            return CountField(entry, start, self._parameter_values, self)
        if entry.kind in ("float", "int"):
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
            if self.spec.name == "create_seal" and entry.name == "path_sketch":
                return SealPathField(parent=self)
            # §30.1 Stufe zwei: der Text ist ein Speicherformat, keine
            # Eingabe — gezeichnet wird im Editor, das Feld fasst zusammen.
            from app.ui.sketch_editor import SketchField

            return SketchField(
                str(start or ""),
                self._parameter_values,
                self,
                self._surroundings,
                required=entry.required,
                empty_hint=(
                    str(entry.doc)
                    if entry.doc and (entry.required or entry.name != "sketch")
                    else None
                ),
                # Die Ebenen, auf denen die Zeichnung liegen darf, sagt der
                # Parameter (``ParamSpec.sketch_planes``, RM-183).
                planes=entry.sketch_planes,
            )
        if entry.kind == "feature" or entry.targets_feature:
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
            elif entry.targets_feature and not start:
                # **Ein Pflichtziel beginnt leer** (RM-394, Regel 21). Ohne
                # diesen Eintrag wählte die Liste ihren ersten — bei *An
                # Merkmal ausrichten* die linke Seite des anderen Körpers —, und
                # wer sein Ziel im Bild anklickte, traf damit das Quellmerkmal:
                # Der Körper saß still an der falschen Seite. Leer sperrt
                # *Übernehmen* mit Grund (:meth:`_target_missing`).
                combo.addItem(tr("— im Bild wählen —"), "")
            choices = self._target_features if entry.targets_feature else self._features
            for identifier, label in choices.items():
                combo.addItem(label, identifier)
            if start:
                index = combo.findData(str(start))
                if index < 0:
                    combo.addItem(str(start), str(start))
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            return combo
        if entry.kind == "strokes":
            return StrokeSummary(str(start or ""), self)
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
            object_choices: Mapping[str, str] = self._sources if entry.kind == "source" else objects
            combo = QComboBox(self)
            for identifier, name in object_choices.items():
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

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Das zuletzt gewählte Zielfeld bleibt beim Klick ins Modell die Frage."""
        if stop_watching_the_dying(self, watched, event):
            return False
        if event.type() == QEvent.Type.FocusIn:
            self._feature_focus = next(
                (name for name, editor in self._editors.items() if editor is watched), ""
            )
        return super().eventFilter(watched, event)

    def take_feature(self, feature_id: str, label: str, object_id: str | None = None) -> bool:
        """Trägt ein angeklicktes Merkmal ein, wenn der Dialog eines erwartet.

        Der ``doc``-Satz dieses Parameters versprach das seit je — „wird beim
        Anklicken im Fenster eingetragen" —, und einzulösen war es nicht: der
        Dialog sperrte das Fenster, es gab also kein Anklicken, solange er
        offen war. Seit er das nicht mehr tut, ist der kürzeste Weg zu einer
        Fläche wieder der, auf sie zu zeigen.

        Gibt zurück, ob etwas gesetzt wurde — der Aufrufer weiß sonst nicht, ob
        sein Klick angekommen ist.
        """
        fields = [
            entry
            for entry in self.spec.params.spec()
            if entry.kind in ("feature", "features") or entry.targets_feature
            if not (
                entry.name == "at_feature"
                and isinstance(self._editors.get("at_features"), FeatureSetField)
            )
        ]
        entry = next((item for item in fields if item.name == self._feature_focus), None)
        if entry is None:
            # Ohne Fokus füllt der Klick das erste noch leere Pflichtfeld, das
            # dieses Merkmal annimmt — ein Quellmerkmal nur auf dem eigenen
            # Körper, ein Ziel auf jedem (RM-394).
            entry = next(
                (
                    item
                    for item in fields
                    if item.required
                    and self._feature_field_empty(item.name)
                    and self._takes_feature_of(item, object_id)
                ),
                None,
            )
        if entry is None:
            entry = next((item for item in fields if not item.targets_feature), None)
        if entry is None:
            return False
        editor = self._editors.get(entry.name)
        if not isinstance(editor, (QComboBox, FeatureSetField)):
            return False
        if entry.targets_feature:
            if object_id is None:
                return False
            reference = f"{object_id}:{feature_id}"
            label = f"{self._object_names.get(object_id, object_id)} · {label or feature_id}"
        else:
            if (
                object_id is not None
                and self.source_objects
                and object_id not in self.source_objects
            ):
                return False
            reference = feature_id
        if isinstance(editor, FeatureSetField):
            editor.add_feature(reference, label)
            return True
        index = editor.findData(reference)
        if index < 0:
            editor.addItem(label or feature_id, reference)
            index = editor.count() - 1
        editor.setCurrentIndex(index)
        return True

    def _feature_field_empty(self, name: str) -> bool:
        editor = self._editors.get(name)
        return isinstance(editor, QComboBox) and not editor.currentData()

    def _takes_feature_of(self, entry: Any, object_id: str | None) -> bool:
        """Ob ein Merkmalsfeld ein Merkmal dieses Körpers annehmen kann."""
        if entry.targets_feature:
            return object_id is not None
        return object_id is None or not self.source_objects or object_id in self.source_objects

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
        if self.spec.name == "create_seal" and name in _SEAL_PATH_COMPANIONS:
            name = "path_sketch"
        editor = self._editors.get(name)
        if editor is None or editor.isHidden():
            # Eine Zeile, deren Bedingung nicht gilt, ist fort und gesperrt
            # (``_couple_dependent_fields``); ``setFocus`` täte dort nichts,
            # und ein „erledigt" dafür wäre gelogen.
            return False
        entry = next((item for item in self.spec.params.spec() if item.name == name), None)
        if entry is not None and (entry.kind in ("feature", "features") or entry.targets_feature):
            self._feature_focus = name
        klappe = getattr(self, "advanced", None)
        # Gefragt wird das Formular, in dem die Zeile steht, nicht das Schema:
        # Ein entschiedener Wert steht vorn, auch wenn sein Schema ihn nach
        # hinten legt (``_promoted_fields``), und die Klappe ginge sonst für
        # ein Feld auf, das gar nicht darin liegt.
        if self._rows.get(name) is self._advanced_form and klappe is not None:
            klappe.setChecked(True)
        editor.setFocus(Qt.FocusReason.OtherFocusReason)
        # Ein ``ValueField`` ist ein Verbund; der Cursor gehört in sein Drehfeld,
        # und der Wert darin wird ausgewählt, damit Tippen ihn ersetzt.
        inner = editor.findChild(QDoubleSpinBox)
        if inner is not None:
            inner.setFocus(Qt.FocusReason.OtherFocusReason)
            inner.selectAll()
        self._scroll.ensureWidgetVisible(editor)
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
        from app.core.knowledge.parts.ops import placement_fields

        if (
            self.centre_mode is not None
            and self.centre_mode.currentData() == "point"
            and self._centre_row is not None
            and not self._centre_row.isHidden()
        ):
            self.take_placement(dict(zip(("cx", "cy", "cz"), point, strict=True)))
            return True
        fields = {entry.name for entry in self.spec.params.spec()}
        placed = placement_fields(self.spec.params)
        axes = tuple(placed.get(name, name) for name in ("x", "y", "z"))
        if not set(axes) <= fields:
            return False
        self._place_known = self._place is not None
        for name, value in zip(axes, point, strict=True):
            editor = self._editors.get(name)
            if isinstance(editor, ValueField):
                editor.set_value(float(value))
        self._refresh_place()
        return True

    def take_plane_point(self, point: Sequence[float]) -> int | None:
        """Einen im Bild angeklickten Punkt in das Punktefeld eintragen (RM-400).

        Gibt die Nummer des gesetzten Punkts zurück, 1 bis 3 — oder ``None``,
        wenn der Dialog gerade kein wirksames Punktefeld trägt: Wer die Ebene
        inzwischen auf eine Achse gestellt hat, dessen Klick ist keine Antwort.
        """
        for editor in self._editors.values():
            if isinstance(editor, PointsField) and editor.isEnabled():
                return editor.take_point(point)
        return None

    def take_placement(self, values: Mapping[str, Any]) -> None:
        """Übernimmt eine vollständige Raumlage ohne gerundete Zwischenwerte."""
        if self._place is not None and any(name in values for name in self._place):
            self._place_known = True
        with QSignalBlocker(self):
            for name, value in values.items():
                editor = self._editors.get(name)
                if isinstance(editor, ValueField):
                    editor.toggle.setChecked(False)
                    editor.set_value(value)
                elif isinstance(editor, QComboBox):
                    index = editor.findData(value)
                    if index >= 0:
                        editor.setCurrentIndex(index)
                elif isinstance(editor, QLineEdit):
                    editor.setText(str(value))
                elif isinstance(editor, QCheckBox) and isinstance(value, bool):
                    editor.setChecked(value)
        self.valuesChanged.emit()

    def switch_variant(self, spec: OperationSpec) -> None:
        """Der Dialog gehört jetzt einer anderen Variante derselben Handlung.

        Eine Variantengruppe (``VARIANT_GROUPS``) wechselt hier ihre Art, und
        die Schemata sind nicht dieselben. Bis P2.8 galt das auch den
        zusammengelegten Zwillingen (``MENU_TWINS``) über den Haken im Dialog:
        Die überzähligen Werte wurden **beim Anwenden** weggefiltert — im Dialog
        standen sie weiter da, wer „Exakt" ankreuzte und den Bezugspunkt auf
        „Ecke" stellte, bekam einen mittigen Quader und keinen Ton dazu. Ein
        Feld ohne Wirkung ist ein Versprechen, das niemand hält; es
        verschwindet, statt zu lügen.

        Die Beschreibung wechselt mit: die des Mesh-Quaders nennt eine Wahl
        („mittig auf Z = 0 oder auf einer Ecke"), die es im exakten Kern nicht
        gibt.
        """
        if spec.name == self.spec.name:
            return
        entered = self.values()
        self._variant_values[self.spec.name] = entered
        given = {**self._variant_values.get(spec.name, {}), **entered}
        retired: list[QWidget] = []
        with QSignalBlocker(self):
            for callback in self._couplings:
                self.valuesChanged.disconnect(callback)
            self._couplings.clear()
            for field in self._source_fields:
                field.cancel_pending()
            for name, editor in self._editors.items():
                editor.removeEventFilter(self)
                if isinstance(editor, ValueField):
                    # Qt löst das Feld mit nullptr; der PySide-Stub erlaubt nur QWidget.
                    editor._completer.setWidget(None)  # type: ignore[arg-type]
                row = self._rows[name].takeRow(editor)
                for item in (row.labelItem, row.fieldItem):
                    widget = item.widget() if item is not None else None
                    if widget is not None:
                        widget.blockSignals(True)
                        widget.hide()
                        retired.append(widget)
            self._editors.clear()
            self._rows.clear()
            self.spec = spec
            self._feature_focus = ""
            promoted = _promoted_fields(spec, given) if self._promote_values else frozenset()
            for entry in spec.params.spec():
                if spec.name == "create_seal" and entry.name in _SEAL_PATH_COMPANIONS:
                    continue
                editor = self._editor_for(entry, self._object_names, given.get(entry.name))
                if isinstance(editor, SealPathField):
                    editor.set_selection(given)
                self._editors[entry.name] = editor
                self._watch(editor)
                if entry.kind in ("feature", "features") or entry.targets_feature:
                    editor.installEventFilter(self)
                decided = entry.name in promoted
                form = (
                    self._front
                    if entry.placement == "front" or isinstance(editor, ArmatureField) or decided
                    else self._advanced_form
                )
                # Der Artwähler bleibt nach den Feldern, nicht zwischen ihnen,
                # und die Lesezeile *Stelle* bleibt ihre erste Zeile.
                if form is self._front:
                    form.insertRow(
                        1 + len([f for f in self._rows.values() if f is form]),
                        str(entry.title),
                        editor,
                    )
                else:
                    form.addRow(str(entry.title), editor)
                self._rows[entry.name] = form
                _explain(editor, form.labelForField(editor), str(entry.doc or ""))
                if isinstance(editor, RowCheckBox):
                    caption_toggles(form.labelForField(editor), editor)
                if isinstance(editor, ValueField) and editor.circle_toggle is not None:
                    caption = form.labelForField(editor)
                    if isinstance(caption, QLabel):
                        caption.setText(editor.caption())
                        editor.captionChanged.connect(caption.setText)
            self._source_fields = tuple(
                editor for editor in self._editors.values() if isinstance(editor, ImageSourceField)
            )
            for field in self._source_fields:
                field.pendingChanged.connect(self._follow_source_pending)
            self._couple_dependent_fields()
            self._couple_surface_binding()
            self._install_rotation_centre(given)
            self._link_sketch_planes()
        # Alte Komplettierer und ihre Felder leben bis nach dem Neuaufbau.
        # removeRow zerstörte sie synchron mitten im Variantenwechsel.
        for widget in retired:
            widget.deleteLater()
        self.setWindowTitle(str(spec.title))
        self._accept_button.setText(
            str(tr("Einsetzen")) if spec.category == "parts" else str(spec.title)
        )
        if self._description is not None:
            self._description.setText(lead_sentence(spec))
            self._description.setVisible(bool(spec.doc))
            self._describe_fully(spec)
        # Ein Zwilling hat seine eigene Grenze — oder keine. Stehen bleibt
        # sonst die des anderen Rechenkerns, und das ist schlechter als keine
        # Angabe.
        self._show_caveat(spec)
        self._place = place_fields(spec)
        self._follow_source_pending()
        self._hide_legacy_feature_field()
        self._hide_internal_fields()
        self._refresh_place()
        self._align_to_the_front()
        self._even_number_fields()
        self._refresh_advanced_summary()
        self._resize_to_content("passive")
        self.schemaChanged.emit()

    def showEvent(self, event: Any) -> None:  # noqa: N802 — Qt gibt den Namen vor
        super().showEvent(event)
        if not event.spontaneous() and not self._first_focus_given:
            self._first_focus_given = True
            self._focus_first_empty_feature()
        self._queue_refit("initial")

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
        if self.isVisible():
            self._height.fit_to_screen(self)

    def _even_number_fields(self) -> None:
        """Alle Zahlenfelder des Dialogs so breit wie das breiteste."""
        even_value_fields(
            editor for editor in self._editors.values() if isinstance(editor, ValueField)
        )

    def _before_folding(self, inner: QWidget) -> None:
        """Vor dem Zuklappen: Fokus aus der Rückseite an die Überschrift.

        Gerufen beim Drücken, also bevor ``panels.collapsible`` den Inhalt
        verbirgt — danach hätte Qt den Fokus schon an den nächsten Knopf in der
        Kette gegeben, und Enter träfe ihn statt des Hauptknopfs.
        """
        if not self.advanced.isChecked():
            return
        focused = inner.focusWidget()
        if focused is not None and focused.hasFocus() and inner.isAncestorOf(focused):
            self.advanced.setFocus(Qt.FocusReason.OtherFocusReason)

    def _advanced_toggled(self, _open_now: bool) -> None:
        """Ausdrücklich auf- oder zugeklappt: die Höhe folgt (``fenster.md``)."""
        self._queue_refit("explicit")

    def _advanced_titles(self) -> list[str]:
        """Die Beschriftungen der sichtbaren Zeilen hinter der Klappe, in ihrer Reihenfolge.

        Ohne Stelle und Richtung: Die Stelle nennt vorn die Lesezeile, und
        „Position X, Position Y, Position Z …“ verriete nicht, was die Klappe
        sonst noch hält (Tiefe, Aufweitung).
        """
        form = self._advanced_form
        names = {id(editor): name for name, editor in self._editors.items()}
        where = set(self._place or ()) | set(direction_fields(self.spec))
        titles: list[str] = []
        for row in range(form.rowCount()):
            if not form.isRowVisible(row):
                continue
            field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if field is not None and names.get(id(field.widget())) in where:
                continue
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            label = item.widget() if item is not None else None
            if isinstance(label, QLabel) and label.text().strip():
                titles.append(label.text().strip())
        return titles

    def _refresh_advanced_summary(self) -> None:
        """Was die Klappe nennt, folgt den Zeilen, die gerade hinter ihr stehen."""
        if self._advanced_summary is None:
            return
        said = advanced_summary(self._advanced_titles())
        if said == self._advanced_summary.text():
            return
        self._advanced_summary.setText(said)
        self.advanced.setToolTip(said)
        self.advanced.setAccessibleDescription(said)

    def _align_to_the_front(self) -> None:
        """Eine Beschriftungskante, bemessen an der Vorderseite (RM-518, C21).

        ``panels.align_forms`` zählte die zugeklappte Rückseite mit, und ihre
        längste Beschriftung schob die Felder vorn um 120 bis 170 Punkte nach
        rechts. Jetzt setzt die Vorderseite die Spalte, und eine längere
        Beschriftung hinten bricht um (:func:`app.ui.dialogs.align_to_the_front`).
        """
        align_to_the_front(self._front, self._advanced_form)
        self._aligned = True

    def _queue_refit(self, intent: ContentFitIntent) -> None:
        """Fasst gleichzeitige Größenwünsche mit Vorrang der bewussten Aktion zusammen."""
        priority = {"passive": 0, "explicit": 1, "initial": 2}
        if priority[intent] > priority[self._refit_intent]:
            self._refit_intent = intent
        self._refit.start(0)

    def _run_queued_refit(self) -> None:
        intent = self._refit_intent
        self._refit_intent = "passive"
        self._resize_to_content(intent)

    def _resize_to_content(self, intent: ContentFitIntent = "passive") -> None:
        """Misst den aktuellen Inhalt entsprechend seiner Änderung.

        Eine Klappe darf ein automatisch bemessenes Fenster vertikal anpassen;
        bedingte Felder und Schemaänderungen aktualisieren nur den Rollbereich.
        Die anfängliche Breite berücksichtigt auch die verborgene Rückseite.
        """
        layout = self.layout()
        if layout is None:
            return
        content = self._scroll.widget()
        content_layout = content.layout() if content is not None else None
        if content_layout is not None:
            content_layout.activate()
        self._scroll.updateGeometry()
        layout.activate()
        natural_width = expanded_width(self._scroll, self._advanced_form)
        self._height.fit(
            self,
            self._scroll,
            grow_width=intent == "initial",
            intent=intent,
            natural_width=natural_width if intent == "initial" else 0,
        )

    def _fill_filament_fields(
        self,
        name: str,
        colour: str,
        material_type: str,
        slicer_profile: str,
    ) -> None:
        """Die Identität des gewählten Filaments in ihre eigenen Felder.

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
        for key, value in (
            ("name", name),
            ("colour", colour),
            ("material_type", material_type),
            ("slicer_profile", slicer_profile),
        ):
            editor = self._editors.get(key)
            # Auch leer ist eine vollständige Antwort: Eine lokale Spule hat
            # bewusst kein Herstellerprofil. Ließe man diesen Wert aus, bliebe
            # beim Wechsel das unsichtbare Profil der vorherigen Spule stehen
            # und der Slicer nähme deren Druckwerte.
            if isinstance(editor, QLineEdit):
                editor.setText(value)

    def _filament_spool_chosen(self, spool: object) -> None:
        """Die ausdrückliche Wahl ersetzt auch leere Typ- und Profilangaben vollständig."""
        editor = self._editors.get("replace_filament")
        if isinstance(editor, QCheckBox):
            editor.setChecked(spool is not None)
        self.spoolChosen.emit(spool)

    def _filament_choice_notice(self, message: str) -> None:
        """Eine überholte Lagerwahl wird im offenen Dialog erklärt und neu angeboten."""
        self._filament_notice.setText(message)
        self._filament_notice.setVisible(bool(message))

    def _filament_choice_problem(self, problem: object) -> None:
        """Der Lagerfehler behält seine eigenen Handlungen im Operationsdialog."""
        from app.ui.filament_picker import FilamentField

        picker = self.sender()
        handlers = (
            {"retry": weak_slot(picker, FilamentField.retry_choice, forward=True)}
            if isinstance(picker, FilamentField)
            else {}
        )
        self._filament_notice.set_error(problem, handlers)
        self._filament_notice.show()

    def names_dimensions(self) -> bool:
        """Ob die Maße von vorn als Projektparameter angelegt werden sollen (§13).

        Falsch, wenn der Dialog den Haken gar nicht trägt — dann gibt es
        nichts zu benennen, und der Aufrufer braucht keinen zweiten Fall.
        """
        return self._naming is not None and self._naming.isChecked()

    def offers_naming(self) -> bool:
        """Ob der Dialog den Haken *Maße als Parameter anlegen* trägt."""
        return self._naming is not None

    def values(self) -> dict[str, Any]:
        """Was der Nutzer eingetragen hat, fertig für die Operationsparameter."""
        from app.ui.filament_picker import FilamentField
        from app.ui.sketch_editor import SketchField

        collected: dict[str, Any] = {}
        for entry in self.spec.params.spec():
            if self.spec.name == "create_seal" and entry.name in _SEAL_PATH_COMPANIONS:
                continue
            editor = self._editors[entry.name]
            if isinstance(editor, SealPathField):
                collected.update(editor.selection())
            elif isinstance(
                editor,
                FeatureSetField | EdgeSetField | ContourField | OrganizerLayoutField | PointsField,
            ):
                collected[entry.name] = editor.value()
            elif isinstance(editor, MaterialField):
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
            elif isinstance(
                editor, ImageSourceField | ArmatureField | ArmatureSummary | StrokeSummary
            ):
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


_SKETCH_EPS = 0.01
"""Ab wann eine getippte Zahl als neues Maß gilt und nicht als Anzeige.

Hundertstelmillimeter: feiner als die zweistellige Anzeige und gröber als der
Rest, den der Löser auf seiner Toleranz stehen lässt. Zu klein gewählt, hielte
eine Rundungsdifferenz den Dialog für eine Ansage und er streckte im Kreis; zu
groß, verschluckte er eine echte Änderung.
"""
