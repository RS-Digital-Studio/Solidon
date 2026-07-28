"""Shared ground for every part (Bauplan §24.1).

Three things every part needs and none of them should invent for itself: a way
to join shapes, a way to name a provenance feature, and the rule that a
subtracted shape reaches a hair past the surface it cuts (§39).

The features are the reason parts exist at all. A bore that comes out of the
library is called ``bore_1`` from the start and does not have to be recognised
again afterwards (§21.1) — the fit, the digest and the agent all speak about it
by that name.
"""

from __future__ import annotations

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.types import Feature, FeatureId, PartResult, Vec3


def union(*meshes: MeshData) -> MeshData:
    """Join shapes. One body in, one body out."""
    bodies = [mesh for mesh in meshes if mesh is not None]
    if len(bodies) == 1:
        return bodies[0]
    return boolean("union", bodies, quality="fine").mesh


def subtract(base: MeshData, *cutters: MeshData) -> MeshData:
    return boolean("difference", [base, *cutters], quality="fine").mesh


def bore(
    identifier: FeatureId,
    diameter: float,
    centre: Vec3,
    *,
    depth: float = 0.0,
    axis: Vec3 = (0.0, 0.0, 1.0),
    through: bool = False,
) -> tuple[FeatureId, Feature]:
    """A named bore, as the part promises it (§24.1)."""
    return identifier, Feature(
        id=identifier,
        kind="hole",
        provenance="generated",
        params={
            "diameter": round(diameter, 4),
            "centre": centre,
            "axis": axis,
            "depth": round(depth, 4),
            "through": through,
        },
    )


def pin(
    identifier: FeatureId,
    diameter: float,
    centre: Vec3,
    *,
    length: float = 0.0,
    axis: Vec3 = (0.0, 0.0, 1.0),
) -> tuple[FeatureId, Feature]:
    """The counterpart of a bore — what a fit pairs it with (§14)."""
    return identifier, Feature(
        id=identifier,
        kind="pin",
        provenance="generated",
        params={
            "diameter": round(diameter, 4),
            "centre": centre,
            "axis": axis,
            "depth": round(length, 4),
        },
    )


def face(
    identifier: FeatureId,
    area: float,
    centre: Vec3,
    normal: Vec3 = (0.0, 0.0, 1.0),
) -> tuple[FeatureId, Feature]:
    return identifier, Feature(
        id=identifier,
        kind="face",
        provenance="generated",
        params={"area": round(area, 4), "centre": centre, "normal": normal},
    )


def thread(
    identifier: FeatureId,
    diameter: float,
    pitch: float,
    centre: Vec3,
    *,
    axis: Vec3 = (0.0, 0.0, 1.0),
    internal: bool = False,
) -> tuple[FeatureId, Feature]:
    return identifier, Feature(
        id=identifier,
        kind="thread",
        provenance="generated",
        params={
            "diameter": round(diameter, 4),
            "pitch": round(pitch, 4),
            "centre": centre,
            "axis": axis,
            "internal": internal,
        },
    )


def result(mesh: MeshData, *features: tuple[FeatureId, Feature]) -> PartResult:
    """A part's answer: the geometry and everything it is willing to be called."""
    return PartResult(mesh=mesh, features=dict(features))
