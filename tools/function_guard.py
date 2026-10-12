"""Der Wächter des Prüfstands: keine Abkürzung am Fenster (D0-P, RM-737, Plan D0 B5).

Falle: **Ein Prüfstand am Fenster nimmt keine Abkürzung.** Jede Handlung ist
ein Eingabeereignis an der Stelle, die der Kunde trifft. ``click``,
``set_value*``, ``setText``, ``setCurrent*``, ``accept``, ``emit``,
``session.apply``, ``trigger``, ``select_*``, Undo/Redo über Methoden — auch
über ``getattr`` oder ``invokeMethod`` mit Zeichenkette — und private Namen
fremder Objekte sind Umwege (:data:`FORBIDDEN_CALLS`). Was so nicht erreichbar
ist, wird ein Ziel im Wortschatz, nie ein Zugriff auf private Attribute und nie
ein Kernaufruf.

:func:`forbidden_calls` findet sie im Quelltext; ``tests/test_function_guard.py``
fährt ihn über jedes Modul aus :data:`BENCH_MODULES` und über ``WindowFlow``
in ``tools/file_acceptance.py`` und hält, dass jedes Werkzeugmodul, das den
Prüfstand benutzt, in dieser Liste steht.
"""

from __future__ import annotations

import ast
from typing import Final

#: Die Module des Prüfstands unter ``tools/`` — jedes trägt Bedienung am Fenster
#: oder Bausteine dafür, und keines darf sie umgehen. ``WindowFlow`` in
#: ``file_acceptance`` prüft der Wächter für sich.
BENCH_MODULES: Final[tuple[str, ...]] = (
    "function_machine",
    "function_walk",
    "function_setup",
    "function_protocol",
    "function_guard",
    "function_bench",
    "function_start",
    "function_language",
    "function_capture",
)

#: Die Namen, über die eine Bedienung umgangen wird (Konzept §12 „Die Abkürzungen
#: der Bildwerkzeuge“, Plan D0 B5, Review M8). Ein Name mit ``*`` meint den
#: Anfang. ``setValue``, ``setCurrent*``, ``setChecked``, ``setText``,
#: ``setSelected``, ``toggle``, ``setFocus`` und ``animateClick`` sind dieselben
#: Abkürzungen in Qts Schreibweise; ``accept``, ``reject`` und ``done`` schließen
#: einen Dialog am Kunden vorbei, ``start_new`` und ``run_operation`` rufen den
#: Kern statt der Oberfläche, ``area_for`` deckt auf, statt den Weg zu gehen (B2).
FORBIDDEN_CALLS: Final[tuple[str, ...]] = (
    "click",
    "animateClick",
    "set_value*",
    "setValue",
    "setCurrent*",
    "setChecked",
    "setSelected",
    "setText",
    "setFocus",
    "toggle",
    "emit",
    "trigger",
    "select_*",
    "action_undo",
    "action_redo",
    "accept",
    "reject",
    "done",
    "start_new",
    "run_operation",
    "area_for",
)

#: Namen, die nur als Aufruf verboten sind: ``done`` heißt am Automaten „fertig“
#: (:attr:`StepMachine.done`), nur ``dialog.done(…)`` schließt einen Dialog.
CALL_ONLY: Final[frozenset[str]] = frozenset({"done"})

#: Private Namen fremder Objekte, die der Prüfstand berühren darf: die
#: Nahtstellen der Suite für die Vorbereitung (``tests/conftest.py``) und der
#: Aufrufstapel der Wache. Alles andere mit ``_`` an einem fremden Objekt ist
#: ein Umweg an der Oberfläche vorbei (Konzept §5).
ALLOWED_PRIVATE: Final[frozenset[str]] = frozenset(
    {"activation._cached", "discover._remembered_program", "sys._getframe"}
)


def _forbidden_name(name: str) -> bool:
    return any(
        name == pattern or (pattern.endswith("*") and name.startswith(pattern.rstrip("*")))
        for pattern in FORBIDDEN_CALLS
    )


def _private(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def forbidden_calls(source: str, *, within_class: str | None = None) -> list[tuple[int, str]]:
    """Wo ein Quelltext eine Bedienung umgeht: Zeile und Umweg (Review M8).

    Gefunden werden ein verbotener Name als Aufruf und als Zugriff (``press =
    button.click``), über ``getattr`` mit Zeichenkette, über
    ``QMetaObject.invokeMethod`` mit Zeichenkette, ``session.apply`` als
    Kernaufruf an der Oberfläche vorbei und jeder private Name an einem
    fremden Objekt — Attribut oder ``getattr`` — außer :data:`ALLOWED_PRIVATE`.
    ``within_class`` prüft nur den Rumpf dieser Klasse (``WindowFlow`` in
    ``file_acceptance``). Der Wächter in ``tests/test_function_guard.py`` fährt
    diese Funktion über jedes Modul aus :data:`BENCH_MODULES`, über ``WindowFlow``
    und über einen Quelltext mit allen bekannten Umwegen.
    """
    tree = ast.parse(source)
    roots: list[ast.AST] = [tree]
    if within_class is not None:
        roots = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == within_class
        ]
        if not roots:
            raise LookupError(f"Klasse {within_class} steht nicht im Quelltext")
    called = {
        id(node.func)
        for root in roots
        for node in ast.walk(root)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    found: set[tuple[int, str]] = set()
    for root in roots:
        for node in ast.walk(root):
            if isinstance(node, ast.Attribute):
                name, receiver = node.attr, ast.unparse(node.value)
                whole = f"{receiver}.{name}"
                core = name == "apply" and "session" in receiver.lower() and id(node) in called
                shortcut = _forbidden_name(name) and (name not in CALL_ONLY or id(node) in called)
                foreign = (
                    _private(name)
                    and receiver not in ("self", "cls")
                    and whole not in ALLOWED_PRIVATE
                )
                if core or shortcut or foreign:
                    found.add((node.lineno, whole))
            elif isinstance(node, ast.Call):
                label = ast.unparse(node.func)
                texts = [
                    argument.value
                    for argument in node.args
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
                ]
                second = node.args[1] if label == "getattr" and len(node.args) >= 2 else None
                named = (
                    second.value
                    if isinstance(second, ast.Constant) and isinstance(second.value, str)
                    else None
                )
                if named is not None and (_forbidden_name(named) or _private(named)):
                    found.add((node.lineno, f"getattr(…, {named!r})"))
                elif label.endswith("invokeMethod") and any(_forbidden_name(t) for t in texts):
                    found.add((node.lineno, f"{label}(…, {texts!r})"))
    return sorted(found)
