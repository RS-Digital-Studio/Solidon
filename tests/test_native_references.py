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
from importlib import import_module
from pathlib import Path

import pytest

from app.core.errors import InternalError, NativeReferenceLost
from app.core.perceive.matching import MatchResult
from app.core.scene import History, OperationDraft, ResultCache, evaluate, orphans
from app.core.scene.cache import CACHE_FORMAT_VERSION, CachedResult, DiskCache
from app.core.scene.project import ProjectSources, new_project
from app.core.types import (
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
from tests.conftest import FakeMesh, make_object
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
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit
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

    outcome, calls = _native_call(monkeypatch, None, needed={})

    assert calls == [], "nichts gebraucht, nichts zugeordnet, nichts zu beweisen"
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
        None,
        needed={name: ("Passung a",)},
        continuations=(FeatureContinuation(FeatureRef("body", name), name),),
    )

    assert calls == []
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


def _box_project(profile: Profile):
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
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
        [OperationDraft(op="push_face", inputs=("obj_1",), params={"face": top, "distance": 15.0})],
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
        [OperationDraft(op="push_face", inputs=("obj_1",), params={"face": top, "distance": 15.0})],
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


def test_the_session_hands_the_blocked_references_to_the_check() -> None:
    """Der einzige Anschluss, an dem der Sperrzustand eingelöst wird — dort wird er geprüft."""
    source = (Path(__file__).parent.parent / "app" / "ui" / "session.py").read_text(
        encoding="utf-8"
    )
    call = source[source.index("orphans.check(") :]
    call = call[: call.index(")\n")]
    assert "blocked=result.blocked_references" in call
