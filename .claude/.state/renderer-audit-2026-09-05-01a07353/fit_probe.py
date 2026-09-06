"""Prüft echtes Pos1 vor jedem künstlichen Bildaufruf am nativen Peg-Fenster."""
from __future__ import annotations
import argparse, collections, dataclasses, faulthandler, itertools, json, os, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, default=HERE / "final-source-v6")
parser.add_argument("--renderer", choices=("gfx", "vtk"), required=True)
parser.add_argument("--output", default="fit-probe-v6")
parser.add_argument("--project", type=Path, default=HERE / "final-v5-calibration/gfx/file-09/bearbeitung-geprueft.p3d")
args = parser.parse_args()
OUT = HERE / args.output / args.renderer
OUT.mkdir(parents=True, exist_ok=True)
sys.stdout = (OUT / "run.log").open("w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
faulthandler.enable()
faulthandler.dump_traceback_later(90, repeat=True)
watchdog = threading.Timer(180, lambda: os._exit(124))
watchdog.daemon = True
watchdog.start()
sys.path.insert(0, str(args.source.resolve()))
os.environ["SOLIDON_RENDERER"] = args.renderer
os.environ.pop("QT_QPA_PLATFORM", None)
for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    os.environ[key] = str(OUT / "profile" / key)

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from app.core.bootstrap import load_operations
from app.ui.settings import UiSettings, save_settings
save_settings(UiSettings(first_run_done=True, language="de", check_for_updates=False))
load_operations()
from app.ui.app import build_application
from tools.window_bench import shutdown_window

app, window = build_application(["solidon-fit-probe"])
window.resize(1600, 1000)
window.show()
window.activateWindow()
view = window.viewport
counts = collections.Counter()
result = {"source": str(args.source.resolve()), "renderer": args.renderer,
          "platform": app.platformName(), "project": str(args.project.resolve()), "checks": []}

def pump(seconds=0):
    end = time.perf_counter() + seconds
    while True:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        if time.perf_counter() >= end:
            break
        time.sleep(.002)

def wrap(owner, name, key):
    original = getattr(owner, name)
    def call(*values, **options):
        counts[key] += 1
        return original(*values, **options)
    setattr(owner, name, call)

def shot(name):
    """Nur das bereits sichtbare Fenster erfassen, niemals den Renderer anstoßen."""
    pixmap = window.screen().grabWindow(window.winId())
    if pixmap.isNull():
        raise RuntimeError("Die native Fensteraufnahme ist leer")
    pixmap.save(str(OUT / f"{name}.png"))
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    array = np.frombuffer(image.bits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    return array[:, :image.width()*4].reshape(image.height(), image.width(), 4)[:, :, :3].copy()

def rectangle(widget):
    point = renderer.widget.mapFromGlobal(widget.mapToGlobal(QPoint()))
    ratio = renderer.widget.devicePixelRatioF()
    return [point.x()*ratio, point.y()*ratio,
            (point.x()+widget.width())*ratio, (point.y()+widget.height())*ratio]

def projection():
    """Originale Netzecken und Hüllquader nur mit der aktuellen Kamera projizieren."""
    raw = window.session.last_result.scene.objects[oid].mesh.raw
    low, high = np.asarray(raw.bounds)
    corners = np.asarray(list(itertools.product(*zip(low, high))))
    shift = view._shown_offset(window.session.last_result.scene.objects[oid], view._result)
    projected = np.asarray([renderer.world_to_display(tuple(point + shift)) for point in corners])
    vertices = np.asarray([renderer.world_to_display(tuple(point + shift)) for point in raw.vertices])
    width, height = renderer.view_size()
    ratio = renderer.widget.devicePixelRatioF()
    left, right, bottom = view._zone_margins
    free = np.asarray([left*ratio, 0, width-right*ratio, height-bottom*ratio])
    def box(points):
        return np.r_[points[:, :2].min(axis=0), points[:, :2].max(axis=0)]
    bounds_box, mesh_box = box(projected), box(vertices)
    return {"bounds_world": [low.tolist(), high.tolist()], "projected_bounds_corners": projected.tolist(),
            "bounds_box": bounds_box.tolist(), "mesh_box": mesh_box.tolist(), "free_rect": free.tolist(),
            "zone_margins": list(view._zone_margins), "canvas_size": [width, height],
            "analysis_visible": window.analysis_bar.isVisible(),
            "analysis_rect": rectangle(window.analysis_bar) if window.analysis_bar.isVisible() else None,
            "bottom_zone_rect": rectangle(window.overlay.bottom),
            "mesh_exceeds_free_rect": bool(np.any(mesh_box[:2] < free[:2]) or np.any(mesh_box[2:] > free[2:]))}

def image_delta(before, after):
    """Nur die mittlere freie Canvasfläche vergleichen; Menütexte und Cursor sind außerhalb."""
    ratio = renderer.widget.devicePixelRatioF()
    at = renderer.widget.mapTo(window, QPoint())
    left, right, bottom = view._zone_margins
    x0, x1 = round((at.x()+left+8)*ratio), round((at.x()+renderer.widget.width()-right-8)*ratio)
    y0, y1 = round((at.y()+8)*ratio), round((at.y()+renderer.widget.height()-bottom-8)*ratio)
    first, second = before[y0:y1, x0:x1], after[y0:y1, x0:x1]
    if first.shape != second.shape or not first.size:
        raise RuntimeError("Die Bildvergleichsfläche ist nicht stabil")
    delta = np.max(np.abs(first.astype(int)-second.astype(int)), axis=2)
    return {"rect": [x0, y0, x1, y1], "changed_pixels": int(np.count_nonzero(delta > 8)),
            "max_channel_delta": int(delta.max()), "mean_max_delta": float(delta.mean())}

try:
    pump(.4)
    window.session.open_project(args.project)
    end = time.perf_counter() + 60
    while window.session.last_result is None or view._scene_worker is not None:
        if time.perf_counter() > end:
            raise RuntimeError("Peg-Aufbau hat keinen Abschluss geliefert")
        pump(.02)
    pump(.8)
    renderer = view.renderer
    if app.platformName() != "windows" or renderer is None or not renderer.widget.isVisible():
        raise RuntimeError("Kein sichtbarer Windows-Renderer")
    oid = next(iter(window.session.last_result.scene.objects))
    window.object_tree.select_object(oid)
    view.select(oid)
    view.select_feature(None)
    view.set_feature_overlay(False)
    pump(.3)
    base_pose = view.camera_pose()
    wrap(renderer, "render", "renderer_render")
    if args.renderer == "gfx":
        wrap(renderer._renderer, "render", "actual_wgpu_pass")
    else:
        renderer.window.AddObserver("StartEvent", lambda *_: counts.update(["actual_vtk_render"]))
    fit_action = next(a for a in window._display_actions if a.shortcut().toString() == "Home")
    fit_action.triggered.connect(lambda *_: counts.update(["fit_action_triggered"]))
    for opened in (False, True):
        name = "analysis-open" if opened else "analysis-closed"
        button = window.tools._buttons["analysis"]
        camera_before_card = dataclasses.asdict(renderer.camera_pose())
        if button.isChecked() != opened:
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        pump(.4)
        camera_after_card = dataclasses.asdict(renderer.camera_pose())
        position, focal, up, scale = base_pose
        near = tuple(np.asarray(focal) + (np.asarray(position)-focal)/1.7)
        view.set_camera_pose(near, focal, up, scale/1.7 if scale is not None else None)
        QTest.mouseMove(window.menuBar(), QPoint(800, 10))
        renderer.widget.setFocus(Qt.FocusReason.OtherFocusReason)
        pump(.3)
        before = shot(name + "-before-pos1")
        row = {"analysis_open": opened, "camera_before_card": camera_before_card,
               "camera_after_card": camera_after_card, "camera_before": dataclasses.asdict(renderer.camera_pose()),
               "before_projection": projection(), "action_enabled": fit_action.isEnabled(),
               "window_active": window.isActiveWindow()}
        counts.clear()
        QTest.keyClick(window, Qt.Key.Key_Home)
        row["immediate_counts"] = dict(counts)
        pump(.3)
        row["settled_counts"] = dict(counts)
        after = shot(name + "-after-pos1")
        row["camera_after"] = dataclasses.asdict(renderer.camera_pose())
        row["after_projection"] = projection()
        row["image_delta"] = image_delta(before, after)
        # Erst jetzt ist die Frage nach dem selbst ausgelösten Bild abgeschlossen.
        # Der getrennte Diagnoseaufruf zeigt die eventuell bislang unsichtbare Kamera.
        renderer.render()
        pump(.1)
        revealed = shot(name + "-after-explicit-diagnostic-render")
        row["diagnostic_render_delta"] = image_delta(after, revealed)
        result["checks"].append(row)
        (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "checks": len(result["checks"])}))
finally:
    window.session._dirty = False
    shutdown_window(window, app)
    watchdog.cancel()
    faulthandler.cancel_dump_traceback_later()
