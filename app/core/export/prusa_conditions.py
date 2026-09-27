"""PrusaSlicers Verträglichkeitsbedingungen, ohne ``eval`` ausgewertet (Regel 10).

Ein Prozess- oder Filamentprofil in PrusaSlicers Bündel sagt meist nicht mit
einer Liste, zu welchen Druckern es passt, sondern mit einer Bedingung über die
Werte des Druckers::

    printer_model=~/(MK4S|MK4SMMU3)/ and nozzle_diameter[0]!=0.8 and nozzle_high_flow[0]

Solidon las nur die Liste. Damit galten am MK4S 6740 von 6772 Filamenten des
Bestands als verträglich, das PETG der Vorwahl kam aus irgendeinem Bündel, und
die Suche stand 43 Sekunden (gemessen 27.09.2026, PrusaSlicer 2.9.6).

Ausgewertet wird die Teilmenge, die in den Bündeln von PrusaSlicer 2.9.6
vorkommt: Kennungen mit Index (``nozzle_diameter[0]``), Zeichenketten, Zahlen,
reguläre Ausdrücke zwischen Schrägstrichen, ``== != < <= > >= =~ !~``,
``and or not !`` und Klammern. ``=~`` muss wie in PrusaSlicer den ganzen Text
treffen. Was darüber hinausgeht, ist :class:`ConditionError`, und das Profil
gilt als nicht verträglich: lieber eine Auswahl zu wenig als eine, die nicht
passt.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Final

#: Werte, die PrusaSlicer je Extruder als Liste führt. Eine Bedingung nennt sie
#: mit Index; ohne Index sind sie kein Wert, den eine Bedingung vergleichen kann.
VECTOR_KEYS: Final = frozenset(
    {"nozzle_diameter", "nozzle_high_flow", "filament_type", "extruder_colour", "filament_diameter"}
)


class ConditionError(ValueError):
    """Eine Bedingung, die Solidon nicht lesen oder nicht auswerten kann."""


_TOKEN: Final = re.compile(
    r"""
    \s*(?:
        (?P<string>"(?:[^"\\]|\\.)*")
      | (?P<regex>/(?:[^/\\]|\\.)*/)
      | (?P<number>\d+(?:\.\d*)?|\.\d+)
      | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<operator>==|!=|<=|>=|=~|!~|<|>|!|\(|\)|\[|\])
    )
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str


def _tokens(condition: str) -> list[_Token]:
    found: list[_Token] = []
    position = 0
    while position < len(condition):
        if condition[position:].strip() == "":
            break
        matched = _TOKEN.match(condition, position)
        if matched is None or matched.lastgroup is None:
            raise ConditionError(
                f"unreadable at {position}: {condition[position : position + 20]!r}"
            )
        found.append(_Token(matched.lastgroup, matched.group(matched.lastgroup)))
        position = matched.end()
    return found


# Knoten des Ausdrucks: ("or", a, b) · ("and", a, b) · ("not", a) · ("cmp", op, a, b)
# · ("var", name, index | None) · ("str", text) · ("num", text) · ("re", pattern)
# · ("bool", True | False)
_Node = tuple[Any, ...]


class _Parser:
    """Rekursiver Abstieg: or < and < not < Vergleich < Operand."""

    def __init__(self, tokens: Sequence[_Token]) -> None:
        self._tokens = list(tokens)
        self._index = 0

    def parse(self) -> _Node:
        node = self._or()
        if self._index != len(self._tokens):
            raise ConditionError(f"unexpected {self._tokens[self._index].text!r}")
        return node

    def _peek(self) -> _Token | None:
        return self._tokens[self._index] if self._index < len(self._tokens) else None

    def _take(self, text: str) -> bool:
        token = self._peek()
        if token is not None and token.text == text and token.kind in ("name", "operator"):
            self._index += 1
            return True
        return False

    def _next(self) -> _Token:
        token = self._peek()
        if token is None:
            raise ConditionError("condition ends too early")
        self._index += 1
        return token

    def _or(self) -> _Node:
        node = self._and()
        while self._take("or"):
            node = ("or", node, self._and())
        return node

    def _and(self) -> _Node:
        node = self._not()
        while self._take("and"):
            node = ("and", node, self._not())
        return node

    def _not(self) -> _Node:
        if self._take("not") or self._take("!"):
            return ("not", self._not())
        return self._comparison()

    def _comparison(self) -> _Node:
        left = self._operand()
        token = self._peek()
        if token is not None and token.kind == "operator" and token.text in _COMPARISONS:
            self._index += 1
            return ("cmp", token.text, left, self._operand())
        return left

    def _operand(self) -> _Node:
        token = self._next()
        if token.kind == "operator" and token.text == "(":
            node = self._or()
            if not self._take(")"):
                raise ConditionError("missing )")
            return node
        if token.kind == "string":
            return ("str", _unquoted(token.text))
        if token.kind == "number":
            return ("num", token.text)
        if token.kind == "regex":
            return ("re", token.text[1:-1])
        if token.kind == "name":
            if token.text in ("true", "false"):
                return ("bool", token.text == "true")
            if token.text in ("and", "or", "not"):
                raise ConditionError(f"unexpected {token.text!r}")
            index: int | None = None
            if self._take("["):
                number = self._next()
                if number.kind != "number" or not number.text.isdigit():
                    raise ConditionError("index must be a whole number")
                index = int(number.text)
                if not self._take("]"):
                    raise ConditionError("missing ]")
            return ("var", token.text, index)
        raise ConditionError(f"unexpected {token.text!r}")


