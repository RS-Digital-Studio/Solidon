"""Namen im Wortschatz für die Knöpfe der Meldungs- und Fragefenster (RM-737).

Ein Fenster trägt sein Kennzeichen selbst (``guides.TARGET_PROPERTY``,
``message:<sache>``), benannt nach der Frage und nie nach Datei oder Modul, die
beim Aufteilen der Oberfläche wandern: eine Rückfrage als ``QMessageBox(…)``
über ``setProperty``, eine Meldung und eine Eingabe im Hausstil über ``target=``
(:mod:`app.ui.message_dialog`, :mod:`app.ui.input_dialog`,
:mod:`app.ui.place_popup`). Seine Knöpfe bekommen ihres über
:func:`name_button` (``message.button:<sache>.<knopf>``). Rohe Fenster ohne
eigene Klasse — ``QMessageBox.information``, ``QInputDialog.get…``,
``QColorDialog.getColor`` — gibt es im Kundenweg nicht mehr (FD-21, FD-22);
dass jedes Fenster seinen Namen trägt, hält ``tests/test_guide_targets.py``.
"""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton

from app.core import guides


def name_button(button: QAbstractButton, name: str) -> None:
    """Gibt einem Knopf eines Meldungs- oder Fragefensters seinen Namen im Wortschatz.

    Ein eigener Aufruf und kein ``setProperty`` am Knopf: Die Funktionsliste liest
    das Kennzeichen eines Meldungsfensters aus dem ``setProperty`` seiner
    Funktion (``tools/function_scan``), und ein Knopfname dort hieße sonst wie
    das Fenster.
    """
    button.setProperty(guides.TARGET_PROPERTY, name)
