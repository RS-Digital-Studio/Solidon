"""Slicer, passende Drucker und eigene Maße in den ersten Schritten."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog

from app.core import discover
from app.core.knowledge import profiles
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
        # Die Resin-Geräte hängen an keinem FDM-Slicer und bleiben stehen.
        assert setup_dialog.printer.findData("generic-resin-130") >= 0
        _assert_grouped_and_sorted(setup_dialog)


def test_failed_slicer_worker_keeps_saved_custom_printers_and_current_choice(
    setup_dialog: FirstRunDialog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein unbekannter Slicer verbirgt weder eigene Drucker noch deren aktuelle Auswahl.

    Seit dem 22.09.2026 ist ein unbekanntes Programm kein Fehler mehr, sondern
    die Familie ``other`` (RM-071): Die Erhebung läuft durch und nennt keine
    Drucker, und der Satz darunter sagt, warum.
    """
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
    assert "kennt Solidon nicht" in setup_dialog.printer_state.text()


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
    _assert_grouped_and_sorted(setup_dialog)


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
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args, **_kwargs: (str(model), ""))

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
