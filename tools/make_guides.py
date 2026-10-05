"""Die Bildanleitungen des Handbuchs aufnehmen — aus der echten Oberfläche.

    .venv\\Scripts\\python.exe tools/make_guides.py [sprachen …] [--nur ANLEITUNG]
        [--ziel ORDNER] [--film-ziel ORDNER] [--schirm N]

Jede Anleitung aus :mod:`app.core.guides` hat hier eine **Geschichte**: eine
Funktion, die den Weg der Anleitung durch die Oberfläche geht, jeden Schritt
abwartet und danach ein Bild nimmt. Auf das Bild kommen, was die Anleitung
verlangt: ein Rahmen um jedes Ziel, eine Nummer, bei kleinen Zielen ein Pfeil,
und der Rest leicht abgedunkelt. **Wo** ein Ziel steht, sagt
:mod:`app.ui.guide_targets` zur Aufnahmezeit, aus der Geometrie des echten
Widgets. Verschiebt sich ein Knopf, wandert der Rahmen mit.

**Beim Release, und nur dann** (Konzept Handbuch §6, Robert, 27.09.2026:
„immer aktuell … wenn wir eine neue version erstellen, zwischendrin brauchen
wir es nicht"). Der Lauf gehört in ``/erzeugen``, vor ``make_manual.py``.
Während der Entwicklung schreibt ``--ziel`` in einen Ordner außerhalb des
Baums; eingecheckt werden Bilder nur aus dem Release-Lauf.

**Laut scheitern ist die Aufgabe.** Fehlt ein Ziel, lässt sich ein Schritt
nicht gehen oder wird eine Auswertung nicht fertig, endet das Werkzeug mit
einem Fehler, der Anleitung und Schritt nennt — und der Release hält an. Die
Filmwerkzeuge daneben überspringen ein fehlendes Menü still, und zwei ihrer
drei Geschichten scheitern am 27.09.2026 an einem Knopf, den es nicht mehr
gibt, ohne dass es jemand gemerkt hätte (``konzepte/nachweise-handbuch-2026-09/
aufnahmetechnik.md``). Eine Anleitung, die nicht mehr stimmt, soll auffallen,
bevor ein Kunde sie liest.

Dieselben Bedingungen wie bei ``make_figures.py`` und ``make_web_images.py``,
aus denselben Gründen: nicht offscreen (dort fehlen die Schriften, und der
Viewport zeichnet nur auf einem echten Schirm), das Fenster maximiert auf dem
Zielschirm, in nativen Bildpunkten, gegriffen über den Bildschirm, damit
Menüs und Dialoge als eigene Fenster mit im Bild stehen. **Ein Prozess je
Sprache mit eigenen Nutzerverzeichnissen**: Die Geschichten öffnen Dateien
und merken sich Einstellungen, und nichts davon darf Roberts Profil
streifen.

Je Sprache schreibt der Lauf neben die Bilder ``guides.json``: je Anleitung
die Version, in der sie aufgenommen wurde, und den Abdruck ihrer
Beschreibung (:func:`app.core.guides.fingerprint`). Ein Test mit Marker
``rendered`` vergleicht beides mit dem heutigen Stand.

**Aus derselben Aufnahme entsteht je Schritt ein zweites Bild für den Film**
(``--film-ziel``, lokal unter ``marketing/``): in nativen Bildpunkten und so
groß wie die Fläche des 2K-Films (:func:`film_cut`), mit eigenem
``guides.json``. Das Handbuchbild bleibt der engere Ausschnitt, höchstens
:data:`MAX_WIDTH` breit — kleinere Bilder entstehen durch Verkleinern, nie
durch Hochrechnen.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QImage,
    QImageWriter,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    qGray,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QMenu,
    QTextEdit,
    QToolTip,
    QWidget,
)

from app.branding import APP_NAME, APP_VERSION
from app.core import figures, guides
from app.core.bootstrap import load_operations
from app.i18n import install_catalog, set_language, tr
from app.i18n.catalog import read_catalog
from tools import make_figures as shots
from tools import make_guide_video as film
from tools import make_web_images as web
from tools.make_web_images import ISOLATED_VARIABLES, framed, grab

#: Woran das Kind erkennt, dass es isoliert läuft (Muster ``make_web_images``).
ROOM_VARIABLE: Final = "SOLIDON_GUIDES_ROOM"

#: Das Beispiel, an dem die Anleitungen über das Fenster entstehen — dasselbe
#: wie das Hauptfensterbild des Handbuchs (``make_figures.EXAMPLE``): benannte
#: Maße, ein gefüllter Verlauf, erkannte Merkmale. Ein leeres Fenster zeigte
#: Bereiche, in denen nichts steht.
EXAMPLE: Final = shots.EXAMPLE

#: Die Netze, an denen die Anleitungen mit heruntergeladenen Modellen
#: entstehen — aus dem Korpus der Suite, nicht aus einem Beispielprojekt:
#: Ein Beispiel wird für seine eigene Tour gepflegt, und eine Änderung dort
#: soll nicht still das Handbuch verschieben.
MESHES: Final = Path(__file__).resolve().parent.parent / "tests" / "data" / "meshes"

#: Ein Netz mit offener Stelle, wie es aus dem Netz kommt: Der Prüfbericht hat
#: etwas zu sagen, und seine Handlung behebt es.
BROKEN_MODEL: Final = MESHES / "broken_open.stl"

#: Eine Platte mit ebener Oberseite und schon vorhandenen Löchern — dorthin
#: kommt in *Ein Loch bohren* eine weitere Bohrung.
PLATE_MODEL: Final = MESHES / "plate_holes.stl"

#: Ein Balken von 400 mm, länger als jedes Bett der Vorgabe — für
#: *Ein zu großes Teil teilen*.
OVERSIZED_MODEL: Final = MESHES / "oversized.stl"

#: Ein Würfel mit einer großen Öffnung, die Solidon beim Einlesen schließt,
#: und einer, deren Stelle der Bericht zeigt — für *Ein Modell reparieren*.
OPEN_MODEL: Final = MESHES / "partially_open.stl"

#: Zwei Teile, die ineinanderstecken: Der Bericht bietet an, sie aufzulösen.
CROSSING_MODEL: Final = MESHES / "broken_selfint.stl"

SPOOL_COLOURS: Final = ("#f2f2ee", "#c8372d")


def _spool_names() -> tuple[str, str]:
    """Die Namen der Aufnahme aus dem aktiven Katalog bilden."""
    return f"PLA {tr('Weiß').lower()}", f"PLA {tr('Rot').lower()}"


#: Wie breit ein Schrittbild höchstens gespeichert wird. Die Bilder reisen mit
#: der Anwendung, sechs Sprachen lang; das Handbuchfenster zeigt sie ohnehin
#: in der Breite seiner Textspalte.
MAX_WIDTH: Final = 1600

#: Wie viel Umgebung ein Schritt um seine Ziele zeigt, in nativen Bildpunkten
#: — genug, damit man erkennt, wo im Fenster man ist.
MARGIN: Final = 220

#: Das Seitenverhältnis eines Ausschnitts.
RATIO: Final = 16 / 10

#: Unter dieser Kantenlänge bekommt ein Ziel einen Pfeil: Ein Rahmen um einen
#: Menüeintrag oder einen kleinen Knopf ist auf einer Handbuchseite schnell
#: übersehen.
SMALL: Final = 56

#: Innenabstand zwischen Ziel und Rahmen.
PADDING: Final = 6

#: Radius der Nummernscheibe.
BADGE: Final = 17

#: Wie weit die Nummer eines kleinen Ziels abgesetzt steht, damit ein Pfeil
#: zwischen beide passt.
AWAY: Final = 64

#: Der Rand um das Bildschirmfoto. Die Nummer sitzt auf der linken oberen
#: Ecke ihres Rahmens, halb innen, halb außen; am Fensterrand stünde sie ohne
#: diesen Rand über dem Menü oder dem ersten Knopf — so verdeckte die Nummer
#: der Werkzeugleiste im ersten Probelauf das Wort „Datei".
BORDER: Final = 2 * (BADGE + 3) + 8

#: Wie stark der Rest des Bildes zurücktritt.
DIM: Final = QColor(0, 0, 0, 105)

#: Wie viel Unruhe (:func:`_busyness`, mittlere Helligkeitsabweichung) eine
#: Stelle für die Nummer ruhiger sein muss als die vor ihr in der Reihenfolge.
#: Leere Flächen der Oberfläche liegen unter drei, Schrift über zwanzig; bei
#: sechzehn Stellen bleibt die Vorliebe damit unter dem Abstand zur Schrift.
CALM_ORDER: Final = 0.5

#: Wo entlang des Pfeils gemessen wird, als Anteil des Wegs von der Nummer zur
#: Spitze.
PATH_SHARES: Final = (0.25, 0.4, 0.55, 0.7, 0.82)


#: Die Qualität der WebP-Bilder. 86 wie bei den Website-Bildern
#: (``make_web_images``): Die Schrift der Oberfläche bleibt scharf, und das
#: Übersichtsbild misst 85 statt 408 KB als PNG.
QUALITY: Final = 86


def film_cut(focus: QRect, bounds: QRect, size: tuple[int, int]) -> QRect:
    """Der Ausschnitt eines Filmbilds um ``focus``: mindestens so groß wie die Bildfläche des Films.

    Mindestens die Fläche, die der Film für ihn freihält, abzüglich des Rands,
    den :func:`annotate` anlegt, und immer das Gezeigte samt :data:`MARGIN` —
    der Film verkleinert dann höchstens (Robert, 04.10.2026: „wenn wir kleinere
    Bilder benötigen, davon herunterskalieren"). Ein Gezeigtes, das höher ist
    als das breite Filmformat, bekommt seinen ganzen Ausschnitt, und der Film
    setzt ihn kleiner hinein; wo das Fenster kleiner ist als die Fläche,
    bleibt es beim ganzen Fenster.
    """
    reach = focus.adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN).intersected(bounds)
    width = min(max(size[0] - 2 * BORDER, reach.width()), bounds.width())
    height = min(max(size[1] - 2 * BORDER, reach.height()), bounds.height())
    left = reach.left() + (reach.width() - width) // 2
    top = reach.top() + (reach.height() - height) // 2
    left = min(max(left, bounds.left()), bounds.right() + 1 - width)
    top = min(max(top, bounds.top()), bounds.bottom() + 1 - height)
    cut = QRect(left, top, width, height)
    if not cut.contains(focus):
        raise SystemExit(
            f"Der Filmausschnitt {cut.getRect()} fasst das Gezeigte {focus.getRect()} nicht."
        )
    return cut


def _picture_path(folder: Path, key: str) -> Path:
    """Wohin das Bild eines Schritts gehört — mit der Endung, die der Katalog nennt."""
    figure = figures.find(key)
    if figure is None:
        raise SystemExit(f"{key}: keine Abbildung dieses Namens im Katalog")
    return folder / figure.path().name


@dataclass(frozen=True, slots=True)
class Spot:
    """Ein Ziel im Bild, in Bildkoordinaten."""

    rect: QRect
    point: bool = False
    """Ein Punkt statt eines Bereichs — ein Ring um eine Stelle im Modell."""
    pointer: bool = False
    """Am Punkt steht der Mauszeiger mit Klickring: Hier wird geklickt. Ohne ihn
    zeigt der Ring nur, wo etwas zu sehen ist — die Vorschau eines Lochs ist
    keine Stelle zum Klicken."""


# --- Zeichnen -------------------------------------------------------------------


def _palette() -> dict[str, str]:
    from app.ui.theme import THEMES

    return THEMES["dark"]


def annotate(
    piece: QImage,
    spots: list[Spot],
    *,
    legend: bool,
    number: int,
    protected: tuple[QRect, ...] = (),
) -> QImage:
    """Das Bildschirmfoto mit Rand, Rahmen, Nummern und Pfeilen.

    Ein gewöhnlicher Schritt dunkelt alles außer seinen Zielen ab; das erste
    Ziel trägt die Nummer des Schritts, weitere nur einen Rahmen. Eine Legende
    dunkelt nicht ab — sie zeigt das ganze Fenster —, und jedes Ziel trägt
    seine eigene Nummer. Die Nummer ist die zweite Kodierung neben der Farbe
    (Regel 18). ``spots`` steht in den Koordinaten von ``piece``.
    """
    palette = _palette()
    amber, ink = QColor(palette["highlight"]), QColor(palette["highlight_text"])
    halo = QColor(ink.red(), ink.green(), ink.blue(), 190)
    canvas = QImage(
        piece.width() + 2 * BORDER,
        piece.height() + 2 * BORDER,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    canvas.fill(QColor(palette["base"]))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.drawImage(BORDER, BORDER, piece)
    shot = QRectF(BORDER, BORDER, piece.width(), piece.height())
    frames = [frame.translated(BORDER, BORDER) for frame in _frames(spots)]

    if not legend and frames:
        shade = QPainterPath()
        shade.setFillRule(Qt.FillRule.OddEvenFill)
        shade.addRect(shot)
        for spot, frame in zip(spots, frames, strict=True):
            if spot.point:
                shade.addEllipse(frame)
            else:
                shade.addRoundedRect(frame, 8, 8)
        painter.fillPath(shade, DIM)
    painter.setPen(QPen(QColor(palette["line"]), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(shot.adjusted(-0.5, -0.5, 0.5, 0.5))

    for spot, frame in zip(spots, frames, strict=True):
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for colour, width in ((halo, 7.0), (amber, 3.5)):
            painter.setPen(QPen(colour, width))
            if spot.point:
                painter.drawEllipse(frame)
            else:
                painter.drawRoundedRect(frame, 8, 8)

    taken: list[QPointF] = []
    bounds = QRectF(canvas.rect())
    for index, (spot, frame) in enumerate(zip(spots, frames, strict=True), start=1):
        label = index if legend else (number if index == 1 else None)
        if label is None:
            continue
        away = not legend and _small(spot)
        others = [other for other in frames if other is not frame]
        centre = _badge_centre(
            frame,
            others,
            bounds,
            taken,
            away=away,
            picture=piece,
            protected=[QRectF(area.translated(BORDER, BORDER)) for area in protected],
        )
        taken.append(centre)
        if away or not frame.contains(centre):
            _arrow(painter, centre, frame, amber, halo)
        _badge(painter, centre, str(label), amber, ink)
    painter.end()

    for spot in spots:
        if spot.pointer:
            _pointer(canvas, spot.rect.center() + QPoint(BORDER, BORDER))
    return canvas


def _shows_the_window(image: QImage, window: Any) -> bool:
    """Ob die Menüzeile im Bild die ist, die Qt für dieses Fenster zeichnet.

    Verglichen wird an einem Raster von 20 mal 20 Punkten. Kantenglättung und ein Farbstich
    zählen nicht; liegt aber ein anderes Fenster darüber, weicht mehr als ein
    Fünftel der Punkte deutlich ab.
    """
    bar = window.menuBar()
    if bar is None or not bar.isVisible():
        return True
    drawn = bar.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    corner = bar.mapTo(window, QPoint(0, 0))
    shown = image.copy(QRect(corner, drawn.size())).convertToFormat(QImage.Format.Format_RGB32)
    if shown.size() != drawn.size() or drawn.width() < 20 or drawn.height() < 4:
        return True
    wrong = 0
    for column in range(20):
        for row in range(20):
            x = (drawn.width() - 1) * column // 19
            y = (drawn.height() - 1) * row // 19
            expected, found = QColor(drawn.pixel(x, y)), QColor(shown.pixel(x, y))
            apart = (
                abs(expected.red() - found.red())
                + abs(expected.green() - found.green())
                + abs(expected.blue() - found.blue())
            )
            wrong += apart > 90
    return wrong <= 80


def _small(spot: Spot) -> bool:
    return spot.point or min(spot.rect.width(), spot.rect.height()) < SMALL


def _frame(spot: Spot) -> QRectF:
    """Der Rahmen um ein Ziel. Ein Punkt ohne eigene Größe bekommt einen Ring
    von fester Größe; eine Stelle mit Größe — ein Loch, auf den Schirm
    projiziert — einen Ring, der sie umschließt."""
    if spot.point and spot.rect.width() <= 1 and spot.rect.height() <= 1:
        centre = QPointF(spot.rect.center())
        return QRectF(centre.x() - 22, centre.y() - 22, 44, 44)
    return QRectF(spot.rect).adjusted(-PADDING, -PADDING, PADDING, PADDING)


def _frames(spots: list[Spot]) -> list[QRectF]:
    """Die Rahmen um die Ziele — enger, wo zwei sonst ineinandergriffen.

    Einträge eines Menüs stehen Zeile an Zeile. Mit dem gewöhnlichen Abstand
    griff jeder Rahmen in die Nachbarzeile, und zwei Rahmen deckten die Zeile
    dazwischen zu (*Nach unten* im Kontextmenü des Verlaufs, Durchsicht
    28.09.2026). Wo zwei Ziele näher beieinander stehen als zwei Abstände,
    teilen sie sich den Platz dazwischen.
    """
    padding = [float(PADDING)] * len(spots)
    for first, one in enumerate(spots):
        for second in range(first + 1, len(spots)):
            other = spots[second]
            if one.point or other.point or one.rect.intersects(other.rect):
                continue
            gap = max(
                other.rect.left() - one.rect.right(),
                one.rect.left() - other.rect.right(),
                other.rect.top() - one.rect.bottom(),
                one.rect.top() - other.rect.bottom(),
            )
            if gap > 2 * PADDING:
                continue
            room = max(0.0, (gap - 1) / 2)
            padding[first] = min(padding[first], room)
            padding[second] = min(padding[second], room)
    return [
        _frame(spot) if spot.point else QRectF(spot.rect).adjusted(-pad, -pad, pad, pad)
        for spot, pad in zip(spots, padding, strict=True)
    ]


def _reach(spot: Spot) -> QRect:
    """Was ein Ausschnitt um ein Ziel mindestens zeigen muss: Rahmen, Nummer, Pfeil."""
    frame = _frame(spot)
    extra = AWAY + BADGE if _small(spot) else BADGE
    return frame.adjusted(-extra, -extra, extra, extra).toAlignedRect()


def _badge_centre(
    frame: QRectF,
    others: list[QRectF],
    bounds: QRectF,
    taken: list[QPointF],
    *,
    away: bool,
    picture: QImage | None = None,
    protected: list[QRectF] | None = None,
) -> QPointF:
    """Wo die Nummer steht — und nie auf einem anderen Bereich.

    Zuerst auf der linken oberen Ecke des Rahmens, halb innen, halb außen: So
    liest man sie als Etikett dieses Rahmens. Grenzt dort ein anderer Rahmen
    an (die Ansicht beginnt genau unter der Werkzeugleiste), wird die nächste
    Stelle versucht: in die Ecke hinein, links oder rechts neben den Rahmen,
    auf die Mitte der Oberkante. Eine Nummer, die auf einem fremden Bereich
    steht, zeigte auf den falschen. Ein kleines Ziel bekommt seine Nummer
    abgesetzt, damit der Pfeil dazwischen passt.

    **Unter den freien Stellen die ruhigste** (Durchsicht 28.09.2026): Die
    erste freie verdeckte die Beschriftung eines Nachbarfelds, und ein
    Pfeil kreuzte einen Hinweissatz. Gemessen wird am Bildschirmfoto
    (:func:`_busyness`), unter der Nummer und entlang des Pfeils; bei
    gleicher Ruhe gilt die Reihenfolge unten. Eine abgesetzte Nummer hat dafür
    acht Richtungen in zwei Abständen: Mit den vier Ecken allein lag in einem
    dichten Dialog jede Stelle auf Text.
    """
    reach = BADGE + 3
    middle = frame.center()
    if away:
        candidates = [
            spot
            for distance in (AWAY, AWAY * 1.6)
            for spot in (
                QPointF(frame.left() - distance, frame.top() - distance),
                QPointF(frame.right() + distance, frame.top() - distance),
                QPointF(frame.left() - distance, frame.bottom() + distance),
                QPointF(frame.right() + distance, frame.bottom() + distance),
                QPointF(frame.left() - distance - BADGE, middle.y()),
                QPointF(frame.right() + distance + BADGE, middle.y()),
                QPointF(middle.x(), frame.top() - distance),
                QPointF(middle.x(), frame.bottom() + distance),
            )
        ]
    else:
        # In die Ecke hinein erst zuletzt: Dort verdeckt die Nummer den Inhalt
        # ihres eigenen Bereichs — im Probelauf das erste Wort der Werkzeugzeile.
        candidates = [
            frame.topLeft(),
            QPointF(frame.left() - BADGE - 8, middle.y()),
            QPointF(frame.right() + BADGE + 8, middle.y()),
            QPointF(middle.x(), frame.top()),
            QPointF(frame.left() + BADGE + 10, frame.top() + BADGE + 10),
        ]

    def free(centre: QPointF) -> bool:
        disc = QRectF(centre.x() - reach, centre.y() - reach, 2 * reach, 2 * reach)
        return (
            bounds.contains(disc)
            and not any(other.intersects(disc) for other in others)
            and not any(area.intersects(disc) for area in protected or ())
            and all(
                abs(centre.x() - spot.x()) > 2 * BADGE + 4
                or abs(centre.y() - spot.y()) > 2 * BADGE + 4
                for spot in taken
            )
        )

    def unrest(centre: QPointF) -> float:
        score = _busyness(picture, centre, reach)
        if away:
            tip = QPointF(
                min(max(centre.x(), frame.left()), frame.right()),
                min(max(centre.y(), frame.top()), frame.bottom()),
            )
            # Die unruhigste Stelle des Wegs zählt: Eine einzige Textzeile,
            # die der Pfeil kreuzt, stört, auch wenn der Rest leer ist. Kurz
            # vor der Spitze wird nicht gemessen, dort beginnt das Ziel selbst.
            path = [centre + (tip - centre) * share for share in PATH_SHARES]
            score += max(_busyness(picture, point, 5.0) for point in path)
        return score

    usable = [rank for rank, centre in enumerate(candidates) if free(centre)]
    if not usable:
        # Ein dichter Dialog kann ringsum nur Text tragen. Im zusätzlichen
        # Bildrand bleibt ein sicherer Platz; eine Nummer verdeckt nie Text.
        margin = BADGE + 3
        candidates = [
            point
            for distance in range(margin, int(bounds.width()) - margin, 2 * margin + 4)
            for point in (QPointF(distance, margin), QPointF(distance, bounds.bottom() - margin))
        ] + [
            point
            for distance in range(margin, int(bounds.height()) - margin, 2 * margin + 4)
            for point in (QPointF(margin, distance), QPointF(bounds.right() - margin, distance))
        ]
        usable = [rank for rank, centre in enumerate(candidates) if free(centre)]
        if not usable:
            raise ValueError("Kein freier Platz für die Schrittnummer; Bildausschnitt vergrößern.")
        return min(
            (candidates[rank] for rank in usable),
            key=lambda point: (point.x() - middle.x()) ** 2 + (point.y() - middle.y()) ** 2,
        )
    chosen = candidates[
        min(usable, key=lambda rank: unrest(candidates[rank]) + CALM_ORDER * rank) if usable else 0
    ]
    x = min(max(chosen.x(), bounds.left() + reach), bounds.right() - reach)
    y = min(max(chosen.y(), bounds.top() + reach), bounds.bottom() - reach)
    return QPointF(x, y)


def _text_areas(window: QWidget) -> tuple[QRect, ...]:
    """Sichtbare Textträger einschließlich Menüs und Dialogen sperren.

    Listen werden ganz gesperrt: Delegates zeichnen ihren Text selbst und
    tragen keine eigenen Widgets. So bleibt auch eine übersetzte Zeile frei.
    """
    origin = window.mapToGlobal(QPoint())
    kinds = (
        QAbstractButton,
        QAbstractItemView,
        QAbstractSpinBox,
        QComboBox,
        QLabel,
        QLineEdit,
        QMenu,
        QTextEdit,
    )
    areas = []
    for top in QApplication.topLevelWidgets():
        if top is not window and not window.isAncestorOf(top):
            continue
        for widget in (top, *top.findChildren(QWidget)):
            if isinstance(widget, kinds) and widget.isVisible():
                areas.append(QRect(widget.mapToGlobal(QPoint()) - origin, widget.size()))
    return tuple(areas)


def _busyness(picture: QImage | None, centre: QPointF, radius: float) -> float:
    """Wie unruhig das Bildschirmfoto um einen Punkt der Leinwand ist.

    Die mittlere Abweichung der Helligkeit, jeder dritte Bildpunkt: Schrift
    und Kanten liegen weit darüber, eine leere Fläche nahe null. Der Rand
    um das Foto zählt als ruhig.
    """
    if picture is None:
        return 0.0
    left = int(centre.x() - radius) - BORDER
    top = int(centre.y() - radius) - BORDER
    size = max(1, int(2 * radius))
    values = [
        qGray(picture.pixel(x, y))
        for y in range(max(0, top), min(picture.height(), top + size), 3)
        for x in range(max(0, left), min(picture.width(), left + size), 3)
    ]
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum(abs(value - mean) for value in values) / len(values)


def _badge(painter: QPainter, centre: QPointF, text: str, amber: QColor, ink: QColor) -> None:
    painter.setPen(QPen(ink, 3))
    painter.setBrush(amber)
    painter.drawEllipse(centre, BADGE, BADGE)
    font = QFont(painter.font())
    font.setBold(True)
    font.setPixelSize(20)
    painter.setFont(font)
    painter.setPen(ink)
    painter.drawText(
        QRectF(centre.x() - BADGE, centre.y() - BADGE, 2 * BADGE, 2 * BADGE),
        int(Qt.AlignmentFlag.AlignCenter),
        text,
    )


def _arrow(painter: QPainter, start: QPointF, frame: QRectF, amber: QColor, halo: QColor) -> None:
    """Ein Pfeil von der Nummer zum nächsten Punkt des Rahmens."""
    tip = QPointF(
        min(max(start.x(), frame.left()), frame.right()),
        min(max(start.y(), frame.top()), frame.bottom()),
    )
    dx, dy = tip.x() - start.x(), tip.y() - start.y()
    length = (dx * dx + dy * dy) ** 0.5
    if length < BADGE + 12:
        return
    ux, uy = dx / length, dy / length
    begin = QPointF(start.x() + ux * (BADGE + 2), start.y() + uy * (BADGE + 2))
    head = 14.0
    base = QPointF(tip.x() - ux * head, tip.y() - uy * head)
    left = QPointF(base.x() - uy * head * 0.6, base.y() + ux * head * 0.6)
    right = QPointF(base.x() + uy * head * 0.6, base.y() - ux * head * 0.6)
    for colour, width in ((halo, 8.0), (amber, 4.0)):
        painter.setPen(QPen(colour, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(begin, base)
    painter.setPen(QPen(halo, 2))
    painter.setBrush(amber)
    painter.drawPolygon(QPolygonF([tip, left, right]))


def _pointer(image: QImage, spot: QPoint) -> None:
    """Der Mauszeiger mit Klickring — derselbe wie in den Filmen."""
    from tools.make_video import _paint_pointer

    _paint_pointer(image, (float(spot.x()), float(spot.y()), True))


# --- Ein Lauf durch eine Anleitung --------------------------------------------------


class GuideRun:
    """Was eine Geschichte braucht: das Fenster, und wie man einen Schritt aufnimmt."""

    def __init__(
        self, app: QApplication, window: Any, guide: guides.Guide, folder: Path, frames: Path
    ) -> None:
        self.app = app
        self.window = window
        self.session = window.session
        self.guide = guide
        self.folder = folder
        self.frames = frames
        self.taken = 0

    def settle(self, rounds: int = 12) -> None:
        shots.settle(self.app, rounds)

    def capture(
        self,
        number: int,
        *,
        points: dict[str, QPoint] | None = None,
        rings: dict[str, QPoint | QRect] | None = None,
    ) -> None:
        """Den Zustand für Schritt ``number`` aufnehmen, markiert und zugeschnitten.

        ``points`` setzt für ein Ziel einen Punkt mit Mauszeiger statt seines
        Rahmens: dort, wo die Geschichte in die Ansicht geklickt hat. ``rings``
        setzt einen Ring ohne Zeiger: eine Stelle, an der etwas zu sehen ist,
        als Punkt oder als Rechteck, das der Ring umschließt. Beides global,
        wie ``mapToGlobal`` es liefert.
        """
        from app.ui import guide_targets

        if number != self.taken + 1:
            raise SystemExit(
                f"{self.guide.key}: Schritt {number} aufgenommen, erwartet war {self.taken + 1}"
            )
        step = self.guide.steps[number - 1]
        self.settle()
        origin = self.window.mapToGlobal(QPoint(0, 0))

        def located() -> list[Spot]:
            spots: list[Spot] = []
            for mark in step.marks:
                if points and mark.target in points:
                    where = points[mark.target] - origin
                    spots.append(Spot(QRect(where, QSize(1, 1)), point=True, pointer=True))
                    continue
                if rings and mark.target in rings:
                    ring = rings[mark.target]
                    box = ring if isinstance(ring, QRect) else QRect(ring, QSize(1, 1))
                    spots.append(Spot(box.translated(-origin), point=True))
                    continue
                try:
                    area = guide_targets.area_for(self.window, mark.target)
                except guide_targets.MissingTargetError as missing:
                    raise SystemExit(f"{self.guide.key}, Schritt {number}: {missing}") from missing
                spots.append(Spot(area.translated(-origin)))
            return spots

        # Zweimal gefragt: Die erste Frage rollt ein Ziel in den Blick, und erst
        # nach dem nächsten Bildaufbau zeigt der Schirm, wo der Rahmen sitzt.
        # Im Probelauf stand der Rahmen um *Verrunden*, das Bild noch auf dem
        # alten Rollstand, und gerahmt war der Knopf darüber.
        located()
        self.settle(8)
        spots = located()
        image = self._grab(number)
        focus = QRect()
        if step.whole_window:
            crop = image.rect()
        else:
            for spot in spots:
                focus = focus.united(_reach(spot))
            # Ein offenes Menü steht ganz im Bild, mit seinem Titel im
            # Menübalken: Markiert ist der Eintrag, gefunden wird er über den
            # Weg dorthin.
            menus = _open_menu_area(self.window)
            if not menus.isNull():
                focus = focus.united(menus.translated(-origin))
            crop = framed(focus.intersected(image.rect()), RATIO, image.rect(), MARGIN)
        protected = _text_areas(self.window)

        def marked(cut: QRect) -> QImage:
            corner = cut.topLeft()
            return annotate(
                image.copy(cut),
                [Spot(spot.rect.translated(-corner), spot.point, spot.pointer) for spot in spots],
                legend=step.is_legend,
                number=number,
                protected=tuple(area.translated(-corner) for area in protected),
            )

        picture = marked(crop)
        if picture.width() > MAX_WIDTH:
            picture = picture.scaledToWidth(MAX_WIDTH, Qt.TransformationMode.SmoothTransformation)
        key = self.guide.figure_key(number)
        self._write(picture, _picture_path(self.folder, key))
        # **Das Filmbild aus derselben Aufnahme**, in nativen Bildpunkten und
        # so groß wie die Fläche im 2K-Film; ein ganzes Fenster bleibt ganz.
        cut = (
            image.rect()
            if step.whole_window
            else film_cut(
                focus.intersected(image.rect()),
                image.rect(),
                film.picture_size(step.is_legend),
            )
        )
        self._write(marked(cut), _picture_path(self.frames, key))
        self.taken = number

    @staticmethod
    def _write(picture: QImage, target: Path) -> None:
        writer = QImageWriter(str(target), target.suffix.lstrip(".").encode("ascii"))
        writer.setQuality(QUALITY)
        if not writer.write(picture):
            raise SystemExit(f"{target} ließ sich nicht schreiben: {writer.errorString()}")
        size = target.stat().st_size // 1024
        shown = f"{target.parent.name}/{target.name}"
        print(f"  {shown:<44} {picture.width()}x{picture.height()}  {size} KB")

    def _grab(self, number: int) -> QImage:
        """Das Fenster vom Schirm, und nur, wenn darauf wirklich das Fenster steht.

        Am 27.09.2026 zeigte ein Ergebnisbild statt Solidon das Fenster der
        Claude-Sitzung: Es war in dem Augenblick nach vorn gekommen, und die
        Prüfung auf fremde Fenster kurz davor hatte nichts gesehen. Deshalb
        dreierlei: das eigene Fenster vor jedem Bild wieder obenauf, dieselbe
        Prüfung auch nach dem Abgreifen, und die Menüzeile im Bild gegen die,
        die Qt selbst zeichnet — fremder Inhalt darüber fällt dort auf.
        """
        for _attempt in range(10):
            _stay_on_top(self.window)
            # Ein Tooltip ist ein eigenes Fenster über dem Aufnahmefenster und
            # käme mit ins Bild: Im Portugiesischen stand „Dividido: 2 · 2
            # Ajustes“ über dem Verlauf der Teilen-Anleitung (Release 0.5.1).
            QToolTip.hideText()
            self.settle(2)
            image = grab(self.window)
            other = shots.foreign_window_over(self.window)
            if not other and _shows_the_window(image, self.window):
                return image
            print(
                f"  … über Schritt {number} lag beim Abgreifen etwas anderes "
                f"({other or 'fremder Inhalt'}), noch einmal",
                flush=True,
            )
            self.settle(40)
        raise SystemExit(
            f"{self.guide.key}, Schritt {number}: Das Bild zeigte zehnmal nicht das "
            "Aufnahmefenster. Fremde Fenster vom Aufnahmeschirm nehmen (--schirm N)."
        )

    def finish(self) -> None:
        if self.taken != len(self.guide.steps):
            raise SystemExit(
                f"{self.guide.key}: {self.taken} von {len(self.guide.steps)} Schritten aufgenommen"
            )


# --- Die Geschichten ------------------------------------------------------------------
#
# Die Wege durch die Oberfläche, die es schon gibt, kommen aus
# ``make_web_images`` — dort öffnet ``open_example`` ein Beispiel ohne die
# Zuletzt-Liste, ``select_body`` wählt wie ein Klick im Objektbaum und
# ``until_quiet`` wartet auch den Prüfbericht ab. Eine zweite Fassung davon
# hier wäre ein Zwilling, der beim nächsten Umbau auseinanderläuft.


def _fresh(run: GuideRun) -> None:
    """Zurück auf den Startbildschirm, ohne gespeicherte Änderung."""
    run.session.forget_changes()
    run.session.start_new()
    run.window._show_start_screen(True)
    run.settle(20)


def _import(run: GuideRun, model: Path) -> None:
    """Ein Modell einlesen wie hereingezogen und alles abwarten, den Prüfbericht eingeschlossen."""
    if not model.is_file():
        raise SystemExit(f"Anleitungsmodell fehlt: {model}")
    run.session.start_new()
    run.session.import_model(model, raise_on_error=True)
    run.window._show_start_screen(False)
    web.until_quiet(run.app, run.session, model.name)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(20)


def story_window_overview(run: GuideRun) -> None:
    """Das ganze Fenster mit einem gewählten Körper: alle Bereiche gefüllt."""
    web.open_example(run.window, run.app, EXAMPLE)
    web.select_body(run.window, 0)
    run.window.right.setCurrentWidget(run.window.report)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    run.capture(1)


def _visible(run: GuideRun, world: tuple[float, float, float]) -> QPoint:
    """Wo ein Weltpunkt auf dem Schirm steht — global, für ``capture(points=…)``."""
    from tools.make_video import _world_to_window

    x, y = _world_to_window(run.window, world)
    return run.window.mapToGlobal(QPoint(round(x), round(y)))


def _top_face(entry: Any) -> tuple[str, Any]:
    """Die größte nach oben zeigende Fläche eines Körpers — dorthin kommt das Loch."""
    faces = [
        (feature_id, feature)
        for feature_id, feature in entry.features.items()
        if feature.kind == "face" and float(feature.params["normal"][2]) > 0.99
    ]
    if not faces:
        raise SystemExit("Der Körper hat keine Fläche, die nach oben zeigt")
    return max(faces, key=lambda item: float(item[1].params["area"]))


def _menu_trail(window: Any, action: QAction) -> list[QAction]:
    """Die Aktionen vom Menübalken bis zu ``action``: Titel, Untermenüs, Eintrag."""

    def walk(actions: list[QAction]) -> list[QAction] | None:
        for candidate in actions:
            if candidate is action:
                return [candidate]
            sub = candidate.menu()
            if isinstance(sub, QMenu):
                below = walk(sub.actions())
                if below is not None:
                    return [candidate, *below]
        return None

    trail = walk(window.menuBar().actions())
    if trail is None:
        raise SystemExit(f"„{action.text()}“ steht in keinem Menü")
    return trail


def _open_menu(run: GuideRun, action: QAction) -> None:
    """Das Menü bis zu ``action`` aufklappen und den Eintrag hervorheben, wie mit der Maus.

    Ausgelöst wird nichts: Den Eintrag führt die Geschichte danach selbst aus,
    wenn das Bild steht und die Menüs wieder zu sind.
    """
    trail = _menu_trail(run.window, action)
    run.window.menuBar().setActiveAction(trail[0])
    run.settle(10)
    menu = trail[0].menu()
    for step in trail[1:]:
        if not isinstance(menu, QMenu) or not menu.isVisible():
            raise SystemExit(f"Das Menü vor „{step.text()}“ ging nicht auf")
        menu.setActiveAction(step)
        run.settle(10)
        menu = step.menu()
    run.settle(20)


def _close_menus(run: GuideRun) -> None:
    """Alle offenen Menüs schließen, ohne einen Eintrag auszulösen."""
    for _attempt in range(10):
        popup = QApplication.activePopupWidget()
        if popup is None:
            break
        popup.close()
        run.settle(4)
    run.settle(10)


def _open_menu_area(window: Any) -> QRect:
    """Wo gerade Menüs offen sind, samt ihrem Titel im Menübalken; global, leer ohne Menü."""
    area = QRect()
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMenu) and widget.isVisible():
            area = area.united(QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size()))
    if area.isNull():
        return area
    bar = window.menuBar()
    active = bar.activeAction()
    if active is not None:
        title = bar.actionGeometry(active)
        area = area.united(QRect(bar.mapToGlobal(title.topLeft()), title.size()))
    return area


def story_drill_a_hole(run: GuideRun) -> None:
    """Teil wählen, Fläche wählen, Bohrung setzen, im Verlauf wiederfinden."""
    from app.ui import guide_targets

    _import(run, PLATE_MODEL)
    body = web.select_body(run.window, 0)
    result = run.session.last_result
    if result is None:
        raise SystemExit(f"{PLATE_MODEL.name}: keine Auswertung")
    face_id, face = _top_face(result.scene.objects[body])
    centre = tuple(float(value) for value in face.params["centre"])
    run.capture(1, points={"viewport": _visible(run, (centre[0], centre[1], centre[2]))})

    run.window.object_tree.select_feature(body, face_id)
    run.settle(30)
    # Neben die Mitte, damit der Klick nicht in einem der vorhandenen Löcher liegt.
    spot = (centre[0] + 12.0, centre[1], centre[2])
    run.capture(2, points={"viewport": _visible(run, spot)})

    run.capture(3)
    guide_targets.widget_for(run.window, "operation:drill_hole").click()
    run.settle(40)
    dialog = run.window._op_dialog
    if dialog is None or not dialog.isVisible():
        raise SystemExit("Der Dialog „Bohrung setzen“ ging nicht auf")
    dialog._editors["diameter"].set_value(5.0)
    run.settle(40)
    run.capture(4)
    run.capture(5)
    # Wo das Loch sitzt: die Werte des Dialogs, die er aus der gewählten
    # Fläche übernommen hat, gelesen vor dem Schließen.
    chosen = dialog.values()
    mouth = (float(chosen["x"]), float(chosen["y"]), float(chosen["z"]))
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Bohrung")
    # Ohne Auswahl und näher heran: Das Werkzeugkreuz einer gewählten Fläche
    # läge sonst über dem Loch, und fünf Millimeter in einer Platte von
    # hundert sind aus der Ferne ein Punkt. Ein Ring ohne Zeiger — hier wird
    # nicht geklickt, hier ist etwas zu sehen.
    run.window.object_tree.select_object(None)
    run.window.viewport.reset_camera(follow_selection=False)
    run.window.viewport.zoom(2.5)
    run.settle(30)
    # Der Ring umschließt das Loch: sein Rand, auf den Schirm projiziert.
    radius = float(chosen["diameter"]) / 2.0
    rim = [
        _visible(run, (mouth[0] + dx, mouth[1] + dy, mouth[2]))
        for dx, dy in ((radius, 0.0), (-radius, 0.0), (0.0, radius), (0.0, -radius))
    ]
    xs, ys = [point.x() for point in rim], [point.y() for point in rim]
    hole = QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys)))
    run.capture(6, rings={"viewport": hole})
    run.capture(7)

    # Der Doppelklick aus Schritt 7, wie ihn der Kunde macht, und im wieder
    # geöffneten Dialog die Lage: Die Kurzfassung verspricht das Verschieben.
    history = run.window.history_panel.list
    history.itemDoubleClicked.emit(history.item(history.count() - 1))
    run.settle(40)
    dialog = run.window._op_dialog
    if dialog is None or not dialog.isVisible():
        raise SystemExit("Der Schritt „Bohrung setzen“ ging im Verlauf nicht wieder auf")
    # Die Lage steht hinter der Klappe, wie beim Kunden: aufklappen wie er.
    if not dialog.advanced.isChecked():
        dialog.advanced.click()
        run.settle(40)
    dialog._editors["x"].set_value(float(chosen["x"]) + 15.0)
    run.settle(40)
    run.capture(8)
    dialog.reject()
    run.settle(20)


def story_print_a_model(run: GuideRun) -> None:
    """Vom Startbildschirm über den Prüfbericht in den Druckdialog."""
    from app.ui import guide_targets
    from app.ui.print_settings_dialog import PrintSettingsDialog

    _fresh(run)
    run.capture(1)

    _import(run, BROKEN_MODEL)
    report = run.window.report
    run.window.right.setCurrentWidget(report)
    run.settle(10)
    run.capture(2)

    if report.list.count() == 0:
        raise SystemExit(f"{BROKEN_MODEL.name}: der Prüfbericht meldet nichts")
    _choose_finding(report, 0)
    run.settle(10)
    run.capture(3)

    guide_targets.widget_for(run.window, "report.action").click()
    web.until_quiet(run.app, run.session, "Reparatur")
    run.window.right.setCurrentWidget(report)
    run.settle(10)
    run.capture(4)

    def in_dialog(dialog: Any) -> None:
        # Erst wenn Slicer und Profile gefunden sind, steht der Dialog so da,
        # wie der Kunde ihn sieht (Muster ``make_web_images``, Motiv
        # „schritt-druck"); vorher stünde „Die Slicer werden gesucht …".
        if not dialog.wait_for_slicers():
            raise SystemExit("Die Slicersuche des Druckdialogs kam nicht zurück")
        for _ in range(200):
            if not dialog._profiles_pending:
                break
            run.settle(2)
        run.settle(20)
        run.capture(5)
        run.capture(6)

    button = guide_targets.widget_for(run.window, "report.slicer")
    web.while_open(PrintSettingsDialog, button.click, in_dialog)
    run.settle(20)


def story_first_part(run: GuideRun) -> None:
    """Vom leeren Projekt zur Platte mit gesenktem Schraubenloch, jeder Schritt am Knopf."""
    from app.core.knowledge import standards
    from app.core.knowledge.parts import PARTS
    from app.ui import guide_targets
    from app.ui.catalog import PartCatalog

    _fresh(run)
    run.capture(1)
    guide_targets.widget_for(run.window, "start.new").click()
    run.settle(30)

    box = guide_targets.action_for(run.window, "operation:create_brep_box")
    _open_menu(run, box)
    run.capture(2)
    _close_menus(run)
    box.trigger()
    run.settle(40)
    dialog = run.window._op_dialog
    if dialog is None or not dialog.isVisible():
        raise SystemExit("Der Dialog „Quader anlegen“ ging nicht auf")
    for name, value in (("width", 60.0), ("depth", 30.0), ("height", 5.0)):
        dialog._editors[name].set_value(value)
    run.settle(40)
    run.capture(3)
    run.capture(4)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Quader")
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(20)

    body = web.select_body(run.window, 0)
    result = run.session.last_result
    if result is None:
        raise SystemExit("Der Quader wurde nicht gerechnet")
    face_id, face = _top_face(result.scene.objects[body])
    run.window.object_tree.select_feature(body, face_id)
    run.settle(30)
    centre = tuple(float(value) for value in face.params["centre"])
    # Neben die Mitte: Dort sitzt das Werkzeugkreuz der gewählten Fläche, und
    # ein Klickpunkt darauf sah im Probelauf aus wie ein Griff am Kreuz.
    spot = (centre[0] + 18.0, centre[1], centre[2])
    run.capture(5, points={"viewport": _visible(run, spot)})

    run.capture(6)

    def in_catalog(opened: Any) -> None:
        # Die Vorschaubilder füllen sich nacheinander, in rund zwei Sekunden;
        # vorher trug die Kachel im Probelauf einen leeren Platzhalter.
        for _round in range(200):
            if all(spec.name in opened._previews for spec in PARTS.all()):
                break
            run.settle(2)
        else:
            raise SystemExit("Die Vorschaubilder des Katalogs wurden nicht fertig")
        tile = next(
            (
                item
                for row in range(opened.list.count())
                if (item := opened.list.item(row)) is not None
                and item.data(Qt.ItemDataRole.UserRole) == "screw_hole"
            ),
            None,
        )
        if tile is None:
            raise SystemExit("Der Katalog zeigt kein „Schraubenloch mit Senkung“")
        # Gewählt wie mit einem Klick: Die Detailspalte sagt dann, was er tut.
        opened.list.setCurrentItem(tile)
        run.settle(10)
        run.capture(7)
        # Der Doppelklick über das Signal der Liste, denselben Weg, den ein
        # echter nimmt. Ein nachgestellter Mausdoppelklick (``QTest``) wählte
        # die Kachel nur und löste nichts aus; der Katalog schloss dann mit
        # „Abbrechen", und der Dialog des Bausteins kam nie.
        opened.list.itemDoubleClicked.emit(tile)

    parts = guide_targets.widget_for(run.window, "selection.parts")
    web.while_open(PartCatalog, parts.click, in_catalog)
    run.settle(40)
    dialog = run.window._op_dialog
    if dialog is None or not dialog.isVisible():
        raise SystemExit("Der Dialog „Schraubenloch mit Senkung“ ging nicht auf")
    size = dialog._editors["size"]
    index = size.findData("M4")
    if index < 0:
        raise SystemExit("Die Schraubengröße M4 steht nicht zur Wahl")
    size.setCurrentIndex(index)
    run.settle(40)
    run.capture(8)
    chosen = dialog.values()
    mouth = (float(chosen["x"]), float(chosen["y"]), float(chosen["z"]))
    radius = standards.screw(str(chosen["size"])).countersink / 2.0
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Schraubenloch")

    # Ohne Auswahl, damit kein Werkzeugkreuz über der Senkung liegt, und mit
    # dem Prüfbericht rechts, in dem der Knopf zum Drucken steht.
    run.window.object_tree.select_object(None)
    run.window.right.setCurrentWidget(run.window.report)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    rim = [
        _visible(run, (mouth[0] + dx, mouth[1] + dy, mouth[2]))
        for dx, dy in ((radius, 0.0), (-radius, 0.0), (0.0, radius), (0.0, -radius))
    ]
    xs, ys = [point.x() for point in rim], [point.y() for point in rim]
    sink = QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys)))
    run.capture(9, rings={"viewport": sink})


def story_housing_with_lid(run: GuideRun) -> None:
    """Quader, aushöhlen mit offener Oberseite, Deckel dazu, beide druckfertig hinlegen."""
    from app.ui import guide_targets

    def open_dialog(what: str) -> Any:
        dialog = run.window._op_dialog
        if dialog is None or not dialog.isVisible():
            raise SystemExit(f"Der Dialog „{what}“ ging nicht auf")
        return dialog

    # Der Quader entsteht wie in „Das erste eigene Teil"; dort hat der Weg
    # seine Bilder, hier zählt das Ergebnis.
    _fresh(run)
    guide_targets.widget_for(run.window, "start.new").click()
    run.settle(30)
    guide_targets.action_for(run.window, "operation:create_brep_box").trigger()
    run.settle(40)
    dialog = open_dialog("Quader anlegen")
    for name, value in (("width", 80.0), ("depth", 60.0), ("height", 40.0)):
        dialog._editors[name].set_value(value)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Quader")
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(20)

    body = web.select_body(run.window, 0)
    result = run.session.last_result
    if result is None:
        raise SystemExit("Der Quader wurde nicht gerechnet")
    _face_id, face = _top_face(result.scene.objects[body])
    centre = tuple(float(value) for value in face.params["centre"])
    run.capture(1, points={"viewport": _visible(run, (centre[0], centre[1], centre[2]))})
    run.capture(2)

    guide_targets.widget_for(run.window, "operation:hollow_object").click()
    run.settle(40)
    dialog = open_dialog("Aushöhlen")
    dialog._editors["wall"].set_value(2.0)
    dialog._editors["open_top"].setChecked(True)
    run.settle(40)
    run.capture(3)
    run.capture(4)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Aushöhlen")

    lid = guide_targets.action_for(run.window, "operation:create_lid")
    _open_menu(run, lid)
    run.capture(5)
    _close_menus(run)
    lid.trigger()
    run.settle(40)
    open_dialog("Deckel erzeugen")
    run.capture(6)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Deckel")

    # Der Klick ins Leere hebt die Auswahl auf (``Viewport``: ohne Taste der
    # Weg, sie ohne den Baum loszuwerden); die Stelle liegt vor der Dose auf
    # dem Bett, wo kein Körper steht.
    run.window.object_tree.select_object(None)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    bounds = run.session.last_result.scene.objects[body].mesh.bounds
    free = (0.0, float(bounds.minimum[1]) - 15.0, 0.0)
    run.capture(7, points={"viewport": _visible(run, free)})
    run.capture(8)
    guide_targets.widget_for(run.window, "operation:orient_for_print").click()
    run.settle(40)
    open_dialog("Druckoptimal ausrichten")
    # Die Vorschau rechnet die Lage im Hintergrund; aufgenommen wird, wenn sie steht.
    run.session.wait_for_idle(120_000)
    run.settle(30)
    run.capture(9)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Druckoptimal ausrichten")

    # Mit dem Prüfbericht rechts, in dem der Knopf zum Drucken steht.
    run.window.object_tree.select_object(None)
    run.window.right.setCurrentWidget(run.window.report)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    run.capture(10)


def _open_dialog(run: GuideRun, what: str) -> Any:
    """Der Operationsdialog, den der letzte Klick geöffnet haben muss."""
    dialog = run.window._op_dialog
    if dialog is None or not dialog.isVisible():
        raise SystemExit(f"Der Dialog „{what}“ ging nicht auf")
    return dialog


def _choose_finding(report: Any, row: int) -> None:
    """Einen Befund wählen, wie der Kunde es tut: Hinweise allein stehen
    zugeklappt (RM-508), ihre Zahl im Kopf des Berichts öffnet sie."""
    if not report.list_toggle.isChecked():
        report.list_toggle.click()
    report.list.setCurrentRow(row)


def _finding_row(report: Any, code: str) -> int:
    """Die Zeile des Prüfberichts mit diesem Befund — über den Code, nicht über den Satz."""
    for row in range(report.list.count()):
        finding = report.list.item(row).data(Qt.ItemDataRole.UserRole)
        if getattr(finding, "code", None) == code:
            return row
    raise SystemExit(f"Der Prüfbericht meldet keinen Befund {code}")


def _new_box(run: GuideRun, sizes: tuple[float, float, float], *, named: bool = False) -> Any:
    """Ein neues Projekt mit einem Quader, ohne Bilder — den Weg zeigt „Das erste eigene Teil".

    ``named`` hält den Dialog mit dem Haken *Maße als Parameter anlegen* offen
    und gibt ihn zurück; sonst wird angelegt und der Körper gewählt.
    """
    from app.ui import guide_targets

    _fresh(run)
    guide_targets.widget_for(run.window, "start.new").click()
    run.settle(30)
    guide_targets.action_for(run.window, "operation:create_brep_box").trigger()
    run.settle(40)
    dialog = _open_dialog(run, "Quader anlegen")
    for name, value in zip(("width", "depth", "height"), sizes, strict=True):
        dialog._editors[name].set_value(value)
    if named:
        return dialog
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Quader")
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(20)
    return web.select_body(run.window, 0)


def _click_spot(run: GuideRun, body: str) -> QPoint:
    """Wo der Klick auf ein Teil hinzeigt: neben die Mitte seiner Oberseite.

    Neben die Mitte, weil dort nach dem Klick das Werkzeugkreuz steht; ein
    Klickpunkt darauf sähe aus wie ein Griff am Kreuz.
    """
    result = run.session.last_result
    if result is None:
        raise SystemExit("nichts gerechnet — kein Teil zum Anklicken")
    _face_id, face = _top_face(result.scene.objects[body])
    centre = tuple(float(value) for value in face.params["centre"])
    return _visible(run, (centre[0] + 12.0, centre[1] + 6.0, centre[2]))


def _face_spot(run: GuideRun, body: str) -> QPoint:
    """Die Oberseite wählen, wie mit dem zweiten Klick, und sagen, wo er hinzeigt."""
    result = run.session.last_result
    if result is None:
        raise SystemExit("nichts gerechnet — keine Fläche zum Anklicken")
    face_id, face = _top_face(result.scene.objects[body])
    run.window.object_tree.select_feature(body, face_id)
    run.settle(30)
    centre = tuple(float(value) for value in face.params["centre"])
    return _visible(run, (centre[0] + 18.0, centre[1] + 8.0, centre[2]))


def story_split_a_large_part(run: GuideRun) -> None:
    """Ein zu langer Balken: Befund, *Modell teilen*, Stücke anordnen."""
    from app.ui import guide_targets

    _import(run, OVERSIZED_MODEL)
    report = run.window.report
    run.window.right.setCurrentWidget(report)
    _choose_finding(report, _finding_row(report, "arrange.out_of_build_volume"))
    run.settle(10)
    run.capture(1)
    run.capture(2)
    guide_targets.widget_for(run.window, "report.action").click()
    # Die Teilung sucht im Hintergrund; das Bild entsteht, wenn sie steht.
    for _round in range(1200):
        run.settle(2)
        if not run.session.split_running:
            break
    web.until_quiet(run.app, run.session, "Teilen")
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    run.capture(3)
    run.window.right.setCurrentWidget(report)
    _choose_finding(report, _finding_row(report, "prepare.halves_in_place"))
    run.settle(10)
    run.capture(4)
    guide_targets.widget_for(run.window, "report.action").click()
    web.until_quiet(run.app, run.session, "Anordnen")
    # Die Explosionsansicht, die das Teilen geöffnet hat, zöge die Stücke im
    # Bild auseinander; gezeigt wird die Lage, die gedruckt wird.
    run.window.tools.close_tool()
    run.window.object_tree.select_object(None)
    run.window.right.setCurrentWidget(report)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    run.capture(5)


def story_move_and_turn(run: GuideRun) -> None:
    """Teil wählen, *Bewegen*, am Griff oder mit Zahlen verschieben, dann drehen."""
    from app.ui import guide_targets

    _import(run, PLATE_MODEL)
    body = web.select_body(run.window, 0)
    run.capture(1, points={"viewport": _click_spot(run, body)})
    run.capture(2)
    guide_targets.widget_for(run.window, "tool:transform").click()
    run.settle(30)
    run.capture(3)
    bar = run.window.transform_bar
    bar.dx.set_value_mm(20.0)
    run.settle(20)
    run.capture(4)
    bar._apply()
    web.until_quiet(run.app, run.session, "Verschieben")
    guide_targets.widget_for(run.window, "transform:rotate").click()
    run.settle(20)
    run.capture(5)
    bar._apply()
    web.until_quiet(run.app, run.session, "Drehen")
    run.settle(20)
    run.capture(6)


def story_change_a_dimension(run: GuideRun) -> None:
    """Quader mit benannten Maßen, dann die Breite unter *Parameter* ändern."""
    from app.ui import guide_targets

    _new_box(run, (60.0, 40.0, 10.0), named=True)
    naming = guide_targets.widget_for(run.window, "dialog.naming")
    naming.setChecked(True)  # type: ignore[attr-defined]
    run.settle(30)
    run.capture(1)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Quader")
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(20)
    run.capture(2)
    width = guide_targets.widget_for(run.window, "parameters.first")
    width.setValue(80.0)  # type: ignore[attr-defined]
    web.until_quiet(run.app, run.session, "Parameter")
    run.settle(20)
    run.capture(3)
    run.window.object_tree.select_object(None)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    run.capture(4)


def story_undo_a_step(run: GuideRun) -> None:
    """*Rückgängig* im Menü, das Kontextmenü eines Schritts, die Nachfrage beim Löschen."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    from app.ui import guide_targets

    # Zwei Schritte, der zweite hängt am ersten: Beim Löschen des Quaders
    # nennt die Nachfrage die Bohrung, die mit ihm verschwände.
    body = _new_box(run, (60.0, 40.0, 10.0))
    _face_spot(run, body)
    guide_targets.widget_for(run.window, "operation:drill_hole").click()
    run.settle(40)
    _open_dialog(run, "Bohrung setzen")
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Bohrung")
    run.window.object_tree.select_object(None)
    run.settle(20)
    undo = guide_targets.action_for(run.window, "command:edit.undo")
    _open_menu(run, undo)
    run.capture(1)
    _close_menus(run)

    history = run.window.history_panel
    item = history.list.item(0)
    if item is None:
        raise SystemExit("Der Verlauf ist leer — es gibt keinen Schritt für das Kontextmenü")
    history.list.setCurrentItem(item)
    run.settle(10)
    state: dict[str, Any] = {"error": None}

    def with_menu(rounds: int = 0) -> None:
        # Das Kontextmenü läuft über ``exec``; aufgenommen wird aus seiner
        # Schleife heraus, sobald es steht.
        popup = QApplication.activePopupWidget()
        if not isinstance(popup, QMenu) or not popup.isVisible():
            if rounds < 200:
                QTimer.singleShot(20, lambda: with_menu(rounds + 1))
            else:
                state["error"] = "Das Kontextmenü des Verlaufs ging nicht auf"
            return
        try:
            run.capture(2)
        except BaseException as error:  # nach dem Schließen weiterreichen
            state["error"] = error
        popup.close()

    QTimer.singleShot(0, with_menu)
    history.list.customContextMenuRequested.emit(history.list.visualItemRect(item).center())
    run.settle(20)
    if state["error"] is not None:
        error = state["error"]
        raise error if isinstance(error, BaseException) else SystemExit(str(error))

    step = item.data(Qt.ItemDataRole.UserRole)
    web.while_open(
        QMessageBox,
        lambda: history.removalRequested.emit((int(step),)),
        lambda _box: run.capture(3),
    )
    run.settle(20)


def story_thread_a_hole(run: GuideRun) -> None:
    """Bohrung wählen, Katalog über das Menü, *Druckbares Gewinde* einsetzen."""
    from app.core.knowledge.parts import PARTS
    from app.ui import guide_targets
    from app.ui.catalog import PartCatalog

    _import(run, PLATE_MODEL)
    body = web.select_body(run.window, 0)
    result = run.session.last_result
    if result is None:
        raise SystemExit(f"{PLATE_MODEL.name}: keine Auswertung")
    entry = result.scene.objects[body]
    hole_id, hole = next(
        (found, feature) for found, feature in entry.features.items() if feature.kind == "hole"
    )
    run.window.object_tree.select_feature(body, hole_id)
    run.settle(30)
    # Der Klick trifft die Öffnung oben, nicht die Mitte der Bohrung im Material.
    centre = tuple(float(value) for value in hole.params["centre"])
    top = float(entry.mesh.bounds.maximum[2])
    run.capture(1, points={"viewport": _visible(run, (centre[0], centre[1], top))})
    catalog = guide_targets.action_for(run.window, "command:file.catalog")
    _open_menu(run, catalog)
    run.capture(2)
    _close_menus(run)

    def in_catalog(opened: Any) -> None:
        for _round in range(300):
            if all(spec.name in opened._previews for spec in PARTS.all()):
                break
            run.settle(2)
        else:
            raise SystemExit("Die Vorschaubilder des Katalogs wurden nicht fertig")
        tile = next(
            (
                item
                for row in range(opened.list.count())
                if (item := opened.list.item(row)) is not None
                and item.data(Qt.ItemDataRole.UserRole) == "printed_thread"
            ),
            None,
        )
        if tile is None:
            raise SystemExit("Der Katalog zeigt kein „Druckbares Gewinde“")
        opened.list.setCurrentItem(tile)
        run.settle(10)
        run.capture(3)
        opened.list.itemDoubleClicked.emit(tile)

    web.while_open(PartCatalog, catalog.trigger, in_catalog)
    run.settle(40)
    _open_dialog(run, "Druckbares Gewinde")
    run.settle(40)
    run.capture(4)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Gewinde")
    # Die Bohrung liegt in einer Ecke der Platte; die Kamera geht zu ihr, statt
    # auf die Mitte zu zoomen, und ein Ring umschließt die Öffnung.
    run.window.object_tree.select_object(None)
    run.window.viewport.reset_camera(follow_selection=False)
    run.window.viewport.fly_to((centre[0], centre[1], top), reach=45.0)
    run.settle(30)
    radius = float(hole.params["diameter"]) / 2.0 + 1.5
    rim = [
        _visible(run, (centre[0] + dx, centre[1] + dy, top))
        for dx, dy in ((radius, 0.0), (-radius, 0.0), (0.0, radius), (0.0, -radius))
    ]
    xs, ys = [point.x() for point in rim], [point.y() for point in rim]
    run.capture(5, rings={"viewport": QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys)))})


