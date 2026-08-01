"""Der Bausteinkatalog (Bauplan §24.3, §2.6).

„Eine Bibliothek, die man nicht sehen kann, existiert für den Nutzer nicht."
Also ist das ein Fenster mit Bildern, einer kurzen Beschreibung und den zwei
wichtigsten Parametern jedes Bausteins — und die Bilder kommen aus den
Bausteinen selbst (§24.3), gerendert beim Öffnen des Katalogs.

Eigene Bausteine sind als solche gekennzeichnet (§24.5). Der Unterschied
zählt: sie existieren nur auf dieser Maschine, und ein Projekt, das einen
benutzt, lässt sich nicht so weitergeben wie der Rest.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QByteArray, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.knowledge.parts import GROUPS, PARTS
from app.core.knowledge.parts.preview import SIZE, render
from app.core.knowledge.parts.registry import PartSpec
from app.i18n import tr

#: Wie viele Parameter ein Katalogeintrag zeigt. §24.3 verlangt die zwei
#: wichtigsten — und das sind die zwei zuerst deklarierten, denn eine
#: Deklaration wird in der Reihenfolge geschrieben, in der jemand über den
#: Baustein nachdenkt.
SHOWN_PARAMETERS = 2

OWN_MARKER = "*"


class PartCatalog(QDialog):
    """Bilder, Beschreibungen und ein Suchfeld."""

    partChosen = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Bausteine"))
        self.resize(560, 640)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Suchen — zum Beispiel Mutter, Magnet, Kabel"))
        self.search.textChanged.connect(self.show_parts)

        self.list = QListWidget(self)
        self.list.setIconSize(_icon_size())
        self.list.setWordWrap(True)
        self.list.itemDoubleClicked.connect(self._chosen)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list, stretch=1)
        layout.addWidget(buttons)

        self._previews: dict[str, QPixmap] = {}
        self.show_parts()
        QTimer.singleShot(0, self._render_pending)

    # --- content ----------------------------------------------------------------

    def show_parts(self, text: str = "") -> None:
        """Füllt die Liste, gruppiert wie der Katalog gruppiert."""
        self.list.clear()
        wanted = PARTS.search(text) if text.strip() else PARTS.all()
        by_group: dict[str, list[PartSpec]] = {}
        for spec in wanted:
            by_group.setdefault(spec.group, []).append(spec)

        for group, title in GROUPS.items():
            entries = by_group.get(group)
            if not entries:
                continue
            heading = QListWidgetItem(str(title))
            heading.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(heading)
            for spec in entries:
                self.list.addItem(self._item(spec))

    def _item(self, spec: PartSpec) -> QListWidgetItem:
        item = QListWidgetItem(describe(spec))
        item.setData(Qt.ItemDataRole.UserRole, spec.name)
        item.setIcon(self._preview(spec))
        item.setToolTip(str(spec.doc))
        return item

    def _preview(self, spec: PartSpec) -> Any:
        """Das Vorschaubild, wenn es schon da ist — sonst nichts.

        Jedes Bild wird aus dem Baustein gerechnet (§24.3). Alle beim Öffnen
        nacheinander zu rendern hieß: der Katalog geht auf, wenn das letzte
        fertig ist, und bis dahin hängt das Fenster. Jetzt füllen sie sich
        nach, und die Liste ist sofort lesbar — die Beschreibung daneben steht
        ohnehin von Anfang an.
        """
        from PySide6.QtGui import QIcon

        found = self._previews.get(spec.name)
        return QIcon(found) if found is not None else QIcon()

    def _render_pending(self) -> None:
        """Rendert das nächste fehlende Bild und reiht sich neu ein.

        Eines je Durchlauf der Ereignisschleife: das Fenster bleibt zwischen
        den Bildern bedienbar, und wer den Katalog gleich wieder schließt,
        hat nicht auf achtzehn Rechnungen gewartet.
        """
        from PySide6.QtGui import QPainter

        missing = next((spec for spec in PARTS.all() if spec.name not in self._previews), None)
        if missing is None:
            return

        image = render(missing)
        pixmap = QPixmap(_icon_size())
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(image.svg.encode("utf-8")))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self._previews[missing.name] = pixmap

        self._refresh_icon(missing.name)
        QTimer.singleShot(0, self._render_pending)

    def _refresh_icon(self, name: str) -> None:
        """Hängt ein fertiges Bild an seine Zeile, ohne die Liste neu zu bauen —
        ein Neuaufbau würde die Auswahl und die Bildlaufposition mitnehmen.
        """
        pixmap = self._previews.get(name)
        if pixmap is None:
            return
        from PySide6.QtGui import QIcon

        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
                item.setIcon(QIcon(pixmap))
                return

    # --- choosing ---------------------------------------------------------------

    def chosen(self) -> str | None:
        item = self.list.currentItem()
        value: str | None = item.data(Qt.ItemDataRole.UserRole) if item else None
        return value

    def _chosen(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.partChosen.emit(name)
            self.accept()

    def _accept(self) -> None:
        name = self.chosen()
        if name:
            self.partChosen.emit(name)
        self.accept()


def describe(spec: PartSpec) -> str:
    """Titel, die zwei wichtigsten Parameter, und woher der Baustein kommt."""
    parameters = ", ".join(str(entry.title) for entry in spec.params.spec()[:SHOWN_PARAMETERS])
    marker = f" {OWN_MARKER} {tr('eigener Baustein')}" if spec.own else ""
    return f"{spec.title}{marker}\n{parameters}"


def _icon_size() -> Any:
    from PySide6.QtCore import QSize

    return QSize(SIZE, SIZE)
