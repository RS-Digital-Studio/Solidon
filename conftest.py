"""Makes the repository importable without an install step."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402

# The registry has to be filled before tests are collected: the consistency
# checks in tests/test_registry_consistency.py parametrise over it.
load_operations()
