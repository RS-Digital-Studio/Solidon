"""Ein Schritt im Änderungsweg: *Übernehmen*, und vor der ersten Änderung grau mit Weg (FD-99).

Der Änderungsweg (``MainWindow.edit_operation``, *Diesen Schritt ändern*,
*Eingabe korrigieren*) öffnet denselben Dialog wie das Anlegen. Sein Knopf hieß
dort wie beim Anlegen — „Einsetzen“ an einem Baustein, obwohl kein neues Teil
eingesetzt wird —, und er war vor jeder Änderung offen oder grau ohne Satz,
je nach Fläche. Die Regel für alle Flächen (FD-31): Solange nichts geändert
ist, ist *Übernehmen* grau, und der Satz nennt das Feld, das man ändern kann
(``app.ui.first_change``). Ein Fokus ist keine Änderung.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from PySide6.QtWidgets import QApplication

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.i18n import tr
from tests.ui_helpers import wait_until

#: Der Gewindeschritt aus dem Lauf (Szene ``gewinde_zu_kurz``).
THREAD = {"size": "M6", "length": 2.0, "internal": True, "at_feature": "hole_1"}


@contextmanager
def _changing(operation: str, values: dict[str, Any], **extra: Any) -> Iterator[Any]:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(
        REGISTRY.get(operation),
        {"obj_1": "Quader"},
        None,
        values=values,
        promote_values=False,
        changing=True,
        **extra,
    )
    try:
        yield dialog
    finally:
        dialog.reject()
        dialog.deleteLater()


def _type_into(spin: Any, text: str) -> None:
    """Ersetzt den Inhalt eines Zahlenfelds über die Tastatur und bestätigt."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    spin.setFocus(Qt.FocusReason.TabFocusReason)
    spin.lineEdit().selectAll()
    QTest.keyClicks(spin.lineEdit(), text)
    QTest.keyClick(spin.lineEdit(), Qt.Key.Key_Return)


def test_a_part_changed_in_its_step_says_apply(qt_app: QApplication) -> None:
    """Beim Anlegen „Einsetzen“, im Änderungsweg „Übernehmen“."""
    from app.ui.op_dialog import OperationDialog, accept_text

    bootstrap.load_operations()
    spec = REGISTRY.get("insert_printed_thread")
    assert accept_text(spec) == tr("Einsetzen"), "Vorbedingung: ein Baustein ohne Verb"
    assert accept_text(spec, changing=True) == tr("Übernehmen")
    fresh = OperationDialog(spec, {"obj_1": "Quader"}, None, values=THREAD)
    try:
        assert fresh._accept_button.text() == tr("Einsetzen")
    finally:
        fresh.deleteLater()
    with _changing("insert_printed_thread", THREAD) as dialog:
        assert dialog._accept_button.text() == tr("Übernehmen")


def test_before_the_first_change_the_button_names_the_field(qt_app: QApplication) -> None:
    from app.ui.first_change import first_change_sentence

    with _changing("insert_printed_thread", THREAD) as dialog:
        button = dialog._accept_button
        dialog.show()
        qt_app.processEvents()
        assert not button.isEnabled()
        said = button.toolTip()
        assert said == first_change_sentence(dialog._editors.values(), dialog)
        assert said and button.accessibleDescription() == said

        # Kommt der Kunde über ein Feld (*Eingabe korrigieren* nennt „Länge“),
        # nennt der Satz dieses Feld.
        assert dialog.focus_field("length")
        assert tr("Länge") in button.toolTip(), button.toolTip()

        # Fokus und dieselbe Zahl sind keine Änderung.
        field = dialog._editors["length"]
        field.spin.lineEdit().selectAll()
        field.spin.lineEdit().insert("2,00")
        field.spin.interpretText()
        qt_app.processEvents()
        assert not button.isEnabled(), "dieselbe Zahl ist keine Änderung"

        # Über die Tastatur, nicht über ein Signal von Hand: So zählt auch der
        # Anschluss des Feldes an den Dialog (Review F2a, R3).
        _type_into(field.spin, "3")
        wait_until(qt_app, button.isEnabled)
        assert tr("Länge") not in button.toolTip()

        # Zurück auf den alten Wert: wieder nichts zu übernehmen.
        _type_into(field.spin, "2")
        wait_until(qt_app, lambda: not button.isEnabled())


