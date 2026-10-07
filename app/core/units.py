"""Zahlen, Einheiten und die drei benannten Toleranzen (Bauplan §11).

Der Kern rechnet in Millimetern und doppelter Genauigkeit, immer. Eine andere
Anzeigeeinheit ist Sache der Oberfläche und erreicht den Kern nie; umgerechnet
wird genau zweimal: beim Import (§17.1) und bei der Anzeige.

Fließkommawerte werden nie mit ``==`` verglichen (AGENTS.md Regel 6) — dafür
gibt es :func:`is_close`, :func:`is_zero`, :func:`is_greater` und
:func:`is_less`.
"""

from __future__ import annotations

import decimal
import fractions
import functools
import math
from collections.abc import Sequence
from typing import Any, Final, Literal, Protocol

from app.i18n import Figure, TranslatableText, _

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

#: Wann zwei Werte der Druckeinstellungen dasselbe sagen — Regel 6 für
#: Flussverhältnis, Schichthöhe, Füllanteil und alles, was der Druckdialog
#: führt. Sechs Stellen liegen unter jeder Anzeige (höchstens drei
#: Nachkommastellen) und über dem Rauschen, das beim Hin- und Herrechnen
#: durch den Umrechnungsfaktor eines Feldes entsteht. Dieselbe Zahl wie
#: :data:`EPS_GEOM`, aber eine andere Frage: Die eine ist eine Länge, die
#: andere eine Einstellung jeder Einheit.
EPS_SETTING: Final[float] = 1e-6

# --- Wie fein eine Krümmung zu Facetten wird -------------------------------------

#: Wie weit eine ebene Facette von der Rundung abweichen darf, die sie ersetzt.
#:
#: Keine Toleranz im Sinne von §11.2 — es wird nichts daran gemessen —, sondern
#: eine Auflösung: fein genug, dass eine Verrundung auf dem Bildschirm und im
#: Druck rund aussieht, grob genug, dass eine STEP-Baugruppe nicht als Million
#: Dreiecke ankommt (§31).
#:
#: **Sie steht hier, weil beide Rechenkerne sie brauchen.** OpenCASCADE
#: tesselliert damit (`brep.kernel.DEFLECTION`), und am Netz entscheidet sie,
#: aus wie vielen Sehnen ein Verrundungsbogen besteht. Zwei Zahlen mit
#: demselben Wert wären zwei Stellen, an denen die Kerne auseinanderlaufen —
#: und genau davor steht die Zusage, dass beide dieselbe Kante gleich nennen.
MAX_FACET_SAG: Final[float] = 0.05

#: Wie viele Körper eine eingelesene Baugruppe höchstens trägt — dieselbe Zahl
#: wie ``scene.project.MAX_PROJECT_OBJECTS``: Jeder Körper wird ein Objekt im
#: Stapel, und mehr ließe sich nie speichern. 3MF (``ingest.threemf``) und STEP
#: (``brep.step``) lesen sie von hier; zwei Zahlen wären zwei Stellen, an denen
#: die Formate auseinanderlaufen.
ASSEMBLY_BODIES: Final[int] = 10_000

#: Wie tief Baugruppen ineinander stecken dürfen, bevor das Einlesen anhält —
#: für 3MF und STEP dieselbe Grenze. Was eine vervielfachende Datei wirklich
#: stoppt, ist die Körpergrenze darüber; diese hält die Tiefe davor.
ASSEMBLY_DEPTH: Final[int] = 32

#: Wie weit vom Ursprung ein **gemessener Ort** liegen darf, in Millimetern
#: und je Achse — die Grenze der Ortsfelder an erkannten Merkmalen (*Merkmal
#: verschieben*, *Bohrung ändern*, *Zum Langloch ziehen* …). Ein Ort sagt nichts
#: über die Druckbarkeit; er hängt daran, wo der Körper liegt. Mit ±1000 mm
#: lehnte das Merkmalfenster an einem Körper über einen Meter den eigenen
#: Messwert ab, und *Bohrung ändern* ließ sich nicht übernehmen, ohne die
#: Bohrung zu versetzen. Hundert Meter sind die Grenze, die das Merkmalfenster
#: einem Feld ohne eigene gibt.
FEATURE_REACH: Final[float] = 100_000.0

#: Und die zweite Grenze daneben, im Bogenmaß: Wie weit eine Facette drehen
#: darf, auch wenn sie die Abweichung darüber einhält.
#:
#: Ohne sie bekäme ein kleiner Radius zu wenige Stücke — bei R = 1 mm reichten
#: drei Sehnen auf einen Viertelkreis, um die Abweichung zu halten, und das
#: sieht man.
MAX_FACET_ANGLE: Final[float] = 0.3

#: Wie weit die Normale einer Nachbarfläche aus der Senkrechten zur Achse einer
#: Rundung kippen darf und noch als die Fläche gilt, zwischen denen sie liegt.
#: Deckel und Boden einer Rundung an einer senkrechten Kante liegen entlang der
#: Achse und sind nicht gemeint. Erkennung (``perceive.features``) und
#: Bearbeitung (``geom.edges``) lesen dieselbe Zahl — bis zum 15.09.2026 stand
#: sie allein bei der Bearbeitung, und die Erkennung nannte Kante, was jene
#: nicht als Kante zurückrechnen konnte.
UPRIGHT_TO_AXIS: Final[float] = 0.1

