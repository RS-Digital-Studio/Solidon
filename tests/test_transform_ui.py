"""Die Bewegen-Leiste: drei Rollen, und was ihre Zahlen auslösen.

Geprüft wird der Weg vom Feld bis in den Verlauf — nicht, ob ein Widget
existiert. Die Leiste rechnet nichts; sie nennt eine registrierte Operation und
ihre Werte, und genau das ist die Zusage.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import as_mesh_data
from app.ui.labels import set_display_unit
from app.ui.main_window import MainWindow
from app.ui.transform_bar import TransformBar

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    """Ein Fenster wie in ``test_ui.py`` — aufgeräumt wird zentral in conftest."""
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    return MainWindow(Session(), UiSettings())


@pytest.fixture
def bar(qt_app: QApplication) -> TransformBar:
    """Eine Leiste ohne Fenster — für alles, was nur ihre Werte betrifft."""
    return TransformBar()


# --- Was eine Rolle auslöst -----------------------------------------------------


def test_each_role_names_its_own_operation(bar: TransformBar) -> None:
    """Drei Rollen, drei Operationen — und die Werte der sichtbaren Felder.

    Die Leiste entscheidet nichts über Geometrie (Regel 2). Was sie liefert,
    ist ein Name aus dem Register und ein Satz Werte; daraus macht das Fenster
    einen Schritt im Verlauf.
    """
    bar.dx.set_value_mm(12.0)
    bar.dy.set_value_mm(-3.5)
    bar.dz.set_value_mm(0.0)
    assert bar.draft() == ("translate_object", {"dx": 12.0, "dy": -3.5, "dz": 0.0})

    bar.role_buttons["rotate"].click()
    bar.axis.setCurrentIndex(0)
    bar.angle_value.setValue(45.0)
    assert bar.draft() == ("rotate_object", {"axis": "x", "angle": 45.0})

    bar.role_buttons["scale"].click()
    bar.factor.setValue(150.0)
    assert bar.draft() == ("scale_object", {"factor": 1.5})


def test_scaling_to_a_size_is_a_different_operation(bar: TransformBar) -> None:
    """„auf 120 %" und „auf 80 mm" sind für den Kunden dieselbe Handlung.

    Für den Kern sind es zwei Operationen. Der Umschalter ist der Grund, aus
    dem beide Felder hier liegen: Wer ein Teil auf ein Maß bringen will, soll
    das Maß eintippen können, statt den Faktor auszurechnen.
    """
    bar.role_buttons["scale"].click()
    bar.by_size.setChecked(True)
    bar.largest.set_value_mm(80.0)

    assert bar.draft() == ("fit_to_size", {"largest": 80.0})
    assert not bar.factor.isVisible() or not bar.isVisible()


def test_the_role_decides_which_fields_stand_there(bar: TransformBar) -> None:
    """Der Griff im Bild bleibt vollständig — nur die Zahlen wechseln."""
    assert bar.role() == "move"
    assert bar.fields.currentIndex() == 0

    bar.role_buttons["rotate"].click()
    assert bar.role() == "rotate"
    assert bar.fields.currentIndex() == 1

    bar.role_buttons["scale"].click()
    assert bar.role() == "scale"
    assert bar.fields.currentIndex() == 2


def test_every_role_button_says_what_it_does(bar: TransformBar) -> None:
    """Symbol **und** Wort, dazu ein Satz — verstanden, bevor man liest.

    Die drei Zeichen sind geeinigt (jeder Slicer führt sie), aber wer sie zum
    ersten Mal sieht, bekommt beides und lernt das Bild nebenbei. Der Satz
    steht im Tooltip und in der Statuszeile — zwei Kodierungen, nicht eine
    (Regel 18).
    """
    for key, button in bar.role_buttons.items():
        assert button.text(), f"{key}: kein Wort am Knopf"
        assert not button.icon().isNull(), f"{key}: kein Symbol"
        assert button.toolTip(), f"{key}: kein Satz im Tooltip"
        assert button.statusTip() == button.toolTip(), f"{key}: zwei Formulierungen"


def test_the_axis_box_has_a_name_a_screen_reader_can_read(bar: TransformBar) -> None:
    """Ein Etikett daneben steht im Layout, nicht im Barrierefreiheitsbaum.

    Ohne eigenen Namen meldet die Box sich als ``QComboBox(-)`` — gefunden im
    Torlauf einer anderen Sitzung, nicht hier: ``test_what_a_screen_reader_can_
    name`` in ``test_ui.py`` prüft das gebaute Fenster, dieser Test die Leiste
    für sich. Beide gehören zu derselben Zusage (Regel 18), und der hier fällt
    schneller.
    """
    assert bar.axis.accessibleName(), "die Achswahl hat keinen Namen"


def test_the_snap_still_works_behind_its_button(bar: TransformBar) -> None:
    """Der Fang ist umgezogen, nicht verschwunden.

    Er stand als vier Widgets in der Zeile und kostete dort mehr Breite als die
    drei Rollen zusammen — 397 von 1253 Punkten auf Französisch, davon 202 für
    die zwei Etiketten. Jetzt liegt er hinter einem Knopf.

    **Geprüft wird, dass er wirkt, nicht dass das Menü aufgeht.** Ein Popup,
    das sich öffnet und dessen Werte niemand mehr liest, wäre der teurere
    Fehler: Er sieht aus wie eine Verbesserung.
    """
    gemeldet: list[tuple[float, float]] = []
    bar.snappingChanged.connect(lambda grid, angle: gemeldet.append((grid, angle)))

    bar.grid.set_value_mm(2.5)
    assert bar.steps()[0] == pytest.approx(2.5)
    assert gemeldet and gemeldet[-1][0] == pytest.approx(2.5), "die Änderung kam nicht an"

    bar.angle.setValue(45.0)
    assert bar.steps() == (pytest.approx(2.5), pytest.approx(45.0))


def test_the_snap_button_says_what_it_is_without_a_word_on_it(bar: TransformBar) -> None:
    """Ein wortloser Knopf trägt seinen Namen an drei Stellen.

    Barrierefreiheitsbaum, Tooltip, Statuszeile — so steht es in
    ``oberflaeche.md``. Ohne das ist ein Symbol allein eine Vokabel, die
    niemand nachschlagen kann.
    """
    assert not bar.snap.text(), "der Knopf trägt ein Wort — dann gilt diese Regel nicht"
    assert bar.snap.accessibleName(), "kein Name im Barrierefreiheitsbaum"
    assert bar.snap.toolTip(), "kein Tooltip"
    assert bar.snap.statusTip() == bar.snap.toolTip(), "zwei Formulierungen für dasselbe"
    assert not bar.snap.icon().isNull(), "kein Symbol"
    assert bar.snap.menu() is not None, "der Knopf öffnet nichts"


# --- Die Einheit ----------------------------------------------------------------


def test_a_bar_driven_in_inches_still_hands_over_millimetres(bar: TransformBar) -> None:
    """Der Kern rechnet in Millimetern, gleich was angezeigt wird (Regel 6).

    **Keine Leiste war je in Zoll gefahren** — die Umschaltung war an ihren
    Anzeigen geprüft und an keiner Handlung. Genau dort lagen die drei Funde
    vom 27.08.2026, unter anderem ein Pinselradius, der als 0,1969 in der Szene
    ankam, wo 5 mm eingestellt waren.

    Ein Zoll-Wert, der ungerechnet in einen Draft liefe, wäre ein Teil um den
    Faktor 25,4 daneben — und kein Fehler, den jemand als Fehler sieht: Die
    Zahl im Feld stimmt ja.
    """
    set_display_unit("in")
    try:
        # Wie im Betrieb: Das Fenster stößt die Felder an, wenn die Einheit
        # wechselt (``_set_length_unit``). Ohne diesen Schritt stünde das Feld
        # noch in Millimetern, und der Test prüfte seinen eigenen Aufbau.
        bar.dx.refresh_unit()
        bar.largest.refresh_unit()
        bar.dx.setValue(1.0)  # ein Zoll, so wie der Kunde es tippt
        op, params = bar.draft()
        assert op == "translate_object"
        assert params["dx"] == pytest.approx(25.4), f"{params['dx']} statt 25,4 mm"

        bar.role_buttons["scale"].click()
        bar.by_size.setChecked(True)
        bar.largest.setValue(2.0)
        assert bar.draft()[1]["largest"] == pytest.approx(50.8)
    finally:
        set_display_unit("mm")


def test_the_angle_stays_degrees_in_every_unit(bar: TransformBar) -> None:
    """Ein Winkel in Zoll wäre keine Umschaltung, sondern ein Fehler."""
    bar.role_buttons["rotate"].click()
    bar.angle_value.setValue(30.0)

    set_display_unit("in")
    try:
        assert bar.draft()[1]["angle"] == pytest.approx(30.0)
    finally:
        set_display_unit("mm")


def test_no_element_of_the_bar_is_squeezed(window: MainWindow) -> None:
    """Jedes Element bekommt, was es verlangt — sonst ist eine Beschriftung weg.

    **Die Zusage ist metrik-unabhängig** und gilt deshalb auch offscreen, wo
    Qt keine Schrift hat: Ob ``width()`` einer Sprache 110 oder 228 Punkte
    misst, ist gleichgültig — gequetscht ist es, wenn es weniger bekommt als es
    will.

    **Gemessen wird mit geladenem Modell**, und das ist der Kern dieses Tests.
    Ohne eines zeigt das Fenster den Startbildschirm; die Leiste liegt dann in
    einem Zweig des Stapels, den niemand sieht, und ihre Kinder stehen auf drei
    Pixeln. Eine Messung dort meldet die Leiste als vollständig zerdrückt und
    misst in Wahrheit einen Zustand, den kein Kunde herstellt — genau so ist am
    30.08.2026 ein Fehlbefund entstanden.
    """
    window.resize(1600, 900)
    window.show()
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    window.tools.activate("transform")
    QApplication.processEvents()

    bar = window.transform_bar
    assert bar.isVisible(), "die Leiste liegt nicht im gezeigten Zweig — der Test misst nichts"

    squeezed = [
        f"{name}: {widget.width()} statt {widget.sizeHint().width()}"
        for name, widget in [
            *((key, button) for key, button in bar.role_buttons.items()),
            ("Felder", bar.fields),
            ("Anwenden", bar.apply),
            ("Fang", bar.snap),
        ]
        if widget.width() < widget.sizeHint().width()
    ]
    assert not squeezed, "gequetscht: " + ", ".join(squeezed)


def test_when_it_gets_tight_the_word_goes_and_the_symbol_stays(bar: TransformBar) -> None:
    """Ein halbes Wort ist schlechter als kein Wort.

    Ein Layout kürzt im Zweifel jeden Posten anteilig, und ein Knopf mit
    Beschriftung verliert dabei zuerst die Beschriftung — gemessen stand
    „Verschieben" mit 149 Punkten für 184 gewünschte da. Das Symbol allein ist
    hier zumutbar: Es bedeutet in jedem Slicer dasselbe, und der Name steht
    weiter im Tooltip, in der Statuszeile und im Barrierefreiheitsbaum.

    Geprüft wird über zwei Breiten und wieder zurück — die Umschaltung muss in
    **beide** Richtungen greifen. Ein Knopf, der sein Wort verliert und nie
    zurückbekommt, wäre der teurere Fehler.
    """
    bar.resize(2000, 40)
    bar.show()
    QApplication.processEvents()
    assert bar.roles_show_words(), "bei zweitausend Punkten ist Platz für das Wort"

    bar.resize(300, 40)
    QApplication.processEvents()
    assert not bar.roles_show_words(), "bei dreihundert steht das Wort noch da"
    for key, button in bar.role_buttons.items():
        assert button.toolTip(), f"{key}: ohne Wort und ohne Tooltip"
        assert button.accessibleName() or button.text(), f"{key}: kein Name mehr"

    bar.resize(2000, 40)
    QApplication.processEvents()
    assert bar.roles_show_words(), "das Wort kam nicht zurück"


# --- Der ganze Weg bis in den Verlauf -------------------------------------------


def test_a_typed_value_becomes_a_step_in_the_history(window: MainWindow) -> None:
    """Vom Feld bis in den Verlauf — der Weg, den ein Kunde geht.

    Nicht ``draft()`` allein: Was die Leiste liefert, muss auch als Schritt
    ankommen. Ein Wert, der eine Operation nennt, die das Fenster nicht
    anwendet, wäre ein Feld ohne Wirkung.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    window.object_tree.select_object(next(iter(result.scene.objects)))

    before = len(window.session.project.document.ops)
    window.transform_bar.dz.set_value_mm(5.0)
    window.transform_bar.apply.click()
    window.session.wait_for_idle()

    ops = [entry.op for entry in window.session.project.document.ops]
    assert len(ops) > before, "der Klick hat keinen Schritt erzeugt"
    assert ops[-1] == "translate_object", f"letzter Schritt: {ops[-1]}"


