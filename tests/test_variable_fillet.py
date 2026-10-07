"""P6.1 — Verrunden mit veränderlichem Radius, an beiden Kernen.

Konzept §13.2, Zeile P6.1: Radiuswerte an dauerhaft referenzierten Stellen
einer Kante oder Kantenkette; unabhängige Querschnitte prüfen Sollradien,
Übergänge und die größte Netzabweichung; unmögliche Radien erzeugen einen
Handlungsvorschlag und keine Teiländerung.

**Die Sollwerte stammen nicht aus dem Prüfling.** Der Radiusverlauf kommt für
zwei Stellen aus der Geraden und für mehr Stellen aus ``scipy``s
``PchipInterpolator`` — einer fremden Umsetzung derselben monotonen
Hermite-Interpolation. Das abgetragene Volumen an einer rechtwinkligen Kante
ist ``(1 − π/4) · ∫ r(s)² ds``, der Radius in einem Querschnitt der Kreis durch
die Punkte der Rundung, beide ohne Umweg über die Operation gerechnet.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
import trimesh
from scipy import integrate
from scipy.interpolate import PchipInterpolator

from app.core.bootstrap import load_operations
from app.core.errors import CORRECT_INPUT, AppError, GeometryError, ValidationError
from app.core.geom.edges import RadiusLaw, edges_of, round_edges
from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, OpResult, Profile, Scene, SceneObject
from app.core.units import MAX_FACET_ANGLE, MAX_FACET_SAG
from tests.helpers import exact_kernel

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0
#: Die obere vordere Kante des Quaders: entlang X, bei y = -15 und z = 20.
FRONT_TOP = (-DEPTH / 2.0, HEIGHT)


def block() -> MeshData:
    """Der Quader auf der Platte, wie ``brep.edit.box`` ihn legt."""
    body = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    body.apply_translation((0.0, 0.0, HEIGHT / 2.0))
    return MeshData(body)


def front_top_key(mesh: MeshData) -> str:
    """Der Schlüssel der oberen vorderen Kante."""
    from app.core.geom.edges import edge_key

    entry = next(
        entry
        for entry in edges_of(mesh)
        if abs(entry.middle[1] - FRONT_TOP[0]) < 1e-6 and abs(entry.middle[2] - FRONT_TOP[1]) < 1e-6
    )
    return edge_key(entry)


def reference(positions: list[float], radii: list[float]) -> Any:
    """Der Sollverlauf, unabhängig gerechnet: Gerade bei zwei Stellen, sonst scipy."""
    if len(positions) == 2:
        return lambda t: (
            radii[0] + (radii[1] - radii[0]) * (t - positions[0]) / (positions[1] - positions[0])
        )
    curve = PchipInterpolator(positions, radii)
    return lambda t: float(curve(t))


def removed_volume(law: Any, length: float) -> float:
    """``(1 − π/4) · ∫ r(s)² ds`` — der Zwickel an einer rechtwinkligen Kante."""
    value, _error = integrate.quad(lambda t: law(t) ** 2, 0.0, 1.0, limit=200)
    return (1.0 - math.pi / 4.0) * length * value


def polygon_share(radius: float) -> float:
    """Der Anteil des Zwickels, den ein Sehnenzug mit der Feinheit der Zusage lässt.

    Aus den zwei Grenzen der Zusage gerechnet (``MAX_FACET_SAG``,
    ``MAX_FACET_ANGLE``), nicht aus dem Prüfling: ``n`` Sehnen über einen
    rechten Winkel, der Zwickel ist ``r² − n·r²·sin(φ)/2``.
    """
    turn = min(2.0 * math.acos(1.0 - MAX_FACET_SAG / radius), MAX_FACET_ANGLE)
    steps = max(4, math.ceil((math.pi / 2.0) / turn))
    return 1.0 - steps * math.sin((math.pi / 2.0) / steps) / 2.0


def fit_circle(points: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Kreis durch Punkte (Kleinstquadrate): Mitte, Radius, größte Abweichung."""
    matrix = np.c_[2.0 * points, np.ones(len(points))]
    solution, *_ = np.linalg.lstsq(matrix, (points**2).sum(axis=1), rcond=None)
    centre = solution[:2]
    radius = float(np.sqrt(solution[2] + centre @ centre))
    worst = float(np.abs(np.linalg.norm(points - centre, axis=1) - radius).max())
    return centre, radius, worst


def mesh_section_arc(mesh: MeshData, x: float) -> np.ndarray:
    """Die Punkte der Rundung im Schnitt ``x = const`` — (y, z), ohne die zwei Flächen."""
    path = mesh.raw.section(plane_origin=(x, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0))
    assert path is not None, "der Schnitt trifft den Körper"
    points = np.asarray(path.vertices)[:, 1:]
    on_front = np.abs(points[:, 0] - FRONT_TOP[0]) < 1e-6
    on_top = np.abs(points[:, 1] - FRONT_TOP[1]) < 1e-6
    near = (points[:, 0] < 0.0) & (points[:, 1] > HEIGHT / 2.0)
    return points[near & ~on_front & ~on_top]


