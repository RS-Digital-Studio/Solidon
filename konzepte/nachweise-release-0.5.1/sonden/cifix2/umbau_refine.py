"""Baut die Wächterprobe in tests/test_refine.py auf Lagen um (Runde 2)."""

from pathlib import Path

p = Path(r"F:\3D Druck.review-051\wt-cifix2\tests\test_refine.py")
s = p.read_text(encoding="utf-8")
start = s.index("#: Wie weit der echte Lauf am Wächterfall um das Budget streut")
end = s.index("def test_no_verdict_turns_under_platform_noise(")
new = '''#: Wie weit der echte Lauf am Wächterfall um das Budget streut, in
#: Auswertungen. Gemessen: 97 hier, 98 unter Linux und 100 ohne Antwort unter
#: Windows in der CI, 97 bis 100 in den Lagen aus :data:`GUARD_PATTERNS`
#: (``sonden/cifix2``, Paket CI-Fehlschläge 0.5.1).
GUARD_EDGE = 10

#: Wie viele feste Rauschmuster (``platform_noise(pattern)``) neben der
#: eigenen Rechnung der Maschine die **Lagen** des Wächterfalls bilden.
#:
#: Der Fall steht am letzten Bit: Ob der Stapel ohne Abstände „vergeblich“
#: sagt und ob der echte Lauf im Budget antwortet, entscheidet die Rundung
#: der Maschine — hier sagt er es, auf einem Linux-Runner der CI nicht. Eine
#: Zusicherung über eine einzige Lage gilt deshalb nur auf der Maschine, auf
#: der sie gemessen wurde. Jedes Muster verschiebt die plattformabhängigen
#: Rechnungen um ein ULP, wie eine andere Maschine es täte, und zwar **auf**
#: der Rechnung der laufenden Maschine: Jede Maschine zieht so ihre eigenen
#: Lagen um dieselbe Kante. Gemessen an 49 Lagen (``sonden/cifix2``): ohne
#: Abstände 15 falsche Neins, mit allen dreien keines, jeder Abstand allein
#: verhindert 11 bis 15 davon.
GUARD_PATTERNS = 48

#: Wie jeder Abstand ausgeschaltet wird.
MARGINS_OFF: dict[str, float] = {
    "DECISION_MARGIN": -np.inf,
    "STOP_MARGIN_DECADES": -np.inf,
    "SHADOW_AGREEMENT": np.inf,
}


def _guard_lagen() -> Iterator[contextlib.AbstractContextManager[None]]:
    """Die eigene Rechnung der Maschine, dann jedes Rauschmuster."""
    from tests.test_platform_identity import platform_noise

    yield contextlib.nullcontext()
    for pattern in range(GUARD_PATTERNS):
        yield platform_noise(pattern)


def _guard_solver(problem: refine.TorusProblem) -> tuple[np.ndarray, Any, Any]:
    """Startwert, Residuen und Ableitung aus der Ringeinpassung selbst.

    ``features._torus_from_plan`` baut sie und ruft den Löser; der wird hier
    abgefangen, damit der Test denselben Lauf rechnet wie die Einpassung.
    """
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

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(features, "_refined_fit", capture)
        with pytest.raises(_CapturedError):
            features._torus_from_plan(plan, None)
    return captured[0]


def _real_run(solver: tuple[np.ndarray, Any, Any], evaluations: int) -> Any:
    """Der echte Lauf der Einpassung mit diesem Budget."""
    initial, residual, jacobian = solver
    return refine.solve(
        residual,
        jacobian,
        initial,
        precision=features.ROUND_FIT_PRECISION,
        evaluations=evaluations,
    )


def _verdict(problem: refine.TorusProblem, monkeypatch: pytest.MonkeyPatch, **off: float) -> bool:
    """Das Urteil des Stapels, mit den genannten Größen ersetzt."""
    with monkeypatch.context() as patch:
        for name, value in off.items():
            patch.setattr(refine, name, value)
        return verdicts_of([problem], patch)[0]


def _false_noes(problem: refine.TorusProblem, monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """Die Lagen, in denen der Stapel ohne Abstände falsch „vergeblich“ sagt.

    Falsch heißt: Der echte Lauf antwortet in derselben Lage im Budget.
    Gegeben wird die Nummer der Lage, **während sie gilt** — der Aufrufer
    fragt darin weiter. Er schließt den Erzeuger (``contextlib.closing``),
    sonst bliebe das Rauschen nach einem vorzeitigen Ende stehen.
    """
    solver = _guard_solver(problem)
    for number, lage in enumerate(_guard_lagen()):
        with lage:
            if not _verdict(problem, monkeypatch, **MARGINS_OFF):
                continue
            if _real_run(solver, features.ROUND_FIT_EVALUATIONS).status == 0:
                continue
            yield number


def test_the_guard_case_is_a_run_that_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Voraussetzung der Wächterprobe: Der echte Ringlauf dort antwortet, knapp am Budget.

    Wie viele Auswertungen der Lauf braucht, hängt an der letzten Stelle der
    Maschine (:data:`GUARD_EDGE`) — hier endet er drei vor dem Budget über
    ``xtol``, anderswo knapp dahinter. Zugesichert wird, was auf jeder gilt:
    Mit Luft im Budget antwortet er, und zwar nahe dessen Grenze, sodass ein
    Nein des Stapels ohne Abstand dort am letzten Bit hängt. Mit allen
    Abständen sagt der Stapel in **keiner** Lage „vergeblich“
    (:data:`GUARD_PATTERNS`) — das ist der Schutz, den das Produkt trägt.
    """
    problem = _guard_case()
    solver = _guard_solver(problem)
    assert _same_bits(solver[0], problem.initial)
    budget = features.ROUND_FIT_EVALUATIONS
    # Das Budget begrenzt den Weg nicht, es beendet ihn nur: Mit mehr Luft
    # geht der Löser dieselben Schritte und hält, wo er antwortet.
    real = _real_run(solver, budget + 4 * GUARD_EDGE)
    assert real.status != 0, f"the real run does not answer ({real.nfev}, {real.status})"
    assert abs(real.nfev - budget) <= GUARD_EDGE, (
        f"the real run answers after {real.nfev}, far from the budget of {budget}: "
        "the case no longer guards anything"
    )
    said = []
    for number, lage in enumerate(_guard_lagen()):
        with lage:
            if _verdict(problem, monkeypatch):
                said.append(number)
    assert not said, f"with the margins the batch says 'in vain' in the lagen {said}"


def test_without_any_margin_the_guard_case_is_turned_away(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenprobe: Ohne jeden Abstand sagt der Stapel an diesem Fall falsch „vergeblich“.

    Nicht in jeder Lage — der Fall steht am letzten Bit —, aber in einer der
    Lagen, die jede Maschine um ihre eigene Rechnung zieht
    (:data:`GUARD_PATTERNS`). Gemessen: in 15 von 49.
    """
    problem = _guard_case()
    with contextlib.closing(_false_noes(problem, monkeypatch)) as found:
        first = next(found, None)
    assert first is not None, "without margins no lage says 'in vain' while the real run answers"


@pytest.mark.parametrize("only", sorted(MARGINS_OFF))
def test_each_margin_alone_keeps_the_guard_case(
    only: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jeder Abstand wirkt: In einer Lage mit falschem Nein verhindert er es allein.

    Nicht in jeder — ein einzelner Abstand hielt an 49 Lagen 11 bis 15 der 15
    falschen Neins auf; erst alle drei zusammen halten jedes
    (:func:`test_the_guard_case_is_a_run_that_answers`). Wer einen Abstand
    ausschaltet, macht seinen Fall hier rot. Der Schatten schützt nur, weil er
    gestört wird: Ungestört sagt er in derselben Lage dasselbe wie der Plan.
    """
    problem = _guard_case()
    alone = {name: value for name, value in MARGINS_OFF.items() if name != only}
    with contextlib.closing(_false_noes(problem, monkeypatch)) as found:
        for number in found:
            if _verdict(problem, monkeypatch, **alone):
                continue
            if only == "SHADOW_AGREEMENT":
                assert _verdict(problem, monkeypatch, **alone, SHADOW_NOISE=0.0), (
                    f"lage {number}: an undisturbed shadow agrees with the plan"
                )
            return
    pytest.fail(f"{only} alone prevents no false 'in vain' in any lage")


'''
s = s[:start] + new + s[end:]
old_imports = "import json\nfrom collections.abc import Iterator\n"
assert s.count(old_imports) == 1
s = s.replace(old_imports, "import contextlib\nimport json\nfrom collections.abc import Iterator\n")
p.write_text(s, encoding="utf-8", newline="")
print("ok")
