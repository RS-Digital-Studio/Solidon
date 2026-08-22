"""Analysekarten (Bauplan §18.4).

Jede Karte wird gegen einen Körper geprüft, dessen Antwort vorher feststeht —
eine Platte ist 8 mm dick, ein Würfel hat keinen Überhang, ein Kegel auf der
Seite reichlich.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import trimesh

from app.core.geom.measure import wall_thickness
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import apply, place_on_bed, rotation
from app.core.ingest.loader import normalise
from app.core.perceive import maps
from app.core.perceive.features import detect
from app.core.types import (
    Feature,
    FeatureRef,
    Finding,
    Fit,
    Profile,
    Report,
    Scene,
    SceneObject,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def plate() -> MeshData:
    """80 × 50 × 8 mm mit vier Bohrungen."""
    return place_on_bed(
        normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    )


def cube() -> MeshData:
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def object_with(mesh: MeshData) -> SceneObject:
    return SceneObject(id="obj_1", name="Prüfkörper", mesh=mesh, features=detect(mesh))


# --- wall thickness -------------------------------------------------------------


def test_the_wall_map_measures_the_plate(profile: Profile) -> None:
    entry = object_with(plate())
    analysis = maps.build("wall", entry, profile=profile)

    assert len(analysis.values) == entry.mesh.triangle_count
    assert analysis.unit == "mm"
    assert analysis.resolution is not None, "a sampled number says how fine it was sampled"
    # An der großen Fläche gemessen: 8 mm Material darunter. Die Toleranz ist ein
    # Rasterschritt, denn das ist, was das Raster unterscheiden kann.
    for index in entry.features["face_1"].face_indices:
        assert analysis.values[index] == pytest.approx(8.0, abs=analysis.resolution)


def test_the_wall_map_marks_what_is_too_thin(profile: Profile) -> None:
    """§39: zwei Extrusionsbreiten sind der Boden, und die Karte sagt, wo er
    unterschritten wird.
    """
    thin = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 0.5)))
    analysis = maps.build("wall", object_with(thin), profile=profile)

    assert analysis.threshold == pytest.approx(profile.minimum_wall_thickness)
    assert analysis.highlighted, "half a millimetre is below two extrusion widths"


def test_the_wall_scale_ends_where_the_question_ends(profile: Profile) -> None:
    """An einer Stirnfläche misst der Strahl quer durch das ganze Teil.

    Bei einem Brett von 8 mm Dicke und 80 mm Länge spannte die Legende damit
    über 80 mm — und der Bereich, um den es beim Drucken geht (unter zwei
    Extrusionsbreiten), fiel in eine einzige Farbstufe. Die Karte konnte ihre
    eigene Frage nicht beantworten.
    """
    long_plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    analysis = maps.build("wall", object_with(long_plate), profile=profile)

    assert max(analysis.known) > 40.0, "gemessen wird weiterhin, was da ist"
    assert analysis.high <= profile.minimum_wall_thickness * maps.WALL_SCALE_FACTOR
    assert analysis.high < max(analysis.known), "die Skala endet vor dem Höchstwert"
    assert "Skala" in str(analysis.note), "und sie sagt, dass sie das tut"


def test_a_map_explains_what_it_cannot_say(profile: Profile) -> None:
    """Die Fußzeile zählte sie („17 × nicht bestimmbar") und ließ die Zahl
    unerklärt stehen."""
    half = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    half.faces = half.faces[:6]
    analysis = maps.wall_thickness_map(MeshData.of(half))

    assert analysis.unknown_count, "sonst prüft dieser Test nichts"
    assert analysis.unknown_note, "und wer nichts sagen kann, sagt warum"


def test_an_open_body_says_it_cannot_say() -> None:
    """Eine halbe Box hat kein Innen — und keine Dicke. Null wäre eine Lüge."""
    open_body = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    open_body.raw.faces = open_body.raw.faces[:6]
    analysis = maps.wall_thickness_map(open_body)

    assert analysis.unknown_count > 0
    assert all(not math.isnan(value) for value in analysis.known)


def test_the_map_agrees_with_the_measuring_tool() -> None:
    """§18.3 und §18.4 müssen dieselbe Antwort geben, sonst lügt eine von
    beiden.
    """
    body = plate()
    analysis = maps.wall_thickness_map(body)
    assert analysis.resolution is not None

    centres = body.raw.triangles_center
    for index in (0, 5, 11):
        point = (float(centres[index][0]), float(centres[index][1]), float(centres[index][2]))
        measured = wall_thickness(body, point, direction=tuple(-body.raw.face_normals[index]))
        if measured is None or math.isnan(analysis.values[index]):
            continue
        assert analysis.values[index] == pytest.approx(measured, abs=2.0 * analysis.resolution)


def test_a_thick_block_is_thick_everywhere() -> None:
    block = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    analysis = maps.wall_thickness_map(block)

    assert analysis.resolution is not None
    assert min(analysis.known) == pytest.approx(20.0, abs=2.0 * analysis.resolution)


# --- overhang -------------------------------------------------------------------


def test_a_cube_has_no_overhang_worth_the_name() -> None:
    analysis = maps.overhang_map(cube())

    assert analysis.unit == "°"
    # The underside faces straight down, everything else stands vertical.
    assert {round(value) for value in analysis.values} <= {0, 90}
    assert analysis.threshold == 45.0


def test_a_tilted_face_is_measured_not_guessed() -> None:
    """Um 30 Grad gedreht steht die Unterseite auf 60 und eine Seite auf 30."""
    tilted = apply(cube(), rotation("x", 30.0))
    analysis = maps.overhang_map(tilted)

    assert max(analysis.values) == pytest.approx(60.0, abs=0.5)
    assert any(value == pytest.approx(30.0, abs=0.5) for value in analysis.values)


def test_steep_faces_are_the_ones_highlighted() -> None:
    cone = MeshData.of(trimesh.creation.cone(radius=20.0, height=10.0, sections=32))
    analysis = maps.overhang_map(apply(cone, rotation("x", 180.0)))

    assert analysis.highlighted, "a cone on its base overhangs at 63 degrees"
    for index in analysis.highlighted:
        assert analysis.values[index] > 45.0


# --- mesh defects ---------------------------------------------------------------


def test_the_defect_map_finds_the_open_edges() -> None:
    broken = normalise(read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm").mesh
    analysis = maps.defect_map(broken)

    assert analysis.highlighted, "the missing wall leaves open edges behind"
    assert analysis.categories[1] == "offene Kante"


def test_a_clean_body_has_a_clean_map() -> None:
    analysis = maps.defect_map(cube())

    assert analysis.highlighted == ()
    assert set(analysis.values) == {0.0}


# --- curvature ------------------------------------------------------------------


def test_the_curvature_map_shows_the_edges() -> None:
    """Ein Würfel hat nur Kanten und ebene Flächen — beide haben keinen Radius.

    Bis zum 22.08.2026 stand hier ``high == 90``, der Winkel einer Würfelkante
    in Grad. Die Karte misst jetzt den Radius, und die richtige Antwort für
    eine scharfe Kante ist **null** und nicht neunzig.
    """
    analysis = maps.curvature_map(cube())

    assert analysis.unit == "mm"
    assert analysis.high == pytest.approx(0.0, abs=0.01), "a cube edge is sharp"


def test_the_curvature_map_measures_the_fillet_and_not_the_mesh() -> None:
    """Die Frage aus §18.4 ist *wie* rund, nicht *dass* — und die alte Karte
    konnte sie nicht beantworten.

    Sie mass den schärfsten Winkel zu einem Nachbarn, und der wird kleiner, je
    feiner eine Verrundung vernetzt ist, obwohl ihr Radius derselbe bleibt.
    Gemessen wird hier deshalb an **zwei** Vernetzungen desselben Zylinders:
    Der Radius muss beide Male derselbe sein, der Winkel wäre es nicht.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    def radius_of(sections: int) -> float:
        body = trimesh.creation.cylinder(radius=5.0, height=20.0, sections=sections)
        analysis = maps.curvature_map(MeshData.of(body))
        known = [value for value in analysis.values if value == value]
        return sum(known) / len(known)

    coarse, fine = radius_of(32), radius_of(128)

    assert coarse == pytest.approx(5.0, rel=0.02), coarse
    assert fine == pytest.approx(5.0, rel=0.02), fine
    assert coarse == pytest.approx(fine, rel=0.02), "the mesh must not change the answer"


def test_the_curvature_map_finds_a_fillet_beside_its_cylinder() -> None:
    """Der Fall, für den die Karte gebaut wurde (§18.4, §41).

    Eine Säule Ø 12 auf einer Platte, der Fuß mit R 3 verrundet. Beide Flächen
    hängen **tangential** aneinander — die Merkmalserkennung liest sie deshalb
    als einen Fleck und findet dort weder Zylinder noch Torus. Die Karte trennt
    sie, weil sie nicht nach Knicken fragt, sondern nach Radien.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    plate = trimesh.creation.box(extents=(60.0, 60.0, 6.0))
    plate.apply_translation((0.0, 0.0, -3.0))
    post = trimesh.creation.cylinder(radius=6.0, height=30.0, sections=96)
    post.apply_translation((0.0, 0.0, 15.0))
    outer = trimesh.creation.cylinder(radius=9.0, height=3.0, sections=96)
    outer.apply_translation((0.0, 0.0, 1.5))
    inner = trimesh.creation.cylinder(radius=6.0, height=6.0, sections=96)
    inner.apply_translation((0.0, 0.0, 1.5))
    ring = trimesh.boolean.difference([outer, inner])
    torus = trimesh.creation.torus(
        major_radius=9.0, minor_radius=3.0, major_sections=96, minor_sections=48
    )
    torus.apply_translation((0.0, 0.0, 3.0))
    fillet = trimesh.boolean.difference([ring, torus])

    analysis = maps.curvature_map(MeshData.of(trimesh.boolean.union([plate, post, fillet])))
    found = {round(value, 1) for value in analysis.values if value == value}

    assert 3.0 in found, f"the fillet radius is 3 mm: {sorted(found)[:6]}"
    assert 6.0 in found, f"the post radius is 6 mm: {sorted(found)[:6]}"


# --- Features und Passungen -----------------------------------------------------


def test_every_feature_gets_its_own_level() -> None:
    """§18.4: "verstehen, was die KI sieht" — one colour per feature."""
    entry = object_with(plate())
    analysis = maps.build("features", entry)

    assert analysis.categories[0].startswith("ohne")
    assert "hole_1" in analysis.categories
    hole = entry.features["hole_1"]
    level = analysis.categories.index("hole_1")
    assert all(analysis.values[index] == float(level) for index in hole.face_indices)


def test_the_fit_map_marks_the_violated_pair(profile: Profile) -> None:
    entry = object_with(plate())
    scene = Scene(objects={"obj_1": entry}, profile=profile)
    scene.fits.append(
        Fit(
            name="stift_1",
            a=FeatureRef("obj_1", "hole_1"),
            b=FeatureRef("obj_2", "pin_1"),
            kind="clearance",
        )
    )
    scene.report = Report(
        (
            Finding(
                code="fit.violated",
                severity="warning",
                message="zu eng",
                object_id="obj_1",
                feature_ids=("hole_1",),
            ),
        )
    )
    analysis = maps.build("fits", entry, scene=scene)

    assert analysis.highlighted, "the violated fit is the thing to look at"
    assert analysis.categories[2] == "Passung verletzt"
    assert maps.fits_of(scene, "obj_1")


def test_without_fits_the_map_stays_empty(profile: Profile) -> None:
    entry = object_with(plate())
    scene = Scene(objects={"obj_1": entry}, profile=profile)

    assert set(maps.build("fits", entry, scene=scene).values) == {0.0}


# --- support --------------------------------------------------------------------


def test_the_support_map_comes_from_the_layer_analysis(profile: Profile) -> None:
    """§18.4: das Urteil gehört dem Schneider, keiner Faustregel über
    Normalenvektoren.
    """
    analysis = maps.build("support", object_with(_table()), profile=profile)

    assert analysis.highlighted, "the overhanging arm rests on nothing"
    assert max(analysis.values) == pytest.approx(20.0, abs=0.5), "that is how tall it grows"
    assert analysis.source == "internal"
    assert analysis.note is not None, "an estimate has to say that it is one (§22.5)"


def _table() -> MeshData:
    """Eine Säule auf der Platte mit einem Arm darauf, der über nichts
    hinausreicht.
    """
    post = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    post.apply_translation([0.0, 0.0, 10.0])
    arm = trimesh.creation.box(extents=(40.0, 10.0, 4.0))
    arm.apply_translation([0.0, 0.0, 22.0])
    return MeshData.of(trimesh.boolean.union([post, arm]))


def test_a_body_on_the_plate_needs_nothing(profile: Profile) -> None:
    analysis = maps.build("support", object_with(plate()), profile=profile)

    assert analysis.highlighted == ()


# --- Abbrechen ------------------------------------------------------------------


def test_a_map_stops_when_nobody_waits_for_it_any_more(profile: Profile) -> None:
    """§18.4 verspricht abbrechbare Karten, und keine war es.

    Wer die zweite Karte wählte, wartete erst die erste ab — bei 51 000
    Dreiecken 3,4 Sekunden, in denen das Fenster „wird berechnet …" für die
    falsche meldete. Gefragt wird am Eingang und in der teuersten Schleife.
    """
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        maps.build("support", object_with(_table()), profile=profile, cancelled=signal)


def test_the_expensive_loop_asks_too(profile: Profile) -> None:
    """Am Eingang zu fragen genügt nicht.

    Die Sekunden liegen in der Schleife über die Dreiecke, nicht davor — ein
    Abbruch, der nur beim Start greift, kommt genau dann nie an, wenn er
    gebraucht wird.
    """
    from app.core.errors import OperationCancelled

    class _AfterTheFirstLook:
        """Sagt beim zweiten Fragen ab — und das zweite Mal ist die Schleife."""

        def __init__(self) -> None:
            self.asked = 0

        @property
        def is_cancelled(self) -> bool:
            return self.asked > 1

        def raise_if_cancelled(self) -> None:
            self.asked += 1
            if self.asked > 1:
                raise OperationCancelled

    token = _AfterTheFirstLook()
    with pytest.raises(OperationCancelled):
        maps.build("support", object_with(_table()), profile=profile, cancelled=token)

    assert token.asked > 1, "die Schleife hat gefragt, nicht nur der Eingang"


def test_a_map_runs_through_while_nobody_cancels(profile: Profile) -> None:
    """Der Schalter ist da und wird nicht gezogen — dann ändert er nichts."""
    from app.core.scene.cancel import CancelSignal

    analysis = maps.build(
        "support", object_with(_table()), profile=profile, cancelled=CancelSignal()
    )

    assert analysis.highlighted


# --- Der Weg von der Warnung zur Stelle -----------------------------------------


def test_a_finding_picks_its_map() -> None:
    assert maps.map_for(Finding(code="fit.violated", severity="warning", message="x")) == "fits"
    assert maps.map_for(Finding(code="repair.still_open", severity="warning", message="x")) == (
        "defects"
    )
    assert maps.map_for(Finding(code="orient.heuristic", severity="info", message="x")) == (
        "overhang"
    )
    assert maps.map_for(Finding(code="etwas.anderes", severity="info", message="x")) is None


def test_the_camera_target_is_the_centre_of_what_is_marked(profile: Profile) -> None:
    entry = object_with(plate())
    analysis = maps.build("wall", entry, profile=profile)
    assert maps.focus_point(entry, analysis) is None, "nothing marked, nowhere to fly"

    hole = entry.features["hole_1"]
    marked = maps.AnalysisMap(
        kind="wall",
        title="x",
        values=analysis.values,
        unit="mm",
        low=0.0,
        high=1.0,
        highlighted=hole.face_indices,
    )
    point = maps.focus_point(entry, marked)
    assert point is not None
    assert point[0] == pytest.approx(hole.params["centre"][0], abs=0.5)


def test_a_finding_without_a_place_falls_back_to_its_features() -> None:
    entry = object_with(plate())
    finding = Finding(code="fit.violated", severity="warning", message="x", feature_ids=("hole_2",))

    point = maps.location_of(entry, finding)
    assert point is not None
    assert point[0] == pytest.approx(entry.features["hole_2"].params["centre"][0], abs=0.5)


def test_a_finding_that_points_nowhere_stays_that_way() -> None:
    entry = object_with(cube())
    assert maps.location_of(entry, Finding(code="x", severity="info", message="y")) is None


# --- limits ---------------------------------------------------------------------


def test_a_huge_body_is_refused_rather_than_ground_through(profile: Profile) -> None:
    """§31: eine Karte, die Minuten braucht, ist schlechter als eine, die Nein
    sagt.
    """
    dense = MeshData.of(trimesh.creation.icosphere(subdivisions=3))
    entry = SceneObject(id="obj_1", name="x", mesh=dense, features={})
    limit = maps.MAP_LIMIT_TRIANGLES
    try:
        maps.MAP_LIMIT_TRIANGLES = 10
        with pytest.raises(maps.MapTooLarge):
            maps.build("wall", entry, profile=profile)
    finally:
        maps.MAP_LIMIT_TRIANGLES = limit


def test_features_without_faces_do_not_fall_over() -> None:
    entry = SceneObject(
        id="obj_1",
        name="x",
        mesh=cube(),
        features={"loop": Feature(id="loop", kind="edge_loop", provenance="detected", params={})},
    )
    analysis = maps.build("features", entry)

    assert set(analysis.values) == {0.0}
