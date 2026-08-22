"""Kurze Texte, auf die sich mehrere Teile der Oberfläche einigen müssen.

Ein Merkmal wird in der Viewport-Überlagerung, im Objektbaum und in der
Statusleiste gleich geschrieben — ``hole_3 · ⌀4.2``. Ein Ort dafür heißt: der
Name, den der Nutzer liest, ist der Name, den der Agent benutzt (§18.5,
Leitprinzip 5).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from PySide6.QtCore import QLocale, Signal
from PySide6.QtGui import QColor, QValidator
from PySide6.QtWidgets import QDoubleSpinBox, QWidget

from app.core import figures
from app.core.activation import Activation
from app.core.errors import AppError
from app.core.registry import MENU_GROUPS as MENU_GROUPS
from app.core.registry import group_title as group_title
from app.core.types import Feature, FeatureId
from app.core.units import (
    DEGREE_UNIT,
    LengthUnit,
    decimals_for,
    format_area,
    format_length,
    format_volume,
    from_mm,
    to_mm,
)
from app.i18n import TranslatableText, _, tr

# Die Zuordnung Kategorie → Menü (MENU_GROUPS, group_title) lebt seit der
# Agent-Vertiefung (4.3) im Register: neben Leiste und Kontextmenü braucht sie
# jetzt auch der Kern — die Werkzeugbeschreibungen nennen den Menüort, damit
# der Chat als Suchfeld taugt (§2.6). Die Nutzer der Oberfläche importieren
# beide weiter von hier; der Import darüber ist die Weiterleitung.


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
    return text.replace(".", separator) if separator != "." else text


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
#: Überlagerung, im Objektbaum und in der Statusleiste). Deshalb liegt die
#: Einheit hier, wie ``QLocale`` für das Dezimaltrennzeichen daneben.
#:
#: **Ein ausdrücklich übergebenes Argument gewinnt.** Das ist kein zweites
#: Verzeichnis, sondern ein Vorrang: Wer eine Einheit nennt, meint sie.
_DISPLAY_UNIT: LengthUnit = "mm"


def set_display_unit(unit: LengthUnit) -> None:
    """Stellt die Anzeigeeinheit für den ganzen Prozess (§19.3).

    Der Kern bleibt bei Millimetern — hier wird nur geschrieben, nicht
    gerechnet.
    """
    global _DISPLAY_UNIT
    _DISPLAY_UNIT = unit


def display_unit() -> LengthUnit:
    """Die eingestellte Anzeigeeinheit."""
    return _DISPLAY_UNIT


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

    def validate(self, text: str, pos: int) -> object:
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
            # Qts Stub sagt ``object``; tatsächlich kommt das Tripel aus
            # Zustand, Text und Position zurück.
            checked = cast(
                "tuple[QValidator.State, str, int]",
                super().validate(reading, min(pos, len(reading))),
            )
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


def length(value_mm: float, unit: LengthUnit | None = None, with_unit: bool = True) -> str:
    """Eine Länge, wie die Oberfläche sie schreibt.

    Ohne ``unit`` gilt die eingestellte Anzeigeeinheit — siehe
    :data:`_DISPLAY_UNIT`. Vorher stand hier „mm" als Vorgabe, und damit war
    jede Ausgabe, die keine Einheit durchgereicht bekam, gegen die Einstellung
    stumm.
    """
    return localised(format_length(value_mm, unit or _DISPLAY_UNIT, with_unit))


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
    text = format_length(value_mm, unit or _DISPLAY_UNIT, with_unit=False)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return localised(text or "0")


def area(value_mm2: float, unit: LengthUnit | None = None) -> str:
    """Eine Fläche, wie der Nutzer sie liest — in seiner Einheit und mit
    seinem Trennzeichen."""
    return localised(format_area(value_mm2, unit or _DISPLAY_UNIT))


def volume(value_mm3: float, unit: LengthUnit | None = None) -> str:
    """Ein Volumen, wie die Oberfläche es schreibt."""
    return localised(format_volume(value_mm3, unit or _DISPLAY_UNIT))


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


#: Auswahlwerte, die selbst kein Name sind. Der Schlüssel bleibt englisch, weil
#: er in der Projektdatei steht (§4.2); gezeigt wird der übersetzte Text. Was
#: schon ein Name ist — „M4", „PLA", „z" — steht hier nicht.
#: Wie ein Auswahlwert heißt, wenn er nicht schon sein eigener Name ist.
#:
#: Die Liste ist flach, und das ist eine Entscheidung: derselbe Schlüssel
#: bedeutet in dieser Anwendung überall dasselbe. Wo das einmal nicht mehr
#: stimmt, bekommt der Wert einen eigenen Schlüssel — nicht diese Liste eine
#: zweite Ebene.
_CHOICE_NAMES: dict[str, TranslatableText] = {
    "mouth": _("Mündung"),
    "centre": _("Mitte"),
    # Die acht Texturmuster standen als „knurl_diamond" und „voronoi" im
    # Dialog: englische Schlüssel, unübersetzt, und damit gegen Regel 20 dem
    # Geist nach. Die Namen kommen aus dem Abbildungskatalog, der dieselben
    # Kacheln beschriftet — zwei Listen wären eine Frage der Zeit.
    **figures.TEXTURE_NAMES,
    # Und dieselbe Sorte Fund im selben Dialog eine Zeile tiefer: „Art:
    # raised", „Auflegen: flat". Über das ganze Register waren es
    # sechsundzwanzig Werte; ``tests/test_translations.py`` hält sie jetzt
    # zusammen.
    # Die Symmetrieebenen des Formens. „xz" ist für den Kern der richtige
    # Schlüssel und für den Dialog kein Wort — „ohne" und „X- und Z-Ebene"
    # sagen dasselbe in lesbar. Die einzelnen Achsen bleiben, wie sie sind:
    # ein „x" ist selbst schon der Name (siehe ``SELF_NAMING`` in der Suite).
    "none": _("Ohne"),
    "xy": _("X- und Y-Ebene"),
    "xz": _("X- und Z-Ebene"),
    "yz": _("Y- und Z-Ebene"),
    "xyz": _("Alle drei Ebenen"),
    # Die drei Projektionen des Reliefs. „planar" ist kein Wort, das jemand
    # in einem Auswahlfeld erwartet, und „spherical" schon gar nicht — benannt
    # wird, was passiert, nicht wie die Rechnung heißt.
    "planar": _("Von oben"),
    "cylindrical": _("Um die Achse"),
    "spherical": _("Über die Kugel"),
    "face": _("Auf eine Fläche"),
    "raised": _("Erhaben"),
    "engraved": _("Vertieft"),
    "flat": _("Flach"),
    "cylinder": _("Umlaufend"),
    "all": _("Alle"),
    "top": _("Oben"),
    "bottom": _("Unten"),
    "side": _("Seitlich"),
    "horizontal": _("Waagerecht"),
    "vertical": _("Senkrecht"),
    "linear": _("Geradlinig"),
    "circular": _("Kreisförmig"),
    "origin": _("Ursprung"),
    "bed": _("Druckbett"),
    "corner": _("Ecke"),
    # Wie eine Kollision geprüft wurde: genau am Netz oder nur über die
    # Hüllquader. Der Befund trug „exact" und „box" als rohes Englisch in
    # den Tooltip — dieselbe Sorte Fund wie bei den Texturmustern.
    "exact": _("Genau"),
    "box": _("Über den Hüllquader"),
    "pin": _("Stift"),
    "bore": _("Bohrung"),
    "rectangle": _("Rechteck"),
    "circle": _("Kreis"),
    "polygon": _("Vieleck"),
    "slot": _("Langloch"),
    # Die vier Verbinder. „round" und „hex" wären als Schlüssel noch zu
    # erraten, „dovetail" und „snap" nicht — und das sind die beiden, für die
    # man sich bewusst entscheidet.
    "round": _("Rund"),
    "hex": _("Sechskant"),
    "dovetail": _("Schwalbenschwanz"),
    "snap": _("Schnapper"),
    "honeycomb": _("Wabe"),
    "cubic": _("Würfelgitter"),
    "auto": _("Automatisch"),
    # **Die Druckeinstellungen waren die zweite Feldquelle, und sie stand hier
    # nicht drin.** ``tests/test_translations.py`` prüft Regel 20 für
    # Auswahlwerte am Operationsregister; die sechsundfünfzig Felder des
    # Druckdialogs (``print_settings_dialog.FIELDS``) sind eine eigene Liste
    # und liefen an der Prüfung vorbei. Im deutschen Fenster stand deshalb
    # „Naht: aligned", „Wandbahnen: arachne", „Plattenhaftung: brim" — und im
    # Füllmuster englische Schlüssel **neben** deutschen Namen: grid, lines,
    # triangles, Wabe, Würfelgitter.
    #
    # Wo der englische Begriff der ist, unter dem der Kunde ihn in seinem
    # Slicer wiederfindet, steht er in Klammern dahinter — dasselbe Muster wie
    # „Exakter Körper (B-Rep)".
    "aligned": _("Ausgerichtet"),
    "nearest": _("Nächstgelegen"),
    "random": _("Zufällig"),
    # Nicht „Hinten" und nicht „Rückseite": Das erste ist die **Rückansicht**
    # im Ansichtsmenü (Strg+2, englisch „Back"), das zweite der Name einer
    # **Fläche**, deren Normale nach hinten zeigt (``_SIDES``). Ein
    # Katalogschlüssel trägt genau eine Bedeutung — mit einem für zwei bekäme
    # eine von ihnen das falsche Wort. (``TranslatableText`` kennt ein
    # ``context``-Feld, aber der Extraktor liest es nicht; siehe ROADMAP.)
    "rear": _("Auf der Rückseite"),
    "classic": _("Klassisch"),
    # Eigennamen wie „Gyroid": so heißt der Algorithmus, in jedem Slicer und in
    # jeder Sprache. Dasselbe gilt für die drei Haftarten — im Dialog heißen die
    # Felder daneben „Skirt-Runden", „Brim-Breite" und „Raft-Schichten", und ein
    # Wert, der anders heißt als sein Feld, ist eine Fährte ins Nichts.
    "arachne": _("Arachne"),
    "gyroid": _("Gyroid"),
    "grid": _("Gitter"),
    "lines": _("Linien"),
    "triangles": _("Dreiecke"),
    "tree": _("Baum"),
    "everywhere": _("Überall"),
    "build_plate": _("Nur von der Platte"),
    "skirt": _("Skirt"),
    "brim": _("Brim"),
    "raft": _("Raft"),
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
    "attempted": _("Versuchte Stufen"),
    "exit_code": _("Rückgabewert"),
    "first": _("Erste Bedingung"),
    "first_layer": _("Erste Schicht"),
    "overshoot": _("Überstand je Achse"),
    "second": _("Zweite Bedingung"),
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
    "bones": _("Knochen"),
    "bore": _("Bohrung"),
    "brush": _("Pinsel"),
    "bytes": _("Bytes"),
    "candidates": _("Kandidaten"),
    "cavities": _("Hohlräume"),
    "chain": _("Kette"),
    "changes": _("Änderungen"),
    "character": _("Zeichen"),
    "choice": _("Wahl"),
    "choices": _("Auswahl"),
    "checked": _("Geprüft"),
    "clearance": _("Spiel"),
    "comfortable": _("Bequem"),
    "components": _("Komponenten"),
    "constraint": _("Bedingung"),
    "contours": _("Konturen"),
    "core": _("Kern"),
    "count": _("Anzahl"),
    "cut": _("Schnitt"),
    "cycle": _("Zyklus"),
    "depth": _("Tiefe"),
    "deviation": _("Abweichung"),
    "diameter": _("Durchmesser"),
    "drawn_width": _("Gezeichnete Breite"),
    "detail": _("Einzelheit"),
    "edge": _("Kante"),
    "edges": _("Kanten"),
    "entries": _("Einträge"),
    "estimated": _("Geschätzt"),
    "expected": _("Erwartet"),
    "got": _("Bekommen"),
    "expected_prefix": _("Erwarteter Anfang"),
    "faces": _("Flächen"),
    "feature": _("Merkmal"),
    "field": _("Feld"),
    "file": _("Datei"),
    "file_version": _("Dateiversion"),
    "first_kind": _("Erste Art"),
    "fit": _("Passung"),
    "format": _("Format"),
    "excess": _("Überstand"),
    "footprint": _("Standfläche"),
    "formats": _("Formate"),
    "from": _("Von"),
    "gap": _("Spalt"),
    "given": _("Vorhanden"),
    "grams": _("Gramm"),
    "grid": _("Raster"),
    "groups": _("Gruppen"),
    "height": _("Höhe"),
    "key_major": _("Schlüsselversion"),
    "kind": _("Art"),
    "known": _("Bekannt"),
    "known_faces": _("Bekannte Flächen"),
    "layer": _("Schicht"),
    "layer_height": _("Schichthöhe"),
    "layers": _("Schichten"),
    "limit": _("Grenze"),
    "materials": _("Materialien"),
    "lost": _("Verloren"),
    "major": _("Hauptversion"),
    "material": _("Material"),
    "maximum": _("Höchstwert"),
    "measured": _("Gemessen"),
    "megabytes": _("Megabyte"),
    "minimum": _("Mindestwert"),
    "minutes": _("Minuten"),
    "missing": _("Fehlt"),
    "name": _("Name"),
    "neck": _("Hals"),
    "needed": _("Nötig"),
    "node": _("Knoten"),
    "nominal": _("Nennmaß"),
    "now": _("Jetzt"),
    "nozzle": _("Düse"),
    "object": _("Objekt"),
    "op": _("Operation"),
    "open_edges": _("Offene Kanten"),
    "operation": _("Operation"),
    "operations": _("Operationen"),
    "output": _("Ausgabe"),
    "overhang": _("Überhang"),
    "oversize": _("Übermaß"),
    "parameter": _("Parameter"),
    "params": _("Parameter"),
    "part": _("Baustein"),
    "parts": _("Teile"),
    "path": _("Pfad"),
    "pitch": _("Steigung"),
    "pixels": _("Bildpunkte"),
    "plate": _("Platte"),
    "plates": _("Platten"),
    "posed": _("Gestellt"),
    "position": _("Position"),
    "printed": _("Gedruckt"),
    "printer": _("Drucker"),
    "produced": _("Erzeugt"),
    "profile": _("Profil"),
    "radius": _("Radius"),
    "reachable": _("Erreichbar"),
    "read": _("Gelesen"),
    "reason": _("Grund"),
    "reference": _("Bezug"),
    "refused": _("Abgelehnt"),
    "regions": _("Bereiche"),
    "removed": _("Entfernt"),
    "requested": _("Angefragt"),
    "residual": _("Rest"),
    "role": _("Rolle"),
    "samples": _("Stichproben"),
    "saved": _("Gespart"),
    "scale": _("Maßstab"),
    "scheme": _("Schema"),
    "seams": _("Nähte"),
    "second_kind": _("Zweite Art"),
    "seconds": _("Sekunden"),
    "seed": _("Startwert"),
    "settings": _("Einstellungen"),
    "share": _("Anteil"),
    "shortcut": _("Kürzel"),
    "shared": _("Überschneidung"),
    "size": _("Größe"),
    "slicer": _("Slicer"),
    "slot": _("Platz"),
    "slots": _("Plätze"),
    "source": _("Quelle"),
    "sources": _("Quellen"),
    "span": _("Spannweite"),
    "stages": _("Stufen"),
    "status": _("Zustand"),
    "strokes": _("Striche"),
    "suffix": _("Endung"),
    "support": _("Stützen"),
    "supported": _("Unterstützt"),
    "target": _("Ziel"),
    "text": _("Text"),
    "to": _("Nach"),
    "tolerance": _("Toleranz"),
    "transaction": _("Transaktion"),
    "triangles": _("Dreiecke"),
    "type": _("Art"),
    "unit": _("Einheit"),
    "unpacked": _("Entpackt"),
    "url": _("Adresse"),
    "used_by": _("Benutzt von"),
    "value": _("Wert"),
    "vents": _("Entlüftungen"),
    "vertices": _("Ecken"),
    "volume": _("Volumen"),
    "wall": _("Wandstärke"),
    "wanted": _("Gewünscht"),
    "what": _("Was"),
    "where": _("Wo"),
    "z": _("Z"),
}


def plain_number(value: float) -> str:
    """Eine Zahl ohne Einheit, so kurz wie sie ehrlich ist.

    ``:g`` lässt die abschließenden Nullen weg: 15 bleibt 15 und wird nicht zu
    „15,00". Bei einem Anteil und einem Winkel ist das die ganze Auskunft.
    """
    return localised(f"{value:g}")


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


def value_text(key: str, value: object) -> str:
    """Der Wert mit seiner Einheit, in der Einheit der Anzeige (§19.3)."""
    for suffix, unit, show in _VALUE_UNITS:
        if not key.endswith(suffix):
            continue
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            # Keine Zahl, also keine Umrechnung. Die Einheit des Schlüssels
            # bleibt stehen: Sie ist dann die einzige Auskunft, die es gibt.
            return f"{localised_value(value)} {unit}"
        return show(number)
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


def value_line(key: str, value: object) -> str:
    """Eine Zeile „Beschriftung: Wert" für Tooltip und Einzelheiten.

    Die Zahl bekommt ihr Komma (§13) und ihre Einheit, der Rest bleibt, wie er
    ist — siehe :func:`value_text` und :func:`localised_value`.
    """
    return f"{value_label(key)}: {value_text(key, value)}"


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
    exakt, dann geht es um den Haken beim Anlegen. Oder er war es und ist es
    nicht mehr — dann hilft kein Haken, sondern nur die Reihenfolge.
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
                "„{step}“ hat aus dem exakten Körper ein Netz gemacht — Operationen des "
                "exakten Kerns gehen nur davor. Die Schritte ab dort zurücknehmen, diese "
                "Operation anwenden und den Rest neu setzen."
            )
        ).format(step=spoiled_by)
    # Der Satz sagte, woher exakte Körper *kommen*, und ließ offen, was man
    # jetzt tun soll: „aus den Grundformen mit „Exakt"" liest sich wie ein
    # eigener Menüeintrag, den es nicht gibt. Es ist ein Haken im Dialog — und
    # er ist nicht nur beim Anlegen zu haben: derselbe Haken steht im Dialog
    # des Schritts, wenn man ihn im Verlauf wieder öffnet.
    return str(
        tr(
            "Diese Operation braucht einen exakten Körper (B-Rep). Der Haken „Exakter "
            "Körper“ im Dialog der Grundform macht einen daraus — auch nachträglich, "
            "über den Schritt im Verlauf. Auch eine STEP-Datei bringt einen mit."
        )
    )


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
    """Ein Auswahlwert, wie der Nutzer ihn lesen kann.

    Normteilschlüssel sind englisch und kurz, weil sie Schlüssel sind — im
    Dialog standen sie aber als Beschriftung: „cable-5", „ptfe-4x2". Das tippt
    niemand ab und niemand erkennt es, ohne die Tabelle danebenzulegen.

    Erzeugt aus den Maßen und nicht als zweite Liste gepflegt: sonst hätte ein
    neues Normteil einen Namen an einer Stelle und keinen an der anderen. Was
    die Tabelle nicht kennt — „M4", „PLA", „z" —, bleibt, wie es ist; diese
    Werte sind selbst schon der Name.
    """
    from app.core.knowledge import standards

    named = _CHOICE_NAMES.get(value)
    if named is not None:
        return str(named)
    try:
        tube = standards.tube(value)
    except AppError:
        return value
    if tube.inner > 0.0:
        return f"{tr('Schlauch')} {length(tube.outer, with_unit=False)} × {length(tube.inner)}"
    return f"{tr('Rundkabel')} Ø{length(tube.outer)}"


#: Wie eine Fläche heißt, deren Normale in diese Richtung zeigt. Die Reihenfolge
#: ist die der Achsen; ein Vorzeichen entscheidet zwischen den beiden Namen.
#:
#: Als ``_()``-Literale und nicht als nackte Zeichenketten mit ``tr()``
#: darüber: der Extraktor liest den Quelltext, und ``tr(variable)`` sieht er
#: nicht. Sechs Namen wären stumm ins Englische durchgereicht worden.
_SIDES: tuple[tuple[TranslatableText, TranslatableText], ...] = (
    (_("Rechte Seite"), _("Linke Seite")),
    (_("Rückseite"), _("Vorderseite")),
    (_("Oberseite"), _("Unterseite")),
)

#: Ab wann eine Normale als achsparallel gilt. Darunter ist die Fläche schräg,
#: und ein Seitenname wäre eine Behauptung.
_AXIS_ALIGNED = 0.9


def feature_name(feature_id: FeatureId, feature: Feature) -> str:
    """Wie das Merkmal heißt, wenn man es jemandem zeigt.

    Im Baum stand `face_2` — die Kennung, mit der der Op-Stack rechnet, und
    für einen Menschen eine Nummer ohne Aussage. Eine ebene Fläche weiß, wohin
    sie zeigt, und „Oberseite" ist dieselbe Auskunft in lesbar. Die Kennung
    bleibt: sie steht im Tooltip und in jedem Parameterfeld.
    """
    if feature.kind == "face":
        normal = feature.params.get("normal")
        if isinstance(normal, tuple | list) and len(normal) == 3:
            for axis, (positive, negative) in enumerate(_SIDES):
                value = float(normal[axis])
                if abs(value) >= _AXIS_ALIGNED:
                    return str(positive if value > 0 else negative)
        return tr("Schrägfläche")
    if feature.kind == "hole":
        return f"{tr('Bohrung')} {feature_id.rsplit('_', 1)[-1]}"
    if feature.kind == "cone":
        return tr("Senkung") if feature.params.get("recess") else tr("Verjüngung")
    if feature.kind == "edge_loop":
        return tr("Offene Kante")
    return feature_id


def feature_measure(feature: Feature) -> str:
    """Die eine Zahl, die dieses Merkmal ausmacht — ohne seinen Namen.

    Getrennt vom Namen, weil der Objektbaum zwei Spalten hat: dort stand die
    ganze Beschriftung links und rechts der Typ („hole", „face"). Links war
    damit abgeschnitten, was rechts gefehlt hat.
    """
    params = feature.params
    if feature.kind == "hole":
        return f"Ø{length(float(params.get('diameter', 0.0)))}"
    if feature.kind == "face":
        return area(float(params.get("area", 0.0)))
    if feature.kind == "cone":
        angle = float(params.get("angle", 0.0))
        return f"{angle:.0f}° Ø{length(float(params.get('diameter', 0.0)))}"
    if feature.kind == "edge_loop":
        return f"{params.get('open_edges', 0)} {tr('offene Kanten')}"
    return ""


def feature_label(feature_id: FeatureId, feature: Feature) -> str:
    """``Bohrung 3 · ⌀4,2`` — die Beschriftung, die §18.5 verlangt, Name
    zuerst.

    Für die Stellen, an denen nur eine Zeile Platz hat: Viewport-Beschriftung
    und Statusleiste. Wo zwei Spalten stehen, gehören Name und Maß getrennt.
    """
    measure = feature_measure(feature)
    name = feature_name(feature_id, feature)
    return f"{name} · {measure}" if measure else name


def deadline_date(state: Activation) -> str:
    """Der Stichtag der Demo, wie ihn der Nutzer liest.

    Ein Ort dafür, weil er an fünf Stellen steht: Statusleiste, Über-Dialog,
    Freischaltdialog, Ersteinrichtung und die Meldung, mit der sich eine
    abgelaufene Demo verabschiedet. Fünf Formulierungen desselben Datums
    lesen sich wie fünf verschiedene Fristen.
    """
    return state.deadline.strftime("%d.%m.%Y") if state.deadline is not None else ""


def demo_line(state: Activation) -> str:
    """„Demo — noch 47 Tage, bis zum 30.10.2026".

    Steht dauerhaft in der Statusleiste und nicht erst am vorletzten Tag. Für
    ein Kaufprodukt wäre das Druck (Veröffentlichungskonzept §2 C); für eine
    Demo mit hartem Ende ist es die Zusage, dass niemand überrascht wird —
    wer am 28.10. ein Projekt anfängt, soll es vorher gewusst haben.
    """
    return tr("Demo — noch {days} Tage, bis zum {date}").format(
        days=state.days_left, date=deadline_date(state)
    )