def story_round_edges(run: GuideRun) -> None:
    """Quader wählen, *Ändern* aufklappen, *Verrunden*, Ergebnis mit *Fase anbringen*."""
    from app.ui import guide_targets

    body = _new_box(run, (60.0, 40.0, 20.0))
    run.capture(1, points={"viewport": _click_spot(run, body)})
    heading = guide_targets.widget_for(run.window, "section:shaping")
    # Wie beim Kunden, der den Abschnitt noch nie geöffnet hat: zu.
    if heading.isChecked():  # type: ignore[attr-defined]
        heading.click()  # type: ignore[attr-defined]
        run.settle(10)
    run.capture(2)
    heading.click()  # type: ignore[attr-defined]
    run.settle(20)
    run.capture(3)
    guide_targets.widget_for(run.window, "operation:fillet_edges").click()
    run.settle(40)
    dialog = _open_dialog(run, "Verrunden")
    dialog._editors["radius"].set_value(5.0)
    run.settle(60)
    run.capture(4)
    run.capture(5)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Verrunden")
    web.select_body(run.window, 0)
    run.settle(20)
    heading = guide_targets.widget_for(run.window, "section:shaping")
    if not heading.isChecked():  # type: ignore[attr-defined]
        heading.click()  # type: ignore[attr-defined]
        run.settle(20)
    run.capture(6)


