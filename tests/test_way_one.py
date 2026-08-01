"""Weg 1 aus Bauplan §2.2, Ende zu Ende — der Abnahmetest für P2 (§40).

    Datei fallen lassen → Einheitenfrage, wenn nötig → das Modell steht,
    Prüfbericht sichtbar → eine Fläche anklicken → eine Operation wählen →
    Vorschau → annehmen → exportieren.

Der Chat-Teil gehört zu P4; hier kommt die Operation aus dem Kontextmenü, und
das ist die andere Hälfte desselben Satzes in §2.2. Alles übrige ist der echte
Weg: echte Dateien, der echte Stapel, die echte Auswertung, echte exportierte
Bytes.
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
    # --- Die Datei wird auf das Fenster fallen gelassen ------------------------
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

    # --- Die Einheit ist mehrdeutig, also wird gefragt, nicht geraten (§17.1) --
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

    # --- Das Modell steht, der Prüfbericht ist sichtbar (§17.3) ----------------
    assert result.scene.report.findings, "the input stage always has something to say"

    # --- Reparieren, denn ein heruntergeladenes Modell braucht das meist -------
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])

    # --- Aufs Bett setzen und bohren, wie es das Kontextmenü täte --------------
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

    # --- Die Vorschau ist eine zweite Auswertung, und sie stimmt mit der ersten überein
    again = evaluate(project.document, profile, sources=sources, cache=cache, ask=ask)
    assert again.object_hashes == result.object_hashes

    # --- Angenommen: speichern, und der Stapel übersteht die runde Reise -------
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
    """Nichts ist endgültig: jeder Schritt von Weg 1 kommt vom Stapel wieder
    herunter (§2.1).
    """
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
