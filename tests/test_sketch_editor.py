"""Der grafische Skizzeneditor (§30.1, Stufe zwei), offscreen.

Geprüft wird die Verdrahtung und das Modell, keine Pixel: gezeichnet wird
über dieselben Methoden, die auch die Maus ruft, Bedingungen gehen den Weg
der Knöpfe, und am Ende steht der Text, den die Skizzen-Ops lesen.

Am Ende der Datei der **Skizzenmodus des Fensters**: er benutzt dasselbe
Panel, geprüft wird dort deshalb der Weg hinein und heraus, nicht noch einmal
das Zeichnen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("scipy")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.core.sketch import shapes
from app.core.sketch.planes import image_normal
from app.core.sketch.serialize import sketch_from_text, sketch_to_text
from app.core.types import PlaneFrame
from app.ui.op_dialog import OperationDialog
from app.ui.sketch_editor import (
    ExpressionDialog,
    SketchCanvas,
    SketchEditorDialog,
    SketchField,
    SketchPanel,
    _constraint_label,
)
from app.ui.viewport import FIT_ROOM, camera_for_span


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


def test_the_auto_width_snaps_to_the_drawn_grid(qt_app: QApplication) -> None:
    """Null heißt „Automatisch": Der Fang ist das Raster im Bild.

    Roberts Regel vom 24.08.2026 („das fang sollte immer das raster sein")
    galt im Zeichnen-Dialog nicht: Dort führt niemand ``follow_grid`` nach,
    ``set_snapping`` übernahm nur Weiten über null, und gefangen wurde auf
    dem letzten stehengebliebenen Wert, während das Bild ein zoomabhängiges
    Raster zeichnete — zwei Zahlen für dieselbe Zusage.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)

    canvas.set_snapping(True, 0.0)
    step = canvas.grid_step()
    assert step > 0.0, "ohne Rasterweite prüft der Test nichts"
    close_to_one = (step * 1.4, step * 0.6)
    assert canvas.snapped(close_to_one) == pytest.approx((step, step))


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

        # **Getippt wird dorthin, wo der Fokus im Betrieb liegt.** Seit dem
        # Schnitt ist das der Viewport und nicht mehr der Zeichenbereich — der
        # ist unsichtbar und bekommt keine Tasten. Genau deshalb gelten die
        # Ebenen-Kürzel im Viewport-Modus fensterweit; ein Kürzel, das nur im
        # unsichtbaren Bereich feuert, feuert nie.
        window.viewport.setFocus()
        QTest.keyClick(window, Qt.Key.Key_2)
        qt_app.processEvents()
        assert panel.canvas.sketch.plane == "plane:xz", (
            "Die Taste 2 kam nicht an — liegt wieder ein Kürzel des Fensters darauf?"
        )

        QTest.keyClick(window, Qt.Key.Key_3)
        qt_app.processEvents()
        assert panel.canvas.sketch.plane == "plane:yz"

        # Die Gegenprobe im selben Lauf: Mit wieder aktiven Menü-Kürzeln muss
        # dieselbe Taste versagen. Ohne sie stünde hier ein Test, der auch dann
        # grün bliebe, wenn es den Konflikt nie gegeben hätte.
        for action in window._display_actions:
            action.setEnabled(True)
        panel.choose_plane("plane:xy")
        QTest.keyClick(window, Qt.Key.Key_2)
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

    # **Der Bogen fragt Anfang, Ende, Wölbung** — seit dem 24.08.2026 in
    # dieser Reihenfolge, wie in Fusion und Onshape. Vorher war der erste
    # Klick die Mitte: ein Punkt, der auf keiner Kante liegt.
    canvas.set_tool("arc")
    assert "Anfang" in canvas.status_text()
    canvas.place(canvas._to_screen(0.0, 0.0))
    assert "Ende" in canvas.status_text()
    canvas.place(canvas._to_screen(40.0, 0.0))
    assert "wölbt" in canvas.status_text()


def test_a_flat_arc_is_refused_and_says_so(qt_app: QApplication) -> None:
    """Drei Punkte auf einer Geraden geben keinen Kreis — und das steht da.

    Ein abgelehnter Klick, der nichts sagt, sieht aus wie ein verschluckter:
    Der Nutzer klickt, es passiert nichts, und er klickt wieder. Regel 17
    verlangt einen Handlungsvorschlag, und der ist hier „weiter daneben".

    Stehen bleiben Anfang und Ende — nur der eine Klick ist zu wiederholen
    und nicht der ganze Bogen.
    """
    canvas = SketchCanvas()
    canvas.resize(400, 400)
    canvas.set_tool("arc")
    canvas.place(canvas._to_screen(0.0, 0.0))
    canvas.place(canvas._to_screen(40.0, 0.0))
    vorher = len(canvas.sketch.elements)

    canvas.place(canvas._to_screen(20.0, 0.0))  # genau auf der Sehne
    assert len(canvas.sketch.elements) == vorher, "aus einer Geraden wird kein Bogen"
    zeile = canvas.status_text()
    assert "Geraden" in zeile and "daneben" in zeile, f"die Zeile sagt warum: {zeile!r}"

    # Und weiter daneben geht es: der Bogen entsteht, die Zeile ist wieder
    # die gewöhnliche.
    canvas.place(canvas._to_screen(20.0, 15.0))
    assert len(canvas.sketch.elements) == vorher + 1
    assert "Geraden" not in canvas.status_text()


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
        assert window.sketching(), "der Skizzenmodus läuft"
        # **Diese Zusicherung hat sich mit dem Schnitt (§30.1, P4) umgedreht,
        # und sie ist dabei näher an den Bauplan gerückt.** Er verlangt den
        # Editor „im Viewport, nicht in einem Fenster darüber"; solange die
        # Zeichenfläche die Ansicht *ersetzte*, war das nur halb wahr — sie lag
        # an ihrer Stelle. Jetzt liegt sie darin: Die Ansicht bleibt stehen,
        # das Modell tritt zurück, und die Skizze liegt auf ihrer Ebene.
        assert window.middle_stack.currentWidget() is window.viewport, (
            "die Ansicht bleibt stehen — gezeichnet wird in ihr"
        )
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


def test_projecting_on_a_face_plane_cuts_along_that_face(qt_app: QApplication) -> None:
    """Auf einer Flächenebene schneidet die Projektion durch diese Ebene.

    Vorher lief der Schnitt immer durch die globale XY-Ebene: Wer auf einer
    Seitenwand zeichnete, bekam die Grundfläche des Körpers als Hilfskontur —
    Kanten, die auf dieser Wand gar nicht liegen.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import PlaneFrame

    wall = PlaneFrame(
        origin=(0.0, 0.0, 0.0),
        x_axis=(0.0, 1.0, 0.0),
        y_axis=(0.0, 0.0, 1.0),
        normal=(1.0, 0.0, 0.0),
    )
    canvas = SketchCanvas()
    canvas.set_plane("feature:face_3")
    canvas.offer_frames(lambda plane: wall if plane == "feature:face_3" else None)
    canvas.offer_bodies([MeshData.of(trimesh.creation.box(extents=(20.0, 10.0, 6.0)))])

    canvas.project_bodies()

    assert canvas.sketch.elements
    spans_x = [abs(point[0]) for element in canvas.sketch.elements for point in element.points]
    spans_y = [abs(point[1]) for element in canvas.sketch.elements for point in element.points]
    # Der Schnitt bei x = 0 ist das 10 x 6-Rechteck (y, z) — nicht das
    # 20 x 10 der Grundfläche.
    assert max(spans_x) == pytest.approx(5.0, abs=1e-6)
    assert max(spans_y) == pytest.approx(3.0, abs=1e-6)


def test_projecting_on_a_vanished_face_says_so(qt_app: QApplication) -> None:
    """Ist die Fläche der Zeichenebene weg, sagt es die Statuszeile.

    Der stille Rückfall auf XY wäre die alte Falle in neuer Gestalt: ein
    Schnitt durch eine Ebene, die niemand gewählt hat.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    canvas = SketchCanvas()
    canvas.set_plane("feature:face_9")
    canvas.offer_frames(lambda plane: None)
    canvas.offer_bodies([MeshData.of(trimesh.creation.box(extents=(20.0, 10.0, 6.0)))])
    said: list[str] = []
    canvas.statusChanged.connect(said.append)

    canvas.project_bodies()

    assert not canvas.sketch.elements
    assert said and "Fläche" in said[-1]


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


def test_the_snap_radius_follows_the_visible_scale(qt_app: QApplication) -> None:
    """Acht Bildpunkte Fang sind acht Punkte des Bildes, das man ansieht.

    Im Viewport-Modus ist der Canvas unsichtbar und sein Maßstab steht auf
    der Start-Einpassung (~1,2 px/mm über ein 220-mm-Bett): Der Fang wurde
    darüber gerechnet 6,7 mm weit — ein Klick fünf Millimeter neben einem
    Punkt schnappte auf ihn und erzeugte eine ungewollte Deckungsbedingung
    (Gesamtreview 25.08.2026, J-2). Das Fenster meldet deshalb den
    Kamera-Maßstab, und die Trefferrechnung nimmt ihn.
    """
    canvas = SketchCanvas()
    canvas.resize(600, 600)
    canvas.set_tool("point")
    canvas.place(canvas._to_screen(20.0, 0.0))

    # Zeichenflächen-Modus: der eigene Maßstab gilt weiter.
    nearby = canvas._to_screen(20.0, 0.0)
    nearby.setX(nearby.x() + 4.0)
    assert canvas._hit_point(nearby) == 0, "vier Canvas-Punkte daneben fängt"

    # Das sichtbare Bild zeigt 20 px je mm: 0,5 mm sind zehn Bildpunkte.
    canvas.set_view_scale(20.0)
    assert canvas._hit_point(canvas._to_screen(20.5, 0.0)) is None, (
        "ein halber Millimeter ist bei 20 px/mm außerhalb der acht Punkte"
    )
    assert canvas._hit_point(canvas._to_screen(20.3, 0.0)) == 0, (
        "0,3 mm sind sechs Bildpunkte — der Fang bleibt ein Fang"
    )

    canvas.set_view_scale(None)
    assert canvas._hit_point(nearby) == 0, "zurück im Zeichenflächen-Modus"


