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

from PySide6.QtCore import QPointF, Qt
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
    _constraint_label,
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


def test_a_click_falls_on_the_grid(qt_app: QApplication) -> None:
    """Ohne Fang landete ein Klick auf -29,75 mm.

    Aus so einem Wert wird kein Maß, sondern Nacharbeit: jede Bemaßung, die
    danach kommt, korrigiert erst einmal die krumme Zahl. Der Fang ist die
    Vorgabe, weil gedruckt wird, was in Millimetern beschrieben ist.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)
    canvas.set_tool("line")

    canvas.place(canvas._to_screen(12.4, -7.7))
    canvas.place(canvas._to_screen(30.2, 5.1))

    assert canvas.sketch.elements[0].points == ((12.0, -8.0), (30.0, 5.0))


def test_the_grid_lets_go_when_the_hook_comes_off(qt_app: QApplication) -> None:
    """Wer frei zeichnen will, nimmt den Haken weg — und dann fängt nichts.

    Und mit anderer Weite fängt es anders: eine Einstellung, die nur an und
    aus kennt, wäre bei einem Teil mit halben Millimetern keine.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)

    canvas.set_snapping(False)
    assert canvas.snapped((12.4, -7.7)) == (12.4, -7.7)

    canvas.set_snapping(True, 0.5)
    assert canvas.snapped((12.4, -7.7)) == pytest.approx((12.5, -7.5))

    canvas.set_snapping(True, 10.0)
    assert canvas.snapped((12.4, -7.7)) == pytest.approx((10.0, -10.0))


def test_an_existing_point_beats_the_grid(qt_app: QApplication) -> None:
    """Ein vorhandener Punkt fängt vor dem Raster.

    Sonst risse der Fang gerade die Verbindung auf, für die er da ist: der
    Endpunkt einer Linie auf -0,25 mm rutschte auf null, und die Deckung, die
    das Element zusammenhält, käme nie zustande.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)
    canvas.add_element("line", ((0.0, 0.0), (30.25, 0.0)))

    canvas.set_tool("line")
    canvas.place(canvas._to_screen(30.3, 0.05))
    canvas.place(canvas._to_screen(30.0, 20.0))

    assert canvas.sketch.elements[1].points[0] == (30.25, 0.0), "der vorhandene Punkt, nicht 30,0"
    assert [entry.kind for entry in canvas.sketch.constraints] == ["coincident"]


def test_the_axes_say_what_they_are_on_this_plane(qt_app: QApplication) -> None:
    """Auf der stehenden Ebene ist die Senkrechte Z, nicht Y.

    Beschriftet stand dort immer „X" und „Y" — die Zeichenfläche behauptete
    eine Richtung, die es auf dieser Ebene nicht gibt. Auf einer angeklickten
    Fläche des Körpers bleibt der Buchstabe weg: sie kann beliebig geneigt
    sein, und dann wäre er geraten.
    """
    canvas = SketchCanvas()

    assert canvas.axis_names() == ("X", "Y")
    canvas.set_plane("plane:xz")
    assert canvas.axis_names() == ("X", "Z")
    canvas.set_plane("plane:yz")
    assert canvas.axis_names() == ("Y", "Z")
    canvas.set_plane("feature:face_1")
    assert canvas.axis_names() == ("", "")


def test_the_grid_follows_the_scale(qt_app: QApplication) -> None:
    """Die Rasterweite stand fest auf zehn Millimetern.

    Herausgezoomt wurde daraus eine Fläche aus Linien, hineingezoomt ein
    Blatt mit vier Linien darauf. Sie folgt jetzt dem Maßstab — und bleibt in
    der Folge 1, 2, 5, damit ein Kästchen ablesbar bleibt.
    """
    from app.ui.sketch_editor import GRID_STEPS, MIN_GRID_PX

    canvas = SketchCanvas()
    for scale in (0.5, 2.0, 4.0, 20.0, 100.0):
        canvas._scale = scale
        step = canvas.grid_step()
        assert step in GRID_STEPS
        assert step * scale >= MIN_GRID_PX or step == GRID_STEPS[-1], "Linien kleben nicht"


def test_zooming_keeps_the_point_under_the_pointer(qt_app: QApplication) -> None:
    """Das Rad zoomt auf den Zeiger, nicht auf die Bildmitte.

    Vorher blieb die Mitte stehen: wer an einer Ecke der Zeichnung arbeitete
    und heranzoomte, verlor sie aus dem Bild und musste hinterherschieben.
    """
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    canvas = SketchCanvas()
    canvas.resize(400, 400)
    spot = QPointF(340.0, 90.0)
    before = canvas._to_world(spot)

    canvas.wheelEvent(
        QWheelEvent(
            spot,
            spot,
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
    )

    assert canvas._to_world(spot) == pytest.approx(before), "derselbe Punkt liegt noch dort"


def test_a_digit_switches_the_view(qt_app: QApplication) -> None:
    """Die Ebene zu wechseln ist kein seltener Griff.

    Ein Gehäuse zeichnet man von oben, seine Aufhängung von der Seite, und
    dazwischen lag jedes Mal ein Klappmenü. Die Ziffern sind dieselben wie in
    Fusion und FreeCAD — und sie gehen über die Wahl, damit nicht zwei
    Stellen zweierlei behaupten.
    """
    from app.ui.sketch_editor import PLANE_KEYS

    panel = SketchPanel()
    try:
        panel.choose_plane("plane:xz")
        assert panel.canvas.sketch.plane == "plane:xz"
        assert panel.plane_choice.currentData() == "plane:xz", "die Wahl steht mit"

        panel.choose_plane("plane:yz")
        assert panel.canvas.axis_names() == ("Y", "Z")

        # Und die Belegung steht am Eintrag: eine Taste ohne sichtbares Ziel
        # findet niemand (§19.2, Regel 18).
        for plane, key in PLANE_KEYS.items():
            index = panel.plane_choice.findData(plane)
            assert key in panel.plane_choice.itemText(index)
    finally:
        panel.deleteLater()


def test_the_digit_really_switches_the_plane_inside_the_window(qt_app: QApplication) -> None:
    """Und zwar gedrückt, nicht gerufen.

    Der Test darüber ruft ``choose_plane`` an einem nackten ``SketchPanel`` —
    also in genau der Umgebung, in der der Fehler nicht auftritt. Im Fenster
    lagen auf denselben Ziffern die Einträge unter *Ansicht → Darstellung*,
    und Qt lässt bei zwei aktiven Kürzeln derselben Taste **keines** von beiden
    feuern: Die Taste tat nichts, weder das eine noch das andere. Die
    Zeichenfläche versprach sie sichtbar — „(1)", „(2)", „(3)" stehen am
    Ebenenfeld und noch einmal im Tooltip.

    Gemessen wird deshalb am gebauten Fenster mit offener Skizze.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.show()
        window._show_start_screen(False)
        window.start_sketch("sketch_extrude")
        qt_app.processEvents()

        panel = window._sketch_panel
        assert panel is not None, "ohne offene Skizze prüft dieser Test nichts"
        assert panel.canvas.sketch.plane == "plane:xy"

        panel.canvas.setFocus()
        QTest.keyClick(panel.canvas, Qt.Key.Key_2)
        qt_app.processEvents()
        assert panel.canvas.sketch.plane == "plane:xz", (
            "Die Taste 2 kam nicht an — liegt wieder ein Kürzel des Fensters darauf?"
        )

        QTest.keyClick(panel.canvas, Qt.Key.Key_3)
        qt_app.processEvents()
        assert panel.canvas.sketch.plane == "plane:yz"

        # Die Gegenprobe im selben Lauf: Mit wieder aktiven Menü-Kürzeln muss
        # dieselbe Taste versagen. Ohne sie stünde hier ein Test, der auch dann
        # grün bliebe, wenn es den Konflikt nie gegeben hätte.
        for action in window._display_actions:
            action.setEnabled(True)
        panel.choose_plane("plane:xy")
        QTest.keyClick(panel.canvas, Qt.Key.Key_2)
        qt_app.processEvents()
        assert panel.canvas.sketch.plane == "plane:xy", (
            "Zwei aktive Kürzel auf einer Taste, und sie feuert trotzdem — dann misst "
            "dieser Test den Konflikt nicht mehr und braucht eine andere Begründung."
        )
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_the_status_says_what_the_next_click_does(qt_app: QApplication) -> None:
    """Dass Esc den Linienzug beendet, stand nirgends.

    Nach dem zweiten Klick hängt der nächste Strich am Zeiger und läuft
    weiter — ein Werkzeug, das man nur durch Ausprobieren verlässt, ist eine
    Sackgasse mit Ausgang (§2.1).
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)

    canvas.set_tool("line")
    assert "Anfang" in canvas.status_text()

    canvas.place(canvas._to_screen(0.0, 0.0))
    assert "Esc" in canvas.status_text(), "der Ausgang steht da, solange er gebraucht wird"

    canvas.set_tool("select")
    assert "Esc" not in canvas.status_text(), "wer auswählt, zeichnet nicht"

    canvas.set_tool("arc")
    assert "Mitte" in canvas.status_text()


def test_a_bed_that_arrives_late_still_gets_fitted(qt_app: QApplication) -> None:
    """Ein leeres Blatt passt auf den Bauraum ein — auch wenn der erst nach
    dem Aufbau hereinkommt.

    Sonst stand der Maßstab auf der Vorgabe, und der Rand, der die früheste
    Warnung tragen soll (E1), lag zur Hälfte außerhalb.
    """
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.fit_view()
    before = canvas._scale

    canvas.set_bed((220.0, 220.0))
    assert canvas._scale != pytest.approx(before), "die Einpassung zieht nach"

    # Wer selbst gezoomt hat, behält seinen Ausschnitt.
    _zoom(canvas)
    own = canvas._scale
    canvas.set_bed((120.0, 120.0))
    assert canvas._scale == pytest.approx(own)


def test_the_hook_in_the_bar_reaches_the_canvas(qt_app: QApplication) -> None:
    """Haken und Weite stehen an der Ebenenzeile — beides entscheidet man vor
    dem ersten Strich."""
    panel = SketchPanel()
    try:
        assert panel.snap_toggle.isChecked(), "an ist die Vorgabe"
        assert panel.snap_step.isEnabled()

        panel.snap_step.setValue(5.0)
        assert panel.canvas.snap_step == pytest.approx(5.0)

        panel.snap_toggle.setChecked(False)
        assert not panel.canvas.snapping
        assert not panel.snap_step.isEnabled(), "eine Weite, die nichts tut, wird nicht angeboten"
    finally:
        panel.deleteLater()


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


def test_a_greyed_out_constraint_in_the_menu_says_what_it_needs(qt_app: QApplication) -> None:
    """Im Kontextmenü stand die Bedingung grau da und schwieg.

    Der Satz existiert längst — ``_needs_phrase`` liefert ihn, der Knopf trägt
    ihn im Hinweis, und wer das Kürzel ohne passende Auswahl drückt, liest ihn
    in der Statuszeile. Nur das Kontextmenü setzte ``setEnabled(False)`` und
    sonst nichts: zehn gleich aussehende Zeilen, die halbe Hälfte grau, und
    keine sagt warum.

    Dazu ``toolTipsVisible``: ``QMenu`` zeigt Hinweise von Haus aus nicht an.
    Ein Satz an einer Handlung in einem Menü, das keine Hinweise zeigt, ist
    geschrieben und ungelesen.
    """
    dialog = SketchEditorDialog(sketch_to_text(shapes.rectangle(40.0, 20.0)))
    canvas = dialog.canvas
    canvas.selection = [("line", (0, 1))]

    menu = canvas.context_menu_at(None)
    assert menu.toolTipsVisible(), "das Kontextmenü der Skizze zeigt keine Hinweise an"

    locked = [action for action in menu.actions() if not action.isEnabled() and action.text()]
    assert locked, "ohne eine gesperrte Bedingung prüft dieser Test nichts"
    for action in locked:
        assert action.toolTip(), f"{action.text()!r} ist grau und sagt nicht, warum"
        assert "auswählen" in action.toolTip(), (
            f"{action.text()!r} nennt nicht die fehlende Auswahl: {action.toolTip()!r}"
        )

    # Und was geht, trägt keinen Grund — sonst wäre der Hinweis eine Warnung
    # an jeder Zeile statt einer Auskunft an der gesperrten.
    open_ones = [action for action in menu.actions() if action.isEnabled() and action.text()]
    assert open_ones, "alles gesperrt wäre kein Menü"
    menu.deleteLater()


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


def test_a_second_click_on_the_same_point_closes_the_spline(qt_app: QApplication) -> None:
    """Der dritte Weg, einen Spline zu schließen — versprochen und nicht da.

    Der Kommentar in ``place`` nannte ihn seit je („Doppelklick, Eingabetaste
    oder ein zweiter Klick auf denselben Punkt"), und die Wirkung war eine
    andere: der Klick hängte einen weiteren, deckungsgleichen Punkt an die
    Kurve. Still, ohne Meldung, und wer den Griff aus einem CAD mitbringt,
    holte sich damit einen doppelten Punkt in seinen Spline.

    Gemessen wird in Bildschirmpunkten wie beim Fang: derselbe Klick liegt bei
    einem herausgezoomten Blatt weiter weg, aber nicht anders auf dem Schirm.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)
    canvas.set_tool("spline")

    for x, y in ((0.0, 0.0), (20.0, 0.0), (20.0, 20.0)):
        canvas.place(canvas._to_screen(x, y))
    assert not canvas.sketch.elements

    canvas.place(canvas._to_screen(20.0, 20.0))

    assert len(canvas.sketch.elements) == 1, "der Klick schließt, statt zu sammeln"
    assert len(canvas.sketch.elements[0].points) == 3, "und legt keinen vierten Punkt an"
    assert not canvas._pending_world, "nichts bleibt offen"


