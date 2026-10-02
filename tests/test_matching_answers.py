"""Zuordnungsentscheidungen an echter Geometrie und an der atomaren Operationsgrenze."""

from copy import deepcopy
from dataclasses import replace
from importlib import import_module

import pytest
import trimesh

from app.core.errors import (
    CORRECT_INPUT,
    SHOW_HISTORY,
    AmbiguityError,
    OperationCancelled,
    QuestionDeclined,
)
from app.core.geom.mesh import MeshCodec, MeshData
from app.core.perceive.features import detect
from app.core.perceive.match_records import group_key
from app.core.perceive.matching import MatchResult, fingerprint
from app.core.registry import Registry, op_params, param, register_op
from app.core.scene import CancelSignal, History, OperationDraft, ResultCache, evaluate
from app.core.scene.cache import DiskCache
from app.core.scene.evaluate import (
    QUESTION_LEFT_OPEN,
    _answer_matches,
    _with_feature_reservations,
    _with_features,
)
from app.core.scene.project import load, new_project, save
from app.core.types import BaseParams, Feature, Operation, OpResult, SceneObject
from app.i18n import _, tr
from tests.helpers import exact_kernel


@pytest.fixture(scope="module")
def plates():
    """Ein mittiges Loch wird durch zwei getrennte wirkliche Bohrungen ersetzt."""
    meshes = []
    for positions in ((0.0,), (-3.0, 3.0)):
        body = trimesh.creation.box(extents=(80.0, 40.0, 8.0))
        for x in positions:
            cutter = trimesh.creation.cylinder(radius=1.0, height=20.0, sections=32)
            cutter.apply_translation((x, 0, 0))
            body = trimesh.boolean.difference([body, cutter])
        meshes.append(MeshData.of(body))
    return tuple(meshes)


def old_holes(count=1):
    """Gleichwertige alte Bezüge haben verschiedene Namen und Erzeuger."""
    return {
        f"before_{index}": Feature(
            id=f"before_{index}",
            kind="hole",
            provenance="generated",
            params={"centre": (0.0, 0.0, 4.0), "axis": (0.0, 0.0, 1.0), "diameter": 2.0},
            created_by=index,
        )
        for index in range(1, count + 1)
    }


def test_competing_group_asks_every_owner_and_never_offers_one_target_twice(plates):
    """Drei alte Bohrungen um zwei neue: Die verwiesene wird **zuerst** gefragt und hat die
    volle Auswahl, die nächste bekommt, was übrig ist — und wem nichts bleibt und auf den sich
    nichts bezieht, dem wird keine Frage mit „Nicht weiterführen" als einziger Antwort
    gestellt. Wer nicht fortgeführt wird, bleibt als Kennung reserviert.

    Bis zum 23.09.2026 lief die Frage in der Reihenfolge der Namen: Die verwiesene Bohrung
    kam zuletzt und bekam nur noch „Nicht weiterführen" — ausgerechnet der Bezug, an dem eine
    Passung hing, verlor seinen Nachfolger an zwei, die niemand benutzt.
    """
    body = SceneObject(id="body", name="Platte", mesh=plates[1])
    before = old_holes(3)
    recorded, asked, contexts = {}, [], []

    def ask(question, choices):
        asked.append((question, tuple(choices)))
        return choices[0]

    def announce(scene, targets, _previous_feature):
        contexts.append((scene, targets))

    result = _with_features(
        body,
        deepcopy(before),
        Operation(id=4, op="thicken", outputs=("body",)),
        ask,
        [],
        recorded=recorded,
        referenced={"before_3"},
        question_context=announce,
    )
    result = _with_feature_reservations(result, set(before), set(before))
    assert len(asked) == 2
    assert [len(choices) for _, choices in asked] == [3, 2]
    assert "before_3" in asked[0][0].split("?")[0], "die verwiesene Bohrung kommt zuerst"
    assert set(asked[0][1][:-1]) > set(asked[1][1][:-1])
    assert all(name in asked[0][0] for name in before)
    for name in ("before_3", "before_1"):
        assert result.features[name].created_by == before[name].created_by
    assert "before_2" not in result.features
    assert "before_2" in result.reserved_feature_ids
    record = recorded[group_key("body", before)]
    assert record["decisions"]["before_2"] == {"not_carried": True}
    assert len(contexts) == 4 and contexts[-1] == (None, ())
    for scene, targets in contexts[::2]:
        assert scene.mesh is body.mesh
        assert set(targets) <= set(scene.features)
        assert all(scene.features[name].face_indices for name in targets)

    def refuse(*_):
        pytest.fail("a complete saved group must not ask again")

    repeated = _with_features(
        body,
        deepcopy(before),
        Operation(id=4, op="thicken", outputs=("body",), matches=recorded),
        refuse,
        [],
        referenced={"before_3"},
    )
    repeated = _with_feature_reservations(repeated, set(before), set(before))
    assert repeated.features == result.features
    assert repeated.reserved_feature_ids == result.reserved_feature_ids


