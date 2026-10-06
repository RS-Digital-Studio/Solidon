"""Ausdrücklich gewählte Kanten werden vor dem Verbrauchercache gebunden (§21.3, P1.4c).

Ein Kantenschlüssel ist eine gerundete Lage, und zwei Kanten können denselben
tragen. Die Auswertung fragt dann den Kunden — vor ``cache.get``, an den
Kanten, die die Operation gleich sieht —, gibt der Operation die bestätigte
Auswahl als Indizes mit und hält die Antwort in ``Operation.matches`` fest
(Domäne ``edge-answer:``, Projektformat 29). Der Aliasfall wird zum
Parameter.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom import edge_ops, edges
from app.core.geom.edges import EDGE_SELECTION_REJECTED, edge_key, edges_of
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles
from app.core.perceive.match_records import (
    EDGE_DOMAIN,
    NATIVE_DOMAIN,
    domain_of,
    edge_answer_key,
    validate_edge_answer,
    validate_matches,
)
from app.core.registry import REGISTRY, Registry
from app.core.scene import FORMAT_VERSION, EdgeTarget, History, ResultCache, evaluate
from app.core.scene.edge_binding import bind_edges
from app.core.scene.history import _copy_operation_matches
from app.core.scene.project import load, project_data, save
from app.core.types import Document, OpContext, Operation, OpResult, SceneObject
from tests.helpers import exact_kernel

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0
#: Zwei Quader, deren Nachbarkanten vier Tausendstel auseinanderliegen — der
#: gerundete Schlüssel unterscheidet sie nicht.
GAP = 0.004
COLLIDING_KEY = f"e:0.00,{DEPTH / 2:.2f},{HEIGHT / 2:.2f}:0.000,0.000,1.000"


def _mesh_pair() -> MeshData:
    left = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    left.apply_translation((-WIDTH / 2.0, 0.0, HEIGHT / 2.0))
    right = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    right.apply_translation((WIDTH / 2.0 + GAP, 0.0, HEIGHT / 2.0))
    return MeshData(trimesh.util.concatenate([left, right]))


def _brep_pair() -> Any:
    exact_kernel()
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    from app.core.brep import edit
    from app.core.brep.kernel import Solid

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    builder.Add(
        compound, edit.moved(edit.box(WIDTH, DEPTH, HEIGHT), (-WIDTH / 2.0, 0.0, 0.0)).shape
    )
    builder.Add(
        compound, edit.moved(edit.box(WIDTH, DEPTH, HEIGHT), (WIDTH / 2.0 + GAP, 0.0, 0.0)).shape
    )
    return Solid(compound)


def _body(backend: str) -> tuple[Any, str]:
    if backend == "mesh":
        return _mesh_pair(), "mesh"
    return _brep_pair(), "brep"


def _document(
    keys: str, *, operation: str = "fillet_edges", choice: str = "named", size: float = 2.0
) -> Document:
    measure = "distance" if operation == "chamfer_edges" else "radius"
    return Document(
        format_version=1,
        app_version="0.0.1",
        ops=[
            Operation(id=1, op="create_brep_cylinder", inputs=[], outputs=["obj_1"], params={}),
            Operation(
                id=2,
                op=operation,
                inputs=["obj_1"],
                outputs=["obj_1"],
                params={measure: size, "edges": choice, "edge_keys": keys},
            ),
        ],
    )


def _registry(body: Any, kind: str, operation: str = "fillet_edges") -> Registry:
    """Die echte Kantenoperation hinter einer Quelle, die den Prüfkörper liefert."""
    load_operations()

    def make_body(ctx: OpContext) -> OpResult:
        return OpResult(outputs=[SceneObject(id="", name="Paar", mesh=body, kind=kind)])

    registry = Registry()
    registry.register(dataclasses.replace(REGISTRY.get("create_brep_cylinder"), fn=make_body))
    registry.register(REGISTRY.get(operation))
    return registry


class _EdgeChooser:
    """Antwortet wie ein Kunde, der die Kante im Bild anklickt, die ``pick`` beschreibt."""

    def __init__(self, pick: Callable[[EdgeTarget], bool]) -> None:
        self.pick = pick
        self.asked: list[str] = []
        self.offered: list[list[str]] = []
        self.previews: list[Any] = []
        self.targets: tuple[EdgeTarget, ...] = ()
        self.cleared = 0

    def context(self, preview: Any, candidates: tuple[Any, ...]) -> None:
        if preview is None:
            self.cleared += 1
            return
        self.previews.append(preview)
        assert all(isinstance(entry, EdgeTarget) for entry in candidates)
        self.targets = candidates

    def __call__(self, question: str, choices: list[str]) -> str:
        self.asked.append(question)
        self.offered.append(list(choices))
        for target in self.targets:
            if target.token in choices and self.pick(target):
                return target.token
        pytest.fail(f"kein passender Kandidat: {self.targets}")


def _right_box(target: EdgeTarget) -> bool:
    return target.middle[0] > GAP / 2.0


def _left_box(target: EdgeTarget) -> bool:
    return target.middle[0] < GAP / 2.0


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Was die Operation an den Kern weiterreicht — die Indizes und den Körper."""
    seen: dict[str, Any] = {}
    original_round = edge_ops.round_edges
    original_bevel = edge_ops.bevel_edges
    original_bead = edge_ops.bead_edges

    def round_spy(mesh: Any, *args: Any, **kwargs: Any) -> Any:
        seen["kernel"], seen["body"] = "mesh", mesh
        seen["selected_edges"] = kwargs.get("selected_edges")
        return original_round(mesh, *args, **kwargs)

    def bevel_spy(mesh: Any, *args: Any, **kwargs: Any) -> Any:
        seen["kernel"], seen["body"] = "mesh", mesh
        seen["selected_edges"] = kwargs.get("selected_edges")
        return original_bevel(mesh, *args, **kwargs)

    def bead_spy(mesh: Any, *args: Any, **kwargs: Any) -> Any:
        seen["kernel"], seen["body"] = "mesh", mesh
        seen["selected_edges"] = kwargs.get("selected_edges")
        return original_bead(mesh, *args, **kwargs)

    monkeypatch.setattr(edge_ops, "round_edges", round_spy)
    monkeypatch.setattr(edge_ops, "bevel_edges", bevel_spy)
    monkeypatch.setattr(edge_ops, "bead_edges", bead_spy)
    try:
        from app.core.brep import edit
    except ImportError:
        return seen
    original_fillet = edit.fillet
    original_chamfer = edit.chamfer

    def fillet_spy(solid: Any, *args: Any, **kwargs: Any) -> Any:
        seen["kernel"], seen["body"] = "brep", solid
        seen["selected_edges"] = kwargs.get("selected_edges")
        return original_fillet(solid, *args, **kwargs)

    def chamfer_spy(solid: Any, *args: Any, **kwargs: Any) -> Any:
        seen["kernel"], seen["body"] = "brep", solid
        seen["selected_edges"] = kwargs.get("selected_edges")
        return original_chamfer(solid, *args, **kwargs)

    monkeypatch.setattr(edit, "fillet", fillet_spy)
    monkeypatch.setattr(edit, "chamfer", chamfer_spy)
    return seen


