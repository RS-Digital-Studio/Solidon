"""Der Wächter des Prüfstands: keine Abkürzung am Fenster, kein eigener Einstieg (D0-P).

Jedes Modul aus ``function_guard.BENCH_MODULES`` und ``WindowFlow`` in
``file_acceptance`` bedienen das Fenster nur über Eingabeereignisse; der
Wächter findet jeden bekannten Umweg, und eine Gegenprobe je Modul zeigt, dass
er dessen Quelltext wirklich liest. Jedes Werkzeugmodul, das den Prüfstand
benutzt, steht in der Liste, und keines trägt einen eigenen Einstieg (kein
drittes Fensterwerkzeug, Konzept Funktionsdurchgang §12).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools import function_guard
from tools.file_acceptance import ROOT

TOOLS = ROOT / "tools"
ACCEPTANCE = TOOLS / "file_acceptance.py"


def _source(module: str) -> str:
    return (TOOLS / f"{module}.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("module", function_guard.BENCH_MODULES)
def test_every_bench_module_goes_through_input_events_only(module: str) -> None:
    """Kein Modul des Prüfstands umgeht eine Bedienung — mit Gegenprobe an seinem Quelltext.

    Die Gegenprobe hängt an das echte Modul eine Funktion mit einem Umweg: Der
    Wächter findet ihn genau dort. So liest er jedes Modul der Liste wirklich,
    auch eines, das nach der Teilung von ``function_bench`` neu ist.
    """
    source = _source(module)
    assert function_guard.forbidden_calls(source) == []
    broken = source + "\n\ndef _gegenprobe(button):\n    button.click()\n"
    last = len(broken.splitlines())
    assert function_guard.forbidden_calls(broken) == [(last, "button.click")]


def test_the_window_flow_goes_through_input_events_only() -> None:
    """``WindowFlow``, der Dateiweg in ``file_acceptance``, bedient nur über Eingabeereignisse."""
    assert (
        function_guard.forbidden_calls(_source("file_acceptance"), within_class="WindowFlow") == []
    )


def test_the_guard_finds_every_known_detour() -> None:
    """Kein ``click``, ``set_value*``, ``emit``, ``session.apply``, ``trigger``, ``select_*``.

    Dazu ``action_undo``/``action_redo`` und die vierzehn Umwege der Durchsicht
    (Review M8) — der Wächter muss jeden finden, erlaubte Stellen bleiben frei.
    """
    broken = "\n".join(
        [
            "class WindowFlow:",
            "    def run(self):",
            "        self.button.click()",
            "        self.spin.set_value_mm(3.0)",
            "        self.spin.setValue(3.0)",
            "        self.window.valueChanged.emit(1)",
            "        self.session.apply('x', [])",
            "        self.window.session.apply('y', [])",
            "        self.action.trigger()",
            "        self.tree.select_feature('obj_1', 'hole_1')",
            "        self.window.action_undo()",
            "        self.window.action_redo()",
            "        self.tabs.setCurrentIndex(1)",
            "        self.box.setChecked(True)",
            "        self.button.animateClick()",
            "        self.history.apply('erlaubt', [])",
            "        QTest.mouseClick(widget, button)",
        ]
    )
    found = function_guard.forbidden_calls(broken, within_class="WindowFlow")
    assert [line for line, _call in found] == list(range(3, 16))
    assert "self.history.apply" not in {call for _line, call in found}
    detours = "\n".join(
        [
            "class WindowFlow:",
            "    def run(self):",
            "        getattr(self.button, 'click')()",
            "        press = self.button.click",
            "        QMetaObject.invokeMethod(self.button, 'click')",
            "        self.window._show_start_screen(False)",
            "        approval = getattr(self.window, '_preview_approval')",
            "        self.window.feature_panel._apply.released.connect(print)",
            "        guide_targets.area_for(self.window, 'feature.apply')",
            "        self.dialog.accept()",
            "        self.edit.setText('5')",
            "        self.session.start_new('p', 'm')",
            "        self.window.run_operation(spec)",
            "        self.list.setCurrentRow(2)",
            "        self.box.toggle()",
            "        self.dialog.done(0)",
            "        self.dialog.reject()",
            "        self.row.setSelected(True)",
            "        self.field.setFocus()",
            "        if machine.done or self._answering:",
            "            activation._cached = cached",
            "            sys._getframe(1)",
            "        getattr(view, 'renderer', None)",
        ]
    )
    found = function_guard.forbidden_calls(detours, within_class="WindowFlow")
    lines = sorted({line for line, _call in found})
    assert lines == list(range(3, 20)), found
    with pytest.raises(LookupError):
        function_guard.forbidden_calls("x = 1\n", within_class="WindowFlow")


def _imports(path: Path) -> set[str]:
    """Die Module unter ``tools``, die eine Datei importiert, als Namen ohne Paket."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module == "tools":
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tools."):
            found.add((node.module or "").removeprefix("tools."))
        elif isinstance(node, ast.Import):
            found.update(
                alias.name.removeprefix("tools.")
                for alias in node.names
                if alias.name.startswith("tools.")
            )
    return found


def test_every_tool_that_uses_the_bench_is_guarded() -> None:
    """Reichweite: Wer ein Modul des Prüfstands benutzt, steht selbst unter dem Wächter.

    Sonst wüchse ein neues Modul neben der Liste, das klickt, ohne dass jemand
    hinsieht. ``file_acceptance`` legt Fälle an und reicht sie weiter; sein
    Fensterweg ``WindowFlow`` hat einen eigenen Test.
    """

    def unguarded(listed: set[str]) -> set[str]:
        return {
            path.stem
            for path in TOOLS.glob("*.py")
            if path.stem != "file_acceptance"
            and path.stem not in listed
            and _imports(path) & listed
        }

    bench = set(function_guard.BENCH_MODULES)
    assert all((TOOLS / f"{module}.py").is_file() for module in bench)
    assert unguarded(bench) == set()
    # Gegenprobe: ``function_language`` benutzt ``function_bench`` und fiele auf.
    assert unguarded(bench - {"function_language"}) == {"function_language"}


def test_no_bench_module_has_an_entry_of_its_own() -> None:
    """Die Module des Prüfstands laufen nur unter ``file_acceptance``.

    Kein ``if __name__ == "__main__"``, kein ``argparse`` — sonst wäre es das
    dritte Fensterwerkzeug (Konzept Funktionsdurchgang §12). Gegenprobe:
    ``file_acceptance`` hat beides.
    """

    def entries(path: Path) -> tuple[bool, bool]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        main = any(
            isinstance(node, ast.If) and "__main__" in ast.unparse(node.test) for node in tree.body
        )
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in (
                node.names if isinstance(node, ast.Import) else [ast.alias(node.module or "")]
            )
        }
        return main, "argparse" in imports

    for module in function_guard.BENCH_MODULES:
        assert entries(TOOLS / f"{module}.py") == (False, False), module
    assert entries(ACCEPTANCE) == (True, True)
