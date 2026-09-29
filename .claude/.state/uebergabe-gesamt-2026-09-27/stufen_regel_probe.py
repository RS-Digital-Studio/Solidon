"""Die Regeln für Stufe F an den gemessenen Prozesslisten vorab prüfen.

Aufruf: python stufen_regel_probe.py <stufen-prozesse.json> [<prusa.json>]
Liest die Listen aus stufen_prozesse.py und zeigt je Slicer und Drucker, welchen
Prozess jede Stufe nach den Regeln aus Entscheidung I bekäme.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LAYER = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*mm\b", re.IGNORECASE)
WORDS = {"fine": ("fine", "detail", "quality"), "draft": ("draft",), "strong": ("strength", "structural")}
TARGET = {"fine": 0.12, "draft": 0.28}
STRONG_TOLERANCE = 0.02


def layer(name: str) -> float | None:
    found = LAYER.match(name)
    return float(found.group(1)) if found else None


def stage(fitting: list[str], standard: str, quality: str) -> str:
    base = layer(standard)
    if base is None:
        return "-"
    best = None
    for name in fitting:
        if name == standard:
            continue
        height = layer(name)
        if height is None:
            continue
        text = name.casefold()
        rank = next((index for index, word in enumerate(WORDS[quality]) if word in text), None)
        if rank is None:
            continue
        if quality == "fine" and not height < base - 1e-9:
            continue
        if quality == "draft" and not height > base + 1e-9:
            continue
        if quality == "strong" and abs(height - base) > STRONG_TOLERANCE:
            continue
        target = base if quality == "strong" else TARGET[quality]
        key = (abs(height - target), rank, len(name), name)
        if best is None or key < best[0]:
            best = (key, name)
    return best[1] if best else "-"


reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in sys.argv[1:]]
merged: dict[str, dict[str, object]] = {}
for report in reports:
    merged.update(report)
for slicer, rows in merged.items():
    if "skip" in rows:
        continue
    for printer, row in rows.items():
        standard = row["chosen"]
        names = [re.sub(r"\s*@.*", "", name) for name in (stage(row["processes"], standard, q) for q in WORDS)]
        print(f"{slicer:8} {printer:22} Standard {re.sub(r'\s*@.*', '', standard):22} -> "
              f"Fein {names[0]:22} Entwurf {names[1]:22} Belastbar {names[2]}")
