"""Der Wächter des Prüfstands: keine Abkürzung am Fenster (D0-P, RM-737, Plan D0 B5).

Falle: **Ein Prüfstand am Fenster nimmt keine Abkürzung.** Jede Handlung ist
ein Eingabeereignis an der Stelle, die der Kunde trifft. ``click``,
``set_value*``, ``setText`` und die übrigen Wertsetzer, ``setCurrent*``,
``accept``, ``emit``, ``session.apply`` (auch über einen Alias), ``trigger``,
``activate``, ``select_*``, ``action_*``, ``apply_*``, Undo/Redo über
Methoden, Ereignismethoden wie ``keyPressEvent`` direkt — auch über
``getattr``, ``setattr``, ``vars``, ``__dict__``, ``methodcaller`` oder
``invokeMethod`` mit Zeichenkette oder Variable, auch als importierter Name —
und private Namen fremder Objekte sind Umwege (:data:`FORBIDDEN_CALLS`). Was so
nicht erreichbar ist, wird ein Ziel im Wortschatz, nie ein Zugriff auf private
Attribute und nie ein Kernaufruf.

:func:`forbidden_calls` findet sie im Quelltext; ``tests/test_function_guard.py``
fährt ihn über jedes Modul aus :data:`BENCH_MODULES` und über ``WindowFlow``
in ``tools/file_acceptance.py`` und hält, dass jedes Werkzeugmodul, das den
Prüfstand benutzt, in dieser Liste steht. Die nativen Läufer
(:data:`READING_MODULES`) stehen unter einer engen Ausnahme: Privates dürfen sie
lesen, nicht bedienen.

**Grenze:** Ein Wächter über den Quelltext sieht Namen, keine Typen. Ein Name an
``self``, ``cls`` oder ``super()`` gilt als eigene Methode des Prüfstands; ein
Name, den erst die Laufzeit kennt, ist ein Fund, sobald er ein fremdes Objekt
bedient oder aufgerufen wird.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator
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
    "function_gestures",
    "function_switch",
    "function_matrix",
    "function_cases",
    "function_revision",
    "function_surface",
    "function_start",
    "function_language",
    "function_capture",
    "function_spot",
    "function_prediction",
    "function_fonts",
    "function_way",
    "function_tooltips",
)

#: Die Namen, über die eine Bedienung umgangen wird (Konzept §12 „Die Abkürzungen
#: der Bildwerkzeuge“, Plan D0 B5, Review M8, Durchsicht welle4 C-M3). Ein Name
#: mit ``*`` meint den Anfang. ``setValue``, ``setCurrent*``, ``setChecked``,
#: ``setCheckState``, ``setText``, ``setPlainText``, ``insertPlainText``,
#: ``setEditText``, ``setDate``, ``setTime``, ``setDateTime``,
#: ``setSliderPosition``, ``setSelected``, ``toggle``, ``setFocus`` und
#: ``animateClick`` sind dieselben Abkürzungen in Qts Schreibweise, ``activate``
#: ist ``trigger`` an einer ``QAction``; ``accept``, ``reject`` und ``done``
#: schließen einen Dialog am Kunden vorbei, ``start_new`` und ``run_operation``
#: rufen den Kern statt der Oberfläche, ``area_for`` deckt auf, statt den Weg zu
#: gehen (B2). ``action_*`` sind die Handlungen des Hauptfensters, ``apply_*``
#: die öffentlichen Übernahmen von Tafeln und Dialogen, ``undo`` und ``redo``
#: nehmen Schritte an Sitzung oder Verlauf zurück.
FORBIDDEN_CALLS: Final[tuple[str, ...]] = (
    "click",
    "animateClick",
    "set_value*",
    "setValue",
    "setCurrent*",
    "setChecked",
    "setCheckState",
    "setSelected",
    "setText",
    "setPlainText",
    "insertPlainText",
    "setEditText",
    "setDate",
    "setTime",
    "setDateTime",
    "setSliderPosition",
    "setFocus",
    "toggle",
    "emit",
    "trigger",
    "activate",
    "select_*",
    "action_*",
    "apply_*",
    "undo",
    "redo",
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

#: Aufrufe, die einen verbotenen Namen tragen und doch keiner sind:
#: ``machine.insert`` reiht Schritte in den Automaten ein,
#: ``guide_targets.action_for`` liest die Handlung zu einem Ziel nur nach,
#: ``style.apply_style`` gibt die Schrift des Falls durch den Stilweg der
#: Anwendung wie ein Wechsel der Systemschrift (``function_fonts``) — eine
#: Bedingung des Falls wie Thema und Skalierung, keine Bedienung.
ALLOWED_CALLS: Final[frozenset[str]] = frozenset(
    {"machine.insert", "guide_targets.action_for", "QTest.wheelEvent", "style.apply_style"}
)

#: Private Namen fremder Objekte, die der Prüfstand berühren darf: die
#: Nahtstellen der Suite für die Vorbereitung (``tests/conftest.py``) und der
#: Aufrufstapel der Wache. Alles andere mit ``_`` an einem fremden Objekt ist
#: ein Umweg an der Oberfläche vorbei (Konzept §5).
ALLOWED_PRIVATE: Final[frozenset[str]] = frozenset(
    {"activation._cached", "discover._remembered_program", "sys._getframe"}
)

#: Die nativen Läufer (F10, RF10-1). Sie fahren den Prüfstand am echten Fenster
#: und messen dabei Zustand, den keine Schnittstelle anbietet: Lage und Zugraum der
#: Maßkarte, ob die Anordnung ruht, ob eine Vorschau läuft. Eine öffentliche
#: Schnittstelle dafür hieße neue Methoden in ``main_window.py`` und den Karten,
#: die über der Größengrenze stehen (Regel 6), nur für einen Messläufer. Die
#: Ausnahme ist deshalb eng: Sie bedienen wie jedes Modul des Prüfstands nur über
#: Eingabeereignisse, und Privates dürfen sie **nur lesen**
#: (``forbidden_calls(…, private_reads=True)``, ``tests/test_function_guard.py``).
READING_MODULES: Final[tuple[str, ...]] = ("native_runs", "native_measure_card", "native_binding")

#: Was ein Läufer an einem privat erreichten Objekt aufrufen darf: Qts lesende
#: Methoden, die die Läufer brauchen. ``is*`` meint ``isVisible``, ``isChecked`` …
READERS: Final[tuple[str, ...]] = (
    "is*",
    "geometry",
    "layout",
    "itemAt",
    "widget",
    "findChild",
    "findChildren",
    "values",
    "boundingRect",
    "center",
    "x",
    "y",
    "property",
    "mapToGlobal",
    "visibleRegion",
    "toolTip",
    "accessibleDescription",
)

#: Die öffentliche Schnittstelle eines ``NamedTuple``: Sie heißt mit ``_``, damit
#: sie keinem Feld im Weg steht, und liefert nur neue Daten.
NAMEDTUPLE_API: Final[frozenset[str]] = frozenset({"_asdict", "_replace", "_fields", "_make"})

#: Die Vorbereitung eines Falls vor dem Fenster, die ein Läufer wie
#: ``file_acceptance`` selbst setzt: der Lizenzzustand über die Nahtstelle der
#: Suite. Sie bedient nichts; der Name trägt nur ``apply_``.
PREPARATION: Final[frozenset[str]] = frozenset({"apply_licence", "apply_preconditions"})


def _reader(name: str) -> bool:
    """Eine lesende Methode: ein Name aus :data:`READERS` oder ``isX…``."""
    for pattern in READERS:
        prefix = pattern.rstrip("*")
        if name == pattern or (
            pattern.endswith("*")
            and name.startswith(prefix)
            and name[len(prefix) : len(prefix) + 1].isupper()
        ):
            return True
    return False


def _through_private(
    expression: ast.expr, resolve: Callable[[ast.expr], ast.expr] | None = None
) -> bool:
    """Ob ein Ausdruck über ein privates Attribut eines fremden Objekts läuft.

    Mit ``resolve`` (``_Bindings.resolve``) auch über einen Namen, der an einen
    solchen Ausdruck gebunden ist: ``box = window._placement._box`` und danach
    ``box.setGeometry(…)`` ist derselbe Umweg wie direkt geschrieben (RC2-11).
    """
    seen: set[int] = set()

    def follow(expression: ast.expr) -> ast.expr:
        # ``x = x.y`` bindet einen Namen an sich selbst: jeder Knoten nur einmal.
        while isinstance(expression, ast.Name) and resolve is not None:
            if id(expression) in seen:
                return ast.Constant(None)
            seen.add(id(expression))
            found = resolve(expression)
            if found is expression:
                break
            expression = found
        return expression

    expression = follow(expression)
    while isinstance(expression, (ast.Attribute, ast.Call, ast.Subscript)):
        if isinstance(expression, ast.Attribute):
            receiver = ast.unparse(expression.value)
            whole = f"{receiver}.{expression.attr}"
            if (
                _private(expression.attr)
                and receiver not in ("self", "cls")
                and whole not in ALLOWED_PRIVATE
            ):
                return True
            expression = expression.value
        elif isinstance(expression, ast.Call):
            expression = expression.func
        else:
            expression = expression.value
        expression = follow(expression)
    return False


#: Empfänger, deren Namen dem Prüfstand selbst gehören.
OWN: Final[frozenset[str]] = frozenset({"self", "cls", "super()"})

#: Die Wege, auf denen Qt ein Ereignis zustellt — sie sind Eingabe, nicht
#: Umweg. Jeder andere Name auf ``…Event`` ist eine Ereignismethode, die man
#: nicht selbst ruft (``keyPressEvent``, ``mousePressEvent``, ``wheelEvent``).
EVENT_DELIVERY: Final[frozenset[str]] = frozenset(
    {"sendEvent", "postEvent", "sendKeyEvent", "keyEvent", "mouseEvent", "touchEvent"}
)

#: Aufrufe, die einen Namen als Zeichenkette nehmen, mit der Stelle des Namens.
#: ``getattr`` nur liest, solange niemand das Ergebnis aufruft.
NAMED_ACCESS: Final[dict[str, int]] = {
    "getattr": 1,
    "setattr": 1,
    "delattr": 1,
    "invokeMethod": 1,
    "methodcaller": 0,
    "attrgetter": 0,
}


def _forbidden_name(name: str) -> bool:
    return any(
        name == pattern or (pattern.endswith("*") and name.startswith(pattern.rstrip("*")))
        for pattern in FORBIDDEN_CALLS
    )


def _private(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _event_method(name: str) -> bool:
    """Eine Ereignismethode eines Widgets: ``event``, ``eventFilter``, ``…Event``."""
    if name in ("event", "eventFilter"):
        return True
    return name.endswith("Event") and name[:1].islower() and name not in EVENT_DELIVERY


def _scope_nodes(tree: ast.AST) -> Iterator[ast.AST]:
    """Ein Namensraum ohne Rümpfe darin definierter Funktionen und Klassen."""
    yield tree
    for child in ast.iter_child_nodes(tree):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from _scope_nodes(child)


def _string_values(tree: ast.AST) -> dict[str, set[str] | None]:
    """Je Name die Zeichenketten, die ihm zugewiesen werden; ``None``, wenn auch anderes.

    So liest der Wächter ``name = 'click'`` vor ``getattr(button, name)``. Eine
    Schleifenvariable, ein Parameter oder ein berechneter Wert bleibt unbekannt.
    """
    values: dict[str, set[str] | None] = {}
    for node in _scope_nodes(tree):
        if isinstance(node, ast.Assign):
            pairs = [(target, node.value) for target in node.targets]
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            pairs = [(node.target, node.value)]
        elif isinstance(node, (ast.For, ast.comprehension)):
            pairs = [(node.target, None)]
        else:
            continue
        for target, value in pairs:
            if not isinstance(target, ast.Name):
                continue
            known = values.setdefault(target.id, set())
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                if known is not None:
                    known.add(value.value)
            else:
                values[target.id] = None
    return values


def _names_of(argument: ast.expr, values: dict[str, set[str] | None]) -> tuple[list[str], bool]:
    """Die Namen, die ein Argument tragen kann, und ob es weitere geben kann."""
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return [argument.value], False
    if isinstance(argument, ast.Name):
        known = values.get(argument.id)
        if known:
            return sorted(known), False
    return [], True


def _bound_at(target: ast.AST, value: ast.expr | None) -> tuple[float, int]:
    """Ab welcher Stelle eine Bindung gilt: hinter ihrem Wert, sonst an ihrem Ziel."""
    if value is None:
        return (target.lineno, target.col_offset)
    return (value.end_lineno or value.lineno, value.end_col_offset or value.col_offset)


class _Bindings:
    """Lexikalische Bindungen für Aliase, mit Reihenfolge und verdeckenden Parametern.

    Ein Alias erbt den Wert zum Zeitpunkt seiner Zuweisung. Eine spätere
    Neubelegung der Quelle ändert ihn nicht; gleichnamige Nachbarfunktionen
    teilen keine Bindung. Innere Funktionen dürfen dagegen äußere Namen lesen.
    """

    def __init__(self, tree: ast.AST) -> None:
        self.scopes: dict[ast.AST, ast.AST] = {}
        self.parents: dict[ast.AST, ast.AST] = {}
        self.values: dict[ast.AST, dict[str, list[tuple[ast.AST, ast.expr | None]]]] = {}
        self.collect(tree, tree)

    def collect(self, node: ast.AST, scope: ast.AST) -> None:
        if node is not scope and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            self.parents[node] = scope
            scope = node
        self.scopes[node] = scope
        values = self.values.setdefault(scope, {})
        pairs: list[tuple[ast.AST, ast.expr | None]] = []
        if isinstance(node, ast.Assign):
            pairs = [(target, node.value) for target in node.targets]
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            pairs = [(node.target, node.value)]
        elif isinstance(node, (ast.For, ast.comprehension)):
            pairs = [(node.target, None)]
        elif isinstance(node, ast.arg):
            values.setdefault(node.arg, []).append((node, None))
        for target, value in pairs:
            if isinstance(target, ast.Name):
                values.setdefault(target.id, []).append((target, value))
        for child in ast.iter_child_nodes(node):
            self.collect(child, scope)

    def resolve(self, expression: ast.expr) -> ast.expr:
        """Folgt einer Namenskette zu ihrem Wert; Unbekanntes bleibt ein Name."""
        seen: set[ast.AST] = set()
        while isinstance(expression, ast.Name) and expression not in seen:
            seen.add(expression)
            scope = self.scopes[expression]
            before = (expression.lineno, expression.col_offset)
            while expression.id not in self.values[scope] and scope in self.parents:
                scope = self.parents[scope]
                # Klassenattribute sind keine lexikalischen Variablen der Methode.
                while isinstance(scope, ast.ClassDef) and scope in self.parents:
                    scope = self.parents[scope]
                before = (float("inf"), 0)
            # Eine Zuweisung bindet erst nach ihrem Wert: In ``x = x.y`` meint das
            # rechte ``x`` die Bindung davor, nicht sich selbst.
            candidates = [
                (target, value)
                for target, value in self.values[scope].get(expression.id, [])
                if _bound_at(target, value) <= before
            ]
            if not candidates:
                break
            _target, value = max(candidates, key=lambda pair: (pair[0].lineno, pair[0].col_offset))
            if value is None or value in seen:
                break
            expression = value
        return expression

    def sessions(self, expression: ast.expr) -> set[str]:
        """Ob der Empfänger direkt oder durch Aliase die Sitzung hält."""
        value = self.resolve(expression)
        held = value.attr if isinstance(value, ast.Attribute) else getattr(value, "id", "")
        return {ast.unparse(expression)} if held == "session" else set()


def _imported_forbidden(tree: ast.AST) -> dict[str, str]:
    """Verbotene Namen, die als Name importiert werden: lokaler Name → Original."""
    return {
        alias.asname or alias.name: alias.name
        for node in _scope_nodes(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if _forbidden_name(alias.name) or _event_method(alias.name)
    }


def _attribute_detour(
    node: ast.Attribute, called: set[int], sessions: set[str], *, private_reads: bool = False
) -> bool:
    name, receiver = node.attr, ast.unparse(node.value)
    whole = f"{receiver}.{name}"
    if whole in ALLOWED_CALLS:
        return False
    own = receiver in OWN
    is_called = id(node) in called
    core = name == "apply" and ("session" in receiver.lower() or receiver in sessions)
    shortcut = not own and _forbidden_name(name) and (name not in CALL_ONLY or is_called)
    event = not own and _event_method(name)
    foreign = _private(name) and receiver not in ("self", "cls") and whole not in ALLOWED_PRIVATE
    if foreign and private_reads:
        # Ein Läufer liest: kein Aufruf, kein Setzen — außer der Schnittstelle
        # eines ``NamedTuple``, die nur neue Daten liefert.
        reading = isinstance(node.ctx, ast.Load) and not is_called
        foreign = not (reading or (is_called and name in NAMEDTUPLE_API))
    return core or shortcut or event or foreign


def _named_access(
    node: ast.Call,
    label: str,
    values: dict[str, set[str] | None],
    called: set[int],
    sessions: set[str],
) -> str | None:
    """``getattr``, ``setattr``, ``invokeMethod`` und Verwandte: Zeichenkette oder Variable."""
    kind = label.rsplit(".", 1)[-1]
    if kind not in NAMED_ACCESS:
        return None
    position = NAMED_ACCESS[kind]
    if len(node.args) <= position:
        return None
    receiver = ast.unparse(node.args[0]) if kind not in ("methodcaller", "attrgetter") else ""
    arguments = node.args[position:] if kind == "attrgetter" else [node.args[position]]
    for argument in arguments:
        names, open_ended = _names_of(argument, values)
        for name in names:
            if f"{receiver}.{name}" in ALLOWED_PRIVATE:
                continue
            core = name == "apply" and ("session" in receiver.lower() or receiver in sessions)
            if core or _forbidden_name(name) or _private(name) or _event_method(name):
                return f"{label}(…, {name!r})"
        # Ein Name, den erst die Laufzeit kennt: Lesen bleibt Lesen, aber wer
        # das Ergebnis aufruft oder etwas setzt, bedient vielleicht.
        acts = kind != "getattr" or id(node) in called
        if open_ended and receiver not in OWN and acts:
            return f"{label}(…, {ast.unparse(argument)})"
    return None


def _dictionary_detour(node: ast.Subscript, values: dict[str, set[str] | None]) -> str | None:
    """``vars(x)[…]`` und ``x.__dict__[…]`` an einem fremden Objekt."""
    held = node.value
    if isinstance(held, ast.Call) and ast.unparse(held.func) == "vars" and held.args:
        receiver = ast.unparse(held.args[0])
    elif isinstance(held, ast.Attribute) and held.attr == "__dict__":
        receiver = ast.unparse(held.value)
    else:
        return None
    if receiver in OWN:
        return None
    names, open_ended = _names_of(node.slice, values)
    writes = isinstance(node.ctx, (ast.Store, ast.Del))
    if writes or open_ended or any(_private(n) or _forbidden_name(n) for n in names):
        return ast.unparse(node)
    return None


def forbidden_calls(
    source: str, *, within_class: str | None = None, private_reads: bool = False
) -> list[tuple[int, str]]:
    """Wo ein Quelltext eine Bedienung umgeht: Zeile und Umweg (Review M8, C-M3).

    Gefunden werden ein verbotener Name als Aufruf und als Zugriff (``press =
    button.click``), als importierter Name (``from … import area_for``) und als
    dessen Aufruf; eine Ereignismethode an einem fremden Objekt; ``getattr``,
    ``setattr``, ``delattr``, ``QMetaObject.invokeMethod``, ``methodcaller`` und
    ``attrgetter`` mit einem verbotenen oder privaten Namen — als Zeichenkette
    oder als Variable, der eine solche zugewiesen wird — und mit einem Namen,
    den erst die Laufzeit kennt, sobald er ein fremdes Objekt setzt oder
    aufgerufen wird; ``vars(x)[…]`` und ``x.__dict__[…]`` an einem fremden
    Objekt; ``session.apply`` als Kernaufruf an der Oberfläche vorbei, auch über
    einen Alias der Sitzung; und jeder private Name an einem fremden Objekt
    außer :data:`ALLOWED_PRIVATE`. ``insert`` mit einem Argument setzt Text in
    eine Zeile; mit zweien ist es das der Liste. ``within_class`` prüft nur den
    Rumpf dieser Klasse (``WindowFlow`` in ``file_acceptance``). Der Wächter in
    ``tests/test_function_guard.py`` fährt diese Funktion über jedes Modul aus
    :data:`BENCH_MODULES`, über ``WindowFlow`` und über Quelltexte mit allen
    bekannten Umwegen. ``private_reads`` ist die Ausnahme der nativen Läufer
    (:data:`READING_MODULES`): Ein privates Attribut darf gelesen werden, und
    an dem, was es liefert, nur eine lesende Methode (:data:`READERS`); setzen,
    privat aufrufen oder darüber etwas anderes aufrufen bleibt ein Umweg.
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
    scopes = [
        node
        for root in roots
        for node in ast.walk(root)
        if node is root
        or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))
    ]
    bindings = _Bindings(tree)
    called = {
        id(value)
        for root in roots
        for node in ast.walk(root)
        if isinstance(node, ast.Call)
        for value in (node.func, bindings.resolve(node.func))
    }
    found: set[tuple[int, str]] = set()
    for scope in scopes:
        values = _string_values(scope)
        imported = _imported_forbidden(scope)
        if private_reads:
            imported = {local: name for local, name in imported.items() if name not in PREPARATION}
        for node in _scope_nodes(scope):
            if isinstance(node, ast.Attribute):
                if _attribute_detour(
                    node, called, bindings.sessions(node.value), private_reads=private_reads
                ):
                    found.add((node.lineno, f"{ast.unparse(node.value)}.{node.attr}"))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if (alias.asname or alias.name) in imported:
                        found.add((node.lineno, f"import {alias.name}"))
            elif isinstance(node, ast.Subscript):
                dictionary = _dictionary_detour(node, values)
                if dictionary is not None:
                    found.add((node.lineno, dictionary))
            elif isinstance(node, ast.Call):
                label = ast.unparse(node.func)
                if (
                    private_reads
                    and isinstance(node.func, ast.Attribute)
                    and not _private(node.func.attr)
                    and not _reader(node.func.attr)
                    and _through_private(node.func.value, bindings.resolve)
                ):
                    # Was über Privates erreicht ist, wird nur gelesen.
                    found.add((node.lineno, label))
                if isinstance(node.func, ast.Name) and node.func.id in imported:
                    found.add((node.lineno, f"{node.func.id}(…)"))
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "insert"
                    and len(node.args) == 1
                    and label not in ALLOWED_CALLS
                    and ast.unparse(node.func.value) not in OWN
                ):
                    found.add((node.lineno, label))
                sessions = bindings.sessions(node.args[0]) if node.args else set()
                named = _named_access(node, label, values, called, sessions)
                if named is not None:
                    found.add((node.lineno, named))
    return sorted(found)
