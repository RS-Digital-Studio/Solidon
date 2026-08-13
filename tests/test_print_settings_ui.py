"""Der Druckeinstellungsdialog (Bauplan §29, §2.4).

Offscreen wie alle Oberflächentests. Geprüft wird, was der Dialog verspricht:
jede Einstellung des Modells hat ein Feld, die Felder schreiben zurück, die
Vorschläge kommen mit Begründung, und ohne Slicer bleibt er benutzbar.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
)

from app.core.export import handover
from app.core.export.slicer_profiles import SlicerProfile
from app.core.knowledge import print_settings, profiles
from app.core.slice import gcode
from app.ui.print_settings_dialog import FIELDS, GROUPS, PrintSettingsDialog, _ColourButton
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    return Session()


@pytest.fixture
def dialog(qt_app: QApplication, session: Session) -> PrintSettingsDialog:
    return PrintSettingsDialog(session, UiSettings())


# --- Vollständigkeit ----------------------------------------------------------------


def test_every_setting_in_the_model_has_a_field() -> None:
    """Eine Einstellung ohne Feld wäre eine, die der Nutzer nie zu sehen
    bekommt — und die er trotzdem an den Slicer schickt."""
    settings = print_settings.resolve(profiles.make_profile())
    covered = {field.path for field in FIELDS}

    for group in (
        "layers",
        "shell",
        "infill",
        "temperature",
        "cooling",
        "speed",
        "support",
        "adhesion",
        "retraction",
        "filament",
    ):
        section = getattr(settings, group)
        for name in section.__slots__:
            assert f"{group}.{name}" in covered, f"{group}.{name} hat kein Feld im Dialog"


def test_every_field_points_at_a_real_setting(dialog: PrintSettingsDialog) -> None:
    for field in FIELDS:
        print_settings.read_path(dialog.settings, field.path)


def test_every_field_lands_in_a_known_group() -> None:
    for field in FIELDS:
        assert field.group in GROUPS


def test_the_front_page_stays_short() -> None:
    """§2.4: vorn die zwei bis drei Werte, die man ändert. Wird das eine
    zweite vollständige Liste, ist die gestufte Tiefe verloren."""
    front = [field for field in FIELDS if field.front]
    assert 3 <= len(front) <= 10


# --- Werte hin und zurück -----------------------------------------------------------


def test_the_editors_start_on_the_resolved_values(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["layers.layer_height"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.layers.layer_height)


def test_a_speed_survives_being_shown(dialog: PrintSettingsDialog) -> None:
    """Ein Feld, das einen Wert nur anzeigt, darf ihn nicht verändern.

    Die Bahngeschwindigkeiten standen auf null Nachkommastellen. Das ist keine
    Frage der Anzeige: der Wert, den ``advise`` aus dem Volumenstrom errechnet,
    ist selten glatt — bei 5 mm³/s, 0,2 mm Schicht und 0,42 mm Bahn sind es
    59,52 mm/s. Gerundet auf 60 fördert die Düse 5,04 mm³/s, und damit stand
    allein durch das Öffnen des Fensters mehr in der Datei, als das Material
    verträgt.
    """
    genau = 59.52380952380952
    dialog.settings = replace(
        dialog.settings, speed=replace(dialog.settings.speed, outer_wall=genau)
    )
    dialog._load_into_editors()

    zurueck = dialog._collect().speed.outer_wall

    fluss = dialog.settings.layers.layer_height * dialog.settings.layers.line_width
    assert zurueck * fluss <= dialog.settings.filament.max_flow + 1e-9, (
        "der angezeigte Wert darf den Volumenstrom des Materials nicht überschreiten"
    )
    assert zurueck == pytest.approx(genau, abs=0.05), "und er bleibt bei dem, was er war"


def test_choosing_a_filament_adopts_its_values(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Wer eine Spule wählt, bekommt ihre Werte — auch den Volumenstrom.

    Solidon kennt „PETG" und bringt 10 mm³/s mit; Elegoo PETG PRO fährt 5.
    Ohne diese Übernahme rechnet die Beratung gegen eine Grenze, die das
    eingelegte Material nicht hat.
    """
    datei = tmp_path / "Spule.json"
    datei.write_text(
        json.dumps(
            {
                "name": "Spule",
                "nozzle_temperature": ["255"],
                "hot_plate_temp": ["75"],
                "filament_max_volumetric_speed": ["5"],
            }
        ),
        encoding="utf-8",
    )
    dialog.filament_choice.addItem("Spule", str(datei))
    dialog.filament_choice.setCurrentIndex(dialog.filament_choice.count() - 1)

    dialog._filament_chosen(dialog.filament_choice.currentIndex())

    assert dialog.settings.filament.max_flow == 5.0
    assert dialog.settings.temperature.nozzle == 255
    assert dialog.settings.temperature.bed == 75


