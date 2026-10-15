"""Modus ``copies`` des Verschiebewerkzeugs: Kopfkopien gepatchter Namen werden Modulzugriffe.

Plan Schritt 0, 2.7 Punkt 7, und Entscheidung E1: Für jedes erklärte Original ``(M, N)``
(``[[bindings]]``) liefert der Auflöser jede Kopfkopie in ``app/`` und ``tools/`` samt der Kette
über Rück- und Lazy-Exporte (``Index.head_copies``). Jede wird umgestellt:

* im Halter ``from M import N as b`` → ``from P import m`` und jedes Lesen von ``b`` auf
  Modulebene → ``m.N`` (``b = M.N`` als Zuweisung fällt weg, gelesen wird ebenso ``m.N``);
* außerhalb jeder Bezug auf die Kopie (``from H import b``, ``H.b``, ``getattr(H, "b")``) → auf
  den Leseweg;
* jede Patch-Stelle auf die Kopie → auf das **Original**. Ein solcher Patch erreicht danach
  absichtlich jeden Leser des Originals (Plan 4); der Beweis weist je Patch-Stelle aus, wen er
  vorher und nachher erreicht.

**Leseweg** ist das erste Glied der Kette, das keine Kopie ist: das Original selbst oder ein
träges Paket davor (``app.core.lazy``) — das liest bei jedem Zugriff beim Ursprung, und sein
Untermodul ist unter demselben Namen verdeckt. Patches zielen immer auf das Original: Ein
Attribut, das jemand auf ein träges Paket setzt, liest niemand.

Abgewiesen wird vor dem Schreiben, jeweils mit Ausweg: ein Original, das selbst eine Kopie ist;
eine Kopie, die auf Modulebene mehrfach gebunden, über ``global`` geschrieben oder von außen
gesetzt wird; ein Leseweg hinter einem gleichnamigen trägen Export; eine gefaltete Patch-Stelle;
ein Lesen über einen Namen, den eine Funktion verdeckt; ``__all__`` mit der Kopie; ein Lazy-Export
auf die Kopie, wenn das Original nicht im selben Paket liegt; eine Zeichenkette, die die Kopie
nennt, ohne Patch-Stelle zu sein.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass

from tools.code_index import HeadCopy, Index
from tools.move_compare import FileScopes, TopLevel, string_constants
from tools.move_cut import Cut
from tools.move_edits import Edit
from tools.move_refs import (
    AlreadyAppliedError,
    Context,
    FileRewrite,
    import_text,
    lazy_table,
    quoted,
)
from tools.move_source import AREAS, Source, bound_name, import_binders, path_of

RULE_HOLDER = "Kopie wird Modulzugriff"
RULE_OUTSIDE = "Bezug auf die Kopie folgt dem Leseweg"
RULE_PATCH = "Patch auf die Kopie zielt aufs Original"

#: Aufrufe, deren zweites Argument ein Attributname des ersten ist.
ATTRIBUTE_CALLS = frozenset({"getattr", "hasattr", "setattr", "delattr"})


@dataclass(frozen=True)
class Copy:
    """Eine Kopfkopie einer erklärten Familie: wo sie steht (``head``), worüber gelesen wird
    (``access``) und wohin ein Patch auf sie danach zielt (``origin``)."""

    head: HeadCopy
    access: tuple[str, str]
    origin: tuple[str, str]

    @property
    def key(self) -> tuple[str, str]:
        return self.head.holder, self.head.bound


def families(
    index: Index, cut: Cut, package: Callable[[str], Source | None]
) -> tuple[dict[tuple[str, str], Copy], list[str]]:
    """Die Kopfkopien der erklärten Originale je ``(Halter, Name)`` und die Funde in den
    Erklärungen. Planer und Beweis leiten die Familien gleich aus dem Auflöser ab; ``package``
    liefert das ``__init__`` eines Pakets (für einen verdeckten Leseweg, :func:`route`)."""
    problems: list[str] = []
    heads = index.head_copies()
    by_key: dict[tuple[str, str], HeadCopy] = {}
    for head in heads:
        key = (head.holder, head.bound)
        if key in by_key:
            problems.append(
                f"{head.path}:{head.line}: {head.bound} ist zweimal eine Kopfkopie — vor dem "
                "Schnitt auf eine Bindung bringen"
            )
        by_key[key] = head
    selected = {(b.module, b.name) for b in cut.bindings}
    for binding in cut.bindings:
        key = (binding.module, binding.name)
        if not index.exists(*key):
            problems.append(
                f"bindings: {binding.module}.{binding.name} gibt es nicht — Original prüfen"
            )
        elif key in by_key:
            origin = by_key[key].chain[-1]
            problems.append(
                f"bindings: {binding.module}.{binding.name} ist selbst eine Kopie von "
                f"{origin[0]}.{origin[1]} — das Original nennen"
            )
    copies: dict[tuple[str, str], Copy] = {}
    for head in heads:
        origin = head.chain[-1]
        if origin not in selected:
            continue
        access = route(next(link for link in head.chain if link not in by_key), package)
        copies[(head.holder, head.bound)] = Copy(head, access, origin)
    return copies, problems


def route(access: tuple[str, str], package: Callable[[str], Source | None]) -> tuple[str, str]:
    """Liegt das Modul des Lesewegs hinter einem gleichnamigen trägen Export seines Pakets
    (``app.core.scene.evaluate``), führt der Leseweg über das Paket, wenn es den Namen träge
    exportiert: ``scene.evaluate`` liest bei jedem Zugriff ``app.core.scene.evaluate.evaluate``."""
    module, name = access
    parent, _, last = module.rpartition(".")
    source = package(parent) if parent else None
    if source is None:
        return access
    table = {k: (a.value, b.value) for k, (a, b) in lazy_table(source).items()}
    if last not in table:
        return access
    for key, entry in sorted(table.items()):
        if entry == (last, name):
            return parent, key
    return access


def list_copies(index: Index) -> list[tuple[str, str]]:
    """Die Originale, deren Kopfkopien W2 c) beanstandet — der Vorschlag für ``bindings``."""
    flagged = {(f.path, f.line, f.name) for f in index.patch_findings()["c"]}
    found = {
        copy.chain[-1]
        for copy in index.head_copies()
        if (copy.path, copy.line, copy.bound) in flagged
    }
    return sorted(found)


def bindings_toml(originals: list[tuple[str, str]]) -> str:
    """Die Liste ``[[bindings]]`` eines Zuschnitts im Modus ``copies``."""
    blocks = [f'[[bindings]]\nmodule = "{m}"\nname = "{n}"\n' for m, n in originals]
    return "\n".join(blocks)


class CopiesPlanner:
    """Plant die Umstellung der erklärten Kopienfamilien; Funde sammelt ``ctx``."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.cut = ctx.cut
        self.copies, problems = families(ctx.index, ctx.cut, self._package)
        for problem in problems:
            ctx.problem(problem)
        self.statements: set[tuple[str, int]] = {
            (c.head.path, c.head.line) for c in self.copies.values()
        }

    def _package(self, package: str) -> Source | None:
        path = path_of(package, package=True)
        return self.ctx.source(path) if (self.ctx.root / path).is_file() else None

    def plan(self) -> dict[str, list[Edit]]:
        self.ctx.raise_problems()
        if not self.copies:
            raise AlreadyAppliedError(
                "keine Kopfkopie der erklärten Originale mehr — der Schnitt ist angewandt; "
                "nichts zu tun"
            )
        reached = {c.origin for c in self.copies.values()}
        for binding in self.cut.bindings:
            if (binding.module, binding.name) not in reached:
                self.ctx.problem(
                    f"bindings: {binding.module}.{binding.name} hat keine Kopfkopie — Erklärung "
                    "streichen"
                )
        for copy in self.copies.values():
            if self.ctx.shadowed(copy.access[0]):
                self.ctx.problem(
                    f"{copy.head.path}:{copy.head.line}: der Leseweg {copy.access[0]} liegt hinter "
                    "dem gleichnamigen trägen Export seines Pakets — vor dem Schnitt über das "
                    "Paket importieren (der träge Export liest beim Original)"
                )
        self.ctx.raise_problems()
        by_path: dict[str, list[Copy]] = {}
        for copy in sorted(self.copies.values(), key=lambda c: (c.head.path, c.head.line)):
            by_path.setdefault(copy.head.path, []).append(copy)
        for path, group in sorted(by_path.items()):
            self._holder(path, group)
        self._outside()
        self._patches()
        self._lazy_exports()
        self._stale_strings()
        self.ctx.raise_problems()
        edits: dict[str, list[Edit]] = {}
        for path, rewrite in sorted(self.ctx.rewrites().items()):
            found = rewrite.finish()
            if found:
                edits[path] = found
        self.ctx.raise_problems()
        return edits

    # ------------------------------------------------------------------ im Halter

    def _holder(self, path: str, group: list[Copy]) -> None:
        rewrite = self.ctx.rewrite(path)
        source = rewrite.source
        top = TopLevel(source)
        scopes = FileScopes(source)
        converted = {c.head.bound for c in group}
        sites: dict[str, list[ast.Name]] = {}
        anchors: dict[str, ast.Import | ast.ImportFrom] = {}
        for copy in group:
            bound = copy.head.bound
            count = len(top.units.get(bound, [])) + len(top.imports.get(bound, []))
            stmt = self._statement(source, copy)
            if count != 1 or stmt is None:
                self.ctx.problem(
                    f"{path}:{copy.head.line}: {bound} wird auf Modulebene {count}-mal gebunden — "
                    "vor dem Schnitt auf eine Bindung bringen"
                )
                continue
            loads: list[ast.Name] = []
            for node in scopes.global_names(bound):
                if isinstance(node.ctx, ast.Load):
                    loads.append(node)
                    alias = _module_alias(source, node)
                    if alias is not None:
                        self.ctx.problem(
                            f"{path}:{node.lineno}: {alias} = {bound} bindet die Kopie beim "
                            f"Import unter neuem Namen — danach wäre {alias} eine Kopfkopie des "
                            f"Originals {copy.origin[0]}.{copy.origin[1]}; vor dem Schnitt "
                            f"entscheiden: {alias} liest das Original zur Aufrufzeit oder ist "
                            "eine eigene Zahl"
                        )
                elif not _inside(stmt, node):
                    self.ctx.problem(
                        f"{path}:{node.lineno}: {bound} wird geschrieben (Zuweisung, global, del) "
                        "— die Kopie ist dann ein Zustand; vor dem Schnitt auflösen"
                    )
            sites[bound] = loads
            if isinstance(stmt, ast.ImportFrom):
                number = next(n for n, a in enumerate(stmt.names) if bound_name(a) == bound)
                rewrite.plan(stmt).drop.add(number)
                rewrite.plan(stmt).rules.append(RULE_HOLDER)
                anchors.setdefault(copy.access[0], stmt)
            else:
                rewrite.remove_statement(stmt, RULE_HOLDER)
                self._watch_assignment(rewrite, stmt)
            self._all_entries(rewrite, bound)
        aliases: dict[str, str] = {}
        for module in sorted({c.access[0] for c in group if c.head.bound in sites}):
            nodes = [n for c in group if c.access[0] == module for n in sites.get(c.head.bound, [])]
            existing = self._existing(top, scopes, module, nodes)
            if existing is not None:
                aliases[module] = existing
                continue
            alias = self._fresh(rewrite, scopes, module, nodes, converted)
            anchor = anchors.get(module) or rewrite.head_anchor()
            if alias is None:
                continue
            if anchor is None:
                self.ctx.problem(
                    f"{path}: kein Importkopf auf Modulebene für {module} — vor dem Schnitt "
                    "einen Import an den Kopf stellen"
                )
                continue
            aliases[module] = alias
            rewrite.add_import(anchor, import_text(module, alias), RULE_HOLDER)
        for copy in group:
            bound = copy.head.bound
            alias = aliases.get(copy.access[0])
            if alias is None or bound not in sites:
                continue
            text = f"{alias}.{copy.access[1]}"
            for node in sites[bound]:
                rewrite.replace(node, text, RULE_HOLDER)
            self._annotations(rewrite, scopes, bound, text)

    def _statement(self, source: Source, copy: Copy) -> ast.ImportFrom | ast.Assign | None:
        """Die Anweisung der Modulebene, die die Kopie bindet."""
        for node in ast.walk(source.tree):
            if getattr(node, "lineno", None) != copy.head.line:
                continue
            if (
                copy.head.kind == "from"
                and isinstance(node, ast.ImportFrom)
                and any(bound_name(a) == copy.head.bound for a in node.names)
            ):
                return node
            if (
                copy.head.kind == "assign"
                and isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == copy.head.bound
            ):
                return node
        return None

    def _watch_assignment(self, rewrite: FileRewrite, stmt: ast.Assign) -> None:
        """``b = m.N``: Liest danach niemand mehr ``m``, fällt sein Import weg."""
        value = stmt.value
        if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name):
            base = value.value
            values = self.ctx.index.resolve(rewrite.path, base)
            modules = {v.ref for v in values if v.kind == "module"}
            if len(modules) == 1:
                binders = import_binders(rewrite.source, base.id, base)
                rewrite.watch_import(binders, base.id, modules.pop())

    def _existing(
        self, top: TopLevel, scopes: FileScopes, module: str, nodes: list[ast.Name]
    ) -> str | None:
        """Ein Import der Modulebene, der ``module`` schon bindet und überall sichtbar ist."""
        for name, bindings in sorted(top.imports.items()):
            if (
                any(b.checking for b in bindings)
                or top.binding_module(name, self.ctx.index) != module
            ):
                continue
            if all(scopes.is_global(node, name) for node in nodes):
                return name
        return None

    def _fresh(
        self,
        rewrite: FileRewrite,
        scopes: FileScopes,
        module: str,
        nodes: list[ast.Name],
        converted: set[str],
    ) -> str | None:
        """Ein neuer Name für ``module``: erklärt in ``aliases``, sonst der letzte Teil, sonst
        ``<vorletzter>_<letzter>``. Frei ist er, wenn die Datei ihn nicht kennt — oder wenn er
        eine Kopie dieser Datei war, die jetzt wegfällt (``from app.geom import boolean`` statt
        der Kopie ``boolean``)."""
        declared = [
            a.name for a in self.cut.aliases if a.path == rewrite.path and a.module == module
        ]
        parts = module.split(".")
        candidates = declared or [parts[-1], "_".join(parts[-2:]), "_".join(parts[-3:])]
        for name in candidates:
            taken = name in rewrite.identifiers and name not in converted
            if taken or name in rewrite.chosen.values():
                continue
            hidden = [n for n in nodes if not scopes.is_global(n, name)]
            if hidden:
                self.ctx.problem(
                    f"{rewrite.path}:{hidden[0].lineno}: dort verdeckt ein lokaler Name {name!r} "
                    f"das Modul {module} — in [[aliases]] einen anderen Namen erklären"
                )
                return None
            rewrite.chosen[module] = name
            return name
        self.ctx.problem(
            f"{rewrite.path}: kein freier Name für {module} (versucht {candidates}) — in "
            "[[aliases]] einen Namen erklären"
        )
        return None

    def _annotations(self, rewrite: FileRewrite, scopes: FileScopes, bound: str, text: str) -> None:
        """Eine Annotation als Zeichenkette, die die Kopie nennt, nennt danach ``m.N``."""
        for node in string_constants(rewrite.source):
            if not _is_annotation(rewrite.source, node):
                continue
            new = _annotation_text(rewrite.source, node, bound, text)
            if new is None:
                if bound in _string_names(str(node.value)):
                    self.ctx.problem(
                        f"{rewrite.path}:{node.lineno}: Annotation als Zeichenkette nennt die "
                        f"Kopie {bound} in einer Form, die sich nicht umschreiben lässt — vor dem "
                        "Schnitt ohne Anführung schreiben"
                    )
                continue
            if new != rewrite.source.node_text(node):
                rewrite.replace(node, new, RULE_HOLDER)

    def _all_entries(self, rewrite: FileRewrite, bound: str) -> None:
        for stmt in rewrite.source.tree.body:
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                continue
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                continue
            if any(isinstance(n, ast.Constant) and n.value == bound for n in ast.walk(stmt)):
                self.ctx.problem(
                    f"{rewrite.path}:{stmt.lineno}: die Kopie {bound} steht in __all__ — vor dem "
                    "Schnitt entfernen"
                )

    # ------------------------------------------------------------------ außerhalb

    def _outside(self) -> None:
        for (holder, bound), copy in sorted(self.copies.items()):
            module, name = copy.access
            for ref in self.ctx.index.references(holder, bound):
                if ref.kind in ("patch", "import", "import_module"):
                    continue
                if ref.kind == "from" and (ref.path, ref.line) in self.statements:
                    continue  # selbst eine Kopfkopie dieser Familie: _holder stellt sie um
                rewrite = self.ctx.rewrite(ref.path)
                where = (ref.line, ref.col, holder, bound, module, name, RULE_OUTSIDE)
                if ref.kind == "from":
                    rewrite.rebind_from(*where)
                elif ref.kind == "attribute":
                    if not rewrite.retarget_attribute(*where):
                        self.ctx.problem(
                            f"{ref.path}:{ref.line}: Zugriff auf die Kopie {holder}.{bound} nicht "
                            "über das Modul geschrieben — vor dem Schnitt als Modulzugriff "
                            "schreiben"
                        )
                elif ref.kind in ("store", "delete"):
                    self.ctx.problem(
                        f"{ref.path}:{ref.line}: setzt oder löscht die Kopie {holder}.{bound} — "
                        "danach träfe das das Original für jeden Leser und ohne Rücknahme; vor "
                        "dem Schnitt mit monkeypatch schreiben"
                    )
                elif ref.kind == "getattr":
                    rewrite.retarget_getattr(*where)
                else:
                    self.ctx.problem(
                        f"{ref.path}:{ref.line}: Bezug auf die Kopie {holder}.{bound} über "
                        f"{ref.kind} — vor dem Schnitt als Import oder Attribut schreiben"
                    )

    def _patches(self) -> None:
        for site in self.ctx.index.patch_sites():
            loaded = [
                t
                for t in site.targets
                if t.status == "loaded" and (t.module, t.name or "") in self.copies
            ]
            if loaded:
                self.ctx.problem(
                    f"{site.path}:{site.line}: Patch auf die Kopie {loaded[0].module}."
                    f"{loaded[0].name} in einem über den Pfad geladenen Modul — danach fehlt der "
                    "Name dort; vor dem Schnitt das Original patchen"
                )
                continue
            hits = [
                t
                for t in site.targets
                if t.status == "module" and t.name is not None and (t.module, t.name) in self.copies
            ]
            if not hits:
                continue
            if len(site.targets) != 1:
                self.ctx.problem(
                    f"{site.path}:{site.line}: Patch-Stelle mit gefaltetem Ziel ({site.text}) "
                    "trifft eine Kopie — vor dem Schnitt je Ziel eine Stelle mit festem Text "
                    "schreiben"
                )
                continue
            copy = self.copies[(hits[0].module, hits[0].name or "")]
            module, name = copy.origin
            self.ctx.rewrite(site.path).retarget_patch(
                site.line, site.col, site.form, copy.head.holder, module, name, RULE_PATCH
            )

    def _lazy_exports(self) -> None:
        """Ein träger Export auf eine Kopie zeigt danach auf das Original, wenn es im selben
        Paket liegt."""
        seen: set[str] = set()
        for copy in self.copies.values():
            parent = copy.head.holder.rpartition(".")[0]
            path = path_of(parent, package=True) if parent else ""
            if not path or path in seen or not (self.ctx.root / path).is_file():
                continue
            seen.add(path)
            source = self.ctx.source(path)
            for (holder, bound), other in sorted(self.copies.items()):
                if not holder.startswith(parent + "."):
                    continue
                sub = holder[len(parent) + 1 :]
                for first, second in lazy_table(source).values():
                    if first.value != sub or second.value != bound:
                        continue
                    origin, name = other.origin
                    if not origin.startswith(parent + "."):
                        self.ctx.problem(
                            f"{path}:{first.lineno}: der träge Export zeigt auf die Kopie "
                            f"{holder}.{bound}, das Original {origin} liegt außerhalb von "
                            f"{parent} — vor dem Schnitt den Export auf das Original stellen"
                        )
                        continue
                    rewrite = self.ctx.rewrite(path)
                    rule = "Lazy-Export folgt dem Original"
                    rewrite.replace(first, quoted(source, first, origin[len(parent) + 1 :]), rule)
                    if name != bound:
                        rewrite.replace(second, quoted(source, second, name), rule)

    def _stale_strings(self) -> None:
        """Jede Zeichenkette ``"H.b"`` einer Kopie ist eine umgestellte Patch-Stelle, und jeder
        Attributname ``"b"`` an ``getattr``/``hasattr``/``setattr``/``delattr`` auf den Halter ist
        umgestellt — sonst ein Fund."""
        dotted_names = {f"{h}.{b}" for h, b in self.copies}
        bounds = {b for _h, b in self.copies}
        for area in AREAS:
            base = self.ctx.root / area
            if not base.is_dir():
                continue
            for full in sorted(base.rglob("*.py")):
                relative = full.relative_to(self.ctx.root).as_posix()
                if any(p == "__pycache__" or p.startswith(".") for p in relative.split("/")[:-1]):
                    continue
                data = full.read_bytes().decode("utf-8", "replace")
                hit_dotted = any(d in data for d in dotted_names)
                hit_attr = "attr(" in data and any(b in data for b in bounds)
                if not hit_dotted and not hit_attr:
                    continue
                rewrite = self.ctx.rewrites().get(relative)
                source = rewrite.source if rewrite else self.ctx.source(relative)
                if hit_dotted:
                    for node in string_constants(source):
                        value = str(node.value)
                        stale = any(value == d or value.startswith(d + ".") for d in dotted_names)
                        if stale and not (rewrite and rewrite.covered(node)):
                            self.ctx.problem(
                                f"{relative}:{node.lineno}: Zeichenkette {value!r} nennt eine "
                                "Kopie — vor dem Schnitt umschreiben (Patch auf das Original)"
                            )
                if hit_attr:
                    self._attribute_names(relative, source, rewrite)

    def _attribute_names(self, path: str, source: Source, rewrite: FileRewrite | None) -> None:
        for node in ast.walk(source.tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ATTRIBUTE_CALLS
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                continue
            first = node.args[0]
            for holder, bound in self.copies:
                if node.args[1].value != bound or (rewrite is not None and rewrite.covered(first)):
                    continue
                if self.ctx.is_module(path, first, holder):
                    self.ctx.problem(
                        f"{path}:{node.lineno}: {node.func.id}({source.node_text(first)}, "
                        f"{bound!r}) fragt nach der Kopie — vor dem Schnitt als Zugriff auf das "
                        "Original schreiben"
                    )


# ------------------------------------------------------------------------------ Hilfen


def _inside(stmt: ast.stmt, node: ast.AST) -> bool:
    return any(child is node for child in ast.walk(stmt))


def _module_alias(source: Source, node: ast.Name) -> str | None:
    """``X = b`` oder ``X: T = b`` außerhalb jeder Funktion: der neue Name ``X``."""
    parent = source.parent(node)
    if isinstance(parent, ast.Assign) and parent.value is node and len(parent.targets) == 1:
        target: ast.expr | None = parent.targets[0]
    elif isinstance(parent, ast.AnnAssign) and parent.value is node:
        target = parent.target
    else:
        return None
    if not isinstance(target, ast.Name):
        return None
    if any(
        isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))
        for outer in source.ancestors(parent)
    ):
        return None
    return target.id


