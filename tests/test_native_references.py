"""Alte Flächenbezüge halten am umgebauten exakten Körper an, bis ein Beleg sie trägt (§21.2).

Drei Belege gibt es, und nur drei: Die Operation hat das Merkmal unverändert
durchgereicht, sie hat den Übergang selbst ausgestellt
(``OpResult.feature_continuations``), oder die geometrische Zuordnung findet
es eindeutig unter demselben Namen wieder. Ein frisch vergebener gleicher
Name ist keiner davon — ``features_of`` nummeriert neu.
"""

from __future__ import annotations

import dataclasses
import json
import math
from importlib import import_module
from pathlib import Path

import pytest

from app.core.errors import InternalError, NativeReferenceLost
from app.core.perceive.matching import MatchResult
from app.core.scene import History, OperationDraft, ResultCache, evaluate, orphans
from app.core.scene.cache import CACHE_FORMAT_VERSION, CachedResult, DiskCache
from app.core.scene.project import ProjectSources, new_project
from app.core.types import (
    Document,
    Feature,
    FeatureContinuation,
    FeatureRef,
    Fit,
    Operation,
    OpResult,
    Profile,
    Scene,
    SceneObject,
)
from tests.helpers import FakeMesh, exact_kernel, make_object
from tests.test_cache import FakeCodec

# Über den Paketnamen käme die **Funktion** ``evaluate`` — das Paket exportiert
# sie träge unter demselben Namen wie das Modul.
evaluate_module = import_module("app.core.scene.evaluate")

# --- der Beleg reist durch beide Cacheebenen ---------------------------------------


def _continued(source_id: str = "obj_1") -> tuple[tuple[FeatureContinuation, ...], ...]:
    return (
        (FeatureContinuation(FeatureRef(source_id, "hole_1"), "hole_1"),),
        (FeatureContinuation(FeatureRef(source_id, "face_2"), "face_9"),),
    )


def test_the_result_carries_no_continuation_unless_the_operation_issued_one() -> None:
    assert OpResult(outputs=[]).feature_continuations == ()
    assert CachedResult(objects=()).continuations == ()


def test_operation_continuation_releases_the_displaced_match_candidate() -> None:
    matched = MatchResult(mapping={"fillet_1": "fillet_8"}, fresh=())

    continued = evaluate_module._continued_match_result(matched, ("fillet_1",))

    assert continued.mapping == {"fillet_1": "fillet_1"}
    assert continued.fresh == ("fillet_8",)


def test_continuations_survive_the_disk_level_per_output(tmp_path: Path) -> None:
    """Zwei Ausgaben, zwei Belegfolgen — die Zuordnung ist ordinal und bleibt es."""
    cache = DiskCache(codec=FakeCodec(), directory=tmp_path)
    stored = CachedResult(
        objects=(make_object("obj_1"), make_object("obj_2")), continuations=_continued()
    )
    cache.put("key", stored)

    again = cache.get("key")

    assert again is not None
    assert again.continuations == _continued()
    payload = json.loads(next(tmp_path.rglob("objects.json")).read_text(encoding="utf-8"))
    assert payload["format_version"] == CACHE_FORMAT_VERSION
    assert payload["continuations"][1] == [{"source": "obj_1:face_2", "target": "face_9"}]


def test_the_memory_level_keeps_the_continuations(tmp_path: Path) -> None:
    cache = ResultCache(disk=DiskCache(codec=FakeCodec(), directory=tmp_path))
    stored = CachedResult(objects=(make_object("obj_1"),), continuations=_continued()[:1])
    cache.put("key", stored, to_disk=True)

    assert cache.get("key") is stored
    fresh = ResultCache(disk=DiskCache(codec=FakeCodec(), directory=tmp_path))
    from_disk = fresh.get("key")
    assert from_disk is not None and from_disk.continuations == _continued()[:1]


def test_an_entry_from_before_the_field_is_not_read(tmp_path: Path) -> None:
    """Ein alter Eintrag kennt keinen Beleg — er darf nicht als „kein Beleg" gelten."""
    cache = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache.put("key", CachedResult(objects=(make_object("obj_1"),), continuations=_continued()[:1]))
    index = next(tmp_path.rglob("objects.json"))
    payload = json.loads(index.read_text(encoding="utf-8"))
    payload["format_version"] = CACHE_FORMAT_VERSION - 1
    index.write_text(json.dumps(payload), encoding="utf-8")

    assert DiskCache(codec=FakeCodec(), directory=tmp_path).get("key") is None


@pytest.mark.parametrize(
    "damage",
    [
        "not a list",
        [[{"source": "obj_1:hole_1", "target": "hole_1"}], []],
        [[{"source": "malformed", "target": "hole_1"}]],
        [[{"source": "obj_1:hole_1", "target": ""}]],
        [[{"source": "obj_1:hole_1"}]],
        [["obj_1:hole_1"]],
    ],
)
def test_a_damaged_continuation_drops_the_whole_entry(tmp_path: Path, damage: object) -> None:
    cache = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache.put("key", CachedResult(objects=(make_object("obj_1"),), continuations=_continued()[:1]))
    index = next(tmp_path.rglob("objects.json"))
    payload = json.loads(index.read_text(encoding="utf-8"))
    payload["continuations"] = damage
    index.write_text(json.dumps(payload), encoding="utf-8")

    assert DiskCache(codec=FakeCodec(), directory=tmp_path).get("key") is None
    assert not list(tmp_path.rglob("objects.json")), "ein beschädigter Eintrag wird verworfen"


# --- Struktur und Bezug des Belegs --------------------------------------------------


def _hole(name: str = "hole_1") -> Feature:
    return Feature(id=name, kind="hole", provenance="detected", params={"diameter": 6.0})


def _body(object_id: str, features: dict[str, Feature]) -> SceneObject:
    return SceneObject(id=object_id, name="Teil", mesh=FakeMesh(), features=features)  # type: ignore[arg-type]


def _output(*names: str) -> SceneObject:
    return _body("obj_1", {name: _hole(name) for name in names})


def _operation() -> Operation:
    return Operation(id=2, op="resize_hole", inputs=("obj_1",), outputs=("obj_1",))


def test_a_valid_continuation_is_returned_per_output() -> None:
    result = CachedResult(
        objects=(_output("hole_1"),),
        continuations=((FeatureContinuation(FeatureRef("obj_1", "hole_1"), "hole_1"),),),
    )

    checked = evaluate_module._checked_continuations(
        _operation(), result, {"obj_1": {"hole_1": _hole()}}
    )

    assert checked == result.continuations
    assert (
        evaluate_module._checked_continuations(
            _operation(), CachedResult(objects=(_output("hole_1"),)), {"obj_1": {"hole_1": _hole()}}
        )
        == ()
    )


@pytest.mark.parametrize(
    ("continuations", "previous"),
    [
        # Quelle ist kein Eingang dieser Operation.
        (
            ((FeatureContinuation(FeatureRef("obj_7", "hole_1"), "hole_1"),),),
            {"obj_1": {"hole_1": _hole()}},
        ),
        # Quelle trug das Merkmal nicht.
        (
            ((FeatureContinuation(FeatureRef("obj_1", "hole_3"), "hole_1"),),),
            {"obj_1": {"hole_1": _hole()}},
        ),
        # Ziel fehlt an der Ausgabe.
        (
            ((FeatureContinuation(FeatureRef("obj_1", "hole_1"), "hole_9"),),),
            {"obj_1": {"hole_1": _hole()}},
        ),
        # Doppeltes Ziel.
        (
            (
                (
                    FeatureContinuation(FeatureRef("obj_1", "hole_1"), "hole_1"),
                    FeatureContinuation(FeatureRef("obj_1", "hole_2"), "hole_1"),
                ),
            ),
            {"obj_1": {"hole_1": _hole(), "hole_2": _hole("hole_2")}},
        ),
        # Doppelte Quelle.
        (
            (
                (
                    FeatureContinuation(FeatureRef("obj_1", "hole_1"), "hole_1"),
                    FeatureContinuation(FeatureRef("obj_1", "hole_1"), "hole_2"),
                ),
            ),
            {"obj_1": {"hole_1": _hole()}},
        ),
        # Eine Belegfolge zu viel.
        (((), ()), {"obj_1": {"hole_1": _hole()}}),
    ],
)
def test_an_invalid_continuation_is_a_programming_error(continuations, previous) -> None:
    """Falsche Quelle, fehlendes Ziel, Doppelziel: abgewiesen, nie still zu „kein Beleg"."""
    result = CachedResult(objects=(_output("hole_1", "hole_2"),), continuations=continuations)

    with pytest.raises(InternalError):
        evaluate_module._checked_continuations(_operation(), result, previous)


def test_an_invalid_continuation_stops_the_chain_before_any_output(profile: Profile) -> None:
    """Der Halt liegt an der Erzeugergrenze: kein Objekt, kein Hash, kein Folgecache."""
    from app.core.registry import Registry, register_op
    from app.core.types import BaseParams, Document, OpContext

    registry = Registry()

    @register_op(
        name="make_body",
        title="Körper",
        category="primitive",
        params=BaseParams,
        consumes=0,
        produces=1,
        registry=registry,
    )
    def make(ctx: OpContext) -> OpResult:
        return OpResult(outputs=[_body("", {"hole_1": _hole()})])

    @register_op(
        name="claim_body",
        title="Beleg behaupten",
        category="prepare",
        params=BaseParams,
        consumes=1,
        produces=1,
        registry=registry,
    )
    def claim(ctx: OpContext) -> OpResult:
        return OpResult(
            outputs=[dataclasses.replace(ctx.inputs[0], features={})],
            feature_continuations=(
                (FeatureContinuation(FeatureRef("obj_1", "hole_1"), "hole_1"),),
            ),
        )

    document = Document(
        format_version=1,
        app_version="0.0.1",
        ops=[
            Operation(id=1, op="make_body", outputs=("obj_1",)),
            Operation(id=2, op="claim_body", inputs=("obj_1",), outputs=("obj_1",)),
        ],
    )
    cache = ResultCache()

    result = evaluate(document, profile, registry=registry, cache=cache)

    assert result.stopped_at == 2
    assert "hole_1" in result.scene.objects["obj_1"].features, "der letzte gültige Stand bleibt"
    assert [f.code for f in result.scene.report.findings if f.op_id == 2] == [
        "op.claim_body.InternalError"
    ]
    assert cache.statistics.hits == 0 and not cache._entries, "ein Halt schreibt keinen Cache"


