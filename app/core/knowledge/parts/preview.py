"""Preview images for the catalogue (Bauplan §24.3).

"A library one cannot see does not exist for the user." So the catalogue shows
pictures — and they are **rendered from the parts themselves**, not maintained
by hand. A hand-drawn preview is wrong the day a part changes, and nobody
notices until someone picks the wrong part.

Rendered here without a 3D context: the mesh is projected, the triangles are
sorted back to front and drawn as an SVG. That is enough for a thumbnail, it
works on a build server without a screen, and it costs no dependency (§36).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts.registry import PartSpec
from app.core.types import BaseParams

#: Edge length of a thumbnail in pixels.
SIZE = 160

#: Where the light comes from — over the left shoulder, as in every technical
#: drawing.
LIGHT = np.array([-0.4, -0.6, 0.7])

#: Base colour of a part, and of one that removes material rather than adding it.
SOLID_COLOUR = (0.72, 0.77, 0.82)
SUBTRACTIVE_COLOUR = (0.88, 0.66, 0.36)


@dataclass(frozen=True, slots=True)
class Preview:
    """One rendered thumbnail."""

    svg: str
    triangles: int

    def write(self, path: object) -> None:
        from pathlib import Path

        Path(str(path)).write_text(self.svg, encoding="utf-8")


def render(spec: PartSpec, params: BaseParams | None = None, size: int = SIZE) -> Preview:
    """A part as an SVG thumbnail, seen from the usual three-quarter angle."""
    mesh = as_mesh_data(spec.fn(params or spec.params()).mesh)
    colour = SUBTRACTIVE_COLOUR if spec.subtractive else SOLID_COLOUR
    return Preview(svg=_svg(mesh, size, colour), triangles=mesh.triangle_count)


def _camera() -> np.ndarray:
    """Isometric-ish: turned 35 degrees around Z, tilted 25 degrees down."""
    around = math.radians(-35.0)
    down = math.radians(25.0)
    turn = np.array(
        [
            [math.cos(around), -math.sin(around), 0.0],
            [math.sin(around), math.cos(around), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    tilt = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(down), -math.sin(down)],
            [0.0, math.sin(down), math.cos(down)],
        ]
    )
    return np.asarray(tilt @ turn, dtype=float)


def _svg(mesh: MeshData, size: int, colour: tuple[float, float, float]) -> str:
    body = mesh.raw
    if not len(body.faces):
        return _empty(size)

    matrix = _camera()
    points = np.asarray(body.vertices, dtype=float) @ matrix.T
    normals = np.asarray(body.face_normals, dtype=float) @ matrix.T

    flat = points[:, :2]
    low, high = flat.min(axis=0), flat.max(axis=0)
    span = float(max(high - low)) or 1.0
    scale = (size - 16) / span
    offset = (np.array([size, size]) - (high - low) * scale) / 2.0

    screen = (flat - low) * scale + offset
    screen[:, 1] = size - screen[:, 1]

    light = LIGHT / float(np.linalg.norm(LIGHT))
    depth = points[np.asarray(body.faces), 2].mean(axis=1)
    order = np.argsort(depth)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}">'
    ]
    for index in order:
        triangle = body.faces[index]
        shade = float(np.clip(normals[index] @ light, 0.0, 1.0)) * 0.55 + 0.45
        red, green, blue = (int(255 * value * shade) for value in colour)
        fill = f"#{red:02x}{green:02x}{blue:02x}"
        corners = " ".join(f"{screen[point][0]:.1f},{screen[point][1]:.1f}" for point in triangle)
        lines.append(f'<polygon points="{corners}" fill="{fill}" />')
    lines.append("</svg>")
    return "\n".join(lines)


def _empty(size: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}"></svg>'
    )
