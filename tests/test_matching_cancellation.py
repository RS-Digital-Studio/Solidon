"""Das vorhandene Abbruchsignal erreicht die Zuordnung aller Produktionswege."""

from __future__ import annotations

import io
from dataclasses import replace
from importlib import import_module
from types import ModuleType

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.brep import edit
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid
from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive import local, matching
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import CancelSignal
from app.core.sketch.planes import frame_of
from app.core.types import OpContext, Operation, Profile, Scene, SceneObject
from tests.helpers import exact_kernel


def _source(kind: str, *, entrance: bool = False) -> SceneObject:
    """Eine wirkliche Bohrung, wahlweise mit dem eindeutigen Einlauf derselben Achse."""
    from tests.helpers import exact_kernel

    exact_kernel()
    stock = edit.box(40.0, 30.0, 12.0)
    if entrance:
        exact = edit.bore_profile(
            stock,
            [(0.0, 2.0), (3.0, 2.0), (3.0, 10.0), (5.0, 12.0), (0.0, 12.0), (0.0, 2.0)],
            frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
        )
    else:
        exact = edit.bore(stock, position=(0.0, 0.0, 12.0), axis="z", diameter=6.0)
    body = exact if kind == "brep" else as_mesh_data(exact)
    features = features_of(exact) if kind == "brep" else detect(body)
    assert any(feature.kind == "hole" for feature in features.values())
    return SceneObject(id="obj_1", name="Bohrplatte", kind=kind, mesh=body, features=features)


def _geometry_bytes(source: SceneObject) -> bytes:
    """Die Originalgeometrie vor der abgebrochenen Folgeoperation festhalten."""
    if isinstance(source.mesh, Solid):
        exact_kernel()
        from OCP.BRepTools import BRepTools

        stream = io.BytesIO()
        BRepTools.Write_s(source.mesh.shape, stream)
        return stream.getvalue()
    return source.mesh.raw.vertices.tobytes() + source.mesh.raw.faces.tobytes()


def _cancel_at_match(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    signal: CancelSignal,
    *,
    at: int = 1,
) -> list:
    """Erst am tatsächlichen Zuordnungseintritt abbrechen; der echte Matcher läuft weiter."""
    original = module.match
    calls = []

    def stopped(*args, check_cancelled=None, **kwargs):
        assert getattr(check_cancelled, "__self__", None) is signal
        calls.append(check_cancelled)
        if len(calls) == at:
            signal.cancel()
        return original(*args, check_cancelled=check_cancelled, **kwargs)

    monkeypatch.setattr(module, "match", stopped)
    # Die erklärten Merkmale suchen ihren Partner über ``matching.declared_partners``
    # (Durchsicht 0.5.1, derselbe Weg für Netz und exakten Baustein) — die
    # Zuordnung beginnt dort, im Modul der Zuordnung.
    matching = import_module("app.core.perceive.matching")
    if module is not matching:
        monkeypatch.setattr(matching, "match", stopped)
    return calls


