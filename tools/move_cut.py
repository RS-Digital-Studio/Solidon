"""Die Zuschnittliste des Verschiebewerkzeugs: TOML lesen und streng prüfen.

Eine Datei ist ein Schnitt (``schema_version = 1``, ``mode`` ist ``module``, ``copies`` oder
``component``). Unbekannte Schlüssel, falsche Typen und Widersprüche halten **vor** jedem
Schreiben an, mit dem Weg, wie die Liste richtig aussähe. Es gibt keinen Schlüssel, der einen Fund
übergeht, keinen Schalter für „trotzdem“ und keine Ersetzung nach Muster: Was die Liste erklärt,
ist je Stelle genannt (Konzept Codestruktur 4.1, keine Ausnahmeliste). Jede Erklärung muss im
Schnitt auch greifen; eine, die nichts trifft, ist ein Fehler.

Die Felder je Modus beschreibt ``tools/move_names.py`` (``--help`` und Modul-Docstring).
"""

from __future__ import annotations

import keyword
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from tools.move_source import AREAS, module_of

SCHEMA_VERSION = 1
MODES = ("module", "copies", "component")
#: Rollen eines nackten ``self`` im verschobenen Rumpf (Konzept 3.3).
ROLES = ("qt_parent", "owner", "event_filter", "flow_host")
DECISIONS = ("component", "keep")
#: ``member`` einer Erklärung für einen Zugriff mit offenem Namen (Review 2, RM-M20).
OPEN_MEMBER = "*"


class CutError(Exception):
    """Die Zuschnittliste ist ungültig; die Meldung nennt Schlüssel und Ausweg."""


@dataclass(frozen=True)
class Target:
    module: str
    docstring: str
    definitions: tuple[str, ...]
    over_limit: bool = False


@dataclass(frozen=True)
class Rename:
    name: str
    to: str


@dataclass(frozen=True)
class Identity:
    name: str
    reason: str


@dataclass(frozen=True)
class NameList:
    """Eine Zeichenkette in einer Liste, die Module oder Namen als Text hält (W6)."""

    path: str
    value: str
    to: tuple[str, ...]


@dataclass(frozen=True)
class SourceReader:
    """Ein Leser der Quelldatei über ``Path(M.__file__)``: Er liest danach ``module``."""

    path: str
    scope: str
    module: str


@dataclass(frozen=True)
class Alias:
    path: str
    module: str
    name: str


@dataclass(frozen=True)
class Binding:
    module: str
    name: str


@dataclass(frozen=True)
class SelfRole:
    scope: str
    call: str
    argument: str
    role: str


@dataclass(frozen=True)
class Access:
    path: str
    scope: str
    member: str
    decision: str


@dataclass(frozen=True)
class Cut:
    """Ein gelesener Schnitt; welche Felder gelten, sagt ``mode``."""

    id: str
    mode: str
    file: Path
    source: str = ""
    package_docstring: str = ""
    targets: tuple[Target, ...] = ()
    renames: tuple[Rename, ...] = ()
    duplicate: tuple[str, ...] = ()
    identity: tuple[Identity, ...] = ()
    name_lists: tuple[NameList, ...] = ()
    source_readers: tuple[SourceReader, ...] = ()
    aliases: tuple[Alias, ...] = ()
    bindings: tuple[Binding, ...] = ()
    host: str = ""
    component: str = ""
    host_attribute: str = ""
    host_protocol: str = ""
    methods: tuple[str, ...] = ()
    own_attributes: tuple[str, ...] = ()
    host_members: tuple[str, ...] = ()
    parent_members: tuple[str, ...] = ()
    self_roles: tuple[SelfRole, ...] = ()
    accesses: tuple[Access, ...] = ()

    @property
    def source_module(self) -> str:
        return module_of(self.source)

    @property
    def component_module(self) -> str:
        return self.component.partition(":")[0]

    @property
    def component_class(self) -> str:
        return self.component.partition(":")[2]

    def target_of(self, name: str) -> Target | None:
        return next((t for t in self.targets if name in t.definitions), None)

    def renamed(self, name: str) -> str:
        return next((r.to for r in self.renames if r.name == name), name)

    @property
    def package(self) -> bool:
        """Ob die Quelle ein Paket gleichen Namens wird (Konzept 3.1, Regel 2): ja, wenn ein
        Ziel darin liegt."""
        return any(t.module.startswith(self.source_module + ".") for t in self.targets)