@pytest.mark.parametrize("stop", ("cancel", "invalid", "raise"))
def test_answer_failure_after_another_group_keeps_mapping_records_and_findings(plates, stop):
    """Bricht die zweite Antwort ab — Abbruch, ungültige Wahl oder Ausnahme —, bleibt von der
    ersten nichts stehen: Zuordnung, Aufzeichnung und Befunde sind wie vorher, der Kontext ist
    geleert.
    """
    body = SceneObject(id="body", name="Platte", mesh=plates[1], features=detect(plates[1]))
    targets = tuple(name for name, feature in body.features.items() if feature.kind == "hole")
    matched = MatchResult(ambiguous={"old_a": (targets[0],), "old_b": (targets[1],)})
    original = deepcopy(matched)
    recorded, findings, contexts = {}, [], []
    signal, calls = CancelSignal(), []

    def ask(question, choices):
        calls.append(question)
        if len(calls) == 2:
            if stop == "cancel":
                signal.cancel()
            elif stop == "invalid":
                return "not an offered choice"
            else:
                raise AmbiguityError("Bitte erneut zuordnen.")
        return choices[0]

    with pytest.raises((OperationCancelled, AmbiguityError)):
        _answer_matches(
            body,
            matched,
            Operation(id=2, op="thicken"),
            ask,
            findings,
            recorded,
            {"old_a", "old_b"},
            signal,
            lambda scene, targets, _previous_feature: contexts.append((scene, targets)),
            None,
        )
    assert len(calls) == 2
    assert matched == original and recorded == {} and findings == []
    assert contexts[-1] == (None, ())


def test_an_unused_owner_with_nothing_left_is_not_asked(plates):
    """Ein Dialog mit „Nicht weiterführen" als einziger Antwort fragt nichts: Bleibt einem
    bisherigen Merkmal kein Nachfolger und bezieht sich nichts darauf, wird es still nicht
    fortgeführt — festgehalten wie eine Antwort. Einem verwiesenen bleibt die Frage, denn an
    ihm hängt eine Passung oder ein Schritt, und Abbrechen beginnt die Gruppe neu.
    """
    body = SceneObject(id="body", name="Platte", mesh=plates[1], features=detect(plates[1]))
    targets = tuple(name for name, feature in body.features.items() if feature.kind == "hole")
    matched = MatchResult(ambiguous={"used": targets, "spare_1": targets, "spare_2": targets})
    asked: list[tuple[str, tuple[str, ...]]] = []
    recorded: dict = {}

    def ask(question, choices):
        asked.append((question, tuple(choices)))
        return choices[0]

    _answer_matches(
        body,
        matched,
        Operation(id=2, op="thicken"),
        ask,
        [],
        recorded,
        {"used"},
        CancelSignal(),
        None,
        None,
    )

    assert len(asked) == 2, 'die dritte Frage hätte nur „Nicht weiterführen" angeboten'
    assert asked[0][0].split("?")[0].endswith("used")
    record = next(iter(recorded.values()))
    assert sum(1 for entry in record["decisions"].values() if entry == {"not_carried": True}) == 1

    asked.clear()
    lonely = MatchResult(ambiguous={"used": (targets[0],), "also_used": (targets[0],)})
    _answer_matches(
        body,
        lonely,
        Operation(id=2, op="thicken"),
        ask,
        [],
        {},
        {"used", "also_used"},
        CancelSignal(),
        None,
        None,
    )
    assert [len(choices) for _question, choices in asked] == [2, 1], (
        "ein verwiesener Bezug ohne Nachfolger wird weiter gefragt"
    )


