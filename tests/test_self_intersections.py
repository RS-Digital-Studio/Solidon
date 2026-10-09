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


@pytest.mark.parametrize("offset", [0.0, 1e7], ids=["ursprung", "weit-verschoben"])
def test_a_shallow_crossing_survives_translation_at_representable_precision(
    offset: float,
) -> None:
    """Ein flacher Schnitt bleibt trotz Koordinatenverschiebung sichtbar."""
    first, second = _pairs_at_the_tolerance()
    shift = np.array([offset, -offset, offset])
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    vertices = np.concatenate((first[0] + shift, second[0] + shift))
    surface = intersections._surface(vertices, faces)
    assert surface is not None
    one, other = np.array([0]), np.array([1])
    separated, _ = intersections._separated(surface, one, other)
    crossing = intersections.crossing_pairs(
        surface.triangles[one],
        surface.triangles[other],
        surface.faces[one],
        surface.faces[other],
    )

    assert crossing.tolist() == [True]
    assert separated.tolist() == [False]


@pytest.mark.parametrize("angle", [0, 17, 41, 73])
@pytest.mark.parametrize("offset", [0.0, 1000.0, 1e7])
def test_a_shared_split_edge_survives_rotation_and_translation(angle: int, offset: float) -> None:
    """Eine gemeinsam unterteilte Kante bleibt nach starrer Bewegung Berührung."""
    first = np.array([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)])
    second = np.array([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 2.0)])
    rotation = trimesh.transformations.rotation_matrix(math.radians(angle), (1.0, 2.0, 3.0))[:3, :3]
    shift = np.array([offset, -offset, offset])
    first = first @ rotation.T + shift
    second = second @ rotation.T + shift
    faces = np.array([[0, 1, 2], [3, 4, 5]])

    for one, other, one_faces, other_faces in (
        (first[None, ...], second[None, ...], faces[:1], faces[1:]),
        (second[None, ...], first[None, ...], faces[1:], faces[:1]),
    ):
        crossing = intersections.crossing_pairs(one, other, one_faces, other_faces)
        assert crossing.tolist() == [False]


@pytest.mark.parametrize("reverse", [False, True], ids=["vorwaerts", "vertauscht"])
def test_a_short_split_edge_survives_large_translation(reverse: bool) -> None:
    """Eine kurze Teilkante bleibt auch bei großer Weltlage als Kontakt erkennbar."""
    first = np.array([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)])
    second = np.array([(0.0, 0.0, 0.0), (0.03, 0.0, 0.0), (0.0, 0.0, 2.0)])
    rotation = trimesh.transformations.rotation_matrix(math.radians(17), (1.0, 2.0, 3.0))[:3, :3]
    shift = np.array([1e7, -1e7, 1e7])
    first = first @ rotation.T + shift
    second = second @ rotation.T + shift
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    if reverse:
        first, second = second, first
        faces = faces[::-1]

    crossing = intersections.crossing_pairs(
        first[None, ...], second[None, ...], faces[:1], faces[1:]
    )

    assert crossing.tolist() == [False]


@pytest.mark.parametrize("reverse", [False, True], ids=["vorwaerts", "vertauscht"])
def test_a_diagonal_split_edge_survives_axis_rounding(reverse: bool) -> None:
    """Rundung auf der großen x-Koordinate zählt nach der Projektion auch in y."""
    first = np.array([(0.0, 0.0, 0.0), (2.0, 2.0, 0.0), (-2.0, 2.0, 0.0)])
    second = np.array([(0.0, 0.0, 0.0), (0.03, 0.03, 0.0), (0.0, 0.0, 2.0)])
    shift = np.array([1e7, 0.0, 0.0])
    first += shift
    second += shift
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    if reverse:
        first, second = second, first
        faces = faces[::-1]

    crossing = intersections.crossing_pairs(
        first[None, ...], second[None, ...], faces[:1], faces[1:]
    )

    assert crossing.tolist() == [False]


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


