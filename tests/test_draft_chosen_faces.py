"""P6.4 — Formschräge an gewählten Flächen, mit Entformungsrichtung und neutraler Ebene.

Konzept §13.2, Zeile P6.4: nur die gewählten Bereiche und die nötigen
Übergänge ändern, Maße an der neutralen Ebene erhalten; das bisherige Anstellen
aller senkrechten Flächen bleibt für alte Projekte reproduzierbar.

**Die Sollwerte sind Geometrie aus dem Lehrbuch, nicht aus dem Prüfling.** Eine
Wand der Höhe ``H`` und Breite ``W``, die um ``α`` um ihre Unterkante kippt,
nimmt den Keil ``W·H²·tan α / 2`` weg; ein Hohlraum, dessen Wände mit der
Höhe um ``z·tan α`` zurückweichen, wächst um das Integral seiner Querschnitte.
Die Nachbarflächen werden verlängert oder beschnitten, nie ersetzt — geprüft
daran, dass jede Ecke des Ergebnisses auf einer der alten Ebenen oder auf der
neuen liegt, und am Sechskant, an dem die Nachbarn nicht rechtwinklig stehen.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
import trimesh
from scipy import integrate

from app.core.bootstrap import load_operations
from app.core.errors import CORRECT_INPUT, AppError, OperationCancelled
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, OpResult, Scene, SceneObject
from tests.helpers import exact_kernel

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0
ANGLE = 5.0
SLOPE = math.tan(math.radians(ANGLE))
#: 4 mm Wand: Bei 5° über 20 mm Höhe weichen Außen- und Innenwand oben
#: zusammen um 2·20·tan 5° = 3,5 mm zurück — es bleibt Wand übrig.
WALL = 4.0
#: 3 mm Wand: dieselbe Schräge schneidet sie oben durch (0,5 mm fehlen).
THIN_WALL = 3.0


def block() -> MeshData:
    body = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    body.apply_translation((0.0, 0.0, HEIGHT / 2.0))
    return MeshData(body)


def hollow(wall: float = WALL) -> MeshData:
    """Ein oben offener Kasten: Wand und Boden gleich dick."""
    inner = trimesh.creation.box(extents=(WIDTH - 2 * wall, DEPTH - 2 * wall, HEIGHT))
    inner.apply_translation((0.0, 0.0, wall + HEIGHT / 2.0))
    return boolean("difference", [block(), MeshData(inner)], quality="fine").mesh


def exact_block() -> Any:
    return exact_kernel().box(WIDTH, DEPTH, HEIGHT)


def exact_hollow(wall: float = WALL) -> Any:
    edit = exact_kernel()
    inner = edit.moved(edit.box(WIDTH - 2 * wall, DEPTH - 2 * wall, HEIGHT), (0.0, 0.0, wall))
    return edit.boolean("difference", [edit.box(WIDTH, DEPTH, HEIGHT), inner])


def body_of(kind: str, shape: str = "block", wall: float = WALL) -> SceneObject:
    """Der Körper als Szenenobjekt, mit den Merkmalen, die der Kunde anklickt."""
    if kind == "mesh":
        mesh = block() if shape == "block" else hollow(wall)
        return SceneObject(id="obj_1", name="Teil", mesh=mesh, features=detect(mesh))
    from app.core.brep.features import features_of

    solid = exact_block() if shape == "block" else exact_hollow(wall)
    return SceneObject(
        id="obj_1", name="Teil", mesh=solid, kind="brep", features=features_of(solid)
    )


def faces_facing(
    entry: SceneObject, normal: tuple[float, float, float], *, inner: bool = False
) -> list[str]:
    """Die Flächenmerkmale mit dieser Normale — außen oder innen (nahe der Mitte)."""
    found = []
    for name, feature in entry.features.items():
        if feature.kind != "face":
            continue
        n = np.asarray(feature.params["normal"], dtype=float)
        if float(n @ np.asarray(normal)) < 1.0 - 1e-6:
            continue
        centre = np.asarray(feature.params["centre"], dtype=float)
        near_middle = abs(centre[0]) < WIDTH / 2.0 - 1.0 and abs(centre[1]) < DEPTH / 2.0 - 1.0
        if near_middle == inner:
            found.append(name)
    return found


def run(entry: SceneObject, *, cancelled: Any = None, **params: Any) -> OpResult:
    load_operations()
    spec = REGISTRY.get("draft_faces")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=None,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=cancelled if cancelled is not None else NeverCancelled(),
        )
    )


def corners_on_planes(mesh: MeshData, planes: list[tuple[np.ndarray, float]]) -> float:
    """Der größte Abstand einer Ecke von der nächsten der Ebenen."""
    points = np.asarray(mesh.raw.vertices, dtype=float)
    distances = np.stack([np.abs(points @ normal - offset) for normal, offset in planes], axis=1)
    return float(distances.min(axis=1).max())


def box_planes() -> list[tuple[np.ndarray, float]]:
    return [
        (np.array([1.0, 0.0, 0.0]), WIDTH / 2.0),
        (np.array([-1.0, 0.0, 0.0]), WIDTH / 2.0),
        (np.array([0.0, 1.0, 0.0]), DEPTH / 2.0),
        (np.array([0.0, -1.0, 0.0]), DEPTH / 2.0),
        (np.array([0.0, 0.0, 1.0]), HEIGHT),
        (np.array([0.0, 0.0, -1.0]), 0.0),
    ]


def tilted(normal: tuple[float, float, float], offset: float) -> tuple[np.ndarray, float]:
    vector = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(vector))
    return vector / length, offset / length


KINDS = ["mesh", "brep"]


# --- Eine Fläche, Richtung nach oben ---------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_only_the_front_face_leans_and_the_standing_face_keeps_its_size(kind: str) -> None:
    """Nur die Vorderseite, neutral unten: Keil ``W·H²·tan α/2``, Standfläche gleich."""
    entry = body_of(kind)
    front = faces_facing(entry, (0.0, -1.0, 0.0))
    assert len(front) == 1
    result = run(entry, faces=tuple(front), angle=ANGLE)
    shaped = as_mesh_data(result.outputs[0].mesh)

    assert shaped.raw.is_watertight
    assert shaped.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - WIDTH * HEIGHT**2 * SLOPE / 2.0, abs=1e-4
    )
    assert np.allclose(shaped.bounds.minimum, (-WIDTH / 2, -DEPTH / 2, 0.0), atol=1e-6)
    assert np.allclose(shaped.bounds.maximum, (WIDTH / 2, DEPTH / 2, HEIGHT), atol=1e-6)
    # Jede Ecke liegt auf einer alten Ebene oder auf der neuen: y = -15 + z*tan(a).
    planes = [*box_planes()[:2], box_planes()[2], *box_planes()[4:]]
    planes.append(tilted((0.0, -1.0, SLOPE), DEPTH / 2.0))
    assert corners_on_planes(shaped, planes) < 1e-6


@pytest.mark.parametrize("kind", KINDS)
def test_a_neutral_plane_at_the_top_adds_material_below(kind: str) -> None:
    """Neutral oben: Oben bleibt das Maß, nach unten wird das Teil breiter."""
    entry = body_of(kind)
    front = faces_facing(entry, (0.0, -1.0, 0.0))
    result = run(entry, faces=tuple(front), angle=ANGLE, neutral="neutral_end")
    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT + WIDTH * HEIGHT**2 * SLOPE / 2.0, abs=1e-4
    )
    assert shaped.bounds.minimum[1] == pytest.approx(-DEPTH / 2.0 - HEIGHT * SLOPE, abs=1e-6)


@pytest.mark.parametrize("kind", KINDS)
def test_a_neutral_plane_in_the_middle_keeps_the_volume(kind: str) -> None:
    """Neutral auf halber Höhe: oben weg, unten dazu, gleich viel."""
    entry = body_of(kind)
    front = faces_facing(entry, (0.0, -1.0, 0.0))
    result = run(
        entry, faces=tuple(front), angle=ANGLE, neutral="neutral_height", neutral_height=HEIGHT / 2
    )
    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.volume == pytest.approx(WIDTH * DEPTH * HEIGHT, abs=1e-4)
    assert shaped.bounds.minimum[1] == pytest.approx(-DEPTH / 2.0 - HEIGHT / 2 * SLOPE, abs=1e-6)
    planes = [*box_planes()[:2], box_planes()[2], *box_planes()[4:]]
    planes.append(tilted((0.0, -1.0, SLOPE), DEPTH / 2.0 + HEIGHT / 2 * SLOPE))
    assert corners_on_planes(shaped, planes) < 1e-6


@pytest.mark.parametrize("kind", KINDS)
def test_the_part_narrows_in_the_pull_direction(kind: str) -> None:
    """Entformungsrichtung nach rechts: Die Vorderseite kippt entlang X."""
    entry = body_of(kind)
    front = faces_facing(entry, (0.0, -1.0, 0.0))
    result = run(entry, faces=tuple(front), angle=ANGLE, direction="pull_right")
    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - HEIGHT * WIDTH**2 * SLOPE / 2.0, abs=1e-4
    )
    planes = [box_planes()[0], box_planes()[1], box_planes()[2], *box_planes()[4:]]
    # y = -15 + (x + 20)*tan(a)
    planes.append(tilted((-SLOPE, -1.0, 0.0), DEPTH / 2.0 + WIDTH / 2.0 * SLOPE))
    assert corners_on_planes(shaped, planes) < 1e-6


@pytest.mark.parametrize("kind", KINDS)
def test_pulling_down_keeps_the_top(kind: str) -> None:
    """Nach unten entformt, neutral am Anfang — das ist bei „nach unten“ die Oberseite."""
    entry = body_of(kind)
    front = faces_facing(entry, (0.0, -1.0, 0.0))
    result = run(entry, faces=tuple(front), angle=ANGLE, direction="pull_down")
    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - WIDTH * HEIGHT**2 * SLOPE / 2.0, abs=1e-4
    )
    planes = [*box_planes()[:2], box_planes()[2], *box_planes()[4:]]
    # y = -15 + (20 - z)*tan(a)
    planes.append(tilted((0.0, -1.0, -SLOPE), DEPTH / 2.0 - HEIGHT * SLOPE))
    assert corners_on_planes(shaped, planes) < 1e-6


# --- Nachbarn, die nicht rechtwinklig stehen ------------------------------------------


def hexagon_side() -> float:
    return 10.0


def mesh_hexagon() -> MeshData:
    rod = trimesh.creation.cylinder(radius=hexagon_side(), height=HEIGHT, sections=6)
    rod.apply_translation((0.0, 0.0, HEIGHT / 2.0))
    return MeshData(rod)


def exact_hexagon() -> Any:
    exact_kernel()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec

    from app.core.brep.kernel import Solid

    polygon = BRepBuilderAPI_MakePolygon()
    corners = trimesh.creation.cylinder(radius=hexagon_side(), height=HEIGHT, sections=6).vertices
    ring = sorted(
        {
            (round(float(x), 12), round(float(y), 12))
            for x, y, _z in corners
            if math.hypot(x, y) > 1
        },
        key=lambda point: math.atan2(point[1], point[0]),
    )
    for x, y in ring:
        polygon.Add(gp_Pnt(x, y, 0.0))
    polygon.Close()
    face = BRepBuilderAPI_MakeFace(polygon.Wire()).Face()
    return Solid(BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, HEIGHT)).Shape())


@pytest.mark.parametrize("kind", KINDS)
def test_neighbours_at_120_degrees_are_extended_not_left_as_fins(kind: str) -> None:
    """Am Sechskant rückt eine Wand ein; ihre Nachbarn wachsen in ihren eigenen Ebenen nach.

    Die Nachbarn laufen von der Wand aus nach innen auseinander, die neue Kante
    ist länger: weggenommen wird im Querschnitt das Trapez ``δ·(s + δ/√3)`` mit
    ``δ = z·tan w``, über die Höhe ``s·t·H²/2 + t²·H³/(3√3)``. Ein Keil, der
    nur über der Wand steht, ließe an beiden Enden eine Rippe stehen — genau
    ``t²·H³/(3√3)`` zu wenig (hier 11,8 mm³).
    """
    from app.core.brep.features import features_of

    side = hexagon_side()
    if kind == "mesh":
        mesh = mesh_hexagon()
        entry = SceneObject(id="obj_1", name="Sechskant", mesh=mesh, features=detect(mesh))
    else:
        solid = exact_hexagon()
        entry = SceneObject(
            id="obj_1", name="Sechskant", mesh=solid, kind="brep", features=features_of(solid)
        )
    before = as_mesh_data(entry.mesh).volume
    walls = [
        name
        for name, feature in entry.features.items()
        if feature.kind == "face" and abs(feature.params["normal"][2]) < 1e-6
    ]
    assert len(walls) == 6
    chosen = max(walls, key=lambda name: entry.features[name].params["centre"][0])
    result = run(entry, faces=(chosen,), angle=ANGLE)
    removed = before - as_mesh_data(result.outputs[0].mesh).volume
    expected = side * SLOPE * HEIGHT**2 / 2.0 + SLOPE**2 * HEIGHT**3 / (3.0 * math.sqrt(3.0))
    assert removed == pytest.approx(expected, abs=1e-4)


# --- Das Gehäuse: Innenwände gewählt --------------------------------------------------


def cavity_growth(start: float) -> float:
    """Wie viel der Hohlraum wächst, wenn seine Wände mit der Höhe um ``z·tan α`` zurückweichen."""
    inner_w, inner_d = WIDTH - 2 * WALL, DEPTH - 2 * WALL
    value, _error = integrate.quad(
        lambda z: (inner_w + 2 * z * SLOPE) * (inner_d + 2 * z * SLOPE) - inner_w * inner_d,
        start,
        HEIGHT,
    )
    return value


@pytest.mark.parametrize("kind", KINDS)
def test_a_housing_drafts_its_inner_walls_without_leaving_the_corners(kind: str) -> None:
    """Kundenweg §13.9: Gehäuse mit gewählten Entformungsflächen — die vier Innenwände.

    Der Hohlraum weitet sich nach oben; die Außenwände bleiben stehen, der
    Boden behält sein Maß. An den Innenecken bleibt keine Säule stehen: Der
    frühere Keil über jeder Wand erreichte die Ecke nicht.
    """
    entry = body_of(kind, "hollow")
    inner = [
        name
        for normal in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))
        for name in faces_facing(entry, normal, inner=True)
    ]
    assert len(inner) == 4
    before = as_mesh_data(entry.mesh).volume
    result = run(entry, faces=tuple(inner), angle=ANGLE)
    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.raw.is_watertight
    assert shaped.volume == pytest.approx(before - cavity_growth(WALL), abs=1e-3)
    assert np.allclose(shaped.bounds.minimum, (-WIDTH / 2, -DEPTH / 2, 0.0), atol=1e-6)
    assert np.allclose(shaped.bounds.maximum, (WIDTH / 2, DEPTH / 2, HEIGHT), atol=1e-6)


@pytest.mark.parametrize("kind", KINDS)
def test_every_upright_wall_of_a_housing_on_both_kernels(kind: str) -> None:
    """Der alte Weg (keine Fläche gewählt) am Gehäuse: außen schmaler, innen weiter.

    Vorher ließ das Netz an den vier Innenecken Säulen stehen: Die Keile über
    den Innenwänden erreichten die Ecke nicht (gemessen an 3 mm Wand und 2°:
    8371,29 statt 8358,33 mm³, genau ``4·t²·(20³ − 3³)/3``).
    """
    entry = body_of(kind, "hollow")
    result = run(entry, angle=ANGLE)
    shaped = as_mesh_data(result.outputs[0].mesh)
    outer, _error = integrate.quad(
        lambda z: (WIDTH - 2 * z * SLOPE) * (DEPTH - 2 * z * SLOPE), 0.0, HEIGHT
    )
    inner_w, inner_d = WIDTH - 2 * WALL, DEPTH - 2 * WALL
    cavity, _error = integrate.quad(
        lambda z: (inner_w + 2 * z * SLOPE) * (inner_d + 2 * z * SLOPE), WALL, HEIGHT
    )
    assert shaped.volume == pytest.approx(outer - cavity, abs=1e-3)


# --- Absagen, Abbruch, Register --------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_a_face_across_the_pull_direction_is_refused_with_a_way(kind: str) -> None:
    """Die Oberseite steht quer zu „nach oben" — sie lässt sich nicht anstellen."""
    entry = body_of(kind)
    top = [
        name
        for name, feature in entry.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 1.0 - 1e-6
    ]
    assert len(top) == 1
    with pytest.raises(AppError) as caught:
        run(entry, faces=tuple(top), angle=ANGLE)
    assert CORRECT_INPUT in caught.value.suggestions