def _bound_middle(seen: dict[str, Any]) -> tuple[float, float, float]:
    """Die Mitte der Kante, die als gebundener Index beim Kern ankam."""
    (index,) = seen["selected_edges"]
    if seen["kernel"] == "brep":
        exact_kernel()
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        props = GProp_GProps()
        BRepGProp.LinearProperties_s(seen["body"].edges()[index], props)
        point = props.CentreOfMass()
        return (point.X(), point.Y(), point.Z())
    entry = edges_of(seen["body"])[index]
    return (entry.middle[0], entry.middle[1], entry.middle[2])


def _profile() -> Any:
    return profiles.make_profile("centauri-carbon-2", "petg")


# --- die Frage vor dem Cache ------------------------------------------------------------


@pytest.mark.parametrize("backend", ["mesh", "brep"])
def test_a_colliding_key_asks_before_the_cache_and_binds_the_chosen_edge(
    backend: str, captured: dict[str, Any]
) -> None:
    """Zwei Kanten, ein Schlüssel: Der Kunde wählt im Bild, der Kern bekommt genau die."""
    body, kind = _body(backend)
    document = _document(COLLIDING_KEY)
    registry = _registry(body, kind)
    cache = ResultCache()
    chooser = _EdgeChooser(_right_box)

    result = evaluate(
        document,
        _profile(),
        registry=registry,
        cache=cache,
        ask=chooser,
        question_context=chooser.context,
    )

    assert result.complete, result.scene.report.findings
    assert len(chooser.asked) == 1 and "fast an derselben Stelle" in chooser.asked[0]
    assert COLLIDING_KEY not in chooser.asked[0], "die Frage zeigt keinen Schlüssel aus Zahlen"
    assert chooser.offered[0] == [f"{COLLIDING_KEY}#1", f"{COLLIDING_KEY}#2"]
    assert chooser.cleared == 1, "die Kandidaten werden nach der Antwort weggeräumt"
    assert len(chooser.targets) == 2 and {entry.object_id for entry in chooser.targets} == {"obj_1"}
    assert all(
        len(entry.points) >= 2 and entry.upright and not entry.flat for entry in chooser.targets
    )
    assert all(entry.length == pytest.approx(HEIGHT) for entry in chooser.targets)
    assert chooser.previews[0].stopped_at == 2 and "obj_1" in chooser.previews[0].scene.objects
    assert chooser.previews[0].scene.objects["obj_1"].mesh.volume == pytest.approx(
        2 * WIDTH * DEPTH * HEIGHT, rel=1e-9
    ), "gefragt wird am gültigen Eingangsstand, nicht an einer Ausgabe"

    assert captured["selected_edges"] is not None and len(captured["selected_edges"]) == 1
    middle = _bound_middle(captured)
    assert middle[0] == pytest.approx(GAP) and middle[1] == pytest.approx(DEPTH / 2.0)
    removed = 2 * WIDTH * DEPTH * HEIGHT - result.scene.objects["obj_1"].mesh.volume
    # Am Netz ist der Bogen ein Sehnenzug innerhalb der Rundung: er nimmt etwas mehr.
    assert removed == pytest.approx(HEIGHT * 2.0**2 * (1.0 - math.pi / 4.0), rel=0.1)

    records = result.matches[2]
    (key,) = records
    assert domain_of(key) == EDGE_DOMAIN
    record = records[key]
    assert record["object_id"] == "obj_1" and record["field"] == "edge_keys"
    assert record["keys"] == [COLLIDING_KEY]
    assert list(record["candidates"]) == [COLLIDING_KEY]
    assert len(record["candidates"][COLLIDING_KEY]) == 2
    chosen = record["candidates"][COLLIDING_KEY][record["decisions"][COLLIDING_KEY]["candidate"]]
    assert chosen["middle"][0] == pytest.approx(GAP) and chosen["length"] == pytest.approx(HEIGHT)
    alone = evaluate(
        Document(format_version=1, app_version="0.0.1", ops=[document.ops[0]]),
        _profile(),
        registry=registry,
    )
    assert record["scope"] == alone.object_hashes["obj_1"], "der Scope ist die Fassung des Eingangs"
    assert not result.answers, "eine echte Kollision ist kein Parameter"

    # Festgehalten gilt die Antwort: keine Frage mehr, und der Verbraucher ist ein Cachetreffer.
    History(document).record_matches(result.matches)
    again = evaluate(
        document,
        _profile(),
        registry=registry,
        cache=cache,
        ask=lambda *_: pytest.fail("die gespeicherte Wahl gilt"),
    )
    assert again.complete and not again.matches
    assert cache.statistics.hits >= 1
    assert again.scene.objects["obj_1"].mesh.volume == pytest.approx(
        result.scene.objects["obj_1"].mesh.volume
    )


