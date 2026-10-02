"""Der SVG-Leser des Umrissimports gegen Sollwerte aus der Geometrie selbst.

Jede Fläche hier ist von Hand gerechnet: ein gedrehtes Rechteck tauscht Breite
und Höhe, eine Scherung erhält die Fläche, eine Ellipse hat π·a·b. trimeshs
eigener Leser verfehlte mehrere davon still (``rotate(90)`` drehte um gut 107°,
``skewX`` fehlte, Ellipsen fehlten ganz, abgerundete Ecken waren spitz).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.ingest import outline, svg_drawing
from app.core.units import MAX_FACET_SAG

HEIGHT = 3.0


def _svg(body: str) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        f"{body}</svg>"
    ).encode()


def _area(body: str) -> float:
    return float(outline.extrude(_svg(body), ".svg", height=HEIGHT).mesh.volume) / HEIGHT


def _rings(body: str) -> list[np.ndarray]:
    path = trimesh.load_path(svg_drawing.path_arguments(_svg(body)))
    return [np.asarray(ring, dtype=float) for ring in path.discrete]


def _bounds(body: str) -> tuple[np.ndarray, np.ndarray]:
    points = np.vstack(_rings(body))
    return points.min(axis=0), points.max(axis=0)


def test_rotate_turns_by_degrees() -> None:
    low, high = _bounds('<rect width="20" height="10" transform="rotate(90)"/>')
    assert high - low == pytest.approx((10.0, 20.0), abs=1e-9)
    assert _area('<rect width="20" height="10" transform="rotate(90)"/>') == pytest.approx(200.0)


def test_rotate_about_a_centre_keeps_that_centre() -> None:
    low, high = _bounds('<rect width="20" height="10" transform="rotate(90 10 5)"/>')
    assert (low + high) / 2 == pytest.approx((10.0, 5.0), abs=1e-9)
    assert high - low == pytest.approx((10.0, 20.0), abs=1e-9)


@pytest.mark.parametrize("transform", ["skewX(45)", "skewY(30)"])
def test_a_shear_keeps_the_area(transform: str) -> None:
    body = f'<rect width="10" height="10" transform="{transform}"/>'
    assert _area(body) == pytest.approx(100.0)
    low, high = _bounds(body)
    if transform == "skewX(45)":
        assert high - low == pytest.approx((20.0, 10.0), abs=1e-9)
    else:
        assert high - low == pytest.approx((10.0, 10.0 + 10.0 * math.tan(math.radians(30))))


def test_transforms_apply_through_every_level() -> None:
    nested = '<g transform="translate(1,0)">' * 12 + '<rect width="2" height="2"/>' + "</g>" * 12
    low, _high = _bounds(nested)
    assert low == pytest.approx((12.0, 0.0), abs=1e-9)


@pytest.mark.parametrize(
    "body",
    [
        '<ellipse cx="0" cy="0" rx="20" ry="10"/>',
        '<circle r="10" transform="scale(2,1)"/>',
    ],
)
def test_an_ellipse_is_read_as_an_ellipse(body: str) -> None:
    exact = math.pi * 20.0 * 10.0
    area = _area(body)
    assert exact * 0.99 < area <= exact + 1e-9
    low, high = _bounds(body)
    # Die Punkte liegen auf der Ellipse, treffen ihren Scheitel aber nicht zwingend.
    assert high - low == pytest.approx((40.0, 20.0), abs=MAX_FACET_SAG)
    assert (high - low <= (40.0 + 1e-9, 20.0 + 1e-9)).all()
    for ring in _rings(body):
        # Jeder Punkt liegt auf der Ellipse; die Sehnen halten MAX_FACET_SAG.
        assert np.allclose((ring[:, 0] / 20.0) ** 2 + (ring[:, 1] / 10.0) ** 2, 1.0, atol=1e-9)
        middles = (ring[1:] + ring[:-1]) / 2
        gap = 1.0 - np.hypot(middles[:, 0] / 20.0, middles[:, 1] / 10.0)
        assert float(gap.max()) * 20.0 <= MAX_FACET_SAG + 1e-9


def test_an_elliptical_arc_in_a_path_stays_elliptical() -> None:
    exact = math.pi * 20.0 * 10.0 / 2
    area = _area('<path d="M0,0 A 20 10 0 0 1 40 0 Z"/>')
    assert exact * 0.99 < area <= exact + 1e-9


def test_rounded_corners_are_round() -> None:
    exact = 40.0 * 20.0 - (4.0 - math.pi) * 5.0**2
    assert _area('<rect width="40" height="20" rx="5"/>') == pytest.approx(exact, rel=1e-3)
    # ``rx`` fehlt und folgt ``ry``. Zu große Radien kappt die Vorschrift je Achse
    # auf die halbe Seite (SVG 1.1, §9.2): aus rx = ry = 50 wird eine Ellipse von 40 auf 20.
    assert _area('<rect width="40" height="20" ry="5"/>') == pytest.approx(exact, rel=1e-3)
    ellipse = math.pi * 20.0 * 10.0
    assert ellipse * 0.99 < _area('<rect width="40" height="20" rx="50"/>') <= ellipse


def test_what_is_not_drawn_is_not_read() -> None:
    body = (
        '<defs><rect id="r" width="5" height="5"/></defs>'
        '<clipPath id="c"><rect width="99" height="99"/></clipPath>'
        '<marker id="m"><circle r="3"/></marker>'
        '<g style="fill:red; display: none"><rect width="50" height="50"/></g>'
        '<rect display="none" width="60" height="60"/>'
        '<rect width="20" height="10"/>'
    )
    rings = _rings(body)
    assert len(rings) == 1
    assert _area(body) == pytest.approx(200.0)


def test_use_places_what_it_points_at() -> None:
    body = (
        '<defs><rect id="r" width="5" height="5"/></defs>'
        '<symbol id="s"><rect width="4" height="4"/></symbol>'
        '<use href="#r" x="30"/>'
        '<use xlink:href="#s" x="10" y="10" transform="translate(100,0)"/>'
    )
    lows = sorted(tuple(np.round(ring.min(axis=0), 9)) for ring in _rings(body))
    assert lows == [(30.0, 0.0), (110.0, 10.0)]


def test_a_use_that_points_at_itself_draws_nothing_twice() -> None:
    body = '<g id="a"><rect width="5" height="5"/><use href="#a" x="10"/></g>'
    assert len(_rings(body)) == 1


def test_a_drawing_that_multiplies_itself_is_refused() -> None:
    levels = ['<rect id="l0" width="1" height="1"/>']
    for level in range(1, 7):
        uses = "".join(f'<use href="#l{level - 1}" x="{index}"/>' for index in range(10))
        levels.append(f'<g id="l{level}">{uses}</g>')
    payload = _svg("<defs>" + "".join(levels) + '</defs><use href="#l6"/>')
    with pytest.raises(ValueError, match="Grundformen"):
        svg_drawing.path_arguments(payload)
    with pytest.raises(ValidationError) as refused:
        outline.read_profiles(payload, ".svg")
    assert refused.value.constraint == "unreadable"


@pytest.mark.parametrize(
    "body",
    [
        '<rect width="20" height="10" transform="rotate(abc)"/>',
        '<rect width="20" height="10" transform="wobble(3)"/>',
        '<rect width="20" height="10" transform="translate(1,2,3)"/>',
        '<rect width="20mm" height="10"/>',
    ],
)
def test_an_unreadable_value_says_so(body: str) -> None:
    with pytest.raises(ValidationError) as refused:
        outline.read_profiles(_svg(body), ".svg")
    assert refused.value.constraint == "unreadable"
    assert refused.value.suggestions


def test_pixels_are_the_user_unit() -> None:
    assert _area('<rect width="20px" height="10px"/>') == pytest.approx(200.0)


def test_a_transform_list_multiplies_from_the_left() -> None:
    matrix = svg_drawing.parse_transform("translate(10, 0) scale(2), rotate(90)")
    assert matrix @ np.array([1.0, 0.0, 1.0]) == pytest.approx((10.0, 2.0, 1.0))
    assert svg_drawing.parse_transform("matrix(1 0 0 1 3 4)") @ np.array(
        [0.0, 0.0, 1.0]
    ) == pytest.approx((3.0, 4.0, 1.0))