def test_an_unchanged_step_is_not_applied_by_the_keyboard(qt_app: QApplication) -> None:
    """Die Eingabetaste läuft über ``accept`` — auch dort gilt die Regel, und
    kein Klick wartet auf eine Vorschau."""
    waited: list[bool] = []
    with _changing("insert_printed_thread", THREAD) as dialog:
        dialog.preview_defer = lambda: waited.append(True)
        dialog.show()
        qt_app.processEvents()
        assert not dialog.can_accept()
        dialog.accept()
        assert dialog.result() == 0
        assert not waited, "ein ungeänderter Schritt wartet auf keine Vorschau"


def test_naming_the_dimensions_is_a_change(qt_app: QApplication) -> None:
    """*Maße als Parameter anlegen* ändert den Schritt, ohne eine Zahl zu ändern."""
    with _changing(
        "create_box",
        {"length": 20.0, "width": 20.0, "height": 20.0},
        offer_naming=True,
        naming_default=False,
    ) as dialog:
        button = dialog._accept_button
        dialog.show()
        qt_app.processEvents()
        assert not button.isEnabled()
        assert dialog._naming is not None
        dialog._naming.setChecked(True)
        wait_until(qt_app, button.isEnabled)


def test_a_new_operation_is_ready_at_once(qt_app: QApplication) -> None:
    """Beim Anlegen sind die Vorgaben die Entscheidung — der Knopf ist sofort offen."""
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(REGISTRY.get("create_box"), {}, None)
    try:
        dialog.show()
        qt_app.processEvents()
        assert dialog._accept_button.isEnabled()
    finally:
        dialog.deleteLater()


def test_a_field_behind_the_flap_is_named_once_it_is_open(qt_app: QApplication) -> None:
    """*Eingabe korrigieren* kann in ein Feld hinter „Weitere Einstellungen“ führen;
    der Satz nennt es, sobald die Klappe es zeigt."""
    with _changing("insert_printed_thread", THREAD) as dialog:
        dialog.show()
        qt_app.processEvents()
        spec = {entry.name: entry for entry in dialog.spec.params.spec()}
        behind = next(
            name
            for name, entry in spec.items()
            if entry.placement == "advanced"
            and entry.kind == "float"
            and not entry.internal
            and dialog._editors[name].isEnabled()
        )
        assert dialog.focus_field(behind)
        qt_app.processEvents()
        assert str(spec[behind].title) in dialog._accept_button.toolTip()


def test_values_changed_on_the_way_in_are_ready_to_apply(qt_app: QApplication) -> None:
    """Kommt die Änderung schon mit (eine Geste, eine Zeichnung aus dem Raum,
    ``edit_operation(given=…)``) oder hält der Schritt die Kette an, wartet der
    Knopf nicht: Erst die Vorschau sagt dann, was gilt."""
    with _changing(
        "insert_printed_thread", {**THREAD, "length": 6.0}, wait_for_change=False
    ) as dialog:
        dialog.show()
        qt_app.processEvents()
        assert dialog._accept_button.text() == tr("Übernehmen")
        assert dialog._accept_button.isEnabled()
        assert dialog.can_accept()


def test_a_preset_naming_hook_is_already_a_change(qt_app: QApplication) -> None:
    """Steht der Haken aus den Einstellungen schon beim Öffnen, legt Übernehmen
    die Maße als Parameter an — das ist eine Änderung, der Knopf ist frei."""
    with _changing(
        "create_box",
        {"length": 20.0, "width": 20.0, "height": 20.0},
        offer_naming=True,
        naming_default=True,
    ) as dialog:
        dialog.show()
        qt_app.processEvents()
        assert dialog._accept_button.isEnabled()


#: Vorn nur Haken oder eine Liste — dort war *Übernehmen* sofort frei (Review F2a, R4).
TICKS_AND_LISTS = ("repair", "orient_for_print", "clear_filament", "pose_armature")


def _waits(dialog: Any) -> bool:
    button = dialog._accept_button
    return not button.isEnabled() and bool(button.toolTip()) and dialog._waits_for_change