def test_dragging_a_point_keeps_the_construction_flag(qt_app: QApplication) -> None:
    """Ziehen baut das Element neu — und verlor dabei das Kennzeichen: Aus
    einer nachgezogenen Mittellinie wurde eine Profilkante, und der Körper
    bekam eine Trennung mitten hindurch, ohne Meldung (Gesamtreview
    25.08.2026, J-3). Dasselbe gilt für „Koordinaten …", das denselben Weg
    nimmt.
    """
    from app.core.types import Sketch, SketchElement

    canvas = SketchCanvas()
    canvas.set_sketch(
        Sketch(
            plane="plane:xy",
            elements=(
                SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0)), construction=True),
            ),
        )
    )

    canvas.move_point(0, 2.0, 3.0)

    assert canvas.sketch.elements[0].construction, "gezogen bleibt Hilfsgeometrie"


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


# --- Die Umrechnung Blatt ↔ Zeichnung (§30.1, P2c) ---------------------------
#
# Sie war als Methodenpaar eines Widgets nur mit einem Widget prüfbar, und
# ihre tragende Eigenschaft — dass beide Richtungen zueinander passen —
# deshalb nie gegen Zahlen gehalten. Ein Klick landete dort, wo `_to_screen`
# ihn hingelegt hatte, und das sah in jedem Test richtig aus.

SHEET = (400.0, 300.0)
"""Eine Blattgröße mit ungleichen Seiten: quadratisch fiele eine vertauschte
Achse nicht auf."""


def test_the_centre_of_the_drawing_sits_in_the_middle_of_the_sheet() -> None:
    """Der Ankerpunkt der ganzen Rechnung."""
    from app.ui.sketch_editor import sheet_point

    assert sheet_point((7.0, -3.0), (7.0, -3.0), 4.0, SHEET) == pytest.approx((200.0, 150.0))


def test_the_sheet_counts_y_downwards_and_the_drawing_does_not() -> None:
    """Qt zählt Y nach unten, eine Zeichnung nach oben.

    Dieses Minus **ist** die Umrechnung. Ohne es steht die Skizze auf dem
    Kopf — und zwar spiegelbildlich richtig, was in jedem Test mit
    symmetrischen Formen unauffällig bleibt.
    """
    from app.ui.sketch_editor import sheet_point

    up = sheet_point((0.0, 10.0), (0.0, 0.0), 2.0, SHEET)
    down = sheet_point((0.0, -10.0), (0.0, 0.0), 2.0, SHEET)

    assert up[1] < down[1], "zehn Millimeter nach oben liegen weiter oben auf dem Blatt"
    assert up == pytest.approx((200.0, 130.0))
    assert down == pytest.approx((200.0, 170.0))


def test_the_two_directions_undo_each_other() -> None:
    """Hin und zurück muss denselben Punkt ergeben — in beiden Richtungen.

    Die teure Form dieses Fehlers ist keine Ausnahme, sondern ein Klick, der
    einen halben Bildpunkt neben dem Punkt landet, den er greifen wollte.
    """
    from app.ui.sketch_editor import drawing_point, sheet_point

    centre, scale = (12.0, -4.0), 3.5
    for drawing in ((0.0, 0.0), (25.5, -13.25), (-40.0, 40.0)):
        back = drawing_point(sheet_point(drawing, centre, scale, SHEET), centre, scale, SHEET)
        assert back == pytest.approx(drawing)

    for place in ((0.0, 0.0), (399.0, 1.0), (123.5, 222.25)):
        again = sheet_point(drawing_point(place, centre, scale, SHEET), centre, scale, SHEET)
        assert again == pytest.approx(place)


def test_a_bigger_scale_spreads_the_drawing() -> None:
    """Der Maßstab ist Bildpunkte je Millimeter, nicht umgekehrt.

    Ein vertauschter Kehrwert liefert immer noch ein Bild — nur ein winziges,
    und beim Zoomen wird es kleiner statt größer.
    """
    from app.ui.sketch_editor import sheet_point

    near = sheet_point((10.0, 0.0), (0.0, 0.0), 2.0, SHEET)
    far = sheet_point((10.0, 0.0), (0.0, 0.0), 8.0, SHEET)

    assert near[0] - 200.0 == pytest.approx(20.0)
    assert far[0] - 200.0 == pytest.approx(80.0)


def test_moving_the_centre_moves_the_drawing_the_other_way() -> None:
    """Wer den Blick nach rechts schiebt, sieht die Zeichnung nach links gehen.

    Das Vorzeichen hier ist das, das beim Schieben mit der Maus umkippt: Ein
    Fehler darin lässt die Zeichnung dem Zeiger doppelt so schnell und in die
    falsche Richtung folgen.
    """
    from app.ui.sketch_editor import sheet_point

    still = sheet_point((0.0, 0.0), (0.0, 0.0), 2.0, SHEET)
    shifted = sheet_point((0.0, 0.0), (10.0, 0.0), 2.0, SHEET)

    assert shifted[0] < still[0], "die Mitte wanderte nach rechts, der Ursprung nach links"
    assert still[0] - shifted[0] == pytest.approx(20.0)


def test_the_canvas_only_passes_the_numbers_through(qt_app: QApplication) -> None:
    """Das Widget rechnet nicht selbst, es reicht durch.

    Sonst wäre die geprüfte Rechnung eine zweite neben der benutzten — genau
    die Doppelung, die dieser Umbau aufgelöst hat.
    """
    from app.ui.sketch_editor import SketchCanvas, sheet_point

    canvas = SketchCanvas()
    canvas.resize(int(SHEET[0]), int(SHEET[1]))
    centre, scale, size = canvas._sheet()

    place = canvas._to_screen(15.0, -7.0)
    wanted = sheet_point((15.0, -7.0), centre, scale, size)

    assert (place.x(), place.y()) == pytest.approx(wanted)
    assert canvas._to_world(place) == pytest.approx((15.0, -7.0))


# --- Auf einer Fläche des Körpers zeichnen (§30.1, P3) -----------------------


def test_a_face_of_the_body_can_be_chosen_as_the_drawing_plane(qt_app: QApplication) -> None:
    """`feature:<id>` ist eine Ebene wie XY auch — und der interessantere Weg.

    ``app/core/sketch/planes.py`` nennt sie so: „der Weg, auf einem
    vorhandenen Teil weiterzubauen, statt daneben". Geprüft war bisher nur der
    Wechsel zwischen den drei Grundebenen; dass eine angebotene Fläche
    dasselbe kann, stand nirgends.
    """
    from app.ui.sketch_editor import SketchPanel, Surroundings

    panel = SketchPanel(
        surroundings=Surroundings(
            faces=(("face_7", "Fläche an Gehäuse — 2 400 mm², oben", (0.0, 0.0, 1.0)),)
        )
    )
    try:
        assert panel.choose_plane("feature:face_7") is True
        assert panel.canvas.sketch.plane == "feature:face_7"
        assert panel.plane_choice.currentData() == "feature:face_7", "die Wahl steht mit"

        # Auf einer angeklickten Fläche bleiben die Achsenbuchstaben weg: sie
        # kann beliebig geneigt sein, und „X" auf einer schrägen Wand wäre
        # eine Angabe, die nicht stimmt.
        assert panel.canvas.axis_names() == ("", "")
    finally:
        panel.deleteLater()


def test_a_plane_that_is_not_offered_says_so_instead_of_staying_quiet(
    qt_app: QApplication,
) -> None:
    """Eine Fläche, die der Körper nicht hat, darf nicht still auf XY landen.

    Für die Ziffern 1 bis 3 war der stille Zweig folgenlos — sie treffen
    immer. Für „Fläche anklicken, dann darauf zeichnen" wäre er die
    schlechteste Antwort: Wer auf eine Deckfläche zeigt und danach unbemerkt
    auf der Grundebene zeichnet, sucht den Fehler in seiner Zeichnung.
    """
    from app.ui.sketch_editor import SketchPanel

    panel = SketchPanel()
    try:
        assert panel.choose_plane("feature:face_99") is False
        assert panel.canvas.sketch.plane == "plane:xy", "und nichts hat sich geändert"
        assert panel.plane_choice.currentData() == "plane:xy"
    finally:
        panel.deleteLater()


# --- Zeichnen ohne eigene Zeichenfläche (§30.1, P4) --------------------------


def test_a_click_given_in_millimetres_lands_where_it_says(qt_app: QApplication) -> None:
    """Der Weg für den Skizzenmodus im Viewport.

    Dort kommt der Ort nicht aus einem Mausereignis auf dieser Fläche,
    sondern aus dem Schnitt des Sichtstrahls mit der Zeichenebene.
    Millimeter sind, was beide Wege gemeinsam haben.
    """
    from app.ui.sketch_editor import SketchCanvas

    canvas = SketchCanvas()
    canvas.resize(400, 300)
    canvas.set_tool("line")
    canvas.place_on_plane((10.0, 5.0))
    canvas.place_on_plane((30.0, 5.0))

    assert len(canvas.sketch.elements) == 1, "eine Linie aus zwei Klicks"
    start, end = canvas.sketch.elements[0].points
    assert start == pytest.approx((10.0, 5.0))
    assert end == pytest.approx((30.0, 5.0))


def test_the_size_of_the_drawing_area_does_not_move_the_point(qt_app: QApplication) -> None:
    """**Die Zusage, auf der der unsichtbare Canvas steht.**

    Im Viewport-Modus hat die Zeichenfläche kein Bild mehr — sie rechnet nur
    noch. Damit das trägt, muss ein in Millimetern gegebener Klick unabhängig
    von ihrer Größe landen: ``_to_screen`` und ``_to_world`` sind exakt
    umkehrbar (P2c), also kürzt sich die Größe aus beiden Richtungen heraus.

    Geprüft an drei sehr verschiedenen Größen. Ginge es schief, läge der
    Punkt nicht daneben, sondern **skaliert** daneben — ein Fehler, der mit
    dem Fenster wächst und im Test mit einer festen Größe nie auffällt.
    """
    from app.ui.sketch_editor import SketchCanvas

    ohne_fang = []
    mit_fang = []
    for width, height in ((400, 300), (1600, 900), (120, 4000)):
        free = SketchCanvas()
        free.resize(width, height)
        free.set_snapping(False)
        free.set_tool("point")
        free.place_on_plane((-17.5, 42.25))
        ohne_fang.append(free.sketch.elements[0].points[0])

        snapped = SketchCanvas()
        snapped.resize(width, height)
        snapped.set_tool("point")
        snapped.place_on_plane((-17.5, 42.25))
        mit_fang.append(snapped.sketch.elements[0].points[0])

    for place in ohne_fang:
        assert place == pytest.approx((-17.5, 42.25)), "ohne Fang genau die gegebene Zahl"

    # **Und mit Fang dieselbe Stelle für alle drei.** Der Fang rundet
    # (-17,5 | 42,25) auf ganze Millimeter — das ist richtig und war der
    # Grund, warum die erste Fassung dieses Tests rot war. Die Zusage lautet
    # nicht „der Fang greift nicht", sondern „er greift überall gleich": Hinge
    # er an der Größe der Fläche, säße derselbe Klick im großen Fenster
    # woanders als im kleinen.
    assert len(set(mit_fang)) == 1, f"der Fang fällt verschieden aus: {mit_fang}"
    assert mit_fang[0] != pytest.approx((-17.5, 42.25)), "und er hat wirklich gefangen"


