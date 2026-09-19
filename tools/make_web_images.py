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

**Ein Motiv läuft in einem eigenen Prozess:** das Regal des Filamentlagers
(``beleg-filamentlager``). Es legt Spulen an und bucht Verbrauch, und das
geschieht in umgebogenen Nutzerverzeichnissen — siehe :func:`take_inventory`.
Die übrigen Motive lesen Roberts Profil nur; dieses hätte es beschrieben.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
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
from app.i18n.catalog import read_catalog

#: Wohin die Belege gehen.
TARGET = Path(__file__).resolve().parent.parent / "website" / "bilder"

#: Welche Gruppen des Katalogs den Beleg bilden.
#:
#: „Verbindungen" und „Mechanik" — zusammen sagen sie beides, was der
#: Abschnitt behauptet: dass es Normteile gibt (Mutternfalle, Gewinde,
#: Schraubenloch) und dass es mehr als Normteile gibt (Passstift, Rastnase,
#: Scharniere, Schnappverbindungen). Auf Stückzahlen zählt dieser Kommentar
#: nicht mehr — die Bibliothek wächst, und eine mitgeschriebene Zahl war beim
#: Review vom 26.08.2026 bereits zweimal falsch.
#:
#: **„Befestigung" kam dazu, weil der Text daneben damit wirbt.** Die
#: Startseite nennt vier Bausteine beim Namen, und einer davon — der
#: Lochwand-Einhänger — lag in einer Gruppe, die das Bild nicht zeigte. Ein
#: Beleg, der das Genannte nicht enthält, belegt nichts; wer hier eine Gruppe
#: streicht, liest deshalb zuerst, welche Namen auf der Seite stehen.
SHOWN_GROUPS = ("fasteners", "mechanics", "mounting")

#: Wie viel Luft um ein Band bleibt, in Bildpunkten.
PADDING = 12


#: Wo die Aussage eines Belegs in einem **Detail** steckt, zeigt er einen
#: Ausschnitt statt des ganzen Fensters.
#:
#: **Die Regel ist eine über Dichte, nicht über Form** (50s Größen-Konzept,
#: 31.08.2026): Dateibreite geteilt durch Anzeigebreite muss mindestens 1,3
#: betragen, sonst ist das Bild auf einem Schirm mit doppelter Punktdichte
#: sichtbar unscharf. Der Hero der KI-Seite steht auf 460 Punkten; ein
#: Vollfenster von 1400 Punkten erfüllt die Zahl mühelos und zeigt trotzdem
#: nichts — die Befundliste, um die es auf der ganzen Seite geht, ist dort eine
#: graue Fläche, und auf dem Telefon bei 390 Punkten erkennt man gar nichts.
#:
#: **Vollfenster bleiben, wo die Aussage „so sieht das Programm aus" ist** —
#: Startseite und Funktionsseite. Dort *ist* das ganze Fenster der Inhalt.
#:
#: Die Region steht als **Name** und nicht als vier Zahlen: „ab dem linken Rand
#: des Viewports" bleibt richtig, wenn jemand die Spaltenbreite ändert; „ab 270"
#: wäre am nächsten Tag eine Zahl ohne Herkunft.
CROPS: dict[str, str] = {}

#: Auf diese Breite wird ein Ausschnitt herunterskaliert. 900 zu 460 Punkten
#: Anzeige sind 1,96 — deutlich über der Grenze von 1,3 und ohne die Bytes, die
#: der rohe Ausschnitt von 1130 kosten würde.
CROP_WIDTH = 900


