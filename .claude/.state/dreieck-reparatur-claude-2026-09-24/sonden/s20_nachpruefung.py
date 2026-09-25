"""Sonde 20: Alle Befunde am aktuellen Stand in einem Lauf nachmessen (Statuszeilen je Befund)."""

from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path

import numpy as np
import trimesh

from common import KUNDE, MESHES, R, MeshData, codes, facts, signed_volume_local, welded

from app.core.geom.mesh import face_components, read_mesh
from app.core.ingest import threemf
from app.core.ingest.loader import normalise



def tube_along(points, radius=1.5, sides=12):
    n = len(points); rings = []
    for i in range(n):
        tangent = points[(i + 1) % n] - points[i - 1]; tangent /= np.linalg.norm(tangent)
        side = np.cross(tangent, [0.0, 0.0, 1.0]); side /= np.linalg.norm(side)
        up2 = np.cross(side, tangent)
        rings.append([points[i] + radius * (math.cos(t) * up2 + math.sin(t) * side) for t in np.linspace(0, 2 * math.pi, sides, endpoint=False)])
    vertices = np.asarray(rings).reshape(-1, 3); faces = []
    for i in range(n):
        j = (i + 1) % n
        for k in range(sides):
            l = (k + 1) % sides
            a_, b_, c_, d_ = i * sides + k, i * sides + l, j * sides + l, j * sides + k
            faces += [[a_, b_, c_], [a_, c_, d_]]
    body = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
    if body.volume < 0:
        body.invert()
    return body


def figure_eight(samples=96, size=20.0):
    t = np.linspace(0, 2 * math.pi, samples, endpoint=False)
    return np.column_stack([size * np.sin(t), size * np.sin(t) * np.cos(t), np.zeros_like(t)])


def two_colour_hole(subdivisions=3, half=4.0):
    body = trimesh.creation.box(extents=(20, 20, 20))
    for _ in range(subdivisions):
        body = body.subdivide()
    centres = body.triangles_center
    hole = (centres[:, 2] > 9.99) & (np.abs(centres[:, 0]) < half) & (np.abs(centres[:, 1]) < half)
    body = trimesh.Trimesh(vertices=body.vertices.copy(), faces=body.faces[~hole].copy(), process=False)
    slots = np.where(body.triangles_center[:, 0] < 0.0, 1, 2)
    return MeshData.of(body, slots=tuple(int(s) for s in slots))


print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8], time.strftime("%H:%M:%S"))


def parts_volumes(mesh: MeshData) -> list[float]:
    return [round(signed_volume_local(mesh.raw.submesh([p], append=True, repair=False)), 3)
            for p in face_components(mesh.raw)]


def line(tag: str, text: str) -> None:
    print(f"[{tag}] {text}", flush=True)


# B1
a = welded(MESHES / "broken_selfint.stl")
got, changed = R.resolve_self_intersections(a)
line("B1", f"zwei Würfel: changed={changed} vol={signed_volume_local(got.raw):.1f} (Soll 14272)")

# B2 STL-Suppe, Dreieck 0 falsch + Loch
body = trimesh.creation.box(extents=(20, 20, 20)).subdivide().subdivide()
faces = body.faces.copy(); faces[0] = faces[0, ::-1]
keep = np.ones(len(faces), bool); keep[50] = False
soup = trimesh.Trimesh(vertices=body.vertices[faces[keep]].reshape(-1, 3), faces=np.arange(3 * int(keep.sum())).reshape(-1, 3), process=False)
imp = normalise(MeshData.of(soup), "mm", weld_is_reading=True)
line("B2", f"STL-Suppe: {codes(imp.findings)} vol={facts(imp.mesh)['vol']} (Soll +8000)")
cube = trimesh.creation.box(extents=(20, 20, 20)); cube.invert()
opened = trimesh.Trimesh(vertices=cube.vertices.copy(), faces=cube.faces[1:].copy(), process=False)
imp = normalise(MeshData.of(opened), "mm")
line("B2", f"offener umgestülpter Würfel: {codes(imp.findings)} vol={facts(imp.mesh)['vol']}")

# B3 Budget
path = KUNDE / "3D Drucker/13_Besteckkorb_Abtropfkorb/Modular/Besteckkorb_Modular.3mf"
mesh = next(o.mesh for o in threemf.read_objects(path.read_bytes()) if str(o.name) == "Modul B · Mitte links")
mesh = normalise(mesh, "mm").mesh
t0 = time.perf_counter(); rep = R.repair(mesh, inspect_intersections=True)
line("B3", f"Besteckkorb 8672: {codes(rep.findings)} {time.perf_counter()-t0:.2f}s")
payload = (KUNDE / "drill-holder.3mf").read_bytes()
dh = normalise(next(o.mesh for o in threemf.read_objects(payload) if str(o.name) == "Körper 1"), "mm").mesh
t0 = time.perf_counter(); rep = R.repair(dh, self_intersections=True, inspect_intersections=True)
line("B3", f"drill-holder SI an: {codes(rep.findings)} parts={facts(rep.mesh)['parts']} {time.perf_counter()-t0:.2f}s")

