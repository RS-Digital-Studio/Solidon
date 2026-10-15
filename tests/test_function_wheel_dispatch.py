"""Radereignisse nehmen den Qt-Weg über ignorierende Kinder und Rollbereiche."""

from collections.abc import Iterator
from typing import Any, override

import pytest
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QToolButton, QWidget

from tools.function_guard import forbidden_calls
from tools.function_walk import QtPorts


def test_guard_accepts_public_wheel_dispatcher() -> None:
    assert forbidden_calls("QTest.wheelEvent(handle, point, delta)") == []


@pytest.mark.parametrize(
    "source",
    [
        "widget.wheelEvent(event)",
        "other.wheelEvent(event)",
        "getattr(QTest, 'wheelEvent')(handle, point, delta)",
        "wheel = widget.wheelEvent\nwheel(event)",
    ],
)
def test_guard_still_rejects_handlers_and_dynamic_dispatch(source: str) -> None:
    assert forbidden_calls(source)


class WheelButton(QToolButton):
    """Notiert den echten Empfang und nimmt wahlweise das Rad an."""

    def __init__(self, parent: QWidget, accepts: bool = False) -> None:
        super().__init__(parent)
        self.accepts = accepts
        self.received: list[dict[str, Any]] = []

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        self.received.append(
            {
                "local": event.position().toPoint(),
                "global": event.globalPosition().toPoint(),
                "angle": event.angleDelta(),
                "pixels": event.pixelDelta(),
                "modifiers": event.modifiers(),
                "buttons": event.buttons(),
                "phase": event.phase(),
                "spontaneous": event.spontaneous(),
            }
        )
        if self.accepts:
            event.accept()
        else:
            super().wheelEvent(event)