def story_label_a_part(run: GuideRun) -> None:
    """Oberseite wählen, *Text aufbringen*, Text und Größe, erhaben aufbringen."""
    from app.ui import guide_targets

    _import(run, PLATE_MODEL)
    body = web.select_body(run.window, 0)
    run.capture(1, points={"viewport": _face_spot(run, body)})
    run.capture(2)
    guide_targets.widget_for(run.window, "operation:label_text").click()
    run.settle(40)
    dialog = _open_dialog(run, "Text aufbringen")
    dialog._editors["text"].setText(APP_NAME)
    dialog._editors["size"].set_value(10.0)
    run.settle(60)
    run.capture(3)
    run.capture(4)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Text")
    run.window.object_tree.select_object(None)
    run.window.viewport.reset_camera(follow_selection=False)
    run.window.viewport.zoom(1.6)
    run.settle(30)
    run.capture(5)


def story_draw_and_pull(run: GuideRun) -> None:
    """*Zeichnen*, Ebene, Rechteck, *Hochziehen*, Höhe, fertiges Teil."""
    from app.core.sketch import shapes
    from app.ui import guide_targets

    _fresh(run)
    guide_targets.widget_for(run.window, "start.new").click()
    run.settle(30)
    run.capture(1)
    guide_targets.widget_for(run.window, "toolbar.draw").click()
    run.settle(60)
    panel = run.window._sketch_panel
    if panel is None:
        raise SystemExit("Der Zeichenmodus ging nicht auf")
    run.capture(2)
    guide_targets.widget_for(run.window, "sketch:rectangle").click()
    run.settle(20)
    run.capture(3)
    # Gezeichnet wird wie in ``make_figures.frame_sketch``: Das Rechteck mit
    # seinen Maßen ist dasselbe, das der Kunde mit zwei Zahlen aufzieht.
    panel.canvas.insert_shape(shapes.rectangle(50.0, 30.0))
    # Näher heran wie mit dem Mausrad: Auf der ganzen Platte stünde das
    # Rechteck briefmarkengroß im Bild, und seine Maße wären nicht zu lesen.
    # Nicht ``fit_view``: Die Ansicht reicht unter den Seitenkarten durch, und
    # auf das Rechteck selbst eingepasst lief es hinter ihnen aus dem Bild.
    # Die Kamera hört auf dasselbe Signal wie beim Einpassen.
    panel.canvas.viewFitted.emit(0.0, 0.0, 175.0, 105.0)
    run.settle(40)
    run.capture(4)
    run.capture(5)
    guide_targets.widget_for(run.window, "sketch.pull").click()
    run.settle(60)
    dialog = _open_dialog(run, "Grundform hochziehen")
    dialog._editors["height"].set_value(10.0)
    run.settle(60)
    run.capture(6)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Hochziehen")
    run.window.object_tree.select_object(None)
    run.window.right.setCurrentWidget(run.window.report)
    run.window.viewport.view_from("iso")
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(40)
    run.capture(7)


