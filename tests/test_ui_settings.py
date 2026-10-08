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
    main_window.MainWindow.show_setting(window, "")
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


def _settings_with_slicer(
    monkeypatch: pytest.MonkeyPatch, remembered: str, found: tuple[Path, ...]
):
    """Einstellungen mit gestellter Programm- und Druckersuche."""
    from app.core.knowledge import profiles
    from app.ui import settings_dialog as module
    from app.ui.first_run import PrinterChoices

    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: remembered)
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit(found))
    monkeypatch.setattr(
        module._PrinterSurvey,
        "work",
        lambda worker: worker.done.emit(
            PrinterChoices(worker.executable, (profiles.DEFAULT_PRINTER,), profiles.DEFAULT_PRINTER)
        ),
    )
    return module


@pytest.mark.skipif(Path("A") != Path("a"), reason="Pfade unterscheiden Groß und Klein")
def test_a_remembered_slicer_in_another_case_stays_chosen_in_the_settings(
    qt_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Gemerkt auf ``c:``, gefunden auf ``C:``: Die Liste fasst beide zusammen, die
    Wahl sprang auf „Später auswählen“ (RM-418)."""
    from app.ui.settings import UiSettings

    found = tmp_path / "orca-slicer.exe"
    text = str(found)
    module = _settings_with_slicer(monkeypatch, text[0].swapcase() + text[1:], (found,))
    dialog = module.SettingsDialog(UiSettings())
    try:
        assert dialog.wait_for_survey(5000)
        assert dialog.slicer.currentIndex() != 0, "nicht „Später auswählen“"
        assert Path(dialog.slicer_path) == found
        assert dialog.slicer.count() == 2, "eine Zeile je Programm"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_a_slicer_chosen_with_forward_slashes_frees_save_in_the_settings(
    qt_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der Dateidialog nennt ``C:/…``, die Druckersuche ``C:\\…``: „Speichern“
    blieb gesperrt, und ein so gemerkter Pfad sprang nach der Programmsuche auf
    „Später auswählen“ (RM-335)."""
    from PySide6.QtWidgets import QDialogButtonBox, QFileDialog

    from app.ui.settings import UiSettings

    remembered = tmp_path / "remembered" / "orca-slicer.exe"
    chosen = tmp_path / "portable" / "prusa-slicer.exe"
    module = _settings_with_slicer(monkeypatch, remembered.as_posix(), (remembered,))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (chosen.as_posix(), ""))
    dialog = module.SettingsDialog(UiSettings())
    try:
        assert dialog.wait_for_survey(5000)
        assert Path(dialog.slicer_path) == remembered
        dialog._choose_slicer_file()
        assert dialog.wait_for_survey(5000)
        assert Path(dialog.slicer_path) == chosen
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        assert buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    finally:
        dialog.release()
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("stored", "chosen", "profile_slicer", "forgets"),
    [
        ("", "", "orca/", False),
        ("", "orca/", "orca", False),
        ("orca", "orca/", "", False),
        ("", "prusa/", "orca", True),
        ("orca/", "", "orca/", True),
        ("", "orca/", "", True),
    ],
)
def test_only_another_slicer_forgets_the_slicer_profiles(
    tmp_path: Path, stored: str, chosen: str, profile_slicer: str, forgets: bool
) -> None:
    """Die Entscheidung hinter „Speichern“ — gleich in welcher Schreibweise (RM-337).

    ``name/`` steht für die Schreibweise des Dateidialogs mit ``/``, ``name``
    für die des Systems.
    """
    from app.ui.settings_dialog import forgets_slicer_profiles

    def written(token: str) -> str:
        if not token:
            return ""
        path = tmp_path / f"{token.rstrip('/')}.exe"
        return path.as_posix() if token.endswith("/") else str(path)

    assert (
        forgets_slicer_profiles(written(stored), written(chosen), written(profile_slicer))
        is forgets
    )


