"""Prüft beide Renderer an Roberts Dateien über das sichtbare Windows-Fenster."""
from __future__ import annotations
import argparse, collections, dataclasses, faulthandler, hashlib, importlib.metadata
import json, os, sys, threading, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--index", type=int, required=True)
parser.add_argument("--renderer", choices=("gfx","vtk"), required=True)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--phase", default="baseline")
parser.add_argument("--full", action="store_true")
parser.add_argument("--gesture-only", action="store_true")
args = parser.parse_args()
SOURCE = args.source.resolve()
OUT = ROOT / args.phase / args.renderer / f"file-{args.index:02d}"
OUT.mkdir(parents=True, exist_ok=True)
sys.stdout = (OUT / "run.log").open("w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout
faulthandler.enable()
faulthandler.dump_traceback_later(120, repeat=True)
watchdog = threading.Timer(900, lambda: os._exit(124))
watchdog.daemon = True
watchdog.start()
sys.path.insert(0, str(SOURCE))
os.chdir(SOURCE)
os.environ["SOLIDON_RENDERER"] = args.renderer
os.environ.pop("QT_QPA_PLATFORM", None)
for variable in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    os.environ[variable] = str(OUT / "profile" / variable)
import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QAbstractButton, QAbstractSpinBox,
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QScrollArea, QTreeWidgetItemIterator, QVBoxLayout)
from shiboken6 import isValid
QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
from app.core.bootstrap import load_operations
from app.ui.settings import UiSettings, save_settings
save_settings(UiSettings(first_run_done=True, language="de", check_for_updates=False))
load_operations()
from app.ui.app import build_application
from app.core.registry import REGISTRY
from tools.window_bench import working_set_mb, drag_frames, shutdown_window
started = time.perf_counter()
app, window = build_application(["solidon-renderer-prüfung"])
session = window.session
entry = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))[args.index-1]
results = {"index": args.index, "renderer": args.renderer, "phase": args.phase,
    "run_id": os.environ.get("SOLIDON_AUDIT_RUN_ID"),
    "probe_files_sha256": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        for name in ("probe.py", "probe_template.py", "probe_helpers.py.inc", "helper-pins.json", "menu_driver.py", "feature_checks.py", "general_checks.py", "analysis_checks.py", "run_context.py", "gesture_checks.py", "stl_export_checks.py", "surface_pick_footprint.py")},
    "source_directory": str(SOURCE), "entry": entry, "full": args.full,
    "gesture_only": args.gesture_only,
    "platform": app.platformName(), "checks": [], "dialogs": [], "screenshots": [],
    "window_build_seconds": time.perf_counter()-started,
    "versions": {n: importlib.metadata.version(n) for n in
        ("numpy","trimesh","PySide6","vtk","pygfx","wgpu","rendercanvas")},
    "source_files_sha256": {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((SOURCE/"app").rglob("*.py"))}}
pending_file = None
pending_filter = None
handled_dialogs = set()
guard_active = False
last_heartbeat = 0.0
errors = []
dialog_timer = None

def plain(value):
    if dataclasses.is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [plain(v) for v in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)

def write():
    payload = json.dumps(results, ensure_ascii=False, indent=2)
    temporary = OUT / ("result-" + str(os.getpid()) + ".tmp")
    for attempt in range(20):
        try:
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(OUT / "result.json")
            return
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.05)

def log(label, **values):
    row = {"time": time.strftime("%H:%M:%S"), "label": label, **plain(values)}
    results["checks"].append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    write()

def pump_events():
    """Pumpt Qt einschließlich der ohne echte Ereignisschleife offenen Löschaufträge."""
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def settle(ms=150):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        pump_events()
        time.sleep(0.01)

def wait(label, condition, seconds=120):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        pump_events()
        if condition():
            settle(100)
            return
        time.sleep(0.02)
    modal = app.activeModalWidget()
    popup = app.activePopupWidget()
    log("Wartebedingung nicht erfüllt", status="probe_timeout", waiting_for=label, busy=session.busy, transactions=len(session.project.document.transactions) if session.project else None, undo_enabled=window.undo_action.isEnabled(), redo_enabled=window.redo_action.isEnabled(), modal=modal.windowTitle() if modal else None, popup=popup.windowTitle() if popup else None)
    raise TimeoutError(label)

def click(widget):
    for parent in window.findChildren(QScrollArea):
        if parent.isAncestorOf(widget):
            parent.ensureWidgetVisible(widget)
    settle(40)
    QTest.mouseMove(widget, widget.rect().center())
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=widget.rect().center())
    settle(80)