def _crop_region(window: Any, kind: str) -> QRect:
    """Die benannte Region als Rechteck im Fenster.

    ``viewport_und_bericht`` beginnt hinter der linken Spalte und reicht bis zum
    Fensterrand: Modell und Prüfbericht groß, Objekte, Parameter und Verlauf
    bleiben draußen.

    **Gemessen wird an den Panels, nicht am Viewport** — und das ist kein
    Geschmack. Der Viewport füllt das ganze Fenster (gemessen: 0, 0, 1400, 757),
    die Panels schweben **darüber**. Ein Ausschnitt „ab dem linken Rand des
    Viewports" wäre deshalb das ganze Fenster gewesen; genau das hat er beim
    ersten Anlauf geliefert, und dem Bild sah man es nicht an, weil es
    trotzdem besser aussah als vorher (kleiner skaliert, also schärfer).

    Eine Konstante steht hier auch nicht: Die Spalte ist heute 271 Punkte
    breit, und wer das Layout ändert, soll den Ausschnitt nicht nachpflegen
    müssen.
    """
    if kind != "viewport_und_bericht":
        raise SystemExit(f"Unbekannter Ausschnitt: {kind}")
    edges = []
    for name in ("object_tree", "parameters", "history_panel", "filaments"):
        panel = getattr(window, name, None)
        if panel is not None:
            edges.append(panel.mapTo(window, panel.rect().topRight()).x())
    if not edges:
        raise SystemExit("Kein Panel der linken Spalte gefunden — Ausschnitt unbestimmbar")
    # Der linke Rand der Panels ist zugleich der Abstand, den sie zum
    # Fensterrand halten; denselben lassen wir rechts von ihnen stehen.
    margin = min(
        panel.mapTo(window, QPoint(0, 0)).x()
        for name in ("object_tree", "parameters", "history_panel")
        if (panel := getattr(window, name, None)) is not None
    )
    left = max(edges) + margin
    # **Oben genauso: nichts anschneiden.** Der erste Anlauf begann bei y = 0
    # und zerteilte die Menüleiste — links stand ein halbes „chern" von
    # „Speichern", und ein angeschnittenes Menü liest sich als Fehler im Bild
    # (Roberts Einwand vom 31.08.2026, im Wortlaut zum Schild-Motiv: „dass da
    # was rausgeschnitten ist ist auch nicht gut"). Der Schnitt liegt deshalb
    # am oberen Rand der Panels: Was darüber steht, endet als Ganzes.
    #
    # Gemessen wird am **Container**, nicht am Inhalt: ``report`` ist die
    # Befundliste, ihr Reiter („Prüfbericht · 1") gehört dem Elternteil. Der
    # zweite Anlauf schnitt genau durch diesen Reiter — dieselbe Sorte Fehler
    # eine Ebene feiner.
    corners = []
    for name in ("object_tree", "report"):
        panel = getattr(window, name, None)
        if panel is None:
            continue
        parent = panel.parentWidget() or panel
        corners.append(parent.mapTo(window, QPoint(0, 0)).y())
    top = max(0, min(corners) - margin) if corners else 0
    return QRect(left, top, window.width() - left, window.height() - top)


def _capture(window: Any, name: str, target: Path) -> None:
    """Das Fenster ins Bild — ganz oder als benannter Ausschnitt.

    Über den Bildschirm und nicht über den Qt-Painter: Der weiß nichts von dem,
    was OpenGL in den Viewport gezeichnet hat, und die Bildmitte bliebe schwarz.
    """
    screen = window.screen() or QApplication.primaryScreen()
    shot = screen.grabWindow(window.winId())
    kind = CROPS.get(name)
    if kind is not None:
        shot = shot.copy(_crop_region(window, kind))
        if shot.width() > CROP_WIDTH:
            shot = shot.scaledToWidth(CROP_WIDTH, Qt.TransformationMode.SmoothTransformation)
    shot.save(str(target)) or _explode(target)


def _explode(target: Path) -> None:
    """Ein Speichern, dessen Rückgabe niemand liest, sieht immer nach Erfolg aus."""
    raise SystemExit(f"{target} ließ sich nicht schreiben — kein leises Fertig")


#: Abstand zwischen den beiden Bändern.
GAP = 8

#: Das Schaustück der Verkaufsseite — bewusst ein anderes als das
#: Handbuch-Beispiel (``figures.EXAMPLE``, die Dose): Das Handbuch lehrt am
#: Lehrgang, die Startseite verkauft am Ergebnis, und das zweifarbige Schild
#: zeigt auf einen Blick, was die Dose nicht zeigen kann — erhabene Prägung
#: in zwei Materialien. Der erste Eindruck trägt außerdem keinen
#: Warnungsstapel (Hebel A der Website-Durchsicht vom 25.08.2026): Die
#: Befundsorten zeigt weiterhin das ``report.png`` der Fremddatei im
#: Handbuch; hier steht ein Bericht, der sagt, dass nichts zu tun ist.
WEB_EXAMPLE = "schild-zweifarbig.p3d"