def test_a_click_elsewhere_keeps_the_spline_collecting(qt_app: QApplication) -> None:
    """Die Gegenprobe: nur der Klick auf denselben Punkt schließt.

    Sonst wäre aus dem einen Griff ein Spline geworden, der sich bei jedem
    dritten Klick von selbst beendet.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)
    canvas.set_tool("spline")

    for x, y in ((0.0, 0.0), (20.0, 0.0), (40.0, 10.0)):
        canvas.place(canvas._to_screen(x, y))

    assert not canvas.sketch.elements
    assert len(canvas._pending_world) == 3


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

    **Mit Einheit**, und die Erwartung hier stand vorher ohne. „50,00" ist eine
    Zahl ohne Angabe, wovon; solange alles Millimeter waren, konnte man sie sich
    denken, aber seit die Anzeigeeinheit umschaltbar ist (§19.3), ist sie eine
    Vermutung.
    """
    from app.core.types import SketchConstraint
    from app.ui.sketch_editor import measure_label

    points = [(0.0, 0.0), (30.0, 40.0)]
    reference = SketchConstraint(kind="reference", targets=(0, 1))
    assert measure_label(reference, points) == "(50,00 mm)", "drei, vier, fünf"

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


def _sized(panel: SketchPanel, qt_app: QApplication) -> SketchPanel:
    """Ein Panel mit wirklicher Größe — sonst passt es nicht ein.

    Ohne ``show`` verteilt das Layout nichts, die Zeichenfläche bleibt auf
    ihrer Mindestgröße, und ihr ``resizeEvent`` kommt nie. In der Anwendung
    wird sie immer gezeigt; hier muss man es sagen.
    """
    panel.resize(900, 560)
    panel.show()
    qt_app.processEvents()
    return panel


def _visible_span(panel: SketchPanel) -> tuple[float, float]:
    """Wie viele Millimeter die Fläche gerade zeigt, waagerecht und senkrecht."""
    canvas = panel.canvas
    left, top = canvas._to_world(canvas.rect().topLeft())
    right, bottom = canvas._to_world(canvas.rect().bottomRight())
    return (right - left, top - bottom)


def test_an_opened_sketch_is_fitted_into_the_view(qt_app: QApplication) -> None:
    """Eine geöffnete Zeichnung liegt im Bild, nicht halb daneben (E1).

    Der Maßstab startete fest auf vier Punkte je Millimeter und blieb dort:
    ``set_sketch`` rührte ihn nicht an. Eine Skizze von 300 mm lag damit zur
    Hälfte außerhalb, und wer sie öffnete, sah einen Ausschnitt und musste
    raten, wie weit er herauszoomen muss.
    """
    panel = _sized(SketchPanel(sketch_to_text(shapes.rectangle(300.0, 200.0))), qt_app)
    try:
        wide, high = _visible_span(panel)
        assert wide > 300.0, f"300 mm müssen hineinpassen, sichtbar sind {wide:.0f}"
        assert high > 200.0, f"200 mm ebenso, sichtbar sind {high:.0f}"
        # Und nicht beliebig weit heraus: eingepasst heißt auch, dass die
        # Zeichnung die Fläche füllt.
        assert wide < 3 * 300.0, "sonst ist es keine Einpassung, sondern eine Übersicht"
    finally:
        panel.deleteLater()


def test_an_empty_sheet_starts_on_the_build_volume(qt_app: QApplication) -> None:
    """Ohne Zeichnung gibt der Bauraum das Maß — dann sieht man, wohin man
    zeichnet, bevor der erste Strich sitzt.

    Der Rahmen soll die früheste Warnung tragen (E1) und lag beim Start
    außerhalb des Bildes: 220 mm bei vier Punkten je Millimeter sind das
    Vierfache der Fläche.
    """
    from app.ui.sketch_editor import Surroundings

    panel = _sized(SketchPanel("", None, None, Surroundings(bed=(220.0, 220.0))), qt_app)
    try:
        wide, high = _visible_span(panel)
        assert wide > 220.0 and high > 220.0, f"sichtbar {wide:.0f} × {high:.0f} mm"
    finally:
        panel.deleteLater()


