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
    # Der Weg der Oberfläche seit dem Wegfall des Knopfes: die Eingabetaste im
    # Feld wendet an, und zwar alle drei Achsen in **einem** Schritt.
    QTest.keyClick(window.transform_bar.dz.lineEdit(), Qt.Key.Key_Return)
    window.session.wait_for_idle()

    ops = [entry.op for entry in window.session.project.document.ops]
    assert len(ops) > before, "der Klick hat keinen Schritt erzeugt"
    assert ops[-1] == "translate_object", f"letzter Schritt: {ops[-1]}"


def test_leaving_a_field_applies_nothing(window: MainWindow) -> None:
    """Einen getippten Wert stehen lassen und weggehen bewegt **nichts**.

    Der Test hieß bis zum 03.09.2026 „tippen, dann auf Anwenden klicken" und
    prüfte, dass beides zusammen **einen** Schritt ergibt. Den Knopf gibt es
    nicht mehr (Robert: „das Anwenden unten bei Bewegen brauchen wir auch
    nicht"), und damit hat der Test seinen Gegenstand verloren — dass die
    Eingabetaste einmal anwendet, prüft
    :func:`test_the_return_key_still_applies_the_value`.

    **Was bleibt, ist die Zusage dahinter, und sie ist die wichtigere:** Das
    Anwenden hängt an der Eingabetaste und **nicht** am Verlassen des Feldes.
    Hinge es daran, würde jeder Wechsel in ein anderes Feld anwenden — aus
    5 mm wurden 10 mm, aus 90° 180°, und zurück brauchte es zwei Strg+Z. Genau
    diesen Fall gab es einmal, und `editingFinished` feuert weiterhin; nur
    hört niemand mehr darauf.

    Gefahren wird mit echtem Fokus — ohne ``show()`` und ``activateWindow()``
    vergibt Qt offscreen gar keinen, und dann prüft der Test nicht, worum es
    geht.
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
    # **Weggehen, ohne die Eingabetaste zu drücken.** Der Wechsel in ein
    # anderes Feld löst `editingFinished` aus — und genau das darf nichts
    # bewirken.
    window.transform_bar.dy.setFocus()
    QApplication.processEvents()
    window.session.wait_for_idle()

    ops = [entry.op for entry in window.session.project.document.ops]
    assert len(ops) == vorher, (
        f"das Verlassen des Feldes hat {len(ops) - vorher} Schritte erzeugt: {ops[vorher:]}"
    )
    # Und die Gegenprobe an der Geometrie: Was kein Schritt ist, hat auch
    # nichts bewegt. Ohne sie stünde nur da, dass der Verlauf gleich lang
    # blieb — und ein Zug, der am Verlauf vorbei bewegt, wäre schlimmer.
    unbewegt = min(
        as_mesh_data(entry.mesh).bounds.minimum[2]
        for entry in window.session.evaluate_now().scene.objects.values()
    )
    assert unbewegt == pytest.approx(unterkante, abs=1e-6), (
        f"das Teil ist um {unbewegt - unterkante:.3f} mm gewandert, ohne dass ein Schritt entstand"
    )

    # **Und jetzt der Gegenbeweis, dass der Test überhaupt etwas kann**: mit
    # der Eingabetaste bewegt sich dasselbe Feld sehr wohl. Ohne diese Hälfte
    # wäre er auch grün, wenn die Leiste gar nichts mehr täte.
    feld.setFocus()
    QApplication.processEvents()
    feld.lineEdit().selectAll()
    QTest.keyClicks(feld.lineEdit(), "5")
    QTest.keyClick(feld.lineEdit(), Qt.Key.Key_Return)
    window.session.wait_for_idle()
    gehoben = min(
        as_mesh_data(entry.mesh).bounds.minimum[2]
        for entry in window.session.evaluate_now().scene.objects.values()
    )
    assert gehoben - unterkante == pytest.approx(5.0, abs=1e-6), (
        f"mit der Eingabetaste wurden aus 5 mm {gehoben - unterkante:.3f} mm"
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
    QTest.keyClick(window.transform_bar.angle_value.lineEdit(), Qt.Key.Key_Return)
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
    QTest.keyClick(window.transform_bar.angle_value.lineEdit(), Qt.Key.Key_Return)
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
    QTest.keyClick(window.transform_bar.angle_value.lineEdit(), Qt.Key.Key_Return)
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
    QTest.keyClick(window.transform_bar.angle_value.lineEdit(), Qt.Key.Key_Return)
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
    QTest.keyClick(window.transform_bar.angle_value.lineEdit(), Qt.Key.Key_Return)
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
    # Der Weg der Oberfläche seit dem Wegfall des Knopfes: die Eingabetaste im
    # Feld wendet an, und zwar alle drei Achsen in **einem** Schritt.
    QTest.keyClick(window.transform_bar.dz.lineEdit(), Qt.Key.Key_Return)

    assert "Objekt" in window.status_message.text(), window.status_message.text()


def test_a_small_turn_is_not_swallowed_by_a_hidden_snap(bar: TransformBar) -> None:
    """Eine 3D-Szene rastet nicht ein, solange es niemand einstellt.

    **Der Befund (Robert, 03.09.2026):** „bei bewegen geht das drehen des
    modells nicht, nur das normale verschieben". Er stimmte, und die Ursache
    war ein Fang, den niemand sehen konnte: fünfzehn Grad als Vorgabe, gesetzt
    in einem Popup hinter einem Symbolknopf. Ein Zug um wenige Grad drehte den
    Körper unter der Maus mit, die Zahl am Zeiger zählte mit — und das
    Loslassen rundete auf null. Beim Verschieben fiel derselbe Fang nicht auf,
    weil ein Millimeter feiner ist als eine Mausbewegung.

    Wer runde Werte will, tippt sie oder stellt den Fang ein; null heißt dort
    seit je „kein Einrasten". Geprüft wird beides: die Vorgabe der Leiste und
    dass eine kleine Drehung die Rechnung übersteht.
    """
    from app.core.geom.transform import snap_to_step

    assert bar.grid.value_mm() == 0.0, "der Rasterfang ist ab Werk aus"
    assert bar.angle.value() == 0.0, "der Winkelfang ebenso"

    grid, angle = bar.grid.value_mm(), bar.angle.value()
    assert snap_to_step(5.0, angle) == 5.0, "fünf Grad bleiben fünf Grad"
    assert snap_to_step(0.4, grid) == 0.4, "und ein Zehntelmillimeter bleibt einer"


def test_every_axis_turns_and_moves_the_way_it_was_dragged() -> None:
    """Was am Griff gezogen wird, kommt als dieselbe Achse und Richtung an.

    Robert hat es ausdrücklich verlangt („korrektes drehen und schieben
    verifizieren"), und die Frage ist berechtigt: Ein Vorzeichenfehler oder
    eine vertauschte Achse fällt beim Ziehen kaum auf — man korrigiert
    unbewusst mit der Maus nach. Fünfzehn Fälle, drei Achsen, beide
    Richtungen.
    """
    import numpy as np

    from app.ui.viewport import decompose_transform

    def turned(axis: str, degrees: float) -> np.ndarray:
        radians = np.radians(degrees)
        c, s = np.cos(radians), np.sin(radians)
        matrix = np.eye(4)
        matrix[:3, :3] = {
            "x": [[1, 0, 0], [0, c, -s], [0, s, c]],
            "y": [[c, 0, s], [0, 1, 0], [-s, 0, c]],
            "z": [[c, -s, 0], [s, c, 0], [0, 0, 1]],
        }[axis]
        return matrix

    for axis in ("x", "y", "z"):
        for degrees in (7.0, -12.5, 90.0):
            steps = decompose_transform(turned(axis, degrees))
            assert steps.axis == axis, f"{axis} um {degrees}° wurde zu {steps.axis}"
            assert steps.angle == pytest.approx(degrees, abs=0.01), (
                f"{axis}: {steps.angle} statt {degrees}"
            )

    for index, axis in enumerate(("x", "y", "z")):
        for distance in (3.4, -0.2):
            matrix = np.eye(4)
            matrix[index, 3] = distance
            steps = decompose_transform(matrix)
            assert steps.offset[index] == pytest.approx(distance), f"{axis} verlor seinen Weg"
            others = [value for position, value in enumerate(steps.offset) if position != index]
            assert others == pytest.approx([0.0, 0.0]), f"{axis} färbte auf die Nachbarn ab"


def test_the_magnet_holds_near_a_step_and_lets_go_beyond_it() -> None:
    """Frei drehen, aber bei jedem Vielfachen kurz einrasten.

    **Roberts Vorgabe vom 03.09.2026:** „freies drehen, aber kurzes einrasten
    bei allen 45 grad winkeln außer man dreht weiter". Das ist nicht
    :func:`snap_to_step` — jenes zieht *jeden* Wert auf ein Vielfaches und
    macht aus einer Drehung eine Auswahl aus acht Möglichkeiten. Und es ist
    auch nicht „kein Fang", denn dann trifft niemand genau 45 Grad.

    Geprüft werden beide Seiten der Zone am selben Vielfachen, dazu die zwei
    Abschaltungen: Schritt null und Zone null heißen beide „kein Magnet".
    """
    from app.core.geom.transform import snap_near

    assert snap_near(43.0, 45.0, 4.0) == 45.0, "knapp davor rastet ein"
    assert snap_near(47.5, 45.0, 4.0) == 45.0, "knapp dahinter auch"
    assert snap_near(45.0, 45.0, 4.0) == 45.0, "genau darauf bleibt darauf"
    assert snap_near(38.0, 45.0, 4.0) == 38.0, "wer weiterdreht, kommt heraus"
    assert snap_near(52.0, 45.0, 4.0) == 52.0

    assert snap_near(-43.0, 45.0, 4.0) == -45.0, "und in die andere Richtung ebenso"
    assert snap_near(2.0, 45.0, 4.0) == 0.0, "die Null ist auch ein Vielfaches"
    assert snap_near(20.0, 45.0, 4.0) == 20.0, "dazwischen bleibt es frei"

    assert snap_near(43.0, 0.0, 4.0) == 43.0, "ohne Schritt kein Magnet"
    assert snap_near(43.0, 45.0, 0.0) == 43.0, "ohne Zone auch nicht"

    # Eine Zone von der halben Schrittweite wäre wieder ein hartes Raster;
    # weiter als das kann sie nicht greifen.
    assert snap_near(30.0, 45.0, 100.0) == 45.0
    assert snap_near(20.0, 45.0, 100.0) == 0.0


def test_a_rotation_about_a_point_turns_around_that_point() -> None:
    """Die Drehmatrix dreht um die Achse **durch den gegebenen Punkt**.

    Um den Ursprung zu drehen wäre die halbe Antwort: Der Griff sitzt am
    Körper, und eine Korrektur um die Weltachse verschöbe ihn quer durch die
    Szene.
    """
    import numpy as np

    from app.core.geom.transform import rotation_about

    mitte = (10.0, 0.0, 0.0)
    matrix = rotation_about((0.0, 0.0, 1.0), mitte, 90.0)

    fest = matrix @ np.array([10.0, 0.0, 0.0, 1.0])
    assert fest[:3] == pytest.approx([10.0, 0.0, 0.0], abs=1e-9), "der Punkt selbst bleibt liegen"

    gedreht = matrix @ np.array([11.0, 0.0, 0.0, 1.0])
    assert gedreht[:3] == pytest.approx([10.0, 1.0, 0.0], abs=1e-9), (
        "und was einen Millimeter daneben liegt, wandert im Viertelkreis um ihn"
    )


def test_the_turn_handle_sticks_at_forty_five_degrees(qt_app: QApplication) -> None:
    """Der Drehgriff rastet sichtbar ein, ohne das freie Drehen zu nehmen.

    **Roberts Vorgabe vom 03.09.2026:** „freies drehen, aber kurzes einrasten
    bei allen 45 grad winkeln außer man dreht weiter". Geprüft wird die
    Kette, die das leistet, an ihren beiden Enden — der Zahl am Zeiger und
    der Matrix des Körpers.

    Die Matrix ist der Teil, den man sonst erst beim Loslassen merkt:
    `AffineWidget3D` ruft seinen Rückruf **vor** dem Setzen der neuen Matrix
    und übergibt ihm die alte. Was dort gesetzt würde, wäre in derselben Zeile
    wieder weg — deshalb hängt der Magnet an einem eigenen Beobachter, der
    danach läuft.
    """
    import numpy as np

    from app.core.geom.transform import decompose_transform, rotation_about
    from app.ui.viewport import TURN_MAGNET_STEP, TURN_MAGNET_ZONE, Viewport

    viewport = Viewport()
    assert viewport._angle_step == 0.0, "ohne Ansage der Leiste gilt der Magnet"

    # Knapp neben der Raste: der gezeigte Wert ist die Raste.
    assert viewport._settled_angle(43.0) == TURN_MAGNET_STEP
    assert viewport._settled_angle(-43.0) == -TURN_MAGNET_STEP
    # Weit genug weg: der rohe Wert.
    assert viewport._settled_angle(30.0) == 30.0
    assert viewport._settled_angle(TURN_MAGNET_STEP + TURN_MAGNET_ZONE + 1.0) == pytest.approx(50.0)

    # Und eine Ansage der Leiste gewinnt: dann gilt ihr Raster, hart.
    viewport._angle_step = 15.0
    assert viewport._settled_angle(43.0) == 45.0, "45 ist auch ein Vielfaches von 15"
    assert viewport._settled_angle(30.0) == 30.0
    assert viewport._settled_angle(8.0) == 15.0, (
        "das eingestellte Raster zieht jeden Wert, nicht nur den nahen"
    )

    # Die Matrix, die der Magnet daraus baut: aus 43 Grad werden 45.
    achse = (0.0, 0.0, 1.0)
    mitte = (0.0, 0.0, 0.0)
    roh = rotation_about(achse, mitte, 43.0)
    korrektur = rotation_about(achse, mitte, 2.0)
    steps = decompose_transform(np.asarray(korrektur @ roh, dtype=float))
    assert steps.angle == pytest.approx(45.0, abs=1e-6), (
        "die Korrektur um die Differenz führt genau auf die Raste"
    )


def test_the_magnet_corrects_the_turn_while_it_runs(qt_app: QApplication) -> None:
    """Der Magnet sitzt im Rückruf des Griffs: aus 43 Grad werden 45, und der
    Griff bekommt die berichtigte Matrix zurück (§18.11).

    Bis zum 05.09.2026 hing er an einem eigenen Beobachter, weil PyVistas
    Widget seinen Rückruf vor dem Setzen der Matrix rief. Der eigene Griff
    setzt, was der Rückruf zurückgibt — der Beobachter ist damit weg, und
    ein vergessener kann nicht mehr am Griff der vorigen Auswahl ziehen.
    """
    import numpy as np

    from app.core.geom.transform import decompose_transform, rotation_about
    from app.ui.render import shapes
    from app.ui.render.gizmo import Gizmo
    from app.ui.viewport import Viewport
    from tests.render_fakes import RecordingItem, RecordingRenderer

    viewport = Viewport()
    try:
        renderer = RecordingRenderer(scale=20.0)
        viewport.renderer = renderer
        vertices, _faces = shapes.cube((0.0, 0.0, 0.0), 10.0)
        body = RecordingItem("object:obj_1", np.asarray(vertices), "#ffffff")
        viewport._gizmo = Gizmo(renderer, body, scale=0.3)

        roh = rotation_about((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 43.0)
        corrected = viewport._on_gizmo_interacted(roh)
        assert corrected is not None, "knapp neben der Raste greift der Magnet"
        assert decompose_transform(np.asarray(corrected)).angle == pytest.approx(45.0, abs=1e-6)

        # Weit genug weg von jeder Raste bleibt es beim rohen Wert.
        frei = rotation_about((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 30.0)
        assert viewport._on_gizmo_interacted(frei) is None
    finally:
        viewport.renderer = None
        viewport.deleteLater()


def test_a_face_offers_only_moving(qt_app: QApplication) -> None:
    """Bei einer gewählten Fläche fallen Drehen und Skalieren weg.

    „Eine Seite zu bewegen oder skalieren oder drehen zu lassen ist denke ich
    sowieso sinnlos" (Robert, 03.09.2026). Beides gibt am Netz einen
    `NeedsSolidError` — und zwar **erst nach** dem ausgefüllten Feld und dem
    Klick. Regel 19 verbietet genau das: Ein Werkzeug, das für diese Auswahl
    nichts kann, wird gar nicht erst angeboten.

    *Verschieben* bleibt, denn es ist Press/Pull entlang der Normalen und für
    den Kunden „Maß ändern" — die einzige der drei Rollen, die an einer Fläche
    etwas bedeutet.

    Geprüft wird auch die **zweite Kodierung** (Regel 18): Der Grund steht als
    Text im Tooltip, nicht nur als graue Farbe. „Warum geht das nicht" ist die
    Frage, die eine ausgegraute Schaltfläche sonst offen lässt.
    """
    from app.ui.transform_bar import TransformBar

    bar = TransformBar()
    bar.limit_roles({"move": None, "rotate": "Das braucht einen exakten Körper.", "scale": None})

    assert bar.role_buttons["move"].isEnabled()
    assert not bar.role_buttons["rotate"].isEnabled()
    assert bar.role_buttons["rotate"].toolTip() == "Das braucht einen exakten Körper."
    assert bar.role_buttons["rotate"].statusTip() == "Das braucht einen exakten Körper."

    # Und zurück: Ohne Sperre gilt wieder der eigene Satz der Rolle.
    bar.limit_roles({"move": None, "rotate": None, "scale": None})
    assert bar.role_buttons["rotate"].isEnabled()
    assert "Achse" in bar.role_buttons["rotate"].toolTip(), "der eigene Hinweis kommt zurück"


def test_a_locked_role_does_not_stay_selected(qt_app: QApplication) -> None:
    """Wird die gewählte Rolle gesperrt, springt die Leiste auf eine freie.

    Sonst zeigt sie Felder, die niemand anwenden kann: Der Kunde tippt einen
    Winkel, drückt die Eingabetaste und bekommt nichts — dieselbe Sackgasse
    wie vorher, nur eine Ebene später.
    """
    from app.ui.transform_bar import TransformBar

    bar = TransformBar()
    bar.role_buttons["rotate"].setChecked(True)
    assert bar.role_buttons["rotate"].isChecked()

    bar.limit_roles({"move": None, "rotate": "geht hier nicht", "scale": "geht hier auch nicht"})
    assert bar.role_buttons["move"].isChecked(), "die freie Rolle übernimmt"
    assert not bar.role_buttons["rotate"].isChecked()


def test_one_press_of_return_applies_once(qt_app: QApplication) -> None:
    """Ein Tastendruck, ein Schritt — auch wenn Qt zweimal meldet.

    Gemessen am 03.09.2026: Ein Return im Eingabefeld einer
    ``QDoubleSpinBox`` löst ``returnPressed`` **zweimal** aus.

        keyClick(Return) auf dem Feld       2 Aufrufe
        returnPressed direkt emittiert      1
        keyClick(Return) auf der SpinBox    1

    Aus 5 mm wurden damit 10, aus 90° 180°, und zurück brauchte es zwei
    Strg+Z. **Der Fehler ist älter als der Wegfall des Anwenden-Knopfes und
    war von ihm verdeckt**: Jeder Test, der die Wirkung prüfte, ging über den
    Knopf, und der feuert einmal. Der Kunde tippt aber im Feld.

    Der Test geht deshalb genau den Weg des Kunden — `QTest.keyClick` auf dem
    Eingabefeld, nicht auf der SpinBox und nicht über das Signal. Über das
    Signal wäre er grün gewesen, ohne etwas zu prüfen.
    """
    from app.ui.transform_bar import TransformBar

    bar = TransformBar()
    gerufen: list[str] = []
    bar.applyRequested.connect(lambda op, _params: gerufen.append(op))

    bar.dz.set_value_mm(5.0)
    QTest.keyClick(bar.dz.lineEdit(), Qt.Key.Key_Return)
    assert gerufen == ["translate_object"], f"ein Tastendruck ergab {len(gerufen)} Schritte"

    # **Und das Gatter öffnet wieder.** Eine Entprellung, die klemmt, wäre
    # schlimmer als die Doppelung: Der zweite Tastendruck täte dann nichts.
    QApplication.processEvents()
    QTest.keyClick(bar.dz.lineEdit(), Qt.Key.Key_Return)
    assert len(gerufen) == 2, "der nächste Tastendruck muss wieder anwenden"