def test_typing_and_then_clicking_moves_the_part_once(window: MainWindow) -> None:
    """Tippen, dann auf „Anwenden" klicken — eine Bewegung, ein Schritt.

    **Der Weg, den jeder geht, und der einzige, den die Tests bisher nicht
    gingen.** Der Knopf nimmt beim Klick den Fokus (``StrongFocus``), und das
    Feld verliert ihn damit, bevor der Knopf wirkt. Hing das Anwenden am
    Verlassen des Feldes, wurde derselbe Wert zweimal angewandt: aus 5 mm
    wurden 10 mm, aus 90° wurden 180°, und zurück brauchte es zwei Strg+Z.

    Gefahren wird deshalb mit echtem Fokus und echtem Mausklick — ohne
    ``show()`` und ``activateWindow()`` vergibt Qt offscreen gar keinen Fokus,
    und dann prüft der Test genau das nicht, worum es geht.
    """
    window.resize(1600, 900)
    window.show()
    window.activateWindow()
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    window.object_tree.select_object(next(iter(result.scene.objects)))
    window.tools.activate("transform")
    QApplication.processEvents()
    # Danach noch einmal aktivieren: Beim Laden entsteht ein elternloser Knopf
    # (*Auf das Bett setzen*), der offscreen selbst zum aktiven Fenster wird —
    # und ein Feld in einem inaktiven Fenster bekommt keinen Fokus.
    window.activateWindow()
    QApplication.processEvents()

    vorher = len(window.session.project.document.ops)
    unterkante = min(
        as_mesh_data(entry.mesh).bounds.minimum[2] for entry in result.scene.objects.values()
    )

    feld = window.transform_bar.dz
    feld.setFocus()
    QApplication.processEvents()
    assert feld.hasFocus(), "ohne Fokus im Feld misst der Test den Fokusverlust nicht"
    feld.lineEdit().selectAll()
    QTest.keyClicks(feld.lineEdit(), "5")
    QTest.mouseClick(window.transform_bar.apply, Qt.MouseButton.LeftButton)
    window.session.wait_for_idle()

    ops = [entry.op for entry in window.session.project.document.ops]
    assert len(ops) == vorher + 1, (
        f"ein getippter Wert und ein Klick ergaben {len(ops) - vorher} Schritte: {ops[vorher:]}"
    )
    gehoben = min(
        as_mesh_data(entry.mesh).bounds.minimum[2]
        for entry in window.session.evaluate_now().scene.objects.values()
    )
    assert gehoben - unterkante == pytest.approx(5.0, abs=1e-6), (
        f"aus 5 mm wurden {gehoben - unterkante:.3f} mm — der Wert wirkte mehr als einmal"
    )

    window.session.undo()
    window.session.wait_for_idle()
    zurueck = min(
        as_mesh_data(entry.mesh).bounds.minimum[2]
        for entry in window.session.evaluate_now().scene.objects.values()
    )
    assert zurueck == pytest.approx(unterkante, abs=1e-6), (
        f"nach einem Undo steht das Teil bei {zurueck:.3f} statt {unterkante:.3f} mm"
    )


