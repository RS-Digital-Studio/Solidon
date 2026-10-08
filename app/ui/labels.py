"""Kurze Texte, auf die sich mehrere Teile der Oberfläche einigen müssen.

Ein Merkmal wird in der Viewport-Überlagerung, im Objektbaum und in der
Statusleiste gleich geschrieben — ``hole_3 · ⌀4.2``. Ein Ort dafür heißt: der
Name, den der Nutzer liest, ist der Name, den der Agent benutzt (§18.5,
Leitprinzip 5).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, Literal, cast

from PySide6.QtCore import QDate, QDateTime, QEvent, QLocale, QObject, QSize, Qt, Signal
from PySide6.QtGui import QColor, QShowEvent, QValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QHBoxLayout,
    QSlider,
    QStyle,
    QToolButton,
    QWidget,
)

from app import i18n
from app.core import discover
from app.core.activation import Activation
from app.core.export.slicer_profiles import model_name
from app.core.geom.mesh import MeshData, face_components
from app.core.perceive.actions import measure_explanation, measure_qualifier
from app.core.perceive.groups import FunctionalGroup, GroupMeasure
from app.core.registry import MENU_GROUPS as MENU_GROUPS
from app.core.registry import REGISTRY
from app.core.registry import group_title as group_title
from app.core.registry.surfaces import _CHOICE_NAMES as _CHOICE_NAMES
from app.core.registry.surfaces import SIDE_NAMES
from app.core.registry.surfaces import choice_label as _choice_label
from app.core.types import (
    Document,
    Feature,
    FeatureId,
    Finding,
    PrinterProfile,
    SceneObject,
    measure_status,
    thread_is_tapered,
)
from app.core.units import (
    DEGREE_UNIT,
    LengthUnit,
    decimals_for,
    format_area,
    format_length,
    format_length_bound,
    format_volume,
    from_mm,
    to_mm,
)
from app.i18n import Figure, TranslatableText, _, get_language, tr

# Die Zuordnung Kategorie → Menü (MENU_GROUPS, group_title) lebt seit der
# Agent-Vertiefung (4.3) im Register: neben Leiste und Kontextmenü braucht sie
# jetzt auch der Kern — die Werkzeugbeschreibungen nennen den Menüort, damit
# der Chat als Suchfeld taugt (§2.6). Die Nutzer der Oberfläche importieren
# beide weiter von hier; der Import darüber ist die Weiterleitung.


def step_number(document: Document | None, op_id: int) -> int:
    """Sichtbare Position eines Schritts; interne Kennungen bleiben unverändert.

    Eine Quelle mit den Sätzen des Kerns: ``scene.history.step_position``.
    """
    from app.core.scene.history import step_position

    return step_position(document.ops, op_id) if document is not None else op_id


def localised(text: str) -> str:
    """Setzt das Dezimaltrennzeichen der Anzeigesprache ein.

    Der Kern rechnet und schreibt mit Punkt — das ist richtig, dort ist eine
    Zahl ein Wert und keine Anzeige. Nur kam sie so auch beim Nutzer an: im
    Objektbaum standen die Maße mit Punkt, vierzig Pixel neben einem
    Eingabefeld mit Komma. Zwei Schreibweisen derselben Zahl im selben Blick.

    Gefragt wird ``QLocale`` und nicht die Sprache selbst, weil die
    Eingabefelder es ebenso tun — eine Quelle, oder das Problem kommt an der
    nächsten Stelle wieder.
    """
    separator = QLocale().decimalPoint()
    # Ein schlichter Text: Eine ``Figure`` des Kerns, hier schon lokalisiert,
    # schriebe sich als Platzhalterwert sonst ein zweites Mal um.
    text = str(text)
    return text.replace(".", separator) if separator != "." else text


#: Die drei Bedeutungen eines Projektparameters (§13), als feste Auswahl.
#:
#: Ein freies Einheitenfeld ist bei Maßen gefährlich: ``cm`` sieht plausibel
#: aus, der Kern rechnet aber weiterhin in Millimetern. Längen bleiben deshalb
#: in der Kerneinheit; Winkel und einheitenlose Anzahlen sind die beiden anderen
#: Bedeutungen. Dieselbe Liste bedient Parameterdialog, linke Leiste und
#: Rezeptdialog, damit ein Projektparameter überall dieselbe Sprache spricht.
PARAMETER_UNITS: Final[tuple[tuple[str, TranslatableText], ...]] = (
    ("mm", _("mm — Länge")),
    (DEGREE_UNIT, _("Grad — Winkel")),
    ("", _("ohne Einheit")),
)


def fill_parameter_units(box: QComboBox, selected: str = "mm") -> None:
    """Füllt *box* mit den festen Parametereinheiten und wählt *selected*.

    Eine alte Projektdatei kann einen freien Wert tragen. Er wird sichtbar als
    zusätzlicher Eintrag erhalten, nie still als Millimeter umgedeutet. Tippen
    lässt die Auswahl trotzdem nicht zu: Neue Werte kommen nur aus der
    freigegebenen Liste.
    """
    box.clear()
    box.setEditable(False)
    for code, label in PARAMETER_UNITS:
        box.addItem(str(label), code)
    index = box.findData(selected)
    if index < 0:
        unknown_label = str(tr("{unit} — wird nicht umgerechnet").format(unit=selected or "?"))
        box.addItem(unknown_label, selected)
        index = box.count() - 1
    box.setCurrentIndex(index)


#: Die Einheit, in der die Oberfläche Längen schreibt (§19.3).
#:
#: **Ein Zustand, wie die Sprache einer ist.** Die Einstellung gab es seit P0;
#: gelesen hat sie dann die Statusleiste, der Objektbaum und die Kopfzeile —
#: drei Stellen, weil drei sie durchgereicht bekamen. Die anderen elf
#: Längenausgaben standen weiter auf der Vorgabe „mm": der ganze
#: Skizzeneditor, die Analyseleiste, die Schnittleiste und die
#: Merkmalsbeschriftungen. Wer auf Zoll stellte, las im selben Fenster beides,
#: und im Skizzeneditor eine Zahl ohne Einheit dazu.
#:
#: Durch vierundzwanzig Konstruktoren zu reichen war der Weg dorthin, und er
#: hätte beim nächsten Widget wieder eine Stelle vergessen — ``labels.length``
#: rufen Funktionen ohne Widget (die Merkmalsbeschriftung steht in der
#: Überlagerung, im Objektbaum und in der Statusleiste). Deshalb ist die
#: Einheit ein Prozesszustand. Er liegt in ``app.i18n`` neben der Sprache,
#: weil auch der Kern Text mit Längen fertig ausliefert (die Einheitenfrage
#: beim Einlesen, RM-358 W1-1); hier steht nur der Zugang der Oberfläche.
#:
#: **Ein ausdrücklich übergebenes Argument gewinnt.** Das ist kein zweites
#: Verzeichnis, sondern ein Vorrang: Wer eine Einheit nennt, meint sie.


def set_display_unit(unit: LengthUnit) -> None:
    """Stellt die Anzeigeeinheit für den ganzen Prozess (§19.3).

    Der Kern bleibt bei Millimetern — hier wird nur geschrieben, nicht
    gerechnet.
    """
    i18n.set_display_unit(unit)


def display_unit() -> LengthUnit:
    """Die eingestellte Anzeigeeinheit."""
    return cast(LengthUnit, i18n.display_unit())


def read_number(text: str) -> float | None:
    """Eine getippte Zahl nach der Leseregel von :class:`NumberSpin`.

    Das letzte Trennzeichen ist das Dezimaltrennzeichen, alle davor sind
    Tausendertrennungen: „12,5", „12.5", „1.234,5" und „1,234.5" lesen sich
    alle richtig. ``None`` heißt: das ist keine Zahl.
    """
    raw = text.strip()
    if not raw:
        return None
    last = max(raw.rfind(","), raw.rfind("."))
    if last >= 0:
        head = raw[:last].replace(",", "").replace(".", "")
        raw = f"{head}.{raw[last + 1 :]}"
    try:
        return float(raw)
    except ValueError:
        return None


CircleMeasure = Literal["diameter", "radius"]

#: Wie ein Kreismaß gezeigt und eingegeben wird — als Durchmesser oder als
#: Radius. Ein Zustand wie die Anzeigeeinheit, aus demselben Grund: Das
#: Kreisfeld der Skizze, jedes ``diameter``-Feld eines Dialogs und die
#: Maßkarte am Kreis sollen dieselbe Antwort geben (Robert, 02.09.2026: „ein
#: Umschalten zwischen Radius und Durchmesser bei den jeweiligen Eingaben").
#: Gespeichert wird immer der Durchmesser — der Drucker spricht in
#: Durchmessern und die Norm auch; der Radius ist eine Anzeige davon.
_CIRCLE_MEASURE: CircleMeasure = "diameter"


class _MeasureViews(QObject):
    """Der Rundruf zum Zustand darüber — ein Sender, beliebig viele Ohren.

    ``set_display_unit`` daneben kommt ohne aus: Das Hauptfenster ruft die
    Ansichten dort einzeln nach, und der Docstring von
    ``MainWindow.set_display_unit`` sagt auch warum — „ein Zustand wirkt erst,
    wenn etwas ihn wieder liest". Für das Kreismaß fehlte genau dieses
    Nachrufen: Über den Knopf im Skizzeneditor stimmte alles, über den
    Einstellungsdialog blieb der Knopf auf dem Zeichen der alten Ansicht
    stehen, bis jemand ein Maßfeld neu setzte.

    Ein Signal statt einer Aufrufliste, weil der Zustand global ist und seine
    Leser es nicht sind: Der Skizzeneditor kann offen sein oder nicht, und
    einer, der gerade neu gebaut wird, liest den Zustand ohnehin selbst.
    """

    circleMeasureChanged = Signal()


#: Die eine Instanz dazu. Sie lebt so lange wie das Modul; Empfänger melden
#: sich über ``weak_slot`` an, damit ein geschlossener Editor daran nicht
#: hängen bleibt.
measure_views = _MeasureViews()


def set_circle_measure(kind: CircleMeasure) -> None:
    """Stellt um, ob Kreismaße als Durchmesser oder Radius sprechen.

    Sendet nur bei echter Änderung: Der Einstellungsdialog setzt den Wert
    beim Schließen auch dann, wenn niemand ihn angefasst hat, und ein
    Rundruf darauf ließe jede offene Skizze ohne Anlass neu zeichnen.
    """
    global _CIRCLE_MEASURE
    if kind == _CIRCLE_MEASURE:
        return
    _CIRCLE_MEASURE = kind
    measure_views.circleMeasureChanged.emit()


def circle_measure() -> CircleMeasure:
    """Ob Kreismaße gerade als Durchmesser oder als Radius gezeigt werden."""
    return _CIRCLE_MEASURE


def circle_shown(diameter: float) -> float:
    """Ein gespeicherter Durchmesser, wie das Feld ihn zeigt."""
    return diameter / 2.0 if _CIRCLE_MEASURE == "radius" else diameter


def circle_stored(shown: float) -> float:
    """Was im Feld steht, als Durchmesser — so wird es gespeichert."""
    return shown * 2.0 if _CIRCLE_MEASURE == "radius" else shown


def circle_sign() -> str:
    """Das Zeichen vor einem Kreismaß: Ø oder R."""
    return "R" if _CIRCLE_MEASURE == "radius" else "Ø"


def circle_word() -> str:
    """Das Wort für ein Kreismaß, für Beschriftungen und Vorleser."""
    return str(tr("Radius") if _CIRCLE_MEASURE == "radius" else tr("Durchmesser"))


class TrackSlider(QSlider):
    """Ein Regler, der dorthin springt, wohin man klickt.

    **Qts Vorgabe ist seitenweise**, und das ist für einen Regler, mit dem man
    ein Teil durchfährt, die falsche Geste: Ein Klick ans andere Ende bewegt
    ihn um eine Seite, und bei einem 40 mm hohen Körper braucht man vierzig
    Klicks, um von unten nach oben zu kommen. Wer auf eine Stelle der Rinne
    zeigt, meint diese Stelle (Robert, 03.09.2026: „die Slider sind auch
    schwer zu bedienen").

    Dazu zwei Kleinigkeiten, die zur selben Geste gehören: Das Mausrad fährt
    in Seitenschritten statt in Einzelschritten — eine Radraste soll etwas
    bewegen —, und ein Zug bleibt ein Zug, weil der Klick den Griff unter den
    Zeiger setzt und Qt von dort weiterzieht.
    """

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Name
        if event.button() == Qt.MouseButton.LeftButton and not self._on_handle(event):
            self.setValue(self._value_at(event))
            event.accept()
            # Qt zieht ab hier weiter, als hätte man den Griff gegriffen.
        super().mousePressEvent(event)

    def wheelEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Name
        notches = event.angleDelta().y() / 120.0
        if notches:
            step = self.pageStep() or self.singleStep()
            self.setValue(self.value() + round(notches) * step)
            event.accept()
            return
        super().wheelEvent(event)

    def _on_handle(self, event: Any) -> bool:
        """Ob der Klick den Griff selbst getroffen hat — dann zieht Qt."""
        from PySide6.QtWidgets import QStyleOptionSlider

        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, self
        )
        return handle.contains(event.position().toPoint())

    def _value_at(self, event: Any) -> int:
        """Welcher Wert unter dem Zeiger liegt — die Griffbreite herausgerechnet."""
        from PySide6.QtWidgets import QStyleOptionSlider

        option = QStyleOptionSlider()
        self.initStyleOption(option)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderGroove, self
        )
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, self
        )
        if self.orientation() == Qt.Orientation.Horizontal:
            travel = groove.width() - handle.width()
            spot = event.position().toPoint().x() - groove.x() - handle.width() // 2
        else:
            travel = groove.height() - handle.height()
            spot = event.position().toPoint().y() - groove.y() - handle.height() // 2
        return int(
            QStyle.sliderValueFromPosition(
                self.minimum(),
                self.maximum(),
                int(spot),
                int(travel) or 1,
                self.orientation() == Qt.Orientation.Vertical,
            )
        )


class _WheelNeedsFocus(QObject):
    """Ein Rad über einem Feld ohne Fokus rollt die Seite, nicht den Wert."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt-Name
        if (
            event.type() == QEvent.Type.Wheel
            and isinstance(watched, QWidget)
            and not watched.hasFocus()
        ):
            # Ignoriert heißt bei Qt: weiter an das Elternteil — den
            # Rollbereich. Das Feld selbst bekommt das Ereignis nicht.
            event.ignore()
            return True
        return super().eventFilter(watched, event)


def wheel_needs_focus(widget: QWidget) -> None:
    """Das Mausrad dreht dieses Feld erst, wenn es den Fokus hat.

    In einem rollenden Fenster liegt der Zeiger beim Rollen zwangsläufig über
    Feldern, und Qt gibt eine Radraste über einem Drehfeld dem Feld: Im
    Merkmalfenster sprangen Werte, wo die Seite rollen sollte (Robert,
    16.09.2026: „hier sollten wir erst reinklicken müssen"). ``StrongFocus``
    nimmt dem Rad den Fokuswechsel, der Filter reicht die Raste ohne Fokus an
    den Rollbereich weiter. Wer ins Feld klickt, dreht danach wie gewohnt.
    Gilt für Dreh- und Auswahlfelder; ein Haken kennt kein Rad.

    **Ein zweiter Aufruf legt keinen zweiten Filter an**, sondern setzt den
    vorhandenen wieder nach vorn — Qt fragt den zuletzt angemeldeten Filter
    zuerst. So bleibt die Reihenfolge, wenn ein Feld seinen Besitzer wechselt
    und dessen Filter nach diesem kommt (``PlacementFlow._wire_floating``).
    """
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    helper = widget.findChild(_WheelNeedsFocus, options=Qt.FindChildOption.FindDirectChildrenOnly)
    widget.installEventFilter(helper if helper is not None else _WheelNeedsFocus(widget))


class NumberSpin(QDoubleSpinBox):
    """Ein Zahlenfeld, dem beide Trennzeichen dasselbe bedeuten.

    **Wer im deutschen Fenster „12.5" tippte, bekam 125.** Ohne Fehler, ohne
    Rückfrage: Qt liest den Punkt in einer deutschen Anzeigesprache als
    Tausendertrennung, und aus zwölf ein halb wurden hundertfünfundzwanzig
    Millimeter. Im englischen Fenster genau umgekehrt — „12,5" wurde 125. Ein
    Maß, das aus einem Datenblatt, einer Fundstelle im Netz oder der Gewohnheit
    des Nutzers kommt, trägt das Trennzeichen von dort und nicht das der
    Oberfläche.

    **Die Regel: Das letzte Trennzeichen ist das Dezimaltrennzeichen, alle
    davor sind Tausendertrennungen.** Damit liest das Feld „12.5", „12,5",
    „1.000,50" und „1,000.50" alle richtig, in jeder Sprache — und es braucht
    dafür nicht zu erraten, was gemeint war.

    Die erste Version tauschte einfach jeden Punkt gegen ein Komma, und das war
    ein neuer Fehler derselben Sorte: „1.000,50" wurde damit im deutschen
    Fenster zu 1,00. Sichtbar war es, aber um den Faktor tausend falsch. Was
    zweideutig **bleibt**, ist „1.000" ohne Nachkomma — nach dieser Regel eins.
    Angezeigt wird nie mit Tausendertrennung
    (``setGroupSeparatorShown`` steht auf falsch), also gibt es keine
    Schreibweise, die das Feld vormacht und dann nicht liest.
    ``DragValueBar.typed_value`` im Viewport entscheidet ähnlich, nur ohne die
    Gruppen.

    Fällt eine Tausendertrennung weg, wird der Text kürzer; ``validate`` hält
    die Einfügemarke deshalb im Text. Ohne wegfallende Gruppe ist der Tausch
    längentreu, und dann bleibt sie ohnehin, wo sie war.

    **Zwei Überschreibungen, zwei Wege.** ``validate`` deckt alles ab, was
    durch das Eingabefeld geht — Tippen, Einfügen, ``setText`` —, und weil es
    den getauschten Text zurückgibt, steht danach die Schreibweise der
    Sprache da. ``valueFromText`` deckt den Aufruf ohne diesen Weg ab; Qt
    ruft es selbst, und wer die Klasse benutzt, darf sich auf beide
    verlassen.
    """

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        """Nie niedriger als die Wunschhöhe.

        Fehlt einem Layout die Höhe, presst es den Fehlbetrag in die Felder
        darüber. Auf macOS ARM fiel dieses Feld dabei von 26 auf 22 Punkte
        (08.09.2026), und derselbe Fall stand am 26.08.2026 schon einmal da —
        Auswahlfelder mit 16 von 28. Eine Zahl, die man nicht mehr lesen kann,
        ist kein gesparter Platz: Wo es eng wird, gehört gescrollt, und dafür
        muss das Feld seine Untergrenze auch nennen.

        Die Breite bleibt, wie Qt sie meldet — dort ist Schrumpfen erlaubt und
        richtig, ein Zahlenfeld darf schmaler werden.
        """
        base = super().minimumSizeHint()
        return QSize(base.width(), max(base.height(), self.sizeHint().height()))

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt-Name
        """Die Untergrenze festschreiben, sobald die Höhe feststeht.

        **Der Hinweis allein genügt nicht.** Gemessen am Druckdialog: Das Feld
        meldete `minimumSizeHint` 23 und wurde trotzdem auf 18 gedrückt — hat
        ein Elternteil eine feste Höhe, verteilt Qt den Platz hart und
        unterschreitet den Hinweis. Ein ausdrücklich gesetztes Minimum kann es
        nicht unterschreiten; dann geht der Fehlbetrag dorthin, wo er
        hingehört, nämlich in den Rollbalken.

        Erst beim Anzeigen, weil `sizeHint` vorher die Schrift des Fensters
        noch nicht kennt.
        """
        super().showEvent(event)
        self.setMinimumHeight(max(self.minimumHeight(), self.sizeHint().height()))

    def _as_shown(self, text: str) -> str:
        """Dasselbe Maß mit dem Trennzeichen der Anzeigesprache.

        Das letzte Trennzeichen ist das Dezimaltrennzeichen, alle davor sind
        Tausendertrennungen und fallen weg.
        """
        separator = QLocale().decimalPoint()
        other = "." if separator == "," else ","
        last = max(text.rfind(separator), text.rfind(other))
        if last < 0:
            return text
        head = text[:last].replace(other, "").replace(separator, "")
        return head + separator + text[last + 1 :]

    def _as_grouped(self, text: str) -> str:
        """Dasselbe Maß, wenn *jedes* Trennzeichen eine Tausendertrennung ist."""
        separator = QLocale().decimalPoint()
        other = "." if separator == "," else ","
        return text.replace(other, "").replace(separator, "")

    def validate(self, text: str, pos: int) -> Any:
        """Angenommen wird, was in **einer** der beiden Lesarten eine Zahl ist —
        und zurückgegeben wird der getippte Text, unverändert.

        Der erste Versuch tauschte hier das Trennzeichen und gab den getauschten
        Text zurück. Qt übernimmt ihn dann ins Feld, und damit war die Absicht
        beim zweiten Tastendruck entschieden: Wer „1.000,50" tippte, sah nach dem
        Punkt „1," stehen, und die dritte Null fiel an ``decimals`` weg — heraus
        kam 100,50. Ein neuer Fehler derselben Sorte, nur in der anderen
        Richtung.

        Jetzt bleibt der Text, wie er getippt wurde, und geprüft wird gegen beide
        Lesarten. Gelesen wird erst beim Übernehmen, in :meth:`valueFromText`.
        """
        for reading in (self._as_shown(text), self._as_grouped(text)):
            # **``Any`` und kein ``cast``, und zwar wegen der Qt-Version.**
            # Zur Laufzeit kommt hier immer das Tripel aus Zustand, Text und
            # Position. Der Stub sagt dazu je nach PySide6 etwas anderes: bis
            # 6.11.1 ``object`` — dann braucht die Verengung einen ``cast`` —,
            # ab 6.11.2 das Tripel selbst — dann ist derselbe ``cast``
            # überflüssig und mypy meldet ``redundant-cast``. Dieselbe Datei
            # kann nicht beides sein; ``Any`` passt zu beiden und behauptet
            # nichts, was die eine oder andere Version widerlegt.
            checked: Any = super().validate(reading, min(pos, len(reading)))
            if checked[0] != QValidator.State.Invalid:
                return checked[0], text, pos
        return QValidator.State.Invalid, text, pos

    def _digits_only(self, text: str) -> str:
        """Der Text ohne Vor- und Nachsatz — die Zahl allein."""
        body = text.strip()
        prefix, suffix = self.prefix(), self.suffix()
        if prefix and body.startswith(prefix):
            body = body[len(prefix) :]
        if suffix and body.endswith(suffix):
            body = body[: -len(suffix)]
        return body.strip()

    def valueFromText(self, text: str) -> float:  # noqa: N802 - Qt-Name
        """Gelesen wird nach der Regel aus :meth:`_as_shown`.

        Selbst geparst und nicht über Qt: Nach dem Zusammenziehen der Gruppen
        stehen dort mehr Nachkommastellen, als ``decimals`` erlaubt („0,100"
        bei zwei Stellen), und Qts Auswerter gibt dann nicht die gerundete Zahl
        zurück, sondern null. Gerundet wird ohnehin beim Setzen.
        """
        shown = self._as_shown(text)
        try:
            return float(self._digits_only(shown).replace(QLocale().decimalPoint(), "."))
        except ValueError:
            return super().valueFromText(shown)


def limit_sentence(value: str, limit: str, *, above: bool) -> str:
    """Warum eine getippte Zahl nicht angenommen wird — mit der Grenze beim Namen."""
    if above:
        return tr("{value} liegt über der Obergrenze {limit}.").format(value=value, limit=limit)
    return tr("{value} liegt unter der Untergrenze {limit}.").format(value=value, limit=limit)


class _BoundedBehavior:
    """Ein Zahlenfeld, das eine Zahl jenseits seiner Grenzen **ablehnt**, statt sie zu kürzen.

    Ein ``QDoubleSpinBox`` mit Obergrenze 100 nimmt beim Tippen von „150“ die
    Null nicht an: Qts Prüfung nennt „150“ ungültig, die Taste verfällt, und die
    Eingabetaste übernimmt „15“. Gemessen an der Parameterleiste (Durchsicht
    0.5.1): Obergrenze 100, getippt 150, im Modell stand danach 15 — ohne ein
    Wort. Hier gilt die Regel des Zeichnens (``zeichenflaeche.md``): **Beim
    Tippen wird abgelehnt, beim Drehen geklemmt**, und die abgelehnte Zahl
    bleibt markiert im Feld stehen.

    * ``validate`` lässt eine Zahl außerhalb der Grenzen als Zwischenstand zu —
      keine Ziffer verfällt.
    * Eingabetaste und Fokuswechsel übernehmen sie nicht: ``valueRefused``
      meldet die getippte Zahl, das Feld behält sie, markiert. Wer anzeigt,
      nennt die Grenze (:func:`limit_sentence`) und den Weg, sie zu ändern.
    * Pfeile und Rad klemmen an der Grenze, wie Qt es ohnehin tut.
    * Ein geleertes Feld mit Sondertext nimmt den Sonderwert an
      (:meth:`_empty_is_special`).

    Die Qt-Grenzen bleiben die echten Grenzen — die Breite des Feldes misst
    sich an ihnen, und ``value()`` liegt nie außerhalb.
    """

    def _empty_is_special(self: Any, text: str) -> bool:
        """Ob das Feld leer ist und einen Sondertext trägt — dann gilt der Sonderwert.

        Wer die Zahl löscht, meint, was der Sondertext sagt: „Oberkante“,
        „automatisch“, „Vorgabe des Slicers“. Qt nannte den leeren Text einen
        Zwischenstand, Eingabetaste und Fokuswechsel stellten still die vorige
        Zahl zurück, und zurück führten nur Pfeil und Rad bis unter die
        kleinste Zahl — an einer Welthöhe ohne Untergrenze eine Million
        Millimeter tief (RM-526).
        """
        # Qt lässt die Einheit stehen, wenn die Zahl gelöscht wird („ mm“), und
        # ``_digits_only`` trennt sie nur mit ihrem Leerzeichen ab.
        body = text.strip().removeprefix(self.prefix().strip())
        return (
            bool(self.specialValueText()) and not body.removesuffix(self.suffix().strip()).strip()
        )

    def stepBy(self: Any, steps: int) -> None:  # noqa: N802 - Qt-Name
        """Aus dem Sonderwert heraus beginnt ein Schritt nach oben am ``special_start``.

        Der Sonderwert eines ``optional``-Feldes sitzt eine Stufe unter der
        Untergrenze, an einer Welthöhe ohne Grenze eine Million Millimeter tief;
        ein Pfeil nach oben führte von „Oberkante“ auf -999 999,01 mm (Review
        RM-526, K5).
        """
        start = getattr(self, "special_start", None)
        if (
            start is not None
            and steps > 0
            and self.specialValueText()
            and self.value() <= self.minimum()
        ):
            self.setValue(start)
            return
        NumberSpin.stepBy(self, steps)

    def valueFromText(self: Any, text: str) -> float:  # noqa: N802 - Qt-Name
        """Wie :class:`NumberSpin`; ein geleertes Feld mit Sondertext ist der Mindestwert."""
        if self._empty_is_special(text):
            return float(self.minimum())
        return float(NumberSpin.valueFromText(self, text))

    def validate(self: Any, text: str, pos: int) -> Any:
        """Wie :class:`NumberSpin` — nur ist eine Zahl jenseits der Grenzen ein
        Zwischenstand und kein Tippfehler.

        **Nur jenseits der Grenzen, und nur mit erlaubter Stellenzahl.** Eine
        Nachkommastelle zu viel („1,875“ bei zwei Stellen) bleibt Qts Urteil:
        Die Taste verfällt, und übernommen wird 1,87 wie im gewöhnlichen Feld.
        Als Zwischenstand verwarf die Eingabetaste sonst die ganze Zahl und
        stellte still den alten Wert zurück (Code-Review 0.5.1, U-1).
        """
        if self._empty_is_special(text):
            return QValidator.State.Acceptable, text, pos
        checked: Any = NumberSpin.validate(self, text, pos)
        if checked[0] != QValidator.State.Invalid:
            return checked
        number = self._typed_number(text)
        if number is not None and self._places(text) <= self.decimals() and self._outside(number):
            return QValidator.State.Intermediate, text, pos
        return checked

    def _typed_number(self: Any, text: str) -> float | None:
        """Die getippte Zahl, gleich ob innerhalb der Grenzen — ``None`` ohne Zahl."""
        body = self._digits_only(self._as_shown(text))
        if not re.fullmatch(r"[+-]?\d+(?:[.,]\d*)?", body):
            return None
        return float(body.replace(",", "."))

    def _places(self: Any, text: str) -> int:
        """Wie viele Nachkommastellen getippt sind."""
        body = self._digits_only(self._as_shown(text))
        _whole, separator, fraction = body.replace(",", ".").partition(".")
        return len(fraction) if separator else 0

    def _outside(self: Any, number: float) -> bool:
        """Ob eine Zahl jenseits der Grenzen liegt — auf die halbe Anzeigestufe."""
        slack = 0.5 * 10.0 ** -self.decimals()
        return bool(number > self.maximum() + slack or number < self.minimum() - slack)

    def name_limits(self: Any, low: float | None, high: float | None) -> None:
        """Welche Grenzen der Satz nennt, wo sie von den Qt-Grenzen abweichen.

        Ein Feld mit „wie gemessen“ trägt seinen Sonderwert eine Stufe unter
        dem Mindestwert (``setSpecialValueText``); genannt wird der Mindestwert
        des Schemas, nicht die Stufe darunter („-0,01 mm“ statt 0, U-3).
        ``None`` heißt: die Qt-Grenze.
        """
        self._named_limits = (low, high)

    def refused_value(self: Any) -> float | None:
        """Die getippte Zahl, wenn sie außerhalb der Grenzen liegt — sonst ``None``."""
        number = self._typed_number(self.lineEdit().text())
        if number is None or not self._outside(number):
            return None
        return float(number)

    def refusal(self: Any, unit: str = "") -> str:
        """Der Satz zur abgelehnten Zahl, in der Schreibweise des Feldes — leer ohne Ablehnung.

        ``unit`` für ein Feld, dessen Einheit daneben steht statt im Feld (die
        Parameterleiste führt sie in einer eigenen Auswahl).
        """
        number = self.refused_value()
        if number is None:
            return ""
        above = number > self.maximum()
        low, high = self._named_limits
        if above:
            limit = high if high is not None else self.maximum()
        else:
            limit = low if low is not None else self.minimum()
        suffix = self.suffix() or (f" {unit}" if unit else "")
        return limit_sentence(
            self.textFromValue(number) + suffix, self.textFromValue(limit) + suffix, above=above
        )

    def interpretText(self: Any) -> None:  # noqa: N802 - Qt-Name
        """Eine abgelehnte Zahl bleibt stehen, auch wenn jemand von außen auswertet.

        Der Operationsdialog wertet vor dem Übernehmen jedes Zahlenfeld aus
        (``can_accept``); Qt setzte dabei den vorigen Wert zurück, und die
        Ablehnung wäre still verschwunden.
        """
        if self.refused_value() is None:
            NumberSpin.interpretText(self)

    def keyPressEvent(self: Any, event: Any) -> None:  # noqa: N802 - Qt-Name
        """Die Eingabetaste übernimmt keine Zahl jenseits der Grenzen — und
        schickt sie auch nicht an den Hauptknopf des Dialogs weiter."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            refused = self.refused_value()
            if refused is not None:
                self.selectAll()
                self.valueRefused.emit(refused)
                event.accept()
                return
        NumberSpin.keyPressEvent(self, event)

    def focusOutEvent(self: Any, event: Any) -> None:  # noqa: N802 - Qt-Name
        """Der Fokuswechsel verwirft die abgelehnte Zahl nicht still.

        Qt setzte sonst den alten Wert zurück; der Text bleibt stehen, und der
        Anzeigende sagt warum.
        """
        refused = self.refused_value()
        typed = self.lineEdit().text()
        NumberSpin.focusOutEvent(self, event)
        if refused is not None:
            self.lineEdit().setText(typed)
            self.valueRefused.emit(refused)

    def hideEvent(self: Any, event: Any) -> None:  # noqa: N802 - Qt-Name
        """Auch Aus- und Einblenden verwerfen die abgelehnte Zahl nicht still.

        Qt wertet beim Verbergen eine offene Eingabe aus und schreibt beim
        Einblenden den Wert neu ins Feld — beides an :meth:`interpretText`
        vorbei. Ein Feld, das einer Wahl folgt oder auf einem anderen Reiter
        steht, kam so mit dem alten Wert und ohne Ablehnung zurück. Ob eine
        verborgene Ablehnung etwas sperrt, entscheidet der Anzeigende — meist
        nicht, denn das Feld wirkt gerade nicht.
        """
        refused = self.refused_value()
        typed = self.lineEdit().text()
        NumberSpin.hideEvent(self, event)
        if refused is not None:
            self.lineEdit().setText(typed)

    def showEvent(self: Any, event: Any) -> None:  # noqa: N802 - Qt-Name
        """Siehe :meth:`hideEvent`."""
        refused = self.refused_value()
        typed = self.lineEdit().text()
        NumberSpin.showEvent(self, event)
        if refused is not None:
            self.lineEdit().setText(typed)


class BoundedSpin(_BoundedBehavior, NumberSpin):
    """Ein Zahlenfeld, das eine Zahl jenseits ihrer Grenzen stehen lässt."""

    valueRefused = Signal(float)
    """Eine getippte Zahl liegt außerhalb der Grenzen und wurde nicht übernommen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        NumberSpin.__init__(self, parent)
        self._named_limits: tuple[float | None, float | None] = (None, None)
        self.special_start: float | None = None
        """Wohin ein Schritt aus dem Sonderwert führt (:meth:`stepBy`) — sonst Qts Stufe."""


class LengthSpin(NumberSpin):
    """Ein Zahlenfeld für eine Länge — außen die Anzeigeeinheit, innen Millimeter.

    Die dreizehn Längenfelder der Leisten waren gewöhnliche ``QDoubleSpinBox``
    mit ``setSuffix(f" {DISPLAY_UNITS[0]}")``, also fest auf Millimeter, und
    ihre Leisten lasen ``value()`` und gaben es dem Kern. Nur das Suffix zu
    tauschen wäre deshalb kein halber Schritt gewesen, sondern ein falscher:
    „20,00 in" über einem Wert von 20 mm behauptet 20 Zoll.

    Hier stehen beide Seiten zusammen. Wer eine Länge setzt oder liest, tut es
    in **Millimetern** (``value_mm``, ``set_value_mm``, ``set_range_mm``) — was
    im Feld steht, ist eine Anzeige. Damit ist die Umrechnung an einer Stelle
    und nicht dreizehnmal, und eine Lesestelle, die sie vergisst, gibt es
    nicht: ``value()`` heißt hier nicht mehr, was der Kern will.

    **Eine gab es doch, und sie hieß ``valueChanged``.** Qts Signal trägt die
    Zahl aus dem Feld, also einen Anzeigewert; wer sie weitergibt, hat die
    Umrechnung übersprungen, ohne ``value()`` zu schreiben. Genau so kam der
    Pinselradius als 0,1969 in der Szene an, wo 5 mm gemeint waren. Deshalb
    gibt es ``valueChangedMm``: dieselbe Nachricht in der Einheit des Kerns.
    Wer an einer Länge etwas ändern will, hängt sich dort an — ``valueChanged``
    bleibt für alles, was den Wert fallen lässt und selbst ``value_mm()`` liest.

    **Der Rundungsschutz ist derselbe wie im Operationsdialog** und aus
    demselben Grund: 40 mm sind 1,5748 Zoll, und zurückgerechnet 39,99992 mm.
    Ein Feld, das nur angesehen wurde, gibt den Wert zurück, den es bekam.
    """

    valueChangedMm = Signal(float)
    """Der Wert hat sich geändert — in Millimetern, wie der Kern ihn braucht."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bounds_mm: tuple[float, float] = (0.0, 100.0)
        self._step_mm = 1.0
        self._value_mm: float | None = None
        self._unit: LengthUnit = display_unit()
        self._apply_unit()
        self.valueChanged.connect(self._announce_mm)

    def _announce_mm(self, _shown: float) -> None:
        """Sagt dieselbe Änderung noch einmal, in Millimetern.

        Das Argument von ``valueChanged`` wird bewusst nicht benutzt: es ist
        die Zahl aus dem Feld. Gefragt wird ``value_mm()``, damit der
        Rundungsschutz greift — sonst käme aus 40 mm in Zoll 39,99992.
        """
        self.valueChangedMm.emit(self.value_mm())

    # --- Setzen und lesen, immer in Millimetern ---------------------------------

    def set_range_mm(self, minimum: float, maximum: float) -> None:
        """Die Grenzen, wie der Kern sie kennt."""
        self._bounds_mm = (minimum, maximum)
        self._apply_unit()

    def set_step_mm(self, step: float) -> None:
        """Wie weit ein Klick auf den Drehknopf trägt — physisch, nicht als Zahl.

        Ohne das wäre die Schrittweite in Zoll dieselbe *Zahl* und damit der
        fünfundzwanzigfache Weg.
        """
        self._step_mm = step
        self._apply_unit()

    def set_value_mm(self, value: float) -> None:
        self._value_mm = value
        self.setValue(from_mm(value, self._unit))

    def value_mm(self) -> float:
        """Was im Feld steht, in Millimetern.

        Unverändert heißt: der Wert, der hereinkam — nicht seine Anzeige
        zurückgerechnet. Verglichen wird auf Anzeigegenauigkeit und nicht mit
        ``==`` (Regel 6).
        """
        shown = float(self.value())
        if self._value_mm is not None:
            step = 10.0 ** -self.decimals()
            if abs(from_mm(self._value_mm, self._unit) - shown) < step / 2.0:
                return self._value_mm
        return to_mm(shown, self._unit)

    # --- Einheitenwechsel -------------------------------------------------------

    def refresh_unit(self) -> None:
        """Übernimmt die eingestellte Anzeigeeinheit (§19.3).

        Der bisher gezeigte Wert wird mitgenommen, nicht die Zahl: Wer bei
        6 mm Pinselradius auf Zoll umstellt, will 0,2362 in sehen und nicht
        6 in.
        """
        if display_unit() == self._unit:
            return
        carried = self.value_mm()
        # Stumm, und das ist keine Bequemlichkeit: ``_apply_unit`` legt die
        # neue Spanne, während noch der Wert der alten steht. Bei 10 mm Raster
        # klemmt Qt die 10 auf die Zolluntergrenze 3,937 und feuert damit —
        # ein Empfänger, der daraufhin ``value_mm()`` liest, bekam 99,9998.
        # In Millimetern ändert sich hier nichts, also gibt es nichts zu
        # melden; wer die Anzeige nachziehen muss, tut das über
        # ``refresh_labels`` und nicht über einen Wertwechsel.
        was_blocked = self.blockSignals(True)
        try:
            self._apply_unit()
            self.set_value_mm(carried)
        finally:
            self.blockSignals(was_blocked)

    def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Name
        """Beim Einblenden nachziehen.

        Die Leisten leben, während der Einstellungsdialog offen ist; ohne diesen
        Haken stünde eine Leiste, die man danach hervorholt, in der alten
        Einheit. Das Fenster stößt offene Leisten zusätzlich an — beides, denn
        eine Leiste, die auf einen Anstoß von außen wartet, ist eine, die
        jemand vergessen kann.
        """
        self.refresh_unit()
        super().showEvent(event)

    def _apply_unit(self) -> None:
        """Suffix, Stellenzahl, Grenzen und Schrittweite für die aktuelle Einheit."""
        self._unit = display_unit()
        low, high = (from_mm(value, self._unit) for value in self._bounds_mm)
        # Erst die Feinheit, dann die Grenzen: Qt schneidet einen Wert auf die
        # eingestellte Stellenzahl, und bei zwei Stellen wäre eine Untergrenze
        # von 0,0039 Zoll eine von null.
        self.setDecimals(decimals_for(self._unit))
        self.setRange(low, high)
        self.setSingleStep(from_mm(self._step_mm, self._unit))
        # Ein Einheitenzeichen ist keine Übersetzung — es kommt aus der
        # Einheitentabelle (§11.1).
        self.setSuffix(f" {self._unit}")


class BoundedLengthSpin(_BoundedBehavior, LengthSpin):
    """Ein Längenfeld, das Grenzablehnung und Anzeigeeinheiten zusammenhält."""

    valueRefused = Signal(float)
    """Eine getippte Zahl liegt außerhalb der Grenzen und wurde nicht übernommen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        LengthSpin.__init__(self, parent)
        self._named_limits: tuple[float | None, float | None] = (None, None)

    def refresh_unit(self) -> None:
        """Nimmt beim Einheitenwechsel auch eine noch abgelehnte Zahl mit."""
        if display_unit() == self._unit:
            return
        refused = self.refused_value()
        if refused is None:
            LengthSpin.refresh_unit(self)
            return
        refused_mm = to_mm(refused, self._unit)
        was_blocked = self.blockSignals(True)
        try:
            self._apply_unit()
            if self._value_mm is not None:
                self.set_value_mm(self._value_mm)
            shown = from_mm(refused_mm, self._unit)
            self.lineEdit().setText(self.textFromValue(shown))
        finally:
            self.blockSignals(was_blocked)
        self.valueRefused.emit(shown)

    def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Name
        """Erst die Einheit nachziehen, dann die abgelehnte Zahl halten.

        Wie :meth:`LengthSpin.showEvent`, nur in dieser Reihenfolge: Bewahrt
        wird der Text, den :meth:`refresh_unit` schon umgerechnet hat.
        """
        self.refresh_unit()
        _BoundedBehavior.showEvent(self, event)


class RowCheckBox(QCheckBox):
    """Ein Haken ohne eigenen Text, der auf seiner ganzen Zeile antwortet.

    Ein ``QCheckBox`` ohne Text nimmt nur Klicks auf sein Kästchen an — Qt
    prüft in ``hitButton`` gegen Kästchen und Text, und ohne Text bleibt das
    Kästchen. In einer Formularzeile füllt das Feld aber die ganze Spalte:
    Gemessen am 13.09.2026 im Aushöhlen-Dialog waren 14 mal 14 Bildpunkte in
    einem Feld von 241 mal 14 heiß, alles rechts davon tot. Wer die Zeile
    traf und nicht das Kästchen, sah nichts geschehen (Robert: „bei Aushöhlen
    reagiert die Checkbox zum Öffnen ab und zu nicht").

    Hier antwortet das ganze Feld. Die Beschriftung links davon hängt
    :func:`caption_toggles` dazu — zusammen ist die Zeile so breit anklickbar
    wie die Zahlenfelder darüber und darunter.

    **Und so hoch.** Gemessen am 14.09.2026 auf der echten Plattform mit dem
    Stylesheet der Anwendung: Die Zahlenfelder des Aushöhlen-Dialogs sind 31
    Punkte hoch, der Haken ohne Text 12 — ein Klick acht Punkte über oder
    unter seiner Mitte traf nichts (``childAt``: „nichts"), obwohl er in der
    Zeile lag, die der Kunde meinte. Das ist der Rest von „ab und zu": nicht
    die Breite, die Höhe. Der Haken meldet deshalb die Höhe eines
    Eingabefelds unter dem geltenden Stil (:meth:`sizeHint`), gemessen an
    einem Drehfeld statt geraten; das Kästchen zeichnet der Stil mittig.
    """

    #: Ob die Beschriftung gerade gedrückt ist — gesetzt beim Druck, gelesen
    #: und gelöscht beim Loslassen.
    _caption_pressed: bool = False
    #: Die gemessene Höhe eines Eingabefelds — je Haken einmal, bis der Stil
    #: wechselt.
    _field_height: int | None = None

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        base = super().sizeHint()
        height = self._field_height
        if height is None:
            height = self._field_height = input_field_height(self)
        return QSize(base.width(), max(base.height(), height))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        base = super().minimumSizeHint()
        return QSize(base.width(), max(base.height(), self.sizeHint().height()))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 — Qt-Name
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.FontChange):
            self._field_height = None
        super().changeEvent(event)

    def hitButton(self, pos: Any) -> bool:  # noqa: N802 — Qt-Name
        return self.rect().contains(pos)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        """Ein Klick auf die Beschriftung schaltet den Haken.

        **Der Haken selbst ist der Filter, kein eigenes Objekt daneben.** Die
        erste Fassung hängte einen ``QObject``-Filter als Kind an die
        Beschriftung; ein Widget im Formular hat eine Lebensdauer, die Qt und
        Python gleich sehen.
        """
        # Gefragt wird der Ereignistyp, und die Taste liest ``button()`` ab,
        # das nur Mausereignisse tragen — ohne ``isinstance`` gegen
        # ``QMouseEvent``. Der Import dieses Namens riss am 14.09.2026
        # ``tests/test_filament_picker.py`` mit ``0xc0000374``; die Ursache war
        # nicht der Name, sondern PySides verzögerte Typinitialisierung, und
        # die ist seit dem 15.09.2026 abgeschaltet (``app/ui/__init__.py``).
        kind = event.type()
        # Der Doppelklick zählt als Druck: Qt schickt Druck, Loslassen,
        # Doppelklick, Loslassen — das Kästchen schaltet dabei zweimal, und
        # die Beschriftung soll nicht auf ihrer Hälfte anders antworten.
        presses = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)
        if kind in (*presses, QEvent.Type.MouseButtonRelease):
            button = getattr(event, "button", None)
            if button is None or button() != Qt.MouseButton.LeftButton:
                return super().eventFilter(watched, event)
            if kind in presses:
                self._caption_pressed = True
            else:
                pressed = self._caption_pressed
                self._caption_pressed = False
                # Losgelassen wird über der Beschriftung — wer mit gehaltener
                # Taste hinausfährt, hat es sich anders überlegt, wie am
                # Kästchen selbst (``hitButton``) und an jedem Knopf von Qt.
                position = getattr(event, "position", None)
                inside = (
                    position is not None
                    and isinstance(watched, QWidget)
                    and watched.rect().contains(position().toPoint())
                )
                # Der Weg über ``click`` und nicht über ``toggle``: Ein
                # gesperrter Haken bleibt gesperrt, und ``clicked`` kommt mit.
                if pressed and inside and self.isEnabled():
                    self.click()
                    return True
        return super().eventFilter(watched, event)


