"""Die Maßzahlen an der Platte (§18.6) — in der Anzeigeeinheit (§19.3).

Ein Raster ohne Zahlen sagt nur, dass es ein Raster gibt. Erst die Zahl
daneben macht daraus einen Maßstab, an dem man ein Teil einordnet, ohne zu
messen — und das ist der Zweck der Platte in echter Größe.

Zahlen und Raster zählen deshalb ab derselben Mitte im selben Schritt: Jede
Hauptlinie trägt eine Zahl, jede Zahl steht an einer Hauptlinie (FD-170).

Als eigene Rechnung und nicht im Zeichnen versteckt: offscreen gibt es keinen
Renderer, und eine Prüfung, die sich dort überspringt, prüft nie etwas. Die
Ansicht (``Viewport._draw_one_bed``) setzt Marken und Linien nur noch ab.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

from app.core.units import EPS_GEOM, UNIT_TO_MM, LengthUnit
from app.ui.labels import compact_figure, display_unit, localised

#: Abstand der Maßzahlen an der Platte, in Millimetern. Fünfzig, weil das
#: Raster bei zehn liegt: eine Zahl an jeder Rasterlinie wäre ein Zaun aus
#: Ziffern, und eine alle hundert ließe eine 220er-Platte mit zwei Zahlen
#: zurück. In einer anderen Einheit gilt die runde Zahl, die dem am nächsten
#: kommt (:func:`scale_step`).
BED_SCALE_STEP: Final = 50.0

#: Abstand der Nebenlinien des Bettrasters, in Millimetern; in einer anderen
#: Einheit die runde Zahl, die dem am nächsten kommt (:func:`grid_step`).
BED_GRID_STEP: Final = 10.0

#: Wie weit die Zahlen neben der Plattenkante stehen. Weit genug, dass sie
#: nicht auf einem Teil liegen, das bis an den Rand geht.
BED_SCALE_GAP: Final = 8.0

#: Wie nah eine Rasterlinie dem Plattenrand kommen darf, als Anteil des
#: Rasterschritts, bevor Rand und Linie einer werden: 256 mm in Zoll legten
#: sonst eine Linie bei 127 mm neben den Rand bei 128 mm.
_EDGE_CROWD: Final = 0.2

#: Die runden Ziffern einer Skala: 1, 2 und 5 je Zehnerpotenz.
_ROUND_DIGITS: Final = (1.0, 2.0, 5.0)

Mark = tuple[tuple[float, float, float], str]


def _round_near(millimetres: float, unit: LengthUnit) -> float:
    """Aus 1, 2 und 5 je Zehnerpotenz die Zahl in ``unit``, die ``millimetres``
    im Verhältnis am nächsten kommt."""
    target = millimetres / UNIT_TO_MM[unit]
    exponent = math.floor(math.log10(target))
    candidates = [
        digit * 10.0**power for power in (exponent, exponent + 1) for digit in _ROUND_DIGITS
    ]
    return min(candidates, key=lambda candidate: abs(math.log(candidate / target)))


def scale_step(unit: LengthUnit) -> float:
    """Der Schritt der Skala in ``unit``: die runde Zahl nahe :data:`BED_SCALE_STEP`.

    In Zoll wären fünfzig Millimeter 1,97 — eine Skala, die so zählt, liest
    niemand. Gewählt wird aus 1, 2 und 5 je Zehnerpotenz die, deren Abstand im
    Verhältnis am kleinsten ist: 50 mm, 2 in, 5 cm.
    """
    return _round_near(BED_SCALE_STEP, unit)


def grid_step(unit: LengthUnit) -> float:
    """Der Abstand der Nebenlinien in ``unit``: die runde Zahl nahe :data:`BED_GRID_STEP`.

    10 mm, 1 cm und ein halber Zoll — nicht 0,4 in, die ein Fünftel des
    Skalenschritts wären: Ein Zoll-Lineal teilt in Halbe, nicht in Fünftel.
    Jede dieser Zahlen teilt den Skalenschritt ohne Rest, sodass jede
    Hauptlinie zugleich eine Rasterlinie ist.
    """
    return _round_near(BED_GRID_STEP, unit)


def bed_grid(
    width: float, depth: float, unit: LengthUnit | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Die Linien des Bettrasters um die Plattenmitte: Neben- und Hauptlinien.

    Je Stufe Punktpaare in Millimetern auf Höhe null, für
    ``add_lines(polylines=[2, …])``. **Die Hauptlinien liegen an den Zahlen
    von** :func:`bed_scale` — dieselbe Mitte, derselbe Schritt, dieselbe
    Einheit; vorher teilte das Raster die Platte ab ihrer Ecke in gleiche
    Felder, und die „0“ stand zwischen zwei Hauptlinien (FD-170). Die Ränder
    schließen das Raster als Nebenlinien, wo keine Rasterlinie auf oder dicht
    neben ihnen liegt (:data:`_EDGE_CROWD`). Keine Linie steht in beiden Stufen.
    """
    shown = unit or display_unit()
    minor_step = grid_step(shown) * UNIT_TO_MM[shown]
    major_step = scale_step(shown) * UNIT_TO_MM[shown]
    every = round(major_step / minor_step)
    half_width, half_depth = width / 2.0, depth / 2.0

    def levels(half: float) -> tuple[np.ndarray, np.ndarray]:
        """Die Lagen einer Richtung, getrennt in Neben- und Hauptlagen."""
        count = math.floor((half + EPS_GEOM) / minor_step)
        index = np.arange(-count, count + 1)
        major = index % every == 0
        values = index * minor_step
        # Die Hauptlagen rechnen wie die Zahlen, damit beide genau übereinander stehen.
        values[major] = (index[major] // every) * major_step
        gap = half - count * minor_step
        if gap <= EPS_GEOM or (gap < _EDGE_CROWD * minor_step and major[-1]):
            # Der Rand liegt auf der letzten Linie oder dicht an einer Hauptlinie,
            # die an ihrer Zahl bleibt.
            return values[~major], values[major]
        if gap < _EDGE_CROWD * minor_step:
            # Zwei Striche dicht beieinander läsen sich als ein dicker: Der Rand
            # nimmt den Platz der letzten Nebenlinie.
            values, major = values[1:-1], major[1:-1]
        values = np.concatenate(([-half], values, [half]))
        major = np.concatenate(([False], major, [False]))
        return values[~major], values[major]

    def lines(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """Linien quer (an ``xs``) und längs (an ``ys``) über die ganze Platte."""
        across = np.zeros((len(xs), 2, 3))
        across[:, :, 0] = xs[:, None]
        across[:, :, 1] = (-half_depth, half_depth)
        along = np.zeros((len(ys), 2, 3))
        along[:, :, 0] = (-half_width, half_width)
        along[:, :, 1] = ys[:, None]
        return np.concatenate((across, along)).reshape(-1, 3)

    minor_x, major_x = levels(half_width)
    minor_y, major_y = levels(half_depth)
    return lines(minor_x, minor_y), lines(major_x, major_y)


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
