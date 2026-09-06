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

from PySide6.QtCore import QByteArray, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QDesktopServices,
    QImage,
    QKeySequence,
    QPainter,
    QResizeEvent,
    QShortcut,
    QTextDocument,
)
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

from app.branding import APP_NAME, WEBSITE_URL
from app.core import drawing, figures, manual
from app.core.log import get_logger
from app.i18n import get_language, tr

_log = get_logger(__name__)

#: Was der Textspalte neben der Abbildung bleibt — Innenabstand und Rollbalken.
#: Ohne diesen Abzug läge eine Zeichnung genau auf der Kante und der
#: Rollbalken schnitte ihren rechten Rand ab.
COLUMN_MARGIN = 40


class PageView(QTextBrowser):
    """Die Textspalte — und die Stelle, an der Abbildungen entstehen.

    ``loadResource`` ist der Haken, den Qt dafür vorsieht: der Text nennt
    ``figure:schlüssel``, und wenn die Zeile wirklich angezeigt wird, wird
    gefragt, was dahintersteckt. Vorher passiert nichts, und das ist der Punkt
    — sonst rechnete das Öffnen des Handbuchs jedes Netz aus jedem Kapitel.
    """

    #: Wie lange nach der letzten Größenänderung gewartet wird, bevor die
    #: Abbildungen neu auf die Spalte gebracht werden. Ein Zug am Fensterrand
    #: schickt hunderte Ereignisse, und jedes Nachlegen kostet ein Skalieren.
    REFIT_DELAY_MS = 150

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Gemerkt wird nur, was teuer ist — siehe :meth:`_source`.
        self._drawings: dict[tuple[str, drawing.Theme], QImage] = {}
        #: Die Schlüssel, nach denen die offene Seite gefragt hat. Nur die
        #: werden nachgelegt; für die anderen wäre es Arbeit ohne Leser.
        self._asked: set[str] = set()
        self._column_width = 0
        self._refit_timer = QTimer(self)
        self._refit_timer.setSingleShot(True)
        self._refit_timer.setInterval(self.REFIT_DELAY_MS)
        self._refit_timer.timeout.connect(self._refit)

    def setMarkdown(self, markdown: str) -> None:  # noqa: N802 — Qt gibt den Namen vor
        """Eine neue Seite fragt nach ihren eigenen Abbildungen.

        Gerendert wird **ohne HTML-Auswertung**. Qts Vorgabe ist der
        GitHub-Dialekt, und der lässt rohes HTML durch: ein ``<a href=…>`` im
        Text wurde zu einem echten Anker. Das Handbuch entsteht aus dem
        Register, und ein mitgereistes Rezept bringt Titel und Beschreibung
        aus einer fremden Projektdatei mit (Sicherheitsdurchsicht 04.09.2026).
        Mit ``MarkdownNoHTML`` steht dasselbe HTML als Text da — sichtbar,
        aber wirkungslos.

        Es ist die **zweite** Schicht, nicht die erste: Markdown-Linksyntax
        bleibt Markdown, ``[Text](beliebiges:ziel)`` wird also weiter ein
        Anker. Wohin ein Klick darf, entscheidet
        :meth:`ManualWindow._open_link`.
        """
        self._asked.clear()
        self.document().setMarkdown(
            markdown,
            QTextDocument.MarkdownFeature.MarkdownDialectGitHub
            | QTextDocument.MarkdownFeature.MarkdownNoHTML,
        )

    def loadResource(  # noqa: N802 — Qt gibt den Namen vor
        self, kind: int, name: QUrl | str
    ) -> object:
        """Löst ``figure:``-Verweise auf — und sonst nichts.

        Alles andere ging an Qt, und Qt lädt: Eine Rezeptbeschreibung mit
        ``![Bild](file:///…)`` kam über ``recipe.register`` ungefiltert in die
        Handbuchreferenz, und schon das **Öffnen** der Seite las die Datei —
        ohne Klick, an der Hostprüfung von ``_open_link`` vorbei; unter
        Windows wäre eine UNC-Anforderung dieselbe Zeile (Gesamtreview
        05.09.2026, UI-22). Das Handbuch kennt genau eine Bildquelle, seinen
        Abbildungskatalog, und die ist lokal.
        """
        url = QUrl(name) if isinstance(name, str) else name
        if url.scheme() != "figure":
            _log.info("manual page asked for %s — only figure: is served", url.toString())
            # None ist ein ungültiger QVariant und erlaubt QTextDocument,
            # selbst von der Adresse nachzuladen. Leere Daten sind dagegen
            # eine beantwortete Anfrage: keine zweite Quelle hinter Qt.
            return QByteArray()
        return self._image(url.path() or url.toString().removeprefix("figure:"))

    def _image(self, key: str) -> QImage | None:
        """Eine Abbildung, auf die Breite der Textspalte gebracht."""
        source = self._source(key, self._theme())
        if source is None:
            return None
        self._asked.add(key)
        self._column_width = self._column()
        return _fitted(source, self._column_width)

    def _source(self, key: str, theme: drawing.Theme) -> QImage | None:
        """Die Abbildung in ihrer natürlichen Größe.

        Gemerkt wird nur, was teuer ist: das Rastern eines SVG. Ein
        Bildschirmfoto kommt bei jedem Bedarf frisch von der Platte — die
        sechs im Katalog wiegen entpackt zusammen 51 MB, drei davon je 14,
        und wer sie behält, um sie später anders skalieren zu können, tauscht
        ein Bildproblem gegen ein Speicherproblem. Von der Platte lesen
        kostet Millisekunden und passiert je Seitenwechsel einmal, weil Qt
        das Ergebnis selbst im Dokument behält.

        Was hier zurückkommt, hängt **nicht** von der Spaltenbreite ab. Das
        ist der Punkt: Die Breite kam früher im Cache-Schlüssel nicht vor,
        steckte aber im gespeicherten Bild — womit ein einmal verkleinertes
        Bild verkleinert blieb.
        """
        figure = figures.find(key)
        if figure is None:
            return None
        if figure.kind == "shot":
            shot = QImage(str(figure.path(get_language())))
            return None if shot.isNull() else shot
        cached = self._drawings.get((key, theme))
        if cached is not None:
            return cached
        image = _rendered(figures.svg(key, theme))
        if image is None or image.isNull():
            return None
        self._drawings[(key, theme)] = image
        return image

    def _column(self) -> int:
        """Die Breite, auf die eine Abbildung passen muss."""
        return self.viewport().width() - COLUMN_MARGIN

    def _theme(self) -> drawing.Theme:
        return "dark" if self._dark() else "light"

    #: Wie viele Zeichen eine Zeile höchstens trägt.
    #:
    #: Typografie nennt sechzig bis achtzig; gemessen liefen es 96, weil der
    #: Text die ganze Fensterbreite nahm (Befund B34). Wer eine so lange Zeile
    #: zu Ende liest, findet den Anfang der nächsten nicht mehr wieder — das
    #: ist der Grund für die Regel und keine Geschmacksfrage. Achtzig, weil ein
    #: Handbuch Code-Zeilen und Tabellen trägt, denen die enge Fassung wehtut.
    MAX_CHARACTERS = 80

    def _fit_the_column(self) -> None:
        """Der Textspalte einen Rand geben, wo das Fenster ihr zu viel lässt.

        Über ``setViewportMargins`` und nicht über die Dokumentbreite: Der
        Rand gehört zur Ansicht, und ein Dokument, dessen Breite von der
        Fenstergröße abweicht, rollt waagerecht. Symmetrisch, damit die Spalte
        in der Mitte bleibt statt links zu kleben.
        """
        fits = self.MAX_CHARACTERS * max(self.fontMetrics().horizontalAdvance("n"), 1)
        margin = max(0, (self.width() - fits) // 2)
        self.setViewportMargins(margin, 0, margin, 0)
        # **Und die Dokumentbreite mit.** Qt zieht sie nicht selbst nach:
        # Gemessen blieb sie bei 1294, während der Sichtbereich auf 942 ging —
        # der Text hätte waagerecht gerollt, was schlimmer ist als eine lange
        # Zeile.
        self.document().setTextWidth(float(self.viewport().width()))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 — Qt gibt den Namen vor
        """Eine breitere Spalte verlangt größere Abbildungen (§19.2)."""
        super().resizeEvent(event)
        self._fit_the_column()
        if self._asked and self._column() != self._column_width:
            self._refit_timer.start()

    def _refit(self) -> None:
        """Die Abbildungen der offenen Seite auf die neue Spalte bringen.

        Nachgelegt wird über ``addResource`` und nicht über ein neues
        ``setMarkdown``: Das setzte die Leseposition auf den Seitenanfang
        zurück, mitten im Lesen.

        Dass es dieses Nachlegen überhaupt braucht, ist gemessen: Qt behält,
        was ``loadResource`` geliefert hat, im Dokument und fragt nie wieder
        — nach zwei Größenänderungen kamen null weitere Rufe an. Eine
        Abbildung, die für eine schmale Spalte verkleinert wurde, blieb also
        klein. Bei 400 Punkten Spaltenbreite stand der Startbildschirm auf
        374 und blieb dort, auch als das Fenster auf 1600 aufging.
        """
        width = self._column()
        if width == self._column_width:
            return
        self._column_width = width
        theme = self._theme()
        document = self.document()
        for key in sorted(self._asked):
            source = self._source(key, theme)
            if source is None:
                continue
            document.addResource(
                QTextDocument.ResourceType.ImageResource,
                QUrl(f"figure:{key}"),
                _fitted(source, width),
            )
        # Ohne das bleibt der Umbruch auf den alten Maßen stehen — das
        # Dokument hätte die neuen Bilder und zeichnete die alten Kästen.
        document.markContentsDirty(0, document.characterCount())

    def _dark(self) -> bool:
        """Ob gerade das dunkle Thema läuft — die Abbildung richtet sich danach."""
        return self.palette().window().color().lightness() < 128


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
        # **Kein Klick öffnet von selbst etwas.** Das Handbuch entsteht aus dem
        # Register, und ein mitgereistes Rezept bringt Titel und Beschreibung
        # aus einer fremden Projektdatei mit. ``setOpenLinks(False)`` schließt
        # dabei auch den Weg über ``setSource``: Ein ``file://`` auf einen
        # UNC-Pfad startet kein Programm, erzwingt aber eine SMB-Anmeldung.
        # Dasselbe Muster wie in ``ai_disclosure`` und ``changes_dialog``.
        self.text.setOpenLinks(False)
        self.text.setOpenExternalLinks(False)
        self.text.anchorClicked.connect(self._open_link)

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

    def _open_link(self, address: QUrl) -> None:
        """Öffnet nur Adressen auf der eigenen Website.

        Das Handbuch trägt heute keinen einzigen externen Link — gemessen über
        ``app/`` am 04.09.2026, null Markdown-Links. Die Erlaubnis für die
        eigene Domain steht trotzdem, damit ein künftiges Kapitel einen setzen
        kann, ohne dass hier jemand nachziehen muss.

        Alles andere bleibt liegen, und der Grund ist nicht Vorsicht, sondern
        ein Weg, den es gab: ``QDesktopServices.openUrl`` reicht unter Windows
        jedes Protokoll an seinen eingetragenen Handler weiter — ``search-ms:``
        stellt eine fremde Netzfreigabe als Suchergebnis dar, und was sonst
        auf dem Rechner ein Protokoll angemeldet hat, weiß Solidon nicht.
        Verglichen wird der **Host**, nicht ein Präfix: ``solidon3d.de.fremd``
        beginnt sonst mit der eigenen Adresse und ist es nicht.
        """
        if address.scheme() == "https" and address.host() == QUrl(WEBSITE_URL).host():
            QDesktopServices.openUrl(address)

    # --- Inhalt ---------------------------------------------------------------

    def _fill(self, pages: list[manual.Page] | tuple[manual.Page, ...]) -> None:
        """Die Seitenliste neu setzen und die erste zeigen."""
        self._visible = list(pages)
        self.contents.clear()
        for page in self._visible:
            item = QListWidgetItem(str(page.title))
            # Die erzeugten Kapitel bilden die zweite Hälfte des Handbuchs; der
            # Hinweis sagt, dass dort die vollständige Liste steht.
            # **Der volle Name im Hinweis, die Art dahinter.** „Ausprobieren
            # statt raten: Varianten und Kalibriere" stand im Verzeichnis —
            # mitten im Wort zu Ende und ohne Auslassungszeichen, also wie ein
            # kurzer Titel (Befund B34). Die Kürzung selbst ist richtig; was
            # fehlte, war der Weg zum ganzen Namen.
            art = (
                tr("Alle Operationen dieses Bereichs")
                if page.generated
                else tr("Erklärung, kein Nachschlagewerk")
            )
            item.setToolTip(str(page.title))
            item.setStatusTip(f"{page.title} — {art}")
            self.contents.addItem(item)
        if self._visible:
            self.contents.setCurrentRow(0)
        else:
            self.text.setMarkdown(tr("Dazu steht nichts im Handbuch."))

    def _show_current(self, row: int) -> None:
        if 0 <= row < len(self._visible):
            page = self._visible[row]
            # ``manual.titled`` und nicht ``if not page.generated``: Die vier
            # Wissensseiten sind erzeugt und bringen doch keine Überschrift mit
            # — über ihnen stand hier keine, und der Text fing mitten im Satz
            # an. Dieselbe Regel gilt für das erzeugte Handbuch; sie steht
            # deshalb im Kern und nicht zweimal.
            self.text.setMarkdown(manual.titled(page, self._with_figures(page)))
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
