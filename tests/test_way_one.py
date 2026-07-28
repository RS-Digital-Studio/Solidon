"""Way 1 from Bauplan §2.2, end to end — the acceptance test for P2 (§40).

    Drop a file → unit question if needed → the model stands, report visible →
    click a face → pick an operation → preview → accept → export.

The chat part belongs to P4; here the operation comes from the context menu,
which is the other half of the same sentence in §2.2. Everything else is the
real path: real files, the real stack, the real evaluation, real exported bytes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.export.writer import plan_export, write_plan
from app.core.geom.mesh import read_mesh
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.scene.project import ProjectSources, load, new_project, save
from app.core.types import Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def test_way_one_from_dropped_file_to_exported_part(tmp_path: Path, profile: Profile) -> None:
    # --- the file is dropped on the window -------------------------------------
    project = new_project("centauri-carbon-2", "petg")
    incoming = MESHES / "bracket_inch.stl"
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/bracket_inch.stl", sha256=""
    )
    project.sources["src_1"] = incoming.read_bytes()

    history = History(project.document)
    history.apply(
        _("Modell laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "auto"})],
    )

    # --- the unit is ambiguous, so it is asked, not guessed (§17.1) -------------
    asked: list[list[str]] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(choices)
        return "in"

    cache = ResultCache()
    sources = ProjectSources(project)
    result = evaluate(project.document, profile, sources=sources, cache=cache, ask=ask)

    assert asked, "an inch file is ambiguous and the chain asks"
    assert result.complete
    body = result.scene.objects["obj_1"]
    assert body.mesh.bounds.size == pytest.approx((101.6, 50.8, 6.35))

    # --- the model stands, the report is visible (§17.3) -----------------------
    assert result.scene.report.findings, "the input stage always has something to say"

    # --- repair, because a downloaded model usually needs it -------------------
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])

    # --- put it on the bed and drill a hole, as the context menu would ---------
    assert "drill_hole" in {spec.name for spec in REGISTRY.for_feature("face")}
    history.apply(_("Auf das Bett setzen"), [OperationDraft(op="place_on_bed", inputs=("obj_1",))])
    history.apply(
        _("Bohrung setzen"),
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ],
    )

    result = evaluate(project.document, profile, sources=sources, cache=cache, ask=ask)
    assert result.complete
    drilled = result.scene.objects["obj_1"]
    assert drilled.mesh.is_watertight
    assert drilled.mesh.volume < body.mesh.volume, "the bore removed material"
    assert drilled.mesh.bounds.minimum[2] == pytest.approx(0.0), "it sits on the bed"
    assert "bore.compensated" in {finding.code for finding in result.scene.report.findings}

    # --- the preview is a second evaluation, and it agrees with the first ------
    again = evaluate(project.document, profile, sources=sources, cache=cache, ask=ask)
    assert again.object_hashes == result.object_hashes

    # --- accepted: save, and the stack survives the round trip -----------------
    history.record_solvers(result.solvers)
    path = save(project, tmp_path / "halterung.p3d")
    reopened = load(path)
    assert [entry.op for entry in reopened.document.ops] == [
        "load",
        "repair",
        "place_on_bed",
        "drill_hole",
    ]
    assert reopened.document.ops[-1].solver is not None, "the solver stage was kept (§17.2)"
    assert reopened.document.ops[-1].seed is not None, "the seed was kept (§11.3)"

    # --- exported --------------------------------------------------------------
    plan = plan_export(
        list(result.scene.objects.values()),
        project_name="Halterung",
        profile=profile,
        sources=project.document.sources,
    )
    written = write_plan(plan, tmp_path / "export")

    assert [path.name for path in written] == ["Halterung_bracket_inch.stl"]
    exported = read_mesh(written[0].read_bytes(), ".stl")
    assert exported.triangle_count == drilled.mesh.triangle_count
    assert not [finding for finding in plan.findings if finding.severity == "error"]


def test_way_one_undone_completely(tmp_path: Path, profile: Profile) -> None:
    """Nothing is final: every step of way 1 comes back off the stack (§2.1)."""
    project = new_project("centauri-carbon-2", "petg")
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
        _("Bohrung setzen"),
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0})],
    )

    sources = ProjectSources(project)
    drilled = evaluate(project.document, profile, sources=sources)
    assert drilled.scene.objects["obj_1"].mesh.volume < 8000.0

    history.undo()
    after_undo = evaluate(project.document, profile, sources=sources)
    assert after_undo.scene.objects["obj_1"].mesh.volume == pytest.approx(8000.0)

    history.redo()
    after_redo = evaluate(project.document, profile, sources=sources)
    assert after_redo.object_hashes == drilled.object_hashes, "redo restores exactly"
