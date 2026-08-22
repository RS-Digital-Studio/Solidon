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

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.core.log import get_logger
from app.core.types import Feature, FeatureId, Transform, Vec3
from app.core.units import EPS_GEOM

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


@dataclass(slots=True)
class MatchResult:
    """Wer wer geworden ist, und was sich nicht entscheiden ließ."""

    mapping: dict[FeatureId, FeatureId] = field(default_factory=dict)
    """Alte Kennung auf neue Kennung."""
    orphaned: tuple[FeatureId, ...] = ()
    """Alte Merkmale ohne Partner (§21.2)."""
    ambiguous: dict[FeatureId, tuple[FeatureId, ...]] = field(default_factory=dict)
    """Alte Merkmale mit mehreren gleich guten Kandidaten — nach denen wird gefragt."""
    fresh: tuple[FeatureId, ...] = ()
    """Neue Merkmale, die niemand erwartet hat."""

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

    position = float(np.linalg.norm(one[:3] - two[:3])) / POSITION_TOLERANCE
    # Eine Bohrungs- oder Stiftachse ist eine Linie, keine Richtung: die
    # Erkennung liefert sie nach einer Drehung mal als +v, mal als -v, und
    # beides ist dasselbe Merkmal. Eine Flächennormale trägt ihr Vorzeichen
    # dagegen zu Recht — innen ist nicht außen. Unterschieden am Parameter,
    # nicht an einer Artenliste: was eine ``axis`` hat, ist richtungslos.
    delta = float(np.linalg.norm(one[3:6] - two[3:6]))
    if "axis" in first.params:
        delta = min(delta, float(np.linalg.norm(one[3:6] + two[3:6])))
    axis = delta / AXIS_TOLERANCE
    scale = max(abs(float(one[6])), abs(float(two[6])), EPS_GEOM)
    diameter = abs(float(one[6]) - float(two[6])) / scale / DIAMETER_TOLERANCE
    return float(position + axis + diameter)


def match(
    old: dict[FeatureId, Feature],
    new: dict[FeatureId, Feature],
    centre: Vec3,
    diagonal: float,
    old_centre: Vec3 | None = None,
) -> MatchResult:
    """Ordnet neue Merkmale alten Bezeichnern zu und sagt, was offen blieb.

    ``centre`` ist das Bezugssystem des neuen Körpers, ``old_centre`` das, in
    dem die alten Merkmale gemessen wurden — per Vorgabe dasselbe.
    """
    if not old:
        return MatchResult(fresh=tuple(new))
    if not new:
        return MatchResult(orphaned=tuple(old))

    before = old_centre if old_centre is not None else centre
    old_ids = list(old)
    new_ids = list(new)
    matrix = np.array(
        [[cost(old[a], new[b], before, centre, diagonal) for b in new_ids] for a in old_ids],
        dtype=float,
    )
    threshold = MATCH_THRESHOLD
    # **Was ohnehin abgelehnt würde, kostet so viel wie eine falsche Art.**
    # Die ungarische Methode minimiert die *Gesamtsumme* und kennt die Schwelle
    # nicht — sie opfert deshalb ein annehmbares Paar, wenn zwei unannehmbare
    # zusammen billiger sind. Gemessen an einer Platte mit Schraubenlöchern und
    # einer Mutternfalle:
    #
    #     nut_trap_pocket_1 -> hole_2   3,281   verwaist
    #     nut_trap_bore_1   -> hole_1   3,742   verwaist   (bester wäre hole_2 mit 0,757)
    #
    # Die Summe 7,02 ist kleiner als jede Lösung, die ``hole_2`` an die Bohrung
    # gibt — und **beide** fallen über die Schwelle. Mit dem 0,757er Paar wäre
    # eines gerettet worden statt keines. Angehoben sieht die Optimierung, dass
    # ein Paar über der Schwelle so wertlos ist wie gar keines, und nimmt
    # lieber das eine, das zählt.
    matrix = np.where(matrix > threshold, KIND_PENALTY, matrix)

    rows, columns = linear_sum_assignment(matrix)
    result = MatchResult()
    taken: set[str] = set()

    for row, column in zip(rows, columns, strict=True):
        old_id = old_ids[row]
        best = float(matrix[row, column])
        if best > threshold:
            result.orphaned = (*result.orphaned, old_id)
            continue

        # Ein Rivale ist einer, der *ähnlich gut* passt — nicht jeder, der
        # überhaupt in Frage kommt. Mit ``max(…, threshold)`` war jeder
        # Kandidat unter der Annahmeschwelle ein Rivale, auch wenn der beste
        # Treffer null kostete und er selbst fast eins: eine Mutternfalle mit
        # Tasche und Bohrung übereinander machte jede Auswertung des Gehäuses
        # zur Rückfrage. Der Boden hält den Fall offen, dass zwei Kandidaten
        # beide fast nichts kosten und wirklich nicht zu unterscheiden sind.
        limit = best * (1.0 + AMBIGUITY_MARGIN) + AMBIGUITY_FLOOR
        rivals = [
            new_ids[other]
            for other in range(len(new_ids))
            if other != column and float(matrix[row, other]) <= limit
        ]
        if rivals:
            # §21.3: mehrere dichte Kandidaten — anhalten und fragen statt raten.
            result.ambiguous[old_id] = (new_ids[column], *rivals)
            continue

        result.mapping[old_id] = new_ids[column]
        taken.add(new_ids[column])

    unmatched = [identifier for identifier in old_ids if identifier not in result.mapping]
    result.orphaned = tuple(
        identifier
        for identifier in unmatched
        if identifier not in result.ambiguous and identifier not in result.orphaned
    ) + tuple(entry for entry in result.orphaned)
    result.fresh = tuple(identifier for identifier in new_ids if identifier not in taken)

    if result.ambiguous:
        _log.info("feature matching left %d ambiguous", len(result.ambiguous))
    return result


