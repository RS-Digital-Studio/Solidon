"""Sieht ein gesperrtes Bedienelement gesperrt aus? Referenzvergleich.

Nicht ansehen und schätzen, sondern beides im selben Widget rendern und die
Bildpunkte vergleichen — die Lehre aus dem Komma-Fund im ROADMAP.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


def build(enabled: bool, theme: str) -> QWidget:
    host = QWidget()
    layout = QVBoxLayout(host)
    slider = QSlider(Qt.Orientation.Horizontal, host)
    slider.setRange(0, 100)
    slider.setValue(50)
    bar = QProgressBar(host)
    bar.setValue(60)
    button = QPushButton("Jetzt trennen", host)
    check = QCheckBox("Scheibe", host)
    label = QLabel("0,0 mm", host)
    for widget in (slider, bar, button, check, label):
        widget.setEnabled(enabled)
        layout.addWidget(widget)
    host.resize(220, 200)
    return host


def colours(widget: QWidget) -> dict[str, int]:
    image = widget.grab().toImage()
    tally: dict[str, int] = {}
    for y in range(image.height()):
        for x in range(image.width()):
            name = QColor(image.pixel(x, y)).name()
            tally[name] = tally.get(name, 0) + 1
    return tally


def main() -> int:
    from app.ui.theme import apply_theme, contrast_ratio, enable_hidpi

    enable_hidpi()
    app = QApplication(sys.argv)

    for theme in ("dark", "light"):
        apply_theme(app, theme)
        report: dict[bool, dict[str, int]] = {}
        for enabled in (True, False):
            host = build(enabled, theme)
            host.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            host.show()
            for _ in range(10):
                app.processEvents()
            host.grab().save(str(OUT / f"disabled-{theme}-{'an' if enabled else 'aus'}.png"))
            report[enabled] = colours(host)
            host.close()

        accent = QColor(app.palette().highlight().color()).name()
        an = report[True].get(accent, 0)
        aus = report[False].get(accent, 0)
        print(f"{theme}: Akzent {accent} — bedienbar {an} Punkte, gesperrt {aus} Punkte")
        if aus > 0:
            print("   der Akzent bleibt im gesperrten Zustand stehen")
        # Und der Kontrast der gesperrten Schrift
        palette = app.palette()
        text = palette.color(palette.ColorGroup.Disabled, palette.ColorRole.WindowText).name()
        window = palette.color(palette.ColorRole.Window).name()
        print(f"   gesperrte Schrift {text} auf {window}: {contrast_ratio(text, window):.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
