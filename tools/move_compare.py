"""Der Vergleich zweier Syntaxbäume für den Beweis des Verschiebewerkzeugs.

Der Beweis (``tools/move_proof.py``) vergleicht den alten und den neuen Baum **ohne** die
Umschreibtabelle des Planers: Zwei Fassungen einer Datei oder einer Definition müssen Knoten für
Knoten gleich sein; wo sie abweichen, muss die Abweichung eine erklärte sein — ein Bezug, der vorher
und nachher dasselbe meint (nach der erklärten Abbildung alter auf neue Namen), eine Patch-Stelle,
deren Ziele einander entsprechen, ein erklärter Eintrag einer Namensliste. Jede andere Abweichung
ist rot. So bestätigt kein Weg sich selbst: Schreibt der Schreiber Falsches, steht es im neuen
Baum, und der Vergleich findet es, ganz gleich, was die Tabelle sagte.

Was ein Bezug meint, kommt aus zwei Quellen und nie aus einem eigenen Auflöser:

* **Leserdateien** (unverschobener Code): der Auflöser aus Paket R (``Index.resolve``) über
  beide Bäume.
* **Verschobene Definitionen**: die Bindung auf Modulebene, die ein Name liest — ob er dort
  global ist, sagt ``symtable`` (:class:`Scopes`), welche Anweisung ihn bindet, die Tabelle der
  Modulebene (:class:`TopLevel`). Ein Wert wie ``0`` für ``COUNT`` sagt nichts über die Herkunft;
  die Bindung schon.
"""

from __future__ import annotations

import ast
import symtable
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field

from tools.code_index import Index, PatchSite, Val
from tools.move_source import (
    BUILTINS,
    IMPORTS,
    Source,
    SourceError,
    Span,
    absolute_module,
    bound_name,
    docstring_ids,
    dotted,
    identifiers,
    is_type_checking,
    module_of,
    spans,
)
from tools.move_trees import Mapping, Trees

#: Eine Identität: was ein Bezug meint. ``("def", modul, name)`` eine Bindung auf Modulebene,
#: ``("imp", modul, name|"", typprüfung)`` ein Import, ``("builtin", name)``, ``("identity",
#: name, modul)`` die Identität des Moduls selbst (``__name__``), ``("unbound", name)``.
Identity = tuple[object, ...]

MODULE_IDENTITY = frozenset({"__name__", "__file__", "__spec__", "__loader__", "__package__"})


# ---------------------------------------------------------------------- Bindungen der Modulebene


@dataclass(frozen=True, order=True)
class ImportBinding:
    """Ein Eintrag einer Importanweisung: ``form`` ist ``import`` oder ``from``; ``module`` der
    absolute Punktname, ``name`` der importierte Name (bei ``import`` leer), ``bound`` der
    gebundene Name, ``checking`` ob unter ``TYPE_CHECKING``."""

    form: str
    module: str
    name: str
    bound: str
    checking: bool = False

    @property
    def identity(self) -> Identity:
        return ("imp", self.module, self.name, self.checking)

    def text(self) -> str:
        if self.form == "import":
            return f"import {self.module}" + (
                f" as {self.bound}" if self.bound != self.module.partition(".")[0] else ""
            )
        alias = f" as {self.bound}" if self.bound != self.name else ""
        return f"from {self.module} import {self.name}{alias}"


def import_bindings(
    path: str, stmt: ast.Import | ast.ImportFrom, checking: bool
) -> list[ImportBinding]:
    if isinstance(stmt, ast.Import):
        return [ImportBinding("import", a.name, "", bound_name(a), checking) for a in stmt.names]
    module = absolute_module(path, stmt)
    return [ImportBinding("from", module, a.name, bound_name(a), checking) for a in stmt.names]


