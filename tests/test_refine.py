"""Der Stapel der Rundformläufe nimmt nur weg, was nichts geliefert hätte (RM-209).

:func:`app.core.perceive.refine.exhausted` sagt für viele Kegel- und
Ringverfeinerungen zugleich, welcher Löserlauf sein Budget sicher ausschöpft;
die Erkennung lässt genau diese Läufe aus (``features._screened_fits``). Die
Zusage an den Kunden ist, dass kein Merkmal sich dadurch ändert — nach Art,
Zahl und Maß, Bit für Bit. Hier stehen die Regeln, die sie tragen:

* Der Stapel rechnet dieselben Residuen und Ableitungen wie die Einpassung.
* Er sagt nie „vergeblich" zu einem Lauf, der eine Antwort bringt.
* Der Nachbau des Lösers (:func:`refine.solve`) rechnet Bit für Bit wie SciPy.
* Sein Urteil hängt nicht an der Reihenfolge der Probleme, ihrer Punkte oder
  daran, welche anderen Probleme im Stapel stehen.
* Jeder seiner Abstände kann allein ein Nein verhindern (Gegenproben).
* Mit dem Stapel findet die Erkennung dieselben Formen wie ohne ihn und ruft
  den Löser seltener — an einem Körper, an dem wirklich Läufe vergeblich sind.

Der Prüfkörper ist eine kleine verrauschte Beulenkugel, gebaut wie die
Freiform der Leistungstests: Ihre Splitter bringen Kegel- und Ringläufe, die
ihr Budget ausschöpfen, und solche, die antworten.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import trimesh
from scipy.optimize import least_squares

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import features, refine

MESHES = Path(__file__).parent / "data" / "meshes"


def bumpy_ball() -> MeshData:
    """Eine verrauschte Beulenkugel mit 10 000 Dreiecken — Splitter mit vergeblichen Läufen."""
    rng = np.random.default_rng(7)
    ball = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    vertices = np.asarray(ball.vertices, dtype=float).copy()
    unit = vertices / np.linalg.norm(vertices, axis=1)[:, None]
    centres = rng.normal(size=(40, 3))
    centres /= np.linalg.norm(centres, axis=1)[:, None]
    widths = rng.uniform(0.15, 0.5, size=40)
    heights = rng.uniform(-0.25, 0.25, size=40)
    scale = np.ones(len(vertices))
    for centre, width, height in zip(centres, widths, heights, strict=True):
        distance = np.arccos(np.clip(unit @ centre, -1.0, 1.0))
        scale += height * np.exp(-((distance / width) ** 2))
    scale += rng.normal(scale=0.01, size=len(vertices))
    rough = trimesh.Trimesh(vertices=vertices * scale[:, None], faces=ball.faces, process=False)
    return MeshData.of(rough.simplify_quadric_decimation(face_count=10_000))


@dataclass(frozen=True)
class Run:
    """Ein Löserlauf der Erkennung: die Aufgabe für den Stapel und der echte Lauf."""

    problem: refine.Problem
    residual: Any
    jacobian: Any
    nfev: int


@pytest.fixture(scope="module")
def bumpy() -> MeshData:
    return bumpy_ball()


@pytest.fixture(scope="module")
def runs(bumpy: MeshData) -> list[Run]:
    """Jeder Kegel- und Ringlauf der Erkennung am Prüfkörper, ohne Stapel gerechnet."""
    captured: list[Run] = []
    current: list[refine.Problem] = []
    with pytest.MonkeyPatch.context() as patch:
        plain_cone, plain_torus = features._cone_from_plan, features._torus_from_plan
        plain_fit = features._refined_fit

        def cone(plan: Any, check: Any, *, exhausted: bool = False) -> Any:
            current[:] = [plan.problem()]
            return plain_cone(plan, check, exhausted=exhausted)

        def torus(plan: Any, check: Any, *, exhausted: bool = False) -> Any:
            current[:] = [plan.problem()]
            return plain_torus(plan, check, exhausted=exhausted)

        def fit(initial: Any, residual: Any, check: Any, jacobian: Any = None) -> Any:
            if current and jacobian is not None and len(initial) == len(current[0].initial):
                result = least_squares(
                    residual,
                    initial,
                    jac=jacobian,
                    ftol=features.ROUND_FIT_PRECISION,
                    xtol=features.ROUND_FIT_PRECISION,
                    gtol=features.ROUND_FIT_PRECISION,
                    max_nfev=features.ROUND_FIT_EVALUATIONS,
                )
                captured.append(Run(current[0], residual, jacobian, int(result.nfev)))
                current.clear()
            return plain_fit(initial, residual, check, jacobian)

        patch.setattr(features, "_cone_from_plan", cone)
        patch.setattr(features, "_torus_from_plan", torus)
        patch.setattr(features, "_refined_fit", fit)
        patch.setattr(refine, "exhausted", lambda problems, **_options: [False] * len(problems))
        features.forget_cache()
        features.detect(bumpy)
    features.forget_cache()
    return captured


def verdicts_of(problems: list[refine.Problem], monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Das Urteil des Stapels, auch für Gruppen unter :data:`refine.MIN_BATCH`."""
    monkeypatch.setattr(refine, "MIN_BATCH", 1)
    return refine.exhausted(
        problems,
        precision=features.ROUND_FIT_PRECISION,
        evaluations=features.ROUND_FIT_EVALUATIONS,
    )


