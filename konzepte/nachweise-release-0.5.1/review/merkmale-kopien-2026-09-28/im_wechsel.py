"""Fährt die Minigolf-Sonde im Wechsel vorher/nachher, je zweimal, nacheinander.

Aufruf (gebunden): python bound.py im_wechsel.py
"""

import subprocess
import sys
from pathlib import Path

OUT = Path(r"F:\3D Druck\output\review\merkmale-kopien-2026-09-28")
PROBE = OUT / "sonde_minigolf.py"
TREES = {
    "vorher": r"%USERPROFILE%\AppData\Local\Temp\claude\F--3D-Druck\d53049d8-8567-40fb-bb95-f784e37acda5\scratchpad\vorher",
    "nachher": r"F:\3D Druck\.claude\worktrees\agent-a04370ddf520c87cd",
}
for round_ in (1, 2):
    for label, tree in TREES.items():
        name = f"{label}-{round_}"
        with open(OUT / f"{name}.log", "w", encoding="utf-8") as log:
            code = subprocess.run(
                [sys.executable, str(PROBE), tree, str(OUT / f"{name}.json")],
                stdout=log,
                stderr=subprocess.STDOUT,
            ).returncode
        print(name, code, flush=True)
