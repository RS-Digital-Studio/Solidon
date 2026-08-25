"""Die Belegbilder der Website aus der laufenden Oberfläche schneiden.

    .venv\\Scripts\\python.exe tools/make_web_images.py

Die Startseite belegt ihre Behauptungen mit Bildern. Für den Prüfbericht reicht
das Handbuchbild — die Seite verweist einfach darauf. Für den Bausteinkatalog
nicht: In halber Spaltenbreite wird aus einem Dialog von 1560 Bildpunkten ein
Bild, auf dem niemand mehr liest, wie die Teile heißen.

Gezeigt werden deshalb zwei Gruppen als Bänder untereinander — acht der
siebzehn Bausteine, jeder mit Vorschau und seinen Maßen. Das war bis hierher
von Hand montiert, mit den Folgen, die Handarbeit hat: Die untere Zeile war
abgeschnitten, rechts stand ein Streifen Rollbalken im Bild, und als der
Katalog seine Gruppen neu umbrach, stimmte nichts mehr. Ein Bild, das niemand
nachziehen kann, ist so alt wie der Tag, an dem es entstand.

Geschnitten wird nicht nach Augenmaß, sondern nach den Kachelrechtecken, die
die Liste selbst kennt (``visualItemRect``). Damit sitzt der Schnitt in jeder
Sprache richtig — die Beschriftungen sind unterschiedlich lang, und was auf
Deutsch in eine Zeile passt, braucht auf Französisch zwei.

Dieselben zwei Fallen wie bei ``make_figures.py``, aus denselben Gründen: Es
läuft **nicht** offscreen (dort hat Qt hier keine Schriften), und es ist kein
Testlauf — die Suite prüft, dass die Dateien da sind, nicht wie sie aussehen.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Auch der eigene Ordner: ``make_figures`` liegt daneben und ist kein Paket.
sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import make_figures as figures
from PySide6.QtCore import QEventLoop, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.i18n import SOURCE_LANGUAGE, install_catalog, set_language
from app.i18n.catalog import available_languages, read_catalog

#: Wohin die Belege gehen.
TARGET = Path(__file__).resolve().parent.parent / "website" / "bilder"

#: Welche Gruppen des Katalogs den Beleg bilden.
#:
#: „Verbindungen" und „Mechanik" — drei und fünf Bausteine, und zusammen sagen
#: sie beides, was der Abschnitt behauptet: dass es Normteile gibt (Mutternfalle,
#: Gewinde, Schraubenloch) und dass es mehr als Normteile gibt (Passstift,
#: Rastnase, Filmscharnier, zwei Schnappverbindungen). Die Einlegeteile stehen
#: mit einem einzigen Baustein dazwischen; ein Band aus einer Kachel sieht aus
#: wie ein Fehler.
SHOWN_GROUPS = ("fasteners", "mechanics")

#: Wie viel Luft um ein Band bleibt, in Bildpunkten.
PADDING = 12

#: Abstand zwischen den beiden Bändern.
GAP = 8

#: Wie groß die Fenster für die Website aufgenommen werden.
#:
#: **Nicht bildschirmfüllend, und genau darin liegt der Zweck.** Fürs Handbuch
#: steht das Fenster so da, wie es beim ersten Start aufgeht — 2560 Bildpunkte
#: breit, auf einer Handbuchseite groß und scharf. Auf der Startseite steht
#: dasselbe Bild in einer Spalte von 650 Punkten: ein Viertel der Größe, und
#: die Menüleiste ist ein grauer Strich. Gemessen wurden 25 Prozent beim
#: Hauptfenster und 19 beim Skizzenmodus.
#:
#: Diese Maße sind so gewählt, dass die Spalte etwa die Hälfte bis zwei Drittel
#: zeigt — nah genug an eins zu eins, dass Leisten und Beschriftungen als das
#: erkennbar bleiben, was sie sind, und weit genug darüber, dass ein Bildschirm
#: mit doppelter Punktdichte nichts nachschärfen muss.
#:
#: Die Höhe des Startbildschirms ist gemessen und nicht geschätzt: Bei 1400
#: Punkten Breite brauchen seine neun Kacheln und die Zuletzt-Liste 984 Punkte
#: (``verticalScrollBar().maximum()`` plus Fensterhöhe). Bei 840 endete das Bild
#: mitten in der letzten Kachelreihe — ein Schnitt, den man für einen Fehler
#: hält, weil er wie einer aussieht.
WEB_WINDOW = (1400, 860)
WEB_SKETCH = (1100, 640)
WEB_START = (1400, 1000)

#: Wie lange ein Durchgang beim Setzenlassen dauert, in Millisekunden.
SETTLE_MS = 50


def settle(rounds: int = 12) -> None:
    """Der Oberfläche Zeit geben — mit laufender Ereignisschleife.

    Die Vorschaubilder des Katalogs entstehen eines je Durchlauf
    (:meth:`PartCatalog._render_pending`); ohne echte Schleife bleibt das Band
    eine Reihe leerer Kacheln.
    """
    loop = QEventLoop()
    QTimer.singleShot(rounds * SETTLE_MS, loop.quit)
    loop.exec()


def band_rect(catalog: Any, group: str) -> QRect | None:
    """Das Rechteck aus Überschrift und Kacheln einer Gruppe, in Listenkoordinaten.

    **Die Breite kommt allein von den Kacheln.** Die Überschrift nimmt im Raster
    die ganze Zeile ein, damit die Gruppe darunter neu beginnt
    (:meth:`PartCatalog._stretch_headings`) — mitgerechnet macht sie aus einem
    Band von 880 Bildpunkten eines von 1296, und die vierhundert dahinter sind
    leerer Grund. Ihre Höhe zählt selbstverständlich mit; sie steht ja im Bild.

    ``None``, wenn die Gruppe leer ist — dann gibt es nichts zu zeigen, und ein
    leeres Band wäre schlimmer als kein Band.
    """
    from app.core.knowledge.parts import PARTS

    wanted = {spec.name for spec in PARTS.all() if spec.group == group}
    if not wanted:
        return None

    from PySide6.QtCore import QRect as Rect

    tiles: QRect | None = None
    top: int | None = None
    seen_heading = False
    for row in range(catalog.list.count()):
        item = catalog.list.item(row)
        if item is None:
            continue
        name = item.data(Qt.ItemDataRole.UserRole)
        rect = catalog.list.visualItemRect(item)
        if name is None:
            # Eine Überschrift: die der Gruppe eröffnet das Band, jede spätere
            # beendet es.
            if tiles is not None:
                break
            seen_heading = _is_group_heading(catalog, row, wanted)
            if seen_heading:
                top = rect.top()
            continue
        if not seen_heading or name not in wanted:
            continue
        tiles = Rect(rect) if tiles is None else tiles.united(rect)
    if tiles is None or top is None:
        return None
    return Rect(tiles.left(), top, tiles.width(), tiles.bottom() - top)


def _is_group_heading(catalog: Any, row: int, wanted: set[str]) -> bool:
    """Ob die Überschrift in ``row`` zu den Bausteinen in ``wanted`` gehört.

    Über den ersten Eintrag darunter und nicht über den Text: Der Titel ist
    übersetzt, der Bausteinname nicht — und genau darum geht es hier.
    """
    following = catalog.list.item(row + 1)
    if following is None:
        return False
    name = following.data(Qt.ItemDataRole.UserRole)
    return bool(name) and name in wanted


def shot_of(catalog: Any, rect: QRect) -> QImage:
    """Ein Band aus der Liste greifen — auch, wenn es unter der Kante liegt.

    Gerollt wird vor dem Abgriff: Der Katalog zeigt siebzehn Bausteine in
    sieben Gruppen, und die zweite gezeigte Gruppe steht je nach Sprache und
    Zeilenumbruch schon außerhalb.
    """
    view = catalog.list
    view.verticalScrollBar().setValue(view.verticalScrollBar().minimum())
    settle(4)
    offset = view.verticalScrollBar().value()
    if rect.bottom() - offset > view.viewport().height():
        view.verticalScrollBar().setValue(rect.top() - PADDING)
        settle(4)
        offset = view.verticalScrollBar().value()
    visible = QRect(
        max(rect.left() - PADDING, 0),
        max(rect.top() - offset - PADDING, 0),
        rect.width() + 2 * PADDING,
        rect.height() + 2 * PADDING,
    )
    visible = visible.intersected(view.viewport().rect())
    return view.viewport().grab(visible).toImage()


def stack(bands: list[QImage]) -> QImage:
    """Die Bänder untereinander auf einen gemeinsamen Grund."""
    width = max(band.width() for band in bands)
    height = sum(band.height() for band in bands) + GAP * (len(bands) - 1)
    sheet = QImage(width, height, QImage.Format.Format_RGB32)
    # Die Farbe des ersten Bildpunkts und keine geratene: Das Band kommt aus
    # der Liste, und deren Grund steht im Thema. Ein eingetippter Farbwert wäre
    # beim nächsten Themenwechsel falsch, ohne dass es jemandem auffiele.
    sheet.fill(bands[0].pixelColor(0, 0))
    painter = QPainter(sheet)
    top = 0
    for band in bands:
        painter.drawImage(QPoint(0, top), band)
        top += band.height() + GAP
    painter.end()
    return sheet


def named(stem: str, language: str) -> Path:
    """Wohin ein Beleg gehört. Deutsch ohne Kürzel, wie auf der Website."""
    suffix = "" if language == SOURCE_LANGUAGE else f"-{language}"
    target = TARGET / f"{stem}{suffix}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def take_parts(language: str) -> Path:
    """Den Bausteinbeleg einer Sprache schneiden und ablegen."""
    from app.ui.catalog import PartCatalog

    catalog = PartCatalog()
    catalog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    catalog.show()
    # Genug für alle siebzehn Vorschaubilder, eines je Durchlauf.
    settle(40)

    bands = []
    for group in SHOWN_GROUPS:
        rect = band_rect(catalog, group)
        if rect is None:
            raise SystemExit(f"Gruppe {group!r} ist leer — kein Beleg möglich")
        bands.append(shot_of(catalog, rect))
    sheet = stack(bands)
    catalog.close()

    target = named("beleg-bausteine", language)
    sheet.save(str(target))
    return target


def take_windows(app: QApplication, language: str) -> list[Path]:
    """Hauptfenster, Skizzenmodus und Startbildschirm in Website-Maßen.

    Aufgebaut wie im Handbuch, nur kleiner — die Bausteine dafür stehen in
    ``make_figures`` und werden hier benutzt statt nachgebaut. Ein zweiter
    Aufbau desselben Fensters wäre die Sorte Kopie, die auseinanderläuft,
    sobald jemand an einem der beiden etwas ändert.
    """
    from app.core import examples
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.start_screen import StartScreen

    written = []

    start = figures.prepared(StartScreen(), WEB_START)
    figures.settle(app)
    target = named("beleg-start", language)
    start.grab().save(str(target))
    written.append(target)
    start.close()

    session = Session()
    window = figures.prepared(
        MainWindow(session, UiSettings()), WEB_WINDOW, hidden=False, maximize=False
    )
    project = examples.directory() / figures.EXAMPLE
    if not project.is_file():
        raise SystemExit(f"Beispielprojekt fehlt: {project}")
    session.open_project(project)
    figures.translate_parameter_titles(session)
    window.parameters.show_document(session.project.document)
    window._show_start_screen(False)
    if not figures.await_result(app, session):
        raise SystemExit("Die Auswertung wurde nicht fertig — kein Bild vom Hauptfenster")
    window.report.add_findings(figures.sample_findings(language))
    window.raise_()
    window.activateWindow()
    figures.settle(app, 60)
    target = named("beleg-fenster", language)
    # Über den Bildschirm, nicht über den Qt-Painter: der weiß nichts von dem,
    # was OpenGL in den Viewport gezeichnet hat — die Bildmitte bliebe schwarz.
    screen = window.screen() or QApplication.primaryScreen()
    screen.grabWindow(window.winId()).save(str(target))
    written.append(target)

    # **Der Skizzenmodus im selben Fenster** — er ist seit P4 keine eigene Seite
    # mehr. Wie er fürs Bild aufgesetzt wird, steht in ``make_figures``: Zwei
    # Werkzeuge, ein Bild, und der Ausschnitt hängt an Maßen, die man messen muss.
    figures.frame_sketch(window, app)
    target = named("beleg-skizze", language)
    screen.grabWindow(window.winId()).save(str(target))
    written.append(target)
    window.finish_sketch(keep=False)
    figures.settle(app, 20)

    window.close()
    figures.release_viewport(window)

    return written


def main() -> int:
    os.environ.pop("QT_QPA_PLATFORM", None)

    from app.ui.app import install_qt_translations
    from app.ui.theme import apply_theme

    load_operations()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    apply_theme(app, "dark")

    wanted = tuple(sys.argv[1:]) or available_languages()
    translator = None
    for language in wanted:
        install_catalog(language, read_catalog(language))
        set_language(language)
        if translator is not None:
            app.removeTranslator(translator)
        translator = install_qt_translations(app, language)
        print(f"{language}:")
        for target in (take_parts(language), *take_windows(app, language)):
            image = QImage(str(target))
            print(f"  {target.name:<26} {image.width()}x{image.height()}")
    print("\nFertig. Die Maße gehören in die <img>-Angaben der Seiten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
