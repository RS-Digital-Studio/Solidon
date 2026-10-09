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

import hashlib
import json
import math
import threading
from collections import OrderedDict
from collections.abc import Callable, Collection, Iterator, Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from app.core.deferred import cKDTree, linear_sum_assignment
from app.core.errors import AmbiguityError, InternalError
from app.core.log import get_logger
from app.core.perceive.match_records import valid_fingerprint
from app.core.perceive.surfaces import radial_scales, transformed_patches
from app.core.types import Feature, FeatureId, Mesh, Transform, Vec3
from app.core.units import EPS_GEOM, MAX_FACET_SAG, exact_mean, match_tolerance
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


def _query_radius(limit: float = MATCH_THRESHOLD) -> float:
    """Nur Rundungsreserve für den Raumfilter, keine zusätzliche Annahmetoleranz.

    Bei u=eps/2 umfasst R/(1-u)^5 die Rundungen von Norm, Division und
    Koordinatendifferenz. Die Baumabfrage verwendet die Maximumsnorm und
    exakt dieselben gerundeten Positionen wie die Kostenformel. Nahe der
    festen Grenze R=0,08 sind Quadrat und Wurzel normal darstellbar.

    ``limit`` ist die Kostengrenze, bis zu der jedes Paar gefunden werden
    muss — die Annahmeschwelle, im Nahweg (:func:`_near_assignment`) die
    Grenze der Mehrdeutigkeit. Die Lage allein kostet schon bis dahin; ab
    ``limit`` = 0,05 ist R nicht kleiner als 0,004 und die Rechnung dieselbe.
    """
    unit = Fraction(float(np.finfo(float).eps)) / 2
    radius = Fraction(POSITION_TOLERANCE) * Fraction(limit) / (1 - unit) ** 5
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
    """Alle räumlich möglichen Paare ohne Nachbarlimit; Kosten in Paketen.

    **Die Kosten mehrerer Zeilen in einem Aufruf** (RM-568): Je Zeile einzeln
    gerechnet, waren es am Eiffelturm 30 656 Aufrufe über eine Handvoll
    Spalten und 2,2 s je Zuordnung. Gesammelt wird, bis ein Paket
    :data:`COST_PAIRS` Paare erreicht — so bleibt die Spitze beim Rechnen
    begrenzt wie vorher in den Blöcken je Zeile, und ein Abbruch greift nach
    jedem Paket (Review L, G1). Die Formel rechnet elementweise; welche Paare
    nebeneinanderstehen, ändert keine Zahl.
    """
    kinds = np.asarray([entry.kind for entry in second], dtype=object)
    for start in range(0, len(first), VECTOR_ROWS):
        if check is not None:
            check()
        neighbours = tree.query_ball_point(
            one[start : start + VECTOR_ROWS, :3], radius, p=np.inf, return_sorted=True
        )
        if check is not None:
            check()
        rows: list[int] = []
        found: list[np.ndarray] = []
        gathered = 0
        for offset, nearby in enumerate(neighbours):
            row = start + offset
            indices = np.asarray(nearby, dtype=np.intp)
            indices = indices[kinds[indices] == first[row].kind]
            if gathered and gathered + len(indices) > COST_PAIRS:
                yield from _costed(first, one, two, rows, found, check)
                rows, found, gathered = [], [], 0
            rows.append(row)
            found.append(indices)
            gathered += len(indices)
        if rows:
            yield from _costed(first, one, two, rows, found, check)


#: Wie viele Paare :func:`_candidate_costs` höchstens in einem Aufruf bewertet —
#: so viele, wie früher ein Block aus Zeilen trug (``VECTOR_ROWS`` Spalten).
COST_PAIRS: Final = 65_536


def _costed(
    first: list[Feature],
    one: np.ndarray,
    two: np.ndarray,
    rows: list[int],
    found: list[np.ndarray],
    check: Callable[[], None] | None,
) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
    """Ein Paket Zeilen bewerten und zeilenweise in Blöcken ausgeben."""
    sizes = np.fromiter((len(indices) for indices in found), dtype=np.intp, count=len(found))
    if not sizes.sum():
        return
    pair_rows = np.repeat(np.asarray(rows, dtype=np.intp), sizes)
    pair_columns = np.concatenate(found)
    signless = np.repeat(
        np.fromiter(("axis" in first[row].params for row in rows), dtype=bool, count=len(rows)),
        sizes,
    )
    costs = _vector_costs(one[pair_rows], two[pair_columns], signless)
    ends = np.cumsum(sizes)
    for row, indices, end, size in zip(rows, found, ends.tolist(), sizes.tolist(), strict=True):
        values_of_row = costs[end - size : end]
        for block in range(0, size, VECTOR_ROWS):
            if check is not None:
                check()
            columns = indices[block : block + VECTOR_ROWS]
            values = values_of_row[block : block + VECTOR_ROWS]
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


