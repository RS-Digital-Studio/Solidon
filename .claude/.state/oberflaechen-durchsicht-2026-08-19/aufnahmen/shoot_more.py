"""Die großen Flächen aufnehmen, die im Handbuch nicht vorkommen.

Druckeinstellungen, Chat im leeren Zustand, Generierungsdialog, Bausteinkatalog
in kleinerem Fenster, Befehlspalette. Alles in natürlicher Größe, damit
Leerraum und Gedrängtes echt sind.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def settle(app: QApplication, rounds: int = 20) -> None:
    for _ in range(rounds):
        app.processEvents()


def shoot(widget, key: str) -> None:
    widget.grab().save(str(OUT / f"{key}.png"))
    hint = widget.sizeHint()
    print(f"{key}: gezeigt {widget.width()}x{widget.height()} sizeHint {hint.width()}x{hint.height()}")


def natural(widget, size=None):
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    if size is None:
        widget.adjustSize()
    else:
        widget.resize(*size)
    widget.show()
    return widget


def main() -> int:
    from app.i18n import set_language
    from app.ui.app import install_qt_translations
    from app.ui.theme import apply_theme, enable_hidpi

    enable_hidpi()
    app = QApplication(sys.argv)
    set_language("de")
    install_qt_translations(app, "de")
    apply_theme(app, "dark")

    from app.core.bootstrap import load_operations

    load_operations()

    # Chat im leeren Zustand.
    from app.ui.chat import ChatPanel

    try:
        chat = natural(ChatPanel(), (420, 640))
        settle(app)
        shoot(chat, "chat-leer")
        chat.close()
    except Exception as error:  # pragma: no cover - Aufnahme, kein Test
        print(f"chat: {type(error).__name__}: {error}")

    # Generierungsdialog.
    from app.ui.generate_dialog import GenerateDialog

    try:
        generate = natural(GenerateDialog())
        settle(app)
        shoot(generate, "generate")
        generate.close()
    except Exception as error:
        print(f"generate: {type(error).__name__}: {error}")

    # Befehlspalette.
    from app.ui.command_palette import CommandPalette

    try:
        palette = natural(CommandPalette([]))
        settle(app)
        shoot(palette, "palette")
        palette.close()
    except Exception as error:
        print(f"palette: {type(error).__name__}: {error}")

    # Katalog in einem realistischen Fenster.
    from app.ui.catalog import PartCatalog

    try:
        catalog = natural(PartCatalog(), (900, 620))
        settle(app, 40)
        shoot(catalog, "katalog-900")
        catalog.close()
    except Exception as error:
        print(f"katalog: {type(error).__name__}: {error}")

    # Startbildschirm in einem kleinen Fenster — was sieht jemand mit 1366x768?
    from app.ui.start_screen import StartScreen

    try:
        start = natural(StartScreen(), (1180, 700))
        settle(app, 30)
        shoot(start, "start-1180")
        start.close()
    except Exception as error:
        print(f"start: {type(error).__name__}: {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