def guard():
    global pending_file, pending_filter, guard_active, last_heartbeat
    if guard_active:
        return
    if time.monotonic() - last_heartbeat > 15:
        last_heartbeat = time.monotonic()
        print("STATUS", time.strftime("%H:%M:%S"), "busy=", session.busy, "result=", session.last_result is not None, "text=", window.status_message.text(), flush=True)
    modal = app.activeModalWidget()
    if modal is None:
        return
    guard_active = True
    try:
        if isinstance(modal, QFileDialog) and pending_file is not None:
            destination = pending_file
            modal.setDirectory(str(destination.parent))
            if pending_filter is not None:
                matching = next((f for f in modal.nameFilters() if pending_filter.lower() in f.lower()), None)
                if matching:
                    modal.selectNameFilter(matching)
                pending_filter = None
            modal.selectFile(str(destination))
            edit = modal.findChild(QLineEdit, "fileNameEdit")
            if edit is not None:
                edit.setText(str(destination))
            settle(300)
            boxes = modal.findChildren(QDialogButtonBox)
            button = next((b for box in boxes for b in box.buttons() if box.buttonRole(b) == QDialogButtonBox.ButtonRole.AcceptRole), None)
            results["dialogs"].append({"type": "file", "title": modal.windowTitle(), "path": str(destination)})
            if button is not None:
                print("DATEIDIALOG", button.text(), button.isEnabled(), modal.selectedFiles(), flush=True)
                modal.screen().grabWindow(int(modal.winId())).save(str(OUT / "00-file-dialog.png"))
                if button.isEnabled():
                    pending_file = None
                    QTest.mouseClick(button, Qt.MouseButton.LeftButton, pos=button.rect().center())
            write()
        elif modal.__class__.__name__ == "AskDialog":
            labels = [v.text() for v in modal.findChildren(QLabel)]
            choices = [modal.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(modal.list.count())]
            preferred = next((i for i, c in enumerate(choices) if str(c).lower() == "mm"), 0)
            item = modal.list.item(preferred)
            QTest.mouseClick(modal.list.viewport(), Qt.MouseButton.LeftButton, pos=modal.list.visualItemRect(item).center())
            results["dialogs"].append({"type": "question", "labels": labels, "choices": choices, "chosen": choices[preferred]})
            QTest.mouseClick(modal._accept, Qt.MouseButton.LeftButton, pos=modal._accept.rect().center())
            write()
        elif isinstance(modal, QMessageBox):
            description = modal.text() + " " + modal.informativeText()
            buttons = modal.buttons()
            texts = [b.text() for b in buttons]
            results["dialogs"].append({"type": "message", "text": description, "buttons": texts})
            print("DIALOG", description, texts, flush=True)
            preferred = next((b for b in buttons if any(t in b.text().lower() for t in ("millimeter", "verwerfen", "schließen", "weiter", "ok"))), None)
            if preferred is None:
                preferred = next((b for b in buttons if modal.buttonRole(b) in (QMessageBox.ButtonRole.AcceptRole, QMessageBox.ButtonRole.YesRole)), None)
            if preferred is not None:
                QTest.mouseClick(preferred, Qt.MouseButton.LeftButton, pos=preferred.rect().center())
            write()
        elif modal.__class__.__name__ not in ("OperationDialog",):
            token = (modal.__class__.__name__, modal.windowTitle())
            if token not in handled_dialogs:
                handled_dialogs.add(token)
                labels = [v.text() for v in modal.findChildren(QLabel)]
                buttons = [b for b in modal.findChildren(QAbstractButton) if b.isVisible()]
                results["dialogs"].append({"type": token[0], "title": token[1], "labels": labels, "buttons": [b.text() for b in buttons]})
                print("UNBEKANNTER DIALOG", token, labels, [b.text() for b in buttons], flush=True)
                write()
    except Exception:
        print(traceback.format_exc(), flush=True)
    finally:
        try:
            pump_events()
        finally:
            guard_active = False

def scene_data():
    result = session.last_result
    if result is None:
        return None
    objects = []
    for oid, obj in result.scene.objects.items():
        mesh = obj.mesh
        features = {str(fid): {"kind": f.kind, "params": plain(f.params), "face_count": len(f.face_indices)} for fid, f in obj.features.items()}
        objects.append({"id": str(oid), "name": str(obj.name), "kind": obj.kind, "plate": obj.plate, "triangles": mesh.triangle_count, "bounds": [plain(mesh.bounds.minimum), plain(mesh.bounds.maximum)], "volume": float(mesh.volume), "watertight": bool(mesh.is_watertight), "components": mesh.component_count, "features": features})
    return {"objects": objects, "stopped_at": plain(result.stopped_at), "findings": plain(result.scene.report.findings)}

def tree_items():
    iterator = QTreeWidgetItemIterator(window.object_tree.tree)
    items = []
    while iterator.value():
        items.append(iterator.value())
        iterator += 1
    return items

def select_item(item):
    tree = window.object_tree.tree
    parent = item.parent()
    while parent:
        parent.setExpanded(True)
        parent = parent.parent()
    expected = item.data(1, Qt.ItemDataRole.UserRole)
    for attempt in range(3):
        tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        settle(550 if attempt else 150)
        rectangle = tree.visualItemRect(item).intersected(tree.viewport().rect())
        if rectangle.height() < 8 or tree.itemAt(rectangle.center()) is not item:
            continue
        QTest.mouseMove(tree.viewport(), rectangle.center())
        QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rectangle.center())
        settle(250)
        if item.isSelected() and (not expected or window.feature_panel.feature_id == expected):
            return
        log("Auswahl benötigt Wiederholung", attempt=attempt+1, expected=str(expected), selected=window.feature_panel.feature_id, rect=[rectangle.x(), rectangle.y(), rectangle.width(), rectangle.height()], viewport=[tree.viewport().width(), tree.viewport().height()])
    raise RuntimeError("Baumklick erreicht Auswahl nicht: " + str(expected or item.text(0)))


# Die lokal versionierte Dialogsteuerung bleibt getrennt; dieser Beobachter
# misst das Signal unmittelbar vor der Importarbeit, nicht den Menüweg.
_dialog_guard = guard
import_clock = {}

def guard():
    if guard_active:
        return
    modal = app.activeModalWidget()
    if isinstance(modal, QFileDialog) and pending_file is not None and not modal.property("audit_clock"):
        destination = str(pending_file)
        modal.setProperty("audit_clock", True)
        def accepted():
            if import_clock.get("path") == destination and "accepted" not in import_clock:
                import_clock["accepted"] = time.perf_counter()
        modal.accepted.connect(accepted)
    _dialog_guard()

def canvas_access(widget, local):
    """Prüft die eigene Qt-Hierarchie; fremde Desktop-Verdeckung ist damit nicht belegt."""
    global_point = widget.mapToGlobal(local)
    position = window.mapFromGlobal(global_point)
    front = app.widgetAt(global_point)
    child = window.childAt(position) if window.rect().contains(position) else None
    details = {"allowed": False, "resolution": "widgetAt",
        "window_active": window.isActiveWindow(), "canvas_visible": widget.isVisible(),
        "global_point": [global_point.x(), global_point.y()],
        "widget_at": front.__class__.__name__ if front is not None else None,
        "window_child_at": child.__class__.__name__ if child is not None else None,
        "desktop_occlusion_checked": False, "covered_by": None}
    if not widget.isVisible() or not widget.rect().contains(local):
        return {**details, "resolution": "outside_or_hidden"}
    for method, blocker in (("activeModalWidget", app.activeModalWidget()),
                            ("activePopupWidget", app.activePopupWidget())):
        if blocker is not None and blocker.isVisible():
            return {**details, "resolution": method, "covered_by": blocker.__class__.__name__}
    if front is None:
        front = child
        details["resolution"] = "window.childAt"
    details["covered_by"] = front.__class__.__name__ if front is not None else None
    details["allowed"] = front is widget or (front is not None and widget.isAncestorOf(front))
    if front is None:
        details["unresolved"] = True
    return details


