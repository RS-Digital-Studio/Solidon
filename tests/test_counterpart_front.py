"""Gegenstücke zeigen die gewöhnlichen Maße zuerst und erklären die Paarauswahl."""

from dataclasses import asdict

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QFont, QScreen, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QDialogButtonBox, QToolButton

from app.core.bootstrap import load_operations
from app.core.counterpart import PAIRS
from app.core.knowledge.parts.registry import PARTS
from app.i18n import set_language
from app.i18n.catalog import available_languages, install_language
from app.ui.counterpart_dialog import CounterpartDialog
from app.ui.labels import LengthSpin
from app.ui.style import DialogScrollArea, apply_style


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("pair_key", [pair.key for pair in PAIRS])
def test_counterpart_front_respects_the_shared_parameter_schema(qt_app, language, pair_key):
    """Paar und gewöhnliche Maße vorn; das gemeinsame Schema bestimmt die Rückseite."""
    install_language(language)
    set_language(language)
    load_operations()
    dialog = CounterpartDialog("Erste Fläche", "Zweite Fläche")
    try:
        dialog.pairs.setCurrentIndex(dialog.pairs.findData(pair_key))
        pair = dialog.pair()
        schema = PARTS.get(pair.part_a).params.spec()
        front = {
            field.name
            for field in schema
            if field.name in pair.shared and field.placement != "advanced"
        }
        visible = {name for name, field in dialog._fields.items() if field.isVisibleTo(dialog)}
        assert visible == front
        assert len(visible) + 1 <= 3
        assert set(dialog.shared()) == set(pair.shared)
    finally:
        dialog.close()
        dialog.deleteLater()


def test_counterpart_flap_preserves_every_edited_shared_value(qt_app):
    """Klappen erhält Form, Spiel und Fase; auch der nächste Paartyp bleibt vollständig."""
    load_operations()
    dialog = CounterpartDialog("Erste Fläche", "Zweite Fläche")
    try:
        dialog.show()
        qt_app.processEvents()
        flap = dialog.findChild(QToolButton, "sectionHeading")
        assert flap is not None and not flap.isChecked()
        QTest.mouseClick(flap, Qt.MouseButton.LeftButton)
        values = {"diameter": 6.0, "length": 12.0, "shape": "hex", "play": 0.2, "chamfer": 0.8}
        for name, value in values.items():
            field = dialog._fields[name]
            assert field.isVisibleTo(dialog)
            if isinstance(field, QComboBox):
                field.setCurrentIndex(field.findData(value))
            else:
                assert isinstance(field, LengthSpin)
                field.set_value_mm(value)
        QTest.mouseClick(flap, Qt.MouseButton.LeftButton)
        assert dialog.shared()["shape"] == "hex"
        assert {
            key: value for key, value in dialog.shared().items() if key != "shape"
        } == pytest.approx({key: value for key, value in values.items() if key != "shape"})
        QTest.mouseClick(flap, Qt.MouseButton.LeftButton)
        assert dialog.shared()["shape"] == "hex"
        assert {
            key: value for key, value in dialog.shared().items() if key != "shape"
        } == pytest.approx({key: value for key, value in values.items() if key != "shape"})
        dialog.pairs.setCurrentIndex(dialog.pairs.findData("heatset_and_screw_hole"))
        assert set(dialog.shared()) == {"size"}
        assert not flap.isVisibleTo(dialog)
        dialog.pairs.setCurrentIndex(dialog.pairs.findData("screw_and_nut"))
        assert set(dialog.shared()) == {"size", "play"}
        assert flap.isVisibleTo(dialog)
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("pair_key", [pair.key for pair in PAIRS])
def test_counterpart_pair_carries_its_current_explanation(qt_app, language, pair_key):
    """FD-50: Der Erklärungssatz gehört auch zur Kurzhilfe und zum Bildschirmleser."""
    install_language(language)
    set_language(language)
    load_operations()
    dialog = CounterpartDialog("Erste Fläche", "Zweite Fläche")
    try:
        dialog.pairs.setCurrentIndex(dialog.pairs.findData(pair_key))
        expected = str(dialog.pair().doc)
        assert expected
        assert len(expected.split()) <= 25
        assert dialog.note.text() == expected
        assert dialog.pairs.toolTip() == expected
        assert dialog.pairs.accessibleDescription() == expected
        caption = dialog._head.labelForField(dialog.pairs)
        assert caption is not None
        assert caption.toolTip() == expected
        assert caption.accessibleDescription() == expected
    finally:
        dialog.close()
        dialog.deleteLater()
        set_language("de")


def _settle(application):
    """Die verzögerten Layoutmessungen bis hinter die Klappe zustellen."""
    for _ in range(8):
        application.processEvents()


