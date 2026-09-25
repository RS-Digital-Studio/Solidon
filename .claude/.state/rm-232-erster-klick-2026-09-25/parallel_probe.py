"""RM-232: Überlappen Kernauskünfte und Trägerfläche in zwei Fäden an zwei Kopien?"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
_iso = tempfile.mkdtemp(prefix="solidon-sonde-")
for var in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[var] = _iso

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.placement import seat_of  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
from app.ui.panels import feature_answers  # noqa: E402

path = Path(sys.argv[1])
mode = sys.argv[2]
project = new_project("centauri-carbon-2", "petg")
document = project.document
document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
project.sources["src_1"] = path.read_bytes()
History(document).apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
profile = profiles.make_profile("centauri-carbon-2", "petg")
result = evaluate(project.document, profile, sources=ProjectSources(project))
entry = next(iter(result.scene.objects.values()))
features = entry.features
source = as_mesh_data(entry.mesh)
a = source.replacing(source.raw.copy(include_cache=True))
b = source.replacing(source.raw.copy(include_cache=True))
fid = next(f for f, v in features.items() if v.kind == "hole")
feature = features[fid]
times = {}


def answers():
    t = time.perf_counter()
    feature_answers(fid, feature, features, a)
    times["answers"] = time.perf_counter() - t


def seat():
    t = time.perf_counter()
    seat_of(b if mode == "parallel" else a, feature, features)
    times["seat"] = time.perf_counter() - t


start = time.perf_counter()
if mode == "parallel":
    threads = [threading.Thread(target=answers), threading.Thread(target=seat)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
else:
    answers()
    seat()
wall = time.perf_counter() - start
print(f"{mode}: Wand {wall * 1000:.0f} ms, Antworten {times['answers'] * 1000:.0f}, Sitz {times['seat'] * 1000:.0f}")