def test_every_step_with_a_field_waits_whatever_kind_and_flap(qt_app: QApplication) -> None:
    """Jede Operation, deren Dialog ein Feld zeigt, wartet im Änderungsweg auf
    die erste Änderung — auch mit nur Haken oder Listen vorn, und gleich, ob
    „Weitere Einstellungen“ offen oder zu ist (R4)."""
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    waiting: set[str] = set()
    free: list[str] = []
    for spec in sorted(REGISTRY.all(), key=lambda entry: entry.name):
        values = {
            entry.name: entry.default for entry in spec.params.spec() if entry.default is not None
        }
        dialog = OperationDialog(
            spec,
            {"obj_1": "Quader"},
            None,
            features={"hole_1": "Bohrung 1"},
            values=values,
            promote_values=False,
            changing=True,
        )
        try:
            dialog.show()
            qt_app.processEvents()
            # Ein Feld zählt, ob es vorn steht oder hinter der zugeklappten Klappe.
            behind = dialog._advanced_form.parentWidget()
            shown = [
                editor
                for editor in dialog._editors.values()
                if editor.isEnabled() and (editor.isVisibleTo(dialog) or editor.isVisibleTo(behind))
            ]
            if not shown:
                continue
            states = [_waits(dialog)]
            advanced = getattr(dialog, "advanced", None)
            if advanced is not None and advanced.isVisible():
                for _ in range(2):
                    advanced.click()
                    qt_app.processEvents()
                    states.append(_waits(dialog))
            if all(states):
                waiting.add(spec.name)
            else:
                free.append(f"{spec.name}: {states}")
        finally:
            dialog.reject()
            dialog.deleteLater()
    assert set(TICKS_AND_LISTS) <= waiting, sorted(set(TICKS_AND_LISTS) - waiting)
    assert len(waiting) > 150, len(waiting)
    assert not free, "frei vor der ersten Änderung (Zustände: zu, auf, zu):\n" + "\n".join(free)


def test_a_tick_is_named_and_its_change_frees_the_button(qt_app: QApplication) -> None:
    """*Prüfen und reparieren* trägt vorn nur Haken: Der Satz nennt den ersten,
    ein Klick darauf gibt den Knopf frei, ein zweiter nimmt es zurück."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QCheckBox

    bootstrap.load_operations()
    spec = REGISTRY.get("repair")
    values = {
        entry.name: entry.default for entry in spec.params.spec() if entry.default is not None
    }
    with _changing("repair", values) as dialog:
        dialog.show()
        qt_app.processEvents()
        button = dialog._accept_button
        tick = next(
            editor
            for editor in dialog._editors.values()
            if isinstance(editor, QCheckBox) and editor.isVisibleTo(dialog)
        )
        assert not button.isEnabled()
        assert tick.accessibleName() in button.toolTip(), button.toolTip()
        QTest.mouseClick(tick, Qt.MouseButton.LeftButton)
        wait_until(qt_app, button.isEnabled)
        QTest.mouseClick(tick, Qt.MouseButton.LeftButton)
        wait_until(qt_app, lambda: not button.isEnabled())


def test_fields_only_behind_the_flap_are_named_with_the_flap(qt_app: QApplication) -> None:
    """*Skelett stellen* hat vorn kein Feld: Der Satz nennt das erste Feld hinter
    der Klappe und die Klappe dazu; aufgeklappt nennt er das Feld allein."""
    bootstrap.load_operations()
    spec = REGISTRY.get("pose_armature")
    values = {
        entry.name: entry.default for entry in spec.params.spec() if entry.default is not None
    }
    with _changing("pose_armature", values) as dialog:
        dialog.show()
        qt_app.processEvents()
        button = dialog._accept_button
        assert not button.isEnabled()
        said = button.toolTip()
        assert tr("Weitere Einstellungen") in said and tr("Skelett") in said, said
        dialog.advanced.click()
        qt_app.processEvents()
        assert not button.isEnabled()
        assert tr("Weitere Einstellungen") not in button.toolTip(), button.toolTip()
        assert tr("Skelett") in button.toolTip(), button.toolTip()
