"""Eingeschlossene Maximalabstände ausgefüllter Originaldreiecke zu vorhandenen Trägern.

Ein Zeuge ``(u, v)`` bezeichnet die exakte reelle Kombination der ursprünglichen
Float-Ecken ``(1-u-v)*p0 + u*p1 + v*p2``. Angezeigte gerundete Koordinaten sind
kein Ersatz für diesen Punkt. Untergrenzen stammen ausschließlich von solchen
Zeugen; obere Grenzen umfassen das ganze Dreieck.

Die vorhandenen ``exact_sin/exact_cos`` beantworten die Frage nach reproduzierbaren
Floatwerten, nicht nach einer bewiesenen Fehlerklammer. Für den gespeicherten
Kegelhalbwinkel wird deshalb einmal je Träger eine feste alternierende Reihe
mit exakten rationalen Termen gerechnet. Zwei aufeinanderfolgende Teilsummen
schließen den Wert ein: ab dem ersten Folgeterm fallen die Beträge für
``0 < angle < pi/2`` streng. Keine libm-ULP-Annahme und keine zweite Formeinpassung.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import suppress
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Any, Final, cast

import numpy as np

from app.core.scene.cancel import NeverCancelled
from app.core.types import CancelToken, SurfacePatch, Vec3

Triangle = tuple[Vec3, Vec3, Vec3]
_UV = tuple[float, float]

#: Wie oft der Stapel jedes Torus-Stück nach den Extremstellen noch halbiert.
#:
#: Die Sehnenschranke in :meth:`_Batch._torus_edge_upper` wächst mit dem
#: Quadrat der Stückbreite, also viertelt jede Halbierung ihren Beitrag. Zwei
#: sind gemessen: ohne sie blieb der Stapel an 138 von 1 024 Ringdreiecken
#: hinter dem skalaren Weg zurück, weil eine Doppelwurzel je nach Verfahren
#: als Sattel oder als komplexes Paar erscheint und die Teilung dort fehlte.
_TORUS_HALVINGS: Final = 2

#: Kantenarbeit je **Dreieck**, einschließlich der ersten Intervalle.
#:
#: **Sie galt bis zum 22.09.2026 je Trägeraufruf, und das war ein Wettlauf.**
#: Die ersten Dreiecke eines Rings verbrauchten die Marke, alle weiteren
#: bekamen die Rechteckklammer — an einem Ring aus 4 096 Dreiecken blieb sie
#: im Mittel 0,16 mm breit, wo Ebene, Zylinder, Kugel und Kegel auf
#: Mikrometer schließen (RM-202). Je Dreieck vergeben schließt sie überall
#: gleich, und bezahlbar wird das erst durch :func:`_torus_breakpoints`:
#: Die Kante wird an den Extremstellen geteilt statt blind halbiert, also
#: reichen zwei Stücke je Kante für das, wofür die Halbierung sechzehn
#: brauchte.
_MAX_REFINEMENTS: Final = 32
_TRIG_TERMS: Final = 32


@dataclass(frozen=True, slots=True)
class FacetDeviation:
    """Maximum in mm; ``lower_mm`` gehört genau zum enthaltenen ``witness_uv``."""

    lower_mm: float
    upper_mm: float
    witness_uv: _UV
    converged: bool


@dataclass(frozen=True, slots=True)
class DeviationTable:
    """Dieselben Klammern für viele Dreiecke als Arrays — ``nan``, wo nichts belegt ist.

    Die Karte fasst kein Dreieck einzeln an; 41 000 Ergebnisobjekte zu bauen
    und wieder auszulesen kostete mehr als die Rechnung selbst.
    """

    lower_mm: np.ndarray
    upper_mm: np.ndarray
    witness_uv: np.ndarray
    converged: np.ndarray

    @property
    def known(self) -> np.ndarray:
        return np.isfinite(self.lower_mm) & np.isfinite(self.upper_mm)

    def sliced(self, start: int, stop: int) -> DeviationTable:
        return DeviationTable(
            self.lower_mm[start:stop],
            self.upper_mm[start:stop],
            self.witness_uv[start:stop],
            self.converged[start:stop],
        )

    @classmethod
    def joined(cls, tables: Sequence[DeviationTable], count: int) -> DeviationTable:
        if not tables:
            return cls.empty(count)
        return cls(
            np.concatenate([table.lower_mm for table in tables]),
            np.concatenate([table.upper_mm for table in tables]),
            np.concatenate([table.witness_uv for table in tables]),
            np.concatenate([table.converged for table in tables]),
        )

    @classmethod
    def empty(cls, count: int = 0) -> DeviationTable:
        return cls(
            np.full(count, np.nan),
            np.full(count, np.nan),
            np.zeros((count, 2)),
            np.zeros(count, bool),
        )


def _down(value: float) -> float:
    return math.nextafter(value, -math.inf)


def _up(value: float) -> float:
    return math.nextafter(value, math.inf)


@dataclass(frozen=True, slots=True)
class _I:
    """Kleine gerichtete Zahlenklammer ausschließlich für diesen Prüfweg."""

    lo: float
    hi: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.lo) or not math.isfinite(self.hi) or self.lo > self.hi:
            raise ArithmeticError("deviation_interval_not_finite")

    def __add__(self, other: _I) -> _I:
        return _I(_down(self.lo + other.lo), _up(self.hi + other.hi))

    def __neg__(self) -> _I:
        return _I(-self.hi, -self.lo)

    def __sub__(self, other: _I) -> _I:
        return self + -other

    def __mul__(self, other: _I) -> _I:
        products = (self.lo * other.lo, self.lo * other.hi, self.hi * other.lo, self.hi * other.hi)
        return _I(_down(min(products)), _up(max(products)))

    def __truediv__(self, other: _I) -> _I:
        if other.lo <= 0.0 <= other.hi:
            raise ArithmeticError("deviation_division_contains_zero")
        ratios = (self.lo / other.lo, self.lo / other.hi, self.hi / other.lo, self.hi / other.hi)
        return _I(_down(min(ratios)), _up(max(ratios)))

    def square(self) -> _I:
        low = 0.0 if self.lo <= 0.0 <= self.hi else min(self.lo * self.lo, self.hi * self.hi)
        return _I(max(0.0, _down(low)), _up(max(self.lo * self.lo, self.hi * self.hi)))

    def absolute(self) -> _I:
        return _I(
            0.0 if self.lo <= 0 <= self.hi else min(abs(self.lo), abs(self.hi)),
            max(abs(self.lo), abs(self.hi)),
        )

    def sqrt(self) -> _I:
        if self.hi < 0.0:
            raise ArithmeticError("deviation_negative_root")
        return _I(_sqrt_bound(max(0.0, self.lo), False), _sqrt_bound(self.hi, True))

    @property
    def middle(self) -> float:
        return self.lo / 2.0 + self.hi / 2.0


def _number(value: float) -> _I:
    return _I(value, value)


def _fraction(value: Fraction) -> _I:
    rounded = float(value)
    actual = Fraction(rounded)
    return _I(
        _down(rounded) if actual > value else rounded, _up(rounded) if actual < value else rounded
    )


def _sqrt_bound(value: float, upper: bool) -> float:
    """Den Vorschlag durch exaktes rationales Quadrieren bestätigen, nicht ULPs unterstellen."""
    result = math.sqrt(value)
    target = Fraction(value)
    for _ in range(8):
        squared = Fraction(result) ** 2
        if (squared >= target) if upper else (squared <= target):
            return result
        result = _up(result) if upper else max(0.0, _down(result))
    raise ArithmeticError("deviation_root_not_certified")


_V = tuple[_I, _I, _I]
_ZERO = _number(0.0)
_ONE = _number(1.0)


def _add(a: _V, b: _V) -> _V:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _sub(a: _V, b: _V) -> _V:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _scale(a: _V, factor: _I) -> _V:
    return a[0] * factor, a[1] * factor, a[2] * factor


def _dot(a: Sequence[_I], b: Sequence[_I]) -> _I:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[_I], b: Sequence[_I]) -> _V:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _norm(a: Sequence[_I]) -> _I:
    scale = max(value.absolute().hi for value in a)
    if not scale:
        return _ZERO
    divided = tuple(value / _number(scale) for value in a)
    result = (divided[0].square() + divided[1].square() + divided[2].square()).sqrt() * _number(
        scale
    )
    return _I(max(0.0, result.lo), result.hi)


def _vector(value: Sequence[float]) -> _V:
    return _number(float(value[0])), _number(float(value[1])), _number(float(value[2]))


def _trig(angle: float, cancelled: CancelToken) -> tuple[_I, _I]:
    """Sinus/Kosinus durch aufeinanderfolgende exakte Teilsummen einschließen."""
    x = Fraction(angle)
    square = x * x
    sine = sine_term = x
    cosine = cosine_term = Fraction(1)
    previous_sine, previous_cosine = sine, cosine
    for index in range(1, _TRIG_TERMS + 1):
        cancelled.raise_if_cancelled()
        previous_sine, previous_cosine = sine, cosine
        sine_term *= -square / ((2 * index) * (2 * index + 1))
        cosine_term *= -square / ((2 * index - 1) * (2 * index))
        sine += sine_term
        cosine += cosine_term
    return (
        _I(_fraction(min(sine, previous_sine)).lo, _fraction(max(sine, previous_sine)).hi),
        _I(_fraction(min(cosine, previous_cosine)).lo, _fraction(max(cosine, previous_cosine)).hi),
    )


@dataclass(slots=True)
class _Surface:
    patch: SurfacePatch
    origin: _V
    axis: _V
    axis_size: _I
    radius: _I
    tube_radius: _I
    sine: _I
    cosine: _I
    cancelled: CancelToken
    refinements: int = _MAX_REFINEMENTS

    def radial(self, point: _V) -> _V:
        return _scale(_cross(point, self.axis), _ONE / self.axis_size)

    def axial(self, point: _V) -> _I:
        return _dot(point, self.axis) / self.axis_size

    def distance(self, point: _V) -> _I:
        kind = self.patch.kind
        if kind == "sphere":
            return (_norm(point) - self.radius).absolute()
        z = self.axial(point)
        if kind == "plane":
            return z.absolute()
        rho = _norm(self.radial(point))
        if kind == "cylinder":
            return (rho - self.radius).absolute()
        if kind == "cone":
            h = self.sine * z - self.cosine * rho
            t = self.sine * rho + self.cosine * z
            return (h.square() + _I(min(t.lo, 0.0), min(t.hi, 0.0)).square()).sqrt()
        return (((rho - self.radius).square() + z.square()).sqrt() - self.tube_radius).absolute()


def _prepare(patch: SurfacePatch, cancelled: CancelToken) -> _Surface | None:
    from app.core.perceive.surfaces import valid_patch

    cancelled.raise_if_cancelled()
    if not valid_patch(patch, check_cancelled=cancelled.raise_if_cancelled):
        return None
    params = patch.params
    origin = params["apex" if patch.kind == "cone" else "centre"]
    assert isinstance(origin, tuple)
    axis = params.get("axis", (0.0, 0.0, 1.0))
    assert isinstance(axis, tuple)
    sine, cosine = _ZERO, _ONE
    if patch.kind == "cone":
        angle = params["half_angle"]
        assert isinstance(angle, (int, float))
        sine, cosine = _trig(float(angle), cancelled)
    radius = params.get("ring_radius", params.get("radius", 0.0))
    tube = params.get("tube_radius", 0.0)
    assert isinstance(radius, (int, float)) and isinstance(tube, (int, float))
    axis_scale = _number(max(abs(value) for value in axis))
    direction = cast(_V, tuple(value / axis_scale for value in _vector(axis)))
    return _Surface(
        patch,
        _vector(origin),
        direction,
        _norm(direction),
        _number(float(radius)),
        _number(float(tube)),
        sine,
        cosine,
        cancelled,
        _MAX_REFINEMENTS,
    )


def _legal_uv(u: float, v: float) -> _UV:
    """Jeder Vorschlag wird ein echter Punkt; Rundung darf seine Summe nicht über eins heben."""
    if not math.isfinite(u) or not math.isfinite(v):
        return 0.0, 0.0
    u = min(1.0, max(0.0, u))
    v = min(1.0, max(0.0, v))
    remaining = 1 - Fraction(u)
    if Fraction(v) > remaining:
        v = _fraction(remaining).lo
    return u, max(0.0, v)


class _Facet:
    """Begrenzte Proben eines Originaldreiecks und ihre globale Ausgangsklammer."""

    def __init__(self, triangle: Triangle, surface: _Surface):
        self.raw = triangle
        self.surface = surface
        vertices = tuple(_vector(point) for point in triangle)
        self.points = tuple(_sub(point, surface.origin) for point in vertices)
        self.edges = _sub(vertices[1], vertices[0]), _sub(vertices[2], vertices[0])
        self.samples: dict[_UV, _I] = {}
        self.lower = 0.0
        self.witness = (0.0, 0.0)
        self.upper = math.inf
        for uv in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.25, 0.25)):
            value = self.sample(uv)
            position = self.point(uv)
            radius = max(_norm(_sub(point, position)).hi for point in self.points)
            self.upper = min(self.upper, _up(value.hi + radius))

    def point(self, uv: _UV) -> _V:
        if uv == (0.0, 0.0):
            return self.points[0]
        if uv == (1.0, 0.0):
            return self.points[1]
        if uv == (0.0, 1.0):
            return self.points[2]
        return _add(
            self.points[0],
            _add(_scale(self.edges[0], _number(uv[0])), _scale(self.edges[1], _number(uv[1]))),
        )

    def sample(self, uv: _UV) -> _I:
        uv = _legal_uv(*uv)
        if uv not in self.samples:
            self.surface.cancelled.raise_if_cancelled()
            self.samples[uv] = self.surface.distance(self.point(uv))
        value = self.samples[uv]
        if value.lo > self.lower:
            self.lower, self.witness = value.lo, uv
        return value


_CORNERS: Final = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
_EDGES: Final = ((0, 1), (1, 2), (2, 0))


def _middle(point: _V) -> Vec3:
    return point[0].middle, point[1].middle, point[2].middle


def _float_dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _float_sub(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _edge_uv(first: int, second: int, value: float) -> _UV:
    a, b = _CORNERS[first], _CORNERS[second]
    return _legal_uv(a[0] + value * (b[0] - a[0]), a[1] + value * (b[1] - a[1]))


def _barycentric(points: tuple[Vec3, ...], target: Vec3) -> _UV | None:
    """Nur ein Probenvorschlag; seine Genauigkeit begründet keine obere Schranke."""
    vectors = tuple(_float_sub(point, target) for point in points)
    scale = max(abs(value) for vector in vectors for value in vector)
    if not 0.0 < scale < math.inf:
        return None
    a, b, c = (tuple(value / scale for value in vector) for vector in vectors)
    e, f = _float_sub(b, a), _float_sub(c, a)
    ee, ef, ff = _float_dot(e, e), _float_dot(e, f), _float_dot(f, f)
    ae, af = _float_dot(a, e), _float_dot(a, f)
    determinant = ee * ff - ef * ef
    if determinant <= 0.0:
        return None
    return _legal_uv((af * ef - ae * ff) / determinant, (ae * ef - af * ee) / determinant)


def _closest_proposals(points: tuple[_V, ...]) -> list[_UV]:
    floats = tuple(_middle(point) for point in points)
    scale = max(abs(value) for point in floats for value in point)
    if not scale:
        return list(_CORNERS)
    scaled = tuple(tuple(value / scale for value in point) for point in floats)
    proposals = list(_CORNERS)
    for first, second in _EDGES:
        a, b = scaled[first], scaled[second]
        edge = _float_sub(b, a)
        size = _float_dot(edge, edge)
        if size > 0.0:
            value = min(1.0, max(0.0, -_float_dot(a, edge) / size))
            proposals.append(_edge_uv(first, second, value))
    projected = _barycentric(floats, (0.0, 0.0, 0.0))
    if projected is not None:
        proposals.append(projected)
    return proposals


def _affine(points: tuple[_V, ...], uv: _UV) -> _V:
    return _add(
        points[0],
        _add(
            _scale(_sub(points[1], points[0]), _number(uv[0])),
            _scale(_sub(points[2], points[0]), _number(uv[1])),
        ),
    )


def _support_radius(points: tuple[_V, ...], direction: Sequence[float]) -> float:
    """Jede Richtung liefert eine gültige Stützebene für den Abstand zum Ursprung."""
    vector = _vector(direction)
    size = _norm(vector)
    if size.lo <= 0.0:
        return 0.0
    return max(0.0, min((_dot(point, vector) / size).lo for point in points))


def _radius_range(facet: _Facet, points: tuple[_V, ...]) -> tuple[_I, _UV]:
    lower = 0.0
    closest = (0.0, 0.0)
    minimum = math.inf
    for uv in _closest_proposals(points):
        facet.sample(uv)
        point = _affine(points, uv)
        size = _norm(point)
        if size.hi < minimum:
            minimum, closest = size.hi, uv
        lower = max(lower, _support_radius(points, _middle(point)))
    return _I(lower, max(_norm(point).hi for point in points)), closest


def _cone(facet: _Facet, radial: tuple[_V, ...], closest: _UV) -> None:
    """Konkave Stützebenen umfassen H global; Kandidaten verbessern nur die echten Zeugen."""
    surface = facet.surface
    z = tuple(surface.axial(point) for point in facet.points)
    q = tuple(_middle(point) for point in radial)
    axial = tuple(value.middle for value in z)
    for first, second in _EDGES:
        surface.cancelled.raise_if_cancelled()
        p, v = q[first], _float_sub(q[second], q[first])
        a, b = _float_dot(v, v), _float_dot(p, v)
        if not a > 0.0:
            continue
        u0 = -b / a
        facet.sample(_edge_uv(first, second, min(1.0, max(0.0, u0))))
        cross = (p[1] * v[2] - p[2] * v[1], p[2] * v[0] - p[0] * v[2], p[0] * v[1] - p[1] * v[0])
        delta = _float_dot(cross, cross)
        k = (axial[second] - axial[first]) * surface.sine.middle / surface.cosine.middle
        if a > k * k:
            root = u0 + k * math.sqrt(max(0.0, delta / (a * a * (a - k * k))))
            if 0.0 <= root <= 1.0:
                facet.sample(_edge_uv(first, second, root))
    _axis_candidates(facet)
    directions: list[Sequence[float]] = [_middle(_affine(radial, uv)) for uv in facet.samples]
    directions.append((0.0, 0.0, 0.0))
    # Am Achsenmaximum darf die Norm jeden Untergradienten aus der Einheitskugel
    # haben. Die Schnittpunkte der drei linearen Stützbedingungen liefern die
    # nötigen Vorschläge, ihre Zulässigkeit wird durch Normieren hergestellt.
    best_z = surface.axial(facet.point(closest)).middle
    slope = surface.sine.middle / surface.cosine.middle
    offsets = tuple(slope * (value - best_z) for value in axial)
    for first, second in _EDGES:
        left_vector, right_vector = q[first], q[second]
        aa, ab, bb = (
            _float_dot(left_vector, left_vector),
            _float_dot(left_vector, right_vector),
            _float_dot(right_vector, right_vector),
        )
        if aa > 0.0:
            directions.append(tuple(offsets[first] * value / aa for value in left_vector))
        determinant = aa * bb - ab * ab
        if determinant > 0.0:
            left = (offsets[first] * bb - offsets[second] * ab) / determinant
            right = (offsets[second] * aa - offsets[first] * ab) / determinant
            directions.append(
                tuple(left * x + right * y for x, y in zip(left_vector, right_vector, strict=True))
            )
    h_upper = math.inf
    for direction in directions:
        surface.cancelled.raise_if_cancelled()
        if not all(math.isfinite(value) for value in direction):
            continue
        vector = _vector(direction)
        size = _norm(vector)
        # Auch die mathematisch normierte Richtung wird als Intervall gerechnet.
        denominator = _I(max(1.0, size.lo), max(1.0, size.hi))
        unit = _scale(vector, _ONE / denominator)
        bound = max(
            (surface.sine * height - surface.cosine * _dot(unit, point)).hi
            for height, point in zip(z, radial, strict=True)
        )
        h_upper = min(h_upper, bound)
    outside = 0.0
    for point, height in zip(radial, z, strict=True):
        rho = _norm(point)
        h = surface.sine * height - surface.cosine * rho
        t = surface.sine * rho + surface.cosine * height
        value = (
            _I(min(h.lo, 0.0), min(h.hi, 0.0)).square()
            + _I(min(t.lo, 0.0), min(t.hi, 0.0)).square()
        ).sqrt()
        outside = max(outside, value.hi)
    facet.upper = min(facet.upper, max(0.0, outside, h_upper))


_F3 = tuple[Fraction, Fraction, Fraction]


def _fraction_cross(a: Sequence[Fraction], b: Sequence[Fraction]) -> _F3:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _fraction_dot(a: Sequence[Fraction], b: Sequence[Fraction]) -> Fraction:
    return sum((x * y for x, y in zip(a, b, strict=True)), Fraction())


def _axis_candidates(facet: _Facet) -> tuple[list[float], bool]:
    """Achse gegen Originaldreieck, einschließlich exakt koplanarer und entarteter Fälle."""
    surface = facet.surface
    origin = surface.patch.params["apex" if surface.patch.kind == "cone" else "centre"]
    axis = surface.patch.params["axis"]
    assert isinstance(origin, tuple) and isinstance(axis, tuple)
    points = tuple(
        tuple(
            Fraction(value) - Fraction(anchor) for value, anchor in zip(point, origin, strict=True)
        )
        for point in facet.raw
    )
    direction = tuple(Fraction(value) for value in axis)
    edges = tuple(
        tuple(b - a for a, b in zip(points[0], point, strict=True)) for point in points[1:]
    )
    normal = _fraction_cross(edges[0], edges[1])
    if not any(normal):
        return [], True
    denominator = _fraction_dot(normal, direction)
    height = _fraction_dot(normal, points[0])
    candidates: list[tuple[Fraction, ...]] = []
    if denominator:
        point = tuple(value * height / denominator for value in direction)
        relative = tuple(a - b for a, b in zip(point, points[0], strict=True))
        aa, ab, bb = (
            _fraction_dot(edges[0], edges[0]),
            _fraction_dot(edges[0], edges[1]),
            _fraction_dot(edges[1], edges[1]),
        )
        ea, eb = _fraction_dot(relative, edges[0]), _fraction_dot(relative, edges[1])
        determinant = aa * bb - ab * ab
        u, v = (ea * bb - eb * ab) / determinant, (eb * aa - ea * ab) / determinant
        if u >= 0 and v >= 0 and u + v <= 1:
            candidates.append((u, v))
    elif not height:
        for first, second in _EDGES:
            a, b = (
                _fraction_cross(points[first], direction),
                _fraction_cross(points[second], direction),
            )
            delta = tuple(y - x for x, y in zip(a, b, strict=True))
            nonzero = next((index for index, value in enumerate(delta) if value), None)
            if nonzero is None:
                if not any(a):
                    candidates.extend(
                        tuple(Fraction(value) for value in _CORNERS[index])
                        for index in (first, second)
                    )
                continue
            value = -a[nonzero] / delta[nonzero]
            if 0 <= value <= 1 and all(x + value * y == 0 for x, y in zip(a, delta, strict=True)):
                candidates.append(
                    tuple(
                        Fraction(x) + value * Fraction(y - x)
                        for x, y in zip(_CORNERS[first], _CORNERS[second], strict=True)
                    )
                )
    upper = []
    for u, v in candidates:
        surface.cancelled.raise_if_cancelled()
        point_box = cast(
            _V,
            tuple(
                _fraction((1 - u - v) * a + u * b + v * c) for a, b, c in zip(*points, strict=True)
            ),
        )
        upper.append(surface.distance(point_box).hi)
        facet.sample(_legal_uv(float(u), float(v)))
    return upper, False


def _candidate_upper(facet: _Facet, point: _V, normal: _V) -> float | None:
    """Nur bewiesen außerhalb liegende Kandidaten streichen; Zeugen bleiben Originalpunkte."""
    for first, second in _EDGES:
        edge = _sub(facet.points[second], facet.points[first])
        sign = _dot(_cross(edge, _sub(point, facet.points[first])), normal)
        if sign.hi < 0.0:
            return None
    proposal = _barycentric(tuple(_middle(entry) for entry in facet.points), _middle(point))
    if proposal is not None:
        facet.sample(proposal)
    return facet.surface.distance(point).hi


def _torus_interior(facet: _Facet) -> tuple[list[float], bool]:
    """Vier glatte Innenkandidaten und die Achse; unklare Horizontalität bleibt offen."""
    surface = facet.surface
    upper, degenerate = _axis_candidates(facet)
    if degenerate:
        return upper, True
    normal = _cross(facet.edges[0], facet.edges[1])
    size = _norm(normal)
    if size.lo <= 0.0:
        return upper, False
    unit = _scale(normal, _ONE / size)
    axis = _scale(surface.axis, _ONE / surface.axis_size)
    b = _dot(unit, axis)
    projected = _sub(unit, _scale(axis, b))
    a = _norm(projected)
    if a.lo <= 0.0:
        return upper, False
    radial = _scale(projected, _ONE / a)
    side = _cross(axis, radial)
    height = _dot(unit, facet.points[0])
    for sign in (-1.0, 1.0):
        surface.cancelled.raise_if_cancelled()
        offset = height - _number(sign) * a * surface.radius
        point = _add(_scale(radial, _number(sign) * surface.radius), _scale(unit, offset))
        # Die Meridianhalbebene ist Teil der analytischen Kandidatenbedingung.
        if (_dot(point, radial) * _number(sign)).hi > 0.0:
            bound = _candidate_upper(facet, point, normal)
            if bound is not None:
                upper.append(bound)
    along = height / a
    square = surface.radius.square() - along.square()
    if square.hi >= 0.0:
        root = _I(max(0.0, square.lo), square.hi).sqrt()
        for sign in (-1.0, 1.0):
            point = _add(_scale(radial, along), _scale(side, _number(sign) * root))
            bound = _candidate_upper(facet, point, normal)
            if bound is not None:
                upper.append(bound)
    return upper, True


def _torus_ring_proposals(facet: _Facet, radial: tuple[_V, ...], closest: _UV) -> None:
    """Radienübergänge liefern günstige Originalzeugen, keinen Existenzbeweis für Extrema."""
    start = _middle(_affine(radial, closest))
    radius = facet.surface.radius.middle
    for index, corner in enumerate(radial):
        delta = _float_sub(_middle(corner), start)
        a, b = _float_dot(delta, delta), _float_dot(start, delta)
        c = _float_dot(start, start) - radius * radius
        discriminant = b * b - a * c
        if a <= 0.0 or discriminant < 0.0:
            continue
        for sign in (-1.0, 1.0):
            value = (-b + sign * math.sqrt(discriminant)) / a
            if 0.0 <= value <= 1.0:
                corner_uv = _CORNERS[index]
                facet.sample(
                    _legal_uv(
                        closest[0] + value * (corner_uv[0] - closest[0]),
                        closest[1] + value * (corner_uv[1] - closest[1]),
                    )
                )


def _torus_square(surface: _Surface, point: _V) -> _I:
    return (_norm(surface.radial(point)) - surface.radius).square() + surface.axial(point).square()


def _edge_point(facet: _Facet, first: int, second: int, value: float) -> _V:
    """Die exakte lineare Kantenposition einschließen, auch wenn 1-t kein Float mehr ist."""
    return _add(
        facet.points[first], _scale(_sub(facet.points[second], facet.points[first]), _number(value))
    )


def _edge_upper(facet: _Facet, first: int, second: int, low: float, high: float) -> float:
    """Vollständiges Kantenintervall: Lipschitz, monotone Ableitung und quadratische Sehne."""
    surface = facet.surface
    surface.cancelled.raise_if_cancelled()
    middle = low / 2.0 + high / 2.0
    point = _edge_point(facet, first, second, middle)
    left, right = _edge_point(facet, first, second, low), _edge_point(facet, first, second, high)
    at_middle = surface.distance(point)
    at_left, at_right = surface.distance(left), surface.distance(right)
    for value in (low, middle, high):
        facet.sample(_edge_uv(first, second, value))
    edge = _sub(facet.points[second], facet.points[first])
    width = _number(high) - _number(low)
    half_width = max(
        (_number(middle) - _number(low)).hi,
        (_number(high) - _number(middle)).hi,
    )
    upper = (at_middle + _norm(edge) * _number(half_width)).hi
    qleft, qright = surface.radial(left), surface.radial(right)
    qdelta = surface.radial(edge)
    a, delta = _middle(qleft), _float_sub(_middle(qright), _middle(qleft))
    length = _float_dot(delta, delta)
    t = min(1.0, max(0.0, -_float_dot(a, delta) / length)) if length > 0.0 else 0.0
    direction = tuple(x + t * y for x, y in zip(a, delta, strict=True))
    radial_lower = _support_radius((qleft, qright), direction)
    radial_upper = max(_norm(qleft).hi, _norm(qright).hi)
    if radial_lower > 0.0:
        rho = _I(radial_lower, radial_upper)
        box = tuple(_I(min(a.lo, b.lo), max(a.hi, b.hi)) for a, b in zip(left, right, strict=True))
        qbox = tuple(
            _I(min(a.lo, b.lo), max(a.hi, b.hi)) for a, b in zip(qleft, qright, strict=True)
        )
        derivative = _number(2.0) * (_dot(box, edge) - surface.radius * _dot(qbox, qdelta) / rho)
        if derivative.lo > 0.0 or derivative.hi < 0.0:
            return min(upper, max(at_left.hi, at_right.hi))
        delta_square = _norm(_cross(qleft, qdelta)).square()
        curvature = _number(2.0) * _norm(edge).square() + _number(
            2.0
        ) * surface.radius * delta_square / (_number(radial_lower).square() * _number(radial_lower))
        error = curvature * width.square() / _number(8.0)
        fleft, fright = _torus_square(surface, left), _torus_square(surface, right)
        frange = _I(
            max(0.0, _down(min(fleft.lo, fright.lo) - error.hi)),
            _up(max(fleft.hi, fright.hi) + error.hi),
        )
        upper = min(upper, (frange.sqrt() - surface.tube_radius).absolute().hi)
    return upper


def _torus_breakpoints(facet: _Facet, first: int, second: int) -> tuple[float, ...]:
    """Wo der Abstand zum Ring auf dieser Kante seine Extrema hat — geschlossen.

    Auf der Kante ``P(t) = A + tD`` ist der quadrierte Abstand zum Ringkreis
    ``f(t) = |P|² - 2R·r + R²``, wobei ``r`` der Abstand zur Achse ist und
    ``r² + z² = |P|²``. Mit ``m = <P,D>``, ``z = <P,Achse>`` und
    ``h = m - z·z'`` ist

        f'(t) = 2m - 2R·h/r  =  0  <=>  m·r = R·h,

    quadriert also ``m²·r² - R²·h² = 0`` — ``m`` und ``h`` linear, ``r²``
    quadratisch, zusammen ein Polynom **vierten** Grades. Seine reellen
    Wurzeln in ``(0, 1)`` sind die Stellen, an denen ``f`` kehrt.

    **Das ist ein Vorschlag, kein Beweis.** Gerechnet wird in Fließkomma, und
    das Quadrieren bringt Scheinwurzeln mit (``m·r = -R·h``). Beides schadet
    nicht: :func:`_edge_upper` schließt jedes Stück für sich mit
    Intervallarithmetik ein, und eine Teilung an einer Stelle, an der nichts
    kehrt, kostet nur einen Aufruf. Was der Vorschlag leistet, ist die
    **Zahl** der Stücke: an einem Ring im Mittel 2,02 je Kante statt sechzehn
    Halbierungen für dieselbe Breite (gemessen am 22.09.2026).
    """
    surface = facet.surface
    start = np.asarray(_middle(facet.points[first]), dtype=float)
    direction = np.asarray(_middle(facet.points[second]), dtype=float) - start
    axis = np.asarray(_middle(surface.axis), dtype=float)
    size = float(np.linalg.norm(axis))
    if size <= 0.0:
        return ()
    axis = axis / size
    ring = surface.radius.middle
    m0, m1 = float(start @ direction), float(direction @ direction)
    z0, z1 = float(start @ axis), float(direction @ axis)
    h0, h1 = m0 - z0 * z1, m1 - z1 * z1
    # Der quadrierte Achsabstand: r²(t) = |P|² - z(t)²
    q0, q1, q2 = float(start @ start) - z0 * z0, 2.0 * (m0 - z0 * z1), m1 - z1 * z1
    squared = np.polynomial.polynomial.polymul([m0, m1], [m0, m1])
    poly = np.polynomial.polynomial.polymul(squared, [q0, q1, q2])
    minus = np.polynomial.polynomial.polymul([h0, h1], [h0, h1]) * (ring * ring)
    poly = poly.copy()
    poly[: len(minus)] -= minus
    if not np.all(np.isfinite(poly)) or not np.any(np.abs(poly) > 0.0):
        return ()
    try:
        roots = np.polynomial.polynomial.polyroots(poly)
    except np.linalg.LinAlgError, ValueError:
        return ()
    inside = sorted(
        float(root.real)
        for root in roots
        if abs(root.imag) <= 1e-9 * max(1.0, abs(root.real)) and 0.0 < root.real < 1.0
    )
    return tuple(inside)


def _torus_intervals(facet: _Facet) -> list[tuple[int, int, float, float, float]]:
    """Die Startintervalle aller drei Kanten, an den Extremstellen geteilt."""
    intervals: list[tuple[int, int, float, float, float]] = []
    for first, second in _EDGES:
        stops = (0.0, *_torus_breakpoints(facet, first, second), 1.0)
        for low, high in pairwise(stops):
            if low < high:
                intervals.append(
                    (first, second, low, high, _edge_upper(facet, first, second, low, high))
                )
    return intervals


def _torus(facet: _Facet, radial: tuple[_V, ...], radius: _I, closest: _UV, epsilon: float) -> None:
    surface = facet.surface
    _torus_ring_proposals(facet, radial, closest)
    heights = tuple(surface.axial(point) for point in facet.points)
    height = _I(min(value.lo for value in heights), max(value.hi for value in heights))
    # Dies ist auch für fast horizontale Ebenen gültig, ohne einen Winkel auf
    # null zu setzen: der ganze tatsächliche Höhenbereich bleibt enthalten.
    rectangle = ((radius - surface.radius).square() + height.square()).sqrt()
    facet.upper = min(facet.upper, (rectangle - surface.tube_radius).absolute().hi)
    if facet.upper - facet.lower <= epsilon:
        return
    if surface.refinements < 3:
        return
    interior, complete = _torus_interior(facet)
    if not complete:
        return
    fixed = max(interior, default=0.0)
    surface.refinements -= 3
    intervals = _torus_intervals(facet)
    if not intervals:
        return
    while True:
        surface.cancelled.raise_if_cancelled()
        largest = max(range(len(intervals)), key=lambda index: intervals[index][4])
        first, second, low, high, upper = intervals[largest]
        facet.upper = min(facet.upper, max(fixed, upper))
        if (
            facet.upper - facet.lower <= epsilon
            or upper <= max(fixed, facet.lower + epsilon)
            or surface.refinements < 2
        ):
            return
        middle = low / 2.0 + high / 2.0
        if not low < middle < high:
            return
        surface.refinements -= 2
        children = [
            (first, second, a, b, min(upper, _edge_upper(facet, first, second, a, b)))
            for a, b in ((low, middle), (middle, high))
        ]
        intervals[largest] = children[0]
        intervals.append(children[1])


def _tighten(facet: _Facet, epsilon: float) -> None:
    kind = facet.surface.patch.kind
    if kind == "plane":
        facet.upper = min(facet.upper, max(facet.sample(uv).hi for uv in _CORNERS))
        return
    radial = (
        facet.points
        if kind == "sphere"
        else tuple(facet.surface.radial(point) for point in facet.points)
    )
    radius, closest = _radius_range(facet, radial)
    if kind in {"sphere", "cylinder"}:
        facet.upper = min(facet.upper, (radius - facet.surface.radius).absolute().hi)
    elif kind == "cone":
        _cone(facet, radial, closest)
    else:
        _torus(facet, radial, radius, closest, epsilon)


# --- Alle Dreiecke einer Trägerart zugleich ----------------------------------------
#
# Bis zum 21.09.2026 lief jedes Dreieck einzeln durch die skalaren Klammern
# oben: 605 124 ``_I``-Objekte für 796 Dreiecke, 200 bis 800 Dreiecke je
# Sekunde, die Karte „Formabweichung" an einem Lochblech 10 mal 10 in einer
# knappen Minute. Die Rechnung je Dreieck ist für Ebene, Kugel, Zylinder und
# Kegel geschlossen — Ecken, Lotfußpunkte, Achsentreffer, Stützebenen —, und
# genau das rechnet ``_Batch`` für alle Dreiecke einer Trägerart zugleich in
# NumPy, mit den Trägerparametern je Dreieck: Ein Lochblech mit hundert
# Bohrungen ist ein Stapel, nicht hundert. Die Zusage bleibt dieselbe:
# ``_Bands`` rundet jede Summe, jedes Produkt und jeden Quotienten wie ``_I``
# um ein ULP nach außen und bestätigt jede Wurzel durch exaktes Quadrieren;
# ein Dreieck, dessen Rechnung nicht endlich bleibt, geht den skalaren Weg.
# Der Torus bekommt hier seine Zeugen und die Rechteckklammer; verfeinert wird
# nur, was danach noch über der Zielbreite liegt — auf dem skalaren Kantenweg
# mit dem gemeinsamen Budget je Träger.

_SPLIT: Final = 134217729.0  # 2**27 + 1, Veltkamp-Aufspaltung
_EXACT_PRODUCT_FLOOR: Final = (
    2.0**-968
)  # unter der kleinsten Normalzahl mal 2⁵⁴ verliert Dekker Bits
_TINY_ROOT: Final = 2.0**-484  # exakt, und sein Quadrat ist genau die Schwelle darüber
_CHUNK: Final = 8192
_ULP_STEP: Final = 2.0**-51
_SMALLEST: Final = 5e-324
#: Bis hierhin läuft in den Formeln des Stapels nichts über (höchstens zwei
#: Produkte vor einer Normierung); größere Zahlen gehen den skalaren Weg.
_BATCH_MAGNITUDE: Final = 1e100
_CORNER_UV: Final = np.array(_CORNERS, dtype=np.float64)


def _up_array(value: np.ndarray) -> np.ndarray:
    """Mindestens ein ULP nach oben — mit Fließkomma-Arithmetik statt ``np.nextafter``.

    ``np.nextafter`` kostet je Element das Dreißigfache einer Multiplikation
    (gemessen 21.09.2026: 0,58 gegen 0,017 ms an 86 400 Werten). Der Schritt
    ``|x|·2⁻⁵¹`` ist für jedes endliche ``x ≠ 0`` mindestens ein ULP und
    höchstens zwei — für ``x`` in ``[2ᵉ, 2ᵉ⁺¹)`` ist das ULP ``2ᵉ⁻⁵²``, der
    Schritt liegt zwischen ``2ᵉ⁻⁵¹`` und ``2ᵉ⁻⁵⁰`` —, und eine Summe, die um
    mindestens ein ULP über ``x`` liegt, rundet nie unter ``x`` plus ein ULP,
    denn das ist selbst ein Float. Die kleinste Denormalzahl daneben hebt
    auch die Null. Die Klammer wird damit um höchstens ein ULP breiter als
    mit ``nextafter``; ``tests/test_surface_deviation.py`` misst die Breite.

    Überlauf gibt es hier nicht: Der Stapel rechnet nur, was unter
    ``_BATCH_MAGNITUDE`` liegt, und ``nan`` — aus einem Quotienten durch eine
    Klammer um null, den ``__truediv__`` vermerkt — überlebt jedes Minimum
    und Maximum bis ins Ergebnis.
    """
    out = np.abs(value)
    out *= _ULP_STEP
    out += _SMALLEST
    out += value
    return out


def _down_array(value: np.ndarray) -> np.ndarray:
    out = np.abs(value)
    out *= _ULP_STEP
    out += _SMALLEST
    np.subtract(value, out, out=out)
    return out


def _exact_square(value: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``value²`` exakt als Summe ``product + error`` (Dekker), ohne Über- und Unterlauf."""
    product = value * value
    scaled = _SPLIT * value
    high = scaled - (scaled - value)
    low = value - high
    error = ((high * high - product) + 2.0 * high * low) + low * low
    return product, error


