"""Die Rundformeinpassung antwortet unabhängig davon, wo der Körper liegt (RM-210).

Gemessen am 22.09.2026 an echten Modellen: `Elegoo_erster_Druck.3mf` liefert
166 Merkmale, derselbe Körper um 13,7 mm verschoben 164, um 37 Grad gedreht
171. Zweimal am unveränderten Körper gelesen kommt dagegen beide Male dasselbe
heraus — die Erkennung ist deterministisch, nur nicht lageunabhängig.

Die Ursache ist bis auf den einzelnen Fleck eingegrenzt: Von 202 Kegelfits
antwortete genau einer anders, und sein Startwert war in beiden Lagen Bit für
Bit derselbe. Was ihn kippte, war die Rundung in ``support.points - origin``,
und er stand mit hundert Auswertungen ohnehin an der Kippe.

Hier stehen die drei Zusicherungen, die daraus folgen. Zwei davon sind
Regeln, die der Löser einhält, die dritte ist die Zusage an den Kunden:

* Ein Lauf, der sein Auswertungsbudget ausschöpft, hat nicht konvergiert und
  antwortet deshalb gar nicht.
* Ein Fleck, dessen Normalen zu flach stehen, bekommt keinen Kegellauf — die
  Antwort stünde ohnehin fest.
* Derselbe Körper liefert verschoben und gedreht dieselben Merkmale.

**Der eingecheckte Korpus allein macht die dritte Zusicherung stumpf**: Alle
34 Körper sind stabil, weil sie analytisch gebaut sind. Der Lagefehler ist ein
statistischer Effekt und braucht tausende Flecken an der Kippe, wie sie ein
CAD-Export mitbringt; ein solcher Körper gehört nicht in das Entwicklungstor.
Die ersten beiden Zusicherungen prüfen deshalb die **Regel**, nicht ihre
Wirkung — sie bleiben scharf, auch wenn kein Korpuskörper den Fall trägt.

Seit dem 23.09.2026 stehen drei weitere Regeln hier, gefunden an den
Verrundungen, die in der Lageprobe über 101 echte Körper kippten:

* Welche Konturecken einen Kreis tragen, hängt nicht davon ab, an welcher Ecke
  die Hülle beginnt — und die folgt den Koordinaten.
* Welche Flecken zu einer Fläche zusammenfinden, hängt nicht an ihrer
  Reihenfolge, und die Rechtfertigung einer Vereinigung gilt in beide
  Richtungen.
* Unter :data:`MIN_ROUND_ARC` ist eine Rundform eine Kante — an beiden Kernen
  (Entscheidung Robert zu RM-210).
"""

from __future__ import annotations

import itertools
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh
from shapely.geometry import LineString

from app.core import units
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import features as features_module
from app.core.perceive.features import (
    CONE_START_ANGLE,
    MIN_PATCH_FACES,
    MIN_ROUND_ARC,
    RIGID_KEY_POINTS,
    ROUND_FIT_EVALUATIONS,
    ConeFit,
    CylinderFit,
    _refined_fit,
    _rigid_key,
    detect,
    forget_cache,
    span_about,
)
from tests.helpers import exact_kernel

MESHES = Path(__file__).parent / "data" / "meshes"


def plate(name: str = "plate_holes.stl") -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def moved(mesh: MeshData, *, turn: float = 0.0, shift: tuple[float, float, float]) -> MeshData:
    """Derselbe Körper, starr bewegt — dieselbe Geometrie, andere Koordinaten."""
    body = trimesh.Trimesh(
        vertices=np.asarray(mesh.raw.vertices, dtype=float).copy(),
        faces=np.asarray(mesh.raw.faces, dtype=np.int64).copy(),
        process=False,
    )
    if turn:
        axis = np.array([1.0, 2.0, 3.0])
        matrix = trimesh.transformations.rotation_matrix(turn, axis / np.linalg.norm(axis))
    else:
        matrix = np.eye(4)
    matrix[:3, 3] = shift
    body.apply_transform(matrix)
    return MeshData(raw=body, slots=mesh.slots)


def kinds(found: dict[str, Any]) -> dict[str, int]:
    """Was der Kunde sieht: wie viele Merkmale je Art.

    Die Kennungen (``cone_1``, ``cone_2``) sind Positionsnummern und wandern
    beim Drehen mit — sie taugen als Maßstab nicht.
    """
    tally: dict[str, int] = {}
    for feature in found.values():
        tally[feature.kind] = tally.get(feature.kind, 0) + 1
    return dict(sorted(tally.items()))


# --- Der Löser antwortet nur, wenn er fertig geworden ist -----------------------


def test_a_run_that_spends_its_whole_budget_answers_nothing() -> None:
    """Wer am Limit endet, hat nicht konvergiert — und hat damit nichts zu sagen.

    Die Residuenfunktion hier hat ihr Minimum im Unendlichen: Jeder Schritt
    verbessert etwas, keiner kommt an. Genau so verhalten sich die 1 093 von
    1 127 Kegelläufen an der Kumiko-Schale, die ihr Budget ausschöpfen.
    """

    def a_bent_valley(values: np.ndarray) -> np.ndarray:
        """Rosenbrocks Tal: krumm genug, dass es mehr als drei Schritte braucht."""
        return np.asarray([10.0 * (values[1] - values[0] ** 2), 1.0 - values[0]], dtype=float)

    def slope(values: np.ndarray) -> np.ndarray:
        return np.asarray([[-20.0 * values[0], 10.0], [-1.0, 0.0]], dtype=float)

    start = np.array([-1.2, 1.0])

    # **Das Budget wird gesenkt, nicht die Aufgabe verbogen.** Die Regel hängt
    # an :data:`ROUND_FIT_EVALUATIONS`, und ein knappes Budget prüft sie an
    # derselben Stelle wie ein knapper Fleck — ohne eine pathologische Funktion
    # zu konstruieren, die es in keinem Netz gibt.
    features_module.ROUND_FIT_EVALUATIONS = 3
    try:
        answer = _refined_fit(start, a_bent_valley, None, slope)
    finally:
        features_module.ROUND_FIT_EVALUATIONS = ROUND_FIT_EVALUATIONS

    assert answer is None, "a run that stops at its limit must not produce a fit"


def test_the_same_valley_is_answered_with_room_to_work() -> None:
    """Die Gegenprobe — sonst schriebe der Test oben nur eine Abwesenheit fest.

    Dieselbe Aufgabe, dasselbe Startfeld, nur das volle Budget: Jetzt muss die
    Antwort kommen, und sie muss die richtige sein.
    """

    def a_bent_valley(values: np.ndarray) -> np.ndarray:
        return np.asarray([10.0 * (values[1] - values[0] ** 2), 1.0 - values[0]], dtype=float)

    def slope(values: np.ndarray) -> np.ndarray:
        return np.asarray([[-20.0 * values[0], 10.0], [-1.0, 0.0]], dtype=float)

    answer = _refined_fit(np.array([-1.2, 1.0]), a_bent_valley, None, slope)

    assert answer is not None, "with room to work the valley is walked to its end"
    assert answer == pytest.approx([1.0, 1.0], abs=1e-6)


def test_a_run_that_converges_still_answers() -> None:
    """Die Gegenprobe — sonst schriebe der Test oben nur eine Abwesenheit fest.

    Zwei Größen, zwei lineare Beobachtungen: Das ist in wenigen Schritten
    gelöst, und die Antwort muss kommen.
    """
    target = np.array([3.0, -2.0])

    def plain(values: np.ndarray) -> np.ndarray:
        return np.asarray(values - target, dtype=float)

    answer = _refined_fit(np.array([0.0, 0.0]), plain, None)

    assert answer is not None, "a well-posed fit must still be answered"
    assert answer == pytest.approx(target, abs=1e-9)