def import_scene_observed(result):
    scene=getattr(result,"scene",None)
    if "accepted" in import_clock and "evaluated" not in import_clock and scene is not None and scene.objects:
        import_clock["evaluated"] = time.perf_counter()

def independent_surface(view, x, y):
    """CPU-Strahl gegen Originaldreiecke, ohne Renderer-Pick oder Auswahlcode."""
    near = view.renderer.display_to_world(x, y, 0.0)
    far = view.renderer.display_to_world(x, y, 1.0)
    if near is None or far is None:
        return {"reason": "Kein Kamerastrahl"}
    origin = np.asarray(near, dtype=float)
    direction = np.asarray(far, dtype=float) - origin
    direction /= np.linalg.norm(direction)
    nearest = float("inf")
    found = None
    for oid, obj in session.last_result.scene.objects.items():
        if not obj.visible or oid in view.hidden or (view._plate >= 0 and obj.plate != view._plate):
            continue
        raw = getattr(obj.mesh, "raw", None)
        if raw is None:
            continue
        # Der Ansichtsversatz ist Darstellung; die Trefferrechnung bleibt
        # vollständig unabhängig von _world_at, _aim_at und _feature_hit.
        shift = np.asarray(view._view_offset(obj, session.last_result), dtype=float)
        start = origin - shift
        for offset in range(0, len(raw.faces), 32768):
            triangles = np.asarray(raw.vertices[raw.faces[offset:offset+32768]], dtype=float)
            edge1, edge2 = triangles[:,1]-triangles[:,0], triangles[:,2]-triangles[:,0]
            cross = np.cross(np.broadcast_to(direction, edge2.shape), edge2)
            det = np.einsum("ij,ij->i", edge1, cross)
            valid = np.abs(det) > 1e-12
            inverse = np.divide(1.0, det, out=np.zeros_like(det), where=valid)
            delta = start - triangles[:,0]
            u = np.einsum("ij,ij->i", delta, cross) * inverse
            q = np.cross(delta, edge1)
            v = q @ direction * inverse
            distance = np.einsum("ij,ij->i", edge2, q) * inverse
            valid &= (u >= 0) & (v >= 0) & (u+v <= 1) & (distance >= 0) & (distance < nearest)
            candidates = np.flatnonzero(valid)
            if not len(candidates):
                continue
            index = candidates[np.argmin(distance[candidates])]
            nearest = float(distance[index])
            cell = offset + int(index)
            point = start + direction*nearest
            features = [str(fid) for fid, feature in obj.features.items() if cell in feature.face_indices]
            soft_target = False
            for feature in obj.features.values():
                # Nur wirkliche axiale Öffnungen erlauben eine Zielhilfe vor
                # der sichtbaren Fläche. Runde Außenflächen bleiben voll prüfbar.
                opening = (feature.kind == "hole"
                    or (feature.kind == "cone" and feature.params.get("recess") is True)
                    or (feature.kind == "thread" and feature.params.get("internal") is True))
                if not opening:
                    continue
                diameter, axis, centre = (feature.params.get(name) for name in ("diameter", "axis", "centre"))
                if not diameter or axis is None or centre is None:
                    continue
                line = np.asarray(axis, dtype=float)
                span = np.linalg.norm(line)
                if span <= 1e-12:
                    continue
                radial = np.linalg.norm(np.cross(point-np.asarray(centre), line/span))
                if radial <= float(diameter)/2 + max(0.5, np.linalg.norm(obj.mesh.bounds.size)*0.01):
                    soft_target = True
            margin = float(min(u[index], v[index], 1-u[index]-v[index]))
            found = {"object": str(oid), "cell": cell, "point": plain(point+shift),
                     "features": features, "interior": margin > 0.02,
                     "barycentric_margin": margin, "near_axial_feature": soft_target}
    return found or {"reason": "Strahl trifft keine Originaloberfläche; Öffnungszielhilfe bleibt möglich"}


