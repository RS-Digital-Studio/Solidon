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
    SketchPanel,
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


def test_a_spline_is_drawn_with_as_many_clicks_as_you_like(qt_app: QApplication) -> None:
    """Ein Spline endet nicht bei einer Punktzahl, sondern wenn jemand sagt,
    dass er fertig ist (D11).

    Linie, Kreis und Bogen schließen sich nach zwei oder drei Klicks selbst —
    beim Spline geht das nicht, weil es keine richtige Zahl gibt. Doppelklick
    oder Eingabetaste schließen ihn.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)
    canvas.set_tool("spline")

    for x, y in ((0.0, 0.0), (10.0, 8.0), (20.0, -4.0), (30.0, 0.0)):
        canvas.place(canvas._to_screen(x, y))
    assert not canvas.sketch.elements, "solange gesammelt wird, entsteht nichts"

    canvas.finish_spline()
    assert len(canvas.sketch.elements) == 1
    element = canvas.sketch.elements[0]
    assert element.kind == "spline"
    assert len(element.points) == 4, "so viele Punkte, wie geklickt wurde"


def test_a_spline_with_one_point_is_dropped(qt_app: QApplication) -> None:
    """Ein Spline durch einen Punkt ist ein Punkt — und den gibt es als
    eigenes Werkzeug. Die gesammelten Klicks fallen weg, statt eine ungültige
    Skizze zu erzeugen, die der Solver dann ablehnt.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)
    canvas.set_tool("spline")
    canvas.place(canvas._to_screen(5.0, 5.0))

    canvas.finish_spline()

    assert not canvas.sketch.elements
    assert canvas.solved is None


def test_a_reference_measure_shows_what_is_there(qt_app: QApplication) -> None:
    """Ein Referenzmaß zeigt den gemessenen Abstand in Klammern (D13).

    In Klammern wie in jedem CAD, damit man es nie mit einem treibenden Maß
    verwechselt — das zeigt seinen Ausdruck, auch wenn der Solver ihn gerade
    nicht erfüllen konnte.
    """
    from app.core.types import SketchConstraint
    from app.ui.sketch_editor import measure_label

    points = [(0.0, 0.0), (30.0, 40.0)]
    reference = SketchConstraint(kind="reference", targets=(0, 1))
    assert measure_label(reference, points) == "(50,00)", "drei, vier, fünf"

    driving = SketchConstraint(kind="distance", targets=(0, 1), value="=@width")
    assert measure_label(driving, points) == "=@width", "ein Ausdruck bleibt der Ausdruck"

    # Ein Ziel, das es nicht gibt, malt nichts statt abzustürzen.
    assert measure_label(SketchConstraint(kind="reference", targets=(0, 9)), points) == ""


def test_a_reference_measure_is_offered_for_two_points(qt_app: QApplication) -> None:
    """Es passt zur selben Auswahl wie ein Maß — zwei Punkte."""
    panel = SketchPanel(sketch_to_text(shapes.rectangle(40.0, 20.0)))
    try:
        panel.canvas.selection = [("point", (0,)), ("point", (2,))]
        offers = panel.constraint_offers()
        assert offers["reference"] and offers["distance"]

        panel.canvas.selection = [("line", (0, 1))]
        assert not panel.constraint_offers()["reference"]
    finally:
        panel.deleteLater()


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

    # Gelesen wird der gespeicherte Wert — der trägt einen Punkt, weil er eine
    # Zahl ist. Geschrieben wird in der Schreibweise der Anzeigesprache.
    assert readable_measure("40.000000000") == "40,00"
    assert readable_measure("12.345000000") == "12,35"
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


# --- Orientierung und Kürzel (Konzept Teil 4, E15 und E16) ----------------------


def test_the_axes_have_their_own_colours_and_letters() -> None:
    """Fusion zeigt einen sichtbaren Ursprung und durchgezogene Achsen in Rot
    und Grün; Formwerk zeichnete beide in der Rasterfarbe.

    Wo der Nullpunkt liegt, musste man aus der Zeichnung erschließen. Die
    Buchstaben stehen daneben, weil Farbe nie allein trägt (Regel 18).
    """
    from app.ui.palette import ROLES

    assert ROLES["axis_x"] != ROLES["axis_y"]
    assert ROLES["axis_x"] not in (ROLES["axis_y"], ROLES["select"])