@pytest.mark.parametrize("backend", ["mesh", "brep"])
def test_a_different_answer_is_a_different_key_and_result(
    backend: str, captured: dict[str, Any]
) -> None:
    """Dieselben Parameter, derselbe Eingang, andere Kante: ein anderer Cacheeintrag."""
    body, kind = _body(backend)
    registry = _registry(body, kind)
    cache = ResultCache()
    first = evaluate(
        _document(COLLIDING_KEY),
        _profile(),
        registry=registry,
        cache=cache,
        ask=(right := _EdgeChooser(_right_box)),
        question_context=right.context,
    )
    right_middle = _bound_middle(captured)
    entries_after_first = len(cache)
    second = evaluate(
        _document(COLLIDING_KEY),
        _profile(),
        registry=registry,
        cache=cache,
        ask=(left := _EdgeChooser(_left_box)),
        question_context=left.context,
    )
    left_middle = _bound_middle(captured)

    assert first.complete and second.complete
    assert right_middle[0] == pytest.approx(GAP) and left_middle[0] == pytest.approx(0.0)
    assert len(cache) == entries_after_first + 1, "die zweite Antwort ist ein eigener Eintrag"
    assert first.matches[2] != second.matches[2], (
        "zwei Antworten, zwei Datensätze unter demselben Schlüssel"
    )


