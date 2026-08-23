"""Einstiegspunkt der Desktop-Oberfläche (Bauplan §38).

Startet das Protokoll, füllt das Register, installiert den Sprachkatalog und
öffnet das Fenster. Nichts hier rechnet; alles, was rechnet, lebt in
``app.core``.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QByteArray,
    QCoreApplication,
    QEvent,
    QLibraryInfo,
    QLocale,
    QObject,
    QTranslator,
)
from PySide6.QtGui import QFileOpenEvent
from PySide6.QtWidgets import QApplication

from app.branding import APP_ID, APP_NAME, APP_VERSION
from app.core import activation
from app.core.bootstrap import load_operations, load_user_parts
from app.core.log import configure, get_logger
from app.i18n import set_language, tr
from app.i18n.catalog import install_language
from app.ui.icons import application_icon
from app.ui.settings import load_settings
from app.ui.splash import SplashScreen
from app.ui.theme import apply_theme, enable_hidpi

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

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


def requested_file(argv: list[str]) -> Path | None:
    """Die Datei, die beim Start mitkam — oder ``None``.

    Unter Windows und Linux ist das der ganze Mechanismus hinter einer
    Dateizuordnung: Ein Doppelklick auf ein Projekt startet die Anwendung mit
    dessen Pfad als Argument. Bis hierher wurde er an ``QApplication``
    weitergereicht und dort verworfen — die Zuordnung, die der Menüeintrag
    unter Linux längst versprach, ging ins Leere.

    Genommen wird die erste Angabe, die keine Option ist und die es gibt. Was
    es nicht gibt, wird protokolliert und übergangen: Ein leeres Fenster ist
    die bessere Antwort auf einen Tippfehler als eine Fehlermeldung vor dem
    ersten Blick auf das Programm.
    """
    for entry in argv[1:]:
        if entry.startswith("-"):
            continue
        candidate = Path(entry)
        if candidate.is_file():
            return candidate
        # Zwei Fälle, zwei Sätze: „gibt es nicht" ist die falsche Auskunft über
        # ein Verzeichnis, das es sehr wohl gibt — und wer im Protokoll danach
        # sucht, warum sein Doppelklick nichts tat, liest genau diese Zeile.
        if candidate.exists():
            _log.warning("what was given on the command line is not a file: %s", entry)
        else:
            _log.warning("file given on the command line does not exist: %s", entry)
    return None


class FileOpenListener(QObject):
    """Öffnet, was der Finder der laufenden Anwendung zuschickt.

    **Nur macOS schickt es.** Dort startet ein Doppelklick keine zweite
    Anwendung mit einem Argument, sondern sendet der schon laufenden ein
    ``QFileOpenEvent`` — auch dann, wenn sie gerade erst durch diesen
    Doppelklick gestartet wurde. Ohne diesen Filter bliebe die Zuordnung im
    Bundle ein Eintrag ohne Wirkung, und der Nutzer sähe ein leeres Fenster.

    Auf den anderen Systemen kostet der Filter einen Vergleich je Ereignis und
    tut sonst nichts.
    """

    def __init__(self, window: MainWindow, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt gibt den Namen
        if isinstance(event, QFileOpenEvent):
            # Beide Felder können leer sein, und ``Path("")`` ist ``Path(".")``
            # — die Warnung meldete dann „.", was niemandem sagt, dass gar
            # nichts mitkam.
            named = event.file() or event.url().toLocalFile()
            if not named:
                _log.warning("open event came without a file")
                return True
            path = Path(named)
            if path.is_file():
                self._window.open_path(path)
            else:
                _log.warning("open event names something that is not a file: %s", path)
            return True
        return super().eventFilter(watched, event)


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

    # Erst hier und nicht oben im Modulkopf: Der Import von ``main_window``
    # zieht ``app.core.scene`` und damit trimesh und networkx nach, und das
    # sind gemessen 2,2 der 2,4 Sekunden, die ``import app.ui.app`` kostete —
    # vergangen, **bevor** der Ladebildschirm überhaupt gebaut werden konnte.
    # Ein leerer Bildschirm ist nach §2.8 ab zwei Sekunden keine Anzeige.
    # Jetzt liegt die Zeit hinter dem Ladebildschirm, unter der Zeile
    # „Operationen werden geladen …", die sie ohnehin schon beschrieb.
    from app.ui.main_window import MainWindow
    from app.ui.session import Session

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
    # **Das Thema, bevor irgendetwas zu sehen ist.** Gesetzt hat es bisher erst
    # ``build_application`` — und dazwischen liegen der Ladebildschirm und das
    # Laden der Operationen. Gemessen: die Palette steht dort auf dem
    # Systemgrau #efefef, danach auf #343a45, und zwischen beiden liegen knapp
    # drei Sekunden. Der erste Eindruck war ein hellgrauer Kasten, der mitten
    # im Laden die Farbe wechselt. Dieselbe Zeile deckt den Abschiedsdialog
    # einer abgelaufenen Demo darunter ab: der wäre sonst das einzige Fenster
    # dieses Starts gewesen — und ungefärbt. ``build_application`` setzt es
    # danach noch einmal; das kostet nichts und bleibt die Stelle, an der ein
    # Themenwechsel im Betrieb ankommt.
    apply_theme(application, settings.theme)  # type: ignore[arg-type]
    state = activation.state()
    if state.over:
        # Auch dieser Import ist schwer (``app.core.scene`` über
        # ``app.ui.dialogs``), und er gilt für einen von hundert Starts. Wer
        # eine laufende Demo hat, soll ihn nicht bezahlen.
        from app.ui.dialogs import show_expired_demo

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

    # Was per Doppelklick oder von der Kommandozeile mitkam, wird geöffnet —
    # nach ``start()``, damit der erste Start seine Fragen zuerst stellt.
    opening = requested_file(argv or sys.argv)
    if opening is not None:
        window.open_path(opening)
    # Auf dem Mac kommt die Datei nicht über argv: Der Finder schickt der
    # laufenden Anwendung ein Ereignis, und ohne diesen Filter fällt es unter
    # den Tisch — die Zuordnung im Bundle wäre dort ein Versprechen ohne
    # Wirkung.
    application.installEventFilter(FileOpenListener(window, application))

    # **Und die Gegenzeile dazu.** Bis zum 23.08.2026 vermerkte das Protokoll
    # den Start und über das Ende nichts — damit sehen ein Absturz, ein
    # abgeschossener Prozess und ein normales Beenden gleich aus, nämlich wie
    # nichts. Im Protokoll des ersten Kunden mit 0.1.3 steht dreimal „started",
    # zweimal davon binnen einer Minute und jedes Mal gefolgt von der
    # Wiederherstellungsfrage; ob dort etwas abgestürzt ist, war nicht zu
    # beantworten.
    #
    # ``aboutToQuit`` und nicht ``closeEvent``: Das Signal feuert genau dann,
    # wenn die Ereignisschleife ordentlich endet — bei einem Absturz nicht, und
    # dann ist die **fehlende** Zeile die Aussage. Der ``closeEvent`` eines
    # Fensters taugt dafür nicht: In der Suite laufen siebenhundert davon, und
    # ein Fenster ist nicht die Anwendung.
    application.aboutToQuit.connect(
        lambda: _log.info("%s %s ended normally", APP_NAME, APP_VERSION)
    )

    _log.info("%s %s started", APP_NAME, APP_VERSION)
    return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