def test_the_draft_can_be_stopped_between_chosen_faces() -> None:
    """Gefragt wird zwischen den Flächen, nicht nur am Eingang (§15.6)."""

    class StopsAtTheSecond:
        def __init__(self) -> None:
            self.asked = 0

        @property
        def is_cancelled(self) -> bool:
            return self.asked >= 2

        def raise_if_cancelled(self) -> None:
            self.asked += 1
            if self.asked >= 2:
                raise OperationCancelled

    entry = body_of("mesh")
    walls = [name for normal in ((1, 0, 0), (0, -1, 0)) for name in faces_facing(entry, normal)]
    token = StopsAtTheSecond()
    with pytest.raises(OperationCancelled):
        run(entry, faces=tuple(walls), angle=ANGLE, cancelled=token)
    assert token.asked == 2


def test_the_register_offers_the_draft_at_a_face_and_on_the_whole_body() -> None:
    """Merkmalfenster und Auswahlkarte finden die Formschräge an einer Fläche — und am Körper."""
    load_operations()
    spec = REGISTRY.get("draft_faces")
    assert "face" in spec.applies_to
    assert spec.also_on_body, "ohne gewählte Fläche bleibt das Anstellen aller Wände"
    names = {entry.name: entry for entry in spec.params.spec()}
    assert names["faces"].kind == "features"
    assert names["faces"].default == ()
    assert names["direction"].default == "pull_up"
    assert names["neutral"].default == "neutral_start"


