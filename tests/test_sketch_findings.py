"""Fehlerbilder aus der Durchsicht des Skizzenkerns (Bauplan §30.1).

Jeder Test hier hält **ein** gemessenes Fehlerbild fest — kein Sonderfall im
Code, sondern eine Datei im Korpus (AGENTS.md). Die Sollwerte sind analytisch
und nicht aus einem früheren Lauf abgeschrieben: Ein Pac-Man aus einem
270°-Bogen hat 3/4 der Kreisfläche, und daran misst sich, ob der Kern seinen
Drehsinn richtig liest.

Zwei Tests halten fest, was **nicht** kaputt war: Die durchgehende Tasche im
Netz trägt genau ihr Volumen ab, obwohl ihre Deckfläche koplanar mit der
Körperoberseite liegt, und eine Skizze aus lauter Bögen läuft nie in den
Konflikt-Zweig des Lösers. Beides stand als Verdacht in der Durchsicht; beides
ist nachgemessen und gilt.
"""

from __future__ import annotations

import math

import pytest

from app.core.brep.kernel import Solid, available
from app.core.brep.profiles import bounds
from app.core.sketch.profile import (
    Profile,
    ProfileSegment,
    arc_through,
    regions_of,
    signed_area,
)
from app.core.sketch.serialize import sketch_to_text
from app.core.sketch.solver import solve_sketch
from app.core.types import (
    SceneObject,
    Sketch,
    SketchConstraint,
    SketchElement,
    SolvedSketch,
)
from tests.test_sketch_ops import run, solid_of

needs_brep = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")

#: Der Radius des Pac-Man in allen Tests darüber.
PAC_RADIUS = 10.0
#: Sein Loch: Durchmesser drei, Mitte bei (4, -3) — mitten im Material, weit
#: weg vom fehlenden Viertel.
HOLE_CENTRE = (4.0, -3.0)
HOLE_RADIUS = 1.5


def pac_man() -> Sketch:
    """Ein Pac-Man mit einem Loch: 270°-Bogen, zwei Schenkel, ein Kreis.

    Der Bogen läuft gegen den Uhrzeigersinn von 135° nach 45° und nimmt damit
    den **langen** Weg — genau der Fall, an dem das Sehnenvieleck kippte. Das
    fehlende Viertel zeigt nach oben, das Loch liegt unten rechts im Material.
    """
    start = (
        PAC_RADIUS * math.cos(math.radians(135.0)),
        PAC_RADIUS * math.sin(math.radians(135.0)),
    )
    end = (PAC_RADIUS * math.cos(math.radians(45.0)), PAC_RADIUS * math.sin(math.radians(45.0)))
    rim = (HOLE_CENTRE[0] + HOLE_RADIUS, HOLE_CENTRE[1])
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("arc", ((0.0, 0.0), start, end)),
            SketchElement("line", (end, (0.0, 0.0))),
            SketchElement("line", ((0.0, 0.0), start)),
            SketchElement("circle", (HOLE_CENTRE, rim)),
        ),
    )


# --- Befund 1: der Bogen über 180° und der Drehsinn ----------------------------


def test_an_arc_over_half_a_turn_keeps_its_winding() -> None:
    """Der Umriss eines Pac-Man ist linksherum und misst 3/4 der Kreisfläche.

    Gemessen wurde -50,0 mm²: Das Sehnenvieleck sah nur ``start → end`` und
    bekam damit das umgekehrte Vorzeichen — der Stützpunkt stand in
    ``_points`` **hinter** dem Endpunkt, und ``end → via → end`` hebt sich in
    der Schuhbandformel auf.
    """
    outer = regions_of(solve_sketch(pac_man()))[0]

    assert signed_area(outer) == pytest.approx(0.75 * math.pi * PAC_RADIUS**2, rel=1e-9)
    assert signed_area(outer) > 0.0, "linksherum gezeichnet, also positiv"