# --- die Auswertungsgrenze am exakten Körper ----------------------------------------


def _exact_box():
    edit = exact_kernel()
    from app.core.brep.features import features_of

    solid = edit.box(10.0, 10.0, 10.0)
    return solid, features_of(solid)


def _rebuilt(features: dict[str, Feature]) -> dict[str, Feature]:
    """Dieselben Namen, aber neu gerechnet — nichts davon ist „unverändert durchgereicht"."""
    return {
        name: dataclasses.replace(
            feature, params={**feature.params, "area": float(feature.params["area"]) + 1e-9}
        )
        for name, feature in features.items()
    }


def _matched(mapping: dict[str, str], *, orphaned: tuple[str, ...] = ()) -> MatchResult:
    return MatchResult(mapping=mapping, orphaned=orphaned)


def _native_call(
    monkeypatch: pytest.MonkeyPatch,
    matched: MatchResult | None,
    *,
    features: dict[str, Feature] | None = None,
    needed: dict[str, tuple[str, ...]] | None,
    touches_features: bool = False,
    continuations: tuple[FeatureContinuation, ...] = (),
) -> tuple[SceneObject, list[int]]:
    solid, found = _exact_box()
    calls: list[int] = []

    def fake_match(*args, **kwargs):
        calls.append(1)
        assert matched is not None, "die Zuordnung darf hier gar nicht laufen"
        return dataclasses.replace(matched, mapping=dict(matched.mapping))

    monkeypatch.setattr(evaluate_module, "match", fake_match)
    body = SceneObject(
        id="body",
        name="Quader",
        kind="brep",
        mesh=solid,
        features=_rebuilt(found) if features is None else features,
    )
    outcome = evaluate_module._with_features(
        body,
        dict(found),
        Operation(id=2, op="push_face", inputs=("body",), outputs=("body",)),
        lambda *_: pytest.fail("nichts zu fragen"),
        [],
        referenced=set(needed or ()),
        touches_features=touches_features,
        needed=needed,
        continuations=continuations,
    )
    return outcome, calls


def _rounding_transition(*, changed_neighbour: bool = False) -> tuple[SceneObject, SceneObject]:
    """Drei echte Rundungen; der linke Nachbar bleibt R2 oder verlangt als R3 eine Wahl."""
    edit = exact_kernel()
    from app.core.brep.features import features_of

    def body(corners: tuple[tuple[bool, bool], ...], *, changed: bool) -> SceneObject:
        solid = edit.box(40.0, 30.0, 20.0)
        selected = [
            edit.edge_key(edge)
            for edge in edit.edges_of(solid)
            if edge.upright and (edge.middle[0] > 0.0, edge.middle[1] > 0.0) in corners
        ]
        assert len(selected) == 3
        solid = edit.fillet(solid, 2.0, "named", selected)
        if changed:
            chosen = next(
                feature
                for feature in features_of(solid).values()
                if feature.kind == "fillet"
                and feature.params["centre"][0] > 0.0
                and feature.params["centre"][1] < 0.0
            )
            solid = edit.reround(
                solid,
                chosen.params["centre"],
                2.0,
                12.0,
                selected_faces=solid.complete_faces_of_triangles(chosen.face_indices),
            )
            if changed_neighbour:
                neighbour = next(
                    feature
                    for feature in features_of(solid).values()
                    if feature.kind == "fillet"
                    and feature.params["centre"][0] < 0.0
                    and feature.params["centre"][1] > 0.0
                )
                solid = edit.reround(
                    solid,
                    neighbour.params["centre"],
                    2.0,
                    3.0,
                    selected_faces=solid.complete_faces_of_triangles(neighbour.face_indices),
                )
        by_corner = {
            (feature.params["centre"][0] > 0.0, feature.params["centre"][1] > 0.0): feature
            for feature in features_of(solid).values()
            if feature.kind == "fillet"
        }
        assert len(by_corner) == 3
        features = {
            f"fillet_{number}": dataclasses.replace(by_corner[corner], id=f"fillet_{number}")
            for number, corner in enumerate(corners, 1)
        }
        return SceneObject(
            id="obj_1", name="Drei Rundungen", mesh=solid, kind="brep", features=features
        )

    previous = body(((False, True), (False, False), (True, False)), changed=False)
    current = body(((True, True), (False, True), (True, False)), changed=True)
    return previous, current


@pytest.mark.parametrize("continued", [False, True])
def test_unchanged_native_features_do_not_rename_a_proven_changed_rounding(
    continued: bool,
) -> None:
    """Die unveränderte Nachbarrundung darf die belegte Kennung nicht verdrängen."""
    previous, current = _rounding_transition()
    matched = evaluate_module.match(
        previous.features,
        current.features,
        current.mesh.bounds.centre,
        current.mesh.bounds.diagonal,
    )
    assert matched.mapping == {"fillet_1": "fillet_2"}
    assert set(matched.orphaned) == {"fillet_2", "fillet_3"}
    continuation = FeatureContinuation(FeatureRef("obj_1", "fillet_3"), "fillet_3")

    def bind() -> SceneObject:
        return evaluate_module._with_features(
            current,
            dict(previous.features),
            Operation(id=2, op="resize_feature", inputs=("obj_1",), outputs=("obj_1",)),
            lambda question, choices: pytest.fail(f"Unerwartete Zuordnungsfrage: {question}"),
            [],
            referenced={"fillet_3"},
            touches_features=True,
            needed={"fillet_3": ("Operation 3",)},
            continuations=(continuation,) if continued else (),
        )

    if not continued:
        with pytest.raises(NativeReferenceLost) as stopped:
            bind()
        assert stopped.value.references == (FeatureRef("obj_1", "fillet_3"),)
        return

    result = bind()
    chosen = result.features["fillet_3"]
    assert chosen.params["radius"] == pytest.approx(12.0, abs=1e-6, rel=0.0)
    assert chosen.face_indices == current.features["fillet_3"].face_indices
    assert result.features["fillet_1"].face_indices == current.features["fillet_2"].face_indices
    assert result.features["fillet_4"].face_indices == current.features["fillet_1"].face_indices


@pytest.mark.parametrize("accepted", [False, True])
def test_native_reselection_does_not_rename_a_proven_changed_rounding(accepted: bool) -> None:
    """Die ausdrückliche Wahl links oben lässt die belegte R12 rechts unten stehen."""
    previous, current = _rounding_transition(changed_neighbour=True)
    matched = evaluate_module.match(
        previous.features,
        current.features,
        current.mesh.bounds.centre,
        current.mesh.bounds.diagonal,
    )
    # Beide Radiuswechsel brauchen einen Beleg: R12 liefert die Operation,
    # R3 links oben wird erst durch die ausdrückliche Wahl weitergeführt.
    assert not matched.mapping
    assert set(matched.orphaned) == {"fillet_1", "fillet_2", "fillet_3"}
    assert not evaluate_module._unchanged(
        previous.features["fillet_1"], current.features["fillet_2"]
    )
    continued = evaluate_module._continued_match_result(matched, {"fillet_3"})
    assert continued.mapping == {"fillet_3": "fillet_3"}
    assert continued.orphaned == ("fillet_1", "fillet_2")
    asked: list[tuple[str, ...]] = []

    def choose(question: str, choices: list[str]) -> str:
        assert "fillet_1" in question
        assert "fillet_5" in choices and "fillet_3" not in choices
        asked.append(tuple(choices))
        return "fillet_5" if accepted else "Nicht weiterführen"

    recorded: dict[str, dict] = {}

    def bind() -> SceneObject:
        return evaluate_module._with_features(
            current,
            dict(previous.features),
            Operation(id=2, op="resize_feature", inputs=("obj_1",), outputs=("obj_1",)),
            choose,
            [],
            recorded=recorded,
            referenced={"fillet_1", "fillet_3"},
            touches_features=True,
            needed={"fillet_1": ("Operation 3",), "fillet_3": ("Operation 4",)},
            continuations=(FeatureContinuation(FeatureRef("obj_1", "fillet_3"), "fillet_3"),),
            scope="rundungsumbau:0",
        )

    if not accepted:
        with pytest.raises(NativeReferenceLost) as stopped:
            bind()
        assert stopped.value.references == (FeatureRef("obj_1", "fillet_1"),)
    else:
        output = bind()
        assert set(output.features) == {"fillet_1", "fillet_3", "fillet_4"}
        assert output.features["fillet_3"].params["radius"] == pytest.approx(12.0, abs=1e-6)
        assert output.features["fillet_3"].face_indices == current.features["fillet_3"].face_indices
        assert output.features["fillet_1"].params["radius"] == pytest.approx(3.0, abs=1e-6)
        assert output.features["fillet_1"].face_indices == current.features["fillet_2"].face_indices
        assert output.features["fillet_4"].face_indices == current.features["fillet_1"].face_indices
        assert len(recorded) == 1
        assert next(iter(recorded)).startswith("native-group:")
    assert len(asked) == 1
    assert current.features["fillet_3"].params["radius"] == pytest.approx(12.0, abs=1e-6)


