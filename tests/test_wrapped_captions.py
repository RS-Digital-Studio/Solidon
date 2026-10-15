"""Eine umgebrochene Beschriftung zeigt jede ihrer Zeilen (FD-183).

``dialogs.align_to_the_front`` lässt eine Beschriftung der Rückseite in der
Spalte der Vorderseite umbrechen. Die Höhe der Zeile nahm das Formular aber
aus der Wunschgröße des Labels, und die rechnet Qt für eine breitere Zeile:
„Durchmesser der Aufweitung“ an *Bohrung setzen* brauchte drei Zeilen, bekam
zwei, und „Aufweitung“ fehlte. Geprüft wird jede Beschriftung jedes
Operationsdialogs bei der Grundschrift und bei großer Schrift, dazu die
übrigen Dialoge mit Rückseite.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QDialog, QFormLayout, QLabel, QToolButton

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.ui.style import apply_style
from app.ui.theme import apply_theme

#: Grundschrift unter Windows und die große Schrift aus den Einstellungen.
POINTS = (9, 16)


@contextmanager
def _font(qt_app: QApplication, points: int) -> Iterator[None]:
    previous = QFont(qt_app.font())
    font = QFont(previous)
    font.setPointSize(points)
    qt_app.setFont(font)
    apply_theme(qt_app, "light")
    apply_style(qt_app, "light")
    try:
        yield
    finally:
        qt_app.setFont(previous)
        apply_style(qt_app, "light")


def _settle(qt_app: QApplication) -> None:
    for _ in range(6):
        qt_app.processEvents()


def _open_every_flap(dialog: QDialog) -> None:
    for heading in dialog.findChildren(QToolButton, "sectionHeading"):
        if heading.isCheckable() and not heading.isChecked():
            heading.setChecked(True)


def _cut_captions(dialog: QDialog) -> list[str]:
    """Jede sichtbare umbrechende Beschriftung, die niedriger ist als ihr Text."""
    cut: list[str] = []
    for form in dialog.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            label = item.widget() if item is not None else None
            if not isinstance(label, QLabel) or not label.wordWrap() or not label.isVisible():
                continue
            need = label.heightForWidth(label.width())
            if label.height() < need:
                cut.append(f"„{label.text()}“ {label.height()} statt {need} Punkte")
    return cut


@pytest.mark.parametrize("points", POINTS)
def test_every_caption_of_an_operation_dialog_shows_all_its_lines(
    qt_app: QApplication, points: int
) -> None:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    found: list[str] = []
    with _font(qt_app, points):
        for spec in REGISTRY.all():
            dialog = OperationDialog(spec, {"obj_1": "Quader"}, None)
            try:
                dialog.show()
                _settle(qt_app)
                _open_every_flap(dialog)
                _settle(qt_app)
                found += [f"{spec.name}: {entry}" for entry in _cut_captions(dialog)]
            finally:
                dialog.reject()
                dialog.deleteLater()
    assert not found, f"{len(found)} Beschriftungen abgeschnitten:\n" + "\n".join(found)


@pytest.mark.parametrize("points", POINTS)
def test_the_drill_back_names_the_widening_in_full(qt_app: QApplication, points: int) -> None:
    """Der Fall aus dem Lauf: *Bohrung setzen*, „Durchmesser der Aufweitung“."""
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    with _font(qt_app, points):
        dialog = OperationDialog(REGISTRY.get("drill_hole"), {"obj_1": "Quader"}, None)
        try:
            dialog.show()
            _settle(qt_app)
            dialog.advanced.setChecked(True)
            _settle(qt_app)
            label = dialog._advanced_form.labelForField(dialog._editors["widening_diameter"])
            assert isinstance(label, QLabel)
            assert label.height() >= label.heightForWidth(label.width()), label.height()
        finally:
            dialog.reject()
            dialog.deleteLater()


def test_a_font_change_keeps_every_line(qt_app: QApplication) -> None:
    """Wird die Schrift im offenen Dialog größer, wachsen die Beschriftungen mit."""
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    with _font(qt_app, POINTS[0]):
        dialog = OperationDialog(REGISTRY.get("drill_hole"), {"obj_1": "Quader"}, None)
        try:
            dialog.show()
            _settle(qt_app)
            dialog.advanced.setChecked(True)
            _settle(qt_app)
            bigger = QFont(qt_app.font())
            bigger.setPointSize(POINTS[1])
            qt_app.setFont(bigger)
            apply_style(qt_app, "light")
            _settle(qt_app)
            assert not _cut_captions(dialog)
        finally:
            dialog.reject()
            dialog.deleteLater()


@contextmanager
def _calibration() -> Iterator[QDialog]:
    from app.core.knowledge import profiles
    from app.ui.calibration_dialog import CalibrationDialog

    dialog = CalibrationDialog("petg", process=profiles.make_profile("centauri-carbon-2", "petg"))
    try:
        yield dialog
    finally:
        dialog.deleteLater()


@contextmanager
def _parameter() -> Iterator[QDialog]:
    from app.core.types import Parameter
    from app.ui.parameter_dialog import ParameterDialog

    dialog = ParameterDialog({"breite": Parameter(name="breite", value=40.0, unit="mm")})
    try:
        yield dialog
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("points", POINTS)
@pytest.mark.parametrize("make", [_calibration, _parameter], ids=["kalibrieren", "parameter"])
def test_the_other_dialogs_with_a_back_show_every_line(
    qt_app: QApplication, points: int, make: object
) -> None:
    with _font(qt_app, points), make() as dialog:  # type: ignore[operator]
        dialog.show()
        _settle(qt_app)
        _open_every_flap(dialog)
        _settle(qt_app)
        assert not _cut_captions(dialog)
        dialog.reject()
