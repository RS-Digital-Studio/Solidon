"""Das Handbuchfenster (Bauplan §2.7, §19.2).

Links die Seiten, rechts der Text, oben ein Feld zum Suchen. Mehr braucht es
nicht, und weniger wäre zu wenig: eine Anwendung mit zweiundsechzig
Operationen, deren einzige Erklärung ein Satz im Menü ist, verlangt vom Nutzer,
dass er ausprobiert, was er hätte lesen können.

Drei Entscheidungen stecken darin:

* **Der Text kommt aus dem Kern** (:mod:`app.core.manual`), nicht von hier.
  Die Referenzseiten sind aus dem Register erzeugt und können deshalb nicht
  veralten; die Kommandozeile gibt denselben Text aus.
* **Gesucht wird über alles**, nicht nur über die Überschriften. Wer wissen
  will, wo „Elefantenfuß" vorkommt, weiß nicht, in welchem Kapitel er steht —
  das ist ja der Grund, warum er sucht.
* **Es ist ein Fenster, kein Dialog.** Ein Handbuch, das man zum Arbeiten
  schließen muss, wird beim zweiten Mal nicht mehr geöffnet.

Die Abbildungen kommen über :meth:`QTextBrowser.loadResource`: im Markdown
steht ``![](figure:schlüssel)``, und aufgelöst wird der Verweis erst, wenn die
Seite wirklich angezeigt wird. Das hält das Öffnen schnell — ein gerendertes
Netz kostet spürbar Zeit, und niemand liest fünfundzwanzig Kapitel auf einmal.
Was sich nicht erzeugen lässt, wird durch den Alt-Text ersetzt statt durch ein
kaputtes Bildsymbol.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, QUrl
from PySide6.QtGui import QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME
from app.core import drawing, figures, manual
from app.i18n import get_language, tr


class PageView(QTextBrowser):
    """Die Textspalte — und die Stelle, an der Abbildungen entstehen.

    ``loadResource`` ist der Haken, den Qt dafür vorsieht: der Text nennt
    ``figure:schlüssel``, und wenn die Zeile wirklich angezeigt wird, wird
    gefragt, was dahintersteckt. Vorher passiert nichts, und das ist der Punkt
    — sonst rechnete das Öffnen des Handbuchs jedes Netz aus jedem Kapitel.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._images: dict[tuple[str, drawing.Theme], QImage] = {}

    def loadResource(  # noqa: N802 — Qt gibt den Namen vor
        self, kind: int, name: QUrl | str
    ) -> object:
        """Löst ``figure:``-Verweise auf; alles andere macht Qt wie bisher."""
        url = QUrl(name) if isinstance(name, str) else name
        if url.scheme() != "figure":
            return super().loadResource(kind, name)
        return self._image(url.path() or url.toString().removeprefix("figure:"))

    def _image(self, key: str) -> QImage | None:
        """Eine Abbildung als Bild, gemerkt für das nächste Mal."""
        theme: drawing.Theme = "dark" if self._dark() else "light"
        cached = self._images.get((key, theme))
        if cached is not None:
            return cached
        figure = figures.find(key)
        if figure is None:
            return None
        if figure.kind == "shot":
            image: QImage | None = QImage(str(figure.path(get_language())))
        else:
            image = _rendered(figures.svg(key, theme))
        if image is None or image.isNull():
            return None
        image = _fitted(image, self.viewport().width() - 40)
        self._images[(key, theme)] = image
        return image

    def _dark(self) -> bool:
        """Ob gerade das dunkle Thema läuft — die Abbildung richtet sich danach."""
        return self.palette().window().color().lightness() < 128

    def forget_images(self) -> None:
        """Gemerkte Bilder wegwerfen — nach einem Sprach- oder Themenwechsel."""
        self._images.clear()


