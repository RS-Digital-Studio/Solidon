"""Schichten, in denen der Slicer am Anschlag seines Mindesttempos druckt.

Aufruf: python gcode_anschlag.py <mindesttempo mm/s> <gcode> [<mindesttempo> <gcode> …]

Eine Schicht steht am Anschlag, wenn ihr schnellster Extrusionsvorschub nicht über
dem Mindesttempo liegt: Dann hat der Slicer alles auf das Mindesttempo gebremst und
die Mindestschichtzeit trotzdem nicht erreicht.
"""

from __future__ import annotations

import re
import sys

LAYER = re.compile(r"^;\s*(?:LAYER_CHANGE|CHANGE_LAYER|LAYER\s*:\s*-?\d+)", re.IGNORECASE)
WORD = re.compile(r"([A-Z])(-?(?:\d+\.?\d*|\.\d+))")


def floored(path: str, minimum: float) -> list[float]:
    z = 0.0
    feed = 0.0
    relative = False
    e = 0.0
    fastest = 0.0
    printed = False
    layers: list[tuple[float, float, bool]] = []
    with open(path, encoding="utf-8", errors="replace") as handle:  # noqa: PTH123
        for raw in handle:
            line = raw.strip()
            if line.startswith(";"):
                if LAYER.match(line):
                    layers.append((z, fastest, printed))
                    fastest = 0.0
                    printed = False
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
            elif command in ("G1", "G2", "G3"):
                if "F" in words:
                    feed = words["F"] / 60.0
                if "Z" in words:
                    z = words["Z"]
                extrude = 0.0
                if "E" in words:
                    extrude = words["E"] if relative else words["E"] - e
                    if not relative:
                        e = words["E"]
                if extrude > 0.0 and ("X" in words or "Y" in words):
                    fastest = max(fastest, feed)
                    printed = True
    layers.append((z, fastest, printed))
    return [z for z, fast, printed in layers if printed and fast <= minimum + 0.05]


arguments = sys.argv[1:]
for minimum, path in zip(arguments[0::2], arguments[1::2], strict=True):
    hits = floored(path, float(minimum))
    print(
        f"{path[-60:]}: {len(hits)} Schichten am Anschlag {minimum} mm/s, ab z {min(hits, default=None)}"
    )
