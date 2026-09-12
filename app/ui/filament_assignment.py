"""Schnelle ausdrückliche Spulenwahl an der Auswahl, ohne eigene Operation."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.errors import AppError
from app.core.export.threemf import slot_identity, slots_for_object
from app.core.geom.attributes import used_slots
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge import filaments
from app.core.types import SceneObject
from app.i18n import tr
from app.ui.filament_picker import hex_of, spool_label, spool_slot, swatch
from app.ui.style import TIGHT, set_level


class QuickFilamentPicker(QWidget):
    """Die Wahl meldet eine reale Spule; das Hauptfenster bestimmt den Op-Wirkungsbereich."""

    spoolChosen = Signal(object)
    inventoryRequested = Signal()
    clearRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._objects: list[SceneObject] = []
        self._selected_features: tuple[tuple[str, str], ...] = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scope = QLabel(self)
        self.scope.setWordWrap(True)
        set_level(self.scope, "caption")
        layout.addWidget(self.scope)
        self.picker = QComboBox(self)
        self.picker.setAccessibleName(tr("Filament für die Auswahl"))
        self.picker.setMinimumContentsLength(12)
        self.picker.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.picker.activated.connect(self._chosen)
        layout.addWidget(self.picker)
        self.notice = QLabel(self)
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.hide()
        layout.addWidget(self.notice)
        self.clear_button = QPushButton(tr("Filament entfernen"), self)
        self.clear_button.clicked.connect(self.clearRequested)
        layout.addWidget(self.clear_button)
        self.inventory_button = QPushButton(tr("Filamentlager öffnen"), self)
        self.inventory_button.clicked.connect(self.inventoryRequested)
        layout.addWidget(self.inventory_button)
        self.refresh()

    def set_context(
        self, objects: list[SceneObject], selected_features: tuple[tuple[str, str], ...] = ()
    ) -> None:
        """Gespeicherte Druckwerte anzeigen; aus Ähnlichkeit folgt keine physische Bindung."""
        self._objects = list(objects)
        self._selected_features = selected_features
        self.refresh()

    def refresh(self) -> None:
        """Neue Lagerwerte stehen sofort zur Wahl, die Szene bleibt dabei unverändert."""
        face_owners = {owner for owner, _feature in self._selected_features}
        occupied = {
            obj.id: set(used_slots(as_mesh_data(obj.mesh)))
            for obj in self._objects
            if obj.id not in face_owners
        }
        if not self._objects:
            current = tr("Körper wählen, um ein Filament zuzuweisen")
            scope = tr("Das Filamentlager ist auch ohne Auswahl erreichbar.")
        elif self._selected_features:
            current = tr("Filament für die gewählte Fläche wählen")
            owners = {owner for owner, _feature in self._selected_features}
            bodies = sum(obj.id not in owners for obj in self._objects)
            faces = len(self._selected_features)
            if bodies:
                current = tr("Filament für die Auswahl")
                scope = tr("Ganze Körper: {bodies}. Gewählte Flächen: {faces}.").format(
                    bodies=bodies, faces=faces
                )
            else:
                scope = (
                    tr("Die Zuweisung betrifft nur die gewählte Fläche.")
                    if faces == 1
                    else tr("Die Zuweisung betrifft {count} gewählte Flächen.").format(count=faces)
                )
        else:
            slots = []
            all_assigned = True
            for obj in self._objects:
                declared = {slot.index: slot for slot in slots_for_object(obj)}
                for index in occupied[obj.id]:
                    slot = declared.get(index)
                    if slot is None:
                        all_assigned = False
                    else:
                        slots.append(slot)
            keys = {slot_identity(slot) for slot in slots}
            if len(keys) == 1 and all_assigned:
                current = tr("Im Projekt: {filament}").format(filament=slots[0].name)
            elif not keys:
                current = tr("Noch kein Filament zugewiesen")
            else:
                current = tr("Mehrere Filamente in der Auswahl")
            scope = tr("Die Zuweisung betrifft {count} gewählte Körper.").format(
                count=len(self._objects)
            )
        self.scope.setText(scope)
        try:
            entries = filaments.catalogue()
        except AppError as problem:
            entries = ()
            self.notice.setText(str(problem))
            self.notice.show()
        else:
            self.notice.hide()
        with QSignalBlocker(self.picker):
            self.picker.clear()
            self.picker.addItem(current, "")
            if self._objects and not self._selected_features and len(keys) == 1 and all_assigned:
                self.picker.setItemIcon(0, swatch(hex_of(slots[0].colour)))
            self.picker.setToolTip(current)
            for entry in entries:
                label = spool_label(entry)
                self.picker.addItem(swatch(entry.colour), label, entry.identifier)
                row = self.picker.count() - 1
                self.picker.setItemData(row, label, Qt.ItemDataRole.ToolTipRole)
                self.picker.setItemData(row, label, Qt.ItemDataRole.AccessibleDescriptionRole)
                self.picker.setItemData(
                    row, slot_identity(spool_slot(entry)), int(Qt.ItemDataRole.UserRole) + 1
                )
            self.picker.setCurrentIndex(0)
        self.picker.setEnabled(bool(self._objects))
        removable = self._has_assigned_selection(occupied)
        self.clear_button.setEnabled(removable)
        explanation = (
            tr("Entfernt die Zuweisung in der angezeigten Auswahl. Strg+Z stellt sie wieder her.")
            if removable
            else tr("Wählen Sie einen Körper oder eine Fläche mit zugewiesenem Filament.")
        )
        self.clear_button.setToolTip(explanation)
        self.clear_button.setStatusTip(explanation)
        self.clear_button.setAccessibleDescription(explanation)

    def _has_assigned_selection(self, occupied: dict[str, set[int]]) -> bool:
        """Nur tatsächliche Zuweisungen im gewählten Wirkungsbereich lassen sich entfernen."""
        for body in self._objects:
            mesh = as_mesh_data(body.mesh)
            targets = [feature for owner, feature in self._selected_features if owner == body.id]
            if targets:
                if any(
                    feature not in body.features or not body.features[feature].face_indices
                    for feature in targets
                ):
                    continue
                indices = {
                    mesh.slots[face] if mesh.slots else 0
                    for feature in targets
                    for face in body.features[feature].face_indices
                }
            else:
                indices = occupied[body.id]
            if any(slot.index in indices for slot in slots_for_object(body)):
                return True
        return False

    def _chosen(self, index: int) -> None:
        """Nur eine ausdrückliche Wahl einer noch aktiven Spule wird weitergereicht."""
        identifier = str(self.picker.itemData(index) or "")
        if not identifier or not self._objects:
            return
        try:
            entry = filaments.get(identifier)
        except AppError as problem:
            self.notice.setText(str(problem))
            self.notice.show()
            return
        expected = self.picker.itemData(index, int(Qt.ItemDataRole.UserRole) + 1)
        if (
            entry is None
            or entry.archived
            or tuple(expected or ()) != slot_identity(spool_slot(entry))
        ):
            self.refresh()
            self.notice.setText(
                tr("Die Spule wurde inzwischen geändert. Wählen Sie sie erneut aus dem Lager.")
            )
            self.notice.show()
            return
        self.notice.hide()
        self.spoolChosen.emit(entry)
