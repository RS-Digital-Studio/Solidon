"""Stabile Merkmalsbezeichner, und was passiert, wenn sie es nicht sein
können (§21.2, §21.3).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import apply, translation
from app.core.ingest.loader import normalise
from app.core.knowledge import standards
from app.core.perceive.features import detect_holes
from app.core.perceive.matching import (
    _cost_matrix,
    apply_mapping,
    cost,
    match,
    question_for,
)
from app.core.registry import REGISTRY
from app.core.scene.placement import bore_advice, screw_for_bore, values_for
from app.core.types import Feature
from app.core.units import format_length

MESHES = Path(__file__).parent / "data" / "meshes"

load_operations()


def body(name: str) -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def holes_of(mesh: MeshData) -> dict[str, Feature]:
    return {hole.id: hole for hole in detect_holes(mesh)}


def one_hole_plate() -> MeshData:
    """Eine Platte mit einer einzigen Bohrung in der Mitte — das „Vorher" des
    Zwillingsfalls.
    """
    plate = trimesh.creation.box(extents=(60.0, 30.0, 8.0))
    drill = trimesh.creation.cylinder(radius=2.6, height=40.0, sections=48)
    return MeshData.of(trimesh.boolean.difference([plate, drill]))


def socket_plate(thickness: float = 15.0) -> MeshData:
    """Ein Block mit eingefräster Kalotte — dieselbe Pfanne wie im Korpus, nur
    mit wählbarer Dicke, damit sich der Körper ändern lässt, ohne dass das
    Merkmal verschwindet.
    """
    block = trimesh.creation.box(extents=(40.0, 40.0, thickness))
    ball = trimesh.creation.icosphere(subdivisions=3, radius=8.0)
    ball.apply_translation((0.0, 0.0, thickness / 2.0))
    return MeshData.of(trimesh.boolean.difference([block, ball]))


def test_the_vectorised_matrix_is_the_single_pair_formula() -> None:
    """Die schnelle Rechnung darf keine neue Zuordnungsregel erfinden.

    Gemischt werden richtungslose Achsen, gerichtete Normalen, verschiedene
    Arten und die beiden Größenschlüssel. Damit steht jede Verzweigung von
    ``cost`` mindestens einmal in der Matrix und wird elementweise gegen die
    lesbare Einzelpaar-Referenz geprüft.
    """
    old = [
        Feature(
            id="hole_old",
            kind="hole",
            provenance="detected",
            params={
                "centre": (1.0, 2.0, 3.0),
                "axis": (0.0, 0.0, 1.0),
                "diameter": 5.2,
            },
        ),
        Feature(
            id="face_old",
            kind="face",
            provenance="detected",
            params={
                "centre": (-4.0, 1.5, 8.0),
                "normal": (0.0, 1.0, 0.0),
                "area": 120.0,
            },
        ),
        Feature(
            id="sphere_old",
            kind="sphere",
            provenance="detected",
            params={"centre": (3.0, -2.0, 4.0), "diameter": 16.0},
        ),
    ]
    new = [
        Feature(
            id="hole_new",
            kind="hole",
            provenance="detected",
            params={
                "centre": (11.1, -2.0, 5.0),
                "axis": (0.0, 0.0, -1.0),
                "diameter": 5.4,
            },
        ),
        Feature(
            id="face_new",
            kind="face",
            provenance="detected",
            params={
                "centre": (5.0, -2.5, 10.0),
                "normal": (0.0, -1.0, 0.0),
                "area": 118.0,
            },
        ),
        Feature(
            id="sphere_new",
            kind="sphere",
            provenance="detected",
            params={"centre": (13.0, -6.0, 6.0), "diameter": 15.8},
        ),
    ]
    before = (0.0, 0.0, 0.0)
    after = (10.0, -4.0, 2.0)
    diagonal = 80.0

    matrix = _cost_matrix(old, new, before, after, diagonal)
    reference = np.asarray(
        [[cost(first, second, before, after, diagonal) for second in new] for first in old]
    )

    np.testing.assert_allclose(matrix, reference, rtol=1e-12, atol=1e-12)


def test_the_matching_needs_no_entry_for_a_new_kind_of_feature() -> None:
    """Kugel und Torus kamen am 22.08.2026 dazu, und die Kostenmatrix hat
    dafür keine Zeile bekommen — sie braucht keine.

    ``feature_vector`` liest ``centre``, ``axis`` und ``diameter`` **für jede
    Art gleich**; der Kommentar dort sagt es: „Unterschieden am Parameter,
    nicht an einer Artenliste." Eine neue Art muss also nichts anmelden, sie
    muss den Vertrag erfüllen. Dieser Test hält fest, dass sie es tut — sonst
    ist es eine einmalige Messung und kein Zustand.
    """
    from app.core.perceive.features import detect_spheres

    mesh = socket_plate()
    old = {sphere.id: sphere for sphere in detect_spheres(mesh)}
    new = {sphere.id: sphere for sphere in detect_spheres(socket_plate(18.0))}

    result = match(old, new, mesh.bounds.centre, mesh.bounds.diagonal)

    assert result.settled, f"the socket lost its name: {result}"
    assert result.mapping == {"sphere_1": "sphere_1"}


def test_two_rings_of_different_size_are_not_the_same_feature() -> None:
    """Der Fall, an dem die Zuordnung für Tori beinahe blind gewesen wäre.

    Die Torus-Parameter hießen zuerst ``ring_diameter`` und ``tube_diameter``
    — beides aussagekräftiger als ein nacktes ``diameter``, und beides falsch:
    ``feature_vector`` liest die Größe eines Merkmals aus genau diesem einen
    Schlüssel. Unter einem eigenen Namen war die Komponente null, und zwei
    Ringe mit Ø 40 und Ø 60 kosteten gegeneinander **0,0** — für die Zuordnung
    dasselbe Merkmal. Zwei Dichtnuten übereinander hätten den Nutzer bei jeder
    Auswertung dasselbe gefragt, mit der Antwort in den Daten (§21.3).

    Kein Test war damals rot. Dieser hier ist es, wenn jemand den Schlüssel
    zurückbenennt.
    """
    from app.core.perceive.features import detect_tori
    from app.core.perceive.matching import cost

    def ring(major: float) -> Feature:
        mesh = MeshData.of(
            trimesh.creation.torus(
                major_radius=major, minor_radius=5.0, major_sections=48, minor_sections=24
            )
        )
        return detect_tori(mesh)[0]

    wide, narrow = ring(30.0), ring(20.0)

    assert cost(wide, narrow, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 100.0) > 1.0, (
        "two rings of different size must not cost nothing against each other"
    )


def test_a_good_pair_is_not_sacrificed_to_a_cheaper_total() -> None:
    """Die ungarische Methode minimiert die **Summe** und kennt die Schwelle
    nicht — sie opfert deshalb ein annehmbares Paar, wenn zwei unannehmbare
    zusammen billiger sind.

    Gemessen an einer Platte mit Schraubenlöchern und einer Mutternfalle:

    ==================  ========  =======  =========
    altes Merkmal       gewählt   Kosten   Ergebnis
    ==================  ========  =======  =========
    ``nut_trap_pocket``  hole_2     3,281   verwaist
    ``nut_trap_bore``    hole_1     3,742   verwaist
    ==================  ========  =======  =========

    Die Summe 7,02 ist kleiner als jede Lösung, die ``hole_2`` an die Bohrung
    gibt — deren bestes Paar kostet 0,757 und läge damit **unter** der
    Schwelle. Beide fielen heraus, wo eines hätte bleiben können.

    Hier nachgestellt mit zwei alten Merkmalen und einem neuen, das nur zu
    einem von beiden passt: Wer die Summe minimiert, gibt es dem falschen.
    """
    mesh = body("plate_holes.stl")
    holes = holes_of(mesh)
    names = sorted(holes)
    near, far = holes[names[0]], holes[names[1]]

    result = match({"a": near, "b": far}, {"new": near}, mesh.bounds.centre, mesh.bounds.diagonal)

    assert result.mapping == {"a": "new"}, "the pair that fits must win, not the cheaper sum"
    assert result.orphaned == ("b",)


def test_identifiers_survive_an_operation_that_changes_nothing() -> None:
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    new = holes_of(mesh)

    result = match(old, new, mesh.bounds.centre, mesh.bounds.diagonal)

    assert result.settled
    assert result.mapping == {identifier: identifier for identifier in old}


def test_moving_the_whole_body_does_not_orphan_its_features() -> None:
    """§21.2: die Lage zählt im eigenen Bezug des Objekts, nicht im Weltbezug."""
    mesh = body("plate_holes.stl")
    moved = apply(mesh, translation((120.0, -40.0, 15.0)))

    result = match(
        holes_of(mesh),
        holes_of(moved),
        moved.bounds.centre,
        moved.bounds.diagonal,
        old_centre=mesh.bounds.centre,
    )

    assert result.settled, "a move is not a reason to lose every identifier"
    assert len(result.mapping) == 4


def test_a_vanished_feature_is_reported_as_orphaned() -> None:
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    new = {"hole_1": old["hole_1"]}

    result = match(old, new, mesh.bounds.centre, mesh.bounds.diagonal)

    assert len(result.orphaned) == 3
    assert not result.settled


def test_a_new_feature_is_reported_as_fresh() -> None:
    mesh = body("plate_holes.stl")
    all_holes = holes_of(mesh)
    old = {"hole_1": all_holes["hole_1"]}

    result = match(old, all_holes, mesh.bounds.centre, mesh.bounds.diagonal)

    assert len(result.fresh) == 3


def test_two_identical_bores_close_together_are_ambiguous() -> None:
    """§40: plate_holes_twin wird als mehrdeutig gemeldet statt geraten."""
    before = one_hole_plate()
    after = body("plate_holes_twin.stl")

    result = match(
        holes_of(before),
        holes_of(after),
        after.bounds.centre,
        after.bounds.diagonal,
        old_centre=before.bounds.centre,
    )

    assert result.ambiguous, "one bore in the middle fits both twins equally well"
    assert not result.settled
    candidates = next(iter(result.ambiguous.values()))
    assert len(candidates) >= 2


def test_the_ambiguity_becomes_a_question_with_choices() -> None:
    """§21.3: die Auswertung hält dort an und fragt über ctx.ask."""
    question, choices = question_for("hole_1", ("hole_1", "hole_2"))

    assert "hole_1" in question
    assert "hole_1" in choices and "hole_2" in choices
    assert len(choices) == 3, "the candidates plus the way out"


def test_a_different_kind_never_matches() -> None:
    mesh = body("plate_holes.stl")
    hole = next(iter(holes_of(mesh).values()))
    face = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"centre": hole.params["centre"], "normal": hole.params["axis"], "area": 10.0},
    )

    centre = mesh.bounds.centre
    assert cost(hole, face, centre, centre, mesh.bounds.diagonal) > 1000.0


def test_a_bore_that_changed_size_still_matches_if_it_stayed_put() -> None:
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    widened = {
        identifier: Feature(
            id=identifier,
            kind="hole",
            provenance="detected",
            params={**feature.params, "diameter": feature.params["diameter"] + 0.2},
        )
        for identifier, feature in old.items()
    }

    result = match(old, widened, mesh.bounds.centre, mesh.bounds.diagonal)
    assert result.settled, "widening a hole by a fifth of a millimetre keeps its name"


def test_renaming_carries_the_old_identifiers_over() -> None:
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    new = {f"detected_{index}": feature for index, feature in enumerate(old.values(), start=1)}

    result = match(old, new, mesh.bounds.centre, mesh.bounds.diagonal)
    renamed = apply_mapping(new, result)

    assert set(renamed) == set(old), "the stack keeps referring to the same names"
    for identifier, feature in renamed.items():
        assert feature.id == identifier


def test_a_bore_axis_has_no_sign() -> None:
    """Zweiter Fund vom 08.08.2026, freigelegt vom ersten: nach einer
    25°-Drehung erkennt die Suche die Zylinderachsen mal als ``+v``, mal als
    ``-v`` — eine Bohrungsachse ist eine Linie, keine Richtung. Der
    vorzeichenempfindliche Vergleich verwaiste die Hälfte der Löcher, und die
    stille Namens-Wiederverwendung kaschierte es, bis sie fiel.
    """
    mesh = body("plate_holes.stl")
    hole = next(iter(holes_of(mesh).values()))
    flipped = Feature(
        id="flipped",
        kind="hole",
        provenance="detected",
        params={
            **hole.params,
            "axis": tuple(-value for value in hole.params["axis"]),
        },
    )

    centre = mesh.bounds.centre
    same = cost(hole, flipped, centre, centre, mesh.bounds.diagonal)
    assert same < 1.0, "dieselbe Bohrung, nur mit umgekehrt gelesener Achse"


def test_a_face_normal_keeps_its_sign() -> None:
    """Die Gegenprobe: eine Flächennormale trägt Bedeutung — innen ist nicht
    außen, und zwei entgegengesetzte Flächen sind zwei Flächen.
    """
    face = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"centre": (0.0, 0.0, 8.0), "normal": (0.0, 0.0, 1.0), "area": 100.0},
    )
    opposite = Feature(
        id="face_2",
        kind="face",
        provenance="detected",
        params={"centre": (0.0, 0.0, 8.0), "normal": (0.0, 0.0, -1.0), "area": 100.0},
    )

    assert cost(face, opposite, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 100.0) > 1.0


def test_a_new_feature_does_not_swallow_a_survivor() -> None:
    """Das Fehlerbild vom 08.08.2026: eine neue Bohrung sortiert sich in der
    Erkennung vor die bestehenden, deren Nummern rutschen um eins — und beim
    Umbenennen kollidierte das unzugeordnete neue Merkmal mit dem vergebenen
    Namen eines Überlebenden. Eines von beiden verschwand wortlos aus der
    Szene: ``drill_hole`` bohrte ein Loch, das nie ein Merkmal wurde, und
    niemand konnte je darauf zeigen.
    """
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    survivors = list(old.values())
    first_centre = survivors[0].params["centre"]
    fresh_centre = (first_centre[0] + 17.3, first_centre[1] - 4.2, first_centre[2])
    drilled = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={**survivors[0].params, "centre": fresh_centre},
    )
    # Die Erkennung nummeriert nach Lage: das neue Loch zuerst, alle
    # Überlebenden rutschen um eine Nummer nach hinten.
    new = {"hole_1": drilled}
    for index, feature in enumerate(survivors, start=2):
        new[f"hole_{index}"] = feature

    result = match(old, new, mesh.bounds.centre, mesh.bounds.diagonal)
    renamed = apply_mapping(new, result)

    assert len(renamed) == len(old) + 1, "kein Merkmal geht verloren"
    assert set(old) <= set(renamed), "die Überlebenden behalten ihre Namen"
    added = set(renamed) - set(old)
    assert len(added) == 1
    fresh_id = added.pop()
    assert renamed[fresh_id].params["centre"] == fresh_centre
    assert renamed[fresh_id].id == fresh_id


def test_matching_against_nothing_is_not_a_crash() -> None:
    mesh = body("plate_holes.stl")
    holes = holes_of(mesh)

    assert match({}, holes, mesh.bounds.centre, mesh.bounds.diagonal).fresh == tuple(holes)
    assert match(holes, {}, mesh.bounds.centre, mesh.bounds.diagonal).orphaned == tuple(holes)
    assert match({}, {}, mesh.bounds.centre, mesh.bounds.diagonal).settled


def test_identifiers_survive_ten_operations(document, profile) -> None:
    """§40 für P3: nach zehn Schritten tragen die Bohrungen noch die Namen,
    mit denen sie begannen.
    """
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from app.i18n import _

    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    before = set(evaluate(document, profile, sources=sources).scene.objects["obj_1"].features)

    steps: list[OperationDraft] = [
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 5.0}),
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dy": -3.0}),
        OperationDraft(op="rotate_object", inputs=("obj_1",), params={"axis": "z", "angle": 15.0}),
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dz": 2.0}),
        OperationDraft(op="rotate_object", inputs=("obj_1",), params={"axis": "z", "angle": -15.0}),
        OperationDraft(op="place_on_bed", inputs=("obj_1",), params={}),
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": -5.0}),
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dy": 3.0}),
        OperationDraft(op="scale_object", inputs=("obj_1",), params={"factor": 1.0}),
        OperationDraft(op="place_on_bed", inputs=("obj_1",), params={}),
    ]
    for step in steps:
        history.apply(_("Schritt"), [step])

    result = evaluate(document, profile, sources=sources)

    assert result.complete
    assert set(result.scene.objects["obj_1"].features) == before
    assert "perceive.orphaned" not in {finding.code for finding in result.scene.report.findings}


def test_features_travel_with_the_motion_the_operation_reports() -> None:
    """§21.2: ein gedrehter Körper ist derselbe Körper, und die Op ist es, die
    das sagt.
    """
    from app.core.geom.ops import as_transform
    from app.core.geom.transform import rotation
    from app.core.perceive.matching import moved_features

    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    turned = apply(mesh, rotation("z", 15.0))

    carried = moved_features(old, as_transform(rotation("z", 15.0)))
    result = match(carried, holes_of(turned), turned.bounds.centre, turned.bounds.diagonal)

    assert result.settled, "carried along first, every bore finds itself again"
    assert not result.orphaned


def test_a_rigid_motion_keeps_a_feature_when_detection_misses_it(
    monkeypatch,
) -> None:
    """Eine starre Bewegung kann kein Merkmal geometrisch entfernen.

    Die Erkennung bleibt eine Messung am Dreiecksnetz und kann an einer
    Rundungsgrenze nach einer großen Verschiebung anders runden. Dann ist das
    zuvor bekannte Merkmal nicht fort: Die Operation hat seine exakte Matrix
    mitgegeben, also reist es mit ihr weiter. Ohne diese Zusicherung öffnete
    die sauber angeordnete CC2-Werkzeugbox mit fünf irreführenden
    ``perceive.orphaned``-Hinweisen.
    """
    from app.core.geom.ops import as_transform
    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    mesh = one_hole_plate()
    previous = holes_of(mesh)
    assert previous, "the fixture must expose a feature before it moves"
    matrix = translation((480.0, -125.0, 0.0))
    moved = apply(mesh, matrix)
    import importlib

    evaluation = importlib.import_module("app.core.scene.evaluate")
    monkeypatch.setattr(evaluation, "detect", lambda _mesh: {})
    findings = []

    result = _with_features(
        SceneObject(id="obj_1", name="Platte", mesh=moved),
        previous,
        Operation(
            id=2,
            op="translate_object",
            inputs=("obj_1",),
            outputs=("obj_1",),
            params={},
        ),
        lambda question, choices: choices[0],
        findings,
        as_transform(matrix),
        mesh.bounds,
    )

    assert set(result.features) == set(previous)
    assert "perceive.orphaned" not in {entry.code for entry in findings}
    old_centre = next(iter(previous.values())).params["centre"]
    new_centre = next(iter(result.features.values())).params["centre"]
    assert new_centre[0] == pytest.approx(old_centre[0] + 480.0)
    assert new_centre[1] == pytest.approx(old_centre[1] - 125.0)


def test_arranging_keeps_a_feature_when_detection_misses_it(monkeypatch) -> None:
    """Anordnen verschiebt jeden Körper starr, aber mit eigener Matrix.

    Die Operation arbeitet auf der ganzen Szene und kann deshalb keine
    einzelne gemeinsame ``transform``-Matrix zurückgeben. Aus ihrem Vertrag
    ist trotzdem bekannt, dass sie die Körper nur verschiebt. Ein numerisch
    nicht wiedererkanntes Merkmal muss deshalb um den Versatz seines Körpers
    mitgenommen werden.
    """
    import importlib

    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    mesh = one_hole_plate()
    previous = holes_of(mesh)
    matrix = translation((-120.0, 45.0, 0.0))
    moved = apply(mesh, matrix)
    evaluation = importlib.import_module("app.core.scene.evaluate")
    monkeypatch.setattr(evaluation, "detect", lambda _mesh: {})
    findings = []

    result = _with_features(
        SceneObject(id="obj_1", name="Platte", mesh=moved),
        previous,
        Operation(
            id=2,
            op="arrange_bed",
            inputs=("obj_1",),
            outputs=("obj_1",),
            params={},
        ),
        lambda question, choices: choices[0],
        findings,
        previous_bounds=mesh.bounds,
    )

    assert set(result.features) == set(previous)
    assert "perceive.orphaned" not in {entry.code for entry in findings}
    old_centre = next(iter(previous.values())).params["centre"]
    new_centre = next(iter(result.features.values())).params["centre"]
    assert new_centre[0] == pytest.approx(old_centre[0] - 120.0)
    assert new_centre[1] == pytest.approx(old_centre[1] + 45.0)


def test_without_the_motion_a_rotation_would_lose_them() -> None:
    """Warum die Matrix es wert ist, mitgetragen zu werden: derselbe Fall ohne
    sie.
    """
    from app.core.geom.transform import rotation

    mesh = body("plate_holes.stl")
    turned = apply(mesh, rotation("z", 40.0))

    result = match(holes_of(mesh), holes_of(turned), turned.bounds.centre, turned.bounds.diagonal)

    assert result.orphaned, "positions alone cannot follow a turn"


def test_a_transform_operation_reports_what_it_did() -> None:
    """Die Matrix kommt aus der Operation, nicht aus einem Vergleich danach."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    mesh = body("cube_clean.stl")
    entry = SceneObject(id="obj_1", name="x", mesh=mesh)
    spec = REGISTRY.get("translate_object")
    context = OpContext(
        scene=Scene(objects={"obj_1": entry}),
        inputs=[entry],
        params=spec.params(dx=5.0, dy=0.0, dz=0.0),
        profile=None,
        quality="fine",
        seed=None,
        progress=lambda fraction, text: None,
        ask=lambda question, choices: choices[0],
        cancelled=NeverCancelled(),
    )

    result = spec.fn(context)

    assert result.transform is not None
    assert result.transform[0][3] == 5.0