class TopLevel:
    """Die Bindungen der Modulebene einer Datei: Definitionen (je Anweisung) und Importe, auch
    unter ``TYPE_CHECKING``."""

    def __init__(self, source: Source) -> None:
        self.source = source
        self.module = module_of(source.path)
        self.units: dict[str, list[ast.stmt]] = {}
        self.imports: dict[str, list[ImportBinding]] = {}
        self.import_statements: list[tuple[ast.Import | ast.ImportFrom, bool]] = []
        for stmt in source.tree.body:
            self._add(stmt, checking=False)

    def _add(self, stmt: ast.stmt, *, checking: bool) -> None:
        if isinstance(stmt, IMPORTS):
            self.import_statements.append((stmt, checking))
            for binding in import_bindings(self.source.path, stmt, checking):
                self.imports.setdefault(binding.bound, []).append(binding)
            return
        if (
            isinstance(stmt, ast.If)
            and is_type_checking(stmt.test)
            and not stmt.orelse
            and all(isinstance(inner, IMPORTS) for inner in stmt.body)
        ):
            for inner in stmt.body:
                self._add(inner, checking=True)
            return
        for name in top_names(stmt):
            self.units.setdefault(name, []).append(stmt)

    def identity(self, name: str) -> Identity:
        """Was der Name ``name`` auf Modulebene meint."""
        if name in MODULE_IDENTITY:
            return ("identity", name, self.module)
        if name in self.units:
            return ("def", self.module, name)
        found = self.imports.get(name)
        if found:
            return ("imp", *sorted({b.identity for b in found}))
        if name in BUILTINS:
            return ("builtin", name)
        return ("unbound", name)

    def binding_module(self, name: str, index: Index) -> str | None:
        """Das eigene Modul, das ``name`` als Import bindet (``import a.b`` bindet ``a``,
        ``import a.b as m`` und ``from a import b`` binden ``a.b``), sonst ``None``."""
        modules: set[str] = set()
        for binding in self.imports.get(name, []):
            if binding.form == "import":
                root = binding.module.partition(".")[0]
                modules.add(root if binding.bound == root else binding.module)
            elif index.module_exists(f"{binding.module}.{binding.name}"):
                modules.add(f"{binding.module}.{binding.name}")
            else:
                return None
        if len(modules) != 1:
            return None
        module = modules.pop()
        return module if index.module_exists(module) else None


