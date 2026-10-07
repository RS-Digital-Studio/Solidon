"""Der Puppenhaus-Weg im Fenster: Fläche anklicken, Aushöhlen, die Seite ist offen (RM-087)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.i18n import tr
from app.ui.main_window import MainWindow
from app.ui.op_dialog import FeatureSetField, OperationDialog
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window

MESHES = Path(__file__).parent / "data" / "meshes"


def test_a_clicked_side_face_is_the_opening_of_the_hollowing_dialog(window: MainWindow) -> None:
    """Fläche wählen, Strg+H — und das Feld *Öffnungen* nennt sie schon.

    Das ist der ganze Kundenweg: kein Haken, keine Kennung zum Abtippen. Eine
    gewählte Bohrung trägt sich dagegen nicht ein — an ihr lässt sich nichts
    öffnen, und das Feld bleibt leer.

    **Seit P6.3 (23.09.2026) unter „Öffnungen" statt „Öffnen an Fläche".**
    Der Klick meint genau diese Fläche; ``open_at`` öffnet in ihre
    Achsrichtung und bleibt für gespeicherte Schritte, was es war. Der Haken
    der leeren Liste heißt dort „Keine", nicht „Ganzer Körper".
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
        assert dialog.values()["openings"] == [side]
        assert dialog.values()["open_at"] == "", "der ältere Achsweg bleibt leer"
        assert dialog.values()["open_top"] is False, "die Fläche gilt, nicht der Haken"
        field = dialog.findChild(FeatureSetField)
        assert field is not None and field.whole.text() == tr("Keine")
    finally:
        dialog.reject()

    window.object_tree.select_object(object_id)
    window.run_operation(spec)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        assert dialog.values()["openings"] == [], "ohne gewählte Fläche bleibt das Feld leer"
    finally:
        dialog.reject()


def test_a_chosen_face_offers_hollowing_in_the_card_and_becomes_the_opening(
    window: MainWindow,
) -> None:
    """Rechts unter *Auswahl* steht *Aushöhlen* auch an einer Fläche.

    Fragebogen zu 0.5.3: „Aushöhlen erscheint nicht so, wie im Handbuch
    beschrieben.“ Ein angelegter Quader ist gewählt, der Klick darauf nahm die
    Oberseite, und an einer Fläche stand *Aushöhlen* weder vorn noch in der
    Liste. Jetzt steht es dort, und der Knopf trägt die Fläche als Öffnung ein
    — oben offen, wie die Anleitung *Ein Gehäuse mit Deckel* es will.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    top = next(
        identifier
        for identifier, feature in entry.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 0.9
    )

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, top)
    panel = window.selection_operations
    assert panel.chosen_level() == "face"
    assert panel._buttons["hollow_object"].isHidden(), "oben steht es an der Fläche nicht"
    button = panel._list_twins["hollow_object"]
    assert not button.isHidden() and button.isEnabled(), "aber in der Liste darunter"

    button.click()
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        assert dialog.values()["openings"] == [top], "die gewählte Fläche ist die Öffnung"
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


def test_a_guide_finds_hollowing_in_the_list_at_a_chosen_face(qt_app: QApplication) -> None:
    """Eine Anleitung, die auf *Aushöhlen* zeigt, findet an der Fläche den Listenknopf.

    ``guide_targets`` las nur den oberen Knopf; an einer Fläche ist der
    verborgen, und Rahmen wie Nummer fanden kein Ziel, obwohl die Handlung in
    der Liste stand (Zwilling zu ``_list_twins``).
    """
    from app.ui.guide_targets import area_for, widget_for
    from tests.ui_helpers import shown_window

    windows = shown_window(qt_app)
    window = next(windows)
    try:
        window.open_path(MESHES / "cube_clean.stl")
        window.session.wait_for_idle()
        result = window.session.evaluate_now()
        object_id, entry = next(iter(result.scene.objects.items()))
        top = next(
            identifier
            for identifier, feature in entry.features.items()
            if feature.kind == "face" and feature.params["normal"][2] > 0.9
        )
        window.object_tree.select_object(object_id)
        window.object_tree.select_feature(object_id, top)
        window.right.setCurrentWidget(window.feature_dock)
        qt_app.processEvents()
        twin = window.selection_operations._list_twins["hollow_object"]
        area = area_for(window, "operation:hollow_object")
        assert twin.isVisible(), "der Listenknopf wird hervorgeholt"
        assert widget_for(window, "operation:hollow_object") is twin
        assert area.contains(twin.mapToGlobal(twin.rect().center())), area
    finally:
        next(windows, None)