def test_the_return_key_still_applies_the_value(window: MainWindow) -> None:
    """Die Eingabetaste bleibt der kurze Weg — sie wirkt wie der Knopf.

    Die Gegenprobe zum Test darüber: Angewandt wird auf Return und auf den
    Knopf, nur nicht auf den Fokuswechsel dazwischen.
    """
    window.resize(1600, 900)
    window.show()
    window.activateWindow()
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    window.object_tree.select_object(next(iter(result.scene.objects)))
    window.tools.activate("transform")
    QApplication.processEvents()
    # Danach noch einmal aktivieren: Beim Laden entsteht ein elternloser Knopf
    # (*Auf das Bett setzen*), der offscreen selbst zum aktiven Fenster wird —
    # und ein Feld in einem inaktiven Fenster bekommt keinen Fokus.
    window.activateWindow()
    QApplication.processEvents()

    vorher = len(window.session.project.document.ops)
    feld = window.transform_bar.dz
    feld.setFocus()
    QApplication.processEvents()
    feld.lineEdit().selectAll()
    QTest.keyClicks(feld.lineEdit(), "5")
    QTest.keyClick(feld, Qt.Key.Key_Return)
    window.session.wait_for_idle()

    ops = [entry.op for entry in window.session.project.document.ops]
    assert ops[vorher:] == ["translate_object"], (
        f"die Eingabetaste ergab {ops[vorher:]} statt genau eines Schritts"
    )


