"""Native Einzelprobe: letzter Counter-Schichtanker und Kanten beim gehaltenen Zug.

Nur nach exklusiver Slotfreigabe ausführen. Gespeichertes Projekt und bereits
errechnete Cacheeinträge bleiben unverändert; Undo nimmt nur die Prüfgeste zurück.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import faulthandler
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--renderer", choices=("gfx", "vtk"), required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
SOURCE = args.source.resolve()
OUT = args.output.resolve()
if not OUT.is_relative_to(ROOT) or OUT.exists():
    raise RuntimeError("Die Probe braucht einen neuen Ausgabeordner unter dem Auditordner")
OUT.mkdir(parents=True)
sys.stdout = (OUT / "run.log").open("w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
faulthandler.enable()
faulthandler.dump_traceback_later(90, repeat=True)
watchdog = threading.Timer(240, lambda: os._exit(124))
watchdog.daemon = True
watchdog.start()
helpers = ROOT / "anchor-edge-probe-helpers-v1"
pins = json.loads((helpers / "pins.json").read_text(encoding="utf-8"))
for name in ("feature_checks.py", "gesture_checks.py", "analysis_checks.py", "menu_driver.py"):
    if hashlib.sha256((helpers / name).read_bytes()).hexdigest() != pins[name]:
        raise RuntimeError(f"Helferpin wurde verändert: {name}")
if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != pins["anchor_edge_probe.py"]:
    raise RuntimeError("Die vorbereitete Sonde wurde nach dem Pinnen geändert")
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(helpers))
os.chdir(SOURCE)
os.environ["SOLIDON_RENDERER"] = args.renderer
os.environ.pop("QT_QPA_PLATFORM", None)
for name in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    os.environ[name] = str(OUT / "profile" / name)

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView, QScrollArea, QTreeWidgetItemIterator

from app.core.bootstrap import load_operations
from app.core.paths import results_cache_dir
from app.ui.settings import UiSettings, save_settings

project = ROOT / "final/gfx/file-18/bearbeitung-geprueft.p3d"
reference_path = project.parent / "result.json"
reference = json.loads(reference_path.read_text(encoding="utf-8"))
expected_geometry = next(row["fingerprint"] for row in reference["checks"] if row.get("label") == "Export-Ausgangsszene")
cache_versions = list((project.parent / "profile/LOCALAPPDATA/RS Digital/Solidon3D/cache/results").iterdir())
if len(cache_versions) != 1 or not cache_versions[0].is_dir():
    raise RuntimeError("Der bewiesene Countercache ist nicht eindeutig")
cache_source = cache_versions[0]
cache_target = results_cache_dir().resolve()
if not cache_target.is_relative_to(OUT):
    raise RuntimeError("Cacheziel verlässt das isolierte Prüfprofil")
cache_inputs = {str(p.relative_to(cache_source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(cache_source.rglob("*")) if p.is_file()}
shutil.copytree(cache_source, cache_target, dirs_exist_ok=True)
QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
save_settings(UiSettings(first_run_done=True, language="de", check_for_updates=False))
load_operations()
from app.ui.app import build_application
from app.ui.labels import feature_label
from tools.window_bench import shutdown_window
import analysis_checks
import feature_checks
import gesture_checks
import menu_driver

source_hashes = {str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((SOURCE / "app").rglob("*.py"))}
app, window = build_application(["solidon-anker-kanten-gegenprobe"])
session = window.session
view = window.viewport
results = {
    "status": "running", "closed": False, "renderer": args.renderer,
    "source_directory": str(SOURCE), "source_files_sha256": source_hashes,
    "helper_pins": pins, "project": str(project),
    "project_sha256": hashlib.sha256(project.read_bytes()).hexdigest(),
    "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
    "cache_source": str(cache_source), "cache_target": str(cache_target),
    "cache_inputs_sha256": cache_inputs, "checks": [], "screenshots": [],
    "platform": app.platformName(), "run_id": os.environ.get("SOLIDON_AUDIT_RUN_ID"),
    "scope": "Letzte Schicht, reale Flächenmarker und ein Körperzug mit Konturen/Undo; kein Vollmodell- oder Leistungsdurchlauf",
}
errors = []
edge_stages = {}
edge_buffers = {}

# PINNED_UI_FUNCTIONS


def edge_state(stage):
    """Echte getrennte Linienpuffer und ihre tatsächliche Transformation lesen."""
    states = {}
    buffers = {}
    for oid, edge in view._edge_actors.items():
        points = gesture_checks._points(edge)
        body = view._actors.get(oid)
        state = gesture_checks._item_state(edge)
        body_state = gesture_checks._item_state(body)
        sample = points[np.linspace(0, len(points) - 1, min(24, len(points)), dtype=int)]
        homogeneous = np.column_stack((sample, np.ones(len(sample))))
        actual_world = (homogeneous @ state["matrix"].T)[:, :3] + state["position"]
        actual_screen = [view.renderer.world_to_display(tuple(point)) for point in actual_world]
        states[str(oid)] = {
            **state, "body": body_state, "point_count": len(points),
            "buffer_sha256": hashlib.sha256(points.tobytes()).hexdigest(),
            "world_sample": actual_world, "device_sample": actual_screen,
            "same_matrix_as_body": bool(np.allclose(state["matrix"], body_state["matrix"], rtol=0, atol=1e-12)),
            "same_position_as_body": bool(np.allclose(state["position"], body_state["position"], rtol=0, atol=1e-12)),
        }
        buffers[str(oid)] = points
    edge_stages[stage] = states
    edge_buffers[stage] = buffers
    results["edge_stages"] = plain(edge_stages)


def shot(name):
    """Native Fensterpixel erfassen; davor ausschließlich bereits eingereihte Bilder abwarten."""
    if name.startswith("gesture-body-"):
        edge_state(name)
    if args.renderer == "gfx":
        view.renderer._renderer._device.queue.on_submitted_work_done_sync()
    else:
        view.renderer.window.WaitForCompletion()
    pixmap = window.screen().grabWindow(window.winId())
    if pixmap.isNull() or not pixmap.save(str(OUT / (name + ".png"))):
        raise RuntimeError("Das native Bildschirmfoto konnte nicht gespeichert werden")
    results["screenshots"].append(name + ".png")
    write()


def witness_on_triangle(raw, indices, point, tolerance):
    """Baryzentrische Zugehörigkeit unabhängig von Ankerwahl und Clipalgorithmus prüfen."""
    for offset in range(0, len(indices), 32768):
        cells = np.asarray(indices[offset:offset + 32768], dtype=np.int64)
        triangles = np.asarray(raw.vertices[raw.faces[cells]], dtype=float)
        a = triangles[:, 1] - triangles[:, 0]
        b = triangles[:, 2] - triangles[:, 0]
        normal = np.cross(a, b)
        normal_size = np.linalg.norm(normal, axis=1)
        delta = np.asarray(point) - triangles[:, 0]
        distance = np.divide(np.abs(np.einsum("ij,ij->i", delta, normal)), normal_size, out=np.full(len(cells), np.inf), where=normal_size > 1e-15)
        aa = np.einsum("ij,ij->i", a, a)
        ab = np.einsum("ij,ij->i", a, b)
        bb = np.einsum("ij,ij->i", b, b)
        da = np.einsum("ij,ij->i", delta, a)
        db = np.einsum("ij,ij->i", delta, b)
        determinant = aa * bb - ab * ab
        u = np.divide(bb * da - ab * db, determinant, out=np.full(len(cells), np.inf), where=determinant > 1e-24)
        v = np.divide(aa * db - ab * da, determinant, out=np.full(len(cells), np.inf), where=determinant > 1e-24)
        valid = (distance <= tolerance) & (u >= -1e-7) & (v >= -1e-7) & (u + v <= 1 + 1e-7)
        accepted = np.flatnonzero(valid)
        if len(accepted):
            index = int(accepted[0])
            return {"cell": int(cells[index]), "distance_mm": float(distance[index]), "barycentric": [float(1-u[index]-v[index]), float(u[index]), float(v[index])], "triangle": triangles[index].tolist()}
    return None


def check_last_anchors(oid):
    """Ausgegebene Marker müssen in einem Originaldreieck UND im sichtbaren Rest liegen."""
    entry = session.last_result.scene.objects[oid]
    raw = entry.mesh.raw
    tolerance = max(1e-7, float(np.linalg.norm(np.ptp(raw.vertices, axis=0))) * 1e-9)
    marker_points = gesture_checks._points(view._feature_marker_item)
    labels = {}
    for fid, feature in entry.features.items():
        if feature.kind == "face":
            labels.setdefault(feature_label(fid, feature), []).append((fid, feature))
    rows = []
    for index, ((shown, text, priority), owner) in enumerate(zip(view._feature_label_data, view._feature_label_owners, strict=True)):
        if owner != oid or text not in labels:
            continue
        candidates = labels[text]
        if len(candidates) != 1:
            raise AssertionError("Das Flächenetikett lässt keine eindeutige unabhängige Merkmalszuordnung zu")
        fid, feature = candidates[0]
        point = np.asarray(shown) - np.asarray(view._shown_offset(entry, view._result))
        witness = witness_on_triangle(raw, feature.face_indices, point, tolerance)
        on_plane = abs(point[2] - view._layer.z) <= tolerance
        in_rest = point[2] <= view._layer.z + tolerance
        marker_matches = bool(np.allclose(marker_points[index], shown, rtol=0, atol=tolerance))
        passed = witness is not None and in_rest and (priority < 2 or on_plane) and marker_matches
        rows.append({"feature": str(fid), "text": text, "priority": priority, "point": point.tolist(), "witness": witness, "on_layer_plane": bool(on_plane), "inside_visible_halfspace": bool(in_rest), "renderer_marker_matches": marker_matches, "passed": passed})
    if len(rows) < 2:
        raise AssertionError(f"Die letzte Schicht zeigt nur {len(rows)} zugeordnete Flächenmarker")
    log("Letzte Schicht: echte Flächenanker", status="passed" if all(row["passed"] for row in rows) else "failed", rows=rows, layer_z=float(view._layer.z), tolerance_mm=tolerance, note="Dreieckszugehörigkeit plus Halbraum beweist den sichtbaren konvexen Rest; Textanker werden nicht als Flächenpunkt gewertet.")
    return all(row["passed"] for row in rows)


def check_edges():
    before = edge_stages.get("gesture-body-before", {})
    held = edge_stages.get("gesture-body-held-preview", {})
    undo = edge_stages.get("gesture-body-after-undo", {})
    rows = []
    for oid, original in before.items():
        preview = held.get(oid)
        restored = undo.get(oid)
        if preview is None or restored is None:
            rows.append({"object": oid, "passed": False, "reason": "Kantenaktor fehlt in einem Zustand"})
            continue
        device_before = np.asarray(original["device_sample"])
        device_held = np.asarray(preview["device_sample"])
        displacement = float(np.max(np.linalg.norm((device_held - device_before)[:, :2], axis=1)))
        checks = {
            "edge_visible_while_held": preview["visible"],
            "edge_follows_body_matrix": preview["same_matrix_as_body"],
            "edge_follows_body_position": preview["same_position_as_body"],
            "original_line_buffer_unchanged_while_held": original["buffer_sha256"] == preview["buffer_sha256"],
            "edge_visibly_displaced": displacement > 4 * view.renderer.widget.devicePixelRatioF(),
            "undo_restores_line_geometry": gesture_checks._same_points(edge_buffers["gesture-body-before"][oid], edge_buffers["gesture-body-after-undo"][oid]),
            "undo_restores_transform": gesture_checks._same_points(original["matrix"], restored["matrix"]) and gesture_checks._same_points(original["position"], restored["position"]),
        }
        rows.append({"object": oid, "device_displacement": displacement, "checks": checks, "passed": all(checks.values())})
    passed = bool(rows) and all(row["passed"] for row in rows)
    log("Getrennte Kanten beim echten Körperzug", status="passed" if passed else "failed", rows=rows, screenshot_review_required=True)
    return passed


probe = sys.modules[__name__]
menu_driver.install(probe)
window.resize(1600, 1000)
window.show()
window.activateWindow()
try:
    settle(400)
    session.open_project(project)
    wait("Gespeichertes Counterprojekt aufgebaut", lambda: session.last_result is not None and not session.busy and view._scene_worker is None, 120)
    actual_geometry = feature_checks.fingerprint(probe)["hash"]
    if actual_geometry != expected_geometry:
        raise AssertionError(f"Geladene Geometrie weicht vom nativen Referenzfingerprint ab: {actual_geometry} != {expected_geometry}")
    log("Vorhandenes Counterprojekt verifiziert", fingerprint=actual_geometry, cache_statistics=plain(session.cache.statistics))
    oid = next(iter(session.last_result.scene.objects))
    select_item(feature_checks._item(probe, oid))
    gesture_checks._automatic_labels(probe, True)
    QTest.keyClick(view.renderer.widget, Qt.Key.Key_Home)
    settle(300)
    camera_before_layers = view.camera_pose()
    shot("00-all-features")
    document_before = gesture_checks._document(probe)
    click(window.tools._buttons["layers"])
    wait("Schichtanalyse fertig", lambda: window._slice_worker is None and window._slice_pending is None and window.layer_bar._result is not None, 90)
    bar = window.layer_bar
    analysis_checks._layer_position(probe, bar.slider, bar.slider.maximum())
    wait("Letzte Schicht gezeichnet", lambda: view._layer is bar._result.layers[-1] and not view._layer_rebuild.isActive() and view._scene_worker is None, 45)
    QTest.mouseMove(window.menuBar(), QPoint(800, 10))
    settle(350)
    anchors_ok = check_last_anchors(oid)
    shot("01-last-layer-face-anchors")
    log("Letzte Schicht über Regler", index=bar.slider.value(), layer_count=len(bar._result.layers), readout=bar.readout.text(), camera=view.camera_pose(), document_unchanged=gesture_checks._document(probe) == document_before)
    click(window.tools._buttons["layers"])
    wait("Schichtansicht geschlossen", lambda: view._layer is None and not view._layer_rebuild.isActive() and view._scene_worker is None, 45)
    QTest.keyClick(view.renderer.widget, Qt.Key.Key_Home)
    settle(300)
    gesture = gesture_checks.run(probe)
    edges_ok = check_edges()
    results["anchor_passed"] = anchors_ok
    results["edge_passed"] = edges_ok
    results["gesture_status"] = gesture["status"]
    results["geometry_restored"] = feature_checks.fingerprint(probe)["hash"] == expected_geometry
    results["status"] = "complete" if anchors_ok and edges_ok and results["geometry_restored"] and gesture["status"] == "passed" else "failed"
except Exception:
    results["status"] = "failed"
    results["error"] = traceback.format_exc()
    print(results["error"], flush=True)
finally:
    write()
    try:
        session._dirty = False
        shutdown_window(window, app)
        pump_events()
        results["closed"] = not window.isVisible()
        results["source_unchanged"] = all(hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == digest for name, digest in source_hashes.items())
        results["project_unchanged"] = hashlib.sha256(project.read_bytes()).hexdigest() == results["project_sha256"]
        results["cache_source_unchanged"] = all(hashlib.sha256((cache_source / name).read_bytes()).hexdigest() == digest for name, digest in cache_inputs.items())
        if not all(results[name] for name in ("closed", "source_unchanged", "project_unchanged", "cache_source_unchanged")):
            results["status"] = "failed"
    finally:
        write()
        watchdog.cancel()
        faulthandler.cancel_dump_traceback_later()
raise SystemExit(0 if results["status"] == "complete" and results["closed"] else 1)
