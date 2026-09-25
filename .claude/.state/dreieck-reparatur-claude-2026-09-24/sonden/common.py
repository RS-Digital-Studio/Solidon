"""Gemeinsame Helfer der Sonden: Laden, Kennzahlen, Zeitmessung (nur lesend)."""

from __future__ import annotations

import importlib.util
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(r"F:\3D Druck")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402

import app.core.bootstrap  # noqa: E402,F401
from app.core.geom import repair as R  # noqa: E402
from app.core.geom.mesh import MeshData, face_components  # noqa: E402

MESHES = ROOT / "tests" / "data" / "meshes"
KUNDE = Path(r"F:\3D Dateien")
HERE = Path(__file__).parent


def head_repair():
    """HEAD-Fassung von repair.py als eigenes Modul (Vergleichsweg)."""
    spec = importlib.util.spec_from_file_location("repair_head", HERE / "repair_head.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["repair_head"] = module
    spec.loader.exec_module(module)
    return module


def raw(path: Path | str) -> MeshData:
    """Datei roh laden (ohne Verarbeitung), wie der Test-Helfer."""
    body = trimesh.load(str(path), process=False, force="mesh")
    return MeshData.of(body)


def welded(path: Path | str) -> MeshData:
    mesh, _ = R.merge_vertices(raw(path))
    return mesh


def signed_volume_local(body: trimesh.Trimesh) -> float:
    tri = np.asarray(body.triangles, dtype=np.float64)
    if not len(tri):
        return 0.0
    local = tri - tri[0, 0]
    first, crossed = local[:, 0], np.cross(local[:, 1], local[:, 2])
    products = first[:, 0] * crossed[:, 0] + first[:, 1] * crossed[:, 1] + first[:, 2] * crossed[:, 2]
    return math.fsum(products.tolist()) / 6.0


def facts(mesh: MeshData, *, intersections: bool = False) -> dict:
    """Kennzahlen eines Netzes."""
    body = mesh.raw
    out = {
        "tri": len(body.faces),
        "open": R.open_edge_count(mesh),
        "branch": R.branching_edge_count(mesh),
        "tight": bool(body.is_watertight),
        "wound": bool(body.is_winding_consistent) if len(body.faces) else False,
        "vol": round(signed_volume_local(body), 3),
        "parts": len(face_components(body)),
    }
    if intersections:
        t0 = time.perf_counter()
        found, complete = R.self_intersection_check(mesh)
        out["x_faces"] = len(found)
        out["x_complete"] = complete
        out["x_s"] = round(time.perf_counter() - t0, 2)
    return out


def codes(findings) -> list[str]:
    return [f.code for f in findings]


class Timer:
    def __init__(self) -> None:
        self.start = time.perf_counter()

    def __call__(self) -> float:
        now = time.perf_counter()
        spent = now - self.start
        self.start = now
        return round(spent, 3)
