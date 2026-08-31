"""Die Bausteinbibliothek (Bauplan §24).

Anders als der Rest der Anwendung unter MIT lizenziert (siehe die
LICENSE-Datei in diesem Verzeichnis). Der Grund steht in §36: die Geometrie,
die diese Bausteine erzeugen, landet in den eigenen Modellen der Nutzer —
nichts hier darf für sie eine Lizenzfrage aufwerfen.

Bausteine sind gegen ``manifold3d`` gebaut, nicht gegen OpenSCAD —
``insert_part`` hängt so an keiner externen Installation und bleibt testbar.

Ein bloßer Paketimport registriert nichts. Der Anwendungstakt lädt die fünf
mitgelieferten Gruppen ausdrücklich über :mod:`app.core.bootstrap`. Der
öffentliche ``PARTS``-Import behält seine bisherige Zusage und lädt die
Bibliothek beim ersten Zugriff; eigene Bausteine bleiben davon getrennt
(§24.5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from app.core.lazy import install

if TYPE_CHECKING:
    from app.core.knowledge.parts.registry import (
        GROUPS,
        LIBRARY_VERSION,
        PARTS,
        PartChange,
        PartRegistry,
        PartSpec,
        changed_since,
        missing_parts,
        register_part,
    )

_EXPORTS: Final = {
    "GROUPS": ("registry", "GROUPS"),
    "LIBRARY_VERSION": ("registry", "LIBRARY_VERSION"),
    "PARTS": ("builtin", "PARTS"),
    "PartChange": ("registry", "PartChange"),
    "PartRegistry": ("registry", "PartRegistry"),
    "PartSpec": ("registry", "PartSpec"),
    "changed_since": ("builtin", "changed_since"),
    "missing_parts": ("builtin", "missing_parts"),
    "register_part": ("registry", "register_part"),
}

__all__ = [
    "GROUPS",
    "LIBRARY_VERSION",
    "PARTS",
    "PartChange",
    "PartRegistry",
    "PartSpec",
    "changed_since",
    "missing_parts",
    "register_part",
]

install(__name__, _EXPORTS)
