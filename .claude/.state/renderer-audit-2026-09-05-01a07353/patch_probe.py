"""Vergleicht ausschließlich private Markierungskontrollen am gespeicherten Counter-Projekt."""
from __future__ import annotations
import faulthandler, json, os, sys, threading, time, types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "final-source-v6"
OUT = HERE / "patch-probe-v6"
OUT.mkdir(exist_ok=True)
sys.stdout = (OUT / "run.log").open("w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
faulthandler.enable()
faulthandler.dump_traceback_later(120, repeat=True)
watchdog = threading.Timer(240, lambda: os._exit(124))
watchdog.daemon = True
watchdog.start()
sys.path.insert(0, str(SOURCE))
os.environ["SOLIDON_RENDERER"] = "gfx"
os.environ.pop("QT_QPA_PLATFORM", None)
for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    os.environ[key] = str(OUT / "profile" / key)

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTreeWidgetItemIterator, QAbstractItemView
from app.core.bootstrap import load_operations
from app.ui.settings import UiSettings, save_settings
save_settings(UiSettings(first_run_done=True, language="de", check_for_updates=False))
load_operations()
from app.ui.app import build_application
from tools.window_bench import shutdown_window

app, window = build_application(["solidon-patch-probe"])
window.resize(1600, 1000)
window.show()
window.activateWindow()
view = window.viewport
result = {"source": str(SOURCE), "platform": app.platformName(), "checks": []}

def pump(seconds=0):
    end = time.perf_counter() + seconds
    while True:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        if time.perf_counter() >= end:
            break
        time.sleep(.002)

def shot(name):
    pixmap = window.screen().grabWindow(window.winId())
    assert not pixmap.isNull()
    pixmap.save(str(OUT / f"{name}.png"))
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    return np.frombuffer(image.bits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())[:, :image.width()*4].reshape(image.height(), image.width(), 4).copy()

def choose_feature(oid, fid):
    tree = window.object_tree.tree
    iterator = QTreeWidgetItemIterator(tree)
    while iterator.value():
        item = iterator.value()
        if item.data(0, Qt.ItemDataRole.UserRole) == oid and item.data(1, Qt.ItemDataRole.UserRole) == fid:
            parent = item.parent()
            while parent:
                parent.setExpanded(True)
                parent = parent.parent()
            tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
            pump(.2)
            rectangle = tree.visualItemRect(item).intersected(tree.viewport().rect())
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rectangle.center())
            pump(.4)
            assert window.feature_panel.feature_id == fid
            window.feature_dock.show()
            pump(.3)
            return
        iterator += 1
    raise AssertionError("face_1 fehlt im vorhandenen Projektbaum")

try:
    pump(.4)
    project = HERE / "preflight-v6/gfx/file-18/bearbeitung-geprueft.p3d"
    result["project"] = str(project)
    window.session.open_project(project)
    end = time.perf_counter() + 120
    while window.session.last_result is None or window.session.busy or view._scene_worker is not None:
        if time.perf_counter() > end:
            raise RuntimeError("Das gespeicherte Counter-Projekt wurde nicht fertig aufgebaut")
        pump(.02)
    pump(.7)
    oid, entry = next(iter(window.session.last_result.scene.objects.items()))
    choose_feature(oid, "face_1")
    renderer = view.renderer
    original = view._lifted_corners
    raw = entry.mesh.raw
    chosen = np.asarray(entry.features["face_1"].face_indices, dtype=np.int64)
    normals = np.asarray(raw.face_normals)[chosen]
    corners = np.asarray(raw.vertices)[np.asarray(raw.faces)[chosen].reshape(-1)]
    lift = view._patch_lift()
    unique, inverse = np.unique(corners, axis=0, return_inverse=True)
    displacement = np.repeat(normals, 3, axis=0) * lift
    low = np.full((len(unique), 3), np.inf)
    high = np.full((len(unique), 3), -np.inf)
    np.minimum.at(low, inverse, displacement)
    np.maximum.at(high, inverse, displacement)
    span = np.linalg.norm(high-low, axis=1)
    result.update({"feature_faces": len(chosen), "normal_groups_4": len(np.unique(normals.round(4),axis=0)),
                   "lift_mm": lift, "split_original_positions": int(np.count_nonzero(span>1e-7)),
                   "max_displacement_box_diagonal_mm": float(span.max()), "canvas": renderer.view_size(),
                   "camera": view.camera_pose()})
    QTest.mouseMove(window.menuBar(), QPoint(800, 10))
    pump(.3)
    reference = shot("00-original")

    def zero(self, raw, chosen, lift, offset):
        return original(raw, chosen, 0.0, offset)

    def grouped(self, raw, chosen, lift, offset):
        tri = np.asarray(raw.faces)[chosen]
        ns = np.asarray(raw.face_normals)[chosen].copy()
        major = np.argmax(np.abs(ns), axis=1)
        keys = major*2 + (ns[np.arange(len(ns)), major] < 0)
        for key in np.unique(keys):
            indices = keys == key
            mean = np.sum(ns[indices] * np.asarray(raw.area_faces)[chosen][indices, None],axis=0)
            mean /= np.linalg.norm(mean)
            ns[indices] = mean
        return self._clip_feature_corners(self._lift_within_section(np.asarray(raw.vertices)[tri.reshape(-1)], np.repeat(ns,3,axis=0)*lift)) + offset

    def control(name, method, depth):
        view._lifted_corners = types.MethodType(method, view) if method else original
        view._redraw_feature_patch()
        patch = view._feature_patch
        for obj in patch.objects:
            obj.material.depth_test = depth
        view._draw()
        pump(.3)
        image = shot(name)
        delta = np.max(np.abs(image.astype(int)-reference.astype(int)),axis=2)
        result["checks"].append({"name": name, "depth_test": depth, "pixels_changed_vs_original": int(np.count_nonzero(delta>3))})
        print(name, flush=True)
        (OUT/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")

    control("01-zero-lift", zero, True)
    control("02-original-no-depth", None, False)
    control("03-grouped-normal", grouped, True)
    control("04-grouped-normal-no-depth", grouped, False)
    control("05-original-restored", None, True)
    print(json.dumps({"status":"complete", "checks":len(result["checks"])}),flush=True)
finally:
    window.session._dirty = False
    shutdown_window(window, app)
    watchdog.cancel()
    faulthandler.cancel_dump_traceback_later()
