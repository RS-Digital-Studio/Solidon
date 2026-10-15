"""Widgetabbau bei weiterlebendem Layout über die öffentliche Qt-Bindung."""

from PySide6.QtWidgets import QLayout, QWidget


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
