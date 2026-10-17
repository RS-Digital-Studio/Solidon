"""Mausfolgen wie die des Kunden, für Prüfstand, Tests und Videowerkzeuge (FD-142).

Ein eigenes Modul und keines des Prüfstands: Wer hier einen Doppelklick holt,
benutzt den Prüfstand nicht und steht nicht unter dessen Wächter
(``function_guard.BENCH_MODULES``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def double_click(
    widget: Any,
    local: Any = None,
    modifiers: Any = None,
    *,
    under: Callable[[Any], Any] | None = None,
) -> None:
    """Ein Doppelklick, wie der Kunde ihn gibt: Klick, zweiter Druck, Loslassen.

    ``QTest.mouseDClick`` allein schickt nur das Doppelklickereignis, und eine
    Liste meldet ``itemDoubleClicked`` nur an der Zeile, die vorher gedrückt
    war — kein Doppelklick des Prüfstands öffnete je einen Verlaufsschritt
    (Probelauf F-34, Prüfpunkt 12). Losgelassen wird damit auch nicht: Qt
    hielt die linke Taste bis zum nächsten Klick im selben Prozess für
    gedrückt, jede Bewegung bis dahin war ein Zug ohne Enter und Leave, und
    ein Tooltip blieb über dem nächsten Ziel stehen (FD-83).

    ``local`` ist die Stelle im Widget, ohne Angabe seine Mitte. Wie bei Qt
    empfängt das Loslassen das gedrückte Widget oder, wenn der Doppelklick es
    abgebaut hat, das unter dem Zeiger (``under``, sonst
    ``QApplication.widgetAt``).
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid

    if local is None:
        local = widget.rect().center()
    if modifiers is None:
        modifiers = Qt.KeyboardModifier.NoModifier
    point = widget.mapToGlobal(local)
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, modifiers, local)
    QTest.mouseDClick(widget, Qt.MouseButton.LeftButton, modifiers, local)
    release = widget if isValid(widget) else (under or QApplication.widgetAt)(point)
    if release is not None:
        QTest.mouseRelease(
            release, Qt.MouseButton.LeftButton, modifiers, release.mapFromGlobal(point)
        )