@pytest.mark.parametrize("reselected", [False, True])
def test_a_later_radius_change_uses_the_proven_rounding_after_native_renumbering(
    profile: Profile,
    reselected: bool,
) -> None:
    """Kalt und warm bleiben beide Bezüge richtig, auch nach bestätigter Neuwahl."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY, OperationSpec, Registry
    from app.core.types import BaseParams, OpContext

    previous, current = _rounding_transition(changed_neighbour=reselected)
    load_operations()
    registry = Registry()
    for spec in REGISTRY.all():
        registry.register(spec)
    registry.register(
        OperationSpec(
            name="probe_roundings",
            title="Drei Rundungen",
            category="primitive",
            params=BaseParams,
            fn=lambda ctx: OpResult(outputs=[dataclasses.replace(previous, id="")]),
            consumes=0,
            produces=1,
            touches_features=True,
        )
    )

    def rebuild(ctx: OpContext) -> OpResult:
        source = ctx.inputs[0]
        return OpResult(
            outputs=[dataclasses.replace(current, id=source.id)],
            feature_continuations=(
                (FeatureContinuation(FeatureRef(source.id, "fillet_3"), "fillet_3"),),
            ),
        )

    registry.register(
        OperationSpec(
            name="probe_rebuild_roundings",
            title="Rundungen umbauen",
            category="prepare",
            params=BaseParams,
            fn=rebuild,
            consumes=1,
            produces=1,
            touches_features=True,
        )
    )
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document, registry=registry)
    history.apply("Drei Rundungen", [OperationDraft(op="probe_roundings")])
    target = project.document.ops[0].outputs[0]
    history.apply(
        "Rundungen umbauen", [OperationDraft(op="probe_rebuild_roundings", inputs=(target,))]
    )
    if reselected:
        history.apply(
            "Gewählte Rundung ändern",
            [
                OperationDraft(
                    op="resize_feature",
                    inputs=(target,),
                    params={"at_feature": "fillet_1", "diameter": 8.0},
                    seed=1,
                )
            ],
        )
    history.apply(
        "Belegte Rundung ändern",
        [
            OperationDraft(
                op="resize_feature",
                inputs=(target,),
                params={"at_feature": "fillet_3", "diameter": 20.0},
                seed=1,
            )
        ],
    )
    cache = ResultCache()
    asked: list[tuple[str, ...]] = []

    def choose(question: str, choices: list[str]) -> str:
        assert reselected, f"Unerwartete Zuordnungsfrage: {question}"
        assert not asked, "Die gespeicherte Wahl muss kalt und warm wiederverwendet werden."
        assert "fillet_1" in question
        assert "fillet_5" in choices and "fillet_3" not in choices
        asked.append(tuple(choices))
        return "fillet_5"

    for _warm in (False, True):
        result = evaluate(
            project.document,
            profile,
            registry=registry,
            sources=ProjectSources(project),
            cache=cache,
            ask=choose,
        )
        assert result.complete, [
            (finding.code, dict(finding.values)) for finding in result.scene.report.findings
        ]
        assert not result.answers and not result.blocked_references
        if reselected and not _warm:
            assert history.record_matches(result.matches)
        else:
            assert not result.matches
        output = result.scene.objects[target]
        chosen = output.features["fillet_3"]
        assert chosen.params["centre"][0] > 0.0 and chosen.params["centre"][1] < 0.0
        assert chosen.params["radius"] == pytest.approx(10.0, abs=1e-6, rel=0.0)
        neighbours = [
            feature
            for name, feature in output.features.items()
            if feature.kind == "fillet" and name != "fillet_3"
        ]
        assert len(neighbours) == 2
        neighbour_radius = 4.0 if reselected else 2.0
        for feature in neighbours:
            assert feature.params["centre"][1] > 0.0
            radius = neighbour_radius if feature.params["centre"][0] < 0.0 else 2.0
            assert feature.params["radius"] == pytest.approx(radius, abs=1e-6, rel=0.0)
        assert output.features["fillet_1"].params["centre"][0] < 0.0
        # Drei Viertelkreisrundungen über 20 mm: R2, R2 oder R4, und R10.
        assert output.mesh.volume == pytest.approx(
            40.0 * 30.0 * 20.0 - (4.0 + neighbour_radius**2 + 100.0) * (1.0 - math.pi / 4.0) * 20.0,
            abs=1e-6,
            rel=0.0,
        )
        assert output.mesh.is_closed and output.mesh.is_watertight
        assert output.mesh.solid_count == 1
    assert cache.statistics.hits >= 3
    assert len(asked) == int(reselected)


def test_a_reference_found_under_the_same_name_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _solid, found = _exact_box()
    name = next(iter(found))

    outcome, calls = _native_call(
        monkeypatch, _matched({name: name}), needed={name: ("Passung deckel",)}
    )

    assert calls == [1], "ohne Durchreichen und ohne Beleg entscheidet die Zuordnung"
    assert name in outcome.features


def test_a_reference_matched_to_another_name_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein eindeutiger Partner unter neuem Namen ist noch keine Fortführung des alten."""
    _solid, found = _exact_box()
    first, second = list(found)[:2]

    with pytest.raises(NativeReferenceLost) as stopped:
        _native_call(monkeypatch, _matched({first: second}), needed={first: ("Operation 3",)})

    assert stopped.value.references == (FeatureRef("body", first),)
    assert stopped.value.values["where"] == "Operation 3"
    assert stopped.value.values["references"] == [f"body:{first}"]
    assert stopped.value.object_id == "body"


def test_a_fresh_feature_with_the_old_name_does_not_heal_a_lost_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``face_1`` steht wieder da — als Name. Die Zuordnung sagt: verloren."""
    _solid, found = _exact_box()
    name = next(iter(found))

    with pytest.raises(NativeReferenceLost):
        _native_call(monkeypatch, _matched({}, orphaned=(name,)), needed={name: ("Passung a",)})


def test_the_check_runs_without_touches_features(monkeypatch: pytest.MonkeyPatch) -> None:
    """*Fläche versetzen* trägt das Flag nicht und baut trotzdem neu — geprüft wird es."""
    _solid, found = _exact_box()
    name = next(iter(found))

    with pytest.raises(NativeReferenceLost):
        _native_call(
            monkeypatch,
            _matched({}, orphaned=(name,)),
            needed={name: ("Passung a",)},
            touches_features=False,
        )


def test_a_reference_nobody_needs_later_does_not_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Was nur ein früherer Schritt benannt hat, sperrt den bewussten Umbau nicht."""
    _solid, found = _exact_box()
    name = next(iter(found))

    outcome, calls = _native_call(monkeypatch, _matched({key: key for key in found}), needed={})

    assert calls == [1], "Die sichtbaren Namen entstehen unabhängig von späteren Bezügen."
    assert name in outcome.features


def test_an_unchanged_feature_proves_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wer ein Merkmal unverändert durchreicht, braucht keine Zuordnung dafür."""
    _solid, found = _exact_box()
    name = next(iter(found))

    outcome, calls = _native_call(
        monkeypatch, None, features=dict(found), needed={name: ("Passung a",)}
    )

    assert calls == []
    assert outcome.features[name] == found[name]


def test_a_continuation_of_the_operation_carries_the_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Beleg der Operation gilt, auch wo die Zuordnung das Merkmal verlöre."""
    _solid, found = _exact_box()
    name = next(iter(found))

    outcome, calls = _native_call(
        monkeypatch,
        _matched({key: key for key in found}),
        needed={name: ("Passung a",)},
        continuations=(FeatureContinuation(FeatureRef("body", name), name),),
    )

    assert calls == [1]
    assert name in outcome.features