def test_every_drawing_tool_wears_its_key(qt_app: QApplication) -> None:
    """„Die Kürzel stehen neben den Knöpfen, so lernt man sie nebenbei" (§19.2).

    Nachgestellt hatten `L`, `R` und `C` im Editor gar nichts bewirkt —
    „Auswählen" blieb aktiv.
    """
    from app.ui.sketch_editor import TOOL_KEYS

    panel = SketchPanel()
    for name, key in TOOL_KEYS.items():
        button = panel._tool_buttons[name]
        assert key in button.text(), f"{name} trägt sein Kürzel nicht"
        assert button.toolTip(), "und der Tooltip bleibt der Klartext"


def test_a_key_picks_the_tool_and_the_button_follows(qt_app: QApplication) -> None:
    """Sonst stünde die Leiste auf „Auswählen", während gezeichnet wird."""
    panel = SketchPanel()

    panel.choose_tool("line")
    assert panel.canvas.tool == "line"
    assert panel._tool_buttons["line"].isChecked()
    assert not panel._tool_buttons["select"].isChecked()

    panel.choose_tool("select")
    assert panel.canvas.tool == "select"
    assert panel._tool_buttons["select"].isChecked()


def test_the_drawing_keys_follow_fusion(qt_app: QApplication) -> None:
    """Wer aus Fusion kommt, hat sie in den Fingern: L Linie, C Kreis,
    A Bogen, R Rechteck, D Bemaßung, Esc beendet das Werkzeug."""
    from app.ui.sketch_editor import ACTION_KEYS, TOOL_KEYS

    assert TOOL_KEYS["line"] == "L"
    assert TOOL_KEYS["circle"] == "C"
    assert TOOL_KEYS["arc"] == "A"
    assert TOOL_KEYS["select"] == "Esc"
    assert ACTION_KEYS["rectangle"] == "R"
    assert ACTION_KEYS["distance"] == "D"


def test_the_keys_only_apply_while_drawing(qt_app: QApplication) -> None:
    """Außerhalb des Skizzenmodus liegen R und C auf Drehen und Fasen.

    Kontextabhängig zu belegen ist genau das, was Fusion tut, und der einzige
    Weg, beide Sätze widerspruchsfrei zu haben.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QShortcut

    panel = SketchPanel()
    keys = {shortcut.key().toString() for shortcut in panel.findChildren(QShortcut)}
    assert {"L", "C", "A", "R", "D"} <= keys

    for shortcut in panel.findChildren(QShortcut):
        assert shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut


def test_the_drawing_keys_win_while_drawing(qt_app: QApplication) -> None:
    """`R` und `C` liegen im Fusion-Schema auf Drehen und Fasen.

    Qt lässt bei zwei aktiven Kürzeln derselben Taste **keines** von beiden
    feuern — die Zeichenkürzel wären also nicht nur zweitrangig gewesen,
    sondern wirkungslos. Im Skizzenmodus ist deshalb keine Operation dran, und
    das ist zugleich die inhaltlich richtige Aussage: wer zeichnet,
    modelliert nicht.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings(shortcut_scheme="fusion"))
    try:
        colliding = [
            action
            for name, action in window._op_actions.items()
            if any(sequence.toString() in {"R", "C", "P", "S"} for sequence in action.shortcuts())
        ]
        assert colliding, "sonst prüft dieser Test nichts"

        window.start_sketch("sketch_extrude")
        assert not any(action.isEnabled() for action in colliding), (
            "im Skizzenmodus gilt der Zeichensatz"
        )

        window.finish_sketch(keep=False)
        window.session.wait_for_idle()
        assert window._sketch_panel is None
    finally:
        window.deleteLater()


# --- Die Ändern-Gruppe (Konzept Teil 4, E17) ------------------------------------


def _cross_canvas() -> SketchCanvas:
    from app.core.types import Sketch, SketchElement

    canvas = SketchCanvas()
    canvas.set_sketch(
        Sketch(
            plane="plane:xy",
            elements=(
                SketchElement(kind="line", points=((-10.0, 0.0), (10.0, 0.0))),
                SketchElement(kind="line", points=((0.0, -10.0), (0.0, 10.0))),
            ),
        )
    )
    return canvas


def test_trimming_takes_the_clicked_half(qt_app: QApplication) -> None:
    """Ohne Trimmen ist jede Kontur Handarbeit, die nicht aus einer Grundform
    kommt — der Befund aus dem Vergleich mit Fusion."""
    canvas = _cross_canvas()
    canvas.set_tool("trim")

    canvas.cut_or_grow(canvas._to_screen(-5.0, 0.0))

    line = canvas.sketch.elements[0]
    assert line.points[0][0] == pytest.approx(0.0), "die geklickte Hälfte ist weg"


