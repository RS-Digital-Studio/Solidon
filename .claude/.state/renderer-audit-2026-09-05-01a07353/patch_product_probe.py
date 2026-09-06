"""Vergleicht ausschließlich private Markierungskontrollen am gespeicherten Counter-Projekt."""
from __future__ import annotations
import argparse, faulthandler, json, os, sys, threading, time, types
from pathlib import Path

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--renderer", choices=("gfx","vtk"), required=True)
args = parser.parse_args()
SOURCE = HERE / "patch-source-v6-fixed"
OUT = HERE / "patch-product-v6-fixed" / args.renderer
OUT.mkdir(parents=True, exist_ok=True)
sys.stdout = (OUT / "run.log").open("w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
faulthandler.enable()
faulthandler.dump_traceback_later(120, repeat=True)
watchdog = threading.Timer(240, lambda: os._exit(124))
watchdog.daemon = True
watchdog.start()
sys.path.insert(0, str(SOURCE))
os.environ["SOLIDON_RENDERER"] = args.renderer
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
    reference = json.loads((HERE / "patch-probe-v6-followup/result.json").read_text())
    view.set_camera_pose(*reference["camera"])
    QTest.mouseMove(window.menuBar(), QPoint(800, 10))
    pump(.4)
    first = shot("00-product")
    view._redraw_feature_patch()
    view._draw()
    pump(.2)
    second = shot("01-product-repeated")
    result.update({"renderer":args.renderer, "camera":view.camera_pose(), "canvas":renderer.view_size(), "feature":window.feature_panel.feature_id, "patch_faces":len(view.highlighted_faces()), "repeat_changed_pixels":int(np.count_nonzero(np.max(np.abs(first.astype(int)-second.astype(int)),axis=2)>3)), "status":"complete"})
    (OUT / "result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result),flush=True)
finally:
    window.session._dirty = False
    shutdown_window(window, app)
    watchdog.cancel()
    faulthandler.cancel_dump_traceback_later()