def test_old_unqualified_answer_never_frees_a_new_competing_group(plates):
    """Eine alte Antwort ohne Objektbezug entscheidet keine neue Konkurrenz um dasselbe Ziel; beide
    Bewerber werden gefragt.
    """
    body = SceneObject(id="body", name="Platte", mesh=plates[1])
    holes = {name: feature for name, feature in detect(plates[1]).items() if feature.kind == "hole"}
    old = old_holes(2)
    saved = fingerprint(
        next(iter(holes.values())), body.mesh.bounds.centre, body.mesh.bounds.diagonal
    )
    operation = Operation(
        id=3, op="thicken", outputs=("body",), matches={"legacy": {"before_1": saved}}
    )
    asked = []

    def ask(question, choices):
        asked.append(question)
        return choices[0]

    _with_features(body, old, operation, ask, [], referenced={"before_1"})
    assert len(asked) == 2


def test_valid_old_single_answer_is_reused_without_inventing_a_group(plates):
    """Eine gültige alte Einzelantwort ohne Gegenbewerber wird stumm wiederverwendet; niemand wird
    gefragt, und keine Gruppe entsteht.
    """
    body = SceneObject(id="body", name="Platte", mesh=plates[1])
    target = next(feature for feature in detect(plates[1]).values() if feature.kind == "hole")
    saved = fingerprint(target, body.mesh.bounds.centre, body.mesh.bounds.diagonal)
    operation = Operation(
        id=3, op="thicken", outputs=("body",), matches={"legacy": {"before_1": saved}}
    )
    result = _with_features(
        body,
        old_holes(),
        operation,
        lambda *_: pytest.fail("a valid unopposed historical answer must remain usable"),
        [],
        referenced={"before_1"},
    )
    assert result.features["before_1"].params["centre"] == target.params["centre"]


def test_stale_group_cannot_fall_back_to_a_superseded_legacy_answer(plates):
    """Passt die aufgezeichnete Gruppe nicht mehr, gilt die ältere Einzelantwort daneben nicht als
    Ersatz: Es wird einmal neu gefragt.
    """
    body = SceneObject(id="body", name="Platte", mesh=plates[1])
    operation = Operation(id=3, op="thicken", outputs=("body",))
    recorded = {}
    _with_features(
        body,
        old_holes(),
        operation,
        lambda _, choices: choices[0],
        [],
        recorded=recorded,
        referenced={"before_1"},
    )
    saved = recorded[group_key("body", ("before_1",))]
    legacy = deepcopy(saved["candidates"][0]["fingerprint"])
    saved["candidates"][1]["fingerprint"]["relative"][0] += 4.0
    asked = []

    def ask(question, choices):
        asked.append(question)
        return choices[0]

    _with_features(
        body,
        old_holes(),
        replace(operation, matches={**recorded, "legacy": {"before_1": legacy}}),
        ask,
        [],
        referenced={"before_1"},
    )
    assert len(asked) == 1


@op_params
class EmptyParams(BaseParams):
    pass


@op_params
class ReferenceParams(BaseParams):
    at: str = param(title=_("Merkmal"), kind="feature")