def test_filling_the_filament_list_changes_nothing(dialog: PrintSettingsDialog) -> None:
    """Was ein Projekt mitbringt, gilt.

    Die Liste wird beim Öffnen befüllt und dabei eine Vorauswahl gesetzt. Käme
    daraus eine Übernahme, überschriebe allein das Aufgehen des Fensters die
    Einstellungen des Projekts — eine Dichtung aus TPU wäre danach keine mehr.
    Deshalb hängt die Übernahme an ``activated`` (der Wahl eines Menschen) und
    nicht an ``currentIndexChanged``.
    """
    vorher = dialog.settings

    dialog._fill_filaments(None)

    assert dialog.settings is vorher, "das Befüllen der Liste ändert keine Einstellung"


def test_changing_a_field_reaches_the_settings(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["shell.wall_count"]
    assert isinstance(editor, QSpinBox)

    editor.setValue(7)

    assert dialog.settings.shell.wall_count == 7


def test_changing_the_quality_reloads_every_field(dialog: PrintSettingsDialog) -> None:
    before = dialog.settings.layers.layer_height
    index = dialog.quality.findData("fine")
    assert index >= 0

    dialog.quality.setCurrentIndex(index)

    assert dialog.settings.quality == "fine"
    assert dialog.settings.layers.layer_height != before
    editor = dialog._editors["layers.layer_height"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.layers.layer_height)


def test_the_colour_button_says_which_colour_it_is() -> None:
    """Regel 18: die Farbe allein trägt die Bedeutung nicht.

    Getragen hat sie bisher der Hexwert — richtig als zweite Kodierung und
    trotzdem schwach: „#4A90D9" beschreibt für niemanden eine Spule im Regal.
    Der Name tut beides, und die Zahl steht im Tooltip, wo sie hingehört.
    """
    button = _ColourButton("#3FAE6B")
    assert button.text() == "Grün"
    assert "3FAE6B" in button.toolTip().upper(), "genau bleibt genau"

    button.set_value("#112233")
    assert button.text() == "Schwarz"
    assert "112233" in button.toolTip().upper()


def test_a_checkbox_writes_through(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["shell.outer_wall_first"]
    assert isinstance(editor, QCheckBox)

    editor.setChecked(True)

    assert dialog.settings.shell.outer_wall_first is True


def test_an_enum_writes_through(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors["support.style"]
    assert isinstance(editor, QComboBox)

    editor.setCurrentIndex(editor.findData("tree"))

    assert dialog.settings.support.style == "tree"


def test_an_enum_shows_words_and_stores_the_english_value(dialog: PrintSettingsDialog) -> None:
    """§4.1: der gespeicherte Wert geht in die Projektdatei und zum Slicer und
    bleibt englisch; gezeigt wird die Übersetzung."""
    editor = dialog._editors["infill.pattern"]
    assert isinstance(editor, QComboBox)

    index = editor.findData("gyroid")
    assert index >= 0
    editor.setCurrentIndex(index)

    assert dialog.settings.infill.pattern == "gyroid"
    assert editor.itemData(editor.findData("grid")) == "grid"
    assert editor.itemText(editor.findData("grid")) != "grid", "Gitter, nicht grid"


def test_a_share_is_shown_in_percent_and_stored_as_a_fraction(
    dialog: PrintSettingsDialog,
) -> None:
    """Ein Feld mit [%] und einer 0,15 darin ist falsch beschriftet — der Kern
    rechnet in Anteilen, die Werkstatt spricht in Prozent."""
    editor = dialog._editors["infill.density"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.infill.density * 100.0)

    editor.setValue(35.0)

    assert dialog.settings.infill.density == pytest.approx(0.35)


def test_the_close_button_speaks_german(dialog: PrintSettingsDialog) -> None:
    """Regel 20: Qt beschriftet seine Standardknöpfe selbst — auch der Text
    muss durch tr() gehen."""
    from PySide6.QtWidgets import QDialogButtonBox

    boxes = dialog.findChildren(QDialogButtonBox)
    close = next(
        button
        for box in boxes
        if (button := box.button(QDialogButtonBox.StandardButton.Close)) is not None
    )
    assert close.text() == "Schließen"


# --- Vorschläge ---------------------------------------------------------------------


def test_the_advice_list_names_a_reason(qt_app: QApplication) -> None:
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog.advice_view.topLevelItemCount() > 0
    first = dialog.advice_view.topLevelItem(0)
    assert first is not None
    assert first.text(2), "die dritte Spalte ist der Grund, und sie darf nicht leer sein"


def test_applying_the_advice_moves_the_editors(qt_app: QApplication) -> None:
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    before = dialog.settings.speed.outer_wall

    dialog._apply_advice()

    assert dialog.settings.speed.outer_wall < before
    editor = dialog._editors["speed.outer_wall"]
    assert isinstance(editor, QDoubleSpinBox)
    assert editor.value() == pytest.approx(dialog.settings.speed.outer_wall)


def test_the_advice_list_is_never_empty_of_words(dialog: PrintSettingsDialog) -> None:
    """Auch wenn nichts einzuwenden ist, steht das da — eine leere Liste sähe
    aus wie ein Fehler."""
    dialog._refresh_advice()

    assert dialog.advice_view.topLevelItemCount() >= 1
    first = dialog.advice_view.topLevelItem(0)
    assert first is not None and first.text(0)


# --- ohne Slicer --------------------------------------------------------------------


def test_the_dialog_opens_without_a_slicer(
    monkeypatch: pytest.MonkeyPatch, session: Session
) -> None:
    """§27: das Backend meldet sich ab, es nörgelt nicht — die Einstellungen
    bleiben trotzdem pflegbar."""
    monkeypatch.setattr("app.core.discover.find_program", lambda *args, **kwargs: None)

    dialog = PrintSettingsDialog(session, UiSettings())

    assert not dialog.slice_button.isEnabled()
    assert dialog.state.text()
    assert dialog._editors["layers.layer_height"].isEnabled()


def test_slicing_without_a_scene_says_what_is_missing(dialog: PrintSettingsDialog) -> None:
    dialog._slice()
    assert dialog.state.text()


def test_both_orca_profiles_are_asked_for_before_the_run(qt_app: QApplication) -> None:
    """Die Orca-Familie braucht zwei Profile, geprüft wurde nur eines.

    Ohne Prozessprofil hat Solidons Datei kein Systemprofil, auf das sie sich
    legen kann (siehe `handover._orca_process`), und der Slicer bricht ab,
    bevor er das Modell ansieht. Gemessen gegen ElegooSlicer 1.5.3.4: mit dem
    Systemprofil darunter läuft derselbe Aufruf durch, ohne es endet er in
    „Der Slicer hat keine Druckdatei geschrieben" — ein Satz über das Ende,
    nicht über die Ursache.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parent.parent / "app" / "ui" / "print_settings_dialog.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    guarded: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        condition = ast.unparse(node.test)
        if "setup.flavour" not in condition:
            continue
        for field in ("machine_profile", "base_process"):
            if f"setup.{field}" in condition:
                guarded.add(field)

    assert guarded == {"machine_profile", "base_process"}, (
        f"nur diese Profile werden vor dem Lauf verlangt: {sorted(guarded)}"
    )


# --- was bleibt, wenn der Dialog zugeht ---------------------------------------------


def test_the_project_settings_win_over_the_preset(qt_app: QApplication) -> None:
    """§29: was eingestellt wurde, gilt beim nächsten Öffnen weiter — sonst
    wäre der Dialog eine Sitzung lang gültig und danach vergessen."""
    session = Session()
    stored = print_settings.with_path(
        print_settings.resolve(session.profile), "shell.wall_count", 9
    )
    session.project.document.print_settings = stored

    dialog = PrintSettingsDialog(session, UiSettings())

    assert dialog.settings.shell.wall_count == 9


def test_a_project_without_settings_falls_back_to_the_preset(dialog: PrintSettingsDialog) -> None:
    """Kein eigener Satz heißt „noch nichts entschieden", nicht „alles null"."""
    assert dialog.settings.shell.wall_count > 0


def test_the_session_takes_the_settings_and_marks_the_project(qt_app: QApplication) -> None:
    session = Session()
    changed = print_settings.with_path(
        print_settings.resolve(session.profile), "infill.density", 0.42
    )

    session.set_print_settings(changed)

    assert session.project.document.print_settings == changed
    assert session.modified


def test_setting_the_same_values_changes_nothing(qt_app: QApplication) -> None:
    """Den Dialog zu öffnen und ohne Änderung zu schließen darf ein Projekt
    nicht als geändert markieren."""
    session = Session()
    same = print_settings.resolve(session.profile)
    session.set_print_settings(same)
    session._dirty = False

    session.set_print_settings(same)

    assert not session.modified


# --- Vorschläge einzeln wählen ------------------------------------------------------


def test_advice_can_be_taken_one_at_a_time(qt_app: QApplication) -> None:
    """Alles oder nichts hieße: wer einen Vorschlag nicht will, gibt die
    übrigen mit auf."""
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.advice_view.topLevelItemCount() >= 2

    first = dialog.advice_view.topLevelItem(0)
    assert first is not None
    first.setCheckState(0, Qt.CheckState.Unchecked)
    skipped = str(first.data(0, Qt.ItemDataRole.UserRole))
    before = print_settings.read_path(dialog.settings, skipped)

    dialog._apply_advice()

    assert print_settings.read_path(dialog.settings, skipped) == before


def test_every_advice_starts_checked(qt_app: QApplication) -> None:
    """Die Vorschläge sind begründet — sie vorbelegt zu lassen ist die gute
    Vorgabe, nicht die bequeme."""
    session = Session()
    session.project.document.material = "tpu-95a"
    dialog = PrintSettingsDialog(session, UiSettings())

    for index in range(dialog.advice_view.topLevelItemCount()):
        item = dialog.advice_view.topLevelItem(index)
        assert item is not None and item.checkState(0) == Qt.CheckState.Checked


# --- die Druckdatei -----------------------------------------------------------------


def test_the_save_button_stays_off_until_something_was_sliced(
    dialog: PrintSettingsDialog,
) -> None:
    """Ein Knopf, der eine Datei speichern soll, die es nicht gibt, ist eine
    Sackgasse."""
    assert not dialog.save_button.isEnabled()


def test_slicing_makes_the_file_available(dialog: PrintSettingsDialog, tmp_path: Path) -> None:
    """Ohne diesen Schritt wäre der ganze Lauf eine Zahl auf dem Bildschirm
    und nichts, was auf einen Drucker geht."""
    produced = tmp_path / "plate_1.gcode"
    produced.write_text("; nur ein Test\n", encoding="utf-8")
    outcome = handover.SliceOutcome(gcode_path=produced, metrics=gcode.GcodeMetrics())

    dialog._sliced(outcome)

    assert dialog.save_button.isEnabled()
    assert dialog._gcode == produced


# --- Profilauswahl (§29) ------------------------------------------------------------


def _profile(name: str, kind: str, **kwargs: object) -> SlicerProfile:
    return SlicerProfile(path=Path(f"/x/{name}.json"), name=name, kind=kind, **kwargs)  # type: ignore[arg-type]


def test_the_found_profiles_fill_both_choices(dialog: PrintSettingsDialog) -> None:
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    found = [
        machine,
        _profile("0.20mm Standard", "process", compatible_printers=(machine.name,)),
        _profile("0.12mm Fein", "process", inherits="0.20mm Standard"),
    ]

    dialog._profiles_found(found)

    assert dialog.machine_choice.count() == 1
    assert dialog.machine_choice.isEnabled()
    assert dialog.process_choice.count() == 2


def test_the_matching_profile_is_preselected(qt_app: QApplication) -> None:
    """§2.4: eine gute Vorgabe ist mehr wert als eine gute
    Einstellmöglichkeit. Das Maschinenprofil nennt seinen Drucker und sein
    Standard-Prozessprofil selbst — es gibt nichts zu erfragen."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    dialog = PrintSettingsDialog(session, UiSettings())
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
        default_process="0.20mm Standard",
    )
    other = _profile(
        "Ganz anderes Gerät", "machine", printer_model="Ganz anderes Gerät", nozzle=0.4
    )

    dialog._profiles_found(
        [
            other,
            machine,
            _profile("0.12mm Fein", "process", compatible_printers=(machine.name,)),
            _profile("0.20mm Standard", "process", compatible_printers=(machine.name,)),
        ]
    )

    assert dialog.machine_choice.currentData() == str(machine.path)
    assert dialog.process_choice.currentText().startswith("0.20mm Standard")


def test_processes_of_other_printers_stay_out(dialog: PrintSettingsDialog) -> None:
    """Ungefiltert stünden hier zweitausend Einträge, von denen einer stimmt —
    und der Slicer lehnte jeden anderen ab, ohne zu sagen warum."""
    machine = _profile("Meiner 0.4 nozzle", "machine", printer_model="Meiner", nozzle=0.4)
    dialog._profiles_found(
        [
            machine,
            _profile("Passt", "process", compatible_printers=(machine.name,)),
            _profile("Passt nicht", "process", compatible_printers=("Ein anderer",)),
        ]
    )

    shown = [
        dialog.process_choice.itemText(index) for index in range(dialog.process_choice.count())
    ]
    assert shown == ["Passt"]


def test_an_own_profile_is_marked_in_words(dialog: PrintSettingsDialog) -> None:
    machine = _profile("Meiner 0.4 nozzle", "machine", printer_model="Meiner", nozzle=0.4)
    dialog._profiles_found([machine, _profile("Meine Fassung", "process", from_user=True)])

    assert "(" in dialog.process_choice.itemText(0)


def test_no_profiles_found_says_what_that_means(dialog: PrintSettingsDialog) -> None:
    dialog._profiles_found([])

    assert dialog.profile_note.text()
    assert not dialog.machine_choice.isEnabled()


def test_a_remembered_choice_wins_over_the_match(qt_app: QApplication) -> None:
    """Wer einmal abgewichen ist, meinte es so."""
    session = Session()
    session.project.document.printer = "centauri-carbon-2"
    settings = UiSettings()
    machine = _profile(
        "Elegoo Centauri Carbon 2 0.4 nozzle",
        "machine",
        printer_model="Elegoo Centauri Carbon 2",
        nozzle=0.4,
    )
    other = _profile("Etwas anderes", "machine", printer_model="Etwas anderes", nozzle=0.4)
    settings.slicer_machine_profile = str(other.path)
    dialog = PrintSettingsDialog(session, settings)

    dialog._profiles_found([machine, other])

    assert dialog.machine_choice.currentData() == str(other.path)


def test_a_built_fit_counts_like_an_entered_one(session: Session, qt_app) -> None:
    """§29: die Regeln für Passungen greifen auch ohne Eintrag im Dokument.

    Der Deckel aus ``create_lid`` bekommt sein Spiel aus dem Materialprofil und
    trägt es nirgends ein — im gedruckten Gewürzset liefen deshalb genau die
    Regeln nicht, die es für Passungen gibt: genaue Außenwand, gebremste
    Beschleunigung, Bügeln der Gleitfläche. Der Stapel weiß es trotzdem.
    """
    from app.core.scene import History, OperationDraft
    from app.ui.print_settings_dialog import PrintSettingsDialog

    dialog = PrintSettingsDialog(session, UiSettings())
    try:
        assert not dialog._fits_in_play(), "ein leeres Projekt hat keine Passung"

        History(session.project.document).apply(
            "Grundkörper",
            [OperationDraft(op="create_cylinder", params={"diameter": 40.0, "height": 20.0})],
        )
        assert not dialog._fits_in_play(), "ein Zylinder ist noch keine"

        History(session.project.document).apply(
            "Deckel",
            [OperationDraft(op="create_lid", inputs=("obj_1",), params={"thickness": 2.4})],
        )
        assert dialog._fits_in_play(), "ein Deckel legt zwei Flächen mit Spiel aufeinander"
    finally:
        dialog.deleteLater()


# --- ein Filament je Materialslot (§20) -----------------------------------------


def _two_slots() -> list[object]:
    """Zwei Materialslots, wie ein Schild mit Schriftzug sie hat.

    Der Dialog liest sie über ``_plate_slots`` aus der Szene; hier wird genau
    diese eine Auskunft ersetzt. Ein wirklich erzeugter Schriftzug kostete in
    einem Oberflächentest mehr Zeit als der ganze Rest der Datei — und geprüft
    wird der Dialog, nicht die Beschriftungs-Op.
    """
    from app.core.types import MaterialSlot

    return [
        MaterialSlot(index=0, name="Gehäuse", colour=(0.0, 0.0, 0.0)),
        MaterialSlot(index=1, name="Schrift", colour=(1.0, 1.0, 1.0)),
    ]


def test_one_slot_shows_no_list(dialog: PrintSettingsDialog) -> None:
    """Ein einfarbiges Teil hat eine Farbe und braucht keine Liste darüber.

    Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2): die Zeile
    „Filament" ist dann die ganze Aussage.
    """
    assert dialog.slot_rows == []


def test_a_second_slot_gets_its_own_choice(
    qt_app: QApplication, session: Session, tmp_path: Path, monkeypatch
) -> None:
    """Zwei Slots, zwei Auswahlen — und die Wahl bleibt im Projekt.

    Ein Schriftzug in Weiß auf schwarzem Gehäuse sind zwei Spulen mit zwei
    Temperaturen. Ohne diese Zeilen ließe sich das drucken, aber nicht sagen,
    und die zweite Farbe liefe mit den Werten der ersten.
    """
    monkeypatch.setattr(PrintSettingsDialog, "_plate_slots", lambda _self: _two_slots())
    dialog = PrintSettingsDialog(session, UiSettings())

    assert len(dialog.slot_rows) == 2, "je Slot eine Zeile"
    assert "Gehäuse" in dialog.slot_rows[0][0].text()
    assert "Schrift" in dialog.slot_rows[1][0].text()

    box = dialog.slot_rows[1][1]
    box.addItem("Haus PLA weiß", str(tmp_path / "pla.json"))
    box.setCurrentIndex(box.count() - 1)
    dialog._slot_filament_chosen(1)

    gemerkt = dialog.settings.slot_profiles
    assert len(gemerkt) == 2, "ein Eintrag je Slot"
    assert gemerkt[1] == "Haus PLA weiß", "der Name reist mit, nicht der Pfad"


def test_the_slot_choice_survives_the_project_file(tmp_path: Path) -> None:
    """Die Zuordnung gehört ins Projekt und nicht an den Rechner.

    Sie beschreibt das Teil — welcher Slot aus welcher Spule kommt —, und ein
    Projekt, das man weitergibt, soll das mitbringen. Der **Name** reist,
    nicht der Pfad (Regel 12).
    """
    from app.core.scene.serialise import print_settings_from_data, print_settings_to_data

    settings = replace(
        print_settings.resolve(profiles.make_profile()),
        slot_profiles=("Haus PETG", "Haus PLA weiß"),
    )

    zurueck = print_settings_from_data(print_settings_to_data(settings))

    assert zurueck.slot_profiles == ("Haus PETG", "Haus PLA weiß")