# --- Ein flacher Fleck bekommt keinen Kegellauf --------------------------------


def test_a_flat_patch_never_reaches_the_cone_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Kegelwinkel steht vor dem Löser fest; unter der Schranke ist er keiner.

    Die Bohrungen von ``plate_holes.stl`` sind gerade. Ihr Startwinkel kommt
    aus den Normalen und liegt bei Bruchteilen eines Grades — der Löser würde
    hundert Auswertungen lang bestätigen, was die Normalen schon sagen.
    """
    runs = [0]
    raw = features_module._refined_fit

    def counted(
        initial: Any, residual: Any, check: Any, jacobian: Any = None, **options: Any
    ) -> Any:
        if len(np.asarray(initial)) == 6:
            runs[0] += 1
        return raw(initial, residual, check, jacobian, **options)

    monkeypatch.setattr(features_module, "_refined_fit", counted)
    forget_cache()
    found = detect(plate())

    assert runs[0] == 0, f"straight bores need no cone solver, {runs[0]} ran"
    assert kinds(found)["hole"] == 4, "and the four bores are still found"


def test_the_start_angle_bound_stays_below_the_cone_threshold() -> None:
    """Die Schranke darf keinen Kegel abschneiden, den die Erkennung noch meldet.

    Gemessen an drei echten Modellen ist der kleinste Startwinkel, aus dem
    noch ein Kegelzweig wird, 0,88 Grad. Ein halbes Grad liegt darunter und
    ist zugleich ein Zehntel von :data:`CONE_MIN_ANGLE`.
    """
    assert CONE_START_ANGLE < features_module.CONE_MIN_ANGLE / 5.0, (
        "the start bound must stay far below the angle that makes a cone a cone"
    )


# --- Deckungsgleiche Flecken sind dieselbe Aufgabe ------------------------------


def test_four_identical_bores_are_fitted_once() -> None:
    """Vier STL-gerundete Bohrungen teilen ihre zusätzliche Kegelfrage.

    ``plate_holes.stl`` ist 80 x 50 x 8 mm mit vier Bohrungen zu 5,2 mm. Sie
    sind deckungsgleich bis auf eine Verschiebung, tragen also dieselbe
    Kennzahl. Ihre Originalecken sind gröber gerundet als EPS_GEOM; deshalb
    wird ein Kegel einmal gefragt und die leere Antwort danach geteilt.
    """
    mesh = plate()
    body = mesh.raw
    curved = features_module._all_but(len(body.faces), features_module._large_facet_faces(body))
    patches = [
        entry
        for entry in features_module._connected_patches(body, curved)
        if len(entry) >= MIN_PATCH_FACES
    ]
    marks = {_rigid_key(body, entry) for entry in patches}

    assert len(patches) == 4, f"the plate has four bores, {len(patches)} patches were found"
    assert None not in marks, "the bores must be small enough to carry a key"
    assert len(marks) == 1, f"four identical bores are one class, not {len(marks)}"

    asked: list[tuple[int, ...]] = []
    raw = features_module.fit_cone

    def watching(body_in: Any, patch: Any, *, check_cancelled: Any = None) -> Any:
        asked.append(tuple(patch))
        return raw(body_in, patch, check_cancelled=check_cancelled)

    features_module.fit_cone = watching  # type: ignore[assignment]
    try:
        forget_cache()
        found = detect(mesh)
    finally:
        features_module.fit_cone = raw  # type: ignore[assignment]

    assert len(asked) == 1, f"one class is one fit, not {len(asked)}"
    assert kinds(found)["hole"] == 4, "and all four bores are still reported"


def test_a_key_is_refused_for_patches_that_are_too_large() -> None:
    """Alle paarweisen Abstände kosten quadratisch — ein Riesenfleck zahlt nicht.

    Ohne diese Grenze wäre der Hebel an einer Figur teurer als der Lauf, den
    er spart: Die Haut eines erzeugten Netzes ist **ein** Fleck mit
    dreihunderttausend Dreiecken.
    """
    body = trimesh.creation.icosphere(subdivisions=3)
    everything = list(range(len(body.faces)))

    assert len(everything) > RIGID_KEY_POINTS, "the probe needs a patch above the bound"
    assert _rigid_key(body, everything) is None
    assert _rigid_key(body, everything[: MIN_PATCH_FACES - 1]) is None, (
        "and a patch below the fitting size carries no key either"
    )


def test_a_moved_patch_keeps_its_key() -> None:
    """Die Kennzahl steht auf Abständen, und Abstände überleben eine Bewegung."""
    body = trimesh.creation.box(extents=(10.0, 6.0, 4.0))
    patch = list(range(MIN_PATCH_FACES))
    here = _rigid_key(body, patch)

    turned = body.copy()
    axis = np.array([1.0, 2.0, 3.0])
    matrix = trimesh.transformations.rotation_matrix(
        math.radians(37.0), axis / np.linalg.norm(axis)
    )
    matrix[:3, 3] = (13.7, -4.25, 6.5)
    turned.apply_transform(matrix)

    assert here is not None
    assert _rigid_key(turned, patch) == here, "a rigid motion must not change the key"


# --- Die Zusage an den Kunden ---------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "plate_holes.stl",
        "plate_countersunk.stl",
        "post_with_fillet.stl",
        "block_with_rounded_edge.stl",
        "sphere_socket.stl",
        "torus_ring.stl",
    ],
)
def test_the_same_body_moved_is_read_the_same(name: str) -> None:
    """Wer sein Teil anders auf die Platte legt, bekommt denselben Steckbrief.

    Drei Bewegungen, die nichts an der Geometrie ändern: eine ungleichmäßige
    Verschiebung, eine gleichmäßige und eine Drehung um eine schiefe Achse.
    Alle drei trafen an echten Modellen schon einmal daneben.
    """
    mesh = plate(name)
    forget_cache()
    here = kinds(detect(mesh))

    for label, turn, shift in (
        ("verschoben", 0.0, (13.7, -4.25, 6.5)),
        ("gleichmäßig", 0.0, (13.7, 13.7, 13.7)),
        ("gedreht", math.radians(37.0), (0.0, 0.0, 0.0)),
    ):
        forget_cache()
        there = kinds(detect(moved(mesh, turn=turn, shift=shift)))
        assert there == here, f"{name} reads differently once {label}: {here} -> {there}"


def test_a_cone_keeps_its_angle_when_the_body_turns() -> None:
    """Nicht nur die Zahl der Merkmale — auch ihre drehfesten Maße bleiben.

    Eine Senkung hat einen Öffnungswinkel und einen Durchmesser. Beides sind
    Eigenschaften des Teils, nicht seiner Lage auf der Platte.
    """
    mesh = plate("plate_countersunk.stl")
    forget_cache()
    here = sorted(
        (round(float(entry.params["angle"]), 6), round(float(entry.params["diameter"]), 6))
        for entry in detect(mesh).values()
        if entry.kind == "cone"
    )
    forget_cache()
    there = sorted(
        (round(float(entry.params["angle"]), 6), round(float(entry.params["diameter"]), 6))
        for entry in detect(moved(mesh, turn=math.radians(37.0), shift=(13.7, -4.25, 6.5))).values()
        if entry.kind == "cone"
    )

    assert here, "the probe needs at least one cone"
    assert there == pytest.approx(here, abs=1e-3), (
        f"a countersink keeps its angle and diameter when the body turns: {here} -> {there}"
    )


# --- Die Konturecken hängen nicht am Anfang der Hülle ----------------------------


def _two_rows_of_corners(step: float = 5.1) -> np.ndarray:
    """Der Schnitt einer Verrundung R 10 aus zwei Eckenreihen, nachgebaut am 1x1-Tray.

    Sechs Ecken liegen auf dem Kreis, dazwischen sechs einer zweiten Reihe
    4,6 µm weiter innen — so ungleich verteilt wie am echten Teil, in einer
    Lücke zwei. Die Mitte liegt abseits des Ursprungs, wie in jedem Fleck.
    """
    radius, inner = 10.0, 10.0 - 0.0046
    points = [
        (
            radius * units.exact_cos_degrees(index * step),
            radius * units.exact_sin_degrees(index * step),
        )
        for index in range(6)
    ]
    for gap, shares in enumerate(([0.23], [0.24], [0.2, 0.62], [0.25], [0.26])):
        for share in shares:
            angle = (gap + share) * step
            points.append(
                (inner * units.exact_cos_degrees(angle), inner * units.exact_sin_degrees(angle))
            )
    return np.asarray(points) + np.array([3.7, -12.1])


def test_the_contour_carries_the_same_circle_wherever_its_ring_starts() -> None:
    """Welche Ecken den Kreis tragen, entscheidet nicht die Lage des Körpers.

    Douglas-Peucker hielt den Anfang des Rings fest und teilte am jeweils
    fernsten Punkt; GEOS lässt die Hülle an der Ecke mit den kleinsten
    Koordinaten beginnen. Am 1x1-Tray blieb so in der gelesenen Lage eine
    innere Ecke stehen — r = 10,058 und Streuung 0,11 —, um 37 Grad gedreht
    nicht: r = 10,000. Die zwei Hälften der Verrundung fanden danach je nach
    Lage zusammen oder nicht. Am Nachbau kamen über 52 Drehungen drei
    verschiedene Radien heraus, bis 10,062.
    """
    points = _two_rows_of_corners()
    radii = set()
    for turn in range(0, 360, 7):
        cos, sin = units.exact_cos_degrees(turn), units.exact_sin_degrees(turn)
        turned = np.column_stack(
            (points[:, 0] * cos - points[:, 1] * sin, points[:, 0] * sin + points[:, 1] * cos)
        )
        outline = features_module._cylinder_contour(turned, 0.01, None)
        assert outline is not None, f"the arc is a contour at {turn} degrees"
        _centre, radius = features_module._fit_circle(outline)
        radii.add(round(float(radius), 6))

    assert radii == {10.0}, f"one circle in every pose, not {sorted(radii)}"


@pytest.mark.parametrize(
    ("span", "centre"),
    [
        (360.0, (3.7, -12.1)),
        (5.0, (3000.0, -2000.0)),
        (0.1, (0.0, 0.0)),
        (180.0, (1_000_000.0, -1_000_000.0)),
    ],
)
def test_the_circle_fit_keeps_short_arcs_and_distant_centres(
    span: float,
    centre: tuple[float, float],
) -> None:
    """Der plattformgleiche Ausgleich behält die Genauigkeit schmaler Bögen.

    Die erwarteten Maße erzeugen die Punkte direkt. Der schmalste Bogen liegt
    absichtlich unter der Erkennungsschwelle und prüft nur den Zahlenausgleich.
    """
    radius = 12.7
    angles = np.linspace(13.0 - span / 2.0, 13.0 + span / 2.0, 61)
    points = np.asarray(
        [
            (
                centre[0] + radius * units.exact_cos_degrees(float(angle)),
                centre[1] + radius * units.exact_sin_degrees(float(angle)),
            )
            for angle in angles
        ]
    )

    found, measured = features_module._fit_circle(points)

    assert math.hypot(float(found[0]) - centre[0], float(found[1]) - centre[1]) < units.EPS_GEOM
    assert measured == pytest.approx(radius, abs=units.EPS_GEOM, rel=0.0)


@pytest.mark.parametrize(
    "points",
    [[(-1.0, 0.0), (0.0, 0.0), (1.0, 0.0)], [(3.0, -2.0)] * 3],
)
def test_a_circle_fit_does_not_invent_a_radius_on_a_line(
    points: list[tuple[float, float]],
) -> None:
    """Ein rangloser Ausgleich ist kein Beleg für einen Kreis."""
    _centre, radius = features_module._fit_circle(np.asarray(points))

    assert units.is_zero(radius)


# --- Welche Flecken zusammenfinden, hängt nicht an ihrer Folge ----------------


_PIECES = {"A": list(range(6)), "B": list(range(10, 16)), "C": list(range(20, 26))}


def _pieces_in(patch: list[int]) -> frozenset[str]:
    """Aus welchen der drei Stücke ein Fleck besteht."""
    faces = set(patch)
    return frozenset(name for name, piece in _PIECES.items() if set(piece) <= faces)


def _wall(radius: float = 5.0, spread: float = 0.1) -> CylinderFit:
    """Ein Zylinderfit ohne Körper — die Zusammenlegung liest nur seine Zahlen."""
    return CylinderFit(
        axis=(0.0, 0.0, 1.0),
        centre=(0.0, 0.0, 0.0),
        radius=radius,
        residual=0.0,
        inward=False,
        spread=spread,
    )


@pytest.mark.parametrize("angle", [0.0, 37.0, 90.0])
@pytest.mark.parametrize("radius, expected", [(40.0, True), (80.0, False)])
def test_the_size_proof_uses_the_body_and_not_its_rotated_world_box(
    angle: float, radius: float, expected: bool
) -> None:
    """Eine gedrehte Weltbox macht keinen zuvor zu großen Kreis passend (RM-210)."""
    body = trimesh.creation.box(extents=(120.0, 100.0, 10.0))
    matrix = trimesh.transformations.rotation_matrix(math.radians(angle), (1.0, 2.0, 3.0))
    body.apply_transform(matrix)
    direction = matrix[:3, :3] @ np.array([0.0, 0.0, 1.0])
    fit = CylinderFit(
        axis=tuple(float(value) for value in direction),
        centre=(0.0, 0.0, 0.0),
        radius=radius,
        residual=0.0,
        inward=False,
        spread=0.0,
        radial_min=radius,
        radial_max=radius,
    )

    assert features_module._fits_in_the_body(MeshData.of(body), fit) is expected


@pytest.mark.parametrize("angle", [0.0, 37.0, 90.0])
@pytest.mark.parametrize("width, narrow", [(0.24, False), (0.18, True)])
@pytest.mark.parametrize("subdivide", [False, True])
def test_a_small_faces_width_survives_rotation_and_subdivision(
    angle: float, width: float, narrow: bool, subdivide: bool
) -> None:
    """Vier Flächen am Bohrerhalter kippten allein an der Weltboxdiagonale (RM-210)."""
    vertices = np.array([[0.0, 0.0, 0.0], [0.6, 0.0, 0.0], [0.6, width, 0.0], [0.0, width, 0.0]])
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    if subdivide:
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    body.apply_transform(
        trimesh.transformations.rotation_matrix(math.radians(angle), (1.0, 2.0, 3.0))
    )
    patch = list(range(len(body.faces)))

    assert features_module._a_sliver(body, patch) is narrow
    area, reach = features_module._area_and_reach(body, patch)
    assert area == pytest.approx(0.6 * width, abs=units.EPS_GEOM)
    assert reach == pytest.approx(math.hypot(0.6, width), abs=units.EPS_GEOM)


@pytest.mark.parametrize("flat", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_the_point_diameter_agrees_with_all_actual_pairs(flat: bool, reverse: bool) -> None:
    """Die Boxen des Suchbaums sind nur Schranken; auch innere Ecken können gewinnen."""
    points = np.random.default_rng(37).normal(size=(257, 3))
    if flat:
        points[:, 2] = 0.0
    if reverse:
        points = points[::-1].copy()
    expected = max(math.dist(first, second) for first in points for second in points)
    matrix = trimesh.transformations.rotation_matrix(math.radians(37.0), (1.0, 2.0, 3.0))
    turned = points @ matrix[:3, :3].T + (12.5, -4.0, 80.0)

    assert features_module._point_diameter(points) == pytest.approx(expected, abs=units.EPS_GEOM)
    assert features_module._point_diameter(turned) == pytest.approx(expected, abs=units.EPS_GEOM)
    assert features_module._point_diameter(points, stop_after=expected / 2.0) > expected / 2.0


def _joined_by(monkeypatch: pytest.MonkeyPatch, answers: dict[frozenset[str], Any]) -> None:
    """Die Zusammenlegung fragt nur noch die Tafel: Welche Vereinigung ist ein Zylinder?"""

    def fit(body: Any, patch: list[int], *, check_cancelled: Any = None) -> Any:
        return answers.get(_pieces_in(patch))

    monkeypatch.setattr(features_module, "fit_cylinder", fit)
    monkeypatch.setattr(features_module, "_same_cylinder", lambda body, one, two: True)
    monkeypatch.setattr(features_module, "_fits_in_the_body", lambda mesh, found: True)
    monkeypatch.setattr(
        features_module, "in_body_order", lambda body, groups: [sorted(group) for group in groups]
    )


def test_three_pieces_of_one_fillet_join_in_every_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Welche Stücke einer Verrundung zusammenfinden, hängt nicht an ihrer Folge.

    Nachgestellt ist das Keilschloss (``Wedge-Lock (Top).stl``): Zwei der drei
    Stücke ergeben zusammen keinen Zylinder, jedes mit dem dritten und alle
    drei schon. In der gelesenen Lage kamen die zwei zuerst, und am Ende
    standen zwei Verrundungen; um 90 Grad gedreht war es eine. Die Folge der
    Flecken ist seit ``in_body_order`` die der Koordinaten — also der Lage.
    """
    joined = _wall()
    _joined_by(
        monkeypatch,
        {frozenset("AB"): joined, frozenset("AC"): joined, frozenset("ABC"): joined},
    )
    monkeypatch.setattr(features_module, "_lies_on_the_cylinder", lambda *args, **kwargs: False)

    outcomes = set()
    for order in itertools.permutations("ABC"):
        merged = features_module._merged_cylinders(
            None, None, [(_wall(), _PIECES[name]) for name in order]
        )
        outcomes.add(frozenset(_pieces_in(patch) for _fit, patch in merged))

    assert outcomes == {frozenset({frozenset("ABC")})}, (
        f"one fillet in every order, not {sorted(map(sorted, outcomes))}"
    )


