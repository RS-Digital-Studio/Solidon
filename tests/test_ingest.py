"""The input stage: six steps, a unit question, and hard import limits (§17.1, §32)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshCodec, MeshData, read_mesh
from app.core.ingest.loader import (
    MAX_FILE_BYTES,
    MAX_TRIANGLES,
    check_limits,
    detect_unit,
    normalise,
)
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import CachedResult, DiskCache
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def mesh_of(name: str) -> MeshData:
    return read_mesh((MESHES / name).read_bytes(), ".stl")


# --- unit heuristic -------------------------------------------------------------


def test_a_single_plausible_reading_needs_no_question() -> None:
    guess = detect_unit(mesh_of("cube_clean.stl").bounds.diagonal)
    assert guess.certain
    assert guess.unit == "mm"


def test_an_ambiguous_size_asks_instead_of_assuming() -> None:
    for name in ("bracket_inch.stl", "plate_cm.stl"):
        guess = detect_unit(mesh_of(name).bounds.diagonal)
        assert not guess.certain, name
        assert set(guess.candidates) >= {"cm", "in"}, name


def test_an_empty_model_offers_every_unit() -> None:
    guess = detect_unit(0.0)
    assert not guess.certain
    assert guess.candidates == ("mm", "cm", "in", "m")


# --- reading --------------------------------------------------------------------


def test_a_clean_cube_reads_as_twelve_triangles() -> None:
    """Reading is only reading: STL repeats every vertex, so the raw mesh is not
    yet watertight — that is exactly what step 2 of the input stage is for."""
    mesh = mesh_of("cube_clean.stl")
    assert mesh.triangle_count == 12
    assert mesh.vertex_count == 36
    assert not mesh.is_watertight
    assert mesh.volume == pytest.approx(8000.0)
    assert mesh.bounds.size == pytest.approx((20.0, 20.0, 20.0))


def test_an_unknown_format_is_refused_with_a_suggestion() -> None:
    with pytest.raises(ValidationError) as caught:
        read_mesh(b"whatever", ".xyz")
    assert caught.value.constraint == "unsupported_format"
    assert caught.value.suggestions


def test_a_damaged_file_is_reported_not_raised_raw() -> None:
    with pytest.raises(ValidationError) as caught:
        read_mesh(b"not an stl at all", ".stl")
    assert caught.value.constraint in ("unreadable", "no_geometry")


# --- the six steps --------------------------------------------------------------


def test_welding_turns_a_raw_stl_into_a_solid() -> None:
    result = normalise(mesh_of("cube_clean.stl"), "mm")
    assert result.mesh.triangle_count == 12
    assert result.mesh.vertex_count == 8, "the 36 repeated STL vertices were welded"
    assert result.mesh.is_watertight
    assert result.info.welded
    assert result.info.scale == pytest.approx(1.0)
    assert result.info.components == 1
    assert result.info.removed_triangles == 0
    assert result.mesh.volume == pytest.approx(8000.0)


def test_welding_can_be_switched_off() -> None:
    result = normalise(mesh_of("cube_clean.stl"), "mm", weld=False)
    assert not result.info.welded
    assert result.mesh.vertex_count == 36


def test_the_unit_is_converted_exactly_once() -> None:
    result = normalise(mesh_of("bracket_inch.stl"), "in")
    assert result.info.scale == pytest.approx(25.4)
    assert result.mesh.bounds.size == pytest.approx((101.6, 50.8, 6.35))
    assert "ingest.scaled" in {finding.code for finding in result.findings}


def test_degenerate_triangles_are_removed_and_reported() -> None:
    before = mesh_of("degenerate.stl")
    result = normalise(before, "mm")
    assert result.mesh.triangle_count < before.triangle_count
    assert result.info.removed_triangles > 0
    assert "ingest.degenerate_removed" in {finding.code for finding in result.findings}


def test_an_open_model_is_reported_not_repaired() -> None:
    result = normalise(mesh_of("broken_open.stl"), "mm")
    assert not result.mesh.is_watertight
    finding = next(f for f in result.findings if f.code == "ingest.not_watertight")
    assert finding.severity == "warning"


def test_small_components_are_reported_and_kept() -> None:
    before = mesh_of("two_components.stl")
    result = normalise(before, "mm")
    codes = {finding.code for finding in result.findings}
    assert "ingest.multiple_components" in codes
    assert "ingest.small_components" in codes
    assert result.info.components == 2
    assert result.mesh.triangle_count == before.triangle_count, "nothing is deleted silently"


def test_placing_on_the_bed_is_offered_not_forced() -> None:
    lying = normalise(mesh_of("cube_clean.stl"), "mm")
    assert lying.mesh.bounds.minimum[2] == pytest.approx(-10.0)

    placed = normalise(mesh_of("cube_clean.stl"), "mm", place_on_bed=True)
    assert placed.mesh.bounds.minimum[2] == pytest.approx(0.0)


def test_progress_is_reported_while_running() -> None:
    seen: list[float] = []
    normalise(
        mesh_of("cube_clean.stl"), "mm", progress=lambda fraction, text: seen.append(fraction)
    )
    assert seen and seen[-1] == pytest.approx(1.0)


# --- limits (§32) ---------------------------------------------------------------


def test_import_limits_are_stated_clearly() -> None:
    check_limits(1000, 1000)

    with pytest.raises(ValidationError) as big_file:
        check_limits(MAX_FILE_BYTES + 1, 10)
    assert big_file.value.constraint == "file_too_large"
    assert big_file.value.suggestions

    with pytest.raises(ValidationError) as many_triangles:
        check_limits(10, MAX_TRIANGLES + 1)
    assert many_triangles.value.constraint == "too_many_triangles"


# --- the load operation ---------------------------------------------------------


def project_with(name: str) -> Project:
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    project.sources["src_1"] = (MESHES / name).read_bytes()
    return project


def test_load_puts_a_named_object_into_the_scene(profile: Profile) -> None:
    project = project_with("cube_clean.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    body = result.scene.objects["obj_1"]
    assert body.name == "cube_clean"
    assert body.mesh.volume == pytest.approx(8000.0)
    assert body.created_by == 1


def test_load_asks_when_the_unit_is_ambiguous(profile: Profile) -> None:
    project = project_with("bracket_inch.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])
    asked: list[tuple[str, list[str]]] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append((question, choices))
        return "in"

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=ask)

    assert asked, "an ambiguous unit is a question, not a guess"
    assert "in" in asked[0][1]
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((101.6, 50.8, 6.35))


def test_the_answer_can_be_stored_in_the_operation(profile: Profile) -> None:
    """Storing the unit is what makes the question a one-off (§17.1)."""
    project = project_with("plate_cm.stl")
    history = History(project.document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "cm"})],
    )

    def refuse(question: str, choices: list[str]) -> str:
        raise AssertionError("a stored unit must not be asked for again")

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=refuse)
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((80.0, 50.0, 5.0))


def test_without_anyone_to_ask_the_chain_stops(profile: Profile) -> None:
    project = project_with("bracket_inch.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.stopped_at == 1, "guessing would be worse than stopping"
    assert any("AmbiguityError" in finding.code for finding in result.scene.report.findings)


def test_findings_of_the_input_stage_reach_the_report(profile: Profile) -> None:
    project = project_with("two_components.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "ingest.small_components" in codes
    assert all(finding.op_id == 1 for finding in result.scene.report.findings)


def test_an_unknown_source_is_a_user_error(profile: Profile) -> None:
    project = project_with("cube_clean.stl")
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_9"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.stopped_at == 1


def test_a_linked_source_is_read_relative_to_the_project(profile: Profile, tmp_path: Path) -> None:
    (tmp_path / "meshes").mkdir()
    (tmp_path / "meshes" / "cube_clean.stl").write_bytes((MESHES / "cube_clean.stl").read_bytes())
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path="meshes/cube_clean.stl",
        sha256="",
        embedded=False,
    )
    history = History(project.document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1"})])

    result = evaluate(project.document, profile, sources=ProjectSources(project, base_dir=tmp_path))
    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(8000.0)


# --- mesh hull ------------------------------------------------------------------


def test_a_mesh_survives_the_disk_cache_losslessly(tmp_path: Path) -> None:
    mesh = mesh_of("cube_clean.stl")
    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    from app.core.types import SceneObject

    disk.put("key", CachedResult(objects=(SceneObject(id="obj_1", name="Würfel", mesh=mesh),)))

    restored = disk.get("key")
    assert restored is not None
    assert restored.objects[0].mesh.triangle_count == 12
    assert restored.objects[0].mesh.volume == pytest.approx(8000.0)


def test_the_hull_exports_binary_stl() -> None:
    payload = mesh_of("cube_clean.stl").to_stl()
    assert read_mesh(payload, ".stl").triangle_count == 12