def test_a_small_sketch_beats_the_build_volume(qt_app: QApplication) -> None:
    """Ist eine Zeichnung da, gibt sie das Maß und nicht die Platte.

    Sonst wäre jede Ansicht eine Plattenübersicht, und an einem 40er Teil
    arbeitet niemand in einem Maßstab, der 220 mm zeigt. Ragt die Zeichnung
    über den Bauraum, kommt der Rahmen von selbst mit ins Bild — dafür braucht
    es keine zweite Regel.
    """
    from app.ui.sketch_editor import Surroundings

    small = _sized(
        SketchPanel(
            sketch_to_text(shapes.rectangle(40.0, 20.0)),
            None,
            None,
            Surroundings(bed=(220.0, 220.0)),
        ),
        qt_app,
    )
    try:
        wide, _high = _visible_span(small)
        assert wide < 220.0, f"die Zeichnung gibt das Maß, sichtbar sind {wide:.0f} mm"
        assert wide > 40.0, "und sie passt hinein"
    finally:
        small.deleteLater()


def _zoom(canvas: SketchCanvas) -> None:
    """Einen Mausradschritt auslösen — den Weg, den die Hand nimmt."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    canvas.wheelEvent(
        QWheelEvent(
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
    )


def test_fitting_comes_back_after_zooming_away(qt_app: QApplication) -> None:
    """Der Knopf holt zurück, wer sich verzoomt hat — mit Kürzel am Werkzeug.

    Eine Belegung ohne sichtbares Ziel findet niemand, deshalb steht sie im
    Hinweistext des Knopfes (§19.2, Regel 18).
    """
    from PySide6.QtGui import QKeySequence, QShortcut

    from app.ui.sketch_editor import VIEW_KEYS

    panel = _sized(SketchPanel(sketch_to_text(shapes.rectangle(40.0, 20.0))), qt_app)
    try:
        fitted = panel.canvas._scale
        _zoom(panel.canvas)
        assert panel.canvas._scale != pytest.approx(fitted)

        panel.canvas.fit_view()
        assert panel.canvas._scale == pytest.approx(fitted)

        keys = [entry.key().toString() for entry in panel.findChildren(QShortcut)]
        assert QKeySequence(VIEW_KEYS["fit"]).toString() in keys
    finally:
        panel.deleteLater()


def test_the_view_belongs_to_whoever_zoomed_it(qt_app: QApplication) -> None:
    """Nach eigenem Zoom bleibt der Maßstab, auch wenn sich die Größe ändert.

    Die Einpassung hängt an der Fläche und nicht an einem einmaligen Moment:
    das Layout verteilt in mehreren Durchgängen, und der erste bringt oft die
    Mindestgröße — einmalig eingepasst stand der Maßstab danach auf der Größe
    von vorher. Sie mitzuziehen heißt aber auch, sie loszulassen, sobald
    jemand selbst am Rad dreht.
    """
    panel = _sized(SketchPanel("", None, None, None), qt_app)
    try:
        panel.canvas.set_sketch(sketch_from_text(sketch_to_text(shapes.rectangle(40.0, 20.0))))
        panel.canvas.fit_view()
        followed = panel.canvas._scale

        panel.resize(1200, 700)
        qt_app.processEvents()
        assert panel.canvas._scale != pytest.approx(followed), "eingepasst zieht mit"

        own = panel.canvas._scale
        _zoom(panel.canvas)
        mine = panel.canvas._scale
        panel.resize(900, 560)
        qt_app.processEvents()
        assert panel.canvas._scale == pytest.approx(mine), "eigener Zoom bleibt"
        assert mine != pytest.approx(own)
    finally:
        panel.deleteLater()


def test_a_single_point_does_not_zoom_to_infinity(qt_app: QApplication) -> None:
    """Ein Punkt hat keine Ausdehnung, und der Maßstab bleibt endlich.

    Dasselbe gilt für eine waagerechte Linie: in einer Richtung ist ihre
    Ausdehnung null, und ohne Untergrenze wäre der Quotient unendlich.
    """
    from app.core.types import Sketch, SketchElement
    from app.ui.sketch_editor import MAX_SCALE

    for element in (
        SketchElement(kind="point", points=((5.0, 5.0),)),
        SketchElement(kind="line", points=((0.0, 0.0), (30.0, 0.0))),
    ):
        panel = _sized(SketchPanel(), qt_app)
        try:
            panel.canvas.set_sketch(Sketch(plane="plane:xy", elements=(element,)))
            panel.canvas.fit_view()
            assert 0.0 < panel.canvas._scale <= MAX_SCALE
            wide, high = _visible_span(panel)
            assert wide > 0.0 and high > 0.0
        finally:
            panel.deleteLater()


def test_a_measure_is_shown_rounded_but_stored_exactly(qt_app: QApplication) -> None:
    """§11.2: gerundet wird in der Anzeige, nie im Wert.

    Grundformen schreiben neun Nachkommastellen, damit kein ``1e-05`` in einem
    Ausdruck landet. An der Bemaßung stand damit ``40.000000000``.
    """
    from app.ui.sketch_editor import readable_measure

    # Gelesen wird der gespeicherte Wert — der trägt einen Punkt, weil er eine
    # Zahl ist. Geschrieben wird in der Schreibweise der Anzeigesprache, und mit
    # Einheit: ohne sie stand in der Bedingungsliste „Abstand 30,00".
    assert readable_measure("40.000000000") == "40,00 mm"
    assert readable_measure("12.345000000") == "12,35 mm"
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
    und Grün; Solidon zeichnete beide in der Rasterfarbe.

    Wo der Nullpunkt liegt, musste man aus der Zeichnung erschließen. Die
    Buchstaben stehen daneben, weil Farbe nie allein trägt (Regel 18).
    """
    from app.ui.palette import ROLES

    assert ROLES["axis_x"] != ROLES["axis_y"]
    assert ROLES["axis_x"] not in (ROLES["axis_y"], ROLES["select"])


def test_every_drawing_tool_wears_its_key(qt_app: QApplication) -> None:
    """Jedes Zeichenwerkzeug nennt sein Kürzel — im Tooltip, samt Klartext.

    Vierzehn beschriftete Knöpfe passten nicht in die Zeile: Qt kürzte sie auf
    „Tri… T" und „Ver…ern", und ein abgeschnittenes Wort ist schlechter zu
    lesen als ein Bild. Seitdem tragen sie nur das Zeichen.

    §19.2 steht dem nicht entgegen: er verlangt ein eindeutiges Kürzel je
    Operation und die Befehlspalette als Universalzugang, nicht ein Wort neben
    dem Knopf. Beides gilt weiter — hier wird geprüft, dass das Kürzel
    dennoch am Werkzeug selbst ablesbar bleibt.
    """
    from app.ui.sketch_editor import TOOL_KEYS

    panel = SketchPanel()
    for name, key in TOOL_KEYS.items():
        button = panel._tool_buttons[name]
        assert key in button.toolTip(), f"{name} nennt sein Kürzel nicht"
        assert not button.icon().isNull(), f"{name} hat kein Zeichen"


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
    """Fusion hat eine eigene Gruppe dafür; Solidon hatte sie gar nicht."""
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
    # Seit die Leiste Zeichen statt Wörter trägt, steht der Klartext im
    # Tooltip. Erreichbar heißt weiterhin: benannt und anklickbar.
    hinweise = " | ".join(
        button.toolTip() for button in panel.findChildren(type(panel._tool_buttons["line"]))
    )

    assert tr("Projizieren") in hinweise
    assert tr("Hilfsgeometrie") in hinweise
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
    """Ein Feld ohne Bezug ist eine Einladung zu einem Klick, der nichts tut.

    Seit Schritt zwei steht es an der Zeichenfläche statt in der Werkzeugzeile,
    und „bedienbar" heißt dort „sichtbar": Ein schwebendes Feld, das grau über
    dem Blatt hinge, wäre ein Fleck ohne Aufgabe — anders als in einer Leiste,
    wo eine leere Stelle auffiele.
    """
    panel = SketchPanel()
    field = panel.canvas.measure_field
    assert not field.isVisibleTo(panel.canvas)

    panel.canvas.set_tool("line")
    panel.canvas.place(panel.canvas._to_screen(0.0, 0.0))
    panel.canvas._pointer = (10.0, 0.0)
    panel.canvas.measuringChanged.emit(panel.canvas.pending_measure())

    assert field.isVisibleTo(panel.canvas)
    assert field.value_mm() == pytest.approx(10.0)


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


# --- Was ein Neuling braucht: sagen, was fehlt, und Zahlen zulassen -------------