def input_field_height(reference: QWidget) -> int:
    """Die Höhe, die ein Eingabefeld unter dem geltenden Stil bekommt.

    Gemessen an einem Zahlenfeld der Anwendung (:class:`NumberSpin`), das
    kurz als Kind des fragenden Widgets entsteht und gleich wieder geht —
    nicht aus Padding und Rahmen des Stylesheets nachgerechnet, denn die
    Summe hängt an der Schrift und am Stil, und eine nachgerechnete Zahl
    stimmt genau einmal.
    """
    probe = NumberSpin(reference)
    probe.hide()
    probe.ensurePolished()
    height = int(probe.sizeHint().height())
    probe.deleteLater()
    return height


def caption_toggles(caption: QWidget | None, box: RowCheckBox) -> None:
    """Macht die Beschriftung einer Hakenzeile anklickbar.

    ``None`` ist erlaubt — ``QFormLayout.labelForField`` gibt es für Zeilen
    über beide Spalten zurück, und die haben keine Beschriftung. Der Filter
    ist der Haken selbst, deshalb nimmt die Signatur nur :class:`RowCheckBox`:
    Ein nackter ``QCheckBox`` bekäme den Zeigefinger, ohne dass ein Klick auf
    das Wort etwas täte — und mypy fängt die Stelle, die ihn das nächste Mal
    so baut.
    """
    if caption is None:
        return
    caption.installEventFilter(box)
    caption.setCursor(Qt.CursorShape.PointingHandCursor)


