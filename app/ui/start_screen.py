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

from itertools import pairwise
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
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
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, PROJECT_SUFFIX
from app.core import examples
from app.core.brep.step import SUFFIXES as STEP_SUFFIXES
from app.core.examples import Example
from app.core.geom.mesh import READABLE_SUFFIXES
from app.core.ingest.fetch import ALLOWED_SUFFIXES, suffix_of
from app.core.ingest.outline import OUTLINE_SUFFIXES
from app.i18n import tr
from app.ui.icons import icon
from app.ui.style import NORMAL, ROOMY, TIGHT, WIDE, make_primary, set_level
from app.ui.theme import THEMES

#: Wie breit die Spalte höchstens wird. Darüber hinaus wächst nur der Rand:
#: eine Zeile über 1900 Pixel liest niemand, und ein Knopf, der am linken Rand
#: klebt, während sein Verweis am rechten steht, gehört sichtbar nicht mehr
#: zusammen.
COLUMN_WIDTH = 900

#: Kacheln je Zeile. Zwei bei 900 Pixel heißt gut 430 pro Kachel: das
#: Vorschaubild links, daneben Titel und Satz.
TILE_COLUMNS = 2


class DropArea(QFrame):
    """Die große Ablagefläche. Nimmt Projekte und Modelle gleichermaßen.

    Vorher stand hier ein Satz in der Bildmitte, ohne Rahmen, ohne Feld, ohne
    Symbol — man sah nicht, dass das eine Ablagefläche ist. Der gestrichelte
    Rahmen kommt aus dem Thema und nicht aus ``palette(mid)``: das war im
    dunklen Thema unsichtbar, also genau dort, wo die Anwendung startet.
    """

    fileDropped = Signal(Path)
    urlDropped = Signal(str)
    """Ein Verweis aus dem Browser, gezogen statt heruntergeladen (§16.3)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self._hover = False

        self.symbol = QLabel(self)
        self.symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size = self.fontMetrics().height() * 2
        self.symbol.setPixmap(icon("import", self).pixmap(size, size))

        hint = QLabel(tr("Modell oder Projekt hier ablegen"), self)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_level(hint, "section")

        kinds = QLabel(f"STL · 3MF · OBJ · GLB · {PROJECT_SUFFIX}", self)
        kinds.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_level(kinds, "caption")

        # Das Feld nimmt auch einen Verweis (:attr:`urlDropped`), und das ist
        # der kürzeste Weg von einer Modellseite hierher: kein Herunterladen,
        # kein Suchen im Download-Ordner. Es stand nirgends — ein Weg, den
        # niemand kennt, ist keiner.
        link = QLabel(tr("Auch ein Verweis aus dem Browser"), self)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_level(link, "caption")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        layout.setSpacing(TIGHT)
        layout.addStretch(1)
        layout.addWidget(self.symbol)
        layout.addWidget(hint)
        layout.addWidget(kinds)
        layout.addWidget(link)
        layout.addStretch(1)
        self._painted: tuple[str, bool] | None = None
        self._paint("dark")

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
            f" background: {fill}; }}"
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
        if accepted_path(event) is not None or accepted_url(event) is not None:
            self._set_hover(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802 - Qt name
        self._set_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt name
        self._set_hover(False)
        path = accepted_path(event)
        if path is not None:
            self.fileDropped.emit(path)
            event.acceptProposedAction()
            return
        url = accepted_url(event)
        if url is not None:
            self.urlDropped.emit(url)
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
#: erkennen, klein genug, dass Titel und Satz ihre Zeilen behalten.
PREVIEW_HEIGHT = 88


def _preview_pixmap(entry: Example) -> QPixmap | None:
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
    image = QImage(
        QSize(PREVIEW_HEIGHT, PREVIEW_HEIGHT) * 2, QImage.Format.Format_ARGB32_Premultiplied
    )
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(2.0)
    return QPixmap.fromImage(image)


class ExampleTile(QFrame):
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Eine Kachel ist ein Knopf aus zwei Labels, und ein Bildschirmleser
        # las davon nichts vor: Der Titel gehört einem Kind, nicht ihr. Neun
        # solcher Kacheln sind das Erste, was jemand hier sieht — und ohne
        # Namen neun Mal „Rahmen".
        self.setAccessibleName(str(entry.title))
        self.setAccessibleDescription(str(entry.doc))
        # Waagerecht dehnbar, senkrecht mitwachsend: sonst steht neben einer
        # Kachel mit drei Zeilen eine mit zwei, und die Zeile sieht schief aus.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

        title = QLabel(str(entry.title), self)
        title.setWordWrap(True)
        set_level(title, "section")

        doc = QLabel(str(entry.doc), self)
        doc.setWordWrap(True)
        set_level(doc, "caption")

        # Das Bild kommt aus dem Beispiel selbst, gerendert von
        # `tools/make_examples.py` beim Bauen. Fehlt es, steht die Kachel wie
        # vorher da: ein frisch ausgecheckter Baum hat die Bilder erst, wenn
        # das Werkzeug gelaufen ist, und eine leere Fläche wäre schlimmer als
        # keine.
        self.preview = QLabel(self)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        picture = _preview_pixmap(entry)
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
        layout.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        layout.setSpacing(ROOMY)
        layout.addWidget(self.preview)
        layout.addWidget(words, stretch=1)

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        if event.button() == Qt.MouseButton.LeftButton:
            self.chosen.emit(self.path)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        """Was mit der Maus geht, geht mit der Tastatur (§19.2)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.chosen.emit(self.path)
            return
        super().keyPressEvent(event)