def test_a_continuation_to_another_name_does_not_serve_the_old_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``face_1 → face_9`` sagt, wo die Fläche ist — nicht, dass ``face_1`` sie noch nennt."""
    _solid, found = _exact_box()
    first, second = list(found)[:2]

    with pytest.raises(NativeReferenceLost):
        _native_call(
            monkeypatch,
            _matched({}, orphaned=(first,)),
            needed={first: ("Passung a",)},
            continuations=(FeatureContinuation(FeatureRef("body", first), second),),
        )


def test_a_continuation_of_another_body_does_not_count(monkeypatch: pytest.MonkeyPatch) -> None:
    _solid, found = _exact_box()
    name = next(iter(found))

    with pytest.raises(NativeReferenceLost):
        _native_call(
            monkeypatch,
            _matched({}, orphaned=(name,)),
            needed={name: ("Passung a",)},
            continuations=(FeatureContinuation(FeatureRef("other", name), name),),
        )


def test_over_the_feature_limit_an_unchecked_reference_is_unknown_not_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _solid, found = _exact_box()
    name = next(iter(found))
    monkeypatch.setattr(evaluate_module, "FEATURE_LIMIT_COUNT", 2)

    with pytest.raises(NativeReferenceLost):
        _native_call(monkeypatch, None, needed={name: ("Passung a",)})


def test_a_matched_name_without_a_valid_current_selection_is_not_proven() -> None:
    solid, found = _exact_box()
    name = next(iter(found))
    broken = SceneObject(
        id="body",
        name="Quader",
        kind="brep",
        mesh=solid,
        features={name: dataclasses.replace(found[name], face_indices=(solid.triangle_count,))},
    )
    empty = dataclasses.replace(
        broken, features={name: dataclasses.replace(found[name], face_indices=())}
    )

    assert evaluate_module._unproven_native_references([name], broken, _matched({name: name})) == {
        name
    }
    assert evaluate_module._unproven_native_references([name], empty, _matched({name: name})) == {
        name
    }
    assert evaluate_module._unproven_native_references([name], broken, None) == {name}
    assert evaluate_module._unproven_native_references([], broken, None) == frozenset()


# --- die Lebensdauer eines Verweises --------------------------------------------------


def _reference(where: str, object_id: str, feature_id: str) -> orphans.Reference:
    return orphans.Reference(where, FeatureRef(object_id, feature_id))


def test_only_later_consumers_and_active_fits_are_needed() -> None:
    references = [
        _reference("op:1:face", "obj_1", "face_1"),
        _reference("op:2:face", "obj_1", "face_2"),
        _reference("op:3:face", "obj_1", "face_3"),
        _reference("plane:3:sketch", "", "face_4"),
        _reference("op:3:face", "obj_9", "face_5"),
        _reference("fit:deckel:a", "obj_1", "face_6"),
        _reference("fit:alt:a", "obj_1", "face_7"),
    ]
    positions = {1: 0, 2: 1, 3: 2}

    needed = evaluate_module._needed_after(references, positions, {"deckel"}, 1, "obj_1")

    assert set(needed) == {"face_3", "face_4", "face_6"}
    assert needed["face_3"] == ("Operation 3",)
    assert needed["face_6"] == ("deckel",)


# --- Ende zu Ende am exakten Körper ------------------------------------------------------


#: *Fläche versetzen* in der älteren Form — über eine Richtung statt über die
#: gewählte Fläche. Seit dem 23.09.2026 belegt die Operation mit gewählter
#: Fläche ihre Übergänge selbst (``faces.pushed_features``), und die Deckfläche
#: behält ihren Namen; diese Tests brauchen einen Umbau **ohne** Beleg, und
#: den gibt die Richtungsform weiter.
_UNPROVEN_PUSH: dict[str, float] = {"nx": 0.0, "ny": 0.0, "nz": 1.0}


def _box_project(profile: Profile):
    exact_kernel()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Exakter Quader",
        [OperationDraft(op="create_brep_box", params={"width": 40, "depth": 30, "height": 20})],
    )
    sources = ProjectSources(project)
    first = evaluate(project.document, profile, sources=sources)
    assert first.complete
    faces = first.scene.objects["obj_1"].features
    top = next(
        name
        for name, feature in faces.items()
        if feature.kind == "face" and feature.params["normal"][2] > 0.5
    )
    bottom = next(
        name
        for name, feature in faces.items()
        if feature.kind == "face" and feature.params["normal"][2] < -0.5
    )
    return project, history, sources, top, bottom


def test_a_fit_on_a_face_stops_the_step_that_rebuilds_the_exact_body(profile: Profile) -> None:
    """Weg: Quader, Passung auf die Deckfläche, dann *Fläche versetzen* — Halt am Versetzen."""
    project, history, sources, top, bottom = _box_project(profile)
    project.document.fits.append(
        Fit(name="deckel", a=FeatureRef("obj_1", top), b=FeatureRef("obj_1", bottom), kind="flush")
    )
    history.apply(
        "Fläche versetzen",
        [
            OperationDraft(
                op="push_face", inputs=("obj_1",), params={**_UNPROVEN_PUSH, "distance": 15.0}
            )
        ],
    )

    result = evaluate(project.document, profile, sources=sources)

    assert result.stopped_at == project.document.ops[-1].id
    assert FeatureRef("obj_1", top) in result.blocked_references
    assert all(reference.object_id == "obj_1" for reference in result.blocked_references)
    stop = [f for f in result.scene.report.findings if f.op_id == result.stopped_at]
    assert [f.code for f in stop] == ["op.push_face.NativeReferenceLost"]
    assert stop[0].values["where"] == "deckel"
    assert f"obj_1:{top}" in str(stop[0].values["references"])
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(24000.0, rel=1e-9), (
        "der letzte vollständige Stand bleibt: der Quader vor dem Versetzen"
    )


def test_a_later_step_that_needs_the_moved_face_stops_the_rebuild(profile: Profile) -> None:
    """Der eigene Bezug des Schritts sperrt ihn nicht; der des nächsten Schritts schon."""
    project, history, sources, top, _bottom = _box_project(profile)
    history.apply(
        "Fläche versetzen",
        [
            OperationDraft(
                op="push_face", inputs=("obj_1",), params={**_UNPROVEN_PUSH, "distance": 15.0}
            )
        ],
    )
    alone = evaluate(project.document, profile, sources=sources)
    assert alone.complete, "nur der eigene Bezug: kein Verbraucher danach, kein Halt"
    assert alone.scene.objects["obj_1"].mesh.volume == pytest.approx(42000.0, rel=1e-9)

    history.apply(
        "Noch einmal versetzen",
        [OperationDraft(op="push_face", inputs=("obj_1",), params={"face": top, "distance": 1.0})],
    )
    result = evaluate(project.document, profile, sources=sources)

    assert result.stopped_at == project.document.ops[-2].id, "der Halt liegt am Erzeuger"
    assert FeatureRef("obj_1", top) in result.blocked_references
    stop = [f for f in result.scene.report.findings if f.op_id == result.stopped_at]
    assert stop and str(stop[0].values["where"]).startswith("Operation")


def test_pushing_the_chosen_face_proves_its_own_continuation(profile: Profile) -> None:
    """Mit gewählter Fläche belegt *Fläche versetzen* den Übergang selbst (23.09.2026).

    Die Passung auf der Deckfläche hält danach nicht an; die Deckfläche heißt,
    wie sie hieß, und liegt 15 mm höher.
    """
    project, history, sources, top, bottom = _box_project(profile)
    project.document.fits.append(
        Fit(name="deckel", a=FeatureRef("obj_1", top), b=FeatureRef("obj_1", bottom), kind="flush")
    )
    history.apply(
        "Fläche versetzen",
        [OperationDraft(op="push_face", inputs=("obj_1",), params={"face": top, "distance": 15.0})],
    )

    result = evaluate(project.document, profile, sources=sources)

    assert result.complete and not result.blocked_references
    moved = result.scene.objects["obj_1"].features[top]
    assert moved.kind == "face" and moved.params["centre"][2] == pytest.approx(35.0)


def test_a_step_that_passes_the_faces_through_is_free(profile: Profile) -> None:
    project, history, sources, top, bottom = _box_project(profile)
    project.document.fits.append(
        Fit(name="deckel", a=FeatureRef("obj_1", top), b=FeatureRef("obj_1", bottom), kind="flush")
    )
    history.apply(
        "Umbenennen",
        [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Deckel"})],
    )

    result = evaluate(project.document, profile, sources=sources)

    assert result.complete and not result.blocked_references


def _bore_project(profile: Profile):
    project, history, sources, _top, _bottom = _box_project(profile)
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_brep_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "z": 20.0, "compensate": False},
            )
        ],
    )
    drilled = evaluate(project.document, profile, sources=sources)
    assert drilled.complete
    hole = next(
        name
        for name, feature in drilled.scene.objects["obj_1"].features.items()
        if feature.kind == "hole"
    )
    return project, history, sources, hole


def test_a_deliberate_bore_change_keeps_its_reference_cold_and_warm(profile: Profile) -> None:
    """Ø 6 auf Ø 12 sprengt jede Zuordnungstoleranz — der Beleg der Operation trägt."""
    project, history, sources, hole = _bore_project(profile)
    history.apply(
        "Bohrung ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"at_feature": hole, "diameter": 12.0, "compensate": False},
            )
        ],
    )
    history.apply(
        "Noch einmal ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"at_feature": hole, "diameter": 14.0, "compensate": False},
            )
        ],
    )
    cache = ResultCache()

    cold = evaluate(project.document, profile, sources=sources, cache=cache)
    assert cold.complete, [dict(f.values) | {"code": f.code} for f in cold.scene.report.findings]
    assert cold.scene.objects["obj_1"].features[hole].params["diameter"] == pytest.approx(14.0)

    warm = evaluate(project.document, profile, sources=sources, cache=cache)
    assert warm.complete and cache.statistics.hits >= 3
    assert warm.scene.objects["obj_1"].features[hole].params["diameter"] == pytest.approx(14.0)


@pytest.mark.parametrize("diameter", [4.0, 8.0])
def test_following_a_resized_countersink_keeps_the_floor_in_the_real_stack(
    profile: Profile, diameter: float, tmp_path: Path
) -> None:
    """Der Sackboden bleibt nach gemeinsamem Einlaufwechsel ein echter Folgeschritt."""
    exact_kernel()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 30.0, "depth": 24.0, "height": 12.0}
            )
        ],
    )
    history.apply(
        "Sackbohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "depth": 10.0, "z": 12.0, "compensate": False},
            )
        ],
    )
    history.apply(
        "Senkung",
        [
            OperationDraft(
                op="countersink_hole", inputs=("obj_1",), params={"diameter": 10.0, "z": 12.0}
            )
        ],
    )
    sources = ProjectSources(project)
    cache = ResultCache()
    initial = evaluate(project.document, profile, sources=sources, cache=cache)
    assert initial.complete, initial.scene.report.findings
    features = initial.scene.objects["obj_1"].features
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    floor = next(
        feature
        for feature in features.values()
        if feature.kind == "face" and feature.params["centre"][2] == pytest.approx(2.0)
    )
    history.apply(
        "Bohrung und Senkung ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={
                    "at_feature": hole.id,
                    "diameter": diameter,
                    "entrance_mode": "follow",
                    "compensate": False,
                },
            )
        ],
    )
    history.apply(
        "Boden versetzen",
        [
            OperationDraft(
                op="push_face", inputs=("obj_1",), params={"face": floor.id, "distance": 0.25}
            )
        ],
    )
    for current_cache in (cache, ResultCache()):
        result = evaluate(project.document, profile, sources=sources, cache=current_cache)
        assert result.complete, result.scene.report.findings
        kept = result.scene.objects["obj_1"].features[floor.id]
        assert kept.params["centre"][2] == pytest.approx(2.25)
        assert kept.params["area"] == pytest.approx(math.pi * diameter**2 / 4.0)
    assert history.undo() is not None
    undone = evaluate(project.document, profile, sources=sources, cache=cache)
    assert undone.complete
    assert undone.scene.objects["obj_1"].features[floor.id].params["centre"][2] == pytest.approx(
        2.0
    )
    assert history.redo() is not None
    from app.core.scene.project import load, save

    reopened = load(save(project, tmp_path / "bodenfolge.p3d"))
    reloaded = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert reloaded.complete, reloaded.scene.report.findings
    assert reloaded.scene.objects["obj_1"].features[floor.id].params["centre"][2] == pytest.approx(
        2.25
    )


def test_without_the_operations_continuation_the_same_change_would_stop(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gegenprobe: Es ist der Beleg, der trägt — nicht der Name und nicht die Operation."""
    project, history, sources, hole = _bore_project(profile)
    history.apply(
        "Bohrung ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"at_feature": hole, "diameter": 12.0, "compensate": False},
            )
        ],
    )
    history.apply(
        "Noch einmal ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"at_feature": hole, "diameter": 14.0, "compensate": False},
            )
        ],
    )
    monkeypatch.setattr(evaluate_module, "_checked_continuations", lambda *_: ())

    result = evaluate(project.document, profile, sources=sources)

    assert result.stopped_at == project.document.ops[-2].id
    assert result.blocked_references == (FeatureRef("obj_1", hole),)