def test_a_piece_on_the_other_cylinder_joins_whichever_came_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Rechtfertigung einer Vereinigung gilt in beide Richtungen.

    Nachgestellt ist das Unterteil ``bottom-double.stl``: ein kurzer Bogen mit
    r = 5,0143, ein langer mit r = 5,0004, zusammen streuen sie mehr als jeder
    für sich. Der kurze liegt auf dem Zylinder des langen, der lange nicht auf
    dem des kurzen — gefragt war nur, ob der später gekommene auf dem früheren
    liegt, und kam der kurze zuerst, blieben es zwei Verrundungen.
    """
    short, long_ = _wall(5.0143, 0.0046), _wall(5.0004, 0.0092)
    _joined_by(monkeypatch, {frozenset("AB"): _wall(5.0022, 0.0155)})

    def lies(body: Any, fit: CylinderFit, patch: list[int], **kwargs: Any) -> bool:
        return fit is long_ and _pieces_in(patch) == frozenset("A")

    monkeypatch.setattr(features_module, "_lies_on_the_cylinder", lies)

    for first, second in (("A", "B"), ("B", "A")):
        fits = {"A": short, "B": long_}
        merged = features_module._merged_cylinders(
            None, None, [(fits[first], _PIECES[first]), (fits[second], _PIECES[second])]
        )
        assert [_pieces_in(patch) for _fit, patch in merged] == [frozenset("AB")], (
            f"one fillet when {first} comes first"
        )


def test_three_pieces_of_one_cone_join_in_every_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dieselbe Regel für die Kegel — am Siebhalter kippte eine Senkung daran."""

    def cone(radius: float = 6.0) -> ConeFit:
        return ConeFit(
            axis=(0.0, 0.0, 1.0),
            apex=(0.0, 0.0, -6.0),
            centre=(0.0, 0.0, 0.0),
            half_angle=45.0,
            radius=radius,
            residual=0.0,
            recess=True,
        )

    answers = {frozenset("AB"): cone(), frozenset("AC"): cone(), frozenset("ABC"): cone()}
    monkeypatch.setattr(
        features_module,
        "fit_cone",
        lambda body, patch, *, check_cancelled=None: answers.get(_pieces_in(patch)),
    )
    monkeypatch.setattr(features_module, "_same_cone", lambda one, two: True)
    monkeypatch.setattr(
        features_module, "in_body_order", lambda body, groups: [sorted(group) for group in groups]
    )

    outcomes = set()
    for order in itertools.permutations("ABC"):
        merged = features_module._merged_cones(None, [(cone(), _PIECES[name]) for name in order])
        outcomes.add(frozenset(_pieces_in(patch) for _fit, patch in merged))

    assert outcomes == {frozenset({frozenset("ABC")})}, (
        f"one cone in every order, not {sorted(map(sorted, outcomes))}"
    )