#: Wie genau eine Ebene einen Bogen **tangential** fortsetzen muss, damit sie als
#: eine seiner beiden Kantenflächen gilt: Am gemeinsamen Rand darf die radiale
#: Richtung des Bogens höchstens rund 26° von der Normalen der Ebene abweichen
#: (Skalarprodukt ≥ 0,9). Grob genug für den Sehnenzug eines fremden Netzes,
#: dessen letzte Facette bis zu ``MAX_FACET_ANGLE`` schräg steht, und eng
#: genug für zwei Ebenen, die einen Bogen im spitzen Winkel schneiden (die
#: Gleise einer Modellscheune, 15.09.2026). Eine eigene Zahl, nicht
#: ``UPRIGHT_TO_AXIS``: Die misst eine Normale gegen die Achse, dies misst sie
#: gegen den Radius.
TANGENT_TO_THE_ARC: Final[float] = 0.9

#: Wann zwei Dreiecke an einer Ecke **dieselbe** Ebene tragen: ihre Normalen
#: weichen um höchstens ``1 - Skalarprodukt`` so viel voneinander ab, rund
#: 0,8°. Die Formschräge am Netz (P6.4) setzt jede Ecke einer gewählten Fläche
#: neu in den Schnitt ihrer Ebenen; dafür muss sie die Ebenen an der Ecke
#: zählen. Eng genug für die Facetten eines Zylinders mit 48 Teilen (7,5°
#: auseinander), weit genug für das Rauschen einer STL mit vier Byte je Zahl.
SAME_PLANE_AT_A_CORNER: Final[float] = 1e-4