@pytest.mark.parametrize("kind", KINDS)
def test_a_draft_that_cuts_through_a_wall_is_refused_on_both_kernels(kind: str) -> None:
    """3 mm Wand, 5° über 20 mm: Außen und innen weichen oben zusammen 3,5 mm zurück.

    Die Wand würde oben dünner als nichts. Der exakte Kern baute daraus einen
    Körper, den seine eigene Prüfung ablehnte (Netzvolumen seiner
    Tessellierung 12 569 statt 5 694 mm³), das Netz einen mit fehlender Wand.
    Beide sagen jetzt denselben Satz, mit Weg (Regel 17).
    """
    entry = body_of(kind, "hollow", THIN_WALL)
    with pytest.raises(AppError) as caught:
        run(entry, angle=ANGLE)
    assert CORRECT_INPUT in caught.value.suggestions
    assert "Wand" in str(caught.value.detail)


# --- Gerundete senkrechte Ecken: die Tangentenkette -----------------------------------

ROUND = 5.0


def rounded_body(kind: str) -> SceneObject:
    """Der Quader mit gerundeten senkrechten Kanten — wie ein Stapelbehälter von außen."""
    from app.core.geom.edges import round_edges

    if kind == "mesh":
        mesh = round_edges(block(), ROUND, "vertical").mesh
        return SceneObject(id="obj_1", name="Teil", mesh=mesh, features=detect(mesh))
    from app.core.brep.features import features_of

    solid = exact_kernel().fillet(exact_block(), ROUND, "vertical")
    return SceneObject(
        id="obj_1", name="Teil", mesh=solid, kind="brep", features=features_of(solid)
    )


