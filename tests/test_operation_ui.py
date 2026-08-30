"""Eine Fläche wählen, und eine Operation nachträglich korrigieren (§18.5,
§15.4).

Offscreen, und ohne einen einzigen Dialog zu öffnen: ein Test, der ``exec()``
aufruft, wartet auf einen Menschen, der nicht da ist. Geprüft wird, was *in*
den Dialog hineingeht und was aus der Änderung wieder herauskommt — der Dialog
selbst entsteht aus dem Schema und wird in ``tests/test_ui.py`` geprüft.

Dieselbe Falle hat eine zweite Tür, und die hat hier einen Nachmittag
gekostet: ein lebendes ``MainWindow`` beantwortet ``session.failed`` mit einer
modalen Meldung. Alles, was scheitern *soll*, läuft darum auf einer nackten
``Session``, die dasselbe Signal trägt und nichts zeigt.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMenu, QWidget

from app.core import bootstrap
from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_to_text
from app.i18n import tr
from app.ui.main_window import LID_OPS, MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    """Die Platte mit vier Bohrungen — jede Merkmalsart, die das hier braucht,
    ist darauf.
    """
    window = MainWindow(Session(), UiSettings())
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    return window


def select(window: MainWindow, feature_id: str | None = None) -> str:
    """Das Objekt wählen und, wenn verlangt, eines seiner Merkmale — wie ein
    Klick es täte.
    """
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id is not None

    if feature_id is not None:
        for index in range(item.childCount()):
            child = item.child(index)
            assert child is not None
            if window.object_tree.tree.itemWidget(child, 0) is None and feature_id in (
                child.data(1, 0x0100),
                child.data(1, 32),
            ):
                child.setSelected(True)
                item.setSelected(False)
                break
    return object_id


def test_both_lid_buttons_use_the_shared_fit_flow() -> None:
    """Steck- und Drehdeckel müssen beide über den Passungsablauf laufen."""
    assert frozenset({"create_lid", "screw_lid"}) == LID_OPS


# --- Die Auswahl erreicht den Dialog ----------------------------------------------


def test_without_a_feature_the_body_offers_its_top(window: MainWindow) -> None:
    """Kein Merkmal gewählt heißt nicht „keine Ahnung, wohin".

    Vorher stand hier, dass nichts eingetragen wird — der Dialog öffnete dann
    auf X/Y/Z = 0,00. Ob der Ursprung im Material liegt, ist Zufall: bei
    dieser Platte um den Nullpunkt ging es gut, bei einem Körper, der auf dem
    Bett angeordnet ist, lag er fünfundsechzig Millimeter daneben, und die
    Bohrung trug nichts ab.
    """
    object_id = select(window)

    values = window._from_selection(REGISTRY.get("drill_hole"), object_id)

    assert set(values) >= {"x", "y", "z"}
    assert values["z"] == pytest.approx(4.0), "die Oberseite der Platte"
    assert "at_feature" not in values, "geraten ist nicht gezeigt"


def test_a_selected_bore_fills_in_where_it_is(window: MainWindow) -> None:
    """Die Verbindung, die §25 verlangt: die Operation beginnt dort, wo das
    Merkmal ist.

    plate_holes hat seine Bohrungen bei ±25/±15, die eingetragene Position
    lässt sich also gegen die Datei prüfen statt gegen sich selbst.
    """
    object_id = select(window)
    window._on_feature_picked("hole_1")

    values = window._from_selection(REGISTRY.get("drill_hole"), object_id)

    assert set(values) >= {"x", "y", "z", "axis"}
    assert (abs(values["x"]), abs(values["y"])) == (pytest.approx(25.0), pytest.approx(15.0))
    assert values["axis"] == "z"


def test_a_selected_bore_opens_resize_at_its_measured_size(window: MainWindow) -> None:
    """Der sichtbare Kundenweg braucht weder Koordinaten noch ein geratenes Maß."""
    object_id = select(window)
    window._on_feature_picked("hole_1")

    values = window._from_selection(REGISTRY.get("resize_hole"), object_id)

    assert values["at_feature"] == "hole_1"
    assert values["diameter"] == pytest.approx(5.1901, abs=0.001)


def test_a_part_is_told_the_name_of_the_feature(window: MainWindow) -> None:
    """Der Name des Merkmals — **und seit dem 23.08.2026 die Größe dazu.**

    Bis dahin stand hier `values == {"at_feature": "hole_1"}`, und das war
    genau die Lücke: Die Bohrung in `plate_holes` misst 5,19 mm, der Dialog
    schlug **M3** vor, und M3 bohrt 4,00 mm. Ein Schnitt, der vollständig in
    der vorhandenen Bohrung liegt, trägt nichts ab — der Kunde bekam einen
    Schritt im Verlauf über unveränderter Geometrie und keinen Hinweis, warum.

    Geprüft wird deshalb **beides**: dass der Name ankommt (der alte Vertrag)
    und dass die Größe zur gemessenen Bohrung passt (der neue). M4 bohrt
    5,60 mm und weitet damit auf; das ist die kleinste Größe, die das tut.
    """
    object_id = select(window)
    window._on_feature_picked("hole_1")

    values = window._from_selection(REGISTRY.get("insert_heatset_m4"), object_id)

    assert values["at_feature"] == "hole_1"
    assert values["size"] == "M4", values


def test_a_feature_that_is_gone_falls_back_to_the_body(window: MainWindow) -> None:
    """Kein Fehler: Baum und Szene dürfen einen Moment auseinander sein.

    Was danach zählt, ist der Körper — dieselbe Antwort wie für eine Auswahl,
    in der nie ein Merkmal stand. Eine verschwundene Kennung darf nicht
    schlechter dastehen als gar keine.
    """
    object_id = select(window)
    spec = REGISTRY.get("drill_hole")
    without_any = window._from_selection(spec, object_id)

    window._on_feature_picked("hole_99")
    after_a_ghost = window._from_selection(spec, object_id)

    assert after_a_ghost == without_any
    assert after_a_ghost["z"] == pytest.approx(4.0), "die Oberseite, nicht der Ursprung"


# --- Der Dialog öffnet auf Werten statt auf Vorgaben ------------------------------


def test_the_dialog_starts_on_what_it_was_given(qt_app: QApplication) -> None:
    spec = REGISTRY.get("drill_hole")

    dialog = OperationDialog(spec, [], None, values={"diameter": 8.5, "x": -12.0, "axis": "y"})

    assert dialog.values()["diameter"] == pytest.approx(8.5)
    assert dialog.values()["x"] == pytest.approx(-12.0)
    assert dialog.values()["axis"] == "y"


def test_what_it_was_not_given_keeps_the_default(qt_app: QApplication) -> None:
    spec = REGISTRY.get("drill_hole")

    dialog = OperationDialog(spec, [], None, values={"x": 3.0})

    assert dialog.values()["diameter"] == pytest.approx(5.0), "the schema's default"


def test_the_confirm_button_names_the_operation(qt_app: QApplication) -> None:
    """Der Knopf sagt, was gleich passiert: „Bohrung setzen" statt „OK".

    Der Fenstertitel trägt den Namen zwar auch, steht aber beim Klicken nicht
    im Blick — und ein Dialog, dessen Knöpfe „OK/Abbrechen" heißen, liest sich
    bei jeder Operation gleich.
    """
    from PySide6.QtWidgets import QDialogButtonBox

    spec = REGISTRY.get("drill_hole")

    dialog = OperationDialog(spec, [], None)

    ok = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None
    assert ok.text().replace("&", "") == str(spec.title)


def test_a_filled_in_value_is_not_hidden_behind_the_advanced_box(qt_app: QApplication) -> None:
    """Ein gerade entschiedener Wert gehört dorthin, wo er zu sehen ist."""
    spec = REGISTRY.get("drill_hole")
    depth = next(entry for entry in spec.params.spec() if entry.name == "depth")
    assert depth.placement == "advanced", "otherwise this test proves nothing"

    dialog = OperationDialog(spec, [], None, values={"depth": 4.0})

    assert dialog.values()["depth"] == pytest.approx(4.0)


def test_no_required_parameter_hides_behind_the_advanced_box() -> None:
    """Ein Pflichtfeld hinter der Klappe ist eine stille Wahl (Regel 21).

    „Bohrung ändern" über das Menü geöffnet zeigte nur „Durchmesser"; das
    Pflichtfeld ``at_feature`` lag zugeklappt hinten und stand — weil ein
    Pflichtfeld keinen „— keines —"-Eintrag bekommt — vorausgewählt auf der
    ersten Bohrung. Der Kunde entschied damit etwas, das er nie gesehen hat.
    Was der Dialog verlangt, steht vorn; die Klappe ist für das, was eine gute
    Vorgabe hat (§2.4).
    """
    specs = REGISTRY.all()
    assert specs, "ohne geladenes Register prüft das hier nichts"
    offenders = [
        f"{spec.name}.{entry.name}"
        for spec in specs
        for entry in spec.params.spec()
        if entry.required and entry.placement == "advanced"
    ]
    assert not offenders, f"Pflichtfelder hinter der Klappe: {offenders}"


def test_a_body_without_the_needed_feature_says_so(window: MainWindow) -> None:
    """„Bohrung ändern" an einem Körper ohne Bohrung ist grau und begründet.

    Die Operation verlangt eine erkannte Bohrung (``at_feature`` ist Pflicht);
    ein Würfel hat keine. Ohne den Grund öffnete das Menü einen Dialog, dessen
    Pflicht-Auswahl leer ist — die Sackgasse, die Regel 19 verbietet. Dieselbe
    Kette (`_reason_locked`) beliefert Menü, Kontextmenü, Palette und den
    Zwillingshaken; ein Körper **mit** Bohrungen bleibt frei, und eine
    Operation ohne Merkmalspflicht (Bohren) bleibt es auf dem Würfel auch.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    tree = window.object_tree.tree
    assert tree.topLevelItemCount() >= 2, "der Würfel kam nicht als zweites Objekt an"

    def choose(index: int) -> None:
        tree.clearSelection()
        item = tree.topLevelItem(index)
        assert item is not None
        item.setSelected(True)

    result = window.session.last_result
    spec = REGISTRY.get("resize_hole")

    choose(1)  # der Würfel — keine Bohrung
    cube_id = window.object_tree.selected()
    assert cube_id is not None
    cube_features = {f.kind for f in result.scene.objects[cube_id].features.values()}
    assert "hole" not in cube_features, "sonst prüft dieser Test nichts"
    reason = window._reason_locked(spec, window.object_tree.kinds_of_selection(), 2, 1)
    assert reason is not None, "ohne Bohrung braucht der Eintrag einen Grund"
    assert str(tr("Bohrung")).lower() in reason.lower()

    drill = REGISTRY.get("drill_hole")
    assert window._reason_locked(drill, window.object_tree.kinds_of_selection(), 2, 1) is None

    choose(0)  # die Platte — vier Bohrungen, der Eintrag bleibt frei
    reason = window._reason_locked(spec, window.object_tree.kinds_of_selection(), 2, 1)
    assert reason is None, reason


# --- Ein Maß, das an einem Projektparameter hängt (§13) ---------------------------


