"""Merkmalsbezeichner über Operationen hinweg stabil halten (Bauplan
§21.2, §21.3).

Nach jeder Operation läuft die Erkennung erneut, und die neuen Merkmale müssen
den alten zugeordnet werden — sonst ist ``hole_3`` in Schritt fünf ein anderes
Loch als ``hole_3`` in Schritt vier, und jeder Verweis im Stapel verrottet
still.

Zugeordnet wird über einen Merkmalsvektor (Art, Durchmesser, Achse, Position
**im eigenen Bezugssystem des Objekts**, Nachbarschaft) mit der ungarischen
Methode über der Kostenmatrix. Die Position wird relativ zum Körper genommen,
damit das Verschieben des ganzen Objekts nicht jedes Merkmal verwaist.

Drei Ausgänge, und nur einer davon ist still:

* ein klarer Partner unter der Schwelle — der Bezeichner bleibt;
* kein Partner — verwaist;
* mehrere gleich gute Kandidaten — **mehrdeutig**, und das hält die Kette an
  und fragt (§21.3). Hier zu raten wäre schlimmer als zu fragen.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import TYPE_CHECKING, Any

import numpy as np

from app.core.deferred import cKDTree, linear_sum_assignment
from app.core.errors import AmbiguityError, InternalError
from app.core.log import get_logger
from app.core.perceive.match_records import valid_fingerprint
from app.core.perceive.surfaces import radial_scales, transformed_patches
from app.core.types import Feature, FeatureId, Transform, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

if TYPE_CHECKING:
    from app.core.geom.mesh import MeshData

_log = get_logger(__name__)

#: Wie nah der zweitbeste Kandidat sein darf, bevor die Zuordnung als
#: mehrdeutig gilt — relativ zur besten Kostenzahl.
AMBIGUITY_MARGIN = 0.25

#: …und absolut, für den Fall, dass der beste Treffer fast nichts kostet.
#:
#: Ohne den Boden wäre bei einem Treffer mit Kosten null nur ein Rivale mit
#: exakt null mehrdeutig — zwei Kandidaten, die beide praktisch auf der Stelle
#: liegen, würden nach der letzten Nachkommastelle entschieden. Mit ihm gilt:
#: wer weniger als fünf Prozent der Annahmeschwelle vom Besten entfernt ist,
#: ist nicht zu unterscheiden.
AMBIGUITY_FLOOR = 0.05

#: Toleranzen, eine je Teil des Merkmalsvektors. Jedes Teil wird durch seine
#: eigene Toleranz geteilt — eine Kostenzahl von 1.0 heißt also „so weit
#: daneben, wie wir gerade noch annehmen", egal aus welchem Teil sie kam.
POSITION_TOLERANCE = 0.08
"""Anteil der Modelldiagonale, um den ein Merkmal gewandert sein darf."""
DIAMETER_TOLERANCE = 0.15
"""Relative Änderung des Durchmessers — eine Bohrung kann geweitet werden und
sich selbst bleiben."""
AXIS_TOLERANCE = 0.3
"""Länge der Differenz zwischen den Einheitsachsen, rund 17 Grad."""

#: Alles darunter zählt als dasselbe Merkmal.
MATCH_THRESHOLD = 1.0

#: Was ein Artunterschied kostet: mehr, als alles andere zusammen erreichen
#: kann.
KIND_PENALTY = 1e6

#: Wie viele alte Merkmale gleichzeitig gegen alle neuen gerechnet werden.
#:
#: Eine volle Matrix entsteht nur beim nicht eindeutig zertifizierten
#: Gesamtkonflikt. Koordinaten je Paar und Baumabfragen bleiben auch dort
#: blockweise begrenzt; der Abbruch wird zwischen diesen Blöcken geprüft.
VECTOR_ROWS = 256


@dataclass(slots=True)
class MatchResult:
    """Wer wer geworden ist, und was sich nicht entscheiden ließ."""

    mapping: dict[FeatureId, FeatureId] = field(default_factory=dict)
    """Alte Kennung auf neue Kennung."""
    orphaned: tuple[FeatureId, ...] = ()
    """Alte Merkmale ohne Partner (§21.2)."""
    ambiguous: dict[FeatureId, tuple[FeatureId, ...]] = field(default_factory=dict)
    """Offene alte Identitäten; mehrere alte Ansprüche dürfen um nur ein Ziel konkurrieren."""
    fresh: tuple[FeatureId, ...] = ()
    """Neue Merkmale ohne freigegebenen alten Namen, einschließlich offener Kandidaten."""

    @property
    def settled(self) -> bool:
        """True, wenn nichts eine Entscheidung des Nutzers braucht."""
        return not self.ambiguous and not self.orphaned


def feature_vector(feature: Feature, centre: Vec3, diagonal: float) -> np.ndarray:
    """Position relativ zum Körper, plus was das Merkmal ist."""
    params = feature.params
    position = np.asarray(params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
    relative = (position - np.asarray(centre, dtype=float)) / max(diagonal, EPS_GEOM)
    axis = np.asarray(params.get("axis", params.get("normal", (0.0, 0.0, 0.0))), dtype=float)
    diameter = float(params.get("diameter", params.get("area", 0.0)))
    return np.concatenate([relative, axis, [diameter]])


def cost(
    first: Feature,
    second: Feature,
    first_centre: Vec3,
    second_centre: Vec3,
    diagonal: float,
) -> float:
    """Was es kostete, diese zwei dasselbe Merkmal zu nennen.

    Jeder Körper wird in seinem eigenen Bezugssystem gemessen — das Verschieben
    des ganzen Objekts lässt also jede Kostenzahl unberührt; sonst verwaiste
    eine Verschiebung alles.
    """
    if first.kind != second.kind:
        return KIND_PENALTY

    one = feature_vector(first, first_centre, diagonal)
    two = feature_vector(second, second_centre, diagonal)

    return float(_vector_costs(one, two, "axis" in first.params))


def _vector_norm(values: np.ndarray) -> np.ndarray:
    """Skalar- und Batchreduktion des bisherigen Kostenwegs jeweils erhalten."""
    return np.asarray(
        np.linalg.norm(values) if values.ndim == 1 else np.linalg.norm(values, axis=-1)
    )


def _vector_costs(one: np.ndarray, two: np.ndarray, signless: np.ndarray | bool) -> np.ndarray:
    """Eine Kostenformel für Einzelpaar, Matrix, Vorauswahl und gespeicherte Antwort."""
    position = _vector_norm(one[..., :3] - two[..., :3]) / POSITION_TOLERANCE
    # Eine Bohrungs- oder Stiftachse ist eine Linie, keine Richtung: die
    # Erkennung liefert sie nach einer Drehung mal als +v, mal als -v, und
    # beides ist dasselbe Merkmal. Eine Flächennormale trägt ihr Vorzeichen
    # dagegen zu Recht — innen ist nicht außen. Unterschieden am Parameter,
    # nicht an einer Artenliste: was eine ``axis`` hat, ist richtungslos.
    delta = _vector_norm(one[..., 3:6] - two[..., 3:6])
    if np.any(signless):
        opposite = _vector_norm(one[..., 3:6] + two[..., 3:6])
        delta = np.where(signless, np.minimum(delta, opposite), delta)
    axis = delta / AXIS_TOLERANCE
    scale = np.maximum(np.maximum(np.abs(one[..., 6]), np.abs(two[..., 6])), EPS_GEOM)
    diameter = np.abs(one[..., 6] - two[..., 6]) / scale / DIAMETER_TOLERANCE
    return np.asarray(position + axis + diameter)


def _vectors(
    features: list[Feature], centre: Vec3, diagonal: float, check: Callable[[], None] | None
) -> np.ndarray:
    """Originale Bezugsrechnung blockweise aufbereiten, ohne eigene Zentrierungsformel."""
    vectors = np.empty((len(features), 7), dtype=float)
    for start in range(0, len(features), VECTOR_ROWS):
        if check is not None:
            check()
        stop = min(start + VECTOR_ROWS, len(features))
        vectors[start:stop] = [
            feature_vector(entry, centre, diagonal) for entry in features[start:stop]
        ]
    return vectors


def _cost_matrix(
    first: list[Feature],
    second: list[Feature],
    first_centre: Vec3,
    second_centre: Vec3,
    diagonal: float,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> np.ndarray:
    """Vollständige Referenzmatrix mit derselben Formel wie selektive Paare."""
    first_vectors = _vectors(first, first_centre, diagonal, check_cancelled)
    second_vectors = _vectors(second, second_centre, diagonal, check_cancelled)
    second_kinds = np.asarray([feature.kind for feature in second], dtype=object)
    matrix = np.empty((len(first), len(second)), dtype=float)

    for start in range(0, len(first), VECTOR_ROWS):
        if check_cancelled is not None:
            check_cancelled()
        stop = min(start + VECTOR_ROWS, len(first))
        one = first_vectors[start:stop]
        signless = np.fromiter(
            ("axis" in feature.params for feature in first[start:stop]),
            dtype=bool,
            count=stop - start,
        )
        block = _vector_costs(one[:, None, :], second_vectors[None, :, :], signless[:, None])
        first_kinds = np.asarray([feature.kind for feature in first[start:stop]], dtype=object)
        block[first_kinds[:, None] != second_kinds[None, :]] = KIND_PENALTY
        matrix[start:stop] = block

    return matrix


def _query_radius() -> float:
    """Nur Rundungsreserve für den Raumfilter, keine zusätzliche Annahmetoleranz.

    Bei u=eps/2 umfasst R/(1-u)^5 die Rundungen von Norm, Division und
    Koordinatendifferenz. Die Baumabfrage verwendet die Maximumsnorm und
    exakt dieselben gerundeten Positionen wie die Kostenformel. Nahe der
    festen Grenze R=0,08 sind Quadrat und Wurzel normal darstellbar.
    """
    unit = Fraction(float(np.finfo(float).eps)) / 2
    radius = Fraction(POSITION_TOLERANCE) * Fraction(MATCH_THRESHOLD) / (1 - unit) ** 5
    rounded = float(radius)
    return float(np.nextafter(rounded, np.inf)) if Fraction(rounded) < radius else rounded


def _candidate_costs(
    first: list[Feature],
    second: list[Feature],
    one: np.ndarray,
    two: np.ndarray,
    tree: Any,
    radius: float,
    check: Callable[[], None] | None,
) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
    """Alle räumlich möglichen Paare ohne Nachbarlimit; Kosten nur in kleinen Blöcken."""
    kinds = np.asarray([entry.kind for entry in second], dtype=object)
    for start in range(0, len(first), VECTOR_ROWS):
        if check is not None:
            check()
        neighbours = tree.query_ball_point(
            one[start : start + VECTOR_ROWS, :3], radius, p=np.inf, return_sorted=True
        )
        if check is not None:
            check()
        for offset, nearby in enumerate(neighbours):
            row = start + offset
            indices = np.asarray(nearby, dtype=np.intp)
            indices = indices[kinds[indices] == first[row].kind]
            for block in range(0, len(indices), VECTOR_ROWS):
                if check is not None:
                    check()
                columns = indices[block : block + VECTOR_ROWS]
                values = _vector_costs(one[row], two[columns], "axis" in first[row].params)
                accepted = values <= MATCH_THRESHOLD
                yield row, columns[accepted], values[accepted]


@dataclass(slots=True)
class _Assignment:
    """Vollständige Solverantwort und wiederholbarer Zugang zu ihren Originalkosten."""

    rows: np.ndarray
    columns: np.ndarray
    values: np.ndarray
    matrix: np.ndarray | None
    pairs: Callable[[], Iterator[tuple[int, np.ndarray, np.ndarray]]]


def _matrix_pairs(
    matrix: np.ndarray, check: Callable[[], None] | None
) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
    """Bereits gerechnete angenommene Paare in denselben begrenzten Blöcken lesen."""
    for row, values in enumerate(matrix):
        if check is not None:
            check()
        indices = np.flatnonzero(values <= MATCH_THRESHOLD)
        for start in range(0, len(indices), VECTOR_ROWS):
            if check is not None:
                check()
            columns = indices[start : start + VECTOR_ROWS]
            yield row, columns, values[columns]


def _not_finite(features: list[Feature], vectors: np.ndarray) -> list[str]:
    """Die Kennungen der Merkmale, deren Vektor keine endliche Zahl trägt."""
    finite = np.all(np.isfinite(vectors), axis=1) if len(vectors) else np.ones(0, dtype=bool)
    return [str(feature.id) for feature, good in zip(features, finite, strict=True) if not good]


def _assignment(
    first: list[Feature],
    second: list[Feature],
    before: Vec3,
    centre: Vec3,
    diagonal: float,
    check: Callable[[], None] | None,
) -> _Assignment:
    """Strikte freie Zeilenminima zertifizieren; sonst den ganzen Solverkontext erhalten."""
    one, two = _vectors(first, before, diagonal, check), _vectors(second, centre, diagonal, check)
    broken = _not_finite(first, one) + _not_finite(second, two)
    if broken:
        # **Ein Merkmal ohne Zahl ist ein Programmfehler, kein Bedienfehler.**
        # Bis zum 21.09.2026 lief der Fall in den Vollvergleich, und scipy
        # warf dort „matrix contains invalid numeric entries" — ein Satz
        # ohne Handlung (Regel 17). Jetzt nennt die Ausnahme das Merkmal und
        # trägt den Fehlerbericht als Vorschlag.
        raise InternalError(
            detail="feature vectors contain non-finite values",
            values={"features": broken[:8], "count": len(broken)},
        )
    if check is not None:
        check()
    tree = cKDTree(two[:, :3])
    radius = _query_radius()
    smaller = min(len(first), len(second))
    transposed = len(first) > len(second)
    minima = np.full(smaller, np.inf)
    runners = np.full(smaller, np.inf)
    partners = np.full(smaller, -1, dtype=np.intp)
    for row, columns, values in _candidate_costs(first, second, one, two, tree, radius, check):
        if not len(columns):
            continue
        if transposed:
            improve = values < minima[columns]
            runners[columns] = np.minimum(
                runners[columns], np.where(improve, minima[columns], values)
            )
            minima[columns] = np.minimum(minima[columns], values)
            partners[columns[improve]] = row
        else:
            best = int(np.argmin(values))
            value, column = float(values[best]), int(columns[best])
            other = np.min(np.delete(values, best), initial=np.inf)
            if value < minima[row]:
                runners[row] = min(runners[row], minima[row], other)
                minima[row], partners[row] = value, column
            else:
                runners[row] = min(runners[row], value)
    certified = (
        np.all(minima <= MATCH_THRESHOLD)
        and np.all(runners > minima)
        and len(np.unique(partners)) == smaller
    )
    if certified:
        # Der globale Solver findet auf seiner kleineren Seite jedes strikte
        # Minimum sofort auf einer freien Spalte. Kein Alternierungspfad und
        # keine Strafkostenarithmetik können eine andere Paarung erzeugen.
        rows = partners if transposed else np.arange(smaller)
        columns = np.arange(smaller) if transposed else partners
        order = np.argsort(rows)
        rows, columns = rows[order], columns[order]
        return _Assignment(
            rows,
            columns,
            minima[columns if transposed else rows],
            None,
            lambda: _candidate_costs(first, second, one, two, tree, radius, check),
        )
    if check is not None:
        check()
    # Abgelehnte Paare kosten überall dieselbe Strafe. Sonst könnte der
    # Summenoptimierer ein annehmbares Paar zugunsten zweier billigerer,
    # aber beide abgelehnter Paare opfern. Der vollständige globale Kontext
    # bleibt auch bei räumlich getrennten Konkurrenzgruppen erhalten.
    matrix = np.full((len(first), len(second)), KIND_PENALTY, dtype=float)
    for row, columns, values in _candidate_costs(first, second, one, two, tree, radius, check):
        matrix[row, columns] = values
    if check is not None:
        check()
    rows, columns = linear_sum_assignment(matrix)
    if check is not None:
        check()
    return _Assignment(
        rows, columns, matrix[rows, columns], matrix, lambda: _matrix_pairs(matrix, check)
    )


def _hull_limits(
    matrix: np.ndarray, assignment: _Assignment, check: Callable[[], None] | None
) -> np.ndarray:
    """Notwendige Kostenhülle aus exakten binären U-L-Summen, ohne Strafsummenverlust.

    Jede vollständige Zuteilung nimmt genau eine Kante der kleineren Seite.
    Mit deren Minima m und L=sum(m) kann C[r,j] nur dann zu einem Optimum
    gehören, wenn C[r,j] <= m[r] + U - L. U enthält auch alle Strafpaare.
    Die Zeilengrenze wird abgerundet: Der Floatvergleich entscheidet danach
    exakt dieselbe Menge wie der rationale Vergleich, ohne Fraction je Paar.
    """
    oriented = matrix.T if matrix.shape[0] > matrix.shape[1] else matrix
    minima = np.empty(len(oriented))
    for start in range(0, len(oriented), VECTOR_ROWS):
        if check is not None:
            check()
        minima[start : start + VECTOR_ROWS] = np.min(oriented[start : start + VECTOR_ROWS], axis=1)
    gap = Fraction(0)
    for index, (selected, minimum) in enumerate(zip(assignment.values, minima, strict=True)):
        if check is not None and index % VECTOR_ROWS == 0:
            check()
        gap += Fraction(float(selected)) - Fraction(float(minimum))
    limits = np.empty(len(minima))
    for index, minimum in enumerate(minima):
        if check is not None and index % VECTOR_ROWS == 0:
            check()
        exact = Fraction(float(minimum)) + gap
        rounded = float(exact)
        if Fraction(rounded) > exact:
            rounded = float(np.nextafter(rounded, -np.inf))
        limits[index] = rounded
    return limits


def _reachable(
    graph: list[list[int]], starts: list[int], check: Callable[[], None] | None
) -> np.ndarray:
    """Gerichtete Reichweite ohne Rekursion; auch lange Kantenlisten sind abbrechbar."""
    reached = np.zeros(len(graph), dtype=bool)
    pending = list(starts)
    reached[starts] = True
    while pending:
        node = pending.pop()
        for start in range(0, len(graph[node]), VECTOR_ROWS):
            if check is not None:
                check()
            for neighbour in graph[node][start : start + VECTOR_ROWS]:
                if not reached[neighbour]:
                    reached[neighbour] = True
                    pending.append(neighbour)
    if check is not None:
        check()
    return reached


def _strong_components(
    graph: list[list[int]], reverse: list[list[int]], check: Callable[[], None] | None
) -> np.ndarray:
    """Kosaraju mit ausdrücklichem Stapel statt Rekursion über Merkmalsketten."""
    visited: set[int] = set()
    order: list[int] = []
    steps = 0
    for root in range(len(graph)):
        if check is not None:
            check()
        if root in visited:
            continue
        visited.add(root)
        pending = [(root, iter(graph[root]))]
        while pending:
            steps += 1
            if check is not None and steps % VECTOR_ROWS == 0:
                check()
            node, edges = pending[-1]
            neighbour = next(edges, None)
            if neighbour is None:
                order.append(node)
                pending.pop()
            elif neighbour not in visited:
                visited.add(neighbour)
                pending.append((neighbour, iter(graph[neighbour])))
    labels = np.full(len(graph), -1, dtype=np.intp)
    for root in reversed(order):
        if check is not None:
            check()
        if labels[root] >= 0:
            continue
        labels[root] = root
        stack = [root]
        while stack:
            node = stack.pop()
            for start in range(0, len(reverse[node]), VECTOR_ROWS):
                if check is not None:
                    check()
                for neighbour in reverse[node][start : start + VECTOR_ROWS]:
                    if labels[neighbour] < 0:
                        labels[neighbour] = root
                        stack.append(neighbour)
    return labels


def _global_support(
    assignment: _Assignment, partners: np.ndarray, new_count: int, check: Callable[[], None] | None
) -> list[list[int]]:
    """Globale Wechselmöglichkeiten durch Hülle, Maximalität und alternierende Wege begrenzen."""
    support = [[int(partner)] if partner >= 0 else [] for partner in partners]
    matrix = assignment.matrix
    if matrix is None:
        # Alle strikten freien Minima zusammen beweisen das eindeutige Optimum.
        return support
    limits = _hull_limits(matrix, assignment, check)
    old_count = len(partners)
    transposed = old_count > new_count
    hull: list[list[int]] = [[] for _ in partners]
    graph: list[list[int]] = [[] for _ in range(old_count + new_count)]
    reverse: list[list[int]] = [[] for _ in graph]
    for row, columns, values in assignment.pairs():
        kept = columns[values <= (limits[columns] if transposed else limits[row])]
        hull[row].extend(int(column) for column in kept)
        for column in kept:
            before, after = row, old_count + int(column)
            if partners[row] == column:
                before, after = after, before
            graph[before].append(after)
            reverse[after].append(before)
    free_old = [index for index, partner in enumerate(partners) if partner < 0]
    taken = {int(partner) for partner in partners if partner >= 0}
    free_new = [old_count + column for column in range(new_count) if column not in taken]
    forward = _reachable(graph, free_old, check)
    if np.any(forward[free_new]):
        raise AmbiguityError(
            _("Die Merkmalszuordnung ist widersprüchlich. Bitte die Zuordnung erneut prüfen.")
        )
    backward = _reachable(reverse, free_new, check)
    labels = _strong_components(graph, reverse, check)
    for row, neighbours in enumerate(hull):
        for start in range(0, len(neighbours), VECTOR_ROWS):
            if check is not None:
                check()
            for column in neighbours[start : start + VECTOR_ROWS]:
                node = old_count + column
                if column != partners[row] and (
                    labels[row] == labels[node]
                    or (forward[row] and forward[node])
                    or (backward[row] and backward[node])
                ):
                    support[row].append(column)
    return support


def _open_claims(
    assignment: _Assignment, old_count: int, new_count: int, check: Callable[[], None] | None
) -> tuple[np.ndarray, dict[int, list[int]]]:
    """Feste A-Referenzen mit Zeilenrivalen R und aktivierten Besitzeransprüchen Q schließen."""
    partners = np.full(old_count, -1, dtype=np.intp)
    accepted = assignment.values <= MATCH_THRESHOLD
    partners[assignment.rows[accepted]] = assignment.columns[accepted]
    support = _global_support(assignment, partners, new_count, check)
    old_upper = np.full(old_count, -np.inf)
    new_upper = np.full(new_count, -np.inf)
    owners: list[list[int]] = [[] for _ in range(new_count)]
    for row, targets in enumerate(support):
        if check is not None:
            check()
        for start in range(0, len(targets), VECTOR_ROWS):
            if check is not None:
                check()
            for column in targets[start : start + VECTOR_ROWS]:
                owners[column].append(row)
        if targets and assignment.matrix is not None:
            values = assignment.matrix[row, targets]
            old_upper[row] = np.max(values)
            np.maximum.at(new_upper, targets, values)
    if assignment.matrix is None:
        old_upper[assignment.rows] = assignment.values
        new_upper[assignment.columns] = assignment.values
    row_limits = old_upper * (1.0 + AMBIGUITY_MARGIN) + AMBIGUITY_FLOOR
    column_limits = new_upper * (1.0 + AMBIGUITY_MARGIN) + AMBIGUITY_FLOOR
    row_claims: list[list[int]] = [[] for _ in partners]
    extra_claims: list[list[int]] = [[] for _ in partners]
    for row, columns, values in assignment.pairs():
        row_claims[row].extend(int(column) for column in columns[values <= row_limits[row]])
        extra_claims[row].extend(
            int(column) for column in columns[values <= column_limits[columns]]
        )
    return partners, _close_claims(partners, support, owners, row_claims, extra_claims, check)


def _close_claims(
    partners: np.ndarray,
    support: list[list[int]],
    owners: list[list[int]],
    row_claims: list[list[int]],
    extra_claims: list[list[int]],
    check: Callable[[], None] | None,
) -> dict[int, list[int]]:
    """Alle geöffneten Besitzer vollständig nachführen, ohne ihre Referenzkosten zu ändern."""
    pending: list[int] = []
    for row in range(len(partners)):
        if check is not None:
            check()
        if (
            len(support[row]) > 1
            or any(len(owners[column]) > 1 for column in support[row])
            or any(column != partners[row] for column in row_claims[row])
            or (partners[row] < 0 and extra_claims[row])
        ):
            pending.append(row)
    opened = set(pending)
    claims: dict[int, list[int]] = {}
    while pending:
        if check is not None:
            check()
        row = pending.pop()
        columns = sorted(set(support[row]) | set(row_claims[row]) | set(extra_claims[row]))
        claims[row] = columns
        for start in range(0, len(columns), VECTOR_ROWS):
            if check is not None:
                check()
            for column in columns[start : start + VECTOR_ROWS]:
                for offset in range(0, len(owners[column]), VECTOR_ROWS):
                    if check is not None:
                        check()
                    for owner in owners[column][offset : offset + VECTOR_ROWS]:
                        if owner not in opened:
                            opened.add(owner)
                            pending.append(owner)
    return claims


def match(
    old: dict[FeatureId, Feature],
    new: dict[FeatureId, Feature],
    centre: Vec3,
    diagonal: float,
    old_centre: Vec3 | None = None,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> MatchResult:
    """Ordnet neue Merkmale alten Bezeichnern zu und sagt, was offen blieb.

    ``centre`` ist das Bezugssystem des neuen Körpers, ``old_centre`` das, in
    dem die alten Merkmale gemessen wurden — per Vorgabe dasselbe.
    """
    if check_cancelled is not None:
        check_cancelled()
    if not old:
        return MatchResult(fresh=tuple(new))
    if not new:
        return MatchResult(orphaned=tuple(old))

    before = old_centre if old_centre is not None else centre
    old_ids = list(old)
    new_ids = list(new)
    assignment = _assignment(
        [old[identifier] for identifier in old_ids],
        [new[identifier] for identifier in new_ids],
        before,
        centre,
        diagonal,
        check_cancelled,
    )
    partners, claims = _open_claims(assignment, len(old_ids), len(new_ids), check_cancelled)
    result = MatchResult()
    taken: set[str] = set()
    for row, old_id in enumerate(old_ids):
        if check_cancelled is not None:
            check_cancelled()
        column = int(partners[row])
        if row in claims:
            candidates = claims[row]
            # Die bisherige Anzeigeordnung bleibt: vorgeschlagener Partner
            # zuerst. Diese Reihenfolge ist keine bestätigte Entscheidung.
            ordered = ([column] if column in candidates else []) + [
                other for other in candidates if other != column
            ]
            result.ambiguous[old_id] = tuple(new_ids[other] for other in ordered)
        elif column >= 0:
            result.mapping[old_id] = new_ids[column]
            taken.add(new_ids[column])
    rejected = [
        old_ids[int(row)]
        for row, value in zip(assignment.rows, assignment.values, strict=True)
        if value > MATCH_THRESHOLD and int(row) not in claims
    ]
    # Nicht zugeteilte alte Zeilen vor den ausdrücklich abgewiesenen Paaren,
    # wie im ursprünglichen vollständigen Solverweg.
    result.orphaned = tuple(
        identifier
        for identifier in old_ids
        if identifier not in result.mapping
        and identifier not in result.ambiguous
        and identifier not in rejected
    ) + tuple(rejected)
    result.fresh = tuple(identifier for identifier in new_ids if identifier not in taken)

    if check_cancelled is not None:
        check_cancelled()
    if result.ambiguous:
        _log.info("feature matching left %d ambiguous", len(result.ambiguous))
    return result


def require_injective(mapping: Mapping[str, str]) -> None:
    """Verhindert doppelte Nachfolger vor jeder Namen- und Erzeugerübernahme."""
    if len(set(mapping.values())) != len(mapping):
        raise AmbiguityError(
            _(
                "Mehrere bisherige Merkmale wurden demselben aktuellen Merkmal zugeordnet. "
                "Bitte die Zuordnung erneut wählen."
            )
        )


def inherit_originators(
    new: Mapping[FeatureId, Feature],
    result: MatchResult,
    previous: Mapping[FeatureId, Feature],
) -> dict[FeatureId, Feature]:
    """Übernimmt belegte Erzeuger, ohne native Kennungen oder neue Formdaten umzubenennen.

    Dieselbe Übernahme gilt für ``apply_mapping`` am Netz und für native
    Flächen, deren Topologiekennungen erhalten bleiben müssen. Ein gleicher
    Name oder eine mehrdeutige Zuordnung beweist keinen Vorfahren.
    """
    require_injective(result.mapping)
    inherited = dict(new)
    for old, name in result.mapping.items():
        feature, ancestor = inherited.get(name), previous.get(old)
        if feature is not None and ancestor is not None and feature.created_by is None:
            inherited[name] = replace(feature, created_by=ancestor.created_by)
    return inherited


def apply_mapping(
    new: dict[FeatureId, Feature],
    result: MatchResult,
    *,
    previous: Mapping[FeatureId, Feature] | None = None,
) -> dict[FeatureId, Feature]:
    """Benennt die neuen Merkmale auf die alten Bezeichner um, die überlebt
    haben.

    Ein Merkmal ohne Partner behält seinen Namen nur, wenn der frei ist.
    Sortiert sich eine neue Bohrung in der Erkennung vor die bestehenden,
    rutschen deren Nummern — und der Name des neuen Merkmals ist zugleich der
    vergebene Name eines Überlebenden. Ohne Ausweichen überschrieb hier eines
    das andere und verschwand wortlos aus der Szene: ``drill_hole`` bohrte
    ein Loch, das nie ein Merkmal wurde. Verwaiste Namen bleiben ebenfalls
    gesperrt — eine ID, die eben noch etwas anderes hieß, sofort neu zu
    vergeben, ließe Passungen und Ops auf das falsche Merkmal zeigen.

    ``previous`` liegt bereits im neuen Bezugsrahmen. Bei Bohrung, Zapfen,
    Verrundung, Langloch und Gewinde gibt seine Achse das Vorzeichen der neuen
    Messachse vor; die gemessene Achslage bleibt erhalten. Kegel und
    Flächennormalen sind geometrisch gerichtet. Der Torus trägt die Normale
    seiner Symmetrieebene, keine Längsrichtung, und behält sie ebenfalls.
    """
    require_injective(result.mapping)
    renamed: dict[FeatureId, Feature] = {}
    reverse = {value: key for key, value in result.mapping.items()}
    # Auch die mehrdeutigen alten Namen bleiben gesperrt: wer eine
    # Mehrdeutigkeit mit „Verwerfen" beantwortet, hat den Namen aufgegeben —
    # ihn sofort neu zu vergeben ließe eine Passung auf das falsche Merkmal
    # zeigen. Aufgelöste stehen ohnehin schon im mapping, der Zusatz ist
    # dann folgenlos.
    taken: set[FeatureId] = set(result.mapping) | set(result.orphaned) | set(result.ambiguous)
    inherited = inherit_originators(new, result, previous) if previous is not None else new
    for identifier, feature in inherited.items():
        target = reverse.get(identifier)
        if (
            target is not None
            and previous is not None
            and feature.kind in {"hole", "pin", "fillet", "slot", "thread"}
        ):
            reference = previous.get(target)
            if reference is not None and "axis" in reference.params and "axis" in feature.params:
                axis = np.asarray(feature.params["axis"], dtype=float)
                if float(axis @ np.asarray(reference.params["axis"], dtype=float)) < 0.0:
                    feature = replace(
                        feature,
                        params={**feature.params, "axis": tuple(float(value) for value in -axis)},
                    )
        if target is None:
            target = identifier if identifier not in taken else _fresh_id(identifier, taken)
        taken.add(target)
        # **``replace`` und nicht ein frisches Feature** — dieselbe Falle wie in
        # ``moved_features`` weiter unten, und dort steht seit dem 23.08.2026,
        # was sie kostet: Der Aufbau von Hand nannte fünf der sieben Felder,
        # und die zwei fehlenden fielen still weg. Hier waren es dieselben
        # zwei, nur fiel es nicht auf: ``created_by`` trug bei einem erkannten
        # Merkmal ohnehin nichts, und ``recognised`` steht für sie auf der
        # Vorgabe.
        #
        # Seit erkannte Merkmale ihren Erzeuger bekommen können (§21.2, das
        # Tor in ``scene.evaluate._with_features``), trägt es: Gemessen gingen
        # sechs Merkmale mit ``created_by`` hinein und null kamen heraus. Ein
        # Feld, das später dazukommt, reist jetzt auch hier von selbst mit.
        renamed[target] = replace(feature, id=target)
    return renamed


def _fresh_id(identifier: FeatureId, taken: set[FeatureId]) -> FeatureId:
    """Der nächste freie Name derselben Art: ``hole_5``, wenn bis ``hole_4``
    alles vergeben ist. Ein Name ohne Endziffer bekommt ein Trennzeichen —
    aus ``face_top`` wird ``face_top_1``, nicht ``face_top1``."""
    stem = identifier.rstrip("0123456789")
    if not stem.endswith("_"):
        stem = f"{stem}_"
    number = 1
    while f"{stem}{number}" in taken:
        number += 1
    return f"{stem}{number}"


def question_for(old_id: FeatureId, candidates: tuple[FeatureId, ...]) -> tuple[str, list[str]]:
    """Die Frage, die der Kern stellt, wenn sich ein Merkmal nicht
    unterscheiden lässt (§21.3).
    """
    from app.i18n import tr

    return (
        tr("Welches Merkmal entspricht {name}?").replace("{name}", old_id),
        [*candidates, tr("Verwerfen")],
    )


def fingerprint(feature: Feature, centre: Vec3, diagonal: float) -> dict[str, Any]:
    """Der Abdruck, unter dem eine Zuordnungsantwort festgehalten wird (§15.7).

    **Gespeichert wird, woran man das Merkmal wiedererkennt — nicht sein
    Name.** Ein ``alt → neu`` wäre fragil: Die Erkennung nummeriert beim
    nächsten Lauf womöglich anders, und dann zeigte die Antwort auf ein fremdes
    Merkmal. Aus „fragt zu oft" würde „nimmt stillschweigend das falsche", und
    das ist der schlechtere Fehler (Regel 21).

    **Relativ zum Körper, nicht absolut.** Es ist derselbe Bezugsrahmen, in dem
    :func:`cost` rechnet, und genau das ist der Punkt: Verschiebt eine spätere
    Operation das ganze Objekt, wandert der Abdruck mit und bleibt gültig. Ein
    absoluter Punkt verlöre seine Gültigkeit beim ersten *Auf dem Bett
    anordnen*. Der Preis ist bekannt und tragbar: Baut eine Operation Material
    an und verschiebt damit Mitte und Diagonale, altert der Abdruck — dann
    gewinnt kein Kandidat mit Abstand, und es wird wieder gefragt. Das ist der
    gutartige Ausgang.

    Lesbares JSON, weil es in der Projektdatei steht und dort jemand
    hineinsehen können soll.
    """
    vector = feature_vector(feature, centre, diagonal)
    return {
        "kind": feature.kind,
        "relative": [round(float(value), 6) for value in vector[:3]],
        "axis": [round(float(value), 6) for value in vector[3:6]],
        "diameter": round(float(vector[6]), 6),
        "directional": "axis" not in feature.params,
    }


def resolve(
    saved: Mapping[str, Any],
    candidates: tuple[FeatureId, ...],
    detected: Mapping[FeatureId, Feature],
    centre: Vec3,
    diagonal: float,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> FeatureId | None:
    """Welcher Kandidat der gespeicherten Antwort entspricht — oder ``None``.

    ``None`` heißt „frag wieder", und das ist die wichtige Hälfte dieser
    Funktion. **Der Rückfall braucht einen Abstand, nicht „am nächsten".** Die
    Kandidaten waren mehrdeutig, *weil* sie sich gleichen; wer hier „der
    nächstliegende gewinnt" nimmt, entscheidet über einen Abstand, der kleiner
    ist als der zwischen den Kandidaten — und rät damit genau dort, wo §21.3
    das Fragen verlangt.

    Genommen wird deshalb dieselbe Rivalenlogik wie in :func:`match`: Der Beste
    muss unter der Annahmeschwelle liegen **und** die anderen müssen deutlich
    schlechter sein. Sonst ``None``. Ein nicht vergleichbarer gleichartiger
    Kandidat sperrt die gesamte Wiedererkennung; er ist kein schlechter Rivale.
    """
    if check_cancelled is not None:
        check_cancelled()
    if not valid_fingerprint(saved, legacy=True):
        return None
    try:
        frame = np.asarray(centre, dtype=float)
        if frame.shape != (3,) or not np.isfinite(frame).all() or not np.isfinite(diagonal):
            return None
    except TypeError, ValueError, OverflowError:
        return None
    kind = saved.get("kind")
    reference = np.concatenate(
        [
            np.asarray(saved.get("relative", (0.0, 0.0, 0.0)), dtype=float),
            np.asarray(saved.get("axis", (0.0, 0.0, 0.0)), dtype=float),
            [float(saved.get("diameter", 0.0))],
        ]
    )
    directional = bool(saved.get("directional", False))

    costs: list[tuple[float, FeatureId]] = []
    for identifier in candidates:
        if check_cancelled is not None:
            check_cancelled()
        feature = detected.get(identifier)
        if feature is None or feature.kind != kind:
            continue
        try:
            # Die gemeinsame Vektorrechnung bewahrt historische Vorgaben für
            # optionale Richtungen/Maße. Eine fehlende aktuelle Lage darf aber
            # weder zum Ursprung werden noch durch Broadcasting passend wirken.
            params = feature.params
            if np.shape(params.get("centre", ())) != (3,) or np.shape(
                params.get("axis", params.get("normal", (0.0, 0.0, 0.0)))
            ) != (3,):
                return None
            with np.errstate(over="ignore", invalid="ignore"):
                vector = feature_vector(feature, centre, diagonal)
                value = float(_vector_costs(reference, vector, not directional))
        except TypeError, ValueError, OverflowError:
            return None
        if check_cancelled is not None:
            check_cancelled()
        if not np.isfinite(vector).all() or not np.isfinite(value):
            return None
        costs.append((value, identifier))

    if check_cancelled is not None:
        check_cancelled()
    if not costs:
        return None
    costs.sort()
    if check_cancelled is not None:
        check_cancelled()
    best, winner = costs[0]
    if best > MATCH_THRESHOLD:
        return None
    limit = best * (1.0 + AMBIGUITY_MARGIN) + AMBIGUITY_FLOOR
    ambiguous = any(value <= limit for value, identifier in costs[1:])
    if check_cancelled is not None:
        check_cancelled()
    return None if ambiguous else winner


def moved_features(
    features: dict[FeatureId, Feature],
    transform: Transform,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Führt Orte und Richtungen mit (§21.2), bei Spiegelung auch die Händigkeit.

    Formmaße bleiben hier unverändert. Für einen Maßstab oder eine Scherung
    liefert ``transformed_features`` zusätzlich die Maßänderung und deren
    Gültigkeit. Normalen folgen auch dort der invers-transponierten Matrix,
    Richtungen der gewöhnlichen linearen Abbildung.
    """
    if check_cancelled is not None:
        check_cancelled()
    matrix = np.asarray(transform, dtype=float)
    turn = matrix[:3, :3]
    # Normalen folgen der invers-transponierten Matrix — einmal gerechnet,
    # nicht ein Gleichungssystem je Merkmal (531 Verrundungen am Hemmungsrad).
    for_normals = np.linalg.inv(turn).T
    moved: dict[FeatureId, Feature] = {}
    for identifier, feature in features.items():
        if check_cancelled is not None:
            check_cancelled()
        params = dict(feature.params)
        for key in ("centre", "position", "arc_centre", "mouth_centre", "anchor"):
            if key in params:
                point = np.asarray(params[key], dtype=float)
                carried = matrix @ np.array([*point, 1.0])
                params[key] = (float(carried[0]), float(carried[1]), float(carried[2]))
        for key in (
            "axis",
            "normal",
            "direction",
            "opening_normal",
            "profile_clamp_y",
            "carrier_axis",
        ):
            if key in params:
                original = np.asarray(params[key], dtype=float)
                direction = (
                    for_normals @ original
                    if key in {"normal", "opening_normal"}
                    else turn @ original
                )
                length = float(np.linalg.norm(direction))
                if length > EPS_GEOM:
                    direction = direction / length
                params[key] = (float(direction[0]), float(direction[1]), float(direction[2]))
        if feature.kind == "thread" and float(np.linalg.det(turn)) < 0.0:
            handedness = params.get("handedness")
            if handedness in {"right", "left"}:
                params["handedness"] = "left" if handedness == "right" else "right"
        # replace und nicht ein frisches Feature: Der Aufbau von Hand
        # nannte fünf der sieben Felder, und die zwei fehlenden fielen bei
        # jedem Verschieben still weg. created_by ist der Eintrag „diesen
        # Schritt ändern" (§21.2) — nach einer Drehung war er weg. Und
        # recognised=False" wurde zu True", also maß die Zuordnung beim
        # nächsten Schritt die Bohrungen eines Bausteins an einer Erkennung,
        # die sie nie findet, und ließ sie verwaisen. Ein Feld, das später
        # dazukommt, reist jetzt von selbst mit.
        moved[identifier] = replace(
            feature,
            params=params,
            surface_patches=transformed_patches(
                feature.surface_patches, transform, check_cancelled=check_cancelled
            ),
        )
    return moved


