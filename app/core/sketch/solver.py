"""Der 2D-Solver für Skizzen (Bauplan §30.1).

Kleinste Quadrate auf scipy — BSD und bereits in der Freigabeliste; SolveSpace
und py-slvs sind GPL und darum keine Option (Regel 15). Deterministisch: der
Startzustand sind die Punkte der Skizze selbst, Zufall kommt nicht vor, und
derselbe Aufruf liefert dieselbe Lösung (Regel 9 greift nicht — es gibt keinen
Startwert, weil es keine Streuung gibt).

Jede Bedingung bringt ihre Residuen **und ihre analytische Ableitung** mit.
Das ist kein Luxus: mit numerischer Differenzenbildung kostet die Jacobimatrix
eine Funktionsauswertung je Variable und verfehlt das Budget aus §31 um eine
Größenordnung — und ihre Näherungsfehler verschmieren die Ranganalyse, an der
die Erkennung überbestimmter Skizzen hängt.

Unterbestimmt ist kein Fehler: die verbleibenden Freiheitsgrade stehen im
Ergebnis, ein Befund daraus wird erst auf Op-Ebene. Überbestimmt oder
widersprüchlich hält an und nennt das kollidierende Bedingungspaar
(Regel 17, §30.1).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np

from app.core.deferred import csr_matrix, least_squares
from app.core.errors import SketchConflictError, ValidationError
from app.core.expressions import evaluate
from app.core.types import Point2, Sketch, SketchConstraint, SketchElement, SolvedSketch
from app.core.units import EPS_GEOM
from app.i18n import _

#: Restfehler, ab dem eine Lösung als widersprüchlich gilt. Konsistente Systeme
#: konvergieren um Größenordnungen tiefer; die Lücke dazwischen ist die Antwort.
_TOL: Final[float] = EPS_GEOM

#: Wie viele Punkte ein Element je ``kind`` trägt (§9).
_ELEMENT_POINTS: Final[dict[str, int]] = {"point": 1, "line": 2, "circle": 2, "arc": 3}

#: Arten ohne feste Punktzahl, mit ihrem Mindestmaß. Ein Spline läuft durch so
#: viele Punkte, wie jemand gesetzt hat — unter zweien ist er ein Punkt.
_ELEMENT_MINIMUM: Final[dict[str, int]] = {"spline": 2}

#: Wie viele Zielpunkte eine Bedingung je ``kind`` nimmt.
_CONSTRAINT_TARGETS: Final[dict[str, int]] = {
    "distance": 2,
    "coincident": 2,
    "horizontal": 2,
    "vertical": 2,
    "parallel": 4,
    "perpendicular": 4,
    "tangent": 4,
    "symmetric": 4,
    "fixed": 1,
    "reference": 2,
}

#: Bedingungen, die nichts festlegen. Sie werden geprüft wie jede andere —
#: falsche Zielzahl bleibt ein Fehler — aber sie kommen nie ins
#: Gleichungssystem: ein Referenzmaß misst (§30.1).
_MEASURING_ONLY: Final[frozenset[str]] = frozenset({"reference"})

_ResidualFn = Callable[[np.ndarray], tuple[float, ...]]
_GradientFn = Callable[[np.ndarray, np.ndarray], None]
"""Schreibt die Zeilen einer Gleichung in die übergebene Jacobimatrix.

