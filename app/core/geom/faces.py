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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any, Final

import numpy as np

from app.core import units
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CORRECT_INPUT,
    REPAIR_AND_RETRY,
    GeometryError,
    ValidationError,
)
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    BooleanKind,
    BooleanOutcome,
    boolean,
    deepest,
)
from app.core.geom.mesh import MeshData
from app.core.geom.repair import (
    merge_vertices,
    remove_degenerate_faces,
    remove_doubled_faces,
    remove_hollow_shells,
)
from app.core.geom.section import settled_on_plane
from app.core.types import CancelToken, Feature, FeatureId, Finding, Quality, Vec3
from app.core.units import EPS_GEOM, MAX_FACET_SAG
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

#: Wie weit eine Ecke einer gewählten ebenen Fläche neben ihrer Ebene liegen
#: darf, wenn ein Werkzeug flach auf diese Ebene gelegt wird — ein Muster bis
#: zum Rand, eine Dichtnut in der Trägerfläche.
#:
#: **Nicht ``EPS_GEOM``.** Eine STL speichert vier Byte je Koordinate, und
#: eine schräge Fläche liegt nach dem Einlesen um deren Rundung neben ihrer
#: Ebene: 5·10⁻⁵ mm an der Keilfläche von ``Wedge-Lock (Base).stl`` (gemessen
#: am 22.09.2026), zwanzigmal ``EPS_GEOM``. *Muster bis zum Rand* lehnte die
#: Fläche daraufhin als „nicht eben" ab, obwohl die Erkennung sie als Ebene
#: führte. Achsparallele Flächen fielen nicht auf, weil dort alle Ecken
#: dieselbe gerundete Zahl tragen.
#:
#: Die Grenze kommt aus dem, was das Werkzeug aushält: Es greift um
#: ``BOOLEAN_OVERLAP`` in den Körper, und von diesem Überlapp bleiben bei einer
#: Ecke ein Viertel daneben noch drei Viertel. Eine gewölbte Fläche liegt um
#: Millimeter neben jeder Ebene und bleibt abgelehnt.
FLAT_ENOUGH_FOR_A_TOOL: Final = BOOLEAN_OVERLAP / 4.0

#: Wie weit die Normale einer Wand aus der Waagerechten kippen darf und noch
#: als senkrecht gilt. Dieselbe Frage wie ``edges.MeshEdge.flat``, nur an der
#: Fläche statt an der Kante.
UPRIGHT_ENOUGH = 0.1

#: Die Obergrenze der Formschräge, wie im exakten Kern.
MAX_DRAFT_DEGREES = 30.0

#: Der Satz beider Kerne, wenn eine angestellte Fläche durch anderes Material
#: läuft — am Netz aus der Volumenbilanz der Werkzeuge, am exakten Körper aus
#: seiner Gültigkeitsprüfung (P6.4).
DRAFT_CUTS_THROUGH = _(
    "Mit diesem Winkel läuft eine angestellte Fläche durch anderes Material — eine Wand "
    "würde dünner als null. Stellen Sie einen kleineren Winkel ein, oder wählen Sie "
    "weniger Flächen."
)

#: Der Satz beider Kerne, wenn an einer angestellten Wand quer zur
#: Entformungsrichtung eine Verrundung anschließt (RM-230). OpenCASCADE rechnet
#: sie neben der gekippten Wand nicht nach (``Draft_FaceRecomputation``), und das
#: Netz behielt sie mit Knick oder sagte je nach Winkel ab. Gefragt wird deshalb
#: vor der Rechnung, an beiden Kernen gleich (:func:`_round_beside_the_walls`,
#: ``brep.profiles._tangent_chain``). Ein kleinerer Winkel hilft dort nicht. Der
#: Weg einer CAD-Konstruktion — Rundung weg, anstellen, neu runden — trägt hier
#: noch nicht: Eine Fußrundung in einer Kette mit Eckstücken entfernt *Merkmal
#: entfernen* nicht (RM-230). Der Satz nennt deshalb nur, was hilft.
DRAFT_BESIDE_A_ROUND = _(
    "An einer angestellten Wand liegt quer zur Entformungsrichtung eine Verrundung an, "
    "etwa unten am Fuß. Neben ihr lässt sich die Schräge nicht anlegen. Wählen Sie nur "
    "Wände ohne diese Verrundung."
)

#: Der Satz des exakten Kerns, wenn ohne Kante eine stehende Fläche anschließt,
#: die sich nicht mit anstellen lässt — eine frei geformte Ecke (B-Spline) oder ein
#: fast stehender Zylinder (Review RM-230, F3). ``BRepOffsetAPI_DraftAngle``
#: ließ sie still senkrecht stehen, und die gekippten Wände schnitten sich in sie
#: ein: An der Ecke gab es keine Schräge, genau dort klemmt das Teil. Am Netz
#: sind solche Ecken Streifen; ihr Zwilling sagt an der B-Spline-Ecke ebenfalls
#: ab, aber mit dem Ecksatz und dem Rat zum Winkel (``_moved_corners``) — die
#: Kerne sind dort uneins im Satz (RM-230, „Kerne uneins“). Eine schon
#: angestellte gerundete Ecke ist ein Kegel und geht mit
#: (``profiles._tangent_chain``, Review P2 G2, G4).
DRAFT_BESIDE_A_FREE_FACE = _(
    "An einer angestellten Wand schließt ohne Kante eine gewölbte Fläche an, die sich "
    "nicht mit anstellen lässt, etwa eine frei geformte Ecke. Wählen Sie nur Wände, an "
    "die keine solche Fläche anschließt."
)


def leaning_band(along: np.ndarray) -> np.ndarray:
    """Welche Flächen schräg zur Entformungsrichtung liegen, aus ``n · d`` je
    Fläche — weder Wand noch Boden oder Decke, wie ein Streifen einer liegenden
    Rundung. Die eine Stelle für das Band beider Kerne (:func:`leans_across`)."""
    magnitude = np.abs(np.asarray(along, dtype=np.float64))
    return (magnitude >= UPRIGHT_ENOUGH) & (magnitude <= 1.0 - UPRIGHT_ENOUGH)


def leans_across(normal: units.Indexable3, pull: units.Indexable3) -> bool:
    """Ob eine Fläche schräg zur Entformungsrichtung liegt (:func:`leaning_band`)."""
    return bool(leaning_band(np.asarray([float(units.dot3(normal, pull))]))[0])


