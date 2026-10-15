"""Verträge des echten Fensterprüfstands, ohne selbst ein Fenster zu öffnen."""

from __future__ import annotations

from typing import Any

import pytest

from tools.window_bench import EVENT_DRAIN_ROUNDS, shutdown_window


@pytest.mark.parametrize("state", ["old", "busy", "incomplete", "not_shown", "no_renderer"])
def test_quiet_counters_do_not_turn_an_unfinished_scene_into_a_measurement(state: str) -> None:
    from types import SimpleNamespace

    from tools.window_bench import await_scene

    result = SimpleNamespace(
        complete=state != "incomplete", scene=SimpleNamespace(objects={"one": 1})
    )
    window = SimpleNamespace(
        session=SimpleNamespace(last_result=result, busy=state == "busy"),
        viewport=SimpleNamespace(
            _result=None if state == "not_shown" else result,
            renderer=None if state == "no_renderer" else object(),
        ),
    )
    elapsed = [0.0]

    def tick(_seconds: float) -> None:
        elapsed[0] += 0.1

    with pytest.raises(TimeoutError):
        await_scene(
            window,
            _Application([]),
            result if state == "old" else None,
            {},
            {},
            settle=0.01,
            timeout=0.5,
            timer=lambda: elapsed[0],
            pause=tick,
        )


def test_a_completed_scene_is_measured_after_it_reaches_the_viewport() -> None:
    from types import SimpleNamespace

    from tools.window_bench import await_scene

    result = SimpleNamespace(complete=True, scene=SimpleNamespace(objects={"one": 1}))
    window = SimpleNamespace(
        session=SimpleNamespace(last_result=result, busy=True),
        viewport=SimpleNamespace(_result=None, renderer=object()),
    )
    elapsed = [0.0]

    def tick(_seconds: float) -> None:
        elapsed[0] += 0.1
        if elapsed[0] >= 0.3:
            window.session.busy = False
            window.viewport._result = result

    await_scene(
        window,
        _Application([]),
        None,
        {},
        {},
        settle=0.2,
        timeout=1.0,
        timer=lambda: elapsed[0],
        pause=tick,
    )
    assert elapsed[0] >= 0.4


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


class _Sleeper:
    """Steht für einen Arbeiter, der nach der Frist am Ende noch läuft."""


def _exit_wait(
    monkeypatch: pytest.MonkeyPatch, events: list[str], stubborn: tuple[Any, ...] = ()
) -> None:
    """Die Wartestelle der Leine als Ereignis, ohne echte Arbeiter (FD-154)."""
    from app.ui import leash

    def finish_before_exit() -> tuple[Any, ...]:
        events.append("leash.finish_before_exit")
        return stubborn

    monkeypatch.setattr(leash, "finish_before_exit", finish_before_exit)


def test_the_renderer_closes_while_its_qt_parent_is_still_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der native Renderer stirbt vor seinem Elternfenster, nicht beim Prozessende —
    und beide erst, wenn jeder Arbeiter zurück ist (FD-154): Schloss das Fenster
    vorher, lehnte ``closeEvent`` ab, und PySide zerstörte den Faden am Ende."""
    events: list[str] = []
    window = _Window(events)
    _exit_wait(monkeypatch, events)

    assert shutdown_window(window, _Application(events)) == ()

    assert events[:4] == [
        "window.release",
        "leash.finish_before_exit",
        "renderer.close",
        "window.close",
    ]
    assert events[4:] == ["application.processEvents"] * EVENT_DRAIN_ROUNDS
    assert window.viewport.renderer is None


def test_offscreen_shutdown_uses_the_same_platform_neutral_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne Renderer bleibt derselbe Weg auf allen Qt-Plattformen gültig."""
    events: list[str] = []
    window = _Window(events, with_renderer=False)
    _exit_wait(monkeypatch, events)

    shutdown_window(window, _Application(events))

    assert events[:3] == ["window.release", "leash.finish_before_exit", "window.close"]
    assert events[3:] == ["application.processEvents"] * EVENT_DRAIN_ROUNDS


