"""Die ersten fünf Minuten (Bauplan §2.3).

Kein leerer Startbildschirm: zuletzt geöffnete Projekte, die Beispielprojekte,
sobald es sie gibt, und eine große Ablagefläche. Ziehen und Fallenlassen
funktioniert hier wie am Fenster, am Viewport und am Objektbaum.

**Der leere Zustand ist der erste Eindruck**, und er war einer von einem
Formular, dem die Felder fehlen: der Inhalt über 1900 Pixel verteilt, das
Ablagefeld ein Satz ohne Rahmen, die Beispiele eine Textliste ohne
erkennbare Anklickbarkeit, und der Verweis aufs Handbuch 1700 Pixel weiter
rechts als die Knöpfe, zu denen er gehört.

Jetzt eine Spalte begrenzter Breite in der Mitte, ein Ablagefeld, das eines
ist, und die Beispiele als Kacheln — Titel und ein Satz, so groß, dass man
sieht, dass man sie anklicken kann.
"""

from __future__ import annotations

import time
from itertools import pairwise
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QEvent, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QImage,
    QPainter,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, PART_FILE_SUFFIX, PROJECT_SUFFIX
from app.core import examples
from app.core.errors import AppError
from app.core.examples import Example
from app.core.ingest.archive import IMPORT_SUFFIXES
from app.core.knowledge import filaments
from app.i18n import tr
from app.ui.filament_inventory import paint_spool
from app.ui.icons import icon
from app.ui.leash import stop_watching_the_dying
from app.ui.panels import collapsible
from app.ui.style import NORMAL, TIGHT, WIDE, make_large_target, make_primary, set_level
from app.ui.theme import THEMES

#: Wie breit die Spalte höchstens wird. Darüber hinaus wächst nur der Rand:
#: eine Zeile über 1900 Pixel liest niemand, und ein Knopf, der am linken Rand
#: klebt, während sein Verweis am rechten steht, gehört sichtbar nicht mehr
#: zusammen.
COLUMN_WIDTH = 900

#: Wie viele Zeilen von „Zuletzt geöffnet" ohne Rollen sichtbar sind.
#:
#: Vier, und die Zahl kommt aus einer Messung: Der Startbildschirm brauchte mit
#: sechs Projekten 198 Pixel Rollweg auf 1920x1080 und 378 auf 1600x900. Leer
#: waren es 26 beziehungsweise 206 — die Liste allein kostete 172 Pixel und
#: fraß damit genau den Gewinn auf, den ein früherer Umbau gebracht hatte.
RECENT_ROWS = 4

#: Kacheln je Zeile. Zwei bei 900 Pixel heißt gut 430 pro Kachel: das
#: Vorschaubild links, daneben Titel und Satz.
TILE_COLUMNS = 2

#: Unter zwei lesbaren Kachelbreiten wird aus dem Raster eine Liste. Senkrecht
#: rollen ist auf einem schmalen Fenster erwartbar; waagerecht suchen ist es
#: nicht.
NARROW_COLUMNS = 1

#: Wie schmal eine Kachel werden darf, bevor Titel und Satz aneinander kleben.
#:
#: Gemessen an der Zweispaltigkeit, die es seit je gibt: 900 Pixel Spalte, zwei
#: Kacheln, gut 430 je Stück. Darunter wird der Satz zur Wortkolonne.
TILE_MIN_WIDTH = 420

#: Abstand zwischen zwei Beispielkacheln. Er gehört zur Umschaltgrenze: Zwei
#: 420 Punkte breite Kacheln passen erst, wenn auch diese Fuge Platz hat.
TILE_GRID_SPACING = NORMAL

#: Tatsächlich verfügbare Breite, ab der das Raster zwei Spalten tragen kann.
MEDIUM_LAYOUT_MIN_WIDTH = 2 * TILE_MIN_WIDTH + TILE_GRID_SPACING + WIDE

#: Wie breit die Spalte wird, wenn drei Kacheln nebeneinander passen.
#:
#: Auf 1920 mal 1080 blieben neben der 900 Pixel breiten Spalte gut 900 leer,
#: während unten die neunte Kachel und „Zuletzt geöffnet" unter der Kante lagen
#: — gemessen: Sichtfeld 956, Inhalt 1154. Fünf Kachelzeilen wurden zu vier,
#: sobald die Breite genutzt wird. Der Satz über :data:`COLUMN_WIDTH` gilt
#: weiter für Text; hier geht es um ein Raster aus Bildern.
WIDE_COLUMN_WIDTH = 1360

#: Ab dieser **verfügbaren** Breite trägt das zusätzliche Raster wirklich.
#:
#: Der frühere Sprung bei drei theoretischen Mindestbreiten (1260 Punkte)
#: machte schon ein 1536-Punkte-Fenster 1360 Punkte breit, obwohl die vier
#: sichtbaren Einstiege bewusst als zwei mal zwei stehen. Erst ab 1600 Punkten
#: bleibt neben einer dritten Rasterspalte genug Ruhe für die Texte.
WIDE_LAYOUT_MIN_WIDTH = 1600

#: Die Ablagefläche ist eine große Trefferfläche, aber kein eigener Bildschirm.
#: Seit Formatliste und Verweis in der Kurzhilfe stehen (RM-515), trägt sie
#: Zeichen und zwei kurze Sätze.
DROP_AREA_MIN_HEIGHT = 88


