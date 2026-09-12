"""Die **Flächen** eines Netzes bearbeiten — Gegenstück zu :mod:`edges`.

Der exakte Kern greift eine Fläche an ihrer Topologie: Sie ist dort ein Ding
mit einem Rand. Ein Netz hat davon nichts — es hat eine Menge Dreiecke, die
zufällig in einer Ebene liegen, und was der Kunde als Fläche anklickt, ist ein
erkanntes Merkmal (§21) mit genau dieser Dreiecksmenge in ``face_indices``.

**Trotzdem ist es dieselbe Handlung**, und der Weg dahin ist derselbe wie beim
Verrunden: Über der Fläche entsteht ein Prisma ihres eigenen Umrisses, das nach
außen vereinigt und nach innen abgezogen wird. Der exakte Kern tut wörtlich
dasselbe (``brep.profiles.push_faces``) — nur baut er das Prisma aus einer
B-Rep-Fläche und hier entsteht es aus den Dreiecken.

**Der Umriss wird dabei nicht ausgerechnet, sondern übernommen.** Ein Polygon
aus der Dreiecksmenge zu gewinnen hieße, den Rand zu verketten, Löcher zu
erkennen und in eine Ebene zu projizieren — drei Stellen, an denen etwas
schiefgeht, und alle drei ohne Gewinn: Boden und Deckel des Prismas *sind* die
Dreiecke, und der Mantel steht auf den Kanten, die nur zu einem von ihnen
gehören.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from app.core.errors import CANCEL, CHANGE_SELECTION, CORRECT_INPUT, GeometryError, ValidationError
from app.core.geom.boolean import BooleanKind, BooleanOutcome, boolean
from app.core.geom.mesh import MeshData
from app.core.geom.repair import merge_vertices, remove_degenerate_faces
from app.core.types import Feature, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

#: Wie weit die Flächen eines Merkmals von **einer** Ebene abweichen dürfen,
#: damit
#: „versetzen" noch bedeutet, was es sagt.
#:
#: Press/Pull verschiebt eine Fläche entlang **ihrer** Normalen; hat jedes
#: Dreieck eine andere, gibt es diese Richtung nicht. Ein Zylindermantel ist
#: der Fall, den das trifft — dort ist die Handlung nicht zu streng, sondern
#: undefiniert.
SAME_PLANE_ENOUGH = 0.02

#: Wie weit die Normale einer Wand aus der Waagerechten kippen darf und noch
#: als senkrecht gilt. Dieselbe Frage wie ``edges.MeshEdge.flat``, nur an der
#: Fläche statt an der Kante.
UPRIGHT_ENOUGH = 0.1

#: Die Obergrenze der Formschräge, wie im exakten Kern.
MAX_DRAFT_DEGREES = 30.0


def face_normal(feature: Feature) -> Vec3:
    """Die Normale des Merkmals, als Vektor der Länge eins."""
    raw = np.asarray(feature.params.get("normal", (0.0, 0.0, 1.0)), dtype=float)
    length = float(np.linalg.norm(raw))
    if length <= EPS_GEOM:
        raise GeometryError(
            detail=_("Zu dieser Fläche ist keine Richtung bekannt. Wählen Sie sie im Bild erneut."),
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    return tuple(float(value) for value in raw / length)  # type: ignore[return-value]


def push_face(mesh: MeshData, feature: Feature, distance: float) -> BooleanOutcome:
    """Versetzt **eine** Fläche entlang ihrer Normalen; die Nachbarwände wachsen mit.

    ``distance`` zählt nach außen positiv, nach innen negativ — dasselbe
    Werkzeug für beides, wie im exakten Kern.

    **Eine Fläche und nicht alle einer Richtung.** Der exakte Weg nahm bis zum
    10.09.2026 eine Richtung entgegen und bewegte jede Fläche, deren Normale
    dorthin zeigte; an einer Treppe wanderten damit alle Stufen zugleich
    (gemessen: 24000,0 mm³ statt 21000,0). Der Kunde klickt eine Fläche an, und
    genau die ist gemeint (Befund Robert, 10.09.2026).
    """
    if abs(distance) <= EPS_GEOM:
        raise ValidationError(
            "distance",
            _("Ohne Weg bewegt sich nichts — dieser Wert darf nicht null sein."),
            value=distance,
        )
    tool = _prism_over(mesh, feature, distance)
    kind: BooleanKind = "union" if distance > 0.0 else "difference"
    outcome = boolean(kind, [mesh, tool], quality="fine")
    if outcome.mesh.raw.volume <= EPS_GEOM:
        raise GeometryError(
            detail=_(
                "Mit diesem Weg bleibt vom Körper nichts übrig — kleiner "
                "versetzen oder die Richtung umkehren."
            ),
            values={"distance_mm": round(distance, 3)},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return outcome


def _prism_over(mesh: MeshData, feature: Feature, distance: float) -> MeshData:
    """Das Prisma über der Fläche: ihre Dreiecke, verschoben, plus Mantel.

    Gebaut wird von Hand statt über ``trimesh.creation``: Boden und Deckel
    sind die Dreiecke selbst, der Mantel steht auf den Randkanten. Das trifft
    jeden Umriss — auch einen mit Loch —, ohne ihn je als Polygon zu sehen.
    """
    triangles = _triangles_of(mesh, feature)
    normal = np.asarray(face_normal(feature), dtype=float)
    _must_be_flat(mesh, triangles, normal)
    # **Mit Vorzeichen und nicht mit Betrag.** Nach innen versetzen heißt, das
    # Prisma ins Material zu legen und abzuziehen; mit ``abs`` stand es außen,
    # die Differenz traf nichts, und der Körper kam unverändert zurück —
    # wasserdicht, einteilig, 24000 mm³ statt 18000.
    return _prism_from(mesh, triangles, lambda _points: normal * distance)


def _prism_from(
    mesh: MeshData,
    triangles: list[int],
    offset: Callable[[np.ndarray], np.ndarray],
) -> MeshData:
    """Das Prisma über einer Dreiecksmenge, mit **einem Versatz je Knoten**.

    ``offset`` bekommt die Knoten der Fläche als Feld und gibt zurück, wohin
    jeder von ihnen wandert. Ein fester Vektor macht daraus das gerade Prisma
    des Versetzens; ein Versatz, der mit der Höhe wächst, macht daraus den Keil
    der Formschräge. Beide Handlungen unterscheidet sonst nichts, und zwei
    Fassungen wären zwei Stellen für dieselbe Umlaufrichtung.
    """
    import trimesh

    corners = np.asarray(mesh.raw.faces, dtype=np.int64)[triangles]
    used = np.unique(corners)
    # Die Knoten neu nummerieren, damit das Prisma für sich steht.
    fresh = {int(old): index for index, old in enumerate(used.tolist())}
    below = np.asarray(mesh.raw.vertices, dtype=float)[used]
    above = below + offset(below)
    count = len(below)

    faces: list[tuple[int, int, int]] = []
    for a, b, c in corners.tolist():
        low = (fresh[a], fresh[b], fresh[c])
        # Der Boden zeigt nach innen, der Deckel nach außen — sonst wäre der
        # Körper von innen nach außen gestülpt und hätte negatives Volumen.
        faces.append((low[0], low[2], low[1]))
        faces.append((low[0] + count, low[1] + count, low[2] + count))

    for first, second in _border_edges(corners):
        low_a, low_b = fresh[first], fresh[second]
        faces.append((low_a, low_b, low_b + count))
        faces.append((low_a, low_b + count, low_a + count))

    body = trimesh.Trimesh(
        vertices=np.vstack([below, above]), faces=np.asarray(faces, dtype=np.int64)
    )
    body.fix_normals()
    # **Zeigt der Versatz ins Material, steht der Körper auf links.** Die
    # Umlaufrichtung von Boden und Deckel ist für einen Versatz nach außen
    # gebaut; kehrt er sich um, kommt derselbe Keil mit **negativem** Volumen
    # heraus (gemessen -419,262 statt 419,262). ``fix_normals`` richtet dabei
    # nur die Nachbarn zueinander aus, nicht die Richtung des Ganzen — und für
    # ``manifold3d`` ist so ein Körper kein „positive closed volume", worauf
    # die Kette bis zur Voxelstufe durchfällt: 4,8 Sekunden statt 30 ms, und
    # das Ergebnis 0,13 % daneben.
    if body.volume < 0.0:
        body.invert()
    # **Wo der Versatz auf null läuft, liegen Boden und Deckel aufeinander.**
    # Bei der Formschräge ist das die ganze neutrale Kante: Dort hat der Keil
    # keine Dicke, und die Dreiecke des Mantels haben keine Fläche. Ein solcher
    # Körper ist für ``manifold3d`` kein „positive closed volume", die Kette
    # fällt bis auf die Voxelstufe durch — gemessen 4,8 Sekunden für einen
    # Quader und ein Ergebnis, das 0,13 % daneben lag. Verschweißt und von den
    # entarteten Dreiecken befreit ist es derselbe Keil, den die erste Stufe
    # in Millisekunden nimmt.
    welded, _seams = merge_vertices(MeshData(body))
    cleaned, _flat = remove_degenerate_faces(welded)
    return cleaned


def _triangles_of(mesh: MeshData, feature: Feature) -> list[int]:
    """Die Dreiecke des Merkmals — und ein Satz, wenn sie nicht mehr passen.

    Ein Index in eine Dreiecksliste altert (§21.2): Ein Schritt davor kann das
    Netz neu vernetzt haben, und dann zeigt er auf etwas anderes oder ins
    Leere. Das ist eine Auskunft an den Kunden und kein Programmfehler.
    """
    total = len(mesh.raw.faces)
    chosen = [int(index) for index in feature.face_indices if 0 <= int(index) < total]
    if not chosen or len(chosen) != len(feature.face_indices):
        raise GeometryError(
            detail=_(
                "Diese Fläche gibt es an dem Körper nicht mehr — ein Schritt davor "
                "hat ihn verändert. Wählen Sie sie neu."
            ),
            values={"faces": len(feature.face_indices)},
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    return chosen


def _must_be_flat(mesh: MeshData, triangles: list[int], normal: np.ndarray) -> None:
    """Hält an, wo „entlang ihrer Normalen" keine Richtung mehr benennt."""
    normals = np.asarray(mesh.raw.face_normals, dtype=float)[triangles]
    if float(np.min(normals @ normal)) < 1.0 - SAME_PLANE_ENOUGH:
        raise GeometryError(
            detail=_(
                "Diese Fläche ist gewölbt — versetzen lässt sich nur eine ebene. "
                "Wählen Sie eine ebene Fläche, oder ändern Sie das Merkmal über "
                "seine Maße."
            ),
            suggestions=(CHANGE_SELECTION, CANCEL),
        )


