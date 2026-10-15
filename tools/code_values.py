"""Werte des statischen Auflösers und exakte Faltung eingebauter Folgenaufrufe."""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable
from typing import NamedTuple


class Val(NamedTuple):
    """Was ein Ausdruck statisch bedeutet.

    ``kind`` ist eines von ``module`` (Modul oder Paket unter ``app``, ``tools``, ``tests``;
    ``ref`` ist der Punktname), ``ext`` (Modul oder Name außerhalb, etwa ``numpy.linalg``),
    ``def`` und ``class`` (``ref`` ist ``modul:qualname``), ``const`` (``data`` ist der Wert),
    ``seq`` und ``map`` (``data`` sind die Elemente bzw. Paare), ``obj`` (ein Objekt, das kein
    Modul ist), ``missing`` (ein Modul oder Name in den eigenen Bereichen, den es nicht gibt;
    ``data`` ist ``(modul, name)``), ``request`` (das ``request`` einer Fixture) und
    ``unknown`` (statisch nicht auflösbar, ``ref`` nennt den Grund).
    """

    kind: str
    ref: str
    data: object = None


class PatchTarget(NamedTuple):
    """Ein aufgelöstes Ziel einer Patch-Stelle, je Zeile der Konstantenfaltung eines.

    ``status``: ``module`` (Modul aus ``app``/``tools``), ``tests`` (Testmodul), ``foreign``
    (fremdes Modul oder Objekt darin), ``object`` (kein Modul), ``missing`` (Modulpfad in den
    eigenen Bereichen, den es nicht gibt) oder ``unknown`` (statisch nicht auflösbar).
    ``module`` ist der Punktname des Zielmoduls (bei ``unknown``/``object`` der Grund),
    ``name`` der gefaltete Attributname oder ``None``, wenn er sich nicht falten ließ.
    """

    status: str
    module: str
    name: str | None


class PatchSite(NamedTuple):
    """Eine Patch-Stelle in ``tests/``: ``monkeypatch.setattr``/``delattr`` (auch mit Pfad als
    Text), ``mock.patch`` (Aufruf, Dekorator, ``with``) und ``mock.patch.object``."""

    path: str
    line: int
    col: int
    scope: str
    form: str
    text: str
    raising: bool | None
    targets: tuple[PatchTarget, ...]
    false_targets: tuple[PatchTarget, ...] = ()


class Reader(NamedTuple):
    """Wer ``M.N`` zur Aufrufzeit erreicht: ``kind`` ist ``global`` (Funktion in ``M``, die ``N``
    als Global liest), ``attribute`` (``M.N`` über einen Modulalias), ``getattr`` oder
    ``import`` (später ``from M import N`` in einer Funktion)."""

    module: str
    qualname: str
    path: str
    line: int
    kind: str


class HeadCopy(NamedTuple):
    """Eine Kopfkopie: ``from M import N`` (``kind == "from"``) oder ``x = M.N``
    (``kind == "assign"``) zur Importzeit in ``app/`` oder ``tools/``, außerhalb von
    ``TYPE_CHECKING``. ``chain`` führt von ``(M, N)`` über Rückexporte bis zum Ursprung."""

    holder: str
    path: str
    line: int
    bound: str
    module: str
    name: str
    chain: tuple[tuple[str, str], ...]
    kind: str


class Reference(NamedTuple):
    """Ein aufgelöster Bezug auf ``module.name`` an einer Stelle des Baums.

    ``kind``: ``import`` (``import M``, dann ist ``name`` leer), ``from``, ``import_module``,
    ``attribute``, ``store``, ``delete``, ``getattr`` oder ``patch``. ``runtime`` sagt, ob der
    Bezug zur Aufrufzeit (in einer Funktion) läuft, ``checking``, ob er unter ``TYPE_CHECKING``
    steht.
    """

    path: str
    line: int
    col: int
    kind: str
    module: str
    name: str
    runtime: bool
    checking: bool


class Unresolved(NamedTuple):
    """Ein Bezug auf ``app``/``tools``, der sich nicht auflöst (W5)."""

    path: str
    line: int
    col: int
    kind: str
    module: str
    name: str
    text: str


class Finding(NamedTuple):
    """Ein Verstoß gegen eine Regel von W2 (``rule`` ist ``a`` bis ``e``, Plan 2.2)."""

    rule: str
    path: str
    line: int
    module: str
    name: str
    detail: str


class Results(NamedTuple):
    """Was ein analysierter Index beantwortet, ohne einen Auszug zu brauchen: die Abfragen von
    W2, W5, W6 und dem Verschiebewerkzeug. Der Ergebnisspeicher (``tools/code_store.py``) hält
    genau das. ``readers`` je ``(M, N)``: ``(halter, qualname, art) → (pfad, zeile)``;
    ``references`` je ``(M, N)`` sortiert und ohne Doppel."""

    sites: tuple[PatchSite, ...]
    heads: tuple[HeadCopy, ...]
    unresolved: tuple[Unresolved, ...]
    findings: dict[str, tuple[Finding, ...]]
    readers: dict[tuple[str, str], dict[tuple[str, str, str], tuple[str, int]]]
    references: dict[tuple[str, str], tuple[Reference, ...]]
    counts: dict[str, int]
    timings: dict[str, float]


def constant(value: object) -> Val:
    """Typ und Wert bleiben gemeinsam eindeutig (False ist kein Integer 0)."""
    return Val("const", type(value).__name__, value)


