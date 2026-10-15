"""Ein Sprachfall darf keine Fenster der vorigen Teilfläche mitnehmen."""

from types import SimpleNamespace

import pytest

from tools import function_language, function_surface
from tools.function_setup import Variant


@pytest.mark.parametrize("stubborn", [False, True])
def test_language_surfaces_close_their_windows_before_the_next_project(
    tmp_path, monkeypatch, stubborn
):
    """Nachgestelltes nichtmodales Fenster; nur Escape schließt, andernfalls hält der Lauf."""
    from PySide6.QtTest import QTest

    opened = []
    events = []
    window = SimpleNamespace(width=lambda: 800, height=lambda: 600)

    class Dialog:
        """Ein sichtbarer Dialog der vorigen Zeile."""

    class Flow:
        def __init__(self, application, window, folder, data, persist, row, *args, **kwargs):
            self.data, self.row, self.window = data, row, window
            self.walker = SimpleNamespace(record=lambda entry: events.append(entry["key"]))

        def reset(self):
            events.append(f"reset:{self.row['id']}")
            assert not opened, "Der vorige Dialog steht beim nächsten Projekt noch offen"
            return True

        def phase_surface(self):
            opened.append(Dialog())

        def run_steps(self, label, steps):
            for step in steps:
                step.act(None)
            return True

    monkeypatch.setattr(function_language, "FunctionFlow", Flow)
    monkeypatch.setattr(function_language, "place_window", lambda *args: {})
    monkeypatch.setattr(function_language, "without_way", lambda row: "")
    monkeypatch.setattr(function_surface, "windows_to_picture", lambda window: list(opened))
    monkeypatch.setattr(QTest, "keyClick", lambda *args: None if stubborn else opened.clear())
    # Nach vorn holt die Attrappe nichts; das echte Fenster prüft
    # ``test_function_language_escape.py``.
    monkeypatch.setattr(function_language, "bring_forward", lambda widget: None)
    rows = [
        {"id": name, "target": "operation:test", "kind": "operation", "package": "D4"}
        for name in ("first", "second")
    ]
    bench = {}
    flow = function_language.LanguageFlow(
        None,
        window,
        tmp_path,
        bench,
        lambda: None,
        rows,
        Variant.of({"set": "sprachen"}),
        tmp_path,
        {},
    )
    if stubborn:
        with pytest.raises(RuntimeError, match="Fenster der vorigen Fläche"):
            flow.run()
        assert "reset:second" not in events
        assert bench.get("surface_cleanup_failed") == "first"
    else:
        flow.run()
        assert events == ["reset:first", "Escape", "reset:second", "Escape"]
        assert not opened
