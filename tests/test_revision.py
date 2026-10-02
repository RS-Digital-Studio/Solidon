"""Den Verlauf umbauen, ohne einen Bezug still umzubiegen (RM-188 P7.1 bis P7.3).

Einfügen, Umsortieren, Aus- und Einschalten an echten Operationen beider
Kerne: Der Vorschlag wird isoliert gerechnet, und erst ein gültiges Ergebnis
ersetzt die Folge (``scene.revision``). Die Sollwerte kommen aus den
Parametern der Schritte selbst — Lage und Durchmesser jeder Bohrung stehen in
ihrem Entwurf —, nicht aus dem Ergebnis, das geprüft wird.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.core.errors import AmbiguityError, UserError
from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.scene.project import load, new_project, save
from app.core.scene.revision import commit, dependencies, revise
from app.core.scene.serialise import document_to_data
from app.core.types import Document, FeatureRef, Fit, Profile, ReferenceSight

#: Die beiden Bohrungen der kleinen Platte: links (A) und rechts (C), aus ihren Entwürfen.
LEFT_X = -20.0
RIGHT_X = 20.0
#: Der Enddurchmesser von „Bohrung vergrößern" — der Wert im Schritt.
WIDENED = 8.0
#: Der Durchmesser beider Bohrungen, bevor eine vergrößert wird.
DRILLED = 5.0

KERNELS = {
    "mesh": ("create_box", "drill_hole"),
    "brep": ("create_brep_box", "drill_brep_hole"),
}

FIT_NAMES = ["Passung", "RM218: Bohrung B und Prüfpin", ":a::b:"]


def _plate(kernel: str, *, first_x: float = LEFT_X, second_x: float = RIGHT_X) -> History:
    """Quader 80 × 40 × 10 mit zwei Bohrungen Ø 5 — die erste bei ``first_x``."""
    box, drill = KERNELS[kernel]
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader", [OperationDraft(op=box, params={"width": 80.0, "depth": 40.0, "height": 10.0})]
    )
    for seed, x in ((1, first_x), (2, second_x)):
        history.apply(
            "Bohrung",
            [
                OperationDraft(
                    op=drill,
                    inputs=("obj_1",),
                    params={"diameter": DRILLED, "x": x, "y": 0.0, "z": 10.0, "depth": 10.0},
                    seed=seed,
                )
            ],
        )
    return history


def _runner(profile: Profile) -> tuple[ResultCache, object]:
    cache = ResultCache()

    def run(document: Document) -> object:
        return evaluate(document, profile, cache=cache)

    return cache, run


def _holes(result: object) -> dict[float, float]:
    """Durchmesser je x-Lage der Bohrungen — gerundet auf die Anzeige."""
    features = result.scene.objects["obj_1"].features  # type: ignore[attr-defined]
    return {
        round(float(feature.params["centre"][0]), 1): round(float(feature.params["diameter"]), 1)
        for feature in features.values()
        if feature.kind == "hole"
    }


def _name_at(result: object, x: float) -> str:
    features = result.scene.objects["obj_1"].features  # type: ignore[attr-defined]
    return next(
        name
        for name, feature in features.items()
        if feature.kind == "hole" and abs(float(feature.params["centre"][0]) - x) < 1e-3
    )


def _document_without_numbering(history: History) -> dict[str, object]:
    """Der Projektinhalt nach Strg+Z; fortlaufende Zähler sind kein Zustand."""
    data = document_to_data(history.document)
    data.pop("numbering", None)
    return data


def _widen(history: History, name: str) -> None:
    history.apply(
        "Vergrößern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"at_feature": name, "diameter": WIDENED},
            )
        ],
    )


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_moving_a_hole_before_another_keeps_the_resize_on_its_hole(
    profile: Profile, kernel: str
) -> None:
    """P7.2: Die Namen tauschen, der Verweis folgt seiner Bohrung.

    **Die Gegenprobe steht im Test.** Derselbe Plan ohne Prüfung übernommen
    vergrößert am Netz und am exakten Körper still die andere Bohrung — genau
    das „still umbiegen", das §21.3 verbietet. Mit Prüfung folgt der Verweis,
    und ein Befund sagt es.
    """
    history = _plate(kernel)
    _cache, run = _runner(profile)
    base = run(history.document)
    _widen(history, _name_at(base, LEFT_X))
    base = run(history.document)
    assert _holes(base)[LEFT_X] > WIDENED - 0.5 > _holes(base)[RIGHT_X]
    before = _document_without_numbering(history)
    before_hashes = dict(base.object_hashes)
    ops = history.operations
    left, right = ops[1], ops[2]
    context = dependencies(history.document, base)

    raw = history.plan_move([right.id], left.id, context)
    history.commit(raw)
    unchecked = _holes(run(history.document))
    assert unchecked[RIGHT_X] > WIDENED - 0.5, "ohne Prüfung trifft der Verweis still die andere"
    history.undo()
    assert _document_without_numbering(history) == before

    plan = history.plan_move([right.id], left.id, context)
    revision = revise(history, plan, evaluate=run, baseline=base, context=context)
    assert [finding.code for finding in revision.findings] == ["history.reference_followed"]
    commit(history, revision)
    moved = _holes(run(history.document))
    assert moved[LEFT_X] > WIDENED - 0.5, "die linke Bohrung bleibt die vergrößerte"
    assert moved[RIGHT_X] < DRILLED + 0.5
    history.undo()
    assert _document_without_numbering(history) == before
    assert dict(run(history.document).object_hashes) == before_hashes


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_suppressing_a_hole_rests_its_resize_and_reactivating_restores_it(
    profile: Profile, kernel: str
) -> None:
    """P7.3 an beiden Kernen: aus, mitgenommen, wieder an — und dasselbe Teil wie vorher."""
    history = _plate(kernel)
    _cache, run = _runner(profile)
    base = run(history.document)
    _widen(history, _name_at(base, LEFT_X))
    base = run(history.document)
    before = _holes(base)
    left = history.operations[1]
    resize = history.operations[3]

    context = dependencies(history.document, base)
    plan = history.plan_suppress([left.id], context)
    revision = revise(history, plan, evaluate=run, baseline=base, context=context)
    assert resize.id in revision.plan.carried, "die Vergrößerung braucht die Bohrung"
    commit(history, revision)
    off = run(history.document)
    assert off.complete
    assert set(_holes(off)) == {RIGHT_X}, "die linke Bohrung entsteht nicht, ersetzt wird nichts"
    codes = {finding.code: finding.op_id for finding in off.scene.report.findings}
    assert codes.get("history.step_off") == left.id
    assert codes.get("history.step_resting") == resize.id

    context = dependencies(history.document, off)
    plan = history.plan_reactivate([left.id], context)
    commit(history, revise(history, plan, evaluate=run, baseline=off, context=context))
    back = run(history.document)
    assert back.complete and _holes(back) == before, "reproduzierbarer Endzustand"


def test_inserting_a_hole_early_keeps_a_later_resize_on_its_hole(profile: Profile) -> None:
    """P7.1: Eine neue Bohrung vor der ersten nimmt ihr den Namen — der Verweis folgt."""
    box, drill = KERNELS["mesh"]
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader", [OperationDraft(op=box, params={"width": 80.0, "depth": 40.0, "height": 10.0})]
    )
    history.apply(
        "Bohrung rechts",
        [
            OperationDraft(
                op=drill,
                inputs=("obj_1",),
                params={"diameter": DRILLED, "x": RIGHT_X, "y": 0.0, "z": 10.0, "depth": 10.0},
                seed=2,
            )
        ],
    )
    _cache, run = _runner(profile)
    base = run(history.document)
    _widen(history, _name_at(base, RIGHT_X))
    base = run(history.document)
    right = history.operations[1]
    context = dependencies(history.document, base)
    plan = history.plan_insert(
        right.id,
        "Bohrung links",
        [
            OperationDraft(
                op=drill,
                inputs=("obj_1",),
                params={"diameter": DRILLED, "x": LEFT_X, "y": 0.0, "z": 10.0, "depth": 10.0},
                seed=1,
            )
        ],
    )
    revision = revise(history, plan, evaluate=run, baseline=base, context=context)
    commit(history, revision)
    done = _holes(run(history.document))
    assert done[RIGHT_X] > WIDENED - 0.5 and done[LEFT_X] < DRILLED + 0.5
    history.undo()
    assert _holes(run(history.document)) == _holes(base), "Strg+Z stellt die alte Folge her"


@pytest.mark.parametrize("insert_x", [0.0, 30.0], ids=["zwischen", "rechts"])
def test_inserting_an_exact_bore_between_steps_keeps_the_later_reference(
    profile: Profile, insert_x: float
) -> None:
    """P7.1: Eine Bohrung zwischen zwei Schritten darf keinen alten Namen übernehmen.

    Bei ``insert_x=0`` liegt das neue Loch auch geometrisch zwischen beiden.
    Bei ``insert_x=30`` wird der neue Schritt vor die rechte Bohrung gesetzt,
    seine Geometrie liegt aber rechts davon — der Erkennungsschlüssel wechselt.
    In beiden Fällen folgt die spätere Vergrößerung der rechten Bohrung.
    """
    history = _plate("brep")
    _cache, run = _runner(profile)
    base = run(history.document)
    _widen(history, _name_at(base, RIGHT_X))
    base = run(history.document)
    assert _holes(base)[RIGHT_X] > WIDENED - 0.5 > _holes(base)[LEFT_X]
    before = _document_without_numbering(history)
    before_hashes = dict(base.object_hashes)
    right = history.operations[2]
    plan = history.plan_insert(
        right.id,
        "Bohrung einfügen",
        [
            OperationDraft(
                op="drill_brep_hole",
                inputs=("obj_1",),
                params={
                    "diameter": DRILLED,
                    "x": insert_x,
                    "y": 0.0,
                    "z": 10.0,
                    "depth": 10.0,
                },
            )
        ],
    )

    revision = revise(
        history,
        plan,
        evaluate=run,
        baseline=base,
        context=dependencies(history.document, base),
    )
    assert [finding.code for finding in revision.findings] == ["history.reference_followed"]
    commit(history, revision)
    after = run(history.document)
    holes = _holes(after)
    assert set(holes) == {LEFT_X, insert_x, RIGHT_X}
    assert holes[LEFT_X] < DRILLED + 0.5
    assert holes[insert_x] < DRILLED + 0.5
    assert holes[RIGHT_X] > WIDENED - 0.5
    resize = history.operations[-1]
    assert resize.params["at_feature"] == _name_at(after, RIGHT_X)

    history.undo()
    assert _document_without_numbering(history) == before
    assert dict(run(history.document).object_hashes) == before_hashes


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_fit_follows_its_hole_when_the_names_swap(profile: Profile, kernel: str) -> None:
    """Eine Passung am Endstand folgt ihrem Merkmal wie ein Schritt (§14)."""
    history = _plate(kernel)
    _cache, run = _runner(profile)
    base = run(history.document)
    name = _name_at(base, LEFT_X)
    history.document.fits.append(
        Fit(name="loch", a=FeatureRef("obj_1", name), b=FeatureRef("obj_1", name))
    )
    base = run(history.document)
    ops = history.operations
    context = dependencies(history.document, base)
    plan = history.plan_move([ops[2].id], ops[1].id, context)
    revision = revise(history, plan, evaluate=run, baseline=base, context=context)
    commit(history, revision)
    after = run(history.document)
    followed = history.document.fits[0].a.feature_id
    assert followed == _name_at(after, LEFT_X) != name, "die Passung nennt die linke Bohrung"


def _named_fit_sight(name: str, side: str) -> ReferenceSight:
    """Ein belegtes Loch von Schritt 2; die Namenslesung braucht keinen Geometrielauf."""
    from app.core.types import Feature

    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="generated",
        created_by=2,
        params={"centre": (0.0, 0.0, 5.0), "axis": (0.0, 0.0, 1.0), "diameter": 5.0, "depth": 10.0},
    )
    return ReferenceSight(
        key=f"fit:{name}:{side}",
        ref=FeatureRef("obj_1", "hole_1"),
        feature=feature,
        candidates={feature.id: feature},
        diagonal=20.0,
    )


@pytest.mark.parametrize("name", FIT_NAMES)
def test_named_fit_dependencies_keep_the_whole_name(name: str) -> None:
    """Der Abhängigkeitsgraph braucht den Dokumentnamen, sonst ruht die Passung nicht mit."""
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Operation, Scene

    document = new_project().document
    document.ops.extend(
        [
            Operation(id=1, op="create_box", outputs=("obj_1",)),
            Operation(id=2, op="drill_hole", inputs=("obj_1",), outputs=("obj_1",)),
        ]
    )
    result = EvaluationResult(
        Scene(), fit_sights=tuple(_named_fit_sight(name, side) for side in ("a", "b"))
    )

    context = dependencies(document, result)

    assert context.fit_needs == {name: frozenset({1, 2})}
    assert set(context.fit_expectations) == {name}
    assert [entry.key for entry in context.fit_expectations[name]] == [
        f"fit:{name}:a",
        f"fit:{name}:b",
    ]


@pytest.mark.parametrize("name", FIT_NAMES)
@pytest.mark.parametrize("side", ["a", "b"])
@pytest.mark.parametrize("stored", [False, True], ids=["Grundstand", "Ruhevermerk"])
def test_named_fit_drifts_keep_the_whole_name(name: str, side: str, stored: bool) -> None:
    """Beide Umbauwege müssen einen geänderten Merkmalsnamen derselben Passung zuordnen."""
    from app.core.scene.evaluate import EvaluationResult
    from app.core.scene.history import RevisionPlan
    from app.core.scene.revision import drifts, expectation_of
    from app.core.types import Operation, Scene, Suppression, Transaction

    sight = _named_fit_sight(name, side)
    assert sight.feature is not None
    successor = replace(sight.feature, id="hole_2")
    proposal = EvaluationResult(
        Scene(),
        fit_sights=(replace(sight, feature=None, candidates={successor.id: successor}),),
    )
    document = new_project().document
    if stored:
        expected = expectation_of(sight)
        assert expected is not None
        document.ops.append(
            Operation(
                id=2,
                op="drill_hole",
                suppressed=Suppression(expects=(expected,), fits=(name,)),
            )
        )
    baseline = None if stored else EvaluationResult(Scene(), fit_sights=(sight,))
    plan = RevisionPlan(kind="reactivate" if stored else "move", transaction=Transaction(1, "", ()))

    found = drifts(document, plan, baseline, proposal)

    assert len(found) == 1
    assert found[0].fit == name and found[0].key == f"fit:{name}:{side}"
    assert found[0].verdict.state == "renamed" and found[0].verdict.name == "hole_2"


@pytest.mark.parametrize("name", FIT_NAMES)
@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_named_fit_revision_survives_saving_and_undo(
    profile: Profile, tmp_path: Path, kernel: str, name: str
) -> None:
    """Zwei getrennte Bohrungsbezüge reisen mit dem Umbau, der Datei und genau einem Undo."""
    from app.core.knowledge.parts import LIBRARY_VERSION
    from app.core.scene.history import change_for

    if kernel == "brep":
        from tests.helpers import exact_kernel

        exact_kernel()
    history = _plate(kernel)
    # Das Öffnen aktualisiert die Bibliotheksversion; der Undo-Vergleich beginnt
    # deshalb bereits im aktuellen Dateivertrag, nicht mit dem Altwert "0".
    history.document.parts_version = LIBRARY_VERSION
    _cache, run = _runner(profile)
    base = run(history.document)
    original = Fit(
        name=name,
        a=FeatureRef("obj_1", _name_at(base, LEFT_X)),
        b=FeatureRef("obj_1", _name_at(base, RIGHT_X)),
    )
    history.apply("Passung", [], changes=change_for(history.document, fits=[original]))
    base = run(history.document)
    assert base.complete
    assert [(sight.key, sight.ref) for sight in base.fit_sights] == [
        (f"fit:{name}:a", original.a),
        (f"fit:{name}:b", original.b),
    ]
    before = _document_without_numbering(history)
    left, right = history.operations[1:3]
    context = dependencies(history.document, base)
    assert context.fit_needs == {name: frozenset({history.operations[0].id, left.id, right.id})}
    plan = history.plan_move([right.id], left.id, context)
    revision = revise(history, plan, evaluate=run, baseline=base, context=context)
    transaction = commit(history, revision)
    after = run(history.document)
    assert after.complete
    expected_fit = replace(
        original,
        a=FeatureRef("obj_1", _name_at(after, LEFT_X)),
        b=FeatureRef("obj_1", _name_at(after, RIGHT_X)),
    )
    assert history.document.fits == [expected_fit]
    assert expected_fit.a != original.a and expected_fit.b != original.b
    assert len(after.fit_sights) == 2
    assert _document_without_numbering(history) != before

    project = new_project("centauri-carbon-2", "petg")
    project.document = history.document
    reopened = load(save(project, tmp_path / "Passung.p3d"))
    reopened_history = History(reopened.document)
    assert reopened.document.fits == [expected_fit]
    assert _document_without_numbering(reopened_history) == _document_without_numbering(history)
    undone = reopened_history.undo()
    assert undone is not None and undone.id == transaction.id
    assert _document_without_numbering(reopened_history) == before
    restored = run(reopened.document)
    assert restored.complete and _holes(restored) == _holes(base)
    assert [(sight.key, sight.ref) for sight in restored.fit_sights] == [
        (f"fit:{name}:a", original.a),
        (f"fit:{name}:b", original.b),
    ]


def test_a_lost_reference_asks_and_a_refusal_changes_nothing(profile: Profile) -> None:
    """Verliert ein Verweis sein Merkmal, wird gefragt — ohne Antwort bleibt alles, wie es war."""
    history = _plate("mesh")
    _cache, run = _runner(profile)
    base = run(history.document)
    _widen(history, _name_at(base, LEFT_X))
    base = run(history.document)
    before = document_to_data(history.document)
    ops = history.operations
    left, resize = ops[1], ops[3]
    context = dependencies(history.document, base)
    # Die Vergrößerung vor die Bohrung, die sie meint: Das verbietet die
    # Merkmalskante vorab, ohne Rechnung.
    with pytest.raises(UserError) as caught:
        history.plan_move([resize.id], left.id, context)
    assert caught.value.values["step"] == resize.id
    assert document_to_data(history.document) == before

    # Ohne Kante (etwa ein Stand ohne Lauf) fängt es die isolierte Auswertung:
    # Die linke Bohrung ans Ende — an der Stelle der Vergrößerung steht nur die
    # rechte, und die trägt jetzt den Namen. Gefragt wird, nicht still genommen.
    plan = history.plan_move([left.id], None)
    asked: list[list[str]] = []

    def refuse(question: str, choices: list[str]) -> str:
        asked.append(list(choices))
        return choices[-1]

    with pytest.raises(AmbiguityError) as refused:
        revise(history, plan, evaluate=run, baseline=base, ask=refuse)
    # Gefragt wird am Vorschlag: Dort ist die rechte die einzige Bohrung und heißt hole_1.
    assert asked and asked[0][:-1] == ["hole_1"], "die rechte steht zur Wahl"
    assert refused.value.suggestions
    assert document_to_data(history.document) == before, "ein ungültiger Vorschlag ändert nichts"

    # Und ohne jemanden zum Fragen (Kommandozeile, Agent) dieselbe Absage,
    # die Kandidaten als Vorschläge.
    with pytest.raises(AmbiguityError) as unasked:
        revise(history, plan, evaluate=run, baseline=base)
    assert any(action.id.startswith("choose:") for action in unasked.value.suggestions)
    assert document_to_data(history.document) == before

    # Wer die rechte ausdrücklich wählt, bekommt sie — als Antwort, nicht als Rat.
    revision = revise(history, plan, evaluate=run, baseline=base, ask=lambda q, c: c[0])
    commit(history, revision)
    assert _holes(run(history.document))[RIGHT_X] > WIDENED - 0.5


def test_a_resting_step_survives_saving_and_reopens_to_the_same_part(
    profile: Profile, tmp_path: Path
) -> None:
    """Wiederöffnung: Der Zustand reist in der Datei, kalt und warm dasselbe Teil."""
    history = _plate("mesh")
    _cache, run = _runner(profile)
    base = run(history.document)
    _widen(history, _name_at(base, LEFT_X))
    base = run(history.document)
    left = history.operations[1]
    context = dependencies(history.document, base)
    commit(
        history,
        revise(
            history,
            history.plan_suppress([left.id], context),
            evaluate=run,
            baseline=base,
            context=context,
        ),
    )
    warm = run(history.document)
    project = new_project("centauri-carbon-2", "petg")
    project.document = history.document
    reopened = load(save(project, tmp_path / "aus.p3d"))
    cold = evaluate(reopened.document, profile, cache=ResultCache())
    assert _holes(cold) == _holes(warm) == {RIGHT_X: _holes(warm)[RIGHT_X]}
    reopened_history = History(reopened.document)
    reopened_history.undo()
    again = evaluate(reopened.document, profile, cache=ResultCache())
    assert _holes(again) == _holes(base), "Strg+Z aus der Datei schaltet wieder ein"


def test_the_arrangement_keeps_running_when_the_split_is_off(profile: Profile) -> None:
    """Ist die Teilung aus, ordnet das Anordnen den ganzen Körper an, statt mitzuruhen."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 60.0, "depth": 30.0, "height": 20.0})],
    )
    history.apply(
        "Teilen",
        [
            OperationDraft(
                op="split_pinned",
                inputs=("obj_1",),
                params={"axis": "z", "position": 10.0, "pins": 0},
            )
        ],
    )
    _cache, run = _runner(profile)
    base = run(history.document)
    assert base.complete, [finding.code for finding in base.scene.report.findings]
    pieces = tuple(base.scene.objects)
    history.apply("Anordnen", [OperationDraft(op="arrange_bed", inputs=pieces)])
    base = run(history.document)
    assert base.complete
    split = history.operations[1]
    context = dependencies(history.document, base)
    plan = history.plan_suppress([split.id], context)
    assert plan.carried == ()
    commit(history, revise(history, plan, evaluate=run, baseline=base, context=context))
    after = run(history.document)
    assert after.complete and set(after.scene.objects) == {"obj_1"}
    height = after.scene.objects["obj_1"].mesh.bounds
    assert abs((height.maximum[2] - height.minimum[2]) - 20.0) < 1e-6, "der ganze Quader"