def test_the_body_brings_runs_that_answer_and_runs_that_do_not(runs: list[Run]) -> None:
    """Die Voraussetzung aller Proben hier: beide Sorten Lauf, bei Kegel und Ring."""
    for kind in (refine.ConeProblem, refine.TorusProblem):
        mine = [run for run in runs if isinstance(run.problem, kind)]
        assert sum(run.nfev >= features.ROUND_FIT_EVALUATIONS for run in mine) >= 5, kind
        assert sum(run.nfev < features.ROUND_FIT_EVALUATIONS for run in mine) >= 20, kind


def test_the_batch_computes_the_residuals_of_the_fit(runs: list[Run]) -> None:
    """Dieselben Formeln wie ``_cone_from_plan`` und ``_torus_from_plan``, auf die Rundung genau.

    Wer eine Residue oder Ableitung der Einpassung ändert und den Stapel
    vergisst, sagt ihm einen anderen Lauf vorher, als der Löser rechnet.
    """
    rng = np.random.default_rng(3)
    for run in runs[::7]:
        problem = run.problem
        cone = isinstance(problem, refine.ConeProblem)
        rows = refine._padded_rows(len(problem.points))
        data, _size = (
            refine._cone_data([problem], rows) if cone else refine._torus_data([problem], rows)
        )
        data.pop("initial")
        evaluate = refine._cone_residual if cone else refine._torus_residual
        for values in (
            problem.initial,
            problem.initial * (1.0 + 1e-3 * rng.standard_normal(len(problem.initial))),
        ):
            expected_f = run.residual(values.copy())
            expected_j = run.jacobian(values.copy())
            f, jacobian = evaluate(values[None, :], data, True)
            assert jacobian is not None
            used = len(problem.points)
            np.testing.assert_allclose(f[0, :used], expected_f[:used], rtol=1e-12, atol=1e-12)
            np.testing.assert_allclose(
                jacobian[0, :used], expected_j[:used], rtol=1e-10, atol=1e-12
            )
            if cone and problem.apex is not None:  # type: ignore[union-attr]
                np.testing.assert_allclose(f[0, rows:], expected_f[used:], rtol=1e-12, atol=1e-12)
                np.testing.assert_allclose(
                    jacobian[0, rows:], expected_j[used:], rtol=1e-12, atol=1e-12
                )
            assert not f[0, used:rows].any() and not jacobian[0, used:rows].any()


