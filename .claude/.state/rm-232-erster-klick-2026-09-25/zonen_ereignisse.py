"""RM-232: Welche Ereignisse der Überlagerungszonen lösen nach dem ersten Klick Bilder aus?"""

from __future__ import annotations

import collections
import os
import runpy
import sys

from PySide6.QtCore import QEvent

from app.ui import placement_flow

OUT = os.environ.get("ZONES_OUT", "zonen.txt")
SEEN: collections.Counter[str] = collections.Counter()
original = placement_flow.PlacementFlow.eventFilter


def event_filter(self, watched, event):
    if getattr(self, "active", False) and watched in getattr(self, "_overlay_zones", ()) and event.type() in (
        QEvent.Type.Move,
        QEvent.Type.Resize,
        QEvent.Type.Show,
        QEvent.Type.Hide,
    ):
        detail = ""
        if event.type() == QEvent.Type.Resize:
            detail = f" {event.oldSize().width()}x{event.oldSize().height()}->{event.size().width()}x{event.size().height()}"
        SEEN[f"{type(watched).__name__}:{watched.objectName()} {event.type().name}{detail}"] += 1
        with open(OUT, "w", encoding="utf-8") as handle:
            for text, count in SEEN.most_common(30):
                handle.write(f"{count:4d}  {text}\n")
    return original(self, watched, event)


placement_flow.PlacementFlow.eventFilter = event_filter
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