def test_a_constraint_that_does_not_fit_says_what_to_select(qt_app: QApplication) -> None:
    """„D" ohne passende Auswahl tat gar nichts — kein Ton, keine Zeile.

    Ein Weg, der gerade nicht geht, nennt seine Bedingung (Regel 17). Stumm
    zurückzukehren ist die schlechtere Hälfte von „fehlgeschlagen": es sagt
    nicht einmal, dass etwas nicht ging.
    """
    panel = SketchPanel()
    said: list[str] = []
    panel.canvas.statusChanged.connect(said.append)

    panel.request_constraint("distance")

    assert said, "der Versuch bleibt nicht stumm"
    assert "zwei Punkte" in said[-1], "und er nennt die Auswahl, die fehlt"
    assert not panel.canvas.sketch.constraints


def test_every_constraint_knows_what_it_needs(qt_app: QApplication) -> None:
    """Zu jeder Bedingung gehört ein Halbsatz — sonst bliebe ein Knopf grau
    ohne Grund."""
    from app.ui.sketch_editor import _NEEDS, _needs_phrase

    for kind in _NEEDS:
        assert _needs_phrase(kind), kind


def test_the_constraint_buttons_start_locked(qt_app: QApplication) -> None:
    """Beim Öffnen ist nichts ausgewählt, also passt keine Bedingung.

    Sie standen alle zehn bedienbar da: ``_refresh_buttons`` hing allein am
    Auswahlsignal, und das kam vor dem ersten Klick nie.
    """
    panel = SketchPanel()

    assert not any(button.isEnabled() for button in panel._constraint_buttons.values())
    for kind, button in panel._constraint_buttons.items():
        assert _constraint_label(kind) in button.toolTip()
        assert "auswählen" in button.toolTip(), "der Hinweis nennt die nötige Auswahl"


def test_an_opened_sketch_shows_its_constraints(qt_app: QApplication) -> None:
    """Eine geöffnete Skizze zeigte rechts eine leere Liste.

    Die Skizze wird im Konstruktor gesetzt, also **vor** den Verbindungen —
    das Signal lief ins Leere, und die Liste füllte sich erst bei der nächsten
    Änderung. Wer seine Bedingungen nicht sieht, setzt sie ein zweites Mal.
    """
    panel = SketchPanel(sketch_to_text(shapes.rectangle(40.0, 20.0)))

    assert panel.canvas.sketch.constraints, "die Vorlage bringt welche mit"
    assert panel.constraint_list.count() == len(panel.canvas.sketch.constraints)


def test_the_measure_starts_at_what_is_already_there(qt_app: QApplication) -> None:
    """Das Maßfeld stand leer — wer 30 mm setzen wollte, musste die Zahl
    kennen, die er gerade selbst gezeichnet hatte."""
    from app.ui.sketch_editor import measured_expression

    assert measured_expression([(0.0, 0.0), (30.0, 0.0)], (0, 1)) == "30"
    assert measured_expression([(0.0, 0.0), (0.0, 12.5)], (0, 1)) == "12.5"
    assert "," not in measured_expression([(0.0, 0.0), (7.25, 0.0)], (0, 1)), (
        "ein Ausdruck der Grammatik, keine Beschriftung"
    )
    assert measured_expression([(0.0, 0.0)], (0, 1)) == "", "ohne zweiten Punkt kein Maß"


def test_the_pointer_position_reaches_the_bar(qt_app: QApplication) -> None:
    """Wo der Zeiger steht, stand nirgends — und ohne das ist ein gezogener
    Punkt eine ungefähre Lage."""
    panel = SketchPanel()
    panel.canvas.set_tool("line")
    panel.canvas._pointer = (12.0, 8.0)

    panel.canvas.pointerChanged.emit(*panel.canvas.pointer_target())

    shown = panel.coordinates.text()
    assert "12" in shown and "8" in shown
    assert "X" in shown and "Y" in shown, "mit den Achsen dieser Ebene"


def test_the_shown_position_is_where_the_click_lands(qt_app: QApplication) -> None:
    """Gefangen wird auf die Rasterweite — eine Anzeige, die 29,75 zeigt, wo
    30 entsteht, wäre schlechter als keine."""
    canvas = SketchCanvas()
    canvas.set_tool("line")
    canvas.set_snapping(True, 1.0)
    canvas._pointer = (29.75, 0.4)

    assert canvas.pointer_target() == pytest.approx((30.0, 0.0))

    canvas.set_tool("select")
    assert canvas.pointer_target() == pytest.approx((29.75, 0.4)), "beim Auswählen ungefangen"