# --- der Sperrzustand erreicht den Verweisfilter --------------------------------------------


def test_a_blocked_reference_is_neither_resolved_by_name_nor_asked_again(
    profile: Profile,
) -> None:
    """Der Name steht in der alten Szene — und genau deshalb darf sie nicht antworten."""
    from app.core.types import Document

    scene = Scene(
        objects={
            "obj_1": _body(
                "obj_1",
                {
                    "face_1": Feature(
                        id="face_1", kind="face", provenance="detected", params={"area": 1.0}
                    ),
                    "face_2": Feature(
                        id="face_2", kind="face", provenance="detected", params={"area": 2.0}
                    ),
                },
            )
        },
        profile=profile,
    )
    document = Document(format_version=1, app_version="0.0.1")
    document.fits.append(
        Fit(name="deckel", a=FeatureRef("obj_1", "face_1"), b=FeatureRef("obj_1", "face_2"))
    )
    document.fits.append(
        Fit(name="alt", a=FeatureRef("obj_1", "face_9"), b=FeatureRef("obj_1", "face_2"))
    )
    asked: list[str] = []

    result = orphans.check(
        document,
        scene,
        lambda question, choices: asked.append(question) or choices[0],
        blocked=[FeatureRef("obj_1", "face_1")],
    )

    blocked = [f for f in result.findings if f.code == "feature.blocked"]
    assert len(blocked) == 1 and blocked[0].severity == "error"
    assert blocked[0].values == {"reference": "obj_1:face_1", "where": "deckel"}
    assert blocked[0].feature_ids == ("face_1",) and blocked[0].object_id == "obj_1"
    assert document.fits[0].a == FeatureRef("obj_1", "face_1"), "nichts umgeschrieben"
    assert len(asked) == 1 and "face_9" in asked[0], "der andere verlorene Verweis fragt wie bisher"
    assert result.rewritten == 1


# --- die native Neuwahl: Format 28, Domäne native-group, Erzeugerscope ---------------------


def _pushed_project(profile: Profile, distance: float = 15.0):
    """Quader, bündige Passung auf Deck- und Bodenfläche, dann die Deckfläche versetzt."""
    project, history, sources, top, bottom = _box_project(profile)
    project.document.fits.append(
        Fit(name="deckel", a=FeatureRef("obj_1", top), b=FeatureRef("obj_1", bottom), kind="flush")
    )
    history.apply(
        "Fläche versetzen",
        [
            OperationDraft(
                op="push_face",
                inputs=("obj_1",),
                params={**_UNPROVEN_PUSH, "distance": distance},
            )
        ],
    )
    return project, history, sources, top, bottom


class _Chooser:
    """Antwortet wie ein Kunde, der die versetzte Deckfläche im Bild anklickt.

    Die Auswahl entsteht aus der tatsächlichen Fragegeometrie: ``question_context``
    liefert die ungeklärte Ausgabe als Vorschau, und gewählt wird der Kandidat,
    dessen Mitte auf der neuen Höhe liegt — nicht der erste, nicht ein Name.
    """

    def __init__(self, height: float, *, decline: bool = False) -> None:
        self.height = height
        self.decline = decline
        self.asked: list[str] = []
        self.offered: list[list[str]] = []
        self.preview: object = None
        self.candidates: tuple[tuple[str, str], ...] = ()
        self.previous_reference: tuple[object, str] | None = None

    def context(self, preview, candidates) -> None:
        if preview is not None:
            self.preview = preview
            self.candidates = candidates
            self.previous_reference = preview.question_reference

    def __call__(self, question: str, choices: list[str]) -> str:
        self.asked.append(question)
        self.offered.append(list(choices))
        if self.decline:
            return choices[-1]
        scene = self.preview.scene  # type: ignore[attr-defined]
        for object_id, candidate in self.candidates:
            feature = scene.objects[object_id].features[candidate]
            if abs(float(feature.params["centre"][2]) - self.height) < 1e-6:
                assert candidate in choices
                return candidate
        pytest.fail(f"kein Kandidat auf Höhe {self.height}: {self.candidates}")


def test_the_customer_chooses_the_face_that_carries_the_reference_on(
    profile: Profile, tmp_path: Path
) -> None:
    """Die Wahl gilt als Alias, wird gespeichert, überlebt Wiederöffnen und warmen Cache."""
    from app.core.perceive.match_records import NATIVE_DOMAIN, domain_of
    from app.core.scene import FORMAT_VERSION
    from app.core.scene.project import load, save

    project, history, sources, top, _bottom = _pushed_project(profile)
    push_id = project.document.ops[-1].id
    chooser = _Chooser(35.0)
    cache = ResultCache()

    result = evaluate(
        project.document,
        profile,
        sources=sources,
        cache=cache,
        ask=chooser,
        question_context=chooser.context,
    )

    assert result.complete and not result.blocked_references
    assert len(chooser.asked) == 1 and "exakten Körper neu gebaut" in chooser.asked[0]
    assert chooser.offered[0][-1] == "Nicht weiterführen"
    assert chooser.previous_reference is not None
    old_body, old_feature = chooser.previous_reference
    assert old_body.id == "obj_1"
    assert old_feature == top
    assert hasattr(old_body.mesh, "raw"), "die Ansichtsdreiecke kommen aus dem Auswertungsarbeiter"
    assert old_body.features[top].params["centre"][2] == pytest.approx(20.0)
    body = result.scene.objects["obj_1"]
    assert body.mesh.volume == pytest.approx(42000.0, rel=1e-9)
    assert body.features[top].params["centre"][2] == pytest.approx(35.0)
    assert set(body.features[top].face_indices) <= set(range(body.mesh.triangle_count))
    assert project.document.fits[0].a == FeatureRef("obj_1", top), "der Bezug bleibt, wie er war"
    records = result.matches[push_id]
    (key,) = records
    assert domain_of(key) == NATIVE_DOMAIN
    (decision,) = records[key]["decisions"].values()
    assert list(records[key]["decisions"]) == [top] and "candidate" in decision
    chosen = records[key]["candidates"][decision["candidate"]]
    assert chosen["claims"] == [top] and chosen["fingerprint"]["kind"] == "face"
    assert chosen["fingerprint"]["relative"][2] > 0.0, "die gewählte Fläche liegt oben"
    assert records[key]["scope"] and records[key]["object_id"] == "obj_1"
    assert records[key]["old_ids"] == [top]

    assert history.record_matches(result.matches)
    again = evaluate(
        project.document,
        profile,
        sources=sources,
        cache=cache,
        ask=lambda *_: pytest.fail("die gespeicherte Wahl gilt"),
    )
    assert again.complete and not again.matches
    assert cache.statistics.hits >= 1, "der Erzeuger bleibt ein Cachetreffer"
    assert again.scene.objects["obj_1"].features[top].params["centre"][2] == pytest.approx(35.0)

    reopened = load(save(project, tmp_path / "neuwahl.p3d"))
    assert reopened.document.format_version == FORMAT_VERSION
    assert reopened.document.ops[-1].matches == records
    cold = evaluate(
        reopened.document,
        profile,
        sources=ProjectSources(reopened),
        ask=lambda *_: pytest.fail("auch nach dem Wiederöffnen gilt sie"),
    )
    assert cold.complete
    assert cold.scene.objects["obj_1"].features[top].params["centre"][2] == pytest.approx(35.0)


def _side_of(faces, sign: float) -> str:
    """Die Seitenfläche, deren Normale in ``sign``-Richtung von X zeigt."""
    return next(
        name
        for name, feature in faces.items()
        if feature.kind == "face" and feature.params["normal"][0] * sign > 0.5
    )


def _blind_bore_into_the_right_side() -> OperationDraft:
    """Eine Sackbohrung Ø 6, 10 mm tief, mitten in die rechte Seite des 40er Quaders.

    Ein Umbau des exakten Körpers **ohne** Beleg: ``drill_brep_hole`` stellt keine
    Übergänge aus, und die native Erkennung nummeriert danach neu (gemessen: die
    Vorderseite hieß danach ``face_2``, die Deckfläche kam unter einem frischen Namen).
    Geändert ist nur die rechte Seite — sie bekommt die Öffnung, ihr Inhalt fällt von
    600 auf 571,73 mm²; Deck, Boden, Vorder-, Rück- und linke Seite sind bitgleich.
    """
    return OperationDraft(
        op="drill_brep_hole",
        inputs=("obj_1",),
        params={
            "diameter": 6.0,
            "x": 20.0,
            "y": 0.0,
            "z": 10.0,
            "nx": 1.0,
            "ny": 0.0,
            "nz": 0.0,
            "depth": 10.0,
            "compensate": False,
        },
    )


