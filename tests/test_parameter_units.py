"""Ein Längenparameter spricht in der Anzeigeeinheit, gespeichert wird in mm (FD-125).

Bei Zollanzeige bot *Parameter anlegen* nur „mm — Länge“, und der Wert stand in
Millimetern, während Kopf und Baum Zoll zeigten — wer in Zoll arbeitet, rechnete
für einen Parameter um. Der Kern rechnet weiter in Millimetern (harte Regel 6);
umgerechnet wird nur an der Grenze der Oberfläche, in beide Richtungen.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QApplication

from app.core.scene.project import new_project
from app.core.types import Feature, Parameter
from app.ui.labels import set_display_unit


@pytest.fixture
def in_inches() -> Iterator[None]:
    """Zoll für einen Test — ``tests/conftest.py`` stellt danach zurück."""
    set_display_unit("in")
    yield


def test_the_number_helpers_keep_millimetres_inside(in_inches: None) -> None:
    """Hinaus in Zoll, herein in mm; Winkel und Anzahlen bleiben, wie sie sind."""
    from app.ui.parameter_dialog import number_places, shown_number, stored_number

    assert shown_number(25.4, "mm") == pytest.approx(1.0)
    assert stored_number(2.0, "mm") == pytest.approx(50.8)
    assert shown_number(45.0, "°") == 45.0, "ein Winkel bleibt, wie er ist"
    assert stored_number(3.0, "") == 3.0, "eine Anzahl auch"
    assert number_places("mm", 2) == 4, "Zoll braucht vier Stellen"
    assert number_places("°", 2) == 2


def test_a_length_parameter_is_typed_in_inches_and_stored_in_millimetres(
    qt_app: QApplication, in_inches: None
) -> None:
    from app.ui.parameter_dialog import ParameterDialog

    dialog = ParameterDialog({})
    try:
        assert dialog.unit_field.currentData() == "mm", "der Code im Dokument bleibt mm"
        assert dialog.unit_field.currentText() == "in — Länge", "gezeigt wird Zoll"
        dialog.name_field.setText("breite")
        dialog.value_field.setValue(2.0)
        dialog.minimum_field.setText("1")
        dialog.maximum_field.setText("3,5")
        assert dialog.validation_problem() is None
        made = dialog.parameter()
        assert made.unit == "mm"
        assert made.value == pytest.approx(50.8)
        assert made.minimum == pytest.approx(25.4)
        assert made.maximum == pytest.approx(88.9)

        dialog.maximum_field.setText("1,5")
        assert dialog.validation_problem() is not None, "die Grenze gilt in derselben Einheit"
    finally:
        dialog.deleteLater()


def test_an_existing_length_opens_in_inches_and_comes_back_unchanged(
    qt_app: QApplication, in_inches: None
) -> None:
    from app.ui.parameter_dialog import ParameterDialog

    existing = Parameter(name="breite", value=40.0, unit="mm", minimum=25.4, maximum=101.6)
    dialog = ParameterDialog({"breite": existing}, existing=existing)
    try:
        assert dialog.value_field.value() == pytest.approx(1.5748)
        assert dialog.minimum_field.text() == "1"
        assert dialog.maximum_field.text() == "4"
        made = dialog.parameter()
        assert made.value == 40.0, "ohne Änderung kein Rundungsfehler"
        assert made.minimum == 25.4 and made.maximum == 101.6

        dialog.value_field.setValue(2.0)
        assert dialog.parameter().value == pytest.approx(50.8)
    finally:
        dialog.deleteLater()


def test_an_angle_stays_in_degrees_while_lengths_show_inches(
    qt_app: QApplication, in_inches: None
) -> None:
    from app.core.units import DEGREE_UNIT
    from app.ui.parameter_dialog import ParameterDialog

    existing = Parameter(name="winkel", value=45.0, unit=DEGREE_UNIT)
    dialog = ParameterDialog({"winkel": existing}, existing=existing)
    try:
        assert dialog.value_field.value() == pytest.approx(45.0)
        assert dialog.parameter().value == 45.0
    finally:
        dialog.deleteLater()


def test_the_part_dialog_shows_a_length_in_inches_and_stores_millimetres(
    qt_app: QApplication, in_inches: None
) -> None:
    """Derselbe Fund im Bausteindialog (``recipe_dialog``, Grenzen und Vorgabe)."""
    from app.ui.recipe_dialog import RecipeDialog

    document = replace(
        new_project().document,
        parameters={"breite": Parameter(name="breite", value=40.0, unit="mm", title="Breite")},
    )
    feature = Feature(id="hole_1", kind="hole", provenance="detected", params={"diameter": 5.2})
    dialog = RecipeDialog(document, {}, (1,), (feature,), None)  # type: ignore[arg-type]
    try:
        row = dialog._params[0]
        assert row.unit.currentText() == "in — Länge"
        assert row.default.value() == pytest.approx(1.5748)
        exposed = row.exposed()
        assert exposed.default == 40.0, "unberührt kommt der gespeicherte Wert zurück"
        assert exposed.unit == "mm"

        row.default.setValue(2.0)
        assert row.exposed().default == pytest.approx(50.8)
    finally:
        dialog.release()
        dialog.deleteLater()
