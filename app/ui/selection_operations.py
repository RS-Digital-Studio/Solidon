"""Kontextsensitive Körperoperationen unter Prüfbericht und Chat.

Die Liste entsteht einmal aus dem Operationsregister. Auswahlwechsel ändern
nur Sichtbarkeit, Freigabe und Hinweise der vorhandenen Knöpfe; bei großen
Registern wird weder ein Modell noch ein Qt-Baum neu gebaut.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import (
    MENU_TWINS,
    OperationSpec,
    catalogue_operations,
    caveat_line,
    group_title,
)
from app.i18n import tr
from app.ui.icons import icon, icon_name_for
from app.ui.leash import weak_slot
from app.ui.style import NORMAL, TARGET_SIZE, TIGHT, set_level

QUICK_OPERATIONS = ("union_objects", "subtract_objects", "intersect_objects")
"""Die drei Handlungen, wegen derer die Auswahlfläche zuerst gebraucht wird."""

_SEPARATE_CATEGORIES = frozenset({"holes", "parts"})


def body_operations(specs: Iterable[OperationSpec]) -> tuple[OperationSpec, ...]:
    """Körperoperationen, ohne die getrennten Merkmals- und Bausteinwege.

    Versteckte Rechenkern-Zwillinge sind keine zweite Handlung. Erzeuger ohne
    Eingang gehören ebenfalls nicht an eine Auswahl; sie bleiben im Menü und
    in der Befehlspalette.
    """
    catalogue = catalogue_operations()
    return tuple(
        spec
        for spec in specs
        if (spec.consumes != 0 or spec.takes_whole_scene)
        and spec.name not in MENU_TWINS
        and spec.name not in catalogue
        and spec.category not in _SEPARATE_CATEGORIES
        and not spec.applies_to
    )


class SelectionOperationsPanel(QWidget):
    """Alle Handlungen für die aktuelle Körperauswahl, dauerhaft aufgebaut."""

    operationRequested = Signal(object)
    catalogRequested = Signal()
    featurePanelRequested = Signal()

    def __init__(self, specs: Iterable[OperationSpec], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("selectionOperations")
        self.setAccessibleName(tr("Operationen für die Auswahl"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Drei Hauptaktionen, Suche, Trefferliste und die beiden getrennten
        # Wege dürfen sich auch in einem 720-Pixel-Fenster nicht überlagern.
        # Mit der früheren 190-Pixel-Untergrenze drückte Qt jede Hauptaktion
        # auf rund 15 Pixel und legte das Suchfeld über „Schnittmenge“.
        self.setMinimumHeight(280)
        self.setMaximumHeight(420)

        operations = body_operations(specs)
        by_name = {spec.name: spec for spec in operations}
        self._buttons: dict[str, QToolButton] = {}
        self._groups: dict[str, tuple[QLabel, tuple[QToolButton, ...]]] = {}
        self._states: dict[str, tuple[bool, str]] = {}

        self.summary = QLabel("", self)
        set_level(self.summary, "section")
        self.summary.setAccessibleName(tr("Aktuelle Auswahl"))

        quick = QGridLayout()
        quick.setContentsMargins(0, 0, 0, 0)
        quick.setHorizontalSpacing(TIGHT)
        quick.setVerticalSpacing(TIGHT)
        for index, name in enumerate(QUICK_OPERATIONS):
            spec = by_name.get(name)
            if spec is None:
                continue
            button = self._operation_button(spec)
            button.setObjectName("quickOperation")
            # Zwei kurze Hauptaktionen teilen die erste Zeile, die längere
            # Schnittmenge bekommt die zweite allein. Das spart dem Bericht
            # auf 720 Pixel Höhe eine volle Zeile, ohne einen Titel zu kürzen.
            if index < 2:
                quick.addWidget(button, 0, index)
            else:
                quick.addWidget(button, 1, 0, 1, 2)
        quick.setColumnStretch(0, 1)
        quick.setColumnStretch(1, 1)

        self.search = QLineEdit(self)
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(TARGET_SIZE)
        self.search.setPlaceholderText(tr("Weitere Operationen durchsuchen"))
        self.search.setAccessibleName(tr("Körperoperationen durchsuchen"))
        self.search.textChanged.connect(self._filter)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(TIGHT)

        grouped: dict[str, list[OperationSpec]] = {}
        for spec in operations:
            if spec.name in QUICK_OPERATIONS:
                continue
            grouped.setdefault(str(group_title(spec.category)), []).append(spec)
        for title in sorted(grouped, key=str.casefold):
            heading = QLabel(title, content)
            set_level(heading, "caption")
            content_layout.addWidget(heading)
            buttons: list[QToolButton] = []
            for spec in sorted(grouped[title], key=lambda entry: str(entry.title).casefold()):
                button = self._operation_button(spec, content)
                content_layout.addWidget(button)
                buttons.append(button)
            self._groups[title] = (heading, tuple(buttons))
        content_layout.addStretch(1)

        self.scroller = QScrollArea(self)
        self.scroller.setWidget(content)
        self.scroller.setWidgetResizable(True)
        self.scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroller.setMinimumHeight(TARGET_SIZE)
        self.scroller.setAccessibleName(tr("Passende Körperoperationen"))

        self.feature_button = QToolButton(self)
        self.feature_button.setText(tr("Merkmale"))
        self.feature_button.setIcon(icon("category.holes", self.feature_button))
        self.feature_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.feature_button.setMinimumHeight(TARGET_SIZE)
        self.feature_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.feature_button.clicked.connect(self.featurePanelRequested)

        self.catalog_button = QToolButton(self)
        self.catalog_button.setText(tr("Bausteine"))
        self.catalog_button.setIcon(icon("category.parts", self.catalog_button))
        self.catalog_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.catalog_button.setMinimumHeight(TARGET_SIZE)
        self.catalog_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.catalog_button.setToolTip(
            tr("Öffnet den vollständigen Bausteinkatalog mit Bildern und Suche.")
        )
        self.catalog_button.setStatusTip(self.catalog_button.toolTip())
        self.catalog_button.setAccessibleDescription(self.catalog_button.toolTip())
        self.catalog_button.clicked.connect(self.catalogRequested)

        separate = QHBoxLayout()
        separate.setContentsMargins(0, 0, 0, 0)
        separate.setSpacing(TIGHT)
        separate.addWidget(self.feature_button)
        separate.addWidget(self.catalog_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, NORMAL)
        layout.setSpacing(TIGHT)
        layout.addWidget(self.summary)
        layout.addLayout(quick)
        layout.addWidget(self.search)
        layout.addWidget(self.scroller, 1)
        layout.addLayout(separate)
        self.hide()

    def _operation_button(self, spec: OperationSpec, parent: QWidget | None = None) -> QToolButton:
        """Einen Registereintrag als direkte, tastaturfähige Handlung bauen."""
        button = QToolButton(parent or self)
        button.setText(str(spec.title))
        button.setIcon(icon(icon_name_for(spec), button))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(TARGET_SIZE)
        warning = caveat_line(spec)
        tip = f"{spec.doc}\n\n{warning}" if warning else str(spec.doc)
        button.setToolTip(tip)
        button.setStatusTip(str(spec.doc))
        button.setAccessibleDescription(tip)
        button.clicked.connect(weak_slot(self, SelectionOperationsPanel._request_operation, spec))
        button.setProperty("operationName", spec.name)
        self._buttons[spec.name] = button
        return button

    def _request_operation(self, spec: OperationSpec) -> None:
        """Den Registereintrag ohne dauerhafte Lambda-Rückbindung weiterreichen."""
        self.operationRequested.emit(spec)

    def set_context(
        self,
        selected: int,
        availability: Callable[[str], tuple[bool, str]],
        *,
        feature_chosen: bool,
    ) -> None:
        """Auswahlzahl und Freigaben nachführen, ohne die Liste neu zu bauen."""
        self.setVisible(selected > 0)
        if selected <= 0:
            return
        self.summary.setText(
            tr("1 Objekt gewählt")
            if selected == 1
            else tr("{count} Objekte gewählt").replace("{count}", str(selected))
        )
        for name, button in self._buttons.items():
            enabled, reason = availability(name)
            state = (enabled, reason)
            if self._states.get(name) == state:
                continue
            self._states[name] = state
            button.setEnabled(enabled)
            spec_tip = button.property("operationTip")
            if spec_tip is None:
                spec_tip = button.toolTip()
                button.setProperty("operationTip", spec_tip)
            tip = str(spec_tip) if enabled or not reason else reason
            button.setToolTip(tip)
            button.setStatusTip(tip)
            button.setAccessibleDescription(tip)

        self.feature_button.setEnabled(feature_chosen)
        feature_tip = (
            tr("Öffnet rechts die Maße und Handlungen des gewählten Merkmals.")
            if feature_chosen
            else tr("Wählen Sie zuerst eine Fläche, Bohrung oder ein anderes Merkmal im Bild.")
        )
        self.feature_button.setToolTip(feature_tip)
        self.feature_button.setStatusTip(feature_tip)
        self.feature_button.setAccessibleDescription(feature_tip)

    def _filter(self, query: str) -> None:
        """Nur die Darstellung filtern; Registereinträge und Knöpfe bleiben bestehen."""
        wanted = query.strip().casefold()
        for title, (heading, buttons) in self._groups.items():
            visible = False
            for button in buttons:
                match = not wanted or wanted in f"{title} {button.text()}".casefold()
                button.setVisible(match)
                visible = visible or match
            heading.setVisible(visible)
