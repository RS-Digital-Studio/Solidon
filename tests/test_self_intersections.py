"""Die Selbstdurchdringung wird je Paar als Feld gerechnet, nicht in einer Schleife.

Die Netzfehlerkarte (§18.4) fragt `repair.self_intersecting_faces`; bis zum
21.09.2026 lief jedes Dreieckspaar nach dem Sweep einzeln durch Python —
507 ms an der Lochplatte mit 796 Dreiecken, 5,3 s an ihrer zweifachen
Unterteilung. Die Antwort muss dieselbe bleiben: dieselben acht Dreiecke der
zwei durcheinanderlaufenden Quader, und an einem sauberen Netz keines.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from app.core.geom import repair
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise

MESHES = Path(__file__).parent / "data" / "meshes"


def _edges_pierce_reference(edges_of: np.ndarray, face: np.ndarray) -> bool:
    """Die skalare Fassung von Möller-Trumbore, wie sie bis zum 21.09.2026 stand."""
    from app.core.units import EPS_GEOM

    starts = edges_of
    directions = np.roll(edges_of, -1, axis=0) - edges_of
    first, second = face[1] - face[0], face[2] - face[0]
    normals = np.cross(directions, second)
    determinants = normals @ first
    parallel = np.abs(determinants) <= EPS_GEOM
    safe = np.where(parallel, 1.0, determinants)
    offsets = starts - face[0]
    u = np.einsum("ij,ij->i", offsets, normals) / safe
    crossed = np.cross(offsets, first)
    v = np.einsum("ij,ij->i", directions, crossed) / safe
    t = (crossed @ second) / safe
    inside = (
        ~parallel
        & (u > EPS_GEOM)
        & (v > EPS_GEOM)
        & (u + v < 1.0 - EPS_GEOM)
        & (t > EPS_GEOM)
        & (t < 1.0 - EPS_GEOM)
    )
    return bool(np.any(inside))


def test_the_two_blocks_still_report_their_eight_crossing_triangles() -> None:
    mesh = normalise(read_mesh((MESHES / "broken_selfint.stl").read_bytes(), ".stl"), "mm").mesh
    found = repair.self_intersecting_faces(mesh)
    assert len(found) == 8
    assert repair.self_intersecting_faces(MeshData.of(trimesh.creation.box())) == ()


def test_pairwise_piercing_matches_the_scalar_reference_on_random_pairs() -> None:
    """Tausend zufällige Dreieckspaare: das Feld sagt je Paar dasselbe wie die
    Schleife — und die Helfer nehmen ``(m, 3, 3)``, nicht ein Paar je Aufruf."""
    source = np.random.default_rng(21092026)
    ones = source.uniform(-1.0, 1.0, size=(1000, 3, 3))
    others = source.uniform(-1.0, 1.0, size=(1000, 3, 3))
    # Ein Teil der Paare teilt sich eine Ecke, ein Teil ist eine verschobene Kopie.
    others[:100, 0] = ones[:100, 1]
    others[100:200] = ones[100:200] + 0.01
    batched = repair._edges_pierce(ones, others)
    assert batched.shape == (1000,) and batched.dtype == bool
    expected = np.array([_edges_pierce_reference(a, b) for a, b in zip(ones, others, strict=True)])
    assert np.array_equal(batched, expected)
    assert batched.any() and not batched.all(), "beide Antworten kommen vor"
    shared = repair._share_a_corner(ones, others)
    assert shared.shape == (1000,)
    assert shared[:100].all() and not shared[200:].any()
