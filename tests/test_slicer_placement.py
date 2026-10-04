"""Exportlokale Drucklagen und ihre sichtbaren Fehlerhandlungen, ohne Fenster."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh

from app.core import activation, build_area
from app.core.errors import AppError, ExternalToolError, OperationCancelled
from app.core.export import handover, writer
from app.core.geom import transform
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.scene.cancel import CancelSignal
from app.core.types import Finding, SceneObject


@pytest.fixture
def subject(tmp_path, monkeypatch):
    for key in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, str(tmp_path / "user"))
    monkeypatch.setattr(activation, "require", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        handover, "run_limited", lambda *_args, **_kwargs: pytest.fail("Kein Slicerstart")
    )
    profile = profiles.make_profile("prusa-mini", "pla")
    setup = handover.SlicerSetup(Path("prusa-slicer-console.exe"), "prusa")
    return writer, profile, setup


def body(name, size, *, angle=0.0, z=0.0, plate=0):
    raw = trimesh.creation.box(extents=size)
    raw.apply_translation((0, 0, size[2] / 2 + z))
    mesh = MeshData.of(raw, slots=tuple(i % 2 for i in range(len(raw.faces))))
    if angle:
        mesh = transform.apply(mesh, transform.rotation("z", angle))
    return SceneObject(name, name, mesh, plate=plate)


@pytest.mark.parametrize("kind", ("area", "height"))
def test_actual_limits_keep_an_already_valid_body(subject, kind):
    writer, profile, setup = subject
    profile = replace(
        profile,
        printer=replace(
            profile.printer,
            **(
                {"printable_area": ((-95, -95), (95, -95), (95, 95), (-95, 95))}
                if kind == "area"
                else {"printable_height": 200.0}
            ),
        ),
    )
    entry = body("valid", (188, 188, 10) if kind == "area" else (20, 20, 190))
    assert build_area.fits_on_bed(entry.mesh, profile.printer)
    planned, changed = writer.prepare_slicer_meshes([entry], profile, setup)
    assert not changed and planned[entry.id] is entry.mesh
    assert writer.arrangement_holds([entry.mesh], profile)


@pytest.mark.parametrize("kind", ("exclusion", "triangle"))
def test_shared_arrangement_predicate_uses_the_actual_contour(subject, kind):
    writer, profile, _setup = subject
    profile = replace(
        profile,
        printer=replace(
            profile.printer,
            **(
                {"bed_exclusions": (((-15, -15), (15, -15), (15, 15), (-15, 15)),)}
                if kind == "exclusion"
                else {"printable_area": ((-90, -90), (90, -90), (-90, 90))}
            ),
        ),
    )
    entry = body("outside", (20, 20, 10))
    if kind == "triangle":
        entry.mesh = transform.apply(entry.mesh, transform.translation((70, 0, 0)))
    assert not build_area.fits_on_bed(entry.mesh, profile.printer)
    assert not writer.arrangement_holds([entry.mesh], profile)


@pytest.mark.parametrize("size", ((300, 300, 10), (20, 20, 190)))
def test_size_refusal_precedes_packer_and_binds_object(subject, monkeypatch, size):
    writer, profile, setup = subject
    monkeypatch.setattr(
        writer, "arrange_on_bed", lambda *_a, **_kw: pytest.fail("Packer lief vor Größenprüfung")
    )
    objects = [body("first", (20, 20, 10)), body("offender", size)]
    with pytest.raises(ExternalToolError) as raised:
        writer.prepare_slicer_meshes(objects, profile, setup)
    assert raised.value.values["constraint"] == "slicer_build_volume"
    assert raised.value.object_id == "offender"
    assert raised.value.values["part_index"] == 1
    assert {"split_model", "scale_to_fit"} <= {action.id for action in raised.value.suggestions}


@pytest.mark.parametrize("case", ("rod", "half_degree", "half_turn_triangle"))
def test_rotation_finds_an_actual_pose_and_keeps_source(subject, case):
    writer, profile, setup = subject
    if case == "half_turn_triangle":
        profile = replace(
            profile,
            printer=replace(profile.printer, printable_area=((-90, -90), (90, -90), (-90, 90))),
        )
        raw = trimesh.convex.convex_hull(
            np.asarray([(x, y, z) for z in (0, 10) for x, y in ((-80, 80), (80, -80), (80, 80))])
        )
        entry = SceneObject("turn", "turn", MeshData.of(raw))
    else:
        entry = body(
            "turn",
            (200, 20, 10) if case == "rod" else (179, 169, 10),
            angle=0 if case == "rod" else 0.5,
        )
    before = entry.mesh.raw.vertices.copy()
    planned, changed = writer.prepare_slicer_meshes([entry], profile, setup)
    assert changed and build_area.fits_on_bed(planned[entry.id], profile.printer)
    assert writer.arrangement_holds(list(planned.values()), profile)
    np.testing.assert_array_equal(entry.mesh.raw.vertices, before)
    np.testing.assert_array_equal(entry.mesh.raw.faces, planned[entry.id].raw.faces)
    assert entry.mesh.slots == planned[entry.id].slots
    assert entry.mesh.volume == pytest.approx(planned[entry.id].volume, rel=1e-10)
    second, _ = writer.prepare_slicer_meshes([entry], profile, setup)
    np.testing.assert_array_equal(planned[entry.id].raw.vertices, second[entry.id].raw.vertices)


@pytest.mark.parametrize(
    "program", ["orca-slicer.exe", "bambu-studio.exe", "ElegooSlicer.exe", "CrealityPrint.exe"]
)
def test_programs_that_arrange_themselves_get_a_part_that_fits_only_turned_turned(subject, program):
    """Die Orca-Familie verschiebt beim Anordnen, sie dreht nicht.

    In der Slicer-Matrix (RM-312) passte die Waschschüssel (240 mal 200 mm) auf
    das 220er-Bett des K1 und des Kobra 2 nur um 14,5° gedreht; Solidons
    Vorprüfung ließ sie deshalb durch, Creality Print und OrcaSlicer sagten
    mit -50 ab. Hier passt ein 200-mm-Stab nur schräg aufs 180er-Bett. Was
    ungedreht irgendwo Platz hat, bleibt unberührt — die Lage gehört dort dem
    Slicer.
    """
    writer, profile, _setup = subject
    setup = handover.SlicerSetup(Path(program), "orca")
    rod = body("rod", (200, 20, 10))
    assert not build_area.fits_on_bed(rod.mesh, profile.printer)
    planned, changed = writer.prepare_slicer_meshes([rod], profile, setup)
    assert changed and build_area.fits_on_bed(planned[rod.id], profile.printer)
    assert rod.mesh.volume == pytest.approx(planned[rod.id].volume, rel=1e-10)

    shifted = body("shifted", (100, 20, 10))
    shifted.mesh = transform.apply(shifted.mesh, transform.translation((150, 0, 0)))
    assert not build_area.fits_on_bed(shifted.mesh, profile.printer)
    planned, changed = writer.prepare_slicer_meshes([shifted], profile, setup)
    assert not changed and planned[shifted.id] is shifted.mesh


def test_valid_diagonal_pose_is_unchanged(subject):
    writer, profile, setup = subject
    entry = body("turn", (200, 20, 10), angle=45)
    planned, changed = writer.prepare_slicer_meshes([entry], profile, setup)
    assert not changed and planned[entry.id] is entry.mesh


def packing_error(subject):
    writer, profile, setup = subject
    with pytest.raises(AppError) as raised:
        writer.prepare_slicer_meshes(
            [body("a", (100, 100, 10)), body("b", (100, 100, 10))], profile, setup
        )
    return raised.value


def test_packing_refusal_has_bound_context_without_selection_fallback(subject):
    problem = packing_error(subject)
    assert problem.values["constraint"] == "slicer_build_volume"
    assert problem.object_id is None
    actions = {action.id for action in problem.suggestions}
    assert {"arrange_on_bed", "choose_printer", "cancel"} <= actions
    assert not actions.intersection({"scale_to_fit", "split_model"})


@pytest.mark.parametrize("stale", (False, True))
def test_visible_error_action_closes_modal_before_scene_action(subject, monkeypatch, stale):
    from app.ui import print_settings_dialog as dialog

    problem = packing_error(subject)
    calls = []
    context = ("job",)
    fake = SimpleNamespace(
        _job_context=context,
        _print_context=lambda: ("new_job",) if stale else context,
        parentWidget=lambda: None,
        _failed_save_copies=None,
        _show_slicer_output=lambda *_a: None,
        _open_slicer_section=lambda *_a, **_kw: None,
        _open_printer_choice=lambda *_a: calls.append("printer_popup"),
        reject=lambda: calls.append("closed"),
    )
    monkeypatch.setattr(
        dialog,
        "handlers_of",
        lambda _parent: {"arrange_on_bed": lambda _problem: calls.append("scene_handler")},
    )
    handlers = dialog.PrintSettingsDialog.error_handlers(fake)
    handlers["arrange_on_bed"](problem)
    assert calls == ([] if stale else ["closed"])
    if not stale:
        assert fake.scene_action == ("arrange_on_bed", problem)
        handlers["choose_printer"](problem)
        assert calls[-1] == "printer_popup"


def test_cancellation_before_tessellation(subject, monkeypatch):
    writer, profile, setup = subject
    token = CancelSignal()
    token.cancel()
    monkeypatch.setattr(
        writer, "mesh_for_export", lambda *_a: pytest.fail("Vernetzung trotz Abbruch")
    )
    with pytest.raises(OperationCancelled):
        writer.prepare_slicer_meshes([body("a", (20, 20, 10))], profile, setup, cancelled=token)


def test_window_and_file_routes_still_write_oversized_parts(subject, tmp_path):
    writer, profile, setup = subject
    objects = [body("big", (300, 300, 10))]
    for route in ("window", "file"):
        target, _ = writer.write_assembly(
            objects,
            tmp_path / route,
            project_name="big",
            profile=profile,
            setup=setup,
            flavour="prusa",
            checked=[],
            for_window=route == "window",
            for_slicer=route != "file",
        )
        assert target.is_file()


def test_plate_preparation_binds_early_failure_to_the_chosen_part(subject, tmp_path, monkeypatch):
    from app.ui import print_settings_dialog as dialog

    _writer, profile, setup = subject
    objects = (body("another_plate", (400, 400, 10), plate=1), body("selected_bad", (300, 300, 10)))
    job = dialog._PlateJob(
        objects=objects,
        plates=(0,),
        folder=tmp_path,
        name="case",
        setup=setup,
        settings=print_settings.resolve(profile),
        profile=profile,
        slot_profiles={},
        with_settings=False,
    )
    with pytest.raises(ExternalToolError) as raised:
        dialog._prepare_plate(job, 0)
    assert raised.value.object_id == "selected_bad"
    assert raised.value.values["part_index"] == 0
    assert not list(tmp_path.glob("*.3mf"))


@pytest.mark.parametrize("pattern", (0, 1, 2))
@pytest.mark.parametrize("angle,size", ((0, (200, 20, 10)), (0.5, (179, 169, 10))))
def test_emitted_rotated_vertices_are_platform_identical(subject, pattern, angle, size):
    from tests.test_platform_identity import platform_noise

    writer, profile, setup = subject
    first = body("turn", size, angle=angle)
    baseline, _ = writer.prepare_slicer_meshes([first], profile, setup)
    second = body("turn", size, angle=angle)
    with platform_noise(pattern):
        noisy, _ = writer.prepare_slicer_meshes([second], profile, setup)
    np.testing.assert_array_equal(baseline["turn"].raw.vertices, noisy["turn"].raw.vertices)
    np.testing.assert_array_equal(baseline["turn"].raw.faces, noisy["turn"].raw.faces)


@pytest.mark.parametrize("pattern", (0, 1, 2))
def test_asymmetric_bed_turn_is_platform_identical(subject, pattern):
    from tests.test_platform_identity import platform_noise

    writer, profile, setup = subject
    profile = replace(
        profile, printer=replace(profile.printer, printable_area=((-90, -90), (90, -90), (-90, 90)))
    )
    raw = trimesh.convex.convex_hull(
        np.asarray([(x, y, z) for z in (0, 10) for x, y in ((-80, 80), (80, -80), (80, 80))])
    )
    first = SceneObject("turn", "turn", MeshData.of(raw.copy()))
    baseline, _ = writer.prepare_slicer_meshes([first], profile, setup)
    second = SceneObject("turn", "turn", MeshData.of(raw.copy()))
    with platform_noise(pattern):
        noisy, _ = writer.prepare_slicer_meshes([second], profile, setup)
    np.testing.assert_array_equal(baseline["turn"].raw.vertices, noisy["turn"].raw.vertices)


def test_rotated_output_preserves_face_colours_and_slots(subject):
    writer, profile, setup = subject
    entry = body("turn", (179, 169, 10), angle=0.5)
    colours = np.asarray(
        [(255, 0, 0, 255) if i % 2 else (0, 0, 255, 255) for i in range(12)], dtype=np.uint8
    )
    entry.mesh.raw.visual.face_colors = colours
    faces = entry.mesh.raw.faces.copy()
    source = entry.mesh.raw.vertices.copy()
    planned, changed = writer.prepare_slicer_meshes([entry], profile, setup)
    assert changed and planned["turn"].slots == entry.mesh.slots
    np.testing.assert_array_equal(planned["turn"].raw.visual.face_colors, colours)
    np.testing.assert_array_equal(planned["turn"].raw.faces, faces)
    np.testing.assert_array_equal(entry.mesh.raw.vertices, source)


def test_cancellation_during_candidate_search(subject, monkeypatch):
    writer, profile, setup = subject
    token = CancelSignal()
    real = writer._cli_turns

    def interrupted(mesh):
        for turn in real(mesh):
            token.cancel()
            yield turn

    monkeypatch.setattr(writer, "_cli_turns", interrupted)
    with pytest.raises(OperationCancelled):
        writer.prepare_slicer_meshes([body("turn", (200, 20, 10))], profile, setup, cancelled=token)


def test_an_unrelated_arrange_finding_survives_export(subject, tmp_path):
    writer, profile, setup = subject
    evidence = Finding(code="arrange.material_groups", severity="info", message="Material")
    outdated = Finding(code="arrange.collision", severity="warning", message="Kollision")
    _path, findings = writer.write_assembly(
        [body("a", (20, 20, 10)), body("b", (20, 20, 10))],
        tmp_path,
        project_name="parts",
        profile=profile,
        setup=setup,
        flavour="prusa",
        checked=[evidence, outdated],
    )
    assert evidence in findings and outdated not in findings


@pytest.mark.parametrize("kind", ("empty", "floating", "below", "touching"))
def test_shared_predicate_keeps_the_existing_bed_and_gap_guards(subject, kind):
    writer, profile, _setup = subject
    if kind == "empty":
        meshes = []
    elif kind == "floating":
        meshes = [body("a", (20, 20, 10), z=1).mesh]
    elif kind == "below":
        meshes = [body("a", (20, 20, 10), z=-1).mesh]
    else:
        meshes = [
            body("a", (20, 20, 10)).mesh,
            transform.apply(body("b", (20, 20, 10)).mesh, transform.translation((20, 0, 0))),
        ]
    assert not writer.arrangement_holds(meshes, profile)


def test_visible_arrange_action_moves_other_plates_and_one_undo_restores_all(subject):
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from app.ui.main_window import MainWindow

    _writer, profile, _setup = subject
    problem = packing_error(subject)
    assert str(problem.detail) == (
        "Für diese Teile wurde keine Anordnung auf einer Druckplatte gefunden. "
        "Sie können alle Teile des Projekts neu auf Platten anordnen "
        "oder einen größeren Drucker wählen."
    )
    load_operations()
    project = new_project("prusa-mini", "pla")
    document = project.document
    history = History(document)
    drafts = []
    for index, size in enumerate(((100, 100, 10), (100, 100, 10), (20, 20, 10)), 1):
        key = f"src_{index}"
        project.sources[key] = body(key, size).mesh.raw.export(file_type="stl")
        document.sources[key] = Source(id=key, kind="import", path=f"sources/{key}.stl", sha256="")
        drafts.append(OperationDraft(op="load", params={"source": key, "unit": "mm"}))
    history.apply("Laden", drafts)
    history.apply(
        "Platte wechseln",
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_3",),
                params={"dx": 60, "dy": 60, "plate": 2, "keep_on_bed": False},
            )
        ],
    )

    def current():
        result = evaluate(document, profile, sources=ProjectSources(project))
        assert result.complete
        return result

    before = current()
    original = {
        key: (entry.plate, entry.mesh.raw.vertices.copy())
        for key, entry in before.scene.objects.items()
    }
    calls = []

    def apply(title, drafts):
        calls.append((str(title), tuple(drafts)))
        history.apply(title, drafts)

    fake = SimpleNamespace(
        session=SimpleNamespace(last_result=before, apply=apply),
        _spacing_for=lambda _spec: {"spacing": 5, "plates": 12, "by_material": False},
    )
    MainWindow._arrange_after_error(fake, problem)
    assert len(calls) == 1 and len(calls[0][1]) == 1
    assert calls[0][1][0].inputs == ("obj_1", "obj_2", "obj_3")
    after = current()
    assert before.scene.objects["obj_3"].plate == 1
    assert after.scene.objects["obj_3"].plate == 0
    assert not np.array_equal(original["obj_3"][1], after.scene.objects["obj_3"].mesh.raw.vertices)
    undone = history.undo()
    assert undone is not None
    restored = current()
    for key, (plate, vertices) in original.items():
        assert restored.scene.objects[key].plate == plate
        np.testing.assert_array_equal(restored.scene.objects[key].mesh.raw.vertices, vertices)