def test_a_worker_past_the_deadline_is_named_and_not_awaited_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wer nach der Frist noch läuft, steht mit Namen im Fallzustand, und der Prozess
    endet gleich danach benannt — statt am Ende noch einmal ``EXIT_WAIT_MS`` zu warten
    und mit Exit 3 ohne Grund im Fall zu enden (Schlussreview D0, RF-11)."""
    from app.ui import leash
    from tools.window_bench import record_shutdown

    events: list[str] = []
    _exit_wait(monkeypatch, events, (_Sleeper(), _Sleeper()))
    left: list[str] = []

    def leave_without_teardown(names: str) -> None:
        left.append(names)
        raise SystemExit(leash.STRAGGLER_EXIT_CODE)

    monkeypatch.setattr(leash, "leave_without_teardown", leave_without_teardown)
    stragglers = shutdown_window(_Window(events), _Application(events))
    assert stragglers == ("_Sleeper", "_Sleeper")

    state: dict[str, Any] = {"stage": "done"}
    written: list[dict[str, Any]] = []
    with pytest.raises(SystemExit):
        record_shutdown(state, lambda: written.append(dict(state)), stragglers)
    assert written == [
        {"stage": "done", "shutdown_complete": False, "stragglers": ["_Sleeper", "_Sleeper"]}
    ], "geschrieben, bevor der Prozess endet"
    assert left == ["_Sleeper, _Sleeper"]

    calm: dict[str, Any] = {}
    record_shutdown(calm, lambda: None, ())
    assert calm == {"shutdown_complete": True} and left == ["_Sleeper, _Sleeper"]


def test_accepted_application_exit_uses_the_terminal_viewport_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bestätigtes Schließen bricht die Frage vor Warten und Rendererfreigabe ab."""
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

    class _Notice:
        def clear(self) -> None:
            events.append("notice.clear")

    class _ExitViewport:
        def wait_for_workers(self, _timeout_ms: int) -> bool:
            return True

        def release_renderer(self) -> None:
            events.append("viewport.release_renderer")

    class _SpaceMouse:
        def stop(self) -> None:
            events.append("spacemouse.stop")

    class _Session:
        def release_recovery(self) -> None:
            events.append("session.release_recovery")

    class _Tabs:
        def layout_state(self) -> dict[str, object]:
            events.append("tabs.layout_state")
            return {"order": ["report"], "windows": {"report": [100, 100, 400, 500]}}

        def shutdown_windows(self) -> None:
            events.append("tabs.shutdown_windows")

    class _ExitWindow:
        right = _Tabs()
        _remote = None
        _rebuild_dialog = None
        session = _Session()
        settings = type("Settings", (), {"window_geometry": ""})()
        _usage = _Usage()
        _action_notice = _Notice()
        viewport = _ExitViewport()
        spacemouse = _SpaceMouse()

        def _may_lose_the_generation(self) -> bool:
            return True

        def _may_discard(self) -> bool:
            return True

        def _cancel_pending_question(self) -> None:
            events.append("question.cancel")

        def wait_for_workers(self, _timeout_ms: int = 2000) -> bool:
            events.append("window.wait_for_workers")
            return True

        _close_requested = False

        class _Retry:
            def stop(self) -> None:
                pass

        _close_retry = _Retry()

        class _CardPlacesSave:
            def stop(self) -> None:
                events.append("card_places.stop")

        # Die gebündelt gespeicherte Kartenlage geht mit dem Schließen in die
        # Datei: Ihr Zeitgeber hält an, und ``_store_settings`` schreibt sie.
        _card_places_save = _CardPlacesSave()

        def setEnabled(self, enabled: bool) -> None:  # noqa: N802 — bildet die Qt-API nach
            events.append(f"window.setEnabled:{enabled}")

        def saveGeometry(self) -> _Geometry:  # noqa: N802 — bildet die Qt-API nach
            return _Geometry()

        def _store_settings(self) -> bool:
            events.append("settings.save")
            return False

    event = QCloseEvent()

    window = _ExitWindow()
    main_window.MainWindow.closeEvent(window, event)

    assert window.settings.tab_layout == {
        "order": ["report"],
        "windows": {"report": [100, 100, 400, 500]},
    }
    assert event.isAccepted()
    assert events == [
        "question.cancel",
        "window.setEnabled:False",
        "window.wait_for_workers",
        "spacemouse.stop",
        "tabs.layout_state",
        "tabs.shutdown_windows",
        "card_places.stop",
        "settings.save",
        "usage.stop",
        "notice.clear",
        "viewport.release_renderer",
        "session.release_recovery",
    ]


