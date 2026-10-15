"""Komponentenmodus des Verschiebewerkzeugs: Methoden einer Großklasse wandern in eine Komponente.

Konzept Codestruktur 3.3, Plan 2.7 Punkt 8 (E6). Die Komponente steht schon im eigenen Modul
(Gerüst-Commit vor dem Schnitt): ein ``QObject``-Kind des Wirts, das Wirt (``_host``, als
Protokoll) und Qt-Elternteil (``_parent``) schwach hält und ein eigenes ``release()`` hat; der
Wirt baut sie in ``__init__`` als ``self.<host_attribute>`` und ruft ihr ``release()`` vor
``disconnect(self)``. Das Werkzeug verschiebt dann die erklärten Methoden ans Ende der
Komponentenklasse und wendet **genau** die Ersetzungsliste an:

============================================  ================================================
im verschobenen Rumpf                         wird
============================================  ================================================
``self.<eigenes>`` (``methods``,              bleibt
``own_attributes``)
``self.<geteiltes>`` (``host_members``)       ``self._host.<geteiltes>``
von Qt ererbt (``parent_members``)            ``self._parent.<member>``
nacktes ``self`` als Besitzer                 bleibt — die Komponente besitzt
(:data:`OWNER_CALLS`)
nacktes ``self`` als Ereignisfilter           ``self``, wenn ``eventFilter`` mitwandert, sonst
                                              ``self._host``
nacktes ``self`` an einer erklärten Stelle    ``qt_parent`` → ``self._parent``, ``owner`` →
(``[[self_roles]]``)                          ``self``, ``event_filter`` wie oben,
                                              ``flow_host`` → ``self``, wenn der Fluss in ein
                                              eigenes Attribut kommt, sonst ``self._host``
``<Wirt>.<methode>`` als Klassenbezug         ``<Komponente>.<methode>``; ruft er auf, zieht
                                              der Empfänger mit (``x`` → ``x.<host_attribute>``)
============================================  ================================================

Im Wirt und überall sonst (``app/``, ``tools/``, ``tests/``) wird jedes verschobene Member
``<empfänger>.<host_attribute>.<name>`` — als Zugriff, Zuweisungsziel, an
``getattr``/``setattr``/``delattr``, ``monkeypatch.setattr`` und ``patch.object``, als Pfad
``"<modul>.<Wirt>.<name>"`` — aber nur, wenn der Empfänger **nachweislich** der Wirt ist, und
er bleibt nur stehen, wenn er nachweislich etwas anderes ist (``tools/move_receivers.py``: der
Auflöser, dann die Annotation von Parameter, Variable oder Rückgabe). Was offen bleibt — ein
Parameter ohne Annotation, ``timers["main"]`` —, entscheidet eine Erklärung je Stelle
(``[[accesses]]``: Datei, Bereich, Member, ``component`` oder ``keep``), sonst hält der Schnitt an.
Eine Erklärung, die dem Nachweis widerspricht oder nichts entscheidet, ist selbst ein Fund. Dass
kein anderer Ort des Baums ein Member dieses Namens definiert, ist kein Nachweis: Fremde Typen
tragen dieselben Namen (Review 2 über Paket M, RM-M18).

Abgewiesen wird vor dem Schreiben, jeweils mit Ausweg: ein ``self.<x>`` ohne Rolle, ein nacktes
``self`` ohne Rolle, ``super()``, ein verdeckter Name ``self.__x``, eine verschobene Methode
mit ``classmethod``/``staticmethod``, ein Lesen einer Definition des Wirtsmoduls (die Komponente
importiert den Wirt nicht), ein gepatchter Name des Wirtsmoduls, den eine verschobene Methode
liest, ``hasattr`` oder ``getattr`` mit Vorgabe auf ein verschobenes Member, eine Zeichenkette mit
seinem Namen ohne Erklärung, eine Erklärung, die nichts trifft — und was Qt danach anders sähe
(``tools/move_qt.py``): ``self.sender()`` in einem verschobenen Rumpf, eine verschobene
Überschreibung einer Methode der Qt-Basis, ``eventFilter``, wenn der Wirt selbst als Filter
installiert bleibt, und eine Unterklasse des Wirts, die ein verschobenes Member definiert.

**Lebensdauer ist ein eigener Nachweis.** Gleiche Rümpfe heißen nicht gleiche Lebensdauer. Das
Werkzeug prüft am Gerüst statisch, was sich statisch prüfen lässt (:func:`lifetime`); ob nach
``release()`` kein Signal mehr ankommt und der Wirt ohne ``gc.collect`` fort ist, belegt ein
Laufzeittest.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from tools.code_index import Index, Val
from tools.move_compare import (
    FileScopes,
    Scopes,
    TopLevel,
    fixed_parts,
    qualname_of,
    string_constants,
)
from tools.move_cut import Cut
from tools.move_edits import Edit, EditError, apply_text
from tools.move_qt import (
    FILTER_CALLS,
    RECEIVER_MEMBERS,
    class_reference,
    filter_argument,
    qt_bases,
    qt_members,
)
from tools.move_receivers import HOST, NEUTRAL, OPEN, OTHER, Receivers
from tools.move_refs import AlreadyAppliedError, Context, FileRewrite, quoted
from tools.move_source import (
    AREAS,
    BUILTINS,
    IMPORTS,
    Source,
    Span,
    bound_name,
    class_spans,
    import_binders,
    is_type_checking,
    module_of,
    path_of,
)

#: Wer ein nacktes ``self`` als **Besitzer** nimmt (Konzept 3.3): Die Komponente besitzt.
OWNER_CALLS = frozenset(
    {
        "PySide6.QtCore.QTimer",
        "weakref.ref",
        "weakref.WeakMethod",
        "shiboken6.isValid",
        "shiboken6.Shiboken.isValid",
        "app.ui.leash:WorkerLeash",
        "app.ui.leash:weak_slot",
    }
)
#: Aufrufe, deren zweites Argument ein Attributname des ersten ist.
NAMED_CALLS = frozenset({"getattr", "hasattr", "setattr", "delattr"})
#: ``monkeypatch.setattr``/``delattr`` und ``patch.object``: der letzte Teil des Aufrufs.
PATCH_CALLS = frozenset({"setattr", "delattr", "object"})

RULE_BODY = "Komponente: Ersetzungsliste"
RULE_HOST = "Wirt greift über die Komponente zu"
RULE_OUTSIDE = "Zugriff auf ein verschobenes Member"
RULE_CLASS = "Klassenbezug zeigt auf die Komponente"

Method = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass
class Moved:
    """Eine verschobene Methode: ihre Definitionen (Eigenschaft samt Setter) und Spannen."""

    name: str
    defs: list[Method] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)


class Shape:
    """Wirt, Komponente und Protokoll im Baum vor dem Schnitt — gemeinsam für Planer und Beweis,
    beides nur aus dem Zuschnitt und dem Auflöser abgeleitet."""

    def __init__(
        self,
        cut: Cut,
        index: Index,
        host: Source,
        component: Source,
        source_of: Callable[[str], Source | None],
        *,
        before: bool = True,
    ) -> None:
        """``before``: der Baum vor dem Schnitt (die Methoden stehen im Wirt); danach liest die
        Form nur Klassen und Protokoll (für den Lebensdauernachweis am neuen Baum).
        ``source_of`` liefert eine Datei desselben Baums (``None``, wenn es sie nicht gibt)."""
        self.cut = cut
        self.index = index
        self.host_source = host
        self.component_source = component
        self.module = module_of(cut.source)
        #: Ob ein Empfänger nachweislich der Wirt ist (Review 2, RM-M18).
        self.receivers = Receivers(index, self.module, cut.host, source_of)
        self.component_module = cut.component_module
        self.moved_names = set(cut.methods) | set(cut.own_attributes)
        self.problems: list[str] = []
        self.host_class = _class(host, cut.host)
        self.component_class = _class(component, cut.component_class)
        self.protocol = _class(component, cut.host_protocol)
        self.methods: dict[str, Moved] = {}
        self.unique: dict[str, list[str]] = {}
        #: Die Namen der Qt-Basen von Wirt und Komponente (:meth:`_qt_overrides`).
        self.qt_names: frozenset[str] = frozenset()
        if self.host_class is None:
            self.problems.append(f"{cut.source}: keine Klasse {cut.host} auf Modulebene — prüfen")
            return
        if self.component_class is None:
            self.problems.append(
                f"{path_of(self.component_module)}: keine Klasse {cut.component_class} — die "
                "Komponente (QObject-Kind, schwache _host und _parent, release) vorher im "
                "Gerüst-Commit anlegen"
            )
        if self.protocol is None:
            self.problems.append(
                f"{path_of(self.component_module)}: kein Wirtsprotokoll {cut.host_protocol} — "
                "vorher im Gerüst-Commit erheben"
            )
        if before:
            self._methods()

    def _methods(self) -> None:
        assert self.host_class is not None
        cls = self.host_class
        for stmt, span in zip(cls.body, class_spans(self.host_source, cls), strict=True):
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if stmt.name in self.cut.methods:
                    moved = self.methods.setdefault(stmt.name, Moved(stmt.name))
                    moved.defs.append(stmt)
                    moved.spans.append(span)
                continue
            for name in _class_level_names(stmt):
                if name in self.moved_names:
                    self.problems.append(
                        f"{self.cut.source}:{stmt.lineno}: {name} ist ein Klassenattribut von "
                        f"{self.cut.host} — wandert nicht; vorher im Gerüst-Commit klären"
                    )
        for name in self.cut.methods:
            if name not in self.methods:
                self.problems.append(
                    f"methods: {self.cut.host}.{name} gibt es nicht — Namen prüfen"
                )
        if len(self.methods) and all(
            isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and s.name in self.methods
            for s in cls.body
        ):
            self.problems.append(
                f"{self.cut.source}: es wanderte der ganze Rumpf von {self.cut.host} — der Wirt "
                "behält mindestens __init__ und release"
            )
        for moved in self.methods.values():
            for method in moved.defs:
                for decorator in method.decorator_list:
                    text = ast.unparse(decorator)
                    if text in ("classmethod", "staticmethod"):
                        self.problems.append(
                            f"{self.cut.source}:{method.lineno}: {moved.name} ist @{text} — die "
                            "Ersetzungsliste kennt nur Methoden mit self; vorher umschreiben"
                        )
                if self_name(method) is None:
                    self.problems.append(
                        f"{self.cut.source}:{method.lineno}: {moved.name} hat kein self — "
                        "vorher umschreiben"
                    )
        self._receivers()
        self._qt_overrides()

    def _receivers(self) -> None:
        """``self.sender()`` in einem verschobenen Rumpf (``tools/move_qt.py``)."""
        scopes = FileScopes(self.host_source)
        for moved in self.methods.values():
            for method in moved.defs:
                me = self_name(method)
                if me is None:
                    continue
                for node in ast.walk(method):
                    first: ast.expr | None = None
                    member = ""
                    if isinstance(node, ast.Attribute) and node.attr in RECEIVER_MEMBERS:
                        first, member = node.value, node.attr
                    elif isinstance(node, ast.Call) and named_call(node) in NAMED_CALLS:
                        second = node.args[1]
                        assert isinstance(second, ast.Constant)
                        if second.value in RECEIVER_MEMBERS:
                            first, member = node.args[0], str(second.value)
                    if not (
                        isinstance(first, ast.Name)
                        and first.id == me
                        and refers_to(scopes.of(method), method, first, me)
                    ):
                        continue
                    self.problems.append(
                        f"{self.cut.source}:{first.lineno}: {me}.{member}() in "
                        f"{self.cut.host}.{moved.name} gilt dem Empfänger eines Signals — nach "
                        "dem Schnitt wäre das die Komponente oder niemand; vorher den Sender als "
                        "Argument übergeben (connect mit functools.partial oder lambda) oder die "
                        "Methode im Wirt lassen"
                    )

    def _qt_overrides(self) -> None:
        """Eine verschobene Methode, die eine Methode der Qt-Basis von Wirt oder Komponente
        überschreibt (``eventFilter`` prüft :meth:`scan_uniqueness`)."""
        assert self.host_class is not None
        refs, unresolved = qt_bases(self.index, self.cut.source, self.host_class)
        if self.component_class is not None:
            more, missing = qt_bases(
                self.index, path_of(self.component_module), self.component_class
            )
            refs, unresolved = sorted({*refs, *more}), [*unresolved, *missing]
        for text in unresolved:
            self.problems.append(
                f"{text}: eine Basis, die sich nicht auflöst — ob eine verschobene Methode Qt "
                "überschreibt, ist so nicht prüfbar; vorher die Basis als Import schreiben"
            )
        members, failed = qt_members(refs)
        self.qt_names = members
        for text in failed:
            self.problems.append(
                f"Qt-Basis {text} lässt sich nicht laden — ob eine verschobene Methode Qt "
                "überschreibt, ist so nicht prüfbar; Umgebung prüfen (PySide6)"
            )
        for name, moved in self.methods.items():
            if name in members and name != "eventFilter":
                self.problems.append(
                    f"{self.cut.source}:{moved.defs[0].lineno}: {name} überschreibt eine Methode "
                    f"der Qt-Basis ({', '.join(refs)}) — Qt ruft sie am Wirt, in der Komponente "
                    "riefe Qt sie anders oder nie; sie bleibt im Wirt (Konzept 3.3), aus methods "
                    "streichen"
                )

    # ---- Fragen an die Form

    def scope_name(self, method: str) -> str:
        return f"{self.cut.host}.{method}"

    def is_host_class(self, values: frozenset[Val]) -> bool:
        return bool(values) and all(
            v.kind == "class" and v.ref == f"{self.module}:{self.cut.host}" for v in values
        )

    def moved_method_of(self, node: ast.AST) -> tuple[Moved, Method] | None:
        """Die verschobene Methode, in deren Spanne ``node`` steht."""
        line = getattr(node, "lineno", 0)
        for moved in self.methods.values():
            for method, span in zip(moved.defs, moved.spans, strict=True):
                if span.first <= line <= span.last:
                    return moved, method
        return None

    def decision(
        self, path: str, source: Source, scope: str, member: str, node: ast.expr
    ) -> tuple[str | None, str]:
        """Ob ein Zugriff ``<node>.member`` in ``path`` dem Wirt gilt: ``("component" | "keep",
        Grund)`` oder ``(None, Grund samt Ausweg)``. Umgeschrieben wird nur, was nachweislich
        dem Wirt gilt; was der Nachweis offen lässt, entscheidet ``[[accesses]]``, und eine
        Erklärung, die dem Nachweis widerspricht oder nichts entscheidet, ist selbst ein Fund
        (Review 2, RM-M18; :mod:`tools.move_receivers`)."""
        judged = self.receivers.judge(path, source, node)
        declared = next(
            (
                access.decision
                for access in self.cut.accesses
                if (access.path, access.scope, access.member) == (path, scope, member)
            ),
            None,
        )
        if declared is not None:
            if judged.verdict == OPEN:
                return declared, "erklärt in accesses"
            proven = "component" if judged.verdict == HOST else "keep"
            if proven != declared:
                return None, (
                    f"erklärt als {declared}, aber {judged.why} — die Erklärung in [[accesses]] "
                    "berichtigen oder streichen"
                )
            return None, (
                f"erklärt als {declared}, doch das steht schon fest ({judged.why}) — die "
                "Erklärung in [[accesses]] streichen; sie gilt nur, wo der Nachweis offen bleibt"
            )
        if judged.verdict == HOST:
            return "component", judged.why
        if judged.verdict in (OTHER, NEUTRAL):
            return "keep", judged.why
        others = self.unique.get(member, [])
        also = f"; {member!r} gibt es auch in {', '.join(others[:3])}" if others else ""
        return None, (
            f"Empfänger nicht nachweislich der Wirt ({judged.why}){also} — in [[accesses]] "
            "entscheiden (component oder keep) oder den Empfänger nachweisbar schreiben "
            "(Annotation)"
        )

    def needles(self) -> tuple[str, ...]:
        """Was eine Datei nennen muss, damit der Schnitt sie liest: ein verschobener Name, den
        Wirt (eine Unterklasse) oder ``EventFilter(`` (den Wirt als Ereignisfilter)."""
        return (*sorted(self.moved_names), self.cut.host, "EventFilter(")

    def scan_uniqueness(self, files: Iterator[tuple[str, Source]]) -> None:
        """Wo ein Member gleichen Namens außerhalb von Wirt und Komponente definiert wird:
        Methode, Klassenattribut, ``self.<name> = …`` in einer Methode, Schlüsselwort eines
        Aufrufs (``SimpleNamespace(count=…)``) — Konzept 4.1, W5. Dazu, was nach dem Schnitt
        anders wirkte (``tools/move_qt.py``): eine Unterklasse des Wirts, die ein verschobenes
        Member definiert, und der Wirt als installierter Ereignisfilter, wenn ``eventFilter``
        wandert. Die Funde stehen danach in :attr:`problems`."""
        found: dict[str, list[str]] = {name: [] for name in self.moved_names}
        classes: list[tuple[str, Source, ast.ClassDef]] = []
        for path, source in files:
            for node in ast.walk(source.tree):
                if isinstance(node, ast.ClassDef):
                    own = (path == self.cut.source and node.name == self.cut.host) or (
                        module_of(path) == self.component_module
                        and node.name in (self.cut.component_class, self.cut.host_protocol)
                    )
                    if own:
                        continue
                    for name in _class_members(node):
                        if name in found:
                            found[name].append(f"{path}:{node.lineno} ({node.name})")
                    classes.append((path, source, node))
                elif isinstance(node, ast.keyword) and node.arg in found:
                    found[node.arg].append(f"{path}:{node.lineno} (Schlüsselwort)")
                elif isinstance(node, ast.Call) and "eventFilter" in self.methods:
                    self._host_filter(path, source, node)
        self.unique = {name: places for name, places in found.items() if places}
        self._subclasses(classes)

    def _host_filter(self, path: str, source: Source, call: ast.Call) -> None:
        """``x.installEventFilter(<Wirt>)`` außerhalb der verschobenen Rümpfe: Danach filterte
        niemand, denn ``eventFilter`` wandert."""
        argument = filter_argument(call)
        if argument is None:
            return
        if path == self.cut.source and self.moved_method_of(call) is not None:
            return
        if self.receivers.judge(path, source, argument).verdict != HOST:
            return
        self.problems.append(
            f"{path}:{call.lineno}: installiert den Wirt {self.cut.host} als Ereignisfilter, "
            "eventFilter wandert aber — danach filterte niemand; die Installation mit in die "
            "Komponente ziehen (eine verschobene Methode) oder eventFilter im Wirt lassen"
        )

    def _subclasses(self, classes: list[tuple[str, Source, ast.ClassDef]]) -> None:
        """Eine Unterklasse des Wirts (auch über Zwischenklassen, die in Dateien ohne Bezug zum
        Schnitt stehen — :meth:`Receivers.class_kind` folgt den Basen selbst), die ein
        verschobenes Member definiert: Danach riefe der Wirt die Fassung der Komponente, nicht
        ihre."""
        for path, source, node in classes:
            own = sorted(_class_members(node) & self.moved_names)
            ref = class_reference(module_of(path), source, node)
            if own and self.receivers.class_kind(ref) == HOST:
                self.problems.append(
                    f"{path}:{node.lineno}: {node.name} erbt von {self.cut.host} und definiert "
                    f"{', '.join(own)} — nach dem Schnitt riefe der Wirt die Fassung der "
                    "Komponente, nicht diese; vorher die Unterklasse auf die Komponente "
                    "umstellen (etwa das Member der Komponente des Exemplars ersetzen)"
                )


def self_name(method: Method) -> str | None:
    args = [*method.args.posonlyargs, *method.args.args]
    return args[0].arg if args else None


def self_role(
    shape: Shape,
    path: str,
    method: str,
    call: ast.Call,
    position: str,
    source: Source,
    me: str,
) -> tuple[str | None, str]:
    """Die Rolle eines nackten ``self`` als Argument ``position`` von ``call`` in der Methode
    ``method``: der Ersatztext (``self``, ``self._parent``, ``self._host``) und der Grund, oder
    ``None``, wenn keine Rolle feststeht."""
    func = source.node_text(call.func)
    stays = me
    for role in shape.cut.self_roles:
        if role.scope != shape.scope_name(method) or role.call != func:
            continue
        if role.argument != position:
            continue
        if role.role == "qt_parent":
            return f"{me}._parent", "Qt-Elternteil (erklärt)"
        if role.role == "owner":
            return stays, "Besitzer (erklärt)"
        if role.role == "event_filter":
            return _filter(shape, me)
        moves = _assigned_to_own(shape, source, call, me)
        if moves:
            return stays, "Wirt eines Flusses, der in die Komponente zieht (erklärt)"
        return f"{me}._host", "Wirt eines Flusses, der beim Wirt bleibt (erklärt)"
    if isinstance(call.func, ast.Attribute) and call.func.attr in FILTER_CALLS and position == "0":
        return _filter(shape, me)
    values = shape.index.resolve(path, call.func)
    if values and all(v.ref in OWNER_CALLS for v in values):
        return stays, f"Besitzer ({func})"
    return None, f"{func}(…) Argument {position}"


def _filter(shape: Shape, me: str) -> tuple[str, str]:
    if "eventFilter" in shape.cut.methods:
        return me, "Ereignisfilter, eventFilter zieht mit"
    return f"{me}._host", "Ereignisfilter, eventFilter bleibt beim Wirt"


def _assigned_to_own(shape: Shape, source: Source, call: ast.Call, me: str) -> bool:
    parent = source.parent(call)
    return (
        isinstance(parent, ast.Assign)
        and len(parent.targets) == 1
        and isinstance(parent.targets[0], ast.Attribute)
        and isinstance(parent.targets[0].value, ast.Name)
        and parent.targets[0].value.id == me
        and parent.targets[0].attr in shape.cut.own_attributes
    )


def refers_to(scopes: Scopes, method: Method, node: ast.Name, name: str) -> bool:
    """Ob ``node`` (ein Name ``name`` im Rumpf von ``method``) den Parameter ``name`` der Methode
    meint — nicht einen gleichnamigen Parameter oder Namen einer inneren Funktion."""
    current: ast.AST = node
    for outer in scopes.source.ancestors(node):
        if outer is method:
            return any(current is s for s in method.body) or current in method.decorator_list
        if isinstance(outer, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            targets = {
                t.id
                for g in outer.generators
                for t in ast.walk(g.target)
                if isinstance(t, ast.Name)
            }
            if name in targets and current is not outer.generators[0].iter:
                return False
        if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            inside = (
                current is outer.body
                if isinstance(outer, ast.Lambda)
                else any(current is s for s in outer.body)
            )
            if inside:
                table = scopes.table_of.get(id(outer))
                if table is None or name not in table.get_identifiers():
                    current = outer
                    continue
                symbol = table.lookup(name)
                if symbol.is_local() or symbol.is_parameter():
                    return False
        current = outer
    return False


def call_position(call: ast.Call, node: ast.AST) -> str | None:
    """Die Stelle von ``node`` unter den Argumenten von ``call``: Zahl oder Schlüsselwort."""
    for number, argument in enumerate(call.args):
        if argument is node:
            return str(number)
    for keyword in call.keywords:
        if keyword.value is node and keyword.arg:
            return keyword.arg
    return None


def named_call(call: ast.Call) -> str | None:
    """``getattr``/``hasattr``/``setattr``/``delattr`` oder ``…setattr``/``…delattr``/
    ``…patch.object`` mit festem Namen an zweiter Stelle: die Art, sonst ``None``."""
    if len(call.args) < 2:
        return None
    second = call.args[1]
    if not isinstance(second, ast.Constant) or not isinstance(second.value, str):
        return None
    if isinstance(call.func, ast.Name) and call.func.id in NAMED_CALLS:
        return call.func.id
    if isinstance(call.func, ast.Attribute) and call.func.attr in PATCH_CALLS:
        return call.func.attr
    return None


def receiver_text(source: Source, node: ast.expr, attribute: str) -> str:
    """``x`` → ``x.<attribute>``, geklammert, wo der Vorrang es verlangt."""
    text = source.node_text(node)
    if not isinstance(node, (ast.Name, ast.Attribute, ast.Call, ast.Subscript)):
        text = f"({text})"
    return f"{text}.{attribute}"


# ------------------------------------------------------------------------------ Planer


@dataclass
class ComponentPlan:
    edits: dict[str, list[Edit]]
    notes: list[str]


class ComponentPlanner:
    """Plant den Schnitt einer Komponente aus ihrem Wirt; Funde sammelt ``ctx``."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.cut = ctx.cut
        self.path = self.cut.source
        self.component_path = path_of(self.cut.component_module)
        self.notes: list[str] = []
        self.body_edits: list[Edit] = []
        self.used_roles: set[int] = set()
        self.used_accesses: set[tuple[str, str, str]] = set()

    def plan(self) -> ComponentPlan:
        root = self.ctx.root
        for path in (self.path, self.component_path):
            if not (root / path).is_file():
                self.ctx.problem(
                    f"{path} fehlt — Wirt und Komponente (Gerüst-Commit) müssen im Baum stehen"
                )
        self.ctx.raise_problems()
        self.host = self.ctx.source(self.path)
        self.component = self.ctx.source(self.component_path)
        if _applied(self.cut, self.host, self.component):
            raise AlreadyAppliedError(
                f"{self.cut.component} trägt schon {', '.join(self.cut.methods)}, "
                f"{self.cut.host} keine davon — der Schnitt ist angewandt; nichts zu tun"
            )
        self.shape = Shape(
            self.cut, self.ctx.index, self.host, self.component, self._source_or_none
        )
        for problem in self.shape.problems:
            self.ctx.problem(problem)
        self.ctx.raise_problems()
        self.shape.scan_uniqueness(self._files())
        for problem in self.shape.problems:
            self.ctx.problem(problem)
        self.ctx.raise_problems()
        self.host_scopes = FileScopes(self.host)
        for moved in self.shape.methods.values():
            for method in moved.defs:
                self._body(moved, method)
        self._dependencies()
        self.ctx.raise_problems()
        self._host_side()
        self._outside()
        for problem in lifetime(self.shape):
            self.ctx.problem(problem)
        self._declared_used()
        self.ctx.raise_problems()
        self._move()
        self.ctx.raise_problems()
        edits: dict[str, list[Edit]] = {}
        for path, rewrite in sorted(self.ctx.rewrites().items()):
            found = rewrite.finish()
            if found:
                edits[path] = found
        self.ctx.raise_problems()
        return ComponentPlan(edits, self.notes)

    def _source_or_none(self, path: str) -> Source | None:
        return self.ctx.source(path) if (self.ctx.root / path).is_file() else None

    def _files(self) -> Iterator[tuple[str, Source]]:
        names = self.shape.needles()
        for area in AREAS:
            base = self.ctx.root / area
            if not base.is_dir():
                continue
            for full in sorted(base.rglob("*.py")):
                relative = full.relative_to(self.ctx.root).as_posix()
                if any(p == "__pycache__" or p.startswith(".") for p in relative.split("/")[:-1]):
                    continue
                if not any(n in full.read_bytes().decode("utf-8", "replace") for n in names):
                    continue
                yield relative, self.ctx.source(relative)

    # ------------------------------------------------------------------ verschobene Rümpfe

    def _edit(self, node: ast.AST, text: str, detail: str) -> None:
        self.body_edits.append(Edit.at(self.path, "expr", node, text, RULE_BODY, detail))

    def _body(self, moved: Moved, method: Method) -> None:
        me = self_name(method)
        assert me is not None
        scopes = self.host_scopes.of(method)
        label = f"{self.cut.host}.{moved.name}"
        for node in ast.walk(method):
            if isinstance(node, ast.Name) and node.id == me:
                if refers_to(scopes, method, node, me):
                    self._self(moved, method, node, me)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "super"
            ):
                self.ctx.problem(
                    f"{self.path}:{node.lineno}: super() in {label} — in der Komponente hieße "
                    "es etwas anderes; vorher ohne super() schreiben oder im Wirt lassen"
                )
            elif isinstance(node, ast.Attribute) and node.attr in self.shape.moved_names:
                base = node.value
                if (
                    isinstance(base, ast.Name)
                    and base.id == me
                    and refers_to(scopes, method, base, me)
                ):
                    continue
                self._access(self.path, node, base, node.attr, label, body=True)
            elif isinstance(node, ast.Call) and named_call(node) is not None:
                self._named(self.path, node, label, body=(method, me, scopes))
        for node in string_constants(self.host):
            if _inside(method, node):
                self._string(self.path, node, label, body=True)
        for part in fixed_parts(self.ctx.index, self.path, self.host):
            if _inside(method, part):
                self._fixed_part(self.path, part, label)

    def _self(self, moved: Moved, method: Method, node: ast.Name, me: str) -> None:
        source = self.host
        label = f"{self.cut.host}.{moved.name}"
        parent = source.parent(node)
        if isinstance(parent, ast.Attribute) and parent.value is node:
            member = parent.attr
            if member.startswith("__") and not member.endswith("__"):
                self.ctx.problem(
                    f"{self.path}:{node.lineno}: {me}.{member} in {label} — ein verdeckter Name "
                    "hängt am Klassennamen; vorher umbenennen"
                )
            elif member in self.shape.moved_names:
                return
            elif member in self.cut.host_members:
                self._edit(node, f"{me}._host", f"{me}.{member} → {me}._host.{member}")
            elif member in self.cut.parent_members:
                self._edit(node, f"{me}._parent", f"{me}.{member} → {me}._parent.{member}")
            else:
                self.ctx.problem(
                    f"{self.path}:{node.lineno}: {me}.{member} in {label} hat keine Rolle — in "
                    "methods/own_attributes, host_members oder parent_members eintragen"
                )
            return
        if not isinstance(node.ctx, ast.Load):
            self.ctx.problem(f"{self.path}:{node.lineno}: {me} wird in {label} neu gebunden")
            return
        call = parent if isinstance(parent, ast.Call) else None
        if isinstance(parent, ast.keyword):
            outer = source.parent(parent)
            call = outer if isinstance(outer, ast.Call) else None
        position = call_position(call, node) if call is not None else None
        if call is None or position is None:
            self.ctx.problem(
                f"{self.path}:{node.lineno}: nacktes {me} in {label} außerhalb eines Aufrufs — "
                "in der Komponente wäre es etwas anderes; vorher umschreiben"
            )
            return
        if named_call(call) is not None and position == "0":
            self._named_self(call, me, label)
            return
        if self._class_call(call) and position == "0":
            return  # ``Wirt.m(self, …)``: der Klassenbezug wird ``Komponente.m(self, …)``
        text, why = self_role(self.shape, self.path, moved.name, call, position, source, me)
        self._mark_role(moved.name, call, position)
        if text is None:
            self.ctx.problem(
                f"{self.path}:{node.lineno}: nacktes {me} in {label} an {why} ohne Rolle — in "
                "[[self_roles]] erklären (qt_parent, owner, event_filter, flow_host)"
            )
            return
        self.notes.append(f"{self.path}:{node.lineno}: {label}: {me} → {text} ({why})")
        if text != me:
            self._edit(node, text, f"{me} → {text} ({why})")

    def _mark_role(self, method: str, call: ast.Call, position: str) -> None:
        func = self.host.node_text(call.func)
        for number, role in enumerate(self.cut.self_roles):
            if (role.scope, role.call, role.argument) == (
                self.shape.scope_name(method),
                func,
                position,
            ):
                self.used_roles.add(number)

    def _named_self(self, call: ast.Call, me: str, label: str) -> None:
        """``getattr(self, "x")`` im Rumpf: wie ``self.x``."""
        second = call.args[1]
        assert isinstance(second, ast.Constant)
        member = str(second.value)
        first = call.args[0]
        if member in self.shape.moved_names:
            return
        if member in self.cut.host_members:
            self._edit(first, f"{me}._host", f"{me} → {me}._host ({member})")
        elif member in self.cut.parent_members:
            self._edit(first, f"{me}._parent", f"{me} → {me}._parent ({member})")
        else:
            self.ctx.problem(
                f"{self.path}:{call.lineno}: {member!r} in {label} hat keine Rolle — in "
                "methods/own_attributes, host_members oder parent_members eintragen"
            )

    def _class_call(self, call: ast.Call) -> bool:
        func = call.func
        return (
            isinstance(func, ast.Attribute)
            and func.attr in self.shape.moved_names
            and self.shape.is_host_class(self.ctx.index.resolve(self.path, func.value))
        )

    # ------------------------------------------------------------------ Zugriffe

    def _access(
        self, path: str, node: ast.Attribute, base: ast.expr, member: str, scope: str, *, body: bool
    ) -> None:
        """``<empfänger>.member`` außerhalb der Komponente (auch im verschobenen Rumpf mit
        fremdem Empfänger)."""
        values = self.ctx.index.resolve(path, base)
        if self.shape.is_host_class(values):
            self._class_reference(path, node, base, body=body)
            return
        if body:
            self._decide_body(node, base, member, scope)
            return
        rewrite = self.ctx.rewrite(path)
        if rewrite.covered(base):
            return
        decision, _why = self._decide(path, scope, member, base, node.lineno)
        if decision == "component":
            rewrite.replace(
                base, receiver_text(rewrite.source, base, self.cut.host_attribute), RULE_OUTSIDE
            )

    def _decide_body(self, node: ast.Attribute, base: ast.expr, member: str, scope: str) -> None:
        decision, _why = self._decide(self.path, scope, member, base, node.lineno)
        if decision == "component":
            text = receiver_text(self.host, base, self.cut.host_attribute)
            self._edit(base, text, f"{self.host.node_text(base)} → {text}")

    def _decide(
        self, path: str, scope: str, member: str, receiver: ast.expr, line: int
    ) -> tuple[str | None, str]:
        """Die Entscheidung über den Zugriff ``<receiver>.member`` (:meth:`Shape.decision`);
        ohne Entscheidung ein Fund mit Grund und Ausweg."""
        source = self.host if path == self.path else self.ctx.source(path)
        decision, why = self.shape.decision(path, source, scope, member, receiver)
        if any((a.path, a.scope, a.member) == (path, scope, member) for a in self.cut.accesses):
            self.used_accesses.add((path, scope, member))
        if decision is None:
            self.ctx.problem(f"{path}:{line}: Zugriff auf {member} ({scope}) — {why}")
        return decision, why

    def _named(
        self,
        path: str,
        call: ast.Call,
        scope: str,
        *,
        body: tuple[Method, str, Scopes] | None = None,
    ) -> None:
        """``getattr(x, "m")``, ``monkeypatch.setattr(x, "m", …)``, ``patch.object(x, "m")``."""
        kind = named_call(call)
        second = call.args[1]
        assert kind is not None and isinstance(second, ast.Constant)
        member = str(second.value)
        if member not in self.shape.moved_names:
            return
        first = call.args[0]
        if body is not None:
            method, me, scopes = body
            if (
                isinstance(first, ast.Name)
                and first.id == me
                and refers_to(scopes, method, first, me)
            ):
                return  # nacktes self: _self
        values = self.ctx.index.resolve(path, first)
        if self.shape.is_host_class(values):
            self._class_reference(path, None, first, body=body is not None)
            return
        decision, _why = self._decide(path, scope, member, first, call.lineno)
        if decision != "component":
            return
        if kind == "hasattr" or (kind == "getattr" and len(call.args) > 2):
            self.ctx.problem(
                f"{path}:{call.lineno}: {kind}(…, {member!r}{', …' if len(call.args) > 2 else ''}) "
                "auf ein verschobenes Member — vorher als gewöhnlichen Zugriff ohne Vorgabe "
                "schreiben (Konzept 3.3)"
            )
            return
        if body is not None:
            text = receiver_text(self.host, first, self.cut.host_attribute)
            self._edit(first, text, f"{self.host.node_text(first)} → {text}")
            return
        rewrite = self.ctx.rewrite(path)
        rewrite.replace(
            first, receiver_text(rewrite.source, first, self.cut.host_attribute), RULE_OUTSIDE
        )

    def _class_reference(
        self, path: str, node: ast.Attribute | None, base: ast.expr, *, body: bool
    ) -> None:
        """``Wirt.m`` wird ``Komponente.m``; ruft es auf, zieht der Empfänger mit."""
        component = self.cut.component_class
        if body:
            self._edit(base, component, f"{self.cut.host} → {component}")
        else:
            rewrite = self.ctx.rewrite(path)
            text = self._component_expression(rewrite, base)
            if text is None:
                return
            rewrite.replace(base, text, RULE_CLASS)
        if node is None:
            return
        source = self.host if body else self.ctx.rewrite(path).source
        call = source.parent(node)
        if not (isinstance(call, ast.Call) and call.func is node and call.args):
            return
        first = call.args[0]
        if body:
            if isinstance(first, ast.Name) and first.id == "self":
                return
            text = receiver_text(source, first, self.cut.host_attribute)
            self._edit(first, text, f"{source.node_text(first)} → {text}")
            return
        rewrite = self.ctx.rewrite(path)
        rewrite.replace(first, receiver_text(source, first, self.cut.host_attribute), RULE_CLASS)

    def _component_expression(self, rewrite: FileRewrite, base: ast.expr) -> str | None:
        """Ein Ausdruck für die Komponentenklasse an der Stelle von ``base`` (dem Wirt)."""
        component = self.cut.component_class
        module = self.cut.component_module
        if isinstance(base, ast.Attribute):
            text = rewrite.module_expression(base.value, module, self.shape.module, RULE_CLASS)
            return f"{text}.{component}" if text is not None else None
        if not isinstance(base, ast.Name):
            self.ctx.problem(
                f"{rewrite.path}:{base.lineno}: Klassenbezug über "
                f"{rewrite.source.node_text(base)!r} — vor dem Schnitt über den Namen der "
                "Klasse schreiben"
            )
            return None
        if rewrite.path == self.path:
            top = TopLevel(self.host)
            for name, bindings in top.imports.items():
                if any(
                    b.form == "from"
                    and (b.module, b.name) == (module, component)
                    and not b.checking
                    for b in bindings
                ):
                    return name
            self.ctx.problem(
                f"{self.path}: importiert {component} nicht zur Laufzeit — im Gerüst-Commit "
                "ergänzen"
            )
            return None
        binders = import_binders(rewrite.source, base.id, base)
        if not binders:
            self.ctx.problem(
                f"{rewrite.path}:{base.lineno}: {base.id} ist der Wirt, aber nicht über einen "
                "Import gebunden — vor dem Schnitt als Import schreiben"
            )
            return None
        top = TopLevel(rewrite.source)
        for name, bindings in top.imports.items():
            if any(
                b.form == "from" and (b.module, b.name) == (module, component) and not b.checking
                for b in bindings
            ):
                rewrite.watch_name(binders, base.id)
                return name
        if component in rewrite.identifiers:
            self.ctx.problem(
                f"{rewrite.path}: der Name {component} ist dort vergeben — vor dem Schnitt "
                "umbenennen"
            )
            return None
        text = f"from {module} import {component}"
        for binder in binders:
            rewrite.add_import(binder, text, RULE_CLASS)
        rewrite.watch_name(binders, base.id)
        return component

    def _string(self, path: str, node: ast.Constant, scope: str, *, body: bool = False) -> None:
        """Eine Zeichenkette mit dem Namen eines verschobenen Members oder dem Pfad
        ``"<modul>.<Wirt>.<m>"``."""
        value = str(node.value)
        prefix = f"{self.shape.module}.{self.cut.host}."
        rest = value[len(prefix) :]
        if value.startswith(prefix) and rest.split(".")[0] in self.shape.moved_names:
            source = self.host if body else self.ctx.rewrite(path).source
            new = f"{self.cut.component_module}.{self.cut.component_class}.{rest}"
            text = quoted(source, node, new)
            if body:
                self._edit(node, text, f"{value!r} → {new!r}")
            else:
                self.ctx.rewrite(path).replace(node, text, RULE_CLASS)
            return
        if value not in self.shape.moved_names:
            return
        parent = (self.host if path == self.path else self.ctx.source(path)).parent(node)
        if (
            isinstance(parent, ast.Call)
            and len(parent.args) > 1
            and parent.args[1] is node
            and named_call(parent) is not None
        ):
            return  # über _named
        for access in self.cut.accesses:
            if (access.path, access.scope, access.member) == (path, scope, value):
                self.used_accesses.add((path, scope, value))
                if access.decision == "keep":
                    return
        self.ctx.problem(
            f"{path}:{node.lineno}: Zeichenkette {value!r} ({scope}) nennt ein verschobenes "
            'Member — als Zugriff schreiben oder in [[accesses]] mit decision = "keep" erklären'
        )

    # ------------------------------------------------------------------ Wirt und außen

    def _host_side(self) -> None:
        """In den bleibenden Methoden des Wirts wird ``self.<m>`` zu ``self.<attr>.<m>``."""
        cls = self.shape.host_class
        assert cls is not None
        rewrite = self.ctx.rewrite(self.path)
        attribute = self.cut.host_attribute
        built: int | None = None
        early: list[int] = []
        for stmt in cls.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if stmt.name in self.shape.methods:
                continue
            me = self_name(stmt)
            scopes = self.host_scopes.of(stmt)
            label = f"{self.cut.host}.{stmt.name}"

            def mine(
                node: ast.expr, me: str | None = me, stmt: Method = stmt, scopes: Scopes = scopes
            ) -> bool:
                return (
                    me is not None
                    and isinstance(node, ast.Name)
                    and node.id == me
                    and refers_to(scopes, stmt, node, me)
                )

            for node in ast.walk(stmt):
                if isinstance(node, ast.Attribute) and mine(node.value):
                    if node.attr == attribute and stmt.name == "__init__":
                        parent = self.host.parent(node)
                        if isinstance(parent, ast.Assign) and node in parent.targets:
                            built = node.lineno if built is None else built
                    if node.attr in self.shape.moved_names:
                        rewrite.replace(node.value, f"{me}.{attribute}", RULE_HOST)
                        if stmt.name == "__init__":
                            early.append(node.lineno)
                elif isinstance(node, ast.Attribute) and node.attr in self.shape.moved_names:
                    self._access(self.path, node, node.value, node.attr, label, body=False)
                elif isinstance(node, ast.Call) and named_call(node) is not None:
                    first = node.args[0]
                    second = node.args[1]
                    assert isinstance(second, ast.Constant)
                    if not mine(first) or second.value not in self.shape.moved_names:
                        self._named(self.path, node, label)
                        continue
                    kind = named_call(node)
                    if kind == "hasattr" or (kind == "getattr" and len(node.args) > 2):
                        self.ctx.problem(
                            f"{self.path}:{node.lineno}: {kind}({me}, {second.value!r}…) — "
                            "vorher als gewöhnlichen Zugriff schreiben (Konzept 3.3)"
                        )
                        continue
                    rewrite.replace(first, f"{me}.{attribute}", RULE_HOST)
            for node in string_constants(self.host):
                if _inside(stmt, node):
                    self._string(self.path, node, label)
            for part in fixed_parts(self.ctx.index, self.path, self.host):
                if _inside(stmt, part):
                    self._fixed_part(self.path, part, label)
        if built is None:
            self.ctx.problem(
                f"{self.path}: {self.cut.host}.__init__ baut die Komponente nicht "
                f"(self.{attribute} = {self.cut.component_class}(…)) — im Gerüst-Commit ergänzen"
            )
        elif any(line < built for line in early):
            self.ctx.problem(
                f"{self.path}: {self.cut.host}.__init__ nutzt verschobene Member vor dem Bau der "
                f"Komponente (Zeile {built}) — den Bau davor stellen"
            )

    def _outside(self) -> None:
        cls = self.shape.host_class
        assert cls is not None
        for path, source in self._files():
            if path == self.component_path:
                continue
            for node in ast.walk(source.tree):
                if path == self.path and _inside(cls, node):
                    continue
                scope = qualname_of(source, node)
                if isinstance(node, ast.Attribute) and node.attr in self.shape.moved_names:
                    self._access(path, node, node.value, node.attr, scope, body=False)
                elif isinstance(node, ast.Call) and named_call(node) is not None:
                    self._named(path, node, scope)
            for constant in string_constants(source):
                if path == self.path and _inside(cls, constant):
                    continue
                self._string(path, constant, qualname_of(source, constant))
            for part in fixed_parts(self.ctx.index, path, source):
                self._fixed_part(path, part, qualname_of(source, part))

    def _fixed_part(self, path: str, node: ast.Constant, scope: str) -> None:
        """Der feste Teil eines f-Strings, den der Auflöser nicht faltet: Er lässt sich nicht
        umschreiben — nennt er den Pfad eines verschobenen Members oder das Member selbst
        (ohne Erklärung ``keep``), hält der Schnitt an (Review 2, RM-M22)."""
        value = str(node.value)
        prefix = f"{self.shape.module}.{self.cut.host}."
        rest = value.partition(prefix)[2] if prefix in value else None
        if rest is not None and rest.split(".")[0] in {*self.shape.moved_names, ""}:
            self.ctx.problem(
                f"{path}:{node.lineno}: f-String mit dem festen Teil {value!r} zeigt auf "
                f"{self.cut.host} und lässt sich nicht falten — vor dem Schnitt den Pfad als "
                "feste Zeichenkette schreiben"
            )
        elif value in self.shape.moved_names:
            self._string(path, node, scope)

    def _declared_used(self) -> None:
        for number, role in enumerate(self.cut.self_roles):
            if number not in self.used_roles:
                self.ctx.problem(
                    f"self_roles[{number}] ({role.scope}, {role.call}, {role.argument}) trifft "
                    "kein nacktes self — streichen oder prüfen"
                )
        for access in self.cut.accesses:
            if (access.path, access.scope, access.member) not in self.used_accesses:
                self.ctx.problem(
                    f"accesses ({access.path}, {access.scope}, {access.member}) trifft keine "
                    "Stelle — streichen oder prüfen"
                )

    # ------------------------------------------------------------------ Abhängigkeiten

    def _dependencies(self) -> None:
        """Was die verschobenen Methoden aus dem Modul des Wirts lesen: Importe ziehen mit,
        eine Definition des Wirtsmoduls nur als Typ (unter ``TYPE_CHECKING``)."""
        host_top = TopLevel(self.host)
        component_top = TopLevel(self.component)
        patched = self.ctx.index.patched_names()
        self.runtime: list[str] = []
        self.checking: list[str] = []
        future = any(
            isinstance(s, ast.ImportFrom) and s.module == "__future__" for s in self.host.tree.body
        )
        future_component = any(
            isinstance(s, ast.ImportFrom) and s.module == "__future__"
            for s in self.component.tree.body
        )
        if future != future_component:
            self.ctx.problem(
                f"{self.component_path}: from __future__ import annotations steht nur in einem "
                "von Wirt und Komponente — Annotationen würden anders ausgewertet; angleichen"
            )
        for moved in self.shape.methods.values():
            for method in moved.defs:
                scopes = self.host_scopes.of(method)
                for node in ast.walk(method):
                    if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
                        continue
                    if not scopes.is_global(node) or node.id in BUILTINS:
                        continue
                    if node.id == self.cut.host and self._class_ref_node(node):
                        continue
                    self._dependency(node, host_top, component_top, patched, future)

    def _class_ref_node(self, node: ast.Name) -> bool:
        parent = self.host.parent(node)
        return isinstance(parent, ast.Attribute) and parent.attr in self.shape.moved_names

    def _dependency(
        self,
        node: ast.Name,
        host_top: TopLevel,
        component_top: TopLevel,
        patched: frozenset[tuple[str, str]],
        future: bool,
    ) -> None:
        name = node.id
        if (self.shape.module, name) in patched:
            self.ctx.problem(
                f"{self.path}:{node.lineno}: eine verschobene Methode liest {name}, den ein Test "
                f"auf {self.shape.module} patcht — danach erreichte ihn der Patch nicht mehr; vor "
                "dem Schnitt den Patch auf den Ursprung des Namens setzen"
            )
            return
        bindings = host_top.imports.get(name, [])
        if bindings:
            have = {b.identity for b in component_top.imports.get(name, [])}
            if component_top.units.get(name):
                self.ctx.problem(
                    f"{self.component_path}: {name} ist dort anders gebunden — vorher umbenennen"
                )
                return
            for binding in bindings:
                if binding.identity in have:
                    continue
                target = self.checking if binding.checking else self.runtime
                if binding.text() not in target:
                    target.append(binding.text())
            return
        if host_top.units.get(name):
            annotation = in_annotation(self.host, node)
            if annotation and future:
                text = f"from {self.shape.module} import {name}"
                if text not in self.checking:
                    self.checking.append(text)
                return
            self.ctx.problem(
                f"{self.path}:{node.lineno}: eine verschobene Methode liest {name} aus dem Modul "
                "des Wirts — die Komponente importiert den Wirt nicht (Kreis); vorher in ein "
                "eigenes Modul ziehen (Modulmodus)"
            )
            return
        self.ctx.problem(f"{self.path}:{node.lineno}: {name!r} ist nicht gebunden — prüfen")

    # ------------------------------------------------------------------ Schreiben

    def _move(self) -> None:
        rewrite = self.ctx.rewrite(self.path)
        try:
            moved_text = apply_text(self.host, self.body_edits)
        except EditError as error:
            self.ctx.problem(f"{error} — die Stelle vor dem Schnitt einfacher schreiben")
            return
        # Ersetzungen bleiben in ihrer Zeile: Die Spannen gelten auch im ersetzten Text.
        source = Source(self.path, moved_text.encode("utf-8"))
        component = self.shape.component_class
        assert component is not None
        indent = self.component.indent_of(component.body[0].lineno)
        texts: list[str] = []
        for moved in self.shape.methods.values():
            for method, span in zip(moved.defs, moved.spans, strict=True):
                if self.host.indent_of(method.lineno) != indent:
                    self.ctx.problem(
                        f"{self.path}:{method.lineno}: {moved.name} ist anders eingerückt als der "
                        f"Rumpf von {self.cut.component_class} — angleichen"
                    )
                    return
                texts.append(source.lines_text(span.first, span.last))
                rule = "Methode wandert in die Komponente"
                rewrite.remove_lines(span.first, span.last, method, rule)
        target = self.ctx.rewrite(self.component_path)
        end = component.end_lineno or component.lineno
        body = "".join(t.replace("\r\n", "\n") for t in texts)
        if not body.startswith("\n"):
            body = "\n" + body
        target.insert_after_line(end, body.rstrip("\n") + "\n", "Methoden der Komponente")
        self._imports(target)
        self._host_imports(rewrite)

    def _imports(self, rewrite: FileRewrite) -> None:
        if self.runtime:
            anchor = rewrite.head_anchor()
            if anchor is None:
                self.ctx.problem(
                    f"{self.component_path}: kein Importkopf — im Gerüst-Commit anlegen"
                )
                return
            for text in self.runtime:
                rewrite.add_import(anchor, text, "Importe der verschobenen Methoden")
        if self.checking:
            blocks = [
                s
                for s in self.component.tree.body
                if isinstance(s, ast.If) and is_type_checking(s.test)
            ]
            if not blocks or not isinstance(blocks[0].body[-1], IMPORTS):
                self.ctx.problem(
                    f"{self.component_path}: kein Block if TYPE_CHECKING mit Importen für "
                    f"{', '.join(self.checking)} — im Gerüst-Commit anlegen"
                )
                return
            last = blocks[0].body[-1]
            assert isinstance(last, (ast.Import, ast.ImportFrom))
            for text in self.checking:
                rewrite.add_import(last, text, "Typimporte der verschobenen Methoden")

    def _host_imports(self, rewrite: FileRewrite) -> None:
        """Ein Import des Wirtsmoduls, den nach dem Schnitt niemand mehr liest, fällt weg."""
        read: set[str] = set()
        for moved in self.shape.methods.values():
            for method in moved.defs:
                scopes = self.host_scopes.of(method)
                read |= {
                    n.id
                    for n in ast.walk(method)
                    if isinstance(n, ast.Name) and scopes.is_global(n)
                }
        top = TopLevel(self.host)
        for stmt, _checking in top.import_statements:
            for number, alias in enumerate(stmt.names):
                name = bound_name(alias)
                if name not in read or self._still_read(name):
                    continue
                plan = rewrite.plan(stmt)
                plan.drop.add(number)
                plan.rules.append("Import ohne Leser im Wirt fällt weg")

    def _still_read(self, name: str) -> bool:
        rewrite = self.ctx.rewrite(self.path)
        for node in self.host_scopes.global_names(name):
            if isinstance(node.ctx, ast.Load) and not rewrite.covered(node):
                return True
        for constant in string_constants(self.host):
            parent = self.host.parent(constant)
            if _is_annotation_node(parent, constant) and not rewrite.covered(constant):
                try:
                    tree = ast.parse(str(constant.value), mode="eval")
                except SyntaxError, ValueError:
                    continue
                if any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(tree)):
                    return True
        return False