def apply_mapping(new: dict[FeatureId, Feature], result: MatchResult) -> dict[FeatureId, Feature]:
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
    """
    renamed: dict[FeatureId, Feature] = {}
    reverse = {value: key for key, value in result.mapping.items()}
    # Auch die mehrdeutigen alten Namen bleiben gesperrt: wer eine
    # Mehrdeutigkeit mit „Verwerfen" beantwortet, hat den Namen aufgegeben —
    # ihn sofort neu zu vergeben ließe eine Passung auf das falsche Merkmal
    # zeigen. Aufgelöste stehen ohnehin schon im mapping, der Zusatz ist
    # dann folgenlos.
    taken: set[FeatureId] = set(result.mapping) | set(result.orphaned) | set(result.ambiguous)
    for identifier, feature in new.items():
        target = reverse.get(identifier)
        if target is None:
            target = identifier if identifier not in taken else _fresh_id(identifier, taken)
        taken.add(target)
        renamed[target] = Feature(
            id=target,
            kind=feature.kind,
            provenance=feature.provenance,
            params=feature.params,
            face_indices=feature.face_indices,
        )
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
    schlechter sein. Sonst ``None``.
    """
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
        feature = detected.get(identifier)
        if feature is None or feature.kind != kind:
            continue
        vector = feature_vector(feature, centre, diagonal)
        position = float(np.linalg.norm(reference[:3] - vector[:3])) / POSITION_TOLERANCE
        delta = float(np.linalg.norm(reference[3:6] - vector[3:6]))
        if not directional:
            # Dieselbe Regel wie in `cost`: was eine ``axis`` hat, ist eine
            # Linie und keine Richtung — +v und -v sind dasselbe Merkmal.
            delta = min(delta, float(np.linalg.norm(reference[3:6] + vector[3:6])))
        axis = delta / AXIS_TOLERANCE
        scale = max(abs(float(reference[6])), abs(float(vector[6])), EPS_GEOM)
        diameter = abs(float(reference[6]) - float(vector[6])) / scale / DIAMETER_TOLERANCE
        costs.append((float(position + axis + diameter), identifier))

    if not costs:
        return None
    costs.sort()
    best, winner = costs[0]
    if best > MATCH_THRESHOLD:
        return None
    limit = best * (1.0 + AMBIGUITY_MARGIN) + AMBIGUITY_FLOOR
    if any(value <= limit for value, identifier in costs[1:]):
        return None
    return winner


def moved_features(
    features: dict[FeatureId, Feature], transform: Transform
) -> dict[FeatureId, Feature]:
    """Nimmt Merkmale entlang einer starren Bewegung mit, die die Operation
    gemeldet hat (§21.2).

    Angefasst wird nur, was im Raum lebt: der Punkt, an dem ein Merkmal sitzt,
    und die Richtung, in die es zeigt. Ein Durchmesser bewegt sich nicht, und
    eine Fläche ist kein Ort. Ohne das verwaiste eine Drehung jedes Merkmal am
    Körper — nicht weil es verschwunden wäre, sondern weil es jetzt woanders
    ist.
    """
    matrix = np.asarray(transform, dtype=float)
    turn = matrix[:3, :3]
    moved: dict[FeatureId, Feature] = {}
    for identifier, feature in features.items():
        params = dict(feature.params)
        for key in ("centre", "position"):
            if key in params:
                point = np.asarray(params[key], dtype=float)
                carried = matrix @ np.array([*point, 1.0])
                params[key] = (float(carried[0]), float(carried[1]), float(carried[2]))
        for key in ("axis", "normal"):
            if key in params:
                direction = turn @ np.asarray(params[key], dtype=float)
                length = float(np.linalg.norm(direction))
                if length > EPS_GEOM:
                    direction = direction / length
                params[key] = (float(direction[0]), float(direction[1]), float(direction[2]))
        moved[identifier] = Feature(
            id=feature.id,
            kind=feature.kind,
            provenance=feature.provenance,
            params=params,
            face_indices=feature.face_indices,
        )
    return moved
