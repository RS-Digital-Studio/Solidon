"""RM-232: Merkmalklick bis Ruhe und längste Lücke im Hauptfaden (offscreen).

Aufruf: PROBE_ROOT=<baum> python rm232_probe.py <modell> [--kinds=hole,face] [--count=8]
            [--phases] [--profile=<datei>]

Ruhe heißt: Die Maßgruppe steht (bei Bohrung und Langloch), kein
Platzierungsarbeiter läuft mehr, und 60 ms lang kam kein Ereignis mehr, das
etwas zu tun hatte. Die Lücke misst ein 5-ms-Zeitgeber im Hauptfaden: der
größte Abstand zwischen zwei Takten während des Klicks.
"""

import os
import sys
import tempfile
import time

BAUM = os.environ["PROBE_ROOT"]
sys.path.insert(0, BAUM)
sys.path.insert(0, BAUM + "/tests")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_iso = tempfile.mkdtemp(prefix="solidon-sonde-")
for var in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[var] = _iso
import app.ui  # noqa: E402

assert os.path.normcase(BAUM) in os.path.normcase(app.ui.__file__), app.ui.__file__
from pathlib import Path  # noqa: E402
import statistics  # noqa: E402

from PySide6.QtCore import QElapsedTimer, QLocale, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QLocale.setDefault(QLocale("de"))
qa = QApplication.instance() or QApplication([])
from render_fakes import RecordingRenderer  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

ARGS = dict(a.lstrip("-").split("=", 1) if "=" in a else (a.lstrip("-"), "1") for a in sys.argv[2:])

PHASES: dict[str, float] = {}
TIMELINE: list[tuple[float, float, str, int]] = []
DEPTH = [0]
CALLERS: dict[str, dict[str, int]] = {}
TRACED = {"PlacementFlow.redraw", "MainWindow._update_actions", "FeaturePanel.set_measuring"}
COUNTS: dict[str, int] = {}


def instrument() -> None:
    import functools
    import importlib
    import threading

    main = threading.main_thread()
    targets = [
        ("app.ui.main_window", "MainWindow", "_on_feature_selected"),
        ("app.ui.main_window", "MainWindow", "_on_features_selected"),
        ("app.ui.main_window", "MainWindow", "_show_feature_fields"),
        ("app.ui.main_window", "MainWindow", "_place_from_feature_panel"),
        ("app.ui.main_window", "MainWindow", "_update_actions"),
        ("app.ui.main_window", "MainWindow", "_on_selection"),
        ("app.ui.main_window", "MainWindow", "_on_tree_selection"),
        ("app.ui.viewport", "Viewport", "select_feature"),
        ("app.ui.viewport", "Viewport", "select"),
        ("app.ui.viewport", "Viewport", "set_gizmo"),
        ("app.ui.viewport", "Viewport", "_redraw_feature_patch"),
        ("app.ui.viewport", "Viewport", "_redraw_features"),
        ("app.ui.panels", "FeaturePanel", "show_feature"),
        ("app.ui.panels", "FeaturePanel", "set_measuring"),
        ("app.ui.panels", "ObjectTree", "_restore"),
        ("app.ui.panels", "ObjectTree", "select_feature"),
        ("app.ui.selection_operations", "SelectionOperationsPanel", "set_context"),
        ("app.ui.placement_flow", "PlacementFlow", "redraw"),
        ("app.ui.placement_flow", "PlacementFlow", "_set_values"),
        ("app.ui.placement_flow", "PlacementFlow", "_settle"),
        ("app.ui.placement_flow", "PlacementFlow", "start"),
        ("app.ui.placement_flow", "PlacementFlow", "set_measure_fields"),
        ("app.ui.placement_flow", "PlacementFlow", "_begin_at_feature"),
        ("app.ui.placement_flow", "PlacementFlow", "_request_tool"),
        ("app.ui.panels", "FeaturePanel", "_answers_for"),
        ("app.ui.main_window", "MainWindow", "_body_facts_of_selection"),
        ("app.ui.main_window", "MainWindow", "_lid_reason"),
        ("app.ui.main_window", "MainWindow", "_prepare_slot_change"),
        ("app.ui.viewport", "Viewport", "_feature_geometry"),
        ("app.ui.viewport", "Viewport", "set_slot_handle"),
        ("app.ui.viewport", "Viewport", "_attach_slot_handle"),
    ]
    for module_name, owner, name in targets:
        module = importlib.import_module(module_name)
        cls = getattr(module, owner, None)
        if cls is None or not hasattr(cls, name):
            print("fehlt", owner, name)
            continue
        original = getattr(cls, name)

        def wrap(original=original, label=f"{owner}.{name}"):
            @functools.wraps(original)
            def timed(*args, **kwargs):
                if threading.current_thread() is not main:
                    return original(*args, **kwargs)
                if label in TRACED and "callers" in ARGS:
                    import traceback

                    stack = traceback.extract_stack(limit=7)[:-1]
                    where = " <- ".join(f"{f.name}:{f.lineno}" for f in reversed(stack[-5:]))
                    CALLERS.setdefault(label, {}).setdefault(where, 0)
                    CALLERS[label][where] += 1
                t = time.perf_counter()
                DEPTH[0] += 1
                try:
                    return original(*args, **kwargs)
                finally:
                    DEPTH[0] -= 1
                    PHASES[label] = PHASES.get(label, 0.0) + time.perf_counter() - t
                    COUNTS[label] = COUNTS.get(label, 0) + 1
                    if "timeline" in ARGS:
                        TIMELINE.append((t, time.perf_counter(), label, DEPTH[0]))

            return timed

        setattr(cls, name, wrap())


