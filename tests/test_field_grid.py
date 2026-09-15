"""Gemeinsame Rasterlage bleibt für Skizze und Feldschnitt identisch."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.sketch import shapes


@pytest.mark.parametrize("columns,rows", [(1, 2), (2, 2), (3, 3), (4, 3), (1, 1)])
def test_even_and_odd_grids_keep_their_center_and_origin(columns, rows):
    centers = shapes.grid_centres(columns, rows, 15, origin=(7, -11))
    expected = [
        ((column - (columns - 1) / 2) * 15 + 7, (row - (rows - 1) / 2) * 15 - 11)
        for row in range(rows)
        for column in range(columns)
    ]
    assert centers == expected
    assert np.mean(centers, axis=0) == pytest.approx((7, -11))
    if columns * rows > 1:
        sketch = shapes.hole_grid(columns, rows, 15, 6)
        assert [element.points[0] for element in sketch.elements] == shapes.grid_centres(
            columns, rows, 15
        )


@pytest.mark.parametrize("columns,rows", [(0, 1), (1, -1), (1.5, 2), (True, 2)])
def test_invalid_grid_count_is_an_actionable_error(columns, rows):
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError):
        shapes.grid_centres(columns, rows, 15)