class DropArea(QPushButton):
    """Die große Ablagefläche für Projekte, Modelle und Bausteindateien.

    Vorher stand hier ein Satz in der Bildmitte, ohne Rahmen, ohne Feld, ohne
    Symbol — man sah nicht, dass das eine Ablagefläche ist. Der gestrichelte
    Rahmen kommt aus dem Thema und nicht aus ``palette(mid)``: das war im
    dunklen Thema unsichtbar, also genau dort, wo die Anwendung startet.
    """

    fileDropped = Signal(Path)
    filesDropped = Signal(object)
    urlDropped = Signal(str)
    """Ein Verweis aus dem Browser, gezogen statt heruntergeladen (§16.3)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropArea")
        self.setFlat(True)
        self.setAutoDefault(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setAcceptDrops(True)
        self.setMinimumHeight(DROP_AREA_MIN_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

        self.symbol = QLabel(self)
        self.symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size = self.fontMetrics().height() * 2
        self.symbol.setPixmap(icon("import", self).pixmap(size, size))

        # „Bausteindatei" steht hier nicht mehr: Beim allerersten Start ist
        # das Wort bedeutungslos, und die Endungsliste darunter nennt die
        # Endung ohnehin. Der zweite Satz sagt, dass Klicken auch geht.
        hint_text = tr("Modell oder Projekt hier ablegen")
        click_text = tr("oder klicken, um eine Datei zu wählen")
        self.setAccessibleName(f"{hint_text} — {click_text}")
        hint = QLabel(hint_text, self)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        set_level(hint, "section")
        click_hint = QLabel(click_text, self)
        click_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        click_hint.setWordWrap(True)
        set_level(click_hint, "caption")

        # **Formatliste und Verweis stehen in der Kurzhilfe** (RM-515, D15):
        # neunzehn Endungen und ein Satz machten die Fläche zu einem Absatz.
        # Wer wissen will, ob seine Datei geht, zeigt auf die Fläche; wer sie
        # einfach ablegt, liest nichts. Das Feld nimmt auch einen Verweis
        # (:attr:`urlDropped`) — der kürzeste Weg von einer Modellseite hierher.
        self.formats = " · ".join(
            suffix.lstrip(".").upper()
            for suffix in (*IMPORT_SUFFIXES, PROJECT_SUFFIX, PART_FILE_SUFFIX)
        )
        self._tip = tr(
            "Liest {formats}. Auch ein Verweis aus dem Browser geht.", formats=self.formats
        )
        self.setToolTip(self._tip)
        self.setAccessibleDescription(self._tip)

        # Die Antwort auf eine Datei, die Solidon nicht liest (RM-358 W1-6):
        # Die Quittung des Fensters liegt über der Ansicht und damit hinter
        # dem Startbildschirm; hier steht der Satz dort, wo abgelegt wurde.
        self.note = QLabel("", self)
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.setWordWrap(True)
        self.note.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.setSpacing(TIGHT)
        layout.addStretch(1)
        layout.addWidget(self.symbol)
        layout.addWidget(hint)
        layout.addWidget(click_hint)
        layout.addWidget(self.note)
        layout.addStretch(1)
        self._painted: tuple[str, bool] | None = None
        self._paint("dark")

    def say(self, text: str) -> None:
        """Einen Satz zur zuletzt abgelegten Datei zeigen — leer räumt ihn weg."""
        self.note.setText(text)
        self.note.setVisible(bool(text))
        self.setAccessibleDescription(text or self._tip)
        self.updateGeometry()

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Die Beschriftungen bestimmen die Höhe des zusammengesetzten Knopfs."""

        hint = super().sizeHint()
        layout = self.layout()
        if layout is None:
            return hint
        content = layout.sizeHint()
        wrapped_reserve = self.fontMetrics().height()
        return QSize(
            max(hint.width(), content.width()),
            max(hint.height(), content.height() + wrapped_reserve),
        )

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Auch bei großer Systemschrift keine Beschriftung zusammendrücken."""

        layout = self.layout()
        if layout is None:
            return super().minimumSizeHint()
        content = layout.minimumSize()
        # QBoxLayout zählt bei umbrechenden Labels nur deren einzeilige
        # Mindesthöhe. Eine Zeile Reserve hält auch bei großer Systemschrift
        # beide Sätze vollständig sichtbar.
        wrapped_reserve = self.fontMetrics().height()
        return QSize(
            content.width(),
            max(DROP_AREA_MIN_HEIGHT, content.height() + wrapped_reserve),
        )

    def hasHeightForWidth(self) -> bool:  # noqa: N802 — Qt-Name
        """Der umbrochene Inhalt meldet seine Höhe an das äußere Layout."""

        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 — Qt-Name
        """Die Höhe sämtlicher umbrochener Beschriftungen bei ``width``."""

        layout = self.layout()
        if layout is None:
            return DROP_AREA_MIN_HEIGHT
        return max(DROP_AREA_MIN_HEIGHT, layout.heightForWidth(width))

    def _paint(self, theme: str) -> None:
        """Malt nur, wenn sich etwas geändert hat.

        Ohne diese Prüfung eine Endlosschleife: ``setStyleSheet`` löst selbst
        ein ``PaletteChange`` aus, und das führte zurück hierher.
        """
        state = (theme, self._hover)
        if state == self._painted:
            return
        self._painted = state
        colours = THEMES["light" if theme == "light" else "dark"]
        edge = colours["highlight"] if self._hover else colours["line"]
        fill = colours["alternate"] if self._hover else "transparent"
        self.setStyleSheet(
            f"#dropArea {{ border: 2px dashed {edge}; border-radius: {NORMAL}px;"
            f" background: {fill}; min-height: {DROP_AREA_MIN_HEIGHT}px; }}"
        )

    def changeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self._paint(current_theme())

    def _set_hover(self, hover: bool) -> None:
        if hover == self._hover:
            return
        self._hover = hover
        self._paint(current_theme())

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt name
        if dropped_file(event) is not None or accepted_url(event) is not None:
            self.say("")
            self._set_hover(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802 - Qt name
        self._set_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt name
        self._set_hover(False)
        paths = accepted_paths(event)
        if paths:
            if len(paths) > 1:
                self.filesDropped.emit(paths)
            else:
                self.fileDropped.emit(paths[0])
            event.acceptProposedAction()
            return
        url = accepted_url(event)
        if url is not None:
            self.urlDropped.emit(url)
            event.acceptProposedAction()
            return
        # Eine Datei, die Solidon nicht liest, bekommt trotzdem eine Antwort:
        # das Fenster sagt, wie das Modell hereinkommt (RM-358 W1-6).
        other = dropped_file(event)
        if other is not None:
            self.fileDropped.emit(other)
            event.acceptProposedAction()


def current_theme() -> str:
    """Welches Thema gerade gilt — abgelesen an der Fensterfarbe der Anwendung.

    Ein Widget kennt seine Palette, aber nicht den Namen des Themas; die Farbe
    zu vergleichen ist ehrlicher, als das Thema durch fünf Ebenen zu reichen.

    Gefragt wird die **Anwendung**, nicht das Widget. Ein Widget mit eigenem
    Stylesheet hat eine eigene Palette, und die ändert sich, sobald hier
    gemalt wird — das war eine Endlosschleife aus Malen und Nachsehen.
    """
    application = QApplication.instance()
    if not isinstance(application, QApplication):
        return "dark"
    return "light" if application.palette().window().color().lightness() > 127 else "dark"


#: Wie hoch ein Vorschaubild in der Kachel steht. Groß genug, um die Form zu
#: erkennen, klein genug, dass Titel und Satz ihre Zeilen behalten — die
#: Beispiele unter „Was kann das noch?“.
PREVIEW_HEIGHT = 88

#: Das Vorschaubild der vier Einstiege. Sie sind der Anfang des Programms und
#: stehen deshalb größer als alles andere auf der Seite (RM-515); die Kachel
#: wird damit rund anderthalbmal so hoch, und der Titel bekommt die Größe
#: dazu (:data:`START_TITLE_SCALE`).
START_PREVIEW_HEIGHT = 132

#: Schriftgröße eines Einstiegstitels relativ zur Grundschrift — zwischen
#: Abschnitt (1,15) und Fenstertitel (1,75): Die vier sollen auffallen, ohne
#: lauter zu sein als der Name der Anwendung darüber.
START_TITLE_SCALE = 1.4


def _preview_pixmap(entry: Example, height: int = PREVIEW_HEIGHT) -> QPixmap | None:
    """Das Vorschaubild eines Beispiels als Pixmap, oder nichts.

    Gerastert wird beim Aufbau der Kachel: das SVG ist ein Bild und kein
    Zustand, und es steht in derselben Größe, solange der Startbildschirm
    offen ist.
    """
    source = examples.preview_of(entry)
    if not source:
        return None
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        return None
    image = QImage(QSize(height, height) * 2, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(2.0)
    return QPixmap.fromImage(image)


class ExampleTile(QPushButton):
    """Ein Beispielprojekt als Kachel: Titel, ein Satz, und klickbar.

    Vorher eine Zeile Text unter sechs anderen. Eine Liste sagt nicht, dass
    hinter jedem Eintrag ein fertiges Projekt mit einer geführten Tour liegt —
    und §37.2 nennt die Beispiele Dokumentation, Abnahmetest und Inhalt des
    Startbildschirms zugleich.
    """

    chosen = Signal(Path)

    def __init__(self, entry: Example, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("exampleTile")
        self.entry = entry
        self.path = path
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        guided = tr("Geführte Tour · Schritt für Schritt")
        # Eine Kachel ist ein Knopf aus zwei Labels, und ein Bildschirmleser
        # las davon nichts vor: Der Titel gehört einem Kind, nicht ihr. Neun
        # solcher Kacheln sind das Erste, was jemand hier sieht — und ohne
        # Namen neun Mal „Rahmen".
        self.setAccessibleName(str(entry.title))
        self.setAccessibleDescription(f"{entry.doc} {guided}")
        self.clicked.connect(lambda _checked=False: self.chosen.emit(self.path))
        # Waagerecht dehnbar, senkrecht mitwachsend: sonst steht neben einer
        # Kachel mit drei Zeilen eine mit zwei, und die Zeile sieht schief aus.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        # **Tiefe als Rückmeldung, ohne Bewegung.** Überfahren hebt die Kachel
        # leicht an, Tastaturfokus bleibt zusätzlich der klare Rahmen aus dem
        # gemeinsamen Stylesheet. Es läuft keine Animation: Wer reduzierte
        # Bewegung gewählt hat, bekommt dieselbe unmittelbare Antwort.
        self._hovered = False
        self._shadow = QGraphicsDropShadowEffect(self)
        self.setGraphicsEffect(self._shadow)
        self._paint_depth()

        # **Die vier Einstiege groß, die übrigen Beispiele ruhig** (RM-515):
        # Vorher waren alle Kacheln gleich und Feedback und Spende genauso
        # groß — der Blick fand keinen Anfang. Ob eine Kachel ein Einstieg
        # ist, sagt das Beispiel selbst (``way``).
        self.starts = bool(entry.way)
        title = QLabel(str(entry.title), self)
        title.setWordWrap(True)
        if self.starts:
            title.setObjectName("startTourTitle")
            base = max(QApplication.font().pointSize(), 1)
            title.setStyleSheet(
                f"QLabel#startTourTitle {{ font-size: {round(base * START_TITLE_SCALE)}pt;"
                " font-weight: 600; }"
            )
        else:
            set_level(title, "section")
        self.title_label = title

        doc = QLabel(str(entry.doc), self)
        doc.setWordWrap(True)
        set_level(doc, "body" if self.starts else "caption")

        # Das Bild kommt aus dem Beispiel selbst, gerendert von
        # `tools/make_examples.py` beim Bauen. Fehlt es, steht die Kachel wie
        # vorher da: ein frisch ausgecheckter Baum hat die Bilder erst, wenn
        # das Werkzeug gelaufen ist, und eine leere Fläche wäre schlimmer als
        # keine.
        self.preview = QLabel(self)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        picture = _preview_pixmap(entry, START_PREVIEW_HEIGHT if self.starts else PREVIEW_HEIGHT)
        self.preview.setVisible(picture is not None)
        if picture is not None:
            self.preview.setPixmap(picture)

        # Der Text sitzt in einem eigenen Widget, nicht in einem Layout im
        # Layout: ein umbrechendes Label meldet seine bevorzugte Breite, und
        # ein verschachteltes Layout gibt ihm nicht mehr. Der Satz brach nach
        # fünf Wörtern um, während rechts dreihundert Pixel frei blieben.
        words = QWidget(self)
        # ``setHeightForWidth`` ist der Teil, ohne den nichts davon greift: ein
        # umbrechendes Label bestimmt seine Höhe aus seiner Breite, und ein
        # Layout, dem diese Abhängigkeit nicht angemeldet ist, rechnet mit der
        # bevorzugten Breite und lässt den Rest der Kachel leer stehen.
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        words.setSizePolicy(policy)
        text = QVBoxLayout(words)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(TIGHT)
        # Ein Einstieg stellt Titel und Satz mittig neben sein großes Bild;
        # oben angeschlagen stand unter zwei Zeilen eine leere Kachelhälfte.
        if self.starts:
            text.addStretch(1)
        text.addWidget(title)
        text.addWidget(doc)
        # Der Überschuss sammelt sich unten, nicht zwischen Titel und Satz:
        # eine Kachel wächst auf die Höhe ihrer Nachbarin, und ohne diese
        # Feder verteilte Qt die gewonnene Höhe auf beide Beschriftungen.
        #
        # Sie steht hier und nicht im waagerechten Layout darunter. Dort war
        # sie es, die den Satz auf hundertachtundsechzig Pixel zusammendrückte
        # — beim Umbau von einer Spalte auf Bild-und-Text wurde aus einer
        # senkrechten Feder eine waagerechte, und die frisst, was der Text
        # gebraucht hätte.
        text.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.preview)
        layout.addWidget(words, stretch=1)

    def _paint_depth(self) -> None:
        """Eine ruhige Karte und eine klar angehobene unter dem Zeiger."""
        active = self._hovered or self.hasFocus()
        self._shadow.setBlurRadius(18.0 if active else 8.0)
        self._shadow.setOffset(0.0, 3.0 if active else 1.0)
        self._shadow.setColor(QColor(0, 0, 0, 82 if active else 40))

    def enterEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        self._hovered = True
        self._paint_depth()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        self._hovered = False
        self._paint_depth()
        super().leaveEvent(event)

    def focusInEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().focusInEvent(event)
        self._paint_depth()

    def focusOutEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().focusOutEvent(event)
        self._paint_depth()

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        """Was mit der Maus geht, geht mit der Tastatur (§19.2)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)


