"""Kleine Formen, aus denen die Bausteine gebaut werden (Bauplan §24.1).

Alles hier steht gegen ``manifold3d``, nicht gegen OpenSCAD (§24.1): ein
Baustein hängt so an keiner externen Installation und bleibt testbar.
"""

from __future__ import annotations

import math

import numpy as np

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.types import Vec3

#: Segmente einer runden Form. Fein genug, dass eine gedruckte Bohrung rund
#: ist, grob genug, dass ein Baustein ein paar tausend Dreiecke bleibt (§31).
SEGMENTS = 48

#: Wie weit der Gang eines Gewindes aus seinem Kern heraussteht, als Anteil
#: der Steigung. Benannt, weil drei Stellen sich darauf einigen müssen: der
#: hier gebaute Gang, der Kern, auf dem die Schraube ihn trägt, und der
#: Durchmesser, aus dem die Mutter geschnitten wird. Zwei der drei mit einer
#: anderen Zahl sind ein Paar, das sich nicht zusammenschrauben lässt — und in
#: keiner Hälfte für sich zu sehen.
RIDGE_SHARE = 0.55

#: Wo der Gang eines Rings endet, als Anteil der Steigung: Der oberste Punkt
#: jedes Rings sitzt ``pitch * RIDGE_END`` über seiner Grundhöhe. Der letzte
#: Ring liegt auf ``height``, also reicht der Gewindekörper um genau diesen
#: Betrag über seine angegebene Höhe hinaus — wer ihn auf eine Fläche schneidet,
#: rechnet das ab, sonst durchbricht der Gang die Wand dahinter.
RIDGE_END = 0.8

#: Zusatztiefe einer Aufnahme über das hinaus, was in ihr steckt — damit zwei
#: Hälften auf ihrer Naht schließen und nicht auf dem Ende des Verbinders.
#:
#: Steht hier und nicht bei den Verbindern, weil zwei Stellen sie brauchen:
#: `geom/pins.py` beim Bohren und `parts/mechanics.py` beim Schnappverbinder.
#: `pins.py` importiert Bausteine, umgekehrt ginge es nicht — also wohnt die
#: Zahl unter beiden statt zweimal nebeneinander.
SEAT_RELIEF = 0.4


def cylinder(diameter: float, height: float, *, segments: int = SEGMENTS) -> MeshData:
    """Auf Z = 0 stehend, nach oben wachsend — der Rahmen, den jeder Baustein
    benutzt.
    """
    body = trimesh.creation.cylinder(radius=diameter / 2.0, height=height, sections=segments)
    body.apply_translation([0.0, 0.0, height / 2.0])
    return MeshData.of(body)


def box(width: float, depth: float, height: float) -> MeshData:
    """In X und Y zentriert, auf Z = 0 stehend."""
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation([0.0, 0.0, height / 2.0])
    return MeshData.of(body)


def hexagon(width: float, height: float) -> MeshData:
    """Ein Sechskantprisma, ``width`` über die Schlüsselweite — eine Mutter,
    mit anderen Worten.
    """
    radius = width / math.sqrt(3.0)
    angles = np.linspace(0.0, 2.0 * math.pi, 7)[:-1] + math.pi / 6.0
    points = np.column_stack([radius * np.cos(angles), radius * np.sin(angles)])
    body = trimesh.creation.extrude_polygon(_polygon(points), height=height)
    return MeshData.of(body)


def dovetail(width: float, height: float, *, taper: float = 0.55) -> MeshData:
    """Ein Schwalbenschwanz-Prisma, ``width`` über die breite Seite.

    Der Querschnitt ist ein gleichschenkliges Trapez: hinten schmal, vorn
    breit. In einer Trennfuge sichert das gegen Verdrehen *und* gegen
    Auseinanderziehen quer zur Naht — ein runder Stift kann nur das Erste, und
    dafür braucht er zwei Stück.

    ``taper`` ist die schmale Seite als Anteil der breiten. Über etwa 0,7
    verschwindet der Formschluss, unter etwa 0,4 wird die schmale Seite zur
    Sollbruchstelle; die Vorgabe liegt dazwischen und entspricht dem, was die
    Slicer für ihre Schwalbenschwänze nehmen.
    """
    broad = width / 2.0
    narrow = broad * taper
    depth = width / 2.0
    points = np.array(
        [[-narrow, -depth], [narrow, -depth], [broad, depth], [-broad, depth]], dtype=float
    )
    body = trimesh.creation.extrude_polygon(_polygon(points), height=height)
    return MeshData.of(body)