def rounded_drafted_volume() -> float:
    """Querschnitt auf Höhe z: Rechteck mit gerundeten Ecken, alles um ``z·t`` eingerückt."""

    def area(z: float) -> float:
        inset = z * SLOPE
        radius = ROUND - inset
        return (WIDTH - 2 * inset) * (DEPTH - 2 * inset) - (4.0 - math.pi) * radius**2

    value, _error = integrate.quad(area, 0.0, HEIGHT)
    return value


@pytest.mark.parametrize("kind", KINDS)
def test_rounded_corners_are_drafted_with_their_walls(kind: str) -> None:
    """Alle Wände eines gerundeten Quaders: Die Ecken werden zu Kegelstücken.

    Vorher sagte der exakte Kern ab (OpenCASCADE stellt eine Wand neben einer
    stehenden Rundung nicht an), und das Netz schob die Ecke über den ersten
    Streifen der Rundung. Soll ist der eingerückte Querschnitt; am Netz sind
    die Rundungen Sehnenzüge, daher dort zwei Promille.
    """
    result = run(rounded_body(kind), angle=ANGLE)
    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.raw.is_watertight
    if kind == "brep":
        assert result.outputs[0].mesh.volume == pytest.approx(rounded_drafted_volume(), abs=1e-3)
    else:
        assert shaped.volume == pytest.approx(rounded_drafted_volume(), rel=2e-3)
    assert not [entry for entry in result.findings if entry.code == "draft.tangent_faces"], (
        "ohne Auswahl ist die Kette kein Befund — alle Wände sind gemeint"
    )


@pytest.mark.parametrize("kind", KINDS)
def test_one_chosen_wall_takes_its_tangent_chain_along_and_says_so(kind: str) -> None:
    """Eine gewählte Wand am gerundeten Quader: Die Kette aus Rundungen und Wänden geht mit.

    Zwischen einer angestellten Wand und einer stehenden Rundung gäbe es keine
    Kante (die Rundung schließt tangential an). Wie Fusions „Tangentenkette"
    werden die tangential anschließenden Flächen mit angestellt — hier der
    ganze Ring —, und der Befund sagt es.
    """
    entry = rounded_body(kind)
    front = faces_facing(entry, (0.0, -1.0, 0.0))
    assert len(front) == 1
    result = run(entry, faces=tuple(front), angle=ANGLE)
    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.raw.is_watertight
    told = [entry for entry in result.findings if entry.code == "draft.tangent_faces"]
    assert told and told[0].values["faces"] > 0
    if kind == "brep":
        assert result.outputs[0].mesh.volume == pytest.approx(rounded_drafted_volume(), abs=1e-3)
    else:
        assert shaped.volume == pytest.approx(rounded_drafted_volume(), rel=2e-3)


def test_the_selection_card_lists_the_draft_for_bodies_and_for_faces() -> None:
    """Die Auswahlkarte führt die Formschräge an beiden Stufen — gelesen aus dem Register."""
    from app.ui.selection_operations import body_operations, feature_operations

    load_operations()
    specs = REGISTRY.all()
    assert "draft_faces" in {spec.name for spec in body_operations(specs)}
    assert "draft_faces" in {spec.name for spec in feature_operations(specs)}


