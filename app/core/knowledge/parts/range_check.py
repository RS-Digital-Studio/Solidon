"""Der Bereichstest in der Anwendung (§24.3, §24.5 — Konzept E3).

§24.3 sagt: „Ein Baustein ohne diesen Test gilt als nicht vorhanden", und
§24.5 verlangt für eigene Bausteine denselben Test, mit Warnhinweis im
Katalog, wenn er nicht bestanden ist. Für die mitgelieferten Bausteine läuft
er in der Suite (``tests/test_parts.py``); ein Kunde hat keine Suite — sein
Rezept wird deshalb **beim Anlegen** geprüft, mit Fortschritt und Abbruch,
und das Ergebnis bleibt am Baustein.

Die Ecken sind dieselben wie im Test, und das ist der Punkt: eine Regel, ein
Ort. Das kartesische Produkt ist Absicht — erst die Kombination zweier Grenzen
ist oft die Stelle, an der eine Geometrie zusammenfällt.
"""

from __future__ import annotations

import gc
import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final, SupportsInt, cast

from app.core.errors import ValidationError
from app.core.knowledge.parts.ops import PLAY_FIELD
from app.core.knowledge.parts.registry import FeatureRequirement, PartSpec, WallRequirement
from app.core.types import BaseParams, CancelToken, PartResult, Profile, ProgressFn
from app.core.units import EPS_DISPLAY, EPS_GEOM
from app.i18n import _


def corners(params: type[BaseParams]) -> list[dict[str, Any]]:
    """Der Parameterbereich als die Werte, die ein Baustein überstehen muss.

    Der kleinste und der größte Wert jeder Zahl, jede Wahl jedes Enums und
    beide Zustände jedes Schalters — als vollständiges kartesisches Produkt.
    Die Vorgabe ist keine Grenze; sie wird im Reproduzierbarkeitstest gefahren.

    Die vorherige zyklische Fassung prüfte jeden Einzelwert, aber nicht sein
    Zusammenspiel: 124 Zeilen sahen nach Abdeckung aus, obwohl die Bibliothek
    2.114 Grenzkombinationen hat. Gemessen am 31.08.2026 brauchen ihre reinen
    Builds 73,2 Sekunden. Das ist ein sichtbarer, abbrechbarer Arbeitslauf und
    kein Grund, die zugesagte Menge still zu verkürzen.
    """
    lists: list[tuple[str, list[Any]]] = []
    for entry in params.spec():
        values: list[Any] = []
        if entry.kind == "enum":
            values = list(entry.choices)
        elif entry.kind == "bool":
            values = [True, False]
        elif entry.kind in ("float", "int"):
            values = [entry.minimum, entry.maximum]
        values = list(dict.fromkeys(value for value in values if value is not None))
        if values:
            lists.append((entry.name, values))
    if not lists:
        return [{}]
    return [
        dict(zip((name for name, _values in lists), combination, strict=True))
        for combination in itertools.product(*(values for _name, values in lists))
    ]


DEFAULT_WALL_REQUIREMENT: Final = WallRequirement()


def _is_cancelled(token: CancelToken) -> bool:
    """Fragt erneut; der Zustand darf sich während einer Phase ändern."""
    return token.is_cancelled


@dataclass(frozen=True, slots=True)
class RangeFailure:
    """Eine Ecke, die nicht hielt — mit den Werten, bei denen es geschah."""

    values: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class RangeExclusion:
    """Eine Ecke, die der Baustein selbst als nicht baubar erklärt hat."""

    values: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class RangeReport:
    """Was der Bereichstest ergeben hat. Hängt am Baustein, nicht im Hash.

    Der Hash ist die Version des Rezepts (§24.4) — stünde der Bericht darin,
    machte das **Prüfen** aus dem Rezept ein anderes, und jedes Projekt
    meldete beim Öffnen eine Änderung, die keine ist.

    ``excluded`` sind die Ecken, die :attr:`PartSpec.feasible` vorher als
    nicht baubar erklärt hat und an denen der Baustein wie erklärt ablehnt.
    Sie zählen nicht als Fehler — ein erklärter Ausschluss ist Teil des
    Vertrags; ein **unerklärter** Abbruch bleibt einer.
    """

    checked: int = 0
    failures: tuple[RangeFailure, ...] = ()
    excluded: tuple[RangeExclusion, ...] = ()

    @property
    def passed(self) -> bool:
        return self.checked > 0 and not self.failures


@dataclass(slots=True)
class _Silent:
    @property
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return None


#: Zwei Flächen bilden eine Wand, wenn ihre Normalen höchstens rund 18 Grad
#: von der Gegenrichtung abweichen. Eine Fase oder Keilspitze ist damit kein
#: vermeintlich dünnes Wandstück; eine facettierte Rundung bleibt eines.
OPPOSING_NORMAL: Final = -0.95

#: Höchstens so viele Flächen je Seite bekommt ein nativer Kreuzsatz. Das
#: begrenzt einen nicht unterbrechbaren VTK-Aufruf; rekursive Paarpartitionen
#: behalten trotzdem jedes Paar. Der Wert ändert nur die Bündelgröße.
INTERSECTION_BATCH_FACES: Final = 512

#: Der große, vektorisierte Schnittpfad materialisiert höchstens so viele
#: AABB-Paare gleichzeitig. Die Gesamtmenge bleibt vollständig; nur der
#: Arbeitsspeicher ist begrenzt.
INTERSECTION_PAIR_BATCH: Final = 250_000


@dataclass(frozen=True, slots=True)
class _AabbNode:
    """Ein Knoten der vollständigen Flächen-BVH."""

    indices: Any
    low: Any
    high: Any
    left: _AabbNode | None = None
    right: _AabbNode | None = None

    @property
    def is_leaf(self) -> bool:
        """Ob VTK diesen Knoten als begrenzten Kreuzsatz übernimmt."""
        return self.left is None


class _RangeCancelledError(Exception):
    """Beendet eine rekursive Geometriephase am nächsten sicheren Punkt."""


def _vtk_poly_data(vertices: Any, faces: Any) -> Any:
    """Das Netz für den räumlichen VTK-Index, ohne Qt oder Renderfenster."""
    import numpy as np
    from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    from vtkmodules.vtkCommonCore import vtkPoints
    from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData

    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)

    points = vtkPoints()
    points.SetData(numpy_to_vtk(vertices, deep=True))  # type: ignore[no-untyped-call]
    offsets = np.arange(0, len(faces) * 3 + 1, 3, dtype=np.int64)
    cells = vtkCellArray()
    cells.SetData(
        numpy_to_vtkIdTypeArray(offsets, deep=True),  # type: ignore[no-untyped-call]
        numpy_to_vtkIdTypeArray(faces.reshape(-1), deep=True),  # type: ignore[no-untyped-call]
    )
    data = vtkPolyData()
    data.SetPoints(points)
    data.SetPolys(cells)
    return data


