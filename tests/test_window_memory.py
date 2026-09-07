"""Der Speicherprüfstand muss tatsächliche Sprachwechsel anfordern."""

from __future__ import annotations

import gc
import sys
import weakref
from types import SimpleNamespace

import pytest


def test_qt_widget_types_do_not_keep_their_renderer_alive(
    qt_app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Qt darf die Widgetklasse behalten, ohne deren Renderer mitzubehalten."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QWidget
    from rendercanvas import qt

    from app.ui.render.gfx_renderer import GfxRenderer

    class Canvas(QWidget):
        def __init__(self, parent: object, **_options: object) -> None:
            super().__init__(parent)

    monkeypatch.setattr(qt, "QRenderWidget", Canvas)
    renderer = object.__new__(GfxRenderer)
    reference = weakref.ref(renderer)
    widget = renderer._qt_widget(None)
    try:
        del renderer
        gc.collect()
        assert reference() is None, "die Qt-Klasse hält ihren früheren Renderer fest"
        # Bereits eingereihte Zeigerereignisse dürfen nach der Freigabe noch ankommen.
        widget.leaveEvent(QEvent(QEvent.Type.Leave))
    finally:
        widget.close()
        widget.deleteLater()


def test_language_rebuild_closes_the_previous_render_canvas(qt_app: object) -> None:
    """Der Fensterwechsel muss die alte Zeichenfunktion samt Grafikkontext lösen."""
    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.app import rebuild_for_language
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    settings = UiSettings()
    window = MainWindow(Session(), settings)
    previous = window
    closed: list[bool] = []
    previous.viewport.renderer = SimpleNamespace(close=lambda: closed.append(True))
    try:
        settings.language = "en"
        window = rebuild_for_language(qt_app, previous, settings)
        assert closed == [True], "die Zeichenfunktion des alten Fensters bleibt registriert"
        assert previous.viewport.renderer is None
    finally:
        window.close()
        window.deleteLater()
        install_language("de")
        set_language("de")


def test_memory_drain_really_releases_deferred_qt_objects(qt_app: object) -> None:
    """processEvents allein lässt deleteLater-Fenster bis zum Schleifenende liegen."""
    from PySide6.QtCore import QObject
    from shiboken6 import isValid

    from tools.window_memory import drain

    old_window = QObject()
    old_window.deleteLater()
    drain(qt_app)
    assert not isValid(old_window), "der Prüfstand zählt ein zur Löschung vorgemerktes Fenster"


def test_memory_probe_changes_the_language_read_by_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Globale Sprache allein wird beim Neuaufbau von settings.language ersetzt."""
    from PySide6 import QtWidgets

    from app.core import bootstrap
    from app.i18n.catalog import available_languages
    from app.ui import app, main_window, session, settings, viewport
    from tools import window_memory

    requested: list[str] = []
    language_count = len(available_languages())

    class Window:
        def __init__(self, *_args: object) -> None:
            pass

        def show(self) -> None:
            pass

    def rebuild(_application: object, window: object, chosen: SimpleNamespace) -> object:
        requested.append(chosen.language)
        return window

    monkeypatch.setattr(
        sys, "argv", ["window_memory", "--windows", "0", "--languages", str(language_count * 2)]
    )
    monkeypatch.setattr(window_memory, "isolate", lambda *_args: None)
    monkeypatch.setattr(window_memory, "drain", lambda *_args: None)
    monkeypatch.setattr(window_memory, "shutdown_window", lambda *_args: None)
    monkeypatch.setattr(window_memory, "working_set_mb", lambda: 100.0)
    monkeypatch.setattr(QtWidgets, "QApplication", lambda *_args: object())
    monkeypatch.setattr(bootstrap, "load_operations", lambda: None)
    monkeypatch.setattr(viewport, "_available", lambda: True)
    monkeypatch.setattr(main_window, "MainWindow", Window)
    monkeypatch.setattr(session, "Session", lambda: object())
    monkeypatch.setattr(settings, "UiSettings", lambda: SimpleNamespace(language="de"))
    monkeypatch.setattr(app, "rebuild_for_language", rebuild)

    try:
        assert window_memory.main() == 0
    finally:
        # Die autouse-Fixtures lesen QApplication vor dem automatischen
        # monkeypatch-Abbau; unsere örtlichen Ersatzklassen müssen vorher weg.
        monkeypatch.undo()
    assert len(requested) == language_count * 2
    assert set(requested[:language_count]) == set(available_languages())
    assert requested[:language_count] == requested[language_count:]
    assert all(
        before != after for before, after in zip(["de", *requested[:-1]], requested, strict=True)
    )