@pytest.mark.parametrize("backend", ["mesh", "brep"])
def test_without_anyone_to_ask_the_collision_is_a_finding_with_the_candidates(backend: str) -> None:
    """Kommandozeile und Agent: Halt vor dem Verbraucher, die Kandidaten als Vorschläge."""
    body, kind = _body(backend)
    cache = ResultCache()

    result = evaluate(
        _document(COLLIDING_KEY), _profile(), registry=_registry(body, kind), cache=cache
    )

    assert result.stopped_at == 2 and not result.matches and not result.answers
    stop = [entry for entry in result.scene.report.findings if entry.op_id == 2]
    assert [entry.code for entry in stop] == ["op.fillet_edges.AmbiguityError"]
    assert "nicht eindeutig" in str(stop[0].message)
    assert [action.id for action in stop[0].suggestions][:2] == [
        f"choose:{COLLIDING_KEY}#1",
        f"choose:{COLLIDING_KEY}#2",
    ]
    assert cache.statistics.hits == 0, "der Verbraucher hat den Cache nie erreicht"


def test_an_answer_outside_the_offer_stops_without_a_record() -> None:
    body, kind = _body("mesh")
    chooser = _EdgeChooser(_right_box)

    result = evaluate(
        _document(COLLIDING_KEY),
        _profile(),
        registry=_registry(body, kind),
        ask=lambda question, choices: "irgendwas",
        question_context=chooser.context,
    )

    assert result.stopped_at == 2 and not result.matches
    assert chooser.cleared == 1, (
        "auch nach einer ungültigen Antwort werden die Kandidaten weggeräumt"
    )


def test_a_saved_answer_holds_only_for_the_same_input_version(captured: dict[str, Any]) -> None:
    """Ein anderer Eingang — hier ein anderes Paar — ist ein anderer Scope: neue Frage."""
    body, kind = _body("mesh")
    document = _document(COLLIDING_KEY)
    chooser = _EdgeChooser(_right_box)
    first = evaluate(
        document,
        _profile(),
        registry=_registry(body, kind),
        ask=chooser,
        question_context=chooser.context,
    )
    History(document).record_matches(first.matches)

    taller = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    taller.apply_translation((-WIDTH / 2.0, 0.0, HEIGHT / 2.0))
    right = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    right.apply_translation((WIDTH / 2.0 + GAP, 0.0, HEIGHT / 2.0))
    # Derselbe Körper unter einem anderen Erzeugerschlüssel: ein anderer Eingangshash.
    document.ops[0] = dataclasses.replace(document.ops[0], params={"diameter": 12.0})
    again_chooser = _EdgeChooser(_left_box)
    again = evaluate(
        document,
        _profile(),
        registry=_registry(MeshData(trimesh.util.concatenate([taller, right])), kind),
        ask=again_chooser,
        question_context=again_chooser.context,
    )

    assert again.complete and len(again_chooser.asked) == 1
    assert _bound_middle(captured)[0] == pytest.approx(0.0)
    (key,) = again.matches[2]
    assert again.matches[2][key]["scope"] != first.matches[2][key]["scope"]


