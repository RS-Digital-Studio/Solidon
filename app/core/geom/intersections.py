"""Selbstdurchdringung eines Netzes, als Feld gerechnet (§18.4, §24.3, RM-206).

**Eine Rechnung für zwei Fragen.** Die Netzfehlerkarte will wissen, *welche*
Dreiecke durch andere laufen (`repair.self_intersecting_faces`), der
Bereichstest eines Bausteins, *ob* überhaupt eines es tut
(`knowledge.parts.range_check.has_self_intersections`). Bis zum 22.09.2026
standen dafür zwei Fassungen nebeneinander: die der Karte als Feld über
Möller-Trumbore — schnell, aber blind für zwei Dreiecke, die **in derselben
Ebene** übereinanderliegen, und für jedes Paar, das sich eine Ecke teilt —, die
des Bereichstests vollständig, aber als Python-Schleife über die Kontakte
eines VTK-Filters: 632 ms für 352 Dreiecke, 1,5 s je Ecke am Schraubenloch.
Hier steht die eine vollständige Rechnung, und sie ist ein Feld.

Gerechnet wird in zwei Stufen:

* **Kandidaten** über Sweep-and-Prune, je nach Netz in Scheiben entlang einer
  zweiten Achse (:func:`_plan` wählt Achsen und Breite an einer Stichprobe) —
  ein Gewinde ist entlang seiner Achse lang und quer dazu rund, und entlang
  X gezählt träfe jeder Gang jeden anderen; ein Baum aus 166 000 Dreiecken
  überdeckt sich auf jeder Achse zu Hunderten. Die übrigen Achsen filtern
  danach als Feld. Nichts wird gekappt: Das
  Budget ``max_pairs`` gibt es nur für Karte und Reparatur, die ehrlich sagen,
  was sie gefunden haben; der Bereichstest prüft jedes Paar. **Gezählt werden
  die Paare nach diesem Filter** (Durchsicht 24.09.2026): Sie kosten die
  Rechenzeit, rund zwei Mikrosekunden je Paar. Die Rohpaare des Sweeps sagten
  darüber wenig — ein Besenhalter mit langen Splitterdreiecken brachte 22
  Millionen davon für 3,2 Millionen echte Kandidaten, ein Spiderman 49 für 6.
* **Das Paar selbst**, je Block als ``(m, 3, 3)``: Ecken beider Dreiecke, die
  innerhalb ``EPS_GEOM`` zusammenfallen, sind *ein* topologischer Punkt und
  werden auf ihre gemeinsame Mitte gelegt — eine gemeinsame Kante ist
  Nachbarschaft, keine Durchdringung. Dann die Ebenenseiten, und je nachdem,
  ob die Ebenen zusammenfallen:

  * **nicht koplanar:** die Schnittstrecken beider Dreiecke auf der
    Schnittgeraden ihrer Ebenen. Überdecken sie sich, ist das ein Schnitt —
    es sei denn, die Überdeckung liegt ganz in den gemeinsamen Punkten
    (Nachbarn an Kante oder Ecke).
  * **koplanar:** positive Flächenüberdeckung nach dem Trennachsensatz. Reiner
    Kanten- oder Eckkontakt hat auf einer Trennachse die Breite null und
    bleibt erlaubt; **zwei deckungsgleiche Dreiecke** mit eigenen Ecken sind
    dagegen der Fall, für den die Prüfung da ist — zwei Bausteinflächen, die
    an einer Ecke des Parameterbereichs aufeinanderfallen. Nur dieselbe
    Fläche mit denselben Eckennummern in anderer Reihenfolge ist eine
    doppelte Zelle und kein Schnitt.

Nullflächen haben keine Oberfläche, die etwas durchdringen könnte, und gehen
vorher heraus.

**Gerechnet wird ohne** ``np.einsum`` (RM-187): Ob ein Paar sich schneidet,
entscheidet über das Ergebnis einer Reparatur, und ``einsum`` darf auf ARM
mit FMA runden. Die Skalarprodukte stehen als Grundrechenarten
(:func:`_dot_rows`, :func:`_dot_grid`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Final

import numpy as np

from app.core.errors import OperationCancelled
from app.core.types import CancelToken
from app.core.units import EPS_GEOM

#: Wie viele Kandidatenpaare der Sweep höchstens auf einmal als Indexfeld
#: bildet, bevor die übrigen zwei Achsen filtern. Die Gesamtmenge bleibt
#: vollständig; begrenzt wird nur der Arbeitsspeicher.
SWEEP_PAIRS: Final = 1_000_000

#: Wie viele Paare die genaue Prüfung auf einmal als Feld rechnet — je Paar
#: stehen rund achtzig Gleitkommazahlen im Speicher.
PAIR_BLOCK: Final = 65_536


class _CancelledError(Exception):
    """Abbruch mitten in einer Stufe — die Aufrufer übersetzen ihn."""


def _dot_rows(points: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Je Paar ``k`` und Ecke ``v`` das Skalarprodukt ``points[k, v] · direction[k]``.

    ``points`` ist ``(k, v, 3)``, ``direction`` ``(k, 3)`` — elementweise, ohne
    BLAS und ohne ``einsum`` (RM-187).
    """
    return np.asarray(
        points[:, :, 0] * direction[:, None, 0]
        + points[:, :, 1] * direction[:, None, 1]
        + points[:, :, 2] * direction[:, None, 2]
    )


