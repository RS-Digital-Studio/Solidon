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


#: Die zwanzig Umwege der Durchsicht welle4 (C-M3, Sonde ``guard_probe.py``):
#: Keinen fand der Wächter. Jeder steht für sich, damit ein Treffer an einer
#: Nachbarzeile keinen anderen verdeckt.
UNSEEN_DETOURS = {
    "Sitzung über einen Alias": "s = self.window.session\ns.apply('x', [])",
    "Rückgängig über die Sitzung": "self.window.session.undo()",
    "Rückgängig über den Verlauf": "self.window.history_panel.undo()",
    "area_for als Name": (
        "from app.ui.guide_targets import area_for\narea_for(window, 'feature.apply')"
    ),
    "select_feature als Name": (
        "from app.ui.panels import select_feature\nselect_feature(tree, 'hole_1')"
    ),
    "QAction.activate": "action.activate(QAction.ActionEvent.Trigger)",
    "setattr privat": "setattr(window, '_busy', False)",
    "vars privat": "vars(window)['_busy'] = False",
    "__dict__ privat": "window.__dict__['_busy'] = False",
    "getattr mit Variable": "name = 'click'\ngetattr(button, name)()",
    "methodcaller": "import operator\noperator.methodcaller('click')(button)",
    "setPlainText": "editor.setPlainText('5')",
    "insert in Zeile": "line.insert('5')",
    "setEditText": "combo.setEditText('PLA')",
    "setCheckState": "box.setCheckState(Qt.CheckState.Checked)",
    "Ereignismethode direkt": "spin.keyPressEvent(event)",
    "Slot direkt": "window.action_save_as()",
    "invokeMethod mit Variable": "slot = 'click'\nQMetaObject.invokeMethod(button, slot)",
    "invokeMethod privat": "QMetaObject.invokeMethod(window, '_on_apply')",
    "QTimer mit Lambda auf öffentliche Methode": (
        "QTimer.singleShot(0, lambda: panel.apply_action('x'))"
    ),
}

#: Was der Prüfstand heute so schreibt und schreiben darf: eigene Methoden an
#: ``self``, der Automat, Lesezugriffe, Eingabeereignisse über Qt.
ALLOWED_FORMS = (
    "machine.insert([self.walker.step(target)])",
    "listing.insert(0, entry)",
    "self.apply_step()",
    "self.action_step(name)",
    "guide_targets.action_for(window, hit)",
    "self.history.apply('erlaubt', [])",
    "getattr(cached, state)",
    "phase = getattr(self, f'phase_{name}')\nphase()",
    "signals = [getattr(view, name) for name in DRAG_SIGNALS]",
    "found = 'paintEvent' in vars(cls)",
    "QApplication.sendEvent(widget, event)",
    "QTest.sendKeyEvent(QTest.KeyAction.Click, target, key, text, modifier)",
    "top.activateWindow()",
    "super().eventFilter(watched, event)",
    "self.session.forget_changes()",
    "result = self.session.last_result",
)


@pytest.mark.parametrize("label", sorted(UNSEEN_DETOURS))
def test_the_guard_finds_the_detours_the_review_found(label: str) -> None:
    """Jede der zwanzig Formen der Durchsicht welle4 ist ein Fund (C-M3).

    Aufrufe über importierte Namen und Aliasse, Undo/Redo an Sitzung und
    Verlauf, Werteinstellung über ``setPlainText``/``setEditText``/
    ``setCheckState``/``insert``, Ereignismethoden und öffentliche Slots direkt,
    dazu ``setattr``, ``vars``, ``__dict__``, ``methodcaller`` und
    ``invokeMethod`` mit privatem Namen oder einer Variablen wie ``getattr``.
    """
    assert function_guard.forbidden_calls(UNSEEN_DETOURS[label]) != [], label


@pytest.mark.parametrize(
    "source",
    [
        "def run(button, name):\n    getattr(button, name)()",
        "def run(window, name):\n    setattr(window, name, False)",
        "def run(button, slot):\n    QMetaObject.invokeMethod(button, slot)",
        "def run(button, name):\n    operator.methodcaller(name)(button)",
        "def run(window, key):\n    vars(window)[key]",
        "from app.ui.main_window import action_save as save",
    ],
)
def test_a_name_only_the_run_knows_is_a_detour_once_it_acts(source: str) -> None:
    """Ein Name, den erst die Laufzeit kennt, ist ein Fund, sobald er bedient (C-M3).

    ``getattr`` mit einem solchen Namen darf lesen; wer das Ergebnis aufruft,
    setzt, eine Methode über Qt auslöst oder ``vars`` mit offenem Schlüssel
    liest, wird gefunden. Ein umbenannter Import zählt wie der Name selbst.
    """
    assert function_guard.forbidden_calls(source) != [], source


