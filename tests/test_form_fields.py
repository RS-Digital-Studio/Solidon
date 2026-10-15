"""Jedes Formularfeld trägt seinen Namen und seinen Satz (FD-94, FD-11).

Ein Bildschirmleser, der ein Feld ohne Namen erreicht, liest seinen Inhalt
vor — „breite“, „40,00“ — oder nichts (``oberflaeche.md``, „Ein Feld ohne
Namen“). Geprüft werden der gemeinsame Weg (``app.ui.form_fields``) und die
Dialoge, die ihn gehen.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import Any

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)

from app.core.scene.project import new_project
from app.core.types import Feature, Parameter
from app.ui.form_fields import explain_row, name_rows, repeated_names, unnamed_inputs


def test_a_field_that_is_its_own_editor_is_named_after_its_row(qt_app: QApplication) -> None:
    """Auswahl und Haken, die selbst das Eingabefeld sind, bekamen keinen Namen —
    benannt wurden nur Felder in einem Behälter (FD-94, ``op_dialog._explain``)."""
    host = QWidget()
    form = QFormLayout(host)
    choice = QComboBox(host)
    choice.addItems(["Bohrung 1", "Bohrung 2"])
    hook = QCheckBox(host)
    form.addRow("Bohrung", choice)
    form.addRow("Als Langloch", hook)
    assert set(unnamed_inputs(host)) == {"QComboBox", "QCheckBox"}, "Vorbedingung"

    name_rows(form)

    assert choice.accessibleName() == "Bohrung"
    assert hook.accessibleName() == "Als Langloch"
    assert unnamed_inputs(host) == []
    label = form.labelForField(choice)
    assert isinstance(label, QLabel) and label.buddy() is choice, "die Beschriftung führt hin"
    host.deleteLater()


def test_a_container_names_every_field_inside_and_keeps_given_names(
    qt_app: QApplication,
) -> None:
    """Ein Behälter (Zahl mit *fx*) gibt seinen Namen an die Felder darin; ein
    gesetzter Name trägt oft mehr als die Zeile und bleibt."""
    host = QWidget()
    form = QFormLayout(host)
    row = QWidget(host)
    layout = QHBoxLayout(row)
    number = QLineEdit(row)
    fx = QToolButton(row)
    own = QLineEdit(row)
    own.setAccessibleName("Vorgabe · Breite")
    for widget in (number, fx, own):
        layout.addWidget(widget)
    form.addRow("Wert", row)

    name_rows(form)
    explain_row(form, row, "Die Zahl, mit der gerechnet wird.")

    assert number.accessibleName() == "Wert"
    assert own.accessibleName() == "Vorgabe · Breite", "ein gesetzter Name bleibt"
    assert number.accessibleDescription() == "Die Zahl, mit der gerechnet wird."
    caption = form.labelForField(row)
    assert caption is not None and caption.toolTip() == "Die Zahl, mit der gerechnet wird."
    assert unnamed_inputs(host) == []
    host.deleteLater()


def test_a_name_used_twice_is_found(qt_app: QApplication) -> None:
    """Zwei Felder mit demselben Namen sind für den Vorleser eine Frage ohne Antwort."""
    host = QWidget()
    first, second = QLineEdit(host), QLineEdit(host)
    first.setAccessibleName("Einheit")
    second.setAccessibleName("Einheit")
    assert repeated_names(host) == ["Einheit"]
    host.deleteLater()


def _feature(identifier: str) -> Feature:
    return Feature(id=identifier, kind="hole", provenance="detected", params={"diameter": 5.2})


@contextmanager
def _parameter_dialog() -> Iterator[QDialog]:
    from app.ui.parameter_dialog import ParameterDialog

    dialog = ParameterDialog({"breite": Parameter(name="breite", value=40.0, unit="mm")})
    try:
        yield dialog
    finally:
        dialog.deleteLater()


@contextmanager
def _changed_parameter_dialog() -> Iterator[QDialog]:
    from app.ui.parameter_dialog import ParameterDialog

    existing = Parameter(name="spiel", value=0.4, unit="mm", minimum=0.1, maximum=1.0)
    dialog = ParameterDialog({"spiel": existing}, existing=existing)
    try:
        yield dialog
    finally:
        dialog.deleteLater()


@contextmanager
def _calibration_dialog() -> Iterator[QDialog]:
    from app.core.knowledge import profiles
    from app.ui.calibration_dialog import CalibrationDialog

    dialog = CalibrationDialog("petg", process=profiles.make_profile("centauri-carbon-2", "petg"))
    try:
        yield dialog
    finally:
        dialog.deleteLater()


@contextmanager
def _recipe_dialog() -> Iterator[QDialog]:
    from app.ui.recipe_dialog import RecipeDialog

    document = replace(
        new_project().document,
        parameters={
            "breite": Parameter(name="breite", value=40.0, unit="mm", title="Breite"),
            "hoehe": Parameter(name="hoehe", value=10.0, unit="mm", title="Höhe"),
        },
    )
    dialog = RecipeDialog(document, {}, (1,), (_feature("hole_1"),), None)  # type: ignore[arg-type]
    try:
        yield dialog
    finally:
        dialog.release()
        dialog.deleteLater()


@contextmanager
def _key_dialog() -> Iterator[QDialog]:
    from app.ui.dialogs import KeyDialog
    from app.ui.settings import UiSettings

    dialog = KeyDialog(settings=UiSettings())
    try:
        dialog.wait_for_look(5000)
        yield dialog
    finally:
        dialog.release(5000)


DIALOGS: dict[str, Callable[[], Any]] = {
    "parameter_anlegen": _parameter_dialog,
    "parameter_aendern": _changed_parameter_dialog,
    "kalibrieren": _calibration_dialog,
    "baustein": _recipe_dialog,
    "chat_einrichten": _key_dialog,
}


@pytest.mark.parametrize("name", sorted(DIALOGS))
def test_every_field_of_the_dialog_has_its_own_name(qt_app: QApplication, name: str) -> None:
    """Der Wächter über die Formulare von Parameter-, Kalibrier-, Baustein- und
    Chatdialog: kein Eingabefeld ohne Namen, keine zwei mit demselben."""
    with DIALOGS[name]() as dialog:
        assert unnamed_inputs(dialog) == [], f"{name}: Felder ohne Namen"
        assert repeated_names(dialog) == [], f"{name}: Namen doppelt"