def targeted_surface_points(view, used_pixels):
    """Bis zu zwölf echte Klickziele, aus Originalflächen statt einem groben Raster.

    Projektion schlägt nur Punkte vor. Ob dort eine Oberfläche erreichbar ist,
    entscheidet danach der unabhängige CPU-Strahl am gerundeten Qt-Klickpixel.
    Die erste Runde reserviert jedem sichtbaren Körper ein Ziel; weitere Ziele
    verteilen sich auf seine übrigen Merkmalsarten. Grenzen bleiben im Befund.
    """
    renderer, widget = view.renderer, view.renderer.widget
    dpr = float(widget.devicePixelRatioF())
    camera = np.asarray(renderer.camera_pose().position, dtype=float)
    bodies = [(str(oid), obj) for oid, obj in session.last_result.scene.objects.items()
              if obj.visible and oid not in view.hidden
              and (view._plate < 0 or obj.plate == view._plate)]
    diagnostics = {oid: {"proposals": 0, "cpu_rays": 0, "chosen": 0,
                         "rejected": collections.Counter()} for oid, _obj in bodies}
    pools = {}
    for oid, obj in bodies:
        raw = getattr(obj.mesh, "raw", None)
        if raw is None or not len(raw.faces):
            diagnostics[oid]["rejected"]["no_original_triangles"] += 1
            continue
        by_kind = collections.defaultdict(list)
        # Jede Merkmalsart bekommt höchstens 32 Originaldreiecke. Bei vielen
        # gleichartigen Bohrungen werden auch verschiedene Merkmale abgetastet.
        features_by_kind = collections.defaultdict(list)
        for feature in obj.features.values():
            if feature.face_indices:
                features_by_kind[str(feature.kind)].append(feature)
        for kind, features in features_by_kind.items():
            for index in np.linspace(0, len(features)-1, min(8, len(features)), dtype=int):
                faces = features[int(index)].face_indices
                for at in np.linspace(0, len(faces)-1, min(4, len(faces)), dtype=int):
                    cell = int(faces[int(at)])
                    if 0 <= cell < len(raw.faces):
                        by_kind[kind].append(cell)
        # Auch Körper ohne erkannte Merkmale sowie unklassifizierte Flächen
        # müssen tatsächlich angeklickt werden können.
        by_kind["original_surface"] = list(np.linspace(
            0, len(raw.faces)-1, min(96, len(raw.faces)), dtype=int))
        shift = np.asarray(view._view_offset(obj, session.last_result), dtype=float)
        buckets = []
        for kind, cells in by_kind.items():
            proposals = []
            for cell in dict.fromkeys(int(cell) for cell in cells):
                triangle = np.asarray(raw.vertices[raw.faces[cell]], dtype=float) + shift
                centre = triangle.mean(axis=0)
                normal = np.cross(triangle[1]-triangle[0], triangle[2]-triangle[0])
                if float(normal @ (camera-centre)) <= 0:
                    continue
                projected = np.asarray(renderer.world_to_display(tuple(centre)), dtype=float)
                if not np.all(np.isfinite(projected)) or not 0 <= projected[2] <= 1:
                    continue
                local = QPoint(round(projected[0]/dpr), round(projected[1]/dpr))
                if not widget.rect().contains(local):
                    continue
                screen = np.asarray([renderer.world_to_display(tuple(point))[:2]
                                     for point in triangle], dtype=float)
                a, b = screen[1]-screen[0], screen[2]-screen[0]
                area = abs(float(a[0]*b[1]-a[1]*b[0]))
                proposals.append({"pixel": [local.x()*dpr, local.y()*dpr],
                    "source": "original_triangle_centre", "source_object": oid,
                    "source_cell": cell, "source_kind": kind,
                    "projected_area_pixels": area, "projected_original": plain(projected)})
            proposals.sort(key=lambda proposal: proposal["projected_area_pixels"], reverse=True)
            diagnostics[oid]["proposals"] += len(proposals)
            if proposals:
                buckets.append(proposals)
        # Gute Kandidaten jeder Art zuerst, bevor ein einziges feines Merkmal
        # das gesamte begrenzte Suchbudget beansprucht.
        pools[oid] = [bucket[rank] for rank in range(max(map(len, buckets), default=0))
                      for bucket in buckets if rank < len(bucket)]

    chosen, chosen_kinds = [], set()
    tried_pixels = set(used_pixels)
    ray_budget = 96

    def choose(oid, *, new_kind):
        nonlocal ray_budget
        pool = pools.get(oid, [])
        attempts = 0
        for proposal in list(pool):
            if new_kind and (oid, proposal["source_kind"]) in chosen_kinds:
                continue
            if attempts >= 24 or ray_budget <= 0:
                break
            pool.remove(proposal)
            pixel = tuple(proposal["pixel"])
            if pixel in tried_pixels:
                continue
            tried_pixels.add(pixel)
            local = QPoint(round(pixel[0]/dpr), round(pixel[1]/dpr))
            access = canvas_access(widget, local)
            if not access["allowed"]:
                diagnostics[oid]["rejected"]["qt_overlay_or_unresolved"] += 1
                continue
            attempts += 1
            ray_budget -= 1
            diagnostics[oid]["cpu_rays"] += 1
            expected = independent_surface(view, *pixel)
            if expected.get("object") != oid:
                diagnostics[oid]["rejected"]["occluded_or_missed_original"] += 1
                continue
            if not expected.get("interior", False):
                diagnostics[oid]["rejected"]["rounded_pixel_near_triangle_boundary"] += 1
                continue
            # Am einzelnen Peg kann die Zielhilfe ein anderes Merkmal meinen,
            # aber keinen anderen Körper. Bei Baugruppen wäre das nicht sicher.
            if expected.get("near_axial_feature", False) and len(bodies) > 1:
                diagnostics[oid]["rejected"]["axial_help_between_bodies_not_resolved"] += 1
                continue
            chosen.append({**proposal, "expected_cpu": expected})
            chosen_kinds.add((oid, proposal["source_kind"]))
            diagnostics[oid]["chosen"] += 1
            return True
        return False

    for oid, _obj in bodies:
        if len(chosen) >= 12:
            diagnostics[oid]["rejected"]["twelve_click_limit"] += 1
            continue
        choose(oid, new_kind=False)
    progress = True
    while len(chosen) < 12 and ray_budget > 0 and progress:
        progress = False
        for oid, _obj in bodies:
            if len(chosen) >= 12 or ray_budget <= 0:
                break
            progress = choose(oid, new_kind=True) or progress
    for oid, _obj in bodies:
        if not diagnostics[oid]["chosen"]:
            diagnostics[oid]["reason"] = (
                "CPU-Strahlbudget erschöpft" if ray_budget <= 0 else
                "Kein sicherer, unverdeckter Dreiecksklick im begrenzten Suchraster gefunden")
    return chosen, diagnostics, len(bodies)

def verify_exported_3mf():
    """Liest den Dateiexport erneut über die Import-API und vergleicht Geometrie."""
    from concurrent.futures import ThreadPoolExecutor
    from app.core.ingest.threemf import read_objects
    records = [row for row in results["checks"] if row["label"] == "Export-Ausgangsszene"]
    files = sorted((OUT / "export-3mf").glob("*.3mf"))
    if not records or not files:
        log("3MF-Geometrie nicht geprüft", passed=False, reason="Export-Ausgangsszene oder 3MF fehlt")
        return
    expected = records[-1]["scene"]["objects"]
    def inspect():
        return [{"file": str(path), "name": part.name, "triangles": part.mesh.triangle_count,
                 "bounds": [plain(part.mesh.bounds.minimum), plain(part.mesh.bounds.maximum)],
                 "volume": float(part.mesh.volume), "watertight": bool(part.mesh.is_watertight),
                 "components": part.mesh.component_count}
                for path in files for part in read_objects(path.read_bytes())]
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(inspect)
        wait("3MF unabhängig wieder eingelesen", future.done, 300)
        actual = future.result()
    unmatched = list(actual)
    matches = []
    for before in expected:
        candidate = next((after for after in unmatched
            if before["triangles"] == after["triangles"]
            and before["watertight"] == after["watertight"]
            and before["components"] == after["components"]
            and np.allclose(before["bounds"], after["bounds"], atol=1e-5, rtol=1e-7)
            and np.isclose(before["volume"], after["volume"], atol=1e-5, rtol=1e-6)), None)
        matches.append({"expected_object": before["id"], "matched": candidate is not None})
        if candidate is not None:
            unmatched.remove(candidate)
    passed = len(expected) == len(actual) and all(row["matched"] for row in matches) and not unmatched
    log("3MF-Geometrie unabhängig wieder eingelesen", passed=passed, matches=matches,
        expected=expected, actual=actual, checks=["Objektzahl", "Dreiecke", "Hüllquader", "Volumen", "Wasserdichtheit", "Komponenten"])

