"""Ein Ereignisfilter an der Anwendung — für alle, die dort zuhören.

Mauszeiger (:mod:`app.ui.cursors`), Fensterchrom (:mod:`app.ui.window_chrome`),
die Navigationstasten (:mod:`app.ui.shortcut_schemes`), die Nutzungsuhr des
Fragebogens (:mod:`app.ui.survey`) und der Dateiempfang unter macOS
(``app.FileOpenListener``) hören je auf ein, zwei Ereignisarten der **ganzen**
Anwendung. Als eigene Filter angemeldet, rief Qt jeden von ihnen für **jedes**
Ereignis in Python auf: Ein Klick von Bohrung zu Bohrung am Wabenhalter
schickt rund 2 400 Ereignisse durch die Anwendung — Bewegen, Größe, Malen,
Zeigen, Stil —, und drei Filter kosteten dabei 17 ms je Klick (Durchsicht
0.5.1, RM-232, gemessen am echten Fenster, abwechselnd mit und ohne).

Hier hört **einer** zu und reicht ein Ereignis nur an die weiter, die seine
Art angemeldet haben (:func:`listen`). Die Zuhörer bleiben, was sie waren —
Objekte mit ``eventFilter`` —, und entscheiden wie zuvor, ob sie das Ereignis
schlucken. Wer stirbt, fällt von selbst heraus, so wie Qt einen gelöschten
Filter vergisst.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject


class ApplicationEvents(QObject):
    """Der eine Filter an der Anwendung; je Ereignisart die Zuhörer in Anmeldereihenfolge."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listeners: dict[QEvent.Type, tuple[QObject, ...]] = {}
        #: Je Zuhörer, unter seiner Kennung, die Verbindung, die ihn bei seinem
        #: Tod abmeldet.
        self._farewells: dict[int, QMetaObject.Connection] = {}

    def listen(self, listener: QObject, kinds: Iterable[QEvent.Type]) -> None:
        """``listener.eventFilter`` bekommt die Ereignisse dieser Arten — einmal je Art."""
        for kind in kinds:
            present = self._listeners.get(kind, ())
            if not any(known is listener for known in present):
                self._listeners[kind] = (*present, listener)
        ident = id(listener)
        if ident not in self._farewells and self.listening(listener):
            # **Nach der Kennung, nicht nach dem Objekt:** ``destroyed`` reicht
            # einen frischen Wrapper um das sterbende C++-Objekt, nicht den, der
            # hier steht — ein Vergleich mit ``is`` fände ihn nie, und der Filter
            # riefe danach einen gelöschten Zuhörer (gemessen: Zugriffsverletzung).
            self._farewells[ident] = listener.destroyed.connect(
                lambda *_args, ident=ident: self._drop(ident)
            )

    def forget(self, listener: QObject) -> None:
        """Den Zuhörer aus allen Arten nehmen — das Gegenstück zu ``removeEventFilter``."""
        farewell = self._farewells.pop(id(listener), None)
        if farewell is not None:
            QObject.disconnect(farewell)
        self._drop(id(listener))

    def listening(self, listener: QObject) -> bool:
        """Ob dieser Zuhörer irgendeine Art angemeldet hat. Der Test fragt danach."""
        return any(known is listener for present in self._listeners.values() for known in present)

    def _drop(self, ident: int) -> None:
        """Den Zuhörer mit dieser Kennung aus allen Arten nehmen."""
        self._farewells.pop(ident, None)
        for kind, present in list(self._listeners.items()):
            kept = tuple(known for known in present if id(known) != ident)
            if kept:
                self._listeners[kind] = kept
            else:
                del self._listeners[kind]

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt-Name
        """Ein Aufruf je Ereignis statt einer je Zuhörer — und keiner ohne Zuhörer."""
        listeners = self._listeners.get(event.type())
        if listeners is None:
            return False
        return any(listener.eventFilter(watched, event) for listener in listeners)


def application_events() -> ApplicationEvents | None:
    """Der Filter der laufenden Anwendung, beim ersten Aufruf angemeldet — ``None`` ohne sie."""
    application = QCoreApplication.instance()
    if application is None:
        return None
    for existing in application.findChildren(ApplicationEvents):
        return existing
    watcher = ApplicationEvents(application)
    application.installEventFilter(watcher)
    return watcher


def listen(listener: QObject, kinds: Iterable[QEvent.Type]) -> bool:
    """Einen Zuhörer an der laufenden Anwendung anmelden; ``False``, wo es keine gibt."""
    watcher = application_events()
    if watcher is None:
        return False
    watcher.listen(listener, kinds)
    return True


def forget(listener: QObject) -> None:
    """Einen Zuhörer abmelden; ohne Anwendung gibt es nichts abzumelden."""
    application = QCoreApplication.instance()
    if application is None:
        return
    for existing in application.findChildren(ApplicationEvents):
        existing.forget(listener)
