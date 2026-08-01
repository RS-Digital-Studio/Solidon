"""Der Druckeinstellungsdialog (Bauplan §29, §2.4).

Offscreen wie alle Oberflächentests. Geprüft wird, was der Dialog verspricht:
jede Einstellung des Modells hat ein Feld, die Felder schreiben zurück, die
Vorschläge kommen mit Begründung, und ohne Slicer bleibt er benutzbar.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
)

from app.core.knowledge import print_settings, profiles
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


def test_the_colour_button_shows_its_value_as_text() -> None:
    """Regel 18: die Farbe allein trägt die Bedeutung nicht."""
    button = _ColourButton("#3FAE6B")
    assert "3FAE6B" in button.text().upper()

    button.set_value("#112233")
    assert "112233" in button.text().upper()


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