# --- erzeugte Merkmale (§21.2, Provenienz) --------------------------------------


def _generated(feature: Feature, name: str) -> Feature:
    """Dasselbe Merkmal, aber als eines, das eine Operation benannt hat."""
    import dataclasses

    return dataclasses.replace(feature, id=name, provenance="generated")


def _carried(
    mesh: MeshData,
    previous: dict[str, Feature],
    referenced: frozenset[str] | set[str] = frozenset(),
) -> tuple[dict[str, Feature], list]:
    """``_with_features`` an einer Operation, die ``features={}`` zurückgibt.

    Elf Stellen unter ``app/core/geom/`` tun das, und keine von ihnen meint
    damit „die erzeugten Merkmale sind fort" — sie füllen das Feld nur nicht.
    """
    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    def never(question: str, choices: list[str]) -> str:
        raise AssertionError(f"nothing here is ambiguous: {question}")

    entry = SceneObject(id="obj_1", name="Teil", mesh=mesh, features={})
    findings: list = []
    operation = Operation(id=4, op="thicken", inputs=("obj_1",), outputs=("obj_1",), params={})
    result = _with_features(entry, previous, operation, never, findings, referenced=referenced)
    return result.features, findings


def test_a_generated_feature_survives_an_operation_that_returns_none() -> None:
    """§21.2: „Keine Erkennung, keine Mehrdeutigkeit" — dann darf ein erzeugtes
    Merkmal auch nicht daran verschwinden, dass eine Operation sein Feld leer
    lässt.
    """
    mesh = one_hole_plate()
    bore = next(iter(holes_of(mesh).values()))
    previous = {"op3.bore_1": _generated(bore, "op3.bore_1")}

    features, _findings = _carried(mesh, previous)

    assert "op3.bore_1" in features, "the operation changed nothing; the name must hold"
    assert features["op3.bore_1"].provenance == "generated"