# --- Unter dem Mindestbogen ist eine Rundform eine Kante (RM-210) ---------------


def bent_strip(turn: float, segments: int, radius: float = 20.0) -> MeshData:
    """Ein Streifen, 3 mm dick und 10 mm hoch, der mit einem Bogen R ``radius`` knickt.

    Der Bogen dreht um ``turn`` Grad in ``segments`` Sehnen; an der Außen- und
    an der Innenseite liegt je eine Rundung.
    """
    points = [(0.0, 0.0), (30.0, 0.0)]
    for step in range(1, segments + 1):
        angle = -90.0 + turn * step / segments
        points.append(
            (
                30.0 + radius * units.exact_cos_degrees(angle),
                radius + radius * units.exact_sin_degrees(angle),
            )
        )
    end_x, end_y = points[-1]
    points.append(
        (
            end_x + 30.0 * units.exact_cos_degrees(turn),
            end_y + 30.0 * units.exact_sin_degrees(turn),
        )
    )
    band = LineString(points).buffer(-3.0, single_sided=True, cap_style=2, join_style=2)
    return MeshData.of(trimesh.creation.extrude_polygon(band, height=10.0))


def fillet_arcs(mesh: MeshData) -> list[float]:
    """Der Bogen jeder erkannten Verrundung, in Grad."""
    forget_cache()
    found = detect(mesh)
    welded = features_module._one_body(mesh).raw
    return sorted(
        span_about(
            welded,
            np.asarray(feature.params["axis"], dtype=float),
            np.asarray(feature.params["centre"], dtype=float),
            feature.face_indices,
        )
        for feature in found.values()
        if feature.kind == "fillet"
    )


