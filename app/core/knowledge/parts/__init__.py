"""Die Bausteinbibliothek (Bauplan §24).

Anders als der Rest der Anwendung unter MIT lizenziert (siehe die
LICENSE-Datei in diesem Verzeichnis). Der Grund steht in §36: die Geometrie,
die diese Bausteine erzeugen, landet in den eigenen Modellen der Nutzer —
nichts hier darf für sie eine Lizenzfrage aufwerfen.

Bausteine sind gegen ``manifold3d`` gebaut, nicht gegen OpenSCAD —
``insert_part`` hängt so an keiner externen Installation und bleibt testbar.

Der Import dieses Pakets registriert die mitgelieferten Bausteine. Eigene
Bausteine aus dem Nutzerverzeichnis werden getrennt und mit Absicht geladen
(§24.5) — sie sind nicht Teil der Anwendung, nur der Bibliothek auf einem
Rechner.
"""

from app.core.knowledge.parts import (  # noqa: F401
    fasteners,
    mechanics,
    mounting,
    structure,
    testbodies,
)
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
