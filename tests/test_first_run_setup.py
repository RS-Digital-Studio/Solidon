"""Slicer, passende Drucker und eigene Maße in den ersten Schritten."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import mock

import pytest
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from app.core import discover
from app.core.errors import AppError
from app.core.knowledge import profiles
from app.core.types import PrinterProfile
from app.ui import first_run
from app.ui.first_run import FirstRunDialog
from app.ui.settings import UiSettings


def _grouped_titles(dialog: FirstRunDialog) -> list[list[str]]:
    """Die Druckerliste, wie der Kunde sie liest: je Verfahren eine Gruppe.

    Ein Gruppenkopf trennt; „Benutzerdefiniert …" steht als eigene letzte
    Gruppe. Innerhalb jeder Gruppe ist die Liste nach Titel sortiert (RM-071).
    """
    groups: list[list[str]] = [[]]
    for row in range(dialog.printer.count()):
        data = str(dialog.printer.itemData(row) or "")
        if data == first_run._GROUP_HEADER:
            groups.append([])
            continue
        if data == "__custom__":
            groups.append([dialog.printer.itemText(row)])
            continue
        groups[-1].append(dialog.printer.itemText(row))
    return [group for group in groups if group]


@pytest.mark.parametrize("commit", ["keyboard", "mouse"])
def test_printer_popup_filters_groups_and_commits_the_source_row(qt_app, commit: str) -> None:
    """Suchzeile und Listenindex bleiben auch mit ausgefilterten Gruppen getrennt."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QVBoxLayout

    dialog = QDialog()
    box = first_run.PrinterComboBox(dialog)
    layout = QVBoxLayout(dialog)
    layout.addWidget(box)
    for title, identifier in (
        ("FDM", first_run._GROUP_HEADER),
        ("Hersteller Alpha", "alpha"),
        ("Resin", first_run._GROUP_HEADER),
        ("Hersteller Beta", "beta"),
    ):
        box.addItem(title, identifier)
        if identifier == first_run._GROUP_HEADER:
            box.model().item(box.count() - 1).setFlags(Qt.ItemFlag.NoItemFlags)
    box.setCurrentIndex(1)
    try:
        dialog.show()
        box.showPopup()
        box.search_field.setText("bEtA")
        qt_app.processEvents()
        assert box.currentData() == "alpha"
        assert box.filtered.rowCount() == 2
        assert box.filtered.index(0, 0).data() == "Resin"
        assert box.popup.layout().itemAt(0).widget() is box.search_field
        assert box.results.currentIndex().data(Qt.ItemDataRole.UserRole) == "beta"
        if commit == "keyboard":
            QTest.keyClick(box.search_field, Qt.Key.Key_Return)
        else:
            point = box.results.visualRect(box.filtered.index(1, 0)).center()
            QTest.mouseClick(box.results.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert box.currentData() == "beta"
        assert box.currentIndex() == 3
        assert not box.popup.isVisible()
        assert dialog.isVisible()
        box.showPopup()
        box.search_field.setText("Später gefunden")
        assert box.filtered.rowCount() == 0
        box.addItem("Später gefunden", "late")
        qt_app.processEvents()
        assert box.filtered.rowCount() == 2
        assert box.filtered.index(0, 0).data() == "Resin"
        assert box.results.currentIndex().data(Qt.ItemDataRole.UserRole) == "late"
        assert box.currentData() == "beta"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_printer_popup_keeps_search_fixed_and_escape_preserves_the_dialog(qt_app) -> None:
    """Scrollen, keine Treffer und nachgelieferte Profile verändern die Auswahl nicht."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QVBoxLayout

    dialog = QDialog()
    box = first_run.PrinterComboBox(dialog)
    layout = QVBoxLayout(dialog)
    layout.addWidget(box)
    for row in range(40):
        box.addItem(f"Drucker {row:02d}", str(row))
    box.setCurrentIndex(7)
    try:
        dialog.show()
        box.showPopup()
        qt_app.processEvents()
        position = box.search_field.pos()
        box.results.verticalScrollBar().setValue(box.results.verticalScrollBar().maximum())
        assert box.search_field.pos() == position
        box.search_field.setText("Später gefunden")
        qt_app.processEvents()
        assert box.empty.isVisible()
        QTest.keyClick(box.search_field, Qt.Key.Key_Return)
        assert box.popup.isVisible()
        assert box.currentData() == "7"
        box.addItem("Später gefunden", "late")
        qt_app.processEvents()
        assert box.filtered.rowCount() == 1
        assert box.results.currentIndex().data(Qt.ItemDataRole.UserRole) == "late"
        assert box.currentData() == "7"
        QTest.keyClick(box.search_field, Qt.Key.Key_Escape)
        assert not box.popup.isVisible()
        assert dialog.isVisible()
        assert box.currentData() == "7"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_exact_printer_name_precedes_a_partial_model_number_match(qt_app) -> None:
    """Modellnummer 2 und Düse 0.2 dürfen bei Enter keine falsche Maschine wählen."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QVBoxLayout

    dialog = QDialog()
    box = first_run.PrinterComboBox(dialog)
    layout = QVBoxLayout(dialog)
    layout.addWidget(box)
    box.addItem("FDM", first_run._GROUP_HEADER)
    box.model().item(0).setFlags(Qt.ItemFlag.NoItemFlags)
    box.addItem("Elegoo Centauri Carbon 0.2 nozzle", "cc1")
    box.addItem("Elegoo Centauri Carbon 2 0.2 nozzle", "cc2")
    box.setCurrentIndex(1)
    try:
        dialog.show()
        box.showPopup()
        box.search_field.setText("Elegoo Centauri Carbon 2 0.2 nozzle")
        assert box.filtered.rowCount() == 3
        assert box.filtered.index(0, 0).data() == "FDM"
        assert box.filtered.index(1, 0).data(Qt.ItemDataRole.UserRole) == "cc2"
        assert box.currentData() == "cc1"
        QTest.keyClick(box.search_field, Qt.Key.Key_Return)
        assert box.currentData() == "cc2"
    finally:
        dialog.close()
        dialog.deleteLater()


def _assert_grouped_and_sorted(dialog: FirstRunDialog) -> None:
    groups = _grouped_titles(dialog)
    assert groups[-1] == [dialog.printer.itemText(dialog.printer.findData("__custom__"))]
    for group in groups[:-1]:
        assert group == sorted(group, key=str.casefold), group
    # Die Resin-Geräte stehen als eigene Gruppe hinter den FDM-Druckern,
    # nie dazwischen — der Kopf ist nicht wählbar.
    known = profiles.printer_profiles()
    technologies = [
        [known[str(dialog.printer.itemData(row))].technology]
        for row in range(dialog.printer.count())
        if str(dialog.printer.itemData(row) or "") in known
    ]
    flat = [entry[0] for entry in technologies]
    assert flat == sorted(flat, key=("fdm", "resin").index)
    for row in range(dialog.printer.count()):
        if str(dialog.printer.itemData(row) or "") == first_run._GROUP_HEADER:
            item = dialog.printer.model().item(row)
            assert not item.flags() & Qt.ItemFlag.ItemIsSelectable


@pytest.fixture
def setup_dialog(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> FirstRunDialog:
    """Die Zusatzprogramme haben für diese gezielten Bedienwege keine Bedeutung.

    Auch kein gemerkter Slicer: Die Nutzerverzeichnisse gelten für den ganzen
    Lauf, und ein Test des Druckdialogs, der vorher im selben Prozess den
    Slicer wechselte, hinterließ seinen Pfad als Vorauswahl.
    """
    monkeypatch.setattr(FirstRunDialog, "look", lambda _self: None)
    discover.remember_path("slicer", "")
    return FirstRunDialog(UiSettings())


def test_the_custom_printer_reads_in_one_column(setup_dialog: FirstRunDialog) -> None:
    """Eigener Drucker: Beschriftung neben dem Feld, Bauraum in einer Zeile (RM-515).

    Mit ``WrapLongRows`` brach der Bauraum unter seine Beschriftung, drei
    Überschriften standen über drei Feldern, und der Namenshinweis war eine
    eigene Zeile. Der Weg zum eigenen Drucker steht an der Druckerliste.
    """
    from PySide6.QtWidgets import QFormLayout

    form = setup_dialog.custom_printer.layout()
    assert isinstance(form, QFormLayout)
    assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.DontWrapRows
    _row, name_role = form.getWidgetPosition(setup_dialog.printer_name)
    assert name_role == QFormLayout.ItemRole.FieldRole
    assert setup_dialog.printer_name.toolTip(), "der Hinweis steht am Feld"
    rows = {form.getWidgetPosition(field)[0] for field in setup_dialog.printer_dimensions}
    rows |= {
        form.getWidgetPosition(field.parentWidget())[0]
        for field in setup_dialog.printer_dimensions
        if field.parentWidget() is not setup_dialog.custom_printer
    }
    assert len({row for row in rows if row >= 0}) == 1, "Breite, Tiefe und Höhe in einer Zeile"
    assert "Benutzerdefiniert" in setup_dialog.printer.toolTip()
    assert "Benutzerdefiniert" in setup_dialog.printer.accessibleDescription()

    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData("__custom__"))
    assert not setup_dialog.custom_printer.isHidden()
    labels = [
        form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget()
        for row in range(form.rowCount())
        if form.itemAt(row, QFormLayout.ItemRole.LabelRole) is not None
    ]
    basics = setup_dialog.basics.layout()
    assert isinstance(basics, QFormLayout)
    language = basics.labelForField(setup_dialog.language)
    assert language is not None
    widths = {label.minimumWidth() for label in labels} | {language.minimumWidth()}
    assert len(widths) == 1, f"eine Beschriftungskante, nicht {sorted(widths)}"


def test_selected_slicer_filters_printers_and_keeps_custom_choice(
    setup_dialog: FirstRunDialog, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Drucker stammen jeweils aus dem ausdrücklich gewählten Slicer."""
    known = profiles.printer_profiles()
    first = "prusa-mk4s"
    second = "centauri-carbon-2"
    machine_names = {
        "PrusaSlicer.exe": (known[first],),
        "elegoo-slicer.exe": (known[second],),
    }
    monkeypatch.setattr(
        first_run.slicer_profiles,
        "discover_printers",
        lambda path, _flavour: machine_names[path.name],
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
        # Die Resin-Geräte hängen an keinem FDM-Slicer und bleiben stehen.
        assert setup_dialog.printer.findData("generic-resin-130") >= 0
        _assert_grouped_and_sorted(setup_dialog)


def test_slicer_survey_prefers_the_current_source_over_a_saved_namesake(
    setup_dialog: FirstRunDialog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein gleich benanntes gespeichertes Profil verdrängt nicht die aktuelle Slicer-ID."""
    template = profiles.printer(profiles.DEFAULT_PRINTER)
    discovered = replace(template, id="slicer-current-source")
    monkeypatch.setattr(
        first_run.slicer_profiles, "discover_printers", lambda *_args: (discovered,)
    )
    monkeypatch.setattr(
        first_run.slicer_profiles, "chosen_machine", lambda *_args: discovered.title
    )
    survey = first_run._PrinterSurvey(Path("OrcaSlicer.exe"))
    found: list[first_run.PrinterChoices] = []
    survey.done.connect(found.append)
    survey.work()
    assert len(found) == 1
    assert found[0].suggested == discovered.id


def test_failed_slicer_worker_keeps_saved_custom_printers_and_current_choice(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Slicer ohne Familie verbirgt weder eigene Drucker noch deren aktuelle Auswahl.

    Seit dem 22.09.2026 ist ein Programm ohne Familie kein Fehler mehr, sondern
    die Familie ``other`` (RM-071): Die Erhebung läuft durch und nennt keine
    Drucker, und der Satz darunter sagt, warum. Zur Wahl steht so eines seit
    dem 08.10.2026 nur noch als Resin-Slicer.
    """
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    template = profiles.printer(profiles.DEFAULT_PRINTER)
    first = profiles.save_printer(replace(template, id="user-workshop", title="Werkstatt"))
    second = profiles.save_printer(replace(template, id="user-garage", title="Garage"))
    setup_dialog._fill_printers(tuple(profiles.printer_profiles()))
    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData(first.id))
    setup_dialog._fill_slicers((Path("CHITUBOX.exe"),))
    setup_dialog.slicer.setCurrentIndex(1)

    assert setup_dialog.wait_for_survey()
    assert setup_dialog.printer.isEnabled()
    assert setup_dialog.printer.currentData() == first.id
    assert setup_dialog.printer.findData(second.id) >= 0
    assert setup_dialog.printer.findData("__custom__") >= 0
    assert "kennt Solidon nicht" in setup_dialog.printer_state.text()


def test_only_slicers_solidon_works_with_are_offered(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„erste schritte und druckdialog sollten auch nur die unterstützen slicer anzeigen“
    (Robert, 08.10.2026).

    Die Suche findet nur Namen aus Solidons Liste, aber der gemerkte Pfad steht
    vorn, und über „Programm wählen …“ ließ sich jedes Programm wählen — danach
    stand es in jeder Slicerliste. Die Liste filtert der Kern
    (``test_discover.py::test_only_slicers_solidon_works_with_are_found``); hier
    zählt, dass auch der gemerkte Eintrag beim Öffnen nicht erscheint.
    """
    foreign = tmp_path / "notepad.exe"
    foreign.write_bytes(b"")
    discover.remember_path("slicer", str(foreign))
    again = FirstRunDialog(UiSettings())
    try:
        assert again.slicer.findData(str(foreign)) < 0, "auch nicht als gemerkter Slicer"
    finally:
        again.release()
        discover.remember_path("slicer", "")


def test_choosing_a_program_solidon_does_not_work_with_is_refused(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Programm wählen …“ nimmt nur einen Slicer an — und sagt es, mit dem Weg zu einem anderen.

    Ein Satz ohne Handlung wäre eine Sackgasse (Regel 17): Die Absage bietet
    *Einen anderen Slicer auswählen* an, und der Knopf öffnet die Auswahl erneut.
    """
    monkeypatch.setattr(first_run.slicer_profiles, "discover_printers", lambda *_args: ())
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: "")
    orca = tmp_path / "OrcaSlicer" / "orca-slicer.exe"
    picks = iter([str(tmp_path / "notepad.exe"), str(orca)])
    monkeypatch.setattr(
        first_run.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (next(picks), "")),
    )
    shown: list[AppError] = []

    def refuse(error: AppError, _parent: object = None, handlers: object = None) -> None:
        shown.append(error)
        assert isinstance(handlers, dict)
        handlers["choose_slicer"](error)

    monkeypatch.setattr(first_run, "show_error", refuse)
    setup_dialog._choose_slicer_file()

    assert len(shown) == 1, "einmal abgelehnt"
    assert "notepad.exe" in str(shown[0].detail)
    assert "Bambu Studio" in str(shown[0].detail), "die Absage nennt die Slicer"
    assert shown[0].suggestions[0].id == "choose_slicer"
    assert Path(setup_dialog.slicer.currentData()) == orca, "die zweite Wahl gilt"

    # *Abbrechen* lässt die Wahl, wie sie war.
    picks = iter([str(tmp_path / "notepad.exe")])
    monkeypatch.setattr(first_run, "show_error", lambda error, *_args: shown.append(error))
    setup_dialog._choose_slicer_file()
    assert len(shown) == 2
    assert Path(setup_dialog.slicer.currentData()) == orca, "abgebrochen, nichts geändert"


def test_choosing_a_slicer_printer_again_keeps_the_nozzle_from_the_print_dialog(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Liste nennt den Drucker ohne Düse, und Speichern setzt eine im
    Druckdialog gewählte Düse nicht still auf die Variante des Slicers zurück."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    template = profiles.printer(profiles.DEFAULT_PRINTER)
    found = replace(
        template,
        id="slicer-orca-a1",
        title="Bambu Lab A1 0.4 nozzle",
        vendor="BBL",
        nozzle_diameter=0.4,
        extrusion_width=0.42,
    )
    # So legt der Druckdialog eine andere Düse ab (``_nozzle_changed``).
    profiles.save_printer(replace(found, nozzle_diameter=0.6, extrusion_width=0.63))
    setup_dialog._discovered_printers = {found.id: found}
    setup_dialog._fill_printers((found.id,), found.id)

    assert setup_dialog.printer.currentData() == found.id
    assert setup_dialog.printer.currentText() == "Bambu Lab A1"
    assert setup_dialog._save_custom_printer()
    assert profiles.printer_profiles()[found.id].nozzle_diameter == pytest.approx(0.6)


def test_slicer_profile_search_stays_outside_the_gui_thread(
    setup_dialog: FirstRunDialog, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch das Wechseln nach der ersten Erhebung liest Profile im Arbeiter."""
    import threading

    thread_ids: list[int] = []

    def known(_path: Path, _flavour: str) -> tuple[PrinterProfile, ...]:
        thread_ids.append(threading.get_ident())
        return ()

    monkeypatch.setattr(first_run.slicer_profiles, "discover_printers", known)
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
    monkeypatch.setattr(
        first_run.slicer_profiles,
        "discover_printers",
        lambda *_args: (profiles.printer("prusa-mk4s"),),
    )
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: name)
    setup_dialog._fill_slicers((Path("PrusaSlicer.exe"),))
    setup_dialog.slicer.setCurrentIndex(1)
    assert setup_dialog.wait_for_survey()
    assert setup_dialog.printer.currentData() == "prusa-mk4s"


def test_the_remembered_slicer_suggests_its_printer_and_done_waits_for_it(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der gemerkte Slicer schlägt seinen Drucker gleich beim Öffnen vor, und
    *Fertig* speichert ihn auch, wenn die Suche noch läuft — ohne auf sie zu warten.

    Robert, 27.09.2026: Der ElegooSlicer steht auf dem Centauri Carbon 2, im
    Druckdialog stand danach der allgemeine Drucker. Die Drucker des Slicers
    wurden erst nach der Programmsuche gesucht, rund sechs Sekunden nach dem
    Öffnen, und *Fertig* nach vier Sekunden übernahm die Vorbelegung.
    """
    import threading

    slicer = tmp_path / "elegoo-slicer.exe"
    slicer.write_text("")
    discover.remember_path("slicer", str(slicer))
    name = profiles.printer("centauri-carbon-2").title
    gate = threading.Event()

    def slow_machine(*_args: object) -> str:
        gate.wait(10.0)
        return name

    monkeypatch.setattr(FirstRunDialog, "look", lambda _self: None)
    monkeypatch.setattr(
        first_run.slicer_profiles,
        "discover_printers",
        lambda *_args: (profiles.printer("centauri-carbon-2"),),
    )
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", slow_machine)
    settings = UiSettings(printer=profiles.DEFAULT_PRINTER)

    dialog = FirstRunDialog(settings)

    assert dialog._printer_survey is not None, "die Drucker des gemerkten Slicers werden gesucht"
    assert not dialog.printer.isEnabled(), "und die Auswahl sagt, dass sie noch kommt"
    # *Fertig* hält den Oberflächen-Thread nicht an (RM-289, B10): Der Klick
    # kehrt sofort zurück, solange die Suche noch am Tor wartet, und die
    # schließenden Knöpfe sind bis zur Antwort gesperrt.
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert not dialog.start.isEnabled() and not dialog.open_button.isEnabled()
    assert not dialog.inventory_button.isEnabled()
    gate.set()
    assert dialog.wait_for_survey()
    assert dialog.result() == QDialog.DialogCode.Accepted, (
        "der gemerkte Klick läuft nach der Antwort"
    )
    assert dialog.start.isEnabled()
    dialog.apply_to(settings)
    assert settings.printer == "centauri-carbon-2"


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
        first_run.slicer_profiles,
        "discover_printers",
        lambda path, _flavour: tuple(
            entry for entry in known.values() if entry.title == names[path.name]
        ),
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

    def names(path: Path, _flavour: str) -> tuple[PrinterProfile, ...]:
        if path.name == "PrusaSlicer.exe":
            entered.set()
            assert release.wait(5)
            return (known["prusa-mk4s"],)
        return (known["centauri-carbon-2"],)

    monkeypatch.setattr(first_run.slicer_profiles, "discover_printers", names)
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
    monkeypatch.setattr(first_run.slicer_profiles, "discover_printers", lambda *_args: ())
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: "")
    setup_dialog._choose_slicer_file()
    assert setup_dialog.wait_for_survey()
    assert setup_dialog.slicer.currentData() == str(path)
    assert discover.remembered_path("slicer") == ""
    setup_dialog.apply_to(setup_dialog.settings)
    assert discover.remembered_path("slicer") == str(path)


def test_a_slicer_chosen_with_forward_slashes_ends_its_printer_search(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Dateidialog nennt unter Windows ``C:/…``, die Suche antwortet mit ``C:\\…``.

    Verglich der Dialog beide als Text, verwarf er die Antwort und ließ die
    Druckerliste grau mit „werden gesucht …“ stehen; „Speichern und starten“
    tat danach nichts mehr (RM-335).
    """
    path = tmp_path / "portable" / "orca-slicer.exe"
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (path.as_posix(), ""))
    monkeypatch.setattr(first_run.slicer_profiles, "discover_printers", lambda *_args: ())
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: "")
    setup_dialog._choose_slicer_file()
    assert setup_dialog.wait_for_survey()
    assert setup_dialog._printer_survey is None
    assert setup_dialog.printer.isEnabled()
    assert Path(setup_dialog.slicer.currentData()) == path
    setup_dialog.apply_to(setup_dialog.settings)
    assert Path(discover.remembered_path("slicer")) == path


def test_a_remembered_slicer_with_forward_slashes_is_read_in_the_native_form(
    tmp_path: Path,
) -> None:
    """Ein Pfad, den 0.5.1 mit ``/`` gemerkt hat, kommt in der Schreibweise des
    Systems zurück — sonst findet ihn keine Liste wieder, deren Einträge die
    Programmsuche in dieser Schreibweise anlegt (RM-335)."""
    path = tmp_path / "orca-slicer.exe"
    discover.remember_path("slicer", path.as_posix())
    try:
        assert discover.remembered_path("slicer") == str(path)
    finally:
        discover.remember_path("slicer", "")


#: Nur Windows liest Pfade ohne Rücksicht auf Groß- und Kleinschreibung; dort
#: allein kann derselbe Slicer in zwei Schreibweisen ankommen (RM-418).
_CASE_BLIND = pytest.mark.skipif(
    Path("A") != Path("a"), reason="Pfade unterscheiden hier Groß- und Kleinschreibung"
)


def _other_case(path: Path) -> str:
    """Derselbe Pfad mit anders geschriebenem Laufwerk — so nennt ihn mancher Dateidialog."""
    text = str(path)
    return text[0].swapcase() + text[1:]


@_CASE_BLIND
def test_a_slicer_in_another_case_stays_chosen_in_the_first_run(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Liste fasst das Laufwerk ``c:`` und ``C:`` über ``Path`` zusammen, gesucht
    wurde der exakte Text: Die Wahl sprang auf „Später auswählen“ (RM-418)."""
    monkeypatch.setattr(first_run.slicer_profiles, "discover_printers", lambda *_args: ())
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: "")
    found = tmp_path / "OrcaSlicer.exe"
    setup_dialog._fill_slicers((Path(_other_case(found)),))
    setup_dialog.slicer.setCurrentIndex(1)
    assert setup_dialog.wait_for_survey()
    setup_dialog._fill_slicers((found,))
    assert setup_dialog.slicer.currentIndex() != 0, "nicht „Später auswählen“"
    assert Path(setup_dialog.slicer.currentData()) == found
    assert setup_dialog.slicer.count() == 2, "eine Zeile je Programm"


@_CASE_BLIND
def test_a_remembered_slicer_in_another_case_is_the_one_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Druckdialog und Filamentwähler nahmen bei abweichender Schreibweise den
    ersten Fund statt des gemerkten Slicers (RM-418)."""
    from app.ui import filament_picker
    from app.ui.print_settings_dialog import PrintSettingsDialog

    first = tmp_path / "PrusaSlicer.exe"
    remembered = tmp_path / "OrcaSlicer.exe"
    found = (first, remembered)
    for program in found:
        program.write_bytes(b"")
    monkeypatch.setattr(discover, "remembered_path", lambda _key: _other_case(remembered))
    assert PrintSettingsDialog._choose_slicer(mock.Mock(), found) == remembered

    used: list[Path] = []
    monkeypatch.setattr(discover, "find_programs", lambda *_args: found)
    monkeypatch.setattr(
        filament_picker, "detect", lambda path: used.append(path) or mock.Mock(flavour="orca")
    )
    monkeypatch.setattr(filament_picker.slicer_profiles, "find_profiles", lambda *_a, **_k: ())
    filament_picker.slicer_filaments()
    assert used == [remembered]


def test_setup_and_print_dialog_accept_the_same_smallest_nozzle(
    setup_dialog: FirstRunDialog,
) -> None:
    """Die kleinste Düse ist eine Zahl: Sie trägt die Druckgrenze (§11.2), und
    die Ersteinrichtung nahm 0,05 mm an, die der Druckdialog still auf 0,1 kürzte."""
    from app.core.units import SMALLEST_NOZZLE
    from app.ui import print_settings_dialog

    assert setup_dialog.printer_nozzle.minimum() == pytest.approx(SMALLEST_NOZZLE)
    assert print_settings_dialog._NOZZLE_RANGE_MM[0] == pytest.approx(SMALLEST_NOZZLE)


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
    _assert_grouped_and_sorted(setup_dialog)


def test_discovered_printer_stays_a_draft_across_language_rebuild_until_accepted(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lesen und Sprachwechsel schreiben keine Profile; übernommen wird nur die Auswahl."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    template = profiles.printer(profiles.DEFAULT_PRINTER)
    first = replace(template, id="slicer-orca-first", title="Werkstatt mit 0,4-mm-Düse")
    second = replace(
        template,
        id="slicer-orca-second",
        title="Werkstatt mit 0,6-mm-Düse",
        nozzle_diameter=0.6,
        extrusion_width=0.63,
        build_volume=(315.0, 270.0, 420.0),
    )
    monkeypatch.setattr(
        first_run.slicer_profiles, "discover_printers", lambda *_args: (first, second)
    )
    monkeypatch.setattr(first_run.slicer_profiles, "chosen_machine", lambda *_args: first.title)
    setup_dialog._fill_slicers((Path("OrcaSlicer.exe"),))
    setup_dialog.slicer.setCurrentIndex(1)
    assert setup_dialog.wait_for_survey()
    assert setup_dialog.printer.findData(second.id) >= 0
    assert not {first.id, second.id} & profiles.user_printer_profiles().keys()
    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData(second.id))
    persisted = setup_dialog.settings.printer
    setup_dialog._carry_over(setup_dialog.settings)
    assert setup_dialog.settings.printer == persisted
    rebuilt = FirstRunDialog(
        setup_dialog.settings,
        discovered_printers=setup_dialog.discovered_printers,
        printer_selection=setup_dialog.printer_selection,
    )
    try:
        assert rebuilt.wait_for_survey()
        assert rebuilt.printer.currentData() == second.id
        assert not {first.id, second.id} & profiles.user_printer_profiles().keys()
        rebuilt.accept()
        rebuilt.apply_to(rebuilt.settings)
        assert rebuilt.settings.printer == second.id
        assert profiles.printer(second.id).build_volume == pytest.approx(second.build_volume)
        assert profiles.printer(second.id).nozzle_diameter == pytest.approx(0.6)
        assert first.id not in profiles.user_printer_profiles()
    finally:
        rebuilt.release()


@pytest.mark.parametrize("close_window", [False, True])
def test_language_switch_then_skip_does_not_store_an_unsaved_printer(
    setup_dialog: FirstRunDialog,
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    close_window: bool,
) -> None:
    """Sprachwechsel trägt die Auswahl weiter; Später und Fensterkreuz speichern keine fremde ID."""
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language
    from app.ui import main_window
    from app.ui.session import Session

    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    template = profiles.printer(profiles.DEFAULT_PRINTER)
    discovered = replace(template, id="slicer-orca-language-draft", title="Ungespeicherte Maschine")
    spoken = get_language()
    other_language = "en" if spoken != "en" else "de"
    rounds: list[str] = []
    saved: list[str] = []

    class LanguageDialog(FirstRunDialog):
        def exec(self) -> int:
            if not rounds:
                self._discovered_printers = {discovered.id: discovered}
                self._fill_printers((discovered.id,))
                self.printer.setCurrentIndex(self.printer.findData(discovered.id))
                rounds.append(discovered.id)
                self.language.setCurrentIndex(self.language.findData(other_language))
                assert self.result() == first_run.LANGUAGE_CHANGED
            else:
                assert self.printer.currentData() == discovered.id
                rounds.append(str(self.printer.currentData()))
                if close_window:
                    self.close()
                else:
                    self.reject()
            return self.result()

    monkeypatch.setattr(first_run, "FirstRunDialog", LanguageDialog)
    monkeypatch.setattr(
        main_window, "save_settings", lambda settings: saved.append(settings.printer)
    )
    monkeypatch.setattr(Session, "set_agent_backend", lambda *_args: None)
    settings = UiSettings(language=spoken, printer=profiles.DEFAULT_PRINTER)
    window = main_window.MainWindow(Session(), settings)
    monkeypatch.setattr(window, "_refresh_chat_availability", lambda **_kwargs: None)
    try:
        window.action_first_run()
        assert rounds == [discovered.id, discovered.id]
        assert settings.language == other_language
        assert settings.first_run_done
        assert settings.printer == profiles.DEFAULT_PRINTER
        assert saved and set(saved) == {profiles.DEFAULT_PRINTER}
        assert discovered.id not in profiles.user_printer_profiles()
    finally:
        window.wait_for_workers()
        window.close()
        install_language(spoken)
        set_language(spoken)


@pytest.mark.parametrize("route", ["accept", "open", "inventory", "language", "apply"])
def test_failed_slicer_path_save_keeps_first_run_open_and_can_be_retried(
    setup_dialog: FirstRunDialog,
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    """Ein Schreibfehler übernimmt keine Antworten und startet keinen nachgelagerten Weg."""
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language

    dialog = setup_dialog
    spoken = get_language()
    before = replace(dialog.settings)
    destination = "en" if before.language != "en" else "de"
    opened: list[str] = []
    dialog.importRequested.connect(lambda: opened.append("import"))
    dialog.inventoryRequested.connect(lambda: opened.append("inventory"))
    with QSignalBlocker(dialog.slicer), QSignalBlocker(dialog.language):
        dialog.slicer.addItem("OrcaSlicer", userData="OrcaSlicer.exe")
        dialog.slicer.setCurrentIndex(dialog.slicer.count() - 1)
        dialog.language.setCurrentIndex(dialog.language.findData(destination))
    save_path = discover.remember_path
    failed_save = mock.Mock(side_effect=OSError("Datenträger nicht beschreibbar"))
    monkeypatch.setattr(discover, "remember_path", failed_save)

    def follow_route() -> None:
        if route == "accept":
            dialog.accept()
        elif route == "open":
            dialog._open()
        elif route == "inventory":
            dialog._open_inventory()
        elif route == "language":
            dialog._language_changed()
        else:
            dialog.apply_to(dialog.settings)

    try:
        dialog.show()
        qt_app.processEvents()
        follow_route()
        assert failed_save.call_count == 1
        assert dialog.isVisible()
        assert dialog.result() == FirstRunDialog.DialogCode.Rejected
        assert dialog.settings == before
        assert not opened
        assert "Schreibrechte" in dialog.printer_state.text()

        monkeypatch.setattr(discover, "remember_path", save_path)
        follow_route()
        assert discover.remembered_path("slicer") == "OrcaSlicer.exe"
        assert dialog.settings.language == destination
        expected = {"open": ["import"], "inventory": ["inventory"]}.get(route, [])
        assert opened == expected
        if route == "language":
            assert dialog.result() == first_run.LANGUAGE_CHANGED
        elif route == "apply":
            assert dialog.settings.first_run_done
        else:
            assert dialog.result() == FirstRunDialog.DialogCode.Accepted
    finally:
        dialog.close()
        install_language(spoken)
        set_language(spoken)


def _room(dialog: FirstRunDialog) -> int:
    """Die Breite, die ``fit_dialog_to_screen`` einem Dialog höchstens lässt."""
    from app.ui.style import NORMAL

    screen = dialog.screen()
    assert screen is not None
    border = dialog.frameGeometry().width() - dialog.width()
    return screen.availableGeometry().width() - 2 * NORMAL - border


def _sideways_at_most(dialog: FirstRunDialog, natural: int) -> None:
    """Quer rollt höchstens, was der Bildschirm von der natürlichen Breite abschneidet."""
    assert dialog._scroll.horizontalScrollBar().maximum() <= max(0, natural - dialog.width())


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
@pytest.mark.parametrize("technology", ["fdm", "resin"])
def test_custom_printer_natural_width_and_manual_height_survive_toggling(
    setup_dialog: FirstRunDialog, qt_app: QApplication, language: str, technology: str
) -> None:
    """Die langen Maßzeilen bekommen Platz; eine bewusst gewählte Höhe bleibt erhalten.

    Platz heißt: die natürliche Breite samt zugeklappter Maßzeilen
    (``_natural_width``), soweit der Bildschirm sie lässt. Offscreen ist er
    800 Punkte breit, und französisch braucht der Dialog dort 973 — was der
    Bildschirm abschneidet, rollt (``fenster.md``), mehr nicht. Auf einem
    Bildschirm mit Platz rollt nichts.
    """
    from PySide6.QtTest import QTest

    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language
    from app.ui.theme import apply_theme

    spoken = get_language()
    apply_theme(qt_app, UiSettings().theme)
    install_language(language)
    set_language(language)
    dialog = FirstRunDialog(UiSettings(language=language))
    try:
        dialog.show()
        QTest.qWait(100)
        initial_height = dialog.height()
        initial_width = dialog.width()
        natural = dialog._natural_width()
        assert initial_width == min(natural, _room(dialog)), "beim Öffnen so breit wie nötig"
        _sideways_at_most(dialog, natural)
        default = dialog.printer.currentData()
        dialog.printer.setCurrentIndex(dialog.printer.findData("__custom__"))
        dialog.printer_technology.setCurrentIndex(dialog.printer_technology.findData(technology))
        QTest.qWait(100)
        _sideways_at_most(dialog, natural)
        assert dialog.width() == initial_width
        # Die Maßzeilen dürfen den Rahmen wachsen lassen, zurückgegeben wird
        # nichts — sonst spränge er bei jedem Wechsel (RM-487).
        assert dialog.height() >= initial_height
        expanded_height = dialog.height()
        dialog.printer.setCurrentIndex(dialog.printer.findData(default))
        QTest.qWait(100)
        assert dialog.height() == expanded_height
        assert dialog.width() == initial_width

        manual_height = dialog.height() - 70
        dialog.resize(dialog.width(), manual_height)
        QTest.qWait(100)
        dialog.printer.setCurrentIndex(dialog.printer.findData("__custom__"))
        QTest.qWait(100)
        assert dialog.height() == manual_height
        _sideways_at_most(dialog, natural)
        dialog.printer.setCurrentIndex(dialog.printer.findData(default))
        QTest.qWait(100)
        assert dialog.height() == manual_height
    finally:
        dialog.release()
        dialog.close()
        install_language(spoken)
        set_language(spoken)


def test_printer_search_preserves_the_confirmed_choice_across_language_changes(
    setup_dialog: FirstRunDialog,
) -> None:
    """Freier Suchtext ändert die bestätigte Druckerwahl auch beim Sprachwechsel nicht."""
    previous = str(setup_dialog.printer.currentData())
    query = "Dieser Drucker ist noch kein Treffer"
    setup_dialog.printer.search_field.setText(query)
    assert setup_dialog.printer.currentData() == previous
    assert setup_dialog.start.isEnabled()
    assert setup_dialog.open_button.isEnabled()
    assert setup_dialog.inventory_button.isEnabled()
    setup_dialog._carry_over(setup_dialog.settings)
    rebuilt = FirstRunDialog(
        setup_dialog.settings,
        discovered_printers=setup_dialog.discovered_printers,
        printer_query=setup_dialog.printer_query,
    )
    try:
        assert rebuilt.printer.search_field.text() == query
        assert rebuilt.printer.currentData() == previous
        assert rebuilt.start.isEnabled()
        rebuilt.apply_to(rebuilt.settings)
        assert rebuilt.settings.first_run_done
        assert rebuilt.settings.printer == previous
    finally:
        rebuilt.release()


def test_a_custom_resin_printer_is_saved_with_pixel_and_wall_and_starts_with_resin(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein eigener Resin-Drucker trägt Pixel und Mindestwand, keine Düse — und
    das Projekt danach beginnt mit Harz, nicht mit PLA (RM-071, Abnahme 5)."""
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    setup_dialog.printer.setCurrentIndex(setup_dialog.printer.findData("__custom__"))
    setup_dialog.printer_name.setText("Mars im Keller")
    setup_dialog.printer_technology.setCurrentIndex(
        setup_dialog.printer_technology.findData("resin")
    )
    assert setup_dialog.printer_pixel.isVisibleTo(setup_dialog.custom_printer)
    assert not setup_dialog.printer_nozzle.isVisibleTo(setup_dialog.custom_printer)
    for field, value in zip(setup_dialog.printer_dimensions, (143, 90, 175), strict=True):
        field.setValue(value)
    setup_dialog.printer_pixel.setValue(0.035)
    setup_dialog.printer_wall.setValue(0.5)
    draft = setup_dialog.custom_printer_draft()
    assert draft is not None and draft.technology == "resin"

    setup_dialog.apply_to(setup_dialog.settings)
    entry = profiles.printer(setup_dialog.settings.printer)
    assert entry.is_resin
    assert entry.build_volume == pytest.approx((143, 90, 175))
    assert entry.pixel_size == pytest.approx(0.035)
    assert entry.minimum_wall == pytest.approx(0.5)
    assert entry.nozzle_diameter == 0.0 and entry.extrusion_width == 0.0
    assert setup_dialog.settings.material == profiles.DEFAULT_RESIN_MATERIAL
    # Wer den Drucker ausgesucht hat, bekommt sein Verfahren im Bestand wieder.
    profiles.reload()
    assert profiles.printer(entry.id).is_resin


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


def test_a_model_opened_from_the_first_steps_is_not_replaced_by_the_empty_project(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Eigenes Modell öffnen …" endet mit dem Modell im Fenster (§2.3).

    Der Knopf meldete den Import, **während der Dialog noch offen war**: Das
    Fenster las die Datei an, der Dialog schloss, und danach legte
    ``_adopt_defaults`` das leere Projekt mit den eben gewählten Vorgaben an
    — weil das Dokument noch keinen Schritt trug. Bei einer Datei über der
    Grenze, ab der der Plan im Arbeiter entsteht (8 MB), kam dessen Antwort
    danach und war veraltet: Das erste Modell des Kunden verschwand ohne
    Wort. Die Grenze ist hier heruntergesetzt; der Weg ist derselbe.
    """
    import time

    from app.ui import main_window, session
    from app.ui.session import Session

    model = Path(__file__).parent / "data" / "meshes" / "cube_clean.stl"
    monkeypatch.setattr(session, "PLAN_IN_WORKER_ABOVE", 0)
    # Eine große Datei plant Sekunden; die kleine hier braucht dafür einen
    # Aufschub im Arbeiter, sonst kommt ihr Plan noch vor dem Schließen an.
    plan = session.import_plan

    def slow_plan(*args: object, **kwargs: object) -> object:
        time.sleep(0.5)
        return plan(*args, **kwargs)

    monkeypatch.setattr(session, "import_plan", slow_plan)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames", lambda *_args, **_kwargs: ([str(model)], "")
    )

    class OpenDialog(FirstRunDialog):
        def look(self) -> None:
            pass

        def exec(self) -> int:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, self, self.open_button.click)
            return super().exec()

    monkeypatch.setattr(first_run, "FirstRunDialog", OpenDialog)
    monkeypatch.setattr(main_window, "save_settings", lambda _settings: None)
    monkeypatch.setattr(Session, "set_agent_backend", lambda *_args: None)
    window = main_window.MainWindow(Session(), UiSettings())
    monkeypatch.setattr(window, "_refresh_chat_availability", lambda *_args, **_kwargs: None)
    try:
        window.action_first_run()
        deadline = time.monotonic() + 10
        while not window.session.project.document.ops and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)

        assert window.settings.first_run_done
        kinds = [op.op for op in window.session.project.document.ops]
        assert kinds == ["load"], kinds
        assert window.session.project.document.printer == window.settings.printer
    finally:
        window.wait_for_workers()
        window.close()


def _assert_box_grouped_by_technology(box: object) -> None:
    """Eine Druckerliste liest sich überall gleich: je Verfahren ein Kopf, der
    nicht wählbar ist und sich nicht nur über seine graue Farbe abhebt,
    darunter die Drucker dieses Verfahrens nach Titel."""
    from PySide6.QtWidgets import QComboBox

    assert isinstance(box, QComboBox)
    known = profiles.printer_profiles()
    heads: list[str] = []
    members: dict[str, list[str]] = {}
    for row in range(box.count()):
        data = str(box.itemData(row) or "")
        if data == first_run._GROUP_HEADER:
            heads.append(box.itemText(row))
            members[heads[-1]] = []
            item = box.model().item(row)
            assert not item.flags() & Qt.ItemFlag.ItemIsEnabled, box.itemText(row)
            assert item.font().bold(), f"Kopf nur über die Farbe erkennbar: {box.itemText(row)}"
            continue
        if data not in known:
            continue
        assert heads, f"{box.itemText(row)} steht vor dem ersten Kopf"
        assert heads[-1] == first_run._group_title(known[data].technology), box.itemText(row)
        members[heads[-1]].append(box.itemText(row))
    assert heads == [first_run._group_title("fdm"), first_run._group_title("resin")]
    for head, titles in members.items():
        assert titles == sorted(titles, key=str.casefold), (head, titles)


def test_every_printer_list_is_grouped_like_the_first_steps(qt_app: QApplication) -> None:
    """Dieselbe Druckerliste an drei Stellen, und nur eine war gruppiert.

    Der Erststart trägt seit RM-071 je Verfahren einen Kopf; die Einstellungen
    und die Druckvorbereitung listeten dieselben Drucker weiter flach nach
    Titel — der Resin-Drucker stand dort zwischen den FDM-Geräten, als wäre
    er einer von ihnen. Und der Kopf hob sich nur über seine graue Farbe ab,
    die jedes gesperrte Element trägt (Regel 18).
    """
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings_dialog import SettingsDialog

    first_steps = FirstRunDialog(UiSettings())
    settings = SettingsDialog(UiSettings())
    session = Session()
    printing = PrintSettingsDialog(session, UiSettings())
    try:
        for box in (first_steps.printer, settings.printer, printing.printer_choice):
            _assert_box_grouped_by_technology(box)
        # Der gewählte Drucker bleibt gewählt, der Kopf wird es nie.
        assert settings.printer.currentData() == profiles.DEFAULT_PRINTER
        assert printing.printer_choice.currentData() == session.project.document.printer
    finally:
        first_steps.release()
        printing.release()


@pytest.mark.parametrize("technology", ["fdm", "resin"])
def test_a_custom_printer_takes_its_layer_height_or_names_the_derived_one(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, technology: str
) -> None:
    """„Gebraucht werden Bauraum und Schichthöhe", sagt die Website — und das
    Formular des eigenen Druckers hatte kein Feld dafür.

    Leer bleibt der abgeleitete Wert (FDM: aus der Düse, höchstens die
    Vorlage; Resin: die Vorlage), und das Feld nennt ihn, statt leer zu
    schweigen. Eingetragen gilt der eigene, gespeichert im Profil.
    """
    monkeypatch.setattr(profiles, "user_profiles_dir", lambda: tmp_path)
    dialog = setup_dialog
    dialog.printer.setCurrentIndex(dialog.printer.findData("__custom__"))
    dialog.printer_technology.setCurrentIndex(dialog.printer_technology.findData(technology))
    assert dialog.printer_layer.isVisibleTo(dialog.custom_printer)
    if technology == "fdm":
        dialog.printer_nozzle.setValue(0.3)
        derived = 0.15
    else:
        derived = profiles.printer(profiles.DEFAULT_RESIN_PRINTER).layer_height
    shown = dialog.printer_layer.specialValueText()
    assert dialog.printer_layer.value() == dialog.printer_layer.minimum(), "leer heißt abgeleitet"
    assert f"{derived:g}".replace(".", ",") in shown, shown

    dialog.printer_name.setText("Leer")
    dialog.apply_to(dialog.settings)
    assert profiles.printer(dialog.settings.printer).layer_height == pytest.approx(derived)

    other = FirstRunDialog(UiSettings())
    try:
        other.printer.setCurrentIndex(other.printer.findData("__custom__"))
        other.printer_technology.setCurrentIndex(other.printer_technology.findData(technology))
        own = 0.28 if technology == "fdm" else 0.03
        other.printer_layer.setValue(own)
        other.printer_name.setText("Eigen")
        draft = other.custom_printer_draft()
        assert draft is not None and draft.layer_height == pytest.approx(own)
        other.apply_to(other.settings)
        assert profiles.printer(other.settings.printer).layer_height == pytest.approx(own)
    finally:
        other.release()


# --- Die Druckervorwahl gilt für Erststart und Einstellungen gleich ---------------


def test_the_printer_list_keeps_the_standard_and_every_resin_printer() -> None:
    """Ein FDM-Slicer filtert nur die FDM-Drucker; Standard und Resin bleiben wählbar."""
    known = {
        "fdm-a": replace(profiles.printer_profiles()[profiles.DEFAULT_PRINTER], id="fdm-a"),
        "resin-a": replace(
            profiles.printer_profiles()[profiles.DEFAULT_PRINTER], id="resin-a", technology="resin"
        ),
    }

    assert first_run.allowed_printers(("fdm-b",), known) == {
        "fdm-b",
        profiles.DEFAULT_PRINTER,
        "resin-a",
    }


def test_a_suggestion_outside_the_list_never_replaces_a_fitting_printer() -> None:
    """Stand die Wahl auf dem letzten Vorschlag und nennt der Slicer einen, den es
    in der Liste nicht gibt, bleibt der passende Drucker — nicht der Standard."""
    allowed = {"elegoo", profiles.DEFAULT_PRINTER}

    chosen, remembered = first_run.preferred_printer("elegoo", "unknown", "elegoo", allowed)

    assert chosen == "elegoo"
    assert remembered == "elegoo"


def test_a_choice_on_the_suggestion_follows_the_next_suggestion() -> None:
    """Wer die Vorwahl stehen ließ, bekommt beim nächsten Slicer dessen Vorschlag —
    auch wenn die Wahl schon vorher auf dem Vorschlag stand."""
    allowed = {"elegoo", "bambu", profiles.DEFAULT_PRINTER}

    first, remembered = first_run.preferred_printer("elegoo", "elegoo", "", allowed)
    second, _ = first_run.preferred_printer(first, "bambu", remembered, allowed)

    assert first == "elegoo"
    assert remembered == "elegoo", "die Wahl steht auf dem Vorschlag, also gilt er als gemerkt"
    assert second == "bambu"


def test_a_deliberate_choice_survives_a_new_suggestion() -> None:
    allowed = {"elegoo", "bambu", profiles.DEFAULT_PRINTER}

    chosen, remembered = first_run.preferred_printer("elegoo", "bambu", "prusa", allowed)

    assert (chosen, remembered) == ("elegoo", "prusa")


def test_a_choice_that_left_the_list_takes_the_suggestion_or_the_standard() -> None:
    allowed = {"bambu", profiles.DEFAULT_PRINTER}

    assert first_run.preferred_printer("gone", "bambu", "", allowed) == ("bambu", "bambu")
    assert first_run.preferred_printer("gone", "", "", allowed) == (profiles.DEFAULT_PRINTER, "")
    assert first_run.preferred_printer("__custom__", "bambu", "", allowed, keep={"__custom__"}) == (
        "__custom__",
        "",
    )