# ------------------------------------------------------------------------------ Lebensdauer


def lifetime(shape: Shape) -> list[str]:
    """Der statische Teil des Lebensdauernachweises am Gerüst (Konzept 3.3): ``release()`` in
    der Komponente, ``_host`` und ``_parent`` als Eigenschaften, kein starkes Halten eines
    Parameters im ``__init__``, und der Wirt ruft ``<attr>.release()`` vor ``disconnect(self)``.
    Ob danach kein Signal mehr ankommt, belegt ein Laufzeittest — nicht dieser."""
    problems: list[str] = []
    component = shape.component_class
    host = shape.host_class
    cut = shape.cut
    if component is None or host is None:
        return problems
    members = {s.name: s for s in component.body if isinstance(s, ast.FunctionDef)}
    if "release" not in members:
        problems.append(
            f"{cut.component}: kein release() — jede Komponente gibt selbst frei (Konzept 3.3); "
            "im Gerüst-Commit anlegen"
        )
    for name in ("_host", "_parent"):
        found = members.get(name)
        if found is None or not any(ast.unparse(d) == "property" for d in found.decorator_list):
            problems.append(
                f"{cut.component}.{name}: Eigenschaft über einer schwachen Referenz fehlt — im "
                "Gerüst-Commit anlegen (Konzept 3.3)"
            )
    init = members.get("__init__")
    if init is not None:
        params = {a.arg for a in [*init.args.args, *init.args.kwonlyargs][1:]}
        for node in ast.walk(init):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Name)
                and node.value.id in params
                and any(isinstance(t, ast.Attribute) for t in node.targets)
            ):
                problems.append(
                    f"{path_of(shape.component_module)}:{node.lineno}: {cut.component_class} "
                    f"hält {node.value.id} stark — schwach halten (weakref), sonst entsteht ein "
                    "Ring zwischen Wirt und Komponente"
                )
    host_release = next(
        (s for s in host.body if isinstance(s, ast.FunctionDef) and s.name == "release"), None
    )
    if host_release is None:
        problems.append(
            f"{cut.host} hat kein release(), das {cut.host_attribute}.release() ruft — im "
            "Gerüst-Commit ergänzen"
        )
        return problems
    calls = [n for n in ast.walk(host_release) if isinstance(n, ast.Call)]
    mine = [n.lineno for n in calls if ast.unparse(n.func) == f"self.{cut.host_attribute}.release"]
    disconnects = [
        n.lineno
        for n in calls
        if isinstance(n.func, ast.Attribute)
        and n.func.attr == "disconnect"
        and any(isinstance(a, ast.Name) and a.id == "self" for a in n.args)
    ]
    if not mine:
        problems.append(
            f"{cut.host}.release ruft self.{cut.host_attribute}.release() nicht — ergänzen, "
            "vor disconnect(self)"
        )
    elif disconnects and min(mine) > min(disconnects):
        problems.append(
            f"{cut.host}.release ruft self.{cut.host_attribute}.release() erst nach "
            "disconnect(self) — davor stellen (Konzept 3.3)"
        )
    protocol = shape.protocol
    if protocol is not None:
        offered = _class_members(protocol)
        missing = [m for m in cut.host_members if m not in offered]
        if missing:
            problems.append(
                f"{cut.host_protocol} nennt {', '.join(missing)} nicht — das Protokoll ist "
                "erhoben: jedes geteilte Member, das die Komponente anspricht, steht darin"
            )
    return problems


