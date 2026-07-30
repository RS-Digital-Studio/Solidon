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
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
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
from app.core import manual
from app.i18n import tr


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

        self.text = QTextBrowser(self)
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
            body = str(page.body)
            if not page.generated:
                body = f"## {page.title}\n\n{body}"
            self.text.setMarkdown(body)
            self.text.moveCursor(self.text.textCursor().MoveOperation.Start)

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
                if wanted in str(page.title).casefold() or wanted in str(page.body).casefold()
            ]
        )

    def show_page(self, key: str) -> None:
        """Eine bestimmte Seite zeigen — der Weg von einer Operation ins Kapitel."""
        self.search.clear()
        for row, page in enumerate(self._visible):
            if page.key == key:
                self.contents.setCurrentRow(row)
                return
