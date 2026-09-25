"""Prüfstand am echten Fenster: Langlochzug, Merkmalpanel, Maße.

Aufruf: python slot_probe.py <szenario> [<modell>]
Schreibt Protokoll und Bilder nach SCRATCH/probe-out/<szenario>/.
"""

from __future__ import annotations

import faulthandler
import os
import sys
import threading
import time
from pathlib import Path

threading.Timer(900.0, lambda: os._exit(9)).start()

SCRATCH = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("PROBE_ROOT", r"F:\3D Druck"))
SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "hole"
MODEL = Path(
    sys.argv[2]
    if len(sys.argv) > 2
    else r"F:\3D Dateien\large-screwdriver-holder-with-honeycomb-pattern.stl"
)
OUT = SCRATCH / "probe-out" / SCENARIO
OUT.mkdir(parents=True, exist_ok=True)
LOG = open(OUT / "log.txt", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
faulthandler.enable(LOG)
faulthandler.dump_traceback_later(600, exit=True, file=LOG)

PROFILE = SCRATCH / "probe-profile"
PROFILE.mkdir(exist_ok=True)
for variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
    os.environ[variable] = str(PROFILE)
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, str(ROOT))


def log(*parts: object) -> None:
    LOG.write(" ".join(str(part) for part in parts) + "\n")


from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

if os.environ.get("PROBE_NO_SIBLINGS"):
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)
application = QApplication([])
load_operations()
# Vergleich unter gleicher Last: „alt" nimmt die Regel gegen native Geschwister
# zurück, „alien" lässt auch die Überlagerungen ohne eigenes Fenster (unsichtbar
# über der Fläche, nur für die Zeit).
VARIANT = os.environ.get("PROBE_VARIANT", "")
if VARIANT == "alt":
    import app.ui.viewport as _viewport_module  # noqa: E402

    _viewport_module.keep_widgets_alien = lambda: None
elif VARIANT == "alien":
    import app.ui.overlay as _overlay_module  # noqa: E402
    import app.ui.viewport as _viewport_module  # noqa: E402

    _viewport_module.hold_above_the_view = lambda event: None
    _overlay_module.hold_above_the_view = lambda event: None
from app.ui.app import build_application  # noqa: E402

application, window = build_application([])
window.settings.first_run_done = True

closed: list[str] = []


def sweep() -> None:
    widget = application.activeModalWidget()
    if widget is not None and widget.window() is not window:
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

screen = application.primaryScreen()
window.setGeometry(screen.availableGeometry())
window.showMaximized()
for _ in range(30):
    application.processEvents()
if os.environ.get("PROBE_FPS"):
    _fps = application.primaryScreen().refreshRate() if os.environ["PROBE_FPS"] == "screen" else float(os.environ["PROBE_FPS"])
    window.viewport.renderer._canvas.set_update_mode("ondemand", max_fps=_fps)


def pump(seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        application.processEvents()
        time.sleep(0.005)


def idle(settle: float = 0.6, timeout: float = 180.0) -> None:
    """Bis Sitzung, Platzierungsarbeiter und Vorschau ruhen."""
    deadline = time.monotonic() + timeout
    quiet = time.monotonic()
    while time.monotonic() < deadline:
        application.processEvents()
        # Wie die Ereignisschleife: ohne exec() löscht processEvents nichts, was
        # deleteLater bestellt hat, und die Sonde sammelte je Klick 30 Widgets an.
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.005)
        flow = window._quiet_placement
        approval = window._preview_approval
        busy = (
            window.session.busy
            or (flow is not None and getattr(flow, "_tool_busy", False))
            or window._feature_preview.isActive()
            or bool(window.session._previews)
            or (approval is not None and approval.pending_click is not None)
            or bool(getattr(window.session, "_placements", None))
        )
        if busy:
            quiet = time.monotonic()
        elif time.monotonic() - quiet >= settle:
            return
    log("WARNUNG: idle timeout")


def shot(name: str) -> None:
    application.processEvents()
    picture = screen.grabWindow(int(window.winId()))
    picture.save(str(OUT / f"{name}.png"))
    log("BILD", name)


