"""Selbstkalibrierung, Prüfkörper und Variantengenerator (Bauplan §28.3)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.knowledge import calibration, profiles
from app.core.knowledge.parts import PARTS
from app.core.scene import History, OperationDraft, evaluate, variants
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Parameter, Profile

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture(autouse=True)
def own_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Nie in das Profilverzeichnis der Maschine schreiben, auf der die Tests
    laufen.
    """
    directory = tmp_path / "profiles"
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: directory)
    monkeypatch.setattr(calibration, "user_profiles_dir", lambda: directory)
    profiles.reload()
    yield directory
    profiles.reload()


# --- die Prüfkörper (§28.3) -----------------------------------------------------------


@pytest.mark.parametrize(
    "name,bodies", [("fit_ladder", 2), ("wall_ladder", 1), ("overhang_fan", 1)]
)
def test_a_test_body_prints_its_declared_measuring_pieces(name: str, bodies: int) -> None:
    """Die Steckleiter hat zwei Messleisten, Wand und Überhang je einen verbundenen Körper.

    Den realen Steckgriff prüft test_fit_ladder_rails_really_assemble über
    Vorgabe und Parametergrenzen; hier bleibt unerklärtes Zerfallen verboten.
    """
    spec = PARTS.get(name)
    result = spec.fn(spec.params())

    assert result.mesh.is_watertight
    assert result.mesh.component_count == spec.bodies == bodies
    assert result.mesh.volume > 0.0


def test_the_fit_ladder_staggers_its_play() -> None:
    """§28.3: Stifte und Bohrungen mit gestaffeltem Spiel — und die Zahlen
    sagen, welche.
    """
    spec = PARTS.get("fit_ladder")
    result = spec.fn(spec.params(diameter=6.0, steps=4, first=0.10, step=0.05))

    bores = sorted(
        (feature.params["diameter"] for name, feature in result.features.items() if "bore" in name)
    )
    assert bores == pytest.approx([6.10, 6.15, 6.20, 6.25])
    pins = [feature for name, feature in result.features.items() if "pin" in name]
    assert len(pins) == 4
    assert all(entry.params["diameter"] == pytest.approx(6.0) for entry in pins)


def test_the_wall_ladder_climbs_in_extrusion_widths() -> None:
    spec = PARTS.get("wall_ladder")
    thin = spec.fn(spec.params(extrusion=0.42, steps=3))
    thick = spec.fn(spec.params(extrusion=0.42, steps=6))

    assert thick.mesh.volume > thin.mesh.volume


