"""Die Oberflächen-Einstellungen in ``settings.json`` (Bauplan §38)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


def test_an_unreadable_settings_file_keeps_the_language_of_the_system(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Eine kaputte Einstellungsdatei machte aus jedem System ein deutsches.

    Der allererste Start fragt Installer und System nach der Sprache. Eine
    Datei, die sich nicht lesen ließ — halb geschrieben, von Hand verdorben —,
    führte dagegen auf die blanke Vorgabe, und die ist Deutsch. Unlesbar ist
    keine Wahl des Nutzers (Review Fenster 0.5.0, 22.09.2026).
    """
    from app.ui import settings as settings_module

    broken = tmp_path / "settings.json"
    broken.write_text("{ nicht fertig", encoding="utf-8")
    monkeypatch.setattr(settings_module, "settings_path", lambda: broken)
    monkeypatch.setattr(settings_module, "installed_language", lambda: None)
    monkeypatch.setattr(settings_module, "system_language", lambda: "es")

    assert settings_module.load_settings().language == "es"


@pytest.mark.parametrize("retry", [False, True])
def test_a_slicer_path_write_error_reopens_the_settings_draft(monkeypatch, retry) -> None:
    """Ein Schreibfehler erklärt den Rückweg; der Entwurf bleibt bis Speichern erhalten."""
    from copy import deepcopy
    from types import SimpleNamespace

    from app.core.errors import FileWriteError
    from app.ui import main_window, settings_dialog
    from app.ui.settings import UiSettings

    opened = []
    problems = []
    stored = []
    paths = []
    settings = UiSettings()
    original = deepcopy(settings)

    def remember(_key, path):
        paths.append(path)
        if len(paths) == 1:
            raise PermissionError("test: settings folder is read-only")

    class DraftDialog:
        DialogCode = settings_dialog.SettingsDialog.DialogCode

        def __init__(self, draft, _parent, **choices):
            opened.append(deepcopy(draft))
            self._reset_ai_disclosure = False
            self.printer = SimpleNamespace(currentData=lambda: original.printer)
            self._discovered_printers = {}
            self.discovered_printers = {}
            self.slicer_path = "selected-slicer.exe"
            self.printer_query = None
            if len(opened) > 1:
                assert draft.theme == "light"
                assert choices["slicer_path"] == self.slicer_path
                assert settings == original

        def exec(self):
            return (
                self.DialogCode.Accepted if len(opened) == 1 or retry else self.DialogCode.Rejected
            )

        def save_external_choices(self):
            settings_dialog.SettingsDialog.save_external_choices(self)

        def apply_to(self, draft):
            draft.theme = "light"
            return draft

        def deleteLater(self):  # noqa: N802 — Qt-Name
            pass

    monkeypatch.setattr(settings_dialog.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(settings_dialog.discover, "remember_path", remember)
    monkeypatch.setattr(main_window, "SettingsDialog", DraftDialog)
    monkeypatch.setattr(main_window, "show_error", lambda error, _parent: problems.append(error))
    monkeypatch.setattr("app.i18n.catalog.install_language", lambda _chosen: None)
    monkeypatch.setattr("app.i18n.set_language", lambda _chosen: None)
    window = SimpleNamespace(
        settings=settings,
        _store_settings=lambda: stored.append(deepcopy(settings)),
        _apply_settings=lambda: None,
        _apply_remote=lambda: None,
    )
    main_window.MainWindow.action_settings(window)
    assert len(opened) == 2
    assert len(problems) == 1 and isinstance(problems[0], FileWriteError)
    assert {action.id for action in problems[0].suggestions} == {"retry", "cancel"}
    assert settings.theme == ("light" if retry else original.theme)
    assert len(stored) == int(retry)
    assert len(paths) == 1 + int(retry)


def test_settings_slicer_changes_ignore_old_printers_and_do_not_write_on_cancel(
    qt_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine langsame Antwort gehört ihrem Slicer; Abbrechen speichert keinen Entwurf."""
    import threading

    from PySide6.QtWidgets import QDialogButtonBox

    from app.core.knowledge import profiles
    from app.ui import settings_dialog as module
    from app.ui.first_run import PrinterChoices
    from app.ui.settings import UiSettings

    first = Path("first-slicer.exe")
    second = Path("second-slicer.exe")
    arrived = threading.Event()
    release_first = threading.Event()
    writes: list[tuple[str, str]] = []
    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(
        module.discover, "remember_path", lambda key, path: writes.append((key, path))
    )
    monkeypatch.setattr(
        module._SlicerWorker, "work", lambda worker: worker.done.emit((first, second))
    )

    def survey(worker):
        if worker.executable == first:
            arrived.set()
            assert release_first.wait(5)
            found = ("prusa-mk4s",)
        else:
            found = (profiles.DEFAULT_RESIN_PRINTER,)
        worker.done.emit(PrinterChoices(worker.executable, found, found[0]))

    monkeypatch.setattr(module._PrinterSurvey, "work", survey)
    dialog = module.SettingsDialog(UiSettings())
    try:
        assert dialog.wait_for_survey(5000)
        dialog.slicer.setCurrentIndex(dialog.slicer.findData(str(first)))
        assert arrived.wait(2)
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        assert not buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
        dialog.slicer.setCurrentIndex(dialog.slicer.findData(str(second)))
        second_worker = dialog._printer_survey
        assert second_worker is not None and second_worker.wait(5000)
        qt_app.processEvents()
        assert dialog.printer.currentData() == profiles.DEFAULT_RESIN_PRINTER
        release_first.set()
        assert dialog.wait_for_survey(5000)
        assert dialog.printer.currentData() == profiles.DEFAULT_RESIN_PRINTER
        assert dialog.printer.findData("prusa-mk4s") < 0
        assert dialog.material.currentData() == "resin"
        dialog.reject()
        assert not writes
    finally:
        release_first.set()
        dialog.release()
        dialog.deleteLater()


def test_settings_keep_imported_printers_local_until_the_selected_one_is_saved(
    qt_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Auswahl importiert nur das gewünschte Profil, auch nach einem Sprach-Entwurf."""
    from dataclasses import replace

    from app.core.knowledge import profiles
    from app.ui import settings_dialog as module
    from app.ui.first_run import LANGUAGE_CHANGED, PrinterChoices
    from app.ui.settings import UiSettings

    first = replace(
        profiles.printer(profiles.DEFAULT_PRINTER), id="slicer-first", title="Printer A"
    )
    second = replace(first, id="slicer-second", title="Printer B")
    path = Path("my-slicer.exe")
    saved: list[object] = []
    paths: list[str] = []
    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(module.discover, "remember_path", lambda _key, value: paths.append(value))
    monkeypatch.setattr(profiles, "save_printer", lambda profile: saved.append(profile))
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit((path,)))
    monkeypatch.setattr(
        module._PrinterSurvey,
        "work",
        lambda worker: worker.done.emit(
            PrinterChoices(path, (first.id, second.id), first.id, profiles=(first, second))
        ),
    )
    draft = UiSettings(
        slicer_profile_slicer="previous-slicer.exe",
        slicer_machine_profile="previous machine",
        slicer_base_process="previous process",
    )
    dialog = module.SettingsDialog(draft, slicer_path=str(path))
    try:
        assert dialog.wait_for_survey(5000)
        dialog.printer.setCurrentIndex(dialog.printer.findData(second.id))
        dialog.language.setCurrentIndex(dialog.language.findData("en"))
        assert dialog.result() == LANGUAGE_CHANGED
        dialog.apply_to(draft)
        assert draft.printer == second.id
        assert draft.language == "en"
        assert draft.slicer_profile_slicer == str(path)
        assert not draft.slicer_machine_profile and not draft.slicer_base_process
        assert not saved and not paths
        carried = dict(dialog.discovered_printers)
    finally:
        dialog.release()
        dialog.deleteLater()
    rebuilt = module.SettingsDialog(draft, slicer_path=str(path), discovered_printers=carried)
    try:
        assert rebuilt.wait_for_survey(5000)
        assert rebuilt.printer.currentData() == second.id
        rebuilt.save_external_choices()
        assert saved == [second]
        assert paths == [str(path)]
    finally:
        rebuilt.release()
        rebuilt.deleteLater()


def test_settings_details_give_back_only_their_own_height(qt_app, monkeypatch) -> None:
    """Auf- und Zuklappen lässt die Speichertasten stehen und erhält eine gezogene Höhe."""
    from PySide6.QtWidgets import QToolButton

    from app.ui import settings_dialog as module
    from app.ui.settings import UiSettings

    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit(()))
    dialog = module.SettingsDialog(UiSettings())

    def settle():
        for _ in range(12):
            qt_app.processEvents()

    try:
        dialog.show()
        assert dialog.wait_for_survey(5000)
        settle()
        compact = dialog.height()
        heading = dialog.advanced.findChild(QToolButton)
        assert heading is not None
        heading.click()
        settle()
        assert dialog.navigation.isVisibleTo(dialog)
        assert dialog.height() >= compact
        assert not dialog._scroll.isAncestorOf(dialog.save)
        heading.click()
        settle()
        assert dialog.height() == compact
        dialog.resize(dialog.width(), compact + 80)
        drawn = dialog.height()
        heading.click()
        settle()
        heading.click()
        settle()
        assert dialog.height() == drawn
    finally:
        dialog.close()
        dialog.release()
        dialog.deleteLater()