#: Zwei grüne Sätze je Sprache: wasserdicht, druckfertig. Gestellt wie
#: ``figures.SAMPLE_FINDINGS`` und aus demselben Grund — nur passt hier die
#: Aussage zum gezeigten Teil statt zur Sortenschau.
SHOWCASE_FINDINGS = {
    "de": (
        "Wasserdicht und aus einem Stück — keine offenen Kanten.",
        "Passt auf das Druckbett; keine Stützen nötig.",
    ),
    "en": (
        "Watertight and in one piece — no open edges.",
        "Fits the build plate; no supports needed.",
    ),
    "es": (
        "Estanco y de una pieza — sin aristas abiertas.",
        "Cabe en la placa de impresión; no necesita soportes.",
    ),
    "fr": (
        "Étanche et d'une seule pièce — aucune arête ouverte.",
        "Tient sur le plateau ; aucun support nécessaire.",
    ),
    "it": (
        "A tenuta stagna e in un pezzo solo — nessuno spigolo aperto.",
        "Entra nel piatto di stampa; nessun supporto necessario.",
    ),
    "pt": (
        "Estanque e de uma só peça — sem arestas abertas.",
        "Cabe na mesa de impressão; não precisa de suportes.",
    ),
}


def showcase_findings(language: str) -> list:
    """Der Bericht des Schaustücks: zwei Zeilen, beide grün."""
    from app.core.types import Finding

    watertight, printable = SHOWCASE_FINDINGS.get(language, SHOWCASE_FINDINGS["de"])
    return [
        Finding(code="ingest.watertight", severity="info", message=watertight),
        Finding(code="slice.printable", severity="info", message=printable),
    ]


#: Wie groß die Fenster für die Website aufgenommen werden: **so groß wie der
#: Bildschirm**, genau wie fürs Handbuch.
#:
#: **Hier standen einmal 1400 auf 860, und die Begründung dafür war für sich
#: richtig.** Ein Bild von 2560 Punkten steht auf der Startseite in einer
#: Spalte von 650 und ist damit auf ein Viertel gestaucht; die Menüleiste wird
#: ein grauer Strich, und Beschriftungen sind nicht mehr zu lesen. Kleiner
#: aufgenommen bleibt davon mehr erkennbar.
#:
#: **Nur zeigt das Bild dann die falsche Sache.** Nachgemessen am fertigen
#: ``beleg-fenster.png`` (Robert, 08.09.2026): Die linke Spalte nimmt 315
#: Punkte, die rechte 710 — zusammen 73 Prozent der Breite. Für das Modell
#: blieb ein Streifen von 375 Punkten in der Mitte. Beide Spalten haben feste
#: Breiten und skalieren nicht mit; je schmaler das Fenster aufgenommen wird,
#: desto größer ihr Anteil. Auf 2560 Punkten sind dieselben 1025 nur noch 40
#: Prozent.
#:
#: Wer auf einer Verkaufsseite ein Bildschirmfoto ansieht, liest keine
#: Menütitel — er sieht das Erzeugnis. Also bekommt es den Raum, und die
#: Lesbarkeit der Leisten wiegt weniger. ``None`` heißt: die Arbeitsfläche des
#: Zielschirms, dieselbe Quelle wie in ``make_figures.work_area``.
WEB_WINDOW: tuple[int, int] | None = None
WEB_START: tuple[int, int] | None = None