def test_a_point_can_be_set_by_number(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ziehen ist der schnelle Weg; wo es auf den Zehntel ankommt, ist Zielen
    mit der Maus der falsche Griff. Den Weg gab es gar nicht."""
    from app.ui import sketch_editor

    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (10.0, 0.0)))

    class Stub:
        DialogCode = sketch_editor.PointDialog.DialogCode

        def __init__(
            self, point: tuple[float, float], axes: tuple[str, str], parent: object
        ) -> None:
            self.start = point

        def exec(self) -> object:
            return sketch_editor.PointDialog.DialogCode.Accepted

        def point(self) -> tuple[float, float]:
            return (25.0, 4.5)

    monkeypatch.setattr(sketch_editor, "PointDialog", Stub)
    canvas.edit_point(1)

    assert canvas.points()[1] == pytest.approx((25.0, 4.5))

    canvas.undo()
    assert canvas.points()[1] == pytest.approx((10.0, 0.0)), "und ein Rückgängig nimmt es zurück"


def test_the_point_dialog_starts_where_the_point_is(qt_app: QApplication) -> None:
    """Der Dialog fragt nicht, wohin es gehen soll — er zeigt, wo es ist."""
    from app.ui.sketch_editor import PointDialog

    dialog = PointDialog((12.0, -3.5), ("X", "Y"))

    assert dialog.point() == pytest.approx((12.0, -3.5))


def test_an_untouched_field_gives_the_exact_number_back(qt_app: QApplication) -> None:
    """Ansehen ist keine Änderung (Regel 6).

    Das Feld zeigt zwei Dezimalstellen, weil die Anzeige das überall tut — der
    Kern rechnet weiter genau. Ohne diese Trennung verschob der Dialog den
    Punkt allein dadurch, dass man ihn öffnete und mit OK schloss: Ein
    projizierter Punkt bei 30,125 mm kam als 30,13 zurück, einer bei 0,001 mm
    als 0. Gemessen an der Klasse selbst, nicht an einer Attrappe.

    Der Merker hängt am Signal und nicht an einem Zahlenvergleich: Qt rundet
    beim Vorbelegen 30,125 auf 30,13 und Python auf 30,12, und ein Vergleich
    gegen die eigene Rundung hielte genau diesen Fall für eine Eingabe.
    """
    from app.ui.sketch_editor import PointDialog

    for exact in (30.125, 12.3456, 0.001, -7.0049):
        dialog = PointDialog((exact, exact), ("X", "Y"))

        assert dialog.point() == (exact, exact), f"{exact} kam gerundet zurück"


def test_a_typed_number_wins_and_the_other_field_stays(qt_app: QApplication) -> None:
    """Wer eine Zahl eintippt, meint sie — und nur sie.

    Der Docstring der Klasse verspricht genau das: „Wer nur die Waagerechte
    genau braucht, tippt eine Zahl und lässt die andere stehen."
    """
    from app.ui.sketch_editor import PointDialog

    dialog = PointDialog((30.125, 0.001), ("X", "Y"))
    dialog._across.setValue(42.5)

    assert dialog.point() == (42.5, 0.001), "das unangetastete Feld hat sich mitverändert"


def test_one_selected_says_how_the_second_comes_along(qt_app: QApplication) -> None:
    """Dass Strg mehrere wählt, stand nirgends.

    Ein Maß zwischen zwei Punkten braucht beide ausgewählt; wer den zweiten
    anklickt, verliert den ersten, und der Knopf bleibt grau. Die Zeile nennt
    die Taste genau dann, wenn sie gebraucht wird.
    """
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    said: list[str] = []
    canvas.statusChanged.connect(said.append)

    canvas._select(("point", (0,)), False)
    assert "Strg" in said[-1], "beim ersten Klick steht die Taste da"

    canvas._select(("point", (1,)), True)
    assert "Strg" not in said[-1], "beim zweiten nicht mehr"
    assert "2" in said[-1]


def test_without_a_selection_the_line_belongs_to_the_degrees_of_freedom(
    qt_app: QApplication,
) -> None:
    """Der Hinweis verdrängt die Freiheitsgrade nur, solange er etwas sagt."""
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))

    assert not canvas.selection_hint()
    assert "Freiheitsgrade" in canvas.status_text()


# --- Punkte setzen und danach greifen (der Weg, an dem es scheiterte) ----------


def test_a_click_on_a_point_grabs_it(qt_app: QApplication) -> None:
    """Wer drei Punkte gesetzt hat und den mittleren anklickt, um ihn zu
    ziehen, bekam einen vierten genau darauf.

    Deckungsgleich, unsichtbar, mit Bedingung — und ausgewählt war nichts. Man
    klickt, sieht nichts, klickt wieder und stapelt. Ein Klick auf einen Punkt
    greift ihn jetzt, gleich welches der beiden Werkzeuge läuft.
    """
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.set_tool("point")
    for x, y in ((0.0, 0.0), (20.0, 0.0), (20.0, 15.0)):
        canvas.place(canvas._to_screen(x, y))

    canvas.place(canvas._to_screen(20.0, 0.0))

    assert len(canvas.sketch.elements) == 3, "kein vierter Punkt"
    assert not canvas.sketch.constraints, "und keine Deckung auf sich selbst"
    assert canvas.selection == [("point", (1,))], "der getroffene Punkt ist ausgewählt"
    assert canvas._dragging == 1, "und er hängt schon am Zeiger"


def test_ctrl_takes_the_second_point_along_with_the_point_tool(qt_app: QApplication) -> None:
    """Strg gilt auf demselben Weg, den die Maus nimmt.

    Der Griff stand einmal im Mausereignis und einmal in ``place``; das erste
    reichte Strg weiter, das zweite nicht — und weil das Ereignis zuerst kam,
    prüften alle Greif-Tests den Weg, den die Maus nie nahm. Jetzt greift
    ``place`` allein, und dieser Test hält fest, dass die Taste dort ankommt:
    ein Maß zwischen zwei Punkten braucht beide ausgewählt.
    """
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.set_tool("point")
    canvas.place(canvas._to_screen(0.0, 0.0))
    canvas.place(canvas._to_screen(20.0, 0.0))

    canvas.place(canvas._to_screen(0.0, 0.0))
    canvas.place(canvas._to_screen(20.0, 0.0), extend=True)

    assert canvas.selection == [("point", (0,)), ("point", (1,))], "Strg nimmt dazu"
    assert len(canvas.sketch.elements) == 2, "und setzt dabei keinen neuen Punkt"


def test_the_snap_mark_gives_way_where_a_point_lights_up(qt_app: QApplication) -> None:
    """Zwei Zeichen an zwei Stellen behaupten zwei Ziele.

    Beim Punktwerkzeug greift ein Klick den vorhandenen Punkt. Stand die
    Fangmarke daneben auf dem Rasterpunkt, zeigte sie eine Stelle, die der
    Klick nicht nimmt — also weicht sie, wo ein Punkt aufleuchtet.
    """
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.set_tool("point")
    canvas.place(canvas._to_screen(20.0, 0.0))

    # Neben dem Punkt: Marke ja, kein Aufleuchten.
    canvas._pointer = (40.0, 30.0)
    neben = canvas._hit_point(canvas._to_screen(40.0, 30.0))
    canvas._note_hover(neben)
    canvas._note_snap_mark(over_point=neben is not None)
    assert neben is None, "vierzig Millimeter daneben trifft keinen Punkt"
    assert not canvas.highlighted
    assert canvas._snap_mark is not None, "ohne Treffer gehört die Marke ins Bild"

    # Auf dem Punkt: Aufleuchten ja, keine Marke.
    canvas._pointer = (20.0, 0.0)
    darauf = canvas._hit_point(canvas._to_screen(20.0, 0.0))
    canvas._note_hover(darauf)
    canvas._note_snap_mark(over_point=darauf is not None)
    assert darauf == 0, "der Klick trifft den gesetzten Punkt"
    assert canvas.highlighted, "der getroffene Punkt leuchtet auch beim Punktwerkzeug"
    assert canvas._snap_mark is None, "und die Fangmarke weicht ihm"


def test_the_grabbed_point_moves_and_comes_back(qt_app: QApplication) -> None:
    """Greifen und ziehen ist ein Schritt — und einer, den ein Undo nimmt."""
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.set_tool("point")
    canvas.place(canvas._to_screen(20.0, 0.0))

    canvas.place(canvas._to_screen(20.0, 0.0))
    canvas.move_point(0, 26.0, 4.0)
    assert canvas.points()[0] == pytest.approx((26.0, 4.0))

    canvas.undo()
    assert canvas.points()[0] == pytest.approx((20.0, 0.0))


def test_drawing_goes_on_next_to_the_grabbed_point(qt_app: QApplication) -> None:
    """Das Werkzeug bleibt, was es ist: daneben entsteht weiter ein Punkt."""
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.set_tool("point")
    canvas.place(canvas._to_screen(20.0, 0.0))
    canvas.place(canvas._to_screen(20.0, 0.0))

    canvas.place(canvas._to_screen(40.0, 30.0))

    assert len(canvas.sketch.elements) == 2
    assert canvas.points()[1] == pytest.approx((40.0, 30.0))


def test_the_line_says_what_is_selected_with_the_point_tool(qt_app: QApplication) -> None:
    """Sonst stünde dort weiter „jeder Klick setzt einen", während der eben
    gegriffene Punkt dick im Bild liegt."""
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.set_tool("point")
    canvas.place(canvas._to_screen(20.0, 0.0))
    assert "jeder Klick" in canvas.status_text()

    canvas.place(canvas._to_screen(20.0, 0.0))

    assert "ausgewählt" in canvas.status_text()


def test_the_snap_still_joins_a_line_to_a_point(qt_app: QApplication) -> None:
    """Nur das Punktwerkzeug lässt es bleiben — bei Linie, Kreis und Bogen ist
    derselbe Fang die Verbindung, für die er da ist."""
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.set_tool("point")
    canvas.place(canvas._to_screen(0.0, 0.0))

    canvas.set_tool("line")
    canvas.place(canvas._to_screen(0.05, 0.0))
    canvas.place(canvas._to_screen(30.0, 0.0))

    assert [entry.kind for entry in canvas.sketch.constraints] == ["coincident"]


def test_the_pointer_says_whether_it_draws_or_selects(qt_app: QApplication) -> None:
    """Auf der Zeichenfläche stand der Pfeil, gleich ob ein Werkzeug lief.

    Ein Zustand, den man nur am gedrückten Knopf sieht, ist bei Symbolgröße
    keiner, den jemand bemerkt.
    """
    from PySide6.QtCore import Qt as QtCore

    canvas = SketchCanvas()

    canvas.set_tool("point")
    assert canvas.cursor().shape() == QtCore.CursorShape.CrossCursor
    canvas.set_tool("line")
    assert canvas.cursor().shape() == QtCore.CursorShape.CrossCursor

    canvas.set_tool("select")
    assert canvas.cursor().shape() != QtCore.CursorShape.CrossCursor


def test_the_point_under_the_pointer_lights_up(qt_app: QApplication) -> None:
    """Ohne das ist nicht zu sehen, ob ein Klick den Punkt trifft oder
    danebengeht.

    Gesucht wird im Mausereignis, einmal je Bewegung — die Fangmarke braucht
    dasselbe Ergebnis. Hier steht deshalb dieselbe Kette wie dort: erst
    ``_hit_point``, dann der Merker.
    """
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.add_element("point", ((20.0, 0.0),))
    canvas.set_tool("select")

    assert canvas._note_hover(canvas._hit_point(canvas._to_screen(20.0, 0.0)))
    assert canvas.highlighted == frozenset({0})

    assert canvas._note_hover(canvas._hit_point(canvas._to_screen(60.0, 60.0)))
    assert not canvas.highlighted, "daneben leuchtet nichts"


def test_nothing_lights_up_while_drawing(qt_app: QApplication) -> None:
    """Beim Zeichnen leuchtet die Fangmarke — zwei Zeichen an derselben Stelle
    sind eines zu viel.

    Das Werkzeug entscheidet, ob überhaupt gesucht wird: bei ``line`` sucht das
    Mausereignis keinen Treffer, also kommt hier ``None`` an.
    """
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.add_element("point", ((20.0, 0.0),))
    canvas.set_tool("line")

    canvas._note_hover(None)

    assert not canvas.highlighted


def test_a_conflict_says_which_two_constraints(qt_app: QApplication) -> None:
    """„Zwei Bedingungen widersprechen sich" — bei vierzehn in der Liste.

    Der Kern nennt das Paar seit jeher (``error.first``/``error.second``) und
    bietet sogar an, die eine oder die andere zu entfernen. Im Fenster stand
    davon nichts: Wer den Satz las, durfte suchen, welche zwei gemeint sind.
    Die Zeichenfläche merkt sich das Paar jetzt, und die Liste rechts schreibt
    beide an — mit einem Zeichen und nicht nur mit Farbe (Regel 18).
    """
    from app.ui.sketch_editor import CONFLICT_MARKER, SketchPanel

    panel = SketchPanel()
    try:
        canvas = panel.canvas
        canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
        canvas.add_constraint("fixed", (0,))
        canvas.add_constraint("distance", (0, 1), "30")
        canvas.add_constraint("distance", (0, 1), "40")

        assert canvas.conflict, "ohne Konflikt prüft dieser Test nichts"
        assert canvas.conflict_pair is not None, "das Paar wird nicht gemerkt"
        erste, zweite = canvas.conflict_pair
        assert erste != zweite

        markiert = [
            row
            for row in range(panel.constraint_list.count())
            if panel.constraint_list.item(row).text().startswith(CONFLICT_MARKER)
        ]
        assert set(markiert) == {erste, zweite}, (
            f"markiert sind {markiert}, gemeint sind {sorted(canvas.conflict_pair)}"
        )

        canvas.remove_constraint(zweite)
        assert canvas.conflict_pair is None, "geheilt, und die Markierung geht mit"
        assert not any(
            panel.constraint_list.item(row).text().startswith(CONFLICT_MARKER)
            for row in range(panel.constraint_list.count())
        )
    finally:
        panel.deleteLater()


def test_escape_has_exactly_one_owner_in_the_sketch_mode(qt_app: QApplication) -> None:
    """Escape war im Skizzenmodus tot — und ein Test sah es nicht.

    Zwei Kürzel lagen auf derselben Taste: das Fenster verlässt damit die
    Skizze, der Editor wählte damit das Auswahlwerkzeug. Qt entscheidet die
    Mehrdeutigkeit, bevor irgendein Code von uns läuft — es meldet
    ``activatedAmbiguously`` und führt **keines** von beiden aus. Gemessen im
    offenen Skizzenmodus: null Ausführungen, die Skizze blieb stehen, und das
    ist die Taste, nach der jeder als Erstes greift.

    Der Test daneben rief ``window._escape()`` direkt und war deshalb grün: Er
    prüfte den Handler, nicht die Belegung. Geprüft wird hier die Ursache —
    **ein** Besitzer der Taste —, denn sie ist unabhängig davon, welches Fenster
    ein Testlauf gerade für das aktive hält.

    Dazu die zwei Stufen: Wer eine Linie zieht, meint mit Escape das Werkzeug;
    wer nur schaut, meint die Skizze.
    """
    from PySide6.QtGui import QShortcut

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.show()
        window.start_sketch("sketch_extrude")
        panel = window._sketch_panel
        assert panel is not None

        owners = [
            shortcut
            for shortcut in window.findChildren(QShortcut)
            if shortcut.key().toString() == "Esc" and shortcut.isEnabled()
        ]
        assert len(owners) == 1, (
            f"{len(owners)} Kürzel auf Escape — Qt führt dann keines aus: "
            f"{[type(entry.parent()).__name__ for entry in owners]}"
        )

        panel.choose_tool("line")
        assert panel.canvas.tool == "line"

        window._escape()
        assert panel.canvas.tool == "select", "Escape legt zuerst das Werkzeug ab"
        assert window.sketching(), "und wirft die Zeichnung nicht gleich mit weg"

        window._escape()
        assert not window.sketching(), "beim zweiten Mal verlässt es die Skizze"
    finally:
        window.deleteLater()


def test_the_constraint_list_says_what_a_constraint_holds(qt_app: QApplication) -> None:
    """Die Liste zeigte die rohen Punktindizes.

    „Deckung  (1, 2)" ist die flache Nummerierung der Skizze — Elemente der
    Reihe nach, Punkte je Element der Reihe nach. Lesbar ist sie für niemanden,
    der sie nicht im Kopf hat; das Aufleuchten beim Überfahren (E19) half nur
    dem, der die Maus schon dort hatte, und ausgedruckt half es gar nicht.

    Liegen alle Ziele auf einem Element, steht es einmal da: „Waagerecht —
    Linie 1", nicht „Linie 1 Anfang, Linie 1 Ende". Die Zahlen bleiben im
    Tooltip, denn wer eine Bedingung aus einer Solvermeldung sucht, sucht nach
    ihnen.
    """
    from app.core.types import Sketch, SketchConstraint, SketchElement
    from app.ui.sketch_editor import point_names, targets_phrase

    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (30.0, 0.0))),
            SketchElement(kind="line", points=((30.0, 0.0), (30.0, 20.0))),
            SketchElement(kind="circle", points=((10.0, 10.0), (14.0, 10.0))),
            SketchElement(kind="arc", points=((0.0, 20.0), (5.0, 20.0), (0.0, 25.0))),
        ),
    )

    assert point_names(sketch)[:4] == (
        "Linie 1 Anfang",
        "Linie 1 Ende",
        "Linie 2 Anfang",
        "Linie 2 Ende",
    )
    assert point_names(sketch)[4:6] == ("Kreis 1 Mitte", "Kreis 1 Rand")
    assert point_names(sketch)[6:] == ("Bogen 1 Mitte", "Bogen 1 Anfang", "Bogen 1 Ende")

    assert targets_phrase(sketch, (1, 2)) == "Linie 1 Ende, Linie 2 Anfang"
    assert targets_phrase(sketch, (0, 1)) == "Linie 1", "ein ganzes Element wird einmal genannt"
    assert targets_phrase(sketch, (6, 8)) == "Bogen 1 Mitte, Bogen 1 Ende"
    assert targets_phrase(sketch, (99,)) == "", "ein Index, den es nicht gibt, wird nicht geraten"

    panel = SketchPanel(sketch_to_text(shapes.rectangle(40.0, 20.0)))
    try:
        panel.canvas.set_sketch(
            Sketch(
                plane="plane:xy",
                elements=sketch.elements,
                constraints=(SketchConstraint(kind="coincident", targets=(1, 2)),),
            )
        )
        panel._refresh_constraints()
        item = panel.constraint_list.item(0)
        assert item is not None
        assert "Linie 1 Ende" in item.text(), f"die Liste sagt es nicht: {item.text()!r}"
        assert "(1, 2)" not in item.text(), "die rohen Nummern stehen weiter im Eintrag"
        assert "(1, 2)" in item.toolTip(), "und im Tooltip sind sie weg"
    finally:
        panel.deleteLater()


def test_the_constraint_buttons_stay_readable_on_a_laptop(qt_app: QApplication) -> None:
    """Zehn beschriftete Knöpfe in einer Zeile passen auf keinen Laptopschirm.

    Gemessen an Qts eigener Rechnung, im Fenster bei 1366 Bildpunkten Breite:
    jeder der zehn Bedingungsknöpfe bekam **71** von den 146, die „Abstand  D"
    braucht; bei 1024 noch 36. Abgeschnitten war die Beschriftung damit überall
    außer auf einem sehr breiten Schirm — und zwar an der Stelle, an der jemand
    ohne CAD-Erfahrung *lernen* soll, was eine Bedingung ist. Dieselbe Sorte
    Fehler wie „etzt trenne" auf dem Hauptknopf des Trennwerkzeugs, nur
    zehnmal.

    Zwei Zeilen à fünf brauchen 790 statt 1332 Bildpunkte; dazu ist das
    Ebenenfeld nicht mehr so breit wie sein längster Eintrag (612 Bildpunkte)
    und die beiden Zahlenfelder der Werkzeugzeile nicht mehr 199 breit für
    „2,00 mm". Die Mindestbreite des ganzen Bereichs fiel damit von 1316 auf
    812 Bildpunkte.

    **Der Test setzt sein Thema selbst, und das ist die halbe Prüfung.** Ohne
    Stylesheet fehlt die Polsterung, die ein Kunde sieht: Gemessen sind die
    Knöpfe der Bedingungszeile mit Thema 37 statt 28 Bildpunkte breit. Lief
    diese Datei allein, stand kein Thema, und der Test war grün, ohne die Lage
    des Kunden zu messen — lief ``test_ui.py`` davor, war er es nicht mehr. Ein
    Test, dessen Ergebnis von seinen Nachbarn abhängt, misst nichts.

    Gemessen wird die **Bedingungszeile** und nicht der ganze Bereich, denn das
    ist sein Thema — und der Bereich war es nie: Ihr Kasten trägt
    ``setMinimumWidth(1)``, sie kann also beliebig schmal werden. Die 1007
    Bildpunkte des Bereichs kommen aus der Werkzeugzeile: fünfzehn Knöpfe à 37
    plus zwei Zahlenfelder à 163 in *einer* Reihe. Das ist ein eigener Fund,
    steht als eigener Punkt in der Roadmap, und hier zu prüfen hieße zwei
    Sachen in einer Prüfung zu vermischen.
    """
    from app.ui.style import stylesheet

    davor = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("light", 10))
    panel = SketchPanel()
    try:
        breite = panel._constraints_row.minimumSize().width()
        assert breite <= 900, f"die Bedingungszeile verlangt {breite} Bildpunkte Breite"
        for width in (1600, 1366, 1280, 1152):
            panel.resize(width, 700)
            panel.show()
            qt_app.processEvents()
            assert len(panel._constraint_buttons) > 3, (
                f"nur {len(panel._constraint_buttons)} Bedingungsknöpfe — "
                "dann sagt die Breitenprüfung darunter nichts"
            )
            squeezed = [
                f"{button.text()!r}: {button.width()} statt {button.sizeHint().width()}"
                for button in panel._constraint_buttons.values()
                if button.width() < button.sizeHint().width()
            ]
            assert not squeezed, f"bei {width} Bildpunkten Fensterbreite: " + ", ".join(squeezed)
    finally:
        panel.deleteLater()
        qt_app.setStyleSheet(davor)


def test_every_number_field_of_the_sketch_bar_says_what_it_is(qt_app: QApplication) -> None:
    """Drei Zahlenfelder standen unbeschriftet in der Leiste.

    „2,00 mm", „0,00 mm", „1,00 mm" — dazu ein Hinweis, den nur sieht, wer mit
    der Maus darüber fährt, und ein Vorleser sagte „Drehfeld, 2,00 mm". Der
    Name gehört ans Feld, und er ist der des Werkzeugs, zu dem es gehört.

    Das Maß steht seit Schritt zwei nicht mehr in der Leiste, sondern an der
    Zeichenfläche — geprüft wird es hier weiter, denn ein schwebendes Feld
    braucht seinen Namen genauso: Ein Vorleser findet es sogar eher, weil es
    nur dann da ist, wenn es etwas sagt.
    """
    panel = SketchPanel()
    try:
        felder = {
            "Versatz": panel.offset_distance,
            "Maß": panel.canvas.measure_field,
            "Raster": panel.snap_step,
        }
        ohne = [name for name, field in felder.items() if not field.accessibleName()]
        assert not ohne, f"ohne Namen: {ohne}"
        for name, field in felder.items():
            assert field.toolTip(), f"{name} ohne Hinweis"
            assert field.maximumWidth() <= 200, f"{name} ist {field.maximumWidth()} breit"
    finally:
        panel.deleteLater()


def test_home_has_exactly_one_owner_in_the_sketch_mode(qt_app: QApplication) -> None:
    """Pos1 war im Skizzenmodus tot — derselbe Fall wie Escape.

    Die Zeichenfläche hat die Taste für ihr Einpassen (``VIEW_KEYS['fit']``),
    das Fenster hat sie fensterweit für „Alles einpassen". Zwei aktive Kürzel
    auf einer Taste lassen Qt **keines** von beiden ausführen: gemessen sechs
    Drücke mit Fokus auf dem Blatt, null Aufrufe von ``fit_view``, zwei
    ``activatedAmbiguously``.

    Versprochen wird die Taste zweimal — im Tooltip des Einpassen-Knopfes und im
    Handbuch („*Einpassen* (`Pos1`) holt alles zurück ins Bild"). Wer sich
    verzoomt hat und die genannte Taste drückt, blieb verzoomt.

    Geprüft wird die Ursache und nicht der Handler: **ein** Besitzer der Taste,
    solange die Skizze offen ist, und danach wieder das Fenster.
    """
    from PySide6.QtGui import QAction, QShortcut

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.show()

        def owners() -> list[object]:
            actions = [
                action
                for action in window.findChildren(QAction)
                if action.shortcut().toString() == "Home" and action.isEnabled()
            ]
            keys = [
                shortcut
                for shortcut in window.findChildren(QShortcut)
                if shortcut.key().toString() == "Home" and shortcut.isEnabled()
            ]
            return [*actions, *keys]

        window._update_actions()
        assert len(owners()) == 1, "ohne Skizze gehört Pos1 dem Fenster, und nur ihm"

        window.start_sketch("sketch_extrude")
        window._update_actions()
        panel = window._sketch_panel
        assert panel is not None
        found = owners()
        assert len(found) <= 1, (
            f"{len(found)} Besitzer auf Pos1 — Qt führt dann keinen aus: "
            f"{[type(entry.parent()).__name__ for entry in found]}"
        )

        window.finish_sketch(keep=False)
        # Die Kürzel der Zeichenfläche sind ihre Kinder und gehen mit ihr — aber
        # erst, wenn die zurückgestellten Löschungen abgearbeitet sind.
        # ``processEvents`` allein tut das **nicht**: Das Panel lag danach noch
        # da, unsichtbar, mit aktivem Kürzel, und der Test zählte zwei Besitzer
        # für einen Zustand, den es im laufenden Programm nicht gibt.
        from PySide6.QtCore import QEvent

        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()
        window._update_actions()
        assert len(owners()) == 1, "nach der Skizze gehört sie wieder dem Fenster"
    finally:
        window.close()
        window.deleteLater()


# --- Was der Zeichnung fehlt, steht in der Zeile -------------------------------


def test_the_line_says_whether_the_outline_is_closed(qt_app: QApplication) -> None:
    """Ob die Fläche geschlossen ist, erfuhr man erst beim Bestätigen (§2.7).

    Wer vier Linien zog und den letzten Klick knapp neben den ersten Punkt
    setzte, sah dasselbe Bild wie einer, der getroffen hatte — die Auskunft
    kam danach, als Absage der Operation. Gefragt wird derselbe Kern, der
    später rechnet, und angezeigt wird **sein** Satz.
    """
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))

    assert canvas.status_text().startswith("Noch offen"), canvas.status_text()

    canvas.add_element("line", ((30.0, 0.0), (30.0, 20.0)))
    canvas.add_element("line", ((30.0, 20.0), (0.0, 20.0)))
    canvas.add_element("line", ((0.0, 20.0), (0.0, 0.0)))

    assert canvas.status_text().startswith("Geschlossen"), canvas.status_text()


def test_a_closed_outline_still_counts_its_degrees_of_freedom(qt_app: QApplication) -> None:
    """Die Freiheitsgrade bleiben in der Zeile — sie sind die zweite Frage,
    nicht die abgeschaffte."""
    canvas = SketchCanvas()
    canvas.insert_shape(shapes.rectangle(40.0, 20.0))

    line = canvas.status_text()
    assert line.startswith("Geschlossen"), line
    assert "Freiheitsgrade" in line or "Freiheitsgrad" in line, line


def test_a_selection_can_be_moved_in_one_go(qt_app: QApplication) -> None:
    """Verschieben gab es nicht — nur Punkt für Punkt (§30.1, Stufe zwei).

    Bei einem Rechteck sind das vier Züge, von denen die ersten drei die Form
    verziehen. Der Griff schiebt die ganze Auswahl und lässt die Bedingungen
    zeigen, wohin sie zeigten: die Elemente behalten ihren Platz in der Liste.
    """
    canvas = SketchCanvas()
    canvas.insert_shape(shapes.rectangle(40.0, 20.0))
    before = canvas.points()
    canvas.selection.clear()
    for index in range(len(canvas.sketch.elements)):
        canvas._select((canvas.sketch.elements[index].kind, (index * 2,)), True)

    canvas.move_selected(10.0, 5.0)

    after = canvas.points()
    assert len(after) == len(before)
    for (bx, by), (ax, ay) in zip(before, after, strict=True):
        assert ax == pytest.approx(bx + 10.0), "die Form ist nicht mitgekommen"
        assert ay == pytest.approx(by + 5.0)


def test_moving_nothing_says_what_is_missing(qt_app: QApplication) -> None:
    """Ohne Auswahl passiert nichts — und zwar hörbar (Regel 17)."""
    from app.core.errors import ValidationError
    from app.core.sketch import edit

    canvas = SketchCanvas()
    canvas.insert_shape(shapes.rectangle(40.0, 20.0))

    with pytest.raises(ValidationError) as raised:
        edit.move(canvas.sketch, (), 5.0, 0.0)
    assert "wählen" in str(raised.value)


def test_the_context_menu_offers_deleting(qt_app: QApplication) -> None:
    """Löschen lag allein auf der Entf-Taste.

    In der Werkzeugleiste steht es nicht, und wer die Taste nicht rät, wird
    ein Element nicht los. Das Kontextmenü ist der Ort, an dem man nachsieht,
    was mit *dem hier* geht — das Kürzel steht daneben, so lernt man es
    nebenbei.

    Gefragt wird ``context_menu_at`` und nicht das Mausereignis: ein Menü,
    das sich selbst öffnet, hält die Suite an.
    """
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.insert_shape(shapes.rectangle(40.0, 20.0))
    canvas._select(("line", (0,)), False)

    menu = canvas.context_menu_at(None)
    entries = [action.text() for action in menu.actions()]

    assert any("Löschen" in entry for entry in entries), entries
    assert any("Entf" in entry for entry in entries), "das Kürzel steht daneben"

    before = len(canvas.sketch.elements)
    for action in menu.actions():
        if "Löschen" in action.text():
            action.trigger()
    assert len(canvas.sketch.elements) < before, "der Eintrag löscht nichts"


def test_the_context_menu_keeps_quiet_without_a_selection(qt_app: QApplication) -> None:
    """Ohne Auswahl gibt es nichts zu löschen — und keinen Eintrag dafür."""
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.insert_shape(shapes.rectangle(40.0, 20.0))
    canvas.selection.clear()

    entries = [action.text() for action in canvas.context_menu_at(None).actions()]

    assert not any("Löschen" in entry for entry in entries), entries


def test_a_click_with_a_trembling_hand_moves_nothing(qt_app: QApplication) -> None:
    """Ein Auswahlklick ist kein Verschieben (§30.1, Stufe zwei).

    Die Hand wandert beim Klicken um ein, zwei Bildpunkte. Ohne Schwelle säße
    die Form danach ein Zehntelmillimeter daneben — eine Änderung, die niemand
    gewollt und niemand bemerkt hat, bis das Maß nicht mehr stimmt. Die Zahl
    kommt von Qt, es ist dieselbe, die ein Ziehen überall sonst auslöst.
    """
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication as App

    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.insert_shape(shapes.rectangle(40.0, 20.0))
    canvas._select(("line", (0,)), False)
    before = canvas.points()

    start = canvas._to_screen(*canvas.points()[0])
    canvas._shift_from = canvas._to_world(start)
    canvas._shifting = False
    tremble = QPointF(start.x() + 2.0, start.y() + 1.0)
    canvas._pointer = canvas._to_world(tremble)
    canvas._shift_selection(tremble)

    assert canvas.points() == before, "ein Klick hat die Zeichnung verschoben"

    # Und ab der Schwelle bewegt sie sich.
    far = QPointF(start.x() + App.startDragDistance() + 5.0, start.y())
    canvas._pointer = canvas._to_world(far)
    canvas._shift_selection(far)

    assert canvas.points() != before, "ab der Schwelle muss der Zug greifen"


def test_the_sketch_area_fits_a_laptop_screen(qt_app: QApplication) -> None:
    """**Die Zahl stimmte, die Ursache nicht — und jetzt stimmt beides.**

    Der Punkt in der Roadmap schrieb die 1007 Bildpunkte den achtzehn Knöpfen
    der Bedingungszeile zu. Gemessen war es die **Werkzeugzeile**, und
    „achtzehn Knöpfe" waren fünfzehn Knöpfe und drei Zahlenfelder, von denen
    zwei in dieser Zeile stehen:

        12 Knöpfe à 37                   444
        „Grundform" (Aufklappmenü)       153
        offset_distance („2,00 mm")      163
        measure_field („0,00 mm")        163
        ------------------------------------
        Summe der Posten                 997   (+ Abstände = 1007)

    Verschwunden ist ``measure_field`` aus dieser Zeile **ganz** — Schritt zwei
    hat es an die Zeichenfläche gehängt, wo es dem Zeiger folgt. Schritt eins
    hatte es nur ausgeblendet, solange nichts gezeichnet wird; die 881 galten
    für den Anfangszustand und sprangen beim ersten Klick zurück auf 1007. Jetzt
    bleiben sie, und kein Werkzeug ist dafür weggefallen.
    ``offset_distance`` bleibt — *Versetzen* ist ein Sofort-Knopf und kein
    Modus, sein Wert muss **vor** dem Klick einstellbar sein.

    Vier Knöpfe unter einen Überlaufknopf zu legen hätte 148 Bildpunkte
    gespart und vier Werkzeuge versteckt; das eine Feld spart mehr.

    Die Grenze ist dieselbe wie für die Bedingungszeile darüber, und aus
    demselben Grund: Zwei Zeilen desselben Bereichs nach verschiedenen
    Maßstäben zu messen wäre schlechter als eine Zahl, die man begründen kann.
    ``MAX_TOOLS = 8`` aus ``tests/test_interface_limits.py`` gilt hier
    ausdrücklich **nicht** — die zählt die Umschalter unter dem Viewport.

    Gemessen **mit Thema**: Ohne fehlt die Polsterung, die ein Kunde sieht,
    und der Nachbartest war daran zwei Runden lang grün, ohne etwas zu messen.
    """
    from app.ui.style import stylesheet

    davor = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("light", 10))
    panel = SketchPanel()
    try:
        bereich = panel.minimumSizeHint().width()
        bedingungen = panel._constraints_row.minimumSize().width()

        zeile = panel._tools_row.minimumSize().width()

        assert bereich <= 900, f"der Skizzenbereich verlangt {bereich} Bildpunkte Breite"
        assert zeile <= 900, f"die Werkzeugzeile verlangt {zeile} Bildpunkte Breite"
        assert bedingungen <= 900, f"die Bedingungszeile verlangt {bedingungen} Bildpunkte"
        assert not panel.canvas.measure_field.isVisibleTo(panel.canvas), (
            "solange nichts gezeichnet ist, hat das Maßfeld nichts zu zeigen"
        )
    finally:
        panel.deleteLater()
        qt_app.setStyleSheet(davor)


def test_the_measure_follows_the_pointer_instead_of_sitting_in_the_toolbar(
    qt_app: QApplication,
) -> None:
    """Das Maß steht dort, wo der Blick ist — am Zeiger, nicht in der Leiste.

    **Schritt zwei des Registerpunkts.** Schritt eins hat das Feld aus der
    Werkzeugzeile verschwinden lassen, solange nichts gezeichnet wird (1007 →
    881 Bildpunkte). Es stand aber weiterhin *in der Leiste*, und das ist beim
    Zeichnen die falsche Stelle: Wer eine Linie zieht, sieht auf die Spitze der
    Linie, und die Zahl, die er gerade eintippen will, steht am unteren Rand
    des Fensters. Fusion legt sie an den Zeiger; darum ist das Eintippen dort
    der Normalweg und hier war es eine Funktion, die man kennen musste.

    Drei Zusagen, und die dritte ist die, die man vergisst:

    1. Das Feld gehört der Zeichenfläche, nicht der Werkzeugzeile.
    2. Es folgt dem Zeiger, mit Abstand — läge es darunter, finge es die
       Mausbewegungen ab, und die Linie bliebe stehen.
    3. Es bleibt im Bild. Am rechten und unteren Rand kippt es auf die andere
       Seite des Zeigers, statt hinauszuragen.
    """
    panel = SketchPanel()
    canvas = panel.canvas
    canvas.resize(400, 300)
    field = canvas.measure_field

    assert field.parent() is canvas, "das Maß gehört an die Fläche, nicht in die Leiste"
    assert not field.isVisibleTo(canvas), "ohne angefangenes Element hat es nichts zu zeigen"

    canvas.set_tool("line")
    canvas.place(canvas._to_screen(0.0, 0.0))
    canvas._pointer = (10.0, 0.0)
    canvas.measuringChanged.emit(canvas.pending_measure())

    assert field.isVisibleTo(canvas), "beim Zeichnen steht es da"
    assert field.value_mm() == pytest.approx(10.0)

    spitze = canvas._to_screen(*canvas._pointer)
    kasten = field.geometry()
    assert not kasten.contains(spitze.toPoint()), (
        "das Feld liegt unter dem Zeiger und fängt damit die Mausbewegungen ab"
    )
    assert canvas.rect().contains(kasten), f"das Feld ragt aus dem Bild: {kasten}"

    # Und am Rand kippt es, statt hinauszuragen.
    canvas._pointer = canvas._to_world(QPointF(canvas.width() - 4.0, canvas.height() - 4.0))
    canvas.measuringChanged.emit(canvas.pending_measure())
    assert canvas.rect().contains(field.geometry()), (
        f"am unteren rechten Rand ragt es hinaus: {field.geometry()}"
    )

    panel.deleteLater()


def test_typing_a_digit_while_drawing_goes_into_the_measure(qt_app: QApplication) -> None:
    """Wer zeichnet, tippt die Zahl — er klickt nicht erst ins Feld.

    Das ist der Grund, warum das Feld überhaupt an den Zeiger gehört: In Fusion
    beginnt die Eingabe mit der ersten Ziffer, ohne Klick und ohne Tabulator.
    Ein Feld, das man erst anklicken muss, verlangt genau die Handbewegung, die
    das Zeichnen unterbricht — und der Zeiger steht danach woanders.
    """
    from PySide6.QtGui import QKeyEvent

    panel = SketchPanel()
    canvas = panel.canvas
    canvas.set_tool("line")
    canvas.place(canvas._to_screen(0.0, 0.0))
    canvas._pointer = (10.0, 0.0)
    canvas.measuringChanged.emit(canvas.pending_measure())

    canvas.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier, "2")
    )

    # **Die Wirkung, nicht der Mechanismus.** ``hasFocus()`` wäre hier immer
    # falsch: Ein Fenster, das nie gezeigt wurde, ist nie aktiv, und ohne
    # aktives Fenster vergibt Qt keinen Tastaturfokus. Der Test hätte damit
    # eine Eigenschaft der Testumgebung geprüft und nicht die Bedienung.
    assert "2" in canvas.measure_field.text(), (
        f"die Ziffer kam nicht im Feld an: {canvas.measure_field.text()!r}"
    )

    panel.deleteLater()
