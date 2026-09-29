"""Prüfstand massbild am echten Fenster, gebaut wie die Anwendung.

Aufruf: python probe.py <baum> <szenario> <modell> [<marke>]

Lädt ``app`` aus <baum> (erste Zeile des Suchpfads, geprüft), baut das Fenster
über ``build_application`` wie ``app.ui.app.main`` (``load_operations`` davor,
maximiert, ``start``), öffnet <modell> und führt ``scenario_<szenario>.py``
aus. Ausgabe nach ``out/<szenario>-<marke>.txt`` mit ``buffering=1``. Das
Fenster ist sichtbar (die Ansicht rendert sonst nicht) und wird am Ende sofort
geschlossen; ein harter Zeitgeber beendet den Prozess nach 300 s.
"""

from __future__ import annotations

import os
import sys
import threading

threading.Timer(240.0, lambda: os._exit(9)).start()

import faulthandler  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

TREE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TREE))
SCENARIO = sys.argv[2]
MODEL = Path(sys.argv[3])
TAG = sys.argv[4] if len(sys.argv) > 4 else TREE.name
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
LOG = open(OUT / f"{SCENARIO}-{TAG}.txt", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
faulthandler.enable(LOG)
faulthandler.dump_traceback_later(230, exit=True, file=LOG)

PROFILE = HERE / "profile" / TAG
import shutil  # noqa: E402

shutil.rmtree(PROFILE, ignore_errors=True)
PROFILE.mkdir(parents=True, exist_ok=True)
for variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
    os.environ[variable] = str(PROFILE)
os.environ.pop("QT_QPA_PLATFORM", None)


def log(*parts: object) -> None:
    LOG.write(" ".join(str(part) for part in parts) + "\n")


import app  # noqa: E402

log("app:", app.__file__)
if not Path(app.__file__).resolve().is_relative_to(TREE):
    log("ABBRUCH: app liegt nicht im Baum")
    os._exit(3)

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.app import build_application  # noqa: E402

# Einzelne Wege abschalten, ohne den Baum zu ändern: ``OHNE=1`` (keine
# Wiederkehr abgeräumter Renderer-Elemente), ``OHNE=2`` (Griff neu statt
# versetzt), ``OHNE=3`` (Maßgruppe neu statt behalten). Mehrere: ``OHNE=12``.
_ohne = os.environ.get("OHNE", "")
if "1" in _ohne:
    from app.ui.render.gfx_renderer import GfxRenderer as _Gfx  # noqa: E402

    _Gfx._reused = lambda self, *args, **kwargs: None  # type: ignore[method-assign]
    _Gfx._reused_labels = lambda self, *args, **kwargs: None  # type: ignore[method-assign]
if "2" in _ohne:
    from app.ui.render.gizmo import Gizmo as _Gizmo  # noqa: E402

    _Gizmo.rotation = property(lambda self: None)  # type: ignore[assignment]
if "3" in _ohne:
    import app.ui.panels as _panels_o3  # noqa: E402

    _panels_o3.FeaturePanel._measure_signature = lambda self, *a, **k: None
log("abgeschaltet:", _ohne or "nichts")
if "4" in _ohne:
    import pygfx as _pygfx  # noqa: E402

    _orig_wgpu_init = _pygfx.WgpuRenderer.__init__

    def _with_events(self, *args, **kwargs):
        kwargs["enable_events"] = True
        _orig_wgpu_init(self, *args, **kwargs)

    _pygfx.WgpuRenderer.__init__ = _with_events
application, window = build_application([])
window.settings.first_run_done = True
# Wie ``app.main``: der Dateiempfang hängt an der Anwendung — im Baum mit
# ``app_events`` dort, sonst als eigener Filter.
from app.ui.app import FileOpenListener  # noqa: E402

_listener = FileOpenListener(window, application)
try:
    from app.ui import app_events as _app_events  # noqa: E402

    _app_events.listen(_listener, (QEvent.Type.FileOpen,))
    log("Dateiempfang: app_events")
except ImportError:
    application.installEventFilter(_listener)
    log("Dateiempfang: eigener Filter")

closed: list[str] = []


def sweep() -> None:
    widget = application.activeModalWidget()
    if widget is not None and widget is not window and widget.window() is not window:
        closed.append(f"{type(widget).__name__}:{widget.windowTitle()}")
        log("DIALOG geschlossen:", type(widget).__name__, widget.windowTitle())
        widget.close()
    popup = application.activePopupWidget()
    if popup is not None:
        closed.append(f"popup:{type(popup).__name__}")
        popup.close()


sweeper = QTimer()
sweeper.timeout.connect(sweep)
sweeper.start(400)

screen = next(
    (s for s in application.screens() if s != application.primaryScreen()),
    application.primaryScreen(),
)
log("Bildschirm:", screen.name(), screen.size().width(), screen.size().height())
# Ohne zweiten Monitor (Bildschirme aus, nur „NV-Failsafe“ 640 × 480) wird das
# Fenster auf die Größe des MSI gestellt, damit Malen und Bild dieselbe Fläche
# kosten wie dort: ``PROBE_SIZE=2560x1392``.
_size = os.environ.get("PROBE_SIZE")
if _size:
    from PySide6.QtCore import QRect  # noqa: E402

    _w, _h = (int(v) for v in _size.split("x"))
    window.setGeometry(QRect(screen.availableGeometry().topLeft(), __import__("PySide6.QtCore").QtCore.QSize(_w, _h)))
    window.show()
else:
    window.setGeometry(screen.availableGeometry())
    window.showMaximized()
window.start()
for _ in range(30):
    application.processEvents()
log("Fenster:", window.width(), window.height(), "Ansicht:", window.viewport.renderer.view_size() if window.viewport.renderer is not None else None)


def pump(seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        application.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.002)


def idle(settle: float = 0.6, timeout: float = 120.0) -> None:
    """Bis Sitzung, Platzierungsarbeiter und Vorschau ruhen."""
    deadline = time.monotonic() + timeout
    quiet = time.monotonic()
    while time.monotonic() < deadline:
        application.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.003)
        flow = window._quiet_placement
        approval = window._preview_approval
        busy = (
            window.session.busy
            or (flow is not None and getattr(flow, "_tool_busy", False))
            or (flow is not None and getattr(flow, "_surface_busy", False))
            or window._feature_preview.isActive()
            or bool(window.session._previews)
            or (approval is not None and approval.pending_click is not None)
            or bool(getattr(window.session, "_placements", None))
            or getattr(window, "_answers_worker", None) is not None
        )
        if busy:
            quiet = time.monotonic()
        elif time.monotonic() - quiet >= settle:
            return
    log("WARNUNG: idle timeout")