def exact_section_points(
    solid: Any, origin: tuple[float, float, float], normal: tuple[float, float, float]
) -> np.ndarray:
    """Liest native Schnittkurven ohne vorherige Tessellierung."""
    exact_kernel()
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    section = BRepAlgoAPI_Section(solid.shape, gp_Pln(gp_Pnt(*origin), gp_Dir(*normal)))
    section.Build()
    found = []
    explorer = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
    while explorer.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(explorer.Current()))
        for step in range(41):
            point = curve.Value(
                curve.FirstParameter()
                + (curve.LastParameter() - curve.FirstParameter()) * step / 40
            )
            found.append((point.X(), point.Y(), point.Z()))
        explorer.Next()
    return np.asarray(found)


def exact_section_arc(solid: Any, x: float) -> np.ndarray:
    """Dasselbe am exakten Körper, über ``BRepAlgoAPI_Section`` und die Kurven selbst."""
    points = exact_section_points(solid, (x, 0.0, 0.0), (1.0, 0.0, 0.0))[:, 1:]
    on_front = np.abs(points[:, 0] - FRONT_TOP[0]) < 1e-6
    on_top = np.abs(points[:, 1] - FRONT_TOP[1]) < 1e-6
    near = (points[:, 0] < 0.0) & (points[:, 1] > HEIGHT / 2.0)
    return points[near & ~on_front & ~on_top]


def run(
    op: str,
    entry: SceneObject,
    profile: Profile | None = None,
    **params: Any,
) -> OpResult:
    """Eine Operation so fahren, wie die Auswertung sie fährt."""
    load_operations()
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def imported(mesh: MeshData) -> SceneObject:
    return SceneObject(id="obj_1", name="Import", mesh=mesh)


def exact_body(solid: Any) -> SceneObject:
    return SceneObject(id="obj_1", name="Quader", mesh=solid, kind="brep")


# --- Der Verlauf selbst ---------------------------------------------------------


def test_two_stations_run_straight_from_start_to_end() -> None:
    """Zwei Stellen sind eine Gerade — „gleichmäßig von 2 auf 5"."""
    law = RadiusLaw((0.0, 1.0), (2.0, 5.0))
    for t in np.linspace(0.0, 1.0, 11):
        assert law.at(float(t)) == pytest.approx(2.0 + 3.0 * t, abs=1e-12)


@pytest.mark.parametrize(
    ("positions", "radii"),
    [
        ([0.0, 0.5, 1.0], [2.0, 5.0, 3.0]),
        ([0.0, 0.3, 0.7, 1.0], [2.0, 4.0, 4.0, 2.0]),
        ([0.0, 0.1, 1.0], [3.0, 1.0, 3.0]),
        ([0.0, 0.25, 0.5, 0.9, 1.0], [1.0, 1.5, 4.0, 4.5, 0.5]),
    ],
)
def test_more_stations_follow_the_monotone_hermite_curve(
    positions: list[float], radii: list[float]
) -> None:
    """Mehr Stellen: der monotone kubische Verlauf, gegen scipy als fremde Umsetzung.

    Monoton heißt: zwischen zwei Stellen nie über oder unter deren Werte —
    der größte Radius steht an einer Stelle und nirgends dazwischen.
    """
    law = RadiusLaw(tuple(positions), tuple(radii))
    want = reference(positions, radii)
    for t in np.linspace(0.0, 1.0, 201):
        assert law.at(float(t)) == pytest.approx(want(float(t)), abs=1e-12)
    assert law.largest == pytest.approx(max(radii))
    assert law.smallest == pytest.approx(min(radii))


def test_the_transitions_have_no_kink() -> None:
    """„Übergänge": Der Radius knickt an einer Zwischenstelle nicht (stetige Steigung)."""
    law = RadiusLaw((0.0, 0.4, 1.0), (2.0, 4.0, 3.0))
    step = 1e-7
    left = (law.at(0.4) - law.at(0.4 - step)) / step
    right = (law.at(0.4 + step) - law.at(0.4)) / step
    assert left == pytest.approx(right, abs=1e-4)


def test_reversing_swaps_start_and_end() -> None:
    law = RadiusLaw((0.0, 0.25, 1.0), (2.0, 3.0, 5.0), reversed=True)
    assert law.at(0.0) == pytest.approx(5.0)
    assert law.at(1.0) == pytest.approx(2.0)
    assert law.at(0.75) == pytest.approx(3.0)


# --- Die Parameter der Operation -------------------------------------------------


def test_the_stations_text_reads_percent_and_both_decimal_marks() -> None:
    from app.core.geom.edge_ops import radius_law

    load_operations()
    params = REGISTRY.get("fillet_edges").params(
        radius=2.0, mode="variable_radius", end_radius=5.0, stations="50:4  75:3,5; 90:4.25"
    )
    law = radius_law(params)
    assert law is not None
    assert law.positions == pytest.approx((0.0, 0.5, 0.75, 0.9, 1.0))
    assert law.radii == pytest.approx((2.0, 4.0, 3.5, 4.25, 5.0))


@pytest.mark.parametrize(
    "text", ["abc", "50", "150:3", "0:3", "100:3", "50:-1", "50:0", "50:300", "50:3 50:4"]
)
def test_a_wrong_stations_text_says_how_to_write_it(text: str) -> None:
    from app.core.geom.edge_ops import radius_law

    load_operations()
    params = REGISTRY.get("fillet_edges").params(
        radius=2.0, mode="variable_radius", end_radius=5.0, stations=text
    )
    with pytest.raises(ValidationError) as caught:
        radius_law(params)
    assert caught.value.field == "stations"
    assert CORRECT_INPUT in caught.value.suggestions


