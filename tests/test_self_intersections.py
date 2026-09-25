"""Die Selbstdurchdringung wird je Paar als Feld gerechnet, nicht in einer Schleife.

Die Netzfehlerkarte (§18.4) fragt `repair.self_intersecting_faces`, der
Bereichstest eines Bausteins (§24.3) `range_check.has_self_intersections`.
Bis zum 22.09.2026 waren das zwei Fassungen: die der Karte ein Feld über
Möller-Trumbore, die sich eine gemeinsame Ecke nie ansah und zwei Dreiecke in
derselben Ebene nicht fand; die des Bereichstests vollständig, aber eine
Python-Schleife über die Kontakte eines VTK-Filters. Beide rechnen jetzt in
`geom.intersections` (RM-206). Diese Datei hält die eine Rechnung gegen eine
skalare Fassung je Paar fest — dieselbe Paarlogik, die bis dahin im
Bereichstest stand — und die Fälle, die der alten Karte fehlten.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom import intersections, repair
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.units import EPS_GEOM

MESHES = Path(__file__).parent / "data" / "meshes"


def _plane_cut(triangle: np.ndarray, distance: np.ndarray) -> np.ndarray:
    numeric = 64.0 * np.finfo(float).eps * max(1.0, float(np.linalg.norm(np.ptp(triangle, axis=0))))
    points = []
    for index in range(3):
        following = (index + 1) % 3
        start, end = float(distance[index]), float(distance[following])
        if abs(start) <= numeric:
            points.append(triangle[index])
        if start * end < 0.0:
            fraction = start / (start - end)
            points.append(triangle[index] + fraction * (triangle[following] - triangle[index]))
    return np.asarray(points, dtype=float)


def _coplanar_reference(first: np.ndarray, second: np.ndarray, normal: np.ndarray) -> bool:
    keep = [axis for axis in range(3) if axis != int(np.argmax(np.abs(normal)))]
    one, other = first[:, keep], second[:, keep]
    for triangle in (one, other):
        for index in range(3):
            edge = triangle[(index + 1) % 3] - triangle[index]
            axis = np.array([-edge[1], edge[0]])
            a, b = one @ axis, other @ axis
            if min(a.max(), b.max()) - max(a.min(), b.min()) <= EPS_GEOM * np.linalg.norm(axis):
                return False
    return True


def _pair_reference(first: np.ndarray, second: np.ndarray, same_cell: bool) -> bool:
    """Die skalare Paarprüfung, wie sie bis zum 22.09.2026 im Bereichstest stand.

    Gemeinsame Punkte (Ecken innerhalb ``EPS_GEOM``) werden auf ihre Mitte
    gelegt; koplanare Paare entscheidet der Trennachsensatz, alle übrigen die
    Schnittstrecken auf der Schnittgeraden ihrer Ebenen.
    """
    first, second = first.copy(), second.copy()
    shared = []
    for a in range(3):
        for b in range(3):
            if np.linalg.norm(first[a] - second[b]) <= EPS_GEOM:
                shared.append((first[a] + second[b]) / 2.0)
                break
    for point in shared:
        first[np.linalg.norm(first - point, axis=1) <= EPS_GEOM] = point
        second[np.linalg.norm(second - point, axis=1) <= EPS_GEOM] = point
    first_normal = np.cross(first[1] - first[0], first[2] - first[0])
    second_normal = np.cross(second[1] - second[0], second[2] - second[0])
    first_length, second_length = np.linalg.norm(first_normal), np.linalg.norm(second_normal)
    first_distance = (first - second[0]) @ second_normal / second_length
    second_distance = (second - first[0]) @ first_normal / first_length
    for distance in (first_distance, second_distance):
        if np.all(distance > EPS_GEOM) or np.all(distance < -EPS_GEOM):
            return False
    coplanar = np.linalg.norm(np.cross(first_normal, second_normal)) <= (
        EPS_GEOM * first_length * second_length
    ) or (
        np.all(np.abs(first_distance) <= EPS_GEOM) and np.all(np.abs(second_distance) <= EPS_GEOM)
    )
    if coplanar:
        return not same_cell and _coplanar_reference(first, second, first_normal)
    first_cut, second_cut = _plane_cut(first, first_distance), _plane_cut(second, second_distance)
    if not len(first_cut) or not len(second_cut):
        return False
    direction = np.cross(first_normal, second_normal)
    direction /= np.linalg.norm(direction)
    low = max((first_cut @ direction).min(), (second_cut @ direction).min())
    high = min((first_cut @ direction).max(), (second_cut @ direction).max())
    if high < low - EPS_GEOM:
        return False
    if not shared:
        return True
    projection = np.asarray(shared) @ direction
    if high - low <= EPS_GEOM:
        return bool(np.all(np.abs(projection - (high + low) / 2.0) > EPS_GEOM))
    return bool(low < projection.min() - EPS_GEOM or high > projection.max() + EPS_GEOM)


def _random_pairs(count: int) -> tuple[np.ndarray, np.ndarray]:
    """Zufällige Paare, dazu geteilte Ecken, Kanten, Kopien und flache Paare."""
    source = np.random.default_rng(22092026)
    ones = source.uniform(-1.0, 1.0, size=(count, 3, 3))
    others = source.uniform(-1.0, 1.0, size=(count, 3, 3))
    others[: count // 8, 0] = ones[: count // 8, 1]
    others[count // 8 : count // 4, :2] = ones[count // 8 : count // 4, 1:]
    others[count // 4 : 3 * count // 8] = ones[count // 4 : 3 * count // 8] + 0.01
    flat = slice(3 * count // 8, count // 2)
    ones[flat, :, 2] = 0.0
    others[flat, :, 2] = 0.0
    others[count // 2 : 5 * count // 8] = ones[count // 2 : 5 * count // 8][:, [1, 2, 0]]
    return ones, others


def test_the_field_answers_like_the_scalar_pair_check_on_random_pairs() -> None:
    """Zweitausend Paare: das Feld sagt je Paar dasselbe wie die Schleife von früher."""
    ones, others = _random_pairs(2000)
    faces_one = np.tile(np.array([0, 1, 2]), (2000, 1))
    faces_other = np.tile(np.array([3, 4, 5]), (2000, 1))
    batched = intersections.crossing_pairs(ones, others, faces_one, faces_other)
    expected = np.array(
        [_pair_reference(a, b, False) for a, b in zip(ones, others, strict=True)], dtype=bool
    )

    assert batched.shape == (2000,) and batched.dtype == bool
    assert np.array_equal(batched, expected)
    assert batched.any() and not batched.all(), "beide Antworten kommen vor"


def _shared_surface(
    ones: np.ndarray, others: np.ndarray
) -> tuple[intersections._Surface, np.ndarray, np.ndarray]:
    """Die Paare als ein Netz, gleiche Koordinaten unter einer Nummer — wie ein verschweißtes."""
    corners = np.concatenate([ones, others]).reshape(-1, 3)
    vertices, faces = np.unique(corners, axis=0, return_inverse=True)
    faces = faces.reshape(-1, 3)
    surface = intersections._surface(vertices, faces)
    assert surface is not None and len(surface.kept) == len(faces), "keine Nullfläche dabei"
    count = len(ones)
    return surface, np.arange(count), np.arange(count, 2 * count)


def _touching_pairs() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Die Grenzfälle der Trennprüfung: Fächer, Falten, Berührung um EPS_GEOM, Kopien.

    Je Nabe vier Paare, und jedes zweite Dreieck steht um ``lift`` aus der
    Ebene: nichts, um weniger als ``EPS_GEOM``, um den Abstand der Prüfung
    herum oder deutlich.
    """
    source = np.random.default_rng(25092026)
    ones, others, lifts = [], [], []
    for _ in range(400):
        hub = source.uniform(-1.0, 1.0, 3)
        angles = np.sort(source.uniform(0.0, 2.0 * np.pi, 4))
        length = source.uniform(0.5, 3.0, 4)
        rim = hub + np.column_stack((length * np.cos(angles), length * np.sin(angles), np.zeros(4)))
        lift = float(source.choice([0.0, 0.0, 1e-7, 1e-6, 3e-6, 0.05]))
        up, aside = np.array([0.0, 0.0, lift]), np.array([lift, lift, 0.0])
        own = [hub, rim[0], rim[1]]
        # Dieselbe Nabe daneben im Fächer, eine Falte über die gemeinsame Kante,
        # eine Ecke um lift neben einer fremden und eine fast deckungsgleiche Kopie.
        pairs = (
            [hub, rim[2], rim[3] + up],
            [hub, rim[1], hub + 0.5 * (rim[0] - hub) + up],
            [rim[1] + aside, rim[2], rim[3]],
            [hub + aside, rim[0] + up + aside, rim[1]],
        )
        for other in pairs:
            ones.append(own)
            others.append(other)
            lifts.append(lift)
    return np.asarray(ones), np.asarray(others), np.asarray(lifts)