def test_a_clockwise_pac_man_measures_the_same_area_the_other_way() -> None:
    """Andersherum gezeichnet dreht sich nur das Vorzeichen, nicht der Betrag.

    Die Zeichenfläche hat kein Rechteckwerkzeug: Welchen Drehsinn ein Umriss
    hat, entscheidet die Klickreihenfolge. Deshalb darf ``signed_area`` den
    Betrag nicht davon abhängig machen.

    Gespiegelt wird an der y-Achse und **ohne** die Kette umzudrehen: Eine
    Spiegelung kehrt den Drehsinn schon für sich um, die Reihenfolge bleibt
    dieselbe, und damit prüft der Vergleich genau das Vorzeichen — nicht
    nebenbei noch die Verkettung.
    """
    outer = regions_of(solve_sketch(pac_man()))[0]
    mirrored = Profile(
        segments=tuple(
            ProfileSegment(
                segment.kind,
                (-segment.start[0], segment.start[1]),
                (-segment.end[0], segment.end[1]),
                via=None if segment.via is None else (-segment.via[0], segment.via[1]),
                through=tuple((-x, y) for x, y in segment.through),
            )
            for segment in outer.segments
        )
    )

    assert signed_area(mirrored) == pytest.approx(-signed_area(outer), rel=1e-9)


@needs_brep
def test_a_pac_man_gets_smaller_when_it_is_drilled() -> None:
    """Ein Loch nimmt Material weg — das war der eigentliche Schaden.

    Gemessen: 1213,44 mm³ **mit** Loch gegen 1178,10 mm³ ohne, Soll 1142,75.
    Der Kern las das Loch als gleichsinnig, drehte es um und setzte es damit
    als zweite Außenkontur ein (``brep.profiles._face``).
    """
    drawn = sketch_to_text(pac_man())
    body = solid_of(run("sketch_extrude", sketch=drawn, height=5.0))

    solid_area = 0.75 * math.pi * PAC_RADIUS**2
    hole_area = math.pi * HOLE_RADIUS**2
    assert body.volume == pytest.approx((solid_area - hole_area) * 5.0, rel=1e-9)
    assert body.volume < solid_area * 5.0, "gebohrt wird kleiner, nicht größer"


# --- Befund 2: der Bogen, dessen Ende auf seinem Anfang liegt ------------------


def closed_arc(radius: float = 10.0) -> Sketch:
    """Eine Skizze aus **einem** Bogen, dessen Ende auf seinem Anfang liegt.

    ``_arc_midpoint`` und ``_flat_curve`` lesen das seit je als vollen Umlauf;
    die Ansicht zeichnet einen Kreis.
    """
    return Sketch(
        plane="plane:xy",
        elements=(SketchElement("arc", ((0.0, 0.0), (radius, 0.0), (radius, 0.0))),),
    )


def test_an_arc_that_closes_on_itself_encloses_a_face() -> None:
    """Was die Ansicht als Kreis zeichnet, ist auch für den Umriss einer.

    ``_outline`` gab für diese Kette zwei Punkte, daraus die Fläche null, und
    der Flächenfilter in ``regions_of`` warf „Die Skizze umschließt keine
    Fläche." — für eine Zeichnung, die auf dem Schirm ein Kreis war.
    """
    found = regions_of(solve_sketch(closed_arc()))

    assert len(found) == 1
    assert signed_area(found[0]) == pytest.approx(math.pi * 100.0, rel=1e-9)


def test_a_closed_arc_is_read_as_a_full_turn() -> None:
    """Die Umkehrung von ``_arc_midpoint``: drei Punkte zurück zum Kreis."""
    turn = arc_through((10.0, 0.0), (-10.0, 0.0), (10.0, 0.0))

    assert turn is not None
    centre, radius, sweep = turn
    assert centre == pytest.approx((0.0, 0.0), abs=1e-12)
    assert radius == pytest.approx(10.0, rel=1e-12)
    assert sweep == pytest.approx(2.0 * math.pi, rel=1e-12)


def test_three_points_on_a_line_carry_no_circle() -> None:
    """Keine Krümmung, kein Kreis — der Aufrufer nimmt dann die Sehne."""
    assert arc_through((0.0, 0.0), (5.0, 0.0), (10.0, 0.0)) is None


@needs_brep
def test_a_closed_arc_extrudes_to_a_cylinder() -> None:
    """Und im exakten Kern wird daraus ein Zylinder, kein ``StdFail_NotDone``.

    ``GC_MakeArcOfCircle`` macht aus drei Punkten, von denen zwei
    zusammenfallen, keinen Bogen; die C++-Ausnahme wurde nach der Regel in
    ``errors.py`` zu „Im Programm ist ein unerwarteter Fehler aufgetreten".
    """
    body = solid_of(run("sketch_extrude", sketch=sketch_to_text(closed_arc()), height=4.0))

    assert body.volume == pytest.approx(math.pi * 100.0 * 4.0, rel=1e-9)