# ---------------------------------------------------------------------------- Prüfen


def _where(context: str, key: str) -> str:
    return f"{context}.{key}" if context else key


class _Table:
    """Ein TOML-Abschnitt, der jeden gelesenen Schlüssel zählt; übrige sind ein Fehler."""

    def __init__(self, data: object, context: str) -> None:
        if not isinstance(data, dict):
            raise CutError(f"{context or 'Zuschnitt'}: Tabelle erwartet")
        self.data: dict[str, Any] = data
        self.context = context
        self.read: set[str] = set()

    def get(self, key: str, kind: type, default: object = None, *, required: bool = False) -> Any:
        self.read.add(key)
        if key not in self.data:
            if required:
                raise CutError(f"{_where(self.context, key)} fehlt — Schlüssel ergänzen")
            return default
        value = self.data[key]
        ok = {
            bool: isinstance(value, bool),
            str: isinstance(value, str),
            int: isinstance(value, int) and not isinstance(value, bool),
            list: isinstance(value, list),
        }.get(kind, True)
        if not ok:
            expected = {bool: "true oder false", str: "Zeichenkette", int: "ganze Zahl"}
            raise CutError(f"{_where(self.context, key)}: {expected.get(kind, 'Liste')} erwartet")
        return value

    def text(self, key: str, *, required: bool = True) -> str:
        value = self.get(key, str, "", required=required)
        if required and not value.strip():
            raise CutError(f"{_where(self.context, key)} ist leer — Text eintragen")
        return str(value)

    def strings(self, key: str, *, required: bool = False) -> tuple[str, ...]:
        value = self.get(key, list, [], required=required)
        if not all(isinstance(item, str) and item for item in value):
            raise CutError(
                f"{_where(self.context, key)}: Liste nicht leerer Zeichenketten erwartet"
            )
        if len(set(value)) != len(value):
            doubled = sorted({item for item in value if value.count(item) > 1})
            raise CutError(f"{_where(self.context, key)}: doppelt {doubled} — einmal nennen")
        return tuple(value)

    def tables(self, key: str) -> list[_Table]:
        value = self.get(key, list, [])
        return [_Table(item, f"{_where(self.context, key)}[{n}]") for n, item in enumerate(value)]

    def done(self) -> None:
        unknown = sorted(set(self.data) - self.read)
        if unknown:
            raise CutError(
                f"{self.context or 'Zuschnitt'}: unbekannte Schlüssel {unknown} — Schreibweise "
                "prüfen (Felder: tools/move_names.py --help)"
            )


def _identifier(value: str, context: str) -> str:
    if not value.isidentifier() or keyword.iskeyword(value):
        raise CutError(f"{context}: {value!r} ist kein Python-Name")
    return value


def _module(value: str, context: str, *, areas: tuple[str, ...] = ("app", "tools")) -> str:
    parts = value.split(".")
    if parts[0] not in areas or not all(
        p.isidentifier() and not keyword.iskeyword(p) for p in parts
    ):
        raise CutError(f"{context}: {value!r} ist kein Modul unter {'/, '.join(areas)}/")
    return value


def _path(value: str, context: str) -> str:
    path = PurePosixPath(value)
    if (
        "\\" in value
        or path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] not in AREAS
        or path.suffix != ".py"
    ):
        raise CutError(
            f"{context}: {value!r} ist kein relativer Pfad einer .py-Datei unter app/, tools/ "
            "oder tests/ (Schrägstriche, ohne ..)"
        )
    return path.as_posix()


