"""Sonde 6: Scheinmerkmale aus Lochfüllungen auf gekrümmten Flächen.

Entfernt um eine Ecke herum 1, 2 oder 3 Ringe von Dreiecken auf Kugel,
Torus, Zapfenmantel und Verrundung und fragt nach der Reparatur, ob die
Füllung als eigenes Merkmal (Fläche, Kegel, Kugel …) erscheint oder ein
echtes Merkmal verliert.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.geom.repair import open_edge_count, repair, self_intersection_check  # noqa: E402
from app.core.ingest.loader import normalise, read_model  # noqa: E402
from app.core.perceive.features import detect, forget_cache  # noqa: E402

REPO = Path(r"F:\3D Druck")
OUT = Path(__file__).with_suffix(".txt")


def load(name: str) -> MeshData:
    path = REPO / "tests/data/meshes" / name
    return normalise(read_model(path.read_bytes(), path.suffix), "mm").mesh


def rings(mesh: MeshData, vertex: int, depth: int) -> list[int]:
    faces = np.asarray(mesh.raw.faces)
    chosen: set[int] = set()
    corners = {vertex}
    for _level in range(depth):
        touching = set(np.flatnonzero(np.isin(faces, list(corners)).any(axis=1)).tolist())
        chosen |= touching
        corners = set(faces[list(chosen)].ravel().tolist())
    return sorted(chosen)


def without(mesh: MeshData, gone) -> MeshData:
    keep = np.ones(mesh.triangle_count, dtype=bool)
    keep[list(gone)] = False
    return MeshData.of(trimesh.Trimesh(np.asarray(mesh.raw.vertices),
                                       np.asarray(mesh.raw.faces)[keep], process=False))


def label(feature) -> str:
    params = feature.params
    dims = ",".join(f"{k}={float(params[k]):.3f}" for k in ("diameter", "area", "angle", "radius")
                    if isinstance(params.get(k), int | float) and not isinstance(params.get(k), bool))
    return f"{feature.kind}[{dims}] n={len(feature.face_indices)}"


def main() -> None:
    with OUT.open("w", encoding="utf-8") as out:
        for name in ("torus_ring.stl", "sphere_socket.stl", "post_with_fillet.stl",
                     "block_with_rounded_edge.stl", "near_sphere_ellipsoid.stl"):
            mesh = load(name)
            forget_cache()
            reference = detect(mesh)
            out.write(f"\n# {name}: {mesh.triangle_count} △ {dict(Counter(f.kind for f in reference.values()))}\n")
            owned = {}
            for feature in reference.values():
                for face in feature.face_indices:
                    owned[face] = feature
            targets = {}
            for feature in reference.values():
                if feature.kind in {"sphere", "torus", "pin", "fillet", "hole", "cone"} and feature.kind not in targets:
                    targets[feature.kind] = feature
            for kind, feature in targets.items():
                faces = np.asarray(mesh.raw.faces)[list(feature.face_indices)]
                counts = Counter(faces.ravel().tolist())
                inner = [v for v, c in counts.items() if c >= 5]
                if not inner:
                    continue
                vertex = inner[len(inner) // 2]
                for depth in (1, 2, 3):
                    gone = rings(mesh, vertex, depth)
                    if not set(gone) <= set(feature.face_indices):
                        out.write(f"  {kind} Tiefe {depth}: Bereich verlässt das Merkmal, übersprungen\n")
                        break
                    damaged = without(mesh, gone)
                    fixed = repair(damaged)
                    forget_cache()
                    healed = detect(fixed.mesh)
                    crossings, _complete = self_intersection_check(fixed.mesh)
                    before = Counter(f.kind for f in reference.values())
                    after = Counter(f.kind for f in healed.values())
                    new = fixed.mesh.triangle_count - damaged.triangle_count
                    first_new = damaged.triangle_count
                    claim = Counter()
                    for other in healed.values():
                        mine = [i for i in other.face_indices if i >= first_new]
                        if mine:
                            claim[label(other)] += len(mine)
                    same_kind = [f for f in healed.values() if f.kind == kind]
                    out.write(
                        f"  {kind} Tiefe {depth}: {len(gone)} △ entfernt, {new} gefüllt, "
                        f"open={open_edge_count(fixed.mesh)} Durchdringungen={len(crossings)} "
                        f"Befunde={[f.code for f in fixed.findings]}\n"
                        f"      Arten {dict(before)} -> {dict(after)}\n"
                        f"      {kind} vorher {label(feature)}; nachher {[label(f) for f in same_kind]}\n"
                        f"      Fülldreiecke bei: {dict(claim)}\n"
                    )
                    out.flush()


if __name__ == "__main__":
    main()
