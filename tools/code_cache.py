"""Datenrahmen für Quelltextauszüge: Versionsprüfung vor dem Inhalt, keine Rückrufe."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import marshal
from collections.abc import Callable
from itertools import chain
from pathlib import Path
from types import UnionType
from typing import TYPE_CHECKING, ForwardRef, cast, get_args, get_origin

if TYPE_CHECKING:
    from tools.code_facts import Facts

MAGIC = b"SOLIDON-CODE-INDEX-DATA-1\n"
# Zusammen mit code_facts.stamp() bindet dies die statisch gelesenen Typen an
# die tatsächlich importierten Implementierungen, auch bei Änderungen auf Platte.
_SOURCE = Path(__file__).read_bytes()
type Packed = bool | int | float | str | bytes | tuple[Packed, ...] | None
type Check = Callable[[object], bool]
type Records = dict[str, tuple[type, tuple[Check, ...]]]


def _pack(value: object, memo: dict[int, Packed] | None = None) -> Packed:
    """Nur Daten; jede Struktur bekommt eine eindeutige Formmarke."""
    if value is None or type(value) in (bool, int, float, str, bytes):
        return cast(Packed, value)
    if memo is None:
        memo = {}
    key = id(value)
    if key in memo:
        return memo[key]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        packed: Packed = (
            type(value).__name__,
            tuple(_pack(getattr(value, field.name), memo) for field in dataclasses.fields(value)),
        )
    elif isinstance(value, tuple):
        tag: str | int = type(value).__name__ if hasattr(type(value), "_fields") else 0
        packed = tag, tuple(_pack(item, memo) for item in value)
    elif isinstance(value, list):
        packed = 1, tuple(_pack(item, memo) for item in value)
    elif isinstance(value, dict):
        packed = 2, tuple((_pack(k, memo), _pack(item, memo)) for k, item in value.items())
    elif isinstance(value, set):
        packed = 3, tuple(_pack(item, memo) for item in value)
    else:
        raise TypeError(f"Kein Auszugswert: {type(value).__name__}")
    # Nur Identität, nie Tupelgleichheit: False und 0 sowie verschiedene IR-Formen
    # dürfen nicht verschmelzen. Der Merker lebt nur für diesen unveränderten Eingabegraphen.
    memo[key] = packed
    return packed


def _container_check(origin: object, args: tuple[Check, ...], repeated: bool = False) -> Check:
    if origin is tuple:
        if repeated:
            (item_check,) = args
            return lambda value: isinstance(value, tuple) and all(map(item_check, value))
        return lambda value: (
            type(value) is tuple
            and len(value) == len(args)
            and all(check(item) for check, item in zip(args, value, strict=True))
        )
    if origin in (list, set) and len(args) == 1:
        (item_check,) = args
        return lambda value: (
            isinstance(value, (list, set)) and type(value) is origin and all(map(item_check, value))
        )
    if origin is dict and len(args) == 2:
        key_check, item_check = args
        return lambda value: (
            isinstance(value, dict)
            and all(key_check(key) and item_check(item) for key, item in value.items())
        )
    if origin is UnionType:
        return lambda value: any(check(value) for check in args)
    raise ValueError("Unbekannte Containerbeschreibung")


def _check(annotation: object, names: dict[str, object]) -> Check:
    """Nur eigene Typbeschreibungen lesen; Zeichenketten werden niemals ausgewertet."""
    if isinstance(annotation, ForwardRef):
        annotation = annotation.__forward_arg__
    if isinstance(annotation, str):
        return _syntax_check(ast.parse(annotation, mode="eval").body, names)
    if annotation is object:
        # Jedes Objekt kam bereits durch _unpack: ausschließlich Daten und geprüfte Records.
        return lambda value: True
    if isinstance(annotation, type):
        return lambda value: type(value) is annotation
    origin = get_origin(annotation)
    args = get_args(annotation)
    repeated = origin is tuple and len(args) == 2 and args[-1] is Ellipsis
    return _container_check(
        origin, tuple(_check(arg, names) for arg in (args[:1] if repeated else args)), repeated
    )


def _syntax_check(node: ast.expr, names: dict[str, object]) -> Check:
    if isinstance(node, ast.Name):
        return _check(names[node.id], names)
    if isinstance(node, ast.Constant) and node.value is None:
        return _check(type(None), names)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _container_check(
            UnionType, (_syntax_check(node.left, names), _syntax_check(node.right, names))
        )
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        items = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        repeated = (
            node.value.id == "tuple"
            and len(items) == 2
            and isinstance(items[-1], ast.Constant)
            and items[-1].value is Ellipsis
        )
        return _container_check(
            names[node.value.id],
            tuple(_syntax_check(item, names) for item in (items[:1] if repeated else items)),
            repeated,
        )
    raise ValueError("Unbekannte Typbeschreibung")


def _records(namespace: dict[str, object], source: bytes) -> Records:
    classes = {
        name: value
        for name, value in namespace.items()
        if isinstance(value, type)
        and value.__module__ == namespace["__name__"]
        and (
            dataclasses.is_dataclass(value)
            or (issubclass(value, tuple) and hasattr(value, "_fields"))
        )
    }
    names: dict[str, object] = {
        cls.__name__: cls for cls in (object, bool, int, float, str, bytes, tuple, list, dict, set)
    }
    names.update(namespace)
    # NamedTuple hält seine Annotationen ab Python 3.14 hinter einem Callback.
    # Nur der eigene, stempelgeprüfte Syntaxbaum wird gelesen, kein Callback aufgerufen.
    annotations = {
        node.name: {
            item.target.id: item.annotation
            for item in node.body
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
        }
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name in classes
    }
    records: Records = {}
    for name, cls in classes.items():
        fields = (
            tuple(field.name for field in dataclasses.fields(cls))
            if dataclasses.is_dataclass(cls)
            else cls._fields
        )
        records[name] = (
            cls,
            tuple(_syntax_check(annotations[name][field], names) for field in fields),
        )
    return records


def _scope_count(cls: type, items: tuple[object, ...]) -> int:
    """Bereichsgrenze vor den Unterrecords lesen; ihre Feldformen folgen im selben Gang."""
    position = next(i for i, field in enumerate(dataclasses.fields(cls)) if field.name == "scopes")
    scopes = items[position]
    if (
        not isinstance(scopes, tuple)
        or len(scopes) != 2
        or type(scopes[0]) is not int
        or scopes[0] != 1
        or not isinstance(scopes[1], tuple)
        or not scopes[1]
    ):
        raise ValueError("Die Modulwurzel fehlt")
    return len(scopes[1])


def _check_scopes(facts: Facts) -> None:
    """Ein Bereich gehört zu dieser Datei und seine Elternkette endet an ihrer Modulwurzel."""
    root = facts.scopes[0]
    if root.kind != "module" or root.parent != -1:
        raise ValueError("Ungültige Modulwurzel")
    if any(
        scope.kind == "module" or not 0 <= scope.parent < number
        for number, scope in enumerate(facts.scopes[1:], 1)
    ):
        raise ValueError("Ungültiger Elternbereich")
    references = chain(
        facts.comprehensions.values(),
        (context[0] for context in facts.contexts.values()),
        (reload[0] for reload in facts.reloads),
        (reset[0] for reset in facts.resets),
    )
    if any(not 0 <= number < len(facts.scopes) for number in references):
        raise ValueError("Ungültiger Bereichsverweis")


def _unpack(
    value: object, records: Records, memo: dict[int, object], scope_count: int | None = None
) -> object:
    if not isinstance(value, tuple):
        if value is None or isinstance(value, (bool, int, float, str, bytes)):
            return value
        raise ValueError("Ungültiger Auszugswert")
    if len(value) != 2 or not isinstance(value[1], tuple):
        raise ValueError("Ungültige Auszugsform")
    key = id(value)
    if key in memo:
        return memo[key]
    tag, items = value
    if type(tag) is int:
        if tag == 2:
            result: object = {
                _unpack(k, records, memo, scope_count): _unpack(item, records, memo, scope_count)
                for k, item in items
            }
        elif tag in (0, 1, 3):
            children = tuple(_unpack(item, records, memo, scope_count) for item in items)
            result = children if tag == 0 else list(children) if tag == 1 else set(children)
        else:
            raise ValueError("Unbekannte Auszugsform")
    elif isinstance(tag, str) and tag in records:
        cls, checks = records[tag]
        if len(items) != len(checks):
            raise ValueError("Ungültige Feldzahl")
        if tag == "Facts":
            scope_count = _scope_count(cls, items)
            # Ein geteilter Unterbaum kann in einer Datei gültig und in einer anderen
            # außerhalb der Bereichsliste liegen. Deshalb keine Treffer über Dateigrenzen.
            child_memo: dict[int, object] = {}
        else:
            child_memo = memo
        children = tuple(_unpack(item, records, child_memo, scope_count) for item in items)
        if not all(check(item) for check, item in zip(checks, children, strict=True)):
            raise ValueError("Ungültige Feldform")
        result = cls(*children)
        reference = getattr(result, "scope", None)
        if reference is not None and (scope_count is None or not 0 <= reference < scope_count):
            raise ValueError("Ungültiger Bereichsverweis")
        if tag == "Facts":
            _check_scopes(cast("Facts", result))
    else:
        raise ValueError("Unbekannte Auszugsform")
    # Erst vollständig geprüfte Records merken. Gemeinsame Unterbäume werden nur einmal
    # rekonstruiert; Kreisverweise erreichen den Merker nicht und werden verworfen.
    memo[key] = result
    return result


def encode(current: str, files: dict[str, tuple[str, Facts]]) -> bytes:
    """Stempel im Klartext, dahinter ausschließlich Marshal-Daten ohne Codeobjekte."""
    return MAGIC + current.encode("ascii") + b"\n" + marshal.dumps(_pack(files), allow_code=False)


def decode(path: Path, current: str) -> dict[str, tuple[str, Facts]]:
    """Veraltete, beschädigte und alte Pickle-Speicher werden ohne Ausführung verworfen."""
    from tools import code_facts

    try:
        data = path.read_bytes()
        header = MAGIC + current.encode("ascii") + b"\n"
        if not data.startswith(header):
            return {}
        source = Path(code_facts.__file__).read_bytes()
        if hashlib.sha256(source + _SOURCE).hexdigest() != code_facts.stamp():
            return {}
        records = _records(vars(code_facts), source)
        stored = _unpack(marshal.loads(data[len(header) :], allow_code=False), records, {})
        if not isinstance(stored, dict):
            return {}
        files: dict[str, tuple[str, Facts]] = {}
        for name, entry in stored.items():
            if not isinstance(name, str) or not isinstance(entry, tuple) or len(entry) != 2:
                return {}
            digest, facts = entry
            if not isinstance(digest, str) or not isinstance(facts, code_facts.Facts):
                return {}
            files[name] = digest, facts
        return files
    except OSError, ValueError, TypeError, EOFError, KeyError, RecursionError, SyntaxError:
        # Der Cache ist eine Ableitung. Ein unlesbarer Stand wird aus dem Quelltext erneuert.
        return {}
