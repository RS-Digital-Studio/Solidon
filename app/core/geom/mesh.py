"""Die Mesh-Hülle um den Geometriekern (Bauplan §9, §7).

Der Rest des Kerns spricht mit dem ``Mesh``-Protokoll, nie direkt mit
``trimesh`` oder ``manifold3d``. Das hält den Kern austauschbar und macht den
B-Rep-Kern (§30) zu einer Ergänzung statt einem Umbau.

Eine ``MeshData`` gilt als unveränderlich: jede Operation gibt eine neue
zurück — das ist non-destruktives Bearbeiten, eine Ebene tiefer.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # das 3MF-Modul braucht MeshData, der Import geht also nur in eine Richtung
    from app.core.export.threemf import Part

import numpy as np
import trimesh

from app.core.errors import CANCEL, CHOOSE, PROGRAMMING_ERRORS, GeometryError, ValidationError
from app.core.log import get_logger
from app.core.types import BoundingBox, Mesh
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

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
        # **Ein leeres Netz hat Volumen null und wirft nicht.** ``bounds``
        # darüber fängt den Fall seit je ab, ``volume`` und ``area`` taten es
        # nicht — dieselbe Klasse, zwei Haltungen. trimesh rechnet dort nicht
        # null, sondern wirft ``ValueError: Triangles must be (n, 3, 3)!``,
        # und das kam beim Vergleich zweier gleicher Zustände heraus, sobald
        # die Boolesche Kette ein leeres Ergebnis durchlassen durfte.
        if self.triangle_count == 0:
            return 0.0
        return float(self.raw.volume)

    @property
    def area(self) -> float:
        if self.triangle_count == 0:
            return 0.0
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
        # Auch hier nicht die Vorgabe: Netzreparatur macht aus einem exakten
        # Körper kein Netz, und Stellen nennt dieser Fehler keine. Was hilft,
        # ist eine andere Auswahl — der Körper, an dem die Operation arbeiten
        # kann.
        suggestions=(CHOOSE, CANCEL),
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


def on_surface(
    body: trimesh.Trimesh, points: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Für jeden Punkt der nächste Ort auf der Oberfläche, sein Abstand und
    sein Dreieck.

    Warum das hier steht und nicht dreimal beim Aufrufer: Der Weg dorthin
    führt durch ``rtree``, und ``rtree`` greift auf dieser Maschine daneben —
    eine Zugriffsverletzung, die als ``OSError`` zurückkommt und unter der der
    Index liegt, den ``trimesh`` am Netz zwischenspeichert.

    Also wird sie einmal wiederholt, und zwar an einer **Kopie**: die bringt
    einen frischen Zwischenspeicher und damit einen frisch gebauten Index
    mit. Das ist kein Verschlucken — scheitert auch der zweite Versuch, fliegt
    der Fehler.

    **Der Wiederholversuch heilt den Aufruf, nicht den Speicher.** Wo die
    Bibliothek in fremde Seiten greift, fällt kurz darauf etwas anderes um: im
    Audit vom 08.08.2026 ein gewöhnliches Python-Set in
    ``perceive.features``, unmittelbar gefolgt von einem Segmentation Fault.
    Die einzige verlässliche Gegenmaßnahme ist deshalb, *weniger* zu fragen.

    Genau das ist geschehen. Die Slot-Übertragung stellte je Auswertung
    113168 Anfragen an den Index, weil sie für jedes Dreieck des Ergebnisses
    den Abstand zu jeder Quelle suchte; mit dem Vorfilter in
    ``geom.attributes`` sind es 1180. Gemessen danach: sechzig Auswertungen
    hintereinander, kein einziger Fehlgriff — vorher wären bei dieser Zahl
    etwa drei zu erwarten gewesen. Das ist kein Beweis, dass es nie wieder
    passiert; es ist zwei Größenordnungen weniger Gelegenheit.
    """
    try:
        return _asked(body, points)
    except OSError as stumble:
        _log.warning("proximity query stumbled over its index, asking again: %s", stumble)
        return _asked(body.copy(), points)


