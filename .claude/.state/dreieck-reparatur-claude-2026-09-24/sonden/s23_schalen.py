"""Sonde 23: turn_shells_outward — Laufzeit mit vielen Hohlräumen in großem Körper, Grenzfälle."""
import hashlib, time
from pathlib import Path
import numpy as np
import trimesh
from common import R, MeshData, facts, signed_volume_local
from app.core.geom.mesh import face_components

print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8])

def cavities(count, outer_subdiv=6, inside=True, radius=40.0):
    outer = trimesh.creation.icosphere(subdivisions=outer_subdiv, radius=radius)
    rng = np.random.default_rng(7)
    shells = [outer]
    for _ in range(count):
        c = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        if inside:
            d = rng.random(3) * 2 - 1; d *= (radius * 0.6) * rng.random() / max(np.linalg.norm(d), 1e-9)
            c.apply_translation(d)
        else:
            d = rng.random(3) * 2 - 1; d /= np.linalg.norm(d); c.apply_translation(d * (radius + 5 + 10 * rng.random()))
        c.invert()
        shells.append(c)
    return MeshData.of(trimesh.util.concatenate(shells))

for count, subdiv, inside in ((50, 6, True), (300, 6, True), (300, 7, True), (300, 6, False)):
    mesh = cavities(count, subdiv, inside)
    t0 = time.perf_counter(); fixed, flipped = R.unify_normals(mesh); spent = time.perf_counter() - t0
    vols = [signed_volume_local(fixed.raw.submesh([p], append=True, repair=False)) for p in face_components(fixed.raw)]
    neg = sum(1 for v in vols if v < 0)
    print(f"{count} Würfel {'innen' if inside else 'außen'}, Kugel Unterteilung {subdiv} ({mesh.triangle_count} Dreiecke): "
          f"unify_normals {spent:.2f}s umgedreht={flipped} negative Schalen danach={neg}", flush=True)

# Grenzfall: umgestülpter Würfel, der die Außenhaut berührt (teilt Fläche nicht, liegt aber auf ihr)
outer = trimesh.creation.box(extents=(20, 20, 20))
touch = trimesh.creation.box(extents=(4, 4, 4)); touch.apply_translation((8, 0, 0)); touch.invert()   # innen, berührt die Wand x=10
mesh = MeshData.of(trimesh.util.concatenate([outer, touch]))
fixed, flipped = R.unify_normals(mesh)
print("Hohlraum an der Wand:", flipped, [round(signed_volume_local(fixed.raw.submesh([p], append=True, repair=False)), 1) for p in face_components(fixed.raw)])
# Grenzfall: umgestülptes Teil in der Hüllbox eines U, aber außerhalb des Materials
u = trimesh.util.concatenate([trimesh.creation.box(extents=(30, 5, 10)).apply_translation((0, -12.5, 0)),
                              trimesh.creation.box(extents=(30, 5, 10)).apply_translation((0, 12.5, 0)),
                              trimesh.creation.box(extents=(5, 30, 10)).apply_translation((-12.5, 0, 0))])
free = trimesh.creation.box(extents=(4, 4, 4)); free.apply_translation((5, 0, 0)); free.invert()
mesh = MeshData.of(trimesh.util.concatenate([u, free]))
fixed, flipped = R.unify_normals(mesh)
print("umgestülptes Teil im Maul eines U (drei Quader):", flipped, [round(signed_volume_local(fixed.raw.submesh([p], append=True, repair=False)), 1) for p in face_components(fixed.raw)])