# --- Eine Rundung quer zur Entformungsrichtung: die Grenze beider Kerne ------------------


def footed_body(
    kind: str, edge: str, where: str = "bottom", wall: float | None = None
) -> SceneObject:
    """Der Quader (oder Kasten mit ``wall``) mit gerundeten oder gefasten Kanten
    unten oder oben — wie der Rand eines Trays."""
    from app.core.geom.edges import bevel_edges, round_edges

    size = 2.0 if wall is None else 1.0
    if kind == "mesh":
        work = round_edges if edge == "fillet" else bevel_edges
        mesh = work(block() if wall is None else hollow(wall), size, where).mesh
        return SceneObject(id="obj_1", name="Teil", mesh=mesh, features=detect(mesh))
    from app.core.brep.features import features_of

    edit = exact_kernel()
    work_exact = edit.fillet if edge == "fillet" else edit.chamfer
    solid = work_exact(exact_block() if wall is None else exact_hollow(wall), size, where)
    return SceneObject(
        id="obj_1", name="Teil", mesh=solid, kind="brep", features=features_of(solid)
    )


def exact_entry_as(kind: str, solid: Any) -> SceneObject:
    """Ein exakter Körper — oder sein Netzzwilling, wie ihn eine STL aus einem CAD bringt."""
    from app.core.brep.features import features_of

    if kind == "brep":
        return SceneObject(
            id="obj_1", name="Teil", mesh=solid, kind="brep", features=features_of(solid)
        )
    mesh = MeshData.of(as_mesh_data(solid).raw.copy())
    return SceneObject(id="obj_1", name="Teil", mesh=mesh, features=detect(mesh))


def refusal_of(entry: SceneObject, **params: Any) -> AppError:
    with pytest.raises(AppError) as caught:
        run(entry, **params)
    return caught.value


@pytest.mark.parametrize("where", ["bottom", "top"])
@pytest.mark.parametrize("angle", [0.5, 2.0, 5.0])
@pytest.mark.parametrize("kind", KINDS)
def test_a_wall_beside_a_round_names_the_round_on_both_kernels(
    kind: str, angle: float, where: str
) -> None:
    """RM-230: Liegt an den Wänden unten oder oben eine Rundung, gibt es keine Schräge.

    Am Tray ``build_tray_v3.step`` tragen alle Wände unten eine Rundung R 2.
    OpenCASCADE rechnet die Rundung neben der gekippten Wand nicht nach
    (``Draft_FaceRecomputation``); das Netz behielt sie bei 2° mit Knick
    (22 921 statt 22 909 mm³ über den Weg aus dem Satz) und sagte bei 0,5° und
    5° ab. Beide sagten „kleineren Winkel oder weniger Flächen“, und beides
    half nicht. Jetzt fragen beide vor der Rechnung und sagen bei jedem Winkel
    denselben Satz; sein Weg sind die Wände ohne diese Verrundung. *Merkmal
    entfernen* nimmt eine Fußrundung in einer Kette mit Eckstücken nicht weg
    (RM-230), der Satz nennt es deshalb nicht.
    """
    from app.core.geom.faces import DRAFT_BESIDE_A_ROUND

    refused = refusal_of(footed_body(kind, "fillet", where), angle=angle)

    assert refused.detail is DRAFT_BESIDE_A_ROUND
    assert [action.id for action in refused.suggestions] == ["change_selection", "cancel"]


@pytest.mark.parametrize("angle", [2.0, 5.0])
@pytest.mark.parametrize("kind", KINDS)
def test_the_rounded_corner_of_a_tray_names_the_round_on_both_kernels(
    kind: str, angle: float
) -> None:
    """Die Ecke des Trays: senkrecht R 5, am Fuß R 2 (Review RM-230, E2-3).

    Am Netzzwilling nahm die Tangentenkette den ersten, fast stehenden Streifen
    der Fußrundung als Wand mit; die Ecke sah dann keine schräge Fläche mehr,
    und es blieb der alte Ecksatz mit „kleineren Winkel“, während der exakte
    Kern die Rundung nannte. Gefragt wird jetzt am zweiten Streifen.
    """
    from app.core.geom.faces import DRAFT_BESIDE_A_ROUND

    edit = exact_kernel()
    tray = edit.fillet(edit.fillet(exact_block(), 5.0, "vertical"), 2.0, "bottom")

    refused = refusal_of(exact_entry_as(kind, tray), angle=angle)

    assert refused.detail is DRAFT_BESIDE_A_ROUND


@pytest.mark.parametrize("kind", KINDS)
def test_a_chamfer_at_the_foot_of_a_thin_wall_keeps_the_angle_advice(kind: str) -> None:
    """Eine Fase ist keine Rundung (Review RM-230, E2-2).

    Am 3-mm-Kasten mit Fase am Fuß läuft die Schräge bei 5° durch die Wand; ein
    kleinerer Winkel hilft (exakt baut 3° genau). Die erste Fassung zählte am
    Netz jedes schräge Dreieck als Rundung und strich den Rat zum Winkel.
    """
    from app.core.geom.faces import DRAFT_CUTS_THROUGH

    refused = refusal_of(footed_body(kind, "chamfer", wall=THIN_WALL), angle=ANGLE)

    assert refused.detail is DRAFT_CUTS_THROUGH
    assert CORRECT_INPUT in refused.suggestions