def test_a_generated_feature_learns_which_step_made_it() -> None:
    """§21.2 sagt jedem erzeugten Merkmal eine Handlung zu — „den Schritt
    ändern, der es erzeugt hat". Die Antwort darauf gab es bis zum 22.08.2026
    nirgends.

    ``provenance`` sagt nur *dass* ein Merkmal erzeugt wurde. Das ID-Präfix
    ``op4.pin_1``, das §21.2 als Beispiel führt, wird im Produktivcode nirgends
    vergeben und nirgends gelesen — es steht allein in Tests, die es von Hand
    hinschreiben, dieser hier eingeschlossen. Und ``SceneObject.created_by``
    beantwortet eine andere Frage.
    """
    mesh = one_hole_plate()
    bore = next(iter(holes_of(mesh).values()))
    entry = _made_by(mesh, {"bore_1": _generated(bore, "bore_1")})

    assert entry.features["bore_1"].created_by == 4, "the step that made it"


def test_passing_a_feature_along_is_not_making_it() -> None:
    """Und die Nummer bleibt stehen, wenn eine spätere Operation dasselbe
    Merkmal erneut ausgibt.

    Das ist der Fehler, den ``SceneObject.created_by`` macht: Es wird bei jeder
    Operation gesetzt, die das Objekt ausgibt, und zeigt deshalb auf die
    zuletzt beteiligte statt auf die erzeugende. Wer ein Merkmal durchreicht,
    hat es nicht erzeugt.
    """
    import dataclasses

    mesh = one_hole_plate()
    bore = next(iter(holes_of(mesh).values()))
    older = dataclasses.replace(_generated(bore, "bore_1"), created_by=2)
    entry = _made_by(mesh, {"bore_1": older})

    assert entry.features["bore_1"].created_by == 2, "step 4 only passed it on"


