"""Merkmallisten geben Leerfläche frei und behalten alle wählbaren Zeilen (FD45)."""

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.i18n import set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.op_dialog import FeatureSetField, OperationDialog
from app.ui.style import apply_style
from app.ui.theme import apply_theme


def _settle(application: QApplication) -> None:
    for _ in range(12):
        application.processEvents()


@pytest.fixture
def field(qt_app: QApplication) -> Iterator[FeatureSetField]:
    apply_theme(qt_app, "light")
    widget = FeatureSetField({}, (), empty=None)
    widget.show()
    _settle(qt_app)
    try:
        yield widget
    finally:
        widget.close()
        widget.deleteLater()


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("points", [11, 18])
@pytest.mark.parametrize(
    "operation, count", [("pattern_feature", 1), ("group_pattern", 6), ("hollow_object", 6)]
)
def test_short_feature_lists_fit_the_actual_rows_in_both_dialogs(
    qt_app: QApplication, language: str, points: int, operation: str, count: int
) -> None:
    """Die Fundstellen bleiben mit sechs Katalogen und größerer Schrift kompakt."""
    load_operations()
    install_language(language)
    set_language(language)
    apply_theme(qt_app, "light")
    previous_font = QFont(qt_app.font())
    font = QFont(previous_font)
    font.setPointSize(points)
    qt_app.setFont(font)
    apply_style(qt_app, "light")
    choices = {str(row): f"{tr('Fläche')} {row + 1}" for row in range(count)}
    dialog = OperationDialog(
        REGISTRY.get(operation),
        {"body": "Körper"},
        features=choices,
        values={"openings" if operation == "hollow_object" else "at_features": list(choices)},
    )
    try:
        dialog.show()
        _settle(qt_app)
        editor = dialog.findChild(FeatureSetField)
        assert editor is not None
        assert editor.isVisibleTo(dialog)
        listing = editor.list
        assert listing.font().pointSizeF() == pytest.approx(points)
        last = listing.visualItemRect(listing.item(count - 1))
        assert listing.viewport().rect().contains(last)
        assert listing.verticalScrollBar().maximum() == 0
        assert listing.viewport().height() - last.bottom() - 1 < last.height(), (
            "Unter den Zeilen bleibt weniger als eine weitere Zeile leer."
        )
        assert editor.value() == list(choices)
        assert editor.whole.isVisibleTo(dialog) == (operation == "hollow_object")
    finally:
        dialog.close()
        dialog.deleteLater()
        qt_app.setFont(previous_font)
        apply_style(qt_app, "light")


def test_empty_then_added_and_removed_features_resize_without_losing_the_selection(
    qt_app: QApplication, field: FeatureSetField
) -> None:
    """Eine leere Pflichtliste bleibt sichtbar; Modelländerungen bestimmen ihre Höhe neu."""
    empty = field.list.height()
    assert 0 < empty <= 2 * field.list.fontMetrics().lineSpacing() + 2 * field.list.frameWidth()
    assert not field.valid
    for row in range(6):
        field.add_feature(str(row), f"Fläche {row + 1}")
    _settle(qt_app)
    six = field.list.height()
    assert six > empty
    assert field.value() == [str(row) for row in range(6)]
    for _ in range(5):
        field.list.takeItem(field.list.count() - 1)
    _settle(qt_app)
    assert field.list.height() < six
    assert field.list.verticalScrollBar().maximum() == 0
    field.list.clear()
    _settle(qt_app)
    assert field.list.height() == empty


def test_a_font_change_grows_the_rows_and_a_changed_label_gets_its_full_height(
    qt_app: QApplication, field: FeatureSetField
) -> None:
    """Schrift und mehrzeilige Bezeichnungen ändern die echte Zeilenhöhe nach dem Öffnen."""
    field.add_feature("one", "Fläche 1")
    _settle(qt_app)
    small = field.list.height()
    font = QFont(field.list.font())
    font.setPointSizeF(font.pointSizeF() * 2)
    field.list.setFont(font)
    _settle(qt_app)
    assert field.list.height() > small
    large = field.list.height()
    field.list.item(0).setText("Fläche 1\n    unten")
    _settle(qt_app)
    assert field.list.height() > large
    assert field.list.viewport().rect().contains(field.list.visualItemRect(field.list.item(0)))


def test_a_long_list_scrolls_to_the_last_feature_and_keeps_it_keyboard_selectable(
    qt_app: QApplication, field: FeatureSetField
) -> None:
    """Die Höhenbegrenzung entfernt keine Merkmale und sperrt die letzte Zeile nicht aus."""
    for row in range(80):
        field.add_feature(str(row), f"Fläche {row + 1}")
    _settle(qt_app)
    listing = field.list
    assert listing.count() == 80
    assert listing.height() < sum(listing.sizeHintForRow(row) for row in range(80))
    assert listing.verticalScrollBar().maximum() > 0
    listing.setCurrentRow(0)
    listing.setFocus()
    QTest.keyClick(listing, Qt.Key.Key_End)
    _settle(qt_app)
    assert listing.currentRow() == 79
    assert listing.viewport().rect().contains(listing.visualItemRect(listing.item(79)))
    QTest.keyClick(listing, Qt.Key.Key_Space)
    assert "79" not in field.value()
    QTest.keyClick(listing, Qt.Key.Key_Space)
    assert "79" in field.value()