def _root_certified(result: np.ndarray, value: np.ndarray, upper: bool) -> np.ndarray:
    """Ob ``result²`` exakt auf der verlangten Seite von ``value`` liegt."""
    product, error = _exact_square(result)
    representable = (product == 0.0) | (product >= _EXACT_PRODUCT_FLOOR)
    if upper:
        ok = (product > value) | ((product == value) & (error >= 0.0))
    else:
        ok = (product < value) | ((product == value) & (error <= 0.0))
    return np.asarray(ok & representable, dtype=bool)


class _Bands:
    """Gerichtete Zahlenklammern als Arrays — dieselbe Zusage wie ``_I`` für viele Dreiecke.

    Jede Rechenart trägt die Rundungsregel ihres skalaren Zwillings. Was
    dabei nicht endlich bleibt, bleibt es bis zum Ergebnis — NumPy trägt
    ``inf`` und ``nan`` durch jede Summe, jedes Produkt und jedes Minimum
    weiter, und die Fallunterscheidungen unten sind so geschrieben, dass keine
    davon einen solchen Wert verschluckt. Was ``_I`` als Ausnahme wirft — ein
    Quotient durch eine Klammer um null, eine unbestätigte Wurzel —, wird je
    Dreieck vermerkt (``bad``): Die erste Achse jedes Arrays ist das Dreieck,
    und diese Dreiecke rechnet der skalare Weg nach.
    """

    def __init__(self, count: int) -> None:
        self.count = count
        self.bad = np.zeros(count, dtype=bool)

    def flag(self, invalid: np.ndarray) -> None:
        if not np.any(invalid):
            return
        if invalid.ndim == 0 or invalid.shape[0] != self.count:
            self.bad[:] = True
            return
        self.bad |= invalid.reshape(invalid.shape[0], -1).any(axis=1)

    def number(self, value: np.ndarray | float) -> _A:
        array = np.asarray(value, dtype=np.float64)
        return _A(self, array, array, True)

    def root(self, value: np.ndarray, upper: bool) -> np.ndarray:
        """Wie ``_sqrt_bound``: den Vorschlag durch exaktes Quadrieren bestätigen.

        Unterhalb von ``_EXACT_PRODUCT_FLOOR`` ist das Quadrat nicht mehr exakt
        darstellbar — dort ist ``2⁻⁴⁸⁴`` die Obergrenze, denn sein Quadrat ist
        genau die Schwelle, und null die Untergrenze. Eine Klammer um null
        hebt ihren oberen Rand um ein ULP auf eine Denormalzahl, und deren
        Wurzel muss genauso bestätigt sein wie jede andere.
        """
        result = np.sqrt(value)
        for _ in range(8):
            certified = _root_certified(result, value, upper)
            if certified.all():
                return result
            step = _up_array(result) if upper else np.maximum(0.0, _down_array(result))
            result = np.where(certified, result, step)
        certified = _root_certified(result, value, upper)
        if upper:
            small = value <= _EXACT_PRODUCT_FLOOR
            result = np.where(certified, result, np.where(small, _TINY_ROOT, result))
            certified |= small
        else:
            result = np.where(certified, result, 0.0)
            certified = certified | (value >= 0.0)
        self.flag(~certified)
        return result


