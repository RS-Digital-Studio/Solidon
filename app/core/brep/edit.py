"""Einen B-Rep-Körper formen (Bauplan §30, §25).

Die zwei Operationen, die der Grund für einen zweiten Kern sind: Verrundung
und Fase an echten Kanten. Auf einem Netz sind beide Näherungen einer
Näherung — die Kante ist schon eine Kette von Segmenten, und sie zu runden
rundet die Segmente. Hier ist die Kante eine Kurve, und das Ergebnis ist
exakt.

Welche Kanten behandelt werden, ist eine Auswahl, und die Auswahl läuft über
Geometrie, nicht über Indizes: ein Index in die Topologie eines Körpers
ändert sich, sobald sich irgendetwas anderes an ihm ändert, und eine
Verrundung, die wandert, wenn ein unbeteiligtes Loch gebohrt wird, ist
schlimmer als gar keine (§21.2, derselbe Grund, aus dem Merkmalsbezeichner
zugeordnet werden).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.brep.kernel import Solid, require
from app.core.errors import CANCEL, CORRECT_INPUT, PROGRAMMING_ERRORS, GeometryError
from app.core.log import get_logger
from app.core.types import Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

EdgeChoice = Literal["all", "vertical", "horizontal", "top", "bottom"]

#: Welche Kanten eine Auswahl meint. „Senkrecht" ist, was jemand mit „runde
#: die Ecken dieser Box" meint: die vier Stehenden, nicht die Plattenkanten.
EDGE_CHOICES: tuple[EdgeChoice, ...] = ("all", "vertical", "horizontal", "top", "bottom")


@dataclass(frozen=True, slots=True)
class EdgeInfo:
    """Eine Kante, beschrieben über das, was sie ist, statt über ihren
    Speicherplatz.
    """

    edge: Any
    length: float
    direction: Vec3
    middle: Vec3

    @property
    def upright(self) -> bool:
        return abs(self.direction[2]) > 0.9

    @property
    def flat(self) -> bool:
        return abs(self.direction[2]) < 0.1


def box(width: float, depth: float, height: float) -> Solid:
    """Ein Quader auf dem Bett, in X und Y zentriert — derselbe Ankerpunkt wie
    auf der Mesh-Seite.
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    corner = gp_Pnt(-width / 2.0, -depth / 2.0, 0.0)
    return Solid(BRepPrimAPI_MakeBox(corner, width, depth, height).Shape())


