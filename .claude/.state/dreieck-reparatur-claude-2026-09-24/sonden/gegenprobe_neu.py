"""Gegenprobe: die neuen Regressionsfälle gegen gesicherte Altstände von repair.py."""

from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path.cwd()))
from app.core.geom.mesh import MeshData  # noqa: E402

warnings.simplefilter("ignore")
HERE = Path(__file__).resolve().parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"alt_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def box(size=20.0, at=(0.0, 0.0, 0.0)):
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(at)
    return body


def cases():
    body = box()
    edge = body.edges_unique[0]
    tip = (body.vertices[edge[0]] + body.vertices[edge[1]]) / 2.0 + np.array([15.0, 15.0, 0.0])
    yield "flosse", MeshData.of(trimesh.Trimesh(np.vstack([body.vertices, tip]),
        np.vstack([body.faces, [edge[0], edge[1], len(body.vertices)]]), process=False))
    yield "blatt", MeshData.of(trimesh.Trimesh([[0, 0, 0], [30, 0, 0], [30, 30, 0], [0, 30, 0]],
        [[0, 1, 2], [0, 2, 3]], process=False))
    yield "dreieck", MeshData.of(trimesh.Trimesh([[0, 0, 0], [10, 0, 0], [0, 10, 0]], [[0, 1, 2]], process=False))
    wrong = box(at=(40.0, 0.0, 0.0))
    wrong.invert()
    yield "umgestuelpt", MeshData.of(trimesh.util.concatenate([box(), wrong]))


for stand in sys.argv[1:]:
    module = load(stand)
    print(f"== {stand}")
    for name, mesh in cases():
        try:
            result = module.repair(mesh)
            m = result.mesh
            codes = sorted({f.code for f in result.findings})
            vol = float(np.sum(np.einsum("ij,ij->i", m.raw.triangles[:, 0], np.cross(m.raw.triangles[:, 1], m.raw.triangles[:, 2])))) / 6.0
            print(f"  {name}: Dreiecke={m.triangle_count} dicht={m.is_watertight} Vol={vol:.1f} {codes}")
        except Exception as error:  # noqa: BLE001
            print(f"  {name}: {type(error).__name__}: {error}")
