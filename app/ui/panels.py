"""Die drei Panels links und der Prüfbericht rechts (Bauplan §2.5).

Drei einklappbare Abschnitte, keine drei Fenster: Objektbaum, Parameter,
Verlauf. Sie lesen aus dem Dokument und der letzten Auswertung, und sie ändern
nie selbst Geometrie — jede Änderung geht durch eine Operation (AGENTS.md
Regel 2).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSizePolicy,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import REGISTRY
from app.core.scene import EvaluationResult
from app.core.types import Document, Finding, ObjectId
from app.core.units import LengthUnit, format_length, format_volume
from app.i18n import tr
from app.ui.icons import icon
from app.ui.labels import feature_label
from app.ui.palette import SEVERITY_ENCODING

#: Zeichen je Schweregrad, aus der gemeinsamen Kodierung — Farbe steht nie
#: allein (§19.1).
SEVERITY_MARKER = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}


def origin_label(source: str) -> str:
    """Hier geschätzt oder aus G-Code gemessen — nie verwechselt (§22.5)."""
    return tr("intern geschätzt") if source == "internal" else tr("aus G-Code")


def _origin_text(created_by: int | None, document: Document | None) -> str:
    """Aus welcher Operation und Transaktion ein Körper stammt (§18.8).

    Die Transaktion ist die Einheit, die der Verlauf zeigt und die ein Undo
    nimmt (§15.5) — sie zu nennen verbindet den Körper im Baum mit der Zeile
    im Verlauf. Fehlt das Dokument, bleibt die Operationsnummer.
    """
    if created_by is None:
        return ""
    text = f"{tr('aus Operation')} {created_by}"
    if document is None:
        return text
    for transaction in document.transactions:
        if created_by in transaction.ops:
            return f"{text} · {transaction.title}"
    return text


class ObjectTree(QWidget):
    """Objekte der Szene mit ihren Merkmalen, Herkunft und Größe (§18.8,
    §18.5).
    """

    selectionChanged = Signal(object)
    featureSelected = Signal(object)
    """A feature picked in the tree — carries its id, or None."""
    operationRequested = Signal(object)
    """An operation picked from the context menu — carries its ``OperationSpec``."""
    visibilityRequested = Signal(object, bool)
    """Ein- oder ausblenden (§18.8) — trägt die Kennungen und den Wunsch."""
    isolateRequested = Signal(object)
    """Nur diese zeigen — trägt die Kennungen. Ein zweiter Aufruf hebt es auf."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr("Objekt"), tr("Maße")])
        # §25: Vereinigen, Abziehen und Schnittmenge nehmen zwei Körper. Mit
        # Einfachauswahl war keine davon über das Menü ausführbar — die
        # Operation bekam einen Eingang, wo sie zwei erwartet, und lehnte ab.
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        self._order: list[ObjectId] = []
        """Die Reihenfolge, in der angeklickt wurde. „A minus B" ist nicht „B
        minus A", und die Reihenfolge im Baum weiß davon nichts."""
        self._hidden: frozenset[ObjectId] = frozenset()
        self._unit: LengthUnit = "mm"
        self._result: EvaluationResult | None = None
        self._document: Document | None = None
        """Das Zuletzt-Gezeigte, damit sich der Baum ohne neue Auswertung
        neu zeichnen kann — beim Ausblenden ändert sich nur die Anzeige."""
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.tree.setAcceptDrops(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)

    def set_hidden(self, hidden: frozenset[ObjectId]) -> None:
        """Welche Körper gerade nicht gezeichnet werden — nur zum Anzeigen."""
        if hidden == self._hidden:
            return
        self._hidden = hidden
        self.show_scene(self._result, self._document)

    def set_unit(self, unit: LengthUnit) -> None:
        """§19.3: Millimeter oder Zoll in der Maße-Spalte."""
        if unit == self._unit:
            return
        self._unit = unit
        self.show_scene(self._result, self._document)

    def show_scene(self, result: EvaluationResult | None, document: Document | None = None) -> None:
        selected = self.selected_objects()
        selected_feature = self.selected_feature()
        self._result = result
        self._document = document
        self.tree.clear()
        if result is None:
            return
        for object_id, entry in result.scene.objects.items():
            size = entry.mesh.bounds.size
            # §19.3: die Einheit stand hier fest, obwohl sie eine Einstellung
            # ist. Umgerechnet wird nur für die Anzeige — im Netz bleibt jede
            # Zahl ein Millimeter.
            measures = " × ".join(
                format_length(value, self._unit, with_unit=False) for value in size
            )
            item = QTreeWidgetItem([entry.name, f"{measures} {self._unit}"])
            item.setData(0, Qt.ItemDataRole.UserRole, object_id)
            state = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
            # §30: welche Sorte Körper das ist, gehört in den Baum, denn sie
            # entscheidet, was sich noch mit ihm tun lässt — und der Weg von
            # B-Rep zu Mesh ist eine Einbahnstraße.
            kind = tr("exakt") if entry.kind == "brep" else tr("Netz")
            tip = f"{object_id} · {kind} · {entry.mesh.triangle_count} {tr('Dreiecke')} · {state}"
            if entry.material:
                tip += f" · {entry.material}"
            # §18.8: woher der Körper kommt. Ohne das ist ein Baum mit sieben
            # Teilen aus einer Teilung eine Liste ohne Vorgeschichte — und die
            # Frage „welcher Schritt hat das gemacht" nur durch Ausprobieren zu
            # beantworten.
            origin = _origin_text(entry.created_by, document)
            if origin:
                tip += f" · {origin}"
            item.setToolTip(0, tip)
            if entry.kind == "brep":
                item.setText(0, f"{entry.name}  ·  {kind}")
            if object_id in self._hidden:
                # Zeichen und Wort: eine ausgegraute Zeile allein wäre Farbe als
                # einzige Kodierung (Regel 18).
                item.setIcon(0, icon("hidden", self.tree))
                item.setText(0, f"{item.text(0)}  ·  {tr('ausgeblendet')}")
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
            item.setExpanded(object_id in selected)
        self.tree.resizeColumnToContents(0)
        self._restore(selected, selected_feature)

    def _restore(self, objects: Sequence[ObjectId], feature_id: str | None) -> None:
        """Behält die Auswahl über eine Neuauswertung hinweg — sie zu verlieren
        kostet den Nutzer die Stelle, an der er gearbeitet hat.

        Das Merkmal gilt nur, wenn genau ein Körper gewählt war; bei mehreren
        gibt es keines, auf das es sich beziehen könnte.
        """
        if not objects:
            return
        wanted = set(objects)
        self._order = list(objects)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is None or item.data(0, Qt.ItemDataRole.UserRole) not in wanted:
                continue
            if feature_id is not None and len(wanted) == 1:
                for child_index in range(item.childCount()):
                    child = item.child(child_index)
                    if child is not None and child.data(1, Qt.ItemDataRole.UserRole) == feature_id:
                        child.setSelected(True)
                        break
                else:
                    item.setSelected(True)
                continue
            item.setSelected(True)

    def selected(self) -> ObjectId | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        value: ObjectId | None = items[0].data(0, Qt.ItemDataRole.UserRole)
        return value

    def selected_objects(self) -> tuple[ObjectId, ...]:
        """Die gewählten Körper in der Reihenfolge, in der sie angeklickt
        wurden.

        Ein angeklicktes Merkmal zählt für seinen Körper: wer eine Bohrung
        markiert und dann etwas mit dem Teil tut, meint das Teil.
        """
        chosen = {
            object_id
            for item in self.tree.selectedItems()
            if (object_id := item.data(0, Qt.ItemDataRole.UserRole)) is not None
        }
        ordered = [object_id for object_id in self._order if object_id in chosen]
        ordered.extend(sorted(chosen.difference(ordered)))
        return tuple(ordered)

    def selected_feature(self) -> str | None:
        items = self.tree.selectedItems()
        if len(items) != 1:
            # Bei mehreren Zeilen ist „das gewählte Merkmal" keine Frage mit
            # einer Antwort — dann gilt keines als gewählt.
            return None
        value: str | None = items[0].data(1, Qt.ItemDataRole.UserRole)
        return value

    def select_object(self, object_id: ObjectId) -> None:
        """Wählt einen Körper von außen aus — der Fehlerdialog tut das, wenn er
        zeigt, worum es ging."""
        self.tree.clearSelection()
        self._restore((object_id,), None)

    def select_feature(self, object_id: ObjectId, feature_id: str) -> None:
        """Folgt einem Klick im Viewport — die zwei Ansichten zeigen eine
        Auswahl (§18.5).
        """
        self.tree.clearSelection()
        self._restore((object_id,), feature_id)

    def _on_selection(self) -> None:
        self._remember_order()
        self.selectionChanged.emit(self.selected())
        self.featureSelected.emit(self.selected_feature())

    def _remember_order(self) -> None:
        """Führt mit, in welcher Reihenfolge angeklickt wurde.

        Qt gibt die Auswahl in Baumreihenfolge zurück, und die sagt nichts
        darüber, was zuerst gemeint war. Abgewähltes fällt heraus, Neues kommt
        hinten dazu.
        """
        current = {
            object_id
            for item in self.tree.selectedItems()
            if (object_id := item.data(0, Qt.ItemDataRole.UserRole)) is not None
        }
        self._order = [object_id for object_id in self._order if object_id in current]
        self._order.extend(sorted(current.difference(self._order)))

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
        chosen = self.selected_objects()
        if not chosen:
            return

        menu = QMenu(self)
        self._add_visibility(menu, chosen)

        kind = self._feature_kind()
        entries = self.operations_for_feature(kind) if kind else self.operations_for_object()
        if entries:
            menu.addSeparator()
            for spec in entries:
                action = menu.addAction(str(spec.title))
                action.triggered.connect(
                    lambda _checked=False, entry=spec: self.operationRequested.emit(entry)
                )
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _add_visibility(self, menu: QMenu, chosen: tuple[ObjectId, ...]) -> None:
        """Ein- und ausblenden und isolieren (§18.8).

        Keine Operationen: eine Ansichtsentscheidung gehört nicht in den
        Verlauf, sonst steht dort bald mehr Hin und Her als Arbeit. Zurück
        kommt sie über denselben Eintrag, nicht über ein Undo.
        """
        wants_hiding = any(object_id not in self._hidden for object_id in chosen)
        label = tr("Ausblenden") if wants_hiding else tr("Einblenden")
        hide = menu.addAction(label)
        hide.triggered.connect(
            lambda _checked=False: self.visibilityRequested.emit(chosen, not wants_hiding)
        )

        isolated = self._hidden and all(object_id not in self._hidden for object_id in chosen)
        isolate = menu.addAction(
            tr("Alles andere ausblenden") if not isolated else tr("Alle zeigen")
        )
        isolate.triggered.connect(lambda _checked=False: self.isolateRequested.emit(chosen))


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
        encoding = SEVERITY_ENCODING[finding.severity]
        item = QListWidgetItem(str(finding.message))
        # Die Form trägt den Schweregrad, die Farbe verstärkt ihn nur: ein
        # Dreieck bleibt ein Dreieck, auch wo die Farbe nicht ankommt.
        item.setIcon(
            icon(f"severity-{finding.severity}", self.list, colour=QColor(encoding.colour))
        )
        item.setData(Qt.ItemDataRole.UserRole, finding)
        item.setForeground(QColor(encoding.colour))
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
        self._unit: LengthUnit = "mm"
        self.clear_selection()

    def set_unit(self, unit: LengthUnit) -> None:
        """§19.3: die Anzeigeeinheit. Der Kern bleibt bei Millimetern."""
        self._unit = unit

    def clear_selection(self) -> None:
        self.setText(tr("Keine Auswahl"))

    def show_object(self, name: str, size: tuple[float, float, float], volume: float) -> None:
        self.setText(
            f"{name}   "
            f"{format_length(size[0], self._unit, with_unit=False)} × "
            f"{format_length(size[1], self._unit, with_unit=False)} × "
            f"{format_length(size[2], self._unit)}   "
            f"{format_volume(volume, self._unit)}"
        )


