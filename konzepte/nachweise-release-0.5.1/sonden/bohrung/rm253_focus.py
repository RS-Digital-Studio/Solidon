"""RM-253 gezielt: eine Bohrung des Laptop-Ständers kippen, versetzen, verdoppeln —
gemessen gegen den **vereinigten** Eingang (wie gedruckt), nicht gegen die
Summe der Schalen.

Vor den Mündungen: Volumen des Eingangs jenseits jeder alten Randebene minus
Volumen des Ergebnisses jenseits derselben Ebene, beide als geschlossene
Körper geschnitten. Dazu Windungszahl an der Bohrungsachse.

Aufruf: python rm253_focus.py hole_11 [winkel]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import AXES, as_mesh_data, codes, load, run  # noqa: E402

import manifold3d  # noqa: E402
import numpy as np  # noqa: E402

from app.core.deferred import trimesh  # noqa: E402
from app.core.geom import prepare_ops  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.geom.section import SectionPlane, cut  # noqa: E402
from app.core.perceive.relations import cavity_chain_at  # noqa: E402


def united(mesh: MeshData) -> MeshData:
    """Alle Schalen einzeln als Manifold, dann vereinigt — wie ein Slicer mit Vereinigung."""
    parts = []
    for piece in mesh.raw.split(only_watertight=False):
        solid = manifold3d.Manifold(
            manifold3d.Mesh(
                vert_properties=np.asarray(piece.vertices, dtype=np.float32),
                tri_verts=np.asarray(piece.faces, dtype=np.uint32),
            )
        )
        if solid.volume() < 0:
            continue
        parts.append(solid)
    whole = manifold3d.Manifold.batch_boolean(parts, manifold3d.OpType.Add)
    out = whole.to_mesh()
    return MeshData.of(
        trimesh.Trimesh(
            vertices=np.asarray(out.vert_properties[:, :3], dtype=float),
            faces=np.asarray(out.tri_verts, dtype=np.int64),
            process=False,
        )
    )


def beyond(mesh: MeshData, plane: SectionPlane) -> float:
    kept = cut(
        mesh, SectionPlane(normal=tuple(-v for v in plane.normal), position=-plane.position)
    ).mesh
    return abs(float(kept.volume)) if len(kept.raw.faces) else 0.0


def main() -> int:
    name = sys.argv[1]
    angle = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    path = Path(r"F:\3D Dateien\parametric-laptop-riser.stl")
    _project, profile, result, _seconds = load(path)
    entry = next(iter(result.scene.objects.values()))
    mesh = as_mesh_data(entry.mesh)
    whole = mesh
    print(f"Summe der Schalen {mesh.volume:.2f} (die Teile lassen sich nicht vereinigen)")
    bore = entry.features[name]
    chain = cavity_chain_at(bore, entry.features, mesh)
    print("Kette:", [f.id for f in chain] if chain else None)
    for member in chain or (bore,):
        print(
            f"  {member.id} {member.kind} Ø{member.params.get('diameter'):.3f} "
            f"Tiefe {member.params.get('depth')} Mitte {np.round(member.params['centre'], 3).tolist()} "
            f"durch={member.params.get('through')}"
        )
    axis = np.asarray(bore.params["axis"], dtype=float)
    turn = min(AXES, key=lambda key: abs(float(AXES[key] @ axis)))
    caps = prepare_ops._old_rim_caps(
        mesh, bore, entry.features, chain if chain and len(chain) > 1 else None
    )
    print("Kappen:", [(np.round(p.normal, 3).tolist(), round(p.position, 3)) for p in caps])
    started = time.perf_counter()
    done = run("rotate_feature", entry, profile, at_feature=bore.id, axis=turn, angle=angle)
    after = as_mesh_data(done.outputs[0].mesh)
    print(
        f"gekippt {angle:g}° um {turn} in {time.perf_counter() - started:.1f} s: "
        f"V {after.volume:.2f} (vereinigt vorher {whole.volume:.2f}, Δ {after.volume - whole.volume:+.2f}) "
        f"dicht={after.is_watertight} Teile {after.component_count} {codes(done)} solver={done.solver}"
    )
    for plane in caps:
        print(
            f"  jenseits {np.round(plane.normal, 3).tolist()}@{plane.position:.3f}: "
            f"vorher {beyond(whole, plane):.3f}, nachher {beyond(after, plane):.3f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
