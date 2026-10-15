"""Der Beweis eines Schnitts im Komponentenmodus (``tools/move_proof.py``).

Konzept Codestruktur 3.3: Jede verschobene Methode ist nach dem Schritt ``ast``-gleich mit ihrer
Fassung davor, nachdem **genau** die Ersetzungsliste angewandt ist. Verglichen werden alter und
neuer Baum, nicht die Tabelle des Planers; die erwartete Rolle eines nackten ``self`` leitet der
Beweis wie der Planer aus dem Zuschnitt und dem Auflöser des alten Baums ab
(:func:`tools.move_component.self_role`), der Sollbaum der Attrappe prüft beide von außen.

* **Methoden:** je verschobener Methode der alte Rumpf im Wirt gegen den neuen in der Komponente —
  ``self.<eigenes>`` gleich, ``self.<geteiltes>`` → ``self._host.…``, ererbt → ``self._parent.…``,
  nacktes ``self`` nach seiner Rolle, ``Wirt.m`` → ``Komponente.m`` samt Empfänger, jeder globale
  Name meint dieselbe Bindung (Import im Wirtsmodul gleich Import im Komponentenmodul; eine
  Definition des Wirtsmoduls nur als Typ unter ``TYPE_CHECKING``), Kommentare gleich.
* **Wirt:** der Klassenrumpf ohne die verschobenen Methoden gleich, ``self.<m>`` →
  ``self.<attr>.<m>``, Importe fallen nur weg, wenn sie danach niemand liest.
* **Komponente:** der Klassenrumpf gleich bis auf die angehängten Methoden, neue Importe nur
  solche, die die verschobenen Methoden im Wirtsmodul lasen.
* **Leser:** ``x.<m>`` → ``x.<attr>.<m>`` genau dort, wo der Zuschnitt oder die Eindeutigkeit des
  Namens den Wirt meint, ``Wirt.m`` → ``Komponente.m``, Pfade als Text auf die Komponente — in
  **jeder** Datei, die einen verschobenen Namen nennt, auch in einer unveränderten: Der Auflöser
  sieht Zugriffe über Instanzen nicht, ein vergessener Leser fiele baumweit nicht auf (Konzept
  4.1, W5: ein Rest ist rot). Eine Zeichenkette gleich einem verschobenen Member ist erklärt
  (``[[accesses]]`` mit ``keep``) oder das Namensargument eines Aufrufs mit festem Namen.

**Lebensdauer liegt außerhalb dieses Vergleichs.** Der Beweis prüft am neuen Baum den statischen
Teil (:func:`tools.move_component.lifetime`) und sagt im Protokoll, dass der Laufzeitnachweis
(kein Signal nach ``release()``, Wirt ohne ``gc.collect`` fort) eigens zu führen ist.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterator

from tools.code_index import Index, PatchSite
from tools.move_compare import (
    Comparison,
    FileScopes,
    ImportBinding,
    MappedValues,
    ReaderComparison,
    Scopes,
    TopLevel,
    _difference,
    _text,
    comments,
    loaded_names,
    qualname_of,
    string_constants,
)
from tools.move_component import (
    Method,
    Shape,
    call_position,
    in_annotation,
    lifetime,
    named_call,
    refers_to,
    self_name,
    self_role,
)
from tools.move_cut import Cut
from tools.move_source import LINE_LIMIT, Source, class_spans, path_of
from tools.move_trees import Mapping, Proof, Trees


class ComponentMapping(Mapping):
    """Leser in verschobenen Methoden heißen danach ``<Komponente>.<m>``; ein Patch auf ein
    verschobenes Member trifft danach die Komponente (Klasse oder Instanz)."""

    def __init__(self, shape: Shape) -> None:
        self.shape = shape
        self.host = shape.cut.host
        self.module = shape.module
        self.component = shape.cut.component_class
        self.component_module = shape.component_module

    def reader(self, module: str, qualname: str) -> tuple[str, str]:
        head, _, rest = qualname.partition(".")
        if module == self.module and head == self.host and rest.split(".")[0] in self.shape.methods:
            return self.component_module, f"{self.component}.{rest}"
        return module, qualname

    def site_mismatch(self, old: PatchSite, new: PatchSite) -> str | None:
        if len(old.targets) != len(new.targets):
            return f"{len(new.targets)} Ziele statt {len(old.targets)}"
        host_class = f"class {self.module}:{self.host}"
        for before, after in zip(old.targets, new.targets, strict=True):
            moved = before.name in self.shape.moved_names
            if before.status == "object" and moved and before.module == host_class:
                expected = ("object", f"class {self.component_module}:{self.component}")
                if (after.status, after.module, after.name) != (*expected, before.name):
                    return f"zielt auf {after}, erwartet die Klasse {self.component}"
                continue
            if before.status == "object" and moved:
                if after.status != "object" or after.name != before.name:
                    return f"zielt auf {after}, erwartet ein Objekt mit {before.name}"
                continue
            if (before.status, before.module, before.name) != (
                after.status,
                after.module,
                after.name,
            ):
                return f"zielt auf {after}, erwartet {before}"
        return None


class ComponentProof:
    """Der Beweis eines Schnitts im Komponentenmodus."""

    def __init__(self, proof: Proof, trees: Trees, cut: Cut) -> None:
        self.proof = proof
        self.trees = trees
        self.cut = cut
        self.path = cut.source
        self.component_path = path_of(cut.component_module)

    def run(self) -> Mapping:
        trees = self.trees
        for path in (self.path, self.component_path):
            if path not in trees.old_files or path not in trees.new_files:
                self.proof.error(f"{path}: fehlt im alten oder neuen Baum")
        old_host = trees.old(self.path)
        old_component = trees.old(self.component_path)
        self.shape = Shape(self.cut, trees.old_index, old_host, old_component)
        sources = list(self._old_sources())
        self.shape.scan_uniqueness(iter(sources))
        mapping = ComponentMapping(self.shape)
        self.mapping = mapping
        self.values = MappedValues(mapping.ref)
        for problem in self.shape.problems:
            self.proof.error(problem)
        if self.proof.errors:
            return mapping
        for path in trees.added:
            self.proof.error(f"{path}: neue Datei — der Komponentenmodus legt keine an")
        for path in trees.removed:
            self.proof.error(f"{path}: entfernt — der Komponentenmodus entfernt keine Datei")
        new_host = trees.new(self.path)
        new_component = trees.new(self.component_path)
        self.read_by_moved = self._read_by_moved(old_host)
        self.moved_comments: Counter[str] = Counter()
        for moved in self.shape.methods.values():
            for span in moved.spans:
                self.moved_comments += comments(old_host, span.first, span.last)
        self._methods(old_host, new_component)
        lines = trees.new_files[self.component_path].count(b"\n")
        if lines > LINE_LIMIT:
            self.proof.error(
                f"{self.component_path}: {lines} Zeilen, mehr als {LINE_LIMIT} — die Komponente "
                f"steht unter {LINE_LIMIT} Zeilen (Konzept 4.5)"
            )
        for path in trees.changed:
            if not path.endswith(".py"):
                continue
            if path == self.path:
                comparison: ReaderComparison = HostComparison(self, path)
            elif path == self.component_path:
                comparison = ComponentFileComparison(self, path)
            else:
                comparison = ComponentReaderComparison(self, path)
            self._file(path, comparison)
        needles = tuple(n.encode() for n in self.shape.moved_names)
        for path, _source in sources:
            if path in trees.changed or path in (self.path, self.component_path):
                continue
            if path in trees.new_files and any(n in trees.old_files[path] for n in needles):
                self._unchanged(path)
        self._strings(sources)
        new_shape = Shape(self.cut, trees.new_index, new_host, new_component, before=False)
        for problem in [*new_shape.problems, *lifetime(new_shape)]:
            self.proof.error(f"Lebensdauer (statisch): {problem}")
        self.proof.note(
            "Lebensdauer (statisch) am neuen Baum: release() der Komponente, _host und _parent "
            "als Eigenschaften über schwachen Referenzen, kein starkes Halten im __init__, "
            f"{self.cut.host}.release ruft {self.cut.host_attribute}.release() vor "
            "disconnect(self). Der Laufzeitnachweis (kein Signal nach release, Wirt ohne "
            "gc.collect fort) ist eigens zu führen."
        )
        return mapping

    def _unchanged(self, path: str) -> None:
        """Eine Datei, die einen verschobenen Namen nennt und unverändert blieb, gegen sich selbst
        verglichen: Jede Stelle, die laut Zuschnitt, Auflöser oder Eindeutigkeit des Namens dem
        Wirt gilt, ist dann ein vergessener Leser — rot, auch wenn der Planer sie übersah oder sie
        erst nach dem Planen entstand (Konzept 4.1, W5: ein Rest ist rot)."""
        comparison = ComponentReaderComparison(self, path)
        comparison.label = "Leser, unverändert"
        comparison.run()
        for error in comparison.errors:
            self.proof.error(error)
        self.proof.counts["unchanged_files"] += 1

    def _strings(self, sources: list[tuple[str, Source]]) -> None:
        """Jede Zeichenkette gleich einem verschobenen Member ist das zweite Argument eines
        Aufrufs mit festem Namen (dort verglichen) oder in ``[[accesses]]`` mit ``keep`` erklärt;
        kein Pfad als Text zeigt nachher noch auf den Wirt."""
        moved = self.shape.moved_names
        kept = {(a.path, a.scope, a.member) for a in self.cut.accesses if a.decision == "keep"}
        for path, source in sources:
            for node in string_constants(source):
                value = str(node.value)
                if value not in moved:
                    continue
                parent = source.parent(node)
                if (
                    isinstance(parent, ast.Call)
                    and len(parent.args) > 1
                    and parent.args[1] is node
                    and named_call(parent) is not None
                ):
                    continue
                scope = self._string_scope(path, source, node)
                if (path, scope, value) in kept:
                    continue
                self.proof.error(
                    f"{path}:{node.lineno}: Zeichenkette {value!r} ({scope}) nennt ein "
                    "verschobenes Member ohne Erklärung — als Zugriff schreiben oder in "
                    '[[accesses]] mit decision = "keep" erklären'
                )
        prefix = f"{self.shape.module}.{self.cut.host}."
        for path, data in self.trees.new_files.items():
            if not path.endswith(".py") or prefix.encode() not in data:
                continue
            for node in string_constants(self.trees.new(path)):
                value = str(node.value)
                if value.startswith(prefix) and value[len(prefix) :].split(".")[0] in moved:
                    self.proof.error(
                        f"{path}:{node.lineno}: Pfad als Text {value!r} zeigt noch auf "
                        f"{self.cut.host} — auf {self.cut.component_class} umschreiben"
                    )

    def _string_scope(self, path: str, source: Source, node: ast.AST) -> str:
        """Der Bereich einer Zeichenkette wie im Zuschnitt: im Wirt die Methode
        (``Wirt.methode``), sonst der Qualname."""
        scope = qualname_of(source, node)
        parts = scope.split(".")
        if path == self.path and parts[0] == self.cut.host and len(parts) > 2:
            return ".".join(parts[:2])
        return scope

    def _old_sources(self) -> Iterator[tuple[str, Source]]:
        names = self.shape.needles()
        for path, data in self.trees.old_files.items():
            if path.endswith(".py") and any(n.encode() in data for n in names):
                yield path, self.trees.old(path)

    def _read_by_moved(self, old_host: Source) -> set[str]:
        scopes = FileScopes(old_host)
        found: set[str] = set()
        for moved in self.shape.methods.values():
            for method in moved.defs:
                found |= {
                    n.id
                    for n in ast.walk(method)
                    if isinstance(n, ast.Name) and scopes.of(method).is_global(n)
                }
        return found

    def _methods(self, old_host: Source, new_component: Source) -> None:
        component = _class(new_component, self.cut.component_class)
        if component is None:
            self.proof.error(f"{self.component_path}: die Klasse {self.cut.component_class} fehlt")
            return
        new_spans = dict(
            zip(map(id, component.body), class_spans(new_component, component), strict=True)
        )
        found: dict[str, list[Method]] = {}
        for stmt in component.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name in (
                self.shape.methods
            ):
                found.setdefault(stmt.name, []).append(stmt)
        old_scopes = FileScopes(old_host)
        new_scopes = FileScopes(new_component)
        for name, moved in self.shape.methods.items():
            news = found.get(name, [])
            if len(news) != len(moved.defs):
                self.proof.error(
                    f"{self.component_path}: {name} steht {len(news)}-mal in "
                    f"{self.cut.component_class}, im Wirt {len(moved.defs)}-mal"
                )
                continue
            for old_def, old_span, new_def in zip(moved.defs, moved.spans, news, strict=True):
                comparison = MethodComparison(
                    self,
                    old_host,
                    new_component,
                    (old_def, old_scopes.of(old_def)),
                    (new_def, new_scopes.of(new_def)),
                )
                comparison.compare(old_def, new_def)
                for error in comparison.errors:
                    self.proof.error(error)
                new_span = new_spans[id(new_def)]
                before = comments(old_host, old_span.head, old_def.end_lineno or old_span.last)
                after = comments(new_component, new_span.head, new_def.end_lineno or new_span.last)
                if before != after:
                    self.proof.error(
                        f"{self.component_path}:{new_def.lineno} ({name}): Kommentar verloren "
                        f"oder neu — vorher {sorted(before)}, nachher {sorted(after)}"
                    )
                self.proof.counts["methods"] += 1
                self.proof.note(
                    f"Methode {self.cut.host}.{name} → {self.cut.component_class}.{name}: "
                    f"ast-gleich nach {len(comparison.accepted)} erklärten Ersetzungen"
                    + (f" ({'; '.join(comparison.accepted)})" if comparison.accepted else "")
                )

    def _file(self, path: str, comparison: ReaderComparison) -> None:
        comparison.run()
        for error in comparison.errors:
            self.proof.error(error)
        self.proof.counts["changed_files"] += 1
        self.proof.counts["references"] += len(comparison.accepted)
        moved_here = path in (self.path, self.component_path)
        if not comparison.accepted and not comparison.import_changes and not moved_here:
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


# ------------------------------------------------------------------------------ Regeln


class _Rules(Comparison):
    """Was überall gilt: ``x.<m>`` → ``x.<attr>.<m>`` (Wirt laut Erklärung, Auflöser oder
    Eindeutigkeit), ``Wirt.m`` → ``Komponente.m`` samt Empfänger, ``getattr(x, "m")`` und
    Patches mit festem Namen wie ein Zugriff, ``"<modul>.<Wirt>.<m>"`` → Komponente."""

    owner: ComponentProof
    shape: Shape
    rel: str
    index_old: Index
    index_new: Index
    body: tuple[Method, Scopes] | None = None
    new_body: tuple[Method, Scopes] | None = None

    def rules(self, old: ast.AST, new: ast.AST) -> bool:
        if (
            isinstance(old, ast.Call)
            and isinstance(new, ast.Call)
            and (self._class_call(old, new) or self._named(old, new))
        ):
            return True
        if isinstance(old, ast.Attribute) and old.attr in self.shape.moved_names:
            return self._member(old, new)
        if (
            isinstance(old, ast.Constant)
            and isinstance(new, ast.Constant)
            and isinstance(old.value, str)
            and isinstance(new.value, str)
            and old.value != new.value
        ):
            return self._path(old, new)
        return False

    # ---- Hilfen

    def _bare_self(self, node: ast.AST) -> bool:
        if self.body is None or not isinstance(node, ast.Name):
            return False
        method, scopes = self.body
        me = self_name(method)
        return me is not None and node.id == me and refers_to(scopes, method, node, me)

    def _scope(self, node: ast.AST) -> str:
        if self.body is not None:
            return f"{self.shape.cut.host}.{self.body[0].name}"
        return qualname_of(self.old, node)

    def _host_class(self, node: ast.expr) -> bool:
        return self.shape.is_host_class(self.index_old.resolve(self.rel, node))

    def _component_class(self, node: ast.AST) -> bool:
        if not isinstance(node, (ast.Name, ast.Attribute)):
            return False
        if self.new_body is not None:
            return isinstance(node, ast.Name) and node.id == self.shape.cut.component_class
        values = self.index_new.resolve(self.rel, node)
        ref = f"{self.shape.component_module}:{self.shape.cut.component_class}"
        return bool(values) and all(v.kind == "class" and v.ref == ref for v in values)

    def _receiver(self, old: ast.expr, new: ast.AST, why: str) -> None:
        """``new`` ist ``X.<attr>`` mit ``X`` gleich ``old``."""
        attribute = self.shape.cut.host_attribute
        if isinstance(new, ast.Attribute) and new.attr == attribute:
            self.compare(old, new.value)
            self.accept(f"{_text(self.old, old)} → {_text(self.new, new)} ({why})")
        else:
            self.fail(old, new, f"erwartet {_text(self.old, old)}.{attribute} ({why})")

    # ---- Regeln

    def _member(self, old: ast.Attribute, new: ast.AST) -> bool:
        base = old.value
        if self._bare_self(base):
            return False  # eigenes Member im verschobenen Rumpf: der Name selbst
        if not isinstance(new, ast.Attribute) or new.attr != old.attr:
            self.fail(old, new, f"Zugriff auf {old.attr} anders geändert")
            return True
        if self._host_class(base):
            if self._component_class(new.value):
                self.accept(f"{_text(self.old, old)} → {_text(self.new, new)}")
            else:
                self.fail(old, new, f"Klassenbezug auf {self.shape.cut.component_class} erwartet")
            return True
        decision, why = self.shape.decision(
            self.rel, self._scope(old), old.attr, self.index_old.resolve(self.rel, base)
        )
        if decision == "component":
            self._receiver(base, new.value, why)
            return True
        if decision is None:
            self.fail(old, new, f"Zugriff auf {old.attr} ohne Entscheidung ({why})")
            return True
        return False

    def _class_call(self, old: ast.Call, new: ast.Call) -> bool:
        func = old.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr in self.shape.moved_names
            and self._host_class(func.value)
        ):
            return False
        if not (
            isinstance(new.func, ast.Attribute)
            and new.func.attr == func.attr
            and self._component_class(new.func.value)
        ):
            self.fail(old, new, f"Klassenbezug {self.shape.cut.host}.{func.attr} nicht umgestellt")
            return True
        self.accept(f"{_text(self.old, func)} → {_text(self.new, new.func)}")
        if len(old.args) != len(new.args) or not old.args:
            self.expressions(old, "args", old.args, new.args)
        elif self._bare_self(old.args[0]):
            self.compare(old.args[0], new.args[0])
            self.expressions(old, "args", old.args[1:], new.args[1:])
        else:
            self._receiver(old.args[0], new.args[0], "Empfänger des Klassenbezugs")
            self.expressions(old, "args", old.args[1:], new.args[1:])
        self.expressions(old, "keywords", list(old.keywords), list(new.keywords))
        return True

    def _named(self, old: ast.Call, new: ast.Call) -> bool:
        kind = named_call(old)
        if kind is None:
            return False
        second = old.args[1]
        assert isinstance(second, ast.Constant)
        if second.value not in self.shape.moved_names or self._bare_self(old.args[0]):
            return False
        if len(old.args) != len(new.args):
            self.fail(old, new, "Aufruf mit festem Namen anders geändert")
            return True
        first = old.args[0]
        self.compare(old.func, new.func)
        if self._host_class(first):
            if self._component_class(new.args[0]):
                self.accept(f"{_text(self.old, old)} → {_text(self.new, new)}")
            else:
                self.fail(old, new, f"Klassenbezug auf {self.shape.cut.component_class} erwartet")
        else:
            decision, why = self.shape.decision(
                self.rel,
                self._scope(old),
                str(second.value),
                self.index_old.resolve(self.rel, first),
            )
            if decision == "component":
                self._receiver(first, new.args[0], why)
            elif decision is None:
                self.fail(old, new, f"{second.value} ohne Entscheidung ({why})")
            else:
                self.compare(first, new.args[0])
        self.expressions(old, "args", old.args[1:], new.args[1:])
        self.expressions(old, "keywords", list(old.keywords), list(new.keywords))
        return True

    def _path(self, old: ast.Constant, new: ast.Constant) -> bool:
        prefix = f"{self.shape.module}.{self.shape.cut.host}."
        value = str(old.value)
        rest = value[len(prefix) :]
        if not value.startswith(prefix) or rest.split(".")[0] not in self.shape.moved_names:
            return False
        expected = f"{self.shape.component_module}.{self.shape.cut.component_class}.{rest}"
        if new.value == expected:
            self.accept(f"{value!r} → {expected!r}")
        else:
            self.fail(old, new, f"Pfad als Text: erwartet {expected!r}")
        return True


# ------------------------------------------------------------------------------ Methoden


class MethodComparison(_Rules):
    """Eine verschobene Methode: alter Rumpf im Wirt gegen neuen in der Komponente."""

    def __init__(
        self,
        owner: ComponentProof,
        old: Source,
        new: Source,
        body: tuple[Method, Scopes],
        new_body: tuple[Method, Scopes],
    ) -> None:
        super().__init__(f"{owner.cut.host}.{body[0].name}", old, new)
        self.owner = owner
        self.shape = owner.shape
        self.rel = owner.path
        self.index_old = owner.trees.old_index
        self.index_new = owner.trees.new_index
        self.body = body
        self.new_body = new_body
        self.old_top = TopLevel(old)
        self.new_top = TopLevel(new)
        self.me = self_name(body[0]) or "self"

    def special(self, old: ast.AST, new: ast.AST) -> bool:
        if isinstance(old, ast.Attribute) and self._bare_self(old.value):
            return self._self_member(old, new)
        if self._bare_self(old):
            assert isinstance(old, ast.Name)
            return self._self_role(old, new)
        if self.rules(old, new):
            return True
        if isinstance(old, ast.Name) and isinstance(new, ast.Name):
            return self._global(old, new)
        return False

    def _self_member(self, old: ast.Attribute, new: ast.AST) -> bool:
        member = old.attr
        cut = self.shape.cut
        if member in self.shape.moved_names:
            expected = ""
        elif member in cut.host_members:
            expected = "_host"
        elif member in cut.parent_members:
            expected = "_parent"
        else:
            self.fail(old, new, f"{self.me}.{member} hat keine Rolle im Zuschnitt")
            return True
        self._expect_self(old, new, expected, member)
        return True

    def _expect_self(self, old: ast.Attribute, new: ast.AST, via: str, member: str) -> None:
        """``new`` ist ``self.member`` (``via`` leer) oder ``self.<via>.member``."""
        ok = isinstance(new, ast.Attribute) and new.attr == member
        if ok and via:
            assert isinstance(new, ast.Attribute)
            inner = new.value
            ok = isinstance(inner, ast.Attribute) and inner.attr == via
            ok = ok and self._new_self(inner.value if isinstance(inner, ast.Attribute) else inner)
        elif ok:
            assert isinstance(new, ast.Attribute)
            ok = self._new_self(new.value)
        if not ok:
            target = f"{self.me}.{via}.{member}" if via else f"{self.me}.{member}"
            self.fail(old, new, f"erwartet {target}")
            return
        assert isinstance(new, ast.Attribute)
        if not isinstance(old.ctx, type(new.ctx)):
            self.fail(old, new, "Zugriffsart geändert")
        if via:
            self.accept(f"{self.me}.{member} → {self.me}.{via}.{member}")

    def _new_self(self, node: ast.AST) -> bool:
        assert self.new_body is not None
        method, scopes = self.new_body
        me = self_name(method)
        return (
            me is not None
            and isinstance(node, ast.Name)
            and node.id == me
            and refers_to(scopes, method, node, me)
        )

    def _self_role(self, old: ast.Name, new: ast.AST) -> bool:
        parent = self.old.parent(old)
        call = parent if isinstance(parent, ast.Call) else None
        if isinstance(parent, ast.keyword):
            outer = self.old.parent(parent)
            call = outer if isinstance(outer, ast.Call) else None
        position = call_position(call, old) if call is not None else None
        if call is None or position is None:
            self.fail(old, new, f"nacktes {self.me} außerhalb eines Aufrufs")
            return True
        if named_call(call) is not None and position == "0":
            second = call.args[1]
            assert isinstance(second, ast.Constant)
            member = str(second.value)
            cut = self.shape.cut
            via = (
                ""
                if member in self.shape.moved_names
                else "_host"
                if member in cut.host_members
                else "_parent"
                if member in cut.parent_members
                else None
            )
            if via is None:
                self.fail(old, new, f"{member!r} hat keine Rolle im Zuschnitt")
            else:
                self._expect_bare(old, new, via, f"{member} über {via or 'self'}")
            return True
        func = call.func
        if (
            position == "0"
            and isinstance(func, ast.Attribute)
            and func.attr in self.shape.moved_names
            and self._host_class(func.value)
        ):
            self._expect_bare(old, new, "", "Empfänger des Klassenbezugs")
            return True
        assert self.body is not None
        text, why = self_role(
            self.shape, self.rel, self.body[0].name, call, position, self.old, self.me
        )
        if text is None:
            self.fail(old, new, f"nacktes {self.me} ohne Rolle ({why})")
            return True
        via = text.partition(".")[2]
        self._expect_bare(old, new, via, why)
        return True

    def _expect_bare(self, old: ast.Name, new: ast.AST, via: str, why: str) -> None:
        if not via:
            if self._new_self(new):
                return
            self.fail(old, new, f"erwartet {self.me} ({why})")
            return
        if isinstance(new, ast.Attribute) and new.attr == via and self._new_self(new.value):
            self.accept(f"{self.me} → {self.me}.{via} ({why})")
            return
        self.fail(old, new, f"erwartet {self.me}.{via} ({why})")

    def _global(self, old: ast.Name, new: ast.Name) -> bool:
        """Ein Name, der den Modulnamensraum liest, meint vorher (Wirtsmodul) und nachher
        (Komponentenmodul) dieselbe Bindung."""
        assert self.body is not None and self.new_body is not None
        if not self.body[1].is_global(old):
            return False
        if not self.new_body[1].is_global(new) or old.id != new.id:
            self.fail(old, new, "ein globaler Name wurde lokal oder umbenannt")
            return True
        if old.id == self.shape.cut.host and new.id == self.shape.cut.component_class:
            return True
        before = self.old_top.identity(old.id)
        after = self.new_top.identity(new.id)
        if before == after:
            return True
        typed = ("imp", self.shape.module, old.id, True)
        if (
            before == ("def", self.shape.module, old.id)
            and typed in after[1:]
            and in_annotation(self.old, old)
            and in_annotation(self.new, new)
        ):
            # Nur in einer Annotation: Mit ``from __future__ import annotations`` (der Planer
            # verlangt es in beiden Modulen) wird sie zur Laufzeit nicht ausgewertet.
            self.accept(f"{old.id}: Typ aus dem Wirtsmodul unter TYPE_CHECKING")
            return True
        self.fail(old, new, f"{old.id} meint vorher {before}, nachher {after}")
        return True


# ------------------------------------------------------------------------------ Dateien


class _FileRules(_Rules, ReaderComparison):
    """Eine geänderte Datei im Komponentenmodus."""

    def __init__(self, owner: ComponentProof, path: str) -> None:
        ReaderComparison.__init__(self, owner.trees, path, owner.mapping, owner.values)
        self.owner = owner
        self.shape = owner.shape
        self.rel = path
        self.index_old = owner.trees.old_index
        self.index_new = owner.trees.new_index

    def special(self, old: ast.AST, new: ast.AST) -> bool:
        if self.rules(old, new):
            return True
        return ReaderComparison.special(self, old, new)

    def allowed_module_alias(self, binding: ImportBinding) -> bool:
        return (
            binding.form == "from"
            and binding.module == self.shape.component_module
            and binding.name == self.shape.cut.component_class
        )

    def allowed_removal(self, binding: ImportBinding) -> bool:
        return binding.bound not in loaded_names(self.new.tree)


class ComponentReaderComparison(_FileRules):
    """Ein Leser außerhalb von Wirt und Komponente: Es entfällt nur ein Import von Wirt oder
    Komponente (Modul oder Klasse), den danach niemand mehr liest."""

    def allowed_removal(self, binding: ImportBinding) -> bool:
        shape = self.shape
        modules = (shape.module, shape.component_module)
        own = (
            binding.module in modules
            if binding.form == "import"
            else f"{binding.module}.{binding.name}" in modules
            or (binding.module, binding.name) == (shape.module, shape.cut.host)
            or (binding.module, binding.name) == (shape.component_module, shape.cut.component_class)
        )
        return own and super().allowed_removal(binding)


class HostComparison(_FileRules):
    """Das Modul des Wirts: der Klassenrumpf ohne die verschobenen Methoden, ``self.<m>`` →
    ``self.<attr>.<m>`` in den bleibenden Methoden, Importe fallen nur ungelesen weg."""

    def __init__(self, owner: ComponentProof, path: str) -> None:
        super().__init__(owner, path)
        self.host_class = owner.shape.host_class

    def expected_comments(self, before: Counter[str]) -> Counter[str]:
        return before - self.owner.moved_comments

    def blocks(
        self, owner: ast.AST, old: list[ast.stmt], new: list[ast.stmt]
    ) -> tuple[list[ast.stmt | list[ast.stmt]], list[ast.stmt | list[ast.stmt]]]:
        if owner is self.host_class:
            moved = {id(d) for m in self.shape.methods.values() for d in m.defs}
            old = [s for s in old if id(s) not in moved]
            for stmt in new:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    stmt.name in self.shape.methods
                ):
                    self.fail(stmt, stmt, f"{stmt.name} steht noch im Wirt")
        return super().blocks(owner, old, new)

    def allowed_removal(self, binding: ImportBinding) -> bool:
        return binding.bound in self.owner.read_by_moved and super().allowed_removal(binding)


class ComponentFileComparison(_FileRules):
    """Das Modul der Komponente: der Klassenrumpf gleich bis auf die angehängten Methoden, neue
    Importe nur solche, die die verschobenen Methoden im Wirtsmodul lasen."""

    def expected_comments(self, before: Counter[str]) -> Counter[str]:
        return before + self.owner.moved_comments

    def __init__(self, owner: ComponentProof, path: str) -> None:
        super().__init__(owner, path)
        self.component_class = _class(self.old, owner.cut.component_class)
        host_top = TopLevel(owner.trees.old(owner.path))
        self.needed = {b for name in owner.read_by_moved for b in host_top.imports.get(name, [])}
        self.host_definitions = {name for name in owner.read_by_moved if host_top.units.get(name)}

    def blocks(
        self, owner: ast.AST, old: list[ast.stmt], new: list[ast.stmt]
    ) -> tuple[list[ast.stmt | list[ast.stmt]], list[ast.stmt | list[ast.stmt]]]:
        if owner is self.component_class:
            new = [
                s
                for s in new
                if not (
                    isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and s.name in self.shape.methods
                )
            ]
        return super().blocks(owner, old, new)

    def imports(self, owner: ast.AST, old: list[ast.stmt], new: list[ast.stmt]) -> None:
        """Neu sind nur Importe, die die verschobenen Methoden im Wirtsmodul lasen — im selben
        Kontext (Laufzeit oder ``TYPE_CHECKING``) —, und Typen des Wirtsmoduls, nur unter
        ``TYPE_CHECKING``; ob sie dann nur in Annotationen stehen, prüft
        :meth:`MethodComparison._global` je Stelle."""
        removed, added = _difference(self.path, old, new, self.checking)
        for binding in removed:
            self.errors.append(f"{self.path}: Import {binding.text()} entfernt")
        for binding in added:
            typed = (
                binding.checking
                and binding.form == "from"
                and binding.module == self.shape.module
                and binding.name in self.host_definitions
            )
            if binding in self.needed or typed:
                self.import_changes.append(f"neu {binding.text()}")
            else:
                self.errors.append(
                    f"{self.path}: neuer Import {binding.text()} gehört nicht zu den "
                    "verschobenen Methoden"
                )


def _class(source: Source, name: str) -> ast.ClassDef | None:
    return next(
        (s for s in source.tree.body if isinstance(s, ast.ClassDef) and s.name == name), None
    )
