"""Der Vergleich der genauen Vorschau an der Senkplatte, Stück für Stück (RM-212).

Modell lesen wie die Anwendung, *Bohrung ändern* vorschauen, dann
``difference.compare`` am Körper davor und danach nachstellen: Größe der
Änderungsbox, beschnittene Körper, die zwei Schnitte — mit Zeit und Ausgang.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

TREE = os.environ["SONDE_TREE"]
sys.path.insert(0, TREE)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_ISOLATED = tempfile.mkdtemp(prefix="sonde-vergleich-")
for _variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED

import app  # noqa: E402

assert str(Path(app.__file__).resolve()).startswith(str(Path(TREE).resolve())), app.__file__

from PySide6.QtWidgets import QApplication  # noqa: E402

QT = QApplication.instance() or QApplication([])

from app.core import bootstrap  # noqa: E402

bootstrap.load_operations()

import numpy as np  # noqa: E402

from app.core.geom import difference as difference_module  # noqa: E402
from app.core.geom.mesh import signed_volume  # noqa: E402
from app.core.scene import OperationDraft  # noqa: E402
from app.ui.session import Session  # noqa: E402


def describe(label, mesh):
    raw = mesh.raw
    print(
        f"    {label}: {mesh.triangle_count} Dreiecke, dicht={raw.is_watertight}, "
        f"gleichsinnig={raw.is_winding_consistent}, Volumen={signed_volume(raw):.4f}",
        flush=True,
    )


session = Session()
session.import_model(Path(sys.argv[1]), unit="mm")
result = session.evaluate_now()
body, entry = next(iter(result.scene.objects.items()))
hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
for diameter in (6.0, 6.5, 7.0):
    draft = OperationDraft(op="resize_hole", params={"at_feature": hole, "diameter": diameter}, inputs=(body,))
    scene, _difference, _reason = session._preview_outcome([draft], detect_features=False)
    before, after = entry.mesh, scene.objects[body].mesh
    print(f"Ø {diameter:g}:", flush=True)
    started = time.perf_counter()
    region = difference_module._changed_region(before, after)
    print(f"  Änderungsbox in {time.perf_counter() - started:.2f} s: {None if region is None else np.round(region[1] - region[0], 3)}")
    started = time.perf_counter()
    first, second = difference_module._clipped_to_the_change(before, after, "draft")
    print(f"  beschnitten in {time.perf_counter() - started:.2f} s")
    describe("davor", first)
    describe("danach", second)
    parts = difference_module._comparison_parts(first, second)
    for label, keep, subtract in (("dazu", parts[1], parts[0]), ("weg", parts[0], parts[1])):
        started = time.perf_counter()
        cut = difference_module._cut_parts(keep, subtract, parts[2], "draft")
        print(f"  {label}: {time.perf_counter() - started:.2f} s, {'gescheitert' if cut is None else f'{cut[0].triangle_count} Dreiecke, {cut[0].volume:.3f} mm³'}", flush=True)
session.release(30_000)
