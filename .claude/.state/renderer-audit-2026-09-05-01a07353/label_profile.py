"""Begrenzt den nativen Peg-Vergleich auf zwei Orbitreihen und reine Zeitwrapper."""
from __future__ import annotations
import argparse, collections, faulthandler, json, math, os, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, default=HERE / "final-source-v5")
parser.add_argument("--output", default="label-profile-v5")
args = parser.parse_args()
OUT = HERE / args.output
OUT.mkdir(exist_ok=True)
sys.stdout = (OUT / "run.log").open("w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
faulthandler.enable()
faulthandler.dump_traceback_later(90, repeat=True)
watchdog = threading.Timer(180, lambda: os._exit(124))
watchdog.daemon = True
watchdog.start()
sys.path.insert(0, str(args.source.resolve()))
os.environ["SOLIDON_RENDERER"] = "gfx"
os.environ.pop("QT_QPA_PLATFORM", None)
for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    os.environ[key] = str(OUT / "profile" / key)

import numpy as np
import wgpu
from PySide6.QtCore import QCoreApplication, QEvent
from app.core.bootstrap import load_operations
from app.ui.settings import UiSettings, save_settings
save_settings(UiSettings(first_run_done=True, language="de", check_for_updates=False))
load_operations()
from app.ui.app import build_application
from app.ui.render.gfx_renderer import GfxLabels
from app.ui import viewport as viewport_module
from tools.window_bench import shutdown_window
from run_context import cpu_context, cpu_snapshot

app, window = build_application(["solidon-label-profile"])
window.resize(1600, 1000)
window.show()
view = window.viewport
rows = []
active = None

def pump(seconds=0):
    end = time.perf_counter() + seconds
    while True:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        if time.perf_counter() >= end:
            break
        time.sleep(.002)

def timed(owner, name, key):
    original = getattr(owner, name)
    def call(*values, **options):
        start = time.perf_counter()
        extra = None
        if active is not None and key == "label_build":
            extra = {"before": list(values[0].labels), "after": list(values[2])}
        try:
            return original(*values, **options)
        finally:
            if active is not None:
                active["calls"][key].append((time.perf_counter() - start) * 1000)
                if extra is not None:
                    active["builds"].append(extra)
    setattr(owner, name, call)

try:
    pump(.4)
    window.session.open_project(HERE / "final/gfx/file-09/bearbeitung-geprueft.p3d")
    end = time.perf_counter() + 60
    while window.session.last_result is None or view._scene_worker is not None:
        if time.perf_counter() > end:
            raise RuntimeError("Peg-Aufbau hat keinen Abschluss geliefert")
        pump(.02)
    pump(.8)
    oid = next(iter(window.session.last_result.scene.objects))
    window.object_tree.select_object(oid)
    view.select(oid)
    view.select_feature(None)
    if not window.tools._buttons["analysis"].isChecked():
        window.tools._buttons["analysis"].click()
    pump(.3)
    renderer = view.renderer
    pose = view.camera_pose()
    result = {"source": str(args.source), "feature_count": len(view._features_of_selection()),
              "size": renderer.view_size(), "pose": pose, "rows": rows, "phases": []}
    timed(view, "_layout_feature_labels", "layout_total")
    timed(view, "_refresh_feature_label_layout", "queued_refresh")
    timed(view, "_sync_feature_preview", "preview_sync")
    timed(viewport_module, "layout_feature_labels", "collision_layout")
    timed(GfxLabels, "build", "label_build")
    timed(GfxLabels, "update_labels", "label_update")
    timed(GfxLabels, "fit_fields", "fit_fields")
    timed(renderer, "_draw", "renderer_draw")
    timed(renderer._renderer, "render", "wgpu_render")
    timed(renderer, "world_to_display", "project")
    timed(renderer, "display_to_world", "unproject")
    original_render = renderer.render
    device = renderer._renderer._device
    buffer = device.create_buffer(size=4, usage=wgpu.BufferUsage.COPY_SRC | wgpu.BufferUsage.COPY_DST)
    def complete():
        began = time.perf_counter()
        original_render()
        submitted = time.perf_counter()
        device.queue.write_buffer(buffer, 0, b"\0\0\0\0")
        device.queue.read_buffer(buffer)
        if active is not None:
            active["calls"]["render_submit"].append((submitted - began) * 1000)
            active["calls"]["fence"].append((time.perf_counter() - submitted) * 1000)
    renderer.render = complete
    for enabled in (False, True):
        view.set_feature_overlay(enabled)
        pump(.3)
        view.set_camera_pose(*pose)
        pump(.1)
        context = cpu_snapshot()
        position, focal, _up, _scale = pose
        offset = np.asarray(position) - focal
        radius = math.hypot(offset[0], offset[1])
        base = math.atan2(offset[1], offset[0])
        for frame in range(12):
            angle = base + 2 * math.pi * (frame + 1) / 12
            moved = (focal[0] + radius * math.cos(angle), focal[1] + radius * math.sin(angle), focal[2] + offset[2])
            row = {"overlay": enabled, "frame": frame, "calls": collections.defaultdict(list), "builds": []}
            active = row
            began = time.perf_counter()
            view.set_camera_pose(moved, focal, (0, 0, 1))
            pump()
            row["frame_ms"] = (time.perf_counter() - began) * 1000
            active = None
            row["labels"] = list(view._feature_text_item.labels) if view._feature_text_item else []
            row["objects"] = len(view._feature_text_item.objects) if view._feature_text_item else 0
            rows.append(row)
        result["phases"].append({"overlay": enabled, "cpu": cpu_context(context)})
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "features": result["feature_count"], "size": result["size"]}))
finally:
    active = None
    window.session._dirty = False
    shutdown_window(window, app)
    watchdog.cancel()
    faulthandler.cancel_dump_traceback_later()
