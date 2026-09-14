"""Der Puppenhaus-Weg im Fenster: Fläche anklicken, Aushöhlen, die Seite ist offen (RM-087)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    # Aufgeräumt wird zentral: ``tests/conftest.py`` wartet nach jedem Test
    # auf die Arbeiter jedes offenen Fensters.
    return MainWindow(Session(), UiSettings())


def test_a_clicked_side_face_is_the_opening_of_the_hollowing_dialog(window: MainWindow) -> None:
    """Fläche wählen, Strg+H — und das Feld *Öffnen an Fläche* nennt sie schon.

    Das ist der ganze Kundenweg: kein Haken, keine Kennung zum Abtippen. Eine
    gewählte Bohrung trägt sich dagegen nicht ein — an ihr lässt sich nichts
    öffnen, und das Feld bleibt leer.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    side = next(
        identifier
        for identifier, feature in entry.features.items()
        if feature.kind == "face" and feature.params["normal"][1] < -0.9
    )
    spec = REGISTRY.get("hollow_object")

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, side)
    window.run_operation(spec)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        assert dialog.values()["open_at"] == f"{object_id}:{side}"
        assert dialog.values()["open_top"] is False, "die Fläche gilt, nicht der Haken"
    finally:
        dialog.reject()

    window.object_tree.select_object(object_id)
    window.run_operation(spec)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        assert dialog.values()["open_at"] == "", "ohne gewählte Fläche bleibt das Feld leer"
    finally:
        dialog.reject()


def test_hollowing_at_the_clicked_side_ends_in_the_history_with_the_face(
    window: MainWindow,
) -> None:
    """Der Schritt im Verlauf trägt die Fläche — und ist damit reproduzierbar (§11).

    Gemessen am Ergebnis: Die gewählte Seite ist offen, die Decke bleibt zu.
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene.history import OperationDraft
    from app.core.slice.analysis import cross_section

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    side = next(
        identifier
        for identifier, feature in entry.features.items()
        if feature.kind == "face" and feature.params["normal"][1] < -0.9
    )

    window.session.apply(
        REGISTRY.get("hollow_object").title,
        [
            OperationDraft(
                op="hollow_object",
                inputs=(object_id,),
                params={"wall": 2.0, "vents": 0, "open_at": f"{object_id}:{side}"},
            )
        ],
    )
    window.session.wait_for_idle()
    after = window.session.evaluate_now()

    step = window.session.project.document.ops[-1]
    assert step.op == "hollow_object" and step.params["open_at"] == f"{object_id}:{side}"
    opened = as_mesh_data(after.scene.objects[object_id].mesh)
    top = float(opened.bounds.maximum[2])
    ceiling = cross_section(opened, top - 0.5)
    assert ceiling is not None and not list(getattr(ceiling, "interiors", [])), (
        "die Decke bleibt zu"
    )
    assert opened.volume < entry.mesh.volume, "es wurde ausgehöhlt"
