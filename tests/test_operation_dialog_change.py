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

        field.set_value(3.0)
        dialog.valuesChanged.emit()
        wait_until(qt_app, button.isEnabled)
        assert tr("Länge") not in button.toolTip()

        # Zurück auf den alten Wert: wieder nichts zu übernehmen.
        field.set_value(2.0)
        dialog.valuesChanged.emit()
        qt_app.processEvents()
        assert not button.isEnabled()


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
