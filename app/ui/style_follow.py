"""Stil und Knöpfe folgen der Schrift, solange Solidon läuft (FD-194, FD-185).

**Ein Wechsel der Systemschrift kam erst nach einem Neustart an.** Qt setzt
dann die neue Schrift der Anwendung und schickt ``ApplicationFontChange``;
das Stylesheet trägt die Größen der Stufen aber fest (``style.stylesheet``)
und wurde nur beim Themenwechsel neu gesetzt. Nach 9 → 14 pt blieben Titel,
Abschnitt und Knöpfe bei 16, 10 und 9 pt. Hier setzt ein Zuhörer am
Anwendungsobjekt den Stil neu, wie ``window_chrome`` es für den
Palettenwechsel tut.

**Derselbe Zuhörer hebt die Knöpfe** (``button_floor``): Das Stylesheet macht
aus ``min-height`` eine ausdrückliche Mindesthöhe, die in einem engen Layout
die Schrift schlägt. Nach jedem Polieren, Stil- und Schriftwechsel bekommt ein
Knopf in der nächsten Runde die Höhe seiner Beschriftung — erst dann, weil der
Zuhörer ein Ereignis vor dem Knopf sieht und dessen Wunschmaß bis dahin das
der alten Schrift ist.
"""

from __future__ import annotations

import weakref

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QPushButton

from app.ui import app_events
from app.ui.button_floor import hold_text_height

#: Nach diesen Ereignissen steht die Höhe einer Knopfbeschriftung neu fest;
#: ``ApplicationFontChange`` gilt nur am Anwendungsobjekt.
_KINDS = (
    QEvent.Type.Polish,
    QEvent.Type.StyleChange,
    QEvent.Type.FontChange,
    QEvent.Type.ApplicationFontChange,
)


#: Unter diesem Namen merkt sich die Anwendung das Stylesheet, das Solidon
#: zuletzt gesetzt hat.
_OWN_SHEET = "solidonStyleSheet"


def remember(application: QApplication) -> None:
    """Das gerade gesetzte Stylesheet als Solidons eigenes merken (``apply_style``)."""
    application.setProperty(_OWN_SHEET, application.styleSheet())


def restyle() -> None:
    """Den Stil des laufenden Themas in der Schrift der Anwendung neu setzen.

    Nur über Solidons eigenem Stylesheet: Hat jemand anderes eines gesetzt
    oder keins — der Prüfstand, der das Aussehen nach einem Fall
    zurückgibt —, bleibt es, wie es ist.
    """
    from app.ui.style import apply_style
    from app.ui.theme import current_theme

    application = QApplication.instance()
    if not isinstance(application, QApplication):
        return
    sheet = application.styleSheet()
    if not sheet or sheet != application.property(_OWN_SHEET):
        return
    apply_style(application, current_theme())
    # Die offenen Dialoge messen nach, sobald die neue Schrift im Layout steht.
    QTimer.singleShot(0, refit_dialogs)


def refit_dialogs() -> None:
    """Jeder offene Dialog mit Inhaltshöhe misst sich in der neuen Schrift (FD-195).

    Ein Schriftwechsel ist kein nachgereichter Inhalt: Er darf Höhe auch
    zurückgeben (Absicht ``font``). Eine Größe, die der Kunde aufgezogen hat,
    bleibt (``ContentHeight``).
    """
    from PySide6.QtWidgets import QDialog

    from app.ui.style import ContentHeight, DialogScrollArea

    for window in QApplication.topLevelWidgets():
        if not isinstance(window, QDialog) or not window.isVisible():
            continue
        queue = getattr(window, "queue_refit", None)
        if callable(queue):
            # Ein Dialog mit eigener Messung (Operationsdialog, Druckeinstellungen)
            # legt vorher Breite, Beschreibung und Listen zurecht.
            queue("font")
            continue
        for scroll in window.findChildren(DialogScrollArea):
            height = scroll.content_height
            if isinstance(height, ContentHeight):
                height.fit(window, scroll, intent="font")


class StyleFollower(QObject):
    """Der eine Zuhörer für Schriftwechsel und Knopfhöhen."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._waiting: dict[int, weakref.ReferenceType[QPushButton]] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._settle)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt gibt den Namen
        if event.type() == QEvent.Type.ApplicationFontChange:
            # **Nur am Anwendungsobjekt** — Qt stellt das Ereignis zusätzlich
            # jedem Widget zu, neu gesetzt wird der Stil einmal.
            if watched is QCoreApplication.instance():
                restyle()
            return False
        if isinstance(watched, QPushButton):
            self._waiting[id(watched)] = weakref.ref(watched)
            self._timer.start()
        return False

    def _settle(self) -> None:
        waiting, self._waiting = self._waiting, {}
        for reference in waiting.values():
            button = reference()
            if button is None:
                continue
            try:
                hold_text_height(button)
            except RuntimeError:
                # Das C++-Objekt ist schon fort; der Python-Wrapper lebte noch.
                continue


def install() -> None:
    """Den Zuhörer einmal je Anwendung anmelden (``style.apply_style``)."""
    application = QCoreApplication.instance()
    if application is None or application.findChildren(StyleFollower):
        return
    app_events.listen(StyleFollower(application), _KINDS)