def length(value_mm: float, unit: LengthUnit | None = None, with_unit: bool = True) -> str:
    """Eine Länge, wie die Oberfläche sie schreibt.

    Ohne ``unit`` gilt die eingestellte Anzeigeeinheit — siehe
    :func:`display_unit`. Vorher stand hier „mm" als Vorgabe, und damit war
    jede Ausgabe, die keine Einheit durchgereicht bekam, gegen die Einstellung
    stumm.
    """
    return localised(format_length(value_mm, unit or display_unit(), with_unit))


def length_bound(value_mm: float, *, upper: bool) -> str:
    """Eine numerische Längenschranke mit Anzeigeeinheit und gerichteter Rundung."""
    return localised(format_length_bound(value_mm, display_unit(), upper=upper))


def compact_length(value_mm: float, unit: LengthUnit | None = None) -> str:
    """Dieselbe Länge, ohne Nachkommastellen, die nichts sagen.

    „60,00" braucht Platz und trägt genau so viel Auskunft wie „60" — die
    Nullen stehen dort, weil die Formatierung eine feste Stellenzahl hat,
    nicht weil jemand sie gemessen hätte. Wo ein Maß wirklich krumm ist,
    bleiben die Stellen stehen: „60,25" sagt etwas anderes als „60", und
    genau diesen Unterschied darf eine Abkürzung nicht verschlucken.

    Für Spalten und Zeilen, die eng sind. Wo Platz ist, gilt weiter
    :func:`length` — eine Anzeige, die zwischen zwei Schreibweisen springt,
    weil das Fenster schmaler wurde, ist schlimmer als eine lange.
    """
    return localised(compact_figure(value_mm, unit))


def compact_figure(
    value_mm: float, unit: LengthUnit | None = None, with_unit: bool = False
) -> Figure:
    """:func:`compact_length` für den Platzhalter eines übersetzbaren Satzes.

    Als :class:`~app.i18n.Figure` bekommt die Zahl ihr Dezimalzeichen erst beim
    Einsetzen; ein aufbewahrter Satz wie das Druckziel folgt so dem nächsten
    Sprachwechsel, ohne neu gebaut zu werden.
    """
    shown = unit or display_unit()
    text = format_length(value_mm, shown, with_unit=False)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    text = text or "0"
    return Figure(f"{text} {shown}" if with_unit else text)


def area(value_mm2: float, unit: LengthUnit | None = None) -> str:
    """Eine Fläche, wie der Nutzer sie liest — in seiner Einheit und mit
    seinem Trennzeichen."""
    return localised(format_area(value_mm2, unit or display_unit()))


def volume(value_mm3: float, unit: LengthUnit | None = None) -> str:
    """Ein Volumen, wie die Oberfläche es schreibt."""
    return localised(format_volume(value_mm3, unit or display_unit()))


#: Grundfarben nach Farbton, in Grad. Die Grenze gilt bis zu diesem Wert.
#:
#: Als ``_()`` und nicht als nackte Zeichenkette: der Sprachtest sammelt die
#: Texte aus dem Quelltext, und was nur als Variable in ein ``tr()`` geht,
#: findet er nicht — es stünde übersetzt im Katalog und gälte trotzdem als
#: verwaist.
_HUES: tuple[tuple[int, TranslatableText], ...] = (
    (15, _("Rot")),
    (45, _("Orange")),
    (70, _("Gelb")),
    (160, _("Grün")),
    (200, _("Türkis")),
    (260, _("Blau")),
    (290, _("Violett")),
    (345, _("Magenta")),
    (360, _("Rot")),
)

#: Was vier Dialoge sagen, wenn ein Arbeiter im Hintergrund abstürzt:
#: ComfyUI einrichten, Modell prüfen, Erzeugen, Installieren. Der Satz
#: stand viermal wortgleich im Quelltext — vier Stellen, an denen er sich
#: ändern kann, und der Kunde bekäme je nach Dialog eine andere
#: Formulierung für denselben Fall.
UNEXPECTED_CRASH = _("Dabei ist etwas schiefgegangen, womit hier niemand gerechnet hat.")


_BLACK = _("Schwarz")
_WHITE = _("Weiß")
_GREY = _("Grau")
_BROWN = _("Braun")


def colour_name(value: str) -> str:
    """Eine Farbe, wie man sie nennt — nicht, wie man sie schreibt.

    Über dem Filamentfeld stand „#4A90D9". Das ist der genaue Wert und
    beschreibt für niemanden eine Spule im Regal; wer sein Filament sucht, sucht
    Blau.

    Grob mit Absicht: Filamentfarben sind Regalfarben, und ein Name wie
    „Kornblumenblau" wäre genauer und trotzdem nicht die Spule, die dasteht.
    Der Hexwert bleibt daneben stehen, wo er hingehört — im Tooltip.
    """
    colour = QColor(value)
    if not colour.isValid():
        return value
    hue = colour.hslHue()
    saturation = colour.hslSaturation()
    lightness = colour.lightness()
    if lightness < 40:
        return str(_BLACK)
    if lightness > 225 and saturation < 40:
        return str(_WHITE)
    if saturation < 40:
        return str(_GREY)
    if hue < 0:
        return value
    for limit, name in _HUES:
        if hue <= limit:
            # Dunkles Orange heißt Braun, und nur dort — bei jeder anderen
            # Farbe ist Dunkelheit kein eigener Name.
            if name.msgid == "Orange" and lightness < 110:
                return str(_BROWN)
            return str(name)
    return value


