"""Das eine Befehlsband über den drei Fensterzonen (Bauplan §2.5).

Die festen Hauptwege bleiben immer an derselben Stelle. Nur die benannte
Kontextgruppe folgt einem gewählten Merkmal, und auch dort kommen Eignung,
Titel und Handlung aus dem Operationsregister beziehungsweise aus den bereits
gebauten ``QAction``-Objekten. Das Band erfindet keine zweite Bedienlogik.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import MENU_GROUPS, MENU_TWINS, REGISTRY, OperationSpec
from app.core.registry.registry import FEATURE_TITLES, Registry
from app.i18n import sort_key, tr
from app.ui.style import NORMAL, TIGHT, set_level

MAX_CONTEXT_ACTIONS: Final = 4
"""Mehr liest sich nicht mehr als Antwort auf die Auswahl, sondern als Menü."""


def _category_rank(category: str) -> tuple[int, int]:
    """Die vorhandene Menüordnung als Rang, ohne eine zweite Liste zu bauen."""
    for group_index, (_title, categories) in enumerate(MENU_GROUPS):
        if category in categories:
            return group_index, categories.index(category)
    return len(MENU_GROUPS), 0


def context_specs(feature_kind: str, registry: Registry | None = None) -> tuple[OperationSpec, ...]:
    """Bis zu vier textlich geeignete Operationen für ein Merkmal.

    Bausteine bleiben im Bildkatalog. Vier beliebige Bausteinnamen aus einer
    längeren Reihe herauszugreifen wäre keine Empfehlung, sondern Zufall. Die
    unsichtbaren Rechenkern-Zwillinge bleiben ebenfalls bei ihrem sichtbaren
    Partner, genau wie in der Menüleiste.
    """
    source = registry or REGISTRY
    suitable = [
        spec
        for spec in source.for_feature(feature_kind)
        if spec.category != "parts" and spec.name not in MENU_TWINS
    ]
    suitable.sort(key=lambda spec: (*_category_rank(spec.category), sort_key(spec.title)))
    return tuple(suitable[:MAX_CONTEXT_ACTIONS])


class CommandBand(QWidget):
    """Feste Hauptwege, Kontextgruppe, Projektzustand und Werkzeugzeile."""

    def __init__(
        self,
        menus: Sequence[QMenu],
        primary_actions: Sequence[QAction],
        palette_action: QAction,
        header: QWidget,
        tool_area: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("commandBand")
        self._operation_actions: Mapping[str, QAction] = {}

        top = QHBoxLayout()
        top.setContentsMargins(TIGHT, TIGHT, TIGHT, TIGHT)
        top.setSpacing(TIGHT)

        self.menu = QMenu(self)
        self.menu.setToolTipsVisible(True)
        for source in menus:
            self.menu.addAction(source.menuAction())

        self.menu_button = QToolButton(self)
        self.menu_button.setText(tr("Menü"))
        self.menu_button.setAccessibleName(tr("Menü"))
        self.menu_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_button.setMenu(self.menu)
        top.addWidget(self.menu_button)

        for action in primary_actions:
            top.addWidget(self._button(action))

        self.context = QWidget(self)
        self.context.setObjectName("commandContext")
        self.context.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        context_box = QVBoxLayout(self.context)
        context_box.setContentsMargins(NORMAL, 0, NORMAL, 0)
        context_box.setSpacing(0)
        self.context_title = QLabel(tr("Auswahl"), self.context)
        self.context_title.setObjectName("commandContextTitle")
        set_level(self.context_title, "caption")
        context_box.addWidget(self.context_title)
        context_row = QHBoxLayout()
        context_row.setContentsMargins(0, 0, 0, 0)
        context_row.setSpacing(TIGHT)
        self._context_buttons = tuple(QToolButton(self.context) for _ in range(MAX_CONTEXT_ACTIONS))
        for button in self._context_buttons:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setAutoRaise(True)
            button.setVisible(False)
            context_row.addWidget(button)
        self.palette_button = self._button(palette_action)
        context_row.addWidget(self.palette_button)
        context_row.addStretch(1)
        context_box.addLayout(context_row)
        top.addWidget(self.context, 1)

        top.addWidget(header)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top)
        self._tool_slot = QVBoxLayout()
        self._tool_slot.setContentsMargins(0, 0, 0, 0)
        self._tool_slot.setSpacing(0)
        layout.addLayout(self._tool_slot)
        if tool_area is not None:
            self.set_tool_area(tool_area)

    def _button(self, action: QAction) -> QToolButton:
        """Eine vorhandene Handlung anzeigen, statt sie noch einmal zu bauen."""
        button = QToolButton(self)
        button.setDefaultAction(action)
        button.setAutoRaise(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAccessibleName(action.text().replace("&", ""))
        return button

    def set_operation_actions(self, actions: Mapping[str, QAction]) -> None:
        """Die von Menü und Palette gepflegten Handlungen anschließen."""
        self._operation_actions = actions

    def set_context(self, feature_kind: str | None) -> None:
        """Nur die feste Kontextgruppe auf das gewählte Merkmal einstellen."""
        feature_title = FEATURE_TITLES.get(feature_kind or "")
        self.context_title.setText(
            f"{tr('Auswahl')}: {feature_title}" if feature_title is not None else tr("Auswahl")
        )

        found = (
            [(spec, self._operation_actions.get(spec.name)) for spec in context_specs(feature_kind)]
            if feature_kind
            else []
        )
        visible = [(spec, action) for spec, action in found if action is not None]
        for index, button in enumerate(self._context_buttons):
            if index >= len(visible):
                button.setVisible(False)
                continue
            _spec, action = visible[index]
            button.setDefaultAction(action)
            button.setAccessibleName(action.text().replace("&", ""))
            button.setVisible(True)

    def set_tool_area(self, widget: QWidget) -> None:
        """Ansichtswerkzeuge in dieselbe Zone holen, ohne ihre Logik zu kopieren."""
        while self._tool_slot.count():
            item = self._tool_slot.takeAt(0)
            if item is None:
                continue
            previous = item.widget()
            if previous is not None:
                previous.setParent(None)
        self._tool_slot.addWidget(widget)

    def context_names(self) -> tuple[str, ...]:
        """Die sichtbaren Handlungen; Tests lesen die Aussage, nicht Pixel."""
        return tuple(
            button.defaultAction().objectName()
            for button in self._context_buttons
            if not button.isHidden() and button.defaultAction() is not None
        )