def test_a_round_form_under_the_minimum_arc_is_an_edge() -> None:
    """Unter :data:`MIN_ROUND_ARC` meldet die Erkennung keine Rundung.

    Entscheidung Robert zu RM-210 (23.09.2026): konservativ, etwa fünf Grad.
    Der Streifen knickt um 4,5 Grad in acht Sehnen, und bis dahin standen
    dort zwei Verrundungen mit je 3,37 Grad Bogen — für einen Drucker ist
    das eine Kante.
    """
    arcs = fillet_arcs(bent_strip(4.5, 8))

    assert arcs == [], f"a bend of 4.5 degrees carries no fillet, found arcs {arcs}"


def test_a_round_form_over_the_minimum_arc_stays_a_fillet() -> None:
    """Die Gegenprobe: Zwölf Grad sind eine Rundung, außen wie innen."""
    arcs = fillet_arcs(bent_strip(12.0, 8))

    assert len(arcs) == 2, f"a bend of 12 degrees carries two fillets, found arcs {arcs}"
    assert min(arcs) >= MIN_ROUND_ARC


def test_the_exact_kernel_holds_the_same_minimum_arc() -> None:
    """Dieselbe Schranke am exakten Körper, sonst hinge der Steckbrief am Format.

    Eine Platte 200 x 10, auf deren Oberseite ein flacher Buckel R 40 sitzt.
    Bei drei Grad meldete der exakte Kern eine Verrundung, sein eigener
    Netzzwilling keine; bei zwölf Grad ist es an beiden eine Verrundung.

    Der Buckel und nicht ein Bogen über die ganze Breite: Der passt mit R 764
    oder R 191 quer zur Achse nicht in einen 40 mm breiten Quader und ist
    darum an beiden Kernen gar keine Rundform, sondern eine gekrümmte Fläche
    (RM-226, ``test_exact_body_parity``). Hier soll allein der Mindestbogen
    entscheiden, also passt der Buckel in die Platte.
    """
    exact_kernel()
    from app.core.brep import profiles
    from app.core.brep.features import features_of
    from app.core.sketch.profile import Profile, ProfileSegment

    def bumped(arc: float) -> tuple[Any, float]:
        radius = 40.0
        half = radius * units.exact_sin_degrees(arc / 2.0)
        rise = radius * (1.0 - units.exact_cos_degrees(arc / 2.0))
        outline = Profile(
            segments=(
                ProfileSegment("line", (0.0, 0.0), (200.0, 0.0)),
                ProfileSegment("line", (200.0, 0.0), (200.0, 10.0)),
                ProfileSegment("line", (200.0, 10.0), (100.0 + half, 10.0)),
                ProfileSegment(
                    "arc", (100.0 + half, 10.0), (100.0 - half, 10.0), via=(100.0, 10.0 + rise)
                ),
                ProfileSegment("line", (100.0 - half, 10.0), (0.0, 10.0)),
                ProfileSegment("line", (0.0, 10.0), (0.0, 0.0)),
            )
        )
        return profiles.extrude(outline, 8.0), radius

    shallow, _radius = bumped(3.0)
    fillets = [f.id for f in features_of(shallow).values() if f.kind == "fillet"]
    assert fillets == [], f"three degrees of arc are an edge at the exact kernel: {fillets}"

    kept, radius = bumped(12.0)
    radii = [f.params["radius"] for f in features_of(kept).values() if f.kind == "fillet"]
    assert radii == [pytest.approx(radius, rel=1e-9)], f"twelve degrees stay a fillet: {radii}"


# --- Die Erkennung fragt ihre Flecken nach Größe, nicht nach Lage ---------------


def plate_with_three_bores() -> MeshData:
    """Eine Platte 60 x 40 x 8 mit drei Bohrungen Ø 4, 6 und 9 an drei Stellen.

    Die Stellen sind so gewählt, dass ihre Folge nach X eine andere ist als
    nach Y: Eine Vierteldrehung um Z ordnet sie nach den Koordinaten um.
    """
    plate = trimesh.creation.box(extents=(60.0, 40.0, 8.0))
    bores = []
    for diameter, (x, y) in ((4.0, (-20.0, 10.0)), (6.0, (0.0, -10.0)), (9.0, (20.0, 5.0))):
        bore = trimesh.creation.cylinder(radius=diameter / 2.0, height=20.0, sections=48)
        bore.apply_translation((x, y, 0.0))
        bores.append(bore)
    return MeshData.of(trimesh.boolean.difference([plate, *bores], engine="manifold"))