def shot(name, widget=None):
    """Nimmt das sichtbare native Fenster einschließlich GPU-Fläche auf."""
    widget = widget or window
    renderer = window.viewport.renderer
    if renderer is not None:
        renderer.render()
    pump_events()
    app.sync()
    target = OUT / (name + ".png")
    widget.screen().grabWindow(int(widget.winId())).save(str(target))
    results["screenshots"].append(target.name)
    if widget is not window:
        context = OUT / (name + "-context.png")
        window.screen().grabWindow(int(window.winId())).save(str(context))
        results["screenshots"].append(context.name)
    write()

def summary_stats(values):
    values = np.asarray(values, dtype=float)*1000
    return {"count":len(values),"median_ms":float(np.median(values)),
            "p95_ms":float(np.percentile(values,95)),"max_ms":float(np.max(values))}

def choose_combo(combo, value):
    """Wählt einen sichtbaren Eintrag mit Tastatureingaben."""
    index = combo.findData(value)
    if index < 0:
        raise LookupError(str(value))
    click(combo)
    QTest.keyClick(combo, Qt.Key.Key_Home)
    for _ in range(index):
        QTest.keyClick(combo, Qt.Key.Key_Down)
    QTest.keyClick(combo, Qt.Key.Key_Return)
    settle(150)
    if combo.currentData() != value:
        raise AssertionError("Auswahl erreicht Wert nicht")

def finish_gpu(renderer):
    """GPU-Aufträge abschließen; kein Nachweis für den späteren OS-Scanout."""
    if args.renderer == "gfx":
        # wgpu 0.32.0 deklariert den Queue-Fertig-Callback mit einer zur
        # mitgelieferten C-Signatur inkompatiblen Parameterliste. Ein
        # geordneter 4-Byte-Readback wartet ebenfalls auf vorherige Aufträge;
        # sein Aufwand bleibt in der separat gemessenen Fence-Zeit sichtbar.
        import wgpu
        device=renderer._renderer._device
        buffer=getattr(renderer,"_audit_fence_buffer",None)
        if buffer is None:
            buffer=device.create_buffer(size=4,usage=wgpu.BufferUsage.COPY_SRC|wgpu.BufferUsage.COPY_DST)
            renderer._audit_fence_buffer=buffer
        device.queue.write_buffer(buffer,0,b"\x00\x00\x00\x00")
        device.queue.read_buffer(buffer)
        results["gpu_completion_method"]="ordered_4_byte_readback"
    else:
        renderer.window.WaitForCompletion()
        results["gpu_completion_method"]="vtk_WaitForCompletion"

def display_performance(kind):
    """Vergleicht den Bildaufwand der verschiedenen Darstellungen."""
    from run_context import cpu_context, cpu_snapshot
    context_before=cpu_snapshot()
    renderer=window.viewport.renderer
    original=renderer.render
    def completed():
        original()
        finish_gpu(renderer)
    renderer.render=completed
    try:
        frames=drag_frames(window,app,12)
    finally:
        renderer.render=original
    log("Darstellungsleistung",kind=kind,**summary_stats(frames),gpu_queue_complete=True,cpu=cpu_context(context_before))

