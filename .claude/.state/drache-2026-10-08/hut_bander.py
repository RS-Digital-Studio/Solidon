"""Stütze unter dem Pilzhut je Höhenband und Bahnart, aus dem G-Code.

Aufruf: python hut_bander.py <gcode> [<gcode> …]

Je Datei: Grundriss des Huts (Modellbahnen zwischen 12 und 14 mm, linke Gruppe),
dann je Band unter der Unterseite (0 bis 0,6 / 2 / 5 / 10 mm) der Anteil der
1-mm-Zellen des Huts (ohne Stiel) mit Stützbahn, getrennt nach Bahnart.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

TYPE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
WORD = re.compile(r"([XYZEF])(-?(?:\d+\.?\d*|\.\d+))")
SKIP = ("brim", "skirt", "prime", "wipe", "custom", "purge", "flush")
BANDS = ((0.0, 0.6), (0.6, 2.0), (2.0, 5.0), (5.0, 10.0))


def main() -> None:
    for name in sys.argv[1:]:
        support: dict[str, list[tuple[float, float, float, float, float]]] = defaultdict(list)
        model: list[tuple[float, float, float]] = []
        x = y = z = e_abs = 0.0
        relative = False
        kind = ""
        for line in Path(name).read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(";"):
                found = TYPE.match(line.strip())
                if found:
                    kind = found.group(1).lower()
                continue
            code = line.split(";", 1)[0].strip().upper()
            if code.startswith("M83"):
                relative = True
            elif code.startswith("M82"):
                relative = False
            elif code.startswith("G92"):
                for letter, value in WORD.findall(code):
                    if letter == "E":
                        e_abs = float(value)
            elif code.startswith(("G0", "G1")):
                values = dict(WORD.findall(code[2:]))
                nx, ny, nz = (float(values.get(k, v)) for k, v in (("X", x), ("Y", y), ("Z", z)))
                extruding = False
                if "E" in values:
                    e = float(values["E"])
                    extruding = (e if relative else e - e_abs) > 1e-5
                    if not relative:
                        e_abs = e
                if extruding and (nx != x or ny != y):
                    if "support" in kind or "tree" in kind:
                        support[kind].append((x, y, nx, ny, nz))
                    elif kind and not any(word in kind for word in SKIP):
                        model.append((nx, ny, nz))
                x, y, z = nx, ny, nz
        points = np.asarray(model)
        hat = points[(points[:, 2] > 12.05) & (points[:, 2] <= 14.05)]
        xs = np.sort(hat[:, 0])
        gaps = np.diff(xs)
        split = xs[int(np.argmax(gaps))] + gaps.max() / 2
        pilz = hat[hat[:, 0] < split]
        x0, y0, x1, y1 = pilz[:, 0].min(), pilz[:, 1].min(), pilz[:, 0].max(), pilz[:, 1].max()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cells = {
            (i, j)
            for i in range(int(np.floor(x0)), int(np.ceil(x1)))
            for j in range(int(np.floor(y0)), int(np.ceil(y1)))
            if not (abs(i + 0.5 - cx) < 5 and abs(j + 0.5 - cy) < 5)
        }
        print(Path(name).parent.name, "Hut", [round(float(v), 1) for v in (x0, y0, x1, y1)])
        for low, high in BANDS:
            row = []
            every: set[tuple[int, int]] = set()
            for kind, segments in sorted(support.items()):
                rows = np.asarray(segments)
                rows = rows[(rows[:, 4] < 12.0 - low + 1e-6) & (rows[:, 4] >= 12.0 - high + 1e-6)]
                hit = set()
                for sx, sy, ex, ey, _z in rows:
                    steps = max(1, int(np.hypot(ex - sx, ey - sy) / 0.25))
                    for t in np.linspace(0.0, 1.0, steps + 1):
                        hit.add(
                            (int(np.floor(sx + (ex - sx) * t)), int(np.floor(sy + (ey - sy) * t)))
                        )
                share = len(hit & cells) / len(cells)
                every |= hit
                if share:
                    row.append(f"{kind} {share:.0%}")
            total = len(every & cells) / len(cells)
            print(f"   {low:4.1f} bis {high:4.1f} mm: gesamt {total:.0%}  ({', '.join(row)})")


if __name__ == "__main__":
    main()