def top_names(stmt: ast.stmt) -> list[str]:
    """Die Namen, die eine Anweisung auf Modulebene bindet (ohne ``global`` in Funktionen)."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [stmt.name]
    if isinstance(stmt, ast.TypeAlias) and isinstance(stmt.name, ast.Name):
        return [stmt.name.id]
    found: list[str] = []
    for node in _walk_module_level(stmt):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            found.append(node.id)
        elif isinstance(node, IMPORTS):
            found.extend(bound_name(a) for a in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name is not None:
            found.extend([node.name])
    return list(dict.fromkeys(found))


def _walk_module_level(stmt: ast.AST) -> Iterator[ast.AST]:
    """Die Knoten einer Anweisung, die auf Modulebene binden können — ohne Rümpfe von
    Funktionen, Klassen, Lambdas und Abstraktionen."""
    stack = [stmt]
    while stack:
        node = stack.pop()
        yield node
        if node is not stmt and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue
        stack.extend(ast.iter_child_nodes(node))


# ------------------------------------------------------------- global oder lokal (symtable)


class Scopes:
    """Ob ein Name in einer Anweisung der Modulebene den Modulnamensraum liest.

    Die Antwort gibt ``symtable`` für den Text der Anweisung allein; die Tabellen werden den
    Knoten über Art, Name und Zeile zugeordnet. Eine Abstraktion (``[q for q in …]``) bindet ihre
    Laufvariablen selbst; Annotationen, Vorgaben und Dekoratoren laufen im umschließenden
    Bereich."""

    def __init__(self, source: Source, stmt: ast.stmt, span: Span) -> None:
        self.source = source
        self.stmt = stmt
        self.offset = span.start - 1
        text = source.lines_text(span.start, stmt.end_lineno or span.start)
        self.top = symtable.symtable(text, source.path, "exec")
        self.tables: dict[tuple[str, str, int], list[symtable.SymbolTable]] = {}
        self._index(self.top)
        self._used: dict[tuple[str, str, int], int] = {}
        self.table_of: dict[int, symtable.SymbolTable] = {}
        self._assign(stmt)

    def _index(self, table: symtable.SymbolTable) -> None:
        for child in table.get_children():
            key = (child.get_type().name, child.get_name(), child.get_lineno())
            self.tables.setdefault(key, []).append(child)
            self._index(child)

    def _assign(self, root: ast.AST) -> None:
        for node in ast.walk(root):
            key: tuple[str, str, int] | None = None
            line = getattr(node, "lineno", 0) - self.offset
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = ("FUNCTION", node.name, line)
            elif isinstance(node, ast.Lambda):
                key = ("FUNCTION", "lambda", line)
            elif isinstance(node, ast.ClassDef):
                key = ("CLASS", node.name, line)
            elif isinstance(node, ast.GeneratorExp):
                key = ("FUNCTION", "genexpr", line)
            if key is None:
                continue
            candidates = self.tables.get(key, [])
            used = self._used.get(key, 0)
            if used < len(candidates):
                self.table_of[id(node)] = candidates[used]
                self._used[key] = used + 1

    def is_global(self, node: ast.expr, name: str | None = None) -> bool:
        """Ob ``node`` die Bindung der Modulebene liest (oder schreibt); mit ``name``: ob an der
        Stelle von ``node`` der Name ``name`` die Bindung der Modulebene meinte."""
        if name is None:
            assert isinstance(node, ast.Name)
            name = node.id
        current: ast.AST = node
        for outer in self.source.ancestors(node):
            if isinstance(outer, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                if (
                    any(
                        isinstance(t, ast.Name) and t.id == name
                        for g in outer.generators
                        for t in ast.walk(g.target)
                    )
                    and current is not outer.generators[0].iter
                ):
                    return False
            elif isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if not _in_body(outer, current):
                    current = outer
                    if outer is self.stmt:
                        return True
                    continue
                table = self.table_of.get(id(outer))
                if table is not None and name in table.get_identifiers():
                    symbol = table.lookup(name)
                    if symbol.is_global() or symbol.is_declared_global():
                        return True
                    if symbol.is_local() or symbol.is_free() or symbol.is_parameter():
                        return False
            elif isinstance(outer, ast.ClassDef) and any(current is s for s in outer.body):
                table = self.table_of.get(id(outer))
                if table is not None and name in table.get_identifiers():
                    symbol = table.lookup(name)
                    if symbol.is_local() or symbol.is_assigned():
                        return False
            if outer is self.stmt:
                return True
            current = outer
        return True


class FileScopes:
    """:class:`Scopes` für jede Anweisung der Modulebene einer Datei — ob ein Name an einer
    beliebigen Stelle die Bindung der Modulebene meint."""

    def __init__(self, source: Source) -> None:
        self.source = source
        body = source.tree.body
        self._items = list(zip(body, spans(source, body), strict=True))
        self._scopes: dict[int, Scopes] = {}

    def of(self, node: ast.AST) -> Scopes:
        line = getattr(node, "lineno", 0)
        for stmt, span in self._items:
            if span.start <= line <= (stmt.end_lineno or span.start):
                found = self._scopes.get(id(stmt))
                if found is None:
                    found = Scopes(self.source, stmt, span)
                    self._scopes[id(stmt)] = found
                return found
        raise SourceError(
            f"{self.source.path}:{line}: keine Anweisung der Modulebene (Werkzeugfehler)"
        )

    def is_global(self, node: ast.expr, name: str | None = None) -> bool:
        return self.of(node).is_global(node, name)

    def global_names(self, name: str) -> list[ast.Name]:
        """Jedes Vorkommen von ``name``, das die Bindung der Modulebene meint (lesend,
        schreibend, löschend), in Reihenfolge."""
        found = [
            node
            for node in ast.walk(self.source.tree)
            if isinstance(node, ast.Name) and node.id == name and self.is_global(node)
        ]
        return sorted(found, key=lambda n: (n.lineno, n.col_offset))


def _in_body(function: ast.AST, child: ast.AST) -> bool:
    """Ob ``child`` (ein direktes Kind von ``function``) im Rumpf liegt, nicht in Signatur,
    Dekoratoren oder Annotationen."""
    if isinstance(function, ast.Lambda):
        return child is function.body
    assert isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
    return any(child is stmt for stmt in function.body)


# ---------------------------------------------------------------------------- Vergleich


@dataclass
class Difference:
    """Ein Paar abweichender Knoten und das Urteil darüber."""

    old: ast.AST
    new: ast.AST
    note: str


class Comparison:
    """Der Strukturvergleich zweier Bäume. Unterklassen entscheiden in :meth:`special`, ob ein
    abweichendes Knotenpaar erklärt ist; alles andere muss gleich sein."""

    def __init__(self, label: str, old: Source, new: Source) -> None:
        self.label = label
        self.old = old
        self.new = new
        self.errors: list[str] = []
        self.accepted: list[str] = []
        self.compared = 0

    # ---- Meldungen

    def where(self, node: ast.AST, source: Source) -> str:
        return f"{source.path}:{getattr(node, 'lineno', '?')}"

    def fail(self, old: ast.AST, new: ast.AST, why: str) -> None:
        old_text = _short(self.old, old)
        new_text = _short(self.new, new)
        self.errors.append(
            f"{self.where(new, self.new)} ({self.label}): {why} — vorher {old_text!r}, nachher "
            f"{new_text!r}"
        )

    def accept(self, text: str) -> None:
        self.accepted.append(text)

    # ---- Haken

    def special(self, old: ast.AST, new: ast.AST) -> bool:
        """``True``, wenn das Paar erklärt (und geprüft) ist; dann wird nicht weiter verglichen."""
        return False

    def scalar(self, old: ast.AST, new: ast.AST, name: str, before: object, after: object) -> bool:
        """``True``, wenn ein abweichendes Feld erklärt ist (etwa eine erklärte Umbenennung)."""
        return False

    def statements(
        self, owner: ast.AST, name: str, old: list[ast.stmt], new: list[ast.stmt]
    ) -> None:
        """Vergleicht zwei Anweisungslisten; Importblöcke gehen an :meth:`imports`."""
        old_items, new_items = self.blocks(owner, old, new)
        if len(old_items) != len(new_items):
            self.errors.append(
                f"{self.where(owner, self.new)} ({self.label}): {len(new_items)} Anweisungen "
                f"oder Importblöcke statt {len(old_items)} in {type(owner).__name__}.{name}"
            )
            return
        for before, after in zip(old_items, new_items, strict=True):
            if isinstance(before, list) and isinstance(after, list):
                self.imports(owner, before, after)
            elif isinstance(before, list) or isinstance(after, list):
                node = after[0] if isinstance(after, list) else after
                self.errors.append(
                    f"{self.where(node, self.new)} ({self.label}): Importblock und Anweisung "
                    "stehen nicht an derselben Stelle"
                )
            else:
                self.compare(before, after)

    def blocks(
        self, owner: ast.AST, old: list[ast.stmt], new: list[ast.stmt]
    ) -> tuple[list[ast.stmt | list[ast.stmt]], list[ast.stmt | list[ast.stmt]]]:
        """Die Anweisungen beider Seiten, zusammenhängende Importe als ein Block; Unterklassen
        nehmen erklärte Zu- und Abgänge heraus."""
        return list(_blocks(old)), list(_blocks(new))

    def imports(self, owner: ast.AST, old: list[ast.stmt], new: list[ast.stmt]) -> None:
        """Vergleicht zwei Importblöcke; Vorgabe: dieselben Bindungen."""
        before = Counter(_binding_keys(self.old.path, old))
        after = Counter(_binding_keys(self.new.path, new))
        if before != after:
            self.errors.append(
                f"{self.where(new[0], self.new)} ({self.label}): Importe geändert — vorher "
                f"{sorted(before)}, nachher {sorted(after)}"
            )

    def expressions(
        self, owner: ast.AST, name: str, old: Sequence[ast.AST], new: Sequence[ast.AST]
    ) -> None:
        if len(old) != len(new):
            self.fail(owner, owner, f"{name}: {len(new)} statt {len(old)} Einträge")
            return
        for before, after in zip(old, new, strict=True):
            self.compare(before, after)

    # ---- Vergleich

    def compare(self, old: ast.AST, new: ast.AST) -> None:
        self.compared += 1
        if self.special(old, new):
            return
        if type(old) is not type(new):
            self.fail(old, new, "andere Form")
            return
        for name, before in ast.iter_fields(old):
            if name == "type_comment":
                continue
            after = getattr(new, name, None)
            if isinstance(before, list):
                if not isinstance(after, list):
                    self.fail(old, new, f"Feld {name}")
                elif not all(isinstance(item, ast.AST) for item in [*before, *after]):
                    if before != after and not self.scalar(old, new, name, before, after):
                        self.fail(old, new, f"{name} {before!r} → {after!r}")
                elif (before and isinstance(before[0], ast.stmt)) or (
                    after and isinstance(after[0], ast.stmt)
                ):
                    self.statements(old, name, before, after)
                else:
                    self.expressions(old, name, before, after)
            elif isinstance(before, ast.AST):
                if not isinstance(after, ast.AST):
                    self.fail(old, new, f"Feld {name}")
                else:
                    self.compare(before, after)
            elif before != after and not self.scalar(old, new, name, before, after):
                self.fail(old, new, f"{name} {before!r} → {after!r}")


def _blocks(body: list[ast.stmt]) -> Iterator[ast.stmt | list[ast.stmt]]:
    """Die Anweisungen eines Rumpfs, zusammenhängende Importe als ein Block."""
    run: list[ast.stmt] = []
    for stmt in body:
        if isinstance(stmt, IMPORTS):
            run.append(stmt)
            continue
        if run:
            yield run
            run = []
        yield stmt
    if run:
        yield run


def _binding_keys(path: str, block: list[ast.stmt]) -> list[ImportBinding]:
    found: list[ImportBinding] = []
    for stmt in block:
        assert isinstance(stmt, (ast.Import, ast.ImportFrom))
        found.extend(import_bindings(path, stmt, checking=False))
    return found


def block_bindings(path: str, block: list[ast.stmt]) -> list[ImportBinding]:
    return _binding_keys(path, block)


def _short(source: Source, node: ast.AST) -> str:
    try:
        text = source.node_text(node)
    except Exception:
        text = ast.unparse(node) if isinstance(node, ast.AST) else str(node)
    text = " ".join(text.split())
    return text if len(text) <= 120 else text[:117] + "…"


# ------------------------------------------------------------------- Bedeutung über R


def module_of_expression(index: Index, path: str, node: ast.expr) -> str | None:
    """Das Modul, das ``node`` laut Auflöser ist — genau eines, keine Kopie über den Pfad."""
    values = index.resolve(path, node)
    modules = {v.ref for v in values if v.kind == "module" and v.data != "loaded"}
    if len(modules) == 1 and len(values) == 1:
        return modules.pop()
    return None


def comments(source: Source, first: int, last: int) -> Counter[str]:
    return Counter(c.text.strip() for c in source.comments_between(first, last))


def all_comments(source: Source) -> Counter[str]:
    return Counter(c.text.strip() for c in source.comments())


def string_constants(source: Source) -> Iterator[ast.Constant]:
    """Jede Zeichenkette einer Datei außer Docstrings."""
    skip = docstring_ids(source.tree)
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            yield node


def qualname_of(source: Source, node: ast.AST) -> str:
    """Der Bereich einer Stelle als Qualname der umschließenden Definitionen (``<module>`` auf
    Modulebene)."""
    names: list[str] = []
    for outer in source.ancestors(node):
        if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(outer.name)
    return ".".join(reversed(names)) or "<module>"


@dataclass
class MappedValues:
    """Abbildung alter Werte des Auflösers auf neue (je Modus)."""

    ref: Callable[[str, str], tuple[str, str]]
    seen: set[str] = field(default_factory=set)

    def value(self, value: Val) -> Val:
        if value.kind in ("def", "class") and ":" in value.ref:
            module, _, qualname = value.ref.partition(":")
            head, dot, rest = qualname.partition(".")
            new_module, new_head = self.ref(module, head)
            return Val(value.kind, f"{new_module}:{new_head}{dot}{rest}", value.data)
        return value

    def values(self, values: frozenset[Val]) -> frozenset[Val]:
        return frozenset(self.value(v) for v in values)


# ------------------------------------------------------------------- Hilfen


def _text(source: Source, node: ast.AST) -> str:
    try:
        return " ".join(source.node_text(node).split())
    except SourceError:
        return ast.unparse(node)


def _is_annotation(parent: ast.AST | None, node: ast.AST) -> bool:
    if isinstance(parent, ast.arg):
        return parent.annotation is node
    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return parent.returns is node
    if isinstance(parent, ast.AnnAssign):
        return parent.annotation is node
    return False


def _string_names(text: str) -> set[str]:
    try:
        expression = ast.parse(text.strip(), mode="eval")
    except SyntaxError:
        return set()
    return {node.id for node in ast.walk(expression) if isinstance(node, ast.Name)}


# ------------------------------------------------------------------- Leserdateien


#: Aufrufe, deren zweites Argument ein Attributname des ersten ist.
ATTRIBUTE_CALLS = frozenset(
    {"builtins.getattr", "builtins.hasattr", "builtins.setattr", "builtins.delattr"}
)


class ReaderComparison(Comparison):
    """Eine Datei, die nicht verschoben, nur umgeschrieben wird: Abweichungen sind Bezüge, die
    laut R vorher (abgebildet) und nachher dasselbe meinen, Patch-Stellen mit abgebildeten Zielen
    und erklärte Zeichenketten. Ein Name, dessen Import sich geändert hat, wird an **jeder**
    Stelle über R verglichen."""

    def __init__(self, trees: Trees, path: str, mapping: Mapping, values: MappedValues) -> None:
        super().__init__("Leser", trees.old(path), trees.new(path))
        self.trees = trees
        self.path = path
        self.mapping = mapping
        self.values = values
        self.changed: set[str] = set()
        self.added: set[str] = set()
        self.import_changes: list[str] = []
        self.old_sites = {
            (s.line, s.col): s for (p, _l, _c), s in trees.sites("old").items() if p == path
        }
        self.new_sites = {
            (s.line, s.col): s for (p, _l, _c), s in trees.sites("new").items() if p == path
        }
        self.old_identifiers = identifiers(self.old.tree)

    # ---- Ablauf

    def run(self) -> None:
        self._collect_import_changes(self.old.tree, self.new.tree)
        self.compare(self.old.tree, self.new.tree)
        for name in sorted(self.added):
            uses = sum(
                1
                for node in ast.walk(self.new.tree)
                if isinstance(node, ast.Name) and node.id == name
            )
            if not uses:
                self.errors.append(f"{self.path}: neuer Import {name!r} wird nicht gelesen")
        if all_comments(self.old) != all_comments(self.new):
            before = all_comments(self.old)
            after = all_comments(self.new)
            self.errors.append(
                f"{self.path}: Kommentare geändert — verloren "
                f"{sorted((before - after).elements())}, neu {sorted((after - before).elements())}"
            )

    def _collect_import_changes(self, old: ast.AST, new: ast.AST) -> None:
        """Erster Durchgang: welche Namen ihre Importbindung ändern — je Name alle Bindungen der
        Datei vorher gegen nachher. Jede Stelle dieser Namen vergleicht der zweite Durchgang
        über R."""
        before: dict[str, Counter[ImportBinding]] = {}
        after: dict[str, Counter[ImportBinding]] = {}
        for tree, found in ((old, before), (new, after)):
            for block in _import_blocks(tree):
                for binding in block_bindings(self.path, block):
                    found.setdefault(binding.bound, Counter())[binding] += 1
        for name in set(before) | set(after):
            if before.get(name) != after.get(name):
                self.changed.add(name)

    # ---- Haken

    def blocks(
        self, owner: ast.AST, old: list[ast.stmt], new: list[ast.stmt]
    ) -> tuple[list[ast.stmt | list[ast.stmt]], list[ast.stmt | list[ast.stmt]]]:
        """Erklärte Zu- und Abgänge einer Leserdatei: Eine Zuweisung ``x =
        importlib.import_module("M")``, die nach dem Schnitt niemand mehr liest, fällt weg (``M``
        laut :meth:`removable_module`); ein Import des neuen Moduls kommt in einer Funktion als
        eigener Block hinter die Zuweisung. Jede Stelle von ``x`` wird danach über R
        verglichen — ein Leser, der bliebe, meint nachher nichts mehr."""
        new_dumps = {ast.dump(s) for s in new}
        kept_old: list[ast.stmt] = []
        for stmt in old:
            target = _removable_target(stmt)
            if target is not None and ast.dump(stmt) not in new_dumps:
                assert isinstance(stmt, ast.Assign)
                values = self.trees.old_index.resolve(self.path, stmt.value)
                modules = {v.ref for v in values if v.kind == "module" and v.data != "loaded"}
                if len(values) == 1 and len(modules) == 1 and self.removable_module(modules.pop()):
                    self.changed.add(target)
                    self.import_changes.append(f"entfällt {_text(self.old, stmt)}")
                    continue
            kept_old.append(stmt)
        old_items = list(_blocks(kept_old))
        new_items = list(_blocks(new))
        if len(new_items) > len(old_items):
            old_dumps = {ast.dump(s) for s in old}
            kept_new: list[ast.stmt | list[ast.stmt]] = []
            for item in new_items:
                if isinstance(item, list) and all(ast.dump(s) not in old_dumps for s in item):
                    bindings = block_bindings(self.path, item)
                    if bindings and all(self.allowed_module_alias(b) for b in bindings):
                        self.imports(owner, [], item)
                        continue
                kept_new.append(item)
            new_items = kept_new
        return old_items, new_items

    def removable_module(self, module: str) -> bool:
        """Ob eine Zuweisung, die das Modul ``module`` bindet, wegfallen darf."""
        return False

    def imports(self, owner: ast.AST, old: list[ast.stmt], new: list[ast.stmt]) -> None:
        removed, added = _difference(self.path, old, new)
        if not removed and not added:
            return
        removed_names = {b.bound for b in removed}
        for binding in added:
            if binding.bound in removed_names:
                previous = [b for b in removed if b.bound == binding.bound]
                if not self.allowed_rebinding(previous, binding):
                    self.errors.append(
                        f"{self.path}:{new[0].lineno}: Import {binding.text()} ersetzt "
                        f"{', '.join(b.text() for b in previous)} ohne Erklärung"
                    )
                    continue
                self.import_changes.append(
                    f"{', '.join(b.text() for b in previous)} → {binding.text()}"
                )
                continue
            if not self.allowed_module_alias(binding):
                self.errors.append(
                    f"{self.path}:{new[0].lineno}: neuer Import {binding.text()} gehört nicht zum "
                    "Schnitt"
                )
                continue
            if _same_root(binding, block_bindings(self.path, old)):
                # ``import a.b.ziel`` neben ``import a.b``: dieselbe Wurzel ``a``, die Kette
                # prüft jede Stelle (``_covered``).
                self.import_changes.append(f"neu {binding.text()}")
                continue
            if binding.bound in self.old_identifiers:
                self.errors.append(
                    f"{self.path}:{new[0].lineno}: neuer Import bindet {binding.bound!r}, den die "
                    "Datei schon verwendet — einen freien Namen wählen (aliases)"
                )
                continue
            self.added.add(binding.bound)
            self.import_changes.append(f"neu {binding.text()}")
        added_names = {b.bound for b in added}
        for binding in removed:
            if binding.bound in added_names:
                continue
            if not self.allowed_removal(binding):
                self.errors.append(
                    f"{self.path}:{old[0].lineno}: Import {binding.text()} entfernt ohne Bezug "
                    "zum Schnitt"
                )
                continue
            self.import_changes.append(f"entfällt {binding.text()}")

    def allowed_rebinding(self, previous: list[ImportBinding], binding: ImportBinding) -> bool:
        return False

    def allowed_module_alias(self, binding: ImportBinding) -> bool:
        return False

    def allowed_removal(self, binding: ImportBinding) -> bool:
        return False

    def special(self, old: ast.AST, new: ast.AST) -> bool:
        if isinstance(old, ast.Call) and isinstance(new, ast.Call):
            site_old = self.old_sites.get((old.lineno, old.col_offset))
            site_new = self.new_sites.get((new.lineno, new.col_offset))
            if site_old is not None or site_new is not None:
                return self._patch_site(old, new, site_old, site_new)
            if self._attribute_call(old, new):
                return True
        if isinstance(old, (ast.Name, ast.Attribute)) and isinstance(
            new, (ast.Name, ast.Attribute)
        ):
            return self._reference(old, new)
        if (
            isinstance(old, ast.Constant)
            and isinstance(new, ast.Constant)
            and old.value != new.value
        ):
            return self.constant(old, new)
        return False

    def constant(self, old: ast.Constant, new: ast.Constant) -> bool:
        return False

    def reference(
        self, old: ast.expr, new: ast.expr, before: tuple[str, str], after: tuple[str, str]
    ) -> bool:
        """Ein abweichender Bezug ``before`` → ``after`` (Modul, Name); Vorgabe: abgebildet."""
        return self.mapping.ref(*before) == after

    def _reference(self, old: ast.expr, new: ast.expr) -> bool:
        same = ast.dump(old) == ast.dump(new)
        if same:
            if isinstance(old, ast.Name) and isinstance(new, ast.Name) and old.id in self.changed:
                self._meaning(old, new)
                return True
            return False
        before = self._attribute_identity(old, "old")
        after = self._attribute_identity(new, "new")
        if before is None or after is None:
            return False
        if self.reference(old, new, before, after):
            self._covered(new, after)
            self.accept(f"{_text(self.old, old)} → {_text(self.new, new)}")
            return True
        self.fail(
            old,
            new,
            f"Bezug {before[0]}.{before[1]} wird {after[0]}.{after[1]}, erwartet "
            f"{'.'.join(self.mapping.ref(*before))}",
        )
        return True

    def _covered(self, new: ast.expr, after: tuple[str, str]) -> None:
        """Eine Kette ``a.b.c.name`` über einen einfachen Import braucht ``import a.b.c``."""
        if isinstance(new, ast.Attribute) and isinstance(new.value, ast.Attribute):
            chain = dotted(new.value)
            if chain == after[0] and not _imports_module(self.new.tree, chain):
                self.fail(new, new, f"liest {chain} über eine Kette ohne ``import {chain}``")

    def _attribute_identity(self, node: ast.expr, side: str) -> tuple[str, str] | None:
        if not isinstance(node, ast.Attribute):
            return None
        index = self.trees.old_index if side == "old" else self.trees.new_index
        module = module_of_expression(index, self.path, node.value)
        if module is None:
            return None
        return module, node.attr

    def _meaning(self, old: ast.Name, new: ast.Name) -> None:
        before = self.trees.old_index.resolve(self.path, old)
        after = self.trees.new_index.resolve(self.path, new)
        if self.values.values(before) != after:
            self.fail(old, new, f"{old.id} meint vorher {sorted(before)}, nachher {sorted(after)}")

    def _attribute_call(self, old: ast.Call, new: ast.Call) -> bool:
        if len(old.args) < 2 or len(new.args) < 2:
            return False
        kinds = self.trees.old_index.resolve(self.path, old.func)
        if not kinds or not all(v.kind == "ext" and v.ref in ATTRIBUTE_CALLS for v in kinds):
            return False
        first_old, second_old = old.args[0], old.args[1]
        first_new, second_new = new.args[0], new.args[1]
        if not (
            isinstance(second_old, ast.Constant)
            and isinstance(second_new, ast.Constant)
            and isinstance(second_old.value, str)
            and isinstance(second_new.value, str)
        ):
            return False
        if ast.dump(first_old) == ast.dump(first_new) and second_old.value == second_new.value:
            return False
        module_old = module_of_expression(self.trees.old_index, self.path, first_old)
        module_new = module_of_expression(self.trees.new_index, self.path, first_new)
        if module_old is None or module_new is None:
            return False
        before = (module_old, second_old.value)
        after = (module_new, second_new.value)
        if self.reference(first_old, first_new, before, after):
            self.accept(f"{_text(self.old, old)} → {_text(self.new, new)}")
        else:
            self.fail(old, new, f"Bezug {before} wird {after}")
        self.compare(old.func, new.func)
        self.expressions(old, "args", old.args[2:], new.args[2:])
        self.expressions(old, "keywords", list(old.keywords), list(new.keywords))
        return True

    def _patch_site(
        self, old: ast.Call, new: ast.Call, site_old: PatchSite | None, site_new: PatchSite | None
    ) -> bool:
        if site_old is None or site_new is None:
            self.fail(old, new, "Patch-Stelle nur auf einer Seite")
            return True
        if ast.dump(old) == ast.dump(new) and not self.changed:
            return False
        if site_old.form != site_new.form:
            self.fail(old, new, f"Patch-Form {site_old.form} → {site_new.form}")
            return True
        expected = [self.mapping.target(site_old, n) for n in range(len(site_old.targets))]
        actual = [(t.status, t.module, t.name) for t in site_new.targets]
        if expected != actual:
            self.fail(old, new, f"Patch-Ziele {actual}, erwartet {expected}")
            return True
        skip = _designating(site_old.form, old)
        if skip != _designating(site_new.form, new):
            self.fail(old, new, "Patch-Stelle mit anderer Zielform")
            return True
        self.compare(old.func, new.func)
        self.expressions(old, "args", old.args[skip:], new.args[skip:])
        self.expressions(old, "keywords", list(old.keywords), list(new.keywords))
        if ast.dump(old) != ast.dump(new):
            self.accept(f"Patch {site_old.text} → {site_new.text}")
        return True


def _removable_target(stmt: ast.stmt) -> str | None:
    """Der Name einer einfachen Zuweisung ``x = …``, sonst ``None``."""
    if (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
    ):
        return stmt.targets[0].id
    return None


def _same_root(binding: ImportBinding, block: list[ImportBinding]) -> bool:
    """Ob ``binding`` ein ``import a.b.c`` ist, dessen Wurzel ``a`` derselbe Block schon über
    ein einfaches ``import a…`` bindet."""
    root = binding.module.partition(".")[0]
    if binding.form != "import" or binding.bound != root:
        return False
    return any(b.form == "import" and b.bound == root and b != binding for b in block)


def _designating(form: str, call: ast.Call) -> int:
    """Wie viele Argumente einer Patch-Stelle ihr Ziel bestimmen."""
    if form in ("setattr", "delattr"):
        first = call.args[0] if call.args else None
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return 1
        return 2
    if form == "patch":
        return 1
    return 2


def _imports_module(tree: ast.AST, module: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            a.name == module and a.asname is None for a in node.names
        ):
            return True
    return False


def _import_blocks(tree: ast.AST) -> Iterator[list[ast.stmt]]:
    for node in ast.walk(tree):
        for name in ("body", "orelse", "finalbody"):
            body = getattr(node, name, None)
            if isinstance(body, list) and body and isinstance(body[0], ast.stmt):
                run: list[ast.stmt] = []
                for stmt in [*body, None]:
                    if isinstance(stmt, IMPORTS):
                        run.append(stmt)
                        continue
                    if run:
                        yield run
                        run = []


def _difference(
    path: str, old: list[ast.stmt], new: list[ast.stmt]
) -> tuple[list[ImportBinding], list[ImportBinding]]:
    before = Counter(block_bindings(path, old))
    after = Counter(block_bindings(path, new))
    return list((before - after).elements()), list((after - before).elements())
