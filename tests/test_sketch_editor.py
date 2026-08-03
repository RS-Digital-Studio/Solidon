"""Der grafische Skizzeneditor (§30.1, Stufe zwei), offscreen.

Geprüft wird die Verdrahtung und das Modell, keine Pixel: gezeichnet wird
über dieselben Methoden, die auch die Maus ruft, Bedingungen gehen den Weg
der Knöpfe, und am Ende steht der Text, den die Skizzen-Ops lesen.

Am Ende der Datei der **Skizzenmodus des Fensters**: er benutzt dasselbe
Panel, geprüft wird dort deshalb der Weg hinein und heraus, nicht noch einmal
das Zeichnen.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("scipy")

from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_from_text, sketch_to_text
from app.ui.op_dialog import OperationDialog
from app.ui.sketch_editor import (
    ExpressionDialog,
    SketchCanvas,
    SketchEditorDialog,
    SketchField,
)


def test_a_drawn_line_becomes_determined_by_constraints(qt_app: QApplication) -> None:
    """Der Kern von §30.1: zeichnen, Bedingungen setzen, und die
    Freiheitsgrade zählen live herunter, bis die Skizze bestimmt ist."""
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    assert canvas.solved is not None
    assert canvas.solved.free_dof == 4, "zwei freie Punkte"

    canvas.add_constraint("fixed", (0,))
    canvas.add_constraint("horizontal", (0, 1))
    canvas.add_constraint("distance", (0, 1), "30")
    assert canvas.solved.free_dof == 0, "fest + waagerecht + Maß bestimmt die Linie"


def test_a_conflict_keeps_the_last_valid_solution(qt_app: QApplication) -> None:
    """Ein widersprüchliches Maß wird eine Meldung mit dem benannten Paar —
    die letzte gültige Lage bleibt sichtbar (§15.3, Regel 17)."""
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    canvas.add_constraint("fixed", (0,))
    canvas.add_constraint("distance", (0, 1), "30")
    before = canvas.points()

    canvas.add_constraint("distance", (0, 1), "40")

    assert canvas.conflict, "die Statuszeile nennt den Konflikt"
    assert canvas.points() == before, "die Anzeige bleibt die letzte gültige"

    canvas.remove_constraint(2)
    assert not canvas.conflict, "die Bedingung zu entfernen heilt die Skizze"


def test_a_sketch_measure_may_read_a_project_parameter(qt_app: QApplication) -> None:
    """Maße sind Ausdrücke der Parametergrammatik (§13) — der Editor rechnet
    mit den aufgelösten Projektparametern."""
    canvas = SketchCanvas(parameter_values={"width": 25.0})
    canvas.add_element("line", ((0.0, 0.0), (10.0, 0.0)))
    canvas.add_constraint("fixed", (0,))
    canvas.add_constraint("horizontal", (0, 1))
    canvas.add_constraint("distance", (0, 1), "=@width")

    assert canvas.solved is not None and canvas.solved.free_dof == 0
    end = canvas.points()[1]
    assert end[0] == pytest.approx(25.0), "die Linie ist so lang wie @width"


def test_placing_snaps_to_an_existing_point(qt_app: QApplication) -> None:
    """Ein Klick nahe eines vorhandenen Punkts fängt: das neue Element
    bekommt eine Deckungs-Bedingung statt einer Kopie der Zahl — und der
    ganze Klickzug ist ein einziger Rückgängig-Schritt."""
    canvas = SketchCanvas()
    canvas.resize(400, 400)
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))

    canvas.set_tool("line")
    canvas.place(canvas._to_screen(30.1, 0.05))
    canvas.place(canvas._to_screen(30.0, 20.0))

    assert len(canvas.sketch.elements) == 2
    kinds = [entry.kind for entry in canvas.sketch.constraints]
    assert kinds == ["coincident"], "der Fang wird eine Deckung"

    canvas.undo()
    assert len(canvas.sketch.elements) == 1, "ein Rückgängig nimmt den ganzen Klickzug"
    assert not canvas.sketch.constraints


def test_inserting_a_shape_shifts_its_targets(qt_app: QApplication) -> None:
    """Eine Grundform hinter bestehenden Elementen behält ihre Bedingungen —
    die Ziele zählen über die ganze flache Punktliste."""
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    rectangle = shapes.rectangle(40.0, 20.0)

    canvas.insert_shape(rectangle)

    assert len(canvas.sketch.elements) == 1 + len(rectangle.elements)
    shift = 2
    first = canvas.sketch.constraints[0]
    assert first.targets == tuple(target + shift for target in rectangle.constraints[0].targets)
    assert canvas.solved is not None, "die verschobene Form löst sich weiter"


def test_the_editor_round_trips_the_op_text(qt_app: QApplication) -> None:
    """Der Editor liest und schreibt denselben Text, den die Skizzen-Ops
    lesen — es gibt keinen zweiten Skizzenbegriff (§30.1)."""
    text = sketch_to_text(shapes.circle(20.0))
    dialog = SketchEditorDialog(text)

    written = dialog.sketch_text()

    assert sketch_from_text(written) == sketch_from_text(text)


def test_a_damaged_text_is_not_silently_replaced(qt_app: QApplication) -> None:
    """Ein beschädigter Parametertext öffnet einen leeren Editor mit dem
    Grund in der Statuszeile — im Feld bleibt der alte Wert, bis jemand
    Übernehmen drückt."""
    dialog = SketchEditorDialog('{"plane": 7}')

    assert not dialog.canvas.sketch.elements
    assert dialog.status.text(), "die Statuszeile sagt, warum hier nichts steht"


def test_constraint_offers_follow_the_selection(qt_app: QApplication) -> None:
    """Die Knöpfe folgen der Auswahl: eine Linie bietet Waagerecht an,
    keine zwei Punkte — nicht andersherum (§30.1)."""
    dialog = SketchEditorDialog(sketch_to_text(shapes.rectangle(40.0, 20.0)))
    canvas = dialog.canvas

    canvas.selection = [("line", (0, 1))]
    offers = dialog.constraint_offers()
    assert offers["horizontal"] and not offers["coincident"]

    canvas.selection = [("point", (0,)), ("point", (2,))]
    offers = dialog.constraint_offers()
    assert offers["coincident"] and offers["distance"] and not offers["parallel"]


def test_the_expression_dialog_validates_inline(qt_app: QApplication) -> None:
    """Ein Maß außerhalb der Grammatik fällt inline durch — kein Fenster auf
    dem Fenster, kein eval (§13, Regel 10)."""
    dialog = ExpressionDialog({"width": 25.0})

    dialog.field.setText("import os")
    dialog._accept()
    # ``isVisible`` wäre offscreen immer falsch — ein nie gezeigter Dialog
    # hat keine sichtbaren Kinder. Der Text ist die prüfbare Wahrheit.
    assert dialog.problem.text(), "alles außerhalb der Grammatik wird abgelehnt"
    assert dialog.result() != ExpressionDialog.DialogCode.Accepted

    dialog.field.setText("=@width / 2")
    dialog._accept()
    assert dialog.result() == ExpressionDialog.DialogCode.Accepted


def test_the_sketch_field_carries_the_parameter(qt_app: QApplication) -> None:
    """Der ``kind="sketch"``-Parameter wird ein Feld mit Zeichnen-Knopf —
    und sein Text reist unverändert in die Werte der Operation."""
    spec = REGISTRY.get("sketch_extrude")
    text = sketch_to_text(shapes.rectangle(40.0, 20.0))
    dialog = OperationDialog(spec, [], values={"sketch": text})

    field = dialog._editors["sketch"]
    assert isinstance(field, SketchField)
    assert dialog.values()["sketch"] == text
    assert "4" in field.summary.text(), "die Zusammenfassung zählt die Elemente"

    fired: list[bool] = []
    dialog.valuesChanged.connect(lambda: fired.append(True))
    field.set_text("")
    assert fired, "eine geänderte Skizze meldet sich bei der Live-Vorschau"
    assert dialog.values()["sketch"] == ""


def test_removing_an_element_renumbers_the_constraints(qt_app: QApplication) -> None:
    """Löschen entfernt die Bedingungen des Elements und nummeriert die
    übrigen Ziele um — eine Bedingung auf einen toten Punkt wäre ein
    stiller Fehler im Text."""
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    canvas.add_element("line", ((0.0, 10.0), (30.0, 10.0)))
    canvas.add_constraint("horizontal", (2, 3))

    canvas.selection = [("line", (0, 1))]
    canvas.remove_selected()

    assert len(canvas.sketch.elements) == 1
    assert canvas.sketch.constraints[0].targets == (0, 1), "die Ziele sind umnummeriert"


def test_the_chosen_plane_travels_with_the_sketch(qt_app: QApplication) -> None:
    """Die Ebene wird vor dem Zeichnen gewählt und reist im Text mit (§30.1).

    Sie zu wählen ist erst dann etwas wert, wenn sie ankommt —
    ``tests/test_sketch_ops.py`` misst am Körper nach, dass sie das tut.
    """
    from app.ui.sketch_editor import SketchPanel

    panel = SketchPanel()
    try:
        assert panel.canvas.sketch.plane == "plane:xy", "liegend ist die Vorgabe"

        panel.plane_choice.setCurrentIndex(panel.plane_choice.findData("plane:xz"))
        panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))

        assert panel.canvas.sketch.plane == "plane:xz"
        assert sketch_from_text(panel.sketch_text()).plane == "plane:xz"
    finally:
        panel.deleteLater()


def test_the_canvas_knows_when_a_sketch_leaves_the_build_volume(qt_app: QApplication) -> None:
    """Die Zeichenfläche ist der früheste Ort, an dem ein zu großes Teil
    auffällt (Konzept P15 §4, E1).

    Später kostet derselbe Fehler einen Export, einen Slicerlauf und die
    Frage, warum das Teil nicht auf die Platte passt. SindriCAD kann eine
    Skizze zeichnen; ob sie in den Drucker passt, weiß dort niemand.
    """
    canvas = SketchCanvas()
    canvas.set_bed((220.0, 220.0))
    canvas.insert_shape(shapes.rectangle(40.0, 20.0))
    assert not canvas.outside_bed(), "vierzig Millimeter passen auf zweihundertzwanzig"

    canvas.set_sketch(shapes.rectangle(300.0, 20.0))
    assert canvas.outside_bed(), "dreihundert nicht"

    # Ohne bekannten Bauraum wird nichts behauptet.
    canvas.set_bed(None)
    assert not canvas.outside_bed()


def test_a_measure_is_shown_rounded_but_stored_exactly(qt_app: QApplication) -> None:
    """§11.2: gerundet wird in der Anzeige, nie im Wert.

    Grundformen schreiben neun Nachkommastellen, damit kein ``1e-05`` in einem
    Ausdruck landet. An der Bemaßung stand damit ``40.000000000``.
    """
    from app.ui.sketch_editor import readable_measure

    assert readable_measure("40.000000000") == "40.00"
    assert readable_measure("12.345000000") == "12.35"
    # Ein Ausdruck bleibt, was er ist: ihn auszurechnen verbärge den Parameter.
    assert readable_measure("=@width / 2") == "=@width / 2"

    text = sketch_to_text(shapes.rectangle(40.0, 20.0))
    assert "40.000000000" in text, "gespeichert bleibt die genaue Zahl"


# --- der Skizzenmodus im Fenster (§30.1 Stufe zwei) -----------------------------


def test_a_sketch_operation_opens_the_mode_not_a_dialog(qt_app: QApplication) -> None:
    """Der Bauplan verlangt den Editor **im Viewport**, nicht in einem Fenster
    darüber (§30.1).

    Geprüft wird, was ein Mensch tut: den Menüeintrag auslösen. Dahinter
    entscheidet ``_has_sketch_param``, ob es in den Modus geht — und für eine
    Operation ohne Skizzenfeld darf es das nicht.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        assert not window.sketching()

        window.start_sketch("sketch_extrude")
        assert window.sketching(), "die Zeichenfläche liegt vor der Ansicht"
        assert window.middle_stack.currentWidget() is not window.viewport
        # ``isHidden`` statt ``isVisible``: ein Fenster, das nie ``show()``
        # gesehen hat, hat keine sichtbaren Kinder — versteckt worden zu sein
        # ist die Aussage, die hier trägt.
        assert not window.sketch_bar.isHidden(), "Fertig und Verwerfen stehen bereit"

        # Escape verlässt den Modus wie jedes andere Werkzeug (§2.1).
        window._escape()
        assert not window.sketching()
        assert window.middle_stack.currentWidget() is window.viewport
    finally:
        window.deleteLater()


