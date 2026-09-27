"""Die Aufnahmen der Anwendung für die Website — aus dem maximierten Hauptfenster.

    .venv\\Scripts\\python.exe tools/make_web_images.py [sprachen] [--nur fenster|verwandlung]

Die Startseite und die Funktionsseite belegen ihre Behauptungen mit Bildern aus
der laufenden Anwendung. **Jedes davon entsteht im ganzen Solidon-Fenster,
maximiert auf dem Zielschirm** (``make_figures.target_screen``), in nativen
Bildpunkten — Bildstandard von Robert, 23.09.2026: „Du nimmst die Bilder aber
schon so auf, dass der ganze Bildschirm verwendet wird und wir nicht nur so
eine kleine Szene haben". Braucht eine Karte einen anderen Zuschnitt, wird er
aus dieser Vollbildaufnahme geschnitten, nie hochgerechnet und nie auf einen
Grund gelegt: Was im Bild steht, steht so auf dem Bildschirm.

Daraus folgt, was hier anders ist als bis zum 23.09.2026:

* **Keine Widgets mehr einzeln.** Der Bausteinkatalog war eine Montage aus
  Kachelbändern, das Filamentlager ein Regal auf einem Blatt in 3:2, die
  Schrittbilder eigene kleine Fenster mit Zeichenfaktor 1,5. Jetzt steht jedes
  Motiv im selben Hauptfenster, und Dialoge gehen über **den Weg auf, den der
  Kunde klickt** — ``action_catalog``, ``action_print_settings``, der Knopf
  „Auswahl als Baustein speichern". Gegriffen wird der Bildschirm und nicht das
  Widget, damit der Dialog mit seinem Rahmen über dem Fenster im Bild steht.
* **Keine gestellten Befunde.** Das Hauptfenster zeigte zwei eingesetzte grüne
  Sätze („Wasserdicht und aus einem Stück …"). Jetzt steht im Prüfbericht, was
  die Auswertung sagt — dieselbe Regel, die ``make_figures`` seit dem
  02.09.2026 für das Handbuch einhält.
* **Die Statuszeile ist aus.** Sie trägt die Restlaufzeit der Demo („noch 39
  Tage") — auf einer Website eine Zahl, die in einer Woche falsch ist.
* **Das Modell füllt die Ansicht.** Nach dem Einpassen rückt die Kamera näher
  (:data:`FILL`); eingepasst lässt die Anwendung Luft für die schwebenden
  Leisten, und auf dem Bild wurde das Teil zum Fleck in einem Raster.

**Ein Prozess je Sprache, mit eigenen Nutzerverzeichnissen** (§38): Das
Filamentlager bekommt Beispielspulen und gebuchten Verbrauch, der
Startbildschirm liest Zuletzt-Liste und Lager, und der Druckdialog merkt sich
den gewählten Slicer. Nichts davon darf Roberts Profil streifen. Und ein
Prozess je Sprache, weil ein Hauptfenster je Prozess der Fall ist, den die
Anwendung kennt — mehrere nacheinander enden nach einigen Sprachen in einem
nativen Abbruch (gemessen am 23.09.2026 beim Kreisflug, Exit 127).

Dieselben zwei Fallen wie bei ``make_figures.py``, aus denselben Gründen: Es
läuft **nicht** offscreen (dort hat Qt hier keine Schriften, und der Viewport
zeichnet nur auf einem echten Schirm), und es ist kein Testlauf — die Suite
prüft, dass die Dateien da sind und Rechte haben, nicht wie sie aussehen.
Angesehen wird jedes Bild von dem, der es erzeugt.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Auch der eigene Ordner: ``make_figures`` liegt daneben und ist kein Paket.
sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import make_figures as figures
from PySide6.QtCore import QEventLoop, QPoint, QRect, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.i18n import SOURCE_LANGUAGE, install_catalog, set_language
from app.i18n.catalog import read_catalog

#: Wohin die Aufnahmen gehen.
TARGET = Path(__file__).resolve().parent.parent / "website" / "bilder"

#: Das Schaustück der Verkaufsseite — bewusst ein anderes als das
#: Handbuch-Beispiel (``figures.EXAMPLE``, die Dose): Das Handbuch lehrt am
#: Lehrgang, die Startseite verkauft am Ergebnis, und das zweifarbige Schild
#: zeigt auf einen Blick, was die Dose nicht zeigen kann — erhabene Prägung
#: in zwei Materialien. Sein Prüfbericht kommt aus der Auswertung.
WEB_EXAMPLE = "schild-zweifarbig.p3d"

#: Das Projekt, aus dem ein eigener Baustein gespeichert wird: der Halter aus
#: Weg 2. Er trägt benannte Maße, und genau die fragt der Dialog ab — an einem
#: Projekt ohne Parameter bliebe der Knopf „Auswahl als Baustein speichern"
#: gesperrt, und das Bild zeigte eine Absage.
PART_EXAMPLE = "weg2-halter-konstruieren.p3d"

#: Das eingelesene Netz mit fünf erkannten Bohrungen — dasselbe wie im
#: Bedienloop der Startseite. An ihm zeigt ein Bild, was eine angeklickte
#: Bohrung anbietet: die Maße im Bild und rechts im Fenster „Auswahl" ihre
#: Handlungen. Die Bohrung vorn rechts, wie im Loop.
FEATURE_EXAMPLE = ("weg1-halterung-anpassen.p3d", "hole_4")

#: Das Modell für den zweiten Schritt: die selbst erzeugte Referenzfigur, die
#: auch im Vorher/Nachher steht — eine eingelesene Datei, an der Solidon beim
#: Einlesen wirklich etwas zu reparieren hat. Eingelesen wird über
#: ``import_model``, denselben Weg wie ein abgelegtes Modell.
STEP_MODEL = (
    Path(__file__).resolve().parent.parent / "tests" / "data" / "meshes" / "generated_figure.stl"
)

#: Wie viel näher die Kamera nach dem Einpassen rückt, je Motiv.
#:
#: Eingepasst lässt die Anwendung Luft (``CAMERA_MARGIN``) und spart die
#: schwebenden Leisten aus — richtig für die Arbeit, auf einem Bild aber zu
#: weit: Das Schild stand auf 2560 Punkten als Streifen von 800 in der Mitte
#: eines leeren Rasters. Die Faktoren sind angesehen, nicht gerechnet: Das Teil
#: soll die freie Mitte füllen, ohne unter eine Leiste zu geraten.
FILL = {
    "bericht": 1.35,
    "fenster": 1.3,
    "dialog": 1.3,
    "bericht-beispiel": 1.4,
    "merkmal": 1.5,
}

#: Seitenverhältnis der Schrittkarten (16:10) und der Funktionskarten (3:2).
STEP_RATIO = 1.6
CARD_RATIO = 1.5

#: Wie viel vom Fenster um einen Dialog oder eine Leiste stehen bleibt, in
#: Bildpunkten. Genug, dass man sieht, worüber er liegt; zu wenig, dass es vom
#: Dialog ablenkt.
MARGIN = 40

#: Das Vorschaubild für geteilte Links (``og:image``), in Bildpunkten: das
#: Maß, das Facebook, LinkedIn und die Messenger als große Karte zeigen.
SHARE_SIZE = (1200, 630)

#: WebP-Qualität. Oberfläche mit feiner Schrift: darunter franst die Kante der
#: Buchstaben sichtbar aus. WebP und nicht PNG: Ein Vollfenster wog als PNG
#: über 300 kB, und ``asset_rights`` liefert AVIF nicht aus.
QUALITY = 86

#: Wie lange ein Durchgang beim Setzenlassen dauert, in Millisekunden.
SETTLE_MS = 50


def settle(rounds: int = 12) -> None:
    """Der Oberfläche Zeit geben — mit laufender Ereignisschleife.

    Die Vorschaubilder des Katalogs entstehen eines je Durchlauf
    (:meth:`PartCatalog._render_pending`); ohne echte Schleife bleibt das Raster
    eine Reihe leerer Kacheln.
    """
    loop = QEventLoop()
    QTimer.singleShot(rounds * SETTLE_MS, loop.quit)
    loop.exec()


def _explode(target: Path) -> None:
    """Ein Speichern, dessen Rückgabe niemand liest, sieht immer nach Erfolg aus."""
    raise SystemExit(f"{target} ließ sich nicht schreiben — kein leises Fertig")


def named(stem: str, language: str, kind: str = ".webp") -> Path:
    """Wohin eine Aufnahme gehört. Deutsch ohne Kürzel, wie auf der Website."""
    suffix = "" if language == SOURCE_LANGUAGE else f"-{language}"
    target = TARGET / f"{stem}{suffix}{kind}"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def save_still(image: QImage, stem: str, language: str) -> Path:
    """Eine Aufnahme als WebP ablegen — in der Größe, in der sie gegriffen wurde."""
    target = named(stem, language)
    if not image.save(str(target), "WEBP", QUALITY):
        _explode(target)
    print(f"  {target.name:<34} {image.width()}x{image.height()}")
    return target


def save_share(image: QImage, language: str) -> Path:
    """Das Vorschaubild für geteilte Links — PNG, auf :data:`SHARE_SIZE` verkleinert.

    PNG und nicht WebP, weil nicht jeder Dienst, der eine Linkvorschau baut,
    WebP liest. Verkleinert und nicht in Aufnahmegröße: Eine Karte in einem
    Forum ist ein paar hundert Punkte breit, und das Bild soll dort schnell
    laden. Hochgerechnet wird auch hier nie — der Zuschnitt ist größer.
    """
    from PySide6.QtCore import Qt

    if image.width() < SHARE_SIZE[0]:
        raise SystemExit("Der Zuschnitt fürs Vorschaubild ist kleiner als 1200 Punkte")
    scaled = image.scaled(
        *SHARE_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    target = named("teilen", language, ".png")
    if not scaled.save(str(target), "PNG"):
        _explode(target)
    print(f"  {target.name:<34} {scaled.width()}x{scaled.height()}")
    return target


#: Die Nutzerverzeichnisse, die der Kindprozess der Aufnahmen umbiegt —
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


# --- Greifen und Zuschneiden ---------------------------------------------------


def grab(window: Any, rect: QRect | None = None) -> QImage:
    """Ein Rechteck in Fensterkoordinaten, so wie der Bildschirm es zeigt.

    Über den Bildschirm und nicht über ``window.grab()``: Der Qt-Painter weiß
    nichts von dem, was der Renderer in die Ansicht zeichnet, und die Bildmitte
    bliebe schwarz. Und über den **Schirm** statt über ``grabWindow(winId)``:
    Nur so stehen Dialoge, die eigene Fenster sind, mit im Bild. Ohne ``rect``
    kommt die ganze Client-Fläche; ein Rechteck darf über sie hinausreichen,
    wenn ein Dialog höher ist als das Fenster (:func:`dialog_bounds`).
    """
    area = rect if rect is not None else window.rect()
    # Eine andere Sitzung nimmt vielleicht gerade auf denselben Schirm auf —
    # dann läge ihr Fenster im Bild (``figures.foreign_window_over``).
    figures.wait_until_uncovered(window, area)
    screen = window.screen() or QApplication.primaryScreen()
    corner = window.geometry().topLeft() - screen.geometry().topLeft()
    shot = screen.grabWindow(
        0, corner.x() + area.x(), corner.y() + area.y(), area.width(), area.height()
    ).toImage()
    if shot.width() != area.width() or shot.height() != area.height():
        raise SystemExit(
            f"Die Aufnahme misst {shot.width()}x{shot.height()} statt "
            f"{area.width()}x{area.height()} — der Schirm rechnet mit einem "
            "Zeichenfaktor. Aufgenommen wird in nativen Bildpunkten (Faktor 1)."
        )
    return shot


def dialog_bounds(window: Any, dialog_frame: QRect) -> QRect:
    """Worin ein Zuschnitt um einen Dialog liegen darf.

    Im Fenster, solange der Dialog hineinpasst. Der Dialog für einen eigenen
    Baustein ist höher: 1347 Punkte samt Rahmen, oben über die Titelzeile des
    Fensters hinaus — dann gilt die Arbeitsfläche des Schirms, ohne Taskleiste.
    """
    if window.rect().contains(dialog_frame):
        return window.rect()
    screen = window.screen() or QApplication.primaryScreen()
    return screen.availableGeometry().translated(-window.geometry().topLeft())


def window_rect(window: Any, widget: Any) -> QRect:
    """Wo ein Kind des Fensters im Fenster liegt."""
    corner = widget.mapTo(window, QPoint(0, 0))
    return QRect(corner.x(), corner.y(), widget.width(), widget.height())


def frame_rect(window: Any, dialog: Any) -> QRect:
    """Wo ein Dialog samt Rahmen und Titelzeile über dem Fenster liegt."""
    frame = dialog.frameGeometry()
    return frame.translated(-window.geometry().topLeft())


def framed(focus: QRect, ratio: float | None, bounds: QRect, margin: int = MARGIN) -> QRect:
    """Ein Zuschnitt um ``focus`` — mit Rand, im Verhältnis ``ratio``, im Fenster.

    Wächst nur, schrumpft nie unter den Fokus: Passt das Gezeigte nicht in
    diesen Zuschnitt, bricht der Lauf ab, statt einen Dialog halb abzuschneiden.
    Ein angeschnittenes Bedienelement liest sich als Fehler der Anwendung
    (Roberts Einwand vom 31.08.2026: „dass da was rausgeschnitten ist ist auch
    nicht gut").
    """
    rect = focus.adjusted(-margin, -margin, margin, margin)
    width, height = rect.width(), rect.height()
    if ratio is not None:
        if width / height < ratio:
            width = round(height * ratio)
        else:
            height = round(width / ratio)
        if width > bounds.width():
            width, height = bounds.width(), round(bounds.width() / ratio)
        if height > bounds.height():
            width, height = round(bounds.height() * ratio), bounds.height()
    width, height = min(width, bounds.width()), min(height, bounds.height())
    # Aus Kante und Breite, nicht aus ``QRect.center()``: Das rundet bei
    # gerader Breite um einen Punkt nach links, und ein Zuschnitt genau am
    # Dialograhmen verlor so seine rechte Kante.
    left = rect.left() + (rect.width() - width) // 2
    top = rect.top() + (rect.height() - height) // 2
    left = min(max(left, bounds.left()), bounds.right() + 1 - width)
    top = min(max(top, bounds.top()), bounds.bottom() + 1 - height)
    result = QRect(left, top, width, height)
    if not result.contains(focus):
        raise SystemExit(
            f"Der Zuschnitt {result.getRect()} fasst das Gezeigte {focus.getRect()} "
            "nicht — ein angeschnittenes Bild wird nicht geschrieben."
        )
    return result


def content_rect(image: QImage, area: QRect) -> QRect:
    """Was in ``area`` nicht die Grundfarbe trägt — der Inhalt einer Fläche.

    Der Startbildschirm zentriert seine Karten in der Fensterfläche; gemessen
    wird am Bild selbst und nicht an einer Widgetgeometrie: Was nicht die
    Grundfarbe trägt, ist Inhalt.
    """
    import numpy as np

    part = image.copy(area).convertToFormat(QImage.Format.Format_RGB32)
    width, height = part.width(), part.height()
    pixels = np.frombuffer(part.constBits(), dtype=np.uint8).reshape(
        height, part.bytesPerLine() // 4, 4
    )[:, :width, :3]
    ground = pixels[height // 2, 2].astype(int)
    differs = np.abs(pixels.astype(int) - ground).sum(axis=2) > 12
    rows = np.flatnonzero(differs.any(axis=1))
    columns = np.flatnonzero(differs.any(axis=0))
    if rows.size == 0 or columns.size == 0:
        raise SystemExit("Die Fläche ist leer — der Startbildschirm hat nichts gezeichnet")
    return QRect(
        area.left() + int(columns[0]),
        area.top() + int(rows[0]),
        int(columns[-1] - columns[0]) + 1,
        int(rows[-1] - rows[0]) + 1,
    )


def work_rect(window: Any, ratio: float | None = None) -> QRect:
    """Die Arbeitsfläche ohne die linke Spalte: Ansicht und Prüfbericht.

    Links beginnt sie hinter der Karte mit Objekten, Parametern und Verlauf,
    rechts endet sie hinter der Karte des Prüfberichts, oben an deren
    Oberkante, unten am Fensterrand — so steht jede Karte ganz im Bild oder
    ganz draußen, und der Reiter „Prüfbericht · Chat" wird nicht angeschnitten.
    Gemessen an den Zonen der Überlagerung (``overlay.left``,
    ``right_column``) und nicht an Zahlen: Wer das Layout ändert, soll hier
    nichts nachziehen.

    Mit ``ratio`` wird die Fläche unten gekürzt, bis sie das Verhältnis hat —
    die Schrittkarten stehen in 16:10 nebeneinander, und ein Bild, das die
    Karte erst per CSS beschneidet, schnitt die schwebende Werkzeugleiste
    unten durch. Liegt die neue Unterkante in einer Werkzeug- oder Ansichtsleiste, endet der
    Zuschnitt über ihr, und die Breite gibt links nach — dort ist nur Ansicht,
    rechts steht die Karte des Prüfberichts.
    """
    left_zone = window_rect(window, window.overlay.left)
    right_zone = window_rect(window, window.right_column)
    # Der Abstand der linken Karte zum Fensterrand ist der Rand, den der
    # Zuschnitt um beide Karten lässt.
    gap = max(left_zone.left(), 8)
    left = left_zone.right() + 1 + gap
    top = max(0, min(left_zone.top(), right_zone.top()) - gap)
    right = min(window.width(), right_zone.right() + 1 + gap)
    area = QRect(left, top, right - left, window.height() - top)
    if ratio is None:
        return area
    height = min(area.height(), round(area.width() / ratio))
    for widget in (window.overlay.bottom, window.viewport.view_bar):
        if widget.isVisible():
            bar = window_rect(window, widget)
            if bar.top() < top + height and bar.bottom() >= top + height - 1:
                height = bar.top() - gap - top
    width = round(height * ratio)
    return QRect(area.right() + 1 - width, top, width, height)


def free_rect(window: Any) -> QRect:
    """Die freie Mitte zwischen den beiden Karten, von deren Oberkante bis unten.

    Darin liegt ein Dialog, den die Anwendung über dem Fenster mittig öffnet —
    der Druckdialog. Ein Zuschnitt in dieser Fläche schneidet keine Karte an;
    der erste Anlauf schnitt die Befundliste rechts mitten im Satz ab.
    """
    work = work_rect(window)
    right_zone = window_rect(window, window.right_column)
    gap = work.left() - (window_rect(window, window.overlay.left).right() + 1)
    return QRect(work.left(), work.top(), right_zone.left() - gap - work.left(), work.height())


# --- Warten und Dialoge ---------------------------------------------------------


def until_quiet(app: QApplication, session: Any, what: str) -> None:
    """Warten, bis gerechnet ist — auch der Prüfbericht, der nach der Auswertung kommt."""
    if not figures.await_result(app, session, 120.0):
        raise SystemExit(f"{what} rechnete nicht fertig — kein Bild davon")
    session.wait_for_idle(120_000)
    settle(30)


def fill_view(window: Any, motif: str) -> None:
    """Einpassen — auf die ganze Szene, nicht auf den gewählten Körper —, dann näher heran.

    ``follow_selection=False``: Mit gewählten Lettern rahmte die Kamera nur
    die Lettern, und das Schild stand angeschnitten dahinter.
    """
    window.viewport.reset_camera(follow_selection=False)
    settle(6)
    window.viewport.zoom(FILL[motif])
    settle(12)


def while_open(
    kind: type,
    opener: Callable[[], None],
    act: Callable[[Any], None],
    seconds: float = 90.0,
) -> None:
    """Einen modalen Dialog über den echten Weg öffnen und ``act`` darauf wirken lassen.

    ``opener`` ist die Handlung des Kunden — ``action_catalog``, ein Knopf —,
    und die kehrt erst zurück, wenn der Dialog zu ist. Ein Zeitgeber wartet
    deshalb in der Schleife des Dialogs, bis er steht, lässt ``act`` ihn
    aufnehmen und schließt ihn mit *Abbrechen*. Ein Fehler in ``act`` wird nach
    dem Schließen weitergereicht: In einem Qt-Slot verschluckt, endete der Lauf
    sonst mit „Fertig." und einem fehlenden Bild.
    """
    state: dict[str, Any] = {"done": False, "error": None}
    deadline = time.monotonic() + seconds

    def poll() -> None:
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, kind) and dialog.isVisible():
            try:
                act(dialog)
            except BaseException as error:  # auch SystemExit aus act
                state["error"] = error
            finally:
                state["done"] = True
                dialog.reject()
            return
        if time.monotonic() > deadline:
            state["error"] = SystemExit(f"{kind.__name__} ging nicht auf")
            state["done"] = True
            other = QApplication.activeModalWidget()
            if other is not None and hasattr(other, "reject"):
                other.reject()
            return
        QTimer.singleShot(100, poll)

    QTimer.singleShot(100, poll)
    opener()
    if state["error"] is not None:
        raise state["error"]
    if not state["done"]:
        raise SystemExit(f"{kind.__name__} schloss, bevor er aufgenommen war")


def open_example(window: Any, app: QApplication, name: str) -> None:
    """Ein Beispielprojekt öffnen — ohne die Zuletzt-Liste, mit übersetzten Titeln."""
    from app.core import examples

    session = window.session
    project = examples.directory() / name
    if not project.is_file():
        raise SystemExit(f"Beispielprojekt fehlt: {project}")
    session.forget_changes()
    session.open_project(project)
    figures.translate_parameter_titles(session)
    window.parameters.show_document(session.project.document)
    window._show_start_screen(False)
    until_quiet(app, session, name)


def select_body(window: Any, index: int) -> str:
    """Den ``index``-ten Körper wählen, wie ein Klick im Objektbaum."""
    result = window.session.last_result
    bodies = list(result.scene.objects) if result is not None else []
    if len(bodies) <= index:
        raise SystemExit(f"Die Szene hat {len(bodies)} Körper — Nummer {index + 1} fehlt")
    window.object_tree.select_object(bodies[index])
    settle(20)
    return bodies[index]


# --- Die Motive -------------------------------------------------------------------


def take_screens(language: str) -> list[Path]:
    """Alle Aufnahmen einer Sprache — in einem Kindprozess mit eigenem Profil.

    **Warum ein Kindprozess.** Das Lager liest und schreibt ``filaments.json``
    unter ``%APPDATA%``, der Druckdialog merkt sich den Slicer, der
    Startbildschirm liest die Zuletzt-Liste — Roberts echtes Profil. Umgebogen
    werden die Nutzerverzeichnisse deshalb **in der Umgebung des Kindes**, also
    vor dessen erstem Import: Im eigenen Prozess käme jede Umbiegung nach
    ``import app`` zu spät, weil ``filaments`` den Pfad über einen lokal
    gebundenen Namen auflöst (zweimal
    zugeschnappt). Dieselbe Bauart wie ``make_feature_images.py``.
    """
    with tempfile.TemporaryDirectory(prefix="solidon-web-fenster-") as room:
        environment = dict(os.environ)
        for name in ISOLATED_VARIABLES:
            environment[name] = room
        environment[ROOM_VARIABLE] = room
        environment.pop("QT_QPA_PLATFORM", None)
        environment.pop("QT_SCALE_FACTOR", None)
        arguments = [sys.executable, str(Path(__file__).resolve()), "--fenster", language]
        arguments += ["--schirm", str(figures.SCREEN_INDEX)]
        run = subprocess.run(arguments, env=environment, check=False)
    targets = [named(stem, language) for stem in SCREEN_MOTIFS]
    targets.append(named("teilen", language, ".png"))
    missing = [target.name for target in targets if not target.is_file()]
    if run.returncode != 0 or missing:
        raise SystemExit(
            f"Die Aufnahmen für {language!r} sind nicht vollständig entstanden "
            f"(Kindprozess endete mit {run.returncode}; es fehlen: {', '.join(missing) or '—'})"
        )
    return targets


#: Was :func:`take_screens` je Sprache schreibt — in dieser Reihenfolge.
SCREEN_MOTIFS = (
    "schritt-start",
    "schritt-bericht",
    "schritt-druck",
    "beleg-bericht",
    "beleg-merkmal",
    "beleg-fenster",
    "beleg-dialog",
    "beleg-skizze",
    "beleg-bausteine",
    "beleg-eigener-baustein",
    "beleg-filamentlager",
)


def _screens_child(language: str) -> int:
    """Die Kindseite von :func:`take_screens`: ein Fenster, alle Motive."""
    from app.core.paths import user_config_dir

    room = os.environ.get(ROOM_VARIABLE)
    if not room or not str(user_config_dir()).startswith(room):
        raise SystemExit(
            "Die Website-Aufnahmen entstehen nur isoliert — über take_screens(), nie von "
            f"Hand: {user_config_dir()} ist Roberts echtes Profil."
        )

    from app.core import discover
    from app.core import tools as external_tools
    from app.core.registry import REGISTRY
    from app.ui.app import install_qt_translations
    from app.ui.catalog import PartCatalog
    from app.ui.main_window import MainWindow
    from app.ui.print_disclosure import remember_disclosure
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.recipe_dialog import RecipeDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.theme import apply_theme

    load_operations()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    apply_theme(app, "dark")
    install_catalog(language, read_catalog(language))
    set_language(language)
    install_qt_translations(app, language)

    # Der Stand eines Kunden, der schon ein wenig gearbeitet hat: Spulen im
    # Lager, den Hinweis zu den Druckeinstellungen gelesen, PrusaSlicer als
    # gewählten Slicer. Alles in diesem Profil und über dieselben Aufrufe, die
    # der Dialog selbst benutzt — nichts wird für die Dauer eines Bildes
    # vorgetäuscht.
    _stock_the_shelf(language)
    found = discover.find_programs("slicer", external_tools.SLICERS)
    prusa = next((one for one in found if "prusa" in one.name.lower()), None)
    if prusa is not None:
        discover.remember_path("slicer", str(prusa))
    settings = UiSettings()
    remember_disclosure(settings)

    session = Session()
    window = figures.prepared(MainWindow(session, settings), None, hidden=False)
    window.statusBar().hide()
    window.raise_()
    window.activateWindow()
    settle(40)

    # 1 Der Startbildschirm, zugeschnitten um seinen Inhalt. Ganz gezeigt
    # stünden seine Karten als kleine Insel mitten in 2560 Punkten Grund —
    # die Anwendung zentriert sie, und genau das ist auf einer Seite zu wenig.
    shot = grab(window)
    area = window_rect(window, window.start_screen)
    save_still(
        shot.copy(framed(content_rect(shot, area), STEP_RATIO, area, 56)),
        "schritt-start",
        language,
    )

    # 2 Ein Modell hereingezogen: die Ansicht und der Prüfbericht daneben.
    session.start_new()
    session.import_model(STEP_MODEL, raise_on_error=True)
    window._show_start_screen(False)
    until_quiet(app, session, STEP_MODEL.name)
    fill_view(window, "bericht")
    save_still(grab(window, work_rect(window, STEP_RATIO)), "schritt-bericht", language)

    # 3 Dasselbe Modell, die Druckeinstellungen darüber — geöffnet über den
    # Knopf der Anwendung, gewartet, bis die Slicersuche und die Profilsuche
    # durch sind (ein Bild mit „Die Slicer werden gesucht …" zeigte einen
    # Moment, keinen Zustand).
    def print_dialog(dialog: Any) -> None:
        if not dialog.wait_for_slicers():
            raise SystemExit("Die Slicersuche des Druckdialogs kam nicht zurück")
        for _ in range(200):
            if not dialog._profiles_pending:
                break
            settle(2)
        settle(20)
        crop = framed(frame_rect(window, dialog), STEP_RATIO, free_rect(window))
        save_still(grab(window, crop), "schritt-druck", language)

    while_open(PrintSettingsDialog, window.action_print_settings, print_dialog)
    settle(20)

    # 4 Der Prüfbericht mit etwas darin: das Beispiel, das mit einer Warnung
    # öffnet (``figures.REPORT_EXAMPLE``) — die Warnung kommt aus der
    # Auswertung, nicht aus diesem Werkzeug.
    open_example(window, app, figures.REPORT_EXAMPLE)
    fill_view(window, "bericht-beispiel")
    save_still(grab(window, work_rect(window, STEP_RATIO)), "beleg-bericht", language)

    # 4a Eine erkannte Bohrung, angeklickt: Maße im Bild, Handlungen rechts —
    # so, wie ein Klick im Objektbaum oder im Bild sie wählt.
    open_example(window, app, FEATURE_EXAMPLE[0])
    body = select_body(window, 0)
    fill_view(window, "merkmal")
    window.object_tree.select_feature(body, FEATURE_EXAMPLE[1])
    settle(40)
    if window.object_tree.selected_feature() != FEATURE_EXAMPLE[1]:
        raise SystemExit(f"Die Bohrung {FEATURE_EXAMPLE[1]} ließ sich nicht wählen")
    save_still(grab(window), "beleg-merkmal", language)
    window.object_tree.select_object(None)
    settle(10)

    # 5 Das Hauptfenster mit dem Schaustück. Die Lettern sind gewählt: Rechts
    # steht dann, was sich mit ihnen tun lässt, statt „Nichts gewählt".
    open_example(window, app, WEB_EXAMPLE)
    select_body(window, 1)
    fill_view(window, "fenster")
    save_still(grab(window), "beleg-fenster", language)
    # 5a Dasselbe als Vorschaubild für geteilte Links: Ansicht und Prüfbericht
    # im Verhältnis der Karte, ohne die linke Spalte — in der kleinen Karte
    # zählt das Teil.
    save_share(grab(window, work_rect(window, SHARE_SIZE[0] / SHARE_SIZE[1])), language)

    # 6 Eine Operation mit ihrem Dialog: am Schild eine Bohrung setzen. Der
    # Dialog ist nicht modal (Vorschau), er steht danach in ``_op_dialog`` —
    # rechts oben über der Karte des Prüfberichts. Deshalb das ganze Fenster:
    # Jeder Zuschnitt um Dialog und Modell schnitt entweder die Werkzeugleiste
    # („chern" von „Speichern") oder die Auswahlleiste daneben an.
    select_body(window, 0)
    fill_view(window, "dialog")
    window.run_operation(REGISTRY.get("drill_hole"))
    settle(40)
    dialog = window._op_dialog
    if dialog is None or not dialog.isVisible():
        raise SystemExit("Der Dialog „Bohrung setzen“ ging nicht auf")
    if not window.rect().contains(frame_rect(window, dialog)):
        raise SystemExit("Der Dialog „Bohrung setzen“ ragt aus dem Fenster — so kein Vollbild")
    save_still(grab(window), "beleg-dialog", language)
    dialog.reject()
    settle(20)

    # 7 Der Weg-2-Halter: an ihm wird gezeichnet, und aus ihm wird ein
    # eigener Baustein. Das Schild taugt für die Skizze nicht mehr: Seine
    # höchste nach oben zeigende Fläche ist die Deckfläche einer Letter
    # (11 mm²), und ein Rechteck von 50 mal 30 darauf zeigt nichts Echtes.
    open_example(window, app, PART_EXAMPLE)
    figures.frame_sketch(window, app)
    save_still(grab(window), "beleg-skizze", language)
    window.finish_sketch(keep=False)
    settle(20)

    # 8 Der Bausteinkatalog über dem Halter, und aus ihm heraus der Dialog für
    # einen eigenen Baustein — beides über die Knöpfe der Anwendung.
    # Geschnitten wird genau am Rahmen des Dialogs: Ein Rand drumherum zeigte
    # Streifen angeschnittener Leisten, und die lesen sich als Fehler.
    select_body(window, 0)
    fill_view(window, "fenster")

    def recipe(dialog: Any) -> None:
        settle(20)
        frame = frame_rect(window, dialog)
        crop = framed(frame, None, dialog_bounds(window, frame), 0)
        save_still(grab(window, crop), "beleg-eigener-baustein", language)

    def catalog(dialog: Any) -> None:
        # Genug für alle Vorschaubilder, eines je Durchlauf.
        settle(80)
        frame = frame_rect(window, dialog)
        crop = framed(frame, None, dialog_bounds(window, frame), 0)
        save_still(grab(window, crop), "beleg-bausteine", language)
        if not dialog.save_part.isEnabled():
            raise SystemExit(
                f"„Auswahl als Baustein speichern“ ist gesperrt: {dialog.save_hint.text()}"
            )
        while_open(RecipeDialog, dialog.save_part.click, recipe)

    while_open(PartCatalog, window.action_catalog, catalog)
    settle(20)

    # 9 Das Filamentlager, nach Lagerort gruppiert — über die Auswahl, die der
    # Kunde trifft. Nur das Regal mit seinen Gruppenüberschriften: Die volle
    # Such- und Filterzeile darüber gehört nicht in den schmalen Zuschnitt.
    window.action_inventory()
    settle(20)
    view = window._inventory_view
    view.grouping.setCurrentIndex(view.grouping.findData("location"))
    settle(30)
    expected = 6
    if len(view.cards) != expected:
        raise SystemExit(f"Das Regal zeigt {len(view.cards)} Spulen statt {expected}")
    shelf = window_rect(window, view.page_scroll.viewport())
    focus = QRect(shelf.topLeft(), QPoint(shelf.left() + 1, shelf.top() + 1))
    for card in view.cards:
        focus = focus.united(window_rect(window, card))
    save_still(grab(window, framed(focus, CARD_RATIO, shelf, 24)), "beleg-filamentlager", language)

    session.forget_changes()
    window.close()
    figures.release_viewport(window)
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


#: Die Motivgruppen, die ``--nur`` einzeln aufnehmen kann.
MOTIFS = ("fenster", "verwandlung")


def main() -> int:
    os.environ.pop("QT_QPA_PLATFORM", None)

    # Die Kindseite: ein Prozess, eine Sprache, eigene Nutzerverzeichnisse —
    # gestartet von ``take_screens``, nicht von Hand.
    if sys.argv[1:2] == ["--fenster"]:
        arguments = figures.chosen_screen(sys.argv[2:])
        if len(arguments) != 1:
            raise SystemExit("--fenster braucht genau eine Sprache, etwa: --fenster de")
        return _screens_child(arguments[0])

    # ``--nur <gruppe>`` nimmt eine Gruppe allein auf — etwa das
    # Verwandlungspaar, wenn sich nur das Beispielprojekt geändert hat. Ohne
    # den Schalter entsteht alles. ``--schirm N`` wählt den Zielschirm.
    arguments = figures.chosen_screen(list(sys.argv[1:]))
    only = ""
    if "--nur" in arguments:
        position = arguments.index("--nur")
        if position + 1 >= len(arguments) or arguments[position + 1] not in MOTIFS:
            raise SystemExit(f"--nur braucht eine Gruppe aus {', '.join(MOTIFS)}")
        only = arguments[position + 1]
        del arguments[position : position + 2]

    # Dieselbe Prüfung wie in ``make_figures``: Eine unbekannte Sprache gäbe
    # einen leeren Katalog, jedes ``tr()`` fiele auf Deutsch zurück, und der
    # Lauf endete mit „Fertig." — die Falle aus 229490a, über den anderen Weg.
    load_operations()
    wanted = figures.chosen_languages(tuple(arguments))
    for language in wanted:
        if only in ("", "fenster"):
            print(f"{language}:", flush=True)
            take_screens(language)
    if SOURCE_LANGUAGE in wanted and only in ("", "verwandlung"):
        # Das Verwandlungspaar trägt keinen Text und entsteht deshalb einmal,
        # nicht je Sprache (WD3).
        for target in take_transformation():
            print(f"  {target.name:<34} SVG")
    print("\nFertig. Die Maße gehören in die <img>-Angaben der Seiten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
