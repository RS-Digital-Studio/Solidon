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
from collections.abc import Iterable, Iterator, Sequence
from contextlib import suppress
from dataclasses import dataclass
from fractions import Fraction
from typing import Final, cast

from app.core.scene.cancel import NeverCancelled
from app.core.types import CancelToken, SurfacePatch, Vec3

Triangle = tuple[Vec3, Vec3, Vec3]
_UV = tuple[float, float]

#: Gemeinsame Kantenarbeit je Trägeraufruf, einschließlich der ersten drei Intervalle.
_MAX_REFINEMENTS: Final = 256
_TRIG_TERMS: Final = 32


@dataclass(frozen=True, slots=True)
class FacetDeviation:
    """Maximum in mm; ``lower_mm`` gehört genau zum enthaltenen ``witness_uv``."""

    lower_mm: float
    upper_mm: float
    witness_uv: _UV
    converged: bool


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
        return (
            ((rho - self.radius).square() + z.square()).sqrt().__sub__(self.tube_radius).absolute()
        )


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
    intervals = [
        (first, second, 0.0, 1.0, _edge_upper(facet, first, second, 0.0, 1.0))
        for first, second in _EDGES
    ]
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


def deviation_bounds(
    patch: SurfacePatch,
    triangles: Iterable[Triangle],
    *,
    epsilon_mm: float,
    cancelled: CancelToken | None = None,
) -> Iterator[FacetDeviation | None]:
    """Genau eine Klammer je Originaldreieck; Verfeinerung ist gemeinsam je Aufruf begrenzt.

    ``None`` bezeichnet ungültige oder nicht endlich einschließbare Daten,
    niemals einen gemessenen Nullabstand. Die Zuordnung zum Patch übernimmt der
    Aufrufer. Ein Abbruch wird durchgereicht, auch während der Vorbereitung.
    """
    if isinstance(epsilon_mm, bool) or not math.isfinite(epsilon_mm) or epsilon_mm <= 0.0:
        raise ValueError("Die numerische Zielbreite muss endlich und positiv sein.")
    token = cancelled if cancelled is not None else NeverCancelled()
    token.raise_if_cancelled()
    try:
        surface = _prepare(patch, token)
    except ArithmeticError:
        surface = None
    for triangle in triangles:
        token.raise_if_cancelled()
        result = None
        if surface is not None:
            try:
                facet = _Facet(triangle, surface)
                # Eine numerisch offene Kandidatenrechnung löscht keinen
                # bereits gesicherten globalen Ausgangsnachweis.
                with suppress(ArithmeticError):
                    _tighten(facet, epsilon_mm)
                # Auch eine überlaufende Lipschitzsumme darf nach offener
                # Verfeinerung nicht als unendliche Ergebnisklammer erscheinen.
                bounds = _I(facet.lower, facet.upper)
                result = FacetDeviation(
                    bounds.lo,
                    bounds.hi,
                    facet.witness,
                    _up(bounds.hi - bounds.lo) <= epsilon_mm,
                )
            except ArithmeticError:
                pass
        token.raise_if_cancelled()
        yield result
