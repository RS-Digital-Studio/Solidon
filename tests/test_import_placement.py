"""Ein Import bleibt eine Gruppe; gemeinsames Aufsetzen ist ein eigener Schritt."""

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.export import threemf
from app.core.geom.mesh import MeshCodec, MeshData
from app.core.ingest import plan
from app.core.registry import REGISTRY, VARIABLE
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import DiskCache, ResultCache
from app.core.scene.project import ProjectSources, checksum, load, new_project, save
from app.core.types import Source
from app.i18n import _


def _imported_pair(lower_z=-5.0):
    """Zwei Würfel mit verschiedenen Höhen neben einem schon vorhandenen Körper."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(_("Vorhanden"), [OperationDraft(op="create_box")])
    parts = []
    for name, centre in (("Unten", (40.0, 0.0, lower_z)), ("Oben", (70.0, 0.0, 15.0))):
        mesh = trimesh.creation.box((10.0, 10.0, 10.0))
        mesh.apply_translation(centre)
        parts.append(threemf.AssemblyPart(mesh=MeshData.of(mesh), name=name))
    payload = threemf.write_assembly(parts)
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/paar.3mf", sha256=checksum(payload)
    )
    prepared = plan.import_plan("src_1", "paar.3mf", payload, first_model=False)
    history.apply(prepared.title, [prepared.draft])
    return project, history, project.document.ops[-1].outputs


def test_import_group_placement_is_a_separate_reversible_cached_step(profile, tmp_path):
    """Originalkoordinaten, gemeinsame Verschiebung und beide Undo-Grenzen sind sichtbar."""
    project, history, targets = _imported_pair()
    cache_dir = tmp_path / "cache"

    def run(current=project):
        return evaluate(
            current.document,
            profile,
            sources=ProjectSources(current),
            cache=ResultCache(disk=DiskCache(codec=MeshCodec(), directory=cache_dir)),
        )

    before = run()
    assert before.complete
    assert [before.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == pytest.approx(
        [-10.0, 10.0]
    )
    assert plan.imported_group(project.document, targets[1], before.scene.objects) == targets
    assert (
        plan.imported_group_for_bed(project.document, targets[1], before.scene.objects) == targets
    )
    original = before.scene.objects["obj_1"].mesh.bounds
    history.apply(
        _("Gemeinsam auf das Bett setzen"),
        [OperationDraft(op="place_group_on_bed", inputs=targets)],
    )
    for result in (run(), run()):
        assert result.complete
        assert [
            result.scene.objects[key].mesh.bounds.minimum[2] for key in targets
        ] == pytest.approx([0.0, 20.0])
        assert [
            result.scene.objects[key].mesh.bounds.centre[0] for key in targets
        ] == pytest.approx([40.0, 70.0])
        untouched = result.scene.objects["obj_1"].mesh.bounds
        assert untouched.minimum == pytest.approx(original.minimum)
        assert untouched.maximum == pytest.approx(original.maximum)
    assert plan.imported_group(project.document, targets[0], result.scene.objects) == ()
    path = save(project, tmp_path / "gruppe.p3d")
    restored = run(load(path))
    assert restored.complete
    assert [restored.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == pytest.approx(
        [0.0, 20.0]
    )
    history.undo()
    undone = run()
    assert [undone.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == pytest.approx(
        [-10.0, 10.0]
    )
    assert plan.imported_group(project.document, targets[0], undone.scene.objects) == targets
    history.undo()
    assert set(run().scene.objects) == {"obj_1"}
    history.redo()
    history.redo()
    assert [run().scene.objects[key].mesh.bounds.minimum[2] for key in targets] == pytest.approx(
        [0.0, 20.0]
    )


@pytest.mark.parametrize("kind", ["mesh", "brep", "mixed"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_group_placement_recomputes_one_offset_for_all_current_inputs(profile, kind, quality):
    """Eine spätere Höhenänderung wird ausgewertet, nicht ein früherer UI-Versatz wiederholt."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    for index in range(2):
        exact = kind == "brep" or (kind == "mixed" and index == 1)
        history.apply(
            _("Körper"),
            [
                OperationDraft(
                    op="create_brep_box" if exact else "create_box", params={"height": 20.0}
                )
            ],
        )
    history.apply(
        _("Größe"),
        [OperationDraft(op="scale_object", inputs=("obj_1",), params={"factor": 1.0})],
    )
    history.apply(
        _("Versetzen"),
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dz": 30.0})],
    )
    before = evaluate(project.document, profile, quality=quality)
    assert before.complete
    centres = [before.scene.objects[key].mesh.bounds.centre[2] for key in ("obj_1", "obj_2")]
    history.apply(
        _("Gemeinsam auf das Bett setzen"),
        [OperationDraft(op="place_group_on_bed", inputs=("obj_1", "obj_2"))],
    )
    cache = ResultCache()
    scaling = project.document.ops[2]
    for factor in (1.0, 2.0):
        # Über den Verlauf, nicht am Dokument vorbei: So ändert der Kunde den Wert.
        history.change_params(scaling.id, {"factor": factor})
        result = evaluate(project.document, profile, quality=quality, cache=cache)
        assert result.complete
        objects = [result.scene.objects[key] for key in ("obj_1", "obj_2")]
        assert min(obj.mesh.bounds.minimum[2] for obj in objects) == pytest.approx(0.0)
        assert objects[1].mesh.bounds.centre[2] - objects[0].mesh.bounds.centre[2] == pytest.approx(
            centres[1] - centres[0]
        )
        assert objects[1].mesh.bounds.minimum[2] == pytest.approx(30.0 + 10.0 * (factor - 1.0))
        assert [obj.kind for obj in objects] == [
            before.scene.objects[obj.id].kind for obj in objects
        ]
        assert all(
            len([f for f in obj.features.values() if f.kind == "face"]) == 6 for obj in objects
        )