def story_two_colours(run: GuideRun) -> None:
    """Körper weiß, Oberseite rot: *Filament auf eine Fläche* mit einer zweiten Spule."""
    from app.core.knowledge import filaments
    from app.core.scene import OperationDraft
    from app.ui import guide_targets

    names = _spool_names()
    for name, colour in zip(names, SPOOL_COLOURS, strict=True):
        filaments.save(filaments.CatalogueFilament(name=name, colour=colour, material_type="PLA"))
    _import(run, PLATE_MODEL)
    body = web.select_body(run.window, 0)
    # Der Körper hat schon sein Filament, wie beim Kunden, der gedruckt hat;
    # die Fläche bekommt das zweite.
    run.session.apply(
        names[0],
        [
            OperationDraft(
                op="assign_slot",
                inputs=(body,),
                params={
                    "slot": 1,
                    "name": names[0],
                    "colour": SPOOL_COLOURS[0],
                    "material_type": "PLA",
                },
            )
        ],
        raise_on_error=True,
    )
    web.until_quiet(run.app, run.session, "Filament")
    body = web.select_body(run.window, 0)
    run.capture(1, points={"viewport": _face_spot(run, body)})
    run.capture(2)
    guide_targets.widget_for(run.window, "operation:paint_slot").click()
    run.settle(40)
    dialog = _open_dialog(run, "Filament auf eine Fläche")
    slot = dialog._editors["slot"]
    index = next((row for row in range(slot.count()) if names[1] in str(slot.itemText(row))), -1)
    if index < 0:
        raise SystemExit(f"Das Filamentfeld bietet „{names[1]}“ nicht an")
    slot.setCurrentIndex(index)
    # Wie der Klick in die Liste: Erst ``activated`` übernimmt Name und Farbe
    # der Spule (``FilamentField._chosen``). Ohne das Signal bekam die Fläche
    # einen Slot ohne Farbe, und das Ergebnisbild zeigte eine graue Platte.
    slot.activated.emit(index)
    run.settle(60)
    run.capture(3)
    run.capture(4)
    guide_targets.widget_for(run.window, "dialog.accept").click()
    web.until_quiet(run.app, run.session, "Filament")
    run.window.object_tree.select_object(None)
    run.window.right.setCurrentWidget(run.window.report)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    run.capture(5)