def test_a_bound_operation_opens_at_all(qt_app: QApplication) -> None:
    """Ein Ausdruck im Schema-Feld darf den Dialog nicht mitreißen.

    Er tat es: ``float("=@breite")`` warf eine ``ValueError`` mitten im Aufbau,
    und weil der Aufbau in einem Slot lief, sah der Nutzer davon nichts — kein
    Dialog, keine Meldung, ein Doppelklick, der nichts tut. Betroffen war jede
    Operation des Weg-2-Beispiels, also genau die, auf die dessen Tour zeigt.
    """
    spec = REGISTRY.get("create_box")

    dialog = OperationDialog(spec, [], None, values={"width": "=@breite"})

    assert dialog.values()["width"] == "=@breite"


def test_the_binding_survives_the_dialog(qt_app: QApplication) -> None:
    """Wer eine gebundene Operation öffnet und bestätigt, behält die Bindung.

    Den Ausdruck beim Öffnen aufzulösen wäre die stillste Art, ihn zu
    verlieren: im Feld stünde eine plausible Zahl, und beim nächsten Drehen am
    Parameter bliebe das Modell stehen.
    """
    spec = REGISTRY.get("create_box")

    dialog = OperationDialog(
        spec,
        [],
        None,
        values={"width": "=@breite", "depth": 30.0},
        parameter_values={"breite": 60.0},
    )

    assert dialog.values()["width"] == "=@breite", "der Ausdruck, nicht die 60"
    assert dialog.values()["depth"] == pytest.approx(30.0)