@pytest.mark.parametrize(
    ("choice", "kept"), [("unchanged", True), ("same", True), ("other", False)]
)
def test_saving_the_settings_keeps_the_slicer_profiles_unless_the_slicer_changes(
    qt_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, choice: str, kept: bool
) -> None:
    """Nur ein anderer Slicer verwirft Maschine, Prozess und Filament.

    Der Druckdialog merkt sich die Profile auch für einen nur gefundenen,
    nie gespeicherten Slicer. Wer danach in den Einstellungen allein das Thema
    wechselte oder genau diesen Slicer wählte, verlor sie (RM-337).
    """
    from PySide6.QtWidgets import QFileDialog

    from app.ui.settings import UiSettings

    profile_slicer = tmp_path / "orca-slicer.exe"
    other = tmp_path / "prusa-slicer.exe"
    module = _settings_with_slicer(monkeypatch, "", (profile_slicer, other))
    settings = UiSettings(
        slicer_profile_slicer=str(profile_slicer),
        slicer_machine_profile="Elegoo Centauri Carbon 2 0.4 nozzle",
        slicer_base_process="0.20mm Standard",
        slicer_base_filament="Elegoo PLA",
    )
    target = {"same": profile_slicer, "other": other}.get(choice)
    if target is not None:
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (target.as_posix(), ""))
    dialog = module.SettingsDialog(settings)
    try:
        assert dialog.wait_for_survey(5000)
        dialog.theme.setCurrentIndex((dialog.theme.currentIndex() + 1) % dialog.theme.count())
        if target is not None:
            dialog._choose_slicer_file()
            assert dialog.wait_for_survey(5000)
        dialog.apply_to(settings)
    finally:
        dialog.release()
        dialog.deleteLater()
    profiles_kept = (
        settings.slicer_machine_profile,
        settings.slicer_base_process,
        settings.slicer_base_filament,
    )
    if kept:
        assert profiles_kept == (
            "Elegoo Centauri Carbon 2 0.4 nozzle",
            "0.20mm Standard",
            "Elegoo PLA",
        )
        assert Path(settings.slicer_profile_slicer) == profile_slicer
    else:
        assert profiles_kept == ("", "", "")
        assert Path(settings.slicer_profile_slicer) == other


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
    monkeypatch.setattr(profiles, "save_printer", lambda profile, **_values: saved.append(profile))
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


def test_saving_the_settings_keeps_the_nozzle_chosen_in_the_print_dialog(
    qt_app, monkeypatch, tmp_path
) -> None:
    """Ein frisch aus dem Slicer gelesener Drucker behält beim Speichern die
    Düse, die der Druckdialog unter seiner Kennung abgelegt hat."""
    from dataclasses import replace

    from app.core.knowledge import profiles
    from app.ui import settings_dialog as module
    from app.ui.first_run import PrinterChoices
    from app.ui.settings import UiSettings

    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    found = replace(
        profiles.printer(profiles.DEFAULT_PRINTER),
        id="slicer-orca-a1",
        title="Bambu Lab A1 0.4 nozzle",
        vendor="BBL",
        nozzle_diameter=0.4,
        extrusion_width=0.42,
    )
    profiles.save_printer(replace(found, nozzle_diameter=0.6, extrusion_width=0.63))
    path = Path("my-slicer.exe")
    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: str(path))
    monkeypatch.setattr(module.discover, "remember_path", lambda _key, _value: None)
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit((path,)))
    monkeypatch.setattr(
        module._PrinterSurvey,
        "work",
        lambda worker: worker.done.emit(
            PrinterChoices(path, (found.id,), found.id, profiles=(found,))
        ),
    )
    dialog = module.SettingsDialog(UiSettings(printer=found.id), slicer_path=str(path))
    try:
        assert dialog.wait_for_survey(5000)
        assert dialog.printer.currentData() == found.id
        assert dialog.printer.currentText() == "Bambu Lab A1"
        dialog.save_external_choices()
        assert profiles.printer_profiles()[found.id].nozzle_diameter == pytest.approx(0.6)
    finally:
        dialog.release()
        dialog.deleteLater()


