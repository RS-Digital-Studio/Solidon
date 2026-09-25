"""RM-232: Was kostet die Arbeiterkopie mit und ohne trimesh-Cache, und was bringt sie?"""

from __future__ import annotations

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
path = Path(sys.argv[1])
project = new_project("centauri-carbon-2", "petg")
document = project.document
document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
project.sources["src_1"] = path.read_bytes()
History(document).apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
profile = profiles.make_profile("centauri-carbon-2", "petg")
result = evaluate(project.document, profile, sources=ProjectSources(project))
entry = next(iter(result.scene.objects.values()))
source = as_mesh_data(entry.mesh)
raw = source.raw
print("Dreiecke", len(raw.faces), "Cacheeinträge", len(raw._cache.cache))
sizes = sorted(((getattr(v, "nbytes", 0), k) for k, v in raw._cache.cache.items()), reverse=True)
print("größte:", [(k, round(n / 1e6, 1)) for n, k in sizes[:8]], "MB gesamt", round(sum(n for n, _ in sizes) / 1e6, 1))
for include in (False, True, False, True):
    t = time.perf_counter()
    copy = raw.copy(include_cache=include)
    print(f"copy(include_cache={include}) {(time.perf_counter() - t) * 1000:6.1f} ms  Einträge {len(copy._cache.cache)}")
print({k: type(v).__name__ for k, v in raw._cache.cache.items() if not hasattr(v, "nbytes")})
print({k: bool(getattr(v, "flags", None) is not None and v.flags.writeable) for k, v in raw._cache.cache.items() if hasattr(v, "flags")})
