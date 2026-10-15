"""Umschreiben in Leserdateien, gemeinsam für alle Modi des Verschiebewerkzeugs.

:class:`Context` hält den Baum vor dem Schnitt: den Index aus Paket R, die gelesenen Quellen mit
ihrem Hash (der Schnitt ist an genau diese Bytes gebunden) und die gesammelten Funde. Ein Fund hält
den Schnitt an, bevor etwas geschrieben wird; gemeldet werden alle auf einmal, jeder mit Stelle und
Ausweg — es gibt kein stilles Überspringen.

:class:`FileRewrite` sammelt die Tabelle einer Datei. Was ein Ausdruck **bedeutet**, fragt es
beim Auflöser (``Index.resolve``); selbst bestimmt es nur, **wo** ein Name per Import gebunden wird
(``move_source.import_binders``), damit ein neuer Modulimport **neben** den alten kommt — in
denselben Bereich, also mit derselben Ladezeit: Ein später Import bleibt spät, einer unter
``TYPE_CHECKING`` bleibt dort. Ein Import, den danach niemand mehr liest, fällt weg.
"""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from tools.code_index import Index, PatchSite
from tools.move_cut import Cut
from tools.move_edits import Edit, trailing_comment
from tools.move_source import (
    IMPORTS,
    Source,
    SourceError,
    absolute_module,
    bound_name,
    docstring_node,
    dotted,
    identifiers,
    import_binders,
    own_statements,
    path_of,
    scope_of,
)


