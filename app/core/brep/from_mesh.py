"""Vom Dreiecksnetz zum exakten Körper — ohne Konstruktionsverlauf (Konzept P4.0).

Ein eingelesenes Netz kennt keine Flächen, nur Dreiecke. Die Erkennung
(:mod:`app.core.perceive.features`) hat für die meisten davon schon gesagt,
auf welcher Ebene, welchem Zylinder, Kegel, welcher Kugel oder welchem Ring
sie liegen — als ``SurfacePatch`` mit Träger und Originaldreiecken. Dieses
Modul macht daraus einen exakten Körper, den STEP tragen kann:

1. **Bereiche.** Jedes Dreieck bekommt genau einen Träger: den seines
   erkannten Merkmals, wenn alle drei Ecken innerhalb der Toleranz darauf
   liegen; einen benachbarten, der es ebenso trägt (die flachen Facetten am
   Fuß einer Kehle ließ die Erkennung liegen); eine Ebene aus koplanaren
   Nachbarn; oder die eigene Ebene des Dreiecks — das ist der Freiformrest,
   und er wird gezählt, nie geglättet.
2. **Ränder.** Wo zwei Bereiche aneinanderstoßen, läuft eine Kette von
   Netzkanten. Ecken sind die Punkte, an denen drei Bereiche zusammenkommen.
3. **Kanten.** Jede Ecke wird auf alle Träger gezogen, die sich dort treffen;
   jede Kette wird zur Schnittkurve ihrer zwei Träger — Strecke, Kreis oder,
   wo die Schnittkurve keine der beiden ist, eine B-Spline durch Punkte auf
   beiden Trägern. Neben einem Freiformdreieck bleibt sie eine Strecke.
4. **Flächen.** Je Bereich eine Fläche auf seinem Träger, begrenzt von seinen
   Ketten, orientiert wie das Netz (``Inside=False`` — gemessen: ``True``
   dreht einen richtig orientierten Draht auf Zylinder und Torus um).
5. **Körper.** Schale, Körper, Gültigkeit, gleichartige Nachbarflächen
   zusammengelegt (``edit.unified``) — und am Ende die Abweichung zum Netz in
   beide Richtungen gemessen.

Das Ergebnis trägt **keinen Konstruktionsverlauf**: Flächen, Kanten und
Merkmale sind da, die Schritte, mit denen jemand das Teil einmal gebaut hat,
nicht (Bauplan §42). Die Toleranz gilt den **Ecken** des Netzes — seine
Dreiecke sind Sehnen der runden Flächen und weichen um die Sehnenhöhe ab, die
das Netz beim Export bekommen hat; diese Abweichung wird gemessen und
genannt, nicht versteckt.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final, Literal

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import CancelToken, SurfacePatch, Vec3
from app.core.units import EPS_GEOM, MAX_FACET_SAG

if TYPE_CHECKING:
    from app.core.brep.kernel import Solid
    from app.core.geom.deviation import SampledDeviation
    from app.core.types import Feature, FeatureId

_log = get_logger(__name__)

CarrierKind = Literal["plane", "cylinder", "cone", "sphere", "torus"]

#: Wie weit eine Ecke des Netzes höchstens von dem Träger liegen darf, der sie
#: aufnimmt — die Vorgabe der Operation. Ein Fünftel der Sehnenhöhe, mit der
#: der exakte Kern tesselliert (``units.MAX_FACET_SAG``), und damit dieselbe
#: Zahl wie die runde Wand der Erkennung (``features.ROUND_WALL_TOLERANCE``):
#: Eine STL aus einer Konstruktion legt ihre Ecken bis auf die Rundung ihrer
#: ``float32``-Zahlen auf die Flächen (gemessen am Kundenkorpus: 0,3 µm am
#: Kragen, 3,9 µm am Nutboden des Siebhalters), und alles darüber ist Streuung
#: eines Scans oder einer neuen Vernetzung — dafür steht das Feld offen.
DEFAULT_TOLERANCE: Final = MAX_FACET_SAG / 5.0

#: Wie viele Gauß-Newton-Schritte eine Ecke höchstens bekommt, um auf alle
#: ihre Träger zu kommen. Wo sie sich schneiden, genügen drei; die Grenze ist
#: eine Arbeitsgrenze, keine Toleranz.
SNAP_STEPS: Final = 40

#: Welche Richtungen eine Ecke nicht bestimmt: Singulärwerte der
#: Normalenmatrix unter diesem Anteil des größten. Zwei Träger, die sich
#: berühren (eine Verrundung an ihrer Ebene), haben dort fast gleiche Normalen,
#: und ihre eingepassten Maße weichen um Mikrometer ab — dann schneiden sie
#: sich in **zwei** Linien links und rechts der Berührung, ``sqrt(2·R·δ)``
#: auseinander: an ``block_with_rounded_edge.stl`` 3,2 µm bei 1,7·10⁻⁶ mm
#: Maßabweichung, und die Punkte einer Kante fielen auf beide Seiten. Quer
#: zur Berührung bleibt die Ecke deshalb, wo das Netz sie hatte; entlang
#: der Normalen wird sie gezogen. 0,05 ist der Sinus von knapp drei Grad —
#: zwei Flächen, die sich flacher schneiden, bestimmen die Querlage nicht.
SNAP_RCOND: Final = 0.05

#: Wie weit eine Ecke wandern darf, um auf ihre Träger zu kommen, als
#: Vielfaches der Toleranz. Liegt sie auf jedem innerhalb der Toleranz und
#: schneiden sich die Träger unter mindestens 35 Grad, trennen sie
#: höchstens das Dreifache von ihrem Schnittpunkt. Weiter weg liegt er nur,
#: wo sich Träger streifen — und dann bestimmen sie ihn nicht: An
#: ``bottom-single.stl`` traf die Schnittgerade zweier Ebenen einen
#: eingepassten Zylinder, der an der Ecke 0,0095 mm danebenlag, unter 8 Grad;
#: die Ecke wanderte 0,067 mm die Gerade entlang, die Nachbarfacette lag
#: danach 0,008 mm daneben, und die Zylinderfläche schnitt sich selbst.
#: Dann gelten die Ebenen allein, sonst bleibt die Ecke, wo sie war, und ihre
#: Toleranz trägt die Lücke.
CORNER_REACH: Final = 3.0

#: Wie viele zusätzliche Punkte je Netzkante eine kurze Kette bekommt, bevor
#: ihre Schnittkurve bestimmt wird. Eine Kette aus einer einzigen Netzkante
#: hat nur zwei Punkte, und durch zwei Punkte geht jede Kurve.
DENSIFY_BELOW: Final = 9
DENSIFY_STEPS: Final = 4

#: Wie dicht eine Strecke oder ein Kreis an den Punkten der Kette liegen muss,
#: als Anteil der Eckentoleranz. Ein Zehntel: Eine Schnittkurve, die um die
#: halbe Toleranz von einem Kreis abweicht, ist kein Kreis, sondern eine
#: Kurve, die fast einer ist — sie wird eine B-Spline durch ihre Punkte.
CURVE_SHARE: Final = 0.1

#: Wie genau eine Ebene aus dem Netz eine Ebene ist, relativ zur größten
#: Koordinate: das Achtfache der Rundung eines ``float32``, in dem jede STL
#: ihre Ecken speichert (2⁻²³). Eine Ebene wird nicht mit der Toleranz der
#: runden Flächen gefunden — sonst legt die Zerlegung die Facetten einer
#: sanft gekrümmten Fläche zu Ebenen zusammen, die sich unter wenigen Grad
#: schneiden, und ihre Schnittgeraden liegen dann Zehntel neben den Ecken
#: (gemessen an ``top-single.stl`` aus dem Kundenordner: Ecken bis 0,056 mm
#: gezogen, 32 ebene Flächen ungültig).
PLANAR_SPAN: Final = 8.0 * 2.0**-23

#: Wie weit die Normale eines Dreiecks von der seiner Rundung abweichen darf,
#: im Bogenmaß: 30 Grad. Die Facette eines Zylinders aus acht Segmenten steht
#: um 22,5 Grad schräg zu seiner Normalen in ihrer Mitte; ein Deckel, dessen
#: Ecken auf dem Rand der Rundung liegen, um 45 (Fase) bis 90 Grad (Mantel).
FACET_TILT: Final = math.radians(30.0)

#: Wie eng das Nähen zuerst sucht, in mm. Jede Fläche baut ihre Kanten aus
#: denselben Zahlen wie ihre Nachbarin; zwei Zwillinge liegen deshalb bis auf
#: die Rundung aufeinander, und mehr als diese Enge braucht das Nähen für fast
#: alle. **Mit der Toleranz der weitesten Kante wurde es unbezahlbar:** Am
#: Rucksackhalter aus dem Kundenordner (13 841 Flächen) trug eine Sehne über
#: einer groben Rundung 0,7 mm, das Nähen suchte daraufhin mit 1,4 mm um jeden
#: Punkt und brauchte 1024 der 1062 Sekunden der ganzen Umwandlung; mit
#: 1e-4 mm 3,4 s, und zehn Kanten blieben offen. Die bekommen einen zweiten
#: Gang mit der weiten Toleranz, der nur noch sie anfasst.
SEWING_FIRST: Final = 1e-4

#: Wie viele Freiformdreiecke höchstens als ebene Einzelflächen in den
#: exakten Körper gehen. Darüber sagt die Umwandlung ab und schlägt vor, die
#: Dreiecke zu verringern: Ein STEP mit hunderttausend Dreiecksflächen öffnet
#: kein CAD-Programm flüssig, und er ist nichts, was sich dort bearbeiten
#: ließe. Gemessen, nicht geraten — siehe ``tests/test_mesh_to_exact.py``.
MAX_FREEFORM_FACES: Final = 20_000


class ConversionRefusedError(Exception):
    """Innerer Abbruch mit Grund; die Operation macht daraus die Absage mit Vorschlag."""

    def __init__(self, reason: str, **values: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.values = values


# --- Träger ----------------------------------------------------------------


def _unit(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if not math.isfinite(length) or length <= 0.0:
        raise ValueError("zero vector")
    return vector / length


def _cross(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Das Kreuzprodukt zweier einzelner Vektoren.

    ``np.cross`` ist für Stapel gebaut: an zwei Vektoren 24,5 µs, hier 1,6 µs
    (gemessen). ``top-single.stl`` rechnet 21 576 davon.
    """
    a0, a1, a2 = float(first[0]), float(first[1]), float(first[2])
    b0, b1, b2 = float(second[0]), float(second[1]), float(second[2])
    return np.array((a1 * b2 - a2 * b1, a2 * b0 - a0 * b2, a0 * b1 - a1 * b0))


def _perpendicular(axis: np.ndarray) -> np.ndarray:
    """Eine feste Querrichtung zu ``axis`` — immer dieselbe für dieselbe Achse."""
    helper = np.zeros(3)
    helper[int(np.argmin(np.abs(axis)))] = 1.0
    return _unit(_cross(axis, helper))


def _radial_units(radial: np.ndarray, rho: np.ndarray, axis: np.ndarray) -> np.ndarray:
    """Radiale Einheitsrichtungen; ein Punkt auf der Achse bekommt eine feste Querrichtung."""
    units = np.empty_like(radial)
    inside = rho > 0.0
    units[inside] = radial[inside] / rho[inside, None]
    if not inside.all():
        units[~inside] = _perpendicular(axis)
    return units


