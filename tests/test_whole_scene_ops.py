"""Operationen, die auf der ganzen Szene arbeiten (Bauplan §25, §10).

Anordnen und die Kollisionsprüfung nehmen kein bestimmtes Objekt und geben alle
zurück. Wer die Transaktion baut, muss das sagen — ein Menüeintrag, der auf
einer leeren Eingabeliste läuft, ändert nichts und sieht kaputt aus, und genau
das tat er, bevor es diesen Test gab.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Profile, Source

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.mark.parametrize("name", ["arrange_bed", "check_collisions"])
def test_the_registry_says_which_operations_take_everything(name: str) -> None:
    assert REGISTRY.get(name).takes_whole_scene


@pytest.mark.parametrize("name", ["translate_object", "repair", "split_pinned"])
def test_an_ordinary_operation_does_not(name: str) -> None:
    assert not REGISTRY.get(name).takes_whole_scene


def two_objects(project: Project) -> None:
    """Zwei Würfel übereinander — das Anordnen muss sie auseinanderbringen."""
    payload = (MESHES / "cube_clean.stl").read_bytes()
    for index in (1, 2):
        source_id = f"src_{index}"
        project.sources[source_id] = payload
        project.document.sources[source_id] = Source(
            id=source_id, kind="import", path=f"sources/cube_{index}.stl", sha256=""
        )
    History(project.document).apply(
        "Laden",
        [
            OperationDraft(op="load", params={"source": "src_1", "unit": "mm"}),
            OperationDraft(op="load", params={"source": "src_2", "unit": "mm"}),
        ],
    )


def test_arranging_without_inputs_changes_nothing(profile: Profile) -> None:
    """Der Fehler, um den es in dieser Datei geht — als Test gehalten, damit er
    nicht zurückkommen kann.
    """
    project = new_project("centauri-carbon-2", "petg")
    two_objects(project)
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    places = {name: entry.mesh.bounds.centre for name, entry in before.scene.objects.items()}

    History(project.document).apply(
        "Anordnen", [OperationDraft(op="arrange_bed", inputs=(), params={"spacing": 5.0})]
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))

    assert {name: entry.mesh.bounds.centre for name, entry in after.scene.objects.items()} == places


def test_arranging_with_the_scene_moves_the_objects_apart(profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    two_objects(project)
    History(project.document).apply(
        "Anordnen",
        [OperationDraft(op="arrange_bed", inputs=("obj_1", "obj_2"), params={"spacing": 5.0})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    first, second = (result.scene.objects[name].mesh.bounds for name in ("obj_1", "obj_2"))
    assert first.maximum[0] <= second.minimum[0] + 1e-6, "side by side, not on top of each other"
    assert first.minimum[2] == pytest.approx(0.0) and second.minimum[2] == pytest.approx(0.0)


def test_the_window_hands_the_whole_scene_in() -> None:
    """§10: eine Deklaration, und jede Oberfläche liest dasselbe daraus ab."""
    from app.ui.main_window import inputs_for

    objects = ["obj_1", "obj_2", "obj_3"]

    assert inputs_for(REGISTRY.get("arrange_bed"), objects, ()) == ("obj_1", "obj_2", "obj_3")
    assert inputs_for(REGISTRY.get("repair"), objects, ("obj_2",)) == ("obj_2",)
    assert inputs_for(REGISTRY.get("repair"), objects, ()) == ()
    creating = REGISTRY.get("create_box")
    assert inputs_for(creating, objects, ("obj_2",)) == (), "creates, takes nothing"


def test_an_operation_on_two_bodies_gets_two() -> None:
    """§25: Vereinigen, Abziehen und Schnittmenge nehmen zwei Körper.

    Solange die Auswahl immer genau eines lieferte, war keine der drei über
    das Menü ausführbar — der Stapel lehnte sie mit „erwartet eine andere
    Anzahl an Objekten" ab. Die Reihenfolge zählt mit: „A minus B" ist nicht
    „B minus A".
    """
    from app.ui.main_window import inputs_for

    objects = ["obj_1", "obj_2", "obj_3"]
    spec = REGISTRY.get("subtract_objects")
    assert spec.consumes == 2

    assert inputs_for(spec, objects, ("obj_2", "obj_1")) == ("obj_2", "obj_1")
    assert inputs_for(spec, objects, ("obj_1", "obj_2", "obj_3")) == ("obj_1", "obj_2")
    assert inputs_for(spec, objects, ("obj_1",)) == ("obj_1",), "zu wenige — das Fenster hält an"


def test_orienting_turns_the_body(profile: Profile) -> None:
    """Die andere Hälfte des Berichts: das Orientieren ändert sehr wohl etwas."""
    plate = trimesh.creation.box(extents=(60.0, 40.0, 4.0))
    plate.apply_transform(trimesh.transformations.rotation_matrix(0.6, [1.0, 0.0, 0.0]))
    entry = MeshData.of(plate)

    from app.core.geom.orient import orient_for_print

    result = orient_for_print(entry)

    assert result.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6), "sits on the bed"
    assert result.mesh.bounds.size[2] < entry.bounds.size[2], "and lies flatter than before"