def _example(name: str, profile_of: object = None) -> tuple[History, object, object]:
    """Ein mitgeliefertes Beispielprojekt — ein echtes Projekt aus dem Korpus (§34)."""
    from app.core.knowledge import profiles
    from app.core.scene.project import ProjectSources

    folder = Path(__file__).resolve().parent.parent / "app" / "examples"
    project = load(folder / f"{name}.p3d")
    document = project.document
    profile = profiles.scene_profile(
        document.printer or profiles.DEFAULT_PRINTER,
        document.material or profiles.DEFAULT_MATERIAL,
    )
    sources = ProjectSources(project, base_dir=folder)
    cache = ResultCache()

    def run(doc: Document) -> object:
        return evaluate(doc, profile, cache=cache, sources=sources)

    return History(document), run, run(document)


def test_the_box_with_lid_offers_to_switch_the_lid_off_with_its_cavity() -> None:
    """„Dose mit Deckel": Ohne Aushöhlen hat der Deckel nichts zu verschließen.

    Der Vorschlag hält am Deckel an und ändert nichts; der Weg ist ein Knopf,
    der den Deckel ausdrücklich mit ausschaltet — kein stilles Mitnehmen. Mit
    beiden aus rechnet die Dose massiv, die Deckelpassung ruht, und das
    Anordnen legt den einen Körper aufs Bett. Wieder an: dasselbe Teil wie vorher.
    """
    history, run, base = _example("dose-mit-deckel")
    assert base.complete
    before = document_to_data(history.document)
    hashes = dict(base.object_hashes)
    ops = {entry.op: entry for entry in history.operations}
    hollow, lid = ops["hollow_object"], ops["create_lid"]
    context = dependencies(history.document, base)
    with pytest.raises(UserError) as caught:
        revise(
            history,
            history.plan_suppress([hollow.id], context),
            evaluate=run,
            baseline=base,
            context=context,
        )
    assert caught.value.suggestions[0].id == "suppress_along"
    assert caught.value.values["also"] == lid.id
    assert document_to_data(history.document) == before

    steps = [int(step) for step in str(caught.value.values["steps"]).split(",")]
    plan = history.plan_suppress([*steps, caught.value.values["also"]], context)
    commit(history, revise(history, plan, evaluate=run, baseline=base, context=context))
    off = run(history.document)
    assert off.complete and set(off.scene.objects) == {"obj_1"}
    assert not off.scene.fits, "die Deckelpassung ruht mit ihrem Schritt"

    context = dependencies(history.document, off)
    plan = history.plan_reactivate([hollow.id, lid.id], context)
    commit(history, revise(history, plan, evaluate=run, baseline=off, context=context))
    back = run(history.document)
    assert back.complete and dict(back.object_hashes) == hashes


