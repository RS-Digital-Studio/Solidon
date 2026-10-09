"""Seitenansicht eines Netzes als Schattenriss (X–Z und Y–Z), mit Höhenmarken.

Aufruf: python seitenbild.py <netz.stl> <bild.png> [<z,…>]
"""

from __future__ import annotations

import sys

import numpy as np
import trimesh
from PIL import Image, ImageDraw

mesh = trimesh.load(sys.argv[1], force="mesh", process=False)
mesh.apply_translation((0.0, 0.0, -mesh.bounds[0][2]))
marks = [float(value) for value in sys.argv[3].split(",")] if len(sys.argv) > 3 else []
scale = 4.0
low, high = mesh.bounds
panels = []
for axis in (0, 1):
    width = int((high[axis] - low[axis]) * scale) + 20
    height = int(high[2] * scale) + 20
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    tri = mesh.triangles
    xs = (tri[:, :, axis] - low[axis]) * scale + 10
    zs = height - 10 - tri[:, :, 2] * scale
    for x, z in zip(xs, zs, strict=True):
        draw.polygon(list(zip(x.tolist(), z.tolist(), strict=True)), fill=90)
    for mark in marks:
        y = height - 10 - mark * scale
        draw.line([(0, y), (width, y)], fill=0)
        draw.text((2, y - 12), f"{mark:g}", fill=0)
    panels.append(image)
total = Image.new(
    "L", (sum(panel.width for panel in panels) + 10, max(p.height for p in panels)), 255
)
offset = 0
for panel in panels:
    total.paste(panel, (offset, 0))
    offset += panel.width + 10
total.save(sys.argv[2])
print(np.round(mesh.bounds, 1).tolist())