def two_body_project(plates):
    """Zwei unabhängig referenzierte Ausgaben tragen absichtlich denselben alten Namen."""
    registry = Registry()

    @register_op(
        name="make_plates",
        title=_("Platten"),
        category="primitive",
        params=EmptyParams,
        consumes=0,
        produces=2,
        registry=registry,
    )
    def make(ctx):
        return OpResult(
            outputs=[
                SceneObject(id="", name=name, mesh=plates[0], features=old_holes())
                for name in ("Links", "Rechts")
            ]
        )

    @register_op(
        name="change_plates",
        title=_("Platten ändern"),
        category="prepare",
        params=EmptyParams,
        consumes=2,
        produces=2,
        registry=registry,
    )
    def change(ctx):
        return OpResult(outputs=[replace(body, mesh=plates[1], features={}) for body in ctx.inputs])

    @register_op(
        name="use_plate",
        title=_("Bezug verwenden"),
        category="scene",
        params=ReferenceParams,
        consumes=1,
        produces=1,
        registry=registry,
    )
    def use(ctx):
        return OpResult(outputs=list(ctx.inputs))

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document, registry=registry)
    history.apply("Platten", [OperationDraft(op="make_plates")])
    history.apply("Ändern", [OperationDraft(op="change_plates", inputs=("obj_1", "obj_2"))])
    for name in ("obj_1", "obj_2"):
        history.apply(
            "Bezug",
            [OperationDraft(op="use_plate", inputs=(name,), params={"at": "before_1"})],
        )
    return project, history, registry


@pytest.mark.parametrize("abort_second", (False, True))
def test_whole_operation_answers_are_object_qualified_and_atomic(
    plates, profile, tmp_path, abort_second
):
    """Eine Operation über zwei Körper fragt je Körper mit dessen Namen, zeigt dabei die Vorschau
    des angehaltenen Stands — und der Stapel bleibt bis zur letzten Antwort unverändert.
    """
    project, history, registry = two_body_project(plates)
    before = deepcopy(project.document.ops)
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    contexts, asked = [], []

    def announce(scene, targets):
        contexts.append((scene, targets))

    def ask(question, choices):
        asked.append((question, tuple(choices)))
        preview, targets = contexts[-1]
        assert ("Links" if len(asked) == 1 else "Rechts") in question
        assert tr("Nicht weiterführen") in question
        assert preview.stopped_at == 2 and preview.completed == (1,)
        assert set(preview.scene.objects) == {"obj_1", "obj_2"}
        assert preview.object_hashes == {} and not preview.matches
        assert all(body.mesh is plates[1] for body in preview.scene.objects.values())
        assert {object_id for object_id, _ in targets} == {f"obj_{len(asked)}"}
        assert project.document.ops == before
        if len(asked) == 2 and abort_second:
            raise AmbiguityError("Bitte erneut zuordnen.")
        return choices[len(asked) - 1]

    result = evaluate(
        project.document,
        profile,
        registry=registry,
        cache=cache,
        ask=ask,
        question_context=announce,
    )
    assert len(asked) == 2 and contexts[-1] == (None, ())
    assert project.document.ops == before
    if abort_second:
        assert result.stopped_at == 2 and result.completed == (1,)
        assert result.matches == {}
        assert all(body.mesh is plates[0] for body in result.scene.objects.values())
        assert not tuple((tmp_path / "cache").glob("**/*.json"))
        return
    assert result.complete
    assert set(result.matches[2]) == {group_key(name, ("before_1",)) for name in ("obj_1", "obj_2")}
    centres = [
        result.scene.objects[name].features["before_1"].params["centre"][0]
        for name in ("obj_1", "obj_2")
    ]
    assert sorted(centres) == pytest.approx([-3.0, 3.0])
    assert history.record_matches(result.matches)
    reopened = load(save(project, tmp_path / "grouped.p3d"))
    again = evaluate(
        reopened.document,
        profile,
        registry=registry,
        cache=cache,
        ask=lambda *_: pytest.fail("saved object-qualified groups must be reused"),
    )
    assert again.complete and not again.matches


