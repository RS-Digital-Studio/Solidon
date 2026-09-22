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
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import features as features_module
from app.core.perceive.features import (
    CONE_START_ANGLE,
    MIN_PATCH_FACES,
    RIGID_KEY_POINTS,
    ROUND_FIT_EVALUATIONS,
    _refined_fit,
    _rigid_key,
    detect,
    forget_cache,
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
