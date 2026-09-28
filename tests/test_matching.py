"""Stabile Merkmalsbezeichner, und was passiert, wenn sie es nicht sein
können (§21.2, §21.3).
"""

from __future__ import annotations

from dataclasses import replace
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


def test_transform_carries_measure_sources_only_with_proved_form_values() -> None:
    """Ein Kreisfit bleibt geschätzt; eine Ellipse bekommt keine alte Kreis-Zusage."""
    from app.core.perceive.matching import transformed_features
    from app.core.types import measure_status

    feature = Feature(
        "bore",
        "hole",
        "generated",
        {"diameter": 8.0, "depth": 4.0, "centre": (1.0, 2.0, 3.0), "axis": (0.0, 0.0, 1.0)},
        measure_sources={"diameter": "fit", "depth": "facets", "centre": "fit", "axis": "fit"},
    )
    scaled = transformed_features({"bore": feature}, np.diag([2.0, 2.0, 3.0, 1.0]))
    assert scaled.exact == {"bore"}
    assert scaled.candidates["bore"].params["diameter"] == pytest.approx(16.0)
    assert measure_status(scaled.candidates["bore"], "diameter").state == "estimated"
    ellipse = transformed_features({"bore": feature}, np.diag([2.0, 3.0, 3.0, 1.0]))
    assert not ellipse.exact
    assert measure_status(ellipse.candidates["bore"], "diameter").state == "unknown"
    assert measure_status(feature, "diameter").state == "estimated"


def test_renamed_fit_keeps_its_measure_source_from_the_new_geometry() -> None:
    """Ein geerbter Erzeuger macht einen neu gemessenen Wert nicht zum Vorgabemaß."""
    from app.core.perceive.matching import MatchResult
    from app.core.types import measure_status

    old = Feature(
        "made_bore",
        "hole",
        "generated",
        {"diameter": 8.0},
        created_by=3,
        measure_sources={"diameter": "parameter"},
    )
    found = Feature(
        "hole_1", "hole", "detected", {"diameter": 8.02}, measure_sources={"diameter": "fit"}
    )
    mapped = apply_mapping(
        {"hole_1": found}, MatchResult(mapping={"made_bore": "hole_1"}), previous={"made_bore": old}
    )["made_bore"]
    assert mapped.created_by == 3
    assert mapped.params["diameter"] == pytest.approx(8.02)
    assert measure_status(mapped, "diameter").state == "estimated"


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


@pytest.mark.parametrize("kind", ["hole", "pin", "fillet", "slot", "thread"])
def test_matching_keeps_the_new_axis_measurement_with_the_previous_direction(kind: str) -> None:
    """Die Orientierung reist mit, eine tatsächliche Änderung der Achslage bleibt messbar."""
    old = Feature(
        id="hole_old",
        kind=kind,
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 5.0},
    )
    measured = (0.01, 0.0, -float(np.sqrt(1.0 - 0.01**2)))
    new = Feature(
        id="hole_new",
        kind=kind,
        provenance="detected",
        params={**old.params, "axis": measured},
    )
    result = match({old.id: old}, {new.id: new}, (0.0, 0.0, 0.0), 20.0)

    mapped = apply_mapping({new.id: new}, result, previous={old.id: old})

    np.testing.assert_allclose(mapped[old.id].params["axis"], -np.asarray(measured))
    assert old.params["axis"] == (0.0, 0.0, 1.0)
    assert new.params["axis"] == measured


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


def test_recognition_and_ids_survive_printer_and_material_changes(document, profile) -> None:
    """Fertigungsprofile ändern die Analyse, niemals die erkannte Modellgeometrie."""
    from app.core.perceive.features import forget_cache
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    History(document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    sources = ProjectSources(project)
    before = evaluate(document, profile, sources=sources)
    assert before.complete
    features = before.scene.objects["obj_1"].features
    assert any(feature.kind == "hole" for feature in features.values())
    for width in (0.26, 0.84):
        changed = replace(
            profile,
            printer=replace(profile.printer, nozzle_diameter=width, extrusion_width=width),
            material=replace(profile.material, clearance=width),
        )
        forget_cache()
        after = evaluate(document, changed, sources=sources)
        assert after.complete
        assert after.scene.objects["obj_1"].features == features


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


@pytest.mark.parametrize("angle", [180.0, 127.0])
def test_the_evaluated_bore_direction_travels_through_a_rigid_rotation(
    document, profile, angle: float
) -> None:
    """Eine gedrehte Mündung folgt dem Körper auch jenseits einer halben Vierteldrehung."""
    from app.core.geom.transform import rotation
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    history = History(document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    before = evaluate(document, profile, sources=sources)
    assert before.complete
    old_axes = {
        name: tuple(feature.params["axis"])
        for name, feature in before.scene.objects["obj_1"].features.items()
        if feature.kind == "hole"
    }
    assert len(old_axes) == 4
    history.apply(
        "Drehen",
        [
            OperationDraft(
                op="rotate_object", inputs=("obj_1",), params={"axis": "x", "angle": angle}
            )
        ],
    )

    after = evaluate(document, profile, sources=sources)

    assert after.complete
    turn = rotation("x", angle)[:3, :3]
    for name, axis in old_axes.items():
        np.testing.assert_allclose(
            after.scene.objects["obj_1"].features[name].params["axis"],
            turn @ np.asarray(axis),
            atol=1e-8,
        )
        assert before.scene.objects["obj_1"].features[name].params["axis"] == axis


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
    monkeypatch.setattr(evaluation, "detect", lambda _mesh, **_kwargs: {})
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
    monkeypatch.setattr(evaluation, "detect", lambda _mesh, **_kwargs: {})
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


def test_a_moved_twin_takes_its_features_from_the_memory(monkeypatch) -> None:
    """Verschieben und Drehen rechnen die Erkennung nicht neu (§21.2, §31).

    Bis zum 22.09.2026 lief ``detect`` am bewegten Netz vollständig — 1,3 s an
    204 000 Dreiecken je Schritt —, und die Zuordnung fand danach heraus, dass
    alles beim Alten war. Jetzt überträgt ``carry_detection`` den Merker des
    Eingangs auf den bewegten Zwilling, und ``detect`` trifft. Gemessen wird
    am Kern der Erkennung: Läuft er trotzdem, ist die Übertragung ausgefallen.
    """
    import importlib

    from app.core.geom.transform import rotation
    from app.core.perceive.features import carry_detection, detect, forget_cache

    features = importlib.import_module("app.core.perceive.features")
    forget_cache()
    mesh = body("plate_holes.stl")
    known = detect(mesh)
    assert len(known) == 10

    matrix = rotation("z", 40.0) @ translation((12.0, -7.5, 3.0))
    moved = apply(mesh, matrix)
    cells = tuple(tuple(float(value) for value in row) for row in matrix)
    assert carry_detection(mesh, moved, cells)

    def never(*_args, **_kwargs):
        raise AssertionError("die Erkennung darf am bewegten Zwilling nicht rechnen")

    monkeypatch.setattr(features, "_large_facet_faces", never)
    found = detect(moved)

    assert set(found) == set(known)
    for name, feature in known.items():
        carried = found[name]
        assert carried.kind == feature.kind
        assert carried.face_indices == feature.face_indices, "dieselben Dreiecke"
        if "centre" in feature.params:
            expected = matrix[:3, :3] @ np.asarray(feature.params["centre"]) + matrix[:3, 3]
            assert np.allclose(carried.params["centre"], expected, atol=1e-6)
        if "diameter" in feature.params:
            assert carried.params["diameter"] == pytest.approx(feature.params["diameter"])


def test_carrying_needs_the_proof_not_the_promise() -> None:
    """Ohne Beleg wird nichts übertragen: andere Dreiecke, Skalierung, kein Merker."""
    from app.core.geom.transform import scaling
    from app.core.perceive.features import carry_detection, detect, forget_cache

    forget_cache()
    mesh = body("plate_holes.stl")
    shift = translation((5.0, 0.0, 0.0))
    cells = tuple(tuple(float(value) for value in row) for row in shift)
    # Kein Eintrag im Merker: nichts zu übertragen.
    assert not carry_detection(mesh, apply(mesh, shift), cells)
    detect(mesh)
    # Eine Skalierung ist keine starre Bewegung.
    grown = scaling((2.0, 2.0, 2.0))
    assert not carry_detection(
        mesh, apply(mesh, grown), tuple(tuple(float(v) for v in row) for row in grown)
    )
    # Dieselbe Matrix, aber ein anderes Netz dahinter.
    other = body("cube_clean.stl")
    assert not carry_detection(mesh, apply(other, shift), cells)
    # Die Matrix stimmt nicht mit der Lage der Ecken überein.
    elsewhere = apply(mesh, translation((5.0, 1.0, 0.0)))
    assert not carry_detection(mesh, elsewhere, cells)
    # Und mit Beleg geht es.
    assert carry_detection(mesh, apply(mesh, shift), cells)


def test_the_evaluation_carries_features_across_a_translation(profile) -> None:
    """Der Weg durch die Auswertung: Verschieben erkennt nicht neu, die Namen bleiben."""
    import importlib

    from app.core.perceive.features import forget_cache
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    features = importlib.import_module("app.core.perceive.features")
    forget_cache()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    first = evaluate(project.document, profile, sources=sources)
    body_id = project.document.ops[-1].outputs[0]
    before = first.scene.objects[body_id].features
    assert len(before) == 10

    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(body_id,), params={"dx": 10.0, "dy": 5.0})],
    )
    runs: list[int] = []
    original = features._large_facet_faces

    def counted(*args, **kwargs):
        runs.append(1)
        return original(*args, **kwargs)

    features._large_facet_faces = counted
    try:
        second = evaluate(project.document, profile, sources=sources)
    finally:
        features._large_facet_faces = original

    assert second.stopped_at is None
    after = second.scene.objects[project.document.ops[-1].outputs[0]].features
    assert set(after) == set(before), "dieselben Namen nach dem Verschieben"
    assert runs == [], "die Erkennung lief am bewegten Netz nicht noch einmal"
    for name, feature in before.items():
        if "centre" in feature.params:
            expected = np.asarray(feature.params["centre"]) + np.asarray((10.0, 5.0, 0.0))
            assert np.allclose(after[name].params["centre"], expected, atol=1e-6)


