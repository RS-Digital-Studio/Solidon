"""Verträge des echten Fensterprüfstands, ohne selbst ein Fenster zu öffnen."""

from __future__ import annotations

from typing import Any

import pytest

from tools.window_bench import EVENT_DRAIN_ROUNDS, shutdown_window


class _Plotter:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def close(self) -> None:
        self.events.append("plotter.close")


class _Viewport:
    def __init__(self, events: list[str], *, with_plotter: bool) -> None:
        self.plotter: Any | None = _Plotter(events) if with_plotter else None

    def release_plotter(self) -> None:
        plotter = self.plotter
        if plotter is None:
            return
        plotter.close()
        self.plotter = None


class _Window:
    def __init__(self, events: list[str], *, with_plotter: bool = True) -> None:
        self.events = events
        self.viewport = _Viewport(events, with_plotter=with_plotter)

    def release(self) -> None:
        self.events.append("window.release")

    def close(self) -> None:
        self.events.append("window.close")


class _Application:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def processEvents(self) -> None:  # noqa: N802 — bildet die Qt-API nach
        self.events.append("application.processEvents")


def test_vtk_closes_while_its_qt_parent_is_still_alive() -> None:
    """Der native Plotter stirbt vor seinem Elternfenster, nicht beim Prozessende."""
    events: list[str] = []
    window = _Window(events)

    shutdown_window(window, _Application(events))

    assert events[:3] == ["window.release", "plotter.close", "window.close"]
    assert events[3:] == ["application.processEvents"] * EVENT_DRAIN_ROUNDS
    assert window.viewport.plotter is None


def test_offscreen_shutdown_uses_the_same_platform_neutral_order() -> None:
    """Ohne Plotter bleibt derselbe Weg auf allen Qt-Plattformen gültig."""
    events: list[str] = []
    window = _Window(events, with_plotter=False)

    shutdown_window(window, _Application(events))

    assert events[:2] == ["window.release", "window.close"]
    assert events[2:] == ["application.processEvents"] * EVENT_DRAIN_ROUNDS


def test_accepted_application_exit_uses_the_terminal_viewport_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nur ein bestätigtes echtes Schließen finalisiert den VTK-Renderer."""
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
        def release_plotter(self) -> None:
            events.append("viewport.release_plotter")

    class _ExitWindow:
        _remote = None
        settings = type("Settings", (), {"window_geometry": ""})()
        _usage = _Usage()
        viewport = _ExitViewport()

        def _may_discard(self) -> bool:
            return True

        def wait_for_workers(self) -> None:
            events.append("window.wait_for_workers")

        def saveGeometry(self) -> _Geometry:  # noqa: N802 — bildet die Qt-API nach
            return _Geometry()

    monkeypatch.setattr(
        main_window,
        "save_settings",
        lambda _settings: events.append("settings.save"),
    )
    event = QCloseEvent()

    main_window.MainWindow.closeEvent(_ExitWindow(), event)

    assert event.isAccepted()
    assert events == [
        "window.wait_for_workers",
        "settings.save",
        "usage.stop",
        "viewport.release_plotter",
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
