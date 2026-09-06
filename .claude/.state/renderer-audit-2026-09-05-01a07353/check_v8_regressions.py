"""Lädt ausdrücklich den alten Viewport und prüft aktuelle neue Gegenbeispiele."""

from pathlib import Path
import os
import sys

root = Path(__file__).resolve().parent
source = root / "final-source-v8"
repository = root.parents[2]
sys.path.insert(0, str(source))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import app.ui.viewport as viewport

assert Path(viewport.__file__).resolve() == source / "app/ui/viewport.py"
print(f"Unveränderter Viewport: {viewport.__file__}", flush=True)

import pytest

raise SystemExit(pytest.main([
    str(repository / "tests/test_viewport_decisions.py"),
    str(repository / "tests/test_feature_label_layout.py"),
    "-q", "-k", "bed_visibility_reuses or bed_visibility_uses or clipped_face_anchor or bore_marker_keeps",
]))