def _asked(body: trimesh.Trimesh, points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    closest, distance, triangle = trimesh.proximity.ProximityQuery(body).on_surface(points)
    return (
        np.asarray(closest, dtype=float),
        np.asarray(distance, dtype=float),
        np.asarray(triangle, dtype=np.int64),
    )


def distance_to_triangles(triangles: np.ndarray, point: np.ndarray) -> float:
    """Der kürzeste Abstand von einem Punkt zu einer gegebenen Menge Dreiecke.

    Die Frage hinter „welches Merkmal liegt unter diesem Klick?" (§18.5): Die
    Dreiecke sind die eines erkannten Merkmals, der Punkt ist die Stelle, auf
    die gezeigt wurde. Gerechnet wird gegen den nächsten **Ort auf dem
    Dreieck** und nicht gegen den nächsten Eckpunkt — der Unterschied ist kein
    Feinschliff: Die Deckfläche der Platte aus dem Korpus besteht aus zwei
    großen Dreiecken, und ein Klick in ihre Mitte liegt vierzig Millimeter von
    jedem ihrer Eckpunkte entfernt.

    **Ohne den Näherungsindex**, anders als :func:`on_surface`: Hier steht die
    Dreiecksmenge schon fest, es ist also nichts zu suchen, sondern nur zu
    rechnen — reine Arithmetik über ein Array. Damit bleibt der Weg an
    ``rtree`` vorbei, und was dort oben über Zugriffsverletzungen steht, gilt
    hier nicht.

    Eine leere Menge hat keinen Abstand und bekommt unendlich — der Aufrufer
    vergleicht gegen eine Reichweite, und „unendlich" fällt dort heraus, ohne
    dass er einen Sonderfall braucht.
    """
    if not len(triangles):
        return float("inf")
    query = np.repeat(np.asarray(point, dtype=float).reshape(1, 3), len(triangles), axis=0)
    nearest = trimesh.triangles.closest_point(np.asarray(triangles, dtype=float), query)
    return float(np.linalg.norm(np.asarray(nearest, dtype=float) - query, axis=1).min())


#: Wie viele Eckpunkte höchstens in die konvexe Hülle eingehen
#: (:func:`hull_planes`). Dieselbe Zahl und derselbe Grund wie beim
#: Schattenumriss der Ansicht: Bei einer feinen Kugel liegt **jeder** Punkt auf
#: der Hülle, und die exakte Rechnung kostet dann mehr als sie wert ist.
#: Gemessen an ``dense_1m.stl`` (655 362 Eckpunkte): **5084 ms** exakt gegen
#: **20 ms** über die Stichprobe. An der Korpusplatte liefern beide dasselbe —
#: zwölf Flächen, Volumen 32 000 mm³.
HULL_SAMPLE_LIMIT = 4096


def hull_planes(mesh: Mesh) -> np.ndarray | None:
    """Die konvexe Hülle eines Netzes als Halbräume, ``n·x + d <= 0`` innen.

    Nicht als Netz, sondern als Ebenengleichungen: Die Frage dahinter ist „läuft
    dieser Sichtstrahl **durch** den Körper hindurch?" (:func:`ray_span_in_hull`),
    und die beantwortet ein Halbraumschnitt in einer Handvoll Rechenschritten,
    während ein Strahl gegen ein Hüllnetz wieder jedes Dreieck anfassen müsste.

    **Die Stichprobe ist der Kostendeckel**, und sie unterschätzt die Hülle
    leicht: Jeder ``n``-te Eckpunkt, dazu die äußersten in allen sechs
    Achsenrichtungen, damit ein gescannter Halter seine Ecken behält. Für die
    Frage, ob ein Klick durch eine Öffnung geht, ist das genau genug — die
    Öffnung ist millimeterweit, die Abweichung liegt im Bereich der Punktdichte.

    ``None`` heißt „keine räumliche Hülle": ein ebener oder entarteter Körper —
    oder einer ohne Eckpunkte, denn das ``Mesh``-Protokoll (§9) sagt nichts über
    ein ``raw`` zu; ein B-Rep-Körper hat keines. Der Aufrufer hat dann keinen
    Innenraum zu prüfen und braucht dafür keinen Sonderfall.
    """
    from scipy.spatial import ConvexHull, QhullError

    raw = getattr(mesh, "raw", None)
    if raw is None:
        return None
    points = np.asarray(raw.vertices, dtype=float)
    if len(points) < 4:
        return None
    if len(points) > HULL_SAMPLE_LIMIT:
        step = len(points) // HULL_SAMPLE_LIMIT + 1
        extremes = np.concatenate(
            [points[points[:, axis].argmin()][None] for axis in range(3)]
            + [points[points[:, axis].argmax()][None] for axis in range(3)]
        )
        points = np.concatenate([points[::step], extremes])
    try:
        return np.asarray(ConvexHull(points).equations, dtype=float)
    except QhullError as problem:
        # Flach, entartet oder alle Punkte auf einer Linie — kein Innenraum.
        _log.info("convex hull unavailable: %s", problem)
        return None


def ray_span_in_hull(
    planes: np.ndarray, origin: np.ndarray, direction: np.ndarray
) -> tuple[float, float] | None:
    """Von wo bis wo ein Strahl innerhalb dieser Halbräume läuft.

    Der Schnitt eines Strahls mit einem konvexen Körper, gerechnet wie das
    Kappen an Schichten: Jede Ebene schiebt entweder den Eintritt nach hinten
    oder den Austritt nach vorn, und bleibt am Ende ein Stück übrig, geht der
    Strahl hindurch. Zurück kommen die beiden Strahlparameter in Millimetern,
    gemessen von ``origin`` entlang ``direction`` (das normiert erwartet wird),
    oder nichts.

    Der Eintritt kann ``-inf`` sein — dann liegt der Ursprung selbst innen. Wer
    nur nach vorn sehen will, klemmt auf null; hier bleibt es stehen, weil die
    Aussage „von hier bis dort" nichts über die Blickrichtung des Aufrufers
    voraussetzen soll.
    """
    if planes is None or not len(planes):
        return None
    normals = np.asarray(planes, dtype=float)[:, :3]
    offsets = np.asarray(planes, dtype=float)[:, 3]
    along = normals @ np.asarray(direction, dtype=float)
    gap = normals @ np.asarray(origin, dtype=float) + offsets

    # Parallel zu einer Ebene und außerhalb von ihr: der Strahl kommt nie hinein.
    parallel = np.abs(along) <= EPS_GEOM
    if bool(np.any(parallel & (gap > EPS_GEOM))):
        return None

    crossing = ~parallel
    if not bool(np.any(crossing)):
        return None
    steps = -gap[crossing] / along[crossing]
    leaving = along[crossing] > 0.0
    enter = float(steps[~leaving].max()) if bool(np.any(~leaving)) else -math.inf
    leave = float(steps[leaving].min()) if bool(np.any(leaving)) else math.inf
    return (enter, leave) if enter < leave else None


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
        # ``load_mesh`` statt ``load(force="mesh")``: trimesh 5 führt ``load``
        # nur noch als Rückwärtskompatibilität und nennt es im Docstring
        # veraltet. Der Nachfolger sagt schon im Rückgabetyp, dass ein
        # ``Trimesh`` herauskommt — mehrere Körper in einer Datei verschweißt
        # er wie zuvor ``force="mesh"``, gemessen an einer GLB mit zwei
        # Quadern: beide Wege 24 Dreiecke.
        loaded = trimesh.load_mesh(
            io.BytesIO(payload), file_type=normalised.lstrip("."), process=False
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

    # Eine Datei, an der der Parser scheitert, ohne zu werfen, kommt als leerer
    # Körper heraus — das ist der Fall, den die Zeile abfängt.
    if not len(loaded.faces):
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