@pytest.mark.parametrize("name", ["insert_fit_ladder", "insert_wall_ladder", "insert_overhang_fan"])
def test_a_test_body_reaches_the_scene_as_an_operation(name: str, profile: Profile) -> None:
    """Wie jeder Baustein ist ein Prüfkörper eine Operation (§10) — in einem
    Schritt druckbar.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Grundplatte", [OperationDraft(op="create_box", params={"width": 5.0, "depth": 5.0})]
    )
    History(project.document).apply(name, [OperationDraft(op=name, inputs=("obj_1",), params={})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    assert result.scene.objects["obj_1"].mesh.volume > 0.0


def test_the_overhang_fan_leans_further_step_by_step() -> None:
    spec = PARTS.get("overhang_fan")
    flat = spec.fn(spec.params(first=20.0, step=10.0, steps=6))

    assert flat.mesh.bounds.size[1] > 6.0, "the ramps reach out over nothing"


# --- calibration (§28.3) --------------------------------------------------------------


@pytest.mark.parametrize("name", ["PLA matte", "PLA.matte", 'PLA "matt"'])
def test_calibration_preserves_quoted_material_ids(own_profiles: Path, name: str) -> None:
    """Eine zweite Kalibrierung erhält fremde gültige TOML-Kennungen."""
    import json
    import tomllib

    own_profiles.mkdir(parents=True, exist_ok=True)
    path = own_profiles / calibration.USER_MATERIALS
    original = {
        name: {
            "title": name,
            "clearance": 0.32,
            "press": -0.1,
            "hole_compensation": 0.2,
            "elephant_foot": 0.1,
        }
    }
    path.write_text(
        f"[{json.dumps(name)}]\ntitle = {json.dumps(name)}\nclearance = 0.32\n"
        "press = -0.1\nhole_compensation = 0.2\nelephant_foot = 0.1\n",
        encoding="utf-8",
    )
    profiles.reload()
    calibration.apply(calibration.from_measurements("petg", clearance=0.3))
    saved = tomllib.loads(path.read_text(encoding="utf-8"))
    assert saved[name] == original[name]
    assert saved["petg"]["clearance"] == pytest.approx(0.3)


def test_a_measurement_lands_in_the_material_profile(own_profiles: Path) -> None:
    """Schritt drei aus §28.3: die Werte gehen ins Profil, nicht in ein Modell."""
    before = profiles.material("petg")
    assert not before.calibrated

    after = calibration.apply(
        calibration.from_measurements("petg", clearance=0.18, hole_compensation=0.15)
    )

    assert after.calibrated
    assert after.clearance == pytest.approx(0.18)
    assert after.hole_compensation == pytest.approx(0.15)
    assert (own_profiles / "materials.toml").is_file()


def test_process_measurements_reach_only_the_measured_print_process(own_profiles: Path) -> None:
    """Die Wand- und Überhangprobe gilt für Material, Maschine und Druckraster gemeinsam."""
    before = profiles.make_profile("centauri-carbon-2", "petg")
    after = calibration.apply(
        calibration.from_measurements("petg", minimum_wall=0.55, overhang_angle=60.0),
        process=before,
    )
    measured = dataclasses.replace(before, material=after)
    assert measured.has_process_calibration
    assert measured.minimum_wall_thickness == pytest.approx(0.55)
    assert measured.overhang_limit_degrees == pytest.approx(60.0)
    assert after.youngs_modulus == pytest.approx(before.material.youngs_modulus)
    assert after.yield_strength == pytest.approx(before.material.yield_strength)
    for changes in (
        {"id": "other-printer"},
        {"nozzle_diameter": before.printer.nozzle_diameter * 2},
        {"layer_height": before.printer.layer_height * 2},
        {"extrusion_width": before.printer.extrusion_width * 2},
    ):
        other = dataclasses.replace(
            measured, printer=dataclasses.replace(before.printer, **changes)
        )
        assert not other.has_process_calibration
        assert other.minimum_wall_thickness == pytest.approx(2 * other.printer.extrusion_width)
        assert other.overhang_limit_degrees == pytest.approx(before.overhang_limit_degrees)


def test_a_new_process_does_not_relabel_the_previous_other_measurement(own_profiles: Path) -> None:
    """Eine neue Wandprobe macht keine alte Überhangprobe zur Messung an der neuen Düse."""
    original = profiles.make_profile("centauri-carbon-2", "petg")
    calibration.apply(
        calibration.from_measurements("petg", minimum_wall=0.55, overhang_angle=60.0),
        process=original,
    )
    other = dataclasses.replace(
        original, printer=dataclasses.replace(original.printer, nozzle_diameter=0.8)
    )
    after = calibration.apply(
        calibration.from_measurements("petg", minimum_wall=1.0), process=other
    )
    assert after.overhang_angle is None
    assert dataclasses.replace(other, material=after).minimum_wall_thickness == pytest.approx(1.0)


def test_process_measurements_require_their_print_process() -> None:
    with pytest.raises(ValidationError, match="Drucker"):
        calibration.apply(calibration.from_measurements("petg", minimum_wall=0.55))


def test_orientation_operation_and_agent_use_the_body_material(
    own_profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Projektprobe verbessert nicht die Druckbarkeit eines anderen Körpermaterials."""
    from app.core.agent import analysis
    from app.core.geom import prepare_ops
    from app.core.slice.orientation import search

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    after = calibration.apply(
        calibration.from_measurements("pla", overhang_angle=60.0), process=profile
    )
    measured = dataclasses.replace(profile, material=after)
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply("Körper", [OperationDraft(op="create_box", params={"height": 8.0})])
    first = evaluate(project.document, measured, sources=ProjectSources(project))
    body = first.scene.objects["obj_1"]
    body.material = "petg"
    seen: list[float] = []

    def actual_search(mesh, **kwargs):
        seen.append(kwargs["overhang_angle"])
        return search(mesh, **kwargs)

    monkeypatch.setattr(analysis, "search", actual_search)
    monkeypatch.setattr(prepare_ops, "search", actual_search)
    analysis.analysis_text("orientation", first.scene, project.document, measured)
    # Die Op erhält denselben tatsächlichen Körper über ihren normalen Kontext.
    from tests.test_brep import run

    result = run("orient_for_print", body, measured, thorough=True)
    assert result.outputs
    assert seen == pytest.approx([45.0, 45.0])


