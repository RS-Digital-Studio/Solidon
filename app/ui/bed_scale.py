"""Die Maßzahlen an der Platte (§18.6) — in der Anzeigeeinheit (§19.3).

Ein Raster ohne Zahlen sagt nur, dass es ein Raster gibt. Erst die Zahl
daneben macht daraus einen Maßstab, an dem man ein Teil einordnet, ohne zu
messen — und das ist der Zweck der Platte in echter Größe.

Als eigene Rechnung und nicht im Zeichnen versteckt: offscreen gibt es keinen
Renderer, und eine Prüfung, die sich dort überspringt, prüft nie etwas. Die
Ansicht (``Viewport._draw_one_bed``) setzt die Marken nur noch ab.
"""

from __future__ import annotations

import math
from typing import Final

from app.core.units import EPS_GEOM, UNIT_TO_MM, LengthUnit
from app.ui.labels import compact_figure, display_unit, localised

#: Abstand der Maßzahlen an der Platte, in Millimetern. Fünfzig, weil das
#: Raster bei zehn liegt: eine Zahl an jeder Rasterlinie wäre ein Zaun aus
#: Ziffern, und eine alle hundert ließe eine 220er-Platte mit zwei Zahlen
#: zurück. In einer anderen Einheit gilt die runde Zahl, die dem am nächsten
#: kommt (:func:`scale_step`).
BED_SCALE_STEP: Final = 50.0

#: Wie weit die Zahlen neben der Plattenkante stehen. Weit genug, dass sie
#: nicht auf einem Teil liegen, das bis an den Rand geht.
BED_SCALE_GAP: Final = 8.0

#: Die runden Ziffern einer Skala: 1, 2 und 5 je Zehnerpotenz.
_ROUND_DIGITS: Final = (1.0, 2.0, 5.0)

Mark = tuple[tuple[float, float, float], str]


def scale_step(unit: LengthUnit) -> float:
    """Der Schritt der Skala in ``unit``: die runde Zahl nahe :data:`BED_SCALE_STEP`.

    In Zoll wären fünfzig Millimeter 1,97 — eine Skala, die so zählt, liest
    niemand. Gewählt wird aus 1, 2 und 5 je Zehnerpotenz die, deren Abstand im
    Verhältnis am kleinsten ist: 50 mm, 2 in, 5 cm.
    """
    target = BED_SCALE_STEP / UNIT_TO_MM[unit]
    exponent = math.floor(math.log10(target))
    candidates = [
        digit * 10.0**power for power in (exponent, exponent + 1) for digit in _ROUND_DIGITS
    ]
    return min(candidates, key=lambda candidate: abs(math.log(candidate / target)))


def bed_scale(width: float, depth: float, unit: LengthUnit | None = None) -> list[Mark]:
    """Die Maßzahlen an der vorderen und linken Plattenkante.

    Lagen in Millimetern, Texte in ``unit`` (ohne Angabe die Anzeigeeinheit):
    In Zoll steht die „2" bei 50,8 mm, nicht „50" bei 50 mm (FD-92).

    **Die Zahlen tragen ihr Vorzeichen, und die Null steht in der Mitte ihrer
    Kante.** Der Nullpunkt der Szene ist die Mitte der Platte, nicht ihre Ecke;
    jede Kante bekommt ihre eigene Null. Vorzeichenbehaftet und nicht als
    Abstand von der Mitte, weil die Positionsfelder der Operationsdialoge es
    auch sind — wer „Position X = -40" tippt, soll die -40 auf der Platte finden.

    **Das Einheitenzeichen steht einmal**, an der größten Zahl der Vorderkante:
    an jeder Zahl wäre es ein Zaun, und allein in der Ecke läse sich „in" als
    Wort. Eine Platte schmaler als ein Schritt behält ihre Null; dann trägt sie
    die Einheit.
    """
    shown = unit or display_unit()
    step = scale_step(shown) * UNIT_TO_MM[shown]
    half_width, half_depth = width / 2.0, depth / 2.0

    def along(half: float) -> list[float]:
        """Die Lagen einer Kante: die Null, dann schrittweise nach beiden Seiten."""
        values = [0.0]
        count = 1
        while count * step <= half + EPS_GEOM:
            values.extend((-count * step, count * step))
            count += 1
        return values

    def text(value: float, *, with_unit: bool = False) -> str:
        """Die Zahl in der gezeigten Einheit, ohne Stellen, die nichts sagen."""
        return localised(compact_figure(value, shown, with_unit=with_unit))

    front = along(half_width)
    widest = max(front)
    marks: list[Mark] = [
        ((value, -half_depth - BED_SCALE_GAP, 0.0), text(value, with_unit=value == widest))
        for value in front
    ]
    marks.extend(
        ((-half_width - BED_SCALE_GAP, value, 0.0), text(value)) for value in along(half_depth)
    )
    return marks
