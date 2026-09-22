"""Facettenabstände umfassen ausgefüllte Dreiecke und ihre wirklichen baryzentrischen Zeugen."""

from __future__ import annotations

import math
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import pairwise

import numpy as np
import pytest
import trimesh

from app.core.geom.deviation import deviation_bounds
from app.core.types import SurfacePatch


def patch(kind: str, **params) -> SurfacePatch:
    """Unabhängig deklarierter analytischer Träger ohne Erkennungsrechnung."""
    base = {
        "plane": {"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0)},
        "sphere": {"centre": (0.0, 0.0, 0.0), "radius": 10.0},
        "cylinder": {"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "radius": 10.0},
        "cone": {"apex": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "half_angle": math.pi / 4},
        "torus": {
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "ring_radius": 10.0,
            "tube_radius": 1.0,
        },
    }[kind]
    return SurfacePatch(kind, {**base, **params}, (0,), "fit")


@pytest.mark.parametrize(
    ("carrier", "triangle", "expected"),
    [
        (patch("plane"), ((-2.0, 0.0, 3.0), (2.0, 0.0, -1.0), (0.0, 2.0, 2.0)), 3.0),
        (patch("sphere"), ((-10.0, -10.0, 2.0), (10.0, -10.0, 2.0), (0.0, 10.0, 2.0)), 8.0),
        (patch("cylinder"), ((-5.0, -5.0, 0.0), (5.0, -5.0, 10.0), (0.0, 5.0, 20.0)), 10.0),
        (
            patch("cone"),
            ((-2.0, -2.0, 10.0), (2.0, -2.0, 10.0), (0.0, 2.0, 10.0)),
            10 * math.sin(math.pi / 4),
        ),
        (
            patch("cone"),
            ((-3.0, 2.0, 5.0), (3.0, 2.0, 5.0), (0.0, 3.0, 5.0)),
            5 * math.sin(math.pi / 4) - 2 * math.cos(math.pi / 4),
        ),
        (patch("cone"), ((0.0, 0.0, -4.0), (1.0, 0.0, -4.0), (0.0, 1.0, -4.0)), math.sqrt(17.0)),
        (
            patch("torus"),
            ((-12.0, 3.0, 2.0), (12.0, 3.0, 2.0), (0.0, 3.0, 2.0)),
            math.sqrt(53.0) - 1,
        ),
        (
            patch("torus"),
            ((-10.0, -10.0, 2.0), (10.0, -10.0, 2.0), (0.0, 10.0, 2.0)),
            math.sqrt(104.0) - 1,
        ),
        (
            patch("torus", tube_radius=5.0),
            ((12.0, -5.0, -5.0), (12.0, 5.0, -5.0), (12.0, 0.0, 5.0)),
            3.0,
        ),
    ],
)
def test_complete_triangle_extrema_include_edges_axis_and_interior(carrier, triangle, expected):
    """Die Sollwerte folgen aus einfachen Ebenen, Radien oder dem gerichteten Kegel."""
    result = next(deviation_bounds(carrier, [triangle], epsilon_mm=1e-6))
    assert result is not None
    assert result.lower_mm <= expected <= result.upper_mm
    assert result.upper_mm - result.lower_mm <= 1e-6
    assert result.converged
    u, v = map(Fraction, result.witness_uv)
    assert u >= 0 and v >= 0 and u + v <= 1


@pytest.mark.parametrize("kind", ["plane", "sphere", "cylinder", "cone", "torus"])
def test_point_triangle_keeps_its_exact_original_witness(kind: str) -> None:
    point = (11.0, 0.0, 0.0)
    expected = {
        "plane": 0.0,
        "sphere": 1.0,
        "cylinder": 1.0,
        "cone": 11 * math.cos(math.pi / 4),
        "torus": 0.0,
    }[kind]
    result = next(deviation_bounds(patch(kind), [(point, point, point)], epsilon_mm=1e-9))
    assert result is not None
    assert result.lower_mm <= expected <= result.upper_mm
    assert result.upper_mm - result.lower_mm <= 1e-9
    if kind in {"plane", "torus"}:
        assert result.lower_mm == 0.0


@pytest.mark.parametrize("kind", ["plane", "sphere", "cylinder", "cone", "torus"])
def test_invalid_original_triangle_is_unknown_not_zero(kind: str) -> None:
    triangle = ((float("nan"), 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert list(deviation_bounds(patch(kind), [triangle], epsilon_mm=1e-6)) == [None]


def reference_distance(carrier, triangle, uv):
    """Unabhängige 90-stellige Punktrechnung am exakten rationalen Originalzeugen."""
    with localcontext() as context:
        context.prec = 90
        u, v = map(Fraction, uv)
        fractions = tuple(
            (1 - u - v) * Fraction(a) + u * Fraction(b) + v * Fraction(c)
            for a, b, c in zip(*triangle, strict=True)
        )
        centre = carrier.params["apex" if carrier.kind == "cone" else "centre"]
        point = tuple(
            Decimal(value.numerator) / Decimal(value.denominator) - Decimal(anchor)
            for value, anchor in zip(fractions, centre, strict=True)
        )
        axis = tuple(Decimal(value) for value in carrier.params.get("axis", (0.0, 0.0, 1.0)))
        axis_size = sum(value * value for value in axis).sqrt()
        z = sum(x * y for x, y in zip(point, axis, strict=True)) / axis_size
        cross = (
            point[1] * axis[2] - point[2] * axis[1],
            point[2] * axis[0] - point[0] * axis[2],
            point[0] * axis[1] - point[1] * axis[0],
        )
        rho = sum(value * value for value in cross).sqrt() / axis_size
        if carrier.kind == "plane":
            return abs(z)
        if carrier.kind == "sphere":
            return abs(
                sum(value * value for value in point).sqrt() - Decimal(carrier.params["radius"])
            )
        if carrier.kind == "cylinder":
            return abs(rho - Decimal(carrier.params["radius"]))
        if carrier.kind == "torus":
            return abs(
                ((rho - Decimal(carrier.params["ring_radius"])) ** 2 + z * z).sqrt()
                - Decimal(carrier.params["tube_radius"])
            )
        angle = Decimal(carrier.params["half_angle"])
        sine = sine_term = angle
        cosine = cosine_term = Decimal(1)
        for index in range(1, 60):
            sine_term *= -angle * angle / ((2 * index) * (2 * index + 1))
            cosine_term *= -angle * angle / ((2 * index - 1) * (2 * index))
            sine += sine_term
            cosine += cosine_term
        h, t = sine * z - cosine * rho, sine * rho + cosine * z
        return (h * h + min(t, Decimal(0)) ** 2).sqrt()


@pytest.mark.parametrize("kind", ["plane", "sphere", "cylinder", "cone", "torus"])
def test_seeded_original_points_and_witnesses_stay_inside_the_certified_bounds(kind):
    """Feste Gegenproben ersetzen keinen Extrembeweis, entlarven aber falsche Zweige und Zeugen."""
    import random

    random_source = random.Random(16062026)
    carrier = patch(kind)
    for _ in range(12):
        triangle = tuple(
            tuple(random_source.uniform(-15.0, 15.0) for _ in range(3)) for _ in range(3)
        )
        result = next(deviation_bounds(carrier, [triangle], epsilon_mm=1e-6))
        assert result is not None
        assert 0 <= result.lower_mm <= result.upper_mm
        actual = reference_distance(carrier, triangle, result.witness_uv)
        assert Decimal(result.lower_mm) <= actual + Decimal("1e-70")
        assert actual <= Decimal(result.upper_mm) + Decimal("1e-70")
        for u in range(9):
            for v in range(9 - u):
                point_distance = reference_distance(
                    carrier, triangle, (Fraction(u, 8), Fraction(v, 8))
                )
                assert point_distance <= Decimal(result.upper_mm) + Decimal("1e-70")


@pytest.mark.parametrize("scale", [1e-200, 1.0, 1e200])
def test_axis_scaling_and_large_world_translation_keep_the_same_plane(scale):
    centre = (1e16, 1e16, 1e16)
    carrier = patch("plane", centre=centre, axis=(scale, scale, 0.0))
    triangle = ((1e16 + 2, 1e16, 1e16), (1e16, 1e16, 1e16 + 2), centre)
    result = next(deviation_bounds(carrier, [triangle], epsilon_mm=1e-6))
    assert result is not None and result.converged
    with localcontext() as context:
        context.prec = 80
        expected = Decimal(2).sqrt()
        assert Decimal(result.lower_mm) <= expected <= Decimal(result.upper_mm)
        assert Decimal(result.lower_mm) <= reference_distance(carrier, triangle, result.witness_uv)


@pytest.mark.parametrize("offset", [0.0, 1e-12, -1e-12])
@pytest.mark.parametrize("tilt", [0.0, 1e-12, 0.1])
def test_torus_horizontal_vertical_and_nearly_tangent_cases_keep_all_samples(offset, tilt):
    carrier = patch("torus", tube_radius=5.0)
    triangles = [
        ((12.0, -5.0, -5.0), (12.0 + tilt, 5.0, -5.0), (12.0, 0.0, 5.0)),
        ((9.0 + offset, -1.0, 0.0), (11.0 + offset, -1.0, tilt), (10.0 + offset, 1.0, 0.0)),
        ((-12.0, 0.0, -2.0), (12.0, tilt, -2.0), (0.0, 0.0, 2.0)),
    ]
    for triangle in triangles:
        result = next(deviation_bounds(carrier, [triangle], epsilon_mm=1e-6))
        assert result is not None
        for u in range(9):
            for v in range(9 - u):
                value = reference_distance(carrier, triangle, (Fraction(u, 8), Fraction(v, 8)))
                assert value <= Decimal(result.upper_mm) + Decimal("1e-70")
        assert Decimal(result.lower_mm) <= reference_distance(
            carrier, triangle, result.witness_uv
        ) + Decimal("1e-70")


@pytest.mark.parametrize("height", [-4.0, -1e-12, 0.0, 1e-12, 4.0])
@pytest.mark.parametrize("direction", [-1.0, 1.0])
def test_cone_uses_only_its_directed_nappe(height, direction):
    carrier = patch("cone", axis=(0.0, 0.0, direction))
    point = (1.0, 0.0, height)
    triangle = (point, point, point)
    result = next(deviation_bounds(carrier, [triangle], epsilon_mm=1e-6))
    expected = reference_distance(carrier, triangle, (0.0, 0.0))
    assert result is not None and result.converged
    assert Decimal(result.lower_mm) <= expected <= Decimal(result.upper_mm)


def test_every_carrier_closes_its_bracket_on_its_own_body() -> None:
    """RM-202: Der Ring schloss als Einziger nicht — 0,16 mm, wo die anderen null hatten.

    Gemessen am 22.09.2026 an einem Ring aus 4 096 Dreiecken: Ebene,
    Zylinder, Kugel und Kegel klammerten jedes Dreieck auf Mikrometer ein, der
    Torus blieb im Mittel 0,16 mm und schlimmstenfalls 0,30 mm breit. Zwei
    Ursachen, beide behoben: Das Verfeinerungsbudget gehörte dem **Träger**,
    also bekamen die ersten Dreiecke alles und der Rest nichts; und die Kante
    wurde blind halbiert, statt an den Stellen geteilt zu werden, an denen der
    Abstand kehrt (``_torus_breakpoints``).

    Geprüft wird der Ring selbst — der Träger, an dem es auffiel — und
    daneben ein Zylinder, damit ein Rückschritt an den übrigen Trägern hier
    ebenfalls rot wird.
    """
    ring = trimesh.creation.torus(
        major_radius=10.0, minor_radius=3.0, major_sections=48, minor_sections=24
    )
    triangles = np.asarray(ring.triangles, dtype=float)
    torus = patch("torus", tube_radius=3.0)
    breiten = [
        entry.upper_mm - entry.lower_mm
        for entry in deviation_bounds(torus, triangles, epsilon_mm=1e-6)
        if entry is not None
    ]
    assert len(breiten) == len(triangles)
    assert max(breiten) < 0.01, f"breiteste Klammer am Ring: {max(breiten):.6f} mm"

    tube = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=64)
    walls = np.asarray(tube.triangles, dtype=float)
    cylinder = patch("cylinder")
    andere = [
        entry.upper_mm - entry.lower_mm
        for entry in deviation_bounds(cylinder, walls, epsilon_mm=1e-6)
        if entry is not None
    ]
    assert max(andere) <= 1e-9, f"der Zylinder schloss immer: {max(andere):.12f} mm"


def test_refinement_is_per_triangle_and_exhaustion_keeps_a_finite_valid_interval(monkeypatch):
    """Das Budget gehört dem Dreieck, und ein erschöpftes liefert trotzdem eine Klammer.

    **Bis zum 22.09.2026 galt es je Aufruf, und dieser Test schrieb das fest.**
    Er war damit die Stelle, an der ein Ring seine Genauigkeit verlor: Die
    ersten Dreiecke verbrauchten die gemeinsame Marke, alle weiteren bekamen
    die Rechteckklammer — an 4 096 Ringdreiecken im Mittel 0,16 mm breit, wo
    Ebene, Zylinder, Kugel und Kegel auf Mikrometer schließen (RM-202).

    Was bleibt und hier geprüft wird, ist die Zusicherung dahinter: Ein
    aufgebrauchtes Budget endet nie mit einer unendlichen oder ungültigen
    Klammer, und jedes Dreieck bekommt dieselbe Arbeit — der zwanzigste ist so
    genau wie der erste.
    """
    from app.core.geom import deviation

    monkeypatch.setattr(deviation, "_MAX_REFINEMENTS", 5)
    calls: list[tuple] = []
    original = deviation._edge_upper

    def counted(*args):
        calls.append(args[1:])
        return original(*args)

    monkeypatch.setattr(deviation, "_edge_upper", counted)
    carrier = patch("torus", tube_radius=5.0)
    triangle = ((12.0, -5.0, -5.0), (12.0, 5.0, -5.0), (12.0, 0.0, 5.0))
    result = list(deviation_bounds(carrier, [triangle] * 20, epsilon_mm=1e-12))
    assert len(result) == 20
    for entry in result:
        assert entry is not None and entry.lower_mm <= 3.0 <= entry.upper_mm
        assert math.isfinite(entry.upper_mm), "ein aufgebrauchtes Budget endet nicht im Unendlichen"
    # Zwanzig gleiche Dreiecke, zwanzig gleiche Klammern — der Beleg dafür,
    # dass keines das Budget eines anderen verbraucht. Vorher trug das letzte
    # die rohe Rechteckklammer, und genau deshalb stand hier einmal
    # ``assert not result[-1].converged``: Mit fünf gemeinsamen Schritten kam
    # es nie ans Ziel. Seit die Kante an ihren Extremstellen geteilt wird
    # (``_torus_breakpoints``), schließt es auch mit fünf.
    breiten = {round(entry.upper_mm - entry.lower_mm, 12) for entry in result}
    assert len(breiten) == 1, breiten
    assert calls, "die Kantenarbeit läuft — sonst prüft der Test nichts"


def test_cancel_during_preparation_and_between_original_triangles_propagates():
    from app.core.errors import OperationCancelled
    from app.core.scene import CancelSignal

    class CountingCancel(CancelSignal):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def raise_if_cancelled(self):
            self.calls += 1
            if self.calls == 10:
                self.cancel()
            super().raise_if_cancelled()

    triangle = ((1.0, 0.0, 0.0),) * 3
    with pytest.raises(OperationCancelled):
        next(
            deviation_bounds(patch("cone"), [triangle], epsilon_mm=1e-6, cancelled=CountingCancel())
        )
    signal = CancelSignal()
    iterator = deviation_bounds(
        patch("sphere"), [triangle, triangle], epsilon_mm=1e-6, cancelled=signal
    )
    assert next(iterator) is not None
    signal.cancel()
    with pytest.raises(OperationCancelled):
        next(iterator)


@pytest.mark.parametrize(
    "angle", [math.nextafter(0.0, 1.0), 1e-12, 0.1, math.pi / 4, math.nextafter(math.pi / 2, 0.0)]
)
def test_cone_angle_bracket_encloses_a_high_precision_independent_point(angle):
    carrier = patch("cone", half_angle=angle)
    triangle = ((1.0, 0.0, 2.0),) * 3
    result = next(deviation_bounds(carrier, [triangle], epsilon_mm=1e-6))
    expected = reference_distance(carrier, triangle, (0.0, 0.0))
    assert result is not None
    assert Decimal(result.lower_mm) <= expected <= Decimal(result.upper_mm)


def test_elementary_interval_operations_enclose_exact_float_arithmetic():
    from app.core.geom.deviation import _I

    for left, right in (
        (1e16, 1.0),
        (math.nextafter(1.0, 2.0), -1.0),
        (1e-200, 1e-100),
        (-1e100, 1e-100),
    ):
        a, b = _I(left, left), _I(right, right)
        for interval, actual in (
            (a + b, Fraction(left) + Fraction(right)),
            (a - b, Fraction(left) - Fraction(right)),
            (a * b, Fraction(left) * Fraction(right)),
            (a / b, Fraction(left) / Fraction(right)),
        ):
            assert Fraction(interval.lo) <= actual <= Fraction(interval.hi)
    result = (_I(1e16, 1e16) + _I(1.0, 1.0)) - _I(1e16, 1e16)
    assert result.lo <= 1.0 <= result.hi
    with pytest.raises(ArithmeticError):
        _I(1.0, 1.0) / _I(-1.0, 1.0)


def test_edge_interval_uses_exact_linear_position_when_one_minus_t_is_not_a_float():
    from app.core.geom.deviation import _edge_upper, _Facet, _prepare
    from app.core.scene.cancel import NeverCancelled

    carrier = patch("torus")
    triangle = ((0.0, 0.0, 0.0), (11.0, 0.0, 0.0), (1e30, 0.0, 0.0))
    facet = _Facet(triangle, _prepare(carrier, NeverCancelled()))
    low, high = 2.0**-100, 2.0**-99
    upper = _edge_upper(facet, 1, 2, low, high)
    for value in (Fraction(low), Fraction(high)):
        exact = reference_distance(carrier, triangle, (1 - value, value))
        assert exact <= Decimal(upper)


def test_tighter_requested_interval_keeps_previous_bounds_and_real_maximum():
    carrier = patch("torus", tube_radius=5.0)
    triangle = ((12.0, -5.0, -5.0), (12.0, 5.0, -5.0), (12.0, 0.0, 5.0))
    results = [
        next(deviation_bounds(carrier, [triangle], epsilon_mm=epsilon))
        for epsilon in (1.0, 1e-3, 1e-9)
    ]
    for result in results:
        assert result is not None and result.lower_mm <= 3.0 <= result.upper_mm
    for earlier, later in pairwise(results):
        assert later.lower_mm >= earlier.lower_mm
        assert later.upper_mm <= earlier.upper_mm


def test_subdivision_preserves_the_same_filled_surface_maximum():
    carrier = patch("torus")
    triangle = ((-10.0, -10.0, 2.0), (10.0, -10.0, 2.0), (0.0, 10.0, 2.0))
    a, b, c = triangle
    ab, ac, bc = (
        tuple((x + y) / 2 for x, y in zip(first, second, strict=True))
        for first, second in ((a, b), (a, c), (b, c))
    )
    children = ((a, ab, ac), (ab, b, bc), (ac, bc, c), (ab, bc, ac))
    results = list(deviation_bounds(carrier, children, epsilon_mm=1e-6))
    assert all(result is not None for result in results)
    expected = math.sqrt(104.0) - 1
    lower, upper = (
        max(result.lower_mm for result in results),
        max(result.upper_mm for result in results),
    )
    assert lower <= expected <= upper and upper - lower <= 1e-6


@pytest.mark.parametrize(
    "carrier",
    [
        patch("torus", ring_radius=1.0, tube_radius=1.0),
        patch("cone", half_angle=0.0),
        patch("sphere", radius=True),
        patch("plane", axis=(0.0, 0.0, 0.0)),
    ],
)
def test_invalid_carrier_never_creates_a_zero_result(carrier):
    triangle = ((1.0, 0.0, 0.0),) * 3
    assert list(deviation_bounds(carrier, [triangle], epsilon_mm=1e-6)) == [None]


def test_unrepresentable_world_difference_is_unknown():
    triangle = ((1e308, 0.0, 0.0),) * 3
    carrier = patch("sphere", centre=(-1e308, 0.0, 0.0))
    assert list(deviation_bounds(carrier, [triangle], epsilon_mm=1e-6)) == [None]


def test_overflowing_initial_bound_never_publishes_infinity():
    triangle = (
        (1.55e308, 0.4e308, 0.0),
        (1.55e308, -0.4e308, 0.0),
        (1.55e308, 0.0, 0.4e308),
    )
    # Das Dreieck liegt ganz außerhalb der Kugel; die konvexe Norm erreicht
    # ihr Maximum an den gleich weit entfernten Ecken, noch im Floatbereich.
    with localcontext() as context:
        context.prec = 400
        maximum = sum(Decimal(value) ** 2 for value in triangle[0]).sqrt() - Decimal(10)
    assert math.isfinite(float(maximum))
    assert list(deviation_bounds(patch("sphere"), [triangle], epsilon_mm=1.0)) == [None]


def test_machine_width_is_reported_instead_of_claiming_requested_accuracy():
    triangle = ((11.0, 0.0, 0.0),) * 3
    result = next(deviation_bounds(patch("torus"), [triangle], epsilon_mm=1e-100))
    assert result is not None
    assert result.lower_mm == 0.0 and result.upper_mm > 1e-100
    assert not result.converged


def test_cancel_inside_a_real_edge_probe_yields_no_partial_triangle(monkeypatch):
    from app.core.errors import OperationCancelled
    from app.core.geom import deviation
    from app.core.scene import CancelSignal

    signal = CancelSignal()
    original = deviation._edge_upper
    calls = []

    def cancelled(*args):
        result = original(*args)
        calls.append(result)
        signal.cancel()
        return result

    monkeypatch.setattr(deviation, "_edge_upper", cancelled)
    triangle = ((12.0, -5.0, -5.0), (12.0, 5.0, -5.0), (12.0, 0.0, 5.0))
    with pytest.raises(OperationCancelled):
        next(
            deviation_bounds(
                patch("torus", tube_radius=5.0), [triangle], epsilon_mm=1e-9, cancelled=signal
            )
        )
    assert len(calls) == 1


def test_iterator_preserves_order_and_prepares_the_carrier_once(monkeypatch):
    from app.core.geom import deviation

    carrier = patch("cone")
    before = dict(carrier.params)
    calls = []
    original = deviation._trig

    def counted(*args):
        calls.append(args[0])
        return original(*args)

    monkeypatch.setattr(deviation, "_trig", counted)
    inputs = [((1.0, 0.0, -4.0),) * 3, ((float("inf"), 0.0, 0.0),) * 3, ((0.0, 0.0, 10.0),) * 3]
    results = list(deviation_bounds(carrier, iter(inputs), epsilon_mm=1e-6))
    assert len(results) == 3 and results[1] is None
    assert results[0].lower_mm <= math.sqrt(17) <= results[0].upper_mm
    assert results[2].lower_mm <= 10 * math.sin(math.pi / 4) <= results[2].upper_mm
    assert calls == [carrier.params["half_angle"]]
    assert dict(carrier.params) == before


# --- Alle Dreiecke einer Trägerart zugleich -------------------------------------


def _random_triangles(seed: int, count: int) -> list:
    import random

    source = random.Random(seed)
    return [
        tuple(tuple(source.uniform(-15.0, 15.0) for _ in range(3)) for _ in range(3))
        for _ in range(count)
    ]


def test_grouped_bounds_say_the_same_as_the_single_carrier_path() -> None:
    """Zwei Zylinder mit verschiedenen Radien und Achsen, eine Ebene, eine Kugel, ein
    Kegel und ein Torus in einem Aufruf: Jede Klammer schließt dieselben Zeugen und
    Rasterpunkte ein wie der Einzelweg, und beide Klammern liegen auf zwölf Stellen
    beieinander — der Stapel rundet um höchstens ein ULP weiter als ``_I``."""
    import numpy as np

    from app.core.geom.deviation import deviation_bounds_grouped

    carriers = [
        patch("cylinder"),
        patch("cylinder", centre=(3.0, -2.0, 1.0), axis=(0.0, 1.0, 1.0), radius=4.0),
        patch("plane", centre=(1.0, 1.0, 1.0), axis=(1.0, 2.0, 3.0)),
        patch("sphere", radius=7.0),
        patch("cone", half_angle=0.3),
        patch("torus", tube_radius=5.0),
    ]
    triangles = [_random_triangles(seed, 9) for seed in range(len(carriers))]
    tables = deviation_bounds_grouped(
        carriers, [np.asarray(entry) for entry in triangles], epsilon_mm=1e-6
    )
    assert len(tables) == len(carriers)
    for carrier, entries, table in zip(carriers, triangles, tables, strict=True):
        single = list(deviation_bounds(carrier, entries, epsilon_mm=1e-6))
        assert table.known.all() and len(single) == len(entries)
        for index, (triangle, expected) in enumerate(zip(entries, single, strict=True)):
            assert expected is not None
            lower, upper = float(table.lower_mm[index]), float(table.upper_mm[index])
            scale = max(1.0, expected.upper_mm)
            assert abs(lower - expected.lower_mm) <= 1e-12 * scale
            assert abs(upper - expected.upper_mm) <= 1e-12 * scale
            assert bool(table.converged[index]) == expected.converged
            witness = (
                Fraction(float(table.witness_uv[index, 0])),
                Fraction(float(table.witness_uv[index, 1])),
            )
            assert witness[0] >= 0 and witness[1] >= 0 and witness[0] + witness[1] <= 1
            assert Decimal(lower) <= reference_distance(carrier, triangle, witness) + Decimal(
                "1e-70"
            )
            for u in range(5):
                for v in range(5 - u):
                    value = reference_distance(carrier, triangle, (Fraction(u, 4), Fraction(v, 4)))
                    assert value <= Decimal(upper) + Decimal("1e-70")


def test_grouped_table_keeps_order_and_marks_the_unknown() -> None:
    """Ein Dreieck mit ``nan`` mitten im Stapel bleibt unbekannt, seine Nachbarn nicht —
    und Zahlen jenseits von 10¹⁰⁰ gehen den skalaren Weg, ohne die Reihenfolge zu stören."""
    import numpy as np

    from app.core.geom.deviation import deviation_bounds_grouped

    good = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    broken = ((float("nan"), 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    huge = ((1e150, 0.0, 0.0),) * 3
    (table,) = deviation_bounds_grouped(
        [patch("sphere")], [np.asarray([good, broken, good, huge])], epsilon_mm=1e-6
    )
    assert table.known.tolist() == [True, False, True, True]
    assert table.lower_mm[0] == table.lower_mm[2] and table.upper_mm[0] == table.upper_mm[2]
    single = list(deviation_bounds(patch("sphere"), [huge], epsilon_mm=1e-6))
    assert single[0] is not None
    assert table.lower_mm[3] == single[0].lower_mm and table.upper_mm[3] == single[0].upper_mm


@pytest.mark.parametrize("kind", ["plane", "sphere", "cylinder", "cone"])
def test_closed_form_carriers_never_fall_back_to_the_scalar_path(kind: str, monkeypatch) -> None:
    """Ebene, Kugel, Zylinder und Kegel sind im Stapel geschlossen gerechnet — auch mit
    einem Dreieck, das die Achse trifft, und mit Klammern um null, deren oberer Rand
    eine Denormalzahl ist (die Wurzel daraus war am 21.09.2026 nicht bestätigbar,
    und 96 von 96 Kegeldreiecken der Dose gingen den langsamen Weg)."""
    from app.core.geom import deviation

    def forbidden(*args):
        raise AssertionError("the batch must carry every closed-form carrier itself")

    monkeypatch.setattr(deviation, "_scalar_result", forbidden)
    carrier = patch(kind)
    triangles = [
        ((-2.0, -2.0, 10.0), (2.0, -2.0, 10.0), (0.0, 2.0, 10.0)),
        ((11.0, 0.0, 0.0),) * 3,
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        *_random_triangles(21092026, 6),
    ]
    results = list(deviation_bounds(carrier, triangles, epsilon_mm=1e-6))
    assert all(result is not None for result in results)
    for triangle, result in zip(triangles, results, strict=True):
        assert result is not None and result.converged
        for u in range(5):
            for v in range(5 - u):
                value = reference_distance(carrier, triangle, (Fraction(u, 4), Fraction(v, 4)))
                assert value <= Decimal(result.upper_mm) + Decimal("1e-70")