def test_a_trim_that_cannot_work_says_why(qt_app: QApplication) -> None:
    """Regel 17, und im Bild statt in einem Dialog: was man wegklickt, bevor
    man es gelesen hat, hat nichts gesagt."""
    from app.core.types import Sketch, SketchElement

    canvas = SketchCanvas()
    canvas.set_sketch(
        Sketch(
            plane="plane:xy",
            elements=(SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),),
        )
    )
    canvas.set_tool("trim")
    said: list[str] = []
    canvas.statusChanged.connect(said.append)

    canvas.cut_or_grow(canvas._to_screen(5.0, 0.0))

    assert said and "kreuzt" in said[-1]
    assert len(canvas.sketch.elements) == 1, "und nichts ist passiert"


def test_offsetting_needs_a_selection(qt_app: QApplication) -> None:
    canvas = _cross_canvas()
    said: list[str] = []
    canvas.statusChanged.connect(said.append)

    canvas.offset_selected(3.0)

    assert said and "auswählen" in said[-1]
    assert len(canvas.sketch.elements) == 2


def test_offsetting_the_selection_adds_a_copy(qt_app: QApplication) -> None:
    canvas = _cross_canvas()
    canvas.selection = [("line", (0, 1))]

    canvas.offset_selected(3.0)

    assert len(canvas.sketch.elements) == 3, "die Vorlage bleibt, die Kopie kommt dazu"


def test_mirroring_the_selection_adds_a_copy(qt_app: QApplication) -> None:
    canvas = _cross_canvas()
    canvas.selection = [("line", (0, 1))]

    canvas.mirror_selected("y")

    assert len(canvas.sketch.elements) == 3


def test_the_modify_group_is_reachable_and_labelled(qt_app: QApplication) -> None:
    """Fusion hat eine eigene Gruppe dafür; Formwerk hatte sie gar nicht."""
    from app.ui.sketch_editor import ACTION_KEYS, TOOL_KEYS

    panel = SketchPanel()

    assert "trim" in panel._tool_buttons
    assert "extend" in panel._tool_buttons
    assert TOOL_KEYS["trim"] == "T", "wie in Fusion"
    assert ACTION_KEYS["offset"] == "O"
    assert panel.offset_distance.value() != 0.0, "ein Versatz um nichts wäre keiner"


def test_construction_geometry_is_a_toggle(qt_app: QApplication) -> None:
    """Dieselbe Linie ist mal Kontur, mal Hilfslinie — wer sich vertut, klickt
    noch einmal."""
    canvas = _cross_canvas()
    canvas.selection = [("line", (0, 1))]

    canvas.toggle_construction()
    assert canvas.sketch.elements[0].construction
    assert not canvas.sketch.elements[1].construction, "nur die Auswahl"

    canvas.toggle_construction()
    assert not canvas.sketch.elements[0].construction


def test_projecting_needs_a_body(qt_app: QApplication) -> None:
    canvas = SketchCanvas()
    said: list[str] = []
    canvas.statusChanged.connect(said.append)

    canvas.project_bodies()

    assert said and "Körper" in said[-1]


def test_projecting_brings_the_edges_in(qt_app: QApplication) -> None:
    """Bei Weg 1 ist das der Normalfall, nicht die Ausnahme."""
    import trimesh

    from app.core.geom.mesh import MeshData

    canvas = SketchCanvas()
    canvas.offer_bodies([MeshData.of(trimesh.creation.box(extents=(20.0, 10.0, 6.0)))])

    canvas.project_bodies()

    assert canvas.sketch.elements
    assert all(element.construction for element in canvas.sketch.elements)


def test_the_reference_tools_are_reachable(qt_app: QApplication) -> None:
    """Projizieren und Konstruktionsgeometrie fehlten ganz — beide waren im
    Vergleich mit Fusion eine leere Zeile."""
    from app.i18n import tr
    from app.ui.sketch_editor import ACTION_KEYS

    panel = SketchPanel()
    labels = {
        button.text().split("  ")[0]
        for button in panel.findChildren(type(panel._tool_buttons["line"]))
    }

    assert tr("Projizieren") in labels
    assert tr("Hilfsgeometrie") in labels
    assert ACTION_KEYS["construction"] == "X", "wie in Fusion"


