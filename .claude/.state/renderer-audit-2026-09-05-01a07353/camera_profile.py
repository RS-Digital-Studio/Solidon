"""Profiliert den Kamerazug mit Merkmalsbeschriftung am echten Fenster (GFX).

Aufruf: python label_profile.py <projekt.p3d> [--frames 40] [--renderer gfx]
Öffnet ein sichtbares Fenster; nicht neben anderen GPU-Läufen fahren.
"""
from __future__ import annotations
import argparse, cProfile, io, math, os, pstats, sys, time
from pathlib import Path

ROOT = Path(r"F:/3D Druck")
parser = argparse.ArgumentParser()
parser.add_argument("project", type=Path)
parser.add_argument("--frames", type=int, default=40)
parser.add_argument("--renderer", default="gfx")
parser.add_argument("--overlay", action="store_true", help="Merkmalsbeschriftung einschalten")
parser.add_argument("--mode", default=None, help="Darstellungsmodus, z. B. solid_edges")
args = parser.parse_args()
os.environ["SOLIDON_RENDERER"] = args.renderer
os.environ.pop("QT_QPA_PLATFORM", None)
profile = ROOT / "tools" / ".window-bench-profile"
for name in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    os.environ[name] = str(profile / name)
    (profile / name).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
app = QApplication([])
from app.core import bootstrap
bootstrap.load_operations()
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

def sweep():
    widget = app.activeModalWidget()
    if widget is not None:
        widget.close()
    popup = app.activePopupWidget()
    if popup is not None:
        popup.close()
sweeper = QTimer(); sweeper.timeout.connect(sweep); sweeper.start(300)
session = Session()
window = MainWindow(session, UiSettings())
window.resize(1600, 1000); window.move(40, 40); window.show()
for _ in range(30): app.processEvents()
window.open_path(args.project)
deadline = time.perf_counter() + 120
while time.perf_counter() < deadline:
    app.processEvents(); time.sleep(0.005)
    result = getattr(session, "last_result", None)
    if result is not None and result.scene.objects and not session.busy and window.viewport._scene_worker is None:
        break
for _ in range(50): app.processEvents(); time.sleep(0.01)
view = window.viewport
renderer = view.renderer
print("Renderer:", type(renderer).__name__, "Objekte:", len(session.last_result.scene.objects), flush=True)
objects = session.last_result.scene.objects
oid = max(objects, key=lambda key: objects[key].mesh.triangle_count)
if args.mode:
    action = next(a for a in window._mode_group.actions() if a.data() == args.mode)
    action.trigger()
    for _ in range(50): app.processEvents(); time.sleep(0.01)
    while window.viewport._scene_worker is not None: app.processEvents(); time.sleep(0.01)
window.object_tree.select_object(oid) if hasattr(window.object_tree, "select_object") else view.select(oid)
for _ in range(20): app.processEvents(); time.sleep(0.01)
if args.overlay:
    view.set_feature_overlay(True)
    for _ in range(50): app.processEvents(); time.sleep(0.01)
    print("Merkmalsaktoren:", len(view._feature_actors), "Labels:", len(view._feature_label_data), flush=True)
pose = view.camera_pose()
position, focal, up, scale = pose
import numpy as np
centre = np.asarray(focal); start = np.asarray(position)
radius_vec = start - centre
def frame(i):
    angle = 2 * math.pi * i / args.frames
    c, s = math.cos(angle), math.sin(angle)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    p = centre + rot @ radius_vec
    view.set_camera_pose(tuple(p), tuple(centre), (0.0, 0.0, 1.0), scale)
    app.processEvents()
for i in range(5): frame(i)  # warm
times = []
prof = cProfile.Profile()
prof.enable()
for i in range(args.frames):
    t = time.perf_counter(); frame(i); times.append(time.perf_counter() - t)
prof.disable()
times.sort()
print(f"Bild je Kamerastellung: Median {times[len(times)//2]*1000:.1f} ms, p95 {times[int(len(times)*0.95)-1]*1000:.1f} ms, max {times[-1]*1000:.1f} ms", flush=True)
stream = io.StringIO()
stats = pstats.Stats(prof, stream=stream)
stats.sort_stats("cumulative").print_stats(r"app\ui|pygfx|rendercanvas|wgpu", 45)
print(stream.getvalue())
stream = io.StringIO(); stats = pstats.Stats(prof, stream=stream); stats.sort_stats("tottime").print_stats(30); print(stream.getvalue())
view.set_camera_pose(position, focal, up, scale)
window.close(); app.processEvents()
os._exit(0)
