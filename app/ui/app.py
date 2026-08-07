"""Einstiegspunkt der Desktop-Oberfläche (Bauplan §38).

Startet das Protokoll, füllt das Register, installiert den Sprachkatalog und
öffnet das Fenster. Nichts hier rechnet; alles, was rechnet, lebt in
``app.core``.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from app.branding import APP_ID, APP_NAME, APP_VERSION
from app.core.bootstrap import load_operations
from app.core.log import configure, get_logger
from app.i18n import set_language, tr
from app.i18n.catalog import install_language
from app.ui.icons import application_icon
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import load_settings
from app.ui.splash import SplashScreen
from app.ui.theme import apply_theme, enable_hidpi

_log = get_logger(__name__)


def install_qt_translations(application: QCoreApplication, language: str) -> QTranslator | None:
    """Bringt Qt selbst die Anwendungssprache bei.

    Die Standardknöpfe (OK, Abbrechen, Schließen) beschriftet Qt aus seinem
    eigenen Katalog. Ohne ihn stand auf jedem zweiten Dialog „Cancel" — und
    der Sprachtest sah es nicht, weil es keine eigene Zeichenkette ist
    (Regel 20 dem Geist nach, nicht dem Buchstaben).
    """
    # Dieselbe Sprache auch für Zahlen und Daten: die Eingabefelder schreiben
    # ihr Dezimaltrennzeichen aus QLocale, und ohne diese Zeile käme es vom
    # Betriebssystem. Auf einem deutschen Windows mit englischer Oberfläche
    # stünden dann Komma im Feld und Punkt im Text daneben.
    QLocale.setDefault(QLocale(language))

    translator = QTranslator(application)
    directory = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if not translator.load(QLocale(language), "qtbase", "_", directory):
        _log.warning("no qtbase translation for %s in %s", language, directory)
        return None
    application.installTranslator(translator)
    return translator


def build_application(
    argv: list[str] | None = None,
    progress: Callable[[str, float], None] | None = None,
) -> tuple[QApplication, MainWindow]:
    """Baut Anwendung und Fenster zusammen, ohne die Ereignisschleife zu
    starten.

    ``progress`` bekommt nach jedem Abschnitt Text und Anteil — der
    Ladebildschirm hängt daran. Ohne ihn verhält sich alles wie zuvor; die
    Suite baut die Anwendung so, und ein Fenster, das nur für einen Test
    entsteht, braucht kein Startbild.
    """

    def report(text: str, done: float) -> None:
        if progress is not None:
            progress(text, done)

    enable_hidpi()
    existing = QApplication.instance()
    application = existing if isinstance(existing, QApplication) else QApplication(argv or sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationDomain(APP_ID)
    application.setWindowIcon(application_icon())

    report(tr("Einstellungen werden gelesen …"), 0.45)
    settings = load_settings()
    install_language(settings.language)
    set_language(settings.language)
    install_qt_translations(application, settings.language)

    report(tr("Das Erscheinungsbild wird gesetzt …"), 0.6)
    apply_theme(application, settings.theme)  # type: ignore[arg-type]

    report(tr("Das Fenster wird aufgebaut …"), 0.72)
    session = Session()
    window = MainWindow(session, settings)
    # Eine Stelle für alle gespeicherten Werte. Vorher standen hier zwei, und
    # die Anzeigeeinheit und die Differenzpalette gehörten zu den Einstellungen,
    # die niemand las (§19.3).
    window._apply_settings()
    return application, window


def main(argv: list[str] | None = None) -> int:
    configure(to_console=False)

    # Qt muss vor dem Ladebildschirm stehen, und das Register danach: sonst
    # sieht niemand die Sekunden, die das Füllen des Registers kostet. Deshalb
    # ist ``load_operations`` hierher gewandert und läuft nicht mehr vor
    # ``build_application``.
    enable_hidpi()
    existing = QApplication.instance()
    application = existing if isinstance(existing, QApplication) else QApplication(argv or sys.argv)
    application.setWindowIcon(application_icon())

    splash = SplashScreen()
    splash.show()
    splash.step(tr("Operationen werden geladen …"), 0.12)
    load_operations()

    application, window = build_application(argv, progress=splash.step)
    splash.step(tr("Bereit."), 1.0)

    window.show()
    splash.finish(window)
    # Der erste Start und der Update-Hinweis gehören hinter das sichtbare
    # Fenster (§38) — und nur hierher, wo wirklich ein Mensch hinsieht.
    window.start()
    _log.info("%s %s started", APP_NAME, APP_VERSION)
    return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