def test_the_batch_never_turns_away_a_run_that_answers(
    runs: list[Run], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jedes Nein des Stapels ist ein Lauf, der sein Budget wirklich ausschöpft.

    Und es gibt Neins — sonst wäre die Probe über die leere Menge.
    """
    verdicts = verdicts_of([run.problem for run in runs], monkeypatch)
    wrong = [
        run.nfev
        for run, said in zip(runs, verdicts, strict=True)
        if said and run.nfev < features.ROUND_FIT_EVALUATIONS
    ]
    assert not wrong, f"the batch turned away runs that answer after {wrong} evaluations"
    vain = sum(run.nfev >= features.ROUND_FIT_EVALUATIONS for run in runs)
    assert sum(verdicts) >= vain // 2, f"only {sum(verdicts)} of {vain} vain runs recognised"


def _same_bits(first: Any, second: Any) -> bool:
    first, second = np.asarray(first), np.asarray(second)
    return bool(
        first.shape == second.shape
        and first.dtype == second.dtype
        and first.tobytes() == second.tobytes()
    )


def test_the_solver_computes_what_scipy_computes(runs: list[Run]) -> None:
    """:func:`refine.solve` ist ``least_squares`` auf diesem Weg — Bit für Bit.

    Parameter, Residuen, Ableitung, Auswertungszahl und Status an jedem
    Kegel- und Ringlauf des Prüfkörpers, vergeblich oder nicht. Hebt jemand
    SciPy und ändert sich dort ein Schritt, fällt es hier auf und nicht
    erst in einem Merkmal.
    """
    for run in runs:
        start = np.asarray(run.problem.initial)
        expected = least_squares(
            run.residual,
            start,
            jac=run.jacobian,
            ftol=features.ROUND_FIT_PRECISION,
            xtol=features.ROUND_FIT_PRECISION,
            gtol=features.ROUND_FIT_PRECISION,
            max_nfev=features.ROUND_FIT_EVALUATIONS,
        )
        mine = refine.solve(
            run.residual,
            run.jacobian,
            start,
            precision=features.ROUND_FIT_PRECISION,
            evaluations=features.ROUND_FIT_EVALUATIONS,
        )
        assert (mine.nfev, mine.status, mine.success) == (
            expected.nfev,
            expected.status,
            expected.success,
        )
        assert _same_bits(mine.x, expected.x)
        assert _same_bits(mine.fun, expected.fun)
        assert _same_bits(mine.jac, expected.jac)


def _reversed_points(problem: refine.Problem) -> refine.Problem:
    """Dieselbe Aufgabe mit umgekehrter Punktfolge — die Spitze bleibt dieselbe Zeile."""
    return replace(problem, points=np.ascontiguousarray(problem.points[::-1]))


def test_the_verdict_does_not_depend_on_any_order(
    runs: list[Run], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Weder Folge der Probleme noch ihrer Punkte, noch Nachbarn im Stapel ändern ein Urteil.

    Die Punktfolge folgt der Nummerierung der Ecken und Dreiecke: Ein anders
    geschriebenes Netz stellt dieselbe Aufgabe in anderer Folge.
    """
    problems = [run.problem for run in runs]
    verdicts = verdicts_of(problems, monkeypatch)
    order = np.random.default_rng(11).permutation(len(problems))
    shuffled = verdicts_of([problems[index] for index in order], monkeypatch)
    assert [
        shuffled[int(np.flatnonzero(order == index)[0])] for index in range(len(problems))
    ] == verdicts
    turned = verdicts_of([_reversed_points(problem) for problem in problems], monkeypatch)
    assert turned == verdicts
    half = problems[::2]
    assert verdicts_of(half, monkeypatch) == verdicts[::2]


@pytest.mark.parametrize(
    ("guard", "impossible"),
    (
        ("DECISION_MARGIN", 1.0),
        ("STOP_MARGIN_DECADES", 99.0),
        ("SHADOW_AGREEMENT", -1.0),
    ),
)
def test_every_margin_can_refuse_on_its_own(
    runs: list[Run], monkeypatch: pytest.MonkeyPatch, guard: str, impossible: float
) -> None:
    """Die Gegenprobe je Abstand: Ist er unerfüllbar, sagt der Stapel zu keinem Lauf nein."""
    problems = [run.problem for run in runs]
    assert any(verdicts_of(problems, monkeypatch)), "without the change the batch recognises runs"
    monkeypatch.setattr(refine, guard, impossible)
    assert not any(verdicts_of(problems, monkeypatch)), f"{guard} is not asked"


def test_a_cancel_stops_the_batch(runs: list[Run], monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Abbruch erreicht den Stapel in jeder Runde (§2.8)."""
    monkeypatch.setattr(refine, "MIN_BATCH", 1)
    calls = [0]

    def cancel() -> None:
        calls[0] += 1
        if calls[0] > 3:
            raise OperationCancelled()

    with pytest.raises(OperationCancelled):
        refine.exhausted(
            [run.problem for run in runs],
            precision=features.ROUND_FIT_PRECISION,
            evaluations=features.ROUND_FIT_EVALUATIONS,
            check_cancelled=cancel,
        )


def _fits(mesh: MeshData) -> str:
    """Alles, was die Fleckensuche hergibt — jede Form, auch jeder Kandidat, Bit für Bit."""
    features.forget_cache()
    fitted = features._fitted(mesh)
    found = features.detect(mesh)
    rows = [repr(fitted)]
    for name, feature in sorted(found.items()):
        rows.append(
            repr((name, feature.kind, sorted(feature.params.items()), feature.face_indices))
        )
    rows.append(repr((features.freeform_dropped(mesh), features.recognised_as_freeform(mesh))))
    return "\n".join(rows)


@pytest.fixture
def counted(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    """Wie oft die Erkennung den echten Löser ruft."""
    calls = [0]
    plain = features._refined_fit

    def fit(initial: Any, residual: Any, check: Any, jacobian: Any = None) -> Any:
        calls[0] += 1
        return plain(initial, residual, check, jacobian)

    monkeypatch.setattr(features, "_refined_fit", fit)
    yield calls
    features.forget_cache()


@pytest.mark.parametrize(
    "name",
    (
        "bumpy",
        "post_with_fillet.stl",
        "plate_countersunk.stl",
        "torus_ring.stl",
        "sphere_socket.stl",
        "generated_figure.stl",
    ),
)
def test_the_screen_keeps_every_shape_and_saves_runs(
    name: str, bumpy: MeshData, counted: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mit Stapel dieselben Formen, Kandidaten und Freiformauskunft wie ohne, nie mehr Läufe.

    Am Prüfkörper, an dem Läufe wirklich vergeblich sind, spart er welche;
    die Korpuskörper zeigen, dass er dort, wo alles antwortet, nichts nimmt.
    """
    if name == "bumpy":
        mesh = bumpy
    else:
        mesh = normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh
    monkeypatch.setattr(refine, "MIN_BATCH", 1)
    screened = _fits(mesh)
    with_screen = counted[0]
    counted[0] = 0
    with monkeypatch.context() as patch:
        patch.setattr(refine, "exhausted", lambda problems, **_options: [False] * len(problems))
        plain = _fits(mesh)
    without_screen = counted[0]
    assert screened == plain, "the screen changed what the recognition finds"
    assert with_screen <= without_screen
    if name == "bumpy":
        assert with_screen < without_screen - 20, "the screen must take vain runs away"


def test_the_shipped_batch_size_takes_runs_away(
    bumpy: MeshData, counted: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Betriebsweg: Mit dem ausgelieferten :data:`refine.MIN_BATCH` spart der Stapel Läufe.

    Die Proben oben setzen die Gruppengrenze auf eins, damit auch kleine Gruppen
    ein Urteil bekommen. Ob die Anwendung selbst etwas auslässt, sagt nur ein
    Lauf mit der Grenze, wie sie ausgeliefert wird (Review stapel: 41 von 792
    Läufen an diesem Körper).
    """
    screened = _fits(bumpy)
    with_screen = counted[0]
    counted[0] = 0
    with monkeypatch.context() as patch:
        patch.setattr(refine, "exhausted", lambda problems, **_options: [False] * len(problems))
        plain = _fits(bumpy)
    assert screened == plain
    assert with_screen < counted[0] - 20, "the shipped screen takes no vain run away"


def _both(fun: Any, jac: Any, start: np.ndarray, precision: float, budget: int) -> None:
    """``solve`` und ``least_squares`` an derselben Aufgabe, Bit für Bit."""
    expected = least_squares(
        fun, start, jac=jac, ftol=precision, xtol=precision, gtol=precision, max_nfev=budget
    )
    mine = refine.solve(fun, jac, start, precision=precision, evaluations=budget)
    assert (mine.nfev, mine.status) == (expected.nfev, expected.status)
    assert _same_bits(mine.x, expected.x)
    assert _same_bits(mine.fun, expected.fun)
    assert _same_bits(mine.jac, expected.jac)


def _linear(matrix: np.ndarray, target: np.ndarray) -> tuple[Any, Any]:
    """Residuen und Ableitung einer linearen Aufgabe ``matrix @ x - target``."""

    def residual(x: np.ndarray) -> np.ndarray:
        return np.asarray(matrix @ x - target, dtype=float)

    def slope(_x: np.ndarray) -> np.ndarray:
        return matrix

    return residual, slope


def _valley(x: np.ndarray) -> np.ndarray:
    return np.array([10.0 * (x[1] - x[0] * x[0]), 1.0 - x[0]])


def _valley_slope(x: np.ndarray) -> np.ndarray:
    return np.array([[-20.0 * x[0], 10.0], [-1.0, 0.0]])


@pytest.mark.parametrize("budget", (1, 2, 3, 5, 100))
def test_the_solver_follows_scipy_on_its_edges(budget: int) -> None:
    """Die Zweige, die kein Kegel und kein Ring der Beulenkugel berührt.

    Voller und fehlender Rang (doppelte Spalte, weniger Beobachtungen als
    Größen) — dort startet die Newton-Suche des Vertrauensbereichs neu —,
    Start null, knappe Budgets und Probepunkte, an denen die Residuen nicht
    endlich sind. Hebt jemand SciPy und ändert sich einer dieser Schritte,
    fällt es hier auf.
    """
    rng = np.random.default_rng(budget)
    precision = features.ROUND_FIT_PRECISION
    crossed = [0]
    for _case in range(6):
        matrix = rng.standard_normal((8, 3))
        target = rng.standard_normal(8)
        doubled = np.column_stack((matrix, matrix[:, 0]))
        wide = rng.standard_normal((2, 4))
        _both(*_linear(matrix, target), np.zeros(3), precision, budget)
        _both(*_linear(doubled, target), rng.standard_normal(4), precision, budget)
        _both(*_linear(wide, np.ones(2)), rng.standard_normal(4), precision, budget)
        _both(_valley, _valley_slope, rng.uniform(-2.0, 2.0, 2), precision, budget)
        centre, wall = rng.uniform(-6.0, 6.0, 3), float(rng.uniform(0.5, 3.0))

        def fenced(x: np.ndarray, c: np.ndarray = centre, w: float = wall) -> np.ndarray:
            if np.abs(x).max() > w:
                crossed[0] += 1
                return np.array([np.inf, 0.0, np.nan, 0.0])
            return np.r_[x - c, 0.3 * x[0] * x[1]]

        def fenced_slope(x: np.ndarray) -> np.ndarray:
            return np.vstack((np.eye(3), [[0.3 * x[1], 0.3 * x[0], 0.0]]))

        _both(fenced, fenced_slope, rng.uniform(-0.2, 0.2, 3), 1e-10, budget)
    if budget >= 5:
        assert crossed[0] > 0, "the case with residuals that are not finite must be reached"


def _outcomes(
    problems: list[refine.Problem],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Der Stapellauf je Problem: sicher, Status, letzte Parameter, Abstand zum Schatten.

    Gebündelt wie in :func:`refine.exhausted` (Art und aufgefüllte Zeilenzahl),
    aber ohne Gruppengrenze und Blockteilung.
    """
    groups: dict[tuple[str, int], list[int]] = {}
    for index, problem in enumerate(problems):
        key = (type(problem).__name__, refine._padded_rows(len(problem.points)))
        groups.setdefault(key, []).append(index)
    safe = np.zeros(len(problems), dtype=bool)
    status = np.zeros(len(problems), dtype=np.int64)
    apart = np.zeros(len(problems))
    last = np.zeros((len(problems), 7))
    for (kind, rows), members in groups.items():
        chosen = [problems[index] for index in members]
        cone = kind == refine.ConeProblem.__name__
        data, size = refine._cone_data(chosen, rows) if cone else refine._torus_data(chosen, rows)
        stacked = {key: np.concatenate((value, value)) for key, value in data.items()}
        outcome = refine._run(
            stacked,
            size,
            refine._cone_residual if cone else refine._torus_residual,
            features.ROUND_FIT_PRECISION,
            features.ROUND_FIT_EVALUATIONS,
            None,
        )
        count = len(members)
        where = np.asarray(members)
        safe[where] = outcome.safe[:count] & outcome.safe[count:]
        status[where] = outcome.status[:count]
        apart[where] = outcome.apart
        last[where, :size] = outcome.x[:count]
    return safe, status, apart, last


def test_the_batch_walks_the_path_of_the_solver(runs: list[Run]) -> None:
    """Der Plan des Stapels geht den Weg des echten Lösers, Auswertung für Auswertung.

    An jedem Lauf, der sein Budget ausschöpft und dem der Stapel bis zum Ende
    folgt, stehen beide nach hundert Auswertungen an derselben Stelle, bis auf
    Rundung (``1e-9`` relativ; gemessen höchstens ``3e-11``). Ein Stapel, der
    einen anderen Algorithmus rechnet (etwa eine andere Grenze der
    Newton-Suche), trennt sich davon um Prozente. Und kein Lauf, der antwortet,
    endet im Stapel am Budget.
    """
    _safe, status, _apart, last = _outcomes([run.problem for run in runs])
    followed = 0
    for index, run in enumerate(runs):
        if run.nfev < features.ROUND_FIT_EVALUATIONS:
            assert status[index] != 0, f"run {index} answers after {run.nfev}, the batch ran dry"
            continue
        if status[index] != 0:
            continue
        real = refine.solve(
            run.residual,
            run.jacobian,
            np.asarray(run.problem.initial),
            precision=features.ROUND_FIT_PRECISION,
            evaluations=features.ROUND_FIT_EVALUATIONS,
        )
        size = len(real.x)
        scale = max(1.0, float(np.abs(real.x).max()))
        gap = float(np.abs(last[index, :size] - real.x).max()) / scale
        assert gap <= 1e-9, f"run {index}: the batch left the path of the solver by {gap:.3g}"
        followed += 1
    assert followed >= 20, f"only {followed} vain runs followed to their end"


def test_the_shadow_is_disturbed(runs: list[Run], monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Schatten weicht vom Plan ab, sonst prüft sein Vergleich nichts.

    Mit :data:`refine.SHADOW_NOISE` trennen sich Plan und Schatten messbar,
    ohne Störung fallen sie Bit für Bit zusammen.
    """
    problems = [run.problem for run in runs if run.nfev >= features.ROUND_FIT_EVALUATIONS]
    _safe, _status, apart, _last = _outcomes(problems)
    assert (apart > 0.0).sum() >= len(problems) // 2
    monkeypatch.setattr(refine, "SHADOW_NOISE", 0.0)
    _safe, _status, quiet, _last = _outcomes(problems)
    assert not quiet.any()


def _guard_case() -> refine.TorusProblem:
    """Der Fall aus der Review-Sonde H (``tests/data/refine_guard_case.json``)."""
    case = json.loads(
        (Path(__file__).parent / "data" / "refine_guard_case.json").read_text("utf-8")
    )
    return refine.TorusProblem(
        points=np.asarray(case["points"], dtype=float),
        axis=np.asarray(case["axis"], dtype=float),
        first=np.asarray(case["first"], dtype=float),
        second=np.asarray(case["second"], dtype=float),
        initial=np.asarray(case["initial"], dtype=float),
    )


class _CapturedError(Exception):
    """Hält die Ringeinpassung an, sobald sie ihren Löser ruft."""


def test_the_guard_case_is_a_run_that_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Voraussetzung der Wächterprobe: Der echte Ringlauf dort antwortet.

    Residuen und Ableitung kommen aus der Ringeinpassung selbst
    (``features._torus_from_plan``); der Lauf endet nach 97 Auswertungen über
    ``xtol``, drei vor dem Budget.
    """
    problem = _guard_case()
    start = problem.initial
    plan = features._TorusPlan(
        support=cast(Any, None),
        initial=features.TorusFit(
            axis=cast(Any, tuple(problem.axis)),
            centre=cast(Any, tuple(start[:3])),
            ring_radius=float(start[5]),
            tube_radius=float(start[6]),
            residual=0.0,
            recess=False,
        ),
        origin=np.zeros(3),
        scale=1.0,
        initial_axis=problem.axis,
        first=problem.first,
        second=problem.second,
        solving=problem.points,
    )
    captured: list[tuple[np.ndarray, Any, Any]] = []

    def capture(initial: Any, residual: Any, check: Any, jacobian: Any = None) -> Any:
        captured.append((np.asarray(initial), residual, jacobian))
        raise _CapturedError

    monkeypatch.setattr(features, "_refined_fit", capture)
    with pytest.raises(_CapturedError):
        features._torus_from_plan(plan, None)
    initial, residual, jacobian = captured[0]
    assert _same_bits(initial, start)
    real = refine.solve(
        residual,
        jacobian,
        initial,
        precision=features.ROUND_FIT_PRECISION,
        evaluations=features.ROUND_FIT_EVALUATIONS,
    )
    assert (real.nfev, real.status) == (97, 3)


@pytest.mark.parametrize(
    ("only", "off"),
    (
        ("DECISION_MARGIN", {"STOP_MARGIN_DECADES": -np.inf, "SHADOW_AGREEMENT": np.inf}),
        ("STOP_MARGIN_DECADES", {"DECISION_MARGIN": -np.inf, "SHADOW_AGREEMENT": np.inf}),
        ("SHADOW_AGREEMENT", {"DECISION_MARGIN": -np.inf, "STOP_MARGIN_DECADES": -np.inf}),
    ),
)
def test_each_margin_alone_keeps_the_guard_case(
    only: str, off: dict[str, float], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wo ein Stapel ohne Schutz falsch „vergeblich“ sagt, hält jeder Abstand allein.

    Ohne alle drei sagt er „vergeblich“ (Gegenprobe unten); mit nur einem,
    dem genannten, sagt er nichts. Der Schatten schützt nur, weil er gestört
    wird: Ungestört sagt er dasselbe wie der Plan.
    """
    problem = _guard_case()
    for name, value in off.items():
        monkeypatch.setattr(refine, name, value)
    assert verdicts_of([problem], monkeypatch) == [False], f"{only} alone does not hold"
    if only == "SHADOW_AGREEMENT":
        monkeypatch.setattr(refine, "SHADOW_NOISE", 0.0)
        assert verdicts_of([problem], monkeypatch) == [True]


def test_without_any_margin_the_guard_case_is_turned_away(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenprobe: Ohne jeden Abstand sagt der Stapel an diesem Fall falsch „vergeblich“."""
    problem = _guard_case()
    monkeypatch.setattr(refine, "DECISION_MARGIN", -np.inf)
    monkeypatch.setattr(refine, "STOP_MARGIN_DECADES", -np.inf)
    monkeypatch.setattr(refine, "SHADOW_AGREEMENT", np.inf)
    assert verdicts_of([problem], monkeypatch) == [True]


def test_no_verdict_turns_under_platform_noise(
    runs: list[Run], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rechnet eine andere Maschine in der letzten Stelle anders, kippt kein Urteil.

    Der Stapel rechnet über BLAS, LAPACK und Winkelfunktionen. Das ist erlaubt,
    weil sein Nein Abstand zu jedem Zweig und Abbruch hält und der Schatten es
    bestätigt (``schichtanalyse.md``, ``kern.md``). Unter dem Rauschen aus
    ``test_platform_identity`` (ein ULP auf jedem dieser Wege) bleibt jedes
    Urteil, wie es ist, und keines trifft einen Lauf, der antwortet.
    """
    from tests.test_platform_identity import platform_noise

    problems = [run.problem for run in runs]
    quiet = verdicts_of(problems, monkeypatch)
    with platform_noise():
        noisy = verdicts_of(problems, monkeypatch)
    assert noisy == quiet
    assert not any(
        said and run.nfev < features.ROUND_FIT_EVALUATIONS
        for said, run in zip(noisy, runs, strict=True)
    )