def performance():
    """Misst fertige Bilder, rohe Picks und echte Hover-Ereignisse getrennt."""
    from run_context import cpu_context, cpu_snapshot
    view = window.viewport
    renderer = view.renderer
    settle(350)
    results["ram_before_mib"] = working_set_mb()
    renders=[]
    original_render=renderer.render
    def completed_render():
        begin=time.perf_counter()
        original_render()
        submitted=time.perf_counter()
        finish_gpu(renderer)
        done=time.perf_counter()
        renders.append({"submission":submitted-begin,"fence":done-submitted,"complete":done-begin})
    context_before=cpu_snapshot()
    renderer.render=completed_render
    try:
        frames=drag_frames(window,app,40)
    finally:
        renderer.render=original_render
    log("Navigation fertiger Bilder",**summary_stats(frames),gpu_queue_complete=True,os_scanout_measured=False,cpu=cpu_context(context_before))
    for part in ("submission","fence","complete"):
        log("Renderaufrufe "+part,**summary_stats([row[part] for row in renders]),includes_camera_restore=True)
    widget = renderer.widget
    dpr = float(widget.devicePixelRatioF())
    coords = [(widget.width()*x, widget.height()*y) for x,y in
              ((.2,.2),(.5,.2),(.8,.2),(.2,.5),(.5,.5),(.8,.5),(.2,.8),(.5,.8),(.8,.8))]
    durations = []
    for _ in range(3):
        for x,y in coords:
            begin = time.perf_counter()
            renderer.pick_surface(x*dpr,y*dpr)
            durations.append(time.perf_counter()-begin)
    log("Oberflächentreffer Renderer", **summary_stats(durations))
    import general_checks
    objects=session.last_result.scene.objects
    oid=max(objects,key=lambda key:objects[key].mesh.triangle_count)
    general_checks.select_objects(sys.modules[__name__],[oid])
    settle(200)
    samples=[]
    callbacks=[]
    pending_hover={}
    original_hover=view._look_under_pointer
    def measured_hover():
        begin=time.perf_counter()
        at=view._hover_at
        original_hover()
        calculated=time.perf_counter()
        finish_gpu(renderer)
        done=time.perf_counter()
        callbacks.append({"at":plain(at),"callback_seconds":calculated-begin,
            "gpu_fence_seconds":done-calculated,"ready_seconds":done-pending_hover.get("sent",begin),
            "debounce_seconds":begin-pending_hover.get("sent",begin)})
    view._hover_timer.timeout.disconnect(original_hover)
    view._hover_timer.timeout.connect(measured_hover)
    try:
        for _ in range(3):
            for x,y in coords:
                local=QPoint(round(x),round(y))
                access=canvas_access(widget,local)
                if not access["allowed"]:
                    samples.append({"pixel":[x,y],"skipped":"unresolved" if access.get("unresolved") else "covered", "access":access})
                    continue
                previous=len(callbacks)
                pending_hover["sent"]=time.perf_counter()
                QTest.mouseMove(widget,local)
                pump_events()
                dispatch=time.perf_counter()-pending_hover["sent"]
                end=time.monotonic()+2
                while len(callbacks)==previous and time.monotonic()<end:
                    pump_events()
                    time.sleep(0.002)
                if len(callbacks)==previous:
                    samples.append({"pixel":[x,y],"skipped":"no_hover_callback","access":access,
                        "hover_at":plain(view._hover_at),"timer_active":view._hover_timer.isActive(),"dispatch_seconds":dispatch})
                else:
                    samples.append({"pixel":[x,y],"dispatch_seconds":dispatch,"access":access,**callbacks[-1]})
    finally:
        view._hover_timer.timeout.disconnect(measured_hover)
        view._hover_timer.timeout.connect(original_hover)
    measured=[row for row in samples if "callback_seconds" in row]
    log("Hover-Ereignisse und Ausnahmen",samples=samples,measured=len(measured),requested=len(samples))
    for label,key in (("Hover Ereignisdispatch","dispatch_seconds"),("Hover Entprellwartezeit","debounce_seconds"),
        ("Hover Merkmalssuche","callback_seconds"),("Hover GPU-Abschluss","gpu_fence_seconds"),
        ("Hover bis fertige Rückmeldung","ready_seconds")):
        if measured:
            log(label,**summary_stats([row[key] for row in measured]))
    before = view.camera_pose()
    p = QPoint(round(widget.width()*.75),round(widget.height()*.5))
    QTest.mousePress(widget,Qt.MouseButton.RightButton,pos=p)
    for step in range(1,17):
        QTest.mouseMove(widget,p+QPoint(step*8,step*2))
        pump_events()
    QTest.mouseRelease(widget,Qt.MouseButton.RightButton,pos=p+QPoint(128,32))
    settle(100)
    log("Kamera durch Mauszug", changed=before != view.camera_pose())
    if app.activePopupWidget() is not None:
        QTest.keyClick(app.activePopupWidget(),Qt.Key.Key_Escape)
    view.set_camera_pose(*before)
    settle(100)
    results["ram_after_mib"] = working_set_mb()

def feature_selection():
    """Prüft je Körper und Merkmalsart Baum sowie echte Oberflächenklicks."""
    import feature_checks
    groups = {}
    for oid,obj in session.last_result.scene.objects.items():
        for fid,feature in obj.features.items():
            groups.setdefault((oid,feature.kind),(fid,feature))
    for number,((oid,kind),(fid,feature)) in enumerate(groups.items()):
        feature_checks._choose(sys.modules[__name__],oid,fid)
        log("Merkmal im Baum gewählt", object=str(oid), feature=str(fid),kind=kind,
            selected=window.feature_panel.feature_id==fid)
        if number < 4:
            shot(f"feature-{number:02d}-{kind}")
    log("Merkmalsauswahl Umfang", groups=len(groups),features=sum(len(o.features) for o in session.last_result.scene.objects.values()))
    view=window.viewport
    renderer=view.renderer
    widget=renderer.widget
    dpr=float(widget.devicePixelRatioF())
    hits=[]
    visible_bodies=sum(1 for oid,obj in session.last_result.scene.objects.items()
        if obj.visible and oid not in view.hidden and (view._plate < 0 or obj.plate == view._plate))

    def click_surface(proposal):
        """Die echte Geste wird gegen Originalgeometrie geprüft, nicht gegen den GPU-Pick."""
        x,y=proposal["pixel"]
        local=QPoint(round(x/dpr),round(y/dpr))
        x,y=local.x()*dpr,local.y()*dpr
        access=canvas_access(widget,local)
        if not access["allowed"]:
            hits.append({**proposal,"pixel":[x,y],
                "skipped":"unresolved" if access.get("unresolved") else "covered","access":access})
            return
        expected=proposal.get("expected_cpu") or independent_surface(view,x,y)
        before=window.object_tree.selected()
        # Der GPU-Pick ist ein zusätzlich beobachtetes Ergebnis. Die Erwartung
        # oben wurde ausschließlich aus dem Kamerastrahl und Originaldreiecken
        # gewonnen, und die Auswahl selbst entsteht erst durch diesen QTest-Klick.
        surface=renderer.pick_surface(x,y,among=list(view._actors.values()) or None)
        QTest.mouseClick(widget,Qt.MouseButton.LeftButton,pos=local)
        settle(80)
        selected=[str(o) for o in window.object_tree.selected_objects()]
        interior=expected.get("interior",False)
        axial=expected.get("near_axial_feature",False)
        body_reliable=interior and (not axial or visible_bodies==1)
        feature_reliable=interior and not axial
        object_match=expected["object"] in selected if body_reliable else None
        candidates=expected.get("features",[])
        feature_match=(window.feature_panel.feature_id==candidates[0]
            if feature_reliable and str(before)==expected.get("object") and len(candidates)==1 else None)
        actor_owner=next((str(oid) for oid,actor in view._actors.items()
                          if surface is not None and actor is surface.item),None)
        surface_match=(surface is not None and actor_owner==expected["object"]
                       if interior else None)
        limits=[]
        if not interior:
            limits.append(expected.get("reason","CPU-Treffer liegt zu nahe an einer Dreieckskante"))
        if axial:
            limits.append("Axiale Zielhilfe: Merkmalsvergleich offen" if visible_bodies==1 else
                          "Axiale Zielhilfe zwischen Körpern nicht unabhängig aufgelöst")
        hits.append({**proposal,"pixel":[x,y],"hit":surface is not None,"access":access,
                     "cell":int(surface.cell) if surface is not None and surface.cell is not None else None,
                     "surface_point":plain(surface.point) if surface is not None else None,
                     "surface_object":actor_owner,"surface_matches":surface_match,
                     "objects":selected,"feature":window.feature_panel.feature_id,
                     "expected_cpu":expected,"object_matches":object_match,"feature_matches":feature_match,
                     "selection_before":str(before),"comparison_limits":limits})

    # Gleichmäßig verteilte Bildpunkte prüfen die echte Auswahl ohne vorab die
    # erwartete Antwort mit derselben Merkmalslogik auszurechnen.
    for fx,fy in ((.35,.35),(.5,.35),(.65,.35),(.35,.5),(.5,.5),(.65,.5),(.35,.65),(.5,.65),(.65,.65)):
        x,y=widget.width()*fx*dpr,widget.height()*fy*dpr
        click_surface({"pixel":[x,y],"source":"grid"})
    targeted,diagnostics,_count=targeted_surface_points(view,{tuple(row["pixel"]) for row in hits})
    for proposal in targeted:
        click_surface(proposal)
    comparisons=[value for row in hits for key,value in row.items()
                 if key in ("surface_matches","object_matches","feature_matches") and value is not None]
    covered_bodies=sorted({row["expected_cpu"]["object"] for row in hits
        if row.get("object_matches") is True and row.get("surface_matches") is True})
    missing_bodies=sorted(set(diagnostics)-set(covered_bodies))
    log("Oberflächenklicks",hits=hits,independent_comparisons=len(comparisons),
        targeted_clicks=len(targeted),target_search=diagnostics,
        verified_bodies=covered_bodies,unverified_bodies=missing_bodies,
        coverage_complete=not missing_bodies,
        passed=all(comparisons) if comparisons else None)
    shot("surface-selection")
    # Eine rote Beobachtung behält ihren Status. Die zusätzliche Sicherung
    # erhält genau diese Pose für eine unabhängige Diagnose des Pixelumfelds.
    red_pixels = [row["pixel"] for row in hits if any(row.get(key) is False
        for key in ("surface_matches", "object_matches", "feature_matches"))]
    if red_pixels:
        from surface_pick_footprint import capture_and_diagnose
        capture_and_diagnose(sys.modules[__name__], red_pixels, observations=hits)