#: Wie weit eine Ecke beim Anstellen höchstens entlang ihrer Nachbarflächen
#: wandern darf, als Vielfaches des Wegs ihrer eigenen Fläche. Mehr heißt: Die
#: Nachbarfläche läuft fast parallel zur gewählten (unter 5,7°, etwa der
#: Anfang einer Rundung), und der neue Schnittpunkt ist keine Kante mehr,
#: sondern eine Frage der Rundung (P6.4).
GRAZING_SLIDE: Final[float] = 10.0

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
        return Figure(f"<{bound} {suffix}" if value > 0.0 else f">-{bound} {suffix}")
    return Figure(f"{value:.{decimals}f} {suffix}")


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
    return Figure(f"{cubic_centimetres:.1f} cm³")


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
    Oberfläche, nicht im Kern. Als :class:`~app.i18n.Figure` markiert,
    schreibt sich die Zahl in einem Satz des Kerns mit dem Zeichen der
    Anzeigesprache (Fensterabnahme 04.10.2026).
    """
    decimals = _UNIT_DECIMALS[unit]
    converted = from_mm(value_mm, unit)
    text = f"{converted:.{decimals}f}"
    if text.startswith("-") and float(text) == 0.0:
        text = text[1:]
    return Figure(f"{text} {unit}" if with_unit else text)


def format_length_bound(value_mm: float, unit: LengthUnit = "mm", *, upper: bool) -> str:
    """Eine Längenschranke bei Einheitenwechsel und Anzeige nach außen runden.

    Die Umrechnung rechnet dezimal gerichtet, damit bereits vor der letzten
    Anzeigestelle keine obere Schranke nach unten wandert. Kleine Nichtnullwerte
    behalten zwei geltende Ziffern — auch unter fünf Nachkommastellen als
    Dezimalzahl („0,00000012 mm"), nicht als Exponent: Ein Kunde liest
    Millimeter, keine Zehnerpotenzen. Das ist ausschließlich Anzeigepräzision,
    keine geometrische Toleranz.
    """
    if not math.isfinite(value_mm):
        raise ValueError("Eine Längenschranke muss endlich sein.")
    value = decimal.Decimal(float(value_mm))
    rounding = decimal.ROUND_CEILING if upper else decimal.ROUND_FLOOR
    with decimal.localcontext() as context:
        context.prec = max(34, value.adjusted() + 10)
        context.rounding = rounding
        converted = value / decimal.Decimal(str(UNIT_TO_MM[unit]))
        exponent = converted.adjusted()
        tiny = not converted.is_zero() and exponent < -5
        places = max(_UNIT_DECIMALS[unit], min(5, 1 - exponent))
        quantum = decimal.Decimal(1).scaleb(exponent - 1 if tiny else -places)
        rounded = converted.quantize(quantum)
        if rounded.is_zero():
            rounded = rounded.copy_abs()
        text = format(rounded, "f")
    return Figure(f"{text} {unit}")


#: Unter welcher Länge ein Kreuzprodukt als parallel gilt — dieselbe Zahl,
#: mit der ``sketch.planes`` seit je rechnet.
PLANE_PARALLEL: Final[float] = 1e-9

#: Wie weit zwei Volumen desselben Körpers auseinanderliegen dürfen, wenn nur
#: die Vernetzung eine andere ist: um das Rauschen der Summe, als Anteil des
#: Volumens. **Eine Rechengrenze, keine Geometrietoleranz** — deshalb steht
#: hier eine Zahl und kein Verweis ins Materialprofil. Eine Volumensumme über
#: hunderttausend Dreiecke ist auf ihre letzten Stellen nicht verlässlich; ein
#: Kern, der mehr als das verlöre, hätte Form verloren. Gemessen an der
#: viermal unterteilten Lochplatte: 0,0 mm³ von 31 322.
VOLUME_SUM_NOISE: Final[float] = 1e-9


def plane_axes(
    normal: Sequence[float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """Die zwei Achsen in einer Ebene zu ihrer Normalen — die Wahl von ``frame_of``.

    Die erste Achse ist das Kreuzprodukt aus Z und der Normalen, außer die
    Normale zeigt selbst nach Z — dann ist sie X. So wird die waagerechte
    Fläche zur globalen XY-Ebene, und dieselbe Skizze liegt auf Tisch und
    Deckel gleich herum. ``sketch.planes.frame_of`` baut seinen Rahmen
    daraus, ``perceive.patterns`` liest die Feldlage eines Musters darin —
    zwei Leser, eine Regel, und die Wahrnehmung importiert keine Skizze.
    ``None``, wenn die Normale keine Länge hat.
    """
    length = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if length < PLANE_PARALLEL:
        return None
    unit = (normal[0] / length, normal[1] / length, normal[2] / length)
    x_axis = (-unit[1], unit[0], 0.0)  # Kreuzprodukt Z mit n
    reach = math.sqrt(x_axis[0] ** 2 + x_axis[1] ** 2)
    if reach < PLANE_PARALLEL:
        x_axis = (unit[2], 0.0, -unit[0])  # Kreuzprodukt Y mit n
        reach = math.sqrt(x_axis[0] ** 2 + x_axis[2] ** 2)
    x_axis = (x_axis[0] / reach, x_axis[1] / reach, x_axis[2] / reach)
    y_axis = (
        unit[1] * x_axis[2] - unit[2] * x_axis[1],
        unit[2] * x_axis[0] - unit[0] * x_axis[2],
        unit[0] * x_axis[1] - unit[1] * x_axis[0],
    )
    span = math.sqrt(y_axis[0] ** 2 + y_axis[1] ** 2 + y_axis[2] ** 2)
    return x_axis, (y_axis[0] / span, y_axis[1] / span, y_axis[2] / span)


def positive_axis(axis: Sequence[float]) -> tuple[float, float, float]:
    """Eine gemessene Achse mit festem Vorzeichen: erste größte Betragskomponente positiv.

    Eine Achse hat von sich aus keines — ein Eigenvektor und sein Gegenvektor
    beschreiben dieselbe Gerade, und die Zylinderfläche eines exakten Körpers
    trägt das Vorzeichen, das ihr Erzeuger ihr gab. Für alles, was daran
    hängt, muss es **eines** sein: ``sketch.planes.frame_of`` spiegelt seine
    erste Achse mit der Normalen, und gegen diesen Rahmen zählen der Winkel
    eines Langlochs (``prepare.slot_profile``, ``prepare_ops.slot_angle_of``)
    und der Griff im Bild.

    **Beide Kerne rufen hier** — ``perceive.features.fit_cylinder`` am Netz,
    ``brep.features`` am exakten Körper —, und der Anlass ist gemessen
    (11.09.2026): Der exakte Kern gab die Achse so zurück, wie die Fläche sie
    trug. Nach *Zum Langloch ziehen* mit 45 Grad stand sie auf **minus** Z,
    das Feld *Richtung* zeigte minus 45, und wer dieselbe 45 noch einmal
    eintrug, bekam ein Kreuz statt eines längeren Langlochs. Eine Bohrung von
    unten trug am Netz plus Z und am exakten Körper minus Z — derselbe Winkel
    lag an den zwei Kernen gespiegelt.

    Nahezu gleiche Komponenten entscheiden nicht über Rundungsreste: Gewählt
    wird die **erste**, die das Maximum bis auf :data:`EPS_GEOM` erreicht.
    Eine negative Null kommt nicht zurück — sie schriebe sich als ``-0.000``
    und trennte zwei Schlüssel, die dieselbe Achse meinen. **Auch dann nicht,
    wenn gar nicht gespiegelt wird:** Die Zusage stand bis zum 13.09.2026 nur
    im gespiegelten Zweig, und ``positive_axis((1.0, -0.0, 0.0))`` gab die
    negative Null unverändert zurück. Eine halbe Zusage sieht aus wie eine
    ganze — und ``json.dumps`` schreibt ``-0.0`` neben ``0.0``, wo der
    Vergleich beide gleich nennt.
    """
    values = (float(axis[0]), float(axis[1]), float(axis[2]))
    largest = max(abs(value) for value in values)
    leading = next(index for index, value in enumerate(values) if abs(value) >= largest - EPS_GEOM)
    sign = -1.0 if values[leading] < 0.0 else 1.0
    # ``+ 0.0`` streicht die negative Null, ohne eine andere Zahl zu ändern.
    return (sign * values[0] + 0.0, sign * values[1] + 0.0, sign * values[2] + 0.0)


# --- Winkelfunktionen, die auf jeder Maschine dieselbe Zahl geben -----------------

#: Pi als feste Ziffernfolge, weit über :data:`EXACT_DIGITS`.
#:
#: Keine Reihe: Pi ändert sich nicht, und eine Konstante kann nicht
#: plattformweise streuen — worum es hier ja gerade geht. ``math.pi`` wäre der
#: nächstliegende Weg und der falsche: Es ist ein ``float`` und trägt nur
#: sechzehn Stellen, die Reihen bekämen also einen abgeschnittenen Winkel.
_PI: Final = decimal.Decimal(
    "3.14159265358979323846264338327950288419716939937510582097494459230781640628620899862803"
)

#: Stellen, mit denen die Reihen rechnen, bevor auf ``float`` gerundet wird.
#:
#: Fünfzig sind reichlich mehr als die sechzehn, die ein ``float`` trägt. Der
#: Abstand ist Absicht: Er macht die Rundung auf die letzte Stelle eindeutig,
#: und eindeutig ist hier das ganze Ziel.
EXACT_DIGITS: Final = 50

#: Wie viele verschiedene Winkel gemerkt werden.
#:
#: Die Reihe kostet rund ein Zehntel einer Millisekunde; ein Bauteil fragt
#: dieselben Winkel immer wieder. Begrenzt, weil ein unbegrenzter Speicher über
#: eine lange Sitzung wächst, ohne dass jemand ihn je leert.
ANGLE_CACHE: Final = 8192


def circle_point(sections: int, index: int) -> tuple[float, float]:
    """Kosinus und Sinus an der ``index``-ten Ecke eines regelmäßigen ``sections``-Ecks.

    **Warum es diese Funktion gibt** (17.09.2026, RM-187): ``np.cos`` und
    ``math.cos`` geben auf verschiedenen Rechnern verschiedene Zahlen. Gemessen
    über drei Runner mit demselben Python und demselben NumPy — Ubuntu rechnet
    mit AVX-512, Windows mit AVX2, macOS mit NEON, und die drei runden die
    letzte Stelle verschieden. Der Unterschied ist winzig (3,4·10⁻¹⁵ mm) und
    bleibt es nicht: Durch eine Boolesche Operation wächst er zu einem anderen
    Netz. Derselbe Körper trug 1226 Dreiecke auf Windows, 1224 auf Ubuntu und
    1228 auf macOS, und eine Bohrungskette, die Solidon auf zwei Plattformen
    erkennt, war auf der dritten nicht mehr da.

    **Ein exakter Boolescher Kern hätte das nicht geheilt.** Geogram und
    trueform rechnen exakt *mit* ihrer Eingabe; zwei verschiedene Eingaben
    geben zwei verschiedene Ergebnisse, auch exakt gerechnet. Die Ursache liegt
    davor, und deshalb liegt die Lösung hier.

    Gerechnet wird über ``decimal`` — reine Ganzzahlarithmetik, die von der
    Maschine nichts wissen will. Der Winkel entsteht dabei aus **Ganzzahlen**
    (``index`` und ``sections``) und nicht aus einem vorher gerundeten
    ``float``: Schon ``index * tau / sections`` wäre eine Fließkommadivision
    und brächte die Plattform wieder ins Spiel.

    Die Ecke ``0`` liegt auf ``(1, 0)``, und der Umlauf ist mathematisch
    positiv — dieselbe Belegung wie ``cos``/``sin`` sie hätten.
    """
    if sections < 3:
        raise ValueError(f"Ein Kreis braucht mindestens drei Ecken, nicht {sections}")
    return _circle_table(int(sections))[int(index) % int(sections)]


def circle_cos_sin(sections: int) -> tuple[tuple[float, float], ...]:
    """Alle ``sections`` Eckenpaare auf einmal — dieselbe Zahlenfolge wie einzeln."""
    if sections < 3:
        raise ValueError(f"Ein Kreis braucht mindestens drei Ecken, nicht {sections}")
    return _circle_table(int(sections))


def exact_cos(angle: float) -> float:
    """Kosinus, auf jeder Maschine dieselbe Zahl. Siehe :func:`circle_point`.

    Für eine regelmäßige Teilung ist :func:`circle_point` der genauere Weg:
    Dort entsteht der Winkel aus Ganzzahlen, hier ist er schon ein ``float``
    und trägt, was seine Herkunft ihm angetan hat.
    """
    return _exact_pair(float(angle))[0]


def exact_sin(angle: float) -> float:
    """Sinus, auf jeder Maschine dieselbe Zahl. Siehe :func:`exact_cos`."""
    return _exact_pair(float(angle))[1]


@functools.lru_cache(maxsize=ANGLE_CACHE)
def _exact_pair(angle: float) -> tuple[float, float]:
    """Kosinus und Sinus zu einem ``float``-Winkel, über die Reihen gerechnet."""
    with decimal.localcontext() as context:
        context.prec = EXACT_DIGITS
        reduced = _reduced(decimal.Decimal(angle))
        return (float(_cos_series(reduced)), float(_sin_series(reduced)))


@functools.lru_cache(maxsize=256)
def _circle_table(sections: int) -> tuple[tuple[float, float], ...]:
    """Die Tabelle eines regelmäßigen ``sections``-Ecks, einmal je Prozess.

    Jede Ecke geht über :func:`_turn_cos_sin` — als **Bruch eines Umlaufs**
    aus zwei Ganzzahlen, auf eine Achteldrehung zurückgeführt. Vorzeichen,
    Tausch und Ergänzung sind in Fließkomma exakt; damit steht die Symmetrie,
    die ein Kreis haben soll, auch bei ``sections``, die nicht durch vier
    teilbar sind. Dort rechnete bis zum 22.09.2026 jede Ecke ihre eigene
    Reihe, und der halbe Umlauf eines Sechsecks lag bei ``y = -7·10⁻⁵⁰``
    statt auf der Achse.
    """
    return tuple(_turn_cos_sin(fractions.Fraction(index, sections)) for index in range(sections))


def _turn_cos_sin(turn: fractions.Fraction) -> tuple[float, float]:
    """Kosinus und Sinus zu einem exakten Bruchteil eines Umlaufs.

    **Erst exakt reduzieren, dann rechnen.** Der Bruch wird auf ``[0, 1)``
    gebracht, in Viertel und Rest zerlegt, und ein Rest über einer
    Achteldrehung geht über seine Ergänzung. Die Reihe sieht damit nur
    Winkel zwischen null und 45 Grad; ein Vielfaches von 90 Grad ist ein
    Rest von **null** und gibt exakt ``(±1, 0)`` oder ``(0, ±1)``. Vorher lief
    die Reihe über den ungekürzten Winkel und traf die Null an einem rechten
    Winkel nur bis auf die fünfzig Stellen, mit denen sie rechnet:
    ``cos(90°)`` war ``-8,5·10⁻⁵⁰`` und ``sin(360°)`` ``-2·10⁻⁴⁹`` — auf jeder
    Maschine gleich, aber nicht null, und eine Ecke auf der Achse lag nach
    einer Vierteldrehung um diesen Rest daneben (Review, 22.09.2026).

    Vorzeichenwechsel und Tausch ändern kein Bit der Mantisse; ``+ 0.0``
    streicht die negative Null (dieselbe Falle, die :func:`positive_axis`
    schon einmal gestellt hat).
    """
    fraction = turn % 1
    quadrant, rest = divmod(fraction * 4, 1)
    # ``rest`` ist der Anteil einer Vierteldrehung, also in [0, 1).
    complement = rest > fractions.Fraction(1, 2)
    if complement:
        rest = 1 - rest
    with decimal.localcontext() as context:
        context.prec = EXACT_DIGITS
        angle = (
            decimal.Decimal(rest.numerator) / decimal.Decimal(rest.denominator) * _PI / 2
            if rest
            else decimal.Decimal(0)
        )
        cos, sin = float(_cos_series(angle)), float(_sin_series(angle))
    if complement:
        cos, sin = sin, cos
    turned = ((cos, sin), (-sin, cos), (-cos, -sin), (sin, -cos))[int(quadrant)]
    return (turned[0] + 0.0, turned[1] + 0.0)


def _reduced(angle: decimal.Decimal) -> decimal.Decimal:
    """Den Winkel in ``[-π, π]`` holen — die Reihen konvergieren dort am besten."""
    turn = 2 * _PI
    angle = angle.remainder_near(turn)
    if angle > _PI:
        angle -= turn
    elif angle < -_PI:
        angle += turn
    return +angle


def _cos_series(angle: decimal.Decimal) -> decimal.Decimal:
    """Kosinus über die Taylorreihe, abgebrochen wenn ein Term nichts mehr ändert."""
    index, factorial, power, sign, total = (
        0,
        decimal.Decimal(1),
        decimal.Decimal(1),
        1,
        decimal.Decimal(1),
    )
    square = angle * angle
    while True:
        index += 2
        factorial *= index * (index - 1)
        power *= square
        sign = -sign
        term = sign * power / factorial
        if total + term == total:
            return +total
        total += term


def _sin_series(angle: decimal.Decimal) -> decimal.Decimal:
    """Sinus über die Taylorreihe, gleiche Bauart wie :func:`_cos_series`."""
    index, factorial, power, sign, total = (
        1,
        decimal.Decimal(1),
        decimal.Decimal(angle),
        1,
        decimal.Decimal(angle),
    )
    square = angle * angle
    while True:
        index += 2
        factorial *= index * (index - 1)
        power *= square
        sign = -sign
        term = sign * power / factorial
        if total + term == total:
            return +total
        total += term


def inscribed_ratio(sections: int) -> float:
    """``cos(π/n)`` — In- zu Umkreis eines regelmäßigen ``sections``-Ecks.

    Der Faktor, mit dem ein eingeschriebenes Vieleck aufgeweitet wird, damit es
    den gemeinten Kreis wirklich umschließt: ``trimesh`` baut seine Zylinder
    eingeschrieben, ihre Facetten liegen also **innerhalb** des Radius, und wer
    ein Loch von Ø 6 schneiden will, braucht ein Werkzeug, das bis Ø 6 reicht.

    **Nicht ``math.cos(math.pi / sections)``**, obwohl das dasselbe meint:
    ``math.pi / sections`` ist eine Fließkommadivision und ``math.cos`` eine
    Bibliotheksfunktion, und beide bringen die Plattform wieder ins Spiel
    (RM-187). Hier steht dieselbe Zahl als Ecke eines ``2·sections``-Ecks —
    aus Ganzzahlen gerechnet, denn ``cos(2π/(2n))`` *ist* ``cos(π/n)``.
    """
    return circle_point(2 * int(sections), 1)[0]


def exact_cos_degrees(degrees: float) -> float:
    """Kosinus eines Winkels in Grad, auf jeder Maschine dieselbe Zahl.

    **Nicht ``exact_cos(math.radians(degrees))``:** Das Umrechnen rundet, und
    der gerundete Winkel geht in die Reihe. Hier bleibt die Umrechnung
    innerhalb der genauen Arithmetik, und erst das Ergebnis wird ``float``.

    Ein Vielfaches von 90 Grad gibt exakt ``0`` oder ``±1`` — ein ``float`` in
    Grad ist ein exakter Bruch, und :func:`_turn_cos_sin` reduziert ihn, bevor
    die Reihe rechnet. Eine halbe Drehung um eine Achse lässt deshalb jede
    Koordinate auf ihr, wo sie war.
    """
    return _exact_degrees(float(degrees))[0]


def exact_sin_degrees(degrees: float) -> float:
    """Sinus eines Winkels in Grad. Siehe :func:`exact_cos_degrees`."""
    return _exact_degrees(float(degrees))[1]


def exact_tan_degrees(degrees: float) -> float:
    """Tangens eines Winkels in Grad, als Quotient aus :func:`exact_sin_degrees`
    und :func:`exact_cos_degrees` — der Ersatz für ``math.tan(math.radians(…))``,
    dessen letzte Stelle an der Plattform hängt (RM-187). Bei 90 Grad ist der
    Kosinus genau null und die Division ein Fehler, wie die Sache es ist.
    """
    return exact_sin_degrees(degrees) / exact_cos_degrees(degrees)


def exact_atan_degrees(ratio: float) -> float:
    """Arkustangens in Grad, auf jeder Maschine dieselbe Zahl.

    Für Winkel, die entscheiden (RM-187): ``math.atan`` ist eine
    Bibliotheksfunktion, und ihre letzte Stelle hängt an der Plattform. Hier
    rechnet die Reihe in genauer Arithmetik wie bei :func:`exact_cos`, und erst
    das Ergebnis wird ``float``. Anlass ist PrusaSlicers automatische
    Stützschwelle, ein Arkustangens aus Außenwand und Schichthöhe, mit dem die
    Schichtanalyse über Überhänge entscheidet.
    """
    if not math.isfinite(ratio):
        raise ValueError(f"Ein Verhältnis muss endlich sein, nicht {ratio}")
    return _exact_atan_degrees(float(ratio))


def exact_atan2_degrees(y: float, x: float) -> float:
    """Der Winkel des Punkts ``(x, y)`` gegen die x-Achse, in Grad in ``(-180, 180]``.

    Der Arkustangens aus :func:`exact_atan_degrees`, immer über das Verhältnis
    der kleineren zur größeren Koordinate (höchstens eins, also kein Überlauf),
    der Rest aus Grundrechenarten — plattformgleich wie der Arkustangens
    selbst, anders als ``math.atan2``. Der Ursprung hat keine Richtung und
    bekommt null.
    """
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError(f"Ein Punkt muss endlich sein, nicht ({x}, {y})")
    if abs(x) >= abs(y):
        if x == 0.0:
            return 0.0
        base = exact_atan_degrees(y / x)
        if x > 0.0:
            return base
        return base + (180.0 if y >= 0.0 else -180.0)
    base = exact_atan_degrees(x / y)
    return 90.0 - base if y > 0.0 else -90.0 - base


def exact_acos_degrees(cosine: float) -> float:
    """Arkuskosinus in Grad, auf jeder Maschine dieselbe Zahl (RM-187).

    Als ``atan2(√((1 - c)(1 + c)), c)`` über :func:`exact_atan2_degrees`; die
    Wurzel aus dem Produkt löscht an den Rändern nicht aus. Ein Kosinus
    außerhalb von ``[-1, 1]`` — Rundung eines Skalarprodukts von Einheitsvektoren —
    wird auf den Rand gelegt, wie ``min(1.0, …)`` vor ``math.acos`` es tat.
    """
    value = min(1.0, max(-1.0, float(cosine)))
    return exact_atan2_degrees(math.sqrt((1.0 - value) * (1.0 + value)), value)


def exact_atan2(y: float, x: float) -> float:
    """:func:`exact_atan2_degrees` im Bogenmaß — der Ersatz für ``math.atan2`` (RM-187).

    ``math.radians`` ist ein Produkt mit ``π/180`` und damit auf jeder
    Maschine gleich gerundet. Der Arkussinus und der Arkuskosinus folgen
    daraus: ``asin x = atan2(x, √((1 - x)(1 + x)))``, ``acos x`` mit den
    Argumenten getauscht.
    """
    return math.radians(exact_atan2_degrees(y, x))


@functools.lru_cache(maxsize=ANGLE_CACHE)
def _exact_atan_degrees(ratio: float) -> float:
    """Der Arkustangens über die Reihe, nach Rückführung auf ein kleines Argument.

    Über eins gilt die Ergänzung ``π/2 - atan(1/x)``; darunter halbiert
    ``atan x = 2·atan(x / (1 + √(1 + x²)))`` das Argument, bis die Reihe nach
    wenigen Gliedern endet. ``Decimal.sqrt`` rundet korrekt und ist damit so
    plattformgleich wie die Grundrechenarten.
    """
    with decimal.localcontext() as context:
        context.prec = EXACT_DIGITS
        value = decimal.Decimal(ratio)
        negative = value < 0
        value = abs(value)
        complement = value > 1
        if complement:
            value = 1 / value
        halvings = 0
        limit = decimal.Decimal("0.1")
        while value > limit:
            value = value / (1 + (1 + value * value).sqrt())
            halvings += 1
        angle = _atan_series(value) * (2**halvings)
        if complement:
            angle = _PI / 2 - angle
        if negative:
            angle = -angle
        return float(angle * 180 / _PI) + 0.0


def _atan_series(value: decimal.Decimal) -> decimal.Decimal:
    """Arkustangens über ``x - x³/3 + x⁵/5 - …``, abgebrochen wie :func:`_cos_series`."""
    index, power, sign, total = 1, value, 1, value
    square = value * value
    while True:
        index += 2
        power *= square
        sign = -sign
        term = sign * power / index
        if total + term == total:
            return +total
        total += term


@functools.lru_cache(maxsize=ANGLE_CACHE)
def _exact_degrees(degrees: float) -> tuple[float, float]:
    """Kosinus und Sinus zu einem Gradwinkel, ohne vorher zu runden."""
    if not math.isfinite(degrees):
        # Wie ``math.cos``: Ein unendlicher Winkel hat keinen Kosinus.
        raise ValueError(f"Ein Winkel muss endlich sein, nicht {degrees}")
    return _turn_cos_sin(fractions.Fraction(degrees) / 360)


def exact_mean(values: Sequence[float]) -> float:
    """Der Mittelwert einer Zahlenreihe, auf jeder Maschine dieselbe Zahl.

    **Warum nicht ``np.mean``** (17.09.2026, RM-187): NumPy summiert
    vektorisiert und in Teilsummen, und wie viele Teilsummen es sind, hängt
    von der SIMD-Breite der CPU ab. Fließkommaaddition ist nicht assoziativ —
    eine andere Gruppierung gibt ein anderes letztes Bit. Auf x86 und ARM kam
    dabei ein anderer Wert heraus, und weil dieser Wert als **Eckpunkt** in ein
    Netz geschrieben wurde, war das Bauteil danach ein anderes.

    ``math.fsum`` summiert exakt (nach Shewchuk) und rundet erst am Ende
    einmal. Das Ergebnis hängt damit weder von der Reihenfolge noch von der
    Maschine ab — und es ist obendrein genauer als jede Teilsummenvariante.

    Für Punkte im Raum wird je Achse gerufen; ``exact_centre`` tut das.
    """
    series = list(values)
    if not series:
        raise ValueError("Der Mittelwert einer leeren Reihe ist nicht bestimmt")
    return math.fsum(series) / len(series)


def exact_centre(points: Sequence[Sequence[float]]) -> tuple[float, float, float]:
    """Der Schwerpunkt einer Punktwolke im Raum — siehe :func:`exact_mean`.

    Nimmt alles, was sich zeilenweise in drei Zahlen zerlegen lässt, auch ein
    NumPy-Feld. Zurück kommen einfache ``float``, damit der Aufrufer sie ohne
    Umweg in ein Feld schreiben kann.
    """
    rows = [tuple(float(value) for value in point) for point in points]
    if not rows:
        raise ValueError("Der Schwerpunkt einer leeren Punktwolke ist nicht bestimmt")
    return (
        exact_mean([row[0] for row in rows]),
        exact_mean([row[1] for row in rows]),
        exact_mean([row[2] for row in rows]),
    )


class Indexable3(Protocol):
    """Was drei Komponenten über ``[0]``, ``[1]``, ``[2]`` hergibt — Tupel,
    Liste oder NumPy-Feld."""

    def __getitem__(self, index: int, /) -> Any: ...


def dot3(first: Indexable3, second: Indexable3) -> float:
    """Das Skalarprodukt zweier Raumvektoren — auf jeder Maschine dieselbe Zahl.

    **Nicht ``np.dot`` und nicht ``a @ b``:** Beide gehen durch BLAS, und
    dessen Kern wählt seine Reihenfolge und seine FMA-Nutzung nach der CPU —
    auf dem Mac ist es Apples Accelerate, auf Windows und Linux OpenBLAS mit
    je eigenem Kern. Drei Produkte, von links nach rechts summiert, in
    Pythons ``float``: Jede Operation ist einzeln nach IEEE-754 gerundet, und
    kein Compiler zieht sie zusammen (RM-187).
    """
    return (
        float(first[0]) * float(second[0])
        + float(first[1]) * float(second[1])
        + float(first[2]) * float(second[2])
    )


#: Wie viele Jacobi-Durchgänge :func:`symmetric_eigen3` höchstens macht. Eine
#: symmetrische 3x3-Matrix ist nach fünf bis sechs Durchgängen diagonal bis auf
#: die letzte Stelle; die Grenze fängt nur, was nie konvergiert (``nan``).
JACOBI_SWEEPS: Final = 64


def symmetric_eigen3(
    matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, float, float], tuple[tuple[float, float, float], ...]]:
    """Eigenwerte und Eigenvektoren einer symmetrischen 3x3-Matrix — ohne LAPACK.

    Zurück kommen die Eigenwerte **aufsteigend** und je Eigenwert sein
    Einheitsvektor, in derselben Reihenfolge.

    **Warum nicht ``np.linalg.eigh`` oder ``svd``** (22.09.2026, RM-187):
    LAPACK ist die plattformabhängigste Bibliothek im Stapel — Accelerate
    auf dem Mac, OpenBLAS mit eigenem Kern je CPU auf Windows und Linux, und
    beide dürfen einen Eigenvektor mit dem anderen Vorzeichen liefern. Gemessen
    an der Senkbohrung des Änderungswegs: Die Ebene einer schrägen Mündung kam
    aus einer SVD, und ihre letzte Stelle entschied über jede Ecke des
    Werkzeugs; ein ULP daneben, und das geänderte Netz trug einen anderen
    Fingerabdruck.

    Das zyklische Jacobi-Verfahren braucht nur Grundrechenarten und
    ``math.sqrt``, und beides ist nach IEEE-754 korrekt gerundet — auf jeder
    Maschine dieselben Bits. Es ist dabei das genaueste Verfahren für kleine
    symmetrische Matrizen. Abgebrochen wird, sobald kein Nebenelement mehr
    zählt, spätestens nach :data:`JACOBI_SWEEPS` Durchgängen.
    """
    a = [[float(matrix[row][column]) for column in range(3)] for row in range(3)]
    v = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for _sweep in range(JACOBI_SWEEPS):
        settled = True
        for p, q in ((0, 1), (0, 2), (1, 2)):
            apq = a[p][q]
            # Ein Nebenelement zählt nicht mehr, wenn es neben beiden
            # Diagonalelementen unter der Rundung verschwindet — auch
            # hundertfach genommen (das Kriterium aus „Numerical Recipes").
            reach = 100.0 * abs(apq)
            if apq == 0.0 or (
                abs(a[p][p]) + reach == abs(a[p][p]) and abs(a[q][q]) + reach == abs(a[q][q])
            ):
                a[p][q] = a[q][p] = 0.0
                continue
            settled = False
            theta = (a[q][q] - a[p][p]) / (2.0 * apq)
            if abs(theta) > 1e150:
                t = 0.5 / theta
            else:
                t = 1.0 / (abs(theta) + math.sqrt(theta * theta + 1.0))
                if theta < 0.0:
                    t = -t
            c = 1.0 / math.sqrt(t * t + 1.0)
            s = t * c
            tau = s / (1.0 + c)
            a[p][p] -= t * apq
            a[q][q] += t * apq
            a[p][q] = a[q][p] = 0.0
            r = 3 - p - q
            arp, arq = a[r][p], a[r][q]
            a[r][p] = a[p][r] = arp - s * (arq + tau * arp)
            a[r][q] = a[q][r] = arq + s * (arp - tau * arq)
            for row in range(3):
                vrp, vrq = v[row][p], v[row][q]
                v[row][p] = vrp - s * (vrq + tau * vrp)
                v[row][q] = vrq + s * (vrp - tau * vrq)
        if settled:
            break
    order = sorted(range(3), key=lambda index: (a[index][index], index))
    values = (a[order[0]][order[0]], a[order[1]][order[1]], a[order[2]][order[2]])
    vectors = []
    for index in order:
        column = (v[0][index], v[1][index], v[2][index])
        length = math.hypot(*column)
        vectors.append((column[0] / length, column[1] / length, column[2] / length))
    return values, tuple(vectors)


def plane_fit(
    points: Sequence[Sequence[float]],
) -> tuple[tuple[float, float, float], tuple[float, float, float], float]:
    """Die Ausgleichsebene durch eine Punktwolke: Mitte, Normale und Restspanne.

    Dasselbe, was ``np.linalg.svd(points - mitte)`` beantwortet — die
    Richtung des kleinsten Singulärwerts ist die Normale, der Singulärwert
    selbst die Restspanne (die Wurzel der Quadratsumme der Abstände zur
    Ebene) —, aber **auf jeder Maschine dieselben Bits** (RM-187, siehe
    :func:`symmetric_eigen3`): Die Mitte kommt aus :func:`exact_centre`, die
    Streumatrix aus ``math.fsum`` über die einzeln gerundeten Produkte, die
    Eigenrichtung aus Jacobi.

    Das Vorzeichen der Normalen ist fest (:func:`positive_axis`); wer eine
    Seite meint, dreht sie selbst um. Weniger als drei Punkte haben keine
    Ebene.
    """
    rows = [(float(point[0]), float(point[1]), float(point[2])) for point in points]
    if len(rows) < 3:
        raise ValueError("Eine Ebene braucht mindestens drei Punkte")
    centre = exact_centre(rows)
    offsets = [(x - centre[0], y - centre[1], z - centre[2]) for x, y, z in rows]
    entry = [
        [math.fsum(offset[row] * offset[column] for offset in offsets) for column in range(3)]
        for row in range(3)
    ]
    _values, vectors = symmetric_eigen3(entry)
    normal = positive_axis(vectors[0])
    # Die Restspanne aus den Abständen selbst, nicht aus dem kleinsten
    # Eigenwert: Die Streumatrix quadriert die Kondition, und ihr kleinster
    # Eigenwert trägt einen Fehler von ``eps·λmax`` — an einem ebenen Ring von
    # 60 mm zwei Zehntel Mikrometer Scheinspanne, wo die SVD 10⁻¹³ sagt.
    # ``d * d`` und nicht ``d ** 2``: Pythons Potenz ruft ``pow`` aus der
    # Mathematikbibliothek der Plattform, das Produkt ist IEEE-754.
    distances = [dot3(offset, normal) for offset in offsets]
    spread = math.sqrt(math.fsum(distance * distance for distance in distances))
    return centre, normal, spread


def ring_area(points: Sequence[Sequence[float]]) -> float:
    """Die Fläche eines geschlossenen Streckenzugs in der Ebene, ohne Vorzeichen
    — die Schnürsenkelformel.

    **Eine Schleife in Python, kein NumPy und kein GEOS**, und das ist
    gemessen: Die Ringe, um die es geht, sind klein — die Stegunterseiten
    eines Gitterbechers zu je acht Punkten, die Umrisse einer Skizze —, und
    dort kostet allein das Umpacken einer Tupel-Liste in ein Feld das
    Zwanzigfache der Rechnung: 10,5 µs je Achteck gegen 0,4 µs (21.09.2026);
    erst ab tausend Punkten liegt NumPy überhaupt in derselben Größenordnung,
    und bei 4096 ist die Schleife immer noch dreimal schneller. Vorher stand
    dieselbe Formel zweimal, einmal je Weg — in ``sketch/profile`` und in
    ``slice/analysis`` —, und die eine davon brauchte an 476 Schichten mal 56
    Stücken 287 ms je Vorschlagsrechnung.

    Der Ring darf offen oder mit seinem ersten Punkt geschlossen übergeben
    werden: Der Schluss trägt nichts bei, weil ``x·y - x·y`` null ist.
    Weniger als drei Punkte haben keine Fläche.
    """
    if len(points) < 3:
        return 0.0
    total = 0.0
    ax, ay = points[-1][0], points[-1][1]
    for point in points:
        bx, by = point[0], point[1]
        total += ax * by - bx * ay
        ax, ay = bx, by
    return abs(total) / 2.0
