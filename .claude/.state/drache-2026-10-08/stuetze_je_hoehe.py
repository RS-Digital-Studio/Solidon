"""Stützbahn je 10-mm-Band einer Druckdatei: Länge und Ausdehnung in X/Y.

Aufruf: python stuetze_je_hoehe.py <gcode> [<gcode> …]
"""

from __future__ import annotations

import math
import re
import sys
from collections import defaultdict

TYPE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
WORD = re.compile(r"([A-Z])(-?(?:\d+\.?\d*|\.\d+))")


def bands(path: str) -> dict[int, list[float]]:
    x = y = z = e = 0.0
    relative = False
    support = False
    found: dict[int, list[float]] = defaultdict(lambda: [0.0, 1e9, -1e9, 1e9, -1e9])
    with open(path, encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if line.startswith(";"):
                kind = TYPE.match(line)
                if kind:
                    support = "support" in kind.group(1).lower()
                continue
            code = line.split(";", 1)[0].strip().upper()
            if not code:
                continue
            command = code.split()[0]
            words = {key: float(value) for key, value in WORD.findall(code[len(command) :])}
            if command == "M83":
                relative = True
            elif command == "M82":
                relative = False
            elif command == "G92" and "E" in words:
                e = words["E"]
            elif command in ("G0", "G1", "G2", "G3"):
                nx, ny, nz = words.get("X", x), words.get("Y", y), words.get("Z", z)
                extrude = 0.0
                if "E" in words:
                    extrude = words["E"] if relative else words["E"] - e
                    if not relative:
                        e = words["E"]
                if support and extrude > 0.0:
                    entry = found[int(nz // 10) * 10]
                    entry[0] += math.dist((x, y), (nx, ny))
                    entry[1] = min(entry[1], nx)
                    entry[2] = max(entry[2], nx)
                    entry[3] = min(entry[3], ny)
                    entry[4] = max(entry[4], ny)
                x, y, z = nx, ny, nz
    return found


for path in sys.argv[1:]:
    found = bands(path)
    total = sum(entry[0] for entry in found.values()) / 1000.0
    print(f"== {path[-70:]}  Stütze {total:.1f} m")
    for band in sorted(found):
        length, x0, x1, y0, y1 = found[band]
        print(
            f"   z {band:3d}–{band + 10:3d}: {length / 1000.0:6.1f} m  "
            f"x {x0:6.1f}…{x1:6.1f}  y {y0:6.1f}…{y1:6.1f}"
        )