# B4 Achterröhre
tube = MeshData.of(tube_along(figure_eight()))
rep = R.repair(tube, inspect_intersections=True)
line("B4", f"Achterröhre Vorgabe: {[(f.code, [a.id for a in f.suggestions]) for f in rep.findings]}")
rep = R.repair(tube, self_intersections=True, inspect_intersections=True)
line("B4", f"Achterröhre SI an: {codes(rep.findings)}")

# B5 Naht, Klein-Röhre
naht = read_mesh((KUNDE / "3D Drucker/16_CC2-Auffangrinne/Naht-zusammengesetzt.stl").read_bytes(), ".stl")
imp = normalise(naht, "mm", weld_is_reading=True)
line("B5", f"Naht Import: {codes(imp.findings)} {facts(imp.mesh)}")
rep = R.repair(imp.mesh, inspect_intersections=True)
line("B5", f"Naht Reparieren: {codes(rep.findings)} {facts(rep.mesh)}")
import s10_klein  # noqa: E402,F401  (druckt selbst)

# B7 generated_figure
fig = welded(MESHES / "generated_figure.stl")
rep = R.repair(fig)
line("B7", f"generated_figure repair: {codes(rep.findings)} Teilvolumina={parts_volumes(rep.mesh)[:4]} {facts(rep.mesh)}")
imp = normalise(read_mesh((MESHES / "generated_figure.stl").read_bytes(), ".stl"), "mm", weld_is_reading=True)
line("B7", f"generated_figure Import: {codes(imp.findings)} {facts(imp.mesh)}")

# B8 broken_open
rep = R.repair(welded(MESHES / "broken_open.stl"))
wide = next((f for f in rep.findings if f.code == "repair.wide_hole_filled"), None)
line("B8", f"broken_open: location={None if wide is None else wide.location} suggestions={None if wide is None else [a.id for a in wide.suggestions]}")

# B9 Teilschalen
a = trimesh.creation.box(extents=(20, 20, 20))
b = a.copy(); b.apply_translation((40, 0, 0)); b.invert()
pair = MeshData.of(trimesh.util.concatenate([a, b]))
rep = R.repair(pair, inspect_intersections=True)
line("B9", f"freistehend umgestülpt: {codes(rep.findings)} Teile={parts_volumes(rep.mesh)}")
inner = a.copy(); inner.apply_scale(0.5); inner.invert()
rep = R.repair(MeshData.of(trimesh.util.concatenate([a, inner])), inspect_intersections=True)
line("B9", f"Hohlkörper richtig: {codes(rep.findings)} Teile={parts_volumes(rep.mesh)}")
inner2 = a.copy(); inner2.apply_scale(0.5)
rep = R.repair(MeshData.of(trimesh.util.concatenate([a, inner2])), inspect_intersections=True)
line("B9", f"Innenschale positiv (mehrdeutig): {codes(rep.findings)} Teile={parts_volumes(rep.mesh)}")
imp = normalise(pair, "mm")
line("B9", f"Import freistehend umgestülpt: {codes(imp.findings)} Teile={parts_volumes(imp.mesh)}")

# B10 Slots am zweifarbigen Loch
src = two_colour_hole()
closed, _f, _w = R.fill_boundary_loops(src)
n = src.triangle_count
edges = {}
for index, face in enumerate(np.asarray(src.raw.faces)):
    for x, y in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
        edges.setdefault((min(x, y), max(x, y)), []).append(index)
pts = np.asarray(src.raw.vertices)
by_place = {tuple(sorted((tuple(np.round(pts[x], 6)), tuple(np.round(pts[y], 6))))): src.slots[o[0]]
            for (x, y), o in edges.items() if len(o) == 1}
cp = np.asarray(closed.raw.vertices)
wrong = 0
for index in range(n, closed.triangle_count):
    f = closed.raw.faces[index]
    rim = [by_place[k] for k in (tuple(sorted((tuple(np.round(cp[u], 6)), tuple(np.round(cp[v], 6))))) for u, v in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0]))) if k in by_place]
    wrong += bool(rim) and closed.slots[index] not in rim
line("B10", f"zweifarbiges Loch: {wrong} von {closed.triangle_count - n} Fülldreiecken mit fremdem Slot")


# B14 Schale mit gezacktem Rand, Zylinderfenster
sphere = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
cs = sphere.triangles_center
bowl = MeshData.of(trimesh.Trimesh(vertices=sphere.vertices.copy(), faces=sphere.faces[~(cs[:, 2] > -2.0)].copy(), process=False))
rep = R.repair(bowl)
line("B14", f"Schale z<-2: {codes(rep.findings)} tight={rep.mesh.is_watertight}")

# B16 fern
box = trimesh.creation.box(extents=(1, 1, 1)).subdivide().subdivide(); box.apply_translation((1e8, 7e7, 3e7))
fixed, flipped = R.unify_normals(MeshData.of(box))
line("B16", f"Würfel 1 mm bei 1e8: umgestülpt={flipped} danach Volumen lokal={signed_volume_local(fixed.raw):+.3f}")
