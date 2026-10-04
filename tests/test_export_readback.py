"""Die Gegenprobe nach dem Schreiben liest die Datei wirklich zurück (RM-090, §29).

Ein gelungener Schreibvorgang ist noch keine Gegenprobe (Produktkompass 4.5).
Hier wird jede Datei so geschrieben, wie Export und Slicer-Übergabe sie
schreiben, und mit denselben Lesern wie beim Import zurückgeholt. Sollwerte
sind die Kennzahlen der Netze, die in den Schreiber gingen; jede Abweichung
wird an einer absichtlich beschädigten Datei gegengeprüft.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.export import readback, writer
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import new_project
from app.core.types import SceneObject


def _bodies() -> tuple[list[SceneObject], object]:
    """Ein Quader 20 × 30 × 10 und ein Zylinder, wie Weg 2 sie anlegt."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 30.0, "height": 10.0})],
    )
    history.apply("Zylinder", [OperationDraft(op="create_cylinder")])
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = evaluate(project.document, profile, detect_features=False)
    objects = list(result.scene.objects.values())
    assert len(objects) == 2
    return objects, profile


def _written(
    objects: list[SceneObject], profile: object, tmp_path: Path, export_format: str
) -> list[tuple[Path, list[readback.BodyFigures]]]:
    plan = writer.plan_export(
        objects,
        project_name="probe",
        profile=profile,  # type: ignore[arg-type]
        export_format=export_format,  # type: ignore[arg-type]
        checked=[],
    )
    paths = writer.write_plan(plan, tmp_path, export_format)  # type: ignore[arg-type]
    by_id = {entry.object_id: entry for entry in plan.entries}
    return [
        (path, [readback.BodyFigures.of_mesh(entry.name, entry.mesh)])
        for path, entry in zip(paths, by_id.values(), strict=True)
    ]


@pytest.mark.parametrize("export_format", ["stl", "obj", "ply", "glb", "3mf"])
def test_every_mesh_format_reads_back_what_was_written(tmp_path, export_format):
    objects, profile = _bodies()
    checked = readback.read_back(_written(objects, profile, tmp_path, export_format))
    assert checked.state == "matched", [str(note) for note in checked.notes]
    assert checked.found == checked.expected == 2
    assert len(checked.files) == 2
    assert "erneut eingelesen" in str(checked.summary())


def test_a_file_that_lost_triangles_is_named_as_a_deviation(tmp_path):
    """Gegenprobe: Ein abgeschnittenes STL fällt auf, mit dem Namen des Körpers."""
    objects, profile = _bodies()
    expected = _written(objects, profile, tmp_path, "stl")
    damaged, figures = expected[0]
    payload = damaged.read_bytes()
    count = int.from_bytes(payload[80:84], "little")
    # Das letzte Dreieck weglassen und den Kopf ehrlich nachführen: Die Datei
    # bleibt lesbar, nur fehlt ihr ein Stück Oberfläche.
    damaged.write_bytes(payload[:80] + (count - 1).to_bytes(4, "little") + payload[84:-50])
    checked = readback.read_back(expected)
    assert checked.state == "deviated"
    assert any(figures[0].name in str(note) for note in checked.notes)
    assert "weicht vom Auftrag ab" in str(checked.summary())


def test_an_unreadable_file_is_a_deviation_and_not_a_skipped_check(tmp_path):
    objects, profile = _bodies()
    expected = _written(objects, profile, tmp_path, "3mf")
    expected[0][0].write_bytes(b"kein zip")
    checked = readback.read_back(expected)
    assert checked.state == "deviated"
    assert any("nicht wieder einlesen" in str(note) for note in checked.notes)


def test_a_file_with_more_bodies_than_the_job_says_so(tmp_path):
    objects, profile = _bodies()
    path, _findings = writer.write_assembly(
        objects,
        tmp_path,
        project_name="beide",
        profile=profile,  # type: ignore[arg-type]
        for_slicer=False,
        checked=[],
    )
    only_one = [
        readback.BodyFigures.of_mesh(
            objects[0].name, writer.mesh_for_export(objects[0].mesh, profile)
        )  # type: ignore[arg-type]
    ]
    checked = readback.read_back([(path, only_one)])
    assert checked.state == "deviated"
    assert any("1 Körper mehr" in str(note) for note in checked.notes)


@pytest.mark.parametrize(
    "flavour, window",
    [("orca", False), ("prusa", False), ("orca", True), ("prusa", True), ("cura", True)],
)
def test_every_assembly_reads_back_where_the_slicer_puts_it(tmp_path, flavour, window):
    """Bettkoordinaten und Plattenraster ändern die Lage, nicht die Kennzahlen."""
    objects, profile = _bodies()
    path, _findings = writer.write_assembly(
        objects,
        tmp_path,
        project_name="baugruppe",
        profile=profile,  # type: ignore[arg-type]
        flavour=flavour,  # type: ignore[arg-type]
        for_slicer=window,
        for_window=window,
        checked=[],
    )
    expected = [
        readback.BodyFigures.of_mesh(body.name, writer.mesh_for_export(body.mesh, profile))  # type: ignore[arg-type]
        for body in objects
    ]
    checked = readback.read_back([(path, expected)])
    assert checked.state == "matched", [str(note) for note in checked.notes]
    assert checked.found == 2


def test_nothing_written_is_not_performed_with_a_reason():
    checked = readback.read_back([])
    assert checked.state == "not_performed"
    assert "keine Datei" in str(checked.summary())


def test_a_step_file_reads_back_as_the_same_solid(tmp_path):
    from tests.helpers import exact_kernel

    exact_kernel()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 20.0, "depth": 30.0, "height": 10.0}
            )
        ],
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = evaluate(project.document, profile, detect_features=False)
    exact = [body for body in result.scene.objects.values() if body.kind == "brep"]
    assert exact, "der exakte Quader entsteht exakt"
    plan = writer.plan_export(
        exact,
        project_name="exakt",
        profile=profile,  # type: ignore[arg-type]
        export_format="step",
        checked=[],
    )
    paths = writer.write_plan(plan, tmp_path, "step")
    expected = []
    for path, entry in zip(paths, plan.entries, strict=True):
        body = entry.body
        assert body is not None
        size = sorted(float(value) for value in body.bounds.size)
        expected.append(
            (
                path,
                [
                    readback.BodyFigures(
                        entry.name,
                        float(body.volume),
                        float(body.area),
                        (size[0], size[1], size[2]),
                    )
                ],
            )
        )
    checked = readback.read_back(expected)
    assert checked.state == "matched", [str(note) for note in checked.notes]