def _qualname(value: str, context: str) -> str:
    if value == "<module>":
        return value
    for part in value.split("."):
        _identifier(part, context)
    return value


def load(file: Path) -> Cut:
    """Liest und prüft eine Zuschnittliste."""
    try:
        data = tomllib.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise CutError(f"{file}: nicht lesbar ({error})") from None
    except tomllib.TOMLDecodeError as error:
        raise CutError(f"{file}: kein gültiges TOML ({error})") from None
    return parse(data, file)


def parse(data: dict[str, Any], file: Path) -> Cut:
    """Prüft einen geladenen Zuschnitt; jede Abweichung ist ein :class:`CutError`."""
    top = _Table(data, "")
    version = top.get("schema_version", int, required=True)
    if version != SCHEMA_VERSION:
        raise CutError(f"schema_version {version}: dieses Werkzeug liest Version {SCHEMA_VERSION}")
    mode = top.text("mode")
    if mode not in MODES:
        raise CutError(f"mode {mode!r}: erlaubt sind {', '.join(MODES)}")
    cut_id = top.text("id")
    aliases: list[Alias] = []
    for table in top.tables("aliases"):
        aliases.append(
            Alias(
                _path(table.text("path"), table.context),
                _module(table.text("module"), table.context),
                _identifier(table.text("name"), table.context),
            )
        )
        table.done()
    if len({(a.path, a.module) for a in aliases}) != len(aliases):
        raise CutError("aliases: je Datei und Modul höchstens ein Alias")
    if mode == "module":
        cut = _module_cut(top, cut_id, file, tuple(aliases))
    elif mode == "copies":
        cut = _copies_cut(top, cut_id, file, tuple(aliases))
    else:
        cut = _component_cut(top, cut_id, file, tuple(aliases))
    top.done()
    return cut