def _pairs_at_the_tolerance() -> tuple[np.ndarray, np.ndarray]:
    """Drei Paare, die die genaue Prüfung nur mit ihren Toleranzen kreuzen sieht.

    In der Draufsicht trennt jedes eine Kante, und jedes zeigt eine Sicherung
    der Trennprüfung. Die ersten zwei teilen eine Ecke. Das erste steht
    schräg, aber fast parallel (Sinus 2·10⁻⁶): Die
    zweite Ecke des kurzen Dreiecks liegt innerhalb der Rechengrenze in der
    Ebene des anderen, und die genaue Prüfung sieht eine Schnittstrecke über
    die gemeinsame Ecke hinaus — darum trennt die Prüfung eine gemeinsame Ecke
    nur in derselben Ebene. Im zweiten ist die gemeinsame Ecke die Spitze
    einer flachen Nadel, 1,2 ``EPS_GEOM`` unter ihrer langen Kante — darum
    darf sie nur einen halben ``EPS_GEOM`` hinter dem Rand liegen. Das dritte
    steht senkrecht einen halben ``EPS_GEOM`` neben der Kante des anderen,
    ohne gemeinsame Ecke: Eine Lücke unter ``EPS_GEOM`` ist für die genaue
    Prüfung ein Schnitt — darum der Abstand.
    """
    theta, phi, rise = 2e-6, 5e-6, 3e-6
    normal = (
        -math.sin(phi) * math.sin(theta),
        math.cos(phi) * math.sin(theta),
        math.cos(theta),
    )

    def tilted(x: float, y: float) -> list[float]:
        return [x, y, -(normal[0] * x + normal[1] * y) / normal[2]]

    corner = [0.0, 0.0, 0.0]
    tip = [0.0, -1.2e-6, 0.0]
    ones = [
        [corner, [0.001, 0.0, 0.0], [0.0005, -0.001, 0.0]],
        [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0], tip],
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]],
    ]
    others = [
        [corner, tilted(math.cos(rise), math.sin(rise)), tilted(0.0, 1.0)],
        [tip, [0.3, 0.5, 0.0], [-0.3, 0.5, 0.0]],
        [[0.5, 5e-7, -1.0], [0.5, 5e-7, 1.0], [0.5, 1.0, 0.0]],
    ]
    return np.asarray(ones), np.asarray(others)


