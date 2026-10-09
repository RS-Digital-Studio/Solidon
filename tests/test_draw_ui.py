"""Das Werkzeug *Zeichnen* am Fenster: drei Klicks, ein Schritt (RM-559, RM-561).

Fenstertests (``qt_app``) — gefahren beim Release. Offscreen gibt es keinen
Renderer, also auch keinen Sichtstrahl; die Klicks gehen deshalb über die
Methoden, die die Ansicht nach dem Treffer ruft (``take``, ``aim``, ``place``,
``lift_to``, ``settle``) — dieselbe Teilung wie ``place``/``grab_point`` im
Skizzeneditor. Was ein Klick **bedeutet**, prüft ohne Fenster
``tests/test_drawn_body.py``; wohin ein echter Mausklick fällt, zeigt nur die
echte Plattform.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_from_text, sketch_to_text
from app.ui.draw_tool import DRAW_KEY, DrawSurface, Lift, bed_surface, face_surface
from app.ui.main_window import MainWindow
from app.ui.op_dialog import ValueField
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.helpers import exact_kernel

exact_kernel()


@pytest.fixture
def window(qt_app: QApplication) -> Any:
    shown = MainWindow(Session(), UiSettings())
    shown.session.start_new()
    assert shown.session.wait_for_idle(60_000)
    yield shown
    if shown.drawing():
        shown.draw_flow().close()
    shown.wait_for_workers()
    shown.deleteLater()


def _three_clicks_on_the_bed(window: MainWindow, height: float = 10.0) -> None:
    flow = window.draw_flow()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    flow.aim((40.0, 30.0))
    flow.place()
    flow.lift = Lift(height)
    assert flow.settle()
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()


def _the_toolbar_action(window: MainWindow) -> Any:
    from PySide6.QtGui import QKeySequence

    return next(
        action for action in window.toolbar.actions() if action.shortcut() == QKeySequence(DRAW_KEY)
    )


def test_the_shortcut_and_three_clicks_make_one_extrude_step(window: MainWindow) -> None:
    """Abnahme 1: leere Szene, Kürzel, drei Klicks — ein Schritt, ein Körper, gewählt."""
    _the_toolbar_action(window).trigger()
    assert window.drawing(), "das Kürzel öffnet das Aufziehen"
    assert window._sketch_panel is None, "ohne Moduswechsel"
    assert window.draw_bar.isVisibleTo(window) and not window.tools.isVisibleTo(window)
    _three_clicks_on_the_bed(window)
    operations = window.session.history.operations
    assert [entry.op for entry in operations] == ["sketch_extrude"]
    scene = window.session.last_result.scene
    assert len(scene.objects) == 1
    body = next(iter(scene.objects.values()))
    assert body.mesh.volume == pytest.approx(12000.0, rel=1e-9)
    assert not window.drawing(), "ein Einmalwerkzeug: nach Klick 3 ist es zu"
    assert window.object_tree.selected() == body.id, "der Körper ist gewählt"


def test_undo_takes_the_whole_step_and_redo_brings_it_back(window: MainWindow) -> None:
    """Abnahme 6: Strg+Z nach Klick 3 — Verlauf und Objekte wie davor; Strg+Y stellt her."""
    window.start_drawing()
    _three_clicks_on_the_bed(window)
    window.action_undo()
    assert window.session.wait_for_idle(60_000)
    assert window.session.history.operations == ()
    assert not window.session.last_result.scene.objects
    window.action_redo()
    assert window.session.wait_for_idle(60_000)
    assert [entry.op for entry in window.session.history.operations] == ["sketch_extrude"]


def test_undo_in_the_draft_goes_back_one_click(window: MainWindow) -> None:
    """Abnahme 6, zweiter Teil: im Entwurf nimmt Strg+Z den letzten Klick, nichts im Verlauf."""
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    flow.aim((20.0, 10.0))
    flow.place()
    assert flow.draft is not None and flow.draft.phase == 2
    assert window.undo_action.isEnabled(), "Rückgängig meint jetzt den Klick"
    window.action_undo()
    assert flow.draft.phase == 1
    window.action_undo()
    assert flow.draft.phase == 0
    assert window.drawing(), "das Werkzeug bleibt offen"
    assert window.session.history.operations == ()


def test_escape_before_the_third_click_changes_nothing(window: MainWindow) -> None:
    """Abnahme 7: Escape vor Klick 3 — Dokument unverändert, Werkzeug zu."""
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    flow.aim((20.0, 10.0))
    flow.place()
    window._escape()
    assert not window.drawing()
    assert window.session.history.operations == ()
    assert window.tools.isVisibleTo(window) and not window.draw_bar.isVisibleTo(window)


def test_a_double_click_on_the_step_opens_its_three_measures(window: MainWindow) -> None:
    """Abnahme 8: Breite, Tiefe und Höhe vorn; Breite 50 ändert denselben Schritt."""
    from PySide6.QtTest import QTest

    window.start_drawing()
    _three_clicks_on_the_bed(window)
    step = window.session.history.operations[-1].id
    window.edit_operation(step)
    dialog = window._op_dialog
    assert dialog is not None, "ein Rechteck öffnet seine Maße, nicht den Editor"
    assert window._sketch_panel is None
    front = [
        name
        for name, editor in dialog._editors.items()
        if dialog._rows[name] is dialog._front and not editor.isHidden()
    ]
    assert sorted(front) == ["height", "length", "width"], front
    titles = {
        name: dialog._front.labelForField(dialog._editors[name]).text()
        for name in ("length", "width", "height")
    }
    assert titles == {"length": "Breite", "width": "Tiefe", "height": "Höhe"}
    width = dialog._editors["length"]
    assert isinstance(width, ValueField)
    width.set_value(50.0)
    QTest.qWait(350)
    assert window.session.wait_for_idle(60_000)
    dialog.accept()
    assert window.session.wait_for_idle(60_000)
    assert len(window.session.history.operations) == 1, "derselbe Schritt, kein zweiter"
    body = next(iter(window.session.last_result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(15000.0, rel=1e-6)


def test_the_keyboard_alone_draws_the_same_block(window: MainWindow) -> None:
    """Abnahme 9: Kürzel, Enter, 40 Tab 30 Enter, 10 Enter — der Quader auf der Plattenmitte."""
    _the_toolbar_action(window).trigger()
    flow = window.draw_flow()
    flow.press_enter()
    assert flow.draft is not None and flow.draft.first == (0.0, 0.0)
    assert flow.type_first("4")
    assert flow.type_values([40.0, 30.0])
    assert flow.type_first("1")
    assert flow.type_values([10.0])
    assert window.session.wait_for_idle(60_000)
    body = next(iter(window.session.last_result.scene.objects.values()))
    box = body.mesh.bounds
    assert body.mesh.volume == pytest.approx(12000.0, rel=1e-9)
    assert box.minimum[0] == pytest.approx(0.0) and box.minimum[1] == pytest.approx(0.0)
    assert box.maximum[2] == pytest.approx(10.0)


def test_outward_on_a_face_joins_and_inward_cuts(window: MainWindow) -> None:
    """Abnahme 3 und 4 am Fenster: die Richtung des dritten Klicks entscheidet."""
    window.session.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}
            )
        ],
    )
    assert window.session.wait_for_idle(60_000)
    entry = next(iter(window.session.last_result.scene.objects.values()))
    top = next(
        key
        for key, feature in entry.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 0.9
    )
    surface = face_surface(entry, top)
    assert surface is not None
    for lift, op, change in (
        (Lift(5.0), "sketch_join", 500.0),
        (Lift(-5.0), "sketch_pocket", -500.0),
    ):
        window.start_drawing()
        flow = window.draw_flow()
        flow.take(("face", surface, (-5.0, -5.0), (0.0, 0.0, 0.0)))
        flow.aim((5.0, 5.0))
        flow.place()
        flow.lift = lift
        assert flow.settle()
        assert window.session.wait_for_idle(60_000)
        assert window.session.history.operations[-1].op == op
        assert len(window.session.last_result.scene.objects) == 1
        body = next(iter(window.session.last_result.scene.objects.values()))
        assert body.mesh.volume == pytest.approx(24000.0 + change, rel=1e-9)
        window.action_undo()
        assert window.session.wait_for_idle(60_000)


def test_a_curved_face_takes_nothing_and_says_why(window: MainWindow) -> None:
    """F-a: kein Schritt, der Satz steht."""
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("curved", None, None, None))
    assert flow.draft is not None and flow.draft.phase == 0
    assert "gewölbten" in window._announcement
    assert window.session.history.operations == ()


def test_an_unrecognised_place_offers_the_recognition(window: MainWindow) -> None:
    """F-b: kein Schritt, der Satz steht, *Hier Merkmale erkennen* daneben."""
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("unknown", ("obj_1", (0.0, 0.0, 0.0), 0, None), None, None))
    assert "nicht als Fläche erkannt" in window._announcement
    assert window.draw_bar.recognise.isVisibleTo(window.draw_bar)
    assert window.session.history.operations == ()


def test_a_new_body_over_another_offers_union_and_subtraction(window: MainWindow) -> None:
    """F-g: Die Überdeckung meldet sich mit zwei Wegen; nichts geschieht von selbst."""
    window.session.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 10.0})],
    )
    assert window.session.wait_for_idle(60_000)
    window.start_drawing()
    _three_clicks_on_the_bed(window)
    assert window.draw_flow().wait_for_overlap()
    assert "überdeckt" in window._announcement
    offered = [button.text() for button in window._draw_offers if button.isVisibleTo(window)]
    assert offered == ["Vereinigen", "Davon abziehen"]
    assert len(window.session.last_result.scene.objects) == 2


def test_a_block_inside_the_hole_of_a_frame_overlaps_nothing(window: MainWindow) -> None:
    """M6: Die Hülle des Rahmens umschließt den Quader, sein Volumen berührt ihn nicht."""
    frame_top = _a_box_and_its_top(window, 40.0, 40.0, 10.0)
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("face", frame_top, (-10.0, -10.0), (0.0, 0.0, 0.0)))
    flow.aim((10.0, 10.0))
    flow.place()
    flow.lift = Lift(-frame_top.through_depth, through=True)
    assert flow.settle()
    assert window.session.wait_for_idle(60_000)
    window.announce("")
    frame = next(iter(window.session.last_result.scene.objects.values()))
    low, high = frame.mesh.bounds.minimum, frame.mesh.bounds.maximum
    centre = ((low[0] + high[0]) / 2.0, (low[1] + high[1]) / 2.0)
    window.start_drawing()
    flow.take(("bed", bed_surface(), (centre[0] - 5.0, centre[1] - 5.0), (0.0, 0.0, 0.0)))
    flow.aim((centre[0] + 5.0, centre[1] + 5.0))
    flow.place()
    flow.lift = Lift(5.0)
    assert flow.settle()
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    assert flow.wait_for_overlap()
    assert len(window.session.last_result.scene.objects) == 2
    assert "überdeckt" not in window._announcement
    assert not any(button.isVisibleTo(window) for button in window._draw_offers)


def test_extrude_join_and_pocket_open_the_drawing_tool(window: MainWindow) -> None:
    """Menü, Palette und im Fusion-Schema E führen alle drei ins Aufziehen (G12)."""
    for name in ("sketch_extrude", "sketch_join", "sketch_pocket"):
        window.launch_operation(REGISTRY.get(name))
        assert window.drawing(), name
        assert window._sketch_panel is None, name
        assert window.draw_flow().inward_first == (name == "sketch_pocket"), name
        window.draw_flow().close()


def test_another_kind_keeps_its_own_dialog(window: MainWindow) -> None:
    """Wer für *Rotationskörper aufziehen* zeichnet, bekommt nach *Fertig* dessen Dialog."""
    window.start_sketch("sketch_revolve", text=sketch_to_text(shapes.rectangle(10.0, 20.0)))
    window.finish_sketch(keep=True)
    dialog = window._op_dialog
    assert dialog is not None and dialog.spec.name == "sketch_revolve"
    assert not window.drawing()
    dialog.reject()


# --- Review-Fixes: Art, Umriss, Richtung, Tasche ----------------------------------


def _a_box_and_its_top(
    window: MainWindow, width: float = 40.0, depth: float = 30.0, height: float = 20.0
) -> Any:
    window.session.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": width, "depth": depth, "height": height}
            )
        ],
    )
    assert window.session.wait_for_idle(60_000)
    entry = next(iter(window.session.last_result.scene.objects.values()))
    top = next(
        key
        for key, feature in entry.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 0.9
    )
    surface = face_surface(entry, top)
    assert surface is not None
    return surface


def _kind_choice(dialog: Any) -> QComboBox:
    return next(
        choice
        for choice in dialog.findChildren(QComboBox)
        if choice.findData("sketch_revolve") >= 0
    )


def test_the_kind_changes_in_the_step_dialog(window: MainWindow) -> None:
    """H1: Ein aufgezogener Quader wird im Schrittdialog zum Rotationskörper — derselbe Schritt."""
    from PySide6.QtGui import QStandardItemModel
    from PySide6.QtTest import QTest

    window.start_drawing()
    _three_clicks_on_the_bed(window)
    step = window.session.history.operations[-1].id
    window.edit_operation(step)
    dialog = window._op_dialog
    assert dialog is not None
    choice = _kind_choice(dialog)
    model = choice.model()
    assert isinstance(model, QStandardItemModel)
    pocket = model.item(choice.findData("sketch_pocket"))
    assert not pocket.isEnabled(), "ohne Körper gibt es keine Tasche"
    assert "Körper" in pocket.toolTip()
    assert choice.findData("field_cut") >= 0, "das Lochfeld steht mit in der Liste"
    choice.setCurrentIndex(choice.findData("sketch_revolve"))
    assert dialog.spec.name == "sketch_revolve"
    QTest.qWait(350)
    assert window.session.wait_for_idle(60_000)
    dialog.accept()
    assert window.session.wait_for_idle(60_000)
    operations = window.session.history.operations
    assert [entry.op for entry in operations] == ["sketch_revolve"], "ersetzt, nicht angehängt"
    body = next(iter(window.session.last_result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(math.pi * 40.0**2 * 30.0, rel=1e-6)
    window.action_undo()
    assert window.session.wait_for_idle(60_000)
    assert [entry.op for entry in window.session.history.operations] == ["sketch_extrude"]


def _an_outline_waiting_for_its_height(window: MainWindow) -> Any:
    """*Freie Form …*, ein Rechteck im Editor, *Fertig* — das Aufziehen wartet auf die Höhe."""
    window.start_drawing()
    flow = window.draw_flow()
    flow.arm_free()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.set_sketch(shapes.rectangle(20.0, 10.0))
    window.sketch_finish_button.click()
    assert window.drawing() and flow.draft is not None and flow.draft.outline is not None
    return flow


def test_escape_keeps_a_finished_outline_for_undo(window: MainWindow) -> None:
    """H2: Escape legt den Umriss beiseite, Strg+Z holt ihn — der Verlauf bleibt."""
    window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    _an_outline_waiting_for_its_height(window)
    window._escape()
    assert not window.drawing()
    assert window._discarded_sketch is not None
    assert "Strg+Z" in window._announcement
    window.action_undo()
    panel = window._sketch_panel
    assert panel is not None, "der Umriss ist zurück im Editor"
    assert panel.sketch_text(), "mit seiner Zeichnung"
    assert [entry.op for entry in window.session.history.operations] == ["create_box"]


def test_undo_in_the_height_phase_returns_to_the_editor(window: MainWindow) -> None:
    """H2: Strg+Z mit einem Umriss in der Hand führt zurück in den Editor, nie in den Verlauf."""
    window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    _an_outline_waiting_for_its_height(window)
    assert window.undo_action.isEnabled()
    window.action_undo()
    assert not window.drawing()
    assert window._sketch_panel is not None
    assert [entry.op for entry in window.session.history.operations] == ["create_box"]


def test_undo_before_the_first_click_says_how_to_go_on(window: MainWindow) -> None:
    """G10: Strg+Z in Phase 0 nimmt keinen Schritt und schweigt nicht."""
    window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    window.start_drawing()
    assert window.undo_action.isEnabled()
    window.action_undo()
    assert window.drawing()
    assert "Escape" in window._announcement
    assert [entry.op for entry in window.session.history.operations] == ["create_box"]


def test_a_lost_target_keeps_the_outline_and_clears_the_clicks(window: MainWindow) -> None:
    """F-k: Verschwindet der Körper, fällt der Entwurf mit Satz; ein Umriss bleibt für Strg+Z."""
    top = _a_box_and_its_top(window)
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("face", top, (-5.0, -5.0), (0.0, 0.0, 0.0)))
    flow.aim((5.0, 5.0))
    flow.place()
    window.session.undo()
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    assert flow.draft is not None and flow.draft.phase == 0
    assert "nicht mehr da" in window._announcement
    flow.close()
    top = _a_box_and_its_top(window)
    window.start_drawing()
    flow.arm_free()
    flow.take(("face", top, (0.0, 0.0), (0.0, 0.0, 0.0)))
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.set_sketch(shapes.rectangle(10.0, 10.0))
    window.sketch_finish_button.click()
    assert flow.draft is not None and flow.draft.outline is not None
    window.session.undo()
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    assert not window.drawing()
    assert window._discarded_sketch is not None, "der Umriss wartet auf Strg+Z"


def test_a_click_below_the_bed_builds_nothing(window: MainWindow) -> None:
    """M2: Ein Klick in die falsche Richtung sagt es und legt keinen Splitter an."""
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    flow.aim((40.0, 30.0))
    flow.place()
    flow.lift_to(-6.0)
    assert not flow.settle()
    assert "Unter das Bett" in window._announcement
    assert window.drawing() and window.session.history.operations == ()


def test_a_typed_height_keeps_the_direction_it_was_typed_in(window: MainWindow) -> None:
    """M3: Die Maus rutscht nach innen, nachdem 5 getippt ist — es bleibt ein Anbau."""
    top = _a_box_and_its_top(window)
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("face", top, (-5.0, -5.0), (0.0, 0.0, 0.0)))
    flow.aim((5.0, 5.0))
    flow.place()
    flow.lift = Lift(3.0)
    assert flow.type_first("5")
    assert flow.entry.names[0].text() == "Höhe"
    flow.move_to(10, 10)
    assert flow.lift is not None and flow.lift.height > 0.0, "die Maus ändert nichts mehr"
    flow.lift = Lift(-3.0)
    assert flow.type_values([5.0])
    assert window.session.wait_for_idle(60_000)
    assert window.session.history.operations[-1].op == "sketch_join"


def test_a_chosen_pocket_stays_a_pocket(window: MainWindow) -> None:
    """M4: *Loch oder Aussparung zeichnen …*, *Fertig*, 5 Enter — eine Tasche, 5 mm tief."""
    top = _a_box_and_its_top(window)
    window.object_tree.select_object(top.body)
    _object, feature = top.plane.removeprefix("feature:").split(":", 1)
    window._sketch_on_the_shown_face(feature, True)
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.set_sketch(
        shapes.rectangle_between((-5.0, -5.0), (5.0, 5.0), panel.canvas.sketch.plane)
    )
    window.sketch_finish_button.click()
    flow = window.draw_flow()
    assert window.drawing() and flow.inward_first
    assert "Tiefe" in window.draw_bar.state.text()
    assert flow.type_first("5")
    assert flow.entry.names[0].text() == "Tiefe"
    assert flow.type_values([5.0])
    assert window.session.wait_for_idle(60_000)
    assert window.session.history.operations[-1].op == "sketch_pocket"
    body = next(iter(window.session.last_result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(24000.0 - 500.0, rel=1e-6)


def test_a_pocket_without_a_body_stays_in_the_editor(window: MainWindow) -> None:
    """M4: Ohne Ziel geht die Zeichnung nicht verloren, der Satz nennt den Weg."""
    window.start_sketch("sketch_pocket", text=sketch_to_text(shapes.rectangle(10.0, 10.0)))
    window.finish_sketch(keep=True)
    assert window._sketch_panel is not None and not window.drawing()
    assert "Körper" in window._announcement


def test_an_open_outline_does_not_reach_the_height(window: MainWindow) -> None:
    """M5: Zwei Linien sind kein Umriss — der Editor bleibt, der Satz sagt es."""
    from app.core.types import Sketch, SketchElement

    window.start_sketch("")
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.set_sketch(
        Sketch(
            "plane:xy",
            (
                SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
                SketchElement("line", ((10.0, 0.0), (10.0, 10.0))),
            ),
        )
    )
    window.sketch_finish_button.click()
    assert window._sketch_panel is not None and not window.drawing()
    assert "geschlossenen Umriss" in window._announcement
    assert window.session.history.operations == ()


def test_a_figure_generator_gets_a_new_plate_and_the_video_its_dialog(
    qt_app: QApplication, window: MainWindow
) -> None:
    """M7: Die Erzeuger beim Release gehen ihren Weg, ohne ein Bild zu rendern."""
    from tools.make_figures import extrude_the_figure_sketch

    top = _a_box_and_its_top(window)
    window.object_tree.select_object(top.body)
    plane = top.plane
    text = sketch_to_text(shapes.rectangle_between((-5.0, -5.0), (5.0, 5.0), plane))
    window.start_sketch("sketch_extrude", text, plane=plane)
    extrude_the_figure_sketch(window, qt_app)
    assert [entry.op for entry in window.session.history.operations][-1] == "sketch_extrude"
    assert len(window.session.last_result.scene.objects) == 2, "eine neue Platte"
    window.start_sketch("sketch_extrude", sketch_to_text(shapes.rectangle(30.0, 20.0)))
    window.finish_sketch(keep=True, given={"height": 7.0})
    dialog = window._op_dialog
    assert dialog is not None and dialog.values()["height"] == pytest.approx(7.0)
    assert not window.drawing(), "gegebene Werte gehen in den Dialog, nicht ins Aufziehen"
    dialog.reject()


def test_other_actions_wait_while_drawing(window: MainWindow) -> None:
    """G2: Einfügen, Erzeugen, Teilen, Varianten, Formen und Skelett warten aufs Aufziehen."""
    window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    window.start_drawing()
    for action in (window.import_action, window.generate_action, window._toolbar_import):
        assert not action.isEnabled()
        assert "Escape" in action.toolTip()
    for action in (window._toolbar_sculpt, window._toolbar_armature):
        assert "Escape" in action.toolTip()
    window.action_auto_split()
    assert "Escape" in window._announcement
    window.announce("")
    window.action_variants()
    assert "Escape" in window._announcement
    assert window._toolbar_sketch.isChecked(), "Zeichnen steht gedrückt"
    window._toolbar_sketch.trigger()
    assert not window.drawing() and not window._toolbar_sketch.isChecked()


def test_the_bar_has_a_visible_way_out(window: MainWindow) -> None:
    """G10: *Schließen* in der Leiste — dasselbe wie Escape."""
    window.start_drawing()
    window.draw_bar.close_button.click()
    assert not window.drawing()


def test_a_single_click_is_no_unsaved_work(window: MainWindow) -> None:
    """G3: Ein Klick allein ist kein ungesicherter Stand; ein Umriss aus dem Editor ist es."""
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    assert not window._has_unsaved_gestures()
    flow.close()
    _an_outline_waiting_for_its_height(window)
    assert window._has_unsaved_gestures()


def test_a_value_beyond_the_limit_is_refused(window: MainWindow) -> None:
    """F-d: Die Zahl bleibt markiert stehen, der Satz nennt die Grenze, kein Schritt."""
    from app.ui.draw_tool import height_limits
    from app.ui.labels import length, limit_sentence

    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    flow.aim((40.0, 30.0))
    flow.place()
    flow.lift = Lift(5.0)
    assert flow.type_first("9")
    assert not flow.type_values([99_999.0])
    said = limit_sentence(length(99_999.0), length(height_limits()[1]), above=True)
    assert said in window._announcement, "der Satz nennt die Grenze aus dem Schema"
    assert flow.entry.fields[0].toolTip() == said
    assert window.session.history.operations == ()


def test_a_rectangle_beyond_the_face_still_cuts(window: MainWindow) -> None:
    """F-f: Ragt das Rechteck über die Fläche, schneidet die Tasche, so weit der Körper reicht."""
    top = _a_box_and_its_top(window)
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("face", top, (10.0, 5.0), (0.0, 0.0, 0.0)))
    flow.aim((30.0, 25.0))
    flow.place()
    flow.lift = Lift(-5.0)
    assert flow.settle()
    assert window.session.wait_for_idle(60_000)
    body = next(iter(window.session.last_result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(24000.0 - 10.0 * 10.0 * 5.0, rel=1e-6)


def test_a_pocket_that_splits_the_body_offers_to_split(window: MainWindow) -> None:
    """F-h: Zerfällt der Körper, sagt es der Satz und bietet *In Teile zerlegen* an."""
    top = _a_box_and_its_top(window)
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("face", top, (-2.0, -20.0), (0.0, 0.0, 0.0)))
    flow.aim((2.0, 20.0))
    flow.place()
    flow.lift = Lift(-top.through_depth, through=True)
    assert flow.settle()
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    assert "2 Teilen" in window._announcement
    offered = [
        button.property("operation") for button in window._draw_offers if button.isVisibleTo(window)
    ]
    assert offered == ["split_bodies"]


def test_without_the_exact_kernel_drawing_is_grey_and_says_why(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-j: ohne exakten Kern grau, mit dem Satz der Skizzen-Operationen."""
    import app.ui.main_window as module

    monkeypatch.setattr(module, "_drawing_needs_the_kernel", lambda: "Kern fehlt")
    window._update_actions()
    assert not window._toolbar_sketch.isEnabled()
    assert "Kern fehlt" in window._toolbar_sketch.toolTip()
    window.start_drawing()
    assert not window.drawing()
    assert "Kern fehlt" in window._announcement