class _A:
    """Ein Array von Klammern ``[lo, hi]``; die Operatoren lesen wie an ``_I``.

    ``exact`` heißt: beide Ränder sind dieselbe Zahl — ein Eckpunkt, ein
    Parameter, eine Konstante. Ein Produkt mit einer exakten Zahl braucht zwei
    Produkte statt vier, und Schnitte und eingefügte Achsen erhalten die
    Eigenschaft; jede Rechnung nimmt sie.
    """

    __slots__ = ("bands", "exact", "hi", "lo")

    def __init__(self, bands: _Bands, lo: np.ndarray, hi: np.ndarray, exact: bool = False) -> None:
        self.bands = bands
        self.lo = lo
        self.hi = hi
        self.exact = exact

    def _other(self, value: _A | float) -> _A:
        if isinstance(value, _A):
            return value
        return self.bands.number(value)

    def __getitem__(self, key: Any) -> _A:
        return _A(self.bands, self.lo[key], self.hi[key], self.exact)

    def __add__(self, other: _A | float) -> _A:
        other = self._other(other)
        return _A(self.bands, _down_array(self.lo + other.lo), _up_array(self.hi + other.hi))

    def __neg__(self) -> _A:
        return _A(self.bands, -self.hi, -self.lo)

    def __sub__(self, other: _A | float) -> _A:
        return self + -self._other(other)

    def __mul__(self, other: _A | float) -> _A:
        other = self._other(other)
        if other.exact:
            first, second = self.lo * other.lo, self.hi * other.lo
            low, high = np.minimum(first, second), np.maximum(first, second)
        elif self.exact:
            first, second = self.lo * other.lo, self.lo * other.hi
            low, high = np.minimum(first, second), np.maximum(first, second)
        else:
            first, second = self.lo * other.lo, self.lo * other.hi
            third, fourth = self.hi * other.lo, self.hi * other.hi
            low = np.minimum(np.minimum(first, second), np.minimum(third, fourth))
            high = np.maximum(np.maximum(first, second), np.maximum(third, fourth))
        return _A(self.bands, _down_array(low), _up_array(high))

    def __truediv__(self, other: _A | float) -> _A:
        other = self._other(other)
        through_zero = (other.lo <= 0.0) & (other.hi >= 0.0)
        self.bands.flag(np.broadcast_to(through_zero, np.broadcast(self.lo, other.lo).shape))
        safe_lo = np.where(through_zero, 1.0, other.lo)
        if other.exact:
            first, second = self.lo / safe_lo, self.hi / safe_lo
            low, high = np.minimum(first, second), np.maximum(first, second)
        else:
            safe_hi = np.where(through_zero, 1.0, other.hi)
            first, second = self.lo / safe_lo, self.lo / safe_hi
            third, fourth = self.hi / safe_lo, self.hi / safe_hi
            low = np.minimum(np.minimum(first, second), np.minimum(third, fourth))
            high = np.maximum(np.maximum(first, second), np.maximum(third, fourth))
        return _A(self.bands, _down_array(low), _up_array(high))

    def square(self) -> _A:
        straddles = (self.lo <= 0.0) & (self.hi >= 0.0)
        first, second = self.lo * self.lo, self.hi * self.hi
        low = np.where(straddles, 0.0, np.minimum(first, second))
        return _A(
            self.bands, np.maximum(0.0, _down_array(low)), _up_array(np.maximum(first, second))
        )

    def absolute(self) -> _A:
        straddles = (self.lo <= 0.0) & (self.hi >= 0.0)
        first, second = np.abs(self.lo), np.abs(self.hi)
        return _A(
            self.bands,
            np.where(straddles, 0.0, np.minimum(first, second)),
            np.maximum(first, second),
        )

    def sqrt(self) -> _A:
        self.bands.flag(self.hi < 0.0)
        return _A(
            self.bands,
            self.bands.root(np.maximum(0.0, self.lo), False),
            self.bands.root(np.maximum(0.0, self.hi), True),
        )

    @property
    def middle(self) -> np.ndarray:
        return self.lo / 2.0 + self.hi / 2.0

    def negative_part(self) -> _A:
        """``[min(lo, 0), min(hi, 0)]`` — der Anteil hinter der Kegelspitze."""
        return _A(self.bands, np.minimum(self.lo, 0.0), np.minimum(self.hi, 0.0))

    def unsqueeze(self, axis: int) -> _A:
        """Eine Achse einfügen, damit Parameter je Dreieck gegen Proben je Dreieck laufen."""
        return _A(
            self.bands, np.expand_dims(self.lo, axis), np.expand_dims(self.hi, axis), self.exact
        )


