"""Parameter expressions with an own grammar (Bauplan §13, §32).

Project files travel between people, so a foreign file must never execute
anything. That rules out ``eval`` — also a guarded one. Instead: a tokeniser and
a recursive-descent parser over a grammar small enough to read in one go.

    expression := term (("+" | "-") term)*
    term       := factor (("*" | "/") factor)*
    factor     := ("+" | "-") factor | primary
    primary    := NUMBER | "@" NAME | FUNCTION "(" arguments ")" | "(" expression ")"
    arguments  := expression ("," expression)*

Functions: ``min``, ``max``, ``round``, ``abs``. Everything else is rejected —
names without ``@``, attribute access, calls, powers, comparisons, bit
operations. What the grammar does not contain cannot happen.

Written as ``"=@width/2 - @wall"`` or, for a plain reference, ``"@width"``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Final, TypeGuard

from app.core.errors import ValidationError
from app.core.types import Parameter, ParameterName
from app.i18n import _

EXPRESSION_PREFIX: Final = "="
REFERENCE_PREFIX: Final = "@"

_MAX_DEPTH: Final = 32
_NAME_PATTERN: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_PATTERN: Final = re.compile(r"\d+(\.\d+)?")

_FUNCTIONS: Final[dict[str, tuple[int, int, Callable[..., float]]]] = {
    # name: (minimum arguments, maximum arguments, implementation)
    "min": (2, 8, min),
    "max": (2, 8, max),
    "abs": (1, 1, abs),
    "round": (1, 2, lambda value, digits=0: round(value, int(digits))),
}


def is_expression(text: object) -> TypeGuard[str]:
    """True for a value that has to be evaluated rather than taken as a number."""
    return isinstance(text, str) and text.startswith((EXPRESSION_PREFIX, REFERENCE_PREFIX))


# --- Tokenising ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    position: int


def _fail(detail: str, source: str, position: int) -> ValidationError:
    return ValidationError(
        field="expression",
        detail=detail,
        value=source,
        constraint="grammar",
        values={"position": position},
    )


def _tokenise(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    length = len(source)
    while index < length:
        character = source[index]
        if character.isspace():
            index += 1
            continue
        if character in "+-*/(),":
            tokens.append(_Token(character, character, index))
            index += 1
            continue
        if character == REFERENCE_PREFIX:
            match = _NAME_PATTERN.match(source, index + 1)
            if match is None:
                raise _fail(
                    str(_("Nach @ muss ein Parametername stehen.")),
                    source,
                    index,
                )
            tokens.append(_Token("reference", match.group(), index))
            index = match.end()
            continue
        number = _NUMBER_PATTERN.match(source, index)
        if number is not None:
            tokens.append(_Token("number", number.group(), index))
            index = number.end()
            continue
        name = _NAME_PATTERN.match(source, index)
        if name is not None:
            if name.group() not in _FUNCTIONS:
                raise _fail(
                    str(_("Unbekannter Name im Ausdruck. Parameter werden mit @ geschrieben.")),
                    source,
                    index,
                )
            tokens.append(_Token("function", name.group(), index))
            index = name.end()
            continue
        raise _fail(str(_("Dieses Zeichen ist in Ausdrücken nicht erlaubt.")), source, index)
    tokens.append(_Token("end", "", length))
    return tokens


# --- Parsing and evaluation ----------------------------------------------------


class _Parser:
    """Recursive descent. Parses and evaluates in one pass — the tree is not needed."""

    def __init__(self, source: str, values: Mapping[str, float] | None) -> None:
        self.source = source
        self.values = values
        self.tokens = _tokenise(source)
        self.index = 0
        self.references: set[str] = set()

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def advance(self) -> _Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def expect(self, kind: str) -> _Token:
        if self.current.kind != kind:
            raise _fail(
                str(_("Der Ausdruck ist unvollständig oder falsch geklammert.")),
                self.source,
                self.current.position,
            )
        return self.advance()

    def run(self) -> float:
        value = self.expression(0)
        if self.current.kind != "end":
            raise _fail(
                str(_("Nach dem Ausdruck steht noch etwas.")),
                self.source,
                self.current.position,
            )
        return value

    def expression(self, depth: int) -> float:
        self._check_depth(depth)
        value = self.term(depth + 1)
        while self.current.kind in ("+", "-"):
            operator = self.advance().kind
            right = self.term(depth + 1)
            value = value + right if operator == "+" else value - right
        return value

    def term(self, depth: int) -> float:
        self._check_depth(depth)
        value = self.factor(depth + 1)
        while self.current.kind in ("*", "/"):
            token = self.advance()
            right = self.factor(depth + 1)
            if token.kind == "*":
                value *= right
                continue
            if right == 0.0:
                raise _fail(
                    str(_("Division durch null.")),
                    self.source,
                    token.position,
                )
            value /= right
        return value

    def factor(self, depth: int) -> float:
        self._check_depth(depth)
        if self.current.kind == "-":
            self.advance()
            return -self.factor(depth + 1)
        if self.current.kind == "+":
            self.advance()
            return self.factor(depth + 1)
        return self.primary(depth + 1)

    def primary(self, depth: int) -> float:
        self._check_depth(depth)
        token = self.current
        if token.kind == "number":
            self.advance()
            return float(token.text)
        if token.kind == "reference":
            self.advance()
            self.references.add(token.text)
            return self._lookup(token)
        if token.kind == "function":
            self.advance()
            return self._call(token, depth)
        if token.kind == "(":
            self.advance()
            value = self.expression(depth + 1)
            self.expect(")")
            return value
        raise _fail(
            str(_("Hier wird eine Zahl, ein Parameter oder eine Klammer erwartet.")),
            self.source,
            token.position,
        )

    def _call(self, token: _Token, depth: int) -> float:
        minimum, maximum, function = _FUNCTIONS[token.text]
        self.expect("(")
        arguments = [self.expression(depth + 1)]
        while self.current.kind == ",":
            self.advance()
            arguments.append(self.expression(depth + 1))
        self.expect(")")
        if not minimum <= len(arguments) <= maximum:
            raise _fail(
                str(_("Diese Funktion wurde mit der falschen Anzahl an Werten aufgerufen.")),
                self.source,
                token.position,
            )
        return float(function(*arguments))

    def _lookup(self, token: _Token) -> float:
        if self.values is None:
            return 0.0
        if token.text not in self.values:
            raise ValidationError(
                field="expression",
                detail=_("Der Ausdruck verweist auf einen Parameter, den es nicht gibt."),
                value=self.source,
                constraint="unknown_parameter",
                values={"parameter": token.text},
            )
        return float(self.values[token.text])

    def _check_depth(self, depth: int) -> None:
        if depth > _MAX_DEPTH:
            raise _fail(
                str(_("Der Ausdruck ist zu tief verschachtelt.")),
                self.source,
                self.current.position,
            )


def _body(text: str) -> str:
    return text[1:] if text.startswith(EXPRESSION_PREFIX) else text


def evaluate(text: str, values: Mapping[str, float]) -> float:
    """Evaluate an expression against the current parameter values."""
    result = _Parser(_body(text), values).run()
    if not math.isfinite(result):
        raise _fail(str(_("Das Ergebnis ist keine gültige Zahl.")), text, 0)
    return result


def references(text: str) -> frozenset[str]:
    """Parameters an expression reads. Also the syntax check (§13)."""
    parser = _Parser(_body(text), None)
    parser.run()
    return frozenset(parser.references)


def check(text: str) -> None:
    """Reject anything outside the grammar. Raises, or returns quietly."""
    references(text)


# --- Parameter resolution ------------------------------------------------------


def dependencies(parameters: Mapping[ParameterName, Parameter]) -> dict[ParameterName, set[str]]:
    """Which parameter reads which — the graph the cycle check runs on."""
    graph: dict[ParameterName, set[str]] = {}
    for name, parameter in parameters.items():
        expression = parameter.expression
        graph[name] = set(references(expression)) if expression else set()
    return graph


def resolution_order(parameters: Mapping[ParameterName, Parameter]) -> list[ParameterName]:
    """Order in which parameters can be evaluated. Cycles are rejected (§13)."""
    graph = dependencies(parameters)
    unknown = {
        reference for reads in graph.values() for reference in reads if reference not in parameters
    }
    if unknown:
        raise ValidationError(
            field="parameters",
            detail=_("Ein Ausdruck verweist auf einen Parameter, den es nicht gibt."),
            constraint="unknown_parameter",
            values={"missing": sorted(unknown)},
        )

    order: list[ParameterName] = []
    state: dict[ParameterName, int] = dict.fromkeys(graph, 0)  # 0 open, 1 visiting, 2 done
    path: list[ParameterName] = []

    def visit(name: ParameterName) -> None:
        if state[name] == 2:
            return
        if state[name] == 1:
            cycle = [*path[path.index(name) :], name]
            raise ValidationError(
                field="parameters",
                detail=_("Die Parameter verweisen im Kreis aufeinander."),
                constraint="cycle",
                values={"cycle": cycle},
            )
        state[name] = 1
        path.append(name)
        for reference in sorted(graph[name]):
            visit(reference)
        path.pop()
        state[name] = 2
        order.append(name)

    for name in sorted(graph):
        visit(name)
    return order


def resolve(parameters: Mapping[ParameterName, Parameter]) -> dict[ParameterName, float]:
    """Evaluate all parameters in dependency order."""
    values: dict[ParameterName, float] = {}
    for name in resolution_order(parameters):
        parameter = parameters[name]
        values[name] = (
            evaluate(parameter.expression, values) if parameter.expression else parameter.value
        )
    return values


def resolve_value(value: object, values: Mapping[str, float]) -> object:
    """Resolve one operation parameter: expressions become numbers, the rest passes."""
    return evaluate(value, values) if is_expression(value) else value


def resolve_params(params: Mapping[str, object], values: Mapping[str, float]) -> dict[str, object]:
    """Resolve a whole stored parameter set before validation (§10, §13)."""
    return {name: resolve_value(entry, values) for name, entry in params.items()}


def used_parameters(params: Iterable[object]) -> frozenset[str]:
    """Which project parameters a stored parameter set depends on."""
    found: set[str] = set()
    for entry in params:
        if is_expression(entry):
            found |= references(str(entry))
    return frozenset(found)
