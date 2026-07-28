"""The B-Rep body and its way into a mesh (Bauplan §30, §9).

A :class:`Solid` satisfies the same ``Mesh`` protocol as everything else, so
the viewport, the report, the layer analysis and the export keep working on a
B-Rep object without knowing it is one. What it does *not* do is answer from the
tessellation where it can answer exactly: volume and area come from the kernel,
not from the triangles, and the difference on a filleted part is not academic.

The tessellation is made once and kept. It is a view of the body, never the
body — every operation works on the shape, and the triangles are recomputed
after it. The other direction, mesh back to B-Rep, does not exist here: the
edges are gone, and a "reconstruction" would invent them (§30).

OpenCASCADE is optional. Without it every entry point says so in one sentence
and the rest of the application is untouched (§36).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from app.core.errors import AppError
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import BoundingBox
from app.i18n import _

_log = get_logger(__name__)

#: How far the tessellation may deviate from the real surface, in mm. Fine
#: enough that a fillet looks round on screen, coarse enough that a STEP
#: assembly does not arrive as a million triangles (§31).
DEFLECTION = 0.05

#: Angular deviation in radians, for the same reason.
ANGULAR_DEFLECTION = 0.3


class BRepUnavailable(AppError):
    """The B-Rep kernel is not installed."""

    default_title = _("Der B-Rep-Kern ist auf diesem Rechner nicht installiert.")

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            detail=detail
            or _(
                "Fasen, Verrundungen und STEP brauchen OpenCASCADE. "
                "Alles andere in Formwerk funktioniert ohne."
            )
        )


def available() -> bool:
    """Is the kernel there? Asked before an action offers itself (§36)."""
    try:
        import OCP.BRepPrimAPI  # noqa: F401
    except Exception:  # a compiled extension fails in more ways than ImportError
        return False
    return True


def require() -> None:
    """Raise the one clear error, rather than an import trace from a binding."""
    if not available():
        raise BRepUnavailable()
    _quieten()


def _quieten() -> None:
    """Take OpenCASCADE's own printer off the console.

    The STEP writer reports its progress on standard output, which on the
    command line lands in the middle of whatever was being written and in the
    packaged application goes nowhere useful at all. Formwerk logs (§33.2); the
    kernel does not get its own channel.
    """
    global _quiet
    if _quiet:
        return
    try:
        from OCP.Message import Message, Message_PrinterOStream

        Message.DefaultMessenger_s().RemovePrinters(Message_PrinterOStream.get_type_descriptor_s())
    except Exception as problem:  # a binding without the printer API is fine
        _log.debug("could not silence the kernel messenger: %s", problem)
    _quiet = True


_quiet = False


@dataclass(frozen=True, slots=True)
class Solid:
    """One B-Rep body. Satisfies the ``Mesh`` protocol by tessellating itself."""

    shape: Any
    """``TopoDS_Shape``. Typed loosely on purpose — the binding is optional."""
    deflection: float = DEFLECTION
    _cache: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    # --- the exact answers ------------------------------------------------------

    @property
    def volume(self) -> float:
        """From the kernel, not from the triangles — that is the whole point."""
        return float(self._properties("volume").Mass())

    @property
    def area(self) -> float:
        return float(self._properties("surface").Mass())

    @property
    def face_count(self) -> int:
        return len(self.faces())

    @property
    def edge_count(self) -> int:
        return len(self.edges())

    def faces(self) -> list[Any]:
        """Every face, once. Named entities — this is what §30 buys."""
        return self._explore("face")

    def edges(self) -> list[Any]:
        return self._explore("edge")

    # --- the tessellated answers ------------------------------------------------

    @property
    def mesh(self) -> MeshData:
        """The triangles. Made once, and never fed back into the shape."""
        cached = self._cache.get("mesh")
        if cached is None:
            cached = tessellate(self.shape, self.deflection)
            self._cache["mesh"] = cached
        return cast(MeshData, cached)

    def to_mesh(self) -> MeshData:
        """The one-way door of §30. Explicit, because the way back is closed."""
        return self.mesh

    @property
    def vertex_count(self) -> int:
        return self.mesh.vertex_count

    @property
    def triangle_count(self) -> int:
        return self.mesh.triangle_count

    @property
    def bounds(self) -> BoundingBox:
        return self.mesh.bounds

    @property
    def is_watertight(self) -> bool:
        return self.mesh.is_watertight

    @property
    def component_count(self) -> int:
        return self.mesh.component_count

    @property
    def slot_indices(self) -> tuple[int, ...]:
        return tuple(self.mesh.slot_indices)

    @property
    def raw(self) -> Any:
        """The triangles, for the surfaces that draw them."""
        return self.mesh.raw

    def to_stl(self) -> bytes:
        return self.mesh.to_stl()

    def replacing(self, shape: Any) -> Solid:
        """A new body around a changed shape, at the same tessellation quality."""
        return Solid(shape=shape, deflection=self.deflection)

    # --- inside ------------------------------------------------------------------

    def _properties(self, kind: str) -> Any:
        cached = self._cache.get(kind)
        if cached is not None:
            return cached
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        props = GProp_GProps()
        if kind == "volume":
            BRepGProp.VolumeProperties_s(self.shape, props)
        else:
            BRepGProp.SurfaceProperties_s(self.shape, props)
        self._cache[kind] = props
        return props

    def _explore(self, kind: str) -> list[Any]:
        """Topology entities, deduplicated — an explorer visits edges per face."""
        cached = self._cache.get(f"list:{kind}")
        if cached is not None:
            return list(cached)
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
        from OCP.TopExp import TopExp
        from OCP.TopoDS import TopoDS
        from OCP.TopTools import TopTools_IndexedMapOfShape

        found = TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(self.shape, TopAbs_FACE if kind == "face" else TopAbs_EDGE, found)
        # The map hands back plain shapes; everything downstream wants the real
        # type, and a wrong cast here fails much further away.
        as_typed = TopoDS.Face_s if kind == "face" else TopoDS.Edge_s
        entities = [as_typed(found.FindKey(index)) for index in range(1, found.Extent() + 1)]
        self._cache[f"list:{kind}"] = entities
        return list(entities)


def tessellate(shape: Any, deflection: float = DEFLECTION) -> MeshData:
    """Triangles for a shape, fine enough that a fillet reads as round."""
    import numpy as np
    import trimesh
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    BRepMesh_IncrementalMesh(shape, deflection, False, ANGULAR_DEFLECTION, True)

    points: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        explorer.Next()
        if triangulation is None:
            continue

        transform = location.Transformation()
        offset = len(points)
        for index in range(1, triangulation.NbNodes() + 1):
            node = triangulation.Node(index).Transformed(transform)
            points.append((node.X(), node.Y(), node.Z()))

        reversed_face = face.Orientation() == TopAbs_REVERSED
        for index in range(1, triangulation.NbTriangles() + 1):
            first, second, third = triangulation.Triangle(index).Get()
            # A reversed face means the winding has to be turned around, or the
            # body comes out inside-out and every volume is negative.
            corners = (third, second, first) if reversed_face else (first, second, third)
            faces.append(
                (corners[0] - 1 + offset, corners[1] - 1 + offset, corners[2] - 1 + offset)
            )

    if not faces:
        return MeshData.of(trimesh.Trimesh())
    body = trimesh.Trimesh(
        vertices=np.asarray(points, dtype=float),
        faces=np.asarray(faces, dtype=np.int64),
        process=True,
    )
    _log.info("tessellated a B-Rep body into %d triangles", len(body.faces))
    return MeshData.of(body)
