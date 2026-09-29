"""Der Nachbau der gs-100-Mündung als Hilfsmodul: Platte 44 × 24 × 12, Unterseite
Zylinder R (Achse X, R = 0 heißt eben), Bohrung Ø 6 mit Zylindersenkung Ø 10
unten und Fase oben bei x = −8, die Mündungskante der Senkung um r gerundet.

Importiert erst, nachdem ``common`` den Baum gesetzt hat.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Curve
from tests.test_feature_moves_keep_shape import BOTH_ENDS

from app.core.brep import edit
from app.core.sketch.planes import frame_of


def plate(radius: float):
    """Die Platte ohne Bohrung."""
    body = edit.box(44.0, 24.0, 12.0)
    if radius > 0.0:
        roll = edit.revolved_bore_tool(
            [(0.0, -30.0), (radius, -30.0), (radius, 30.0), (0.0, 30.0), (0.0, -30.0)],
            frame_of((1.0, 0.0, 0.0), (0.0, 0.0, radius)),
        )
        body = edit.unified(edit.boolean("intersection", [body, roll]))
    return body


def built(radius: float, rounding: float, *, at: float = -8.0):
    """Die Platte mit Bohrung, Senkung und gerundeter Mündungskante."""
    solid = edit.bore_profile(
        plate(radius), list(BOTH_ENDS["Zylindersenkung und Fase"]), frame_of((0, 0, 1), (at, 0, 0))
    )
    picked = []
    for index, edge in enumerate(solid.edges()):
        curve = BRepAdaptor_Curve(edge)
        middle = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2.0)
        if abs(((middle.X() - at) ** 2 + middle.Y() ** 2) ** 0.5 - 5.0) < 0.05 and middle.Z() < 2.0:
            picked.append(index)
    return edit.fillet(solid, rounding, selected_edges=picked) if rounding > 0.0 else solid