def test_the_constant_mode_ignores_end_radius_and_stations() -> None:
    """Die Vorgabe ist die alte Bedeutung: ein Radius, und die neuen Felder schweigen."""
    from app.core.geom.edge_ops import radius_law

    load_operations()
    params = REGISTRY.get("fillet_edges").params(radius=2.0, end_radius=9.0, stations="50:4")
    assert radius_law(params) is None


def test_old_steps_keep_their_meaning() -> None:
    """Ein gespeicherter Schritt ohne die neuen Felder rechnet wie zuvor."""
    old = run("fillet_edges", imported(block()), radius=3.0, edges="vertical")
    new = run(
        "fillet_edges", imported(block()), radius=3.0, edges="vertical", mode="constant_radius"
    )
    assert new.outputs[0].mesh.volume == pytest.approx(old.outputs[0].mesh.volume, abs=1e-9)
    expected = WIDTH * DEPTH * HEIGHT - 4.0 * polygon_share(3.0) * 9.0 * HEIGHT
    assert old.outputs[0].mesh.volume == pytest.approx(expected, abs=1e-3)


# --- Am Netz ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("positions", "radii"),
    [([0.0, 1.0], [2.0, 5.0]), ([0.0, 0.5, 1.0], [2.0, 5.0, 3.0])],
)
def test_mesh_sections_carry_the_wanted_radius(positions: list[float], radii: list[float]) -> None:
    """Unabhängige Querschnitte: Radius, Tangente an beide Flächen, größte Abweichung."""
    body = block()
    law = RadiusLaw(tuple(positions), tuple(radii))
    want = reference(positions, radii)
    outcome = round_edges(body, law.largest, "named", (front_top_key(body),), law=law)
    shaped = outcome.mesh

    assert shaped.raw.is_watertight and shaped.raw.body_count == 1
    for t in (0.05, 0.2, 0.37, 0.5, 0.63, 0.8, 0.95):
        x = -WIDTH / 2.0 + WIDTH * t
        arc = mesh_section_arc(shaped, x)
        assert len(arc) >= 4, f"im Schnitt bei t={t} liegt eine Rundung"
        radius = want(t)
        # Größte Netzabweichung: jeder Punkt der Rundung liegt höchstens eine
        # Sehnenabweichung neben dem Sollkreis (tangential an beide Flächen).
        centre = np.array([FRONT_TOP[0] + radius, FRONT_TOP[1] - radius])
        deviation = np.abs(np.linalg.norm(arc - centre, axis=1) - radius)
        assert float(deviation.max()) <= MAX_FACET_SAG, f"t={t}: {deviation.max():.4f}"


def test_mesh_removes_the_analytic_volume() -> None:
    """Das abgetragene Volumen folgt ``∫ r²`` — mit dem Sehnenanteil der Zusage."""
    body = block()
    law = RadiusLaw((0.0, 1.0), (2.0, 5.0))
    shaped = round_edges(body, 5.0, "named", (front_top_key(body),), law=law).mesh
    removed = WIDTH * DEPTH * HEIGHT - shaped.volume
    # Linear und gerade ist die Rundungsfläche ein Kegel und der Sehnenzug
    # liegt mit gleicher Unterteilung auf ihm: Soll ist der Polygonzwickel.
    share = polygon_share(5.0)
    expected = share * WIDTH * integrate.quad(lambda t: (2.0 + 3.0 * t) ** 2, 0.0, 1.0)[0]
    assert removed == pytest.approx(expected, rel=1e-6)
    # Gegen die Lehrbuchzahl nur als Richtung: Die Sehnen liegen innerhalb des
    # Bogens, der Sehnenzug nimmt mehr weg (bei R = 5 und sechs Sehnen 4,2 %).
    textbook = removed_volume(lambda t: 2.0 + 3.0 * t, WIDTH)
    assert removed > textbook
    assert removed / textbook == pytest.approx(share / (1.0 - math.pi / 4.0), rel=1e-6)


def test_mesh_start_is_the_left_end_and_reverse_swaps_it() -> None:
    """Dauerhafte Stelle: Anfang ist das linke, vordere oder untere Ende — nicht die Nummer.

    Bei x = −19 liegt die Stelle t = 1/40: 1 + 4/40 = 1,1 mm von vorn, umgekehrt 4,9.
    """
    body = block()
    key = (front_top_key(body),)
    forward = round_edges(body, 5.0, "named", key, law=RadiusLaw((0.0, 1.0), (1.0, 5.0))).mesh
    turned = RadiusLaw((0.0, 1.0), (1.0, 5.0), reversed=True)
    backward = round_edges(body, 5.0, "named", key, law=turned).mesh
    for shaped, wanted in ((forward, 1.1), (backward, 4.9)):
        _centre, radius, _worst = fit_circle(mesh_section_arc(shaped, -WIDTH / 2.0 + 1.0))
        assert radius == pytest.approx(wanted, abs=MAX_FACET_SAG)


def test_mesh_refuses_a_radius_that_leaves_no_room_and_changes_nothing() -> None:
    """Unmöglich: 25 mm an einer 20 mm hohen Wand — Satz mit Weg, kein halber Körper."""
    body = block()
    before = body.volume
    law = RadiusLaw((0.0, 1.0), (2.0, 25.0))
    with pytest.raises(GeometryError) as caught:
        round_edges(body, 25.0, "named", (front_top_key(body),), law=law)
    assert CORRECT_INPUT in caught.value.suggestions
    assert body.volume == pytest.approx(before)