def test_a_detected_feature_has_no_maker() -> None:
    """Ein erkanntes Merkmal behält ``None``, und der Menüeintrag entfällt dort
    ersatzlos — er führte ins Leere, und das ist schlechter als keiner (§21.2).
    """
    assert all(hole.created_by is None for hole in holes_of(one_hole_plate()).values())


def _made_by(mesh: MeshData, declared: dict[str, Feature]) -> object:
    """``_with_features`` an einer Operation, die diese Merkmale **ausgibt**.

    Der Unterschied zu :func:`_carried`: Dort stehen sie in ``previous``, hier
    im Objekt, das die Operation produziert hat.
    """
    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    def never(question: str, choices: list[str]) -> str:
        raise AssertionError(f"nothing here is ambiguous: {question}")

    entry = SceneObject(id="obj_1", name="Teil", mesh=mesh, features=declared)
    operation = Operation(id=4, op="thicken", inputs=("obj_1",), outputs=("obj_1",), params={})
    return _with_features(entry, {}, operation, never, [])


def test_a_generated_feature_that_is_really_gone_is_reported() -> None:
    """Ein unbenutztes Merkmal darf verschwinden, aber nicht als Warnung.

    Grundkörper benennen ihre Flächen. Aushöhlen mit offener Oberseite und
    weiches Verschmelzen nehmen eine davon erwartbar mit — genau das tun zwei
    Beispielprojekte. Solange keine spätere Operation und keine Passung auf
    den Namen zeigt, ist das eine Auskunft und kein Problem (§21.3).
    """
    plate = one_hole_plate()
    bore = next(iter(holes_of(plate).values()))
    previous = {"op3.bore_1": _generated(bore, "op3.bore_1")}
    plugged = MeshData.of(trimesh.creation.box(extents=(60.0, 30.0, 8.0)))

    features, findings = _carried(plugged, previous)

    assert "op3.bore_1" not in features, "the bore is filled; keeping the name would be a phantom"
    reported = [entry for entry in findings if entry.values.get("feature") == "op3.bore_1"]
    assert reported, "a named feature that vanishes is a finding, not a silence"
    assert {entry.severity for entry in reported} == {"info"}
    assert not [entry for entry in reported if entry.code == "perceive.generated_lost"]