def test_the_mark_reach_stays_the_same_in_logical_points_at_any_scaling(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Fangweite der Flächenmarken gilt in logischen Bildpunkten, gleich bei 100 und 200 %."""
    flow = window.draw_flow()
    surface = DrawSurface(plane="plane:xy", frame=bed_surface().frame, marks=((3.0, 0.0),))
    reached = []
    for ratio in (1.0, 2.0):
        monkeypatch.setattr(window.viewport, "_device_ratio", lambda ratio=ratio: ratio)
        # Bei doppelter Auflösung zeigt ein Millimeter doppelt so viele Gerätepunkte.
        monkeypatch.setattr(
            window.viewport, "pixels_per_mm", lambda _frame, ratio=ratio: 2.0 * ratio
        )
        monkeypatch.setattr(flow, "_step", lambda _frame: 0.0)
        reached.append(flow._snap((0.0, 0.0), surface) == (3.0, 0.0))
        reached.append(flow._snap((-3.0, 0.0), surface) == (3.0, 0.0))
    assert reached == [True, False, True, False]


def test_the_recognition_resumes_the_first_click(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abnahme 10: Nach der Erkennung geht es mit Klick 1 an derselben Stelle weiter."""
    top = _a_box_and_its_top(window)
    result = window.session.last_result
    entry = result.scene.objects[top.body]
    window.start_drawing()
    flow = window.draw_flow()
    flow._resume_at = (top.body, tuple(top.frame.origin), False)
    flow.close()
    flow.resume_after_recognition(result)
    assert window.drawing() and flow.draft is not None and flow.draft.phase == 1
    assert flow.draft.surface is not None and flow.draft.surface.body == entry.id


def test_free_form_opens_the_editor_and_finish_comes_back_for_the_height(
    window: MainWindow,
) -> None:
    """RM-561: *Freie Form …*, Linie in der Hand, *Fertig* — zurück in die Ansicht, Phase 3."""
    window.start_drawing()
    flow = window.draw_flow()
    flow.arm_free()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    panel = window._sketch_panel
    assert panel is not None, "der Klick öffnet den Skizzeneditor"
    assert panel.canvas.tool == "line", "mit der Linie in der Hand"
    panel.canvas.set_sketch(shapes.rectangle(20.0, 10.0))
    window.sketch_finish_button.click()
    assert window._sketch_panel is None
    assert window.drawing() and flow.draft is not None
    assert flow.draft.phase == 2, "es fehlt nur die Höhe"
    flow.lift = Lift(4.0)
    assert flow.settle()
    assert window.session.wait_for_idle(60_000)
    assert window.session.history.operations[-1].op == "sketch_extrude"
    assert window._op_dialog is None, "kein Dialog"


def test_the_drawing_step_keeps_its_simple_shape(window: MainWindow) -> None:
    window.start_drawing()
    _three_clicks_on_the_bed(window)
    text = window.session.history.operations[-1].params["sketch"]
    assert shapes.simple_shape(sketch_from_text(text)) == "rectangle"


# --- Nachprüfung: N1 bis N12 und F-i -------------------------------------------


@pytest.mark.parametrize(
    ("op_name", "said"), [("sketch_pocket", "Tasche"), ("sketch_join", "Anfügen")]
)
def test_a_chosen_pocket_or_join_refuses_the_bed(
    window: MainWindow, op_name: str, said: str
) -> None:
    """N1: Aus Menü oder Palette gewählt, nimmt die Art das Bett nicht an (Regel 21)."""
    window.launch_operation(REGISTRY.get(op_name))
    flow = window.draw_flow()
    assert flow.intent == op_name
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    assert flow.draft is not None and flow.draft.phase == 0
    assert said in window._announcement and "Fläche eines Körpers" in window._announcement
    assert window.session.history.operations == ()


def test_a_lost_body_brings_the_outline_back_on_the_bed(window: MainWindow) -> None:
    """N2: Nach F-k liegt der Umriss auf der Grundebene, *Fertig* führt in die Höhe."""
    top = _a_box_and_its_top(window)
    window.start_drawing()
    flow = window.draw_flow()
    flow.arm_free()
    flow.take(("face", top, (0.0, 0.0), (0.0, 0.0, 0.0)))
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.set_sketch(
        shapes.rectangle_between((-5.0, -5.0), (5.0, 5.0), panel.canvas.sketch.plane)
    )
    window.sketch_finish_button.click()
    assert flow.draft is not None and flow.draft.outline is not None
    window.session.undo()
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    assert window._discarded_sketch is not None
    window.action_undo()
    panel = window._sketch_panel
    assert panel is not None
    assert panel.canvas.sketch.plane == "plane:xy", "der Umriss selbst liegt auf dem Bett"
    window.sketch_finish_button.click()
    assert window.drawing() and flow.draft is not None and flow.draft.outline is not None
    flow.lift = Lift(4.0)
    assert flow.settle()
    assert window.session.wait_for_idle(60_000)
    assert window.session.history.operations[-1].op == "sketch_extrude"


def test_the_overlap_worker_gets_its_own_copies(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N3: Keine geteilte Arbeiterkopie ohne ihr Schloss — und ein exakter Körper bleibt exakt."""
    import app.ui.draw_flow as module
    from app.core.brep.kernel import Solid
    from app.ui import placement_flow

    handed: list[Any] = []
    original = module._OverlapWorker.__init__

    def noted(self: Any, made: Any, others: list[tuple[str, Any]]) -> None:
        handed.extend([made, *(other for _id, other in others)])
        original(self, made, others)

    monkeypatch.setattr(module._OverlapWorker, "__init__", noted)
    window.session.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 10.0})],
    )
    assert window.session.wait_for_idle(60_000)
    window.start_drawing()
    _three_clicks_on_the_bed(window)
    assert window.draw_flow().wait_for_overlap()
    assert len(handed) == 2
    shared = [held[1] for held in placement_flow._worker_copies.values()]
    scene = [entry.mesh for entry in window.session.last_result.scene.objects.values()]
    assert not any(any(copy is one for one in shared) for copy in handed)
    assert not any(any(copy is one for one in scene) for copy in handed)
    assert isinstance(handed[0], Solid), "der aufgezogene Körper bleibt exakt"


def test_the_film_pulls_up_its_plate_with_three_clicks(
    qt_app: QApplication, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N4: Der Langfilm zeigt den Weg von heute — drei Klicks, keine Skizze, kein Dialog davor."""
    from app.core.types import Parameter
    from tools.make_longform_video import pull_up_plate

    class Recorder:
        app = qt_app

        def __init__(self) -> None:
            self.window = window
            self.titles: list[str] = []

        def add(self, title: str, detail: str, seconds: float = 6.0, **_rest: Any) -> None:
            self.titles.append(title)

        def click(self, title: str, detail: str, **_rest: Any) -> None:
            self.titles.append(title)

    def no_sketch(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("der Film geht nicht über den Skizzenmodus")

    monkeypatch.setattr(window, "start_sketch", no_sketch)
    window._show_start_screen(False)  # wie ``_begin_video``: der Film beginnt im Arbeitsbereich
    assert window.session.add_parameter(
        Parameter(name="plattenstaerke", value=6.0, unit="mm", minimum=3.0, maximum=12.0)
    )
    assert window.session.wait_for_idle(60_000)
    recorder = Recorder()
    pull_up_plate(
        recorder,
        window.session,
        (70.0, 45.0, 6.0),
        {"height": "=@plattenstaerke", "name": "Montagehalter"},
        bind=("Binden", "Die Höhe folgt dem Projektmaß."),
        accept=("Übernehmen", "Ein Klick übernimmt."),
    )
    operations = window.session.history.operations
    assert [entry.op for entry in operations] == ["sketch_extrude"]
    assert operations[-1].params["height"] == "=@plattenstaerke"
    body = next(iter(window.session.last_result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(70.0 * 45.0 * 6.0, rel=1e-6)
    assert "Zeichnen öffnen" in recorder.titles


def test_a_changed_outline_goes_along_to_the_hole_field(window: MainWindow) -> None:
    """N5: Wer den Umriss im Dialog ändert und auf *Lochfeld* wechselt, behält die Änderung."""
    window.start_drawing()
    _three_clicks_on_the_bed(window)
    window.edit_operation(window.session.history.operations[-1].id)
    dialog = window._op_dialog
    assert dialog is not None
    changed = sketch_to_text(shapes.rectangle_between((0.0, 0.0), (25.0, 15.0)))
    dialog._editors["sketch"].set_text(changed)
    choice = _kind_choice(dialog)
    choice.setCurrentIndex(choice.findData("sketch_revolve"))
    choice.setCurrentIndex(choice.findData("field_cut"))
    assert dialog._editors["region_sketch"].text() == changed
    dialog.reject()


def test_a_refused_start_leaves_draw_unpressed(window: MainWindow) -> None:
    """N6: Sagt *Zeichnen* ab, steht der Knopf nicht gedrückt."""
    window.start_sketch("")
    assert window._sketch_panel is not None
    window._toolbar_sketch.trigger()
    assert not window.drawing()
    assert not window._toolbar_sketch.isChecked()
    window.finish_sketch(keep=False)


def test_a_project_change_cancels_the_overlap_check(window: MainWindow) -> None:
    """N7: Ein Projektwechsel bricht die Überdeckungsprüfung ab; ihre Schwelle ist ein Volumen."""
    from app.core.scene.cancel import CancelSignal
    from app.core.units import EPS_DISPLAY
    from app.ui.draw_flow import OVERLAP_VOLUME

    assert pytest.approx(EPS_DISPLAY**3) == OVERLAP_VOLUME

    class Running:
        cancelled = CancelSignal()

    flow = window.draw_flow()
    running = Running()
    flow._overlap = running  # type: ignore[assignment]
    window.session.start_new()
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    assert running.cancelled.is_cancelled


def test_the_escape_key_is_named_by_qt(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N8: Der Tastenname im Tooltip von *Schließen* kommt aus Qt (Regel 20)."""
    import app.ui.draw_bar as module

    class French:
        class SequenceFormat:
            NativeText = 0

        def __init__(self, _key: Any) -> None:
            pass

        def toString(self, _form: Any) -> str:  # noqa: N802 — Qt-Name
            return "Échap"

    monkeypatch.setattr(module, "QKeySequence", French)
    bar = module.DrawBar()
    assert "Échap" in bar.close_button.toolTip()
    bar.deleteLater()


def test_the_resume_after_recognition_comes_through_the_scene(window: MainWindow) -> None:
    """N10, Abnahme 10: Das nächste Bild nach der Erkennung nimmt Klick 1 an derselben Stelle."""
    top = _a_box_and_its_top(window)
    flow = window.draw_flow()
    point = (top.frame.origin[0] + 3.0, top.frame.origin[1] + 2.0, top.frame.origin[2])
    flow._resume_at = (top.body, point, False)
    window.session.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(top.body,), params={"x": 0.0})],
    )
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    assert window.drawing() and flow.draft is not None and flow.draft.phase == 1
    assert flow.draft.surface is not None and flow.draft.surface.body == top.body
    reach = max(flow._step(top.frame), 1.0)
    assert flow.draft.first == pytest.approx((3.0, 2.0), abs=reach), "an derselben Stelle"


def test_enter_on_plate_two_sets_the_offset_of_the_body(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N10, G4: Auf Platte 2 steht der Entwurf beim Körper, nicht eine Bettbreite daneben."""
    top = _a_box_and_its_top(window)
    window.object_tree.select_object(top.body)
    monkeypatch.setattr(window, "drawn_face_of_the_selection", lambda: top)
    monkeypatch.setattr(window.viewport, "view_offset_of", lambda _body: (260.0, 0.0, 0.0))
    window.start_drawing()
    flow = window.draw_flow()
    flow.press_enter()
    assert flow.draft is not None and flow.draft.shift == (260.0, 0.0, 0.0)


def test_an_unchanged_restored_outline_is_not_offered_twice(window: MainWindow) -> None:
    """N12: Zurückgeholt und unverändert verworfen — dann gehört Strg+Z wieder dem Verlauf."""
    window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    _an_outline_waiting_for_its_height(window)
    window._escape()
    window.action_undo()
    assert window._sketch_panel is not None
    window.finish_sketch(keep=False)
    assert window._discarded_sketch is None
    window.action_undo()
    assert window.session.wait_for_idle(60_000)
    assert window._sketch_panel is None
    assert window.session.history.operations == (), "Strg+Z nahm den Quader"


def _an_open_box_with_a_failing_pocket(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Ein offenes Netz, an dem die Tasche scheitert, bis es repariert ist (F-i)."""
    import dataclasses

    from app.core.errors import NotManifoldError
    from tests.helpers import MESHES

    window.session.import_model(MESHES / "broken_open.stl")
    assert window.session.wait_for_idle(120_000)
    window.session.change_params(window.session.history.operations[0].id, {"mend": False})
    assert window.session.wait_for_idle(120_000)
    spec = REGISTRY.get("sketch_pocket")
    original = spec.fn

    def failing(ctx: Any) -> Any:
        if not getattr(ctx.inputs[0].mesh, "is_watertight", True):
            raise NotManifoldError(open_edges=3)
        return original(ctx)

    monkeypatch.setitem(REGISTRY._ops, "sketch_pocket", dataclasses.replace(spec, fn=failing))
    entry = next(iter(window.session.last_result.scene.objects.values()))
    top = max(
        (key for key, feature in entry.features.items() if feature.kind == "face"),
        key=lambda key: entry.features[key].params["normal"][2],
    )
    surface = face_surface(entry, top)
    assert surface is not None
    window.start_drawing()
    flow = window.draw_flow()
    flow.take(("face", surface, (-2.0, -2.0), (0.0, 0.0, 0.0)))
    assert flow.type_values([4.0, 4.0]), "getippt: Ein Klick fiele aufs Raster"
    flow.lift = Lift(-1.0)
    assert flow.settle()
    assert window.session.wait_for_idle(120_000)
    QApplication.processEvents()
    return flow


def test_a_failed_pocket_comes_back_and_repair_computes_the_same_step(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-i: Der Entwurf kommt zurück, die Leiste nennt die Ursache, *Reparieren* rechnet weiter."""
    flow = _an_open_box_with_a_failing_pocket(window, monkeypatch)
    assert window.drawing() and flow.failed
    bar = window.draw_bar
    assert "3 Stellen" in bar.state.text()
    assert bar.repair.isVisibleTo(bar) and bar.places.isVisibleTo(bar)
    bar.repair.click()
    assert window.session.wait_for_idle(120_000)
    QApplication.processEvents()
    assert not window.drawing(), "derselbe Schritt ist gerechnet, ohne neuen Klick"
    result = window.session.last_result
    assert result.stopped_at is None
    operations = [entry.op for entry in window.session.history.operations]
    assert operations.count("sketch_pocket") == 1 and "repair" in operations
    body = next(iter(result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(20.0**3 - 4.0 * 4.0 * 1.0, rel=1e-6)


def test_escape_after_a_failed_pocket_takes_the_step_and_lays_the_outline_aside(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-i: Escape nimmt den gescheiterten Schritt zurück, Strg+Z holt den Umriss in den Editor."""
    flow = _an_open_box_with_a_failing_pocket(window, monkeypatch)
    assert flow.failed
    window._escape()
    assert window.session.wait_for_idle(120_000)
    assert not window.drawing()
    assert [entry.op for entry in window.session.history.operations] == ["load"]
    assert window._discarded_sketch is not None
    window.action_undo()
    assert window._sketch_panel is not None and window._sketch_panel.sketch_text()


def test_places_after_a_failed_pocket_shows_the_defect_map(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-i: *Stellen zeigen* lässt den Schritt stehen und zeigt die Karte der Stellen."""
    shown: list[str] = []
    monkeypatch.setattr(window, "show_places_of", shown.append)
    flow = _an_open_box_with_a_failing_pocket(window, monkeypatch)
    window.draw_bar.places.click()
    assert not window.drawing() and not flow.failed
    assert shown == [next(iter(window.session.last_result.scene.objects))]
    assert window.session.history.operations[-1].op == "sketch_pocket"
