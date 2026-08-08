"""Kurze Texte, auf die sich mehrere Teile der Oberfläche einigen müssen.

Ein Merkmal wird in der Viewport-Überlagerung, im Objektbaum und in der
Statusleiste gleich geschrieben — ``hole_3 · ⌀4.2``. Ein Ort dafür heißt: der
Name, den der Nutzer liest, ist der Name, den der Agent benutzt (§18.5,
Leitprinzip 5).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor

from app.core.errors import AppError
from app.core.registry import MENU_GROUPS as MENU_GROUPS
from app.core.registry import group_title as group_title
from app.core.types import Feature, FeatureId
from app.core.units import LengthUnit, format_length, format_volume
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


def length(value_mm: float, unit: LengthUnit = "mm", with_unit: bool = True) -> str:
    """Eine Länge, wie die Oberfläche sie schreibt."""
    return localised(format_length(value_mm, unit, with_unit))


def compact_length(value_mm: float, unit: LengthUnit = "mm") -> str:
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
    text = format_length(value_mm, unit, with_unit=False)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return localised(text or "0")


def volume(value_mm3: float, unit: LengthUnit = "mm") -> str:
    """Ein Volumen, wie die Oberfläche es schreibt."""
    return localised(format_volume(value_mm3, unit))


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
_CHOICE_NAMES: dict[str, TranslatableText] = {
    "mouth": _("Mündung"),
    "centre": _("Mitte"),
}


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
        return f"{float(params.get('area', 0.0)):.0f} mm²"
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
