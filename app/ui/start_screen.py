"""The first five minutes (Bauplan §2.3).

No empty start screen: recent projects, the example projects once they exist,
and a large drop area. Dragging and dropping works here as it does on the window,
the viewport and the object tree.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, PROJECT_SUFFIX
from app.core.geom.mesh import READABLE_SUFFIXES
from app.i18n import tr


class DropArea(QFrame):
    """The large drop area. Accepts projects and models alike."""

    fileDropped = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(160)
        self.setStyleSheet("QFrame { border: 2px dashed palette(mid); border-radius: 8px; }")

        hint = QLabel(
            tr("Modell oder Projekt hier ablegen\nSTL · 3MF · OBJ · GLB · {suffix}").replace(
                "{suffix}", PROJECT_SUFFIX
            ),
            self,
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt name
        if accepted_path(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt name
        path = accepted_path(event)
        if path is not None:
            self.fileDropped.emit(path)
            event.acceptProposedAction()


def accepted_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
    """The first dropped file this application can do something with."""
    data = event.mimeData()
    if not data.hasUrls():
        return None
    for url in data.urls():
        if not url.isLocalFile():
            continue
        path = Path(url.toLocalFile())
        if path.suffix.lower() in (*READABLE_SUFFIXES, PROJECT_SUFFIX):
            return path
    return None


class StartScreen(QWidget):
    """What is shown before a project is open."""

    openRequested = Signal(Path)
    newRequested = Signal()
    browseRequested = Signal()
    fileDropped = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        title = QLabel(APP_NAME, self)
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        self.recent_list = QListWidget(self)
        self.recent_list.itemActivated.connect(self._on_recent)

        new_button = QPushButton(tr("Neues Projekt"), self)
        new_button.clicked.connect(self.newRequested)
        open_button = QPushButton(tr("Projekt öffnen …"), self)
        open_button.clicked.connect(self.browseRequested)

        drop = DropArea(self)
        drop.fileDropped.connect(self.fileDropped)

        buttons = QHBoxLayout()
        buttons.addWidget(new_button)
        buttons.addWidget(open_button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(drop)
        layout.addLayout(buttons)
        layout.addWidget(QLabel(tr("Zuletzt geöffnet"), self))
        layout.addWidget(self.recent_list, stretch=1)

    def show_recent(self, paths: list[Path]) -> None:
        self.recent_list.clear()
        if not paths:
            item = QListWidgetItem(tr("Noch nichts geöffnet."))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recent_list.addItem(item)
            return
        for path in paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.recent_list.addItem(item)

    def _on_recent(self, item: QListWidgetItem) -> None:
        stored = item.data(Qt.ItemDataRole.UserRole)
        if stored:
            self.openRequested.emit(Path(stored))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt name
        if accepted_path(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt name
        path = accepted_path(event)
        if path is not None:
            self.fileDropped.emit(path)
            event.acceptProposedAction()
