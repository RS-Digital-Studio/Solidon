"""Modulmodus des Verschiebewerkzeugs: Definitionen eines Moduls wandern in neue Module.

Die Quelle ``app/x.py`` wird ein Paket ``app/x/`` mit den Zielmodulen der Zuschnittliste, dessen
``__init__.py`` nur ein Docstring ist (Konzept Codestruktur 3.1, Regeln 2 und 3) — oder sie gibt
Definitionen an Nachbarmodule ab. Jede Anweisung der Quelle auf Modulebene hat danach genau einen
Ort:

* Docstring: ersetzt durch die erklärten Docstrings (Paket und je Ziel).
* ``from __future__`` und Importe, auch unter ``TYPE_CHECKING``: in jedes Ziel, das den Namen
  liest, im selben Kontext, absolut geschrieben.
* Jede andere Anweisung: in das Ziel, das ihre Namen in ``definitions`` nennt — samt Dekoratoren,
  Kopfkommentar und freien Kommentaren davor (``move_source.spans``); ``duplicate`` kommt in jedes
  Ziel, das den Namen liest.

Liest eine Definition einen Namen, der in ein anderes Ziel wandert, liest sie ihn danach über
das Modul (``state.bump()``): Ein Patch am Original erreicht so dieselben Leser wie vorher, und
eine Kopfkopie entsteht nicht (W2 c, Entscheidung E1).

Abgewiesen wird **vor** dem Schreiben, jeweils mit Ausweg: ein ``global``-Schreiber, getrennt
von seiner Variable oder ihren Lesern; ein Name, der die Identität des Moduls liest (``__name__``,
``globals()``) ohne Erklärung in ``identity``; ein Kreis zwischen Zielen, der beim Import gelesen
wird; ein Import zwischen den Definitionen; eine Anweisung ohne Bindung; ``__all__``; eine
Zeichenkette, die die alte Datei oder einen verschobenen Namen nennt, ohne Erklärung; ein Patch
auf eine Kopie, die die Quelle hält.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from tools.move_compare import Scopes, qualname_of, string_constants, top_names
from tools.move_cut import Target
from tools.move_edits import Edit
from tools.move_refs import AlreadyAppliedError, Context, quoted
from tools.move_source import (
    AREAS,
    IMPORTS,
    Source,
    Span,
    StatementNames,
    absolute_module,
    bound_name,
    docstring_node,
    is_type_checking,
    names_source,
    path_of,
    spans,
    statement_names,
)


@dataclass
class Unit:
    """Eine Anweisung der Quelle auf Modulebene mit ihren Namen — oder eine Gruppe: die
    ``@overload``-Fassungen einer Funktion samt Umsetzung, die nur zusammen wandern."""

    stmt: ast.stmt
    span: Span
    names: list[str]
    target: Target | None
    facts: StatementNames
    duplicate: bool = False
    group: list[tuple[ast.stmt, Span]] = field(default_factory=list)

    def parts(self) -> list[tuple[ast.stmt, Span]]:
        """Die Anweisungen der Einheit mit ihren eigenen Spannen."""
        return self.group or [(self.stmt, self.span)]

    def absorb(self, stmt: ast.stmt, span: Span, facts: StatementNames) -> None:
        """Nimmt die nächste Fassung einer überladenen Funktion auf."""
        if not self.group:
            self.group.append((self.stmt, self.span))
        self.group.append((stmt, span))
        self.stmt = stmt
        self.span = Span(self.span.first, self.span.head, self.span.start, span.last)
        for name in ("binds", "reads", "writes", "string_reads", "identity"):
            getattr(self.facts, name).update(getattr(facts, name))


def is_overload(stmt: ast.stmt) -> bool:
    """Ob ``stmt`` eine ``@overload``-Fassung einer Funktion ist."""
    return isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
        ast.unparse(d) in ("overload", "typing.overload") for d in stmt.decorator_list
    )


@dataclass
class ModulePlan:
    files: dict[str, str] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    edits: dict[str, list[Edit]] = field(default_factory=dict)


_HEAD = re.compile(r"^(\s*)(async\s+def|def|class)(\s+)([A-Za-z_][A-Za-z0-9_]*)")

#: Attribute, die das Modul als Ganzes beschreiben: Nach dem Schnitt beschrieben sie das Paket.
MODULE_VALUE_ATTRIBUTES = frozenset(
    {"__dict__", "__doc__", "__spec__", "__loader__", "__package__", "__cached__", "__path__"}
)


class ModulePlanner:
    """Plant einen Schnitt im Modulmodus; Funde sammelt ``ctx`` und meldet sie gemeinsam."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.cut = ctx.cut
        self.path = self.cut.source
        self.src = self.cut.source_module
        self.targets = {t.module: t for t in self.cut.targets}
        self.units: list[Unit] = []
        self.unit_of: dict[str, Unit] = {}
        self.future: list[ast.ImportFrom] = []
        self.imports: list[tuple[ast.Import | ast.ImportFrom, bool]] = []
        self.patched = ctx.index.patched_names()
        self.unit_edits: list[Edit] = []
        self.aliases: dict[str, dict[str, str]] = {}
        self.used_lists: set[int] = set()
        self.used_readers: set[int] = set()

    # ------------------------------------------------------------------ Einstieg

    def plan(self) -> ModulePlan:
        self._tree()
        self.ctx.raise_problems()
        self.source = self.ctx.source(self.path)
        self._classify()
        self.ctx.raise_problems()
        self._head()
        self._check_globals()
        self._check_identity()
        self._dependencies()
        self.ctx.raise_problems()
        self._unit_rewrites()
        self._source_texts()
        files = {path_of(t.module): self._target_text(t) for t in self.cut.targets}
        if self.cut.package:
            files[path_of(self.src, package=True)] = _docstring_text(self.cut.package_docstring)
        self._references()
        self._patches()
        self._long_patches()
        self._hasattr()
        self._module_values()
        self._source_readers()
        self._name_lists()
        self._lazy_exports()
        self._stale_strings()
        self.ctx.raise_problems()
        plan = ModulePlan(files=files)
        if self.src not in self.targets:
            plan.removed.append(self.path)
        for path, rewrite in sorted(self.ctx.rewrites().items()):
            edits = rewrite.finish()
            if edits:
                plan.edits[path] = edits
        self.ctx.raise_problems()
        return plan

    # ------------------------------------------------------------------ Baum

    def _tree(self) -> None:
        root = self.ctx.root
        target_paths = [path_of(t) for t in self.targets if t != self.src]
        if self.cut.package:
            target_paths.append(path_of(self.src, package=True))
        present = [p for p in target_paths if (root / p).exists()]
        if not (root / self.path).is_file():
            if present and len(present) == len(target_paths):
                raise AlreadyAppliedError(
                    f"{self.path} fehlt, {', '.join(present)} stehen schon — der Schnitt ist "
                    "angewandt; nichts zu tun"
                )
            self.ctx.problem(f"{self.path}: die Quelle fehlt im Baum")
            return
        for path in present:
            self.ctx.problem(
                f"{path}: das Zielmodul gibt es schon — ein anderes Ziel wählen oder den Stand "
                "prüfen (halb angewandter Schnitt?)"
            )
        if (root / self.path).with_suffix(".pyi").exists():
            self.ctx.problem(f"{self.path}: neben der Quelle liegt ein Stub (.pyi) — erst klären")

    # ------------------------------------------------------------------ Quelle zerlegen

    def _classify(self) -> None:
        body = self.source.tree.body
        found = spans(self.source, body)
        doc = docstring_node(body)
        declared = {n for t in self.cut.targets for n in t.definitions}
        seen_unit = False
        for stmt, span in zip(body, found, strict=True):
            if stmt is doc:
                continue
            if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
                self.future.append(stmt)
                continue
            checking = isinstance(stmt, ast.If) and is_type_checking(stmt.test)
            if isinstance(stmt, IMPORTS) or checking:
                if seen_unit:
                    self.ctx.problem(
                        f"{self.path}:{stmt.lineno}: Import zwischen den Definitionen — vor dem "
                        "Schnitt an den Kopf der Datei ziehen"
                    )
                if isinstance(stmt, IMPORTS):
                    self.imports.append((stmt, False))
                    continue
                assert isinstance(stmt, ast.If)
                if stmt.orelse or not all(isinstance(s, IMPORTS) for s in stmt.body):
                    self.ctx.problem(
                        f"{self.path}:{stmt.lineno}: ``if TYPE_CHECKING:`` mit mehr als Importen "
                        "— Typen vorher in ein Modul ziehen, unter TYPE_CHECKING bleiben nur "
                        "Importe"
                    )
                    continue
                for inner in stmt.body:
                    assert isinstance(inner, (ast.Import, ast.ImportFrom))
                    self.imports.append((inner, True))
                continue
            seen_unit = True
            names = top_names(stmt)
            text = " ".join(self.source.lines[stmt.lineno - 1].split())[:60]
            if not names:
                self.ctx.problem(
                    f"{self.path}:{stmt.lineno}: Anweisung ohne Bindung ({text!r}) — vor dem "
                    "Schnitt in eine Funktion ziehen oder einer Definition zuordnen"
                )
                continue
            if "__all__" in names:
                self.ctx.problem(
                    f"{self.path}:{stmt.lineno}: ``__all__`` in der Quelle — vor dem Schnitt "
                    "entfernen; danach zeigt jeder Importeur auf das Modul des Namens"
                )
                continue
            targets = {t.module: t for n in names if (t := self.cut.target_of(n)) is not None}
            duplicate = all(n in self.cut.duplicate for n in names)
            missing = [n for n in names if self.cut.target_of(n) is None and not duplicate]
            if missing:
                self.ctx.problem(
                    f"{self.path}:{stmt.lineno}: {', '.join(missing)} in keinem Ziel — in "
                    "definitions eines Ziels oder in duplicate eintragen"
                )
                continue
            if len(targets) > 1:
                self.ctx.problem(
                    f"{self.path}:{stmt.lineno}: eine Anweisung bindet {', '.join(names)}, der "
                    f"Zuschnitt verteilt sie auf {', '.join(sorted(targets))} — alle in ein Ziel "
                    "(eine Anweisung wird nicht zerrissen)"
                )
                continue
            facts = statement_names(self.source, stmt, span)
            previous = self.units[-1] if self.units else None
            if (
                previous is not None
                and isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                and previous.names == names
                and all(is_overload(part) for part, _span in previous.parts())
            ):
                previous.absorb(stmt, span, facts)
                continue
            unit = Unit(stmt, span, names, next(iter(targets.values()), None), facts, duplicate)
            self.units.append(unit)
            for name in names:
                if name in self.unit_of:
                    self.ctx.problem(
                        f"{self.path}:{stmt.lineno}: {name!r} wird zweimal gebunden — vor dem "
                        "Schnitt einen umbenennen"
                    )
                self.unit_of[name] = unit
        for name in sorted(declared - set(self.unit_of)):
            self.ctx.problem(
                f"{name!r} steht in definitions, ist in {self.path} aber nicht auf Modulebene "
                "gebunden — Namen prüfen"
            )
        for name in sorted(set(self.cut.duplicate) - set(self.unit_of)):
            self.ctx.problem(f"duplicate: {name!r} ist in {self.path} nicht gebunden")
        bound = {bound_name(a) for stmt, _ in self.imports for a in stmt.names}
        for name in sorted(bound & set(self.unit_of)):
            self.ctx.problem(
                f"{self.path}: {name!r} wird importiert und neu gebunden — vor dem Schnitt einen "
                "der beiden umbenennen"
            )

    def _head(self) -> None:
        """Der Kopf der Quelle (Docstring, Importe) entsteht in jedem Ziel neu: Ein Kommentar
        dort hätte kein Ziel, und ein Import, den keine Definition liest (ein Seiteneffekt),
        fiele still weg — beides hält den Schnitt an."""
        end = self.units[0].span.first - 1 if self.units else len(self.source.lines)
        for comment in self.source.comments_between(1, end):
            self.ctx.problem(
                f"{self.path}:{comment.line}: Kommentar im Kopf der Quelle "
                f"({comment.text.strip()!r}) — die Köpfe der Ziele entstehen neu; vor dem Schnitt "
                "an eine Definition stellen oder entfernen"
            )
        needed: set[str] = set()
        for unit in self.units:
            needed |= unit.facts.all_reads
        checking_read = any(
            bound_name(alias) in needed
            for stmt, checking in self.imports
            if checking
            for alias in stmt.names
        )
        tests = {
            node.id
            for stmt in self.source.tree.body
            if isinstance(stmt, ast.If) and is_type_checking(stmt.test)
            for node in ast.walk(stmt.test)
            if isinstance(node, ast.Name)
        }
        for stmt, _checking in self.imports:
            for alias in stmt.names:
                name = bound_name(alias)
                if name in needed or (name in tests and checking_read):
                    continue
                self.ctx.problem(
                    f"{self.path}:{stmt.lineno}: Import {_import_text(self.path, stmt, [alias])} "
                    "liest keine Definition der Quelle (ein Seiteneffekt?) — er fiele beim Schnitt "
                    "weg; vorher in die Definition ziehen, die ihn braucht, oder entfernen"
                )

    def _check_globals(self) -> None:
        """Ein ``global``-Schreiber bleibt mit seiner Variable und deren Lesern in einem Modul
        (Plan 2.7, Punkt 3)."""
        for unit in self.units:
            for name in sorted(unit.facts.writes):
                coupled = [u for u in self.units if name in u.facts.all_reads or name in u.names]
                owner = self.unit_of.get(name)
                if owner is not None and owner not in coupled:
                    coupled.append(owner)
                if unit not in coupled:
                    coupled.append(unit)
                homes = {u.target.module if u.target else "(doppelt)" for u in coupled}
                if len(homes) > 1 or any(u.duplicate for u in coupled):
                    names = sorted({n for u in coupled for n in u.names})
                    home = owner.target.module if owner and owner.target else min(homes)
                    self.ctx.problem(
                        f"{self.path}: {', '.join(unit.names)} schreibt {name!r} über global; "
                        f"Schreiber, Variable und Leser ({', '.join(names)}) liegen in "
                        f"{', '.join(sorted(homes))} — alle in ein Ziel legen, etwa {home}"
                    )

    def _check_identity(self) -> None:
        declared = {i.name for i in self.cut.identity}
        for unit in self.units:
            if unit.facts.identity and not declared & set(unit.names):
                self.ctx.problem(
                    f"{self.path}:{unit.stmt.lineno}: {', '.join(unit.names)} liest die "
                    f"Identität des Moduls ({', '.join(sorted(unit.facts.identity))}), die der "
                    "Schnitt ändert — in [[identity]] mit Grund erklären oder vorher umschreiben"
                )
        for name in sorted(declared):
            found = self.unit_of.get(name)
            if found is not None and not found.facts.identity:
                self.ctx.problem(f"identity: {name!r} liest keine Modulidentität — streichen")

    # ------------------------------------------------------------------ Abhängigkeiten

    def _homes(self, unit: Unit) -> list[str]:
        if unit.target is not None:
            return [unit.target.module]
        return [t for t in self.targets if self._reads(t, unit.names[0])]

    def _reads(self, target: str, name: str) -> bool:
        return any(
            name in u.facts.all_reads
            for u in self.units
            if u.target is not None and u.target.module == target
        )

    def _cross(self) -> list[tuple[Unit, ast.Name, Unit, bool]]:
        """Jeder Name einer Definition, der eine Definition eines anderen Ziels liest: (Leser,
        Knoten, gelesene Definition, beim Import gelesen)."""
        found: list[tuple[Unit, ast.Name, Unit, bool]] = []
        for unit in self.units:
            homes = self._homes(unit)
            for part, span in unit.parts():
                scopes = Scopes(self.source, part, span)
                for node in ast.walk(part):
                    if not isinstance(node, ast.Name) or node.id in unit.names:
                        continue
                    other = self.unit_of.get(node.id)
                    if other is None or other.duplicate or not scopes.is_global(node):
                        continue
                    assert other.target is not None
                    if all(home == other.target.module for home in homes):
                        continue
                    found.append((unit, node, other, self._import_time(part, node)))
        return found

    def _import_time(self, stmt: ast.stmt, node: ast.AST) -> bool:
        """Ob ``node`` beim Import läuft (Modulebene, Klassenrumpf, Dekorator, Vorgabe) — nicht in
        einem Funktionsrumpf und nicht in einer Annotation (Python 3.14 wertet sie erst bei
        Bedarf aus)."""
        current = node
        for outer in self.source.ancestors(node):
            if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(current is s for s in outer.body):
                    return False
                if current is outer.returns or any(
                    current is a.annotation
                    for a in [*outer.args.posonlyargs, *outer.args.args, *outer.args.kwonlyargs]
                ):
                    return False
            if isinstance(outer, ast.Lambda) and current is outer.body:
                return False
            if isinstance(outer, ast.AnnAssign) and current is outer.annotation:
                return False
            if isinstance(outer, ast.arg) and current is outer.annotation:
                return False
            if outer is stmt:
                return True
            current = outer
        return True

    def _dependencies(self) -> None:
        """Ein Kreis zwischen Zielen ist nur dann ein Problem, wenn ein Modul ein anderes schon
        beim Import liest, das es selbst (über seine Kopfimporte) noch nicht fertig geladen hat."""
        cross = self._cross()
        self.cross = cross
        imports: dict[str, set[str]] = {}
        for unit, _node, other, _early in cross:
            assert other.target is not None
            for home in self._homes(unit):
                imports.setdefault(home, set()).add(other.target.module)
        for unit, node, other, early in cross:
            if not early:
                continue
            assert other.target is not None
            for home in self._homes(unit):
                if _reaches(imports, other.target.module, home):
                    self.ctx.problem(
                        f"{self.path}:{node.lineno}: {', '.join(unit.names)} ({home}) liest "
                        f"{other.names[0]} ({other.target.module}) beim Import, und "
                        f"{other.target.module} importiert {home} — die beiden in ein Ziel legen "
                        "oder den gemeinsamen Teil in ein drittes"
                    )

    # ------------------------------------------------------------------ Ziele

    def _alias(self, home: str, module: str) -> str:
        chosen = self.aliases.setdefault(home, {})
        if module in chosen:
            return chosen[module]
        taken = {n for u in self.units for n in u.names} | {
            bound_name(a) for stmt, _ in self.imports for a in stmt.names
        }
        declared = [
            a.name for a in self.cut.aliases if a.path == path_of(home) and a.module == module
        ]
        parts = module.split(".")
        candidates = declared or [parts[-1], "_".join(parts[-2:])]
        for name in candidates:
            if name not in taken and name not in chosen.values():
                chosen[module] = name
                return name
        self.ctx.problem(
            f"{path_of(home)}: kein freier Name für {module} (versucht {candidates}) — in "
            "[[aliases]] einen Namen erklären"
        )
        return candidates[0]

    def _unit_rewrites(self) -> None:
        """Umbenennungen und Zugriffe über ein anderes Ziel in den verschobenen Rümpfen."""
        for unit, reader, other, _early in self.cross:
            assert other.target is not None
            if unit.duplicate:
                self.ctx.problem(
                    f"{self.path}:{reader.lineno}: das doppelt Mitgenommene {unit.names[0]!r} "
                    f"liest {reader.id!r} aus einem anderen Ziel — nicht doppelt mitnehmen"
                )
                continue
            assert unit.target is not None
            alias = self._alias(unit.target.module, other.target.module)
            text = f"{alias}.{self.cut.renamed(reader.id)}"
            if not isinstance(reader.ctx, ast.Load):
                self.ctx.problem(
                    f"{self.path}:{reader.lineno}: {reader.id!r} wird aus einem anderen Ziel "
                    "geschrieben — Schreiber und Variable in ein Ziel"
                )
                continue
            self.unit_edits.append(
                Edit.at(self.path, "expr", reader, text, "Zugriff über das Zielmodul", reader.id)
            )
        renamed = {r.name: r.to for r in self.cut.renames}
        cross_nodes = {id(name) for _u, name, _o, _e in self.cross}
        crossed = {o.names[0] for _u, _n, o, _e in self.cross}
        for unit in self.units:
            for part, span in unit.parts():
                self._part_rewrites(part, span, renamed, cross_nodes, crossed)

    def _part_rewrites(
        self,
        part: ast.stmt,
        span: Span,
        renamed: dict[str, str],
        cross_nodes: set[int],
        crossed: set[str],
    ) -> None:
        scopes = Scopes(self.source, part, span)
        for node in ast.walk(part):
            if (
                isinstance(node, ast.Name)
                and node.id in renamed
                and id(node) not in cross_nodes
                and scopes.is_global(node)
            ):
                self.unit_edits.append(
                    Edit.at(self.path, "expr", node, renamed[node.id], "Umbenennung", node.id)
                )
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                touched = _string_annotation_names(self.source, node) & (set(renamed) | crossed)
                if touched:
                    self.ctx.problem(
                        f"{self.path}:{node.lineno}: Annotation als Zeichenkette nennt "
                        f"{', '.join(sorted(touched))}, das umbenannt oder über ein anderes "
                        "Ziel gelesen wird — vor dem Schnitt ohne Anführung schreiben"
                    )
        if (
            isinstance(part, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and part.name in renamed
        ):
            self.unit_edits.append(self._head_edit(part, renamed[part.name]))

    def _head_edit(
        self, stmt: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, new: str
    ) -> Edit:
        line = self.source.lines[stmt.lineno - 1]
        match = _HEAD.match(line)
        if match is None or match.group(4) != stmt.name:
            self.ctx.problem(f"{self.path}:{stmt.lineno}: Kopf von {stmt.name!r} nicht lesbar")
            return Edit.at(self.path, "expr", stmt, "", "", "")
        start = len(line[: match.start(4)].encode("utf-8"))
        end = start + len(stmt.name.encode("utf-8"))
        return Edit(
            self.path, "expr", "Umbenennung", stmt.name, new, stmt.lineno, start, stmt.lineno, end
        )

    def _target_text(self, target: Target) -> str:
        units = [
            u
            for u in self.units
            if (u.target is target) or (u.duplicate and self._reads(target.module, u.names[0]))
        ]
        needed: set[str] = set()
        for unit in units:
            needed |= unit.facts.all_reads
        runtime: list[str] = []
        checking: list[str] = []
        for stmt, in_checking in self.imports:
            kept = [a for a in stmt.names if bound_name(a) in needed]
            if not kept:
                continue
            text = _import_text(self.path, stmt, kept)
            (checking if in_checking else runtime).append(text)
        if checking:
            for stmt, in_checking in self.imports:
                if not in_checking and any(bound_name(a) == "TYPE_CHECKING" for a in stmt.names):
                    text = _import_text(
                        self.path, stmt, [a for a in stmt.names if bound_name(a) == "TYPE_CHECKING"]
                    )
                    if text not in runtime:
                        runtime.append(text)
        for module, alias in sorted(self.aliases.get(target.module, {}).items()):
            parent, _, last = module.rpartition(".")
            runtime.append(
                f"from {parent} import {last}" + (f" as {alias}" if alias != last else "")
            )
        parts = [_docstring_text(target.docstring).rstrip("\n")]
        if self.future:
            parts.append("\n".join(self.source.node_text(f) for f in self.future))
        if runtime:
            parts.append("\n".join(runtime))
        if checking:
            parts.append("if TYPE_CHECKING:\n" + "\n".join("    " + c for c in checking))
        head = "\n\n".join(parts) + "\n"
        body = "".join(self._unit_text(unit) for unit in units).lstrip("\n")
        return head + "\n\n" + body.rstrip("\n") + "\n"

    def _unit_text(self, unit: Unit) -> str:
        first = unit.span.first
        last = unit.span.last
        sub = self.source.lines_text(first, last)
        start = self.source.line_start(first)
        end = self.source.line_end(last)
        ops = []
        for edit in self.unit_edits:
            a = self.source.offset(edit.line, edit.col)
            b = self.source.offset(edit.end_line, edit.end_col)
            if start <= a and b <= end:
                ops.append((a - start, b - start, edit.text))
        out: list[str] = []
        cursor = 0
        for a, b, text in sorted(ops):
            out.append(sub[cursor:a])
            out.append(text)
            cursor = b
        out.append(sub[cursor:])
        # Leerzeilen davor bleiben, wie sie in der Quelle standen; dahinter genau ein Zeilenende.
        return "".join(out).replace("\r\n", "\n").rstrip("\n") + "\n"

    # ------------------------------------------------------------------ Leser

    def _moved(self) -> dict[str, tuple[str, str]]:
        return {
            name: (unit.target.module, self.cut.renamed(name))
            for unit in self.units
            if unit.target is not None
            for name in unit.names
        }

    def _reexports(self) -> dict[str, tuple[str, str]]:
        """Importbindungen der Quelle, die kein Modul sind: ``Shape`` → (app.core.shapes, Shape)."""
        found: dict[str, tuple[str, str]] = {}
        for stmt, checking in self.imports:
            if checking or not isinstance(stmt, ast.ImportFrom):
                continue
            module = absolute_module(self.path, stmt)
            for alias in stmt.names:
                if not self.ctx.index.module_exists(f"{module}.{alias.name}"):
                    found[bound_name(alias)] = (module, alias.name)
        return found

    def _references(self) -> None:
        moved = self._moved()
        reexports = self._reexports()
        for name, (module, new_name) in [*moved.items(), *reexports.items()]:
            rule = "verschoben" if name in moved else "Rückexport der Quelle zeigt auf den Ursprung"
            for ref in self.ctx.index.references(self.src, name):
                if ref.path == self.path or ref.kind == "patch":
                    continue
                rewrite = self.ctx.rewrite(ref.path)
                where = (ref.line, ref.col, self.src, name, module, new_name, rule)
                if ref.kind == "from":
                    rewrite.rebind_from(*where)
                elif ref.kind in ("attribute", "store", "delete"):
                    # Ohne Zugriff über das Modul: ein Lazy-Export, den _lazy_exports umschreibt.
                    rewrite.retarget_attribute(*where)
                elif ref.kind == "getattr":
                    rewrite.retarget_getattr(*where)
                else:
                    self.ctx.problem(
                        f"{ref.path}:{ref.line}: Bezug auf {self.src}.{name} über {ref.kind} — "
                        "vor dem Schnitt als Import oder Attribut schreiben"
                    )
        for name in self.cut.duplicate:
            for ref in self.ctx.index.references(self.src, name):
                if ref.path == self.path or ref.kind == "patch":
                    continue
                self.ctx.problem(
                    f"{ref.path}:{ref.line}: liest {self.src}.{name} von außen, das der Zuschnitt "
                    "in jedes lesende Ziel kopiert (duplicate) — danach gäbe es den Namen dort "
                    "nicht; vor dem Schnitt nicht doppelt mitnehmen, sondern in ein Ziel legen"
                )
        for ref in self.ctx.index.references(self.src, "__file__"):
            if not any(r.path == ref.path for r in self.cut.source_readers):
                self.ctx.problem(
                    f"{ref.path}:{ref.line}: liest die Quelldatei über __file__ — in "
                    "[[source_readers]] das Modul nennen, dessen Definition die Prüfung sucht"
                )

    def _patches(self) -> None:
        moved = self._moved()
        reexports = self._reexports()
        for site in self.ctx.index.patch_sites():
            hits = [t for t in site.targets if t.status == "module" and t.module == self.src]
            if not hits:
                continue
            if len(site.targets) != 1:
                self.ctx.problem(
                    f"{site.path}:{site.line}: Patch-Stelle mit gefaltetem Ziel "
                    f"({site.text}) trifft {self.src} — vor dem Schnitt je Ziel eine Stelle mit "
                    "festem Text schreiben"
                )
                continue
            name = hits[0].name or ""
            if name in self.cut.duplicate:
                self.ctx.problem(
                    f"{site.path}:{site.line}: Patch auf {self.src}.{name}, das der Zuschnitt in "
                    "jedes lesende Ziel kopiert (duplicate) — danach träfe der Patch keine der "
                    "Kopien; vor dem Schnitt nicht doppelt mitnehmen, sondern in ein Ziel legen"
                )
                continue
            if name in reexports:
                self.ctx.problem(
                    f"{site.path}:{site.line}: Patch auf die Kopie {self.src}.{name} — vor dem "
                    "Schnitt mit dem Modus copies auf das Original setzen"
                )
                continue
            if name not in moved:
                continue
            module, new_name = moved[name]
            self.ctx.rewrite(site.path).retarget_patch(
                site.line,
                site.col,
                site.form,
                self.src,
                module,
                new_name,
                "Patch-Ziel folgt dem Namen",
            )

    def _source_readers(self) -> None:
        refs = self.ctx.index.references(self.src, "__file__")
        for number, reader in enumerate(self.cut.source_readers):
            rewrite = self.ctx.rewrite(reader.path)
            for ref in refs:
                if ref.path != reader.path:
                    continue
                node = rewrite.attribute_at(ref.line, ref.col, "__file__", self.src)
                if node is None:
                    continue
                if qualname_of(rewrite.source, node) != reader.scope:
                    continue
                text = rewrite.module_expression(
                    node.value, reader.module, self.src, "Quelltextleser"
                )
                if text is not None:
                    rewrite.replace(node, f"{text}.__file__", "Quelltextleser liest das Ziel")
                    self.used_readers.add(number)
            if number not in self.used_readers:
                self.ctx.problem(
                    f"source_readers: in {reader.path} ({reader.scope}) liest nichts die Quelle "
                    "über M.__file__ — Erklärung streichen oder Bereich prüfen"
                )
        for ref in refs:
            if not any(r.path == ref.path for r in self.cut.source_readers):
                continue
            rewrite = self.ctx.rewrite(ref.path)
            node = rewrite.attribute_at(ref.line, ref.col, "__file__", self.src)
            if node is not None and not rewrite.covered(node):
                self.ctx.problem(
                    f"{ref.path}:{ref.line}: liest die Quelldatei über __file__ außerhalb der "
                    "erklärten Bereiche — in [[source_readers]] erklären"
                )

    def _source_texts(self) -> None:
        """``[[name_lists]]`` mit der Quelle als Pfad gilt für die Zeichenketten in den
        verschobenen Definitionen: Sie bleiben (``to = [value]``) oder werden der eine neue Wert
        — in der Tabelle der Einheiten, also vor dem Schreiben der Ziele."""
        for number, entry in enumerate(self.cut.name_lists):
            if entry.path != self.path:
                continue
            for node in string_constants(self.source):
                if node.value != entry.value:
                    continue
                self.used_lists.add(number)
                if entry.to != (entry.value,):
                    text = quoted(self.source, node, entry.to[0])
                    self.unit_edits.append(
                        Edit.at(self.path, "expr", node, text, "name_lists", entry.value)
                    )
            if number not in self.used_lists:
                self.ctx.problem(
                    f"name_lists: {entry.value!r} steht nicht in {entry.path} — Erklärung streichen"
                )

    def _name_lists(self) -> None:
        for number, entry in enumerate(self.cut.name_lists):
            if entry.path == self.path:
                continue  # in den verschobenen Definitionen: _source_texts
            if not (self.ctx.root / entry.path).is_file():
                self.ctx.problem(f"name_lists: {entry.path} fehlt")
                continue
            rewrite = self.ctx.rewrite(entry.path)
            for node in string_constants(rewrite.source):
                if node.value != entry.value:
                    continue
                if entry.to == (entry.value,):
                    rewrite.keep(node)
                    self.used_lists.add(number)
                    continue
                parent = rewrite.source.parent(node)
                if isinstance(parent, (ast.Tuple, ast.List, ast.Set)):
                    text = ", ".join(quoted(rewrite.source, node, v) for v in entry.to)
                elif len(entry.to) == 1:
                    text = quoted(rewrite.source, node, entry.to[0])
                else:
                    self.ctx.problem(
                        f"{entry.path}:{node.lineno}: {entry.value!r} steht nicht in einer Liste, "
                        "der Zuschnitt nennt aber mehrere neue Werte"
                    )
                    continue
                rewrite.replace(node, text, "name_lists")
                self.used_lists.add(number)
            if number not in self.used_lists:
                self.ctx.problem(
                    f"name_lists: {entry.value!r} steht nicht in {entry.path} — Erklärung streichen"
                )

    def _lazy_exports(self) -> None:
        """Ein träges Paket über der Quelle (``_EXPORTS = {"N": ("quelle", "N")}``) zeigt danach
        auf das Zielmodul."""
        parent, _, last = self.src.rpartition(".")
        path = path_of(parent, package=True)
        if not parent or not (self.ctx.root / path).is_file():
            return
        source = self.ctx.source(path)
        moved = self._moved()
        for node in ast.walk(source.tree):
            if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
                continue
            first, second = node.elts
            if not (
                isinstance(first, ast.Constant)
                and first.value == last
                and isinstance(second, ast.Constant)
                and isinstance(second.value, str)
            ):
                continue
            name = second.value
            if name not in moved:
                if name in self.unit_of or name in self._reexports():
                    self.ctx.problem(f"{path}:{node.lineno}: Lazy-Export auf {name!r} ohne Ziel")
                continue
            module, new_name = moved[name]
            if not module.startswith(parent + "."):
                self.ctx.problem(
                    f"{path}:{node.lineno}: der träge Export auf {name!r} zeigte nach {module}, "
                    f"außerhalb von {parent} — das Ziel ins Paket legen oder den Export vorher "
                    "umstellen"
                )
                continue
            rewrite = self.ctx.rewrite(path)
            sub = module[len(parent) + 1 :]
            rewrite.replace(first, quoted(source, first, sub), "Lazy-Export folgt dem Namen")
            if new_name != name:
                rewrite.replace(
                    second, quoted(source, second, new_name), "Lazy-Export folgt dem Namen"
                )

    def _files(self, needles: tuple[str, ...]) -> list[str]:
        """Die Dateien der Bereiche (ohne die Quelle), deren Text eine der Nadeln enthält."""
        found: list[str] = []
        for area in AREAS:
            base = self.ctx.root / area
            if not base.is_dir():
                continue
            for full in sorted(base.rglob("*.py")):
                relative = full.relative_to(self.ctx.root).as_posix()
                parts = relative.split("/")[:-1]
                if relative == self.path or any(
                    p == "__pycache__" or p.startswith(".") for p in parts
                ):
                    continue
                data = full.read_bytes().decode("utf-8", "replace")
                if any(n in data for n in needles):
                    found.append(relative)
        return found

    def _long_patches(self) -> None:
        """Ein Pfad als Text, der durch einen verschobenen Namen weiterführt
        (``"app.x.Klasse.methode"``), führt danach durch das Zielmodul."""
        moved = self._moved()
        prefix = self.src + "."
        for site in self.ctx.index.patch_sites():
            if not site.targets or any(t.status != "object" for t in site.targets):
                continue
            source = self.ctx.source(site.path)
            calls = [
                n
                for n in ast.walk(source.tree)
                if isinstance(n, ast.Call)
                and (n.lineno, n.col_offset) == (site.line, site.col)
                and n.args
            ]
            first = calls[0].args[0] if calls else None
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            head, dot, rest = first.value.removeprefix(prefix).partition(".")
            if not first.value.startswith(prefix) or not dot or head not in moved:
                continue
            module, new_name = moved[head]
            rewrite = self.ctx.rewrite(site.path)
            text = quoted(source, first, f"{module}.{new_name}.{rest}")
            rewrite.replace(first, text, "Patch-Ziel folgt dem Namen")

    def _hasattr(self) -> None:
        """``hasattr(M, "N")`` fragt danach das Zielmodul — der Auflöser zählt es nicht als
        Bezug, und ohne Umschreiben antwortete es still ``False``."""
        moved = self._moved()
        for path in self._files(("hasattr(",)):
            source = self.ctx.source(path)
            for node in ast.walk(source.tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "hasattr"
                    and len(node.args) == 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value in moved
                    and self.ctx.is_module(path, node.args[0], self.src)
                ):
                    continue
                name = str(node.args[1].value)
                module, new_name = moved[name]
                self.ctx.rewrite(path).retarget_getattr(
                    node.lineno, node.col_offset, self.src, name, module, new_name, "verschoben"
                )

    def _module_values(self) -> None:
        """Eine Stelle, die die Quelle als **Wert** liest — ``importlib.reload(M)``, ``dir(M)``,
        ``vars(M)``, ``inspect.getsource(M)``, ``M.__dict__``, ``getattr(M, name)`` mit offenem
        Namen, ``f(M)`` —, sähe nach dem Schnitt das Paket ohne die Namen (oder kein Modul mehr).
        Der Auflöser nennt so etwas nicht als Bezug. Gesucht wird jeder Ausdruck, der laut R genau
        die Quelle ist; erlaubt ist er nur als Basis eines Attributs, als Ziel eines Patches, an
        ``getattr``/``hasattr``/``setattr``/``delattr`` mit festem Namen und als Wert eines
        Alias (dessen Stellen dann ebenso geprüft werden)."""
        last = self.src.rpartition(".")[2]
        for path in self._files((last,)):
            source = self.ctx.source(path)
            sites = {(site.line, site.col) for site in self.ctx.sites(path)}
            found = self._source_expressions(path, source)
            self._effect_imports(path, source, found)
            for node in found:
                why = self._value_use(path, source, node, sites)
                if why is None:
                    continue
                self.ctx.problem(
                    f"{path}:{node.lineno}: liest die Quelle {self.src} als Wert ({why}: "
                    f"{_short_text(source, node)!r}) — nach dem Schnitt "
                    + (
                        f"ist {self.src} ein Paket ohne ihre Namen"
                        if self.cut.package
                        else f"gibt es {self.src} nicht mehr"
                    )
                    + "; vorher auf das Modul umschreiben, dessen Definitionen die Stelle meint, "
                    "oder je Zielmodul nach dem Schnitt"
                )

    def _effect_imports(self, path: str, source: Source, found: list[ast.expr]) -> None:
        """Ein Import der Quelle, über den nichts gelesen wird, steht um ihrer Wirkung willen da
        (``import app.x  # noqa: F401`` registriert Operationen): Nach dem Schnitt lüde er nur
        das Paket, die Wirkung der Definitionen fiele still weg."""
        roots: set[str] = set()
        for node in found:
            current: ast.expr = node
            while isinstance(current, ast.Attribute):
                current = current.value
            if isinstance(current, ast.Name):
                roots.add(current.id)
        for stmt in ast.walk(source.tree):
            if isinstance(stmt, ast.Import):
                hits = [a for a in stmt.names if a.name == self.src]
            elif isinstance(stmt, ast.ImportFrom):
                module = absolute_module(path, stmt)
                hits = [a for a in stmt.names if f"{module}.{a.name}" == self.src]
            else:
                continue
            for alias in hits:
                if bound_name(alias) in roots:
                    continue
                self.ctx.problem(
                    f"{path}:{stmt.lineno}: importiert {self.src} nur um der Wirkung willen "
                    "(niemand liest den Namen) — nach dem Schnitt lüde das nur das Paket; vorher "
                    "die Ziele importieren, deren Wirkung gebraucht wird, oder den Import entfernen"
                )

    def _source_expressions(self, path: str, source: Source) -> list[ast.expr]:
        """Die Ausdrücke einer Datei, die laut R genau die Quelle sind: Namen und Ketten aus
        einem Import oder einer Zuweisung, die die Quelle binden, und
        ``importlib.import_module("<Quelle>")``."""
        names: set[str] = set()
        for node in ast.walk(source.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == self.src or self.src.startswith(alias.name + "."):
                        names.add(bound_name(alias))
            elif isinstance(node, ast.ImportFrom):
                module = absolute_module(path, node)
                names.update(
                    bound_name(alias)
                    for alias in node.names
                    if f"{module}.{alias.name}" == self.src
                )
        grown = True
        while grown:
            grown = False
            for node in ast.walk(source.tree):
                if not (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id not in names
                ):
                    continue
                value = node.value
                literal = isinstance(value, ast.Call) and any(
                    isinstance(a, ast.Constant) and a.value == self.src for a in value.args
                )
                if literal or (isinstance(value, ast.Name) and value.id in names):
                    names.add(node.targets[0].id)
                    grown = True
        found: list[ast.expr] = []
        for node in ast.walk(source.tree):
            if (
                isinstance(node, ast.Call)
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == self.src
                and self.ctx.is_module(path, node, self.src)
            ):
                found.append(node)
                continue
            if not (
                isinstance(node, ast.Name) and node.id in names and isinstance(node.ctx, ast.Load)
            ):
                continue
            current: ast.expr = node
            while True:
                if self.ctx.is_module(path, current, self.src):
                    found.append(current)
                    break
                parent = source.parent(current)
                if not (isinstance(parent, ast.Attribute) and parent.value is current):
                    break
                current = parent
        return found

    def _value_use(
        self, path: str, source: Source, node: ast.expr, sites: set[tuple[int, int]]
    ) -> str | None:
        """Warum ``node`` (die Quelle) hier als Wert gelesen wird, sonst ``None``."""
        parent = source.parent(node)
        if isinstance(parent, ast.Attribute) and parent.value is node:
            return f"Attribut {parent.attr}" if parent.attr in MODULE_VALUE_ATTRIBUTES else None
        if isinstance(parent, ast.Assign) and parent.value is node:
            targets = parent.targets
            if len(targets) == 1 and isinstance(targets[0], ast.Name):
                return None  # ein Alias: seine Stellen prüft dieselbe Suche
            return "abgelegt"
        if isinstance(parent, ast.Expr) and isinstance(node, ast.Call):
            return None  # ein Import um seiner Wirkung willen: den Text prüft _stale_strings
        if isinstance(parent, ast.Call) and parent.args and parent.args[0] is node:
            if (parent.lineno, parent.col_offset) in sites:
                return None
            kinds = self.ctx.index.resolve(path, parent.func)
            named = bool(kinds) and all(
                v.kind == "ext"
                and v.ref
                in ("builtins.getattr", "builtins.hasattr", "builtins.setattr", "builtins.delattr")
                for v in kinds
            )
            if named:
                second = parent.args[1] if len(parent.args) > 1 else None
                fixed = isinstance(second, ast.Constant) and isinstance(second.value, str)
                return None if fixed else "Attributname nicht fest"
        if isinstance(parent, ast.Call):
            return f"Argument von {_short_text(source, parent.func)}"
        return type(parent).__name__ if parent is not None else "Wert"

    def _stale_strings(self) -> None:
        """Jede Zeichenkette, die die alte Datei, das alte Modul oder einen verschobenen Namen
        darunter nennt, ist umgeschrieben oder erklärt — sonst ein Fund."""
        moved = {f"{self.src}.{name}" for name in self.unit_of}
        file_name = self.path.rpartition("/")[2]
        declared = {e.value for e in self.cut.name_lists if e.path == self.path}
        for node in string_constants(self.source):
            value = str(node.value)
            if names_source(value, self.path, self.src, moved) and value not in declared:
                self.ctx.problem(
                    f"{self.path}:{node.lineno}: Zeichenkette {value!r} nennt die alte Quelle "
                    "und wandert mit ihrer Definition — in [[name_lists]] mit der Quelle als "
                    "Pfad erklären (to = [derselbe Wert], wenn sie bleibt) oder vorher umschreiben"
                )
        for relative in self._files((self.path, file_name, self.src)):
            rewrite = self.ctx.rewrites().get(relative)
            source = rewrite.source if rewrite else self.ctx.source(relative)
            gone = rewrite.removed_assignments() if rewrite else []
            for node in string_constants(source):
                value = str(node.value)
                stale = names_source(value, self.path, self.src, moved)
                if not stale or (rewrite and rewrite.covered(node)):
                    continue
                if any(_inside_statement(stmt, node) for stmt in gone):
                    continue
                self.ctx.problem(
                    f"{relative}:{node.lineno}: Zeichenkette {value!r} nennt die alte Quelle — "
                    "in [[name_lists]] (auch to = [derselbe Wert], wenn sie bleibt) oder "
                    "[[source_readers]] erklären oder vorher umschreiben"
                )


def _short_text(source: Source, node: ast.AST) -> str:
    text = " ".join(source.node_text(node).split())
    return text if len(text) <= 60 else text[:57] + "…"


def _inside_statement(stmt: ast.stmt, node: ast.AST) -> bool:
    return any(child is node for child in ast.walk(stmt))


def _reaches(graph: dict[str, set[str]], start: str, goal: str) -> bool:
    seen: set[str] = set()
    stack = [start]
    while stack:
        current = stack.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.get(current, ()))
    return False


def _docstring_text(text: str) -> str:
    """Ein Docstring als Quelltext; Zeilen über 96 Zeichen werden an Wortgrenzen umbrochen."""
    import textwrap

    escaped = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    lines = textwrap.wrap(escaped, width=96, break_long_words=False, break_on_hyphens=False)
    if len(lines) <= 1:
        return f'"""{escaped}"""\n'
    return '"""' + "\n".join(lines) + '\n"""\n'


def _import_text(path: str, stmt: ast.Import | ast.ImportFrom, kept: list[ast.alias]) -> str:
    if isinstance(stmt, ast.Import):
        parts = [a.name + (f" as {a.asname}" if a.asname else "") for a in kept]
        return f"import {', '.join(parts)}"
    module = absolute_module(path, stmt)
    parts = [a.name + (f" as {a.asname}" if a.asname else "") for a in kept]
    return f"from {module} import {', '.join(parts)}"


def _string_annotation_names(source: Source, node: ast.Constant) -> set[str]:
    parent = source.parent(node)
    annotation = (
        (isinstance(parent, ast.arg) and parent.annotation is node)
        or (isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and parent.returns is node)
        or (isinstance(parent, ast.AnnAssign) and parent.annotation is node)
    )
    if not annotation:
        return set()
    try:
        expression = ast.parse(str(node.value).strip(), mode="eval")
    except SyntaxError:
        return set()
    return {n.id for n in ast.walk(expression) if isinstance(n, ast.Name)}
