"""Sonde: Was trifft der Merker über die Körpergrenze nach einer Booleschen?

python probe_local.py <modell> <still|moved> [--cx X --cy Y] [--diameter D]
"""

from __future__ import annotations

import functools
import os
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

PROFILE_DIR = tempfile.mkdtemp(prefix="solidon-oe-")
for variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[variable] = PROFILE_DIR
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True
TREE = Path("F:/3D Druck")
sys.path.insert(0, str(TREE))

import app  # noqa: E402

assert Path(app.__file__).resolve().parent.parent == TREE.resolve(), app.__file__

STAGES = (
    "_one_body",
    "_large_facet_faces",
    "_fitted",
    "_connected_patches",
    "_screening",
    "curvature_jumps",
    "_split_patches_by_curvature",
    "_tangential_pieces",
    "find_helices",
    "_merged_cylinders",
    "_merged_cones",
    "_merged_tori",
    "_read_surface_support",
    "_sphere_candidates",
    "detect_spheres",
    "_torus_candidates",
    "detect_tori",
    "_planar_face_entries",
    "detect_holes",
    "detect_pins",
    "detect_fillets",
    "detect_cones",
    "_face_candidates",
    "detect_edge_loops",
    "_threads_instead_of_phantoms",
    "slots_instead_of_half_bores",
    "patterns_instead_of_cells",
    "_faces_finished_in",
    "_faces_on_a_round_wall",
    "_detect_voids",
    "_partial_cones_folded",
    "_partial_bores_marked",
    "_corners_named_as_fillets",
    "narrowings_marked",
    "detect_curved_faces",
)

spent = {}
calls = Counter()
stack = []
geometry = Counter()
armed = [False]


def watch(module, name):
    original = getattr(module, name, None)
    if original is None:
        print("fehlt:", name)
        return

    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        if not armed[0]:
            return original(*args, **kwargs)
        calls[name] += 1
        if name in stack:
            return original(*args, **kwargs)
        stack.append(name)
        started = time.process_time()
        try:
            return original(*args, **kwargs)
        finally:
            spent[name] = spent.get(name, 0.0) + time.process_time() - started
            stack.pop()

    setattr(module, name, wrapped)


