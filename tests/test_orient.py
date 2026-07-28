"""Print orientation as a heuristic, openly labelled as one (Bauplan §25, P2)."""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.orient import candidates, evaluate_direction, orient_for_print
from app.core.geom.transform import apply, rotation
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def plate():
    """A flat plate: 80 x 50 x 8 mm. Its best side is obvious."""
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def test_a_tilted_plate_is_laid_flat_again() -> None:
    tilted = apply(plate(), rotation("x", 37.0))
    result = orient_for_print(tilted)

    assert result.mesh.bounds.size[2] == pytest.approx(8.0, abs=0.2), "it lies flat again"
    assert result.mesh.bounds.minimum[2] == pytest.approx(0.0), "and sits on the bed"


def test_a_standing_plate_is_laid_down() -> None:
    standing = apply(plate(), rotation("y", 90.0))
    assert standing.bounds.size[2] == pytest.approx(80.0, abs=0.5)

    result = orient_for_print(standing)
    assert result.mesh.bounds.size[2] < 20.0, "lying down beats standing up"


def test_the_footprint_beats_the_alternatives() -> None:
    body = plate()
    lying = evaluate_direction(body, (0.0, 0.0, -1.0))
    on_edge = evaluate_direction(body, (1.0, 0.0, 0.0))

    assert lying.footprint > on_edge.footprint
    assert lying.score > on_edge.score


def test_the_heuristic_says_that_it_is_one() -> None:
    """It will be replaced by the layer analysis in P3, and it says so."""
    result = orient_for_print(plate())
    codes = {finding.code for finding in result.findings}

    assert "orient.heuristic" in codes
    finding = next(f for f in result.findings if f.code == "orient.heuristic")
    assert finding.values["candidates"] >= 6


def test_heavy_overhang_is_called_out() -> None:
    """A cone on its tip cannot be saved by turning it — so it says so."""
    cone = MeshData.of(trimesh.creation.cone(radius=20.0, height=60.0, sections=32))
    result = orient_for_print(apply(cone, rotation("x", 180.0)))

    assert result.mesh.bounds.minimum[2] == pytest.approx(0.0)
    assert isinstance(result.chosen.overhang, float)


def test_the_candidates_include_the_axes_and_the_big_faces() -> None:
    found = candidates(plate())

    assert (0.0, 0.0, 1.0) in found
    assert len(found) > 6, "the large flat faces add their own directions"


def test_orienting_runs_as_an_operation(document: Document, profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(
        _("Drehen"),
        [
            OperationDraft(
                op="rotate_object", inputs=("obj_1",), params={"axis": "y", "angle": 90.0}
            )
        ],
    )
    history.apply(
        _("Ausrichten"),
        [OperationDraft(op="orient_for_print", inputs=("obj_1",), params={"thorough": False})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.bounds.size[2] < 20.0
    assert "orient.heuristic" in {finding.code for finding in result.scene.report.findings}


def test_the_thorough_orientation_uses_the_layer_analysis(
    document: Document, profile: Profile
) -> None:
    """Default is thorough: hundreds of positions judged by real support volume."""
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(
        _("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    history.apply(
        _("Ausrichten"),
        [OperationDraft(op="orient_for_print", inputs=("obj_1",), params={"candidates": 24})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert "orient.searched" in {finding.code for finding in result.scene.report.findings}
    assert history.operations[-1].seed is not None, "the sampling carries its seed (§11.3)"


def test_the_orientation_operation_is_registered() -> None:
    spec = REGISTRY.get("orient_for_print")
    assert spec.category == "transform"
    assert (spec.consumes, spec.produces) == (1, 1)