def test_a_stored_answer_whose_fingerprints_no_longer_tell_the_edges_apart_asks_again(
    captured: dict[str, Any],
) -> None:
    body, kind = _body("mesh")
    document = _document(COLLIDING_KEY)
    chooser = _EdgeChooser(_right_box)
    first = evaluate(
        document,
        _profile(),
        registry=_registry(body, kind),
        ask=chooser,
        question_context=chooser.context,
    )
    (key,) = first.matches[2]
    record = first.matches[2][key]
    # Beide Kandidaten tragen denselben Abdruck: keine belegte Wahl mehr.
    record["candidates"][COLLIDING_KEY][1] = dict(record["candidates"][COLLIDING_KEY][0])
    History(document).record_matches(first.matches)
    again_chooser = _EdgeChooser(_right_box)

    again = evaluate(
        document,
        _profile(),
        registry=_registry(body, kind),
        ask=again_chooser,
        question_context=again_chooser.context,
    )

    assert again.complete and len(again_chooser.asked) == 1


def test_a_group_choice_binds_nothing_even_with_colliding_keys_in_the_field(
    captured: dict[str, Any],
) -> None:
    """Das ausgegraute Feld hat keine Meinung: Die Gruppe rechnet wie bisher, ohne Frage."""
    body, kind = _body("mesh")

    result = evaluate(
        _document(COLLIDING_KEY, choice="vertical"),
        _profile(),
        registry=_registry(body, kind),
        ask=lambda *_: pytest.fail("eine Gruppe fragt nicht"),
    )

    assert result.complete and not result.matches and captured["selected_edges"] is None


def test_a_unique_key_is_bound_without_a_question_and_reaches_the_kernel(
    captured: dict[str, Any],
) -> None:
    body, kind = _body("brep")
    unique = next(
        entry
        for entry in edges.edges_in_kernel(body, "brep")[1]
        if entry.middle[0] < -WIDTH + 1.0 and entry.upright and entry.middle[1] > 0.0
    )

    result = evaluate(
        _document(edge_key(unique)),
        _profile(),
        registry=_registry(body, kind),
        ask=lambda *_: pytest.fail("ein eindeutiger Schlüssel fragt nicht"),
    )

    assert result.complete and not result.matches and not result.answers
    assert _bound_middle(captured) == pytest.approx(unique.middle)


def test_the_alias_case_becomes_a_parameter_not_a_record(captured: dict[str, Any]) -> None:
    """Ein alter Rohrschlüssel trifft beide Ränder; die Wahl ist ein eindeutiger neuer Schlüssel."""
    from app.core.brep import edit

    exact_kernel()
    tube = edit.boolean("difference", [edit.cylinder(20.0, HEIGHT), edit.cylinder(10.0, HEIGHT)])
    legacy = f"e:0.00,0.00,{HEIGHT:.2f}:0.000,0.000,0.000"
    document = _document(legacy)
    outer = _EdgeChooser(lambda target: target.length > 2.0 * math.pi * 7.5)

    result = evaluate(
        document,
        _profile(),
        registry=_registry(tube, "brep"),
        ask=outer,
        question_context=outer.context,
    )

    assert result.complete and not result.matches, "kein Datensatz — der Schlüssel ist eindeutig"
    rims = edges.described_by_key(edit.edges_of(tube))
    assert len(rims[legacy]) == 2, "der Alias trifft beide Ränder"
    chosen_key = result.answers[2]["edge_keys"]
    assert chosen_key != legacy and chosen_key.endswith(":r:10.00")
    assert len(rims[chosen_key]) == 1
    history = History(document)
    assert history.record_answers(result.answers)
    again = evaluate(
        document,
        _profile(),
        registry=_registry(tube, "brep"),
        ask=lambda *_: pytest.fail("der eindeutige Schlüssel fragt nicht mehr"),
    )
    assert again.complete and not again.answers


