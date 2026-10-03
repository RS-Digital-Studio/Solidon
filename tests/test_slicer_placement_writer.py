"""Die geschriebenen CLI-Netze bewahren Form, Teile und Stützsperren."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core import activation, build_area
from app.core.brep import edit
from app.core.errors import AppError
from app.core.export import handover, writer
from app.core.geom.mesh import MeshData
from app.core.ingest import loader, threemf
from app.core.knowledge import print_settings, profiles
from app.core.types import SceneObject
from app.ui import print_settings_dialog as dialog

PROGRAMS = [
    ("prusa", "prusa-slicer-console.exe"),
    ("prusa", "SuperSlicer.exe"),
    ("cura", "CuraEngine.exe"),
]


@pytest.fixture(autouse=True)
def isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, str(tmp_path / "user"))
    monkeypatch.setattr(activation, "require", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handover, "run_limited", lambda *_a, **_kw: pytest.fail("Kein Slicerstart"))


def body(index: int, size=(40.0, 40.0, 10.0), x=0.0, plate=0) -> SceneObject:
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation((x, 0.0, size[2] / 2.0))
    return SceneObject(f"obj_{index}", f"Teil {index}", MeshData.of(mesh), plate=plate)


def read_written(
    target: Path, flavour: str, profile, *, machine_coordinates=True
) -> list[MeshData]:
    if target.suffix == ".3mf":
        meshes = [part.mesh for part in threemf.read_objects(target.read_bytes())]
        if machine_coordinates and flavour != "cura":
            shift = build_area.machine_shift(profile.printer)
            for mesh in meshes:
                mesh.raw.apply_translation((-shift[0], -shift[1], 0.0))
        return meshes
    return [
        loader.read_model(entry.path.read_bytes(), ".stl")
        for entry in handover.cura_meshes(target)
        if entry.settings.get("anti_overhang_mesh") != "true"
    ]


def export(objects, tmp_path, flavour, program, **options):
    profile = options.pop("profile", profiles.make_profile("prusa-mk4s", "pla"))
    return writer.write_assembly(
        objects,
        tmp_path,
        project_name="RM478",
        profile=profile,
        flavour=flavour,
        setup=handover.SlicerSetup(tmp_path / program, flavour),
        checked=[],
        **options,
    )


@pytest.mark.parametrize(("flavour", "program"), PROGRAMS)
def test_overlapping_parts_are_written_as_a_valid_plate_without_changing_the_scene(
    tmp_path, flavour, program
):
    objects = [body(1), body(2, size=(20.0, 30.0, 15.0))]
    profile = profiles.make_profile("prusa-mk4s", "pla")
    before = [entry.mesh.raw.vertices.copy() for entry in objects]
    assert not writer.arrangement_holds([entry.mesh for entry in objects], profile)

    target, findings = export(objects, tmp_path, flavour, program, place_on_bed=False)

    meshes = read_written(target, flavour, profile)
    assert len(meshes) == 2
    for old, entry in zip(before, objects, strict=True):
        np.testing.assert_array_equal(old, entry.mesh.raw.vertices)
    assert writer.arrangement_holds(meshes, profile), "CLI bekommt getrennte Teile im Bauraum"
    assert all(build_area.fits_on_bed(mesh, profile.printer) for mesh in meshes)
    assert sorted(mesh.volume for mesh in meshes) == pytest.approx(
        sorted(entry.mesh.volume for entry in objects), rel=1e-6
    )
    assert any(finding.code == "export.arranged_for_slicer" for finding in findings)


@pytest.mark.parametrize(("flavour", "program"), PROGRAMS)
def test_a_shifted_single_part_is_placed_for_the_cli(tmp_path, flavour, program):
    objects = [body(1, x=300.0)]
    profile = profiles.make_profile("prusa-mk4s", "pla")
    before = objects[0].mesh.raw.vertices.copy()
    target, _findings = export(objects, tmp_path, flavour, program, place_on_bed=False)
    meshes = read_written(target, flavour, profile)
    np.testing.assert_array_equal(before, objects[0].mesh.raw.vertices)
    assert writer.arrangement_holds(meshes, profile)


@pytest.mark.parametrize(("flavour", "program"), PROGRAMS)
def test_a_valid_arrangement_is_kept_exactly(tmp_path, flavour, program):
    objects = [body(1, x=-40.0), body(2, x=40.0)]
    profile = profiles.make_profile("prusa-mk4s", "pla")
    assert writer.arrangement_holds([entry.mesh for entry in objects], profile)
    target, findings = export(objects, tmp_path, flavour, program, place_on_bed=True)
    meshes = read_written(target, flavour, profile)
    for mesh, entry in zip(meshes, objects, strict=True):
        assert mesh.bounds.minimum == pytest.approx(entry.mesh.bounds.minimum, abs=1e-6)
        assert mesh.bounds.maximum == pytest.approx(entry.mesh.bounds.maximum, abs=1e-6)
    assert "export.arranged_for_slicer" not in {finding.code for finding in findings}


@pytest.mark.parametrize(("flavour", "program"), PROGRAMS)
@pytest.mark.parametrize("route", ["window", "file"])
def test_only_the_cli_path_changes_an_arrangement(tmp_path, flavour, program, route):
    objects = [body(1), body(2, size=(20.0, 20.0, 10.0))]
    profile = profiles.make_profile("prusa-mk4s", "pla")
    options = {"for_window": True} if route == "window" else {"for_slicer": False}
    target, findings = export(objects, tmp_path, flavour, program, place_on_bed=False, **options)
    meshes = read_written(target, flavour, profile, machine_coordinates=False)
    assert len(meshes) == 2
    centres = [mesh.bounds.centre for mesh in meshes]
    assert centres[0][:2] == pytest.approx(centres[1][:2]), "Fenster und Datei behalten Überlappung"
    assert "export.arranged_for_slicer" not in {finding.code for finding in findings}


@pytest.mark.parametrize(
    "program", ["orca-slicer.exe", "bambu-studio.exe", "ElegooSlicer.exe", "CrealityPrint.exe"]
)
def test_programs_that_arrange_themselves_keep_the_existing_handoff(tmp_path, program):
    objects = [body(1), body(2)]
    profile = profiles.make_profile("prusa-mk4s", "pla")
    target, findings = export(objects, tmp_path, "orca", program, place_on_bed=False)
    meshes = read_written(target, "orca", profile, machine_coordinates=False)
    assert meshes[0].bounds.centre == pytest.approx(meshes[1].bounds.centre)
    assert "export.arranged_for_slicer" not in {finding.code for finding in findings}


@pytest.mark.parametrize(("flavour", "program"), PROGRAMS)
def test_no_single_plate_arrangement_stops_the_cli_export_with_its_own_reason(
    tmp_path, flavour, program
):
    objects = [body(1, (100.0, 100.0, 10.0)), body(2, (100.0, 100.0, 10.0))]
    profile = profiles.make_profile("prusa-mini", "pla")
    before = [entry.mesh.raw.vertices.copy() for entry in objects]
    with pytest.raises(AppError) as raised:
        export(objects, tmp_path, flavour, program, profile=profile, place_on_bed=False)
    for old, entry in zip(before, objects, strict=True):
        np.testing.assert_array_equal(old, entry.mesh.raw.vertices)
    assert "arrange_on_bed" in {action.id for action in raised.value.suggestions}
    assert "platte" in str(raised.value.detail).casefold()
    assert "unmöglich" not in str(raised.value.detail).casefold()
    assert not list(tmp_path.glob("*.3mf")) and not list(tmp_path.glob("*.stl"))


@pytest.mark.parametrize(("flavour", "program"), PROGRAMS)
def test_only_the_selected_plate_is_locally_arranged(tmp_path, flavour, program):
    objects = [body(1), body(2), body(3, (400.0, 400.0, 10.0), plate=1)]
    profile = profiles.make_profile("prusa-mk4s", "pla")
    before = [entry.mesh.raw.vertices.copy() for entry in objects]
    target, _findings = export(objects, tmp_path, flavour, program, plate=0, place_on_bed=False)
    meshes = read_written(target, flavour, profile)
    assert len(meshes) == 2 and writer.arrangement_holds(meshes, profile)
    for old, entry in zip(before, objects, strict=True):
        np.testing.assert_array_equal(old, entry.mesh.raw.vertices)


def test_the_real_cura_support_blocker_follows_its_arranged_body(tmp_path):
    """Die echte Kanalberechnung sieht das Ausgabenetz in seiner neuen Lage."""
    outer = trimesh.creation.box(extents=(60.0, 40.0, 40.0))
    outer.apply_translation((0.0, 0.0, 20.0))
    tunnel = trimesh.creation.box(extents=(20.0, 50.0, 20.0))
    tunnel.apply_translation((0.0, 0.0, 18.0))
    channel = SceneObject(
        "obj_1", "Kanal", MeshData.of(trimesh.boolean.difference([outer, tunnel]))
    )
    objects = [channel, body(2)]
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )
    before = [entry.mesh.raw.vertices.copy() for entry in objects]

    target, _findings = export(
        objects, tmp_path, "cura", "CuraEngine.exe", place_on_bed=False, settings=settings
    )

    entries = handover.cura_meshes(target)
    models = [entry for entry in entries if entry.settings.get("anti_overhang_mesh") != "true"]
    blockers = [entry for entry in entries if entry.settings.get("anti_overhang_mesh") == "true"]
    assert len(models) == 2 and len(blockers) == 1
    meshes = [loader.read_model(entry.path.read_bytes(), ".stl") for entry in models]
    barrier = loader.read_model(blockers[0].path.read_bytes(), ".stl")
    assert writer.arrangement_holds(meshes, profile)
    assert barrier.bounds.centre[:2] == pytest.approx(meshes[0].bounds.centre[:2], abs=1e-5)
    assert barrier.bounds.centre[:2] != pytest.approx(meshes[1].bounds.centre[:2], abs=1e-5)
    for old, entry in zip(before, objects, strict=True):
        np.testing.assert_array_equal(old, entry.mesh.raw.vertices)


@pytest.mark.parametrize("with_comparison", [False, True])
def test_prepared_plate_and_writer_share_one_arranged_export_snapshot(
    tmp_path, monkeypatch, with_comparison
):
    profile = profiles.make_profile("prusa-mk4s", "pla")
    exact = replace(edit.cylinder(40.0, 10.0), deflection=0.5)
    objects = (
        SceneObject("exact", "Rundteil", exact, kind="brep"),
        body(2, (20.0, 20.0, 10.0)),
        body(3, (400.0, 400.0, 10.0), plate=1),
    )
    before = [entry.mesh.raw.vertices.copy() for entry in objects]
    settings = print_settings.with_accepted(
        print_settings.resolve(profile), "support.style", "auto"
    )
    job = dialog._PlateJob(
        objects=objects,
        plates=(0, 1),
        folder=tmp_path,
        name="RM478",
        setup=handover.SlicerSetup(tmp_path / "prusa-slicer-console.exe", "prusa"),
        settings=settings,
        profile=profile,
        slot_profiles={},
        with_settings=with_comparison,
        with_comparison=with_comparison,
    )
    captured = []
    comparisons = []
    resolved_parts = []
    original_values = writer._part_values
    expected_comparison = dialog.PlateComparison(0, None, None)

    def compare(plate, parts, actual_profile, **kwargs):
        comparisons.append((plate, tuple(parts), actual_profile, kwargs))
        return expected_comparison

    def values(*args, **kwargs):
        result = original_values(*args, **kwargs)
        resolved_parts.append(result.effective)
        return result

    monkeypatch.setattr(dialog, "plate_comparison", compare)
    monkeypatch.setattr(writer, "_part_values", values)
    original_write = dialog.write_assembly

    def observed(*args, **kwargs):
        captured.append(kwargs.get("mesh_plan"))
        return original_write(*args, **kwargs)

    monkeypatch.setattr(dialog, "write_assembly", observed)
    run = dialog._prepare_plate(job, 0)

    assert len(captured) == 1 and captured[0] is not None, "Der gemeinsame Netzplan fehlt"
    planned, changed = captured[0]
    assert changed is True
    assert tuple(planned) == ("exact", "obj_2")
    assert all(
        mesh is planned[entry.id] for mesh, entry in zip(run.meshes, objects[:2], strict=True)
    )
    assert run.meshes[0].triangle_count > exact.triangle_count
    assert run.keep_arrangement is True
    assert writer.arrangement_holds(run.meshes, profile)
    written = read_written(run.model, "prusa", profile)
    for mesh, prepared in zip(written, run.meshes, strict=True):
        assert mesh.triangle_count == prepared.triangle_count
        assert mesh.bounds.minimum == pytest.approx(prepared.bounds.minimum, abs=1e-5)
        assert mesh.bounds.maximum == pytest.approx(prepared.bounds.maximum, abs=1e-5)
    for old, entry in zip(before, objects, strict=True):
        np.testing.assert_array_equal(old, entry.mesh.raw.vertices)

    if with_comparison:
        assert len(comparisons) == 1
        plate, parts, actual_profile, options = comparisons[0]
        assert plate == run.plate == 0 and actual_profile is profile
        assert options == {
            "keep_arrangement": True,
            "separate_objects": True,
            "cancelled": job.cancelled,
        }
        assert tuple(entry.id for entry, _mesh, _settings in parts) == run.object_ids
        for (entry, mesh, effective), prepared, original in zip(
            parts, run.meshes, objects[:2], strict=True
        ):
            assert entry.id == original.id
            assert entry.mesh is original.mesh
            assert mesh is prepared
            assert mesh is not original.mesh
            assert effective.support.style == "auto"
        # Keines der Teile verlangt Stützen: Erst der endgültige Writerweg
        # verteilt den übernommenen Vorschlag auf beide. Der Vergleich muss
        # diesen letzten Stand bekommen, nicht die vorherige Grundlage.
        assert resolved_parts
        assert all(value.support.style == "none" for value in resolved_parts)
        assert any(
            finding.code == "export.part_setting_all"
            and finding.values["setting"] == "support.style"
            for finding in run.findings
        )
        assert run.comparison is expected_comparison
    else:
        assert comparisons == [] and run.comparison is None
