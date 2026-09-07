"""Die eine Baustelle des Renderers (§18): Wache und Aufbau, ohne Fenster."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.ui.render import factory
from app.ui.render.gfx_renderer import GfxRenderer
from tests.test_render_contract import GFX_MISSING


def test_availability_is_a_plain_answer() -> None:
    """Die Wache antwortet mit ja oder nein, nie mit einer Ausnahme."""
    assert isinstance(factory.available(), bool)
    if GFX_MISSING is None:
        assert factory.available() is True


def test_ci_has_a_working_graphics_adapter() -> None:
    """Eine CI ohne Renderer darf übersprungene Bildtests nicht als Abnahme melden."""
    if os.environ.get("CI"):
        assert GFX_MISSING is None, f"Die CI kann den einzigen Renderer nicht prüfen: {GFX_MISSING}"


@pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")
def test_the_factory_builds_pygfx_without_a_window() -> None:
    """Ohne Fenster entsteht derselbe Renderer, den die Ansicht zeichnet."""
    view = factory.make_renderer(offscreen=True, size=(64, 48))
    try:
        assert isinstance(view, GfxRenderer)
        assert view.view_size() == (64, 48)
    finally:
        view.close()


@pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")
def test_native_qt_canvas_draws_and_releases_its_renderer() -> None:
    """Ein eigener Prozess prüft den echten Qt-Fensterweg neben den Offscreen-Verträgen."""
    platform = {"win32": "windows", "darwin": "cocoa"}.get(sys.platform, "xcb")
    if platform == "xcb" and not os.environ.get("DISPLAY"):
        if os.environ.get("CI"):
            pytest.fail("Der native Linux-Fenstertest braucht DISPLAY, zum Beispiel durch Xvfb.")
        pytest.skip("kein X11-Display für den nativen Qt-Fensterweg")
    script = """
import gc
import weakref
from PySide6.QtCore import QEvent, QLocale, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QVBoxLayout, QWidget
from app.ui.render.factory import make_renderer
from app.ui.render.api import SurfaceStyle
from tests.test_render_contract import cube, look_down

application = QApplication([])
window = QWidget()
window.resize(320, 240)
layout = QVBoxLayout(window)
text_field = QLineEdit(window)
number_field = QDoubleSpinBox(window)
number_field.setLocale(QLocale(QLocale.Language.German))
layout.addWidget(text_field)
layout.addWidget(number_field)
view = make_renderer(window)
layout.addWidget(view.widget)
window.show()
window.activateWindow()
for _ in range(10):
    application.processEvents()
body = view.add_surface(*cube(), name="body", style=SurfaceStyle(lighting=False))
look_down(view, body.bounds())
view.render()
assert view.screenshot().max() > 100
text_field.setFocus()
application.processEvents()
assert application.focusWidget() is text_field
QTest.keyClicks(text_field, "wasdqeWASDQE0123456789")
assert text_field.text() == "wasdqeWASDQE0123456789"
number_field.setFocus()
number_field.lineEdit().selectAll()
QTest.keyClicks(number_field, "12,5")
QTest.keyClick(number_field, Qt.Key.Key_Return)
assert abs(number_field.value() - 12.5) < 1e-9
reference = weakref.ref(view)
view.close()
view.close()
window.close()
window.deleteLater()
del view, window, layout, body, text_field, number_field
application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
gc.collect()
assert reference() is None, "Der geschlossene native Renderer lebt weiter."
print("native canvas drawn and released")
"""
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": platform},
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Traceback" not in done.stderr, done.stderr
    assert "native canvas drawn and released" in done.stdout


def test_the_viewport_asks_the_factory_before_it_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Adapter bleibt die Ansicht leer — und sagt es nicht erst beim Absturz."""
    from app.ui import viewport

    monkeypatch.setattr(viewport, "_effective_platform", lambda: "windows")
    monkeypatch.delenv(viewport.HEADLESS_VARIABLE, raising=False)
    monkeypatch.setattr(factory, "available", lambda: False)
    assert viewport._available() is False
    monkeypatch.setattr(factory, "available", lambda: True)
    assert viewport._available() is True
