"""Parameterausdrücke mit eigener Grammatik (Bauplan §13, §32).

Projektdateien wandern zwischen Leuten, also darf eine fremde Datei nie etwas
ausführen. Das schließt ``eval`` aus — auch ein abgesichertes. Stattdessen:
ein Tokenisierer und ein rekursiver Abstiegsparser über einer Grammatik, die
sich in einem Zug lesen lässt.

    expression := term (("+" | "-") term)*
    term       := factor (("*" | "/") factor)*
    factor     := ("+" | "-") factor | primary
    primary    := NUMBER | "@" NAME | FUNCTION "(" arguments ")" | "(" expression ")"
    arguments  := expression ("," expression)*

Funktionen: ``min``, ``max``, ``round``, ``abs``. Alles andere wird
abgelehnt — Namen ohne ``@``, Attributzugriffe, Aufrufe, Potenzen,
Vergleiche, Bit-Operationen. Was die Grammatik nicht enthält, kann nicht
passieren.

Geschrieben als ``"=@width/2 - @wall"`` oder, für den nackten Verweis,
``"@width"``.
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
    # Name: (Mindest-Argumente, Höchst-Argumente, Umsetzung)
    "min": (2, 8, min),
    "max": (2, 8, max),
    "abs": (1, 1, abs),
    "round": (1, 2, lambda value, digits=0: round(value, int(digits))),
}


def is_expression(text: object) -> TypeGuard[str]:
    """True für einen Wert, der ausgewertet werden muss, statt als Zahl
    genommen zu werden."""
    return isinstance(text, str) and text.startswith((EXPRESSION_PREFIX, REFERENCE_PREFIX))


# --- Tokenisieren ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    position: int


def _fail(detail: str, source: str, position: int) -> ValidationError:
    # Der Vorgabetitel von ValidationError spricht von einem Wert außerhalb
    # seines Bereichs. Hier ist nichts außerhalb eines Bereichs — hier steht
    # ein Zeichen an einer Stelle, an der der Auswerter keines lesen kann.
    return ValidationError(
        title=_("Dieser Ausdruck lässt sich nicht lesen."),
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


# --- Zerlegen und Auswerten ----------------------------------------------------


class _Parser:
    """Rekursiver Abstieg. Parst und wertet in einem Durchgang — der Baum wird
    nicht gebraucht."""

    def __init__(self, source: str, values: Mapping[str, float] | None) -> None:
        self.source = source
        self.values = values
        self.tokens = _tokenise(source)
        self.index = 0
        self.references: set[str] = set()
        # Zählt jedes Referenz-Vorkommen, auch das wiederholte — das Set
        # dedupliziert und taugt deshalb nicht als Vorher-nachher-Marke.
        self.reference_hits = 0

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
            # **Ein übrig gebliebenes Komma ist fast immer ein Dezimalkomma.**
            # Die Zahlenfelder der Oberfläche lesen „12,5" richtig — sie sind
            # ausdrücklich dafür gebaut —, hier geht es nicht: Das Komma trennt
            # die Argumente von ``min`` und ``max``, und ``max(1,5)`` wäre sonst
            # nicht von ``max(1.5)`` zu unterscheiden. Das ist ein Grund, den
            # der Kunde nicht ahnen kann, und „Nach dem Ausdruck steht noch
            # etwas" schickt ihn ans Ende statt in die Mitte.
            if self.current.kind == ",":
                raise _fail(
                    str(_("Zahlen werden hier mit Punkt geschrieben: 10.5 statt 10,5.")),
                    self.source,
                    self.current.position,
                )
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
            marker = self.reference_hits
            right = self.factor(depth + 1)
            if token.kind == "*":
                value *= right
                continue
            if right == 0.0:
                # Der Vergleich mit exakt null ist hier richtig: nur exakt
                # null teilt nicht. Im Prüfmodus stehen Referenzen aber als
                # Platzhalter-Null da — hängt der Nenner an einer, entscheidet
                # erst die Auswertung mit echten Werten, ob durch null geteilt
                # wird. Eine Literal-Null bleibt auch im Prüfmodus ein Fehler.
                if self.values is None and self.reference_hits > marker:
                    continue
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
            self.reference_hits += 1
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
    """Wertet einen Ausdruck gegen die aktuellen Parameterwerte aus."""
    result = _Parser(_body(text), values).run()
    if not math.isfinite(result):
        raise _fail(str(_("Das Ergebnis ist keine gültige Zahl.")), text, 0)
    return result


def references(text: str) -> frozenset[str]:
    """Die Parameter, die ein Ausdruck liest. Zugleich die Syntaxprüfung (§13)."""
    parser = _Parser(_body(text), None)
    parser.run()
    return frozenset(parser.references)


def check(text: str) -> None:
    """Lehnt alles außerhalb der Grammatik ab. Wirft — oder kehrt still zurück."""
    references(text)


def function_names() -> tuple[str, ...]:
    """Die Namen, die ein Ausdruck aufrufen darf — alphabetisch.

    Für die Hilfe an der Oberfläche: Wer das Ausdrucksfeld aufmacht, sieht ein
    leeres Feld und muss raten, was darin erlaubt ist. Die Namen kommen aus
    **derselben** Tabelle, gegen die der Auswerter prüft (:data:`_FUNCTIONS`);
    eine zweite Liste in der Oberfläche wäre beim nächsten Zuwachs still falsch
    und würde etwas anbieten, das die Grammatik ablehnt.
    """
    return tuple(sorted(_FUNCTIONS))


# --- Parameterauflösung ----------------------------------------------------------


def dependencies(parameters: Mapping[ParameterName, Parameter]) -> dict[ParameterName, set[str]]:
    """Welcher Parameter welchen liest — der Graph, auf dem die Zyklusprüfung
    läuft."""
    graph: dict[ParameterName, set[str]] = {}
    for name, parameter in parameters.items():
        expression = parameter.expression
        graph[name] = set(references(expression)) if expression else set()
    return graph


def resolution_order(parameters: Mapping[ParameterName, Parameter]) -> list[ParameterName]:
    """Die Reihenfolge, in der sich die Parameter auswerten lassen. Zyklen
    werden abgelehnt (§13)."""
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
    """Wertet alle Parameter in Abhängigkeitsreihenfolge aus.

    Grenzen (``minimum``/``maximum``) prüft **nicht** diese Stelle: Ein Halt
    hier machte eine geöffnete Datei mit einem hinausgelaufenen Ausdruck
    unauswertbar — eine Sackgasse, wo ein Befund reicht (Regel 19). Die
    Eingabe prüft der Dialog, das Ergebnis meldet die Auswertung als Befund
    (Gesamtreview B-15, ``scene/evaluate.py``).
    """
    values: dict[ParameterName, float] = {}
    for name in resolution_order(parameters):
        parameter = parameters[name]
        values[name] = (
            evaluate(parameter.expression, values) if parameter.expression else parameter.value
        )
    return values


def resolve_value(value: object, values: Mapping[str, float]) -> object:
    """Löst einen Operationsparameter auf: Ausdrücke werden Zahlen, der Rest
    geht durch."""
    return evaluate(value, values) if is_expression(value) else value


def resolve_params(params: Mapping[str, object], values: Mapping[str, float]) -> dict[str, object]:
    """Löst einen ganzen gespeicherten Parametersatz vor der
    Validierung auf (§10, §13)."""
    return {name: resolve_value(entry, values) for name, entry in params.items()}


def used_parameters(params: Iterable[object]) -> frozenset[str]:
    """Von welchen Projektparametern ein gespeicherter Parametersatz abhängt."""
    found: set[str] = set()
    for entry in params:
        if is_expression(entry):
            found |= references(str(entry))
    return frozenset(found)