def test_an_untouched_face_keeps_its_name_through_a_rebuild_without_a_question(
    profile: Profile,
) -> None:
    """Eine Fläche, die der Umbau nicht berührt hat, ist dieselbe — gefragt wird nicht.

    Die native Erkennung nummeriert nach jedem Umbau neu; eine unberührte Fläche kommt
    deshalb oft unter anderem Namen zurück, und eine Zuordnung auf einen anderen Namen
    galt nicht als Beleg (P1.4c.2). Nachgestellt: exakter Quader, Passung auf Deck und
    Boden, eine Sackbohrung in die rechte Seite — Solidon fragte nach der Deckfläche,
    die niemand angefasst hatte (Gegenprobe ohne ``_unchanged_continuations``: eine
    Frage). Gemessen (``probe_native_identity.py``, ``probe_bez2_drill.py``): Mitte,
    Normale und Inhalt solcher Flächen sind nach dem Umbau bitgleich. Dieselbe Geometrie
    bis auf Rechenrauschen ist ein Beleg — strenger als die Zuordnung, die §21.2 für
    „ID bleibt“ genügt.

    Bis zum 23.09.2026 stand hier *Fläche versetzen* an der rechten Seite. Seit die
    Operation ihre Übergänge selbst belegt, fragt sie ohnehin nicht, und die Deckfläche
    wächst dabei auf 41 mm — sie ist dann nicht unberührt, und der Test prüfte etwas,
    das nicht mehr stimmte.
    """
    project, history, sources, top, bottom = _box_project(profile)
    before = evaluate(project.document, profile, sources=sources)
    faces = before.scene.objects["obj_1"].features
    project.document.fits.append(
        Fit(name="deckel", a=FeatureRef("obj_1", top), b=FeatureRef("obj_1", bottom), kind="flush")
    )
    history.apply("Sackbohrung", [_blind_bore_into_the_right_side()])

    result = evaluate(
        project.document,
        profile,
        sources=sources,
        ask=lambda *_: pytest.fail("eine unberührte Fläche wird nicht erfragt"),
    )

    assert result.complete and not result.blocked_references, [
        (finding.code, str(finding.message)) for finding in result.scene.report.findings
    ]
    body = result.scene.objects["obj_1"]
    for name in (top, bottom):
        assert body.features[name].params["centre"] == pytest.approx(
            faces[name].params["centre"], abs=1e-9
        )
        assert body.features[name].params["normal"] == pytest.approx(
            faces[name].params["normal"], abs=1e-9
        )
        assert body.features[name].params["area"] == pytest.approx(faces[name].params["area"])
    assert body.mesh.volume == pytest.approx(24000.0 - math.pi * 9.0 * 10.0, rel=1e-6)
    assert project.document.fits[0].a == FeatureRef("obj_1", top), "der Bezug bleibt, wie er war"


def test_the_found_successor_of_a_changed_face_is_offered_and_taken(profile: Profile) -> None:
    """Die angebohrte Fläche selbst trägt die Passung: gefragt wird, und die Antwort gilt.

    Exakter Quader, bündige Passung zwischen rechter und linker Seite, dann eine
    Sackbohrung in die rechte. Die Zuordnung findet die angebohrte Fläche eindeutig unter
    neuem Namen; sie ist nicht unverändert (ihr Inhalt fällt um die Öffnung), und die
    Bohrung stellt keinen Übergang aus — also wird gefragt (P1.4c.3). Bis zum 23.09.2026
    stand genau dieser gefundene Nachfolger nicht unter den Antworten — er galt als
    vergeben —, und jede Antwort endete in „Die Zuordnung ist nicht mehr gültig": Der alte
    Name stand noch in der Zuordnung, die er neu bekommen sollte. Eine Sackgasse im
    einfachsten Weg am exakten Körper (Gegenprobe mit dem Stand ``9307a844``).
    """
    project, history, sources, _top, _bottom = _box_project(profile)
    before = evaluate(project.document, profile, sources=sources)
    faces = before.scene.objects["obj_1"].features
    right, left = _side_of(faces, 1.0), _side_of(faces, -1.0)
    project.document.fits.append(
        Fit(name="seiten", a=FeatureRef("obj_1", right), b=FeatureRef("obj_1", left), kind="flush")
    )
    history.apply("Sackbohrung", [_blind_bore_into_the_right_side()])
    asked: list[list[str]] = []
    shown: dict[str, object] = {}

    def context(preview, candidates) -> None:
        if preview is not None:
            shown["scene"] = preview.scene

    def choose(question: str, choices: list[str]) -> str:
        asked.append(list(choices))
        scene = shown["scene"]
        for candidate in choices:
            feature = scene.objects["obj_1"].features.get(candidate)  # type: ignore[attr-defined]
            if (
                feature is not None
                and abs(float(feature.params["centre"][0]) - 20.0) < 1e-6
                and float(feature.params["area"]) > 500.0
            ):
                return candidate
        pytest.fail(f"die angebohrte Seite steht nicht unter den Antworten: {choices}")

    result = evaluate(
        project.document, profile, sources=sources, ask=choose, question_context=context
    )

    assert result.complete and not result.blocked_references, [
        (finding.code, str(finding.message)) for finding in result.scene.report.findings
    ]
    assert len(asked) == 1, "nur die angebohrte Seite wird erfragt, die linke ist unberührt"
    scene = shown["scene"]
    first = scene.objects["obj_1"].features[asked[0][0]]  # type: ignore[attr-defined]
    assert float(first.params["centre"][0]) == pytest.approx(20.0), (
        "der gefundene Nachfolger steht als erste Antwort da"
    )
    body = result.scene.objects["obj_1"]
    assert float(body.features[right].params["centre"][0]) == pytest.approx(20.0)
    assert float(body.features[right].params["area"]) == pytest.approx(600.0 - math.pi * 9.0)
    assert body.features[left].params["centre"] == pytest.approx(
        faces[left].params["centre"], abs=1e-9
    )


def test_another_producer_version_asks_again(profile: Profile) -> None:
    """Der Scope ist die Fassung des Erzeugers: ein anderer Versatz, eine neue Frage."""
    project, history, sources, _top, _bottom = _pushed_project(profile)
    push_id = project.document.ops[-1].id
    chooser = _Chooser(35.0)
    first = evaluate(
        project.document, profile, sources=sources, ask=chooser, question_context=chooser.context
    )
    assert first.complete and history.record_matches(first.matches)

    history.change_params(push_id, {**_UNPROVEN_PUSH, "distance": 16.0})
    later = _Chooser(36.0)
    second = evaluate(
        project.document, profile, sources=sources, ask=later, question_context=later.context
    )

    assert second.complete and len(later.asked) == 1
    stored = next(iter(second.matches[push_id].values()))
    assert stored["scope"] != next(iter(first.matches[push_id].values()))["scope"]


def test_not_carried_keeps_the_reference_blocked(profile: Profile) -> None:
    """„Nicht weiterführen" ist ehrlich: Der Bezug bleibt gesperrt, die Kette steht."""
    project, _history, sources, top, _bottom = _pushed_project(profile)
    chooser = _Chooser(35.0, decline=True)

    result = evaluate(
        project.document, profile, sources=sources, ask=chooser, question_context=chooser.context
    )

    assert result.stopped_at == project.document.ops[-1].id
    assert result.blocked_references == (FeatureRef("obj_1", top),)
    assert not result.matches, "eine Absage wird am exakten Körper nicht festgeschrieben"
    stop = [f for f in result.scene.report.findings if f.op_id == result.stopped_at]
    assert [f.code for f in stop] == ["op.push_face.NativeReferenceLost"]
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(24000.0, rel=1e-9)


def test_without_anyone_to_ask_the_question_stays_open_with_its_choices(
    profile: Profile,
) -> None:
    """Kommandozeile und Agent: kein Raten, die Kandidaten stehen als Vorschläge da."""
    project, _history, sources, top, _bottom = _pushed_project(profile)

    result = evaluate(project.document, profile, sources=sources)

    assert result.stopped_at == project.document.ops[-1].id
    assert FeatureRef("obj_1", top) in result.blocked_references
    stop = [f for f in result.scene.report.findings if f.op_id == result.stopped_at]
    assert [f.code for f in stop] == ["op.push_face.NativeReferenceLost"]
    choices = [action.id for action in stop[0].suggestions if action.id.startswith("choose:")]
    assert choices, stop[0].suggestions
    assert "Nicht weiterführen" in choices[-1]


def test_a_mesh_answer_never_serves_the_native_reselection(profile: Profile) -> None:
    """Dieselbe Wahl unter ``group:`` statt ``native-group:`` ist keine native Zustimmung."""
    from app.core.perceive.match_records import GROUP_DOMAIN, group_key

    project, history, sources, top, _bottom = _pushed_project(profile)
    push_id = project.document.ops[-1].id
    chooser = _Chooser(35.0)
    result = evaluate(
        project.document, profile, sources=sources, ask=chooser, question_context=chooser.context
    )
    record = dict(next(iter(result.matches[push_id].values())))
    del record["scope"]
    mesh_key = group_key("obj_1", record["old_ids"], domain=GROUP_DOMAIN)
    assert history.record_matches({push_id: {mesh_key: record}})

    again = evaluate(project.document, profile, sources=sources)

    assert again.stopped_at == push_id
    assert FeatureRef("obj_1", top) in again.blocked_references