def test_a_typed_angle_turns_the_group_around_one_common_point(
    window: MainWindow,
) -> None:
    """Der getippte Winkel nimmt denselben Bezugspunkt wie der Zug am Griff.

    Dass zwei markierte Teile sich als Gruppe drehen und nicht jedes um sich
    selbst, misst ``test_selection.py`` an der Geometrie. Hier geht es um den
    **zweiten Weg dorthin**: Was die Leiste in den Verlauf schreibt, muss den
    genannten Punkt genauso tragen. Sonst führen Ziehen und Tippen zu zwei
    verschiedenen Ergebnissen, und der Kunde hat keinen Anhalt, welches gilt.

    Der Sollwert ist nicht gerechnet, sondern abgelesen: Zwei gleiche Kästen,
    einer um 50 mm versetzt, haben ihre gemeinsame Mitte bei 25 mm. Eine Zahl,
    die aus dem Aufbau folgt und nicht aus dem Prüfling.
    """
    from app.core.scene.history import OperationDraft

    box = {"width": 10.0, "depth": 10.0, "height": 10.0}
    window.session.apply("Kasten", [OperationDraft(op="create_box", inputs=(), params=box)])
    window.session.wait_for_idle()
    window.session.apply("Kasten", [OperationDraft(op="create_box", inputs=(), params=box)])
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)

    ids = list(result.scene.objects)
    assert len(ids) == 2, f"der Aufbau braucht genau zwei Körper, es sind {len(ids)}"
    window.session.apply(
        "Danebenstellen",
        [OperationDraft(op="translate_object", inputs=(ids[1],), params={"dx": 50.0})],
    )
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())

    for row in range(window.object_tree.tree.topLevelItemCount()):
        window.object_tree.tree.topLevelItem(row).setSelected(True)
    assert len(window.object_tree.selected_objects()) == 2, (
        "ohne zwei markierte Körper misst der Test die Einzelfall-Vorgabe und "
        f"bliebe grün: markiert sind {window.object_tree.selected_objects()}"
    )

    window.transform_bar.role_buttons["rotate"].click()
    window.transform_bar.angle_value.setValue(90.0)
    window.transform_bar.apply.click()
    window.session.wait_for_idle()

    turns = [one for one in window.session.project.document.ops if one.op == "rotate_object"]
    assert turns, "der Klick hat keinen Drehschritt erzeugt"
    params = turns[-1].params
    assert params.get("about") == "point", (
        f"ohne genannten Punkt dreht jeder Körper um sich selbst: {params}"
    )
    assert params.get("pivot_x") == pytest.approx(25.0, abs=1e-6), (
        f"die gemeinsame Mitte zweier Kästen bei 0 und 50 liegt bei 25, "
        f"nicht bei {params.get('pivot_x')}"
    )


