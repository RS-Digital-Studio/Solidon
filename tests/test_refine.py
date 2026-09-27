"""Der Stapel der Rundformläufe nimmt nur weg, was nichts geliefert hätte (RM-209).

:func:`app.core.perceive.refine.exhausted` sagt für viele Kegel- und
Ringverfeinerungen zugleich, welcher Löserlauf sein Budget sicher ausschöpft;
die Erkennung lässt genau diese Läufe aus (``features._screened_fits``). Die
Zusage an den Kunden ist, dass kein Merkmal sich dadurch ändert — nach Art,
Zahl und Maß, Bit für Bit. Hier stehen die Regeln, die sie tragen:

* Der Stapel rechnet dieselben Residuen und Ableitungen wie die Einpassung.
* Er sagt nie „vergeblich" zu einem Lauf, der eine Antwort bringt.
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

from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

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