def test_the_separation_never_drops_a_pair_that_crosses() -> None:
    """Was die Trennprüfung verwirft, schneidet nicht — an Zufall und an den Grenzfällen.

    Die Trennprüfung spart am Besenhalter 96 Prozent der genauen Prüfungen
    (RM-244). Sie darf dafür keinen Treffer kosten: nicht an einer
    gemeinsamen Ecke, nicht an einer Falte über eine gemeinsame Kante, nicht
    an einem Paar, das um Bruchteile von ``EPS_GEOM`` absteht, und nicht an
    zwei deckungsgleichen Dreiecken unter eigenen Nummern.
    """
    ones, others = _random_pairs(2000)
    fans, folds, lifts = _touching_pairs()
    tolerant, tolerated = _pairs_at_the_tolerance()
    answers = {}
    for name, first_corners, second_corners in (
        ("zufällig", ones, others),
        ("an der Toleranz", tolerant, tolerated),
        ("Fächer", fans, folds),
    ):
        surface, first, second = _shared_surface(first_corners, second_corners)
        separated, _searched = intersections._separated(surface, first, second)
        crossed = intersections.crossing_pairs(
            surface.triangles[first],
            surface.triangles[second],
            surface.faces[first],
            surface.faces[second],
        )
        assert isinstance(crossed, np.ndarray)
        assert not np.any(separated & crossed), (name, np.flatnonzero(separated & crossed)[:10])
        answers[name] = separated, crossed
    separated, crossed = answers["an der Toleranz"]
    assert crossed.all(), "die genaue Prüfung sieht alle drei gekreuzt"
    for name in ("zufällig", "Fächer"):
        separated, crossed = answers[name]
        assert separated.any() and crossed.any(), f"{name}: beide Antworten kommen vor"
    # Zwei Nadeln eines ebenen Fächers berühren sich nur an der Nabe: getrennt.
    separated, crossed = answers["Fächer"]
    beside = np.zeros(len(fans), dtype=bool)
    beside[::4] = True
    flat_fan = beside & (lifts == 0.0) & ~crossed
    assert flat_fan.sum() > 50, "der Fächer kommt vor"
    assert separated[flat_fan].all(), np.flatnonzero(flat_fan & ~separated)[:10]