def test_the_bead_binds_on_the_mesh_even_for_an_exact_body(captured: dict[str, Any]) -> None:
    """*Wulst* vereinigt am Netz, also fragt die Bindung an den Zügen des Netzes."""
    body, kind = _body("brep")
    chooser = _EdgeChooser(_right_box)

    result = evaluate(
        _document(COLLIDING_KEY, operation="bead_edges", size=1.5),
        _profile(),
        registry=_registry(body, kind, "bead_edges"),
        ask=chooser,
        question_context=chooser.context,
    )

    assert result.complete and len(chooser.asked) == 1
    assert captured["kernel"] == "mesh" and len(captured["selected_edges"]) == 1
    assert _bound_middle(captured)[0] == pytest.approx(GAP, abs=1e-6)


def test_bind_edges_leaves_operations_without_an_edge_field_alone() -> None:
    load_operations()
    spec = REGISTRY.get("create_brep_cylinder")
    operation = Operation(id=1, op=spec.name, inputs=(), outputs=("obj_1",), params={})

    binding = bind_edges(
        spec,
        operation,
        {},
        [],
        {},
        ask=lambda *_: pytest.fail("nichts zu fragen"),
        announce=None,
        check_cancelled=lambda: None,
    )

    assert binding.selections == {} and binding.context == {} and binding.records == {}


# --- die ausdrückliche Auswahl am Netz --------------------------------------------------


@pytest.mark.parametrize("work", [edges.round_edges, edges.bevel_edges, edges.bead_edges])
def test_an_explicit_selection_takes_precedence_over_keys_and_group_on_a_mesh(work: Any) -> None:
    body = _mesh_pair()
    found = edges_of(body)
    wanted_index = next(
        index for index, entry in enumerate(found) if entry.middle[0] > GAP / 2 and entry.upright
    )
    other = next(entry for entry in found if entry.flat)

    outcome = work(body, 2.0, "vertical", [edge_key(other)], selected_edges=(wanted_index,))
    group = work(body, 2.0, "vertical")

    changed = abs(outcome.mesh.volume - body.volume)
    by_group = abs(group.mesh.volume - body.volume)
    if work is edges.round_edges:
        assert changed == pytest.approx(HEIGHT * 2.0**2 * (1.0 - math.pi / 4.0), rel=0.1)
    elif work is edges.bevel_edges:
        assert changed == pytest.approx(HEIGHT * 2.0**2 / 2.0, rel=0.02)
    assert 0.0 < changed < by_group / 4.0, "eine Kante, nicht die Gruppe und nicht der Schlüssel"


@pytest.mark.parametrize("indices", [(), (-1,), (10**6,), (1.5,), (True,), ("0",)], ids=repr)
def test_an_invalid_mesh_selection_is_rejected_with_the_shared_sentence(indices: Any) -> None:
    body = _mesh_pair()
    with pytest.raises(ValidationError) as rejected:
        edges.round_edges(body, 2.0, "all", selected_edges=indices)
    assert rejected.value.detail == EDGE_SELECTION_REJECTED
    assert rejected.value.suggestions


# --- der Datensatz ------------------------------------------------------------------------


def _record() -> tuple[str, dict[str, Any]]:
    keys = [COLLIDING_KEY]
    fingerprint = {
        "middle": [0.0, 15.0, 10.0],
        "direction": [0.0, 0.0, 1.0],
        "extent": 10.0,
        "length": 20.0,
    }
    other = {**fingerprint, "middle": [GAP, 15.0, 10.0]}
    record = {
        "object_id": "obj_1",
        "field": "edge_keys",
        "keys": keys,
        "scope": "fassung",
        "candidates": {COLLIDING_KEY: [fingerprint, other]},
        "decisions": {COLLIDING_KEY: {"candidate": 1}},
    }
    return edge_answer_key("obj_1", "edge_keys", keys), record


