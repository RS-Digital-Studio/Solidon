"""Schnelle ausdrückliche Spulenwahl an der Auswahl, ohne eigene Operation."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.export.threemf import slot_identity
from app.core.knowledge import filaments
from app.core.types import SceneObject
from app.i18n import tr
from app.ui.filament_picker import spool_label, swatch
from app.ui.style import TIGHT, set_level


class QuickFilamentPicker(QWidget):
    """Die Wahl meldet eine reale Spule; das Hauptfenster bestimmt den Op-Wirkungsbereich."""

    spoolChosen = Signal(object)
    inventoryRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._objects: list[SceneObject] = []
        self._has_feature = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
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
        self.inventory_button = QPushButton(tr("Filamentlager öffnen"), self)
        self.inventory_button.clicked.connect(self.inventoryRequested)
        layout.addWidget(self.inventory_button)
        self.refresh()

    def set_context(self, objects: list[SceneObject], has_feature: bool = False) -> None:
        """Gespeicherte Druckwerte anzeigen; aus Ähnlichkeit folgt keine physische Bindung."""
        self._objects = list(objects)
        self._has_feature = has_feature
        self.refresh()

    def refresh(self) -> None:
        """Neue Lagerwerte stehen sofort zur Wahl, die Szene bleibt dabei unverändert."""
        if not self._objects:
            current = tr("Körper wählen, um ein Filament zuzuweisen")
            scope = tr("Das Filamentlager ist auch ohne Auswahl erreichbar.")
        elif self._has_feature:
            current = tr("Filament für die gewählte Fläche wählen")
            scope = tr("Die Zuweisung betrifft nur die gewählte Fläche.")
        else:
            slots = [slot for obj in self._objects for slot in obj.material_slots]
            keys = {slot_identity(slot) for slot in slots}
            all_assigned = all(obj.material_slots for obj in self._objects)
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
        with QSignalBlocker(self.picker):
            self.picker.clear()
            self.picker.addItem(current, "")
            self.picker.setToolTip(current)
            for entry in filaments.catalogue():
                self.picker.addItem(swatch(entry.colour), spool_label(entry), entry.identifier)
            self.picker.setCurrentIndex(0)
        self.picker.setEnabled(bool(self._objects))

    def _chosen(self, index: int) -> None:
        """Nur eine ausdrückliche Wahl einer noch aktiven Spule wird weitergereicht."""
        identifier = str(self.picker.itemData(index) or "")
        if not identifier or not self._objects:
            return
        entry = filaments.get(identifier)
        if entry is None or entry.archived:
            self.refresh()
            return
        self.spoolChosen.emit(entry)