def test_a_question_closed_without_a_choice_stops_the_step_with_its_way_back(plates, profile):
    """Wer die Zuordnungsfrage schließt, ohne zu wählen, bekommt einen Befund am Schritt — mit
    dem Weg zurück als Knöpfe — und sieht den Stand davor.

    Bis zum 23.09.2026 warf die Sitzung dafür ``OperationCancelled``: Die ganze Rechnung galt
    als abgebrochen, das Fenster sagte nichts (``_cancel_by_user`` stand nicht), und im Bild
    stand der alte Stand, als wäre nichts gewesen. RM-024 verlangt „Abbruch liefert einen
    Befund".
    """
    project, _history, registry = two_body_project(plates)
    before = deepcopy(project.document.ops)
    asked = []

    def ask(question, choices):
        asked.append(question)
        raise QuestionDeclined

    result = evaluate(project.document, profile, registry=registry, ask=ask)

    assert len(asked) == 1, "nach der geschlossenen Frage fragt dieser Lauf nicht weiter"
    assert result.stopped_at == 2 and result.completed == (1,)
    assert project.document.ops == before and not result.matches
    stop = [finding for finding in result.scene.report.findings if finding.op_id == 2]
    assert len(stop) == 1 and stop[0].severity == "error"
    assert stop[0].message == QUESTION_LEFT_OPEN
    assert [action.id for action in stop[0].suggestions] == [CORRECT_INPUT.id, SHOW_HISTORY.id]


def test_native_competition_does_not_take_a_matching_mesh_answer(monkeypatch):
    """Eine gespeicherte Netzantwort passt nicht auf einen exakten Körper: Die
    Zuordnung fragt neu, statt Kennungen über die Kerngrenze zu übernehmen."""
    edit = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.perceive.match_decisions import group_fingerprint

    module = import_module("app.core.scene.evaluate")
    solid = edit.box(10, 10, 10)
    found = features_of(solid)
    name = next(iter(found))
    body = SceneObject(id="body", name="Quader", mesh=solid, features=found)
    matched = MatchResult(ambiguous={name: (name,)}, fresh=(name,))
    monkeypatch.setattr(module, "match", lambda *_, **__: deepcopy(matched))
    before = deepcopy(body.features)
    saved = group_fingerprint(
        "body", matched.ambiguous, {name: name}, found, solid.bounds.centre, solid.bounds.diagonal
    )
    with pytest.raises(AmbiguityError):
        _with_features(
            body,
            dict(found),
            Operation(
                id=2,
                op="resize_feature",
                outputs=("body",),
                matches={group_key("body", (name,)): saved},
            ),
            lambda *_: pytest.fail("native identity needs its own topology proof"),
            [],
            referenced={name},
            touches_features=True,
        )
    assert body.features == before


@pytest.mark.parametrize("noncontinuation", (False, True))
def test_two_bodies_never_share_legacy_answer_and_save_explicit_noncontinuation(
    plates, profile, tmp_path, noncontinuation
):
    """Zwei Körper mit gleich benannten Merkmalen teilen sich keine alte Antwort; „Nicht
    weiterführen" wird je Körper ausdrücklich gespeichert und beim Wiederöffnen nicht erneut
    gefragt.
    """
    project, history, registry = two_body_project(plates)
    hole = next(feature for feature in detect(plates[1]).values() if feature.kind == "hole")
    saved = fingerprint(hole, plates[1].bounds.centre, plates[1].bounds.diagonal)
    history.record_matches({2: {"legacy": {"before_1": saved}}})
    asked = []

    def ask(question, choices):
        asked.append(question)
        return choices[-1] if noncontinuation else choices[0]

    result = evaluate(project.document, profile, registry=registry, ask=ask)
    assert len(asked) == 2 and result.complete
    assert len(result.matches[2]) == 2
    if noncontinuation:
        assert all("before_1" not in body.features for body in result.scene.objects.values())
        assert all(
            "before_1" in body.reserved_feature_ids for body in result.scene.objects.values()
        )
        assert all(
            record["decisions"]["before_1"] == {"not_carried": True}
            for record in result.matches[2].values()
        )
    assert history.record_matches(result.matches)
    reopened = load(save(project, tmp_path / "noncontinuation.p3d"))
    again = evaluate(
        reopened.document,
        profile,
        registry=registry,
        ask=lambda *_: pytest.fail("the whole group must supersede unqualified legacy answers"),
    )
    assert again.complete and not again.matches
    if noncontinuation:
        assert all("before_1" not in body.features for body in again.scene.objects.values())