# ------------------------------------------------------------------------------ Hilfen


def _class(source: Source, name: str) -> ast.ClassDef | None:
    return next(
        (s for s in source.tree.body if isinstance(s, ast.ClassDef) and s.name == name), None
    )


def _applied(cut: Cut, host: Source, component: Source) -> bool:
    """Ob die Komponente jede erklärte Methode trägt und der Wirt keine mehr."""
    host_class = _class(host, cut.host)
    component_class = _class(component, cut.component_class)
    if host_class is None or component_class is None:
        return False

    def names(cls: ast.ClassDef) -> set[str]:
        return {s.name for s in cls.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))}

    return set(cut.methods) <= names(component_class) and not set(cut.methods) & names(host_class)


def _class_level_names(stmt: ast.stmt) -> list[str]:
    if isinstance(stmt, ast.Assign):
        return [t.id for t in stmt.targets if isinstance(t, ast.Name)]
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return [stmt.target.id]
    return []


def _class_members(cls: ast.ClassDef) -> set[str]:
    """Methoden, Klassenattribute und ``self.<x> = …`` in Methoden einer Klasse."""
    found: set[str] = set()
    for stmt in cls.body:
        found.update(_class_level_names(stmt))
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.add(stmt.name)
            me = self_name(stmt)
            if me is None:
                continue
            for node in ast.walk(stmt):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.ctx, ast.Store)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == me
                ):
                    found.add(node.attr)
    return found


def _inside(outer: ast.AST, node: ast.AST) -> bool:
    line: int = getattr(node, "lineno", 0)
    decorators: list[ast.expr] = getattr(outer, "decorator_list", [])
    first: int = min([getattr(outer, "lineno", 0), *(d.lineno for d in decorators)])
    last: int = getattr(outer, "end_lineno", 0) or 0
    return first <= line <= last


def in_annotation(source: Source, node: ast.AST) -> bool:
    current: ast.AST = node
    for outer in source.ancestors(node):
        if _is_annotation_node(outer, current):
            return True
        if isinstance(outer, ast.stmt) and not isinstance(outer, ast.AnnAssign):
            return False
        current = outer
    return False


def _is_annotation_node(parent: ast.AST | None, node: ast.AST) -> bool:
    if isinstance(parent, ast.arg):
        return parent.annotation is node
    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return parent.returns is node
    if isinstance(parent, ast.AnnAssign):
        return parent.annotation is node
    return False
