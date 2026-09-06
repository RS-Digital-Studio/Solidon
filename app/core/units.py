"""Zahlen, Einheiten und die drei benannten Toleranzen (Bauplan §11).

Der Kern rechnet in Millimetern und doppelter Genauigkeit, immer. Eine andere
Anzeigeeinheit ist Sache der Oberfläche und erreicht den Kern nie; umgerechnet
wird genau zweimal: beim Import (§17.1) und bei der Anzeige.

Fließkommawerte werden nie mit ``==`` verglichen (AGENTS.md Regel 6) — dafür
gibt es :func:`is_close`, :func:`is_zero`, :func:`is_greater` und
:func:`is_less`.
"""

from __future__ import annotations

import math
from typing import Final, Literal

from app.i18n import TranslatableText, _

# --- Die drei benannten Toleranzen (§11.2) -------------------------------------

#: Zusammenfallende Punkte, Null-Flächen, Verschweißen. Absolut, fürs Fertigen.
EPS_GEOM: Final[float] = 1e-6

#: Rundung für Maße, Steckbrief und Berichte. Absolut, für die Anzeige.
EPS_DISPLAY: Final[float] = 0.01

#: Merkmalsvergleich. Relativ zur Modelldiagonale — siehe :func:`match_tolerance`.
EPS_MATCH_RELATIVE: Final[float] = 0.005

#: Untergrenze der abgeleiteten Vergleichstoleranz, damit winzige Modelle
#: vergleichbar bleiben.
EPS_MATCH_MINIMUM: Final[float] = EPS_DISPLAY

# --- Einheiten -------------------------------------------------------------------

LengthUnit = Literal["mm", "cm", "m", "in"]

#: Skalierungsfaktor nach Millimetern. STL trägt keine Einheit, daher die
#: Heuristik in §17.1.
UNIT_TO_MM: Final[dict[LengthUnit, float]] = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
}

#: Nachkommastellen je Einheit, so gewählt, dass die gezeigte Genauigkeit
#: EPS_DISPLAY entspricht.
_UNIT_DECIMALS: Final[dict[LengthUnit, int]] = {"mm": 2, "cm": 3, "m": 5, "in": 4}

#: Einheiten, die die Oberfläche anbietet (§19.3). Der Kern bleibt bei Millimetern.
DISPLAY_UNITS: Final[tuple[LengthUnit, ...]] = ("mm", "in")

#: Wie eine Einheit heißt, wo sie **allein** steht (§17.1).
#:
#: Neben einer Zahl ist „in" eindeutig; als Antwort auf eine Frage nicht — auf
#: Deutsch ist „in" ein Verhältniswort, und die Einheitenrückfrage bot es als
#: Knopfbeschriftung an. Der Name sagt, was gemeint ist; das Kürzel daneben
#: bleibt für den, der es ohnehin kennt.
#:
#: Nur für Beschriftungen. Der Wert bleibt überall das Kürzel — er steht in der
#: Kennung der Handlung, in den Parametern und in der Projektdatei.
UNIT_NAMES: Final[dict[str, TranslatableText]] = {
    "mm": _("Millimeter (mm)"),
    "cm": _("Zentimeter (cm)"),
    "m": _("Meter (m)"),
    "in": _("Zoll (in)"),
}

#: Die Einheit eines Winkels, in jeder Sprache dieselbe.
#:
#: Sie stand als Zeichenkette in den Registereinträgen, und zwar in zwei
#: Schreibweisen: 26 Parameter trugen ``"grad"``, vier ``"°"``. Im Dialog las
#: sich das als „Winkel [grad]" hier und „Winkel [°]" dort — zwei Schreibweisen
#: derselben Einheit im selben Produkt. „grad" ist obendrein ein roher deutscher
#: Schlüssel, der in keinem Katalog steht und deshalb auch in der englischen
#: Oberfläche so dastand.
#:
#: Als Konstante und nicht als Vereinbarung: Eine Vereinbarung hält, bis jemand
#: den nächsten Winkelparameter schreibt.
DEGREE_UNIT: Final = "°"


