"""Der Kontrastprüfer liest die gezeichnete Schrift eines Hauptknopfs samt Zustand."""

from collections import Counter
from types import SimpleNamespace

import pytest

from tests.bundled_fonts import bundled_font
from tools import function_capture
from tools.function_judges import CRITERION_JUDGES
from tools.function_samples import sample_context


@pytest.fixture
def styled_app(qt_app):
    """Gebündelte Sans in 12 pt; Schrift und Thema gibt ``conftest.py`` zurück."""
    with bundled_font(qt_app, 12):
        yield qt_app


def _button(qt_app, theme):
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from app.ui.style import apply_style
    from app.ui.theme import apply_theme

    font = QFont(qt_app.font())
    font.setPointSize(12)
    qt_app.setFont(font)
    apply_theme(qt_app, theme)
    apply_style(qt_app, theme)
    root = QWidget()
    button = QPushButton("Auf das Bett setzen", root)
    button.setAutoDefault(False)
    QVBoxLayout(root).addWidget(button)
    root.resize(360, 90)
    root.show()
    qt_app.processEvents()
    return root, button


def _entry(root, theme):
    entries = function_capture.contrast_entries(root, theme)
    assert len(entries) == 1
    return entries[0]


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_primary_text_colour_matches_the_painted_button_and_survives_role_changes(
    styled_app, theme
):
    """Dunkel macht den falschen Palettenwert sichtbar; normal/primär/normal bleibt messbar."""
    from app.ui.style import make_primary
    from app.ui.theme import THEMES, contrast_ratio

    qt_app = styled_app
    root, button = _button(qt_app, theme)
    try:
        for primary in (False, True, False):
            make_primary(button, leading=primary)
            qt_app.processEvents()
            entry = _entry(root, theme)
            expected = THEMES[theme]["highlight_text" if primary else "text"]
            assert entry["foreground"] == expected
            image = button.grab().toImage()
            colours = Counter(
                image.pixelColor(x, y).name()
                for y in range(image.height())
                for x in range(image.width())
            )
            assert colours[expected] > 0, (
                "Der behauptete Vordergrund muss im wirklichen Knopfbild stehen"
            )
            assert contrast_ratio(entry["foreground"], entry["background"]) >= 4.5
            assert (
                CRITERION_JUDGES["G6"]({"contrast": [entry]}, sample_context()).verdict
                == "erfuellt"
            )
    finally:
        root.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("pressed", [False, True])
def test_primary_text_colour_keeps_a_deliberately_bad_state_colour(styled_app, theme, pressed):
    """Eine falsche tatsächliche Farbe darf nicht durch die gute Themenrolle ersetzt werden."""
    from app.ui.style import make_primary

    qt_app = styled_app
    root, button = _button(qt_app, theme)
    try:
        make_primary(button)
        button.setStyleSheet(
            "QPushButton:default { color: #f0a54a; background: #f0a54a; }"
            "QPushButton:default:pressed { color: #808080; background: #808080; }"
        )
        button.setDown(pressed)
        qt_app.processEvents()
        entry = _entry(root, theme)
        expected = "#808080" if pressed else "#f0a54a"
        assert entry["foreground"] == expected
        assert entry["background"] == expected
        assert CRITERION_JUDGES["G6"]({"contrast": [entry]}, sample_context()).verdict == "fund"
    finally:
        root.close()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_primary_text_colour_reads_the_actual_hover_state(styled_app, theme):
    """Eine nur beim Überfahren falsche Schriftfarbe bleibt ein wirklicher Fund."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    from app.ui.style import make_primary

    qt_app = styled_app
    root, button = _button(qt_app, theme)
    try:
        make_primary(button)
        button.setStyleSheet("QPushButton:default:hover { color: #808080; background: #808080; }")
        window = root.windowHandle()
        assert window is not None
        QTest.mouseMove(window, QPoint(1, 1))
        qt_app.processEvents()
        assert not button.underMouse()
        resting = _entry(root, theme)
        assert (
            CRITERION_JUDGES["G6"]({"contrast": [resting]}, sample_context()).verdict == "erfuellt"
        )
        QTest.mouseMove(window, button.mapTo(root, button.rect().center()))
        qt_app.processEvents()
        assert button.underMouse()
        hovered = _entry(root, theme)
        assert hovered["foreground"] == hovered["background"] == "#808080"
        assert CRITERION_JUDGES["G6"]({"contrast": [hovered]}, sample_context()).verdict == "fund"
    finally:
        root.close()


def test_primary_colour_without_full_text_pixels_stays_unmeasured(styled_app):
    """Halbtransparente Glyphen liefern keinen erfundenen voll gedeckten Farbwert."""
    from app.ui.style import make_primary

    qt_app = styled_app
    root, button = _button(qt_app, "dark")
    try:
        make_primary(button)
        button.setStyleSheet("QPushButton:default { color: rgba(240, 165, 74, 128); }")
        qt_app.processEvents()
        entry = _entry(root, "dark")
        assert entry["foreground"] is None
        assert entry["background"] is not None
        assert (
            CRITERION_JUDGES["G6"]({"contrast": [entry]}, sample_context()).verdict
            == "nicht_gelaufen"
        )
    finally:
        root.close()


def test_primary_text_colour_does_not_read_the_icon_as_the_label(styled_app):
    """Eine große andersfarbige Symbolfläche ist kein Schriftfarbbeleg."""
    from PySide6.QtGui import QColor, QIcon, QPixmap

    from app.ui.style import make_primary
    from app.ui.theme import THEMES

    qt_app = styled_app
    root, button = _button(qt_app, "dark")
    try:
        make_primary(button)
        icon = QPixmap(32, 32)
        icon.fill(QColor("#ff00ff"))
        button.setIcon(QIcon(icon))
        qt_app.processEvents()
        assert _entry(root, "dark")["foreground"] == THEMES["dark"]["highlight_text"]
    finally:
        root.close()


@pytest.mark.parametrize("missing", ["null", "outside"])
def test_primary_text_colour_does_not_rescue_missing_native_pixels(
    styled_app, monkeypatch, missing
):
    """Der richtige Stil ersetzt niemals den nicht aufgenommenen Kundenhintergrund."""
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from app.ui.style import make_primary

    qt_app = styled_app
    root, button = _button(qt_app, "dark")
    try:
        make_primary(button)
        qt_app.processEvents()
        picture = QImage() if missing == "null" else QImage(1, 1, QImage.Format.Format_RGB32)
        monkeypatch.setattr(QApplication, "platformName", lambda: "windows")
        monkeypatch.setattr(root, "winId", lambda: 42)
        monkeypatch.setattr(
            root,
            "screen",
            lambda: SimpleNamespace(
                grabWindow=lambda handle: SimpleNamespace(toImage=lambda: picture)
            ),
        )
        entry = _entry(root, "dark")
        assert entry["background"] is None
        outcome = CRITERION_JUDGES["G6"]({"contrast": [entry]}, sample_context())
        assert outcome.verdict == "nicht_gelaufen"
    finally:
        root.close()


def test_disabled_primary_does_not_enter_the_contrast_sample(styled_app):
    """Der bestehende Ausschluss gesperrter Bedienelemente bleibt erhalten."""
    from app.ui.style import make_primary

    qt_app = styled_app
    root, button = _button(qt_app, "dark")
    try:
        make_primary(button)
        button.setEnabled(False)
        qt_app.processEvents()
        assert function_capture.contrast_entries(root, "dark") == []
    finally:
        root.close()
