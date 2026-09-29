"""Sonde p08: Versetzen am Gartenschlauchhalter übernehmen, wie das Fenster es tut.

Aufruf: python p08_schritte.py <baum> <ausgabe.jsonl> [--pruefen] [<bohrung> ...]

Laden über ``import_plan`` mit Erkennung und Ergebniscache. Dann je Bohrung
(Vorgabe hole_10, hole_4, hole_9) ein Schritt *Merkmal verschieben* 1 mm quer
über ``History.apply`` und die Auswertung in voller Güte mit Erkennung — das
ist „Übernehmen“: Die Vorschau des Dialogs rechnet in der Entwurfsgüte, deren
Ergebnis trägt einen anderen Cacheschlüssel, und nach dem Klick rechnet die
Operation in voller Güte, dann die Erkennung.

Je Schritt eine Zeile: Zeiten (Übernehmen, darin ``detect``),
Dreiecke, Abdruck der Merkmale der Szene (Name, Art, Dreiecke, Maße auf vier
Stellen) und der rohen Erkennung (Bit für Bit).

``--pruefen``: Danach dieselbe Erkennung an einer Kopie des Netzes ganz neu —
ohne Erkennungscache und ohne Merker über die Körpergrenze — und der
Vergleich Bit für Bit mit der gemerkten Antwort. Die Zeiten dieser Läufe
zählen dann nicht (die Prüfung rechnet dazwischen).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baum  # noqa: E402

TREE = _baum.setup(sys.argv[1])
_baum.activation_free()
_WATCHDOG = threading.Timer(2400.0, lambda: os._exit(9))
_WATCHDOG.daemon = True
_WATCHDOG.start()

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.geom.mesh import MeshData, as_mesh_data  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import features as F  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache  # noqa: E402
from app.core.scene.history import OperationDraft  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

evaluate_module = importlib.import_module("app.core.scene.evaluate")
load_operations()
TARGET = Path(sys.argv[2])
CHECK = "--pruefen" in sys.argv
NAMES = [a for a in sys.argv[3:] if not a.startswith("--")] or ["hole_10", "hole_4", "hole_9"]
# ``--zaehlen``: je Schritt, wie oft der Merker über die Körpergrenze traf und
# rechnete — getrennt für die Operation und die Erkennung danach.
# ``--profil=<bohrung>``: ein cProfile um die Erkennung dieses Schritts,
# ``--ganz=<bohrung>`` um das ganze Übernehmen.
SPENT: dict[str, float] = {}
_shipped_detect = evaluate_module.detect


PHASE = {"name": "op", "step": ""}
COUNTS: dict[str, int] = {}
PROFILE_STEP = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--profil=")), None)
WHOLE_STEP = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--ganz=")), None)


def timed_detect(mesh, **kwargs):
    started = time.perf_counter()
    PHASE["name"] = "detect"
    profiler = None
    if PROFILE_STEP is not None and PHASE["step"] == PROFILE_STEP:
        import cProfile

        profiler = cProfile.Profile()
        profiler.enable()
    try:
        return _shipped_detect(mesh, **kwargs)
    finally:
        if profiler is not None:
            profiler.disable()
            profiler.dump_stats(str(TARGET.with_suffix(f".{PROFILE_STEP}.prof")))
        PHASE["name"] = "op"
        SPENT["detect"] = SPENT.get("detect", 0.0) + time.perf_counter() - started


evaluate_module.detect = timed_detect
_shipped_by_geometry = getattr(F, "_by_geometry", None)
if _shipped_by_geometry is not None and "--zaehlen" in sys.argv:

    def counted_by_geometry(name, body, support, compute, *read):
        ran = []

        def watched():
            ran.append(True)
            return compute()

        value = _shipped_by_geometry(name, body, support, watched, *read)
        label = f"{PHASE['name']} {'gerechnet' if ran else 'Treffer'}"
        COUNTS[label] = COUNTS.get(label, 0) + 1
        return value

    F._by_geometry = counted_by_geometry


def rounded_print(found) -> str:
    rows = []
    for feature in found.values():
        params = []
        for key in sorted(feature.params):
            value = feature.params[key]
            if isinstance(value, bool):
                params.append((key, value))
            elif isinstance(value, float):
                params.append((key, round(value, 4)))
            elif isinstance(value, (list, tuple)) and all(isinstance(i, (int, float)) for i in value):
                params.append((key, tuple(round(float(i), 4) for i in value)))
        faces = hashlib.blake2b(np.asarray(sorted(feature.face_indices), dtype=np.int64).tobytes(), digest_size=6).hexdigest()
        rows.append(repr((feature.id, feature.kind, len(feature.face_indices), faces, tuple(params))))
    return json.dumps(sorted(rows))


def exact_print(found) -> str:
    rows = []
    for feature in found.values():
        params = []
        for key in sorted(feature.params):
            value = feature.params[key]
            if isinstance(value, float):
                params.append((key, value.hex()))
            elif isinstance(value, (list, tuple)) and all(isinstance(i, (int, float)) for i in value):
                params.append((key, tuple(float(i).hex() for i in value)))
            elif isinstance(value, (bool, int, str)):
                params.append((key, value))
        faces = hashlib.blake2b(np.asarray(sorted(feature.face_indices), dtype=np.int64).tobytes(), digest_size=6).hexdigest()
        patches = tuple(
            sorted(
                (
                    patch.kind,
                    hashlib.blake2b(np.asarray(sorted(patch.face_indices), dtype=np.int64).tobytes(), digest_size=6).hexdigest(),
                    repr(tuple((k, patch.params[k]) for k in sorted(patch.params))),
                )
                for patch in feature.surface_patches
            )
        )
        rows.append(repr((feature.id, feature.kind, faces, patches, tuple(params))))
    return hashlib.blake2b(repr(sorted(rows)).encode(), digest_size=10).hexdigest()


def fresh_detection(mesh: MeshData):
    """Dieselbe Erkennung an einer Kopie, ohne Erkennungscache und ohne Merker über die Körpergrenze."""
    raw = mesh.raw
    copy = MeshData.of(
        trimesh.Trimesh(
            np.array(raw.vertices, dtype=np.float64, copy=True),
            np.array(raw.faces, dtype=np.int64, copy=True),
            process=False,
        )
    )
    shipped_cached = F._cached_detection
    shipped_geometry = getattr(F, "_by_geometry", None)
    F._cached_detection = lambda key: None
    if shipped_geometry is not None:
        F._by_geometry = lambda name, body, support, compute, *read: compute()
    try:
        return F.detect(copy)
    finally:
        F._cached_detection = shipped_cached
        if shipped_geometry is not None:
            F._by_geometry = shipped_geometry


def main() -> None:
    path = _baum.KUNDE / "garden-hose-holder.3mf"
    payload = path.read_bytes()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
    project.sources["src_1"] = payload
    plan = import_plan("src_1", path.name, payload, unit="auto", first_model=True)
    history = History(project.document)
    history.apply("Laden", [plan.draft])
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    sources = ProjectSources(project)
    cache = ResultCache()
    clock = time.perf_counter()
    result = evaluate(project.document, profile, sources=sources, ask=lambda q, c: c[0], cache=cache)
    entry = next(iter(result.scene.objects.values()))
    record = {
        "tree": TREE.name,
        "step": "laden",
        "seconds": round(time.perf_counter() - clock, 2),
        "triangles": entry.mesh.triangle_count,
        "scene": hashlib.blake2b(rounded_print(entry.features).encode(), digest_size=10).hexdigest(),
    }
    lines = [record]
    print(json.dumps(record), flush=True)
    for step, name in enumerate(NAMES, start=1):
        if name not in entry.features:
            lines.append({"tree": TREE.name, "step": name, "error": "fehlt"})
            continue
        bore = entry.features[name]
        axis = np.asarray(bore.params["axis"], dtype=float)
        helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        across = np.cross(axis, helper)
        across /= np.linalg.norm(across)
        target = np.asarray(bore.params["centre"], dtype=float) + across
        history.apply(
            f"Versetzen {name}",
            [
                OperationDraft(
                    op="move_feature",
                    inputs=(entry.id,),
                    params={"at_feature": bore.id, "x": float(target[0]), "y": float(target[1]), "z": float(target[2])},
                    seed=step,
                )
            ],
        )
        SPENT.clear()
        COUNTS.clear()
        PHASE["step"] = name
        whole = None
        if WHOLE_STEP == name:
            import cProfile

            whole = cProfile.Profile()
            whole.enable()
        clock = time.perf_counter()
        result = evaluate(project.document, profile, sources=sources, ask=lambda q, c: c[0], cache=cache)
        taken = time.perf_counter() - clock
        if whole is not None:
            whole.disable()
            whole.dump_stats(str(TARGET.with_suffix(f".{name}.ganz.prof")))
        entry = next(iter(result.scene.objects.values()))
        mesh = as_mesh_data(entry.mesh)
        raw_detection = F.known_detection(mesh)
        record = {
            "tree": TREE.name,
            "step": name,
            "take": round(taken, 2),
            "detect": round(SPENT.get("detect", 0.0), 2),
            "triangles": entry.mesh.triangle_count,
            "complete": bool(result.complete),
            "codes": sorted({f.code for f in result.scene.report.findings}),
            "scene": hashlib.blake2b(rounded_print(entry.features).encode(), digest_size=10).hexdigest(),
            "scene_rows": rounded_print(entry.features),
            "detection": exact_print(raw_detection) if raw_detection is not None else None,
            "counts": dict(sorted(COUNTS.items())),
        }
        if CHECK and raw_detection is not None:
            clock = time.perf_counter()
            fresh = fresh_detection(mesh)
            record["fresh_seconds"] = round(time.perf_counter() - clock, 2)
            record["fresh_same"] = exact_print(fresh) == record["detection"]
        lines.append(record)
        print(json.dumps({k: v for k, v in record.items() if k != "scene_rows"}), flush=True)
    with TARGET.open("a", encoding="utf-8") as out:
        for line in lines:
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
    os._exit(0)


if __name__ == "__main__":
    main()
