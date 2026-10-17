"""Wohin die Tastatur geht, wenn der Skizzenmodus aufgeht (FD-190).

Der Modus setzte keinen Fokus. Kam man über einen Knopf des Prüfberichts —
*Eine andere Ebene wählen*, *Eingabe korrigieren* an einer kaputten
Zeichnung —, verschwand der gedrückte Knopf, und der Bericht parkte den Fokus
in seiner Liste (FD-4). Die Tastatur stand damit im Bericht, während der
Modus nach der Ebene oder nach der Zeichnung fragte.

Das Ziel ergibt sich aus dem, was der Modus braucht: Lässt sich die Ebene der
Zeichnung nicht auflösen (unlesbar, Fläche fort), ist es die Ebenenwahl; sonst
die Ansicht, in der gezeichnet wird und deren Ereignisfilter die erste Ziffer
ins Maßfeld bringt. Die freie Ansicht hat keinen Rahmen und braucht trotzdem
keine Ebene.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from app.ui.sketch_editor import FREE_VIEW, SketchPanel


def keyboard_target(panel: SketchPanel, view: QWidget, frame: object | None) -> QWidget:
    """Die Ebenenwahl, wenn die Ebene fehlt; sonst die Ansicht."""
    if frame is None and panel.plane_choice.currentData() != FREE_VIEW:
        return panel.plane_choice
    return view


def focus_the_sketch(panel: SketchPanel, view: QWidget, frame: object | None) -> None:
    """Die Tastatur ins Ziel des Modus setzen (:func:`keyboard_target`)."""
    keyboard_target(panel, view, frame).setFocus(Qt.FocusReason.OtherFocusReason)