def test_the_patches_are_asked_in_the_same_order_in_every_pose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Welcher Fleck zuerst gefragt wird, entscheidet die Größe, nicht die Lage.

    Die Folge zählt: Von zwei deckungsgleichen Flecken antwortet der erste für
    den zweiten (:func:`_rigid_key`), und ein Stück fragt nach dem Ring, den
    ein früherer Fleck gefunden hat. Seit :func:`in_body_order` folgte sie den
    Koordinaten — am Siebhalter sprang eine Senkung danach bei einer
    Vierteldrehung um Z auf andere Dreiecke. Die Fläche hängt weder an der
    Dreiecksfolge noch an der Lage.
    """
    mesh = plate_with_three_bores()
    asked: list[frozenset[int]] = []
    raw = features_module.fit_cylinder

    def watching(body: Any, patch: Any, *, check_cancelled: Any = None) -> Any:
        asked.append(frozenset(int(index) for index in patch))
        return raw(body, patch, check_cancelled=check_cancelled)

    monkeypatch.setattr(features_module, "fit_cylinder", watching)
    sequences = []
    for axis, degrees in (((0.0, 0.0, 1.0), 0.0), ((0.0, 0.0, 1.0), 90.0), ((1.0, 2.0, 3.0), 37.0)):
        body = mesh.raw.copy()
        body.apply_transform(trimesh.transformations.rotation_matrix(math.radians(degrees), axis))
        asked.clear()
        forget_cache()
        found = detect(MeshData(raw=body, slots=mesh.slots))
        assert kinds(found)["hole"] == 3, f"three bores at {degrees} degrees"
        sequences.append(list(asked))

    assert sequences[0] == sequences[1] == sequences[2], (
        "the order of the questions must not follow the pose"
    )


# --- Derselbe Fleck an einem neuen Körper (RM-261) ------------------------------
#
# Nach jedem Schritt erkennt die Auswertung den ganzen Körper neu (§21.1). Eine
# Boolesche übernimmt jedes Dreieck, das sie nicht schneidet, bitgleich und —
# seit ``geom.attributes.in_source_layout`` — in der Darstellung seines
# Eingangs. Ein unberührter Fleck liest dann dieselben Zahlen und bekommt
# dieselbe Antwort; der Merker über die Körpergrenze gibt sie ohne Rechnung.

#: Körper mit Rundformen, deren Einpassung den Löser braucht — und eine Stelle
#: auf ihrer größten Fläche, weit weg von allen Rundformen.
_ROUNDS_AND_A_FAR_SPOT = (
    "post_with_fillet.stl",
    "plate_chamfer_and_taper.stl",
    "plate_countersunk.stl",
    "sphere_socket.stl",
)
_ROUND_KINDS = frozenset({"fillet", "cone", "sphere", "torus", "hole", "pin"})


def _bored_far_away(mesh: MeshData, found: dict[str, Any]) -> MeshData:
    """Eine Bohrung Ø 2 in die größte Fläche, am weitesten weg von jeder Rundform."""
    from app.core.geom.boolean import boolean

    rounds = [feature for feature in found.values() if feature.kind in _ROUND_KINDS]
    largest = max(
        (feature for feature in found.values() if feature.kind == "face"),
        key=lambda feature: float(feature.params["area"]),
    )
    centres = np.asarray(mesh.raw.triangles_center, dtype=float)
    taken = centres[sorted({index for feature in rounds for index in feature.face_indices})]
    spots = centres[sorted(largest.face_indices)]
    gaps = np.min(np.linalg.norm(spots[:, None, :] - taken[None, :, :], axis=2), axis=1)
    tool = trimesh.creation.cylinder(radius=1.0, height=6.0, sections=32)
    tool.apply_transform(
        trimesh.geometry.align_vectors(
            np.array([0.0, 0.0, 1.0]), np.asarray(largest.params["normal"], dtype=float)
        )
    )
    tool.apply_translation(spots[int(np.argmax(gaps))])
    return boolean("difference", [mesh, MeshData.of(tool)]).mesh


def _every_bit(feature: Any) -> tuple[Any, ...]:
    """Art und jedes Maß Bit für Bit."""
    rows: list[Any] = [feature.kind]
    for key in sorted(feature.params):
        value = feature.params[key]
        if isinstance(value, float):
            rows.append((key, value.hex()))
        elif isinstance(value, (list, tuple)) and all(isinstance(i, (int, float)) for i in value):
            rows.append((key, tuple(float(item).hex() for item in value)))
        else:
            rows.append((key, repr(value)))
    return tuple(rows)


@pytest.mark.parametrize("name", _ROUNDS_AND_A_FAR_SPOT)
def test_untouched_round_forms_read_the_same_numbers_after_a_bore_elsewhere(name: str) -> None:
    """Eine Bohrung weit weg ändert an einer Verrundung, einem Kegel, einer Kugel nichts.

    Gerechnet wird frisch, ohne Merker: Es ist die Darstellung, die es trägt.
    Vor ``in_source_layout`` las die Erkennung nach der ersten Booleschen jede
    Rundform in den letzten Stellen anders — an diesen vier Körpern 6 der 8
    unberührten —, und am Gartenschlauchhalter verschwand eine Verrundung
    113 mm von der Bohrung entfernt in einem Kegel.
    """
    from app.core.geom import attributes

    mesh = plate(name)
    forget_cache()
    before = detect(mesh)
    bored = _bored_far_away(mesh, before)
    forget_cache()
    after = detect(bored)

    match = attributes._same_triangles(mesh.raw, bored.raw)
    to_after = np.full(mesh.triangle_count, -1, dtype=np.int64)
    rows = np.flatnonzero(match >= 0)
    to_after[match[rows]] = rows
    by_triangles = {frozenset(feature.face_indices): feature for feature in after.values()}
    untouched = 0
    for feature in before.values():
        if feature.kind not in _ROUND_KINDS:
            continue
        mapped = to_after[sorted(feature.face_indices)]
        if (mapped < 0).any():
            continue
        untouched += 1
        partner = by_triangles.get(frozenset(mapped.tolist()))
        assert partner is not None, (name, feature.id)
        assert _every_bit(partner) == _every_bit(feature), (name, feature.id)
    assert untouched, f"{name}: the bore must leave a round form untouched"


def test_the_next_body_takes_the_answers_of_its_untouched_patches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nach einer Bohrung braucht kein unberührter Fleck den Löser — und die Antwort bleibt.

    Die Verrundung am Pfosten kostet frisch zehn Läufe des Lösers; nach der
    Erkennung des Eingangs keinen, denn die neue Bohrung ist ein gerader
    Zylinder. Dieselbe Erkennung ganz neu gerechnet sagt Bit für Bit dasselbe.
    """
    runs = [0]
    raw = features_module._refined_fit

    def counted(*args: Any, **kwargs: Any) -> Any:
        runs[0] += 1
        return raw(*args, **kwargs)

    monkeypatch.setattr(features_module, "_refined_fit", counted)
    mesh = plate("post_with_fillet.stl")
    forget_cache()
    bored = _bored_far_away(mesh, detect(mesh))
    runs[0] = 0
    taken_over = detect(bored)
    over = runs[0]
    forget_cache()
    runs[0] = 0
    fresh = detect(bored)

    assert over == 0 < runs[0], (over, runs[0])
    assert sorted(map(_every_bit, taken_over.values())) == sorted(map(_every_bit, fresh.values()))
    assert {name: sorted(f.face_indices) for name, f in taken_over.items()} == {
        name: sorted(f.face_indices) for name, f in fresh.items()
    }


def test_answers_across_bodies_go_with_the_last_body_that_asked() -> None:
    """Der Merker über die Körpergrenze hält eine Antwort, solange ein Körper sie gefragt hat.

    Dieselbe Grenze wie jede kleine Frage (``CACHE_LIMIT_PER_QUESTION``) und
    dieselbe Lebensdauer wie der Merker je Körper: Ein zweiter Körper mit
    derselben Lesung liest die Antwort mit, und erst mit dem letzten geht sie.
    """
    import gc

    forget_cache()
    first = trimesh.creation.icosphere(subdivisions=2, radius=6.0)
    second = trimesh.Trimesh(
        np.asarray(first.vertices).copy(), np.asarray(first.faces).copy(), process=False
    )
    patch = list(range(len(first.faces)))
    held = features_module._BY_GEOMETRY

    ball = features_module.fit_sphere(first, patch)
    assert ball is not None
    assert len(held["fit_sphere"]) == 1
    assert features_module.fit_sphere(second, patch) is ball, "dieselbe Lesung, dieselbe Antwort"
    assert len(held["fit_sphere"]) == 1

    del first
    gc.collect()
    assert len(held["fit_sphere"]) == 1, "der zweite Körper hält sie noch"
    del second
    gc.collect()
    assert not held["fit_sphere"], "mit dem letzten Körper geht die Antwort"


def test_moving_a_bore_keeps_the_layout_of_the_rest_of_the_body(profile: Any) -> None:
    """*Merkmal verschieben* füllt, glättet die Narben und schneidet — der Rest bleibt, wie er war.

    Drei Aufrufe des Kerns, und der zweite (``_without_scars``) läuft an
    ``boolean()`` vorbei: Jeder legt zurück, was er nicht geschnitten hat
    (``attributes.in_source_layout``). Am Ende beginnt jedes übernommene
    Dreieck an derselben Ecke wie im Eingang — sonst läse die Erkennung nach
    dem Schritt jeden Fleck in den letzten Stellen anders.
    """
    from app.core.geom import attributes
    from tests.helpers import feature_operation

    mesh = plate("plate_holes.stl")
    forget_cache()
    found = detect(mesh)
    bore = min((f for f in found.values() if f.kind == "hole"), key=lambda f: f.id)
    centre = np.asarray(bore.params["centre"], dtype=float)
    result = feature_operation(
        "move_feature",
        mesh,
        found,
        bore,
        profile,
        x=float(centre[0]) + 1.0,
        y=float(centre[1]),
        z=float(centre[2]),
    )
    moved = result.outputs[0].mesh
    match = attributes._same_triangles(mesh.raw, moved.raw)
    kept = np.flatnonzero(match >= 0)
    assert len(kept) > moved.triangle_count // 2, "der größte Teil der Platte bleibt unberührt"
    assert np.array_equal(
        np.asarray(moved.raw.triangles)[kept], np.asarray(mesh.raw.triangles)[match[kept]]
    ), "jedes übernommene Dreieck beginnt an der Ecke seines Vorbilds"


