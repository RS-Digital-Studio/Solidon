"""Gegenprobe zu CS-9a: Das Spulenverbot der Ersteinrichtung trifft den echten Aufruf.

``test_first_run.py::test_repeated_slicer_surveys_leave_material_and_inventory_for_the_later_step``
verbietet ``filament_inventory.configured_spools``: Eine Slicererhebung der
Ersteinrichtung übernimmt keine Spulen aus dem Slicer. Ein Verbot prüft nur
dann etwas, wenn der verbotene Aufruf über genau diese Bindung läuft (Konzept
Codestruktur 4.1, W2; Entscheidung E8 im Plan zu Schritt 0). Das Filamentlager
hält ``configured_spools`` als eigene Kopie (``from app.ui.filament_picker import
configured_spools``); ein Verbot am Original in ``filament_picker`` erreichte
deshalb nie einen Aufruf und war immer grün.

Hier läuft der Weg, den der Kunde nimmt — leeres Regal, „Aus dem Slicer
übernehmen“, Arbeiter, Antwort — mit derselben Bindung wie das Verbot, nur
durchgereicht statt verboten. Wer ``configured_spools`` im Lager anders
bindet, macht diesen Test rot, bevor das Verbot still wird.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from PySide6.QtWidgets import QApplication

from app.core.knowledge import filaments
from app.ui import filament_inventory
from tests.ui_helpers import wait_until


def test_the_spool_import_reaches_the_binding_the_first_run_forbids(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Knopf im leeren Regal ruft ``filament_inventory.configured_spools`` genau einmal,
    im Arbeiter und mit seinem Abbruchsignal, und seine Antwort kommt im Regal an."""
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    configured = mock.Mock(wraps=filament_inventory.configured_spools)
    monkeypatch.setattr(filament_inventory, "configured_spools", configured)
    view = filament_inventory.InventoryView()
    try:
        assert view.empty_import_button.isVisibleTo(view), "der Eingang im leeren Regal"
        assert not view.message.text()

        view.empty_import_button.click()
        wait_until(qt_app, view.wait_for_workers)

        configured.assert_called_once()
        assert set(configured.call_args.kwargs) == {"cancelled"}
        assert view.message.text(), "die Antwort der Suche steht im Regal"
    finally:
        assert view.wait_for_workers(5_000)
        view.close()
        view.deleteLater()
        qt_app.processEvents()