@pytest.mark.parametrize("angle", [10.0, 20.0])
@pytest.mark.parametrize("kind", KINDS)
def test_a_cross_bore_is_not_called_a_round(kind: str, angle: float) -> None:
    """Eine liegende Bohrung durch eine Wand ist keine Rundung (Review RM-230, E2-2).

    Ihr Mantel schließt mit Knick an die Wand an. Am exakten 3-mm-Kasten mit
    Querbohrung nannte die erste Fassung bei 10° bis 30° die Rundung, am Netz
    zählte jedes schräge Dreieck daneben; der Grund ist der Winkel, und der Rat
    dazu bleibt.
    """
    edit = exact_kernel()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.kernel import Solid
    from app.core.geom.faces import DRAFT_BESIDE_A_ROUND

    rod = Solid(
        BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(0.0, -DEPTH / 2.0 - 5.0, 10.0), gp_Dir(0.0, 1.0, 0.0)), 3.0, DEPTH + 10.0
        ).Shape()
    )
    bored = edit.boolean("difference", [exact_hollow(THIN_WALL), rod])

    refused = refusal_of(exact_entry_as(kind, bored), angle=angle)

    assert refused.detail is not DRAFT_BESIDE_A_ROUND
    assert CORRECT_INPUT in refused.suggestions


def flat_slope_at_the_foot(tilt_deg: float = 15.0) -> Any:
    """Der Quader, an der linken Wand unten eine **ebene** Schräge 15° gegen die
    Wand, 4 mm hoch — sie stößt flacher an als die Knickschwelle des Netzes."""
    exact_kernel()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec

    from app.core.brep.kernel import Solid

    rise = 4.0
    run_in = rise * math.tan(math.radians(tilt_deg))
    outline = [
        (-WIDTH / 2.0 + run_in, 0.0),
        (WIDTH / 2.0, 0.0),
        (WIDTH / 2.0, HEIGHT),
        (-WIDTH / 2.0, HEIGHT),
        (-WIDTH / 2.0, rise),
    ]
    polygon = BRepBuilderAPI_MakePolygon()
    for x, z in outline:
        polygon.Add(gp_Pnt(x, -DEPTH / 2.0, z))
    polygon.Close()
    face = BRepBuilderAPI_MakeFace(polygon.Wire()).Face()
    return Solid(BRepPrimAPI_MakePrism(face, gp_Vec(0.0, DEPTH, 0.0)).Shape())


@pytest.mark.parametrize("kind", KINDS)
def test_a_flat_slope_meeting_a_wall_shallowly_is_drafted_on_both_kernels(kind: str) -> None:
    """Gegenrichtung: Eine ebene Schräge, die mit 15° an eine Wand stößt, ist keine
    Rundung, obwohl die Kante am Netz unter der Knickschwelle von 20° liegt.

    Am Netz zählt deshalb nur eine Fläche, die sich hinter der glatten Kante
    krümmt. Beide Kerne bauen das Volumen des Querschnittsintegrals.
    """
    result = run(exact_entry_as(kind, flat_slope_at_the_foot()), angle=ANGLE)

    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.raw.is_watertight
    volume = result.outputs[0].mesh.volume if kind == "brep" else shaped.volume
    assert volume == pytest.approx(flat_slope_volume(), abs=1e-2)


def flat_slope_volume(tilt_deg: float = 15.0, rise: float = 4.0) -> float:
    """Querschnitt auf Höhe z: Die Schräge bleibt, die linke Wand kippt um ihren
    Fuß; links begrenzt, was weiter innen liegt. Die rechte Wand kippt ebenso,
    vorn und hinten beide."""
    run_in = rise * math.tan(math.radians(tilt_deg))
    meet = run_in / (SLOPE + run_in / rise)

    def area(z: float) -> float:
        wall = -WIDTH / 2.0 + z * SLOPE
        left = max(-WIDTH / 2.0 + run_in * (1.0 - z / rise), wall) if z < rise else wall
        return (WIDTH / 2.0 - z * SLOPE - left) * (DEPTH - 2.0 * z * SLOPE)

    return sum(
        integrate.quad(area, low, high)[0]
        for low, high in ((0.0, meet), (meet, rise), (rise, HEIGHT))
    )


def chamfered_foot_volume(chamfer: float = 2.0) -> float:
    """Querschnitt auf Höhe z: unten begrenzt die Fase (45°), darüber die
    angestellte Wand; sie treffen sich bei ``z = c / (1 + tan w)``."""
    meet = chamfer / (1.0 + SLOPE)

    def area(z: float) -> float:
        inset = chamfer - z if z < meet else z * SLOPE
        return (WIDTH - 2.0 * inset) * (DEPTH - 2.0 * inset)

    low, _error = integrate.quad(area, 0.0, meet)
    high, _error = integrate.quad(area, meet, HEIGHT)
    return low + high


@pytest.mark.parametrize("kind", KINDS)
def test_a_wall_on_a_chamfered_foot_is_drafted_on_both_kernels(kind: str) -> None:
    """Eine Fase am Fuß ist eben: Die gekippte Wand schneidet sie in einer neuen
    Kante, an beiden Kernen gleich (RM-230, Gegenfall zur Rundung)."""
    result = run(footed_body(kind, "chamfer"), angle=ANGLE)
    shaped = as_mesh_data(result.outputs[0].mesh)
    assert shaped.raw.is_watertight
    volume = result.outputs[0].mesh.volume if kind == "brep" else shaped.volume
    assert volume == pytest.approx(chamfered_foot_volume(), abs=1e-3)


def bullnose_wall(seam_down: bool) -> Any:
    """Eine 4 mm dicke Wand mit Vollrundung oben: eine Halbzylinderfläche über 180°,
    die Naht unten (eine Fläche) oder oben (zwei Flächen)."""
    edit = exact_kernel()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.kernel import Solid

    seam = gp_Dir(0.0, 0.0, -1.0) if seam_down else gp_Dir(0.0, 0.0, 1.0)
    frame = gp_Ax2(gp_Pnt(-WIDTH / 2.0, 0.0, 18.0), gp_Dir(1.0, 0.0, 0.0), seam)
    rod = Solid(BRepPrimAPI_MakeCylinder(frame, 2.0, WIDTH).Shape())
    wall = edit.moved(edit.box(WIDTH, 4.0, 18.0), (0.0, 0.0, 0.0))
    return edit.boolean("union", [wall, rod])