def displays():
    """Geht durch sichtbare Darstellungsmenüs und Analyseleisten."""
    for mode in ("solid_edges","wireframe","transparent","solid"):
        action=next(a for a in window._mode_group.actions() if a.data()==mode)
        menu(action)
        wait("Darstellung aufgebaut",lambda:window.viewport._scene_worker is None,180)
        settle(150)
        log("Darstellung",mode=mode,checked=action.isChecked())
        shot("mode-"+mode)
        display_performance(mode)
    for mode in ("orthographic","perspective"):
        action=next(a for a in window._projection_group.actions() if a.data()==mode)
        menu(action)
        log("Projektion",mode=mode,checked=action.isChecked())
    import general_checks
    objects=session.last_result.scene.objects
    oid=max(objects,key=lambda key:objects[key].mesh.triangle_count)
    general_checks.select_objects(sys.modules[__name__],[oid])
    analysis_button=window.tools._buttons["analysis"]
    if not analysis_button.isVisible() or not analysis_button.isEnabled():
        raise AssertionError("Analysewerkzeug ist für den gewählten Körper nicht bedienbar")
    if not analysis_button.isChecked():
        click(analysis_button)
    combo=window.analysis_bar.selector
    wait("Analyseleiste geöffnet",lambda:window.analysis_bar.isVisible() and combo.isVisible(),10)
    for value in ("features","overhang",None):
        choose_combo(combo,value)
        wait("Analysekarte fertig",lambda:window._map_worker is None and window.viewport._scene_worker is None,180)
        shot("analysis-"+str(value))
        actual=window.viewport._map
        log("Analysekarte",kind=value,selected=combo.currentData(),bar_visible=window.analysis_bar.isVisible(),
            computed=actual is not None,actual_kind=getattr(actual,"kind",None),
            visible_feedback=[label.text() for label in window.analysis_bar.findChildren(QLabel) if label.isVisible()])
        if actual is not None:
            display_performance("analysis-"+str(value))
    section_button=window.tools._buttons["section"]
    if not section_button.isVisible() or not section_button.isEnabled():
        raise AssertionError("Schnittwerkzeug ist nicht bedienbar")
    if not section_button.isChecked():
        click(section_button)
    combo=window.section_bar.axis
    wait("Schnittleiste geöffnet",lambda:window.section_bar.isVisible() and combo.isVisible(),10)
    choose_combo(combo,"z")
    slider=window.section_bar.position
    before=slider.value()
    slider.setFocus()
    QTest.keyClick(slider,Qt.Key.Key_Right)
    from app.ui.section_bar import STEPS_PER_MM
    expected_position=slider.value()/STEPS_PER_MM
    wait("Schnitt dargestellt",lambda:window.viewport._section is not None
        and abs(window.viewport._section.position-expected_position)<1e-6
        and window.viewport._scene_worker is None,120)
    settle(300)
    shot("section-z")
    log("Schnittdarstellung",axis="z",bar_visible=window.section_bar.isVisible(),
        plane=plain(window.viewport._section),slider_before=before,slider_after=slider.value(),
        slider_changed=slider.value()!=before)
    choose_combo(combo,None)
    wait("Schnitt zurückgenommen",lambda:window.viewport._section is None and window.viewport._scene_worker is None,120)
    if section_button.isChecked():
        click(section_button)
    log("Schnittdarstellung zurückgenommen",restored=window.viewport._section is None)
    import feature_checks
    labelled=next(((key,next(iter(obj.features))) for key,obj in objects.items() if obj.features),None)
    if labelled is not None:
        feature_checks._choose(sys.modules[__name__],*labelled)
    for theme in ("light","dark"):
        action=next(action for action in window._theme_group.actions() if action.data()==theme)
        menu(action)
        wait("Themenwechsel dargestellt",lambda:window.viewport._scene_worker is None,60)
        settle(200)
        shot("theme-"+theme)
        log("Thema am sichtbaren Fenster",theme=theme,checked=action.isChecked(),
            selected_feature=window.feature_panel.feature_id,expected_feature=labelled[1] if labelled else None)

