"""RM-232: Was kosten die Kernauskünfte an der Arbeiterkopie gegen das Original?

Aufruf: python kopie_kalt.py <modell> [--profile=<datei>] [--order=orig,copy,cache]
"""

from __future__ import annotations

import cProfile
import os
import sys
import tempfile
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
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
from app.ui.panels import feature_answers  # noqa: E402

path = Path(sys.argv[1])
ARGS = dict(a.lstrip("-").split("=", 1) if "=" in a else (a.lstrip("-"), "1") for a in sys.argv[2:])
project = new_project("centauri-carbon-2", "petg")
document = project.document
document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
project.sources["src_1"] = path.read_bytes()
history = History(document)
history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
profile = profiles.make_profile("centauri-carbon-2", "petg")
start = time.perf_counter()
result = evaluate(project.document, profile, sources=ProjectSources(project))
print(f"ausgewertet in {time.perf_counter() - start:.2f} s")
entry = next(iter(result.scene.objects.values()))
features = entry.features
source = as_mesh_data(entry.mesh)
fid = ARGS.get("feature", next(f for f, v in features.items() if v.kind == "hole"))
feature = features[fid]
order = ARGS.get("order", "orig,copy,cache").split(",")
profiler = cProfile.Profile() if "profile" in ARGS else None
for way in order:
    if way == "orig":
        mesh = source
    elif way == "copy":
        mesh = source.replacing(source.raw.copy())
    else:
        mesh = source.replacing(source.raw.copy(include_cache=True))
    for round_ in (1, 2):
        if profiler is not None and way == ARGS.get("profile_way", "copy") and round_ == 1:
            profiler.enable()
        t = time.perf_counter()
        feature_answers(fid, feature, features, mesh)
        took = (time.perf_counter() - t) * 1000
        if profiler is not None:
            profiler.disable()
        print(f"{way:6s} Runde {round_}  {took:8.1f} ms")
if profiler is not None:
    profiler.dump_stats(ARGS["profile"])
