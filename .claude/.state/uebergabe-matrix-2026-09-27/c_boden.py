"""Was druckt der G-Code im Inneren des C-Teils, Schicht für Schicht?

Aufruf: python c_boden.py <druckdatei.gcode> <bild.png>

Zeichnet die ersten Schichten im Ausschnitt des C-Teils (x 50…145, y 45…200)
und zählt je Schicht die Extrusionslänge nach Art (Orcas ``;TYPE:``).
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

GCODE = Path(sys.argv[1])
TARGET = Path(sys.argv[2])
BOX = (50.0, 145.0, 45.0, 200.0)
LAYERS = 6

layer = 0
kind = "?"
x = y = 0.0
e_mode_relative = True
segments: dict[int, list[tuple[str, float, float, float, float]]] = defaultdict(list)
move = re.compile(r"^G[01]\s")
with GCODE.open(encoding="utf-8", errors="replace") as handle:
    for line in handle:
        if line.startswith(";LAYER_CHANGE"):
            layer += 1
            if layer > LAYERS:
                break
            continue
        if line.startswith(";TYPE:"):
            kind = line[6:].strip()
            continue
        if line.startswith("M83"):
            e_mode_relative = True
        if line.startswith("M82"):
            e_mode_relative = False
        if not move.match(line) or layer == 0:
            continue
        words = dict((w[0], float(w[1:])) for w in line.split(";")[0].split()[1:] if w[0] in "XYE" and len(w) > 1)
        nx, ny = words.get("X", x), words.get("Y", y)
        if words.get("E", 0.0) > 0.0 and (nx != x or ny != y):
            segments[layer].append((kind, x, y, nx, ny))
        x, y = nx, ny

colours = {
    "Outer wall": "#1c7ed6",
    "Inner wall": "#4dabf7",
    "Bottom surface": "#2b8a3e",
    "Internal solid infill": "#51cf66",
    "Sparse infill": "#94d82d",
    "Top surface": "#f08c00",
    "Brim": "#862e9c",
    "Skirt": "#862e9c",
    "Overhang wall": "#e03131",
    "Bridge": "#e8590c",
}
fig, axes = plt.subplots(2, 3, figsize=(15, 11))
for index, ax in enumerate(axes.flat, start=1):
    totals: dict[str, float] = defaultdict(float)
    for kind, x0, y0, x1, y1 in segments.get(index, []):
        inside = BOX[0] <= (x0 + x1) / 2 <= BOX[1] and BOX[2] <= (y0 + y1) / 2 <= BOX[3]
        if not inside:
            continue
        ax.plot([x0, x1], [y0, y1], color=colours.get(kind, "#aaaaaa"), lw=0.5)
        totals[kind] += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    ax.set_xlim(BOX[0], BOX[1])
    ax.set_ylim(BOX[2], BOX[3])
    ax.set_aspect("equal")
    summary = ", ".join(f"{k} {v / 1000:.2f} m" for k, v in sorted(totals.items(), key=lambda kv: -kv[1]))
    ax.set_title(f"Schicht {index}\n{summary}", fontsize=8)
    print(f"Schicht {index}: {summary}")
plt.tight_layout()
plt.savefig(TARGET, dpi=70)
print(TARGET)
