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
    path_of,
    spans,
    statement_names,
)


@dataclass
class Unit:
    """Eine Anweisung der Quelle auf Modulebene mit ihren Namen."""

    stmt: ast.stmt
    span: Span
    names: list[str]
    target: Target | None
    facts: StatementNames
    duplicate: bool = False


@dataclass
class ModulePlan:
    files: dict[str, str] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    edits: dict[str, list[Edit]] = field(default_factory=dict)


_HEAD = re.compile(r"^(\s*)(async\s+def|def|class)(\s+)([A-Za-z_][A-Za-z0-9_]*)")


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
        self._check_globals()
        self._check_identity()
        self._dependencies()
        self.ctx.raise_problems()
        self._unit_rewrites()
        files = {path_of(t.module): self._target_text(t) for t in self.cut.targets}
        if self.cut.package:
            files[path_of(self.src, package=True)] = _docstring_text(self.cut.package_docstring)
        self._references()
        self._patches()
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
            scopes = Scopes(self.source, unit.stmt, unit.span)
            homes = self._homes(unit)
            for node in ast.walk(unit.stmt):
                if not isinstance(node, ast.Name) or node.id in unit.names:
                    continue
                other = self.unit_of.get(node.id)
                if other is None or other.duplicate or not scopes.is_global(node):
                    continue
                assert other.target is not None
                if all(home == other.target.module for home in homes):
                    continue
                found.append((unit, node, other, self._import_time(unit.stmt, node)))
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
        for unit in self.units:
            scopes = Scopes(self.source, unit.stmt, unit.span)
            for node in ast.walk(unit.stmt):
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
                    names = _string_annotation_names(self.source, node)
                    touched = names & (set(renamed) | {o.names[0] for _u, _n, o, _e in self.cross})
                    if touched:
                        self.ctx.problem(
                            f"{self.path}:{node.lineno}: Annotation als Zeichenkette nennt "
                            f"{', '.join(sorted(touched))}, das umbenannt oder über ein anderes "
                            "Ziel gelesen wird — vor dem Schnitt ohne Anführung schreiben"
                        )
            if isinstance(unit.stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = unit.stmt.name
                if name in renamed:
                    self.unit_edits.append(self._head_edit(unit.stmt, renamed[name]))

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

    def _name_lists(self) -> None:
        for number, entry in enumerate(self.cut.name_lists):
            if not (self.ctx.root / entry.path).is_file():
                self.ctx.problem(f"name_lists: {entry.path} fehlt")
                continue
            rewrite = self.ctx.rewrite(entry.path)
            for node in string_constants(rewrite.source):
                if node.value != entry.value:
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
            rewrite = self.ctx.rewrite(path)
            sub = module[len(parent) + 1 :]
            rewrite.replace(first, quoted(source, first, sub), "Lazy-Export folgt dem Namen")
            if new_name != name:
                rewrite.replace(
                    second, quoted(source, second, new_name), "Lazy-Export folgt dem Namen"
                )

    def _stale_strings(self) -> None:
        """Jede Zeichenkette, die die alte Datei oder einen verschobenen Namen unter dem alten
        Modul nennt, ist umgeschrieben oder erklärt — sonst ein Fund."""
        moved = {f"{self.src}.{name}" for name in self.unit_of}
        file_name = self.path.rpartition("/")[2]
        needles = (self.path, file_name, self.src)
        files = [
            full
            for area in AREAS
            if (self.ctx.root / area).is_dir()
            for full in sorted((self.ctx.root / area).rglob("*.py"))
        ]
        for full in files:
            relative = full.relative_to(self.ctx.root).as_posix()
            parts = relative.split("/")[:-1]
            if relative == self.path or any(p == "__pycache__" or p.startswith(".") for p in parts):
                continue
            data = full.read_bytes().decode("utf-8", "replace")
            if not any(n in data for n in needles):
                continue
            rewrite = self.ctx.rewrite(relative) if relative in self.ctx.rewrites() else None
            source = rewrite.source if rewrite else self.ctx.source(relative)
            for node in string_constants(source):
                value = str(node.value)
                stale = (
                    self.path in value
                    or value == file_name
                    or value.endswith("/" + file_name)
                    or any(value == m or value.startswith(m + ".") for m in moved)
                )
                if stale and not (rewrite and rewrite.covered(node)):
                    self.ctx.problem(
                        f"{relative}:{node.lineno}: Zeichenkette {value!r} nennt die alte Quelle — "
                        "in [[name_lists]] oder [[source_readers]] erklären oder vorher umschreiben"
                    )


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
