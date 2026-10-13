"""Die Kontrastprobe liest native Pixel, ohne das Fenster erneut zu rendern."""

from types import SimpleNamespace

import pytest

from tools import function_capture


def test_contrast_reads_the_native_window_without_widget_grab(monkeypatch):
    """Ein Hauptfenster mit Renderer darf nicht per QWidget.grab neu gezeichnet werden."""
    from PySide6.QtWidgets import QApplication

    monkeypatch.setattr(QApplication, "platformName", lambda: "windows")
    seen = []
    image = object()
    screen = SimpleNamespace(
        grabWindow=lambda handle: seen.append(handle) or SimpleNamespace(toImage=lambda: image)
    )
    window = SimpleNamespace(winId=lambda: 42, screen=lambda: screen)
    root = SimpleNamespace(window=lambda: window, findChildren=lambda kind: [])
    assert function_capture.contrast_entries(root, "light") == []
    assert seen == [42]


@pytest.mark.parametrize("ratio", [1.0, 1.5, 2.0])
@pytest.mark.parametrize("origin", [(-1920, -900), (3413, 78)])
def test_background_samples_window_local_pixels_at_the_image_ratio(ratio, origin):
    """Monitorversatz darf nicht zu fensterlokalen Pixeln addiert werden."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QColor, QImage, QRegion

    top = SimpleNamespace(pos=lambda: QPoint(*origin))
    picture = QImage(int(100 * ratio), int(80 * ratio), QImage.Format.Format_RGB32)
    picture.setDevicePixelRatio(ratio)
    picture.fill(QColor("#ff0000"))
    for y in range(int(20 * ratio), int(40 * ratio)):
        for x in range(int(30 * ratio), int(60 * ratio)):
            picture.setPixelColor(x, y, QColor("#123456"))

    def mapped(parent, point):
        assert parent is top
        return QPoint(30, 20) + point

    widget = SimpleNamespace(
        width=lambda: 30,
        height=lambda: 20,
        visibleRegion=lambda: QRegion(QRect(0, 0, 30, 20)),
        mapTo=mapped,
    )
    assert function_capture._shown_background(picture, top, widget) == "#123456"
    # Ein falscher Ursprung bzw. eine andere Fläche darf nicht dieselbe Farbe liefern.
    widget.mapTo = lambda parent, point: QPoint(0, 0)
    assert function_capture._shown_background(picture, top, widget) == "#ff0000"


@pytest.mark.parametrize("missing", ["null", "outside"])
def test_background_without_sampled_pixels_is_missing(missing):
    """Weder ein leeres Bild noch ein Träger außerhalb seiner Pixel liefert eine Farbe."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QImage, QRegion

    picture = QImage() if missing == "null" else QImage(5, 5, QImage.Format.Format_RGB32)
    widget = SimpleNamespace(
        width=lambda: 20,
        height=lambda: 20,
        visibleRegion=lambda: QRegion(QRect(0, 0, 20, 20)),
        mapTo=lambda parent, point: QPoint(100, 100) + point,
    )
    assert function_capture._shown_background(picture, object(), widget) is None


@pytest.mark.parametrize("colour", [None, "#000000", "#ffffff"])
def test_native_image_failure_stays_open_in_the_real_widget_judgement(qt_app, monkeypatch, colour):
    """Echter Textträger, injiziertes natives Bild, echter G6-Richter samt Negativkontrolle."""
    from PySide6.QtGui import QColor, QImage, QPalette
    from PySide6.QtWidgets import QApplication, QLabel, QWidget

    from tools.function_judges import CRITERION_JUDGES
    from tools.function_samples import sample_context

    root = QWidget()
    root.resize(220, 80)
    label = QLabel("Messbarer Text", root)
    label.setGeometry(10, 10, 180, 30)
    palette = label.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#000000"))
    label.setPalette(palette)
    root.show()
    qt_app.processEvents()
    picture = QImage() if colour is None else QImage(220, 80, QImage.Format.Format_RGB32)
    if colour:
        picture.fill(QColor(colour))
    monkeypatch.setattr(QApplication, "platformName", lambda: "windows")
    monkeypatch.setattr(root, "winId", lambda: 42)
    monkeypatch.setattr(
        root,
        "screen",
        lambda: SimpleNamespace(grabWindow=lambda handle: SimpleNamespace(toImage=lambda: picture)),
    )
    pairs = function_capture.contrast_entries(root, "light")
    outcome = CRITERION_JUDGES["G6"]({"contrast": pairs}, sample_context())
    assert len(pairs) == 1
    assert pairs[0]["background"] == colour
    assert (outcome.verdict == "erfuellt") is (colour == "#ffffff")
    assert bool(outcome.issues) is (colour == "#000000")
    root.close()
