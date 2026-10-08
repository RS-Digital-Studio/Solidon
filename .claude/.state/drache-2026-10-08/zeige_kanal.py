"""Schichtbild: Körper, Sperrbereich und Stützbahnen des G-Codes übereinander.

Aufruf: python zeige_kanal.py <körper.stl> <bereich.stl> <gcode> <z1,z2,…> <bild.png> [<halb>]

Grau der Körper, rot umrandet der Sperrbereich (alter Stand), blau die
Stützbahnen der Schicht. Die Lage auf dem Bett wie in ``gcode_im_kanal.py``:
Mitte der Modellbahnen gegen Mitte des Körpers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent

body = trimesh.load(sys.argv[1], process=False)
region = trimesh.load(sys.argv[2], process=False)
gcode = Path(sys.argv[3])
levels = [float(value) for value in sys.argv[4].split(",")]
out = Path(sys.argv[5])

exec(  # noqa: S102 — die eigene Lesefunktion der Nachbarsonde, nicht fremder Code
    (HERE / "gcode_im_kanal.py").read_text(encoding="utf-8").split("\n\n\nbody = ")[0],
    globals(),
)
support, model = read(gcode)  # noqa: F821
centre = (body.bounds[0][:2] + body.bounds[1][:2]) / 2.0
shift = (model.min(axis=0) + model.max(axis=0)) / 2.0 - centre
segments = np.asarray(support) if support else np.zeros((0, 5))

low = region.bounds[0][:2] - 15.0
high = region.bounds[1][:2] + 15.0
size = 420
scale = size / float(max(high - low))
tiles = []
for level in levels:
    image = Image.new("RGB", (size, size + 20), "white")
    draw = ImageDraw.Draw(image)
    draw.text((4, 2), f"z = {level:.1f} mm", fill="black")

    def point(x: float, y: float) -> tuple[float, float]:
        return ((x - low[0]) * scale, 20 + size - (y - low[1]) * scale)

    for mesh, colour, fill in ((body, "black", (190, 190, 190)), (region, "red", None)):
        section = mesh.section(plane_origin=(0, 0, level), plane_normal=(0, 0, 1))
        if section is None:
            continue
        for loop in section.discrete:
            draw.polygon(
                [point(x, y) for x, y, _z in loop], outline=colour, fill=fill if fill else None
            )
    pick = np.abs(segments[:, 4] - level) < 0.11 if len(segments) else np.zeros(0, bool)
    for x0, y0, x1, y1, _z in segments[pick]:
        draw.line(
            [point(x0 - shift[0], y0 - shift[1]), point(x1 - shift[0], y1 - shift[1])],
            fill=(30, 80, 220),
            width=2,
        )
    tiles.append(image)
sheet = Image.new("RGB", (size * len(tiles), size + 20), "white")
for index, tile in enumerate(tiles):
    sheet.paste(tile, (index * size, 0))
sheet.save(out)
print(out)