def _same_surface(before: MeshData, after: MeshData, old: Feature, new: Feature) -> None:
    """Das übertragene Merkmal deckt dieselbe Fläche wie das alte — nur feiner geteilt."""
    assert new.kind == old.kind
    assert dict(new.params) == dict(old.params), "die Oberfläche ist dieselbe, also die Maße"
    old_area = float(np.asarray(before.raw.area_faces)[list(old.face_indices)].sum())
    new_area = float(np.asarray(after.raw.area_faces)[list(new.face_indices)].sum())
    assert new_area == pytest.approx(old_area, rel=1e-9)
    assert len(new.face_indices) >= len(old.face_indices)


def test_a_refined_twin_takes_its_features_from_the_memory(monkeypatch) -> None:
    """*Kanten verfeinern* rechnet die Erkennung nicht neu (§21.2, §31).

    Das Verfeinern verschiebt keinen Punkt, es teilt nur; jedes neue Dreieck
    liegt in seinem alten. Bis zum 25.09.2026 lief die Erkennung am feineren
    Netz trotzdem vollständig — und über der Grenze der Vollerkennung wurde
    jedes bekannte Merkmal örtlich nachgemessen: am Bohrmaschinenhalter bei
    0,5 mm 317 Merkmale in 644 s, und am Ende hieß es „nicht mehr
    wiederzuerkennen". Jetzt trägt der Merker jedes Merkmal über die Herkunft
    seiner Dreiecke weiter.
    """
    import importlib

    from app.core.geom.mesh_ops import remesh
    from app.core.perceive.features import (
        carry_refined_detection,
        detect,
        forget_cache,
        refined_twin,
    )

    features = importlib.import_module("app.core.perceive.features")
    forget_cache()
    mesh = body("plate_holes.stl")
    known = detect(mesh)
    assert len(known) == 10

    refined = remesh(mesh, 2.0)
    origin = refined_twin(mesh, refined)
    assert origin is not None, "das verfeinerte Netz trägt seine Herkunft"
    assert carry_refined_detection(mesh, refined, origin)

    def never(*_args, **_kwargs):
        raise AssertionError("die Erkennung darf am verfeinerten Zwilling nicht rechnen")

    monkeypatch.setattr(features, "_large_facet_faces", never)
    found = detect(refined)

    assert set(found) == set(known)
    for name, feature in known.items():
        _same_surface(mesh, refined, feature, found[name])


def test_a_refinement_needs_the_proof_not_the_note() -> None:
    """Der Vermerk der Operation allein trägt nichts: anderes Netz, fremde Herkunft, geändert."""
    from app.core.geom.mesh_ops import remesh
    from app.core.perceive.features import note_refinement, refined_twin

    mesh = body("plate_holes.stl")
    refined = remesh(mesh, 2.0)
    origin = refined_twin(mesh, refined)
    assert origin is not None

    # Ein anderes Netz als Quelle.
    assert refined_twin(body("cube_clean.stl"), refined) is None
    # Eine Herkunft, die nicht stimmt: jedes Dreieck dem Nachbarn zugeschrieben.
    forged = remesh(mesh, 2.0)
    note_refinement(mesh, forged, np.roll(origin, 1))
    assert refined_twin(mesh, forged) is None
    # Ein Netz ohne Vermerk.
    plain = MeshData.of(refined.raw.copy())
    assert refined_twin(mesh, plain) is None
    # Und ein Netz, das nach dem Vermerk verändert wurde, verliert ihn.
    moved = refined.raw.copy(include_cache=True)
    moved.vertices = np.asarray(moved.vertices) + np.array([0.0, 0.0, 1.0])
    assert refined_twin(mesh, MeshData.of(moved)) is None