#: **Warum hier keine Dialoge stehen, obwohl die Verkaufsseite drei zeigt.**
#:
#: Gemessen am 26.08.2026 im Browser: Auf ``funktionen.html`` werden
#: ``own-part.png`` und ``op-dialog.png`` auf 133 Prozent gezogen,
#: ``report.png`` auf 112 — die Spalte ist 691 Punkte breit, die Bilder sind
#: 520 und 620. Drei unscharfe Bildschirmfotos auf einer Seite, die mit
#: Genauigkeit wirbt.
#:
#: Der naheliegende Griff wäre, sie hier in Spaltenbreite noch einmal
#: aufzunehmen. **Er ist falsch:** Ein Dialog, den man auf 760 Punkte zieht,
#: zeigt Felder in einer Breite, die der Kunde nie zu sehen bekommt — dasselbe
#: hat beim Operationsdialog schon einmal zweihundert Punkte Leerraum erzeugt
#: (siehe ``make_figures``). Ein Fenster darf man kleiner aufnehmen, weil es
#: mitwächst; ein Dialog hat seine Größe.
#:
#: Was wirklich hilft, ist die doppelte Pixeldichte — dieselbe Aufnahme mit
#: ``devicePixelRatio`` 2, dann ist sie in jeder Anzeigegröße scharf und auf
#: einem hochauflösenden Bildschirm gleich mit. Das betrifft **alle**
#: Bildschirmfotos, nicht nur diese drei, und gehört als eigener Schritt
#: gemessen — nicht nebenbei in einer Auslieferung.

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
    sheet.save(str(target)) or _explode(target)
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

    start = figures.prepared(StartScreen(), WEB_START or figures.work_area())
    figures.settle(app)
    target = named("beleg-start", language)
    start.grab().save(str(target)) or _explode(target)
    written.append(target)
    start.close()

    session = Session()
    window = figures.prepared(
        MainWindow(session, UiSettings()),
        WEB_WINDOW or figures.work_area(),
        hidden=False,
        maximize=False,
    )
    project = examples.directory() / WEB_EXAMPLE
    if not project.is_file():
        raise SystemExit(f"Beispielprojekt fehlt: {project}")
    session.open_project(project)
    figures.translate_parameter_titles(session)
    window.parameters.show_document(session.project.document)
    window._show_start_screen(False)
    if not figures.await_result(app, session):
        raise SystemExit("Die Auswertung wurde nicht fertig — kein Bild vom Hauptfenster")
    window.report.add_findings(showcase_findings(language))
    window.raise_()
    window.activateWindow()
    figures.settle(app, 60)
    target = named("beleg-fenster", language)
    _capture(window, "beleg-fenster", target)
    written.append(target)

    # **Der Skizzenmodus im selben Fenster** — er ist seit P4 keine eigene Seite
    # mehr. Wie er fürs Bild aufgesetzt wird, steht in ``make_figures``: Zwei
    # Werkzeuge, ein Bild, und der Ausschnitt hängt an Maßen, die man messen muss.
    figures.frame_sketch(window, app)
    target = named("beleg-skizze", language)
    _capture(window, "beleg-skizze", target)
    written.append(target)
    window.finish_sketch(keep=False)
    figures.settle(app, 20)

    window.close()
    figures.release_viewport(window)

    return written


#: Wie groß das Regal des Filamentlagers aufgenommen wird — **vier Spalten,
#: zwei Regalbretter, kein Rollbalken.**
#:
#: Die Spaltenzahl rechnet das Regal selbst (``InventoryView._shelf_columns``:
#: eine Karte ist 236 Punkte breit, dazu der Abstand), und sie kippt bei 1260
#: Punkten Fensterbreite auf fünf. Sechs Spulen in fünf Spalten lassen zwei
#: Fünftel des Bildes leer; in vier stehen sie als volles Brett und halbes
#: Brett. Die Höhe ist gemessen: Zwei Bretter mit Überschrift brauchen 638
#: Punkte im Rollbereich, und der bekommt die Fensterhöhe minus Kopf, Suche,
#: Knopfzeile und Einstellungen. Bei 852 passt es ohne Rollbalken — und der
#: Lauf prüft das, statt es anzunehmen: Ein Regal, dessen zweites Brett unten
#: angeschnitten ist, sähe aus wie ein Fehler der Anwendung.
INVENTORY_VIEW = (1256, 852)

#: Die Karte auf der Startseite zeigt ihr Bild in 3:2 (``.feature-card img``,
#: ``aspect-ratio: 3 / 2``), wie die gerenderten Funktionsbilder. Ein Bild in
#: einem anderen Verhältnis bekäme dort Balken in der Kartenfarbe — im hellen
#: Thema weiße Streifen neben einer dunklen Oberfläche. Das Regal wird
#: deshalb auf ein 3:2-Blatt in seiner eigenen Fenstergrundfarbe gelegt: elf
#: Punkte je Seite, vom Rand des Regals nicht zu unterscheiden.
INVENTORY_RATIO = 1.5

