"""Sonde 3: Einzelfälle zu Normalen, Farben/Slots beim Füllen, Teilkörpern."""

from __future__ import annotations

import numpy as np
import trimesh

from common import MESHES, R, MeshData, codes, facts, head_repair, signed_volume_local, welded

from app.core.geom.mesh import face_components
from app.core.ingest.loader import normalise

H = head_repair()


def component_volumes(mesh: MeshData) -> list[float]:
    body = mesh.raw
    return [round(signed_volume_local(body.submesh([p], append=True, repair=False)), 3)
            for p in face_components(body)]


print("=== 3a generated_figure nach Reparatur: Teile")
fig = welded(MESHES / "generated_figure.stl")
res = R.repair(fig, self_intersections=True, inspect_intersections=True)
print(codes(res.findings), facts(res.mesh, intersections=True))
print("Teilvolumina:", component_volumes(res.mesh))
parts = face_components(res.mesh.raw)
for p in parts:
    sub = res.mesh.raw.submesh([p], append=True, repair=False)
    print("  Teil", len(p), "Dreiecke, Hülle", np.round(sub.bounds, 2).tolist())

print("\n=== 3b offener, ganz umgestülpter Würfel durch den Import")
cube = trimesh.creation.box(extents=(20, 20, 20))
cube.invert()
opened = trimesh.Trimesh(vertices=cube.vertices.copy(), faces=cube.faces[1:].copy(), process=False)
result = normalise(MeshData.of(opened), "mm")
print("Import:", codes(result.findings), facts(result.mesh))
rep = R.repair(MeshData.of(opened))
print("Reparieren:", codes(rep.findings), facts(rep.mesh))
# gleiches mit einem größeren Loch in einem unterteilten Würfel
sub = trimesh.creation.box(extents=(20, 20, 20)).subdivide().subdivide()
sub.invert()
top = np.flatnonzero(sub.face_normals[:, 2] < -0.5)[:6]  # (umgestülpt: Oberseite zeigt nach unten)
keep = np.ones(len(sub.faces), bool)
keep[top] = False
opened2 = trimesh.Trimesh(vertices=sub.vertices.copy(), faces=sub.faces[keep].copy(), process=False)
result2 = normalise(MeshData.of(opened2), "mm")
print("Import unterteilt:", codes(result2.findings), facts(result2.mesh))

print("\n=== 3c zweifarbiges Loch: welche Farbe/Slot bekommen die Füllflächen?")
body = trimesh.creation.box(extents=(20, 20, 20)).subdivide().subdivide().subdivide()
centres = body.triangles_center
# Loch oben: ein quadratischer Ausschnitt von 8x8 mm in der Mitte der Oberseite
hole = (centres[:, 2] > 9.99) & (np.abs(centres[:, 0]) < 4) & (np.abs(centres[:, 1]) < 4)
keep = ~hole
body = trimesh.Trimesh(vertices=body.vertices.copy(), faces=body.faces[keep].copy(), process=False)
centres = body.triangles_center
slots = np.where(centres[:, 0] < 0.0, 1, 2)  # linke Hälfte Slot 1, rechte Hälfte Slot 2
colours = np.where(slots[:, None] == 1, [255, 0, 0, 255], [0, 0, 255, 255]).astype(np.uint8)
body.visual.face_colors = colours
source = MeshData.of(body, slots=tuple(int(s) for s in slots))
for label, module in (("NEU", R), ("HEAD", H)):
    closed, changed = module.fill_holes(source)
    n = source.triangle_count
    new = np.asarray(closed.slots[n:]) if closed.slots else np.array([])
    new_centres = closed.raw.triangles_center[n:]
    left = new_centres[:, 0] < 0.0
    wrong_left = int(np.count_nonzero(new[left] != 1)) if len(new) else -1
    wrong_right = int(np.count_nonzero(new[~left] != 2)) if len(new) else -1
    fc = np.asarray(closed.raw.visual.face_colors)[n:]
    red = np.all(fc == [255, 0, 0, 255], axis=1)
    print(f"{label}: Füllflächen {len(new)}, links {int(left.sum())} davon falsch {wrong_left}, "
          f"rechts {int((~left).sum())} davon falsch {wrong_right}; "
          f"Farbe rot links {int(red[left].sum())}/{int(left.sum())}, rot rechts {int(red[~left].sum())}/{int((~left).sum())}; "
          f"dicht={closed.is_watertight}")

print("\n=== 3d zwei getrennte Würfel, einer umgestülpt (kein Überlapp)")
a = trimesh.creation.box(extents=(20, 20, 20))
b = a.copy()
b.apply_translation((40, 0, 0))
b.invert()
pair = MeshData.of(trimesh.util.concatenate([a, b]))
print("vorher:", facts(pair), component_volumes(pair))
rep = R.repair(pair, inspect_intersections=True)
print("Reparieren:", codes(rep.findings), facts(rep.mesh), component_volumes(rep.mesh))
imp = normalise(pair, "mm")
print("Import:", codes(imp.findings), facts(imp.mesh), component_volumes(imp.mesh))

print("\n=== 3e Hohlkörper mit richtig orientierter Innenschale (Soll: unverändert)")
inner = a.copy()
inner.apply_scale(0.5)
inner.invert()
hollow = MeshData.of(trimesh.util.concatenate([a, inner]))
rep = R.repair(hollow, inspect_intersections=True)
print("Reparieren:", codes(rep.findings), facts(rep.mesh), component_volumes(rep.mesh))

print("\n=== 3f Hohlkörper, Innenschale falsch herum (zeigt in den Hohlraum hinein = positiv)")
inner2 = a.copy()
inner2.apply_scale(0.5)
wrong = MeshData.of(trimesh.util.concatenate([a, inner2]))
print("vorher:", facts(wrong), component_volumes(wrong))
rep = R.repair(wrong, inspect_intersections=True)
print("Reparieren:", codes(rep.findings), facts(rep.mesh), component_volumes(rep.mesh))

print("\n=== 3g ganzer Körper umgestülpt und geschlossen")
inv = a.copy()
inv.invert()
rep = R.repair(MeshData.of(inv))
print("Reparieren:", codes(rep.findings), facts(rep.mesh))
imp = normalise(MeshData.of(inv), "mm")
print("Import:", codes(imp.findings), facts(imp.mesh))