@pytest.mark.parametrize("above_the_limit", [False, True])
def test_the_evaluation_carries_features_across_a_refinement(
    profile, monkeypatch, above_the_limit: bool
) -> None:
    """Der Weg durch die Auswertung, unter und über der Grenze der Vollerkennung.

    Darunter trifft ``detect`` den Merker, darüber gelten die übertragenen
    Merkmale als stehend und werden nicht örtlich nachgemessen. In beiden
    Fällen bleiben Namen und Maße.
    """
    import importlib

    from app.core.perceive import local
    from app.core.perceive.features import forget_cache
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    features = importlib.import_module("app.core.perceive.features")
    evaluation = importlib.import_module("app.core.scene.evaluate")
    forget_cache()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    first = evaluate(project.document, profile, sources=sources)
    body_id = project.document.ops[-1].outputs[0]
    source_mesh = first.scene.objects[body_id].mesh
    before = first.scene.objects[body_id].features
    assert len(before) == 10

    history.apply(
        "Verfeinern",
        [OperationDraft(op="remesh_mesh", inputs=(body_id,), params={"edge": 2.0})],
    )
    if above_the_limit:
        # Der Eingang liegt darunter, das feinere Netz darüber.
        monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", source_mesh.triangle_count)
        monkeypatch.setattr(
            local, "_recognise_region", lambda *_a, **_k: pytest.fail("örtlich nachgemessen")
        )
    runs: list[int] = []
    original = features._large_facet_faces

    def counted(*args, **kwargs):
        runs.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(features, "_large_facet_faces", counted)
    second = evaluate(project.document, profile, sources=sources)

    assert second.stopped_at is None
    output = second.scene.objects[project.document.ops[-1].outputs[0]]
    assert output.mesh.triangle_count > source_mesh.triangle_count
    assert set(output.features) == set(before), "dieselben Namen nach dem Verfeinern"
    assert runs == [], "die Erkennung lief am verfeinerten Netz nicht noch einmal"
    for name, feature in before.items():
        _same_surface(source_mesh, output.mesh, feature, output.features[name])
    codes = {finding.code for finding in second.scene.report.findings}
    assert "perceive.orphaned" not in codes


@pytest.mark.parametrize("above_the_limit", [False, True])
def test_a_refinement_keeps_its_features_when_the_project_is_opened_again(
    profile, monkeypatch, tmp_path, above_the_limit: bool
) -> None:
    """Nach dem Wiederöffnen trägt der geteilte Körper dieselben Merkmale wie in der Sitzung.

    Der Vermerk, aus welchem Dreieck jedes neue stammt, lag nur im Speicher
    des Netzes. Kam das feinere Netz beim Öffnen von der Platte, fehlte er:
    Die Erkennung lief am feineren Netz neu und las dort etwas anderes — am
    Screen-Cover nach 1 mm statt einer gerundeten Seite 45 Verrundungen,
    72 Namen zeigten auf andere Merkmale (Durchsicht 0.5.1, erkennung-02).
    Dasselbe Dokument ergab je nach Cache zwei Merkmalsstände (§15.1).
    """
    import importlib

    from app.core.geom.mesh import MeshCodec
    from app.core.perceive import local
    from app.core.perceive.features import forget_cache
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    features = importlib.import_module("app.core.perceive.features")
    evaluation = importlib.import_module("app.core.scene.evaluate")
    forget_cache()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    body_id = project.document.ops[-1].outputs[0]
    history.apply(
        "Verfeinern",
        [OperationDraft(op="remesh_mesh", inputs=(body_id,), params={"edge": 2.0})],
    )
    if above_the_limit:
        # Der Eingang liegt darunter, das feinere Netz darüber.
        monkeypatch.setattr(
            evaluation, "FEATURE_LIMIT_TRIANGLES", body("plate_holes.stl").triangle_count
        )
        monkeypatch.setattr(
            local, "_recognise_region", lambda *_a, **_k: pytest.fail("örtlich nachgemessen")
        )
    folder = tmp_path / "ergebnisse"
    first = evaluate(
        project.document,
        profile,
        sources=sources,
        cache=ResultCache(disk=DiskCache(codec=MeshCodec(), directory=folder)),
    )
    assert first.stopped_at is None
    output_id = project.document.ops[-1].outputs[0]
    in_session = first.scene.objects[output_id]
    assert len(in_session.features) == 10

    # Wiederöffnen: Merker leer, der Speicher des Caches leer, die Platte voll.
    forget_cache()
    examined: list[int] = []
    original = features._large_facet_faces

    def counted(body, *args, **kwargs):
        examined.append(len(body.faces))
        return original(body, *args, **kwargs)

    monkeypatch.setattr(features, "_large_facet_faces", counted)
    reopened_cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=folder))
    second = evaluate(project.document, profile, sources=sources, cache=reopened_cache)

    assert reopened_cache.statistics.disk_hits == 2, "beide Schritte kommen von der Platte"
    reopened = second.scene.objects[output_id]
    assert reopened.mesh.triangle_count == in_session.mesh.triangle_count
    assert in_session.mesh.triangle_count not in examined, (
        "am feineren Netz lief die Erkennung nach dem Öffnen noch einmal"
    )
    assert set(reopened.features) == set(in_session.features)
    for name, feature in in_session.features.items():
        assert reopened.features[name].kind == feature.kind
        assert reopened.features[name].face_indices == feature.face_indices