@pytest.mark.parametrize("source", ALLOWED_FORMS)
def test_the_guard_leaves_the_benchs_own_ways_alone(source: str) -> None:
    """Die Gegenseite: Was der Prüfstand heute rechtmäßig schreibt, bleibt frei."""
    assert function_guard.forbidden_calls(source) == [], source


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
    Fensterweg ``WindowFlow`` hat einen eigenen Test. Die nativen Läufer stehen
    unter dem Lesemodus des Wächters (``READING_MODULES``, Test darunter).
    """
    reading = set(function_guard.READING_MODULES)

    def unguarded(listed: set[str]) -> set[str]:
        return {
            path.stem
            for path in TOOLS.glob("*.py")
            if path.stem != "file_acceptance"
            and path.stem not in listed | reading
            and _imports(path) & listed
        }

    bench = set(function_guard.BENCH_MODULES)
    assert all((TOOLS / f"{module}.py").is_file() for module in bench | reading)
    assert not bench & reading, "ein Modul steht unter genau einer Regel"
    assert unguarded(bench) == set()
    # Gegenprobe: ``function_language`` benutzt ``function_bench`` und fiele auf.
    assert unguarded(bench - {"function_language"}) == {"function_language"}


@pytest.mark.parametrize("module", function_guard.READING_MODULES)
def test_the_native_runners_handle_through_input_and_only_read_what_is_private(
    module: str,
) -> None:
    """Die Ausnahme der nativen Läufer ist eng (RF10-1): bedienen wie der Prüfstand, Privates lesen.

    Sie messen Lage und Zugraum der Maßkarte oder ob die Anordnung ruht — Zustand
    ohne Schnittstelle. Erlaubt ist, ein privates Attribut zu lesen und am
    Gelesenen eine lesende Methode zu rufen; nicht erlaubt bleibt jeder Umweg
    des Prüfstands, ein privater Aufruf, ein Setzen und jede andere Methode an
    etwas privat Erreichtem.
    """
    assert function_guard.forbidden_calls(_source(module), private_reads=True) == []


def test_the_reading_exception_still_finds_every_detour() -> None:
    """Gegenprobe: Der Lesemodus lässt Lesen durch, sonst nichts."""
    allowed = (
        "def read(window, row):\n"
        "    room = window._placement._drag._room\n"
        "    box = window._placement._box.geometry()\n"
        "    shown = window._preview.isActive()\n"
        "    return room, box, shown, row._asdict(), row._replace(id=1)\n"
        "from tools.function_setup import apply_licence\n"
        "apply_licence('licensed')\n"
    )
    assert function_guard.forbidden_calls(allowed, private_reads=True) == []
    assert function_guard.forbidden_calls(allowed) != [], "ohne Ausnahme sind es Umwege"
    detours = {
        "window._placement._drag = None\n": "window._placement._drag",
        "window._placement._helper()\n": "window._placement._helper",
        "window._placement._drag.press(1)\n": "window._placement._drag.press",
        "window._placement._box.setGeometry(1)\n": "window._placement._box.setGeometry",
        "button.click()\n": "button.click",
        "window.measure.setValue(3)\n": "window.measure.setValue",
        "from tools.function_setup import apply_scene\n": "import apply_scene",
        # Über einen Namen: derselbe Umweg wie direkt geschrieben (RC2-11).
        "box = window._placement._box\nbox.setGeometry(1)\n": "box.setGeometry",
        "drag = window._placement._drag\ndrag.press(1)\n": "drag.press",
        "item = window._placement._box\nitem = item.parent()\nitem.setGeometry(1)\n": (
            "item.setGeometry"
        ),
    }
    # Ein Name, der an sich selbst gebunden ist, endet — kein Umweg, keine Schleife.
    looped = "row = row.next\nrow.geometry()\n"
    assert function_guard.forbidden_calls(looped, private_reads=True) == []
    for source, detour in detours.items():
        found = [call for _line, call in function_guard.forbidden_calls(source, private_reads=True)]
        assert detour in found, (source, found)


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
