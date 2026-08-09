"""Die Operationen, die §25 nennt und die dem Register fehlten (§25, §10).

Spiegeln, Netz, Aushöhlen, Elefantenfuß, Senken, Verschließen, Beschriftung,
Zeichnungen. Jede einzelne ist etwas, wofür Leute die Anwendung sonst verlassen
— und jede einzelne wird hier gegen eine Zahl gemessen, die sich von Hand
nachrechnen lässt, nicht auf einem Bild angeschaut.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom import mesh_ops
from app.core.geom.hollow import hollow
from app.core.geom.label_ops import outlines
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import compensate_elephant_foot, countersink, plug
from app.core.ingest.outline import extrude, is_outline
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<path d="M10,10 L90,10 L90,90 L10,90 Z M30,30 L30,70 L70,70 L70,30 Z"/></svg>'
)


def block(width: float = 40.0, depth: float = 40.0, height: float = 40.0) -> MeshData:
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation((0.0, 0.0, height / 2.0))
    return MeshData.of(body)


def run(op: str, entry: SceneObject | None, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


# --- mirroring ------------------------------------------------------------------


def test_mirroring_turns_the_part_over_without_turning_it_inside_out(profile: Profile) -> None:
    """Eine Spiegelung stülpt jedes Dreieck um — ein Körper mit umgedrehten
    Normalen ist kaputt.
    """
    wedge = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    wedge.apply_translation((15.0, 0.0, 10.0))
    entry = SceneObject(id="obj_1", name="Rechts", mesh=MeshData.of(wedge))

    result = run("mirror_object", entry, profile, axis="x", about="origin")

    mirrored = result.outputs[0].mesh
    assert mirrored.volume == pytest.approx(8000.0), "positive, so not inside out"
    assert mirrored.is_watertight
    assert mirrored.bounds.centre[0] == pytest.approx(-15.0)


# --- the net --------------------------------------------------------------------


def test_decimation_keeps_the_shape_within_a_measured_bound(profile: Profile) -> None:
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=5, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=sphere)

    result = run("decimate_mesh", entry, profile, triangles=2000)

    after = result.outputs[0].mesh
    assert after.triangle_count == 2000
    assert mesh_ops.deviation(sphere, after) < 0.2, "under two tenths on a 40 mm ball"
    assert [finding.code for finding in result.findings] == ["mesh.deviation"]
    assert result.findings[0].values["deviation_mm"] > 0.0, "it says what it cost"


def test_a_small_body_is_left_alone() -> None:
    small = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    assert mesh_ops.decimate(small, 4).triangle_count == small.triangle_count


def test_smoothing_does_not_shrink_the_body(profile: Profile) -> None:
    """Taubin statt Laplace — zehn Durchgänge des Letzteren kosten eine
    Passung.
    """
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=sphere)

    result = run("smooth_mesh", entry, profile, iterations=10)

    assert result.outputs[0].mesh.volume == pytest.approx(sphere.volume, rel=0.02)


def test_remeshing_splits_edges_without_moving_anything(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Würfel", mesh=block(20.0, 20.0, 20.0))

    result = run("remesh_mesh", entry, profile, edge=5.0)

    after = result.outputs[0].mesh
    assert after.triangle_count > 12
    assert after.volume == pytest.approx(8000.0), "the shape is untouched"
    assert after.is_watertight


def test_remeshing_an_uneven_body_keeps_it_closed(profile: Profile) -> None:
    """Der Würfel oben ging immer gut, weil alle seine Kanten gleich lang sind.

    Bei ungleichen Kanten wird jede Fläche verschieden oft geteilt, und an den
    Nähten dazwischen stand ein Punkt auf einer Kante, die ihn nicht kannte:
    192 Kanten mit nur einem Nachbarn, drei Komponenten, kein geschlossener
    Körper. Der Befund sagte trotzdem „die Form ist unverändert", und die
    nächste boolesche Operation fiel auf die Voxelstufe und rundete die Maße.
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=block(40.0, 30.0, 10.0))

    result = run("remesh_mesh", entry, profile, edge=5.0)

    after = result.outputs[0].mesh
    assert after.is_watertight, "ein zerrissenes Netz bricht alles, was danach kommt"
    assert after.component_count == 1
    assert after.volume == pytest.approx(12_000.0)
    assert after.triangle_count > 12