def local_wall_thickness(mesh: Any, cancelled: CancelToken | None = None) -> float | None:
    """Die kleinste lokale Wand zwischen wirklich gegenläufigen Flächen.

    Von **jedem** Dreiecksmittelpunkt läuft ein Strahl nach innen bis zum
    ersten Austritt. Dessen Fläche muss gegenläufig sein: Nur dann ist der
    Abstand eine Wandstärke. So werden eine Fase, ein scharfer Keil und das
    Ende eines Zylinders nicht mit einer dünnen Wand verwechselt.

    Der räumliche Index rechnet in VTKs plattformgleichem C++-Kern. Das ist
    kein Rendering und zieht insbesondere weder Qt noch PySide in ``core``.
    Es gibt keine Stichprobe: auch ein kleines Detail mit einem einzigen
    Dreieck wird vermessen. ``None`` bedeutet, dass der Körper keine zwei
    gegenläufigen Flächen trägt, oder dass der Lauf abgebrochen wurde; der
    Aufrufer unterscheidet beides am Token.
    """
    import numpy as np
    from vtkmodules.vtkCommonCore import reference
    from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator

    body = mesh.raw
    if not len(body.faces):
        return None
    data = _vtk_poly_data(body.vertices, body.faces)
    locator = vtkStaticCellLocator()
    locator.SetDataSet(data)
    locator.BuildLocator()

    diagonal = float(mesh.bounds.diagonal)
    least = float("inf")
    centres = np.asarray(body.triangles_center, dtype=float)
    normals = np.asarray(body.face_normals, dtype=float)
    try:
        for origin, normal in zip(centres, normals, strict=True):
            if cancelled is not None and cancelled.is_cancelled:
                return None
            # Der Start liegt knapp **im** Körper. Sonst ist das eigene Dreieck
            # der erste Treffer bei t=0, und die Messung sagt an jeder Wand null.
            start = origin - normal * EPS_GEOM
            end = origin - normal * (diagonal + EPS_GEOM)
            travel = reference(0.0)
            point = [0.0, 0.0, 0.0]
            coordinates = [0.0, 0.0, 0.0]
            sub_id = reference(0)
            cell_id = reference(0)
            found = locator.IntersectWithLine(  # type: ignore[call-overload]
                start,
                end,
                EPS_GEOM,
                travel,
                point,
                coordinates,
                sub_id,
                cell_id,
            )
            if not found:
                continue
            # VTK schreibt hier eine ganzzahlige Zellkennung. Der reference-Stub
            # führt deren zur Laufzeit vorhandenes __int__ nicht auf.
            opposite = normals[int(cast(SupportsInt, cell_id))]
            if float(np.dot(normal, opposite)) > OPPOSING_NORMAL:
                continue
            least = min(least, float(np.linalg.norm(np.asarray(point) - origin)))
        return least if least < float("inf") else None
    finally:
        locator.FreeSearchStructure()
        locator.SetDataSet(None)  # type: ignore[arg-type]
        data.Initialize()


def _plane_cut(triangle: Any, distance: Any) -> Any:
    """Schnittpunkte eines Dreiecks mit einer Ebene, ohne Float32-Ausgabe."""
    import numpy as np

    points: list[Any] = []
    numeric_epsilon = (
        64.0 * np.finfo(float).eps * max(1.0, float(np.linalg.norm(np.ptp(triangle, axis=0))))
    )
    for index in range(3):
        following = (index + 1) % 3
        start_distance = float(distance[index])
        end_distance = float(distance[following])
        if abs(start_distance) <= numeric_epsilon:
            points.append(triangle[index])
        if start_distance * end_distance < 0.0:
            fraction = start_distance / (start_distance - end_distance)
            points.append(triangle[index] + fraction * (triangle[following] - triangle[index]))
    unique: list[Any] = []
    for point in points:
        if all(np.linalg.norm(point - existing) > EPS_GEOM for existing in unique):
            unique.append(point)
    return np.asarray(unique, dtype=float)


def _intervals_on_line(triangle: Any, distance: Any, direction: Any) -> tuple[Any, Any]:
    """Schnittintervalle gepaarter Dreiecke auf ihrer Ebenengeraden."""
    import numpy as np

    projection = np.einsum("kvd,kd->kv", triangle, direction)
    span = np.linalg.norm(np.ptp(triangle, axis=1), axis=1)
    numeric = 64.0 * np.finfo(float).eps * np.maximum(1.0, span)
    low = np.full(len(triangle), np.inf)
    high = np.full(len(triangle), -np.inf)
    for vertex in range(3):
        on_plane = np.abs(distance[:, vertex]) <= numeric
        value = projection[:, vertex]
        low = np.where(on_plane, np.minimum(low, value), low)
        high = np.where(on_plane, np.maximum(high, value), high)
        following = (vertex + 1) % 3
        start_distance = distance[:, vertex]
        end_distance = distance[:, following]
        crossing = start_distance * end_distance < 0.0
        denominator = start_distance - end_distance
        fraction = np.divide(
            start_distance,
            denominator,
            out=np.zeros_like(start_distance),
            where=denominator != 0.0,
        )
        crossing_value = value + fraction * (projection[:, following] - value)
        low = np.where(crossing, np.minimum(low, crossing_value), low)
        high = np.where(crossing, np.maximum(high, crossing_value), high)
    return low, high


def _coplanar_overlap(first_triangle: Any, second_triangle: Any, normal: Any) -> Any:
    """Positive Flächenüberdeckung gepaarter koplanarer Dreiecke (SAT in 2D)."""
    import numpy as np

    result = np.zeros(len(first_triangle), dtype=bool)
    dominant = np.argmax(np.abs(normal), axis=1)
    for dropped in range(3):
        selected = dominant == dropped
        if not np.any(selected):
            continue
        keep = [axis for axis in range(3) if axis != dropped]
        first_2d = first_triangle[selected][:, :, keep]
        second_2d = second_triangle[selected][:, :, keep]
        edges = np.concatenate(
            (
                np.roll(first_2d, -1, axis=1) - first_2d,
                np.roll(second_2d, -1, axis=1) - second_2d,
            ),
            axis=1,
        )
        axes = np.stack((-edges[:, :, 1], edges[:, :, 0]), axis=2)
        axis_length = np.linalg.norm(axes, axis=2)
        first_projection = np.einsum("ked,kvd->kev", axes, first_2d)
        second_projection = np.einsum("ked,kvd->kev", axes, second_2d)
        overlap = np.minimum(
            first_projection.max(axis=2), second_projection.max(axis=2)
        ) - np.maximum(first_projection.min(axis=2), second_projection.min(axis=2))
        result[selected] = np.all(overlap > EPS_GEOM * axis_length, axis=1)
    return result


def _distinct_points(candidates: Any) -> list[Any]:
    """Die Kandidaten ohne Wiederholung innerhalb der Geometrietoleranz."""
    import numpy as np

    unique: list[Any] = []
    for candidate in candidates:
        if all(np.linalg.norm(candidate - existing) > EPS_GEOM for existing in unique):
            unique.append(candidate)
    return unique


@dataclass(slots=True)
class _PendingPairs:
    """AABB-Kandidatenpaare, die der große Pfad blockweise sammelt."""

    first: list[Any] = field(default_factory=list)
    second: list[Any] = field(default_factory=list)
    count: int = 0

    def add(self, first_index: int, later: Any) -> None:
        import numpy as np

        self.first.append(np.full(len(later), first_index, dtype=np.int64))
        self.second.append(later)
        self.count += len(later)

    def take(self) -> tuple[Any, Any]:
        """Gibt die gesammelten Paare heraus und leert den Speicher dahinter."""
        import numpy as np

        first = np.concatenate(self.first)
        second = np.concatenate(self.second)
        self.first = []
        self.second = []
        self.count = 0
        return first, second