Erster Parameter sind die Punkte ``(n, 2)``, zweiter die Zeilen dieser
Gleichung als Sicht auf die Matrix ``(rows, n, 2)`` — addiert wird an
``[zeile, punkt, koordinate]``, die Sicht beginnt bei null."""


@dataclass(frozen=True, slots=True)
class _Equation:
    """Eine Gleichungsgruppe: ihr Ursprung, ihre Residuen, ihre Ableitung.

    ``constraint`` ist der Index in ``sketch.constraints`` — oder ``None`` für
    die implizite Bedingung eines Bogens (beide Schenkel gleich lang)."""

    constraint: int | None
    rows: int
    fn: _ResidualFn
    grad: _GradientFn


def _unit(points: np.ndarray, tail: int, head: int) -> tuple[float, float, float]:
    """Einheitsrichtung von ``tail`` nach ``head`` und die echte Länge,
    gegen Länge null gesichert."""
    dx = float(points[head][0] - points[tail][0])
    dy = float(points[head][1] - points[tail][1])
    length = max(float(np.hypot(dx, dy)), EPS_GEOM)
    return dx / length, dy / length, length


def _span(points: np.ndarray, tail: int, head: int) -> float:
    return float(np.hypot(points[head][0] - points[tail][0], points[head][1] - points[tail][1]))


def _project(points: np.ndarray, tail: int, head: int, gx: float, gy: float) -> tuple[float, float]:
    """Gradient eines Ausdrucks in der Einheitsrichtung, zurückgeholt auf die
    rohe Differenz: ``(I - ûûᵀ)/L`` angewandt auf ``(gx, gy)``."""
    ux, uy, length = _unit(points, tail, head)
    dot = ux * gx + uy * gy
    return (gx - ux * dot) / length, (gy - uy * dot) / length


def _distance_equation(a: int, b: int, length: float) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (_span(pts, a, b) - length,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        out[0, b, 0] += ux
        out[0, b, 1] += uy
        out[0, a, 0] -= ux
        out[0, a, 1] -= uy

    return fn, grad


def _coincident_equation(a: int, b: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (float(pts[b][0] - pts[a][0]), float(pts[b][1] - pts[a][1]))

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        out[0, b, 0] += 1.0
        out[0, a, 0] -= 1.0
        out[1, b, 1] += 1.0
        out[1, a, 1] -= 1.0

    return fn, grad


def _axis_equation(a: int, b: int, axis: int) -> tuple[_ResidualFn, _GradientFn]:
    """``horizontal`` gleicht die y-Koordinaten an (axis 1), ``vertical`` die x."""

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (float(pts[b][axis] - pts[a][axis]),)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        out[0, b, axis] += 1.0
        out[0, a, axis] -= 1.0

    return fn, grad


def _parallel_equation(a: int, b: int, c: int, d: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        return (ux * vy - uy * vx,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        gux, guy = _project(pts, a, b, vy, -vx)
        gvx, gvy = _project(pts, c, d, -uy, ux)
        out[0, b, 0] += gux
        out[0, b, 1] += guy
        out[0, a, 0] -= gux
        out[0, a, 1] -= guy
        out[0, d, 0] += gvx
        out[0, d, 1] += gvy
        out[0, c, 0] -= gvx
        out[0, c, 1] -= gvy

    return fn, grad


def _perpendicular_equation(a: int, b: int, c: int, d: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        return (ux * vx + uy * vy,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        gux, guy = _project(pts, a, b, vx, vy)
        gvx, gvy = _project(pts, c, d, ux, uy)
        out[0, b, 0] += gux
        out[0, b, 1] += guy
        out[0, a, 0] -= gux
        out[0, a, 1] -= guy
        out[0, d, 0] += gvx
        out[0, d, 1] += gvy
        out[0, c, 0] -= gvx
        out[0, c, 1] -= gvy

    return fn, grad


def _tangent_equation(a: int, b: int, centre: int, rim: int) -> tuple[_ResidualFn, _GradientFn]:
    def cross(pts: np.ndarray) -> float:
        ux, uy, _ = _unit(pts, a, b)
        wx = float(pts[centre][0] - pts[a][0])
        wy = float(pts[centre][1] - pts[a][1])
        return ux * wy - uy * wx

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (abs(cross(pts)) - _span(pts, centre, rim),)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        wx = float(pts[centre][0] - pts[a][0])
        wy = float(pts[centre][1] - pts[a][1])
        sign = 1.0 if cross(pts) >= 0.0 else -1.0
        # Anteil über die Linienrichtung û …
        gux, guy = _project(pts, a, b, wy, -wx)
        out[0, b, 0] += sign * gux
        out[0, b, 1] += sign * guy
        out[0, a, 0] -= sign * gux
        out[0, a, 1] -= sign * guy
        # … und über den Fußpunktvektor w = Mittelpunkt - a.
        out[0, centre, 0] += sign * -uy
        out[0, centre, 1] += sign * ux
        out[0, a, 0] -= sign * -uy
        out[0, a, 1] -= sign * ux
        # Radiusanteil: -|rim - centre|.
        rx, ry, _ = _unit(pts, centre, rim)
        out[0, rim, 0] -= rx
        out[0, rim, 1] -= ry
        out[0, centre, 0] += rx
        out[0, centre, 1] += ry

    return fn, grad


def _symmetric_equation(p: int, q: int, a: int, b: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        ux, uy, _ = _unit(pts, a, b)
        mx = (float(pts[p][0]) + float(pts[q][0])) / 2.0 - float(pts[a][0])
        my = (float(pts[p][1]) + float(pts[q][1])) / 2.0 - float(pts[a][1])
        cx = float(pts[q][0] - pts[p][0])
        cy = float(pts[q][1] - pts[p][1])
        return (ux * my - uy * mx, ux * cx + uy * cy)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        mx = (float(pts[p][0]) + float(pts[q][0])) / 2.0 - float(pts[a][0])
        my = (float(pts[p][1]) + float(pts[q][1])) / 2.0 - float(pts[a][1])
        cx = float(pts[q][0] - pts[p][0])
        cy = float(pts[q][1] - pts[p][1])
        # Zeile 1: die Mitte liegt auf der Achse — cross(û, m).
        gux, guy = _project(pts, a, b, my, -mx)
        out[0, b, 0] += gux
        out[0, b, 1] += guy
        out[0, a, 0] -= gux
        out[0, a, 1] -= guy
        out[0, p, 0] += -uy / 2.0
        out[0, p, 1] += ux / 2.0
        out[0, q, 0] += -uy / 2.0
        out[0, q, 1] += ux / 2.0
        out[0, a, 0] -= -uy
        out[0, a, 1] -= ux
        # Zeile 2: die Verbindung steht senkrecht auf der Achse — û · (q - p).
        hux, huy = _project(pts, a, b, cx, cy)
        out[1, b, 0] += hux
        out[1, b, 1] += huy
        out[1, a, 0] -= hux
        out[1, a, 1] -= huy
        out[1, q, 0] += ux
        out[1, q, 1] += uy
        out[1, p, 0] -= ux
        out[1, p, 1] -= uy

    return fn, grad


def _fixed_equation(p: int, anchor_x: float, anchor_y: float) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (float(pts[p][0]) - anchor_x, float(pts[p][1]) - anchor_y)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        out[0, p, 0] += 1.0
        out[1, p, 1] += 1.0

    return fn, grad


def _arc_equation(centre: int, start: int, end: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (_span(pts, centre, start) - _span(pts, centre, end),)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        sx, sy, _ = _unit(pts, centre, start)
        ex, ey, _ = _unit(pts, centre, end)
        out[0, start, 0] += sx
        out[0, start, 1] += sy
        out[0, end, 0] -= ex
        out[0, end, 1] -= ey
        out[0, centre, 0] += ex - sx
        out[0, centre, 1] += ey - sy

    return fn, grad


def _constraint_equation(
    constraint: SketchConstraint, length: float, anchors: np.ndarray
) -> tuple[int, _ResidualFn, _GradientFn]:
    """Übersetzt eine Bedingung in Residuen, Ableitung und Zeilenzahl."""
    kind = constraint.kind
    targets = constraint.targets
    if kind == "distance":
        return 1, *_distance_equation(targets[0], targets[1], length)
    if kind == "coincident":
        return 2, *_coincident_equation(targets[0], targets[1])
    if kind == "horizontal":
        return 1, *_axis_equation(targets[0], targets[1], 1)
    if kind == "vertical":
        return 1, *_axis_equation(targets[0], targets[1], 0)
    if kind == "parallel":
        return 1, *_parallel_equation(*targets)
    if kind == "perpendicular":
        return 1, *_perpendicular_equation(*targets)
    if kind == "tangent":
        return 1, *_tangent_equation(*targets)
    if kind == "symmetric":
        return 2, *_symmetric_equation(*targets)
    # fixed: heftet den Punkt an seine Eingangskoordinaten.
    (p,) = targets
    return 2, *_fixed_equation(p, float(anchors[p][0]), float(anchors[p][1]))


def _build_equations(
    sketch: Sketch, params: Mapping[str, float]
) -> tuple[list[_Equation], np.ndarray]:
    """Validiert die Skizze und übersetzt sie in Gleichungen (§30.1)."""
    offsets: list[int] = []
    coords: list[Point2] = []
    for position, element in enumerate(sketch.elements):
        least = _ELEMENT_MINIMUM.get(element.kind)
        if least is not None:
            if len(element.points) < least:
                raise ValidationError(
                    f"elements[{position}]",
                    _("Das Element hat zu wenige Punkte."),
                    value=len(element.points),
                    constraint="point_count",
                )
        elif len(element.points) != _ELEMENT_POINTS[element.kind]:
            raise ValidationError(
                f"elements[{position}]",
                _("Das Element hat die falsche Zahl von Punkten."),
                value=len(element.points),
                constraint="point_count",
            )
        offsets.append(len(coords))
        coords.extend(element.points)
    anchors = np.asarray(coords, dtype=float).reshape(-1, 2)
    total = len(coords)

    equations: list[_Equation] = []
    for index, constraint in enumerate(sketch.constraints):
        field = f"constraints[{index}]"
        if len(constraint.targets) != _CONSTRAINT_TARGETS[constraint.kind]:
            raise ValidationError(
                field,
                _("Die Bedingung hat die falsche Zahl von Zielpunkten."),
                value=len(constraint.targets),
                constraint="target_count",
            )
        if constraint.kind in _MEASURING_ONLY:
            # Zielprüfung oben gilt weiter; hier endet der Weg, denn ohne
            # Gleichung gibt es weder Rang noch Rest noch Konflikt.
            for target in constraint.targets:
                if not 0 <= target < total:
                    raise ValidationError(
                        field,
                        _("Diese Bedingung zeigt auf einen Punkt, den es nicht gibt."),
                        value=target,
                        constraint="unknown_target",
                    )
            continue
        for target in constraint.targets:
            if not 0 <= target < total:
                raise ValidationError(
                    field,
                    _("Die Bedingung zeigt auf einen Punkt, den es nicht gibt."),
                    value=target,
                    constraint="unknown_target",
                )
        length = 0.0
        if constraint.kind == "distance":
            if not constraint.value:
                raise ValidationError(
                    field, _("Ein Maß braucht einen Wert."), constraint="required"
                )
            length = evaluate(constraint.value, params)
            if length < 0.0:
                raise ValidationError(
                    field,
                    _("Ein Maß unter null gibt es nicht."),
                    value=length,
                    constraint="negative",
                )
        elif constraint.value:
            raise ValidationError(
                field,
                _("Nur ein Maß trägt einen Wert."),
                value=constraint.value,
                constraint="value_not_allowed",
            )
        rows, fn, grad = _constraint_equation(constraint, length, anchors)
        equations.append(_Equation(index, rows, fn, grad))

    for position, element in enumerate(sketch.elements):
        if element.kind not in ("circle", "arc"):
            continue
        centre = offsets[position]
        if _span(anchors, centre, centre + 1) < EPS_GEOM:
            # ``positive`` und nicht ``element.kind``: Die Beschränkung sagt,
            # **was** verletzt wurde, nicht **woran**. Hier stand einmal
            # „circle", und weil das keine Spanne ist, las der Kunde über einem
            # Satz mit einer klaren Grenze den vagen Titel der Oberklasse. Um
            # welches Element es geht, steht ohnehin im Feld.
            raise ValidationError(
                f"elements[{position}]",
                _("Ein Kreis braucht einen Radius größer als null."),
                constraint="positive",
            )
        if element.kind == "arc":
            fn, grad = _arc_equation(centre, centre + 1, centre + 2)
            equations.append(_Equation(None, 1, fn, grad))

    return equations, anchors


def _solve(
    equations: Sequence[_Equation], start: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ein Lauf des Lösers: Koordinaten, Residuen, Jacobimatrix an der Lösung."""
    flat = start.reshape(-1)
    total_rows = sum(equation.rows for equation in equations)
    points = flat.size // 2

    def fun(x: np.ndarray) -> np.ndarray:
        pts = x.reshape(-1, 2)
        rows: list[float] = []
        for equation in equations:
            rows.extend(equation.fn(pts))
        return np.asarray(rows, dtype=float)

    def jac(x: np.ndarray) -> np.ndarray:
        pts = x.reshape(-1, 2)
        matrix = np.zeros((total_rows, points, 2))
        begin = 0
        for equation in equations:
            equation.grad(pts, matrix[begin : begin + equation.rows])
            begin += equation.rows
        return matrix.reshape(total_rows, points * 2)

    def sparse_jac(x: np.ndarray) -> csr_matrix:
        return csr_matrix(jac(x))

    if not equations:
        return flat, np.zeros(0), np.zeros((0, flat.size))
    # ``lsmr`` statt der dichten SVD je Iteration: bei 200 Bedingungen der
    # Unterschied zwischen 700 ms und dem Budget aus §31 — nachgemessen.
    result = least_squares(
        fun,
        flat,
        jac=sparse_jac,
        method="trf",
        tr_solver="lsmr",
        # Ohne Grenze läuft LSMR hier bis zur kleineren Matrixkante. Bei der
        # langen, dünn besetzten Kette des §31-Korpus sind das 300 innere
        # Schritte je Versuch und 105 ms insgesamt. Mit 150 Schritten braucht
        # der äußere Löser acht statt achtzehn Versuche, hält denselben Rest
        # weit unter ``_TOL`` und löst die 200 Bedingungen in 42 ms. Die
        # Grenze ist keine Genauigkeitsschranke: TRF setzt mit dem verbleibenden
        # Rest weiter an, statt eine unfertige Antwort zurückzugeben.
        tr_options={"maxiter": 150},
        xtol=1e-10,
        ftol=1e-10,
        gtol=1e-10,
    )
    return (
        np.asarray(result.x, dtype=float),
        np.asarray(result.fun, dtype=float),
        jac(np.asarray(result.x, dtype=float)),
    )


