"""Wohin gehen die Sekunden einer groben Vorschau nach der ersten? (RM-212)

Liest das Modell wie die Anwendung, rechnet die erste grobe Vorschau
(*Bohrung* Ø 5 durch die Mitte der Oberseite) und profiliert die zweite (Ø 6).
Baum aus ``SONDE_TREE``.
"""

from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys
import tempfile
import time
from pathlib import Path

TREE = os.environ["SONDE_TREE"]
sys.path.insert(0, TREE)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_ISOLATED = tempfile.mkdtemp(prefix="sonde-profil-")
for _variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED

import app  # noqa: E402

assert str(Path(app.__file__).resolve()).startswith(str(Path(TREE).resolve())), app.__file__

from PySide6.QtWidgets import QApplication  # noqa: E402

QT = QApplication.instance() or QApplication([])

from app.core import bootstrap  # noqa: E402

bootstrap.load_operations()

from app.core.scene import OperationDraft  # noqa: E402
from app.ui.session import Session  # noqa: E402


def drill(body, entry, diameter):
    low, high = entry.mesh.bounds.minimum, entry.mesh.bounds.maximum
    return OperationDraft(
        op="drill_hole",
        params={"diameter": diameter, "x": (low[0] + high[0]) / 2.0, "y": (low[1] + high[1]) / 2.0, "z": high[2], "depth": 0.0},
        inputs=(body,),
    )


session = Session()
session.import_model(Path(sys.argv[1]), unit="mm")
result = session.evaluate_now()
body, entry = max(result.scene.objects.items(), key=lambda item: item[1].mesh.triangle_count)
seen: list[int] = []
started = time.perf_counter()
session._preview_outcome(detect_features=False, coarsened=seen.append, drafts=[drill(body, entry, 5.0)])
print(f"erste grobe Vorschau {time.perf_counter() - started:.2f} s, grob={bool(seen)}", flush=True)
profile = cProfile.Profile()
started = time.perf_counter()
profile.enable()
session._preview_outcome(detect_features=False, coarsened=seen.append, drafts=[drill(body, entry, 6.0)])
profile.disable()
print(f"zweite grobe Vorschau {time.perf_counter() - started:.2f} s", flush=True)
out = io.StringIO()
pstats.Stats(profile, stream=out).sort_stats("cumulative").print_stats(45)
print(out.getvalue()[:12000])
session.release(30_000)
