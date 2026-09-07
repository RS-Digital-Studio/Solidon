"""Das kontextsensitive Operationsfeld der rechten Spalte."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY, catalogue_operations, needed_inputs
from app.ui.selection_operations import (
    QUICK_OPERATIONS,
    SelectionOperationsPanel,
    body_operations,
)
from app.ui.style import TARGET_SIZE


def _availability(selected: int):
    """Dieselbe Mindestzahlentscheidung wie der Fensterpfad."""

    def answer(name: str) -> tuple[bool, str]:
        needed = needed_inputs(REGISTRY.get(name))
        return (
            (True, "")
            if selected >= needed
            else (False, f"Dafür müssen {needed} Körper ausgewählt sein.")
        )

    return answer


def test_the_panel_is_the_registry_without_features_and_parts(qt_app: QApplication) -> None:
    """Die Oberfläche pflegt keine zweite Operationsliste."""
    load_operations()
    specs = body_operations(REGISTRY.all())
    panel = SelectionOperationsPanel(REGISTRY.all())

    assert {spec.name for spec in specs} == set(panel._buttons)
    assert set(QUICK_OPERATIONS) <= set(panel._buttons)
    assert not (set(panel._buttons) & catalogue_operations())
    assert all(not spec.applies_to for spec in specs), "Merkmale behalten ihren eigenen Weg"
    assert all(spec.category not in {"holes", "parts"} for spec in specs)


def test_selection_changes_update_in_place_and_explain_disabled_actions(
    qt_app: QApplication,
) -> None:
    """Eine große Registerliste wird bei jedem Klick nur nachgeführt."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, 340)
    panel.show()
    identities = {name: id(button) for name, button in panel._buttons.items()}

    panel.set_context(1, _availability(1), feature_chosen=False)
    joining = panel._buttons["union_objects"]
    assert not panel.isHidden()
    assert panel.summary.text() == "1 Objekt gewählt"
    assert not joining.isEnabled()
    assert "2 Körper" in joining.toolTip()
    assert not panel.feature_button.isEnabled()

    panel.set_context(2, _availability(2), feature_chosen=True)
    QApplication.processEvents()
    assert identities == {name: id(button) for name, button in panel._buttons.items()}
    assert joining.isEnabled()
    assert panel.feature_button.isEnabled()
    assert panel.summary.text() == "2 Objekte gewählt"
    for name in QUICK_OPERATIONS:
        button = panel._buttons[name]
        assert button.width() >= button.sizeHint().width(), f"{button.text()} ist abgeschnitten"
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus

    panel.set_context(0, _availability(0), feature_chosen=False)
    assert panel.isHidden()


def test_search_filters_existing_buttons_and_a_click_carries_the_register_entry(
    qt_app: QApplication,
) -> None:
    """Suche und Klick bleiben am vorhandenen Registereintrag."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(2, _availability(2), feature_chosen=False)
    extra = next(
        button
        for name, button in panel._buttons.items()
        if name not in QUICK_OPERATIONS and button.isEnabled()
    )
    received = []
    panel.operationRequested.connect(received.append)

    panel.search.setText(extra.text())
    QApplication.processEvents()
    assert not extra.isHidden()
    assert any(
        button.isHidden() for name, button in panel._buttons.items() if name not in QUICK_OPERATIONS
    )

    extra.click()
    assert [entry.name for entry in received] == [str(extra.property("operationName"))]


def test_every_action_row_keeps_a_keyboard_sized_height(qt_app: QApplication) -> None:
    """Der Bericht darf die Hauptaktionen nicht zu überlappenden Zeilen drücken."""
    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.resize(320, panel.minimumHeight())
    panel.set_context(2, _availability(2), feature_chosen=True)
    panel.show()
    qt_app.processEvents()

    for name in QUICK_OPERATIONS:
        assert panel._buttons[name].height() >= TARGET_SIZE
    assert panel.search.height() >= TARGET_SIZE
    assert panel.catalog_button.height() >= TARGET_SIZE
