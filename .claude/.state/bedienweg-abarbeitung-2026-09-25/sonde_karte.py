"""Sonde: Netzfehlerkarte — Farben im Bild (B3) und Knopf zur Reparatur (B1), offscreen.

Fährt dieselben Schritte wie die zwei Fenstertests in ``tests/test_analysis_ui.py``,
die erst beim Release laufen. Nur lesend gegenüber dem Repository.
"""

from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(r"F:\3D Druck")
sys.path.insert(0, str(ROOT))

import app.ui  # noqa: E402,F401
from PySide6.QtWidgets import QApplication  # noqa: E402

application = QApplication([])

import trimesh  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.perceive import maps  # noqa: E402
from app.core.scene import EvaluationResult  # noqa: E402
from app.core.types import Scene, SceneObject  # noqa: E402
from app.i18n import tr  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.palette import category_colours  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402
from app.ui.viewport import Viewport  # noqa: E402
from tests.render_fakes import RecordingRenderer  # noqa: E402

levels = tuple(str(level) for level in maps.DEFECT_LEVELS)

# B3 — die Ansicht färbt aus derselben Tabelle wie die Legende.
body = MeshData(trimesh.creation.box(extents=(20.0, 20.0, 10.0)))
result = EvaluationResult(
    scene=Scene(objects={"obj_1": SceneObject(id="obj_1", name="Halter", mesh=body)})
)
viewport = Viewport()
renderer = RecordingRenderer()
viewport.renderer = renderer
viewport.show_scene(result)
values = [0.0] * body.triangle_count
values[0] = 3.0
defects = maps.AnalysisMap(
    kind="defects",
    title="Netzfehler",
    values=tuple(values),
    unit="",
    low=0.0,
    high=4.0,
    categories=levels,
)
viewport.set_analysis_map(defects, "obj_1")
drawn = [entry for _kind, entry in renderer.drawn if entry.get("cell_colours") is not None]
colours = drawn[-1]["cell_colours"]
print("B3 kategorisch:", colours.categorical)
print(
    "B3 Tabelle gleich:",
    tuple(colours.colormap) == category_colours(len(levels), viewport.body_colour()),
)
print("B3 erste Farbe:", colours.colormap[0], "Körper:", viewport.body_colour())

# B1 — der Knopf an der Karte.
window = MainWindow(Session(), UiSettings())
window.open_path(ROOT / "tests" / "data" / "meshes" / "plate_holes.stl")
window.session.wait_for_idle()
last = window.session.last_result
object_id = next(iter(last.scene.objects))
mesh = last.scene.objects[object_id].mesh
clean = maps.AnalysisMap(
    kind="defects",
    title="Netzfehler",
    values=(0.0,) * mesh.triangle_count,
    unit="",
    low=0.0,
    high=4.0,
    categories=levels,
    note="Keine Netzfehler gefunden.",
)
window._show_map(clean, object_id)
print("B1 ohne Fehler Knopf:", window.analysis_bar.legend.action)
print("B1 ohne Fehler Satz:", window.analysis_bar.legend.note.text())
hole = dataclasses.replace(clean, values=(1.0,) + (0.0,) * (mesh.triangle_count - 1), note=None)
window._show_map(hole, object_id)
print("B1 Loch nach geschlossenem Import, Knopf:", window.analysis_bar.legend.action)
broken = dataclasses.replace(clean, values=(3.0,) + (0.0,) * (mesh.triangle_count - 1), note=None)
window._show_map(broken, object_id)
button = window.analysis_bar.legend.action
print("B1 mit Fehler Knopf:", button.text() if button else None, "==", tr("Reparieren"))
steps = len(window.session.project.document.ops)
button.click()
window.session.wait_for_idle()
ops = window.session.project.document.ops
print("B1 Schritte:", steps, "->", len(ops), ops[-1].op, ops[-1].inputs)
window._show_map(broken, ops[-1].outputs[0])
print("B1 nach dem Reparieren, Knopf:", window.analysis_bar.legend.action)
window.release()
