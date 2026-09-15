"""Slicer, passende Drucker und eigene Maße in den ersten Schritten."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog

from app.core import discover
from app.core.knowledge import profiles
from app.ui import first_run
from app.ui.first_run import FirstRunDialog
from app.ui.settings import UiSettings


@pytest.fixture
def setup_dialog(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> FirstRunDialog:
    """Die Zusatzprogramme haben für diese gezielten Bedienwege keine Bedeutung."""
    monkeypatch.setattr(FirstRunDialog, "look", lambda _self: None)
    return FirstRunDialog(UiSettings())


def test_selected_slicer_filters_printers_and_keeps_custom_choice(
    setup_dialog: FirstRunDialog, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Drucker stammen jeweils aus dem ausdrücklich gewählten Slicer."""
    known = profiles.printer_profiles()
    first = "prusa-mk4s"
    second = "centauri-carbon-2"
    machine_names = {
        "PrusaSlicer.exe": (known[first].title,),
        "elegoo-slicer.exe": (known[second].title,),
    }
    monkeypatch.setattr(
        first_run.slicer_profiles, "known_printers", lambda _flavour, path: machine_names[path.name]
    )
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: "")
    setup_dialog._fill_slicers(tuple(Path(name) for name in machine_names))

    for index, included, excluded in ((1, first, second), (2, second, first)):
        setup_dialog.slicer.setCurrentIndex(index)
        assert setup_dialog.wait_for_survey()
        assert setup_dialog.printer.findData(included) >= 0
        assert setup_dialog.printer.findData(excluded) < 0
        assert setup_dialog.printer.findData("__custom__") >= 0
        assert setup_dialog.printer.isEnabled()
        titles = [setup_dialog.printer.itemText(row) for row in range(setup_dialog.printer.count())]
        assert titles == sorted(titles, key=str.casefold)


def test_failed_slicer_worker_keeps_saved_custom_printers_and_current_choice(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein unbekannter Slicer verbirgt weder eigene Drucker noch deren aktuelle Auswahl."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    template = profiles.printer(profiles.DEFAULT_PRINTER)
    first = profiles.save_printer(replace(template, id="user-workshop", title="Werkstatt"))
    second = profiles.save_printer(replace(template, id="user-garage", title="Garage"))
    setup_dialog._fill_printers(tuple(profiles.printer_profiles()))
    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData(first.id))
    setup_dialog._fill_slicers((Path("unsupported-program.exe"),))
    setup_dialog.slicer.setCurrentIndex(1)

    assert setup_dialog.wait_for_survey()
    assert setup_dialog.printer.isEnabled()
    assert setup_dialog.printer.currentData() == first.id
    assert setup_dialog.printer.findData(second.id) >= 0
    assert setup_dialog.printer.findData("__custom__") >= 0
    assert "anderen Slicer" in setup_dialog.printer_state.text()


