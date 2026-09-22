"""Resin-Stufe 1 (RM-071, Konzept ``konzepte/konzept-resin-2026-08.md`` §4, §9).

Bis zum 22.09.2026 setzte Solidon einen FDM-Drucker voraus, ohne je danach zu
fragen. Diese Datei hält die acht Abnahmepunkte der ersten Stufe: das
Verfahren im Profil, die zwei zentralen Eigenschaften, den Geltungsbereich der
neun FDM-Befunde, die Mindestwand aus dem Profil, den Bauraum, das Material
je Verfahren, den Export ohne Übersetzung — und dass ein Nutzerprofil ohne
Verfahrensangabe als FDM lädt, ohne Migration.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.export import handover
from app.core.export.writer import mesh_for_export, plan_export, write_assembly
from app.core.geom import hollow, orient
from app.core.geom.mesh import read_mesh
from app.core.knowledge import print_settings, profiles
from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.scene.hashing import profile_key
from app.core.scene.project import ProjectSources, new_project
from app.core.slice import advise
from app.core.types import Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"

#: Die neun Befunde aus B4 des Konzepts — an einem Resin-Projekt kommt keiner vor.
FDM_ONLY_CODES = frozenset(
    {
        "hollow.wall_below_nozzle",
        "settings.wall_below_nozzle",
        "prepare.elephant_foot",
        "orient.support_likely",
        "slice.long_bridge",
        "settings.warping_material_open_printer",
        "settings.uncalibrated_material",
        "arrange.filament_changes",
        "arrange.adhesion_too_close",
    }
)


@pytest.fixture
def resin() -> Profile:
    return profiles.make_profile(profiles.DEFAULT_RESIN_PRINTER, profiles.DEFAULT_RESIN_MATERIAL)


@pytest.fixture
def fdm() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


# --- Das Verfahren im Profil (Abnahme 1) ----------------------------------------


def test_the_two_resin_printers_ship_with_the_measures_of_their_technology() -> None:
    small = profiles.printer("generic-resin-130")
    large = profiles.printer("generic-resin-220")
    for printer in (small, large):
        assert printer.is_resin
        assert printer.nozzle_diameter == 0.0 and printer.extrusion_width == 0.0
        assert printer.pixel_size == pytest.approx(0.05)
        assert printer.minimum_wall == pytest.approx(0.4)
        assert printer.layer_height == pytest.approx(0.05)
        assert printer.bed_temperature_max == 0 and printer.nozzle_temperature_max == 0
    # Klein wie Mars und Photon Mono, groß wie Saturn und Photon M
    # (Entscheidung 30.08.2026: zwei Bauräume, weil der Bauraum die häufigste
    # Resin-Fehlerquelle ist).
    assert small.build_volume == pytest.approx((130.0, 80.0, 160.0))
    assert large.build_volume == pytest.approx((220.0, 120.0, 220.0))
    assert not profiles.printer(profiles.DEFAULT_PRINTER).is_resin


def test_a_user_profile_without_a_technology_loads_as_fdm_without_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jedes vor dem 22.09.2026 angelegte Profil ist ein FDM-Drucker."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    (tmp_path / "printers.toml").write_text(
        '["user-alt"]\n"title" = "Alt"\n"build_volume" = [200.0, 200.0, 200.0]\n'
        '"nozzle_diameter" = 0.6\n',
        encoding="utf-8",
    )
    profiles.reload()
    try:
        old = profiles.printer("user-alt")
        assert old.technology == "fdm" and not old.is_resin
        assert old.nozzle_diameter == pytest.approx(0.6)
        assert old.pixel_size == 0.0 and old.minimum_wall == 0.0
    finally:
        profiles.reload()


def test_a_saved_resin_printer_keeps_its_technology_and_refuses_a_missing_pixel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    template = profiles.printer(profiles.DEFAULT_RESIN_PRINTER)
    saved = profiles.save_printer(
        replace(template, id="user-mars", title="Mars", pixel_size=0.035, minimum_wall=0.5)
    )
    try:
        assert saved.is_resin and saved.pixel_size == pytest.approx(0.035)
        profiles.reload()
        again = profiles.printer("user-mars")
        assert again.is_resin and again.minimum_wall == pytest.approx(0.5)
        assert again.nozzle_diameter == 0.0
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            profiles.save_printer(replace(template, id="user-broken", title="X", pixel_size=0.0))
    finally:
        profiles.reload()


def test_an_unknown_technology_in_a_profile_file_is_refused_with_the_file_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.errors import ValidationError

    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    (tmp_path / "printers.toml").write_text(
        '["user-x"]\n"title" = "X"\n"build_volume" = [200.0, 200.0, 200.0]\n'
        '"technology" = "laser"\n',
        encoding="utf-8",
    )
    profiles.reload()
    try:
        with pytest.raises(ValidationError) as raised:
            profiles.printer_profiles()
        assert raised.value.suggestions
    finally:
        profiles.reload()


# --- Die zwei zentralen Eigenschaften (B2) und die Mindestwand (Abnahme 3) -------


def test_the_central_properties_come_from_the_technology(resin: Profile, fdm: Profile) -> None:
    assert resin.minimum_wall_thickness == pytest.approx(0.4)
    assert fdm.minimum_wall_thickness == pytest.approx(2.0 * 0.42)
    # Ein belichtetes Voxel gegen ein Stück Bahn.
    assert resin.smallest_printable_volume == pytest.approx(0.05**2 * 0.05)
    assert fdm.smallest_printable_volume == pytest.approx(0.42**2 * 0.2)
    # Kein Standgebot für ein Teil, das an Stützen hängt.
    assert resin.smallest_first_layer == 0.0
    assert fdm.smallest_first_layer > 0.0
    assert resin.printer.smallest_detail == pytest.approx(0.05)
    assert fdm.printer.smallest_detail == pytest.approx(0.42)


def test_a_half_millimetre_wall_passes_the_resin_profile_and_not_the_fdm_one(
    resin: Profile, fdm: Profile
) -> None:
    """Abnahme 3: 0,5 mm Wand meldet am Resin-Profil nichts, am FDM-Profil weiterhin."""
    assert hollow.below_printable_wall(0.5, resin) is None
    warned = hollow.below_printable_wall(0.5, fdm)
    assert warned is not None and warned.code == "hollow.wall_below_nozzle"
    # Und unter der Resin-Grenze heißt der Befund nicht „Düse".
    thin = hollow.below_printable_wall(0.2, resin)
    assert thin is not None and thin.code == "hollow.wall_below_minimum"
    assert "Düse" not in str(thin.message)


def test_a_resin_calibration_binds_to_the_layer_height_not_to_a_nozzle(resin: Profile) -> None:
    measured = replace(
        resin.material,
        minimum_wall=0.6,
        calibration_printer=resin.printer.id,
        calibration_layer_height=resin.printer.layer_height,
    )
    calibrated = Profile(printer=resin.printer, material=measured)
    assert calibrated.has_process_calibration
    assert calibrated.minimum_wall_thickness == pytest.approx(0.6)
    other_layer = Profile(printer=replace(resin.printer, layer_height=0.1), material=measured)
    assert not other_layer.has_process_calibration
    assert other_layer.minimum_wall_thickness == pytest.approx(0.4)


# --- Der Geltungsbereich der neun Befunde (Abnahme 2 und 6) ------------------------


def test_the_advice_axis_is_silent_for_resin(resin: Profile, fdm: Profile) -> None:
    settings = print_settings.resolve(resin)
    assert settings.layers.layer_height == pytest.approx(0.05)
    assert settings.layers.line_width == pytest.approx(0.05)
    assert advise.advise(settings, resin) == []
    assert advise.warnings_for(settings, resin) == []
    # Am FDM-Profil bleibt der Startwert-Hinweis, wie er war.
    assert "settings.uncalibrated_material" in {
        entry.code for entry in advise.warnings_for(print_settings.resolve(fdm), fdm)
    }


def test_no_fdm_only_code_reaches_a_resin_project_on_way_one(
    tmp_path: Path, resin: Profile
) -> None:
    """Weg 1 mit Resin-Profil, Ende zu Ende: Laden, Reparieren, Ausrichten,
    Aushöhlen, Exportieren — und im ganzen Bericht keine FDM-Aussage."""
    project = new_project(resin.printer.id, resin.material.id)
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "cube_clean.stl").read_bytes()
    history = History(project.document)
    history.apply(
        _("Modell laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])
    history.apply(
        _("Aushöhlen"),
        [OperationDraft(op="hollow_object", inputs=("obj_1",), params={"wall": 0.5})],
    )
    history.apply(_("Auf das Bett setzen"), [OperationDraft(op="place_on_bed", inputs=("obj_1",))])
    result = evaluate(
        project.document,
        resin,
        sources=ProjectSources(project),
        cache=ResultCache(),
        ask=lambda question, choices: choices[0],
    )
    assert result.complete
    codes = {finding.code for finding in result.scene.report.findings}
    assert codes, "der Eingang hat immer etwas zu sagen"
    assert not codes & FDM_ONLY_CODES, sorted(codes & FDM_ONLY_CODES)
    assert "hollow.wall_below_nozzle" not in codes and "hollow.wall_below_minimum" not in codes

    objects = list(result.scene.objects.values())
    turned = orient.orient_for_print(objects[0].mesh, printer=resin.printer)  # type: ignore[arg-type]
    assert not {entry.code for entry in turned.findings} & FDM_ONLY_CODES

    plan = plan_export(
        objects, project_name="Harz", profile=resin, sources=project.document.sources
    )
    assert not {entry.code for entry in plan.findings} & FDM_ONLY_CODES

    # Auch mit einem FDM-Satz in der Hand schreibt die Baugruppe für Harz
    # keine Haftungs- und Filamentbefunde und keine Beilage.
    written, findings = write_assembly(
        objects,
        tmp_path,
        project_name="Harz",
        profile=resin,
        settings=print_settings.resolve(resin),
        for_slicer=False,
    )
    assert written.is_file()
    assert not {entry.code for entry in findings} & FDM_ONLY_CODES
    assert not [entry for entry in findings if entry.code.startswith("slicer.")]


def test_the_overhang_heuristic_still_speaks_for_fdm(fdm: Profile) -> None:
    """Die Gegenprobe zum Geltungsbereich: derselbe Weg am FDM-Profil meldet weiter."""
    mesh = read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl")
    turned = orient.orient_for_print(mesh, printer=fdm.printer)
    assert {entry.code for entry in turned.findings} >= {"orient.heuristic"}


# --- Der Cache-Schlüssel trennt die Verfahren (Konzept §10) -------------------------


def test_the_profile_key_tells_resin_from_fdm(resin: Profile, fdm: Profile) -> None:
    assert profile_key(resin) != profile_key(fdm)
    finer = replace(resin, printer=replace(resin.printer, pixel_size=0.035))
    assert profile_key(finer) != profile_key(resin)


# --- Material je Verfahren (Abnahme 5, 6) -------------------------------------------


def test_the_material_follows_the_technology_of_the_printer() -> None:
    assert profiles.default_material_for(profiles.DEFAULT_RESIN_PRINTER) == "resin"
    assert profiles.default_material_for(profiles.DEFAULT_PRINTER) == "pla"
    assert profiles.material_for(profiles.DEFAULT_RESIN_PRINTER, "pla") == "resin"
    assert profiles.material_for("prusa-mk4s", "resin") == "pla"
    assert profiles.material_for("prusa-mk4s", "petg") == "petg"
    assert profiles.material_for("unbekannt", "petg") == "petg"
    assert profiles.material("resin").technology == "resin"
    assert profiles.material("resin").fits(profiles.printer(profiles.DEFAULT_RESIN_PRINTER))
    assert not profiles.material("pla").fits(profiles.printer(profiles.DEFAULT_RESIN_PRINTER))


# --- Die Exportauflösung (Abnahme 7, §29/§30) ------------------------------------------


def test_the_export_deflection_follows_the_smallest_detail(resin: Profile, fdm: Profile) -> None:
    from app.core.units import MAX_FACET_SAG

    assert fdm.export_deflection == pytest.approx(MAX_FACET_SAG)
    assert resin.export_deflection == pytest.approx(0.05 / 8.0)
    blind = replace(resin, printer=replace(resin.printer, pixel_size=0.0))
    assert blind.export_deflection == pytest.approx(MAX_FACET_SAG)


def test_an_exact_body_is_exported_finer_for_a_resin_printer(
    tmp_path: Path, resin: Profile, fdm: Profile
) -> None:
    """Dieselbe Kugel, zwei Drucker: Die Datei für das Harzbad trägt mehr
    Dreiecke, und der Bericht sagt es; die für die Düse bleibt, wie der Kern
    sie vernetzt."""
    from tests.helpers import exact_kernel

    exact_kernel()
    from app.core.brep import edit

    body = edit.sphere(10.0)
    own = mesh_for_export(body, fdm)
    finer = mesh_for_export(body, resin)
    assert own.triangle_count == body.to_mesh().triangle_count
    assert finer.triangle_count > 2 * own.triangle_count
    # Feiner heißt näher an der Kugel: 4/3 π r³ bei r = 5.
    true_volume = 4.0 / 3.0 * math.pi * 5.0**3
    assert abs(finer.volume - true_volume) < abs(own.volume - true_volume)
    assert abs(finer.volume - true_volume) / true_volume < 0.005

    from app.core.types import SceneObject

    entry = SceneObject(id="obj_1", name="Kugel", kind="brep", mesh=body)
    plan = plan_export([entry], project_name="Kugel", profile=resin)
    assert plan.entries[0].mesh.triangle_count == finer.triangle_count
    told = [finding for finding in plan.findings if finding.code == "export.tessellated"]
    assert told and told[0].values["deflection_mm"] == pytest.approx(resin.export_deflection)
    plain = plan_export([entry], project_name="Kugel", profile=fdm)
    assert plain.entries[0].mesh.triangle_count == own.triangle_count
    assert not [finding for finding in plain.findings if finding.code == "export.tessellated"]
    # STEP trägt den exakten Körper — dort wird nichts vernetzt und nichts gesagt.
    step = plan_export([entry], project_name="Kugel", profile=resin, export_format="step")
    assert not [finding for finding in step.findings if finding.code == "export.tessellated"]


# --- Die Übergabe per Öffnen ohne Übersetzung (Abnahme 7) ---------------------------


def test_a_resin_slicer_is_a_program_that_only_opens(resin: Profile) -> None:
    setup = handover.detect(Path("LycheeSlicer.exe"))
    assert handover.only_opens(setup)
    assert handover.machine_missing(setup, resin) == []
    assert handover.setting_limitations(setup.flavour) == []
