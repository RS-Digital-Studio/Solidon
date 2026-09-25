"""RM-232: Wer ruft PlacementFlow.redraw nach dem ersten Klick so oft? (offscreen)

Aufruf: REDRAW_OUT=<datei> python redraw_callers.py rm232_probe.py <modell> [Sondenschalter]
Die Zählung steht nach jedem Aufruf in der Datei — der Prozess stirbt beim
Abbau von Qt, bevor ein ``atexit`` schreiben könnte.
"""

from __future__ import annotations

import collections
import os
import runpy
import sys
import traceback

from app.ui import placement_flow

OUT = os.environ.get("REDRAW_OUT", "redraw.txt")
CALLERS: collections.Counter[str] = collections.Counter()
original = placement_flow.PlacementFlow.redraw


def redraw(self, *args, **kwargs):
    stack = traceback.extract_stack(limit=8)[:-1]
    CALLERS[" <- ".join(f"{f.name}:{f.lineno}" for f in reversed(stack[-5:]))] += 1
    with open(OUT, "w", encoding="utf-8") as handle:
        for text, count in CALLERS.most_common(12):
            handle.write(f"{count:4d}  {text}\n")
    return original(self, *args, **kwargs)


placement_flow.PlacementFlow.redraw = redraw
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
