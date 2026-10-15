"""Die Maßkartenfolge am echten Fenster: ein Sprachprozess, Kundengesten über den Prüfstand.

Gestartet nur als Kindprozess von ``tools/native_runs.py measure-card``, nach
der Siegelprüfung in ``native_binding.enter`` — erst danach lädt dieses Modul
Qt. Übernommen aus dem gesiegelten Sitzungsläufer der Maßgruppe
(``native_case.py``, 62 von 62 Bedingungen am MSI-Schirm), ergänzt um den
Außenzug mit Zeigerlesung (FD-164).

Der Weg je Sprache: **Bohrung ändern** — Vorderseite, Außenzug bis zur Mitte
der Menüleiste, Titel- und Freiflächenzug, Feld am neuen Ort, Klappe, drei
Feldhilfen, *Abbrechen*, Einzel- und Sammelübernahme je mit einem Strg+Z —,
danach **Merkmal verschieben, duplizieren und drehen** bis zur rechten Karte
und zurück zum Körper. Jede Handlung ist ein Eingabeereignis über
``function_walk`` (``QtPorts``, ``click_button``) oder ``QTest`` am
Hauptfenster; Zustand wird gelesen, nie eine Produktaktion aufgerufen. Bilder
nur über ``screen().grabWindow``, erst nach fertiger Rechnung und stehendem
Fenster. Exit 0 ist keine Bildabnahme: ``visual_review_complete`` bleibt
falsch, die Bilder liest ein Mensch oder Agent danach.

**Der Zeiger steht am Fenster des Druckempfängers.** Die Maßkarte trägt ein
eigenes natives Fenster (``overlay.hold_above_the_view``), und Qt setzt einen
Widgetzeiger am nächsten nativen Vorfahren. Gelesen wird deshalb das
``QWindow`` dieses Vorfahren (:func:`native_window_of`). Die erste Fassung des
Außenzugs las das Hauptfenster; dort steht ein anderer Zeiger, und die
Bedingung war an der falschen Stelle rot (native-d0-claude, Zusatzlauf 2b).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import traceback
from collections.abc import Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QFontInfo, QWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QToolTip,
    QWidget,
)

from tools.native_runs import CARD_ROWS

#: Die linke Maustaste als Zahl, wie ``QApplication.mouseButtons().value`` sie liefert.
LEFT = Qt.MouseButton.LeftButton.value

#: Was die Maßkarte im Protokoll statt eines gemessenen Referenzfaktors trägt.
NO_REFERENCE = {
    "reference_factor": 1.0,
    "reference_factor_status": "technischer Platzhalter, ausdrücklich nicht gemessen",
}


def rectangle(value: Any) -> list[int]:
    return [value.x(), value.y(), value.width(), value.height()]


def widget_state(widget: Any) -> dict[str, Any] | None:
    """Lage, Text, Schrift und Zustand eines Widgets — gelesen, nichts gesetzt."""
    if widget is None:
        return None
    origin = widget.mapToGlobal(QPoint())
    text_method = getattr(widget, "text", None)
    text = str(text_method()) if callable(text_method) else ""
    font, metrics = widget.font(), widget.fontMetrics()
    actual = QFontInfo(font)
    state: dict[str, Any] = {
        "class": type(widget).__name__,
        "name": widget.objectName(),
        "text": text,
        "visible": widget.isVisible(),
        "enabled": widget.isEnabled(),
        "rect": [origin.x(), origin.y(), widget.width(), widget.height()],
        "contents": rectangle(widget.contentsRect()),
        "size_hint": [widget.sizeHint().width(), widget.sizeHint().height()],
        "accessible_name": widget.accessibleName(),
        "description": widget.accessibleDescription(),
        "tooltip": widget.toolTip(),
        "font": font.toString(),
        "font_weight": font.weight(),
        "actual_family": actual.family(),
        "actual_points": actual.pointSizeF(),
        "pixel_size": actual.pixelSize(),
        "font_height": metrics.height(),
        "text_natural_width": metrics.horizontalAdvance(text),
        "palette_button": widget.palette().button().color().name(),
        "palette_text": widget.palette().buttonText().color().name(),
    }
    if isinstance(widget, (QPushButton, QToolButton, QCheckBox)):
        state.update(checked=widget.isChecked(), checkable=widget.isCheckable())
    if isinstance(widget, QPushButton):
        state["default"] = widget.isDefault()
    if isinstance(widget, QLabel):
        state["word_wrap"] = widget.wordWrap()
        flags = int(widget.alignment()) | (
            int(Qt.TextFlag.TextWordWrap) if widget.wordWrap() else 0
        )
        state["derived_text_rect"] = rectangle(
            metrics.boundingRect(QRect(widget.contentsRect()), flags, text)
        )
        state["text_format"] = str(widget.textFormat())
    return state


# --- Zeiger -------------------------------------------------------------------


def native_window_of(widget: Any) -> QWindow | None:
    """Das ``QWindow``, an dem Qt den Zeiger dieses Widgets setzt.

    Das eigene, wenn das Widget nativ ist, sonst das des nächsten nativen
    Vorfahren — derselbe Weg wie ``qt_qpa_set_cursor``. ``nativeParentWidget``
    allein reichte nicht: Es überspringt das Widget selbst, und beim Zug an
    der freien Fläche ist der Druckempfänger die native Karte.
    """
    owner = widget
    while owner is not None:
        handle = owner.windowHandle()
        if handle is not None:
            return handle
        owner = owner.parentWidget()
    return None


def cursor_form(value: Any) -> dict[str, Any] | None:
    """Form, Heißpunkt und Bild eines Zeigers; setzt keinen und ändert keinen Stapel."""
    if value is None:
        return None
    image = value.pixmap().toImage()
    return {
        "shape": value.shape().name,
        "hotspot": [value.hotSpot().x(), value.hotSpot().y()],
        "pixels": [image.width(), image.height()],
        "bitmap": hashlib.sha256(bytes(image.constBits())).hexdigest()
        if not image.isNull()
        else None,
    }


def window_identity(handle: Any, top: Any) -> dict[str, Any] | None:
    if handle is None:
        return None
    return {
        "class": type(handle).__name__,
        "name": handle.objectName(),
        "geometry": rectangle(handle.geometry()),
        "is_main_window": handle is top,
    }


def cursor_sample(
    receiver: Any, *, top: Any, outside: Any = None, delivered: Any = None
) -> dict[str, Any]:
    """Alle Zeiger, die beim Zug zählen — passiv gelesen.

    ``receiver_window`` ist das native Fenster des Druckempfängers, an dem der
    Zugzeiger erscheinen muss; ``main_window`` das Hauptfenster, nur zum
    Vergleich (dort las die erste Fassung).
    """
    handle = native_window_of(receiver)
    return {
        "receiver_window": cursor_form(handle.cursor()) if handle is not None else None,
        "receiver_window_identity": window_identity(handle, top),
        "main_window": cursor_form(top.cursor()),
        "override": cursor_form(QApplication.overrideCursor()),
        "press_widget": cursor_form(receiver.cursor()),
        "press_owns_cursor": receiver.testAttribute(Qt.WidgetAttribute.WA_SetCursor),
        "outside_widget": cursor_form(outside.cursor()) if outside is not None else None,
        "outside_owns_cursor": outside.testAttribute(Qt.WidgetAttribute.WA_SetCursor)
        if outside is not None
        else None,
        "delivered_widget": widget_state(delivered),
        "delivered_cursor": cursor_form(delivered.cursor()) if delivered is not None else None,
        "buttons": QApplication.mouseButtons().value,
    }


def holds_move_cursor(sample: Mapping[str, Any], expected: Mapping[str, Any] | None) -> bool:
    """Während des Haltens: Zugzeiger am Druckempfänger und an seinem Fenster, kein Override."""
    return bool(
        expected is not None
        and sample["receiver_window"] == expected
        and sample["press_widget"] == expected
        and sample["press_owns_cursor"]
        and sample["override"] is None
        and sample["buttons"] & LEFT
    )


def returns_cursor(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    pressed_after: bool,
    expected: Mapping[str, Any] | None,
) -> bool:
    """Nach dem Release: Druck gelöst, kein Zugzeiger am Fenster, alles andere wie vorher."""
    return (
        not pressed_after
        and after["buttons"] == 0
        and after["receiver_window"] != expected
        and after["override"] == before["override"]
        and all(
            after[key] == before[key]
            for key in (
                "press_widget",
                "press_owns_cursor",
                "outside_widget",
                "outside_owns_cursor",
            )
        )
    )


class InputTrace(QObject):
    """Liest echte empfangene Eingabeereignisse; verändert kein Ereignis."""

    def __init__(self, window: Any, out: Path) -> None:
        super().__init__(window)
        self.out = out
        self.turn = 0
        self.events: list[dict[str, Any]] = []
        self.gesture: str | None = None
        self.hover: str | None = None
        self.hover_widget: Any = None
        self.mouse_receiver: Any = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(0)

    def tick(self) -> None:
        self.turn += 1

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 — Qt-Name
        kinds: tuple[Any, ...] = (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
            QEvent.Type.Wheel,
        )
        if self.gesture is not None or self.hover is not None:
            kinds = (*kinds, QEvent.Type.MouseMove)
        if self.hover is not None:
            kinds = (
                *kinds,
                QEvent.Type.Enter,
                QEvent.Type.Leave,
                QEvent.Type.HoverMove,
                QEvent.Type.ToolTip,
            )
        if event.type() not in kinds or not isinstance(watched, (QWidget, QWindow)):
            return False
        names = []
        owner = watched
        while owner is not None:
            names.append(owner.objectName() or type(owner).__name__)
            owner = owner.parentWidget() if isinstance(owner, QWidget) else owner.parent()
        row: dict[str, Any] = {
            "turn": self.turn,
            "monotonic": time.monotonic(),
            "event": str(event.type()),
            "event_name": event.type().name,
            "receiver": watched.objectName() or type(watched).__name__,
            "receiver_class": type(watched).__name__,
            "ancestors": names,
        }
        row["receiver_level"] = "widget" if isinstance(watched, QWidget) else "window"
        if (
            self.gesture is not None
            and isinstance(watched, QWidget)
            and event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease)
        ):
            self.mouse_receiver = watched
        if self.hover_widget is not None and isinstance(watched, QWidget):
            row["at_hover_target"] = watched is self.hover_widget or self.hover_widget.isAncestorOf(
                watched
            )
        if hasattr(event, "globalPosition"):
            point = event.globalPosition().toPoint()
            row["point"] = [point.x(), point.y()]
        elif hasattr(event, "globalPos"):
            point = event.globalPos()
            row["point"] = [point.x(), point.y()]
        if hasattr(event, "key"):
            row["key"] = int(event.key())
        if hasattr(event, "button"):
            row["button"] = str(event.button())
        if hasattr(event, "buttons"):
            row["buttons"] = event.buttons().value
        row["gesture"] = self.gesture
        row["hover"] = self.hover
        row["spontaneous"] = event.spontaneous()
        self.events.append(row)
        with (self.out / "input-events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        return False


class CardRoute:
    """Ein Sprachprozess der Maßkartenfolge: Fenster, Ereignisspur, Zustand, Bilder."""

    def __init__(self, out: Path, language: str) -> None:
        self.out = out
        self.window: Any = None
        self.application: Any = None
        self.trace: Any = None
        self.current: Any = None
        self.state: dict[str, Any] = {
            "language": language,
            "rows_done": [],
            "captures": [],
            "checks": [],
            "unmeasured": [],
            "performance_valid": False,
            "visual_review_complete": False,
        }

    # --- Protokoll ----------------------------------------------------------

    def persist(self) -> None:
        write(self.out / "observation.json", self.state)
        if self.current is not None:
            write(self.out / f"protocol-{self.current.row['id']}.json", self.current.data)

    def walk(self, flow: Any, name: str, steps: list[Any], timeout: float = 75) -> None:
        assert flow.run_steps(name, steps, timeout_s=timeout), (
            f"Eingabeweg nicht abgeschlossen: {name}"
        )
        assert not flow.data["errors"], flow.data["errors"]
        self.persist()

    def check(self, name: str, condition: object, detail: object = None) -> None:
        self.state["checks"].append(
            {"name": name, "holds": bool(condition), "detail": detail, "turn": self.trace.turn}
        )
        self.persist()
        assert condition, f"Prüfbedingung nicht erfüllt: {name}; {detail}"

    # --- Zustand ------------------------------------------------------------

    def display_ready(self) -> bool:
        window = self.window
        session = window.session
        if session.last_result is None or session.busy or session._previews:
            return False
        if window._preview_busy.isActive() or window._preview_reason:
            return False
        difference = window.viewport.difference
        if difference is not None:
            return bool(window.viewport.is_difference_applied(difference))
        return bool(window.viewport.is_scene_applied(session.last_result))

    def quiet(self) -> Any:
        flow = self.window._quiet_placement
        assert flow is not None and flow.active and flow._measure_group is not None
        return flow

    def fields(self) -> dict[str, Any]:
        from app.ui.panels import FIELD_PROPERTY

        group = self.quiet()._measure_group
        return {
            str(widget.property(FIELD_PROPERTY)): widget
            for widget in group.findChildren(QWidget)
            if widget.property(FIELD_PROPERTY)
        }

    def measure_heading(self) -> Any:
        flap = self.quiet()._measure_group.findChild(QWidget, "feature-measure-more")
        assert flap is not None
        heading = flap.findChild(QToolButton, "sectionHeading")
        assert heading is not None
        return heading

    def placement_state(self) -> dict[str, Any]:
        placement = self.quiet()
        drag = placement._measure_drag
        return {
            "card": rectangle(placement._measure_box.geometry()),
            "room": rectangle(drag._room),
            "place": asdict(drag._place) if drag._place is not None else None,
            "overlay_pending": self.window.overlay._pending,
            "overlay_moves": len(self.window.overlay._moves),
            "renderer_ready": self.display_ready(),
            "turn": self.trace.turn,
        }

    def settle_card(self, flow: Any, label: str) -> None:
        """Auf tatsächlichen Raum, Kartenort und abgeschlossene Darstellung warten."""
        from tools.function_walk import STABLE_S

        previous_turn = self.trace.turn
        seen: dict[str, Any] = {"signature": None, "since": 0.0}

        def ready() -> bool:
            if (
                self.trace.turn <= previous_turn
                or self.window.overlay._moves
                or self.window.overlay._pending is not None
                or not self.display_ready()
            ):
                seen["signature"] = None
                return False
            current = self.placement_state()
            signature = (tuple(current["card"]), tuple(current["room"]))
            if signature != seen["signature"]:
                seen.update(signature=signature, since=time.monotonic())
            return bool(time.monotonic() - seen["since"] >= STABLE_S)

        self.walk(flow, label, [flow.wait_step(label, ready, timeout_s=15)])

    def check_manual_place(self, anchor: Any, place: Mapping[str, Any], label: str) -> None:
        placement = self.quiet()
        card, room = placement._measure_box.geometry(), placement._measure_drag._room
        wanted = QPoint(
            max(room.left(), min(anchor.x(), room.right() - card.width() + 1)),
            max(room.top(), min(anchor.y(), room.bottom() - card.height() + 1)),
        )
        self.check(
            label + " erhält den freien Abgabeplatz",
            asdict(placement._measure_drag._place) == place
            and not place["edge"]
            and card.topLeft() == wanted
            and room.contains(card),
            self.placement_state(),
        )

    # --- Gesten -------------------------------------------------------------

    def drag_card(
        self, flow: Any, *, free_surface: bool, fraction: tuple[float, float], outside: bool = False
    ) -> tuple[Any, dict[str, Any]]:
        """Gehaltene Mausgeste im stabilen Fenster, ohne die Produktplatzierung aufzurufen.

        ``outside`` zieht vom Titel bis zur Mitte der Menüleiste — im Fenster
        und auf dem Schirm, außerhalb von Karte und Raum — und liest vor, beim
        Halten und nach dem Release die Zeiger (:func:`cursor_sample`). Die
        nächste Kundengeste danach ist die echte Feldhilfe am Durchmesser.
        """
        from app.ui.cursors import cursor as role_cursor
        from app.ui.overlay import dropped_place
        from tools.function_protocol import compare_prints

        window, application, trace = self.window, self.application, self.trace
        label = "Maßkarte an freier Fläche ziehen" if free_surface else "Maßkarte am Titel ziehen"
        if outside:
            label = "Maßkarte gehalten bis außerhalb ihrer Hülle ziehen"
        self.settle_card(flow, label + " Ausgang steht")
        placement = self.quiet()
        card, room = placement._measure_box, QRect(placement._measure_drag._room)
        title = (
            placement._measure_group.layout().itemAt(0, QFormLayout.ItemRole.SpanningRole).widget()
        )
        assert isinstance(title, QLabel) and title.property("level") == "section"
        if free_surface:
            # Nur ein tatsächlich getroffener Kartenhintergrund gilt als freie Fläche.
            point = None
            spacing = max(2, card.fontMetrics().height() // 4)
            for y in range(2, card.height() - 2, spacing):
                for x in range(2, card.width() - 2, spacing):
                    candidate = card.mapToGlobal(QPoint(x, y))
                    if flow.ports.widget_under(candidate) is card:
                        point = candidate
                        break
                if point is not None:
                    break
            assert point is not None, "Keine sichtbare freie Kartenfläche getroffen"
        else:
            point = title.mapToGlobal(title.visibleRegion().boundingRect().center())
            assert flow.ports.widget_under(point) is title, (
                "Titel ist nicht der tatsächliche Treffer"
            )
        target = QPoint(
            room.left() + round((room.width() - card.width()) * fraction[0]),
            room.top() + round((room.height() - card.height()) * fraction[1]),
        )
        proposed = QRect(target, card.size()).translated(-room.topLeft())
        assert not dropped_place(proposed, room.width(), room.height()).edge, (
            "Ziel ist kein freier Innenplatz"
        )
        delta = target - card.pos()
        outside_point = None
        outside_widget = None
        if outside:
            bar = window.menuBar()
            outside_point = bar.mapToGlobal(bar.rect().center())
            outside_widget = flow.ports.widget_under(outside_point)
            assert outside_widget is not None and outside_widget.window() is window
            client = QRect(window.mapToGlobal(QPoint()), window.size())
            assert client.contains(outside_point)
            assert window.screen().availableGeometry().contains(outside_point)
            assert not QRect(card.mapToGlobal(QPoint()), card.size()).contains(outside_point)
            delta = outside_point - point
        assert delta.manhattanLength() > application.startDragDistance()
        hit = flow.ports.widget_under(point)
        assert hit is not None and hit.window() is window and QApplication.activeWindow() is window
        handle = window.windowHandle()
        assert handle is not None
        before = flow.scene_now()
        transactions = len(window.session.project.document.transactions)
        evidence: dict[str, Any] = {
            "gesture": label,
            "before": self.placement_state(),
            "hit": widget_state(hit),
            "hit_description": flow.ports.describe(hit, point),
            "press_global": [point.x(), point.y()],
            "target_local": [target.x(), target.y()],
            "events_from": len(trace.events),
        }
        native_ancestors = []
        owner = hit
        while owner is not None:
            native = owner.windowHandle()
            native_ancestors.append(
                {
                    "class": type(owner).__name__,
                    "name": owner.objectName(),
                    "native_attribute": owner.testAttribute(Qt.WidgetAttribute.WA_NativeWindow),
                    "handle": window_identity(native, handle),
                }
            )
            owner = owner.parentWidget()
        evidence["native_ancestors"] = native_ancestors
        evidence["receiver_window"] = window_identity(native_window_of(hit), handle)
        self.state.setdefault("gestures", []).append(evidence)
        self.persist()
        trace.gesture = label
        trace.mouse_receiver = None

        def sample() -> dict[str, Any]:
            return cursor_sample(
                hit, top=handle, outside=outside_widget, delivered=trace.mouse_receiver
            )

        if outside_point is not None:
            evidence["outside_global"] = [outside_point.x(), outside_point.y()]
            evidence["cursor_before"] = sample()
            # Der Zeiger, den das Produkt dem Druckempfänger gibt (``measure_card_drag``).
            evidence["expected_move_cursor"] = cursor_form(role_cursor("move", hit))
            assert evidence["cursor_before"]["override"] is None, (
                "Unerwarteter fremder Override im Startzustand"
            )
        held = False
        last = QPoint(point)
        evidence["move_targets"] = []
        try:
            QTest.mousePress(
                handle,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                handle.mapFromGlobal(point),
            )
            held = True
            evidence["pressed_seen_by_product"] = placement._measure_drag._pressed is not None
            assert evidence["pressed_seen_by_product"], (
                "Titel-/Freiflächen-Press erreicht den Dragfilter nicht"
            )
            # Der reine Beobachter liest auch Bewegungen, die der Zugfilter übernimmt.
            application.removeEventFilter(trace)
            application.installEventFilter(trace)
            for part in (1, 2, 3, 4):
                last = point + QPoint(round(delta.x() * part / 4), round(delta.y() * part / 4))
                evidence["move_targets"].append([last.x(), last.y()])
                QTest.mouseMove(handle, handle.mapFromGlobal(last))
                flow.pump()
            evidence["before_release"] = self.placement_state()
            if outside:
                card_global = QRect(card.mapToGlobal(QPoint()), card.size())
                evidence["cursor_held"] = sample()
                evidence["held_card_global"] = rectangle(card_global)
                assert not card_global.contains(last), "Endpunkt liegt noch in der gezogenen Karte"
                assert QRect(window.mapToGlobal(QPoint()), window.size()).contains(last)
                assert window.screen().availableGeometry().contains(last)
            QTest.mouseRelease(
                handle,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                handle.mapFromGlobal(last),
            )
            held = False
            evidence["after_release"] = self.placement_state()
            if outside:
                evidence["cursor_after"] = sample()
                evidence["pressed_after"] = placement._measure_drag._pressed is not None
        finally:
            if held:
                QTest.mouseRelease(
                    handle,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                    handle.mapFromGlobal(last),
                )
            trace.gesture = None
            trace.mouse_receiver = None
            self.persist()
        self.settle_card(flow, label + " Ergebnis steht")
        evidence["settled"] = self.placement_state()
        if not outside:
            self.capture(flow, "resize-freiflaechenzug" if free_surface else "resize-titelzug")
        events = trace.events[evidence["events_from"] :]
        transport = transport_of(events, evidence["move_targets"])
        evidence["transport"] = transport
        self.check(
            label + " echte gehaltene Ereignisfolge",
            any(
                event["receiver_level"] == "widget"
                and event["event_name"] == "MouseButtonPress"
                and event.get("button") == str(Qt.MouseButton.LeftButton)
                and event.get("buttons", 0) & LEFT
                for event in events
            )
            and all(
                len(row["move_indices"]) == 4 and row["release_index"] is not None
                for row in transport.values()
            ),
            {"transport": transport, "move_targets": evidence["move_targets"], "events": events},
        )
        if outside:
            self.outside_checks(flow, label, evidence, card, room, placement)
        else:
            self.check(
                label + " erreicht den freien Sollort",
                card.pos() == target
                and placement._measure_drag._place is not None
                and not placement._measure_drag._place.edge,
                evidence,
            )
        comparison = compare_prints(before, flow.scene_now())
        self.check(
            label + " verändert weder Dokument noch Transaktionen",
            comparison["same"]
            and len(window.session.project.document.transactions) == transactions,
            comparison,
        )
        return QPoint(card.pos()), asdict(placement._measure_drag._place)

    def outside_checks(
        self,
        flow: Any,
        label: str,
        evidence: dict[str, Any],
        card: Any,
        room: Any,
        placement: Any,
    ) -> None:
        """Was der Außenzug zusagt: Karte im Raum, Release-Folge, Zeiger beim Halten und danach."""
        transport = evidence["transport"]
        self.check(
            label + " Außenpunkt bei gebundener Karte",
            room.contains(card.geometry()) and placement._measure_drag._place is not None,
            evidence,
        )
        window_release = transport["window"]["release_index"]
        widget_release = transport["widget"]["release_index"]
        self.check(
            label + " Release zuerst am QWindow, danach am QWidget",
            window_release is not None
            and widget_release is not None
            and window_release < widget_release,
            transport,
        )
        expected = evidence["expected_move_cursor"]
        self.check(
            label + " Zugzeiger am Fenster des Druckempfängers",
            holds_move_cursor(evidence["cursor_held"], expected),
            evidence,
        )
        self.check(
            label + " Zeiger und Druck nach Release zurückgegeben",
            returns_cursor(
                evidence["cursor_before"],
                evidence["cursor_after"],
                pressed_after=evidence["pressed_after"],
                expected=expected,
            ),
            evidence,
        )
        # Nächste Kundengeste nach dem Außenrelease: derselbe echte Tooltipweg, kein Reset.
        self.hover_help(flow, lambda: self.fields()["diameter"], "Durchmesser nach Außenrelease")
        at_field = self.state["help"][-1].get("receiver_window_cursor")
        self.check(
            label + " Kartenfenster zeigt am nächsten Feld nicht mehr den Zugzeiger",
            at_field is not None and at_field != expected,
            {"at_field": at_field, "expected_move_cursor": expected},
        )
        self.capture(flow, "resize-aussenrelease-und-echte-hilfe")

    # --- Aufnahmen ------------------------------------------------------------

    def capture_state(self, flow: Any) -> dict[str, Any]:
        """Teilwerte derselben Aufnahmegrenze, ohne Ereignisse zu verarbeiten."""
        window = self.window
        session = window.session
        difference = window.viewport.difference
        placement = window._quiet_placement
        return {
            "turn": self.trace.turn,
            "restless": flow.restless,
            "display_ready": self.display_ready(),
            "result_present": session.last_result is not None,
            "session_busy": session.busy,
            "preview_workers": len(session._previews),
            "preview_timer": window._preview_busy.isActive(),
            "preview_reason": window._preview_reason,
            "scene_applied": window.viewport.is_scene_applied(session.last_result)
            if session.last_result is not None
            else False,
            "difference_present": difference is not None,
            "difference_applied": window.viewport.is_difference_applied(difference)
            if difference is not None
            else None,
            "overlay_moves": len(window.overlay._moves),
            "overlay_pending": window.overlay._pending,
            "placement": self.placement_state()
            if placement is not None and placement.active and placement._measure_group is not None
            else None,
        }

    def take(self, flow: Any, label: str) -> None:
        from tools.function_capture import field_entries

        window = self.window
        state = self.capture_state(flow)
        self.state.setdefault("capture_readiness", []).append(
            {"label": label, "phase": "unmittelbar vor Originalpixeln", **state}
        )
        self.persist()
        assert (
            state["restless"] is None
            and state["display_ready"]
            and not state["overlay_moves"]
            and state["overlay_pending"] is None
        ), f"Kein stabiler Aufnahmestand: {state}"
        image = self.out / f"{len(self.state['captures']) + 1:03d}-{label}.png"
        picture = window.screen().grabWindow(int(window.winId()))
        assert not picture.isNull() and picture.save(str(image))
        placement = window._quiet_placement
        measure = placement._measure_box if placement is not None and placement.active else None
        editors = (
            self.fields() if measure is not None and placement._measure_group is not None else {}
        )
        card = window.feature_dock
        scope = placement._measure_scope if placement is not None and placement.active else None
        focus = self.application.focusWidget()
        shot = {
            "label": label,
            "row": flow.row["id"],
            "turn": self.trace.turn,
            "monotonic": time.monotonic(),
            "image": image.name,
            "sha256": sha256_of(image),
            "pixels": [picture.width(), picture.height()],
            "dpr": picture.devicePixelRatio(),
            "window": widget_state(window),
            "viewport": widget_state(window.viewport),
            "card": widget_state(card),
            "measure": widget_state(measure),
            "scope": widget_state(scope),
            "placement": self.placement_state()
            if measure is not None and placement._measure_group is not None
            else None,
            "fields": {
                name: {
                    "outer": widget_state(editor),
                    "inners": [widget_state(inner) for inner in editor.findChildren(QLineEdit)],
                }
                for name, editor in editors.items()
            },
            "all_measure_inputs": field_entries(measure) if measure is not None else [],
            "all_measure_labels": [
                widget_state(label) for label in measure.findChildren(QLabel) if label.isVisible()
            ]
            if measure is not None
            else [],
            "measure_visible_field_names": sorted(
                name for name, editor in editors.items() if editor.isVisibleTo(measure)
            ),
            "catalog": widget_state(window.selection_operations.catalog_button),
            "feature_apply": widget_state(window.feature_panel._apply),
            "all_card_buttons": [
                widget_state(button)
                for button in card.findChildren(QPushButton)
                if button.isVisible()
            ],
            "all_card_labels": [
                widget_state(label) for label in card.findChildren(QLabel) if label.isVisible()
            ],
            "focus": widget_state(focus),
            "scene": flow.scene_now(),
            "transactions": len(window.session.project.document.transactions),
            "preview_workers": len(window.session._previews),
            "scene_applied": window.viewport.is_scene_applied(window.session.last_result),
            "difference_applied": window.viewport.is_difference_applied(window.viewport.difference)
            if window.viewport.difference is not None
            else None,
            "step_count": len(flow.data["steps"]),
            "event_count": len(self.trace.events),
            "performance_valid": False,
        }
        self.state["captures"].append(shot)
        self.persist()

    def capture(self, flow: Any, label: str, *, twice: bool = False) -> None:
        from tools.function_machine import Step

        window = self.window

        def one(name: str) -> None:
            still = flow.still_step("Ganzes Fenster steht still", lambda: window, at_most_s=12)
            last: dict[str, Any] = {"state": None}

            def ready() -> bool:
                stationary = still.ready()
                state = self.capture_state(flow)
                state["still_ready"] = stationary
                signature = dict(state)
                signature.pop("turn")
                if signature.get("placement") is not None:
                    signature["placement"] = dict(signature["placement"])
                    signature["placement"].pop("turn")
                if signature != last["state"]:
                    self.state.setdefault("capture_readiness", []).append(
                        {"label": name, "phase": "gemeinsame Bereitschaft", **state}
                    )
                    last["state"] = signature
                    self.persist()
                assert state["restless"] is None, f"Fläche bleibt unruhig: {state}"
                return bool(
                    stationary
                    and state["display_ready"]
                    and not state["overlay_moves"]
                    and state["overlay_pending"] is None
                )

            # ready und Aufnahme gehören zum selben Step: dazwischen läuft keine weitere Qt-Runde.
            self.walk(
                flow,
                name,
                [
                    flow.wait_step(
                        "Berechnung und Bild sind fertig", self.display_ready, timeout_s=60
                    ),
                    Step(
                        "Stillstand und Bereitschaft gemeinsam — Originalpixel aufnehmen",
                        lambda machine: self.take(flow, name),
                        ready=ready,
                        timeout_s=12,
                    ),
                ],
            )

        one(label)
        if twice:
            previous = self.state["captures"][-1]["turn"]
            self.walk(
                flow,
                label + "-ereignisfolge",
                [flow.wait_step("Neue Qt-Runde", lambda: self.trace.turn > previous, timeout_s=3)],
            )
            one(label + "-zweite-runde")
            self.check(
                label + " getrennte Ereignisrunden", self.state["captures"][-1]["turn"] > previous
            )

    # --- Klicks und Hilfen ------------------------------------------------------

    def button_step(self, flow: Any, getter: Callable[[], Any], label: str) -> Any:
        from tools.function_machine import Step
        from tools.function_walk import click_button

        ready = flow.walker.stable(label, button=getter)

        def act(machine: Any) -> None:
            button = getter()
            flow.walker.record(
                {
                    "target": label,
                    "before": widget_state(button),
                    "focus_before": widget_state(self.application.focusWidget()),
                }
            )
            assert click_button(flow.ports, flow.walker, button, label), f"Knopf verdeckt: {label}"
            flow.walker.record(
                {"target": label, "focus_after": widget_state(self.application.focusWidget())}
            )

        return Step(label, act, ready=ready, timeout_s=15)

    def click(self, flow: Any, getter: Callable[[], Any], label: str) -> None:
        self.walk(flow, label, [self.button_step(flow, getter, label)])
        # Ein letzter Step ist sofort done; dessen settle_ms wartet hier nicht.
        clicked_turn = self.trace.turn
        self.walk(
            flow,
            label + "-Anordnung",
            [
                flow.wait_step(
                    "Ereignisrunde nach dem Klick",
                    lambda: self.trace.turn > clicked_turn,
                    timeout_s=3,
                ),
                flow.still_step(
                    "Anordnung nach dem Klick steht still", lambda: self.window, at_most_s=12
                ),
            ],
        )
        assert flow.restless is None, "Anordnung nach dem Klick blieb unruhig"

    def hover_target(self, flow: Any, widget: Any, name: str) -> tuple[Any, Any, bool]:
        """Sichert Treffer und Abschneidung, bevor eine Erwartung den Lauf beendet."""
        point = widget.mapToGlobal(widget.rect().center())
        hit = flow.ports.widget_under(point)
        shown = QRect(widget.mapToGlobal(QPoint()), widget.size())
        chain = []
        owner = widget
        while owner is not None:
            state = widget_state(owner)
            assert state is not None
            state["visible_region"] = rectangle(owner.visibleRegion().boundingRect())
            if hasattr(owner, "verticalScrollBar"):
                bar = owner.verticalScrollBar()
                state["vertical_scroll"] = {
                    "value": bar.value(),
                    "minimum": bar.minimum(),
                    "maximum": bar.maximum(),
                }
                state["viewport"] = widget_state(owner.viewport())
            chain.append(state)
            shown = shown.intersected(QRect(owner.mapToGlobal(QPoint()), owner.size()))
            if owner.isWindow():
                break
            owner = owner.parentWidget()
        matches = hit is not None and (hit is widget or widget.isAncestorOf(hit))
        trace = {
            "target": name,
            "turn": self.trace.turn,
            "point": [point.x(), point.y()],
            "widget": widget_state(widget),
            "hit": widget_state(hit),
            "hit_matches": matches,
            "unclipped_by_parents": rectangle(shown),
            "centre_in_parent_clip": shown.contains(point),
            "ancestors": chain,
        }
        self.state.setdefault("hover_targets", []).append(trace)
        self.persist()
        return point, hit, matches

    def hover_help(self, flow: Any, getter: Callable[[], Any], name: str) -> None:
        """Echte Feldhilfe: weg, hin, sichtbarer Tooltip des Felds, Ereignisse am Ziel, Bild."""
        window, trace = self.window, self.trace
        bar = window.menuBar()
        away = bar.mapToGlobal(QPoint(bar.width() // 2, bar.height() // 2))
        away_hit = flow.ports.widget_under(away)
        assert (
            away_hit is not None
            and away_hit.window() is window
            and QApplication.activeWindow() is window
        )
        tip: dict[str, Any] = {"target": name, "events_from": len(trace.events)}
        self.state.setdefault("help", []).append(tip)
        trace.hover = name
        try:
            # Der echte QWidget-Weg bewegt den Cursor; ein QWindow-Move allein tut das nicht.
            flow.ports.move(away)
            cursor = QCursor.pos()
            tip["away"] = {
                "point": [away.x(), away.y()],
                "cursor": [cursor.x(), cursor.y()],
                "turn": trace.turn,
            }
            assert cursor == away, "Cursor hat den eigenen Wegpunkt nicht erreicht"
            self.walk(
                flow,
                name + " alte Hilfe verlassen",
                [
                    flow.wait_step(
                        "Kein altes Tooltipfenster sichtbar",
                        lambda: not QToolTip.isVisible(),
                        timeout_s=3,
                    )
                ],
            )
            self.settle_card(flow, name + " Hover-Ausgang steht")
            widget = getter()
            trace.hover_widget = widget
            point, hit, matches = self.hover_target(flow, widget, name)
            assert matches and QApplication.activeWindow() is window, f"Hilfeziel verdeckt: {name}"
            wanted = widget.toolTip()
            assert wanted
            tip["before"] = self.capture_state(flow)
            flow.walker.record(
                {
                    "target": name,
                    "gesture": "hover",
                    "point": [point.x(), point.y()],
                    "hit": flow.ports.describe(hit, point),
                }
            )
            flow.ports.move(point)
            until = time.monotonic() + 3.0
            while (
                not (QToolTip.isVisible() and QToolTip.text() == wanted)
                and time.monotonic() < until
            ):
                flow.pump()
            cursor = QCursor.pos()
            matched = QToolTip.isVisible() and QToolTip.text() == wanted and cursor == point
            handle = native_window_of(hit if hit is not None else widget)
            tip.update(
                visible=QToolTip.isVisible(),
                matches_requested_field=matched,
                text=QToolTip.text(),
                widget=widget_state(widget),
                turn=trace.turn,
                point=[point.x(), point.y()],
                cursor=[cursor.x(), cursor.y()],
                cursor_at_target=cursor == point,
                receiver_window_cursor=cursor_form(handle.cursor()) if handle is not None else None,
                receiver_window=window_identity(handle, window.windowHandle()),
            )
            events = trace.events[tip["events_from"] :]
            moved = next(
                (
                    index
                    for index, event in enumerate(events)
                    if event.get("at_hover_target")
                    and event["event_name"] == "MouseMove"
                    and event.get("buttons") == 0
                    and event.get("point") == tip["point"]
                ),
                None,
            )
            tooltip = next(
                (
                    index
                    for index, event in enumerate(events)
                    if moved is not None
                    and index > moved
                    and event.get("at_hover_target")
                    and event["event_name"] == "ToolTip"
                    and event.get("point") == tip["point"]
                ),
                None,
            )
            tip["target_events"] = {"move_index": moved, "tooltip_index": tooltip, "events": events}
            for number, top in enumerate(self.application.topLevelWidgets()):
                if top.isVisible() and top.windowType() == Qt.WindowType.ToolTip:
                    path = self.out / f"help-{len(self.state['help']):02d}-{number}.png"
                    picture = top.screen().grabWindow(int(top.winId()))
                    assert not picture.isNull() and picture.save(str(path))
                    tip.setdefault("images", []).append(
                        {
                            "image": path.name,
                            "sha256": sha256_of(path),
                            "pixels": [picture.width(), picture.height()],
                        }
                    )
            if not matched:
                self.state["unmeasured"].append(
                    {
                        "point": "native_hover_help",
                        "target": name,
                        "reason": "Überfahren erzeugte im begrenzten Beobachtungsfenster kein"
                        " passendes sichtbares Tooltipfenster mit tatsächlichem Cursor am Ziel;"
                        " Eigenschaftstext oder ein alter Tooltip sind kein Hover-Bildbeleg.",
                    }
                )
            elif tooltip is None or not tip.get("images"):
                self.state["unmeasured"].append(
                    {
                        "point": "native_hover_help",
                        "target": name,
                        "reason": "Der passende sichtbare Text ersetzt keinen vollständigen"
                        " Ziel-Empfänger- und Originalbildnachweis.",
                        "target_events": tip["target_events"],
                    }
                )
            self.check(
                name + " echte Feldhilfe nach Drag",
                matched and tooltip is not None and bool(tip.get("images")),
                tip,
            )
        finally:
            # Nur öffentlich wegbewegen, keinen Tooltip künstlich zeigen/verstecken.
            flow.ports.move(away)
            until = time.monotonic() + 3.0
            while QToolTip.isVisible() and time.monotonic() < until:
                flow.pump()
            tip["hidden_after_mouse_left"] = not QToolTip.isVisible()
            tip["events_until"] = len(trace.events)
            trace.hover = None
            trace.hover_widget = None
            self.persist()

    # --- Wege -----------------------------------------------------------------

    def check_front(self) -> None:
        placement = self.quiet()
        visible = {
            name
            for name, widget in self.fields().items()
            if widget.isVisibleTo(placement._measure_box)
        }
        scope = placement._measure_scope
        self.check(
            "Vorderseite umfasst Durchmesser, Tiefe und Sammelhaken",
            visible == {"diameter", "depth"}
            and scope is not None
            and scope.isVisibleTo(placement._measure_box),
            sorted(visible),
        )
        self.check(
            "Sammelhaken erklärt Wirkung und Undo",
            bool(scope.toolTip()) and scope.toolTip() == scope.accessibleDescription(),
        )
        self.check("Geschlossene Klappe", not self.measure_heading().isChecked())
        self.check(
            "Katalog ist während Maßgruppenauftrag zurückgestuft",
            not self.window.selection_operations.catalog_button.isDefault(),
        )

    def select_again(self, flow: Any) -> None:
        self.walk(
            flow,
            "Wiederauswahl über Körper und Merkmal",
            [flow.walker.step("tree.row:obj_1"), *flow.path_steps()],
        )
        self.capture(flow, "resize-wiederauswahl")
        self.check_front()
        self.check(
            "Neuer Maßauftrag übernimmt keinen Nutzerort",
            self.quiet()._measure_drag._place is None,
            self.placement_state(),
        )

    def accept_and_undo(self, flow: Any, *, scope: bool, compensate: bool) -> None:
        from app.core.geom.prepare import bore_diameter
        from tools.function_protocol import compare_prints

        window = self.window
        suffix = "sammel" if scope else "einzeln"
        self.select_again(flow)
        placement = self.quiet()
        diameter = self.fields()["diameter"]
        wanted = diameter.value_mm() + 0.5
        before = flow.scene_now()
        document = window.session.project.document
        op_count, transactions = len(document.ops), len(document.transactions)
        body_id = window.object_tree.selected()
        hole_id = window.object_tree.selected_feature()
        group = window.feature_panel.measure_group("resize_hole")
        assert group is not None and body_id is not None and hole_id is not None
        members = {str(member.target) for member in group.members}
        self.check("Vier vorhandene Gruppenmitglieder", len(members) == 4, sorted(members))
        targets = members if scope else {str(hole_id)}
        if placement._measure_scope.isChecked() != scope:
            self.click(flow, lambda: self.quiet()._measure_scope, "Maßgruppen-Sammelhaken")
        self.click(flow, self.measure_heading, "Weitere Werte öffnen")
        if self.fields()["compensate"].isChecked() != compensate:
            self.click(flow, lambda: self.fields()["compensate"], "Druckabweichung ausgleichen")
        self.capture(flow, suffix + "-rueckseite")
        self.click(flow, self.measure_heading, "Weitere Werte schließen")
        self.walk(
            flow,
            suffix + "-Zielmaß tippen",
            flow.input_steps({"feature.field:resize_hole.diameter": wanted}),
        )
        self.walk(
            flow,
            suffix + "-Übernahme bereit",
            [
                flow.wait_step(
                    "Vorschau fertig und Übernehmen frei",
                    lambda: self.display_ready() and self.quiet()._measure_accept.isEnabled(),
                    timeout_s=60,
                )
            ],
        )
        self.check(
            "Verdeckte Korrektur bleibt gebunden",
            window._quiet_host.values()["compensate"] is compensate,
        )
        self.capture(flow, suffix + "-vor-uebernehmen")
        self.click(flow, lambda: self.quiet()._measure_accept, "placement_measure_accept")
        self.walk(
            flow,
            suffix + "-Transaktion",
            [
                flow.wait_step(
                    "Eine neue Transaktion ist gerechnet",
                    lambda: self.display_ready() and len(document.transactions) == transactions + 1,
                    timeout_s=60,
                )
            ],
        )
        appended = document.ops[op_count:]
        self.check(
            suffix + " richtige Ziele",
            len(appended) == len(targets)
            and {str(op.params["at_feature"]) for op in appended} == targets,
        )
        self.check(
            suffix + " Korrekturparameter",
            all(op.params["compensate"] is compensate for op in appended),
        )
        body = window.session.last_result.scene.objects[body_id]
        expected = bore_diameter(wanted, window.session.evaluation_profile, compensate)
        actual = {target: float(body.features[target].params["diameter"]) for target in targets}
        # Wie pytest.approx im gebundenen fachlichen Gegenfall: relativ 1e-6, absolut 1e-12.
        self.check(
            suffix + " tatsächliche Durchmesser",
            all(
                math.isclose(value, expected, rel_tol=1e-6, abs_tol=1e-12)
                for value in actual.values()
            ),
            {
                "expected": expected,
                "actual": actual,
                "wanted": wanted,
                "material_profile": window.session.evaluation_profile,
            },
        )
        self.capture(flow, suffix + "-uebernommen")
        self.walk(
            flow,
            suffix + "-einmal-Strg-Z",
            [
                flow.key_step(flow.undo_keys(), "Strg+Z"),
                flow.wait_step(
                    "Undo ist gerechnet",
                    lambda: self.display_ready() and len(document.ops) == op_count,
                    timeout_s=60,
                ),
            ],
        )
        comparison = compare_prints(before, flow.scene_now())
        self.check(
            suffix + " ein Undo stellt Dokument und Geometrie her", comparison["same"], comparison
        )
        self.capture(flow, suffix + "-undo")

    def bore_route(self, flow: Any) -> None:
        from app.core.registry import REGISTRY
        from tools.function_protocol import compare_prints

        window = self.window
        self.walk(flow, "Bohrungsweg", flow.path_steps())
        self.capture(flow, "resize-vorderseite", twice=True)
        self.check_front()
        before = flow.scene_now()
        transactions = len(window.session.project.document.transactions)
        diameter = self.fields()["diameter"].value_mm()
        self.drag_card(flow, free_surface=False, fraction=(0.25, 0.18), outside=True)
        self.drag_card(flow, free_surface=False, fraction=(0.25, 0.18))
        anchor, place = self.drag_card(flow, free_surface=True, fraction=(0.55, 0.28))
        input_start = len(self.trace.events)
        self.walk(
            flow,
            "Abbruchentwurf am neuen Ort tippen",
            flow.input_steps({"feature.field:resize_hole.diameter": diameter + 0.5}),
        )
        self.settle_card(flow, "Feld am neuen Ort ist fertig")
        focus = self.application.focusWidget()
        editor = self.fields()["diameter"]
        self.check(
            "Feld am neuen Ort empfängt die Eingabe",
            math.isclose(editor.value_mm(), diameter + 0.5)
            and (focus is editor or editor.isAncestorOf(focus))
            and any(event["event_name"] == "KeyPress" for event in self.trace.events[input_start:]),
            {
                "focus": widget_state(focus),
                "editor": widget_state(editor),
                "events": self.trace.events[input_start:],
            },
        )
        self.check_manual_place(anchor, place, "Feldänderung")
        self.click(flow, self.measure_heading, "Weitere Werte öffnen")
        self.settle_card(flow, "Geöffnete Karte am neuen Ort steht")
        self.check_manual_place(anchor, place, "Aufklappen")
        self.capture(flow, "resize-rueckseite-vor-hover")
        specs = {field.name: field for field in REGISTRY.get("resize_hole").params.spec()}
        for name in ("entrance_mode", "compensate"):
            editor = self.fields()[name]
            meaning = str(specs[name].doc)
            self.check(
                name + " Hilfe am sichtbaren Feld",
                editor.isVisible()
                and bool(meaning)
                and editor.toolTip().startswith(meaning)
                and editor.accessibleDescription() == editor.toolTip(),
            )
            self.hover_help(flow, lambda name=name: self.fields()[name], name)
        self.hover_help(flow, lambda: self.quiet()._measure_scope, "Sammelhaken")
        self.capture(flow, "resize-rueckseite")
        if not self.fields()["compensate"].isChecked():
            self.click(
                flow,
                lambda: self.fields()["compensate"],
                "Druckkorrektur für verworfenen Entwurf einschalten",
            )
        self.click(flow, self.measure_heading, "Weitere Werte schließen")
        self.settle_card(flow, "Geschlossene Karte am neuen Ort steht")
        self.check_manual_place(anchor, place, "Zuklappen")
        self.capture(flow, "resize-feld-und-klappe-am-neuen-ort")
        self.capture(flow, "resize-vor-abbrechen")
        event_start = len(self.trace.events)
        self.click(flow, lambda: self.quiet()._measure_cancel, "placement_measure_cancel")
        self.walk(
            flow,
            "Tatsächlicher Abbrechen-Rückweg",
            [
                flow.wait_step(
                    "Maßgruppe beendet und Auswahl aufgehoben",
                    lambda: (
                        window._quiet_placement is None
                        and window.object_tree.selected_feature() is None
                        and self.display_ready()
                    ),
                    timeout_s=30,
                )
            ],
        )
        events = self.trace.events[event_start:]
        for kind in ("MouseButtonPress", "MouseButtonRelease"):
            self.check(
                "Abbrechen empfing " + kind,
                any(
                    event["event_name"] == kind and "placement_measure_cancel" in event["ancestors"]
                    for event in events
                ),
                events,
            )
        comparison = compare_prints(before, flow.scene_now())
        self.check(
            "Abbrechen lässt Dokument und Geometrie unverändert", comparison["same"], comparison
        )
        self.check(
            "Abbrechen legt keine Transaktion an",
            len(window.session.project.document.transactions) == transactions,
        )
        self.check(
            "Abbrechen stellt Katalogpriorität wieder her",
            window.selection_operations.catalog_button.isDefault()
            and not window.feature_panel._apply.isVisibleTo(window.feature_dock),
        )
        self.capture(flow, "resize-nach-abbrechen", twice=True)
        self.accept_and_undo(flow, scope=False, compensate=False)
        self.accept_and_undo(flow, scope=True, compensate=True)

    def right_route(self, flow: Any) -> None:
        window = self.window
        row = flow.row["id"]
        self.walk(flow, row + "-Kundenweg", flow.path_steps())
        self.capture(flow, row + "-ganze-karte")
        catalog = window.selection_operations.catalog_button
        apply = window.feature_panel._apply
        self.check(
            row + " rechte Karte hat eine führende Aktion",
            catalog.isVisibleTo(window.feature_dock)
            and apply.isVisibleTo(window.feature_dock)
            and apply.isDefault()
            and not catalog.isDefault(),
        )
        self.walk(flow, "Körperauswahl über echten Baumklick", [flow.walker.step("tree.row:obj_1")])
        self.capture(flow, row + "-koerper-rueckweg")
        self.check(row + " Katalog führt nach Körperauswahl", catalog.isDefault())

    # --- Ablauf ---------------------------------------------------------------

    def run(
        self,
        *,
        rows: list[dict[str, Any]],
        scenes: Path,
        screen: str,
        head: str,
        leave: Callable[[], None],
        platform_name: str = "windows",
    ) -> int:
        """Alle Zeilen der Folge in diesem Prozess; danach Abbau und Siegel, immer.

        Auch die Importe stehen im ``try``: Scheitert einer, nennt
        ``observation.json`` den Grund, und das Siegel wird trotzdem geprüft.
        ``platform_name`` ist am echten Schirm ``windows``; nur ``offscreen``
        verzichtet auf den Renderer, den es dort nicht gibt — eine Rauchprobe
        der Mechanik, nie ein Bildnachweis.
        """
        exit_code = 0
        try:
            from app.core.bootstrap import load_operations
            from app.ui.app import build_application
            from tools.file_acceptance import no_native_dialogs
            from tools.function_bench import FunctionFlow
            from tools.function_protocol import empty_protocol
            from tools.function_setup import Variant, apply_licence, write_profile

            if [row["id"] for row in rows] != list(CARD_ROWS):
                raise ValueError(f"Die Folge braucht genau die Zeilen {', '.join(CARD_ROWS)}.")
            language = self.state["language"]
            variant = Variant(
                set="sprachen", language=language, theme="light", unit="mm", screen=screen
            )
            write_profile(variant)
            load_operations()
            apply_licence(variant.licence)
            no_native_dialogs()
            self.application, self.window = build_application([])
            self.application.setQuitOnLastWindowClosed(False)
            assert self.application.platformName() == platform_name, (
                f"Plattform {self.application.platformName()}, verlangt {platform_name}"
            )
            self.trace = InputTrace(self.window, self.out)
            self.application.installEventFilter(self.trace)
            for row in rows:
                data = empty_protocol(
                    row,
                    variant.protocol(None, (0, 0)),
                    {"commit": head, "app": "native Maßkartenfolge"},
                )
                data["performance_valid"] = False
                self.current = FunctionFlow(
                    self.application,
                    self.window,
                    self.out,
                    data,
                    self.persist,
                    row,
                    variant,
                    scenes,
                    bench=dict(NO_REFERENCE),
                    out=self.out.parent,
                )
                flow = self.current
                flow.prepare()
                # Der Konstruktor braucht einen Faktor; diese Probe gibt ihn nicht als Messung aus.
                flow.data["frames"] = {"reference_factor": None, "reason": "keine Leistungsprobe"}
                shown = self.window.screen()
                self.check(
                    "Verlangter Schirm",
                    screen.lower() in f"{shown.name()} {shown.model()}".lower(),
                    {"screen": screen, "name": shown.name(), "model": shown.model()},
                )
                self.check(
                    "Gültiger logischer Schirmvertrag",
                    shown.geometry().width() >= 1920 and shown.geometry().height() >= 1080,
                    rectangle(shown.geometry()),
                )
                assert platform_name == "offscreen" or self.window.viewport.renderer is not None, (
                    "Echter Renderer fehlt"
                )
                assert flow.reset(), "Originale Startszene ist nicht hergestellt"
                self.state["row_started"] = row["id"]
                self.persist()
                if row["id"] == "resize_hole":
                    self.bore_route(flow)
                else:
                    self.right_route(flow)
                flow.finish()
                self.state["rows_done"].append(row["id"])
                self.state["row_started"] = None
                self.persist()
            self.state["execution_complete"] = True
        except Exception:
            exit_code = 1
            self.state["execution_complete"] = False
            self.state["exception"] = traceback.format_exc()
        finally:
            try:
                if self.current is not None:
                    self.current.finish()
                if self.trace is not None:
                    self.application.removeEventFilter(self.trace)
                    self.trace.timer.stop()
                if self.window is not None:
                    from tools.window_bench import shutdown_window

                    self.window.session.forget_changes()
                    shutdown_window(self.window, self.application)
                self.state["shutdown_complete"] = True
                leave()
                self.state["source_pins_unchanged"] = True
            except Exception:
                exit_code = 1
                self.state["shutdown_or_binding_exception"] = traceback.format_exc()
            self.state["exit"] = exit_code
            self.persist()
        return exit_code


def transport_of(
    events: list[dict[str, Any]], targets: list[list[int]]
) -> dict[str, dict[str, Any]]:
    """Je Ebene (Fenster, Widget) die vier gehaltenen Bewegungen und das Release danach."""
    transport: dict[str, dict[str, Any]] = {}
    for level in ("window", "widget"):
        last_index = -1
        moves: list[int] = []
        for target_point in targets:
            found = next(
                (
                    index
                    for index, event in enumerate(events)
                    if index > last_index
                    and event["receiver_level"] == level
                    and event["event_name"] == "MouseMove"
                    and event.get("buttons", 0) & LEFT
                    and event.get("point") == target_point
                ),
                None,
            )
            if found is None:
                break
            moves.append(found)
            last_index = found
        release = next(
            (
                index
                for index, event in enumerate(events)
                if index > last_index
                and event["receiver_level"] == level
                and event["event_name"] == "MouseButtonRelease"
                and event.get("button") == str(Qt.MouseButton.LeftButton)
                and event.get("buttons") == 0
                and targets
                and event.get("point") == targets[-1]
            ),
            None,
        )
        transport[level] = {"move_indices": moves, "release_index": release}
    return transport


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