def test_wide_labels_keep_their_horizontal_scrollbar_below_the_complete_row(
    qt_app: QApplication, field: FeatureSetField
) -> None:
    """Eine lange Bezeichnung bleibt erreichbar, ihr Rollbalken verdeckt keine Textzeile."""
    field.add_feature("wide", "    Ausführliche Flächenbezeichnung " * 12)
    _settle(qt_app)
    listing = field.list
    assert listing.horizontalScrollBar().maximum() > 0
    assert listing.verticalScrollBar().maximum() == 0
    assert listing.visualItemRect(listing.item(0)).bottom() < listing.viewport().height()
    listing.horizontalScrollBar().setValue(listing.horizontalScrollBar().maximum())
    _settle(qt_app)
    assert listing.visualItemRect(listing.item(0)).right() < listing.viewport().width()
    field.list.item(0).setText("Kurz")
    _settle(qt_app)
    assert listing.horizontalScrollBar().maximum() == 0


def test_changed_item_padding_is_measured_after_the_style_change(
    qt_app: QApplication, field: FeatureSetField
) -> None:
    """Auch ein anderer Zeileninnenrand zählt zum Inhalt, nicht nur die Schriftgröße."""
    field.add_feature("one", "Fläche 1")
    _settle(qt_app)
    previous = field.list.height()
    field.list.setStyleSheet("QListWidget::item { padding: 12px; }")
    _settle(qt_app)
    assert field.list.height() > previous
    assert field.list.viewport().rect().contains(field.list.visualItemRect(field.list.item(0)))


@pytest.mark.parametrize("manual", [False, True])
def test_added_features_and_a_later_font_change_reach_the_open_dialog(
    qt_app: QApplication, manual: bool
) -> None:
    """Der Kundeneinstieg wächst bis zum Fenster; eine gewählte Größe bleibt bestehen."""
    load_operations()
    apply_theme(qt_app, "light")
    dialog = OperationDialog(
        REGISTRY.get("group_pattern"),
        {"body": "Körper"},
        features={"0": "Fläche 1"},
        values={"at_features": ["0"]},
    )
    try:
        dialog.show()
        _settle(qt_app)
        editor = dialog.findChild(FeatureSetField)
        assert editor is not None
        if manual:
            dialog.resize(dialog.width() + 30, dialog.height() + 20)
            _settle(qt_app)
        before = dialog.size()
        for row in range(1, 6):
            assert dialog.take_feature(str(row), label=f"Fläche {row + 1}")
        _settle(qt_app)
        assert editor.list.count() == 6
        assert editor.list.verticalScrollBar().maximum() == 0
        if manual:
            assert dialog.size() == before
            assert dialog._scroll.verticalScrollBar().maximum() > 0
        else:
            assert dialog.height() > before.height()
            assert dialog._scroll.verticalScrollBar().maximum() == 0
        normal_row = editor.list.sizeHintForRow(0)
        font = QFont(editor.list.font())
        font.setPointSize(18)
        editor.list.setFont(font)
        _settle(qt_app)
        assert editor.list.font().pointSizeF() == pytest.approx(18)
        assert editor.list.sizeHintForRow(0) > normal_row
        if manual:
            assert dialog.size() == before
            assert dialog._scroll.verticalScrollBar().maximum() > 0
        else:
            assert dialog._scroll.verticalScrollBar().maximum() == 0
        for row in range(6, 80):
            assert dialog.take_feature(str(row), label=f"Fläche {row + 1}")
        _settle(qt_app)
        assert editor.list.count() == 80
        assert editor.list.verticalScrollBar().maximum() > 0
        if manual:
            assert dialog.size() == before
        else:
            assert dialog._scroll.verticalScrollBar().maximum() == 0
    finally:
        dialog.close()
        dialog.deleteLater()


def test_a_later_tall_row_can_scroll_its_last_text_line_into_view(
    qt_app: QApplication, field: FeatureSetField
) -> None:
    """Eine hohe spätere Zeile bleibt unterhalb der Zeilenobergrenze vollständig lesbar."""
    font = QFont(field.list.font())
    font.setPointSize(11)
    field.list.setFont(font)
    field.add_feature("short", "Fläche 1")
    field.add_feature("tall", "\n".join(f"Teilfläche {row}" for row in range(12)))
    _settle(qt_app)
    listing = field.list
    assert listing.font().pointSizeF() == pytest.approx(11)
    assert listing.sizeHintForRow(1) > listing.viewport().height()
    listing.verticalScrollBar().setValue(listing.verticalScrollBar().maximum())
    _settle(qt_app)
    bottom = listing.visualItemRect(listing.item(1)).bottom()
    assert 0 <= bottom < listing.viewport().height()
    assert field.value() == ["short", "tall"]
