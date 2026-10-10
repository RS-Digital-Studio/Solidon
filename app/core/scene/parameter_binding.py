"""Feste Zahlen, die zu einem Projektmaß passen — und ihre Bindung (Dateiaudit §4, RM-184).

Ein Projektmaß wirkt nur dort, wo ein Schritt es liest. Am Puppenhaus aus dem
Dateiaudit lasen Länge und Breite nur den Boden; Wandring, Fenster und Tür
standen mit festen Zahlen da, die genau zu diesen Maßen passten: die Wand bei
90 und -90 ist die halbe Länge, das Fenster bei 58,5 die halbe Breite weniger
die halbe Wand. Am aufklappbaren Schrank lag das Scharnier 60 breit bei -30 —
Breite und halbe Breite des Korpus, beide fest.

Diese Suche findet solche Zahlen und schlägt die Ausdrücke vor, die sie aus
den Maßen machen. **Gebunden wird nur, was der Kunde wählt** (Regel 21):
Dieselbe Zahl kann aus zwei Maßen kommen, und eine zufällig gleiche Zahl ist
keine Absicht. Gesucht wird in Längenfeldern der Schritte und in Zeichnungen,
dort an achsparallelen Rechtecken um den Ursprung — deren Breite und Höhe
werden zu Maßen der Zeichnung, und Waagerecht, Senkrecht und die Mitte im
Ursprung halten das Rechteck dabei in Form.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any, Final

from app.core import expressions
from app.core.errors import AppError
from app.core.registry import REGISTRY, Registry
from app.core.types import (
    Document,
    OpId,
    ParameterName,
    Sketch,
    SketchConstraint,
    SketchElement,
)

#: Wie genau eine feste Zahl zu einem Ausdruck passen muss: die Rundung einer
#: gespeicherten Zahl, keine Fertigungstoleranz. 58,5 aus 120 / 2 - 3 / 2
#: trifft auf die letzte Stelle.
MATCH: Final[float] = 1e-6

#: Wie viele Vorschläge eine Stelle höchstens nennt — mehr liest niemand.
MOST_CHOICES: Final[int] = 3

#: Die Faktoren eines Maßes allein, in der Reihenfolge der Vorschläge: selbst,
#: negativ, die Hälfte (eine Mitte), die negative Hälfte, das Doppelte.
_SINGLE: Final[tuple[float, ...]] = (1.0, -1.0, 0.5, -0.5, 2.0)

#: Zwei Maße zusammen: Breite minus zwei Wände, halbe Breite minus Wand.
_FIRST: Final[tuple[float, ...]] = (1.0, -1.0, 0.5, -0.5)
_SECOND: Final[tuple[float, ...]] = (1.0, -1.0, 0.5, -0.5, 2.0, -2.0)


@dataclass(frozen=True, slots=True)
class BindingChoice:
    """Ein Ausdruck, der eine feste Zahl aus Projektmaßen macht."""

    expression: str
    parameters: tuple[ParameterName, ...]
    exact: bool
    """Genau ein Maß, unverändert — der Vorschlag, der vorgewählt steht."""


@dataclass(frozen=True, slots=True)
class BindingSpot:
    """Eine feste Zahl im Stapel, die zu Projektmaßen passt."""

    op_id: OpId
    field: str
    value: float
    choices: tuple[BindingChoice, ...]
    rectangle: int | None = None
    """In einer Zeichnung: das wievielte Rechteck um den Ursprung."""
    side: str = ""
    """In einer Zeichnung: ``width`` (entlang x) oder ``height`` (entlang y)."""
    size: bool = True
    """Ob die Zahl eine Größe ist — ihr Feld lässt nichts unter null zu. Eine
    Lage (x, y, z, ein Versatz) darf negativ sein und ist keine Größe."""

    @property
    def key(self) -> tuple[OpId, str, int, str]:
        """Woran eine Wahl die Stelle wiederfindet (:func:`bound_params`)."""
        return (self.op_id, self.field, -1 if self.rectangle is None else self.rectangle, self.side)

    @property
    def certain(self) -> bool:
        """Ob der Vorschlag ohne Zweifel ist: eine Größe, und genau ein Maß hat dieselbe Zahl.

        Eine Hälfte oder ein Doppeltes daneben zweifelt ihn nicht an — 180 ist
        die Hauslänge, auch wenn zwei Etagen zufällig ebenso hoch sind. Zwei
        Maße mit derselben Zahl dagegen sind zwei Absichten, und keine steht
        vor. **Eine Lage steht nie vor**: Im Puppenhaus des Audits liegt die
        Tür bei z = 30 und ist das Fenster 30 breit — dieselbe Zahl, keine
        Absicht; gemeint war die halbe Türhöhe.
        """
        return (
            self.size
            and self.choices[0].exact
            and sum(choice.exact for choice in self.choices) == 1
        )


def binding_spots(document: Document, registry: Registry | None = None) -> tuple[BindingSpot, ...]:
    """Alle festen Zahlen des Stapels, die zu Projektmaßen passen — in Stapelfolge.

    Unlesbare Ausdrücke der Maße machen die Suche leer statt falsch: Ohne Werte
    gibt es nichts zu vergleichen, und ``parameter_uses`` meldet den Fehler.
    """
    if not document.parameters:
        return ()
    try:
        values = expressions.resolve(document.parameters)
    except AppError:
        return ()
    known = {
        name: value
        for name in document.parameters
        if (value := values.get(name)) is not None and math.isfinite(value) and abs(value) > MATCH
    }
    if not known:
        return ()
    source = registry or REGISTRY
    index = _Index.of(known)
    found: list[BindingSpot] = []
    for operation in document.ops:
        specs = {entry.name: entry for entry in source.get(operation.op).params.spec()}
        for field, value in operation.params.items():
            spec = specs.get(field)
            if spec is None:
                continue
            if spec.kind == "sketch" and isinstance(value, str) and value:
                found.extend(_sketch_spots(operation.id, field, value, index))
                continue
            if spec.kind != "float" or spec.unit != "mm":
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            number = float(value)
            if not math.isfinite(number) or abs(number) <= MATCH:
                continue
            choices = index.matching(number)
            if choices:
                size = spec.minimum is not None and spec.minimum >= 0.0
                found.append(BindingSpot(operation.id, field, number, choices, size=size))
    return tuple(found)


def matching_expressions(
    value: float, known: Mapping[ParameterName, float]
) -> tuple[BindingChoice, ...]:
    """Die einfachsten Ausdrücke aus Projektmaßen, die genau diese Zahl ergeben.

    Erst ein Maß allein (selbst, negativ, halb, doppelt), dann zwei — und zwei
    nur, wenn eines allein nicht reicht: Sonst stünde neben „Breite“ auch
    „Länge minus Wand“, sobald die Zahlen zufällig passen.
    """
    return _Index.of(known).matching(value)


@dataclass(frozen=True, slots=True)
class _Index:
    """Die Maße einer Suche, einmal sortiert — für jede Zahl des Stapels dieselben.

    Die Paarsuche fragt je erstem Maß und Faktor nur noch den Bereich der
    sortierten zweiten Terme um den Rest ab (``bisect``), statt jedes Paar mit
    jedem Faktor durchzurechnen: An 30 Maßen und 500 Längenfeldern kostete
    das eine Sekunde je Auswertung. Geprüft wird jeder Kandidat mit derselben
    Rechnung wie zuvor, und die Folge der Treffer ist die der vollen Suche —
    erstes Maß, zweites Maß, erster Faktor, zweiter Faktor.
    """

    names: tuple[ParameterName, ...]
    numbers: tuple[float, ...]
    terms: tuple[float, ...]
    """Alle zweiten Terme ``Faktor · Maß``, aufsteigend."""
    owners: tuple[tuple[int, int], ...]
    """Je Eintrag in ``terms``: Nummer des Maßes und des Faktors in ``_SECOND``."""

    @classmethod
    def of(cls, known: Mapping[ParameterName, float]) -> _Index:
        names = tuple(known)
        numbers = tuple(float(known[name]) for name in names)
        entries = sorted(
            (factor * number, position, rank)
            for position, number in enumerate(numbers)
            for rank, factor in enumerate(_SECOND)
        )
        return cls(
            names,
            numbers,
            tuple(entry[0] for entry in entries),
            tuple((entry[1], entry[2]) for entry in entries),
        )

    def matching(self, value: float) -> tuple[BindingChoice, ...]:
        reach = MATCH * max(1.0, abs(value))
        single: list[tuple[int, BindingChoice]] = []
        for name, number in zip(self.names, self.numbers, strict=True):
            for rank, factor in enumerate(_SINGLE):
                if abs(factor * number - value) <= reach:
                    single.append(
                        (rank, BindingChoice(_rendered(((factor, name),)), (name,), factor == 1.0))
                    )
        if single:
            single.sort(key=lambda entry: entry[0])
            return tuple(choice for _rank, choice in single[:MOST_CHOICES])
        # Das Fenster ist doppelt so weit wie die Prüfung: Rest und Summe
        # runden verschieden, und kein Kandidat darf am Fenster hängen.
        found: list[tuple[int, int, int, int]] = []
        for first, number_a in enumerate(self.numbers):
            for rank_a, factor_a in enumerate(_FIRST):
                rest = value - factor_a * number_a
                low = bisect.bisect_left(self.terms, rest - 2.0 * reach)
                high = bisect.bisect_right(self.terms, rest + 2.0 * reach)
                for second, rank_b in self.owners[low:high]:
                    if second == first:
                        continue
                    total = factor_a * number_a + _SECOND[rank_b] * self.numbers[second]
                    if abs(total - value) <= reach:
                        found.append((first, second, rank_a, rank_b))
        double: list[BindingChoice] = []
        seen: set[frozenset[tuple[float, ParameterName]]] = set()
        for first, second, rank_a, rank_b in sorted(found):
            pair = ((_FIRST[rank_a], self.names[first]), (_SECOND[rank_b], self.names[second]))
            terms = frozenset(pair)
            if terms in seen:
                continue
            seen.add(terms)
            double.append(
                BindingChoice(_rendered(pair), (self.names[first], self.names[second]), exact=False)
            )
            if len(double) >= MOST_CHOICES:
                break
        return tuple(double)


def _term(factor: float, name: ParameterName) -> str:
    reference = f"{expressions.REFERENCE_PREFIX}{name}"
    return {
        1.0: reference,
        -1.0: f"-{reference}",
        0.5: f"{reference} / 2",
        -0.5: f"-{reference} / 2",
        2.0: f"2 * {reference}",
        -2.0: f"-2 * {reference}",
    }[factor]


def _rendered(terms: Sequence[tuple[float, ParameterName]]) -> str:
    """Der Ausdruck in der Schreibweise der Projektdatei: ``@a`` oder ``=…``."""
    (factor, name), *rest = terms
    if not rest and factor == 1.0:
        return f"{expressions.REFERENCE_PREFIX}{name}"
    text = _term(factor, name)
    for factor_b, name_b in rest:
        if factor_b < 0:
            text += f" - {_term(-factor_b, name_b)}"
        else:
            text += f" + {_term(factor_b, name_b)}"
    return f"{expressions.EXPRESSION_PREFIX}{text}"


# --- Zeichnungen: Rechtecke um den Ursprung ---------------------------------


@dataclass(frozen=True, slots=True)
class _Rectangle:
    """Vier Linien, die ein achsparalleles Rechteck um den Ursprung schließen."""

    corners: tuple[tuple[int, int], ...]
    """Je Ecke die zwei Punkte: Ende der einen, Anfang der nächsten Linie."""
    horizontal: tuple[int, int]
    vertical: tuple[int, int]
    width: float
    height: float
    diagonal: tuple[int, int]
    """Zwei gegenüberliegende Ecken — ihre Mitte ist der Ursprung."""


def _sketch_spots(op_id: OpId, field: str, text: str, index: _Index) -> list[BindingSpot]:
    from app.core.sketch.serialize import sketch_from_text

    try:
        sketch = sketch_from_text(text)
    except AppError:
        return []
    spots: list[BindingSpot] = []
    for number, rectangle in enumerate(_rectangles(sketch)):
        for side, value in (("width", rectangle.width), ("height", rectangle.height)):
            choices = index.matching(value)
            if choices:
                spots.append(BindingSpot(op_id, field, value, choices, number, side))
    return spots


def _offsets(sketch: Sketch) -> list[int]:
    """Der flache Index des ersten Punkts je Element (``SketchConstraint.targets``)."""
    offsets: list[int] = []
    total = 0
    for element in sketch.elements:
        offsets.append(total)
        total += len(element.points)
    return offsets


def _rectangles(sketch: Sketch) -> list[_Rectangle]:
    """Die achsparallelen Rechtecke der Zeichnung, deren Mitte der Ursprung ist.

    Nur Linien ohne Bedingung an ihren Punkten: Wer schon gemaßt hat, hat die
    Zeichnung bestimmt, und eine zweite Bedingung derselben Art widerspräche
    ihr oder wäre doppelt.
    """
    offsets = _offsets(sketch)
    bound = {target for constraint in sketch.constraints for target in constraint.targets}
    lines = [
        position
        for position, element in enumerate(sketch.elements)
        if element.kind == "line"
        and not element.construction
        and len(element.points) == 2
        and not ({offsets[position], offsets[position] + 1} & bound)
    ]
    used: set[int] = set()
    found: list[_Rectangle] = []
    for start in lines:
        if start in used:
            continue
        loop = _loop_from(start, lines, sketch, used)
        if loop is None:
            continue
        rectangle = _as_rectangle(loop, sketch, offsets)
        if rectangle is not None:
            used.update(loop)
            found.append(rectangle)
    return found


def _same(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= MATCH and abs(a[1] - b[1]) <= MATCH


def _loop_from(
    start: int, lines: Sequence[int], sketch: Sketch, used: set[int]
) -> tuple[int, int, int, int] | None:
    """Vier Linien, die von ``start`` aus Ende an Anfang einen Ring schließen."""
    loop = [start]
    end = sketch.elements[start].points[1]
    while len(loop) < 4:
        following = next(
            (
                line
                for line in lines
                if line not in used
                and line not in loop
                and _same(sketch.elements[line].points[0], end)
            ),
            None,
        )
        if following is None:
            return None
        loop.append(following)
        end = sketch.elements[following].points[1]
    if not _same(end, sketch.elements[start].points[0]):
        return None
    return (loop[0], loop[1], loop[2], loop[3])


def _as_rectangle(
    loop: tuple[int, int, int, int], sketch: Sketch, offsets: Sequence[int]
) -> _Rectangle | None:
    horizontal: list[int] = []
    vertical: list[int] = []
    for line in loop:
        (x0, y0), (x1, y1) = sketch.elements[line].points
        if abs(y0 - y1) <= MATCH < abs(x0 - x1):
            horizontal.append(line)
        elif abs(x0 - x1) <= MATCH < abs(y0 - y1):
            vertical.append(line)
        else:
            return None
    if len(horizontal) != 2 or len(vertical) != 2:
        return None
    xs = [point[0] for line in loop for point in sketch.elements[line].points]
    ys = [point[1] for line in loop for point in sketch.elements[line].points]
    if abs(min(xs) + max(xs)) > MATCH or abs(min(ys) + max(ys)) > MATCH:
        return None
    return _Rectangle(
        corners=tuple(
            (offsets[before] + 1, offsets[after]) for before, after in pairwise((*loop, loop[0]))
        ),
        horizontal=(horizontal[0], horizontal[1]),
        vertical=(vertical[0], vertical[1]),
        width=max(xs) - min(xs),
        height=max(ys) - min(ys),
        diagonal=(offsets[loop[0]], offsets[loop[2]]),
    )


def bound_sketch(text: str, chosen: Mapping[tuple[int, str], str]) -> str:
    """Die Zeichnung mit gebundenen Rechtecken: Form, Mitte und gewählte Maße.

    Je gewähltes Rechteck: die vier Ecken gedeckt, die Seiten waagerecht und
    senkrecht, die Mitte der Diagonale auf einem festen Punkt im Ursprung —
    und Breite oder Höhe als Maß mit dem gewählten Ausdruck. Ohne gewähltes
    Maß bleibt eine Seite, wie sie ist. Der Ursprungspunkt ist Hilfsgeometrie
    und kommt hinten an, damit keine vorhandene Nummer wandert.
    """
    from app.core.sketch.serialize import sketch_from_text, sketch_to_text

    wanted = sorted({index for index, _side in chosen})
    if not wanted:
        return text
    sketch = sketch_from_text(text)
    rectangles = _rectangles(sketch)
    offsets = _offsets(sketch)
    origin = sum(len(element.points) for element in sketch.elements)
    centre = SketchElement(kind="point", points=((0.0, 0.0),), construction=True)
    added: list[SketchConstraint] = [SketchConstraint("fixed", (origin,))]
    for index in wanted:
        if index >= len(rectangles):
            continue
        rectangle = rectangles[index]
        added.extend(SketchConstraint("coincident", pair) for pair in rectangle.corners)
        added.extend(
            SketchConstraint("horizontal", (offsets[line], offsets[line] + 1))
            for line in rectangle.horizontal
        )
        added.extend(
            SketchConstraint("vertical", (offsets[line], offsets[line] + 1))
            for line in rectangle.vertical
        )
        added.append(SketchConstraint("midpoint", (origin, *rectangle.diagonal)))
        for side, lines in (("width", rectangle.horizontal), ("height", rectangle.vertical)):
            expression = chosen.get((index, side))
            if expression is not None:
                line = lines[0]
                added.append(
                    SketchConstraint("distance", (offsets[line], offsets[line] + 1), expression)
                )
    # ``replace`` statt Neubau: Die Fassung des Lösers bleibt an der Zeichnung
    # (RM-541) — gebunden ist sie nicht im Editor geändert.
    return sketch_to_text(
        replace(
            sketch,
            elements=(*sketch.elements, centre),
            constraints=(*sketch.constraints, *added),
        )
    )


def bound_params(
    document: Document, chosen: Mapping[tuple[OpId, str, int, str], str]
) -> dict[OpId, dict[str, Any]]:
    """Die neuen Werte je Schritt für die gewählten Stellen — für ``History.bind_parameters``.

    ``chosen`` ordnet dem Schlüssel einer Stelle (:attr:`BindingSpot.key`) den
    gewählten Ausdruck zu. Ein Längenfeld bekommt den Ausdruck; eine Zeichnung
    bekommt ihren neuen Text mit allen gewählten Rechtecken zugleich.
    """
    by_op = {operation.id: operation for operation in document.ops}
    result: dict[OpId, dict[str, Any]] = {}
    sketches: dict[tuple[OpId, str], dict[tuple[int, str], str]] = {}
    for (op_id, field, rectangle, side), expression in chosen.items():
        if op_id not in by_op:
            continue
        if rectangle >= 0:
            sketches.setdefault((op_id, field), {})[(rectangle, side)] = expression
        else:
            result.setdefault(op_id, {})[field] = expression
    for (op_id, field), rectangles in sketches.items():
        text = by_op[op_id].params.get(field)
        if isinstance(text, str) and text:
            result.setdefault(op_id, {})[field] = bound_sketch(text, rectangles)
    return result


__all__ = [
    "MATCH",
    "MOST_CHOICES",
    "BindingChoice",
    "BindingSpot",
    "binding_spots",
    "bound_params",
    "bound_sketch",
    "matching_expressions",
]