def test_an_empty_interval_without_a_shared_corner_avoids_infinite_subtraction() -> None:
    """Ein leerer Ebenenschnitt im Toleranzrand darf keine ``inf - inf``-Warnung bilden."""
    first = np.array([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)])
    offset = EPS_GEOM
    second = np.array([(-offset, 0.0, -1.0), (-offset, 1.0, -1.0), (-offset, 0.0, 1.0)])
    faces = np.array([[0, 1, 2], [3, 4, 5]])

    with np.errstate(invalid="raise"):
        crossing = intersections.crossing_pairs(
            first[None, ...], second[None, ...], faces[:1], faces[1:]
        )

    assert crossing.tolist() == [False]


def test_a_shared_seal_corner_is_not_a_crossing_in_either_order() -> None:
    """Der Rundungsspalt an der gemeinsamen Ecke einer Dichtung bleibt Berührung (RM-253)."""
    first = np.array(
        [
            (-18.870467011105653, 2.781334266010068, -5.103946401036175),
            (-18.890537819624416, 2.793251832855135, -4.942537485237902),
            (-18.979628571612047, 2.08232456242732, -4.942537485237902),
        ]
    )
    second = np.array(
        [
            (-18.645305537921594, 3.773701241787261, -5.469249075111665),
            (-18.89479814146909, 2.776519282303077, -4.933001532405608),
            (-18.890537819624416, 2.793251832855135, -4.942537485237902),
        ]
    )
    vertices = np.concatenate((first, second))
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    mesh = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))

    for one, other, one_faces, other_faces in (
        (first[None, ...], second[None, ...], faces[:1], faces[1:]),
        (second[None, ...], first[None, ...], faces[1:], faces[:1]),
    ):
        assert intersections.crossing_pairs(one, other, one_faces, other_faces).tolist() == [False]

    assert not intersections.intersects(vertices, faces)
    assert repair.self_intersecting_faces(mesh) == ()


def test_a_shared_way3_edge_is_not_a_crossing_in_either_order() -> None:
    """Zwei Flächen am Weg-3-Beispiel teilen nur eine Kante (RM-319)."""
    first = np.array(
        [
            (16.099135451238062, -16.49400907830801, 5.901074220107633),
            (17.81101445226286, -13.595227806940587, 5.395225543643059),
            (17.599560675816612, -13.488778107452099, 5.867010584911972),
        ]
    )
    second = np.array(
        [
            (16.099135451238062, -16.49400907830801, 5.901074220107633),
            (17.599560675816612, -13.488778107452099, 5.867010584911972),
            (16.855078504523135, -12.905306552904513, 7.711928833866507),
        ]
    )
    vertices = np.concatenate((first, second))
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    mesh = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))

    for one, other, one_faces, other_faces in (
        (first[None, ...], second[None, ...], faces[:1], faces[1:]),
        (second[None, ...], first[None, ...], faces[1:], faces[:1]),
    ):
        assert intersections.crossing_pairs(one, other, one_faces, other_faces).tolist() == [False]

    assert not intersections.intersects(vertices, faces)
    assert repair.self_intersecting_faces(mesh) == ()


def test_a_tolerance_gap_has_the_same_answer_in_either_order() -> None:
    """Ein Spalt über dem Rechenrauschen bleibt innerhalb EPS_GEOM reihenfolgestabil (RM-319)."""
    x = 2**23
    gap = 2**-28
    first = np.array([(x - 1, 0, 0), (x, 1, 0), (x, -1, 0)], dtype=np.float64)
    second = np.array([(x + gap, 0, 0), (x + 1, 0, 1), (x + 1, 0, -1)], dtype=np.float64)
    faces = np.array([[0, 1, 2], [3, 4, 5]])

    for one, other, one_faces, other_faces in (
        (first[None, ...], second[None, ...], faces[:1], faces[1:]),
        (second[None, ...], first[None, ...], faces[1:], faces[:1]),
    ):
        assert intersections.crossing_pairs(one, other, one_faces, other_faces).tolist() == [True]


def test_vertices_inside_the_partner_triangles_do_not_hide_a_crossing() -> None:
    """Innere Punkte einer echten Schnittstrecke sind keine gemeinsamen Randpunkte (RM-319)."""
    first = np.array([(-1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (1.0, -1.0, 0.0)])
    second = np.array([(0.0, 0.0, 0.0), (-2.0, 0.0, 1.0), (-2.0, 0.0, -1.0)])
    vertices = np.concatenate((first, second))
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    mesh = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))

    for one, other, one_faces, other_faces in (
        (first[None, ...], second[None, ...], faces[:1], faces[1:]),
        (second[None, ...], first[None, ...], faces[1:], faces[:1]),
    ):
        crossing = intersections.crossing_pairs(one, other, one_faces, other_faces)
        assert crossing.tolist() == [True]

    assert intersections.intersects(vertices, faces)
    assert repair.self_intersecting_faces(mesh) == (0, 1)