@pytest.mark.parametrize("turn", [37.0, 90.0])
@pytest.mark.parametrize("scale", [0.5, 2.0])
def test_the_cone_solver_sees_the_same_local_problem_after_a_rigid_move(turn, scale):
    """Die Löseraufgabe hängt an der Form, nicht an Weltachsen und Weltbox."""
    from app.core.geom.transform import rotation_about

    source = trimesh.creation.cone(radius=5.0, height=12.0, sections=32)
    source.apply_scale(scale)
    patch = np.flatnonzero(np.asarray(source.face_normals)[:, 2] > 0.0).tolist()
    matrix = rotation_about((1.0, 2.0, 3.0), (0.0, 0.0, 0.0), turn)
    matrix[:3, 3] = (13.7, -4.2, 3.0)
    target = source.copy()
    target.apply_transform(matrix)
    plans = []
    for body, faces in ((source, patch), (target, patch[::-1])):
        forget_cache()
        support = features_module._surface_support(body, faces)
        assert support is not None
        plan = features_module._cone_plan(support, features_module.ROUND_WALL_TOLERANCE, None)
        assert plan is not None
        plans.append(plan)
        fit = features_module.fit_cone(body, faces)
        assert fit is not None and fit.good
        assert fit.half_angle == pytest.approx(math.degrees(math.atan(5.0 / 12.0)), abs=1e-7)
    before, after = plans
    assert after.scale == pytest.approx(before.scale, rel=1e-12)
    assert after.start() == pytest.approx(before.start(), abs=1e-10)
    assert after.solving == pytest.approx(before.solving, abs=1e-10)
    assert after.initial_axis == pytest.approx(before.initial_axis, abs=1e-12)
    assert after.first == pytest.approx(before.first, abs=1e-12)
    assert after.second == pytest.approx(before.second, abs=1e-12)


@pytest.mark.parametrize("turn", [0.0, 37.0])
@pytest.mark.parametrize("scale", [0.5, 2.0])
def test_a_proven_cylinder_does_not_depend_on_a_competing_cone_solver(monkeypatch, turn, scale):
    """Originalecken und Normalen belegen den Zylinder vor einem beliebigen Kegeltal."""
    from app.core.geom.transform import rotation_about

    raw = trimesh.creation.cylinder(radius=5.0 * scale, height=12.0 * scale, sections=64)
    raw.apply_transform(rotation_about((1.0, 2.0, 3.0), (0.0, 0.0, 0.0), turn))
    mesh = MeshData.of(raw)

    def unnecessary_cone(*args, **kwargs):
        pytest.fail("a cylinder already proved by its actual contour needs no cone solver")

    forget_cache()
    monkeypatch.setattr(features_module, "_cone_plan", unnecessary_cone)
    fitted = features_module._fitted(mesh)
    assert len(fitted.cylinders) == 1
    assert not fitted.cones
    cylinder, patch = fitted.cylinders[0]
    assert cylinder.radius == pytest.approx(5.0 * scale, abs=1e-9)
    assert len(patch) == 128


@pytest.mark.parametrize("turn", [0.0, 37.0])
def test_a_short_shallow_cone_is_not_replaced_by_a_close_cylinder(turn):
    """Ein aufgelöster Kegel behält seinen kleineren Formfehler auch bei kurzer Wand."""
    from app.core.geom.transform import rotation_about

    angle, height, radius = 5.5, 0.1, 5.0
    upper = radius - height * math.tan(math.radians(angle))
    angles = np.linspace(0.0, math.tau, 64, endpoint=False)
    vertices = np.vstack(
        [
            np.column_stack((radius * np.cos(angles), radius * np.sin(angles), np.zeros(64))),
            np.column_stack((upper * np.cos(angles), upper * np.sin(angles), np.full(64, height))),
        ]
    )
    faces = []
    for index in range(64):
        following = (index + 1) % 64
        faces.extend(((index, following, index + 64), (following, following + 64, index + 64)))
    raw = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    raw.apply_transform(rotation_about((1.0, 2.0, 3.0), (0.0, 0.0, 0.0), turn))
    forget_cache()
    fitted = features_module._fitted(MeshData.of(raw))
    assert len(fitted.cones) == 1
    assert not fitted.cylinders
    assert fitted.cones[0][0].half_angle == pytest.approx(angle, abs=1e-8)


# --- Der Kegelstart steht nicht im falschen Tal ----------------------------------


