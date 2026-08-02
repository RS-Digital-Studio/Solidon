"""Die Mesh-Hülle um den Geometriekern (Bauplan §9, §7).

Der Rest des Kerns spricht mit dem ``Mesh``-Protokoll, nie direkt mit
``trimesh`` oder ``manifold3d``. Das hält den Kern austauschbar und macht den
B-Rep-Kern (§30) zu einer Ergänzung statt einem Umbau.

Eine ``MeshData`` gilt als unveränderlich: jede Operation gibt eine neue
zurück — das ist non-destruktives Bearbeiten, eine Ebene tiefer.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # das 3MF-Modul braucht MeshData, der Import geht also nur in eine Richtung
    from app.core.export.threemf import Part

import numpy as np
import trimesh

from app.core.errors import PROGRAMMING_ERRORS, GeometryError, ValidationError
from app.core.types import BoundingBox, Mesh
from app.i18n import _

#: Endungen, die die Eingangsstufe lesen kann (§25, „Import").
READABLE_SUFFIXES: tuple[str, ...] = (".stl", ".obj", ".ply", ".off", ".glb", ".gltf", ".3mf")


@dataclass(frozen=True, slots=True)
class MeshData:
    """Ein Körper: Eckpunkte, Dreiecke und ein Materialslot je Dreieck (§20)."""

    raw: trimesh.Trimesh
    slots: tuple[int, ...] = field(default_factory=tuple)

    # --- Protokoll --------------------------------------------------------------

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

    # --- Aufbau -----------------------------------------------------------------

    @classmethod
    def of(cls, mesh: trimesh.Trimesh, slots: tuple[int, ...] = ()) -> MeshData:
        return cls(raw=mesh, slots=slots)

    def replacing(self, mesh: trimesh.Trimesh) -> MeshData:
        """Eine neue Hülle um einen geänderten Körper; die Slots bleiben, wo
        sie passen."""
        slots = self.slots if len(self.slots) == len(mesh.faces) else ()
        return MeshData(raw=mesh, slots=slots)

    # --- Serialisierung ---------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Verlustfreie Form für den Platten-Cache — STL würde die Slots
        verlieren."""
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
        """Binäres STL, für den Export und die Übergabe an einen Slicer (§29)."""
        result: bytes = trimesh.exchange.stl.export_stl(self.raw)
        return result


def as_mesh_data(mesh: Mesh) -> MeshData:
    """Das konkrete Netz hinter dem Protokoll.

    Operationen deklarieren ``Mesh``, denn das ist der Vertrag (§9) — aber die
    Dreiecksarbeit braucht den Kern. Hier wird ein Körper der falschen Sorte
    mit klarer Meldung abgewiesen (§30).
    """
    if isinstance(mesh, MeshData):
        return mesh
    # §30: der Weg von B-Rep zu Mesh steht jederzeit offen — eine Mesh-Op auf
    # einem exakten Körper funktioniert also: auf seiner Tessellation, und das
    # Objekt kommt danach als Mesh markiert heraus, denn das ist es jetzt.
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
    """Zusammenhängende Komponenten als Dreiecksindizes.

    Mit Absicht über die Flächen-Nachbarschaft statt ``Trimesh.split``: das
    Splitten baut Teilnetze und versucht, sie zu reparieren — das ist
    langsamer und zugleich eine Entscheidung, die die Eingangsstufe noch gar
    nicht getroffen hat (§17.1 Schritt 5).
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
    """Parst eine Datei, die schon im Speicher liegt. Noch keine
    Aufbereitung — die ist §17.1."""
    normalised = suffix.lower()
    if normalised not in READABLE_SUFFIXES:
        raise ValidationError(
            field="file",
            detail=_("Dieses Dateiformat kann nicht gelesen werden."),
            constraint="unsupported_format",
            values={"suffix": suffix, "known": list(READABLE_SUFFIXES)},
        )
    if normalised == ".3mf":
        # Nicht über trimesh: es löst eine Komponente, die in eine externe
        # Objektdatei zeigt, zur ganzen Datei auf statt zu dem Objekt, das sie
        # benennt, und gibt jeden Körper einmal je Komponente zurück. Hier
        # statt oben importiert, weil das 3MF-Modul MeshData braucht.
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
    except Exception as problem:  # trimesh wirft eine breite Palette an Parserfehlern
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


def concatenated(parts: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Verschweißt mehrere Netze zu einem.

    trimesh annotiert ``concatenate`` mit dem gemeinsamen Obertyp ``Geometry``,
    weil auch Punktwolken hineinpassen; aus lauter ``Trimesh`` entsteht aber
    immer ein ``Trimesh``. Die eine Engführung lebt hier, nicht an jeder
    Aufrufstelle.
    """
    merged = trimesh.util.concatenate(parts)
    assert isinstance(merged, trimesh.Trimesh)
    return merged


def _joined(parts: list[Part]) -> MeshData:
    """Die Körper einer 3MF als der eine Körper, den diese Funktion verspricht.

    Wer sie getrennt will, fragt :func:`app.core.export.threemf.read_objects`;
    hier werden sie verschweißt, denn das ist, was ein einzelner Rückgabewert
    sein kann. Die Slots reisen nur aus einer Datei mit einem Körper mit:
    jedes Teil nummeriert seine Slots ab null, und diese Nummerierungen ohne
    gemeinsame Palette zu mischen setzte das falsche Filament auf die Hälfte
    der Dreiecke (§20).
    """
    if len(parts) == 1:
        return parts[0].mesh
    return MeshData.of(concatenated([part.mesh.raw for part in parts]))


class MeshCodec:
    """Codec für den Platten-Cache (§38). Registriert, sobald der Kern da ist."""

    suffix = ".npz"

    def dumps(self, mesh: Mesh) -> bytes:
        if not isinstance(mesh, MeshData):
            raise TypeError("the disk cache can only store MeshData")
        return mesh.to_bytes()

    def loads(self, data: bytes) -> Mesh:
        return MeshData.from_bytes(data)