@dataclass(slots=True)
class _IntersectionCheck:
    """Die Selbstdurchdringungsprüfung eines Netzes, in ihre Schritte zerlegt.

    Bis zum 02.09.2026 war das eine Funktion von 806 Zeilen mit acht inneren
    Funktionen, die sich neun Werte über ihre Closure teilten. Die Werte
    stehen jetzt als Felder hier, die Schritte als Methoden — derselbe
    Algorithmus, dieselben Toleranzen, dieselbe Reihenfolge der Prüfungen.
    Was sich geändert hat: Der dreimal kopierte Block „gemeinsame Punkte
    zweier Dreiecke" ist :meth:`shared_points`, und die drei reinen
    Rechenhelfer (:func:`_plane_cut`, :func:`_intervals_on_line`,
    :func:`_coplanar_overlap`) stehen als Modulfunktionen, weil sie nichts
    vom Netz wissen müssen.
    """

    cancelled: CancelToken | None
    faces: Any
    vertices: Any
    triangles: Any
    raw_normals: Any
    normal_lengths: Any
    centres: Any
    triangle_low: Any
    triangle_high: Any

    @classmethod
    def of(cls, mesh: Any, cancelled: CancelToken | None) -> _IntersectionCheck | None:
        """Bereitet das Netz vor; ``None``, wenn nichts zu prüfen ist.

        Nullflächen haben keine Oberfläche, die etwas durchdringen könnte, und
        werden vor der Partition entfernt.
        """
        import numpy as np

        body = mesh.raw.copy()
        faces = np.asarray(body.faces, dtype=np.int64)
        vertices = np.asarray(body.vertices, dtype=float)
        if len(faces) < 2 or not len(vertices):
            return None
        triangles = vertices[faces]
        raw_normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        twice_area = np.linalg.norm(raw_normals, axis=1)
        edge_lengths = np.linalg.norm(np.roll(triangles, -1, axis=1) - triangles, axis=2)
        longest_edge = edge_lengths.max(axis=1)
        altitude = np.divide(
            twice_area,
            longest_edge,
            out=np.zeros_like(twice_area),
            where=longest_edge > 0.0,
        )
        valid_surface = (longest_edge > EPS_GEOM) & (altitude > EPS_GEOM)
        faces = faces[valid_surface]
        raw_normals = raw_normals[valid_surface]
        if len(faces) < 2:
            return None
        triangles = vertices[faces]
        return cls(
            cancelled=cancelled,
            faces=faces,
            vertices=vertices,
            triangles=triangles,
            raw_normals=raw_normals,
            normal_lengths=np.linalg.norm(raw_normals, axis=1),
            centres=triangles.mean(axis=1),
            triangle_low=triangles.min(axis=1),
            triangle_high=triangles.max(axis=1),
        )

    def run(self) -> bool:
        """Groß über den statischen VTK-Index, sonst über die eigene BVH."""
        import numpy as np

        try:
            if len(self.faces) > INTERSECTION_BATCH_FACES * 8:
                return self.large_mesh_intersects()
            root = self.build_node(np.arange(len(self.faces), dtype=np.int64))
            return self.same_node(root)
        except _RangeCancelledError:
            return False

    # --- gemeinsame Punkte -------------------------------------------------

    def shared_points(self, first_index: int, second_index: int, seeds: Any = ()) -> Any:
        """Die Punkte, die zwei Dreiecke topologisch teilen, als Float64-Feld.

        ``seeds`` sind Punkte, die vorab als gemeinsam bekannt sind (etwa über
        einen gemeinsamen Vertex-Index); dazu kommt jedes Eckpaar, das sich
        innerhalb der Geometrietoleranz berührt, als Mittelpunkt. Dieser
        Block stand vorher dreimal im Code.
        """
        import numpy as np

        first_points = self.vertices[self.faces[first_index]]
        second_points = self.vertices[self.faces[second_index]]
        distances = np.linalg.norm(first_points[:, None, :] - second_points[None, :, :], axis=2)
        near = np.argwhere(distances <= EPS_GEOM)
        candidates = list(seeds)
        candidates.extend(
            (first_points[int(left)] + second_points[int(right)]) / 2.0 for left, right in near
        )
        return np.asarray(_distinct_points(candidates), dtype=float)

    # --- ein Paar ------------------------------------------------------------

    def pair_intersects_beyond_topology(
        self, first_index: int, second_index: int, shared_points: Any
    ) -> bool:
        """Bestätigt einen nativen Kandidaten analytisch in Float64.

        VTK liefert Kontaktpunkte intern teilweise in Float32. Damit darf
        weder die absolute Lage noch die Blockgröße aus einem gemeinsamen
        Vertex eine kurze Strecke machen. Die beiden Dreiecke werden deshalb
        gegen die Ebene des jeweils anderen geschnitten und ihre Intervalle
        auf der Schnittgeraden verglichen. Nur der Anteil außerhalb bereits
        gemeinsamer topologischer Punkte ist ein Selbstschnitt. Koplanare
        Paare übernimmt der vollständige SAT.
        """
        import numpy as np

        first_triangle = self.triangles[first_index].copy()
        second_triangle = self.triangles[second_index].copy()
        shared_points = np.asarray(shared_points, dtype=float)
        # Zwei Koordinaten desselben topologischen Punkts werden vor der
        # Rechnung auf ihre gemeinsame Float64-Darstellung gebracht. Das ist
        # keine größere Geometrietoleranz: Ausschließlich die bereits durch
        # EPS_GEOM als identisch erkannte Repräsentation wird dedupliziert.
        for shared_point in shared_points:
            first_triangle[np.linalg.norm(first_triangle - shared_point, axis=1) <= EPS_GEOM] = (
                shared_point
            )
            second_triangle[np.linalg.norm(second_triangle - shared_point, axis=1) <= EPS_GEOM] = (
                shared_point
            )
        first_normal = np.cross(
            first_triangle[1] - first_triangle[0],
            first_triangle[2] - first_triangle[0],
        )
        second_normal = np.cross(
            second_triangle[1] - second_triangle[0],
            second_triangle[2] - second_triangle[0],
        )
        first_length = float(np.linalg.norm(first_normal))
        second_length = float(np.linalg.norm(second_normal))
        if np.linalg.norm(np.cross(first_normal, second_normal)) <= (
            EPS_GEOM * first_length * second_length
        ):
            return False

        first_distance = np.dot(first_triangle - second_triangle[0], second_normal) / second_length
        second_distance = np.dot(second_triangle - first_triangle[0], first_normal) / first_length
        if np.all(np.abs(first_distance) <= EPS_GEOM) and np.all(
            np.abs(second_distance) <= EPS_GEOM
        ):
            return False
        if (
            np.all(first_distance > EPS_GEOM)
            or np.all(first_distance < -EPS_GEOM)
            or np.all(second_distance > EPS_GEOM)
            or np.all(second_distance < -EPS_GEOM)
        ):
            return False

        first_cut = _plane_cut(first_triangle, first_distance)
        second_cut = _plane_cut(second_triangle, second_distance)
        if not len(first_cut) or not len(second_cut):
            return False
        direction = np.cross(first_normal, second_normal)
        direction /= np.linalg.norm(direction)
        first_projection = np.dot(first_cut, direction)
        second_projection = np.dot(second_cut, direction)
        low = max(float(first_projection.min()), float(second_projection.min()))
        high = min(float(first_projection.max()), float(second_projection.max()))
        if high < low - EPS_GEOM:
            return False

        if not len(shared_points):
            return True
        shared_projection = np.dot(shared_points, direction)
        shared_low = float(shared_projection.min())
        shared_high = float(shared_projection.max())
        if high - low <= EPS_GEOM:
            point = (high + low) / 2.0
            return bool(np.all(np.abs(shared_projection - point) > EPS_GEOM))
        return low < shared_low - EPS_GEOM or high > shared_high + EPS_GEOM

    # --- koplanare Gruppen ---------------------------------------------------

    def coplanar_groups_overlap(self, first: Any, second: Any, *, same: bool) -> bool:
        """Prüft positive koplanare Flächenüberdeckung blockweise in NumPy-C.

        ``vtkIntersectionPolyDataFilter`` liefert dafür absichtlich keine
        Linien. Die BVH begrenzt diesen vollständigen Ergänzungstest auf
        höchstens 512² Paare; über einzelne Dreieckspaare läuft keine
        Python-Schleife. Reiner Vertex- oder Kantenkontakt hat auf mindestens
        einer Trennachse keine positive Breite und bleibt deshalb erlaubt.
        """
        import numpy as np

        if self.cancelled is not None and self.cancelled.is_cancelled:
            return False
        triangles = self.triangles
        raw_normals = self.raw_normals
        normal_lengths = self.normal_lengths
        if same:
            first_local, second_local = np.triu_indices(len(first), k=1)
            first_indices = np.asarray(first, dtype=np.int64)[first_local]
            second_indices = np.asarray(second, dtype=np.int64)[second_local]
        else:
            first_indices = np.repeat(np.asarray(first, dtype=np.int64), len(second))
            second_indices = np.tile(np.asarray(second, dtype=np.int64), len(first))
        if not len(first_indices):
            return False

        first_normals = raw_normals[first_indices]
        second_normals = raw_normals[second_indices]
        cross = np.linalg.norm(np.cross(first_normals, second_normals), axis=1)
        parallel = cross <= (
            EPS_GEOM * normal_lengths[first_indices] * normal_lengths[second_indices]
        )
        first_plane_distance = (
            np.abs(
                np.einsum(
                    "kvd,kd->kv",
                    triangles[second_indices] - triangles[first_indices, 0, None, :],
                    first_normals,
                )
            )
            / normal_lengths[first_indices, None]
        )
        second_plane_distance = (
            np.abs(
                np.einsum(
                    "kvd,kd->kv",
                    triangles[first_indices] - triangles[second_indices, 0, None, :],
                    second_normals,
                )
            )
            / normal_lengths[second_indices, None]
        )
        # Auf einer gekrümmten Manifold-Fläche können benachbarte lange
        # Dreiecke um wenige Float32-ULP gegeneinander gekippt sein. Liegen
        # trotzdem alle sechs Punkte innerhalb der unveränderten
        # Geometrietoleranz in der Gegenseite, ist das derselbe koplanare
        # Repräsentationsfall. Der SAT entscheidet weiterhin, ob ihre Flächen
        # wirklich positiv überlappen.
        parallel |= (first_plane_distance.max(axis=1) <= EPS_GEOM) & (
            second_plane_distance.max(axis=1) <= EPS_GEOM
        )
        if not np.any(parallel):
            return False
        first_indices = first_indices[parallel]
        second_indices = second_indices[parallel]
        first_normals = first_normals[parallel]
        plane_distance = (
            np.abs(
                np.einsum(
                    "ij,ij->i",
                    first_normals,
                    triangles[second_indices, 0] - triangles[first_indices, 0],
                )
            )
            / normal_lengths[first_indices]
        )
        coplanar = plane_distance <= EPS_GEOM
        if not np.any(coplanar):
            return False
        first_indices = first_indices[coplanar]
        second_indices = second_indices[coplanar]
        first_normals = first_normals[coplanar]

        # Dieselbe Fläche in anderer Reihenfolge ist nur eine doppelte Zelle,
        # keine zweite sich durchdringende Oberfläche.
        different = np.any(
            np.sort(self.faces[first_indices], axis=1)
            != np.sort(self.faces[second_indices], axis=1),
            axis=1,
        )
        first_indices = first_indices[different]
        second_indices = second_indices[different]
        first_normals = first_normals[different]
        if not len(first_indices):
            return False

        dominant = np.argmax(np.abs(first_normals), axis=1)
        for dropped in range(3):
            if self.cancelled is not None and self.cancelled.is_cancelled:
                return False
            selected = dominant == dropped
            if not np.any(selected):
                continue
            keep = [axis for axis in range(3) if axis != dropped]
            first_2d = triangles[first_indices[selected]][:, :, keep]
            second_2d = triangles[second_indices[selected]][:, :, keep]
            first_edges = np.roll(first_2d, -1, axis=1) - first_2d
            second_edges = np.roll(second_2d, -1, axis=1) - second_2d
            edges = np.concatenate((first_edges, second_edges), axis=1)
            axes = np.stack((-edges[:, :, 1], edges[:, :, 0]), axis=2)
            axis_lengths = np.linalg.norm(axes, axis=2)
            first_projection = np.einsum("ked,kvd->kev", axes, first_2d)
            second_projection = np.einsum("ked,kvd->kev", axes, second_2d)
            overlap = np.minimum(first_projection.max(axis=2), second_projection.max(axis=2)) - (
                np.maximum(first_projection.min(axis=2), second_projection.min(axis=2))
            )
            if np.any(np.all(overlap > EPS_GEOM * axis_lengths, axis=1)):
                return True
        return False

    # --- der große Pfad ------------------------------------------------------

    def large_mesh_intersects(self) -> bool:
        """Prüft große Netze blockweise gegen einen statischen VTK-Index.

        Der Index liefert ausschließlich eine vollständige AABB-Obermenge.
        Ebenenseiten, Schnittintervalle und koplanare Flächenüberdeckung
        werden danach in Float64 gerechnet. Es gibt weder Stichprobe noch
        quadratische Paarmatrix.
        """
        import ctypes

        import numpy as np
        from vtkmodules.vtkCommonCore import vtkIdList, vtkIdTypeArray
        from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator

        data = _vtk_poly_data(self.vertices, self.faces)
        locator = vtkStaticCellLocator()
        locator.SetDataSet(data)
        locator.BuildLocator()
        ids = vtkIdList()
        id_type = ctypes.c_int64 if vtkIdTypeArray().GetDataTypeSize() == 8 else ctypes.c_int32
        pending = _PendingPairs()
        try:
            for first_index, triangle in enumerate(self.triangles):
                if (
                    first_index % 256 == 0
                    and self.cancelled is not None
                    and self.cancelled.is_cancelled
                ):
                    raise _RangeCancelledError
                bounds = np.column_stack((triangle.min(axis=0), triangle.max(axis=0))).ravel()
                ids.Reset()
                locator.FindCellsWithinBounds(bounds.tolist(), ids)
                count = ids.GetNumberOfIds()
                if not count:
                    continue
                address = int(ids.GetPointer(0).split("_")[1], 16)
                array = np.ctypeslib.as_array((id_type * count).from_address(address))
                later = np.array(array[array > first_index], dtype=np.int64, copy=True)
                if not len(later):
                    continue
                pending.add(first_index, later)
                if pending.count >= INTERSECTION_PAIR_BATCH and self.narrow(*pending.take()):
                    return True
            return bool(pending.count) and self.narrow(*pending.take())
        finally:
            locator.FreeSearchStructure()
            locator.SetDataSet(None)  # type: ignore[arg-type]
            data.Initialize()

    def narrow(self, first_indices: Any, second_indices: Any) -> bool:
        """Bestätigt einen Block AABB-Kandidaten analytisch."""
        import numpy as np

        if self.cancelled is not None and self.cancelled.is_cancelled:
            raise _RangeCancelledError
        triangles = self.triangles
        first_triangle = triangles[first_indices]
        second_triangle = triangles[second_indices]
        first_normal = self.raw_normals[first_indices]
        second_normal = self.raw_normals[second_indices]
        first_length = self.normal_lengths[first_indices]
        second_length = self.normal_lengths[second_indices]
        first_distance = (
            np.einsum(
                "kvd,kd->kv",
                first_triangle - second_triangle[:, 0, None, :],
                second_normal,
            )
            / second_length[:, None]
        )
        second_distance = (
            np.einsum(
                "kvd,kd->kv",
                second_triangle - first_triangle[:, 0, None, :],
                first_normal,
            )
            / first_length[:, None]
        )
        possible = ~(
            np.all(first_distance > EPS_GEOM, axis=1)
            | np.all(first_distance < -EPS_GEOM, axis=1)
            | np.all(second_distance > EPS_GEOM, axis=1)
            | np.all(second_distance < -EPS_GEOM, axis=1)
        )
        if not np.any(possible):
            return False
        first_indices = first_indices[possible]
        second_indices = second_indices[possible]
        first_triangle = first_triangle[possible]
        second_triangle = second_triangle[possible]
        first_normal = first_normal[possible]
        second_normal = second_normal[possible]
        first_length = first_length[possible]
        second_length = second_length[possible]
        first_distance = first_distance[possible]
        second_distance = second_distance[possible]

        direction = np.cross(first_normal, second_normal)
        direction_length = np.linalg.norm(direction, axis=1)
        coplanar = direction_length <= (EPS_GEOM * first_length * second_length)
        coplanar |= (np.max(np.abs(first_distance), axis=1) <= EPS_GEOM) & (
            np.max(np.abs(second_distance), axis=1) <= EPS_GEOM
        )
        coplanar_hits = (
            _coplanar_overlap(
                first_triangle[coplanar],
                second_triangle[coplanar],
                first_normal[coplanar],
            )
            if np.any(coplanar)
            else np.asarray([], dtype=bool)
        )
        if np.any(coplanar_hits):
            return True

        noncoplanar = ~coplanar
        if not np.any(noncoplanar):
            return False
        first_indices = first_indices[noncoplanar]
        second_indices = second_indices[noncoplanar]
        first_triangle = first_triangle[noncoplanar]
        second_triangle = second_triangle[noncoplanar]
        first_distance = first_distance[noncoplanar]
        second_distance = second_distance[noncoplanar]
        direction = direction[noncoplanar]
        direction /= direction_length[noncoplanar, None]
        first_low, first_high = _intervals_on_line(first_triangle, first_distance, direction)
        second_low, second_high = _intervals_on_line(second_triangle, second_distance, direction)
        low = np.maximum(first_low, second_low)
        high = np.minimum(first_high, second_high)
        crossing = np.isfinite(low) & np.isfinite(high) & (high >= low - EPS_GEOM)
        if not np.any(crossing):
            return False

        first_indices = first_indices[crossing]
        second_indices = second_indices[crossing]
        first_triangle = first_triangle[crossing]
        second_triangle = second_triangle[crossing]
        direction = direction[crossing]
        low = low[crossing]
        high = high[crossing]
        coordinate_matches = (
            np.linalg.norm(
                first_triangle[:, :, None, :] - second_triangle[:, None, :, :],
                axis=3,
            )
            <= EPS_GEOM
        )
        matched_vertices = np.any(coordinate_matches, axis=2)
        has_common = np.any(matched_vertices, axis=1)
        if np.any(has_common):
            projection = np.einsum("kvd,kd->kv", first_triangle[has_common], direction[has_common])
            selected = matched_vertices[has_common]
            shared_low = np.min(np.where(selected, projection, np.inf), axis=1)
            shared_high = np.max(np.where(selected, projection, -np.inf), axis=1)
            contact_low = low[has_common]
            contact_high = high[has_common]
            point_contact = contact_high - contact_low <= EPS_GEOM
            point = (contact_high + contact_low) / 2.0
            outside_point = (point < shared_low - EPS_GEOM) | (point > shared_high + EPS_GEOM)
            extends = (contact_low < shared_low - EPS_GEOM) | (
                contact_high > shared_high + EPS_GEOM
            )
            suspicious = np.where(point_contact, outside_point, extends)
            if np.any(suspicious):
                common_first = first_indices[has_common][suspicious]
                common_second = second_indices[has_common][suspicious]
                for first_index, second_index in zip(common_first, common_second, strict=True):
                    first_index = int(first_index)
                    second_index = int(second_index)
                    if self.pair_intersects_beyond_topology(
                        first_index, second_index, self.shared_points(first_index, second_index)
                    ):
                        return True

        for first_index, second_index in zip(
            first_indices[~has_common], second_indices[~has_common], strict=True
        ):
            if self.cancelled is not None and self.cancelled.is_cancelled:
                raise _RangeCancelledError
            first_index = int(first_index)
            second_index = int(second_index)
            near_shared_points = self.shared_points(first_index, second_index)
            if not len(near_shared_points) or self.pair_intersects_beyond_topology(
                first_index, second_index, near_shared_points
            ):
                return True
        return False

    # --- der native Pfad -----------------------------------------------------

    def native_groups_intersect(self, first: Any, second: Any, *, same: bool = False) -> bool:
        """Prüft einen begrenzten Kreuzsatz im stillen nativen VTK-Kern.

        Der frühere ``vtkIntersectionPolyDataFilter`` erzeugte für einen
        normalen Negativbefund aus seinem **inneren** Filter eine Warnung auf
        stderr. Ein Observer am äußeren Objekt sah sie nicht; globale
        Warnzustände oder eine Prozessumleitung wären nebenläufig falsch.
        ``vtkCollisionDetectionFilter`` liefert lokal still dieselben beiden
        Face-IDs und die Kontaktstrecke. Koplanare Überdeckung ergänzt danach
        weiterhin der vollständige SAT. Vor dem nativen Aufbau entfernt eine
        vektorisierte AABB-Prüfung ausschließlich unmögliche Paare. Sie ist
        vollständig und macht aus 512 getrennten Flächen keinen Satz von 512
        Identitätskontakten.
        """
        import numpy as np
        from vtkmodules.util.numpy_support import vtk_to_numpy
        from vtkmodules.vtkCommonCore import vtkCommand
        from vtkmodules.vtkCommonMath import vtkMatrix4x4
        from vtkmodules.vtkFiltersModeling import vtkCollisionDetectionFilter

        from app.core.errors import CANCEL, REPAIR_AND_RETRY, GeometryError

        if self.cancelled is not None and self.cancelled.is_cancelled:
            return False
        original_first = np.asarray(first, dtype=np.int64)
        original_second = np.asarray(second, dtype=np.int64)
        overlap = np.ones((len(original_first), len(original_second)), dtype=bool)
        for axis in range(3):
            if self.cancelled is not None and self.cancelled.is_cancelled:
                return False
            overlap &= (
                self.triangle_low[original_first, axis, None]
                <= self.triangle_high[original_second, axis][None, :] + EPS_GEOM
            )
            overlap &= (
                self.triangle_low[original_second, axis][None, :]
                <= self.triangle_high[original_first, axis, None] + EPS_GEOM
            )
        if same:
            overlap = np.triu(overlap, k=1)
        first_local, second_local = np.nonzero(overlap)
        if not len(first_local):
            return False
        # Das Kreuzprodukt dieser beiden Mengen ist nur eine Obermenge der
        # Kandidaten. Deshalb kann kein Paar verloren gehen; der native Filter
        # sieht lediglich gelegentlich zusätzliche, räumlich getrennte Paare.
        first = original_first[np.unique(first_local)]
        second = original_second[np.unique(second_local)]
        native_triangles = self.triangles[np.concatenate((first, second))]
        native_origin = (
            native_triangles.min(axis=(0, 1)) + native_triangles.max(axis=(0, 1))
        ) / 2.0
        native_vertices = self.vertices - native_origin
        first_data = None
        second_data = None
        collision = None
        contacts = None
        try:
            # VTK liefert seine Kontaktpunkte intern teilweise in Float32.
            # Jeder begrenzte Kreuzsatz rechnet deshalb um seinen eigenen
            # Mittelpunkt: Eine identische Hakenform muss bei y=60 denselben
            # Befund haben wie am Ursprung. Die globale Lage ist für Schnitte
            # irrelevant, ihre großen Koordinaten kosten aber Mantissenbits.
            first_data = _vtk_poly_data(native_vertices, self.faces[first])
            second_data = _vtk_poly_data(native_vertices, self.faces[second])
            first_matrix = vtkMatrix4x4()
            first_matrix.Identity()
            second_matrix = vtkMatrix4x4()
            second_matrix.Identity()
            collision = vtkCollisionDetectionFilter()
            collision.SetInputData(0, first_data)
            collision.SetInputData(1, second_data)
            collision.SetMatrix(0, first_matrix)
            collision.SetMatrix(1, second_matrix)
            collision.SetCollisionModeToAllContacts()
            collision.SetBoxTolerance(0.0)
            # Der Kollisionsfilter benutzt diese Zahl nicht als
            # Geometrietoleranz, sondern bläht seine Zellen auf. Schon
            # EPS_GEOM erzeugte dadurch auf sauberen Gewinden und Haken
            # zusätzliche Scheinkontakte; die analytische Float64-Prüfung
            # behandelt Rundung danach gezielt.
            collision.SetCellTolerance(0.0)
            native_errors: list[str] = []

            def remember_native_error(_caller: Any, _event: str, *details: Any) -> None:
                """Merkt nur Fehler dieses Filterobjekts, ohne globalen VTK-Zustand."""
                message = str(details[-1]).strip() if details else ""
                native_errors.append(message or "VTK ErrorEvent")

            collision.AddObserver(vtkCommand.ErrorEvent, remember_native_error)
            collision.Update()
            if native_errors:
                raise RuntimeError(
                    "Der native Kollisionsfilter meldet einen Fehler: " + native_errors[-1]
                )
            if collision.GetErrorCode() != 0:
                raise RuntimeError(
                    "Der native Kollisionsfilter meldet eine unvollständige Ausgabe."
                )
            contacts = collision.GetContactsOutput()
            count = int(collision.GetNumberOfContacts())
            if not count:
                return self.coplanar_groups_overlap(original_first, original_second, same=same)
            first_ids = np.array(
                vtk_to_numpy(  # type: ignore[no-untyped-call]
                    collision.GetContactCells(0)
                ),
                dtype=np.int64,
                copy=True,
            )
            second_ids = np.array(
                vtk_to_numpy(  # type: ignore[no-untyped-call]
                    collision.GetContactCells(1)
                ),
                dtype=np.int64,
                copy=True,
            )
            if not (
                len(first_ids) == count
                and len(second_ids) == count
                and contacts.GetNumberOfCells() == count
            ):
                raise RuntimeError(
                    "Der native Kollisionsfilter ordnet Kontakte und Face-IDs nicht eindeutig zu."
                )
            for position, (local_first, local_second) in enumerate(
                zip(first_ids, second_ids, strict=True)
            ):
                if (
                    position % 256 == 0
                    and self.cancelled is not None
                    and self.cancelled.is_cancelled
                ):
                    return False
                local_first = int(local_first)
                local_second = int(local_second)
                if not (0 <= local_first < len(first) and 0 <= local_second < len(second)):
                    raise RuntimeError(
                        "Der native Kollisionsfilter liefert eine ungültige Face-ID."
                    )
                first_index = int(first[local_first])
                second_index = int(second[local_second])
                if same and first_index == second_index:
                    continue
                cell = contacts.GetCell(position)
                if cell is None or cell.GetNumberOfPoints() != 2:
                    raise RuntimeError(
                        "Der native Kollisionsfilter liefert keine eindeutige Kontaktstrecke."
                    )
                common = np.intersect1d(
                    self.faces[first_index], self.faces[second_index], assume_unique=False
                )
                shared_global = self.shared_points(
                    first_index, second_index, [self.vertices[index] for index in common]
                )
                if self.pair_intersects_beyond_topology(first_index, second_index, shared_global):
                    return True
            return self.coplanar_groups_overlap(original_first, original_second, same=same)
        except GeometryError:
            raise
        except Exception as problem:
            raise GeometryError(
                title=_("Die Geometrie ließ die Operation nicht zu."),
                detail=_("Der Vorgang ist nicht durchgelaufen."),
                suggestions=(REPAIR_AND_RETRY, CANCEL),
                values={"check": "self_intersection"},
            ) from problem
        finally:
            # VTK hält Eingänge und Ausgaben sonst bis zum nächsten zyklischen
            # Python-GC fest. Das ``finally`` gilt ausdrücklich auch für einen
            # nativen Fehler oder fehlende Treffer-ID-Arrays.
            if collision is not None:
                collision.RemoveAllInputs()
            if contacts is not None:
                contacts.Initialize()
            if first_data is not None:
                first_data.Initialize()
            if second_data is not None:
                second_data.Initialize()

    # --- die BVH -------------------------------------------------------------

    @staticmethod
    def bounds_disjoint(first: _AabbNode, second: _AabbNode) -> bool:
        """Ob zwei BVH-Knoten sich geometrisch nicht erreichen können."""
        import numpy as np

        return bool(np.any(first.high < second.low) or np.any(second.high < first.low))

    def build_node(self, indices: Any) -> _AabbNode:
        """Baut räumlich am Median; die Face-Reihenfolge entscheidet nichts."""
        import numpy as np

        if self.cancelled is not None and self.cancelled.is_cancelled:
            raise _RangeCancelledError
        selected = self.triangles[indices]
        low = selected.min(axis=(0, 1))
        high = selected.max(axis=(0, 1))
        if len(indices) <= INTERSECTION_BATCH_FACES:
            return _AabbNode(indices=indices, low=low, high=high)
        centres = self.centres
        span = np.ptp(centres[indices], axis=0)
        axis = int(np.argmax(span if np.any(span) else high - low))
        secondary = [dimension for dimension in range(3) if dimension != axis]
        ordered = indices[
            np.lexsort(
                (
                    centres[indices, secondary[1]],
                    centres[indices, secondary[0]],
                    centres[indices, axis],
                )
            )
        ]
        middle = len(ordered) // 2
        left = self.build_node(ordered[:middle])
        right = self.build_node(ordered[middle:])
        return _AabbNode(indices=ordered, low=low, high=high, left=left, right=right)

    def distinct_nodes(self, first: _AabbNode, second: _AabbNode) -> bool:
        """Prüft zwei disjunkte Teilmengen vollständig gegeneinander."""
        if self.cancelled is not None and self.cancelled.is_cancelled:
            return False
        if self.bounds_disjoint(first, second):
            return False
        if first.is_leaf and second.is_leaf:
            return self.native_groups_intersect(first.indices, second.indices)
        if not first.is_leaf and (second.is_leaf or len(first.indices) >= len(second.indices)):
            assert first.left is not None and first.right is not None
            return self.distinct_nodes(first.left, second) or self.distinct_nodes(
                first.right, second
            )
        assert second.left is not None and second.right is not None
        return self.distinct_nodes(first, second.left) or self.distinct_nodes(first, second.right)

    def same_node(self, node: _AabbNode) -> bool:
        """Prüft alle ungeordneten Paare eines Knotens genau einmal."""
        if self.cancelled is not None and self.cancelled.is_cancelled:
            return False
        if node.is_leaf:
            return self.native_groups_intersect(node.indices, node.indices, same=True)
        assert node.left is not None and node.right is not None
        return (
            self.distinct_nodes(node.left, node.right)
            or self.same_node(node.left)
            or self.same_node(node.right)
        )


