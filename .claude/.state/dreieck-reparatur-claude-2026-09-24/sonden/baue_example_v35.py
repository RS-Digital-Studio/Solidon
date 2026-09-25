"""Einmalig: tests/data/projects/example_v35.p3d aus build_example_project()."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from app.core.bootstrap import load_operations  # noqa: E402
from app.core.scene.migrations import FORMAT_VERSION  # noqa: E402
from app.core.scene.project import save  # noqa: E402

assert FORMAT_VERSION == 35
load_operations()
from tests.test_project import build_example_project  # noqa: E402

target = Path("tests/data/projects/example_v35.p3d")
assert not target.exists()
save(build_example_project(), target)
print(target, target.stat().st_size)
