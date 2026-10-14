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
from collections.abc import Iterable
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
    dotted,
    identifiers,
    import_binders,
)


class PlanError(Exception):
    """Der Schnitt ist so nicht beweisbar; ``problems`` nennt jede Stelle mit Ausweg."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


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
        ``base`` bindet."""
        if isinstance(base, ast.Name):
            binders = import_binders(self.source, base.id, base)
            if not binders:
                self.ctx.problem(
                    f"{self.path}:{base.lineno}: {base.id!r} ist das Modul {old_module}, aber "
                    "nicht über einen Import gebunden (Parameter, Fixture, Zuweisung) — vor dem "
                    "Schnitt als Import schreiben"
                )
                return None
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
            "Schnitt als Import oder Attributkette eines Imports schreiben"
        )
        return None

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
        for plan in self.plans.values():
            edit = self._import_edit(plan)
            if edit is not None:
                out.append(edit)
        return out

    def _still_used(self, watch: Watch) -> bool:
        name = bound_name(watch.stmt.names[watch.number])
        for node in ast.walk(self.source.tree):
            if not isinstance(node, ast.Name) or node.id != name:
                continue
            if not isinstance(node.ctx, ast.Load) or self.covered(node):
                continue
            if watch.plain:
                parent = self.source.parent(node)
                chain = node
                while isinstance(parent, ast.Attribute):
                    chain = parent  # type: ignore[assignment]
                    parent = self.source.parent(parent)
                text = dotted(chain) or ""
                if self.covered(chain):
                    continue
                if text == watch.module or text.startswith(watch.module + "."):
                    return True
                continue
            if self.ctx.is_module(self.path, node, watch.module):
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


def all_imports(source: Source) -> list[ast.Import | ast.ImportFrom]:
    return [node for node in ast.walk(source.tree) if isinstance(node, IMPORTS)]