#: Die Nutzerverzeichnisse, die der Kindprozess des Lagerbelegs umbiegt —
#: dieselben sechs wie ``tests/conftest.py`` (§38). ``HOME`` ist für macOS
#: dabei, wo jede Auflösung über ``Path.home()`` läuft; unter Windows ist der
#: Eintrag folgenlos.
ISOLATED_VARIABLES = (
    "APPDATA",
    "LOCALAPPDATA",
    "HOME",
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
)

#: Woran das Kind erkennt, dass es isoliert läuft. Der Elternprozess setzt die
#: Variable auf den Temp-Ordner; das Kind weigert sich ohne sie — von Hand
#: gestartet stünde es sonst vor Roberts echtem Lager.
ROOM_VARIABLE = "SOLIDON_WEB_IMAGES_ROOM"

#: Sechs Spulen, die ein Regal glaubwürdig machen — je Sprache die Namen, die
#: ein Kunde in dieser Sprache tippen würde; Materialart und Farbe sind
#: überall dieselben. Zwei Lagerorte, damit das Regal seine Gruppierung
#: zeigt; eine Spule mit drei Farben, eine unter der Warnschwelle, eine voll,
#: eine mit gebuchtem Verbrauch (die Restmenge kommt dann aus dem Journal,
#: nicht aus einer getippten Zahl). Die Reihenfolge der Namen: Silk,
#: Schwarz matt, PETG, ASA, TPU, PA-CF — ``SAMPLE_STOCK`` liest sie so.
SAMPLE_NAMES: dict[str, tuple[str, ...]] = {
    "de": (
        "PLA Silk Regenbogen",
        "PLA Schwarz matt",
        "PETG Transparent Blau",
        "ASA Hellgrau",
        "TPU 95A Rot",
        "PA-CF Schwarz",
    ),
    "en": (
        "PLA Silk Rainbow",
        "PLA Matte Black",
        "PETG Translucent Blue",
        "ASA Light Grey",
        "TPU 95A Red",
        "PA-CF Black",
    ),
    "es": (
        "PLA Seda Arcoíris",
        "PLA Negro mate",
        "PETG Azul translúcido",
        "ASA Gris claro",
        "TPU 95A Rojo",
        "PA-CF Negro",
    ),
    "fr": (
        "PLA Soie Arc-en-ciel",
        "PLA Noir mat",
        "PETG Bleu translucide",
        "ASA Gris clair",
        "TPU 95A Rouge",
        "PA-CF Noir",
    ),
    "it": (
        "PLA Silk Arcobaleno",
        "PLA Nero opaco",
        "PETG Blu trasparente",
        "ASA Grigio chiaro",
        "TPU 95A Rosso",
        "PA-CF Nero",
    ),
    "pt": (
        "PLA Silk Arco-íris",
        "PLA Preto fosco",
        "PETG Azul translúcido",
        "ASA Cinzento-claro",
        "TPU 95A Vermelho",
        "PA-CF Preto",
    ),
}

#: Die zwei Lagerorte und die zwei Projektnamen der Buchungen, je Sprache.
#: Die Projektnamen stehen nur im Buchungsverlauf der Spule — im Regal sieht
#: man von ihnen die Restmenge, die sie hinterlassen.
#:
#: **Der Ort der vier Spulen sortiert vor dem der zwei.** Das Regal ordnet
#: seine Bretter nach dem Namen des Orts; steht das halbe Brett oben, liest
#: sich das Bild von der Lücke her. Deshalb heißt der Schrank, wo „Regal"
#: hinter „Trockenbox" fiele — die Wörter sind das, was ein Kunde in seiner
#: Sprache in das Feld tippt, keine Übersetzung voneinander.
SAMPLE_PLACES: dict[str, tuple[str, str, str, str]] = {
    "de": ("Regal Werkstatt", "Trockenbox", "Halter Lochwand", "Vorratsdose"),
    "en": ("Bench shelf", "Dry box", "Pegboard holder", "Storage jar"),
    "es": ("Armario del taller", "Caja seca", "Soporte para panel", "Bote de almacenaje"),
    "fr": ("Armoire de l'atelier", "Boîte sèche", "Support pour panneau", "Bocal de rangement"),
    "it": ("Armadio officina", "Dry box", "Supporto per pannello", "Barattolo"),
    "pt": ("Armário da oficina", "Caixa seca", "Suporte para painel", "Frasco de arrumação"),
}