def cylinder(diameter: float, height: float) -> Solid:
    """Ein Zylinder, stehend auf Z = 0."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    return Solid(BRepPrimAPI_MakeCylinder(diameter / 2.0, height).Shape())


def edges_of(solid: Solid) -> list[EdgeInfo]:
    """Jede Kante mit den Zahlen, aus denen sich eine Auswahl treffen lässt."""
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    described: list[EdgeInfo] = []
    for edge in solid.edges():
        props = GProp_GProps()
        BRepGProp.LinearProperties_s(edge, props)
        length = float(props.Mass())
        if length <= EPS_GEOM:
            continue

        curve = BRepAdaptor_Curve(edge)
        start = curve.Value(curve.FirstParameter())
        end = curve.Value(curve.LastParameter())
        span = (end.X() - start.X(), end.Y() - start.Y(), end.Z() - start.Z())
        norm = max((span[0] ** 2 + span[1] ** 2 + span[2] ** 2) ** 0.5, EPS_GEOM)
        centre = props.CentreOfMass()
        described.append(
            EdgeInfo(
                edge=edge,
                length=length,
                direction=(span[0] / norm, span[1] / norm, span[2] / norm),
                middle=(centre.X(), centre.Y(), centre.Z()),
            )
        )
    return described


def choose(solid: Solid, choice: EdgeChoice) -> list[EdgeInfo]:
    """Die Kanten, die eine benannte Auswahl meint."""
    described = edges_of(solid)
    if choice == "all":
        return described
    if choice == "vertical":
        return [entry for entry in described if entry.upright]
    if choice == "horizontal":
        return [entry for entry in described if entry.flat]

    heights = [entry.middle[2] for entry in described]
    if not heights:
        return []
    wanted = max(heights) if choice == "top" else min(heights)
    return [
        entry
        for entry in described
        if entry.flat and abs(entry.middle[2] - wanted) <= EPS_GEOM * 1000
    ]


def fillet(solid: Solid, radius: float, choice: EdgeChoice = "all") -> Solid:
    """Rundet die gewählten Kanten. Exakt, weil die Kante eine Kurve
    ist (§30).
    """
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

    chosen = choose(solid, choice)
    if not chosen:
        raise GeometryError(
            detail=_("Zu dieser Auswahl gehört keine Kante."),
            values={"choice": choice},
        )

    builder = BRepFilletAPI_MakeFillet(solid.shape)
    for entry in chosen:
        builder.Add(radius, entry.edge)
    return _built(solid, builder, "fillet", radius, len(chosen))


def chamfer(solid: Solid, distance: float, choice: EdgeChoice = "all") -> Solid:
    """Break the chosen edges at 45 degrees."""
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer

    chosen = choose(solid, choice)
    if not chosen:
        raise GeometryError(
            detail=_("Zu dieser Auswahl gehört keine Kante."),
            values={"choice": choice},
        )

    builder = BRepFilletAPI_MakeChamfer(solid.shape)
    for entry in chosen:
        builder.Add(distance, entry.edge)
    return _built(solid, builder, "chamfer", distance, len(chosen))


def _built(solid: Solid, builder: Any, kind: str, size: float, edges: int) -> Solid:
    """Führt den Builder aus und macht aus seinem Scheitern einen Satz, auf
    den jemand reagieren kann.
    """
    try:
        builder.Build()
        if not builder.IsDone():
            raise GeometryError(
                detail=_("Der Radius ist für diese Kanten zu groß."),
                values={"size_mm": round(size, 3), "edges": edges},
            )
        shape = builder.Shape()
    except GeometryError:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE raises its own exception types
        raise GeometryError(
            detail=_("Der Radius ist für diese Kanten zu groß."),
            values={"size_mm": round(size, 3), "edges": edges},
        ) from problem
    _log.info("%s of %.2f mm on %d edge(s)", kind, size, edges)
    return solid.replacing(shape)


def boolean(kind: Literal["union", "difference", "intersection"], parts: list[Solid]) -> Solid:
    """Präzise Boolesche Ops: keine Tessellation, also keine
    Tessellations-Artefakte (§30).

    Eine Rückfallkette gibt es hier nicht, und das ist keine Auslassung — die
    Kette aus §17.2 existiert, weil Netze sich uneinig sind, was innen ist.
    Zwei B-Rep-Volumen sind das nicht, und wo das hier scheitert, ist die
    Antwort ein echter Fehler statt eines gröberen Versuchs.
    """
    require()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse

    if len(parts) < 2:
        raise ValueError("a boolean operation needs at least two bodies")
    makers = {
        "union": BRepAlgoAPI_Fuse,
        "difference": BRepAlgoAPI_Cut,
        "intersection": BRepAlgoAPI_Common,
    }
    shape = parts[0].shape
    for other in parts[1:]:
        operation = makers[kind](shape, other.shape)
        operation.Build()
        if not operation.IsDone():
            # Nicht „fehlgeschlagen" (Regel 17), und nicht die geerbten
            # Vorschläge: Mesh-Reparatur und offene Kanten gibt es für einen
            # B-Rep-Körper nicht. Der häufigste Grund ist eine Berührung
            # ohne Überlappung — und die behebt eine Bewegung, keine
            # Reparatur.
            raise GeometryError(
                detail=_(
                    "Der exakte Kern findet für diese Körper kein Ergebnis — "
                    "meist berühren sie sich nur an einer Fläche oder Kante, "
                    "statt sich zu überlappen. Verschieben Sie einen der "
                    "beiden um die gewünschte Überlappung."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        shape = operation.Shape()
    return parts[0].replacing(shape)


def moved(solid: Solid, offset: Vec3) -> Solid:
    """Verschiebt einen Körper. Starre Bewegungen bleiben auf einem B-Rep exakt."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec

    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(offset[0], offset[1], offset[2]))
    return solid.replacing(BRepBuilderAPI_Transform(solid.shape, transform, True).Shape())
