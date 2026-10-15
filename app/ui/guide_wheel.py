"""Wohin ein Mausrad geht: wer es nimmt und wer es weiterreicht (FD-131, FD-159).

Aus ``guide_targets`` gelöst, das an der Größengrenze der Codestruktur steht
(Regel 6, 2 000 Zeilen). Ein Rollbereich nimmt ein Rad, solange seine Leiste in
dieser Richtung weiterrückt; am Anschlag reicht Qt es an die Eltern weiter.
Die Navigation fragt das, bevor sie einen Rollschritt nennt.
"""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractScrollArea, QWidget


def takes_wheel(widget: QWidget, direction: int) -> bool:
    """Ob ein Rollbereich ein Rad in diese Richtung selbst nimmt, statt es weiterzureichen."""
    if not isinstance(widget, QAbstractScrollArea):
        return False
    bar = widget.verticalScrollBar()
    return bar is not None and (
        bar.value() < bar.maximum() if direction > 0 else bar.value() > bar.minimum()
    )
