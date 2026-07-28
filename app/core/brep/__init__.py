"""The second construction kernel (Bauplan §30).

Boundary representation next to the mesh kernel, not instead of it. What it
buys is what a mesh cannot give: real edges, and therefore fillets and chamfers
that are round rather than faceted, precise booleans without tessellation
artefacts, and STEP in and out.

The way from B-Rep to mesh is open at any time; the way back is not, and the
object tree says so (§30). That is not a shortcoming to hide — a mesh has lost
the edges it was made from, and pretending otherwise would produce a body whose
"exact" fillet is a polygon.
"""

from __future__ import annotations

from app.core.brep.kernel import BRepUnavailable, Solid, available

__all__ = ["BRepUnavailable", "Solid", "available"]