def _shallow_cone_strip(placement: np.ndarray) -> trimesh.Trimesh:
    """Ein Streifen eines Kegels mit 40 Grad Halbwinkel, 15 Grad um die Achse
    und 0,5 mm hoch, unregelmäßig vernetzt wie ein CAD-Export und auf Float32
    gerundet wie eine STL — erst bewegt, dann gerundet."""
    from scipy.spatial import Delaunay

    generator = np.random.default_rng(210)
    corners = np.vstack(
        (generator.random((20, 2)), [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
    )
    height = 10.0 + 0.5 * corners[:, 1]
    turn = np.radians(20.0 + 15.0 * corners[:, 0])
    reach = height * math.tan(math.radians(40.0))
    vertices = np.column_stack((reach * np.cos(turn), reach * np.sin(turn), height))
    raw = trimesh.Trimesh(vertices=vertices, faces=Delaunay(corners).simplices, process=False)
    raw.apply_transform(placement)
    raw.vertices = np.asarray(raw.vertices, dtype=np.float32).astype(float)
    return raw


_PLACEMENTS = {
    "original": np.eye(4),
    "shifted": trimesh.transformations.translation_matrix((13.7, -4.2, 3.0)),
    "z90": trimesh.transformations.rotation_matrix(math.radians(90.0), (0.0, 0.0, 1.0)),
    "oblique37": trimesh.transformations.rotation_matrix(math.radians(37.0), (1.0, 2.0, 3.0)),
}


def test_a_shallow_cone_strip_is_found_wherever_it_lies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der zweite Kegelstart aus der Quadrik trägt einen flachen Streifen in jeder Lage (RM-210).

    Am Gartenschlauchhalter endeten fünf Teilstücke zweier Kegelgruppen nach
    58 bis 100 Auswertungen — je nach Lage knapp unter oder am Budget, dann
    ohne Kegel. Der Start aus den Normalen steht an so einem Streifen im
    falschen Tal: Die Normalen streuen kaum, Achse und Winkel sind aus ihnen
    nicht bestimmt. Schöpft er das Budget aus, rechnet ein zweiter Lauf von
    der Quadrik der Stützpunkte. Der Sollwert ist der gebaute Winkel; die
    Float32-Rundung nach der Bewegung verschiebt ihn um Hundertstel Grad.
    """
    from app.core.perceive.features import fit_cone

    solve = features_module.refine.solve
    spent: list[int] = []

    def counted(*args: Any, **kwargs: Any) -> Any:
        result = solve(*args, **kwargs)
        spent.append(int(result.nfev))
        return result

    monkeypatch.setattr(features_module.refine, "solve", counted)
    for name, placement in _PLACEMENTS.items():
        raw = _shallow_cone_strip(placement)
        forget_cache()
        spent.clear()
        fit = fit_cone(raw, list(range(len(raw.faces))))
        assert fit is not None, f"{name}: kein Kegel"
        assert fit.half_angle == pytest.approx(40.0, abs=0.05), name
        # Der erste Lauf schöpft sein Budget aus, der zweite kommt rasch an.
        assert spent == [ROUND_FIT_EVALUATIONS, spent[-1]], f"{name}: {spent}"
        assert spent[-1] < ROUND_FIT_EVALUATIONS // 4, f"{name}: {spent}"

    # Gegenprobe: Vom Normalenstart aus findet der Löser den Kegel in keiner
    # dieser Lagen — sonst prüfte der Test den Start nicht.
    monkeypatch.setattr(features_module, "_quadric_cone_start", lambda *_args: None)
    missed = []
    for name, placement in _PLACEMENTS.items():
        raw = _shallow_cone_strip(placement)
        forget_cache()
        fit = fit_cone(raw, list(range(len(raw.faces))))
        if fit is None or abs(fit.half_angle - 40.0) > 0.05:
            missed.append(name)
    assert missed == list(_PLACEMENTS), "ohne den Quadrikstart prüft der Test nichts"


def _ring_reference(outline: np.ndarray, tolerance: float) -> np.ndarray:
    """``_simplified_ring`` vor RM-568: je Schritt das Minimum über den Ring, Lücken in NumPy."""
    count = len(outline)
    if count <= 3:
        return outline
    before = np.roll(np.arange(count), 1)
    after = np.roll(np.arange(count), -1)
    kept = np.ones(count, dtype=bool)

    def gap_cost(corner: int) -> float:
        start, end = int(before[corner]), int(after[corner])
        inside = (
            np.arange(start + 1, end)
            if start < end
            else np.r_[np.arange(start + 1, count), np.arange(0, end)]
        )
        return float(
            features_module._segment_distances(outline[inside], outline[start], outline[end]).max()
        )

    costs = features_module._segment_distances(outline, outline[before], outline[after])
    remaining = count
    while remaining > 3:
        masked = np.where(kept, costs, np.inf)
        lowest = float(masked.min())
        if lowest > tolerance:
            break
        tied = np.flatnonzero(masked == lowest)
        corner = int(tied[np.lexsort(outline[tied].T[::-1])[0]])
        kept[corner] = False
        remaining -= 1
        start, end = int(before[corner]), int(after[corner])
        after[start], before[end] = end, start
        costs[start] = gap_cost(start)
        costs[end] = gap_cost(end)
    return np.asarray(outline[kept], dtype=float)


def test_the_ring_simplification_keeps_every_corner_it_kept_before() -> None:
    """Haufen und Python-Zahlen statt Minimum über den Ring — dieselben Ecken, Bit für Bit.

    Am Eiffelturm kostete die alte Fassung 10,1 s der Erkennung (RM-568).
    Geprüft an verrauschten Kreisen, an regelmäßigen Vielecken mit exakt
    gleichen Kosten (Gleichstand über Lage und Nummer), an Ringen weit vom
    Ursprung und bei Toleranzen von null bis über den Radius.
    """
    source = np.random.default_rng(81020261)
    rings = []
    for count in (4, 5, 7, 12, 40, 97, 300):
        angles = np.sort(source.uniform(0.0, 2.0 * math.pi, count))
        radius = 10.0 + source.normal(scale=0.003, size=count)
        rings.append(np.column_stack((radius * np.cos(angles), radius * np.sin(angles))))
        regular = np.linspace(0.0, 2.0 * math.pi, count, endpoint=False)
        rings.append(np.column_stack((np.cos(regular), np.sin(regular))) * 3.0)
        rings.append(rings[-2] + (1.0e5, -3.0e4))
    for outline in rings:
        for tolerance in (0.0, 1e-6, 1e-3, 0.01, 0.1, 1.0, 50.0):
            expected = _ring_reference(outline.copy(), tolerance)
            found = features_module._simplified_ring(outline.copy(), tolerance)
            assert found.shape == expected.shape, (len(outline), tolerance)
            assert np.array_equal(found, expected), (len(outline), tolerance)


def _circle_reference(points: np.ndarray) -> tuple[np.ndarray, float]:
    """``_fit_circle`` vor RM-568: ``math.hypot`` über NumPy-Skalare."""
    from app.core import units

    origin = np.array([units.exact_mean(points[:, index].tolist()) for index in range(2)])
    local = points - origin
    scale = float(np.abs(local).max())
    if len(points) < 3 or scale <= 0.0:
        return origin, 0.0
    local /= scale
    matrix = np.column_stack([local[:, 0], local[:, 1], np.ones(len(points))])
    target = local[:, 0] * local[:, 0] + local[:, 1] * local[:, 1]
    order = [0, 1, 2]
    rank_limit = np.finfo(float).eps * max(matrix.shape) * math.sqrt(len(points))
    for column in range(3):
        norms = [math.hypot(*matrix[column:, index]) for index in range(column, 3)]
        pivot = column + int(np.argmax(norms))
        length = norms[pivot - column]
        if length <= rank_limit:
            return origin, 0.0
        matrix[:, [column, pivot]] = matrix[:, [pivot, column]]
        order[column], order[pivot] = order[pivot], order[column]
        direction = matrix[column:, column].copy()
        diagonal = -math.copysign(length, float(direction[0]))
        direction[0] -= diagonal
        direction /= math.hypot(*direction)
        for remaining in range(column + 1, 3):
            projection = 2.0 * math.fsum((direction * matrix[column:, remaining]).tolist())
            matrix[column:, remaining] -= projection * direction
        projection = 2.0 * math.fsum((direction * target[column:]).tolist())
        target[column:] -= projection * direction
        matrix[column, column] = diagonal
        matrix[column + 1 :, column] = 0.0
    solved = [0.0, 0.0, 0.0]
    for row in (2, 1, 0):
        rest = math.fsum(float(matrix[row, index]) * solved[index] for index in range(row + 1, 3))
        solved[row] = (float(target[row]) - rest) / float(matrix[row, row])
    solution = np.empty(3)
    solution[order] = solved
    centre = np.array([solution[0] / 2.0, solution[1] / 2.0])
    radius = math.sqrt(max(float(solution[2] + centre[0] * centre[0] + centre[1] * centre[1]), 0.0))
    return centre * scale + origin, radius * scale


def test_the_circle_fit_reads_python_numbers_and_answers_bit_for_bit() -> None:
    """``math.hypot`` über ``tolist`` statt über NumPy-Skalare — dasselbe Ergebnis (RM-568).

    Am Spiderman 282 Kreisausgleiche mit Tausenden Punkten, 2,5 s; je Aufruf
    2,7 → 1,9 ms bei 6 000 Punkten. Geprüft an Bögen, Vollkreisen, Rauschen,
    fernem Ursprung und einem rangarmen Fall.
    """
    source = np.random.default_rng(81020263)
    cases = []
    for count in (3, 4, 17, 300, 6000):
        angles = source.uniform(0.0, source.uniform(0.3, 2.0 * math.pi), count)
        radius = source.uniform(0.5, 80.0)
        points = np.column_stack((radius * np.cos(angles), radius * np.sin(angles)))
        cases.append(points + source.normal(scale=1e-3, size=points.shape))
        cases.append(points + np.array((2.0e5, -7.0e4)))
    cases.append(np.column_stack((np.linspace(0.0, 1.0, 50), np.zeros(50))))
    for points in cases:
        expected = _circle_reference(points.copy())
        found = features_module._fit_circle(points.copy())
        assert np.array_equal(found[0], expected[0])
        assert found[1] == expected[1]
