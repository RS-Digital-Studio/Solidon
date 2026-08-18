"""Einstiegspunkt der Desktop-Oberfläche (Bauplan §38).

Startet das Protokoll, füllt das Register, installiert den Sprachkatalog und
öffnet das Fenster. Nichts hier rechnet; alles, was rechnet, lebt in
``app.core``.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from PySide6.QtCore import QByteArray, QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from app.branding import APP_ID, APP_NAME, APP_VERSION
from app.core import activation
from app.core.bootstrap import load_operations, load_user_parts
from app.core.log import configure, get_logger
from app.i18n import set_language, tr
from app.i18n.catalog import install_language
from app.ui.dialogs import show_expired_demo
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

    # Vor allem anderen: eine abgelaufene Demo startet nicht mehr
    # (Demo-Konzept §2 B2). Die Sprache muss dafür schon stehen — diese
    # Meldung ist womöglich das Einzige, was dieser Start noch zeigt, und
    # sie auf Deutsch zu zeigen, weil der Katalog erst später kommt, wäre
    # ausgerechnet beim Abschied der falsche Ton.
    settings = load_settings()
    install_language(settings.language)
    set_language(settings.language)
    install_qt_translations(application, settings.language)
    state = activation.state()
    if state.over:
        _log.info("demo ended on %s, not starting", state.deadline)
        show_expired_demo(state)
        # Kein Erfolg und kein Fehler: die Anwendung hat nicht gearbeitet, und
        # ein Skript, das sie aufruft, soll das an der Rückgabe sehen.
        return 1

    splash = SplashScreen()
    splash.show()
    splash.step(tr("Operationen werden geladen …"), 0.12)
    load_operations()
    # Die eigenen Bausteine des Nutzers, nach der Bibliothek (§24.5). Ihre
    # Befunde — eine Datei, die sich nicht laden ließ — gehören in den
    # Prüfbericht, sobald es ihn gibt.
    user_findings = load_user_parts()

    application, window = build_application(argv, progress=splash.step)
    if user_findings:
        window.report.add_findings(list(user_findings))
    splash.step(tr("Bereit."), 1.0)

    # Bildschirmfüllend, aber ein Fenster: Titelleiste, Menüs und die Knöpfe
    # zum Verkleinern bleiben da. Echtes Vollbild nimmt sie weg, und wer dann
    # eine zweite Anwendung danebenlegen will, findet keinen Griff.
    #
    # Und nicht bloß 1280 auf 820 wie die Vorgabe des Fensters: Objektbaum,
    # Viewport und Prüfbericht nebeneinander brauchen Breite — auf einem
    # 2560er Schirm stünde die Anwendung sonst als Briefmarke in der Ecke.
    #
    # Maximiert ist die Vorgabe für den **ersten** Start. Danach zählt, wie
    # das Fenster verlassen wurde: wer es verkleinert und schließt, fand es
    # beim nächsten Start wieder bildschirmfüllend — als hätte er nichts
    # gesagt.
    if settings.window_geometry:
        window.restoreGeometry(QByteArray.fromHex(settings.window_geometry.encode("ascii")))
        window.show()
    else:
        window.showMaximized()
    splash.finish(window)
    # Der erste Start und der Update-Hinweis gehören hinter das sichtbare
    # Fenster (§38) — und nur hierher, wo wirklich ein Mensch hinsieht.
    window.start()
    _log.info("%s %s started", APP_NAME, APP_VERSION)
    return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
