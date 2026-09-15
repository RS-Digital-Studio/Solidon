"""Die eine Baustelle des Renderers (§18): Wache und Aufbau, ohne Fenster."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import threading
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


def test_the_adapter_answer_is_remembered_for_the_whole_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gefragt wird einmal, nicht je Viewport.

    Die Frage an wgpu kostete am 14.09.2026 gemessene 763 ms im Hauptthread
    (Median aus drei Läufen, Windows 11, RTX 4080, Fremdlast), auf Roberts
    Maschine im guten Fall 5 bis 7,8 s — und ein Sprachwechsel baut das
    Fenster samt Ansicht noch einmal auf.
    """
    asked: list[int] = []

    def counted() -> bool:
        asked.append(1)
        return True

    factory.forget()
    monkeypatch.setattr(factory, "_adapter_present", counted)
    try:
        assert factory.available() is True
        assert factory.available() is True
        assert factory.probe() is True
    finally:
        factory.forget()
    assert asked == [1], "der zweite Viewport fragt die Grafikkarte noch einmal"


def test_a_running_probe_is_awaited_instead_of_asked_a_second_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wer während der vorgezogenen Frage ankommt, wartet auf sie.

    wgpu baut seine Instanz prozessweit und ohne Sperre auf; zwei Fragen
    zugleich wären zwei Aufbauten. Und teurer als Warten ist es ohnehin.
    """
    asked: list[int] = []
    started = threading.Event()
    release = threading.Event()

    def held() -> bool:
        asked.append(1)
        started.set()
        release.wait(30.0)
        return True

    factory.forget()
    monkeypatch.setattr(factory, "_adapter_present", held)
    answers: list[bool] = []
    prober = threading.Thread(target=factory.probe)
    prober.start()
    try:
        assert started.wait(10.0), "die vorgezogene Frage lief nicht an"
        waiting = threading.Thread(target=lambda: answers.append(factory.available()))
        waiting.start()
        # Erst wenn der Wartende steht, darf die Frage antworten — sonst fände
        # er sie fertig vor und der Test misst den anderen Weg.
        waiting.join(0.2)
        assert waiting.is_alive(), "available() hat nicht auf die laufende Frage gewartet"
        release.set()
        waiting.join(10.0)
    finally:
        release.set()
        prober.join(10.0)
        factory.forget()
    assert answers == [True]
    assert asked == [1], "gefragt wurde je Prozess einmal, nicht je Aufrufer"


def test_a_probe_that_does_not_come_back_lets_the_view_sign_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Frist statt einer offenen Wartezeit (§27).

    Auf einem hängenden Treiber dauerte die Adapterfrage Minuten, und das
    Fenster hing daran, ohne dass jemand sie hätte abbrechen können. Nach der
    Frist meldet sich die Ansicht mit dem Satz ab, den sie für einen fehlenden
    Adapter ohnehin hat.
    """
    started = threading.Event()
    release = threading.Event()

    def held() -> bool:
        started.set()
        release.wait(30.0)
        return True

    factory.forget()
    monkeypatch.setattr(factory, "_adapter_present", held)
    monkeypatch.setattr(factory, "ADAPTER_TIMEOUT_SECONDS", 0.05)
    prober = threading.Thread(target=factory.probe)
    prober.start()
    try:
        assert started.wait(10.0), "die vorgezogene Frage lief nicht an"
        assert factory.available() is False, "ohne Antwort in der Frist bleibt die Ansicht aus"
    finally:
        release.set()
        prober.join(10.0)
        factory.forget()


def test_the_application_asks_for_the_adapter_before_it_loads_the_registry() -> None:
    """Die Anwendung zieht die Frage wirklich vor — nicht nur die Fabrik kann es.

    AGENTS.md, Testart „Anschluss": nicht „der Cache kann es", sondern „die
    Anwendung tut es". Gelesen wird der Quelltext und nicht die gebaute
    Anwendung, weil ``main`` eine Ereignisschleife startet — derselbe Weg, den
    ``test_cursors`` für den Zeiger-Wächter geht.
    """
    source = Path(__file__).resolve().parents[1] / "app" / "ui" / "app.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    start = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    order = [
        getattr(call.func, "id", getattr(call.func, "attr", ""))
        for call in ast.walk(start)
        if isinstance(call, ast.Call)
    ]
    assert "_AdapterProbe" in order, "der Start fragt den Adapter nicht vorab"
    assert "start" in order, "der Arbeiter läuft an der Leine vorbei oder gar nicht"
    lines = source.read_text(encoding="utf-8").splitlines()
    probe_line = next(index for index, line in enumerate(lines) if "_AdapterProbe()" in line)
    registry_line = next(index for index, line in enumerate(lines) if "load_operations()" in line)
    assert probe_line < registry_line, (
        "die Frage steht hinter dem Register und überlappt damit nichts mehr"
    )


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
print("bild geprüft", flush=True)
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
print("vor schließen", flush=True)
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


#: **Unter Xvfb reißt der Kindprozess sporadisch** (Tag-Läufe von v0.4.1,
#: 13.09.2026: erst bei 200 Prozent, im nächsten Lauf bei beiden grün, im
#: übernächsten bei 100 Prozent — Geräteverhältnis gemeldet, dann Exit -11).
#: Ob das der Softwarerenderer des Runners ist oder die Anwendung, sagt nur
#: ein Linux mit Bildschirm; bis dahin steht der Fall bei RM-104, und die
#: Marke ist nicht streng: Sie hält den Bau nicht auf und verschweigt den
#: Fall nicht.
_XVFB_TEARS = pytest.mark.xfail(
    sys.platform.startswith("linux"),
    strict=False,
    raises=AssertionError,
    reason="Linux/Xvfb: der Renderer-Kindprozess reißt sporadisch (RM-104)",
)


@pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")
@pytest.mark.parametrize(
    "scale",
    [pytest.param(1, marks=_XVFB_TEARS), pytest.param(2, marks=_XVFB_TEARS)],
)
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