def _module_cut(top: _Table, cut_id: str, file: Path, aliases: tuple[Alias, ...]) -> Cut:
    source = _path(top.text("source"), "source")
    if not source.startswith(("app/", "tools/")) or source.endswith("__init__.py"):
        raise CutError(
            "source: ein Modul unter app/ oder tools/, kein Paket-__init__ und keine Testdatei"
        )
    source_module = module_of(source)
    targets: list[Target] = []
    for table in top.tables("targets"):
        module = _module(table.text("module"), table.context)
        definitions = table.strings("definitions", required=True)
        if not definitions:
            raise CutError(f"{table.context}.definitions ist leer — mindestens eine Definition")
        for name in definitions:
            _identifier(name, table.context + ".definitions")
        targets.append(
            Target(
                module,
                table.text("docstring"),
                definitions,
                table.get("over_limit", bool, False),
            )
        )
        table.done()
    if not targets:
        raise CutError("targets fehlt — mindestens ein Zielmodul")
    if len({t.module for t in targets}) != len(targets):
        raise CutError("targets: ein Zielmodul ist doppelt genannt — zusammenfassen")
    inside = [t.module for t in targets if t.module.startswith(source_module + ".")]
    if inside:
        outside = [t.module for t in targets if t.module not in inside]
        if outside:
            raise CutError(
                f"targets: {', '.join(outside)} liegen neben dem Paket {source_module} — "
                "entweder alle Ziele im neuen Paket (die Quelle wird Paket) oder keines"
            )
        if any(t.module.count(".") != source_module.count(".") + 1 for t in targets):
            raise CutError(
                f"targets: Ziele liegen direkt im neuen Paket {source_module} (Konzept 3.1, "
                "Regel 2: das Paket übernimmt den Namen der Datei)"
            )
    seen: dict[str, str] = {}
    for target in targets:
        for name in target.definitions:
            if name in seen:
                raise CutError(
                    f"Definition {name!r} steht in {seen[name]} und {target.module} — genau "
                    "ein Ziel (oder in duplicate)"
                )
            seen[name] = target.module
    duplicate = top.strings("duplicate")
    for name in duplicate:
        _identifier(name, "duplicate")
        if name in seen:
            raise CutError(
                f"duplicate: {name!r} steht auch in {seen[name]} — doppelt Gebundenes kommt in "
                "jedes Ziel, das es liest, und in kein definitions"
            )
    renames: list[Rename] = []
    for table in top.tables("renames"):
        name = _identifier(table.text("name"), table.context)
        to = _identifier(table.text("to"), table.context)
        if name not in seen:
            raise CutError(f"{table.context}: {name!r} wird nicht verschoben — nur Verschobenes")
        if name == to:
            raise CutError(f"{table.context}: {name!r} → {to!r} ist keine Umbenennung")
        renames.append(Rename(name, to))
        table.done()
    if len({r.name for r in renames}) != len(renames):
        raise CutError("renames: ein Name ist doppelt umbenannt")
    for target in targets:
        after = [next((r.to for r in renames if r.name == n), n) for n in target.definitions]
        after.extend(duplicate)
        if len(set(after)) != len(after):
            raise CutError(
                f"{target.module}: zwei Definitionen hießen danach gleich — anders umbenennen"
            )
    identity: list[Identity] = []
    for table in top.tables("identity"):
        name = _identifier(table.text("name"), table.context)
        if name not in seen and name not in duplicate:
            raise CutError(f"{table.context}.name {name!r} wird nicht verschoben")
        identity.append(Identity(name, table.text("reason")))
        table.done()
    name_lists: list[NameList] = []
    for table in top.tables("name_lists"):
        values = table.strings("to", required=True)
        if not values:
            raise CutError(f"{table.context}.to ist leer — mindestens ein neuer Wert")
        path = _path(table.text("path"), table.context)
        name_lists.append(NameList(path, table.text("value"), values))
        table.done()
    if len({(n.path, n.value) for n in name_lists}) != len(name_lists):
        raise CutError("name_lists: je Datei und Wert höchstens ein Eintrag")
    for entry in name_lists:
        if entry.path == source and len(entry.to) != 1:
            raise CutError(
                f"name_lists {entry.value!r} in der Quelle: genau ein neuer Wert — in einer "
                "verschobenen Definition wird eine Zeichenkette ersetzt, keine Liste verlängert"
            )
    readers: list[SourceReader] = []
    for table in top.tables("source_readers"):
        module = _module(table.text("module"), table.context)
        if module not in {t.module for t in targets}:
            raise CutError(f"{table.context}.module {module!r} ist kein Ziel des Schnitts")
        readers.append(
            SourceReader(
                _path(table.text("path"), table.context),
                _qualname(table.text("scope"), table.context),
                module,
            )
        )
        table.done()
    return Cut(
        id=cut_id,
        mode="module",
        file=file,
        source=source,
        package_docstring=top.text("package_docstring", required=bool(inside)),
        targets=tuple(targets),
        renames=tuple(renames),
        duplicate=duplicate,
        identity=tuple(identity),
        name_lists=tuple(name_lists),
        source_readers=tuple(readers),
        aliases=aliases,
    )


def _copies_cut(top: _Table, cut_id: str, file: Path, aliases: tuple[Alias, ...]) -> Cut:
    bindings: list[Binding] = []
    for table in top.tables("bindings"):
        bindings.append(
            Binding(
                _module(table.text("module"), table.context),
                _identifier(table.text("name"), table.context),
            )
        )
        table.done()
    if not bindings:
        raise CutError(
            "bindings fehlt — die Originale nennen, deren Kopfkopien umgestellt werden "
            "(Vorschlag: tools/move_names.py --list-copies)"
        )
    if len(set(bindings)) != len(bindings):
        raise CutError("bindings: ein Original ist doppelt genannt")
    return Cut(id=cut_id, mode="copies", file=file, bindings=tuple(bindings), aliases=aliases)


