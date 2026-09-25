"""Review-Sonde: Welche neuen Füllwege fahren die Plattformwege aus `_WAYS`? (nur lesend)"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"F:\3D Druck")
sys.path.insert(0, str(ROOT))

import app.core.bootstrap  # noqa: E402,F401
from app.core.geom import repair as R  # noqa: E402
from app.core.perceive import features as F  # noqa: E402
from tests import test_platform_identity as P  # noqa: E402

calls: Counter[str] = Counter()


def counted(module, name):
    original = getattr(module, name)

    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        calls[name + ("" if result is None else ":ergebnis")] += 1
        return result

    setattr(module, name, wrapper)


for name in ("_bridged_holes", "_band_between", "_smoothest_fill", "_loop_triangles", "_loop_fan"):
    counted(R, name)
counted(F, "_point_inside_shell")

for way in ("import_repair", "repair_selfint", "thicken"):
    calls.clear()
    P._WAYS[way]()
    print(way, dict(calls))