def test_a_new_bore_keeps_its_place_after_a_changed_bore_took_the_last_name(profile) -> None:
    """Eine neue Bohrung verschwindet nicht, weil eine geänderte den nächsten Namen trägt (RM-222).

    *Bohrung ändern* gibt die geänderte Bohrung unter ihrem alten Namen selbst
    aus, und jeder Folgeschritt führt sie so weiter — neben der Zuordnung, an
    der Neuerkennung vorbei. Die Zuordnung kannte diesen Namen deshalb nicht
    als vergeben: Eine im nächsten Schritt neu gebohrte Bohrung bekam ihn als
    ersten freien, und beim Zusammenführen überschrieb die geänderte sie. Am
    Besenhalter fehlte so die Durchbohrung der Wand bei y = 0, sobald vorher
    eine andere Bohrung vergrößert worden war — dieselbe Geometrie in anderer
    Reihenfolge gebaut trug sie (Durchsicht 0.5.1, erkennung-06).
    """
    from app.core.perceive.features import forget_cache
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    forget_cache()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    body_id = project.document.ops[-1].outputs[0]
    loaded = evaluate(project.document, profile, sources=sources)
    holes = sorted(
        name
        for name, feature in loaded.scene.objects[body_id].features.items()
        if feature.kind == "hole"
    )
    assert holes == ["hole_1", "hole_2", "hole_3", "hole_4"]
    history.apply(
        "Vergrößern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=(body_id,),
                params={"at_feature": "hole_4", "diameter": 6.5, "compensate": False},
            )
        ],
    )
    history.apply(
        "Bohren",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(project.document.ops[-1].outputs[0],),
                params={
                    "x": 0.0,
                    "y": 0.0,
                    "z": 4.0,
                    "axis": "z",
                    "diameter": 4.0,
                    "depth": 0.0,
                    "compensate": False,
                },
                seed=11,
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)

    assert result.stopped_at is None
    body = result.scene.objects[project.document.ops[-1].outputs[0]]
    places = sorted(
        (round(float(feature.params["centre"][0]), 1), round(float(feature.params["centre"][1]), 1))
        for feature in body.features.values()
        if feature.kind == "hole"
    )
    assert (0.0, 0.0) in places, "die neu gebohrte Bohrung fehlt"
    assert len(places) == 5
    assert float(body.features["hole_4"].params["diameter"]) == pytest.approx(6.5, abs=0.05)


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
    *,
    needed: dict[str, tuple[str, ...]] | None = None,
) -> tuple[dict[str, Feature], list]:
    """``_with_features`` an einer Operation, die ``features={}`` zurückgibt.

    Elf Stellen unter ``app/core/geom/`` tun das, und keine von ihnen meint
    damit „die erzeugten Merkmale sind fort" — sie füllen das Feld nur nicht.
    ``needed`` ist, wer nach diesem Schritt noch auf ein Merkmal zeigt
    (``evaluate._needed_after``); ohne Angabe gilt ``referenced``.
    """
    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    def never(question: str, choices: list[str]) -> str:
        raise AssertionError(f"nothing here is ambiguous: {question}")

    entry = SceneObject(id="obj_1", name="Teil", mesh=mesh, features={})
    findings: list = []
    operation = Operation(id=4, op="thicken", inputs=("obj_1",), outputs=("obj_1",), params={})
    result = _with_features(
        entry, previous, operation, never, findings, referenced=referenced, needed=needed
    )
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
    assert not any("Anklicken" in str(entry.message) for entry in reported), (
        "Kern und Agent bekommen eine Feststellung, die UI ergänzt erst dort ihren Klickweg"
    )


def test_a_referenced_generated_feature_that_is_gone_is_a_warning() -> None:
    """Erst der Verweis macht aus dem Verlust ein Problem (§21.3)."""
    plate = one_hole_plate()
    bore = next(iter(holes_of(plate).values()))
    previous = {"op3.bore_1": _generated(bore, "op3.bore_1")}
    plugged = MeshData.of(trimesh.creation.box(extents=(60.0, 30.0, 8.0)))

    features, findings = _carried(plugged, previous, referenced={"op3.bore_1"})

    reported = [entry for entry in findings if entry.values.get("feature") == "op3.bore_1"]
    assert "op3.bore_1" not in features, "die Karte dürfte sonst nur ein Phantom markieren"
    assert [entry.code for entry in reported] == ["perceive.generated_lost"]
    assert [entry.severity for entry in reported] == ["warning"]


def test_a_referenced_detected_feature_that_is_gone_names_its_step() -> None:
    """Auch ein **erkanntes** Merkmal, auf das eine Passung zeigt, meldet seinen Verlust (RM-189).

    Robert, 18.09.2026: „Eine Passung verweist auf ein Merkmal, das es nicht
    mehr gibt … alles sollte korrekt übernommen werden." Nachgestellt am
    Bohrhalter (``drill-holder.3mf``): Eine Passung zwischen zwei Bohrungen,
    danach *Glätten* mit zwei Durchgängen — alle 29 Bohrungen sind danach keine
    Zylinder mehr und nicht mehr erkennbar; stark *Dreiecke verringern* verliert
    sieben. Der Verlust ist echt, und der Bericht nannte nur die Passung
    („eine Operation danach hat den Körper neu gebaut") und nicht den
    Schritt, der ihn verursacht hat: Der Verlust eines erkannten Merkmals war
    eine stille Feststellung, auch wenn eine Passung darauf zeigte. Jetzt ist
    er eine Warnung am verursachenden Schritt, mit dem Weg dorthin.
    """
    from app.core.errors import CORRECT_INPUT

    plate = one_hole_plate()
    bore = next(iter(holes_of(plate).values()))
    plugged = MeshData.of(trimesh.creation.box(extents=(60.0, 30.0, 8.0)))

    _features, findings = _carried(plugged, {bore.id: bore}, referenced={bore.id})

    reported = [entry for entry in findings if entry.values.get("feature") == bore.id]
    assert [entry.severity for entry in reported] == ["warning"], [
        (entry.code, entry.severity) for entry in reported
    ]
    assert reported[0].op_id == 4, "der Befund nennt den Schritt, der es verloren hat"
    assert CORRECT_INPUT in reported[0].suggestions

    _features, quiet = _carried(plugged, {bore.id: bore})
    assert {entry.severity for entry in quiet if entry.values.get("feature") == bore.id} == {
        "info"
    }, "ohne Verweis bleibt es eine Feststellung"


def test_a_feature_only_its_own_step_names_is_not_reported_lost() -> None:
    """Was der Schritt selbst verbraucht, fehlt danach niemandem.

    *Fläche versetzen* nennt seine Fläche und verändert sie; danach ist sie
    oft nicht mehr dieselbe. Am Zylinder aus dem Piratenschiff-Satz
    (``obj_11_Cylinder_B.stl``) meldete jeder zweite Versatz „Ein Merkmal, auf
    das sich eine Passung oder ein späterer Schritt bezieht, ist nach diesem
    Schritt nicht mehr erkennbar" — ohne Passung, ohne späteren Schritt
    (23.09.2026, Nachmessung zu RM-128). Gezählt wird, wer **nach** dem
    Schritt noch zeigt (``_needed_after``), wie am exakten Körper.
    """
    plate = one_hole_plate()
    bore = next(iter(holes_of(plate).values()))
    plugged = MeshData.of(trimesh.creation.box(extents=(60.0, 30.0, 8.0)))

    _features, own = _carried(plugged, {bore.id: bore}, referenced={bore.id}, needed={})
    assert {entry.severity for entry in own if entry.values.get("feature") == bore.id} == {
        "info"
    }, [(entry.code, entry.severity) for entry in own]

    _features, later = _carried(
        plugged, {bore.id: bore}, referenced={bore.id}, needed={bore.id: ("stift_1",)}
    )
    reported = [entry for entry in later if entry.values.get("feature") == bore.id]
    assert [entry.severity for entry in reported] == ["warning"]
    assert reported[0].values.get("where") == "stift_1", "der Befund nennt, wer das Merkmal braucht"