def test_a_referenced_generated_feature_that_is_gone_is_a_warning() -> None:
    """Erst der Verweis macht aus dem Verlust ein Problem (§21.3)."""
    plate = one_hole_plate()
    bore = next(iter(holes_of(plate).values()))
    previous = {"op3.bore_1": _generated(bore, "op3.bore_1")}
    plugged = MeshData.of(trimesh.creation.box(extents=(60.0, 30.0, 8.0)))

    _features, findings = _carried(plugged, previous, referenced={"op3.bore_1"})

    reported = [entry for entry in findings if entry.values.get("feature") == "op3.bore_1"]
    assert [entry.code for entry in reported] == ["perceive.generated_lost"]
    assert [entry.severity for entry in reported] == ["warning"]


def test_a_thread_travels_unchecked_because_detection_cannot_see_it() -> None:
    """Nicht jede Art ist prüfbar, und die unprüfbaren dürfen nicht daran
    sterben.

    Ein Gewinde entsteht in einem Baustein (§24.1); ``detect`` kennt die Art
    nicht. Gegen die Geometrie geprüft fände es niemals einen Partner und wäre
    nach der ersten Operation fort.
    """
    import dataclasses

    mesh = one_hole_plate()
    bore = next(iter(holes_of(mesh).values()))
    thread = dataclasses.replace(bore, id="op7.thread_1", kind="thread", provenance="generated")

    features, findings = _carried(mesh, {"op7.thread_1": thread})

    assert "op7.thread_1" in features, "an unseeable kind is carried, not judged"
    assert features["op7.thread_1"].kind == "thread"
    assert not [entry for entry in findings if entry.code == "perceive.generated_lost"]