def _row_blocks(equations: Sequence[_Equation]) -> list[range]:
    """Welche Zeilen des Residuenvektors zu welcher Gleichung gehören."""
    blocks: list[range] = []
    begin = 0
    for equation in equations:
        blocks.append(range(begin, begin + equation.rows))
        begin += equation.rows
    return blocks


def _worst_constraints(
    equations: Sequence[_Equation], blocks: Sequence[range], residuals: np.ndarray
) -> list[int]:
    """Bedingungsindizes nach ihrem größten Restfehler, absteigend, stabil."""
    worst: dict[int, float] = {}
    for equation, block in zip(equations, blocks, strict=True):
        if equation.constraint is None:
            continue
        peak = max((abs(float(residuals[row])) for row in block), default=0.0)
        worst[equation.constraint] = max(worst.get(equation.constraint, 0.0), peak)
    return sorted(worst, key=lambda index: (-worst[index], index))


def _conflict_pair(
    equations: Sequence[_Equation], blocks: Sequence[range], residuals: np.ndarray
) -> tuple[int, int]:
    """Das Paar mit den größten Restfehlern.

    Bei mehr als zwei Beteiligten ist das kein vollständiges Bild, aber der
    ehrliche Einstieg: die beiden Bedingungen, an denen der Löser am
    weitesten scheitert, sind die, die man zuerst ansieht."""
    ranked = _worst_constraints(equations, blocks, residuals)
    first = ranked[0] if ranked else 0
    second = ranked[1] if len(ranked) > 1 else first
    return first, second


