"""Was passiert in Schicht 1 und 2 unten im C-Teil (Löcher 3 und 4, innerer Bogen)?

Aufruf: python c_ecke.py <druckdatei.gcode> <bild.png>

Zeichnet den Ausschnitt x 60…145, y 45…125 mit Druckbahnen nach Art und den
Leerfahrten (grau gestrichelt, mit Z-Hub rot), jeweils mit Tempo.
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
BOX = (60.0, 145.0, 45.0, 125.0)

layer = 0
kind = "?"
x = y = z = 0.0
feed = 0.0
prints: dict[int, list[tuple[str, float, float, float, float, float]]] = defaultdict(list)
travels: dict[int, list[tuple[float, float, float, float, bool]]] = defaultdict(list)
speeds: dict[int, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
move = re.compile(r"^G[01]\s")
with GCODE.open(encoding="utf-8", errors="replace") as handle:
    for line in handle:
        if line.startswith(";LAYER_CHANGE"):
            layer += 1
            if layer > 2:
                break
            continue
        if line.startswith(";TYPE:"):
            kind = line[6:].strip()
            continue
        if not move.match(line) or layer == 0:
            continue
        words = {w[0]: float(w[1:]) for w in line.split(";")[0].split()[1:] if w[0] in "XYZEF" and len(w) > 1}
        feed = words.get("F", feed)
        nx, ny, nz = words.get("X", x), words.get("Y", y), words.get("Z", z)
        inside = BOX[0] <= (x + nx) / 2 <= BOX[1] and BOX[2] <= (y + ny) / 2 <= BOX[3]
        if (nx, ny) != (x, y) and inside:
            if words.get("E", 0.0) > 0.0:
                prints[layer].append((kind, x, y, nx, ny, feed / 60.0))
                speeds[layer][kind].add(round(feed / 60.0))
            else:
                travels[layer].append((x, y, nx, ny, nz > z + 1e-6 or z > 0.0 and nz > 0.0 and False))
        x, y, z = nx, ny, nz

colours = {
    "Outer wall": "#1c7ed6",
    "Inner wall": "#4dabf7",
    "Bottom surface": "#2b8a3e",
    "Internal solid infill": "#51cf66",
    "Brim": "#862e9c",
    "Gap infill": "#f08c00",
}
fig, axes = plt.subplots(1, 2, figsize=(16, 8))
for index, ax in enumerate(axes, start=1):
    for kind, x0, y0, x1, y1, _speed in prints[index]:
        ax.plot([x0, x1], [y0, y1], color=colours.get(kind, "#aaaaaa"), lw=0.7)
    for x0, y0, x1, y1, _hop in travels[index]:
        ax.plot([x0, x1], [y0, y1], color="#868e96", lw=0.4, ls="--")
    ax.set_xlim(BOX[0], BOX[1])
    ax.set_ylim(BOX[2], BOX[3])
    ax.set_aspect("equal")
    text = "; ".join(f"{k} {sorted(v)} mm/s" for k, v in speeds[index].items())
    ax.set_title(f"Schicht {index}: Leerfahrten {len(travels[index])}\n{text}", fontsize=8)
    print(f"Schicht {index}: {text}; Leerfahrten im Ausschnitt: {len(travels[index])}")
plt.tight_layout()
plt.savefig(TARGET, dpi=80)
print(TARGET)