def test_remeshing_reaches_the_edge_length_it_promises(profile: Profile) -> None:
    """„Teilt lange Kanten, bis das Netz gleichmäßig ist" — nachgemessen."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=block(40.0, 30.0, 10.0))

    result = run("remesh_mesh", entry, profile, edge=5.0)

    longest = max(mesh_ops.edge_lengths(as_mesh_data(result.outputs[0].mesh)))
    assert longest <= 5.0 + 1e-9


def test_a_torn_remesh_says_so_instead_of_claiming_the_shape_is_fine(profile: Profile) -> None:
    """Was die Operation über ihr Ergebnis sagt, muss sie geprüft haben.

    Ein offener Körper kommt hier nicht aus dem Unterteilen, sondern aus dem
    Eingang — und dann darf die Meldung nicht behaupten, alles sei in Ordnung.
    """
    open_body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    open_body.update_faces(np.arange(len(open_body.faces)) > 1)
    entry = SceneObject(id="obj_1", name="Offen", mesh=MeshData.of(open_body))

    result = run("remesh_mesh", entry, profile, edge=2.0)

    codes = {finding.code for finding in result.findings}
    assert "mesh.remesh_open" in codes
    assert any(finding.severity == "warning" for finding in result.findings)


# --- hollowing ------------------------------------------------------------------


def test_hollowing_leaves_the_wall_and_takes_the_rest(profile: Profile) -> None:
    result = hollow(block(), 2.0, vents=1)

    assert result.mesh.is_watertight
    assert result.removed > 30_000.0, "a 40 mm cube has plenty inside"
    assert result.mesh.volume < 64_000.0 * 0.4
    assert len(result.vents) == 1


def test_a_wall_thicker_than_the_body_leaves_nothing_to_take(profile: Profile) -> None:
    thin = MeshData.of(trimesh.creation.box(extents=(6.0, 6.0, 6.0)))

    result = hollow(thin, 5.0)

    assert result.mesh is thin
    assert [finding.code for finding in result.findings] == ["hollow.too_thin"]


def test_hollowing_without_a_vent_is_possible_and_says_nothing_extra(profile: Profile) -> None:
    result = hollow(block(), 2.0, vents=0)

    assert not result.vents
    assert "hollow.no_vent" not in {finding.code for finding in result.findings}


def test_an_opened_body_is_a_tin(profile: Profile) -> None:
    """§25: der Weg von der Aushöhlung zur Dose ist ein Schalter, kein Umweg.

    Vorher endete *Aushöhlen* immer bei einem geschlossenen Hohlraum, und wer
    eine Dose wollte, baute sie aus zwei Zylindern und einer Differenz — dem
    Weg, den ein CAD-Anwender kennt und den die Bausteine nicht nahelegen.
    """
    closed = hollow(block(), 2.0)
    opened = hollow(block(), 2.0, open_top=True)

    assert opened.mesh.is_watertight
    assert opened.mesh.component_count == 1
    assert opened.mesh.volume < closed.mesh.volume, "die Decke ist weg"
    assert not opened.vents, "eine offene Dose ist ihre eigene Entlüftung"


def test_the_lid_finds_the_opening_that_hollowing_made(profile: Profile) -> None:
    """Die zwei Schritte hintereinander — das ist der Punkt der Sache.

    *Deckel erzeugen* verlangt eine Öffnung und meldete sonst „auf dieser Höhe
    massiv". Ein ausgehöhlter und oben geöffneter Körper hat eine.
    """
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    tin = SceneObject(id="obj_1", name="Dose", mesh=hollow(block(), 3.0, open_top=True).mesh)
    spec = REGISTRY.get("create_lid")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={tin.id: tin}),
            inputs=[tin],
            params=spec.params(thickness=2.4, collar=4.0),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    lid = result.outputs[1].mesh
    assert lid.is_watertight
    assert lid.bounds.size[0] == pytest.approx(40.0, abs=0.5), "der Deckel deckt die Dose"


def test_hollow_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    result = run("hollow_object", entry, profile, wall=2.0, vents=1)

    assert result.outputs[0].mesh.volume < 30_000.0
    assert "hollow.done" in {finding.code for finding in result.findings}


# --- the first layer ------------------------------------------------------------


def test_the_first_layers_are_pulled_in_by_the_profile_value(profile: Profile) -> None:
    """Regel 7: der Wert kommt aus dem Material, nie aus einer Schätzung."""
    body = block(40.0, 40.0, 10.0)
    entry = SceneObject(id="obj_1", name="Klotz", mesh=body)

    result = run("compensate_first_layer", entry, profile, height=0.6)

    corrected = result.outputs[0].mesh
    assert corrected.volume < body.volume
    lost = body.volume - corrected.volume
    expected = (40.0**2 - (40.0 - 2 * profile.material.elephant_foot) ** 2) * 0.6
    assert lost == pytest.approx(expected, rel=0.15)
    assert "prepare.elephant_foot" in {finding.code for finding in result.findings}


def test_without_a_measured_value_nothing_happens(profile: Profile) -> None:
    import dataclasses

    flat = dataclasses.replace(
        profile, material=dataclasses.replace(profile.material, elephant_foot=0.0)
    )
    body = block()

    corrected, findings = compensate_elephant_foot(body, flat)

    assert corrected is body and not findings


# --- holes ----------------------------------------------------------------------


def test_a_countersink_takes_off_the_cone_of_the_head(profile: Profile) -> None:
    body = block(40.0, 40.0, 10.0)
    diameter, angle = 8.0, 90.0

    result = countersink(body, position=(0.0, 0.0, 10.0), axis="z", diameter=diameter, angle=angle)

    depth = diameter / 2.0 / math.tan(math.radians(angle / 2.0))
    cone = math.pi * (diameter / 2.0) ** 2 * depth / 3.0
    assert body.volume - result.mesh.volume == pytest.approx(cone, rel=0.05)


def test_a_plug_fills_a_bore_and_stays_inside_the_part(profile: Profile) -> None:
    from app.core.geom.prepare import drill

    body = block(40.0, 40.0, 10.0)
    drilled = drill(body, position=(0.0, 0.0, 5.0), axis="z", diameter=6.0, profile=profile).mesh
    assert drilled.volume < body.volume

    filled = plug(drilled, position=(0.0, 0.0, 5.0), axis="z", diameter=6.5)

    assert filled.mesh.volume == pytest.approx(body.volume, rel=0.01)
    assert filled.mesh.bounds.size[2] == pytest.approx(10.0, abs=0.01), "no plug sticking out"


def test_the_hole_operations_are_in_the_register() -> None:
    for name in ("countersink_hole", "plug_hole"):
        assert REGISTRY.get(name).category == "holes"


# --- labels ---------------------------------------------------------------------


def test_a_letter_with_a_hole_comes_out_with_a_hole() -> None:
    """„o" sind zwei Ringe, und welcher das Loch ist, folgt aus der
    Enthaltung.
    """
    shapes = outlines("o", 10.0)

    assert shapes
    assert sum(len(entry.interiors) for entry in shapes) == 1


def test_raised_text_adds_exactly_its_own_volume(profile: Profile) -> None:
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))
    area = sum(shape.area for shape in outlines("M4", 8.0))

    result = run("label_text", entry, profile, text="M4", size=8.0, depth=0.6, z=4.0)

    added = result.outputs[0].mesh.volume - 3200.0
    assert added == pytest.approx(area * 0.6, rel=0.01)
    assert result.outputs[0].mesh.bounds.size[2] == pytest.approx(4.6, abs=0.01)


def test_engraved_text_takes_away_the_same_volume(profile: Profile) -> None:
    """Der Fehler, um den es hier geht: ein Schnitt, der nur bis zur
    Überlappung reicht, ist ein Kratzer.
    """
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))
    area = sum(shape.area for shape in outlines("M4", 8.0))

    result = run(
        "label_text", entry, profile, text="M4", size=8.0, depth=0.6, mode="engraved", z=4.0
    )

    removed = 3200.0 - result.outputs[0].mesh.volume
    assert removed == pytest.approx(area * 0.6, rel=0.01)
    assert result.outputs[0].mesh.bounds.size[2] == pytest.approx(4.0, abs=0.01), "nothing proud"


def test_a_label_without_text_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Platte", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("label_text", entry, profile, text="   ", size=8.0)

    assert problem.value.field == "text"


def test_lettering_can_carry_its_own_slot(profile: Profile) -> None:
    """§20: zwei Farben in einer Datei statt in zwei Dateien.

    Die Buchstaben gehen mit ihrem Slot bekleidet in die Vereinigung, und die
    Attributübertragung der Booleschen Op bringt ihn auf der anderen Seite
    heraus (P9). Was der Drucker liest, ist eine 3MF mit zwei Gruppen.
    """
    from app.core.geom.attributes import counts, used_slots

    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate))

    result = run("label_text", entry, profile, text="RS", size=10.0, z=4.0, slot=1)

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1)
    assert counts(output.mesh)[1] > 0, "the letters are in the second slot"
    assert [(slot.index, str(slot.name)) for slot in output.material_slots] == [
        (0, "Körper"),
        (1, "Schrift"),
    ]


def test_without_a_slot_the_lettering_stays_one_colour(profile: Profile) -> None:
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate))

    result = run("label_text", entry, profile, text="RS", size=10.0, z=4.0)

    assert not result.outputs[0].mesh.slots


def test_a_label_can_be_a_body_of_its_own(profile: Profile) -> None:
    """Der andere Weg zu zwei Farben: eine zweite Datei für einen Drucker ohne
    AMS.
    """
    result = run("create_label", None, profile, text="RS", size=10.0, depth=2.0)

    body = result.outputs[0]
    assert body.name == "RS"
    assert body.mesh.bounds.size[2] == pytest.approx(2.0)
    assert body.mesh.triangle_count > 0


def test_a_label_body_keeps_the_counters_of_its_letters(profile: Profile) -> None:
    """Warum es **keinen** Text als Skizzenelement gibt (Konzept P15, D12).

    SindriCADs Sketcher kann einen Schriftzug als Skizzenkontur; unserer kann
    es nicht, und das ist eine Entscheidung. ``Profile`` trägt genau **einen**
    geschlossenen Umriss — ein Schriftzug ist eine Menge davon, jeder Buchstabe
    einer, und A, B und O tragen zusätzlich ein Loch. Das zu ändern hieße, alle
    fünf Skizzen-Operationen und den B-Rep-Kern anzufassen.

    Für einen Fall, den ``create_label`` bereits vollständig löst: drei
    getrennte Körper, jeder geschlossen, mit den Löchern an der richtigen
    Stelle. Dieser Test hält das fest, damit die Entscheidung eine Grundlage
    behält und nicht bei der nächsten Durchsicht neu geraten wird.
    """
    result = run("create_label", None, profile, text="ABO", size=10.0, depth=2.0)

    body = result.outputs[0].mesh
    assert body.raw.is_watertight, "jeder Buchstabe ist ein geschlossener Körper"
    assert len(body.raw.split()) == 3, "drei Buchstaben, drei Teile"
    # Die volle Hüllfläche wäre rund 157 mm³ bei 2 mm Tiefe; die Zähler in A,
    # B und O fehlen darin, also liegt das Volumen deutlich darunter.
    assert body.volume < 0.75 * body.bounds.size[0] * body.bounds.size[1] * 2.0


def test_an_empty_label_body_is_a_user_error(profile: Profile) -> None:
    with pytest.raises(ValidationError) as problem:
        run("create_label", None, profile, text="  ", size=10.0)

    assert problem.value.field == "text"


# --- the test piece -------------------------------------------------------------


def drilled_plate() -> MeshData:
    plate = trimesh.creation.box(extents=(80.0, 50.0, 8.0))
    plate.apply_translation((0.0, 0.0, 4.0))
    drill = trimesh.creation.cylinder(radius=3.0, height=40.0)
    drill.apply_translation((25.0, 15.0, 0.0))
    return MeshData.of(trimesh.boolean.difference([plate, drill]))


def test_a_test_piece_is_a_cut_out_of_the_real_part(profile: Profile) -> None:
    """Ein Stück, das anders druckt als das Teil, wäre schlechter als keines."""
    body = drilled_plate()
    entry = SceneObject(id="obj_1", name="Halterung", mesh=body)

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0)

    piece = result.outputs[0].mesh
    assert piece.bounds.size[0] == pytest.approx(20.0)
    assert piece.bounds.size[2] == pytest.approx(8.0), "the plate is thinner than the window"
    assert piece.is_watertight
    assert piece.volume < body.volume * 0.15, "a tenth of the print time"


def test_the_test_piece_lands_on_the_bed(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0, on_bed=True)

    assert result.outputs[0].mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)


def test_the_bore_is_still_in_the_piece(profile: Profile) -> None:
    """Sonst ist es ein Würfel, und ein Würfel beweist nichts über eine
    Passung.
    """
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0)

    solid = 20.0 * 20.0 * 8.0
    assert result.outputs[0].mesh.volume < solid * 0.98, "a hole is missing from it"


def test_a_window_over_thin_air_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    with pytest.raises(ValidationError) as problem:
        run("test_piece", entry, profile, size=10.0, x=500.0, y=0.0, z=0.0)

    assert problem.value.constraint == "empty"


# --- drawings -------------------------------------------------------------------


def test_a_drawing_becomes_a_body_with_its_holes() -> None:
    result = extrude(SVG, ".svg", 5.0)

    assert result.contours == 1
    assert result.mesh.volume == pytest.approx((80.0**2 - 40.0**2) * 5.0)
    assert result.mesh.is_watertight
    assert result.mesh.bounds.minimum[2] == pytest.approx(0.0), "on the plate"


def test_a_target_width_scales_the_plane_and_not_the_height() -> None:
    result = extrude(SVG, ".svg", 5.0, width=40.0)

    assert result.mesh.bounds.size[0] == pytest.approx(40.0)
    assert result.mesh.bounds.size[2] == pytest.approx(5.0), "the height was asked for in mm"


def test_a_drawing_with_no_closed_area_says_so() -> None:
    open_path = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0,0 L10,10"/></svg>'
    )

    with pytest.raises(ValidationError) as problem:
        extrude(open_path, ".svg", 2.0)

    assert problem.value.constraint == "no_area"


def test_a_drawing_reaches_the_scene_through_load_outline(profile: Profile) -> None:
    """§25: derselbe Weg hinein wie bei jeder anderen Datei — eine Quelle und
    eine Operation.
    """
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = SVG
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/logo.svg", sha256=""
    )
    History(project.document).apply(
        "Zeichnung",
        [OperationDraft(op="load_outline", params={"source": "src_1", "height": 4.0})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    entry = result.scene.objects["obj_1"]
    assert entry.mesh.bounds.size[2] == pytest.approx(4.0)
    assert "ingest.extruded" in {finding.code for finding in result.scene.report.findings}


def test_only_flat_formats_go_this_way() -> None:
    assert is_outline(".SVG") and is_outline(".dxf")
    assert not is_outline(".stl")

    with pytest.raises(ValidationError):
        extrude(SVG, ".stl", 2.0)


# --- the register ---------------------------------------------------------------


def test_every_category_of_the_plan_has_something_in_it() -> None:
    """§25 zählt auf, was die Anwendung kann; eine leere Kategorie ist eine
    Lücke.
    """
    filled = {spec.category for spec in REGISTRY.all()}
    for category in ("transform", "mesh", "prepare", "holes", "label", "import", "colour"):
        assert category in filled, category


# --- Eine Szene, mehr als ein Material (§12) -------------------------------------


def test_a_body_can_be_given_its_own_material(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Dichtung", mesh=block())

    result = run("set_material", entry, profile, material="tpu-95a")

    assert result.outputs[0].material == "tpu-95a"
    assert result.findings and result.findings[0].code == "prepare.material"


def test_an_empty_material_puts_the_body_back_on_the_project(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Dichtung", mesh=block(), material="tpu-95a")

    result = run("set_material", entry, profile, material="")

    assert result.outputs[0].material is None
    assert result.findings == [], "back to normal is not worth a line in the report"


def test_an_unknown_material_says_which_ones_there_are(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Dichtung", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("set_material", entry, profile, material="gummiband")

    assert "petg" in problem.value.values["known"]


def test_the_elephant_foot_follows_the_body_not_the_project(profile: Profile) -> None:
    """§12: TPU quetscht 0,25 mm in seine erste Schicht, PETG 0,2.

    Mit dem Projektmaterial gerechnet kommt eine TPU-Dichtung ringsum 0,05 mm
    zu breit heraus — bei einer Dichtung ist das der Unterschied zwischen
    dichten und nicht dichten.
    """
    plain = run("compensate_first_layer", SceneObject(id="obj_1", name="A", mesh=block()), profile)
    soft = run(
        "compensate_first_layer",
        SceneObject(id="obj_1", name="B", mesh=block(), material="tpu-95a"),
        profile,
    )

    assert soft.outputs[0].mesh.volume < plain.outputs[0].mesh.volume, "TPU is pulled in further"
