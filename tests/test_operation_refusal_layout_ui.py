"""Eine verspätete Ebenenabsage lässt Erklärung und Korrekturwege erreichbar (FD44)."""

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QPushButton

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.sketch.planes import frame_for_sketch
from app.i18n import set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.labels import value_text
from app.ui.op_dialog import OperationDialog
from app.ui.refusal_details import silent_ways
from app.ui.style import apply_style
from app.ui.theme import apply_theme


def _settle(application: QApplication) -> None:
    for _ in range(16):
        application.processEvents()


def _plane_error() -> ValidationError:
    """Die echte Fehlerursache aus dem ursprünglichen FD44-Bild, keine Fehlerattrappe."""
    with pytest.raises(ValidationError) as caught:
        frame_for_sketch("through:0,0,20;10,0,20;20,0,20")
    return caught.value


@pytest.mark.parametrize("language", available_languages())
def test_the_plane_reason_is_explained_in_the_selected_language(language: str) -> None:
    """Die konkrete Kennung wird erklärt; unbekannte Gründe bleiben diagnostizierbar."""
    install_language(language)
    set_language(language)
    reason = _plane_error().values["reason"]
    assert value_text("reason", reason) == tr(
        "Die drei Punkte liegen auf einer Geraden oder aufeinander — "
        "sie spannen keine Ebene auf. Einen davon seitlich versetzen."
    )
    assert value_text("reason", "another_reason") == "another_reason"
    assert value_text("part_name", reason) == reason


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("points", [11, 18])
@pytest.mark.parametrize("manual", [False, True])
def test_a_late_refusal_fits_or_scrolls_without_overriding_a_manual_size(
    qt_app: QApplication, language: str, points: int, manual: bool
) -> None:
    """Automatische Höhe folgt der Absage; ein gezogener Rahmen behält seinen Rollweg."""
    load_operations()
    install_language(language)
    set_language(language)
    apply_theme(qt_app, "light")
    previous_font = QFont(qt_app.font())
    font = QFont(previous_font)
    font.setPointSize(points)
    qt_app.setFont(font)
    apply_style(qt_app, "light")
    dialog = OperationDialog(REGISTRY.get("sketch_pocket"), {"body": "Körper"})
    try:
        dialog.show()
        _settle(qt_app)
        if manual:
            dialog.resize(dialog.width() + 30, dialog.height() + 20)
            _settle(qt_app)
        before = dialog.size()
        error = _plane_error()
        dialog.show_refusal(error)
        _settle(qt_app)
        # Jeder Weg steht da: als Satz oder, wo der Dialog ihn selbst einlöst,
        # als Knopf; was er ohne Feld nicht einlösen kann, sagt er nicht (FD-95,
        # ``refusal_details.field_ways``, ``silent_ways``).
        silent = silent_ways(error, dialog)
        buttons = {button.text() for button in dialog._refusal.findChildren(QPushButton)}
        assert all(
            str(action.label) in dialog._refusal.text() or str(action.label) in buttons
            for action in error.suggestions
            if action.id not in silent
        )
        label = dialog._refusal.label
        assert label.font().pointSizeF() == pytest.approx(points)
        scroll = dialog._scroll
        assert label.height() >= label.heightForWidth(label.width())
        if manual:
            assert dialog.size() == before
            assert scroll.verticalScrollBar().maximum() > 0
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            _settle(qt_app)
        else:
            assert dialog.height() > before.height()
            assert scroll.verticalScrollBar().maximum() == 0
        # Auch die letzte Korrekturzeile ist sichtbar, nicht bloß das QLabel als Objekt.
        bottom = label.mapTo(scroll.viewport(), QPoint(0, label.height() - 1))
        assert scroll.viewport().rect().contains(bottom)
        assert dialog.rect().contains(
            QRect(dialog._accept_button.mapTo(dialog, QPoint()), dialog._accept_button.size())
        )
        grown = dialog.size()
        dialog.show_refusal(None)
        _settle(qt_app)
        assert dialog.size() == grown, "Eine passive Änderung verkleinert den Rahmen nicht."
    finally:
        dialog.close()
        dialog.deleteLater()
        qt_app.setFont(previous_font)
        apply_style(qt_app, "light")


@pytest.mark.parametrize("manual", [False, True])
def test_a_live_application_font_change_preserves_the_refusal_and_size_choice(
    qt_app: QApplication, manual: bool
) -> None:
    """Eine wirkliche größere Inhaltsschrift erreicht den offenen Dialog und seine Absage."""
    load_operations()
    install_language("de")
    set_language("de")
    apply_theme(qt_app, "light")
    previous_font = QFont(qt_app.font())
    font = QFont(previous_font)
    font.setPointSize(11)
    qt_app.setFont(font)
    apply_style(qt_app, "light")
    dialog = OperationDialog(REGISTRY.get("sketch_pocket"), {"body": "Körper"})
    try:
        dialog.show()
        _settle(qt_app)
        dialog.show_refusal(_plane_error())
        _settle(qt_app)
        label = dialog._refusal.label
        assert label.font().pointSizeF() == pytest.approx(11)
        before_line = label.fontMetrics().lineSpacing()
        if manual:
            dialog.resize(dialog.width() + 30, dialog.height() + 20)
            _settle(qt_app)
        before = dialog.size()
        font.setPointSize(18)
        qt_app.setFont(font)
        apply_style(qt_app, "light")
        _settle(qt_app)
        assert label.font().pointSizeF() == pytest.approx(18)
        assert label.fontMetrics().lineSpacing() > before_line
        scroll = dialog._scroll
        if manual:
            assert dialog.size() == before
            assert scroll.verticalScrollBar().maximum() > 0
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            _settle(qt_app)
        else:
            assert dialog.height() > before.height()
            assert scroll.verticalScrollBar().maximum() == 0
        bottom = label.mapTo(scroll.viewport(), QPoint(0, label.height() - 1))
        assert scroll.viewport().rect().contains(bottom)
    finally:
        dialog.close()
        dialog.deleteLater()
        qt_app.setFont(previous_font)
        apply_style(qt_app, "light")