def decimals_for(unit: LengthUnit) -> int:
    """Wie viele Nachkommastellen diese Einheit braucht, um EPS_DISPLAY zu zeigen.

    Öffentlich, weil auch die Eingabefelder es wissen müssen: Ein Zahlenfeld in
    Zoll mit zwei Stellen könnte die Toleranz eines Materialprofils nicht
    aufnehmen — ein Hundertstelmillimeter ist ein Vierteltausendstel Zoll. Die
    Anzeige und die Eingabe aus derselben Tabelle, sonst zeigt ein Feld eine
    Stelle, die es nicht annimmt.
    """
    return _UNIT_DECIMALS[unit]


def to_mm(value: float, unit: LengthUnit) -> float:
    """Rechnet eine ankommende Länge in die Kerneinheit um."""
    return value * UNIT_TO_MM[unit]


def from_mm(value_mm: float, unit: LengthUnit) -> float:
    """Rechnet eine Kernlänge in eine Anzeigeeinheit um."""
    return value_mm / UNIT_TO_MM[unit]


# --- Vergleich -------------------------------------------------------------------


def is_close(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    """True, wenn zwei Längen innerhalb von ``eps`` gleich sind."""
    return abs(a - b) <= eps


def is_zero(value: float, eps: float = EPS_GEOM) -> bool:
    return abs(value) <= eps


def is_greater(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    """True, wenn ``a`` um mehr als ``eps`` größer ist als ``b``."""
    return a - b > eps


def is_less(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    return b - a > eps


def clamp(value: float, minimum: float, maximum: float) -> float:
    if minimum > maximum:
        raise ValueError("minimum must not exceed maximum")
    return max(minimum, min(maximum, value))


# --- Abgeleitete Toleranzen ------------------------------------------------------


def match_tolerance(diagonal_mm: float) -> float:
    """``EPS_MATCH`` als absolute Länge für ein Modell dieser Größe (§11.2).

    Relativ fürs Vergleichen, absolut fürs Fertigen — das ist die Faustregel
    hinter den drei Toleranzen.

    **Nicht die Schwelle der Merkmalszuordnung**, obwohl hier lange „die
    Vergleichsschwelle der Merkmalszuordnung (§21.2)" stand. Die Zuordnung
    rechnet in :mod:`app.core.perceive.matching`, und sie fragt diese Funktion
    nicht: Ihre Position kostet ``POSITION_TOLERANCE`` (0,08 der
    Modelldiagonale), daneben stehen eigene Toleranzen für Durchmesser und
    Achse, und angenommen wird unter ``MATCH_THRESHOLD``. Die Zahlen sind
    gemessen und tragen die Suite — auf 0,005 gesetzt, also auf
    :data:`EPS_MATCH_RELATIVE`, fallen zwei Fälle in
    ``tests/test_matching.py`` um, darunter der, an dem zwei gleiche Bohrungen
    mehrdeutig sein müssen.

    Der Satz war deshalb keine Beschreibung, sondern eine Zusage, die niemand
    einlöste — und der nächste, der die Zuordnung nachstellt, hätte hier
    gedreht und nichts bewirkt.
    """
    return max(EPS_MATCH_MINIMUM, abs(diagonal_mm) * EPS_MATCH_RELATIVE)


def weld_tolerance(diagonal_mm: float) -> float:
    """Der Verschweißabstand für Eckpunkte, skaliert mit der
    Modellgröße (§17.1 Schritt 2)."""
    return max(EPS_GEOM, abs(diagonal_mm) * 1e-6)


def weld_digits(tolerance_mm: float) -> int:
    """Dieselbe Toleranz als Zahl von Nachkommastellen.

    Verschweißen läuft über ein Gitter und nicht über Abstände: ``trimesh``
    gruppiert Eckpunkte nach gerundeten Koordinaten, und die Rundungsstelle ist
    das, was dort von einer Toleranz übrig bleibt. Die Umrechnung steht hier
    und nicht zweimal daneben — sie entscheidet, ob zwei Ecken derselbe Ort
    sind, und zwei Antworten auf diese Frage wären zwei Topologien desselben
    Körpers.

    Gedeckelt auf null bis zwölf Stellen: darunter verschmölze ein ganzer
    Millimeter, darüber ist nichts mehr übrig, was ein ``float`` unterscheiden
    könnte.
    """
    return max(0, min(12, round(float(-math.log10(max(tolerance_mm, EPS_GEOM))))))


# --- Anzeige -------------------------------------------------------------------


def quantize(value: float, step: float = EPS_DISPLAY) -> float:
    """Rundet auf ein Vielfaches von ``step``, halbe weg von null.

    Nur für die Anzeige. Gerundete Werte fließen nie in Geometrie
    zurück (§11.2).
    """
    if step <= 0.0:
        raise ValueError("step must be positive")
    rounded = math.floor(abs(value) / step + 0.5) * step
    return math.copysign(rounded, value) if rounded else 0.0


def round_display(value_mm: float) -> float:
    """Rundet einen Millimeterwert auf Anzeigegenauigkeit."""
    return quantize(value_mm, EPS_DISPLAY)


def _significant_decimals(size: float) -> int:
    """Wie viele Nachkommastellen ein kleines Maß braucht, damit zwei geltende
    Ziffern dastehen.

    Volumen und Fläche brauchen dieselbe Antwort, und sie stand bis zum
    24.08.2026 zweimal da — dieselbe Schleife mit denselben Grenzen, einmal für
    Kubikzoll, einmal für Quadratzoll. Bei zwei festen Stellen sähe alles Kleine
    wie null aus: Ein Quadratmillimeter ist ein Anderthalbtausendstel
    Quadratzoll.

    **Der Anlass war Zoll, die Frage ist es nicht.** Ein Kubikmillimeter unter
    eins steht vor demselben Problem, und seit dem 30.08.2026 nimmt
    :func:`format_volume` dieselbe Antwort auch dort — ein erzeugtes Netz kommt
    normiert an und misst Zehntel eines Kubikmillimeters.

    Bei fünf Stellen ist Schluss. Kleinere Nichtnullwerte zeigt die gemeinsame
    Formatierung als Schranke statt als vermeintlich genau gemessene Null.
    """
    decimals = 2
    while decimals < 5 and 0.0 < size < 10.0 ** (1 - decimals):
        decimals += 1
    return decimals


def _format_with_bound(value: float, decimals: int, suffix: str) -> str:
    """Fläche und Volumen behalten unter ihrer letzten Anzeigestelle eine Schranke."""
    smallest = 10.0**-decimals
    if 0.0 < abs(value) < smallest:
        bound = f"{smallest:.{decimals}f}"
        return f"<{bound} {suffix}" if value > 0.0 else f">-{bound} {suffix}"
    return f"{value:.{decimals}f} {suffix}"


def format_volume(value_mm3: float, unit: LengthUnit = "mm") -> str:
    """Ein Volumen in der Einheit, die zur Anzeigelänge passt (§19.3).

    In Millimetern rechnet niemand ein Volumen — Kubikzentimeter sind das
    Maß, in dem Filament verkauft und Verbrauch angegeben wird. Zu Zoll
    gehören Kubikzoll, und der Unterschied ist zu groß, um ihn zu übergehen.

    **Die Einheit folgt der Größe, nicht der Gewohnheit.** Eine Nachkommastelle
    Kubikzentimeter ist unter einem Kubikzentimeter keine Auskunft mehr: Ein
    Teil von 2 mal 2 mal 1 Millimeter stand im Prüfbericht mit „0,0 cm³", und die
    Überschneidungswarnung meldete für einen Streifschuss von einem
    Kubikmillimeter dasselbe wie für zwei Teile, die zur Hälfte ineinander
    stecken — genau den Unterschied, den sie zeigen soll. Unter einem
    Kubikzentimeter stehen deshalb Kubikmillimeter, über tausend fällt die
    Nachkommastelle weg (30 000 cm³ auf ein Zehntel genau behauptet eine
    Messung, die es nicht gibt).

    In Zoll dasselbe Problem und dieselbe Antwort, nur ohne Einheitenwechsel:
    Kubikmillimeter neben Kubikzoll wären zwei Systeme in einer Zeile. Dort
    wachsen stattdessen die Stellen bis zu zwei geltenden Ziffern, höchstens
    jedoch fünf Nachkommastellen. Kleinere Nichtnullwerte stehen als Schranke
    mit ihrem Vorzeichen da, in Millimetern ebenso wie in Zoll.
    """
    if unit == "in":
        cubic_inches = value_mm3 / UNIT_TO_MM["in"] ** 3
        decimals = _significant_decimals(abs(cubic_inches))
        return _format_with_bound(cubic_inches, decimals, "in³")
    if 0.0 < abs(value_mm3) < 1.0:
        # **Und dieselbe Zusage nach unten.** Ganze Kubikmillimeter lösen den
        # Fall von oben („0,0 cm³" für ein Teil von zwei Millimetern) und
        # schaffen einen neuen darunter: Ein Bildmodell normiert seine Ausgabe
        # auf einen Einheitswürfel, und was aus dem Generator kommt, misst ein
        # bis zwei Millimeter. Gemessen an einem echten Wurf: 0,125 mm³, im
        # Erzeugungsdialog als „0 mm³" neben „geschlossen" — zwei Angaben in
        # einer Zeile, die sich widersprechen, denn ein geschlossener Körper
        # ohne Volumen ist keiner.
        #
        # Der Zollzweig darüber löst genau das seit je, und der Test dazu sagt
        # es wörtlich: „was nicht null ist, sieht nicht so aus". Die Zusage
        # galt nur in einer der beiden Einheiten.
        return _format_with_bound(value_mm3, _significant_decimals(abs(value_mm3)), "mm³")
    if abs(value_mm3) < 1000.0:
        return f"{value_mm3:.0f} mm³"
    cubic_centimetres = value_mm3 / 1000.0
    if abs(cubic_centimetres) >= 1000.0:
        return f"{cubic_centimetres:.0f} cm³"
    return f"{cubic_centimetres:.1f} cm³"


def format_area(value_mm2: float, unit: LengthUnit = "mm") -> str:
    """Eine Fläche in der Einheit, die zur Anzeigelänge passt (§19.3).

    Länge und Volumen folgten der Umschaltung seit je, die Fläche nicht: Wer in
    Zoll arbeitete, sah Maße in Zoll, Volumen in Kubikzoll — und daneben
    „4334 mm²". Vier Stellen zeigen Flächen, und alle vier hatten die Einheit
    fest eingebaut.

    Unter einem Quadratmillimeter wachsen die Stellen wie beim Volumen bis
    zu zwei geltenden Ziffern, höchstens jedoch fünf Nachkommastellen. Noch
    kleinere Flächen werden als Schranke gezeigt: Ein vorhandener Überhang
    darf nicht wie eine Fläche von null aussehen. Ab einem Quadratmillimeter
    bleibt es bei ganzen Zahlen. In Zoll wachsen die Stellen entsprechend.
    """
    if unit == "in":
        square_inches = value_mm2 / UNIT_TO_MM["in"] ** 2
        value, suffix = square_inches, "in²"
        decimals = _significant_decimals(abs(value))
    else:
        value, suffix = value_mm2, "mm²"
        decimals = _significant_decimals(abs(value)) if 0.0 < abs(value) < 1.0 else 0
    return _format_with_bound(value, decimals, suffix)


def format_length(value_mm: float, unit: LengthUnit = "mm", with_unit: bool = True) -> str:
    """Formatiert eine Kernlänge für die Anzeige in der gewünschten Einheit.

    Das Dezimaltrennzeichen bleibt hier ein Punkt; lokalisiert wird in der
    Oberfläche, nicht im Kern.
    """
    decimals = _UNIT_DECIMALS[unit]
    converted = from_mm(value_mm, unit)
    text = f"{converted:.{decimals}f}"
    if text.startswith("-") and float(text) == 0.0:
        text = text[1:]
    return f"{text} {unit}" if with_unit else text