def test_a_fan_of_needles_is_searched_to_the_end() -> None:
    """Ein Zylinder mit Fächerdeckeln: alle Nadeln eines Deckels treffen sich in der Mitte.

    Das Bild des Besenhalters (RM-244): Jede Nadel überdeckt mit ihrem
    Hüllquader fast jede andere desselben Deckels, und die genaue Prüfung
    zählte bis zum Budget. Die Trennprüfung trennt sie an ihrer gemeinsamen
    Nabe, und die Suche kommt unter demselben Budget ans Ende.
    """
    mesh = trimesh.creation.cylinder(radius=10.0, height=5.0, sections=512)
    surface = intersections._surface(mesh.vertices, mesh.faces)
    assert surface is not None
    candidates = sum(
        len(first)
        for first, _second in intersections._candidates(surface, None, intersections._Search())
    )
    # Der alte Weg zählte jeden Kandidaten ganz; drei Viertel reichten ihm nicht.
    budget = 3 * candidates // 4

    found = intersections.crossing_face_pairs(mesh.vertices, mesh.faces, max_pairs=budget)
    assert found.complete and not len(found.first), f"{candidates} Kandidaten, Budget {budget}"


def test_two_congruent_triangles_in_one_plane_are_found() -> None:
    """Der Fall, den die Karte mit Möller-Trumbore übersah: keine Kante durchstößt etwas."""
    triangle = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
    vertices = np.vstack([triangle, triangle[[1, 2, 0]]])
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    mesh = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))

    assert intersections.intersects(vertices, faces)
    assert repair.self_intersecting_faces(mesh) == (0, 1)
    # Dieselben Eckennummern sind eine doppelte Zelle, kein zweiter Körper.
    assert not intersections.intersects(vertices, np.array([[0, 1, 2], [1, 2, 0]]))


def test_a_shared_corner_does_not_excuse_a_crossing() -> None:
    """Ein gemeinsamer Eckpunkt entschuldigt keine weitere Schnittstrecke, auch in der Karte."""
    vertices = np.array(
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (1.0, 1.0, -1.0), (1.0, 1.0, 1.0)]
    )
    faces = np.array([[0, 1, 2], [0, 3, 4]])
    mesh = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))

    assert repair.self_intersecting_faces(mesh) == (0, 1)


def test_the_two_blocks_report_every_triangle_their_crossing_touches() -> None:
    """Die zwei durcheinanderlaufenden Quader: zwölf Dreiecke, an einem sauberen Netz keines.

    Möller-Trumbore fand acht — nur die, deren Inneres eine Kante des anderen
    Quaders durchstößt. Vier weitere trifft die Schnittlinie beider Hüllen auf
    ihrem Rand: Die Oberseite des einen Quaders berührt die Diagonale einer
    Seitenfläche des anderen genau dort, wo beide Flächen einander kreuzen.
    Das ist dieselbe Durchdringung, und der Bereichstest hat sie immer so
    gezählt.
    """
    mesh = normalise(read_mesh((MESHES / "broken_selfint.stl").read_bytes(), ".stl"), "mm").mesh
    found = repair.self_intersecting_faces(mesh)
    moeller = {6, 9, 10, 11, 13, 15, 17, 20}

    assert len(found) == 12
    assert moeller <= set(found)
    assert repair.self_intersecting_faces(MeshData.of(trimesh.creation.box())) == ()


def _overlapping_pairs(low: np.ndarray, high: np.ndarray) -> set[tuple[int, int]]:
    """Alle Paare überdeckender Hüllquader, stumpf gezählt — die Vorgabe für jeden Plan."""
    apart = np.zeros((len(low), len(low)), dtype=bool)
    for axis in range(3):
        apart |= low[None, :, axis] > high[:, None, axis] + EPS_GEOM
        apart |= low[:, None, axis] > high[None, :, axis] + EPS_GEOM
    first, second = np.nonzero(np.triu(~apart, k=1))
    return set(zip(first.tolist(), second.tolist(), strict=True))