def _border_edges(corners: np.ndarray) -> list[tuple[int, int]]:
    """Die Kanten, die nur zu einem der Dreiecke gehören — der Rand.

    Ein Loch in der Fläche gehört dazu und braucht keinen eigenen Fall: Seine
    Kanten liegen ebenso nur an einem Dreieck, der Mantel entsteht dort
    genauso, und die Orientierung kommt aus der Umlaufrichtung des Dreiecks.
    """
    seen: dict[tuple[int, int], int] = {}
    order: dict[tuple[int, int], tuple[int, int]] = {}
    for a, b, c in corners.tolist():
        for first, second in ((a, b), (b, c), (c, a)):
            key = (min(first, second), max(first, second))
            seen[key] = seen.get(key, 0) + 1
            order.setdefault(key, (first, second))
    return [order[key] for key, times in seen.items() if times == 1]


def draft_vertical(mesh: MeshData, angle_deg: float) -> BooleanOutcome:
    """Stellt alle senkrechten Flächen um den Winkel an — die Formschräge.

    Neutral bleibt die Unterkante des Körpers: Dort behält der Körper sein
    Maß, nach oben wird er schmaler. Wörtlich dieselbe Zusage wie im exakten
    Kern (``brep.profiles.draft_vertical``), damit dieselbe Menüzeile an
    beiden Körperarten dasselbe bedeutet.

    Gebaut wird je Wand ein **Keil**: das Prisma über ihren Dreiecken, dessen
    Deckel mit der Höhe über der Unterkante nach innen wandert. Alle Keile zusammen
    werden in einem Zug abgezogen; an den Ecken überlappen sie sich, und genau
    das ist der Grund für den einen Zug — die Überlappung löst die Boolesche
    Rechnung, und niemand muss die Ecke eigens ausrechnen.
    """
    if not 0.0 < angle_deg <= MAX_DRAFT_DEGREES:
        raise ValidationError(
            "angle",
            _("Der Winkel muss zwischen null und 30 Grad liegen."),
            value=angle_deg,
        )
    upright = _upright_faces(mesh)
    if not upright:
        raise GeometryError(detail=_("Dieser Körper hat keine senkrechten Flächen."))

    slope = math.tan(math.radians(angle_deg))
    bottom = mesh.bounds.minimum[2]
    tools: list[MeshData] = []
    for triangles, normal in upright:

        def _wedge(points: np.ndarray, normal: np.ndarray = normal) -> np.ndarray:
            return -np.outer(np.maximum(points[:, 2] - bottom, 0.0) * slope, normal)

        tools.append(_prism_from(mesh, triangles, _wedge))

    outcome = boolean("difference", [mesh, *tools], quality="fine")
    if outcome.mesh.raw.volume <= EPS_GEOM:
        raise GeometryError(
            detail=_("Mit diesem Winkel bleibt vom Körper nichts übrig — kleiner anstellen."),
            values={"angle_deg": round(angle_deg, 2)},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return outcome


def _upright_faces(mesh: MeshData) -> list[tuple[list[int], np.ndarray]]:
    """Die senkrechten Flächen des Netzes, jede mit ihrer Normalen.

    Gefragt wird die Merkmalserkennung und nicht ``face_normals`` direkt: Eine
    Wand aus zwei Dreiecken ist **eine** Fläche, und ihr Keil entsteht in einem
    Stück. Über die Dreiecke gerechnet wären es zwei Keile mit einer
    gemeinsamen Kante — zweimal dieselbe Arbeit und eine Naht mehr, an der die
    Boolesche Rechnung stolpern kann.
    """
    from app.core.perceive.features import detect

    found: list[tuple[list[int], np.ndarray]] = []
    for feature in detect(mesh).values():
        if feature.kind != "face" or not feature.face_indices:
            continue
        normal = np.asarray(face_normal(feature), dtype=float)
        if abs(float(normal[2])) > UPRIGHT_ENOUGH:
            continue
        found.append(([int(index) for index in feature.face_indices], normal))
    return found
