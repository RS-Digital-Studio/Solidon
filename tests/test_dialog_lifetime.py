"""Ein Dialog unter ``app/ui`` gibt sich frei, sobald er geschlossen ist (A-L1).

``exec`` und ``open`` geben einen Dialog nicht frei: Ohne ``deleteLater`` hängt
nach jedem Aufruf ein verborgener Dialog mehr am Elternteil, und mit ihm alles,
was er hält. Die Bauart steht in ``ask_text``: ``try: exec … finally:
deleteLater()``. Ein Dialog, der offen bleibt (``open``, ``show``), gibt sich über
``WA_DeleteOnClose``, über ``finished.connect(x.deleteLater)`` oder in dem
Rückruf frei, an den sein Ende geht.

Der Wächter liest den Quelltext und braucht kein Fenster. Er zählt, was er
geprüft hat, und scheitert bei zu wenig — eine Suche, die nichts mehr findet,
ist sonst grün.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "app" / "ui"

#: Die Dialoge von Qt, die ``app/ui`` selbst baut oder ableitet.
QT_DIALOGS = frozenset(
    {
        "QDialog",
        "QMessageBox",
        "QFileDialog",
        "QInputDialog",
        "QColorDialog",
        "QFontDialog",
        "QProgressDialog",
        "QErrorMessage",
        "QWizard",
    }
)

#: Was einen Dialog stehen lässt, ohne zu warten — er muss sich selbst freigeben.
OPENERS = frozenset({"open", "show"})

#: Wie viele Stellen der Wächter im Baum mindestens prüft. Gezählt am Stand der
#: Nachprüfung; fällt die Zahl darunter, greift die Suche nicht mehr.
LEAST_CHECKED = 70


@dataclass
class Scan:
    """Was der Gang über die Quelltexte gefunden hat."""

    missing: list[str] = field(default_factory=list)
    checked: int = 0


def _name(node: ast.AST) -> str:
    """``f`` aus ``f(…)``, ``x.f(…)`` oder ``Klasse.f`` — sonst leer."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


#: Knoten je Funktion und Funktionen je Baum, für einen Gang gemerkt — ``app/ui``
#: zählt Zehntausende Funktionen, und jede Frage ginge sonst den Baum neu ab.
#: :func:`scan` leert beides am Ende.
_OWN: dict[ast.AST, list[ast.AST]] = {}
_FUNCTIONS: dict[ast.AST, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}


def _own(function: ast.AST) -> list[ast.AST]:
    """Die Knoten einer Funktion ohne die eingeschachtelter Funktionen und Klassen."""
    if function not in _OWN:
        found: list[ast.AST] = []
        pending = list(ast.iter_child_nodes(function))
        while pending:
            node = pending.pop()
            found.append(node)
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
            ):
                pending.extend(ast.iter_child_nodes(node))
        _OWN[function] = found
    return _OWN[function]


def _functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    if tree not in _FUNCTIONS:
        _FUNCTIONS[tree] = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    return _FUNCTIONS[tree]


def _dialog_classes(trees: dict[Path, ast.Module]) -> set[str]:
    """Jede Klasse unter ``app/ui``, die von einem Dialog abstammt — transitiv."""
    bases = {
        node.name: {_name(base) for base in node.bases}
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }
    found = set(QT_DIALOGS)
    grown = True
    while grown:
        grown = False
        for name, parents in bases.items():
            if name not in found and parents & found:
                found.add(name)
                grown = True
    return found


def _builders(trees: dict[Path, ast.Module], classes: set[str]) -> set[str]:
    """Dialogklassen und Fabriken: Funktionen, die einen gebauten Dialog zurückgeben."""
    builders = set(classes)
    grown = True
    while grown:
        grown = False
        for tree in trees.values():
            for function in _functions(tree):
                if function.name in builders:
                    continue
                bound = _bound(function, builders)
                for node in _own(function):
                    if not (isinstance(node, ast.Return) and node.value is not None):
                        continue
                    value = node.value
                    if _built(value, builders) or ast.unparse(value) in bound:
                        builders.add(function.name)
                        grown = True
                        break
    return builders


def _built(node: ast.AST, builders: set[str]) -> bool:
    return isinstance(node, ast.Call) and _name(node.func) in builders


