"""The mesh hull around the geometry kernel (Bauplan §9, §7).

The rest of the core talks to the ``Mesh`` protocol, never to ``trimesh`` or
``manifold3d`` directly. That is what keeps the kernel exchangeable and makes
the B-Rep kernel (§30) an addition rather than a rewrite.

A ``MeshData`` is treated as immutable: every operation returns a new one, which
is what non-destructive editing means one layer down.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # the 3MF module needs MeshData, so the import can only go one way
    from app.core.export.threemf import Part

import numpy as np
import trimesh

from app.core.errors import PROGRAMMING_ERRORS, GeometryError, ValidationError
from app.core.types import BoundingBox, Mesh
from app.i18n import _

#: Extensions the input stage can read (§25, "Import").
READABLE_SUFFIXES: tuple[str, ...] = (".stl", ".obj", ".ply", ".off", ".glb", ".gltf", ".3mf")


@dataclass(frozen=True, slots=True)
class MeshData:
    """One body: vertices, triangles and a material slot per triangle (§20)."""

    raw: trimesh.Trimesh
    slots: tuple[int, ...] = field(default_factory=tuple)

    # --- protocol ---------------------------------------------------------------

    @property
    def vertex_count(self) -> int:
        return len(self.raw.vertices)

    @property
    def triangle_count(self) -> int:
        return len(self.raw.faces)

    @property
    def bounds(self) -> BoundingBox:
        if self.triangle_count == 0:
            return BoundingBox((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        low, high = self.raw.bounds
        return BoundingBox(
            (float(low[0]), float(low[1]), float(low[2])),
            (float(high[0]), float(high[1]), float(high[2])),
        )

    @property
    def volume(self) -> float:
        return float(self.raw.volume)

    @property
    def area(self) -> float:
        return float(self.raw.area)

    @property
    def is_watertight(self) -> bool:
        return bool(self.raw.is_watertight)

    @property
    def component_count(self) -> int:
        return len(face_components(self.raw))

    @property
    def slot_indices(self) -> tuple[int, ...]:
        return self.slots

    # --- construction -----------------------------------------------------------

    @classmethod
    def of(cls, mesh: trimesh.Trimesh, slots: tuple[int, ...] = ()) -> MeshData:
        return cls(raw=mesh, slots=slots)

    def replacing(self, mesh: trimesh.Trimesh) -> MeshData:
        """A new hull around a changed body, keeping the slots where they fit."""
        slots = self.slots if len(self.slots) == len(mesh.faces) else ()
        return MeshData(raw=mesh, slots=slots)

    # --- serialisation ----------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Lossless form for the disk cache — STL would drop the slots."""
        buffer = io.BytesIO()
        np.savez_compressed(
            buffer,
            vertices=np.asarray(self.raw.vertices, dtype=np.float64),
            faces=np.asarray(self.raw.faces, dtype=np.int64),
            slots=np.asarray(self.slots, dtype=np.int32),
        )
        return buffer.getvalue()

    @classmethod
    def from_bytes(cls, payload: bytes) -> MeshData:
        with np.load(io.BytesIO(payload)) as data:
            mesh = trimesh.Trimesh(vertices=data["vertices"], faces=data["faces"], process=False)
            slots = tuple(int(entry) for entry in data["slots"])
        return cls(raw=mesh, slots=slots)

    def to_stl(self) -> bytes:
        """Binary STL, for export and for handing over to a slicer (§29)."""
        result: bytes = trimesh.exchange.stl.export_stl(self.raw)
        return result


def as_mesh_data(mesh: Mesh) -> MeshData:
    """The concrete mesh behind the protocol.

    Operations declare ``Mesh`` because that is the contract (§9), but the
    triangle work needs the kernel. Once the B-Rep core arrives (§30) this is
    where a body of the wrong kind is turned away with a clear message.
    """
    if isinstance(mesh, MeshData):
        return mesh
    # §30: the way from B-Rep to mesh is open at any time, so a mesh operation
    # on an exact body works — on its tessellation, and the object comes out
    # marked as a mesh afterwards, because that is what it now is.
    converted = getattr(mesh, "to_mesh", None)
    if callable(converted):
        result = converted()
        if isinstance(result, MeshData):
            return result
    raise GeometryError(
        _("Diese Operation arbeitet nur auf Netzen."),
        detail=_("Das Objekt liegt in einer anderen Darstellung vor."),
    )


def face_components(mesh: trimesh.Trimesh) -> list[np.ndarray]:
    """Connected components as triangle indices.

    Done over the face adjacency rather than ``Trimesh.split`` on purpose:
    splitting builds submeshes and tries to repair them, which is both slower and
    a decision the input stage has not made yet (§17.1 step 5).
    """
    count = len(mesh.faces)
    if count == 0:
        return []
    return list(
        trimesh.graph.connected_components(
            mesh.face_adjacency, nodes=np.arange(count), engine="scipy"
        )
    )


def read_mesh(payload: bytes, suffix: str) -> MeshData:
    """Parse a file that is already in memory. No processing yet — that is §17.1."""
    normalised = suffix.lower()
    if normalised not in READABLE_SUFFIXES:
        raise ValidationError(
            field="file",
            detail=_("Dieses Dateiformat kann nicht gelesen werden."),
            constraint="unsupported_format",
            values={"suffix": suffix, "known": list(READABLE_SUFFIXES)},
        )
    if normalised == ".3mf":
        # Not through trimesh: it resolves a component that points into an
        # external object file to the whole file instead of to the object it
        # names, and hands back every body once per component. Imported here
        # rather than at the top because the 3MF module needs MeshData.
        from app.core.export import threemf

        parts = threemf.read_objects(payload)
        if parts:
            return _joined(parts)

    try:
        loaded: Any = trimesh.load(
            io.BytesIO(payload), file_type=normalised.lstrip("."), process=False, force="mesh"
        )
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # trimesh raises a wide range of parser errors
        raise ValidationError(
            field="file",
            detail=_("Die Datei ließ sich nicht lesen; sie ist vermutlich beschädigt."),
            constraint="unreadable",
            values={"suffix": suffix},
        ) from problem

    if isinstance(loaded, trimesh.Scene):
        loaded = loaded.to_mesh() if loaded.geometry else trimesh.Trimesh()
    if not isinstance(loaded, trimesh.Trimesh) or not len(loaded.faces):
        raise ValidationError(
            field="file",
            detail=_("Die Datei enthält keine Dreiecksgeometrie."),
            constraint="no_geometry",
            values={"suffix": suffix},
        )
    return MeshData.of(loaded)


def _joined(parts: list[Part]) -> MeshData:
    """The bodies of a 3MF as the one body this function promises.

    Whoever wants them apart asks :func:`app.core.export.threemf.read_objects`;
    here they are welded, because that is what a single return value can be. The
    slots come along only from a file with one body: every part numbers its own
    slots from zero, and merging those numberings without a shared palette would
    put the wrong filament on half the triangles (§20).
    """
    if len(parts) == 1:
        return parts[0].mesh
    return MeshData.of(trimesh.util.concatenate([part.mesh.raw for part in parts]))


class MeshCodec:
    """Codec for the disk cache (§38). Registered once the kernel is available."""

    suffix = ".npz"

    def dumps(self, mesh: Mesh) -> bytes:
        if not isinstance(mesh, MeshData):
            raise TypeError("the disk cache can only store MeshData")
        return mesh.to_bytes()

    def loads(self, data: bytes) -> Mesh:
        return MeshData.from_bytes(data)
