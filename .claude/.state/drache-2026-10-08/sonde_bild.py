"""Schichtbild mit Kanalfrage bei gegebenem Winkel: Material, Stücke, Sperrraum.

Aufruf: python sonde_bild.py <wurzel> <netz.stl> <winkel> <x> <y> <halb> <z1,z2,…> <bild.png>

Grau das Material, dunkle Linie die Schicht darunter; Stücke rot (Kanal mit
Sperre), rosa (Kanal ohne Sperre), orange (auf dem Modell), blau (zum Bett);
violett umrandet der Sperrraum der Scheibe.
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

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice.analysis import channel_space, model_support, slice_body  # noqa: E402

raw = trimesh.load(sys.argv[2], process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
result = slice_body(
    MeshData.of(raw),
    0.2,
    first_layer_height=0.2,
    overhang_angle=float(sys.argv[3]),
    bridge_from=0.84,
    detail="support",
    support_volume=False,
)
model = model_support(result)
slabs = channel_space(result, model, 0.42)
gated = {
    (round(high, 2), round(ShapelyPolygon(outline.outline).centroid.x, 2))
    for outline, _low, high in model.channel_columns
}
cx, cy, half = float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6])
heights = [float(z) for z in sys.argv[7].split(",")]
layers = result.layers
SIZE = 420
scale = SIZE / (2 * half)
window = box(cx - half, cy - half, cx + half, cy + half)
sheet = Image.new("RGB", (SIZE * len(heights), SIZE + 24), "white")
draw = ImageDraw.Draw(sheet)


def parts(shape):
    clipped = shape.intersection(window)
    return [
        p
        for p in getattr(clipped, "geoms", [clipped])
        if p.geom_type == "Polygon" and not p.is_empty
    ]


def points(ring, offset):
    return [
        (offset + (x - cx + half) * scale, 24 + (cy + half - y) * scale) for x, y in ring.coords
    ]


for column, z in enumerate(heights):
    offset = column * SIZE
    index = min(range(len(layers)), key=lambda number: abs(layers[number].z - z))
    layer = layers[index]
    draw.text((offset + 6, 4), f"z = {layer.z:.1f} mm", fill="black")
    for contour in layer.contours:
        for shape in parts(ShapelyPolygon(contour.outline, contour.holes)):
            draw.polygon(points(shape.exterior, offset), fill=(195, 195, 195))
            for hole in shape.interiors:
                draw.polygon(points(hole, offset), fill="white")
    if index > 0:
        for contour in layers[index - 1].contours:
            for shape in parts(ShapelyPolygon(contour.outline)):
                draw.line(points(shape.exterior, offset), fill=(60, 60, 60), width=1)
    for number, piece in enumerate(layer.overhangs):
        name = (index, number)
        shape = ShapelyPolygon(piece.outline, piece.holes)
        if name in model.channels:
            key = (round(layer.z, 2), round(shape.centroid.x, 2))
            colour = (200, 0, 0) if key in gated else (240, 150, 170)
        elif name in model.open_pieces:
            colour = (240, 140, 0)
        else:
            colour = (40, 90, 220)
        for part in parts(shape):
            draw.polygon(points(part.exterior, offset), fill=colour)
    for bottom, top, region in slabs:
        if bottom <= layer.z <= top:
            for part in parts(region):
                draw.line(points(part.exterior, offset), fill=(130, 0, 160), width=2)
sheet.save(sys.argv[8])
print(sys.argv[8])
