"""S1: Registerzählung und Signaturen der Funktionen, die die weiteren Sonden brauchen."""

import inspect
import _iso  # noqa: F401

from app.core.registry import REGISTRY

print("REGISTRY dir:", [n for n in dir(REGISTRY) if not n.startswith("_")])

try:
    from app.core import bootstrap

    ops = bootstrap.load_operations()
    print("bootstrap.load_operations ->", type(ops), getattr(ops, "__len__", lambda: "?")())
except Exception as e:  # noqa: BLE001
    print("bootstrap fehlt:", repr(e))

specs = None
for attr in ("all", "operations", "specs", "values", "items"):
    if hasattr(REGISTRY, attr):
        try:
            candidate = getattr(REGISTRY, attr)()
            specs = list(candidate.values()) if isinstance(candidate, dict) else list(candidate)
            print(f"REGISTRY.{attr}() -> {len(specs)}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"REGISTRY.{attr} scheiterte:", repr(e))

if specs:
    s0 = specs[0]
    print("Spec-Typ:", type(s0), "Felder:", [n for n in dir(s0) if not n.startswith("_")][:40])
    from collections import Counter

    cats = Counter(getattr(s, "category", "?") for s in specs)
    print("Kategorien:", len(cats), dict(cats))
    print("reversible alle:", all(getattr(s, "reversible", None) for s in specs))
    names = {getattr(s, "name", None): s for s in specs}
    print("Anzahl Ops:", len(names))
    for op in (
        "scale_object", "fit_to_size", "mirror_object", "drill_brep_hole", "countersink_hole",
        "insert_heatset_m4", "resize_hole", "slot_hole", "move_feature", "plug_hole",
        "assign_slot", "paint_slot", "fillet_edges", "shell_exact", "hollow_object",
        "sketch_pocket", "sketch_extrude", "create_torus", "create_cylinder", "remove_feature",
    ):
        s = names.get(op)
        if s is None:
            print(f"  {op}: FEHLT")
            continue
        params = getattr(s, "params", None)
        try:
            if isinstance(params, dict):
                items = list(params.items())
            else:
                items = [(getattr(p, "name", "?"), p) for p in params]
            desc = []
            for n, p in items:
                d = getattr(p, "default", getattr(p, "vorgabe", "?"))
                k = getattr(p, "kind", getattr(p, "type", ""))
                desc.append(f"{n}={d!r}:{k}")
            print(f"  {op} [{getattr(s,'category','?')}] applies_to={getattr(s,'applies_to',None)} params: " + ", ".join(desc))
        except Exception as e:  # noqa: BLE001
            print(f"  {op}: params unlesbar {e!r}: {params!r}"[:400])

from app.core.knowledge.parts import PARTS  # noqa: E402

try:
    print("PARTS.all():", len(PARTS.all()))
except Exception as e:  # noqa: BLE001
    print("PARTS:", repr(e), [n for n in dir(PARTS) if not n.startswith("_")])

from app.core import types as T  # noqa: E402

fk = getattr(T, "FeatureKind", None)
try:
    from typing import get_args

    print("FeatureKind:", len(get_args(fk)), get_args(fk))
except Exception as e:  # noqa: BLE001
    print("FeatureKind:", repr(e), fk)

from app.core.sketch import solver  # noqa: E402

ct = getattr(solver, "_CONSTRAINT_TARGETS", None)
print("_CONSTRAINT_TARGETS:", None if ct is None else (len(ct), sorted(ct) if hasattr(ct, "__iter__") else ct))

# Signaturen für spätere Sonden
from app.core.sketch import edit as sedit  # noqa: E402
from app.core.sketch import planes  # noqa: E402
from app.core.scene import placement  # noqa: E402
from app.core.brep import edit as bedit  # noqa: E402
from app.core.perceive import features as pf  # noqa: E402

for mod, name in (
    (sedit, "project"), (planes, "frame_of"), (placement, "prepare_surface"), (placement, "at_point"),
    (placement, "point_with_distances"), (bedit, "edge_key"), (bedit, "edges_of"), (bedit, "transformed"),
    (bedit, "box"), (bedit, "cut_bore"), (pf, "detect_holes"), (pf, "detect"), (pf, "detect_faces"),
    (pf, "forget_cache"),
):
    fn = getattr(mod, name, None)
    if fn is None:
        print(f"{mod.__name__}.{name}: FEHLT")
    else:
        try:
            print(f"{mod.__name__}.{name}{inspect.signature(fn)}")
        except Exception as e:  # noqa: BLE001
            print(f"{mod.__name__}.{name}: {e!r}")
print("edge_key in:", [m for m in ("app.core.brep.edit",) if hasattr(bedit, "edge_key")])
import app.core.perceive.features as _pf  # noqa: E402

print("forget_cache anderswo:", [n for n in dir(_pf) if "cache" in n.lower()])