def _row_minima(
    pairs: Iterator[tuple[int, np.ndarray, np.ndarray]], smaller: int, transposed: bool
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Je Zeile der kleineren Seite das kleinste, das zweitkleinste Paar und den Partner.

    Der Partner ist das erste Paar mit dem kleinsten Wert in der Folge der
    Paare; das zweitkleinste zählt Gleichstände mit — zwei Paare mit gleichem
    kleinstem Wert machen beide gleich. Wie die Paare auf Blöcke verteilt
    sind, ändert keine dieser drei Zahlen.
    """
    minima = np.full(smaller, np.inf)
    runners = np.full(smaller, np.inf)
    partners = np.full(smaller, -1, dtype=np.intp)
    for row, columns, values in pairs:
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
    return minima, runners, partners


#: Bis zu welcher Grenze :func:`_near_assignment` sucht; darüber spart die
#: kleinere Suche zu wenig, und es gilt der volle Weg.
NEAR_LIMIT: Final = 0.25


def _near_assignment(
    first: list[Feature],
    second: list[Feature],
    one: np.ndarray,
    two: np.ndarray,
    check: Callable[[], None] | None,
) -> _Assignment | None:
    """Fast deckungsgleiche Merkmalsmengen aus der Nähe zuordnen — dieselbe Antwort.

    **Nach einem Schritt, der die Merkmale nicht anrührt** — Filament
    zuweisen, Verschieben, Umbenennen —, liegt jedes alte Merkmal auf seinem
    neuen mit Kosten nahe null. Der volle Weg sucht trotzdem jedes Paar bis
    zur Annahmeschwelle 1,0: am Eiffelturm (4 870 Merkmale, dicht gedrängt)
    rund 600 Nachbarn je Merkmal, zweimal durchlaufen, 2,3 s je Schritt.
    Gebraucht wird davon nur, was unter der Grenze der Mehrdeutigkeit liegt.

    **Warum die Antwort dieselbe ist.** Eine vorläufige Paarung (über die
    Kennung, sonst die Stelle) schätzt das größte Minimum m nach oben ab; die
    Suche findet jedes Paar mit Kosten bis L = m·(1 + AMBIGUITY_MARGIN) +
    AMBIGUITY_FLOOR (:func:`_query_radius`). Damit stehen je Zeile das
    Minimum und alle gleich teuren Paare darin, also auch der Partner; liegt
    das zweitkleinste draußen, ist es größer als L und damit größer als das
    Minimum — für die Zertifizierung dasselbe. Zertifiziert, liest
    :func:`_open_claims` nur Paare unter den Zeilen- und Spaltengrenzen, und
    beide sind aus diesen Minima höchstens L. Ob die Abschätzung trägt,
    prüft der Weg an den gefundenen Minima selbst; sonst, und ohne
    Zertifikat, gilt der volle Weg.
    """
    count = len(first)
    if count != len(second) or not count:
        return None
    named = {feature.id: index for index, feature in enumerate(second)}
    order = (
        np.fromiter((named[feature.id] for feature in first), dtype=np.intp, count=count)
        if len(named) == count and all(feature.id in named for feature in first)
        else np.arange(count, dtype=np.intp)
    )
    if any(first[row].kind != second[int(column)].kind for row, column in enumerate(order)):
        return None
    signless = np.fromiter(("axis" in feature.params for feature in first), dtype=bool, count=count)
    largest = float(np.max(_vector_costs(one, two[order], signless)))
    limit = largest * (1.0 + AMBIGUITY_MARGIN) + AMBIGUITY_FLOOR
    if not limit <= NEAR_LIMIT:
        return None
    if check is not None:
        check()
    tree = cKDTree(two[:, :3])
    radius = _query_radius(limit)
    minima, runners, partners = _row_minima(
        _candidate_costs(first, second, one, two, tree, radius, check), count, False
    )
    if not (
        np.all(np.isfinite(minima))
        and float(np.max(minima)) * (1.0 + AMBIGUITY_MARGIN) + AMBIGUITY_FLOOR <= limit
        and np.all(minima <= MATCH_THRESHOLD)
        and np.all(runners > minima)
        and len(np.unique(partners)) == count
    ):
        return None
    rows = np.arange(count)
    return _Assignment(
        rows,
        partners,
        minima,
        None,
        lambda: _candidate_costs(first, second, one, two, tree, radius, check),
    )


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
    near = _near_assignment(first, second, one, two, check)
    if near is not None:
        return near
    tree = cKDTree(two[:, :3])
    radius = _query_radius()
    smaller = min(len(first), len(second))
    transposed = len(first) > len(second)
    minima, runners, partners = _row_minima(
        _candidate_costs(first, second, one, two, tree, radius, check), smaller, transposed
    )
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

    **U und L gelten je Zusammenhangskomponente der angenommenen Paare.**
    Strafpaare kosten überall dieselbe Strafe P, und es gibt nie weniger
    Spalten als Zeilen der kleineren Seite; jedes Optimum zahlt deshalb in
    jeder Komponente genau deren Optimum — sonst ließe sich die günstigere
    Komponente einer anderen Zuteilung übernehmen und die Strafpaare auf
    freie Spalten umlegen. Die Grenze einer Zeile ist damit m[r] + U_K - L_K
    ihrer Komponente K. Bis zum 22.09.2026 stand dort die Lücke des ganzen
    Körpers: Eine einzige Hall-Lücke — zwei alte Kegel, ein neuer — hob sie auf
    P, und die Hülle ließ dann auch den Tausch zweier Bohrungen zu, die mit
    Kosten 0,0 gegen 0,893 eindeutig lagen. Am Halter mit Wabenmuster kamen so
    nach *Dreiecke verringern* vier Fragen zu Bohrungen, die sich nicht bewegt
    hatten (RM-024). Die Zuteilung selbst bleibt die des globalen Lösers; nur
    die Hülle wird enger, und sie bleibt eine notwendige Bedingung.
    """
    transposed = matrix.shape[0] > matrix.shape[1]
    oriented = matrix.T if transposed else matrix
    minima = np.empty(len(oriented))
    for start in range(0, len(oriented), VECTOR_ROWS):
        if check is not None:
            check()
        minima[start : start + VECTOR_ROWS] = np.min(oriented[start : start + VECTOR_ROWS], axis=1)
    # Die gewählte Kante je Zeile der kleineren Seite — dort, wo sie steht.
    selected = np.empty(len(oriented))
    selected[assignment.columns if transposed else assignment.rows] = assignment.values
    components = _accepted_components(oriented, check)
    gaps: dict[int, Fraction] = {}
    for index, (chosen, minimum) in enumerate(zip(selected, minima, strict=True)):
        if check is not None and index % VECTOR_ROWS == 0:
            check()
        component = int(components[index])
        gaps[component] = (
            gaps.get(component, Fraction(0)) + Fraction(float(chosen)) - Fraction(float(minimum))
        )
    limits = np.empty(len(minima))
    for index, minimum in enumerate(minima):
        if check is not None and index % VECTOR_ROWS == 0:
            check()
        exact = Fraction(float(minimum)) + gaps[int(components[index])]
        rounded = float(exact)
        if Fraction(rounded) > exact:
            rounded = float(np.nextafter(rounded, -np.inf))
        limits[index] = rounded
    return limits


def _accepted_components(oriented: np.ndarray, check: Callable[[], None] | None) -> np.ndarray:
    """Je Zeile die Komponente, die ihre angenommenen Paare mit anderen Zeilen verbindet.

    Zwei Zeilen gehören zusammen, wenn sie eine angenommene Spalte teilen —
    auch über Zwischenschritte. Eine Zeile ohne angenommenes Paar steht allein.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    if check is not None:
        check()
    rows, columns = np.nonzero(oriented <= MATCH_THRESHOLD)
    count = oriented.shape[0] + oriented.shape[1]
    graph = coo_matrix(
        (np.ones(len(rows), dtype=np.int8), (rows, oriented.shape[0] + columns)),
        shape=(count, count),
    )
    _number, labels = connected_components(graph, directed=False)
    if check is not None:
        check()
    return np.asarray(labels[: oriented.shape[0]], dtype=np.intp)


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
    first = [old[identifier] for identifier in old_ids]
    second = [new[identifier] for identifier in new_ids]
    one = _vectors(first, before, diagonal, check_cancelled)
    two = _vectors(second, centre, diagonal, check_cancelled)
    key = _match_key(old_ids, first, one, new_ids, second, two)
    ways = tuple(globals()[name] for name in _MATCH_WAYS)
    with _MATCHES_LOCK:
        known = _MATCHES.get(key)
        if known is not None:
            _MATCHES.move_to_end(key)
    if known is not None and all(
        held is current for held, current in zip(known[0], ways, strict=True)
    ):
        return _copied(known[1])
    result = _matched(old_ids, first, new_ids, second, (before, centre, diagonal), check_cancelled)
    from app.core.memory import held_bytes

    stored = _copied(result)
    weight = (_identifiers(stored), held_bytes(stored))
    with _MATCHES_LOCK:
        global _MATCHED_IDS, _MATCHED_BYTES
        replaced = _MATCHES.pop(key, None)
        if replaced is not None:
            _MATCHED_IDS -= replaced[2][0]
            _MATCHED_BYTES -= replaced[2][1]
        _MATCHES[key] = (ways, stored, weight)
        _MATCHED_IDS += weight[0]
        _MATCHED_BYTES += weight[1]
        while len(_MATCHES) > 1 and _MATCHED_IDS > MATCHED_IDS_KEPT:
            _old_key, (_ways, _dropped, dropped) = _MATCHES.popitem(last=False)
            _MATCHED_IDS -= dropped[0]
            _MATCHED_BYTES -= dropped[1]
    return result


def _identifiers(result: MatchResult) -> int:
    """Wie viele Kennungen eine gemerkte Antwort trägt — ihr Gewicht im Merker."""
    return len(result.mapping) + len(result.orphaned) + len(result.ambiguous) + len(result.fresh)


def matched_bytes() -> int:
    """Was die gemerkten Antworten halten, in Bytes — für die Bytegrenze des Ergebniscaches.

    Gezählt einmal beim Ablegen (``memory.held_bytes`` je Antwort); die Frage
    rechnet nichts und kann deshalb bei jedem ``ResultCache.trim`` kommen.
    """
    with _MATCHES_LOCK:
        return _MATCHED_BYTES


#: Wie viele Kennungen die gemerkten Zuordnungen von :func:`match` zusammen
#: tragen. Eine Auswertung geht den ganzen Verlauf durch und ordnet nach jedem
#: Schritt neu zu, auch wenn er aus dem Cache kommt — am Eiffelturm 4,7 s je
#: Schritt und je Auswertung, das dritte Verschieben kostete so 16 statt 6 s
#: (08.10.2026, RM-568). Die Zuordnung hängt nur an Kennungen, Arten und
#: Merkmalsvektoren; dieselben Eingänge geben dieselbe Antwort. Begrenzt
#: über die Kennungen und nicht über die Zahl der Antworten: Eine Antwort mit
#: 5 000 Merkmalen wiegt 309 KiB (Review L, G3); zwei Millionen Kennungen
#: sind rund 120 MB, und die Bytegrenze des Ergebniscaches zählt sie mit
#: (:func:`matched_bytes`).
MATCHED_IDS_KEPT: Final = 2_000_000
#: Je Schlüssel die Rechenwege, die Antwort und ihr Gewicht (Kennungen, Bytes).
_MATCHES: OrderedDict[bytes, tuple[tuple[Any, ...], MatchResult, tuple[int, int]]] = OrderedDict()
_MATCHED_IDS = 0
_MATCHED_BYTES = 0
_MATCHES_LOCK = threading.Lock()


def _match_key(
    old_ids: list[FeatureId],
    first: list[Feature],
    one: np.ndarray,
    new_ids: list[FeatureId],
    second: list[Feature],
    two: np.ndarray,
) -> bytes:
    """Alles, was die Zuordnung liest: Kennungen in ihrer Folge, Arten, Achsenart, Vektoren.

    Dazu die Grenzen der Kostenformel und der Mehrdeutigkeit und die
    Paketgrößen. Die Rechenwege selbst (:data:`_MATCH_WAYS`)
    vergleicht :func:`match` beim Nachschlagen: Ein Test, der eine Grenze
    verstellt oder einen Rechenweg ersetzt, bekommt keine Antwort, die vorher
    unter anderen Regeln entstand.
    """
    digest = hashlib.blake2b(digest_size=20)
    rules = (
        POSITION_TOLERANCE,
        AXIS_TOLERANCE,
        DIAMETER_TOLERANCE,
        MATCH_THRESHOLD,
        KIND_PENALTY,
        AMBIGUITY_MARGIN,
        AMBIGUITY_FLOOR,
        VECTOR_ROWS,
        COST_PAIRS,
    )
    digest.update(repr(rules).encode("ascii"))
    for ids, features, vectors in ((old_ids, first, one), (new_ids, second, two)):
        digest.update(
            json.dumps(
                [
                    [str(identifier), feature.kind, "axis" in feature.params]
                    for identifier, feature in zip(ids, features, strict=True)
                ]
            ).encode("utf-8")
        )
        digest.update(np.ascontiguousarray(vectors, dtype=np.float64).tobytes())
    return digest.digest()


#: Die Rechenwege, an denen die Antwort von :func:`match` hängt — jede Stufe,
#: die ein Test ersetzen kann (Review L, G2).
_MATCH_WAYS: Final = (
    "feature_vector",
    "_vector_norm",
    "_vector_costs",
    "_vectors",
    "_cost_matrix",
    "_query_radius",
    "_candidate_costs",
    "_costed",
    "_matrix_pairs",
    "_not_finite",
    "_row_minima",
    "_near_assignment",
    "_assignment",
    "_hull_limits",
    "_accepted_components",
    "_reachable",
    "_strong_components",
    "_global_support",
    "_open_claims",
    "_close_claims",
    "linear_sum_assignment",
    "cKDTree",
)


def forget_matches() -> None:
    """Vergisst die gemerkten Zuordnungen — für Tests und Messungen."""
    global _MATCHED_IDS, _MATCHED_BYTES
    with _MATCHES_LOCK:
        _MATCHES.clear()
        _MATCHED_IDS = 0
        _MATCHED_BYTES = 0


def _copied(result: MatchResult) -> MatchResult:
    """Eine eigene Antwort je Aufrufer — ``mapping`` und ``ambiguous`` sind veränderlich."""
    return MatchResult(
        mapping=dict(result.mapping),
        orphaned=result.orphaned,
        ambiguous=dict(result.ambiguous),
        fresh=result.fresh,
    )


def _matched(
    old_ids: list[FeatureId],
    first: list[Feature],
    new_ids: list[FeatureId],
    second: list[Feature],
    frame: tuple[Vec3, Vec3, float],
    check_cancelled: Callable[[], None] | None,
) -> MatchResult:
    """Der Rumpf von :func:`match` — die Antwort merkt sich :data:`_MATCHES`."""
    before, centre, diagonal = frame
    # Die Vektoren rechnet ``_assignment`` noch einmal selbst: Tests ersetzen
    # es mit seiner bisherigen Unterschrift, und zweimal kostet es Millisekunden.
    assignment = _assignment(first, second, before, centre, diagonal, check_cancelled)
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


def settled_by_surface(
    result: MatchResult,
    old_places: Mapping[FeatureId, np.ndarray],
    new_places: Mapping[FeatureId, np.ndarray],
    diagonal: float,
) -> MatchResult:
    """Offene Zwillinge an der Lage ihrer Oberfläche entscheiden.

    **Drei Bögen desselben Grats sind für :func:`match` ein Merkmal dreimal**:
    dieselbe Art, Mitte, Achse und Größe — der Merkmalsvektor kennt nichts
    anderes. Jede Auswertung meldete sie mehrdeutig; ohne Verweis kamen sie
    unter neuen Namen zurück, mit Verweis fragte die Zuordnung den Kunden,
    was die Geometrie beantwortet. Am Ring des Siebhalters traf es drei von
    48 Verrundungen, nach *Kanten verfeinern*, *Bohrung setzen* weit weg und
    *Verschieben* gleichermaßen (Durchsicht 0.5.1).

    ``old_places`` und ``new_places`` sind je Merkmal der flächengewichtete
    Schwerpunkt seiner Dreiecke, beide im Rahmen des neuen Körpers. Ein Paar
    gilt nur, wenn es so nah liegt, wie :func:`cost` eine Lage annimmt
    (:data:`POSITION_TOLERANCE` mal Diagonale bis :data:`MATCH_THRESHOLD`),
    und wenn es **für beide Seiten** mit Vorsprung das nächste ist: der
    zweitnächste um :data:`AMBIGUITY_MARGIN` weiter und dazu um mehr als
    ``units.MAX_FACET_SAG`` — was näher beieinander liegt, unterscheidet das
    Netz nicht. Die Untergrenze der Zuordnung (:data:`AMBIGUITY_FLOOR`, ein
    Zwanzigstel der Lagetoleranz) gilt hier nicht: Sie trennt Kandidaten, die
    beide praktisch auf der Stelle liegen; eine Oberfläche, die genau dort
    liegt, und eine zweite 0,08 mm daneben — die Stufen einer geprägten
    Schrift an der Bildschirmabdeckung — sind das nicht. Was sich so nicht
    trennt, bleibt offen und wird gefragt, sobald ein Verweis daran hängt
    (Regel 21). Wer die Lage nicht kennt — ein Merkmal ohne Dreiecke —,
    entscheidet nichts.
    """
    if not result.ambiguous:
        return result
    scale = POSITION_TOLERANCE * max(diagonal, EPS_GEOM)
    taken = set(result.mapping.values())
    claimants: dict[FeatureId, list[FeatureId]] = {}
    for old_id, candidates in result.ambiguous.items():
        for candidate in candidates:
            if candidate not in taken:
                claimants.setdefault(candidate, []).append(old_id)

    def apart(old_id: FeatureId, new_id: FeatureId) -> float:
        one, two = old_places.get(old_id), new_places.get(new_id)
        if one is None or two is None:
            return math.inf
        return float(np.linalg.norm(np.asarray(one, dtype=float) - np.asarray(two, dtype=float)))

    def clearly_nearest(distances: list[float]) -> int | None:
        """Welcher Abstand mit Vorsprung der kleinste ist — oder keiner."""
        ordered = sorted((value, index) for index, value in enumerate(distances))
        if not ordered or not ordered[0][0] / scale <= MATCH_THRESHOLD:
            return None
        best, index = ordered[0]
        runner = ordered[1][0] if len(ordered) > 1 else math.inf
        return index if runner > best * (1.0 + AMBIGUITY_MARGIN) + MAX_FACET_SAG else None

    settled: dict[FeatureId, FeatureId] = {}
    for old_id, candidates in result.ambiguous.items():
        free = [candidate for candidate in candidates if candidate not in taken]
        forth = [apart(old_id, candidate) for candidate in free]
        pick = clearly_nearest(forth) if not any(map(math.isinf, forth)) else None
        if pick is None:
            continue
        chosen = free[pick]
        rivals = claimants[chosen]
        back = [apart(rival, chosen) for rival in rivals]
        if any(map(math.isinf, back)):
            continue
        nearest = clearly_nearest(back)
        if nearest is not None and rivals[nearest] == old_id:
            settled[old_id] = chosen
    if not settled:
        return result
    return replace(
        result,
        mapping={**result.mapping, **settled},
        ambiguous={
            old_id: candidates
            for old_id, candidates in result.ambiguous.items()
            if old_id not in settled
        },
        fresh=tuple(name for name in result.fresh if name not in set(settled.values())),
    )


def surface_places(
    features: Mapping[FeatureId, Feature],
    names: Collection[FeatureId],
    mesh: Mesh | None,
    movement: Transform | None,
) -> dict[FeatureId, Any]:
    """Wo die Oberfläche jedes dieser Merkmale liegt: der Schwerpunkt seiner Dreiecke.

    Flächengewichtet, damit ihn die Teilung der Dreiecke nicht verschiebt;
    ``movement`` bringt ihn in den Rahmen nach dem Schritt
    (``geom.transform.moved_points``, ohne BLAS — der Ort entscheidet zwischen
    Zwillingen). Ein Merkmal ohne Dreiecke oder mit Nummern, die dieses Netz
    nicht hat, bekommt keinen Ort.

    Mittelpunkte und Flächen kommen aus dem Cache des Netzes, wenn er sie
    hat; sonst rechnet diese Frage sie nur für die gefragten Dreiecke, mit
    denselben Formeln wie ``trimesh`` und ohne sie abzulegen. Gefragt wird
    auch nach Treffern aus dem Ergebniscache, und dessen ältere Netze sind
    schlank (``MeshData.lean``) — für das ganze Netz gerechnet, wuchsen sie
    bei jeder Auswertung um vier Felder nach, die ``trim`` wieder freigab
    (Review L, M2).
    """
    from app.core.geom.mesh import MeshData
    from app.core.geom.transform import moved_points

    if not isinstance(mesh, MeshData) or not names:
        return {}
    body = mesh.raw
    count = len(body.faces)
    wanted: dict[FeatureId, np.ndarray] = {}
    for name in names:
        feature = features.get(name)
        if feature is None or not feature.face_indices:
            continue
        faces = np.asarray(feature.face_indices, dtype=np.int64)
        if int(faces.min()) < 0 or int(faces.max()) >= count:
            continue
        wanted[name] = faces
    if not wanted:
        return {}
    centres, areas, rows = _face_centres_and_areas(body, wanted.values())
    places: dict[FeatureId, Any] = {}
    for name, faces in wanted.items():
        at = faces if rows is None else np.searchsorted(rows, faces)
        weights = areas[at]
        total = float(weights.sum())
        if not total > 0.0:
            continue
        place = (centres[at] * weights[:, None]).sum(axis=0) / total
        if movement is not None:
            place = moved_points(place.reshape(1, 3), np.asarray(movement, dtype=float))[0]
        places[name] = place
    return places


def _face_centres_and_areas(
    body: Any, groups: Collection[np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Mittelpunkte und Flächen der Dreiecke in ``groups`` und ihre Zeilen.

    Ohne Zeilen (``None``) sind es die Felder des ganzen Netzes aus seinem
    Cache, gelesen über die Dreiecksnummer. Sonst gilt für jede gefragte
    Nummer die Zeile ``searchsorted(rows, nummer)``; jede Zeile rechnet
    elementweise wie ``trimesh.Trimesh.triangles_center`` und ``area_faces``
    und ist deshalb bitgleich.
    """
    body._cache.verify()
    held = body._cache.cache
    if "triangles_center" in held and "area_faces" in held:
        return (
            np.asarray(held["triangles_center"], dtype=float),
            np.asarray(held["area_faces"], dtype=float),
            None,
        )
    rows = np.unique(np.concatenate(list(groups)))
    corners = body.vertices.view(np.ndarray)[body.faces.view(np.ndarray)[rows]]
    centres = corners.mean(axis=1)
    # trimesh.triangles.cross und .area, Schritt für Schritt
    edges = corners[:, 1:, :] - corners[:, :2, :]
    crosses = np.cross(edges[:, 0], edges[:, 1])
    areas = np.sqrt((crosses**2).sum(axis=1)) / 2.0
    return np.asarray(centres, dtype=float), np.asarray(areas, dtype=float), rows


def settled_twins(
    result: MatchResult,
    before: Mapping[FeatureId, Feature],
    old_mesh: Mesh | None,
    after: Mapping[FeatureId, Feature],
    new_mesh: Mesh | None,
    diagonal: float,
    *,
    movement: Transform | None = None,
) -> MatchResult:
    """:func:`settled_by_surface` mit den Lagen beider Seiten — für jeden Weg,
    der alte Merkmale den neuen eines Körpers zuordnet.

    ``before`` trägt die Dreiecke der alten Merkmale auf ``old_mesh``, ``after``
    die der neuen auf ``new_mesh``; ``movement`` ist die Bewegung des Schritts.
    Wer nur einen Teil der alten Merkmale an ihren alten Dreiecken kennt, gibt
    nur diesen Teil: Ein Zwilling ohne Ort wird nicht entschieden.

    **Dieselbe Frage am Netz und am exakten Kern** (RM-226, Nachtrag
    04.10.2026): Zwei gleiche Rundungen — die Wandstücke einer Tasche zwischen
    zwei Schlitzen, zwei Stücke eines Kegelmantels — sind für :func:`match` ein
    Merkmal zweimal. Die Auswertung am Netz entschied sie schon an der Lage
    ihrer Oberfläche; der Neubau eines exakten Körpers und seine Auswertung
    nicht — am Teppichclip hießen ``cone_4`` und ``cone_11`` nach einer
    Bohrung anderswo ``cone_12`` und ``cone_13``.
    """
    if not result.ambiguous:
        return result
    return settled_by_surface(
        result,
        surface_places(before, set(result.ambiguous), old_mesh, movement),
        surface_places(
            after, {name for names in result.ambiguous.values() for name in names}, new_mesh, None
        ),
        diagonal,
    )


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
        if (
            feature is not None
            and ancestor is not None
            and feature.created_by is None
            and ancestor.created_by is not None
        ):
            # Ohne Erzeuger beim Vorfahren wäre die Kopie dasselbe Merkmal.
            inherited[name] = replace(feature, created_by=ancestor.created_by)
    return inherited


def apply_mapping(
    new: dict[FeatureId, Feature],
    result: MatchResult,
    *,
    previous: Mapping[FeatureId, Feature] | None = None,
    reserved: Collection[FeatureId] = (),
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

    ``reserved`` sind Namen, die neben der Zuordnung weiterleben — was die
    Operation selbst ausgibt, was ungeprüft mitreist, was starr mitbewegt
    bleibt. Ein neues Merkmal bekommt keinen davon (RM-222): Beim
    Zusammenführen überschrieb der Mitreisende das neue, und eine eben
    gebohrte Bohrung fehlte wortlos, sobald eine vorher geänderte den nächsten
    freien Namen trug.
    """
    require_injective(result.mapping)
    renamed: dict[FeatureId, Feature] = {}
    reverse = {value: key for key, value in result.mapping.items()}
    # Auch die mehrdeutigen alten Namen bleiben gesperrt: wer eine
    # Mehrdeutigkeit mit „Verwerfen" beantwortet, hat den Namen aufgegeben —
    # ihn sofort neu zu vergeben ließe eine Passung auf das falsche Merkmal
    # zeigen. Aufgelöste stehen ohnehin schon im mapping, der Zusatz ist
    # dann folgenlos.
    taken: set[FeatureId] = (
        set(result.mapping) | set(result.orphaned) | set(result.ambiguous) | set(reserved)
    )
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
        #
        # **Behält es seinen Namen, bleibt es dasselbe Objekt** (RM-636): Die
        # Kopie wäre in jedem Feld gleich, und ein Merkmal ist unveränderlich.
        # Als neues Objekt traf es nach jedem Schritt, der nichts umbenennt,
        # den Teilhash-Merker der Auswertung nicht (``hashing.object_hash``) —
        # am Eiffelturm 4 870 Teilhashes je Filament zuweisen.
        renamed[target] = feature if feature.id == target else replace(feature, id=target)
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


#: Die Quellen, deren Wert eine Messung an den Dreiecken ist und keine Vorgabe
#: (RM-216): Nur sie liest ein erklärtes Merkmal an seinem heutigen Partner neu.
_MEASURED_SOURCES: Final = frozenset({"facets", "fit"})


def near_its_declaration(declared: Feature, found: Feature) -> bool:
    """Ob ein erkanntes Merkmal dort liegt, wo die Operation ihr erklärtes gesetzt hat.

    Quer zur Achse darf der Mittelpunkt höchstens um die Breite des erklärten
    Merkmals abweichen — Durchmesser, bei einem Langloch seine Länge —, entlang
    der Achse höchstens um seine Tiefe, wo eine erklärt ist: Wo auf der Achse
    eine Mitte liegt, ist eine Frage der Messung (Mündung oder Mitte, je nach
    Erzeuger), wie weit daneben eine Bohrung liegt, nicht. Ohne Achse gilt die
    Breite als Abstand. Ein erklärtes Merkmal ohne Größe oder ohne Ort wird
    nicht beschränkt; dort entscheidet die Zuordnung allein.
    """

    def number(key: str) -> float:
        value = declared.params.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return abs(float(value))
        return 0.0

    width = max(number("diameter"), number("length"))
    where = declared.params.get("centre")
    there = found.params.get("centre")
    if not isinstance(where, tuple | list) or not isinstance(there, tuple | list):
        return True
    if width <= EPS_GEOM:
        return True
    try:
        offset = [float(b) - float(a) for a, b in zip(where, there, strict=True)]
        axis = declared.params.get("axis")
        direction = [float(value) for value in axis] if isinstance(axis, tuple | list) else []
    except TypeError, ValueError:
        return True
    length = math.hypot(*direction) if len(direction) == 3 else 0.0
    if length <= EPS_GEOM:
        return math.hypot(*offset) <= width
    unit = [value / length for value in direction]
    along = sum(a * b for a, b in zip(offset, unit, strict=True))
    across = math.hypot(*(value - along * part for value, part in zip(offset, unit, strict=True)))
    depth = number("depth")
    return across <= width and (depth <= EPS_GEOM or abs(along) <= depth)


def measured_again(declared: Feature, found: Feature) -> dict[str, Any]:
    """Die gemessenen Werte eines erklärten Merkmals, am heutigen Partner abgelesen.

    Nur, was die Erzeugung selbst als Messung ausweist
    (:data:`_MEASURED_SOURCES`), was beide tragen und nur bei derselben Art.
    Eine Vorgabe aus dem Schritt (``parameter``) oder aus der Konstruktion
    (``native``) bleibt, wie sie ist: Die Normale von ``face_top`` ist die
    Richtung, die der Quader seiner Deckfläche gibt, ihre Fläche eine Messung,
    die nach einer Bohrung nicht mehr stimmte (RM-216).
    """
    if found.kind != declared.kind:
        return {}
    return {
        key: found.params[key]
        for key, source in declared.measure_sources.items()
        if source in _MEASURED_SOURCES and key in declared.params and key in found.params
    }


def declared_partners(
    declared: Mapping[FeatureId, Feature],
    detected: Mapping[FeatureId, Feature],
    centre: Vec3,
    diagonal: float,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> MatchResult:
    """Welches erkannte Merkmal ein erklärtes ist — gesucht an seiner Stelle.

    Die Zuordnung toleriert 8 % der Diagonale, weil zwischen zwei Schritten
    ungeklärt gewandert werden darf; was eine Operation selbst gesetzt hat,
    steht aber dort, wo sie es sagt (:func:`near_its_declaration`). Weiter weg
    als seine eigene Größe ist es nicht es selbst und zählt als verwaist.
    Beide Kerne fragen so: die Auswertung am Netz und der Baustein an seinem
    exakten Ergebnis (``knowledge.parts.ops``).
    """
    seen = match(dict(declared), dict(detected), centre, diagonal, check_cancelled=check_cancelled)
    far = {
        name
        for name, found in seen.mapping.items()
        if not near_its_declaration(declared[name], detected[found])
    }
    # **Dieselbe Stelle entscheidet auch unter Konkurrenten** (Durchsicht
    # 0.5.1). Zwei erklärte Stifte 16,6 mm auseinander an einem Körper mit
    # 635 mm Diagonale liegen beide in der Toleranz der Zuordnung, und der
    # eine erkannte Stift war umkämpft: Keiner bekam ihn, er stand unter einem
    # frischen Namen ``pin_3`` daneben, und die Nummer fehlte dem nächsten
    # Verbinder — zwei Passungen des Auto-Split zeigten ins Leere. Wer seinen
    # Kandidaten an seiner Stelle hat und ihn mit niemandem teilt, bekommt ihn;
    # wer an seiner Stelle keinen hat, ist verwaist wie ein zu ferner Partner.
    placed: dict[FeatureId, FeatureId] = {}
    lonely: set[FeatureId] = set()
    if seen.ambiguous:
        near = {
            name: tuple(
                candidate
                for candidate in candidates
                if near_its_declaration(declared[name], detected[candidate])
            )
            for name, candidates in seen.ambiguous.items()
        }
        claimed: dict[FeatureId, list[FeatureId]] = {}
        for name, candidates in near.items():
            for candidate in candidates:
                claimed.setdefault(candidate, []).append(name)
        taken = set(seen.mapping.values())
        for name, candidates in near.items():
            if not candidates:
                lonely.add(name)
            elif (
                len(candidates) == 1
                and claimed[candidates[0]] == [name]
                and candidates[0] not in taken
            ):
                placed[name] = candidates[0]
    if not far and not placed and not lonely:
        return seen
    settled = set(placed) | lonely
    return replace(
        seen,
        mapping={
            **{name: found for name, found in seen.mapping.items() if name not in far},
            **placed,
        },
        ambiguous={
            name: candidates for name, candidates in seen.ambiguous.items() if name not in settled
        },
        orphaned=(*seen.orphaned, *sorted(far | lonely)),
        fresh=tuple(name for name in seen.fresh if name not in set(placed.values())),
    )


def on_their_partners(
    declared: Mapping[FeatureId, Feature],
    detected: Mapping[FeatureId, Feature],
    seen: MatchResult,
) -> dict[FeatureId, Feature]:
    """Die erklärten Merkmale mit der heutigen Oberfläche ihres Partners.

    **Der Name bleibt, die aktuelle Oberfläche geht mit.** Ein Baustein kennt
    Ort und Maß seiner Bohrung, aber nicht die Dreiecksnummern des Körpers,
    der erst aus seiner Geometrie entsteht; die Erkennung kennt genau diese.
    Mit eindeutigem Partner (``seen.mapping``) bekommt das erklärte Merkmal
    dessen Dreiecke und Teilträger und liest seine Messwerte neu
    (:func:`measured_again`); Werte aus dem Schritt bleiben. Wer verwaist ist,
    trägt ``recognised=False`` und keinen Teilträger; ein umkämpftes bleibt,
    wie es war.
    """
    placed: dict[FeatureId, Feature] = {}
    orphaned = set(seen.orphaned)
    for name, feature in declared.items():
        partner = seen.mapping.get(name)
        if partner is not None and partner in detected:
            found = detected[partner]
            feature = replace(
                feature,
                face_indices=found.face_indices,
                surface_patches=found.surface_patches,
                params={**feature.params, **measured_again(feature, found)},
            )
        elif name in orphaned:
            feature = replace(feature, recognised=False, surface_patches=())
        placed[name] = feature
    return placed


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
                # Nur ein Einheitsvektor wird wieder einer. Die Normale einer
                # gerundeten Seite ist das flächengewichtete Mittel und an einem
                # geschlossenen Mantel entsprechend kurz (``detect_curved_faces``);
                # sie auf eins zu strecken machte aus der mitgeführten Erkennung
                # eine andere Auskunft als die frische am bewegten Netz
                # (gemessen am 22.09.2026 an 19 von 125 Körpern des Korpus).
                if length > EPS_GEOM and abs(float(np.linalg.norm(original)) - 1.0) <= EPS_GEOM:
                    direction = direction / length
                params[key] = (float(direction[0]), float(direction[1]), float(direction[2]))
        if feature.kind == "thread" and float(np.linalg.det(turn)) < 0.0:
            handedness = params.get("handedness")
            if handedness in {"right", "left"}:
                params["handedness"] = "left" if handedness == "right" else "right"
        if feature.kind == "pattern" and params.get("carrier") != "cylinder":
            turned = _turned_field_angle(feature.params, params, turn)
            if turned is not None:
                params["angle"] = turned
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


def _turned_field_angle(
    before: Mapping[str, Any], after: Mapping[str, Any], turn: np.ndarray
) -> float | None:
    """Der Feldwinkel eines ebenen Musters in der Ebene nach der Abbildung.

    ``angle`` zählt gegen die erste Achse der Trägerebene, und die folgt allein
    aus der Normalen (``units.plane_axes`` — dieselbe Regel wie
    ``patterns.Frame.plane``). Eine Drehung um die Normale lässt die Normale
    stehen und drehte bis zum 22.09.2026 auch den Winkel nicht: Die
    mitgeführte Erkennung (``features.carry_detection``) trug nach 30 Grad am
    Halter mit Wabenmuster weiter 90, die frische 120, und *Merkmal ändern*
    zeichnete das Feld verdreht neu. Die erste Feldachse wird deshalb in der
    Welt mitgedreht und in der neuen Ebene gelesen; gezählt wird wie bei der
    Erkennung zwischen null und 180 Grad (``patterns._turn``).
    """
    from app.core import units

    try:
        angle = math.radians(float(before["angle"]))
        old_axes = units.plane_axes(tuple(float(value) for value in before["normal"]))
        new_axes = units.plane_axes(tuple(float(value) for value in after["normal"]))
    except KeyError, TypeError, ValueError:
        return None
    if old_axes is None or new_axes is None:
        return None
    first, second = (np.asarray(axis, dtype=float) for axis in old_axes)
    along = turn @ (math.cos(angle) * first + math.sin(angle) * second)
    x_axis, y_axis = (np.asarray(axis, dtype=float) for axis in new_axes)
    turned = math.degrees(math.atan2(float(along @ y_axis), float(along @ x_axis))) % 180.0
    return 0.0 if turned >= 180.0 - 1e-3 else turned


@dataclass(frozen=True, slots=True)
class FeatureTransform:
    """Suchkandidaten und die Teilmenge mit weiterhin gültigen Formmaßen."""

    candidates: dict[FeatureId, Feature]
    exact: frozenset[FeatureId]


#: Die letzten Antworten von :func:`transformed_features` — je Eintrag Schlüssel,
#: die gehaltenen Eingänge (damit keine Kennung neu vergeben wird) und die Antwort.
_TRANSFORMED: OrderedDict[tuple[Any, ...], tuple[tuple[Any, ...], FeatureTransform]] = OrderedDict()
_TRANSFORMED_LOCK = threading.Lock()
#: Zwei reichen: Die Operation und die Zuordnung danach fragen dasselbe nacheinander.
TRANSFORMED_KEPT: Final = 2


def transformed_features(
    features: Mapping[FeatureId, Feature],
    transform: Transform,
    *,
    mesh: MeshData | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> FeatureTransform:
    """Maße einmal für globale und örtliche Zuordnung nachführen — dieselbe Frage einmal.

    **Verschieben fragte zweimal dasselbe** (RM-636): Die Operation bewegt die
    Merkmale ihres Eingangs (``geom.transform.moved_object``), und die
    Zuordnung danach bewegt dieselben Merkmale mit derselben Matrix noch
    einmal an demselben Netz (``scene.evaluate._with_features``) — am
    Eiffelturm 4 870 Merkmale samt Teilträgern je Verschieben doppelt.
    Gemerkt wird die Antwort für dieselben Merkmalsobjekte unter denselben
    Namen in derselben Folge und dieselbe Matrix; die Rechenwege gehören zum
    Schlüssel wie bei :func:`match`. Das Netz liest nur ein Hohlraum — mit
    einem rechnet jede Frage neu, und gehalten wird so kein Netz. Jeder
    Aufrufer bekommt ein eigenes Wörterbuch.
    """
    if any(feature.kind == "void" for feature in features.values()):
        return _transformed_features(
            features, transform, mesh=mesh, check_cancelled=check_cancelled
        )
    ways = (moved_features, transformed_patches, radial_scales, _transformed_features)
    key = (
        tuple((name, id(feature)) for name, feature in features.items()),
        np.ascontiguousarray(np.asarray(transform, dtype=float)).tobytes(),
        tuple(id(way) for way in ways),
    )
    with _TRANSFORMED_LOCK:
        known = _TRANSFORMED.get(key)
        if known is not None:
            _TRANSFORMED.move_to_end(key)
    if known is not None:
        if check_cancelled is not None:
            check_cancelled()
        answer = known[1]
        return FeatureTransform(dict(answer.candidates), answer.exact)
    answer = _transformed_features(features, transform, mesh=mesh, check_cancelled=check_cancelled)
    with _TRANSFORMED_LOCK:
        _TRANSFORMED[key] = ((tuple(features.values()), ways), answer)
        while len(_TRANSFORMED) > TRANSFORMED_KEPT:
            _TRANSFORMED.popitem(last=False)
    return FeatureTransform(dict(answer.candidates), answer.exact)


def forget_transformed() -> None:
    """Vergisst die gemerkten Bewegungen — für Tests und Messungen."""
    with _TRANSFORMED_LOCK:
        _TRANSFORMED.clear()


def _transformed_features(
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
        # Die Öffnung einer Verengung (``features.narrowings_marked``, R3).
        "opening",
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
        if not rigid:
            # Ein vergrößertes gedrucktes Gewinde ist keines aus der Tabelle mehr:
            # Sein Spiel ist mitgewachsen, es ist gebaut, wie es dasteht
            # (``fits._thread_wanted``).
            params.pop("nominal", None)
            sources.pop("nominal", None)
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
                vertices = np.asarray(mesh.raw.vertices)[
                    np.asarray(mesh.raw.faces)[list(feature.face_indices)].ravel()
                ]
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


@dataclass(frozen=True, slots=True)
class PlanarFaces:
    """Die ebenen Flächen nach dem Schritt als Felder — einmal gebaut, je alte Fläche gefragt.

    Die Frage nach den Stücken einer alten Fläche läuft über jede erkannte
    Fläche; als Schleife je alter Fläche wäre das Waisen mal Flächen in
    Python, an der Kumiko-Schale mit 7 295 Flächen Sekunden.
    """

    names: tuple[FeatureId, ...]
    normals: Any
    centres: Any
    areas: Any


def planar_faces(detected: Mapping[FeatureId, Feature]) -> PlanarFaces:
    """Die ebenen Flächen aus ``detected`` mit Normale, Mitte und Fläche."""

    names: list[FeatureId] = []
    normals: list[tuple[float, float, float]] = []
    centres: list[tuple[float, float, float]] = []
    areas: list[float] = []
    for name, candidate in detected.items():
        if candidate.kind != "face":
            continue
        there = candidate.params.get("centre")
        direction = candidate.params.get("normal")
        if not isinstance(there, tuple | list) or not isinstance(direction, tuple | list):
            continue
        if len(there) != 3 or len(direction) != 3:
            continue
        names.append(name)
        normals.append((float(direction[0]), float(direction[1]), float(direction[2])))
        centres.append((float(there[0]), float(there[1]), float(there[2])))
        areas.append(float(candidate.params.get("area", 0.0) or 0.0))
    return PlanarFaces(
        tuple(names),
        np.asarray(normals, dtype=float).reshape(-1, 3),
        np.asarray(centres, dtype=float).reshape(-1, 3),
        np.asarray(areas, dtype=float),
    )


@dataclass(frozen=True, slots=True)
class PlanarSource:
    """Eine alte ebene Fläche, gemessen an ihren Dreiecken im Eingangsnetz.

    ``direction`` ist ihre Normale als Einheitsvektor, ``middle`` ihre Mitte,
    ``tolerance`` die Zuordnungstoleranz des Eingangsnetzes.
    """

    corners: Any
    direction: Any
    middle: Any
    tolerance: float


def planar_source(feature: Feature | None, source: Mesh | None) -> PlanarSource | None:
    """Die Dreiecke einer alten ebenen Fläche im Eingangsnetz — wenn sie diese Fläche sind.

    ``None`` heißt: kein Netz, keine gültigen Nummern, oder die Dreiecke unter
    diesen Nummern sind eine andere Fläche — ihre flächengewichtete Normale
    weicht ab, oder ihre Mitte liegt nicht in der Ebene des Merkmals. So
    sehen Nummern aus, die eine Operation an ihrem eigenen Ergebnis vergeben
    hat: Am Eingang bezeichnen sie fremde Dreiecke, und aus deren Hüllquader
    bekäme ein falsches Stück den Namen. Summiert wird exakt (``math.fsum``,
    RM-187), denn an der Antwort hängt, welches Stück welchen Namen trägt.
    """

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import PARALLEL_FACE_COSINE

    if feature is None or feature.kind != "face" or not feature.face_indices:
        return None
    if source is not None and not isinstance(source, MeshData):
        # Ein exakter Körper: Die Dreiecksnummern seiner Merkmale zeigen auf
        # seine Tessellierung (beide Kerne gleich, R4).
        converted = getattr(source, "to_mesh", None)
        source = converted() if callable(converted) else None
    if not isinstance(source, MeshData):
        return None
    normal = feature.params.get("normal")
    centre = feature.params.get("centre")
    if not isinstance(normal, tuple | list) or not isinstance(centre, tuple | list):
        return None
    if len(normal) != 3 or len(centre) != 3:
        return None
    faces = np.asarray(feature.face_indices, dtype=np.int64)
    if int(faces.max()) >= source.triangle_count or int(faces.min()) < 0:
        return None
    direction = np.asarray([float(value) for value in normal], dtype=float)
    middle = np.asarray([float(value) for value in centre], dtype=float)
    weights = np.asarray(source.raw.area_faces, dtype=float)[faces]
    normals = np.asarray(source.raw.face_normals, dtype=float)[faces] * weights[:, None]
    summed = [math.fsum(normals[:, axis].tolist()) for axis in range(3)]
    length = math.sqrt(math.fsum(value * value for value in summed))
    own = math.sqrt(math.fsum(float(value) * float(value) for value in direction))
    if length <= 0.0 or own <= 0.0:
        return None
    facing = math.fsum(float(a) * float(b) for a, b in zip(summed, direction, strict=True))
    if facing < PARALLEL_FACE_COSINE * length * own:
        return None
    corners = np.asarray(source.raw.vertices, dtype=float)[
        np.asarray(source.raw.faces, dtype=np.int64)[faces].ravel()
    ]
    tolerance = match_tolerance(source.bounds.diagonal)
    unit = direction / own
    offsets = ((corners - middle) * unit).sum(axis=1)
    if abs(exact_mean(offsets.tolist())) > tolerance:
        return None
    return PlanarSource(corners, unit, middle, tolerance)


def pieces_in_place(
    feature: Feature | None, faces_now: PlanarFaces, source: Mesh | None
) -> tuple[FeatureId, ...]:
    """Die erkannten Flächen, die Stücke einer alten ebenen Fläche sind.

    Ein Stück liegt in der Ebene der alten Fläche, gleich gerichtet, und seine
    Mitte im Hüllquader ihrer Dreiecke im Eingangsnetz (:func:`planar_source`).
    Dieselbe Messung für zwei Fragen: ob die alte Fläche fort ist
    (:func:`_divided_in_place`) und welches Stück ihren Namen trägt
    (:func:`_divided_partners`). Gerechnet mit Grundrechenarten (RM-187): An
    der Antwort hängt, welches Stück welchen Namen trägt.
    """

    if not faces_now.names:
        return ()
    old = planar_source(feature, source)
    if old is None:
        return ()
    low = old.corners.min(axis=0) - old.tolerance
    high = old.corners.max(axis=0) + old.tolerance
    chosen = faces_in_plane(faces_now, old.direction, old.middle, old.tolerance, box=(low, high))
    return tuple(faces_now.names[index] for index in np.flatnonzero(chosen))


def faces_in_plane(
    faces_now: PlanarFaces,
    direction: Any,
    middle: Any,
    tolerance: float,
    *,
    box: tuple[Any, Any] | None = None,
) -> Any:
    """Welche erkannten Flächen in einer Ebene liegen, gleich gerichtet — als Maske.

    ``direction`` ist die Normale der Ebene als Einheitsvektor, ``middle`` ein
    Punkt in ihr. Mit ``box`` (untere und obere Ecke) zählt nur, wessen Mitte
    darin liegt. Eine Rechnung für zwei Fragen: welche Stücke eine alte Fläche
    hat (:func:`pieces_in_place`) und ob von einer erzeugten noch etwas da ist
    (``scene.evaluate._consumed_faces``). Grundrechenarten und Summen über eine
    Achse (RM-187): An der Antwort hängt ein Name.
    """
    from app.core.perceive.features import PARALLEL_FACE_COSINE

    facing = (faces_now.normals * direction).sum(axis=1) >= PARALLEL_FACE_COSINE
    apart = np.abs(((faces_now.centres - middle) * direction).sum(axis=1))
    chosen = facing & (apart <= tolerance)
    if box is not None:
        low, high = box
        chosen &= ((faces_now.centres >= low) & (faces_now.centres <= high)).all(axis=1)
    return chosen