def test_the_pointer_can_be_set_without_a_mouse(qt_app: QApplication) -> None:
    """Die Vorschau hängt am Zeiger, und der kommt im Viewport aus dem Strahl.

    ``note_pointer`` ist aus ``mouseMoveEvent`` herausgelöst, damit sie ohne
    Mausereignis auf dieser Fläche gerufen werden kann — dieselbe Aufteilung
    wie bei ``place`` und ``grab_point``.
    """
    from app.ui.sketch_editor import SketchCanvas

    canvas = SketchCanvas()
    canvas.resize(400, 300)
    canvas.set_snapping(False)
    canvas.hover_on_plane((12.0, -8.0))

    assert canvas.pointer_target() == pytest.approx((12.0, -8.0))


def test_the_sketch_view_is_orthographic_and_gives_the_projection_back(
    qt_app: QApplication,
) -> None:
    """Perspektivisch ist eine Draufsicht keine.

    Gesehen im gerenderten Fenster, nicht in einer Zahl: Die Korpusplatte stand
    trapezförmig im Bild, mit sichtbaren Seitenwänden, während die Zeile
    darunter „Draufsicht (XY)" meldete. Der Grund steht seit je am Umschalter
    selbst (§18.1) — Parallelprojektion ist das, was gemessene Längen
    vertrauenswürdig macht. Auf einer Zeichenebene wiegt das schwerer als sonst
    irgendwo: Zwei gleich lange Strecken erscheinen perspektivisch verschieden
    lang, je nachdem, wie weit sie von der Bildmitte weg liegen, und genau
    darauf setzt man beim Zeichnen Punkte.

    **Zurückgestellt wird auf den Wert davor, nicht auf „perspektivisch".** Die
    Projektion ist eine Einstellung des Nutzers; wer orthografisch arbeitet,
    hat sie gewählt und bekommt sie nach dem Zeichnen nicht weggenommen.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    for davor in ("perspective", "orthographic"):
        window = MainWindow(Session(), UiSettings())
        try:
            window.viewport.set_projection(davor)  # type: ignore[arg-type]
            assert window.viewport.projection == davor

            window.start_sketch("sketch_extrude")
            assert window.viewport.projection == "orthographic", (
                f"aus {davor} heraus wird im Skizzenmodus orthografisch gesehen"
            )

            window.finish_sketch(keep=False)
            assert window.viewport.projection == davor, (
                f"nach dem Zeichnen steht wieder {davor} — die Wahl gehört dem Nutzer"
            )
        finally:
            window.deleteLater()


def test_switching_to_parallel_keeps_the_section_instead_of_jumping_to_two_millimetres(
    qt_app: QApplication,
) -> None:
    """VTK führt für beide Projektionen getrennte Größen.

    Die Zentralprojektion lebt vom Blickwinkel, die Parallelprojektion von
    ``parallel_scale`` — der halben sichtbaren Höhe in Weltmaßen. Wer
    umschaltet, ohne die eine aus der anderen zu rechnen, landet auf VTKs
    Startwert von 1,0: ein sichtbarer Ausschnitt von zwei Millimetern, und die
    Skizze wäre beim Betreten des Modus weg.

    Gerechnet wird in der Fokusebene, denn dort liegt die Zeichnung — der eine
    Ort, an dem beide Projektionen dasselbe zeigen sollen.
    """
    import math

    from app.ui.viewport import Viewport

    class _Camera:
        parallel_projection = True
        parallel_scale = 1.0
        view_angle = 30.0

    camera = _Camera()

    class _Plotter:
        pass

    plotter = _Plotter()
    plotter.camera = camera  # type: ignore[attr-defined]

    viewport = Viewport()
    viewport.plotter = plotter  # type: ignore[assignment]

    viewport._fit_parallel_scale(200.0)
    erwartet = 200.0 * math.tan(math.radians(30.0) / 2.0)
    assert camera.parallel_scale == pytest.approx(erwartet)
    assert camera.parallel_scale == pytest.approx(53.59, abs=0.01), (
        "gut hundert Millimeter sichtbare Höhe und nicht zwei"
    )

    # Steht die Kamera perspektivisch, wird nichts angefasst: dort ist
    # ``parallel_scale`` bedeutungslos, und ein Wert darin wäre eine Falle für
    # den nächsten, der umschaltet.
    camera.parallel_projection = False
    camera.parallel_scale = 7.0
    viewport._fit_parallel_scale(200.0)
    assert camera.parallel_scale == pytest.approx(7.0)


def test_the_measure_field_moves_to_the_viewport_and_back(qt_app: QApplication) -> None:
    """E19 gab es im gefahrenen Modus nicht: Das Maßfeld ist ein Kind des
    Canvas, und der ist im Viewport-Modus unsichtbar (Gesamtreview 25.08.2026,
    J-7). Verliehen wohnt es über der Ansicht und rechnet seine Lage gegen
    deren Bild; zurückgeholt wird es, bevor das Panel stirbt.

    ``isVisibleTo`` statt ``isVisible`` — in einem nie gezeigten Fenster lügt
    das zweite (siehe wartezeit.md).
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget

    host = QWidget()
    host.resize(800, 600)
    canvas = SketchCanvas()
    try:
        canvas.resize(600, 600)
        canvas.set_tool("line")
        canvas.lend_measure_field(host, lambda point: QPoint(50, 40))
        assert canvas.measure_field.parent() is host

        canvas.place(canvas._to_screen(0.0, 0.0))
        canvas.note_pointer(canvas._to_screen(30.0, 0.0))

        assert canvas.pending_measure() > 0.0, "eine angefangene Linie misst"
        assert canvas.measure_field.isVisibleTo(host), "das Feld steht im Wirt"
        assert canvas.measure_field.pos().x() > 50, "neben der Bildstelle, nicht auf ihr"

        # Ohne Bildstelle (Ebene hinter der Kamera) bleibt das Feld weg.
        canvas.lend_measure_field(host, lambda point: None)
        canvas.note_pointer(canvas._to_screen(40.0, 0.0))
        assert not canvas.measure_field.isVisibleTo(host)

        canvas.reclaim_measure_field()
        assert canvas.measure_field.parent() is canvas
    finally:
        canvas.deleteLater()
        host.deleteLater()


def test_a_digit_beats_the_plane_shortcut_while_measuring(qt_app: QApplication) -> None:
    """Die Ebenen-Kürzel liegen auf 1, 2 und 3 — und ein Kürzel gewinnt vor
    jedem keyPressEvent: Die erste Ziffer von „12,5" schaltete die Ebene um,
    statt die Eingabe zu beginnen. ``ShortcutOverride`` gibt dem Maß die
    Vorfahrt, solange eines aussteht (Gesamtreview 25.08.2026, J-7).
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    canvas = SketchCanvas()
    try:
        canvas.resize(600, 600)
        canvas.set_tool("line")

        override = QKeyEvent(
            QEvent.Type.ShortcutOverride, Qt.Key.Key_1, Qt.KeyboardModifier.NoModifier, "1"
        )
        assert not canvas.event(override) or not override.isAccepted(), (
            "ohne ausstehendes Maß bleibt die 1 ein Ebenen-Kürzel"
        )

        canvas.place(canvas._to_screen(0.0, 0.0))
        canvas.note_pointer(canvas._to_screen(30.0, 0.0))
        assert canvas.pending_measure() > 0.0

        override = QKeyEvent(
            QEvent.Type.ShortcutOverride, Qt.Key.Key_1, Qt.KeyboardModifier.NoModifier, "1"
        )
        assert canvas.event(override) and override.isAccepted(), (
            "mit ausstehendem Maß gehört die Ziffer der Eingabe"
        )

        press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_1, Qt.KeyboardModifier.NoModifier, "1")
        assert canvas.begin_measure_entry(press), "und der Tastendruck beginnt sie"
        assert canvas.measure_field.lineEdit().text().startswith("1")
    finally:
        canvas.deleteLater()


def test_the_viewport_routes_digits_to_the_lent_measure_field(qt_app: QApplication) -> None:
    """Im gefahrenen Modus liegt der Fokus auf der Ansicht — deren
    Ereignisfilter muss die erste Ziffer zum verliehenen Feld bringen und dem
    Ebenen-Kürzel vorher die Taste nehmen (Gesamtreview 25.08.2026, J-7).
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:

        class _Interactor:
            pass

        class _Plotter:
            interactor = _Interactor()

        viewport.plotter = _Plotter()
        viewport._sketch_frame = object()
        begun: list[str] = []
        viewport.set_sketch_entry(lambda: 12.0, lambda event: begun.append(event.text()) or True)

        override = QKeyEvent(
            QEvent.Type.ShortcutOverride, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier, "2"
        )
        assert viewport.eventFilter(_Plotter.interactor, override)
        assert override.isAccepted(), "die Ziffer gehört dem Maß, nicht der Ebene"

        press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier, "2")
        assert viewport.eventFilter(_Plotter.interactor, press)
        assert begun == ["2"], "der Tastendruck erreicht den Canvas"

        viewport.set_sketch_entry(None, None)
        press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier, "2")
        assert not viewport.eventFilter(_Plotter.interactor, press), (
            "abgeklemmt läuft nichts mehr in ein totes Panel"
        )
    finally:
        viewport.deleteLater()


def test_the_sketch_menu_is_reachable_from_a_plane_point(qt_app: QApplication) -> None:
    """Das Kontextmenü der Zeichnung braucht einen Weg über Millimeter.

    Im Viewport-Modus kommt der Rechtsklick als Stelle der Zeichenebene an,
    nicht als Mausereignis auf dieser Fläche — ohne ``context_menu_on_plane``
    war das gebaute Menü (Koordinaten, Löschen, Bedingungen) dort unerreichbar
    (Gesamtreview 25.08.2026, J-6). Der Treffertest ist derselbe wie beim
    Klick: auf dem Punkt gibt es „Koordinaten …", daneben nicht.
    """
    canvas = SketchCanvas()
    try:
        canvas.resize(600, 600)
        canvas.set_tool("point")
        canvas.place(canvas._to_screen(20.0, 0.0))

        on_the_point = canvas.context_menu_on_plane((20.0, 0.0))
        texts = [action.text() for action in on_the_point.actions() if action.text()]
        assert any("Koordinaten" in text for text in texts), texts

        beside = canvas.context_menu_on_plane((80.0, 40.0))
        beside_texts = [action.text() for action in beside.actions() if action.text()]
        assert not any("Koordinaten" in text for text in beside_texts), beside_texts
    finally:
        canvas.deleteLater()


