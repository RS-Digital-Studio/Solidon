"""Kleine Formen, aus denen die Bausteine gebaut werden (Bauplan §24.1).

Alles hier steht gegen ``manifold3d``, nicht gegen OpenSCAD (§24.1): ein
Baustein hängt so an keiner externen Installation und bleibt testbar.

**Und seit P2.7 sind die Aufrufe eine Formbeschreibung mit zwei Auswertern.**
Ein Baustein sagt „Zylinder, Sechskant, vereinigt, verschoben", und welcher
Kern daraus rechnet, wählt der Aufrufer mit :func:`building`: am Netzträger
das Netz wie bisher, am exakten Träger die Zwillinge in ``exact.py`` — ein
``Solid`` mit demselben Rahmen und denselben Maßen (`zwillinge.md`: der
Zweig endet ohne den zweiten Auswerter). Die Bausteine selbst ändern sich
dafür nicht; nur wer ein Netz **direkt** anfasst (``.raw``), verrät den
Kern und braucht seine Zeile.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Literal

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import InternalError
from app.core.geom import lathe, transform
from app.core.geom.mesh import MeshData
from app.core.types import Finding, Point2, Vec3

if TYPE_CHECKING:
    from app.core.brep.kernel import Solid

#: Was eine Grundform zurückgibt: ein Netz oder ein exakter Körper — je Kern.
type Form = MeshData | Solid

Kernel = Literal["mesh", "brep"]

#: Der Kern, in dem die Bausteine gerade bauen. Eine Kontextvariable und kein
#: Parameter, weil jeder Baustein sonst jede Grundform mit ihm aufrufen müsste
#: — 35 Bausteine, die nichts entscheiden, sondern nur durchreichen.
_KERNEL: ContextVar[Kernel] = ContextVar("solidon_parts_kernel", default="mesh")


#: Was ein Bau nebenbei zu sagen hat — eine gebrauchte Nahttoleranz zum
#: Beispiel. Die Formen geben nur Formen zurück; Befunde gehören trotzdem in
#: das ``PartResult``, nicht ins Protokoll (Regel in ``operationen.md``).
_NOTES: ContextVar[list[Finding] | None] = ContextVar("solidon_parts_notes", default=None)


@contextmanager
def building(kernel: Kernel) -> Iterator[list[Finding]]:
    """Innerhalb dieses Blocks bauen die Grundformen in ``kernel``.

    Die gelieferte Liste sammelt, was die Formen währenddessen über
    :func:`note` melden; der Aufrufer hängt sie an die Befunde des Teils.
    """
    notes: list[Finding] = []
    token = _KERNEL.set(kernel)
    kept = _NOTES.set(notes)
    try:
        yield notes
    finally:
        _NOTES.reset(kept)
        _KERNEL.reset(token)


def note(finding: Finding) -> None:
    """Ein Befund aus dem Bau einer Form — für den, der gerade baut."""
    notes = _NOTES.get()
    if notes is not None:
        notes.append(finding)


def building_exact() -> bool:
    """Ob gerade im exakten Kern gebaut wird."""
    return _KERNEL.get() == "brep"


def mesh_only(form: Form) -> MeshData:
    """Der Weg dahinter kennt nur das Netz — und sagt es, statt am Körper zu scheitern.

    Jede Stelle, die das ruft, fasst Dreiecke an: ``.raw``, eine Flächenmessung
    aus Dreiecksnormalen, eine Netzoperation. Sie ist damit der Ort, an dem
    ihre Bausteingruppe den exakten Zwilling noch schuldet (P2.7, eine Gruppe
    je Commit). Unter dem exakten Kern kommt sie nie dran: ``ops.EXACT_PARTS``
    lässt nur Bausteine dorthin, deren Weg ohne diese Funktion auskommt — ein
    ``Solid`` hier ist ein Programmfehler, kein Bedienfehler.
    """
    if isinstance(form, MeshData):
        return form
    raise InternalError(detail="a mesh-only part path received an exact body")


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

#: Der gerundete Schwalbenschwanz behält vom Vollkreis 300 Grad — von minus
#: 60 Grad an gezählt; die fehlenden 60 Grad ersetzt seine Sehne.
DOVETAIL_START = -math.pi / 3.0
DOVETAIL_ARC = 5.0 * math.pi / 3.0

#: Wo der flache Kamm eines Gangs beginnt, als Anteil der Steigung: Die
#: untere Flanke läuft vom Fuß bei null bis hierher, der Kamm liegt dann bis
#: ``RIDGE_SHARE``. Benannt, weil beide Auswerter dasselbe Profil lesen
#: (:func:`ridge_profile`) und der Test die Analytik daraus rechnet.
RIDGE_START = 0.25

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


def cylinder(diameter: float, height: float, *, segments: int = SEGMENTS) -> Form:
    """Auf Z = 0 stehend, nach oben wachsend — der Rahmen, den jeder Baustein
    benutzt.
    """
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.cylinder(diameter, height)
    body = lathe.cylinder(radius=diameter / 2.0, height=height, sections=segments)
    body.apply_translation([0.0, 0.0, height / 2.0])
    return MeshData.of(body)


def box(width: float, depth: float, height: float) -> Form:
    """In X und Y zentriert, auf Z = 0 stehend."""
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.box(width, depth, height)
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation([0.0, 0.0, height / 2.0])
    return MeshData.of(body)


def hexagon(width: float, height: float) -> Form:
    """Ein Sechskantprisma, ``width`` über die Schlüsselweite — eine Mutter,
    mit anderen Worten.
    """
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.hexagon(width, height)
    radius = width / math.sqrt(3.0)
    angles = np.linspace(0.0, 2.0 * math.pi, 7)[:-1] + math.pi / 6.0
    points = np.column_stack([radius * np.cos(angles), radius * np.sin(angles)])
    body = trimesh.creation.extrude_polygon(_polygon(points), height=height)
    return MeshData.of(body)


def dovetail(width: float, height: float, *, taper: float = 0.55) -> Form:
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
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.dovetail(width, height, taper=taper)
    broad = width / 2.0
    narrow = broad * taper
    depth = width / 2.0
    points = np.array(
        [[-narrow, -depth], [narrow, -depth], [broad, depth], [-broad, depth]], dtype=float
    )
    body = trimesh.creation.extrude_polygon(_polygon(points), height=height)
    return MeshData.of(body)


def cone(bottom: float, top: float, height: float, *, segments: int = SEGMENTS) -> Form:
    """Ein Kegelstumpf auf Z = 0 — eine Senkung, oder eine Fase."""
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.cone(bottom, top, height)
    profile = np.array(
        [[0.0, 0.0], [bottom / 2.0, 0.0], [top / 2.0, height], [0.0, height]], dtype=float
    )
    body = lathe.revolve(profile, sections=segments)
    return MeshData.of(body)


def slot(width: float, length: float, height: float, *, segments: int = SEGMENTS) -> Form:
    """Ein Langloch: zwei Halbkreise mit einem Rechteck dazwischen."""
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.slot(width, length, height)
    if length <= width:
        return cylinder(width, height, segments=segments)
    body = trimesh.creation.extrude_polygon(
        _polygon(_slot_outline(width, length, segments)), height=height
    )
    return MeshData.of(body)


def tapered_bar(width: float, narrow: float, length: float, height: float, taper: float) -> Form:
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
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.tapered_bar(width, narrow, length, height, taper)
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


def wedge(width: float, depth: float, height: float, tip: float = 0.0) -> Form:
    """Eine Rampe: unten volle ``depth``, oben ``tip``.

    Die Form, aus der eine Rastnase und ein Schnapphaken bestehen — sie druckt
    ohne Stütze, weil sie auf dem Weg nach unten nach außen wächst, nicht nach
    oben.

    Als extrudierter Umriss gebaut statt aus acht Ecken von Hand: mit ``tip``
    auf null fielen zwei dieser Ecken zusammen, und ein Körper mit einer
    entarteten Fläche ist nicht wasserdicht (§24.3).
    """
    outline: list[Point2] = [(0.0, 0.0), (depth, 0.0), (tip, height), (0.0, height)]
    if tip <= 0.0:
        outline = [(0.0, 0.0), (depth, 0.0), (0.0, height)]
    return prism_across(outline, width)


def prism_across(outline: Sequence[Point2], width: float) -> Form:
    """Ein Seitenriss, quer über X aufgezogen und zentriert.

    Der Umriss liegt in YZ — sein x ist die Tiefe entlang Y, sein y die Höhe
    entlang Z — und wird über ``width`` entlang X extrudiert, mittig. Die
    Rampe, der Federarm mit seinem Haken und jeder andere Körper, der aus
    einem Seitenriss besteht, entstehen so ohne innere Grenzfläche.
    """
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.prism_across(outline, width)
    body = trimesh.creation.extrude_polygon(_polygon(np.array(outline)), height=width)
    # Der Umriss liegt in XY und wuchs entlang Z; ihn so drehen, dass die Tiefe
    # entlang Y läuft, die Höhe entlang Z und die Extrusion quer über X,
    # zentriert.
    transform.moved(
        body,
        np.array(
            [
                [0.0, 0.0, 1.0, -width / 2.0],
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        ),
    )
    return MeshData.of(body)


def revolved(outline: Sequence[Point2]) -> Form:
    """Ein geschlossener Querschnitt (x = Abstand von der Achse, y = Höhe) um Z gedreht.

    Der Fuß und seine Tasche sind so eine Form: Säule und Fase als ein Umriss,
    ohne innere Fläche zwischen zwei Körpern. Am Netz mit ``SEGMENTS`` Ecken je
    Umfang (``lathe.revolve``, plattformgleiche Ecken), exakt als Drehkörper.
    """
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.revolved(outline)
    return MeshData.of(lathe.revolve([[float(x), float(y)] for x, y in outline], sections=SEGMENTS))


def rounded_dovetail(diameter: float, length: float) -> Form:
    """Ein gerundeter Schwalbenschwanz innerhalb seines Nenn-Umkreises.

    Ein Trapez mit gleicher Breite und Tiefe kann in seinem Umkreis höchstens
    ``diameter / √2`` stark sein. Bei der kleinsten Vorgabe waren das 0,707 mm
    und damit weniger als zwei Extrusionsbahnen. Hier bleibt die große
    Kreisbogen-Seite stehen; nur der rückwärtige 60-Grad-Bogen wird durch
    seine Sehne ersetzt. Diese Sehne bildet den schmalen Einstieg, der Bogen
    dahinter den Formschluss. Alle Punkte bleiben auf oder innerhalb des
    unveränderten Nenn-Umkreises. Exakt ist der Bogen ein Bogen; am Netz sind
    es ``SEGMENTS`` Sehnen je Vollkreis.
    """
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.rounded_dovetail(diameter, length)
    radius = diameter / 2.0
    arc_steps = round(SEGMENTS * DOVETAIL_ARC / (2.0 * math.pi))
    angles = [DOVETAIL_START + DOVETAIL_ARC * step / arc_steps for step in range(arc_steps + 1)]
    outline = [(radius * math.cos(angle), radius * math.sin(angle)) for angle in angles]
    return MeshData.of(trimesh.creation.extrude_polygon(_polygon(np.array(outline)), height=length))


def ridge_profile(
    diameter: float, pitch: float, *, depth: float | None = None, internal: bool = False
) -> tuple[Point2, ...]:
    """Das Gangprofil eines Umlaufs, radial und axial — die eine Quelle für beide Kerne.

    Vier Punkte: Fuß bei null, Kammbeginn bei ``RIDGE_START``, Kammende bei
    ``RIDGE_SHARE``, Fuß bei ``RIDGE_END`` — alles Anteile der Steigung, die
    Tiefe ``RIDGE_SHARE`` Steigungen. Außen liegt der Fuß eine Tiefe unter dem
    Durchmesser und der Kamm auf ihm; innen ist der Durchmesser die Bohrung,
    der Fuß liegt auf ihr und der Kamm eine Tiefe weiter außen. Der Netzweg
    (:func:`thread_body`) legt die Punkte je Ring an, der exakte
    (``exact.threaded``) führt sie entlang der Helix.
    """
    if depth is None:
        depth = pitch * RIDGE_SHARE
    radius = diameter / 2.0
    root = radius if internal else radius - depth
    crest = radius + depth if internal else radius
    return (
        (root, 0.0),
        (crest, pitch * RIDGE_START),
        (crest, pitch * RIDGE_SHARE),
        (root, pitch * RIDGE_END),
    )


def thread_body(
    diameter: float,
    pitch: float,
    height: float,
    *,
    depth: float | None = None,
    segments: int = SEGMENTS,
    internal: bool = False,
) -> Form:
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
    if building_exact():
        # Der Gang allein hat keinen exakten Zwilling: Exakt entstehen Kern und
        # Gang als ein genähter Körper (``build.threaded``), weil ihre
        # Vereinigung dort der unzuverlässigste Schritt wäre (P2.7, B1).
        raise InternalError(detail="the exact kernel builds core and ridge as one body")
    steps = max(round(height / pitch), 1) * segments
    profile = ridge_profile(diameter, pitch, depth=depth, internal=internal)

    angles = np.linspace(0.0, 2.0 * math.pi * height / pitch, steps + 1)
    heights = np.linspace(0.0, height, steps + 1)

    rings = []
    for angle, level in zip(angles, heights, strict=True):
        direction = np.array([math.cos(angle), math.sin(angle), 0.0])
        up = np.array([0.0, 0.0, 1.0])
        rings.append([direction * radial + up * (level + axial) for radial, axial in profile])

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


def moved(mesh: Form, offset: Vec3) -> Form:
    if not isinstance(mesh, MeshData):
        from app.core.knowledge.parts import exact as twins

        return twins.moved(mesh, offset)
    body = mesh.raw.copy()
    body.apply_translation(np.asarray(offset, dtype=float))
    return mesh.replacing(body)


def turned(mesh: Form, degrees: float, axis: Vec3 = (0.0, 0.0, 1.0)) -> Form:
    if not isinstance(mesh, MeshData):
        from app.core.knowledge.parts import exact as twins

        return twins.turned(mesh, degrees, axis)
    body = mesh.raw.copy()
    transform.moved(
        body, trimesh.transformations.rotation_matrix(math.radians(degrees), np.asarray(axis))
    )
    return mesh.replacing(body)
