"""RM-232: Was kosten die Kernauskünfte des Merkmalfensters beim ersten Klick — ohne Fenster.

Aufruf: python antworten_zerlegt.py <modell> [--profile=<datei>]
Lädt wie die Anwendung (evaluate), fragt dann je Bohrung und Fläche nacheinander
die drei Auskünfte aus ``FeaturePanel._answers_for`` und misst jede einzeln.
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
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import relations  # noqa: E402
from app.core.perceive.actions import actions_for  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
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
mesh, features = entry.mesh, entry.features
chosen = [fid for fid, f in features.items() if f.kind in ("hole", "slot", "face")][:6]

profiler = cProfile.Profile() if "profile" in ARGS else None
for fid in chosen:
    feature = features[fid]
    stamps = [time.perf_counter()]
    if profiler is not None:
        profiler.enable()
    state = relations.cavity_chain_state_at(feature, features, mesh)
    stamps.append(time.perf_counter())
    actions = actions_for(
        feature,
        features,
        mesh=mesh,
        cavity=state.chain or (),
        touches_other=state.touches_other,
        reason=state.reason,
    )
    stamps.append(time.perf_counter())
    groups = relations.alike_for_actions(
        (str(action.op) for action in actions if action.op), fid, features, mesh
    )
    stamps.append(time.perf_counter())
    if profiler is not None:
        profiler.disable()
    parts = [(b - a) * 1000 for a, b in zip(stamps, stamps[1:], strict=False)]
    print(
        f"{fid:10s} {feature.kind:6s} Kette {parts[0]:7.1f}  Handlungen {parts[1]:7.1f}"
        f"  Gleichartige {parts[2]:7.1f} ms  ({len(groups)} Gruppen)"
    )
if profiler is not None:
    profiler.dump_stats(ARGS["profile"])
