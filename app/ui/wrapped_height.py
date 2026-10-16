"""Ein umbrochener Satz hält die Höhe, die sein Text in seiner Breite braucht.

Ein ``QLabel`` mit Zeilenumbruch nennt seine Höhe nur über ``heightForWidth``;
die Karten pinnen sie deshalb als Mindesthöhe (``panels.fit_wrapped``).
Gemessen wurde einmal, an der Grundbreite der linken Spalte. Die rechte Karte
ist aber 400 bis 540 Punkte breit und die linke seit FD-20 bis ``LEFT_MAX``:
Ein Satz, der dort in eine Zeile passt, behielt die zweite als Leerraum, den
Text mittig darin. Am Lauf des Funktionsdurchgangs standen so im
Portugiesischen zwei Leerzeilen im Maßblock von *Gegenstücke setzen …*
(FD-133).

Der Folger misst neu, sobald Breite, Text oder Schrift nicht mehr zur
gepinnten Höhe passen: bei einer Größenänderung sofort, nach einem neuen Text
vor dem nächsten Zeichnen. ``style.WrappedNote`` folgt sich selbst und meldet
dabei ``grown``; ihm wird kein zweiter Folger angehängt, sonst käme der
Folger ihm zuvor und das Signal bliebe aus.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QLabel

from app.ui.leash import stop_watching_the_dying
from app.ui.style import UNBOUNDED, WrappedNote


def claim_wrapped_height(label: QLabel, width: int) -> None:
    """Mindest- und Höchsthöhe auf das setzen, was der Text in ``width`` braucht.

    **Gemessen ohne die gepinnten Höhen:** ``QLabel.heightForWidth`` meldet nie
    weniger als die eigene Mindesthöhe, ein kürzerer Text gäbe sonst keine
    Zeile zurück. Ein Satz ohne Umbruch meldet -1; er bekommt keine Grenzen.

    **Auch die Höchsthöhe** (D1 zu FD-133): Eine Karte misst ihre Panels nach
    dem Größenwunsch, und ``QLabel.sizeHint`` rechnet an Qts Schätzbreite. Mit
    der Mindesthöhe allein stand der leere Satz im neuen Projekt eine Zeile
    höher als sein Text; die Höchsthöhe begrenzt den Wunsch auf den Bedarf.
    """
    label.setMinimumHeight(0)
    label.setMaximumHeight(UNBOUNDED)
    needed = label.heightForWidth(width)
    if needed < 0:
        return
    label.setMinimumHeight(needed)
    label.setMaximumHeight(needed)


def _shape(label: QLabel) -> tuple[int, str, str]:
    """Woran die gepinnte Höhe hängt: Breite, Text und Schrift."""
    return label.width(), label.text(), label.font().key()


class _HeightFollower(QObject):
    """Misst den Satz neu, wenn Breite, Text oder Schrift sich geändert haben."""

    def __init__(self, label: QLabel) -> None:
        super().__init__(label)
        self.measured: tuple[int, str, str] | None = None
        label.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt gibt den Namen
        if stop_watching_the_dying(self, watched, event):
            return False
        if isinstance(watched, QLabel) and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Paint,
        ):
            # Vor dem Zeichnen, weil ``setText`` dem Satz selbst kein Ereignis
            # schickt; der Vergleich hält das Messen auf echte Änderungen.
            shape = _shape(watched)
            if shape != self.measured:
                self.measured = shape
                claim_wrapped_height(watched, watched.width())
        return False


def follow_wrapped_height(label: QLabel, estimate: int) -> None:
    """Pinnt die Höhe des Satzes und hält sie an seiner sichtbaren Breite.

    Bevor ein Layout ihm eine Breite gegeben hat, gilt ``estimate``; die erste
    echte Breite kommt mit dem ersten Größenereignis, noch vor dem Zeichnen.
    """
    placed = label.testAttribute(Qt.WidgetAttribute.WA_Resized)
    claim_wrapped_height(label, label.width() if placed else estimate)
    if isinstance(label, WrappedNote):
        return
    follower = label.findChild(_HeightFollower, options=Qt.FindChildOption.FindDirectChildrenOnly)
    if follower is None:
        follower = _HeightFollower(label)
    follower.measured = _shape(label) if placed else None
