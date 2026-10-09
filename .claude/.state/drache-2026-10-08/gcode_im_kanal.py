"""Wie viel Stützbahn liegt im Kanal?

Aufruf: python gcode_im_kanal.py <körper.stl> <bereich.stl> <gcode> [<gcode> …]

``körper.stl`` und ``bereich.stl`` stammen aus derselben Übergabe-3MF
(``extract.py``), liegen also im selben Rahmen; der Bereich ist der Sperrkörper
des neuen Stands, also der freie Raum unter den Kanaldecken. Die Lage auf dem
Bett kommt aus dem G-Code (Mitte der Modellbahnen gegen Mitte des Körpers).
Gezählt wird Stützbahn, deren Mitte im Bereich liegt, in Metern.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import shapely
import trimesh

TYPE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
WORD = re.compile(r"([XYZEF])(-?(?:\d+\.?\d*|\.\d+))")
SKIP = ("brim", "skirt", "prime", "wipe", "custom", "purge", "flush")


def read(path: Path) -> tuple[list[tuple[float, float, float, float, float]], np.ndarray]:
    """Stützsegmente (x0, y0, x1, y1, z) und Punkte der Modellbahnen."""
    support: list[tuple[float, float, float, float, float]] = []
    model: list[tuple[float, float]] = []
    x = y = z = 0.0
    e_abs = 0.0
    relative_e = False
    kind = ""
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(";"):
                found = TYPE.match(line.strip())
                if found:
                    kind = found.group(1).lower()
                continue
            code = line.split(";", 1)[0].strip().upper()
            if not code:
                continue
            if code.startswith("M83"):
                relative_e = True
                continue
            if code.startswith("M82"):
                relative_e = False
                continue
            if code.startswith("G92"):
                for letter, value in WORD.findall(code):
                    if letter == "E":
                        e_abs = float(value)
                continue
            if not (code.startswith("G1") or code.startswith("G0")):
                if code.startswith(("G2", "G3")):
                    pass
                else:
                    continue
            values = dict(WORD.findall(code[2:]))
            nx = float(values["X"]) if "X" in values else x
            ny = float(values["Y"]) if "Y" in values else y
            nz = float(values["Z"]) if "Z" in values else z
            extruding = False
            if "E" in values:
                e = float(values["E"])
                delta = e if relative_e else e - e_abs
                if not relative_e:
                    e_abs = e
                extruding = delta > 1e-5
            if extruding and (nx != x or ny != y):
                if "support" in kind or "tree" in kind:
                    support.append((x, y, nx, ny, nz))
                elif kind and not any(word in kind for word in SKIP):
                    model.append((nx, ny))
            x, y, z = nx, ny, nz
    return support, np.asarray(model)


body = trimesh.load(sys.argv[1], process=False)
region = trimesh.load(sys.argv[2], process=False)
centre = (body.bounds[0][:2] + body.bounds[1][:2]) / 2.0
report = {}
for name in sys.argv[3:]:
    support, model = read(Path(name))
    shift = (model.min(axis=0) + model.max(axis=0)) / 2.0 - centre
    segments = np.asarray(support) if support else np.zeros((0, 5))
    mids = np.column_stack(
        (
            (segments[:, 0] + segments[:, 2]) / 2.0 - shift[0],
            (segments[:, 1] + segments[:, 3]) / 2.0 - shift[1],
            segments[:, 4],
        )
    )
    lengths = np.hypot(segments[:, 2] - segments[:, 0], segments[:, 3] - segments[:, 1])
    inside = np.zeros(len(mids), dtype=bool)
    levels = np.round(mids[:, 2] - 0.1, 2)
    unique = np.unique(levels)
    sections = (
        region.section_multiplane(np.zeros(3), [0, 0, 1], list(unique)) if len(unique) else []
    )
    for level, section in zip(unique, sections, strict=True):
        if section is None:
            continue
        pick = levels == level
        count = np.zeros(pick.sum(), dtype=int)
        for loop in section.discrete:
            if len(loop) < 4:
                continue
            ring = shapely.Polygon(loop[:, :2]).buffer(0)
            count += shapely.contains_xy(ring, mids[pick, 0], mids[pick, 1])
        inside[pick] = count % 2 == 1
    # Je Millimeter Höhe die Stützbahn im Bereich und ihre Lage — wo sie steht.
    by_height: dict[float, list[float]] = {}
    for (x, y, z), length in zip(mids[inside], lengths[inside], strict=True):
        entry = by_height.setdefault(float(np.floor(z)), [0.0, x, x, y, y])
        entry[0] += float(length) / 1000.0
        entry[1], entry[2] = min(entry[1], x), max(entry[2], x)
        entry[3], entry[4] = min(entry[3], y), max(entry[4], y)
    report[name] = {
        "support_m": round(float(lengths.sum()) / 1000.0, 2),
        "in_channel_m": round(float(lengths[inside].sum()) / 1000.0, 2),
        "shift": [round(float(value), 2) for value in shift],
        "by_height": {
            f"{z:g}": [round(float(value), 2) for value in entry]
            for z, entry in sorted(by_height.items())
        },
    }
    print(name, json.dumps(report[name]), flush=True)