#: Was ein Auswahlwert **bewirkt** — der Satz zum Namen aus ``surfaces.py``.
#:
#: Der Name benennt, der Satz erklärt: „Würfelgitter" sagt einem Kunden nicht,
#: wann er es wählen soll, und „Arachne" ist ein Eigenname ohne jede Auskunft.
#: Roberts Auftrag vom 26.08.2026 („mit Hovereffekten arbeiten, damit man
#: eher weiß was was eigentlich ist") landet für Auswahlwerte genau hier.
#:
#: Dieselben zwei Zusagen wie bei der Namenstabelle: **flach** — derselbe
#: Schlüssel bedeutet überall dasselbe, sonst bekommt der Wert einen eigenen
#: Schlüssel —, und **vollständig**: jeder benannte Wert trägt einen Satz,
#: denn fünfzehn erklärte von siebenundsechzig wären schlimmer als keine
#: (dieselbe Regel wie bei den note-Sätzen der Felder). Die Vollständigkeit
#: hält ``tests/test_translations.py`` fest. Selbstnamen („M4", „mm", „z")
#: stehen wie oben nicht drin — wo der Name die ganze Auskunft ist, wäre ein
#: Satz Tapete.
_CHOICE_NOTES: dict[str, TranslatableText] = {
    "mesh": _("Berechnet die Form als Dreiecksnetz."),
    "brep": _("Berechnet die Form mit dem exakten Kern aus Flächen und Kanten."),
    "motedis-2020-b6": _(
        "Für Motedis 20 × 20 mm, B-Typ, Nut 6; die Kopfkontur folgt den Herstellermaßen."
    ),
    "motedis-3030-b8": _(
        "Für Motedis 30 × 30 mm, B-Typ, Nut 8; die Kopfkontur folgt den Herstellermaßen."
    ),
    "2020": _("Behält ältere Maße bei. Für eine neue Passung das genaue Herstellerprofil wählen."),
    "3030": _("Behält ältere Maße bei. Für eine neue Passung das genaue Herstellerprofil wählen."),
    "4040": _("Behält ältere Maße bei. Für eine neue Passung das genaue Herstellerprofil wählen."),
    "relative": _("Addiert den eingegebenen Weg zur bisherigen Lage."),
    "absolute": _("Setzt den Bezugspunkt auf die eingegebenen Koordinaten."),
    "feature": _("Verwendet den Mittelpunkt des gewählten Merkmals am ersten Körper."),
    "corner_000": _("Verwendet diese Ecke des gemeinsamen Hüllquaders aller gewählten Körper."),
    "corner_001": _("Verwendet diese Ecke des gemeinsamen Hüllquaders aller gewählten Körper."),
    "corner_010": _("Verwendet diese Ecke des gemeinsamen Hüllquaders aller gewählten Körper."),
    "corner_011": _("Verwendet diese Ecke des gemeinsamen Hüllquaders aller gewählten Körper."),
    "corner_100": _("Verwendet diese Ecke des gemeinsamen Hüllquaders aller gewählten Körper."),
    "corner_101": _("Verwendet diese Ecke des gemeinsamen Hüllquaders aller gewählten Körper."),
    "corner_110": _("Verwendet diese Ecke des gemeinsamen Hüllquaders aller gewählten Körper."),
    "corner_111": _("Verwendet diese Ecke des gemeinsamen Hüllquaders aller gewählten Körper."),
    "whole_face": _("Füllt die gewählte ebene Fläche bis zum Rand; Bohrungen bleiben frei."),
    "keep": _("Außenmaße und Lage von Senkung, Stufen und Verengung bleiben erhalten."),
    "follow": _(
        "Alle Durchmesser ändern sich gemeinsam, auch die Öffnung einer Verengung; "
        "Breiten, Winkel und Tiefen bleiben."
    ),
    "legacy_raw": _("Behält die Achsen der Quelldatei bei, wie in älteren Projekten."),
    "gltf": _("Richtet GLB und GLTF von Y-oben auf Solidons Z-oben aus."),
    "clearance": _("Prüft das Spiel zwischen Öffnung und Gegenstück anhand ihrer Materialien."),
    "press": _("Prüft das Übermaß der Verbindung anhand ihrer Materialien."),
    "thread": _(
        "Prüft Innen- und Außengewinde auf gleiche Steigung und das vorgesehene Durchmesserspiel."
    ),
    "flush": _("Prüft, ob beide Flächen parallel und in derselben Ebene liegen."),
    "centred": _("Setzt die Unterseite auf die Mitte der gewählten Fläche."),
    "point_on_surface": _("Setzt die Unterseite auf den gewählten Punkt der Fläche."),
    "mouth": _("Die Position ist die Öffnung: Die Bohrung beginnt dort und geht ins Material."),
    # ``centre`` gilt an drei Stellen — Bohranker, Bezugspunkt der Grundkörper,
    # Fixpunkt von Drehen und Skalieren — und der Satz muss an allen dreien
    # wahr sein (flache Tabelle, wie beim Namen darüber).
    "centre": _("Die Mitte als Bezug — nach beiden Seiten geht es gleich weit."),
    "point": _(
        "Eine Stelle, die Sie selbst angeben — dieselbe für alle gewählten Teile, "
        "damit ihre Anordnung erhalten bleibt."
    ),
    # Die acht Texturmuster — der Dialog zeigt die Kachel dazu, der Satz sagt,
    # wofür das Muster taugt.
    "rib": _("Parallele Rillen quer über die Fläche — griffig und schnell gedruckt."),
    "wave": _("Weiche, wellenförmige Rillen — dekorativ und angenehm zu greifen."),
    "knurl_straight": _("Gerade Riffelung wie an Werkzeuggriffen — Halt gegen Verdrehen."),
    "knurl_diamond": _("Gekreuzte Riffelung mit Rautenmuster — der klassische rutschfeste Griff."),
    "hexagon": _("Sechseckfelder wie eine Bienenwabe — gleichmäßig und technisch."),
    "dimple": _("Kleine runde Vertiefungen — dezenter Halt ohne scharfe Kanten."),
    "voronoi": _("Unregelmäßige Zellen wie gesprungenes Glas — organisch, jedes Teil einzigartig."),
    "noise": _("Feines zufälliges Relief — kaschiert Schichtlinien und Fingerabdrücke."),
    "other": _(
        "Ein gelesenes Muster, das Solidon nicht selbst zeichnet. Wählen Sie einen der acht "
        "Stile, dann wird es damit neu gesetzt."
    ),
    "none": _("Nichts davon — es kommt nichts hinzu."),
    "xy": _("Jeder Zug wirkt gespiegelt auch jenseits der X- und der Y-Ebene."),
    "xz": _("Jeder Zug wirkt gespiegelt auch jenseits der X- und der Z-Ebene."),
    "yz": _("Jeder Zug wirkt gespiegelt auch jenseits der Y- und der Z-Ebene."),
    "xyz": _("Jeder Zug wirkt gespiegelt zu allen drei Ebenen zugleich."),
    # Der obere Umriss eines Übergangs (RM-147 E2). Der Satz sagt, was die
    # Wahl kostet: eine Zahl gegen eine zweite Zeichnung.
    "scaled": _("Der untere Umriss, verkleinert — Kegel- oder Pyramidenstumpf, mit einer Zahl."),
    # drawn gilt am Übergang und am Sweep (flache Tabelle): Der Satz muss
    # für beide wahr sein und nennt deshalb die Zeichnung, nicht das Teil.
    "drawn": _(
        "Eine eigene Zeichnung statt der gerechneten Form — für alles, was aus Zahlen nicht folgt."
    ),
    "arc": _("Ein gleichmäßiger Bogen aus Radius und Winkel — der Rohrbogen ohne Zeichnung."),
    "named": _("Genau die Kanten, die Sie darunter ankreuzen — nicht ihre ganze Gruppe."),
    "planar": _("Projiziert das Bild flach von oben — für Deckel und ebene Platten."),
    "cylindrical": _("Wickelt das Bild um die Achse — für Becher, Rohre und runde Gehäuse."),
    "spherical": _("Legt das Bild über eine Kugelform — für gewölbte Flächen."),
    "face": _("Wirkt nur auf der gewählten Fläche statt auf dem ganzen Körper."),
    "raised": _("Steht aus der Fläche hervor — gut lesbar, auch ohne Farbwechsel."),
    "engraved": _("In die Fläche vertieft — bündig und unempfindlich."),
    "regular": _("Der übliche Schnitt — schlank, für Höhen ab etwa fünf Millimetern."),
    "bold": _("Dickere Striche bei gleicher Höhe — die Wahl für kleine Buchstaben."),
    "italic": _("Geneigt, für Hervorhebungen."),
    "bold_italic": _("Geneigt und mit dickeren Strichen."),
    "flat": _("Wird flach aufgelegt, ohne sich der Form zu biegen."),
    "cylinder": _("Läuft einmal rund um den Körper."),
    "all": _("Alle zusammen — ohne Auswahl einer einzelnen."),
    "top": _("Nur an der Oberseite."),
    "bottom": _("Nur an der Unterseite."),
    "side": _("An den Seitenflächen — Ober- und Unterseite bleiben frei."),
    "horizontal": _("Waagerecht, parallel zum Druckbett."),
    "vertical": _("Senkrecht, quer zum Druckbett."),
    "linear": _("In gerader Reihe mit gleichem Abstand."),
    "circular": _("Im Kreis um einen Mittelpunkt verteilt."),
    "mirror": _("Eine Kopie jenseits einer Ebene, spiegelbildlich."),
    "inside": _("Die Außenmaße bleiben; die Wand wächst nach innen."),
    "outside": _("Das Teil wird zum Hohlraum; die Wand legt sich außen darum."),
    "raster": _("Die Wand entsteht über das Raster — das Teil wird ein Dreiecksmodell."),
    "unchanged": _("Nichts geschieht; der Befund sagt, woran es lag."),
    "origin": _(
        "Der Nullpunkt der Szene steht fest — ein Körper abseits davon ändert auch seinen Ort."
    ),
    "bed": _(
        "Die Mitte der Aufstandsfläche steht fest — beim Skalieren bleibt das Teil auf dem Bett."
    ),
    "corner": _("Gemessen von der Ecke aus — die Maße wachsen in eine Richtung."),
    "exact": _("An der tatsächlichen Oberfläche geprüft — genau, aber langsamer."),
    "box": _("Nur die Hüllquader verglichen — schnell, meldet aber auch Beinahe-Berührungen."),
    "pin": _("An diesem Teil entsteht der Stift."),
    "bore": _("An diesem Teil entsteht die Bohrung."),
    "foot": _("Der Fuß wird mitgedruckt."),
    "pocket": _("Eine Tasche nimmt einen gekauften Gummifuß auf."),
    "rectangle": _("Rechteckiger Umriss aus Länge und Breite."),
    "circle": _("Runder Umriss aus dem Durchmesser."),
    "polygon": _("Regelmäßiges Vieleck mit wählbarer Eckenzahl."),
    "slot": _("Langloch mit runden Enden — für Schrauben, die Spiel brauchen."),
    "bolt_circle": _("Löcher gleichmäßig auf einem Teilkreis — Flansch, Deckel, Nabe."),
    "hole_grid": _("Löcher in Spalten und Zeilen — Lüftungsgitter, Steckplatte, Lochblech."),
    "round": _("Runder Querschnitt mit gleichmäßigem Radius."),
    "rectangular": _("Rechteckiger Grundriss mit einstellbaren Ecken."),
    "screw": _("Deckel und Hals erhalten zusammenpassende Gewinde."),
    "push": _("Ein Kragen führt den abnehmbaren Deckel in der Öffnung."),
    "hinged": _("Ein mitgedrucktes Scharnier verbindet Deckel und Behälter."),
    "ellipse": _("Elliptischer Querschnitt aus Breite und Höhe."),
    "lower": _("Die untere Schale nimmt die Schraubenköpfe auf."),
    "upper": _("Die obere Schale nimmt die Muttern auf."),
    # Gilt für jede Ebene von *Abschneiden*, nicht nur für die Achse (N2 der
    # Nachprüfung RM-400): An einer Unterseite stimmte „bei Z unten“ nicht.
    "below": _(
        "Die Seite unter der Ebene bleibt: an einer Achse die mit den kleineren Werten, "
        "bei Z unten; an einer Fläche die Seite hinter ihr, im Körper."
    ),
    "above": _(
        "Die Seite über der Ebene bleibt: an einer Achse die mit den größeren Werten, "
        "bei Z oben; an einer Fläche die Seite, zu der sie zeigt."
    ),
    "along_axis": _("Senkrecht zu X, Y oder Z, auf Wunsch geneigt."),
    "at_face": _("Parallel zu einer ebenen Fläche, um den Abstand versetzt."),
    "through_edge": _("Die Ebene enthält eine gerade Kante und kippt um sie."),
    "through_points": _("Die Ebene geht durch drei Stellen, im Bild angeklickt."),
    "hex": _("Sechskantstift — hält die Teile verdrehsicher."),
    "dovetail": _(
        "Schwalbenschwanz: die Teile schieben sich ein und halten quer zur Fuge ohne Kleber."
    ),
    "snap": _("Schnapper: rastet beim Zusammendrücken ein und hält von selbst."),
    "honeycomb": _("Sechseckige Füllung — steif bei wenig Material, langsamer gedruckt."),
    "cubic": _("Gekippte Würfel — in allen Richtungen gleichmäßig fest, ein guter Standard."),
    "auto": _("Der passende Wert wird aus dem Zusammenhang bestimmt und zieht von selbst mit."),
    "ask": _(
        "Hat der Hohlraum mehrere Abschnitte, wird vor dem Entfernen gefragt, ob alle mitgehen."
    ),
    "ask_side": _(
        "Wird aus einer Durchgangsbohrung ein Sackloch, wird gefragt, welche Seite offen bleibt."
    ),
    "ask_twist": _(
        "Steht der untere Umriss genau zwischen zwei Ecken des oberen, wird gefragt, in welche "
        "Richtung der Übergang dreht."
    ),
    "counterclockwise": _("Gegen den Uhrzeigersinn, von oben auf die Zeichenebene gesehen."),
    "clockwise": _("Im Uhrzeigersinn, von oben auf die Zeichenebene gesehen."),
    "down": _("Beginnt an der Oberseite und läuft nach unten in den Körper."),
    "up": _("Beginnt an der Unterseite und läuft nach oben in den Körper."),
    "equal_distances": _("Die Fase nimmt beide Flächen gleich weit zurück."),
    "two_distances": _(
        "Die Fase nimmt die Bezugsfläche und die zweite Fläche verschieden weit zurück."
    ),
    "distance_angle": _("Ein Abstand auf der Bezugsfläche und der Winkel der Fase zu ihr."),
    "constant_radius": _("Ein Radius über die ganze Kante — die gewohnte Verrundung."),
    "pull_up": _("Das Teil wird nach oben schmaler — die Form wird nach oben abgezogen."),
    "pull_down": _("Das Teil wird nach unten schmaler — die Form wird nach unten abgezogen."),
    "pull_right": _("Das Teil wird nach rechts schmaler."),
    "pull_left": _("Das Teil wird nach links schmaler."),
    "pull_back": _("Das Teil wird nach hinten schmaler."),
    "pull_front": _("Das Teil wird nach vorn schmaler."),
    "neutral_start": _(
        "Das Maß bleibt dort, wo das Teil in Entformungsrichtung beginnt — bei „nach oben“ unten."
    ),
    "neutral_end": _(
        "Das Maß bleibt dort, wo das Teil in Entformungsrichtung endet — bei „nach oben“ oben."
    ),
    "neutral_height": _("Das Maß bleibt auf der eingegebenen Höhe; darunter wird es breiter."),
    "variable_radius": _(
        "Der Radius ändert sich vom Anfang zum Ende der Kante, auf Wunsch über Zwischenstellen."
    ),
    "right_side": _("Die Bohrung bleibt zur rechten Seite hin offen."),
    "left_side": _("Die Bohrung bleibt zur linken Seite hin offen."),
    "back_side": _("Die Bohrung bleibt zur Rückseite hin offen."),
    "front_side": _("Die Bohrung bleibt zur Vorderseite hin offen."),
    "top_side": _("Die Bohrung bleibt zur Oberseite hin offen."),
    "bottom_side": _("Die Bohrung bleibt zur Unterseite hin offen."),
    "chain": _("Bohrung und Senkung gehen zusammen weg — der ganze zusammenhängende Hohlraum."),
    "single": _("Nur der gewählte Abschnitt wird geschlossen; die übrigen bleiben stehen."),
    "aligned": _("Die Naht liegt übereinander an einer Kante — dort fällt sie am wenigsten auf."),
    "nearest": _("Die Naht liegt am jeweils nächsten Punkt — schnell, aber verstreut sichtbar."),
    "random": _(
        "Die Naht springt zufällig — keine durchgehende Linie, dafür überall kleine Punkte."
    ),
    "rear": _("Die Naht liegt gesammelt auf der Rückseite — die Schauseite bleibt frei."),
    "classic": _("Wandbahnen mit fester Breite — vorhersehbar und bewährt."),
    "arachne": _("Wandbahnen mit veränderlicher Breite — füllt dünne Stellen besser aus."),
    "gyroid": _(
        "Geschwungene Flächen, in alle Richtungen gleich fest — auch bei flexiblen Teilen beliebt."
    ),
    "grid": _("Gleichmäßige Reihen und Spalten."),
    "staggered": _("Jede zweite Reihe ist um einen halben Rasterabstand versetzt."),
    "lines": _("Parallele Bahnen, je Schicht gedreht — am schnellsten, am wenigsten fest."),
    "triangles": _("Dreiecksraster — sehr steif in der Ebene."),
    "tree": _("Äste wachsen um das Teil herum — sparsam und leicht zu entfernen."),
    "everywhere": _("Stützen überall, auch auf dem Teil selbst."),
    "build_plate": _("Stützen nur vom Druckbett aus — auf dem Teil selbst steht nichts."),
    "skirt": _("Eine Linie ums Teil, ohne es zu berühren — spült die Düse und prüft die Haftung."),
    "brim": _("Ein flacher Rand am Teil — mehr Haftfläche, nach dem Druck abzuziehen."),
    "raft": _(
        "Ein gedrucktes Floß unter dem Teil — beste Haftung, kostet Zeit und die Unterseite."
    ),
    "measured": _("Misst die Abweichung und meldet sie — genau, an großen Netzen langsam."),
    "fast": _("Vereinfacht wie die Anzeige, ohne Messung — auch große Netze in Sekunden."),
    "keyhole": _("Zwei Schlüssellöcher auf der Rückseite: unsichtbar auf Schrauben gehängt."),
    "screws": _("Zwei Laschen neben dem Halter mit gesenkten Löchern zum Anschrauben."),
    "pegboard": _("Zwei Haken mit Rastzunge für die Lochwand."),
    "clamp": _("Ein Bügel, der über die Kante einer Platte greift — ohne Bohren."),
    # Bajonett und Rastdrehscheibe: die Hälfte eines Paars aus denselben Maßen.
    "socket": _("Das Rohr mit den L-Schlitzen, an das Teil, das verschlossen wird."),
    "plug": _("Der Kragen mit den Nocken, an den Deckel."),
    "base": _("Boden mit Zapfen, Kragen, Rastmulden und den Öffnungen der Stellungen."),
    "disc": _("Die Scheibe mit Fenster, die auf die Führung geklipst wird."),
    # Die Bauformen des Stangenverbinders.
    "sleeve": _("Eine Aufnahme, senkrecht auf ihrem Boden."),
    "straight": _("Zwei Aufnahmen in einer Linie — eine Muffe mit Anschlag in der Mitte."),
    "elbow": _("Zwei Aufnahmen im rechten Winkel."),
    "tee": _("Drei Aufnahmen in einer Ebene: zwei in einer Linie, eine quer dazu."),
    "corner_3d": _("Drei Aufnahmen in drei Richtungen: zwei liegend, eine nach oben."),
    "cross": _("Vier Aufnahmen in einer Ebene, über Kreuz."),
    # Die Bauarten der Kanalnaht.
    "outer_sleeve": _("Die Hülse umgreift beide Segmente; der Kanal bleibt, wie er ist."),
    "inner_insert": _("Die Einlage liegt in beiden Segmenten und verengt den Kanal um ihre Wand."),
    # Die Platten und Öffnungen der Raumvorlage.
    "room_back": _("Die Wand hinten, über die ganze Raumlänge, mit Nuten für die Seitenwände."),
    "room_side": _("Eine Wand links oder rechts, mit Feder in die Nut der Rückwand."),
    "window": _("Mittig in der Wand, innen mit Falz für die Scheibe."),
    "door": _("Vom Boden aus nach oben, ohne Schwelle."),
    # Die Bewegungen des Fügewegs.
    "slide": _("Geradeaus entlang der Achse in die Endlage geschoben."),
    "turn": _("Um die Achse in die Endlage gedreht — ein Klappdeckel, ein Drehverschluss."),
    "slide_turn": _("Erst geradeaus eingesetzt, dann um die Achse gedreht — wie ein Bajonett."),
    "closest": _(
        "Wo sich die ersten beiden gewählten Teile am nächsten kommen — dort sitzt die Passung."
    ),
    "around": _(
        "Die Zeile läuft um eine Rundung herum, deren Achse quer zur Schrift steht — "
        "ein Becher, eine Dose."
    ),
    "along": _(
        "Die Zeile läuft an einer Rundung entlang, die Buchstaben biegen sich über ihre "
        "Höhe — ein Rohr, ein Griff."
    ),
    "barrel": _("Das Scharnier kommt beweglich aus dem Drucker; der Deckel entsteht aufgeklappt."),
    "loose_pin": _(
        "Gehäuse und Deckel bekommen Augen mit Bohrung, der Stift entsteht als eigenes Teil."
    ),
    "hinge_back": _("Die Achse liegt an der hinteren Seite der Öffnung."),
    "hinge_front": _("Die Achse liegt an der vorderen Seite der Öffnung."),
    "hinge_left": _("Die Achse liegt an der linken Seite der Öffnung."),
    "hinge_right": _("Die Achse liegt an der rechten Seite der Öffnung."),
    "custom_size": _(
        "Durchmesser und Steigung frei, etwa für ein Rohr. Ohne Steigung gilt die übliche zum "
        "Durchmesser."
    ),
    "to_the_bore": _(
        "Mit Senkkopf in einer Senkung, Zylinderkopf in einer Ansenkung und Außengewinde in "
        "einem Innengewinde."
    ),
    "plain_pin": _("Ein Zylinder, um das Spiel dünner als die Bohrung, ohne Kopf und Gewinde."),
}