# --- Maß beim Zeichnen und lesbare Bedingungen (E19) ----------------------------


def test_typing_a_measure_finishes_the_line(qt_app: QApplication) -> None:
    """In Fusion zeichnet man selten und bemaßt fast immer — dafür gab es
    hier gar nichts."""
    canvas = SketchCanvas()
    canvas.set_tool("line")
    canvas.place(canvas._to_screen(0.0, 0.0))
    canvas._pointer = (1.0, 0.0)

    canvas.place_measured(25.0)

    assert len(canvas.sketch.elements) == 1
    line = canvas.sketch.elements[0]
    assert line.points[1][0] == pytest.approx(25.0), "die Länge kommt aus dem Feld"
    assert line.points[1][1] == pytest.approx(0.0), "die Richtung vom Zeiger"


def test_a_typed_measure_stays_as_a_constraint(qt_app: QApplication) -> None:
    """Sonst wandert die Linie beim nächsten Solverlauf, und die eingetippte
    Zahl wäre eine Angabe gewesen, die nichts hält."""
    canvas = SketchCanvas()
    canvas.set_tool("line")
    canvas.place(canvas._to_screen(0.0, 0.0))
    canvas._pointer = (1.0, 0.0)

    canvas.place_measured(25.0)

    measures = [entry for entry in canvas.sketch.constraints if entry.kind == "distance"]
    assert measures, "das Maß bleibt stehen"
    assert float(measures[0].value) == pytest.approx(25.0)


def test_a_measure_without_a_start_says_what_to_do(qt_app: QApplication) -> None:
    canvas = SketchCanvas()
    canvas.set_tool("line")
    said: list[str] = []
    canvas.statusChanged.connect(said.append)

    canvas.place_measured(25.0)

    assert said and "Punkt setzen" in said[-1]
    assert not canvas.sketch.elements


def test_the_measure_field_only_works_while_drawing(qt_app: QApplication) -> None:
    """Ein Feld ohne Bezug ist eine Einladung zu einem Klick, der nichts
    tut."""
    panel = SketchPanel()
    assert not panel.measure_field.isEnabled()

    panel.canvas.set_tool("line")
    panel.canvas.place(panel.canvas._to_screen(0.0, 0.0))
    panel.canvas._pointer = (10.0, 0.0)
    panel.canvas.measuringChanged.emit(panel.canvas.pending_measure())

    assert panel.measure_field.isEnabled()
    assert panel.measure_field.value() == pytest.approx(10.0)


def test_hovering_a_constraint_lights_up_its_geometry(qt_app: QApplication) -> None:
    """„Deckung (1, 2)" ist ohne das nicht lesbar: welche zwei Punkte das sind,
    weiß nur, wer die flache Nummerierung im Kopf hat."""
    panel = SketchPanel()
    panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))

    item = panel.constraint_list.item(0)
    assert item is not None
    panel._point_at(item)

    assert panel.canvas.highlighted, "die Punkte der Bedingung leuchten"
    assert panel.canvas.highlighted == frozenset(panel.canvas.sketch.constraints[0].targets)

    panel._point_at(None)
    assert not panel.canvas.highlighted, "und der Zeiger daneben nimmt es zurück"


def test_the_sketch_mode_hides_the_view_tools(qt_app: QApplication) -> None:
    """Schnitt, Messen und Bemalen brauchen einen Körper und ein Bild.

    Sie standen im Skizzenmodus als zweite Leiste unter der des Editors und
    boten sieben Umschalter an, von denen keiner etwas bewirkte.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("sketch_extrude")
        assert window.tools.isHidden()

        window.finish_sketch(keep=False)
        assert not window.tools.isHidden(), "und danach sind sie wieder da"
    finally:
        window.deleteLater()


def test_finishing_a_sketch_looks_like_the_main_action(qt_app: QApplication) -> None:
    """Fusion setzt dafür einen großen Haken oben rechts; hier stand ein
    Textknopf unter den anderen und war von „Verwerfen" nicht zu
    unterscheiden."""
    from PySide6.QtWidgets import QPushButton

    from app.i18n import tr
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        buttons = {button.text(): button for button in window.sketch_bar.findChildren(QPushButton)}
        assert buttons[tr("Fertig")].isDefault()
        assert not buttons[tr("Verwerfen")].isDefault()
    finally:
        window.deleteLater()