def _component_cut(top: _Table, cut_id: str, file: Path, aliases: tuple[Alias, ...]) -> Cut:
    source = _path(top.text("source"), "source")
    host = _identifier(top.text("host"), "host")
    component = top.text("component")
    module, _, cls = component.partition(":")
    _module(module, "component")
    _identifier(cls, "component")
    if module == module_of(source):
        raise CutError("component: die Komponente steht in einem eigenen Modul, nicht im Wirt")
    methods = top.strings("methods", required=True)
    if not methods:
        raise CutError("methods ist leer — mindestens eine Methode wandert")
    own = top.strings("own_attributes")
    shared = top.strings("host_members")
    parent = top.strings("parent_members")
    lists = {
        "methods": methods,
        "own_attributes": own,
        "host_members": shared,
        "parent_members": parent,
    }
    owners: dict[str, str] = {}
    for name, values in lists.items():
        for value in values:
            _identifier(value, name)
            if value in owners:
                raise CutError(
                    f"{value!r} steht in {owners[value]} und {name} — jedes Member hat genau "
                    "eine Rolle (Konzept 3.3)"
                )
            owners[value] = name
    for special in ("__init__", "release"):
        if special in methods:
            raise CutError(
                f"methods: {special!r} wandert nicht — der Wirt behält seine Fassung, die "
                "Komponente hat ihre eigene aus dem Gerüst-Commit"
            )
    roles: list[SelfRole] = []
    for table in top.tables("self_roles"):
        role = table.text("role")
        if role not in ROLES:
            raise CutError(f"{table.context}.role {role!r}: erlaubt sind {', '.join(ROLES)}")
        argument = table.get("argument", object, required=True)
        if isinstance(argument, bool) or not isinstance(argument, (int, str)):
            raise CutError(f"{table.context}.argument: Position (Zahl) oder Schlüsselwort")
        scope = _qualname(table.text("scope"), table.context)
        if scope.split(".")[0] != host or scope.split(".")[-1] not in methods:
            raise CutError(
                f"{table.context}.scope {scope!r}: eine verschobene Methode von {host} "
                f"(<{host}>.<methode>)"
            )
        roles.append(SelfRole(scope, table.text("call"), str(argument), role))
        table.done()
    accesses: list[Access] = []
    for table in top.tables("accesses"):
        decision = table.text("decision")
        if decision not in DECISIONS:
            raise CutError(f"{table.context}.decision: {' oder '.join(DECISIONS)}")
        member = table.text("member")
        if member == OPEN_MEMBER:
            # Ein Zugriff mit offenem Namen (``getattr(x, name)``, ``vars(x)``) lässt sich nicht
            # umschreiben: Erklärbar ist nur, dass sein Empfänger nicht der Wirt ist.
            if decision != "keep":
                raise CutError(
                    f'{table.context}: member = "{OPEN_MEMBER}" (offener Name) nur mit '
                    'decision = "keep" — umschreiben lässt sich ein offener Name nicht'
                )
        else:
            member = _identifier(member, table.context)
            if member not in methods and member not in own:
                raise CutError(f"{table.context}.member {member!r} wandert nicht")
        accesses.append(
            Access(
                _path(table.text("path"), table.context),
                _qualname(table.text("scope"), table.context),
                member,
                decision,
            )
        )
        table.done()
    if len({(a.path, a.scope, a.member) for a in accesses}) != len(accesses):
        raise CutError("accesses: je Datei, Bereich und Member höchstens eine Entscheidung")
    return Cut(
        id=cut_id,
        mode="component",
        file=file,
        source=source,
        host=host,
        component=component,
        host_attribute=_identifier(top.text("host_attribute"), "host_attribute"),
        host_protocol=_identifier(top.text("host_protocol"), "host_protocol"),
        methods=methods,
        own_attributes=own,
        host_members=shared,
        parent_members=parent,
        self_roles=tuple(roles),
        accesses=tuple(accesses),
        aliases=aliases,
    )