def _found(surface: object, plan: object) -> list[tuple[int, int]]:
    found = []
    for first, second in intersections._candidates(
        surface,  # type: ignore[arg-type]
        None,
        intersections._Search(),
        plan,  # type: ignore[arg-type]
    ):
        low, high = np.minimum(first, second), np.maximum(first, second)
        found.extend(zip(low.tolist(), high.tolist(), strict=True))
    return found


def test_every_plan_finds_exactly_the_overlapping_boxes_once() -> None:
    """Sweep oder Scheiben, jede Achse, jede Breite: dieselben Paare, keines doppelt.

    Die Scheiben zählen ein Paar nur in der Scheibe der unteren Ecke seiner
    gemeinsamen Hülle. Ein Fehler in dieser Regel verlöre Paare an der
    Scheibengrenze oder zählte sie zweimal — geprüft an einer Kugel, einer
    Kette entlang Y und zwei Quadern, deren Flächen genau auf einer Grenze liegen.
    """
    sphere = trimesh.creation.icosphere(subdivisions=3)
    links = []
    for index in range(20):
        link = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        link.apply_translation((0.0, 2.0 * index, 0.0))
        links.append(link)
    chain = trimesh.util.concatenate(links)
    left = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    right = left.copy()
    right.apply_translation((1.0, 0.0, 0.0))
    touching = trimesh.util.concatenate([left, right])
    for mesh in (sphere, chain, touching):
        surface = intersections._surface(mesh.vertices, mesh.faces)
        assert surface is not None
        expected = _overlapping_pairs(surface.low, surface.high)
        plans = [intersections._Plan(axis) for axis in range(3)]
        for axis in range(3):
            for bins in range(3):
                if bins != axis:
                    plans.extend(
                        intersections._Plan(axis, bins, width) for width in (0.05, 0.5, 1.0, 7.0)
                    )
        for plan in plans:
            found = _found(surface, plan)
            assert len(found) == len(set(found)), f"{plan}: doppelt"
            assert set(found) == expected, f"{plan}: {len(set(found))} statt {len(expected)}"


def test_a_long_helix_is_searched_in_slabs() -> None:
    """Ein langes Gewinde überdeckt sich quer zur Achse Umlauf um Umlauf.

    Der einfache Sweep zählte an M2 × 200 entlang der Gewindeachse 42 Millionen
    Paare für 2,2 Millionen Kandidaten, an einem Baum aus 166 000 Dreiecken
    146 Millionen für 1,3 Millionen. In Scheiben geteilt sind es 11 bzw.
    8 Millionen, und die Suche am Baum dauert 5 s statt 16 s. Der Plan muss
    diese Teilung von selbst wählen.
    """
    turns = np.linspace(0.0, 40.0 * np.pi, 4000)
    path = np.column_stack((np.cos(turns), np.sin(turns), 0.05 * turns))
    tube = trimesh.creation.sweep_polygon(
        trimesh.path.polygons.Polygon([(0.0, 0.0), (0.2, 0.0), (0.1, 0.15)]), path
    )
    surface = intersections._surface(tube.vertices, tube.faces)
    assert surface is not None
    plan = intersections._plan(surface.low, surface.high)
    assert plan.bins is not None, plan


def test_the_map_budget_says_when_it_stopped() -> None:
    """Das Paarbudget gibt es nur für die Karte, und sie erfährt, dass es griff."""
    sphere = trimesh.creation.icosphere(subdivisions=3)

    found, complete = intersections.crossing_faces(sphere.vertices, sphere.faces, max_pairs=10)
    assert found == () and not complete
    found, complete = intersections.crossing_faces(sphere.vertices, sphere.faces)
    assert found == () and complete


def test_a_cancelled_search_raises_the_cancellation() -> None:
    """Ein Abbruch wird zu ``OperationCancelled`` — die Aufrufer übersetzen ihn selbst."""

    class Cancelled:
        is_cancelled = True

        def raise_if_cancelled(self) -> None:
            raise OperationCancelled

    sphere = trimesh.creation.icosphere(subdivisions=2)
    with pytest.raises(OperationCancelled):
        intersections.intersects(sphere.vertices, sphere.faces, Cancelled())
    with pytest.raises(OperationCancelled):
        repair.self_intersecting_faces(MeshData.of(sphere), Cancelled())