def test_switching_off_the_sphere_rests_what_shapes_it() -> None:
    """„Figur formen": Ohne Kugel ruhen Verschieben und Verschmelzen, der Rest rechnet am Quader."""
    history, run, base = _example("weg4-figur-formen")
    ops = {entry.op: entry for entry in history.operations}
    sphere = ops["create_sphere"]
    context = dependencies(history.document, base)
    revision = revise(
        history,
        history.plan_suppress([sphere.id], context),
        evaluate=run,
        baseline=base,
        context=context,
    )
    assert set(revision.plan.carried) == {ops["translate_object"].id, ops["blend_union"].id}
    commit(history, revision)
    off = run(history.document)
    assert off.complete and set(off.scene.objects) == {"obj_1"}
    history.undo()
    assert dict(run(history.document).object_hashes) == dict(base.object_hashes)


def test_moving_the_last_step_of_every_example_to_a_valid_place_computes_and_undoes() -> None:
    """P7.2 am Korpus: Jede als gültig gezeigte Stelle rechnet, und Strg+Z stellt den Stand her."""
    for name in ("drucker-kalibrieren", "weg1-halterung-anpassen", "weg2-halter-konstruieren"):
        history, run, base = _example(name)
        last = history.operations[-1]
        context = dependencies(history.document, base)
        valid = [
            target for target in history.valid_targets([last.id], context) if target.problem is None
        ]
        assert valid, name
        plan = history.plan_move([last.id], valid[0].before, context)
        commit(history, revise(history, plan, evaluate=run, baseline=base, context=context))
        assert run(history.document).complete, name
        history.undo()
        assert dict(run(history.document).object_hashes) == dict(base.object_hashes), name
