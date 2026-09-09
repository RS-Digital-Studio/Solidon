"""Wie viele Dreiecke einer Vereinigung stammen unverändert aus ihren Quellen?"""

from __future__ import annotations

import numpy as np
import trimesh

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData


def schluessel(mesh) -> set[tuple]:
    """Jedes Dreieck als gerundetes Eckentripel, reihenfolgeunabhängig."""
    ecken = np.asarray(mesh.vertices, dtype=float)[np.asarray(mesh.faces, dtype=int)]
    gerundet = np.round(ecken, 6)
    return {tuple(sorted(map(tuple, dreieck))) for dreieck in gerundet}


def kasten(x: float, y: float, z: float, versatz=(0.0, 0.0, 0.0)) -> MeshData:
    roh = trimesh.creation.box(extents=(x, y, z))
    roh.apply_translation(versatz)
    return MeshData.of(roh)


def main() -> int:
    koerper = kasten(60.0, 40.0, 6.0)
    rippe = kasten(2.0, 30.0, 8.0, (0.0, 0.0, 4.0))

    vorher_koerper = schluessel(koerper.raw)
    vorher_rippe = schluessel(rippe.raw)
    ergebnis = boolean("union", [koerper, rippe])
    netz = ergebnis.mesh
    print(f"Stufe: {ergebnis.solver}")
    nachher = schluessel(netz.raw)

    aus_koerper = len(nachher & vorher_koerper)
    aus_rippe = len(nachher & vorher_rippe)
    neu = len(nachher) - aus_koerper - aus_rippe
    print(f"Körper vorher: {len(vorher_koerper):5d} Dreiecke")
    print(f"Rippe vorher:  {len(vorher_rippe):5d}")
    print(f"Ergebnis:      {len(nachher):5d}")
    print(f"  unverändert aus dem Körper: {aus_koerper}")
    print(f"  unverändert aus der Rippe:  {aus_rippe}")
    print(f"  neu vernetzt:               {neu}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