#: Wie viele senkrechte Wände die Formschräge über die Merkmalserkennung
#: hinaus ergänzt — gezählt werden die **ergänzten**, nicht die Summe.
#:
#: Die Erkennung beantwortet „was kann der Kunde anklicken" und verwirft dabei
#: kleine Flächen (``MIN_FACE_AREA``, ``BROAD_FACE_SHARE``). Für diese
#: Operation ist das die falsche Frage — an ``plate_cm.stl``, einem Quader von
#: 8 auf 5 auf 0,5, sind die beiden schmalen Wände 2,5 mm² groß und damit kein
#: Merkmal. Die Erkennung findet damit vier der sechs Flächen, davon zwei
#: senkrechte — und genau die zwei stellte die Formschräge an (Befund
#: Robert, 18.09.2026: „ganzes Modell gewählt nur 2 seiten verändern sich").
#:
#: **Ergänzt wird trotzdem nicht unbegrenzt**, und die Grenze ist gemessen: Ein
#: facettierter Bohrungsmantel besteht aus lauter ebenen senkrechten Streifen,
#: die kein Merkmal beansprucht. An ``plate_countersunk.stl`` sind das 48
#: Streifen zu vier erkannten Wänden, und jeden davon anzustellen zerlegt die
#: Bohrung: Ihr Rand bei z = 1 mm kommt statt als **eine** Kontur als
#: **22** zurück, acht davon ohne Ausdehnung (gemessen 18.09.2026).
#:
#: **Und keine Kennzahl verrät es.** Der Körper bleibt geschlossen, die Kette
#: bleibt auf Stufe ``welded``, und das Volumen geht von 18635,703 auf
#: 18622,288 mm³ — dreizehn Kubikmillimeter, also nichts, was auffiele. Wer
#: die Grenze anhebt, prüft deshalb die **Ränder** und nicht das Volumen.
#: (Der frühere Vermerk hier sagte, die Rückfallkette falle bis zur Voxelstufe
#: durch und gebe dort auf. Das stimmte, bevor die Ergänzung Nullnormalen und
#: gewölbte Gruppen aussortierte; heute rechnet sie durch und liefert einen
#: Körper, dem man das Falsche nicht ansieht — die schlechtere Lage.)
#:
#: Zwölf ist der gröbste Zylinder, den noch jemand als Vieleck zeichnet;
#: darüber ist die Ergänzung unzuverlässig, und dann bleibt es bei der
#: Erkennung, die dafür gebaut ist.
MOST_WALLS_TO_GUESS = 12


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


def pushed_features(
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    chosen: Feature,
    distance: float,
) -> dict[FeatureId, Feature]:
    """Wo die ebenen Flächen nach dem Versetzen liegen — die gewählte und ihre Nachbarn.

    **Die Operation weiß es, die Zuordnung müsste es raten** (23.09.2026).
    Die gewählte Fläche wandert um den Weg entlang ihrer Normalen, und jede
    ebene Nachbarwand wächst um einen Streifen: so lang wie die gemeinsame
    Kante, so breit, wie der Weg in ihrer Ebene reicht. An einer Platte
    60 x 40 x 10, Oberseite 5 mm hinaus, wuchsen die Seiten um die Hälfte,
    ihre Mitte stieg um 2,5 mm — die Zuordnung fand sie nicht wieder, und am
    Netz standen vier ``perceive.orphaned``, am exakten Körper vier stille
    Umbenennungen. Mit den erwarteten Maßen findet sie beide Kerne.

    ``mesh`` ist das Netz, dessen Dreiecke ``face_indices`` benennt — am
    exakten Körper seine Tessellierung. Gekrümmte Nachbarn bekommen keine
    Erwartung; sie ordnet die Auswertung zu wie jede andere Fläche.
    """
    from app.core.units import weld_digits, weld_tolerance

    normal = np.asarray(chosen.params["normal"], dtype=np.float64)
    normal /= max(float(np.linalg.norm(normal)), EPS_GEOM)
    centre = np.asarray(chosen.params["centre"], dtype=np.float64) + normal * distance
    moved: dict[FeatureId, Feature] = {
        chosen.id: _expected_face(chosen, centre, float(chosen.params.get("area", 0.0)))
    }
    triangles = np.asarray(mesh.raw.triangles, dtype=np.float64)
    digits = weld_digits(weld_tolerance(mesh.bounds.diagonal))

    def rim(indices: tuple[int, ...]) -> dict[tuple[tuple[float, ...], ...], np.ndarray]:
        """Die Randkanten einer Dreiecksmenge, geschlüsselt über gerundete Ecken."""
        counted: dict[tuple[tuple[float, ...], ...], list[np.ndarray]] = {}
        for index in indices:
            if not 0 <= index < len(triangles):
                continue
            corners = triangles[index]
            for first, second in ((0, 1), (1, 2), (2, 0)):
                a, b = corners[first], corners[second]
                key = tuple(sorted((tuple(np.round(a, digits)), tuple(np.round(b, digits)))))
                counted.setdefault(key, []).append(np.stack((a, b)))
        return {key: found[0] for key, found in counted.items() if len(found) == 1}

    chosen_rim = rim(chosen.face_indices)
    for name, other in features.items():
        if (
            name == chosen.id
            or other.kind != "face"
            or not other.face_indices
            or not isinstance(other.params.get("normal"), tuple | list)
        ):
            continue
        shared = [chosen_rim[key] for key in rim(other.face_indices) if key in chosen_rim]
        if not shared:
            continue
        lengths = np.array([float(np.linalg.norm(b - a)) for a, b in shared])
        length = float(lengths.sum())
        if length <= EPS_GEOM:
            continue
        middle = (
            sum(
                ((a + b) / 2.0 * weight for (a, b), weight in zip(shared, lengths, strict=True)),
                start=np.zeros(3),
            )
            / length
        )
        a, b = shared[int(np.argmax(lengths))]
        along = (b - a) / float(np.linalg.norm(b - a))
        side = np.asarray(other.params["normal"], dtype=np.float64)
        inward = np.cross(side, along)
        inward /= max(float(np.linalg.norm(inward)), EPS_GEOM)
        if float(inward @ normal) < 0.0:
            inward = -inward
        reach = float(inward @ normal)
        if reach <= 0.1:
            continue
        width = distance / reach
        area = float(other.params.get("area", 0.0))
        strip = length * width
        grown = area + strip
        if area <= EPS_GEOM or grown <= EPS_GEOM:
            continue
        old_centre = np.asarray(other.params["centre"], dtype=np.float64)
        new_centre = (area * old_centre + strip * (middle + inward * width / 2.0)) / grown
        moved[name] = _expected_face(other, new_centre, grown)
    return moved


def _expected_face(feature: Feature, centre: np.ndarray, area: float) -> Feature:
    """Ein Flächenmerkmal mit neuer Mitte und Fläche, als Erwartung der Operation."""
    params = {
        **feature.params,
        "centre": (float(centre[0]), float(centre[1]), float(centre[2])),
    }
    if "area" in feature.params:
        params["area"] = area
    return replace(
        feature, params=params, provenance="generated", face_indices=(), surface_patches=()
    )