def render_widget():
    return window.viewport.renderer.widget


def to_widget(point) -> QPointF:
    """Weltpunkt (gezeichnet) → logische Widgetkoordinate der Renderfläche."""
    renderer = window.viewport.renderer
    x, y, _depth = renderer.world_to_display(tuple(float(v) for v in point))
    ratio = renderer.device_ratio()
    return QPointF(x / ratio, y / ratio)


def send(kind, position: QPointF, buttons, button=Qt.MouseButton.NoButton) -> None:
    widget = render_widget()
    global_position = QPointF(widget.mapToGlobal(position.toPoint()))
    event = QMouseEvent(
        kind, position, global_position, button, buttons, Qt.KeyboardModifier.NoModifier
    )
    application.sendEvent(widget, event)
    application.processEvents()


def drag(start: QPointF, end: QPointF, steps: int = 12) -> None:
    left = Qt.MouseButton.LeftButton
    send(QEvent.Type.MouseMove, start, Qt.MouseButton.NoButton)
    pump(0.25)  # Hover sucht den Knopf
    send(QEvent.Type.MouseButtonPress, start, left, left)
    for index in range(1, steps + 1):
        share = index / steps
        at = QPointF(
            start.x() + (end.x() - start.x()) * share, start.y() + (end.y() - start.y()) * share
        )
        send(QEvent.Type.MouseMove, at, left)
        pump(0.02)
    send(QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton, left)
    pump(0.2)


