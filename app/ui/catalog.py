"""The part catalogue (Bauplan §24.3, §2.6).

"A library one cannot see does not exist for the user." So this is a window with
pictures, a short description and the two most important parameters of every
part — and the pictures come out of the parts themselves (§24.3), rendered when
the catalogue opens.

Own parts are marked as such (§24.5). The difference matters: they only exist on
this machine, and a project that uses one cannot be passed on the way the rest
can.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QByteArray, Qt, Signal
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

#: How many parameters a catalogue entry shows. §24.3 asks for the two most
#: important ones — which are the first two declared, because a declaration is
#: written in the order someone thinks about the part.
SHOWN_PARAMETERS = 2

OWN_MARKER = "*"


class PartCatalog(QDialog):
    """Pictures, descriptions and a search field."""

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

    # --- content ----------------------------------------------------------------

    def show_parts(self, text: str = "") -> None:
        """Fill the list, grouped as the catalogue groups them."""
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
        """Rendered on first sight, kept for the rest of the session."""
        from PySide6.QtGui import QIcon

        if spec.name not in self._previews:
            image = render(spec)
            pixmap = QPixmap(_icon_size())
            pixmap.fill(Qt.GlobalColor.transparent)
            renderer = QSvgRenderer(QByteArray(image.svg.encode("utf-8")))
            from PySide6.QtGui import QPainter

            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            self._previews[spec.name] = pixmap
        return QIcon(self._previews[spec.name])

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
    """Title, the two most important parameters, and where the part comes from."""
    parameters = ", ".join(str(entry.title) for entry in spec.params.spec()[:SHOWN_PARAMETERS])
    marker = f" {OWN_MARKER} {tr('eigener Baustein')}" if spec.own else ""
    return f"{spec.title}{marker}\n{parameters}"


def _icon_size() -> Any:
    from PySide6.QtCore import QSize

    return QSize(SIZE, SIZE)
