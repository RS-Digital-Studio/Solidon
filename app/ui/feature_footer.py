"""Wo die Knopfzeile des Merkmalfensters steht: unmittelbar unter der offenen Handlung (FD-136).

Die Zeile mit *Im Bild einstellen*, dem Sammelhaken, *Übernehmen* und
*Abbrechen* stand am Ende der Karte, unter Liste, Bausteinen und „Filament und
Druck“ — das Feld ganz oben, der Knopf ganz unten, und der Blick sprang über
die ganze Karte. Jetzt steht sie direkt unter der Handlung, die scharf ist
(``FeaturePanel._arm``), wie die Knöpfe eines aufgeklappten Abschnitts.

Damit sie nicht aus dem Bild rollt — der Grund, aus dem sie einmal unter den
Rollbereich gezogen worden war —, holt :func:`keep_in_sight` sie nach jedem
Wechsel der Handlung ins Sichtfeld des umgebenden Rollbereichs.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QBoxLayout, QScrollArea, QWidget
from shiboken6 import isValid


def place_below(rows: QBoxLayout, footer: QWidget, row: QWidget | None) -> bool:
    """Hängt ``footer`` in ``rows`` direkt hinter ``row`` — oder ans Ende, ohne Zeile.

    ``True``, wenn die Knopfzeile jetzt unter einer Handlung steht. Das Ende
    heißt vor dem letzten Eintrag: ``rows`` schließt mit seinem Stretch.
    """
    index = rows.indexOf(row) if row is not None else -1
    if index >= 0 and rows.indexOf(footer) == index + 1:
        # Steht schon dort: Jede Feldberührung ruft hierher, und ein Umhängen
        # ohne Grund legte das Panel neu.
        return True
    rows.removeWidget(footer)
    index = rows.indexOf(row) if row is not None else -1
    if index < 0:
        rows.insertWidget(rows.count() - 1, footer)
        return False
    rows.insertWidget(index + 1, footer)
    return True


def keep_in_sight(footer: QWidget) -> None:
    """Nach dem nächsten Legen: die Knopfzeile im Sichtfeld ihres Rollbereichs.

    Erst in der nächsten Runde, denn die Zeile wandert gerade und hat ihre neue
    Lage noch nicht. Ohne Rollbereich darüber gibt es nichts zu tun.
    """

    def settle() -> None:
        if not isValid(footer) or footer.isHidden():
            return
        holder = footer.parentWidget()
        while holder is not None and not isinstance(holder, QScrollArea):
            holder = holder.parentWidget()
        if holder is not None:
            holder.ensureWidgetVisible(footer, 0, 0)

    QTimer.singleShot(0, footer, settle)