class PlanError(Exception):
    """Der Schnitt ist so nicht beweisbar; ``problems`` nennt jede Stelle mit Ausweg."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


class AlreadyAppliedError(Exception):
    """Der Schnitt steht schon im Baum; es gibt nichts zu tun."""


class Context:
    """Der Baum vor dem Schnitt, wie der Planer ihn sieht."""

    def __init__(self, root: Path, cut: Cut, index: Index) -> None:
        self.root = root
        self.cut = cut
        self.index = index
        self.hashes: dict[str, str] = {}
        self.problems: list[str] = []
        self.notes: list[str] = []
        self._sources: dict[str, Source] = {}
        self._rewrites: dict[str, FileRewrite] = {}
        self._sites: dict[str, list[PatchSite]] | None = None
        self._lazy: dict[str, frozenset[str]] = {}

    def problem(self, text: str) -> None:
        if text not in self.problems:
            self.problems.append(text)

    def note(self, text: str) -> None:
        self.notes.append(text)

    def raise_problems(self) -> None:
        if self.problems:
            raise PlanError(list(self.problems))

    def source(self, path: str) -> Source:
        found = self._sources.get(path)
        if found is None:
            data = (self.root / path).read_bytes()
            self.hashes[path] = hashlib.sha256(data).hexdigest()
            try:
                found = Source(path, data)
            except SourceError as error:
                raise PlanError([str(error)]) from None
            self._sources[path] = found
        return found

    def rewrite(self, path: str) -> FileRewrite:
        found = self._rewrites.get(path)
        if found is None:
            found = FileRewrite(self, path)
            self._rewrites[path] = found
        return found

    def rewrites(self) -> dict[str, FileRewrite]:
        return dict(self._rewrites)

    def sites(self, path: str) -> list[PatchSite]:
        if self._sites is None:
            self._sites = {}
            for site in self.index.patch_sites():
                self._sites.setdefault(site.path, []).append(site)
        return self._sites.get(path, [])

    def is_module(self, path: str, node: ast.expr, module: str) -> bool:
        """Ob ``node`` laut Auflöser genau das Modul ``module`` ist (keine Kopie über den Pfad)."""
        values = self.index.resolve(path, node)
        return bool(values) and all(
            v.kind == "module" and v.ref == module and v.data != "loaded" for v in values
        )

    def shadowed(self, module: str) -> bool:
        """Ob ``module`` hinter einem gleichnamigen trägen Export seines Pakets liegt
        (``app.core.scene.evaluate``): ``from app.core.scene import evaluate`` bindet dann die
        Funktion, und auch ein Pfad als Text endet bei ihr. Gelesen wird nur die Tabelle
        ``_EXPORTS`` des Pakets (``app.core.lazy``), keine Auflösung."""
        parent, _, last = module.rpartition(".")
        return last in self.lazy_names(parent)

    def lazy_names(self, package: str) -> frozenset[str]:
        """Die Schlüssel der Tabelle ``_EXPORTS`` im ``__init__`` von ``package``."""
        found = self._lazy.get(package)
        if found is None:
            found = frozenset()
            path = path_of(package, package=True) if package else ""
            if path and (self.root / path).is_file():
                found = frozenset(lazy_table(self.source(path)))
            self._lazy[package] = found
        return found


def lazy_table(source: Source) -> dict[str, tuple[ast.Constant, ast.Constant]]:
    """Die Einträge ``"N": ("untermodul", "name")`` der Tabelle ``_EXPORTS`` auf Modulebene
    eines Paket-``__init__`` (``app.core.lazy``), je Schlüssel die beiden Textknoten."""
    found: dict[str, tuple[ast.Constant, ast.Constant]] = {}
    for stmt in source.tree.body:
        target: ast.expr | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
        elif isinstance(stmt, ast.AnnAssign):
            target = stmt.target
        value = stmt.value if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else None
        if not (isinstance(target, ast.Name) and target.id == "_EXPORTS"):
            continue
        if not isinstance(value, ast.Dict):
            continue
        for key, item in zip(value.keys, value.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(item, ast.Tuple)
                and len(item.elts) == 2
                and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in item.elts)
            ):
                first, second = item.elts
                assert isinstance(first, ast.Constant) and isinstance(second, ast.Constant)
                found[key.value] = (first, second)
    return found


def _module_level(source: Source, node: ast.AST) -> bool:
    """Ob ``node`` außerhalb jeder Funktion steht (Modulebene, auch in ``if``/``try``)."""
    return not any(
        isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))
        for outer in source.ancestors(node)
    )


def import_text(module: str, alias: str) -> str:
    """Der Import, der ``alias`` an das Modul ``module`` bindet."""
    parent, _, last = module.rpartition(".")
    if not parent:
        return f"import {module}" + (f" as {alias}" if alias != module else "")
    return f"from {parent} import {last}" + (f" as {alias}" if alias != last else "")


def from_text(module: str, names: Iterable[tuple[str, str | None]]) -> str:
    parts = [n + (f" as {a}" if a and a != n else "") for n, a in names]
    return f"from {module} import {', '.join(parts)}"


def quoted(source: Source, node: ast.Constant, value: str) -> str:
    """``value`` als Zeichenkette in der Anführung, die ``node`` im Quelltext hat."""
    text = source.node_text(node)
    quote = "'" if text[:1] == "'" else '"'
    escaped = value.replace("\\", "\\\\").replace(quote, "\\" + quote)
    return f"{quote}{escaped}{quote}"


def find_nodes[NodeT: ast.AST](
    source: Source, kind: type[NodeT], line: int, col: int
) -> list[NodeT]:
    """Die Knoten einer Art, die an ``line``/``col`` beginnen (Lage wie ``ast``)."""
    return [
        node
        for node in ast.walk(source.tree)
        if isinstance(node, kind)
        and getattr(node, "lineno", None) == line
        and getattr(node, "col_offset", None) == col
    ]


@dataclass
class ImportPlan:
    """Was mit einer Importanweisung geschieht."""

    stmt: ast.Import | ast.ImportFrom
    drop: set[int] = field(default_factory=set)
    replace: dict[int, list[str]] = field(default_factory=dict)
    after: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)


@dataclass
class Watch:
    """Ein Import, der wegfällt, wenn ihn nach allen Ersetzungen niemand mehr liest."""

    stmt: ast.Import | ast.ImportFrom
    number: int
    module: str
    plain: bool


@dataclass
class AssignWatch:
    """Eine Zuweisung ``x = importlib.import_module("M")``, die wegfällt, wenn ``x`` nach allen
    Ersetzungen niemand mehr liest (sonst bliebe eine tote lokale Variable, ruff F841)."""

    stmt: ast.Assign
    name: str
    module: str


def assignment_binders(source: Source, name: str, use: ast.AST) -> list[ast.Assign]:
    """Die Zuweisungen ``name = …``, die ``name`` für die Stelle ``use`` binden, wenn der innerste
    bindende Bereich ihn **nur** über einfache Zuweisungen bindet (kein Import, kein Parameter).
    Ob der Wert das Modul ist, fragt der Aufrufer beim Auflöser."""
    scope: ast.AST = scope_of(source, use)
    while True:
        own = list(own_statements(scope))
        imports = [
            s for s in own if isinstance(s, IMPORTS) and any(bound_name(a) == name for a in s.names)
        ]
        found = [
            s
            for s in own
            if isinstance(s, ast.Assign)
            and len(s.targets) == 1
            and isinstance(s.targets[0], ast.Name)
            and s.targets[0].id == name
        ]
        if imports:
            return []
        if found:
            return found
        if _binds_otherwise(scope, name):
            return []
        if isinstance(scope, ast.Module):
            return []
        scope = _outer_scope(source, scope)


def _binds_otherwise(scope: ast.AST, name: str) -> bool:
    """Ob ``scope`` ``name`` als Parameter oder Definition bindet."""
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = scope.args
        every = [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]
        if any(a is not None and a.arg == name for a in every):
            return True
    return any(
        isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and s.name == name
        for s in own_statements(scope)
    )


def _outer_scope(source: Source, scope: ast.AST) -> ast.AST:
    for outer in source.ancestors(scope):
        if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return outer
    return source.tree


class FileRewrite:
    """Die Tabelle einer Datei, Zeile für Zeile gesammelt."""

    def __init__(self, ctx: Context, path: str) -> None:
        self.ctx = ctx
        self.path = path
        self.source = ctx.source(path)
        self.edits: list[Edit] = []
        self._ranges: list[tuple[int, int, str]] = []
        self.plans: dict[int, ImportPlan] = {}
        self.chosen: dict[str, str] = {}
        self.identifiers = identifiers(self.source.tree)
        self.watches: list[Watch] = []
        self.assign_watches: list[AssignWatch] = []
        self._after_assign: set[tuple[int, str]] = set()

    # ---- Ausdrücke

    def _range(self, node: ast.AST) -> tuple[int, int]:
        line = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)
        end_line = getattr(node, "end_lineno", line)
        end_col = getattr(node, "end_col_offset", col)
        return self.source.offset(line, col), self.source.offset(end_line, end_col)

    def covered(self, node: ast.AST) -> bool:
        start, end = self._range(node)
        return any(s <= start and end <= e for s, e, _ in self._ranges)

    def replace(self, node: ast.AST, text: str, rule: str) -> None:
        """Ersetzt den Ausdruck ``node``; dieselbe Stelle zweimal mit gleichem Text ist eine."""
        start, end = self._range(node)
        for s, e, existing in self._ranges:
            if (s, e) == (start, end):
                if existing != text:
                    self.ctx.problem(
                        f"{self.path}:{getattr(node, 'lineno', '?')}: zwei Regeln ändern "
                        f"denselben Ausdruck ({existing!r} und {text!r}) — Zuschnitt so fassen, "
                        "dass genau eine greift"
                    )
                return
            if s < end and start < e:
                self.ctx.problem(
                    f"{self.path}:{getattr(node, 'lineno', '?')}: zwei Regeln ändern "
                    f"ineinanderliegende Ausdrücke ({self.source.node_text(node)!r})"
                )
                return
        self._ranges.append((start, end, text))
        old = " ".join(self.source.node_text(node).split())
        self.edits.append(Edit.at(self.path, "expr", node, text, rule, f"{old} → {text}"))

    def keep(self, node: ast.AST) -> None:
        """Eine Stelle, die laut Zuschnitt bleibt, wie sie ist: erklärt, ohne Änderung."""
        start, end = self._range(node)
        self._ranges.append((start, end, self.source.text[start:end]))

    def removed_assignments(self) -> list[ast.Assign]:
        """Die Zuweisungen ``x = importlib.import_module(…)``, die nach den Ersetzungen
        niemand mehr liest und die deshalb wegfallen."""
        return [w.stmt for w in self.assign_watches if not self._assignment_used(w)]

    def remove_lines(self, first: int, last: int, node: ast.AST, rule: str) -> None:
        """Entfernt die Zeilen ``first`` bis ``last`` (eine Methode samt Kopfkommentar); was
        darin stand, gilt als ersetzt."""
        start = self.source.line_start(first)
        end = self.source.line_end(last)
        self._ranges.append((start, end, ""))
        name = getattr(node, "name", type(node).__name__)
        self.edits.append(
            Edit(
                self.path,
                "lines",
                rule,
                f"{name} (Zeilen {first} bis {last})",
                "",
                first,
                0,
                last,
                0,
            )
        )

    def insert_after_line(self, line: int, text: str, rule: str) -> None:
        """Fügt fertig eingerückten Text hinter Zeile ``line`` ein."""
        detail = f"hinter Zeile {line}: {text.count(chr(10))} Zeilen"
        self.edits.append(Edit(self.path, "insert", rule, detail, text, line, 0, line, 0))

    def remove_statement(self, stmt: ast.stmt, rule: str) -> None:
        """Entfernt eine Anweisung samt ihrer Zeilen; was darin stand, gilt als ersetzt (ein Import,
        den nur sie las, fällt dann weg)."""
        if self._only_statement(stmt):
            self.ctx.problem(
                f"{self.path}:{stmt.lineno}: die Anweisung ist die einzige ihres Blocks und fiele "
                "weg — Block vorher umschreiben"
            )
            return
        start, end = self._range(stmt)
        self._ranges.append((start, end, ""))
        old = " ".join(self.source.node_text(stmt).split())
        self.edits.append(Edit.at(self.path, "stmt", stmt, "", rule, f"{old} → (entfällt)"))

    # ---- Importe

    def plan(self, stmt: ast.Import | ast.ImportFrom) -> ImportPlan:
        found = self.plans.get(id(stmt))
        if found is None:
            found = ImportPlan(stmt)
            self.plans[id(stmt)] = found
        return found

    def _block_binding(self, stmt: ast.stmt, module: str) -> str | None:
        """Ein Name, den der Importblock um ``stmt`` schon an ``module`` bindet."""
        parent = self.source.parent(stmt)
        body: list[ast.stmt] = []
        for name in ("body", "orelse", "finalbody"):
            candidate = getattr(parent, name, None)
            if isinstance(candidate, list) and any(s is stmt for s in candidate):
                body = candidate
        for other in body:
            if isinstance(other, ast.ImportFrom):
                base = absolute_module(self.path, other)
                for alias in other.names:
                    if f"{base}.{alias.name}" == module:
                        return bound_name(alias)
            elif isinstance(other, ast.Import):
                for alias in other.names:
                    if alias.name == module and alias.asname:
                        return alias.asname
        planned = self.plans.get(id(stmt))
        if planned is not None:
            for text in planned.after:
                if text == import_text(module, self.chosen.get(module, "")):
                    return self.chosen.get(module)
        return None

    def alias(self, module: str) -> str | None:
        """Der freie Name, unter dem ``module`` in dieser Datei gebunden wird: erklärt in
        ``aliases``, sonst der letzte Teil, sonst ``<vorletzter>_<letzter>``."""
        if module in self.chosen:
            return self.chosen[module]
        declared = [
            a.name for a in self.ctx.cut.aliases if a.path == self.path and a.module == module
        ]
        parts = module.split(".")
        candidates = declared or [parts[-1], "_".join(parts[-2:]), "_".join(parts[-3:])]
        for name in candidates:
            if name not in self.identifiers and name not in self.chosen.values():
                self.chosen[module] = name
                return name
        self.ctx.problem(
            f"{self.path}: kein freier Name für {module} (versucht {candidates}) — in [[aliases]] "
            "einen Namen erklären"
        )
        return None

    def module_expression(
        self, base: ast.expr, module: str, old_module: str, rule: str
    ) -> str | None:
        """Der Text eines Ausdrucks, der an der Stelle von ``base`` (heute das Modul
        ``old_module``) das Modul ``module`` liefert; der nötige Import kommt neben den, der
        ``base`` bindet — neben einen Import, neben eine Zuweisung aus
        ``importlib.import_module`` (in einer Funktion dahinter, auf Modulebene in den Kopf).
        ``import_module("…")`` und ``sys.modules["…"]`` als Ausdruck bekommen den neuen Namen."""
        literal = self._literal_module(base, old_module)
        if literal is not None:
            return literal(module)
        if self.ctx.shadowed(module):
            self.ctx.problem(
                f"{self.path}:{getattr(base, 'lineno', '?')}: {module} liegt hinter dem "
                "gleichnamigen trägen Export seines Pakets — ein Import bände den Namen, nicht "
                "das Modul; vor dem Schnitt hier importlib.import_module mit festem Text verwenden"
            )
            return None
        if isinstance(base, ast.Name):
            binders = import_binders(self.source, base.id, base)
            if not binders:
                return self._assigned_module(base, module, old_module, rule)
            existing = {self._block_binding(b, module) for b in binders}
            if len(existing) == 1 and None not in existing:
                found = existing.pop()
                assert found is not None
                self._watch(binders, base.id, old_module, plain=False)
                return found
            alias = self.alias(module)
            if alias is None:
                return None
            for binder in binders:
                plan = self.plan(binder)
                text = import_text(module, alias)
                if text not in plan.after:
                    plan.after.append(text)
                    plan.rules.append(rule)
            self._watch(binders, base.id, old_module, plain=False)
            return alias
        chain = dotted(base)
        if chain is not None:
            root = chain.partition(".")[0]
            root_node = base
            while isinstance(root_node, ast.Attribute):
                root_node = root_node.value
            binders = import_binders(self.source, root, root_node)
            plain = [b for b in binders if isinstance(b, ast.Import)]
            if binders and len(plain) == len(binders) and module.partition(".")[0] == root:
                for binder in plain:
                    if any(a.name == module and a.asname is None for a in binder.names):
                        continue
                    plan = self.plan(binder)
                    text = f"import {module}"
                    if text not in plan.after:
                        plan.after.append(text)
                        plan.rules.append(rule)
                self._watch(binders, root, old_module, plain=True)
                return module
        self.ctx.problem(
            f"{self.path}:{getattr(base, 'lineno', '?')}: Ausdruck "
            f"{self.source.node_text(base)!r} lässt sich nicht auf {module} umstellen — vor dem "
            "Schnitt als Import, Attributkette eines Imports oder importlib.import_module mit "
            "festem Text schreiben"
        )
        return None

    def _literal_module(self, base: ast.expr, old_module: str) -> Callable[[str], str] | None:
        """``importlib.import_module("M")`` als Ausdruck: der Text mit neuem Modulnamen.
        ``sys.modules["M"]`` wird abgewiesen — nach dem Schnitt ist das Zielmodul dort nur, wenn
        es jemand vorher geladen hat."""
        if isinstance(base, ast.Subscript) and isinstance(base.slice, ast.Constant):
            values = self.ctx.index.resolve(self.path, base.value)
            if values and all(v.kind == "ext" and v.ref == "sys.modules" for v in values):
                self.ctx.problem(
                    f"{self.path}:{base.lineno}: sys.modules[{base.slice.value!r}] — nach dem "
                    "Schnitt steht das Zielmodul dort nur, wenn es jemand geladen hat; vor dem "
                    "Schnitt importlib.import_module verwenden"
                )
                return lambda _module: self.source.node_text(base)
        if not (
            isinstance(base, ast.Call)
            and len(base.args) == 1
            and not base.keywords
            and isinstance(base.args[0], ast.Constant)
            and base.args[0].value == old_module
        ):
            return None
        values = self.ctx.index.resolve(self.path, base.func)
        if not values or not all(
            v.kind == "ext" and v.ref == "importlib.import_module" for v in values
        ):
            return None
        func = self.source.node_text(base.func)
        argument = base.args[0]
        return lambda module: f"{func}({quoted(self.source, argument, module)})"

    def _assigned_module(
        self, base: ast.Name, module: str, old_module: str, rule: str
    ) -> str | None:
        """``base`` ist über ``x = importlib.import_module("M")`` gebunden: Der Import des
        neuen Moduls kommt in einer Funktion direkt hinter die Zuweisung, auf Modulebene in den
        Importkopf — dieselbe Ladezeit. Die Zuweisung fällt weg, wenn ``x`` niemand mehr liest."""
        assigns = assignment_binders(self.source, base.id, base)
        if not assigns or not all(
            self.ctx.is_module(self.path, a.value, old_module) for a in assigns
        ):
            self.ctx.problem(
                f"{self.path}:{base.lineno}: {base.id!r} ist das Modul {old_module}, aber nicht "
                "über einen Import oder importlib.import_module gebunden (Parameter, Fixture) — "
                "vor dem Schnitt als Import schreiben"
            )
            return None
        alias = self.alias(module)
        if alias is None:
            return None
        text = import_text(module, alias)
        for assign in assigns:
            if _module_level(self.source, assign):
                anchor = self.head_anchor()
                if anchor is None:
                    self.ctx.problem(
                        f"{self.path}:{assign.lineno}: kein Importkopf auf Modulebene für "
                        f"{text!r} — vor dem Schnitt einen Import an den Kopf stellen"
                    )
                    return None
                plan = self.plan(anchor)
                if text not in plan.after:
                    plan.after.append(text)
                    plan.rules.append(rule)
            elif (id(assign), text) not in self._after_assign:
                self._after_assign.add((id(assign), text))
                detail = f"neu hinter Zeile {assign.lineno}: {text}"
                self.edits.append(Edit.at(self.path, "after", assign, text, rule, detail))
            if not any(w.stmt is assign for w in self.assign_watches):
                self.assign_watches.append(AssignWatch(assign, base.id, old_module))
        return alias

    def head_anchor(self) -> ast.Import | ast.ImportFrom | None:
        """Die letzte Anweisung des ersten Importblocks auf Modulebene (ohne ``__future__``)."""
        last: ast.Import | ast.ImportFrom | None = None
        for stmt in self.source.tree.body:
            if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
                continue
            if isinstance(stmt, IMPORTS):
                last = stmt
                continue
            if last is not None:
                break
            if docstring_node(self.source.tree.body) is stmt:
                continue
            break
        return last

    def watch_import(
        self, binders: list[ast.Import | ast.ImportFrom], name: str, module: str
    ) -> None:
        """Der Import, der ``name`` an ``module`` bindet, fällt weg, wenn ihn danach niemand
        mehr liest."""
        self._watch(binders, name, module, plain=False)

    def watch_name(self, binders: list[ast.Import | ast.ImportFrom], name: str) -> None:
        """Der Import, der ``name`` bindet (eine Klasse, eine Funktion), fällt weg, wenn danach
        kein Name ``name`` in der Datei mehr gelesen wird."""
        self._watch(binders, name, "", plain=False)

    def _replaced_reads(self, name: str) -> bool:
        """Ob ein neuer Text dieser Tabelle ``name`` liest (``state.bump`` liest ``state``)."""
        for _start, _end, text in self._ranges:
            if not text:
                continue
            try:
                tree = ast.parse(text, mode="eval")
            except SyntaxError:
                continue
            if any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(tree)):
                return True
        return False

    def _watch(
        self, binders: list[ast.Import | ast.ImportFrom], name: str, module: str, *, plain: bool
    ) -> None:
        for binder in binders:
            for number, alias in enumerate(binder.names):
                if bound_name(alias) != name:
                    continue
                if plain and not isinstance(binder, ast.Import):
                    continue
                key = (id(binder), number)
                if not any((id(w.stmt), w.number) == key for w in self.watches):
                    self.watches.append(Watch(binder, number, module, plain))

    def rebind(self, stmt: ast.ImportFrom, number: int, module: str, name: str, rule: str) -> None:
        """Ein Eintrag ``from M import N [as b]`` wird ``from module import name as b``; der
        gebundene Name bleibt, damit kein Leser in der Datei umbenannt werden muss."""
        alias = stmt.names[number]
        bound = bound_name(alias)
        plan = self.plan(stmt)
        plan.replace[number] = [from_text(module, [(name, bound)])]
        plan.rules.append(rule)

    # ---- Abschluss

    def finish(self) -> list[Edit]:
        """Die gesammelten Zeilen samt Importänderungen; ungelesene Importe fallen weg."""
        for watch in self.watches:
            plan = self.plan(watch.stmt)
            if watch.number in plan.replace or watch.number in plan.drop:
                continue
            if self._still_used(watch):
                continue
            if watch.plain and not plan.after:
                continue
            plan.drop.add(watch.number)
            plan.rules.append("Import ohne Leser fällt weg")
        out = list(self.edits)
        for assign_watch in self.assign_watches:
            if self._assignment_used(assign_watch):
                continue
            stmt = assign_watch.stmt
            if self._only_statement(stmt):
                self.ctx.problem(
                    f"{self.path}:{stmt.lineno}: die Zuweisung ist die einzige Anweisung ihres "
                    "Blocks und fiele weg — Block vorher umschreiben"
                )
                continue
            old = " ".join(self.source.node_text(stmt).split())
            out.append(
                Edit.at(
                    self.path,
                    "stmt",
                    stmt,
                    "",
                    "Zuweisung des Moduls ohne Leser fällt weg",
                    f"{old} → (entfällt)",
                )
            )
        for plan in self.plans.values():
            edit = self._import_edit(plan)
            if edit is not None:
                out.append(edit)
        return out

    def _assignment_used(self, watch: AssignWatch) -> bool:
        """Ob ``x`` aus ``x = importlib.import_module(…)`` außerhalb der ersetzten Stellen noch
        als dieses Modul gelesen wird."""
        if self._replaced_reads(watch.name):
            return True
        for node in ast.walk(self.source.tree):
            if not isinstance(node, ast.Name) or node.id != watch.name:
                continue
            if not isinstance(node.ctx, ast.Load) or self.covered(node):
                continue
            if self.ctx.is_module(self.path, node, watch.module):
                return True
        return False

    def _still_used(self, watch: Watch) -> bool:
        name = bound_name(watch.stmt.names[watch.number])
        if not watch.plain and self._replaced_reads(name):
            return True
        for node in ast.walk(self.source.tree):
            if not isinstance(node, ast.Name) or node.id != name:
                continue
            if not isinstance(node.ctx, ast.Load) or self.covered(node):
                continue
            if watch.plain:
                parent = self.source.parent(node)
                chain: ast.expr = node
                while isinstance(parent, ast.Attribute):
                    chain = parent
                    parent = self.source.parent(parent)
                text = dotted(chain) or ""
                if self.covered(chain):
                    continue
                if text == watch.module or text.startswith(watch.module + "."):
                    return True
                continue
            if not watch.module or self.ctx.is_module(self.path, node, watch.module):
                return True
        return False

    def _import_edit(self, plan: ImportPlan) -> Edit | None:
        stmt = plan.stmt
        if not plan.drop and not plan.replace and not plan.after:
            return None
        statements: list[str] = []
        kept = [n for n in range(len(stmt.names)) if n not in plan.drop and n not in plan.replace]
        if kept and len(kept) == len(stmt.names):
            statements.append(self._original(stmt))
        elif kept:
            statements.append(self._rebuilt(stmt, kept))
        for number in sorted(plan.replace):
            statements.extend(plan.replace[number])
        for text in plan.after:
            if text not in statements:
                statements.append(text)
        comment = trailing_comment(self.source, stmt)
        if comment:
            statements = [
                s if s.rstrip().endswith(comment) else f"{s}  {comment}" for s in statements
            ]
        rules = "; ".join(dict.fromkeys(plan.rules)) or "Import umgestellt"
        old = " ".join(self.source.node_text(stmt).split())
        detail = f"{old} → {' | '.join(statements) if statements else '(entfällt)'}"
        if not statements and self._only_statement(stmt):
            self.ctx.problem(
                f"{self.path}:{stmt.lineno}: der Import ist die einzige Anweisung seines Blocks "
                "und fiele weg — Block vorher umschreiben"
            )
        if self._inner_comments(stmt) and (plan.drop or plan.replace):
            self.ctx.problem(
                f"{self.path}:{stmt.lineno}: Kommentar in einer mehrzeiligen Importanweisung, die "
                "umgebaut wird — Kommentar vorher hinter die Anweisung stellen"
            )
        return Edit.at(self.path, "stmt", stmt, "\n".join(statements), rules, detail)

    def _original(self, stmt: ast.stmt) -> str:
        text = self.source.node_text(stmt)
        comment = trailing_comment(self.source, stmt)
        return f"{text}  {comment}" if comment else text

    def _rebuilt(self, stmt: ast.Import | ast.ImportFrom, kept: list[int]) -> str:
        if isinstance(stmt, ast.ImportFrom):
            prefix = "." * stmt.level + (stmt.module or "")
            return from_text(prefix, [(stmt.names[n].name, stmt.names[n].asname) for n in kept])
        parts = [
            stmt.names[n].name + (f" as {stmt.names[n].asname}" if stmt.names[n].asname else "")
            for n in kept
        ]
        return f"import {', '.join(parts)}"

    def _only_statement(self, stmt: ast.stmt) -> bool:
        parent = self.source.parent(stmt)
        for name in ("body", "orelse", "finalbody"):
            body = getattr(parent, name, None)
            if isinstance(body, list) and any(s is stmt for s in body):
                return len(body) == 1
        return False

    def _inner_comments(self, stmt: ast.stmt) -> bool:
        if stmt.end_lineno is None or stmt.end_lineno == stmt.lineno:
            return False
        inside = self.source.comments_between(stmt.lineno, stmt.end_lineno - 1)
        return bool(inside)

    # ---- Formen eines Bezugs

    def import_statement(self, line: int, col: int) -> ast.ImportFrom | None:
        found = find_nodes(self.source, ast.ImportFrom, line, col)
        return found[0] if found else None

    def attribute_at(self, line: int, col: int, name: str, module: str) -> ast.Attribute | None:
        """Der Knoten ``X.name`` an der Lage eines Bezugs, dessen ``X`` das Modul ist."""
        for node in find_nodes(self.source, ast.Attribute, line, col):
            if node.attr == name and self.ctx.is_module(self.path, node.value, module):
                return node
        return None

    def call_at(self, line: int, col: int) -> ast.Call | None:
        found = find_nodes(self.source, ast.Call, line, col)
        return found[0] if found else None

    # ---- Umschreiben eines Bezugs (gemeinsam für alle Modi)

    def rebind_from(
        self,
        line: int,
        col: int,
        old_module: str,
        name: str,
        module: str,
        new_name: str,
        rule: str,
    ) -> None:
        """``from old_module import name [as b]`` an der Lage eines Bezugs wird ``from module
        import new_name as b``."""
        stmt = self.import_statement(line, col)
        if stmt is None:
            self.ctx.problem(f"{self.path}:{line}: Importanweisung nicht gefunden (Werkzeugfehler)")
            return
        if absolute_module(self.path, stmt) != old_module:
            return  # über ein anderes Modul (Rückexport, Lazy-Export) — dort umgeschrieben
        for number, alias in enumerate(stmt.names):
            if alias.name == name:
                self.rebind(stmt, number, module, new_name, rule)

    def retarget_attribute(
        self,
        line: int,
        col: int,
        old_module: str,
        name: str,
        module: str,
        new_name: str,
        rule: str,
    ) -> bool:
        """``M.name`` an der Lage eines Bezugs wird ``<modul>.new_name``; ``False``, wenn dort
        kein Zugriff über das Modul steht (Lazy-Export eines Pakets)."""
        node = self.attribute_at(line, col, name, old_module)
        if node is None:
            return False
        text = self.module_expression(node.value, module, old_module, rule)
        if text is not None:
            self.replace(node, f"{text}.{new_name}", rule)
        return True

    def retarget_getattr(
        self,
        line: int,
        col: int,
        old_module: str,
        name: str,
        module: str,
        new_name: str,
        rule: str,
    ) -> None:
        """``getattr(M, "name")`` wird ``getattr(<modul>, "new_name")``."""
        call = self.call_at(line, col)
        if (
            call is None
            or len(call.args) < 2
            or not isinstance(call.args[1], ast.Constant)
            or call.args[1].value != name
        ):
            self.ctx.problem(
                f"{self.path}:{line}: getattr auf {old_module}.{name} ohne festen Namen — vor dem "
                "Schnitt mit fester Zeichenkette schreiben"
            )
            return
        text = self.module_expression(call.args[0], module, old_module, rule)
        if text is None:
            return
        self.replace(call.args[0], text, rule)
        if new_name != name:
            self.replace(call.args[1], quoted(self.source, call.args[1], new_name), rule)

    def retarget_patch(
        self, line: int, col: int, form: str, old_module: str, module: str, name: str, rule: str
    ) -> None:
        """Eine Patch-Stelle auf ``old_module.<alt>`` zielt danach auf ``module.name``: als Text
        (``setattr``/``delattr``/``patch``), über ein Modul (``setattr``/``delattr``) oder
        ``patch.object``."""
        call = self.call_at(line, col)
        if call is None or not call.args:
            self.ctx.problem(f"{self.path}:{line}: Patch-Stelle nicht gefunden (Werkzeugfehler)")
            return
        first = call.args[0]
        if (
            form in ("setattr", "delattr", "patch")
            and isinstance(first, ast.Constant)
            and isinstance(first.value, str)
        ):
            if self.ctx.shadowed(module):
                self.ctx.problem(
                    f"{self.path}:{line}: der Pfad {module}.{name} als Text endete beim "
                    "gleichnamigen trägen Export, nicht beim Modul — vor dem Schnitt mit "
                    "importlib.import_module und patch.object/setattr schreiben"
                )
                return
            self.replace(first, quoted(self.source, first, f"{module}.{name}"), rule)
            return
        if form in ("setattr", "delattr", "patch.object") and len(call.args) >= 2:
            second = call.args[1]
            if not isinstance(second, ast.Constant) or not isinstance(second.value, str):
                self.ctx.problem(
                    f"{self.path}:{line}: Patch-Stelle mit gefaltetem Namen — vor dem Schnitt mit "
                    "festem Namen schreiben"
                )
                return
            text = self.module_expression(first, module, old_module, rule)
            if text is None:
                return
            self.replace(first, text, rule)
            if second.value != name:
                self.replace(second, quoted(self.source, second, name), rule)
            return
        self.ctx.problem(
            f"{self.path}:{line}: Patch-Stelle mit gefaltetem Ziel — vor dem Schnitt mit festem "
            "Text schreiben"
        )


def all_imports(source: Source) -> list[ast.Import | ast.ImportFrom]:
    return [node for node in ast.walk(source.tree) if isinstance(node, IMPORTS)]