def accepted_url(event: QDragEnterEvent | QDropEvent) -> str | None:
    """Die erste fallengelassene **Web**-Adresse, die auf ein Modell zeigt.

    Wer aus dem Browser einen Herunterladen-Verweis auf das Fenster zieht,
    meint dieselbe Handlung wie mit einer Datei — und bekam bisher nichts, weil
    :func:`accepted_path` alles verwirft, was keine lokale Datei ist. Geprüft
    wird nur die Endung; ob dahinter wirklich ein Modell liegt, weiß erst der
    Server (:mod:`app.core.ingest.fetch`).
    """
    data = event.mimeData()
    if not data.hasUrls():
        return None
    for url in data.urls():
        if url.isLocalFile() or url.scheme().lower() not in ("http", "https"):
            continue
        if suffix_of(url.path()) in ALLOWED_SUFFIXES:
            return str(url.toString())
    return None


def accepted_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
    """Die erste fallengelassene Datei, mit der diese Anwendung etwas
    anfangen kann.
    """
    data = event.mimeData()
    if not data.hasUrls():
        return None
    for url in data.urls():
        if not url.isLocalFile():
            continue
        path = Path(url.toLocalFile())
        # STEP liest der andere Kern und steht darum nicht unter den
        # Mesh-Endungen — eines fallenzulassen muss trotzdem gehen (§30).
        if path.suffix.lower() in (
            *READABLE_SUFFIXES,
            *STEP_SUFFIXES,
            *OUTLINE_SUFFIXES,
            PROJECT_SUFFIX,
        ):
            return path
    return None