def test_calibration_changes_the_real_overhang_map_and_slice(own_profiles: Path) -> None:
    """Eine gedruckte 60-Grad-Probe ändert die Auskunft am echten 55-Grad-Körper."""
    import math

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge import print_settings
    from app.core.perceive import maps
    from app.core.slice.analysis import slice_body
    from app.core.types import SceneObject

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    process = profiles.for_process(profile, settings)
    calibration.apply(
        calibration.from_measurements("petg", minimum_wall=0.55, overhang_angle=60.0),
        process=process,
    )
    calibrated = profiles.for_process(profiles.make_profile("centauri-carbon-2", "petg"), settings)
    raw = trimesh.creation.box((8, 8, 8))
    raw.apply_translation((0, 0, 4))
    raw.vertices[:, 0] += raw.vertices[:, 2] * math.tan(math.radians(55))
    body = SceneObject(id="slope", name="Schräges Teil", mesh=MeshData.of(raw))

    def support(current: Profile) -> float:
        wall, angle = profiles.analysis_limits(current, body)
        assert maps.build("wall", body, profile=current).threshold == pytest.approx(wall)
        assert maps.build("overhang", body, profile=current).threshold == pytest.approx(angle)
        return slice_body(
            body.mesh,
            layer_height=current.printer.layer_height,
            overhang_angle=angle,
        ).support_volume

    assert support(process) > 0.0
    assert support(calibrated) == pytest.approx(0.0, abs=1e-6)
    changed = dataclasses.replace(
        settings,
        layers=dataclasses.replace(settings.layers, line_width=settings.layers.line_width * 1.5),
    )
    assert support(profiles.for_process(calibrated, changed)) > 0.0


