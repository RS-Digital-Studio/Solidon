"""Kantenteilung ohne Formänderung: beide Nachbardreiecke einer Kante am Mittelpunkt teilen."""
import sys; sys.path.insert(0, r"F:\3D Druck")
import importlib.util
spec = importlib.util.spec_from_file_location("p1", r"F:\3D Druck\.claude\.state\dreieck-reparatur-claude-2026-09-24\sonden\p1_schaden_reparatur.py")
p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
import numpy as np, trimesh
from collections import Counter
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect, forget_cache

def split_edges(mesh, count, seed):
    body = mesh.raw
    vertices = np.asarray(body.vertices).tolist(); faces = np.asarray(body.faces).tolist()
    pairs = np.asarray(body.face_adjacency); edges = np.asarray(body.face_adjacency_edges)
    rng = np.random.default_rng(seed); used = set(); repl = {}
    for row in rng.permutation(len(pairs)).tolist():
        f1, f2 = (int(v) for v in pairs[row])
        if f1 in used or f2 in used: continue
        a, b = (int(v) for v in edges[row])
        m = len(vertices); vertices.append(((np.asarray(vertices[a]) + np.asarray(vertices[b])) / 2).tolist())
        for f in (f1, f2):
            c = faces[f]; i = c.index(a)
            x, y = (a, b) if c[(i + 1) % 3] == b else (b, a)
            z = next(v for v in c if v not in (a, b))
            repl[f] = [[x, m, z], [m, y, z]]
        used.update((f1, f2))
        if len(repl) >= 2 * count: break
    out = []
    for f, c in enumerate(faces): out.extend(repl.get(f, [c]))
    return MeshData.of(trimesh.Trimesh(np.asarray(vertices), np.asarray(out), process=False))

for path in (p1.KUNDEN / "broomholdervcd_d35mm.stl", p1.KUNDEN / "1x1-bin.stl", p1.KUNDEN / "Wedge-Lock (Base).stl", p1.REPO / "tests/data/meshes/post_with_fillet.stl"):
    name, mesh = p1.load(path)[0]
    forget_cache(); ref = detect(mesh)
    split = split_edges(mesh, max(3, mesh.triangle_count // 300), 11)
    assert split.is_watertight
    forget_cache(); got = detect(split)
    missing, extra = p1.compare(ref, got, mesh.bounds.diagonal)
    print(f"{name}: {mesh.triangle_count}->{split.triangle_count} Volumen {mesh.volume:.3f}->{split.volume:.3f}")
    print("   vorher", dict(Counter(f.kind for f in ref.values())), "nachher", dict(Counter(f.kind for f in got.values())))
    for f in missing: print("   fehlt:", p1.label(f))
    for f in extra: print("   neu:  ", p1.label(f))
print("---- Besenhalter: beanspruchte Fläche je Merkmal vor/nach der Teilung")
name, mesh = p1.load(p1.KUNDEN / "broomholdervcd_d35mm.stl")[0]
forget_cache(); ref = detect(mesh)
split = split_edges(mesh, max(3, mesh.triangle_count // 300), 11)
forget_cache(); got = detect(split)
def claimed_area(m, f): return float(np.asarray(m.raw.area_faces)[list(f.face_indices)].sum())
left = list(got.values())
for f in sorted(ref.values(), key=lambda v: v.kind):
    if f.kind == "curved_face": continue
    partner = next((g for g in left if p1.same(f, g, mesh.bounds.diagonal)), None)
    if partner is None: continue
    left.remove(partner)
    a, b = claimed_area(mesh, f), claimed_area(split, partner)
    if abs(a - b) > 1e-6 * max(a, 1):
        print(f"  {f.kind} {f.id}->{partner.id}: {a:.3f} -> {b:.3f} mm² ({len(f.face_indices)}->{len(partner.face_indices)} △)")
ca = sum(claimed_area(mesh, f) for f in ref.values() if f.kind=="curved_face")
cb = sum(claimed_area(split, f) for f in got.values() if f.kind=="curved_face")
print(f"  gerundete Seiten gesamt: {ca:.3f} -> {cb:.3f} mm²")