def test_a_closed_arc_also_carries_through_the_mesh_path() -> None:
    """Derselbe Bogen auf dem Netzweg — ``geom.sketch_solid`` rechnet mit.

    Dort gab die Determinante des Umkreises null, ``outline_points`` kam mit
    einem einzigen Punkt zurück, und eine Tasche aus dieser Zeichnung endete
    mit „Aus diesem Umriss entsteht kein Körper." Das Netz nähert (72 Sehnen),
    deshalb steht hier eine relative Schranke und keine exakte Zahl.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.sketch_solid import extrude_profile
    from app.core.sketch import planes

    region = regions_of(solve_sketch(closed_arc(radius=3.0)))[0]
    frame = planes.frame_for_plane("plane:xy")
    assert frame is not None

    tool = MeshData.of(extrude_profile(region, -5.0, frame))
    assert tool.volume == pytest.approx(math.pi * 9.0 * 5.0, rel=2e-3)
    assert tool.volume < math.pi * 9.0 * 5.0, "ein Sehnenvieleck liegt innen"

    cube = MeshData.of(trimesh.creation.box(extents=(20, 20, 10)))
    entry = SceneObject(id="obj_1", name="mesh cube", mesh=cube)
    result = run("sketch_pocket", entry, sketch=sketch_to_text(closed_arc(3.0)), through=True)
    assert cube.volume - result.outputs[0].mesh.volume == pytest.approx(
        math.pi * 9.0 * 10.0, rel=2e-3
    )


# --- Befund 4: der Rotationskörper und sein Vieleck ----------------------------


@needs_brep
@pytest.mark.parametrize("corners", [3, 5, 6])
def test_a_revolved_polygon_stands_on_the_bed(corners: int) -> None:
    """„Der Körper steht auf dem Druckbett" — das stand im ``doc`` und galt nicht.

    ``rise = length / 2`` ist der halbe Umkreisdurchmesser und trifft nur beim
    Kreis. Ein Dreieck mit ``length=20`` reicht in y von -5 bis 10 und
    schwebte damit 5,00 mm über null, ein Sechseck 1,34 mm.
    """
    body = solid_of(
        run("sketch_revolve", shape="polygon", corners=corners, length=20.0, offset=10.0)
    )

    assert bounds(body)[2] == pytest.approx(0.0, abs=1e-9)


@needs_brep
@pytest.mark.parametrize("corners", [3, 5, 6])
def test_a_revolved_polygon_keeps_its_distance_from_the_axis(corners: int) -> None:
    """„Abstand der Innenkante des Querschnitts von der Drehachse" — ebenso.

    Der äußerste Punkt liegt beim vollen Umlauf um die Breite des Querschnitts
    weiter draußen als seine Innenkante. Wer beides kennt, kennt die
    Innenkante: Gemessen lag sie beim Dreieck 1,34 mm zu weit außen.

    Die Breite kommt aus derselben Eckenlage wie in ``shapes.polygon`` — die
    steht fest und wurde nicht angefasst; gemessen wird hier, wohin
    ``sketch_revolve`` das Ergebnis legt.
    """
    radius = 10.0
    start_angle = -math.pi / 2.0 - math.pi / corners
    width = (
        2.0
        * radius
        * max(abs(math.cos(start_angle + 2.0 * math.pi * k / corners)) for k in range(corners))
    )
    body = solid_of(
        run("sketch_revolve", shape="polygon", corners=corners, length=20.0, offset=10.0)
    )

    assert bounds(body)[3] == pytest.approx(10.0 + width, rel=1e-9), "außen = Abstand + Breite"


@needs_brep
def test_the_other_three_shapes_revolve_exactly_as_before() -> None:
    """Die Gegenprobe: Rechteck, Langloch und Kreis dürfen sich nicht bewegen.

    Für sie war die alte Formel richtig, und der gemessene Bereich gibt
    dieselbe Verschiebung — sonst wäre aus einer Reparatur eine stille
    Verhaltensänderung geworden.
    """
    ring = solid_of(run("sketch_revolve", shape="rectangle", length=5.0, width=8.0, offset=10.0))
    assert ring.volume == pytest.approx(2.0 * math.pi * 12.5 * 40.0, rel=1e-9)

    torus = solid_of(run("sketch_revolve", shape="circle", length=6.0, offset=10.0))
    assert torus.volume == pytest.approx(2.0 * math.pi * 13.0 * math.pi * 9.0, rel=1e-9)

    for shape, extra in (("rectangle", {"width": 8.0}), ("slot", {"width": 5.0}), ("circle", {})):
        body = solid_of(run("sketch_revolve", shape=shape, length=12.0, offset=7.0, **extra))
        assert bounds(body)[2] == pytest.approx(0.0, abs=1e-9), shape


# --- Befund 5: die koplanare Deckfläche der Netz-Tasche ------------------------


@pytest.mark.parametrize("through", [False, True])
def test_a_pocket_in_a_mesh_leaves_no_skin_on_top(through: bool) -> None:
    """Die Werkzeugdeckfläche liegt koplanar auf dem Körper — und das hält.

    Der exakte Weg gibt seinem Werkzeug oben einen Millimeter Zugabe, der
    Netzweg keine: Er beginnt genau bei ``top``, und bei ``top == high_s``
    heißt das koplanar. Der Verdacht war eine stehengebliebene Haut. Sie steht
    nicht — gemessen über beide Tiefenarten und über alle vier Stufen der
    Rückfallkette. ``manifold3d`` rechnet koplanare Flächen robust, und genau
    das sagt der Kommentar an ``BOOLEAN_OVERLAP`` schon.

    Der Test bleibt trotzdem: Er ist die Zusage, gegen die eine spätere
    Zugabe zu messen wäre.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    cube = MeshData.of(trimesh.creation.box(extents=(10, 10, 10)))
    entry = SceneObject(id="obj_1", name="mesh cube", mesh=cube)

    result = run(
        "sketch_pocket",
        entry,
        shape="rectangle",
        length=5.0,
        width=5.0,
        depth=2.0,
        through=through,
    )
    cut = result.outputs[0].mesh
    taken = 25.0 * (10.0 if through else 2.0)

    assert cube.volume - cut.volume == pytest.approx(taken, rel=1e-9)
    assert result.solver is not None and result.solver.strategy == "direct"
    assert not isinstance(cut, Solid), "aus einem Netz entsteht ein Netz"


