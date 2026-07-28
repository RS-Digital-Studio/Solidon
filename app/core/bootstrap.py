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
    "app.core.geom.prepare_ops",
    "app.core.geom.primitive_ops",
)

#: The part library declares no operations itself — one is generated per part
#: (§24.1). Importing the package fills the part registry, the call after it
#: turns every entry into an operation.
_PART_MODULE: Final = "app.core.knowledge.parts"

_loaded = False


def load_operations() -> None:
    """Import every module that declares operations. Safe to call repeatedly."""
    global _loaded
    if _loaded:
        return
    for name in _OPERATION_MODULES:
        importlib.import_module(name)
    importlib.import_module(_PART_MODULE)
    importlib.import_module(f"{_PART_MODULE}.ops").register_all()
    _loaded = True