def test_settings_details_give_back_only_their_own_height(qt_app, monkeypatch) -> None:
    """Auf- und Zuklappen lässt die Speichertasten stehen und erhält eine gezogene Höhe."""
    from PySide6.QtWidgets import QToolButton

    from app.ui import settings_dialog as module
    from app.ui.settings import UiSettings
    from app.ui.style import apply_style
    from app.ui.theme import apply_theme

    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit(()))
    # **Gemessen in der Lage des Kunden** (``tests.md``): Mit Stylesheet sind
    # Zeilen und Abstände andere; ohne hing das Ergebnis daran, ob ein Test
    # davor ein Thema gesetzt hatte.
    before = qt_app.styleSheet()
    apply_theme(qt_app, "dark")
    apply_style(qt_app, "dark")
    dialog = module.SettingsDialog(UiSettings())

    def settle():
        for _ in range(12):
            qt_app.processEvents()

    try:
        dialog.show()
        assert dialog.wait_for_survey(5000)
        settle()
        compact = dialog.height()
        compact_width = dialog.width()
        heading = dialog.advanced.findChild(QToolButton)
        assert heading is not None
        heading.click()
        settle()
        assert dialog.navigation.isVisibleTo(dialog)
        assert dialog.height() >= compact
        assert dialog.width() == compact_width, (
            "Zusatzzeilen dürfen das Fenster nicht seitlich springen lassen"
        )
        assert not dialog._scroll.isAncestorOf(dialog.save)
        opened = dialog.height()
        heading.click()
        settle()
        # **Der Wunsch des zugeklappten Inhalts, gelesen nach dem Zuklappen.**
        # Die Aufmachgröße kann über dem Bedarf liegen, wenn der Inhalt danach
        # passiv schrumpft (Slicer- und Druckersuche melden sich nach dem
        # Aufmachen); der Rahmen bleibt dann stehen (``fenster.md``). Das
        # ausdrückliche Zuklappen gibt zurück, was der Inhalt nicht mehr
        # braucht. Hier stand ``min(compact, dialog.sizeHint())`` vor dem
        # Aufklappen — ``DialogScrollArea.sizeHint`` rechnet an der Breite des
        # gerade gezeigten Ausschnitts, und im höheren Aufmachrahmen meldete
        # Qt 14 Punkte weniger (470 statt 484), als der Inhalt danach wollte.
        assert dialog.height() < opened, "Zuklappen gibt die Höhe der Zusatzzeilen zurück"
        assert dialog.height() == min(compact, dialog.sizeHint().height())
        # Und es nimmt nicht mehr, als der Inhalt hergibt: Umgebrochen wird an
        # der Breite des Inhalts, nicht an der des Ausschnitts.
        content = dialog._scroll.widget()
        layout = content.layout()
        width = max(content.width(), dialog._scroll.viewport().width())
        needed = (
            max(content.minimumSizeHint().height(), layout.totalHeightForWidth(width))
            if layout.hasHeightForWidth()
            else content.sizeHint().height()
        )
        assert dialog._scroll.viewport().height() >= needed, "zugeklappt ist nichts verdeckt"
        assert dialog.width() == compact_width
        collapsed = dialog.height()
        dialog.resize(dialog.width(), collapsed + 80)
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
        qt_app.setStyleSheet(before)


def test_settings_slicer_choice_and_program_button_share_one_row(qt_app, monkeypatch) -> None:
    """Auswahl und Programmdatei stehen nebeneinander wie die übrigen Formularfelder."""
    from PySide6.QtWidgets import QHBoxLayout

    from app.ui import settings_dialog as module
    from app.ui.settings import UiSettings

    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit(()))
    dialog = module.SettingsDialog(UiSettings())
    try:
        row = dialog.slicer.parentWidget()
        assert row is not None
        row_layout = row.layout()
        assert isinstance(row_layout, QHBoxLayout)
        assert row_layout.indexOf(dialog.slicer) < row_layout.indexOf(dialog.slicer_file)
    finally:
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


def _summary_of(section):
    """Die Zeile unter einer zugeklappten Überschrift, die den Inhalt nennt."""
    from PySide6.QtWidgets import QLabel

    return section.findChild(QLabel, "sectionSummary")


