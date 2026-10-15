"""Finder fester Namen des Wortschatzes, die ``guide_targets`` nicht mehr fasst (FD-101).

``guide_targets`` steht an der Größengrenze der Codestruktur (Regel 6, 2 000
Zeilen); seine Tabelle ``_FINDERS`` verweist für diese Namen hierher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from app.ui.main_window import MainWindow


def first_parameter_label(window: MainWindow) -> QWidget:
    """Die Beschriftung der ersten Zeile unter *Parameter* (``parameters.first.label``).

    Dieselbe Zeile wie ``parameters.first``, über die Reihenfolge. Ein
    Rechtsklick auf die Beschriftung öffnet das Menü der Zeile
    (``menu:parameters.edit``); das Wertfeld trägt das Menü seines Textfelds.
    """
    from app.ui.guide_targets import MissingTargetError

    panel = window.parameters
    if not panel._editors:
        raise MissingTargetError("parameters.first.label: das Projekt hat noch keinen Parameter")
    label: QWidget = panel._titles[next(iter(panel._editors))]
    return label


def bind_button(window: MainWindow) -> QWidget:
    """*Zahlen an Maße binden …* unter den Parametern (``parameters.bind``).

    Er steht nur, solange eine feste Zahl zu einem Maß passt; aufgelöst wird er
    auch verborgen, wie jedes Widget hinter einem festen Namen.
    """
    button: QWidget = window.parameters.bind_button
    return button
