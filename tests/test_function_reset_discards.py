"""Die Rückkehr zur Startszene fragt nie nach ungesicherten Änderungen (FD-235, RM-737).

Seit FD-101/175 gehen die Zeilen eines Sprachfalls ihren Weg und lassen das
Projekt geändert zurück, nach ``finding.action:split_along_line`` mit offenem
Zeichenmodus. ``FunctionFlow.reset`` verwarf nur den Stand
(``session.forget_changes``); ``open_path`` und *Datei → Neu* fragten dann über
``confirm_unsaved`` modal nach dem Entwurf, und L4 des Schlusslaufs hing im
Fall 052. Am echten Fenster, offscreen; die Frage ist ersetzt und zählt nur.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.scene import OperationDraft
from app.core.sketch import shapes
from app.ui import main_window as main_window_module
from app.ui.draw_tool import bed_surface
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tools import function_bench
from tools.function_machine import Step


def _changed_window_in_drawing_mode(qt_app: Any) -> MainWindow:
    """Ein geändertes Projekt und ein Umriss im Zeichenmodus, der auf seine Höhe wartet."""
    window = MainWindow(Session(), UiSettings())
    window.show()
    window._show_start_screen(False)
    assert window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    window.start_drawing()
    flow = window.draw_flow()
    flow.arm_free()
    flow.take(("bed", bed_surface(), (0.0, 0.0), (0.0, 0.0, 0.0)))
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.set_sketch(shapes.rectangle(20.0, 10.0))
    window.sketch_finish_button.click()
    qt_app.processEvents()
    # Voraussetzung, nicht Annahme: Stand und Entwurf sind ungesichert.
    assert window.session.modified and window._has_unsaved_gestures()
    return window


def _flow(window: MainWindow, scene: Path) -> Any:
    """``reset`` mit dem echten Fenster; die Schritte laufen der Reihe nach."""
    flow = object.__new__(function_bench.FunctionFlow)
    flow.window = window
    flow.session = window.session
    flow.scene_key = "fremd"
    flow.scene_path = lambda key: scene
    flow.data = {"scene": {"key": "fremd"}, "errors": []}
    flow.idle = lambda: True
    flow.preparation_steps = list
    flow.wait_step = lambda name, ready, timeout_s=0: Step(name, lambda machine: None)

    def run_steps(label: str, steps: list[Step], timeout_s: float | None = None) -> bool:
        for step in steps:
            step.act(SimpleNamespace(insert=lambda more: None))
        return True

    flow.run_steps = run_steps
    return flow


def _scene(tmp_path: Path) -> Path:
    """Eine Startszene als Projektdatei, wie das Inventar sie ablegt (``scenes/<key>.p3d``)."""
    session = Session()
    assert session.apply("Quader", [OperationDraft(op="create_box")])
    assert session.wait_for_idle(60_000)
    return session.save_project(tmp_path / "szene.p3d")


def test_the_return_to_the_start_scene_asks_nothing(
    qt_app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    def confirm(title: str, parent: Any) -> str:
        asked.append(title)
        return "cancel"  # wie ein Fall, der ewig auf die Antwort wartete

    monkeypatch.setattr(main_window_module, "confirm_unsaved", confirm)
    window = _changed_window_in_drawing_mode(qt_app)
    try:
        assert _flow(window, _scene(tmp_path)).reset()
        qt_app.processEvents()
        assert asked == [], "die Speicherfrage kam vor der Startszene"
        assert not window.drawing() and not window._has_unsaved_gestures()
        assert not window.session.modified
    finally:
        window.hide()
        window.release()


def test_the_way_back_to_the_start_screen_asks_nothing(
    qt_app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwilling: *Datei → Neu* zur Startszene ``startbildschirm`` verwirft genauso."""
    from tools.function_setup import START_SCREEN

    asked: list[str] = []
    monkeypatch.setattr(
        main_window_module, "confirm_unsaved", lambda title, parent: asked.append(title) or "cancel"
    )
    window = _changed_window_in_drawing_mode(qt_app)
    flow = _flow(window, Path("unbenutzt.p3d"))
    flow.scene_key = START_SCREEN
    # Der Klick auf *Datei → Neu* löst die Handlung des Menüeintrags aus.
    flow.walker = SimpleNamespace(
        step=lambda name: Step(name, lambda machine: window.new_action.trigger())
    )
    try:
        assert flow.reset()
        qt_app.processEvents()
        assert asked == [], "die Speicherfrage kam vor dem Startbildschirm"
        assert not window._has_unsaved_gestures() and not window.session.modified
    finally:
        window.hide()
        window.release()