def test_changed_group_choice_invalidates_following_geometry_but_reuses_the_raw_body(
    plates, profile, tmp_path
):
    """Zwei echte Y-Bohrungen werden X-Bohrungen; die gewählte Markierung muss mitwechseln."""
    raw = trimesh.creation.box(extents=(80.0, 40.0, 8.0))
    for y in (-3.0, 3.0):
        cutter = trimesh.creation.cylinder(radius=1.0, height=20.0, sections=32)
        cutter.apply_translation((0.0, y, 0.0))
        raw = trimesh.boolean.difference([raw, cutter])
    original = MeshData.of(raw)
    original_holes = sorted(
        (feature for feature in detect(original).values() if feature.kind == "hole"),
        key=lambda feature: feature.params["centre"][1],
    )
    previous = {
        f"before_{index}": replace(
            feature, id=f"before_{index}", provenance="generated", created_by=1
        )
        for index, feature in enumerate(original_holes, 1)
    }
    assert len(previous) == 2
    registry = Registry()
    runs = {"make": 0, "change": 0, "mark": 0}

    @register_op(
        name="make_choice_plate",
        title=_("Platte"),
        category="primitive",
        params=EmptyParams,
        consumes=0,
        produces=1,
        registry=registry,
    )
    def make(ctx):
        runs["make"] += 1
        return OpResult(
            outputs=[SceneObject(id="", name="Platte", mesh=original, features=previous)]
        )

    @register_op(
        name="change_choice_plate",
        title=_("Bohrungen"),
        category="prepare",
        params=EmptyParams,
        consumes=1,
        produces=1,
        registry=registry,
    )
    def change(ctx):
        runs["change"] += 1
        return OpResult(outputs=[replace(ctx.inputs[0], mesh=plates[1], features={})])

    @register_op(
        name="mark_choice_plate",
        title=_("Markierung"),
        category="scene",
        params=ReferenceParams,
        consumes=1,
        produces=2,
        registry=registry,
    )
    def mark(ctx):
        runs["mark"] += 1
        source = ctx.inputs[0]
        x, y, z = source.features[ctx.params.at].params["centre"]
        marker = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
        marker.apply_translation((x, y, z + 6.0))
        return OpResult(
            outputs=[source, SceneObject(id="", name="Markierung", mesh=MeshData.of(marker))]
        )

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document, registry=registry)
    history.apply("Platte", [OperationDraft(op="make_choice_plate")])
    history.apply("Bohrungen", [OperationDraft(op="change_choice_plate", inputs=("obj_1",))])
    history.apply(
        "Markierung",
        [OperationDraft(op="mark_choice_plate", inputs=("obj_1",), params={"at": "before_1"})],
    )
    cache_path = tmp_path / "bindings"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=cache_path))
    holes = sorted(
        (feature.params["centre"][0], name)
        for name, feature in detect(plates[1]).items()
        if feature.kind == "hole"
    )
    assert [position for position, _ in holes] == pytest.approx([-3.0, 3.0])

    def choose(right):
        def ask(question, choices):
            index = int(right) if "before_1?" in question else int(not right)
            name = holes[index][1]
            assert name in choices
            return name

        return ask

    first = evaluate(project.document, profile, registry=registry, cache=cache, ask=choose(False))
    assert first.complete and runs == {"make": 1, "change": 1, "mark": 1}
    first_marker = next(body for body in first.scene.objects.values() if body.name == "Markierung")
    assert first_marker.mesh.bounds.centre[0] == pytest.approx(-3.0)
    first_plate = next(body for body in first.scene.objects.values() if body.name == "Platte")
    second = evaluate(project.document, profile, registry=registry, cache=cache, ask=choose(True))
    assert second.complete and runs == {"make": 1, "change": 1, "mark": 2}
    second_marker = next(
        body for body in second.scene.objects.values() if body.name == "Markierung"
    )
    second_plate = next(body for body in second.scene.objects.values() if body.name == "Platte")
    assert second_marker.mesh.bounds.centre[0] == pytest.approx(3.0)
    assert second_plate.reserved_feature_ids == first_plate.reserved_feature_ids
    assert second.object_hashes["obj_1"] != first.object_hashes["obj_1"]
    assert history.record_matches(second.matches)

    def refuse(*_):
        pytest.fail("the saved complete group must remain sufficient")

    history.undo()
    undone = evaluate(project.document, profile, registry=registry, cache=cache, ask=refuse)
    assert undone.scene.objects["obj_1"].features["before_1"].params["centre"][0] == pytest.approx(
        3.0
    )
    history.redo()
    redone = evaluate(project.document, profile, registry=registry, cache=cache, ask=refuse)
    assert redone.complete and runs["mark"] == 2
    reopened = load(save(project, tmp_path / "binding-cache.p3d"))
    cold = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=cache_path))
    final = evaluate(reopened.document, profile, registry=registry, cache=cold, ask=refuse)
    assert final.complete and cold.statistics.disk_hits > 0
    marker = next(body for body in final.scene.objects.values() if body.name == "Markierung")
    assert marker.mesh.bounds.centre[0] == pytest.approx(3.0)