#: Materialart, erste Farbe, weitere Farben, Lagerort (0 = Regal, 1 =
#: Trockenbox), Nennfüllung, Restmenge — in der Reihenfolge von
#: :data:`SAMPLE_NAMES`. Die schwarze PLA-Spule beginnt voll; was ihr fehlt,
#: buchen die zwei Druckvorgänge in :func:`_stock_the_shelf`.
SAMPLE_STOCK: tuple[tuple[str, str, tuple[str, ...], int, float, float], ...] = (
    ("PLA", "#e0483c", ("#f2b134", "#2f7fd6"), 0, 1000.0, 1000.0),
    ("PLA", "#2b2b2e", (), 0, 1000.0, 1000.0),
    ("PETG", "#3a8fd9", (), 0, 1000.0, 70.0),
    ("ASA", "#b8bcc2", (), 0, 1000.0, 760.0),
    ("TPU", "#c8342b", (), 1, 500.0, 410.0),
    ("PA-CF", "#1f2124", (), 1, 500.0, 500.0),
)

#: Die zwei Buchungen auf der schwarzen Spule: Gramm aus dem G-Code, wie die
#: Slicer-Übergabe sie liefert (§29). Zusammen 387,6 g — die Karte zeigt
#: danach 612,4 g, gerechnet vom Journal.
SAMPLE_BOOKINGS = (187.6, 200.0)


def take_inventory(language: str) -> Path:
    """Das Regal des Filamentlagers mit Beispielspulen — im eigenen Prozess.

    **Warum ein Kindprozess.** Das Regal liest und schreibt ``filaments.json``
    unter ``%APPDATA%`` — Roberts echtes Lager. Die übrigen Motive dieser
    Datei lesen nur; dieses legt Spulen an und bucht Verbrauch, und das darf
    das echte Lager nicht einmal streifen. Umgebogen werden die
    Nutzerverzeichnisse deshalb **in der Umgebung des Kindes**, also vor
    dessen erstem Import: Im eigenen Prozess käme jede Umbiegung nach
    ``import app`` zu spät, weil ``filaments`` den Pfad über einen lokal
    gebundenen Namen auflöst (Gedächtnis: ``config-dir-hat-keinen-schalter``,
    zweimal zugeschnappt). Dieselbe Bauart wie ``make_feature_images.py``, ein
    Prozess je Motiv mit eigenen Konfigurationsverzeichnissen.
    """
    target = named("beleg-filamentlager", language)
    with tempfile.TemporaryDirectory(prefix="solidon-web-lager-") as room:
        environment = dict(os.environ)
        for name in ISOLATED_VARIABLES:
            environment[name] = room
        environment[ROOM_VARIABLE] = room
        environment.pop("QT_QPA_PLATFORM", None)
        run = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--lager", language],
            env=environment,
            check=False,
        )
    if run.returncode != 0 or not target.is_file():
        raise SystemExit(
            f"Der Lagerbeleg für {language!r} ist nicht entstanden "
            f"(Kindprozess endete mit {run.returncode})"
        )
    return target


def _stock_the_shelf(language: str) -> None:
    """Sechs Spulen anlegen und auf einer davon zwei Drucke buchen.

    Über die Kern-API und nicht über eine hingeschriebene ``filaments.json``:
    So läuft jede Zeile durch dieselbe Prüfung wie eine Eingabe im Dialog, und
    die Restmenge der gebuchten Spule ist gerechnet, nicht getippt.
    """
    from app.core.knowledge import filaments

    names = SAMPLE_NAMES.get(language, SAMPLE_NAMES["de"])
    shelf, box, first_print, second_print = SAMPLE_PLACES.get(language, SAMPLE_PLACES["de"])
    saved = []
    for name, (material, colour, extra, place, nominal, remaining) in zip(
        names, SAMPLE_STOCK, strict=True
    ):
        saved.append(
            filaments.save(
                filaments.CatalogueFilament(
                    name,
                    colour,
                    material,
                    location=(shelf, box)[place],
                    spool_grams=nominal,
                    remaining_grams=remaining,
                    extra_colours=extra,
                    bought_on="2026-08-14",
                    price=24.9,
                    currency="EUR",
                )
            )
        )
    black = saved[1]
    for number, (grams, project) in enumerate(
        zip(SAMPLE_BOOKINGS, (first_print, second_print), strict=True), start=1
    ):
        filaments.book(
            f"web-print-{number}",
            f"web-plate-{number}",
            [
                filaments.BookingPosition(
                    black.identifier, grams, "gcode", stock_revision=black.stock_revision
                )
            ],
            project_name=project,
        )


