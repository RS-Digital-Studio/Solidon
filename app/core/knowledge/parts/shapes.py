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
from app.core.units import EPS_GEOM, MAX_FACET_SAG, exact_cos, exact_cos_sin_array

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

#: Die Gangprofile der Gewindeformen (RM-544; welche Reihe welches baut, sagt
#: ``standards.THREAD_PROFILE_OF``). ``flat`` ist das druckbar abgeflachte Profil
#: von :func:`ridge_profile`, das die metrischen und die Unified-Gewinde tragen;
#: ``whitworth`` das gerundete 55°-Profil von G und R nach ISO 228-1 und ISO 7-1;
#: ``npt`` das 60°-Profil mit flachem Kamm nach ASME B1.20.1. Die zwei
#: Rohrgewindeprofile sind die der Norm, weil ein Rohrgewinde fast immer in ein
#: Metallteil greift — eine Armatur, einen Hahn —, eine gedruckte Schraube selten.
ThreadProfile = Literal["flat", "whitworth", "npt"]
THREAD_PROFILES: tuple[ThreadProfile, ...] = ("flat", "whitworth", "npt")

#: Der halbe Flankenwinkel des Whitworth-Profils: 55° zwischen den Flanken.
WHITWORTH_HALF_ANGLE = math.radians(27.5)

#: Die Gangtiefe des Whitworth-Profils als Anteil der Steigung: zwei Drittel der
#: Höhe des spitzen 55°-Dreiecks, H = P / (2 · tan 27,5°). ISO 228-1 nennt
#: h = 0,640327 P; dieselbe Zahl kommt hier aus dem Winkel.
WHITWORTH_DEPTH = 2.0 / 3.0 / (2.0 * math.tan(WHITWORTH_HALF_ANGLE))

#: Die Gangtiefe des NPT-Profils als Anteil der Steigung (ASME B1.20.1: h = 0,8 P).
NPT_DEPTH = 0.8

#: Die Gangtiefe je Profil als Anteil der Steigung.
DEPTH_SHARE: dict[ThreadProfile, float] = {
    "flat": RIDGE_SHARE,
    "whitworth": WHITWORTH_DEPTH,
    "npt": NPT_DEPTH,
}


def ridge_depth(pitch: float, profile: ThreadProfile = "flat") -> float:
    """Wie tief der Gang dieses Profils ist: der Anteil :data:`DEPTH_SHARE` der Steigung."""
    return pitch * DEPTH_SHARE[profile]


def _whitworth_outline() -> tuple[tuple[float, float], ...]:
    """Das gerundete 55°-Profil eines Gangs, axial und radial in Steigungen.

    Kamm und Grund sind Kreisbögen mit r = 0,137329·P, tangential an die Flanken
    (ISO 228-1), hier als Sehnen von höchstens gut dreißig Grad — das weicht um
    weniger als ein Zweihundertstel der Steigung ab, bei G 1/2 unter zehn
    Mikrometern. Der Gang beginnt und endet ein Stück neben der tiefsten Stelle
    des Grundbogens, wo dieser weniger als 0,003 P über dem Grund liegt: Zwischen
    zwei Umläufen bleibt so ein schmaler Grundstreifen (``helical_thread`` und
    der Netzbau verlangen ihn), und der Gang setzt auf dem Kern auf.
    """
    height = 1.0 / (2.0 * math.tan(WHITWORTH_HALF_ANGLE))
    sine = math.sin(WHITWORTH_HALF_ANGLE)
    radius = height / 6.0 * sine / (1.0 - sine)
    depth = WHITWORTH_DEPTH

    def arc(centre: tuple[float, float], degrees: Sequence[float]) -> list[tuple[float, float]]:
        return [
            (
                centre[0] + radius * math.cos(math.radians(angle)),
                centre[1] + radius * math.sin(math.radians(angle)),
            )
            for angle in degrees
        ]

    points = [
        *arc((0.0, radius), (-80.0, -53.75, -27.5)),
        *arc((0.5, depth - radius), (152.5, 121.25, 90.0, 58.75, 27.5)),
        *arc((1.0, radius), (-152.5, -126.25, -100.0)),
    ]
    start = points[0][0]
    shifted = [(axial - start, rise) for axial, rise in points]
    shifted[0] = (0.0, 0.0)
    shifted[-1] = (shifted[-1][0], 0.0)
    return tuple(shifted)


