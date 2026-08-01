"""Die drei Panels links und der Prüfbericht rechts (Bauplan §2.5).

Drei einklappbare Abschnitte, keine drei Fenster: Objektbaum, Parameter,
Verlauf. Sie lesen aus dem Dokument und der letzten Auswertung, und sie ändern
nie selbst Geometrie — jede Änderung geht durch eine Operation (AGENTS.md
Regel 2).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
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
from app.ui.labels import feature_label
from app.ui.palette import SEVERITY_ENCODING

#: Zeichen je Schweregrad, aus der gemeinsamen Kodierung — Farbe steht nie
#: allein (§19.1).
SEVERITY_MARKER = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}


def origin_label(source: str) -> str:
    """Hier geschätzt oder aus G-Code gemessen — nie verwechselt (§22.5)."""
    return tr("intern geschätzt") if source == "internal" else tr("aus G-Code")


class ObjectTree(QWidget):
    """Objekte der Szene mit ihren Merkmalen, Herkunft und Größe (§18.8,
    §18.5).
    """

    selectionChanged = Signal(object)
    featureSelected = Signal(object)
    """A feature picked in the tree — carries its id, or None."""
    operationRequested = Signal(object)
    """An operation picked from the context menu — carries its ``OperationSpec``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr("Objekt"), tr("Maße")])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.tree.setAcceptDrops(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)

    def show_scene(self, result: EvaluationResult | None) -> None:
        selected_object = self.selected()
        selected_feature = self.selected_feature()
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
            # §30: welche Sorte Körper das ist, gehört in den Baum, denn sie
            # entscheidet, was sich noch mit ihm tun lässt — und der Weg von
            # B-Rep zu Mesh ist eine Einbahnstraße.
            kind = tr("exakt") if entry.kind == "brep" else tr("Netz")
            tip = f"{object_id} · {kind} · {entry.mesh.triangle_count} {tr('Dreiecke')} · {state}"
            if entry.material:
                tip += f" · {entry.material}"
            item.setToolTip(0, tip)
            if entry.kind == "brep":
                item.setText(0, f"{entry.name}  ·  {kind}")
            if entry.material:
                # §12: ein Körper, der nicht im Material des Projekts ist, muss das
                # dort sagen, wo die Teile aufgezählt werden — sonst zeigt sich
                # der Unterschied nur an einer Passung, die auf einmal ein
                # anderes Spiel will.
                item.setText(1, f"{item.text(1)}  ·  {entry.material}")
            for feature_id, feature in entry.features.items():
                child = QTreeWidgetItem([feature_label(feature_id, feature), feature.kind])
                child.setData(0, Qt.ItemDataRole.UserRole, object_id)
                child.setData(1, Qt.ItemDataRole.UserRole, feature_id)
                child.setToolTip(0, f"{feature_id} · {feature.provenance}")
                item.addChild(child)
            self.tree.addTopLevelItem(item)
            item.setExpanded(object_id == selected_object)
        self.tree.resizeColumnToContents(0)
        self._restore(selected_object, selected_feature)

    def _restore(self, object_id: ObjectId | None, feature_id: str | None) -> None:
        """Behält die Auswahl über eine Neuauswertung hinweg — sie zu verlieren
        kostet den Nutzer die Stelle, an der er gearbeitet hat.
        """
        if object_id is None:
            return
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None or item.data(0, Qt.ItemDataRole.UserRole) != object_id:
                continue
            if feature_id is None:
                item.setSelected(True)
                return
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                if child is not None and child.data(1, Qt.ItemDataRole.UserRole) == feature_id:
                    child.setSelected(True)
                    return
            item.setSelected(True)
            return

    def selected(self) -> ObjectId | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        value: ObjectId | None = items[0].data(0, Qt.ItemDataRole.UserRole)
        return value

    def selected_feature(self) -> str | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        value: str | None = items[0].data(1, Qt.ItemDataRole.UserRole)
        return value

    def select_feature(self, object_id: ObjectId, feature_id: str) -> None:
        """Folgt einem Klick im Viewport — die zwei Ansichten zeigen eine
        Auswahl (§18.5).
        """
        self.tree.clearSelection()
        self._restore(object_id, feature_id)

    def _on_selection(self) -> None:
        self.selectionChanged.emit(self.selected())
        self.featureSelected.emit(self.selected_feature())

    def operations_for_object(self) -> tuple[Any, ...]:
        """Operationen, die auf einem gewählten Objekt arbeiten — der kürzeste
        Weg vom Sehen zum Tun (§2.6).
        """
        return tuple(spec for spec in REGISTRY.all() if spec.consumes == 1)

    def operations_for_feature(self, kind: str) -> tuple[Any, ...]:
        """Was eine Bohrung oder eine Fläche anbietet, direkt aus ``applies_to``
        (§10, §18.5).
        """
        return REGISTRY.for_feature(kind)

    def _feature_kind(self) -> str | None:
        items = self.tree.selectedItems()
        if not items or self.selected_feature() is None:
            return None
        return items[0].text(1)

    def _on_context_menu(self, position: QPoint) -> None:
        if self.selected() is None:
            return
        kind = self._feature_kind()
        entries = self.operations_for_feature(kind) if kind else self.operations_for_object()
        if not entries:
            return
        menu = QMenu(self)
        for spec in entries:
            action = menu.addAction(str(spec.title))
            action.triggered.connect(
                lambda _checked=False, entry=spec: self.operationRequested.emit(entry)
            )
        menu.exec(self.tree.viewport().mapToGlobal(position))


