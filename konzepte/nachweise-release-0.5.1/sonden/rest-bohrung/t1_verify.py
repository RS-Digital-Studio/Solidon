"""Aufgabe 1 (RM-248), Nachweis am Produktionsstand gegen den alten Weg — im selben Prozess.

„alt" schaltet den fortgesetzten Deckel und das Werkzeug aus den Flächen ab
(``mouth_cap.mouth_surface`` → None, ``_past_curved_mouths`` → None,
``edit._continued_cap`` → None): genau der Weg von HEAD.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import MODELS, TREE, as_mesh_data, load, np  # noqa: E402

sys.path.insert(0, TREE)
from tests.test_bore_depth import _evaluated  # noqa: E402
from tests.test_feature_moves_keep_shape import BOTH_ENDS, _narrowest_hole, _widened  # noqa: E402

import trimesh  # noqa: E402
from app.core import units  # noqa: E402
from app.core.brep import edit  # noqa: E402
from app.core.geom import mouth_cap, prepare_ops  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.relations import cavity_chains, cavity_surface_indices  # noqa: E402

out = open(Path(__file__).with_suffix(".txt"), "w", encoding="utf-8", buffering=1)


def say(*parts):
    print(*parts, flush=True)
    print(*parts, file=out)


NEW = (mouth_cap.mouth_surface, prepare_ops._past_curved_mouths, edit._continued_cap)


def mode(name: str) -> None:
    if name == "neu":
        mouth_cap.mouth_surface, prepare_ops._past_curved_mouths, edit._continued_cap = NEW
    else:
        mouth_cap.mouth_surface = lambda *a, **k: None
        prepare_ops._past_curved_mouths = lambda *a, **k: None
        edit._continued_cap = lambda *a, **k: None


def warnings(findings):
    return sorted({f.code for f in findings if f.severity in ("warning", "error")})


def delta(before, after):
    own = abs(float(after.mesh.volume)) - abs(float(before.mesh.volume))
    return own


profile = profiles.make_profile("centauri-carbon-2", "petg")
say("Last:", open(Path(__file__).parent / "last.txt").read().strip() if (Path(__file__).parent / "last.txt").exists() else "?")
# 1. Platte mit Zylinder R 40, Rinne R 40 und Naht Ebene-Zylinder unten, beide
# Kerne, versetzen entlang X (Fläche unverändert)
for label in ("Zylinder R 40", "Rinne R 40", "Naht Ebene-Zylinder"):
    for kernel in ("mesh", "brep"):
        source = _widened(kernel, BOTH_ENDS["Zylindersenkung und Fase"], bottom=label)
        bore = _narrowest_hole(source)
        x, y, z = (float(v) for v in bore.params["centre"])
        row = []
        for name in ("alt", "neu"):
            mode(name)
            started = time.perf_counter()
            moved, findings = _evaluated(source, profile, "move_feature", at_feature=bore.id, x=x + 5.0, y=y, z=z)
            removed, rfind = _evaluated(source, profile, "remove_feature", at_feature=bore.id, sections="chain")
            row.append(f"{name}: versetzen {delta(source, moved):+.4f} {warnings(findings)} ({time.perf_counter() - started:.1f} s), entfernen {delta(source, removed):+.3f} {warnings(rfind)}")
        say(f"Platte {label:22s} {kernel}: " + " | ".join(row))
mode("neu")

# 2. Gartenschlauchhalter: Ketten mit gekrümmter Mündung — versetzen entlang der Höhenlinie, kippen, entfernen
_p, prof, result, _t = load(MODELS / "garden-hose-holder.3mf")
entry = next(iter(result.scene.objects.values()))
mesh = as_mesh_data(entry.mesh)
for chain in cavity_chains(entry.features, mesh):
    if chain[0].id not in ("hole_2", "hole_4"):
        continue
    bore = chain[0]
    axis = np.asarray(bore.params["axis"], dtype=float)
    indices = np.unique(np.asarray(cavity_surface_indices(mesh, chain), dtype=np.int64))
    raw = mesh.raw
    patch = trimesh.Trimesh(vertices=raw.vertices, faces=np.asarray(raw.faces)[indices], process=False)
    patch.remove_unreferenced_vertices(); patch.merge_vertices()
    edges = patch.edges_sorted
    single = trimesh.grouping.group_rows(edges, require_count=1)
    points = np.asarray(patch.vertices, dtype=float)
    rings = [points[np.asarray(c)] for c in trimesh.graph.connected_components(edges[single])]
    ring = max(rings, key=lambda r: units.plane_fit(r.tolist())[2] / len(r) ** 0.5)
    normal = np.asarray(units.plane_fit(ring.tolist())[1])
    slope = normal - (normal @ axis) * axis
    across = np.cross(axis, slope / np.linalg.norm(slope))
    across /= np.linalg.norm(across)
    centre = np.asarray(bore.params["centre"], dtype=float)
    target = centre + across
    for name in ("alt", "neu"):
        mode(name)
        results = []
        started = time.perf_counter()
        moved, f1 = _evaluated(entry, prof, "move_feature", at_feature=bore.id, x=float(target[0]), y=float(target[1]), z=float(target[2]))
        results.append(f"versetzen 1 mm Höhenlinie {delta(entry, moved):+.3f} {warnings(f1)} ({time.perf_counter() - started:.1f} s)")
        for angle in (5.0, 15.0):
            turned, f2 = _evaluated(entry, prof, "rotate_feature", at_feature=bore.id, axis="x", angle=angle)
            results.append(f"kippen {angle:.0f}° {delta(entry, turned):+.3f} {warnings(f2)}")
        removed, f3 = _evaluated(entry, prof, "remove_feature", at_feature=bore.id, sections="chain")
        results.append(f"entfernen {delta(entry, removed):+.3f} {warnings(f3)}")
        say(f"Gartenschlauchhalter {bore.id} {name}: " + " | ".join(results))
mode("neu")

# 3. Lochplatte gs-100, 3MF und STEP: hole_3-Kette 1 mm quer (Mündung mit Rundung)
for name in ("pegboard-gs-100-v2.3mf", "pegboard-gs-100-v2.step"):
    _p, prof, result, _t = load(MODELS / name)
    entry = next(iter(result.scene.objects.values()))
    chain = next(c for c in cavity_chains(entry.features, as_mesh_data(entry.mesh)) if any(f.id == "hole_3" for f in c))
    centre = np.asarray(chain[0].params["centre"], dtype=float)
    for label in ("alt", "neu"):
        mode(label)
        results = []
        for across in ((0.0, 0.0, -1.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)):
            target = centre + np.asarray(across)
            moved, findings = _evaluated(entry, prof, "move_feature", at_feature=chain[0].id, x=float(target[0]), y=float(target[1]), z=float(target[2]))
            results.append(f"{delta(entry, moved):+.3f}")
        say(f"{name} {label}: versetzen 1 mm (−z, +z, +x) {' '.join(results)}")
mode("neu")