def test_a_right_click_while_sketching_asks_the_sketch_not_the_scene(
    qt_app: QApplication,
) -> None:
    """Rechts fragt beim Zeichnen die Zeichnung, nicht die Objektauswahl.

    ``_on_right_click`` kannte den Skizzenmodus nicht: Es lief in
    ``_select_at`` und öffnete das Objektbaum-Menü — die Auswahl wechselte
    mitten im Zeichnen, und das Skizzenmenü gab es nicht (Gesamtreview
    25.08.2026, J-6). Jetzt gilt dieselbe Wache wie beim Linksklick.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        happened: list[object] = []
        viewport.sketchMenuAt.connect(lambda point, x, y: happened.append(("menu", point, x, y)))
        viewport.objectPicked.connect(lambda oid: happened.append(("picked", oid)))
        viewport._sketch_frame = object()

        viewport._sketch_hit = lambda x, y: (3.0, 4.0)  # type: ignore[method-assign]
        viewport._on_right_click(10, 20)
        assert happened == [("menu", (3.0, 4.0), 10, 20)], happened

        happened.clear()
        viewport._sketch_hit = lambda x, y: None  # type: ignore[method-assign]
        viewport._on_right_click(10, 20)
        assert happened == [], "neben der Ebene passiert nichts — auch keine Abwahl"
    finally:
        viewport.deleteLater()


def test_viewport_mode_rehangs_every_sketch_shortcut(qt_app: QApplication) -> None:
    """Elf von dreizehn Zeichenkürzeln feuerten im Viewport-Modus nie.

    ``use_viewport`` hob nur die Ebenen-Ziffern auf ``WindowShortcut`` — mit
    der richtigen Begründung, die für alle gilt: Der Fokus liegt im Viewport,
    und ein Kürzel, das nur im unsichtbaren Zeichenbereich feuert, feuert
    nie. Linie, Kreis, Bogen, Trimmen, Rechteck, Abstand, Versatz, Strg+Z und
    Pos1 blieben an ``WidgetWithChildrenShortcut`` — für Strg+Z und Pos1 gab
    es damit gar keinen Tastaturweg, obwohl der Einpassen-Knopf die Taste im
    Tooltip nennt (Gesamtreview 25.08.2026, J-4).

    Das Tippen im Chat bleibt dabei sicher: Textfelder nehmen ihre Zeichen
    über ``ShortcutOverride``, bevor ein Fensterkürzel greift.
    """
    from PySide6.QtGui import QShortcut

    panel = SketchPanel()
    try:
        shortcuts = panel.findChildren(QShortcut)
        assert len(shortcuts) >= 13, "ohne gefundene Kürzel prüft die Zählung nichts"
        assert all(
            entry.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut for entry in shortcuts
        ), "auf der Zeichenfläche bleiben die Kürzel kontextgebunden"

        panel.use_viewport()

        dead = [
            entry.key().toString()
            for entry in panel.findChildren(QShortcut)
            if entry.context() != Qt.ShortcutContext.WindowShortcut
        ]
        assert not dead, f"feuern im Viewport-Modus nie: {dead}"
    finally:
        panel.deleteLater()


def test_no_two_active_shortcuts_collide_while_sketching(qt_app: QApplication) -> None:
    """Der Skizzenmodus legt zehn Tasten dazu, und fünf davon sind schon vergeben.

    ``test_no_two_shortcuts_in_the_window_collide`` misst das Fenster **ohne**
    Skizzenmodus — dann existiert das Panel nicht, und seine Kürzel auch
    nicht. Im Modus kommen `L R C A D T O X P S` hinzu, seit dem Schnitt
    (§30.1, P4) an ``WindowShortcut``: Der Fokus liegt im Viewport, und ein
    Kürzel, das nur im unsichtbaren Zeichenbereich feuert, feuert nie.

    **Gezählt wird, was aktiv ist, nicht was registriert ist** — und das ist
    hier der ganze Unterschied. Registriert kollidieren fünf Tasten: `1`, `2`
    und `3` mit *Massiv*, *Massiv mit Kanten* und *Drahtgitter*, `Strg+Z` mit
    *Rückgängig*, `Pos1` mit *Alles einpassen*. Gemessen ist bei jeder genau
    **eine** Seite aktiv, weil die Fensteraktionen im Skizzenmodus gesperrt
    sind. Ein gesperrtes Kürzel nimmt keiner Taste den Weg.

    Eine Zählung über die reine Registrierung hätte hier fünf Fehler gemeldet,
    die keine sind — und würde zugleich einen echten übersehen, sobald zwei
    *aktive* Kürzel aufeinandertreffen. Genau dafür steht dieser Test.
    """
    from PySide6.QtGui import QAction, QShortcut

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("sketch_extrude")

        aktiv: dict[str, list[str]] = {}
        for action in window.findChildren(QAction):
            if not action.isEnabled():
                continue
            for sequence in action.shortcuts():
                aktiv.setdefault(sequence.toString(), []).append(action.text() or "(ohne Text)")
        for shortcut in window.findChildren(QShortcut):
            if shortcut.isEnabled():
                aktiv.setdefault(shortcut.key().toString(), []).append("QShortcut")

        assert len(aktiv) > 40, "ohne aufgebautes Fenster prüft diese Zählung nichts"
        for taste in ("1", "2", "3"):
            assert taste in aktiv, f"die Ziffer {taste} wechselt im Skizzenmodus die Ebene"

        doppelt = {key: names for key, names in aktiv.items() if key and len(names) > 1}
        assert not doppelt, (
            f"zwei aktive Kürzel auf derselben Taste führen keine der beiden "
            f"Aktionen aus: {doppelt}"
        )
    finally:
        window.deleteLater()


def test_every_sketch_shortcut_is_named_somewhere_on_screen(qt_app: QApplication) -> None:
    """Eine Belegung, zu der kein sichtbares Ziel gehört, findet niemand (§19.2).

    Kürzel stehen neben ihrer Handlung, so lernt man sie nebenbei. Im
    Skizzenmodus heißt das: an einem Knopf der Leiste („Linie (L)"), im
    Eintrag des Ebenenfelds („Draufsicht (XY) — liegend (1)") oder im Text des
    Knopfs selbst („Abstand  D").

    Gemessen am gebauten Fenster war von fünfzehn Kürzeln genau **eines**
    nirgends genannt: `Strg+Z`. Sein Knopf stand da, mit Bild und Tooltip
    „Rückgängig" — und ohne die Taste, während *Einpassen* zwei Zeilen darüber
    sein `Pos1` nennt und der Kommentar dazwischen genau diese Regel zitiert.

    **Was der Test ausnimmt und warum:** `Strg++`, `Strg+-` und die
    Tabulatorkürzel gehören dem **Fenster** und nicht der Skizze — Zoom und
    Reiterwechsel gelten überall, und ihr sichtbarer Weg ist der Menüeintrag.
    Sie hier zu verlangen hieße, jede Skizzenleiste müsste die halbe
    Menüleiste wiederholen.
    """
    from PySide6.QtGui import QShortcut
    from PySide6.QtWidgets import QAbstractButton, QComboBox

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("sketch_extrude")
        panel = window._sketch_panel
        assert panel is not None

        sichtbar = " || ".join(
            f"{knopf.text()} {knopf.toolTip()} {knopf.statusTip()}"
            for knopf in panel.findChildren(QAbstractButton)
        )
        for feld in panel.findChildren(QComboBox):
            sichtbar += " || " + " ".join(feld.itemText(i) for i in range(feld.count()))

        # Dem Fenster gehörig, nicht der Skizze: Zoom und Reiterwechsel.
        des_fensters = {"Ctrl++", "Ctrl+-", "Ctrl+Tab", "Ctrl+Shift+Tab"}
        tasten = {
            shortcut.key().toString()
            for shortcut in window.findChildren(QShortcut)
            if shortcut.isEnabled() and shortcut.key().toString()
        }
        eigene = {
            taste for taste in tasten if taste not in des_fensters and not taste.startswith("Alt+")
        }
        assert len(eigene) > 10, "ohne aufgebaute Leiste prüft diese Zählung nichts"

        stumm = [
            taste
            for taste in sorted(eigene)
            if f"({taste})" not in sichtbar and f" {taste}" not in sichtbar
        ]
        assert not stumm, (
            f"diese Kürzel des Skizzenmodus stehen nirgends an der Oberfläche: {stumm}"
        )
    finally:
        window.deleteLater()


def test_the_snap_step_is_the_grid_that_is_drawn(qt_app: QApplication) -> None:
    """Eine Zahl für beides — was man sieht, darauf fällt der Klick.

    Vorher waren es zwei: Gezeichnet wurden 5 mm, gefangen wurde auf 1 mm, und
    gemessen landeten vier von vier Klicks zwischen zwei sichtbaren Linien
    ((7,3 | −4,8) → (7,0 | −5,0)). Das Kästchen heißt „Am Raster fangen" und
    hat damit etwas versprochen, das nicht eintrat. Robert am 24.08.2026: „das
    fang sollte immer das raster sein."

    Geprüft wird ohne Plotter, also über ``follow_grid`` selbst — offscreen
    gibt es keine Kamera, an der ein Maßstab zu messen wäre (Entscheidung G).
    Dass die Weite im Fenster wirklich ankommt, prüft der Test darunter.
    """
    panel = SketchPanel()
    try:
        assert panel.snap_toggle.isChecked(), "an ist die Vorgabe"
        assert not panel.snap_is_pinned(), "ohne Eingabe folgt die Weite dem Zoom"

        for step in (5.0, 1.0, 20.0):
            panel.follow_grid(step)
            assert panel.canvas.snap_step == pytest.approx(step), (
                "der Fang nimmt die Weite des gezeichneten Rasters"
            )
            assert panel.snap_step.value_mm() == pytest.approx(step), (
                "und das Feld zeigt dieselbe Zahl"
            )

        # **Eine eingetippte Weite bleibt stehen.** Sonst nähme ihr der nächste
        # Zoomschritt die Wirkung, und das Feld wäre eine Anzeige, die aussieht
        # wie eine Einstellung.
        panel.snap_step.setValue(2.0)
        assert panel.snap_is_pinned()
        panel.follow_grid(50.0)
        assert panel.canvas.snap_step == pytest.approx(2.0), "die Eingabe gewinnt"
        assert panel.snap_step.value_mm() == pytest.approx(2.0)
    finally:
        panel.deleteLater()


def test_following_the_grid_does_not_look_like_typing(qt_app: QApplication) -> None:
    """``setValue`` feuert ``valueChanged`` — und das hieße „eingetippt".

    Ohne den Signalblocker in ``follow_grid`` hätte der **erste** Zoomschritt
    die Weite für immer festgenagelt: Er setzt das Feld, das Feld meldet eine
    Änderung, und der Slot deutet sie als Eingabe des Nutzers. Danach folgte
    nichts mehr dem Raster.
    """
    panel = SketchPanel()
    try:
        panel.follow_grid(5.0)
        panel.follow_grid(2.0)
        assert not panel.snap_is_pinned(), (
            "zweimal dem Raster gefolgt ist keine Eingabe des Nutzers"
        )
        assert panel.canvas.snap_step == pytest.approx(2.0)
    finally:
        panel.deleteLater()


def test_the_window_hands_the_grid_step_to_the_canvas(qt_app: QApplication) -> None:
    """Die Anwendung tut es, nicht bloß die Methode.

    ``follow_grid`` allein zu prüfen sagt nichts darüber, ob jemand sie ruft —
    und genau daran hing es: Die Weite entsteht in ``_redraw_sketch`` aus dem
    Kameramaßstab, und ohne die Weitergabe blieben Raster und Fang zwei Zahlen.

    Offscreen gibt es kein Bild, an dem sich ein Maßstab messen ließe; dann
    steht der Rückfallwert, und aus ihm folgt eine bestimmte Rasterweite. Genau
    die muss im Canvas ankommen — sonst hat die Kette ein Loch.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.sketch_editor import grid_step_for
    from app.ui.viewport import FALLBACK_SCALE

    erwartet = grid_step_for(FALLBACK_SCALE)
    assert erwartet > 0.0, "ohne eine Weite prüft dieser Test nichts"

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("sketch_extrude")
        panel = window._sketch_panel
        assert panel is not None
        assert panel.canvas.snap_step == pytest.approx(erwartet), (
            "die Weite aus dem Fenster kommt im Canvas an"
        )
        assert panel.snap_step.value_mm() == pytest.approx(erwartet), "und steht sichtbar im Feld"
    finally:
        window.deleteLater()


def test_a_typed_grid_step_reaches_the_picture(qt_app: QApplication) -> None:
    """Wer die Rasterweite eintippt, sieht sie — auch in der Ansicht.

    Gemeldet als „wenn ich das Raster anpasse ändert es sich im Viewport
    nicht". Die Kette endete am vorletzten Glied: ``_step_typed`` merkte sich
    die Weite und gab sie an die Zeichenfläche, und die zeichnete sich neu —
    unsichtbar, denn seit §30.1 P4 liegt das Bild im Viewport. Dessen Raster
    hängt an ``MainWindow._redraw_sketch``, das an ``sketchChanged`` hängt, und
    eine Rasterweite ist keine Zeichenänderung. Also blieb die alte Weite im
    Bild stehen, während Feld und Fang längst die neue trugen.

    Geprüft wird deshalb an der **Anwendung** und nicht an der Methode: Was
    zählt, ist die Zahl, die der Viewport zuletzt gezeichnet hat.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("sketch_extrude")
        panel = window._sketch_panel
        assert panel is not None
        vorher = window.viewport._sketch_step
        assert vorher > 0.0, "ohne ein gezeichnetes Raster prüft dieser Test nichts"

        gewuenscht = vorher * 5.0
        panel.snap_step.set_value_mm(gewuenscht)
        panel._step_typed()

        assert panel.canvas.snap_step == pytest.approx(gewuenscht), "der Fang folgt der Eingabe"
        assert window.viewport._sketch_step == pytest.approx(gewuenscht), (
            "und das gezeichnete Raster auch — sonst zeigt das Bild eine andere "
            f"Weite als das Feld ({window.viewport._sketch_step} statt {gewuenscht})"
        )
    finally:
        window.deleteLater()


def test_turning_the_snap_off_reaches_the_picture_too(qt_app: QApplication) -> None:
    """Derselbe Weg, andere Geste — der Haken ist die zweite Bedienung daran.

    Er lief durch dieselbe Methode und hatte deshalb dasselbe Loch. Geprüft
    wird hier, dass überhaupt ein Neuzeichnen stattfindet: Die Weite bleibt,
    was der Maßstab sagt, aber die Kette muss laufen.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("sketch_extrude")
        panel = window._sketch_panel
        assert panel is not None
        window.viewport._sketch_step = -1.0  # eine Zahl, die niemand zeichnet

        panel.snap_toggle.setChecked(False)

        assert not panel.canvas.snapping, "der Fang ist aus"
        assert window.viewport._sketch_step > 0.0, (
            "der Haken hat kein Neuzeichnen ausgelöst — die Ansicht steht auf einem "
            "Stand, den niemand mehr gesetzt hat"
        )
    finally:
        window.deleteLater()


def test_the_pointer_mark_sits_where_the_click_lands(qt_app: QApplication) -> None:
    """Die Marke zeigt den **gefangenen** Ort, nicht die rohe Zeigerlage.

    Der Kern von „die Klicks sind wo anders als ich klick": Gefangen wird auf
    das Raster, also fällt ein Klick bis zu einen halben Schritt neben den
    Mauszeiger — bei 2 mm Raster elf Bildpunkte, bei 10 mm sechzig. Der Canvas
    zeigt dafür seit je ein Kreuz; seit die Zeichnung im Viewport liegt, sieht
    das niemand mehr, denn dort rechnet er unsichtbar weiter.

    ``pointerMoved`` trägt deshalb ``pointer_target()`` nach außen — dieselbe
    Antwort, die auch die Statuszeile nennt. Den Fang im Viewport
    nachzurechnen wäre die zweite Zahl für dieselbe Sache.
    """
    panel = SketchPanel()
    try:
        panel.canvas.set_snapping(True, 10.0)
        panel.canvas.set_tool("point")
        gesehen: list[tuple[float, float]] = []
        panel.pointerMoved.connect(lambda x, y: gesehen.append((x, y)))

        panel.canvas.note_pointer(panel.canvas._to_screen(13.2, -7.4))

        assert gesehen, "die Bewegung kam nicht nach außen"
        assert gesehen[-1] == pytest.approx((10.0, -10.0)), (
            f"die Marke säße auf {gesehen[-1]}, der Klick landet auf (10.0, -10.0)"
        )

        # Und die Gegenprobe, die zugleich das Verhalten festhält: Beim
        # **Auswählen** fängt nichts, denn dort entsteht nichts — ein Klick
        # meint die Stelle, auf die er zeigt. Die Marke sitzt dann unter dem
        # Zeiger, und das ist richtig so.
        panel.canvas.set_tool("select")
        panel.canvas.note_pointer(panel.canvas._to_screen(13.2, -7.4))
        assert gesehen[-1] == pytest.approx((13.2, -7.4)), (
            "beim Auswählen ist die rohe Lage der Ort, an dem der Klick landet"
        )
    finally:
        panel.deleteLater()


def test_the_pointer_mark_is_a_cross_and_not_a_dot() -> None:
    """Zwei gekreuzte Strecken, quer zum Raster — und ohne Plotter prüfbar.

    Quer, weil die Marke meistens auf einer Rasterlinie sitzt: Ein
    achsparalleles Kreuz verschwände genau dort. Ein Punkt wiederum sähe aus
    wie ein gesetzter, und der Unterschied zwischen „hier ist etwas" und „hier
    entstünde etwas" hinge allein an der Farbe (Regel 18).
    """
    from app.core.types import PlaneFrame
    from app.ui.viewport import sketch_cursor

    frame = PlaneFrame(
        origin=(0.0, 0.0, 0.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    )
    segments = sketch_cursor(frame, (10.0, -10.0), 2.0)

    assert len(segments) == 2, "ein Kreuz sind zwei Strecken"
    for start, end in segments:
        assert start[0] != pytest.approx(end[0]), "eine achsparallele Strecke liegt im Raster"
        assert start[1] != pytest.approx(end[1]), "eine achsparallele Strecke liegt im Raster"
        assert start[2] == pytest.approx(0.0) and end[2] == pytest.approx(0.0), (
            "die Marke liegt in der Ebene, nicht darüber"
        )
    assert not sketch_cursor(frame, (0.0, 0.0), 0.0), "ohne Größe gibt es nichts zu zeichnen"


def test_a_placed_point_is_not_quieter_than_the_pointer_mark() -> None:
    """Was schon da ist, darf nicht schwächer aussehen als was erst entsteht.

    Der gesetzte Punkt stand auf sechs Bildpunkten, die Fangmarke daneben
    spannt zwanzig. Im Bild las sich das umgekehrt zur Sache: Ein Punkt ist
    ein Ding in der Zeichnung, die Marke nur ein Zeiger — und der Zeiger war
    das Auffälligere. Gesehen an der Aufnahme, nicht an einer Zahl.

    Geprüft wird das **Verhältnis** und nicht die Größe: Welche Zahl richtig
    ist, entscheidet das Auge und darf sich ändern; dass der Punkt dabei nicht
    wieder unter die Marke rutscht, entscheidet dieser Test.
    """
    from app.ui.viewport import CURSOR_PIXELS, SKETCH_POINT_PIXELS

    assert SKETCH_POINT_PIXELS >= CURSOR_PIXELS, (
        f"ein gesetzter Punkt misst {SKETCH_POINT_PIXELS} Bildpunkte, die Marke für den "
        f"nächsten Klick spannt {CURSOR_PIXELS * 2} — dann ist das Vorhandene das Leisere"
    )


def test_a_typed_grid_step_can_be_given_back(qt_app: QApplication) -> None:
    """Die eingetippte Weite war eine Einbahnstraße.

    ``_pinned_step`` wurde gesetzt und nie gelöst: Wer einmal eine Weite
    eintippte, sah bis zum Verlassen des Skizzenmodus kein mitwachsendes
    Raster mehr — herausgezoomt eine Fläche aus Linien, hineingezoomt vier
    Linien im Bild. Die Null im Feld heißt „Automatisch" und gibt sie zurück.

    Geprüft wird beides, denn eine Richtung allein wäre die halbe Zusage.
    """
    panel = SketchPanel()
    try:
        assert not panel.snap_is_pinned(), "ohne Eingabe folgt die Weite dem Zoom"

        panel.snap_step.set_value_mm(7.0)
        panel._step_typed()
        assert panel.snap_is_pinned(), "eine eingetippte Weite bleibt stehen"
        assert panel.canvas.snap_step == pytest.approx(7.0)

        panel.snap_step.set_value_mm(0.0)
        panel._step_typed()
        assert not panel.snap_is_pinned(), (
            "ganz herunter gedreht muss die Weite wieder dem Zoom folgen — sonst "
            "gibt es keinen Weg zurück"
        )

        # Und die Weite des Maßstabs kommt wieder an: ``follow_grid`` schreibt
        # sie in Feld und Fang, sobald sie nicht mehr festgehalten wird.
        panel.follow_grid(2.5)
        assert panel.canvas.snap_step == pytest.approx(2.5)
        assert panel.snap_step.value_mm() == pytest.approx(2.5)
    finally:
        panel.deleteLater()


def test_the_grid_field_offers_its_way_back_in_words(qt_app: QApplication) -> None:
    """Der Rückweg steht im Feld, nicht nur im Verhalten.

    Ein Sonderwert, den niemand sieht, ist keiner: Qt zeigt ihn am Minimum,
    also muss das Minimum null sein und der Text dort stehen.
    """
    panel = SketchPanel()
    try:
        assert panel.snap_step.minimum() == pytest.approx(0.0), (
            'ohne eine Null am unteren Ende gibt es keinen Platz für „Automatisch"'
        )
        assert panel.snap_step.specialValueText(), "der Rückweg ist unbeschriftet"
    finally:
        panel.deleteLater()


def test_the_pointer_mark_does_not_survive_a_change_of_plane(qt_app: QApplication) -> None:
    """Eine Marke gehört der Ebene, auf der sie liegt.

    ``clear_sketch`` lässt sie absichtlich stehen — sie hängt an der Maus und
    nicht an der Zeichnung, und mitgeräumt flackerte sie bei jedem Strich.
    Genommen wird sie deshalb in ``set_sketching``, und zwar **bei jedem**
    Aufruf und nicht nur beim Ende des Modus: Ein Ebenenwechsel geht durch
    dieselbe Methode mit einem neuen Rahmen. Ohne das schwebte die alte Marke
    auf der vorigen Ebene im Raum, bis die Maus sich das nächste Mal bewegte —
    wer über die Ziffern wechselt und die Hand stillhält, sah genau das.

    Geprüft wird die Verdrahtung und nicht der Actor: Offscreen gibt es keinen
    Plotter, dort entsteht nie eine Marke, und ein Test über eine leere Liste
    wäre immer grün.
    """
    from app.core.types import PlaneFrame
    from app.ui.viewport import Viewport

    frames = [
        PlaneFrame(
            origin=(0.0, 0.0, hoehe),
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 1.0, 0.0),
            normal=(0.0, 0.0, 1.0),
        )
        for hoehe in (0.0, 10.0)
    ]
    geraeumt: list[object] = []
    viewport = Viewport()
    try:
        viewport.show_sketch_cursor = geraeumt.append  # type: ignore[method-assign]

        viewport.set_sketching(frames[0])
        viewport.set_sketching(frames[1])
        viewport.set_sketching(None)

        assert geraeumt == [None, None, None], (
            "jeder Wechsel der Ebene muss die Marke nehmen, nicht nur das Ende des "
            f"Modus — geräumt wurde {geraeumt}"
        )
    finally:
        viewport.deleteLater()


def test_the_finest_grid_step_survives_the_way_back(qt_app: QApplication) -> None:
    """Die Null durfte hinein, ohne die Untergrenze mitzunehmen.

    Qt setzt den Sonderwert „Automatisch" immer auf das Minimum des Feldes,
    also musste dieses von 0,05 auf null. Damit war die feinste Weite offen,
    und bei zwei Nachkommastellen nahm das Feld 0,01 mm an — ein Fang, den kein
    Drucker auflöst. Sie gilt weiter, nur jetzt beim Eintippen.

    Angehoben und nicht abgelehnt: Ein Feld, das eine Eingabe verschluckt, ohne
    es zu zeigen, ist schlimmer als eines, das sie berichtigt.
    """
    from app.ui.sketch_editor import LEAST_SNAP_MM

    panel = SketchPanel()
    try:
        panel.snap_step.set_value_mm(0.01)
        panel._step_typed()
        assert panel.snap_step.value_mm() == pytest.approx(LEAST_SNAP_MM), (
            f"0,01 mm blieb stehen — das Feld nimmt Weiten unter {LEAST_SNAP_MM} mm an"
        )
        assert panel.canvas.snap_step == pytest.approx(LEAST_SNAP_MM), "und der Fang folgt"
        assert panel.snap_is_pinned(), "eine angehobene Weite ist trotzdem eine gewählte"

        # Die Null bleibt, was sie ist — sonst hätte die Untergrenze den Weg
        # zurück wieder zugemauert.
        panel.snap_step.set_value_mm(0.0)
        panel._step_typed()
        assert not panel.snap_is_pinned(), "die Null bleibt der Weg zurück"
    finally:
        panel.deleteLater()


def test_a_pointer_step_that_changes_nothing_does_not_redraw(qt_app: QApplication) -> None:
    """Die Marke zeichnet nur, wenn sie sich bewegt.

    Ein Neuzeichnen der Szene kostet gemessen 6,9 ms; bei sechzig
    Mausereignissen in der Sekunde wären das 41 % eines Kerns im
    Qt-Hauptthread. Weil die Marke am **gefangenen** Ort sitzt, ändert sie sich
    zwischen zwei Rasterpunkten nicht — bei 2 mm Raster rund vierundzwanzig
    Bildpunkte Mausweg je Sprung. Gemessen fiel der Normalfall damit von
    6,9 ms auf 0,004.

    Gezählt werden die Zeichenaufrufe: Offscreen entsteht keine Marke, also
    prüft ein Test über Actors nichts.
    """
    from app.core.types import PlaneFrame
    from app.ui.viewport import Viewport

    frame = PlaneFrame(
        origin=(0.0, 0.0, 0.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    )
    viewport = Viewport()
    try:
        viewport._sketch_frame = frame
        viewport.plotter = _StillPlotter()  # type: ignore[assignment]
        # Der Maßstab kommt aus dem Renderer, den es offscreen nicht gibt —
        # geprüft wird hier die Sparsamkeit und nicht seine Messung.
        viewport.pixels_per_mm = lambda _frame: 10.0  # type: ignore[method-assign]
        gezeichnet: list[int] = []
        viewport._draw = lambda: gezeichnet.append(1)  # type: ignore[method-assign]

        viewport.show_sketch_cursor((10.0, 10.0))
        erste = len(gezeichnet)
        for _ in range(20):
            viewport.show_sketch_cursor((10.0, 10.0))
        assert len(gezeichnet) == erste, (
            f"zwanzig Zeigerschritte auf demselben Rasterpunkt haben "
            f"{len(gezeichnet) - erste} Mal gezeichnet"
        )

        viewport.show_sketch_cursor((12.0, 10.0))
        assert len(gezeichnet) > erste, "ein echter Sprung muss zeichnen"
    finally:
        viewport.plotter = None  # type: ignore[assignment]
        viewport.deleteLater()


class _StillPlotter:
    """Gerade so viel Plotter, wie die Fangmarke anfasst.

    Offscreen gibt es keinen, und was hinter dieser Wache liegt, prüft sonst
    niemand — dieselbe Bauart wie die Attrappe in ``tests/test_cursors.py``.
    """

    def add_mesh(self, mesh: object, **_: object) -> object:
        return mesh

    def remove_actor(self, actor: object, **_: object) -> None:
        return None


def test_fitting_the_view_says_what_it_fitted(qt_app: QApplication) -> None:
    """Der Knopf *Einpassen* muss die Ansicht erreichen, nicht nur sich selbst.

    Seit die Skizze im Viewport liegt (P4), ist die Zeichenfläche unsichtbar:
    ``fit_view`` setzte einen Maßstab, den niemand mehr sieht. Gemessen am
    25.08.2026 stand die Kamera vor und nach dem Druck auf derselben Stelle,
    während eine Zeichnung von 300 mm zu drei Vierteln außerhalb des Bildes
    lag — ein Knopf, der genau dagegen da ist.

    Geprüft wird die **Rechnung**, nicht das Bild: Offscreen gibt es keinen
    Plotter, und ein Test über die Kamera wäre dort grün, weil er nichts tut
    (Konzept „Skizze im Raum", Entscheidung G). Was hier zählt, ist, dass die
    Fläche die Werte überhaupt nach außen gibt.
    """
    panel = SketchPanel(sketch_to_text(shapes.rectangle(120.0, 60.0)))
    try:
        gemeldet: list[tuple[float, float, float, float]] = []
        panel.viewFitted.connect(lambda *werte: gemeldet.append(werte))

        panel.canvas.fit_view()

        assert gemeldet, "die Einpassung erreicht die Ansicht nicht"
        x, y, span_x, span_y = gemeldet[-1]
        assert (x, y) == pytest.approx((0.0, 0.0)), "ein mittiges Rechteck ist mittig"
        assert span_x == pytest.approx(120.0), "die Breite der Zeichnung"
        assert span_y == pytest.approx(60.0), "ihre Höhe"
    finally:
        release = getattr(type(panel), "release", None)
        if release is not None:
            release(panel)
        panel.deleteLater()


def test_the_window_listens_when_the_sketch_fits_itself() -> None:
    """Und das Fenster hört zu — sonst endet die Kette am vorletzten Glied.

    Am Quelltext geprüft und nicht am laufenden Fenster: Der Skizzenmodus
    braucht ein Ergebnis, einen Plotter und ein Beispielprojekt, und ein Test,
    der sich das alles baut, prüft am Ende die Attrappen. Was hier fehlen kann,
    ist eine einzige Zeile — dass jemand das Signal anschließt.
    """
    quelle = (Path(__file__).resolve().parents[1] / "app" / "ui" / "main_window.py").read_text(
        encoding="utf-8"
    )

    assert "panel.viewFitted.connect(self._fit_sketch_view)" in quelle, (
        "das Fenster verbindet die Einpassung nicht"
    )
    assert "def _fit_sketch_view(" in quelle, "und hätte auch keinen Empfänger dafür"
    assert "show_span_on_plane" in quelle, "der Empfänger erreicht die Ansicht nicht"


def test_fitting_keeps_the_camera_square_to_the_plane() -> None:
    """Die Kamera schaut senkrecht auf die Ebene — auch wenn die nicht im Nullpunkt liegt.

    ``show_span_on_plane`` verschiebt die Kamera auf die Mitte der Zeichnung
    und behält dabei ihren Abstand. Der Versatz dafür ist ``position - focus``,
    und beides kommt aus ``camera_for_plane``; wer stattdessen gegen (0, 0, 0)
    rechnet, addiert den Ursprung der Ebene ein zweites Mal.

    Der Fall, an dem es auffällt, ist eine Skizze auf einer Deckfläche: Dort
    liegt der Ursprung bei z = 40, und die Kamera blickt schräg. Auf der
    Grundebene — dem einzigen Fall, den die erste Messung kannte — ist der
    Fehler unsichtbar.
    """
    frame = PlaneFrame(
        origin=(12.0, -8.0, 40.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    )
    mitte = (5.0, 3.0)
    abstand = 200.0

    kamera, welt, _up, _scale = camera_for_span(frame, mitte, (40.0, 20.0), abstand, 0.5)

    blick = tuple(k - w for k, w in zip(kamera, welt, strict=True))
    normale = image_normal(frame)

    # Die Blickrichtung ist die Ebenennormale, mal dem Abstand — kein Rest
    # daneben. Ein Versatz gegen den Weltursprung ergäbe hier (17, -5, 240)
    # statt (0, 0, 200).
    for gemessen, erwartet in zip(blick, (n * abstand for n in normale), strict=True):
        assert gemessen == pytest.approx(erwartet, abs=1e-9), f"die Kamera blickt schräg: {blick}"

    assert welt == pytest.approx((17.0, -5.0, 40.0)), "die Mitte liegt in der Ebene"

    # **Und der Ausschnitt fasst die breite Seite mit.** ``parallel_scale`` ist
    # die halbe sichtbare Höhe; eine Zeichnung, die breiter ist als hoch, passt
    # nur hinein, wenn ihre Breite über das Seitenverhältnis hineingerechnet
    # wird. Der erste Testfall hatte beide Seiten gleich groß gewählt und
    # konnte den Unterschied deshalb nicht sehen.
    _p, _w, _u, breit = camera_for_span(frame, mitte, (100.0, 20.0), abstand, 0.5)
    assert breit == pytest.approx(25.0 * FIT_ROOM), "die Breite bestimmt den Ausschnitt"

    _p, _w, _u, hoch = camera_for_span(frame, mitte, (40.0, 60.0), abstand, 0.5)
    assert hoch == pytest.approx(30.0 * FIT_ROOM), "und sonst die Höhe"


def test_a_camera_move_redraws_the_grid_in_the_scene(qt_app: QApplication) -> None:
    """Die dritte Kante: Kamera → Raster (§30.1, P4).

    Feld → Bild läuft über ``sketchChanged``, Bild → Feld über
    ``follow_grid`` — aber Rad, Drehzug und Einpassen änderten den Maßstab,
    ohne dass irgendwer neu zeichnete: Das Raster zeigte die Weite vom
    Betreten, und erst der nächste Strich ließ es springen. Gemeldet von
    Robert am 26.08.2026 („die Gitterlinien sollten genau das Raster sein").

    ``Viewport.cameraMoved`` ist das Signal dafür; dieser Test prüft den
    **Anschluss** (§35): Nach dem Betreten zeichnet ein Kameraschritt die
    Szene neu, nach dem Verlassen ist die Verbindung gelöst — sonst
    zeichnete jede Kamerabewegung im Normalbetrieb eine Skizze, die es
    nicht mehr gibt.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.show()
        window._show_start_screen(False)
        window.start_sketch("sketch_extrude")
        qt_app.processEvents()
        assert window._sketch_panel is not None, "ohne offene Skizze prüft dieser Test nichts"

        # ``show_sketch`` schreibt die gezeichnete Weite **vor** der
        # Plotter-Wache (offscreen gibt es keinen) — sie ist damit der eine
        # messbare Beleg, dass wirklich neu gezeichnet wurde.
        window.viewport._sketch_step = -1.0
        window.viewport.cameraMoved.emit()
        qt_app.processEvents()
        assert window.viewport._sketch_step > 0.0, (
            "Ein Kameraschritt muss das Raster neu zeichnen — die Verbindung aus start_sketch fehlt"
        )

        window.finish_sketch(keep=False)
        qt_app.processEvents()
        # ``finish_sketch`` hat die Verbindung gelöst; ein zweiter Versuch
        # findet nichts mehr. PySide meldet das als ``RuntimeWarning``
        # („Failed to disconnect"), nicht als ``RuntimeError`` — und
        # ``filterwarnings = error`` machte daraus einen ``SystemError``
        # mitten im C-Aufruf. ``pytest.warns`` fängt sie als das, was sie
        # ist: der Beleg, dass nach dem Verlassen niemand mehr zeichnet.
        with pytest.warns(RuntimeWarning):
            window.viewport.cameraMoved.disconnect(window._redraw_sketch)
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_an_empty_sketch_still_changes_its_plane(qt_app: QApplication) -> None:
    """Vor dem ersten Strich legt die Wahl die Ebene fest — wie in jedem CAD.

    Das ist die Hälfte, die immer richtig war, und sie muss bleiben: Wer die
    Ebene wählt, bevor er zeichnet, sagt damit, wo die Skizze liegen soll.
    """
    canvas = SketchCanvas()
    assert not canvas.sketch.elements, "der Test setzt eine leere Skizze voraus"

    canvas.set_plane("plane:yz")

    assert canvas.sketch.plane == "plane:yz", "die leere Skizze zieht um"
    assert canvas.view_plane == "plane:yz", "und die Kamera sieht dorthin"
    assert canvas.view_note() == "", "beide sind dasselbe — nichts zu erklären"


def test_a_drawn_sketch_stays_where_it_was_drawn(qt_app: QApplication) -> None:
    """Der erste Strich nagelt die Ebene fest; danach dreht die Wahl die Ansicht.

    **Robert hat es zweimal gemeldet** — am 24.08.2026 („bei draufsicht,
    seitenansicht usw sieht man auch keinen unterschied") und am 27.08. wieder,
    mit zwölf Kreisen, die in allen drei Ansichten an derselben
    Bildschirmstelle standen.

    Der Grund war nicht die Kamera, die schwenkt seit P4. Es war die Zeichnung:
    Die 2D-Zahlen blieben, der Ort im Raum wanderte mit der Ebene — ein Punkt
    bei (10 | 5) liegt in der Draufsicht bei (10, 5, 0) und in der
    Vorderansicht bei (10, 0, 5). Weil die Kamera mitging, sah jede Ansicht
    gleich aus, und die Frage „wo liegt das im Raum" blieb unbeantwortbar.
    """
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    assert canvas.sketch.plane == "plane:xy", "gezeichnet wird auf der Vorgabe"

    canvas.set_plane("plane:yz")

    assert canvas.sketch.plane == "plane:xy", "die Zeichnung bleibt, wo sie liegt"
    assert canvas.view_plane == "plane:yz", "nur die Blickrichtung wechselt"
    assert canvas.view_note(), "und ein Satz sagt, warum man jetzt die Kante sieht"


def test_the_note_names_both_the_view_and_the_plane(qt_app: QApplication) -> None:
    """Der Satz muss beide Seiten nennen, sonst erklärt er nichts.

    „Sie sehen die Zeichnung von der Seite" allein ließe offen, wo weiter
    gezeichnet wird — und genau das ist die Frage, die als Nächstes kommt.
    """
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    canvas.set_plane("plane:yz")

    note = canvas.view_note()
    assert "Seite" in note, f"die Blickrichtung fehlt: {note}"
    assert "Draufsicht" in note, f"die Zeichenebene fehlt: {note}"


def test_turning_the_view_writes_no_step(qt_app: QApplication) -> None:
    """Drehen ist kein Bearbeiten — der Verlauf bleibt, wie er ist.

    Zwei getrennte Signale, weil es zwei Sachen sind. Wer die Blickrichtung
    über ``sketchChanged`` meldete, schriebe bei jedem Drehen einen Schritt
    ins Dokument.
    """
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    before = canvas.sketch

    changes: list[int] = []
    views: list[str] = []
    canvas.sketchChanged.connect(lambda: changes.append(1))
    canvas.viewPlaneChanged.connect(views.append)
    canvas.set_plane("plane:xz")

    assert canvas.sketch is before, "die Skizze selbst ist unberührt"
    assert changes == [], "kein Dokumentwechsel für einen Blickwechsel"
    assert views == ["plane:xz"], f"aber die Ansicht meldet sich: {views}"


def test_the_note_reaches_the_label_beside_the_plane_field(qt_app: QApplication) -> None:
    """Gesetzt heißt nicht gezeigt — der Satz muss im Fenster stehen.

    Ein Rückgabewert, den niemand anzeigt, ist so still wie kein Satz. Geprüft
    wird deshalb am Beschriftungsfeld neben der Ebenenwahl, und über den Weg,
    den auch der Nutzer nimmt: die Wahl im Feld, nicht die Methode dahinter.
    """
    panel = SketchPanel()
    panel.canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    before = panel.layer_note.text()

    assert panel.choose_plane("plane:yz"), "die Grundebene steht immer zur Wahl"

    after = panel.layer_note.text()
    assert after != before, "der Satz neben der Ebenenwahl hat sich nicht gerührt"
    assert "Seitenansicht" in after, f"die Blickrichtung fehlt: {after}"
    assert "Draufsicht" in after, f"die Zeichenebene fehlt: {after}"
    assert panel.canvas.sketch.plane == "plane:xy", "und gezeichnet wird weiter dort"


# --- Was die Zahl bedeutet, und was ein Knopf tut ----------------------------


def test_the_line_translates_its_number_into_a_consequence(qt_app: QApplication) -> None:
    """„12 Freiheitsgrade sind noch frei" sagt einem Anfänger nichts.

    Weder ob das gut oder schlecht ist, noch was zu tun wäre. Die Zahl bleibt
    stehen — für den Könner ist sie richtig —, und dahinter steht ein Satz, der
    sie in eine Folge übersetzt. Gemeldet am 27.08.2026 als Teil von „mach den
    Skizzenmodus perfekt zum leichten Zeichnen für Anwender ohne große
    CAD-Kenntnisse".
    """
    canvas = SketchCanvas()
    canvas.insert_shape(shapes.rectangle(40.0, 20.0))

    line = canvas.status_text()
    assert "Freiheitsgrade" in line or "Freiheitsgrad" in line, "die Zahl bleibt: " + line
    assert canvas.outline_advice() in line, "und der Satz steht dahinter: " + line
    assert "Körper" in canvas.outline_advice(), canvas.outline_advice()


def test_an_open_outline_says_what_is_missing(qt_app: QApplication) -> None:
    """Der Umriss ist die härtere Bedingung, also nennt der Satz ihn.

    Ohne geschlossenen Umriss scheitert jede der fünf Erzeugungsarten; ein
    Satz über Maße wäre dort ein Rat zur falschen Sache.
    """
    canvas = SketchCanvas()
    canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))

    said = canvas.outline_advice()
    assert "geschlossen" in said, said
    assert said in canvas.status_text()


def test_a_determined_outline_says_that_nothing_moves_any_more(qt_app: QApplication) -> None:
    """Drei Lagen, drei Sätze — und der dritte ist nicht der zweite.

    Ohne die Unterscheidung stünde „Maße legen fest, was nicht mehr wackeln
    soll" auch an einer Skizze, in der nichts mehr wackelt: ein Rat zu einer
    Handlung, die schon getan ist.
    """
    # Gezeichnet: geschlossen, aber ohne Maße — vier Linien, deren Ecken sich
    # nur berühren.
    drawn = SketchCanvas()
    for start, end in (
        ((0.0, 0.0), (30.0, 0.0)),
        ((30.0, 0.0), (30.0, 20.0)),
        ((30.0, 20.0), (0.0, 20.0)),
        ((0.0, 20.0), (0.0, 0.0)),
    ):
        drawn.add_element("line", (start, end))
    assert drawn.outline, "vier Linien im Ring sind geschlossen"
    assert drawn.solved is not None and drawn.solved.free_dof > 0, "und sie wackeln noch"

    # Eingefügt: eine Grundform bringt ihre Maße mit und ist bestimmt.
    inserted = SketchCanvas()
    inserted.insert_shape(shapes.rectangle(40.0, 20.0))
    assert inserted.solved is not None and inserted.solved.free_dof == 0

    assert drawn.outline_advice() != inserted.outline_advice(), (
        "ein bestimmter Umriss sagt etwas anderes als ein wackelnder"
    )
    assert "Maße legen fest" in drawn.outline_advice(), drawn.outline_advice()
    assert "nicht mehr wackeln" in inserted.outline_advice(), inserted.outline_advice()


def test_every_constraint_says_what_it_does(qt_app: QApplication) -> None:
    """Zu jeder Bedingung gehört ein Satz über ihre Wirkung.

    Die Gegenprobe zu ``_needs_phrase``: Der sagt, was ausgewählt sein muss,
    dieser sagt, was danach gilt. „Tangential" ist ein Wort, das jeder aus
    einem CAD kennt und niemand sonst.
    """
    from app.ui.sketch_editor import _NEEDS, _does_phrase

    said = {kind: _does_phrase(kind) for kind in _NEEDS}
    for kind, phrase in said.items():
        assert phrase, kind
        assert phrase != _constraint_label(kind), f"{kind} wiederholt nur seinen Namen"
    assert len(set(said.values())) == len(said), "zehn Bedingungen, zehn verschiedene Sätze"


def test_the_constraint_buttons_carry_both_halves(qt_app: QApplication) -> None:
    """Am Knopf steht, was er bewirkt **und** was ihm fehlt.

    Vorher stand dort nur die zweite Hälfte: Wer das Wort nicht kennt, wusste
    danach, was er anklicken muss, und immer noch nicht, wozu.
    """
    from app.ui.sketch_editor import _does_phrase, _needs_phrase

    panel = SketchPanel("", {})
    button = panel._constraint_buttons["tangent"]
    hint = button.toolTip()

    assert _does_phrase("tangent") in hint, hint
    assert _needs_phrase("tangent") in hint, hint


def test_the_constraint_list_explains_each_entry(qt_app: QApplication) -> None:
    """„Abstand 1,50 mm — Kreis 1" nennt Art, Maß und Ort, nicht die Wirkung.

    Der Hinweis trägt sie nach, aus derselben Quelle wie der Knopf — und die
    rohen Nummern bleiben darunter, denn wer eine Bedingung aus einer Meldung
    des Lösers sucht, sucht nach ihnen.
    """
    from app.ui.sketch_editor import _does_phrase

    panel = SketchPanel("", {})
    panel.canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
    panel.canvas.add_constraint("horizontal", (0, 1))
    panel._refresh_constraints()

    assert panel.constraint_list.count() == 1
    hint = panel.constraint_list.item(0).toolTip()
    assert _does_phrase("horizontal") in hint, hint
    assert "(0, 1)" in hint, hint


# --- Der Ziehgriff der Querschau (§30.1) -------------------------------------


def test_the_grip_is_offered_only_when_the_plane_is_seen_edge_on(qt_app: QApplication) -> None:
    """Robert am 27.08.2026: in der Draufsicht zeichnen, in der Seitenansicht
    nach oben ziehen.

    Genau dieser Zustand ist die Bedingung. In der Draufsicht bliebe die Geste
    dem Zeichnen im Weg: Ein Druck auf eine Umrisskante wäre dort mal ein
    Punkt, mal ein Zug.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("")
        panel = window._sketch_panel
        assert panel is not None
        panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))

        assert window._sketch_pull_offer() == "", "auf der Zeichenebene wird gezeichnet"

        panel.choose_plane("plane:xz")
        assert panel.canvas.view_plane != panel.canvas.sketch.plane, "die Querschau steht"
        assert window._sketch_pull_offer() == "ready"
    finally:
        window.finish_sketch(keep=False)
        window.close()
        window.deleteLater()


def test_an_open_outline_blocks_the_grip_with_a_reason(qt_app: QApplication) -> None:
    """Ein Griff, der stumm nichts tut, sagt nicht einmal, dass etwas nicht
    ging (Regel 17).

    Der Grund kommt aus derselben Quelle, die die Geste auch erlaubt — sonst
    verspricht der Satz in der Leiste etwas, was der Griff nicht hält.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("")
        panel = window._sketch_panel
        assert panel is not None
        panel.canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
        panel.choose_plane("plane:xz")

        said = window._sketch_pull_offer()
        assert said not in ("", "ready"), said
        assert "Umriss" in said, said
        assert said in window._sketch_hint.text(), "und er steht in der Leiste"
    finally:
        window.finish_sketch(keep=False)
        window.close()
        window.deleteLater()


def test_another_sketch_operation_keeps_its_own_dialog(qt_app: QApplication) -> None:
    """Wer den Modus für *Grundform drehen* betreten hat, meint keine Höhe.

    Der Griff gehört zu ``sketch_extrude``; ihn dort anzubieten hieße, die
    gewählte Operation stillschweigend zu tauschen.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("sketch_revolve")
        panel = window._sketch_panel
        assert panel is not None
        panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))
        panel.choose_plane("plane:xz")

        said = window._sketch_pull_offer()
        assert said != "ready", said
        assert str(REGISTRY.get("sketch_revolve").title) in said, said
    finally:
        window.finish_sketch(keep=False)
        window.close()
        window.deleteLater()


def test_the_bar_says_how_the_grip_works_once_it_is_available(qt_app: QApplication) -> None:
    """Ohne den Satz findet die Geste niemand.

    In der Querschau sieht der Umriss aus wie ein Strich, und dass man daran
    ziehen kann, sagt sonst allein der Mauszeiger — wenn man schon darüber ist.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("")
        panel = window._sketch_panel
        assert panel is not None
        panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))
        before = window._sketch_hint.text()
        assert "Am Umriss ziehen" not in before, before

        panel.choose_plane("plane:xz")
        after = window._sketch_hint.text()
        # **Gegen den ganzen Satz und nicht gegen „ziehen".** Der Grund, der
        # statt der Geste dasteht, heißt „Zum **Auf**ziehen fehlt der
        # geschlossene Umriss" und trägt dasselbe Wort: Mit einem Angebot, das
        # nie „ready" liefert, blieb der Test grün (gefunden von der
        # Review-Sitzung, 27.08.2026).
        assert "Am Umriss ziehen" in after, after
        assert "Zeichenebene" in after, "die Ebene bleibt in der Zeile stehen"
    finally:
        window.finish_sketch(keep=False)
        window.close()
        window.deleteLater()


def test_a_pulled_height_reaches_the_operation(qt_app: QApplication) -> None:
    """Der Zug endet als Operation mit **beiden** Werten.

    Die Skizze und die gezogene Höhe: Wer die Höhe im Dialog auf ihre Vorgabe
    zurückstellte, hätte die Geste weggeworfen und den Nutzer die Zahl zweimal
    angeben lassen.
    """
    from app.core.registry import OperationSpec
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    asked: list[tuple[str, dict[str, object]]] = []

    def note(spec: OperationSpec, given: dict[str, object] | None = None, **_rest: object) -> None:
        asked.append((spec.name, dict(given or {})))

    try:
        window.run_operation = note
        window.start_sketch("")
        panel = window._sketch_panel
        assert panel is not None
        panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))
        panel.choose_plane("plane:xz")

        window._on_sketch_pulled(17.5)

        assert len(asked) == 1, f"gemessen {asked}"
        name, given = asked[0]
        assert name == "sketch_extrude"
        assert given["height"] == pytest.approx(17.5)
        assert given["sketch"], "und die Zeichnung reist mit"
    finally:
        window.close()
        window.deleteLater()


def test_the_height_limits_come_from_the_schema(qt_app: QApplication) -> None:
    """Die Grenzen der Ansicht sind die der Operation.

    Abgeschrieben wären sie eine zweite Wahrheit, und die fiele erst auf, wenn
    der Dialog eine Zahl ablehnt, die der Griff gerade gezeigt hat.
    """
    from app.ui.main_window import PULL_FIELD, PULL_OP, pull_limits

    entry = next(item for item in REGISTRY.get(PULL_OP).params.spec() if item.name == PULL_FIELD)
    assert pull_limits() == (entry.minimum, entry.maximum)


def test_the_bar_line_follows_the_drawing_and_does_not_age(qt_app: QApplication) -> None:
    """Die Zeile über der Leiste darf nichts versprechen, was nicht mehr gilt.

    Gerufen wurde sie nur beim Betreten und beim Ebenenwechsel. Wer in der
    Querschau ein Rechteck hatte und eine lose Linie dazuzeichnete, las weiter
    „Am Umriss ziehen", während das Angebot schon „fehlt der geschlossene
    Umriss" sagte — zwei Aussagen über denselben Zustand (gefunden von der
    Review-Sitzung, 27.08.2026).
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("")
        panel = window._sketch_panel
        assert panel is not None
        panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))
        panel.choose_plane("plane:xz")
        assert "Am Umriss ziehen" in window._sketch_hint.text(), window._sketch_hint.text()

        # Eine lose Linie öffnet den Umriss — ab jetzt geht die Geste nicht.
        panel.canvas.add_element("line", ((60.0, 60.0), (80.0, 70.0)))
        assert not panel.canvas.outline, "der Umriss ist jetzt offen"

        after = window._sketch_hint.text()
        assert "Am Umriss ziehen" not in after, after
        assert window._sketch_pull_offer() in after, after
    finally:
        window.finish_sketch(keep=False)
        window.close()
        window.deleteLater()
