"""Die Gegenstückhöhe gehört zum fertigen Umbruch, nicht zu vorläufigen Rollleisten."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontInfo, QScreen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QToolButton

from app.core.bootstrap import load_operations
from app.core.counterpart import PAIRS
from app.i18n import set_language
from app.i18n.catalog import install_language
from app.ui.app import install_qt_translations
from app.ui.counterpart_dialog import CounterpartDialog
from app.ui.style import _hidden_height, apply_style
from app.ui.theme import apply_theme, current_theme

# Die fünf vorhandenen Sprachbilder liefern die vollständigen Herkunftszeilen.
# EN ergänzt denselben Inhalt aus dem Katalog; sein ursprünglicher Lauf brach ab.
PLACES = {
    "de": "Linke Seite · 600 mm² · aus der Konstruktion",
    "en": "Left side · 600 mm² · from the design",
    "es": "Lado izquierdo · 600 mm² · del diseño",
    "fr": "Côté gauche · 600 mm² · de la conception",
    "it": "Lato sinistro · 600 mm² · dal progetto",
    "pt": "Lado esquerdo · 600 mm² · do projeto",
}


def _settle(application):
    """Die vorhandenen Layoutanforderungen und Nullzeitgeber zustellen."""
    for _ in range(8):
        application.processEvents()


def _close(dialog):
    """Den eigenen Dialog vor dem nächsten anwendungsweiten Schriftwechsel freigeben."""
    dialog.close()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _font(application, points):
    font = QFont(application.font())
    font.setPointSize(points)
    application.setFont(font)
    apply_style(application, "light")


@pytest.fixture
def counterpart_environment(qt_app, monkeypatch):
    """Echte Betriebslage mit übersetzten Qt-Knöpfen und zurückgegebenem Schriftstand."""
    before_font = QFont(qt_app.font())
    before_theme = current_theme()
    monkeypatch.setattr(QScreen, "availableGeometry", lambda self: QRect(0, 0, 1920, 1080))
    apply_theme(qt_app, "light")
    load_operations()
    yield qt_app
    qt_app.setFont(before_font)
    # Thema und Metadaten gehören zusammen; der Stil folgt der alten Schrift
    # auch dann, wenn dasselbe Thema bereits aktiv ist.
    apply_theme(qt_app, before_theme)
    apply_style(qt_app, before_theme)
    install_qt_translations(qt_app, "de")
    set_language("de")


def _dialog(application, language, points, pair_key="dowel"):
    install_language(language)
    set_language(language)
    install_qt_translations(application, language)
    _font(application, points)
    dialog = CounterpartDialog(PLACES[language], PLACES[language])
    dialog.pairs.setCurrentIndex(dialog.pairs.findData(pair_key))
    return dialog


def _assert_front(dialog, points):
    assert dialog.places.font().pointSize() == points
    assert dialog.pairs.font().pointSize() == points
    assert QFontInfo(dialog.places.font()).pointSize() == points
    metrics = dialog.places.fontMetrics()
    assert metrics.horizontalAdvance("iii") < metrics.horizontalAdvance("WWW")
    assert all(field.font().pointSize() == points for field in dialog._fields.values())
    assert all(button.font().pointSize() == points for button in dialog._buttons.buttons())
    assert dialog._scroll.horizontalScrollBar().maximum() == 0
    assert dialog._scroll.verticalScrollBar().maximum() == 0
    assert dialog.rect().contains(dialog._buttons.geometry())
    for label in dialog._scroll.widget().findChildren(QLabel):
        if label.isVisibleTo(dialog) and label.hasHeightForWidth():
            assert label.height() >= label.heightForWidth(label.width())


def _state(dialog):
    """Nur Befunddaten; die Erwartung bleibt der gleiche geschlossene Inhalt."""
    scroll = dialog._scroll
    content = scroll.widget()
    spacer = dialog._body.itemAt(dialog._body.count() - 1)
    return {
        "size": (dialog.width(), dialog.height()),
        "content": (content.width(), content.height()),
        "viewport": (scroll.viewport().width(), scroll.viewport().height()),
        "content_height_for_width": dialog._body.totalHeightForWidth(content.width()),
        "footer_height": dialog._buttons.height(),
        "spacer_height": spacer.geometry().height(),
        "places": (dialog.places.width(), dialog.places.height()),
        "note": (dialog.note.width(), dialog.note.height()),
        "user": repr(dialog._height.user),
    }


@pytest.mark.parametrize("language", PLACES)
@pytest.mark.parametrize("points", [9, 16])
@pytest.mark.parametrize("pair_key", [pair.key for pair in PAIRS])
def test_initial_and_reclosed_counterpart_need_the_same_height(
    counterpart_environment, language, points, pair_key, record_trace
):
    """Originalherkunft, echter Textumbruch und Klappen brauchen keine Leerreserve (FD66)."""
    application = counterpart_environment
    dialog = _dialog(application, language, points, pair_key)
    try:
        dialog.show()
        _settle(application)
        initial = QSize(dialog.size())
        values = dialog.shared()
        assert dialog._height.user is None
        _assert_front(dialog, points)
        initial_state = _state(dialog)
        record_trace("initial", repr(initial_state))
        flap = dialog.findChild(QToolButton, "sectionHeading")
        if flap is not None and flap.isVisibleTo(dialog):
            assert not flap.isChecked()
            anchor = QPoint(dialog.frameGeometry().topLeft())
            QTest.mouseClick(flap, Qt.MouseButton.LeftButton)
            _settle(application)
            assert flap.isChecked()
            assert dialog.width() == initial.width()
            assert dialog.frameGeometry().topLeft() == anchor
            _assert_front(dialog, points)
            record_trace("opened", repr(_state(dialog)))
            QTest.mouseClick(flap, Qt.MouseButton.LeftButton)
            _settle(application)
            assert not flap.isChecked()
            closed_state = _state(dialog)
            record_trace("reclosed", repr(closed_state))
            assert dialog.size() == initial, {"initial": initial_state, "reclosed": closed_state}
            assert dialog.frameGeometry().topLeft() == anchor
            _assert_front(dialog, points)
        assert dialog._height.user is None
        assert dialog.shared() == values
    finally:
        _close(dialog)


@pytest.mark.parametrize("language", PLACES)
@pytest.mark.parametrize("short", [False, True])
def test_user_size_survives_folding_pair_and_real_font_changes(
    counterpart_environment, language, short
):
    """Gewählte Maße gelten auch nach 9→16→9 pt, Paarwechsel und Klappen weiter."""
    application = counterpart_environment
    dialog = _dialog(application, language, 9)
    try:
        dialog.show()
        _settle(application)
        initial = QSize(dialog.size())
        height = initial.height() // 2 if short else initial.height() * 2
        # Die bewusst geräumige Breite trägt auch die größere Knopfschrift;
        # der kurze Fall verlangt ausdrücklich Scrollen statt Rahmenwachstum.
        dialog.resize(initial.width() * 2, height)
        _settle(application)
        chosen = QSize(dialog.size())
        for points in (16, 9):
            _font(application, points)
            _settle(application)
            for pair in PAIRS:
                dialog.pairs.setCurrentIndex(dialog.pairs.findData(pair.key))
                _settle(application)
                assert dialog.pairs.font().pointSize() == points
                assert dialog.size() == chosen
                flap = dialog.findChild(QToolButton, "sectionHeading")
                if flap is not None and flap.isVisibleTo(dialog):
                    for checked in (True, False):
                        flap.setChecked(checked)
                        _settle(application)
                        assert dialog.size() == chosen
                scroll = dialog._scroll
                if short and points == 16 and pair.key == "dowel":
                    assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
                    assert scroll.verticalScrollBar().maximum() > 0
                    assert scroll.viewport().width() < scroll.maximumViewportSize().width()
                scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                _settle(application)
                assert dialog.size() == chosen
                assert dialog.rect().contains(dialog._buttons.geometry())
                visible = [field for field in dialog._fields.values() if field.isVisibleTo(dialog)]
                assert visible
                last = max(visible, key=lambda field: field.mapTo(scroll.widget(), QPoint()).y())
                scroll.ensureWidgetVisible(last)
                _settle(application)
                corner = last.mapTo(scroll.viewport(), last.rect().bottomLeft())
                assert 0 <= corner.y() < scroll.viewport().height()
        assert dialog._height.user == chosen
    finally:
        _close(dialog)


@pytest.mark.parametrize("points", [9, 16])
def test_passive_text_grows_once_and_keeps_the_gained_height(counterpart_environment, points):
    """Eine neue natürliche Messung erlaubt kein späteres passives Schrumpfen."""
    application = counterpart_environment
    dialog = _dialog(application, "fr", points)
    try:
        dialog.show()
        _settle(application)
        initial = QSize(dialog.size())
        original = dialog.places.text()
        dialog.places.setText("\n".join([original] * 3))
        _settle(application)
        grown = QSize(dialog.size())
        assert grown.height() > initial.height()
        assert grown.width() == initial.width()
        dialog.places.setText(original)
        _settle(application)
        assert dialog.size() == grown
        assert dialog._height.user is None
        assert dialog._scroll.verticalScrollBar().maximum() == 0
    finally:
        _close(dialog)


def test_permanent_vertical_bar_remains_part_of_the_wrapping_width(counterpart_environment):
    """Eine ausdrücklich dauernde Leiste bleibt bei der natürlichen Messung bestehen."""
    application = counterpart_environment
    dialog = _dialog(application, "fr", 9)
    try:
        dialog._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        dialog.show()
        _settle(application)
        assert dialog._scroll.verticalScrollBar().isVisibleTo(dialog)
        assert dialog._scroll.viewport().width() < dialog._scroll.width()
        _assert_front(dialog, 9)
        dialog._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        flap = dialog.findChild(QToolButton, "sectionHeading")
        assert flap is not None
        for checked in (True, False):
            flap.setChecked(checked)
            _settle(application)
            assert dialog._scroll.horizontalScrollBar().isVisibleTo(dialog)
            _assert_front(dialog, 9)
    finally:
        _close(dialog)


@pytest.mark.parametrize(
    ("horizontal_policy", "wide_content"),
    [
        (Qt.ScrollBarPolicy.ScrollBarAsNeeded, True),
        (Qt.ScrollBarPolicy.ScrollBarAlwaysOn, False),
        (Qt.ScrollBarPolicy.ScrollBarAsNeeded, False),
    ],
    ids=["real-horizontal-range", "permanent-horizontal-bar", "vertical-range-only"],
)
def test_hidden_height_keeps_required_bars_and_the_user_size(
    counterpart_environment, horizontal_policy, wide_content
):
    """Echte Leisten bleiben Teil des Ausschnitts; nur vorläufige Geometrie fällt weg."""
    application = counterpart_environment
    dialog = _dialog(application, "fr", 16)
    try:
        dialog.show()
        _settle(application)
        dialog.resize(dialog.width() * 2, dialog.height() // 2)
        _settle(application)
        chosen = QSize(dialog.size())
        scroll = dialog._scroll
        content = scroll.widget()
        # Echter Text liegt im gemessenen Layout. Eine Mindesthöhe allein am
        # Container wäre kein natürlicher Höhenwunsch dieses Inhalts.
        dialog.places.setText("\n".join([dialog.places.text()] * 3))
        if wide_content:
            dialog.places.setMinimumWidth(scroll.maximumViewportSize().width() * 2)
        scroll.setHorizontalScrollBarPolicy(horizontal_policy)
        _settle(application)
        required_height = dialog._body.totalHeightForWidth(content.width())
        assert content.width() >= scroll.viewport().width()
        assert required_height >= content.minimumSizeHint().height()
        assert dialog.places.height() >= dialog.places.heightForWidth(dialog.places.width())
        assert scroll.verticalScrollBar().maximum() > 0
        assert (scroll.horizontalScrollBar().maximum() > 0) == wide_content
        assert scroll.horizontalScrollBar().isVisibleTo(dialog) == (
            wide_content or horizontal_policy == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        assert _hidden_height(scroll) == required_height - scroll.viewport().height()
        assert dialog.size() == chosen
        assert dialog._height.user == chosen
        assert dialog.rect().contains(dialog._buttons.geometry())
    finally:
        _close(dialog)