def _inventory_child(language: str) -> int:
    """Die Kindseite von :func:`take_inventory`: Regal bauen, füllen, ablegen."""
    from app.core.paths import user_config_dir

    room = os.environ.get(ROOM_VARIABLE)
    if not room or not str(user_config_dir()).startswith(room):
        raise SystemExit(
            "Der Lagerbeleg läuft nur isoliert — über take_inventory(), nie von Hand: "
            f"{user_config_dir()} ist Roberts echtes Profil."
        )

    from app.ui.app import install_qt_translations
    from app.ui.filament_inventory import InventoryView
    from app.ui.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    apply_theme(app, "dark")
    install_catalog(language, read_catalog(language))
    set_language(language)
    install_qt_translations(app, language)

    _stock_the_shelf(language)

    view = InventoryView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    view.resize(*INVENTORY_VIEW)
    # Nach Lagerort gruppiert: zwei Bretter, „Regal" und „Trockenbox". Nach
    # Material wären es fünf Überschriften für sechs Spulen.
    view.grouping.setCurrentIndex(view.grouping.findData("location"))
    view.show()
    settle(20)
    view.refresh()
    settle(20)

    expected = len(SAMPLE_STOCK)
    if len(view.cards) != expected:
        raise SystemExit(f"Das Regal zeigt {len(view.cards)} Spulen statt {expected}")
    if view.page_scroll.verticalScrollBar().maximum() > 0:
        raise SystemExit(
            "Das Regal braucht einen Rollbalken — die Höhe in INVENTORY_VIEW reicht "
            "für zwei Bretter nicht mehr"
        )

    shot = view.grab().toImage()
    width = max(shot.width(), round(shot.height() * INVENTORY_RATIO))
    sheet = QImage(width, shot.height(), QImage.Format.Format_RGB32)
    # Die Grundfarbe aus dem Bild selbst, wie in ``stack``: Der Rand des
    # Regals ist die Fensterfarbe des Themas, und eine getippte wäre beim
    # nächsten Themenwechsel falsch.
    sheet.fill(shot.pixelColor(0, 0))
    painter = QPainter(sheet)
    painter.drawImage(QPoint((width - shot.width()) // 2, 0), shot)
    painter.end()
    view.release()
    view.close()

    target = named("beleg-filamentlager", language)
    if not sheet.save(str(target)):
        _explode(target)
    return 0


def take_transformation() -> tuple[Path, Path]:
    """Das Vorher/Nachher für den Beweis-Teil der Startseite (WD3, M10).

    Links, wie ein erzeugtes oder heruntergeladenes Modell ankommt: nicht
    geschlossen, mit Löchern, die man im Bild sieht. Rechts, wie es die Platte
    verlässt. Transformation ist die überzeugendste Bildform für „aus kaputt
    wird druckbar", und dieses Paar zeigt sie ohne ein Wort.

    **Ohne Fenster, ohne Qt, ohne Renderer** — als einziges Motiv dieser Datei.
    ``drawing.project`` zeichnet das Netz als SVG, dieselbe Projektion, aus der
    auch die Vorschaubilder der Bausteine entstehen. Damit hängt das Bild an
    keiner Bildschirmgröße, keiner Schriftmetrik und keiner Betriebslage; es
    ist auf jedem Rechner dasselbe, und die drei Fallen, an denen die übrigen
    Motive hier hängen, gibt es nicht.

    **Der Stoff kommt aus einem ausgelieferten Beispielprojekt**, nicht aus
    einem Prüfkörper. Das ist keine Bequemlichkeit, sondern der einzige
    ehrliche Weg: Die beiden kaputten Modelle des Testkorpus sind ein Quader
    ohne Deckel und ein sich selbst durchdringender Würfel — beide belegen eine
    Rechenregel und überzeugen niemanden. Und das Beispiel zu Weg 1 taugt
    ebenso wenig, obwohl es einen ``repair``-Schritt trägt: Sein Modell ist
    beim Einlesen bereits geschlossen, die Reparatur hat nichts zu tun.
    Gemessen zeigt allein ``weg3-generiert-aufbereiten`` die Sache — nicht
    geschlossen mit 3372 Dreiecken, danach geschlossen.

    Ohne Sprache: Das Bild trägt keinen Text. Was dazu zu sagen ist, steht als
    Bildunterschrift im HTML und wird dort übersetzt.
    """
    import dataclasses

    from app.core import drawing
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.scene import ResultCache, evaluate
    from app.core.scene.project import ProjectSources, load

    # **Das Register selbst füllen, statt es vorauszusetzen.** Die übrigen
    # Motive hier laufen nur über ``main``, das es lädt; dieses kommt ohne
    # Fenster aus und wird deshalb auch einzeln gerufen. Ohne Register wertet
    # ``evaluate`` keinen einzigen Schritt aus, die Szene bleibt leer, und der
    # nächste Griff endete mit ``StopIteration`` — die schlechteste denkbare
    # Auskunft für „die Operationen fehlen" (Regel 17). Der Aufruf ist
    # unschädlich, wenn das Register schon steht.
    load_operations()

    example = Path(__file__).resolve().parent.parent / "app" / "examples"
    project = load(example / "weg3-generiert-aufbereiten.p3d")
    document = project.document
    profile = profiles.make_profile(
        document.printer or "centauri-carbon-2", document.material or "petg"
    )
    last = max(step.id for step in document.ops)

    written: list[Path] = []
    for until, stem in ((1, "verwandlung-vorher"), (last, "verwandlung-nachher")):
        part = dataclasses.replace(document, ops=[s for s in document.ops if s.id <= until])
        result = evaluate(part, profile, cache=ResultCache(), sources=ProjectSources(project))
        bodies = list(result.scene.objects.values())
        if not bodies:
            raise SystemExit(
                f"{stem}: die Auswertung hat keinen Körper geliefert. "
                f"Steht das Beispielprojekt noch unter {example}, und trägt es "
                f"die Schritte 1 bis {last}?"
            )
        body = bodies[0]
        colours = drawing.palette("light")
        target = TARGET / f"{stem}.svg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            drawing.project(
                body.mesh.raw,
                420,
                colours.solid,
                theme="light",
                edges=True,
                around=-35.0,
                down=25.0,
            ),
            encoding="utf-8",
            # ``newline=""``: der ganze Baum steht auf ``\n``, und hochgeladen
            # wird der Arbeitsbaum — siehe `stamp_assets.stamp_page`.
            newline="",
        )
        written.append(target)
    return written[0], written[1]