# --- Befund 6: der Rückfall auf die erste Bedingung ----------------------------


@pytest.mark.parametrize(
    "elements",
    [
        (SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))),),
        (
            SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))),
            SketchElement("arc", ((5.0, 5.0), (7.0, 5.0), (5.0, 7.0))),
            SketchElement("arc", ((0.0, 0.0), (1e-3, 0.0), (900.0, 900.0))),
        ),
        (SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (10.0, 0.0))),),
    ],
)
def test_a_sketch_without_bearing_constraints_never_asks_who_conflicts(
    elements: tuple[SketchElement, ...],
) -> None:
    """``_conflict_pair`` und ``_redundant_pair`` geben im Rückfall ``0``.

    ``solve_sketch`` greift danach in ``sketch.constraints`` — bei leerer
    Liste wäre das ein ``IndexError``. Ist es nicht, und der Grund ist ein
    Argument: Ohne tragende Bedingung stammt jede Zeile aus ``_arc_equation``,
    die stehen auf getrennten Punkten und sind einzeln erfüllbar. Rest null,
    Rang voll, kein Zweig läuft an. Dieser Test hält das Argument fest — auch
    für ein Referenzmaß, das zählt als Bedingung, steht aber in keiner
    Gleichung.
    """
    solved = solve_sketch(Sketch(plane="plane:xy", elements=elements))
    assert solved.max_residual < 1e-9

    with_reference = solve_sketch(
        Sketch(
            plane="plane:xy",
            elements=elements,
            constraints=(SketchConstraint("reference", (1, 2)),),
        )
    )
    assert with_reference.max_residual < 1e-9


# --- Befund 3: der vierte Freiheitsgrad des Kreises ----------------------------


def test_a_circle_with_a_fixed_centre_and_a_diameter_is_determined() -> None:
    """Mitte fest, Durchmesser bemaßt — daran ist nichts mehr frei."""
    solved = solve_sketch(
        Sketch(
            plane="plane:xy",
            elements=(SketchElement("circle", ((0.0, 0.0), (5.0, 0.0))),),
            constraints=(
                SketchConstraint("fixed", (0,)),
                SketchConstraint("diameter", (0, 1), "10"),
            ),
        )
    )

    assert isinstance(solved, SolvedSketch)
    assert solved.free_dof == 0