def cone(bottom: float, top: float, height: float, *, segments: int = SEGMENTS) -> MeshData:
    """Ein Kegelstumpf auf Z = 0 — eine Senkung, oder eine Fase."""
    profile = np.array(
        [[0.0, 0.0], [bottom / 2.0, 0.0], [top / 2.0, height], [0.0, height]], dtype=float
    )
    body = trimesh.creation.revolve(profile, sections=segments)
    return MeshData.of(body)


def slot(width: float, length: float, height: float, *, segments: int = SEGMENTS) -> MeshData:
    """Ein Langloch: zwei Halbkreise mit einem Rechteck dazwischen."""
    if length <= width:
        return cylinder(width, height, segments=segments)
    body = trimesh.creation.extrude_polygon(
        _polygon(_slot_outline(width, length, segments)), height=height
    )
    return MeshData.of(body)


def tapered_bar(
    width: float, narrow: float, length: float, height: float, taper: float
) -> MeshData:
    """Ein Riegel, der an beiden Enden auf ``narrow`` zuläuft.

    Die Form eines Nutensteins: in der Mitte volle Breite, an den Enden über
    ``taper`` schmaler, damit er sich einschieben lässt statt an der ersten
    Kante zu klemmen. In X liegt die Breite, in Y die Länge, auf Z = 0 stehend
    — derselbe Rahmen wie bei :func:`box`.

    Als extrudierter Umriss und nicht aus Kästen zusammengesetzt: eine
    Vereinigung dreier Körper hätte zwei zusammenfallende Flächen darin, und
    das ist der klassische Weg, eine Boolesche Operation zu brechen (§39).

    Zwei Grenzfälle fängt die Funktion selbst ab, und beide sind dieselbe
    Falle wie bei :func:`wedge` — zwei Ecken, die aufeinander fallen, machen
    eine entartete Fläche, und ein Körper mit einer solchen ist nicht
    wasserdicht (§24.3):

    * **Keine Schräge** (``taper`` auf null, oder ``narrow`` nicht schmaler als
      ``width``): dann ist es ein :func:`box`.
    * **Schräge über die halbe Länge**: dann gibt es keine Schulter mehr, und
      der Umriss hat sechs Ecken statt acht. Gemessen, bevor die Abfrage hier
      stand: bei Länge 6 und Schräge 3 — genau auf der Kante — kam ein Körper
      aus **fünf** Teilen heraus, der nicht wasserdicht war. Bei 4 und bei 6
      ging es wieder gut, die Ecke liegt also nicht am Ende des Bereichs,
      sondern mitten darin, und kein Eckenraster findet sie.
    """
    if taper <= 0.0 or narrow >= width:
        return box(width, length, height)

    half_wide, half_narrow = width / 2.0, narrow / 2.0
    end, shoulder = length / 2.0, length / 2.0 - taper
    if shoulder <= 0.0:
        outline = np.array(
            [
                (-half_narrow, -end),
                (half_narrow, -end),
                (half_wide, 0.0),
                (half_narrow, end),
                (-half_narrow, end),
                (-half_wide, 0.0),
            ]
        )
    else:
        outline = np.array(
            [
                (-half_narrow, -end),
                (half_narrow, -end),
                (half_wide, -shoulder),
                (half_wide, shoulder),
                (half_narrow, end),
                (-half_narrow, end),
                (-half_wide, shoulder),
                (-half_wide, -shoulder),
            ]
        )
    return MeshData.of(trimesh.creation.extrude_polygon(_polygon(outline), height=height))


