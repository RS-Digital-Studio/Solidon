"""Der zweite Konstruktionskern (Bauplan §30).

Boundary Representation neben dem Mesh-Kern, nicht an seiner Stelle. Was er
einbringt, ist, was ein Netz nicht geben kann: echte Kanten, und damit Fasen
und Verrundungen, die rund sind statt facettiert, präzise Boolesche Ops ohne
Tessellations-Artefakte, und STEP hinein wie hinaus.

Der Weg von B-Rep zu Mesh steht jederzeit offen; der Rückweg nicht, und der
Objektbaum sagt das auch (§30). Das ist kein Mangel, den man versteckt — ein
Netz hat die Kanten verloren, aus denen es gebaut wurde, und das Gegenteil zu
behaupten ergäbe einen Körper, dessen „exakte" Verrundung ein Vieleck ist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from app.core.lazy import install

if TYPE_CHECKING:
    from app.core.brep.kernel import BRepUnavailable, Solid, available

#: Welcher Name in welchem Untermodul steht — geladen wird erst beim
#: Zugriff, damit zwei Threads sich nicht über die Modul-Locks
#: verklemmen (:mod:`app.core.lazy`).
_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "BRepUnavailable": ("kernel", "BRepUnavailable"),
    "Solid": ("kernel", "Solid"),
    "available": ("kernel", "available"),
}

install(__name__, _EXPORTS)

__all__ = ["BRepUnavailable", "Solid", "available"]
