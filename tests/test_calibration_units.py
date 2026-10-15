"""*Material kalibrieren* spricht in der Anzeigeeinheit, gespeichert wird in mm (FD-176).

Die Längenfelder trugen ein festes „ mm“ und folgten der Zollanzeige nicht
(§19.3), anders als jedes andere Längenfeld. Ein gewöhnliches Längenfeld hätte
dabei die dritte Stelle der Feinmaße verloren (0,075 mm); deshalb eine Stelle
mehr (``app.ui.fine_length_spin``). Ein unberührtes Feld gibt den
gespeicherten Wert zurück, ohne Rundungsrest der Umrechnung.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from app.core.knowledge import profiles
from app.core.units import from_mm
from app.ui.labels import LengthSpin, set_display_unit

#: Die Längen des Dialogs, vorn und hinten.
LENGTHS = ("clearance", "press", "hole_compensation", "elephant_foot", "minimum_wall")


@pytest.fixture
def in_inches(qt_app: QApplication) -> Iterator[None]:
    set_display_unit("in")
    try:
        yield
    finally:
        set_display_unit("mm")


def _dialog() -> object:
    from app.ui.calibration_dialog import CalibrationDialog

    process = profiles.make_profile("centauri-carbon-2", "petg")
    return CalibrationDialog("petg", process=process)


def test_every_length_speaks_inches(in_inches: None) -> None:
    dialog = _dialog()
    try:
        current = profiles.material("petg")
        for name in LENGTHS:
            editor = dialog.editors[name]  # type: ignore[attr-defined]
            assert isinstance(editor, LengthSpin), name
            assert editor.suffix() == " in", f"{name}: {editor.suffix()!r}"
        clearance = dialog.editors["clearance"]  # type: ignore[attr-defined]
        assert clearance.decimals() == 5, "ein Hundertstelmillimeter ist eine fünfte Zollstelle"
        assert clearance.value() == pytest.approx(from_mm(current.clearance, "in"), abs=1e-5)
    finally:
        dialog.deleteLater()  # type: ignore[attr-defined]


def test_a_typed_inch_is_stored_in_millimetres(in_inches: None) -> None:
    dialog = _dialog()
    try:
        editor = dialog.editors["clearance"]  # type: ignore[attr-defined]
        editor.lineEdit().selectAll()
        editor.lineEdit().insert("0,01")
        editor.interpretText()
        measured = dialog.measured()  # type: ignore[attr-defined]
        assert measured.value("clearance") == pytest.approx(0.254, abs=1e-4)
    finally:
        dialog.deleteLater()  # type: ignore[attr-defined]


def test_an_untouched_fine_value_comes_back_exactly(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """0,075 mm steht in Millimetern mit seiner dritten Stelle im Feld und kommt
    unberührt unverändert zurück, auch über Zoll."""
    from app.ui.calibration_dialog import CalibrationDialog

    original = profiles.material
    monkeypatch.setattr(
        profiles, "material", lambda key: dataclasses.replace(original(key), clearance=0.075)
    )
    for unit in ("mm", "in"):
        set_display_unit(unit)
        try:
            dialog = CalibrationDialog("petg")
            editor = dialog.editors["clearance"]
            assert isinstance(editor, LengthSpin)
            if unit == "mm":
                assert editor.text().startswith("0,075"), editor.text()
            assert editor.value_mm() == pytest.approx(0.075, abs=1e-12), unit
            editor.lineEdit().selectAll()
            editor.lineEdit().insert("0,075" if unit == "mm" else "0,004")
            editor.interpretText()
            wanted = 0.075 if unit == "mm" else 0.004 * 25.4
            assert dialog.measured().value("clearance") == pytest.approx(wanted, abs=1e-9), unit
            dialog.deleteLater()
        finally:
            set_display_unit("mm")
