"""Die Namen auf den Wegen zu Parametermenü, Bindedialog, Rezept und neuer Spule (FD-101).

Ohne einen Namen für ihren letzten Klick erreichte der Prüfstand diese Flächen
nie: *Ändern …* im Menü einer Parameterzeile öffnet ein Rechtsklick auf ihre
Beschriftung, den Bindedialog *Zahlen an Maße binden …*, das Rezept *Auswahl
als Baustein speichern …* im Katalog, die Profile des Slicers *Wählen …* und
den Farbwähler ein Farbknopf im Fenster einer neuen Spule, das *Spule von Hand
anlegen* öffnet.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


def _settle(qt_app: Any, rounds: int = 30) -> None:
    for _ in range(rounds):
        qt_app.processEvents()


@pytest.fixture
def with_parameter(qt_app: Any, tmp_path: Path) -> Iterator[Any]:
    """Das Fenster mit der Startszene der Zeilen ``menu:parameters.edit`` und des Bindedialogs."""
    from app.core.scene.project import save
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tools import function_scenes

    path = tmp_path / "parameter.netz.p3d"
    save(function_scenes.build_scene("parameter.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.show()
    window._show_start_screen(False)
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    _settle(qt_app)
    try:
        yield window
    finally:
        window.hide()
        window.release()


def test_the_label_of_the_first_parameter_opens_the_menu_of_its_row(
    qt_app: Any, with_parameter: Any
) -> None:
    from PySide6.QtWidgets import QLabel

    from app.ui import guide_targets

    window = with_parameter
    panel = window.parameters
    label = guide_targets.widget_for(window, "parameters.first.label")
    assert isinstance(label, QLabel)
    assert label.buddy() is guide_targets.widget_for(window, "parameters.first")
    # Der Rechtsklick dort gehört der Zeile: Ihr Menü trägt *Ändern …*.
    centre = panel.mapFromGlobal(label.mapToGlobal(label.rect().center()))
    menu = panel.context_menu(centre)
    assert menu is not None
    try:
        assert [action.objectName() for action in menu.actions()] == ["parameters.edit"]
    finally:
        menu.deleteLater()
    # Höhe 20 = 0,5 · breite: Der Bindeknopf steht da.
    bind = guide_targets.widget_for(window, "parameters.bind")
    assert bind is panel.bind_button and bind.isVisible()


def test_catalogue_and_new_spool_carry_the_names_of_their_buttons(qt_app: Any) -> None:
    from PySide6.QtWidgets import QWidget

    from app.ui import guide_targets
    from app.ui.catalog import PartCatalog
    from app.ui.filament_inventory import InventoryView
    from app.ui.filament_picker import NewFilamentDialog

    stand_in: Any = QWidget()
    catalogue = PartCatalog()
    inventory = InventoryView()
    spool = NewFilamentDialog()
    opened = (catalogue, inventory, spool)
    for widget in opened:
        widget.show()
    _settle(qt_app)
    try:
        assert guide_targets.widget_for(stand_in, "parts.save") is catalogue.save_part
        add = guide_targets.widget_for(stand_in, "filament.add")
        assert add in (inventory.add_button, inventory.empty_add_button) and add.isVisible()
        assert guide_targets.widget_for(stand_in, "filament.profile") is spool.choose_profile
        assert guide_targets.widget_for(stand_in, "filament.colour") is spool.colour_buttons[0]
    finally:
        for widget in (*opened, stand_in):
            widget.hide()
            widget.deleteLater()
        _settle(qt_app)