def test_printer_search_keeps_the_confirmed_choice_across_a_language_change(
    qt_app, monkeypatch
) -> None:
    """Suche und bestätigter Drucker bleiben beim Sprachwechsel getrennt erhalten."""
    from app.ui import settings_dialog as module
    from app.ui.first_run import LANGUAGE_CHANGED
    from app.ui.settings import UiSettings

    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit(()))
    draft = UiSettings()
    dialog = module.SettingsDialog(draft)
    query = "noch nicht gefundener Drucker"
    try:
        assert dialog.wait_for_survey(5000)
        chosen = dialog.printer.currentData()
        dialog.printer.search_field.setText(query)
        qt_app.processEvents()
        assert dialog.printer.currentData() == chosen
        assert dialog.save.isEnabled()
        assert dialog.material.isEnabled()
        dialog.language.setCurrentIndex(dialog.language.findData("en"))
        assert dialog.result() == LANGUAGE_CHANGED
        dialog.apply_to(draft)
        assert draft.printer == chosen
        carried_query = dialog.printer_query
    finally:
        dialog.release()
        dialog.deleteLater()
    rebuilt = module.SettingsDialog(draft, printer_query=carried_query)
    try:
        assert rebuilt.wait_for_survey(5000)
        assert rebuilt.printer.search_field.text() == query
        assert rebuilt.printer.currentData() == chosen
        assert rebuilt.save.isEnabled()
        rebuilt.printer.setCurrentIndex(rebuilt.printer.findData("prusa-mk4s"))
        qt_app.processEvents()
        assert rebuilt.save.isEnabled()
        rebuilt.accept()
        assert rebuilt.result() == rebuilt.DialogCode.Accepted
    finally:
        rebuilt.release()
        rebuilt.deleteLater()