def _textured_plate(profile, faces_after: int):
    """Die Lochplatte aus dem Korpus, ihre Oberseite und ein Stapel mit Texturschritten.

    Der erste Texturschritt überzieht die ganze Oberseite mit Rippen und ersetzt
    sie dabei durch viele neue Flächen; ``faces_after`` weitere Schritte nennen
    danach dieselbe alte Oberseite.
    """
    from pathlib import Path

    from app.core.bootstrap import load_operations
    from app.core.scene.placement import top_face
    from app.core.scene.project import ProjectSources
    from app.core.types import Source

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    meshes = Path(__file__).parent / "data" / "meshes"
    project.sources["src_1"] = (meshes / "plate_holes.stl").read_bytes()
    history = History(project.document)
    history.apply("Import", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    cache = ResultCache()
    sources = ProjectSources(project)
    loaded = evaluate(project.document, profile, sources=sources, cache=cache)
    body = next(iter(loaded.scene.objects))
    face = top_face(loaded.scene.objects[body].features)
    assert face is not None
    texture = {"coverage": "whole_face", "face": face.id, "pattern": "rib", "pitch": 5.0}
    for _step in range(1 + faces_after):
        history.apply(
            "Muster", [OperationDraft(op="apply_texture", inputs=(body,), params=texture)]
        )
    return project, cache, sources, face.id


def test_a_step_is_not_asked_where_its_own_face_went(profile):
    """Wer eine Fläche texturiert, wird nicht gefragt, welche neue Fläche sie fortführt.

    Der Verweis des Texturschritts auf die Oberseite wird an seinem Eingang
    aufgelöst; nach dem Schritt braucht sie niemand mehr (``_needed_after``).
    Gezählt wurde für die Frage trotzdem jeder Verweis im Stapel, und die Textur
    über die ganze Oberseite fragte „Welches Merkmal entspricht face_2?“ mit
    dreizehn Rippenflächen zur Wahl — im Fenster ein modaler Dialog nach jedem
    Übernehmen, in ``test_operation_ui`` ein Test, der auf ihn wartete.
    """
    project, cache, sources, _face = _textured_plate(profile, faces_after=0)

    def refuse(question, choices):
        pytest.fail(f"nach dem eigenen Verweis gefragt: {question}")

    result = evaluate(project.document, profile, sources=sources, cache=cache, ask=refuse)

    assert result.stopped_at is None


def test_a_later_step_on_the_same_face_still_gets_its_question(profile):
    """Die Gegenprobe: Nennt ein **späterer** Schritt die ersetzte Oberseite, bleibt die
    Frage (§21.3) — die Lebensdauer entscheidet, nicht ein Verbot."""
    project, cache, sources, face = _textured_plate(profile, faces_after=1)
    asked: list[str] = []

    def ask(question, choices):
        asked.append(question)
        return choices[0]

    evaluate(project.document, profile, sources=sources, cache=cache, ask=ask)

    assert asked, "der zweite Schritt braucht die Oberseite nach dem ersten"
    assert f"{face}?" in asked[0]