def elements(value: Val) -> tuple[Val, ...] | None:
    """Bekannte Folge oder Tabellenschlüssel; None bezeichnet eine offene Herkunft."""
    if value.kind == "seq" and isinstance(value.data, tuple):
        return value.data
    if value.kind == "map" and isinstance(value.data, tuple):
        return tuple(key for key, _item in value.data)
    if value.kind == "const" and isinstance(value.data, str):
        return tuple(constant(char) for char in value.data)
    return None


def _numeric(value: Val) -> int | float:
    assert isinstance(value.data, (int, float))
    return value.data


def _string(value: Val) -> str:
    assert isinstance(value.data, str)
    return value.data


def unordered_items(items: tuple[Val, ...]) -> tuple[Val, ...]:
    """Mengen entfernen gleiche Werte; dabei sind etwa False und 0 dasselbe Element."""
    found: dict[object, Val] = {}
    for value in items:
        key = ("const", value.data) if value.kind == "const" else value
        found.setdefault(key, value)
    return tuple(found.values())


def keyword_arguments(
    names: tuple[str, ...], values: tuple[Val, ...]
) -> tuple[dict[str, Val], bool, frozenset[str]]:
    """Schlüsselwörter und **-Tabellen derselben Zeile, ohne Vorgaben zu erraten."""
    found: dict[str, Val] = {}
    open_ = False
    optional: set[str] = set()
    for name, value in zip(names, values, strict=True):
        if name != "**":
            pairs = ((constant(name), value),)
        elif value.kind == "map" and isinstance(value.data, tuple):
            pairs = value.data
            if value.ref == "open":
                # Die bekannte Obermenge einer gefilterten Tabelle enthält keine
                # zusätzlichen Schlüssel; einzelne bekannte dürfen aber fehlen.
                optional.update(
                    key.data
                    for key, _item in pairs
                    if key.kind == "const" and isinstance(key.data, str)
                )
        else:
            open_ = True
            continue
        for key, item in pairs:
            if key.kind != "const" or not isinstance(key.data, str):
                open_ = True
                continue
            if key.data in found:
                item = Val("unknown", f"doppeltes Schlüsselwort {key.data}")
            found[key.data] = item
    return found, open_, frozenset(optional)


def sequence(ref: str, values: tuple[Val, ...], keywords: dict[str, Val], limit: int) -> Val:
    """Unterstützte Signaturen exakt; Überlauf oder unbekannte Semantik bleiben sichtbar."""
    unknown = Val("unknown", f"nicht faltbare Signatur von {ref}")
    start = 0
    reverse = False
    strict = False
    if ref == "builtins.enumerate":
        if not 1 <= len(values) <= 2 or set(keywords) - {"start"}:
            return unknown
        if len(values) == 2 and "start" in keywords:
            return unknown
        offset = values[1] if len(values) == 2 else keywords.get("start", constant(0))
        if offset.kind != "const" or not isinstance(offset.data, int):
            return unknown
        start, values = offset.data, values[:1]
    elif ref == "builtins.zip":
        combos: Iterable[tuple[Val, ...]]
        if set(keywords) - {"strict"}:
            return unknown
        strict_value = keywords.get("strict", constant(False))
        if strict_value.kind != "const" or not isinstance(strict_value.data, bool):
            return unknown
        strict = strict_value.data
    else:
        if len(values) != 1 or (keywords and ref != "builtins.sorted"):
            return unknown
        if set(keywords) - {"key", "reverse"} or keywords.get("key", constant(None)) != constant(
            None
        ):
            return unknown
        direction = keywords.get("reverse", constant(False))
        if direction.kind != "const" or not isinstance(direction.data, bool):
            return unknown
        reverse = direction.data
    if any(value.kind in ("unknown", "missing") for value in values):
        return next(value for value in values if value.kind in ("unknown", "missing"))
    columns = [elements(value) for value in values]
    open_ = any(
        column is None or value.ref in ("open", "unordered")
        for column, value in zip(columns, values, strict=True)
    )
    filled = [
        column if column is not None else (Val("obj", f"Element von {value.ref}"),)
        for column, value in zip(columns, values, strict=True)
    ]
    if ref == "builtins.enumerate":
        items = tuple(
            Val("seq", "", (Val("obj", "Zähler") if open_ else constant(number), item))
            for number, item in enumerate(filled[0], start)
        )
    elif ref == "builtins.zip":
        if open_:
            if math.prod(map(len, filled)) > limit:
                return Val("unknown", "zu viele Zeilen")
            combos = itertools.product(*filled)
        else:
            if strict and len({len(column) for column in filled}) > 1:
                return unknown
            combos = zip(*filled, strict=strict)
        items = tuple(Val("seq", "", tuple(combo)) for combo in combos)
    else:
        items = filled[0]
        if ref in ("builtins.set", "builtins.frozenset"):
            order = "open" if values[0].ref == "open" else "unordered"
            return Val("seq", order, unordered_items(items))
        if ref == "builtins.sorted" and values[0].ref == "unordered":
            open_ = False
        if not open_ and ref == "builtins.sorted":
            if all(item.kind == "const" and isinstance(item.data, (int, float)) for item in items):
                items = tuple(sorted(items, key=_numeric, reverse=reverse))
            elif all(item.kind == "const" and isinstance(item.data, str) for item in items):
                items = tuple(sorted(items, key=_string, reverse=reverse))
            else:
                return unknown
        elif not open_ and ref == "builtins.reversed":
            items = items[::-1]
    order = "open" if open_ else ""
    if (
        ref in ("builtins.list", "builtins.tuple", "builtins.reversed")
        and values[0].ref == "unordered"
    ):
        order = "unordered"
    return Val("seq", order, items)