def _bound(function: ast.AST, builders: set[str]) -> set[str]:
    """Die Namen und Attribute, an die die Funktion einen gebauten Dialog bindet."""
    bound: set[str] = set()
    for node in _own(function):
        if isinstance(node, ast.Assign) and _built(node.value, builders):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target] if _built(node.value, builders) else []
        else:
            continue
        bound.update(
            ast.unparse(target)
            for target in targets
            if isinstance(target, (ast.Name, ast.Attribute))
        )
    return bound


def _is(node: ast.AST, key: str, attribute: str) -> bool:
    """``<key>.<attribute>``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attribute
        and ast.unparse(node.value) == key
    )


def _frees(node: ast.AST, key: str | None = None, releasers: frozenset[str] = frozenset()) -> bool:
    """Ob in ``node`` ein ``deleteLater`` steht — an ``key`` oder, ohne ``key``, an irgendetwas.

    Ein Aufruf einer Freigabehilfe (:func:`_releasers`) mit ``key`` zählt mit.
    """
    for inner in ast.walk(node):
        if (
            isinstance(inner, ast.Attribute)
            and inner.attr == "deleteLater"
            and (key is None or ast.unparse(inner.value) == key)
        ):
            return True
        if (
            key is not None
            and isinstance(inner, ast.Call)
            and _name(inner.func) in releasers
            and any(ast.unparse(arg) == key for arg in inner.args)
        ):
            return True
    return False


def _parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Die Parameter, die ein Aufrufer übergibt — ohne ``self``."""
    names = [arg.arg for arg in function.args.args]
    return names[1:] if names[:1] == ["self"] else names


def _releasers(trees: dict[Path, ast.Module]) -> frozenset[str]:
    """Funktionen, die einen ihrer Parameter freigeben (``_release_dialog(dialog)``)."""
    found: set[str] = set()
    for tree in trees.values():
        for function in _functions(tree):
            freed = {
                ast.unparse(node.value)
                for node in ast.walk(function)
                if isinstance(node, ast.Attribute) and node.attr == "deleteLater"
            }
            if freed & set(_parameters(function)):
                found.add(function.name)
    return frozenset(found)


def _exec_runs(statement: ast.AST, key: str) -> list[ast.Call]:
    return [
        call
        for call in ast.walk(statement)
        if isinstance(call, ast.Call) and _is(call.func, key, "exec")
    ]


def _freed_in_finally(function: ast.AST, key: str, releasers: frozenset[str]) -> set[int]:
    """Die Zeilen der ``exec``-Aufrufe an ``key`` in einem ``try``, dessen ``finally`` freigibt."""
    lines: set[int] = set()
    for guard in ast.walk(function):
        if not isinstance(guard, ast.Try):
            continue
        if not any(_frees(done, key, releasers) for done in guard.finalbody):
            continue
        for statement in guard.body:
            lines.update(call.lineno for call in _exec_runs(statement, key))
    return lines


def _method_frees(owner: ast.ClassDef, name: str, seen: frozenset[str] = frozenset()) -> bool:
    """Ob die Methode ``name`` etwas freigibt — selbst oder über ``self.<andere>()``."""
    for method in owner.body:
        if not (
            isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name == name
        ):
            continue
        if _frees(method):
            return True
        called = {
            call.func.attr
            for call in ast.walk(method)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and ast.unparse(call.func.value) == "self"
        }
        return any(_method_frees(owner, other, seen | {name}) for other in called - seen - {name})
    return False


def _handler_frees(handler: ast.AST, owner: ast.ClassDef | None, function: ast.AST) -> bool:
    """Ob der Rückruf am Ende des Dialogs etwas freigibt.

    ``self.m``, ``Klasse.m`` und ``weak_slot(self, Klasse.m, …)`` meinen eine
    Methode der umgebenden Klasse, gefragt samt der Methoden, die sie ruft; eine
    eingeschachtelte Funktion oder ein Lambda zählt mit ihrem Rumpf.
    """
    if (
        isinstance(handler, ast.Call)
        and _name(handler.func) == "weak_slot"
        and len(handler.args) > 1
    ):
        handler = handler.args[1]
    if isinstance(handler, ast.Lambda):
        return _frees(handler)
    name = _name(handler)
    if isinstance(handler, ast.Name):
        for inner in ast.walk(function):
            if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)) and inner.name == name:
                return _frees(inner)
    return owner is not None and _method_frees(owner, name)