@pytest.mark.parametrize("route", ["native", "measured", "declared"])
def test_evaluation_matching_keeps_the_original_cancellation(
    route: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native, neu gemessene und deklarierte Merkmale teilen den Auswertungsabbruch."""
    module = import_module("app.core.scene.evaluate")
    source = _source("brep" if route == "native" else "mesh")
    before = _geometry_bytes(source)
    previous = dict(source.features)
    entry = source
    if route == "measured":
        entry = replace(source, features={})
    elif route == "declared":
        entry = replace(
            source,
            features={
                name: replace(feature, provenance="generated")
                for name, feature in source.features.items()
            },
        )
        previous = {}
    signal = CancelSignal()
    calls = _cancel_at_match(monkeypatch, module, signal)

    with pytest.raises(OperationCancelled):
        module._with_features(
            entry,
            previous,
            Operation(id=2, op="resize_hole"),
            lambda question, choices: choices[0],
            [],
            touches_features=True,
            cancelled=signal,
        )

    assert len(calls) == 1
    assert _geometry_bytes(source) == before


def test_a_saved_matching_answer_keeps_the_evaluation_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine echte gespeicherte Wahl bleibt beim erneuten Vergleich mit zwei Löchern abbrechbar."""
    module = import_module("app.core.scene.evaluate")

    def bored(positions: tuple[float, ...]) -> MeshData:
        """Ein ursprüngliches Loch und zwei tatsächliche gleichwertige Nachfolger herstellen."""
        tools = []
        for x in positions:
            tool = trimesh.creation.cylinder(radius=1.0, height=20.0, sections=32)
            tool.apply_translation((x, 0.0, 0.0))
            tools.append(tool)
        return MeshData.of(
            trimesh.boolean.difference([trimesh.creation.box(extents=(80.0, 40.0, 8.0)), *tools])
        )

    previous = next(feature for feature in detect(bored((0.0,))).values() if feature.kind == "hole")
    current = bored((-3.0, 3.0))
    source = SceneObject(id="obj_1", name="Zwei Bohrungen", mesh=current)
    before = _geometry_bytes(source)
    asked = []
    recorded = {}

    def ask(question, choices):
        asked.append(question)
        return choices[0]

    operation = Operation(id=2, op="thicken")
    module._with_features(
        source,
        {previous.id: previous},
        operation,
        ask,
        [],
        recorded=recorded,
        referenced={previous.id},
    )
    assert len(asked) == 1
    from app.core.perceive import matching
    from app.core.perceive.match_records import group_key

    assert group_key(source.id, (previous.id,)) in recorded
    answered = replace(operation, matches=recorded)
    signal = CancelSignal()
    calls = []
    original = matching.resolve

    def stopped(*args, check_cancelled=None, **kwargs):
        assert getattr(check_cancelled, "__self__", None) is signal
        calls.append(check_cancelled)
        signal.cancel()
        return original(*args, check_cancelled=check_cancelled, **kwargs)

    monkeypatch.setattr(matching, "resolve", stopped)
    with pytest.raises(OperationCancelled):
        module._with_features(
            source,
            {previous.id: previous},
            answered,
            ask,
            [],
            referenced={previous.id},
            cancelled=signal,
        )

    assert len(calls) == 1
    assert len(asked) == 1
    assert _geometry_bytes(source) == before


@pytest.mark.parametrize(
    ("kind", "operation", "entrance", "at"),
    [
        ("mesh", "resize_hole", False, 1),
        ("brep", "resize_hole", False, 1),
        ("brep", "resize_hole", False, 2),
        ("mesh", "slot_hole", False, 1),
        ("brep", "slot_hole", False, 1),
        ("mesh", "resize_hole", True, 1),
        ("brep", "resize_hole", True, 1),
    ],
)
def test_registered_bore_changes_keep_cancellation_through_matching(
    kind: str,
    operation: str,
    entrance: bool,
    at: int,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Beide Kerne brechen auch nach fertigem Schnitt vor der Merkmalsübernahme ab."""
    load_operations()
    source = _source(kind, entrance=entrance)
    before = _geometry_bytes(source)
    original_features = dict(source.features)
    bore = next(feature.id for feature in source.features.values() if feature.kind == "hole")
    spec = REGISTRY.get(operation)
    values = (
        {"slot_length": 14.0}
        if operation == "slot_hole"
        else {"diameter": 4.0, "entrance_mode": "follow" if entrance else "keep"}
    )
    signal = CancelSignal()
    calls = _cancel_at_match(monkeypatch, matching, signal, at=at)

    with pytest.raises(OperationCancelled):
        spec.fn(
            OpContext(
                scene=Scene(objects={source.id: source}),
                inputs=[source],
                params=spec.params(at_feature=bore, **values),
                profile=profile,
                quality="fine",
                seed=7,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=signal,
            )
        )

    assert len(calls) == at
    assert source.features == original_features
    assert _geometry_bytes(source) == before


def test_local_known_feature_passes_cancellation_to_its_boundary_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der vollständige Sacklochrest neben einer angeschnittenen Außenwand bleibt abbrechbar."""
    mesh = MeshData.of(
        trimesh.creation.revolve(
            [[0.0, 0.0], [6.0, 0.0], [6.0, 20.0], [3.0, 20.0], [3.0, 15.0], [0.0, 15.0]],
            sections=64,
        )
    )
    assert mesh.is_watertight
    found = detect(mesh)
    bore = next(feature for feature in found.values() if feature.kind == "hole")
    vertices, faces = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    signal = CancelSignal()
    calls = _cancel_at_match(monkeypatch, local, signal)

    with pytest.raises(OperationCancelled):
        local.detect_known(mesh, {bore.id: bore}, check_cancelled=signal.raise_if_cancelled)

    assert len(calls) == 1
    np.testing.assert_array_equal(mesh.raw.vertices, vertices)
    np.testing.assert_array_equal(mesh.raw.faces, faces)


def test_mesh_slot_recognition_keeps_the_same_cancellation(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Meshzwilling prüft nach dem Schnitt bereits während seiner Neuerkennung Abbruch."""
    from app.core.perceive import features

    load_operations()
    source = _source("mesh")
    bore = next(feature.id for feature in source.features.values() if feature.kind == "hole")
    before = _geometry_bytes(source)
    signal = CancelSignal()
    original = features.detect
    calls = []

    def stopped(mesh, *, check_cancelled=None, **kwargs):
        assert getattr(check_cancelled, "__self__", None) is signal
        calls.append(check_cancelled)
        signal.cancel()
        return original(mesh, check_cancelled=check_cancelled, **kwargs)

    monkeypatch.setattr(features, "detect", stopped)
    spec = REGISTRY.get("slot_hole")
    with pytest.raises(OperationCancelled):
        spec.fn(
            OpContext(
                scene=Scene(objects={source.id: source}),
                inputs=[source],
                params=spec.params(at_feature=bore, slot_length=14.0),
                profile=profile,
                quality="fine",
                seed=7,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=signal,
            )
        )

    assert len(calls) == 1
    assert _geometry_bytes(source) == before