def has_self_intersections(mesh: Any, cancelled: CancelToken | None = None) -> bool:
    """Ob nicht benachbarte Dreiecke einander schneiden.

    Ein wasserdichtes Netz kann aus zwei geschlossenen Hüllen bestehen, die
    durcheinanderlaufen. Topologieflags sehen das nicht. Disjunkte
    Flächenpartitionen geben jedes Dreieckspaar genau einem Kreuzsatz: dem
    ersten Rekursionsknoten, an dem die beiden Flächen auf verschiedenen
    Seiten liegen. VTK prüft diesen ganzen Kreuzsatz im C++-Kern. Das ist
    formal vollständig und vermeidet eine Python-Schleife über O(n²) Paare.

    Flächen mit gemeinsamem Eckpunkt sind topologische Nachbarn und keine
    Selbstdurchdringung. Nullflächen haben keine Oberfläche, die etwas
    durchdringen könnte, und werden vor der Partition entfernt. Die Schritte
    stehen in :class:`_IntersectionCheck`.
    """
    if cancelled is not None and cancelled.is_cancelled:
        return False
    check = _IntersectionCheck.of(mesh, cancelled)
    if check is None:
        return False
    return check.run()


def printable_gap(
    mesh: Any, profile: Profile, *, cancelled: CancelToken | None = None
) -> float | None:
    """Kleinster Flächenabstand aller Komponenten, unabhängig von ihrer Reihenfolge."""
    from app.core.geom.measure import surface_gap
    from app.core.geom.mesh import MeshData

    pieces = mesh.raw.split(only_watertight=False)
    if len(pieces) < 2:
        return None
    closest = float(mesh.bounds.diagonal)
    for index, first in enumerate(pieces):
        for second in pieces[index + 1 :]:
            if cancelled is not None and cancelled.is_cancelled:
                return None
            measured = surface_gap(MeshData.of(first), MeshData.of(second), closest)
            if measured is None:
                return None
            closest = min(closest, measured)
            if closest <= EPS_GEOM:
                return 0.0
    return closest


