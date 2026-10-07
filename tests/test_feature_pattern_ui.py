"""Das Merkmalsmuster im Fenster: Bohrung wählen, vervielfachen, ein Strg+Z (P6.7).

Der Kundenweg aus Konzept §13.9 an der Stelle, an der der Kunde ihn geht: Die
gewählte Bohrung steht im Dialog als Quelle, eine Pflichtliste ohne den Haken
„Ganzer Körper", und der Schritt, der daraus entsteht, ist einer — ein Undo
nimmt das ganze Muster zurück.
"""

from __future__ import annotations

from pathlib import Path

from app.core.registry import REGISTRY
from app.ui.main_window import MainWindow
from app.ui.op_dialog import FeatureSetField, OperationDialog
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window

MESHES = Path(__file__).parent / "data" / "meshes"


def _plate_with_holes(window: MainWindow) -> tuple[str, str, int]:
    """Die Lochplatte aus dem Korpus, eine ihrer vier Bohrungen und ihre Anzahl."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = sorted(
        (identifier, feature)
        for identifier, feature in entry.features.items()
        if feature.kind == "hole"
    )
    corner = min(holes, key=lambda item: tuple(item[1].params["centre"][:2]))
    return object_id, corner[0], len(holes)


def test_the_pattern_dialog_opened_at_a_hole_names_it_as_the_source(window: MainWindow) -> None:
    """Bohrung wählen, *Merkmal vervielfachen* — die Bohrung ist die Quelle.

    Die Liste ist Pflicht: kein Haken „Ganzer Körper", denn ein Muster ohne
    Quelle gibt es nicht, und die Operation lehnte es ab.
    """
    object_id, hole, _count = _plate_with_holes(window)
    spec = REGISTRY.get("pattern_feature")

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    window.run_operation(spec)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        assert dialog.values()["at_features"] == [hole]
        field = dialog.findChild(FeatureSetField)
        assert field is not None and not field.whole.isVisibleTo(dialog)
        assert dialog.values()["kind"] == "linear"
    finally:
        dialog.reject()


def test_a_pattern_is_one_step_and_one_undo(window: MainWindow) -> None:
    """Drei Plätze längs y an der Ecke der Lochplatte: zwei Bohrungen mehr, ein Strg+Z weg."""
    from app.core.scene.history import OperationDraft

    object_id, hole, count = _plate_with_holes(window)
    before = len(window.session.project.document.ops)

    window.session.apply(
        REGISTRY.get("pattern_feature").title,
        [
            OperationDraft(
                op="pattern_feature",
                inputs=(object_id,),
                params={
                    "at_features": [hole],
                    "kind": "linear",
                    "count": 2,
                    "spacing": 15.0,
                    "dy": 1.0,
                },
            )
        ],
    )
    window.session.wait_for_idle()
    after = window.session.evaluate_now()
    assert len(window.session.project.document.ops) == before + 1
    holes = [f for f in after.scene.objects[object_id].features.values() if f.kind == "hole"]
    assert len(holes) == count + 1

    window.session.undo()
    window.session.wait_for_idle()
    back = window.session.evaluate_now()
    holes = [f for f in back.scene.objects[object_id].features.values() if f.kind == "hole"]
    assert len(holes) == count
