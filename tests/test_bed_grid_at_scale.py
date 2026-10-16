"""Die Hauptlinien des Bettrasters liegen an den Maßzahlen (FD-170, §18.6).

Das Raster teilte die Platte ab ihrer Ecke in gleiche Felder: Bei 256 mm
waren sie 9,85 mm breit, und die „0“ stand zwischen zwei Hauptlinien. Jetzt
zählen Raster und Zahlen ab derselben Mitte im selben Schritt, auch in Zoll.
Alles hier ohne Fenster; die Ansicht setzt nur ab (``test_bed_grid_visibility``).
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.units import UNIT_TO_MM, LengthUnit
from app.ui.bed_scale import BED_GRID_STEP, bed_grid, bed_scale, grid_step, scale_step

BEDS = [(256.0, 256.0), (220.0, 220.0), (200.0, 200.0), (180.0, 235.0), (350.0, 320.0)]


def _x_lines(points: np.ndarray) -> list[float]:
    """Die Linien quer zur Vorderkante, als ihre X-Lage."""
    pairs = points.reshape(-1, 2, 3)
    along_y = np.isclose(pairs[:, 0, 0], pairs[:, 1, 0])
    return sorted(float(x) for x in pairs[along_y, 0, 0])


def _y_lines(points: np.ndarray) -> list[float]:
    """Die Linien längs der Vorderkante, als ihre Y-Lage."""
    pairs = points.reshape(-1, 2, 3)
    along_x = np.isclose(pairs[:, 0, 1], pairs[:, 1, 1])
    return sorted(float(y) for y in pairs[along_x, 0, 1])


@pytest.mark.parametrize("unit", ["mm", "in"])
@pytest.mark.parametrize(("width", "depth"), BEDS)
def test_every_major_line_carries_a_number_and_every_number_a_major_line(
    unit: LengthUnit, width: float, depth: float
) -> None:
    """Vorderkante zählt X, linke Kante Y — dieselben Lagen wie die Zahlen."""
    _minor, major = bed_grid(width, depth, unit)
    marks = bed_scale(width, depth, unit)
    front = sorted(point[0] for point, _text in marks if point[1] < -depth / 2.0)
    left = sorted(point[1] for point, _text in marks if point[0] < -width / 2.0)
    assert _x_lines(major) == pytest.approx(front)
    assert _y_lines(major) == pytest.approx(left)


@pytest.mark.parametrize("unit", ["mm", "in"])
@pytest.mark.parametrize(("width", "depth"), BEDS)
def test_minor_lines_step_evenly_from_the_middle_and_the_edge_closes_the_grid(
    unit: LengthUnit, width: float, depth: float
) -> None:
    minor, major = bed_grid(width, depth, unit)
    step = grid_step(unit) * UNIT_TO_MM[unit]
    for lines, half in ((_x_lines, width / 2.0), (_y_lines, depth / 2.0)):
        both = sorted(lines(minor) + lines(major))
        assert both[0] == pytest.approx(-half) and both[-1] == pytest.approx(half)
        inner = np.asarray(both[1:-1])
        # Innen liegt jede Linie auf einem Vielfachen des Schritts ab der Mitte.
        np.testing.assert_allclose(inner / step, np.round(inner / step), atol=1e-9)
        np.testing.assert_allclose(np.diff(inner), step)
        assert len(set(np.round(both, 9))) == len(both), "keine Linie doppelt"
        # Kein Strich dicht neben dem Rand, der sich mit ihm als einer läse.
        assert min(both[1] - both[0], both[-1] - both[-2]) >= 0.2 * step - 1e-9


@pytest.mark.parametrize(("width", "depth"), BEDS)
def test_every_line_spans_the_plate_and_lies_on_it(width: float, depth: float) -> None:
    minor, major = bed_grid(width, depth, "mm")
    for points in (minor, major):
        np.testing.assert_allclose(points[:, 2], 0.0)
        assert np.all(np.abs(points[:, 0]) <= width / 2.0 + 1e-9)
        assert np.all(np.abs(points[:, 1]) <= depth / 2.0 + 1e-9)
        pairs = points.reshape(-1, 2, 3)
        lengths = np.linalg.norm(pairs[:, 1] - pairs[:, 0], axis=1)
        assert np.all(np.isclose(lengths, width) | np.isclose(lengths, depth))


@pytest.mark.parametrize(
    ("unit", "step", "per_major"), [("mm", 10.0, 5), ("in", 0.5, 4), ("cm", 1.0, 5), ("m", 0.01, 5)]
)
def test_the_grid_step_is_a_round_part_of_the_scale_step(
    unit: LengthUnit, step: float, per_major: int
) -> None:
    """In Zoll ein halber Zoll, nicht 0,4: so teilt ein Zoll-Lineal."""
    assert grid_step(unit) == pytest.approx(step)
    assert scale_step(unit) / grid_step(unit) == pytest.approx(per_major)
    assert 0.5 * BED_GRID_STEP <= step * UNIT_TO_MM[unit] <= 2.0 * BED_GRID_STEP


def test_a_plate_edge_on_a_number_is_a_major_line() -> None:
    """200 mm: Die Kante liegt bei ±100, also an einer Zahl."""
    minor, major = bed_grid(200.0, 200.0, "mm")
    assert _x_lines(major) == pytest.approx([-100.0, -50.0, 0.0, 50.0, 100.0])
    assert -100.0 not in _x_lines(minor) and 100.0 not in _x_lines(minor)


def test_a_line_crowding_the_edge_gives_way_unless_it_carries_a_number() -> None:
    """256 mm in Zoll: keine Linie bei 127 mm neben dem Rand bei 128 mm.

    202 mm: Die Hauptlinie bei ±100 bleibt an ihrer Zahl, und der Rand einen
    Millimeter daneben kommt nicht als zweiter Strich dazu.
    """
    minor, _major = bed_grid(256.0, 256.0, "in")
    assert 127.0 not in np.round(_x_lines(minor), 6)
    assert max(_x_lines(minor)) == pytest.approx(128.0)
    minor, major = bed_grid(202.0, 202.0, "mm")
    assert _x_lines(major) == pytest.approx([-100.0, -50.0, 0.0, 50.0, 100.0])
    assert max(_x_lines(minor)) == pytest.approx(90.0)
