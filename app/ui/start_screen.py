"""Die ersten fünf Minuten (Bauplan §2.3).

Kein leerer Startbildschirm: zuletzt geöffnete Projekte, die Beispielprojekte,
sobald es sie gibt, und eine große Ablagefläche. Ziehen und Fallenlassen
funktioniert hier wie am Fenster, am Viewport und am Objektbaum.
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
from app.core import examples
from app.core.brep.step import SUFFIXES as STEP_SUFFIXES
from app.core.geom.mesh import READABLE_SUFFIXES
from app.core.ingest.outline import OUTLINE_SUFFIXES
from app.i18n import tr


class DropArea(QFrame):
    """Die große Ablagefläche. Nimmt Projekte und Modelle gleichermaßen."""

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
        # STEP is read by the other kernel and is therefore not among the mesh
        # suffixes — dropping one has to work all the same (§30).
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        title = QLabel(APP_NAME, self)
        title.setStyleSheet("font-size: 24px; font-weight: 600;")

        self.recent_list = QListWidget(self)
        self.recent_list.itemActivated.connect(self._on_recent)

        # §37.2: die Beispielprojekte sind Inhalt des Startbildschirms und kein
        # Ordner, den jemand suchen muss. Die Höhe richtet sich nach ihrer Zahl —
        # eine feste Höhe für drei versteckte die vier, die danach dazukamen,
        # hinter einer Bildlaufleiste.
        self.examples_list = QListWidget(self)
        self.examples_list.itemActivated.connect(self._on_recent)
        self.show_examples()

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
        layout.addWidget(QLabel(tr("Beispiele — die drei Wege und was darauf bereitliegt"), self))
        layout.addWidget(self.examples_list)
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

    def show_examples(self) -> None:
        """Die Beispielprojekte, soweit sie installiert sind."""
        self.examples_list.clear()
        for path in examples.paths():
            entry = examples.by_path(path)
            item = QListWidgetItem(str(entry.title) if entry else path.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(entry.doc) if entry else str(path))
            self.examples_list.addItem(item)

        rows = max(self.examples_list.count(), 1)
        height = self.examples_list.sizeHintForRow(0) if self.examples_list.count() else 22
        self.examples_list.setMaximumHeight(rows * max(height, 18) + 8)

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
