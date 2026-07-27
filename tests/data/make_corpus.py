"""Builds the reference corpus (Bauplan §34).

Everything here is generated, never downloaded: the corpus is published with the
application, so it must be free of foreign licences. Run this script only when a
file has to change, and note the expected figures in ``README.md``.

    python tests/data/make_corpus.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).parent
MESHES = HERE / "meshes"


def write(mesh: trimesh.Trimesh, name: str) -> None:
    MESHES.mkdir(parents=True, exist_ok=True)
    path = MESHES / name
    path.write_bytes(trimesh.exchange.stl.export_stl(mesh))
    print(f"{name}: {len(mesh.faces)} triangles, extents {mesh.extents}")


def cube_clean() -> None:
    """The base case: watertight, 12 triangles, written in millimetres."""
    write(trimesh.creation.box(extents=(20.0, 20.0, 20.0)), "cube_clean.stl")


def bracket_inch() -> None:
    """A plate stored in inches — 4 x 2 x 0.25 in, so the unit is ambiguous."""
    write(trimesh.creation.box(extents=(4.0, 2.0, 0.25)), "bracket_inch.stl")


def plate_cm() -> None:
    """A plate stored in centimetres — 8 x 5 x 0.5 cm."""
    write(trimesh.creation.box(extents=(8.0, 5.0, 0.5)), "plate_cm.stl")


def degenerate() -> None:
    """A cube plus a zero-area triangle, a needle and a duplicate face."""
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    vertices = np.vstack(
        [
            box.vertices,
            [[30.0, 0.0, 0.0], [30.0, 0.0, 0.0], [30.0, 0.0, 0.0]],  # zero area
            [[40.0, 0.0, 0.0], [40.0 + 1e-9, 0.0, 0.0], [45.0, 0.0, 0.0]],  # needle
        ]
    )
    count = len(box.vertices)
    faces = np.vstack(
        [
            box.faces,
            [[count, count + 1, count + 2]],
            [[count + 3, count + 4, count + 5]],
            [box.faces[0]],  # duplicate
        ]
    )
    write(trimesh.Trimesh(vertices=vertices, faces=faces, process=False), "degenerate.stl")


def broken_open() -> None:
    """A cube missing three triangles — three open places for the repair chain."""
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    write(
        trimesh.Trimesh(vertices=box.vertices, faces=box.faces[:-3], process=False),
        "broken_open.stl",
    )


def two_components() -> None:
    """A cube with a tiny stray fragment next to it — reported, never deleted."""
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    fragment = trimesh.creation.box(extents=(0.2, 0.2, 0.2))
    fragment.apply_translation((40.0, 0.0, 0.0))
    write(trimesh.util.concatenate([box, fragment]), "two_components.stl")


if __name__ == "__main__":
    cube_clean()
    bracket_inch()
    plate_cm()
    degenerate()
    broken_open()
    two_components()