def test_mesh_refuses_different_radii_meeting_at_a_corner() -> None:
    """Zwei gewählte Kanten mit verschiedenem Radius an einer Ecke: Satz statt Naht."""
    body = block()
    law = RadiusLaw((0.0, 1.0), (1.0, 3.0))
    with pytest.raises(GeometryError) as caught:
        round_edges(body, 3.0, "top", law=law)
    assert CORRECT_INPUT in caught.value.suggestions


def test_mesh_refuses_a_changing_radius_on_a_closed_loop() -> None:
    """Ein Ring hat keinen Anfang — gleiche Radien gehen, verschiedene nicht."""
    rod = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=48)
    rod.apply_translation((0.0, 0.0, 10.0))
    body = MeshData(rod)
    with pytest.raises(GeometryError):
        round_edges(body, 3.0, "top", law=RadiusLaw((0.0, 1.0), (1.0, 3.0)))
    same = round_edges(body, 2.0, "top", law=RadiusLaw((0.0, 1.0), (2.0, 2.0))).mesh
    plain = round_edges(body, 2.0, "top").mesh
    assert same.volume == pytest.approx(plain.volume, abs=1e-6)


# --- Am exakten Körper -------------------------------------------------------------


def front_top_exact_key(solid: Any) -> str:
    edit = exact_kernel()
    from app.core.geom.edges import edge_key

    entry = next(
        entry
        for entry in edit.edges_of(solid)
        if abs(entry.middle[1] - FRONT_TOP[0]) < 1e-6 and abs(entry.middle[2] - FRONT_TOP[1]) < 1e-6
    )
    return edge_key(entry)


@pytest.mark.parametrize(
    ("positions", "radii"),
    [
        ([0.0, 1.0], [2.0, 5.0]),
        ([0.0, 0.5, 1.0], [2.0, 5.0, 3.0]),
        ([0.0, 0.2, 1.0], [4.0, 1.5, 3.0]),
    ],
)
def test_exact_sections_are_circles_of_the_wanted_radius(
    positions: list[float], radii: list[float]
) -> None:
    """Am exakten Körper ist jeder Querschnitt ein Kreis mit dem Sollradius."""
    edit = exact_kernel()
    solid = edit.box(WIDTH, DEPTH, HEIGHT)
    law = RadiusLaw(tuple(positions), tuple(radii))
    want = reference(positions, radii)
    shaped = edit.fillet(solid, law.largest, "named", (front_top_exact_key(solid),), law=law)
    assert shaped.is_closed and shaped.solid_count == 1
    for t in (0.03, 0.2, 0.37, 0.5, 0.63, 0.8, 0.97):
        centre, radius, worst = fit_circle(exact_section_arc(shaped, -WIDTH / 2.0 + WIDTH * t))
        assert worst < 1e-6, "der Querschnitt ist ein Kreis"
        assert radius == pytest.approx(want(t), abs=1e-4)
        # Tangential an beide Flächen: Die Mitte liegt je einen Radius davor.
        assert centre[0] == pytest.approx(FRONT_TOP[0] + radius, abs=1e-4)
        assert centre[1] == pytest.approx(FRONT_TOP[1] - radius, abs=1e-4)
    removed = WIDTH * DEPTH * HEIGHT - shaped.volume
    assert removed == pytest.approx(removed_volume(want, WIDTH), abs=2e-3)


def test_exact_start_is_the_same_end_as_on_the_mesh() -> None:
    """Beide Kerne meinen mit „Anfang" dieselbe Stelle am Teil."""
    edit = exact_kernel()
    solid = edit.box(WIDTH, DEPTH, HEIGHT)
    law = RadiusLaw((0.0, 1.0), (1.0, 5.0))
    shaped = edit.fillet(solid, 5.0, "named", (front_top_exact_key(solid),), law=law)
    _centre, radius, _worst = fit_circle(exact_section_arc(shaped, -WIDTH / 2.0 + 1.0))
    assert radius == pytest.approx(1.1, abs=1e-4)


