"""Kurze Texte, auf die sich mehrere Teile der Oberfläche einigen müssen.

Ein Merkmal wird in der Viewport-Überlagerung, im Objektbaum und in der
Statusleiste gleich geschrieben — ``hole_3 · ⌀4.2``. Ein Ort dafür heißt: der
Name, den der Nutzer liest, ist der Name, den der Agent benutzt (§18.5,
Leitprinzip 5).
"""

from __future__ import annotations

from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor

from app.core.errors import AppError
from app.core.types import Feature, FeatureId
from app.core.units import LengthUnit, format_length, format_volume
from app.i18n import TranslatableText, _, tr


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

    try:
        tube = standards.tube(value)
    except AppError:
        return value
    if tube.inner > 0.0:
        return f"{tr('Schlauch')} {length(tube.outer, with_unit=False)} × {length(tube.inner)}"
    return f"{tr('Rundkabel')} Ø{length(tube.outer)}"


#: Wie eine Fläche heißt, deren Normale in diese Richtung zeigt. Die Reihenfolge
#: ist die der Achsen; ein Vorzeichen entscheidet zwischen den beiden Namen.
_SIDES: tuple[tuple[str, str], ...] = (
    ("Rechte Seite", "Linke Seite"),
    ("Rückseite", "Vorderseite"),
    ("Oberseite", "Unterseite"),
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
                    return tr(positive if value > 0 else negative)
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
