"""Der eine Filter an der Anwendung (``app.ui.app_events``) — ohne Fenster.

Ein Klick von Bohrung zu Bohrung schickt rund 2 400 Ereignisse durch die
Anwendung. Jeder eigene Filter an ihr kostete je Ereignis einen Aufruf in
Python; drei davon 17 ms je Klick (RM-232, Durchsicht 0.5.1). Geprüft wird,
dass der Verteiler nur weiterreicht, was jemand angemeldet hat, dass ein
Zuhörer schlucken darf, dass ein toter Zuhörer herausfällt — und dass kein
Modul wieder einen eigenen Filter an die Anwendung hängt.

Die drei Tests mit Qt-Objekten brauchen die Anwendung (``qt_app``) und laufen
damit in der Fenstergruppe, beim Release; der Wächter über den Quelltext läuft
in jedem Tor.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QEvent, QObject
from shiboken6 import delete

from app.ui.app_events import ApplicationEvents


class _Listener(QObject):
    """Ein Zuhörer, der mitschreibt und auf Wunsch schluckt."""

    def __init__(self, swallow: bool = False) -> None:
        super().__init__()
        self.heard: list[QEvent.Type] = []
        self.swallow = swallow

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt-Name
        self.heard.append(event.type())
        return self.swallow


def test_only_the_announced_kinds_reach_a_listener(qt_app: object) -> None:
    """Wer ``Show`` anmeldet, hört ``Show`` — und sonst nichts, auch kein ``Move``."""
    events = ApplicationEvents()
    listener = _Listener()
    events.listen(listener, (QEvent.Type.Show, QEvent.Type.CursorChange))
    target = QObject()

    assert not events.eventFilter(target, QEvent(QEvent.Type.Move))
    assert not events.eventFilter(target, QEvent(QEvent.Type.Show))
    assert not events.eventFilter(target, QEvent(QEvent.Type.CursorChange))
    assert listener.heard == [QEvent.Type.Show, QEvent.Type.CursorChange]

    events.listen(listener, (QEvent.Type.Show,))
    events.eventFilter(target, QEvent(QEvent.Type.Show))
    assert listener.heard.count(QEvent.Type.Show) == 2, "zweimal angemeldet heißt einmal gehört"


def test_a_listener_may_swallow_and_the_next_one_then_hears_nothing(qt_app: object) -> None:
    """Die Antwort des Zuhörers gilt wie die eines eigenen Filters."""
    events = ApplicationEvents()
    first, second = _Listener(swallow=True), _Listener()
    events.listen(first, (QEvent.Type.ShortcutOverride,))
    events.listen(second, (QEvent.Type.ShortcutOverride,))

    assert events.eventFilter(QObject(), QEvent(QEvent.Type.ShortcutOverride))
    assert first.heard == [QEvent.Type.ShortcutOverride]
    assert second.heard == [], "geschluckt ist geschluckt"


def test_a_forgotten_or_destroyed_listener_hears_nothing_more(qt_app: object) -> None:
    """``forget`` ist ``removeEventFilter``; ein gelöschter Zuhörer fällt von selbst heraus."""
    events = ApplicationEvents()
    kept, forgotten, dying = _Listener(), _Listener(), _Listener()
    for listener in (kept, forgotten, dying):
        events.listen(listener, (QEvent.Type.KeyPress,))

    events.forget(forgotten)
    delete(dying)
    assert events.listening(kept)
    assert not events.listening(forgotten)
    events.eventFilter(QObject(), QEvent(QEvent.Type.KeyPress))
    assert kept.heard == [QEvent.Type.KeyPress]
    assert forgotten.heard == []


def test_no_module_hangs_its_own_filter_on_the_application() -> None:
    """Ein Filter an der Anwendung geht über ``app_events`` — kein zweiter daneben.

    Gelesen wird der Quelltext: Ein eigener Filter kostet erst im laufenden
    Fenster, und dort misst ihn kein Test ohne Fenster.
    """
    root = Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(
        r"(?:application|QApplication\.instance\(\)|QCoreApplication\.instance\(\)|app)"
        r"\s*\.installEventFilter\("
    )
    found = [
        f"{path.relative_to(root)}:{number}"
        for path in root.rglob("*.py")
        if path.name != "app_events.py"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert not found, found
