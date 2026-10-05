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

import re

from PySide6.QtCore import (
    QByteArray,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QFont,
    QImage,
    QKeySequence,
    QPainter,
    QResizeEvent,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, WEBSITE_URL
from app.core import drawing, figures, manual, manual_search, markup
from app.core.log import get_logger
from app.i18n import get_language, tr
from app.ui.dialogs import open_link
from app.ui.icons import OVERSAMPLING
from app.ui.style import SPACE

_log = get_logger(__name__)

#: Was der Textspalte neben der Abbildung bleibt — Innenabstand und Rollbalken.
#: Ohne diesen Abzug läge eine Zeichnung genau auf der Kante und der
#: Rollbalken schnitte ihren rechten Rand ab.
COLUMN_MARGIN = 40

#: Unter dieser Rolle trägt eine Zeile der Seitenliste den Index ihrer Seite.
#: Eine Teilüberschrift trägt keinen; daran erkennen Fenster und Zeichner sie.
PAGE_ROLE = Qt.ItemDataRole.UserRole

#: Der Abstand über einer Teilüberschrift, damit die Teile als Gruppen lesbar
#: sind und nicht als eine Liste mit fetten Zeilen darin.
HEADING_GAP = 3 * SPACE


#: Markdown-Bild, dessen Ziel nicht der eigene Abbildungskatalog ist. Der
#: negative Vorgriff lässt ``figure:`` durch, alles andere fällt — auch
#: ``file:``, ``http:`` und UNC-Pfade, die eine fremde Rezeptbeschreibung
#: mitbringen kann (UI-22).
_FOREIGN_IMAGE = re.compile(r"!\[([^\]]*)\]\((?!figure:)[^)]*\)")


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
        # **Fremde Bilder kommen gar nicht erst ins Dokument.** Ein leeres
        # ``QByteArray`` aus ``loadResource`` reichte nicht: Qts Bildhandler
        # lädt danach selbst von der Adresse nach (``source.load(name)``), und
        # das Bild stand gemessen im gezeichneten Dokument (UI-22, 06.09.2026).
        # Bleibt der Alt-Text — kursiv, damit der Leser sieht, dass hier ein
        # Bild gemeint war, das das Handbuch nicht zeigt.
        markdown = _FOREIGN_IMAGE.sub(r"*\1*", markdown)
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
            # Zweite Schicht hinter dem Filter in ``setMarkdown``. Ein
            # **gültiges** Bild, nicht ``None`` und nicht leere Daten: Bei
            # allem, woraus Qt kein Bild bauen kann, lädt es selbst von der
            # Adresse nach — ein transparentes Pixel ist ein Bild, und damit
            # ist die Anfrage beantwortet.
            blank = QImage(1, 1, QImage.Format.Format_ARGB32)
            blank.fill(0)
            return blank
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


class _Headings(QStyledItemDelegate):
    """Zeichnet die Teilüberschriften der Seitenliste als Überschriften.

    Die Zeile ist gesperrt, damit die Pfeiltasten über sie hinweggehen und ein
    Klick nichts wählt, wie im Bausteinkatalog. Gesperrt heißt in der Palette
    aber grau, und grau hieße „nicht verfügbar"; die Überschrift ist der
    Wegweiser durch die Liste und steht deshalb in voller Schriftfarbe, ohne
    Hervorhebung unter dem Mauszeiger und mit Abstand davor.
    """

    def initStyleOption(  # noqa: N802 — Qt gibt den Namen vor
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        super().initStyleOption(option, index)
        if index.data(PAGE_ROLE) is None:
            option.state |= QStyle.StateFlag.State_Enabled
            option.state &= ~QStyle.StateFlag.State_MouseOver

    def sizeHint(  # noqa: N802 — Qt gibt den Namen vor
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        size = super().sizeHint(option, index)
        if index.data(PAGE_ROLE) is None and index.row() > 0:
            size.setHeight(size.height() + HEADING_GAP)
        return size


def _part_heading(title: str) -> QListWidgetItem:
    """Die Überschrift eines Teils in der Seitenliste: nicht wählbar, fett, unten bündig."""
    heading = QListWidgetItem(title)
    heading.setFlags(Qt.ItemFlag.NoItemFlags)
    font = QFont(heading.font())
    font.setBold(True)
    heading.setFont(font)
    # Unten bündig, damit der Abstand aus ``_Headings.sizeHint`` über der
    # Überschrift steht und sie an ihren Seiten darunter hängt.
    heading.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
    heading.setData(Qt.ItemDataRole.AccessibleDescriptionRole, tr("Teil des Handbuchs"))
    return heading


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
        # Ohne Namen las ein Bildschirmleser „Eingabefeld", „Liste" und
        # „Text" — drei Teile, keiner sagt, wozu.
        self.search.setAccessibleName(tr("Handbuch durchsuchen"))

        self.contents = QListWidget(self)
        self.contents.setItemDelegate(_Headings(self.contents))
        self.contents.currentRowChanged.connect(self._show_current)
        self.contents.setAccessibleName(tr("Seiten des Handbuchs"))

        self.text = PageView(self)
        self.text.setAccessibleName(tr("Handbuchseite"))
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
        self._spots: list[str] = []
        self._reference_cursors: dict[str, QTextCursor] = {}
        # Zerlegt wird beim ersten Suchwort und nicht beim Öffnen: Wer das
        # Handbuch nur liest, wartet nicht auf einen Index, den er nie braucht.
        self._index: manual_search.SearchIndex | None = None
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

        Ein Verweis auf eine andere Seite des Handbuchs (``manual:<schlüssel>``,
        :data:`app.core.markup.MANUAL_LINK`) schlägt sie hier im Fenster auf.
        """
        if address.scheme() == "manual":
            self.show_page(address.path())
            return
        if address.scheme() == "https" and address.host() == QUrl(WEBSITE_URL).host():
            # Über ``open_link``: Ohne Browser liegt die Adresse danach in der
            # Zwischenablage, statt dass der Klick wortlos verpufft.
            open_link(address.toString(), self)

    # --- Inhalt ---------------------------------------------------------------

    def _fill(
        self,
        pages: list[manual.Page] | tuple[manual.Page, ...],
        spots: list[str] | None = None,
        *,
        grouped: bool = True,
    ) -> None:
        """Die Seitenliste neu setzen und die erste Seite zeigen.

        ``spots`` nennt je Seite die Stelle, an der sie nach einer Suche
        aufschlägt; ohne Suche beginnt jede oben. ``grouped`` setzt über jeden
        Teil des Handbuchs eine Überschrift (Konzept Handbuch §4). Eine Suche
        zeigt ihre Rangliste ohne: Dort zählt, was am besten passt, und eine
        Überschrift zwischen Rang eins und zwei risse zusammen, was die Suche
        geordnet hat.
        """
        # **Erst die alten Zeilen weg, dann die neue Liste.** ``clear()`` meldet
        # unterwegs noch eine alte Zeile; ihre Nummer zeigte in die schon neue,
        # kürzere Liste, und eine Suche ohne Treffer warf ``IndexError``
        # (Kundenmeldung zu 0.5.2).
        self.contents.clear()
        self._visible = list(pages)
        self._spots = spots or []
        part = None
        for index, page in enumerate(self._visible):
            if grouped and page.part != part:
                part = page.part
                self.contents.addItem(_part_heading(str(manual.PART_TITLES[part])))
            item = QListWidgetItem(str(page.title))
            item.setData(PAGE_ROLE, index)
            # Die erzeugten Kapitel bilden die zweite Hälfte des Handbuchs; der
            # Hinweis sagt, dass dort die vollständige Liste steht.
            # **Der volle Name im Hinweis, die Art dahinter.** „Ausprobieren
            # statt raten: Varianten und Kalibriere" stand im Verzeichnis —
            # mitten im Wort zu Ende und ohne Auslassungszeichen, also wie ein
            # kurzer Titel (Befund B34). Die Kürzung selbst ist richtig; was
            # fehlte, war der Weg zum ganzen Namen. Die Art ist der Teil des
            # Handbuchs: In einer Rangliste ohne Überschriften sagt er, ob die
            # Seite eine Anleitung, eine Erklärung oder Nachschlagewerk ist.
            art = (
                tr("Alle Operationen dieses Bereichs")
                if page.generated
                else str(manual.PART_TITLES[page.part])
            )
            item.setToolTip(str(page.title))
            item.setStatusTip(f"{page.title} — {art}")
            self.contents.addItem(item)
        if self._visible:
            self.contents.setCurrentRow(self._row_of(0))
        else:
            # Mit dem nächsten Schritt, nicht mit dem Ende (Regel 17).
            self.text.setMarkdown(
                tr(
                    "Dazu steht nichts im Handbuch. Versuchen Sie ein anderes Wort, "
                    "oder leeren Sie das Suchfeld für alle Seiten."
                )
            )

    def _index_at(self, row: int) -> int | None:
        """Welche Seite in dieser Zeile steht — ``None`` für eine Überschrift."""
        item = self.contents.item(row)
        index = item.data(PAGE_ROLE) if item is not None else None
        return index if isinstance(index, int) else None

    def _row_of(self, index: int) -> int:
        """In welcher Zeile die Seite mit diesem Index steht."""
        for row in range(self.contents.count()):
            if self._index_at(row) == index:
                return row
        return -1

    def current_page(self) -> manual.Page | None:
        """Die Seite, die gerade aufgeschlagen ist."""
        index = self._index_at(self.contents.currentRow())
        return None if index is None else self._visible[index]

    def _show_current(self, row: int) -> None:
        index = self._index_at(row)
        if index is None:
            return
        page = self._visible[index]
        # ``manual.titled`` und nicht ``if not page.generated``: Die vier
        # Wissensseiten sind erzeugt und bringen doch keine Überschrift mit
        # — über ihnen stand hier keine, und der Text fing mitten im Satz
        # an. Dieselbe Regel gilt für das erzeugte Handbuch; sie steht
        # deshalb im Kern und nicht zweimal.
        self.text.setMarkdown(manual.titled(page, self._with_figures(page)))
        self._mark_reference_anchors(page.key)
        self.text.moveCursor(self.text.textCursor().MoveOperation.Start)
        if index < len(self._spots) and self._spots[index]:
            self._show_spot(self._spots[index])

    def _mark_reference_anchors(self, key: str) -> None:
        """Unsichtbare Ziele an echte Überschriften im sicher eingelesenen Text hängen.

        Rohes HTML bleibt durch ``MarkdownNoHTML`` wirkungslos. Nur die
        erwarteten Überschriftenblöcke auf oberster Ebene erhalten Namen aus
        dem Register; Fließtext, Zitate und Listen können kein F1-Ziel übernehmen.
        """
        self._reference_cursors.clear()
        anchors = manual.reference_anchors(key)
        if not anchors:
            return
        headings: list[QTextCursor] = []
        block = self.text.document().begin()
        while block.isValid():
            block_format = block.blockFormat()
            if (
                block_format.headingLevel() == 3
                and block_format.indent() == 0
                and block_format.intProperty(QTextFormat.Property.BlockQuoteLevel) == 0
                and block.textList() is None
            ):
                cursor = QTextCursor(block)
                cursor.movePosition(
                    QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
                )
                headings.append(cursor)
            block = block.next()
        if [cursor.selectedText() for cursor in headings] != [
            markup.plain(title) for _anchor, title in anchors
        ]:
            _log.warning("manual reference headings do not match the registry for %r", key)
            return
        for (anchor, _title), cursor in zip(anchors, headings, strict=True):
            named = QTextCharFormat()
            named.setAnchor(True)
            named.setAnchorNames([anchor])
            cursor.mergeCharFormat(named)
            self._reference_cursors[anchor] = cursor

    def _show_anchor(self, anchor: str) -> None:
        """Genau den Referenzeintrag markieren, auch bei gleichen Kundentiteln."""
        cursor = self._reference_cursors.get(anchor)
        if cursor is None:
            _log.warning("manual operation anchor %r is not on the current page", anchor)
            return
        self.text.setTextCursor(cursor)
        self.text.scrollToAnchor(anchor)
        self._reveal_marked()

    def _show_spot(self, spot: str) -> None:
        """Die Seite an der Stelle aufschlagen, die zur Suche passt, und sie markieren.

        Vorher begann jede Seite oben. Bei *Gehäuse* stand das passende Wort in
        der Referenz „Bausteine" bei Wort 5 368 von 6 483, rund dreizehn
        Bildschirmhöhen tiefer (``konzepte/nachweise-handbuch-2026-09/
        findbarkeit.md``). Die Stelle rückt ins obere Drittel, damit der Satz
        davor noch zu sehen ist. Findet das Fenster sie nicht — etwa weil die
        Anzeige ein Zeichen anders setzt als der Text —, bleibt die Seite oben
        stehen, wie früher.
        """
        if not self.text.find(spot, QTextDocument.FindFlag.FindWholeWords):
            return
        self._reveal_marked()

    def _reveal_marked(self) -> None:
        """Die markierte Stelle ins obere Drittel der Textspalte rücken."""
        bar = self.text.verticalScrollBar()
        above = self.text.viewport().height() // 3
        bar.setValue(bar.value() + self.text.cursorRect().top() - above)

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
            # Ohne Auszeichnung: Ein Stern im kursiven Ersatz beendete ihn
            # mitten im Satz, eine Klammer im Alt-Text das Bild.
            alt = markup.plain(str(figure.alt))
            if not figure.available(language):
                return f"*{alt}*"
            caption = f"\n\n*{figure.caption}*" if figure.caption else ""
            return f"![{alt}](figure:{key}){caption}"

        # ``page.text()`` und nicht ``page.body``: Die Kurzfassung steht der
        # Seite voran, im Fenster wie im erzeugten Handbuch.
        return manual.FIGURE_PATTERN.sub(replace, page.text())

    def _filter(self, needle: str) -> None:
        """Über Titel *und* Text suchen, die passendste Seite zuerst.

        Wer sucht, weiß das Kapitel nicht. Wie die Treffer geordnet werden und
        welche Kundenwörter zu welchem Handbuchwort führen, steht im Kern
        (``manual_search``); hier wird nur gezeigt.
        """
        if not needle.strip():
            self._fill(self._pages)
            return
        index = self._index
        if index is None:
            index = self._index = manual_search.SearchIndex(self._pages)
        found = index.search(needle)
        self._fill([hit.page for hit in found], [hit.spot for hit in found], grouped=False)

    def show_page(self, key: str, spot: str = "") -> None:
        """Eine bestimmte Seite zeigen — der Weg von einer Operation ins Kapitel.

        ``spot`` schlägt sie an dieser Stelle auf, markiert. Mit ``#`` nennt
        F1 den eindeutigen Operationsanker; sonst bleibt es eine Textsuche.

        Ein Schlüssel ohne Seite lässt die gezeigte stehen und schreibt eine
        Warnung ins Protokoll: Jeder Aufrufer der Anwendung nennt eine Seite,
        die es gibt (geprüft in ``test_manual.py`` und ``test_guides.py``), und
        ein Fehlgriff soll im Fehlerbericht stehen statt still zu verpuffen —
        so blieb ein umbenanntes Referenzkapitel (``ref-<kategorie>``) in einem
        Test unbemerkt, der die alte Seite weiter für die neue hielt.
        """
        self.search.clear()
        for index, page in enumerate(self._visible):
            if page.key != key:
                continue
            row = self._row_of(index)
            if row == self.contents.currentRow():
                # Schon offen: Qt meldet keinen Wechsel. Eine Stelle wird vom
                # Anfang der Seite aus gesucht, nicht von der letzten; ohne
                # Stelle bleibt die Seite, wo der Leser steht — F1 im Dialog
                # eines Anleitungsschritts führt zum nächsten Schritt, nicht
                # zurück zum ersten.
                if spot:
                    self.text.moveCursor(self.text.textCursor().MoveOperation.Start)
            else:
                self.contents.setCurrentRow(row)
            if spot:
                if spot.startswith("#"):
                    self._show_anchor(spot[1:])
                else:
                    self._show_spot(spot)
            return
        _log.warning("manual page %r is not among the pages shown", key)


# ``OVERSAMPLING`` stand hier bis zum 07.09.2026 als eigene Kopie, mit
# demselben Wert und demselben Grund wie in ``icons.py`` — beide rastern SVG
# feiner, als sie es zeigen. Eine Zahl, ein Ort.


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