def test_one_body_typed_keeps_the_old_meaning(window: MainWindow) -> None:
    """Ein einzelner Körper dreht weiter um sich selbst — wie jede alte Datei.

    Die Gegenprobe zum Test darüber, und der Grund, warum der Bezugspunkt bei
    einem Körper leer bleibt: Stünde dort ein Punkt, bekäme jedes bestehende
    Projekt beim nächsten Dreh ein anderes Ergebnis als bisher.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    window.object_tree.select_object(next(iter(result.scene.objects)))

    window.transform_bar.role_buttons["rotate"].click()
    window.transform_bar.angle_value.setValue(90.0)
    window.transform_bar.apply.click()
    window.session.wait_for_idle()

    turns = [one for one in window.session.project.document.ops if one.op == "rotate_object"]
    assert turns, "der Klick hat keinen Drehschritt erzeugt"
    assert "about" not in turns[-1].params, (
        f"bei einem Körper gilt sein eigener Mittelpunkt: {turns[-1].params}"
    )


def test_turning_puts_the_part_back_on_the_bed(window: MainWindow) -> None:
    """Wer dreht, bekommt sein Teil aufgesetzt — und zwar wirklich.

    **Eine Drehung um X oder Y kippt den Körper**, und seine Unterseite liegt
    danach irgendwo: mal über der Platte, mal darunter. Wer dreht, will fast
    immer drucken, und ein Teil, das nicht aufliegt, druckt nicht.

    Gemessen wird an der Geometrie und nicht an der Zahl der Schritte: Ein
    zweiter Eintrag im Verlauf beweist nur, dass etwas passiert ist — die
    Zusage ist, dass die Unterseite danach auf null liegt.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    window.object_tree.select_object(next(iter(result.scene.objects)))

    window.transform_bar.role_buttons["rotate"].click()
    window.transform_bar.to_bed.setChecked(True)
    window.transform_bar.axis.setCurrentIndex(0)  # um X, damit es kippt
    window.transform_bar.angle_value.setValue(45.0)
    window.transform_bar.apply.click()
    window.session.wait_for_idle()

    scene = window.session.evaluate_now().scene
    unterkante = min(as_mesh_data(entry.mesh).bounds.minimum[2] for entry in scene.objects.values())
    assert unterkante == pytest.approx(0.0, abs=1e-6), (
        f"nach dem Drehen liegt die Unterseite bei {unterkante:.3f} mm statt auf "
        "der Platte — ein Teil, das nicht aufliegt, druckt nicht"
    )