@pytest.mark.parametrize("seam_down", [True, False], ids=["naht_unten", "naht_oben"])
@pytest.mark.parametrize("kind", KINDS)
def test_a_bullnose_on_top_is_a_round_wherever_its_seam_lies(kind: str, seam_down: bool) -> None:
    """Eine Vollrundung aus einer Fläche liegt in ihrer UV-Mitte waagerecht (Review RM-230, F2).

    Der exakte Kern fragte nur dort und riet mit Naht unten wieder zum kleineren
    Winkel, das Netz nannte die Rundung. Gefragt wird jetzt an neun Punkten.
    """
    from app.core.geom.faces import DRAFT_BESIDE_A_ROUND

    refused = refusal_of(exact_entry_as(kind, bullnose_wall(seam_down)), angle=3.0)

    assert refused.detail is DRAFT_BESIDE_A_ROUND


def spline_corner_block(radius: float = 5.0) -> Any:
    """Der Quader 40 × 30 × 20 mit einer stehenden Ecke R 5 als B-Spline durch einen
    Viertelkreis — so kommen gerundete Ecken aus manchem CAD."""
    exact_kernel()
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.collections import Array1_gp_Pnt
    from OCP.GeomAPI import GeomAPI_PointsToBSpline
    from OCP.gp import gp_Pnt, gp_Vec

    from app.core.brep.kernel import Solid

    across, deep = WIDTH - radius, DEPTH - radius
    count = 9
    points = Array1_gp_Pnt(1, count)
    for index in range(count):
        turn = math.pi / 2.0 * index / (count - 1)
        points.SetValue(
            index + 1, gp_Pnt(across + radius * math.cos(turn), deep + radius * math.sin(turn), 0.0)
        )
    spline = GeomAPI_PointsToBSpline(points).Curve()
    wire = BRepBuilderAPI_MakeWire()
    wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(WIDTH, 0, 0)).Edge())
    wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(WIDTH, 0, 0), gp_Pnt(WIDTH, deep, 0.0)).Edge())
    wire.Add(BRepBuilderAPI_MakeEdge(spline).Edge())
    wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(across, DEPTH, 0.0), gp_Pnt(0, DEPTH, 0)).Edge())
    wire.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(0, DEPTH, 0), gp_Pnt(0, 0, 0)).Edge())
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    return Solid(BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, HEIGHT)).Shape())


def test_a_free_form_upright_corner_is_refused_instead_of_left_upright() -> None:
    """Eine stehende B-Spline-Ecke ließ ``BRepOffsetAPI_DraftAngle`` still senkrecht
    (Review RM-230, F3): Die gekippten Wände schnitten sich in sie ein — 22 975,12
    statt 22 942,22 mm³ mit gekippter Ecke —, ohne Befund, und genau dort klemmt
    das Teil beim Entformen. Der exakte Kern sagt jetzt vor der Rechnung ab."""
    from app.core.geom.faces import DRAFT_BESIDE_A_FREE_FACE

    refused = refusal_of(exact_entry_as("brep", spline_corner_block()), angle=2.0)

    assert refused.detail is DRAFT_BESIDE_A_FREE_FACE
    assert [action.id for action in refused.suggestions] == ["change_selection", "cancel"]


def rounded_outline(width: float, depth: float, radius: float, height: float) -> Any:
    """Ein Rechteck mit Eckradius als Draht auf der Höhe ``height`` (Radius 0: scharf)."""
    exact_kernel()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.GC import GC_MakeArcOfCircle
    from OCP.gp import gp_Pnt

    half_w, half_d = width / 2.0, depth / 2.0
    corners = (
        (half_w - radius, -half_d + radius, -90.0),
        (half_w - radius, half_d - radius, 0.0),
        (-half_w + radius, half_d - radius, 90.0),
        (-half_w + radius, -half_d + radius, 180.0),
    )

    def spot(cx: float, cy: float, degrees: float) -> Any:
        turn = math.radians(degrees)
        return gp_Pnt(cx + radius * math.cos(turn), cy + radius * math.sin(turn), height)

    wire = BRepBuilderAPI_MakeWire()
    previous = None
    for cx, cy, start in corners:
        first, middle, last = (
            spot(cx, cy, start),
            spot(cx, cy, start + 45.0),
            spot(cx, cy, start + 90.0),
        )
        if previous is not None and previous.Distance(first) > 1e-9:
            wire.Add(BRepBuilderAPI_MakeEdge(previous, first).Edge())
        if radius > 0.0:
            wire.Add(
                BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(first, middle, last).Value()).Edge()
            )
        previous = last
    opening = spot(*corners[0][:2], -90.0)
    if previous is not None and previous.Distance(opening) > 1e-9:
        wire.Add(BRepBuilderAPI_MakeEdge(previous, opening).Edge())
    return wire.Wire()


SLOPED_FOOT_TILT = 15.0
SLOPED_FOOT_RISE = 4.0


def sloped_foot_block(radius: float) -> Any:
    """Der Quader mit Eckradius, unten ringsum eine ebene Schräge 15° gegen die Wand,
    4 mm hoch — an den gerundeten Ecken wird sie zum Kegelstück."""
    edit = exact_kernel()
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections

    from app.core.brep.kernel import Solid

    run_in = SLOPED_FOOT_RISE * math.tan(math.radians(SLOPED_FOOT_TILT))
    loft = BRepOffsetAPI_ThruSections(True, True)
    loft.AddWire(rounded_outline(WIDTH - 2 * run_in, DEPTH - 2 * run_in, radius - run_in, 0.0))
    loft.AddWire(rounded_outline(WIDTH, DEPTH, radius, SLOPED_FOOT_RISE))
    loft.Build()
    upper = edit.fillet(edit.box(WIDTH, DEPTH, HEIGHT - SLOPED_FOOT_RISE), radius, "vertical")
    upper = edit.moved(upper, (0.0, 0.0, SLOPED_FOOT_RISE))
    return edit.boolean("union", [Solid(loft.Shape()), upper])


