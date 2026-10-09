"""Wo steht die Stütze auf? Auflage auf dem Modell gegen Auflage auf dem Bett.

Aufruf: python gcode_auflage.py <ausgabe.json> <gcode> [<gcode> …]

Eine Stütze, die auf dem Modell aufsetzt, hinterlässt dort eine Narbe und hält
fester als eine, die auf dem Bett steht; sie ist auch schwerer zu erreichen.
Gemessen wird je Schicht, wo Stützbahn neu beginnt — nicht über Stützbahn der
Schicht darunter (0,5 mm Spiel für wandernde Äste) — und was davon über
Modellbahn der drei Schichten darunter liegt (der untere Abstand der Stütze ist
eine Schicht). Bahnen werden mit halber Bahnbreite (0,21 mm) zu Flächen.

Ausgabe je Datei: Auflage auf dem Modell (mm²) und Zahl der Aufsetzpunkte,
Auflage auf dem Bett (Stützfläche der ersten Schicht, mm²), frei beginnende
Stütze (weder über Stütze noch über Modell, mm²) und Stützbahn in m.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely

TYPE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
WORD = re.compile(r"([XYZE])(-?(?:\d+\.?\d*|\.\d+))")
SKIP = ("brim", "skirt", "prime", "wipe", "custom", "purge", "flush")
HALF = 0.21
FOLLOW = 0.5
#: Wie tief unter der Stütze Modellbahn liegen darf: unterer Abstand und Schicht.
BELOW = 0.65


def read(path: Path) -> tuple[dict[float, list], dict[float, list]]:
    """Stütz- und Modellsegmente je Schichthöhe: (x0, y0, x1, y1)."""
    support: dict[float, list] = defaultdict(list)
    model: dict[float, list] = defaultdict(list)
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
            # Bögen (G2/G3, Bambu und Prusa fitten sie) als Sehne: Sonst bleibt die
            # Lage stehen, und jede folgende Bahn sitzt falsch.
            if not code.startswith(("G0", "G1", "G2", "G3")):
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
                level = round(nz, 2)
                if "support" in kind or "tree" in kind:
                    support[level].append((x, y, nx, ny))
                elif kind and not any(word in kind for word in SKIP):
                    model[level].append((x, y, nx, ny))
            x, y, z = nx, ny, nz
    return support, model


def area_of(segments: list) -> shapely.Geometry:
    if not segments:
        return shapely.Polygon()
    array = np.asarray(segments)
    lines = shapely.linestrings(array.reshape(-1, 2, 2))
    return shapely.union_all(shapely.buffer(lines, HALF, quad_segs=2))


def measure(path: Path) -> dict:
    support, model = read(path)
    levels = sorted(set(support) | set(model))
    first = min((level for level in levels if level in model or level in support), default=0.0)
    trees = {
        level: shapely.STRtree(shapely.linestrings(np.asarray(model[level]).reshape(-1, 2, 2)))
        for level in levels
        if model.get(level)
    }
    previous = shapely.Polygon()
    on_model = 0.0
    feet = 0
    free = 0.0
    bed = 0.0
    metres = 0.0
    for index, level in enumerate(levels):
        segments = support.get(level, [])
        metres += float(sum(np.hypot(x1 - x0, y1 - y0) for x0, y0, x1, y1 in segments)) / 1000.0
        if not segments:
            continue
        here = area_of(segments)
        if level == first:
            bed += here.area
            previous = here
            continue
        # Gegen die letzte Schicht **mit** Stütze: Mit eigener Schichthöhe der
        # Stütze (Bambu, Creality, Orca am Kobra) liegen Modell- und
        # Stützschichten auf verschiedenen Höhen.
        new = here.difference(previous.buffer(FOLLOW, quad_segs=2))
        previous = here
        if new.is_empty or new.area < 0.05:
            continue
        below = shapely.Polygon()
        for lower in [other for other in levels[:index] if other >= level - BELOW]:
            tree = trees.get(lower)
            if tree is None:
                continue
            hits = tree.query(new.buffer(HALF))
            if len(hits):
                below = below.union(
                    shapely.union_all(shapely.buffer(tree.geometries.take(hits), HALF, quad_segs=2))
                )
        resting = new.intersection(below)
        on_model += resting.area
        free += new.difference(below).area
        if not resting.is_empty:
            feet += len(getattr(resting, "geoms", [resting]))
    return {
        "on_model_mm2": round(on_model, 1),
        "feet": feet,
        "bed_mm2": round(bed, 1),
        "free_start_mm2": round(free, 1),
        "support_m": round(metres, 2),
    }


report = {}
for name in sys.argv[2:]:
    report[name] = measure(Path(name))
    print(name, json.dumps(report[name]), flush=True)
Path(sys.argv[1]).write_text(json.dumps(report, indent=1), encoding="utf-8")