def test_a_valid_edge_answer_passes_and_belongs_to_an_input() -> None:
    key, record = _record()
    validate_edge_answer(key, record, ("obj_1",))
    validate_matches({key: record}, outputs=("obj_9",), inputs=("obj_1",))
    with pytest.raises(ValueError, match="object_id"):
        validate_edge_answer(key, record, ("obj_2",))
    with pytest.raises(ValueError, match="object_id"):
        validate_matches({key: record}, outputs=("obj_1",), inputs=())


@pytest.mark.parametrize(
    ("damage", "problem"),
    [
        (lambda r: r.pop("scope"), "edge_answer"),
        (lambda r: r.update(scope=""), "scope"),
        (lambda r: r.update(keys=[]), "keys"),
        (lambda r: r.update(keys=[COLLIDING_KEY, COLLIDING_KEY]), "keys"),
        (lambda r: r.update(field=""), "field"),
        (lambda r: r.update(candidates={}), "candidates"),
        (lambda r: r.update(candidates={"fremd": r["candidates"][COLLIDING_KEY]}), "candidates"),
        (
            lambda r: r["candidates"].update({COLLIDING_KEY: r["candidates"][COLLIDING_KEY][:1]}),
            "candidates",
        ),
        (lambda r: r["candidates"][COLLIDING_KEY][0].pop("length"), "fingerprint"),
        (lambda r: r["candidates"][COLLIDING_KEY][0].update(extent=float("nan")), "fingerprint"),
        (lambda r: r.update(decisions={}), "decisions"),
        (lambda r: r.update(decisions={COLLIDING_KEY: {"candidate": 2}}), "candidate_index"),
        (lambda r: r.update(decisions={COLLIDING_KEY: {"candidate": True}}), "candidate_index"),
        (lambda r: r.update(decisions={COLLIDING_KEY: {"not_carried": True}}), "decision"),
    ],
)
def test_a_damaged_edge_answer_names_its_field(
    damage: Callable[[dict[str, Any]], Any], problem: str
) -> None:
    key, record = _record()
    damage(record)
    with pytest.raises(ValueError, match=f"^{problem}$"):
        validate_edge_answer(key, record, ("obj_1",))


def test_domains_do_not_cross() -> None:
    key, record = _record()
    with pytest.raises(ValueError, match="key"):
        validate_edge_answer('group:["obj_1",["hole_1"]]', record, ("obj_1",))
    with pytest.raises(ValueError, match="key"):
        validate_edge_answer(edge_answer_key("obj_1", "edge_keys", ["anders"]), record, ("obj_1",))
    from app.core.perceive.match_records import validate_group

    with pytest.raises(ValueError, match="key"):
        validate_group(key, record, ("obj_1",))
    assert domain_of(key) == EDGE_DOMAIN and domain_of("fremd:x") is None


def test_history_keeps_an_edge_answer_with_its_input_and_drops_it_with_a_new_one() -> None:
    key, record = _record()
    group_key = 'group:["obj_1",["hole_1"]]'
    entry = Operation(
        id=2,
        op="fillet_edges",
        inputs=("obj_1",),
        outputs=("obj_1",),
        params={},
        matches={key: record, group_key: {"object_id": "obj_1"}},
    )

    same = _copy_operation_matches(entry, previous_outputs=("obj_1",), previous_inputs=("obj_1",))
    assert set(same.matches) == {key, group_key}
    new_output = _copy_operation_matches(
        dataclasses.replace(entry, outputs=("obj_2",)),
        previous_outputs=("obj_1",),
        previous_inputs=("obj_1",),
    )
    assert set(new_output.matches) == {key}, "die Kantenantwort hängt am Eingang, nicht am Ausgang"
    new_input = _copy_operation_matches(
        dataclasses.replace(entry, inputs=("obj_7",)),
        previous_outputs=("obj_1",),
        previous_inputs=("obj_1",),
    )
    assert set(new_input.matches) == {group_key}, "ein anderer Eingang trägt keine alte Kantenwahl"