def test_the_closed_settings_name_what_lies_behind_them(qt_app, monkeypatch) -> None:
    """„Weitere Einstellungen" nennt Tastenbelegung und Fernsteuerung (RM-491).

    Seit v0.5.2 liegen sieben Optionen dahinter, und von außen verriet nichts,
    dass es sie gibt. Zugeklappt steht ihr Inhalt unter der Überschrift, ein
    Klick darauf klappt auf, und der nächste Dialog öffnet so, wie der Kunde
    den letzten verließ.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QToolButton

    from app.ui import settings_dialog as module
    from app.ui.settings import UiSettings

    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit(()))

    def settle():
        for _ in range(12):
            qt_app.processEvents()

    dialog = module.SettingsDialog(UiSettings())
    try:
        dialog.show()
        settle()
        summary = _summary_of(dialog.advanced)
        heading = dialog.advanced.findChild(QToolButton)
        assert summary is not None and summary.isVisible(), "zugeklappt steht der Inhalt da"
        for word in ("Tastenbelegung", "Fernsteuerung", "Navigation", "Chat"):
            assert word in summary.text(), (word, summary.text())
        assert heading.accessibleDescription() == summary.text()
        assert not dialog.shortcuts.isVisible()
        QTest.mouseClick(summary, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
        settle()
        assert heading.isChecked() and dialog.shortcuts.isVisible()
        assert not summary.isVisible(), "offen nennt der Inhalt sich selbst"
    finally:
        dialog.close()
        dialog.release()
        dialog.deleteLater()

    again = module.SettingsDialog(UiSettings())
    try:
        heading = again.advanced.findChild(QToolButton)
        assert heading.isChecked(), "der Bereich merkt sich, dass er offen verlassen wurde"
        heading.click()
    finally:
        again.release()
        again.deleteLater()
    closed = module.SettingsDialog(UiSettings())
    try:
        assert not closed.advanced.findChild(QToolButton).isChecked()
    finally:
        closed.release()
        closed.deleteLater()


def test_the_remembered_sections_travel_in_the_settings_file(tmp_path, monkeypatch) -> None:
    """Der Zustand der Abschnitte steht in ``settings.json`` und kommt zurück."""
    from app.ui import settings as settings_module

    monkeypatch.setattr(settings_module, "settings_path", lambda: tmp_path / "settings.json")
    stored = settings_module.UiSettings(open_sections={"settings.more": True})
    assert settings_module.save_settings(stored) is not None
    assert settings_module.load_settings().open_sections == {"settings.more": True}


@pytest.mark.parametrize("option", ["shortcuts", "remote", "remote_port", "language"])
def test_a_setting_from_the_palette_opens_its_row(qt_app, monkeypatch, option) -> None:
    """Die Palette führt zu jeder Zeile, auch hinter „Weitere Einstellungen" (RM-491)."""
    from PySide6.QtWidgets import QToolButton

    from app.ui import settings_dialog as module
    from app.ui.settings import UiSettings

    monkeypatch.setattr(module.discover, "remembered_path", lambda _key: "")
    monkeypatch.setattr(module._SlicerWorker, "work", lambda worker: worker.done.emit(()))
    dialog = module.SettingsDialog(UiSettings())
    try:
        dialog.show_option(option)
        dialog.show()
        for _ in range(12):
            qt_app.processEvents()
        field = getattr(dialog, option)
        assert field.isVisible(), f"{option} steht nach dem Öffnen im Bild"
        # Der Port ist gesperrt, solange die Fernsteuerung aus ist; dann führt
        # der Weg über ihren Haken.
        focused = dialog.remote if option == "remote_port" else field
        assert dialog.focusWidget() is focused, (option, dialog.focusWidget())
        hidden_behind = option != "language"
        assert dialog.advanced.findChild(QToolButton).isChecked() is hidden_behind
    finally:
        dialog.close()
        dialog.release()
        dialog.deleteLater()


def test_the_palette_offers_every_visible_setting_under_its_row_name() -> None:
    """Eine Quelle für Formular und Palette; die 3D-Maus erst, wenn sie da ist."""
    from app.ui.settings import UiSettings
    from app.ui.settings_dialog import SPACEMOUSE_OPTIONS, option_titles, searchable_options

    titles = searchable_options(UiSettings())
    assert titles["shortcuts"] == option_titles()["shortcuts"] == "Tastenbelegung"
    assert "Fernsteuerung" in titles["remote"]
    assert not set(SPACEMOUSE_OPTIONS) & set(titles), "ohne gesehenes Gerät keine 3D-Maus"
    seen = searchable_options(UiSettings(spacemouse_seen=True))
    assert set(SPACEMOUSE_OPTIONS) <= set(seen)
    assert "3D-Maus" in seen["spacemouse_invert"], "„Richtung umkehren“ allein sagt nicht, wessen"