#: Was hinter einem Wert-Schlüssel steht, in der Sprache des Nutzers.
#:
#: ``Finding.values`` und ``AppError.values`` tragen Zahlen, und ihre Schlüssel
#: sind Bezeichner: englisch, mit Unterstrich, mit Einheitensuffix. Die
#: Oberfläche schrieb sie **roh** hin — im Befund-Tooltip und in den
#: Einzelheiten eines Fehlers stand „oversize_mm: 12.4" und „open_edges: 6".
#: Das ist eine feste Zeichenkette in der Oberfläche mit einem Umweg (Regel 20),
#: und für den Leser ist es die Sorte Text, die man überliest statt liest.
#:
#: Die Einheit wird **nicht** eingetragen, sondern aus dem Suffix gelesen
#: (:data:`_VALUE_UNITS`): ``size_mm`` und ``size`` teilen sich einen Eintrag,
#: und ein neuer Schlüssel mit bekanntem Stamm ist damit schon übersetzt. Sie
#: erscheint am Wert und nicht hier — siehe :func:`value_text`.
#:
#: Vollständig gehalten wird die Liste nicht von Hand — von Hand heißt driften.
#: ``tests/test_value_labels.py`` liest jeden ``values=``-Schlüssel aus
#: ``app/core`` per AST und wird rot, sobald einer keine Beschriftung hat.
_VALUE_NAMES: dict[str, TranslatableText] = {
    "a": _("Erstes"),
    # Was eine Ausnahme selbst beisteuert (``_with_values`` in errors.py).
    # Sieben Schlüssel standen als rohes Englisch im Tooltip, weil der
    # Wächter nur Wörterbücher sah und keine Aufrufe.
    "action": _("Handlung"),
    "affected": _("Betroffene Transaktionen"),
    "after_components": _("Teile danach"),
    "anchor": _("Bezugspunkt"),
    "announced": _("Angekündigt"),
    "answer": _("Antwortanfang"),
    "area": _("Flächeninhalt"),
    "at": _("Position auf dem Fügeweg"),
    "at_feature": _("Bezugsmerkmal"),
    "attempted": _("Versuchte Rechenwege"),
    "before_components": _("Teile vorher"),
    "bodies": _("Körper"),
    "bores": _("Geschlossene Bohrungen"),
    "cell_width": _("Zellbreite"),
    "cells": _("Zellen"),
    "centre": _("Mittelpunkt"),
    "constraints": _("Bedingungen"),
    # Die Ecke, an der die Formschräge am Netz keine eindeutige Antwort hat (P6.4).
    "corner": _("Ecke"),
    "drop": _("Einhängeweg"),
    "dropped_call": _("Verworfener Aufruf"),
    "eroded": _("Wirklich abgetragen"),
    "exit_code": _("Rückgabewert"),
    "face": _("Fläche"),
    "fields": _("Felder"),
    "first": _("Erste Bedingung"),
    "first_layer": _("Erste Schicht"),
    # Der Befund „zu fein für diese Düse" nennt die Schrift, um die es geht —
    # bei acht zur Wahl ist das die halbe Auskunft.
    "font": _("Schrift"),
    "grip": _("Verengung"),
    "head_room": _("Kopftiefe"),
    # Was *Stift für Bohrung* gebaut hat (RM-536).
    "head_diameter": _("Kopfdurchmesser"),
    "countersink_angle": _("Senkwinkel"),
    "thread": _("Gewinde"),
    "angle": _("Winkel"),
    "intersection": _("Durchdringung"),
    "last_angle": _("Letzter Winkel"),
    "length": _("Länge"),
    # Wo ein Halt der Booleschen die kaputte Schale traf (RM-382); *Stelle
    # zeigen* fliegt dorthin, im Prüfbericht steht er als Ort des Befunds.
    "location": _("Stelle"),
    "narrowing": _("Verengung"),
    "nominal_side_clearance": _("Seitliches Nennspiel"),
    "normal": _("Richtung der Fläche"),
    "outer": _("Senkung"),
    "overlap": _("Überdeckung"),
    "overshoot": _("Überstand je Achse"),
    "pair": _("Gegenstückpaar"),
    "plane": _("Ebene"),
    "play": _("Spiel"),
    # ``geom.repair``: geglättete Falten, gezählt je Stelle (RM-550).
    "places": _("Stellen"),
    "points": _("Punkte"),
    "press": _("Pressmaß"),
    "previous": _("Bisher"),
    "recipe": _("Rezept"),
    # ``union.bore_*``: was vom Hohlraum der Bohrung nach dem Vereinigen frei bleibt.
    "remaining_volume": _("Freier Bohrungsraum"),
    "required_wall": _("Erforderliche Restwand"),
    "second": _("Zweite Bedingung"),
    # ``ingest.threemf``: was eine 3MF an Hilfsteilen und Aussparungen des
    # Slicers überging, bevor kein druckbarer Körper blieb.
    "skipped": _("Übersprungen"),
    "source_feature": _("Bohrung"),
    "source_object": _("Körper"),
    # ``edges.skipped``: wie viele Kanten einer Gruppe bearbeitet wurden.
    "worked": _("Bearbeitet"),
    # ``hollow.fewer_vents``: wie viele Entlüftungen Platz fanden.
    "placed": _("Gesetzt"),
    # ``resize_hole``: an welchen Seiten eine Bohrung austritt.
    "ends": _("Austrittsseiten"),
    "sliced": _("Mit Schichtanalyse geprüft"),
    "solver": _("Rechenstufe"),
    "stopped_at": _("Angehalten bei Schritt"),
    "taken": _("Vergeben"),
    "technology": _("Verfahren"),
    "thickness": _("Wandstärke"),
    "tool": _("Programm"),
    "actual": _("Tatsächlich"),
    "after": _("Nachher"),
    "alignment": _("Ausrichtung"),
    "allowed": _("Erlaubt"),
    "amount": _("Betrag"),
    "annotation": _("Anmerkung"),
    "app_major": _("Programmversion"),
    "axes": _("Achsen"),
    "axis": _("Achse"),
    "b": _("Zweites"),
    "before": _("Vorher"),
    "blocked_planes": _("Gesperrte Ebenen"),
    "code": _("Fehlerkennung"),
    # ``geom.lid``: ein Kragen, der in die Wand ragt — gewählte und freie Tiefe.
    "collar": _("Kragentiefe"),
    "board": _("Lochwand"),
    "bones": _("Knochen"),
    "bore": _("Bohrung"),
    "brush": _("Pinsel"),
    "candidates": _("Kandidaten"),
    "cavities": _("Hohlräume"),
    "chain": _("Kette"),
    "changes": _("Änderungen"),
    "character": _("Zeichen"),
    "choice": _("Wahl"),
    "choices": _("Auswahl"),
    "checked": _("Geprüft"),
    "clearance": _("Spiel"),
    # ``scene.fits``: die Grenzen des Spiels — ohne ``_mm``, denn die Einheit
    # kommt aus ``_VALUE_UNITS`` und steht am Wert, nicht in der Beschriftung.
    "clearance_min": _("Untere Grenze des Spiels"),
    "clearance_max": _("Obere Grenze des Spiels"),
    "comfortable": _("Grenze der Analysekarten"),
    "components": _("Komponenten"),
    "constraint": _("Bedingung"),
    "contours": _("Konturen"),
    "core": _("Kern"),
    "count": _("Anzahl"),
    "counted": _("Verarbeitet"),
    # ``fasteners.screw_hole``: der Durchmesser einer gerechneten Senkung.
    "countersink": _("Senkung"),
    "cut": _("Schnitt"),
    # ``slicer.profile_value_replaced``: was statt eines abgelehnten Herstellerwerts hinausgeht.
    "default": _("Vorgabe"),
    # ``ingest.threemf``: der Negativkörper aus dem Slicer, der keinen Körper trifft.
    "cutter": _("Aussparung"),
    "cycle": _("Zyklus"),
    # ``mesh_ops._too_fine``: die Dreieckszahl, auf die *Dreiecke verringern*
    # vor dem erneuten Versuch geht — am verringerten Netz nachgezählt.
    "decimate_to": _("Verringern auf"),
    # ``mesh_ops._smoothing_cost``: die Kantenlänge, auf die *Kanten
    # verfeinern* vor dem erneuten *Glätten* teilt — daran durchgespielt.
    "remesh_to": _("Verfeinern auf"),
    "dependencies": _("Begleitdateien"),
    "dependency": _("Begleitdatei"),
    "depth": _("Tiefe"),
    # ``export.tessellated``: wie weit die Dreiecke der Exportvernetzung von
    # den Flächen des exakten Körpers abweichen dürfen (RM-071).
    "deflection": _("Größte Abweichung"),
    "deviation": _("Abweichung"),
    # Die beiden Richtungen der Formabweichung einer Umwandlung (P4.0).
    "mesh_to_body": _("Netz zum Körper"),
    "body_to_mesh": _("Körper zum Netz"),
    # ``perceive.freeform``: wie viele Rundformen die Erkennung auf einer
    # Freiform wegließ — der Kunde liest die Zahl im Prüfbericht.
    "dropped": _("Weggelassen"),
    # ``perceive.voids_unreadable``: wie viele Schalen die Erkennung nicht
    # lesen konnte — ob eine davon Luft einschließt, bleibt offen.
    "shells": _("Schalen"),
    "body_diameter": _("Breiteste Stelle des Körpers"),
    "diameter": _("Durchmesser"),
    # ``geom.faces``: um wie viel eine Fläche versetzt werden sollte, als der
    # Körper dabei verschwand. „Weg" hieße im Italienischen „Percorso" — Pfad.
    "distance": _("Abstand"),
    "volume_change": _("Volumenänderung"),
    "widening": _("Senkung darüber"),
    "wrap_diameter": _("Durchmesser des Wickelzylinders"),
    "drawn_width": _("Gezeichnete Breite"),
    "detail": _("Einzelheit"),
    "edge": _("Kante"),
    "edges": _("Kanten"),
    "entry": _("Eintrag"),
    "entries": _("Einträge"),
    "estimated": _("Geschätzt"),
    "estimated_source": _("Quelle der Schätzung"),
    "measured_source": _("Quelle des G-Code-Werts"),
    "expected": _("Erwartet"),
    "got": _("Bekommen"),
    "expected_prefix": _("Erwarteter Anfang"),
    "extruder": _("Extruder"),
    "faces": _("Flächen"),
    # Die Flächen eines umgewandelten Körpers je Art (P4.0).
    "planes": _("Ebenen"),
    "cylinders": _("Zylinder"),
    "cones": _("Kegel"),
    "spheres": _("Kugeln"),
    "tori": _("Ringe"),
    "factor": _("Maßstab"),
    # Die Spule, die in der Druckdatei fehlt (``gcode.spool_left_out``) — mit
    # ihrem Namen, denn eine Werkzeugnummer sucht niemand im Regal.
    "filament": _("Filament"),
    # Was tatsächlich da war, wo eine Zahl verlangt wurde — beim Zerlegen die
    # Teile, die der Körper hat, gegen die Stückzahl im Feld.
    "found": _("Gefunden"),
    # Ohne das ``_mm`` des Werteschlüssels: ``value_label`` streift die
    # Einheiten-Endung, bevor es hier nachschlägt — wie bei ``eroded``.
    "fair_wall": _("Verlässlich ab"),
    # ``profile.printer_missing``: der Drucker, mit dem gerechnet wird, bis
    # der Kunde einen wählt.
    "fallback_printer": _("Gerechnet mit"),
    "feature": _("Merkmal"),
    "features": _("Merkmale"),
    "field": _("Feld"),
    "file": _("Datei"),
    "files": _("Dateien im Archiv"),
    "file_version": _("Dateiversion"),
    "findings": _("Befunde"),
    "first_kind": _("Erste Art"),
    "fit": _("Passung"),
    # ``fasteners.thread_at_hole``: der Nenndurchmesser, mit dem die Bohrung Kernloch bleibt.
    "fitting": _("Passender Nenndurchmesser"),
    "floor": _("Boden"),
    "flow_limit": _("Höchster Volumenstrom"),
    "format": _("Format"),
    "excess": _("Überstand"),
    "footprint": _("Standfläche"),
    "formats": _("Formate"),
    "free_depth": _("Freie Tiefe"),
    "free_dof": _("Offene Maße"),
    "from": _("Von"),
    "gap": _("Spalt"),
    # ``scene.fits``: woraus die Passung gerechnet wurde — exakt, Netz, gemischt.
    "geometry_source": _("Geometriequelle"),
    "given": _("Vorhanden"),
    "grams": _("Gramm"),
    "grid": _("Raster"),
    # ``geom.prepare_ops``: die Händigkeit eines Gewindes, das nicht neu geschnitten wird.
    "handedness": _("Gangrichtung"),
    "groups": _("Gruppen"),
    "height": _("Höhe"),
    # ``geom.repair``: geschlossene oder offene Stellen, gezählt als Ringe.
    "holes": _("Löcher"),
    # ``scene.evaluate``: der Eingang eines Schritts, dessen Ausgaben fehlen.
    "input_name": _("Eingang"),
    "input_object": _("Eingangskörper"),
    # ``scene.fits``: ob die zwei Körper in Einbaulage einander durchdringen —
    # nicht „Durchdringung“, das ist im Katalog die Selbstdurchdringung.
    "intersects": _("Überschneidung"),
    # Die Kennungen, die ein Erzeuger mit Eingängen aus einer Altdatei nicht
    # verbraucht (``evaluate.creator_inputs_dropped``). „Übersprungen" statt
    # eines neuen Wortes: Es steht schon in allen sechs Katalogen und sagt
    # dasselbe.
    "ignored": _("Übersprungen"),
    # Die Kennung einer gewählten Kante und wie viele sie trifft
    # (``geom.edges.selected``): Steht eine Kennung für zwei Kanten, hält die
    # Operation an, und der Befund nennt beides.
    "key": _("Kantenkennung"),
    "key_major": _("Schlüsselversion"),
    "kept": _("Beibehalten"),
    "kind": _("Art"),
    "known": _("Bekannt"),
    "known_faces": _("Bekannte Flächen"),
    "layer": _("Schicht"),
    "layer_height": _("Schichthöhe"),
    "layers": _("Schichten"),
    # ``counterpart``: die größte Gewindegröße der Tabelle.
    "largest": _("Größte Größe"),
    "least": _("Mindestens"),
    "limit": _("Grenze"),
    # ``parts.changed``: der Bausteinstand, mit dem gespeichert wurde, und der
    # dieser Version (§24.4). „Gespart" hieße Material, nicht Version.
    "library_saved": _("Bausteinstand beim Speichern"),
    "library_now": _("Bausteinstand jetzt"),
    "loose": _("Lose Stücke"),
    "materials": _("Materialien"),
    # ``perceive.too_large`` nach einem Speicherfehler: der geschätzte
    # Spitzenbedarf der Vollerkennung, ganze GB (``local.recognition_gigabytes``).
    "memory": _("Nötiger Arbeitsspeicher"),
    "lost": _("Verloren"),
    "major": _("Hauptversion"),
    "machine": _("Maschine"),
    "margin": _("Randabstand"),
    # ``brep.kernel``: wie viele Dreiecke der Tessellierung eine Fläche kennen.
    "mapped_triangles": _("Zugeordnete Dreiecke"),
    # ``brep.edit``: die Mitte einer Kante, die zu keinem Körper gehört.
    "middle": _("Mitte"),
    "matches": _("Treffer"),
    "material": _("Material"),
    "maximum": _("Höchstwert"),
    "measured": _("Gemessen"),
    "megabytes": _("Megabyte"),
    "minimum": _("Mindestwert"),
    "minutes": _("Minuten"),
    "motion": _("Bewegung"),
    "missed": _("Nicht getroffene Züge"),
    "missing": _("Fehlt"),
    "most": _("Höchstmaß"),
    "moved": _("Größte Bewegung"),
    "name": _("Name"),
    "neck": _("Hals"),
    "needed": _("Nötig"),
    "node": _("Knoten"),
    "nominal": _("Nennmaß"),
    "nozzle": _("Düse"),
    "object": _("Objekt"),
    "object_ids": _("Objekte"),
    "objects": _("Objekte"),
    "op": _("Operation"),
    "open_edges": _("Offene Kanten"),
    "opening": _("Öffnung"),
    "operation": _("Operation"),
    "operations": _("Operationen"),
    "output": _("Ausgabe"),
    "outputs": _("Ausgaben"),
    "overhang": _("Überhang"),
    "oversize": _("Übermaß"),
    "parameter": _("Parameter"),
    "params": _("Parameter"),
    "part": _("Baustein"),
    "part_index": _("Teil"),
    "part_name": _("Teil"),
    "parts": _("Teile"),
    "path": _("Pfad"),
    # ``geom.lid``: der Durchmesser des Scharnierstifts.
    "pin": _("Stift"),
    "pitch": _("Steigung"),
    "pixels": _("Bildpunkte"),
    "plate": _("Platte"),
    "plates": _("Platten"),
    "posed": _("Gestellt"),
    "position": _("Position"),
    "possible": _("Möglich"),
    "printed": _("Gedruckt"),
    "printer": _("Drucker"),
    # ``slicer.machine_mismatch`` trennt Curas Wahl vom Profil in Solidon.
    "cura_printer": _("Cura-Drucker"),
    "solidon_printer": _("Solidon-Drucker"),
    "produced": _("Erzeugt"),
    "profile": _("Profil"),
    "variant": _("Variante"),
    "radius": _("Radius"),
    "reachable": _("Erreichbar"),
    "read": _("Gelesen"),
    "reason": _("Grund"),
    "room": _("Platz daneben"),
    # ``brep.profiles``: der Kerndurchmesser, aus dem kein Gewindegang entsteht.
    "root": _("Kerndurchmesser"),
    "reference": _("Bezug"),
    # ``errors``: die Flächenbezüge, die am exakten Körper nicht mehr belegt sind.
    "references": _("Bezüge"),
    "regions": _("Bereiche"),
    # Die getrennten Umrisse der beiden Zeichnungen eines Übergangs
    # (RM-147 E2) — die Zahlen, an denen der Kunde sieht, was nicht passt.
    "lower_outlines": _("Umrisse unten"),
    "upper_outlines": _("Umrisse oben"),
    "removed": _("Entfernt"),
    "requested": _("Angefragt"),
    "residual": _("Rest"),
    "role": _("Rolle"),
    "safety": _("Sicherheitsfaktor"),
    "samples": _("Stichproben"),
    "saved": _("Gespart"),
    "scale": _("Maßstab"),
    "scheme": _("Schema"),
    "seams": _("Nähte"),
    "second_kind": _("Zweite Art"),
    "section": _("Dateiabschnitt"),
    "seconds": _("Sekunden"),
    "seed": _("Startwert"),
    "setting": _("Einstellung"),
    "settings": _("Einstellungen"),
    "share": _("Anteil"),
    "shortcut": _("Kürzel"),
    "shortest": _("Mindestlänge"),
    "shared": _("Überschneidung"),
    "shown": _("Sichtbar"),
    "size": _("Größe"),
    "slicer": _("Slicer"),
    "slot": _("Platz"),
    "slots": _("Plätze"),
    "source": _("Quelle"),
    "provider": _("Anbieter"),
    "sources": _("Quellen"),
    "span": _("Spannweite"),
    "speed_field": _("Geschwindigkeitsfeld"),
    "stages": _("Stufen"),
    # ``geom.prepare_ops``: die Gangzahl eines mehrgängigen Gewindes.
    "starts": _("Gänge"),
    "status": _("Zustand"),
    "step": _("Schritt"),
    "style": _("Stil"),
    "steps": _("Schritte"),
    "stress": _("Biegespannung"),
    "stroke": _("Zug"),
    "strokes": _("Striche"),
    "suffix": _("Endung"),
    "suggested_name": _("Freier Name"),
    # ``expressions.canonical``: wie der Parameter geschrieben werden muss.
    "suggestion": _("Vorschlag"),
    "support": _("Stützen"),
    "supported": _("Unterstützt"),
    "target": _("Ziel"),
    "text": _("Text"),
    "to": _("Nach"),
    "tolerance": _("Toleranz"),
    "transaction": _("Transaktion"),
    "transactions": _("Transaktionen"),
    "triangles": _("Dreiecke"),
    # ``geom.prepare_ops``: die Schnurstärke eines Rings, die nicht in ihn passt.
    "tube_diameter": _("Schnurstärke"),
    "turn_axis": _("Drehachse"),
    "type": _("Art"),
    "unit": _("Einheit"),
    "unknown": _("Unbekannt"),
    "unpacked": _("Entpackt"),
    "url": _("Adresse"),
    "used_by": _("Benutzt von"),
    "valid": _("Gültige Kandidaten"),
    "value": _("Wert"),
    "vents": _("Entlüftungen"),
    # Aushöhlen mit gewählten Flächen (P6.3): wie viele davon offen sind, und
    # was vom Innenraum trotzdem geschlossen blieb (``hollow.closed_cavities``).
    "openings": _("Öffnungen"),
    "closed": _("Geschlossene Hohlräume"),
    # Das Merkmalsmuster (P6.7) nennt die Plätze, die nicht entstanden sind.
    # „Plätze" allein heißt im Katalog schon die Materialslots.
    "instances": _("Plätze im Muster"),
    "vertices": _("Ecken"),
    "volume": _("Volumen"),
    # Die Einheit steht im Namen, weil ``_minutes`` keines der Suffixe aus
    # :data:`_VALUE_UNITS` ist — ohne sie läse der Kunde „Gewartet: 10" und
    # wüsste nicht, ob Sekunden oder Minuten gemeint sind.
    "waited_minutes": _("Gewartet (Minuten)"),
    "walls": _("Wände"),
    "wall": _("Wandstärke"),
    "wanted": _("Gewünscht"),
    "window": _("Fenster"),
    "width": _("Breite"),
    "what": _("Was"),
    "where": _("Wo"),
    "worst_case": _("Schlechtester Fall"),
    "z": _("Z"),
    # Den Verlauf umbauen (RM-188 P7): der Schritt, an dem ein Umbau hielte,
    # der Schritt, an dem ein anderer hängt, und der Schritt, der wieder
    # rechnen soll — alle drei als Schrittnummer.
    "also": _("Ausschalten"),
    # Der frühere Schritt, der das Merkmal gesetzt hat, an dem ein späterer
    # scheitert (``errors.CHANGE_THREAD_STEP``, Review P2 Bausteine, M2).
    "creating_step": _("Erzeugender Schritt"),
    "number": _("Schritt"),
    "other": _("Anderer Schritt"),
    "reactivate": _("Einschalten"),
}


def plain_number(value: float) -> str:
    """Eine Zahl ohne Einheit, so kurz wie sie ehrlich ist.

    ``:g`` lässt die abschließenden Nullen weg: 15 bleibt 15 und wird nicht zu
    „15,00". Bei einem Anteil und einem Winkel ist das die ganze Auskunft.
    """
    return localised(f"{value:g}")