def test_analysis_keeps_the_stricter_material_and_unknown_slots(own_profiles: Path) -> None:
    """Bemalung mit einem anderen Material erbt keine günstigere Druckprobe."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import MaterialSlot, SceneObject

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    after = calibration.apply(
        calibration.from_measurements("petg", minimum_wall=0.55, overhang_angle=60.0),
        process=profile,
    )
    measured = dataclasses.replace(profile, material=after)
    body = SceneObject(
        id="mixed", name="Mehrere Materialien", mesh=MeshData.of(trimesh.creation.box())
    )
    assert profiles.analysis_limits(measured, body) == pytest.approx((0.55, 60.0))
    for material_type in ("PLA", ""):
        body.material_slots = [
            MaterialSlot(0, "Gehäuse", material_type="PETG"),
            MaterialSlot(1, "Schrift", material_type=material_type),
        ]
        assert profiles.analysis_limits(measured, body) == pytest.approx((0.55, 60.0))
        body.mesh = MeshData.of(trimesh.creation.box(), slots=(0,) * 6 + (1,) * 6)
        assert profiles.analysis_limits(measured, body) == pytest.approx(
            (profile.minimum_wall_thickness, profile.overhang_limit_degrees)
        )
        body.mesh = MeshData.of(trimesh.creation.box())
    body.material_slots = [MaterialSlot(0, "Gehäuse", material_type="PETG")]
    body.mesh = MeshData.of(trimesh.creation.box(), slots=(0,) * 6 + (2,) * 6)
    assert profiles.analysis_limits(measured, body) == pytest.approx(
        (profile.minimum_wall_thickness, profile.overhang_limit_degrees)
    )


@pytest.mark.parametrize(
    "values", [{"minimum_wall": 0}, {"overhang_angle": 90}, {"clearance": float("nan")}]
)
def test_unusable_measurements_are_rejected_before_writing(own_profiles: Path, values) -> None:
    with pytest.raises(ValidationError):
        calibration.apply(
            calibration.from_measurements("petg", **values),
            process=profiles.make_profile("centauri-carbon-2", "petg"),
        )
    assert not (own_profiles / calibration.USER_MATERIALS).exists()


def test_the_shipped_profile_stays_untouched(own_profiles: Path) -> None:
    """Der Startbestand ist der Startbestand — und es bleibt offensichtlich,
    welches welches ist.
    """
    calibration.apply(calibration.from_measurements("petg", clearance=0.18))

    shipped = Path(profiles.__file__).parent / "data" / "materials.toml"
    assert "0.18" not in shipped.read_text(encoding="utf-8")


def test_an_unknown_material_is_refused() -> None:
    with pytest.raises(ValidationError):
        calibration.apply(calibration.from_measurements("gibtsnicht", clearance=0.2))


def test_a_value_that_does_not_belong_is_refused() -> None:
    with pytest.raises(ValidationError):
        calibration.apply(calibration.from_measurements("petg", nozzle=0.4))


def test_a_negative_measurement_is_refused() -> None:
    with pytest.raises(ValidationError):
        calibration.apply(calibration.from_measurements("petg", clearance=-0.1))


def test_a_press_fit_may_be_negative(own_profiles: Path) -> None:
    """Eine Presspassung ist mit Absicht Übermaß — die eine darf unter null
    liegen.
    """
    after = calibration.apply(calibration.from_measurements("petg", press=-0.08))

    assert after.press == pytest.approx(-0.08)


def test_calibration_reaches_existing_projects(own_profiles: Path, profile: Profile) -> None:
    """§28.3, §12: Toleranzen sind Verweise, alte Projekte folgen also mit."""
    from app.core.knowledge.parts.ops import PLAY_FIELD

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Grundkörper", [OperationDraft(op="create_box", params={"width": 30.0, "depth": 30.0})]
    )
    History(project.document).apply(
        "Passbohrung",
        [
            OperationDraft(
                op="insert_dowel",
                inputs=("obj_1",),
                # **Eine Stelle gehört dazu, seit der Baustein danach fragt.** Ohne
                # Fläche und ohne Position hält die Auswertung an und sagt, was
                # fehlt (Regel 21, seit dem 25.08.2026) — vorher landete der
                # Baustein still im Nullpunkt, und dieser Test nahm das Ergebnis.
                params={
                    "kind": "bore",
                    "diameter": 4.0,
                    "length": 6.0,
                    "at_feature": "face_top",
                    PLAY_FIELD: 0.0,
                },
            )
        ],
    )

    before = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    first = before.scene.objects["obj_1"].features["dowel_bore_1"].params["diameter"]

    calibration.apply(calibration.from_measurements("petg", clearance=0.40))

    after = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    second = after.scene.objects["obj_1"].features["dowel_bore_1"].params["diameter"]

    assert second > first
    assert second == pytest.approx(4.40, abs=0.01), "the calibrated play, not the shipped one"


# --- der Variantenerzeuger (§28.3) ----------------------------------------------------


def project_with_parameter() -> Project:
    project = new_project("centauri-carbon-2", "petg")
    project.document.parameters["spiel"] = Parameter(name="spiel", value=0.1, unit="mm")
    History(project.document).apply(
        "Zapfen",
        [OperationDraft(op="create_cylinder", params={"diameter": "=@spiel*10", "height": 8.0})],
    )
    return project


def test_four_variants_come_out_of_one_call(profile: Profile) -> None:
    """§28.3: vier Läufe mit gestaffeltem Spiel, angeordnet, in einem Zug."""
    project = project_with_parameter()

    made = variants.build(
        project.document,
        profile,
        parameter="spiel",
        first=0.10,
        step=0.05,
        count=4,
        sources=ProjectSources(project),
    )

    assert made.complete
    assert [entry.value for entry in made.variants] == pytest.approx([0.10, 0.15, 0.20, 0.25])
    scene = made.scene(profile)
    assert len(scene.objects) == 4


def test_the_variants_stand_next_to_each_other(profile: Profile) -> None:
    """Ein Druck — sie dürfen also nicht ineinander sitzen."""
    project = project_with_parameter()

    made = variants.build(
        project.document,
        profile,
        parameter="spiel",
        first=0.10,
        step=0.05,
        count=3,
        sources=ProjectSources(project),
    )
    scene = made.scene(profile)

    from itertools import pairwise

    boxes = sorted(
        (entry.mesh.bounds.minimum[0], entry.mesh.bounds.maximum[0])
        for entry in scene.objects.values()
    )
    for (_low, high), (following, _end) in pairwise(boxes):
        assert following >= high, "the next variant starts where the previous one ends"


def test_a_variant_is_named_after_its_value(profile: Profile) -> None:
    project = project_with_parameter()

    made = variants.build(
        project.document,
        profile,
        parameter="spiel",
        first=0.1,
        step=0.1,
        count=2,
        sources=ProjectSources(project),
    )
    names = [entry.name for entry in made.scene(profile).objects.values()]

    assert any("0.1" in name for name in names)
    assert any("0.2" in name for name in names)


def test_the_project_is_left_exactly_as_it_was(profile: Profile) -> None:
    """Ein Kalibrierlauf ist ein Druck, kein Konstruktionsschritt — der Stapel
    bleibt, wo er ist.
    """
    project = project_with_parameter()
    before = dataclasses.asdict(project.document.parameters["spiel"])
    ops_before = len(project.document.ops)

    variants.build(
        project.document,
        profile,
        parameter="spiel",
        first=0.5,
        step=0.5,
        count=2,
        sources=ProjectSources(project),
    )

    assert dataclasses.asdict(project.document.parameters["spiel"]) == before
    assert len(project.document.ops) == ops_before


def test_an_unknown_parameter_is_refused(profile: Profile) -> None:
    project = project_with_parameter()

    with pytest.raises(ValidationError):
        variants.build(project.document, profile, parameter="gibtsnicht", first=0.1, step=0.1)


def test_too_many_variants_are_refused(profile: Profile) -> None:
    project = project_with_parameter()

    with pytest.raises(ValidationError):
        variants.build(project.document, profile, parameter="spiel", first=0.1, step=0.1, count=50)


def test_the_values_can_be_read_before_the_run() -> None:
    assert variants.values(0.10, 0.05, 4) == (0.10, 0.15, 0.20, 0.25)


# --- der Dialog (§28.3, zweiter Schritt) ----------------------------------------------


def test_the_dialog_offers_exactly_the_fields_of_the_profile(own_profiles: Path) -> None:
    """Was sich messen lässt, ist das, was das Materialprofil hält — sonst
    nichts.
    """
    import pytest as _pytest

    _pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        QApplication([])
    from app.ui.dialogs import CalibrationDialog

    dialog = CalibrationDialog("petg")

    assert set(dialog.editors) == set(calibration.FIELDS)
    assert dialog.measured().material == "petg"


def test_the_dialog_starts_from_the_current_values(own_profiles: Path) -> None:
    import pytest as _pytest

    _pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        QApplication([])
    from app.ui.dialogs import CalibrationDialog

    current = profiles.material("petg")
    dialog = CalibrationDialog("petg")

    assert dialog.editors["clearance"].value() == pytest.approx(current.clearance)


def test_the_dialog_saves_only_explicitly_selected_process_measurements(
    own_profiles: Path, qt_app: object
) -> None:
    """Vorgabewerte werden erst nach ausdrücklicher Auswahl zu einer Messung."""
    pytest.importorskip("PySide6")
    from app.ui.dialogs import CalibrationDialog

    process = profiles.make_profile("centauri-carbon-2", "petg")
    dialog = CalibrationDialog("petg", process=process)
    assert qt_app is not None
    assert not calibration.PROCESS_FIELDS.intersection(dialog.measured().as_table())
    dialog.measured_fields["minimum_wall"].setChecked(True)
    dialog.editors["minimum_wall"].setValue(0.55)
    after = calibration.apply(dialog.measured(), process=dialog.process)
    assert after.minimum_wall == pytest.approx(0.55)
    assert after.overhang_angle is None
    dialog.close()

    again = CalibrationDialog("petg", process=dataclasses.replace(process, material=after))
    assert again.measured_fields["minimum_wall"].isChecked()
    assert again.editors["minimum_wall"].value() == pytest.approx(0.55)
    again.measured_fields["minimum_wall"].setChecked(False)
    unchanged = calibration.apply(again.measured(), process=again.process)
    assert unchanged.minimum_wall == pytest.approx(0.55)
    again.close()


@pytest.mark.parametrize(
    "edited,value",
    [
        (None, None),
        ("clearance", 0.3),
        ("press", -0.08),
        ("hole_compensation", 0.2),
        ("elephant_foot", 0.1),
        ("shrinkage", 0.75),
        ("minimum_wall", 0.65),
        ("overhang_angle", 61.25),
    ],
)
def test_calibration_keeps_unedited_precision_when_saving(
    own_profiles: Path, qt_app: object, edited: str | None, value: float | None
) -> None:
    """Anzeigepräzision darf beim Speichern keine anderen Messwerte verändern."""
    pytest.importorskip("PySide6")
    from app.ui.dialogs import CalibrationDialog

    original = {
        "clearance": 0.23456,
        "press": -0.05678,
        "hole_compensation": 0.12345,
        "elephant_foot": 0.15678,
        "shrinkage": 0.0045678,
        "minimum_wall": 0.5553,
        "overhang_angle": 60.1234,
    }
    process = profiles.make_profile("centauri-carbon-2", "petg")
    material = calibration.apply(calibration.from_measurements("petg", **original), process=process)
    dialog = CalibrationDialog("petg", process=dataclasses.replace(process, material=material))
    assert qt_app is not None
    try:
        assert dialog.editors["minimum_wall"].value() == pytest.approx(0.56)
        assert dialog.editors["overhang_angle"].value() == pytest.approx(60.12)
        assert dialog.editors["shrinkage"].value() == pytest.approx(0.46)
        expected = dict(original)
        if edited is not None:
            assert value is not None
            dialog.editors[edited].setValue(value)
            expected[edited] = value / 100.0 if edited == "shrinkage" else value
        after = calibration.apply(dialog.measured(), process=dialog.process)
        for name, precise in expected.items():
            assert getattr(after, name) == pytest.approx(precise, abs=1e-12, rel=0)
    finally:
        dialog.close()


def test_calibration_accepts_retyping_the_rounded_percentage(
    own_profiles: Path, qt_app: object
) -> None:
    """Das bewusste Eintippen des Anzeigewerts ersetzt den exakteren Altwert."""
    pytest.importorskip("PySide6")
    from PySide6.QtTest import QTest

    from app.ui.dialogs import CalibrationDialog

    calibration.apply(calibration.from_measurements("petg", shrinkage=0.0045678))
    dialog = CalibrationDialog("petg")
    assert qt_app is not None
    try:
        editor = dialog.editors["shrinkage"]
        line = editor.lineEdit()
        assert line is not None
        editor.selectAll()
        QTest.keyClicks(line, "0.46")
        editor.interpretText()
        assert dialog.measured().as_table()["shrinkage"] == pytest.approx(0.0046)
    finally:
        dialog.close()


def test_a_broken_user_toml_is_a_sentence_not_a_crash(own_profiles: Path) -> None:
    """Regel 17: Eine von Hand beschädigte Nutzerdatei — die fehlende Klammer
    ist der Normalfall, nicht der Sonderfall — war ein Startabbruch mit rohem
    Stapelabzug, denn `printer_profiles()` läuft beim Fensteraufbau."""
    own_profiles.mkdir(parents=True, exist_ok=True)
    (own_profiles / "printers.toml").write_text("[kaputt\n", encoding="utf-8")
    profiles.reload()

    with pytest.raises(ValidationError) as caught:
        profiles.printer_profiles()

    assert caught.value.suggestions
    assert "printers.toml" in str(caught.value.values.get("file", ""))

    (own_profiles / "printers.toml").unlink()
    profiles.reload()


def test_a_quoted_material_title_survives_the_calibration_file(
    own_profiles: Path, profile: Profile
) -> None:
    """Ein Anführungszeichen im Titel machte die Kalibrierdatei unlesbar —
    zusammen mit dem Leser darüber ein Startabbruch, aus dem nur das Löschen
    der Datei führte."""
    own_profiles.mkdir(parents=True, exist_ok=True)
    table = {"pla": {"title": 'PLA "matt"', "clearance": 0.3}}
    text = calibration._as_toml(table)
    (own_profiles / "materials.toml").write_text(text, encoding="utf-8")

    again = calibration._read(own_profiles / "materials.toml")

    assert again["pla"]["title"] == 'PLA "matt"'
    (own_profiles / "materials.toml").unlink()


def test_the_variants_report_progress_and_can_be_stopped(profile: Profile) -> None:
    """§2.8: zwölf Auswertungen sind über zwei Sekunden.

    Gerechnet wurde ohne Fortschritt und ohne Abbruch — der Dialog stand still,
    bis der letzte Lauf durch war, und zwar im Qt-Hauptthread. Beides geht jetzt
    durch: der gemeldete Anteil zählt über **alle** Läufe (ein Balken, der
    viermal von null hochläuft, sagt weniger als keiner), und der Abbruch wirkt
    zwischen den Läufen wie innerhalb eines Laufes.

    Was bis zum Abbruch fertig war, kommt zurück: ein halber Satz ist kein
    Kalibrierdruck, und wer abbricht, weiß das.
    """
    from app.core.scene.cancel import CancelSignal

    project = project_with_parameter()
    seen: list[float] = []

    made = variants.build(
        project.document,
        profile,
        parameter="spiel",
        first=0.10,
        step=0.05,
        count=3,
        sources=ProjectSources(project),
        progress=lambda share, _text: seen.append(share),
    )

    assert len(made.variants) == 3
    assert seen, "ohne Fortschritt sieht niemand, dass etwas läuft"
    assert seen == sorted(seen), f"der Anteil läuft zurück: {seen}"
    assert max(seen) <= 1.0 and max(seen) > 0.5, f"der Anteil kommt nicht an: {max(seen)}"

    # Abgebrochen, bevor der erste Lauf beginnt: nichts wird gerechnet.
    stop = CancelSignal()
    stop.cancel()
    nothing = variants.build(
        project.document,
        profile,
        parameter="spiel",
        first=0.10,
        step=0.05,
        count=3,
        sources=ProjectSources(project),
        cancelled=stop,
    )
    assert nothing.variants == [], "der Abbruch wurde nicht abgefragt"

    # Und mitten drin: der zweite Lauf kommt nicht mehr.
    late = CancelSignal()
    counted = 0

    def after_the_first(share: float, _text: str) -> None:
        nonlocal counted
        counted += 1
        if share >= 1 / 3:
            late.cancel()

    partial = variants.build(
        project.document,
        profile,
        parameter="spiel",
        first=0.10,
        step=0.05,
        count=3,
        sources=ProjectSources(project),
        progress=after_the_first,
        cancelled=late,
    )
    assert counted, "der Fortschritt kam nie an"
    assert 0 < len(partial.variants) < 3, (
        f"nach dem Abbruch stehen {len(partial.variants)} von 3 Varianten da"
    )


def _objects(project: Project) -> list[str]:
    """Die Objektkennungen in Stapelreihenfolge."""
    return [output for op in project.document.ops for output in op.outputs]


def test_a_variant_keeps_two_bodies_apart(profile: Profile) -> None:
    """Zwei Körper einer Variante behalten ihre Lage zueinander.

    Jeden einzeln auf den Versatz zu schieben legte bei „Dose mit Deckel"
    Deckel und Rumpf ineinander, und die gemeldete Breite war die des
    breitesten Einzelkörpers (Fund des Gesamtreviews vom 25.08.2026) — die
    Gruppe bekommt einen Versatz.
    """
    project = new_project("centauri-carbon-2", "petg")
    project.document.parameters["spiel"] = Parameter(name="spiel", value=0.1, unit="mm")
    History(project.document).apply(
        "Rumpf",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 10.0})],
    )
    History(project.document).apply(
        "Deckel daneben",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 4.0})],
    )
    lid = next(reversed(_objects(project)))
    History(project.document).apply(
        "Deckel verschieben",
        [OperationDraft(op="translate_object", inputs=(lid,), params={"dx": 30.0})],
    )

    made = variants.build(
        project.document,
        profile,
        parameter="spiel",
        first=0.10,
        step=0.05,
        count=2,
        sources=ProjectSources(project),
    )
    scene = made.scene(profile)
    assert len(scene.objects) == 4

    # Innerhalb jeder Variante dürfen sich die zwei Körper nicht überlappen —
    # ineinandergeschoben teilten sie denselben X-Bereich.
    from itertools import pairwise

    by_variant: dict[str, list[tuple[float, float]]] = {}
    for object_id, entry in scene.objects.items():
        suffix = object_id.rsplit("_", 1)[-1]
        by_variant.setdefault(suffix, []).append(
            (float(entry.mesh.bounds.minimum[0]), float(entry.mesh.bounds.maximum[0]))
        )
    for suffix, spans in by_variant.items():
        spans.sort()
        for (_low_a, high_a), (low_b, _high_b) in pairwise(spans):
            assert low_b >= high_a - 1e-6, f"Variante {suffix}: zwei Körper teilen denselben Raum"
