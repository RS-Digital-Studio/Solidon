"""Schwere Rechenbibliotheken erst beim ersten wirklichen Rechenschritt laden.

Das Operationsregister importiert jedes Operationsmodul, um Menüs, Dialoge,
Kommandozeile und Agent aus derselben Deklaration zu bauen (§10). Die Module
deklarierten dabei nur Funktionen, luden aber schon ``trimesh`` und damit
``scipy`` sowie ``networkx``. Warm kostete das rund 800 Millisekunden, kalt
mehrere Sekunden — bevor ein Kunde überhaupt ein Modell gewählt hatte.

Diese Stellvertreter ändern keinen Aufruf: ``trimesh.creation.box`` und
``least_squares(...)`` sehen an den Verbrauchsstellen genauso aus. Erst der
erste Attributzugriff lädt das echte Modul. Die Rechnung läuft ohnehin im
Arbeiter; der Hauptthread gewinnt damit Zeit bis zum bedienbaren Fenster,
ohne Geometrie oder Registereinträge zu verändern.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import trimesh as trimesh
    from scipy.optimize import least_squares as least_squares
    from scipy.optimize import linear_sum_assignment as linear_sum_assignment
    from scipy.sparse import csr_matrix as csr_matrix
    from scipy.spatial import cKDTree as cKDTree


class _DeferredModule:
    """Ein Modul, das sich beim ersten Attributzugriff selbst ersetzt."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._loaded: Any | None = None

    def _module(self) -> Any:
        loaded = self._loaded
        if loaded is None:
            loaded = importlib.import_module(self._name)
            self._loaded = loaded
        return loaded

    def __getattr__(self, name: str) -> Any:
        return getattr(self._module(), name)


class _DeferredAttribute:
    """Ein aufrufbarer Name aus einem noch nicht geladenen Modul."""

    def __init__(self, module: str, name: str) -> None:
        self._module_name = module
        self._name = name
        self._loaded: Any | None = None

    def _attribute(self) -> Any:
        loaded = self._loaded
        if loaded is None:
            loaded = getattr(importlib.import_module(self._module_name), self._name)
            self._loaded = loaded
        return loaded

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._attribute()(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._attribute(), name)


if not TYPE_CHECKING:
    trimesh = _DeferredModule("trimesh")
    least_squares = _DeferredAttribute("scipy.optimize", "least_squares")
    linear_sum_assignment = _DeferredAttribute("scipy.optimize", "linear_sum_assignment")
    csr_matrix = _DeferredAttribute("scipy.sparse", "csr_matrix")
    cKDTree = _DeferredAttribute("scipy.spatial", "cKDTree")  # noqa: N816 — SciPy-Name


__all__ = [
    "cKDTree",
    "csr_matrix",
    "least_squares",
    "linear_sum_assignment",
    "trimesh",
]
