"""Vergleicht AO, Körperkanten und Hüllenschatten am gleichen nativen VTK-Bild.

Privater Diagnosehelfer: verändert keine Quelle und keine Projektdatei.
Der Elternprozess hält den tatsächlichen Prozessausgang getrennt fest.
"""
from __future__ import annotations

import argparse
import dataclasses
import faulthandler
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
import uuid

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ssao-pass-probe", action="store_true")
    parser.add_argument("--ssao-edge-probe", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    project = args.project.resolve(strict=True)
    output = args.output.resolve()
    if not args.worker:
        output.mkdir(parents=True, exist_ok=False)
        command = [sys.executable, str(Path(__file__).resolve()), "--source", str(source),
                   "--project", str(project), "--output", str(output), "--worker"]
        if args.ssao_pass_probe:
            command.append("--ssao-pass-probe")
        if args.ssao_edge_probe:
            command.append("--ssao-edge-probe")
        run_id = uuid.uuid4().hex
        record = {"run_id": run_id, "command": command, "source": str(source),
                  "project": str(project), "helper_sha256": digest(Path(__file__)),
                  "started_at": time.time()}
        with (output / "run.log").open("w", encoding="utf-8") as log:
            try:
                run = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT,
                    env=dict(os.environ, SOLIDON_AB_RUN_ID=run_id), timeout=180,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                record["exit"] = run.returncode
            except subprocess.TimeoutExpired:
                record.update(exit=124, process_timeout=True)
        record["finished_at"] = time.time()
        (output / "process.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False))
        return int(record["exit"] != 0)

    manifest_path = source / "audit-source-manifest.json"
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))["final_app_files_sha256"]
    actual = {name: digest(source / name) for name in expected}
    if actual != expected:
        raise RuntimeError("Die gewählte Quelle stimmt nicht mit ihrem eingefrorenen Manifest überein")
    os.environ["SOLIDON_RENDERER"] = "vtk"
    os.environ.pop("QT_QPA_PLATFORM", None)
    for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        os.environ[key] = str(output / "profile" / key)
    sys.path.insert(0, str(source))
    faulthandler.enable()
    faulthandler.dump_traceback_later(60, repeat=True)
    watchdog = threading.Timer(150, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()

    from PySide6.QtCore import QCoreApplication, QEvent, QPoint
    from PySide6.QtTest import QTest
    from shiboken6 import isValid
    from app.core.bootstrap import load_operations
    from app.ui.settings import UiSettings, save_settings
    save_settings(UiSettings(first_run_done=True, language="de", check_for_updates=False))
    load_operations()
    from app.ui.app import build_application
    from tools.window_bench import shutdown_window

    app, window = build_application(["solidon-vtk-visual-ab"])
    window.resize(1600, 1000)
    window.show()
    window.activateWindow()
    view = window.viewport
    result = {"run_id": os.environ["SOLIDON_AB_RUN_ID"], "source": str(source),
              "manifest_sha256": digest(manifest_path), "source_files_sha256": actual,
              "project": str(project), "project_sha256": digest(project),
              "platform": app.platformName(), "cases": [], "complete": False}

    def write():
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    def pump(seconds):
        deadline = time.perf_counter() + seconds
        while True:
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            if time.perf_counter() >= deadline:
                return
            time.sleep(.002)

    def ready():
        deadline = time.perf_counter() + 60
        while window.session.last_result is None or view._scene_worker is not None:
            if time.perf_counter() > deadline:
                raise RuntimeError("Die Szene wurde nicht fertig aufgebaut")
            pump(.02)
        pump(.35)

    code = 0
    explicit_pass = None
    try:
        pump(.3)
        window.session.open_project(project)
        ready()
        view.set_display_mode("solid")
        view.set_feature_overlay(False)
        view.select_feature(None)
        next(action for action in window._theme_group.actions() if action.data() == "light").trigger()
        ready()
        renderer = view.renderer
        if app.platformName() != "windows" or renderer is None or not renderer.widget.isVisible():
            raise RuntimeError("Kein sichtbares natives VTK-Fenster")
        renderer.widget.setFocus()
        QTest.mouseMove(window.menuBar(), QPoint(800, 10))
        pump(.3)
        original_pose = dataclasses.asdict(renderer.camera_pose())
        original_parallel = renderer.parallel_projection()
        original_scale = renderer.parallel_scale()
        original_ao = bool(renderer.renderer.GetUseSSAO())
        edges = view._edge_actors
        edge_items = edges.values() if isinstance(edges, dict) else edges
        edge_states = [(item, item.visible()) for item in edge_items]
        shadow_states = [(item, item.visible()) for item in view._shadow_actors]
        result.update(camera=original_pose, canvas_size=renderer.view_size(),
                      parallel=original_parallel, parallel_scale=original_scale,
                      original_ao=original_ao, edge_items=len(edge_states), shadow_items=len(shadow_states),
                      ao_radius=renderer.renderer.GetSSAORadius(), ao_bias=renderer.renderer.GetSSAOBias(),
                      ao_kernel=renderer.renderer.GetSSAOKernelSize())
        cases = (
            ("01-original", False, False, False),
            ("02-only-ao-off", True, False, False),
            ("03-only-edges-off", False, True, False),
            ("04-only-shadows-off", False, False, True),
            ("05-ao-and-edges-off", True, True, False),
            ("06-original-restored", False, False, False),
        )
        ao_pass = None
        original_bias = renderer.renderer.GetSSAOBias()
        precision_bias = original_bias
        if args.ssao_pass_probe or args.ssao_edge_probe:
            from vtkmodules.vtkRenderingOpenGL2 import (
                vtkCameraPass, vtkLightsPass, vtkOpaquePass, vtkOpenGLFXAAPass,
                vtkOrderIndependentTranslucentPass, vtkOverlayPass, vtkRenderPassCollection,
                vtkSequencePass, vtkSSAOPass, vtkTranslucentPass, vtkVolumetricPass,
            )

            def sequence(*passes):
                collection = vtkRenderPassCollection()
                for render_pass in passes:
                    collection.AddItem(render_pass)
                sequence_pass = vtkSequencePass()
                sequence_pass.SetPasses(collection)
                return sequence_pass

            # Der innere Kamerapass zeichnet den Verlauf in den AO-Farbpuffer.
            opaque_camera = vtkCameraPass()
            opaque_camera.SetDelegatePass(vtkOpaquePass())
            ao_pass = vtkSSAOPass()
            ao_pass.SetDelegatePass(opaque_camera)
            ao_pass.SetRadius(renderer.renderer.GetSSAORadius())
            ao_pass.SetKernelSize(renderer.renderer.GetSSAOKernelSize())
            ao_pass.SetBlur(renderer.renderer.GetSSAOBlur())
            translucent = vtkOrderIndependentTranslucentPass()
            translucent.SetTranslucentPass(vtkTranslucentPass())
            geometry = sequence(vtkLightsPass(), ao_pass, translucent)
            if renderer.renderer.GetUseFXAA():
                antialias = vtkOpenGLFXAAPass()
                antialias.SetDelegatePass(geometry)
                geometry = antialias
            explicit_pass = vtkCameraPass()
            explicit_pass.SetDelegatePass(sequence(geometry, vtkVolumetricPass(), vtkOverlayPass()))
            clipping = renderer.renderer.GetActiveCamera().GetClippingRange()
            precision_bias = max(original_bias, math.ldexp(1.0, math.frexp(max(clipping))[1] - 11))
            result.update(clipping_range=clipping, precision_bias=precision_bias,
                          precision_basis="Eine RGBA16F-Abstandsstufe an der Fernebene; Gegenprobe, keine Produktvorgabe")
            cases = tuple((name, False, False, False) for name in (
                "01-built-in-original", "02-built-in-precision-bias", "03-explicit-original-bias",
                "04-explicit-precision-bias", "05-explicit-double-precision-bias",
                "06-only-ao-off", "07-built-in-original-restored"))
            if args.ssao_edge_probe:
                cases = (
                    ("01-explicit-precision-bias", False, False, False),
                    ("02-explicit-precision-bias-edges-off", False, True, False),
                    ("03-explicit-precision-bias-restored", False, False, False),
                    ("04-only-ao-off", True, False, False),
                )

        for name, ao_off, edges_off, shadows_off in cases:
            renderer.renderer.SetUseSSAO(original_ao and not ao_off)
            if args.ssao_pass_probe or args.ssao_edge_probe:
                explicit = "explicit" in name
                bias = original_bias if "original" in name else precision_bias
                if "double" in name:
                    bias *= 2
                renderer.renderer.SetPass(explicit_pass if explicit else None)
                renderer.renderer.SetSSAOBias(bias)
                if ao_pass is not None:
                    ao_pass.SetBias(bias)
                renderer.renderer.SetUseSSAO("only-ao-off" not in name)
            for item, visible in edge_states:
                item.set_visible(visible and not edges_off)
            for item, visible in shadow_states:
                item.set_visible(visible and not shadows_off)
            renderer.render()
            pump(.2)
            pixmap = window.screen().grabWindow(window.winId())
            if pixmap.isNull() or not pixmap.save(str(output / (name + ".png"))):
                raise RuntimeError("Die native Bildschirmaufnahme ist leer oder wurde nicht gespeichert")
            pose_unchanged = dataclasses.asdict(renderer.camera_pose()) == original_pose
            projection_unchanged = (renderer.parallel_projection() == original_parallel
                and renderer.parallel_scale() == original_scale)
            result["cases"].append({"name": name, "ao": bool(renderer.renderer.GetUseSSAO()),
                "edge_visibility": [item.visible() for item, _ in edge_states],
                "shadow_visibility": [item.visible() for item, _ in shadow_states],
                "camera_unchanged": pose_unchanged, "projection_unchanged": projection_unchanged,
                "explicit_pass": bool(renderer.renderer.GetPass()),
                "bias": renderer.renderer.GetSSAOBias(),
                "canvas_size": renderer.view_size(), "screenshot": name + ".png"})
            write()
            if not pose_unchanged or not projection_unchanged:
                raise RuntimeError("Die Kamera änderte sich zwischen den Vergleichsbildern")
        result["source_unchanged"] = all(digest(source / name) == value for name, value in actual.items())
        result["project_unchanged"] = digest(project) == result["project_sha256"]
        if not result["source_unchanged"] or not result["project_unchanged"]:
            raise RuntimeError("Eine Quelle änderte sich während der Gegenprobe")
        result["complete"] = True
    except BaseException:
        result["fatal"] = traceback.format_exc()
        code = 1
    finally:
        try:
            if explicit_pass is not None:
                renderer.window.MakeCurrent()
                explicit_pass.ReleaseGraphicsResources(renderer.window)
                renderer.renderer.SetPass(None)
            window.session._dirty = False
            shutdown_window(window, app)
            result["closed"] = not isValid(window) or not window.isVisible()
            if not result["closed"]:
                code = 1
        except BaseException:
            result["shutdown_error"] = traceback.format_exc()
            code = 1
        write()
        watchdog.cancel()
        faulthandler.cancel_dump_traceback_later()
    return code


if __name__ == "__main__":
    sys.exit(main())
