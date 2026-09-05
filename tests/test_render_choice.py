"""Welcher Renderer die Ansicht zeichnet — die eine Stelle, an der es entschieden wird."""

from __future__ import annotations

import logging

import pytest

from app.ui.render import choice
from app.ui.render.api import Renderer
from tests.test_render_vtk import GFX_MISSING


def test_vtk_is_the_default_and_the_variable_chooses() -> None:
    assert choice.backend({}) == "vtk"
    assert choice.backend({choice.RENDERER_VARIABLE: "gfx"}) == "gfx"
    assert choice.backend({choice.RENDERER_VARIABLE: " PyGFX "}) == "gfx"
    assert choice.backend({choice.RENDERER_VARIABLE: "wgpu"}) == "gfx"
    assert choice.backend({choice.RENDERER_VARIABLE: "vtk"}) == "vtk"


def test_a_misspelt_renderer_falls_back_to_vtk_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ein Tippfehler kostet nicht die Ansicht — aber er bleibt nicht still."""
    with caplog.at_level(logging.WARNING, logger="app.ui.render.choice"):
        assert choice.backend({choice.RENDERER_VARIABLE: "opengl"}) == "vtk"
    assert any("opengl" in record.getMessage() for record in caplog.records)


def test_the_factory_builds_the_chosen_renderer_without_a_window() -> None:
    from app.ui.render.vtk_renderer import VtkRenderer

    view = choice.make_renderer(offscreen=True, size=(64, 48), kind="vtk")
    try:
        assert isinstance(view, VtkRenderer)
        assert isinstance(view, Renderer)
        assert view.view_size() == (64, 48)
    finally:
        view.close()


@pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")
def test_the_factory_builds_pygfx_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Variable wirkt bis in die Fabrik — ohne ausdrückliches ``kind``."""
    from app.ui.render.gfx_renderer import GfxRenderer

    monkeypatch.setenv(choice.RENDERER_VARIABLE, "gfx")
    view = choice.make_renderer(offscreen=True, size=(64, 48))
    try:
        assert isinstance(view, GfxRenderer)
        assert view.view_size() == (64, 48)
    finally:
        view.close()


def test_availability_is_asked_per_renderer() -> None:
    """Die Wache des Viewports fragt genau den Renderer, der gewählt ist."""
    assert isinstance(choice.available("vtk"), bool)
    if GFX_MISSING is None:
        assert choice.available("gfx") is True