def main() -> int:
    os.environ.pop("QT_QPA_PLATFORM", None)

    # Die Kindseite des Lagerbelegs: ein Prozess, eine Sprache, eigene
    # Nutzerverzeichnisse — gestartet von ``take_inventory``, nicht von Hand.
    if sys.argv[1:2] == ["--lager"]:
        if len(sys.argv) != 3:
            raise SystemExit("--lager braucht genau eine Sprache, etwa: --lager de")
        return _inventory_child(sys.argv[2])

    from app.ui.app import install_qt_translations
    from app.ui.theme import apply_theme

    load_operations()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    apply_theme(app, "dark")

    # Dieselbe Prüfung wie in ``make_figures``: Eine unbekannte Sprache gäbe
    # einen leeren Katalog, jedes ``tr()`` fiele auf Deutsch zurück, und der
    # Lauf endete mit „Fertig." — die Falle aus 229490a, über den anderen Weg.
    from make_figures import chosen_languages

    wanted = chosen_languages(tuple(sys.argv[1:]))
    translator = None
    for language in wanted:
        install_catalog(language, read_catalog(language))
        set_language(language)
        if translator is not None:
            app.removeTranslator(translator)
        translator = install_qt_translations(app, language)
        print(f"{language}:")
        motive = (
            take_parts(language),
            *take_windows(app, language),
            take_inventory(language),
        )
        if language == SOURCE_LANGUAGE:
            # Das Verwandlungspaar trägt keinen Text und entsteht deshalb
            # einmal, nicht je Sprache (WD3).
            for target in take_transformation():
                print(f"  {target.name:<26} SVG")
        for target in motive:
            image = QImage(str(target))
            print(f"  {target.name:<26} {image.width()}x{image.height()}")
    print("\nFertig. Die Maße gehören in die <img>-Angaben der Seiten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