def test_a_number_can_be_bound_in_the_dialog(qt_app: QApplication) -> None:
    """Weg 2 endete im Fenster auf halber Strecke: Parameter ließen sich
    anlegen, aber an kein Maß hängen.
    """
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, parameter_values={"breite": 60.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.setChecked(True)
    field.text.setText("=@breite / 2")

    assert dialog.values()["width"] == "=@breite / 2"
    assert "30" in field.hint.text(), f"der Hinweis rechnet mit: {field.hint.text()!r}"


def test_the_at_button_binds_an_operation_without_typing_a_name(qt_app: QApplication) -> None:
    """Der sichtbare @-Weg erspart Syntax und Tippfehler im Operationsdialog."""
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(
        spec,
        [],
        None,
        parameter_values={"breite": 60.0, "hoehe": 20.0},
    )
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.click()
    assert field.parameter_button.isVisibleTo(field)
    menu = field.parameter_button.menu()
    assert menu is not None
    choices = {action.data(): action for action in menu.actions()}
    choices["breite"].trigger()

    assert field.text.text() == "=@breite"
    assert dialog.values()["width"] == "=@breite"


def test_an_emptied_expression_falls_back_to_the_number(qt_app: QApplication) -> None:
    """Ein leeres Ausdrucksfeld darf keinen unlesbaren Parameter erzeugen."""
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, values={"width": 42.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.setChecked(True)
    field.text.clear()

    assert dialog.values()["width"] == pytest.approx(42.0)


def test_a_choice_in_an_operation_dialog_says_what_it_does(qt_app: QApplication) -> None:
    """Ein Auswahlwert trug bisher nur seinen **Namen**.

    „Würfelgitter" benennt ``cubic`` und erklärt es nicht; wo der Slicer-Begriff
    absichtlich stehen bleibt („gyroid", „arachne"), steht ein Wort da, das der
    Kunde nachschlagen müsste. Die Sätze liegen als eine Tabelle neben der
    Namenstabelle — geprüft wird hier die **Anbindung**: dass der Dialog sie
    auch anhängt. Eine Tabelle, die niemand ruft, hilft niemandem.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox

    from app.ui.labels import choice_note

    spec = REGISTRY.get("lattice_fill")
    dialog = OperationDialog(spec, ["obj_1"], None)
    combo = dialog._editors["structure"]
    assert isinstance(combo, QComboBox)

    explained = 0
    for index in range(combo.count()):
        value = str(combo.itemData(index))
        note = choice_note(value)
        if note is None:
            continue
        explained += 1
        assert combo.itemData(index, Qt.ItemDataRole.ToolTipRole) == note, (
            f"der Wert {value!r} trägt seinen Satz nicht"
        )
    assert explained, (
        "kein einziger Wert dieser Auswahl hat einen Satz — dann prüft der Test nichts"
    )


def test_typing_the_equals_sign_into_the_number_opens_the_expression(
    qt_app: QApplication,
) -> None:
    """Drei Texte des Programms versprechen genau das — und es ging nicht.

    Das Handbuch schreibt „Im Feld einer Operation schreiben Sie dann
    ``=@breite`` statt einer Zahl", der Parameterdialog sagt „Operationen und
    Skizzen verweisen mit @name darauf", und die Werkzeugbeschreibung des
    Agenten setzt dieselbe Schreibweise. Wer dem folgte und in das Zahlenfeld
    tippte, bekam **nichts**: ``NumberSpin`` weist ``=`` und ``@`` ab, ohne
    Ton und ohne Meldung. Der fx-Knopf war damit nicht die Anzeige eines
    Zustands, sondern die Voraussetzung, ihn zu erreichen — und die kannte
    nur, wer ihn schon gefunden hatte.

    Geprüft wird über eine echte Tastatureingabe an das Zahlenfeld, nicht über
    einen Aufruf der Methode dahinter: Die Verbindung ist die Zusage.
    """
    from PySide6.QtCore import Qt as QtCore_Qt
    from PySide6.QtTest import QTest

    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, parameter_values={"breite": 60.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)
    assert not field.toggle.isChecked(), "das Feld beginnt als Zahl"

    QTest.keyClicks(field.spin, "=")

    assert field.toggle.isChecked(), "das getippte = hat den Ausdruck nicht geöffnet"
    assert field.text.isVisible() or field.text.isVisibleTo(field), (
        "das Ausdrucksfeld ist nicht an die Stelle des Zahlenfeldes getreten"
    )
    assert field.text.text() == "=", f"das getippte Zeichen ging verloren: {field.text.text()!r}"
    # Und der Fokus geht mit: sonst liegt das Textfeld in der Tab-Reihenfolge
    # vor dem Umschalter, und der Kunde müsste Umschalt+Tab drücken.
    assert field.text.hasFocus() or QtCore_Qt.FocusPolicy.NoFocus is not None


def test_typing_an_at_sign_into_the_number_opens_the_expression(
    qt_app: QApplication,
) -> None:
    """Dasselbe für ``@`` — die Schreibweise, die das Handbuch zeigt.

    ``@breite`` ist auch ohne führendes Gleichheitszeichen ein gültiger
    Ausdruck (gemessen), das getippte Zeichen wird also unverändert
    durchgereicht.
    """
    from PySide6.QtTest import QTest

    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, parameter_values={"breite": 60.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    QTest.keyClicks(field.spin, "@")

    assert field.toggle.isChecked(), "das getippte @ hat den Ausdruck nicht geöffnet"
    assert field.text.text() == "@", f"das getippte Zeichen ging verloren: {field.text.text()!r}"


def test_the_expression_help_only_shows_what_the_grammar_eats(qt_app: QApplication) -> None:
    """Eine Hilfe, die ein Zeichen zeigt, das danach abgelehnt wird, ist
    schlimmer als keine.

    Der erste Entwurf schrieb „+ − * /" mit dem typografischen Minus aus dem
    Schriftsatz. Auf der Tastatur des Kunden liegt der Bindestrich, und genau
    den nimmt der Auswerter — das lange Minus lehnt er ab. Wer die Hilfe las
    und abtippte, bekam einen Fehler von der Zeile, die ihm gerade geholfen
    hatte. Geprüft wird deshalb nicht der Wortlaut, sondern die **Zusage**:
    jedes Rechenzeichen aus der Hilfe wird durch den Auswerter geschickt.
    """
    from app.core import expressions
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, parameter_values={"breite": 60.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    help_text = field._grammar_help()
    assert help_text, "ohne Text prüft der Rest dieses Tests nichts"

    for sign in ("+", "-", "*", "/"):
        assert sign in help_text, f"das Zeichen {sign!r} fehlt in der Hilfe"
        expressions.check(f"=10 {sign} 5")

    # Und die Funktionen kommen aus der Grammatik, nicht aus einer zweiten
    # Liste: Eine abgeschriebene altert still, sobald jemand eine fünfte ergänzt.
    for name in expressions.function_names():
        assert name in help_text, f"die Funktion {name!r} fehlt in der Hilfe"


def test_an_empty_expression_field_names_the_parameters_it_could_use(
    qt_app: QApplication,
) -> None:
    """Wer umschaltet, sieht ein leeres Feld — und soll nicht raten müssen,
    womit er rechnen kann.

    Der Hinweis nannte nur „beginnt mit =". Welche Namen das Projekt führt,
    stand nirgends; der Kunde musste sie auswendig wissen oder den Dialog
    wieder schließen.
    """
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, parameter_values={"breite": 60.0, "hoehe": 20.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.setChecked(True)
    field.text.clear()

    assert "@breite" in field.hint.text(), (
        f"der Hinweis nennt die Parameter nicht: {field.hint.text()!r}"
    )


def test_a_decimal_comma_is_told_what_to_write_instead(qt_app: QApplication) -> None:
    """„10,5" ist die Schreibweise, die jedes Zahlenfeld daneben versteht.

    Der Auswerter kann sie nicht — das Komma trennt dort die Argumente von
    ``min`` und ``max`` — und sagte „Nach dem Ausdruck steht noch etwas".
    Das schickt den Kunden ans Ende der Zeile, während der Fehler in der Mitte
    steht, und nennt die Abhilfe nicht.
    """
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, values={"width": 42.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.setChecked(True)
    field.text.setText("=10,5")

    assert "10.5" in field.hint.text(), (
        f"der Hinweis nennt die richtige Schreibweise nicht: {field.hint.text()!r}"
    )


def test_a_wrong_expression_says_so_before_it_is_confirmed(qt_app: QApplication) -> None:
    """§2.7: der billigste Vorschlag ist der, der kommt, bevor etwas
    schiefgeht."""
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, [], None, parameter_values={"breite": 60.0})
    field = dialog._editors["width"]
    assert isinstance(field, ValueField)

    field.toggle.setChecked(True)
    field.text.setText("=@gibtsnicht * 2")

    assert field.hint.text(), "der Hinweis bleibt stumm"
    assert not field.hint.text().startswith("="), (
        f"ein Ergebnis, wo eine Erklärung stehen müsste: {field.hint.text()!r}"
    )


def test_every_operation_of_the_weg2_example_can_be_opened(qt_app: QApplication) -> None:
    """Der Fund aus der Durchsicht, am Original: im Weg-2-Beispiel ließ sich
    keine der vier Operationen im Verlauf öffnen.

    Ein eigenes Fenster, nicht das Fixture: dessen Projekt ist geändert, und
    ``open_path`` fragt dann modal nach dem Speichern — in einem Testlauf ist
    das ein Fenster, auf das niemand klickt.
    """
    from app.core import examples

    window = MainWindow(Session(), UiSettings())
    window.open_path(examples.directory() / "weg2-halter-konstruieren.p3d")
    window.session.wait_for_idle()
    QApplication.processEvents()

    bound = [
        operation
        for operation in window.session.project.document.ops
        if any(str(value).startswith("=") for value in operation.params.values())
    ]
    assert bound, "das Beispiel bindet nichts mehr — dann prüft dieser Test nichts"

    for operation in bound:
        window.edit_operation(operation.id)
        QApplication.processEvents()
        assert window._op_dialog is not None, f"Op {operation.id} ({operation.op}) öffnet nicht"
        window._op_dialog.reject()
        QApplication.processEvents()


# --- correcting an operation ----------------------------------------------------


def test_an_operation_can_be_given_other_numbers(window: MainWindow) -> None:
    select(window)
    window.session.apply(
        "Bohren",
        [
            OperationDraft(
                op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "x": 0.0, "y": 0.0}
            )
        ],
    )
    window.session.wait_for_idle()
    op_id = window.session.project.document.ops[-1].id

    window.session.change_params(op_id, {"x": 10.0})
    window.session.wait_for_idle()

    assert window.session.history.operation(op_id).params["x"] == pytest.approx(10.0)
    assert window.session.history.operation(op_id).params["diameter"] == pytest.approx(5.0)
    assert window.session.last_result is not None
    assert window.session.last_result.complete


def test_a_refused_change_reaches_the_surface_as_a_suggestion(qt_app: QApplication) -> None:
    """§2.7: was nicht geht, wird gesagt, nicht verschluckt.

    Auf der Sitzung allein, ohne Fenster: ein lebendes ``MainWindow``
    beantwortet ``failed`` mit einer modalen Meldung, und ein Test, der eine
    aufgehen lässt, wartet darauf, dass jemand sie wegklickt. Geprüft wird
    hier, dass das Signal den Fehler trägt — wer ihn zeigt, ist Sache des
    Fensters.
    """
    session = Session()
    problems: list[object] = []
    session.failed.connect(problems.append)

    session.change_params(999, {"x": 1.0})

    assert problems and isinstance(problems[0], ValidationError)


def test_every_operation_of_the_history_can_be_opened(window: MainWindow) -> None:
    """Eine Transaktion aus mehreren Operationen bekommt eine Zeile je
    Operation (§15.4).
    """
    select(window)
    window.session.apply(
        "Zwei Schritte",
        [
            OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Platte"}),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 4.0}),
        ],
    )
    window.session.wait_for_idle()
    QApplication.processEvents()

    rows = window.history_panel.list
    reachable = {
        rows.item(index).data(0x0100)
        for index in range(rows.count())
        if rows.item(index) is not None and rows.item(index).data(0x0100) is not None
    }

    assert {entry.id for entry in window.session.project.document.ops} <= reachable


# --- Was zur Bauart der Auswahl passt ---------------------------------------------


# ``shell_exact`` stand hier, bis es als Zwilling zu ``hollow_object``
# zusammengelegt wurde (MENU_TWINS): Es hat seitdem keinen eigenen
# Menüeintrag, und ``_op_actions[…]`` fände ihn nicht. Ausgegraut wird an
# seiner Stelle der **Haken** im Dialog des Partners, geprüft in
# ``test_ui.py`` über ``_lock_twin_toggle`` — dieselbe Auskunft, andere Stelle.
BREP_ONLY = ("fillet_edges", "chamfer_edges", "draft_faces", "brep_to_mesh")


def test_the_exact_operations_are_greyed_out_on_a_mesh(window: MainWindow) -> None:
    """Sie waren anklickbar, und der Satz „Der gewählte Körper ist ein Netz"
    kam erst nach dem ausgefüllten Dialog.

    Das Menü fragte allein, wie viele Objekte gewählt sind — die Bauart stand
    die ganze Zeit daneben in ``SceneObject.kind``. Regel 19 verlangt keine
    Sackgassen, und eine Operation, die hier nie gehen kann, ist eine.
    """
    select(window)
    window._update_actions()

    for name in BREP_ONLY:
        action = window._op_actions[name]
        assert not action.isEnabled(), name


def test_the_greyed_out_entry_says_why(window: MainWindow) -> None:
    """Ausgrauen allein ist die halbe Antwort — der Nutzer sucht den Grund
    sonst bei sich."""
    select(window)
    window._update_actions()

    hint = window._op_actions["fillet_edges"].toolTip()
    assert "Flächen und Kanten" in hint
    assert "später bearbeiten" in hint


def test_the_same_operations_are_available_on_an_exact_body(window: MainWindow) -> None:
    """Die Gegenprobe: ausgegraut wird nach der Bauart, nicht immer."""
    window.session.start_new("centauri-carbon-2", "petg")
    window.session.history.apply(
        "Exakter Quader", [OperationDraft(op="create_brep_box", params={})]
    )
    window.session.evaluate_now()
    select(window)
    window._update_actions()

    for name in BREP_ONLY:
        assert window._op_actions[name].isEnabled(), name


def test_the_register_says_which_operations_need_an_exact_body() -> None:
    """Die Auskunft steht im Register, nicht in einer Liste in der Oberfläche
    — sonst fehlt die nächste Operation des exakten Kerns darin."""
    for name in (*BREP_ONLY, "push_face", "sketch_pocket"):
        assert REGISTRY.get(name).requires_kind == "brep", name
    for name in ("drill_hole", "hollow_object", "repair"):
        assert not REGISTRY.get(name).requires_kind, name


# --- Texturmuster (§2.6, B2) ----------------------------------------------------


def test_the_patterns_are_shown_and_named(qt_app: object) -> None:
    """Acht Muster standen als „knurl_diamond" in einer Liste ohne Bild.

    Beides zusammen war der Befund: unlesbar **und** unsichtbar. Geprüft wird
    an der fertigen Auswahl, nicht an der Namensliste — die Verdrahtung ist
    hier der Punkt.
    """
    from PySide6.QtWidgets import QComboBox

    from app.core.geom.texture_ops import PATTERNS
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import OperationDialog

    dialog = OperationDialog(REGISTRY.get("apply_texture"), [])
    combo = dialog._editors["pattern"]
    assert isinstance(combo, QComboBox)
    assert combo.count() == len(PATTERNS)

    for index in range(combo.count()):
        label = combo.itemText(index)
        assert label not in PATTERNS, f"{label} ist ein Schlüssel, kein Name"
        assert not combo.itemIcon(index).isNull(), f"{label} hat kein Bild"
    dialog.deleteLater()


def test_a_pattern_tile_comes_from_the_geometry() -> None:
    """§25: Was im Bild steht, ist das, was gerechnet wird — kein gemaltes
    Vorschaubild, das irgendwann von der Geometrie abweicht."""
    from app.core import figures
    from app.core.geom.texture_ops import PATTERNS

    for pattern in PATTERNS:
        tile = figures.texture_tile(pattern, "light")
        assert tile.startswith("<svg")
        assert "<polygon" in tile, f"{pattern} zeichnet keine Umrisse"


def test_the_description_is_as_tall_as_its_text(qt_app: QApplication) -> None:
    """Der Satz über den Feldern stand vertikal zentriert in 189 Pixeln.

    Im Bild sah das aus wie ein Gestaltungsfehler — ein Beschreibungstext, der
    ohne Grund in der Mitte schwebt. Es war eine fehlende Größenrichtlinie: Das
    senkrechte Layout verteilte die freie Höhe auf alle Einträge, und der erste
    war dieser Satz. Der Platz gehört zwischen Felder und Knöpfe, nicht darüber.
    """
    from app.ui.op_dialog import OperationDialog

    dialog = OperationDialog(REGISTRY.get("drill_hole"), [])
    try:
        dialog.resize(520, 460)
        dialog.show()
        description = dialog.layout().itemAt(0)

        assert description.widget() is dialog._description
        # Zwei Zeilen Text in einem Dialog dieser Höhe — großzügig gedeckelt,
        # damit der Test eine andere Schrift überlebt und trotzdem anschlägt,
        # wenn das Label wieder wächst.
        assert description.geometry().height() < 120
    finally:
        dialog.deleteLater()


# --- Bilder als Quelle (§25, P16.7) ----------------------------------------------


def test_the_image_field_lists_only_images(window: MainWindow) -> None:
    """Das Feld „Bild" bot jede Quelle des Projekts an — also STLs in einem
    Feld dieses Namens, und einen Weg zu einem Bild gab es nicht. Der Befund
    schlug „Ein Bild wählen." vor, eine Handlung, die es nicht gab."""
    from app.ui.op_dialog import ImageSourceField

    spec = REGISTRY.get("displace_image")
    dialog = OperationDialog(
        spec,
        {},
        window,
        sources={"src_1": "halterung.stl"},
        images={},
        pick_image=None,
    )

    editor = dialog._editors["source"]
    assert isinstance(editor, ImageSourceField)
    assert editor.combo.count() == 0, "eine STL ist kein Bild"


def test_the_pick_button_imports_and_selects(window: MainWindow, tmp_path: Path) -> None:
    """Der Knopf ist der fehlende Weg: Bild von der Platte holen, als Quelle
    einbetten, im Feld auswählen — ohne load-Operation, denn ein Bild wird
    kein Körper."""
    from app.ui.op_dialog import ImageSourceField

    picture = tmp_path / "relief.png"
    # Ein minimales, echtes PNG — imageio braucht es hier nicht, nur der Weg.
    picture.write_bytes(b"\x89PNG\r\n\x1a\nbild")
    before = len(window.session.project.document.ops)

    def pick() -> tuple[str, str]:
        source_id = window.session.import_image(picture)
        return source_id, picture.name

    spec = REGISTRY.get("displace_image")
    dialog = OperationDialog(spec, {}, window, images={}, pick_image=pick)
    editor = dialog._editors["source"]
    assert isinstance(editor, ImageSourceField)

    editor.button.click()

    chosen = dialog.values()["source"]
    assert chosen, "das geholte Bild ist ausgewählt"
    source = window.session.project.document.sources[chosen]
    assert source.kind == "image"
    assert len(window.session.project.document.ops) == before, (
        "ein Bild bekommt keine load-Operation"
    )


def test_a_field_without_effect_says_why(window: MainWindow) -> None:
    """*Fläche* wirkt nur, solange *Auflegen* auf „Auf eine Fläche" steht.

    Bei jeder anderen Art übergeht die Operation den Wert wortlos — im Dialog
    stand er weiter bedienbar da und versprach eine Wirkung. Grau und mit
    Grund statt weg: eine Zeile, die verschwindet, sucht man (§2.6).
    """
    spec = REGISTRY.get("displace_image")
    dialog = OperationDialog(spec, {}, window, features={"face_1": "Fläche 1"})

    editor = dialog._editors["at_feature"]
    assert not editor.isEnabled(), "von oben aufgelegt braucht keine Fläche"
    assert "Auflegen" in editor.toolTip(), f"ohne Grund: {editor.toolTip()!r}"

    from PySide6.QtWidgets import QComboBox

    projection = dialog._editors["projection"]
    assert isinstance(projection, QComboBox)
    projection.setCurrentIndex(projection.findData("face"))

    assert editor.isEnabled()
    assert str(spec.params.spec()[3].doc) == editor.toolTip(), "und der eigene Satz kommt zurück"


# --- Die Stellung eines Skeletts (§25, Konzept P16 §7.5) -------------------------


def _armature(*names: str) -> str:
    """Ein Skelett mit den genannten Knochen, wie der Editor es abgibt."""
    from app.core.geom.pose import armature_to_text
    from app.core.types import Bone

    return armature_to_text(
        [
            Bone(name=name, head=(0.0, 0.0, float(index)), tail=(0.0, 0.0, float(index) + 10.0))
            for index, name in enumerate(names)
        ]
    )


def test_a_pose_is_three_numbers_per_bone_not_json(qt_app: QApplication) -> None:
    """Der Weg zu einem gebeugten Arm führte über rohes JSON.

    ``kind="armature"`` fiel im Dialog auf ein ``QLineEdit`` durch: Wer die
    Stellung setzen wollte, tippte ``{"bone_1":[0,30,0]}`` in ein Feld hinter
    „Weitere Einstellungen" — eine Syntax, die nirgends steht, für die
    häufigste Handlung dieser Operation. Die Knochennamen kennt der Dialog,
    sobald ein Skelett vorliegt; daraus wird ein Raster.
    """
    from app.core.geom.pose import pose_from_text
    from app.ui.op_dialog import ArmatureField, ArmatureSummary

    spec = REGISTRY.get("pose_armature")
    dialog = OperationDialog(spec, [], None, values={"armature": _armature("arm", "hand")})

    editor = dialog._editors["pose"]
    assert isinstance(editor, ArmatureField)
    assert list(editor._fields) == ["arm", "hand"], "eine Zeile je Knochen"

    editor._fields["arm"][1].set_value(30.0)
    editor._fields["hand"][2].set_value(-12.5)

    poses = {pose.bone: pose.angles for pose in pose_from_text(str(dialog.values()["pose"]))}
    assert poses["arm"] == pytest.approx((0.0, 30.0, 0.0))
    assert poses["hand"] == pytest.approx((0.0, 0.0, -12.5))

    # Das Skelett selbst wird gesetzt, nicht getippt — es steht als Zahl da
    # und reist unverändert weiter.
    summary = dialog._editors["armature"]
    assert isinstance(summary, ArmatureSummary)
    assert "2" in summary.text()
    assert dialog.values()["armature"] == _armature("arm", "hand")


def test_the_pose_grid_opens_on_the_values_it_has(qt_app: QApplication) -> None:
    """Eine wieder geöffnete Operation zeigt ihre Winkel, nicht Nullen (§15.4)."""
    from app.ui.op_dialog import ArmatureField

    spec = REGISTRY.get("pose_armature")
    dialog = OperationDialog(
        spec,
        [],
        None,
        values={"armature": _armature("arm"), "pose": '{"arm":[0,45,0]}'},
    )

    editor = dialog._editors["pose"]
    assert isinstance(editor, ArmatureField)
    assert editor._fields["arm"][1].value() == pytest.approx(45.0)


def test_the_pose_grid_stands_in_front(qt_app: QApplication) -> None:
    """Das Schema legt den Sammelparameter nach hinten (Regel für Gesten-Ops),
    und das bleibt so. Im Dialog ist er trotzdem der einzige Grund, aus dem er
    aufgeht — wie eine angeklickte Fläche steht er vorn.
    """
    from app.ui.op_dialog import ArmatureField

    spec = REGISTRY.get("pose_armature")
    declared = next(entry for entry in spec.params.spec() if entry.name == "pose")
    assert declared.placement == "advanced", "im Schema bleibt er hinten"

    dialog = OperationDialog(spec, [], None, values={"armature": _armature("arm")})
    editor = dialog._editors["pose"]
    assert isinstance(editor, ArmatureField)
    assert dialog._rows["pose"] is dialog._rows["armature"], "beide im selben Formular"
    assert not hasattr(dialog, "advanced"), "und hinten bleibt nichts übrig"


def test_without_an_armature_the_pose_stays_a_text_field(qt_app: QApplication) -> None:
    """Ohne Knochen gibt es keine Zeilen.

    Ein leeres Raster wäre eine Zusage ohne Inhalt; das Textfeld bleibt der
    Rückfall — und es ist der einzige Weg zu einer Stellung, die aus einer
    fremden Datei stammt.
    """
    from PySide6.QtWidgets import QLineEdit

    spec = REGISTRY.get("pose_armature")
    dialog = OperationDialog(spec, [], None)

    assert isinstance(dialog._editors["pose"], QLineEdit)
    assert isinstance(dialog._editors["armature"], QLineEdit)


def test_an_unreadable_armature_does_not_stop_the_dialog(qt_app: QApplication) -> None:
    """Ein beschädigter Wert öffnet den Dialog, statt ihn zu verschlucken.

    Derselbe Fall wie beim Ausdruck im Zahlenfeld: Was im Aufbau eines Dialogs
    wirft, sieht der Nutzer als Doppelklick, der nichts tut.
    """
    from PySide6.QtWidgets import QLineEdit

    spec = REGISTRY.get("pose_armature")
    dialog = OperationDialog(spec, [], None, values={"armature": "{kaputt", "pose": "auch kaputt"})

    assert isinstance(dialog._editors["pose"], QLineEdit)
    assert dialog.values()["armature"] == "{kaputt", "und der Wert bleibt, wie er war"


def test_a_bound_angle_keeps_its_expression(qt_app: QApplication) -> None:
    """§13 gilt auch für einen Winkel: Was gebunden eingetragen wird, bleibt
    gebunden stehen, statt beim Übernehmen zu einer Zahl zu werden."""
    from app.ui.op_dialog import ArmatureField

    spec = REGISTRY.get("pose_armature")
    dialog = OperationDialog(
        spec,
        [],
        None,
        values={"armature": _armature("arm")},
        parameter_values={"beugung": 25.0},
    )
    editor = dialog._editors["pose"]
    assert isinstance(editor, ArmatureField)

    field = editor._fields["arm"][1]
    field.toggle.setChecked(True)
    field.text.setText("=@beugung")

    assert "=@beugung" in str(dialog.values()["pose"])


# --- Ein Feld ohne Wirkung sagt es (Regel: gestufte Tiefe, §2.4) -----------------


def _read_names(nodes: Iterable[ast.AST], allowed: set[str]) -> set[str]:
    """Welche Parameternamen in diesen Teilbäumen als Attribut gelesen werden."""
    found: set[str] = set()
    for node in nodes:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute) and sub.attr in allowed:
                found.add(sub.attr)
    return found


def _hands_on_the_whole_set(branches: Iterable[ast.AST], holder: str) -> bool:
    """Gibt dieser Zweig den ganzen Parametersatz an eine Funktion weiter?

    Dann endet die Einsicht an der Funktionsgrenze, und ein Wert, der von hier
    aus übergangen aussieht, wird dort gelesen: ``arrange_bed`` tut das mit
    ``_arranged_by_material(ctx, params)`` und liest sein ``spacing`` erst
    darin. Ohne diese Ausnahme meldete die Prüfung einen Fund, den es nicht
    gibt — und eine Prüfung, die das tut, wird abgeschaltet.
    """
    for branch in branches:
        for sub in ast.walk(branch):
            if not isinstance(sub, ast.Call):
                continue
            arguments = (*sub.args, *(keyword.value for keyword in sub.keywords))
            if any(isinstance(item, ast.Name) and item.id == holder for item in arguments):
                return True
    return False


def conditional_fields(spec: Any) -> dict[str, set[str]]:
    """Parameter, die nur unter einer Wahl im selben Dialog etwas bewirken.

    Gelesen wird der Quelltext der Operation: Ein Feld gilt als bedingt, wenn
    **alle** seine Lesestellen in einem ``if`` über einen Auswahl- oder
    Hakenparameter derselben Operation liegen und es in genau einem der beiden
    Zweige vorkommt. In beiden Zweigen heißt: es wirkt immer, und die
    Verzweigung betrifft etwas anderes.
    """
    names = {entry.name for entry in spec.params.spec()}
    switches = {entry.name for entry in spec.params.spec() if entry.choices or entry.kind == "bool"}
    if not switches:
        return {}
    try:
        source = textwrap.dedent(inspect.getsource(spec.fn))
    except (OSError, TypeError):  # pragma: no cover - nur bei erzeugtem Code
        return {}
    tree = ast.parse(source)

    total = dict.fromkeys(names, 0)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in names:
            total[node.attr] += 1

    found: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        governing = _read_names([node.test], switches)
        if not governing or _hands_on_the_whole_set((*node.body, *node.orelse), "params"):
            continue
        one_branch = (_read_names(node.body, names) ^ _read_names(node.orelse, names)) - governing
        for name in one_branch:
            inside = sum(
                1 for sub in ast.walk(node) if isinstance(sub, ast.Attribute) and sub.attr == name
            )
            if inside >= total[name]:
                found.setdefault(name, set()).update(governing)
    return found


def test_a_field_without_effect_says_so() -> None:
    """Jede bedingte Wirkung steht am Parameter (``depends_on``, §2.4, §10).

    Von Hand gepflegt heißt driften, und hier war es schon gedriftet: Die
    Angabe lag als Tabelle in der Oberfläche und hatte einen Eintrag, während
    fünf Operationen bedingte Felder trugen — *Kopien in Reihe oder Kreis*
    allein sechs. Wer auf „kreisförmig" stellte, sah *Abstand* und *Richtung
    X/Y/Z* bedienbar dastehen, und die Operation übergeht sie im anderen Zweig
    wortlos.

    Gefunden wird das im Quelltext der Operation und nicht durch Nachdenken —
    ``sketch_pocket.depth`` stand in keiner der beiden Durchsichten, die diesem
    Test vorausgingen, und ist trotzdem der klarste Fall: *Tiefe* vorn,
    *Durchgehend* hinten, und dessen ``doc``-Satz sagt selbst, dass die Tiefe
    dann nicht zählt.
    """
    missing: list[str] = []
    for spec in REGISTRY.all():
        declared = {entry.name for entry in spec.params.spec() if entry.depends_on is not None}
        for name, switches in conditional_fields(spec).items():
            if name in declared:
                continue
            missing.append(f"{spec.name}.{name} hängt an {', '.join(sorted(switches))}")
    assert not missing, "bedingte Felder ohne ``depends_on``:\n" + "\n".join(missing)


def test_every_dependent_field_names_a_real_switch_without_a_cycle() -> None:
    """Und andersherum: keine Angabe zeigt ins Leere oder im Kreis.

    Ein ``depends_on`` auf einen umbenannten Parameter wäre stumm wirkungslos —
    die Regel in ``_dependent_fields`` verlangt beide Namen im Dialog und
    überspringt, was sie nicht findet. Es stünde da und täte nichts, also genau
    das, was die Angabe verhindern soll.

    Geprüft wird auch die **Art** des Umschalters: Ein Wahrheitswert an einem
    Aufklappmenü oder ein Auswahlwert an einem Haken wäre eine Bedingung, die
    nie zutrifft.
    """
    for spec in REGISTRY.all():
        entries = {entry.name: entry for entry in spec.params.spec()}
        for entry in spec.params.spec():
            if entry.depends_on is None:
                continue
            controller, wanted = entry.depends_on
            assert controller in entries, f"{spec.name}: kein Steuerfeld {controller!r}"
            assert wanted, f"{spec.name}.{entry.name}: keine Werte genannt"
            assert controller != entry.name, f"{spec.name}.{entry.name} hängt an sich selbst"
            governing = entries[controller]
            for value in wanted:
                if isinstance(value, bool):
                    assert governing.kind == "bool", f"{spec.name}.{controller} ist kein Haken"
                else:
                    assert value in governing.choices, (
                        f"{spec.name}.{controller}: {value!r} ist keine Wahl"
                    )

            # Eine Kette ist erlaubt und für die Scheibentasche nötig; ein
            # Kreis hätte dagegen weder einen wirksamen noch einen klar
            # erklärbaren Zustand.
            path = {entry.name}
            current = entry
            while current.depends_on is not None:
                parent, _ = current.depends_on
                assert parent not in path, (
                    f"{spec.name}.{entry.name}: Abhängigkeitskreis bei {parent}"
                )
                path.add(parent)
                current = entries[parent]


def _title_of(spec: Any, name: str) -> str:
    """Der angezeigte Titel eines Parameters — über den Namen, nicht den Platz.

    Über den Index gesucht wäre die Prüfung beim ersten neuen Parameter still
    falsch: Sie träfe dann einen anderen Titel und ginge weiter durch.
    """
    for entry in spec.params.spec():
        if entry.name == name:
            return str(entry.title)
    raise AssertionError(f"{spec.name}: kein Parameter {name!r}")


def test_a_dependent_choice_field_greys_out_with_a_reason(window: MainWindow) -> None:
    """*Abstand* gilt nur bei der linearen Art — und sagt es, statt zu warten.

    Grau allein wäre die halbe Antwort (Regel 18): Wer ein Feld ausgegraut
    sieht, weiß nicht, welcher Schalter es freigibt. Der Tooltip nennt ihn.
    """
    spec = REGISTRY.get("pattern")
    dialog = OperationDialog(spec, {}, window)

    kind = dialog._editors["kind"]
    spacing = dialog._editors["spacing"]
    axis = dialog._editors["axis"]

    kind.setCurrentIndex(kind.findData("linear"))
    assert spacing.isEnabled(), "linear reiht mit Abstand auf"
    assert not axis.isEnabled(), "eine Achse hat nur der Kranz"

    kind.setCurrentIndex(kind.findData("circular"))
    assert not spacing.isEnabled(), "kreisförmig zählt der Winkel, nicht der Abstand"
    assert axis.isEnabled()
    hint = spacing.toolTip()
    assert hint, "ausgegraut ohne Begründung ist die halbe Antwort"
    assert _title_of(spec, "kind") in hint, hint


def test_a_dependent_field_behind_a_tick_says_which_tick(window: MainWindow) -> None:
    """Der Haken ist die zweite Sorte, und sie brauchte einen eigenen Satz.

    Über ``str()`` verglichen hieße der gesuchte Wert „True", und genau das
    stand dann im Tooltip: eine Aussage über die Bauart der Anwendung, nicht
    über ihre Bedienung. Geprüft wird deshalb beides — dass das Feld dem Haken
    folgt, und dass der Satz den Haken benennt statt seinen Wert.
    """
    spec = REGISTRY.get("orient_for_print")
    dialog = OperationDialog(spec, {}, window)

    thorough = dialog._editors["thorough"]
    candidates = dialog._editors["candidates"]

    thorough.setChecked(True)
    assert candidates.isEnabled(), "gründlich rechnet Kandidaten durch"

    thorough.setChecked(False)
    assert not candidates.isEnabled(), "ohne gründlich läuft die Heuristik"
    hint = candidates.toolTip()
    assert "True" not in hint, f"Bauart statt Bedienung: {hint!r}"
    assert _title_of(spec, "thorough") in hint, hint


# --- Wann eine Operation die falsche Wahl ist (§2.7) ----------------------------


def _with_caveat() -> list[Any]:
    """Die Operationen, die eine Grenze deklarieren."""
    return [spec for spec in REGISTRY.all() if str(spec.caveat).strip()]


def test_the_caveat_reaches_every_surface_that_offers_the_operation(window: MainWindow) -> None:
    """Zwölf Grenzen, und gelesen hat sie allein das Handbuch.

    ``caveat`` sagt, wann eine Operation die falsche Wahl ist („Nicht ohne
    Entlüftung, wenn im Slicer Stützen entstehen"). Die einzige Lesestelle im
    ganzen Programm war ``documentation()`` — nicht der Dialog, in dem gerade
    jemand die Operation anwendet, nicht der Tooltip am Menüeintrag daneben,
    und nicht die Werkzeugliste des Agenten. Der Docstring des Feldes rechnet
    selbst mit der Oberfläche: „dann steht neben jedem Menüeintrag eine
    Warnung".

    Geprüft wird jede der drei Stellen, und zwar für **jede** Operation mit
    Grenze: Eine Stichprobe wäre grün, sobald eine einzige durchkommt.
    """
    from app.core.registry import caveat_line, tool_schemas

    specs = _with_caveat()
    assert len(specs) >= 5, "die Prüfung braucht Operationen mit Grenze"

    schemas = {entry["name"]: entry["description"] for entry in tool_schemas()}
    for spec in specs:
        line = caveat_line(spec)
        assert str(spec.caveat) in line, spec.name
        assert line != str(spec.caveat), f"{spec.name}: die Grenze braucht ihr Vorwort"

        # Der Agent wählt aus derselben Auskunft wie ein Mensch (§10).
        assert str(spec.caveat) in schemas[spec.name], f"{spec.name}: der Agent sieht sie nicht"

        # Der Menüeintrag: im Tooltip, nicht in der Statuszeile — die ist eine
        # Zeile, und abgeschnitten wäre eine Warnung schlimmer als keine.
        action = window._operation_action(QMenu(window), spec)
        assert str(spec.caveat) in action.toolTip(), f"{spec.name}: kein Tooltip"
        assert str(spec.doc) in action.toolTip(), f"{spec.name}: der Satz fehlt daneben"

        # Und der Dialog, in dem sie gerade angewendet wird.
        dialog = OperationDialog(spec, {}, window)
        assert dialog._caveat is not None, f"{spec.name}: kein Label"
        assert str(spec.caveat) in dialog._caveat.text(), f"{spec.name}: leer"
        assert dialog._caveat.isVisibleTo(dialog), f"{spec.name}: unsichtbar"


def test_an_operation_without_a_caveat_shows_no_empty_warning(window: MainWindow) -> None:
    """Wo keine Grenze ist, steht keine.

    Ein Vorbehalt an jeder Operation wäre keiner mehr — das steht so in der
    Deklaration des Feldes, und es gilt auch für ein leeres Label, das Platz
    nimmt und nichts sagt.
    """
    spec = next(entry for entry in REGISTRY.all() if not str(entry.caveat).strip())
    dialog = OperationDialog(spec, {}, window)

    assert dialog._caveat is not None, "das Label wird immer gebaut"
    assert not dialog._caveat.isVisibleTo(dialog), f"{spec.name}: leeres Warnfeld"
    assert not dialog._caveat.text()


# --- Die Anzeigeeinheit im Zahlenfeld (§19.3, §11.1) ----------------------------


def _length_param(spec: Any) -> Any:
    """Der erste Parameter dieser Operation, der eine Länge ist."""
    return next(entry for entry in spec.params.spec() if entry.unit == "mm")


def test_a_field_in_inches_takes_inches_and_returns_millimetres(window: MainWindow) -> None:
    """Der Kern bleibt bei Millimetern, das Feld spricht die Anzeigeeinheit.

    Vorher trug jedes Feld „[mm]" aus dem Schema und nahm Millimeter, gleich
    was eingestellt war — die Umschaltung erreichte die Anzeigen und hörte an
    der Eingabe auf. Nur das Kürzel zu tauschen wäre schlimmer gewesen: „20,00
    in" über einem Wert von 20 mm behauptet 20 Zoll.

    Geprüft wird die ganze Kette: die Beschriftung, der eingetragene Wert, und
    was ``values()`` an den Stapel gibt.
    """
    from app.ui.labels import set_display_unit

    spec = REGISTRY.get("create_box")
    entry = _length_param(spec)
    default_mm = float(entry.default)
    assert default_mm > 0.0, "der Test braucht eine Vorgabe größer als null"

    set_display_unit("in")
    dialog = OperationDialog(spec, {}, window)
    field = dialog._editors[entry.name]

    # Der gezeigte Wert ist umgerechnet …
    assert field.spin.value() == pytest.approx(default_mm / 25.4, abs=1e-4)
    # … und die Beschriftung sagt es. Sonst wäre die Zahl eine Behauptung.
    label = dialog._rows[entry.name].labelForField(field)
    assert label is not None and "[in]" in label.text(), label.text() if label else "kein Label"

    # Was der Stapel bekommt, ist Millimeter (§11.1).
    assert dialog.values()[entry.name] == pytest.approx(default_mm, abs=1e-6)

    # Und ein getippter Zollwert kommt als Millimeter an.
    field.spin.setValue(1.0)
    assert dialog.values()[entry.name] == pytest.approx(25.4, abs=1e-6)


def test_an_angle_stays_in_degrees(window: MainWindow) -> None:
    """Umgerechnet wird, was eine Länge ist — und sonst nichts.

    Dreißig Parameter tragen einen Winkel. „45 Zoll" wäre keine Umschaltung
    mehr, sondern ein Fehler mit Einstellung.
    """
    from app.ui.labels import set_display_unit
    from app.ui.op_dialog import shown_unit

    spec = REGISTRY.get("pattern")
    angle = next(entry for entry in spec.params.spec() if entry.name == "angle")
    assert angle.unit in {"grad", "°"}, angle.unit

    set_display_unit("in")
    assert shown_unit(angle) is None, "ein Winkel wird nicht umgerechnet"

    dialog = OperationDialog(spec, {}, window)
    assert dialog.values()["angle"] == pytest.approx(float(angle.default), abs=1e-6)


def test_an_expression_survives_the_unit(window: MainWindow) -> None:
    """Ein Parameterausdruck bleibt wörtlich — in jeder Einheit.

    „=@breite/2" umzurechnen hieße, die Bindung in eine Zahl zu verwandeln;
    §13 rechnet ohnehin in Millimetern, und was hier steht, ist keine Zahl.
    """
    from app.ui.labels import set_display_unit

    spec = REGISTRY.get("create_box")
    entry = _length_param(spec)

    set_display_unit("in")
    dialog = OperationDialog(spec, {}, window, values={entry.name: "=@breite / 2"})

    assert dialog.values()[entry.name] == "=@breite / 2"


def test_a_fine_field_keeps_its_precision_in_inches(window: MainWindow) -> None:
    """Ein Feld für Toleranzen braucht in Zoll mehr Stellen, nicht dieselben.

    Ein Hundertstelmillimeter ist ein Vierteltausendstel Zoll. Mit zwei Stellen
    wäre das Spiel aus einem Materialprofil nicht eintippbar — das Feld zeigte
    eine Genauigkeit, die es nicht annimmt.
    """
    from app.core.units import decimals_for
    from app.ui.labels import set_display_unit
    from app.ui.op_dialog import _decimals_for

    spec = REGISTRY.get("create_box")
    entry = _length_param(spec)

    set_display_unit("mm")
    in_mm = _decimals_for(entry, "mm")
    set_display_unit("in")
    in_inches = _decimals_for(entry, "in")

    assert in_mm == 2
    assert in_inches == decimals_for("in") >= 4
    assert in_inches > in_mm


def test_looking_at_a_dialog_in_inches_changes_nothing(window: MainWindow) -> None:
    """Ein Dialog, den man nur ansieht, verschiebt kein Maß.

    Der Fund kam aus dem Test darüber: 40 mm sind 1,5748 Zoll, und aus 1,5748
    Zoll werden 39,99992 mm. Die Anzeige rundet auf ihre vier Stellen, und die
    Rückrechnung schriebe diese Rundung als Wert fest — wer im Verlauf eine
    Operation aufschlägt, sie ansieht und bestätigt, hätte jedes ihrer Maße um
    den Rundungsfehler verschoben. Bei drei Feldern eines Quaders dreimal.

    Geprüft wird **jeder** Längenparameter jeder Operation, denn der Fehler
    hängt an der Zahl: 40 trifft es, 25,4 nicht.
    """
    from app.ui.labels import set_display_unit

    set_display_unit("in")
    verschoben: list[str] = []
    for spec in REGISTRY.all():
        lengths = [entry for entry in spec.params.spec() if entry.unit == "mm"]
        if not lengths:
            continue
        dialog = OperationDialog(spec, {}, window)
        entered = dialog.values()
        for entry in lengths:
            if not isinstance(entry.default, (int, float)):
                continue
            back = entered.get(entry.name)
            if isinstance(back, str):
                continue  # ein Ausdruck, kein Maß
            if abs(float(back) - float(entry.default)) > 1e-9:
                verschoben.append(f"{spec.name}.{entry.name}: {entry.default} → {back}")
    assert not verschoben, "Ansehen hat Maße verschoben:\n" + "\n".join(verschoben)


def test_the_condition_reaches_every_surface(window: MainWindow) -> None:
    """Eine Quelle, vier Oberflächen — das war der Grund für den Umbau.

    Die Angabe lag als Tabelle in ``op_dialog`` und hatte damit genau *eine*
    Oberfläche: den Dialog. Ihr eigener Kopf nannte die Schwelle, ab der sie an
    den Parameter gehört, und mit elf Einträgen stand sie darüber. Jetzt liest
    jede Oberfläche ``ParamSpec.depends_on``:

    * der **Dialog** graut das Feld aus und sagt, woran es liegt,
    * das **Handbuch** schreibt die Bedingung in die Parametertabelle,
    * der **Agent** bekommt sie in der Werkzeugbeschreibung.

    Die vierte ist die Kommandozeile, und sie liest dasselbe Schema — geprüft
    wird sie über ``json_schema``, aus dem auch ihre Argumente entstehen.

    Der Agent bekommt dabei **Schlüssel**, der Mensch **Namen**: „Gilt bei Art
    = circular" hilft im Handbuch und wäre für den Agenten eine Zuordnung, die
    er raten müsste — er setzt ``kind``.
    """
    from app.core.registry import documentation, tool_schemas
    from app.core.registry.params import condition_text

    conditional = [
        (spec, entry)
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.depends_on is not None
    ]
    assert len(conditional) >= 10, f"nur {len(conditional)} bedingte Felder gefunden"

    schemas = {item["name"]: item["input_schema"]["properties"] for item in tool_schemas()}
    handbook = documentation()

    for spec, entry in conditional:
        schema = spec.params.spec()

        # Der Agent — mit Schlüsseln, und nur wenn er den Parameter überhaupt
        # angeboten bekommt (Gestenfelder bekommt er nicht, §26).
        properties = schemas[spec.name]
        if entry.name in properties:
            keyed = condition_text(entry, schema, keys=True)
            assert keyed, f"{spec.name}.{entry.name}: kein Satz"
            assert entry.depends_on[0] in keyed, f"{spec.name}.{entry.name}: {keyed}"
            assert keyed in properties[entry.name]["description"], (
                f"{spec.name}.{entry.name} fehlt dem Agenten"
            )

        # Das Handbuch — mit Namen.
        named = condition_text(entry, schema)
        assert named in handbook, f"{spec.name}.{entry.name} fehlt im Handbuch: {named}"

        # Und der Dialog: das Feld folgt seinem Umschalter.
        dialog = OperationDialog(spec, {}, window)
        if entry.name not in dialog._editors:
            continue
        controller, wanted = entry.depends_on
        switch = dialog._editors[controller]
        field = dialog._editors[entry.name]
        if isinstance(wanted[0], bool):
            switch.setChecked(not wanted[0])
        else:
            other = next(
                value
                for value in next(item for item in schema if item.name == controller).choices
                if value not in wanted
            )
            switch.setCurrentIndex(switch.findData(other))
        assert not field.isEnabled(), f"{spec.name}.{entry.name} bleibt bedienbar"
        assert field.toolTip(), f"{spec.name}.{entry.name}: ausgegraut ohne Begründung"


def test_a_nested_condition_follows_the_whole_chain(window: MainWindow) -> None:
    """Ein angehaktes, aber selbst unwirksames Feld darf nichts freischalten.

    Beim Schraubenloch lässt sich die Scheibe nur ohne Senkkopf einlassen. Wer
    sie anhakt und danach den Senkkopf wieder einschaltet, behält den Haken zur
    späteren Rückkehr — *Spiel* muss trotzdem grau werden, weil die Operation
    in diesem Zweig weder Scheibe noch Spiel benutzt. Dieselbe vollständige
    Kette brauchen Handbuch und Agent.
    """
    from app.core.registry.params import condition_text

    spec = REGISTRY.get("insert_screw_hole")
    entries = {entry.name: entry for entry in spec.params.spec()}
    play_condition = condition_text(entries["play"], spec.params.spec(), keys=True)

    assert "washer" in play_condition
    assert "countersink" in play_condition

    dialog = OperationDialog(spec, {}, window)
    countersink = dialog._editors["countersink"]
    washer = dialog._editors["washer"]
    play = dialog._editors["play"]

    countersink.setChecked(False)
    washer.setChecked(True)
    assert washer.isEnabled() and play.isEnabled()

    countersink.setChecked(True)
    assert not washer.isEnabled()
    assert not play.isEnabled()
    assert "Senkkopf" in play.toolTip()


def test_both_ways_into_a_dialog_carry_the_feature_names(window: MainWindow) -> None:
    """Auf dem Menüweg zeigte das Feld „An Fläche" die rohe Kennung.

    ``launch_operation`` — der Weg des Kontextmenüs am Merkmal (Weg 1) und der
    Menüs *Erzeugen* und *Ändern* — baute den Dialog ohne ``features``. Ohne
    Liste macht der Dialog seine Auswahl aus dem *Wert*: Aus „hole_1" wurde ein
    Eintrag „hole_1", und die übrigen Flächen des Körpers kannte er nicht.
    Gemessen: ohne Liste „hole_1", mit Liste „Bohrung 1 · Ø5,2".

    Nur ``edit_operation`` übergab sie. Geprüft wird deshalb nicht der Dialog —
    den halten die Tests daneben längst fest —, sondern **beide Aufrufer**: Wer
    einen dritten baut, soll hier auffallen.
    """
    import inspect

    from app.ui import main_window as module

    source = inspect.getsource(module.MainWindow)
    calls = source.count("dialog = OperationDialog(")
    assert calls >= 2, "es gibt nicht mehr zwei Wege in den Dialog — dieser Test ist veraltet"
    assert source.count("features=self._feature_names(),") == calls, (
        f"{calls} Aufrufe von OperationDialog, aber "
        f"{source.count('features=self._feature_names(),')} übergeben die Merkmale"
    )


def test_a_number_field_stays_as_wide_as_a_number(window: MainWindow) -> None:
    """Zahlenfelder wuchsen auf die ganze Dialogbreite.

    ``QFormLayout`` wächst nach Vorgabe mit, und die Breite des Dialogs kommt vom
    umgebrochenen Beschreibungssatz. Gemessen am gezeigten Dialog:
    ``decimate_mesh.triangles`` bekam 366 Pixel für einen Wunsch von 120,
    ``smooth_mesh.iterations`` 342 für 60. Die Zahl klebte links, die Drehknöpfe
    saßen dreihundert Pixel weiter rechts, dazwischen leere Fläche — in jedem
    Operationsdialog.

    Gedeckelt wird nur die Zahl. Aufklappmenüs und Textfelder wachsen weiter:
    Dort *ist* die Breite der Inhalt („Bohrung 1 · Ø5,2 mm"), und ein Deckel
    darauf schnitte ab. Deshalb kein ``FieldsStayAtSizeHint`` für das ganze
    Formular — und deshalb prüft dieser Test beides.
    """
    from PySide6.QtWidgets import QComboBox, QSpinBox

    from app.core.registry import REGISTRY
    from app.ui.op_dialog import NUMBER_AIR, OperationDialog, ValueField

    for name in ("decimate_mesh", "smooth_mesh"):
        dialog = OperationDialog(REGISTRY.get(name), {"obj_1": "Halterung"}, window)
        try:
            dialog.show()
            dialog.resize(dialog.sizeHint())
            QApplication.processEvents()
            boxes = dialog.findChildren(QSpinBox)
            assert boxes, f"{name} hat kein Zahlenfeld — dieser Test prüft nichts"
            for box in boxes:
                assert box.width() <= box.sizeHint().width() + NUMBER_AIR, (
                    f"{name}: {box.width()} px für einen Wunsch von {box.sizeHint().width()}"
                )
        finally:
            dialog.deleteLater()

    # Und das Gegenstück: was den Platz braucht, bekommt ihn weiter.
    dialog = OperationDialog(REGISTRY.get("pattern"), {"obj_1": "Halterung"}, window)
    try:
        dialog.show()
        dialog.resize(dialog.sizeHint())
        QApplication.processEvents()
        combos = dialog.findChildren(QComboBox)
        assert combos, "ohne Aufklappmenü prüft die zweite Hälfte nichts"
        assert max(box.width() for box in combos) > 200, (
            "die Auswahl ist so schmal wie ein Zahlenfeld — dann wurde zu viel gedeckelt"
        )
        fields = dialog.findChildren(ValueField)
        for field in fields:
            assert field.spin.width() <= field.spin.sizeHint().width() + NUMBER_AIR, (
                f"das Drehfeld wuchs auf {field.spin.width()} px"
            )
    finally:
        dialog.deleteLater()


def test_switching_to_an_expression_starts_from_millimetres(window: MainWindow) -> None:
    """Der Ausdruck beginnt bei der Größe, nicht bei ihrer Anzeige.

    Ein Parameterausdruck rechnet in Millimetern (§13). Vorbelegt wurde er aus
    dem Drehfeld, also aus dem Anzeigewert: In Zoll stand nach einem Klick auf
    den Umschalter „=1.5748" dort, wo 40 mm gemeint waren — und der Hinweis
    darunter beschriftete es mit „mm", bezeugte den Fehler also selbst.

    Ein Anzeigefehler wäre halb so schlimm. Der Ausdruck landet im Dokument.
    """
    from app.ui.labels import set_display_unit

    spec = REGISTRY.get("create_box")
    entry = _length_param(spec)
    default_mm = float(entry.default)

    set_display_unit("in")
    dialog = OperationDialog(spec, {}, window)
    try:
        field = dialog._editors[entry.name]
        assert field.spin.value() == pytest.approx(default_mm / 25.4, abs=1e-4), (
            "das Feld muss Zoll zeigen, sonst prüft der Test nichts"
        )

        field.toggle.setChecked(True)

        assert field.text.text() == f"={default_mm:g}", field.text.text()
        # Und der Hinweis stimmt mit dem Ausdruck überein, statt ihn zu widerlegen.
        assert f"{default_mm:g} mm" in field.hint.text(), field.hint.text()
        # Was der Stapel bekommt, ist der Ausdruck — wörtlich, in Millimetern.
        assert dialog.values()[entry.name] == f"={default_mm:g}"
    finally:
        dialog.deleteLater()


# --- Der Satz an beiden Hälften der Zeile ----------------------------------------


def _rows_of(dialog: OperationDialog) -> list[tuple[str, QWidget, QWidget | None]]:
    """Jede Zeile des Dialogs als (Name, Feld, Beschriftung)."""
    rows = []
    for name, editor in dialog._editors.items():
        form = dialog._rows.get(name)
        rows.append((name, editor, form.labelForField(editor) if form is not None else None))
    return rows


def test_every_parameter_explains_itself_at_both_halves_of_its_row(window: MainWindow) -> None:
    """457 Parameter tragen einen ``doc``-Satz, und er stand nur am Feld.

    Wer eine Zeile nicht versteht, zeigt auf das unverständliche Wort — auf die
    Beschriftung, nicht auf den Kasten daneben. Gemessen an vier Dialogen:
    siebenundvierzig Zeilen, siebenundvierzig Sätze am Feld, null an der
    Beschriftung. Dieselbe Lücke wie in den Druckeinstellungen, nur eine Ebene
    höher und mit zehnmal so vielen Feldern.

    Über das ganze Register, nicht über eine Auswahl: Ein Dialog, der als
    einziger stumm bleibt, ist genau der Fall, den eine Stichprobe verpasst.
    """
    silent: list[str] = []
    without_label = 0
    checked = 0
    for spec in REGISTRY.all():
        dialog = OperationDialog(spec, {}, window)
        try:
            docs = {entry.name: str(entry.doc or "") for entry in spec.params.spec()}
            for name, editor, caption in _rows_of(dialog):
                sentence = docs.get(name, "")
                if not sentence:
                    continue
                if not editor.isEnabled():
                    # Eine gesperrte Zeile trägt den Grund und nicht ihren
                    # eigenen Satz — vier Parameter stehen beim Öffnen so da.
                    # Geprüft wird das im Test darunter.
                    continue
                checked += 1
                if editor.toolTip() != sentence:
                    silent.append(f"{spec.name}.{name}: Feld trägt {editor.toolTip()!r}")
                if editor.accessibleDescription() != sentence:
                    silent.append(f"{spec.name}.{name}: kein accessibleDescription")
                if caption is None:
                    without_label += 1
                    continue
                if caption.toolTip() != sentence:
                    silent.append(f"{spec.name}.{name}: Beschriftung trägt {caption.toolTip()!r}")
                if caption.statusTip() != sentence:
                    silent.append(f"{spec.name}.{name}: Beschriftung ohne statusTip")
        finally:
            dialog.reject()
            dialog.deleteLater()

    assert checked > 400, f"nur {checked} Parameter geprüft — die Schleife greift nicht"
    assert not silent, f"{len(silent)} stumme Hälften:\n" + "\n".join(silent[:25])


def test_a_greyed_out_row_says_why_on_both_halves(window: MainWindow) -> None:
    """Und bei einer gesperrten Zeile ist der Grund die Auskunft, die zählt.

    In ein ausgegrautes Feld zeigt niemand — man zeigt auf das Wort davor und
    fragt, warum es grau ist. Der Grund stand nur im Feld.
    """
    spec = REGISTRY.get("orient_for_print")
    dialog = OperationDialog(spec, {}, window)

    candidates = dialog._editors["candidates"]
    caption = dialog._rows["candidates"].labelForField(candidates)
    assert caption is not None

    dialog._editors["thorough"].setChecked(False)
    assert not candidates.isEnabled()
    assert candidates.toolTip() == caption.toolTip(), "beide Hälften sagen dasselbe"
    assert _title_of(spec, "thorough") in caption.toolTip(), caption.toolTip()

    dialog._editors["thorough"].setChecked(True)
    assert candidates.isEnabled()
    assert candidates.toolTip() == caption.toolTip()
    assert _title_of(spec, "thorough") not in caption.toolTip(), "wieder der eigene Satz"


def test_a_drawn_sketch_puts_its_own_size_into_the_dialog(qt_app: QApplication) -> None:
    """Was im Maßfeld steht, muss stimmen — sonst liest der Kunde die falsche Zahl.

    ``_regions_for`` nimmt bei gesetzter Skizze **weder** Grundform **noch**
    Länge, Breite oder Ecken: ``if not sketch_text`` entscheidet, und mit einer
    Zeichnung ist der andere Zweig gemeint. Der Dialog zeigte trotzdem die
    Vorgaben der Operation — gemessen am 25.08.2026 stand dort 40 mal 20 neben
    einer Zeichnung von 50 mal 30.

    Also beides geprüft: dass die Zahlen aus der Zeichnung kommen, und dass die
    Zeile sagt, dass man sie dort nicht ändert (§2.5, „ein Feld ohne Wirkung
    sagt es").
    """
    bootstrap.load_operations()
    spec = REGISTRY.get("sketch_extrude")
    dialog = OperationDialog(
        spec, [], None, values={"sketch": sketch_to_text(shapes.rectangle(50.0, 30.0))}
    )
    try:
        werte = dialog.values()

        assert werte["length"] == pytest.approx(50.0), "die Länge kommt aus der Zeichnung"
        assert werte["width"] == pytest.approx(30.0), "die Breite auch"

        for name in ("shape", "length", "width"):
            editor = dialog._editors[name]
            assert not editor.isEnabled(), f"{name} wirkt nicht und ist trotzdem bedienbar"
            assert "Zeichnung" in editor.toolTip(), f"{name} sagt nicht, woher sein Wert kommt"
    finally:
        release = getattr(type(dialog), "release", None)
        if release is not None:
            release(dialog)
        dialog.deleteLater()


def test_without_a_sketch_the_shape_fields_still_work(qt_app: QApplication) -> None:
    """Die Gegenrichtung: Ohne Zeichnung sind die Felder das, was zählt.

    Ohne sie wäre die Sperre oben eine, die immer greift — und die Grundform
    als Weg zu einem Körper gäbe es nicht mehr.
    """
    bootstrap.load_operations()
    dialog = OperationDialog(REGISTRY.get("sketch_extrude"), [], None)
    try:
        assert dialog._editors["length"].isEnabled(), "ohne Zeichnung zählt das Maßfeld"
        assert dialog._editors["shape"].isEnabled()
    finally:
        release = getattr(type(dialog), "release", None)
        if release is not None:
            release(dialog)
        dialog.deleteLater()


def test_the_sketch_measures_a_circle_by_its_region_not_its_points(
    qt_app: QApplication,
) -> None:
    """Ein Kreis trägt Mitte und **einen** Randpunkt — aus den rohen Punkten
    gerechnet maß ein Kreis Ø 50 „25", und die Zahl stand schreibgeschützt im
    Maßfeld. Gemessen wird über die Regionen, dieselbe Kette wie im Kern.

    Fund des Reviews vom 26.08.2026 — genau der Fehler, gegen den
    ``sketch_extent`` geschrieben wurde, eine Elementsorte weiter.
    """
    bootstrap.load_operations()
    spec = REGISTRY.get("sketch_extrude")
    dialog = OperationDialog(spec, [], None, values={"sketch": sketch_to_text(shapes.circle(50.0))})
    try:
        werte = dialog.values()
        assert werte["length"] == pytest.approx(50.0), "der Durchmesser, nicht der Radius"
        assert werte["width"] == pytest.approx(50.0)
    finally:
        release = getattr(type(dialog), "release", None)
        if release is not None:
            release(dialog)
        dialog.deleteLater()


def test_a_deleted_sketch_gives_the_measure_fields_back(qt_app: QApplication) -> None:
    """Die Sperre der Maßfelder war einseitig: Wer die Zeichnung löschte,
    behielt graue Felder mit der Begründung „Die Maße kommen aus der
    Zeichnung" — während der Kern die Felder längst wieder nahm. Sackgasse
    (§2.1), gefunden im Review vom 26.08.2026.
    """
    from app.ui.sketch_editor import SketchField

    bootstrap.load_operations()
    spec = REGISTRY.get("sketch_extrude")
    dialog = OperationDialog(
        spec, [], None, values={"sketch": sketch_to_text(shapes.rectangle(50.0, 30.0))}
    )
    try:
        assert not dialog._editors["length"].isEnabled(), "mit Zeichnung ist das Feld gesperrt"

        field = dialog._editors["sketch"]
        assert isinstance(field, SketchField)
        field.set_text("")

        for name in ("shape", "length", "width"):
            editor = dialog._editors[name]
            assert editor.isEnabled(), f"{name} muss nach dem Löschen wieder bedienbar sein"
            assert "Zeichnung" not in editor.toolTip(), (
                f"{name} begründet eine Sperre, die es nicht mehr gibt"
            )
    finally:
        release = getattr(type(dialog), "release", None)
        if release is not None:
            release(dialog)
        dialog.deleteLater()


def test_a_part_dialog_offers_to_insert_not_to_name_the_part(qt_app: QApplication) -> None:
    """Der Hauptknopf nennt die Handlung — bei Bausteinen ist der Titel keine.

    „Bohrung setzen" ist ein Verb und darf auf den Knopf; „Lochwand-Einhänger"
    ist ein Ding, und ein Knopf, der ein Ding heißt, sagt nicht, was der Klick
    tut (Robert, 25.08.2026). Bausteindialoge sagen „Einsetzen", der
    Fenstertitel nennt den Baustein; gewöhnliche Operationen behalten ihren
    handelnden Titel.
    """
    from PySide6.QtWidgets import QDialogButtonBox

    from app.core.knowledge.parts.ops import op_name

    part = REGISTRY.get(op_name("nut_trap"))
    dialog = OperationDialog(part, [], None)
    try:
        ok = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None and ok.text() == "Einsetzen"
        assert part.category == "parts", "sonst prüft dieser Test die falsche Sorte"
    finally:
        release = getattr(type(dialog), "release", None)
        if release is not None:
            release(dialog)
        dialog.deleteLater()

    plain = REGISTRY.get("drill_hole")
    # Ein eigener Name: Die zweite Zuweisung auf ``dialog`` nahm dem ersten
    # Fenster die letzte Referenz, und aufgeräumt wurde danach nur noch eines.
    plain_dialog = OperationDialog(plain, [], None)
    try:
        ok = plain_dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None and ok.text() == str(plain.title), "ein Verb bleibt auf dem Knopf"
    finally:
        release = getattr(type(plain_dialog), "release", None)
        if release is not None:
            release(plain_dialog)
        plain_dialog.deleteLater()


def test_the_source_field_offers_a_way_to_pick_a_file(qt_app: QApplication) -> None:
    """Ein leeres Projekt war in den drei Einstiegsdialogen eine Sackgasse.

    *Modell laden*, *STEP laden* und *Zeichnung hochziehen* zeigen im Feld
    „Quelle" die Dateien, die das Projekt schon eingebettet hat — in einem
    frischen Projekt also keine. Die Liste klappte auf und war leer; das liest
    sich nicht als „hier fehlt etwas", sondern als kaputt. Wer über Drag & Drop
    kam, merkte davon nichts; wer die Operation aus dem Menü rief, klickte ins
    Leere (Regel 19: keine Sackgassen).

    **Das Bildfeld hatte seinen Wähler seit je** — derselbe Fall, eine Zeile
    weiter oben im selben Zweig, und nur einer der beiden hatte den Ausweg.

    Ohne Rückruf bleibt es die reine Liste: Ein Aufrufer, der keine Dateien
    einbetten kann, soll keinen Knopf zeigen, der nichts tut.
    """
    from PySide6.QtWidgets import QComboBox

    from app.ui.op_dialog import ImageSourceField, OperationDialog

    for name in ("load", "load_step", "load_outline"):
        spec = REGISTRY.get(name)

        plain = OperationDialog(spec, {})
        assert isinstance(plain._editors.get("source"), QComboBox), (
            f"{name}: ohne Rückruf bleibt es die Liste"
        )

        with_pick = OperationDialog(spec, {}, pick_source=lambda: ("src_1", "teil.stl"))
        editor = with_pick._editors.get("source")
        assert isinstance(editor, ImageSourceField), f"{name}: kein Weg zu einer Datei"
        assert not editor.button.isHidden(), f"{name}: der Knopf ist da, aber unsichtbar"
        assert "wählen" in editor.button.text(), f"{name}: {editor.button.text()!r}"


def test_the_material_is_chosen_not_typed(qt_app: QApplication) -> None:
    """Ein Feld, das nur sechs Zeichenketten annimmt, muss sie auch nennen.

    Hier stand ein Textfeld, und der Kunde musste die **Kennung** erraten: Wer
    „PETG" tippte — so steht es in der Kopfzeile, im Druckdialog und auf jeder
    Spule — bekam „Dieses Materialprofil ist nicht bekannt.", denn intern
    heißt es ``petg`` (Robert, 27.08.2026, am laufenden Fenster).

    Gefüllt wird zur Laufzeit aus dem Katalog, nicht aus einer festen Liste im
    Schema: ``profiles.reload()`` verwirft den Cache ausdrücklich, „etwa
    nachdem der Nutzer ein Profil bearbeitet hat". Eine Aufzählung wäre am Tag
    richtig, an dem sie geschrieben wird.
    """
    from app.core.knowledge import profiles
    from app.ui.op_dialog import MaterialField

    feld = MaterialField("")
    kennungen = [feld.itemData(i) for i in range(feld.count())]

    # Erst „wie das Projekt", dann jedes bekannte Material.
    assert kennungen[0] == "", 'die Vorgabe steht oben und heißt nicht „abs"'
    assert set(kennungen[1:]) == set(profiles.material_profiles()), (
        "der Wähler zeigt den Katalog, nicht eine Auswahl daraus"
    )

    # Sichtbar der Titel, Wert die Kennung — sonst wandert ein übersetzter
    # Text in die Projektdatei.
    petg = kennungen.index("petg")
    assert feld.itemText(petg) == "PETG"
    assert MaterialField("petg").value() == "petg"

    # Und was der Kunde nicht ändert, bleibt leer statt ein Material zu erfinden.
    assert MaterialField("").value() == ""


def test_the_material_kind_is_known_to_the_agent_schema() -> None:
    """Jede Parameterart braucht **zwei** Einträge, nicht einen.

    Der Dialog verzweigt über ``entry.kind``, und ``json_schema`` schlägt
    dieselbe Art in einer Tabelle nach. Wer nur den Dialog bedient, bekommt
    beim ersten Agentenaufruf ein ``KeyError`` — gemessen, bevor dieser Test
    entstand. Der Hinweis darauf kam von der Sitzung, die dieselbe Falle beim
    Filamentwähler hatte.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.registry.params import json_schema

    load_operations()
    spec = next(s for s in REGISTRY.all() if s.name == "set_material")
    schema = json_schema(spec.params)
    assert schema["properties"]["material"]["type"] == "string"


def test_a_required_feature_offers_no_empty_choice(qt_app: QApplication) -> None:
    """Keine Vorauswahl, die beim Übernehmen sicher abgelehnt wird.

    Der Merkmalswähler stellte „— keines —" an die erste Stelle, also
    **vorausgewählt** — auch bei Operationen, die ohne Merkmal ablehnen.
    Robert las den Eintrag als „das ganze Teil", klickte Übernehmen und bekam
    „Zum Färben gehört eine Fläche." (27.08.2026). Die naheliegendste Lesart,
    und keine, der irgendwo widersprochen wurde.

    Der Grund lag eine Ebene tiefer: ``required`` kam aus ``not has_default``,
    und diese drei Felder tragen eine Vorgabe — den leeren Wert, den der Klick
    einsetzt (§21.3). Eine Vorgabe macht ein Feld aber nicht optional.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()

    # **Genau eine** Operation lehnt ohne Merkmal ab, und sie sagt es.
    spec = next(s for s in REGISTRY.all() if s.name == "paint_slot")
    feature = next(p for p in spec.params.spec() if str(p.kind) == "feature")
    assert feature.required, "paint_slot braucht seine Fläche und muss das sagen"

    # **Und die Deckel gehören ausdrücklich nicht dazu** — hier stand das
    # einmal anders, und drei Tests fielen: Beide nutzen ``plane_of``, das bei
    # leerem Namen auf die Zahl zurückfällt, und das ausgelieferte Beispiel
    # lässt das Merkmal leer. Hergeleitet war der Irrtum daraus, dass die
    # Datei ``ValidationError`` zu ``at_feature`` wirft — sie wirft aber für
    # ein **untaugliches** Merkmal, nicht für ein fehlendes. Ein Muster im
    # Text ist keine Aussage über das Verhalten.
    for name in ("create_lid", "screw_lid"):
        andere = next(s for s in REGISTRY.all() if s.name == name)
        feld = next(p for p in andere.params.spec() if str(p.kind) == "feature")
        assert not feld.required, f"{name} kommt ohne Merkmal aus (plane_of fällt zurück)"

    # Und die übrigen kommen weiterhin ohne aus — der leere Eintrag bleibt
    # dort richtig, sonst nähme man dem Kunden eine gültige Wahl.
    optional = [
        s.name
        for s in REGISTRY.all()
        for p in s.params.spec()
        if str(p.kind) == "feature" and not p.required
    ]
    assert len(optional) > 20, "die Ausnahme sind die drei, nicht die Regel"
    assert "insert_screw_hole" in optional, "ein Baustein ohne Merkmal geht an den Ursprung"


def test_every_feature_kind_has_a_name_in_the_tree(qt_app: QApplication) -> None:
    """Keine Merkmalsart darf im Baum ihre Kennung zeigen.

    Der Fall ist dreimal aufgetreten und zweimal halb behoben worden: Erst
    stand „face_2" im Objektbaum, dann „fillet_1", und am 27.08.2026 fanden
    sich „thread_1" und „pin_1" — englische Kennungen in der Oberfläche, an
    ``tr()`` vorbei. Der Kommentar über der Verrundung beschreibt die Falle
    genau, aber wer sie dort schloss, hat die Zwillinge nicht gesucht.

    **Deshalb prüft dieser Test die Art, nicht die Fälle.** Er zählt über
    ``FeatureKind``; kommt eine Art dazu und niemand gibt ihr einen Namen,
    fällt er, statt dass es ein Kunde im Baum liest. Genau das konnten die
    bisherigen Tests nicht: Sie fragen, *ob* ein Merkmal da ist, nicht, *was*
    dort steht.
    """
    import typing

    from app.core.types import Feature, FeatureKind
    from app.ui.labels import feature_measure, feature_name

    arten = typing.get_args(FeatureKind)
    assert len(arten) >= 9, "sonst prüft dieser Test nichts"

    ohne_namen = []
    ohne_mass = []
    for art in arten:
        merkmal = Feature(
            id=f"{art}_1",
            kind=art,
            provenance="detected",
            params={"diameter": 8.0, "pitch": 1.25, "radius": 2.0},
        )
        name = feature_name(merkmal.id, merkmal)
        # Die Kennung selbst ist die Rückfallebene — und genau das Versagen.
        if name == merkmal.id or art in name:
            ohne_namen.append(art)
        # **Der Zwilling zwei Funktionen weiter**, beim ersten Mal
        # übersehen: Der Objektbaum hat zwei Spalten, und repariert wurde
        # eine. Zapfen und Gewinde trugen ihren Namen und daneben nichts.
        if not feature_measure(merkmal):
            ohne_mass.append(art)

    assert not ohne_mass, "diese Arten zeigen im Baum kein Maß: " + ", ".join(ohne_mass)
    assert not ohne_namen, "diese Arten zeigen im Baum ihre englische Kennung: " + ", ".join(
        ohne_namen
    )


def test_a_twin_toggle_says_what_it_takes_away() -> None:
    """Ein Umschalter, der Felder wegnimmt, nennt sie — vor dem Klick.

    Die vier Zwillingspaare (``MENU_TWINS``) sind dieselbe Handlung in zwei
    Rechenkernen, und der Haken im Dialog ist der Weg von einem zum anderen.
    Nur sind sie nicht deckungsgleich: Beim Aushöhlen kann der Mesh-Kern vier
    Dinge (Wand, offene Oberseite, Entlüftung, Lochdurchmesser), der exakte
    eines. Wer den Haken setzt, verliert drei Felder — und der Hinweistext
    zählte bis zum 27.08.2026 nur auf, was der exakte Kern **kann**.

    Das ist dieselbe Regel wie bei ``caveat`` (`registry/surfaces.py`): Eine
    Grenze steht dort, wo gewählt wird. Ein Umschalter, der eine Fähigkeit
    nimmt, ohne es zu sagen, ist eine Absage nach dem Klick — und die verbietet
    Regel 19.

    Geprüft wird über die Parametermengen, nicht über eine gepflegte Liste:
    Was ein Zwilling weniger kann, weiß das Register selbst. Verwandte Felder
    zählen dabei als **eine** Fähigkeit — „Entlüftungen" und
    „Entlüftungsdurchmesser" sind ein Können und nicht zwei, und ein Satz, der
    jedes Unterfeld einzeln aufzählte, wäre kein Hinweis mehr, sondern eine
    zweite Parameterliste.
    """
    from app.core import bootstrap
    from app.core.registry.registry import MENU_TWINS, TWIN_TOGGLES

    bootstrap.load_operations()
    stumm = []
    for exact, plain in MENU_TWINS.items():
        if exact not in TWIN_TOGGLES:
            continue
        verloren = {entry.name for entry in REGISTRY.get(plain).params.spec()} - {
            entry.name for entry in REGISTRY.get(exact).params.spec()
        }
        # ``anchor`` ist der eine Fall, der keine Fähigkeit ist: Der exakte
        # Quader steht immer mittig, und das sagt sein Maßfeld selbst.
        verloren -= {"anchor", "name"}
        if not verloren:
            continue
        satz = str(TWIN_TOGGLES[exact][1]).lower()
        fehlt = sorted(feld for feld in verloren if _stem_of(plain, feld) not in satz)
        if fehlt:
            stumm.append(f"{exact}: nimmt {sorted(verloren)}, verschweigt {fehlt}")

    assert not stumm, (
        "Umschalter, die etwas wegnehmen und schweigen:" + chr(10) + chr(10).join(stumm)
    )


def _stem_of(op: str, feld: str) -> str:
    """Der Wortstamm, unter dem ein Feld im Fließtext auftaucht.

    Der Kunde liest „Entlüftungen", nicht ``vents`` — gesucht wird also der
    übersetzte Titel. Und zwar sein Stamm: „Entlüftungen" und
    „Entlüftungsdurchmesser" beginnen beide mit „entlüftung", also deckt ein
    Satz über die Entlüftung beide.

    **Sechs Zeichen, und die Zahl ist gemessen.** Bei acht meldete der Test
    den Zylinder: Sein Feld heißt „Segmente", der Umschaltertext spricht von
    der „Segmentzahl" — dieselbe Sache, andere Beugung, und „segmente" steht
    nicht in „segmentzahl". Sechs Zeichen (`segmen`) decken beide, und im
    Umschaltertext eines Zwillings ist ein zufälliger Treffer auf sechs
    Zeichen nicht zu befürchten.
    """
    titel = str(next(entry.title for entry in REGISTRY.get(op).params.spec() if entry.name == feld))
    return titel.split()[0].rstrip(",.:").lower()[:6]