def accepted_url(event: QDragEnterEvent | QDropEvent) -> str | None:
    """Die erste fallengelassene **Web**-Adresse.

    Wer aus dem Browser einen Herunterladen-Verweis auf das Fenster zieht,
    meint dieselbe Handlung wie mit einer Datei — und bekam bisher nichts, weil
    :func:`accepted_path` alles verwirft, was keine lokale Datei ist.

    **Jede Web-Adresse wird angenommen, nicht nur eine mit Modellendung.** Die
    Endung war hier bis zum 22.09.2026 die Bedingung, und der häufigste Fall
    fiel durch: der Verweis auf die Modellseite selbst. Er bekam beim Ziehen
    ein Verbotszeichen und keinen Satz. Ob hinter der Adresse eine Datei
    liegt, sagt jetzt :mod:`app.core.ingest.fetch` — für eine Modellseite ohne
    Netzzugriff und mit dem Weg, der geht.
    """
    data = event.mimeData()
    if not data.hasUrls():
        return None
    for url in data.urls():
        if url.isLocalFile() or url.scheme().lower() not in ("http", "https"):
            continue
        return str(url.toString())
    return None


def dropped_file(event: QDragEnterEvent | QDropEvent) -> Path | None:
    """Die erste fallengelassene lokale Datei, gleich welcher Art (RM-358 W1-6).

    Ein Fenster, das eine Datei nicht liest, nimmt sie trotzdem an und sagt,
    wie das Modell hereinkommt. Vorher filterte das Ziehen nach Endung, und
    ``.f3d``, ``.blend``, ``.scad`` oder ``.gcode`` bekamen nur das
    Verbotszeichen — eine Absage ohne Satz. Was mit der Datei geschieht,
    entscheidet ``MainWindow.open_path``.
    """
    data = event.mimeData()
    if not data.hasUrls():
        return None
    for url in data.urls():
        if url.isLocalFile():
            return Path(url.toLocalFile())
    return None