def _left_open_freed(
    function: ast.AST, key: str, owner: ast.ClassDef | None, releasers: frozenset[str]
) -> bool:
    """Ob ein Dialog, der ohne zu warten steht, sich selbst freigibt."""
    if _frees(function, key, releasers):
        return True
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        target = node.func
        if (
            target.attr == "setAttribute"
            and ast.unparse(target.value) == key
            and "WA_DeleteOnClose" in ast.unparse(node)
            and not any(isinstance(arg, ast.Constant) and arg.value is False for arg in node.args)
        ):
            return True
        if (
            target.attr == "connect"
            and isinstance(target.value, ast.Attribute)
            and target.value.attr in {"finished", "accepted", "rejected"}
            and ast.unparse(target.value.value) == key
            and node.args
            and _handler_frees(node.args[0], owner, function)
        ):
            return True
    return False


def _exec_helpers(
    trees: dict[Path, ast.Module],
) -> dict[str, tuple[ast.FunctionDef | ast.AsyncFunctionDef, Path, dict[int, str]]]:
    """Funktionen, die ``exec`` an einem ihrer Parameter rufen: Name → (Funktion, Ort,
    Stelle des Arguments → Name des Parameters)."""
    helpers = {}
    for path, tree in trees.items():
        for function in _functions(tree):
            run = {
                ast.unparse(node.func.value)
                for node in _own(function)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "exec"
            }
            places = {
                index: name for index, name in enumerate(_parameters(function)) if name in run
            }
            if places:
                helpers[function.name] = (function, path, places)
    return helpers


def scan(root: Path) -> Scan:
    """Jede Stelle unter ``root``, an der ein Dialog nach ``exec`` oder ``open`` stehen bleibt."""
    trees = {
        path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(root.rglob("*.py"))
    }
    try:
        return _scan(root, trees)
    finally:
        _OWN.clear()
        _FUNCTIONS.clear()


def _scan(root: Path, trees: dict[Path, ast.Module]) -> Scan:
    builders = _builders(trees, _dialog_classes(trees))
    helpers = _exec_helpers(trees)
    releasers = _releasers(trees)
    result = Scan()
    passed: dict[str, list[str]] = {}
    for path, tree in trees.items():
        where = path.relative_to(root).as_posix()
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for function in _functions(tree):
            holder: ast.AST | None = parents.get(function)
            while holder is not None and not isinstance(holder, ast.ClassDef):
                holder = parents.get(holder)
            owner = holder if isinstance(holder, ast.ClassDef) else None
            bound = _bound(function, builders)
            freed = {key: _freed_in_finally(function, key, releasers) for key in bound}
            label = f"{where}:{function.name}"
            for node in _own(function):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    action, value = node.func.attr, node.func.value
                    if action in {"exec", *OPENERS} and _built(value, builders):
                        result.checked += 1
                        result.missing.append(f"{label}:{node.lineno} {action} ohne Namen")
                        continue
                    key = ast.unparse(value)
                    if key in bound and action == "exec":
                        result.checked += 1
                        if node.lineno not in freed[key]:
                            result.missing.append(
                                f"{label}:{node.lineno} exec ohne deleteLater im finally"
                            )
                        continue
                    if key in bound and action in OPENERS:
                        result.checked += 1
                        if not _left_open_freed(function, key, owner, releasers):
                            result.missing.append(f"{label}:{node.lineno} {action} gibt nie frei")
                        continue
                if isinstance(node, ast.Call) and _name(node.func) in helpers:
                    helper, _place, places = helpers[_name(node.func)]
                    given = [node.args[index] for index in places if index < len(node.args)]
                    if any(_built(arg, builders) or ast.unparse(arg) in bound for arg in given):
                        result.checked += 1
                        if not all(
                            _freed_in_finally(helper, name, releasers) for name in places.values()
                        ):
                            result.missing.append(
                                f"{label}:{node.lineno} übergibt an {helper.name}, "
                                "das nicht freigibt"
                            )
                            passed.setdefault(helper.name, []).append(label)
                above = parents.get(node)
                if (
                    isinstance(node, ast.Attribute)
                    and node.attr == "exec"
                    and ast.unparse(node.value) in bound
                    and not (isinstance(above, ast.Call) and above.func is node)
                ):
                    # ``QTimer.singleShot(0, box.exec)``: Das ``exec`` läuft später,
                    # kein ``finally`` kommt danach — freigeben muss das Ende.
                    result.checked += 1
                    if not _left_open_freed(function, ast.unparse(node.value), owner, releasers):
                        result.missing.append(f"{label}:{node.lineno} exec später, gibt nie frei")
    for name in sorted(passed):
        helper, place, _places = helpers[name]
        result.missing.append(
            f"{place.relative_to(root).as_posix()}:{name}:{helper.lineno} exec am Parameter "
            "ohne finally"
        )
    return result


