"""The command palette (Bauplan §2.6, §19.2).

The universal way in: everything from the registry, reachable by typing. The
shortcut is shown next to each entry — that is how the shortcuts get learned,
without anyone reading a table of them.
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import PaletteEntry, palette_entries
from app.i18n import tr


def matches(entry: PaletteEntry, query: str) -> bool:
    """Substring search over title, name and documentation, accents and all."""
    if not query:
        return True
    haystack = f"{entry.title} {entry.name} {entry.doc}".casefold()
    return all(part in haystack for part in query.casefold().split())


class CommandPalette(QDialog):
    """Type, pick, run."""

    def __init__(self, entries: list[PaletteEntry] | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Befehle"))
        self.setMinimumWidth(520)
        self._entries = entries if entries is not None else list(palette_entries())

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("Befehl suchen …"))
        self.search.textChanged.connect(self._refilter)
        self.search.returnPressed.connect(self.accept)

        self.list = QListWidget(self)
        self.list.itemActivated.connect(lambda _item: self.accept())

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        self._refilter("")

    def _refilter(self, query: str) -> None:
        self.list.clear()
        for entry in self._entries:
            if not matches(entry, query):
                continue
            label = str(entry.title)
            if entry.shortcut:
                label = f"{label}\t{entry.shortcut}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry.name)
            item.setToolTip(str(entry.doc))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def chosen(self) -> str | None:
        """Name of the picked operation, or None."""
        # The stubs promise an item; an empty list returns None all the same.
        item = cast(QListWidgetItem | None, self.list.currentItem())
        if item is None:
            return None
        value: str = item.data(Qt.ItemDataRole.UserRole)
        return value

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt name
        """Arrow keys steer the list even while the cursor is in the search field."""
        key = Qt.Key(event.key())
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            step = 1 if key == Qt.Key.Key_Down else -1
            row = self.list.currentRow() + step
            self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
            return
        super().keyPressEvent(event)
