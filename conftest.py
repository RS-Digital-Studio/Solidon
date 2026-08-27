"""Macht das Repository ohne Installationsschritt importierbar."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402

# Das Register muss gefüllt sein, bevor die Tests eingesammelt werden: die
# Konsistenzprüfungen in tests/test_registry_consistency.py parametrisieren
# darüber.
load_operations()
