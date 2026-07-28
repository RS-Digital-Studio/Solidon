"""The part library (Bauplan §24).

Licensed under MIT, unlike the rest of the application (see the LICENSE file in
this directory). The reason is in §36: the geometry these parts produce ends up
in the users' own models, so nothing here may raise a licence question for them.

Parts are built against ``manifold3d``, not OpenSCAD, so ``insert_part`` depends
on no external installation and stays testable.

Importing this package registers the shipped parts. Own parts from the user
directory are loaded separately and on purpose (§24.5) — they are not part of
the application, only of the library on one machine.
"""

from app.core.knowledge.parts import fasteners, mechanics, mounting, structure  # noqa: F401
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
