"""RM-268: Knöpfe an Befunden eines verbrauchten Körpers (ohne Fenster).

Aufruf: python s268_verbraucht.py <baum> [modell] [schritt]
schritt: split_bodies (Vorgabe) oder split_model
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

TREE = sys.argv[1]
sys.path.insert(0, TREE)
_guard = threading.Timer(600, lambda: os._exit(9))
_guard.daemon = True
_guard.start()
tmp = tempfile.mkdtemp(prefix="s268-")
os.environ["APPDATA"] = tmp
os.environ["LOCALAPPDATA"] = tmp
import app  # noqa: E402

print("app:", app.__file__, flush=True)
assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve())

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Document, Source  # noqa: E402

load_operations()
from app.ui.main_window import MainWindow  # noqa: E402,F401  (Handlernamen zum Abgleich)
from app.ui.panels import actions_for_document  # noqa: E402

model = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(TREE) / "tests/data/meshes/crossing_and_apart.stl"
step = sys.argv[3] if len(sys.argv) > 3 else "split_bodies"
profile = profiles.make_profile("centauri-carbon-2", "petg")
document = Document(format_version=1, app_version="0.0.1")
project = new_project("centauri-carbon-2", "petg")
project.document = document
document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{model.name}", sha256="")
project.sources["src_1"] = model.read_bytes()
history = History(document)
history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
first = evaluate(document, profile, sources=ProjectSources(project))
print("nach Laden:", sorted(first.scene.objects), [f.code for f in first.scene.report.findings])
if step == "split_bodies":
    count = next(
        (f.values.get("components") for f in first.scene.report.findings if f.code == "ingest.multiple_components"),
        2,
    )
    history.apply("Zerlegen", [OperationDraft(op="split_bodies", inputs=("obj_1",), params={"count": count, "keep_tiny": True})])
else:
    from app.core.geom.mesh import as_mesh_data
    from app.core.split import SplitTarget, apply_pinned_split

    entry = first.scene.objects["obj_1"]
    mesh = as_mesh_data(entry.mesh)
    low, high = mesh.bounds.minimum, mesh.bounds.maximum
    axis = "xyz"[max(range(3), key=lambda i: high[i] - low[i])]
    index = "xyz".index(axis)
    apply_pinned_split(
        document,
        [SplitTarget("obj_1", mesh=mesh, features=entry.features)],
        {"axis": axis, "position": (low[index] + high[index]) / 2.0},
        title="Teilen",
    )
result = evaluate(document, profile, sources=ProjectSources(project))
live = result.scene.objects
print("nach", step, ":", sorted(live), "vollständig:", result.complete)
consumed = 0
for finding in result.scene.report.findings:
    offered = [a.id for a in actions_for_document(finding, document, stopped_at=result.stopped_at, live_objects=live)]
    target = finding.object_id
    gone = target is not None and target not in live
    consumed += gone
    print(f"{'VERBRAUCHT ' if gone else ''}{finding.code} @ {target} op {finding.op_id}: {offered}")
print("Befunde an verbrauchten Körpern:", consumed)