class StartScreen(QWidget):
    """Was gezeigt wird, bevor ein Projekt offen ist."""

    openRequested = Signal(Path)
    newRequested = Signal()
    browseRequested = Signal()
    fileDropped = Signal(Path)
    urlDropped = Signal(str)
    """Eine Adresse aus dem Browser ist hier gelandet — dieselbe Handlung wie
    eine Datei, nur liegt sie noch nicht auf der Platte (§16.3)."""
    forgetRequested = Signal(Path)
    """Ein Eintrag soll aus der Liste verschwinden — die Datei bleibt."""
    manualRequested = Signal()
    """Das Handbuch soll aufgehen — hier, wo es gebraucht wird, nicht erst
    im Hilfemenü eines Fensters, das ein neuer Nutzer noch nie gesehen hat."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        title = QLabel(APP_NAME, self)
        set_level(title, "title")

        self.recent_list = QListWidget(self)
        self.recent_list.itemActivated.connect(self._on_recent)
        # Zehn Einträge, und was einmal darin stand, blieb bis es hinausrutschte:
        # ein Versuchsprojekt hielt sich länger als das Interesse daran.
        self.recent_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recent_list.customContextMenuRequested.connect(self._on_recent_menu)

        self.recent_empty = QLabel(tr("Noch nichts geöffnet."), self)
        set_level(self.recent_empty, "caption")

        # §37.2: die Beispielprojekte sind Inhalt des Startbildschirms und kein
        # Ordner, den jemand suchen muss.
        self.examples_area = QWidget(self)
        self.examples_grid = QGridLayout(self.examples_area)
        self.examples_grid.setContentsMargins(0, 0, 0, 0)
        self.examples_grid.setSpacing(NORMAL)
        self.tiles: list[ExampleTile] = []
        self.show_examples()

        # Der Hauptknopf sieht aus wie einer. Vorher standen beide in
        # gewöhnlicher Größe nebeneinander und sagten nicht, welcher gemeint
        # ist, wenn man nichts Bestimmtes vorhat.
        self.new_button = QPushButton(tr("Neues Projekt"), self)
        make_primary(self.new_button)
        self.new_button.clicked.connect(self.newRequested)
        self.open_button = QPushButton(tr("Projekt öffnen …"), self)
        self.open_button.clicked.connect(self.browseRequested)

        drop = DropArea(self)
        drop.fileDropped.connect(self.fileDropped)
        drop.urlDropped.connect(self.urlDropped)

        # Die ersten fünfzehn Minuten stehen im Handbuch — aber der Weg
        # dorthin führte über das Hilfemenü des Hauptfensters, das beim ersten
        # Start noch niemand gesehen hat. Der Verweis gehört hierher, und zwar
        # neben die Knöpfe: am anderen Fensterrand gehörte er sichtbar zu
        # nichts.
        self.manual_button = QPushButton(tr("Handbuch — die ersten fünfzehn Minuten"), self)
        self.manual_button.setFlat(True)
        self.manual_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_button.clicked.connect(self.manualRequested)

        buttons = QHBoxLayout()
        buttons.setSpacing(NORMAL)
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.manual_button)
        buttons.addStretch(1)

        column = QWidget(self)
        column.setMaximumWidth(COLUMN_WIDTH)
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(WIDE)
        inner.addWidget(title)
        inner.addWidget(drop)
        inner.addLayout(buttons)
        inner.addWidget(_caption(tr("Beispiele — die vier Wege und was darauf bereitliegt"), self))
        inner.addWidget(self.examples_area)
        inner.addWidget(_caption(tr("Zuletzt geöffnet"), self))
        inner.addWidget(self.recent_empty)
        inner.addWidget(self.recent_list)
        inner.addStretch(1)

        centred = QWidget(self)
        middle = QHBoxLayout(centred)
        middle.setContentsMargins(WIDE * 3, WIDE * 3, WIDE * 3, WIDE * 3)
        middle.addStretch(1)
        middle.addWidget(column)
        middle.addStretch(1)

        # In einem Rollbereich, weil die Spalte bei einem kleinen Fenster sonst
        # unten abgeschnitten wird — und was man nicht sieht, gibt es nicht.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(centred)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._order_the_tab_chain()
        self.show_recent([])

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
        chain = [self.new_button, self.open_button, self.manual_button, *self.tiles]
        for first, second in pairwise(chain):
            QWidget.setTabOrder(first, second)

    def show_recent(self, paths: list[Path]) -> None:
        """Die zuletzt geöffneten Projekte — oder eine Zeile, wenn es keine gibt.

        Eine leere Liste war eine leere Box über 400 Pixel Höhe mit einem Satz
        darin. Ein leerer Zustand darf klein sein; er muss nur seinen Platz
        wieder hergeben, wenn er gefüllt wird.
        """
        self.recent_list.clear()
        self.recent_empty.setVisible(not paths)
        self.recent_list.setVisible(bool(paths))
        for path in paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.recent_list.addItem(item)

        rows = max(len(paths), 1)
        height = self.recent_list.sizeHintForRow(0) if paths else 22
        self.recent_list.setMaximumHeight(rows * max(height, 18) + NORMAL)

    def show_examples(self) -> None:
        """Die Beispielprojekte, soweit sie installiert sind."""
        while self.examples_grid.count():
            item = self.examples_grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.tiles = []

        for index, path in enumerate(examples.paths()):
            entry = examples.by_path(path)
            if entry is None:
                continue
            tile = ExampleTile(entry, path, self.examples_area)
            tile.chosen.connect(self.openRequested)
            self.examples_grid.addWidget(tile, index // TILE_COLUMNS, index % TILE_COLUMNS)
            self.tiles.append(tile)

        # Neue Kacheln stehen am Ende der Tabulatorkette, wo Qt sie anlegt —
        # also wieder vor die Knöpfe. Beim Aufbau gibt es die Knöpfe noch
        # nicht; dann setzt sie der Konstruktor selbst.
        if hasattr(self, "new_button"):
            self._order_the_tab_chain()

    def _on_recent(self, item: QListWidgetItem) -> None:
        stored = item.data(Qt.ItemDataRole.UserRole)
        if stored:
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

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt name
        if accepted_path(event) is not None or accepted_url(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt name
        path = accepted_path(event)
        if path is not None:
            self.fileDropped.emit(path)
            event.acceptProposedAction()
            return
        url = accepted_url(event)
        if url is not None:
            self.urlDropped.emit(url)
            event.acceptProposedAction()


def _caption(text: str, parent: QWidget) -> QLabel:
    """Eine Abschnittsüberschrift über einer Gruppe."""
    label = QLabel(text, parent)
    set_level(label, "section")
    return label
