"""Das Befehlsband hat feste Wege und eine begrenzte Kontextantwort."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QLabel, QMenu

from app.core import bootstrap
from app.ui.command_band import MAX_CONTEXT_ACTIONS, CommandBand, context_specs


def test_feature_context_is_short_and_keeps_parts_in_the_catalog() -> None:
    """Vier Textknöpfe sind eine Antwort; zufällige Bausteine wären keine."""
    bootstrap.load_operations()

    specs = context_specs("hole")

    assert len(specs) == MAX_CONTEXT_ACTIONS
    assert all(spec.category != "parts" for spec in specs)
    assert {spec.name for spec in specs} == {
        "align_to_feature",
        "countersink_hole",
        "plug_hole",
        "resize_hole",
    }


def test_the_band_reuses_menu_actions_and_their_state(qt_app: QApplication) -> None:
    """Ausgrauen und Hilfetext dürfen nicht an einem zweiten Weg driften."""
    bootstrap.load_operations()
    menu = QMenu("Datei")
    primary = QAction("Öffnen")
    palette = QAction("Befehlspalette …")
    operation_actions: dict[str, QAction] = {}
    for spec in context_specs("hole"):
        action = QAction(str(spec.title))
        action.setObjectName(spec.name)
        operation_actions[spec.name] = action

    operation_actions["resize_hole"].setEnabled(False)
    operation_actions["resize_hole"].setToolTip("Dafür zuerst eine Bohrung wählen.")
    band = CommandBand([menu], [primary], palette, QLabel("Projekt"))
    band.set_operation_actions(operation_actions)
    band.set_context("hole")

    assert band.context_names() == tuple(spec.name for spec in context_specs("hole"))
    button = next(
        entry
        for entry in band._context_buttons
        if entry.defaultAction() is operation_actions["resize_hole"]
    )
    assert not button.isEnabled()
    assert button.toolTip() == "Dafür zuerst eine Bohrung wählen."


def test_only_the_named_context_group_changes(qt_app: QApplication) -> None:
    """Die Hauptwege bleiben stehen, während die Auswahl ihre Antwort wechselt."""
    bootstrap.load_operations()
    menu = QMenu("Datei")
    primary = QAction("Öffnen")
    palette = QAction("Befehlspalette …")
    actions: dict[str, QAction] = {}
    for kind in ("hole", "face"):
        for spec in context_specs(kind):
            action = actions.setdefault(spec.name, QAction(str(spec.title)))
            action.setObjectName(spec.name)
    band = CommandBand([menu], [primary], palette, QLabel("Projekt"))
    band.set_operation_actions(actions)

    band.set_context("hole")
    hole_names = band.context_names()
    band.set_context("face")

    assert primary.text() == "Öffnen"
    assert band.context_title.text() == "Auswahl: Fläche"
    assert band.context_names() != hole_names
    assert len(band.context_names()) <= MAX_CONTEXT_ACTIONS


def test_the_complete_menu_stays_behind_the_named_button(qt_app: QApplication) -> None:
    """Das sichtbare Band wird kürzer, ohne den vollständigen Weg zu verlieren."""
    first = QMenu("Datei")
    second = QMenu("Ändern")
    band = CommandBand(
        [first, second], [QAction("Öffnen")], QAction("Befehlspalette …"), QLabel("Projekt")
    )

    assert band.menu_button.text() == "Menü"
    assert band.menu.actions() == [first.menuAction(), second.menuAction()]