@dataclass(frozen=True, slots=True)
class Carrier:
    """Ein analytischer Träger — derselbe Vertrag wie ``SurfacePatch``.

    ``origin`` ist bei der Ebene ein Punkt der Fläche, bei Zylinder und Ring
    ein Punkt der Achse, beim Kegel die Spitze, bei der Kugel die Mitte.
    ``axis`` ist die Normale der Ebene oder die Richtung der Achse; beim Kegel
    zeigt sie von der Spitze in die Öffnung. Die Normale jedes Trägers zeigt
    wie in OpenCASCADE nach außen (von der Achse, vom Mittelpunkt, aus der
    Röhre) — so kann eine Fläche entscheiden, ob sie umgedreht werden muss.
    """

    kind: CarrierKind
    origin: tuple[float, float, float]
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    radius: float = 0.0
    tube: float = 0.0
    angle: float = 0.0

    @classmethod
    def of_patch(cls, patch: SurfacePatch) -> Carrier | None:
        """Der Träger eines geprüften ``SurfacePatch`` — oder ``None``, wenn er keiner ist."""
        params = patch.params
        try:
            if patch.kind == "plane":
                return cls("plane", _vec(params["centre"]), _dir(params["axis"]))
            if patch.kind == "cylinder":
                return cls(
                    "cylinder",
                    _vec(params["centre"]),
                    _dir(params["axis"]),
                    radius=_positive(params["radius"]),
                )
            if patch.kind == "cone":
                angle = _positive(params["half_angle"])
                if angle >= math.pi / 2.0:
                    return None
                return cls("cone", _vec(params["apex"]), _dir(params["axis"]), angle=angle)
            if patch.kind == "sphere":
                return cls("sphere", _vec(params["centre"]), radius=_positive(params["radius"]))
            if patch.kind == "torus":
                ring = _positive(params["ring_radius"])
                tube = _positive(params["tube_radius"])
                if tube >= ring:
                    return None
                return cls(
                    "torus", _vec(params["centre"]), _dir(params["axis"]), radius=ring, tube=tube
                )
        except KeyError, TypeError, ValueError:
            return None

    @property
    def curved(self) -> bool:
        return self.kind != "plane"

    def _frame(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Axialer Abstand, radialer Abstand und radiale Einheitsrichtung je Punkt."""
        axis = np.asarray(self.axis)
        offset = points - np.asarray(self.origin)
        along = offset @ axis
        radial = offset - along[:, None] * axis
        rho = np.linalg.norm(radial, axis=1)
        return along, rho, _radial_units(radial, rho, axis)

    def distances(self, points: np.ndarray) -> np.ndarray:
        """Vorzeichenbehafteter Abstand, positiv auf der Seite der äußeren Normale."""
        points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        if self.kind == "plane":
            return np.asarray((points - np.asarray(self.origin)) @ np.asarray(self.axis))
        if self.kind == "sphere":
            return np.asarray(
                np.linalg.norm(points - np.asarray(self.origin), axis=1) - self.radius
            )
        along, rho, _units = self._frame(points)
        if self.kind == "cylinder":
            return np.asarray(rho - self.radius)
        if self.kind == "cone":
            return np.asarray(rho * math.cos(self.angle) - along * math.sin(self.angle))
        return np.asarray(np.hypot(rho - self.radius, along) - self.tube)

    def normals(self, points: np.ndarray) -> np.ndarray:
        """Die äußere Einheitsnormale an der nächsten Stelle des Trägers."""
        points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        axis = np.asarray(self.axis)
        if self.kind == "plane":
            return np.broadcast_to(axis, points.shape).copy()
        if self.kind == "sphere":
            offset = points - np.asarray(self.origin)
            length = np.linalg.norm(offset, axis=1)
            return _radial_units(offset, length, np.array((0.0, 0.0, 1.0)))
        along, rho, units = self._frame(points)
        if self.kind == "cylinder":
            return units
        if self.kind == "cone":
            return math.cos(self.angle) * units - math.sin(self.angle) * axis
        # Ring: von der Mittellinie der Röhre nach außen.
        towards = (rho - self.radius)[:, None] * units + along[:, None] * axis
        length = np.linalg.norm(towards, axis=1)
        return _radial_units(towards, length, axis)

    def projected(self, points: np.ndarray) -> np.ndarray:
        """Der nächste Punkt auf dem Träger — für alle fünf Arten exakt entlang der Normale."""
        points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        return np.asarray(points - self.distances(points)[:, None] * self.normals(points))

    def same_surface(self, other: Carrier, tolerance: float) -> bool:
        """Beschreiben beide Träger dieselbe Fläche — nicht nur einen gemeinsamen Streifen?"""
        if self.kind != other.kind:
            return False
        axis, other_axis = np.asarray(self.axis), np.asarray(other.axis)
        origin, other_origin = np.asarray(self.origin), np.asarray(other.origin)
        if self.kind == "plane":
            return bool(
                float(axis @ other_axis) > 1.0 - 1e-12
                and abs(float((other_origin - origin) @ axis)) <= tolerance
            )
        if self.kind == "sphere":
            return bool(
                np.linalg.norm(origin - other_origin) <= tolerance
                and abs(self.radius - other.radius) <= tolerance
            )
        if abs(abs(float(axis @ other_axis)) - 1.0) > 1e-12:
            return False
        if self.kind == "cone" and float(axis @ other_axis) < 0.0:
            return False
        if self.kind == "cone":
            return bool(
                np.linalg.norm(origin - other_origin) <= tolerance
                and abs(self.angle - other.angle) <= 1e-12
            )
        offset = other_origin - origin
        across = offset - (offset @ axis) * axis
        if np.linalg.norm(across) > tolerance:
            return False
        if self.kind == "torus" and abs(float(offset @ axis)) > tolerance:
            return False
        return bool(
            abs(self.radius - other.radius) <= tolerance
            and abs(self.tube - other.tube) <= tolerance
        )


def _vec(value: object) -> tuple[float, float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError("not a vector")
    result = (float(value[0]), float(value[1]), float(value[2]))
    if not all(math.isfinite(item) for item in result):
        raise ValueError("not finite")
    return result


def _dir(value: object) -> tuple[float, float, float]:
    vector = _unit(np.asarray(_vec(value), dtype=np.float64))
    return (float(vector[0]), float(vector[1]), float(vector[2]))


def _positive(value: object) -> float:
    number = float(value)  # type: ignore[arg-type]
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError("not positive")
    return number


def plane_through(points: np.ndarray, normal_hint: np.ndarray) -> Carrier:
    """Die Ausgleichsebene durch Punkte, ihre Normale zur Seite des Hinweises gedreht."""
    centre = points.mean(axis=0)
    _u, _s, vectors = np.linalg.svd(points - centre, full_matrices=False)
    normal = vectors[-1]
    if float(normal @ normal_hint) < 0.0:
        normal = -normal
    normal = _unit(normal)
    return Carrier(
        "plane",
        (float(centre[0]), float(centre[1]), float(centre[2])),
        (float(normal[0]), float(normal[1]), float(normal[2])),
    )


# --- Bereiche -----------------------------------------------------------------

RegionOrigin = Literal["fitted", "grown", "planar", "facet"]


@dataclass(frozen=True, slots=True)
class Regions:
    """Die Zerlegung eines Netzes in Bereiche mit je einem Träger.

    ``of_triangle[i]`` ist der Bereich des Dreiecks ``i``. ``origin`` sagt je
    Bereich, woher sein Träger kommt: ``fitted`` aus einem erkannten Merkmal,
    ``planar`` aus koplanaren Nachbarn, ``facet`` aus dem Dreieck selbst —
    der Freiformrest. ``features`` nennt je Bereich die Merkmale, deren
    Träger er übernommen hat.
    """

    of_triangle: np.ndarray
    carriers: tuple[Carrier, ...]
    origin: tuple[RegionOrigin, ...]
    slots: tuple[int, ...]
    features: tuple[tuple[str, ...], ...]
    rejected: tuple[tuple[str, float], ...] = ()
    """Merkmale, deren Träger die Toleranz an den Ecken nicht hielt, mit dem größten Abstand."""

    @property
    def count(self) -> int:
        return len(self.carriers)

    def facet_triangles(self) -> np.ndarray:
        """Die Dreiecke des Freiformrests — je eines ist eine eigene ebene Fläche."""
        facets = np.asarray([origin == "facet" for origin in self.origin], dtype=bool)
        return np.flatnonzero(facets[self.of_triangle])


def _triangle_distances(
    carrier: Carrier, vertices: np.ndarray, faces: np.ndarray, triangles: np.ndarray
) -> np.ndarray:
    """Der größte Eckenabstand je Dreieck zu einem Träger — unendlich, wo es quer liegt.

    **Drei Ecken auf der Fläche machen noch kein Dreieck auf ihr.** Der Fächer
    eines ebenen Deckels hat alle Ecken auf dem Kreis, in dem der Deckel die
    Fase trifft — und damit auf dem Kegel der Fase. Nach Ecken allein ging er
    an sie, und die Kegelfläche aus dem Draht war nur 0,59 des Bereichs, weil
    ein Drittel davon ein Deckel war (gemessen an ``Wedge-Lock (Base).stl``,
    Normalen bis 45 Grad daneben). Eine Rundung nimmt deshalb nur Dreiecke,
    deren Normale höchstens :data:`FACET_TILT` von ihrer abweicht; eine
    Ebene hat mit ihrer engen Toleranz ohnehin keinen Spielraum.
    """
    if not len(triangles):
        return np.zeros(0)
    corners = vertices[faces[triangles]]
    distance = np.abs(carrier.distances(corners.reshape(-1, 3))).reshape(-1, 3).max(axis=1)
    if carrier.kind == "plane":
        return distance
    across = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    length = np.linalg.norm(across, axis=1)
    usable = length > 0.0
    normals = np.zeros_like(across)
    normals[usable] = across[usable] / length[usable, None]
    agreement = np.abs(np.einsum("ij,ij->i", normals, carrier.normals(corners.mean(axis=1))))
    return np.where(usable & (agreement >= math.cos(FACET_TILT)), distance, np.inf)


def _check(cancelled: CancelToken | None) -> None:
    if cancelled is not None:
        cancelled.raise_if_cancelled()


def surface_regions(
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    tolerance: float,
    *,
    cancelled: CancelToken | None = None,
) -> Regions:
    """Jedes Dreieck auf genau einen Träger — erkannte zuerst, der Rest ehrlich eben.

    ``mesh`` ist das verschweißte Netz, dessen Dreiecksnummern die Merkmale
    tragen. Ein Träger wird nur übernommen, soweit die Ecken seiner Dreiecke
    innerhalb von ``tolerance`` auf ihm liegen: Ein Dreieck, dessen Ecke
    daneben liegt, gehört nicht zu dieser Fläche, gleich was die Einpassung
    darüber sagte.
    """
    from app.core.perceive.surfaces import valid_patch

    vertices = np.asarray(mesh.raw.vertices, dtype=np.float64)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    count = len(faces)
    owner = np.full(count, -1, dtype=np.int64)
    carriers: list[Carrier] = []
    evidence: list[list[str]] = []
    origin: list[RegionOrigin] = []
    identities: dict[tuple[object, ...], int] = {}
    claims: list[tuple[int, np.ndarray]] = []
    rejected: dict[str, float] = {}
    for feature_id in sorted(features):
        _check(cancelled)
        feature = features[feature_id]
        for patch in feature.surface_patches:
            if not valid_patch(patch, face_count=count):
                continue
            carrier = Carrier.of_patch(patch)
            if carrier is None:
                continue
            identity = (carrier.kind, carrier.origin, carrier.axis, carrier.radius, carrier.tube)
            number = identities.get(identity)
            if number is None:
                number = len(carriers)
                identities[identity] = number
                carriers.append(carrier)
                evidence.append([])
                origin.append("fitted")
            if feature_id not in evidence[number]:
                evidence[number].append(feature_id)
            claims.append((number, np.asarray(patch.face_indices, dtype=np.int64)))
    # Wer ein Dreieck beansprucht, muss es tragen: Ecken auf dem Träger. Bei
    # zwei Anwärtern gewinnt der nähere — nie der zuerst genannte.
    best = np.full(count, np.inf)
    for number, triangles in claims:
        _check(cancelled)
        distance = _triangle_distances(carriers[number], vertices, faces, triangles)
        better = (distance < best[triangles]) & (distance <= tolerance)
        owner[triangles[better]] = number
        best[triangles[better]] = distance[better]
        loose = distance > tolerance
        if loose.any():
            for feature_id in evidence[number]:
                rejected[feature_id] = max(rejected.get(feature_id, 0.0), float(distance.max()))
    flat = planar_tolerance(vertices, tolerance)
    owner, best = _grown(owner, best, carriers, vertices, faces, mesh, tolerance, flat, cancelled)
    # Was keiner nimmt: koplanare Nachbarn werden eine Ebene, der Rest je
    # Dreieck seine eigene.
    rest = np.flatnonzero(owner < 0)
    for group in _planar_groups(rest, vertices, faces, mesh, flat, cancelled):
        number = len(carriers)
        normal_hint = np.asarray(mesh.raw.face_normals[group[0]], dtype=np.float64)
        carriers.append(plane_through(vertices[faces[group]].reshape(-1, 3), normal_hint))
        evidence.append([])
        origin.append("planar" if len(group) > 1 else "facet")
        owner[group] = number
    slots = np.asarray(mesh.slots, dtype=np.int64) if mesh.slots else np.zeros(count, np.int64)
    return _split_components(
        owner, slots, carriers, origin, evidence, mesh, tuple(sorted(rejected.items())), cancelled
    )


def planar_tolerance(vertices: np.ndarray, tolerance: float) -> float:
    """Wie weit eine Ecke neben einer Ebene aus dem Netz liegen darf (:data:`PLANAR_SPAN`)."""
    reach = float(np.abs(vertices).max()) if len(vertices) else 0.0
    return min(tolerance, max(EPS_GEOM, PLANAR_SPAN * reach))


def _grown(
    owner: np.ndarray,
    best: np.ndarray,
    carriers: Sequence[Carrier],
    vertices: np.ndarray,
    faces: np.ndarray,
    mesh: MeshData,
    tolerance: float,
    flat: float,
    cancelled: CancelToken | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Freie Nachbardreiecke gehen an den Träger, auf dem ihre Ecken liegen.

    Die Erkennung lässt an einer tangentialen Kehle die flachsten Facetten
    liegen — ihre Normalen unterscheiden sich von der Ebene daneben kaum, und
    sie gehören weder sichtbar zur Rundung noch zur Fläche. Liegen ihre drei
    Ecken auf dem Ring, sind sie Ring: gemessen an ``post_with_fillet.stl``
    290 Dreiecke, die sonst 290 ebene Einzelflächen geworden wären.
    Mehrere Anwärter: der nähere gewinnt. Eine Ebene wächst nur mit der
    Genauigkeit einer Ebene (``flat``), eine Rundung mit der Toleranz.
    """
    pairs = np.asarray(mesh.raw.face_adjacency, dtype=np.int64)
    if not len(pairs) or not carriers:
        return owner, best
    both = np.concatenate([pairs, pairs[:, ::-1]])
    while True:
        _check(cancelled)
        free = owner[both[:, 1]] < 0
        held = owner[both[:, 0]] >= 0
        frontier = both[free & held]
        if not len(frontier):
            return owner, best
        candidate = frontier[:, 1]
        number = owner[frontier[:, 0]]
        order = np.lexsort((candidate, number))
        candidate, number = candidate[order], number[order]
        distance = np.empty(len(candidate))
        starts = np.flatnonzero(np.r_[True, number[1:] != number[:-1]])
        stops = np.r_[starts[1:], len(number)]
        for start, stop in zip(starts, stops, strict=True):
            distance[start:stop] = _triangle_distances(
                carriers[int(number[start])], vertices, faces, candidate[start:stop]
            )
        allowed = np.asarray(
            [flat if carriers[int(item)].kind == "plane" else tolerance for item in number]
        )
        fits = distance <= allowed
        if not fits.any():
            return owner, best
        candidate, number, distance = candidate[fits], number[fits], distance[fits]
        # Je Dreieck der nächste Träger, bei Gleichstand der kleinere Name.
        order = np.lexsort((number, distance, candidate))
        candidate, number, distance = candidate[order], number[order], distance[order]
        first = np.r_[True, candidate[1:] != candidate[:-1]]
        owner[candidate[first]] = number[first]
        best[candidate[first]] = distance[first]


def _planar_groups(
    rest: np.ndarray,
    vertices: np.ndarray,
    faces: np.ndarray,
    mesh: MeshData,
    tolerance: float,
    cancelled: CancelToken | None,
) -> list[np.ndarray]:
    """Zusammenhängende Dreiecke, die innerhalb der Toleranz in einer Ebene liegen.

    Gewachsen wird von jedem noch freien Dreieck aus in Nummernfolge; ein
    Nachbar kommt dazu, wenn seine Ecken auf der Ebene des Anfangsdreiecks
    liegen. Das ist langsamer als eine Zusammenhangsrechnung über
    Normalenwinkel und dafür an einem sanft gekrümmten Streifen richtig: Eine
    Kette fast gleicher Normalen ist noch keine Ebene.
    """
    if not len(rest):
        return []
    free = np.zeros(len(faces), dtype=bool)
    free[rest] = True
    pairs = np.asarray(mesh.raw.face_adjacency, dtype=np.int64)
    usable = free[pairs[:, 0]] & free[pairs[:, 1]]
    pairs = pairs[usable]
    neighbours: dict[int, list[int]] = defaultdict(list)
    for first, second in pairs.tolist():
        neighbours[first].append(second)
        neighbours[second].append(first)
    normals = np.asarray(mesh.raw.face_normals, dtype=np.float64)
    groups: list[np.ndarray] = []
    taken = np.zeros(len(faces), dtype=bool)
    for position, seed in enumerate(rest.tolist()):
        if position % 2048 == 0:
            _check(cancelled)
        if taken[seed]:
            continue
        taken[seed] = True
        corners = vertices[faces[seed]]
        normal = normals[seed]
        centre = corners.mean(axis=0)
        group = [seed]
        stack = list(neighbours.get(seed, ()))
        while stack:
            other = stack.pop()
            if taken[other]:
                continue
            offsets = (vertices[faces[other]] - centre) @ normal
            if np.abs(offsets).max() > tolerance or float(normals[other] @ normal) <= 0.0:
                continue
            taken[other] = True
            group.append(other)
            stack.extend(neighbours.get(other, ()))
        groups.append(np.asarray(sorted(group), dtype=np.int64))
    return groups


def _split_components(
    owner: np.ndarray,
    slots: np.ndarray,
    carriers: Sequence[Carrier],
    origin: Sequence[RegionOrigin],
    evidence: Sequence[Sequence[str]],
    mesh: MeshData,
    rejected: tuple[tuple[str, float], ...],
    cancelled: CancelToken | None,
) -> Regions:
    """Ein Bereich ist zusammenhängend und einfarbig — sonst sind es mehrere.

    Zwei Bohrungen derselben Achse und desselben Durchmessers teilen einen
    Träger und sind trotzdem zwei Flächen; eine Fläche mit zwei Filamenten
    behält ihre Farbgrenze als Kante (P2.2).
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    _check(cancelled)
    count = len(owner)
    pairs = np.asarray(mesh.raw.face_adjacency, dtype=np.int64)
    same = (owner[pairs[:, 0]] == owner[pairs[:, 1]]) & (slots[pairs[:, 0]] == slots[pairs[:, 1]])
    kept = pairs[same]
    graph = coo_matrix((np.ones(len(kept)), (kept[:, 0], kept[:, 1])), shape=(count, count)).tocsr()
    _number, labels = connected_components(graph, directed=False)
    # Nummern in der Reihenfolge des kleinsten Dreiecks — dieselbe Zerlegung
    # gibt dieselben Nummern, gleich wie scipy zählt.
    first_triangle = np.full(int(labels.max()) + 1 if count else 0, count, dtype=np.int64)
    np.minimum.at(first_triangle, labels, np.arange(count))
    order = np.argsort(first_triangle, kind="stable")
    renumber = np.empty_like(order)
    renumber[order] = np.arange(len(order))
    regions = renumber[labels]
    representative = first_triangle[order]
    return Regions(
        of_triangle=regions,
        carriers=tuple(carriers[int(owner[index])] for index in representative),
        origin=tuple(origin[int(owner[index])] for index in representative),
        slots=tuple(int(slots[index]) for index in representative),
        features=tuple(tuple(evidence[int(owner[index])]) for index in representative),
        rejected=rejected,
    )


# --- Nachbessern der Träger -------------------------------------------------------

#: Wie schief eine Achse gegen eine Nachbarebene oder eine Nachbarachse stehen
#: darf, damit die Nachbesserung sie gleichrichtet — der Sinus des Winkels,
#: dieselbe Grenze wie beim Ziehen der Ecken (knapp drei Grad). Übernommen
#: wird die Gleichrichtung nur, wenn der Bereich danach weiter in der
#: Toleranz liegt; eine schiefe Absicht bleibt schief.
ALIGN_SINE: Final = SNAP_RCOND

#: Reihenfolge der Verlässlichkeit: Eine Ebene aus exakt koplanaren Dreiecken
#: gibt nie nach, ein Zylinder aus vielen Punkten eher nicht, Kegel, Ring und
#: Kugel richten sich nach ihnen.
_RANK: Final = {"plane": 0, "cylinder": 1, "cone": 2, "torus": 3, "sphere": 4}


def _circle2d(points: np.ndarray) -> tuple[np.ndarray, float] | None:
    """Kreis durch ebene Punkte: Kåsa zentriert, dann nach Abständen verfeinert."""
    if len(points) < 3:
        return None
    middle = points.mean(axis=0)
    flat = points - middle
    matrix = np.column_stack([flat, np.ones(len(flat))])
    right = (flat**2).sum(axis=1)
    solution, *_rest = np.linalg.lstsq(matrix, right, rcond=None)
    centre = solution[:2] / 2.0
    if not float(solution[2] + centre @ centre) > 0.0:
        return None
    for _ in range(30):
        offset = flat - centre
        distance = np.linalg.norm(offset, axis=1)
        if np.any(distance <= 0.0):
            return None
        radius = float(distance.mean())
        jacobian = np.column_stack([-offset / distance[:, None], -np.ones(len(flat))])
        update, *_rest = np.linalg.lstsq(jacobian, radius - distance, rcond=None)
        centre = centre + update[:2]
        if float(np.abs(update).max()) <= 1e-15 * max(1.0, radius):
            break
    radius = float(np.linalg.norm(flat - centre, axis=1).mean())
    return centre + middle, radius


def _refit_with_axis(
    carrier: Carrier, points: np.ndarray, axis: np.ndarray, line: np.ndarray | None
) -> Carrier | None:
    """Denselben Träger mit vorgegebener Achsrichtung neu einpassen — oder auch Achslage.

    ``line`` ist ein Punkt der vorgegebenen Achse, wenn auch die Lage fest ist
    (gleiche Achse wie ein Nachbar). Sonst wird die Lage quer zur Achse neu
    bestimmt. Eingepasst wird an den Ecken des Bereichs — denselben Punkten,
    an denen die Toleranz danach geprüft wird.
    """
    across = _perpendicular(axis)
    second = _cross(axis, across)
    heights = points @ axis
    flat = np.column_stack([points @ across, points @ second])
    if line is not None:
        centre2 = np.array((float(line @ across), float(line @ second)))
        radii = np.linalg.norm(flat - centre2, axis=1)
    else:
        circle = _circle2d(flat) if carrier.kind == "cylinder" else None
        centre2 = (
            circle[0]
            if circle is not None
            else np.array(
                (
                    float(np.asarray(carrier.origin) @ across),
                    float(np.asarray(carrier.origin) @ second),
                )
            )
        )
        radii = np.linalg.norm(flat - centre2, axis=1)

    def at(height: float) -> tuple[float, float, float]:
        point = centre2[0] * across + centre2[1] * second + height * axis
        return (float(point[0]), float(point[1]), float(point[2]))

    direction = (float(axis[0]), float(axis[1]), float(axis[2]))
    if carrier.kind == "cylinder":
        radius = float(radii.mean())
        if radius <= 0.0:
            return None
        return Carrier("cylinder", at(float(heights.mean())), direction, radius=radius)
    if carrier.kind == "cone":
        # Radius wächst linear mit der Höhe: r = k·h + b, Spitze bei r = 0.
        slope, offset = np.polyfit(heights, radii, 1)
        if abs(slope) <= 1e-9:
            return None
        apex_height = -offset / slope
        angle = math.atan(abs(slope))
        if not 0.0 < angle < math.pi / 2.0:
            return None
        pointing = direction if slope > 0.0 else (-direction[0], -direction[1], -direction[2])
        return Carrier("cone", at(float(apex_height)), pointing, angle=angle)
    if carrier.kind == "torus":
        meridian = _circle2d(np.column_stack([radii, heights]))
        if meridian is None:
            return None
        (ring, height), tube = meridian
        if not 0.0 < tube < ring:
            return None
        return Carrier("torus", at(float(height)), direction, radius=float(ring), tube=float(tube))
    return None


def _holds(
    carrier: Carrier,
    vertices: np.ndarray,
    faces: np.ndarray,
    triangles: np.ndarray,
    tolerance: float,
) -> bool:
    return bool(np.all(_triangle_distances(carrier, vertices, faces, triangles) <= tolerance))


def regularized(
    mesh: MeshData, regions: Regions, tolerance: float, *, cancelled: CancelToken | None = None
) -> tuple[Regions, int]:
    """Was fast gleich gerichtet, gleichachsig oder tangential ist, wird es genau.

    Die Einpassungen der Erkennung stehen je für sich: Der Kegel der Fase an
    einer senkrechten Bohrung lag 1,8 Grad schief, die Verrundung zwischen
    zwei Wänden 3 µm neben ihnen (gemessen an ``Wedge-Lock (Base).stl`` und
    ``2x1-tray.stl``). Dann gibt es keinen exakten Kreis zwischen ihnen und
    keine Berührung — die Kante wird eine B-Spline, und wo zwei Kurven an
    einer Ecke tangential zusammenlaufen sollten, schneiden sie sich. Die
    Konstruktion, aus der das Netz stammt, hatte diese Beziehungen; die
    Nachbesserung stellt sie wieder her, und zwar nur, wo der Bereich danach
    weiter in der Toleranz liegt:

    1. Achsen gleichgerichtet — parallel zur Normalen einer Nachbarebene, in
       ihr liegend oder parallel zu einer verlässlicheren Nachbarachse;
    2. gleiche Achsen zusammengelegt;
    3. Berührungen genau gemacht — Zylinder an Ebene, Ring an Ebene und an
       Zylinder, Kugel an Ebene.

    Ebenen geben nie nach. Zurück kommt die Zerlegung mit den neuen Trägern
    und wie viele sich geändert haben.
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=np.float64)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    areas = np.asarray(mesh.raw.area_faces, dtype=np.float64)
    order = np.argsort(regions.of_triangle, kind="stable")
    bounds = np.searchsorted(regions.of_triangle[order], np.arange(regions.count + 1))
    members = [order[bounds[index] : bounds[index + 1]] for index in range(regions.count)]
    region_area = np.array([float(areas[triangles].sum()) for triangles in members])
    pairs = np.asarray(mesh.raw.face_adjacency, dtype=np.int64)
    first, second = regions.of_triangle[pairs[:, 0]], regions.of_triangle[pairs[:, 1]]
    different = first != second
    stride = regions.count + 1
    codes = np.unique(
        np.minimum(first[different], second[different]) * stride
        + np.maximum(first[different], second[different])
    )
    neighbours: dict[int, list[int]] = defaultdict(list)
    for code in codes.tolist():
        neighbours[code // stride].append(code % stride)
        neighbours[code % stride].append(code // stride)
    carriers = list(regions.carriers)
    usable = [regions.origin[index] != "facet" for index in range(regions.count)]
    corners = [vertices[np.unique(faces[triangles])] for triangles in members]
    changed = 0

    def ranked(index: int) -> tuple[int, float]:
        return (_RANK[carriers[index].kind], -region_area[index])

    def attempt(index: int, candidate: Carrier | None) -> bool:
        nonlocal changed
        if candidate is None or candidate == carriers[index]:
            return False
        if not _holds(candidate, vertices, faces, members[index], tolerance):
            return False
        carriers[index] = candidate
        changed += 1
        return True

    axial = [
        index
        for index in sorted(range(regions.count), key=ranked)
        if usable[index] and carriers[index].kind in ("cylinder", "cone", "torus")
    ]
    fixed_axes: dict[int, np.ndarray] = {}
    # 1 — Richtungen.
    for position, index in enumerate(axial):
        if position % 64 == 0:
            _check(cancelled)
        carrier = carriers[index]
        axis = np.asarray(carrier.axis)
        planes = [
            (other, np.asarray(carriers[other].axis))
            for other in neighbours[index]
            if usable[other] and carriers[other].kind == "plane"
        ]
        target: np.ndarray | None = None
        parallel = [
            (region_area[other], normal)
            for other, normal in planes
            if float(np.linalg.norm(_cross(axis, normal))) <= ALIGN_SINE
        ]
        if parallel:
            normal = max(parallel, key=lambda item: item[0])[1]
            target = normal if float(normal @ axis) >= 0.0 else -normal
        else:
            lying = [normal for _other, normal in planes if abs(float(axis @ normal)) <= ALIGN_SINE]
            crossing = None
            for one in range(len(lying)):
                for two in range(one + 1, len(lying)):
                    cross = _cross(lying[one], lying[two])
                    if float(np.linalg.norm(cross)) > ALIGN_SINE:
                        crossing = _unit(cross)
                        break
                if crossing is not None:
                    break
            if crossing is not None:
                target = crossing if float(crossing @ axis) >= 0.0 else -crossing
            elif lying:
                projected = axis - float(axis @ lying[0]) * lying[0]
                target = _unit(projected)
            else:
                for other in neighbours[index]:
                    known = fixed_axes.get(other)
                    if (
                        known is not None
                        and float(np.linalg.norm(_cross(axis, known))) <= ALIGN_SINE
                    ):
                        target = known if float(known @ axis) >= 0.0 else -known
                        break
        if target is not None and float(np.linalg.norm(target - axis)) > 1e-15:
            attempt(index, _refit_with_axis(carrier, corners[index], target, None))
        fixed_axes[index] = np.asarray(carriers[index].axis)
    # 2 — Gleiche Achsen.
    for position, index in enumerate(axial):
        if position % 64 == 0:
            _check(cancelled)
        carrier = carriers[index]
        axis = np.asarray(carrier.axis)
        for other in sorted(neighbours[index], key=ranked):
            if other not in fixed_axes or ranked(other) >= ranked(index):
                continue
            partner = carriers[other]
            partner_axis = np.asarray(partner.axis)
            if float(np.linalg.norm(_cross(axis, partner_axis))) > 1e-12:
                continue
            offset = np.asarray(carrier.origin) - np.asarray(partner.origin)
            across = offset - float(offset @ partner_axis) * partner_axis
            if float(np.linalg.norm(across)) > tolerance:
                continue
            if float(np.linalg.norm(across)) > 1e-15:
                attempt(
                    index,
                    _refit_with_axis(
                        carrier, corners[index], partner_axis, np.asarray(partner.origin)
                    ),
                )
            break
    # 3 — Berührungen.
    for position, index in enumerate(
        axial
        + [
            index
            for index in range(regions.count)
            if usable[index] and carriers[index].kind == "sphere"
        ]
    ):
        if position % 64 == 0:
            _check(cancelled)
        attempt(index, _tangent(index, carriers, neighbours[index], usable, tolerance))
    return replace(regions, carriers=tuple(carriers)), changed


def _tangent(
    index: int,
    carriers: Sequence[Carrier],
    neighbours: Sequence[int],
    usable: Sequence[bool],
    tolerance: float,
) -> Carrier | None:
    """Denselben Träger so verschoben, dass er seine Nachbarn genau berührt.

    Zylinder an Ebenen: Die Achse rückt quer, bis ihr Abstand zu jeder
    berührten Ebene der Radius ist (zwei Wände einer Verrundung legen sie fest).
    Ring an Ebene quer zur Achse: die Mitte entlang der Achse. Ring an einem
    Zylinder derselben Achse: der Ringradius. Kugel an Ebene: die Mitte längs
    der Normalen. Berührt heißt: bis auf die Toleranz — mehr ist ein Abstand,
    den jemand gebaut hat.
    """
    carrier = carriers[index]
    origin = np.asarray(carrier.origin)
    axis = np.asarray(carrier.axis)
    planes = [
        carriers[other] for other in neighbours if usable[other] and carriers[other].kind == "plane"
    ]
    if carrier.kind == "cylinder":
        rows, values = [], []
        for plane in planes:
            normal = np.asarray(plane.axis)
            if abs(float(normal @ axis)) > 1e-12:
                continue
            distance = float((origin - np.asarray(plane.origin)) @ normal)
            if abs(abs(distance) - carrier.radius) > tolerance:
                continue
            side = 1.0 if distance >= 0.0 else -1.0
            rows.append(normal)
            values.append(float(np.asarray(plane.origin) @ normal) + side * carrier.radius)
        if not rows:
            return None
        matrix = np.asarray(rows)
        shift, *_rest = np.linalg.lstsq(matrix, np.asarray(values) - matrix @ origin, rcond=None)
        shift = shift - float(shift @ axis) * axis
        moved = origin + shift
        return replace(carrier, origin=(float(moved[0]), float(moved[1]), float(moved[2])))
    if carrier.kind == "torus":
        candidate = carrier
        for plane in planes:
            normal = np.asarray(plane.axis)
            if float(np.linalg.norm(_cross(normal, axis))) > 1e-12:
                continue
            height = float((origin - np.asarray(plane.origin)) @ normal)
            if abs(abs(height) - carrier.tube) > tolerance:
                continue
            side = 1.0 if height >= 0.0 else -1.0
            moved = origin + (side * carrier.tube - height) * normal
            candidate = replace(
                candidate, origin=(float(moved[0]), float(moved[1]), float(moved[2]))
            )
            origin = moved
            break
        for other in neighbours:
            partner = carriers[other]
            if not usable[other] or partner.kind != "cylinder":
                continue
            partner_axis = np.asarray(partner.axis)
            if float(np.linalg.norm(_cross(partner_axis, axis))) > 1e-12:
                continue
            offset = np.asarray(partner.origin) - origin
            if float(np.linalg.norm(offset - float(offset @ axis) * axis)) > tolerance:
                continue
            inner = partner.radius + carrier.tube
            outer = partner.radius - carrier.tube
            ring = min((inner, outer), key=lambda value: abs(value - carrier.radius))
            if abs(ring - carrier.radius) <= tolerance and ring > carrier.tube:
                candidate = replace(candidate, radius=float(ring))
            break
        return candidate if candidate != carrier else None
    if carrier.kind == "sphere":
        for plane in planes:
            normal = np.asarray(plane.axis)
            distance = float((origin - np.asarray(plane.origin)) @ normal)
            if abs(abs(distance) - carrier.radius) > tolerance:
                continue
            side = 1.0 if distance >= 0.0 else -1.0
            moved = origin + (side * carrier.radius - distance) * normal
            return replace(carrier, origin=(float(moved[0]), float(moved[1]), float(moved[2])))
    return None


# --- Ränder -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Chain:
    """Eine Folge von Netzkanten zwischen zwei Bereichen, von Ecke zu Ecke.

    ``vertices`` läuft so, dass ``left`` links liegt, von außen gesehen —
    dieselbe Richtung, in der ``left`` seinen Rand umläuft. ``closed``: ein
    Rand ohne Ecke, etwa der Kreis einer Bohrung in einer Deckfläche; sein
    erster und letzter Punkt sind dieselbe Netzecke.
    """

    vertices: tuple[int, ...]
    left: int
    right: int
    closed: bool


@dataclass(frozen=True, slots=True)
class Boundaries:
    """Alle Ketten und je Bereich seine Ränder als Folgen ``(Kette, vorwärts)``."""

    chains: tuple[Chain, ...]
    loops: tuple[tuple[tuple[tuple[int, bool], ...], ...], ...]
    corners: np.ndarray
    """Welche Netzecken Ecken des Körpers werden."""


@dataclass(frozen=True, slots=True, eq=False)
class ConversionReference:
    """Das Netz, aus dem ein Körper umgewandelt wurde, und wie weit jedes Dreieck von ihm lag.

    ``own_mm`` ist je Netzdreieck der größte Abstand seiner Stichproben zum
    eigenen Träger (bei einem Freiformdreieck die Verschiebung seiner Ecken).
    Liegt ein Punkt weiter vom Körper als davon, ist das keine Sehnenhöhe,
    sondern eine Stelle, an der das Netz etwas hat, was der Körper nicht hat
    (:func:`_mesh_to_body`). Die Karte „Formabweichung“ liest dieselbe Zahl.
    """

    mesh: MeshData
    own_mm: np.ndarray
    tolerance: float
    """Die erlaubte Abweichung, mit der umgewandelt wurde."""


class OpenSurfaceError(Exception):
    """Das Netz ist nicht geschlossen oder nicht einheitlich orientiert."""


def boundaries(
    mesh: MeshData, regions: Regions, *, cancelled: CancelToken | None = None
) -> Boundaries:
    """Die Ränder aller Bereiche als Ketten zwischen Ecken.

    Setzt ein geschlossenes, einheitlich orientiertes Netz voraus: Jede
    gerichtete Kante kommt genau einmal vor, ihre Gegenrichtung auch. Sonst
    ``OpenSurfaceError`` — die Operation sagt dann, dass vorher repariert
    werden muss.
    """
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    corners_count = len(mesh.raw.vertices)
    count = len(faces)
    origin = faces.reshape(-1)
    target = faces[:, [1, 2, 0]].reshape(-1)
    keys = origin * corners_count + target
    order = np.argsort(keys, kind="stable")
    ordered = keys[order]
    if len(ordered) > 1 and bool(np.any(ordered[1:] == ordered[:-1])):
        raise OpenSurfaceError
    twin_keys = target * corners_count + origin
    position = np.searchsorted(ordered, twin_keys)
    position = np.minimum(position, len(ordered) - 1)
    if not bool(np.all(ordered[position] == twin_keys)):
        raise OpenSurfaceError
    twin = order[position]
    triangle_of = np.arange(3 * count) // 3
    region = regions.of_triangle[triangle_of]
    boundary = region != region[twin]
    following = np.arange(3 * count) - np.arange(3 * count) % 3
    following = following + (np.arange(3 * count) % 3 + 1) % 3
    edges = np.flatnonzero(boundary)
    _check(cancelled)
    # Die nächste Randkante links um die Ecke — über die Dreiecke desselben
    # Bereichs gedreht, bis eine Randkante kommt. Eine Ecke, an der der
    # Bereich sich selbst berührt, wird so richtig durchlaufen.
    after = following[edges]
    pending = ~boundary[after]
    while pending.any():
        after[pending] = following[twin[after[pending]]]
        pending[pending] = ~boundary[after[pending]]
    step = np.full(3 * count, -1, dtype=np.int64)
    step[edges] = after
    # Ecken: drei oder mehr Bereiche, eine Berührung des Bereichs mit sich
    # selbst, oder eine Ecke eines Freiformdreiecks (dessen Rand bleibt
    # Strecke für Strecke).
    pairs = np.unique(origin * (regions.count + 1) + region)
    around = np.bincount(pairs // (regions.count + 1), minlength=corners_count)
    corner = around >= 3
    leaving = np.unique(origin[edges] * (regions.count + 1) + region[edges], return_counts=True)
    corner[leaving[0][leaving[1] > 1] // (regions.count + 1)] = True
    facet = np.asarray([kind == "facet" for kind in regions.origin], dtype=bool)
    facet_corners = faces[facet[regions.of_triangle]].reshape(-1)
    corner[facet_corners] = True
    edge_code = np.minimum(origin, target) * corners_count + np.maximum(origin, target)

    chains: list[Chain] = []
    chain_of_edge: dict[int, int] = {}
    loops: list[list[tuple[tuple[int, bool], ...]]] = [[] for _ in range(regions.count)]
    seen = np.zeros(3 * count, dtype=bool)
    for position_, start in enumerate(edges.tolist()):
        if position_ % 4096 == 0:
            _check(cancelled)
        if seen[start]:
            continue
        cycle = [start]
        seen[start] = True
        walk = int(step[start])
        while walk != start:
            if seen[walk]:
                raise OpenSurfaceError
            seen[walk] = True
            cycle.append(walk)
            walk = int(step[walk])
        own = int(region[start])
        starts = [index for index, edge in enumerate(cycle) if corner[origin[edge]]]
        if not starts:
            # Ein Rand ohne Ecke: angefangen wird an der kleinsten Netzecke,
            # damit beide Seiten dieselbe Stelle wählen.
            anchor = min(range(len(cycle)), key=lambda index: int(origin[cycle[index]]))
            cycle = cycle[anchor:] + cycle[:anchor]
            pieces = [cycle]
            closed = True
        else:
            cycle = cycle[starts[0] :] + cycle[: starts[0]]
            cut = [index for index, edge in enumerate(cycle) if corner[origin[edge]]]
            pieces = [cycle[a:b] for a, b in zip(cut, [*cut[1:], len(cycle)], strict=True)]
            closed = False
        entries: list[tuple[int, bool]] = []
        for piece in pieces:
            code = int(edge_code[piece[0]])
            known = chain_of_edge.get(code)
            if known is None:
                vertices = (*(int(origin[edge]) for edge in piece), int(target[piece[-1]]))
                known = len(chains)
                chains.append(Chain(vertices, own, int(region[twin[piece[0]]]), closed))
                for edge in piece:
                    chain_of_edge[int(edge_code[edge])] = known
            entries.append((known, chains[known].left == own))
        loops[own].append(tuple(entries))
    return Boundaries(tuple(chains), tuple(tuple(loop) for loop in loops), corner)


# --- Ecken auf die Träger -----------------------------------------------------


def snapped(
    points: np.ndarray, carriers: Sequence[Carrier], *, steps: int = SNAP_STEPS
) -> np.ndarray:
    """Punkte auf die gemeinsame Stelle aller ``carriers`` gezogen.

    Gauß-Newton mit der Pseudoinversen je Punkt: Jeder Schritt ist die
    kürzeste Verschiebung, die alle Abstände in erster Ordnung aufhebt. Wo
    Träger sich schneiden, konvergiert das quadratisch. Richtungen, die sie
    nicht bestimmen (:data:`SNAP_RCOND`), fasst der Schritt nicht an — an
    einer Berührung bleibt der Punkt quer zu ihr stehen.
    """
    current = np.asarray(points, dtype=np.float64).reshape(-1, 3).copy()
    if not carriers or not len(current):
        return current
    for _ in range(steps):
        residual = np.stack([carrier.distances(current) for carrier in carriers], axis=1)
        gradient = np.stack([carrier.normals(current) for carrier in carriers], axis=1)
        step = -np.einsum("nij,nj->ni", np.linalg.pinv(gradient, rtol=SNAP_RCOND), residual)
        current = current + step
        size = float(np.abs(step).max())
        if not math.isfinite(size):
            raise ValueError("snapping diverged")
        if size <= 1e-15 * max(1.0, float(np.abs(current).max())):
            break
    return current


# --- Kettenkurven ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Curve:
    """Die Gestalt einer Kette: Strecke(n), Kreis(bogen) oder B-Spline durch Punkte."""

    kind: Literal["polyline", "line", "circle", "bspline", "occ"]
    points: np.ndarray
    """Die Punkte der Kette auf beiden Trägern — bei ``polyline`` die Ecken der Strecken."""
    centre: np.ndarray | None = None
    normal: np.ndarray | None = None
    radius: float = 0.0
    deviation: float = 0.0
    """Wie weit die Kurve von den Punkten und den zwei Trägern abliegt, in mm."""
    geometry: Any = None
    """Bei ``occ`` die Schnittkurve aus OpenCASCADE, zwischen ``first`` und ``last``."""
    first: float = 0.0
    last: float = 0.0


def _fit_line(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    centre = points.mean(axis=0)
    _u, _s, vectors = np.linalg.svd(points - centre, full_matrices=False)
    direction = vectors[0]
    offset = points - centre
    across = offset - np.outer(offset @ direction, direction)
    return centre, direction, float(np.linalg.norm(across, axis=1).max())


def _fit_circle(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float] | None:
    """Kreis durch Punkte: Ebene, dann Kreis in der Ebene. ``None`` ohne Ebene oder Kreis."""
    if len(points) < 3:
        return None
    centre = points.mean(axis=0)
    _u, singular, vectors = np.linalg.svd(points - centre, full_matrices=False)
    if singular[1] <= 1e-12 * max(1.0, singular[0]):
        return None
    normal = vectors[2]
    first, second = vectors[0], vectors[1]
    flat = np.stack([(points - centre) @ first, (points - centre) @ second], axis=1)
    planar = float(np.abs((points - centre) @ normal).max())
    # Kåsa in zentrierten Koordinaten, dann eine Verfeinerung nach Abständen.
    matrix = np.column_stack([flat, np.ones(len(flat))])
    right = (flat**2).sum(axis=1)
    try:
        solution, *_rest = np.linalg.lstsq(matrix, right, rcond=None)
    except np.linalg.LinAlgError:
        return None
    middle = solution[:2] / 2.0
    radius_squared = float(solution[2] + middle @ middle)
    if not radius_squared > 0.0:
        return None
    for _ in range(20):
        offset = flat - middle
        distance = np.linalg.norm(offset, axis=1)
        if np.any(distance <= 0.0):
            return None
        radius = float(distance.mean())
        jacobian = np.column_stack([-offset / distance[:, None], -np.ones(len(flat))])
        residual = distance - radius
        update, *_rest = np.linalg.lstsq(jacobian, -residual, rcond=None)
        middle = middle + update[:2]
        if float(np.abs(update).max()) <= 1e-15 * max(1.0, radius):
            break
    offset = flat - middle
    radius = float(np.linalg.norm(offset, axis=1).mean())
    spread = float(np.abs(np.linalg.norm(offset, axis=1) - radius).max())
    world = centre + middle[0] * first + middle[1] * second
    return world, normal, radius, max(spread, planar)


def _surface_gap(carriers: Sequence[Carrier], points: np.ndarray) -> float:
    if not len(points):
        return 0.0
    return float(max(np.abs(carrier.distances(points)).max() for carrier in carriers))


def _arc_samples(
    centre: np.ndarray, normal: np.ndarray, radius: float, points: np.ndarray
) -> np.ndarray:
    """Punkte auf dem Kreisbogen zwischen aufeinanderfolgenden Kettenpunkten."""
    first = _unit(points[0] - centre)
    second = _cross(normal, first)
    offset = points - centre
    angles = np.unwrap(np.arctan2(offset @ second, offset @ first))
    middle = (angles[1:] + angles[:-1]) / 2.0
    return np.asarray(
        centre
        + radius * np.cos(middle)[:, None] * first
        + radius * np.sin(middle)[:, None] * second
    )


@dataclass(frozen=True, slots=True)
class _Trace:
    """Ein Träger im ebenen Schnitt: Gerade durch ``point`` mit ``direction`` oder Kreis."""

    kind: Literal["line", "circle"]
    point: np.ndarray
    direction: np.ndarray | None = None
    radius: float = 0.0


def _axis_line(carrier: Carrier) -> tuple[np.ndarray, np.ndarray] | None:
    if carrier.kind in ("cylinder", "cone", "torus"):
        return np.asarray(carrier.origin), np.asarray(carrier.axis)
    return None


def _parallel(first: np.ndarray, second: np.ndarray, sine: float) -> bool:
    return float(np.linalg.norm(_cross(first, second))) <= sine


def _on_line(point: np.ndarray, line: tuple[np.ndarray, np.ndarray], limit: float) -> bool:
    offset = point - line[0]
    across = offset - (offset @ line[1]) * line[1]
    return float(np.linalg.norm(across)) <= limit


def _common_axis(
    first: Carrier, second: Carrier, limit: float, sine: float
) -> tuple[np.ndarray, np.ndarray] | None:
    """Die Achse, um die beide Träger drehsymmetrisch sind — ihre Schnitte sind dann Kreise."""
    for one, other in ((first, second), (second, first)):
        line = _axis_line(one)
        if line is None:
            continue
        other_line = _axis_line(other)
        if other_line is not None:
            if _parallel(line[1], other_line[1], sine) and _on_line(other_line[0], line, limit):
                return line
            return None
        if other.kind == "plane":
            return line if _parallel(line[1], np.asarray(other.axis), sine) else None
        if other.kind == "sphere":
            return line if _on_line(np.asarray(other.origin), line, limit) else None
    kinds = {first.kind, second.kind}
    if kinds == {"plane", "sphere"}:
        plane, ball = (first, second) if first.kind == "plane" else (second, first)
        return np.asarray(ball.origin), np.asarray(plane.axis)
    if kinds == {"sphere"}:
        offset = np.asarray(second.origin) - np.asarray(first.origin)
        if float(np.linalg.norm(offset)) > limit:
            return np.asarray(first.origin), _unit(offset)
    return None


def _common_direction(first: Carrier, second: Carrier, sine: float) -> np.ndarray | None:
    """Die Richtung, längs der beide Träger unverändert bleiben — ihre Schnitte sind Geraden."""
    kinds = (first.kind, second.kind)
    axis_one, axis_two = np.asarray(first.axis), np.asarray(second.axis)
    if kinds == ("plane", "plane"):
        direction = _cross(axis_one, axis_two)
        return None if float(np.linalg.norm(direction)) <= sine else _unit(direction)
    if set(kinds) == {"plane", "cylinder"}:
        normal, axis = (axis_one, axis_two) if kinds[0] == "plane" else (axis_two, axis_one)
        return axis if abs(float(normal @ axis)) <= sine else None
    if kinds == ("cylinder", "cylinder") and _parallel(axis_one, axis_two, sine):
        return axis_one
    return None


def _meridian(carrier: Carrier, origin: np.ndarray, axis: np.ndarray) -> _Trace | None:
    """Der Träger im Halbschnitt durch die Achse, in ``(Radius, Höhe)``."""
    height = float((np.asarray(carrier.origin) - origin) @ axis)
    if carrier.kind == "plane":
        return _Trace("line", np.array((0.0, height)), np.array((1.0, 0.0)))
    if carrier.kind == "cylinder":
        return _Trace("line", np.array((carrier.radius, 0.0)), np.array((0.0, 1.0)))
    if carrier.kind == "cone":
        sign = 1.0 if float(np.asarray(carrier.axis) @ axis) >= 0.0 else -1.0
        direction = np.array((math.sin(carrier.angle), sign * math.cos(carrier.angle)))
        return _Trace("line", np.array((0.0, height)), direction)
    if carrier.kind == "sphere":
        return _Trace("circle", np.array((0.0, height)), radius=carrier.radius)
    return _Trace("circle", np.array((carrier.radius, height)), radius=carrier.tube)


def _section(
    carrier: Carrier, origin: np.ndarray, frame: tuple[np.ndarray, np.ndarray, np.ndarray]
) -> _Trace | None:
    """Der Träger im Querschnitt senkrecht zur gemeinsamen Richtung ``frame[2]``."""
    first, second, direction = frame
    offset = np.asarray(carrier.origin) - origin
    point = np.array((float(offset @ first), float(offset @ second)))
    if carrier.kind == "plane":
        along = _cross(direction, np.asarray(carrier.axis))
        trace = np.array((float(along @ first), float(along @ second)))
        if float(np.linalg.norm(trace)) <= 0.0:
            return None
        return _Trace("line", point, _unit(trace))
    if carrier.kind == "cylinder":
        return _Trace("circle", point, radius=carrier.radius)
    return None


def _cross2(first: np.ndarray, second: np.ndarray) -> float:
    return float(first[0] * second[1] - first[1] * second[0])


def _meetings(one: _Trace, two: _Trace, gap: float) -> list[tuple[np.ndarray, bool]]:
    """Wo sich zwei Spuren treffen — und, wo sie sich bis auf ``gap`` berühren, auch dort.

    Zwei eingepasste Träger, die im Original tangential ineinander übergehen,
    liegen um Mikrometer daneben und schneiden sich dann zweimal dicht
    nebeneinander oder gar nicht; die Kante ist dann die Stelle der größten
    Annäherung, mittig zwischen beiden (``True`` in der Rückgabe). **Beide
    Äste bleiben trotzdem Kandidaten**: Die Sehnenebene einer groben
    Zylinderfacette liegt auch nur um die Sehnenhöhe neben dem Zylinder, und
    ihre Kante ist einer der zwei Äste, nicht die Mitte dazwischen (gemessen
    an ``top-single.stl``: die Mitte lag 0,25 mm neben der Kette). Welcher
    Kandidat gilt, entscheiden die Punkte der Kette.
    """
    if one.kind == "circle" and two.kind == "line":
        one, two = two, one
    found: list[tuple[np.ndarray, bool]] = []
    if one.kind == "line" and two.kind == "line":
        assert one.direction is not None and two.direction is not None
        determinant = _cross2(one.direction, two.direction)
        if abs(determinant) > 1e-12:
            step = _cross2(two.point - one.point, two.direction) / determinant
            found.append((one.point + step * one.direction, False))
        return found
    if one.kind == "line":
        assert one.direction is not None
        foot = one.point + float((two.point - one.point) @ one.direction) * one.direction
        away = float(np.linalg.norm(two.point - foot))
        if away < two.radius:
            half = math.sqrt(two.radius**2 - away**2)
            found.extend(
                ((foot + half * one.direction, False), (foot - half * one.direction, False))
            )
        if abs(away - two.radius) <= gap and away > 0.0:
            touch = two.point + (foot - two.point) / away * two.radius
            found.append(((foot + touch) / 2.0, True))
        return found
    offset = two.point - one.point
    distance = float(np.linalg.norm(offset))
    if distance <= 1e-12:
        return found
    unit = offset / distance
    if abs(one.radius - two.radius) < distance < one.radius + two.radius:
        along = (distance**2 + one.radius**2 - two.radius**2) / (2.0 * distance)
        height = math.sqrt(max(one.radius**2 - along**2, 0.0))
        base = one.point + along * unit
        across = np.array((-unit[1], unit[0]))
        found.extend(((base + height * across, False), (base - height * across, False)))
    if abs(distance - (one.radius + two.radius)) <= gap:
        found.append(
            (((one.point + one.radius * unit) + (two.point - two.radius * unit)) / 2.0, True)
        )
    if abs(distance - abs(one.radius - two.radius)) <= gap:
        sign = 1.0 if one.radius >= two.radius else -1.0
        found.append(
            (
                ((one.point + sign * one.radius * unit) + (two.point + sign * two.radius * unit))
                / 2.0,
                True,
            )
        )
    return found


def _reach(
    carriers: Sequence[Carrier], point: np.ndarray, contact: bool, tolerance: float
) -> float | None:
    """Wie weit die Punkte einer Kette von ihrer Schnittkurve abliegen dürfen — oder ``None``.

    Eine Netzecke liegt innerhalb der Toleranz auf beiden Trägern; schneiden
    sie sich unter dem Winkel t, liegt sie bis zu ``tol / sin t`` neben ihrer
    Schnittkurve. Die Enden einer Kette wandern aber höchstens
    :data:`CORNER_REACH` mal die Toleranz — eine Kurve, die weiter weg liegt,
    erreichen sie nicht, und dieselbe Grenze gilt deshalb hier. An
    ``bottom-single.stl`` streifte eine Ebene einen Zylinder unter 5,2 Grad;
    die Schnittellipse lag 0,040 und 0,065 mm neben den zwei Punkten der
    Kette und wurde angenommen, solange ``3·tol / sin t`` die Grenze war. Die
    Ecken blieben stehen, und ihre Toleranz wuchs auf 0,098 mm. Streifen sich
    die Träger flacher als :data:`SNAP_RCOND`, bestimmen sie keine Kurve: Ihr
    Schnitt wandert mit jedem Mikrometer Maßabweichung.

    Eine Berührung bekommt dieselbe Grenze. Gemessen an sieben Dateien: Wo
    zwei Flächen im Original tangential ineinander übergehen, liegt die Kette
    des Netzes höchstens 0,2 µm neben der Berührkurve (``post_with_fillet``,
    ``2x1-tray``, ``bottom-single``: 3,7·10⁻⁷ bis 1,8·10⁻⁴ mm). Wo sie 0,04
    und 0,25 mm daneben lag (``Wedge-Lock (Top)``, ``top-single``), war die
    Ebene eine Facette, die den Zylinder nur fast berührt — die Kante gehört
    dann an die Kette und nicht an die Berührung.
    """
    if not contact:
        normals = [carrier.normals(point[None, :])[0] for carrier in carriers]
        sine = float(np.linalg.norm(_cross(normals[0], normals[1])))
        if sine < SNAP_RCOND:
            return None
    return CORNER_REACH * tolerance


def _plane_line(
    points: np.ndarray, first: Carrier, second: Carrier, tolerance: float, *, closed: bool
) -> Curve | None:
    """Die Schnittgerade zweier Ebenen, geschlossen gerechnet — derselbe Befund wie der
    allgemeine Weg über den Querschnitt, ohne ihn.

    Zwei Ebenen sind der häufigste Fall überhaupt: am Besenhalter aus dem
    Kundenordner 12 148 ebene Streifen einer facettierten Rundung, und der
    allgemeine Weg über Achse, Querschnitt und Treffpunkt kostete je Kette
    0,35 ms. Dieselben Grenzen: flacher als :data:`SNAP_RCOND` keine Gerade,
    weiter als :func:`_reach` neben der Kette keine.
    """
    if closed or not len(points):
        return None
    normal_one, normal_two = np.asarray(first.axis), np.asarray(second.axis)
    direction = _cross(normal_one, normal_two)
    sine = float(np.linalg.norm(direction))
    if sine < SNAP_RCOND:
        return None
    direction = direction / sine
    middle = points.mean(axis=0)
    system = np.array((normal_one, normal_two, direction))
    right = np.array(
        (
            float(normal_one @ np.asarray(first.origin)),
            float(normal_two @ np.asarray(second.origin)),
            float(direction @ middle),
        )
    )
    through = np.linalg.solve(system, right)
    offset = points - through
    along = offset @ direction
    spread = float(np.linalg.norm(offset - np.outer(along, direction), axis=1).max())
    if spread > CORNER_REACH * tolerance:
        return None
    samples = through + np.outer((along[1:] + along[:-1]) / 2.0, direction)
    return Curve(
        "line",
        points,
        centre=through,
        normal=direction,
        deviation=_surface_gap((first, second), np.concatenate([samples, through[None, :]])),
    )


def structural_curve(
    points: np.ndarray, carriers: Sequence[Carrier], tolerance: float, *, closed: bool
) -> Curve | None:
    """Die Schnittkurve aus der Gestalt der Träger, nicht aus den Punkten.

    Zwei Träger, die um **eine** Achse drehsymmetrisch sind (Ebene quer zur
    Achse, Zylinder, Kegel, Kugel und Ring um dieselbe), schneiden sich in
    Kreisen um diese Achse; zwei, die längs **einer** Richtung gleich bleiben
    (Ebenen, Zylinder mit dieser Achse), in Geraden längs dieser Richtung. Im
    Halbschnitt beziehungsweise Querschnitt sind beide Träger Geraden oder
    Kreise, und ihr Treffpunkt — oder ihre Berührung — ist exakt. So bleibt
    der Kreis einer Kehle an ihrer Ebene ein Kreis, auch wo die Punkte der
    Kette quer zur Berührung um Hundertstel streuen. ``None``, wo die Träger
    keine solche gemeinsame Gestalt haben.
    """
    first, second = carriers
    if first.kind == "plane" and second.kind == "plane":
        return _plane_line(points, first, second, tolerance, closed=closed)
    limit = max(EPS_GEOM, CURVE_SHARE * tolerance)
    extent = float(np.ptp(points, axis=0).max()) if len(points) else 0.0
    sine = limit / max(extent, 1.0)
    axis = _common_axis(first, second, limit, sine)
    if axis is not None:
        origin, direction = axis
        traces = (_meridian(first, origin, direction), _meridian(second, origin, direction))
        if traces[0] is None or traces[1] is None:
            return None
        offset = points - origin
        heights = offset @ direction
        radii = np.linalg.norm(offset - np.outer(heights, direction), axis=1)
        candidates = [
            (float(np.hypot(radii - hit[0], heights - hit[1]).max()), hit, contact)
            for hit, contact in _meetings(traces[0], traces[1], tolerance)
            if hit[0] > limit
        ]
        if not candidates:
            return None
        spread, hit, contact = min(candidates, key=lambda item: item[0])
        on_curve = origin + hit[1] * direction + hit[0] * _perpendicular(direction)
        reach = _reach(carriers, on_curve, contact, tolerance)
        if reach is None or spread > reach:
            return None
        centre = origin + hit[1] * direction
        samples = _arc_samples(centre, direction, float(hit[0]), points)
        return Curve(
            "circle",
            points,
            centre=centre,
            normal=direction,
            radius=float(hit[0]),
            deviation=_surface_gap(carriers, samples) if len(samples) else 0.0,
        )
    along = _common_direction(first, second, sine)
    if along is None or closed:
        return None
    origin = points.mean(axis=0)
    across = _perpendicular(along)
    frame = (across, _cross(along, across), along)
    traces = (_section(first, origin, frame), _section(second, origin, frame))
    if traces[0] is None or traces[1] is None:
        return None
    options = []
    for hit, contact in _meetings(traces[0], traces[1], tolerance):
        through = origin + hit[0] * frame[0] + hit[1] * frame[1]
        offset = points - through
        spread = float(np.linalg.norm(offset - np.outer(offset @ along, along), axis=1).max())
        options.append((spread, through, contact))
    if not options:
        return None
    spread, through, contact = min(options, key=lambda item: item[0])
    offset = points - through
    reach = _reach(carriers, through, contact, tolerance)
    if reach is None or spread > reach:
        return None
    parameters = offset @ along
    samples = through + np.outer((parameters[1:] + parameters[:-1]) / 2.0, along)
    return Curve(
        "line",
        points,
        centre=through,
        normal=along,
        deviation=_surface_gap(carriers, np.concatenate([samples, through[None, :]])),
    )


def _plain_surface(carrier: Carrier) -> Any:
    """Der Träger als unbegrenzte OpenCASCADE-Fläche, ohne Rücksicht auf einen Bereich."""
    from OCP.Geom import (
        Geom_ConicalSurface,
        Geom_CylindricalSurface,
        Geom_Plane,
        Geom_SphericalSurface,
        Geom_ToroidalSurface,
    )
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt

    origin = np.asarray(carrier.origin)
    axis = np.asarray(carrier.axis)
    frame = gp_Ax3(gp_Pnt(*map(float, origin)), gp_Dir(*map(float, axis)))
    if carrier.kind == "plane":
        return Geom_Plane(frame)
    if carrier.kind == "cylinder":
        return Geom_CylindricalSurface(frame, carrier.radius)
    if carrier.kind == "cone":
        shifted = origin + axis
        return Geom_ConicalSurface(
            gp_Ax3(gp_Pnt(*map(float, shifted)), gp_Dir(*map(float, axis))),
            carrier.angle,
            math.tan(carrier.angle),
        )
    if carrier.kind == "sphere":
        return Geom_SphericalSurface(frame, carrier.radius)
    return Geom_ToroidalSurface(frame, carrier.radius, carrier.tube)


def _curve_parameters(curve: Any, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Parameter und Abstand jedes Punkts auf einer OpenCASCADE-Kurve."""
    from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
    from OCP.gp import gp_Pnt

    parameters = np.empty(len(points))
    distances = np.empty(len(points))
    for position, point in enumerate(points):
        projection = GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float, point)), curve)
        if projection.NbPoints() == 0:
            parameters[position] = np.nan
            distances[position] = np.inf
            continue
        parameters[position] = projection.LowerDistanceParameter()
        distances[position] = projection.LowerDistance()
    return parameters, distances


def intersection_curve(
    points: np.ndarray, carriers: Sequence[Carrier], tolerance: float, *, closed: bool
) -> Curve | None:
    """Die Schnittkurve zweier Träger aus OpenCASCADE — exakt, wo sie ein Kegelschnitt ist.

    Für die Paare, die :func:`structural_curve` nicht kennt: eine Ebene schräg
    durch einen Zylinder (Ellipse), durch einen Kegel (Kegelschnitt), zwei
    sich kreuzende Zylinder. ``GeomAPI_IntSS`` rechnet Ebene und Quadrik
    analytisch; wo es nur eine Näherung hat, ist es seine B-Spline. Von
    mehreren Ästen gilt der, an dem die Punkte der Kette liegen. Eine B-Spline
    durch die Kettenpunkte war an ``Wedge-Lock (Base).stl`` nahe ihrer Ecke
    über die tangential anschließende Gerade hinausgeschwungen, und der Draht
    der Ebene schnitt sich selbst.
    """
    from OCP.Geom import Geom_TrimmedCurve
    from OCP.GeomAPI import GeomAPI_IntSS

    try:
        found = GeomAPI_IntSS(_plain_surface(carriers[0]), _plain_surface(carriers[1]), 1e-7)
    except Exception:
        return None
    if not found.IsDone() or found.NbLines() == 0:
        return None
    best: tuple[float, Any, np.ndarray] | None = None
    for number in range(1, found.NbLines() + 1):
        curve = found.Line(number)
        if isinstance(curve, Geom_TrimmedCurve) and curve.BasisCurve().IsPeriodic():
            curve = curve.BasisCurve()
        parameters, distances = _curve_parameters(curve, points)
        spread = float(distances.max())
        if best is None or spread < best[0]:
            best = (spread, curve, parameters)
    if best is None or not np.all(np.isfinite(best[2])):
        return None
    spread, curve, parameters = best
    return _occ_curve(curve, parameters, spread, points, carriers, tolerance, closed=closed)


def _occ_curve(
    curve: Any,
    parameters: np.ndarray,
    spread: float,
    points: np.ndarray,
    carriers: Sequence[Carrier],
    tolerance: float,
    *,
    closed: bool,
) -> Curve | None:
    """Eine Schnittkurve aus OpenCASCADE, auf die Kette zugeschnitten — oder ``None``."""
    reference = curve.Value(float(parameters[len(parameters) // 2]))
    middle = np.array((reference.X(), reference.Y(), reference.Z()))
    reach = _reach(carriers, middle, False, tolerance)
    if reach is None or spread > reach:
        return None
    arranged = _arranged(curve, parameters, closed=closed, gap=0.1 * tolerance)
    if arranged is None:
        return None
    curve, first, last, seam = arranged
    if not _follows(curve, first, last, points, spread):
        return None
    samples = np.array(
        [
            (point.X(), point.Y(), point.Z())
            for point in (curve.Value(float(value)) for value in np.linspace(first, last, 17))
        ]
    )
    return Curve(
        "occ",
        points,
        deviation=max(_surface_gap(carriers, samples), seam),
        geometry=curve,
        first=first,
        last=last,
    )


def _refitted(
    curve: Curve,
    points: np.ndarray,
    carriers: Sequence[Carrier],
    tolerance: float,
    *,
    closed: bool,
) -> Curve | None:
    """Dieselbe Schnittkurve, auf die endgültigen Ecken der Kette neu zugeschnitten."""
    parameters, distances = _curve_parameters(curve.geometry, points)
    if not np.all(np.isfinite(parameters)):
        return None
    found = _occ_curve(
        curve.geometry,
        parameters,
        float(distances.max()),
        points,
        carriers,
        tolerance,
        closed=closed,
    )
    if found is None:
        return None
    return replace(found, deviation=max(found.deviation, curve.deviation))


def _arranged(
    curve: Any, parameters: np.ndarray, *, closed: bool, gap: float
) -> tuple[Any, float, float, float] | None:
    """Die Kurve in Kettenrichtung und der Bereich, den die Kette abdeckt — oder ``None``.

    Die Parameter der Kettenpunkte müssen in einer Richtung laufen. Über den
    Anfang einer geschlossenen Kurve darf die Kette hinweg: Eine periodische
    (Kreis, Ellipse) nimmt das mit. Eine geschlossene B-Spline — so liefert
    ``GeomAPI_IntSS`` den Schnitt eines Zylinders mit einem schräg stehenden
    Kegel — wird an ihrer Naht zusammengesetzt, damit sie dort beginnt, wo
    die Kette beginnt (:func:`_rotated`). Ohne das lief die Kante an
    ``Wedge-Lock (Base).stl`` den langen Weg um den Schnitt herum: 36,6 mm
    statt 16,8 mm, und beide Flächen daran wurden ungültig.

    Zurück kommen Kurve, Anfang, Ende und die Lücke an der zusammengesetzten
    Naht (0, wo keine war).
    """
    start, end = float(curve.FirstParameter()), float(curve.LastParameter())
    periodic = bool(curve.IsPeriodic())
    span = float(curve.Period()) if periodic else end - start
    seam = 0.0
    if not periodic:
        if not (np.isfinite(span) and abs(start) < 1e9 and abs(end) < 1e9):
            span = math.inf
        else:
            seam = float(curve.Value(start).Distance(curve.Value(end)))
    loop = periodic or (np.isfinite(span) and seam <= gap)
    if closed and not loop:
        return None
    steps = np.diff(parameters)
    if loop:
        steps = (steps + span / 2.0) % span - span / 2.0
    total = float(steps.sum())
    if total < 0.0:
        parameters = np.array([curve.ReversedParameter(float(value)) for value in parameters])
        curve = curve.Reversed()
        steps = -steps
        total = -total
    if steps.size and float(steps.min()) < -1e-6 * total:
        return None
    first = float(parameters[0])
    last = first + (span if closed else total)
    if not last > first:
        return None
    if periodic:
        return curve, first, last, 0.0
    if last <= end + 1e-12 * span:
        return curve, first, min(last, end), 0.0
    if first >= end - 1e-12 * span:
        first, last = first - span, last - span
        if last <= end:
            return curve, first, last, seam
    rotated = _rotated(curve, first, last - span, gap)
    if rotated is None:
        return None
    return rotated, float(rotated.FirstParameter()), float(rotated.LastParameter()), seam


def _rotated(curve: Any, first: float, last: float, gap: float) -> Any | None:
    """Eine geschlossene, nicht periodische Kurve von ``first`` über ihre Naht bis ``last``."""
    from OCP.Geom import Geom_TrimmedCurve
    from OCP.GeomConvert import GeomConvert_CompCurveToBSplineCurve

    start, end = float(curve.FirstParameter()), float(curve.LastParameter())
    small = 1e-12 * (end - start)
    joined = None
    for low, high in ((first, end), (start, last)):
        if high - low <= small:
            continue
        piece = Geom_TrimmedCurve(curve, low, high)
        if joined is None:
            joined = GeomConvert_CompCurveToBSplineCurve(piece)
        # Hinten anhängen: Bei einer geschlossenen Kette passen beide Enden,
        # und ohne diese Angabe setzt die Bindung das Stück nach vorn.
        elif not joined.Add(piece, max(gap, EPS_GEOM), True):
            return None
    return None if joined is None else joined.BSplineCurve()


def _follows(curve: Any, first: float, last: float, points: np.ndarray, spread: float) -> bool:
    """Ob die Kurve zwischen ``first`` und ``last`` der Kette folgt, statt auszuholen.

    Die Punkte einer Kette liegen auf der Kurve; das sagt nicht, dass die
    Kurve dazwischen bei ihnen bleibt. An ``top-single.stl`` schnitt eine
    Ebene den Zylinder unter 3,8° — die Schnittellipse hat dort 531 mm
    Halbachse und an ihrem Scheitel 0,03 mm Krümmungsradius. Beide Punkte
    lagen 0,016 mm neben ihr, auf zwei Seiten des Scheitels: 0,5 mm Kette,
    2,4 mm Kante. Ein Bogen ist höchstens so viel länger als seine Sehnen,
    wie ein Netz ihn grob abtastet; ein Viertel lässt über 120° je Kante zu.
    """
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAdaptor import GeomAdaptor_Curve

    chords = float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
    try:
        length = float(GCPnts_AbscissaPoint.Length_s(GeomAdaptor_Curve(curve), first, last))
    except Exception:
        return False
    return length <= 1.25 * (chords + 2.0 * spread * max(1, len(points) - 1))


def chain_curve(
    points: np.ndarray, carriers: Sequence[Carrier], tolerance: float, *, closed: bool
) -> Curve:
    """Die Gestalt der Schnittkurve zweier Träger durch die gezogenen Kettenpunkte.

    Zuerst aus der Gestalt der Träger (:func:`structural_curve`). Sonst aus
    den Punkten: Strecke, wo alle auf einer Geraden liegen und die Gerade auf
    beiden Trägern; Kreis, wo sie auf einem Kreis liegen und der Kreis auf
    beiden; sonst eine B-Spline durch die Punkte. „Auf" heißt: innerhalb von
    ``CURVE_SHARE`` der Toleranz, gemessen auch **zwischen** den Punkten —
    eine Sehne zwischen zwei Punkten eines Kreises liegt auf keinem Träger.
    """
    structural = structural_curve(points, carriers, tolerance, closed=closed)
    if structural is not None:
        return structural
    return fitted_curve(points, carriers, tolerance, closed=closed)


def fitted_curve(
    points: np.ndarray, carriers: Sequence[Carrier], tolerance: float, *, closed: bool
) -> Curve:
    """Strecke, Kreis oder B-Spline aus Punkten, die auf beiden Trägern liegen."""
    limit = max(EPS_GEOM, CURVE_SHARE * tolerance)
    if not closed and len(points) >= 2:
        centre, direction, spread = _fit_line(points)
        middles = (points[1:] + points[:-1]) / 2.0
        if spread <= limit and _surface_gap(carriers, middles) <= limit:
            deviation = max(spread, _surface_gap(carriers, points))
            return Curve("line", points, centre=centre, normal=direction, deviation=deviation)
    circle = _fit_circle(points[:-1] if closed else points)
    if circle is not None:
        centre, normal, radius, spread = circle
        between = _arc_samples(centre, normal, radius, points)
        gap = _surface_gap(carriers, between)
        if spread <= limit and gap <= limit:
            return Curve(
                "circle",
                points,
                centre=centre,
                normal=normal,
                radius=radius,
                deviation=max(spread, gap, _surface_gap(carriers, points)),
            )
    return Curve("bspline", points, deviation=_surface_gap(carriers, points))


def densified(points: np.ndarray, carriers: Sequence[Carrier], steps: int) -> np.ndarray:
    """Zwischen je zwei Punkten ``steps`` weitere, auf beide Träger gezogen."""
    if len(points) < 2 or steps <= 0:
        return points
    fractions = np.arange(1, steps + 1) / (steps + 1)
    start, stop = points[:-1], points[1:]
    between = start[:, None, :] + fractions[None, :, None] * (stop - start)[:, None, :]
    between = snapped(between.reshape(-1, 3), carriers).reshape(len(start), steps, 3)
    merged = np.concatenate([start[:, None, :], between], axis=1).reshape(-1, 3)
    return np.concatenate([merged, points[-1:]], axis=0)


# --- Bauen ---------------------------------------------------------------------


class _RegionFailedError(Exception):
    """Eine Fläche ließ sich nicht gültig bauen — ihr Bereich geht als Dreiecke ein."""

    def __init__(self, regions: Sequence[int]) -> None:
        super().__init__(tuple(regions))
        self.regions = tuple(regions)


@dataclass(frozen=True, slots=True)
class _RegionShape:
    """Was eine Fläche über ihren Bereich wissen muss: Lage, Normale, Größe."""

    corners: np.ndarray
    normal: np.ndarray
    sample: np.ndarray
    sample_normal: np.ndarray
    area: float


def _region_shapes(mesh: MeshData, regions: Regions) -> list[_RegionShape]:
    """Je Bereich seine Ecken, die flächengewichtete Normale und ein Probedreieck."""
    vertices = np.asarray(mesh.raw.vertices, dtype=np.float64)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    normals = np.asarray(mesh.raw.face_normals, dtype=np.float64)
    areas = np.asarray(mesh.raw.area_faces, dtype=np.float64)
    order = np.argsort(regions.of_triangle, kind="stable")
    bounds = np.searchsorted(regions.of_triangle[order], np.arange(regions.count + 1))
    shapes: list[_RegionShape] = []
    for index in range(regions.count):
        members = order[bounds[index] : bounds[index + 1]]
        weights = areas[members]
        weighted = (normals[members] * weights[:, None]).sum(axis=0)
        largest = int(members[int(np.argmax(weights))])
        shapes.append(
            _RegionShape(
                corners=vertices[np.unique(faces[members])],
                normal=weighted,
                sample=vertices[faces[largest]].mean(axis=0),
                sample_normal=normals[largest],
                area=float(weights.sum()),
            )
        )
    return shapes


def _seam_direction(carrier: Carrier, corners: np.ndarray) -> np.ndarray:
    """Die Richtung, in die die Naht des Trägers zeigt — vom Bereich weg.

    Eine periodische Fläche hat bei ``u = 0`` eine Naht. Liegt sie mitten im
    Bereich, bekommt ein Rand zwei Parameterstücke; gegenüber der Mitte des
    Bereichs liegt sie nur dort, wo der Bereich ganz herumreicht, und dann
    braucht er sie ohnehin.
    """
    axis = np.asarray(carrier.axis)
    _along, rho, units = carrier._frame(corners)
    mean = (units * np.maximum(rho, 0.0)[:, None]).sum(axis=0)
    mean = mean - (mean @ axis) * axis
    if np.linalg.norm(mean) <= 1e-9 * max(1.0, float(rho.sum())):
        return _perpendicular(axis)
    return -_unit(mean)


def _occ_surface(carrier: Carrier, shape: _RegionShape) -> tuple[Any, bool]:
    """Die OpenCASCADE-Fläche des Trägers und ob sie gegen das Netz umzudrehen ist."""
    from OCP.Geom import (
        Geom_ConicalSurface,
        Geom_CylindricalSurface,
        Geom_Plane,
        Geom_SphericalSurface,
        Geom_ToroidalSurface,
    )
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt

    def point(vector: np.ndarray) -> Any:
        return gp_Pnt(float(vector[0]), float(vector[1]), float(vector[2]))

    def direction(vector: np.ndarray) -> Any:
        return gp_Dir(float(vector[0]), float(vector[1]), float(vector[2]))

    axis = np.asarray(carrier.axis)
    origin = np.asarray(carrier.origin)
    if carrier.kind == "plane":
        frame = gp_Ax3(point(origin), direction(axis), direction(_perpendicular(axis)))
        surface: Any = Geom_Plane(frame)
    elif carrier.kind == "sphere":
        mean = shape.normal
        if np.linalg.norm(mean) <= 1e-9 * max(1.0, shape.area):
            mean = np.array((1.0, 0.0, 0.0))
        away = _unit(mean)
        pole = _perpendicular(away)
        surface = Geom_SphericalSurface(
            gp_Ax3(point(origin), direction(pole), direction(-away)), carrier.radius
        )
    else:
        seam = _seam_direction(carrier, shape.corners)
        if carrier.kind == "cylinder":
            centre = shape.corners.mean(axis=0)
            location = origin + ((centre - origin) @ axis) * axis
            surface = Geom_CylindricalSurface(
                gp_Ax3(point(location), direction(axis), direction(seam)), carrier.radius
            )
        elif carrier.kind == "cone":
            height = float(((shape.corners - origin) @ axis).mean())
            if height <= 0.0:
                raise ValueError("cone region behind its apex")
            location = origin + height * axis
            surface = Geom_ConicalSurface(
                gp_Ax3(point(location), direction(axis), direction(seam)),
                carrier.angle,
                height * math.tan(carrier.angle),
            )
        else:
            surface = Geom_ToroidalSurface(
                gp_Ax3(point(origin), direction(axis), direction(seam)),
                carrier.radius,
                carrier.tube,
            )
    natural = carrier.normals(shape.sample[None, :])[0]
    return surface, bool(float(natural @ shape.sample_normal) < 0.0)


def _chain_carriers(chain: Chain, regions: Regions) -> tuple[Carrier, ...] | None:
    """Die zwei Träger einer Kette — oder ``None``, wo sie keine Schnittkurve bestimmen.

    Neben einem Freiformdreieck ist die Kante eine Strecke dieses Dreiecks.
    Zwei Bereiche auf derselben Fläche (verschiedene Filamente) haben keine
    Schnittkurve; ihre Grenze ist die Linie der Netzkanten.
    """
    left, right = regions.carriers[chain.left], regions.carriers[chain.right]
    if "facet" in (regions.origin[chain.left], regions.origin[chain.right]):
        return None
    if left.same_surface(right, EPS_GEOM):
        return None
    return (left, right)


def _vertex_positions(
    mesh: MeshData,
    regions: Regions,
    bounds: Boundaries,
    tolerance: float,
    cancelled: CancelToken | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Jede Randecke auf alle Träger gezogen, die sich an ihr treffen.

    Ebenen einzelner Freiformdreiecke zählen nicht: Sie entstehen erst aus den
    gezogenen Ecken. Zurück kommen die Lagen aller Netzecken (unberührt, wo
    keine Kette läuft) und je Ecke, wie weit sie gezogen wurde. Weiter als
    :data:`CORNER_REACH` mal die Toleranz wandert keine: Dann gelten die
    Ebenen unter ihren Trägern allein, und wo auch das zu weit führt, bleibt
    sie stehen.
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=np.float64)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    positions = vertices.copy()
    moved = np.zeros(len(vertices))
    on_chain = np.zeros(len(vertices), dtype=bool)
    for chain in bounds.chains:
        on_chain[list(chain.vertices)] = True
    analytic = np.asarray([kind != "facet" for kind in regions.origin], dtype=bool)
    corner_region = np.repeat(regions.of_triangle, 3)
    corner_vertex = faces.reshape(-1)
    keep = on_chain[corner_vertex] & analytic[corner_region]
    stride = regions.count + 1
    codes = np.unique(corner_vertex[keep] * stride + corner_region[keep])
    around: dict[int, list[int]] = defaultdict(list)
    for code in codes.tolist():
        around[code // stride].append(code % stride)
    groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for vertex, members_here in around.items():
        # Zwei Bereiche auf demselben Träger sind eine Bedingung, nicht zwei.
        distinct: list[int] = []
        for member in members_here:
            carrier = regions.carriers[member]
            if not any(carrier == regions.carriers[other] for other in distinct):
                distinct.append(member)
        groups[tuple(distinct)].append(vertex)
    limit = CORNER_REACH * tolerance
    for position, (members, group) in enumerate(sorted(groups.items())):
        if position % 256 == 0:
            _check(cancelled)
        indices = np.asarray(group, dtype=np.int64)
        carriers = [regions.carriers[member] for member in members]
        try:
            target = snapped(vertices[indices], carriers)
        except ValueError:
            continue
        shift = np.linalg.norm(target - vertices[indices], axis=1)
        far = ~(np.isfinite(shift) & (shift <= limit))
        flat = [carrier for carrier in carriers if carrier.kind == "plane"]
        if far.any() and flat and len(flat) < len(carriers):
            try:
                retry = snapped(vertices[indices[far]], flat)
            except ValueError:
                retry = None
            if retry is not None:
                target[far] = retry
                shift[far] = np.linalg.norm(retry - vertices[indices[far]], axis=1)
        good = np.isfinite(shift) & (shift <= limit)
        positions[indices[good]] = target[good]
        moved[indices[good]] = shift[good]
    return positions, moved


@dataclass(frozen=True, slots=True)
class _Plan:
    """Die numerische Beschreibung aller Kanten, bevor OpenCASCADE sie sieht."""

    curves: tuple[Curve, ...]
    vertex_tolerance: Mapping[int, float]
    edge_tolerance: tuple[float, ...]
    positions: np.ndarray
    """Die endgültigen Lagen der Netzecken — Ecken auf ihre exakten Kurven gezogen."""


def _foot(curve: Curve, point: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Der nächste Punkt einer exakten Kurve und ihre Richtung dort — Strecke, Kreis, Schnitt."""
    if curve.kind == "occ" and curve.geometry is not None:
        parameter = _nearest_parameter(curve.geometry, point)
        if parameter is None:
            return None
        from OCP.gp import gp_Pnt, gp_Vec

        found = gp_Pnt()
        tangent = gp_Vec()
        curve.geometry.D1(parameter, found, tangent)
        length = tangent.Magnitude()
        if not length > 0.0:
            return None
        return (
            np.array((found.X(), found.Y(), found.Z())),
            np.array((tangent.X(), tangent.Y(), tangent.Z())) / length,
        )
    if curve.centre is None or curve.normal is None:
        return None
    offset = point - curve.centre
    if curve.kind == "line":
        return curve.centre + float(offset @ curve.normal) * curve.normal, curve.normal
    if curve.kind == "circle":
        flat = offset - float(offset @ curve.normal) * curve.normal
        length = float(np.linalg.norm(flat))
        if length <= 0.0:
            return None
        return curve.centre + flat / length * curve.radius, _cross(curve.normal, flat / length)
    return None


def _on_curves(
    start: np.ndarray,
    curves: Sequence[Curve],
    carriers: Sequence[Carrier],
    anchor: np.ndarray,
    reach: float,
) -> np.ndarray:
    """Eine Ecke auf die exakten Kurven ihrer Ketten und von dort auf ihre Träger.

    Gauß-Newton auf die Summe der Abstandsquadrate zu allen Kurven: Wo sich
    zwei Kurven kreuzen, ist das ihr Kreuzungspunkt, in wenigen Schritten auf
    Rundungsgenauigkeit. Gemittelte Projektionen, wie zuerst gebaut, laufen
    unter 45 Grad mit dem Faktor 0,85 je Schritt darauf zu — nach 24
    Schritten lag die Ecke an ``bottom-single.stl`` noch 1,7·10⁻⁶ mm neben
    der Ellipse, deren Parameterkurve die Gerade daneben deshalb einmal
    kreuzte, knapp außerhalb der Eckentoleranz: Die Zylinderfläche schnitt
    sich selbst. Richtungen, in denen sich die Kurven flacher als
    :data:`SNAP_RCOND` treffen, bestimmen sie nicht; dort bleibt die Ecke.

    Mit nur einer Kurve wird entlang ihr der Punkt gesucht, an dem auch die
    übrigen Träger liegen — etwa das Ende der Tangentenkante einer Verrundung
    an der Stirnfläche, die quer zu ihr steht. Weiter als ``reach`` von
    ``anchor`` — ihrer Lage im Netz — wandert keine Ecke.
    """
    point = start.copy()
    scale = max(1.0, float(np.abs(point).max()))
    for _ in range(16):
        feet = [found for curve in curves if (found := _foot(curve, point)) is not None]
        if not feet:
            return start
        matrix = np.zeros((3, 3))
        residual = np.zeros(3)
        for foot, direction in feet:
            across = np.eye(3) - np.outer(direction, direction)
            matrix += across
            residual += across @ (point - foot)
        # Zwei Kurven unter dem Winkel t: kleinster Eigenwert 1 - cos t.
        floor = (1.0 - math.sqrt(1.0 - SNAP_RCOND**2)) / len(feet)
        step = -np.linalg.pinv(matrix, rcond=floor, hermitian=True) @ residual
        point = point + step
        if float(np.linalg.norm(step)) <= 1e-14 * scale:
            break
    if len(curves) == 1 and carriers:
        point = _along_curve(point, curves[0], carriers)
    if not np.all(np.isfinite(point)) or float(np.linalg.norm(point - anchor)) > reach:
        return start
    return point


def _nearest_parameter(geometry: Any, point: np.ndarray) -> float | None:
    """Der Parameter des nächsten Punkts einer OpenCASCADE-Kurve — ``None`` ohne Lösung."""
    from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
    from OCP.gp import gp_Pnt

    projection = GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float, point)), geometry)
    if projection.NbPoints() == 0:
        return None
    return float(projection.LowerDistanceParameter())


def _along_curve(point: np.ndarray, curve: Curve, carriers: Sequence[Carrier]) -> np.ndarray:
    """Entlang einer Kurve dorthin, wo die übrigen Träger liegen (Gauß-Newton in einer Größe)."""
    if curve.kind == "occ" and curve.geometry is not None:
        geometry = curve.geometry
        start = _nearest_parameter(geometry, point)
        if start is None:
            return point

        def on_geometry(parameter: float) -> np.ndarray:
            found = geometry.Value(parameter)
            return np.array((found.X(), found.Y(), found.Z()))

        speed = geometry.DN(start, 1).Magnitude()
        if not speed > 0.0:
            return point
        solved = _solved_along(on_geometry, start, 1e-6 / speed, 1e-6, carriers)
        return point if solved is None else solved
    if curve.centre is None or curve.normal is None:
        return point
    centre, normal = curve.centre, curve.normal
    if curve.kind == "line":

        def at(parameter: float) -> np.ndarray:
            return centre + parameter * normal

        parameter = float((point - centre) @ normal)
        step = max(1e-6, 1e-6 * max(1.0, abs(parameter)))
    else:
        first = point - centre
        first = first - float(first @ normal) * normal
        if float(np.linalg.norm(first)) <= 0.0:
            return point
        first = _unit(first)
        second = _cross(normal, first)

        def at(parameter: float) -> np.ndarray:
            return centre + curve.radius * (
                math.cos(parameter) * first + math.sin(parameter) * second
            )

        parameter = 0.0
        step = 1e-6 / max(curve.radius, 1e-9)
    length_step = step if curve.kind == "line" else step * curve.radius
    solved = _solved_along(at, parameter, step, length_step, carriers)
    return point if solved is None else solved


def _solved_along(
    at: Callable[[float], np.ndarray],
    parameter: float,
    step: float,
    length_step: float,
    carriers: Sequence[Carrier],
) -> np.ndarray | None:
    """Der Punkt auf einer Kurve, an dem die quer schneidenden Träger liegen.

    Nur Träger, die die Kurve **quer** schneiden, bestimmen die Stelle auf
    ihr. Eine Verrundung, die tangential an die Ebene der Kurve anschließt,
    streift sie nur: Ihr Abstand ändert sich entlang der Kurve kaum, und um
    drei Mikrometer Maßabweichung auszugleichen, wanderte die Ecke 0,07 mm
    die Gerade entlang (gemessen an ``2x1-tray.stl``). Dieselbe Grenze wie
    beim Ziehen der Ecken (:data:`SNAP_RCOND`), hier als Steigung je mm.
    ``step`` ist ein Parameterschritt, ``length_step`` seine Länge; ``None``,
    wo kein Träger die Kurve quer schneidet.
    """
    here = np.array([carrier.distances(at(parameter)[None, :])[0] for carrier in carriers])
    ahead = np.array([carrier.distances(at(parameter + step)[None, :])[0] for carrier in carriers])
    crossing = np.abs((ahead - here) / length_step) >= SNAP_RCOND
    chosen = [carrier for carrier, keep in zip(carriers, crossing, strict=True) if keep]
    if not chosen:
        return None
    for _ in range(20):
        here = np.array([carrier.distances(at(parameter)[None, :])[0] for carrier in chosen])
        ahead = np.array(
            [carrier.distances(at(parameter + step)[None, :])[0] for carrier in chosen]
        )
        slope = (ahead - here) / step
        weight = float(slope @ slope)
        if weight <= 1e-24:
            break
        change = -float(slope @ here) / weight
        parameter += change
        if abs(change) <= step * 1e-6:
            break
    return at(parameter)


def _plan(
    regions: Regions,
    bounds: Boundaries,
    positions: np.ndarray,
    tolerance: float,
    cancelled: CancelToken | None,
    *,
    anchors: np.ndarray | None = None,
) -> _Plan:
    """Je Kette ihre Kurve; je Ecke und Kante die Toleranz, die sie tragen muss.

    Zwei Durchgänge. Zuerst die exakten Kurven — aus der Gestalt der Träger
    oder als Schnitt aus OpenCASCADE; sie hängen an keiner Ecke. Dann wandert
    jede Ecke auf die exakten Kurven ihrer Ketten: Ein Zylinder, der fast
    tangential an eine der drei Flächen einer Ecke stößt, bestimmt die Ecke
    quer dazu nicht, die Schnittgerade der zwei
    Ebenen aber sehr wohl (gemessen an ``Wedge-Lock (Base).stl``: Ecke
    6,6·10⁻⁴ mm neben der Geraden, und der Draht der Ebene schnitt sich
    selbst). Erst danach entstehen die Kurven aus Punkten, von den endgültigen
    Ecken aus. Eine Ecke muss die Enden aller ihrer Kanten erreichen und auf
    allen ihren Trägern liegen — ihre Toleranz ist der größte dieser Abstände,
    mit Luft für die Rundung. ``anchors`` sind die Lagen im Netz; von ihnen
    aus gilt :data:`CORNER_REACH` (ohne: die übergebenen Lagen).
    """
    anchors = positions if anchors is None else anchors
    positions = positions.copy()
    chains = bounds.chains
    structural: list[Curve | None] = []
    pairs: list[tuple[Carrier, ...] | None] = []
    for index, chain in enumerate(chains):
        if index % 256 == 0:
            _check(cancelled)
        carriers = _chain_carriers(chain, regions)
        pairs.append(carriers)
        if carriers is None:
            structural.append(None)
            continue
        points = positions[list(chain.vertices)]
        found = structural_curve(points, carriers, tolerance, closed=chain.closed)
        if found is None:
            found = intersection_curve(points, carriers, tolerance, closed=chain.closed)
        structural.append(found)
    # Die Ecken auf ihre exakten Kurven.
    incident: dict[int, list[int]] = defaultdict(list)
    for index, chain in enumerate(chains):
        if not chain.closed:
            incident[chain.vertices[0]].append(index)
            incident[chain.vertices[-1]].append(index)
    reach = max(CORNER_REACH * tolerance, EPS_GEOM)
    for position_, (vertex, members) in enumerate(sorted(incident.items())):
        if position_ % 1024 == 0:
            _check(cancelled)
        exact = [curve for member in members if (curve := structural[member]) is not None]
        if not exact:
            continue
        carriers_here: list[Carrier] = []
        covered: list[Carrier] = []
        for member in members:
            pair = pairs[member]
            if pair is None:
                continue
            for carrier in pair:
                if not any(carrier == known for known in carriers_here):
                    carriers_here.append(carrier)
            if structural[member] is not None:
                covered.extend(pair)
        others = [carrier for carrier in carriers_here if not any(carrier == c for c in covered)]
        positions[vertex] = _on_curves(positions[vertex], exact, others, anchors[vertex], reach)
    curves: list[Curve] = []
    vertex_tolerance: dict[int, float] = {}
    edge_tolerance: list[float] = []
    for index, chain in enumerate(chains):
        if index % 256 == 0:
            _check(cancelled)
        points = positions[list(chain.vertices)]
        carriers = pairs[index]
        if carriers is None:
            curved = [
                regions.carriers[side]
                for side in (chain.left, chain.right)
                if regions.origin[side] != "facet" and regions.carriers[side].curved
            ]
            deviation = 0.0
            if curved:
                samples = np.concatenate(
                    [
                        points[:-1] + fraction * (points[1:] - points[:-1])
                        for fraction in (0.25, 0.5, 0.75)
                    ]
                )
                deviation = _surface_gap(curved, samples)
            curve = Curve("polyline", points, deviation=deviation)
            sides = [
                regions.carriers[side]
                for side in (chain.left, chain.right)
                if regions.origin[side] != "facet"
            ]
        else:
            sides = list(carriers)
            found = structural[index]
            if found is not None and found.kind == "occ":
                found = _refitted(found, points, carriers, tolerance, closed=chain.closed)
            elif found is not None:
                found = replace(found, points=points)
            if found is None:
                dense = points
                if len(points) < DENSIFY_BELOW:
                    try:
                        dense = densified(points, carriers, DENSIFY_STEPS)
                    except ValueError:
                        dense = points
                found = fitted_curve(dense, carriers, tolerance, closed=chain.closed)
            curve = found
        curves.append(curve)
        edge_tolerance.append(max(EPS_GEOM, 1.5 * curve.deviation + EPS_GEOM))
        ends = [chain.vertices[0], chain.vertices[-1]]
        if curve.kind == "polyline":
            ends = list(chain.vertices)
        for vertex in ends:
            point = positions[vertex]
            gap = _gap_to_curve(curve, point)
            if sides:
                gap = max(gap, _surface_gap(sides, point[None, :]))
            vertex_tolerance[vertex] = max(
                vertex_tolerance.get(vertex, EPS_GEOM), 1.5 * gap + EPS_GEOM
            )
    return _Plan(tuple(curves), vertex_tolerance, tuple(edge_tolerance), positions)


def _gap_to_curve(curve: Curve, point: np.ndarray) -> float:
    """Wie weit eine Ecke von der Kurve ihrer Kette abliegt."""
    if curve.kind == "line" and curve.centre is not None and curve.normal is not None:
        offset = point - curve.centre
        return float(np.linalg.norm(offset - (offset @ curve.normal) * curve.normal))
    if curve.kind == "circle" and curve.centre is not None and curve.normal is not None:
        offset = point - curve.centre
        height = float(offset @ curve.normal)
        radius = float(np.linalg.norm(offset - height * curve.normal))
        return math.hypot(radius - curve.radius, height)
    if curve.kind == "occ" and curve.geometry is not None:
        _parameters, distances = _curve_parameters(curve.geometry, point[None, :])
        return float(distances[0]) if np.isfinite(distances[0]) else 0.0
    return 0.0


def _occ_edges(
    chain: Chain, curve: Curve, vertex: Callable[[int], Any], tolerance: float
) -> list[Any]:
    """Die OpenCASCADE-Kanten einer Kette, in ihrer Richtung."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.collections import HArray1_gp_Pnt
    from OCP.Geom import Geom_Circle, Geom_Line
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    builder = BRep_Builder()

    def made(maker: Any) -> Any:
        if not maker.IsDone():
            raise ValueError(f"edge not built: {maker.Error()}")
        edge = maker.Edge()
        builder.UpdateEdge(edge, tolerance)
        return edge

    ends = chain.vertices
    if curve.kind == "polyline":
        return [
            made(BRepBuilderAPI_MakeEdge(vertex(first), vertex(second)))
            for first, second in pairwise(ends)
        ]
    points = curve.points
    if curve.kind == "line":
        if curve.centre is None or curve.normal is None:
            return [made(BRepBuilderAPI_MakeEdge(vertex(ends[0]), vertex(ends[-1])))]
        along = curve.normal
        first_at = float((points[0] - curve.centre) @ along)
        last_at = float((points[-1] - curve.centre) @ along)
        if last_at < first_at:
            along, first_at, last_at = -along, -first_at, -last_at
        line = Geom_Line(gp_Pnt(*map(float, curve.centre)), gp_Dir(*map(float, along)))
        return [
            made(
                BRepBuilderAPI_MakeEdge(line, vertex(ends[0]), vertex(ends[-1]), first_at, last_at)
            )
        ]
    if curve.kind == "circle":
        assert curve.centre is not None and curve.normal is not None
        centre = curve.centre
        start = _unit(points[0] - centre)
        start = _unit(start - (start @ curve.normal) * curve.normal)
        normal = curve.normal
        second = _cross(normal, start)
        offset = points - centre
        angles = np.unwrap(np.arctan2(offset @ second, offset @ start))
        if angles[-1] < angles[0] or (chain.closed and angles[len(angles) // 2] < 0.0):
            normal = -normal
            second = _cross(normal, start)
            angles = np.unwrap(np.arctan2(offset @ second, offset @ start))
        end = 2.0 * math.pi if chain.closed else float(angles[-1])
        circle = Geom_Circle(
            gp_Ax2(
                gp_Pnt(*map(float, centre)),
                gp_Dir(*map(float, normal)),
                gp_Dir(*map(float, start)),
            ),
            float(curve.radius),
        )
        return [made(BRepBuilderAPI_MakeEdge(circle, vertex(ends[0]), vertex(ends[-1]), 0.0, end))]
    if curve.kind == "occ":
        return [
            made(
                BRepBuilderAPI_MakeEdge(
                    curve.geometry, vertex(ends[0]), vertex(ends[-1]), curve.first, curve.last
                )
            )
        ]
    samples = points[:-1] if chain.closed else points
    array = HArray1_gp_Pnt(1, len(samples))
    for position, sample in enumerate(samples, start=1):
        array.SetValue(position, gp_Pnt(*map(float, sample)))
    interpolation = GeomAPI_Interpolate(array, bool(chain.closed), EPS_GEOM * 1e-3)
    interpolation.Perform()
    if not interpolation.IsDone():
        raise ValueError("interpolation failed")
    spline = interpolation.Curve()
    first, last = spline.FirstParameter(), spline.LastParameter()
    return [made(BRepBuilderAPI_MakeEdge(spline, vertex(ends[0]), vertex(ends[-1]), first, last))]


def _occ_face(
    carrier: Carrier,
    shape: _RegionShape,
    loops: Sequence[Sequence[tuple[int, bool]]],
    edges_of: Callable[[int], Sequence[Any]],
    facet: bool,
) -> Any:
    """Eine Fläche auf dem Träger, von den Rändern des Bereichs begrenzt (siehe
    :func:`_checked_face`)."""
    return _checked_face(carrier, shape, loops, edges_of, facet)[0]


def _checked_face(
    carrier: Carrier,
    shape: _RegionShape,
    loops: Sequence[Sequence[tuple[int, bool]]],
    edges_of: Callable[[int], Sequence[Any]],
    facet: bool,
) -> tuple[Any, bool | None]:
    """Eine Fläche auf dem Träger, von den Rändern des Bereichs begrenzt — und ob sie gültig ist.

    Die Ränder laufen so, dass der Bereich links liegt, von außen gesehen.
    Zeigt die natürliche Normale des Trägers nach innen (eine Bohrung, eine
    Kehle), wird jeder Draht umgekehrt, die Fläche so gebaut und danach
    umgedreht — ``Inside=False``, weil ``True`` einen richtig orientierten
    Draht auf Zylinder und Torus umdreht (gemessen, Sonde s03).

    **Eine Ebene bekommt ``ShapeFix_Face`` nur, wenn sie es braucht.** Ihre
    Randkurven brauchen keine Parameterkurven, und von 1525 ebenen Flächen
    aus Strecken an ``top-single.stl`` waren ohne die Reparatur 1478 gültig
    (Sonde s34, 0,33 statt 0,63 ms je Fläche); geprüft wird deshalb zuerst,
    repariert nur der Rest. Die Prüfung reist als zweiter Wert mit —
    ``None``, wo keine lief.
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.ShapeFix import ShapeFix_Face
    from OCP.TopoDS import TopoDS, TopoDS_Wire

    builder = BRep_Builder()
    surface, flip = _occ_surface(carrier, shape)
    wires = []
    for loop in loops:
        entries = list(loop)
        if flip:
            entries = [(chain, not forward) for chain, forward in reversed(entries)]
        wire = TopoDS_Wire()
        builder.MakeWire(wire)
        for chain, forward in entries:
            edges = edges_of(chain)
            ordered = edges if forward else list(reversed(edges))
            for edge in ordered:
                builder.Add(wire, edge if forward else TopoDS.Edge(edge.Reversed()))
        wire.Closed(True)
        wires.append(wire)
    if not wires:
        maker = BRepBuilderAPI_MakeFace(surface, EPS_GEOM)
    else:
        maker = BRepBuilderAPI_MakeFace(surface, wires[0], False)
    if not maker.IsDone():
        raise ValueError(f"face not built: {maker.Error()}")
    face = maker.Face()
    for wire in wires[1:]:
        builder.Add(face, wire)
    valid: bool | None = None
    if not facet and carrier.kind == "plane":
        valid = bool(BRepCheck_Analyzer(face).IsValid())
    if not facet and not valid:
        fix = ShapeFix_Face(face)
        fix.Perform()
        face = fix.Face()
        # **Die Naht braucht danach gleiche Parameter.** ``FixMissingSeam``
        # teilt einen geschlossenen Kreis an der Naht und lässt die Stücke
        # ohne abgeglichene pcurves zurück: an einem Zylinderband mit zwei
        # Kreisen waren 30 von 121 Eckenlagen ungültig, mit diesem Schritt
        # keine von 225 (Sonde s08).
        BRepLib.SameParameter_s(face, EPS_GEOM, True)
        valid = None
    if flip:
        face = TopoDS.Face(face.Reversed())
    return face, valid


def _face_is_sound(face: Any, shape: _RegionShape, facet: bool, valid: bool | None = None) -> bool:
    """Gültig, mit der Fläche des Bereichs und der Probe darin — nicht das Gegenstück.

    Ein falsch umlaufender Draht auf einem Zylinder ergibt eine gültige Fläche:
    die anderen drei Viertel. Die Fläche des Netzbereichs und ein Punkt aus
    seiner Mitte entscheiden das. ``valid`` ist eine schon gelaufene Prüfung
    (:func:`_checked_face`); ``None`` prüft hier.
    """
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepGProp import BRepGProp
    from OCP.gp import gp_Pnt
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON

    if facet:
        return True
    if valid is None:
        valid = bool(BRepCheck_Analyzer(face).IsValid())
    if not valid:
        return False
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, properties)
    area = float(properties.Mass())
    if not (0.7 * shape.area <= area <= 1.4 * shape.area + 1e-6):
        return False
    probe = BRepClass_FaceClassifier(face, gp_Pnt(*map(float, shape.sample)), 1e-4)
    return probe.State() in (TopAbs_IN, TopAbs_ON)


def _shells(
    mesh: MeshData, regions: Regions, faces: Sequence[Any], tolerance: float
) -> tuple[list[tuple[Any, float, np.ndarray]], list[Any]]:
    """Je Netzkomponente eine genähte Schale: Schale, Vorzeichenvolumen, ein Punkt darauf.

    **Genäht, obwohl die Kanten schon geteilt gebaut sind.** ``ShapeFix_Face``
    ersetzt an einem Zylinderband die zwei Kreise durch eigene Kopien, wenn es
    die Naht einsetzt — die Deckel daneben halten dann andere Kanten, und die
    Schale ist nicht verbunden (gemessen an ``dense_cylinder.stl``:
    ``BRepCheck_NotConnected``). ``BRepBuilderAPI_Sewing`` legt geometrisch
    gleiche Kanten wieder zusammen; die Toleranz ist die größte, die eine
    Kante ohnehin trägt. Zurück kommen auch die genähten Flächen je Bereich,
    damit die Filamente ihren Platz finden.
    """
    from OCP.BRep import BRep_Builder
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS, TopoDS_Shell

    from app.core.geom.mesh import face_components

    builder = BRep_Builder()
    components = face_components(mesh.raw)
    component_of_region = np.full(regions.count, -1, dtype=np.int64)
    for number, triangles in enumerate(components):
        component_of_region[np.unique(regions.of_triangle[triangles])] = number
    raw = mesh.raw
    vertices = np.asarray(raw.vertices, dtype=np.float64)
    triangles_all = np.asarray(raw.faces, dtype=np.int64)
    sewn_faces: list[Any] = list(faces)
    shells = []
    for number, triangles in enumerate(components):
        members = np.flatnonzero(component_of_region == number).tolist()
        corners = vertices[triangles_all[triangles]]
        signed = float(
            np.einsum("ij,ij->i", corners[:, 0], np.cross(corners[:, 1], corners[:, 2])).sum() / 6.0
        )
        if len(members) == 1:
            shell = TopoDS_Shell()
            builder.MakeShell(shell)
            builder.Add(shell, faces[members[0]])
            shells.append((shell, signed, corners[0].mean(axis=0)))
            continue
        # Zwei Gänge (siehe :data:`SEWING_FIRST`): erst eng, dann nur für die
        # Ränder, die dabei offen blieben, so weit wie ihre Kanten es brauchen.
        # Schließt das nicht, näht ein einziger weiter Gang alles wie zuvor.
        passes, sewn_shape = _sewn([faces[region] for region in members], tolerance, SEWING_FIRST)
        if passes is None:
            passes, sewn_shape = _sewn([faces[region] for region in members], tolerance, None)
        if passes is None:
            raise ValueError("the faces do not close into one shell")
        found = TopExp_Explorer(sewn_shape, TopAbs_SHELL)
        if not found.More():
            raise ValueError("sewing produced no shell")
        shell = TopoDS.Shell(found.Current())
        found.Next()
        if found.More():
            raise ValueError("sewing produced more than one shell")
        for region in members:
            face = faces[region]
            for step in passes:
                if step.IsModified(face):
                    face = step.Modified(face)
            sewn_faces[region] = face
        shells.append((shell, signed, corners[0].mean(axis=0)))
    return shells, sewn_faces


def _sewn(
    faces: Sequence[Any], tolerance: float, first: float | None
) -> tuple[list[Any] | None, Any]:
    """Die Flächen genäht — in einem Gang oder erst eng, dann weit; ``None``, wo es nicht schließt.

    Zurück kommen die Näher in ihrer Reihenfolge, damit der Aufrufer jede
    Fläche bis in die Schale verfolgen kann, und die genähte Form.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing

    narrow = tolerance if first is None else min(first, tolerance)
    sewing = BRepBuilderAPI_Sewing(narrow)
    for face in faces:
        sewing.Add(face)
    sewing.Perform()
    shape = sewing.SewedShape()
    passes = [sewing]
    if sewing.NbFreeEdges() and tolerance > narrow:
        second = BRepBuilderAPI_Sewing(tolerance)
        second.Add(shape)
        second.Perform()
        shape = second.SewedShape()
        passes.append(second)
    last = passes[-1]
    if last.NbFreeEdges() or last.NbMultipleEdges():
        return None, shape
    return passes, shape


def _assembled(shells: Sequence[tuple[Any, float, np.ndarray]]) -> Any:
    """Schalen zu Körpern: jede positive Schale ein Körper, jede negative sein Hohlraum."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.BRepLib import BRepLib
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN
    from OCP.TopoDS import TopoDS_Compound, TopoDS_Solid

    builder = BRep_Builder()
    outer = [(shell, point) for shell, signed, point in shells if signed > 0.0]
    inner = [(shell, point) for shell, signed, point in shells if signed <= 0.0]
    solids = []
    for shell, _point in outer:
        solid = TopoDS_Solid()
        builder.MakeSolid(solid)
        builder.Add(solid, shell)
        solids.append(solid)
    for shell, point in inner:
        host = None
        for position, solid in enumerate(solids):
            probe = BRepClass3d_SolidClassifier(solid, gp_Pnt(*map(float, point)), 1e-6)
            if probe.State() == TopAbs_IN:
                host = position
                break
        if host is None:
            raise ValueError("an inner shell sits in no body")
        builder.Add(solids[host], shell)
    for solid in solids:
        if not BRepLib.OrientClosedSolid_s(solid):
            raise ValueError("a body could not be oriented")
    if len(solids) == 1:
        return solids[0]
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for solid in solids:
        builder.Add(compound, solid)
    return compound


def _demoted(mesh: MeshData, regions: Regions, failed: Sequence[int]) -> Regions:
    """Bereiche, deren Fläche nicht trug, gehen Dreieck für Dreieck als Ebenen ein.

    Ehrlich statt geraten: Was sich nicht als eine Fläche auf seinem Träger
    schließen ließ, bleibt so, wie das Netz es sagt, und zählt zum
    Freiformrest. Die übrigen Bereiche behalten ihre Nummernfolge.
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=np.float64)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    normals = np.asarray(mesh.raw.face_normals, dtype=np.float64)
    failed_set = {int(index) for index in failed}
    keep = [index for index in range(regions.count) if index not in failed_set]
    renumber = np.full(regions.count, -1, dtype=np.int64)
    renumber[keep] = np.arange(len(keep))
    of_triangle = renumber[regions.of_triangle]
    carriers = [regions.carriers[index] for index in keep]
    origin: list[RegionOrigin] = [regions.origin[index] for index in keep]
    slots = [regions.slots[index] for index in keep]
    features = [regions.features[index] for index in keep]
    for triangle in np.flatnonzero(of_triangle < 0).tolist():
        of_triangle[triangle] = len(carriers)
        carriers.append(plane_through(vertices[faces[triangle]], normals[triangle]))
        origin.append("facet")
        slots.append(regions.slots[int(regions.of_triangle[triangle])])
        features.append(())
    return Regions(
        of_triangle=of_triangle,
        carriers=tuple(carriers),
        origin=tuple(origin),
        slots=tuple(slots),
        features=tuple(features),
        rejected=regions.rejected,
    )


@dataclass(frozen=True, slots=True)
class _Built:
    shape: Any
    regions: Regions
    positions: np.ndarray
    moved: np.ndarray
    face_slots: tuple[int, ...]
    curves: tuple[Curve, ...]


def _build(
    mesh: MeshData,
    regions: Regions,
    tolerance: float,
    cancelled: CancelToken | None,
    report: Callable[[float, str], None],
    built_faces: dict[bytes, Any] | None = None,
) -> _Built:
    """Ecken, Kanten, Flächen, Schalen, Körper — oder ``_RegionFailedError`` mit den Schuldigen.

    ``built_faces`` merkt sich jede gebaute und geprüfte Fläche unter dem, was
    sie festlegt (:func:`_face_key`). Nach einem Herabstufen baut der nächste
    Anlauf nur die Flächen neu, an deren Rand sich etwas geändert hat — am
    Besenhalter aus dem Kundenordner (12 148 Ebenen, 23 herabgestuft) war der
    zweite Anlauf sonst ein vollständiger zweiter Bau.
    """
    from OCP.BRep import BRep_Builder
    from OCP.gp import gp_Pnt
    from OCP.TopoDS import TopoDS_Vertex

    report(0.35, "edges")
    bounds = boundaries(mesh, regions, cancelled=cancelled)
    snapped_positions, _moved = _vertex_positions(mesh, regions, bounds, tolerance, cancelled)
    original = np.asarray(mesh.raw.vertices, dtype=np.float64)
    plan = _plan(regions, bounds, snapped_positions, tolerance, cancelled, anchors=original)
    positions = plan.positions
    moved = np.linalg.norm(positions - original, axis=1)

    def own_edges() -> Callable[[int], list[Any]]:
        """Eigene Ecken und Kanten für jede Fläche.

        **Geteilt gebaut hieß: von der Nachbarfläche verändert.**
        ``ShapeFix_Face`` gleicht an einer Fläche die Parameter ihrer Kanten
        ab und schreibt dabei an der Kante selbst — eine ebene Fläche, deren
        Kante zuvor der Kegel daneben angefasst hatte, war danach ungültig,
        obwohl ihr Draht geschlossen, verbunden und schnittfrei war (gemessen
        an ``1x1-bin.stl``: drei Fasenebenen). Jede Fläche bekommt ihre
        Kanten deshalb aus denselben Zahlen neu; zusammen legt sie das Nähen.
        """
        builder = BRep_Builder()
        made: dict[int, Any] = {}
        built: dict[int, list[Any]] = {}

        def vertex(index: int) -> Any:
            known = made.get(index)
            if known is None:
                known = TopoDS_Vertex()
                builder.MakeVertex(
                    known,
                    gp_Pnt(*map(float, positions[index])),
                    float(plan.vertex_tolerance.get(index, EPS_GEOM)),
                )
                made[index] = known
            return known

        def edges(chain: int) -> list[Any]:
            known = built.get(chain)
            if known is None:
                known = _occ_edges(
                    bounds.chains[chain], plan.curves[chain], vertex, plan.edge_tolerance[chain]
                )
                built[chain] = known
            return known

        return edges

    report(0.5, "faces")
    shapes = _region_shapes(mesh, regions)
    faces: list[Any] = []
    failed: set[int] = set()
    for index in range(regions.count):
        if index % 256 == 0:
            _check(cancelled)
            report(0.5 + 0.3 * index / max(regions.count, 1), "faces")
        facet = regions.origin[index] == "facet"
        carrier = regions.carriers[index]
        if facet:
            corners = positions[list(_triangle_corners(mesh, regions, index))]
            carrier = plane_through(corners, shapes[index].sample_normal)
        key = _face_key(carrier, facet, shapes[index], bounds, bounds.loops[index], plan)
        if built_faces is not None and key in built_faces:
            face = built_faces[key]
        else:
            checked: bool | None = None
            try:
                face, checked = _checked_face(
                    carrier, shapes[index], bounds.loops[index], own_edges(), facet
                )
            except ValueError, RuntimeError:
                face = None
            if face is not None and not _face_is_sound(face, shapes[index], facet, checked):
                face = None
            if built_faces is not None:
                built_faces[key] = face
        if face is None:
            if facet:
                raise ValueError("a single triangle does not make a face")
            failed.add(index)
            faces.append(None)
            continue
        faces.append(face)
    if failed:
        raise _RegionFailedError(sorted(failed))
    report(0.8, "body")
    sewing_tolerance = max(EPS_GEOM, 2.0 * max(plan.edge_tolerance, default=EPS_GEOM))
    shells, sewn = _shells(mesh, regions, faces, sewing_tolerance)
    shape = _assembled(shells)
    broken = _broken_after_sewing(shape, sewn, regions)
    if broken:
        raise _RegionFailedError(broken)
    return _Built(shape, regions, positions, moved, _face_slots(shape, sewn, regions), plan.curves)


def _face_key(
    carrier: Carrier,
    facet: bool,
    shape: _RegionShape,
    bounds: Boundaries,
    loops: Sequence[Sequence[tuple[int, bool]]],
    plan: _Plan,
) -> bytes:
    """Was eine Fläche festlegt: Träger, Bereich und ihre Ränder mit Ecken und Kurven.

    Ohne Bereichsnummern — die ändern sich, wenn ein Bereich zu Dreiecken wird.
    Zwei Flächen mit demselben Schlüssel würden gleich gebaut und gleich geprüft.
    """
    digest = hashlib.blake2b(digest_size=20)
    digest.update(repr((carrier, facet, shape.area)).encode())
    digest.update(np.ascontiguousarray(shape.sample).tobytes())
    digest.update(np.ascontiguousarray(shape.sample_normal).tobytes())
    for loop in loops:
        digest.update(b"|")
        for chain_index, forward in loop:
            chain = bounds.chains[chain_index]
            curve = plan.curves[chain_index]
            digest.update(
                repr(
                    (
                        chain.vertices,
                        forward,
                        chain.closed,
                        curve.kind,
                        curve.radius,
                        curve.first,
                        curve.last,
                        curve.deviation,
                        plan.edge_tolerance[chain_index],
                        tuple(plan.vertex_tolerance.get(vertex) for vertex in chain.vertices),
                    )
                ).encode()
            )
            digest.update(np.ascontiguousarray(plan.positions[list(chain.vertices)]).tobytes())
            digest.update(np.ascontiguousarray(curve.points).tobytes())
            for part in (curve.centre, curve.normal):
                if part is not None:
                    digest.update(np.ascontiguousarray(part).tobytes())
    return digest.digest()


def _broken_after_sewing(shape: Any, sewn: Sequence[Any], regions: Regions) -> list[int]:
    """Die eingepassten Bereiche, deren Fläche erst im genähten Körper ungültig ist.

    Jede Fläche wird vor dem Nähen einzeln geprüft (:func:`_face_is_sound`).
    Gemessen an ``Siebhalter.stl`` aus dem Kundenordner: zwei ebene Flächen,
    je ein Dreieck mit einer Ecke mitten auf einer Seite — dort stoßen zwei
    Nachbarflächen aneinander —, gültig vor dem Nähen und danach mit einem
    Draht, der sich selbst schneidet; ``ShapeFix_Shape`` konnte es nicht
    heilen, und die ganze Umwandlung endete als Absage. Als Dreiecke gebaut
    tragen dieselben Bereiche. Geprüft wird Fläche für Fläche nur, wenn der
    Körper als Ganzes ungültig ist.
    """
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    if BRepCheck_Analyzer(shape).IsValid():
        return []
    known = ShapeMap()
    owner: dict[int, int] = {}
    for region, face in enumerate(sewn):
        if face is not None:
            owner[int(known.Add(face))] = region
    broken: set[int] = set()
    walk = TopExp_Explorer(shape, TopAbs_FACE)
    while walk.More():
        face = walk.Current()
        if not BRepCheck_Analyzer(face).IsValid():
            found = owner.get(int(known.FindIndex(face)))
            if found is not None and regions.origin[found] != "facet":
                broken.add(found)
        walk.Next()
    return sorted(broken)


def _face_slots(shape: Any, faces: Sequence[Any], regions: Regions) -> tuple[int, ...]:
    """Das Filament je Fläche in der Reihenfolge des Körpers — leer, wo alles Slot null ist."""
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    if not any(regions.slots):
        return ()
    found = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, found)
    slots = [0] * found.Extent()
    for region, face in enumerate(faces):
        index = int(found.FindIndex(face))
        if index <= 0:
            return ()
        slots[index - 1] = regions.slots[region]
    return tuple(slots)


def _triangle_corners(mesh: MeshData, regions: Regions, region: int) -> tuple[int, ...]:
    """Die drei Netzecken eines Freiformdreiecks."""
    triangle = int(np.flatnonzero(regions.of_triangle == region)[0])
    return tuple(int(index) for index in np.asarray(mesh.raw.faces)[triangle])


def _checked_body(shape: Any, slots: tuple[int, ...]) -> Solid:
    """Ein geschlossener, gültiger Körper — sonst ``ValueError`` mit dem Grund."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.ShapeFix import ShapeFix_Shape

    from app.core.brep.kernel import Solid

    if not BRepCheck_Analyzer(shape).IsValid():
        fix = ShapeFix_Shape(shape)
        fix.Perform()
        shape = fix.Shape()
        if not BRepCheck_Analyzer(shape).IsValid():
            raise ValueError("the rebuilt body is not valid")
        slots = ()
    body = Solid(shape, face_slots=slots if len(set(slots)) > 1 else ())
    if not body.is_closed:
        raise ValueError("the rebuilt body is not closed")
    return body


def _face_kinds(body: Solid, regions: Regions) -> dict[str, int]:
    """Flächen nach Trägerart; eine Ebene, die kein erkannter Träger ist, ist Freiformrest.

    Gezählt wird am fertigen Körper — ``unified`` legt die zwei Dreiecke
    eines Vierecks im Freiformrest zu einer Fläche zusammen, und die Zahl der
    Bereiche davor sagte nicht, was im STEP steht.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import (
        GeomAbs_BSplineSurface,
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    )

    names = {
        GeomAbs_Plane: "plane",
        GeomAbs_Cylinder: "cylinder",
        GeomAbs_Cone: "cone",
        GeomAbs_Sphere: "sphere",
        GeomAbs_Torus: "torus",
        GeomAbs_BSplineSurface: "bspline",
    }
    from scipy.spatial import cKDTree

    planes = [
        carrier
        for carrier, origin in zip(regions.carriers, regions.origin, strict=True)
        if origin != "facet" and carrier.kind == "plane"
    ]
    counted: dict[str, int] = {}
    found: list[tuple[np.ndarray, np.ndarray]] = []
    for face in body.faces():
        adaptor = BRepAdaptor_Surface(face)
        kind = names.get(adaptor.GetType(), "other")
        if kind == "plane":
            plane = adaptor.Plane()
            location, normal = plane.Location(), plane.Axis().Direction()
            found.append(
                (
                    np.array((location.X(), location.Y(), location.Z())),
                    np.array((normal.X(), normal.Y(), normal.Z())),
                )
            )
            continue
        counted[kind] = counted.get(kind, 0) + 1
    if not found:
        return counted
    # Eine Ebene des Körpers ist ein erkannter Träger, wenn ihre Normale bis auf
    # 1e-9 im Kosinus und ihr Abstand bis auf EPS_GEOM stimmen. Die Kandidaten
    # kommen aus einem Baum über (Normale · Gewicht, Abstand vom Mittelpunkt)
    # je Träger und Gegenrichtung; entschieden wird danach genau. Der
    # Vergleich jeder Fläche mit jedem Träger kostete an ``top-single.stl``
    # (1533 Ebenen) 6,8 der 16 Sekunden der ganzen Umwandlung.
    closeness = math.sqrt(2e-9)
    weight = EPS_GEOM / closeness
    origins = np.array([face_origin for face_origin, _normal in found])
    normals = np.array([face_normal for _origin, face_normal in found])
    if planes:
        axes = np.array([np.asarray(carrier.axis, dtype=np.float64) for carrier in planes])
        centres = np.array([np.asarray(carrier.origin, dtype=np.float64) for carrier in planes])
        middle = centres.mean(axis=0)
        offsets = np.einsum("ij,ij->i", axes, centres - middle)
        keys = np.vstack(
            (
                np.column_stack((axes * weight, offsets)),
                np.column_stack((-axes * weight, -offsets)),
            )
        )
        tree = cKDTree(keys)
        probes = np.column_stack(
            (normals * weight, np.einsum("ij,ij->i", normals, origins - middle))
        )
        # Die Abstände zweier fast gleicher Normalen weichen um ihren Winkel
        # mal den Hebel vom Mittelpunkt ab.
        lever = float(
            max(
                np.linalg.norm(centres - middle, axis=1).max(),
                np.linalg.norm(origins - middle, axis=1).max(),
            )
        )
        hits = tree.query_ball_point(probes, r=2.0 * EPS_GEOM + closeness * lever)
    else:
        axes = centres = np.empty((0, 3))
        hits = [[] for _ in found]
    for (face_origin, face_normal), candidates in zip(found, hits, strict=True):
        kind = "facet"
        for candidate in candidates:
            carrier_index = candidate % len(planes)
            if abs(float(face_normal @ axes[carrier_index])) > 1.0 - 1e-9 and (
                abs(float((face_origin - centres[carrier_index]) @ face_normal)) <= EPS_GEOM
            ):
                kind = "plane"
                break
        counted[kind] = counted.get(kind, 0) + 1
    return counted


#: Wo ein Netzdreieck auf seinen Träger hin gemessen wird, baryzentrisch: die
#: Ecken, die Kantenmitten, der Schwerpunkt und die drei Punkte dazwischen.
#: Die Sehne eines Zylinders liegt an ihrer Kantenmitte am weitesten weg, das
#: Viereck eines Rings in seiner Mitte — beides trifft die Stichprobe.
_FACET_SAMPLES: Final = np.array(
    [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.5, 0.5, 0.0),
        (0.0, 0.5, 0.5),
        (0.5, 0.0, 0.5),
        (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
        (2.0 / 3.0, 1.0 / 6.0, 1.0 / 6.0),
        (1.0 / 6.0, 2.0 / 3.0, 1.0 / 6.0),
        (1.0 / 6.0, 1.0 / 6.0, 2.0 / 3.0),
    ]
)


#: Wo ein Dreieck der Messvernetzung auf den Körper hin beprobt wird: seine
#: Ecken, der Schwerpunkt und die drei Punkte dazwischen — **ohne die
#: Kantenmitten.** Eine Randkante der Vernetzung ist die Sehne der Randkurve,
#: und ihre Mitte liegt neben der Fläche: auf der Ebene einer Platte, aber im
#: Loch. Projiziert bleibt sie dort, und an ``plate_holes.stl`` meldete sie
#: 0,0073 mm, wo der Körper 0,0056 mm vom Netz abliegt.
_BODY_SAMPLES: Final = _FACET_SAMPLES[[0, 1, 2, 6, 7, 8, 9]]


def _own_distances(mesh: MeshData, regions: Regions, moved: np.ndarray) -> np.ndarray:
    """Je Netzdreieck der größte Abstand seiner zehn Stichproben zu seinem eigenen Träger.

    Ein eingepasstes Dreieck gegen seinen Träger, ein Freiformdreieck über
    die Verschiebung seiner Ecken: Das neue Dreieck ist das alte mit
    gezogenen Ecken, und kein Punkt wandert weiter als seine weiteste Ecke.
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=np.float64)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    own = moved[faces].max(axis=1) if len(faces) else np.zeros(0)
    for index, carrier in enumerate(regions.carriers):
        if regions.origin[index] == "facet":
            continue
        chosen = np.flatnonzero(regions.of_triangle == index)
        samples = np.einsum("sk,tkj->tsj", _FACET_SAMPLES, vertices[faces[chosen]])
        own[chosen] = (
            np.abs(carrier.distances(samples.reshape(-1, 3)))
            .reshape(len(chosen), len(_FACET_SAMPLES))
            .max(axis=1)
        )
    return own


def _mesh_to_body(
    mesh: MeshData,
    own: np.ndarray,
    body: Solid,
    fine: MeshData,
    tolerance: float,
    cancelled: CancelToken | None,
) -> tuple[float, np.ndarray | None, int]:
    """Größter Abstand des Netzes zum Körper, an zehn Stellen je Dreieck — und die inneren Wände.

    Zuerst jedes Dreieck gegen seine eigene Fläche (``own``). Das misst gegen
    die **unbegrenzte** Fläche, und das genügt nicht: An
    ``post_with_fillet.stl`` liegen Mantel der Säule und Innenwand des
    Kehlrings zwischen z = 0 und 3 aufeinander, eine Naht, die die
    Vereinigung nicht verschmolzen hat. Ihre Dreiecke liegen genau auf dem
    Zylinder des Mantels (Abstand 0) — und 1,24 mm unter der Kehle des
    Körpers, der den Mantel dort gar nicht hat.

    Deshalb danach gegen den Körper selbst: Wessen Punkt weiter von der
    Messvernetzung liegt als von seiner Fläche (plus deren Feinheit), wird
    gegen die Fläche gemessen, die dort am nächsten liegt
    (:func:`app.core.geom.mesh.beyond_surface` — in einem gewöhnlichen Netz
    sind das keine). Solche Punkte sind echte Abweichung oder eine **innere
    Wand** (:func:`_inner_walls`); die zählt eigens, denn außen ändert sie
    nichts. Zurück kommen Abstand, Ort und die Zahl der Dreiecke mit einer
    inneren Wand.

    **Gemessen, nicht eingeschlossen.** Die belegten Obergrenzen der Karte
    „Formabweichung“ (:mod:`app.core.geom.deviation`) kosteten am Ring der
    ``post_with_fillet.stl`` 2,2 der 2,5 Sekunden der ganzen Umwandlung.
    Hier genügt die Stichprobe, und die Zahl heißt so, wie sie entstanden ist.
    """
    from app.core.geom.mesh import beyond_surface

    vertices = np.asarray(mesh.raw.vertices, dtype=np.float64)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    if not len(faces):
        return 0.0, None, 0
    # Gesucht wird an Ecken und Mitten: Eine Naht oder ein fehlendes Stück
    # hat Ausdehnung, kein Punkt davon entgeht beiden. Die zehn Stichproben
    # je Dreieck braucht nur die genaue Zahl darüber (``own``); hier kosteten
    # sie am Besenhalter aus dem Kundenordner 38 Sekunden.
    first = int(np.argmax(own))
    worst = float(own[first])
    point: np.ndarray | None = vertices[faces[first]].mean(axis=0) if worst > 0.0 else None
    corner_own = np.zeros(len(vertices))
    np.maximum.at(corner_own, faces.reshape(-1), np.repeat(own, 3))
    used = np.unique(faces)
    probes = np.vstack((vertices[faces].mean(axis=1), vertices[used]))
    floors = np.concatenate((own, corner_own[used]))
    _check(cancelled)
    deflection = _MEASURE_SAG
    found, distances, spots, nearest = beyond_surface(fine.raw, probes, floors + deflection)
    if not len(found):
        return worst, point, 0
    _check(cancelled)
    exact = _exact_to_body(body, fine, probes[found], distances, nearest, deflection)
    walls = _inner_walls(body, mesh, probes[found], spots, tolerance)
    # Gezählt werden Dreiecke: eine Mitte für ihres, eine Ecke für alle an ihr.
    centres = found[walls][found[walls] < len(faces)]
    corners = used[found[walls][found[walls] >= len(faces)] - len(faces)]
    inner = int(
        (np.isin(np.arange(len(faces)), centres) | np.isin(faces, corners).any(axis=1)).sum()
    )
    outside = ~walls
    if outside.any() and float(exact[outside].max()) > worst:
        position = int(np.flatnonzero(outside)[np.argmax(exact[outside])])
        worst = float(exact[position])
        point = probes[found[position]]
    return worst, point, inner


def _exact_to_body(
    body: Solid,
    shown: MeshData,
    points: np.ndarray,
    distances: np.ndarray,
    nearest: np.ndarray,
    deflection: float,
) -> np.ndarray:
    """Abstände zur Vernetzung eines Körpers, auf seine exakten Flächen umgerechnet.

    Die Vernetzung liegt bis zu ihrer Feinheit neben dem Körper; der Träger
    der nächsten Fläche sagt es genau, wo der Punkt über ihr liegt. Beides
    sind untere Grenzen des wahren Abstands, also gilt die größere.
    """
    from app.core.brep.kernel import _FACE_ATTRIBUTE

    exact = np.maximum(distances - deflection, 0.0)
    owners = np.asarray(shown.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
    if len(owners) != len(shown.raw.faces):
        return exact
    body_faces = body.faces()
    face_of = owners[nearest]
    for face in np.unique(face_of).tolist():
        carrier = _carrier_of_face(body_faces[face]) if 0 <= face < len(body_faces) else None
        if carrier is None:
            continue
        chosen = face_of == face
        exact[chosen] = np.maximum(exact[chosen], np.abs(carrier.distances(points[chosen])))
    return exact


def _inner_walls(
    body: Solid, mesh: MeshData, points: np.ndarray, spots: np.ndarray, tolerance: float
) -> np.ndarray:
    """Welche Netzpunkte eine Wand im Inneren des Körpers sind — eine Naht ohne Volumen.

    Zwei Bedingungen, beide nötig. Der Punkt liegt **im Material** des
    Körpers (``BRepClass3d_SolidClassifier``). Und die Oberfläche des Körpers
    an der nächsten Stelle (``spots``, auf der Messvernetzung) stimmt mit dem
    Netz überein. Ohne die zweite hieße auch ein Körper, der über das Netz
    hinaussteht, „innere Wand“ — dort liegt aber die Oberfläche des Körpers
    weit vom Netz, und das misst die Rückrichtung als Abweichung.
    """
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer

    from app.core.geom.mesh import on_surface

    inside = np.zeros(len(points), dtype=bool)
    if not len(points):
        return inside
    _near, agreement, _triangles = on_surface(mesh.raw, spots)
    agrees = agreement <= CORNER_REACH * tolerance + _MEASURE_SAG
    solids = []
    explorer = TopExp_Explorer(body.shape, TopAbs_SOLID)
    while explorer.More():
        solids.append(explorer.Current())
        explorer.Next()
    for position in np.flatnonzero(agrees).tolist():
        spot = gp_Pnt(*map(float, points[position]))
        inside[position] = any(
            BRepClass3d_SolidClassifier(solid, spot, tolerance).State() == TopAbs_IN
            for solid in solids
        )
    return inside


def _carrier_of_face(face: Any) -> Carrier | None:
    """Die analytische Fläche unter einer Fläche des Körpers als Träger — oder ``None``."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import (
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    )

    def triple(value: Any) -> tuple[float, float, float]:
        return (float(value.X()), float(value.Y()), float(value.Z()))

    adaptor = BRepAdaptor_Surface(face)
    kind = adaptor.GetType()
    if kind == GeomAbs_Plane:
        plane = adaptor.Plane()
        return Carrier("plane", triple(plane.Location()), triple(plane.Axis().Direction()))
    if kind == GeomAbs_Cylinder:
        cylinder = adaptor.Cylinder()
        return Carrier(
            "cylinder",
            triple(cylinder.Location()),
            triple(cylinder.Axis().Direction()),
            radius=float(cylinder.Radius()),
        )
    if kind == GeomAbs_Cone:
        cone = adaptor.Cone()
        # OpenCASCADE misst den Halbwinkel mit Vorzeichen entlang seiner Achse;
        # der Träger zeigt von der Spitze in den Mantel.
        axis = np.asarray(triple(cone.Axis().Direction()))
        angle = float(cone.SemiAngle())
        return Carrier(
            "cone",
            triple(cone.Apex()),
            (float(axis[0]), float(axis[1]), float(axis[2]))
            if angle > 0.0
            else (float(-axis[0]), float(-axis[1]), float(-axis[2])),
            angle=abs(angle),
        )
    if kind == GeomAbs_Sphere:
        sphere = adaptor.Sphere()
        return Carrier(
            "sphere", triple(sphere.Location()), (0.0, 0.0, 1.0), radius=float(sphere.Radius())
        )
    if kind == GeomAbs_Torus:
        torus = adaptor.Torus()
        return Carrier(
            "torus",
            triple(torus.Location()),
            triple(torus.Axis().Direction()),
            radius=float(torus.MajorRadius()),
            tube=float(torus.MinorRadius()),
        )
    return None


def body_to_mesh(body: Solid, mesh: MeshData, fine: MeshData) -> tuple[float, np.ndarray | None]:
    """Größter Abstand eines Körperpunkts zum Netz — an Stichproben auf den exakten Flächen.

    Gemessen wird nicht an den Knoten einer Vernetzung: Ein Zylindermantel
    wird entlang seiner Achse nicht unterteilt, seine Knoten liegen alle auf
    den zwei Randkreisen — also auf den ebenen Deckflächen des Netzes, im
    Abstand null. An ``plate_holes.stl`` ergab das 7,9·10⁻⁷ mm, während der
    Mantel auf halber Höhe um die Sehnenhöhe des 48-Ecks (0,0056 mm) neben
    dem Netz liegt. Stattdessen bekommt jedes Dreieck einer feinen Vernetzung
    Stichproben (:data:`_BODY_SAMPLES`), jede auf die exakte Fläche seiner
    Körperfläche projiziert; ihr Abstand zum Netz ist exakt
    gerechnet, nur dort, wo er das Maximum heben kann
    (:func:`app.core.geom.mesh.farthest_from_surface`). Eine Stichprobe, und
    die Zahl heißt so.

    **Ebene Flächen nur an ihren Ecken.** Ihr Inneres liegt auf der Ebene,
    die die Dreiecke ihres Bereichs trägt; wie weit diese davon abliegen,
    misst die Gegenrichtung an zehn Stellen je Dreieck. Neu an einer Ebene
    ist nur ihr Rand mit den gezogenen Ecken. Am Besenhalter aus dem
    Kundenordner (12 148 Ebenen) kostete das Innere 27 der 31 Sekunden dieser
    Messung.
    """
    from app.core.brep.kernel import _FACE_ATTRIBUTE
    from app.core.geom.mesh import farthest_from_surface

    corners = np.asarray(fine.raw.triangles, dtype=np.float64)
    if not len(corners):
        return 0.0, None
    owners = np.asarray(fine.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
    if len(owners) != len(corners):
        points = np.einsum("sk,tkj->tsj", _BODY_SAMPLES, corners).reshape(-1, 3)
    else:
        faces = body.faces()
        flat = np.zeros(len(corners), dtype=bool)
        parts: list[np.ndarray] = []
        for index in np.unique(owners).tolist():
            chosen = owners == index
            carrier = _carrier_of_face(faces[index]) if 0 <= index < len(faces) else None
            if carrier is not None and carrier.kind == "plane":
                flat |= chosen
                continue
            samples = np.einsum("sk,tkj->tsj", _BODY_SAMPLES, corners[chosen]).reshape(-1, 3)
            parts.append(samples if carrier is None else carrier.projected(samples))
        if flat.any():
            used = np.unique(np.asarray(fine.raw.faces, dtype=np.int64)[flat])
            parts.append(np.asarray(fine.raw.vertices, dtype=np.float64)[used])
        points = np.concatenate(parts) if parts else np.zeros((0, 3))
    if not len(points):
        return 0.0, None
    worst, where = farthest_from_surface(mesh.raw, points)
    return float(worst), (None if where is None else points[where])


def source_deviation(
    body: Solid,
    reference: ConversionReference,
    *,
    cancelled: CancelToken | None = None,
    progress: Callable[[float], None] | None = None,
) -> SampledDeviation:
    """Die Abweichung je Dreieck der Darstellung — für die Karte „Formabweichung“ (P1.6).

    Beide Richtungen, auf dieselben Dreiecke gelegt: Jedes Dreieck der
    Darstellung bekommt den größten Abstand seiner Stichproben (auf die exakte
    Fläche projiziert) zum Netz, und jeder Punkt des Netzes — Ecken und
    Dreiecksmitten — seinen Abstand zur exakten Fläche des Dreiecks, das ihm
    am nächsten liegt. Die Karte zeigt so auch eine Stelle, an der der Körper
    eine Rundung abschneidet, die das Netz noch hatte. Innere Wände des
    Netzes (:func:`_inner_walls`) färben nichts: Sie liegen im Körper, und
    außen stimmt er dort mit dem Netz überein.
    """
    from app.core.brep.kernel import _FACE_ATTRIBUTE
    from app.core.geom.deviation import SampledDeviation
    from app.core.geom.mesh import on_surface, surface_index

    def advance(fraction: float) -> None:
        _check(cancelled)
        if progress is not None:
            progress(fraction)

    advance(0.0)
    display = body.mesh
    triangles = np.asarray(display.raw.triangles, dtype=np.float64)
    count = len(triangles)
    owners = np.asarray(display.raw.face_attributes.get(_FACE_ATTRIBUTE, ()), dtype=np.int64)
    if len(owners) != count:
        owners = np.full(count, -1, dtype=np.int64)
    faces = body.faces()
    carriers = [_carrier_of_face(face) for face in faces]
    # Körper → Netz: Stichproben der Darstellung, auf die exakte Fläche gelegt.
    samples = np.einsum("sk,tkj->tsj", _BODY_SAMPLES, triangles)
    for index in np.unique(owners).tolist():
        carrier = carriers[index] if 0 <= index < len(carriers) else None
        if carrier is None:
            continue
        chosen = owners == index
        samples[chosen] = carrier.projected(samples[chosen].reshape(-1, 3)).reshape(
            -1, len(_BODY_SAMPLES), 3
        )
    advance(0.1)
    points = samples.reshape(-1, 3)
    distances = np.empty(len(points))
    block = 65_536
    # Ein Suchbaum je Netz für alle Portionen, nicht einer je Portion (RM-260).
    reference_index = surface_index(reference.mesh.raw)
    for start in range(0, len(points), block):
        advance(0.1 + 0.4 * start / max(len(points), 1))
        _spots, found, _hit = on_surface(
            reference.mesh.raw, points[start : start + block], index=reference_index
        )
        distances[start : start + block] = found
    per_sample = distances.reshape(count, len(_BODY_SAMPLES))
    values = per_sample.max(axis=1) if count else np.zeros(0)
    from_body = float(values.max()) if count else 0.0
    witness: np.ndarray | None = None
    witness_face: int | None = None
    if count:
        flat = int(np.argmax(per_sample))
        witness_face = flat // len(_BODY_SAMPLES)
        witness = points[flat]
    # Netz → Körper: Ecken und Mitte jedes Netzdreiecks, gegen die exakte
    # Fläche des nächsten Dreiecks der Darstellung.
    raw = reference.mesh.raw
    corners = np.asarray(raw.triangles, dtype=np.float64)
    probes = np.concatenate((corners, corners.mean(axis=1)[:, None, :]), axis=1).reshape(-1, 3)
    probe_triangle = np.repeat(np.arange(len(corners)), 4)
    nearest = np.empty(len(probes), dtype=np.int64)
    gaps = np.empty(len(probes))
    spots = np.empty((len(probes), 3))
    display_index = surface_index(display.raw)
    for start in range(0, len(probes), block):
        advance(0.5 + 0.4 * start / max(len(probes), 1))
        spot, found, hit = on_surface(
            display.raw, probes[start : start + block], index=display_index
        )
        nearest[start : start + block] = hit
        gaps[start : start + block] = found
        spots[start : start + block] = spot
    exact = _exact_to_body(body, display, probes, gaps, nearest, body.deflection)
    own = reference.own_mm[probe_triangle] if len(reference.own_mm) == len(corners) else exact
    odd = np.flatnonzero(exact > own + body.deflection)
    if len(odd):
        walls = _inner_walls(body, reference.mesh, probes[odd], spots[odd], reference.tolerance)
        exact[odd[walls]] = 0.0
    to_body = float(exact.max()) if len(exact) else 0.0
    if count and len(exact):
        np.maximum.at(values, nearest, exact)
        if to_body > from_body:
            where = int(np.argmax(exact))
            witness_face = int(nearest[where])
            witness = spots[where]
    advance(1.0)
    return SampledDeviation(
        values_mm=values,
        to_body_mm=to_body,
        from_body_mm=from_body,
        witness=None
        if witness is None
        else (float(witness[0]), float(witness[1]), float(witness[2])),
        witness_face=witness_face,
    )


def convert(
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    *,
    tolerance: float,
    cancelled: CancelToken | None = None,
    progress: Callable[[float, str], None] | None = None,
) -> Conversion:
    """Das Netz als exakter Körper — gemessen, nie still geglättet.

    ``features`` ist die Erkennung dieses Netzes (dieselben Dreiecksnummern).
    ``tolerance`` ist die größte zulässige Entfernung einer Netzecke von ihrem
    Träger. Wirft ``OpenSurfaceError`` an einem offenen oder widersprüchlich
    orientierten Netz und ``ConversionRefusedError`` mit Grund, wo ein exakter
    Körper nichts Brauchbares wäre.
    """
    from app.core.brep.edit import unified
    from app.core.brep.kernel import require
    from app.core.geom.mesh import fully_stitched
    from app.core.geom.repair import merge_vertices

    require()

    def report(fraction: float, stage: str) -> None:
        _check(cancelled)
        if progress is not None:
            progress(fraction, stage)

    report(0.0, "regions")
    if not fully_stitched(mesh.raw):
        mesh, _gone = merge_vertices(mesh)
    if not mesh.is_watertight:
        raise OpenSurfaceError
    regions = surface_regions(mesh, features, tolerance, cancelled=cancelled)
    regions, _straightened = regularized(mesh, regions, tolerance, cancelled=cancelled)
    freeform = regions.facet_triangles()
    if len(freeform) > MAX_FREEFORM_FACES:
        raise ConversionRefusedError("freeform", triangles=len(freeform))
    report(0.3, "regions")
    demoted = 0
    built: _Built | None = None
    built_faces: dict[bytes, Any] = {}
    for _attempt in range(4):
        try:
            built = _build(mesh, regions, tolerance, cancelled, report, built_faces)
            break
        except (ValueError, RuntimeError) as problem:
            # Ein einzelnes Dreieck, das keine Fläche ergibt, oder eine
            # Ausnahme aus OpenCASCADE: kein Bereich, den ein Herabstufen
            # retten könnte. Der Grund kommt ins Protokoll, dem Kunden sagt
            # die Absage, was er tun kann.
            _log.warning("mesh conversion could not build the body: %r", problem)
            raise ConversionRefusedError("unbuildable") from problem
        except _RegionFailedError as failure:
            demoted += len(failure.regions)
            regions = _demoted(mesh, regions, failure.regions)
            if len(regions.facet_triangles()) > MAX_FREEFORM_FACES:
                raise ConversionRefusedError(
                    "freeform", triangles=len(regions.facet_triangles())
                ) from failure
    if built is None:
        raise ConversionRefusedError("unbuildable")
    try:
        body = _checked_body(built.shape, built.face_slots)
        joined = unified(body)
        if joined.is_closed and joined.solid_count == body.solid_count:
            body = joined
        # Das Netz reist am Körper mit, bevor irgendetwas an ihm gemerkt wird
        # (Volumen, Vernetzung): ``replace`` baut einen neuen Körper, und der
        # fängt mit leerem Merker an.
        own = _own_distances(mesh, regions, built.moved)
        body = replace(body, converted_from=ConversionReference(mesh, own, tolerance))
    except ValueError as problem:
        _log.warning("mesh conversion built an invalid body: %s", problem)
        raise ConversionRefusedError("invalid") from problem
    report(0.85, "measure")
    facets = regions.facet_triangles()
    areas = np.asarray(mesh.raw.area_faces, dtype=np.float64)
    total_area = float(areas.sum())
    share = float(areas[facets].sum() / total_area) if total_area > 0.0 else 0.0
    fine = body.to_mesh(deflection=_MEASURE_SAG)
    to_body, near_body, inner = _mesh_to_body(mesh, own, body, fine, tolerance, cancelled)
    report(0.92, "measure")
    from_body, near_mesh = body_to_mesh(body, mesh, fine)
    worst = near_body if to_body >= from_body else near_mesh
    report(1.0, "measure")
    return Conversion(
        solid=body,
        faces=_face_kinds(body, regions),
        freeform_share=share,
        freeform_triangles=len(facets),
        mesh_to_body=to_body,
        body_to_mesh=from_body,
        worst=None if worst is None else (float(worst[0]), float(worst[1]), float(worst[2])),
        rejected=regions.rejected,
        demoted=demoted,
        inner_walls=inner,
        volume_mesh=float(mesh.volume),
        volume_body=float(body.volume),
    )


#: Wie fein der Körper für die Rückrichtung vernetzt wird: die halbe
#: Sehnenhöhe, mit der der exakte Kern sonst tesselliert. Die Abweichung
#: sitzt über den Facetten des **Netzes**, und die Stichproben müssen so dicht
#: liegen wie sie, nicht dichter: Am Ring aus ``torus_ring.stl`` gab ein
#: Zehntel der Sehnenhöhe 22 436 Dreiecke und 2,1 s für 0,09565 mm, die Hälfte
#: 9 000 Dreiecke und 0,7 s für 0,09538 mm — die Gegenrichtung misst dort
#: 0,09566 mm.
_MEASURE_SAG: Final = 0.5 * MAX_FACET_SAG


@dataclass(frozen=True, slots=True)
class Conversion:
    """Der exakte Körper und was an ihm gemessen wurde."""

    solid: Solid
    faces: Mapping[str, int]
    """Flächen nach Art: ``plane``, ``cylinder``, ``cone``, ``sphere``, ``torus``,
    ``bspline`` und ``facet`` für die ebenen Dreiecke des Freiformrests."""
    freeform_share: float
    """Anteil der Netzoberfläche, der ohne erkannten Träger als ebene Dreiecke
    in den Körper ging, zwischen 0 und 1."""
    freeform_triangles: int
    mesh_to_body: float
    """Größter Abstand eines Netzpunkts zum Körper in mm (Netz → Körper)."""
    body_to_mesh: float
    """Größter Abstand eines Körperpunkts zum Netz in mm (Körper → Netz)."""
    worst: Vec3 | None
    """Wo der größte Abstand liegt — dorthin fliegt die Ansicht."""
    rejected: tuple[tuple[str, float], ...] = ()
    """Erkannte Merkmale, deren Träger die Toleranz nicht hielt."""
    demoted: int = 0
    """Bereiche, deren Fläche sich nicht bauen ließ und die als Dreiecke eingingen."""
    inner_walls: int = 0
    """Dreiecke des Netzes, die im Inneren des Körpers lagen — eine Naht ohne
    Volumen, die der Körper nicht übernimmt (siehe :func:`_inner_walls`)."""
    volume_mesh: float = 0.0
    volume_body: float = 0.0
