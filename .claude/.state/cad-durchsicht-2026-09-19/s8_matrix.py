"""S8: Bauart-Matrix — welche Operation macht aus einem exakten Körper ein Netz?

Grundlage je Op: frisches Dokument, ``create_brep_box`` 40×30×10, dann
``drill_brep_hole`` Ø5 von oben. Danach die Op mit ihren Vorgaben, ``at_feature``
auf die Bohrung beziehungsweise eine Fläche gesetzt. Zusätzlich der
Sechs-Schritte-Kundenweg aus Konzept §5.1.
"""

import dataclasses
import sys
import time
import _iso  # noqa: F401

from app.core import bootstrap
from app.core.registry import REGISTRY

bootstrap.load_operations()

from app.core.knowledge.profiles import make_profile  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402

PROFILE = make_profile("centauri-carbon-2", "petg")


def fresh():
    project = new_project("centauri-carbon-2", "petg")
    doc = project.document
    h = History(doc)
    h.apply("Quader", [OperationDraft(op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 10.0})])
    h.apply("Bohrung", [OperationDraft(op="drill_brep_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 10.0})])
    return project, doc, h


def state(project, doc):
    r = evaluate(doc, PROFILE, sources=ProjectSources(project))
    if not r.scene.objects:
        return None, r
    return list(r.scene.objects.values()), r


def first_feature(obj, kind):
    for f in obj.features.values():
        if f.kind == kind:
            return f.id
    return ""


def out(line):
    print(line)
    sys.stdout.flush()


project, doc, h = fresh()
objs, r = state(project, doc)
base = objs[0]
out(f"Grundlage: kind={base.kind} features={ {k: sum(1 for f in base.features.values() if f.kind == k) for k in {f.kind for f in base.features.values()} } }")
HOLE = first_feature(base, "hole")
FACE = first_feature(base, "face")
out(f"HOLE={HOLE} FACE={FACE}")

OVERRIDES = {
    "insert_heatset_m4": {"size": "M4"},
    "countersink_hole": {"z": 10.0},
    "plug_hole": {"z": 10.0},
    "remove_feature": {"sections": "single"},
    "scale_object": {"factor": 2.0},
    "fit_to_size": {"largest": 50.0},
    "push_face": {"distance": 2.0},
    "translate_object": {"dx": 1.0},
    "rotate_object": {"axis": "z", "angle": 30.0},
    "move_feature": {"x": 3.0},
    "duplicate_feature": {"x": 12.0},
    "slot_hole": {"slot_length": 12.0},
    "resize_hole": {"diameter": 7.0},
    "assign_slot": {"slot": 0, "colour": "#ff0000"},
    "paint_slot": {"slot": 1, "colour": "#00ff00"},
}

results = []
specs = sorted(REGISTRY.all(), key=lambda s: (s.category, s.name))
for spec in specs:
    name = spec.name
    if name in ("create_brep_box", "drill_brep_hole"):
        continue
    if spec.consumes == 0 and not getattr(spec, "takes_whole_scene", False):
        results.append((spec.category, name, "erzeugt", "-", "", ""))
        continue
    if getattr(spec, "minimum_inputs", 1) and spec.minimum_inputs > 1:
        results.append((spec.category, name, "übersprungen: braucht mehrere Eingänge", "-", "", ""))
        continue
    params = {}
    try:
        fields = {f.name for f in dataclasses.fields(spec.params)}
    except TypeError:
        fields = set()
    if "at_feature" in fields:
        want = HOLE if ("hole" in spec.applies_to or not spec.applies_to) else ""
        if not want and "face" in spec.applies_to:
            want = FACE
        if not want:
            want = HOLE
        params["at_feature"] = want
    if "face" in fields:
        params["face"] = FACE
    if "at_features" in fields and "at_feature" not in params:
        params["at_features"] = (HOLE,)
    params.update(OVERRIDES.get(name, {}))
    project, doc, h = fresh()
    t0 = time.perf_counter()
    try:
        h.apply(name, [OperationDraft(op=name, inputs=("obj_1",), params=params)])
        objs, r = state(project, doc)
        dt = time.perf_counter() - t0
        codes = sorted({f.code for f in r.scene.report.findings if f.code not in ("arrange.below_bed",)})
        if objs is None or getattr(r, 'stopped_at', None) is not None:
            stop = r.stopped_at
            titles = [getattr(f, "title", "") for f in r.scene.report.findings][:2]
            results.append((spec.category, name, "ANGEHALTEN", "-", f"{dt:.1f}s", f"{stop} {codes} {titles}"[:160]))
            continue
        kinds = [o.kind for o in objs]
        nfeat = [len(o.features) for o in objs]
        verdict = "exakt" if all(k == "brep" for k in kinds) else ("netz" if all(k == "mesh" for k in kinds) else "gemischt")
        results.append((spec.category, name, verdict, f"{kinds}/{nfeat}", f"{dt:.1f}s", ",".join(codes)[:120]))
    except Exception as e:  # noqa: BLE001
        dt = time.perf_counter() - t0
        results.append((spec.category, name, "FEHLER", "-", f"{dt:.1f}s", f"{type(e).__name__}: {str(e)[:120]}"))
    out(f"{results[-1][0]:10} {results[-1][1]:32} {results[-1][2]:12} {results[-1][3]:22} {results[-1][4]:6} {results[-1][5]}")

from collections import Counter  # noqa: E402

out("")
out("Zusammenfassung: " + str(Counter(r[2] for r in results)))
netz = [r[1] for r in results if r[2] == "netz"]
out(f"netz ({len(netz)}): {netz}")
exakt = [r[1] for r in results if r[2] == "exakt"]
out(f"exakt ({len(exakt)}): {exakt}")
out(f"nach Kategorie netz: {Counter(r[0] for r in results if r[2] == 'netz')}")

# Sechs-Schritte-Kundenweg
out("")
out("Kundenweg §5.1:")
project, doc, h = fresh()
objs, r = state(project, doc)
hole = first_feature(objs[0], "hole")
steps = [
    ("fillet_edges", {"radius": 3.0}),
    ("shell_exact", {"wall": 2.0}),
    ("insert_heatset_m4", {"at_feature": hole, "size": "M4"}),
    ("countersink_hole", {"z": 10.0}),
]
for op, params in steps:
    h.apply(op, [OperationDraft(op=op, inputs=("obj_1",), params=params)])
    objs, r = state(project, doc)
    if objs is None:
        out(f"  {op}: ANGEHALTEN {r.stopped_at} {[f.code for f in r.scene.report.findings]}")
        break
    o = objs[0]
    sev = [(f.code, getattr(f, 'severity', '')) for f in r.scene.report.findings if 'mesh' in f.code or 'brep' in f.code]
    out(f"  {op}: kind={o.kind} features={len(o.features)} Befunde={sev}")
    hole = first_feature(o, "hole") or hole

# ungleichförmig skalieren am Netz und am B-Rep
out("")
for creator in ("create_box", "create_brep_box"):
    project = new_project("centauri-carbon-2", "petg")
    doc = project.document
    h = History(doc)
    h.apply("Quader", [OperationDraft(op=creator, params={"width": 40.0, "depth": 30.0, "height": 10.0})])
    h.apply("Skalieren", [OperationDraft(op="scale_object", inputs=("obj_1",), params={"fx": 2.0, "fy": 1.0, "fz": 1.0})])
    objs, r = state(project, doc)
    o = objs[0]
    areas = sorted(round(f.params.get("area", 0), 1) for f in o.features.values())
    out(f"{creator} + scale fx=2: kind={o.kind} features={len(o.features)} Flächeninhalte={areas}")