def _is_annotation(source: Source, node: ast.AST) -> bool:
    parent = source.parent(node)
    if isinstance(parent, ast.arg):
        return parent.annotation is node
    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return parent.returns is node
    if isinstance(parent, ast.AnnAssign):
        return parent.annotation is node
    return False


def _string_names(text: str) -> set[str]:
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return set()
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _annotation_text(source: Source, node: ast.Constant, bound: str, text: str) -> str | None:
    """Der Quelltext der Annotation ``node`` mit ``text`` statt jedes Namens ``bound`` — nur
    für eine schlichte Zeichenkette ohne Escapes und Präfix (sonst ``None``)."""
    raw = source.node_text(node)
    value = str(node.value)
    quote = raw[:1]
    if quote not in ("'", '"') or raw[-1:] != quote or raw[1:-1] != value or raw[:3] == quote * 3:
        return None
    try:
        tree = ast.parse(value, mode="eval")
    except SyntaxError:
        return None
    data = value.encode("utf-8")
    spots = sorted(
        (n.col_offset, n.end_col_offset or n.col_offset)
        for n in ast.walk(tree)
        if isinstance(n, ast.Name) and n.id == bound and getattr(n, "lineno", 1) == 1
    )
    if not spots:
        return raw
    out = b""
    cursor = 0
    for start, end in spots:
        out += data[cursor:start] + text.encode("utf-8")
        cursor = end
    out += data[cursor:]
    return quote + out.decode("utf-8") + quote
