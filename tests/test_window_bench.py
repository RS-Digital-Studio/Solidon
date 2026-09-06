"""Verträge des echten Fensterprüfstands, ohne selbst ein Fenster zu öffnen."""

from __future__ import annotations

from typing import Any

import pytest

from tools.window_bench import EVENT_DRAIN_ROUNDS, shutdown_window


class _Renderer:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def close(self) -> None:
        self.events.append("renderer.close")


class _Viewport:
    def __init__(self, events: list[str], *, with_renderer: bool) -> None:
        self.renderer: Any | None = _Renderer(events) if with_renderer else None

    def release_renderer(self) -> None:
        renderer = self.renderer
        if renderer is None:
            return
        renderer.close()
        self.renderer = None


class _Window:
    def __init__(self, events: list[str], *, with_renderer: bool = True) -> None:
        self.events = events
        self.viewport = _Viewport(events, with_renderer=with_renderer)

    def release(self) -> None:
        self.events.append("window.release")

    def close(self) -> None:
        self.events.append("window.close")


class _Application:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def processEvents(self) -> None:  # noqa: N802 — bildet die Qt-API nach
        self.events.append("application.processEvents")


def test_the_renderer_closes_while_its_qt_parent_is_still_alive() -> None:
    """Der native Renderer stirbt vor seinem Elternfenster, nicht beim Prozessende."""
    events: list[str] = []
    window = _Window(events)

    shutdown_window(window, _Application(events))

    assert events[:3] == ["window.release", "renderer.close", "window.close"]
    assert events[3:] == ["application.processEvents"] * EVENT_DRAIN_ROUNDS
    assert window.viewport.renderer is None


def test_offscreen_shutdown_uses_the_same_platform_neutral_order() -> None:
    """Ohne Plotter bleibt derselbe Weg auf allen Qt-Plattformen gültig."""
    events: list[str] = []
    window = _Window(events, with_renderer=False)

    shutdown_window(window, _Application(events))

    assert events[:2] == ["window.release", "window.close"]
    assert events[2:] == ["application.processEvents"] * EVENT_DRAIN_ROUNDS


def test_accepted_application_exit_uses_the_terminal_viewport_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nur ein bestätigtes echtes Schließen finalisiert den Renderer."""
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QCloseEvent

    from app.ui import main_window

    events: list[str] = []

    class _Geometry:
        def toHex(self) -> _Geometry:  # noqa: N802 — bildet die Qt-API nach
            return self

        def data(self) -> bytes:
            return b""

    class _Usage:
        def stop(self) -> None:
            events.append("usage.stop")

    class _ExitViewport:
        def wait_for_workers(self, _timeout_ms: int) -> bool:
            return True

        def release_renderer(self) -> None:
            events.append("viewport.release_renderer")

    class _SpaceMouse:
        def stop(self) -> None:
            events.append("spacemouse.stop")

    class _ExitWindow:
        _remote = None
        settings = type("Settings", (), {"window_geometry": ""})()
        _usage = _Usage()
        viewport = _ExitViewport()
        spacemouse = _SpaceMouse()

        def _may_discard(self) -> bool:
            return True

        def wait_for_workers(self, _timeout_ms: int = 2000) -> bool:
            events.append("window.wait_for_workers")
            return True

        _close_requested = False

        class _Retry:
            def stop(self) -> None:
                pass

        _close_retry = _Retry()

        def setEnabled(self, enabled: bool) -> None:  # noqa: N802 — bildet die Qt-API nach
            events.append(f"window.setEnabled:{enabled}")

        def saveGeometry(self) -> _Geometry:  # noqa: N802 — bildet die Qt-API nach
            return _Geometry()

        def _store_settings(self) -> bool:
            events.append("settings.save")
            return False

    event = QCloseEvent()

    main_window.MainWindow.closeEvent(_ExitWindow(), event)

    assert event.isAccepted()
    assert events == [
        "window.setEnabled:False",
        "window.wait_for_workers",
        "spacemouse.stop",
        "settings.save",
        "usage.stop",
        "viewport.release_renderer",
    ]


def test_rejected_application_exit_touches_nothing() -> None:
    """Abbrechen lässt Arbeiter, Einstellungen, Nutzung und Viewport unberührt."""
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QCloseEvent

    from app.ui.main_window import MainWindow

    class _RejectedWindow:
        def _may_discard(self) -> bool:
            return False

    event = QCloseEvent()

    MainWindow.closeEvent(_RejectedWindow(), event)

    assert not event.isAccepted()
