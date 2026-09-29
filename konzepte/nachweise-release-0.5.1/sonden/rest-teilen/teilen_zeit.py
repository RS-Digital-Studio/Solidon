"""Sonde RM-266: Nahtsuche von *Modell teilen* — Zeit und Entscheidung.

Aufruf: python teilen_zeit.py <baum> <ausgabe.json> [<datei>] [<drucker>] [--profile <datei>]

Einlesen wie die Anwendung (``import_plan`` + ``evaluate``), dann ``plan_split``
mit denselben Argumenten wie ``Session.auto_split``. Gemessen wird die Zeit von
``plan_split`` und die Summe der Aufrufe von ``best_face_candidate`` und
``_support_after_cut``. Festgehalten wird die Entscheidung: jeder Schritt mit
Ebene, Stiftseite, Verbinderform, dazu die Stiftlagen und jeder Einzelwert der
Stützschätzung (Kandidat, Stiftseite, Volumen), damit vorher/nachher bitgleich
verglichen werden kann.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)
TREE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TREE))

import tempfile  # noqa: E402

HOME = Path(tempfile.mkdtemp(prefix="sonde-rest-teilen-"))
for name in ("APPDATA", "LOCALAPPDATA"):
    (HOME / name).mkdir()
    os.environ[name] = str(HOME / name)

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE)):
    raise SystemExit(f"falscher Baum geladen: {where}")

watchdog = threading.Timer(1500.0, lambda: os._exit(9))
watchdog.daemon = True
watchdog.start()

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.activation import store as activation_store  # noqa: E402

activation_store.DEMO_UNTIL = None
activation_store.TRIAL_FROM = activation_store.DEMO_FROM

from app.core.geom import autosplit  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.split import bed_margin, plan_split  # noqa: E402
from app.core.types import Source  # noqa: E402

args = sys.argv[2:]
profile_out = None
dump_dir = None
if "--dump" in args:
    at = args.index("--dump")
    dump_dir = Path(args[at + 1])
    dump_dir.mkdir(parents=True, exist_ok=True)
    del args[at : at + 2]
if "--profile" in args:
    at = args.index("--profile")
    profile_out = args[at + 1]
    del args[at : at + 2]
out = Path(args[0])
path = Path(args[1]) if len(args) > 1 else Path(r"F:\3D Dateien\parametric-laptop-riser.stl")
printer = args[2] if len(args) > 2 else "centauri-carbon-2"

timing = {"best_face_candidate": [0.0, 0], "_support_after_cut": [0.0, 0], "_best_by_support": [0.0, 0]}
judged: list[dict] = []
faces: list[dict] = []

original_bfc = autosplit.best_face_candidate
original_sac = autosplit._support_after_cut
original_bbs = autosplit._best_by_support


def timed_bfc(mesh, **kwargs):
    if dump_dir is not None:
        import numpy as np

        np.savez(
            dump_dir / f"part_{timing['best_face_candidate'][1]}.npz",
            vertices=np.asarray(mesh.raw.vertices, dtype=float),
            faces=np.asarray(mesh.raw.faces, dtype=np.int64),
        )
    started = time.perf_counter()
    try:
        result = original_bfc(mesh, **kwargs)
    finally:
        timing["best_face_candidate"][0] += time.perf_counter() - started
        timing["best_face_candidate"][1] += 1
    faces.append(
        {
            "triangles": mesh.triangle_count,
            "direction": [repr(v) for v in result.direction],
            "support": repr(result.support_volume),
            "first_layer": repr(result.first_layer_area),
            "footing": repr(result.footing),
            "stable": result.stable,
        }
    )
    return result


def timed_sac(mesh, candidate, profile, **kwargs):
    started = time.perf_counter()
    try:
        result = original_sac(mesh, candidate, profile, **kwargs)
    finally:
        timing["_support_after_cut"][0] += time.perf_counter() - started
        timing["_support_after_cut"][1] += 1
    judged.append(
        {
            "axis": candidate.axis,
            "position": repr(candidate.position),
            "normal": None if candidate.normal is None else [repr(v) for v in candidate.normal],
            "pins_on_b": bool(kwargs.get("pins_on_b", False)),
            "count": kwargs.get("connector_count", 0),
            "support": repr(result),
        }
    )
    return result


def timed_bbs(*a, **kwargs):
    started = time.perf_counter()
    try:
        return original_bbs(*a, **kwargs)
    finally:
        timing["_best_by_support"][0] += time.perf_counter() - started
        timing["_best_by_support"][1] += 1


autosplit.best_face_candidate = timed_bfc
autosplit._support_after_cut = timed_sac
autosplit._best_by_support = timed_bbs

from app.core.geom import pins as pins_module  # noqa: E402
from app.core.slice import analysis as analysis_module  # noqa: E402
from app.core.slice import orientation as orientation_module  # noqa: E402


def plain_timer(module, name):
    original = getattr(module, name)
    timing.setdefault(name, [0.0, 0])

    def timed(*a, **k):
        started = time.perf_counter()
        try:
            return original(*a, **k)
        finally:
            timing[name][0] += time.perf_counter() - started
            timing[name][1] += 1

    setattr(module, name, timed)


for module, name in (
    (autosplit, "_cut_in_two"),
    (autosplit, "_candidate_pool"),
    (pins_module, "add_pins"),
    (pins_module, "plan_pins"),
    (orientation_module, "ranked_orientations"),
    (orientation_module, "judge"),
    (orientation_module, "slice_body"),
    (analysis_module, "_cross_sections"),
    (analysis_module, "_support_volume"),
    (analysis_module, "_measure_all"),
):
    plain_timer(module, name)

payload = path.read_bytes()
project = new_project(printer, "petg")
document = project.document
document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
project.sources["src_1"] = payload
plan = import_plan("src_1", path.name, payload, unit="auto", first_model=True)
History(document).apply("Laden", [plan.draft])
profile = profiles.make_profile(printer, "petg")
sources = ProjectSources(project)
result = evaluate(document, profile, sources=sources, ask=lambda q, c: c[0])
entry = next(iter(result.scene.objects.values()))
mesh = entry.mesh
settings = print_settings.resolve(profile)
margin = bed_margin(settings)
profiler = None
if profile_out:
    import cProfile

    profiler = cProfile.Profile()
    profiler.enable()
started = time.perf_counter()
split = plan_split(
    as_mesh_data(mesh),
    entry.id,
    profiles.for_object(profile, entry),
    features=entry.features,
    margin=margin,
)
elapsed = time.perf_counter() - started
if profiler is not None:
    profiler.disable()
    import pstats

    with open(profile_out, "w", encoding="utf-8") as sink:
        stats = pstats.Stats(profiler, stream=sink)
        stats.sort_stats("cumulative").print_stats(70)
        stats.sort_stats("tottime").print_stats(40)

steps = []
for step, draft, connector in zip(split.outcome.cuts, split.drafts, split.connectors, strict=True):
    steps.append(
        {
            "part_index": step.part_index,
            "op": draft.op,
            "params": {key: repr(value) for key, value in sorted(draft.params.items())},
            "pins_on_b": step.pins_on_b,
            "shape": step.connector_shape,
            "pins": None
            if connector is None
            else {
                "positions": [[repr(v) for v in p] for p in connector.positions],
                "diameter": repr(connector.diameter),
                "length": repr(connector.length),
                "normal": [repr(v) for v in connector.normal],
                "shape": connector.shape,
            },
        }
    )
record = {
    "tree": where,
    "model": path.name,
    "printer": printer,
    "triangles": mesh.triangle_count,
    "plan_split_s": elapsed,
    "timing": timing,
    "steps": steps,
    "seated": list(split.seated),
    "parts": len(split.outcome.parts),
    "findings": [f.code for f in split.outcome.findings],
    "judged": judged,
    "faces": faces,
}
out.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"{path.name}: plan_split {elapsed:.2f} s, bfc {timing['best_face_candidate']}, steps {len(steps)}")
os._exit(0)
