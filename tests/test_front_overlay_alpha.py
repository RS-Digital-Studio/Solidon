"""Vordergrundmaterial und Beschriftungsfelder halten ihren Vertrag ohne GPU."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from app.ui.render.api import LabelStyle, SurfaceStyle
from app.ui.render.gfx_renderer import OVERLAY_QUEUE, GfxItem, GfxLabels, GfxRenderer


class MaterialRenderer(GfxRenderer):
    """Nur CPU-Materialaufbau; kein Fenster, Gerät oder Renderdurchgang."""

    def __init__(self) -> None:
        import pygfx

        self._gfx = pygfx

    def _register(self, item: GfxItem) -> GfxItem:
        return item

    def _reused(self, key: tuple[Any, ...] | None, rows: int, faces: int = 0) -> None:
        return None


@pytest.fixture
def material_renderer(monkeypatch: pytest.MonkeyPatch) -> MaterialRenderer:
    """Eine versehentliche Adapteranforderung ist ein Fehler, kein Skip."""
    import wgpu

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Dieser Materialtest darf keinen Grafikadapter anfordern")

    monkeypatch.setattr(wgpu.gpu, "request_adapter_sync", forbidden)
    monkeypatch.setattr(wgpu.gpu, "request_adapter_async", forbidden)
    return MaterialRenderer()


def surface(renderer: MaterialRenderer, style: SurfaceStyle) -> GfxItem:
    """Ein Dreieck genügt für Fläche, eigene Rückseite und mitgeführte Kanten."""
    vertices = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    faces = np.array([[0, 1, 2]])
    item = renderer.add_surface(vertices, faces, name="test", style=style)
    assert isinstance(item, GfxItem)
    return item


@pytest.mark.parametrize("in_front", [False, True])
@pytest.mark.parametrize("opacity", [0.0, 0.45, 1.0])
@pytest.mark.parametrize("lighting", [False, True])
def test_initial_surface_materials_respect_front_order(
    material_renderer: MaterialRenderer, in_front: bool, opacity: float, lighting: bool
) -> None:
    """Auch Rückseite und Kanten eröffnen keinen späteren OIT-Block vor dem Raum."""
    item = surface(
        material_renderer,
        SurfaceStyle(
            colour="#ffab23",
            opacity=opacity,
            keep_in_front=in_front,
            lighting=lighting,
            backface_colour="#804000",
            show_edges=True,
        ),
    )
    expected = "auto" if opacity == 1.0 else ("blend" if in_front else "weighted_blend")
    assert len(item.objects) == 3
    assert item.in_front is in_front
    assert item.pickable()
    for obj in item.objects:
        assert obj.material.opacity == pytest.approx(opacity)
        assert obj.material.alpha_mode == expected
        assert obj.material.depth_test is (not in_front)
        if in_front:
            assert obj.material.render_queue == OVERLAY_QUEUE
        else:
            assert obj.material.render_queue != OVERLAY_QUEUE


@pytest.mark.parametrize("in_front", [False, True])
@pytest.mark.parametrize("force_opaque", [False, True])
def test_opacity_changes_keep_front_order_and_explicit_opaque_override(
    material_renderer: MaterialRenderer, in_front: bool, force_opaque: bool
) -> None:
    """Hover, Ruhe und Null ändern weder Geometrie noch Pickbarkeit oder Materialbesitz."""
    item = surface(
        material_renderer,
        SurfaceStyle(
            colour="#ffab23",
            opacity=1.0,
            keep_in_front=in_front,
            lighting=False,
            backface_colour="#804000",
            backface_opacity=0.5,
            show_edges=True,
            force_opaque=force_opaque,
        ),
    )
    objects = tuple(item.objects)
    materials = tuple(obj.material for obj in objects)
    geometry = tuple(obj.geometry for obj in objects)
    pick_flags = tuple(obj.material.pick_write for obj in objects)
    depth_test = tuple(obj.material.depth_test for obj in objects)
    for opacity in (0.45, 1.0, 0.0, 0.2, 1.0):
        item.set_opacity(opacity)
        assert tuple(item.objects) == objects
        assert tuple(obj.material for obj in objects) == materials
        assert tuple(obj.geometry for obj in objects) == geometry
        assert tuple(obj.material.pick_write for obj in objects) == pick_flags
        assert tuple(obj.material.depth_test for obj in objects) == depth_test
        assert item.pickable()
        for obj, share in zip(objects, (1.0, 0.5, 1.0), strict=True):
            assert obj.material.render_queue_is_set is in_front
            if in_front:
                assert obj.material.render_queue == OVERLAY_QUEUE
            else:
                assert obj.material.render_queue != OVERLAY_QUEUE
            effective = opacity * share
            expected = "auto" if effective == 1.0 else ("blend" if in_front else "weighted_blend")
            assert obj.material.opacity == pytest.approx(effective)
            assert obj.material.alpha_mode == ("solid" if force_opaque else expected)


@pytest.mark.parametrize("background", [None, "#343b46"])
def test_empty_label_fields_stay_hidden_through_updates_visibility_and_reuse(
    material_renderer: MaterialRenderer, background: str | None
) -> None:
    """Der leere Längenplatz bleibt erhalten, ohne neben echten Buchstaben einen Fleck zu zeigen."""
    gfx = material_renderer._gfx
    style = LabelStyle(background=background, margin=4)
    item = GfxLabels("gizmo_labels", gfx.Group(), style)
    anchors = np.arange(18, dtype=float).reshape(6, 3)
    neighbours = ["X", "Y", "Z", "L", "L"]
    pairs: dict[str, tuple[Any, Any | None]] = {}
    fixed = None
    for text in ("", "16,03 mm", "", "16,03 mm"):
        item.update_labels(anchors, [*neighbours, text])
        assert item.labels == [*neighbours, text]
        assert len(item.texts) == 6 and len(item.fields) == (6 if background else 0)
        np.testing.assert_array_equal(item.anchors, anchors)
        for label, anchor in zip(item.texts, anchors, strict=True):
            np.testing.assert_array_equal(label.local.position, anchor)
        if fixed is None:
            fixed = tuple(item.texts[:5])
        assert tuple(item.texts[:5]) == fixed
        field = item.fields[-1] if background else None
        pair = (item.texts[-1], field)
        if text in pairs:
            assert pair == pairs[text], "ruhende Paare werden über _wake wiederverwendet"
        pairs[text] = pair
        for visible in (False, True):
            item.set_visible(visible)
            assert item.visible() is visible
            assert all(label.visible for label in item.texts)
            if background:
                assert all(part.visible for part in item.fields[:5])
                assert field.visible is bool(text)
        anchors = anchors + 1.0
    # Derselbe Übernahmepfad wie add_labels bei einem abgeräumten Item.
    successor = GfxLabels("gizmo_labels", item.root, style)
    successor.adopt(item)
    item.root = gfx.Group()
    assert item.labels == item.texts == item.fields == []
    for text in ("", "16,03 mm", ""):
        successor.build(anchors, [*neighbours, text])
        assert tuple(successor.texts[:5]) == fixed
        assert successor.texts[-1] is pairs[text][0]
        np.testing.assert_array_equal(successor.anchors, anchors)
        successor.set_visible(False)
        successor.set_visible(True)
        assert all(label.visible for label in successor.texts)
        if background:
            assert successor.fields[-1] is pairs[text][1]
            assert [field.visible for field in successor.fields] == [True] * 5 + [bool(text)]
        else:
            assert successor.fields == []