def layers():
    """Sichtet erste, mittlere und letzte Schicht mit eingeschalteten Merkmalen."""
    import analysis_checks, general_checks
    probe=sys.modules[__name__]
    objects=session.last_result.scene.objects
    oid=max(objects,key=lambda key:objects[key].mesh.triangle_count)
    general_checks.select_objects(probe,[oid])
    button=window.tools._buttons["analysis"]
    if not button.isChecked():
        click(button)
    wait("Analyse für Merkmale sichtbar",lambda:window.analysis_bar.isVisible(),10)
    checkbox=window.analysis_bar.overlay
    previous=checkbox.isChecked()
    if not previous:
        click(checkbox)
    settle(300)
    shot("all-features-before-layers")
    log("Merkmalbeschriftungen vor Schichtansicht",checked=checkbox.isChecked(),
        feature_actors=len(window.viewport._feature_actors))
    display_performance("feature-labels")
    analysis_checks.check_layers(probe,oid,objects[oid])
    if not button.isChecked():
        click(button)
    wait("Analyse nach Schichten sichtbar",lambda:window.analysis_bar.isVisible(),10)
    log("Merkmalanzeige nach Schichten",restored=checkbox.isChecked(),
        feature_actors=len(window.viewport._feature_actors))
    if checkbox.isChecked()!=previous:
        click(checkbox)
    if button.isChecked():
        click(button)

def edits():
    """Prüft repräsentative Bearbeitungen mit Vorschau, Undo und Redo."""
    import general_checks,feature_checks
    from app.core.perceive.actions import actions_for
    probe=sys.modules[__name__]
    objects=session.last_result.scene.objects
    oid=max(objects,key=lambda key:objects[key].mesh.triangle_count)
    general_checks.operation(probe,"translate_object",{"dx":3.0,"dy":0.0,"dz":0.0},oid,1)
    for fid,feature in list(session.last_result.scene.objects[oid].features.items()):
        if feature.kind not in ("hole","pin"):
            continue
        action=next((a for a in actions_for(feature,session.last_result.scene.objects[oid].features) if a.op in ("resize_hole","resize_feature")),None)
        if action is None:
            continue
        diameter=float(feature.params.get("diameter",0))
        if diameter<=0:
            continue
        feature_checks._perform(probe,oid,fid,action,{"diameter":round(diameter+0.5,2)},"plus-0.5-mm",1)
        break
    general_checks.persistence(probe)
    verify_exported_3mf()

def main():
    global pending_file, dialog_timer
    import menu_driver
    menu_driver.install(sys.modules[__name__])
    window.show()
    window.resize(1600,1000)
    window.move(40,40)
    window.activateWindow()
    settle(700)
    log("Sichtbare Anwendung",platform=app.platformName(),size=[window.width(),window.height()],
        viewport=[window.viewport.renderer.widget.width(),window.viewport.renderer.widget.height()])
    dialog_timer=QTimer(app)
    dialog_timer.setInterval(60)
    dialog_timer.timeout.connect(guard)
    dialog_timer.start()
    session.failed.connect(lambda error:errors.append(str(error)),window)
    session.importFailed.connect(lambda error:errors.append(str(error)),window)
    session.sceneChanged.connect(import_scene_observed,window)
    wait("Fenster bereit",lambda:not session.busy,30)
    pending_file=Path(entry["path"])
    if hashlib.sha256(pending_file.read_bytes()).hexdigest()!=entry["sha256"]:
        raise AssertionError("Eingangsdatei geändert")
    previous=session.last_result
    begin=time.perf_counter()
    import_clock.update(path=str(pending_file),menu_started=begin)
    menu(window.import_action)
    wait("Import und Erkennung",lambda:session.last_result is not None and session.last_result is not previous and
         not session.busy and bool(session.last_result.scene.objects),300)
    evaluated=time.perf_counter()
    wait("Viewport zeigt Ergebnis",lambda:window.viewport._result is session.last_result and window.viewport._scene_worker is None,30)
    shown=time.perf_counter()
    accepted=import_clock.get("accepted")
    log("Import und Erkennung",seconds=shown-begin,scene=scene_data(),
        dialog_accept_observed=accepted is not None,
        menu_and_dialog_seconds=accepted-begin if accepted is not None else None,
        import_after_accept_seconds=import_clock.get("evaluated",evaluated)-accepted if accepted is not None else None,
        viewport_after_accept_seconds=shown-accepted if accepted is not None else None)
    shot("01-import")
    if not args.gesture_only:
        performance()
        feature_selection()
        displays()
    if args.full:
        layers()
    if args.full or args.gesture_only:
        import gesture_checks
        gesture = gesture_checks.run(sys.modules[__name__])
        if gesture.get("restore_error") or gesture.get("undo_restored_original_geometry") is False:
            raise AssertionError("Körperzug hat die Ausgangsszene nicht wiederhergestellt")
    if args.full:
        edits()
    log("Originaldatei unverändert",same=hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest()==entry["sha256"])
    results["complete"]=True
    results["errors"]=errors
    write()

exit_code=0
try:
    main()
except BaseException:
    results["fatal"]=traceback.format_exc()
    print(results["fatal"],flush=True)
    write()
    exit_code=1
finally:
    try:
        fence=getattr(window.viewport.renderer,"_audit_fence_buffer",None)
        if fence is not None:
            fence.destroy()
        shutdown_window(window,app)
        wait("Anwendungsfenster geschlossen", lambda:not isValid(window) or not window.isVisible(), 10)
        results["closed"]=not isValid(window) or not window.isVisible()
        write()
    except BaseException:
        results["shutdown_error"]=traceback.format_exc()
        write()
        exit_code=1
    if dialog_timer is not None:
        dialog_timer.stop()
    watchdog.cancel()
    faulthandler.cancel_dump_traceback_later()
sys.exit(exit_code)