class WheelArea(QScrollArea):
    """Zählt tatsächliche Radempfänge, die Qt selbst zum Bereich weiterreicht."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.received = 0

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        self.received += 1
        super().wheelEvent(event)


type WheelScene = tuple[QWidget, WheelArea, QWidget]


@pytest.fixture
def wheel_scene(qt_app: object) -> Iterator[WheelScene]:
    """Ein echter Widgetbaum ohne Renderer oder native Bildschirmmessung."""
    top = QWidget()
    top.resize(540, 440)
    top.move(149, 127)
    outer = WheelArea(top)
    outer.setGeometry(31, 27, 420, 320)
    content = QWidget()
    content.resize(380, 900)
    outer.setWidget(content)
    try:
        yield top, outer, content
    finally:
        top.close()
        top.deleteLater()
        QApplication.processEvents()


def test_missing_dispatcher_reports_pinned_environment(
    wheel_scene: WheelScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    top, outer, content = wheel_scene
    button = WheelButton(content)
    button.setGeometry(23, 19, 170, 45)
    top.show()
    QApplication.processEvents()
    monkeypatch.delattr(QTest, "wheelEvent")
    with pytest.raises(RuntimeError, match=r"Qt 6\.8.*tools/check_env\.py.*constraints\.txt"):
        QtPorts(top, 0.0).press(button, button.mapToGlobal(QPoint(13, 11)), "wheel_down")
    assert not button.received
    assert outer.received == 0


@pytest.mark.parametrize("native_child", [False, True])
def test_ignored_button_reaches_surrounding_scroll_area(
    wheel_scene: WheelScene, native_child: bool
) -> None:
    top, outer, content = wheel_scene
    if native_child:
        outer.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
    button = WheelButton(content)
    button.setGeometry(23, 19, 170, 45)
    top.show()
    QApplication.processEvents()
    assert outer.verticalScrollBar().maximum() > 0
    assert outer.verticalScrollBar().value() == 0
    QtPorts(top, 0.0).press(button, button.mapToGlobal(QPoint(13, 11)), "wheel_down")
    QApplication.processEvents()
    assert outer.verticalScrollBar().value() > 0
    assert outer.received == 1
    assert len(button.received) == 1
    assert button.received[0]["spontaneous"]


@pytest.mark.parametrize("scrollable", [False, True])
def test_nested_scroll_areas_respect_acceptance(wheel_scene: WheelScene, scrollable: bool) -> None:
    top, outer, content = wheel_scene
    inner = WheelArea(content)
    inner.setGeometry(25, 18, 320, 190)
    inner_content = QWidget()
    inner_content.resize(270, 700 if scrollable else 100)
    inner.setWidget(inner_content)
    button = WheelButton(inner_content)
    button.setGeometry(11, 17, 170, 45)
    top.show()
    QApplication.processEvents()
    assert (inner.verticalScrollBar().maximum() > 0) is scrollable
    assert outer.verticalScrollBar().maximum() > 0
    QtPorts(top, 0.0).press(button, button.mapToGlobal(QPoint(15, 12)), "wheel_down")
    QApplication.processEvents()
    assert len(button.received) == 1
    assert inner.received == 1
    assert (inner.verticalScrollBar().value() > 0) is scrollable
    assert (outer.verticalScrollBar().value() > 0) is not scrollable
    assert outer.received == (0 if scrollable else 1)


@pytest.mark.parametrize("direction, delta", [("wheel_up", 120), ("wheel_down", -120)])
@pytest.mark.parametrize(
    "prefix, modifiers",
    [
        ("", Qt.KeyboardModifier.NoModifier),
        ("ctrl+", Qt.KeyboardModifier.ControlModifier),
        ("shift+", Qt.KeyboardModifier.ShiftModifier),
        ("alt+", Qt.KeyboardModifier.AltModifier),
        (
            "ctrl+shift+alt+",
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.AltModifier,
        ),
    ],
)
def test_accepting_receiver_gets_one_event_with_real_coordinates(
    wheel_scene: WheelScene,
    direction: str,
    delta: int,
    prefix: str,
    modifiers: Qt.KeyboardModifier,
) -> None:
    top, outer, content = wheel_scene
    button = WheelButton(content, accepts=True)
    button.setGeometry(47, 29, 170, 45)
    top.show()
    QApplication.processEvents()
    local = QPoint(17, 13)
    point = button.mapToGlobal(local)
    assert QApplication.widgetAt(point) is button
    assert point != local
    QtPorts(top, 0.0).press(button, point, prefix + direction)
    QApplication.processEvents()
    assert len(button.received) == 1
    event = button.received[0]
    assert event["local"] == local
    assert event["global"] == point
    assert event["angle"] == QPoint(0, delta)
    assert event["pixels"].isNull()
    assert event["modifiers"] == modifiers
    assert event["buttons"] == Qt.MouseButton.NoButton
    assert event["phase"] == Qt.ScrollPhase.NoScrollPhase
    assert outer.verticalScrollBar().value() == 0
    assert outer.received == 0


class NavigationPorts(QtPorts):
    """Echte Eingabeports; der kleine Radbaum besitzt keine Hauptfensterzonen."""

    @override
    def zone_of(self, widget: Any) -> str | None:
        return None


class WheelObserver(QObject):
    """Passiver Beleg der Radwinkel am tatsächlichen Scrollbar-Empfänger."""

    def __init__(self, area: QScrollArea) -> None:
        super().__init__(area)
        self.angles: list[int] = []
        area.verticalScrollBar().installEventFilter(self)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(event, QWheelEvent):
            self.angles.append(event.angleDelta().y())
        return False


def _navigation_target(parent: QWidget, *, container: bool = False) -> QWidget:
    """Markiert das echte Ziel im vorhandenen Radaufbau; kein Navigator-Ersatz."""
    from app.core import guides

    target = QWidget(parent) if container else WheelButton(parent)
    target.setProperty(guides.TARGET_PROPERTY, "setting:probe")
    return target


def _target_in(target: QWidget, area: QScrollArea) -> QRect:
    """Das ganze Ziel im lokalen Sichtbereich, unabhängig vom Navigator abgelesen."""
    return QRect(target.mapTo(area.viewport(), QPoint(0, 0)), target.size())


def _roll_next(ports: QtPorts, name: str = "setting:probe") -> dict[str, Any]:
    """Genau ein angesagter Radschritt über den öffentlichen Fensterdispatcher."""
    step = ports.next_click(name)
    assert step.why == "rollen"
    point = step.rect.center()
    hit = ports.widget_under(point)
    assert hit is not None and ports.covers(step, hit)
    from tools.function_walk import Walk

    records: list[dict[str, Any]] = []
    assert Walk(ports, records, 0.0).click_once(name) == "rollen"
    QApplication.processEvents()
    return records[-1]


@pytest.mark.parametrize("edge", ["top", "bottom"])
def test_navigation_reveals_the_whole_fitting_field(wheel_scene: WheelScene, edge: str) -> None:
    """FD77: Treffbare Mitte reicht nicht, wenn noch eine Feldkante abgeschnitten ist."""
    top, outer, content = wheel_scene
    target = _navigation_target(content)
    target.setGeometry(23, 20, 170, 28)
    top.show()
    QApplication.processEvents()
    bar = outer.verticalScrollBar()
    if edge == "top":
        bar.setValue(30)  # Nur Ausgangsaufbau; der geprüfte Weg benutzt das Rad.
    else:
        target.move(23, outer.viewport().height() - 16)
    QApplication.processEvents()
    shown = outer.viewport().rect()
    before = _target_in(target, outer)
    assert shown.contains(before.center()) and not shown.contains(before)
    ports = NavigationPorts(top, 0.0)
    value = bar.value()
    step = ports.next_click("setting:probe")
    assert (step.why, step.direction) == ("rollen", -1 if edge == "top" else 1)
    assert bar.value() == value, "Die Navigation darf nicht selbst rollen."
    _roll_next(ports)
    assert bar.value() != value
    assert ports.next_click("setting:probe").why == "ziel"
    assert shown.contains(_target_in(target, outer))


def test_navigation_does_not_roll_a_fully_visible_field(wheel_scene: WheelScene) -> None:
    """Voll sichtbare Felder benötigen keinen zusätzlichen Wegschritt."""
    top, outer, content = wheel_scene
    target = _navigation_target(content)
    target.setGeometry(23, 20, 170, 28)
    top.show()
    QApplication.processEvents()
    assert outer.viewport().rect().contains(_target_in(target, outer))
    assert QtPorts(top, 0.0).next_click("setting:probe").why == "ziel"
    assert outer.received == 0 and outer.verticalScrollBar().value() == 0


def test_navigation_reveals_the_field_through_the_outer_clip(wheel_scene: WheelScene) -> None:
    """Die innere Sichtfläche enthält das Feld ganz, die äußere erst nach dem Radschritt."""
    top, outer, content = wheel_scene
    inner = WheelArea(content)
    inner.setGeometry(25, 180, 320, 190)
    inner_content = QWidget()
    inner_content.resize(270, 180)
    inner.setWidget(inner_content)
    target = _navigation_target(inner_content)
    target.setGeometry(11, 100, 170, 28)
    top.show()
    QApplication.processEvents()
    delta = outer.viewport().height() - 16 - _target_in(target, outer).top()
    target.move(target.x(), target.y() + delta)
    QApplication.processEvents()
    assert inner.verticalScrollBar().maximum() == 0
    assert inner.viewport().rect().contains(_target_in(target, inner))
    assert outer.viewport().rect().contains(_target_in(target, outer).center())
    assert not outer.viewport().rect().contains(_target_in(target, outer))
    ports = NavigationPorts(top, 0.0)
    _roll_next(ports)
    assert outer.verticalScrollBar().value() > 0
    assert inner.verticalScrollBar().value() == 0
    assert ports.next_click("setting:probe").why == "ziel"
    assert all(area.viewport().rect().contains(_target_in(target, area)) for area in (inner, outer))


def test_oversized_container_keeps_the_finite_centre_route(wheel_scene: WheelScene) -> None:
    """Große Behälter bleiben erreichbar; das behauptet ausdrücklich keine Vollsicht."""
    from tools.function_walk import MOST_WAY_CLICKS

    top, outer, content = wheel_scene
    target = _navigation_target(content, container=True)
    top.show()
    QApplication.processEvents()
    target.setGeometry(23, outer.viewport().height(), 170, outer.viewport().height() + 80)
    QApplication.processEvents()
    assert target.height() > outer.viewport().height()
    ports = NavigationPorts(top, 0.0)
    for _index in range(MOST_WAY_CLICKS):
        if ports.next_click("setting:probe").why == "ziel":
            break
        _roll_next(ports)
    assert ports.next_click("setting:probe").why == "ziel"
    assert outer.verticalScrollBar().value() > 0
    assert outer.viewport().rect().contains(_target_in(target, outer).center())
    assert not outer.viewport().rect().contains(_target_in(target, outer))


def test_fitting_field_at_scroll_end_is_not_reported_as_visible(wheel_scene: WheelScene) -> None:
    """Am Anschlag wird ein weiterhin abgeschnittenes Feld kein erfolgreicher Zielklick."""
    from app.ui.guide_targets import MissingTargetError

    top, outer, content = wheel_scene
    target = _navigation_target(content)
    target.setGeometry(23, content.height() - 16, 170, 28)
    top.show()
    QApplication.processEvents()
    bar = outer.verticalScrollBar()
    bar.setValue(bar.maximum())  # Stellt nur den ausdrücklich zu prüfenden Anschlag her.
    QApplication.processEvents()
    assert target.height() <= outer.viewport().height()
    assert outer.viewport().rect().contains(_target_in(target, outer).center())
    assert not outer.viewport().rect().contains(_target_in(target, outer))
    for _index in range(2):
        with pytest.raises(MissingTargetError, match=r"setting:probe.*Rollanschlag"):
            QtPorts(top, 0.0).next_click("setting:probe")
    assert bar.value() == bar.maximum() and outer.received == 0


def test_two_scrollable_areas_reveal_the_whole_target_without_turning_back(
    wheel_scene: WheelScene, record_property: Any
) -> None:
    """RF77-M1: H80 in H100 braucht den äußeren Empfänger und einen kurzen Radweg."""
    from tools.function_walk import MOST_WAY_CLICKS

    top, outer, content = wheel_scene
    outer.resize(420, 102)
    inner = WheelArea(content)
    inner.setGeometry(25, 49, 320, 202)
    inner_content = QWidget()
    inner_content.resize(270, 700)
    inner.setWidget(inner_content)
    target = _navigation_target(inner_content)
    target.setGeometry(11, 0, 170, 80)
    top.show()
    QApplication.processEvents()
    assert outer.viewport().height() == 100 and inner.viewport().height() == 200
    assert target.height() == 80
    assert all(area.verticalScrollBar().maximum() > 0 for area in (inner, outer))
    assert inner.viewport().rect().contains(_target_in(target, inner))
    assert outer.viewport().rect().contains(_target_in(target, outer).center())
    assert not outer.viewport().rect().contains(_target_in(target, outer))
    ports = NavigationPorts(top, 0.0)
    inner_events, outer_events = WheelObserver(inner), WheelObserver(outer)
    trace = []
    for _index in range(MOST_WAY_CLICKS):
        if ports.next_click("setting:probe").why == "ziel":
            break
        before = (inner.verticalScrollBar().value(), outer.verticalScrollBar().value())
        row = _roll_next(ports)
        after = (inner.verticalScrollBar().value(), outer.verticalScrollBar().value())
        trace.append(
            {
                "before": before,
                "after": after,
                "event": row,
                "target": _target_in(target, outer).getRect(),
            }
        )
    record_property("wheel_trace", str(trace))
    record_property("received_angles", str(outer_events.angles))
    assert trace, "Die treffbare Mitte ist noch kein vollständig sichtbares Feld."
    assert ports.next_click("setting:probe").why == "ziel", trace
    assert inner.verticalScrollBar().value() == 0, trace
    assert outer.verticalScrollBar().value() > 0, trace
    assert all(
        area.viewport().rect().contains(_target_in(target, area)) for area in (inner, outer)
    ), trace
    assert all(row["event"]["widget_at"]["class"] == "QScrollBar" for row in trace)
    assert all(row["after"][1] > row["before"][1] for row in trace), trace
    assert not inner_events.angles
    assert outer_events.angles == [-row["event"]["wheel_angle"] for row in trace]


@pytest.mark.parametrize("step", [0, 10000])
def test_unusable_scroll_step_does_not_send_input(wheel_scene: WheelScene, step: int) -> None:
    """Kein ungerichteter Versuch bei fehlender Schrittgröße oder zu grobem Restweg."""
    from app.ui.guide_targets import MissingTargetError

    top, outer, content = wheel_scene
    outer.resize(420, 102)
    target = _navigation_target(content)
    target.setGeometry(23, 22, 170, 80)
    top.show()
    QApplication.processEvents()
    bar = outer.verticalScrollBar()
    bar.setSingleStep(step)
    assert outer.viewport().height() == 100
    assert outer.viewport().rect().contains(_target_in(target, outer).center())
    assert not outer.viewport().rect().contains(_target_in(target, outer))
    with pytest.raises(MissingTargetError):
        NavigationPorts(top, 0.0).next_click("setting:probe")
    assert bar.value() == 0 and outer.received == 0


@pytest.mark.parametrize("missing", [1, 2, 19, 30])
def test_short_wheel_remainder_stops_with_both_edges_visible(
    wheel_scene: WheelScene, missing: int, record_property: Any
) -> None:
    """Auch eine einzelne fehlende Pixelzeile braucht eine echte kurze Radeingabe."""
    top, outer, content = wheel_scene
    outer.resize(420, 102)
    target = _navigation_target(content)
    target.setGeometry(23, 20 + missing, 170, 80)
    top.show()
    QApplication.processEvents()
    observer = WheelObserver(outer)
    ports = NavigationPorts(top, 0.0)
    before = _target_in(target, outer)
    assert before.bottom() - outer.viewport().rect().bottom() == missing
    row = _roll_next(ports)
    after = _target_in(target, outer)
    record_property(
        "short_wheel",
        str(
            {
                "before": before.getRect(),
                "after": after.getRect(),
                "event": row,
                "received": observer.angles,
            }
        ),
    )
    assert 0 < row["wheel_angle"] < 120
    assert row["widget_at"]["class"] == "QScrollBar"
    assert observer.angles == [-row["wheel_angle"]]
    assert outer.verticalScrollBar().value() == missing
    assert outer.viewport().rect().contains(after)
    assert ports.next_click("setting:probe").why == "ziel"


@pytest.mark.parametrize("angle", [0, -1])
def test_invalid_wheel_angle_does_not_even_move_the_pointer(
    wheel_scene: WheelScene, monkeypatch: pytest.MonkeyPatch, angle: int
) -> None:
    """Der Port lehnt ungültige Mengen vor jedem Eingabeereignis ab."""
    top, outer, content = wheel_scene
    moves = []
    monkeypatch.setattr(QTest, "mouseMove", lambda *args: moves.append(args))
    with pytest.raises(ValueError, match="positiv"):
        QtPorts(top, 0.0).press(content, QPoint(), "wheel_down", wheel_angle=angle)
    assert not moves and outer.received == 0


@pytest.mark.parametrize("angle", [30, 120])
def test_fake_walk_preserves_the_positive_wheel_amount(angle: int) -> None:
    """Der gleiche optionale Winkelvertrag läuft auch durch den kopflosen Walk-Anschluss."""
    from tests.bench_fakes import FakeClick, FakePorts, FakeTimer, FakeWidget
    from tools.function_walk import Walk

    widget = FakeWidget("rolle")
    click = FakeClick((0, 0, 20, 20), "left", "rollen", widget, 1, angle)
    ports = FakePorts(FakeTimer(), {"probe": [click]})
    rows = []
    assert Walk(ports, rows, 0.0).click_once("probe") == "rollen"
    assert ports.wheel_angles == [angle]
    assert rows[0]["wheel_angle"] == angle
    assert ports.pressed[0][2] == "wheel_down"


@pytest.mark.parametrize("kind", ["field", "feature.field", "measure.field"])
def test_scrolling_a_value_field_keeps_the_scrollbar_receiver(
    wheel_scene: WheelScene, kind: str, record_property: Any
) -> None:
    """Der Rollweg eines ValueField darf nicht zu dessen Zahlenkästchen umgelenkt werden."""
    from app.core import guides
    from app.core.types import ParamSpec
    from app.ui.op_dialog import ValueField

    top, outer, content = wheel_scene
    outer.resize(420, 102)
    target = ValueField(ParamSpec("length", "float", "Länge", default=5.0), parent=content)
    name = f"{kind}:probe.length" if kind == "feature.field" else f"{kind}:length"
    target.setProperty(guides.TARGET_PROPERTY, name)
    target.setGeometry(23, 91, 300, 28)
    top.show()
    QApplication.processEvents()
    target.move(target.x(), outer.viewport().height() - target.height() + 9)
    QApplication.processEvents()
    ports = NavigationPorts(top, 0.0)
    observer = WheelObserver(outer)
    before = target.spin.value()
    step = ports.next_click(name)
    assert step.why == "rollen" and step.wheel_angle < 120
    assert ports.aim(step, step.rect.center()) == step.rect.center()
    row = _roll_next(ports, name)
    record_property("field_wheel", str(row))
    assert row["widget_at"]["class"] == "QScrollBar"
    assert observer.angles == [-step.wheel_angle]
    assert outer.viewport().rect().contains(_target_in(target, outer))
    assert target.spin.value() == before
    final = ports.next_click(name)
    assert final.why == "ziel"
    point = ports.aim(final, final.rect.center())
    hit = ports.widget_under(point)
    assert hit is target.spin or target.spin.isAncestorOf(hit)


def test_nested_scroll_reveals_inner_viewport_before_its_lower_field(
    wheel_scene: WheelScene, record_property: Any
) -> None:
    """RF77-M1: Innen passt das Feld gerade; außen muss erst dieser Ausschnitt frei werden."""
    from tools.function_walk import MOST_WAY_CLICKS, Walk

    top, outer, content = wheel_scene
    outer.resize(420, 102)
    inner = WheelArea(content)
    inner.setGeometry(25, 49, 320, 82)
    inner_content = QWidget()
    inner_content.resize(270, 700)
    inner.setWidget(inner_content)
    target = _navigation_target(inner_content)
    target.setGeometry(11, 300, 170, 80)
    top.show()
    QApplication.processEvents()
    assert outer.viewport().height() == 100 and inner.viewport().height() == 80
    assert target.height() == inner.viewport().height()
    assert inner.viewport().mapTo(outer.viewport(), QPoint()).y() == 50
    assert _target_in(target, outer).getRect() == (37, 350, 170, 80)
    assert _target_in(target, inner).getRect() == (11, 300, 170, 80)
    assert all(area.verticalScrollBar().maximum() > 0 for area in (inner, outer))
    inner_events, outer_events = WheelObserver(inner), WheelObserver(outer)
    ports = NavigationPorts(top, 0.0)
    rows: list[dict[str, Any]] = []
    states = []
    try:
        for _index in range(MOST_WAY_CLICKS):
            states.append(
                {
                    "inner_value": inner.verticalScrollBar().value(),
                    "outer_value": outer.verticalScrollBar().value(),
                    "inner_view_in_outer": QRect(
                        inner.viewport().mapTo(outer.viewport(), QPoint()), inner.viewport().size()
                    ).getRect(),
                    "target_in_inner": _target_in(target, inner).getRect(),
                    "target_in_outer": _target_in(target, outer).getRect(),
                }
            )
            if ports.next_click("setting:probe").why == "ziel":
                break
            assert Walk(ports, rows, 0.0).click_once("setting:probe") == "rollen"
            QApplication.processEvents()
        assert ports.next_click("setting:probe").why == "ziel"
        assert all(
            area.viewport().rect().contains(_target_in(target, area)) for area in (inner, outer)
        )
        assert inner.verticalScrollBar().value() > 0 and outer.verticalScrollBar().value() > 0
        assert inner_events.angles and outer_events.angles
        assert len(rows) <= MOST_WAY_CLICKS
    finally:
        record_property("nested_lower_states", str(states))
        record_property("nested_lower_events", str(rows))
        record_property(
            "nested_received", str({"inner": inner_events.angles, "outer": outer_events.angles})
        )