class ParameterPanel(QWidget):
    """Benannte Projektmaße; an einer Zahl zu drehen baut das Modell
    neu (§13).
    """

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
                # Abgeleitete Werte werden gezeigt, nicht bearbeitet — der Ausdruck
                # besitzt sie.
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
    """Transaktionen, neueste zuletzt. Die Einheit des Undo (§15.5).

    Eine Transaktion ist eine Zeile, denn das ist es, was ein Undo
    zurücknimmt. Ihre Operationen bekommen eine eigene Zeile, wo es mehr als
    eine gibt — ein Agentenvorschlag, eine Teilung in vier —, damit sich jeder
    Schritt des Stapels öffnen und korrigieren lässt, nicht nur die, die allein
    kamen (§15.4).
    """

    operationActivated = Signal(int)
    """An operation was double-clicked — carries its id, for editing (§15.4)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget(self)
        self.list.itemDoubleClicked.connect(self._on_activated)
        self.list.setToolTip(tr("Doppelklick öffnet die Operation und ihre Parameter."))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)

    def show_document(self, document: Document, stopped_at: int | None = None) -> None:
        self.list.clear()
        titles = {entry.id: entry.op for entry in document.ops}
        for transaction in document.transactions:
            by = tr("Agent") if transaction.origin.by == "agent" else tr("Nutzer")
            item = QListWidgetItem(f"{transaction.title}  ({by})")
            if stopped_at is not None and stopped_at in transaction.ops:
                # §15.3: die betroffenen Operationen werden im Verlauf markiert.
                item.setText(f"! {item.text()}")
            item.setToolTip(
                f"{transaction.id} · {tr('Ops')} "
                + ", ".join(str(entry) for entry in transaction.ops)
            )
            if len(transaction.ops) == 1:
                item.setData(Qt.ItemDataRole.UserRole, transaction.ops[0])
            self.list.addItem(item)

            if len(transaction.ops) > 1:
                for op_id in transaction.ops:
                    child = QListWidgetItem(f"    {op_id}  {titles.get(op_id, '')}")
                    child.setData(Qt.ItemDataRole.UserRole, op_id)
                    self.list.addItem(child)
        self.list.scrollToBottom()

    def _on_activated(self, item: QListWidgetItem) -> None:
        op_id = item.data(Qt.ItemDataRole.UserRole)
        if op_id is not None:
            self.operationActivated.emit(int(op_id))


class ReportPanel(QWidget):
    """Befunde aus Einlesen, Operationen und Prüfungen (§17.3)."""

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
        for finding in result.scene.report.findings if result else ():
            self._append(finding)
        self._count_up()

    def add_findings(self, findings: list[Finding]) -> None:
        """Hängt Befunde an, die nicht aus der Auswertung kamen — die
        G-Code-Gegenprobe etwa (§28.2). Sie behalten ihre eigene
        Herkunft (§22.5).
        """
        for finding in findings:
            self._append(finding)
        self._count_up()
        self.list.scrollToBottom()

    def _append(self, finding: Finding) -> None:
        """Einen Befund als Eintrag anhängen."""
        item = QListWidgetItem(f"{SEVERITY_MARKER[finding.severity]}  {finding.message}")
        item.setData(Qt.ItemDataRole.UserRole, finding)
        item.setForeground(QColor(SEVERITY_ENCODING[finding.severity].colour))
        # §22.5: woher eine Zahl kommt, ist Teil des Befunds und wird nie dem
        # Leser zum Annehmen überlassen — eine Schätzung ist keine Messung.
        details = [f"{tr('Herkunft')}: {origin_label(finding.source)}"]
        details.extend(f"{key}: {value}" for key, value in finding.values.items())
        item.setToolTip(" · ".join(details))
        self.list.addItem(item)

    def _count_up(self) -> None:
        """Die Zeile über der Liste aus der Liste selbst zählen.

        Nicht aus dem übergebenen Ergebnis: Befunde kommen aus zwei Richtungen
        — aus der Auswertung und über ``add_findings`` —, und wer nur die eine
        zählt, schreibt „Keine Befunde" über eine Liste voller Befunde. Genau
        das stand hier.
        """
        counts = dict.fromkeys(SEVERITY_MARKER, 0)
        for row in range(self.list.count()):
            finding: Finding = self.list.item(row).data(Qt.ItemDataRole.UserRole)
            counts[finding.severity] += 1
        if not any(counts.values()):
            self.summary.setText(tr("Keine Befunde."))
            return
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
    """Ohne LLM-Schlüssel funktioniert alles außer dem Chat — ein Hinweis,
    kein Nörgeln (§2.3).
    """

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
    """Maße der Auswahl für die Statusleiste (§2.5)."""

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
    """Ein Abschnitt mit Überschrift — drei Abschnitte, keine drei
    Fenster (§2.5).
    """
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
    """Name, Größe und Volumen des gewählten Objekts, oder None."""
    if result is None or object_id is None:
        return None
    entry = result.scene.objects.get(object_id)
    if entry is None:
        return None
    return entry.name, entry.mesh.bounds.size, entry.mesh.volume
