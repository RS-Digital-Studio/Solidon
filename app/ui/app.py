"""Application entry point for the desktop surface (Bauplan §38).

Starts logging, fills the registry, installs the language catalog and opens the
window. Nothing here computes; everything that does lives in ``app.core``.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.branding import APP_ID, APP_NAME, APP_VERSION
from app.core.bootstrap import load_operations
from app.core.log import configure, get_logger
from app.i18n import set_language
from app.i18n.catalog import install_language
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import load_settings
from app.ui.theme import apply_theme, enable_hidpi

_log = get_logger(__name__)


def build_application(argv: list[str] | None = None) -> tuple[QApplication, MainWindow]:
    """Assemble application and window without starting the event loop."""
    enable_hidpi()
    application = QApplication.instance() or QApplication(argv or sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationDomain(APP_ID)

    settings = load_settings()
    install_language(settings.language)
    set_language(settings.language)

    apply_theme(application, settings.theme)  # type: ignore[arg-type]

    session = Session()
    window = MainWindow(session, settings)
    window.viewport.set_navigation(settings.navigation)  # type: ignore[arg-type]
    window.viewport.set_theme(settings.theme)
    return application, window  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    configure(to_console=False)
    load_operations()
    application, window = build_application(argv)
    window.show()
    # The first run and the update notice belong after the window is visible
    # (§38) — and only here, where a person is actually looking at it.
    window.start()
    _log.info("%s %s started", APP_NAME, APP_VERSION)
    return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