def _dot_grid(axes: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Je Paar ``k`` jede Achse ``e`` gegen jede Ecke ``v`` in der Ebene: ``(k, e, v)``."""
    return np.asarray(
        axes[:, :, None, 0] * points[:, None, :, 0] + axes[:, :, None, 1] * points[:, None, :, 1]
    )


@dataclass(frozen=True, slots=True)
class _Surface:
    """Die Dreiecke, die eine Fläche haben, mit dem, was jede Stufe braucht."""

    kept: np.ndarray
    """Nummern der verbliebenen Dreiecke im Eingangsnetz."""
    faces: np.ndarray
    triangles: np.ndarray
    low: np.ndarray
    high: np.ndarray


def _surface(vertices: np.ndarray, faces: np.ndarray) -> _Surface | None:
    """Das Netz ohne Nullflächen — oder ``None``, wenn nichts zu prüfen bleibt."""
    faces = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    vertices = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    if len(faces) < 2 or not len(vertices):
        return None
    triangles = vertices[faces]
    twice_area = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    )
    edge_lengths = np.linalg.norm(np.roll(triangles, -1, axis=1) - triangles, axis=2)
    longest = edge_lengths.max(axis=1)
    altitude = np.divide(twice_area, longest, out=np.zeros_like(twice_area), where=longest > 0.0)
    kept = np.flatnonzero((longest > EPS_GEOM) & (altitude > EPS_GEOM))
    if len(kept) < 2:
        return None
    triangles = triangles[kept]
    return _Surface(
        kept=kept,
        faces=faces[kept],
        triangles=triangles,
        low=triangles.min(axis=1),
        high=triangles.max(axis=1),
    )


def _check(cancelled: CancelToken | None) -> None:
    if cancelled is not None and cancelled.is_cancelled:
        raise _CancelledError


@dataclass(frozen=True, slots=True)
class _Plan:
    """Wie die Kandidaten gesucht werden: Sweep entlang ``axis``, wahlweise in Scheiben.

    Ohne ``bins`` ist es der einfache Sweep. Mit ``bins`` wird das Netz entlang
    dieser zweiten Achse in Scheiben der Breite ``width`` geteilt, jedes
    Dreieck in jede Scheibe, die sein Hüllquader berührt, und der Sweep läuft
    je Scheibe. Ein Paar zählt nur in der Scheibe, in der die untere Ecke
    seiner gemeinsamen Hülle liegt — so kommt keines doppelt heraus.
    """

    axis: int
    bins: int | None = None
    width: float = 0.0


@dataclass(frozen=True, slots=True)
class _Entries:
    """Die Einträge eines Plans, nach Scheibe und Anfang auf der Sweep-Achse sortiert."""

    triangle: np.ndarray
    slab: np.ndarray
    counts: np.ndarray
    """Je Eintrag, wie viele der folgenden Einträge seiner Scheibe er überdeckt."""
    origin: float


#: Ab wie vielen Dreiecken die Suche ihren Plan an einer Stichprobe wählt statt
#: am ganzen Netz. Darunter ist jeder Plan in Millisekunden gezählt.
PLAN_SAMPLE: Final = 30_000

#: Die Scheibenbreiten, die der Plan ausprobiert — als Vielfache des mittleren
#: Hüllmaßes auf der geteilten Achse.
SLAB_FACTORS: Final = (1.0, 2.0, 4.0, 8.0, 16.0)

#: Wie viel ein Eintrag gegenüber einem Kandidatenpaar kostet (Sortieren,
#: Suchen) — gemessen an den Netzen aus ``F:\3D Dateien``, gerundet.
ENTRY_WEIGHT: Final = 4.0

#: Größter Schlüssel ``Scheibe · Spannweite``, den die Suche noch als Gleitkommazahl
#: sortiert: darüber verlöre sie Bruchteile von ``EPS_GEOM``.
_MAX_KEY: Final = 2.0**40


def _entries(low: np.ndarray, high: np.ndarray, plan: _Plan) -> _Entries | None:
    """Die Einträge eines Plans — ``None``, wenn sein Schlüssel zu groß würde."""
    count = len(low)
    if plan.bins is None:
        triangle = np.arange(count)
        slab = np.zeros(count, dtype=np.int64)
        origin = 0.0
    else:
        axis = plan.bins
        origin = float(low[:, axis].min()) - EPS_GEOM
        first = np.floor((low[:, axis] - EPS_GEOM - origin) / plan.width).astype(np.int64)
        last = np.floor((high[:, axis] + EPS_GEOM - origin) / plan.width).astype(np.int64)
        span = last - first + 1
        triangle = np.repeat(np.arange(count), span)
        steps = np.arange(int(span.sum())) - np.repeat(np.cumsum(span) - span, span)
        slab = np.repeat(first, span) + steps
    axis = plan.axis
    base = float(low[:, axis].min())
    size = float(high[:, axis].max()) - base + 1.0
    if float(slab.max(initial=0) + 1) * size > _MAX_KEY:
        return None
    key = slab * size + (low[triangle, axis] - base)
    order = np.argsort(key, kind="stable")
    triangle, slab, key = triangle[order], slab[order], key[order]
    reach = np.searchsorted(
        key, slab * size + (high[triangle, axis] - base) + EPS_GEOM, side="right"
    )
    counts = np.maximum(reach - np.arange(len(key)) - 1, 0)
    return _Entries(triangle=triangle, slab=slab, counts=counts, origin=origin)


def _plan(low: np.ndarray, high: np.ndarray) -> _Plan:
    """Der Plan mit der geringsten geschätzten Arbeit.

    Ein langes Gewinde überdeckt sich quer zu seiner Achse Umlauf um Umlauf,
    ein Baum aus 166 000 Dreiecken auf jeder Achse zu Hunderten: Der einfache
    Sweep zählte dort 146 Millionen Paare für 1,3 Millionen echte Kandidaten.
    In Scheiben geteilt sind es 8 Millionen. Welche Achsen und welche Breite am
    wenigsten kosten, hängt am Netz; gezählt wird deshalb an einer festen
    Stichprobe (jedes ``k``-te Dreieck, kein Zufall), und die Schätzung rechnet
    Paare mit ``k²``, Einträge mit ``k`` hoch.
    """
    count = len(low)
    stride = max(1, count // PLAN_SAMPLE)
    sample_low, sample_high = low[::stride], high[::stride]
    plans = [_Plan(axis) for axis in range(3)]
    for axis in range(3):
        for bins in range(3):
            if bins == axis:
                continue
            middle = float(np.median(sample_high[:, bins] - sample_low[:, bins]))
            if middle <= EPS_GEOM:
                continue
            plans.extend(_Plan(axis, bins, middle * factor) for factor in SLAB_FACTORS)
    best: tuple[float, _Plan] | None = None
    for plan in plans:
        entries = _entries(sample_low, sample_high, plan)
        if entries is None:
            continue
        work = float(entries.counts.sum()) * stride * stride + (
            ENTRY_WEIGHT * len(entries.triangle) * stride
        )
        if best is None or work < best[0]:
            best = (work, plan)
    return best[1] if best is not None else _Plan(0)


@dataclass(slots=True)
class _Search:
    """Wie weit die Kandidatensuche kam — ``complete`` fällt nur mit ``max_pairs``.

    ``progress`` bekommt den Anteil der Sweep-Einträge, die schon durchlaufen
    sind — eine Zahl zwischen null und eins, je Block einmal. Endet die Suche
    vorzeitig, nennt ``unchecked`` die Dreiecke (Nummern der Oberfläche), deren
    Paare nicht alle geprüft sind; alle übrigen sind es.
    """

    max_pairs: int | None = None
    complete: bool = True
    progress: Callable[[float], None] | None = None
    unchecked: np.ndarray | None = None


def _candidates(
    surface: _Surface, cancelled: CancelToken | None, search: _Search, plan: _Plan | None = None
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Alle Paare, deren Hüllquader sich (bis auf ``EPS_GEOM``) überdecken, blockweise.

    Endet vorzeitig nur, wenn ``search.max_pairs`` gesetzt ist und die
    Sweep-Paare darüber hinausgehen — dann steht ``search.complete`` auf
    falsch, und die Antwort ist ehrlich unvollständig.
    """
    low, high = surface.low, surface.high
    plan = plan or _plan(low, high)
    entries = _entries(low, high, plan) or _entries(low, high, _Plan(plan.axis))
    assert entries is not None  # der einfache Sweep hat nur eine Scheibe
    others = [dimension for dimension in range(3) if dimension != plan.axis]
    counts = entries.counts
    total = np.cumsum(counts)
    overall = float(total[-1]) if len(total) else 0.0
    positions = np.arange(len(counts))
    counted = 0
    begin = 0
    while begin < len(counts):
        _check(cancelled)
        if search.progress is not None and overall > 0.0:
            search.progress(float(total[begin - 1]) / overall if begin else 0.0)
        # So viele Einträge, dass ihre Paare zusammen etwa SWEEP_PAIRS ergeben —
        # mindestens einer, auch wenn er allein mehr hat.
        before = int(total[begin - 1]) if begin else 0
        end = int(np.searchsorted(total, before + SWEEP_PAIRS, side="right"))
        end = min(max(end, begin + 1), len(counts))
        block = positions[begin:end]
        size = counts[begin:end]
        begin = end
        amount = int(size.sum())
        if not amount:
            continue
        left = np.repeat(block, size)
        steps = np.arange(amount) - np.repeat(np.cumsum(size) - size, size)
        right = left + 1 + steps
        first, second = entries.triangle[left], entries.triangle[right]
        apart = np.zeros(len(first), dtype=bool)
        for dimension in others:
            apart |= low[second, dimension] > high[first, dimension] + EPS_GEOM
            apart |= low[first, dimension] > high[second, dimension] + EPS_GEOM
        if plan.bins is not None:
            # Nur die Scheibe der unteren Ecke der gemeinsamen Hülle zählt.
            corner = np.maximum(low[first, plan.bins], low[second, plan.bins])
            home = np.floor((corner - entries.origin) / plan.width).astype(np.int64)
            apart |= home != entries.slab[left]
        first, second, left = first[~apart], second[~apart], left[~apart]
        if search.max_pairs is not None and counted + len(first) > search.max_pairs:
            search.complete = False
            # Die Paare stehen nach ihrem linken Eintrag geordnet. Geprüft wird
            # bis zum ersten Eintrag, dessen Paare nicht mehr alle ins Budget
            # passen; jedes Paar eines Eintrags steht bei ihm, und ein
            # Dreieck, dessen Einträge alle davor liegen, ist ganz geprüft.
            allowed = max(search.max_pairs - counted, 0)
            cut = int(left[allowed]) if allowed < len(left) else end
            keep = left < cut
            search.unchecked = np.unique(entries.triangle[cut:])
            first, second = first[keep], second[keep]
            for offset in range(0, len(first), PAIR_BLOCK):
                yield first[offset : offset + PAIR_BLOCK], second[offset : offset + PAIR_BLOCK]
            return
        counted += len(first)
        for offset in range(0, len(first), PAIR_BLOCK):
            yield first[offset : offset + PAIR_BLOCK], second[offset : offset + PAIR_BLOCK]


def _intervals_on_line(
    triangle: np.ndarray, distance: np.ndarray, direction: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Wo jedes Dreieck die Ebene des Partners schneidet, auf deren Schnittgerade projiziert.

    Eine Ecke gilt als *in* der Ebene, wenn ihr Abstand unter der numerischen
    Grenze ihres Dreiecks liegt; dazu kommt jede Kante mit echtem
    Vorzeichenwechsel. Ohne beides ist das Intervall leer (``inf``/``-inf``).
    """
    projection = _dot_rows(triangle, direction)
    span = np.linalg.norm(np.ptp(triangle, axis=1), axis=1)
    numeric = 64.0 * np.finfo(float).eps * np.maximum(1.0, span)
    low = np.full(len(triangle), np.inf)
    high = np.full(len(triangle), -np.inf)
    for vertex in range(3):
        on_plane = np.abs(distance[:, vertex]) <= numeric
        value = projection[:, vertex]
        low = np.where(on_plane, np.minimum(low, value), low)
        high = np.where(on_plane, np.maximum(high, value), high)
        following = (vertex + 1) % 3
        start_distance = distance[:, vertex]
        end_distance = distance[:, following]
        crossing = start_distance * end_distance < 0.0
        denominator = start_distance - end_distance
        fraction = np.divide(
            start_distance, denominator, out=np.zeros_like(start_distance), where=crossing
        )
        crossing_value = value + fraction * (projection[:, following] - value)
        low = np.where(crossing, np.minimum(low, crossing_value), low)
        high = np.where(crossing, np.maximum(high, crossing_value), high)
    return low, high


def coplanar_overlap(first: np.ndarray, second: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Positive Flächenüberdeckung gepaarter Dreiecke derselben Ebene (Trennachsen in 2D).

    Projiziert wird auf die Koordinatenebene, die der Normale am wenigsten
    fehlt. Eine Achse trennt, wenn die Projektionen sich um höchstens
    ``EPS_GEOM`` überdecken — Kanten- und Eckkontakt trennen also.
    """
    result = np.zeros(len(first), dtype=bool)
    dominant = np.argmax(np.abs(normal), axis=1)
    for dropped in range(3):
        selected = dominant == dropped
        if not np.any(selected):
            continue
        keep = [axis for axis in range(3) if axis != dropped]
        first_2d = first[selected][:, :, keep]
        second_2d = second[selected][:, :, keep]
        edges = np.concatenate(
            (
                np.roll(first_2d, -1, axis=1) - first_2d,
                np.roll(second_2d, -1, axis=1) - second_2d,
            ),
            axis=1,
        )
        axes = np.stack((-edges[:, :, 1], edges[:, :, 0]), axis=2)
        axis_length = np.linalg.norm(axes, axis=2)
        first_projection = _dot_grid(axes, first_2d)
        second_projection = _dot_grid(axes, second_2d)
        overlap = np.minimum(
            first_projection.max(axis=2), second_projection.max(axis=2)
        ) - np.maximum(first_projection.min(axis=2), second_projection.min(axis=2))
        result[selected] = np.all(overlap > EPS_GEOM * axis_length, axis=1)
    return result


def crossing_pairs(
    first: np.ndarray,
    second: np.ndarray,
    first_faces: np.ndarray,
    second_faces: np.ndarray,
    *,
    with_coplanar: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """Je Paar, ob die zwei Dreiecke einander über ihre gemeinsamen Punkte hinaus schneiden.

    ``first`` und ``second`` sind ``(m, 3, 3)``, ``*_faces`` die Eckennummern
    je Dreieck ``(m, 3)`` — nur für die doppelte Zelle gebraucht. Mit
    ``with_coplanar`` kommt daneben, welche Paare in derselben Ebene liegen:
    Eine deckungsgleiche Überlagerung löst die Reparatur, eine echte
    Eigenkreuzung einer Schale nicht.
    """
    count = len(first)
    hit = np.zeros(count, dtype=bool)
    flat = np.zeros(count, dtype=bool)
    if not count:
        return (hit, flat) if with_coplanar else hit
    # Ecken, die innerhalb der Geometrietoleranz zusammenfallen, sind ein
    # topologischer Punkt: beide Dreiecke bekommen dieselbe Darstellung.
    difference = first[:, :, None, :] - second[:, None, :, :]
    close = (
        difference[..., 0] * difference[..., 0]
        + difference[..., 1] * difference[..., 1]
        + difference[..., 2] * difference[..., 2]
    ) <= EPS_GEOM * EPS_GEOM
    first_matched = close.any(axis=2)
    second_matched = close.any(axis=1)
    partner = np.take_along_axis(second, close.argmax(axis=2)[:, :, None], axis=1)
    first = np.where(first_matched[:, :, None], (first + partner) / 2.0, first)
    partner = np.take_along_axis(first, close.argmax(axis=1)[:, :, None], axis=1)
    second = np.where(second_matched[:, :, None], partner, second)

    first_normal = np.cross(first[:, 1] - first[:, 0], first[:, 2] - first[:, 0])
    second_normal = np.cross(second[:, 1] - second[:, 0], second[:, 2] - second[:, 0])
    first_length = np.linalg.norm(first_normal, axis=1)
    second_length = np.linalg.norm(second_normal, axis=1)
    usable = (first_length > 0.0) & (second_length > 0.0)
    first_length = np.where(usable, first_length, 1.0)
    second_length = np.where(usable, second_length, 1.0)
    first_distance = (
        _dot_rows(first - second[:, 0, None, :], second_normal) / second_length[:, None]
    )
    second_distance = _dot_rows(second - first[:, 0, None, :], first_normal) / first_length[:, None]
    possible = usable & ~(
        np.all(first_distance > EPS_GEOM, axis=1)
        | np.all(first_distance < -EPS_GEOM, axis=1)
        | np.all(second_distance > EPS_GEOM, axis=1)
        | np.all(second_distance < -EPS_GEOM, axis=1)
    )
    direction = np.cross(first_normal, second_normal)
    direction_length = np.linalg.norm(direction, axis=1)
    coplanar = (direction_length <= EPS_GEOM * first_length * second_length) | (
        (np.max(np.abs(first_distance), axis=1) <= EPS_GEOM)
        & (np.max(np.abs(second_distance), axis=1) <= EPS_GEOM)
    )

    flat = possible & coplanar
    if np.any(flat):
        # Dieselbe Fläche mit denselben Eckennummern ist eine doppelte Zelle.
        same_cell = np.all(
            np.sort(first_faces[flat], axis=1) == np.sort(second_faces[flat], axis=1), axis=1
        )
        overlapping = coplanar_overlap(first[flat], second[flat], first_normal[flat])
        hit[np.flatnonzero(flat)] = overlapping & ~same_cell

    steep = np.flatnonzero(possible & ~coplanar)
    if not len(steep):
        return (hit, flat) if with_coplanar else hit
    unit = direction[steep] / direction_length[steep, None]
    first_low, first_high = _intervals_on_line(first[steep], first_distance[steep], unit)
    second_low, second_high = _intervals_on_line(second[steep], second_distance[steep], unit)
    low = np.maximum(first_low, second_low)
    high = np.minimum(first_high, second_high)
    crossing = np.isfinite(low) & np.isfinite(high) & (high >= low - EPS_GEOM)
    steep, low, high, unit = steep[crossing], low[crossing], high[crossing], unit[crossing]

    # Was die beiden Dreiecke teilen, liegt auf der Schnittgeraden: Eine
    # Überdeckung, die ganz darin liegt, ist Nachbarschaft.
    shared = first_matched[steep]
    projection = _dot_rows(first[steep], unit)
    shared_low = np.min(np.where(shared, projection, np.inf), axis=1)
    shared_high = np.max(np.where(shared, projection, -np.inf), axis=1)
    point = high - low <= EPS_GEOM
    middle = (high + low) / 2.0
    point_elsewhere = np.all(~shared | (np.abs(projection - middle[:, None]) > EPS_GEOM), axis=1)
    reaches_past = (low < shared_low - EPS_GEOM) | (high > shared_high + EPS_GEOM)
    beyond = np.where(point, point_elsewhere, reaches_past)
    hit[steep] = np.where(shared.any(axis=1), beyond, True)
    return (hit, flat) if with_coplanar else hit


def _pairs_that_cross(
    surface: _Surface, cancelled: CancelToken | None, search: _Search
) -> Iterator[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Je Kandidatenblock die Paare, die sich wirklich schneiden (Nummern im Netz),
    und welche davon in derselben Ebene liegen."""
    for first, second in _candidates(surface, cancelled, search):
        _check(cancelled)
        crossed, coplanar = crossing_pairs(
            surface.triangles[first],
            surface.triangles[second],
            surface.faces[first],
            surface.faces[second],
            with_coplanar=True,
        )
        if np.any(crossed):
            yield surface.kept[first[crossed]], surface.kept[second[crossed]], coplanar[crossed]


def intersects(
    vertices: np.ndarray, faces: np.ndarray, cancelled: CancelToken | None = None
) -> bool:
    """Ob irgendein Dreieck ein anderes über ihre gemeinsamen Punkte hinaus schneidet.

    Vollständig — jedes Paar mit überdeckenden Hüllquadern wird geprüft — und
    beim ersten Treffer fertig. Ein Abbruch wirft ``OperationCancelled``.
    """
    surface = _surface(vertices, faces)
    if surface is None:
        return False
    try:
        for _found in _pairs_that_cross(surface, cancelled, _Search()):
            return True
    except _CancelledError:
        raise OperationCancelled from None
    return False


@dataclass(frozen=True, slots=True)
class Crossings:
    """Die Paare, die sich schneiden, und ob die Suche alles gesehen hat.

    ``first`` und ``second`` nennen die Dreiecke im Eingangsnetz, ``coplanar``
    je Paar, ob beide in derselben Ebene liegen.
    """

    first: np.ndarray
    second: np.ndarray
    coplanar: np.ndarray
    complete: bool
    checked: np.ndarray | None = None
    """Je Dreieck des Eingangs, ob alle seine Paare geprüft sind — ``None``,
    wenn die Suche vollständig war. Nullflächen gelten als geprüft: Sie
    können nichts durchdringen."""

    @property
    def faces(self) -> tuple[int, ...]:
        """Die Dreiecke, die an einem der Paare beteiligt sind, aufsteigend."""
        return tuple(int(index) for index in np.unique(np.concatenate([self.first, self.second])))


def crossing_face_pairs(
    vertices: np.ndarray,
    faces: np.ndarray,
    cancelled: CancelToken | None = None,
    *,
    max_pairs: int | None = None,
    progress: Callable[[float], None] | None = None,
) -> Crossings:
    """Die Paare, die sich schneiden — und ob die Suche vollständig war.

    ``max_pairs`` begrenzt die Kandidaten nach dem Achsenfilter; darüber endet
    die Suche und meldet mit ``complete=False``, dass sie nicht alles gesehen
    hat. Was sie bis dahin gefunden hat, schneidet wirklich. ``progress``
    bekommt je Block den durchlaufenen Anteil.
    """
    empty = np.zeros(0, dtype=np.int64)
    surface = _surface(vertices, faces)
    if surface is None:
        return Crossings(empty, empty, np.zeros(0, dtype=bool), True)
    firsts: list[np.ndarray] = []
    seconds: list[np.ndarray] = []
    flats: list[np.ndarray] = []
    search = _Search(max_pairs=max_pairs, progress=progress)
    try:
        for first, second, coplanar in _pairs_that_cross(surface, cancelled, search):
            firsts.append(first)
            seconds.append(second)
            flats.append(coplanar)
    except _CancelledError:
        raise OperationCancelled from None
    checked: np.ndarray | None = None
    if search.unchecked is not None:
        checked = np.ones(len(np.asarray(faces).reshape(-1, 3)), dtype=bool)
        checked[surface.kept[search.unchecked]] = False
    if not firsts:
        return Crossings(empty, empty, np.zeros(0, dtype=bool), search.complete, checked)
    return Crossings(
        np.concatenate(firsts).astype(np.int64),
        np.concatenate(seconds).astype(np.int64),
        np.concatenate(flats),
        search.complete,
        checked,
    )


def crossing_faces(
    vertices: np.ndarray,
    faces: np.ndarray,
    cancelled: CancelToken | None = None,
    *,
    max_pairs: int | None = None,
) -> tuple[tuple[int, ...], bool]:
    """Die Dreiecke, die ein anderes schneiden — und ob die Suche vollständig war.

    Die Kurzform von :func:`crossing_face_pairs` für die, die nur die Dreiecke
    brauchen.
    """
    found = crossing_face_pairs(vertices, faces, cancelled, max_pairs=max_pairs)
    return found.faces, found.complete