def test_a_mixed_corner_takes_a_varying_radius_only_at_the_exact_kernel() -> None:
    """RM-230: Eine Ecke aus einer Innen- und zwei Außenkanten mit Radiusverlauf.

    Das Netz sagt ab — sein örtlicher Ersatz der Ecke ist für ein Maß gebaut
    (``edges._mixed_corner_region``). Der exakte Kern baut sie, und gebaut heißt
    hier richtig: In der Mitte jeder Kante liegt die Rundung mit dem Radius des
    Verlaufs dort (3 → 1,5 → 3 mm), geprüft am Abstand ``r·(√2 − 1)`` der
    Rundung von der scharfen Kante entlang der Winkelhalbierenden.
    """
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN
    from shapely.geometry import Polygon

    from app.core.geom.edges import edge_key

    edit = exact_kernel()
    law = RadiusLaw((0.0, 0.5, 1.0), (3.0, 1.5, 3.0))
    # Die Mitten der drei Kanten an der Ecke (10, 10, 20): die senkrechte
    # Innenkante und die zwei Außenkanten oben am Ausschnitt.
    middles = ((10.0, 10.0, 10.0), (10.0, 15.0, 20.0), (15.0, 10.0, 20.0))

    def at_corner(entries: Any) -> list[Any]:
        return [
            entry
            for entry in entries
            if any(math.dist(entry.middle, middle) < 1e-6 for middle in middles)
        ]

    profile = Polygon([(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)])
    mesh = MeshData(trimesh.creation.extrude_polygon(profile, 20.0))
    with pytest.raises(GeometryError) as caught:
        round_edges(
            mesh, 3.0, "named", [edge_key(entry) for entry in at_corner(edges_of(mesh))], law=law
        )
    assert "Außen- und eine Innenkante" in str(caught.value.detail)

    solid = edit.boolean(
        "difference",
        [
            edit.moved(edit.box(20.0, 20.0, 20.0), (10.0, 10.0, 0.0)),
            edit.moved(edit.box(10.0, 10.0, 22.0), (15.0, 15.0, -1.0)),
        ],
    )
    chosen = at_corner(edit.edges_of(solid))
    assert len(chosen) == 3, "Voraussetzung: die Innenkante und die zwei Außenkanten oben"
    rounded = edit.fillet(solid, 3.0, "named", [edge_key(entry) for entry in chosen], law=law)
    assert rounded.is_closed and rounded.solid_count == 1

    reach = 1.5 * (math.sqrt(2.0) - 1.0)
    # Je Kantenmitte: die scharfe Kante, die Richtung in die Rundung hinein und
    # ob dort vorher Luft war (Innenkante: die Rundung füllt auf).
    probes = (
        ((10.0, 10.0, 10.0), (1.0, 1.0, 0.0), True),
        ((10.0, 15.0, 20.0), (-1.0, 0.0, -1.0), False),
        ((15.0, 10.0, 20.0), (0.0, -1.0, -1.0), False),
    )
    for edge, toward, filled in probes:
        unit = np.asarray(toward) / np.linalg.norm(toward)
        for step, beyond in ((reach - 0.02, False), (reach + 0.02, True)):
            point = np.asarray(edge) + unit * step
            inside = (
                BRepClass3d_SolidClassifier(rounded.shape, gp_Pnt(*point), 1e-7).State()
                == TopAbs_IN
            )
            assert inside is (filled is not beyond), (edge, step)


def test_exact_refuses_what_the_mesh_refuses() -> None:
    edit = exact_kernel()
    solid = edit.box(WIDTH, DEPTH, HEIGHT)
    with pytest.raises(GeometryError) as caught:
        edit.fillet(
            solid,
            25.0,
            "named",
            (front_top_exact_key(solid),),
            law=RadiusLaw((0.0, 1.0), (2.0, 25.0)),
        )
    assert CORRECT_INPUT in caught.value.suggestions
    with pytest.raises(GeometryError):
        edit.fillet(solid, 3.0, "top", law=RadiusLaw((0.0, 1.0), (1.0, 3.0)))
    rod = edit.cylinder(20.0, 20.0)
    with pytest.raises(GeometryError):
        edit.fillet(rod, 3.0, "top", law=RadiusLaw((0.0, 1.0), (1.0, 3.0)))


# --- Als Operation, an beiden Kernen -----------------------------------------------


def test_both_kernels_take_the_same_amount_away() -> None:
    """Dieselbe Eingabe an Netz und exaktem Körper: gleiche Form bis auf die Sehnen."""
    edit = exact_kernel()
    params = {
        "radius": 2.0,
        "mode": "variable_radius",
        "end_radius": 3.0,
        "stations": "50:5",
        "edges": "vertical",
    }
    meshed = run("fillet_edges", imported(block()), **params).outputs[0]
    exact = run("fillet_edges", exact_body(edit.box(WIDTH, DEPTH, HEIGHT)), **params).outputs[0]
    assert exact.kind == "brep" and meshed.kind == "mesh"
    want = reference([0.0, 0.5, 1.0], [2.0, 5.0, 3.0])
    full = WIDTH * DEPTH * HEIGHT
    assert full - exact.mesh.volume == pytest.approx(4.0 * removed_volume(want, HEIGHT), abs=5e-3)
    # Das Netz trägt mehr ab: Die Sehnen liegen innerhalb des Bogens. Soll ist
    # der Zwickel des Sehnenzugs mit der Feinheit des größten Radius.
    polygon = (
        4.0
        * polygon_share(5.0)
        * HEIGHT
        * integrate.quad(lambda t: want(t) ** 2, 0.0, 1.0, limit=200)[0]
    )
    assert full - meshed.mesh.volume == pytest.approx(polygon, rel=2e-3)
    assert full - meshed.mesh.volume > full - exact.mesh.volume


def test_a_vertical_edge_starts_at_the_bottom_on_both_kernels() -> None:
    """Eine senkrechte Kante beginnt unten — an beiden Kernen dieselbe Stelle.

    Die Rundung rückt die Ecke um ``r·(√2 − 1)`` von der scharfen Quaderecke ab:
    bei z = 0,5 mit r = 1,075 um 0,445 mm, bei z = 19,5 mit r = 3,925 um 1,626.
    """
    from app.core.geom.mesh import as_mesh_data

    edit = exact_kernel()
    params = {"radius": 1.0, "mode": "variable_radius", "end_radius": 4.0, "edges": "vertical"}
    corner = np.array([WIDTH / 2.0, DEPTH / 2.0])
    for entry in (imported(block()), exact_body(edit.box(WIDTH, DEPTH, HEIGHT))):
        mesh = as_mesh_data(run("fillet_edges", entry, **params).outputs[0].mesh)
        for height, radius in ((0.5, 1.075), (19.5, 3.925)):
            outline = mesh.raw.section(plane_origin=(0, 0, height), plane_normal=(0, 0, 1))
            points = np.asarray(outline.vertices)[:, :2]
            gap = float(np.min(np.linalg.norm(points - corner, axis=1)))
            assert gap == pytest.approx(radius * (math.sqrt(2.0) - 1.0), abs=2 * MAX_FACET_SAG)