def test_a_declared_feature_does_not_take_a_neighbour_far_from_where_it_was_put() -> None:
    """Was eine Operation selbst gesetzt hat, sucht seinen erkannten Partner an seiner Stelle.

    Die Zuordnung eines erklärten Merkmals zur Erkennung lief mit derselben
    Toleranz wie die zwischen zwei Schritten: 8 % der Modelldiagonale. Am
    Schraubenhalter mit Wabenmuster wanderte ``hole_1`` samt Senkung 1 mm
    entlang seiner Achse; die erklärte Senkung stand danach mit ihrem alten
    Durchmesser 1 mm vor der Wand, fand an ihrer Stelle keinen gleichen Kegel
    — und nahm die Senkung der **Nachbarbohrung** 18 mm daneben. ``cone_2``
    war danach verwaist, ohne dass jemand es angefasst hatte (23.09.2026,
    Namensprobe zum Verschieben, Drehen und Zurücknehmen).

    Nachgestellt: zwei Bohrungen Ø 4, 30 mm auseinander; der Schritt erklärt
    ``hole_1`` bei x = 22, wo keine Bohrung ist. Die nächste steht 8 mm weiter —
    innerhalb der Schritt-Toleranz, aber zwei Durchmesser vom erklärten Ort.
    """
    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    plate = trimesh.creation.box(extents=(100.0, 60.0, 10.0))
    for x in (0.0, 30.0):
        drill = trimesh.creation.cylinder(radius=2.0, height=40.0, sections=48)
        drill.apply_translation((x, 0.0, 0.0))
        plate = trimesh.boolean.difference([plate, drill])
    mesh = MeshData.of(plate)
    before = {round(float(hole.params["centre"][0])): hole for hole in holes_of(mesh).values()}
    left = replace(before[0], id="hole_1")
    right = replace(before[30], id="hole_2")
    declared = replace(
        left,
        provenance="generated",
        params={**left.params, "centre": (22.0, 0.0, float(left.params["centre"][2]))},
        face_indices=(),
        surface_patches=(),
    )

    def never(question: str, choices: list[str]) -> str:
        raise AssertionError(f"nothing here is ambiguous: {question}")

    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features={"hole_1": declared})
    findings: list = []
    operation = Operation(id=4, op="thicken", inputs=("obj_1",), outputs=("obj_1",), params={})
    result = _with_features(
        entry,
        {"hole_1": left, "hole_2": right},
        operation,
        never,
        findings,
        referenced={"hole_2"},
    )

    assert "hole_2" in result.features, [(entry.code, entry.values) for entry in findings]
    assert float(result.features["hole_2"].params["centre"][0]) == pytest.approx(30.0, abs=0.1)
    assert not [
        entry
        for entry in findings
        if entry.code in ("perceive.orphaned", "perceive.referenced_lost")
        and entry.values.get("feature") == "hole_2"
    ]


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


@pytest.mark.parametrize("recognised", [True, False])
@pytest.mark.parametrize("declared", [True, False])
@pytest.mark.parametrize("local", [True, False])
@pytest.mark.parametrize("factors", [(2.0, 2.0, 2.0), (1.0, 1.0, 2.0), (2.0, 1.0, 1.0)])
def test_scaling_generated_bores_keeps_only_current_circular_measures(
    recognised: bool,
    declared: bool,
    local: bool,
    factors: tuple[float, float, float],
    monkeypatch,
) -> None:
    """Erzeuger und Name bleiben; aus einem Kreis wird bei Querstreckung eine Ellipse."""
    from app.core.geom.ops import as_transform
    from app.core.geom.transform import scaling
    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    if local:
        import importlib

        monkeypatch.setattr(
            importlib.import_module("app.core.scene.evaluate"), "FEATURE_LIMIT_TRIANGLES", 1
        )
    mesh = one_hole_plate()
    bore = next(iter(holes_of(mesh).values()))
    named = replace(
        bore, id="made_bore", provenance="generated", recognised=recognised, created_by=2
    )
    previous = {named.id: named}
    matrix = scaling(factors)
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=apply(mesh, matrix), features=previous if declared else {}
    )
    operation = Operation(id=4, op="scale_object", inputs=("obj_1",), outputs=("obj_1",), params={})
    findings = []
    result = _with_features(
        entry,
        previous,
        operation,
        lambda q, c: c[0],
        findings,
        as_transform(matrix),
        referenced={named.id},
    )
    if factors[0] != factors[1]:
        assert named.id not in result.features, "an ellipse cannot keep the old circular bore"
        assert any(f.code == "perceive.generated_lost" for f in findings)
        return
    current = result.features[named.id]
    assert current.provenance == "generated"
    assert current.created_by == 2
    assert current.params["diameter"] == pytest.approx(bore.params["diameter"] * factors[0])
    assert current.params["depth"] == pytest.approx(bore.params["depth"] * factors[2])
    assert len([f for f in result.features.values() if f.kind == "hole"]) == 1


def test_affine_feature_normals_follow_the_plane_and_opening() -> None:
    """Scherung und Achsskalierung: Flächennormalen stehen weiter senkrecht auf der Fläche."""
    from app.core.geom.ops import as_transform
    from app.core.perceive.matching import transformed_features

    normal = tuple(np.array((1.0, 1.0, 0.0)) / np.sqrt(2.0))
    feature = Feature(
        id="seat",
        kind="face",
        provenance="generated",
        created_by=3,
        params={
            "centre": (1.0, 2.0, 3.0),
            "normal": normal,
            "area": np.sqrt(2.0),
            "opening_normal": normal,
            "profile_clamp_y": (0.0, 0.0, 1.0),
        },
    )
    matrix = np.array(
        ((2.0, 0.0, 0.0, 7.0), (1.0, 1.0, 0.0, -4.0), (0.0, 0.0, 3.0, 2.0), (0.0, 0.0, 0.0, 1.0))
    )
    result = transformed_features({feature.id: feature}, as_transform(matrix))
    moved = result.candidates[feature.id]
    # Die ursprünglichen Kanten (1,-1,0) und (0,0,1) werden zu (2,0,0) und (0,0,3).
    for key in ("normal", "opening_normal"):
        assert moved.params[key] == pytest.approx((0.0, 1.0, 0.0), abs=1e-12)
    assert moved.params["area"] == pytest.approx(6.0)
    assert moved.params["centre"] == pytest.approx((9.0, -1.0, 11.0))
    assert moved.params["profile_clamp_y"] == pytest.approx((0.0, 0.0, 1.0))
    assert feature.id in result.exact
    assert feature.params["normal"] == normal
    assert feature.params["centre"] == (1.0, 2.0, 3.0)


def test_anisotropic_face_diameter_is_not_an_exact_circular_fit() -> None:
    """Ein ebener Deckelsitz bleibt eben, sein Kreis wird bei Querstreckung elliptisch."""
    from app.core.geom.ops import as_transform
    from app.core.geom.transform import scaling
    from app.core.perceive.matching import transformed_features

    feature = Feature(
        id="neck",
        kind="face",
        provenance="generated",
        params={
            "centre": (0.0, 0.0, 0.0),
            "normal": (0.0, 0.0, 1.0),
            "area": 100.0,
            "diameter": 10.0,
            "fit_role": "outer",
        },
    )
    result = transformed_features({feature.id: feature}, as_transform(scaling((2.0, 1.0, 1.0))))
    assert feature.id not in result.exact