def _a_dot(a: _A, b: _A) -> _A:
    return a[..., 0, :] * b[..., 0, :] + a[..., 1, :] * b[..., 1, :] + a[..., 2, :] * b[..., 2, :]


def _a_cross(a: _A, b: _A) -> _A:
    parts = (
        a[..., 1, :] * b[..., 2, :] - a[..., 2, :] * b[..., 1, :],
        a[..., 2, :] * b[..., 0, :] - a[..., 0, :] * b[..., 2, :],
        a[..., 0, :] * b[..., 1, :] - a[..., 1, :] * b[..., 0, :],
    )
    return _A(
        a.bands,
        np.stack([part.lo for part in parts], axis=-2),
        np.stack([part.hi for part in parts], axis=-2),
    )


def _a_norm(vector: _A) -> _A:
    """Wie ``_norm``: erst durch die größte Komponente teilen, dann Wurzel, dann zurück."""
    bands = vector.bands
    magnitude = vector.absolute().hi.max(axis=-2)
    # ``nan`` muss den Weg zum Ergebnis behalten: Nur eine exakte Null wird
    # zur Null, alles andere rechnet weiter.
    zero = magnitude == 0.0
    safe = np.where(zero, 1.0, magnitude)
    divided = vector / bands.number(safe).unsqueeze(-2)
    squares = divided.square()
    summed = squares[..., 0, :] + squares[..., 1, :] + squares[..., 2, :]
    result = summed.sqrt() * bands.number(safe)
    return _A(
        bands,
        np.where(zero, 0.0, np.maximum(0.0, result.lo)),
        np.where(zero, 0.0, result.hi),
    )