def render_widget():
    return window.viewport.renderer.widget


def to_widget(point) -> QPointF:
    renderer = window.viewport.renderer
    x, y, _depth = renderer.world_to_display(tuple(float(v) for v in point))
    ratio = renderer.device_ratio()
    return QPointF(x / ratio, y / ratio)


def send(kind, position: QPointF, buttons, button=Qt.MouseButton.NoButton, process=True) -> None:
    widget = render_widget()
    global_position = QPointF(widget.mapToGlobal(position.toPoint()))
    event = QMouseEvent(
        kind, position, global_position, button, buttons, Qt.KeyboardModifier.NoModifier
    )
    application.sendEvent(widget, event)
    if process:
        application.processEvents()


def click(point: QPointF, process=True) -> None:
    left = Qt.MouseButton.LeftButton
    send(QEvent.Type.MouseMove, point, Qt.MouseButton.NoButton, process=process)
    send(QEvent.Type.MouseButtonPress, point, left, left, process=process)
    send(QEvent.Type.MouseButtonRelease, point, Qt.MouseButton.NoButton, left, process=process)


def open_model() -> None:
    previous = window.session.last_result
    window.open_path(MODEL)
    deadline = time.monotonic() + 200
    while time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.01)
        result = window.session.last_result
        if (
            result is not None
            and result is not previous
            and result.complete
            and result.scene.objects
            and not window.session.busy
            and window.viewport._result is result
        ):
            break
    idle(1.0)


try:
    t_open = time.monotonic()
    open_model()
    log("geöffnet:", MODEL.name, f"{time.monotonic() - t_open:.1f} s")
    exec((HERE / f"scenario_{SCENARIO}.py").read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    import traceback

    log("AUSNAHME")
    traceback.print_exc(file=LOG)
finally:
    log("Geschlossene Dialoge:", closed)
    try:
        window.session.modified = False
        window.release()
        window.viewport.release_renderer()
        window.hide()
        application.processEvents()
    except Exception:  # noqa: BLE001
        pass
    LOG.flush()
    os._exit(0)