def sloped_foot_volume(radius: float, angle: float) -> float:
    """Querschnitt auf Höhe z: Einzug ist das Größere aus Schräge und gekippter Wand,
    der Eckradius schrumpft um den Einzug."""
    slope = math.tan(math.radians(angle))
    run_in = SLOPED_FOOT_RISE * math.tan(math.radians(SLOPED_FOOT_TILT))

    def area(z: float) -> float:
        wall = z * slope
        inset = max(run_in * (1.0 - z / SLOPED_FOOT_RISE), wall) if z < SLOPED_FOOT_RISE else wall
        return (WIDTH - 2 * inset) * (DEPTH - 2 * inset) - (4 - math.pi) * (radius - inset) ** 2

    meet = run_in / (slope + run_in / SLOPED_FOOT_RISE)
    spans = ((0.0, meet), (meet, SLOPED_FOOT_RISE), (SLOPED_FOOT_RISE, HEIGHT))
    return sum(integrate.quad(area, low, high, limit=200)[0] for low, high in spans)


@pytest.mark.parametrize("kind", KINDS)
def test_a_conical_foot_at_a_rounded_corner_is_no_round(kind: str) -> None:
    """Ein Kegelstück um die Entformungsrichtung krümmt sich nur um sie herum (Review
    RM-230, F4): Seine Neigung bleibt, und es ist keine Verrundung. Exakt baut die
    Schräge genau das Querschnittsintegral; am Netz nannte die erste Fassung hier
    eine Verrundung, die es nicht gibt."""
    from app.core.geom.faces import DRAFT_BESIDE_A_ROUND

    entry = exact_entry_as(kind, sloped_foot_block(5.0))
    if kind == "brep":
        result = run(entry, angle=2.0)
        assert result.outputs[0].mesh.volume == pytest.approx(
            sloped_foot_volume(5.0, 2.0), abs=1e-3
        )
        return
    try:
        run(entry, angle=2.0)
    except AppError as refused:
        assert refused.detail is not DRAFT_BESIDE_A_ROUND


def front_bottom_rounded(kind: str) -> SceneObject:
    """Der Quader mit R 2 nur an der vorderen Unterkante."""
    from app.core.geom.edges import edge_key, edges_of, round_edges

    front = (0.0, -DEPTH / 2.0, 0.0)
    if kind == "mesh":
        body = block()
        keys = [edge_key(edge) for edge in edges_of(body) if math.dist(edge.middle, front) < 1e-6]
        assert len(keys) == 1, keys
        mesh = round_edges(body, 2.0, "named", keys).mesh
        return SceneObject(id="obj_1", name="Teil", mesh=mesh, features=detect(mesh))
    edit = exact_kernel()
    solid = exact_block()
    keys = [edge_key(edge) for edge in edit.edges_of(solid) if math.dist(edge.middle, front) < 1e-6]
    assert len(keys) == 1, keys
    return exact_entry_as("brep", edit.fillet(solid, 2.0, "named", keys))


@pytest.mark.parametrize("kind", KINDS)
def test_walls_without_the_round_are_the_way_out(kind: str) -> None:
    """Der Weg, den der Satz nennt, trägt (Review RM-230, F5): Mit R 2 nur vorn unten
    stellt die Rückwand allein 2° an — Volumen aus der Formel."""
    entry = front_bottom_rounded(kind)
    back = faces_facing(entry, (0.0, 1.0, 0.0))
    assert back, "Voraussetzung: die Rückwand ist als Fläche erkannt"

    result = run(entry, angle=2.0, faces=tuple(back))

    expected = (
        WIDTH * DEPTH * HEIGHT
        - (1.0 - math.pi / 4.0) * 4.0 * WIDTH
        - WIDTH * HEIGHT**2 * math.tan(math.radians(2.0)) / 2.0
    )
    if kind == "brep":
        assert result.outputs[0].mesh.volume == pytest.approx(expected, abs=1e-3)
    else:
        assert as_mesh_data(result.outputs[0].mesh).volume == pytest.approx(expected, rel=2e-3)


def test_removing_a_foot_round_of_a_tray_says_so_instead_of_doing_nothing() -> None:
    """Am Tray meldete *Merkmal entfernen* eine Fußrundung als gebaut und gab den
    Körper unverändert zurück (Review RM-230, F1): OpenCASCADE hat sie in der Kette
    mit den Eckstücken nicht gelöscht, und gefragt wurde nur, ob es fertig ist."""
    from app.core.brep.canonical import CylinderSurface
    from app.core.errors import GeometryError

    edit = exact_kernel()
    tray = edit.fillet(edit.fillet(exact_block(), 5.0, "vertical"), 2.0, "bottom")
    foot = next(
        index
        for index in range(len(tray.faces()))
        if isinstance(surface := tray.surface(index), CylinderSurface)
        and abs(float(surface.cylinder.Radius()) - 2.0) < 1e-6
    )

    with pytest.raises(GeometryError):
        edit.unround(tray, (0.0, 0.0, 0.0), 2.0, selected_faces=[foot])

    rounded = edit.fillet(exact_block(), 2.0, "bottom")
    single = next(
        index
        for index in range(len(rounded.faces()))
        if isinstance(rounded.surface(index), CylinderSurface)
    )
    assert edit.unround(rounded, (0.0, 0.0, 0.0), 2.0, selected_faces=[single]).volume > (
        rounded.volume
    )