def test_slicer_profile_search_stays_outside_the_gui_thread(
    setup_dialog: FirstRunDialog, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch das Wechseln nach der ersten Erhebung liest Profile im Arbeiter."""
    import threading

    thread_ids: list[int] = []

    def known(_flavour: str, _path: Path) -> tuple[str, ...]:
        thread_ids.append(threading.get_ident())
        return ()

    monkeypatch.setattr(first_run.slicer_profiles, "known_printers", known)
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: "")
    setup_dialog._fill_slicers((Path("OrcaSlicer.exe"),))
    setup_dialog.slicer.setCurrentIndex(1)
    assert setup_dialog.wait_for_survey()
    assert thread_ids and threading.get_ident() not in thread_ids


def test_unselected_slicers_do_not_supply_printer_or_material_defaults(
    setup_dialog: FirstRunDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch ein gefundener Slicer liefert vor seiner Auswahl keine stillen Vorgaben."""
    chosen_machine = mock.Mock(return_value="Prusa MK4S")
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", chosen_machine)
    monkeypatch.setattr(first_run.tools, "survey", lambda: ())
    monkeypatch.setattr(first_run, "_chat_text", lambda: "bereit")
    monkeypatch.setattr(
        first_run.discover, "find_programs", lambda *_args: (Path("PrusaSlicer.exe"),)
    )
    setup_dialog.settings.material = "abs"
    before = setup_dialog.printer.currentData()
    survey = first_run._Survey()
    survey.done.connect(setup_dialog._show)
    survey.work()
    assert setup_dialog.slicer.currentData() == ""
    assert setup_dialog.printer.currentData() == before
    assert setup_dialog.settings.material == "abs"
    chosen_machine.assert_not_called()


def test_selected_slicer_can_suggest_its_own_active_printer(
    setup_dialog: FirstRunDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erst die ausdrückliche Slicerwahl erlaubt dessen belegte Druckervorgabe."""
    name = profiles.printer("prusa-mk4s").title
    monkeypatch.setattr(first_run.slicer_profiles, "known_printers", lambda *_args: (name,))
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: name)
    setup_dialog._fill_slicers((Path("PrusaSlicer.exe"),))
    setup_dialog.slicer.setCurrentIndex(1)
    assert setup_dialog.wait_for_survey()
    assert setup_dialog.printer.currentData() == "prusa-mk4s"


def test_late_general_survey_keeps_the_selected_slicer_printer_and_material(
    setup_dialog: FirstRunDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein alter Programmbestand gehört nicht zur inzwischen gewählten Installation."""
    known = profiles.printer_profiles()
    names = {
        "PrusaSlicer.exe": known["prusa-mk4s"].title,
        "elegoo-slicer.exe": known["centauri-carbon-2"].title,
    }
    monkeypatch.setattr(
        first_run.slicer_profiles, "known_printers", lambda _flavour, path: (names[path.name],)
    )
    monkeypatch.setattr(
        first_run.slicer_profiles, "chosen_machine", lambda _flavour, path: names[path.name]
    )
    setup_dialog._fill_slicers(tuple(Path(name) for name in names))
    setup_dialog.slicer.setCurrentIndex(1)
    assert setup_dialog.wait_for_survey()
    setup_dialog.slicer.setCurrentIndex(2)
    assert setup_dialog.wait_for_survey()
    assert setup_dialog.printer.currentData() == "centauri-carbon-2"
    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData("centauri-carbon-2"))
    setup_dialog.settings.material = "abs"

    setup_dialog._show(
        first_run.Findings(tools=(), chat="bereit", slicers=(Path("PrusaSlicer.exe"),))
    )
    assert setup_dialog.wait_for_survey()
    assert setup_dialog.slicer.currentData() == "elegoo-slicer.exe"
    assert setup_dialog.printer.currentData() == "centauri-carbon-2"
    assert setup_dialog.settings.material == "abs"


def test_late_printer_result_cannot_replace_the_newer_slicer_selection(
    setup_dialog: FirstRunDialog, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine langsame erste Installation darf keine zweite Druckerliste überschreiben."""
    from threading import Event

    entered = Event()
    release = Event()
    known = profiles.printer_profiles()

    def names(_flavour: str, path: Path) -> tuple[str, ...]:
        if path.name == "PrusaSlicer.exe":
            entered.set()
            assert release.wait(5)
            return (known["prusa-mk4s"].title,)
        return (known["centauri-carbon-2"].title,)

    monkeypatch.setattr(first_run.slicer_profiles, "known_printers", names)
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: "")
    setup_dialog._fill_slicers((Path("PrusaSlicer.exe"), Path("elegoo-slicer.exe")))
    setup_dialog.slicer.setCurrentIndex(1)
    old_worker = setup_dialog._printer_survey
    try:
        assert entered.wait(5)
        setup_dialog.slicer.setCurrentIndex(2)
        assert setup_dialog.wait_for_survey()
    finally:
        release.set()
        assert old_worker is not None and old_worker.wait(5_000)
    qt_app.processEvents()
    assert setup_dialog.printer.findData("centauri-carbon-2") >= 0
    assert setup_dialog.printer.findData("prusa-mk4s") < 0


def test_custom_slicer_path_is_selected_and_only_remembered_when_applied(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein portabler Slicer braucht keine typische Installationsposition."""
    path = tmp_path / "portable" / "OrcaSlicer.exe"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    monkeypatch.setattr(first_run.slicer_profiles, "known_printers", lambda *_args: ())
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: "")
    setup_dialog._choose_slicer_file()
    assert setup_dialog.wait_for_survey()
    assert setup_dialog.slicer.currentData() == str(path)
    assert discover.remembered_path("slicer") == ""
    setup_dialog.apply_to(setup_dialog.settings)
    assert discover.remembered_path("slicer") == str(path)


def test_custom_printer_is_saved_with_entered_dimensions_before_inventory_opens(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der nächste Schritt sieht bereits das neu gespeicherte Druckerprofil."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData("__custom__"))
    setup_dialog.printer_name.setText('Mein Drucker "Werkstatt"')
    for field, value in zip(setup_dialog.printer_dimensions, (315, 270, 420), strict=True):
        field.setValue(value)
    setup_dialog.printer_nozzle.setValue(0.6)
    chosen: list[str] = []
    setup_dialog.inventoryRequested.connect(lambda: chosen.append(setup_dialog.settings.printer))
    setup_dialog._open_inventory()

    assert setup_dialog.result() == FirstRunDialog.DialogCode.Accepted
    assert chosen == [setup_dialog.settings.printer]
    entry = profiles.printer(chosen[0])
    assert entry.title == 'Mein Drucker "Werkstatt"'
    assert entry.build_volume == pytest.approx((315, 270, 420))
    assert entry.nozzle_diameter == pytest.approx(0.6)
    assert chosen[0] in profiles.user_printer_profiles()
    titles = [setup_dialog.printer.itemText(row) for row in range(setup_dialog.printer.count())]
    assert titles == sorted(titles, key=str.casefold)


def test_empty_custom_printer_name_keeps_the_dialog_open(
    setup_dialog: FirstRunDialog,
) -> None:
    """Ein unvollständiger eigener Drucker wird nicht als generischer gespeichert."""
    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData("__custom__"))
    opened: list[bool] = []
    setup_dialog.inventoryRequested.connect(lambda: opened.append(True))
    setup_dialog._open_inventory()
    assert setup_dialog.result() != FirstRunDialog.DialogCode.Accepted
    assert not setup_dialog.settings.first_run_done
    assert not opened
    assert "Namen" in setup_dialog.printer_state.text()


def test_custom_printer_draft_survives_a_language_rebuild(
    setup_dialog: FirstRunDialog,
) -> None:
    """Auch noch namenlose eigene Maße werden beim Neuaufbau erhalten."""
    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData("__custom__"))
    setup_dialog.printer_dimensions[0].setValue(456)
    draft = setup_dialog.custom_printer_draft()
    rebuilt = FirstRunDialog(setup_dialog.settings)
    rebuilt.restore_custom_printer_draft(draft)
    assert rebuilt.custom_printer_draft() == draft
    assert rebuilt.printer.currentData() == "__custom__"


