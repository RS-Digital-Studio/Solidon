"""Wohin gehen die Sekunden der genauen Vorschau von *Bohrung ändern* an der Senkplatte? (RM-212)

Übernommen aus ``review-050/sonden/ansicht/prof_preview.py``: Modell lesen wie
die Anwendung, die erste Bohrung wählen, ``resize_hole`` auf Ø 6 vorschauen
wie der Dialog (``detect_features=False``) — einmal zum Aufwärmen, einmal
profiliert. Baum aus ``SONDE_TREE``.
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
_ISOLATED = tempfile.mkdtemp(prefix="sonde-genau-")
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

session = Session()
started = time.perf_counter()
session.import_model(Path(sys.argv[1]), unit="mm")
result = session.evaluate_now()
body, entry = next(iter(result.scene.objects.items()))
hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
print(
    f"{Path(sys.argv[1]).name}: {entry.mesh.triangle_count} Dreiecke, {len(entry.features)} Merkmale, "
    f"Bohrung {hole} Ø {entry.features[hole].params.get('diameter')}, geöffnet in {time.perf_counter() - started:.1f} s",
    flush=True,
)
for number, diameter in enumerate((6.0, 6.5, 7.0)):
    draft = OperationDraft(op="resize_hole", params={"at_feature": hole, "diameter": diameter}, inputs=(body,))
    profile = cProfile.Profile() if number == 1 else None
    started = time.perf_counter()
    if profile:
        profile.enable()
    _scene, difference, reason = session._preview_outcome([draft], detect_features=False)
    if profile:
        profile.disable()
    print(f"  Ø {diameter:g}: {time.perf_counter() - started:.2f} s, Vorschau={difference is not None} {reason[:80]}", flush=True)
    if profile:
        out = io.StringIO()
        pstats.Stats(profile, stream=out).sort_stats("cumulative").print_stats(60)
        profiled = out.getvalue()
session.release(30_000)
print(profiled[:16000])