def test_the_turn_and_the_drop_are_one_undo(window: MainWindow) -> None:
    """Beides zusammen ist eine Handlung, also ein Strg+Z.

    **Das ist die eigentliche Zusage von P6.** Zwei getrennte Aufrufe wären
    zwei Schritte im Verlauf und zwei Undos für eine Handlung — der Kunde
    drückt einmal zurück, sieht sein Teil in der Luft und weiß nicht, was er
    da halb zurückgenommen hat.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    window.object_tree.select_object(next(iter(result.scene.objects)))
    vorher = len(window.session.project.document.ops)

    window.transform_bar.role_buttons["rotate"].click()
    window.transform_bar.to_bed.setChecked(True)
    window.transform_bar.axis.setCurrentIndex(0)
    window.transform_bar.angle_value.setValue(45.0)
    window.transform_bar.apply.click()
    window.session.wait_for_idle()

    ops = [entry.op for entry in window.session.project.document.ops]
    assert ops[-2:] == ["rotate_object", "place_on_bed"], f"Verlauf endet auf {ops[-3:]}"

    window.session.undo()
    window.session.wait_for_idle()
    danach = len(window.session.project.document.ops)
    assert danach == vorher, (
        f"ein Undo hat {vorher + 2 - danach} von zwei Schritten zurückgenommen — "
        "Drehen und Aufsetzen sind eine Handlung und gehören in eine Transaktion"
    )


def test_moving_never_drops_to_the_bed(window: MainWindow) -> None:
    """Verschieben ist eine Ansage über den Ort — und die gilt.

    Die Gegenprobe zum Haken. Wer ``dz = 10`` tippt, will das Teil oben haben;
    ein Aufsetzen danach nähme ihm genau das. Der Haken gehört deshalb zum
    Drehen und nicht zur Leiste.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    window.object_tree.select_object(next(iter(result.scene.objects)))

    window.transform_bar.to_bed.setChecked(True)
    window.transform_bar.role_buttons["move"].click()
    window.transform_bar.dz.set_value_mm(10.0)
    window.transform_bar.apply.click()
    window.session.wait_for_idle()

    ops = [entry.op for entry in window.session.project.document.ops]
    assert "place_on_bed" not in ops, (
        f"Verschieben hat aufgesetzt und damit die Ansage überschrieben: {ops}"
    )


def test_without_a_chosen_object_the_status_line_says_so(window: MainWindow) -> None:
    """Kein Dialog vor einer rücknehmbaren Handlung (Regel 19).

    Der Satz kommt aus derselben Quelle wie überall sonst — zwei Stellen, die
    dasselbe verschieden erklären, sind eine zu viel.
    """
    window.object_tree.tree.clearSelection()

    window.transform_bar.dz.set_value_mm(5.0)
    window.transform_bar.apply.click()

    assert "Objekt" in window.status_message.text(), window.status_message.text()
