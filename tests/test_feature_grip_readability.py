"""Ruhende Lochgriffe lassen die Öffnung frei, echte Entwürfe bleiben deutlich."""

from collections.abc import Iterator
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.geom.transform import TransformSteps
from app.core.types import Feature, FeatureKind
from app.ui.render.api import PointerEvent
from app.ui.slot_handle import SlotHandle
from app.ui.viewport import Viewport
from tests.render_fakes import RecordingRenderer


def make_handle(
    renderer: RecordingRenderer, *, outlined: bool = False, length: float = 5.2
) -> SlotHandle:
    """Ein kleiner Griff mit unverändertem öffentlichem Darstellungsvertrag."""
    return SlotHandle(
        renderer,
        centre=(0.0, 0.0, 2.0),
        axis=(0.0, 0.0, 1.0),
        diameter=5.2,
        length=length,
        angle=0.0,
        knob_size=5.2,
        colour="#ff9f1c",
        release_callback=lambda length, angle: None,
        outlined=outlined,
    )


@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("outside", [False, True])
def test_idle_hover_held_and_leave_keep_the_same_pick_geometry(direct: bool, outside: bool) -> None:
    renderer = RecordingRenderer()
    handle = make_handle(renderer)
    first, second = handle._knobs
    renderer.item_picks[(20, 30)] = first
    before = [item.points.copy() for item in handle._knobs]
    assert first.opacity() == second.opacity() == pytest.approx(0.45)
    if direct:
        assert handle.take_press(PointerEvent("press", 20, 30, button="left"), 0)
    else:
        handle.handle(PointerEvent("move", 20, 30))
        assert first.opacity() == pytest.approx(1.0)
        assert handle.handle(PointerEvent("press", 20, 30, button="left"))
    assert handle.pressing and first.opacity() == pytest.approx(1.0)
    handle.handle(PointerEvent("leave", 200, 300))
    assert first.opacity() == pytest.approx(1.0), "der gehaltene Knopf bleibt deutlich"
    x, y = (200, 300) if outside else (20, 30)
    handle.handle(PointerEvent("release", x, y, button="left"))
    assert first.opacity() == pytest.approx(0.45 if outside else 1.0)
    if not outside:
        handle.handle(PointerEvent("leave", 200, 300))
    assert first.opacity() == second.opacity() == pytest.approx(0.45)
    for item, points in zip(handle._knobs, before, strict=True):
        np.testing.assert_array_equal(item.points, points)
        assert item.visible() and item.pickable


def test_waiting_outline_and_rebuilt_knobs_keep_their_roles() -> None:
    renderer = RecordingRenderer()
    handle = make_handle(renderer, outlined=True)
    assert handle._outline is not None and handle._outline.visible()
    assert handle._outline.opacity() == pytest.approx(1.0)
    assert all(item.opacity() == pytest.approx(0.45) for item in handle._knobs)
    previous = tuple(handle._knobs)
    handle.remove()
    rebuilt = make_handle(renderer)
    assert all(item in renderer.removed for item in previous)
    assert all(item.opacity() == pytest.approx(0.45) for item in rebuilt._knobs)


@pytest.fixture
def feature_view(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[Viewport]:
    load_operations()
    view = Viewport()
    view.renderer = RecordingRenderer()
    feature = Feature(
        id="hole_1",
        kind="slot",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "depth": 4.0,
            "diameter": 5.2,
            "length": 10.0,
            "heading": 0.0,
        },
    )
    view._selected_feature = feature.id
    monkeypatch.setattr(view, "_features_of_selection", lambda: {feature.id: feature})
    try:
        yield view
    finally:
        view.renderer = None
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("kind", ["hole", "slot", "pin"])
def test_only_idle_openings_reduce_their_non_pickable_fills(
    feature_view: Viewport, kind: FeatureKind
) -> None:
    view = feature_view
    feature = view._features_of_selection()["hole_1"]
    feature = replace(
        feature,
        kind=kind,
        params={
            **feature.params,
            **({"length": 10.0, "heading": 0.0} if kind == "slot" else {}),
        },
    )
    face = view._face_handle(feature)
    assert face is not None and view._shape_actor is not None
    assert not face.pickable and not view._shape_actor.pickable
    assert face.opacity() == pytest.approx(0.6 if kind == "pin" else 0.12)
    assert view._shape_actor.opacity() == pytest.approx(0.45 if kind == "pin" else 0.18)
    assert face.bounds()[0] < face.bounds()[1], "der Gizmo-Bezug behält seine Ausdehnung"


@pytest.mark.parametrize("state", ["waiting", "width", "held", "turn", "move"])
def test_existing_preview_actor_changes_with_the_actual_proposal(
    feature_view: Viewport, state: str
) -> None:
    view = feature_view
    feature = view._features_of_selection()["hole_1"]
    view._face_handle(feature)
    actor = view._shape_actor
    assert actor is not None and actor.opacity() == pytest.approx(0.18)
    view._slot_handle = make_handle(view.renderer, length=10.0)
    if state == "waiting":
        view._slot_target = feature.id
        view._slot_waiting = (5.2, 0.0)
    elif state == "width":
        view._slot_width = 5.0
    elif state == "held":
        view._slot_handle.take_press(PointerEvent("press", 20, 30, button="left"), 0)
    elif state == "turn":
        view._slot_turn_base = 0.0
    else:
        view._move_target = feature.id
    assert view._repaint_preview()
    assert view._shape_actor is actor, "reine Deckkraftwechsel bauen keine neue Vorschau"
    assert actor.opacity() == pytest.approx(0.45)
    view._slot_handle.pressing = False
    view._slot_turn_base = None
    view.drop_move_proposal()
    assert view._repaint_preview()
    assert view._shape_actor is actor and actor.opacity() == pytest.approx(0.18)
    view._drop_face_handle()
    view._face_handle(feature)
    assert view._shape_actor is not actor
    assert view._shape_actor.opacity() == pytest.approx(0.18)


@pytest.mark.parametrize("turn", [False, True])
def test_real_gizmo_steps_strengthen_preview_but_zero_motion_does_not(
    feature_view: Viewport, turn: bool
) -> None:
    view = feature_view
    feature = view._features_of_selection()["hole_1"]
    view._face_handle(feature)
    actor = view._shape_actor
    assert actor is not None
    view._drag_preview(TransformSteps(offset=(0.0, 0.0, 0.0), axis=None, angle=0.0, scale=1.0))
    assert actor.opacity() == pytest.approx(0.18)
    view._drag_preview(
        TransformSteps(
            offset=(0.0, 0.0, 0.0) if turn else (2.0, 0.0, 0.0),
            axis="z" if turn else None,
            angle=15.0 if turn else 0.0,
            scale=1.0,
        )
    )
    assert view._shape_actor is actor and actor.opacity() == pytest.approx(0.45)
    view._end_drag()
    assert actor in view.renderer.removed
    view._face_handle(feature)
    assert view._shape_actor is not actor and view._shape_actor.opacity() == pytest.approx(0.18)