def push_face(
    mesh: MeshData,
    feature: Feature,
    distance: float,
    *,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
) -> BooleanOutcome:
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
    outcome = boolean(kind, [mesh, tool], quality=quality, cancelled=cancelled)
    if outcome.mesh.volume <= EPS_GEOM:
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
    des Versetzens. Gebaut wird es von :func:`_prism_between`.
    """
    corners = np.asarray(mesh.raw.faces, dtype=np.int64)[triangles]
    used = np.unique(corners)
    below = np.asarray(mesh.raw.vertices, dtype=float)[used]
    local = np.searchsorted(used, corners)
    return _prism_between(below, local, below + offset(below))


def _prism_between(below: np.ndarray, corners: np.ndarray, above: np.ndarray) -> MeshData:
    """Der Körper zwischen einer Dreiecksmenge und ihrer verschobenen Kopie.

    ``below`` sind die Knoten der Fläche, ``corners`` ihre Dreiecke (Indizes in
    ``below``), ``above`` dieselben Knoten an ihrem neuen Ort. Boden und Deckel
    sind die Dreiecke selbst, der Mantel steht auf den Kanten, die nur zu einem
    von ihnen gehören — so trifft es jeden Umriss, auch einen mit Loch, ohne ihn
    je als Polygon zu sehen.

    **Jedes Mantelviereck wird an derselben Diagonale geteilt, gleich welcher
    Körper es baut**: vom alten Ort des lexikographisch kleineren Knotens zum
    neuen des anderen. Zwei angestellte Nachbarwände teilen sich ein solches
    Viereck (die Kante zwischen ihnen und ihr neuer Ort); mit verschiedenen
    Diagonalen bliebe zwischen den zwei Werkzeugen ein Spalt, und durch einen
    Spalt bleibt beim Abziehen eine Haut stehen.
    """
    import trimesh

    count = len(below)
    faces: list[tuple[int, int, int]] = []
    for a, b, c in corners.tolist():
        # Der Boden zeigt nach innen, der Deckel nach außen — sonst wäre der
        # Körper von innen nach außen gestülpt und hätte negatives Volumen.
        faces.append((a, c, b))
        faces.append((a + count, b + count, c + count))

    for first, second in _border_edges(corners):
        if tuple(below[first]) <= tuple(below[second]):
            faces.append((first, second, second + count))
            faces.append((first, second + count, first + count))
        else:
            faces.append((first, second, first + count))
            faces.append((second, second + count, first + count))

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
        raise gone_face_error({"faces": len(feature.face_indices)})
    return chosen


def gone_face_error(values: Mapping[str, Any] | None = None) -> GeometryError:
    """Der Satz, wenn eine gewählte Fläche nicht mehr am Körper ist (Regel 17).

    Ein Schritt davor hat sie neu vernetzt, verbraucht oder abgeschnitten;
    die Auswertung meldet ein Verbrauchen dort als Bezugsverlust (RM-537).
    Gewählt war eine Fläche, also ist die Neuwahl der Weg — nicht „keine
    gewählt". Eine Stelle für den Satz, ob die Dreiecke nicht mehr passen
    (:func:`_triangles_of`) oder die Kennung fehlt (``face_ops``).
    """
    return GeometryError(
        detail=_(
            "Diese Fläche gibt es an dem Körper nicht mehr — ein Schritt davor "
            "hat ihn verändert. Wählen Sie sie neu."
        ),
        values=dict(values or {}),
        suggestions=(CHANGE_SELECTION, CANCEL),
    )


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


def draft_walls(
    mesh: MeshData,
    angle_deg: float,
    *,
    walls: Sequence[Feature] | None = None,
    direction: Sequence[float] = (0.0, 0.0, 1.0),
    neutral: float | None = None,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
) -> BooleanOutcome:
    """Stellt Flächen um den Winkel an — gewählte oder alle in Entformungsrichtung (P6.4).

    ``direction`` ist die Entformungsrichtung: In sie hinein wird das Teil
    schmaler. ``neutral`` ist die Lage der neutralen Ebene entlang dieser
    Richtung (``Skalarprodukt mit direction``); ohne Angabe der Anfang des
    Körpers, bei „nach oben" also seine Unterkante. Dort behält jede
    angestellte Fläche ihr Maß, jenseits davon wird das Teil schmaler, davor
    breiter. ``walls`` sind die gewählten Flächenmerkmale; ohne sie gilt jede
    Wand, die in Entformungsrichtung steht — das Anstellen aller senkrechten
    Wände, wie jeder alte Schritt es meint.

    **Wie am exakten Kern:** Die neue Fläche geht durch die Schnittlinie der
    alten mit der neutralen Ebene und steht im Winkel zur Entformungsrichtung.
    Jede Ecke einer angestellten Fläche wandert in den Schnitt ihrer Ebenen —
    die neuen der angestellten Flächen, die alten aller übrigen, die an ihr
    liegen (:func:`_moved_corners`). Die Nachbarflächen bleiben so in ihrer
    Ebene und werden verlängert oder beschnitten, wie OpenCASCADE es tut; an
    einer Innenecke bleibt keine Säule stehen und an einem Sechskant keine
    Rippe.

    **Gerechnet wird trotzdem boolesch**: Zwischen alter und neuer Fläche
    entsteht ein Körper (:func:`_prism_between`), jenseits der neutralen Ebene
    abgezogen, davor vereinigt. Eine Fläche, die in eine Bohrung dahinter
    hineinwandert, schneidet sie damit an, statt das Netz zu durchdringen.
    """
    if not 0.0 < angle_deg <= MAX_DRAFT_DEGREES:
        raise ValidationError(
            "angle",
            _("Der Winkel muss zwischen null und 30 Grad liegen."),
            value=angle_deg,
        )
    _must_be_closed(mesh)
    pull = np.asarray(direction, dtype=float)
    pull = pull / float(np.linalg.norm(pull))
    chosen = (
        _walls_along(mesh, pull)
        if walls is None
        else [_chosen_wall(mesh, feature, pull) for feature in walls]
    )
    if not chosen:
        raise GeometryError(
            detail=_(
                "Dieser Körper hat keine Flächen, die in Entformungsrichtung stehen. Wählen "
                "Sie eine andere Richtung oder einzelne Flächen."
            ),
            suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
        )
    from app.core.perceive.features import _one_body

    body = _one_body(mesh).raw
    chosen, added = _tangent_walls(body, _without_repeats(body, chosen), pull)
    if _round_beside_the_walls(body, chosen, pull):
        raise GeometryError(
            detail=DRAFT_BESIDE_A_ROUND,
            suggestions=(CHANGE_SELECTION, CANCEL),
            values={"angle_deg": round(angle_deg, 2)},
        )
    heights = np.asarray(body.vertices, dtype=float) @ pull
    level = float(heights.min()) if neutral is None else float(neutral)
    sine = units.exact_sin_degrees(angle_deg)
    cosine = units.exact_cos_degrees(angle_deg)
    shift = _moved_corners(body, chosen, pull, level, sine, cosine, cancelled)
    tools = _draft_tools(body, chosen, shift, pull, level, cancelled)
    runs = _checked_tools(body, chosen, tools, angle_deg, quality=quality, cancelled=cancelled)

    result = mesh
    steps: tuple[tuple[BooleanKind, str], ...] = (("difference", "cut"), ("union", "fill"))
    for kind, wanted in steps:
        chosen_tools = [tool for side, _wall, tool in tools if side == wanted]
        if not chosen_tools:
            continue
        outcome = boolean(kind, [result, *chosen_tools], quality=quality, cancelled=cancelled)
        runs.append(outcome)
        result = outcome.mesh
    # **Was kein Volumen hat, ist kein Körper** — wie nach den Kantenwerkzeugen
    # (``edges._edge_work``). Wo ein Werkzeug genau an einer Deckfläche endet,
    # blieb am Behälter ``1x1-bin.stl`` eine Haut von acht Dreiecken ohne Dicke
    # stehen, und der Prüfbericht zählte zwei Teile.
    cleaned, shells = remove_hollow_shells(result)
    if shells:
        result = cleaned
    if result.volume <= EPS_GEOM:
        raise GeometryError(
            detail=_("Mit diesem Winkel bleibt vom Körper nichts übrig — kleiner anstellen."),
            values={"angle_deg": round(angle_deg, 2)},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    solver = deepest(run.solver for run in runs)
    outcome = BooleanOutcome(
        mesh=result,
        solver=solver if solver is not None else runs[0].solver,
        findings=[finding for run in runs for finding in run.findings],
    )
    # **Ein Teil, das der Keil ganz aufgezehrt hat, wird genannt.** Die
    # neutrale Ebene gilt dem ganzen Körper: Ein loses Stück, das über ihr
    # schwebt, verliert dort ``Höhe mal tan(Winkel)`` — an ``two_components.stl``
    # ist das zweite Stück 0,2 mm groß und sitzt 10 mm über der Unterkante,
    # bei drei Grad also 0,52 mm Abtrag auf 0,2 mm Material. Das ist richtig
    # gerechnet und trotzdem nichts, was jemand stillschweigend hinnehmen
    # will.
    if walls is not None and added:
        outcome.findings.append(tangent_faces_finding(added))
    before, after = mesh.component_count, outcome.mesh.component_count
    if after < before:
        outcome.findings.append(
            Finding(
                code="draft.parts_consumed",
                severity="warning",
                message=_(
                    "Lose Kleinteile hat dieser Winkel ganz abgetragen — sie lagen über "
                    "der Unterkante, an der das Maß bleibt."
                ),
                values={"before": before, "after": after, "angle_deg": round(angle_deg, 2)},
                # Regel 17: Winkel und neutrale Ebene stehen im Schritt.
                suggestions=(CORRECT_INPUT,),
            )
        )
    return outcome


def tangent_faces_finding(count: int) -> Finding:
    """Der Befund beider Kerne, wenn tangential anschließende Flächen mit angestellt wurden."""
    return Finding(
        code="draft.tangent_faces",
        severity="info",
        message=_(
            "Tangential anschließende Flächen wie gerundete Ecken sind mit angestellt, sonst "
            "gäbe es dort keine Kante."
        ),
        values={"faces": count},
    )


def _tangent_walls(
    body: Any, walls: list[tuple[list[int], np.ndarray]], pull: np.ndarray
) -> tuple[list[tuple[list[int], np.ndarray]], int]:
    """Die Wände und alles, was ohne sichtbare Kante an sie anschließt und mitkann.

    Das Gegenstück zu ``brep.profiles._tangent_chain``: Eine gerundete
    senkrechte Ecke ist am Netz eine Reihe schmaler Streifen, und jeder liegt
    in Entformungsrichtung. Ohne sie wanderte die Wand, und der erste Streifen
    daneben bliebe stehen — die Ecke rutschte über ihn hinweg
    (:data:`~app.core.units.GRAZING_SLIDE`, gemessen an ``1x1-bin.stl``).
    Übernommen wird jedes Dreieck, das über eine Kante unterhalb der
    Knickschwelle des Bildes (``SHARP_EDGE_ANGLE``) erreichbar ist und in
    Entformungsrichtung steht; je Ebene eine Wand. Zurück kommt auch, wie
    viele Wände dazukamen.
    """
    from app.core.geom.measure import SHARP_EDGE_ANGLE

    faces_count = len(body.faces)
    normals = np.asarray(body.face_normals, dtype=float)
    owned = np.zeros(faces_count, dtype=bool)
    for triangles, _normal in walls:
        owned[triangles] = True
    pairs = np.asarray(body.face_adjacency, dtype=np.int64)
    angles = np.asarray(body.face_adjacency_angles, dtype=float)
    if not len(pairs):
        return walls, 0
    upright = (np.abs(normals @ pull) <= UPRIGHT_ENOUGH) & (np.linalg.norm(normals, axis=1) > 0.5)
    # Nur Paare zweier stehender Dreiecke: Die Suche betritt ohnehin keine
    # anderen, und an einem großen Netz wäre die Nachbartafel sonst so groß
    # wie das Netz selbst.
    keep = (angles < SHARP_EDGE_ANGLE) & upright[pairs[:, 0]] & upright[pairs[:, 1]]
    smooth = pairs[keep]
    around: dict[int, list[int]] = {}
    for first, second in smooth.tolist():
        around.setdefault(first, []).append(second)
        around.setdefault(second, []).append(first)
    queue = [int(index) for index in np.flatnonzero(owned)]
    grown: list[int] = []
    while queue:
        current = queue.pop()
        for other in around.get(current, ()):
            if owned[other] or not upright[other]:
                continue
            owned[other] = True
            grown.append(other)
            queue.append(other)
    # Je **Ebene** eine Wand, nicht je Richtung: Die Streifen zweier gleich
    # gerundeter Ecken zeigen paarweise in dieselbe Richtung und liegen doch in
    # verschiedenen Ebenen (an ``1x1-bin.stl`` 20 mm auseinander).
    corners = np.asarray(body.vertices, dtype=float)[np.asarray(body.faces, dtype=np.int64)]
    tolerance = units.weld_tolerance(float(np.linalg.norm(np.ptp(body.vertices, axis=0))))
    groups: list[tuple[list[int], np.ndarray, float]] = []
    for triangle in sorted(grown):
        normal = normals[triangle] / float(np.linalg.norm(normals[triangle]))
        offset = float(normal @ corners[triangle].mean(axis=0))
        for members, known, where in groups:
            same_way = 1.0 - float(normal @ known) <= units.SAME_PLANE_AT_A_CORNER
            if same_way and abs(offset - where) <= tolerance:
                members.append(triangle)
                break
        else:
            groups.append(([triangle], normal, offset))
    return [*walls, *((members, normal) for members, normal, _where in groups)], len(groups)


def _without_repeats(
    body: Any, walls: Sequence[tuple[list[int], np.ndarray]]
) -> list[tuple[list[int], np.ndarray]]:
    """Die Wände ohne doppelte und ohne flächenlose Dreiecke.

    Ein doppelt gespeichertes Dreieck (``degenerate.stl`` trägt eines) gäbe
    zwei gleiche Werkzeuge; sie überdeckten sich und sähen aus wie zwei
    Flächen, die sich durch eine Wand schneiden. Ein Dreieck ohne Fläche
    trägt nichts bei. Eine Wand, von der nichts bleibt, fällt weg.
    """
    faces = np.asarray(body.faces, dtype=np.int64)
    areas = np.asarray(body.area_faces, dtype=float)
    seen: set[tuple[int, ...]] = set()
    kept: list[tuple[list[int], np.ndarray]] = []
    for triangles, normal in walls:
        own: list[int] = []
        for triangle in triangles:
            key = tuple(sorted(int(corner) for corner in faces[triangle]))
            if key in seen or areas[triangle] <= EPS_GEOM * EPS_GEOM:
                continue
            seen.add(key)
            own.append(int(triangle))
        if own:
            kept.append((own, normal))
    return kept


def _round_beside_the_walls(
    body: Any, walls: Sequence[tuple[list[int], np.ndarray]], pull: np.ndarray
) -> bool:
    """Ob an einer angestellten Wand eine Verrundung quer zur
    Entformungsrichtung anschließt (RM-230).

    Das Gegenstück zu ``brep.profiles._tangent_chain``, das dieselbe Frage
    exakt stellt: eine Fläche, die nicht mitgestellt wird, **ohne Knick** an
    eine Wand anschließt und schräg zur Entformungsrichtung liegt. Am Netz
    heißt ohne Knick: über eine Kante unter der Knickschwelle des Bildes
    (``SHARP_EDGE_ANGLE``) — und weil eine ebene Schräge, die flach an eine
    Wand stößt, das auch tut, muss sich die Fläche dahinter krümmen: Über
    solche Kanten erreicht man schräge Dreiecke, deren **Neigung** sich um mehr
    als die Knickschwelle ändert. Ein Kegelstück um die Entformungsrichtung —
    eine Schräge am Fuß einer gerundeten Ecke — krümmt sich nur um sie herum,
    seine Neigung bleibt (die Facetten streuen um wenige Grad), und es zählt
    nicht. Eine Fase oder eine Querbohrung schließt mit Knick an. Den ersten,
    fast stehenden Streifen einer Rundung nimmt :func:`_tangent_walls` als Wand
    mit; gefragt wird dann am zweiten. Ohne BLAS (``transform.along``): Die
    Antwort entscheidet über Absage oder Ergebnis.
    """
    import trimesh

    from app.core.geom import transform
    from app.core.geom.measure import SHARP_EDGE_ANGLE

    pairs = np.asarray(body.face_adjacency, dtype=np.int64)
    if not len(pairs):
        return False
    owned = np.zeros(len(body.faces), dtype=bool)
    for triangles, _normal in walls:
        owned[triangles] = True
    along = np.abs(transform.along(np.asarray(body.face_normals, dtype=float), pull))
    leaning = leaning_band(along) & ~owned
    smooth = np.asarray(body.face_adjacency_angles, dtype=float) < SHARP_EDGE_ANGLE
    first, second = pairs[:, 0], pairs[:, 1]
    touching = smooth & (owned[first] != owned[second])
    seeds = np.where(owned[first], second, first)[touching]
    seeds = seeds[leaning[seeds]]
    if not len(seeds):
        return False
    joined = pairs[smooth & leaning[first] & leaning[second]]
    for region in trimesh.graph.connected_components(
        joined, nodes=np.flatnonzero(leaning), min_len=1
    ):
        members = np.asarray(region, dtype=np.int64)
        if not np.isin(members, seeds).any():
            continue
        # Die Spanne der Neigung ohne Arkussinus (Review P2, G3; ``kern.md``):
        # Mit a = größter, b = kleinster Anteil längs der Richtung ist
        # asin(a) - asin(b) > S genau dann, wenn sin(asin(a) - asin(b)) =
        # a·sqrt(1 - b²) - b·sqrt(1 - a²) über sin S liegt — beide Winkel liegen
        # in [0, π/2], und ``math.sqrt`` rundet korrekt.
        high = min(max(float(along[members].max()), 0.0), 1.0)
        low = min(max(float(along[members].min()), 0.0), 1.0)
        spread = high * math.sqrt(1.0 - low * low) - low * math.sqrt(1.0 - high * high)
        if spread > units.exact_sin(SHARP_EDGE_ANGLE):
            return True
    return False


def _checked_tools(
    body: Any,
    walls: Sequence[tuple[list[int], np.ndarray]],
    tools: Sequence[tuple[str, int, MeshData]],
    angle_deg: float,
    *,
    quality: Quality,
    cancelled: CancelToken | None,
) -> list[BooleanOutcome]:
    """Hält an, wo eine angestellte Fläche durch anderes Material liefe.

    **Ein Werkzeug zum Abziehen liegt ganz im Material, eines zum Vereinigen
    ganz davor** — solange keine Fläche in fremdes Material wandert. Je Bauteil
    wird das nachgerechnet: Was von der Vereinigung seiner Abzugswerkzeuge im
    Bauteil liegt, ist genau ihre Summe (gemessen auf 10⁻¹⁷ des Volumens), und
    die Zugabewerkzeuge berühren das Bauteil nur an ihrer Fläche. Weicht es ab,
    überschneiden sich zwei Flächen in einer Wand — am Gehäuse mit 3 mm Wand
    bei 5° über 20 mm Höhe weichen außen und innen oben zusammen 3,5 mm zurück
    —, oder eine Fläche läuft in eine Bohrung dahinter. Der Körper wäre dort
    dünner als nichts; der Satz dazu ist derselbe wie am exakten Kern.

    **Ein Teil, das ganz verschwindet, ist keine solche Stelle.** Ein loses
    Stäubchen über der neutralen Ebene zehrt der Keil vollständig auf; das
    bleibt erlaubt und wird als Befund genannt (``draft.parts_consumed``).
    """
    import trimesh

    faces = np.asarray(body.faces, dtype=np.int64)
    # **Bauteile über gemeinsame Ecken, nicht über Nachbarschaften.** Ein
    # doppelt gespeichertes Dreieck macht seine Kanten mehrdeutig, und
    # ``face_adjacency`` lässt solche Kanten aus: In ``degenerate.stl`` stand
    # ein Dreieck der linken Wand dann als eigenes Bauteil da.
    corners = trimesh.graph.connected_component_labels(  # type: ignore[no-untyped-call]
        body.edges_unique, node_count=len(body.vertices)
    )
    labels = np.asarray(corners, dtype=np.int64)[faces[:, 0]]
    runs: list[BooleanOutcome] = []
    # **Nur eine exakt gerechnete Bilanz darf absagen.** Fällt ein Schritt der
    # Prüfung bis zur Voxelstufe durch, ist sein Volumen genähert: Am Behälter
    # ``1x1-bin.stl`` fehlten so bei 0,3° scheinbar 8,7 mm³, bei 0,5° nichts —
    # eine Absage, die am kleineren Winkel kam und am größeren nicht. Die
    # Stufe steht ohnehin im Bericht (§17.2).
    exact = [True]

    def solved(outcome: BooleanOutcome) -> BooleanOutcome:
        runs.append(outcome)
        if outcome.solver.strategy == "voxel":
            exact[0] = False
        return outcome

    def united(parts: list[MeshData]) -> MeshData | None:
        if len(parts) == 1:
            return parts[0]
        try:
            return solved(boolean("union", parts, quality=quality, cancelled=cancelled)).mesh
        except GeometryError:
            # Im Entwurf endet die Kette nach Stufe 2; die Prüfung lässt dann
            # nach, statt die Operation scheitern zu lassen. Ebenso, wo die
            # Kette vor dem Kern an einer Schale anhält, die sich selbst
            # kreuzt (RM-382): Die Prüfung beurteilt, sie entscheidet nicht.
            exact[0] = False
            return None

    def shared(first: MeshData, second: MeshData | None, kind: BooleanKind) -> float:
        if second is None:
            return 0.0
        try:
            outcome = boolean(
                kind, [first, second], quality=quality, allow_empty=True, cancelled=cancelled
            )
        except GeometryError:
            exact[0] = False
            return 0.0
        return float(solved(outcome).mesh.volume)

    def refused() -> GeometryError:
        return GeometryError(
            detail=DRAFT_CUTS_THROUGH,
            suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
            values={"angle_deg": round(angle_deg, 2)},
        )

    owner = {wall: int(labels[walls[wall][0][0]]) for _side, wall, _tool in tools}
    for label in sorted(set(owner.values())):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        # Doppelte und flächenlose Dreiecke heraus: So ein Bauteil ist für
        # ``manifold3d`` kein geschlossener Körper, und die Kette glättete ihn
        # bis zur Voxelstufe — dann stimmte keine Bilanz mehr.
        part, _gone = remove_degenerate_faces(
            MeshData(body.submesh([np.flatnonzero(labels == label)], append=True))
        )
        part, _doubled = remove_doubled_faces(part)
        noise = max(units.VOLUME_SUM_NOISE * part.volume, EPS_GEOM)
        cuts = [tool for side, wall, tool in tools if side == "cut" and owner[wall] == label]
        fills = [tool for side, wall, tool in tools if side == "fill" and owner[wall] == label]
        # **Nur Differenzen, kein Schnitt.** Werkzeug und Bauteil teilen die
        # Fläche, auf der das Werkzeug steht; ``manifold3d`` rechnet den Schnitt
        # solcher deckungsgleicher Flächen in der ersten Stufe nicht verlässlich:
        # am Behälter bei 0,3° Vereinigung 5000,472 = Summe, Schnitt mit dem
        # Bauteil 4991,780, Bauteil minus Vereinigung aber genau 16 906,228 =
        # Bauteil minus Summe — die Differenz stimmte, der Schnitt nicht.
        if cuts:
            union = united(cuts)
            wanted = sum(tool.volume for tool in cuts)
            left = shared(part, union, "difference")
            # Geht weniger weg als ihre Summe, überschneiden sie sich oder ragen
            # hinaus — erlaubt nur, wo vom Bauteil nichts bleibt.
            mismatch = abs(part.volume - left - wanted) > max(noise, EPS_GEOM * wanted)
            if mismatch and left > noise and exact[0]:
                raise refused()
        if fills:
            union = united(fills)
            added = sum(tool.volume for tool in fills)
            outside = shared(union, part, "difference") if union is not None else added
            if union is not None and union.volume - outside > noise and exact[0]:
                raise refused()
    return runs


def _chosen_wall(
    mesh: MeshData, feature: Feature, pull: np.ndarray
) -> tuple[list[int], np.ndarray]:
    """Eine gewählte Fläche mit ihrer Normale — oder der Satz, warum sie nicht angestellt wird."""
    if feature.kind != "face":
        raise GeometryError(
            detail=_(
                "Angestellt werden ebene Flächen. Wählen Sie eine ebene Seitenwand, "
                "oder lassen Sie die Auswahl leer für alle Wände."
            ),
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    triangles = _triangles_of(mesh, feature)
    normal = np.asarray(face_normal(feature), dtype=float)
    if abs(float(normal @ pull)) > UPRIGHT_ENOUGH:
        raise _across_the_pull()
    return triangles, normal


def _across_the_pull() -> GeometryError:
    """Der Satz beider Kerne für eine Fläche, die quer zur Entformungsrichtung steht."""
    return GeometryError(
        detail=_(
            "Diese Fläche steht quer zur Entformungsrichtung — angestellt werden Flächen, "
            "die in diese Richtung verlaufen. Wählen Sie eine Seitenwand oder eine andere "
            "Entformungsrichtung."
        ),
        suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
    )


def _moved_corners(
    body: Any,
    walls: Sequence[tuple[list[int], np.ndarray]],
    pull: np.ndarray,
    level: float,
    sine: float,
    cosine: float,
    cancelled: CancelToken | None,
) -> np.ndarray:
    """Wohin jede Ecke einer angestellten Fläche wandert — in den Schnitt ihrer Ebenen.

    Die neue Ebene einer Fläche mit der Normale ``n`` geht durch ihre
    Schnittlinie mit der neutralen Ebene; ihre Normale ist ``cos(w)·n_h +
    sin(w)·d`` mit dem Winkel ``w`` und ``n_h``, dem Teil von ``n`` quer zur
    Entformungsrichtung ``d`` — derselbe absolute Winkel, den
    ``BRepOffsetAPI_DraftAngle`` setzt. Eine
    Ecke gehört zu den neuen Ebenen der angestellten Flächen an ihr und zu den
    alten aller übrigen (Dreiecke an ihr, deren Normalen sich um mehr als
    :data:`~app.core.units.SAME_PLANE_AT_A_CORNER` unterscheiden); ihr neuer
    Ort ist der nächste Punkt, der alle zugleich erfüllt. Eine Ecke im Inneren
    einer Fläche kennt nur deren Ebene und rückt senkrecht auf sie.

    Zwei Fälle haben keine Antwort, und beide sagen es statt still zu glätten:
    Die Ebenen treffen sich nicht mehr in einem Punkt (eine Fläche entstünde
    oder verschwände), oder die Ecke wanderte mehr als
    :data:`~app.core.units.GRAZING_SLIDE`-mal so weit wie ihre Fläche — die
    Nachbarfläche läuft dann fast parallel, etwa eine Rundung.
    """
    vertices = np.asarray(body.vertices, dtype=float)
    faces = np.asarray(body.faces, dtype=np.int64)
    normals = np.asarray(body.face_normals, dtype=float)
    owner = np.full(len(faces), -1, dtype=np.int64)
    new_normals = np.zeros((len(walls), 3))
    new_offsets = np.zeros(len(walls))
    for number, (triangles, normal) in enumerate(walls):
        owner[triangles] = number
        across = normal - float(normal @ pull) * pull
        across /= float(np.linalg.norm(across))
        offset = float(normal @ vertices[faces[triangles]].reshape(-1, 3).mean(axis=0))
        # Ein Punkt der Schnittlinie mit der neutralen Ebene: n·x = offset, d·x = level.
        mix = float(normal @ pull)
        weights = np.linalg.solve(np.array([[1.0, mix], [mix, 1.0]]), [offset, level])
        on_line = weights[0] * normal + weights[1] * pull
        new_normals[number] = cosine * across + sine * pull
        new_offsets[number] = float(new_normals[number] @ on_line)

    moving = np.unique(faces[owner >= 0])
    around = np.asarray(body.vertex_faces, dtype=np.int64)[moving]
    owners = np.where(around >= 0, owner[np.maximum(around, 0)], -2)
    shift = np.zeros_like(vertices)
    # Eine Ecke im Inneren genau einer Fläche: senkrecht auf deren neue Ebene.
    lone = owners.max(axis=1)
    inside = np.all((owners == lone[:, None]) | (owners == -2), axis=1) & (lone >= 0)
    inner = moving[inside]
    if len(inner):
        plane = new_normals[lone[inside]]
        gap = new_offsets[lone[inside]] - np.einsum("ij,ij->i", plane, vertices[inner])
        shift[inner] = plane * gap[:, None]

    # **Die Facettengrenze, nicht die Schweißtoleranz.** Eine STL speichert
    # die Streifen einer Rundung oft als leicht verdrehte Vierecke: Ihre zwei
    # Dreiecke liegen um Tausendstel neben einer gemeinsamen Ebene, und an der
    # Ecke treffen sich dann vier statt drei Ebenen. Gemessen an ``1x1-bin.stl``:
    # an 52 von 546 Ecken mehr als die Schweißtoleranz, höchstens 0,013 mm.
    # Innerhalb von ``MAX_FACET_SAG`` weicht die Ecke nicht weiter von ihren
    # Ebenen ab als das Netz selbst von der Fläche, die es darstellt.
    tolerance = MAX_FACET_SAG
    slack = units.weld_tolerance(float(np.linalg.norm(np.ptp(vertices, axis=0))))
    for number, position in enumerate(np.flatnonzero(~inside).tolist()):
        if cancelled is not None and number % 256 == 0:
            cancelled.raise_if_cancelled()
        vertex = int(moving[position])
        point = vertices[vertex]
        incident = around[position]
        incident = incident[incident >= 0]
        rows: list[np.ndarray] = []
        targets: list[float] = []
        free = 0.0
        drafted: list[int] = []
        for wall in sorted({int(owner[face]) for face in incident if owner[face] >= 0}):
            # Zwei angestellte Wände fast gleicher Richtung an einer Ecke — die
            # zwei Dreiecke eines leicht verdrehten Streifens — sind eine Ebene:
            # Ihr Schnitt wäre schlecht bestimmt, und die Ecke rutschte an ihm.
            if any(
                1.0 - float(walls[wall][1] @ walls[known][1]) <= units.SAME_PLANE_AT_A_CORNER
                for known in drafted
            ):
                continue
            drafted.append(wall)
        for wall in drafted:
            rows.append(new_normals[wall])
            targets.append(float(new_offsets[wall]))
            free = max(free, abs(float(new_offsets[wall] - new_normals[wall] @ point)))
        # Ein Dreieck in der alten Ebene einer angestellten Wand gehört zu ihr —
        # ein doppelt gespeichertes zum Beispiel —, nicht als zweite, alte Ebene
        # an die Ecke; sonst widerspräche es der neuen.
        kept: list[np.ndarray] = [np.asarray(walls[wall][1], dtype=float) for wall in drafted]
        for face in incident:
            if owner[face] >= 0:
                continue
            candidate = normals[face]
            if float(np.linalg.norm(candidate)) < 0.5:
                continue
            if any(
                1.0 - float(candidate @ known) <= units.SAME_PLANE_AT_A_CORNER for known in kept
            ):
                continue
            kept.append(candidate)
            rows.append(candidate)
            targets.append(float(candidate @ point))
        matrix = np.asarray(rows, dtype=float)
        residual = np.asarray(targets) - matrix @ point
        step = np.linalg.lstsq(matrix, residual, rcond=None)[0]
        if float(np.abs(matrix @ step - residual).max()) > tolerance:
            raise GeometryError(
                detail=_(
                    "Beim Anstellen entstünde an einer Ecke eine neue Fläche oder eine "
                    "verschwände — so weit reicht dieser Weg am Netz nicht. Stellen Sie einen "
                    "kleineren Winkel ein, oder wählen Sie weniger Flächen."
                ),
                suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
                values={"corner": [round(float(value), 3) for value in point]},
            )
        if float(np.linalg.norm(step)) > units.GRAZING_SLIDE * free + slack:
            raise GeometryError(
                detail=_(
                    "An einer gewählten Fläche schließt eine fast gleich gerichtete Fläche an, "
                    "etwa eine Rundung — dort gibt es keine eindeutige neue Kante. Lassen Sie "
                    "diese Fläche aus, oder wählen Sie die angrenzende mit, wenn sie eben ist."
                ),
                suggestions=(CHANGE_SELECTION, CORRECT_INPUT, CANCEL),
                values={"corner": [round(float(value), 3) for value in point]},
            )
        shift[vertex] = step
    return shift


def _draft_tools(
    body: Any,
    walls: Sequence[tuple[list[int], np.ndarray]],
    shift: np.ndarray,
    pull: np.ndarray,
    level: float,
    cancelled: CancelToken | None,
) -> list[tuple[str, int, MeshData]]:
    """Die Körper zwischen alter und neuer Fläche — jenseits der neutralen Ebene zum
    Abziehen (``"cut"``), davor zum Vereinigen (``"fill"``), je mit ihrer Wand.

    Eine Fläche, die die neutrale Ebene kreuzt, wird dort geteilt: Ihre Ecken
    wandern oberhalb ins Material und unterhalb hinaus, und ein Körper über
    beidem wäre an der Schnittlinie verdreht. Die Knoten der Teilung liegen
    auf der neutralen Linie und bleiben, wo sie sind.
    """
    import trimesh

    vertices = np.asarray(body.vertices, dtype=float)
    faces = np.asarray(body.faces, dtype=np.int64)
    tolerance = units.weld_tolerance(float(np.linalg.norm(np.ptp(vertices, axis=0))))
    found: list[tuple[str, int, MeshData]] = []
    for number, (triangles, _normal) in enumerate(walls):
        # Zwischen den Flächen gefragt: Ein Werkzeug entsteht in numpy und ist
        # dort nicht zu unterbrechen (§15.6, wie in ``edges._edge_work``).
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        corners = faces[triangles]
        used = np.unique(corners)
        heights = vertices[used] @ pull - level
        local = np.searchsorted(used, corners)
        below = vertices[used]
        if float(heights.min()) >= -tolerance:
            parts = [("cut", below, local, shift[used])]
        elif float(heights.max()) <= tolerance:
            parts = [("fill", below, local, shift[used])]
        else:
            # **Was die Teilung zur neutralen Ebene zählt, liegt vorher genau
            # darauf** (``section.settled_on_plane``): Sonst steht eine Ecke
            # der Ebene zweimal da, das Verschweißen unten verfehlt das Paar,
            # und der Keil bekommt eine Wand mitten in der Fläche.
            below = settled_on_plane(below, pull, level)
            moved = {
                tuple(point): step for point, step in zip(below.tolist(), shift[used], strict=True)
            }
            parts = []
            for kind, side in (("cut", pull), ("fill", -pull)):
                points, pieces, _uv = trimesh.intersections.slice_faces_plane(  # type: ignore[no-untyped-call]
                    below, local, plane_normal=side, plane_origin=level * pull
                )
                if not len(pieces):
                    continue
                # **Verschweißt, bevor der Rand gesucht wird.** Die Teilung
                # legt jeden Schnittpunkt je Dreieck neu an; zwei Dreiecke an
                # derselben Kante trügen sonst zwei Knoten, und ihre gemeinsame
                # Kante zählte als Rand — der Mantel stünde mitten in der Fläche.
                piece = trimesh.Trimesh(vertices=points, faces=pieces, process=True)
                welded = np.asarray(piece.vertices, dtype=float)
                steps = np.asarray(
                    [moved.get(tuple(point), np.zeros(3)) for point in welded.tolist()]
                )
                parts.append((kind, welded, np.asarray(piece.faces, dtype=np.int64), steps))
        for kind, points, pieces, steps in parts:
            if float(np.abs(steps).max(initial=0.0)) <= EPS_GEOM:
                continue
            tool = _prism_between(points, pieces, points + steps)
            if tool.triangle_count and tool.volume > EPS_GEOM:
                found.append((kind, number, tool))
    return found


def _walls_along(mesh: MeshData, pull: np.ndarray) -> list[tuple[list[int], np.ndarray]]:
    """Die Flächen des Netzes, die in Entformungsrichtung stehen, jede mit ihrer Normalen.

    Gefragt wird die Merkmalserkennung und nicht ``face_normals`` direkt: Eine
    Wand aus zwei Dreiecken ist **eine** Fläche, und ihr Keil entsteht in einem
    Stück. Über die Dreiecke gerechnet wären es zwei Keile mit einer
    gemeinsamen Kante — zweimal dieselbe Arbeit und eine Naht mehr, an der die
    Boolesche Rechnung stolpern kann.

    **Und was sie übersieht, kommt dazu** — die Begründung und die Grenze
    stehen bei :data:`MOST_WALLS_TO_GUESS`.
    """
    from app.core.perceive.features import detect

    features = detect(mesh)
    found: list[tuple[list[int], np.ndarray]] = []
    for feature in features.values():
        if feature.kind != "face" or not feature.face_indices:
            continue
        normal = np.asarray(face_normal(feature), dtype=float)
        if abs(float(normal @ pull)) > UPRIGHT_ENOUGH:
            continue
        found.append(([int(index) for index in feature.face_indices], normal))
    return found + _walls_no_feature_claims(mesh, features, pull)


def _must_be_closed(mesh: MeshData) -> None:
    """Hält ein Netz an, aus dem die Keile keinen Körper schneiden können.

    Die Keile gehen als Differenz in die Rückfallkette, und die braucht
    geschlossene Körper. An ``broken_open.stl`` fielen alle drei Kernstufen
    durch, die Voxelstufe rechnete 3,7 Sekunden und gab von 4000 mm³ noch 101
    zurück — kein angestellter Körper, sondern ein anderer. Bei einem
    eingelesenen Modell in Kundengröße ist dasselbe der Abriss, den Robert am
    18.09.2026 gemeldet hat: „Formschräge einstellen, Programm stürzt ab."

    **Gefragt wird, was die Kette fragt** — nicht ``is_watertight`` am rohen
    Netz. Eine STL ist per Index nie dicht, und genau dafür gibt es Stufe 2
    (``boolean._welded_input``): ``plate_countersunk.stl`` ist roh offen,
    verschweißt und entnadelt trägt es, und die Formschräge lief dort immer
    schon. Die Probe am rohen Netz hätte es abgewiesen — eine Sperre, die den
    Normalfall trifft, ist keine Sperre, sondern ein neuer Fehler.

    **Gefragt wird in der Reihenfolge, in der die Antworten billiger sind.**
    Ein dichtes Netz sagt das über einen Cache, den ``trimesh`` ohnehin führt;
    verschweißt wird erst, wenn es das nicht tut. Die erste Fassung rechnete
    beides immer und kostete an ``dense_1m.stl`` 0,87 Sekunden für eine
    Antwort, die vorher schon dastand — vor einer Operation, die an demselben
    Netz ohnehin absagt (§2.8).
    """
    if mesh.is_watertight:
        return
    welded, _gone = merge_vertices(mesh)
    if welded.is_watertight:
        return
    cleaned, _dropped = remove_degenerate_faces(welded)
    if cleaned.is_watertight:
        return
    raise GeometryError(
        detail=_(
            "Dieses Modell ist nicht geschlossen — angestellt käme ein anderer "
            "Körper heraus. Erst reparieren."
        ),
        suggestions=(REPAIR_AND_RETRY, CANCEL),
    )


def _walls_no_feature_claims(
    mesh: MeshData,
    features: dict[str, Feature],
    pull: np.ndarray | None = None,
) -> list[tuple[list[int], np.ndarray]]:
    """Die ebenen senkrechten Flächen, die kein erkanntes Merkmal beansprucht.

    Gesucht wird über ``facets`` am **verschweißten** Netz: Eine STL schreibt
    jedes Dreieck mit eigenen Ecken, und ungeschweißt hat sie null
    Nachbarschaften und null Facetten (:func:`perceive.features._one_body`
    beschreibt denselben Fall). Die Dreiecksnummern bleiben dabei dieselben,
    daran hängen die Merkmalsnummern.

    Beansprucht heißt: von **irgendeinem** Merkmal, nicht nur von einer Fläche.
    Der Mantel einer erkannten Bohrung gehört ihr, auch wenn er keine Ebene
    ist — was hier übrig bleibt, hat die Erkennung gar nicht gesehen. (Wie
    viel das ist, hängt am Netz: An ``plate_holes.stl`` bleibt nichts übrig,
    an ``plate_countersunk.stl`` findet die Erkennung keine Bohrung, und dort
    fängt die Grenze die 48 Mantelstreifen ab.)

    **Und ``facets`` ist keine Ebenheitsprüfung**, auch wenn der Name danach
    klingt: ``trimesh`` gruppiert über einen Krümmungsradius, nicht über einen
    Winkel — je feiner ein gewölbtes Netz, desto eher gilt es als **eine**
    Facette. Gemessen: eine Kugel mit 327 680 Dreiecken kommt als **eine**
    Gruppe mit 180 Grad Normalenabweichung zurück, ``dense_1m.stl`` ebenso.
    Ihr erstes Dreieck steht dort zufällig fast senkrecht, und ohne die
    Nachprüfung unten wäre eine ganze Kugel eine Wand. Dass das heute nicht
    aufschlägt, liegt an der Erkennung und an der Grenze — beides Zufall,
    keine Zusage.

    **Ein Dreieck ohne Fläche hat keine Richtung.** Seine Normale ist
    ``[0, 0, 0]``, und deren Z-Anteil ist null: ungeprüft gilt es als
    senkrecht, der Keil darüber hat die Dicke null, und die Rückfallkette
    fällt durch alle vier Stufen. An ``degenerate.stl`` kamen so acht Wände
    statt sechs und ``BooleanFailedError`` statt 7190,772 mm³. Der
    Merkmalsweg hat die Prüfung seit je (:func:`face_normal`).

    **Und die zwei Sperren decken diesen Fall auf zwei Wegen** — wer eine
    davon anfasst, misst deshalb leicht das Falsche. Gemessen am 18.09.2026
    an ``degenerate.stl``: Fällt die Ebenheitsprüfung weg, ändert sich nichts
    (6 Wände, 7190,772 mm³); fällt diese Prüfung weg, kommen acht Wände und
    der Abbruch. Ersetzt man sie dagegen durch ein stilles ``max(länge, eps)``,
    bleibt ein **Nullvektor** stehen, und den verwirft die Ebenheitsprüfung
    ihrerseits — sein Skalarprodukt ist null. Die eine Gestalt, die durch
    beide fällt, ist ``0/0``: ``nan`` ist nie größer als eine Schranke.
    """
    from app.core.perceive.features import _one_body

    if pull is None:
        pull = np.array([0.0, 0.0, 1.0])
    body = _one_body(mesh).raw
    count = len(body.faces)
    # Belegt und gruppiert als Masken und nicht als Mengen: An ``dense_1m.stl``
    # kostete die Buchhaltung über 1 310 720 Dreiecke 140 der 170 ms — für
    # eine einzige Facettengruppe, die die Ebenheitsprüfung danach verwirft.
    claimed = np.zeros(count, dtype=bool)
    for entry in features.values():
        if entry.face_indices:
            claimed[np.asarray(entry.face_indices, dtype=int)] = True
    groups = [np.asarray(group, dtype=int) for group in body.facets]
    grouped = np.zeros(count, dtype=bool)
    for group in groups:
        grouped[group] = True
    groups += [np.array([index]) for index in np.flatnonzero(~grouped)]

    guessed: list[tuple[list[int], np.ndarray]] = []
    for group in groups:
        if bool(claimed[group].any()):
            continue
        normal = np.asarray(body.face_normals[group[0]], dtype=float)
        length = float(np.linalg.norm(normal))
        if length <= EPS_GEOM:
            continue
        normal = normal / length
        if abs(float(normal @ pull)) > UPRIGHT_ENOUGH:
            continue
        # Die Gruppe selbst muss eben sein, nicht nur ihr erstes Dreieck.
        if float(np.abs(body.face_normals[group] @ normal - 1.0).max()) > SAME_PLANE_ENOUGH:
            continue
        guessed.append(([int(index) for index in group], normal))
        # **Gezählt wird, was geraten wird** — nicht die Summe mit den
        # erkannten. Ein Teil mit vielen erkannten senkrechten Flächen bekam
        # sonst keine einzige Ergänzung: An einem Kundenmodell (25 erkannte
        # Wände, 12 ebene Kandidaten mit null Grad Abweichung) wurde alles
        # verworfen, also genau dort nichts behoben, wo der Befund entsteht.
        if len(guessed) > MOST_WALLS_TO_GUESS:
            return []
    return guessed
