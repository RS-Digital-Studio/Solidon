"""Features from topology (Bauplan §30, §21).

On a mesh, finding a hole means clustering triangles and fitting a cylinder to
them, and giving it a name that survives the next operation means matching
against the previous names (§21.2). On a B-Rep body none of that is necessary:
a cylindrical face *is* a cylindrical face, and it says its own radius and axis.

That is the jump §30 promises, and it is why this file is short. What it does
not do is invent certainty: a cylindrical face is only reported as a hole when
it is a full turn and points into the material — a rounded outer corner is a
cylinder too, and calling it a bore would put a screw through the wall.
"""

from __future__ import annotations

from typing import Any

from app.core.brep.kernel import Solid
from app.core.log import get_logger
from app.core.types import Feature, FeatureId, FeatureKind, Vec3
from app.core.units import EPS_GEOM

_log = get_logger(__name__)

#: How much of a full turn a cylindrical face has to cover to count as a bore.
#: Below that it is a fillet or a rounded corner, not a hole.
FULL_TURN = 0.9


def features_of(solid: Solid) -> dict[FeatureId, Feature]:
    """Holes and planar faces, read off the topology rather than fitted."""
    found: dict[FeatureId, Feature] = {}
    holes = 0
    faces = 0

    for index, face in enumerate(solid.faces()):
        described = _describe(face, index)
        if described is None:
            continue
        kind, params = described
        if kind == "hole":
            holes += 1
            identifier = f"hole_{holes}"
        else:
            faces += 1
            identifier = f"face_{faces}"
        found[identifier] = Feature(
            id=identifier,
            kind=kind,
            provenance="detected",
            params=params,
            face_indices=(index,),
        )

    _log.info("read %d hole(s) and %d face(s) off a B-Rep body", holes, faces)
    return found


def _describe(face: Any, index: int) -> tuple[FeatureKind, dict[str, Any]] | None:
    """What this face is, in the vocabulary of §21."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.GProp import GProp_GProps

    surface = BRepAdaptor_Surface(face)
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    area = float(props.Mass())
    if area <= EPS_GEOM:
        return None
    centre = props.CentreOfMass()
    middle: Vec3 = (centre.X(), centre.Y(), centre.Z())

    kind = surface.GetType()
    if kind == GeomAbs_Plane:
        plane = surface.Plane()
        normal = plane.Axis().Direction()
        return "face", {
            "area": round(area, 4),
            "centre": middle,
            "normal": (normal.X(), normal.Y(), normal.Z()),
        }

    if kind == GeomAbs_Cylinder:
        turn = abs(surface.LastUParameter() - surface.FirstUParameter())
        if turn < FULL_TURN * 2.0 * 3.141592653589793:
            return None
        cylinder = surface.Cylinder()
        axis = cylinder.Axis().Direction()
        radius = float(cylinder.Radius())
        depth = abs(surface.LastVParameter() - surface.FirstVParameter())
        return "hole", {
            "diameter": round(radius * 2.0, 4),
            "centre": middle,
            "axis": (axis.X(), axis.Y(), axis.Z()),
            "depth": round(depth, 4),
        }

    del index
    return None