def _npt_outline() -> tuple[tuple[float, float], ...]:
    """Das 60°-Profil mit flachem Kamm und Grund, axial und radial in Steigungen.

    Die Flanken stehen 30° gegen die Senkrechte zur Achse und steigen über
    ``NPT_DEPTH``; Kamm und Grund sind gleich breite Flächen, zusammen das, was
    vom spitzen Dreieck (H = 0,866·P) über der Gangtiefe fehlt.
    """
    flank = NPT_DEPTH * math.tan(math.radians(30.0))
    flat = (1.0 - 2.0 * flank) / 2.0
    return ((0.0, 0.0), (flank, NPT_DEPTH), (flank + flat, NPT_DEPTH), (2.0 * flank + flat, 0.0))


#: Die Profile außer ``flat`` als Umriss in Steigungen (axial, radial), einmal gerechnet.
_OUTLINES: dict[ThreadProfile, tuple[tuple[float, float], ...]] = {
    "whitworth": _whitworth_outline(),
    "npt": _npt_outline(),
}

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
    transform.moved(body, transform.translation((0.0, 0.0, height / 2.0)))
    return MeshData.of(body)


def box(width: float, depth: float, height: float) -> Form:
    """In X und Y zentriert, auf Z = 0 stehend."""
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.box(width, depth, height)
    body = trimesh.creation.box(extents=(width, depth, height))
    transform.moved(body, transform.translation((0.0, 0.0, height / 2.0)))
    return MeshData.of(body)


def rounded_corners(width: float, depth: float, radius: float) -> tuple[Point2, ...]:
    """Die vier Bogenmitten eines gerundeten Rechtecks, im Quadrantenumlauf ab +X/+Y.

    Einmal hier, damit Netz und exakter Kern ihre Bögen um dieselben Punkte
    schlagen — der Zwilling in ``exact.py`` liest sie von hier.
    """
    return (
        (width / 2.0 - radius, depth / 2.0 - radius),
        (-width / 2.0 + radius, depth / 2.0 - radius),
        (-width / 2.0 + radius, -depth / 2.0 + radius),
        (width / 2.0 - radius, -depth / 2.0 + radius),
    )


def rounded_box(width: float, depth: float, height: float, radius: float) -> Form:
    """Ein Quader mit vier gerundeten senkrechten Kanten — der Rahmen von :func:`box`.

    Die Form der Organizer-Wanne und ihres Randes. Am Netz ein aufgezogener
    Umriss, dessen Ecken nach ``MAX_FACET_SAG`` in Sehnen zerlegt sind, in
    Float64 nativ über ``manifold3d``; exakt vier echte Viertelkreise. Die
    Außenmaße bleiben in beiden Kernen exakt: Jeder Sehnenpunkt liegt auf dem
    Bogen, und der Bogen berührt die Geraden. Ein Radius von null ist der
    Quader. Ob der Radius in den Körper passt, prüft der Aufrufer — die Absage
    dazu gehört zu seinen Feldern (``containers.rounded_prism``).
    """
    if radius <= EPS_GEOM:
        return box(width, depth, height)
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.rounded_box(width, depth, height, radius)
    import manifold3d

    count = 4
    while radius * (1 - exact_cos(math.pi / (4 * count))) > MAX_FACET_SAG:
        count += 1
    vertices: list[tuple[float, float]] = []
    for quadrant, (cx, cy) in enumerate(rounded_corners(width, depth, radius)):
        cos, sin = exact_cos_sin_array(
            np.linspace(quadrant * math.pi / 2, (quadrant + 1) * math.pi / 2, count + 1)
        )
        for point in zip((cx + radius * cos).tolist(), (cy + radius * sin).tolist(), strict=True):
            if not vertices or math.dist(point, vertices[-1]) > EPS_GEOM:
                vertices.append(point)
    built = manifold3d.CrossSection([vertices]).extrude(height).to_mesh64()
    return MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(built.vert_properties[:, :3], copy=True),
            faces=np.array(built.tri_verts, copy=True),
            process=False,
        )
    )


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


