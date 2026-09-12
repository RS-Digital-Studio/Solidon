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
import math
import weakref
from PySide6.QtCore import QEvent, QLocale, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QVBoxLayout, QWidget
from app.ui.render.factory import make_renderer
from app.ui.render.api import SurfaceStyle
from app.ui.render.navigator import Navigator, WHEEL_STEP
from tests.test_navigator import _Log
from tests.test_render_contract import cube, look_down

application = QApplication([])
print("qt-app", flush=True)
window = QWidget()
window.resize(320, 240)
layout = QVBoxLayout(window)
text_field = QLineEdit(window)
number_field = QDoubleSpinBox(window)
number_field.setLocale(QLocale(QLocale.Language.German))
layout.addWidget(text_field)
layout.addWidget(number_field)
print("vor make_renderer", flush=True)
view = make_renderer(window)
print("renderer da", flush=True)
layout.addWidget(view.widget)
window.show()
print("fenster gezeigt", flush=True)
window.activateWindow()
print("aktiviert", flush=True)
for runde in range(10):
    application.processEvents()
    print(f"durchlauf-{runde}", flush=True)
body = view.add_surface(*cube(), name="body", style=SurfaceStyle(lighting=False))
print("flaeche da", flush=True)
look_down(view, body.bounds())
view.render()
print("gerendert", flush=True)
assert view.screenshot().max() > 100
print("bild geprueft", flush=True)
# Die echten Qt-Radereignisse müssen bis zur Kamera reichen, auch unterhalb
# einer Raste. Beide Projektionen behalten dabei den Weltpunkt am Zeiger.
navigator = Navigator(view, "solidon", _Log().callbacks())
token = view.add_pointer_listener(navigator.handle)
pointer = QPointF(75, 45)
ratio = view.widget.devicePixelRatioF()
x, y = round(pointer.x() * ratio), round(pointer.y() * ratio)
for parallel in (False, True):
    view.set_parallel_projection(parallel)
    for angles in ([15] * 8, [60, 60], [120], [180], [240], [-15] * 8, [-120], [0]):
        pose = view.camera_pose()
        scale = view.parallel_scale()
        distance = math.dist(pose.position, pose.focal_point)
        anchor = view.display_to_world(x, y, view.focal_depth())
        total = 0
        for angle in angles:
            event = QWheelEvent(
                pointer, pointer, QPoint(), QPoint(0, angle), Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
            )
            QApplication.sendEvent(view.widget, event)
            total += angle
            factor = (1.0 + WHEEL_STEP) ** (total / 120.0)
            after = view.camera_pose()
            actual = scale / view.parallel_scale() if parallel else (
                distance / math.dist(after.position, after.focal_point)
            )
            assert math.isclose(actual, factor, rel_tol=1e-10), (parallel, angles, total, actual)
            current = view.display_to_world(x, y, view.focal_depth())
            assert math.dist(anchor, current) < 1e-8
        view.set_camera_pose(pose)
        view.set_parallel_scale(scale)
view.remove_pointer_listener(token)
del navigator
print("feine und normale Radbewegungen geprüft", flush=True)
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
print("vor schliessen", flush=True)
view.close()
view.close()
print("geschlossen", flush=True)
window.close()
window.deleteLater()
del view, window, layout, body, text_field, number_field
application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
gc.collect()
assert reference() is None, "Der geschlossene native Renderer lebt weiter."
print("native canvas drawn and released")
"""
    try:
        done = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "QT_QPA_PLATFORM": platform},
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired as hanging:
        # **Die Spur retten.** Der Prozess wird gekillt, und mit ihm verschwand
        # bisher jede Auskunft darüber, wo er stehenblieb: Die Meldung trug den
        # ganzen Skripttext und kein einziges Zwischenergebnis. Auf dem
        # Intel-Mac lief der Test am 08.09.2026 genau so ins Leere.
        def spur(strom: object) -> str:
            if strom is None:
                return ""
            return strom.decode("utf-8", "replace") if isinstance(strom, bytes) else str(strom)

        gemeldet = spur(hanging.stdout).split() or ["nichts"]
        pytest.fail(
            f"nach 90 s nicht fertig — zuletzt gemeldet: {gemeldet[-1]} "
            f"(alles: {' '.join(gemeldet)})\n{spur(hanging.stderr)}"
        )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Traceback" not in done.stderr, done.stderr
    assert "native canvas drawn and released" in done.stdout


@pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")
@pytest.mark.parametrize("scale", [1, 2])
def test_native_item_pick_slack_stays_constant_on_hidpi_screens(scale: int) -> None:
    """Drei logische Pixel neben einem Griff bleiben bei 100 und 200 Prozent greifbar."""
    platform = {"win32": "windows", "darwin": "cocoa"}.get(sys.platform, "xcb")
    if platform == "xcb" and not os.environ.get("DISPLAY"):
        if os.environ.get("CI"):
            pytest.fail("Der native Linux-Fenstertest braucht DISPLAY, zum Beispiel durch Xvfb.")
        pytest.skip("kein X11-Display für den nativen Qt-Fensterweg")
    script = """
import math
import os
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from app.ui.render.api import SurfaceStyle
from app.ui.render.factory import make_renderer
from tests.test_render_contract import look_down, plate

application = QApplication([])
window = QWidget()
window.resize(400, 300)
layout = QVBoxLayout(window)
layout.setContentsMargins(0, 0, 0, 0)
view = make_renderer(window)
layout.addWidget(view.widget)
window.show()
application.processEvents()
ratio = view.widget.devicePixelRatioF()
print(f"Geräteverhältnis: {ratio}", flush=True)
assert math.isclose(ratio, float(os.environ["QT_SCALE_FACTOR"]))
try:
    for overlay in (False, True):
        item = view.add_surface(
            *plate(0, 20), name="handle",
            style=SurfaceStyle(lighting=False, keep_in_front=overlay),
        )
        look_down(view, item.bounds())
        view.render()
        x, y, _depth = view.world_to_display((20, 10, 0))
        assert view.pick_surface(x + 3 * ratio, y, tolerance=0) is None
        assert view.pick_item(x + 3 * ratio, y) is item, (ratio, overlay)
        assert view.pick_item(x + 6 * ratio, y) is None, (ratio, overlay)
        view.remove(item)
finally:
    view.close()
    window.close()
    window.deleteLater()
    application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
"""
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "QT_QPA_PLATFORM": platform,
            "QT_SCREEN_SCALE_FACTORS": "1",
            "QT_SCALE_FACTOR": str(scale),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Traceback" not in done.stderr, done.stderr


def test_the_viewport_asks_the_factory_before_it_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Adapter bleibt die Ansicht leer — und sagt es nicht erst beim Absturz."""
    from app.ui import viewport

    monkeypatch.setattr(viewport, "_effective_platform", lambda: "windows")
    monkeypatch.delenv(viewport.HEADLESS_VARIABLE, raising=False)
    monkeypatch.setattr(factory, "available", lambda: False)
    assert viewport._available() is False
    monkeypatch.setattr(factory, "available", lambda: True)
    assert viewport._available() is True
