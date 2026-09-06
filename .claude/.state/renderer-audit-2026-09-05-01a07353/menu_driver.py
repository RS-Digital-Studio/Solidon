"""Bedient vollständige Menüketten mit echten Maus- und Tastaturereignissen."""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu, QMenuBar
from shiboken6 import isValid

VERSION = "full-chain-retry-2-keyboard"


class MenuNavigationError(RuntimeError):
    """Die Prüfsteuerung hat noch keine Handlung ausgelöst."""


def install(probe):
    """Ersetzt ausschließlich probe.menu; Produktaktionen bleiben unverändert."""
    if getattr(probe, "menu_driver_version", None) == VERSION:
        return
    app, window = probe.app, probe.window
    last_click = 0.0
    opened_at = {}

    def pause(ms):
        """Pumpt Qt-Ereignisse und gibt beim Warten den Python-Interpreter frei."""
        end = time.monotonic() + ms / 1000
        while time.monotonic() < end:
            probe.pump_events()
            time.sleep(0.01)

    def until(condition, seconds, label):
        """Interner Timeout gehört zur Wiederholung, nicht zu einem Produktbefund."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            probe.pump_events()
            if condition():
                return
            time.sleep(0.02)
        raise MenuNavigationError(label)

    def visible_menus():
        return [
            widget
            for widget in app.topLevelWidgets()
            if isinstance(widget, QMenu) and isValid(widget) and widget.isVisible()
        ]

    def dismiss_menus():
        """Escape gilt nur dem echten Menüpopup, niemals einem Operationsdialog."""
        for _ in range(12):
            popup = app.activePopupWidget()
            menus = visible_menus()
            if popup is None and not menus:
                return
            if popup is not None and not isinstance(popup, QMenu):
                raise MenuNavigationError("Ein fremdes Popup liegt über dem Menü")
            target = popup if popup is not None else menus[-1]
            QTest.keyClick(target, Qt.Key.Key_Escape)
            pause(70)
        raise MenuNavigationError("Die bestehende Menükette ließ sich nicht schließen")

    def route(container, target, ancestors=()):
        """Folgt den tatsächlichen Menüaktionen statt der QObject-Elternschaft."""
        if id(container) in ancestors:
            return None
        for candidate in container.actions():
            if candidate is target:
                return [(container, candidate)]
            child = candidate.menu()
            if child is not None:
                below = route(child, target, (*ancestors, id(container)))
                if below:
                    return [(container, candidate), *below]
        return None

    def rectangle(container, candidate):
        """Prüft sichtbare Zeile, Treffer und Bildschirm vor jeder Eingabe."""
        if not isValid(container) or not container.isVisible():
            raise MenuNavigationError("Menücontainer ist nicht sichtbar")
        if not isValid(candidate) or not candidate.isVisible() or not candidate.isEnabled():
            raise MenuNavigationError("Menüzeile ist nicht sichtbar oder nicht verfügbar")
        area = container.actionGeometry(candidate).intersected(container.rect())
        if area.width() < 8 or area.height() < 5:
            raise MenuNavigationError("Menüzeile hat keine bedienbare Geometrie")
        centre = area.center()
        if container.actionAt(centre) is not candidate:
            raise MenuNavigationError("Die Menüposition trifft eine andere Handlung")
        global_centre = container.mapToGlobal(centre)
        if not any(screen.geometry().contains(global_centre) for screen in app.screens()):
            raise MenuNavigationError("Die Menüzeile liegt außerhalb der Bildschirme")
        covering = app.widgetAt(global_centre)
        if isinstance(covering, QMenu) and covering is not container:
            raise MenuNavigationError("Ein anderes Popup verdeckt die Menüzeile")
        return area

    def hover(container, candidate):
        """Qt verlangt Bewegung seit dem Öffnen; Warten allein genügt nicht.

        QMenu::hasMouseMoved verlangt mehr als sechs Bewegungen oder einen Weg
        über startDragDistance. Nach enterEvent beginnt der Zähler bei -1.
        Die Bewegung bleibt vollständig in derselben überprüften Aktionszeile.
        """
        area = rectangle(container, candidate)
        left = QPoint(area.left() + max(2, area.width() // 4), area.center().y())
        right = QPoint(area.right() - max(2, area.width() // 4), area.center().y())
        for point in (left, right, left, right, left, right, left, right, area.center()):
            if container.actionAt(point) is not candidate:
                raise MenuNavigationError("Die Mausbewegung verließe die Menüzeile")
            QTest.mouseMove(container, point)
            pause(20)
        rectangle(container, candidate)

    def click_action(container, candidate):
        """Lässt Öffnungs- und Doppelklickschutz auslaufen und klickt genau einmal."""
        nonlocal last_click
        quiet = (app.doubleClickInterval() + 80) / 1000
        after = max(last_click, opened_at.get(id(container), 0.0)) + quiet
        pause(max(0, (after - time.monotonic()) * 1000))
        area = rectangle(container, candidate)
        if isinstance(container, QMenu) and container.activeAction() is not candidate:
            raise MenuNavigationError("Die sichtbare Menüauswahl ist noch nicht die Zielzeile")
        last_click = time.monotonic()
        QTest.mouseClick(container, Qt.MouseButton.LeftButton, pos=area.center())

    def open_child(container, candidate, child):
        """Ein durch Hover geöffnetes Untermenü wird nicht erneut zugeklickt."""
        hover(container, candidate)
        if isinstance(container, QMenuBar):
            if not child.isVisible():
                click_action(container, candidate)
        else:
            try:
                until(child.isVisible, 1.2, "Untermenü öffnet nicht durch Mausbewegung")
            except MenuNavigationError:
                # Reale Tastatur am sichtbaren, überprüften Elternmenü.
                # Kein setActiveAction und kein direkter Aufruf der Zielhandlung.
                rectangle(container, candidate)
                if container.activeAction() is not candidate:
                    raise
                key = Qt.Key.Key_Left if container.isRightToLeft() else Qt.Key.Key_Right
                QTest.keyClick(container, key)
        until(child.isVisible, 2.0, "Menü sichtbar: " + candidate.text())
        if child.width() < 8 or child.height() < 5:
            raise MenuNavigationError("Geöffnetes Untermenü hat keine bedienbare Größe")
        opened_at[id(child)] = time.monotonic()

    def location(container, candidate):
        """Hält beim Wiederholungsfall die tatsächlich gelesene Geometrie fest."""
        if container is None or not isValid(container) or not isValid(candidate):
            return None
        active = container.activeAction()
        return {
            "container": type(container).__name__,
            "action": candidate.text(),
            "visible": container.isVisible(),
            "geometry": container.geometry().getRect(),
            "rect": container.rect().getRect(),
            "action_rect": container.actionGeometry(candidate).getRect(),
            "active_action": active.text() if active is not None else None,
        }

    def keyboard_state(container):
        """Liest die Auswahl nach echten Tasten, ohne Fokus oder Auswahl zu setzen."""
        active = container.activeAction() if isinstance(container, (QMenu, QMenuBar)) else None
        top = window.menuBar().activeAction()
        popup, focus = app.activePopupWidget(), app.focusWidget()
        return {
            "receiver": type(container).__name__,
            "active_action": active.text() if active is not None else None,
            "menubar_active": top.text() if top is not None else None,
            "popup": popup.title() if isinstance(popup, QMenu) else type(popup).__name__,
            "focus": type(focus).__name__,
            "menubar_has_focus": window.menuBar().hasFocus(),
        }

    def press_key(container, key, trace, purpose):
        """Belegt für jeden Tastenschritt den Zustand vorher und nachher."""
        if not isValid(container) or not container.isVisible():
            raise MenuNavigationError("Tastaturziel ist nicht sichtbar")
        before = keyboard_state(container)
        QTest.keyClick(container, key)
        pause(100)
        trace.append(
            {
                "purpose": purpose,
                "key": key.name,
                "before": before,
                "after": keyboard_state(container),
            }
        )

    def enter_menubar(trace, first_key):
        """F10 beziehungsweise Alt aktiviert den regulären Tastaturweg ins Menü."""
        bar = window.menuBar()
        if bar.hasFocus() and bar.activeAction() is not None:
            return
        other = Qt.Key.Key_Alt if first_key == Qt.Key.Key_F10 else Qt.Key.Key_F10
        for key in (first_key, other):
            press_key(window, key, trace, "Menüleiste über Tastatur betreten")
            if bar.activeAction() is not None and (bar.hasFocus() or visible_menus()):
                return
        raise MenuNavigationError("F10 und Alt aktivierten keine Menüauswahl")

    def select_top_action(candidate, trace):
        """Durchläuft die obersten Menüs mit begrenzter Zahl echter Links-/Rechts-Tasten."""
        bar = window.menuBar()
        maximum = len(bar.actions()) + 2
        seen = set()
        for _ in range(maximum):
            active = bar.activeAction()
            if active is candidate:
                return
            if active is not None and id(active) in seen:
                raise MenuNavigationError("Die Tastatur umrundete die Menüleiste ohne Ziel")
            if active is not None:
                seen.add(id(active))
            popup = app.activePopupWidget()
            if popup is not None:
                if not isinstance(popup, QMenu) or active is None or active.menu() is not popup:
                    raise MenuNavigationError("Ein unerwartetes Popup unterbricht die Menüleiste")
                # Links am obersten Popup wechselt zum vorigen Hauptmenü;
                # Rechts könnte stattdessen dessen ausgewähltes Untermenü öffnen.
                key = Qt.Key.Key_Right if bar.isRightToLeft() else Qt.Key.Key_Left
                receiver = popup
            else:
                if not bar.hasFocus():
                    raise MenuNavigationError("Die Menüleiste hat keinen Tastaturfokus")
                key = Qt.Key.Key_Left if bar.isRightToLeft() else Qt.Key.Key_Right
                receiver = bar
            press_key(receiver, key, trace, "Hauptmenü wählen: " + candidate.text())
        raise MenuNavigationError("Die Tastatur erreichte das Hauptmenü nicht")

    def select_popup_action(container, candidate, trace):
        """Qt übernimmt Scrollen und Überspringen gesperrter Zeilen beim Pfeiltastengang."""
        seen = set()
        for _ in range(len(container.actions()) + 2):
            if app.activePopupWidget() is not container:
                raise MenuNavigationError("Die Tasten würden ein anderes Popup treffen")
            active = container.activeAction()
            if active is candidate:
                if not candidate.isVisible() or not candidate.isEnabled():
                    raise MenuNavigationError("Die ausgewählte Menühandlung ist gesperrt")
                return
            if active is not None and id(active) in seen:
                raise MenuNavigationError("Die Tastatur umrundete das Popup ohne Ziel")
            if active is not None:
                seen.add(id(active))
            press_key(container, Qt.Key.Key_Down, trace, "Menüzeile wählen: " + candidate.text())
        raise MenuNavigationError("Die Tastatur erreichte die Menüzeile nicht")

    def keyboard_path(path, trace, first_key):
        """Bedient die gesamte Kette ohne Mauskoordinaten oder gesetzte Auswahl."""
        enter_menubar(trace, first_key)
        for container, candidate in path:
            child = candidate.menu()
            if isinstance(container, QMenuBar):
                select_top_action(candidate, trace)
                if child is None:
                    raise MenuNavigationError("Die oberste Menüzeile hat kein Popup")
                if app.activePopupWidget() is not child:
                    press_key(container, Qt.Key.Key_Down, trace, "Hauptmenü öffnen")
                until(
                    lambda child=child: child.isVisible() and app.activePopupWidget() is child,
                    2.0,
                    "Hauptmenü über Tastatur sichtbar: " + candidate.text(),
                )
                continue
            select_popup_action(container, candidate, trace)
            if child is not None:
                key = Qt.Key.Key_Left if container.isRightToLeft() else Qt.Key.Key_Right
                press_key(container, key, trace, "Untermenü öffnen: " + candidate.text())
                until(
                    lambda child=child: child.isVisible() and app.activePopupWidget() is child,
                    2.0,
                    "Untermenü über Tastatur sichtbar: " + candidate.text(),
                )
            else:
                # Enter trifft ausschließlich das aktive Popup und seine zuvor
                # gelesene Zielhandlung. Es wird niemals an einen Dialog geschickt.
                if container.activeAction() is not candidate:
                    raise MenuNavigationError("Die Zielhandlung änderte sich vor Enter")
                press_key(
                    container, Qt.Key.Key_Return, trace, "Handlung auslösen: " + candidate.text()
                )

    def menu(action):
        """Versucht vollständige Tastatur-/Mauswege und registrierte Tastenkürzel."""
        if not isValid(action) or not action.isEnabled():
            raise ValueError("Menühandlung ist nicht verfügbar")
        title = action.text()
        fired = []
        attempts = []

        def mark(*_args):
            fired.append(time.monotonic())

        action.triggered.connect(mark)
        try:
            for attempt in range(1, 4):
                if fired:
                    return
                container = candidate = None
                trace = []
                method = "mouse" if attempt == 2 else "full_menu_keyboard"
                try:
                    dismiss_menus()
                    if app.activeModalWidget() is not None:
                        raise MenuNavigationError("Ein modaler Dialog ist noch geöffnet")
                    window.activateWindow()
                    path = route(window.menuBar(), action)
                    if not path:
                        raise MenuNavigationError("Menühandlung fehlt in der Menükette")
                    if method == "full_menu_keyboard":
                        first_key = Qt.Key.Key_F10 if attempt == 1 else Qt.Key.Key_Alt
                        keyboard_path(path, trace, first_key)
                    else:
                        for container, candidate in path:
                            child = candidate.menu()
                            if child is not None:
                                open_child(container, candidate, child)
                            else:
                                hover(container, candidate)
                                click_action(container, candidate)
                    until(lambda: bool(fired), 0.8, "Menüklick löste kein Zielsignal aus")
                    if method == "full_menu_keyboard":
                        probe.log(
                            "Menühandlung über vollständige Tastaturkette erreicht",
                            status="probe_recovered" if attempt > 1 else "probe_navigation",
                            action=title,
                            attempt=attempt,
                            input=method,
                            keyboard_steps=trace,
                            previous_attempts=attempts,
                        )
                    elif attempt > 1:
                        probe.log(
                            "Menükette nach Wiederholung erreicht",
                            status="probe_recovered",
                            action=title,
                            attempt=attempt,
                            input=method,
                            previous_attempts=attempts,
                        )
                    return
                except RuntimeError as problem:
                    if fired:
                        return
                    detail = {
                        "attempt": attempt,
                        "error": str(problem),
                        "visible_menus": [item.title() for item in visible_menus()],
                        "location": location(container, candidate),
                        "input": method,
                        "keyboard_steps": trace,
                    }
                    attempts.append(detail)
                    probe.log(
                        "Gesamte Menükette wird wiederholt",
                        status="probe_retry",
                        action=title,
                        **detail,
                    )

            # Ein interner Menüübergangs-Timeout erreicht ebenfalls diesen Weg.
            dismiss_menus()
            if app.activeModalWidget() is not None:
                raise MenuNavigationError("Tastenkürzel würde einen offenen Dialog treffen")
            if not isValid(action) or not action.isEnabled():
                raise MenuNavigationError("Zielhandlung ist inzwischen gesperrt")
            window.activateWindow()
            pause(120)
            for shortcut in action.shortcuts():
                if shortcut.isEmpty():
                    continue
                QTest.keySequence(window, shortcut)
                try:
                    until(lambda: bool(fired), 0.8, "Tastenkürzel löste kein Zielsignal aus")
                except MenuNavigationError:
                    continue
                probe.log(
                    "Menühandlung über sichtbares Tastenkürzel erreicht",
                    status="probe_recovered",
                    action=title,
                    shortcut=shortcut.toString(),
                    previous_attempts=attempts,
                )
                return
            raise MenuNavigationError(
                "Menükette und Tastenkürzel lösten keine Handlung aus: " + title
            )
        finally:
            if isValid(action):
                action.triggered.disconnect(mark)

    probe.menu = menu
    probe.menu_driver_installed = True
    probe.menu_driver_version = VERSION
    probe.results["menu_driver"] = VERSION
    probe.log(
        "Prüfsteuerung für Menüketten aktualisiert",
        status="probe_fix",
        note=(
            "Vollständige Tastaturkette mit Auswahlbeleg nach jeder Taste; "
            "Mauswiederholung und registrierte Tastenkürzel bleiben als Rückfall."
        ),
    )