def test_mirroring_keeps_the_pin_that_an_operation_made() -> None:
    """Die Spiegelung meldet ihre Matrix, also ist der Stift danach derselbe
    Stift — eine Passung darauf bleibt gültig (§14).
    """
    import dataclasses

    from app.core.geom.ops import as_transform
    from app.core.geom.transform import scaling
    from app.core.perceive.features import detect_pins
    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    plate = trimesh.creation.box(extents=(40.0, 20.0, 6.0))
    stud = trimesh.creation.cylinder(radius=2.0, height=10.0, sections=48)
    stud.apply_translation((12.0, 0.0, 5.0))
    body_with_pin = MeshData.of(trimesh.boolean.union([plate, stud]))
    pins = detect_pins(body_with_pin)
    assert pins, "the fixture must actually have a pin"
    previous = {"op3.pin_1": dataclasses.replace(pins[0], id="op3.pin_1", provenance="generated")}

    matrix = scaling((-1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
    entry = SceneObject(id="obj_1", name="Teil", mesh=apply(body_with_pin, matrix), features={})
    operation = Operation(
        id=2, op="mirror_object", inputs=("obj_1",), outputs=("obj_1",), params={}
    )
    result = _with_features(entry, previous, operation, lambda q, c: c[0], [], as_transform(matrix))

    assert "op3.pin_1" in result.features
    assert result.features["op3.pin_1"].provenance == "generated"


def test_apply_mapping_keeps_every_field_of_a_feature() -> None:
    """``apply_mapping`` baute ein frisches ``Feature`` aus fünf von sieben
    Feldern — ``created_by`` und ``recognised`` fielen still weg.

    Dieselbe Falle wie in ``moved_features``, und der Kommentar dort warnt seit
    dem 23.08.2026 wörtlich davor. Hier fiel sie nie auf, weil ein erkanntes
    Merkmal ohnehin nie einen Erzeuger trug — es gab nichts zu verlieren. Seit
    §21.2 ihn eintragen kann, trägt es: Gemessen gingen sechs Merkmale mit
    ``created_by`` hinein und **null** kamen heraus.
    """
    from app.core.perceive.matching import MatchResult

    feature = Feature(
        id="fillet_1",
        kind="fillet",
        provenance="detected",
        params={"radius": 2.4},
        created_by=7,
        recognised=False,
    )

    kept = apply_mapping({"fillet_1": feature}, MatchResult())["fillet_1"]

    assert kept.created_by == 7, "der Erzeuger überlebt die Umbenennung"
    assert kept.recognised is False, "und die zweite der beiden vergessenen Angaben auch"
    assert kept.kind == "fillet"
    assert kept.params == {"radius": 2.4}


def test_apply_mapping_still_renames_to_the_surviving_identifier() -> None:
    """Und das Umbenennen selbst bleibt, wie es war — die Gegenprobe zum Test
    darüber: ``replace(feature, id=target)`` muss die **neue** Kennung tragen,
    nicht die alte des erkannten Merkmals.
    """
    from app.core.perceive.matching import MatchResult

    feature = Feature(id="hole_2", kind="hole", provenance="detected", params={})
    result = MatchResult(mapping={"hole_1": "hole_2"})

    renamed = apply_mapping({"hole_2": feature}, result)

    assert set(renamed) == {"hole_1"}, "das neue Merkmal erbt den alten Namen"
    assert renamed["hole_1"].id == "hole_1", "und trägt ihn auch in sich"


# --- Welche Schraube zu einer gemessenen Bohrung gehört --------------------------
#
# Dieselbe Denkfigur wie ``question_for`` weiter oben, nur an einem Maß statt an
# einem Namen: Was sich nicht eindeutig zuordnen lässt, wird **gesagt und
# gefragt**, nicht geraten (Regel 21). Deshalb stehen diese Fälle hier und nicht
# bei den Vorbelegungen — geprüft wird die Zuordnung samt ihrem Ausgang, wenn
# keine passt.
#
# Der Anlass ist gemessen (23.08.2026, ``plate_holes.stl``, Bohrung ``hole_1``):
# Ein Klick auf eine 5,19-mm-Bohrung schlug **M3** vor. M3 bohrt 4,00 mm, liegt
# damit vollständig innerhalb der vorhandenen Bohrung und trägt nichts ab.


#: Die gemessene Bohrung aus dem gemeldeten Fall.
MEASURED_BORE = 5.19


def clicked_bore(diameter: float = MEASURED_BORE) -> Feature:
    """Eine angeklickte Durchgangsbohrung mit gemessenem Durchmesser."""
    return Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "diameter": diameter,
            "centre": (5.0, -5.0, 4.0),
            "axis": (0.0, 0.0, 1.0),
            "through": True,
        },
    )