def count_text(count: int, *, rough: bool = False) -> str:
    """Eine Anzahl in Dreiergruppen, getrennt durch ein geschütztes Leerzeichen.

    „6081000 Dreiecke" liest niemand auf einen Blick, „6 081 000" schon. Das
    Leerzeichen gilt in jeder Sprache — ein Punkt oder Komma als
    Tausendertrennung hieße in der Hälfte der Sprachen etwas anderes (§19.3).
    ``rough`` rundet vorher auf zwei geltende Ziffern: Eine vorab geschätzte
    Zahl, die bis auf die Einerstelle dasteht, sähe aus wie gezählt.
    """
    whole = max(int(count), 0)
    if rough and whole >= 100:
        step = 10 ** (len(str(whole)) - 2)
        whole = (whole + step // 2) // step * step
    digits = str(whole)
    groups = [digits[max(end - 3, 0) : end] for end in range(len(digits), 0, -3)]
    return " ".join(reversed(groups))


#: Welches Suffix welche Einheit meint, und wie ein Wert damit dasteht.
#:
#: Nach Länge sortiert geprüft, sonst schluckt _mm das _mm3.
#:
#: **Die Einheit steht am Wert und nicht in der Beschriftung.** „Übermaß (mm):
#: 12,4" war eine zweite Antwort auf die Frage aus §19.3: Wer auf Zoll stellt,
#: liest Längen in Zoll und Volumen in Kubikzoll — und daneben stand ein Befund
#: in Millimetern, mit der Einheit als Teil seiner Beschriftung, wo sie nicht
#: umschalten konnte. Jetzt schreiben `length`, `area` und `volume` den Wert,
#: dieselben Funktionen, die der Objektbaum benutzt; die Beschriftung ist nur
#: noch der Name. Dass ein Volumen dabei die Einheit wechseln kann (mm³, cm³,
#: in³), ist derselbe Grund in der Umkehrung: Eine Beschriftung, die „(mm³)"
#: behauptet, während im Wert „16,4 cm³" steht, wäre falsch.
_VALUE_UNITS: tuple[tuple[str, str, Callable[[float], str]], ...] = (
    ("_mm3", "mm³", volume),
    ("_mm2", "mm²", area),
    ("_cm3", "cm³", lambda value: volume(value * 1000.0)),
    ("_percent", "%", lambda value: f"{plain_number(value)} %"),
    ("_deg", DEGREE_UNIT, lambda value: f"{plain_number(value)}{DEGREE_UNIT}"),
    ("_mm", "mm", length),
)


def value_label(key: str) -> str:
    """Die Beschriftung zu einem Wert-Schlüssel — ohne Einheit, die steht am Wert.

    Unbekanntes kommt durch, wie es ist: Ein Schlüssel aus einem Zweig, den der
    Test nicht statisch sieht (``values=dict(...)``), soll den Tooltip nicht
    leeren. Der Test hält die Liste vollständig, diese Zeile hält sie harmlos.
    """
    for suffix, _unit, _show in _VALUE_UNITS:
        if key.endswith(suffix):
            name = _VALUE_NAMES.get(key[: -len(suffix)])
            return str(name) if name is not None else key
    name = _VALUE_NAMES.get(key)
    return str(name) if name is not None else key


#: Die Rechenwege, die ein Befund unter „Rechenstufe“ und „Versuchte Stufen“
#: nennt — als Satzstück statt als Bezeichner aus dem Kern (RM-088): In den
#: Einzelheiten stand „Rechenstufe: voxel“ und „Versuchte Stufen:
#: fast_simplification“. Die Kennungen stammen aus ``types.SolverStage`` und
#: ``mesh_ops.SimplificationSolver``; eine unbekannte bleibt stehen, wie sie ist.
_METHOD_NAMES: Final[dict[str, TranslatableText]] = {
    "direct": _("direkt gerechnet"),
    "welded": _("mit zusammengeführten Punkten gerechnet"),
    "jittered": _("minimal verschoben gerechnet"),
    "voxel": _("auf einem Raster gerechnet"),
    "none": _("nicht vereinfacht"),
    "exact": _("verlustfrei vereinfacht"),
    "fast_simplification": _("schnell vereinfacht"),
    "manifold": _("formtreu vereinfacht"),
}


def value_text(key: str, value: object) -> str:
    """Der Wert mit seiner Einheit, in der Einheit der Anzeige (§19.3)."""
    if key == "part_name":
        # Nutzernamen bleiben wörtlich, auch wenn sie wie Zahlen oder Auswahlwerte aussehen.
        return str(value)
    if key in ("solver", "attempted") and isinstance(value, str) and value in _METHOD_NAMES:
        return str(_METHOD_NAMES[value])
    if key in ("solver", "attempted") and isinstance(value, (list, tuple)):
        # Die Liste der versuchten Wege kam als Python-Liste an: „['direct',
        # 'welded']" (Kundenprüfer, KUNDE-10). Jetzt als Wörter, durch Kommas.
        return ", ".join(
            str(_METHOD_NAMES[entry]) if entry in _METHOD_NAMES else str(entry) for entry in value
        )
    # Diese bestehenden Befundschlüssel tragen keine Einheiten-Endung.
    # Längen folgen trotzdem der Anzeigeeinheit; Materialkennwerte behalten
    # die Einheit des Filamentprofils und der Festigkeitsrechnung.
    if key in ("at", "margin"):
        key += "_mm"
    elif key == "flow_limit":
        return f"{localised_value(value)} mm³/s"
    elif key == "stress":
        return f"{localised_value(value)} MPa"
    elif key == "memory":
        return f"{localised_value(value)} GB"
    for suffix, unit, show in _VALUE_UNITS:
        if not key.endswith(suffix):
            continue
        try:
            number = float(value)  # type: ignore[arg-type]
        except TypeError, ValueError:
            # Keine Zahl, also keine Umrechnung. Die Einheit des Schlüssels
            # bleibt stehen: Sie ist dann die einzige Auskunft, die es gibt.
            return f"{localised_value(value)} {unit}"
        return show(number)
    if key in {"estimated_source", "measured_source"}:
        if value == "internal":
            return tr("Interne Schichtanalyse")
        if value == "gcode":
            return tr("G-Code")
    return localised_value(value)


#: Was als Zahl durchgeht: Vorzeichen, Ziffern, höchstens ein Punkt, dahinter
#: höchstens eine Einheit ohne Ziffern und ohne Punkt.
#:
#: Die Einheit darf nicht selbst Ziffern oder Punkte enthalten, sonst passte
#: „1.2.3" als Zahl mit der Einheit „.3" — und eine Versionsnummer wäre in der
#: Anzeige zerschnitten.
_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?(\s*[^\d.\s]+)?$")


def localised_value(value: object) -> str:
    """Ein Wert, wie er beim Nutzer steht: Zahlen mit Komma, alles andere heil.

    **Hier stand :func:`localised` auf jedem Wert**, und das war eine
    Textverfälschung: Die Funktion tauscht jeden Punkt gegen das
    Dezimaltrennzeichen der Sprache, und Befunde tragen Pfade, Adressen und
    Dateiendungen. In der deutschen Oberfläche stand damit
    ``Pfad: sources/1_cube_clean,stl``, ``Adresse: https://example,com/x,stl``
    und ``Endung: ,step`` — ein Pfad, den niemand benutzen kann, und eine
    Adresse, die falsch ist.

    Was keine Zahl ist, geht durch :func:`choice_label`: Ein Auswahlwert wie
    ``exact`` bekommt dort seinen Namen, und alles Unbekannte kommt unverändert
    durch. Zwei Wege, eine Zeile — und keiner davon fasst einen Pfad an.
    """
    text = str(value)
    return localised(text) if _NUMBER.match(text) else choice_label(text)


#: Werte eines Befunds, die in der Einheit seines Feldes stehen, wenn er sie
#: mitbringt (``values["unit"]``, RM-359 F7).
UNIT_VALUES: Final = frozenset({"minimum", "maximum", "value"})


def value_line(key: str, value: object, unit: str = "") -> str:
    """Eine Zeile „Beschriftung: Wert" für Tooltip und Einzelheiten.

    Die Zahl bekommt ihr Komma (§13) und ihre Einheit, der Rest bleibt, wie er
    ist — siehe :func:`value_text` und :func:`localised_value`. ``unit`` ist
    die Einheit des Feldes, die der Befund daneben nennt: Eine Grenze in
    Millimetern folgt dann der Anzeigeeinheit wie jede andere Länge.
    """
    shown = value_text(key, value)
    if unit and key in UNIT_VALUES and isinstance(value, int | float):
        shown = value_text(f"{key}_mm", value) if unit == "mm" else f"{shown} {unit}"
    return tr("{name}: {value}", name=value_label(key), value=shown)


def unit_of(values: Mapping[str, object]) -> str:
    """Die Einheit, die ein Befund für seine Grenzen nennt — leer ohne."""
    unit = values.get("unit")
    if isinstance(unit, str) and unit and any(key in values for key in UNIT_VALUES):
        return unit
    return ""


def spoiled_the_exact_body(result: Any) -> str:
    """Welcher Schritt aus dem exakten Körper ein Netz gemacht hat — als Titel.

    Die Auswertung meldet es als ``evaluate.exact_became_mesh``, und dort steht
    auch, welche Operation es war. Ohne diese Auskunft rät der Hinweis am
    gesperrten Eintrag am eigentlichen Fall vorbei: Er spricht vom Haken beim
    Anlegen, während der Körper längst exakt angelegt wurde und eine Bohrung
    drei Schritte später ihn zum Netz gemacht hat.

    Neben :func:`kind_requirement` und nicht in den zwei Ansichten, die den
    Satz zeigen — aus demselben Grund, aus dem der Satz selbst hier steht:
    zwei Stellen mit derselben Auskunft driften.

    Der Titel und nicht der Name: „drill_hole" steht in keinem Menü.
    """
    from app.core.registry import REGISTRY

    if result is None:
        return ""
    for finding in result.scene.report.findings:
        if finding.code != "evaluate.exact_became_mesh":
            continue
        name = str(finding.values.get("op", ""))
        return str(REGISTRY.get(name).title) if REGISTRY.has(name) else name
    return ""


def exact_conversion_lines(
    findings: Sequence[Finding], object_names: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """Erklärt erlaubte Umwandlungen vor der Übernahme, einmal je Eingang und Schritt."""
    names = object_names or {}
    detailed = {
        (finding.op_id, finding.object_id)
        for finding in findings
        if finding.code == "evaluate.exact_became_mesh"
    }
    seen = set()
    lines = []
    for finding in findings:
        if not finding.converts_exact_body:
            continue
        if finding.code == "brep.converted" and (finding.op_id, finding.object_id) in detailed:
            continue
        source = str(finding.values.get("input_object") or finding.object_id or "")
        key = (finding.op_id, source)
        if key in seen:
            continue
        seen.add(key)
        name = str(finding.values.get("input_name") or names.get(source) or tr("Körper"))
        operation = str(finding.values.get("op") or "")
        title = str(REGISTRY.get(operation).title) if REGISTRY.has(operation) else tr("Umwandeln")
        # Ein Satz je Eingang, nicht drei (Review Fenster #13): Was danach
        # gilt und dass Strg+Z zurückführt, steht einmal darunter — an drei
        # Eingängen standen die zwei Sätze dreimal.
        lines.append(
            tr("„{operation}“ macht aus „{object}“ ein Dreiecksmodell.").format(
                operation=title, object=name
            )
        )
    if lines:
        lines.append(
            tr(
                "Flächen und Kanten bleiben bearbeitbar; Rundungen bestehen dann aus "
                "geraden Teilstücken. Rückgängig stellt den vorherigen Körper wieder her."
            )
        )
    return tuple(lines)


def kind_requirement(spec: Any, kinds: Sequence[str], spoiled_by: str = "") -> str | None:
    """Warum diese Operation auf dieser Auswahl nicht geht — oder ``None``.

    Eine Operation des exakten Kerns trägt ``requires_kind="brep"``; auf einem
    Netz kann sie nicht arbeiten. Die Menüleiste graut sie dann aus und schreibt
    diesen Satz in den Tooltip, statt sie anzubieten und nach dem ausgefüllten
    Dialog abzulehnen (Regel 19).

    **Der Satz steht hier, weil zwei Ansichten ihn brauchen.** Das Kontextmenü
    am Körper bot alle Operationen mit einem Eingang an, ungeprüft — auch die
    sieben des exakten Kerns. Wer am Netz-Körper *Verrunden* wählte, füllte
    einen Dialog aus und bekam danach eine Absage: genau die Sackgasse, die die
    Menüleiste zwei Dateien weiter vermeidet. Zwei Stellen, dieselbe Auskunft —
    also gehört sie in diese Datei und nicht zweimal in die Oberfläche.

    ``spoiled_by`` ist der Titel des Schritts, der aus einem exakten Körper ein
    Netz gemacht hat — die Auswertung meldet ihn als
    ``evaluate.exact_became_mesh``. Damit gibt es zwei ganz verschiedene Lagen,
    und ein Satz für beide wäre für eine davon falsch: Der Körper war nie
    exakt, dann steht der Wechsel am Erzeugerschritt im Verlauf. Oder er war es
    und ist es nicht mehr — dann hilft nur die Reihenfolge.
    """
    if not spec.requires_kind or not kinds:
        return None
    if all(kind == spec.requires_kind for kind in kinds):
        return None
    if spoiled_by:
        # **Kein Umsortieren vorschlagen.** Der Satz hieß erst „diesen Schritt
        # im Verlauf nach hinten nehmen" — und das kann der Verlauf nicht, aus
        # gutem Grund: spätere Operationen bauen auf den Ausgaben des Schritts
        # auf (`HistoryPanel._on_context_menu`). Ein Handlungsvorschlag, den
        # niemand ausführen kann, ist schlechter als keiner.
        return str(
            tr(
                "Seit „{step}“ ist der Körper ein Dreiecksmodell. Dieses Werkzeug braucht "
                "echte Kurven: Nehmen Sie die Schritte ab dort zurück, wenden Sie es an und "
                "setzen Sie den Rest danach neu."
            )
        ).format(step=spoiled_by)
    # **Welche Art fehlt, entscheidet den Satz** (Review, 21.09.2026). Bis dahin
    # nannte jede Absage den exakten Körper — auch an einem Werkzeug, das das
    # Dreiecksmodell braucht; seit neue Grundkörper exakt entstehen (P2.8),
    # war das der Normalfall an *Merkmale an dieser Stelle erkennen*.
    # **Die zwei Umwandlungen an dem Körper, der schon ist, was sie machen.**
    # Die allgemeinen Sätze darunter schickten ihn im Kreis: „In Flächen und
    # Kanten umwandeln“ an einem exakten Körper über „Flächenbearbeitung
    # beenden“ zum Netz, und „Flächenbearbeitung beenden“ an einem Netz über
    # die Umwandlung zurück.
    if spec.requires_kind == "mesh" and spec.result_kind == "brep":
        return str(tr("Der Körper hat bereits echte Flächen und Kanten."))
    if spec.requires_kind == "brep" and spec.result_kind == "mesh":
        return str(tr("Der Körper besteht bereits aus festen Dreiecken."))
    if spec.requires_kind == "mesh":
        return str(
            tr(
                "Dieses Werkzeug rechnet am Dreiecksmodell. Wandeln Sie den Körper vorher um "
                "(„Flächenbearbeitung beenden“)."
            )
        )
    # Der Satz sagte, woher exakte Körper *kommen*, und ließ offen, was man
    # jetzt tun soll. Seit P2.8 bringt eine Grundform die Flächen und Kanten
    # von sich aus mit; ein älterer Schritt wird im Verlauf umgestellt. Und
    # seit P4.0 bekommt auch ein eingelesenes Netz sie — der häufigste Fall.
    return str(
        tr(
            "Dieses Werkzeug braucht echte Flächen und Kanten. Ein Netz bekommt sie über „In "
            "Flächen und Kanten umwandeln“, eine ältere Grundform im Verlauf über „Mit echten "
            "Flächen und Kanten rechnen“."
        )
    )


def feature_requirement(spec: Any, feature_kinds: Collection[str]) -> str | None:
    """Warum diese Operation ohne passendes Merkmal nicht geht — oder ``None``.

    Die Schwester von :func:`kind_requirement`, eine Frage weiter: Eine
    Operation, deren Pflichtfeld ein Merkmal benennt (etwa die Bohrung beim
    Ändern ihres Durchmessers), kann auf einem Körper ohne ein solches Merkmal
    nichts anfangen. Ohne diesen Satz öffnete das Menü einen Dialog, dessen
    Pflicht-Auswahl leer ist — die Sackgasse aus Regel 19, nur ein Feld
    später. Der Satz steht hier, weil dieselbe Auskunft über
    ``_reason_locked`` an Menü, Kontextmenü, Palette und Zwillingshaken geht.

    Welche Art passt, sagt ``applies_to`` — die Zuordnung, über die auch das
    Auswahlfenster am Merkmal die Operation findet (§18.5). Eine Operation ohne
    diese Angabe wird nicht gesperrt: Raten wäre schlechter als Anbieten.
    """
    needs_feature = any(entry.required and entry.kind == "feature" for entry in spec.params.spec())
    if not needs_feature:
        return None
    wanted = tuple(spec.applies_to or ())
    if not wanted or any(kind in feature_kinds for kind in wanted):
        return None
    if "hole" in wanted:
        return str(tr("Dafür braucht es eine erkannte Bohrung am gewählten Teil."))
    return str(tr("Dafür braucht es ein erkanntes Merkmal am gewählten Teil."))


#: Bis zu wie vielen Dreiecken die Körperfakten fürs Menü gerechnet werden.
#: ``face_components`` kostet 2,3 s an 1,3 Millionen Dreiecken (gemessen
#: 14.09.2026, ``dense_1m.stl``) — bei jedem Klick auf den Körper, denn die
#: Menüs fragen bei jeder Auswahl neu. An der Grenze gemessen (14.09.2026):
#: 34 ms an 81 920 Dreiecken in einem Stück, 91 ms an 100 000 Dreiecken in
#: 36 163 Stücken — unter den 0,2 s, ab denen §2.8 eine Anzeige verlangt.
#: Darüber gilt der Zustand als unbekannt, der Eintrag bleibt frei, und der
#: Dialog sagt es im Band.
BODY_FACTS_LIMIT: Final = 100_000


@dataclass(frozen=True, slots=True)
class BodyFacts:
    """Was ein Körper mitbringt — die drei Fragen aus ``requires_body``.

    ``None`` heißt „nicht gerechnet": ein Netz über :data:`BODY_FACTS_LIMIT`
    oder ein exakter Körper, dessen Tessellation hier niemand anstoßen will.
    Unbekannt sperrt nie — Raten wäre schlechter als Anbieten.
    """

    closed: bool | None
    pieces: int | None
    cavity: bool | None


def body_facts(entry: SceneObject) -> BodyFacts:
    """Die Fakten eines Körpers, so billig wie möglich.

    **Der Hohlraum kommt aus den Merkmalen**, nicht aus einer Rechnung: Die
    Wahrnehmung erkennt einen eingeschlossenen Innenraum als ``void``, und
    *Aushöhlen* trägt seine Kavität am Netz ein — beides liegt nach der
    Auswertung schon da. ``raw.split`` wäre der dritte Weg und kostet an
    1,3 Millionen Dreiecken hundert Sekunden; den geht nur die Operation
    selbst, beim Rechnen.

    ``is_watertight`` liegt nach dem ersten Mal im Cache von trimesh, die
    Komponenten nicht — deshalb die Grenze, und deshalb hält das Fenster die
    Antwort je Körper und Auswertung fest, statt sie bei jedem Menüaufbau zu
    wiederholen.
    """
    hollow = any(feature.kind == "void" for feature in entry.features.values())
    # **Eine durchgehende Bohrung lässt die Frage offen.** Ein ausgehöhlter
    # Körper, der einmal als STL draußen war, ist eine Komponente ohne
    # ``void`` — und *Gitter füllen* kann ihn trotzdem, weil es den Innenraum
    # über die geschlossene Entlüftung bestimmt (RM-041, `lattice._cavity_mesh`).
    # Wo die Operation es kann, darf das Menü nicht sperren.
    vented = any(
        feature.kind == "hole" and feature.params.get("through")
        for feature in entry.features.values()
    )
    mesh = entry.mesh
    if not isinstance(mesh, MeshData):
        return BodyFacts(closed=None, pieces=None, cavity=True if hollow else None)
    hollow = hollow or mesh.cavity is not None
    if mesh.triangle_count > BODY_FACTS_LIMIT:
        return BodyFacts(closed=None, pieces=None, cavity=True if hollow else None)
    pieces = len(face_components(mesh.raw))
    # **Ohne Hohlraum ist nur, was aus einem Stück besteht.** Eine Innenschale
    # ist eine zweite Komponente; wo es zwei gibt und die Wahrnehmung keinen
    # Einschluss gemeldet hat, kann sie ihn auch übersehen haben (offene
    # Außenhülle, verkehrter Umlaufsinn) — dann entscheidet die Operation.
    #
    # **Eine Bohrung durch eine Platte ist keine Entlüftung.** Bis zum
    # 22.09.2026 ließ jede durchgehende Bohrung die Frage offen, und an
    # ``plate_holes.stl`` stand *Gitter füllen* anklickbar da, dessen Dialog
    # nur „Keine Vorschau" sagen konnte. Führen alle Bohrungen an beiden
    # Enden ins Freie, findet auch die Operation nichts — dieselbe Prüfung
    # (``lattice.bores_lead_outside``) entscheidet dort und hier.
    if hollow:
        known: bool | None = True
    elif pieces > 1:
        known = None
    elif vented:
        from app.core.geom.lattice import bores_lead_outside

        known = False if bores_lead_outside(mesh, entry.features) else None
    else:
        known = False
    return BodyFacts(closed=bool(mesh.raw.is_watertight), pieces=pieces, cavity=known)


def body_requirement(spec: Any, facts: BodyFacts | None) -> str | None:
    """Warum diese Operation an diesem Körper nichts tun kann — oder ``None``.

    Die dritte Schwester neben :func:`kind_requirement` und
    :func:`feature_requirement`: Nicht die Bauart, nicht das Merkmal, sondern
    der Zustand. Gemessen am 13.09.2026 über alle Dialoge: *Offene Fläche
    schließen* am geschlossenen Quader, *In Einzelteile aufteilen* an einem
    Stück und *Gitter füllen* am massiven Körper öffneten einen Dialog, dessen
    Vorschau nur „Keine Vorschau: …" sagen konnte — die Sackgasse aus Regel
    19, ein Fenster später. Hier steht der Satz, den die Operation beim
    Rechnen sagt, vor dem Klick am Eintrag.

    Was die Operation verlangt, sagt ``requires_body`` im Register; was der
    Körper hat, sagen die ``facts``. Fehlt eines von beiden oder ist es
    unbekannt, wird nicht gesperrt.
    """
    wanted = getattr(spec, "requires_body", "")
    if not wanted or facts is None:
        return None
    if wanted == "open" and facts.closed is True:
        from app.core.geom.mesh_ops import ALREADY_CLOSED

        return str(ALREADY_CLOSED)
    if wanted == "parts" and facts.pieces is not None and facts.pieces <= 1:
        from app.core.geom.prepare_ops import ONE_PIECE

        return str(ONE_PIECE)
    if wanted == "cavity" and facts.cavity is False:
        from app.core.geom.lattice import NO_CAVITY

        return str(NO_CAVITY)
    return None


def by_title(entries: Mapping[str, Any]) -> list[tuple[str, Any]]:
    """Profile in der Reihenfolge, in der sie gelesen werden.

    Sortiert wurde nach der Kennung, angezeigt wird der Titel — und die beiden
    laufen auseinander, sobald ein Hersteller anders heißt als sein Schlüssel.
    In der Druckerliste stand „Elegoo Centauri Carbon 2" zwischen Bambu und
    Creality (``centauri-carbon-2``) und „Allgemeiner FDM-Drucker 220 mm"
    zwischen Elegoo und Prusa (``generic-220``). Für den, der die Liste liest,
    war sie unsortiert.
    """
    return sorted(entries.items(), key=lambda pair: str(pair[1].title).casefold())


def choice_label(value: str) -> str:
    """Die gemeinsame Auswahlbeschriftung mit der Anzeigeeinheit des Fensters."""
    return _choice_label(
        value, format_measure=lambda size, with_unit: length(size, with_unit=with_unit)
    )


def choice_note(value: str) -> str | None:
    """Der Satz zu einem Auswahlwert — oder ``None``, wo der Name genügt.

    Das Gegenstück zu ``choice_label``: der Name sagt, wie der Wert heißt,
    der Satz sagt, was er bewirkt. ``None`` ist ein gültiges Ergebnis und
    kein Loch — Selbstnamen wie „M4" oder „mm" erklären sich selbst, und ein
    Tooltip, der den Namen wiederholt, wäre Tapete. Dass jeder **benannte**
    Wert einen Satz trägt, hält ``tests/test_translations.py`` fest.
    """
    note = _CHOICE_NOTES.get(value)
    if note is None:
        return None
    return str(note)


def explain_choices(box: QComboBox) -> None:
    """Hängt an jeden Eintrag einer Auswahl den Satz seines Werts.

    Die Dialoge legen den rohen Schlüssel als ``itemData`` ab
    (``addItem(choice_label(choice), choice)``) — genau dort wird er wieder
    gelesen. Je Eintrag zwei Rollen, dieselbe Doktrin wie bei den Feldsätzen:
    der Tooltip fürs Schweben über der offenen Liste, die
    ``AccessibleDescriptionRole`` für den Bildschirmleser (Regel 18 — nicht
    nur eine Kodierung). Einträge ohne Satz bleiben unangetastet; ein leerer
    Tooltip ist besser als ein wiederholter Name.

    Nach jeder Neubefüllung erneut aufrufen — ``clear()`` nimmt die Rollen
    mit den Einträgen mit.
    """
    for index in range(box.count()):
        value = box.itemData(index)
        if not isinstance(value, str):
            continue
        note = choice_note(value)
        if note is None:
            continue
        box.setItemData(index, note, Qt.ItemDataRole.ToolTipRole)
        box.setItemData(index, note, Qt.ItemDataRole.AccessibleDescriptionRole)


#: Wie eine Fläche heißt, deren Normale in diese Richtung zeigt. Die Reihenfolge
#: ist die der Achsen; ein Vorzeichen entscheidet zwischen den beiden Namen.
#:
#: Die Tabelle steht im Kern (``registry.surfaces.SIDE_NAMES``), weil *Bohrung
#: ändern* mit denselben Namen fragt, welche Seite offen bleibt — dort als
#: ``_()``-Literale, damit der Extraktor sie sieht.
_SIDES: tuple[tuple[TranslatableText, TranslatableText], ...] = SIDE_NAMES

#: Die Innenwand je Seite, in derselben Ordnung wie :data:`_SIDES`. Ein eigener
#: Text je Seite und kein „{side} innen“: Das Adjektiv richtet sich nach dem
#: Genus der Seite, fr „Face supérieure intérieure“ gegen „Côté gauche
#: intérieur“ — das kann ein Platzhalter nicht (Durchsicht 0.5.1).
_INNER_SIDES: tuple[tuple[TranslatableText, TranslatableText], ...] = (
    (_("Rechte Seite innen"), _("Linke Seite innen")),
    (_("Rückseite innen"), _("Vorderseite innen")),
    (_("Oberseite innen"), _("Unterseite innen")),
)

#: Ab wann eine Normale als achsparallel gilt. Darunter ist die Fläche schräg,
#: und ein Seitenname wäre eine Behauptung.
_AXIS_ALIGNED = 0.9


def group_summary(group: FunctionalGroup) -> str:
    """Das Maß einer funktionalen Gruppe für die Maßspalte des Baums (RM-184).

    Eine Kammer nennt ihr Innenmaß, eine Nut und ein Kanal Breite und Tiefe, ein
    Gewinde Durchmesser und Steigung, Aufnahmen und Augen ihre Zahl und Weite,
    ein Verschluss seine Stellungen, eine Schrift ihre Teile. Die Zahlen sind
    gemessen (``perceive.groups``), die Einheit folgt der Anzeige.
    """
    width = group.measure("width")
    across = group.measure("length")
    depth = group.measure("depth")
    diameter = group.measure("diameter")
    if group.kind == "chamber" and group.variant != "ring" and width and across and depth:
        return tr(
            "{width} × {length} × {depth}",
            width=length(width, with_unit=False),
            length=length(across, with_unit=False),
            depth=length(depth),
        )
    if group.kind in ("chamber", "channel") and group.variant != "passage" and width and depth:
        return tr("{width} breit, {depth} tief", width=length(width), depth=length(depth))
    if group.kind == "channel" and diameter:
        return tr("Ø{diameter} · {count} Rippen", diameter=length(diameter), count=group.count)
    if group.kind == "thread" and diameter:
        pitch = group.measure("pitch") or 0.0
        return tr(
            "Ø{diameter} × {pitch}",
            diameter=length(diameter, with_unit=False),
            pitch=length(pitch),
        )
    if group.kind in ("socket", "hinge") and diameter:
        return tr("{count} × Ø{diameter}", count=group.count, diameter=length(diameter))
    if group.kind == "closure":
        return tr("{count} Stellungen", count=group.count)
    if group.kind == "lettering":
        return tr("{count} Teile", count=group.count)
    return ""


def group_measure_text(measure: GroupMeasure) -> str:
    """Ein Maß einer funktionalen Gruppe, wie es im Merkmalfenster steht (RM-184).

    Längen folgen der Anzeigeeinheit, Winkel tragen ihr Gradzeichen, und eine
    Anzahl bleibt eine Zahl — auch eine gebrochene wie 4,45 Windungen.
    """
    if measure.unit == "mm":
        return length(measure.value)
    if measure.unit == DEGREE_UNIT:
        return f"{plain_number(measure.value)}{DEGREE_UNIT}"
    return plain_number(round(measure.value, 2))


def cavity_name(feature_id: FeatureId, feature: Feature, cavity: Sequence[Feature] = ()) -> str:
    """Den belegten Zusammenhang schon an der obersten Bohrungszeile nennen.

    **Ein Kegel ist nicht immer eine Senkung** (Durchsicht 0.5.1, R3): Die
    Haltelippe einer Magnettasche verengt die Mündung (``narrowing`` aus der
    Erkennung), und „Sackbohrung 1 mit Senkung" versprach einen Trichter, wo
    der Magnet gehalten wird. Dasselbe Wort wie am Kegel selbst
    (:func:`feature_name`).
    """
    name = feature_name(feature_id, feature)
    if not cavity or cavity[0].id != feature_id or feature.kind != "hole":
        return name
    stepped = sum(member.kind == "hole" for member in cavity) > 1
    cones = [member for member in cavity if member.kind == "cone"]
    narrowed = any(member.params.get("narrowing") for member in cones)
    countersunk = any(not member.params.get("narrowing") for member in cones)
    if stepped and countersunk and narrowed:
        return tr("{feature} mit Stufen, Senkung und Verengung").format(feature=name)
    if stepped and countersunk:
        return tr("{feature} mit Stufen und Senkung").format(feature=name)
    if stepped and narrowed:
        return tr("{feature} mit Stufen und Verengung").format(feature=name)
    if stepped:
        return tr("{feature} mit Stufen").format(feature=name)
    if countersunk and narrowed:
        return tr("{feature} mit Senkung und Verengung").format(feature=name)
    if countersunk:
        return tr("{feature} mit Senkung").format(feature=name)
    if narrowed:
        return tr("{feature} mit Verengung").format(feature=name)
    return name


def feature_name(feature_id: FeatureId, feature: Feature) -> str:
    """Wie das Merkmal heißt, wenn man es jemandem zeigt.

    Im Baum stand `face_2` — die Kennung, mit der der Op-Stack rechnet, und
    für einen Menschen eine Nummer ohne Aussage. Eine ebene Fläche weiß, wohin
    sie zeigt, und „Oberseite" ist dieselbe Auskunft in lesbar. Die Kennung
    bleibt: sie steht im Tooltip und in jedem Parameterfeld.
    """
    if feature.kind == "face":
        normal = feature.params.get("normal")
        # Innen und außen heißen verschieden: Die Wahrnehmung sagt, ob eine
        # gleichgerichtete Fläche weiter außen liegt (``perceive.features``),
        # und „Rückseite innen" ist dann die Innenwand — vorher stand die
        # Fläche in mm² als einziger Unterschied zwischen zwei „Rückseiten".
        inner = bool(feature.params.get("inner", False))
        if isinstance(normal, tuple | list) and len(normal) == 3:
            for axis, (positive, negative) in enumerate(_SIDES):
                value = float(normal[axis])
                if abs(value) >= _AXIS_ALIGNED:
                    names = _INNER_SIDES[axis] if inner else (positive, negative)
                    return str(names[0] if value > 0 else names[1])
        return tr("Schrägfläche innen") if inner else tr("Schrägfläche")
    # Eine gerundete Seite zeigt nirgendwohin — sie ist der Bogen eines D,
    # der Mantel eines o. Innen ist sie, wenn sie hohl liegt: die Innenwand
    # des D, aus der Konvexität ihrer Nähte gelesen (``perceive.features``).
    if feature.kind == "curved_face":
        if bool(feature.params.get("inner", False)):
            return tr("Gerundete Seite innen")
        return tr("Gerundete Seite")
    # **Mit Nummer, wie die Bohrung** — und mit dem Stil als Namen: „Wabenmuster
    # 1", nicht „Muster 1", denn der Stil ist, was der Kunde sieht. Derselbe
    # Name wie im Steckbrief (``perceive/digest.py``).
    if feature.kind == "pattern":
        from app.core.perceive.digest import pattern_style_name

        style = pattern_style_name(str(feature.params.get("style", "other")))
        # Bei vereinigten Körpern bewahrt jede Textur ihre Herkunftskennung.
        # Ihre Nummernkette unterscheidet die Zeilen ohne technische Präfixe.
        number = ".".join(part.rsplit("_", 1)[-1] for part in feature_id.split("."))
        return f"{style} {number}"
    if feature.kind == "hole":
        name = tr("Sackbohrung") if feature.params.get("through") is False else tr("Bohrung")
        # Angeschnitten: Ein Nachbar hat den Mantel geöffnet (P1.5) — dasselbe
        # Wort wie im Steckbrief.
        if feature.params.get("partial"):
            name = tr("Angeschnittene Bohrung")
        return f"{name} {feature_id.rsplit('_', 1)[-1]}"
    # **Mit Nummer, wie die Bohrung.** Ein Teil trägt selten eine Bohrung und
    # oft vier; dasselbe gilt für Langlöcher, und ohne die Nummer stünden im
    # Objektbaum vier Zeilen „Langloch" untereinander.
    if feature.kind == "slot":
        return f"{tr('Langloch')} {feature_id.rsplit('_', 1)[-1]}"
    if feature.kind == "cone":
        # Ein Kegelstück unter dem vollen Umlauf, das zu keinem Langloch und
        # keiner Bohrung gehört, ist eine Kegelfläche — dasselbe Wort wie im
        # Steckbrief (``perceive/digest.py``).
        if feature.params.get("partial"):
            return tr("Kegelfläche")
        # Ein hohler Kegel, der sich zu seiner Bohrung hin öffnet, verengt die
        # Mündung — die Haltelippe einer Magnettasche (``narrowing``, R3).
        if feature.params.get("narrowing"):
            return tr("Verengung")
        return tr("Senkung") if feature.params.get("recess") else tr("Verjüngung")
    # Dieselbe Trennung wie beim Kegel, und deshalb dieselbe Frage: hinein oder
    # heraus. Eine ausgehöhlte Kugel ist eine Pfanne (Kugelgelenk,
    # Magnettasche), eine aufgesetzte eine Kuppel; beim Torus heißt das Kehle
    # und Wulst. Eine Regel, die man einmal lernt, statt drei Einzelfällen.
    if feature.kind == "sphere":
        return tr("Pfanne") if feature.params.get("recess") else tr("Kuppel")
    if feature.kind == "torus":
        return tr("Kehle") if feature.params.get("recess") else tr("Wulst")
    # Dieselbe Unterscheidung wie darüber, und dieselbe Falle: Ohne diese zwei
    # Zeilen fällt die Beschriftung auf die Kennung zurück, und im Objektbaum
    # stand „fillet_1" — ein englisches Wort in der Oberfläche, an `tr()`
    # vorbei. Aufgefallen ist es keinem Test: Sie fragen, *ob* ein Merkmal da
    # ist, nicht, *was* dort steht.
    if feature.kind == "fillet":
        # **Eine runde Wand heißt nicht Verrundung.** Der Nutboden eines
        # Bajonettverschlusses ist ein Zylinder mit 281 Grad Überdeckung und
        # trägt ``radial`` (Siebhalter eines Kunden, 15.09.2026); als
        # „Verrundung R27,18" im Baum sucht der Kunde die Kante, die es nicht
        # gibt. Dasselbe Wort steht schon im Panel: „Diese runde Wand ist
        # keine abgerundete Kante."
        if feature.params.get("radial"):
            return tr("Runde Wand innen") if feature.params.get("recess") else tr("Runde Wand")
        return tr("Hohlkehle") if feature.params.get("recess") else tr("Verrundung")
    if feature.kind == "edge_loop":
        return tr("Offene Kante")
    # **Und dieselbe Falle noch zweimal**, gefunden am 27.08.2026: Der
    # Kommentar über der Verrundung beschreibt sie, aber wer sie dort
    # schloss, hat die Zwillinge nicht gesucht. Im Objektbaum stand
    # „thread_1" und „pin_1" — englische Kennungen in der Oberfläche,
    # an ``tr()`` vorbei. Die Begriffe sind nicht neu erfunden, sondern
    # aus dem Steckbrief übernommen (``perceive/digest.py``), der beide
    # längst richtig benennt; zwei Namen für dieselbe Sache wären
    # schlimmer als einer auf Englisch.
    if feature.kind == "thread":
        return tr("Innengewinde") if feature.params.get("internal") else tr("Außengewinde")
    if feature.kind == "pin":
        return tr("Zapfen")
    # **Ein Name, der sagt, dass hier nichts ist — und nicht, dass es falsch
    # ist.** „Lufteinschluss" beschreibt, was der Kunde beim Drucken bekommt,
    # ohne ihm zu unterstellen, er habe sich geirrt: Die Aussparung für einen
    # eingegossenen Magneten sieht genauso aus wie ein vergessener
    # Negativkörper. Was der Name leisten muss, ist die Unterscheidung von der
    # **Bohrung**, als die es bis zum 10.09.2026 dastand (Robert: „Bohrungen,
    # die im Inneren des Materials sind, was nicht sein kann").
    if feature.kind == "void":
        return f"{tr('Lufteinschluss')} {feature_id.rsplit('_', 1)[-1]}"
    # Seit alle elf Arten einen Namen haben, hält mypy diese Zeile für
    # unerreichbar — und hat für den deklarierten Typ recht. Sie bleibt
    # trotzdem: ``kind`` kommt aus einer Projektdatei, und eine ältere
    # oder neuere Fassung kann eine Art tragen, die dieser Bestand nicht
    # kennt. Dann ist die Kennung hässlich, aber besser als ein Absturz
    # beim Öffnen.
    return feature_id  # type: ignore[unreachable]


#: Das Zeichen hinter einer Zahl, deren Herkunft warnt — eingepasst, aus dem
#: Schritt oder nicht belegt (RM-490). Die Maßspalte des Objektbaums ist zu
#: schmal für „Ø5,20 mm · eingepasst“ und zeigte „Ø5,20 mm · ein…“; die Zahl
#: steht deshalb ganz da, das Wort in Tooltip und Bildschirmleser. „≈“ heißt
#: dort, was alle drei Wörter gemeinsam sagen: Die Oberfläche kann von dieser
#: Zahl abweichen.
MEASURE_MARK: Final = "≈"


def measure_text(
    feature: Feature,
    name: str,
    *,
    prefix: str = "",
    format_value: Callable[[float], str] = length,
    with_source: bool = True,
    compact: bool = False,
    marked: bool = False,
) -> str:
    """Eine vorhandene Zahl und ihre belegte Herkunft, ohne erneute Maßrechnung.

    ``compact`` nennt nur das Wort, das warnt (``measure_qualifier``) — für die
    Marken in der Ansicht, wo viele einzeilige Beschriftungen um Platz ringen.
    ``marked`` setzt statt des warnenden Worts :data:`MEASURE_MARK` hinter die
    Zahl — für die Maßspalte des Objektbaums (RM-490).
    """
    status = measure_status(feature, name)
    qualifier = measure_qualifier(status, compact=compact or marked)
    if not status.available:
        return str(qualifier)
    value = prefix + format_value(float(feature.params[name]))
    if not with_source or qualifier is None:
        return value
    return f"{value} {MEASURE_MARK}" if marked else f"{value} · {qualifier}"


def _measure_group(
    feature: Feature,
    fields: tuple[tuple[str, str, Callable[[float], str]], ...],
    separator: str,
    *,
    compact: bool = False,
    marked: bool = False,
) -> str:
    """Gleiche Quellen teilen ihren Zusatz; gemischte bleiben je Zahl kenntlich."""
    statuses = [measure_status(feature, name) for name, _prefix, _formatter in fields]
    common = all(status == statuses[0] and status.available for status in statuses)
    value = separator.join(
        measure_text(
            feature,
            name,
            prefix=prefix,
            format_value=formatter,
            with_source=not common,
            compact=compact,
            marked=marked,
        )
        for name, prefix, formatter in fields
    )
    qualifier = measure_qualifier(statuses[0], compact=compact or marked) if common else None
    if qualifier is None:
        return value
    return f"{value} {MEASURE_MARK}" if marked else f"{value} · {qualifier}"


def feature_measure_tip(feature: Feature, *names: str) -> str:
    """Die gemeinsame Maßauskunft für Tooltip, Statushinweis und Vorlesen."""
    chosen = names or tuple(
        name
        for name in (
            "diameter",
            "radius",
            "tube_diameter",
            "angle",
            "pitch",
            "area",
            "volume",
            "length",
            "depth",
        )
        if name in feature.params
    )
    descriptions = dict.fromkeys(
        str(measure_explanation(measure_status(feature, name))) for name in chosen
    )
    return "\n".join(descriptions)


def feature_source(feature: Feature) -> str:
    """Woher die Maße eines Merkmals kommen — nur das warnende Wort, ohne Zahl.

    Für die Maßgruppe im Bild (RM-516): Die Zahl steht dort im Feld, und
    davor noch einmal „Aktuell: Ø5,20 mm“ hieß denselben Durchmesser zweimal
    lesen. Eine direkte Quelle sagt nichts (``compact``); dann bleibt die
    Zeile leer.
    """
    words = dict.fromkeys(
        str(word)
        for name in ("diameter", "radius", "tube_diameter", "length", "pitch", "area", "volume")
        if name in feature.params
        and (word := measure_qualifier(measure_status(feature, name), compact=True)) is not None
    )
    if not words:
        return ""
    return tr("Ausgangswert: {source}").format(source=", ".join(words))


def feature_measure(feature: Feature, *, compact: bool = False, marked: bool = False) -> str:
    """Die eine Zahl, die dieses Merkmal ausmacht — ohne seinen Namen.

    Getrennt vom Namen, weil der Objektbaum zwei Spalten hat: dort stand die
    ganze Beschriftung links und rechts der Typ („hole", „face"). Links war
    damit abgeschnitten, was rechts gefehlt hat.

    ``compact`` gilt für die Marken in der Ansicht, ``marked`` für die
    Maßspalte des Objektbaums (siehe :func:`measure_text`).
    """
    params = feature.params
    if feature.kind == "hole":
        return measure_text(feature, "diameter", prefix="Ø", compact=compact, marked=marked)
    # **Beide Maße, und die Breite zuerst.** Ein Langloch bestellt man wie ein
    # Blech: „8 auf 20". Die Breite entscheidet über die Schraube, die Länge
    # über ihr Spiel — eine Zahl allein sagt keines von beidem. Das ``Ø`` steht
    # vorn, weil die Breite wirklich ein Durchmesser ist: die zwei runden Enden.
    if feature.kind == "slot":
        return _measure_group(
            feature,
            (("diameter", "Ø", length), ("length", "", length)),
            " × ",
            compact=compact,
            marked=marked,
        )
    # **R und nicht Ø**, weil eine Verrundung über ihren Radius benannt wird:
    # Der Kunde sagt „R3", der Slicer sagt „R3", Fusion sagt „R3". Ohne diese
    # Zeile blieb die Maßspalte des Objektbaums bei jeder Verrundung leer,
    # während sie bei jedem anderen Merkmal etwas zeigt.
    if feature.kind == "fillet":
        return measure_text(feature, "radius", prefix="R", compact=compact, marked=marked)
    # Zwei Vergleiche statt ``in``: So sieht mypy die Verzweigung vollständig
    # und hält die Zeile am Ende weiter für unerreichbar.
    if feature.kind == "face" or feature.kind == "curved_face":
        return measure_text(feature, "area", format_value=area, compact=compact, marked=marked)
    if feature.kind == "cone":
        # Eine Verengung nennt die Weite, die sie lässt: Ihr weites Ende ist die
        # Bohrung selbst, und „Verengung Ø8,25" neben „Sackbohrung Ø8,25" sagte
        # nicht, wie eng die Mündung ist (R3). Dasselbe Maß im Steckbrief.
        size = "opening" if feature.params.get("narrowing") and "opening" in params else "diameter"
        return _measure_group(
            feature,
            (("angle", "", lambda value: f"{value:.0f}°"), (size, "Ø", length)),
            " ",
            compact=compact,
            marked=marked,
        )
    if feature.kind == "sphere":
        return measure_text(feature, "diameter", prefix="Ø", compact=compact, marked=marked)
    # Zwei Zahlen ohne Wort, wie beim Kegel: Ringdurchmesser, dann Rohrstärke.
    # Ein Wort dazwischen wäre eine zweite Stelle, an der eine Sprache fehlt.
    #
    # **``diameter`` und nicht ``ring_diameter``.** Der Schlüssel ist ein
    # Vertrag und keine Beschriftung: Die Zuordnung liest die Größe eines
    # Merkmals artenunabhängig aus ``params["diameter"]``. Unter einem eigenen
    # Namen war die Komponente null — zwei Tori mit Ringdurchmesser 40 und 60
    # kosteten gegeneinander 0,0 und waren damit ununterscheidbar (§21.2).
    if feature.kind == "torus":
        return _measure_group(
            feature,
            (("diameter", "Ø", length), ("tube_diameter", "Ø", length)),
            " / ",
            compact=compact,
            marked=marked,
        )
    if feature.kind == "edge_loop":
        # Dieselbe Unterscheidung wie im Steckbrief: Die Sammelzeile trägt
        # ``loops`` und meint Stellen, nicht Kanten.
        more = int(params.get("loops", 0))
        if more:
            return f"{more} {tr('weitere offene Stellen')}"
        return f"{params.get('open_edges', 0)} {tr('offene Kanten')}"
    # **Der Zwilling zwei Funktionen weiter oben.** Dort bekamen Zapfen
    # und Gewinde am 27.08.2026 ihren Namen; hier blieb die Spalte
    # daneben leer, und niemandem fiel es auf — der Objektbaum hat zwei
    # Spalten, und repariert wurde eine. Die Maße stehen wie die Namen
    # im Steckbrief: der Zapfen mit seinem Durchmesser, das Gewinde mit
    # Durchmesser und Steigung, denn die macht es aus (Ø6 mit 1,0 ist
    # M6, Ø6 mit 0,75 ist M6 fein).
    if feature.kind == "pin":
        return measure_text(feature, "diameter", prefix="Ø", compact=compact, marked=marked)
    if feature.kind == "thread":
        text = _measure_group(
            feature,
            (("diameter", "Ø", length), ("pitch", "", length)),
            " × ",
            compact=compact,
            marked=marked,
        )
        # **Was vom Üblichen abweicht, steht dabei** (P2.5): Ein Linksgewinde und
        # ein mehrgängiges nennen es — ein rechtsgängiges, eingängiges nicht,
        # sonst trüge jede Zeile zwei Wörter, die nichts unterscheiden.
        if feature.params.get("handedness") == "left":
            text = f"{text} · {tr('linksgängig')}"
        starts = feature.params.get("starts")
        if isinstance(starts, int) and not isinstance(starts, bool) and starts > 1:
            text = f"{text} · {tr('Gangzahl')} {starts}"
        # Ein kegeliges Rohrgewinde ebenso: Sein Durchmesser gilt in der Mitte.
        if thread_is_tapered(feature):
            text = f"{text} · {tr('kegelig')}"
        return text
    # **Das Volumen und kein Durchmesser.** Ein Einschluss hat keine Form, die
    # eine Länge beschriebe — er ist, was ein Negativkörper hinterlassen hat,
    # und das kann ein Zylinder sein oder sonst etwas. Was der Kunde wissen
    # will, ist, wie viel Luft im Teil steckt.
    if feature.kind == "void":
        return measure_text(feature, "volume", format_value=volume, compact=compact, marked=marked)
    # Zahl und Teilung, wie man ein Muster bestellt: „196 · 10,4 mm". Die
    # Zellbreite und die Tiefe stehen im Panel und im Steckbrief.
    if feature.kind == "pattern":
        count = int(params.get("count", 0))
        pitch = measure_text(feature, "pitch", compact=compact, marked=marked)
        return f"{count} {tr('Zellen')} · {pitch}" if pitch else f"{count} {tr('Zellen')}"
    # Wie bei ``feature_name`` oben: Seit alle elf Arten ein Maß haben,
    # hält mypy diese Zeile für unerreichbar — und **das ist die
    # Bestätigung, dass die Verzweigung vollständig ist**. Sie bleibt
    # trotzdem, weil ``kind`` aus einer Projektdatei kommt und eine
    # fremde Fassung eine Art tragen kann, die dieser Bestand nicht
    # kennt. Eine leere Spalte ist besser als ein Absturz beim Öffnen.
    return ""  # type: ignore[unreachable]


def feature_label(feature_id: FeatureId, feature: Feature, *, compact: bool = False) -> str:
    """``Bohrung 3 · ⌀4,2`` — die Beschriftung, die §18.5 verlangt, Name
    zuerst.

    Für die Stellen, an denen nur eine Zeile Platz hat: Viewport-Beschriftung
    und Statusleiste. Wo zwei Spalten stehen, gehören Name und Maß getrennt.
    ``compact`` für die Marken in der Ansicht: nur das warnende Herkunftswort.
    """
    measure = feature_measure(feature, compact=compact)
    name = feature_name(feature_id, feature)
    return f"{name} · {measure}" if measure else name


def edge_label(entry: Any) -> str:
    """``Senkrecht · 20 mm · x -20, y -15`` — eine Kante in einer Zeile (E4).

    Was der Kunde in der Kantenliste liest. Der Schlüssel dahinter beschreibt
    dieselbe Kante für den Kern (``brep.edit.edge_key``) und taugt als
    Beschriftung nicht: Er ist eine Kennung aus sechs Zahlen.

    Drei Angaben, und jede beantwortet eine eigene Frage: **wie** sie liegt
    (senkrecht, waagerecht oder schräg), **wie lang** sie ist, und **wo** sie
    steht. Die Länge geht durch :func:`length` und folgt damit der
    Anzeigeeinheit; der Ort ebenso.

    ``entry`` ist ein ``brep.edit.EdgeInfo`` — als ``Any`` angenommen, weil
    ``labels`` ohne den optionalen B-Rep-Kern importierbar bleiben muss (§30).
    """
    # Die Lage fragt der Kern (``edges.edge_lie_of``): An einem Ring ist die
    # Richtung null, und ``flat`` galt an jedem — die Mündung einer quer
    # liegenden Bohrung hieß „Waagerecht“ (RM-269). Erst hier geladen: Die
    # Kantenrechnung zieht die Boolesche Kette nach, und ``labels`` lädt früh.
    from app.core.geom.edges import edge_lie_of

    shown = edge_lie_of(entry)
    if shown == "upright":
        lie = tr("Senkrecht")
    elif shown == "flat":
        lie = tr("Waagerecht")
    else:
        lie = tr("Schräg")
    x, y, _z = entry.middle
    place = f"x {length(x, with_unit=False)}, y {length(y, with_unit=False)}"
    return f"{lie} · {length(float(entry.length))} · {place}"


def local_timestamp(value: str) -> str:
    """Einen gespeicherten ISO-Zeitpunkt in lokaler Zeit und Anzeigesprache ausgeben."""
    instant = QDateTime.fromString(value, Qt.DateFormat.ISODateWithMs)
    if not instant.isValid():
        return value
    return QLocale(get_language()).toString(instant.toLocalTime(), QLocale.FormatType.ShortFormat)


def local_moment(value: datetime) -> str:
    """Datum und Uhrzeit eines Zeitpunkts in der Anzeigesprache.

    Schwester zu :func:`local_timestamp`, die aus einem gespeicherten
    ISO-Text kommt; diese hier nimmt, was ``datetime.fromtimestamp`` einer
    Dateizeit liefert. Ohne sie stand im Wiederherstellungsdialog ein festes
    ``%d.%m.%Y %H:%M`` — deutsche Reihenfolge in jeder Sprache, während die
    relativen Angaben daneben („vor einer Stunde") längst mitwanderten.

    **Das Jahr bleibt vierstellig.** ``ShortFormat`` kürzt es je nach Sprache
    auf zwei Ziffern — „05.03.26" —, und das war vorher nicht so; eine
    Sicherung aus einem anderen Jahrzehnt ließe sich dann schlechter einordnen
    als zuvor. Geändert wird deshalb nur diese eine Stelle im Muster:
    Reihenfolge, Trenner und Uhrzeitform bleiben Sache der Sprache. Dieselbe
    Bauart wie in :func:`calendar_date`, die den Wochentag herausnimmt.
    """
    locale = QLocale(get_language())
    pattern = locale.dateTimeFormat(QLocale.FormatType.ShortFormat)
    if "yyyy" not in pattern:
        pattern = pattern.replace("yy", "yyyy")
    return locale.toString(QDateTime.fromSecsSinceEpoch(int(value.timestamp())), pattern)


def calendar_date(value: date | None) -> str:
    """Ein Kalendertag mit ausgeschriebenem Jahr in der Anzeigesprache."""
    if value is None:
        return ""
    # ``QLocale()`` folgt der Prozesssprache. Solidon kann seine Sprache aber
    # im laufenden Prozess wechseln; dann bliebe ein ausgeschriebener Monat
    # sonst deutsch in einem spanischen Dialog stehen.
    locale = QLocale(get_language())
    pattern = locale.dateFormat(QLocale.FormatType.LongFormat)
    # Der Wochentag macht aus „bis mindestens 31. Oktober“ einen schwer
    # lesbaren Satz. Reihenfolge, Monatsname und Bindewörter bleiben Sache der
    # Sprache; nur ``dddd`` samt anschließender Trennung fällt weg.
    without_weekday = pattern.replace("dddd", "").lstrip(" ,")
    return locale.toString(QDate(value.year, value.month, value.day), without_weekday)


def calendar_day(value: str) -> str:
    """Ein gespeicherter ISO-Tag (JJJJ-MM-TT) als Kalendertag der Anzeigesprache.

    Leer heißt unbekannt und wird auch so genannt — die Detailseite des
    Lagers schreibt keine leere Zelle neben „Gekauft am".
    """
    if not value:
        return tr("Unbekannt")
    try:
        return calendar_date(date.fromisoformat(value))
    except ValueError:
        return value


class _DateEditor(QDateEdit):
    """Ein Datumsfeld, in das man vom Sonderwert „Unbekannt" aus einfach lostippen kann.

    Gemessen am 19.09.2026: Zeigt ein ``QDateEdit`` seinen Sonderwerttext,
    hängt es getippte Ziffern hinten an — „Unbekannt05092026" — und behält
    das Minimum. Die erste Ziffer setzt deshalb erst ein Datum (heute) und
    wählt den ersten Abschnitt; danach tippt sich das Feld wie gewohnt und
    springt nach zwei Ziffern weiter. Ein getipptes Trennzeichen zwischen den
    Abschnitten wechselt den Abschnitt, statt in ihm zu landen.
    """

    _advanced_by_digit = False

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt-Name
        text = event.text()
        if text.isdigit():
            if self.date() == self.minimumDate():
                # Der 1. Januar, nicht heute: Ein Tag wird vor dem Monat
                # getippt, und ein „31" in einem Monat mit dreißig Tagen
                # würde still zum „30" (gemessen: 31.12.2024 → 30.12.2024).
                self.setDate(QDate(QDate.currentDate().year(), 1, 1))
                self.setCurrentSectionIndex(0)
                self.setSelectedSection(self.currentSection())
            before = self.currentSectionIndex()
            super().keyPressEvent(event)
            # Zwei Ziffern springen von selbst weiter; ein danach getipptes
            # Trennzeichen darf nicht noch einmal springen.
            self._advanced_by_digit = self.currentSectionIndex() != before
            return
        if text in (".", ",", "/", "-") and self.date() != self.minimumDate():
            if not self._advanced_by_digit and self.currentSectionIndex() < self.sectionCount() - 1:
                # Eine einzelne Ziffer („7.3.2025"): erst den Abschnitt
                # abschließen, dann weiter — sonst verfällt die Ziffer.
                self.interpretText()
                self.setCurrentSectionIndex(self.currentSectionIndex() + 1)
                self.setSelectedSection(self.currentSection())
            self._advanced_by_digit = False
            event.accept()
            return
        self._advanced_by_digit = False
        super().keyPressEvent(event)


class DateField(QWidget):
    """Ein freiwilliges Datum: Kalender in der Anzeigesprache, „Unbekannt" als eigener Wert.

    Bis zum 19.09.2026 war das ein Textfeld mit dem Platzhalter „JJJJ-MM-TT";
    ein deutscher Kunde tippte „05.09.2026" und wurde abgewiesen. Hier tippt
    er in der Reihenfolge seiner Sprache oder klickt im Kalender; gespeichert
    wird weiter ISO, denn die Datei kennt eine Schreibweise. ``text()`` und
    ``setText()`` sprechen ISO, damit Dialog und Kern dieselbe Prüfung
    teilen (``filaments.valid_date``) und der Rest des Dialogs unverändert
    bleibt. Der Knopf daneben setzt zurück auf „Unbekannt" — ein Datumsfeld
    hat keine Löschtaste, und bis zum Minimum zu drehen ist kein Weg.
    """

    textChanged = Signal(str)  # Qt-Signalname wie bei QLineEdit

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.editor = _DateEditor(self)
        self.editor.setCalendarPopup(True)
        locale = QLocale(get_language())
        self.editor.setLocale(locale)
        pattern = locale.dateFormat(QLocale.FormatType.ShortFormat)
        if "yyyy" not in pattern:
            pattern = pattern.replace("yy", "yyyy")
        self.editor.setDisplayFormat(pattern)
        self.editor.setMinimumDate(QDate(1970, 1, 1))
        self.editor.setMaximumDate(QDate(2099, 12, 31))
        self.editor.setSpecialValueText(tr("Unbekannt"))
        self.editor.setDate(self.editor.minimumDate())
        self.editor.dateChanged.connect(self._changed)
        layout.addWidget(self.editor, 1)
        self.clear_button = QToolButton(self)
        self.clear_button.setText(tr("Unbekannt"))
        self.clear_button.setToolTip(tr("Das Datum wieder auf Unbekannt setzen."))
        self.clear_button.setAccessibleDescription(self.clear_button.toolTip())
        self.clear_button.clicked.connect(self.clear)
        layout.addWidget(self.clear_button)
        self.setFocusProxy(self.editor)
        self._show_clear_state()

    def text(self) -> str:
        """Der Tag als ISO-Text, leer für unbekannt — was der Kern speichert."""
        chosen = self.editor.date()
        if chosen == self.editor.minimumDate():
            return ""
        return chosen.toString(Qt.DateFormat.ISODate)

    def setText(self, value: str) -> None:  # noqa: N802 - Gegenstück zu QLineEdit.setText
        """Einen gespeicherten ISO-Tag übernehmen; alles andere bleibt unbekannt."""
        parsed = QDate.fromString(value.strip(), Qt.DateFormat.ISODate) if value else QDate()
        self.editor.setDate(parsed if parsed.isValid() else self.editor.minimumDate())

    def clear(self) -> None:
        self.editor.setDate(self.editor.minimumDate())

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802 - Gegenstück zu QLineEdit
        """Ein Datumsfeld zeigt „Unbekannt" statt eines Platzhalters; der Satz wird Kurzhilfe."""
        self.editor.setToolTip(text)

    def _changed(self, _date: QDate) -> None:
        self._show_clear_state()
        self.textChanged.emit(self.text())

    def _show_clear_state(self) -> None:
        self.clear_button.setEnabled(bool(self.text()))


#: Ein Slicer, wie ihn Druckdialog, Erststart und Einstellungen nennen — die
#: Regel steht im Kern, weil die Meldungen der Übergabe ihn genauso nennen
#: (``SlicerSetup.name``).
slicer_title: Final = discover.slicer_title


def printer_title(printer: PrinterProfile) -> str:
    """Der Drucker, wie ihn Listen, Kopfzeile und Druckziel nennen: ohne die
    Düse seiner Slicervariante (Entscheidung Robert).

    Die Slicer führen jede Düse als eigenes Profil („Bambu Lab A1 0.4
    nozzle“); gewählt wird der Drucker, die Düse im Druckdialog. Nach dem
    Wechsel dort stünde im Namen noch die alte. Gekürzt wird nur ein Profil mit
    Hersteller — ein selbst benannter Drucker heißt, wie der Kunde ihn nannte.
    """
    title = str(printer.title)
    return model_name(title) if printer.vendor.strip() else title


def deadline_date(state: Activation) -> str:
    """Der Stichtag der Demo, wie ihn der Nutzer liest.

    Ein Ort dafür, weil er an fünf Stellen steht: Statusleiste, Über-Dialog,
    Freischaltdialog, Ersteinrichtung und die Meldung, mit der sich eine
    abgelaufene Demo verabschiedet. Fünf Formulierungen desselben Datums
    lesen sich wie fünf verschiedene Fristen.
    """
    return calendar_date(state.deadline)


def demo_line(state: Activation) -> str:
    """„Demo — noch 47 Tage, bis zum 30.10.2026".

    Steht dauerhaft in der Statusleiste und nicht erst am vorletzten Tag. Für
    ein Kaufprodukt wäre das Druck (Veröffentlichungskonzept §2 C); für eine
    Demo mit hartem Ende ist es die Zusage, dass niemand überrascht wird —
    wer am 28.10. ein Projekt anfängt, soll es vorher gewusst haben.
    """
    return demo_days(state, sentence=False)


def demo_days(state: Activation, *, sentence: bool = True) -> str:
    """Die Frist der Demo, als Zeile oder als Satz — mit „Tag" bei einem.

    **Am letzten Tag stand „noch 1 Tage".** Der Stichtag zählt mit
    (``store.days_left``: „am 30.10. bleibt ein Tag übrig"), und genau an
    diesem Tag las jeder Demo-Kunde den Fehler, an drei Stellen zugleich.
    Er heißt jetzt, was er ist: „heute letzter Tag" — verständlicher als
    „noch 1 Tag" (Konzept Demo→1.0 §5, Punkt 3), und der Tag, an dem man
    speichert und exportiert.
    """
    if state.days_left == 1:
        template = (
            tr("Demo — heute letzter Tag ({date}).")
            if sentence
            else tr("Demo — heute letzter Tag ({date})")
        )
    else:
        template = (
            tr("Demo — noch {days} Tage, bis zum {date}.")
            if sentence
            else tr("Demo — noch {days} Tage, bis zum {date}")
        )
    return template.format(days=state.days_left, date=deadline_date(state))


#: Ab wie vielen Resttagen die Demo ihr Ende einmal je Sitzung ankündigt —
#: sieben, also ab dem 24.10. für eine Demo bis zum 30.10. (Konzept Demo→1.0
#: §5, Punkt 2). Gezählt wird mit dem Stichtag, wie ``store.days_left``.
SALE_NOTICE_DAYS = 7


def sale_notice(state: Activation) -> str:
    """Der ruhige Hinweis der letzten Demowoche — oder nichts.

    **Einmal je Sitzung, nicht modal, nie eine Kaufaufforderung** (Konzept
    Demo→1.0 §5, Punkt 2): Er sagt, wann die Demo endet, wann 1.0 kommt und
    dass die eigenen Projekte bleiben, und nennt den Weg, auf dem der Kunde
    mehr erfährt. Die dauerhafte Statuszeile trägt das Datum schon; dieser
    Satz trägt die Pause und den Start, die sonst erst der Abschied nennt —
    und der kommt zu spät, um vorher zu speichern.
    """
    if not state.in_demo or not 0 < state.days_left <= SALE_NOTICE_DAYS:
        return ""
    from app.branding import APP_NAME, PLANNED_SALE_START

    return str(
        tr(
            "Die Demo endet am {date}. {app} 1.0 ist für den {start} um 10:00 Uhr "
            "geplant, Ihre Projekte bleiben erhalten. Mehr unter Hilfe → Solidon "
            "freischalten …"
        )
    ).format(
        date=deadline_date(state),
        app=APP_NAME,
        start=calendar_date(PLANNED_SALE_START.date()),
    )


def trial_days(days: int, *, way: bool = False) -> str:
    """Die Resttage des Testlaufs — mit dem Menüweg für die Statusleiste.

    Singular wie in :func:`demo_days`: Die Statuszeile erscheint erst ab
    zwei Tagen, also stand „noch 1 Tage" genau am Tag davor.
    """
    one = days == 1
    if way:
        template = (
            tr("Testzeitraum: noch {days} Tag — Hilfe → Solidon freischalten …")
            if one
            else tr("Testzeitraum: noch {days} Tage — Hilfe → Solidon freischalten …")
        )
    else:
        template = (
            tr("Testzeitraum: noch {days} Tag.") if one else tr("Testzeitraum: noch {days} Tage.")
        )
    return template.format(days=days)


#: Die Druckplatten der Orca-Familie in der Sprache des Kunden. Der Slicer
#: nennt sie englisch und nach seinem Innenleben — „High Temp Plate" ist die
#: glatte PEI-Platte, und das weiß nur, wer Bambu Studio kennt.
_PLATE_TITLES: Final[dict[str, TranslatableText]] = {
    "Cool Plate": _("Kühle Platte"),
    "Engineering Plate": _("Engineering-Platte"),
    "High Temp Plate": _("Glatte PEI-Platte"),
    "Textured PEI Plate": _("Texturierte PEI-Platte"),
    "Supertack Plate": _("Supertack-Platte"),
    "Textured Cool Plate": _("Texturierte kühle Platte"),
    "Epoxy Resin Plate": _("Epoxidharz-Platte"),
}


def plate_title(name: str) -> str:
    """Die Druckplatte, wie der Kunde sie nennt — unbekannte bleiben, wie sie heißen."""
    title = _PLATE_TITLES.get(name)
    return str(title) if title is not None else name
