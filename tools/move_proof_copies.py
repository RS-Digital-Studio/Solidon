"""Der Beweis eines Schnitts im Modus ``copies`` (``tools/move_proof.py``).

Keine Definition wandert; jede geänderte Datei wird als Ganzes gegen ihre alte Fassung verglichen.
Erklärt sind genau diese Abweichungen, alle aus dem Zuschnitt und dem Auflöser des **alten**
Baums abgeleitet, nicht aus der Tabelle des Planers:

* im Halter fällt der Import- oder Zuweisungseintrag der Kopie weg, ein Import des Lesewegs kommt
  dazu, und jedes Lesen der Kopie auf Modulebene ist ``m.N`` mit ``m`` als Bindung des Lesewegs
  (auch in einer Annotation als Zeichenkette);
* außerhalb meint ein Bezug auf die Kopie danach den Leseweg (``from H import b`` → ``from M
  import N as b``, ``H.b`` → ``m.N``), und ein Import des Halters, den niemand mehr liest, fällt
  weg;
* jede Patch-Stelle auf eine Kopie zielt auf das Original.

**Lesermengen je Familie** (Plan 4, A3 der Vorbereitung): Nach dem Schnitt erreicht das Original
genau seine alten Leser und die aller umgestellten Kopien derselben Familie — je Familie
verglichen, nicht als Gesamtmenge, damit vertauschte Leser zweier Familien auffallen. Je
Patch-Stelle nennt das Protokoll, wen sie vorher und nachher erreicht. Danach gibt es keine
Kopfkopie der erklärten Originale mehr.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from tools.code_index import Index, PatchSite
from tools.move_compare import (
    FileScopes,
    ImportBinding,
    MappedValues,
    ReaderComparison,
    TopLevel,
    _is_annotation,
    _text,
)
from tools.move_copies import Copy, families
from tools.move_cut import Cut
from tools.move_source import Source, path_of
from tools.move_trees import Mapping, Proof, Trees


class CopiesMapping(Mapping):
    """Bezüge auf eine Kopie meinen danach den Leseweg, Patches das Original; die Lesermenge des
    Originals ist danach die Vereinigung über die Familie."""

    def __init__(self, copies: dict[tuple[str, str], Copy]) -> None:
        self.copies = copies
        self.origins = {c.origin for c in copies.values()}

    def ref(self, module: str, name: str) -> tuple[str, str]:
        copy = self.copies.get((module, name))
        return copy.access if copy is not None else (module, name)

    def reach_key(self, module: str, name: str) -> tuple[str, str]:
        copy = self.copies.get((module, name))
        return copy.origin if copy is not None else (module, name)

    def target(self, site: PatchSite, number: int) -> tuple[str, str, str | None]:
        target = site.targets[number]
        if target.status == "module" and target.name is not None:
            copy = self.copies.get((target.module, target.name))
            if copy is not None:
                return "module", copy.origin[0], copy.origin[1]
        return target.status, target.module, target.name

    def members(self, origin: tuple[str, str]) -> list[tuple[str, str]]:
        """Das Original und jede Kopie seiner Familie."""
        return [origin, *sorted(k for k, c in self.copies.items() if c.origin == origin)]

    def expected_readers(self, trees: Trees, key: tuple[str, str]) -> set[str] | None:
        origin = self.reach_key(*key)
        if origin not in self.origins:
            return None
        found: set[str] = set()
        for member in self.members(origin):
            found |= _readers(trees.old_index, member)
        return found

    def keys(self) -> Iterator[tuple[str, str]]:
        yield from sorted(self.copies)
        yield from sorted(self.origins)


class CopiesProof:
    """Der Beweis eines Schnitts im Modus ``copies``."""

    def __init__(self, proof: Proof, trees: Trees, cut: Cut) -> None:
        self.proof = proof
        self.trees = trees
        self.cut = cut
        self.copies, problems = families(trees.old_index, cut, self._package)
        for problem in problems:
            proof.error(problem)
        self.mapping = CopiesMapping(self.copies)
        self.values = MappedValues(self.mapping.ref)
        self.holders = {c.head.holder for c in self.copies.values()}
        self.modules = {c.access[0] for c in self.copies.values()} | {
            c.origin[0] for c in self.copies.values()
        }

    def _package(self, package: str) -> Source | None:
        path = path_of(package, package=True)
        return self.trees.old(path) if path in self.trees.old_files else None

    def run(self) -> Mapping:
        if not self.copies:
            self.proof.error("keine Kopfkopie der erklärten Originale im alten Baum")
            return self.mapping
        for path in self.trees.added:
            self.proof.error(f"{path}: neue Datei — der Modus copies legt keine an")
        for path in self.trees.removed:
            self.proof.error(f"{path}: entfernt — der Modus copies entfernt keine Datei")
        for copy in sorted(self.copies.values(), key=lambda c: (c.head.path, c.head.line)):
            self.proof.counts["copies"] += 1
            head = copy.head
            self.proof.note(
                f"Kopie {head.holder}.{head.bound} ({head.path}:{head.line}, {head.kind}) → "
                f"liest {copy.access[0]}.{copy.access[1]}; Patches → "
                f"{copy.origin[0]}.{copy.origin[1]}"
            )
        for head in self.trees.new_index.head_copies():
            if head.chain[-1] in self.mapping.origins:
                self.proof.error(
                    f"{head.path}:{head.line}: Kopfkopie {head.bound} von "
                    f"{head.chain[-1][0]}.{head.chain[-1][1]} besteht noch"
                )
        for path in self.trees.changed:
            if path.endswith(".py"):
                self._reader(path)
        self._patch_reach()
        return self.mapping

    def _reader(self, path: str) -> None:
        comparison = CopiesReaderComparison(self, path)
        comparison.run()
        for error in comparison.errors:
            self.proof.error(error)
        self.proof.counts["changed_files"] += 1
        self.proof.counts["references"] += len(comparison.accepted)
        if not comparison.accepted and not comparison.import_changes:
            self.proof.error(f"{path}: geändert ohne Bezug zum Schnitt")
        self.proof.note(
            f"Datei {path}: {len(comparison.accepted)} Bezüge umgestellt"
            + (f" ({'; '.join(comparison.accepted)})" if comparison.accepted else "")
            + (
                f"; Importe: {'; '.join(comparison.import_changes)}"
                if comparison.import_changes
                else ""
            )
        )

    def _patch_reach(self) -> None:
        """Je Patch-Stelle, die heute eine Kopie trifft: wen sie vorher und nachher erreicht."""
        for site in self.trees.old_index.patch_sites():
            for target in site.targets:
                key = (target.module, target.name or "")
                copy = self.copies.get(key)
                if target.status != "module" or copy is None:
                    continue
                before = _readers(self.trees.old_index, key)
                after = _readers(self.trees.new_index, copy.origin)
                self.proof.counts["patches_retargeted"] += 1
                added = sorted(after - before)
                self.proof.note(
                    f"Patch {site.path}:{site.line} auf {key[0]}.{key[1]} → "
                    f"{copy.origin[0]}.{copy.origin[1]}: erreicht vorher {len(before)}, nachher "
                    f"{len(after)}"
                    + (f", dazu {', '.join(added)}" if added else "")
                    + (f", fort {', '.join(sorted(before - after))}" if before - after else "")
                )


class CopiesReaderComparison(ReaderComparison):
    """Eine geänderte Datei im Modus ``copies``: Halter, Leser einer Kopie oder Test."""

    def __init__(self, owner: CopiesProof, path: str) -> None:
        super().__init__(owner.trees, path, owner.mapping, owner.values)
        self.owner = owner
        self.index_old = owner.trees.old_index
        self.index_new = owner.trees.new_index
        self.local = {c.head.bound: c for c in owner.copies.values() if c.head.path == path}
        self.assign_lines = {c.head.line for c in self.local.values() if c.head.kind == "assign"}
        self.old_top = TopLevel(self.old)
        self.new_top = TopLevel(self.new)
        self.old_scopes = FileScopes(self.old) if self.local else None
        self.new_scopes = FileScopes(self.new) if self.local else None

    # ---- Anweisungen

    def blocks(
        self, owner: ast.AST, old: list[ast.stmt], new: list[ast.stmt]
    ) -> tuple[list[ast.stmt | list[ast.stmt]], list[ast.stmt | list[ast.stmt]]]:
        kept: list[ast.stmt] = []
        for stmt in old:
            if (
                isinstance(stmt, ast.Assign)
                and stmt.lineno in self.assign_lines
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id in self.local
            ):
                self.changed.add(stmt.targets[0].id)
                self.import_changes.append(f"entfällt Kopie {_text(self.old, stmt)}")
                continue
            kept.append(stmt)
        return super().blocks(owner, kept, new)

    # ---- Bezüge

    def special(self, old: ast.AST, new: ast.AST) -> bool:
        if (
            self.local
            and isinstance(old, ast.Name)
            and isinstance(new, ast.Attribute)
            and old.id in self.local
        ):
            return self._converted(old, new)
        if (
            self.local
            and isinstance(old, ast.Constant)
            and isinstance(new, ast.Constant)
            and isinstance(old.value, str)
            and isinstance(new.value, str)
            and old.value != new.value
            and _is_annotation(self.old.parent(old), old)
        ):
            return self._annotation(old, new)
        return super().special(old, new)

    def _converted(self, old: ast.Name, new: ast.Attribute) -> bool:
        """Ein Lesen der Kopie im Halter ist ``m.N`` über den Leseweg."""
        assert self.old_scopes is not None and self.new_scopes is not None
        copy = self.local[old.id]
        if not self.old_scopes.is_global(old):
            self.fail(old, new, f"{old.id} ist hier lokal, nicht die Kopie")
            return True
        module, name = copy.access
        base = new.value
        if (
            new.attr == name
            and isinstance(base, ast.Name)
            and self.new_scopes.is_global(base)
            and self._binds(base.id) == module
        ):
            self.accept(f"{old.id} → {_text(self.new, new)}")
        else:
            self.fail(old, new, f"die Kopie {old.id} liest danach nicht {module}.{name}")
        return True

    def _binds(self, name: str) -> str | None:
        """Das Modul, das ``name`` in der neuen Datei zur Laufzeit bindet."""
        if any(b.checking for b in self.new_top.imports.get(name, [])):
            return None
        return self.new_top.binding_module(name, self.index_new)

    def _annotation(self, old: ast.Constant, new: ast.Constant) -> bool:
        """``"b"`` in einer Annotation ist danach ``"m.N"``: Ersetzt man in der neuen Fassung
        jedes ``m.N`` des Lesewegs zurück durch die Kopie, entsteht die alte."""
        try:
            before = ast.parse(str(old.value), mode="eval")
            after = ast.parse(str(new.value), mode="eval")
        except SyntaxError:
            self.fail(old, new, "Annotation als Zeichenkette nicht lesbar")
            return True
        back = _Back(self, {c.access: bound for bound, c in self.local.items()}).visit(after)
        if ast.dump(back) == ast.dump(before):
            self.accept(f"Annotation {old.value!r} → {new.value!r}")
        else:
            self.fail(old, new, "Annotation als Zeichenkette anders geändert als erklärt")
        return True

    # ---- Importe

    def allowed_removal(self, binding: ImportBinding) -> bool:
        copy = self.local.get(binding.bound)
        if (
            copy is not None
            and binding.form == "from"
            and (binding.module, binding.name) == (copy.head.module, copy.head.name)
        ):
            return True
        module = _bound_module(binding, self.index_old)
        assigned = {c.head.module for c in self.local.values() if c.head.kind == "assign"}
        return module is not None and (module in self.owner.holders or module in assigned)

    def allowed_module_alias(self, binding: ImportBinding) -> bool:
        module = _bound_module(binding, self.index_new)
        return module is not None and module in self.owner.modules

    def allowed_rebinding(self, previous: list[ImportBinding], binding: ImportBinding) -> bool:
        for old in previous:
            copy = self.owner.copies.get((old.module, old.name)) if old.form == "from" else None
            if copy is not None and (binding.form, binding.module, binding.name) == (
                "from",
                *copy.access,
            ):
                return True
            local = self.local.get(old.bound)
            if (
                local is not None
                and old.form == "from"
                and (old.module, old.name) == (local.head.module, local.head.name)
                and _bound_module(binding, self.index_new) == local.access[0]
            ):
                return True
        return False

    def removable_module(self, module: str) -> bool:
        return module in self.owner.holders


class _Back(ast.NodeTransformer):
    """Ersetzt ``m.N`` des Lesewegs zurück durch den Namen der Kopie."""

    def __init__(self, owner: CopiesReaderComparison, names: dict[tuple[str, str], str]) -> None:
        self.owner = owner
        self.names = names

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        if isinstance(node.value, ast.Name):
            module = self.owner._binds(node.value.id)
            bound = self.names.get((module or "", node.attr))
            if bound is not None:
                return ast.Name(bound, ast.Load())
        return self.generic_visit(node)


def _bound_module(binding: ImportBinding, index: Index) -> str | None:
    """Das Modul, das ein Importeintrag bindet (``import a.b`` bindet ``a``), sonst ``None``."""
    if binding.form == "import":
        root = binding.module.partition(".")[0]
        return root if binding.bound == root else binding.module
    module = f"{binding.module}.{binding.name}"
    return module if index.module_exists(module) else None


def _readers(index: Index, key: tuple[str, str]) -> set[str]:
    return {f"{r.module}:{r.qualname}" for r in index.readers(*key)}
