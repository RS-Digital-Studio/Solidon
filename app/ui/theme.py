"""Helles und dunkles Thema (Bauplan §19.3).

Beide Themen werden hier gebaut statt der Plattform überlassen, denn Kontrast
ist Teil des Produkts: Viewport, Analysekarten und Differenzansicht setzen alle
ein bekanntes Hintergrundbild voraus. Farben, die Bedeutung tragen, leben in
``palette.py``; was hier steht, ist nur der Rahmen darum.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

Theme = Literal["dark", "light"]

#: Window, panel and text colours per theme, contrast checked against WCAG AA.
THEMES: dict[Theme, dict[str, str]] = {
    "dark": {
        "window": "#23272e",
        "base": "#1b1f25",
        "alternate": "#262b33",
        "text": "#e6e9ee",
        "disabled": "#7c848f",
        "highlight": "#3d6ea5",
        "highlight_text": "#ffffff",
        "tooltip": "#2c323c",
        "viewport_bottom": "#20242b",
        "viewport_top": "#2c323c",
        "object": "#b9c4d0",
        "bed": "#5a6472",
    },
    "light": {
        "window": "#f2f3f5",
        "base": "#ffffff",
        "alternate": "#e9ebee",
        "text": "#1c2026",
        "disabled": "#8b929b",
        "highlight": "#2f6fb0",
        "highlight_text": "#ffffff",
        "tooltip": "#ffffe1",
        "viewport_bottom": "#dfe3e8",
        "viewport_top": "#f4f6f8",
        "object": "#7d8894",
        "bed": "#9aa3ae",
    },
}


def build_palette(theme: Theme) -> QPalette:
    colours = THEMES[theme]
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colours["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colours["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colours["base"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colours["alternate"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colours["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colours["window"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colours["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colours["tooltip"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colours["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colours["highlight"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colours["highlight_text"]))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(colours["disabled"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(colours["disabled"])
    )
    return palette


def apply_theme(application: QApplication, theme: Theme) -> None:
    """Switch the whole application over. Takes effect immediately."""
    application.setStyle("Fusion")
    application.setPalette(build_palette(theme))


def viewport_colours(theme: Theme) -> dict[str, str]:
    """Die Farben, die die 3D-Ansicht braucht — Hintergrundverlauf, Körper,
    Druckplatte.
    """
    colours = THEMES[theme]
    return {
        "bottom": colours["viewport_bottom"],
        "top": colours["viewport_top"],
        "object": colours["object"],
        "bed": colours["bed"],
    }


def relative_luminance(colour: str) -> float:
    """WCAG-Luminanz — die Grundlage der Kontrastprüfung in den Tests."""
    channels = []
    for value in (colour[1:3], colour[3:5], colour[5:7]):
        component = int(value, 16) / 255.0
        channels.append(
            component / 12.92 if component <= 0.03928 else ((component + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: str, second: str) -> float:
    """Kontrast zwischen zwei Farben, 1 (keiner) bis 21 (schwarz auf weiß)."""
    lighter = max(relative_luminance(first), relative_luminance(second))
    darker = min(relative_luminance(first), relative_luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


#: Qt attributes for HiDPI. Set before the application exists (§19.3).
def enable_hidpi() -> None:
    """HiDPI-Skalierung mit scharfen Pixmaps — muss vor QApplication laufen."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