def test_the_project_schema_rejects_an_edge_answer_on_a_body_that_is_not_an_input(
    tmp_path: Path,
) -> None:
    """Der Leser prüft Kantenantworten gegen die Eingänge — und der Schreiber ebenso."""
    from app.core.scene.project import _validate_operation_schema, new_project

    key, record = _record()
    stored = {
        "id": 1,
        "op": "create_brep_box",
        "in": [],
        "out": ["obj_1"],
        "matches": {key: record},
    }
    with pytest.raises(ValueError, match=r"schema:ops\[0\]\.matches\.object_id"):
        _validate_operation_schema(stored, "ops[0]")
    stored["in"] = ["obj_1"]
    _validate_operation_schema(stored, "ops[0]")

    project = new_project("centauri-carbon-2", "petg")
    project.document.ops.append(
        Operation(
            id=1,
            op="create_brep_box",
            inputs=(),
            outputs=("obj_1",),
            params={},
            matches={key: record},
        )
    )
    with pytest.raises(ValueError, match=r"matches.object_id"):
        save(project, tmp_path / "falsch.p3d")


def test_an_edge_answer_survives_save_and_load() -> None:
    body, kind = _body("mesh")
    from app.core.scene.project import ProjectSources, new_project

    project = new_project("centauri-carbon-2", "petg")
    project.document.ops.extend(_document(COLLIDING_KEY).ops)
    chooser = _EdgeChooser(_right_box)
    result = evaluate(
        project.document,
        _profile(),
        registry=_registry(body, kind),
        ask=chooser,
        question_context=chooser.context,
        sources=ProjectSources(project),
    )
    assert result.complete and History(project.document).record_matches(result.matches)
    (key,) = result.matches[2]

    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        reopened = load(save(project, Path(folder) / "kante.p3d"))
    assert reopened.document.format_version == FORMAT_VERSION
    assert reopened.document.ops[-1].matches == {key: result.matches[2][key]}


def test_the_v29_example_carries_an_edge_answer_and_v28_migrates_unchanged() -> None:
    folder = Path(__file__).parent / "data" / "projects"
    project = load(folder / "example_v29.p3d")
    # Das Beispiel trägt seine Fassung im Namen; ``FORMAT_VERSION`` läuft weiter.
    assert project.document.format_version == FORMAT_VERSION >= 29
    records = project.document.ops[1].matches
    (key,) = records
    assert (
        domain_of(key) == EDGE_DOMAIN
        and records[key]["object_id"] in project.document.ops[1].inputs
    )
    native = [key for key in project.document.ops[0].matches if domain_of(key) == NATIVE_DOMAIN]
    assert len(native) == 1, "die v28-Antwort reist unverändert mit"

    raw = project_data(folder / "example_v28.p3d")
    older = load(folder / "example_v28.p3d")
    assert older.document.format_version == FORMAT_VERSION
    assert older.document.ops[0].matches == raw["ops"][0]["matches"]
    assert not older.document.ops[1].matches


def test_edges_of_is_remembered_at_the_mesh_and_forgets_with_its_geometry() -> None:
    """Die Auswertung bindet die Kanten vor dem Cache, die Operation verkettet dieselben
    Züge gleich darauf noch einmal — am Lochblech 20 mal 20 zweimal 201 ms (Review,
    21.09.2026). Gemerkt wird am Netz selbst, und mit dessen Geometrie verfällt es."""
    mesh = MeshData.of(trimesh.creation.box((10.0, 6.0, 4.0)))
    first = edges_of(mesh)
    second = edges_of(mesh)
    assert first == second and first is not second, "jeder Aufrufer bekommt seine eigene Liste"
    assert any(key.startswith("solidon_edges_") for key in mesh.raw._cache.cache)
    mesh.raw.vertices[:, 2] *= 2.0
    taller = edges_of(mesh)
    assert len(taller) == len(first)
    assert sum(edge.length for edge in taller) > sum(edge.length for edge in first), (
        "nach einer Geometrieänderung wird neu verkettet, nicht aus dem Gedächtnis gelesen"
    )
