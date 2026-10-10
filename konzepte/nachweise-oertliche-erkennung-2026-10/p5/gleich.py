"""P5: Ist eine gebündelte Fassung Byte für Byte die alte? Alt gegen neu über viele Körper.

Aufruf: python gleich.py <baum> <kandidat> <liste.txt> [--max N]

Je Fall: Netz lesen, normalisieren, ``_one_body``; dann die alte Fassung (hier
nachgebaut, wie sie bis P5 im Baum stand) gegen die des Baums, Byte für Byte, samt
Zeit beider. Kandidaten: ``facet_middles``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, r"F:\sl-e\konzepte\nachweise-oertliche-erkennung-2026-10\messbank")
import _baum

TREE = _baum.setup(sys.argv[1])
CANDIDATE = sys.argv[2]
LIMIT = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10**9

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.perceive import features as F  # noqa: E402


def old_facet_middles(body):
    middles = np.asarray(body.triangles_center, dtype=float).copy()
    areas = np.asarray(body.area_faces, dtype=float)
    for facet in body.facets:
        members = np.asarray(facet)
        weight = areas[members].sum()
        if weight <= F.EPS_GEOM:
            continue
        middles[members] = (middles[members] * areas[members][:, None]).sum(axis=0) / weight
    return middles


CANDIDATES = {
    "facet_middles": (old_facet_middles, lambda body: F.facet_middles(body)),
}


def bodies(name: str):
    path = Path(name)
    mesh = normalise(read_mesh(path.read_bytes(), path.suffix), "mm").mesh
    raw = mesh.raw
    for piece in [raw] if len(raw.faces) else []:
        yield F._one_body(MeshData.of(piece)).raw


def main() -> int:
    old, new = CANDIDATES[CANDIDATE]
    names = [line.strip() for line in open(sys.argv[3], encoding="utf-8") if line.strip()]
    names = [name for name in names if not name.startswith("beispiel:")][:LIMIT]
    differing = 0
    checked = 0
    spent = [0.0, 0.0]
    for name in names:
        try:
            for body in bodies(name):
                fresh = trimesh.Trimesh(
                    np.array(body.vertices), np.array(body.faces), process=False
                )
                fresh.facets  # noqa: B018
                fresh.area_faces  # noqa: B018
                fresh.triangles_center  # noqa: B018
                started = time.process_time()
                left = old(fresh)
                spent[0] += time.process_time() - started
                twin = trimesh.Trimesh(np.array(body.vertices), np.array(body.faces), process=False)
                twin.facets  # noqa: B018 — dieselbe Vorarbeit wie oben, nicht in der Zeit
                twin.area_faces  # noqa: B018
                twin.triangles_center  # noqa: B018
                fresh_cost = time.process_time()
                right = new(twin)
                spent[1] += time.process_time() - fresh_cost
                checked += 1
                if (
                    left.dtype != right.dtype
                    or left.shape != right.shape
                    or (left.tobytes() != right.tobytes())
                ):
                    differing += 1
                    print("ANDERS", name, flush=True)
        except Exception as error:
            print("FEHLER", name, type(error).__name__, str(error)[:120], flush=True)
    print(
        f"{CANDIDATE}: {checked} Körper, {differing} anders, CPU alt {spent[0]:.2f} s, neu {spent[1]:.2f} s"
    )
    return 1 if differing else 0


if __name__ == "__main__":
    raise SystemExit(main())
