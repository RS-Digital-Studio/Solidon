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
import functools
import math
from collections.abc import Sequence
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

    Ein Viertelumlauf reicht: Die übrigen drei entstehen durch Vorzeichen und
    Tausch, und beides ist in Fließkomma **exakt** — es ändert kein Bit der
    Mantisse. Das spart nicht nur Zeit; es schreibt auch die Symmetrie fest,
    die ein Kreis haben soll. Bei ``sections``, die nicht durch vier teilbar
    sind, gibt es keine gemeinsamen Viertelpunkte, und dann wird gerechnet.
    """
    with decimal.localcontext() as context:
        context.prec = EXACT_DIGITS
        turn = 2 * _PI
        quarter, remainder = divmod(sections, 4)
        if remainder:
            values = []
            for index in range(sections):
                angle = turn * index / sections
                values.append((float(_cos_series(angle)), float(_sin_series(angle))))
            return tuple(values)
        first = []
        for index in range(quarter + 1):
            angle = turn * index / sections
            first.append((float(_cos_series(angle)), float(_sin_series(angle))))
    values = []
    for index in range(sections):
        eighth, step = divmod(index, quarter)
        cos, sin = first[step]
        # Vorzeichenwechsel und Tausch sind bitgenau — deshalb steht hier
        # eine Tabelle und keine zweite Rechnung.
        turned = ((cos, sin), (-sin, cos), (-cos, -sin), (sin, -cos))[eighth]
        # ``+ 0.0`` streicht die negative Null und lässt jede andere Zahl in
        # Ruhe. Beim Viertelpunkt eines 120-Ecks kam sonst ``(-0.0, 1.0)``
        # heraus: Das Spiegeln dreht auch das Vorzeichen der Null um, und eine
        # negative Null schreibt sich als ``-0.000`` und trennt zwei
        # Schlüssel, die denselben Punkt meinen — dieselbe Falle, die
        # :func:`positive_axis` schon einmal gestellt hat.
        values.append((turned[0] + 0.0, turned[1] + 0.0))
    return tuple(values)


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
    """
    return _exact_degrees(float(degrees))[0]


def exact_sin_degrees(degrees: float) -> float:
    """Sinus eines Winkels in Grad. Siehe :func:`exact_cos_degrees`."""
    return _exact_degrees(float(degrees))[1]


@functools.lru_cache(maxsize=ANGLE_CACHE)
def _exact_degrees(degrees: float) -> tuple[float, float]:
    """Kosinus und Sinus zu einem Gradwinkel, ohne vorher zu runden."""
    with decimal.localcontext() as context:
        context.prec = EXACT_DIGITS
        angle = _reduced(decimal.Decimal(degrees) * _PI / decimal.Decimal(180))
        return (float(_cos_series(angle)), float(_sin_series(angle)))


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
    reihe = list(values)
    if not reihe:
        raise ValueError("Der Mittelwert einer leeren Reihe ist nicht bestimmt")
    return math.fsum(reihe) / len(reihe)


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
