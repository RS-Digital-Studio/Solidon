"""Skizzen mit Zwangsbedingungen (Bauplan §30.1).

Das Datenmodell steht als Vertrag in ``app.core.types`` (§9); hier lebt der
Solver. Kein Qt, keine Dialoge — der Kern rechnet, die Oberfläche fragt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from app.core.lazy import install

if TYPE_CHECKING:
    from app.core.sketch.solver import solve_sketch

#: Welcher Name in welchem Untermodul steht — geladen wird erst beim
#: Zugriff, damit zwei Threads sich nicht über die Modul-Locks
#: verklemmen (:mod:`app.core.lazy`).
_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "solve_sketch": ("solver", "solve_sketch"),
}

install(__name__, _EXPORTS)

__all__ = ["solve_sketch"]
