"""Schriftzüge über HarfBuzz gegen Sollwerte aus den Schriftdateien selbst (RM-471).

Die Sollwerte liest fontTools, nicht HarfBuzz: die exakte Glyphenfläche über
``AreaPen`` und die Kurven über einen eigenen Pen. Gemessen am 03.10.2026 lag
matplotlibs ``to_polygons`` bei 10 mm Schrifthöhe bis 1,5 % unter der exakten
Fläche und bei 3 mm bis 2,4 %; der neue Weg bleibt bei jeder Größe unter 0,2 %.
"""

from __future__ import annotations

import math
import subprocess
import sys

import numpy as np
import pytest
from fontTools.pens.areaPen import AreaPen
from fontTools.ttLib import TTFont
from shapely.geometry import LineString
from shapely.ops import unary_union

from app.core.errors import ValidationError
from app.core.geom import glyphs
from app.core.geom.label_ops import outlines


def _exact_area(text: str, size: float, font: str, style: str = "regular") -> float:
    with TTFont(glyphs.font_file(font, style)) as source:
        glyph_set, cmap = source.getGlyphSet(), source.getBestCmap()
        scale = size / source["head"].unitsPerEm
        total = 0.0
        for character in text:
            pen = AreaPen(glyph_set)
            glyph_set[cmap[ord(character)]].draw(pen)
            total += abs(pen.value)
    return total * scale * scale


@pytest.mark.parametrize("size", [3.0, 10.0, 50.0])
@pytest.mark.parametrize("font", ["DejaVu Sans", "Liberation Serif", "Liberation Mono"])
def test_the_filled_letters_keep_the_exact_glyph_area(font: str, size: float) -> None:
    text = "Deckel 80"
    area = unary_union(outlines(text, size, font)).area
    exact = _exact_area(text.replace(" ", ""), size, font)
    assert abs(area - exact) / exact < 0.002, f"{font} {size} mm: {area:.4f} gegen {exact:.4f}"


@pytest.mark.parametrize("size", [3.0, 50.0])
def test_every_chord_stays_within_the_sag_for_its_size(size: float) -> None:
    """Jede Sehne liegt höchstens ``sag_for(size)`` neben ihrer Kurve."""
    found = glyphs.contours("Og&", size, "Dancing Script", "regular")
    sag = glyphs.sag_for(size)
    assert sag <= 0.05
    worst = 0.0
    for contour in found:
        for poles in contour:
            if len(poles) == 2:
                continue
            chord = LineString(glyphs.flattened(poles, sag))
            degree = len(poles) - 1
            array = np.asarray(poles)
            for t in np.linspace(0.0, 1.0, 41):
                weights = [
                    math.comb(degree, k) * (1 - t) ** (degree - k) * t**k for k in range(degree + 1)
                ]
                x, y = np.asarray(weights) @ array
                worst = max(worst, chord.distance(LineString([(x, y), (x, y + 1e-12)])))
    assert worst <= sag + 1e-9, f"{worst:.5f} mm bei erlaubten {sag:.5f}"


def test_an_unknown_family_and_a_missing_cut_are_refused() -> None:
    with pytest.raises(ValidationError) as unknown:
        glyphs.font_file("Arial", "regular")
    assert unknown.value.field == "font"
    with pytest.raises(ValidationError) as cut:
        glyphs.font_file("Comfortaa", "bold")
    assert cut.value.field == "style"


def test_lettering_runs_without_matplotlib() -> None:
    """Der Kern setzt Schrift, ohne matplotlib zu laden — es liegt nicht mehr im Paket."""
    probe = (
        "import sys; from app.core.geom.label_ops import outlines; "
        "assert outlines('Solidon', 10.0); "
        "assert 'matplotlib' not in sys.modules, 'matplotlib wurde geladen'"
    )
    run = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr[-500:]


def test_no_chord_of_a_curve_is_longer_than_the_chord_for_its_size() -> None:
    """Auch auf der fast geraden Strecke einer Kurve bleiben die Sehnen kurz.

    Sonst liest die Erkennung ihre Streifen als Ebene: Der untere Bogen der „3“
    in DejaVu Sans Mono auf 60 mm zerfiel in zwei Stücke und eine Fläche.
    """
    size = 60.0
    longest = glyphs.chord_for(size)
    for contour in glyphs.contours("3", size, "DejaVu Sans Mono", "regular"):
        for poles in contour:
            if len(poles) == 2:
                continue
            points = np.asarray(glyphs.flattened(poles, glyphs.sag_for(size), longest))
            assert float(np.max(np.linalg.norm(np.diff(points, axis=0), axis=1))) <= longest