def test_inventory_opens_after_main_window_adopts_the_custom_printer(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Lagerknopf übernimmt den eigenen Drucker bis ins neue Projekt."""
    from PySide6.QtCore import QTimer

    from app.core.knowledge import filaments
    from app.ui import main_window
    from app.ui.session import Session

    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    spool = filaments.save(filaments.CatalogueFilament("Eigene Spule", "#102030", "PETG"))

    class InventoryDialog(FirstRunDialog):
        def exec(self) -> int:
            self.printer.setCurrentIndex(self.printer.findData("__custom__"))
            self.printer_name.setText("Mein eigener Drucker")
            self.printer_dimensions[0].setValue(315)
            QTimer.singleShot(0, self, self.inventory_button.click)
            return super().exec()

    monkeypatch.setattr(first_run, "FirstRunDialog", InventoryDialog)
    monkeypatch.setattr(main_window, "save_settings", lambda _settings: None)
    monkeypatch.setattr(Session, "set_agent_backend", lambda *_args: None)
    window = main_window.MainWindow(Session(), UiSettings())
    monkeypatch.setattr(window, "_refresh_chat_availability", lambda **_kwargs: None)
    try:
        window.action_first_run()

        assert window.stack.currentWidget() is window._inventory_view
        assert window.settings.first_run_done
        printer = window.session.profile.printer
        assert printer.id == window.settings.printer
        assert window.session.project.document.printer == printer.id
        assert printer.title == "Mein eigener Drucker"
        assert printer.build_volume[0] == pytest.approx(315)
        assert filaments.catalogue() == (spool,)
    finally:
        window.close()
