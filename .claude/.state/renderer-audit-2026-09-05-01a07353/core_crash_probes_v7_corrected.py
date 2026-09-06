"""Zwei begrenzte Kerngegenproben; ausschließlich eingefrorene Eingaben lesen."""

from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "core_crash_probes_v7_corrected_manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_inputs(manifest):
    for name, wanted in manifest["input_sha256"].items():
        if sha(Path(name)) != wanted:
            raise ValueError(f"Geänderte Eingabe: {name}")
    source = Path(manifest["source_directory"])
    frozen = json.loads((source / "audit-source-manifest.json").read_text(encoding="utf-8"))
    mismatches = [
        name for name, wanted in frozen["final_app_files_sha256"].items()
        if sha(source / name) != wanted
    ]
    if mismatches:
        raise ValueError(f"Geänderte V7-Quellen: {mismatches}")
    return source


def no_ui():
    return not any(
        name.split(".")[0] in {"PySide6", "PyQt6", "vtk", "vtkmodules", "pygfx", "wgpu"}
        for name in sys.modules
    )


def counter(manifest, out):
    import numpy as np

    from app.core.export.threemf import AssemblyPart, write_assembly
    from app.core.geom.mesh import MeshCodec
    from app.core.scene.cache import _slot_from_data

    result = json.loads(Path(manifest["counter_result"]).read_text(encoding="utf-8"))
    expected = next(c for c in result["checks"] if c["label"] == "Export-Ausgangsszene")
    with zipfile.ZipFile(manifest["counter_project"]) as archive:
        document = json.loads(archive.read("project.json"))
    assert document["print_settings"] is None
    assert document["ops"][-1]["params"] == {"dx": 1.25, "dy": -0.75, "dz": 0.5}
    cache = Path(manifest["counter_cache"])
    index = json.loads((cache / "objects.json").read_text(encoding="utf-8"))
    expected_objects = {entry["id"]: entry for entry in expected["scene"]["objects"]}
    assert set(expected_objects) == {entry["id"] for entry in index["objects"]}
    digest = hashlib.sha256()
    parts = []
    meshes = []
    geometry_before = []
    feature_references = {}
    for entry in sorted(index["objects"], key=lambda value: value["id"]):
        mesh = MeshCodec().loads((cache / entry["mesh"]).read_bytes())
        wanted = expected_objects[entry["id"]]
        body = hashlib.sha256()
        geometry = hashlib.sha256()
        for array in (mesh.raw.vertices, mesh.raw.faces):
            values = np.asarray(array)
            header = str((values.shape, values.dtype.str)).encode()
            body.update(header)
            body.update(values.tobytes())
            geometry.update(header)
            geometry.update(values.tobytes())
        # Der Diskcache steht vor der abschließenden Merkmalszuordnung.
        # Die gespeicherte Szene kann deshalb neue IDs für dieselben Dreiecke tragen.
        transform = np.asarray(index["transform"], dtype=float)
        assert np.allclose(transform[:3, 3], [1.25, -0.75, 0.5], rtol=0, atol=1e-12)
        correspondence = {}
        used = set()
        for fid, feature in wanted["features"].items():
            candidates = []
            for cached_id, cached in entry["features"].items():
                if cached_id in used or cached["kind"] != feature["kind"]:
                    continue
                if len(cached["face_indices"]) != feature["face_count"]:
                    continue
                centre = np.asarray(cached["params"]["centre"], dtype=float)
                moved = transform[:3, :3] @ centre + transform[:3, 3]
                if np.allclose(moved, feature["params"]["centre"], rtol=0, atol=1e-6):
                    candidates.append(cached_id)
            assert len(candidates) == 1, (fid, candidates)
            correspondence[fid] = candidates[0]
            used.add(candidates[0])
        assert used == set(entry["features"])
        assert set(correspondence) == set(wanted["features"])
        feature_references[entry["id"]] = correspondence
        metadata = {
            "id": entry["id"], "name": entry["name"], "kind": entry["kind"],
            "plate": entry["plate"],
            "features": {
                fid: {
                    "kind": feature["kind"], "params": feature["params"],
                    "face_count": feature["face_count"],
                    "face_hash": hashlib.sha256(
                        np.asarray(entry["features"][correspondence[fid]]["face_indices"], dtype=np.int64).tobytes()
                    ).hexdigest(),
                }
                for fid, feature in sorted(wanted["features"].items())
            },
        }
        body.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode())
        digest.update(body.hexdigest().encode())
        assert mesh.triangle_count == wanted["triangles"]
        assert np.allclose(mesh.raw.bounds, wanted["bounds"], rtol=0, atol=1e-10)
        parts.append(AssemblyPart(
            mesh=mesh, name=entry["name"],
            slots=tuple(_slot_from_data(slot) for slot in entry["material_slots"]),
            plate=entry["plate"],
        ))
        meshes.append(mesh)
        geometry_before.append(geometry.hexdigest())
    reconstructed = digest.hexdigest()
    assert reconstructed == expected["fingerprint"], (reconstructed, expected["fingerprint"])
    evidence = {
        "case": "counter", "input_fingerprint": reconstructed,
        "exact_saved_geometry": True,
        "feature_references_final_to_cache": feature_references,
        "fingerprint_method": "Native Meshbytes plus gespeicherte finale Metadaten und Cache-Flächenindizes",
        "call": "app.core.export.threemf.write_assembly",
        "scope": "Identischer XML-/ZIP-Kern; Qt-Arbeiter, Exportvorprüfung und Slicer-Suche sind nicht Teil dieser Gegenprobe.",
        "parts": len(parts), "triangles": [mesh.triangle_count for mesh in meshes],
        "geometry_sha256": geometry_before, "main_thread": threading.get_ident(),
    }
    write(out / "counter.json", evidence)

    def work():
        started = time.perf_counter()
        payload = write_assembly(
            parts, "vollstaendige-szene", across=parts, bed=None,
            project_settings={}, prusa_config={}, stride=0.0,
        )
        path = out / "counter-worker.3mf"
        path.write_bytes(payload)
        return {
            "worker_thread": threading.get_ident(), "export_seconds": time.perf_counter() - started,
            "output": str(path), "output_bytes": len(payload), "output_sha256": sha(path),
        }

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="core-counter") as executor:
        evidence.update(executor.submit(work).result())
    evidence["worker_was_separate"] = evidence["worker_thread"] != evidence["main_thread"]
    after = []
    for mesh in meshes:
        digest = hashlib.sha256()
        for array in (mesh.raw.vertices, mesh.raw.faces):
            values = np.asarray(array)
            digest.update(str((values.shape, values.dtype.str)).encode())
            digest.update(values.tobytes())
        after.append(digest.hexdigest())
    evidence["geometry_unchanged"] = after == geometry_before
    evidence["no_qt_gpu_imported"] = no_ui()
    assert evidence["geometry_unchanged"] and evidence["worker_was_separate"] and no_ui()
    return evidence