def _legal_uv_array(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Wie ``_legal_uv``: jeder Vorschlag wird ein echter Punkt, die Summe steigt nie über eins."""
    finite = np.isfinite(u) & np.isfinite(v)
    u = np.where(finite, np.clip(u, 0.0, 1.0), 0.0)
    v = np.where(finite, np.clip(v, 0.0, 1.0), 0.0)
    remaining = 1.0 - u
    # Bei u >= 1/2 ist 1 - u exakt (Sterbenz), sonst genau dann, wenn die
    # Probe zurück auf u führt; andernfalls liegt der nächstkleinere Float
    # sicher unter der wahren Differenz.
    exact = (remaining < 0.5) | ((1.0 - remaining) == u)
    ceiling = np.where(exact, remaining, np.nextafter(remaining, -np.inf))
    v = np.maximum(0.0, np.minimum(v, ceiling))
    return np.stack([u, v])


def _edge_uv_array(first: int, second: int, value: np.ndarray) -> np.ndarray:
    a, b = _CORNER_UV[first], _CORNER_UV[second]
    return _legal_uv_array(a[0] + value * (b[0] - a[0]), a[1] + value * (b[1] - a[1]))


def _rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Skalarprodukt über die Komponentenachse — die vorletzte."""
    return np.asarray(np.einsum("...cn,...cn->...n", a, b))


def _roots_in_unit(coefficients: np.ndarray) -> np.ndarray:
    """Die reellen Wurzeln in ``(0, 1)`` je Spalte, aufsteigend; fehlende ``nan``.

    ``coefficients`` steht aufsteigend nach Grad, eine Spalte je Dreieck. Die
    Wurzeln kommen aus den Eigenwerten der Begleitmatrix, denn die nimmt
    ``np.linalg.eigvals`` als Stapel; ``np.roots`` müsste je Spalte einmal
    laufen. Wo der führende Koeffizient verschwindet, fällt der Grad — solche
    Spalten bleiben leer, und eine fehlende Teilstelle kostet nur Schärfe,
    nie Gültigkeit (:func:`_torus_breakpoints`).
    """
    degree, count = coefficients.shape[0] - 1, coefficients.shape[1]
    scale = np.abs(coefficients).max(axis=0)
    finite = np.isfinite(coefficients).all(axis=0) & (scale > 0.0)
    normed = coefficients / np.where(finite, scale, 1.0)
    leading = normed[degree]
    steady = finite & (np.abs(leading) > 1e-12)
    values = np.full((count, degree), np.nan)
    if steady.any():
        companion = np.zeros((int(steady.sum()), degree, degree))
        companion[:, 1:, :-1] = np.eye(degree - 1)
        companion[:, :, -1] = -(normed[:degree, steady] / leading[steady]).T
        eigen = np.linalg.eigvals(companion)
        real = np.where(
            np.abs(eigen.imag) <= 1e-9 * np.maximum(1.0, np.abs(eigen.real)), eigen.real, np.nan
        )
        values[steady] = np.sort(np.where((real > 0.0) & (real < 1.0), real, np.nan), axis=1)
    return values.T


class _Batch:
    """``_Facet`` und ``_tighten`` für alle Dreiecke einer Trägerart zugleich.

    ``owner`` nennt je Dreieck seinen Träger; Ursprung, Achse, Radien und
    Kegelwinkel liegen deshalb als Arrays je Dreieck vor. **Das Dreieck ist
    die letzte Achse**: Vektoren haben die Gestalt ``(…, 3, n)``, Skalare
    ``(…, n)``. So läuft jede Operation über zusammenhängende Zeilen der
    Länge n — mit ``(n, 3)`` war der innere Schleifenlauf drei Elemente lang,
    und ein Produkt kostete das Dreißigfache (gemessen 21.09.2026).
    """

    def __init__(
        self, kind: str, surfaces: Sequence[_Surface], owner: np.ndarray, triangles: np.ndarray
    ) -> None:
        self.kind = kind
        self.count = len(triangles)
        bands = self.bands = _Bands(self.count)

        def scalars(values: Sequence[_I]) -> _A:
            lo = np.array([entry.lo for entry in values])[owner]
            hi = np.array([entry.hi for entry in values])[owner]
            return _A(bands, lo, hi)

        def vectors(values: Sequence[Sequence[_I]]) -> _A:
            lo = np.array([[entry.lo for entry in row] for row in values])[owner]
            hi = np.array([[entry.hi for entry in row] for row in values])[owner]
            return _A(bands, np.ascontiguousarray(lo.T), np.ascontiguousarray(hi.T))

        self.origin = vectors([surface.origin for surface in surfaces])
        self.axis = vectors([surface.axis for surface in surfaces])
        self.axis_size = scalars([surface.axis_size for surface in surfaces])
        self.radius = scalars([surface.radius for surface in surfaces])
        self.tube_radius = scalars([surface.tube_radius for surface in surfaces])
        self.sine = scalars([surface.sine for surface in surfaces])
        self.cosine = scalars([surface.cosine for surface in surfaces])
        corners = np.ascontiguousarray(np.transpose(triangles, (1, 2, 0)))
        self.points = bands.number(corners) - self.origin
        self.edges = (self.points[1] - self.points[0], self.points[2] - self.points[0])
        # Die Probentafel: uv je Probe und Dreieck, Gültigkeit, Abstandsklammer.
        self.sample_uv: list[np.ndarray] = []
        self.sample_valid: list[np.ndarray] = []
        self.sample_value: list[_A] = []
        self.upper = np.full(self.count, np.inf)
        self._initial()

    # --- Proben ------------------------------------------------------------------

    def point(self, uv: np.ndarray, corner: int | None = None) -> _A:
        if corner is not None:
            return self.points[corner]
        u = self.bands.number(uv[0])
        v = self.bands.number(uv[1])
        return self.points[0] + self.edges[0] * u + self.edges[1] * v

    def sample(
        self,
        uv: np.ndarray,
        valid: np.ndarray | None = None,
        corner: int | None = None,
        *,
        given: _A | None = None,
    ) -> _A:
        """Eine Probe je Dreieck: ihr Abstand wird gemerkt, der beste wird der Zeuge.

        ``given`` übernimmt einen bereits gerechneten Abstand. Die
        Torusverfeinerung hat ihn für jede Stückgrenze ohnehin in der Hand;
        ihn hier noch einmal zu rechnen verdoppelte den teuersten Teil.
        """
        mask = np.ones(self.count, dtype=bool) if valid is None else valid
        uv = np.where(mask, _legal_uv_array(uv[0], uv[1]), 0.0)
        value = self.distance(self.point(uv, corner)) if given is None else given
        self.sample_uv.append(uv)
        self.sample_valid.append(mask)
        self.sample_value.append(value)
        return value

    def _initial(self) -> None:
        """Wie ``_Facet.__init__``: drei Ecken, eine Mitte, und die grobe globale Klammer."""
        quarter = np.full((2, self.count), 0.25)
        for corner in (0, 1, 2, None):
            uv = (
                np.broadcast_to(_CORNER_UV[corner][:, None], (2, self.count)).copy()
                if corner is not None
                else quarter
            )
            value = self.sample(uv, corner=corner)
            position = self.point(uv, corner)
            # Die Summe der Beträge ist nie kleiner als die Länge: eine gültige
            # Obergrenze ohne Wurzel, und die grobe Anfangsklammer trägt bei
            # keiner Trägerart das Ergebnis — sie hält nur den Rückfall endlich.
            around = (self.points - position).absolute().hi
            radius = _up_array(_up_array(around[:, 0] + around[:, 1]) + around[:, 2])
            self.upper = np.minimum(self.upper, _up_array(value.hi + radius.max(axis=0)))

    # --- Abstände ----------------------------------------------------------------

    def axial(self, point: _A) -> _A:
        return _a_dot(point, self.axis) / self.axis_size

    def radial(self, point: _A) -> _A:
        return _a_cross(point, self.axis) * (self.bands.number(1.0) / self.axis_size)

    def distance(self, point: _A) -> _A:
        """Wie ``_Surface.distance``, für ``(…, 3, n)``-Punkte."""
        kind = self.kind
        if kind == "sphere":
            return (_a_norm(point) - self.radius).absolute()
        z = self.axial(point)
        if kind == "plane":
            return z.absolute()
        rho = _a_norm(self.radial(point))
        if kind == "cylinder":
            return (rho - self.radius).absolute()
        if kind == "cone":
            h = self.sine * z - self.cosine * rho
            t = self.sine * rho + self.cosine * z
            return (h.square() + t.negative_part().square()).sqrt()
        return (((rho - self.radius).square() + z.square()).sqrt() - self.tube_radius).absolute()

    # --- Vorschläge --------------------------------------------------------------

    def closest_proposals(self, points: _A) -> list[tuple[np.ndarray, np.ndarray]]:
        """Wie ``_closest_proposals``: Ecken, Lotfußpunkte der Kanten, Fußpunkt der Ebene."""
        count = self.count
        proposals: list[tuple[np.ndarray, np.ndarray]] = [
            (
                np.broadcast_to(_CORNER_UV[index][:, None], (2, count)).copy(),
                np.ones(count, dtype=bool),
            )
            for index in range(3)
        ]
        floats = points.middle
        scale = np.abs(floats).max(axis=(0, 1))
        scaled_ok = scale > 0.0
        scaled = floats / np.where(scaled_ok, scale, 1.0)
        for first, second in _EDGES:
            a, b = scaled[first], scaled[second]
            edge = b - a
            size = _rows(edge, edge)
            ok = scaled_ok & (size > 0.0)
            value = -_rows(a, edge) / np.where(ok, size, 1.0)
            value = np.clip(np.where(ok, value, 0.0), 0.0, 1.0)
            proposals.append((_edge_uv_array(first, second, value), ok))
        projected, ok = self.barycentric(floats, np.zeros((3, count)))
        proposals.append((projected, ok & scaled_ok))
        return proposals

    @staticmethod
    def barycentric(points: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Wie ``_barycentric``: nur ein Probenvorschlag, keine obere Schranke."""
        vectors = points - target
        scale = np.abs(vectors).max(axis=(0, 1))
        ok = (scale > 0.0) & np.isfinite(scale)
        a, b, c = vectors / np.where(ok, scale, 1.0)
        e, f = b - a, c - a
        ee, ef, ff = _rows(e, e), _rows(e, f), _rows(f, f)
        ae, af = _rows(a, e), _rows(a, f)
        determinant = ee * ff - ef * ef
        ok &= determinant > 0.0
        safe = np.where(ok, determinant, 1.0)
        return _legal_uv_array((af * ef - ae * ff) / safe, (ae * ef - af * ee) / safe), ok

    def affine(self, points: _A, uv: np.ndarray) -> _A:
        u = self.bands.number(uv[0])
        v = self.bands.number(uv[1])
        return points[0] + (points[1] - points[0]) * u + (points[2] - points[0]) * v

    def support_radius(self, points: _A, direction: np.ndarray) -> np.ndarray:
        """Wie ``_support_radius``: jede Richtung stützt eine gültige Ebene zum Ursprung."""
        vector = self.bands.number(direction)
        size = _a_norm(vector)
        # Nicht ``size.lo > 0``: Ein ``nan`` muss den Weg ins Ergebnis behalten.
        useless = size.lo <= 0.0
        safe = _A(self.bands, np.where(useless, 1.0, size.lo), np.where(useless, 1.0, size.hi))
        ratio = _a_dot(points, vector) / safe
        return np.where(useless, 0.0, np.maximum(0.0, ratio.lo.min(axis=0)))

    def radius_range(self, points: _A) -> tuple[_A, np.ndarray]:
        """Wie ``_radius_range``: Stützradius nach unten, Eckennorm nach oben, nächste Probe."""
        lower = np.zeros(self.count)
        closest = np.zeros((2, self.count))
        minimum = np.full(self.count, np.inf)
        for uv, valid in self.closest_proposals(points):
            self.sample(uv, valid)
            point = self.affine(points, uv)
            size = _a_norm(point)
            better = valid & (size.hi < minimum)
            minimum = np.where(better, size.hi, minimum)
            closest = np.where(better, uv, closest)
            support = self.support_radius(points, point.middle)
            lower = np.maximum(lower, np.where(valid, support, 0.0))
        upper = _a_norm(points).hi.max(axis=0)
        return _A(self.bands, lower, upper), closest

    def axis_proposal(self) -> tuple[np.ndarray, np.ndarray]:
        """Der Achsentreffer im Dreieck als Probe — hier nur Zeuge, keine Schranke."""
        e1, e2 = self.edges[0].middle, self.edges[1].middle
        normal = np.cross(e1, e2, axis=0)
        axis = self.axis.middle
        denominator = _rows(normal, axis)
        ok = np.any(normal != 0.0, axis=0) & (denominator != 0.0)
        first = self.points[0].middle
        height = _rows(normal, first)
        point = axis * (height / np.where(ok, denominator, 1.0))
        relative = point - first
        aa, ab, bb = _rows(e1, e1), _rows(e1, e2), _rows(e2, e2)
        ea, eb = _rows(relative, e1), _rows(relative, e2)
        determinant = aa * bb - ab * ab
        ok &= determinant > 0.0
        safe = np.where(ok, determinant, 1.0)
        u, v = (ea * bb - eb * ab) / safe, (eb * aa - ea * ab) / safe
        ok &= (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0)
        return _legal_uv_array(u, v), ok

    # --- Je Trägerart --------------------------------------------------------------

    def tighten(self) -> None:
        kind = self.kind
        if kind == "plane":
            corners = np.stack([value.hi for value in self.sample_value[:3]])
            self.upper = np.minimum(self.upper, corners.max(axis=0))
            return
        radial = self.points if kind == "sphere" else self.radial(self.points)
        radius, closest = self.radius_range(radial)
        if kind in {"sphere", "cylinder"}:
            self.upper = np.minimum(self.upper, (radius - self.radius).absolute().hi)
        elif kind == "cone":
            self.cone(radial, closest)
        else:
            self.torus(radial, radius, closest)

    def cone(self, radial: _A, closest: np.ndarray) -> None:
        """Wie ``_cone``: konkave Stützebenen umfassen H global, Kandidaten liefern die Zeugen."""
        count = self.count
        z = self.axial(self.points)
        q = radial.middle
        axial = z.middle
        sine, cosine = self.sine.middle, self.cosine.middle
        for first, second in _EDGES:
            p, v = q[first], q[second] - q[first]
            a, b = _rows(v, v), _rows(p, v)
            ok = a > 0.0
            safe_a = np.where(ok, a, 1.0)
            u0 = -b / safe_a
            self.sample(_edge_uv_array(first, second, np.clip(np.where(ok, u0, 0.0), 0.0, 1.0)), ok)
            cross = np.cross(p, v, axis=0)
            delta = _rows(cross, cross)
            k = (axial[second] - axial[first]) * sine / cosine
            steep = ok & (a > k * k)
            denominator = np.where(steep, safe_a * safe_a * (safe_a - k * k), 1.0)
            root = u0 + k * np.sqrt(np.maximum(0.0, delta / denominator))
            inside = steep & (root >= 0.0) & (root <= 1.0)
            self.sample(_edge_uv_array(first, second, np.where(inside, root, 0.0)), inside)
        axis_uv, axis_ok = self.axis_proposal()
        self.sample(axis_uv, axis_ok)
        directions: list[tuple[np.ndarray, np.ndarray]] = [
            (self.affine(radial, uv).middle, valid)
            for uv, valid in zip(self.sample_uv, self.sample_valid, strict=True)
        ]
        directions.append((np.zeros((3, count)), np.ones(count, dtype=bool)))
        # Am Achsenmaximum darf die Norm jeden Untergradienten aus der Einheitskugel
        # haben. Die Schnittpunkte der drei linearen Stützbedingungen liefern die
        # nötigen Vorschläge, ihre Zulässigkeit wird durch Normieren hergestellt.
        best_z = self.axial(self.point(closest)).middle
        slope = sine / cosine
        offsets = slope * (axial - best_z)
        for first, second in _EDGES:
            left_vector, right_vector = q[first], q[second]
            aa = _rows(left_vector, left_vector)
            ab = _rows(left_vector, right_vector)
            bb = _rows(right_vector, right_vector)
            ok = aa > 0.0
            directions.append(((offsets[first] / np.where(ok, aa, 1.0)) * left_vector, ok))
            determinant = aa * bb - ab * ab
            ok = determinant > 0.0
            safe = np.where(ok, determinant, 1.0)
            left = (offsets[first] * bb - offsets[second] * ab) / safe
            right = (offsets[second] * aa - offsets[first] * ab) / safe
            directions.append((left * left_vector + right * right_vector, ok))
        h_upper = np.full(count, np.inf)
        for direction, valid in directions:
            valid = valid & np.isfinite(direction).all(axis=0)
            vector = self.bands.number(np.where(valid, direction, 0.0))
            size = _a_norm(vector)
            # Auch die mathematisch normierte Richtung wird als Klammer gerechnet.
            scale = _A(self.bands, np.maximum(1.0, size.lo), np.maximum(1.0, size.hi))
            unit = vector * (self.bands.number(1.0) / scale)
            projected = _a_dot(radial, unit)
            bound = (self.sine * z - self.cosine * projected).hi.max(axis=0)
            h_upper = np.where(valid, np.minimum(h_upper, bound), h_upper)
        rho = _a_norm(radial)
        h = self.sine * z - self.cosine * rho
        t = self.sine * rho + self.cosine * z
        outside = (h.negative_part().square() + t.negative_part().square()).sqrt().hi.max(axis=0)
        self.upper = np.minimum(self.upper, np.maximum(0.0, np.maximum(outside, h_upper)))

    def torus(self, radial: _A, radius: _A, closest: np.ndarray) -> None:
        """Wie ``_torus`` vor der Verfeinerung: Ringzeugen und die Rechteckklammer."""
        start = self.affine(radial, closest).middle
        ring = self.radius.middle
        corners = radial.middle
        for index in range(3):
            delta = corners[index] - start
            a, b = _rows(delta, delta), _rows(start, delta)
            c = _rows(start, start) - ring * ring
            discriminant = b * b - a * c
            ok = (a > 0.0) & (discriminant >= 0.0)
            root = np.sqrt(np.maximum(0.0, discriminant))
            for sign in (-1.0, 1.0):
                value = (-b + sign * root) / np.where(ok, a, 1.0)
                inside = ok & (value >= 0.0) & (value <= 1.0)
                corner_uv = _CORNER_UV[index]
                uv = _legal_uv_array(
                    closest[0] + value * (corner_uv[0] - closest[0]),
                    closest[1] + value * (corner_uv[1] - closest[1]),
                )
                self.sample(uv, inside)
        heights = self.axial(self.points)
        height = _A(self.bands, heights.lo.min(axis=0), heights.hi.max(axis=0))
        # Dies ist auch für fast horizontale Ebenen gültig, ohne einen Winkel auf
        # null zu setzen: der ganze tatsächliche Höhenbereich bleibt enthalten.
        rectangle = ((radius - self.radius).square() + height.square()).sqrt()
        self.upper = np.minimum(self.upper, (rectangle - self.tube_radius).absolute().hi)

    # --- Torus: dieselbe Verfeinerung wie skalar, für alle zugleich -----------------

    def torus_refine(self) -> np.ndarray:
        """Innenkandidaten und Kantenstücke — was :func:`_torus` je Dreieck tut.

        **Der Grund steht in der Zeit.** Der skalare Weg braucht je
        Torusdreieck rund vier Millisekunden; eine Analysekarte mit 2 000
        Dreiecken auf einer Verrundung stand damit dreißig Sekunden
        (gemessen am 22.09.2026, RM-202). Dieselbe Rechnung über alle
        Dreiecke zugleich kostet an 1 024 Dreiecken 0,11 s — Faktor 43, bei
        Zahl für Zahl demselben Ergebnis.

        Was der Stapel **nicht** kann, lässt er stehen: Trifft die Achse das
        Dreieck, braucht die Kandidatenmenge exakte Bruchrechnung
        (:func:`_axis_candidates`), und dann bleibt ``upper`` unberührt — die
        Rechteckklammer trägt weiter, und der skalare Weg rechnet nach.
        Zurück kommt genau die Maske der Dreiecke, die er zu Ende gerechnet
        hat.
        """
        best, sure = self._torus_interior()
        if not sure.any():
            return sure
        edges = np.full(self.count, -np.inf)
        for first, second in _EDGES:
            stops = self._torus_breakpoints(first, second)
            # Fehlende Wurzeln stehen als ``nan`` am Ende; als rechter Rand
            # gelesen werden daraus leere Stücke, und die Vereinigung bleibt
            # das ganze Intervall.
            filled = np.where(np.isfinite(stops), stops, 1.0)
            low = np.vstack([np.zeros((1, self.count)), filled])
            high = np.vstack([filled, np.ones((1, self.count))])
            for _turn in range(_TORUS_HALVINGS):
                centre = low / 2.0 + high / 2.0
                low, high = np.vstack([low, centre]), np.vstack([centre, high])
            bound = self._torus_edge_upper(first, second, low, high)
            edges = np.maximum(edges, np.where(low < high, bound, -np.inf).max(axis=0))
        refined = np.maximum(best, edges)
        usable = np.asarray(sure & np.isfinite(refined))
        self.upper = np.where(usable, np.minimum(self.upper, refined), self.upper)
        return usable

    def _torus_interior(self) -> tuple[np.ndarray, np.ndarray]:
        """Wie :func:`_torus_interior` ohne den Achsenfall: Schranke und Sicherheit."""
        bands = self.bands
        normal = _a_cross(self.edges[0], self.edges[1])
        size = _a_norm(normal)
        steady = size.lo > 0.0
        safe_size = _A(bands, np.where(steady, size.lo, 1.0), np.where(steady, size.hi, 1.0))
        unit = normal / safe_size.unsqueeze(-2)
        axis = self.axis / self.axis_size.unsqueeze(-2)
        projected = unit - axis * _a_dot(unit, axis).unsqueeze(-2)
        across = _a_norm(projected)
        steady = steady & (across.lo > 0.0)
        safe_across = _A(bands, np.where(steady, across.lo, 1.0), np.where(steady, across.hi, 1.0))
        radial = projected / safe_across.unsqueeze(-2)
        side = _a_cross(axis, radial)
        height = _a_dot(unit, self.points[0])

        best = np.full(self.count, -np.inf)
        for sign in (-1.0, 1.0):
            offset = height - safe_across * self.radius * sign
            point = radial * (self.radius * sign).unsqueeze(-2) + unit * offset.unsqueeze(-2)
            # Die Meridianhalbebene ist Teil der analytischen Kandidatenbedingung.
            meridian = (_a_dot(point, radial) * sign).hi > 0.0
            bound, inside = self._candidate_upper(point, normal)
            best = np.where(steady & meridian & inside, np.maximum(best, bound), best)

        along = height / safe_across
        square = self.radius.square() - along.square()
        root = _A(bands, np.maximum(0.0, square.lo), np.maximum(0.0, square.hi)).sqrt()
        reachable = square.hi >= 0.0
        for sign in (-1.0, 1.0):
            point = radial * along.unsqueeze(-2) + side * (root * sign).unsqueeze(-2)
            bound, inside = self._candidate_upper(point, normal)
            best = np.where(steady & reachable & inside, np.maximum(best, bound), best)

        return best, steady & ~self._axis_may_hit(normal)

    def _candidate_upper(self, point: _A, normal: _A) -> tuple[np.ndarray, np.ndarray]:
        """Wie :func:`_candidate_upper`: Schranke und ob der Punkt beweisbar innen liegt.

        Und wie dort wird der Punkt zur **Probe**: Er liegt nah am Maximum,
        also hebt er die Untergrenze — und erst beide Ränder zusammen machen
        aus einer Schranke eine geschlossene Klammer.
        """
        inside = np.ones(point.lo.shape[-1], dtype=bool)
        for first, second in _EDGES:
            edge = self.points[second] - self.points[first]
            sign = _a_dot(_a_cross(edge, point - self.points[first]), normal)
            inside = inside & (sign.hi >= 0.0)
        proposal = self._barycentric(point)
        if proposal is not None:
            self.sample(proposal, inside)
        return self.distance(point).hi, inside

    def _barycentric(self, target: _A) -> np.ndarray | None:
        """Wie :func:`_barycentric`: ein Probenvorschlag, keine Schranke."""
        points = self.points.middle - target.middle
        scale = np.abs(points).max(axis=(0, 1))
        good = (scale > 0.0) & np.isfinite(scale)
        if not good.any():
            return None
        scaled = points / np.where(good, scale, 1.0)
        a, b, c = scaled[0], scaled[1], scaled[2]
        e, f = b - a, c - a
        ee, ef, ff = _rows(e, e), _rows(e, f), _rows(f, f)
        ae, af = _rows(a, e), _rows(a, f)
        determinant = ee * ff - ef * ef
        usable = good & (determinant > 0.0)
        safe = np.where(usable, determinant, 1.0)
        u = np.where(usable, (af * ef - ae * ff) / safe, 0.0)
        v = np.where(usable, (ae * ef - af * ee) / safe, 0.0)
        return _legal_uv_array(u, v)

    def _axis_may_hit(self, normal: _A) -> np.ndarray:
        """Ob die Achse das Dreieck treffen könnte — dann rechnet der skalare Weg.

        :func:`_axis_candidates` löst das exakt in Brüchen; hier genügt die
        konservative Frage, und wer unsicher ist, sagt ja.
        """
        axis = self.axis.middle
        flat = normal.middle
        denominator = _rows(flat, axis)
        scale = np.linalg.norm(flat, axis=-2) * np.linalg.norm(axis, axis=-2)
        parallel = np.abs(denominator) <= 1e-12 * np.maximum(scale, 1.0)
        origin = self.points[0].middle
        value = np.where(parallel, 0.0, _rows(flat, origin) / np.where(parallel, 1.0, denominator))
        relative = axis * value[..., None, :] - origin
        first = self.points[1].middle - origin
        second = self.points[2].middle - origin
        aa, ab, bb = _rows(first, first), _rows(first, second), _rows(second, second)
        ea, eb = _rows(relative, first), _rows(relative, second)
        determinant = aa * bb - ab * ab
        good = np.abs(determinant) > 0.0
        safe = np.where(good, determinant, 1.0)
        u = (bb * ea - ab * eb) / safe
        v = (aa * eb - ab * ea) / safe
        margin = 1e-9
        hits = (u >= -margin) & (v >= -margin) & (u + v <= 1.0 + margin)
        return np.asarray(parallel | ~good | hits)

    def _torus_breakpoints(self, first: int, second: int) -> np.ndarray:
        """Bis zu vier Teilstellen je Dreieck, aufsteigend; fehlende sind ``nan``.

        Die Herleitung steht an :func:`_torus_breakpoints`; hier steht sie als
        Koeffizientenfeld, und die Wurzeln kommen aus den Eigenwerten der
        Begleitmatrizen — ``np.linalg.eigvals`` nimmt einen ganzen Stapel,
        ``np.roots`` nur ein Polynom.
        """
        start = self.points[first].middle
        direction = self.points[second].middle - start
        axis = self.axis.middle
        size = np.sqrt(np.maximum(0.0, _rows(axis, axis)))
        axis = axis / np.where(size > 0.0, size, 1.0)[..., None, :]
        ring = self.radius.middle
        m0, m1 = _rows(start, direction), _rows(direction, direction)
        z0, z1 = _rows(start, axis), _rows(direction, axis)
        h0, h1 = m0 - z0 * z1, m1 - z1 * z1
        q0, q1, q2 = _rows(start, start) - z0 * z0, 2.0 * (m0 - z0 * z1), m1 - z1 * z1
        coefficients = np.stack(
            [
                m0 * m0 * q0 - ring * ring * h0 * h0,
                m0 * m0 * q1 + 2.0 * m0 * m1 * q0 - 2.0 * ring * ring * h0 * h1,
                m0 * m0 * q2 + 2.0 * m0 * m1 * q1 + m1 * m1 * q0 - ring * ring * h1 * h1,
                2.0 * m0 * m1 * q2 + m1 * m1 * q1,
                m1 * m1 * q2,
            ]
        )
        return _roots_in_unit(coefficients)

    def _torus_edge_upper(
        self, first: int, second: int, low: np.ndarray, high: np.ndarray
    ) -> np.ndarray:
        """Wie :func:`_edge_upper`, für ein Feld von Kantenstücken ``(k, n)``."""
        bands = self.bands
        start = self.points[first]
        edge = self.points[second] - self.points[first]

        def at(value: np.ndarray) -> _A:
            return start + edge * bands.number(value).unsqueeze(-2)

        middle = low / 2.0 + high / 2.0
        left, right, centre = at(low), at(high), at(middle)
        at_left, at_right = self.distance(left), self.distance(right)
        # Dieselben drei Proben, die der skalare Weg je Stück nimmt: Sie
        # heben die Untergrenze, und ohne sie bliebe die Klammer breit,
        # obwohl die Schranke längst sitzt.
        for share, value in ((low, at_left), (middle, self.distance(centre)), (high, at_right)):
            for row in range(share.shape[0]):
                self.sample(_edge_uv_array(first, second, share[row]), given=value[row])
        half = np.maximum(_up_array(middle - low), _up_array(high - middle))
        length = _a_norm(edge)
        upper = (self.distance(centre) + length * bands.number(half)).hi

        qleft, qright, qedge = self.radial(left), self.radial(right), self.radial(edge)
        base = qleft.middle
        delta = qright.middle - base
        span = _rows(delta, delta)
        parameter = np.where(span > 0.0, -_rows(base, delta) / np.where(span > 0.0, span, 1.0), 0.0)
        # Die Komponentenachse ist die vorletzte; Skalare je Stück brauchen sie.
        direction = base + np.clip(parameter, 0.0, 1.0)[..., None, :] * delta
        reach = np.sqrt(np.maximum(0.0, _rows(direction, direction)))
        positive = reach > 0.0
        unit = direction / np.where(positive, reach, 1.0)[..., None, :]
        support = np.minimum(
            (qleft * bands.number(unit)).lo.sum(axis=-2),
            (qright * bands.number(unit)).lo.sum(axis=-2),
        )
        radial_lower = np.where(positive, np.maximum(0.0, support), 0.0)
        radial_upper = np.maximum(_a_norm(qleft).hi, _a_norm(qright).hi)
        usable = radial_lower > 0.0

        box = _A(bands, np.minimum(left.lo, right.lo), np.maximum(left.hi, right.hi))
        qbox = _A(bands, np.minimum(qleft.lo, qright.lo), np.maximum(qleft.hi, qright.hi))
        rho = _A(
            bands,
            np.where(usable, radial_lower, 1.0),
            np.where(usable, np.maximum(radial_lower, radial_upper), 1.0),
        )
        derivative = (_a_dot(box, edge) - self.radius * _a_dot(qbox, qedge) / rho) * 2.0
        monotone = usable & ((derivative.lo > 0.0) | (derivative.hi < 0.0))
        upper = np.where(monotone, np.minimum(upper, np.maximum(at_left.hi, at_right.hi)), upper)

        cross = _a_norm(_a_cross(qleft, qedge)).square()
        cube = bands.number(np.where(usable, radial_lower, 1.0))
        curvature = length.square() * 2.0 + self.radius * cross * 2.0 / (cube.square() * cube)
        width = bands.number(_up_array(high - low))
        error = curvature * width.square() / 8.0
        fleft, fright = self._torus_square(left), self._torus_square(right)
        frange = _A(
            bands,
            np.maximum(0.0, _down_array(np.minimum(fleft.lo, fright.lo) - error.hi)),
            _up_array(np.maximum(fleft.hi, fright.hi) + error.hi),
        )
        chord = (frange.sqrt() - self.tube_radius).absolute().hi
        return np.where(usable & ~monotone, np.minimum(upper, chord), upper)

    def _torus_square(self, point: _A) -> _A:
        """Wie :func:`_torus_square`: der quadrierte Abstand zum Ringkreis."""
        return (_a_norm(self.radial(point)) - self.radius).square() + self.axial(point).square()

    # --- Ergebnis ------------------------------------------------------------------

    def results(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Untergrenze samt Zeuge aus der Probentafel, Obergrenze aus den Schranken."""
        values = np.stack(
            [
                np.where(valid, value.lo, -np.inf)
                for value, valid in zip(self.sample_value, self.sample_valid, strict=True)
            ]
        )
        best = values.argmax(axis=0)
        everyone = np.arange(self.count)
        lower = np.maximum(0.0, values[best, everyone])
        uv = np.stack(self.sample_uv)[best, :, everyone]
        witness = np.where((lower > 0.0)[:, None], uv, 0.0)
        return lower, self.upper, witness


def _triangle_array(triangles: Iterable[Triangle] | np.ndarray) -> np.ndarray:
    if isinstance(triangles, np.ndarray):
        array = np.asarray(triangles, dtype=np.float64)
    else:
        array = np.asarray(list(triangles), dtype=np.float64)
    if array.size == 0:
        return np.zeros((0, 3, 3))
    if array.ndim != 3 or array.shape[1:] != (3, 3):
        raise ValueError("Dreiecke werden als (n, 3, 3)-Feld aus Ecken erwartet.")
    return array


def _scalar_result(surface: _Surface, triangle: Triangle, epsilon: float) -> FacetDeviation | None:
    """Ein einzelnes Dreieck über die skalaren Klammern — Sonderfälle und Torusverfeinerung."""
    try:
        # Das Budget gehört dem Dreieck, nicht dem Träger (:data:`_MAX_REFINEMENTS`).
        surface.refinements = _MAX_REFINEMENTS
        facet = _Facet(triangle, surface)
        # Eine numerisch offene Kandidatenrechnung löscht keinen
        # bereits gesicherten globalen Ausgangsnachweis.
        with suppress(ArithmeticError):
            _tighten(facet, epsilon)
        # Auch eine überlaufende Lipschitzsumme darf nach offener
        # Verfeinerung nicht als unendliche Ergebnisklammer erscheinen.
        bounds = _I(facet.lower, facet.upper)
    except ArithmeticError:
        return None
    return FacetDeviation(
        bounds.lo, bounds.hi, facet.witness, _up(bounds.hi - bounds.lo) <= epsilon
    )


def _within_batch_magnitude(surface: _Surface) -> bool:
    """Ob Ursprung, Achse und Radien klein genug für den Stapel sind."""
    bounds = [
        *surface.origin,
        *surface.axis,
        surface.axis_size,
        surface.radius,
        surface.tube_radius,
    ]
    return all(max(abs(value.lo), abs(value.hi)) < _BATCH_MAGNITUDE for value in bounds)


def _bounded(
    surfaces: Sequence[_Surface | None],
    owner: np.ndarray,
    triangles: np.ndarray,
    epsilon: float,
    token: CancelToken,
    progress: Callable[[int, int], None] | None,
) -> Iterator[DeviationTable]:
    """Je Block eine Tafel in Reihenfolge; Träger ohne Vorbereitung liefern unbekannt.

    Der Stapel füllt, was er sicher rechnen kann; die übrigen Dreiecke —
    Torus über der Zielbreite, Zahlen über ``_BATCH_MAGNITUDE``, ein
    vermerkter Quotient — rechnet der skalare Weg einzeln nach, mit dem
    Abbruch zwischen je zwei Dreiecken.
    """
    kinds = {surface.patch.kind for surface in surfaces if surface is not None}
    assert len(kinds) <= 1, "ein Stapel je Trägerart"
    kind = next(iter(kinds), "")
    prepared = np.array([surface is not None for surface in surfaces], dtype=bool)
    batchable = np.array(
        [surface is not None and _within_batch_magnitude(surface) for surface in surfaces],
        dtype=bool,
    )
    live = [
        surface
        for surface, ok in zip(surfaces, batchable, strict=True)
        if ok and surface is not None
    ]
    live_index = np.cumsum(batchable) - 1
    total = len(triangles)
    for start in range(0, total, _CHUNK):
        token.raise_if_cancelled()
        chunk = triangles[start : start + _CHUNK]
        chunk_owner = owner[start : start + _CHUNK]
        finite = np.isfinite(chunk).all(axis=(1, 2)) & prepared[chunk_owner]
        batched = (
            finite & (np.abs(chunk).max(axis=(1, 2)) < _BATCH_MAGNITUDE) & batchable[chunk_owner]
        )
        count = len(chunk)
        lower = np.full(count, np.nan)
        upper = np.full(count, np.nan)
        witness = np.zeros((count, 2))
        if batched.any():
            # Der Stapel rechnet alle Dreiecke des Blocks; was er nicht
            # übernehmen darf, steht auf null und wird danach nicht gelesen.
            with np.errstate(all="ignore"):
                batch = _Batch(
                    kind,
                    live,
                    live_index[np.where(batched, chunk_owner, np.flatnonzero(batchable)[0])],
                    np.where(batched[:, None, None], chunk, 0.0),
                )
                token.raise_if_cancelled()
                batch.tighten()
                refined = None
                if kind == "torus":
                    # Die Verfeinerung, die der skalare Weg je Dreieck führt —
                    # hier für alle zugleich (RM-202). Wo sie nicht greift,
                    # bleibt die Rechteckklammer stehen und der Weg darunter
                    # rechnet nach.
                    refined = batch.torus_refine()
                batch_lower, batch_upper, batch_witness = batch.results()
            valid = (
                batched
                & ~batch.bands.bad
                & np.isfinite(batch_lower)
                & np.isfinite(batch_upper)
                & (batch_lower <= batch_upper)
            )
            trusted = valid
            if kind == "torus":
                # **Gefragt wird, ob der Stapel fertig gerechnet hat — nicht,
                # ob die Klammer schon schmal ist.** Bis zum 22.09.2026 stand
                # hier „Breite unter der Zielbreite"; die erreicht am Torus
                # keine endliche Verfeinerung, und deshalb ging **jedes**
                # Dreieck den skalaren Weg: eine Analysekarte mit 2 000
                # Torusdreiecken stand dreißig Sekunden (RM-202). Wo
                # ``torus_refine`` dieselbe Rechnung geführt hat wie der
                # skalare Weg, gibt der keine engere Klammer mehr her.
                assert refined is not None
                trusted = valid & refined
            lower[trusted] = batch_lower[trusted]
            upper[trusted] = batch_upper[trusted]
            witness[trusted] = batch_witness[trusted]
            remaining = finite & ~trusted
        else:
            valid = np.zeros(count, dtype=bool)
            remaining = finite
        for index in np.flatnonzero(remaining):
            token.raise_if_cancelled()
            surface = surfaces[int(chunk_owner[index])]
            assert surface is not None
            # Hier stand die Gegenprobe „das Budget des Trägers ist
            # verbraucht, der skalare Weg gäbe dieselbe Rechteckklammer
            # zurück". Sie stimmte, solange das Budget dem **Träger** gehörte
            # — und war damit die Stelle, an der ein Ring ab dem zweiten
            # Dutzend Dreiecke aufhörte, genauer zu werden (RM-202). Seit das
            # Budget je Dreieck vergeben wird (:data:`_MAX_REFINEMENTS`), gibt
            # es nichts mehr abzukürzen.
            triangle = cast(
                Triangle, tuple(tuple(float(v) for v in point) for point in chunk[index])
            )
            result = _scalar_result(surface, triangle, epsilon)
            if result is not None:
                lower[index], upper[index] = result.lower_mm, result.upper_mm
                witness[index] = result.witness_uv
        token.raise_if_cancelled()
        with np.errstate(invalid="ignore"):
            converged = _up_array(upper - lower) <= epsilon
        yield DeviationTable(lower, upper, witness, converged & np.isfinite(lower))
        if progress is not None:
            progress(min(total, start + _CHUNK), total)


def _checked_epsilon(epsilon_mm: float) -> None:
    if isinstance(epsilon_mm, bool) or not math.isfinite(epsilon_mm) or epsilon_mm <= 0.0:
        raise ValueError("Die numerische Zielbreite muss endlich und positiv sein.")


def deviation_bounds(
    patch: SurfacePatch,
    triangles: Iterable[Triangle] | np.ndarray,
    *,
    epsilon_mm: float,
    cancelled: CancelToken | None = None,
) -> Iterator[FacetDeviation | None]:
    """Genau eine Klammer je Originaldreieck; Verfeinerung ist gemeinsam je Aufruf begrenzt.

    ``None`` bezeichnet ungültige oder nicht endlich einschließbare Daten,
    niemals einen gemessenen Nullabstand. Die Zuordnung zum Patch übernimmt der
    Aufrufer. Ein Abbruch wird durchgereicht, auch während der Vorbereitung.

    Die Dreiecke kommen als Tupel oder als ``(n, 3, 3)``-Feld; gerechnet wird
    für alle zugleich (``_Batch``), und nur ein Torusdreieck über der
    Zielbreite oder ein Dreieck, dessen Rechnung der Stapel nicht übernehmen
    darf, geht den skalaren Weg. Für viele Träger derselben Art nimmt
    `deviation_bounds_grouped` alle in einen Stapel und gibt Tafeln zurück.
    """
    _checked_epsilon(epsilon_mm)
    token = cancelled if cancelled is not None else NeverCancelled()
    token.raise_if_cancelled()
    try:
        surface = _prepare(patch, token)
    except ArithmeticError:
        surface = None
    array = _triangle_array(triangles)
    for table in _bounded(
        [surface], np.zeros(len(array), dtype=np.intp), array, epsilon_mm, token, None
    ):
        known = table.known
        for index in range(len(known)):
            token.raise_if_cancelled()
            yield (
                FacetDeviation(
                    float(table.lower_mm[index]),
                    float(table.upper_mm[index]),
                    (float(table.witness_uv[index, 0]), float(table.witness_uv[index, 1])),
                    bool(table.converged[index]),
                )
                if known[index]
                else None
            )


def deviation_bounds_grouped(
    patches: Sequence[SurfacePatch],
    triangles: Sequence[np.ndarray],
    *,
    epsilon_mm: float,
    cancelled: CancelToken | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[DeviationTable]:
    """Dieselbe Klammer je Dreieck für viele Träger — je Trägerart ein Stapel.

    ``triangles[i]`` sind die Dreiecke des Trägers ``patches[i]`` als
    ``(n, 3, 3)``-Feld; zurück kommt je Träger eine `DeviationTable` in
    derselben Reihenfolge. ``progress`` erfährt nach jedem Block, wie viele
    Dreiecke von allen fertig sind. Das Verfeinerungsbudget des Torus gilt
    weiter je Träger.
    """
    _checked_epsilon(epsilon_mm)
    if len(patches) != len(triangles):
        raise ValueError("Je Träger genau ein Dreiecksfeld.")
    token = cancelled if cancelled is not None else NeverCancelled()
    token.raise_if_cancelled()
    surfaces: list[_Surface | None] = []
    for patch in patches:
        try:
            surfaces.append(_prepare(patch, token))
        except ArithmeticError:
            surfaces.append(None)
    arrays = [_triangle_array(entry) for entry in triangles]
    results: list[DeviationTable | None] = [None] * len(patches)
    total = sum(len(entry) for entry in arrays)
    done = 0
    by_kind: dict[str, list[int]] = {}
    for index, patch in enumerate(patches):
        by_kind.setdefault(patch.kind, []).append(index)
    for members in by_kind.values():
        stacked = np.concatenate([arrays[index] for index in members])
        owner = np.concatenate(
            [
                np.full(len(arrays[index]), position, dtype=np.intp)
                for position, index in enumerate(members)
            ]
        )
        offset = done

        def report(count: int, _total: int, offset: int = offset) -> None:
            if progress is not None:
                progress(offset + count, total)

        tables = list(
            _bounded(
                [surfaces[index] for index in members], owner, stacked, epsilon_mm, token, report
            )
        )
        joined = DeviationTable.joined(tables, len(stacked))
        cursor = 0
        for index in members:
            size = len(arrays[index])
            results[index] = joined.sliced(cursor, cursor + size)
            cursor += size
        done += len(stacked)
    return [table if table is not None else DeviationTable.empty() for table in results]