def _redundant_pair(
    constraints: Sequence[SketchConstraint],
    equations: Sequence[_Equation],
    blocks: Sequence[range],
    jacobian: np.ndarray,
    rank: int,
) -> tuple[int, int]:
    """Das Paar, das dasselbe festlegt.

    Kandidatin ist jede Bedingung, deren Entfernen den Rang nicht senkt —
    ihre Zeilen sagen nichts, was die übrigen nicht auch sagen. Zwei
    Kandidatinnen sind das Paar: jede macht die andere überflüssig. Bleibt
    nur eine (sie hängt an einer Kombination mehrerer), wird ihr die erste
    Bedingung zur Seite gestellt, die einen Zielpunkt mit ihr teilt — und
    zwar eine, die im Gleichungssystem steht: Ein Referenzmaß legt nichts
    fest und kann an keiner Redundanz beteiligt sein. Trägt jede Bedingung
    auch Eigenes bei (die Abhängigkeit verteilt sich über einen Verbund),
    wird die mit dem kleinsten eigenen Beitrag benannt — vorher stand hier
    ein ``(0, 0)``, das blind der ersten Bedingung der Skizze die Schuld
    gab, gleich ob sie beteiligt war."""
    measured: list[tuple[int, int]] = []  # (Rangverlust ohne sie, Index)
    for equation, block in zip(equations, blocks, strict=True):
        if equation.constraint is None:
            continue
        kept = [row for row in range(jacobian.shape[0]) if row not in block]
        loss = rank - int(np.linalg.matrix_rank(jacobian[kept]))
        measured.append((loss, equation.constraint))
    candidates = [index for loss, index in measured if loss == 0]
    if len(candidates) >= 2:
        return candidates[0], candidates[1]
    if not candidates and measured:
        candidates = [min(measured)[1]]
    if candidates:
        first = candidates[0]
        bearing = {index for _, index in measured}
        touched = set(constraints[first].targets)
        partner = next(
            (
                index
                for index, other in enumerate(constraints)
                if index != first and index in bearing and touched.intersection(other.targets)
            ),
            first,
        )
        return first, partner
    return 0, 0