def step(manifest, out):
    import numpy as np

    from app.core.brep.step import read

    started = time.perf_counter()
    body = read(Path(manifest["step_original"]).read_bytes())
    mesh = body.to_mesh()
    evidence = {
        "case": "step", "input_sha256": sha(Path(manifest["step_original"])),
        "load_and_tessellate_seconds": time.perf_counter() - started,
        "triangles": mesh.triangle_count, "calls_completed": 0,
        "scope": "Original-STEP einmal gelesen/tesselliert; wiederholte Bounds am selben Solid, ohne UI-Vorgeschichte.",
    }
    write(out / "step.json", evidence)
    reference = None
    samples = []
    for iteration in range(200):
        started = time.perf_counter()
        box = body.bounds
        samples.append((time.perf_counter() - started) * 1000.0)
        values = np.asarray([box.minimum, box.maximum], dtype=float)
        assert np.isfinite(values).all()
        if reference is None:
            reference = values
        else:
            assert np.allclose(values, reference, rtol=0, atol=1e-10)
        evidence["calls_completed"] = iteration + 1
        if (iteration + 1) % 25 == 0:
            write(out / "step.json", evidence)
    evidence.update({
        "bounds": reference.tolist(), "bounds_ms": samples,
        "median_ms": float(np.median(samples)), "p95_ms": float(np.percentile(samples, 95)),
        "no_qt_gpu_imported": no_ui(),
    })
    assert no_ui()
    return evidence


def child(case, out, manifest):
    faulthandler.enable()
    faulthandler.dump_traceback_later(15, repeat=True)
    source = verify_inputs(manifest)
    sys.path.insert(0, str(source))
    os.chdir(source)
    try:
        assert sys.version_info[:2] == (3, 13)
        evidence = counter(manifest, out) if case == "counter" else step(manifest, out)
        verify_inputs(manifest)
        evidence.update({"complete": True, "source_unchanged": True, "python": sys.version})
        write(out / f"{case}.json", evidence)
    except BaseException:
        traceback.print_exc()
        return 1
    finally:
        faulthandler.cancel_dump_traceback_later()
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--child", choices=("counter", "step"))
    parser.add_argument("--case", choices=("counter", "step", "both"), default="both")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = args.out.resolve()
    if args.child:
        return child(args.child, out, manifest)
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    deadline = started + 85.0
    processes = []
    cases = ("counter", "step") if args.case == "both" else (args.case,)
    for case in cases:
        remaining = deadline - time.perf_counter()
        if remaining < 1.0:
            processes.append({"case": case, "skipped": "Gemeinsame 85-Sekunden-Grenze"})
            break
        command = [sys.executable, str(Path(__file__).resolve()), "--out", str(out), "--child", case]
        before = time.perf_counter()
        with (out / f"{case}.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            timeout = False
            try:
                code = process.wait(timeout=min(50.0 if case == "counter" else 35.0, remaining))
            except subprocess.TimeoutExpired:
                timeout = True
                process.kill()
                code = process.wait()
        row = {"case": case, "command": command, "pid": process.pid, "exit": code,
               "timeout": timeout, "seconds": time.perf_counter() - before}
        processes.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    record = {"manifest_sha256": sha(MANIFEST), "script_sha256": sha(Path(__file__)),
              "processes": processes, "elapsed_seconds": time.perf_counter() - started}
    write(out / "processes.json", record)
    return 0 if len(processes) == len(cases) and all(p.get("exit") == 0 for p in processes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