def test_a_bore_belongs_to_the_screw_whose_clearance_hole_it_is() -> None:
    """Die **eine** Zuordnung: Nennmaß bis Durchgangsloch, aus der Tabelle.

    Zwei Schranken, beide fachlich: Unter dem Nennmaß geht die Schraube nicht
    hindurch, über dem Durchgangsloch ist die Bohrung weiter, als das Normmaß
    für diese Größe vorsieht. Beide stehen in derselben Zeile der
    Normteiltabelle — es gibt also keine zweite Konstante, die dieselbe Frage
    anders beantwortet, und zwischen zwei Größen liegt kein Bereich, in dem
    stillschweigend die eine gewinnt.
    """
    for size in standards.screw_sizes():
        entry = standards.screw(size)
        assert screw_for_bore(entry.nominal) == size, f"{size} geht durch ihr eigenes Nennmaß"
        assert screw_for_bore(entry.clearance) == size, f"{size} passt in ihr Durchgangsloch"

    assert standards.screw("M5").nominal <= MEASURED_BORE <= standards.screw("M5").clearance, (
        "Grundlage des gemeldeten Falls: 5,19 mm liegt zwischen 5,00 und 5,50"
    )
    assert screw_for_bore(MEASURED_BORE) == "M5"


def test_a_countersink_takes_the_head_of_that_screw_and_never_the_bore() -> None:
    """Eine Senkung **sitzt auf** der Bohrung — sie nimmt den Schraubenkopf.

    Der gemessene Durchmesser wäre dort eine falsche Zahl, die wie eine
    gemessene aussieht; die Schraube dagegen folgt aus ihm. Aus 5,19 mm wird
    also nicht 5,19, sondern der Senkkopf der M5 aus der Tabelle.

    Vorher stand im Feld die Schemavorgabe — ein Kopf, der zu keiner Bohrung
    des Teils gehört, und niemand sagte es.
    """
    values = values_for(REGISTRY.get("countersink_hole"), clicked_bore())

    assert values["diameter"] == standards.screw("M5").countersink, (
        "der Senkkopf der Schraube, die durch diese Bohrung geht"
    )
    assert values["diameter"] != MEASURED_BORE, "die Bohrung ist nicht der Kopf"
    default = next(
        entry.default
        for entry in REGISTRY.get("countersink_hole").params.spec()
        if entry.name == "diameter"
    )
    assert values["diameter"] != default, "und auch nicht mehr die Schemavorgabe"