def test_an_impossible_radius_is_a_sentence_with_the_largest_that_fits() -> None:
    """Regel 17: Die Absage nennt, was geht — an beiden Kernen derselbe Satz."""
    edit = exact_kernel()
    params = {"radius": 2.0, "mode": "variable_radius", "end_radius": 25.0, "edges": "vertical"}
    sentences = []
    for entry in (imported(block()), exact_body(edit.box(WIDTH, DEPTH, HEIGHT))):
        with pytest.raises(AppError) as caught:
            run("fillet_edges", entry, **params)
        assert CORRECT_INPUT in caught.value.suggestions
        sentences.append(str(caught.value.detail))
    assert sentences[0] == sentences[1]


# --- Eine Kantenkette: Gerade, Bogen, Gerade ------------------------------------------

CHAIN_ROUND = 5.0


def chain_length() -> float:
    """Länge der oberen Kette um eine gerundete senkrechte Ecke: 35 + πR/2 + 25."""
    return (WIDTH - CHAIN_ROUND) + math.pi * CHAIN_ROUND / 2.0 + (DEPTH - CHAIN_ROUND)


def chain_sections(mesh: MeshData) -> list[tuple[float, np.ndarray]]:
    """Querschnitte auf den geraden Stücken, mehr als einen Radius vom Bogen entfernt.

    Je Eintrag die Bogenlänge vom Anfang der Kette (links vorn) und die Punkte
    der Rundung (quer zur Kante, ohne die zwei Flächen).
    """
    found: list[tuple[float, np.ndarray]] = []
    for x in (-15.0, -5.0, 5.0):
        points = np.asarray(
            mesh.raw.section(plane_origin=(x, 0, 0), plane_normal=(1, 0, 0)).vertices
        )[:, 1:]
        keep = (points[:, 0] < -5.0) & (points[:, 1] > 10.0)
        keep &= (np.abs(points[:, 0] + DEPTH / 2.0) > 1e-6) & (np.abs(points[:, 1] - HEIGHT) > 1e-6)
        found.append((x + WIDTH / 2.0, points[keep]))
    for y in (-2.0, 5.0, 12.0):
        points = np.asarray(
            mesh.raw.section(plane_origin=(0, y, 0), plane_normal=(0, 1, 0)).vertices
        )[:, [0, 2]]
        keep = (points[:, 0] > 5.0) & (points[:, 1] > 10.0)
        keep &= (np.abs(points[:, 0] - WIDTH / 2.0) > 1e-6) & (np.abs(points[:, 1] - HEIGHT) > 1e-6)
        arc = math.pi * CHAIN_ROUND / 2.0
        along = (WIDTH - CHAIN_ROUND) + arc + (y + DEPTH / 2.0 - CHAIN_ROUND)
        found.append((along, points[keep]))
    return found


def test_a_tangent_chain_carries_one_law_on_both_kernels() -> None:
    """„Kantenkette": Ein Verlauf läuft über Gerade, Bogen und Gerade als ein Zug.

    Die obere Kante eines Quaders mit gerundeter senkrechter Ecke ist eine
    Kette aus drei Kanten. OpenCASCADE setzt eine Tabelle je Kante; mit einer
    einzigen für die ganze Kette lief der Verlauf über die erste Gerade allein
    (gemessen 2,17 statt 1,59 mm in ihrer Mitte). Soll ist der Radius an der
    Bogenlänge vom linken vorderen Ende, geteilt durch die Länge der Kette.
    """
    from app.core.geom.edges import edge_key
    from app.core.geom.mesh import as_mesh_data

    edit = exact_kernel()
    law = RadiusLaw((0.0, 1.0), (1.0, 3.0))
    total = chain_length()

    body = block()
    corner = next(e for e in edges_of(body) if e.upright and e.middle[0] > 0 and e.middle[1] < 0)
    rounded = round_edges(body, CHAIN_ROUND, "named", (edge_key(corner),)).mesh
    chain = next(e for e in edges_of(rounded) if abs(e.middle[2] - HEIGHT) < 1e-6 and e.length > 60)
    assert chain.length == pytest.approx(total, abs=0.05), "am Netz ist die Kette ein Zug"
    meshed = round_edges(rounded, 3.0, "named", (edge_key(chain),), law=law).mesh
    assert meshed.raw.is_watertight and meshed.raw.body_count == 1

    solid = edit.box(WIDTH, DEPTH, HEIGHT)
    upright = next(
        e for e in edit.edges_of(solid) if e.upright and e.middle[0] > 0 and e.middle[1] < 0
    )
    solid = edit.fillet(solid, CHAIN_ROUND, "named", (edge_key(upright),))
    front = next(
        e
        for e in edit.edges_of(solid)
        if abs(e.middle[2] - HEIGHT) < 1e-6 and abs(e.middle[1] + DEPTH / 2.0) < 1e-6
    )
    exact = edit.fillet(solid, 3.0, "named", (edge_key(front),), law=law)
    assert exact.is_closed and exact.solid_count == 1

    for along, arc in chain_sections(meshed):
        _centre, radius, _worst = fit_circle(arc)
        assert radius == pytest.approx(law.at(along / chain.length), abs=MAX_FACET_SAG)
    for along, arc in chain_sections(as_mesh_data(exact)):
        _centre, radius, _worst = fit_circle(arc)
        # Gemessen an der Tessellierung des exakten Körpers: ihre Sehnen liegen
        # innerhalb der Rundung, der Kreis durch sie ist um weniger als die
        # Tessellierungsgrenze kleiner.
        assert radius == pytest.approx(law.at(along / total), abs=MAX_FACET_SAG / 2.0)