def state(label: str) -> None:
    """Was Panel, Maßgruppe und Ansicht gerade sagen."""
    view = window.viewport
    panel = window.feature_panel
    flow = window._quiet_placement
    host = window._quiet_host
    log(f"--- {label}")
    log("  Auswahl:", window.object_tree.selected(), window.object_tree.selected_feature())
    feature = window._selected_feature_object() if hasattr(window, "_selected_feature_object") else None
    if feature is not None:
        p = feature.params
        log(
            "  Merkmal:",
            feature.id,
            feature.kind,
            "d=",
            p.get("diameter"),
            "L=",
            p.get("length"),
            "created_by=",
            getattr(feature, "created_by", None),
        )
    armed = panel._runs.get(panel._armed or "")
    log("  Panel scharf:", None if armed is None else armed.op, "measuring=", panel._measuring,
        "measure_op=", panel._measure_op)
    if armed is not None:
        try:
            log("  Panel Werte:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in armed.values().items()})
        except Exception as problem:  # noqa: BLE001
            log("  Panel Werte: FEHLER", problem)
    blocks = []
    for key, (line, row) in panel._blocks.items():
        entry = panel._runs.get(key)
        blocks.append(f"{None if entry is None else entry.op}:{'shown' if not row.isHidden() else 'hidden'}")
    log("  Panel Blöcke:", blocks)
    log("  Panel Apply sichtbar:", not panel._apply.isHidden(), "enabled:", panel._apply.isEnabled(),
        "Cancel sichtbar:", not panel._cancel.isHidden())
    if flow is None:
        log("  Maßgruppe: keine")
    else:
        log("  Maßgruppe:", flow.spec_of().name, "aktiv=", flow.active)
        if host is not None:
            log("  Host begun=", host.begun, "Werte:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in host.values().items()})
        group = getattr(flow, "_measure_group", None)
        if group is not None:
            texts = []
            for child in group.findChildren(object):
                pass
        box = getattr(flow, "_measure_box", None)
        log("  Maßbox sichtbar:", box is not None and not box.isHidden(),
            "Accept enabled:", flow._measure_accept.isEnabled(),
            "Note:", repr(flow._measure_note.text()) if not flow._measure_note.isHidden() else "-")
        measures = [m.value_mm() for m in getattr(flow, "_measures", [])] if getattr(flow, "_measures", None) else []
        centres = [m.value_mm() for m in getattr(flow, "_centre_measures", [])] if getattr(flow, "_centre_measures", None) else []
        visible_measures = [not m.isHidden() for m in getattr(flow, "_measures", []) or []]
        log("  Kantenmaße:", [round(v, 3) for v in measures], "sichtbar:", visible_measures,
            "Mittenmaße:", [round(v, 3) for v in centres])
        dims = getattr(flow, "_dimensions", None)
        if dims is not None:
            try:
                log("  Maßtinte Segmente:", len(dims.segments))
            except Exception as problem:  # noqa: BLE001
                log("  Maßtinte:", problem)
        log("  Fläche:", flow._surface is not None, "Werkzeug:", flow._tool_context is not None,
            "busy:", flow._tool_busy, "distance_valid:", flow._distance_valid)
    handle = view._slot_handle
    try:
        log("  Ansicht intern: sel=", view._selected, "selfeat=", view._selected_feature,
            "slotfeat=", getattr(view.slot_handle_feature(), "id", None),
            "gizmofeat=", getattr(view.gizmo_feature(), "id", None),
            "blocked=", view._feature_gizmo_blocked, "knobs_stay=", view._knobs_stay,
            "grip_item=", view._placement_grip_item is not None,
            "pointer=", view._placement_pointer is not None,
            "face_seat=", bool(view._face_seat), "preview_gizmo=", view._preview_gizmo_wanted,
            "gizmo_wanted=", view._gizmo_wanted, "gizmo=", view._gizmo is not None)
    except Exception as problem:  # noqa: BLE001
        log("  Ansicht intern FEHLER", problem)
    log("  Griff:", None if handle is None else (round(handle.length, 3), round(handle.angle, 2), round(2 * handle.radius, 3)))
    log("  Ansicht slot_target=", view._slot_target, "waiting=", view._slot_waiting,
        "width=", view._slot_width, "drag_kind=", view._drag_kind,
        "move_target=", view._move_target, "grip_shift=", view._grip_shift)
    log("  Statuszeile:", window.statusBar().currentMessage())
    ops = window.session.project.document.ops
    log("  Schritte:", [(op.id, op.op, {k: v for k, v in op.params.items() if k in ("at_feature", "slot_length", "slot_angle", "diameter", "x", "y", "z")}) for op in ops])


def knobs() -> list[QPointF]:
    handle = window.viewport._slot_handle
    return [to_widget(seat) for seat in handle.knob_seats]


def centre_of_handle() -> QPointF:
    centre, _reach = window.viewport._slot_handle.clearance
    return to_widget(centre)


def find_feature(kind: str, index: int = 0):
    result = window.session.last_result
    object_id = next(iter(result.scene.objects))
    entry = result.scene.objects[object_id]
    features = sorted(
        (f for f in entry.features.values() if f.kind == kind),
        key=lambda f: (f.params.get("length") or 0.0, f.id),
    )
    return object_id, features[index]


def select(object_id: str, feature_id: str) -> None:
    window.object_tree.select_object(object_id)
    idle(0.3)
    window.object_tree.select_feature(object_id, feature_id)
    idle(0.8)


def fly_to_feature() -> None:
    feature = window._selected_feature_object()
    view = window.viewport
    if feature is None:
        return
    centre = feature.params["centre"]
    axis = list(feature.params["axis"])
    try:
        from app.core.scene import placement as _placement
        import numpy as _np
        entry = window.session.last_result.scene.objects[window.object_tree.selected()]
        seat = _placement.seat_of(entry.mesh, feature, entry.features)
        if seat is not None:
            outward = _np.asarray(seat[1]) - _np.asarray(centre)
            if float(outward @ _np.asarray(axis)) < 0:
                axis = [-float(v) for v in axis]
    except Exception as problem:  # noqa: BLE001
        log("fly: seat unbekannt", problem)
    distance = 60.0
    eye = tuple(float(centre[i]) + float(axis[i]) * distance for i in range(3))
    up = (0.0, 0.0, 1.0) if abs(float(axis[2])) < 0.9 else (0.0, 1.0, 0.0)
    view.set_camera_pose(eye, tuple(float(c) for c in centre), up)
    idle(0.5)


def click(point: QPointF) -> None:
    left = Qt.MouseButton.LeftButton
    send(QEvent.Type.MouseMove, point, Qt.MouseButton.NoButton)
    pump(0.2)
    send(QEvent.Type.MouseButtonPress, point, left, left)
    send(QEvent.Type.MouseButtonRelease, point, Qt.MouseButton.NoButton, left)
    pump(0.6)


def view_select(object_id: str, feature) -> None:
    """Wie der Kunde: Kamera auf die Mündung, erst den Körper, dann das Loch anklicken."""
    centre = feature.params["centre"]
    axis = feature.params["axis"]
    distance = 60.0
    eye = tuple(float(centre[i]) + float(axis[i]) * distance for i in range(3))
    up = (0.0, 0.0, 1.0) if abs(float(axis[2])) < 0.9 else (0.0, 1.0, 0.0)
    window.viewport.set_camera_pose(eye, tuple(float(c) for c in centre), up)
    idle(0.4)
    target = to_widget(centre)
    click(target)
    idle(0.4)
    if window.object_tree.selected_feature() is None:
        click(target)
    idle(0.8)


def panel_field(op: str, word: str):
    """Das Feld einer Handlung im Merkmalpanel, über seinen zugänglichen Namen."""
    from app.ui.op_dialog import ValueField
    panel = window.feature_panel
    for key, (line, row) in panel._blocks.items():
        entry = panel._runs.get(key)
        if entry is None or entry.op != op:
            continue
        for field in row.findChildren(ValueField):
            if word in field.accessibleName():
                return field
        for field in row.findChildren(object):
            name = getattr(field, "accessibleName", lambda: "")()
            if word in name:
                return field
    return None


def group_field(word: str):
    """Ein Feld der Maßgruppe im Bild."""
    from app.ui.op_dialog import ValueField
    flow = window._quiet_placement
    if flow is None or flow._measure_group is None:
        return None
    from PySide6.QtWidgets import QWidget
    for field in flow._measure_group.findChildren(QWidget):
        if field.property("featureField") == word:
            return field
    return None


def type_into(field, value: float) -> None:
    """Wie ein Kunde: Feld fokussieren, Text ersetzen, Eingabe."""
    from PySide6.QtTest import QTest
    spin = getattr(field, "spin", field)
    spin.setFocus()
    application.processEvents()
    line = spin.lineEdit()
    line.selectAll()
    text = f"{value:.2f}".replace(".", ",")
    QTest.keyClicks(line, text)
    application.processEvents()
    QTest.keyClick(line, Qt.Key.Key_Tab)
    application.processEvents()


def accept() -> None:
    flow = window._quiet_placement
    if flow is not None and not flow._measure_accept.isHidden():
        log("KLICK Übernehmen (Maßgruppe), enabled=", flow._measure_accept.isEnabled())
        flow._measure_accept.click()
    else:
        log("KLICK Übernehmen (Panel), enabled=", window.feature_panel._apply.isEnabled())
        window.feature_panel._apply.click()
    idle(1.0)


def open_model() -> None:
    previous = window.session.last_result
    window.open_path(MODEL)
    deadline = time.monotonic() + 240
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
    window.setWindowTitle("PRÜFSTAND Langloch")


def _signal_log(name):
    return lambda *args: log("  SIGNAL", name, [round(a, 3) if isinstance(a, float) else a for a in args])


for _name in ("slotProposed", "slotDragged", "featureMoveProposed", "featureTurnProposed", "slotStarted"):
    getattr(window.viewport, _name).connect(_signal_log(_name))

try:
    open_model()
    log("geöffnet:", MODEL.name)
    exec(Path(SCRATCH / f"scenario_{SCENARIO}.py").read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    import traceback

    log("AUSNAHME")
    traceback.print_exc(file=LOG)
finally:
    log("Geschlossene Dialoge:", closed)
    try:
        window.session.modified = False
    except Exception:  # noqa: BLE001
        pass
    try:
        window.release()
        window.viewport.release_renderer()
        window.hide()
        for _ in range(10):
            application.processEvents()
    except Exception:  # noqa: BLE001
        pass
    LOG.flush()
    os._exit(0)