def test_an_insert_replaces_the_bore_and_so_takes_its_measurement() -> None:
    """Eine Einpressbuchse **ersetzt** die Bohrung — sie darf sie übernehmen.

    Die Gegenprobe zum Test darüber, und der eigentliche gemeldete Fehler:
    Gewählt wird die kleinste Buchse, die die vorhandene Bohrung noch
    *aufweitet*. Eine kleinere schneidet vollständig innerhalb und trägt
    nichts ab — genau das tat die Vorgabe M3 mit ihren 4,00 mm.
    """
    values = values_for(REGISTRY.get("insert_heatset_m4"), clicked_bore())

    assert values["size"] == "M4"
    assert standards.insert("M4").hole >= MEASURED_BORE, "M4 weitet die Bohrung auf"
    assert standards.insert("M3").hole < MEASURED_BORE, (
        "M3 läge vollständig darin und trüge nichts ab"
    )


def test_a_bore_between_two_sizes_is_named_and_asked_about() -> None:
    """Wo keine Größe passt, wird der Durchmesser genannt und gefragt.

    4,75 mm ist weiter als das Durchgangsloch der M4 (4,50) und enger als das
    Nennmaß der M5 (5,00). Eine der beiden zu wählen wäre geraten; keine zu
    nennen wäre ein stiller Vorschlag über ein leeres Feld.
    """
    between = 4.75
    assert standards.screw("M4").clearance < between < standards.screw("M5").nominal, (
        "der Fall dieses Tests: zwischen zwei Größen"
    )

    assert screw_for_bore(between) is None, "keine Größe wird herbeigerundet"

    text, choices = bore_advice(between)

    assert "4.75" in text, "der Kunde liest, was gemessen wurde"
    assert choices[:2] == ["M4", "M5"], "die beiden Nachbarn, in dieser Reihenfolge"
    assert len(choices) == 3, "und ein Ausweg, der keine Größe behauptet"

    values = values_for(REGISTRY.get("countersink_hole"), clicked_bore(between))
    assert "diameter" not in values, "ohne Zuordnung wird auch kein Kopf eingetragen"


def test_the_measured_diameter_is_said_out_loud() -> None:
    """Der Kern kennt den Durchmesser — also nennt er ihn.

    Das war der zweite Teil des Befunds: Die Anwendung wusste, dass die Bohrung
    5,19 mm misst, und schlug wortlos etwas anderes vor. Wo eine Größe passt,
    ist die Auskunft ein Satz und keine Frage; zu fragen, was ohnehin feststeht,
    wäre eine Rückfrage ohne Mehrdeutigkeit.
    """
    text, choices = bore_advice(MEASURED_BORE)

    assert "5.19" in text, "das gemessene Maß steht im Satz"
    assert "M5" in text, "und die Größe, die daraus folgt"
    assert not choices, "wo eine Größe passt, gibt es nichts zu fragen"


def test_no_bore_falls_between_the_two_answers() -> None:
    """Kein toter Bereich: Jede Bohrung bekommt eine Größe **oder** eine Frage.

    Die Lehre „zwei Schwellen, eine Frage": Entscheiden zwei Konstanten
    dasselbe, liegt dazwischen ein Bereich, in dem beide Antworten falsch sind.
    Hier entscheidet eine Funktion, und ihr Ausgang ist an jeder Stelle
    entweder eine Größe oder eine Rückfrage — nie beides und nie keines.
    """
    for tenth in range(10, 121):
        diameter = tenth / 10.0
        size = screw_for_bore(diameter)
        text, choices = bore_advice(diameter)

        assert format_length(diameter, with_unit=False) in text, (
            f"das Maß {diameter} fehlt in seiner eigenen Auskunft"
        )
        assert bool(choices) == (size is None), (
            f"bei {diameter} mm wird {'gefragt und zugeordnet' if size else 'weder noch'}"
        )
        if size is not None:
            assert size in text, f"{diameter} mm gehört zu {size}, und der Satz sagt es"