def story_repair_a_model(run: GuideRun) -> None:
    """Was beim Einlesen repariert wurde, *Stelle zeigen*, dann *Überschneidungen auflösen*."""
    from app.ui import guide_targets

    _import(run, OPEN_MODEL)
    report = run.window.report
    run.window.right.setCurrentWidget(report)
    run.settle(10)
    run.capture(1)
    _choose_finding(report, 0)
    run.settle(10)
    run.capture(2)
    guide_targets.widget_for(run.window, "report.action").click()
    run.settle(60)
    run.capture(3)
    _import(run, CROSSING_MODEL)
    run.window.right.setCurrentWidget(report)
    _choose_finding(report, _finding_row(report, "ingest.multiple_components"))
    run.settle(10)
    run.capture(4)
    guide_targets.widget_for(run.window, "report.action").click()
    web.until_quiet(run.app, run.session, "Reparieren")
    run.window.right.setCurrentWidget(report)
    run.window.viewport.reset_camera(follow_selection=False)
    run.settle(30)
    run.capture(5)


#: Je Anleitung ihre Geschichte. ``tests/test_guides.py`` verlangt für jede
#: Anleitung im Kern genau eine.
STORIES: Final[dict[str, Callable[[GuideRun], None]]] = {
    "window-overview": story_window_overview,
    "print-a-model": story_print_a_model,
    "drill-a-hole": story_drill_a_hole,
    "first-part": story_first_part,
    "housing-with-lid": story_housing_with_lid,
    "split-a-large-part": story_split_a_large_part,
    "move-and-turn": story_move_and_turn,
    "change-a-dimension": story_change_a_dimension,
    "undo-a-step": story_undo_a_step,
    "thread-a-hole": story_thread_a_hole,
    "round-edges": story_round_edges,
    "label-a-part": story_label_a_part,
    "draw-and-pull": story_draw_and_pull,
    "two-colours": story_two_colours,
    "repair-a-model": story_repair_a_model,
}


