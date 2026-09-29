"""Sonde zu Fehlschlag 3: Rechnet die Auswertung nach dem Übernehmen im Hilfsprozess?

Stellt ``test_the_workers_of_the_window_use_the_helper`` nach und druckt die
Zählung des Hilfsprozesses und die Fäden, in denen ``refine_conforming``
gefragt wird.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading

sys.path.insert(0, r"F:\3D Druck.review-051\wt-cifix")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = tempfile.mkdtemp(prefix="cifix-")
os.environ["APPDATA"] = home
os.environ["LOCALAPPDATA"] = home

from pathlib import Path  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.geom import kernel_process  # noqa: E402

app = QApplication([])
kernel_process.OFFLOAD_ABOVE = 0  # type: ignore[misc]

asked: list[tuple[str, bool, str]] = []
original = kernel_process.run


def noted(job, arrays, values, *, weight, cancelled=None):  # type: ignore[no-untyped-def]
    asked.append((job, kernel_process.offloaded(weight), threading.current_thread().name))
    return original(job, arrays, values, weight=weight, cancelled=cancelled)


kernel_process.run = noted  # type: ignore[assignment]

from app.core.scene import OperationDraft  # noqa: E402
from app.ui.session import Session  # noqa: E402

MESHES = Path(r"F:\3D Druck.review-051\wt-cifix\tests\data\meshes")
session = Session()
assert session.import_model(MESHES / "near_sphere_ellipsoid.stl", unit="mm")
session._leash.wait_all(timeout_ms=120_000)
result = session.evaluate_now()
body = next(iter(result.scene.objects))
print("vorher", kernel_process.statistics(), flush=True)
before = session.last_result
session.history.apply(
    "Verfeinern", [OperationDraft(op="remesh_mesh", params={"edge": 0.8}, inputs=(body,))]
)
print("idle", session.wait_for_idle(60_000), flush=True)
print("neues Ergebnis", session.last_result is not before, flush=True)
print("Schritte", [e.op for e in session.project.document.ops], flush=True)
print("gefragt", asked, flush=True)
print("nachher", kernel_process.statistics(), flush=True)
session.release()
kernel_process.shutdown()