def slot(width: float, length: float, height: float, *, segments: int | None = None) -> Form:
    """Ein Langloch: zwei Halbkreise mit einem Rechteck dazwischen.

    Ohne ``segments`` so viele Ecken, dass die Sehnen der Halbkreise höchstens
    ``MAX_FACET_SAG`` innen liegen (:func:`slot_segments`) — bis zu einem
    Halbmesser von 21,4 mm die achtundvierzig von früher. Darüber wich das runde
    Ende einer Lasche für M64 bis zum 06.10.2026 um 0,13 mm vom Kreis ab.
    """
    if building_exact():
        from app.core.knowledge.parts import exact as twins

        return twins.slot(width, length, height)
    if segments is None:
        segments = slot_segments(width / 2.0)
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


def slot_segments(radius: float) -> int:
    """Ecken eines Langlochs, ein Vielfaches von ``SEGMENTS``, mit Sehnen bis ``MAX_FACET_SAG``.

    Gemessen am Umriss, wie :func:`_slot_outline` ihn legt: Jeder Halbkreis hat
    ``segments // 2`` Punkte, also einen Schritt von ``π / (segments // 2 - 1)``,
    und die tiefste Sehne liegt um ``r · (1 - cos(Schritt / 2))`` innen.
    """
    count = SEGMENTS
    while radius * (1.0 - exact_cos(math.pi / (2.0 * (count // 2 - 1)))) > MAX_FACET_SAG:
        count += SEGMENTS
    return count


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
    diameter: float,
    pitch: float,
    *,
    depth: float | None = None,
    internal: bool = False,
    profile: ThreadProfile = "flat",
) -> tuple[Point2, ...]:
    """Das Gangprofil eines Umlaufs, radial und axial — die eine Quelle für beide Kerne.

    ``flat``, vier Punkte: Fuß bei null, Kammbeginn bei ``RIDGE_START``, Kammende
    bei ``RIDGE_SHARE``, Fuß bei ``RIDGE_END`` — alles Anteile der Steigung, die
    Tiefe ``RIDGE_SHARE`` Steigungen. ``whitworth`` und ``npt`` folgen ihrem
    Umriss (:data:`_OUTLINES`) mit der Tiefe aus :data:`DEPTH_SHARE`. Außen liegt
    der Fuß eine Tiefe unter dem Durchmesser und der Kamm auf ihm; innen ist der
    Durchmesser die Bohrung, der Fuß liegt auf ihr und der Kamm eine Tiefe
    weiter außen. Der Netzweg (:func:`thread_body`) legt die Punkte je Ring an,
    der exakte (``exact.threaded``) führt sie entlang der Helix.
    """
    if depth is None:
        depth = ridge_depth(pitch, profile)
    radius = diameter / 2.0
    root = radius if internal else radius - depth
    crest = radius + depth if internal else radius
    if profile == "flat":
        return (
            (root, 0.0),
            (crest, pitch * RIDGE_START),
            (crest, pitch * RIDGE_SHARE),
            (root, pitch * RIDGE_END),
        )
    scale = depth / DEPTH_SHARE[profile]
    return tuple((root + rise * scale, axial * pitch) for axial, rise in _OUTLINES[profile])


def turn_segments(radius: float) -> int:
    """Wie viele Sehnen ein Gewinde je Umlauf am Netz bekommt: ein Vielfaches von ``SEGMENTS``.

    So viele, dass die Sehne am äußersten ``radius`` des Gangs höchstens
    ``MAX_FACET_SAG`` von der Rundung abweicht. Achtundvierzig halten das bis
    Ø 46 mm, und dort bleibt es — die Tabellengewinde bis M42 behalten ihre
    Sehnenzahl (ihr Netz ändert sich trotzdem: ``THREAD_MESH_WHOLE_TURNS``). Ein
    Gewinde mit eigenem Maß darüber bekam bis zum 06.10.2026 ebenfalls nur
    achtundvierzig, bei Ø 66 ein Vieleck mit 0,07 mm Abweichung, bei Ø 500 mit
    0,53 mm — mehr als das Spiel, mit dem Schraube und Mutter ineinandergehen.
    Ein Vielfaches, damit Kern und Gang auf denselben Winkeln liegen und ein
    Werkzeug mit ``SEGMENTS`` Ecken weiter auf jeder zweiten, dritten … sitzt.
    """
    count = SEGMENTS
    while radius * (1.0 - exact_cos(math.pi / count)) > MAX_FACET_SAG:
        count += SEGMENTS
    return count


def thread_body(
    diameter: float,
    pitch: float,
    height: float,
    *,
    depth: float | None = None,
    segments: int = SEGMENTS,
    internal: bool = False,
    profile: ThreadProfile = "flat",
    starts: int = 1,
    left: bool = False,
    taper: float = 0.0,
    reference: float = 0.0,
) -> Form:
    """Ein druckbares Gewinde als helikaler Gang — oder, invertiert, ein
    Gewindeloch.

    Im Profil ``flat`` kein ISO-Profil: ein Drucker kann es nicht auflösen, und
    etwas anderes zu behaupten wäre die Art Genauigkeit, die Vertrauen kostet
    (§39). Gebaut wird die Form, die Drucker wirklich benutzen — ein dreieckiger
    Gang mit abgeflachtem Kamm, den die Düse ohnehin rundet. Die Rohrgewinde
    tragen ihr Normprofil (:data:`ThreadProfile`).

    ``starts`` Gänge teilen sich den Vorschub ``starts · pitch``, jeder um eine
    Steigung über dem vorigen; ``left`` spiegelt den Gang an der Ebene durch die
    Achse und den Winkel null, die Lage der Gänge dort bleibt. ``taper`` ist der
    Zuwachs des Halbmessers je Millimeter Höhe (ein kegeliges Rohrgewinde), und
    ``diameter`` gilt auf der Höhe ``reference``. ``height`` ist der Weg je Gang;
    ein mehrgängiger Körper reicht um ``(starts - 1) · pitch`` darüber hinaus.

    Das Netz wird von Hand vernäht statt gesweept, denn ein Sweep lässt die
    Enden offen, und ein Baustein, der nicht wasserdicht ist, ist kein
    Baustein (§24.3).
    """
    if building_exact():
        # Der Gang allein hat keinen exakten Zwilling: Exakt entstehen Kern und
        # Gang als ein genähter Körper (``build.threaded``), weil ihre
        # Vereinigung dort der unzuverlässigste Schritt wäre (P2.7, B1).
        raise InternalError(detail="the exact kernel builds core and ridge as one body")
    lead = starts * pitch
    steps = max(round(height / lead), 1) * segments
    outline = ridge_profile(diameter, pitch, depth=depth, internal=internal, profile=profile)
    radial = np.array([point[0] for point in outline])
    axial = np.array([point[1] for point in outline])
    per_ring = len(outline)
    ring_count = steps + 1

    # **Gebündelt, Bit für Bit wie Ring für Ring** (RM-544): Jede Ecke ist
    # ``Richtung · Radius + oben · Höhe`` in genau dieser Folge der Rechenschritte,
    # nur für alle Stationen zugleich; die Winkel kommen aus
    # ``exact_cos_sin_array``, die Bits aus ``exact_cos``/``exact_sin``.
    # ``tests/test_threads.py`` hält das Netz gegen den alten Weg fest.
    cos, sin = exact_cos_sin_array(np.linspace(0.0, 2.0 * math.pi * height / lead, steps + 1))
    direction = np.stack([cos, sin, np.zeros_like(cos)], axis=1)[:, np.newaxis, :]
    del cos, sin
    up = np.array([0.0, 0.0, 1.0])
    side = _ridge_sides(ring_count, per_ring)
    vertex_blocks: list[np.ndarray] = []
    face_blocks: list[np.ndarray] = []
    for course in range(starts):
        offset = sum(len(points) for points in vertex_blocks)
        levels = (np.linspace(0.0, height, steps + 1) + course * pitch)[:, np.newaxis] + axial
        reach = radial + taper * (levels - reference) if taper else radial[np.newaxis, :]
        points = (direction * reach[:, :, np.newaxis] + up * levels[:, :, np.newaxis]).reshape(
            -1, 3
        )
        del levels, reach
        start_ring = [offset + corner for corner in range(per_ring)]
        last = offset + (ring_count - 1) * per_ring
        end_ring = [last + corner for corner in range(per_ring)]
        if per_ring == 4:
            caps = _cap(start_ring, flip=True) + _cap(end_ring, flip=False)
        else:
            # Die Stirnflächen eines Profils mit mehr als vier Punkten sind ein
            # Fächer um ihre Mitte; das Profil ist von dort aus ganz zu sehen.
            centres = offset + ring_count * per_ring
            caps = _fan(start_ring, centres, flip=True) + _fan(end_ring, centres + 1, flip=False)
            first_ring = points[:per_ring]
            last_ring = points[-per_ring:]
            points = np.vstack([points, first_ring.mean(axis=0), last_ring.mean(axis=0)])
        vertex_blocks.append(points)
        face_blocks += [side + offset, np.array(caps, dtype=np.int64)]
    del direction, side

    vertices = np.vstack(vertex_blocks) if len(vertex_blocks) > 1 else vertex_blocks[0]
    faces = np.vstack(face_blocks)
    del vertex_blocks, face_blocks
    if left:
        # Gespiegelt an der Ebene y = 0: Die Gänge bei Winkel null bleiben, wo
        # sie sind, und ihr Drehsinn kehrt sich um. Die Spiegelung dreht auch
        # jedes Dreieck um, deshalb die umgekehrte Eckenfolge.
        vertices = vertices * np.array([1.0, -1.0, 1.0])
        faces = np.ascontiguousarray(faces[:, ::-1])
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    trimesh.repair.fix_normals(body, multibody=starts > 1)
    return MeshData.of(body)


def _ridge_sides(ring_count: int, per_ring: int) -> np.ndarray:
    """Die Mantelfläche des Gangs: je Ring und Profilecke zwei Dreiecke zum nächsten Ring.

    Reihenfolge wie Ring für Ring: Ring, dann Ecke, dann die zwei Dreiecke
    ``(erste, zweite, dritte)`` und ``(erste, dritte, vierte)``.
    """
    corner = np.arange(per_ring, dtype=np.int64)
    following = (corner + 1) % per_ring
    base = np.arange(ring_count - 1, dtype=np.int64)[:, np.newaxis] * per_ring
    first = base + corner
    second = base + following
    third = base + per_ring + following
    fourth = base + per_ring + corner
    pairs = np.stack(
        [np.stack([first, second, third], axis=-1), np.stack([first, third, fourth], axis=-1)],
        axis=2,
    )
    return pairs.reshape(-1, 3)


def _cap(indices: list[int], flip: bool) -> list[list[int]]:
    """Schließt einen Vierpunkt-Ring mit zwei Dreiecken."""
    first, second, third, fourth = indices
    faces = [[first, second, third], [first, third, fourth]]
    return [list(reversed(face)) for face in faces] if flip else faces


def _fan(indices: list[int], centre: int, flip: bool) -> list[list[int]]:
    """Schließt einen Ring mit einem Fächer um seine Mitte, gedreht wie :func:`_cap`."""
    faces = [
        [centre, indices[corner], indices[(corner + 1) % len(indices)]]
        for corner in range(len(indices))
    ]
    return [list(reversed(face)) for face in faces] if flip else faces


def _polygon(points: np.ndarray):  # type: ignore[no-untyped-def]
    from shapely.geometry import Polygon as ShapelyPolygon

    return ShapelyPolygon([(float(x), float(y)) for x, y in points])


def moved(mesh: Form, offset: Vec3) -> Form:
    if not isinstance(mesh, MeshData):
        from app.core.knowledge.parts import exact as twins

        return twins.moved(mesh, offset)
    body = mesh.raw.copy()
    transform.moved(body, transform.translation(offset))
    return mesh.replacing(body)


def turned(mesh: Form, degrees: float, axis: Vec3 = (0.0, 0.0, 1.0)) -> Form:
    if not isinstance(mesh, MeshData):
        from app.core.knowledge.parts import exact as twins

        return twins.turned(mesh, degrees, axis)
    body = mesh.raw.copy()
    # Dieselbe Matrix wie der exakte Zwilling — exakt bei 90 und 180 Grad.
    transform.moved(body, transform.rotation_about(axis, (0.0, 0.0, 0.0), degrees))
    return mesh.replacing(body)