def check(
    params: type[BaseParams],
    build: Any,
    profile: Profile,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
    joined_by_host: bool = False,
    bodies: int = 1,
    wall: WallRequirement = DEFAULT_WALL_REQUIREMENT,
    features: tuple[FeatureRequirement, ...] = (),
    feasible: Callable[[BaseParams], Any] | None = None,
) -> RangeReport:
    """Fährt die Ecken und sagt je Ecke, was nicht hielt.

    ``feasible`` ist die erklärte Bedingung des Bausteins zwischen seinen
    Parametern (:attr:`PartSpec.feasible`): Nennt sie für eine Ecke einen
    Grund, muss der Bau dort mit ``ValidationError`` ablehnen — dann ist die
    Ecke ein erklärter Ausschluss. Baut er trotzdem, ist die Erklärung falsch
    und die Ecke ein Fehler; bricht er anders ab, ebenso.

    ``joined_by_host`` nimmt die Prüfung auf **eine** Komponente heraus — für
    Bausteine, deren Teile erst der Träger verbindet. Der Lochwand-Einhänger
    setzt ohne Rückplatte je Haken einen Zapfen; zwei Zapfen sind zwei Körper,
    und an dem Teil, an das sie kommen, sind sie einer. Ohne diesen Schalter
    trüge sein Katalogeintrag eine Warnung über einen Baustein, der im Einsatz
    tadellos ist (§24.5 verlangt, dass ein gebrochener Bericht dort steht).
    Die übrigen drei Prüfungen gelten unverändert: Ein Baustein darf auch
    mehrteilig weder undicht noch leer noch zu dünn sein.

    ``bodies`` ist der **andere** mehrteilige Fall (§24.3, Entscheidung Robert
    vom 25.08.2026): print-in-place — ein Scharnier, das schon beim Drucken
    beweglich ist. Hier hält kein Träger die Teile zusammen, sie sollen
    getrennt bleiben. Geprüft wird deshalb nicht *ob* der Baustein zerfällt,
    sondern **ob er in so viele Teile zerfällt, wie er erklärt hat**: Zwei
    statt zwei ist die Zusage, drei statt zwei ist ein Fehler wie jeder andere.
    Unerklärtes Zerfallen bleibt damit rot — die Prüfung wird nicht schwächer,
    sondern genauer.

    ``wall`` macht die Mindestwand zum Vertrag statt zur Namenssonderregel:
    Profilgrenze, benannter Geometrieparameter oder eine fachlich begründete
    Nichtanwendbarkeit. ``features`` nennt ebenso, welches Merkmal in welcher
    Parameterstellung vorkommen muss. Ohne diese Deklaration werden vorhandene
    Merkmale weiterhin auf ID, Herkunft und Maße geprüft.

    ``build`` ist, was aus Werten einen Körper macht — für ein Rezept die
    Auswertung, für eine ``.py`` ihre Funktion. Ein Fehlschlag bricht nicht ab:
    Der Kunde soll **alle** brechenden Ecken sehen, nicht je Lauf eine.

    Abbruch ist Abbruch (§15.6): Was bis dahin geprüft ist, kommt zurück,
    und ``checked`` sagt ehrlich, wie weit es kam — ein abgebrochener Lauf
    sieht nie wie ein bestandener aus, denn ``passed`` verlangt Fehlerfreiheit
    **über alle** Ecken, und die Zahl steht daneben.
    """
    from app.core.geom.mesh import as_mesh_data

    token = cancelled or _Silent()
    plan = corners(params)
    failures: list[RangeFailure] = []
    excluded: list[RangeExclusion] = []
    checked = 0

    def announce(index: int, phase: int) -> None:
        if progress is None:
            return
        progress(
            (index * 4 + phase) / (len(plan) * 4),
            str(_("Bereichstest, Ecke {n} von {total}")).format(n=index + 1, total=len(plan)),
        )

    def add(values: dict[str, Any], reason: str) -> None:
        failures.append(RangeFailure(dict(values), reason[:200]))

    for index, values in enumerate(plan):
        if _is_cancelled(token):
            break
        announce(index, 0)
        # **Das Spiel kommt aus dem Profil, wie im Einsatz.** Ein Baustein
        # deklariert ``play`` und lässt es auf null; ``insert_part`` setzt dort
        # ``profile.material.clearance`` ein (``ops.py``, Regel 7). Der
        # Bereichstest tat das nicht und fuhr damit einen Zustand, den es nie
        # gibt: beim Bolzenscharnier ein Gelenk mit einer Hundertstel Spalt,
        # das beim Drucken verschweißt. Geprüft wurde eine Geometrie, die
        # niemand bekommt.
        entered = dict(values)
        if PLAY_FIELD in entered and not entered[PLAY_FIELD]:
            entered[PLAY_FIELD] = profile.material.clearance
        declared = str(feasible(params(**entered)) or "") if feasible is not None else ""
        try:
            result: PartResult = build(params(**entered))
        except ValidationError as problem:
            if declared:
                excluded.append(RangeExclusion(dict(entered), declared[:200]))
            else:
                add(entered, str(problem))
            checked += 1
            announce(index, 4)
            if checked % 16 == 0:
                gc.collect()
            continue
        except Exception as problem:  # eine brechende Ecke ist das Ergebnis, kein Absturz
            add(entered, str(problem))
            checked += 1
            announce(index, 4)
            if checked % 16 == 0:
                gc.collect()
            continue
        if declared:
            add(
                entered,
                str(_("als nicht baubar erklärt, baut aber: {reason}")).format(reason=declared),
            )
        announce(index, 1)
        if _is_cancelled(token):
            break

        mesh = as_mesh_data(result.mesh)
        if not mesh.is_watertight:
            add(entered, str(_("nicht wasserdicht")))
        if mesh.volume <= 0.0:
            add(entered, str(_("kein Volumen")))
        if not joined_by_host and mesh.component_count != max(bodies, 1):
            # **Die erklärte Zahl, nicht die Eins.** Wer nichts deklariert,
            # bekommt ``bodies=1`` und damit genau die alte Prüfung; wer zwei
            # erklärt, muss zwei bauen — auch das ist eine Zusage, die brechen
            # kann, und ein Scharnier, das in drei Teile fällt, ist genauso
            # kaputt wie eine Rastnase, die in zwei fällt.
            add(
                entered,
                str(_("zerfällt in {found} Teile statt {declared}")).format(
                    found=mesh.component_count, declared=max(bodies, 1)
                ),
            )

        minimum = wall.minimum(entered, profile)
        measured = local_wall_thickness(mesh, token) if minimum is not None else None
        if _is_cancelled(token):
            break
        if minimum is not None:
            if measured is None:
                add(entered, str(_("Wandstärke nicht messbar")))
            elif measured < minimum - EPS_GEOM:
                add(
                    entered,
                    f"{_('dünner als druckbar')!s}: {measured:.3f} mm < {minimum:.3f} mm",
                )
        announce(index, 2)
        if _is_cancelled(token):
            break

        if mesh.is_watertight and mesh.volume > 0.0 and has_self_intersections(mesh, token):
            add(entered, str(_("Selbstdurchdringung")))
        if _is_cancelled(token):
            break
        announce(index, 3)

        gap = printable_gap(mesh, profile, cancelled=token) if bodies > 1 else None
        if _is_cancelled(token):
            break
        if bodies > 1 and gap is None and mesh.component_count > 1:
            add(
                entered,
                str(
                    _(
                        "Der Abstand zwischen den Teilkörpern ist nicht messbar. "
                        "Die Geometrie reparieren und erneut prüfen."
                    )
                ),
            )
        if (
            gap is not None
            # **``EPS_DISPLAY`` und nicht ``EPS_GEOM``**: Das hier ist eine
            # Fertigungsfrage, kein Rechenvergleich. Der gemessene Spalt fällt
            # um Bruchteile kleiner aus als der eingestellte, weil ein
            # facettierter Zylinder seine Sehne zeigt und nicht den Bogen —
            # gemessen 0,2499 bei eingestellten 0,25, und mit dem
            # Rechenepsilon meldete die Prüfung ein Scharnier, das genau
            # richtig gebaut war. Ein Hundertstel Millimeter liegt unter jeder
            # Druckauflösung; was darunter liegt, ist kein Spalt und kein
            # Fehler.
            and (gap < profile.material.clearance - EPS_DISPLAY)
        ):
            # **Der Spalt ist bei einem print-in-place-Teil die ganze Sache.**
            # Zu eng verschweißt beim Drucken, und aus zwei Körpern wird einer
            # — der Bereichstest sähe davon nichts, weil er die Geometrie vor
            # dem Drucker prüft und nicht danach. Gemessen wird gegen das
            # kalibrierte Material und nie gegen eine Zahl im Code (Regel 7).
            add(
                entered,
                str(_("Spalt {gap} mm — der Drucker legt {least} mm")).format(
                    gap=round(gap, 2), least=round(profile.material.clearance, 2)
                ),
            )

        generated_features = getattr(result, "features", {})
        names = tuple(generated_features)
        for name, feature in generated_features.items():
            if feature.id != name:
                add(
                    entered,
                    str(_("Merkmal {name}: ID {found} statt {expected}")).format(
                        name=name, found=feature.id, expected=name
                    ),
                )
            if feature.provenance != "generated":
                add(
                    entered,
                    str(_("Merkmal {name}: Herkunft {found} statt generated")).format(
                        name=name, found=feature.provenance
                    ),
                )
            if not feature.params:
                add(entered, str(_("Merkmal {name}: ohne Maße")).format(name=name))
            if features and not any(
                requirement.applies(entered)
                and (name == requirement.name or name.startswith(f"{requirement.name}_"))
                for requirement in features
            ):
                add(entered, str(_("Merkmal {name}: nicht deklariert")).format(name=name))
        for requirement in features:
            if requirement.applies(entered) and not any(
                name == requirement.name or name.startswith(f"{requirement.name}_")
                for name in names
            ):
                add(
                    entered,
                    str(_("Merkmal {name}: fehlt")).format(name=requirement.name),
                )

        checked += 1
        announce(index, 4)
        # VTK-Wrapper und native Manifold-Netze bilden Referenzzyklen. Ohne
        # periodischen Lauf sammelte die vollständige Bibliothek vor dem
        # ersten Gewinde bereits über ein Gigabyte an und wurde durch Paging
        # zwanzigmal langsamer. Die Paar- und Grenzmenge bleibt unverändert.
        if checked % 16 == 0:
            gc.collect()
    if checked < len(plan) and not failures:
        add({}, str(_("Wird abgebrochen …")))
    if progress is not None and checked == len(plan):
        progress(1.0, str(_("Bereichstest abgeschlossen")))
    report = RangeReport(checked=checked, failures=tuple(failures), excluded=tuple(excluded))
    gc.collect()
    return report


def check_part(
    spec: PartSpec,
    profile: Profile,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> RangeReport:
    """Prüft einen Registerbaustein ausschließlich nach seiner Deklaration."""
    return check(
        spec.params,
        spec.fn,
        profile,
        progress=progress,
        cancelled=cancelled,
        joined_by_host=spec.joined_by_host,
        bodies=spec.bodies,
        wall=spec.wall,
        features=spec.feature_requirements,
        feasible=spec.feasible,
    )
