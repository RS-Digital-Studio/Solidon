"""Fachaufteilung bearbeiten und den identischen Organizer im Arbeiter ansehen (§19)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, cast

from PySide6.QtCore import QByteArray, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QMouseEvent, QPainterPath, QPen, QResizeEvent
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import drawing, expressions
from app.core.errors import AppError, InternalError, OperationCancelled
from app.core.organizer.build import OrganizerBuild, build_organizer
from app.core.organizer.layout import Cell, OrganizerLayout, Wall, resolve_layout
from app.core.organizer.ops import DEFAULT_LAYOUT, OrganizerParams
from app.core.organizer.serialize import (
    MAX_COUNT,
    LayoutSpec,
    Node,
    grid_layout,
    invalid,
    layout_from_text,
    layout_to_text,
)
from app.core.scene.cancel import CancelSignal
from app.core.types import ParamSpec
from app.i18n import tr
from app.ui.dialogs import ErrorNotice
from app.ui.labels import length
from app.ui.leash import DIALOG_WAIT_MS, WAIT_TIMEOUT_MS, Worker, WorkerLeash, weak_slot
from app.ui.style import ROOMY, make_primary, no_primary
from app.ui.theme import Theme, current_theme

if TYPE_CHECKING:
    from app.ui.op_dialog import ValueField


class OrganizerLayoutField(QWidget):
    """Eine lesbare Zusammenfassung mit Editorzugang; niemals roher JSON-Text."""

    valueChanged = Signal()
    validityChanged = Signal()
    choiceRequested = Signal()

    def __init__(self, start: Any = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = ""
        self.valid = False
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.button = QPushButton(tr("Fächer aufteilen …"), self)
        self.button.clicked.connect(self.choiceRequested)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.summary, 1)
        row.addWidget(self.button)
        self.setFocusProxy(self.button)
        self.setAccessibleName(tr("Fachaufteilung"))
        self.set_value(start)

    def value(self) -> str:
        return self._value

    def set_value(self, value: Any) -> None:
        self._value = str(value) if value is not None else ""
        try:
            spec = layout_from_text(self._value)
        except AppError:
            self.valid = False
            text = tr("Wählen Sie eine gültige Fachaufteilung.")
        else:
            self.valid = True
            text = (
                tr("Fachaufteilung nach Außenmaß")
                if spec.basis == "outer"
                else tr("Fachaufteilung nach lichten Maßen")
            )
        self.summary.setText(text)
        self.setAccessibleDescription(text)
        self.valueChanged.emit()
        self.validityChanged.emit()


class _BuildWorker(Worker):
    ready = Signal(int, object, object, str)
    failed = Signal(int, object)

    def __init__(
        self,
        values: dict[str, Any],
        parameters: Mapping[str, float],
        revision: int,
        theme: Theme,
        *,
        selection: tuple[str, str] = ("", ""),
        label: str = "",
        previous: tuple[dict[str, Any], OrganizerLayout, OrganizerBuild] | None = None,
    ) -> None:
        super().__init__()
        self.values, self.parameters, self.revision, self.theme = (
            values,
            dict(parameters),
            revision,
            theme,
        )
        self.cancelled = CancelSignal()
        self.selection, self.label, self.previous = selection, label, previous

    def work(self) -> None:
        try:
            self.cancelled.raise_if_cancelled()
            try:
                dimensions = {
                    name: float(
                        cast(
                            float | str,
                            expressions.resolve_value(self.values[name], self.parameters),
                        )
                    )
                    for name in ("width", "depth", "height", "wall", "floor", "radius")
                }
            except (ValueError, TypeError, OverflowError) as error:
                raise invalid(tr("Ein Außenmaß ist ungültig. Korrigieren Sie das Maß.")) from error
            if self.previous is not None and self.previous[0] == self.values:
                _, layout, built = self.previous
            else:
                layout = resolve_layout(
                    layout_from_text(self.values["layout"]), self.parameters, **dimensions
                )
                built = build_organizer(layout, cancelled=self.cancelled)
            self.cancelled.raise_if_cancelled()
            kind, identifier = self.selection
            indices = tuple(
                sorted(
                    {
                        index
                        for feature in built.features.values()
                        if (kind == "wall" and feature.params.get("organizer_id") == identifier)
                        or (
                            kind == "node"
                            and identifier in str(feature.params.get("organizer_id", "")).split("/")
                        )
                        for index in feature.face_indices
                    }
                )
            )
            svg = drawing.project(
                built.mesh.raw,
                512,
                theme=self.theme,
                edges=True,
                highlight_faces=indices,
                highlight_label=self.label,
            )
            self.cancelled.raise_if_cancelled()
            self.ready.emit(self.revision, layout, built, svg)
        except OperationCancelled:
            return
        except AppError as error:
            self.failed.emit(self.revision, error.with_traceback(None))


class _LayoutView(QGraphicsView):
    chosen = Signal(str, str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(QGraphicsScene(parent), parent)
        self.setMinimumSize(250, 240)
        self.setAccessibleName(tr("Fächer und Trennwände in der Draufsicht"))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt
        super().resizeEvent(event)
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item is not None and item.data(0):
                kind, identifier = item.data(0)
                self.chosen.emit(kind, identifier)
                event.accept()
                return
        super().mousePressEvent(event)


class OrganizerDialog(QDialog):
    """Maße und Teilungsbaum sammeln; erst der Besitzer übernimmt eine Operation."""

    valuesChanged = Signal()

    def __init__(
        self,
        values: Mapping[str, Any],
        parameters: Mapping[str, float] | None = None,
        parent: QWidget | None = None,
        *,
        layout_only: bool = False,
    ) -> None:
        super().__init__(parent)
        from app.ui.op_dialog import ValueField

        self.setWindowTitle(tr("Organizer aufteilen"))
        self.resize(1120, 760)
        self._initial = {**OrganizerParams().as_dict(), **dict(values)}
        self._layout_only = layout_only
        self._basis_before: tuple[float, float] | None = None
        self._parameters = dict(parameters or {})
        self._layout_text = str(self._initial.get("layout", DEFAULT_LAYOUT))
        try:
            self._spec: LayoutSpec | None = layout_from_text(self._layout_text)
        except AppError:
            self._spec = None
        self._fields: dict[str, ValueField] = {}
        self._edit_fields: dict[str, ValueField] = {}
        self._closed = False
        self._pending = False
        self._revision = 0
        self._ready_revision = -1
        self._worker: _BuildWorker | None = None
        self._leash = WorkerLeash(self)
        self._selected = ("", "")
        self._nodes: dict[str, Node] = {}
        self._tree_items: dict[str, QTreeWidgetItem] = {}
        self._layout: OrganizerLayout | None = None
        self.result_preview: OrganizerBuild | None = None
        self._ready_values: dict[str, Any] | None = None
        self._preview_svg = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._preview)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        header = QLabel(
            tr(
                "Wählen Sie ein Fach oder eine Trennwand. Die Vorschau zeigt "
                "den berechneten Körper."
            ),
            self,
        )
        header.setWordWrap(True)
        layout.addWidget(header)
        dimensions = QHBoxLayout()
        first, second = QFormLayout(), QFormLayout()
        for index, entry in enumerate(
            e
            for e in OrganizerParams.spec()
            if e.name in ("width", "depth", "height", "wall", "floor", "radius")
        ):
            field = ValueField(entry, self._initial[entry.name], self._parameters, self)
            field.setEnabled(not layout_only)
            field.changed.connect(self._changed)
            (first if index < 3 else second).addRow(str(entry.title), field)
            self._fields[entry.name] = field
        dimensions.addLayout(first, 1)
        dimensions.addLayout(second, 1)
        layout.addLayout(dimensions)
        if layout_only:
            hint = QLabel(
                tr(
                    "Die Außenmaße bleiben im Operationsdialog. Hier ändern "
                    "Sie nur die Fachaufteilung."
                ),
                self,
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)
        controls = QHBoxLayout()
        self.basis = QComboBox(self)
        self.basis.addItem(tr("Außenmaße festhalten"), userData="outer")
        self.basis.addItem(tr("Lichte Fachmaße festhalten"), userData="inner")
        self.basis.setCurrentIndex(
            1 if self._spec is not None and self._spec.basis == "inner" else 0
        )
        self.basis.setToolTip(
            tr("Ein Bezugwechsel übernimmt die aktuell sichtbaren lichten Fachmaße.")
        )
        self.basis.currentIndexChanged.connect(self._basis_changed)
        controls.addWidget(self.basis)
        self.new_grid = QPushButton(tr("Neues Raster"), self)
        self.new_grid.clicked.connect(self._new_grid)
        controls.addWidget(self.new_grid)
        controls.addStretch()
        self.name_field = QLineEdit(str(self._initial.get("name", "")), self)
        self.name_field.setPlaceholderText(tr("Organizer"))
        self.name_field.setAccessibleName(tr("Name"))
        self.name_field.setEnabled(not layout_only)
        controls.addWidget(self.name_field)
        layout.addLayout(controls)
        self.basis_notice = QLabel(self)
        self.basis_notice.setWordWrap(True)
        self.basis_notice.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.basis_notice)

        middle = QSplitter(Qt.Orientation.Horizontal, self)
        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        self.tree = QTreeWidget(left)
        self.tree.setHeaderLabel(tr("Aufteilung"))
        self.tree.setAccessibleName(tr("Fächer und Teilungen"))
        self.tree.setMinimumWidth(215)
        self.tree.currentItemChanged.connect(self._tree_chosen)
        left_layout.addWidget(self.tree, 1)
        self.selection = QLabel(tr("Wählen Sie ein Fach oder eine Wand."), left)
        self.selection.setWordWrap(True)
        left_layout.addWidget(self.selection)
        scroll = QScrollArea(left)
        scroll.setWidgetResizable(True)
        self.editor = QWidget(scroll)
        self.editor_form = QFormLayout(self.editor)
        scroll.setWidget(self.editor)
        left_layout.addWidget(scroll, 1)
        middle.addWidget(left)
        image_column = QWidget(self)
        image_layout = QVBoxLayout(image_column)
        image_layout.addWidget(QLabel(tr("Draufsicht · Fach oder Wand anklicken"), self))
        self.layout_view = _LayoutView(self)
        self.layout_view.chosen.connect(self._graphic_chosen)
        image_layout.addWidget(self.layout_view, 1)
        middle.addWidget(image_column)
        preview_column = QWidget(self)
        preview_layout = QVBoxLayout(preview_column)
        preview_layout.addWidget(QLabel(tr("So sieht Ihr Teil aus"), self))
        self.preview = QSvgWidget(self)
        self.preview.setAccessibleName(tr("Ergebnisvorschau"))
        self.preview.setMinimumSize(260, 240)
        preview_layout.addWidget(self.preview, 1)
        self.measurement = QLabel(self)
        self.measurement.setWordWrap(True)
        preview_layout.addWidget(self.measurement)
        middle.addWidget(preview_column)
        middle.setSizes([300, 330, 350])
        layout.addWidget(middle, 1)
        self.state = ErrorNotice(self)
        layout.addWidget(self.state)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.accept_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.accept_button.setText(
            tr("Aufteilung übernehmen") if layout_only else tr("Organizer anlegen")
        )
        self.accept_button.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Abbrechen"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        no_primary(self)
        make_primary(self.accept_button)
        self._rebuild_tree()
        self._changed()

    def values(self) -> dict[str, Any]:
        return {
            **{name: field.value() for name, field in self._fields.items()},
            "layout": self._layout_text,
            "name": self.name_field.text(),
        }

    def _rebuild_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        self._nodes.clear()
        self._tree_items.clear()

        def add(node: Node, parent: QTreeWidgetItem | None) -> None:
            text = (
                tr("Fach")
                if node.kind == "cell"
                else (tr("Raster längs") if node.axis == "x" else tr("Raster quer"))
                if node.kind == "repeat"
                else (tr("Teilung längs") if node.axis == "x" else tr("Teilung quer"))
            )
            item = QTreeWidgetItem([text])
            item.setData(0, Qt.ItemDataRole.UserRole, node.id)
            (parent.addChild(item) if parent is not None else self.tree.addTopLevelItem(item))
            self._nodes[node.id] = node
            self._tree_items[node.id] = item
            for child in node.children:
                add(child, item)

        if self._spec is not None:
            add(self._spec.root, None)
        self.tree.expandAll()
        self.tree.blockSignals(False)
        if self._nodes:
            self.tree.setCurrentItem(
                self._tree_items.get(self._selected[1], next(iter(self._tree_items.values())))
            )

    def _tree_chosen(self, item: QTreeWidgetItem | None, _old: QTreeWidgetItem | None) -> None:
        if item is not None:
            self._show_node(str(item.data(0, Qt.ItemDataRole.UserRole)))

    def _clear_editor(self) -> None:
        while self.editor_form.rowCount():
            self.editor_form.removeRow(0)
        self._edit_fields.clear()

    def _edit_field(
        self,
        name: str,
        title: str,
        value: Any,
        setter: Callable[[Any], None],
        *,
        count: bool = False,
        zero: bool = False,
    ) -> None:
        from app.ui.op_dialog import ValueField

        entry = ParamSpec(
            name=name,
            kind="int" if count else "float",
            title=title,
            minimum=0 if zero else 1,
            maximum=MAX_COUNT if count else 2000,
            unit=None if count else "mm",
        )
        field = ValueField(entry, value, self._parameters, self.editor)
        field.changed.connect(lambda: setter(field.value()))
        self.editor_form.addRow(title, field)
        self._edit_fields[name] = field

    def _show_node(self, identifier: str) -> None:
        node = self._nodes.get(identifier)
        if node is None:
            return
        previous = self._selected
        self._selected = ("node", identifier)
        self._clear_editor()
        affected = (
            sum(
                cell.id.endswith("/" + identifier) or cell.id == identifier
                for cell in self._layout.cells
            )
            if self._layout is not None
            else 0
        )
        self.selection.setText(
            tr("Ausgewählt: Fachvorlage für {count} Fächer").format(count=affected)
            if node.kind == "cell"
            else tr("Ausgewählt: Teilung der Fachgruppe")
        )
        if node.kind == "cell":
            for name, title in (
                ("width", tr("Lichte Breite")),
                ("depth", tr("Lichte Tiefe")),
                ("radius", tr("Innenradius")),
            ):
                self._edit_field(
                    name,
                    title,
                    getattr(node, name),
                    partial(self._set_node_value, identifier, name),
                    zero=name == "radius",
                )
            for axis, title in (("x", tr("Längs teilen")), ("y", tr("Quer teilen"))):
                button = QPushButton(title, self.editor)
                button.clicked.connect(
                    lambda _checked=False, direction=axis: self._split_node(identifier, direction)
                )
                self.editor_form.addRow(button)
        else:
            self._edit_field(
                "wall",
                tr("Trennwanddicke"),
                node.wall,
                lambda value: self._set_node_value(identifier, "wall", value),
            )
            self._edit_field(
                "opening_radius",
                tr("Radius der Freistellung"),
                node.opening_radius,
                lambda value: self._set_node_value(identifier, "opening_radius", value),
                zero=True,
            )
            if node.kind == "repeat":
                self._edit_field(
                    "count",
                    tr("Anzahl"),
                    node.count,
                    lambda value: self._set_node_value(identifier, "count", value),
                    count=True,
                )
        self._paint_layout()
        if previous != self._selected:
            self._changed()

    def _set_node_value(self, identifier: str, name: str, value: Any) -> None:
        if self._spec is None:
            return

        def change(node: Node) -> Node:
            if node.id == identifier:
                return replace(node, **{name: value})
            return replace(node, children=tuple(change(child) for child in node.children))

        self._spec = replace(self._spec, root=change(self._spec.root))
        self._nodes[identifier] = replace(self._nodes[identifier], **{name: value})
        self._store_layout()

    def _split_node(self, identifier: str, axis: Literal["x", "y"]) -> None:
        if self._spec is None or identifier not in self._nodes:
            return
        node = self._nodes[identifier]
        occupied = set(self._nodes)

        def fresh() -> str:
            for index in range(1, 1025):
                candidate = f"cell_{index}"
                if candidate not in occupied:
                    occupied.add(candidate)
                    return candidate
            raise invalid(tr("Die Fachaufteilung ist zu groß. Entfernen Sie eine Teilung."))

        wall = self._fields["wall"].value()
        if wall is None:
            return
        name = "width" if axis == "x" else "depth"
        raw = getattr(node, name)
        # Eine Teilung ist eine Parameteränderung. Die bestehende Ausdruckssprache
        # hält dabei auch die Bindung des lichten Ausgangsmaßes lebendig.
        dimension = str(raw)[1:] if expressions.is_expression(raw) else str(raw)
        thickness = str(wall)[1:] if expressions.is_expression(wall) else str(wall)
        divided_value = f"=({dimension}-({thickness}))/2"
        divided = (
            replace(node, width=divided_value)
            if axis == "x"
            else replace(node, depth=divided_value)
        )
        children = (replace(divided, id=fresh()), replace(divided, id=fresh()))
        replacement = Node("split", identifier, axis=axis, wall=wall, children=children)

        def change(current: Node) -> Node:
            return (
                replacement
                if current.id == identifier
                else replace(current, children=tuple(change(child) for child in current.children))
            )

        self._spec = replace(self._spec, root=change(self._spec.root))
        self._store_layout()
        self._rebuild_tree()

    def _graphic_chosen(self, kind: str, identifier: str) -> None:
        if kind == "cell":
            node_id = identifier.rsplit("/", 1)[-1]
            if node_id in self._tree_items:
                self.tree.setCurrentItem(self._tree_items[node_id])
                self._show_node(node_id)
            return
        if self._layout is None or self._spec is None:
            return
        wall = next((entry for entry in self._layout.walls if entry.id == identifier), None)
        if wall is None:
            return
        previous = self._selected
        self._selected = ("wall", identifier)
        self.tree.clearSelection()
        self.tree.setCurrentIndex(QModelIndex())
        self._clear_editor()
        number = self._layout.walls.index(wall) + 1
        self.selection.setText(tr("Ausgewählt: Trennwand {number}").format(number=number))
        value = dict(self._spec.wall_heights).get(identifier, wall.height)
        self._edit_field(
            "height",
            tr("Höhe ab Unterseite"),
            value,
            lambda entered: self._set_wall_height(identifier, entered),
        )
        self._paint_layout()
        if previous != self._selected:
            self._changed()

    def _set_wall_height(self, identifier: str, value: Any) -> None:
        if self._spec is not None:
            heights = dict(self._spec.wall_heights)
            heights[identifier] = value
            self._spec = replace(self._spec, wall_heights=tuple(sorted(heights.items())))
            self._store_layout()

    def _store_layout(self) -> None:
        if self._spec is not None:
            self._layout_text = layout_to_text(self._spec)
        self._changed()

    def _new_grid(self) -> None:
        self._spec = grid_layout()
        self.basis.blockSignals(True)
        self.basis.setCurrentIndex(0)
        self.basis.blockSignals(False)
        self._selected = ("", "")
        self._store_layout()
        self._rebuild_tree()

    def _basis_changed(self, _index: int) -> None:
        if self._spec is None:
            return
        if self._layout is None or self._ready_revision != self._revision:
            self.basis.blockSignals(True)
            self.basis.setCurrentIndex(1 if self._spec.basis == "inner" else 0)
            self.basis.blockSignals(False)
            return
        self._basis_before = (self._layout.width, self._layout.depth)
        if self.basis.currentData() == "outer" and not self._layout_only:
            for name, current in zip(("width", "depth"), self._basis_before, strict=True):
                field = self._fields[name]
                if not expressions.is_expression(field.value()):
                    field.set_value(current)
        by_id = {cell.id.rsplit("/", 1)[-1]: cell for cell in self._layout.cells}

        def measured(node: Node) -> Node:
            if node.kind == "cell" and node.id in by_id:
                return replace(
                    node, width=by_id[node.id].rect.width, depth=by_id[node.id].rect.depth
                )
            return replace(node, children=tuple(measured(child) for child in node.children))

        self._spec = replace(
            self._spec, basis=self.basis.currentData(), root=measured(self._spec.root)
        )
        self._store_layout()
        self._rebuild_tree()

    def _changed(self) -> None:
        if self._closed:
            return
        self._revision += 1
        self._pending = True
        self.accept_button.setEnabled(False)
        self.state.setText(tr("Vorschau wird berechnet …"))
        if self._worker is not None:
            self._worker.cancelled.cancel()
        self._timer.start()
        self.valuesChanged.emit()

    def _preview(self) -> None:
        if self._closed or not self._pending or self._worker is not None:
            return
        self._pending = False
        previous = (
            (self._ready_values, self._layout, self.result_preview)
            if self._ready_values is not None
            and self._layout is not None
            and self.result_preview is not None
            else None
        )
        worker = _BuildWorker(
            self.values(),
            self._parameters,
            self._revision,
            current_theme(),
            selection=self._selected,
            label=self.selection.text(),
            previous=previous,
        )
        worker.ready.connect(self._ready)
        worker.failed.connect(self._failed)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(self._finished)
        self._worker = worker
        self._leash.start(worker)

    def _ready(
        self, revision: int, layout: OrganizerLayout, built: OrganizerBuild, svg: str
    ) -> None:
        if self._closed or revision != self._revision:
            return
        self._layout, self.result_preview = layout, built
        self._ready_values = self.values()
        self._preview_svg = svg
        self._ready_revision = revision
        self.preview.load(QByteArray(svg.encode("utf-8")))
        self.measurement.setText(
            tr("{width} × {depth} × {height} · {count} Fächer").format(
                width=length(layout.width),
                depth=length(layout.depth),
                height=length(layout.height),
                count=len(layout.cells),
            )
        )
        self.state.setText(tr("Die Vorschau zeigt das Ergebnis."))
        if self._basis_before is not None:
            previous = self._basis_before
            self.basis_notice.setText(
                tr(
                    "Maßbezug geändert: vorher {before_width} × {before_depth}, jetzt "
                    "{width} × {depth}. Gebundene Außenmaße bleiben unverändert."
                ).format(
                    before_width=length(previous[0]),
                    before_depth=length(previous[1]),
                    width=length(layout.width),
                    depth=length(layout.depth),
                )
            )
        if layout.inactive_heights:
            self.state.setText(
                tr(
                    "{count} gespeicherte Wandhöhen gehören zu derzeit nicht "
                    "vorhandenen Fächern. Beim Vergrößern werden sie wieder verwendet."
                ).format(count=len(layout.inactive_heights))
            )
        self.accept_button.setEnabled(True)
        if self._selected[0] == "node":
            node = self._nodes.get(self._selected[1])
            if node is not None and node.kind == "cell":
                affected = sum(node.id in cell.id.split("/") for cell in layout.cells)
                self.selection.setText(
                    tr("Ausgewählt: Fachvorlage für {count} Fächer").format(count=affected)
                )
        self._paint_layout()

    def _paint_layout(self) -> None:
        if self._layout is None:
            return
        scene = self.layout_view.scene()
        scene.clear()
        selected_kind, selected_id = self._selected
        groups: tuple[tuple[str, tuple[Cell | Wall, ...]], ...] = (
            ("cell", self._layout.cells),
            ("wall", self._layout.walls),
        )
        for kind, entries in groups:
            for number, entry in enumerate(entries, 1):
                rect = entry.rect
                chosen = (selected_kind == "wall" and selected_id == entry.id) or (
                    kind == "cell"
                    and selected_kind == "node"
                    and selected_id in entry.id.split("/")
                )
                pen = QPen(
                    self.palette().highlight().color() if chosen else self.palette().text().color()
                )
                pen.setCosmetic(True)
                pen.setWidth(3 if chosen else 1)
                path = QPainterPath()
                path.addRoundedRect(
                    rect.x, -rect.y - rect.depth, rect.width, rect.depth, entry.radius, entry.radius
                )
                shape = scene.addPath(
                    path,
                    pen,
                    self.palette().highlight() if chosen else QBrush(Qt.BrushStyle.NoBrush),
                )
                shape.setData(0, (kind, entry.id))
                text = (
                    tr("Fach {number}").format(number=number)
                    if kind == "cell"
                    else tr("Wand {number}").format(number=number)
                )
                shape.setToolTip(text)
                label = scene.addSimpleText(
                    str(number) if kind == "cell" else tr("W{number}").format(number=number)
                )
                label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                label.setPos(rect.centre[0], -rect.centre[1])
                label.setBrush(
                    self.palette().highlightedText() if chosen else self.palette().text()
                )
                label.setData(0, (kind, entry.id))
                label.setZValue(2 if kind == "cell" else 3)
        scene.setSceneRect(scene.itemsBoundingRect())
        self.layout_view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _failed(self, revision: int, problem: object) -> None:
        if not self._closed and revision == self._revision:
            self.accept_button.setEnabled(False)
            self.state.set_error(
                problem, {"correct_input": weak_slot(self.tree, QTreeWidget.setFocus)}
            )

    def _crashed(self, detail: str) -> None:
        worker = self.sender()
        if isinstance(worker, _BuildWorker):
            self._failed(worker.revision, InternalError(detail=detail))

    def _finished(self) -> None:
        if self.sender() is self._worker:
            self._worker = None
        if not self._closed and self._pending:
            self._timer.start()

    def accept(self) -> None:
        if (
            not self._closed
            and self._ready_revision == self._revision
            and self.accept_button.isEnabled()
        ):
            super().accept()

    def done(self, result: int) -> None:
        self.release(DIALOG_WAIT_MS)
        super().done(result)

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        self._closed = True
        self._timer.stop()
        if self._worker is not None:
            self._worker.cancelled.cancel()
        self._leash.wait_all(timeout_ms)
