"""Filling the registry (Bauplan §10).

Operations register themselves when their module is imported. That import
happens here, explicitly and in one place, instead of as a side effect of
importing some package — a surface that forgets it would otherwise show an
incomplete menu with no error anywhere.
"""

from __future__ import annotations

import importlib
from typing import Final

_OPERATION_MODULES: Final[tuple[str, ...]] = (
    "app.core.scene.ops",
    "app.core.ingest.ops",
    "app.core.geom.ops",
)

_loaded = False


def load_operations() -> None:
    """Import every module that declares operations. Safe to call repeatedly."""
    global _loaded
    if _loaded:
        return
    for name in _OPERATION_MODULES:
        importlib.import_module(name)
    _loaded = True
