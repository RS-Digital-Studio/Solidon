"""Gegenprobe zu CS-9a: Das Spulenverbot der Ersteinrichtung trifft den echten Aufruf.

``test_first_run.py::test_repeated_slicer_surveys_leave_material_and_inventory_for_the_later_step``
verbietet ``configured_spools`` an der Bindung, die das Filamentlager liest: Eine
Slicererhebung der Ersteinrichtung übernimmt keine Spulen aus dem Slicer. Ein
Verbot prüft nur dann etwas, wenn der verbotene Aufruf über genau diese Bindung
läuft (Konzept Codestruktur 4.1, W2) — statisch: Die verbotene Bindung hat zur
Aufrufzeit einen Leser, Regel d) in ``test_patch_targets.py``. Ein Verbot an
einer Bindung, die das Lager nicht liest — etwa am Original in
``filament_picker``, solange das Lager eine eigene Kopie hält (CS-9a) —,
erreicht nie einen Aufruf und ist immer grün.

Hier läuft der Weg, den der Kunde nimmt — leeres Regal, „Aus dem Slicer
übernehmen“, Arbeiter, Antwort — mit derselben Bindung wie das Verbot, nur
durchgereicht statt verboten. Wer ``configured_spools`` im Lager anders
bindet, macht diesen Test rot, bevor das Verbot still wird.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest import mock

import pytest
from PySide6.QtWidgets import QApplication

from app.core.knowledge import filaments
from app.i18n import tr
from app.ui import filament_inventory
from tests.ui_helpers import wait_until


def test_the_spool_import_reaches_the_binding_the_first_run_forbids(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Knopf im leeren Regal ruft die Bindung des Verbots genau einmal, im
    Arbeiter und mit seinem Abbruchsignal, und die Antwort kommt im Regal an —
    die der leeren Suche (die Suite isoliert die Slicer), nicht die eines Absturzes."""
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    real = filament_inventory.configured_spools
    threads: list[int] = []

    def reading(**kwargs: object) -> object:
        threads.append(threading.get_ident())
        return real(**kwargs)  # type: ignore[arg-type]

    configured = mock.Mock(side_effect=reading)
    monkeypatch.setattr(filament_inventory, "configured_spools", configured)
    view = filament_inventory.InventoryView()
    try:
        assert view.empty_import_button.isVisibleTo(view), "der Eingang im leeren Regal"
        assert not view.message.text()

        view.empty_import_button.click()
        wait_until(qt_app, view.wait_for_workers)

        configured.assert_called_once()
        assert set(configured.call_args.kwargs) == {"cancelled"}
        assert threads[0] != threading.get_ident(), "die Suche lief im Oberflächen-Thread"
        assert view.message.text() == tr(
            "Kein Slicer-Profil gefunden. Unter Bearbeiten → Einstellungen einen Slicer "
            "einrichten oder eine Spule von Hand anlegen."
        ), "die Antwort der leeren Suche steht im Regal"
        assert not view.retry_button.isVisibleTo(view), "die Suche endete im Fehlerweg"
    finally:
        assert view.wait_for_workers(5_000)
        view.close()
        view.deleteLater()
        qt_app.processEvents()