def main():
    model = Path(sys.argv[1])
    variant = sys.argv[2]
    args = sys.argv[3:]
    cx = float(args[args.index("--cx") + 1]) if "--cx" in args else None
    cy = float(args[args.index("--cy") + 1]) if "--cy" in args else None
    diameter = float(args[args.index("--diameter") + 1]) if "--diameter" in args else 6.0

    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.geom import attributes
    from app.core.ingest.plan import import_plan
    from app.core.knowledge import profiles
    from app.core.perceive import features
    from app.core.scene import History, OperationDraft, ResultCache, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from app.i18n import _

    for name in STAGES:
        watch(features, name)

    original_by_geometry = features._by_geometry

    def by_geometry(name, body, support, compute, *read):
        if not armed[0]:
            return original_by_geometry(name, body, support, compute, *read)
        ran = [False]

        def counted():
            ran[0] = True
            return compute()

        value = original_by_geometry(name, body, support, counted, *read)
        geometry[(name, "neu" if ran[0] else "Treffer")] += 1
        return value

    features._by_geometry = by_geometry

    patch_lists = []
    original_connected = features._connected_patches

    def connected(body, faces, *a, **k):
        found = original_connected(body, faces, *a, **k)
        if armed[0]:
            patch_lists.append((body, found))
        return found

    features._connected_patches = connected

    detect_times = []
    original_detect = features.detect

    def detect(mesh, **kwargs):
        started = time.process_time()
        found = original_detect(mesh, **kwargs)
        detect_times.append((mesh.triangle_count, round(time.process_time() - started, 2), len(found)))
        return found

    import importlib

    evaluate_module = importlib.import_module("app.core.scene.evaluate")
    evaluate_module.detect = detect

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    project = new_project("centauri-carbon-2", "petg")
    payload = model.read_bytes()
    suffix = model.suffix.lower()
    project.document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/model{suffix}", sha256="")
    project.sources["src_1"] = payload
    plan = import_plan("src_1", model.name, payload, "mm", first_model=True)
    history = History(project.document)
    history.apply(_("Laden"), [plan.draft])
    cache = ResultCache()
    sources = ProjectSources(project)

    def ask(question, choices):
        for choice in choices:
            if str(choice).startswith("Sofort laden"):
                return choice
        return choices[0]

    def run():
        return evaluate(project.document, profile, sources=sources, cache=cache, ask=ask)

    t0 = time.process_time()
    loaded = run()
    print(f"Laden+Erkennen CPU {time.process_time() - t0:.2f} s; detect {detect_times}", flush=True)
    ids = list(loaded.scene.objects)
    body_before = loaded.scene.objects[ids[0]].mesh
    bounds = body_before.bounds
    print("Koerper", ids, "Dreiecke", body_before.triangle_count, "Merkmale", len(loaded.scene.objects[ids[0]].features))
    print("Huelle min", [round(float(v), 2) for v in bounds.minimum], "max", [round(float(v), 2) for v in bounds.maximum], flush=True)
    if "--repair" in args:
        history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=(ids[0],), params={"self_intersections": True})])
        detect_times.clear()
        t0 = time.process_time()
        repaired = run()
        print(f"Reparieren CPU {time.process_time() - t0:.2f} s; detect {detect_times}", flush=True)
        body_before = repaired.scene.objects[ids[0]].mesh
        print("nach Reparatur Dreiecke", body_before.triangle_count, flush=True)
    if variant == "moved":
        history.apply(_("Verschieben"), [OperationDraft(op="translate_object", inputs=(ids[0],), params={"dx": 5.0})])
        detect_times.clear()
        t0 = time.process_time()
        moved = run()
        print(f"Verschieben CPU {time.process_time() - t0:.2f} s; detect {detect_times}", flush=True)
        body_before = moved.scene.objects[ids[0]].mesh
    if "--at" in args:
        import numpy as np
        raw = body_before.raw
        normals = np.asarray(raw.face_normals)
        areas = np.asarray(raw.area_faces)
        upward = np.flatnonzero(normals[:, 2] > 0.7)
        rank = int(args[args.index("--rank") + 1]) if "--rank" in args else 0
        best = int(upward[np.argsort(-areas[upward], kind="stable")[rank]])
        centre = np.asarray(raw.triangles_center)[best]
        cx, cy = float(centre[0]), float(centre[1])
        print("Bohrstelle", round(cx, 2), round(cy, 2), "Dreieck", best, "Flaeche", round(float(areas[best]), 2), flush=True)
    params = {"diameter": diameter, "height": 400.0, "z": -100.0}
    if cx is not None:
        params["x"] = cx
    if cy is not None:
        params["y"] = cy
    history.apply(_("Zylinder"), [OperationDraft(op="create_cylinder", params=params)])
    cyl = run()
    tool = [k for k in cyl.scene.objects if k not in ids][-1]
    history.apply(_("Abziehen"), [OperationDraft(op="subtract_objects", inputs=(ids[0], tool))])
    detect_times.clear()
    spent.clear()
    calls.clear()
    geometry.clear()
    armed[0] = True
    t0 = time.process_time()
    after = run()
    total = time.process_time() - t0
    armed[0] = False
    body_after = after.scene.objects[ids[0]].mesh
    match = attributes._same_triangles(body_before.raw, body_after.raw)
    kept = int((match >= 0).sum())
    print(f"Abziehen gesamt CPU {total:.2f} s; detect {detect_times}")
    print(
        f"Dreiecke nachher {len(match)}, bitgleich uebernommen {kept} ({kept / max(1, len(match)):.1%}), "
        f"neu {len(match) - kept}; Merkmale {len(after.scene.objects[ids[0]].features)}"
    )
    if patch_lists:
        import numpy as np
        body, patches = max(patch_lists, key=lambda item: sum(len(p) for p in item[1]))
        faces = np.asarray(body.faces)
        fresh = np.zeros(len(faces), dtype=bool)
        if len(faces) == len(match):
            fresh = match < 0
        marked = np.zeros(len(body.vertices), dtype=bool)
        marked[faces[fresh].ravel()] = True
        near = fresh | marked[faces].any(axis=1)
        touched = [p for p in patches if near[np.asarray(p, dtype=np.intp)].any()]
        print(
            f"Flecken {len(patches)} ({sum(len(p) for p in patches)} Dreiecke), beruehrt {len(touched)} "
            f"({sum(len(p) for p in touched)} Dreiecke); Ring um Neues {int(near.sum())} Dreiecke"
        )
    print("Stufen (CPU s, Aufrufe), aeusserste Ebene:")
    for name, value in sorted(spent.items(), key=lambda item: -item[1]):
        print(f"  {name:32s} {value:7.2f}  {calls[name]}")
    print("Merker ueber die Koerpergrenze:")
    for (name, kind), count in sorted(geometry.items()):
        print(f"  {name:28s} {kind:8s} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
