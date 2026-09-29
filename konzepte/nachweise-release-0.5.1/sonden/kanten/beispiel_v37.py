"""Schreibt ``tests/data/projects/example_v37.p3d`` aus ``build_example_project`` (§16.2).

Aufruf aus der Wurzel des Arbeitsbaums: python beispiel_v37.py. Nutzerordner
umgebogen wie in der Suite.
"""

import os
import sys
import tempfile
from pathlib import Path

home = tempfile.mkdtemp(prefix="kanten-v37-")
for name in ("APPDATA", "LOCALAPPDATA"):
    os.environ[name] = home
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "tests"))
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.core.scene.migrations import FORMAT_VERSION  # noqa: E402
from app.core.scene.project import save  # noqa: E402
from test_project import build_example_project  # noqa: E402

assert FORMAT_VERSION == 37
target = Path("tests/data/projects/example_v37.p3d")
assert not target.exists()
save(build_example_project(), target)
print("geschrieben:", target)