# --- Prozesse -------------------------------------------------------------------------


def _write_stamp(folder: Path, taken: list[guides.Guide]) -> None:
    """Je Anleitung Version und Abdruck neben die Bilder schreiben."""
    path = folder / "guides.json"
    stamp: dict[str, Any] = {"guides": {}}
    if path.is_file():
        stamp = json.loads(path.read_text(encoding="utf-8"))
    for guide in taken:
        stamp["guides"][guide.key] = {
            "version": APP_VERSION,
            "fingerprint": guides.fingerprint(guide),
        }
    path.write_text(
        json.dumps(stamp, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _stay_on_top(window: Any) -> None:
    """Das Aufnahmefenster für die Dauer des Laufs über jedes fremde Fenster legen.

    Auf dem Aufnahmeschirm liegt oft ein Fenster des Nutzers, am 27.09.2026 das
    maximierte Claude-Fenster. Windows holt ein Programm aus dem Hintergrund
    nicht nach vorn: ``raise_`` und ``activateWindow`` blieben wirkungslos, und
    ``wait_until_uncovered`` brach nach 300 s ab. Die oberste Ebene
    (``HWND_TOPMOST``) gilt ohne Fokuswechsel. Über Win32 und nicht über
    ``WindowStaysOnTopHint``: Der Schalter baut das native Fenster neu und mit
    ihm die Fläche, in die der Renderer zeichnet. Ein fremdes Fenster, das
    selbst oben liegt, meldet ``foreign_window_over`` weiterhin.

    **Die eigenen Menüs kommen danach wieder darüber.** Ein Dialog gehört dem
    Fenster und bleibt über ihm; ein aufgeklapptes Menü oder eine Liste ist
    ein eigenes Fenster ohne Besitzer. Seit das Fenster vor jedem Bild neu
    angehoben wird, lag jedes offene Menü darunter, und die Bilder zeigten den
    Rahmen um einen Eintrag, den man nicht sah (27.09.2026, *Erzeugen →
    Grundformen*, *Datei → Bausteinkatalog …*, das Kontextmenü im Verlauf).
    Untermenüs kommen nach ihrem Menü, damit sie oben liegen.
    """
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    topmost = wintypes.HWND(-1)
    keep = 0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
    if not user32.SetWindowPos(int(window.winId()), topmost, 0, 0, 0, 0, keep):
        print("  … das Aufnahmefenster ließ sich nicht nach oben legen", flush=True)
    popups = [
        widget
        for widget in QApplication.topLevelWidgets()
        if widget is not window
        and widget.isVisible()
        and widget.windowType() == Qt.WindowType.Popup
    ]
    for popup in sorted(popups, key=_depth):
        user32.SetWindowPos(int(popup.winId()), topmost, 0, 0, 0, 0, keep)


def _depth(widget: Any) -> int:
    """Wie tief ein Fenster unter anderen hängt — ein Untermenü tiefer als sein Menü."""
    depth = 0
    parent = widget.parentWidget()
    while parent is not None:
        depth += 1
        parent = parent.parentWidget()
    return depth


def _child(language: str, keys: list[str], target: Path, film_target: Path) -> int:
    """Die Kindseite: ein Fenster, alle gewählten Anleitungen einer Sprache."""
    from app.core.paths import user_config_dir

    room = os.environ.get(ROOM_VARIABLE)
    if not room or not str(user_config_dir()).startswith(room):
        raise SystemExit(
            "Die Anleitungen entstehen nur isoliert, über den Elternprozess: "
            f"{user_config_dir()} ist ein echtes Profil."
        )
    from app.ui.app import install_qt_translations
    from app.ui.main_window import MainWindow
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

    folder = target / language
    folder.mkdir(parents=True, exist_ok=True)
    frames = film.frames_folder(film_target, language)
    frames.mkdir(parents=True, exist_ok=True)
    chosen = [guide for guide in guides.GUIDES if guide.key in keys]
    # Der Stand eines Kunden, der den Druckdialog schon einmal geöffnet hat:
    # ein gewählter Slicer und der gelesene Hinweis zu den Druckeinstellungen,
    # sonst stünde vor dem Dialog der Hinweis und im Dialog die Slicersuche.
    # Dieselben Aufrufe wie der Dialog selbst, im isolierten Profil
    # (Muster ``make_web_images._screens_child``).
    from app.core import discover
    from app.core import tools as external_tools
    from app.ui.print_disclosure import remember_disclosure

    found = discover.find_programs("slicer", external_tools.SLICERS)
    prusa = next((one for one in found if "prusa" in one.name.lower()), None)
    if prusa is not None:
        discover.remember_path("slicer", str(prusa))
    settings = UiSettings()
    remember_disclosure(settings)
    session = Session()
    window = shots.prepared(MainWindow(session, settings), None, hidden=False)
    # Die Restlaufzeit der Demo steht in der Statuszeile und wäre im Handbuch
    # eine Zahl, die nach einer Woche nicht mehr stimmt.
    window.trial_line.hide()
    window.raise_()
    window.activateWindow()
    _stay_on_top(window)
    shots.settle(app, 40)
    print(f"{language}:")
    try:
        for guide in chosen:
            run = GuideRun(app, window, guide, folder, frames)
            STORIES[guide.key](run)
            run.finish()
    finally:
        session.forget_changes()
        window.close()
        shots.release_viewport(window)
    _write_stamp(folder, chosen)
    _write_stamp(frames, chosen)
    return 0


def _take(language: str, keys: list[str], target: Path, film_target: Path) -> None:
    """Eine Sprache in einem eigenen Prozess mit eigenen Nutzerverzeichnissen."""
    with tempfile.TemporaryDirectory(prefix="solidon-anleitungen-") as room:
        environment = dict(os.environ)
        for name in ISOLATED_VARIABLES:
            environment[name] = room
        environment[ROOM_VARIABLE] = room
        environment.pop("QT_QPA_PLATFORM", None)
        environment.pop("QT_SCALE_FACTOR", None)
        arguments = [sys.executable, str(Path(__file__).resolve()), "--kind", language]
        arguments += ["--ziel", str(target), "--film-ziel", str(film_target)]
        arguments += ["--schirm", str(shots.SCREEN_INDEX)]
        for key in keys:
            arguments += ["--nur", key]
        run = subprocess.run(arguments, env=environment, check=False)
    expected = [
        _picture_path(folder, key)
        for folder in (target / language, film.frames_folder(film_target, language))
        for guide in guides.GUIDES
        if guide.key in keys
        for key in guide.figure_keys()
    ]
    missing = [path.name for path in expected if not path.is_file()]
    if run.returncode != 0 or missing:
        raise SystemExit(
            f"Die Anleitungen für {language!r} sind nicht vollständig entstanden "
            f"(Kindprozess endete mit {run.returncode}; es fehlen: {', '.join(missing) or '—'})"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bildanleitungen des Handbuchs aus der echten Oberfläche aufnehmen."
    )
    # Die Schalter sind deutsch wie bei den übrigen Erzeugern, ihre Ziele
    # englisch wie jeder Bezeichner in ``tools/`` (test_language_rules).
    parser.add_argument(
        "languages", nargs="*", metavar="SPRACHE", help="Sprachen, ohne Angabe alle"
    )
    parser.add_argument(
        "--nur",
        dest="only",
        action="append",
        default=[],
        metavar="ANLEITUNG",
        help="nur diese Anleitung (mehrfach möglich)",
    )
    parser.add_argument(
        "--ziel",
        dest="target",
        type=Path,
        default=figures.IMAGE_ROOT,
        metavar="ORDNER",
        help="Ordner für die Bilder, je Sprache ein Unterordner (Vorgabe: app/images/manual)",
    )
    parser.add_argument(
        "--film-ziel",
        dest="film_target",
        type=Path,
        default=film.OUTPUT,
        metavar="ORDNER",
        help=(
            "Ordner für die 2K-Filmbilder, je Sprache unter <sprache>/frames "
            "(Vorgabe: marketing/video/guides)"
        ),
    )
    parser.add_argument(
        "--schirm",
        dest="screen",
        type=int,
        default=None,
        metavar="N",
        help="Bildschirm für die Aufnahme",
    )
    parser.add_argument("--kind", dest="child", default=None, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)

    if arguments.screen is not None:
        shots.SCREEN_INDEX = arguments.screen
    known = {guide.key for guide in guides.GUIDES}
    unknown = sorted(set(arguments.only) - known)
    if unknown:
        raise SystemExit(
            f"Unbekannte Anleitung: {', '.join(unknown)}. Bekannt: {', '.join(sorted(known))}"
        )
    keys = arguments.only or sorted(known)
    missing = sorted(set(keys) - set(STORIES))
    if missing:
        raise SystemExit(f"Ohne Geschichte: {', '.join(missing)}")

    if arguments.child is not None:
        return _child(arguments.child, keys, arguments.target, arguments.film_target)
    for language in shots.chosen_languages(tuple(arguments.languages)):
        _take(language, keys, arguments.target, arguments.film_target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