def test_every_dialog_is_freed_after_it_closes() -> None:
    """Jeder Dialog unter ``app/ui`` gibt sich nach ``exec``, ``open`` oder ``show`` frei."""
    found = scan(UI)
    assert not found.missing, "Dialoge, die am Elternteil liegen bleiben:\n" + "\n".join(
        found.missing
    )
    assert found.checked >= LEAST_CHECKED, (
        f"nur {found.checked} Stellen geprüft — die Suche greift nicht mehr"
    )


#: Die Formen, die der Wächter sehen muss — die acht der Nachprüfung (Sonde
#: ``sonde_waechter``) und die zwei der ersten Fassung.
LEFT_STANDING = """
class MessageDialog(QDialog):
    pass
class Own(MessageDialog):
    pass
class Grand(Own):
    pass
def bare(parent):
    MessageDialog(parent).exec()
def kept(parent):
    box = Own(parent)
    box.exec()
def annotated(parent):
    box: MessageDialog = MessageDialog(parent)
    box.exec()
def attribute(self):
    self.box = MessageDialog(self)
    self.box.exec()
def _make(parent):
    return MessageDialog(parent)
def factory(parent):
    box = _make(parent)
    box.exec()
def grandchild(parent):
    box = Grand(parent)
    box.exec()
def opened(parent):
    box = MessageDialog(parent)
    box.open()
def later(parent):
    box = MessageDialog(parent)
    QTimer.singleShot(0, box.exec)
def _run(box):
    box.exec()
def helper(parent):
    box = MessageDialog(parent)
    _run(box)
"""

#: Die Formen, die freigeben — keine davon darf er melden.
FREED = """
class Plain(QDialog):
    def ask(self):
        self.box = MessageDialog(self)
        self.box.finished.connect(self._done)
        self.box.open()
    def _done(self):
        box, self.box = self.box, None
        box.deleteLater()
def freed(parent):
    box = MessageDialog(parent)
    try:
        box.exec()
    finally:
        box.deleteLater()
def closing(parent):
    box = Plain(parent)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.show()
def connected(parent):
    box = Plain(parent)
    box.finished.connect(box.deleteLater)
    box.open()
def closure(parent):
    box = Plain(parent)
    def done(accepted):
        box.deleteLater()
    box.finished.connect(done)
    box.open()
def _run_freed(box):
    try:
        return box.exec()
    finally:
        box.deleteLater()
def handed(parent):
    _run_freed(Plain(parent))
"""


def test_the_guard_sees_every_form_left_standing(tmp_path: Path) -> None:
    """Gegenprobe: Jede Form, die stehen bleibt, fällt auf; jede, die freigibt, nicht."""
    (tmp_path / "standing.py").write_text(LEFT_STANDING, encoding="utf-8")
    (tmp_path / "freed.py").write_text(FREED, encoding="utf-8")
    found = scan(tmp_path)
    named = {entry.split(":")[1] for entry in found.missing}
    assert named == {
        "bare",
        "kept",
        "annotated",
        "attribute",
        "factory",
        "grandchild",
        "opened",
        "later",
        "helper",
        "_run",
    }, found.missing
    assert all(entry.startswith("standing.py:") for entry in found.missing), found.missing
    assert found.checked == 15, found.checked


def test_the_guard_counts_what_it_checked(tmp_path: Path) -> None:
    """Über einem Ordner ohne Dialog prüft er nichts — und sagt es über die Zahl."""
    (tmp_path / "empty.py").write_text("def nothing():\n    return 1\n", encoding="utf-8")
    assert scan(tmp_path).checked == 0


if __name__ == "__main__":  # pragma: no cover - Handlauf
    for entry in scan(UI).missing:
        print(entry)
    sys.exit(0)