def _wheel(application, field):
    """Eine echte Radraste abwärts an das Feld zustellen."""
    point = field.rect().center()
    event = QWheelEvent(
        QPointF(point),
        QPointF(field.mapToGlobal(point)),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    application.sendEvent(field, event)
    return event


@pytest.mark.parametrize("pair_key", [pair.key for pair in PAIRS])
def test_counterpart_scrolling_without_focus_preserves_every_value(qt_app, pair_key):
    """KF-M1: Rollen darf weder das Paar tauschen noch offene oder verborgene Werte ändern."""
    load_operations()
    dialog = CounterpartDialog("Erste Fläche", "Zweite Fläche")
    try:
        dialog.pairs.setCurrentIndex(dialog.pairs.findData(pair_key))
        dialog.show()
        flap = dialog.findChild(QToolButton, "sectionHeading")
        if flap is not None and flap.isVisibleTo(dialog):
            flap.setChecked(True)
        _settle(qt_app)
        dialog._accept.setFocus()
        before = dialog.shared()
        changes = []
        dialog.valuesChanged.connect(lambda: changes.append(True))
        for field in [*dialog._fields.values(), dialog.pairs]:
            assert not field.hasFocus()
            event = _wheel(qt_app, field)
            assert not event.isAccepted()
            assert dialog.pair().key == pair_key
            assert dialog.shared() == before
            assert not changes
        if flap is not None and flap.isVisibleTo(dialog):
            flap.setChecked(False)
            _wheel(qt_app, dialog.pairs)
            assert dialog.shared() == before
            assert not changes
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("name", ["diameter", "shape", "pair"])
def test_counterpart_focused_wheel_still_changes_the_chosen_value(qt_app, name):
    """Nach ausdrücklichem Fokussieren bleibt die gewöhnliche Radbedienung erhalten."""
    load_operations()
    dialog = CounterpartDialog("Erste Fläche", "Zweite Fläche")
    try:
        dialog.show()
        flap = dialog.findChild(QToolButton, "sectionHeading")
        assert flap is not None
        flap.setChecked(True)
        _settle(qt_app)
        field = dialog.pairs if name == "pair" else dialog._fields[name]
        field.setFocus()
        assert field.hasFocus()
        before = (dialog.pair().key, dialog.shared())
        event = _wheel(qt_app, field)
        assert event.isAccepted()
        assert (dialog.pair().key, dialog.shared()) != before
    finally:
        dialog.close()
        dialog.deleteLater()


def test_counterpart_wheel_and_cancel_preserve_the_document(qt_app, monkeypatch):
    """Der angeschlossene Ablauf übernimmt weder Radereignisse noch abgebrochene Eingaben."""
    from app.core.types import Parameter
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tests.ui_helpers import top_face, two_plates

    window = MainWindow(Session(), UiSettings())
    try:
        first, second = two_plates(window)
        window.object_tree.select_features(
            ((first, top_face(window, first)), (second, top_face(window, second)))
        )
        _settle(qt_app)
        document = window.session.project.document
        document.parameters["existing_size"] = Parameter("existing_size", 17.0)
        before = asdict(document)
        previews = []
        monkeypatch.setattr(
            window.session,
            "preview_async",
            lambda then, drafts=None, **rest: previews.append(list(drafts or [])),
        )

        def exercise(dialog):
            dialog.show()
            flap = dialog.findChild(QToolButton, "sectionHeading")
            assert flap is not None
            flap.setChecked(True)
            _settle(qt_app)
            dialog._accept.setFocus()
            values = dialog.shared()
            preview_count = len(previews)
            for field in [*dialog._fields.values(), dialog.pairs]:
                _wheel(qt_app, field)
            _settle(qt_app)
            assert dialog.shared() == values
            assert dialog.pair().key == "dowel"
            assert len(previews) == preview_count
            assert asdict(document) == before
            diameter = dialog._fields["diameter"]
            diameter.setFocus()
            _wheel(qt_app, diameter)
            assert dialog.shared()["diameter"] != values["diameter"]
            assert asdict(document) == before
            dialog.reject()
            return int(dialog.DialogCode.Rejected)

        monkeypatch.setattr(CounterpartDialog, "exec", exercise)
        window.action_counterpart()
        assert asdict(document) == before
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("point_size", [10, 16])
def test_counterpart_flap_uses_the_available_width_and_keeps_a_user_size(
    qt_app, monkeypatch, language, point_size
):
    """Auf der kleinsten Arbeitsfläche passen echte Inhaltsschriften und Klappe (§13.3)."""
    monkeypatch.setattr(QScreen, "availableGeometry", lambda self: QRect(0, 0, 1920, 1080))
    install_language(language)
    set_language(language)
    load_operations()
    previous_font = qt_app.font()
    previous_style = qt_app.styleSheet()
    font = QFont(previous_font)
    font.setPointSize(point_size)
    qt_app.setFont(font)
    apply_style(qt_app, "dark")
    dialog = CounterpartDialog("Erste Fläche", "Zweite Fläche")
    try:
        dialog.show()
        _settle(qt_app)
        assert dialog.pairs.font().pointSize() == point_size
        assert all(field.font().pointSize() == point_size for field in dialog._fields.values())
        closed = dialog.size()
        flap = dialog.findChild(QToolButton, "sectionHeading")
        assert flap is not None
        flap.setFocus()
        QTest.keyClick(flap, Qt.Key.Key_Space)
        _settle(qt_app)
        assert flap.isChecked()
        assert dialog.height() >= closed.height()
        scroll = dialog.findChild(DialogScrollArea)
        assert scroll is not None
        assert scroll.horizontalScrollBar().maximum() == 0
        assert dialog.screen().availableGeometry().contains(dialog.frameGeometry())
        assert all(field.isVisibleTo(dialog) for field in dialog._fields.values())
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None and buttons.parentWidget() is dialog
        assert all(button.font().pointSize() == point_size for button in buttons.buttons())
        assert dialog.rect().contains(buttons.geometry())

        dialog.resize(dialog.size() + QSize(20, 20))
        _settle(qt_app)
        chosen = dialog.size()
        QTest.keyClick(flap, Qt.Key.Key_Space)
        _settle(qt_app)
        assert not flap.isChecked()
        assert dialog.size() == chosen
        QTest.keyClick(flap, Qt.Key.Key_Space)
        _settle(qt_app)
        assert dialog.size() == chosen
    finally:
        dialog.close()
        dialog.deleteLater()
        qt_app.setFont(previous_font)
        qt_app.setStyleSheet(previous_style)
        set_language("de")
