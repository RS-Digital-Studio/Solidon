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


@pytest.mark.parametrize("name", ["fit_ladder", "wall_ladder", "overhang_fan"])
def test_a_test_body_prints_as_one_piece(name: str) -> None:
    """Ein Kalibrierkörper, der auf der Platte auseinanderfällt, misst nichts."""
    spec = PARTS.get(name)
    result = spec.fn(spec.params())

    assert result.mesh.is_watertight
    assert result.mesh.component_count == 1
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
                params={"kind": "bore", "diameter": 4.0, "length": 6.0, PLAY_FIELD: 0.0},
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