def test_a_native_record_needs_its_scope_and_a_mesh_record_must_not_carry_one() -> None:
    from app.core.perceive.match_records import (
        GROUP_DOMAIN,
        NATIVE_DOMAIN,
        domain_of,
        group_key,
        validate_group,
    )

    fingerprint = {
        "kind": "face",
        "relative": [0.0, 0.0, 0.5],
        "axis": [0.0, 0.0, 1.0],
        "diameter": 1200.0,
        "directional": True,
    }
    record = {
        "object_id": "obj_1",
        "old_ids": ["face_3"],
        "candidates": [{"fingerprint": fingerprint, "claims": ["face_3"]}],
        "decisions": {"face_3": {"candidate": 0}},
    }
    native_key = group_key("obj_1", ["face_3"], domain=NATIVE_DOMAIN)
    mesh_key = group_key("obj_1", ["face_3"], domain=GROUP_DOMAIN)
    assert domain_of(native_key) == NATIVE_DOMAIN and domain_of(mesh_key) == GROUP_DOMAIN
    assert domain_of("fremd:[]") is None
    validate_group(mesh_key, record, ("obj_1",))
    validate_group(native_key, {**record, "scope": "erzeuger:0"}, ("obj_1",))
    with pytest.raises(ValueError, match="group"):
        validate_group(native_key, record, ("obj_1",))
    with pytest.raises(ValueError, match="group"):
        validate_group(mesh_key, {**record, "scope": "erzeuger:0"}, ("obj_1",))
    with pytest.raises(ValueError, match="scope"):
        validate_group(native_key, {**record, "scope": ""}, ("obj_1",))
    with pytest.raises(ValueError, match="key"):
        validate_group(mesh_key, {**record, "old_ids": ["face_4"]}, ("obj_1",))
    with pytest.raises(ValueError, match="key"):
        validate_group("fremd:[]", record, ("obj_1",))
    with pytest.raises(ValueError, match="domain"):
        group_key("obj_1", ["face_3"], domain="fremd")


def test_a_saved_native_choice_holds_only_for_its_scope() -> None:
    from app.core.perceive.match_decisions import group_fingerprint, resolve_group

    _solid, found = _exact_box()
    name = next(iter(found))
    claims = {name: (name,)}
    centre, diagonal = _solid.bounds.centre, _solid.bounds.diagonal
    record = group_fingerprint("body", claims, {name: name}, found, centre, diagonal, scope="a:0")

    assert record["scope"] == "a:0"
    assert resolve_group(record, "body", claims, found, centre, diagonal, scope="a:0") == {
        name: name
    }
    assert resolve_group(record, "body", claims, found, centre, diagonal, scope="b:0") is None
    assert resolve_group(record, "body", claims, found, centre, diagonal) is None, (
        "ein nativer Datensatz ist keine Netzantwort"
    )


def test_the_v28_example_carries_a_native_reselection_and_v27_migrates_unchanged() -> None:
    from app.core.perceive.match_records import NATIVE_DOMAIN, domain_of
    from app.core.scene import FORMAT_VERSION
    from app.core.scene.project import load, project_data

    folder = Path(__file__).parent / "data" / "projects"
    project = load(folder / "example_v28.p3d")
    assert project.document.format_version == FORMAT_VERSION
    records = project.document.ops[0].matches
    native = [record for key, record in records.items() if domain_of(key) == NATIVE_DOMAIN]
    assert len(native) == 1 and native[0]["scope"] == "beispiel-erzeuger:0"

    raw = project_data(folder / "example_v27.p3d")
    older = load(folder / "example_v27.p3d")
    assert older.document.format_version == FORMAT_VERSION
    assert older.document.ops[0].matches == raw["ops"][0]["matches"]


def test_the_session_hands_the_blocked_references_to_the_check() -> None:
    """Der einzige Anschluss, an dem der Sperrzustand eingelöst wird — dort wird er geprüft.

    Gelesen über den Syntaxbaum, nicht als Text: Bis zum 21.09.2026 nahm der
    Test den ersten ``orphans.check(`` bis zur ersten Zeile, die mit ``)``
    endete — ein zweiter Aufruf ohne ``blocked`` wäre ungesehen geblieben,
    und ein Zeilenumbruch an der falschen Stelle hätte den ersten zerteilt.
    Jetzt zählt jeder Aufruf, und jeder muss die gesperrten Verweise der
    Auswertung weiterreichen.
    """
    import ast

    source = (Path(__file__).parent.parent / "app" / "ui" / "session.py").read_text(
        encoding="utf-8"
    )
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "check"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "orphans"
    ]
    assert calls, "kein orphans.check in session.py — dann prüft dieser Test nichts"
    for call in calls:
        blocked = [keyword for keyword in call.keywords if keyword.arg == "blocked"]
        assert len(blocked) == 1, f"Zeile {call.lineno}: orphans.check ohne blocked="
        assert ast.unparse(blocked[0].value) == "result.blocked_references", (
            f"Zeile {call.lineno}: {ast.unparse(blocked[0].value)}"
        )


@pytest.mark.parametrize("shape", ["drilled_box", "hollow_cylinder"])
@pytest.mark.parametrize("warm", [False, True])
def test_native_face_names_do_not_depend_on_a_later_consumer(
    profile: Profile, shape: str, warm: bool, tmp_path: Path
) -> None:
    """Eine später angeklickte Fläche behält im Lauf dieselbe Lage wie in der Ansicht (RM-388)."""
    exact_kernel()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    if shape == "hollow_cylinder":
        history.apply(
            "Zylinder",
            [OperationDraft(op="create_brep_cylinder", params={"diameter": 45.0, "height": 17.0})],
        )
        # Ohne Entlüftung, sonst ginge *Aushöhlen* den Netzweg, und der Fall
        # prüfte keinen exakten Zylinder (``exactly_hollowable``).
        history.apply(
            "Aushöhlen",
            [
                OperationDraft(
                    op="hollow_object",
                    inputs=("obj_1",),
                    params={"wall": 2.0, "open_top": True, "vents": 0},
                )
            ],
        )
    else:
        history.apply(
            "Quader",
            [
                OperationDraft(
                    op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}
                )
            ],
        )
        history.apply(
            "Bohrung",
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=("obj_1",),
                    params={"diameter": 6.0, "depth": 10.0, "x": 0.0, "y": 0.0, "z": 10.0},
                )
            ],
        )
    sources = ProjectSources(project)
    cache = ResultCache()
    visible = evaluate(project.document, profile, sources=sources, cache=cache)
    assert visible.complete, visible.scene.report.findings
    body = visible.scene.objects["obj_1"]
    assert body.kind == "brep", "der Fall gilt dem exakten Körper"
    top = next(
        feature
        for feature in body.features.values()
        if feature.kind == "face"
        and feature.params["normal"][2] > 0.9
        and feature.params["centre"][2] > body.mesh.bounds.maximum[2] - 1e-6
    )
    # Ein echter Verbraucher: Vor dem Anhängen wurde der Randring oben ausgewählt.
    history.apply(
        "Fläche versetzen",
        [
            OperationDraft(
                op="push_face", inputs=("obj_1",), params={"face": top.id, "distance": 0.5}
            )
        ],
    )
    result = evaluate(
        project.document, profile, sources=sources, cache=cache if warm else ResultCache()
    )
    assert result.complete, result.scene.report.findings
    after = result.scene.objects["obj_1"].features[top.id]
    assert after.params["normal"] == pytest.approx(top.params["normal"])
    assert after.params["centre"][2] == pytest.approx(top.params["centre"][2] + 0.5)
    assert history.undo() is not None
    undone = evaluate(project.document, profile, sources=sources, cache=cache)
    assert undone.complete
    assert undone.scene.objects["obj_1"].features[top.id].params["centre"] == pytest.approx(
        top.params["centre"]
    )
    assert history.redo() is not None
    redone = evaluate(project.document, profile, sources=sources, cache=cache)
    assert redone.complete
    assert redone.scene.objects["obj_1"].features[top.id].params["centre"] == pytest.approx(
        after.params["centre"]
    )
    from app.core.scene.project import load, save

    reopened = load(save(project, tmp_path / "flaechenbezug.p3d"))
    cold = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert cold.complete
    assert cold.scene.objects["obj_1"].features[top.id].params["centre"] == pytest.approx(
        after.params["centre"]
    )


def shown_face_on_top(result: object, height: float) -> Feature:
    """Die Fläche, die die Ansicht nach oben schauend auf ``height`` zeigt — die,
    die der Kunde anklickt; genau eine, sonst ist der Fall falsch gebaut."""
    entry = result.scene.objects["obj_1"]  # type: ignore[attr-defined]
    faces = [
        feature
        for feature in entry.features.values()
        if feature.kind == "face"
        and feature.params["normal"][2] > 0.99
        and abs(feature.params["centre"][2] - height) < 1e-3
    ]
    assert len(faces) == 1, [feature.id for feature in faces]
    return faces[0]


@pytest.mark.parametrize("box", ["create_brep_box", "create_box"])
def test_a_keyhole_chosen_on_the_top_face_after_a_bore_sits_in_the_top_face(
    profile: Profile, box: str, tmp_path: Path
) -> None:
    """Der Originalweg F1 aus RM-388, über die Funktionen, die die Oberfläche ruft.

    Quader 40 x 30 x 10, Deckfläche angeklickt, *Bohrung setzen* Ø 6; danach die
    Deckfläche erneut angeklickt und *Baustein einsetzen* → Schlüsselloch. Den
    Dialog belegt ``placement.values_for`` mit der angezeigten Fläche, übernommen
    wird als Schritt wie über ``Session.apply``. Am exakten Quader tauschten nach
    der Bohrung drei Flächen ihre Namen, und das Schlüsselloch saß in der
    Vorderseite (Achse -Y); vor der Übernahme der Codex-Linien hielt die Kette
    schon an der Bohrung an (``NativeReferenceLost``).
    """
    if box == "create_brep_box":
        exact_kernel()
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.scene.placement import values_for
    from app.core.scene.project import load, save

    load_operations()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op=box, params={"width": 40.0, "depth": 30.0, "height": 10.0})],
    )
    shown = evaluate(project.document, profile, sources=ProjectSources(project))
    drill = values_for(REGISTRY.get("drill_hole"), shown_face_on_top(shown, 10.0), "obj_1")
    history.apply(
        "Bohrung",
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params={**drill, "diameter": 6.0})],
    )
    drilled = evaluate(project.document, profile, sources=ProjectSources(project))
    assert drilled.complete, drilled.scene.report.findings
    chosen = values_for(REGISTRY.get("insert_keyhole"), shown_face_on_top(drilled, 10.0), "obj_1")
    history.apply(
        "Schlüsselloch",
        [OperationDraft(op="insert_keyhole", inputs=("obj_1",), params=chosen)],
    )

    def keyhole_of(document: Document) -> list[Feature]:
        result = evaluate(document, profile, sources=ProjectSources(project))
        assert result.complete, result.scene.report.findings
        return [
            feature
            for name, feature in result.scene.objects["obj_1"].features.items()
            if name.startswith("keyhole")
        ]

    def in_the_top_face(parts: list[Feature]) -> None:
        assert parts, "das Schlüsselloch fehlt"
        for feature in parts:
            assert feature.params["axis"][2] == pytest.approx(1.0, abs=1e-3), feature.params
            centre = feature.params["centre"]
            assert abs(centre[0]) < 20.0 and abs(centre[1]) < 15.0, centre

    in_the_top_face(keyhole_of(project.document))
    assert history.undo() is not None
    assert keyhole_of(project.document) == []
    assert history.redo() is not None
    in_the_top_face(keyhole_of(project.document))
    reopened = load(save(project, tmp_path / "schluesselloch.p3d"))
    in_the_top_face(keyhole_of(reopened.document))