def test_leaving_the_sketch_mode_empty_starts_no_operation(qt_app: QApplication) -> None:
    """Wer nichts gezeichnet hat, hat nichts gemeint.

    Ohne das öffnete jedes versehentliche Escape einen Operationsdialog auf
    einer leeren Skizze — eine Sackgasse, die §2.1 ausdrücklich ausschließt.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("sketch_extrude")
        window.finish_sketch(keep=True)
        assert not window.sketching()
        assert not window.session.history.transactions, "nichts gezeichnet, nichts angewandt"
    finally:
        window.deleteLater()


def test_the_drawn_sketch_reaches_the_operation(qt_app: QApplication) -> None:
    """Was gezeichnet wurde, steht danach im Parameter der Operation.

    Der Text ist derselbe, den auch der Dialog erzeugt — es gibt keinen
    zweiten Skizzenbegriff (§30.1), und dieser Test hält genau das fest.
    """
    from app.ui.main_window import _sketch_param
    from app.ui.sketch_editor import SketchPanel

    panel = SketchPanel()
    try:
        panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))
        text = panel.sketch_text()
        assert text, "eine eingefügte Grundform ist eine Skizze"
        assert sketch_from_text(text).elements, "und sie liest sich zurück"
        assert _sketch_param("sketch_extrude") == "sketch"
    finally:
        panel.deleteLater()