WORKER: dict[str, list[float]] = {}


def instrument_worker() -> None:
    import functools
    import threading

    from app.core.scene import placement as placement_module
    from app.core.geom import prepare_ops
    from app.ui import panels as panels_module

    for module, name in (
        (panels_module, "feature_answers"),
        (placement_module, "seat_of"),
        (placement_module, "prepare_surface"),
        (placement_module, "prepare_tool"),
        (placement_module, "at_point"),
        (prepare_ops, "bore_entrance"),
    ):
        original = getattr(module, name)

        def wrap(original=original, label=name):
            @functools.wraps(original)
            def timed(*args, **kwargs):
                t = time.perf_counter()
                try:
                    return original(*args, **kwargs)
                finally:
                    where = "Haupt" if threading.current_thread() is threading.main_thread() else "Arbeiter"
                    WORKER.setdefault(f"{label} [{where}]", []).append(time.perf_counter() - t)
                    if "timeline" in ARGS and where == "Arbeiter":
                        TIMELINE.append((t, time.perf_counter(), f"{label} [Arbeiter]", 0))

            return timed

        setattr(module, name, wrap())


def main() -> None:
    if "phases" in ARGS:
        instrument()
    if "worker" in ARGS:
        instrument_worker()
    path = Path(sys.argv[1])
    kinds = ARGS.get("kinds", "hole,face").split(",")
    count = int(ARGS.get("count", "8"))
    window = MainWindow(Session(), UiSettings())
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.resize(1600, 1000)
    window.show()
    t = time.perf_counter()
    window.open_path(path)
    assert window.session.wait_for_idle(300_000)
    for _ in range(50):
        qa.processEvents()
    print(f"geladen in {time.perf_counter() - t:.2f} s")
    findings_running = window._print_findings.worker is not None
    print(f"Druckbefunde laufen noch: {findings_running}")
    if "wait-findings" in ARGS:
        t_f = time.perf_counter()
        while window._print_findings.worker is not None and time.perf_counter() - t_f < 120:
            qa.processEvents()
            time.sleep(0.005)
        print(f"auf Druckbefunde gewartet: {time.perf_counter() - t_f:.2f} s")
    result = window.session.last_result
    by_kind: dict[str, list] = {}
    for object_id, entry in result.scene.objects.items():
        print(object_id, getattr(entry.mesh, "triangle_count", None), len(entry.features))
        for fid, f in entry.features.items():
            by_kind.setdefault(f.kind, []).append((object_id, fid))
    order = []
    for kind in kinds:
        order += by_kind.get(kind, [])[:2]
    sequence = (order * count)[: max(count, len(order))]

    ticks = []
    clock = QElapsedTimer()
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(clock.elapsed()))
    clock.start()
    timer.start()

    profile = None
    if "profile" in ARGS:
        import cProfile

        profile = cProfile.Profile()

    rows = []
    current = None
    for object_id, fid in sequence:
        if object_id != current:
            window.object_tree.select_object(object_id)
            for _ in range(10):
                qa.processEvents()
            current = object_id
        feature = result.scene.objects[object_id].features[fid]
        ticks.clear()
        start = clock.elapsed()
        if profile is not None:
            profile.enable()
        t0 = time.perf_counter()
        findings_now = window._print_findings.worker is not None
        window.object_tree.select_feature(object_id, fid)
        took = time.perf_counter() - t0
        if profile is not None and "sync" in ARGS:
            profile.disable()
        quiet_since = time.perf_counter()
        deadline = time.perf_counter() + 20.0
        while time.perf_counter() < deadline:
            before = time.perf_counter()
            qa.processEvents()
            flow = window._quiet_placement
            busy = window.session.busy or getattr(window, "_answers_worker", None) is not None or (
                flow is not None
                and (flow._surface_busy or flow._tool_busy or (flow._surface is None and feature.kind in ("hole", "slot")))
            )
            if busy or time.perf_counter() - before > 0.002:
                quiet_since = time.perf_counter()
            if time.perf_counter() - quiet_since > 0.06:
                break
            time.sleep(0.001)
        settled = quiet_since - t0
        if profile is not None:
            profile.disable()
        stamps = [start, *ticks]
        gap = max((b - a for a, b in zip(stamps, stamps[1:], strict=False)), default=0)
        rows.append((fid, feature.kind, took * 1000, settled * 1000, gap))
        if "timeline" in ARGS:
            for begin, end, label, depth in sorted(TIMELINE):
                if begin >= t0 and (end - begin) > 0.0015:
                    print(f"      {(begin - t0) * 1000:7.1f} +{(end - begin) * 1000:6.1f} ms {'  ' * depth}{label}")
            TIMELINE.clear()
        print(f"{fid:14s} {feature.kind:10s} synchron {took * 1000:7.1f} ms  bis Ruhe {settled * 1000:7.1f} ms  längste Lücke {gap:4d} ms  Befunde {'läuft' if findings_now else 'ruhig'}")
    for kind in kinds:
        values = [row for row in rows if row[1] == kind]
        if values:
            later = values[1:] or values
            print(
                f"{kind}: bis Ruhe Median {statistics.median(r[3] for r in later):.1f} ms"
                f" (ohne ersten), erster {values[0][3]:.1f} ms;"
                f" Lücke Median {statistics.median(r[4] for r in later):.0f} ms, max {max(r[4] for r in values)} ms"
            )
    if PHASES:
        n = len(rows)
        for label, total in sorted(PHASES.items(), key=lambda item: -item[1]):
            print(f"  {label:45s} {total / n * 1000:7.1f} ms je Klick  {COUNTS[label] / n:4.1f} Aufrufe")
    for label, callers in CALLERS.items():
        print(label)
        for where, n in sorted(callers.items(), key=lambda item: -item[1]):
            print(f"    {n:3d}  {where}")
    for label, values in sorted(WORKER.items(), key=lambda item: -sum(item[1])):
        print(f"  {label:36s} {len(values):3d} Aufrufe  zusammen {sum(values) * 1000:8.1f} ms  größter {max(values) * 1000:7.1f} ms")
    if profile is not None:
        profile.dump_stats(ARGS["profile"])
    sys.stdout.flush()
    window.release()
    os._exit(0)


main()
