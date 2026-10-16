"""Welche sichtbaren Fenster ein Fall offen zurücklässt (FD-191).

``test_function_feature_measurement`` fiel mit „Mehrere offene Bedienflächen
ohne eindeutiges aktives Fenster“: ``function_surface.open_dialog`` zählt die
sichtbaren Fenster der Anwendung, und ein Vorgänger im selben Arbeiter hatte
welche offen gelassen. Rot wurde der spätere Fall, nicht der verursachende —
dieselbe Bauart wie die gedrückte Maustaste (FD-142). Der Wächter in
``tests/conftest.py`` fragt hier nach jedem Fall und meldet am Verursacher.

Gezählt werden dieselben Fensterarten wie im Prüfstand
(``function_surface.windows_to_picture``); Menüs und Kurzhilfen nicht.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any


def visible_windows() -> list[Any]:
    """Die sichtbaren Fenster der Anwendung — leer ohne ``QApplication``."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    if not isinstance(application, QApplication):
        return []
    from PySide6.QtWidgets import QWidget

    kinds = (Qt.WindowType.Dialog, Qt.WindowType.Window, Qt.WindowType.Tool, Qt.WindowType.Sheet)
    # Über die Klasse gefragt, nicht über das Objekt: Ein Fall darf
    # ``isVisible`` am Objekt ersetzen (``monkeypatch``), und das Ersetzen
    # endet erst nach diesem Wächter.
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if QWidget.isVisible(widget)
        and QWidget.isWindow(widget)
        and QWidget.windowType(widget) in kinds
    ]


def leftovers(before: Collection[int]) -> list[Any]:
    """Die sichtbaren Fenster, die es vor dem Fall nicht gab (``before``: ihre ``id``)."""
    return [widget for widget in visible_windows() if id(widget) not in before]


def describe(windows: list[Any]) -> str:
    """Klasse und Titel je Fenster, für die Meldung am Verursacher."""
    return ", ".join(f"{type(widget).__name__} „{widget.windowTitle()}“" for widget in windows)


def close_after(request: Any, *windows: Any) -> None:
    """Die Fenster am Ende des Falls schließen, auch wenn er scheitert.

    Für Fälle, die ein Panel oder eine Leiste als eigenes Fenster zeigen; die
    Abmeldung läuft vor dem Wächter, weil sie später angemeldet ist.
    """
    request.addfinalizer(lambda: close_all(list(windows)))


def close_all(windows: list[Any]) -> None:
    """Die übrig gebliebenen Fenster schließen, damit der nächste Fall frei beginnt."""
    from shiboken6 import isValid

    for widget in windows:
        if isValid(widget):
            widget.hide()
            widget.deleteLater()
