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

    def counted(initial: Any, residual: Any, check: Any, jacobian: Any = None) -> Any:
        if len(np.asarray(initial)) == 6:
            runs[0] += 1
        return raw(initial, residual, check, jacobian)

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
    """Die vier Bohrungen der Platte sind dasselbe Stück Geometrie — einmal gerechnet.

    ``plate_holes.stl`` ist 80 x 50 x 8 mm mit vier Bohrungen zu 5,2 mm. Sie
    sind deckungsgleich bis auf eine Verschiebung, tragen also dieselbe
    Kennzahl, und die leere Kegelantwort der ersten gilt für alle vier. Das ist
    zugleich die Probe darauf, dass der Hebel überhaupt greifen **kann**: Wären
    es vier Klassen, prüfte dieser Test nichts.
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

    Ein Quader, dessen Oberseite ein flacher Bogen über 40 mm ist. Bei drei
    Grad (R 764) meldete der exakte Kern eine Verrundung, sein eigener
    Netzzwilling eine gekrümmte Fläche; bei zwölf Grad (R 191) ist es an ihm
    eine Verrundung.
    """
    pytest.importorskip("OCP.BRepPrimAPI")
    from app.core.brep import profiles
    from app.core.brep.features import features_of
    from app.core.sketch.profile import Profile, ProfileSegment

    def arched(arc: float) -> tuple[Any, float]:
        chord = 40.0
        radius = (chord / 2.0) / units.exact_sin_degrees(arc / 2.0)
        rise = radius * (1.0 - units.exact_cos_degrees(arc / 2.0))
        outline = Profile(
            segments=(
                ProfileSegment("line", (0.0, 0.0), (chord, 0.0)),
                ProfileSegment("line", (chord, 0.0), (chord, 10.0)),
                ProfileSegment("arc", (chord, 10.0), (0.0, 10.0), via=(chord / 2.0, 10.0 + rise)),
                ProfileSegment("line", (0.0, 10.0), (0.0, 0.0)),
            )
        )
        return profiles.extrude(outline, 8.0), radius

    shallow, _radius = arched(3.0)
    fillets = [f.id for f in features_of(shallow).values() if f.kind == "fillet"]
    assert fillets == [], f"three degrees of arc are an edge at the exact kernel: {fillets}"

    kept, radius = arched(12.0)
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