def test_boundary_endpoints_do_not_hide_an_interior_crossing() -> None:
    """Zwei Randpunkte machen eine innere Schnittstrecke nicht zum Kantenkontakt (RM-319)."""
    first = np.array([(-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)])
    second = np.array([(0.0, 0.0, 0.0), (-1.0, 0.0, 1.0), (-1.0, 0.0, -1.0)])
    vertices = np.concatenate((first, second))
    faces = np.array([[0, 1, 2], [3, 4, 5]])
    mesh = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))

    for one, other, one_faces, other_faces in (
        (first[None, ...], second[None, ...], faces[:1], faces[1:]),
        (second[None, ...], first[None, ...], faces[1:], faces[:1]),
    ):
        crossing = intersections.crossing_pairs(one, other, one_faces, other_faces)
        assert crossing.tolist() == [True]

    assert intersections.intersects(vertices, faces)
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


def _sweep_before(
    surface: intersections._Surface,
    plan: intersections._Plan,
    search: intersections._Search,
    *,
    separate: bool,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Die Kandidatensuche, wie sie bis zum 09.10.2026 ihre Paare bildete (RM-568).

    Je Paar über die Dreiecksnummern aus den Hüllquadern gelesen, die Heimat
    der gemeinsamen Hülle je Paar gerechnet — die Vorgabe für die Suche, die
    dieselben Paare über die Plätze ihrer Einträge bildet.
    """
    low, high = surface.low, surface.high
    entries = intersections._entries(low, high, plan) or intersections._entries(
        low, high, intersections._Plan(plan.axis)
    )
    assert entries is not None
    others = [dimension for dimension in range(3) if dimension != plan.axis]
    counts = entries.counts
    total = np.cumsum(counts)
    positions = np.arange(len(counts))
    counted = 0.0
    begin = 0
    found: list[tuple[np.ndarray, np.ndarray]] = []
    while begin < len(counts):
        before = int(total[begin - 1]) if begin else 0
        end = int(np.searchsorted(total, before + intersections.SWEEP_PAIRS, side="right"))
        end = min(max(end, begin + 1), len(counts))
        block, size = positions[begin:end], counts[begin:end]
        begin = end
        amount = int(size.sum())
        if not amount:
            continue
        left = np.repeat(block, size)
        right = left + 1 + np.arange(amount) - np.repeat(np.cumsum(size) - size, size)
        first, second = entries.triangle[left], entries.triangle[right]
        apart = np.zeros(len(first), dtype=bool)
        for dimension in others:
            apart |= low[second, dimension] > high[first, dimension] + EPS_GEOM
            apart |= low[first, dimension] > high[second, dimension] + EPS_GEOM
        if plan.bins is not None:
            corner = np.maximum(low[first, plan.bins], low[second, plan.bins])
            home = np.floor((corner - entries.origin) / plan.width).astype(np.int64)
            apart |= home != entries.slab[left]
        first, second, left = first[~apart], second[~apart], left[~apart]
        open_pairs = np.ones(len(first), dtype=bool)
        cost = np.ones(len(first))
        if separate:
            separated, charge = intersections._separated(surface, first, second)
            open_pairs = ~separated
            cost = charge + open_pairs
        spent = float(cost.sum())
        if search.max_pairs is not None and counted + spent > search.max_pairs:
            search.complete = False
            allowed = max(search.max_pairs - counted, 0.0)
            fitting = int(np.searchsorted(np.cumsum(cost), allowed, side="right"))
            cut = int(left[fitting]) if fitting < len(left) else end
            keep = (left < cut) & open_pairs
            search.unchecked = np.unique(entries.triangle[cut:])
            found.append((first[keep], second[keep]))
            return found
        counted += spent
        found.append((first[open_pairs], second[open_pairs]))
    return found


def _plan_before(low: np.ndarray, high: np.ndarray) -> intersections._Plan:
    """Die Planwahl mit geordneten Einträgen, wie bis zum 09.10.2026 (RM-568)."""
    stride = max(1, len(low) // intersections.PLAN_SAMPLE)
    sample_low, sample_high = low[::stride], high[::stride]
    plans = [intersections._Plan(axis) for axis in range(3)]
    for axis in range(3):
        for bins in range(3):
            middle = float(np.median(sample_high[:, bins] - sample_low[:, bins]))
            if bins != axis and middle > EPS_GEOM:
                plans.extend(
                    intersections._Plan(axis, bins, middle * factor)
                    for factor in intersections.SLAB_FACTORS
                )
    best: tuple[float, intersections._Plan] | None = None
    for plan in plans:
        entries = intersections._entries(sample_low, sample_high, plan)
        if entries is None:
            continue
        work = float(entries.counts.sum()) * stride * stride + (
            intersections.ENTRY_WEIGHT * len(entries.triangle) * stride
        )
        if best is None or work < best[0]:
            best = (work, plan)
    return best[1] if best is not None else intersections._Plan(0)


def _sweep_meshes() -> list[tuple[np.ndarray, np.ndarray]]:
    """Kugel, Kette, bündige Quader, Wendel, zwei Kugeln im Schnitt und lange Splitter."""
    sphere = trimesh.creation.icosphere(subdivisions=3)
    chain = trimesh.util.concatenate(
        [
            trimesh.creation.box(extents=(1.0, 1.0, 1.0)).apply_translation((0.0, 2.0 * k, 0.0))
            for k in range(20)
        ]
    )
    left = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    touching = trimesh.util.concatenate([left, left.copy().apply_translation((1.0, 0.0, 0.0))])
    turns = np.linspace(0.0, 12.0 * np.pi, 1200)
    path = np.column_stack((np.cos(turns), np.sin(turns), 0.05 * turns))
    helix = trimesh.creation.sweep_polygon(
        trimesh.path.polygons.Polygon([(0.0, 0.0), (0.2, 0.0), (0.1, 0.15)]), path
    )
    # Lange Splitter quer durch viele Scheiben, dazu kurze, fern vom Ursprung.
    source = np.random.default_rng(9102026)
    corners = source.uniform(-5.0, 5.0, size=(600, 3))
    reach = source.uniform(-0.3, 0.3, size=(600, 2, 3))
    reach[:200, 0, 2] = source.uniform(-8.0, 8.0, size=200)
    soup = np.concatenate((corners[:, None, :], corners[:, None, :] + reach), axis=1) + 1.0e4
    meshes = [
        (np.asarray(mesh.vertices), np.asarray(mesh.faces))
        for mesh in (sphere, chain, touching, helix)
    ]
    meshes.append(_crossed_spheres())
    meshes.append((soup.reshape(-1, 3), np.arange(len(soup) * 3).reshape(-1, 3)))
    return meshes


def test_the_sweep_gives_the_pairs_of_the_old_sweep_in_the_same_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dieselben Paare in derselben Folge, dasselbe Budgetende, dieselben geprüften Dreiecke.

    Die Suche bildet ihre Paare seit RM-568 über die Plätze der Einträge, liest
    die Hüllquader dafür in deren Folge und die Heimatscheibe als das Größere
    der Heimaten beider Dreiecke. Die Vorgabe ist die Suche davor
    (:func:`_sweep_before`), für jeden Plan jeder Achse und Breite, mit und
    ohne Trennprüfung und mit Budgets, die mitten in einem Block enden — auch
    über mehrere Blöcke (``SWEEP_PAIRS`` klein).
    """
    monkeypatch.setattr(intersections, "SWEEP_PAIRS", 2_000)
    for vertices, faces in _sweep_meshes():
        surface = intersections._surface(vertices, faces)
        assert surface is not None
        plans = [intersections._Plan(axis) for axis in range(3)]
        for axis in range(3):
            for bins in range(3):
                if bins != axis:
                    plans.extend(
                        intersections._Plan(axis, bins, width) for width in (0.05, 0.5, 1.0, 7.0)
                    )
        for plan in plans:
            for separate in (False, True):
                for budget in (None, 500, 5_000):
                    before = intersections._Search(max_pairs=budget)
                    expected = _sweep_before(surface, plan, before, separate=separate)
                    now = intersections._Search(max_pairs=budget)
                    blocks = list(
                        intersections._candidates(surface, None, now, plan, separate=separate)
                    )
                    for index in (0, 1):
                        np.testing.assert_array_equal(
                            np.concatenate([b[index] for b in blocks] or [np.zeros(0, int)]),
                            np.concatenate([e[index] for e in expected] or [np.zeros(0, int)]),
                            err_msg=f"{plan}, separate={separate}, budget={budget}",
                        )
                    assert now.complete == before.complete, plan
                    if before.unchecked is None:
                        assert now.unchecked is None, plan
                    else:
                        assert now.unchecked is not None, plan
                        np.testing.assert_array_equal(now.unchecked, before.unchecked)


def test_the_plan_is_chosen_as_with_ordered_entries() -> None:
    """Die Planwahl zählt die Sweep-Paare ohne die Einträge zu ordnen — und wählt gleich.

    Gezählt wird über die Plätze der Enden in den geordneten Anfängen
    (:func:`intersections._pair_count`); die Vorgabe ist die Summe der
    ``counts`` geordneter Einträge, für jeden Plan, an Netzen über und unter der
    Stichprobengrenze.
    """
    for vertices, faces in _sweep_meshes():
        surface = intersections._surface(vertices, faces)
        assert surface is not None
        assert intersections._plan(surface.low, surface.high) == _plan_before(
            surface.low, surface.high
        )
        for axis in range(3):
            for plan in (
                intersections._Plan(axis),
                *(intersections._Plan(axis, (axis + 1) % 3, w) for w in (0.01, 0.3, 4.0)),
            ):
                entries = intersections._entries(surface.low, surface.high, plan)
                counted = intersections._pair_count(surface.low, surface.high, plan)
                if entries is None:
                    assert counted is None
                else:
                    assert counted == (int(entries.counts.sum()), len(entries.triangle))
    big = trimesh.creation.icosphere(subdivisions=6)
    big.apply_translation((3.0e3, -2.0e3, 1.0e3))
    surface = intersections._surface(np.asarray(big.vertices), np.asarray(big.faces))
    assert surface is not None and len(surface.low) > intersections.PLAN_SAMPLE
    assert intersections._plan(surface.low, surface.high) == _plan_before(surface.low, surface.high)


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


# --- nur um aktive Dreiecke (RM-419) -------------------------------------------


def _pairs_with(found: intersections.Crossings, active: np.ndarray) -> set[tuple[int, int]]:
    """Die Paare einer Suche, an denen ein aktives Dreieck beteiligt ist."""
    return {
        (min(int(a), int(b)), max(int(a), int(b)))
        for a, b in zip(found.first, found.second, strict=True)
        if active[a] or active[b]
    }


def _overlapping_balls() -> tuple[np.ndarray, np.ndarray]:
    """Zwei Kugeln, die sich durchdringen, als ein Netz — Hunderte Schnittpaare."""
    one = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
    other = trimesh.creation.icosphere(subdivisions=3, radius=9.0)
    other.apply_translation((6.0, 1.0, 0.5))
    both = trimesh.util.concatenate([one, other])
    return np.asarray(both.vertices, dtype=float), np.asarray(both.faces, dtype=np.int64)


def _folded_ball() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Eine Kugel, deren Kappe über ihre Mitte hinaus gekniffen ist — Falten
    zwischen Nachbarn, dazu das Gedächtnis, welche Ecken sich bewegt haben."""
    from app.core.geom.sculpt import apply_strokes
    from app.core.types import Stroke

    base = MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0))
    pinch = Stroke(
        point=(0.0, 0.0, 20.0), normal=(0.0, 0.0, 1.0), radius=8.0, strength=3.5, tool="pinch"
    )
    shaped = apply_strokes(base, [pinch], front_only=False)
    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(shaped.raw.vertices, dtype=float)
    moved = np.linalg.norm(after - before, axis=1) > 1e-9
    faces = np.asarray(shaped.raw.faces, dtype=np.int64)
    return after, faces, moved[faces].any(axis=1)


def test_the_search_around_active_triangles_finds_exactly_their_pairs() -> None:
    """``crossings_at`` sucht nur um die aktiven Dreiecke und trennt Nachbarn
    vorab (RM-419). Es findet genau die Paare der vollständigen Suche, an
    denen ein aktives Dreieck beteiligt ist — an zwei Kugeln, die sich
    durchdringen, mit zufällig gewählten aktiven Dreiecken, und an einer
    Kappe, deren Kniff Nachbarn übereinanderfaltet."""
    vertices, faces = _overlapping_balls()
    everything = intersections.crossing_face_pairs(vertices, faces)
    assert len(everything.first) > 100, "Voraussetzung: viele Schnittpaare"
    source = np.random.default_rng(2101)
    for share in (0.05, 0.4, 1.0):
        active = source.random(len(faces)) < share
        found = intersections.crossings_at(vertices, faces, active)
        assert _pairs_with(found, active) == _pairs_with(everything, active), share
        assert len(found.first) == len(_pairs_with(found, active)), "jedes Paar einmal"

    folded, faces, active = _folded_ball()
    everything = intersections.crossing_face_pairs(folded, faces)
    found = intersections.crossings_at(folded, faces, active)
    assert len(everything.first) > 0, "Voraussetzung: die Kappe ist gefaltet"
    assert _pairs_with(found, active) == _pairs_with(everything, active)


def _folds_at_the_tolerance() -> tuple[np.ndarray, np.ndarray]:
    """Ein Paar, das nur die Sicherung „nicht fast parallel“ an die genaue
    Prüfung hält (:func:`intersections._touching_apart`).

    Eine gemeinsame Ecke, das zweite Dreieck über das erste gefaltet und um
    einen Sinus von 8,5·10⁻⁷ gekippt: Für die genaue Prüfung liegt es in
    derselben Ebene und überdeckt das erste — ein Schnitt. Seine freien Ecken
    stehen aber 4,8·10⁻⁶ über der Ebene des ersten, mehr als ``margin``; ohne
    die Sicherung hieße es „liegt nur an“.
    """
    tilt = 6e-7

    def lifted(x: float, y: float) -> list[float]:
        return [x, y, tilt * (x + y)]

    ones = [[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 10.0, 0.0]]]
    others = [[[0.0, 0.0, 0.0], lifted(6.0, 2.0), lifted(2.0, 6.0)]]
    return np.asarray(ones), np.asarray(others)


def test_the_neighbour_check_never_drops_a_pair_that_crosses() -> None:
    """Was ``_touching_apart`` vor der genauen Prüfung verwirft, schneidet nicht
    — an Zufall, Fächern, Falten und den Grenzfällen (RM-419).

    Sie verwirft mehr als :func:`intersections._separated`: auch Nachbarn mit
    gemeinsamer Ecke, die schräg stehen, und Sattelpaare, deren
    Schnittstrecken von der Ecke auseinanderlaufen. Dafür darf sie keinen
    Treffer kosten.
    """
    ones, others = _random_pairs(2000)
    fans, folds, _lifts = _touching_pairs()
    tolerant, tolerated = _pairs_at_the_tolerance()
    flat_one, flat_other = _folds_at_the_tolerance()
    apart_any = False
    for name, first_corners, second_corners in (
        ("zufällig", ones, others),
        ("an der Toleranz", tolerant, tolerated),
        ("Fächer", fans, folds),
        ("fast parallel gefaltet", flat_one, flat_other),
    ):
        surface, first, second = _shared_surface(first_corners, second_corners)
        apart = intersections._touching_apart(surface, first, second)
        crossed = intersections.crossing_pairs(
            surface.triangles[first],
            surface.triangles[second],
            surface.faces[first],
            surface.faces[second],
        )
        assert isinstance(crossed, np.ndarray)
        assert not np.any(apart & crossed), (name, np.flatnonzero(apart & crossed)[:10])
        apart_any |= bool(apart.any())
        if name == "fast parallel gefaltet":
            assert crossed.all(), "Voraussetzung: die genaue Prüfung sieht die Falte"
    assert apart_any, "sie verwirft überhaupt etwas"


def test_the_search_around_active_triangles_can_be_stopped_and_reports_progress() -> None:
    """Abbrechen wirkt in der Suche, und der Fortschritt endet bei eins."""

    class Cancelled:
        is_cancelled = True

        def raise_if_cancelled(self) -> None:
            raise OperationCancelled

    vertices, faces = _overlapping_balls()
    active = np.ones(len(faces), dtype=bool)
    with pytest.raises(OperationCancelled):
        intersections.crossings_at(vertices, faces, active, Cancelled())
    shares: list[float] = []
    intersections.crossings_at(vertices, faces, active, progress=shares.append)
    assert shares and shares[-1] == 1.0 and all(0.0 <= share <= 1.0 for share in shares)


def test_a_shared_edge_needs_no_collinearity_recheck(monkeypatch) -> None:
    """Zwei nicht koplanare Nachbarn tragen ihre gemeinsame Kante schon exakt."""
    first = np.array([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 3.0, 0.0]]])
    second = np.array([[[4.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 3.0]]])

    def unwanted(*args):
        raise AssertionError("Die gemeinsame Kante braucht keine erneute Kollinearitätsprüfung")

    monkeypatch.setattr(intersections, "_point_on_line_with_rounding", unwanted)
    hit, flat = intersections.crossing_pairs(
        first, second, np.array([[0, 1, 2]]), np.array([[1, 0, 3]]), with_coplanar=True
    )
    assert not hit.any() and not flat.any()


def _crossed_spheres() -> tuple[np.ndarray, np.ndarray]:
    """Zwei Kugeln, die sich durchdringen, als ein Netz — echte Schnitte und viele Nachbarn."""
    first = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    second = trimesh.creation.icosphere(subdivisions=4, radius=8.0)
    second.apply_translation((9.0, 1.0, 0.5))
    both = trimesh.util.concatenate([first, second])
    return np.asarray(both.vertices), np.asarray(both.faces)


def test_steep_neighbours_leave_the_search_before_the_exact_check() -> None:
    """Schräge Nachbarn trennt schon die Trennprüfung, und sie kosten wie vorher (RM-568).

    An einem geschlossenen Netz teilen fast alle Kandidaten eine Ecke; sie
    gingen bis zum 08.10.2026 alle durch die genaue Prüfung — am Spiderman
    68 s der Selbstschnittsuche, mit der Nachbarprüfung 17 s. Das Budget zählt
    sie weiter als eine genaue Prüfung, damit es an derselben Stelle endet.
    """
    sphere = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
    surface = intersections._surface(np.asarray(sphere.vertices), np.asarray(sphere.faces))
    assert surface is not None
    first, second = next(
        intersections._candidates(surface, None, intersections._Search(), separate=False)
    )
    same = surface.faces[second][:, :, None] == surface.faces[first][:, None, :]
    touching = (same.any(axis=2).sum(axis=1) >= 1) & (same.any(axis=2).sum(axis=1) <= 2)
    separated, cost = intersections._separated(surface, first, second)
    assert touching.sum() > 1000, "Voraussetzung: die Kugel hat ihre Nachbarn"
    assert separated[touching].all(), "a closed sphere has no crossing neighbours"
    assert np.all(cost[touching] == 1.0), "a neighbour costs one exact check, as before"


@pytest.mark.parametrize("budget", [None, 2_000, 20_000, 60_000])
def test_the_neighbour_separation_changes_no_answer_of_the_search(
    monkeypatch: pytest.MonkeyPatch, budget: int | None
) -> None:
    """Dieselben Paare, dieselbe Vollständigkeit, dieselben geprüften Dreiecke — mit Budget.

    Die Gegenprobe ist der Stand davor: ohne Nachbarprüfung in der Trennung.
    """
    vertices, faces = _crossed_spheres()
    now = intersections.crossing_face_pairs(vertices, faces, max_pairs=budget)
    with monkeypatch.context() as patched:
        patched.setattr(
            intersections,
            "_touching_apart",
            lambda surface, first, second: np.zeros(len(first), dtype=bool),
        )
        before = intersections.crossing_face_pairs(vertices, faces, max_pairs=budget)
    assert len(before.first) > 100 or budget is not None, "Voraussetzung: echte Schnitte"
    np.testing.assert_array_equal(now.first, before.first)
    np.testing.assert_array_equal(now.second, before.second)
    np.testing.assert_array_equal(now.coplanar, before.coplanar)
    assert now.complete == before.complete
    if before.checked is None:
        assert now.checked is None
    else:
        assert now.checked is not None
        np.testing.assert_array_equal(now.checked, before.checked)