def test_a_clicked_edge_offers_the_variable_fillet_as_its_own_row() -> None:
    """Direkter Eingabeweg: an der Kante eine Zeile mit Radius am Anfang und am Ende.

    Dieselbe Auskunft speist das Merkmalfenster und das Kontextmenü im Bild
    (``perceive.actions.edge_actions``); die Zeile bringt den Verlauf, die
    Einzelauswahl und den Schlüssel mit, der Kunde gibt nur die zwei Radien ein.
    """
    from app.core.perceive.actions import edge_actions

    load_operations()
    key = "e:-20.00,0.00,20.00:0.000,1.000,0.000"
    rows = [row for row in edge_actions(key) if row.op == "fillet_edges"]
    assert len(rows) == 2, "Verrunden und Verrunden mit Verlauf"
    varying = next(row for row in rows if dict(row.fixed).get("mode") == "variable_radius")
    assert [field.name for field in varying.fields] == ["radius", "end_radius"]
    assert dict(varying.fixed)["edges"] == "named"
    assert dict(varying.fixed)["edge_keys"] == key
    plain = next(row for row in rows if row is not varying)
    assert "mode" not in dict(plain.fixed), "die gewohnte Zeile bleibt der eine Radius"


# --- Ringe: Anfang und Ende sind dieselbe Stelle ---------------------------------------


def test_a_loop_law_runs_smoothly_over_its_seam() -> None:
    """Auf einem Ring ist der Verlauf periodisch: gleicher Wert und gleiche Steigung am Anfang."""
    law = RadiusLaw((0.0, 0.25, 0.6, 1.0), (1.0, 3.0, 2.0, 1.0)).as_loop()
    step = 1e-7
    assert law.at(0.0) == pytest.approx(law.at(1.0))
    rising = (law.at(step) - law.at(0.0)) / step
    arriving = (law.at(1.0) - law.at(1.0 - step)) / step
    assert rising == pytest.approx(arriving, abs=1e-4)
    for position, radius in ((0.25, 3.0), (0.6, 2.0)):
        assert law.at(position) == pytest.approx(radius)


RIM = 10.0
TOP = 20.0


def rim_radius_at(mesh: MeshData, angle_deg: float) -> float:
    """Der Rundungsradius im Schnitt durch die Achse, unter dem Winkel ``angle_deg`` (0° = +x)."""
    direction = np.array(
        [math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg)), 0.0]
    )
    normal = np.cross(direction, [0.0, 0.0, 1.0])
    section = mesh.raw.section(plane_origin=(0.0, 0.0, 0.0), plane_normal=normal)
    points = np.asarray(section.vertices)
    outward = points @ direction
    height = points[:, 2]
    keep = (outward > RIM / 2.0) & (height > TOP / 2.0)
    # Ohne Wand und Deckel: Die Ebene trifft die Facetten der Zylinderwand
    # mittig (0,02 mm innerhalb), also auch nahe daran nichts nehmen.
    keep &= (np.abs(outward - RIM) > MAX_FACET_SAG) & (np.abs(height - TOP) > MAX_FACET_SAG)
    _centre, radius, _worst = fit_circle(np.c_[outward[keep], height[keep]])
    return radius


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_round_rim_starts_at_its_left_point_and_runs_backwards_first(kind: str) -> None:
    """Der obere Rand eines Zylinders: Anfang links (−x), von dort nach hinten (+y).

    Radius 1 am Anfang und Ende, 3 bei einem Viertel: Mit der Regel liegt die
    Spitze hinten (90°), vorn (270°) steht der Verlauf auf dem Rückweg. Das Netz
    ist ein 96-Eck, der exakte Rand ein Kreis — beide meinen dieselbe Stelle.
    """
    from app.core.geom.mesh import as_mesh_data

    law = RadiusLaw((0.0, 0.25, 1.0), (1.0, 3.0, 1.0))
    if kind == "mesh":
        rod = trimesh.creation.cylinder(radius=RIM, height=TOP, sections=96)
        rod.apply_translation((0.0, 0.0, TOP / 2.0))
        shaped = round_edges(MeshData(rod), 3.0, "top", law=law).mesh
        tolerance = 2 * MAX_FACET_SAG
    else:
        edit = exact_kernel()
        shaped = as_mesh_data(edit.fillet(edit.cylinder(2 * RIM, TOP), 3.0, "top", law=law))
        tolerance = MAX_FACET_SAG
    assert shaped.raw.is_watertight
    loop = law.as_loop()
    for angle, share in ((180.0, 0.0), (90.0, 0.25), (0.0, 0.5), (270.0, 0.75), (135.0, 0.125)):
        assert rim_radius_at(shaped, angle) == pytest.approx(loop.at(share), abs=tolerance), angle


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_reverse_on_a_loop_runs_the_other_way_from_the_same_start(kind: str) -> None:
    """„Anfang und Ende tauschen" am Ring: derselbe Anfang, die Spitze liegt vorn."""
    from app.core.geom.mesh import as_mesh_data

    law = RadiusLaw((0.0, 0.25, 1.0), (1.0, 3.0, 1.0), reversed=True)
    if kind == "mesh":
        rod = trimesh.creation.cylinder(radius=RIM, height=TOP, sections=96)
        rod.apply_translation((0.0, 0.0, TOP / 2.0))
        shaped = round_edges(MeshData(rod), 3.0, "top", law=law).mesh
        tolerance = 2 * MAX_FACET_SAG
    else:
        edit = exact_kernel()
        shaped = as_mesh_data(edit.fillet(edit.cylinder(2 * RIM, TOP), 3.0, "top", law=law))
        tolerance = MAX_FACET_SAG
    assert rim_radius_at(shaped, 270.0) == pytest.approx(3.0, abs=tolerance)
    assert rim_radius_at(shaped, 90.0) == pytest.approx(law.as_loop().at(0.25), abs=tolerance)


