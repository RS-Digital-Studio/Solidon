"""Einleitung und Handlungen bleiben nach Schriftwechseln vollständig (FD54)."""

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.i18n import set_language
from app.i18n.catalog import available_languages, install_language
from app.ui.app import install_qt_translations
from app.ui.op_dialog import OperationDialog, accept_text, lead_sentence
from app.ui.style import apply_style
from app.ui.theme import apply_theme


def _settle(application: QApplication) -> None:
    for _ in range(30):
        application.processEvents()


def _font(application: QApplication, points: int) -> None:
    font = QFont(application.font())
    font.setPointSize(points)
    application.setFont(font)
    apply_style(application, "light")
    _settle(application)


@pytest.fixture
def dialog(qt_app: QApplication, request: pytest.FixtureRequest) -> Iterator[OperationDialog]:
    load_operations()
    install_language(request.param)
    set_language(request.param)
    install_qt_translations(qt_app, request.param)
    previous = QFont(qt_app.font())
    apply_theme(qt_app, "light")
    _font(qt_app, 11)
    widget = OperationDialog(
        REGISTRY.get("group_pattern"),
        {"body": "Körper"},
        features={"a": "Fläche 1", "b": "Fläche 2"},
        values={"at_features": ["a", "b"]},
    )
    widget.show()
    _settle(qt_app)
    try:
        yield widget
    finally:
        widget.close()
        widget.deleteLater()
        qt_app.setFont(previous)
        apply_style(qt_app, "light")
        install_qt_translations(qt_app, "de")


@pytest.mark.parametrize("dialog", available_languages(), indirect=True)
@pytest.mark.parametrize("manual", [False, True])
def test_the_complete_lead_and_both_actions_follow_real_font_changes(
    qt_app: QApplication, dialog: OperationDialog, manual: bool
) -> None:
    """Automatisch wird Platz geschaffen, gewählte Maße bleiben mit Umbruch bestehen."""
    box = dialog.findChild(QDialogButtonBox)
    assert box is not None
    primary = box.button(QDialogButtonBox.StandardButton.Ok)
    cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
    assert primary is not None and cancel is not None
    texts = [primary.text(), cancel.text()]
    if manual:
        dialog.resize(dialog.width(), dialog.height() + 11)
        _settle(qt_app)
    chosen = dialog.size()
    for points in (11, 18, 11):
        _font(qt_app, points)
        description = dialog._description
        assert description is not None
        assert description.font().pointSizeF() == pytest.approx(points)
        assert description.text() == lead_sentence(dialog.spec)
        assert description.height() >= description.heightForWidth(description.width())
        for button, source in zip((primary, cancel), texts, strict=True):
            assert button.font().pointSizeF() == pytest.approx(points)
            assert " ".join(button.text().split()) == source
            assert button.width() >= button.sizeHint().width()
            assert button.height() >= button.sizeHint().height()
            assert box.rect().contains(button.geometry())
            assert dialog.rect().contains(button.mapTo(dialog, QPoint(0, 0)))
        if manual:
            assert dialog.size() == chosen
        if points == 11:
            assert box.orientation() == Qt.Orientation.Horizontal
    assert primary.text() == accept_text(dialog.spec)


@pytest.mark.parametrize("dialog", available_languages(), indirect=True)
@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Escape])
def test_the_narrow_footer_keeps_return_and_escape(
    qt_app: QApplication, dialog: OperationDialog, key: Qt.Key
) -> None:
    """Auch nach Umordnung bleiben Annahme und Abbruch dieselben Qt-Handlungen."""
    dialog.resize(dialog.width(), dialog.height() + 11)
    _settle(qt_app)
    _font(qt_app, 18)
    QTest.keyClick(dialog, key)
    _settle(qt_app)
    assert not dialog.isVisible()
    assert dialog.result() == (
        QDialog.DialogCode.Accepted if key == Qt.Key.Key_Return else QDialog.DialogCode.Rejected
    )


@pytest.mark.parametrize("dialog", available_languages(), indirect=True)
def test_a_single_long_action_wraps_without_losing_its_name_and_unwraps_again(
    qt_app: QApplication, dialog: OperationDialog
) -> None:
    """Auch ein langes Wort setzt keine Breitenuntergrenze und bleibt über Return erreichbar."""
    dialog.resize(dialog.width(), dialog.height() + 11)
    _settle(qt_app)
    chosen = dialog.size()
    box = dialog.findChild(QDialogButtonBox)
    assert box is not None
    primary = box.button(QDialogButtonBox.StandardButton.Ok)
    assert primary is not None
    source = primary.text() + " " + "abcdefghijklmnopqrstuv" * 4
    primary.setText(source)
    _font(qt_app, 18)
    assert dialog.width() == chosen.width()
    layout = dialog.layout()
    assert layout is not None
    margins = layout.contentsMargins()
    footer_height = box.sizeHint().height() + margins.top() + margins.bottom() + layout.spacing()
    line = dialog._scroll.widget().fontMetrics().lineSpacing()
    bar = dialog._scroll.horizontalScrollBar()
    rail = bar.height() if bar.isVisibleTo(dialog) else 0
    assert dialog.height() == max(chosen.height(), footer_height + line + rail)
    assert dialog._scroll.viewport().height() >= line
    fitted = dialog.size()
    assert "\n" in primary.text()
    assert "".join(primary.text().split()) == "".join(source.split())
    assert primary.accessibleName() == source
    assert primary.width() >= primary.sizeHint().width()
    assert primary.height() >= primary.sizeHint().height()
    assert box.rect().contains(primary.geometry())
    primary.setText(accept_text(dialog.spec))
    _font(qt_app, 11)
    assert primary.text() == accept_text(dialog.spec)
    assert box.orientation() == Qt.Orientation.Horizontal
    assert dialog.size() == fitted


@pytest.mark.parametrize("dialog", available_languages(), indirect=True)
def test_return_on_the_cancel_button_keeps_its_role_after_reflow(
    qt_app: QApplication, dialog: OperationDialog
) -> None:
    """Tastaturfokus auf Abbrechen bleibt auch in der senkrechten Leiste ein Abbruch."""
    dialog.resize(dialog.width(), dialog.height() + 11)
    _settle(qt_app)
    _font(qt_app, 18)
    box = dialog.findChild(QDialogButtonBox)
    assert box is not None
    cancel = box.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel is not None
    cancel.setFocus(Qt.FocusReason.TabFocusReason)
    _settle(qt_app)
    QTest.keyClick(cancel, Qt.Key.Key_Return)
    _settle(qt_app)
    assert not dialog.isVisible()
    assert dialog.result() == QDialog.DialogCode.Rejected