def test_group_offer_requires_the_unchanged_complete_import(profile):
    """Andere Auswahl zählt nicht; selbst die Nutzung nur eines Mitglieds beendet das Angebot."""
    project, history, targets = _imported_pair()
    live = evaluate(project.document, profile, sources=ProjectSources(project)).scene.objects
    assert plan.imported_group(project.document, "obj_1", live) == ()
    assert plan.imported_group(project.document, targets[0], (targets[0], "obj_1")) == ()
    history.apply(
        _("Umbenennen"),
        [OperationDraft(op="rename_object", inputs=(targets[1],), params={"name": "Anders"})],
    )
    assert plan.imported_group(project.document, targets[0], live) == ()


def test_single_and_group_placement_keep_distinct_input_contracts():
    """Der neue Gruppenweg ändert die bisherige Einzeloperation nicht."""
    load_operations()
    single, group = REGISTRY.get("place_on_bed"), REGISTRY.get("place_group_on_bed")
    assert (single.consumes, single.produces) == (1, 1)
    assert (group.consumes, group.minimum_inputs, group.produces) == (VARIABLE, 2, VARIABLE)
    assert not group.takes_whole_scene
    assert not group.params.spec()


def test_a_later_cross_body_reference_ends_the_import_group_offer(profile):
    """Auch eine gelesene Gegenfläche ist eine Verwendung, nicht nur ein direkter Eingang."""
    project, history, targets = _imported_pair()
    live = evaluate(project.document, profile, sources=ProjectSources(project)).scene.objects
    history.apply(
        _("Ausrichten"),
        [
            OperationDraft(
                op="align_to_feature",
                inputs=("obj_1",),
                params={"target": f"{targets[0]}:face_1"},
            )
        ],
    )
    assert plan.imported_group(project.document, targets[0], live) == ()


def test_a_grounded_import_group_keeps_the_effective_single_body_offer(profile):
    """Unterseiten 0/10: Gemeinsam aufsetzen wäre wirkungslos, einzeln verschwindet der Befund."""
    project, history, targets = _imported_pair(lower_z=5.0)
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    floating = next(
        finding
        for finding in result.scene.report.findings
        if finding.code == "arrange.above_bed" and finding.object_id == targets[1]
    )
    assert [result.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == [0.0, 10.0]
    assert (
        plan.imported_group(project.document, floating.object_id, result.scene.objects) == targets
    )
    assert (
        plan.imported_group_for_bed(project.document, floating.object_id, result.scene.objects)
        == ()
    )
    history.apply(
        "Einzeln aufsetzen", [OperationDraft(op="place_on_bed", inputs=(floating.object_id,))]
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))
    assert after.complete
    assert [after.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == [0.0, 0.0]
    assert not any(
        finding.code == "arrange.above_bed" and finding.object_id in targets
        for finding in after.scene.report.findings
    )
    history.undo()
    restored = evaluate(project.document, profile, sources=ProjectSources(project))
    assert [restored.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == [0.0, 10.0]


def test_group_placement_checks_cancellation_before_measuring_the_next_body(profile, monkeypatch):
    """Ein Abbruch beim ersten Hüllkasten lässt alle weiteren Körper unangetastet."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal
    from app.core.types import OpContext, Scene, SceneObject

    load_operations()
    token = CancelSignal()
    measured = []
    original = MeshData.bounds.fget

    def bounds(mesh):
        measured.append(mesh)
        token.cancel()
        return original(mesh)

    objects = [
        SceneObject(id=f"obj_{index}", name="Körper", mesh=MeshData(trimesh.creation.box()))
        for index in (1, 2, 3)
    ]
    monkeypatch.setattr(MeshData, "bounds", property(bounds))
    spec = REGISTRY.get("place_group_on_bed")
    context = OpContext(
        scene=Scene(objects={obj.id: obj for obj in objects}),
        inputs=objects,
        params=spec.params(),
        profile=profile,
        quality="fine",
        seed=None,
        progress=lambda _fraction, _text: None,
        ask=lambda _question, choices: choices[0],
        cancelled=token,
    )
    with pytest.raises(OperationCancelled):
        spec.fn(context)
    assert measured == [objects[0].mesh]