def collapsible(title: str, content: QWidget) -> QWidget:
    """Ein Abschnitt, der sich zuklappen lässt — §2.5 verlangt genau das.

    Er hieß so und war keiner: eine fette Überschrift über dem Inhalt, ohne
    Umschalter. Wer den Verlauf groß haben wollte, konnte die anderen beiden
    nicht wegklappen, und drei Abschnitte in einer schmalen Spalte teilen sich
    die Höhe, ob sie sie brauchen oder nicht.

    Der Umschalter ist ein Knopf mit dem Titel darauf, kein Zeichen daneben:
    die ganze Zeile ist damit die Fläche, die man trifft, und der gedrückte
    Zustand sagt ohne Farbe, ob offen oder zu ist (Regel 18).
    """
    wrapper = QWidget()
    heading = QToolButton(wrapper)
    heading.setText(title)
    heading.setCheckable(True)
    heading.setChecked(True)
    heading.setAutoRaise(True)
    heading.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    heading.setArrowType(Qt.ArrowType.DownArrow)
    heading.setStyleSheet("font-weight: 600; text-align: left;")
    heading.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def toggled(open_now: bool) -> None:
        content.setVisible(open_now)
        heading.setArrowType(Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow)

    heading.toggled.connect(toggled)

    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(heading)
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
