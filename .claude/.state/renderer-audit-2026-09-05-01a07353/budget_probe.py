r"""Misst einen sichtbaren Viewport, getrennt von Importdialog und Erkennung.

Nur ausdrücklich starten; das Anlegen dieser Datei startet keine Messung.
Je Aufruf genau ein Renderer, eine Unterteilungsstufe und ein Anzeigeweg:

    .venv\Scripts\python.exe .claude/.state/renderer-audit-2026-09-05-01a07353/budget_probe.py --renderer gfx --stage 0 --display full

Stufe 0 benutzt Roberts unveränderte Form (197120 Dreiecke beim vorgesehenen
Baum), Stufe 1 und 2 teilen jedes Dreieck vollständig in vier koplanare
Dreiecke: 788480 beziehungsweise 3153920. Keine Reduktion vor der Messung,
keine Erkennung, keine Operationsauswertung und kein Schreiben der Quelle.
``lod`` benutzt die aktuelle reguläre Viewport-Aufbereitung; ``full`` liefert
das Originalnetz als bereits vorbereitete Szene. Globale Grenzwerte bleiben.
GPU-Fertig bedeutet abgeschlossene Befehle, nicht Zeitpunkt des OS-Scanouts.
``--appearance solid-no-edges`` unterdrückt nur für diesen Prüfstand die
Körperkanten: alle Stufen zeichnen dieselbe gefüllte Darstellungsart. Vorgabe
``product`` misst weiterhin die unveränderte normale Darstellung samt ihren
Kantengrenzen. Synchronisierte Bildlatenzen enthalten den Abschlussmarker;
sie sind keine reinen GPU-Ausführungszeiten.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import threading
import time
import traceback
from types import SimpleNamespace
from typing import Any
from run_context import cpu_context, cpu_snapshot


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
DEFAULT_SOURCE = Path(r"C:\Users\rober\Downloads\tree_with_tray_stl.stl")
CODE_FILES = (
    "app/ui/viewport.py",
    "app/ui/render/api.py",
    "app/ui/render/gfx_renderer.py",
    "app/ui/render/gfx_occlusion.py",
    "app/ui/render/gfx_lines.py",
    "app/ui/render/vtk_renderer.py",
    "app/ui/render/choice.py",
    "tools/window_bench.py",
    "constraints.txt",
)


def digest(path: Path) -> str:
    """Eine Datei blockweise lesen, ohne große Dateien zusätzlich zu halten."""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def command(arguments: list[str], timeout: float = 10) -> dict[str, Any]:
    """Diagnosebefehle ohne zusätzliches Windows-Fenster ausführen."""
    try:
        done = subprocess.run(
            arguments,
            cwd=REPOSITORY,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return {
            "exit_code": done.returncode,
            "stdout": done.stdout.strip(),
            "stderr": done.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as problem:
        return {"unavailable": str(problem)}


def distribution(values: list[float]) -> dict[str, Any]:
    """Sekunden als Millisekunden; p95 ist der beobachtete nächste Rang."""
    if not values:
        return {"count": 0, "median_ms": None, "p95_ms": None, "max_ms": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "median_ms": statistics.median(values) * 1000,
        "p95_ms": ordered[math.ceil(0.95 * len(values)) - 1] * 1000,
        "max_ms": max(values) * 1000,
        "samples_ms": [v * 1000 for v in values],
    }


def main() -> int:
    global REPOSITORY
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--renderer", choices=("gfx", "vtk"), required=True)
    parser.add_argument("--stage", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--display", choices=("full", "lod"), required=True)
    parser.add_argument(
        "--appearance",
        choices=("product", "solid-no-edges"),
        default="product",
        help="normale Produktdarstellung oder einheitlich gefüllt ohne Körperkanten",
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--codebase", type=Path, default=REPOSITORY)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--frames", type=int, default=40)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--nvidia-smi", action="store_true")
    parser.add_argument("--vtk-swap-control", type=int, choices=(-1, 0, 1))
    args = parser.parse_args()
    REPOSITORY = args.codebase.resolve(strict=True)
    if not (REPOSITORY / "app/ui/viewport.py").is_file():
        parser.error("Der Quellstand enthält keinen Solidon-Viewport")
    if args.frames < 1 or args.timeout <= 0:
        parser.error("Bildzahl und Zeitbudget müssen positiv sein")
    source = args.source.resolve(strict=True)
    if source.suffix.lower() != ".stl":
        parser.error("Diese kontrollierte Messreihe erwartet genau eine STL")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    output = (
        args.output
        or HERE
        / "budget-results"
        / f"{stamp}-{args.renderer}-s{args.stage}-{args.display}-{args.appearance}"
    ).resolve()
    if not output.is_relative_to(HERE):
        parser.error("Die Ergebnisablage muss innerhalb dieses Auditordners liegen")
    output.mkdir(parents=True, exist_ok=False)
    result: dict[str, Any] = {
        "schema_version": 2,
        "probe_files_sha256": {name: digest(HERE / name) for name in ("budget_probe.py", "run_context.py")},
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "complete": False,
        "phase": "vorbereiten",
        "arguments": vars(args)
        | {"source": str(source), "output": str(output), "codebase": str(REPOSITORY)},
        "scope": "Sichtbarer bestehender Viewport; keine vollständige Kundenbedienung",
        "excluded": ["Merkmalerkennung", "Operationsauswertung", "Importdialog", "Schnitt"],
        "p95_method": "nearest-rank",
        "gpu_completion": "Synchronisierte Bildlatenz bis Queue-Abschluss; kein Scanoutnachweis",
        "timing_semantics": {
            "render_call_seconds": "CPU-Aufruf inklusive Treiber, möglicher interner Wartezeit und Präsentation",
            "completion_marker_seconds": "Abschlusswartezeit plus Messaufwand; GFX erzeugt/mappt einen 4-Byte-Staging-Buffer, VTK ruft WaitForCompletion",
            "synchronized_frame_seconds": "Renderaufruf plus Abschlussmarker; keine reine GPU-Ausführungszeit",
            "camera_frames": "Kamerastellung plus synchronisiertes Bild und Qt-Ereignisverarbeitung; ohne abschließende Kamerarückstellung",
            "synchronized_camera_fps": "Kamerastellungen geteilt durch gemessene Gesamtzeit; kein Monitor-FPS- oder Scanoutnachweis",
            "marker_overhead_subtracted": False,
        },
        "python": sys.version,
        "platform": platform.platform(),
        "timings": {},
        "source_sha256_before": digest(source),
        "source_size": source.stat().st_size,
        "code_sha256_before": {
            name: digest(REPOSITORY / name) for name in CODE_FILES if (REPOSITORY / name).is_file()
        },
        "git_head": command(["git", "rev-parse", "HEAD"]),
        "git_state": command(["git", "status", "--short", "--", *CODE_FILES]),
        "probe_sha256": digest(Path(__file__)),
    }

    def save(phase: str | None = None) -> None:
        """Jeder beendete Abschnitt hinterlässt einen lesbaren Zwischenstand."""
        if phase is not None:
            result["phase"] = phase
        temporary = output / "result.next.json"
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        temporary.replace(output / "result.json")
        print(result["phase"], flush=True)

    save()

    def timed_out() -> None:
        """Ein hartes Zeitlimit bleibt als eigener Befund erhalten."""
        (output / "timeout.json").write_text(
            json.dumps(
                {
                    "timeout_seconds": args.timeout,
                    "phase": result["phase"],
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }
            ),
            encoding="utf-8",
        )
        os._exit(124)

    watchdog = threading.Timer(args.timeout, timed_out)
    watchdog.daemon = True
    watchdog.start()
    application = view = None
    heartbeat = None
    original_render = original_apply = original_worker = original_edges = None
    phase = "aufbau"
    beats: list[tuple[str, float]] = []
    render_times: list[dict[str, Any]] = []
    worker_times: list[float] = []
    apply_times: list[float] = []
    status = 1
    try:
        sys.path.insert(0, str(REPOSITORY))
        os.environ["SOLIDON_RENDERER"] = args.renderer
        os.environ.pop("QT_QPA_PLATFORM", None)
        profile = output / "profile"
        for variable in (
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_DATA_HOME",
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
        ):
            os.environ[variable] = str(profile / variable)
        import numpy as np
        import trimesh
        from tools.window_bench import drag_frames, working_set_mb

        result["packages"] = {}
        for name in ("numpy", "trimesh", "PySide6", "vtk", "pygfx", "wgpu", "rendercanvas"):
            try:
                result["packages"][name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                result["packages"][name] = None

        def rss() -> float | None:
            """Nicht verfügbare RSS-Werte bleiben null statt ungültigem JSON-NaN."""
            value = working_set_mb()
            return value if math.isfinite(value) else None

        result["rss_before_load_mib"] = rss()
        began = time.perf_counter()
        raw = trimesh.load_mesh(source, process=True)
        if not isinstance(raw, trimesh.Trimesh) or not len(raw.faces):
            raise ValueError("Die Quelle muss genau ein nichtleeres Dreiecksnetz liefern")
        result["timings"]["stl_load_normalize_seconds"] = time.perf_counter() - began
        source_bounds = np.asarray(raw.bounds).copy()
        count = len(raw.faces)
        result["source_triangles"] = count
        result["source_vertices"] = len(raw.vertices)
        result["subdivision"] = []
        for step in range(args.stage):
            began = time.perf_counter()
            vertices, faces = trimesh.remesh.subdivide(raw.vertices, raw.faces)
            raw = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            expected = count * 4 ** (step + 1)
            if len(raw.faces) != expected or not np.allclose(
                raw.bounds, source_bounds, atol=1e-12, rtol=0
            ):
                raise AssertionError("Vollständige Unterteilung hat Zahl oder Hüllmaße verändert")
            result["subdivision"].append(
                {
                    "level": step + 1,
                    "triangles": len(raw.faces),
                    "seconds": time.perf_counter() - began,
                }
            )
        result["input_triangles"] = len(raw.faces)
        result["input_vertices"] = len(raw.vertices)
        result["bounds_mm"] = source_bounds.tolist()
        value = hashlib.sha256()
        for array in (np.ascontiguousarray(raw.vertices), np.ascontiguousarray(raw.faces)):
            value.update(memoryview(array).cast("B"))
        result["derived_geometry_sha256"] = value.hexdigest()
        result["rss_after_subdivision_mib"] = rss()
        save("geometrie-vorbereitet")

        from PySide6.QtCore import QCoreApplication, QEvent, QTimer
        from PySide6.QtWidgets import QApplication
        from app.core.geom.mesh import MeshData
        from app.core.scene.evaluate import EvaluationResult
        from app.core.types import Scene, SceneObject
        from app.ui.viewport import (
            DISPLAY_DECIMATION_ABOVE,
            DISPLAY_DECIMATION_TARGET,
            Viewport,
            _PreparedScene,
            _SceneMeshWorker,
        )

        result["lod_policy"] = {
            "above_triangles": DISPLAY_DECIMATION_ABOVE,
            "target_triangles": DISPLAY_DECIMATION_TARGET,
            "global_limits_changed": False,
        }
        application = QApplication([])
        if application.platformName() != "windows":
            raise RuntimeError("Diese Messreihe verlangt ein echtes Windows-Fenster")
        began = time.perf_counter()
        view = Viewport()
        if args.appearance == "solid-no-edges":
            original_edges = view._draw_feature_edges

            def skip_feature_edges(*values: Any, **options: Any) -> None:
                """Nur dieses Messfenster vergleicht alle Stufen ohne Körperkanten."""

            view._draw_feature_edges = skip_feature_edges
        view.resize(1600, 900)
        view.show()
        view.activateWindow()

        def drain(seconds: float) -> None:
            """Qt pumpen und den Python-Arbeitsfäden den GIL zurückgeben."""
            end = time.perf_counter() + seconds
            while time.perf_counter() < end:
                application.processEvents()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                time.sleep(0.002)

        drain(0.5)
        renderer = view.renderer
        if renderer is None or not renderer.widget.isVisible():
            raise RuntimeError("Der gewünschte Renderer zeigt kein sichtbares Widget")
        if min(renderer.view_size()) <= 0:
            raise RuntimeError(
                f"Keine messbare Grafikfläche: Viewport {view.size()}, Renderer {renderer.view_size()}"
            )
        if (args.renderer == "gfx") != (type(renderer).__name__ == "GfxRenderer"):
            raise RuntimeError("Die tatsächliche Rendererwahl weicht vom Auftrag ab")
        if args.vtk_swap_control is not None:
            if args.renderer != "vtk":
                raise ValueError("SwapControl-Vergleich ist nur für VTK vorgesehen")
            supported = getattr(renderer.window, "SetSwapControl", None)
            if supported is None:
                raise RuntimeError("Diese VTK-Plattform bietet keinen SwapControl-Aufruf")
            renderer.window.MakeCurrent()
            accepted = bool(supported(args.vtk_swap_control))
            result["swap_control_probe"] = {"requested": args.vtk_swap_control, "accepted": accepted}
            if not accepted:
                raise RuntimeError("Der Treiber nimmt den angeforderten SwapControl-Wert nicht an")
        result["renderer_class"] = type(renderer).__name__
        result["view_device_pixels"] = list(renderer.view_size())
        result["widget_logical_pixels"] = [renderer.widget.width(), renderer.widget.height()]
        result["device_pixel_ratio"] = renderer.widget.devicePixelRatioF()
        result["timings"]["visible_viewport_build_seconds"] = time.perf_counter() - began
        if args.renderer == "gfx":
            result["adapter_info"] = dict(renderer._renderer._device.adapter.info)

        def gpu_done() -> None:
            """Backendgerechter Abschlussmarker, ohne vollständiges Bildrücklesen."""
            if args.renderer == "gfx":
                # Der Queue-Callback in wgpu 0.32.0 passt nicht zur C-Signatur.
                # Ein geordneter kleiner Readback wartet auf dieselbe Queue.
                import wgpu

                device = renderer._renderer._device
                buffer = getattr(renderer, "_audit_fence_buffer", None)
                if buffer is None:
                    buffer = device.create_buffer(
                        size=4, usage=wgpu.BufferUsage.COPY_SRC | wgpu.BufferUsage.COPY_DST
                    )
                    renderer._audit_fence_buffer = buffer
                device.queue.write_buffer(buffer, 0, b"\x00\x00\x00\x00")
                device.queue.read_buffer(buffer)
                result["gpu_completion_method"] = "ordered_4_byte_readback"
            else:
                renderer.window.WaitForCompletion()
                result["gpu_completion_method"] = "vtk_WaitForCompletion"

        original_render = renderer.render

        def finished_render() -> None:
            """Renderaufruf und Abschlussmarker samt Messaufwand getrennt aufzeichnen."""
            start = time.perf_counter()
            original_render()
            submitted = time.perf_counter()
            gpu_done()
            ended = time.perf_counter()
            render_times.append(
                {
                    "phase": phase,
                    "render_call_seconds": submitted - start,
                    "completion_marker_seconds": ended - submitted,
                    "synchronized_frame_seconds": ended - start,
                }
            )

        renderer.render = finished_render
        original_apply = view._apply_scene

        def timed_apply(*values: Any, **options: Any) -> Any:
            """Aktorbau und erstes fertiges Bild getrennt vom LOD-Arbeiter messen."""
            start = time.perf_counter()
            try:
                return original_apply(*values, **options)
            finally:
                apply_times.append(time.perf_counter() - start)

        view._apply_scene = timed_apply
        original_worker = _SceneMeshWorker.work

        def timed_worker(worker: Any) -> None:
            """Nur die bestehende LOD-/Schnittaufbereitung zeitlich umschließen."""
            start = time.perf_counter()
            try:
                original_worker(worker)
            finally:
                worker_times.append(time.perf_counter() - start)

        _SceneMeshWorker.work = timed_worker
        heartbeat = QTimer(view)
        heartbeat.setInterval(16)
        heartbeat.timeout.connect(lambda: beats.append((phase, time.perf_counter())))
        heartbeat.start()
        failures: list[str] = []
        view.sceneFailed.connect(failures.append)
        mesh = MeshData(raw)
        scene = EvaluationResult(
            scene=Scene(
                objects={
                    "budget": SceneObject(id="budget", name=source.name, mesh=mesh),
                }
            )
        )
        if args.nvidia_smi:
            result["nvidia_before"] = command(
                [
                    "nvidia-smi",
                    "--query-gpu=name,driver_version,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ]
            )
        save("anzeigeaufbau")
        began = time.perf_counter()
        beats.append((phase, began))
        if args.display == "full":
            view._apply_scene(scene, _PreparedScene({"budget": mesh}, {}, False))
        else:
            view.show_scene(scene)
        while view._result is not scene or view._scene_worker is not None:
            if failures:
                raise RuntimeError("; ".join(failures))
            drain(0.02)
        gpu_done()
        beats.append((phase, time.perf_counter()))
        result["timings"]["scene_ready_seconds"] = time.perf_counter() - began
        result["timings"]["lod_worker_seconds"] = worker_times
        result["timings"]["actor_apply_and_first_frame_seconds"] = apply_times
        actor = view._actors["budget"]
        if args.renderer == "vtk":
            displayed = actor.data.GetNumberOfPolys()
        else:
            displayed = len(
                next(
                    obj.geometry.indices.data
                    for obj in actor.objects
                    if hasattr(obj, "_solidon_positions")
                )
            )
        result["displayed_triangles"] = int(displayed)
        result["appearance"] = {
            "policy": args.appearance,
            "display_mode": view.display_mode,
            "feature_edge_actors": len(view._edge_actors),
            "global_limits_changed": False,
            "scope": "reguläre Produktdarstellung einschließlich Kantengrenze"
            if args.appearance == "product"
            else "einheitliche gefüllte Darstellung ohne Körperkanten; übrige Viewport-Effekte bleiben",
        }
        if args.appearance == "solid-no-edges" and (
            view.display_mode != "solid" or view._edge_actors
        ):
            raise AssertionError(
                "Die Skalierungsdarstellung muss gefüllt und ohne Körperkanten sein"
            )
        if args.display == "full" and displayed != len(raw.faces):
            raise AssertionError("Die Vollnetz-Messung zeigt nicht alle Eingangsdreiecke")
        result["rss_after_scene_mib"] = rss()
        result["ambient_occlusion"] = bool(view.ambient_occlusion)
        save("sichtbares-netz-bereit")
        phase = "aufwärmen"
        # Beide Renderer fahren denselben Orbit um dieselben Originalmaße.
        # Automatisches Einpassen darf nicht die Pixelbelegung des Vergleichs
        # allein durch backendabhängige Anfangsrichtungen verändern.
        centre = (source_bounds[0] + source_bounds[1]) / 2.0
        radius = float(np.linalg.norm(source_bounds[1] - source_bounds[0])) / 2.0
        if radius <= 0:
            raise ValueError("Die Quelle hat keine räumliche Ausdehnung")
        direction = np.asarray((1.0, -1.0, 0.75), dtype=float)
        direction /= np.linalg.norm(direction)
        distance = 1.15 * radius / math.sin(math.radians(30.0) / 2.0)
        view.set_projection("perspective")
        view.set_camera_pose(tuple(centre + direction * distance), tuple(centre), (0.0, 0.0, 1.0))
        result["camera_start"] = {
            "pose": view.camera_pose(),
            "view_angle_degrees": renderer.view_angle(),
            "projection": "perspective",
            "orbit_source": "tools.window_bench.drag_frames",
            "restore_render_in_raw_calls": True,
            "frame_timing_scope": f"{args.frames} Kamerastellungen mit GPU-Abschluss und Qt-Ereignissen; Rückstellung separat",
        }
        result["projected_bounds_pixels"] = [
            list(renderer.world_to_display((float(x), float(y), float(z))))
            for x in source_bounds[:, 0]
            for y in source_bounds[:, 1]
            for z in source_bounds[:, 2]
        ]
        beats.append((phase, time.perf_counter()))
        drain(0.3)
        drag_frames(SimpleNamespace(viewport=view), application, 4)
        beats.append((phase, time.perf_counter()))
        phase = "kamerabilder"
        beats.append((phase, time.perf_counter()))
        context_before = cpu_snapshot()
        frames = drag_frames(SimpleNamespace(viewport=view), application, args.frames)
        result["camera_cpu_context"] = cpu_context(context_before)
        beats.append((phase, time.perf_counter()))
        result["camera_frames"] = distribution(frames)
        result["synchronized_camera_fps"] = len(frames) / sum(frames) if frames else None
        result["render_calls"] = render_times
        result["rss_after_frames_mib"] = rss()
        save("kamerabilder-fertig")
        phase = "picks"
        beats.append((phase, time.perf_counter()))
        picks: list[dict[str, Any]] = []
        width, height = renderer.view_size()
        for y in np.linspace(0.2, 0.8, 5):
            for x in np.linspace(0.2, 0.8, 8):
                started = time.perf_counter()
                point = view._world_at(round(float(x) * width), round(float(y) * height))
                ended = time.perf_counter()
                picks.append(
                    {
                        "seconds": ended - started,
                        "x_fraction": float(x),
                        "y_fraction": float(y),
                        "point": list(point) if point else None,
                    }
                )
                application.processEvents()
        beats.append((phase, time.perf_counter()))
        result["picks"] = {
            "timing": distribution([p["seconds"] for p in picks]),
            "hits": sum(p["point"] is not None for p in picks),
            "samples": picks,
            "contains_surface_hit": any(p["point"] is not None for p in picks),
            "scope": "Oberflächen-Picking samt Körperzuordnung; keine Merkmalerkennung",
        }
        phase = "abschluss"
        view.renderer.render()
        application.sync()
        if not view.screen().grabWindow(int(view.winId())).save(str(output / "visible.png")):
            raise RuntimeError("Bildschirmfoto konnte nicht gespeichert werden")
        heartbeat.stop()
        for name in ("aufbau", "aufwärmen", "kamerabilder", "picks"):
            ticks = [at for label, at in beats if label == name]
            gaps = [second - first for first, second in zip(ticks, ticks[1:])]
            result.setdefault("ui_heartbeat", {})[name] = distribution(gaps)
        result["ui_heartbeat"]["requested_interval_ms"] = 16
        result["rss_after_picks_mib"] = rss()
        if args.nvidia_smi:
            result["nvidia_after"] = command(
                [
                    "nvidia-smi",
                    "--query-gpu=name,driver_version,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ]
            )
        result["source_sha256_after"] = digest(source)
        result["code_sha256_after"] = {
            name: digest(REPOSITORY / name) for name in result["code_sha256_before"]
        }
        if result["source_sha256_after"] != result["source_sha256_before"]:
            raise AssertionError("Die Eingangsdatei änderte sich während der Messung")
        if result["code_sha256_after"] != result["code_sha256_before"]:
            raise RuntimeError("Produktcode änderte sich während der Messung; Vergleich ungültig")
        status = 0
    except Exception:
        result["error"] = traceback.format_exc()
        print(result["error"], file=sys.stderr, flush=True)
    finally:
        if heartbeat is not None:
            heartbeat.stop()
        if original_worker is not None:
            _SceneMeshWorker.work = original_worker
        if view is not None:
            try:
                if original_edges is not None:
                    view._draw_feature_edges = original_edges
                fence = getattr(view.renderer, "_audit_fence_buffer", None)
                if fence is not None:
                    fence.destroy()
                view.release()
                view.release_renderer()
                view.close()
                for _ in range(20):
                    application.processEvents()
            except Exception:
                result["shutdown_error"] = traceback.format_exc()
                status = 1
        result["complete"] = status == 0
        result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        save("fertig" if status == 0 else "fehler")
        watchdog.cancel()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
