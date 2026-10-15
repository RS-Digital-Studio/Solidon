"""Der Beweis eines Schnitts im Modulmodus (``tools/move_proof.py``).

Ein Modul wird ein Paket gleichen Namens oder gibt Definitionen an Nachbarmodule ab. Bewiesen wird
je Definition, dass sie im erklärten Ziel ``ast``-gleich steht — jeder Name, der den
Modulnamensraum liest, meint vorher (abgebildet) und nachher dieselbe Bindung (``symtable`` und die
Tabelle der Modulebene, nicht ein Wert) —, je Zielmodul, dass es nur Docstring, Importe aus der
Quelle oder Nachbarziele und seine Definitionen in alter Reihenfolge trägt, und je Leserdatei, dass
nur erklärte Bezüge abweichen. Der Paket-``__init__`` ist nur ein Docstring (Konzept 3.1, Regel 3).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Sequence

from tools.move_compare import (
    Comparison,
    Identity,
    ImportBinding,
    MappedValues,
    ReaderComparison,
    Scopes,
    TopLevel,
    _is_annotation,
    _string_names,
    _text,
    comments,
    import_bindings,
    qualname_of,
    string_constants,
    top_names,
)
from tools.move_cut import Cut, Target
from tools.move_source import (
    IMPORTS,
    Source,
    Span,
    docstring_node,
    is_type_checking,
    module_of,
    names_source,
    path_of,
    spans,
)
from tools.move_trees import Mapping, Proof, Trees


class ModuleMapping(Mapping):
    def __init__(self, cut: Cut) -> None:
        self.source = cut.source_module
        self.moves: dict[str, tuple[str, str]] = {}
        for target in cut.targets:
            for name in target.definitions:
                self.moves[name] = (target.module, cut.renamed(name))

    def ref(self, module: str, name: str) -> tuple[str, str]:
        if module == self.source and name in self.moves:
            return self.moves[name]
        return module, name

    def keys(self) -> Iterator[tuple[str, str]]:
        for name in self.moves:
            yield self.source, name


class ModuleProof:
    """Der Beweis eines Schnitts im Modulmodus."""

    def __init__(self, proof: Proof, trees: Trees, cut: Cut) -> None:
        self.proof = proof
        self.trees = trees
        self.cut = cut
        self.mapping = ModuleMapping(cut)
        self.values = MappedValues(self.mapping.ref)
        self.src_path = cut.source
        self.src = cut.source_module
        self.targets = {t.module: t for t in cut.targets}
        self.used_readers: set[int] = set()
        self.used_lists: set[int] = set()

    def run(self) -> Mapping:
        if self.src_path not in self.trees.old_files:
            self.proof.error(f"{self.src_path}: die Quelle fehlt im alten Baum")
            return self.mapping
        self._files()
        if self.proof.errors:
            return self.mapping
        old = self.trees.old(self.src_path)
        units = self._source_units(old)
        for target in self.cut.targets:
            self._target(old, units, target)
        self._source_head(old, units)
        if self.cut.package:
            self._package_init()
        for path in self.trees.changed:
            if (
                path.endswith(".py")
                and path != self.src_path
                and module_of(path) not in self.targets
            ):
                self._reader(path)
        self._lazy_parent()
        for number, reader in enumerate(self.cut.source_readers):
            if number not in self.used_readers:
                self.proof.error(
                    f"source_readers: {reader.path} ({reader.scope}) liest die Quelle nicht über "
                    "M.__file__ — Erklärung streichen"
                )
        self._stale_strings()
        for number, entry in enumerate(self.cut.name_lists):
            if number not in self.used_lists:
                self.proof.error(
                    f"name_lists: {entry.value!r} steht nicht in {entry.path} — Erklärung streichen"
                )
        return self.mapping

    # ---- Dateien

    def _files(self) -> None:
        expected_added = {path_of(t) for t in self.targets if t != self.src}
        expected_removed: set[str] = set()
        if self.cut.package:
            expected_added.add(path_of(self.src, package=True))
            expected_removed.add(self.src_path)
        elif self.src not in self.targets:
            expected_removed.add(self.src_path)
        added = set(self.trees.added)
        removed = set(self.trees.removed)
        for path in sorted(added - expected_added):
            self.proof.error(f"{path}: neue Datei, die der Zuschnitt nicht nennt")
        for path in sorted(expected_added - added):
            self.proof.error(f"{path}: Zielmodul fehlt (oder bestand schon vorher)")
        for path in sorted(removed - expected_removed):
            self.proof.error(f"{path}: entfernt, ohne dass der Zuschnitt es verlangt")
        for path in sorted(expected_removed - removed):
            self.proof.error(f"{path}: die Quelle müsste entfallen")
        self.proof.counts["changed_files"] = sum(
            1
            for p in self.trees.changed
            if p.endswith(".py") and p != self.src_path and module_of(p) not in self.targets
        )

    def _package_init(self) -> None:
        path = path_of(self.src, package=True)
        source = self.trees.new(path)
        body = source.tree.body
        doc = docstring_node(body)
        if len(body) != 1 or doc is None:
            self.proof.error(
                f"{path}: das __init__ eines neuen Pakets ist nur ein Docstring (Konzept 3.1, "
                "Regel 3) — kein Import, keine Fassade"
            )
            return
        value = doc.value
        assert isinstance(value, ast.Constant)
        if value.value != self.cut.package_docstring:
            self.proof.error(f"{path}: Docstring weicht von package_docstring ab")
        self.proof.note(f"Paket {self.src}: __init__.py ist nur der erklärte Docstring")

    # ---- Quelle

    def _source_units(self, old: Source) -> list[tuple[list[str], ast.stmt, Span]]:
        """Die Anweisungen der Quelle mit ihren gebundenen Namen und Spannen, in Reihenfolge —
        die ``@overload``-Fassungen einer Funktion je für sich."""
        body = old.tree.body
        found = spans(old, body)
        units: list[tuple[list[str], ast.stmt, Span]] = []
        declared = {n for t in self.cut.targets for n in t.definitions} | set(self.cut.duplicate)
        for number, (stmt, span) in enumerate(zip(body, found, strict=True)):
            if number == 0 and docstring_node(body) is stmt:
                continue
            if isinstance(stmt, IMPORTS):
                continue
            if isinstance(stmt, ast.If) and is_type_checking(stmt.test):
                continue
            names = top_names(stmt)
            if not names:
                self.proof.error(f"{self.src_path}:{stmt.lineno}: Anweisung ohne Bindung")
                continue
            units.append((names, stmt, span))
            for name in names:
                if name not in declared:
                    self.proof.error(
                        f"{self.src_path}:{stmt.lineno}: {name!r} steht in keinem Ziel des "
                        "Zuschnitts"
                    )
        return units

    def _source_head(self, old: Source, units: list[tuple[list[str], ast.stmt, Span]]) -> None:
        """Was im Kopf der Quelle steht, hat ein Ziel: Kein Kommentar steht dort (die Köpfe der
        Ziele entstehen neu), und jeder Import der Quelle steht in mindestens einem Ziel — einer,
        den keine Definition liest, fiele sonst still weg (ein Seiteneffekt)."""
        end = units[0][2].first - 1 if units else len(old.lines)
        for comment in old.comments_between(1, end):
            self.proof.error(
                f"{self.src_path}:{comment.line}: Kommentar im Kopf der Quelle "
                f"({comment.text.strip()!r}) steht in keinem Ziel — vor dem Schnitt an eine "
                "Definition stellen oder entfernen"
            )
        landed: set[Identity] = set()
        for target in self.targets:
            path = path_of(target)
            if path in self.trees.new_files:
                top = TopLevel(self.trees.new(path))
                landed |= {b.identity for found in top.imports.values() for b in found}
        for stmt, checking in TopLevel(old).import_statements:
            for binding in import_bindings(self.src_path, stmt, checking):
                if binding.module != "__future__" and binding.identity not in landed:
                    self.proof.error(
                        f"{self.src_path}:{stmt.lineno}: Import {binding.text()} der Quelle steht "
                        "in keinem Ziel — liest ihn keine Definition (ein Seiteneffekt?), vor dem "
                        "Schnitt in die Definition ziehen, die ihn braucht, oder entfernen"
                    )

    # ---- Ziele

    def _target(
        self, old: Source, units: list[tuple[list[str], ast.stmt, Span]], target: Target
    ) -> None:
        path = path_of(target.module)
        if path not in self.trees.new_files:
            return
        new = self.trees.new(path)
        body = new.tree.body
        new_spans = spans(new, body)
        doc = docstring_node(body)
        if (
            doc is None
            or not isinstance(doc.value, ast.Constant)
            or doc.value.value != target.docstring
        ):
            self.proof.error(f"{path}: Docstring fehlt oder weicht vom erklärten ab")
        old_top = TopLevel(old)
        new_top = TopLevel(new)
        expected = [
            (names, stmt, span)
            for names, stmt, span in units
            if set(names) & set(target.definitions)
        ]
        by_name = {name: (stmt, span) for names, stmt, span in units for name in names}
        new_units: list[tuple[ast.stmt, Span]] = []
        seen_unit = False
        used_imports: set[str] = set()
        for stmt, span in zip(body, new_spans, strict=True):
            if stmt is doc:
                continue
            checking = isinstance(stmt, ast.If) and is_type_checking(stmt.test)
            if checking:
                assert isinstance(stmt, ast.If)
                used_imports |= {n.id for n in ast.walk(stmt.test) if isinstance(n, ast.Name)}
            if isinstance(stmt, IMPORTS) or checking:
                if seen_unit:
                    self.proof.error(f"{path}:{stmt.lineno}: Import zwischen den Definitionen")
                continue
            seen_unit = True
            new_units.append((stmt, span))
        head_end = new_units[0][1].first - 1 if new_units else len(new.lines)
        for comment in new.comments_between(1, head_end):
            self.proof.error(
                f"{path}:{comment.line}: Kommentar im Kopf des Ziels ({comment.text.strip()!r}) — "
                "die Quelle hatte dort keinen"
            )
        duplicates = [
            (stmt, span)
            for stmt, span in new_units
            if set(top_names(stmt)) & set(self.cut.duplicate)
        ]
        own = [(stmt, span) for stmt, span in new_units if (stmt, span) not in duplicates]
        if len(own) != len(expected):
            self.proof.error(
                f"{path}: {len(own)} Definitionen, erklärt sind {len(expected)} "
                f"({', '.join(n for names, _s, _p in expected for n in names)})"
            )
        for (new_stmt, new_span), (_names, old_stmt, old_span) in zip(own, expected, strict=False):
            self._unit(
                old, old_top, old_stmt, old_span, new, new_top, new_stmt, new_span, target.module
            )
            used_imports |= self._used(new, new_stmt, new_span)
        for new_stmt, new_span in duplicates:
            name = top_names(new_stmt)[0]
            old_stmt, old_span = by_name[name]
            self._unit(
                old, old_top, old_stmt, old_span, new, new_top, new_stmt, new_span, target.module
            )
            used_imports |= self._used(new, new_stmt, new_span)
            readers = {n for st, sp in own for n in self._used(new, st, sp)}
            if name not in readers:
                self.proof.error(f"{path}: {name!r} doppelt mitgenommen, aber hier nicht gelesen")
        self._imports(path, old_top, new_top, used_imports)

    def _used(self, source: Source, stmt: ast.stmt, span: Span) -> set[str]:
        scopes = Scopes(source, stmt, span)
        found = {
            node.id
            for node in ast.walk(stmt)
            if isinstance(node, ast.Name) and scopes.is_global(node)
        }
        for node in ast.walk(stmt):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                parent = source.parent(node)
                if _is_annotation(parent, node):
                    found |= _string_names(node.value)
        return found

    def _imports(self, path: str, old_top: TopLevel, new_top: TopLevel, used: set[str]) -> None:
        source_imports = {b for found in old_top.imports.values() for b in found}
        source_identities = {b.identity for b in source_imports}
        for stmt, checking in new_top.import_statements:
            for binding in import_bindings(path, stmt, checking):
                if binding.module == "__future__":
                    continue
                if binding.bound not in used:
                    self.proof.error(f"{path}:{stmt.lineno}: unbenutzter Import {binding.text()}")
                    continue
                module = (
                    f"{binding.module}.{binding.name}" if binding.form == "from" else binding.module
                )
                sibling = module in self.targets and not binding.checking
                if binding.identity not in source_identities and not sibling:
                    self.proof.error(
                        f"{path}:{stmt.lineno}: Import {binding.text()} stammt weder aus der "
                        "Quelle noch bindet er ein Zielmodul"
                    )
        future_old = {b.name for b in source_imports if b.module == "__future__"}
        future_new = {
            b.name for found in new_top.imports.values() for b in found if b.module == "__future__"
        }
        if future_old != future_new:
            self.proof.error(f"{path}: from __future__ weicht von der Quelle ab")

    def _unit(
        self,
        old: Source,
        old_top: TopLevel,
        old_stmt: ast.stmt,
        old_span: Span,
        new: Source,
        new_top: TopLevel,
        new_stmt: ast.stmt,
        new_span: Span,
        target: str,
    ) -> None:
        names = top_names(old_stmt)
        label = ", ".join(names)
        expected_names = [self.cut.renamed(n) for n in names]
        if top_names(new_stmt) != expected_names:
            self.proof.error(
                f"{new.path}:{new_stmt.lineno}: bindet {top_names(new_stmt)} statt {expected_names}"
            )
            return
        comparison = MovedComparison(
            self,
            old,
            old_top,
            Scopes(old, old_stmt, old_span),
            new,
            new_top,
            Scopes(new, new_stmt, new_span),
            target,
            names,
        )
        comparison.compare(old_stmt, new_stmt)
        for error in comparison.errors:
            self.proof.error(error)
        # Die ganze Spanne: Kopfkommentar, freie Kommentare davor (durch Leerzeilen getrennt) und
        # bei der letzten Anweisung, was hinter ihr steht — der Planer nimmt genau das mit.
        before = comments(old, old_span.first, old_span.last)
        after = comments(new, new_span.first, new_span.last)
        if before != after:
            self.proof.error(
                f"{new.path}:{new_stmt.lineno} ({label}): Kommentar verloren oder neu — vorher "
                f"{sorted(before)}, nachher {sorted(after)}"
            )
        self.proof.counts["definitions"] += 1
        for name in names:
            new_module, new_name = (
                self.mapping.ref(self.src, name) if name in self.mapping.moves else (target, name)
            )
            self.proof.note(
                f"Definition {self.src}:{name} → {new_module}:{new_name}: ast-gleich nach "
                f"{len(comparison.accepted)} erklärten Bezügen"
                + (f" ({'; '.join(comparison.accepted)})" if comparison.accepted else "")
            )

    # ---- Leserdateien

    def _reader(self, path: str) -> None:
        comparison = ModuleReaderComparison(self, path)
        comparison.run()
        for error in comparison.errors:
            self.proof.error(error)
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

    def _lazy_parent(self) -> None:
        """Das ``__init__`` des Elternpakets mit einem trägen Export auf einen verschobenen Namen
        wird verglichen, auch wenn es unverändert blieb: Dann zeigte der Export ins Leere."""
        parent = self.src.rpartition(".")[0]
        path = path_of(parent, package=True) if parent else ""
        if not path or path in self.trees.changed or path not in self.trees.new_files:
            return
        comparison = ModuleReaderComparison(self, path)
        if not any(
            isinstance(node, ast.Tuple) and comparison.lazy_entry(node) is not None
            for node in ast.walk(comparison.old.tree)
        ):
            return
        comparison.label = "Leser, unverändert"
        comparison.run()
        for error in comparison.errors:
            self.proof.error(error)

    def _stale_strings(self) -> None:
        """Keine Zeichenkette im neuen Baum zeigt noch auf die alte Quelldatei oder einen
        verschobenen Namen unter dem alten Modul (Pfad, Punktname)."""
        moved = {f"{self.src}.{name}" for name in self.mapping.moves}
        file_name = self.src_path.rpartition("/")[2]
        needles = (self.src_path.encode(), file_name.encode(), self.src.encode())
        targets = {path_of(t) for t in self.targets}
        for path, data in self.trees.new_files.items():
            if not path.endswith(".py") or not any(n in data for n in needles):
                continue
            source = self.trees.new(path)
            sites = {(s.line, s.col) for (p, *_), s in self.trees.sites("new").items() if p == path}
            # Eine Erklärung mit der Quelle als Pfad gilt in jedem Ziel: Dort stehen danach die
            # verschobenen Definitionen.
            places = {path, self.src_path} if path in targets else {path}
            kept = {e.value for e in self.cut.name_lists if e.path in places and e.to == (e.value,)}
            for node in string_constants(source):
                value = node.value
                assert isinstance(value, str)
                stale = names_source(value, self.src_path, self.src, moved)
                if value in kept:
                    for number, entry in enumerate(self.cut.name_lists):
                        if entry.path in places and entry.value == value:
                            self.used_lists.add(number)
                    continue
                if stale and (node.lineno, node.col_offset) not in sites:
                    self.proof.error(
                        f"{path}:{node.lineno}: Zeichenkette {value!r} nennt die alte Quelle — in "
                        "name_lists oder source_readers erklären"
                    )


class MovedComparison(Comparison):
    """Vergleich einer verschobenen Definition mit ihrer alten Fassung: Jeder Name, der den
    Modulnamensraum liest, muss vorher (abgebildet) und nachher dieselbe Bindung meinen."""

    def __init__(
        self,
        owner: ModuleProof,
        old: Source,
        old_top: TopLevel,
        old_scopes: Scopes,
        new: Source,
        new_top: TopLevel,
        new_scopes: Scopes,
        target: str,
        names: list[str],
    ) -> None:
        super().__init__(", ".join(names), old, new)
        self.owner = owner
        self.old_top = old_top
        self.new_top = new_top
        self.old_scopes = old_scopes
        self.new_scopes = new_scopes
        self.target = target
        self.names = names
        self.identity_declared = any(i.name in names for i in owner.cut.identity)

    def _mapped(self, identity: Identity) -> Identity:
        if identity[0] == "def" and identity[1] == self.owner.src:
            name = str(identity[2])
            if name in self.owner.mapping.moves:
                module, new_name = self.owner.mapping.moves[name]
                return ("def", module, new_name)
            return ("def", self.target, name)
        return identity

    def _identity(self, node: ast.AST, side: str) -> Identity | None:
        top = self.old_top if side == "old" else self.new_top
        scopes = self.old_scopes if side == "old" else self.new_scopes
        index = self.owner.trees.old_index if side == "old" else self.owner.trees.new_index
        if isinstance(node, ast.Name):
            if scopes.is_global(node):
                return top.identity(node.id)
            return None
        if isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and scopes.is_global(base):
                module = top.binding_module(base.id, index)
                if module is not None:
                    return ("def", module, node.attr)
        return None

    def special(self, old: ast.AST, new: ast.AST) -> bool:
        if (
            isinstance(old, ast.Constant)
            and isinstance(new, ast.Constant)
            and isinstance(old.value, str)
            and isinstance(new.value, str)
            and _is_annotation(self.old.parent(old), old)
        ):
            return self.annotation(old, new)
        if (
            isinstance(old, ast.Constant)
            and isinstance(new, ast.Constant)
            and isinstance(old.value, str)
            and isinstance(new.value, str)
            and old.value != new.value
        ):
            return self.declared_text(old, new)
        if not isinstance(old, (ast.Name, ast.Attribute)) or not isinstance(
            new, (ast.Name, ast.Attribute)
        ):
            return False
        before = self._identity(old, "old")
        after = self._identity(new, "new")
        if before is None and after is None:
            return False
        mapped = self._mapped(before) if before is not None else None
        if mapped == after:
            if ast.dump(old) != ast.dump(new):
                self.accept(f"{_text(self.old, old)} → {_text(self.new, new)}")
            return True
        if (
            before is not None
            and after is not None
            and before[0] == after[0] == "identity"
            and before[1] == after[1]
            and self.identity_declared
        ):
            self.accept(f"{before[1]} meint danach {after[2]} (erklärt in identity)")
            return True
        self.fail(old, new, f"meint vorher {mapped}, nachher {after}")
        return True

    def scalar(self, old: ast.AST, new: ast.AST, name: str, before: object, after: object) -> bool:
        if (
            name == "name"
            and isinstance(old, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and before in self.names
            and self.owner.cut.renamed(str(before)) == after
        ):
            self.accept(f"{before} heißt {after} (erklärte Umbenennung)")
            return True
        return False

    def declared_text(self, old: ast.Constant, new: ast.Constant) -> bool:
        """Eine Zeichenkette in der verschobenen Definition, die ``[[name_lists]]`` mit der
        Quelle als Pfad ersetzt (genau ein neuer Wert)."""
        cut = self.owner.cut
        for number, entry in enumerate(cut.name_lists):
            if entry.path == cut.source and entry.value == old.value and entry.to == (new.value,):
                self.owner.used_lists.add(number)
                self.accept(f"{old.value!r} → {new.value!r} (name_lists)")
                return True
        self.fail(old, new, f"Zeichenkette {old.value!r} → {new.value!r} ohne Erklärung")
        return True

    def annotation(self, old: ast.Constant, new: ast.Constant) -> bool:
        """Eine Annotation als Zeichenkette (``"Shape"``): Jeder Name darin meint vorher
        (abgebildet) und nachher dieselbe Bindung der Modulebene."""
        try:
            before = ast.parse(str(old.value).strip(), mode="eval")
            after = ast.parse(str(new.value).strip(), mode="eval")
        except SyntaxError:
            return old.value == new.value
        names_before = [n for n in ast.walk(before) if isinstance(n, ast.Name)]
        names_after = [n for n in ast.walk(after) if isinstance(n, ast.Name)]
        shape_before = ast.dump(_without_names(before))
        shape_after = ast.dump(_without_names(after))
        if shape_before != shape_after or len(names_before) != len(names_after):
            self.fail(old, new, "Annotation als Zeichenkette geändert")
            return True
        for first, second in zip(names_before, names_after, strict=True):
            mapped = self._mapped(self.old_top.identity(first.id))
            if mapped != self.new_top.identity(second.id):
                self.fail(old, new, f"{first.id} in der Annotation meint nachher etwas anderes")
                return True
        if old.value != new.value:
            self.accept(f"Annotation {old.value!r} → {new.value!r}")
        return True


class ModuleReaderComparison(ReaderComparison):
    """Leserdatei im Modulmodus."""

    def __init__(self, owner: ModuleProof, path: str) -> None:
        super().__init__(owner.trees, path, owner.mapping, owner.values)
        self.owner = owner
        self.lists = {
            n: entry for n, entry in enumerate(owner.cut.name_lists) if entry.path == path
        }
        self.readers = {
            n: entry for n, entry in enumerate(owner.cut.source_readers) if entry.path == path
        }

    def allowed_rebinding(self, previous: list[ImportBinding], binding: ImportBinding) -> bool:
        for old in previous:
            moved = old.form == "from" and old.module == self.owner.src
            if moved and self.mapping.ref(old.module, old.name) == (binding.module, binding.name):
                return True
            # ``import app.x`` → ``import app.x.ziel``: dieselbe Wurzel, ein Zielmodul.
            if (
                old.form == binding.form == "import"
                and _src_related(old.module, self.owner.src)
                and _target_module(binding.module, self.owner)
            ):
                return True
        return False

    def allowed_module_alias(self, binding: ImportBinding) -> bool:
        module = f"{binding.module}.{binding.name}" if binding.form == "from" else binding.module
        return _target_module(module, self.owner) or (
            binding.form == "import" and _target_module(binding.module, self.owner)
        )

    def allowed_removal(self, binding: ImportBinding) -> bool:
        module = f"{binding.module}.{binding.name}" if binding.form == "from" else binding.module
        return _src_related(module, self.owner.src) or (
            binding.form == "from" and binding.module == self.owner.src
        )

    def removable_module(self, module: str) -> bool:
        return module == self.owner.src

    def reference(
        self, old: ast.expr, new: ast.expr, before: tuple[str, str], after: tuple[str, str]
    ) -> bool:
        if before == (self.owner.src, "__file__"):
            scope = qualname_of(self.old, old)
            for number, reader in self.readers.items():
                if reader.scope == scope and after == (reader.module, "__file__"):
                    self.owner.used_readers.add(number)
                    return True
            return False
        return super().reference(old, new, before, after)

    def special(self, old: ast.AST, new: ast.AST) -> bool:
        if isinstance(old, ast.Tuple) and self.lazy_entry(old) is not None:
            return self._lazy_export(old, new)
        return super().special(old, new)

    def lazy_entry(self, node: ast.Tuple) -> str | None:
        """Der Name eines Eintrags ``("quelle", "N")`` im ``__init__`` des Elternpakets der
        Quelle (``app.core.lazy``), wenn ``N`` verschoben wird; sonst ``None``."""
        parent, _, last = self.owner.src.rpartition(".")
        if not parent or self.path != path_of(parent, package=True) or len(node.elts) != 2:
            return None
        first, second = node.elts
        if not (
            isinstance(first, ast.Constant)
            and first.value == last
            and isinstance(second, ast.Constant)
            and isinstance(second.value, str)
            and second.value in self.owner.mapping.moves
        ):
            return None
        return second.value

    def _lazy_export(self, old: ast.Tuple, new: ast.AST) -> bool:
        """Ein träger Export des Elternpakets zeigt danach auf das Zielmodul und den neuen
        Namen: ``("legacy", "N")`` → ``("legacy.<ziel>", "N'")`` mit ``ref(Quelle, N)``."""
        name = self.lazy_entry(old)
        assert name is not None
        parent = self.owner.src.rpartition(".")[0]
        module, new_name = self.mapping.ref(self.owner.src, name)
        expected = (module.removeprefix(parent + "."), new_name)
        got = (
            tuple(e.value if isinstance(e, ast.Constant) else None for e in new.elts)
            if isinstance(new, ast.Tuple)
            else None
        )
        first = old.elts[0]
        assert isinstance(first, ast.Constant)
        before = (str(first.value), name)
        if not module.startswith(parent + ".") or got != expected:
            self.fail(old, new, f"träger Export {before} → {got}, erwartet {expected}")
            return True
        self.accept(f"träger Export {before} → {expected}")
        return True

    def constant(self, old: ast.Constant, new: ast.Constant) -> bool:
        for number, entry in self.lists.items():
            if old.value == entry.value and len(entry.to) == 1 and new.value == entry.to[0]:
                self.owner.used_lists.add(number)
                self.accept(f"{old.value!r} → {new.value!r} (name_lists)")
                return True
        return False

    def expressions(
        self, owner: ast.AST, name: str, old: Sequence[ast.AST], new: Sequence[ast.AST]
    ) -> None:
        if not any(
            isinstance(item, ast.Constant)
            and any(item.value == e.value for e in self.lists.values())
            for item in old
        ):
            super().expressions(owner, name, old, new)
            return
        cursor = 0
        for item in old:
            entry = next(
                (
                    (n, e)
                    for n, e in self.lists.items()
                    if isinstance(item, ast.Constant) and item.value == e.value
                ),
                None,
            )
            if entry is None:
                if cursor >= len(new):
                    self.fail(owner, owner, f"{name}: Eintrag fehlt")
                    return
                self.compare(item, new[cursor])
                cursor += 1
                continue
            number, declared = entry
            got = [
                n.value if isinstance(n, ast.Constant) else None
                for n in new[cursor : cursor + len(declared.to)]
            ]
            if got != list(declared.to):
                self.fail(
                    item, owner, f"{declared.value!r} wird {got}, erklärt {list(declared.to)}"
                )
                return
            self.owner.used_lists.add(number)
            self.accept(f"{declared.value!r} → {list(declared.to)} (name_lists)")
            cursor += len(declared.to)
        if cursor != len(new):
            self.fail(owner, owner, f"{name}: {len(new) - cursor} Einträge zu viel")


def _src_related(module: str, src: str) -> bool:
    return module == src


def _target_module(module: str, owner: ModuleProof) -> bool:
    return module in owner.targets


def _without_names(tree: ast.AST) -> ast.AST:
    """Eine Kopie mit gleichnamigen Platzhaltern statt Namen — die Form ohne Bezüge."""
    copy = ast.parse(ast.unparse(tree), mode="eval")
    for node in ast.walk(copy):
        if isinstance(node, ast.Name):
            node.id = "_"
    return copy