def test_a_rounded_rim_carries_the_same_loop_law_on_both_kernels() -> None:
    """Die obere Kette eines Quaders mit gerundeten Ecken ist ein Ring aus acht Kanten.

    Anfang ist das vordere Ende der linken Seite; von dort läuft der Verlauf
    nach hinten. Soll am Querschnitt ist der Radius an der Bogenlänge vom
    Anfang, geteilt durch den Umfang ``2·(30 + 20) + 2πR``.
    """
    from app.core.geom.edges import edge_key
    from app.core.geom.mesh import as_mesh_data

    edit = exact_kernel()
    law = RadiusLaw((0.0, 0.5, 1.0), (1.0, 2.5, 1.0))
    perimeter = (
        2.0 * ((WIDTH - 2 * CHAIN_ROUND) + (DEPTH - 2 * CHAIN_ROUND)) + 2 * math.pi * CHAIN_ROUND
    )

    body = round_edges(block(), CHAIN_ROUND, "vertical").mesh
    ring = next(e for e in edges_of(body) if abs(e.middle[2] - HEIGHT) < 1e-6 and e.length > 100)
    meshed = round_edges(body, 2.5, "named", (edge_key(ring),), law=law).mesh
    solid = edit.fillet(edit.box(WIDTH, DEPTH, HEIGHT), CHAIN_ROUND, "vertical")
    side = next(
        e
        for e in edit.edges_of(solid)
        if abs(e.middle[2] - HEIGHT) < 1e-6 and abs(e.middle[0] + WIDTH / 2.0) < 1e-6
    )
    exact_solid = edit.fillet(solid, 2.5, "named", (edge_key(side),), law=law)
    exact = as_mesh_data(exact_solid)
    # Auf der linken Seite (x = -20), vom vorderen Ende y = -10 nach hinten.
    for y in (-7.0, 0.0, 7.0):
        share = (y + DEPTH / 2.0 - CHAIN_ROUND) / perimeter
        # Der symmetrische periodische Hermiteverlauf hat an 0 und 1/2
        # Nullsteigung: r = 1 + 1,5·(3u² - 2u³), u = 2s. Kein Sollwert
        # aus RadiusLaw oder einem Kreisfit durch die Ergebnisfacetten.
        u = 2.0 * share
        radius = 1.0 + 1.5 * (3.0 * u * u - 2.0 * u * u * u)
        centre = np.array([-WIDTH / 2.0 + radius, HEIGHT - radius])
        sections = [
            (
                kind,
                np.asarray(
                    mesh.raw.section(plane_origin=(0, y, 0), plane_normal=(0, 1, 0)).vertices
                )[:, [0, 2]],
                tolerance,
            )
            for kind, mesh, tolerance in (
                ("mesh", meshed, 2 * MAX_FACET_SAG),
                ("brep_mesh", exact, MAX_FACET_SAG),
            )
        ]
        sections.append(
            (
                "brep_curve",
                exact_section_points(exact_solid, (0.0, y, 0.0), (0.0, 1.0, 0.0))[:, [0, 2]],
                MAX_FACET_SAG,
            )
        )
        for kind, points, tolerance in sections:
            keep = (points[:, 0] < -5.0) & (points[:, 1] > 10.0)
            keep &= (np.abs(points[:, 0] + WIDTH / 2.0) > 1e-6) & (
                np.abs(points[:, 1] - HEIGHT) > 1e-6
            )
            arc = points[keep]
            assert len(arc) >= 4, (kind, y, share)
            # Die Zusage begrenzt den Abstand zum Sollkreis. Ein frei gefitteter
            # Radius kann trotz zulässiger Sehnenabweichung deutlich abweichen;
            # seine Mitte ist hier bereits durch die beiden Tangentialflächen bestimmt.
            deviation = np.abs(np.linalg.norm(arc - centre, axis=1) - radius)
            assert float(deviation.max()) <= tolerance, (kind, y, share, deviation.max())
            if kind == "brep_curve":
                # Die native Kurve trägt keine Sehnenabweichung. Hier bleibt
                # zusätzlich der Radius selbst an seiner bisherigen Grenze geprüft.
                _centre, measured_radius, _worst = fit_circle(arc)
                assert measured_radius == pytest.approx(radius, abs=MAX_FACET_SAG), (y, share)
