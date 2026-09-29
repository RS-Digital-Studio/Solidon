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
