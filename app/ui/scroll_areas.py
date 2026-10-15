"""Rollbereiche und die Tabulatortaste (FD-139).

Ein ``QScrollArea`` nimmt in Qts Vorgabe selbst den Fokus (``StrongFocus``)
und trägt keinen Namen: Am Anfang oder Ende jedes Dialogs stand so ein
Tab-Halt, den ein Bildschirmleser nur mit seinem Klassennamen ansagte, und im
Prüfbericht verließ die Kette dort die Fläche, bevor sie die Handlungen
erreichte (FD-140).

Zwei Arten, kein Drittes:

- :class:`PassingScrollArea` — ein reiner Behälter für Felder und Knöpfe. Er
  ist kein Halt; Tab geht in seinen Inhalt, Qt rollt das fokussierte Kind ins
  Bild (``QScrollArea.focusNextPrevChild``), und das Rad rollt ohnehin.
- :class:`ReadingScrollArea` — ein Rollbereich mit Lesetext ohne eigenes
  Bedienelement. Er bleibt ein Halt, damit Pfeil- und Bildtasten ihn rollen,
  und sagt mit Namen und Beschreibung, was dort steht.

Ein nacktes ``QScrollArea`` gibt es in ``app/ui`` nicht mehr
(``tests/test_scroll_areas.py``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QWidget


class PassingScrollArea(QScrollArea):
    """Ein Rollbereich, der selbst kein Tab-Halt ist — die Tastatur geht in den Inhalt."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class ReadingScrollArea(QScrollArea):
    """Ein Rollbereich mit Lesetext: ein Halt mit Namen und Beschreibung.

    ``name`` sagt, was dort steht, ``description``, wie man darin blättert.
    """

    def __init__(self, name: str, description: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(name)
        self.setAccessibleDescription(description)
