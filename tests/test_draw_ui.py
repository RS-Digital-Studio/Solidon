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

from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_from_text
from app.ui.draw_tool import DRAW_KEY, Lift, bed_surface, face_surface
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
    assert "überdeckt" in window._announcement
    offered = [button.text() for button in window._draw_offers if button.isVisibleTo(window)]
    assert offered == ["Vereinigen", "Davon abziehen"]
    assert len(window.session.last_result.scene.objects) == 2


def test_extrude_join_and_pocket_open_the_drawing_tool(window: MainWindow) -> None:
    """Menü, Palette und im Fusion-Schema E führen über ``sketch_extrude`` ins Aufziehen."""
    window.launch_operation(REGISTRY.get("sketch_extrude"))
    assert window.drawing()
    assert window._sketch_panel is None


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
