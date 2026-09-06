"""Die eine Baustelle des Renderers (§18): Wache und Aufbau, ohne Fenster."""

from __future__ import annotations

import pytest

from app.ui.render import factory
from app.ui.render.gfx_renderer import GfxRenderer
from tests.test_render_contract import GFX_MISSING


def test_availability_is_a_plain_answer() -> None:
    """Die Wache antwortet mit ja oder nein, nie mit einer Ausnahme."""
    assert isinstance(factory.available(), bool)
    if GFX_MISSING is None:
        assert factory.available() is True


@pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")
def test_the_factory_builds_pygfx_without_a_window() -> None:
    """Ohne Fenster entsteht derselbe Renderer, den die Ansicht zeichnet."""
    view = factory.make_renderer(offscreen=True, size=(64, 48))
    try:
        assert isinstance(view, GfxRenderer)
        assert view.view_size() == (64, 48)
    finally:
        view.close()


def test_the_viewport_asks_the_factory_before_it_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Adapter bleibt die Ansicht leer — und sagt es nicht erst beim Absturz."""
    from app.ui import viewport

    monkeypatch.setattr(viewport, "_effective_platform", lambda: "windows")
    monkeypatch.delenv(viewport.HEADLESS_VARIABLE, raising=False)
    monkeypatch.setattr(factory, "available", lambda: False)
    assert viewport._available() is False
    monkeypatch.setattr(factory, "available", lambda: True)
    assert viewport._available() is True
