"""Layoutelemente lesen und Widgets aus weiterlebenden Layouts lösen, ohne fremde Hüllen.

Ein ``QLayoutItem`` ist kein ``QObject``: Löscht Qt es selbst, erfährt die
Python-Bindung davon nichts. Eine Hülle, die noch steht, bleibt dann im
Hüllenverzeichnis von Shiboken unter einer freigegebenen Adresse. Entsteht
dort später ein Python-eigenes ``QObject``, findet dessen ``metaObject()``
schon im Konstruktor die fremde Hülle, liest für ihren Typ keine
Signaldaten und greift auf ``nullptr`` (``PySide::SignalManager::
retrieveMetaObject``, FD-60, FD-201) — der Prozess endet ohne Rückweg.
Deshalb hält dieses Modul beide Seiten: Gelesen wird über
:func:`borrowed_items`, gelöst über :func:`detach_from_layout`.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget
from shiboken6 import createdByPython, invalidate, isValid


@contextmanager
def borrowed_items(layout: QLayout) -> Iterator[list[tuple[int, QLayoutItem]]]:
    """Die Elemente eines Layouts samt Index, gültig nur innerhalb des Blocks.

    ``itemAt(index)`` hängt die neue Hülle an die des Layouts; sie lebt, solange
    das Layout lebt, auch wenn Qt das Element vorher löscht — ``removeRow``,
    der Neuaufbau einer Knopfleiste (``QDialogButtonBox.setOrientation``,
    ``DialogFooter``), ein sterbendes Widget. Nach dem Block gibt der Leser jede
    Hülle wieder frei, die beim Lesen entstanden ist; das Element selbst bleibt
    im Layout. Wer ein Element länger braucht, liest es neu.
    """
    taken: list[tuple[int, QLayoutItem]] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is not None:
            taken.append((index, item))
    try:
        yield taken
    finally:
        for _index, item in taken:
            _release(item)


def layout_parts(layout: QLayout) -> list[tuple[QWidget | None, QLayout | None]]:
    """Je Element das Widget oder das innere Layout, in Layoutfolge — ohne gehaltene Hüllen."""
    with borrowed_items(layout) as items:
        return [(item.widget(), item.layout()) for _index, item in items]


def _release(item: QLayoutItem) -> None:
    """Gibt eine beim Lesen entstandene Hülle frei.

    Nie ein ``QObject`` (ein inneres Layout meldet seinen Abbau selbst und
    trägt vielleicht Python-Zustand) und nie ein in Python angelegtes Element
    (ein ``QSpacerItem``, das sein Besitzer später noch verstellt).
    """
    if (
        not isinstance(item, QLayoutItem)
        or isinstance(item, QObject)
        or not isValid(item)
        or createdByPython(item)
    ):
        return
    invalidate(item)


def detach_from_layout(widget: QWidget) -> None:
    """Löst das Widget aus seinem echten Layout, ohne seinen Elternteil zu ändern.

    Der Python-Aufruf removeWidget entwertet gehaltene QWidgetItem-Hüllen.
    Qts späteres natives ChildRemoved beim Widgetabbau durchläuft diese
    Binding-Grenze nicht. Verschachtelte Layouts gehören zum selben Widget;
    indexOf sucht ohne zusätzliche itemAt-Hüllen nach dem richtigen Halter.
    """
    parent = widget.parentWidget()
    layout = parent.layout() if parent is not None else None
    if layout is None:
        return
    for holder in (layout, *layout.findChildren(QLayout)):
        if holder.indexOf(widget) >= 0:
            holder.removeWidget(widget)
            return