def test_rejected_application_exit_touches_nothing() -> None:
    """Abbrechen lässt Arbeiter, Einstellungen, Nutzung und Viewport unberührt."""
    from PySide6.QtGui import QCloseEvent

    from app.ui.main_window import MainWindow

    class _RejectedWindow:
        def _may_lose_the_generation(self) -> bool:
            return True

        def _may_discard(self) -> bool:
            return False

    event = QCloseEvent()

    MainWindow.closeEvent(_RejectedWindow(), event)

    assert not event.isAccepted()


def test_staying_with_a_generation_asks_nothing_else() -> None:
    """RM-499: *Zur Erzeugung* hält das Fenster offen — ohne die Frage nach dem Speichern.

    Erst die Erzeugung, dann das Projekt: Wer zur Erzeugung zurückwill, soll
    nicht noch gefragt werden, ob er speichern möchte.
    """
    from PySide6.QtGui import QCloseEvent

    from app.ui.main_window import MainWindow

    class _StayingWindow:
        def _may_lose_the_generation(self) -> bool:
            return False

        def _may_discard(self) -> bool:
            raise AssertionError("nach „Zur Erzeugung“ kommt keine zweite Frage")

    event = QCloseEvent()

    MainWindow.closeEvent(_StayingWindow(), event)

    assert not event.isAccepted()


def test_every_process_end_names_its_stragglers_once() -> None:
    """Jedes Prozessende eines Werkzeugs geht über ``record_shutdown`` (Review 2, RF-18).

    Wer die Rückgabe von ``shutdown_window`` verwirft, lässt den Haken am
    Prozessende ein zweites Mal bis ``EXIT_WAIT_MS`` warten, und ein Nachzügler
    endet mit Exit 3 ohne Namen im Fall; wer ``shutdown_complete`` selbst setzt,
    meldet einen Abbau als fertig, den niemand geprüft hat. Gelesen wird der
    Quelltext unter ``tools/``: Jeder Aufruf von ``shutdown_window`` und
    ``wait_for_workers`` ist Argument von ``record_shutdown`` oder wird in eine
    Variable gebunden, die ``record_shutdown`` in derselben Funktion bekommt.
    """
    import ast
    from pathlib import Path

    import tools

    folder = Path(next(iter(tools.__path__)))
    waits = {"shutdown_window", "wait_for_workers"}
    seen: list[str] = []
    loose: list[str] = []
    for path in sorted(folder.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
                key = node.slice
                owner = parents[node]
                while not isinstance(owner, ast.FunctionDef | ast.Module):
                    owner = parents[owner]
                setter = getattr(owner, "name", "") == "record_shutdown"
                named = isinstance(key, ast.Constant) and key.value == "shutdown_complete"
                if named and not setter:
                    loose.append(f"{path.name}:{node.lineno} setzt shutdown_complete selbst")
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in waits
            ):
                continue
            where = f"{path.name}:{node.lineno} {node.func.id}"
            seen.append(where)
            parent = parents[node]
            if isinstance(parent, ast.Call) and getattr(parent.func, "id", "") == "record_shutdown":
                continue
            function = parent
            while not isinstance(function, ast.FunctionDef):
                function = parents[function]
            if function.name == "shutdown_window":
                continue
            names = (
                {target.id for target in parent.targets if isinstance(target, ast.Name)}
                if isinstance(parent, ast.Assign)
                else set()
            )
            handed = {
                argument.id
                for call in ast.walk(function)
                if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "record_shutdown"
                for argument in call.args
                if isinstance(argument, ast.Name)
            }
            if not names & handed:
                loose.append(f"{where}: Rückgabe geht nicht an record_shutdown")
    assert len(seen) >= 7, seen
    assert loose == [], loose
