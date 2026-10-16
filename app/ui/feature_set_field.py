"""Benannte Flächen wählen — die Merkmalsliste des Operationsdialogs.

Aus ``op_dialog.py`` gelöst (Codestruktur, Regel 6); ``op_dialog.FeatureSetField``
bleibt als Name. Die Liste heißt für den Bildschirmleser wie ihre Zeile
(FD-94): Sie stand als „Flächen auswählen“ auch unter *Merkmale* und *Zellen*,
und der Prüfstand fand dort nur den verborgenen Haken „Ganzer Körper“.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QListWidgetItem, QVBoxLayout, QWidget

from app.i18n import tr
from app.ui.feature_list import FeatureList
from app.ui.style import TIGHT, set_level
from app.ui.unlisted_choice import unlisted_text


class FeatureSetField(QWidget):
    """Benannte Flächen wählen; eine leere Zwischenwahl erweitert niemals den Auftrag.

    ``empty`` sagt, was eine leere Wahl bedeutet, und beschriftet den Haken
    dafür: am Filament der ganze Körper (die Vorgabe), an den Öffnungen des
    Aushöhlens keine Öffnung. ``None`` heißt, leer gibt es nicht — eine
    Pflichtliste wie die Quellen eines Merkmalsmusters (P6.7) hat keinen
    Haken, auch keinen verborgenen, und gültig ist sie erst mit einem
    markierten Merkmal. Ein Haken „Ganzer Körper" an einer Liste, deren Leere
    etwas anderes heißt, wäre ein Versprechen, das die Operation nicht hält.

    ``name`` ist der Name der Liste für den Bildschirmleser — die Beschriftung
    ihrer Zeile.
    """

    changed = Signal()
    validityChanged = Signal()

    def __init__(
        self,
        choices: Mapping[str, str],
        selected: Sequence[str],
        parent: QWidget | None = None,
        *,
        empty: str | None = "",
        hint: str = "",
        name: str = "",
    ) -> None:
        super().__init__(parent)
        self._last_value = tuple(dict.fromkeys(selected))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        self.whole: QCheckBox | None = None
        if empty is not None:
            self.whole = QCheckBox(empty or tr("Ganzer Körper"), self)
            self.whole.setChecked(not selected)
            layout.addWidget(self.whole)
        self.list = FeatureList(self)
        self.list.setAccessibleName(name or tr("Flächen auswählen"))
        for identifier in dict.fromkeys((*choices, *selected)):
            # Ein Wert ohne Eintrag heißt wie die Einträge, nicht „fillet_1“ (FD-187).
            shown = choices.get(identifier) or unlisted_text(identifier, "feature")
            item = QListWidgetItem(shown, self.list)
            item.setData(Qt.ItemDataRole.UserRole, identifier)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if identifier in selected else Qt.CheckState.Unchecked
            )
        layout.addWidget(self.list)
        self.hint = QLabel(hint or tr("Flächen markieren oder den ganzen Körper wählen."), self)
        self.hint.setWordWrap(True)
        set_level(self.hint, "caption")
        layout.addWidget(self.hint)
        self.list.setEnabled(not self._whole_chosen())
        self.setFocusProxy(self.list)
        if self.whole is not None:
            self.whole.toggled.connect(self._changed)
        self.list.itemChanged.connect(self._changed)

    def _whole_chosen(self) -> bool:
        """Ob der Haken für die leere Wahl steht — ohne Haken nie."""
        return self.whole is not None and self.whole.isChecked()

    def _selected(self) -> tuple[str, ...]:
        return tuple(
            str(self.list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.list.count())
            if self.list.item(row).checkState() == Qt.CheckState.Checked
        )

    @property
    def valid(self) -> bool:
        """Keine markierte Fläche bedeutet nur mit ausdrücklichem Haken den ganzen Körper."""
        return self._whole_chosen() or bool(self._selected())

    def value(self) -> list[str]:
        """Während einer unvollständigen Wahl bleibt die letzte gültige Vorschau erhalten."""
        return list(self._last_value)

    def _changed(self, *_args: object) -> None:
        self.list.setEnabled(not self._whole_chosen())
        self.validityChanged.emit()
        if self.valid:
            self._last_value = () if self._whole_chosen() else self._selected()
            self.changed.emit()

    def add_feature(self, identifier: str, label: str) -> None:
        """Ein Klick im Modell ergänzt die Auswahl statt die vorige Fläche zu ersetzen."""
        with QSignalBlocker(self.list):
            item = next(
                (
                    self.list.item(row)
                    for row in range(self.list.count())
                    if self.list.item(row).data(Qt.ItemDataRole.UserRole) == identifier
                ),
                None,
            )
            if item is None:
                item = QListWidgetItem(label or unlisted_text(identifier, "feature"), self.list)
                item.setData(Qt.ItemDataRole.UserRole, identifier)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if self.whole is not None:
                with QSignalBlocker(self.whole):
                    self.whole.setChecked(False)
            item.setCheckState(Qt.CheckState.Checked)
        self._changed()