class ManualWindow(QMainWindow):
    """Das Handbuch: Seiten links, Text rechts, Suche darüber."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{tr('Handbuch')} — {APP_NAME}")
        self.resize(980, 720)
        self._pages = manual.pages()

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Suchen — auch im Text der Seiten"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)

        self.contents = QListWidget(self)
        self.contents.currentRowChanged.connect(self._show_current)

        self.text = PageView(self)
        self.text.setOpenExternalLinks(True)

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.contents)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(left)
        splitter.addWidget(self.text)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 700])
        self.setCentralWidget(splitter)

        QShortcut(QKeySequence.StandardKey.Find, self, self.search.setFocus)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)

        self._visible: list[manual.Page] = []
        self._fill(self._pages)

    # --- Inhalt ---------------------------------------------------------------

    def _fill(self, pages: list[manual.Page] | tuple[manual.Page, ...]) -> None:
        """Die Seitenliste neu setzen und die erste zeigen."""
        self._visible = list(pages)
        self.contents.clear()
        for page in self._visible:
            item = QListWidgetItem(str(page.title))
            # Die erzeugten Kapitel bilden die zweite Hälfte des Handbuchs; der
            # Hinweis sagt, dass dort die vollständige Liste steht.
            item.setToolTip(
                tr("Alle Operationen dieses Bereichs")
                if page.generated
                else tr("Erklärung, kein Nachschlagewerk")
            )
            self.contents.addItem(item)
        if self._visible:
            self.contents.setCurrentRow(0)
        else:
            self.text.setMarkdown(tr("Dazu steht nichts im Handbuch."))

    def _show_current(self, row: int) -> None:
        if 0 <= row < len(self._visible):
            page = self._visible[row]
            body = self._with_figures(page)
            if not page.generated:
                body = f"## {page.title}\n\n{body}"
            self.text.setMarkdown(body)
            self.text.moveCursor(self.text.textCursor().MoveOperation.Start)

    # --- Abbildungen ------------------------------------------------------------------

    def _with_figures(self, page: manual.Page) -> str:
        """Bildverweise auf das vorbereiten, was ``loadResource`` liefern kann.

        Eine Abbildung, die hier und jetzt nicht entstehen kann — weil die
        Geometriepakete fehlen oder ein Bildschirmfoto noch nicht aufgenommen
        wurde —, wird durch ihren Alt-Text ersetzt. Ein Handbuch mit einem
        kaputten Bildsymbol sieht aus wie ein Fehler; ein Handbuch mit einem
        Satz an derselben Stelle liest sich weiter.
        """
        language = get_language()

        def replace(match: object) -> str:
            key = match.group(1)  # type: ignore[attr-defined]
            figure = figures.find(key)
            if figure is None:
                return ""
            if not figure.available(language):
                return f"*{figure.alt}*"
            caption = f"\n\n*{figure.caption}*" if figure.caption else ""
            return f"![{figure.alt}](figure:{key}){caption}"

        # ``page.text()`` und nicht ``page.body``: Die Kurzfassung steht der
        # Seite voran, im Fenster wie im erzeugten Handbuch.
        return manual.FIGURE_PATTERN.sub(replace, page.text())

    def _filter(self, needle: str) -> None:
        """Über Titel *und* Text suchen — wer sucht, weiß das Kapitel nicht."""
        wanted = needle.strip().casefold()
        if not wanted:
            self._fill(self._pages)
            return
        self._fill(
            [
                page
                for page in self._pages
                if wanted in str(page.title).casefold() or wanted in page.text().casefold()
            ]
        )

    def show_page(self, key: str) -> None:
        """Eine bestimmte Seite zeigen — der Weg von einer Operation ins Kapitel."""
        self.search.clear()
        for row, page in enumerate(self._visible):
            if page.key == key:
                self.contents.setCurrentRow(row)
                return


#: Um wie viel feiner gerastert wird, als die Abbildung am Ende groß ist. Ohne
#: das steht auf einem HiDPI-Bildschirm genau dort Matsch, wo eine Zeichnung
#: ihre Zahlen zeigt.
OVERSAMPLING = 2


def _rendered(svg: str | None) -> QImage | None:
    """Ein SVG zu einem Bild machen, feiner gerastert als angezeigt."""
    if not svg:
        return None
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return None
    image = QImage(renderer.defaultSize() * OVERSAMPLING, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    # Ohne das zeichnet Qt jedes gerasterte Pixel einzeln, und die Abbildung
    # erscheint doppelt so breit, wie sie gemeint war.
    image.setDevicePixelRatio(float(OVERSAMPLING))
    return image


def _fitted(image: QImage, width: int) -> QImage:
    """Ein Bild auf die Spaltenbreite bringen, ohne es zu vergrößern.

    Eine Zeichnung, die breiter ist als das Fenster, würde rechts abgeschnitten
    — und ausgerechnet dort steht in mehreren Abbildungen die Erklärung.
    """
    limit = max(width, 240)
    ratio = image.devicePixelRatio() or 1.0
    if image.width() / ratio <= limit:
        return image
    scaled = image.scaledToWidth(round(limit * ratio), Qt.TransformationMode.SmoothTransformation)
    scaled.setDevicePixelRatio(ratio)
    return scaled
