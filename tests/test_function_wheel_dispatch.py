"""Radereignisse nehmen den Qt-Weg über ignorierende Kinder und Rollbereiche."""

from collections.abc import Iterator
from typing import Any, override

import pytest
from PySide6.QtCore import QPoint, Qt
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