@pytest.mark.parametrize("cylinder", ["create_brep_cylinder", "create_cylinder"])
def test_a_screw_lid_chosen_at_the_rim_of_a_hollowed_cylinder_is_made(
    profile: Profile, cylinder: str, tmp_path: Path
) -> None:
    """Der Originalweg F3 aus RM-388, über die Funktionen, die die Oberfläche ruft.

    Zylinder Ø 45 x 17, *Aushöhlen* mit *Oben öffnen* (Wand 2, ohne Entlüftung,
    sonst rechnete auch der exakte Zylinder am Netz), den Randring angeklickt,
    *Drehdeckel erzeugen*. Die Sperre am Menüeintrag fragt ``lid.reason_against``
    an den angezeigten Merkmalen, der Dialog belegt sich über
    ``placement.values_for``, übernommen wird über ``lid_flow.apply_lid`` wie in
    ``Session.create_lid``. Am exakten Zylinder hieß der Randring in der Ansicht
    ``face_2``, im Lauf war ``face_2`` der Boden: „Der Körper ist auf dieser Höhe
    massiv“, kein Deckel.
    """
    exact = cylinder == "create_brep_cylinder"
    if exact:
        exact_kernel()
    from app.core.bootstrap import load_operations
    from app.core.geom.lid import reason_against
    from app.core.lid_flow import apply_lid
    from app.core.registry import REGISTRY
    from app.core.scene.placement import values_for
    from app.core.scene.project import load, save

    load_operations()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Zylinder", [OperationDraft(op=cylinder, params={"diameter": 45.0, "height": 17.0})]
    )
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=("obj_1",),
                params={"wall": 2.0, "open_top": True, "vents": 0},
            )
        ],
    )
    shown = evaluate(project.document, profile, sources=ProjectSources(project))
    assert shown.complete, shown.scene.report.findings
    entry = shown.scene.objects["obj_1"]
    assert entry.kind == ("brep" if exact else "mesh")
    rim = shown_face_on_top(shown, 17.0)
    assert reason_against(entry, rim.id) is None, "Einsetzen ist frei"
    applied = apply_lid(
        project.document,
        "obj_1",
        dict(values_for(REGISTRY.get("screw_lid"), rim, "obj_1")),
        op="screw_lid",
    )
    assert applied.fit is not None
    made = {"obj_1", *applied.object_ids}
    assert len(made) == 2

    def bodies(document: Document) -> set[str]:
        result = evaluate(document, profile, sources=ProjectSources(project))
        assert result.complete, result.scene.report.findings
        return set(result.scene.objects)

    assert bodies(project.document) == made
    # Der Ablauf hat seinen eigenen Verlauf geführt; Rückgängig und Wiederholen
    # gehen über einen, der den Stapel des Dokuments liest, wie in der Sitzung.
    afterwards = History(project.document)
    assert afterwards.undo() is not None
    assert bodies(project.document) == {"obj_1"}
    assert afterwards.redo() is not None
    assert bodies(project.document) == made
    reopened = load(save(project, tmp_path / "drehdeckel.p3d"))
    assert bodies(reopened.document) == made
    assert [fit.name for fit in reopened.document.fits] == [applied.fit.name]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("side", [-1, 0, 1])
def test_cutting_a_u_keeps_equal_top_pieces_ambiguous(
    profile: Profile, reverse: bool, side: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Zwei gleich große Reste brauchen auch am registrierten Abschneiden eine Wahl (RM-450)."""
    exact_kernel()
    from app.core.bootstrap import load_operations
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom import prepare_ops
    from app.core.geom.transform import translation
    from app.core.registry import REGISTRY, OperationSpec, Registry
    from app.core.types import BaseParams

    body = edit.unified(
        edit.boolean(
            "difference",
            [
                edit.box(40.0, 30.0, 10.0),
                edit.transformed(edit.box(20.0, 30.0, 20.0), translation((0.0, 5.0, -5.0))),
            ],
        )
    )
    features = features_of(body)
    top = next(f for f in features.values() if f.kind == "face" and f.params["normal"][2] > 0.9)
    source = SceneObject(id="obj_1", name="U-Körper", kind="brep", mesh=body, features=features)
    original = prepare_ops._cut_faces_continued

    def ordered(kept, found, continued, mesh):
        return original(
            kept, dict(reversed(tuple(found.items()))) if reverse else found, continued, mesh
        )

    monkeypatch.setattr(prepare_ops, "_cut_faces_continued", ordered)
    load_operations()
    registry = Registry()
    for spec in REGISTRY.all():
        registry.register(spec)
    registry.register(
        OperationSpec(
            name="probe_u",
            title="U-Körper",
            category="primitive",
            params=BaseParams,
            fn=lambda ctx: OpResult(outputs=[source]),
            consumes=0,
            produces=1,
        )
    )
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document, registry=registry)
    history.apply("U-Körper", [OperationDraft(op="probe_u")])
    history.apply(
        "Abschneiden",
        [
            OperationDraft(
                op="cut_away",
                inputs=("obj_1",),
                params={"axis": "y", "position": 0.0, "keep": "above"},
            )
        ],
    )
    history.apply(
        "Alte Deckfläche versetzen",
        [
            OperationDraft(
                op="push_face", inputs=("obj_1",), params={"face": top.id, "distance": 0.5}
            )
        ],
    )
    calls = []
    preview = _Chooser(10.0)
    cache = ResultCache()

    def decline(question, choices):
        calls.append((question, choices))
        if side:
            for object_id, candidate in preview.candidates:
                feature = preview.preview.scene.objects[object_id].features[candidate]
                if feature.params["normal"][2] > 0.9 and feature.params["centre"][0] * side > 0.0:
                    assert candidate in choices
                    return candidate
            pytest.fail("die gewählte obere Restfläche fehlt in der Fragevorschau")
        return "Nicht weiterführen"

    result = evaluate(
        project.document,
        profile,
        registry=registry,
        sources=ProjectSources(project),
        ask=decline,
        cache=cache,
        question_context=preview.context,
    )
    assert calls and top.id in calls[0][0]
    assert len([name for name in calls[0][1] if name.startswith("face_")]) >= 2
    if not side:
        assert not result.complete
        assert FeatureRef("obj_1", top.id) in result.blocked_references
        return
    assert result.complete, result.scene.report.findings
    chosen = result.scene.objects["obj_1"].features[top.id]
    assert chosen.params["centre"][0] * side > 0.0
    assert chosen.params["centre"][2] == pytest.approx(10.5)
    assert history.record_matches(result.matches)
    assert history.undo() is not None
    undone = evaluate(
        project.document, profile, registry=registry, sources=ProjectSources(project), cache=cache
    )
    assert undone.complete
    assert undone.scene.objects["obj_1"].mesh.bounds.maximum[2] == pytest.approx(10.0)
    assert history.redo() is not None
    for active_cache in (cache, ResultCache()):
        again = evaluate(
            project.document,
            profile,
            registry=registry,
            sources=ProjectSources(project),
            cache=active_cache,
            ask=lambda *_: pytest.fail("die gespeicherte Wahl trägt den Bezug"),
        )
        assert again.complete
        assert again.scene.objects["obj_1"].features[top.id].params["centre"] == pytest.approx(
            chosen.params["centre"]
        )
    from app.core.scene.project import load, save

    reopened = load(save(project, tmp_path / "gewaehlter-rest.p3d"))
    cold = evaluate(
        reopened.document,
        profile,
        registry=registry,
        sources=ProjectSources(reopened),
        ask=lambda *_: pytest.fail("die Wahl bleibt nach dem Öffnen gültig"),
    )
    assert cold.complete
    assert cold.scene.objects["obj_1"].features[top.id].params["centre"] == pytest.approx(
        chosen.params["centre"]
    )


def test_cut_face_continuation_excludes_a_foreign_coplanar_face() -> None:
    """Eine größere fremde Fläche in derselben Ebene stammt nicht vom alten Quader."""
    exact_kernel()
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.prepare_ops import _cut_faces_continued

    body = edit.box(20.0, 20.0, 10.0)
    top = next(
        f for f in features_of(body).values() if f.kind == "face" and f.params["normal"][2] > 0.9
    )
    own = dataclasses.replace(
        top, id="face_100", params={**top.params, "area": 100.0, "centre": (0.0, 0.0, 10.0)}
    )
    foreign = dataclasses.replace(
        top, id="face_101", params={**top.params, "area": 1000.0, "centre": (100.0, 0.0, 10.0)}
    )
    for candidates in ({own.id: own, foreign.id: foreign}, {foreign.id: foreign, own.id: own}):
        found, continued = _cut_faces_continued({top.id: top}, candidates, (), body)
        assert found[top.id].params["area"] == pytest.approx(100.0)
        assert foreign.id in found
        assert continued == ((top.id, top.id),)