@dataclass(frozen=True, slots=True)
class FeatureTransform:
    """Suchkandidaten und die Teilmenge mit weiterhin gültigen Formmaßen."""

    candidates: dict[FeatureId, Feature]
    exact: frozenset[FeatureId]


def transformed_features(
    features: Mapping[FeatureId, Feature],
    transform: Transform,
    *,
    mesh: MeshData | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> FeatureTransform:
    """Maße einmal für globale und örtliche Zuordnung nachführen.

    Eine affine Abbildung erhält nicht jede Formart: Ein elliptisch verzerrtes
    Loch bleibt Suchkandidat, aber keine belegte Kreisbohrung. ``exact`` nennt
    nur Merkmale, deren vorhandene Beschreibung die neue Form weiter trägt.
    ``mesh`` ist gegebenenfalls das bereits transformierte Netz mit derselben
    Flächennummerierung; an ihm lässt sich die Hohlraumhülle erneut messen.
    """
    from app.core.geom.transform import is_rigid

    if check_cancelled is not None:
        check_cancelled()
    matrix = np.asarray(transform, dtype=float)
    linear = matrix[:3, :3]
    factors = np.linalg.svd(linear, compute_uv=False)
    uniform = bool(np.allclose(factors, factors[0], rtol=0.0, atol=EPS_GEOM))
    rigid = is_rigid(matrix)
    result = moved_features(dict(features), transform, check_cancelled=check_cancelled)
    exact: set[FeatureId] = set()
    lengths = (
        "diameter",
        "depth",
        "length",
        "radius",
        "tube_diameter",
        "ring_diameter",
        "pitch",
        "width",
        "height",
        "cell_width",
        "cell_depth",
        "carrier_diameter",
        "travel",
        "fit_error",
        "radial_min",
        "radial_max",
    )
    for name, feature in result.items():
        if check_cancelled is not None:
            check_cancelled()
        params = dict(feature.params)
        sources = dict(feature.measure_sources)
        valid = rigid or uniform
        if "local_search_radius" in params:
            params["local_search_radius"] *= float(factors[0])
        if uniform:
            for key in lengths:
                if key in params:
                    params[key] *= float(factors[0])
            if "size" in params:
                params["size"] = tuple(float(value) * float(factors[0]) for value in params["size"])
            if "area" in params:
                params["area"] *= float(factors[0]) ** 2
            if "volume" in params:
                params["volume"] *= float(factors[0]) ** 3
        elif feature.kind in {"hole", "pin"}:
            axis = np.asarray(features[name].params["axis"], dtype=float)
            radial_factors = radial_scales(linear, axis)
            valid = radial_factors is not None
            if radial_factors is not None:
                radial_scale, axial_scale = radial_factors
                for key in ("diameter", "radius", "fit_error", "radial_min", "radial_max"):
                    if key in params:
                        params[key] *= radial_scale
                for key in ("depth", "length"):
                    if key in params:
                        params[key] *= axial_scale
                if "area" in params:
                    params["area"] *= radial_scale * axial_scale
                if "volume" in params:
                    params["volume"] *= radial_scale**2 * axial_scale
                valid = not any(
                    key in params
                    for key in (*lengths, "size")
                    if key
                    not in {
                        "diameter",
                        "radius",
                        "depth",
                        "length",
                        "fit_error",
                        "radial_min",
                        "radial_max",
                    }
                )
        elif feature.kind == "face":
            normal = np.asarray(features[name].params["normal"], dtype=float)
            normal = normal / np.linalg.norm(normal)
            factor = abs(float(np.linalg.det(linear))) * float(
                np.linalg.norm(np.linalg.solve(linear.T, normal))
            )
            if "area" in params:
                params["area"] *= factor
            valid = not any(key in params for key in (*lengths, "size", "volume"))
        if not uniform and not (valid and feature.kind in {"hole", "pin"}):
            # Der relative Konturfehler bleibt bei einheitlicher Vergrößerung
            # und kreisbewahrender Zylinderskalierung gleich. Andere affine
            # Formen brauchen für einen neuen Gütewert die wirklichen Messpunkte.
            params.pop("residual", None)
        if feature.kind == "void":
            # Größe und Mitte des Hohlraums bezeichnen seine Welt-AABB.
            # Die gedrehte alte Hülle umschließt die neue nur konservativ.
            nonzero = np.abs(linear) > EPS_GEOM
            aligned = bool((nonzero.sum(axis=0) == 1).all() and (nonzero.sum(axis=1) == 1).all())
            valid = aligned
            if "volume" in params:
                params["volume"] = features[name].params["volume"] * abs(
                    float(np.linalg.det(linear))
                )
            if "size" in params:
                params["size"] = tuple(
                    float(value) for value in np.abs(linear) @ features[name].params["size"]
                )
            if not aligned and mesh is not None and feature.face_indices:
                vertices = mesh.raw.vertices[mesh.raw.faces[list(feature.face_indices)].ravel()]
                low, high = vertices.min(axis=0), vertices.max(axis=0)
                params["centre"] = tuple(float(value) for value in (low + high) / 2.0)
                params["size"] = tuple(float(value) for value in high - low)
                sources.update(centre="facets", size="facets")
                valid = True
        result[name] = replace(
            feature,
            params=params,
            measure_sources={key: source for key, source in sources.items() if key in params}
            if valid
            else {},
        )
        if valid:
            exact.add(name)
    return FeatureTransform(result, frozenset(exact))
