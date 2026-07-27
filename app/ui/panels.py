"""The three panels on the left and the report on the right (Bauplan §2.5).

Three collapsible sections, not three windows: object tree, parameters, history.
They read from the document and the last evaluation, and they never change
geometry themselves — every change goes through an operation (AGENTS.md rule 2).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import REGISTRY
from app.core.scene import EvaluationResult
from app.core.types import Document, Finding, ObjectId
from app.core.units import format_length
from app.i18n import tr

#: Marker per severity. Never colour alone (§19.1).
SEVERITY_MARKER = {"info": "·", "warning": "!", "error": "×"}


class ObjectTree(QWidget):
    """Objects of the scene with their origin and size (§18.8)."""

    selectionChanged = Signal(object)
    operationRequested = Signal(object)
    """An operation picked from the context menu — carries its ``OperationSpec``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr("Objekt"), tr("Maße")])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setRootIsDecorated(False)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.tree.setAcceptDrops(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)

    def show_scene(self, result: EvaluationResult | None) -> None:
        self.tree.clear()
        if result is None:
            return
        for object_id, entry in result.scene.objects.items():
            size = entry.mesh.bounds.size
            item = QTreeWidgetItem(
                [
                    entry.name,
                    f"{size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm",
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, object_id)
            state = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
            item.setToolTip(
                0,
                f"{object_id} · {entry.mesh.triangle_count} {tr('Dreiecke')} · {state}",
            )
            self.tree.addTopLevelItem(item)
        self.tree.resizeColumnToContents(0)

    def selected(self) -> ObjectId | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        value: ObjectId | None = items[0].data(0, Qt.ItemDataRole.UserRole)
        return value

    def _on_selection(self) -> None:
        self.selectionChanged.emit(self.selected())

    def operations_for_object(self) -> tuple[Any, ...]:
        """Operations that work on a selected object — the shortest way from seeing
        to doing (§2.6). The feature context menu over ``applies_to`` follows in P3."""
        return tuple(spec for spec in REGISTRY.all() if spec.consumes == 1)

    def _on_context_menu(self, position: QPoint) -> None:
        if self.selected() is None:
            return
        menu = QMenu(self)
        for spec in self.operations_for_object():
            action = menu.addAction(str(spec.title))
            action.triggered.connect(
                lambda _checked=False, entry=spec: self.operationRequested.emit(entry)
            )
        menu.exec(self.tree.viewport().mapToGlobal(position))


class ParameterPanel(QWidget):
    """Named project dimensions; turning a number rebuilds the model (§13)."""

    parameterEdited = Signal(str, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._form = QFormLayout(self)
        self._form.setContentsMargins(6, 6, 6, 6)
        self._empty = QLabel(tr("Noch keine Parameter."), self)
        self._empty.setWordWrap(True)
        self._form.addRow(self._empty)
        self._editors: dict[str, QDoubleSpinBox] = {}

    def show_document(self, document: Document) -> None:
        while self._form.rowCount():
            self._form.removeRow(0)
        self._editors.clear()

        if not document.parameters:
            self._empty = QLabel(tr("Noch keine Parameter."), self)
            self._form.addRow(self._empty)
            return

        for name, parameter in document.parameters.items():
            if parameter.expression:
                # Derived values are shown, not edited — the expression owns them.
                label = QLabel(f"{parameter.value:.2f} {parameter.unit}", self)
                label.setToolTip(parameter.expression)
                self._form.addRow(f"{parameter.title or name}", label)
                continue
            editor = QDoubleSpinBox(self)
            editor.setDecimals(2)
            editor.setSuffix(f" {parameter.unit}")
            editor.setMinimum(parameter.minimum if parameter.minimum is not None else -100_000.0)
            editor.setMaximum(parameter.maximum if parameter.maximum is not None else 100_000.0)
            editor.setValue(parameter.value)
            editor.setKeyboardTracking(False)
            editor.valueChanged.connect(
                lambda value, key=name: self.parameterEdited.emit(key, value)
            )
            self._editors[name] = editor
            self._form.addRow(f"{parameter.title or name}", editor)


class HistoryPanel(QWidget):
    """Transactions, newest last. The unit of undo (§15.5)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)

    def show_document(self, document: Document, stopped_at: int | None = None) -> None:
        self.list.clear()
        for transaction in document.transactions:
            by = tr("Agent") if transaction.origin.by == "agent" else tr("Nutzer")
            item = QListWidgetItem(f"{transaction.title}  ({by})")
            if stopped_at is not None and stopped_at in transaction.ops:
                # §15.3: the affected operations are marked in the history.
                item.setText(f"! {item.text()}")
            item.setToolTip(
                f"{transaction.id} · {tr('Ops')} "
                + ", ".join(str(entry) for entry in transaction.ops)
            )
            self.list.addItem(item)
        self.list.scrollToBottom()


class ReportPanel(QWidget):
    """Findings from ingest, operations and checks (§17.3)."""

    findingActivated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget(self)
        self.list.itemActivated.connect(self._on_activated)
        self.summary = QLabel(tr("Keine Befunde."), self)
        self.summary.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.summary)
        layout.addWidget(self.list)

    def show_result(self, result: EvaluationResult | None) -> None:
        self.list.clear()
        findings = result.scene.report.findings if result else ()
        if not findings:
            self.summary.setText(tr("Keine Befunde."))
            return

        counts = {level: 0 for level in SEVERITY_MARKER}
        for finding in findings:
            counts[finding.severity] += 1
            item = QListWidgetItem(f"{SEVERITY_MARKER[finding.severity]}  {finding.message}")
            item.setData(Qt.ItemDataRole.UserRole, finding)
            if finding.values:
                item.setToolTip(
                    ", ".join(f"{key}: {value}" for key, value in finding.values.items())
                )
            self.list.addItem(item)
        self.summary.setText(
            f"{counts['error']} × {tr('Fehler')} · "
            f"{counts['warning']} × {tr('Warnung')} · "
            f"{counts['info']} × {tr('Hinweis')}"
        )

    def worst_severity(self, result: EvaluationResult | None) -> str | None:
        if result is None:
            return None
        return result.scene.report.worst_severity

    def _on_activated(self, item: QListWidgetItem) -> None:
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        self.findingActivated.emit(finding)


class ChatPlaceholder(QWidget):
    """Without an LLM key everything but the chat works — one hint, no nagging (§2.3)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        hint = QLabel(
            tr(
                "Der Chat braucht einen Zugang zu einem Sprachmodell. "
                "Alles andere funktioniert ohne."
            ),
            self,
        )
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(hint)
        layout.addStretch(1)


class MeasurementLabel(QLabel):
    """Dimensions of the selection for the status bar (§2.5)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.clear_selection()

    def clear_selection(self) -> None:
        self.setText(tr("Keine Auswahl"))

    def show_object(self, name: str, size: tuple[float, float, float], volume: float) -> None:
        self.setText(
            f"{name}   "
            f"{format_length(size[0], 'mm', with_unit=False)} × "
            f"{format_length(size[1], 'mm', with_unit=False)} × "
            f"{format_length(size[2], 'mm')}   "
            f"{volume / 1000.0:.1f} cm³"
        )


def collapsible(title: str, content: QWidget) -> QWidget:
    """A section with a heading — three sections, not three windows (§2.5)."""
    wrapper = QWidget()
    heading = QLabel(title, wrapper)
    heading.setStyleSheet("font-weight: 600;")
    header = QHBoxLayout()
    header.setContentsMargins(6, 4, 6, 2)
    header.addWidget(heading)
    header.addStretch(1)

    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addLayout(header)
    layout.addWidget(content)
    return wrapper


def describe_selection(result: EvaluationResult | None, object_id: ObjectId | None) -> Any:
    """Name, size and volume of the selected object, or None."""
    if result is None or object_id is None:
        return None
    entry = result.scene.objects.get(object_id)
    if entry is None:
        return None
    return entry.name, entry.mesh.bounds.size, entry.mesh.volume
