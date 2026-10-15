"""Wo die Knopfzeile des Merkmalfensters steht: unmittelbar unter der offenen Handlung (FD-136).

Die Zeile mit *Im Bild einstellen*, dem Sammelhaken, *Übernehmen* und
*Abbrechen* stand am Ende der Karte, unter Liste, Bausteinen und „Filament und
Druck“ — das Feld ganz oben, der Knopf ganz unten, und der Blick sprang über
die ganze Karte. Jetzt steht sie direkt unter der Handlung, die scharf ist
(``FeaturePanel._arm``), wie die Knöpfe eines aufgeklappten Abschnitts.

Damit sie nicht aus dem Bild rollt — der Grund, aus dem sie einmal unter den
Rollbereich gezogen worden war —, holt :func:`keep_in_sight` sie nach jedem
Wechsel der Handlung ins Sichtfeld des umgebenden Rollbereichs und hält sie
dort mit möglichst wenig Rollweg, solange die Karte noch wächst.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtWidgets import QApplication, QBoxLayout, QScrollArea, QWidget
from shiboken6 import isValid

from app.ui.leash import stop_watching_the_dying


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


FOLLOWER = "featureFooterFollower"
"""Objektname des Begleiters, den :func:`keep_in_sight` an die Knopfzeile hängt."""


class _Follower(QObject):
    """Hält die Knopfzeile im Bild, solange ihr Rollbereich noch die Größe wechselt.

    Geholt wird die Zeile, wenn die Handlung wechselt — oft mitten in der
    Öffnungsbewegung der Karte, deren Sichtfeld dann erst 94 Punkte misst. Wer
    nur dort rollte, ließe die gewachsene Karte an ihrem Anschlag stehen, Kopf
    und Maß der Wahl über dem Rand. Der Begleiter rollt bei jeder Größe so
    wenig wie möglich von der Lage aus, die er vorfand, und tritt ab, sobald
    jemand selbst rollt oder die Tastatur unter die Knopfzeile geht.
    """

    def __init__(self, footer: QWidget, holder: QScrollArea) -> None:
        super().__init__(footer)
        self.setObjectName(FOLLOWER)
        self._footer = footer
        self._holder = holder
        self._start = holder.verticalScrollBar().value()
        holder.viewport().installEventFilter(self)
        holder.verticalScrollBar().actionTriggered.connect(self.release)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._focus_moved)

    def follows(self, holder: QScrollArea) -> bool:
        """Ob dieser Begleiter für ``holder`` rollt."""
        return self._holder is holder

    def settle(self) -> None:
        """Die kleinste Verschiebung ab der Anfangslage, die die ganze Zeile zeigt."""
        footer, holder = self._footer, self._holder
        if not isValid(footer) or not isValid(holder) or footer.isHidden():
            return
        content = holder.widget()
        if content is None:
            return
        bar = holder.verticalScrollBar()
        top = footer.mapTo(content, QPoint(0, 0)).y()
        lowest = top + footer.height() - holder.viewport().height()
        # Höher als das Sichtfeld: ihr Anfang zählt.
        bar.setValue(min(max(self._start, lowest), top))

    def release(self) -> None:
        """Nicht mehr folgen — gerollt hat jetzt jemand anders."""
        if self.objectName() != FOLLOWER:
            return
        self.setObjectName("")
        if isValid(self._holder):
            self._holder.viewport().removeEventFilter(self)
            self._holder.verticalScrollBar().actionTriggered.disconnect(self.release)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.disconnect(self._focus_moved)
        self.deleteLater()

    def _focus_moved(self, _old: QWidget | None, now: QWidget | None) -> None:
        if now is None or not isValid(self._footer) or not isValid(self._holder):
            return
        content = self._holder.widget()
        if content is None or not content.isAncestorOf(now) or self._footer.isAncestorOf(now):
            return
        below = (
            now.mapTo(content, QPoint(0, 0)).y() >= self._footer.mapTo(content, QPoint(0, 0)).y()
        )
        if below:
            self.release()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Schnittstelle
        if stop_watching_the_dying(self, watched, event):
            return False
        if event.type() == QEvent.Type.Resize:
            # Erst nach dem Legen: Mit dem Sichtfeld ändert sich auch der Umbruch.
            QTimer.singleShot(0, self, self.settle)
        return False


def keep_in_sight(footer: QWidget) -> None:
    """Nach dem nächsten Legen: die Knopfzeile im Sichtfeld ihres Rollbereichs.

    Erst in der nächsten Runde, denn die Zeile wandert gerade und hat ihre neue
    Lage noch nicht. Ohne Rollbereich darüber gibt es nichts zu tun. Wächst
    oder schrumpft der Rollbereich danach, folgt :class:`_Follower`.
    """

    def settle() -> None:
        if not isValid(footer) or footer.isHidden():
            return
        holder = footer.parentWidget()
        while holder is not None and not isinstance(holder, QScrollArea):
            holder = holder.parentWidget()
        if holder is None:
            return
        follower = footer.findChild(_Follower, FOLLOWER, Qt.FindChildOption.FindDirectChildrenOnly)
        # Folgt schon einer, gilt seine Anfangslage weiter: Mehrere Wechsel in
        # einer Wahl rollten sonst jeder von der Lage des vorigen aus.
        if follower is not None and not follower.follows(holder):
            follower.release()
            follower = None
        if follower is None:
            follower = _Follower(footer, holder)
        follower.settle()

    QTimer.singleShot(0, footer, settle)
