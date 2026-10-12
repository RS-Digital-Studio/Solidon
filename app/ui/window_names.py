"""Namen im Wortschatz für die rohen Meldungsfenster der Oberfläche (RM-737).

``QMessageBox``, ``QInputDialog.get…`` und ``QColorDialog.getColor`` bauen
Fenster ohne eigene Klasse, und die statischen Aufrufe geben nicht einmal ein
Objekt heraus, an das sich ein Kennzeichen hängen ließe. Der Prüfstand fand
sie deshalb nur als „irgendein Meldungsfenster“ (Konzept Funktionsdurchgang
§5: Was nicht erreichbar ist, wird ein Ziel im Wortschatz).

:func:`raw_window` schließt den Aufruf ein und gibt dem Fenster, das darin
aufgeht, sein Kennzeichen (``guides.TARGET_PROPERTY``) — ``message:<modul>.<funktion>``,
der Name der Funktion, die es baut. Dass jede solche Funktion es tut, hält
``tests/test_guide_targets.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QColorDialog, QInputDialog, QMessageBox, QWidget

from app.core import guides

#: Die Fensterklassen, die ohne eigene Klasse aufgehen.
RAW_WINDOWS = (QMessageBox, QInputDialog, QColorDialog)


class _Namer(QObject):
    """Hängt das Kennzeichen an das erste rohe Fenster, das sich zeigt."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, RAW_WINDOWS)
            and isinstance(watched, QWidget)
            and watched.isWindow()
            and not watched.property(guides.TARGET_PROPERTY)
        ):
            watched.setProperty(guides.TARGET_PROPERTY, self.name)
        return False


@contextmanager
def raw_window(name: str) -> Iterator[None]:
    """Jedes rohe Meldungsfenster, das in diesem Block aufgeht, heißt ``name``.

    Für ein Fenster mit Objekt wie für einen statischen Aufruf
    (``QMessageBox.information``) gleich: Gehört wird auf das Erscheinen, nicht
    auf den Aufruf. Ein Fenster, das schon ein Kennzeichen trägt, behält es.
    """
    application = QApplication.instance()
    if application is None:
        yield
        return
    namer = _Namer(name)
    application.installEventFilter(namer)
    try:
        yield
    finally:
        application.removeEventFilter(namer)
