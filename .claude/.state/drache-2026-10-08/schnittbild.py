"""Schichtumrisse des Drachen um eine Stelle, mit den Überhangstücken, als PNG.

Aufruf: python schnittbild.py <wurzel> <netz.stl> <x> <y> <halb> <z1,z2,...> <bild.png>

Grau das Material der Schicht, dunkle Linie die Schicht darunter; Überhang rot
(Kanal), orange (setzt auf dem Modell auf), blau (erreicht das Bett).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from shapely.geometry import Polygon as ShapelyPolygon  # noqa: E402
from shapely.geometry import box  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.export import writer  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.slice import analysis  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

path = Path(sys.argv[2])
if path.name.startswith("obj"):
    raw = trimesh.load(path, process=False)
else:
    from app.core.ingest.loader import read_local_payload, read_model

    raw = read_model(read_local_payload(path), path.suffix).raw
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
mesh = MeshData.of(raw)
cx, cy, half = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
heights = [float(z) for z in sys.argv[6].split(",")]
entry = SceneObject(id="obj_1", name="Drache", mesh=mesh)
profile = profiles.make_profile("centauri-carbon-2", "pla")
settings = print_settings.resolve(profile)
result = writer._body_analysis(entry, mesh, settings, profile, None, detail="full")
model = analysis.model_support(result)
layers = result.layers
SIZE = 420
scale = SIZE / (2 * half)
canvas = Image.new("RGB", (SIZE * len(heights), SIZE + 24), "white")
draw = ImageDraw.Draw(canvas)


WINDOW = box(cx - half, cy - half, cx + half, cy + half)


def parts(shape):
    clipped = shape.intersection(WINDOW)
    return [
        p
        for p in getattr(clipped, "geoms", [clipped])
        if p.geom_type == "Polygon" and not p.is_empty
    ]


def points(ring, offset: int) -> list[tuple[float, float]]:
    return [
        (offset + (x - cx + half) * scale, 24 + (cy + half - y) * scale) for x, y in ring.coords
    ]


for column, z in enumerate(heights):
    offset = column * SIZE
    index = min(range(len(layers)), key=lambda number: abs(layers[number].z - z))
    draw.text((offset + 6, 4), f"z = {layers[index].z:.1f} mm", fill="black")
    for contour in layers[index].contours:
        for shape in parts(ShapelyPolygon(contour.outline, contour.holes)):
            draw.polygon(points(shape.exterior, offset), fill=(190, 190, 190))
            for hole in shape.interiors:
                draw.polygon(points(hole, offset), fill="white")
    if index > 0:
        for contour in layers[index - 1].contours:
            for shape in parts(ShapelyPolygon(contour.outline)):
                draw.line(points(shape.exterior, offset), fill=(60, 60, 60), width=1)
    for number, piece in enumerate(layers[index].overhangs):
        pieces = parts(ShapelyPolygon(piece.outline))
        if (index, number) in model.channels:
            colour = (220, 0, 0)
        elif (index, number) in model.open_pieces:
            colour = (240, 150, 0)
        else:
            colour = (0, 90, 220)
        for shape in pieces:
            draw.polygon(points(shape.exterior, offset), fill=colour)
    draw.line([(offset, 0), (offset, SIZE + 24)], fill="black")
canvas.save(sys.argv[7])