@pytest.mark.parametrize("factors", [(2.0, 2.0, 2.0), (-2.0, 2.0, 2.0), (2.0, 2.0, 3.0)])
def test_cylinder_mesh_band_follows_the_actual_radial_scale(factors: tuple[float, ...]) -> None:
    """Kreisbewahrende Abbildungen führen Fitfehler und Netzband als Längen mit."""
    from app.core.geom.ops import as_transform
    from app.core.geom.transform import scaling
    from app.core.perceive.matching import transformed_features

    feature = Feature(
        id="bore",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 30.0,
            "depth": 8.0,
            "fit_error": 0.001,
            "residual": 0.001 / 15.0,
            "radial_min": 14.7,
            "radial_max": 15.0,
        },
    )
    result = transformed_features({feature.id: feature}, as_transform(scaling(factors)))
    assert feature.id in result.exact
    params = result.candidates[feature.id].params
    assert params["fit_error"] == pytest.approx(0.002)
    assert params["residual"] == pytest.approx(0.001 / 15.0)
    assert params["radial_min"] == pytest.approx(29.4)
    assert params["radial_max"] == pytest.approx(30.0)
    assert params["depth"] == pytest.approx(8.0 * factors[2])
    assert feature.params["radial_min"] == 14.7


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


def test_a_matched_feature_keeps_its_original_maker_after_new_detection() -> None:
    """Neu erkannte Dreiecke ersetzen die Formdaten, nicht die belegte Herkunft."""
    from app.core.perceive.matching import MatchResult

    previous = Feature(
        id="old",
        kind="face",
        provenance="detected",
        params={"area": 10.0},
        created_by=4,
        face_indices=(0,),
    )
    fresh = Feature(
        id="fresh", kind="face", provenance="detected", params={"area": 12.0}, face_indices=(3, 4)
    )
    kept = apply_mapping(
        {"fresh": fresh}, MatchResult(mapping={"old": "fresh"}), previous={"old": previous}
    )["old"]
    assert kept.created_by == 4
    assert kept.params["area"] == pytest.approx(12.0)
    assert kept.face_indices == (3, 4)
    # Gleicher Name allein belegt keine Nachfolge.
    unrelated = apply_mapping(
        {"old": replace(fresh, id="old")}, MatchResult(), previous={"old": previous}
    )["old"]
    assert unrelated.created_by is None


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

    4,90 mm ist weiter als das grobe Durchgangsloch der M4 (4,80) und enger
    als das Nennmaß der M5 (5,00). Eine der beiden zu wählen wäre geraten;
    keine zu nennen wäre ein stiller Vorschlag über ein leeres Feld.

    Bis zur Durchsicht 0.5.0 stand hier 4,75 mm — gemessen an der mittleren
    Reihe allein. Seit die Tabelle auch die grobe Reihe nach ISO 273 kennt,
    ist 4,75 mm das grobe Durchgangsloch der M4 und kein Fall mehr für diesen
    Test.
    """
    between = 4.9
    assert (
        (standards.screw("M4").clearance_coarse or 0.0) < between < standards.screw("M5").nominal
    ), "der Fall dieses Tests: zwischen zwei Größen"

    assert screw_for_bore(between) is None, "keine Größe wird herbeigerundet"

    text, choices = bore_advice(between)

    assert "4.90" in text, "der Kunde liest, was gemessen wurde"
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
    feature = replace(clicked_bore(), measure_sources={"diameter": "native"})
    text, choices = bore_advice(MEASURED_BORE, feature=feature)

    assert "5.19" in text, "das gemessene Maß steht im Satz"
    assert "M5" in text, "und die Größe, die daraus folgt"
    assert not choices, "wo eine Größe passt, gibt es nichts zu fragen"


def test_a_blind_bore_is_not_described_as_a_through_hole() -> None:
    """Ein passender Durchmesser belegt keinen Durchgang und keinen Einsatzzweck."""
    feature = replace(clicked_bore(9.0), measure_sources={"diameter": "native"})
    feature.params["through"] = False
    text, choices = bore_advice(9.0, feature=feature, ask=False)
    assert "Sackbohrung" in text
    assert "Durchgangsloch" not in text
    assert "9" in text and "M8" in text
    assert not choices


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
        feature = replace(clicked_bore(diameter), measure_sources={"diameter": "native"})
        text, choices = bore_advice(diameter, feature=feature)

        assert format_length(diameter, with_unit=False) in text, (
            f"das Maß {diameter} fehlt in seiner eigenen Auskunft"
        )
        assert bool(choices) == (size is None), (
            f"bei {diameter} mm wird {'gefragt und zugeordnet' if size else 'weder noch'}"
        )
        if size is not None:
            assert size in text, f"{diameter} mm gehört zu {size}, und der Satz sagt es"


@pytest.mark.parametrize("source", ["fit", "parameter", None])
def test_bore_advice_distinguishes_a_measurement_from_a_known_screw(source: str | None) -> None:
    """Ein gemessener Wert nennt die Größe als Einschätzung, nie als Tatsache.

    **Umgestellt in der Durchsicht 0.5.0.** Bis dahin schrieb dieser Test
    ``"M5" not in text`` fest: Eine Messung durfte gar keine Größe nennen, auch
    nicht an 5,19 mm, die nur ins Band der M5 fallen. Die Funktionsseite
    verspricht aber genau diesen Satz für eine fremde STL, und der Kunde
    bekam „nicht sicher bestimmt" und Nachbargrößen ohne die M5.

    Die Grenze zur Konstruktionsangabe bleibt: Die Messung sagt „vermutlich"
    und nennt ihre Herkunft in Klammern; die exakte Fläche sagt „das
    Durchgangsloch für" (``test_the_measured_diameter_is_said_out_loud``).
    """
    feature = replace(
        clicked_bore(),
        measure_sources={"diameter": source} if source else {},  # type: ignore[arg-type]
    )
    text, choices = bore_advice(MEASURED_BORE, feature=feature)
    qualifier = {
        "fit": "eingepasst",
        "parameter": "aus dem Schritt",
        None: "Maßherkunft nicht bestimmt",
    }
    assert qualifier[source] in text
    assert "5.19" in text and "Passt vermutlich zu M5 (Durchgangsloch fein)" in text
    assert "Durchgangsloch für" not in text, "eine Messung ist keine Konstruktionsangabe"
    assert "M5" in choices, f"die passende Größe fehlt unter den Antworten: {choices}"
    assert choices and choices[-1] == "Selbst eintragen"
    passive, choices = bore_advice(MEASURED_BORE, feature=feature, ask=False)
    assert qualifier[source] in passive and "vermutlich zu M5" in passive and not choices


def test_a_measured_bore_offers_its_own_size_among_the_answers() -> None:
    """An 5,19 mm fragte die Rückfrage nach M4 und M6 — die M5 fehlte.

    ``_sizes_around`` nannte nur die Nachbargrößen einer Bohrung, „die zu
    keiner passt", und wurde auch dort gefragt, wo sie passt. Rot bis zur
    Durchsicht 0.5.0.
    """
    feature = replace(clicked_bore(), measure_sources={"diameter": "fit"})

    _text, choices = bore_advice(MEASURED_BORE, feature=feature)

    assert choices == ["M4", "M5", "M6", "Selbst eintragen"]


def test_a_measured_bore_names_every_hole_it_may_be() -> None:
    """4,2 mm ist das feine Durchgangsloch der M4 und das Kernloch der M5.

    Eines davon zu nennen wäre geraten (Regel 21); beide stehen im Satz, in
    der Reihenfolge der Tabelle, und beide Größen unter den Antworten.
    """
    feature = replace(
        clicked_bore(4.2),
        measure_sources={"diameter": "fit"},
    )
    text, choices = bore_advice(4.2, feature=feature)

    assert "M4 (Durchgangsloch fein) oder M5 (Kernloch für Gewinde)" in text
    assert {"M4", "M5"} <= set(choices)


def test_a_measured_bore_outside_every_band_is_still_asked_about() -> None:
    """Zwischen den Bändern bleibt es bei der ehrlichen Frage.

    7,5 mm ist weiter als das grobe Durchgangsloch der M6 (7,0) und enger als
    das Nennmaß der M8 — keine Größe, kein Kernloch, also keine Einschätzung.
    """
    feature = replace(clicked_bore(7.5), measure_sources={"diameter": "fit"})

    text, choices = bore_advice(7.5, feature=feature)

    assert "nicht sicher bestimmt" in text and "vermutlich" not in text
    assert choices == ["M6", "M8", "Selbst eintragen"]


def test_the_measuring_uncertainty_comes_from_the_feature_and_nowhere_else() -> None:
    """Das Intervall nimmt Kreispassung und Netzband, und sonst nichts.

    4,95 mm liegt unter dem Nennmaß der M5 und über dem groben Loch der M4.
    Erst ein belegter Passungsfehler von 0,03 mm hebt das Intervall bis 5,01
    — dann kommt die M5 infrage, vorher nicht, und mit ihr das Kernloch der
    M6. Ein Vorgabemaß bleibt ein Punkt: Für ihn ist keine Messunsicherheit
    bekannt.
    """
    from app.core.scene.placement import BoreMatch, bore_matches, measured_interval
    from app.core.types import MeasureStatus

    fitted = MeasureStatus("estimated", "fit", available=True)
    plain = replace(clicked_bore(4.95), measure_sources={"diameter": "fit"})
    assert measured_interval(4.95, plain, fitted) == (4.95, 4.95)
    assert not bore_matches(4.95, 4.95)

    uncertain = replace(plain, params={**plain.params, "fit_error": 0.03, "radial_min": 2.46})
    low, high = measured_interval(4.95, uncertain, fitted)
    assert low == pytest.approx(4.92 - 0.06)
    assert high == pytest.approx(4.95 + 0.06)
    # Und mit ihr auch das Kernloch der M6: Es misst genau 5,00 mm.
    assert bore_matches(low, high) == (BoreMatch("M5", "fine"), BoreMatch("M6", "tap"))

    given = MeasureStatus("exact", "parameter", available=True)
    assert measured_interval(4.95, uncertain, given) == (4.95, 4.95)


def test_the_clearance_series_are_those_of_iso_273() -> None:
    """Feine, mittlere und grobe Reihe — gegen die Norm, nicht gegen die Tabelle.

    Abgeschrieben aus ISO 273 und nicht aus ``standards.toml``, sonst prüfte
    sich die Tabelle selbst.
    """
    iso_273 = {
        "M2": (2.2, 2.4, 2.6),
        "M2.5": (2.7, 2.9, 3.1),
        "M3": (3.2, 3.4, 3.6),
        "M4": (4.3, 4.5, 4.8),
        "M5": (5.3, 5.5, 5.8),
        "M6": (6.4, 6.6, 7.0),
        "M8": (8.4, 9.0, 10.0),
    }
    for size in standards.screw_sizes():
        entry = standards.screw(size)
        assert (entry.clearance_fine, entry.clearance, entry.clearance_coarse) == iso_273[size]


def test_a_coarse_clearance_hole_gets_the_head_of_its_screw() -> None:
    """5,7 mm ist das grobe Durchgangsloch der M5 — die Senkung nimmt ihren Kopf.

    Der Hinweis darüber sagt „Passt vermutlich zu M5 (Durchgangsloch grob)";
    ein leeres Feld darunter widerspräche ihm.
    """
    values = values_for(REGISTRY.get("countersink_hole"), clicked_bore(5.7))

    assert values["diameter"] == standards.screw("M5").countersink


def test_a_declared_pin_takes_the_twin_at_its_own_place() -> None:
    """Zwei erklärte Stifte, ein erkannter — er gehört dem, an dessen Stelle er steht.

    Gemessen am Auto-Split der Gabel (Durchsicht 0.5.1): Zwei Verbinderstifte
    16,6 mm auseinander an einem Körper mit 635 mm Diagonale lagen beide in der
    Toleranz der Zuordnung (8 % der Diagonale). Der eine erkannte Stift war
    damit umkämpft, keiner bekam ihn, er stand unter einem frischen Namen
    daneben, und die Nummer fehlte dem nächsten Verbinder: Zwei Passungen
    zeigten ins Leere. Der Stift steht 2,4 mm entlang der Achse versetzt — die
    Erkennung misst die Mitte des Mantels, der Verbinder seinen Fuß.
    """
    from app.core.perceive.matching import declared_partners

    def made(name: str, kind: str, centre: tuple[float, float, float], provenance: str) -> Feature:
        return Feature(
            id=name,
            kind=kind,
            provenance=provenance,
            params={"diameter": 3.6, "centre": centre, "axis": (1.0, 0.0, 0.0), "depth": 5.4},
        )

    declared = {
        "pin_1": made("pin_1", "pin", (0.0, 0.0, 28.3), "generated"),
        "pin_2": made("pin_2", "pin", (0.0, 0.0, 11.7), "generated"),
    }
    # Die Fasen der Stiftspitzen gehören dazu: Erst mit ihnen blieb der Stift
    # in der Zuordnung umkämpft (``match`` allein, Sonde p70).
    detected = {
        "cone_1": made("cone_1", "cone", (4.8, 0.0, 11.7), "detected"),
        "cone_2": made("cone_2", "cone", (4.8, 0.0, 28.3), "detected"),
        "pin_1": made("pin_1", "pin", (2.4, 0.0, 28.3), "detected"),
    }

    seen = declared_partners(declared, detected, (-97.3, 0.0, 300.0), 635.0)

    assert seen.mapping == {"pin_1": "pin_1"}
    assert not seen.ambiguous
    assert "pin_2" in seen.orphaned, "an seiner Stelle steht nichts"
    assert "pin_1" not in seen.fresh


def ridged_ring() -> bytes:
    """Ein Ring mit einem Grat innen, dreimal unterbrochen — drei Verrundungen um denselben Kreis.

    Der Grat läuft als schmales Band (0,67 mm) zwischen zwei Kegeln um Ø 54,57;
    drei breite Nasen trennen ihn in drei Bögen. Für die Zuordnung sind die
    drei Bögen Zwillinge: dieselbe Art, dieselbe Mitte, Achse und dasselbe Maß
    — nur ihre Oberfläche liegt an drei Stellen. So sieht der Ring des
    Siebhalters aus dem Korpus aus (``Siebhalter+X1C.3mf``), an dem nach
    *Kanten verfeinern*, *Bohrung setzen* und *Verschieben* drei von 48
    Verrundungen mit bitgleichen Maßen unter neuen Namen zurückkamen.
    """
    from app.core.geom.boolean import boolean
    from app.core.scene.cancel import NeverCancelled

    tip = 0.67
    reach = 8.4 - 6.65 - tip / 2.0
    profile = [
        (28.7, 0.0),
        (35.0, 0.0),
        (35.0, 13.0),
        (28.7, 13.0),
        (28.7, 8.4),
        (28.7 - reach, 6.65 + tip / 2.0),
        (28.7 - reach, 6.65 - tip / 2.0),
        (28.7, 4.9),
        (28.7, 0.0),
    ]
    ring = trimesh.creation.revolve(np.array(profile), sections=128)
    if ring.volume < 0.0:
        ring.invert()
    lugs = []
    for index in range(3):
        lug = trimesh.creation.box(extents=(3.0, 20.0, 5.0))
        lug.apply_translation((27.5, 0.0, 6.65))
        lug.apply_transform(
            trimesh.transformations.rotation_matrix(index * 2.0 * np.pi / 3.0 + 0.3, (0, 0, 1))
        )
        lugs.append(lug)
    cut = boolean(
        "difference",
        [MeshData.of(ring), MeshData.of(trimesh.util.concatenate(lugs))],
        quality="fine",
        cancelled=NeverCancelled(),
    ).mesh
    return bytes(cut.raw.export(file_type="stl"))


def _surface_place(mesh: MeshData, feature: Feature) -> np.ndarray:
    faces = np.asarray(feature.face_indices, dtype=np.int64)
    areas = np.asarray(mesh.raw.area_faces)[faces]
    return (np.asarray(mesh.raw.triangles_center)[faces] * areas[:, None]).sum(axis=0) / areas.sum()


@pytest.mark.parametrize(
    "step",
    [
        ("remesh_mesh", {"edge": 1.0}, (0.0, 0.0, 0.0)),
        (
            "drill_hole",
            {"diameter": 2.0, "x": 31.0, "y": -5.0, "z": 13.0, "depth": 1.0},
            (0.0,) * 3,
        ),
        ("translate_object", {"dx": 5.0}, (5.0, 0.0, 0.0)),
    ],
    ids=["verfeinern", "bohren", "verschieben"],
)
def test_twins_keep_their_names_where_their_surface_stays(profile, step) -> None:
    """Zwillinge für die Zuordnung behalten ihren Namen an der Stelle ihrer Oberfläche.

    Drei Bögen desselben Grats unterscheidet der Merkmalsvektor nicht, und die
    Zuordnung meldete sie nach jedem Schritt mehrdeutig: Ohne Verweis kamen sie
    unter neuen Namen zurück, mit Verweis stellte sie dem Kunden eine Frage,
    die die Geometrie beantwortet. Wo die Oberfläche eines Bogens nach dem
    Schritt liegt, liegt nur einer — der behält den Namen. Gefragt wird nicht
    (``ask`` schlägt fehl).
    """
    from app.core.perceive.features import forget_cache
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    forget_cache()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/ring.stl", sha256=""
    )
    project.sources["src_1"] = ridged_ring()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)

    def no_question(question, choices):
        pytest.fail(f"gefragt: {question}")

    first = evaluate(project.document, profile, sources=sources, ask=no_question)
    body_id = project.document.ops[-1].outputs[0]
    before = first.scene.objects[body_id]
    fillets = sorted(name for name, f in before.features.items() if f.kind == "fillet")
    assert len(fillets) == 3, sorted(before.features)
    centre, diagonal = before.mesh.bounds.centre, before.mesh.bounds.diagonal
    twins = [before.features[name] for name in fillets]
    assert cost(twins[0], twins[1], centre, centre, diagonal) < 0.05, "die drei sind Zwillinge"

    op, params, shift = step
    history.apply(op, [OperationDraft(op=op, inputs=(body_id,), params=params)])
    output_id = project.document.ops[-1].outputs[0]
    second = evaluate(project.document, profile, sources=sources, ask=no_question)
    assert second.stopped_at is None
    after = second.scene.objects[output_id]
    assert sorted(name for name, f in after.features.items() if f.kind == "fillet") == fillets
    for name in fillets:
        np.testing.assert_allclose(
            _surface_place(after.mesh, after.features[name]),
            _surface_place(before.mesh, before.features[name]) + np.asarray(shift),
            atol=0.05,
        )
    assert "perceive.orphaned" not in {finding.code for finding in second.scene.report.findings}


def test_only_a_clearly_nearest_surface_settles_twins() -> None:
    """Die Lage der Oberfläche entscheidet nur, was sie für beide Seiten mit Abstand trennt."""
    from app.core.perceive.matching import MatchResult, settled_by_surface

    open_twins = MatchResult(ambiguous={"a": ("x", "y"), "b": ("x", "y")}, fresh=("x", "y", "z"))
    far = {"a": np.array([0.0, 0.0, 0.0]), "b": np.array([30.0, 0.0, 0.0])}
    near = {"x": np.array([30.0, 0.1, 0.0]), "y": np.array([0.0, 0.1, 0.0])}
    settled = settled_by_surface(open_twins, far, near, 100.0)
    assert settled.mapping == {"a": "y", "b": "x"}
    assert not settled.ambiguous
    assert settled.fresh == ("z",)
    # Gleich weit weg — zwei gleiche Stücke einer geteilten Fläche: bleibt offen.
    halves = {"x": np.array([-5.0, 0.0, 0.0]), "y": np.array([5.0, 0.0, 0.0])}
    one = MatchResult(ambiguous={"a": ("x", "y")}, fresh=("x", "y"))
    assert settled_by_surface(one, {"a": np.zeros(3)}, halves, 100.0) == one
    # Ohne Ort entscheidet nichts, und auch ein Rivale ohne Ort hält das Paar offen.
    assert settled_by_surface(open_twins, {"a": far["a"]}, near, 100.0).mapping == {}
    # Weiter weg als die Lagetoleranz der Zuordnung: kein Paar.
    beyond = {"x": np.array([50.0, 0.0, 0.0]), "y": np.array([90.0, 0.0, 0.0])}
    assert settled_by_surface(one, {"a": np.zeros(3)}, beyond, 100.0) == one
    # Stufen einer geprägten Schrift, 0,08 mm übereinander: Genau an ihrer
    # Stelle liegt nur eine — die Untergrenze der Zuordnung gilt hier nicht,
    # wohl aber die Sehnenabweichung, unter der das Netz nichts unterscheidet.
    step = {"x": np.array([0.0, 0.0, 0.392]), "y": np.array([0.0, 0.0, 0.473])}
    assert settled_by_surface(one, {"a": step["x"]}, step, 40.0).mapping == {"a": "x"}
    close = {"x": np.array([0.0, 0.0, 0.392]), "y": np.array([0.0, 0.0, 0.422])}
    assert settled_by_surface(one, {"a": close["x"]}, close, 40.0) == one