def _slot_outline(width: float, length: float, segments: int) -> np.ndarray:
    radius = width / 2.0
    offset = (length - width) / 2.0
    half = max(segments // 2, 3)
    right = np.linspace(-math.pi / 2.0, math.pi / 2.0, half)
    left = np.linspace(math.pi / 2.0, 3.0 * math.pi / 2.0, half)
    return np.vstack(
        [
            np.column_stack([offset + radius * np.cos(right), radius * np.sin(right)]),
            np.column_stack([-offset + radius * np.cos(left), radius * np.sin(left)]),
        ]
    )


def wedge(width: float, depth: float, height: float, tip: float = 0.0) -> MeshData:
    """Eine Rampe: unten volle ``depth``, oben ``tip``.

    Die Form, aus der eine Rastnase und ein Schnapphaken bestehen — sie druckt
    ohne Stütze, weil sie auf dem Weg nach unten nach außen wächst, nicht nach
    oben.

    Als extrudierter Umriss gebaut statt aus acht Ecken von Hand: mit ``tip``
    auf null fielen zwei dieser Ecken zusammen, und ein Körper mit einer
    entarteten Fläche ist nicht wasserdicht (§24.3).
    """
    outline = [(0.0, 0.0), (depth, 0.0), (tip, height), (0.0, height)]
    if tip <= 0.0:
        outline = [(0.0, 0.0), (depth, 0.0), (0.0, height)]

    body = trimesh.creation.extrude_polygon(_polygon(np.array(outline)), height=width)
    # Der Umriss liegt in XY und wuchs entlang Z; ihn so drehen, dass die Tiefe
    # entlang Y läuft, die Höhe entlang Z und die Extrusion quer über X,
    # zentriert.
    body.apply_transform(
        np.array(
            [
                [0.0, 0.0, 1.0, -width / 2.0],
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
    )
    return MeshData.of(body)


def thread_body(
    diameter: float,
    pitch: float,
    height: float,
    *,
    depth: float | None = None,
    segments: int = SEGMENTS,
    internal: bool = False,
) -> MeshData:
    """Ein druckbares Gewinde als helikaler Gang — oder, invertiert, ein
    Gewindeloch.

    Kein ISO-Profil: ein Drucker kann es nicht auflösen, und etwas anderes zu
    behaupten wäre die Art Genauigkeit, die Vertrauen kostet (§39). Gebaut wird
    die Form, die Drucker wirklich benutzen — ein dreieckiger Gang mit
    abgeflachtem Kamm, den die Düse ohnehin rundet.

    Das Netz wird von Hand vernäht statt gesweept, denn ein Sweep lässt die
    Enden offen, und ein Baustein, der nicht wasserdicht ist, ist kein
    Baustein (§24.3).
    """
    steps = max(round(height / pitch), 1) * segments
    if depth is None:
        depth = pitch * RIDGE_SHARE
    radius = diameter / 2.0
    inner = radius + depth if internal else radius - depth

    angles = np.linspace(0.0, 2.0 * math.pi * height / pitch, steps + 1)
    heights = np.linspace(0.0, height, steps + 1)

    rings = []
    for angle, level in zip(angles, heights, strict=True):
        direction = np.array([math.cos(angle), math.sin(angle), 0.0])
        up = np.array([0.0, 0.0, 1.0])
        crest = direction * radius
        root = direction * inner
        rings.append(
            [
                root + up * level,
                crest + up * (level + pitch * 0.25),
                crest + up * (level + pitch * RIDGE_SHARE),
                root + up * (level + pitch * RIDGE_END),
            ]
        )

    vertices = np.array([point for ring in rings for point in ring], dtype=float)
    faces: list[list[int]] = []
    per_ring = 4
    for index in range(len(rings) - 1):
        base = index * per_ring
        following = base + per_ring
        for corner in range(per_ring):
            first = base + corner
            second = base + (corner + 1) % per_ring
            third = following + (corner + 1) % per_ring
            fourth = following + corner
            faces.append([first, second, third])
            faces.append([first, third, fourth])

    faces.extend(_cap(list(range(per_ring)), flip=True))
    last = (len(rings) - 1) * per_ring
    faces.extend(_cap([last + corner for corner in range(per_ring)], flip=False))

    body = trimesh.Trimesh(vertices=vertices, faces=np.array(faces, dtype=np.int64), process=True)
    trimesh.repair.fix_normals(body)
    return MeshData.of(body)


def _cap(indices: list[int], flip: bool) -> list[list[int]]:
    """Schließt einen Vierpunkt-Ring mit zwei Dreiecken."""
    first, second, third, fourth = indices
    faces = [[first, second, third], [first, third, fourth]]
    return [list(reversed(face)) for face in faces] if flip else faces


def _polygon(points: np.ndarray):  # type: ignore[no-untyped-def]
    from shapely.geometry import Polygon as ShapelyPolygon

    return ShapelyPolygon([(float(x), float(y)) for x, y in points])


def moved(mesh: MeshData, offset: Vec3) -> MeshData:
    body = mesh.raw.copy()
    body.apply_translation(np.asarray(offset, dtype=float))
    return mesh.replacing(body)


def turned(mesh: MeshData, degrees: float, axis: Vec3 = (0.0, 0.0, 1.0)) -> MeshData:
    body = mesh.raw.copy()
    body.apply_transform(
        trimesh.transformations.rotation_matrix(math.radians(degrees), np.asarray(axis))
    )
    return mesh.replacing(body)
