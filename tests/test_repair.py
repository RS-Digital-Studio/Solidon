"""Repair against the broken files in the corpus (Bauplan §25, §34)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.geom.mesh import read_mesh
from app.core.geom.repair import (
    fill_holes,
    merge_vertices,
    open_edge_count,
    remove_degenerate_faces,
    remove_small_components,
    repair,
    unify_normals,
)
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def raw(name: str):
    """Straight from the file — unwelded, as STL delivers it."""
    return read_mesh((MESHES / name).read_bytes(), ".stl")


def test_welding_turns_loose_triangles_into_a_body() -> None:
    mesh, removed = merge_vertices(raw("cube_clean.stl"))

    assert removed == 28, "36 STL vertices become 8"
    assert mesh.is_watertight


def test_degenerate_triangles_go_away() -> None:
    mesh, removed = remove_degenerate_faces(merge_vertices(raw("degenerate.stl"))[0])

    assert removed > 0
    assert mesh.triangle_count == 12, "the cube stays, the junk goes"


def test_filling_closes_a_single_missing_triangle() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    with_hole = body.replacing(body.raw.submesh([range(1, 12)], append=True))
    assert not with_hole.is_watertight

    closed, worked = fill_holes(with_hole)

    assert worked
    assert closed.is_watertight
    assert closed.volume == pytest.approx(8000.0, rel=1e-6)


def test_filling_reaches_its_limit_on_a_missing_wall() -> None:
    """§34: broken_open.stl is missing three faces — that is a wall, not a hole.

    Triangle-sized holes are closed; a missing wall is what the voxel stage of
    the fallback chain is for (§17.2). Until then the finding says so plainly.
    """
    body, _welded = merge_vertices(raw("broken_open.stl"))
    assert open_edge_count(body) > 0

    result = repair(body)

    assert not result.mesh.is_watertight
    assert "repair.still_open" in {finding.code for finding in result.findings}


def test_filling_a_closed_body_changes_nothing() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    same, worked = fill_holes(body)

    assert not worked
    assert same is body


def test_unifying_normals_reports_only_a_real_change() -> None:
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    _mesh, flipped = unify_normals(body)
    assert not flipped, "a clean cube has nothing to correct"


def test_small_components_go_only_when_asked() -> None:
    body, _welded = merge_vertices(raw("two_components.stl"))
    assert body.component_count == 2

    kept = repair(body)
    assert kept.mesh.component_count == 2, "nothing is deleted unasked (§17.1)"

    dropped = repair(body, small_components=True)
    assert dropped.mesh.component_count == 1
    assert "repair.components_removed" in {finding.code for finding in dropped.findings}


def test_removing_small_components_keeps_the_big_one() -> None:
    body, _welded = merge_vertices(raw("two_components.stl"))
    mesh, dropped = remove_small_components(body)

    assert dropped == 1
    assert mesh.volume == pytest.approx(8000.0, rel=1e-3)


def test_repair_reports_every_step_it_took() -> None:
    result = repair(raw("degenerate.stl"))

    codes = {finding.code for finding in result.findings}
    assert "repair.welded" in codes
    assert "repair.degenerate_removed" in codes
    assert result.changed


def test_repair_says_when_it_could_not_close_the_body() -> None:
    """An honest "still open" beats a silent half repair."""
    body, _welded = merge_vertices(raw("cube_clean.stl"))
    half = body.replacing(body.raw.submesh([range(0, 6)], append=True))

    result = repair(half, holes=False)
    assert "repair.still_open" in {finding.code for finding in result.findings}


# --- as an operation ------------------------------------------------------------


def test_repair_runs_as_an_operation(document: Document, profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/broken_open.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "broken_open.stl").read_bytes()

    history = History(document)
    history.apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    codes = {finding.code for finding in result.scene.report.findings}
    assert "repair.still_open" in codes, "the missing wall is reported, not glossed over"
    assert result.scene.objects["obj_1"].created_by == 2, "the repair produced the object"


def test_the_repair_operation_is_registered_completely() -> None:
    spec = REGISTRY.get("repair")
    assert spec.category == "repair"
    assert (spec.consumes, spec.produces) == (1, 1)
    front = [entry.name for entry in spec.params.spec() if entry.placement == "front"]
    assert front == ["fill_holes"], "§2.4: the front side holds what people actually change"
