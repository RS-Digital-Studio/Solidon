"""Shaping a B-Rep body (Bauplan §30, §25).

The two operations that are the reason for a second kernel: a fillet and a
chamfer on real edges. On a mesh both are approximations of an approximation —
the edge is already a chain of segments, and rounding it rounds the segments.
Here the edge is a curve and the result is exact.

Which edges get treated is a selection, and the selection is by geometry, not
by index: an index into the topology of a body changes the moment anything else
about it changes, and a fillet that moves when an unrelated hole is drilled is
worse than no fillet (§21.2, the same reason feature identifiers are matched).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.brep.kernel import Solid, require
from app.core.errors import GeometryError
from app.core.log import get_logger
from app.core.types import Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

EdgeChoice = Literal["all", "vertical", "horizontal", "top", "bottom"]

#: Which edges a choice means. "Vertical" is what somebody means by "round the
#: corners of this box": the four uprights, not the plate edges.
EDGE_CHOICES: tuple[EdgeChoice, ...] = ("all", "vertical", "horizontal", "top", "bottom")


@dataclass(frozen=True, slots=True)
class EdgeInfo:
    """One edge, described by what it is rather than by where it is stored."""

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
    """A box on the bed, centred in X and Y — the same anchor as the mesh side."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    corner = gp_Pnt(-width / 2.0, -depth / 2.0, 0.0)
    return Solid(BRepPrimAPI_MakeBox(corner, width, depth, height).Shape())


def cylinder(diameter: float, height: float) -> Solid:
    """A cylinder standing on Z = 0."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    return Solid(BRepPrimAPI_MakeCylinder(diameter / 2.0, height).Shape())


def edges_of(solid: Solid) -> list[EdgeInfo]:
    """Every edge with the numbers a selection can be made from."""
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
    """The edges a named selection means."""
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
    """Round the chosen edges. Exact, because the edge is a curve (§30)."""
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
    """Run the builder and turn its failure into a sentence somebody can act on."""
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
    except Exception as problem:  # OpenCASCADE raises its own exception types
        raise GeometryError(
            detail=_("Der Radius ist für diese Kanten zu groß."),
            values={"size_mm": round(size, 3), "edges": edges},
        ) from problem
    _log.info("%s of %.2f mm on %d edge(s)", kind, size, edges)
    return solid.replacing(shape)


def boolean(kind: Literal["union", "difference", "intersection"], parts: list[Solid]) -> Solid:
    """Precise booleans: no tessellation, so no tessellation artefacts (§30).

    There is no fallback chain here, and that is not an omission — the chain of
    §17.2 exists because meshes disagree about what is inside. Two B-Rep solids
    do not, and where this fails the answer is a real error rather than a
    coarser attempt.
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
            raise GeometryError(detail=_("Die Boolesche Operation ist fehlgeschlagen."))
        shape = operation.Shape()
    return parts[0].replacing(shape)


def moved(solid: Solid, offset: Vec3) -> Solid:
    """Shift a body. Rigid motions stay exact on a B-Rep."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec

    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(offset[0], offset[1], offset[2]))
    return solid.replacing(BRepBuilderAPI_Transform(solid.shape, transform, True).Shape())