def accepted_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
    """Die erste fallengelassene Datei, mit der diese Anwendung etwas
    anfangen kann.
    """
    paths = accepted_paths(event)
    return paths[0] if paths else None


def accepted_paths(event: QDragEnterEvent | QDropEvent) -> list[Path]:
    """Modelldateien in Ziehreihenfolge; eine Mehrfachauswahl bleibt vollständig.

    Unbekannte Dateien in einer Auswahl erreichen ebenfalls den Importplan,
    damit ein Fehler die ganze Auswahl benennt und nichts still verschwindet.
    """
    data = event.mimeData()
    if not data.hasUrls():
        return []
    paths = [Path(url.toLocalFile()) for url in data.urls() if url.isLocalFile()]
    if len(paths) > 1:
        return paths
    return [
        path
        for path in paths
        if path.suffix.lower() in (*IMPORT_SUFFIXES, PROJECT_SUFFIX, PART_FILE_SUFFIX)
    ]


class FooterLink(QPushButton):
    """Ein schlichter Nebenweg in der Fußzeile: Symbol und Name, der Rest in der Kurzhilfe.

    Feedback und Unterstützung standen als Karten so groß wie die vier
    Einstiege da (A17) — zwei Nebenwege sahen aus wie zwei weitere Anfänge.
    Hier sind sie flache Knöpfe unter allem anderen; was sie öffnen und warum,
    sagen Kurzhilfe und Bildschirmleser.
    """

    def __init__(self, title: str, detail: str, symbol: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setObjectName("startFooterLink")
        self.setFlat(True)
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(detail)
        self.setAccessibleName(title)
        self.setAccessibleDescription(detail)
        self._symbol = symbol
        self._refresh_icon()
        make_large_target(self)
        # Wann zuletzt ausgelöst wurde (``time.monotonic``) — der Doppelklick
        # unten fragt danach.
        self._last_click = -float("inf")
        self.clicked.connect(self._note_click)

    def _note_click(self) -> None:
        self._last_click = time.monotonic()

    def _refresh_icon(self) -> None:
        self.setIcon(icon(self._symbol, self))

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        """Die Eingabetaste löst aus wie die Leertaste (§19.2) — einmal, ohne Wiederholung.

        Ein Knopf außerhalb eines Dialogs nimmt sonst nur die Leertaste.
        """
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not event.isAutoRepeat():
                self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        """Ein hastiger Doppelklick öffnet genau ein modales Fenster, nicht zwei und nicht keins.

        Auf echten Plattformen hat der erste Klick schon ausgelöst, und der
        zweite Druck bleibt liegen. QTest und manche Hilfsmittel senden aber
        nur das Doppelklick-Ereignis; seit RM-515 schluckte der Fußzeilenknopf
        es ganz, und so ein Doppelklick öffnete nichts. Ohne frischen Klick
        davor löst er deshalb selbst einmal aus.
        """
        recent = time.monotonic() - self._last_click <= QApplication.doubleClickInterval() / 1000.0
        if event.button() == Qt.MouseButton.LeftButton and not recent:
            self.click()
        event.accept()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 — Qt-Name
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._refresh_icon()


class InventoryStartCard(QPushButton):
    """Ein direkter Lagerzugang mit echter Spulenzahl und Farbabbildung."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAutoDefault(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        self.colours = QLabel(self)
        self.colours.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.colours)
        self.caption = QLabel(self)
        self.caption.setWordWrap(True)
        self.caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        set_level(self.caption, "section")
        layout.addWidget(self.caption, 1)
        self.refresh()

    def refresh(self) -> None:
        """Nur die Kachel liest das Lager; das Projekt bleibt unverändert."""
        try:
            entries = filaments.catalogue()
        except AppError as problem:
            # **Auf eine Kachel passt ein Satz, nicht der ganze Fehler.** Der
            # vollständige Text stand hier in der Beschriftung und brauchte
            # gemessene 250 Bildpunkte Höhe in 54 — Ursache und Rat lagen unter
            # der Kante, und ein Tooltip, der sie noch trüge, gab es nicht.
            # Die Kachel sagt jetzt, dass etwas nicht stimmt; der ganze Satz
            # steht in Kurzhilfe und Beschreibung (Regel 17 und 18), und der
            # Klick führt ins Lager, wo er mit seinen Knöpfen steht.
            short = str(tr("Filamentlager · nicht lesbar"))
            self.caption.setText(short)
            self.caption.setToolTip(str(problem))
            self.setToolTip(str(problem))
            self.setAccessibleName(short)
            self.setAccessibleDescription(str(problem))
            self.colours.clear()
            return
        text = (
            tr("Filamentlager · {count} Spule")
            if len(entries) == 1
            else tr("Filamentlager · {count} Spulen")
        ).format(count=len(entries))
        self.caption.setText(text)
        # Ein gelöstes Problem nimmt seine Kurzhilfe mit: Sonst behauptete sie
        # beim nächsten Blick einen Fehler, den die Zeile darüber verneint.
        self.caption.setToolTip("")
        self.setToolTip("")
        self.setAccessibleName(text)
        self.setAccessibleDescription(tr("Spulen ansehen, anlegen und Bestand pflegen."))
        shown = entries[:3] or (filaments.CatalogueFilament("", "#808080"),)
        image = QPixmap(32 * len(shown), 32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        for index, entry in enumerate(shown):
            paint_spool(
                painter,
                QRectF(index * 32, 0, 32, 32),
                entry,
                self.palette().buttonText().color(),
                self.palette().button().color(),
            )
        painter.end()
        self.colours.setPixmap(image)


class StartScreen(QWidget):
    """Was gezeigt wird, bevor ein Projekt offen ist."""

    openRequested = Signal(Path)
    newRequested = Signal()
    browseRequested = Signal()
    importRequested = Signal()
    """Ein Modell öffnen — STL, 3MF, OBJ und die übrigen Formate.

    „Projekt öffnen …" zeigt nur ``.p3d``. Wer Solidon wegen einer
    heruntergeladenen STL zum ersten Mal startet, klickte dort, sah ein
    leeres Verzeichnis und war am Ende seines Wegs; der funktionierende Knopf
    hieß anders und stand in der Werkzeugleiste (Review 02.09.2026).
    """
    fileDropped = Signal(Path)
    filesDropped = Signal(object)
    urlDropped = Signal(str)
    """Eine Adresse aus dem Browser ist hier gelandet — dieselbe Handlung wie
    eine Datei, nur liegt sie noch nicht auf der Platte (§16.3)."""
    forgetRequested = Signal(Path)
    """Ein Eintrag soll aus der Liste verschwinden — die Datei bleibt."""
    manualRequested = Signal()
    """Das Handbuch soll aufgehen — hier, wo es gebraucht wird, nicht erst
    im Hilfemenü eines Fensters, das ein neuer Nutzer noch nie gesehen hat."""
    feedbackRequested = Signal()
    """Die bestehende Rückmeldung soll vom ersten Bildschirm aus aufgehen."""
    supportRequested = Signal()
    """Der lokale Hinweis zur freiwilligen Unterstützung soll aufgehen."""
    inventoryRequested = Signal()
    """Das Filamentlager soll ohne Umweg über ein Projekt aufgehen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        title = QLabel(APP_NAME, self)
        set_level(title, "title")

        self.recent_list = QListWidget(self)
        # **Ein Klick öffnet** (RM-269): Ein Eintrag sieht aus wie ein Verweis,
        # ``itemActivated`` allein hieß unter Windows aber Doppelklick oder
        # Eingabetaste. Die Tastatur bleibt über ``itemActivated``; dass ein
        # Doppelklick beide meldet, fängt :meth:`_on_recent` ab.
        self.recent_list.itemClicked.connect(self._on_recent)
        self.recent_list.itemActivated.connect(self._on_recent)
        self.recent_list.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self._recent_opened: tuple[str, float] = ("", 0.0)
        """Welcher Eintrag zuletzt öffnete, und wann (``time.monotonic``)."""
        # Zehn Einträge, und was einmal darin stand, blieb bis es hinausrutschte:
        # ein Versuchsprojekt hielt sich länger als das Interesse daran.
        self.recent_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recent_list.customContextMenuRequested.connect(self._on_recent_menu)
        # **Vier Zeilen hoch, nicht vier Einträge lang.** Der Startbildschirm
        # passte gemessen auf keinen Schirm ohne Rollen, sobald die Liste sich
        # füllte: leer blieben 26 Pixel Rollweg auf 1920x1080, mit sechs
        # Projekten waren es 198 — genau der Wert, den ein früherer Umbau
        # beseitigt hatte. Die Liste fraß den Gewinn auf, sobald jemand die
        # Anwendung ein paarmal benutzt hatte.
        #
        # Wie hoch sie höchstens wird, entscheidet :meth:`show_recent` — dort
        # steht die Zeilenhöhe fest. Eine leere Liste hat keine, und
        # ``sizeHintForRow`` gibt dort einen Vorgabewert zurück, der um mehr
        # als das Doppelte danebenliegt (77 statt 30).

        # §37.2: die Beispielprojekte sind Inhalt des Startbildschirms und kein
        # Ordner, den jemand suchen muss.
        #
        # **Zwei Raster und nicht eines.** Der Code kennt die Zweiteilung seit
        # je — ``examples.py`` sagt es im Kommentar: „Die vier oben beantworten
        # >wie fange ich an<, diese >was kann das eigentlich<." Die Oberfläche
        # zeigte neun gleich aussehende Kacheln unter einer Überschrift, und der
        # Erstnutzer musste aus den Titeln „Weg 1 … Weg 4" schließen, dass genau
        # diese vier der Anfang sind. Das Wort „Weg" erklärt der Startbildschirm
        # nirgends; es stammt aus Bauplan §2.2.
        self.examples_area = QWidget(self)
        self.examples_grid = QGridLayout(self.examples_area)
        self.examples_grid.setContentsMargins(0, 0, 0, 0)
        self.examples_grid.setSpacing(TILE_GRID_SPACING)
        self.more_area = QWidget(self)
        self.more_grid = QGridLayout(self.more_area)
        self.more_grid.setContentsMargins(0, 0, 0, 0)
        self.more_grid.setSpacing(TILE_GRID_SPACING)
        self.tiles: list[ExampleTile] = []
        self._columns = TILE_COLUMNS
        """Wie viele Kacheln gerade in eine Zeile gelegt werden."""
        self.show_examples()

        # Der Hauptknopf sieht aus wie einer. Vorher standen beide in
        # gewöhnlicher Größe nebeneinander und sagten nicht, welcher gemeint
        # ist, wenn man nichts Bestimmtes vorhat.
        self.new_button = QPushButton(tr("Neues Projekt"), self)
        make_primary(self.new_button)
        make_large_target(self.new_button)
        self.new_button.clicked.connect(self.newRequested)
        # **Die Knöpfe heißen wie in der Werkzeugleiste und im Menü** (A17):
        # „Modell öffnen …“ und „Projekt öffnen …“ hier, „Modell einfügen“ und
        # „Öffnen“ dort — der Kunde sucht beim zweiten Mal das Wort, das er
        # zuerst gelesen hat.
        self.import_button = QPushButton(tr("Modell einfügen …"), self)
        self.import_button.setToolTip(tr("Eine STL-, 3MF- oder andere Modelldatei einfügen."))
        make_large_target(self.import_button)
        self.import_button.clicked.connect(self.importRequested)
        self.open_button = QPushButton(tr("Öffnen …"), self)
        self.open_button.setToolTip(tr("Ein gespeichertes Projekt öffnen (.p3d)."))
        make_large_target(self.open_button)
        self.open_button.clicked.connect(self.browseRequested)

        drop = DropArea(self)
        self.drop_area = drop
        drop.fileDropped.connect(self.fileDropped)
        drop.filesDropped.connect(self.filesDropped)
        drop.urlDropped.connect(self.urlDropped)
        drop.clicked.connect(self.importRequested)

        # „Wo fange ich an?" steht im Handbuch — aber der Weg dorthin führte
        # über das Hilfemenü des Hauptfensters, das beim ersten Start noch
        # niemand gesehen hat. Der Verweis gehört hierher, und zwar neben die
        # Knöpfe: am anderen Fensterrand gehörte er sichtbar zu nichts.
        # **Der Knopf nennt seine Handlung, der Zusatz steht daneben** (B27).
        self.manual_button = QPushButton(tr("Handbuch"), self)
        self.manual_button.setToolTip(
            tr("Wo fange ich an? Anleitungen in Bildern, vom ersten Klick bis zum Druck.")
        )
        self.manual_button.setFlat(True)
        make_large_target(self.manual_button)
        self.manual_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_button.clicked.connect(self.manualRequested)

        # **Zwei Nebenwege als Fußzeile, nicht als Karten** (A17). Sie öffnen
        # nur vorhandene lokale Dialoge: Rückmeldung versendet erst nach der
        # Vorschau, Unterstützung führt erst nach der Anbieterwahl zu PayPal
        # oder GoFundMe. Wofür, nicht womit (Entscheidung Robert, 23.09.2026):
        # Der Satz nennt, was das Geld trägt; die Anbieter und „freiwillig“
        # stehen dahinter.
        self.feedback_button = FooterLink(
            tr("Feedback geben"),
            tr(
                "Eine Person entwickelt Solidon unabhängig. Was soll für Sie besser "
                "werden? Vorschau vor dem Senden."
            ),
            "feedback",
            self,
        )
        self.feedback_button.clicked.connect(self.feedbackRequested)
        self.support_button = FooterLink(
            tr("Solidon unterstützen"),
            tr(
                "Trägt die Werkzeuge und laufenden Kosten der Entwicklung. "
                "Freiwillig, über PayPal oder GoFundMe."
            ),
            "support",
            self,
        )
        self.support_button.clicked.connect(self.supportRequested)
        self.secondary_actions = [self.feedback_button, self.support_button]
        self.footer = QWidget(self)
        footer = QHBoxLayout(self.footer)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(NORMAL)
        for link in self.secondary_actions:
            footer.addWidget(link)
        footer.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(NORMAL)
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.import_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.manual_button)
        buttons.addStretch(1)
        self.inventory_button = InventoryStartCard(self)
        self.inventory_button.clicked.connect(self.inventoryRequested)
        self._primary_actions = QGridLayout()
        self._primary_actions.setContentsMargins(0, 0, 0, 0)
        self._primary_actions.setSpacing(NORMAL)
        self._primary_actions.addLayout(buttons, 0, 0)
        self._primary_actions.addWidget(self.inventory_button, 0, 1)
        self._inventory_below = False

        # „Zuletzt geöffnet“ nur, wenn es etwas gibt (:meth:`show_recent`):
        # Beim ersten Start war „Noch nichts geöffnet.“ eine Zeile über
        # nichts, und dann steht Weiterarbeiten vor Entdecken.
        self.recent_section = QWidget(self)
        recent = QVBoxLayout(self.recent_section)
        recent.setContentsMargins(0, 0, 0, 0)
        recent.setSpacing(TIGHT)
        recent.addWidget(_caption(tr("Zuletzt geöffnet"), self.recent_section))
        recent.addWidget(self.recent_list)

        column = QWidget(self)
        self.column = column
        """Die Spalte, deren Breite über die Zahl der Kachelspalten entscheidet."""
        column.setMaximumWidth(COLUMN_WIDTH)
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(NORMAL)
        inner.addWidget(title)
        inner.addWidget(self.recent_section)
        # **Die vier Einstiege oben und groß** (RM-515): Sie sind die Struktur
        # des Programms, die vier Wege aus §2.2. Die Überschrift nennt keine
        # Zahl — „Vier geführte Touren“ stand über sechs Karten.
        #
        # **Einmal über der Gruppe, nicht viermal darin** (B27): Dass hinter
        # jeder Kachel eine Führung beginnt, steht hier; in der Beschreibung
        # jeder Kachel bleibt der Satz, denn ein Vorleser sieht nicht, was
        # darüber steht.
        self.tours_heading = _caption(
            tr("Wo fange ich an? Geführte Touren, Schritt für Schritt."), self
        )
        inner.addWidget(self.tours_heading)
        inner.addWidget(self.examples_area)
        inner.addLayout(self._primary_actions)
        inner.addWidget(drop)
        # **Die weiteren Beispiele klappen zu, die vier Wege nicht.** Wer den
        # Startbildschirm zum ersten Mal sieht, soll die vier sehen; die
        # übrigen sind Vertiefung. Die Überschrift **wird** der Umschalter.
        self.more_section = collapsible(
            tr("Was kann das noch?"),
            self.more_area,
            open_now=False,
            contents=tr("Weitere Beispielprojekte"),
        )
        inner.addWidget(self.more_section)
        inner.addWidget(self.footer)
        # **Ausbalanciert, nicht oben angedockt** (Befund B27): Zwei
        # Dehnfelder teilen den Überschuss, oben weniger als unten. Die Spalte
        # steht dann etwas über der Mitte, wo der Blick sie sucht.
        inner.insertStretch(0, 1)
        inner.addStretch(3)

        centred = QWidget(self)
        centred_policy = centred.sizePolicy()
        centred_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        centred.setSizePolicy(centred_policy)
        middle = QHBoxLayout(centred)
        self._middle = middle
        # Zwei statt drei Weiten Rand: Die drei waren Luft, die oben und unten
        # zusammen zweiunddreißig Pixel kostete.
        middle.setContentsMargins(WIDE * 2, WIDE * 2, WIDE * 2, WIDE * 2)
        middle.addStretch()
        # **Mit Dehnung, sonst bleibt die Spalte bei ihrer Wunschbreite.**
        # ``setMaximumWidth`` erlaubt nur; es zieht nicht. Nur die Spalte
        # erhält einen Dehnungsfaktor: Bis zu ihrem Maximum nimmt sie jeden
        # verfügbaren Punkt, erst danach teilt Qt den Rest auf die Federn.
        middle.addWidget(column, 1)
        middle.addStretch()

        # In einem Rollbereich, weil die Spalte bei einem kleinen Fenster sonst
        # unten abgeschnitten wird — und was man nicht sieht, gibt es nicht.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Die schmale Fassung wird eine Kachelspalte und wächst nach unten.
        # Ein zweiter Rollweg wäre kein Ausweichen, sondern abgeschnittener
        # Inhalt, den man erst durch Probieren findet.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(centred)
        self.page_scroll: QScrollArea = scroll

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._order_the_tab_chain()
        self.show_recent([])

    def _fit_the_columns(self) -> None:
        """Wie viele Kacheln in eine Zeile passen — und wie breit die Spalte dafür ist.

        Auf 1920 mal 1080 blieben neben der 900 Pixel breiten Spalte gut 900
        leer, während unten die neunte Kachel und „Zuletzt geöffnet" unter der
        Kante lagen: Sichtfeld 956, Inhalt 1154. Die Breite lag da und wurde
        nicht benutzt.

        Drei Spalten machen aus fünf Kachelzeilen vier. Sie brauchen eine
        breitere Spalte, und die ist kein Widerspruch zum Satz über
        :data:`COLUMN_WIDTH`: Der gilt für Text — hier geht es um ein Raster aus
        Bildern, und die Beschriftungen darüber bleiben kurz.

        Neu gelegt wird nur, wenn sich die Zahl **ändert**. Bei jedem
        Größenereignis neun Kacheln neu zu bauen wäre ein Ruck bei jedem Zug am
        Fensterrand.
        """
        available = self.width() - 2 * WIDE * 2
        wide_enough = available >= WIDE_LAYOUT_MIN_WIDTH
        narrow = available < MEDIUM_LAYOUT_MIN_WIDTH
        # Der Rollbereich darf bei 640 Punkten nicht an seiner Wunschbreite
        # festhalten. Im einspaltigen Rückweg reichen kompakte Außenränder;
        # die Kacheln selbst behalten ihren großzügigen Innenraum.
        horizontal_margin = NORMAL if narrow else WIDE * 2
        # Auf niedrigen Fenstern bleibt der Inhalt vollständig sichtbar,
        # ohne die Karten oder Touren zusammenzustauchen. Breite Bildschirme
        # behalten ihre ruhige Einfassung; nur die ohnehin knappe Höhe nutzt
        # den Rand als Reserve.
        vertical_margin = NORMAL if self.height() < 800 else horizontal_margin
        self._middle.setContentsMargins(
            horizontal_margin,
            vertical_margin,
            horizontal_margin,
            vertical_margin,
        )
        self.column.setMaximumWidth(WIDE_COLUMN_WIDTH if wide_enough else COLUMN_WIDTH)
        # Auf dem Desktop teilt der Lagerzugang die vorhandene Knopfzeile.
        # Schmal steht er darunter, damit Texte und Tabreihenfolge lesbar bleiben.
        if self._inventory_below != narrow:
            self._primary_actions.removeWidget(self.inventory_button)
            self._primary_actions.addWidget(
                self.inventory_button, 1 if narrow else 0, 0 if narrow else 1
            )
            self._inventory_below = narrow
        columns = 3 if wide_enough else NARROW_COLUMNS if narrow else TILE_COLUMNS
        if columns == self._columns:
            return
        self._columns = columns
        self.show_examples()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Beim Breiterwerden das Kachelraster neu teilen."""
        super().resizeEvent(event)
        self._fit_the_columns()

    def _order_the_tab_chain(self) -> None:
        """Die Knöpfe vor die Kacheln, für den, der ohne Maus kommt (§19.2).

        Qt folgt der Reihenfolge, in der die Widgets entstanden sind, und die
        Kacheln entstehen im Konstruktor vor den Knöpfen — gemessen brauchte
        es einen Schritt je Beispiel und dann noch einen bis „Neues Projekt",
        dem vorbelegten Hauptknopf. (Gemessen am 14.08.2026 mit acht
        Beispielen, also neun Schritte; es sind inzwischen neun Beispiele. Die
        Zahl wächst mit dem Katalog — der Befund nicht.) Für die Maus ist die
        Anordnung richtig, für die Tastatur war sie umgekehrt.

        Gesetzt wird die Kette und nicht die Anordnung: Wo etwas steht,
        entscheidet weiterhin das Layout.
        """
        guided = [tile for tile in self.tiles if tile.entry.way]
        deeper = [tile for tile in self.tiles if not tile.entry.way]
        heading = self.more_section.findChild(QToolButton, "sectionHeading")
        assert heading is not None
        # Von oben nach unten, wie das Auge geht: zuletzt Geöffnetes, die vier
        # Einstiege, die Knöpfe, die Ablagefläche, die weiteren Beispiele und
        # zuletzt die Fußzeile.
        chain = [
            self.recent_list,
            *guided,
            self.new_button,
            self.import_button,
            self.open_button,
            self.manual_button,
            self.inventory_button,
            self.drop_area,
            heading,
            *deeper,
            *self.secondary_actions,
        ]
        self._focus_targets = set(chain)
        for target in chain:
            target.installEventFilter(self)
        for first, second in pairwise(chain):
            QWidget.setTabOrder(first, second)

    def refresh_inventory(self) -> None:
        """Die Startkachel folgt Änderungen aus allen Lagerzugängen."""
        self.inventory_button.refresh()

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Ein Tastaturziel bleibt beim Durchlaufen vollständig sichtbar.

        **Die Menge wird über ``getattr`` geholt**, denn dieser Filter läuft
        auch im Abbau: Ist das Python-Objekt schon halb ausgeräumt, gibt es
        ``_focus_targets`` nicht mehr, und ein ``AttributeError`` aus einem
        Ereignisfilter kommt bei niemandem an, den er etwas anginge.
        """
        targets = getattr(self, "_focus_targets", None)
        if stop_watching_the_dying(self, watched, event):
            if targets is not None:
                targets.discard(watched)
            return False
        if event.type() == QEvent.Type.FocusIn and targets is not None and watched in targets:
            self.page_scroll.ensureWidgetVisible(watched, NORMAL, NORMAL)
        return super().eventFilter(watched, event)

    def show_recent(self, paths: list[Path]) -> None:
        """Die zuletzt geöffneten Projekte — oder nichts, wenn es keine gibt.

        Eine leere Liste war erst eine leere Box über 400 Pixel Höhe, dann eine
        Zeile „Noch nichts geöffnet.“ über nichts. Beim ersten Start gibt es
        nichts fortzusetzen, und der Abschnitt steht nicht da (RM-515).
        """
        self.recent_list.clear()
        self.recent_section.setVisible(bool(paths))
        for path in paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.recent_list.addItem(item)
        # **Höchstens vier Zeilen hoch.** Die Liste wuchs bisher mit jedem
        # Eintrag mit, und damit wuchs der Startbildschirm: leer 26 Pixel
        # Rollweg auf 1920x1080, mit sechs Projekten 198 — genau der Wert, den
        # ein früherer Umbau beseitigt hatte. Gedeckelt wird die Höhe und nicht
        # die Zahl der Einträge: Wer zehn Projekte hat, behält sie und rollt in
        # der Liste; was darunter liegt, ist über *Öffnen* genauso erreichbar.
        rows = min(max(len(paths), 1), RECENT_ROWS)
        height = self.recent_list.sizeHintForRow(0) if paths else 22
        self.recent_list.setMaximumHeight(rows * max(height, 18) + NORMAL)

    def show_examples(self) -> None:
        """Die Beispielprojekte, soweit sie installiert sind."""
        for grid in (self.examples_grid, self.more_grid):
            while grid.count():
                item = grid.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.hide()
                    widget.deleteLater()
        self.tiles = []

        placed = {True: 0, False: 0}
        for path in examples.paths():
            entry = examples.by_path(path)
            if entry is None:
                continue
            # Ein Beispiel mit ``way`` ist ein Einstieg, eines ohne eine
            # Funktionsschau — dieselbe Zweiteilung, die ``examples.py``
            # beschreibt, nur jetzt auch sichtbar.
            starts = bool(entry.way)
            grid = self.examples_grid if starts else self.more_grid
            parent = self.examples_area if starts else self.more_area
            # Die vier Einstiege bilden bei jeder Fensterbreite ein ruhiges
            # Raster aus zwei Spalten und zwei Zeilen. Drei plus eine einzelne
            # Kachel sah auf großen Bildschirmen wie ein fehlender Weg aus;
            # die Funktionsbeispiele darunter nutzen die dritte Spalte
            # weiterhin, wenn sie passt.
            columns = min(self._columns, TILE_COLUMNS) if starts else self._columns
            tile = ExampleTile(entry, path, parent)
            tile.chosen.connect(self.openRequested)
            index = placed[starts]
            grid.addWidget(tile, index // columns, index % columns)
            placed[starts] = index + 1
            self.tiles.append(tile)

        # Neue Kacheln stehen am Ende der Tabulatorkette, wo Qt sie anlegt —
        # also wieder vor die Knöpfe. Beim Aufbau gibt es die Knöpfe noch
        # nicht; dann setzt sie der Konstruktor selbst.
        if hasattr(self, "new_button"):
            self._order_the_tab_chain()

    def _on_recent(self, item: QListWidgetItem) -> None:
        """Einen Eintrag öffnen — einmal, auch wenn ein Doppelklick zwei Signale meldet.

        Ein Doppelklick kommt als ``itemClicked`` und ``itemActivated``; unter
        Stilen, die schon beim Einfachklick aktivieren, kommen beide mit einem
        Klick. Derselbe Eintrag innerhalb der Doppelklickzeit öffnet nicht noch
        einmal — ein zweites Laden desselben Projekts wäre kein Gewinn.
        """
        stored = item.data(Qt.ItemDataRole.UserRole)
        if not stored:
            return
        now = time.monotonic()
        last, when = self._recent_opened
        if last == str(stored) and now - when < QApplication.doubleClickInterval() / 1000.0:
            return
        self._recent_opened = (str(stored), now)
        self.openRequested.emit(Path(stored))

    def _on_recent_menu(self, position: QPoint) -> None:
        """Einen Eintrag vergessen — die Datei selbst bleibt, wo sie ist."""
        item = self.recent_list.itemAt(position)
        stored = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not stored:
            return
        menu = QMenu(self)
        action = menu.addAction(tr("Aus der Liste entfernen"))
        action.triggered.connect(
            lambda _checked=False, path=str(stored): self.forgetRequested.emit(Path(path))
        )
        menu.exec(self.recent_list.viewport().mapToGlobal(position))
        # Kein Menü bleibt als Kind der Startfläche liegen (RM-233, wie im
        # Objektbaum): ``deleteLater`` lässt dem Signal des Eintrags seine Runde.
        menu.deleteLater()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt name
        if dropped_file(event) is not None or accepted_url(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt name
        paths = accepted_paths(event)
        if paths:
            if len(paths) > 1:
                self.filesDropped.emit(paths)
            else:
                self.fileDropped.emit(paths[0])
            event.acceptProposedAction()
            return
        url = accepted_url(event)
        if url is not None:
            self.urlDropped.emit(url)
            event.acceptProposedAction()
            return
        # Eine Datei, die Solidon nicht liest, bekommt trotzdem eine Antwort:
        # das Fenster sagt, wie das Modell hereinkommt (RM-358 W1-6).
        other = dropped_file(event)
        if other is not None:
            self.fileDropped.emit(other)
            event.acceptProposedAction()


def _caption(text: str, parent: QWidget) -> QLabel:
    """Eine Abschnittsüberschrift über einer Gruppe."""
    label = QLabel(text, parent)
    # Die längste Überschrift ist selbst eine Erklärung. Ohne Umbruch machte
    # ihre Wunschbreite auf 640 Punkten den ganzen Rollbereich 146 Punkte
    # breiter als das Fenster — obwohl jede Kachel darunter längst sauber in
    # einer Spalte stand.
    label.setWordWrap(True)
    set_level(label, "section")
    return label