_COMPARISONS: Final = frozenset({"==", "!=", "<", "<=", ">", ">=", "=~", "!~"})


def _unquoted(text: str) -> str:
    return re.sub(r"\\(.)", r"\1", text[1:-1])


@lru_cache(maxsize=4096)
def parse(condition: str) -> _Node:
    """Die Bedingung als Baum — einmal je Text, denn Tausende Profile teilen sich
    wenige Dutzend Bedingungen."""
    tokens = _tokens(condition)
    if not tokens:
        raise ConditionError("empty condition")
    return _Parser(tokens).parse()


def _value(node: _Node, variables: Mapping[str, str]) -> object:
    kind = node[0]
    if kind == "str":
        return node[1]
    if kind == "num":
        return float(node[1])
    if kind == "bool":
        return node[1]
    if kind == "re":
        raise ConditionError("a regular expression is no value")
    if kind == "var":
        name, index = node[1], node[2]
        if name == "num_extruders" and index is None:
            return float(len(_items(variables.get("nozzle_diameter", ""))))
        if name not in variables:
            raise ConditionError(f"unknown value {name!r}")
        raw = variables[name]
        if index is None:
            if name in VECTOR_KEYS:
                raise ConditionError(f"{name} needs an index")
            return raw
        items = _items(raw)
        if index >= len(items):
            raise ConditionError(f"{name}[{index}] is out of range")
        return items[index]
    return _truth(node, variables)


def _items(raw: str) -> list[str]:
    return [item.strip().strip('"') for item in raw.split(",")] if raw else []


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, float):
        return value
    try:
        return float(str(value))
    except ValueError:
        return None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    number = _number(value)
    if number is not None:
        return number != 0.0
    return str(value).strip().casefold() == "true"


def _truth(node: _Node, variables: Mapping[str, str]) -> bool:
    kind = node[0]
    if kind == "or":
        return _truth(node[1], variables) or _truth(node[2], variables)
    if kind == "and":
        return _truth(node[1], variables) and _truth(node[2], variables)
    if kind == "not":
        return not _truth(node[1], variables)
    if kind == "cmp":
        operator, left, right = node[1], node[2], node[3]
        if operator in ("=~", "!~"):
            if right[0] != "re":
                raise ConditionError(f"{operator} needs a regular expression")
            text = str(_value(left, variables))
            try:
                found = re.fullmatch(right[1], text, re.DOTALL) is not None
            except re.error as problem:
                raise ConditionError(f"bad regular expression: {problem}") from problem
            return found if operator == "=~" else not found
        a, b = _value(left, variables), _value(right, variables)
        first, second = _number(a), _number(b)
        if first is not None and second is not None:
            return _compare(operator, first, second)
        return _compare(operator, str(a), str(b))
    return _as_bool(_value(node, variables))


def _compare[T: (float, str)](operator: str, x: T, y: T) -> bool:
    """Zwei Zahlen oder zwei Texte — PrusaSlicer vergleicht ``"0.4"`` mit 0.4 als Zahl."""
    if operator == "==":
        return x == y
    if operator == "!=":
        return x != y
    if operator == "<":
        return x < y
    if operator == "<=":
        return x <= y
    if operator == ">":
        return x > y
    return x >= y


def holds(condition: str, variables: Mapping[str, str]) -> bool:
    """Trifft die Bedingung auf einen Drucker mit diesen Werten zu?

    ``variables`` sind die aufgelösten Werte des Druckerprofils, wie sie in der
    INI stehen (Listen durch Kommas getrennt). Eine leere Bedingung trifft zu.
    Eine, die sich nicht lesen oder auswerten lässt, wirft
    :class:`ConditionError`.
    """
    if not condition.strip():
        return True
    return _truth(parse(condition), variables)
