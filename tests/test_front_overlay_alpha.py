"""Vordergrund mischt geordnet, Raumtransparenz bleibt gewichtet — ohne GPU."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from app.ui.render.api import SurfaceStyle
from app.ui.render.gfx_renderer import OVERLAY_QUEUE, GfxItem, GfxRenderer


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