def solve_sketch(sketch: Sketch, params: Mapping[str, float] | None = None) -> SolvedSketch:
    """Löst eine Skizze deterministisch gegen ihre Bedingungen (§30.1).

    Maße werden über die Parametergrammatik (§13) gegen ``params`` aufgelöst.
    Unterbestimmt liefert ein Ergebnis und zählt die Freiheitsgrade;
    überbestimmt oder widersprüchlich wirft :class:`SketchConflictError`
    mit dem kollidierenden Paar."""
    values = params or {}
    equations, anchors = _build_equations(sketch, values)
    variables = anchors.size

    if not sketch.elements:
        return SolvedSketch(elements=(), free_dof=0, max_residual=0.0)

    solution, residuals, jacobian = _solve(equations, anchors)
    max_residual = float(np.max(np.abs(residuals))) if residuals.size else 0.0
    rank = int(np.linalg.matrix_rank(jacobian)) if residuals.size else 0
    blocks = _row_blocks(equations)

    if max_residual > _TOL:
        first, second = _conflict_pair(equations, blocks, residuals)
        raise SketchConflictError(
            first,
            second,
            values={
                "first_kind": sketch.constraints[first].kind,
                "second_kind": sketch.constraints[second].kind,
                "residual": max_residual,
            },
        )

    if residuals.size and rank < residuals.size:
        first, second = _redundant_pair(sketch.constraints, equations, blocks, jacobian, rank)
        raise SketchConflictError(
            first,
            second,
            title=_("Eine Bedingung legt fest, was schon festliegt."),
            values={
                "first_kind": sketch.constraints[first].kind,
                "second_kind": sketch.constraints[second].kind,
            },
        )

    solved_points = solution.reshape(-1, 2)
    elements: list[SketchElement] = []
    offset = 0
    for element in sketch.elements:
        count = len(element.points)
        points = tuple(
            (float(solved_points[offset + i][0]), float(solved_points[offset + i][1]))
            for i in range(count)
        )
        # Das Kennzeichen reist mit: der Solver rechnet Hilfsgeometrie wie
        # jede andere — nur die Profilbildung übergeht sie, und die sieht
        # ausschließlich das gelöste Ergebnis.
        elements.append(
            SketchElement(kind=element.kind, points=points, construction=element.construction)
        )
        offset += count

    return SolvedSketch(
        elements=tuple(elements),
        free_dof=variables - rank,
        max_residual=max_residual,
    )
