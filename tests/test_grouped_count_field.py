"""Ganzzahlen ab vier Stellen stehen auch im Feld in Dreiergruppen (FD-124).

*Dreiecke verringern* zeigte „1051736“ — sieben Ziffern, die man zählen muss.
Entscheidung Koordinator: Ein Ganzzahlfeld schreibt wie jeder Satz der
Anwendung (``labels.count_text``, geschütztes Leerzeichen in jeder Sprache)
und nimmt Eingaben mit und ohne Trennzeichen an. Zahlen mit Nachkomma
behalten ihr Format, denn dort ist das letzte Trennzeichen das Komma.
"""

from __future__ import annotations

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.ui.labels import count_text
from tests.ui_helpers import wait_until

#: Das geschützte Leerzeichen zwischen den Gruppen.
GAP = " "


def _triangles(qt_app: QApplication, start: int) -> object:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    return OperationDialog(
        REGISTRY.get("decimate_mesh"), {"obj_1": "Körper"}, None, values={"triangles": start}
    )


def _typing_into(qt_app: QApplication, dialog: object, field: object) -> QLineEdit:
    """Fenster aktiv, Fokus im Drehfeld, Inhalt markiert — bereit zum Tippen."""
    dialog.show()  # type: ignore[attr-defined]
    dialog.activateWindow()  # type: ignore[attr-defined]
    spin = field.spin  # type: ignore[attr-defined]
    spin.setFocus()
    wait_until(qt_app, spin.hasFocus)
    line = spin.lineEdit()
    line.selectAll()
    return line


def test_a_large_count_stands_in_groups(qt_app: QApplication) -> None:
    from app.ui.op_dialog import ValueField

    dialog = _triangles(qt_app, 1_051_736)
    try:
        field = dialog._editors["triangles"]  # type: ignore[attr-defined]
        assert isinstance(field, ValueField)
        assert field.spin.lineEdit().text() == f"1{GAP}051{GAP}736"
        assert field.spin.lineEdit().text() == count_text(1_051_736)
        assert field.value() == 1_051_736
        # Die Breite reicht für die größte Zahl samt Trennzeichen.
        assert field.spin.width() >= field.spin.fontMetrics().horizontalAdvance(
            count_text(5_000_000)
        )
    finally:
        dialog.deleteLater()  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "typed",
    ["2103472", "2 103 472", f"2{GAP}103{GAP}472", "2.103.472", "2,103,472"],
)
def test_a_count_is_read_with_and_without_separators(qt_app: QApplication, typed: str) -> None:
    from app.ui.op_dialog import ValueField

    dialog = _triangles(qt_app, 1_000_000)
    try:
        field = dialog._editors["triangles"]  # type: ignore[attr-defined]
        assert isinstance(field, ValueField)
        line = _typing_into(qt_app, dialog, field)
        QTest.keyClicks(line, typed)
        # Wie ein Fokuswechsel aus dem Feld: Qt schreibt die Zahl neu.
        field.spin.clearFocus()
        qt_app.processEvents()
        assert field.value() == 2_103_472, f"{typed!r} → {line.text()!r}"
        assert line.text() == f"2{GAP}103{GAP}472"
        assert not field.refusal()
    finally:
        dialog.reject()  # type: ignore[attr-defined]
        dialog.deleteLater()  # type: ignore[attr-defined]


def test_a_count_beyond_the_limit_is_refused_in_groups(qt_app: QApplication) -> None:
    from app.ui.op_dialog import ValueField

    dialog = _triangles(qt_app, 1_000_000)
    try:
        field = dialog._editors["triangles"]  # type: ignore[attr-defined]
        assert isinstance(field, ValueField)
        line = _typing_into(qt_app, dialog, field)
        QTest.keyClicks(line, "6000000")
        qt_app.processEvents()
        said = field.refusal()
        assert f"6{GAP}000{GAP}000" in said and f"5{GAP}000{GAP}000" in said, said
        assert field.value() != 6_000_000, "die abgelehnte Zahl wird nicht übernommen"
    finally:
        dialog.reject()  # type: ignore[attr-defined]
        dialog.deleteLater()  # type: ignore[attr-defined]


def test_small_counts_and_lengths_keep_their_form(qt_app: QApplication) -> None:
    """Unter vier Stellen kein Trennzeichen; eine Länge bleibt „1234,50 mm“."""
    from app.ui.op_dialog import OperationDialog, ValueField

    bootstrap.load_operations()
    dialog = OperationDialog(REGISTRY.get("drill_hole"), {}, None, values={"x": 1234.5})
    small = _triangles(qt_app, 999)
    try:
        length = dialog._editors["x"]
        assert isinstance(length, ValueField)
        assert length.spin.lineEdit().text().startswith("1234,50")
        count = small._editors["triangles"]  # type: ignore[attr-defined]
        assert isinstance(count, ValueField)
        assert count.spin.lineEdit().text() == "999"
    finally:
        dialog.deleteLater()
        small.deleteLater()  # type: ignore[attr-defined]
