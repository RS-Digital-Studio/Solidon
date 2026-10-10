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

Gerechnet wird in drei Stufen:

* **Kandidaten** über Sweep-and-Prune, je nach Netz in Scheiben entlang einer
  zweiten Achse (:func:`_plan` wählt Achsen und Breite an einer Stichprobe) —
  ein Gewinde ist entlang seiner Achse lang und quer dazu rund, und entlang
  X gezählt träfe jeder Gang jeden anderen; ein Baum aus 166 000 Dreiecken
  überdeckt sich auf jeder Achse zu Hunderten. Die übrigen Achsen filtern
  danach als Feld. Nichts wird gekappt: Das
  Budget ``max_pairs`` gibt es nur für Karte und Reparatur, die ehrlich sagen,
  was sie gefunden haben; der Bereichstest prüft jedes Paar. **Gezählt wird
  in genauen Prüfungen** (Durchsicht 24.09.2026, RM-244): Sie kosten die
  Rechenzeit, rund zwei Mikrosekunden je Paar. Die Rohpaare des Sweeps sagten
  darüber wenig — ein Besenhalter mit langen Splitterdreiecken brachte 22
  Millionen davon für 3,2 Millionen echte Kandidaten, ein Spiderman 49 für 6.
* **Die Trennprüfung** (:func:`_separated`) verwirft, was eine Ebene oder in
  der Draufsicht eine Kante mit Abstand trennt, und kostet dafür einen
  Bruchteil (:data:`SEPARATION_COST`). Am
  Besenhalter trennt sie 92 Prozent der Kandidaten — Nadeln desselben
  ebenen Fächers, die sich nur an der Nabe berühren —, und die Suche kommt
  unter dem Budget ans Ende; an einem organischen Netz teilen fast alle
  Kandidaten eine Ecke und stehen schräg, und dort trennt die Nachbarprüfung
  (:func:`_touching_apart`) die meisten, ohne dass das Budget weiter reicht.
* **Das Paar selbst**, je Block als ``(m, 3, 3)``: Ecken beider Dreiecke, die
  innerhalb ``EPS_GEOM`` zusammenfallen, sind *ein* topologischer Punkt und
  werden auf ihre gemeinsame Mitte gelegt. Ein Eckpunkt, der auf einer Kante
  des anderen Dreiecks liegt, ist ebenfalls gemeinsam — auch bei abweichender
  Unterteilung bleibt ein Kantenkontakt Nachbarschaft. Dann die Ebenenseiten,
  und je nachdem, ob die Ebenen zusammenfallen:

  * **nicht koplanar:** die Schnittstrecken beider Dreiecke auf der
    Schnittgeraden ihrer Ebenen. Überdecken sie sich, ist das ein Schnitt —
    es sei denn, die Überdeckung liegt ganz auf einer gemeinsamen Kante oder
    besteht nur aus einem gemeinsamen Eckpunkt.
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
    normal: np.ndarray
    """Je Dreieck das Kreuzprodukt seiner Kanten, wie :func:`crossing_pairs` es bildet."""
    normal_length: np.ndarray
    margin: float
    """Der Abstand, ab dem :func:`_separated` zwei Dreiecke getrennt nennt."""


def _surface(vertices: np.ndarray, faces: np.ndarray) -> _Surface | None:
    """Das Netz ohne Nullflächen — oder ``None``, wenn nichts zu prüfen bleibt."""
    faces = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    vertices = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    if len(faces) < 2 or not len(vertices):
        return None
    triangles = vertices[faces]
    normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    twice_area = np.linalg.norm(normal, axis=1)
    # Die längste Kante Kante für Kante — dieselben Differenzen und Normen wie
    # über ``np.roll`` des ganzen Feldes, ohne zwei Kopien aller Ecken zugleich
    # (je 72 Byte je Dreieck): An sehr großen Netzen setzte das die Spitze
    # dieses Abschnitts (RM-568).
    longest = np.linalg.norm(triangles[:, 1] - triangles[:, 0], axis=1)
    for corner in (1, 2):
        np.maximum(
            longest,
            np.linalg.norm(triangles[:, (corner + 1) % 3] - triangles[:, corner], axis=1),
            out=longest,
        )
    altitude = np.divide(twice_area, longest, out=np.zeros_like(twice_area), where=longest > 0.0)
    kept = np.flatnonzero((longest > EPS_GEOM) & (altitude > EPS_GEOM))
    if len(kept) < 2:
        return None
    triangles = triangles[kept]
    span = float(np.linalg.norm(np.ptp(triangles, axis=1), axis=1).max())
    return _Surface(
        kept=kept,
        faces=faces[kept],
        triangles=triangles,
        low=triangles.min(axis=1),
        high=triangles.max(axis=1),
        normal=normal[kept],
        normal_length=twice_area[kept],
        margin=2.0 * EPS_GEOM + 4.0 * float(_numeric(span)) / EPS_GEOM,
    )


def _numeric(span: float | np.ndarray) -> np.ndarray:
    """Ab welchem Abstand eine Ecke nicht mehr *in* der Ebene des Partners liegt.

    Die Grenze aus :func:`_intervals_on_line`, für ein Dreieck der Diagonale
    ``span``. Die Schnittgerade wird auf einen gemeinsamen Ursprung bezogen,
    damit große Weltkoordinaten diese Grenze nicht aufblasen.
    """
    return np.asarray(64.0 * np.finfo(float).eps * np.maximum(1.0, span))


def _half_ulp(values: np.ndarray) -> np.ndarray:
    """Die halbe Float64-Schrittweite je gespeicherter Koordinate."""
    return 0.5 * np.abs(np.spacing(values))


def _point_on_line_with_rounding(
    point: np.ndarray, start: np.ndarray, end: np.ndarray
) -> np.ndarray:
    """Prüft Kollinearität mit projizierter Rundung der drei gespeicherten Punkte."""
    direction = end - start
    relative = point - start
    direction_squared = (
        direction[:, 0] * direction[:, 0]
        + direction[:, 1] * direction[:, 1]
        + direction[:, 2] * direction[:, 2]
    )
    numerator = (
        relative[:, 0] * direction[:, 0]
        + relative[:, 1] * direction[:, 1]
        + relative[:, 2] * direction[:, 2]
    )
    parameter = np.divide(
        numerator,
        direction_squared,
        out=np.zeros_like(numerator),
        where=direction_squared > 0.0,
    )
    residual = relative - parameter[:, None] * direction
    local_span = np.linalg.norm(relative, axis=1) + np.abs(parameter) * np.linalg.norm(
        direction, axis=1
    )
    input_rounding = (
        _half_ulp(point)
        + np.abs(1.0 - parameter[:, None]) * _half_ulp(start)
        + np.abs(parameter[:, None]) * _half_ulp(end)
        + _half_ulp(relative)
        + np.abs(parameter[:, None]) * _half_ulp(direction)
    )
    direction_length = np.sqrt(np.where(direction_squared > 0.0, direction_squared, 1.0))
    unit = direction / direction_length[:, None]
    projection_rounding = np.abs(np.eye(3)[None, :, :] - unit[:, :, None] * unit[:, None, :])
    bound = _dot_rows(projection_rounding, input_rounding)
    bound += _numeric(local_span)[:, None]
    return np.asarray(
        (direction_squared > 0.0) & np.all(np.abs(residual) <= bound, axis=1),
        dtype=bool,
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


def _keys(
    low: np.ndarray, high: np.ndarray, plan: _Plan
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float] | None:
    """Je Eintrag eines Plans Dreieck, Scheibe, Anfang und Ende auf der Sweep-Achse.

    Ungeordnet, in der Folge der Dreiecke und je Dreieck seiner Scheiben; das
    Ende trägt schon ``EPS_GEOM``. ``None``, wenn der Schlüssel zu groß würde.

    Die Felder je Eintrag sind die größten der Suche (am Mausoleumsdrachen 4,6
    Millionen Einträge). Deshalb entsteht jedes ohne Zwischenfeld gleicher
    Länge: die Scheibe als eine Wiederholung plus der Platz, Anfang und Ende
    am Ort summiert — dieselben Ganzzahlen und dieselben Additionen in
    derselben Folge wie ``slab * size + (low - base) + EPS_GEOM`` (RM-568).
    """
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
        # Die erste Scheibe des Dreiecks und dahinter je Eintrag eine mehr.
        slab = np.repeat(first - (np.cumsum(span) - span), span)
        slab += np.arange(len(slab))
        del first, last, span
    axis = plan.axis
    base = float(low[:, axis].min())
    size = float(high[:, axis].max()) - base + 1.0
    if float(slab.max(initial=0) + 1) * size > _MAX_KEY:
        return None
    key = slab * size
    key += low[triangle, axis] - base
    end = slab * size
    end += high[triangle, axis] - base
    end += EPS_GEOM
    return triangle, slab, key, end, origin


def _entries(low: np.ndarray, high: np.ndarray, plan: _Plan) -> _Entries | None:
    """Die Einträge eines Plans — ``None``, wenn sein Schlüssel zu groß würde.

    Jedes Zwischenfeld geht, sobald es nicht mehr gebraucht wird, und die Zahl
    der überdeckten Einträge entsteht am Ort: Gehalten blieben sonst die
    ungeordneten Felder neben den geordneten, und am Mausoleumsdrachen lag die
    Spitze der ganzen Suche hier (RM-568).
    """
    keys = _keys(low, high, plan)
    if keys is None:
        return None
    triangle, slab, key, end, origin = keys
    del keys
    order = np.argsort(key, kind="stable")
    key = key[order]
    end = end[order]
    reach = np.searchsorted(key, end, side="right")
    del key, end
    triangle = triangle[order]
    slab = slab[order]
    del order
    # ``max(reach - Platz - 1, 0)``, am Ort gerechnet.
    counts = reach
    counts -= np.arange(len(counts))
    counts -= 1
    np.maximum(counts, 0, out=counts)
    return _Entries(triangle=triangle, slab=slab, counts=counts, origin=origin)


def _pair_count(low: np.ndarray, high: np.ndarray, plan: _Plan) -> tuple[int, int] | None:
    """Wie viele Sweep-Paare und Einträge ein Plan bildet — die Paare als Summe
    der ``counts`` von :func:`_entries`, ohne die Einträge zu ordnen.

    Ein Eintrag überdeckt die Einträge hinter ihm bis zu seinem Ende, und sein
    Ende liegt nie vor seinem Anfang (Rundung ist monoton, ``EPS_GEOM`` nicht
    negativ): Das Ende findet in den geordneten Anfängen mindestens den Platz
    hinter dem Eintrag selbst. Die Summe der ``counts`` ist darum die Summe
    dieser Plätze weniger ``1 + 2 + … + n``, und die hängt nicht an der Folge.
    Der Plan wählt so dieselbe Teilung; das stabile Ordnen der Einträge
    kostete die Wahl am Laptop-Ständer zwei Drittel ihrer Zeit (RM-568).
    """
    keys = _keys(low, high, plan)
    if keys is None:
        return None
    _triangle, _slab, key, end, _origin = keys
    count = len(key)
    reach = np.searchsorted(np.sort(key), end, side="right")
    return int(reach.sum()) - count * (count + 1) // 2, count


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
        counted = _pair_count(sample_low, sample_high, plan)
        if counted is None:
            continue
        pairs, entries = counted
        work = float(pairs) * stride * stride + ENTRY_WEIGHT * entries * stride
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


#: Was die Trennprüfung eines Paares (:func:`_separated`) gegenüber der
#: genauen Prüfung kostet, wenn sie es ganz durchläuft. Das Budget zählt in
#: genauen Prüfungen: Ein Paar, das die Trennprüfung ganz durchläuft, kostet
#: diesen Anteil, eines, das sie danach durchlässt, dazu eine ganze. Gemessen
#: am 25.09.2026 an Besenhalter, Spiderman und Mausoleumsdrachen: 0,39 bis
#: 0,49 der genauen Prüfung allein. Aufgerundet auf Achtel, damit die Summe
#: der Kosten ohne Rundung läuft — sie entscheidet, wo das Budget endet.
#:
#: **Der Nummernvergleich allein kostet nichts extra.** Ein Paar mit
#: gemeinsamer Ecke, schräg zueinander — die Nachbarn eines organischen
#: Netzes —, entscheidet er sofort, und es kostet eine genaue Prüfung wie
#: vorher: Er braucht ein Zehntel davon, und die genaue Prüfung legt gleiche
#: Ecken seither nicht mehr zusammen, was ein Fünftel kostete (Spiderman
#: 2,45 µs vorher, 2,2 µs mit Vergleich). Gebucht mit einem eigenen Anteil,
#: prüfte die Netzfehlerkarte dort in derselben Zeit acht Prozent weniger.
SEPARATION_COST: Final = 0.5


def _separated(
    surface: _Surface, first: np.ndarray, second: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Welche Kandidatenpaare beweisbar nicht schneiden, ohne die genaue Prüfung.

    Dazu je Paar, was es das Budget kostet, ohne die genaue Prüfung der
    Paare, die offen bleiben: :data:`SEPARATION_COST` für die ganze
    Trennprüfung, null für die, die schon der Nummernvergleich entscheidet,
    und eine ganze genaue Prüfung für schräge Nachbarn, die
    :func:`_touching_apart` trennt — so viel kosteten sie, als sie noch durch
    die genaue Prüfung gingen, und das Budget endet damit an derselben Stelle
    wie vorher.

    Befund RM-244 (25.09.2026): Am Besenhalter mit seinen Nadeldreiecken
    überdecken sich 3,2 Millionen Hüllquader — 57 Prozent davon in derselben
    Ebene, 36 Prozent mit gemeinsamer Ecke —, die genaue Prüfung kostete zwei
    bis drei Mikrosekunden je Paar, und das Budget endete nach 35 648 der
    59 740 Dreiecke. Fast alle Paare liegen offensichtlich auseinander: Sie trennt
    eine Ebene oder eine Gerade, mit Abstand.

    Getrennt heißt hier, mit ``surface.margin`` Abstand:

    * **durch eine Ebene** — alle Ecken des einen Dreiecks auf derselben Seite
      der Ebene des anderen; nur ohne gemeinsame Ecke, denn die liegt in
      beiden Ebenen;
    * **durch eine Kante in der Draufsicht** — in der Projektion, die
      :func:`coplanar_overlap` für das erste Dreieck wählt, liegen quer zu
      einer der sechs Kanten alle Ecken des einen Dreiecks jenseits des
      Projektionsintervalls des anderen, dem die Kante gehört. Eine Ecke, die
      beide Dreiecke unter derselben Nummer tragen, darf dabei auf dem Rand des
      Intervalls liegen — aber nur, wenn die Ebenen parallel sind. Gemessen
      wird gegen den Eigner der Kante: Zwei Nadeln eines Fächers teilen die
      Nabe, und auf der Kante der zweiten liegt deren eigene Ecke auf der
      Trenngeraden.

    **Warum das nie einen Treffer verwirft.** Bei mehr als ``2·EPS_GEOM``
    Abstand fällt keine Ecke mit einer des Partners zusammen — die Projektion
    verkürzt keinen Abstand —, und :func:`crossing_pairs` rechnet mit den
    Koordinaten, wie sie sind. Die Ebenentrennung verwirft es dort selbst. In
    derselben Ebene ist die gefundene Kante eine seiner sechs Trennachsen, und
    auf ihr überdecken sich die beiden höchstens um einen halben ``EPS_GEOM``
    — ein Treffer verlangt auf jeder Achse mehr als einen ganzen. Schräg
    zueinander lägen beide Schnittstrecken auf der Schnittgeraden, und eine
    Überdeckung dort hieße zwei Punkte näher als ``EPS_GEOM``. Der Rest von
    ``margin`` deckt die Ecken, die die genaue Prüfung mit ihrer Rechengrenze
    (:func:`_numeric`) in die Ebene des Partners legt: Sie liegen bis zu
    ``numeric / EPS_GEOM`` neben der Schnittgeraden, denn schräg heißt dort
    ein Winkel mit Sinus über ``EPS_GEOM``.

    **Eine gemeinsame Ecke nur in derselben Ebene.** Schräg zueinander schließt
    sich der Abstand zur Trenngeraden an der gemeinsamen Ecke, und dort
    entscheidet die genaue Prüfung mit ihren Toleranzen — kein fester Abstand
    hält dagegen. In derselben Ebene entscheidet der Trennachsensatz, und auf
    der gefundenen Achse ist die Überdeckung null. Eine Nummer und nicht die
    Lage: Nur dieselbe Nummer sind sicher dieselben Koordinaten.

    Gerechnet wird elementweise (RM-187): Welche Paare getrennt heißen,
    entscheidet, wo das Budget endet.
    """
    # Welche Ecken des einen Dreiecks das andere unter derselben Nummer trägt.
    same = surface.faces[second][:, :, None] == surface.faces[first][:, None, :]
    other_shared = same.any(axis=2)
    count = other_shared.sum(axis=1)
    result = np.zeros(len(first), dtype=bool)
    margin = surface.margin
    # Ohne gemeinsame Ecke zuerst die Ebenen; mit einer kann keine trennen.
    alone = np.flatnonzero(count == 0)
    if len(alone):
        # Die Ebene des zweiten fragt nur, wen die des ersten nicht trennt —
        # jede Zahl entsteht wie zuvor, nur für weniger Paare (RM-568).
        one, other = surface.triangles[first[alone]], surface.triangles[second[alone]]
        other_side = (
            _dot_rows(other - one[:, 0, None, :], surface.normal[first[alone]])
            / (surface.normal_length[first[alone], None])
        )
        by_plane = np.all(other_side > margin, axis=1) | np.all(other_side < -margin, axis=1)
        open_rows = np.flatnonzero(~by_plane)
        if len(open_rows):
            partner = second[alone[open_rows]]
            one, other = one[open_rows], other[open_rows]
            one_side = (
                _dot_rows(one - other[:, 0, None, :], surface.normal[partner])
                / (surface.normal_length[partner, None])
            )
            by_plane[open_rows] = np.all(one_side > margin, axis=1) | np.all(
                one_side < -margin, axis=1
            )
        result[alone[by_plane]] = True
        alone = alone[~by_plane]
    # Mit gemeinsamer Ecke: schräg zueinander die Nachbarprüfung der örtlichen
    # Suche (:func:`_touching_apart`, RM-419), in derselben Ebene die
    # Draufsicht unten. Was die Nachbarprüfung trennt, kostet das Budget eine
    # genaue Prüfung — so viel wie vorher, als es noch durch sie ging; das
    # Budget endet damit an derselben Stelle (RM-568). Gemessen am
    # Laptop-Riser (08.10.2026): 1,29 Millionen offene Paare, fast alle
    # Nachbarn eines geschlossenen Netzes, und die genaue Prüfung kostete zwei
    # Drittel der Selbstschnittsuche vor dem Booleschen Abziehen.
    touching = np.flatnonzero((count == 1) | (count == 2))
    charged = np.zeros(len(first), dtype=bool)
    if len(touching):
        apart, tilt = _touching_apart_tilted(
            surface, first[touching], second[touching], np.swapaxes(same[touching], 1, 2)
        )
        result[touching[apart]] = True
        charged[touching[apart]] = True
        parallel = tilt <= (
            0.5
            * EPS_GEOM
            * surface.normal_length[first[touching]]
            * surface.normal_length[second[touching]]
        )
        touching = touching[parallel]
    rest = np.concatenate((alone, touching))
    searched = np.zeros(len(first), dtype=bool)
    searched[count == 0] = True
    searched[touching] = True
    cost = np.where(searched, SEPARATION_COST, 0.0) + charged
    if not len(rest):
        return result, cost
    # Die Draufsicht von coplanar_overlap: die Achse weg, die der Normale des
    # ersten am nächsten liegt.
    dominant = np.argmax(np.abs(surface.normal[first[rest]]), axis=1)
    drop_x, drop_z = (dominant == 0)[:, None], (dominant == 2)[:, None]

    def flat(triangle: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        across = np.where(drop_x, triangle[:, :, 1], triangle[:, :, 0])
        up = np.where(drop_z, triangle[:, :, 1], triangle[:, :, 2])
        return across, up

    one_across, one_up = flat(surface.triangles[first[rest]])
    other_across, other_up = flat(surface.triangles[second[rest]])
    split = _beyond_an_edge(
        (one_across, one_up), (other_across, other_up), other_shared[rest], margin
    )
    left = np.flatnonzero(~split)
    split[left] = _beyond_an_edge(
        (other_across[left], other_up[left]),
        (one_across[left], one_up[left]),
        same[rest[left]].any(axis=1),
        margin,
    )
    result[rest] = split
    return result, cost


def _beyond_an_edge(
    owner: tuple[np.ndarray, np.ndarray],
    foreign: tuple[np.ndarray, np.ndarray],
    touching: np.ndarray,
    margin: float,
) -> np.ndarray:
    """Ob quer zu einer Kante des Eigners das andere Dreieck ganz jenseits liegt.

    Beide Dreiecke in der Draufsicht als ``(quer, hoch)`` je Ecke. Je Kante
    liegt der Eigner zwischen ``low`` und ``high``; das andere muss um
    ``margin`` darüber oder darunter liegen, und eine gemeinsame Ecke
    (``touching``) darf auf dem Rand liegen — bis auf einen halben
    ``EPS_GEOM``: Die Ecken einer Kante liegen nur rechnerisch auf einer Höhe,
    bis auf die letzte Stelle, und ein Treffer verlangt auf jeder Achse mehr
    als einen ganzen (:func:`coplanar_overlap`).
    """
    owner_across, owner_up = owner
    foreign_across, foreign_up = foreign
    found = np.zeros(len(owner_across), dtype=bool)
    for edge in range(3):
        following = (edge + 1) % 3
        edge_across = owner_across[:, following] - owner_across[:, edge]
        edge_up = owner_up[:, following] - owner_up[:, edge]
        own = -edge_up[:, None] * owner_across + edge_across[:, None] * owner_up
        other = -edge_up[:, None] * foreign_across + edge_across[:, None] * foreign_up
        length = np.sqrt(edge_across * edge_across + edge_up * edge_up)[:, None]
        gap, slack = margin * length, 0.5 * EPS_GEOM * length
        high = own.max(axis=1, keepdims=True)
        low = own.min(axis=1, keepdims=True)
        found |= np.all((other > high + gap) | (touching & (other >= high - slack)), axis=1)
        found |= np.all((other < low - gap) | (touching & (other <= low + slack)), axis=1)
    return found


def _candidates(
    surface: _Surface,
    cancelled: CancelToken | None,
    search: _Search,
    plan: _Plan | None = None,
    *,
    separate: bool = False,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Alle Paare, deren Hüllquader sich (bis auf ``EPS_GEOM``) überdecken, blockweise.

    Endet vorzeitig nur, wenn ``search.max_pairs`` gesetzt ist und die
    Sweep-Paare darüber hinausgehen — dann steht ``search.complete`` auf
    falsch, und die Antwort ist ehrlich unvollständig. Mit ``separate``
    fallen die Paare weg, die :func:`_separated` trennt, und das Budget zählt
    nach :data:`SEPARATION_COST`.
    """
    low, high = surface.low, surface.high
    plan = plan or _plan(low, high)
    entries = _entries(low, high, plan) or _entries(low, high, _Plan(plan.axis))
    assert entries is not None  # der einfache Sweep hat nur eine Scheibe
    others = [dimension for dimension in range(3) if dimension != plan.axis]
    counts = entries.counts
    total = np.cumsum(counts)
    overall = float(total[-1]) if len(total) else 0.0
    # Plätze in 32 Bit, solange sie hineinpassen: Die Paarfelder sind die
    # größten der Suche, und halb so breit liest und schreibt sie halb so viel.
    places = np.int32 if len(counts) < 2**31 else np.int64
    # **Je Block, was seine Paare fragen, in der Folge der Einträge**
    # (RM-568): Die Grenzen der beiden übrigen Achsen und die Heimatscheibe
    # liegen für die Einträge vom ersten des Blocks bis zum letzten Partner
    # als zusammenhängende Felder da, und ein Paar liest sie über die Plätze
    # seiner Einträge in diesem Fenster statt über die Dreiecksnummern aus den
    # Hüllquadern. Der linke Eintrag eines Blocks wiederholt sich, also
    # wiederholt er auch seine Werte, statt sie je Paar zu lesen. Jeder
    # Vergleich bleibt derselbe Ausdruck auf denselben Zahlen. Die Heimat der
    # gemeinsamen Hülle ist ``floor((max(a, b) - origin) / width)`` — das ist
    # das Größere der Heimaten beider Dreiecke, denn Abziehen, Teilen durch
    # eine positive Breite und Abrunden sind in Gleitkommarechnung monoton.
    # Am Laptop-Ständer bildet der Sweep 51,6 Millionen Paare für 3,6 Millionen
    # Kandidaten, und das Bilden kostete die Hälfte der Suche. Für die ganze
    # Suche gehalten, kosteten die Felder 40 Byte je Eintrag und hoben an
    # ``dense_1m.stl`` (2,5 Millionen Einträge) die Spitze der Suche über die
    # von vorher, 509 statt 454 MB; je Fenster sind es meist wenige Megabyte.
    order = entries.triangle
    counted = 0.0
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
        start, size = begin, counts[begin:end]
        begin = end
        amount = int(size.sum())
        if not amount:
            continue
        # Plätze im Fenster: der Block vorn, dahinter die Partner bis zum letzten.
        block = np.arange(end - start, dtype=places)
        window = order[start : start + int((block + size).max()) + 1]
        left: np.ndarray = np.repeat(block, size)
        right: np.ndarray = np.arange(amount, dtype=places) + np.repeat(
            block + 1 - (np.cumsum(size) - size).astype(places), size
        )
        apart = np.zeros(amount, dtype=bool)
        for dimension in others:
            lows = low[window, dimension]
            reaches = high[window, dimension] + EPS_GEOM
            apart |= lows[right] > np.repeat(reaches[: end - start], size)
            apart |= np.repeat(lows[: end - start], size) > reaches[right]
        if plan.bins is not None:
            # Nur die Scheibe der unteren Ecke der gemeinsamen Hülle zählt.
            home = np.floor((low[window, plan.bins] - entries.origin) / plan.width).astype(np.int64)
            apart |= np.maximum(np.repeat(home[: end - start], size), home[right]) != np.repeat(
                entries.slab[start:end], size
            )
        near = ~apart
        left, right = left[near] + start, right[near] + start
        first, second = order[left], order[right]
        open_pairs: np.ndarray | None = None
        cost: np.ndarray | None = None
        if separate:
            open_pairs = np.ones(len(first), dtype=bool)
            cost = np.zeros(len(first))
            for offset in range(0, len(first), PAIR_BLOCK):
                piece = slice(offset, offset + PAIR_BLOCK)
                separated, charge = _separated(surface, first[piece], second[piece])
                open_pairs[piece] = ~separated
                cost[piece] = charge
            cost += open_pairs
        spent = float(cost.sum()) if cost is not None else float(len(first))
        if search.max_pairs is not None and counted + spent > search.max_pairs:
            search.complete = False
            # Die Paare stehen nach ihrem linken Eintrag geordnet. Geprüft wird
            # bis zum ersten Eintrag, dessen Paare nicht mehr alle ins Budget
            # passen; jedes Paar eines Eintrags steht bei ihm, und ein
            # Dreieck, dessen Einträge alle davor liegen, ist ganz geprüft.
            allowed = max(search.max_pairs - counted, 0.0)
            fitting = (
                int(np.searchsorted(np.cumsum(cost), allowed, side="right"))
                if cost is not None
                else int(allowed)
            )
            cut = int(left[fitting]) if fitting < len(left) else end
            keep = left < cut
            search.unchecked = np.unique(entries.triangle[cut:])
            if open_pairs is not None:
                keep &= open_pairs
            first, second = first[keep], second[keep]
            for offset in range(0, len(first), PAIR_BLOCK):
                yield first[offset : offset + PAIR_BLOCK], second[offset : offset + PAIR_BLOCK]
            return
        counted += spent
        if open_pairs is not None:
            first, second = first[open_pairs], second[open_pairs]
        for offset in range(0, len(first), PAIR_BLOCK):
            yield first[offset : offset + PAIR_BLOCK], second[offset : offset + PAIR_BLOCK]


def _intervals_on_line(
    triangle: np.ndarray,
    distance: np.ndarray,
    direction: np.ndarray,
    origin: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Wo jedes Dreieck die Ebene des Partners schneidet, auf deren Schnittgerade projiziert.

    Eine Ecke gilt als *in* der Ebene, wenn ihr Abstand unter der numerischen
    Grenze ihres Dreiecks liegt; dazu kommt jede Kante mit echtem
    Vorzeichenwechsel. Ohne beides ist das Intervall leer (``inf``/``-inf``).
    """
    projection = _dot_rows(triangle - origin[:, None, :], direction)
    numeric = _numeric(np.linalg.norm(np.ptp(triangle, axis=1), axis=1))
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
    """Je Paar, ob die zwei Dreiecke sich durchdringen.

    Ein gemeinsamer Einzelpunkt ist eine Berührung. Bei einer Schnittstrecke
    zählt sie nur dann als Berührung, wenn die ganze Strecke auf einer Kante
    beider Dreiecke liegt.

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
    squared = (
        difference[..., 0] * difference[..., 0]
        + difference[..., 1] * difference[..., 1]
        + difference[..., 2] * difference[..., 2]
    )
    close = squared <= EPS_GEOM * EPS_GEOM
    first_matched = close.any(axis=2)
    # Gelegt wird nur, wo zwei Ecken nahe, aber nicht gleich sind: Die Mitte
    # zweier gleicher Ecken ist die Ecke selbst, ohne Rundung. An einem
    # verschweißten Netz teilen fast alle Nachbarn ihre Ecken genau so, und
    # das Zusammenlegen kostete dort ein Fünftel der Prüfung (RM-244).
    moving = np.flatnonzero(np.any(close & (squared > 0.0), axis=(1, 2)))
    if len(moving):
        near = close[moving]
        one, other = first[moving], second[moving]
        partner = np.take_along_axis(other, near.argmax(axis=2)[:, :, None], axis=1)
        one = np.where(first_matched[moving][:, :, None], (one + partner) / 2.0, one)
        partner = np.take_along_axis(one, near.argmax(axis=1)[:, :, None], axis=1)
        other = np.where(near.any(axis=1)[:, :, None], partner, other)
        first, second = first.copy(), second.copy()
        first[moving], second[moving] = one, other

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
    first_anchor, second_anchor = first[steep, 0], second[steep, 0]
    same_sign = np.signbit(first_anchor) == np.signbit(second_anchor)
    origin = np.empty_like(first_anchor)
    origin[same_sign] = 0.5 * first_anchor[same_sign] + 0.5 * second_anchor[same_sign]
    origin[~same_sign] = 0.5 * (first_anchor[~same_sign] + second_anchor[~same_sign])

    first_steep, second_steep = first[steep], second[steep]
    first_rounding = _half_ulp(first_steep).max(axis=1)
    second_rounding = _half_ulp(second_steep).max(axis=1)
    origin_rounding = _half_ulp(origin)
    coordinate_rounding = (
        np.abs(unit[:, 0])
        * (first_rounding[:, 0] + second_rounding[:, 0] + 2.0 * origin_rounding[:, 0])
        + np.abs(unit[:, 1])
        * (first_rounding[:, 1] + second_rounding[:, 1] + 2.0 * origin_rounding[:, 1])
        + np.abs(unit[:, 2])
        * (first_rounding[:, 2] + second_rounding[:, 2] + 2.0 * origin_rounding[:, 2])
    )
    pair_span = np.maximum(
        np.linalg.norm(np.ptp(first_steep, axis=1), axis=1),
        np.linalg.norm(np.ptp(second_steep, axis=1), axis=1),
    )
    line_rounding = _numeric(pair_span) + coordinate_rounding

    first_low, first_high = _intervals_on_line(first_steep, first_distance[steep], unit, origin)
    second_low, second_high = _intervals_on_line(second_steep, second_distance[steep], unit, origin)

    # Gemeinsame Ecken liegen mathematisch auf beiden Schnittintervallen.
    # Ihre Projektion berichtigt die berechneten Endpunkte bei Rundungsfehlern.
    common = np.all(first_steep[:, :, None, :] == second_steep[:, None, :, :], axis=-1)
    common_projection = np.broadcast_to(
        _dot_rows(first_steep - origin[:, None, :], unit)[:, :, None], common.shape
    )
    common_low = np.min(np.where(common, common_projection, np.inf), axis=(1, 2))
    common_high = np.max(np.where(common, common_projection, -np.inf), axis=(1, 2))
    shared_point = np.isfinite(common_low)
    shared_edge = np.zeros(len(steep), dtype=bool)
    for shared_first_edge in range(3):
        shared_first_end = (shared_first_edge + 1) % 3
        first_distinct = np.any(
            first_steep[:, shared_first_edge] != first_steep[:, shared_first_end], axis=1
        )
        for shared_second_edge in range(3):
            shared_second_end = (shared_second_edge + 1) % 3
            second_distinct = np.any(
                second_steep[:, shared_second_edge] != second_steep[:, shared_second_end], axis=1
            )
            same_direction = (
                common[:, shared_first_edge, shared_second_edge]
                & common[:, shared_first_end, shared_second_end]
            )
            reverse_direction = (
                common[:, shared_first_edge, shared_second_end]
                & common[:, shared_first_end, shared_second_edge]
            )
            shared_edge |= first_distinct & second_distinct & (same_direction | reverse_direction)

    # Zwei verschiedene gemeinsame Ecken bestimmen die ganze Ebenenschnitt-
    # geraden: Beide Dreiecke tragen dort dieselbe Kante.
    first_low[shared_edge], first_high[shared_edge] = (
        common_low[shared_edge],
        common_high[shared_edge],
    )
    second_low[shared_edge], second_high[shared_edge] = (
        common_low[shared_edge],
        common_high[shared_edge],
    )

    # Bei genau einer gemeinsamen Ecke wird je Dreieck der nähere berechnete
    # Intervallendpunkt auf deren Projektion gesetzt. Der andere Endpunkt
    # bleibt erhalten, sofern er außerhalb EPS_GEOM liegt, damit eine echte
    # Schnittstrecke durch die Ecke sichtbar ist.
    single_point = shared_point & ~shared_edge
    for interval_low, interval_high in (
        (first_low, first_high),
        (second_low, second_high),
    ):
        finite = np.isfinite(interval_low) & np.isfinite(interval_high)
        missing = single_point & ~finite
        interval_low[missing] = common_low[missing]
        interval_high[missing] = common_high[missing]
        present = single_point & finite
        # Paare ohne gemeinsame Ecke tragen hier ``inf`` als common_low.
        # Deren Abstand ist bedeutungslos und darf nicht ``inf - inf`` bilden.
        near_low = np.zeros(len(steep), dtype=bool)
        low_close = np.zeros(len(steep), dtype=bool)
        high_close = np.zeros(len(steep), dtype=bool)
        near_low[present] = np.abs(interval_low[present] - common_low[present]) <= np.abs(
            interval_high[present] - common_low[present]
        )
        low_close[present] = np.abs(interval_low[present] - common_low[present]) <= EPS_GEOM
        high_close[present] = np.abs(interval_high[present] - common_low[present]) <= EPS_GEOM
        snap_low = present & (near_low | low_close)
        snap_high = present & (~near_low | high_close)
        interval_low[snap_low] = common_low[snap_low]
        interval_high[snap_high] = common_low[snap_high]

    low = np.maximum(first_low, second_low)
    high = np.minimum(first_high, second_high)
    # Nicht koplanare Nachbarn können sich nur auf ihrer bereits belegten
    # gemeinsamen Kante treffen. Die teure Kollinearitätsprüfung unten
    # entscheidet daran nichts mehr; koplanare Überlagerungen wurden oben geprüft.
    crossing = np.isfinite(low) & np.isfinite(high) & (high >= low - EPS_GEOM) & ~shared_edge
    gap = high < low
    steep, low, high, unit, origin, gap, line_rounding, shared_edge = (
        steep[crossing],
        low[crossing],
        high[crossing],
        unit[crossing],
        origin[crossing],
        gap[crossing],
        line_rounding[crossing],
        shared_edge[crossing],
    )

    first_steep, second_steep = first[steep], second[steep]
    point = high - low <= EPS_GEOM
    # Koordinaten-ULPs gehen in die Rundungsgrenze ein. Die Kandidaten werden
    # nur nach Projektionsüberdeckung gewählt: Eine kurze Kante kann die
    # Richtungsrundung beim Verlängern stark verstärken.
    first_projection = _dot_rows(first_steep - origin[:, None, :], unit)
    second_projection = _dot_rows(second_steep - origin[:, None, :], unit)
    first_edge_low = np.minimum(first_projection, np.roll(first_projection, -1, axis=1))
    first_edge_high = np.maximum(first_projection, np.roll(first_projection, -1, axis=1))
    second_edge_low = np.minimum(second_projection, np.roll(second_projection, -1, axis=1))
    second_edge_high = np.maximum(second_projection, np.roll(second_projection, -1, axis=1))
    first_edge_covers = (first_edge_low <= low[:, None] + line_rounding[:, None]) & (
        first_edge_high >= high[:, None] - line_rounding[:, None]
    )
    second_edge_covers = (second_edge_low <= low[:, None] + line_rounding[:, None]) & (
        second_edge_high >= high[:, None] - line_rounding[:, None]
    )
    first_edge_candidates = first_edge_covers
    second_edge_candidates = second_edge_covers
    edge_contact = np.zeros(len(steep), dtype=bool)
    for first_edge in range(3):
        first_start = first_steep[:, first_edge]
        first_end = first_steep[:, (first_edge + 1) % 3]
        for second_edge in range(3):
            possible = first_edge_candidates[:, first_edge] & second_edge_candidates[:, second_edge]
            if not np.any(possible):
                continue
            rows = np.flatnonzero(possible)
            second_start = second_steep[:, second_edge]
            second_end = second_steep[:, (second_edge + 1) % 3]
            intervals_meet = np.minimum(
                first_edge_high[rows, first_edge], second_edge_high[rows, second_edge]
            ) >= (
                np.maximum(first_edge_low[rows, first_edge], second_edge_low[rows, second_edge])
                - line_rounding[rows]
            )
            rows = rows[intervals_meet]
            if not len(rows):
                continue
            # Nur eine vollständig kollineare Kante ist Kontakt. Nach dem
            # ersten Gegenbeleg müssen die übrigen Punkte nicht mehr fragen.
            for probe, start, end in (
                (first_start, second_start, second_end),
                (first_end, second_start, second_end),
                (second_start, first_start, first_end),
                (second_end, first_start, first_end),
            ):
                rows = rows[_point_on_line_with_rounding(probe[rows], start[rows], end[rows])]
                if not len(rows):
                    break
            edge_contact[rows] = True
    # Ein einzelner Punkt und ein innerhalb der Rundungsgrenze liegender Spalt
    # belegen keine Durchdringung. Ein größerer, bis EPS_GEOM reichender Spalt
    # bleibt ein Schnitt; ein Segment braucht beide tragenden Randkanten.
    resolvable_gap = gap & (low - high > line_rounding)
    hit[steep] = ~shared_edge & ~edge_contact & (resolvable_gap | ~point)
    return (hit, flat) if with_coplanar else hit


def _pairs_that_cross(
    surface: _Surface, cancelled: CancelToken | None, search: _Search
) -> Iterator[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Je Kandidatenblock die Paare, die sich wirklich schneiden (Nummern im Netz),
    und welche davon in derselben Ebene liegen."""
    for first, second in _candidates(surface, cancelled, search, separate=True):
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


#: Wie viele Kästen die Suche um aktive Dreiecke höchstens aufspannt
#: (:func:`crossings_at`). Mehr getrennte Stellen werden zu so vielen Kästen
#: zusammengelegt — jeder kostet einen Durchgang über alle Hüllquader.
ACTIVE_BOXES: Final = 24


def face_bounds(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Der Hüllquader jedes Dreiecks, ``(low, high)`` je ``(n, 3)``."""
    first, second, third = (vertices[faces[:, k]] for k in range(3))
    low = np.minimum(np.minimum(first, second), third)
    high = np.maximum(np.maximum(first, second), third)
    return low, high


def faces_touching(
    vertices: np.ndarray,
    faces: np.ndarray,
    boxes: list[tuple[np.ndarray, np.ndarray]],
    longest: float,
) -> np.ndarray:
    """Die Dreiecke, deren Hüllquader einen der Kästen bis auf ``EPS_GEOM`` berührt.

    Gesucht über die Ecken: Berührt ein Dreieck einen Kasten, liegen alle
    seine Ecken höchstens eine Kantenlänge daneben, also mindestens eine im
    um ``longest`` (die längste Kante oder eine Schranke dafür) erweiterten
    Kasten. Nur diese Dreiecke bekommen einen Hüllquader — an einem Netz mit
    Hunderttausenden ein Bruchteil davon.
    """
    marked = np.zeros(len(vertices), dtype=bool)
    reach = longest + EPS_GEOM
    for box_low, box_high in boxes:
        marked |= np.all(vertices >= box_low - reach, axis=1) & np.all(
            vertices <= box_high + reach, axis=1
        )
    candidates = np.flatnonzero(marked[faces].any(axis=1))
    low, high = face_bounds(vertices, faces[candidates])
    hit = np.zeros(len(candidates), dtype=bool)
    for box_low, box_high in boxes:
        hit |= np.all(low <= box_high + EPS_GEOM, axis=1) & np.all(
            high >= box_low - EPS_GEOM, axis=1
        )
    return np.asarray(candidates[hit], dtype=np.int64)


def boxes_around(low: np.ndarray, high: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Die Kästen aus :func:`box_groups`, ohne ihre Mitglieder."""
    return [(box_low, box_high) for box_low, box_high, _members in box_groups(low, high)]


def box_groups(
    low: np.ndarray, high: np.ndarray
) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Die Hüllquader ``low``…``high`` als wenige Kästen, die sie alle umfassen —
    je Kasten untere und obere Ecke und die Nummern der Quader darin.

    Geteilt wird, wo auf einer Achse eine Lücke liegt: Sechs Züge an ±X, ±Y,
    ±Z einer Kugel sind sechs Kästen, nicht einer um die ganze Kugel — der
    gemeinsame Quader nahm dort jedes Dreieck des Körpers in die Suche
    (RM-419). Zu viele Stellen legt :data:`ACTIVE_BOXES` zusammen; die Kästen
    dürfen sich dann überdecken.
    """
    groups = [np.arange(len(low))]
    found: list[np.ndarray] = []
    while groups:
        group = groups.pop()
        parts: list[np.ndarray] | None = None
        for axis in range(3):
            order = group[np.argsort(low[group, axis], kind="stable")]
            reach = np.maximum.accumulate(high[order, axis])
            gaps = np.flatnonzero(low[order[1:], axis] > reach[:-1] + EPS_GEOM)
            if len(gaps):
                parts = np.split(order, gaps + 1)
                break
        if parts is None:
            found.append(group)
        else:
            groups.extend(parts)
    found.sort(key=lambda group: float(low[group, 0].min()))
    if len(found) > ACTIVE_BOXES:
        size = -(-len(found) // ACTIVE_BOXES)
        found = [
            np.concatenate(found[start : start + size]) for start in range(0, len(found), size)
        ]
    return [(low[group].min(axis=0), high[group].max(axis=0), group) for group in found]


def _touching_apart(surface: _Surface, first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Welche Paare beweisbar höchstens an ihren gemeinsamen Ecken anliegen.

    Die Regel steht bei :func:`_touching_apart_tilted`.
    """
    apart, _tilt = _touching_apart_tilted(
        surface,
        first,
        second,
        surface.faces[first][:, :, None] == surface.faces[second][:, None, :],
    )
    return apart


def _touching_apart_tilted(
    surface: _Surface, first: np.ndarray, second: np.ndarray, same: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """:func:`_touching_apart` mit den gemeinsamen Ecken des Aufrufers, dazu je Paar
    die Länge des Kreuzprodukts beider Normalen.

    ``same[k, i, j]``: Ecke ``i`` des ersten trägt dieselbe Nummer wie Ecke
    ``j`` des zweiten. :func:`_separated` hat beides schon gerechnet und fragt
    es hier nicht ein zweites Mal (RM-568).

    Schräg zueinander gingen Nachbarn an die genaue Prüfung — an einer
    glatten Fläche sind das fast alle Kandidaten, und an einem Formschritt
    kostete das Sekunden (RM-419); seit RM-568 fragt auch :func:`_separated`
    hier, bevor es sie durchlässt. Getrennt heißt hier: Die Ecken des einen, die das
    andere nicht trägt, liegen alle um ``surface.margin`` auf derselben Seite
    der Ebene des anderen. Dann trifft das eine die Ebene des anderen nur in
    den gemeinsamen Ecken, und eine gemeinsame Ecke oder Kante ist für
    :func:`crossing_pairs` kein Schnitt. Ohne gemeinsame Ecke ist es die
    Ebenentrennung von :func:`_separated`, hier für alle Paare in einem Feld.
    Reiten bei einer gemeinsamen Ecke beide über die Ebene des anderen,
    entscheidet die Richtung ihrer Schnittstrecken (:func:`_opposite_rays`).

    **Eine Sicherung hält es an die genaue Prüfung: nicht fast parallel**
    (Sinus über ``EPS_GEOM``). Sonst rechnet sie das Paar als eben, und eine
    Falte über die gemeinsame Ecke ist ein Schnitt, auch wenn eine lange Kante
    weiter als ``margin`` absteht (``_folds_at_the_tolerance`` in den Tests).

    **Ecken, die die genaue Prüfung zusammenlegt, brauchen keine:** Liegt
    eine freie Ecke näher als ``EPS_GEOM`` an einer des anderen Dreiecks,
    liegt sie auch innerhalb ``margin`` von dessen Ebene — die Seite trennt
    dann nicht, und die Schnittstrecken beider laufen auf dieselbe Stelle zu,
    also nicht auseinander. Gesucht und nicht gefunden an 200 000 schmalen
    Dreiecken mit einer Ecke knapp neben der anderen.

    Abstände und Normalen sind dieselben Zahlen, die :func:`crossing_pairs`
    rechnet — elementweise, ohne ``einsum`` (RM-187).
    """
    one, other = surface.triangles[first], surface.triangles[second]
    one_normal, other_normal = surface.normal[first], surface.normal[second]
    one_length = surface.normal_length[first]
    other_length = surface.normal_length[second]
    direction = np.cross(one_normal, other_normal)
    tilt = np.linalg.norm(direction, axis=1)
    steep = tilt > EPS_GEOM * one_length * other_length
    margin = surface.margin
    one_side = _dot_rows(one - other[:, 0, None, :], other_normal) / other_length[:, None]
    other_side = _dot_rows(other - one[:, 0, None, :], one_normal) / one_length[:, None]
    one_free, other_free = ~same.any(axis=2), ~same.any(axis=1)
    beside = (
        np.all(~one_free | (one_side > margin), axis=1)
        | np.all(~one_free | (one_side < -margin), axis=1)
        | np.all(~other_free | (other_side > margin), axis=1)
        | np.all(~other_free | (other_side < -margin), axis=1)
    )
    # Eine gemeinsame Ecke, und beide reiten über die Ebene des anderen — am
    # Rand einer Mulde die Regel: Ihre Schnittstrecken beginnen in der
    # gemeinsamen Ecke, und zeigen sie auseinander, liegen die Dreiecke nur
    # dort aneinander.
    saddle = np.flatnonzero((one_free.sum(axis=1) == 2) & ~beside & steep)
    if len(saddle):
        beside[saddle] = _opposite_rays(
            one[saddle],
            other[saddle],
            one_side[saddle],
            other_side[saddle],
            one_free[saddle],
            other_free[saddle],
            direction[saddle],
            margin,
        )
    return np.asarray(beside & steep, dtype=bool), tilt


def _ray_from_the_corner(
    triangle: np.ndarray, side: np.ndarray, free: np.ndarray, direction: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Wo die Schnittstrecke eines Dreiecks mit einer Ebene von seiner
    gemeinsamen Ecke aus hinläuft, entlang ``direction`` — und ob es sie gibt.

    Die zwei freien Ecken liegen auf verschiedenen Seiten der Ebene
    (``side``); die Strecke reicht von der gemeinsamen Ecke bis zum
    Durchstoßpunkt ihrer Kante, wie in :func:`_intervals_on_line`.
    """
    rows = np.arange(len(triangle))
    order = np.argsort(~free, axis=1, kind="stable")
    first, second, shared = order[:, 0], order[:, 1], order[:, 2]
    start_distance, end_distance = side[rows, first], side[rows, second]
    crossing = start_distance * end_distance < 0.0
    fraction = np.divide(
        start_distance,
        start_distance - end_distance,
        out=np.zeros_like(start_distance),
        where=crossing,
    )
    start, end = triangle[rows, first], triangle[rows, second]
    point = start + fraction[:, None] * (end - start)
    away = point - triangle[rows, shared]
    along = (
        away[:, 0] * direction[:, 0] + away[:, 1] * direction[:, 1] + away[:, 2] * direction[:, 2]
    )
    return crossing, along


def _opposite_rays(
    one: np.ndarray,
    other: np.ndarray,
    one_side: np.ndarray,
    other_side: np.ndarray,
    one_free: np.ndarray,
    other_free: np.ndarray,
    direction: np.ndarray,
    margin: float,
) -> np.ndarray:
    """Ob die Schnittstrecken zweier Dreiecke mit einer gemeinsamen Ecke von
    ihr aus auseinanderlaufen — beide um mehr als ``margin``.

    Dann überdecken sich ihre Abschnitte auf der Schnittgeraden nur in der
    gemeinsamen Ecke, und das ist für :func:`crossing_pairs` eine Berührung.
    """
    one_crossing, one_along = _ray_from_the_corner(one, one_side, one_free, direction)
    other_crossing, other_along = _ray_from_the_corner(other, other_side, other_free, direction)
    length = np.linalg.norm(direction, axis=1)
    one_along, other_along = one_along / length, other_along / length
    return np.asarray(
        one_crossing
        & other_crossing
        & (one_along * other_along < 0.0)
        & (np.minimum(np.abs(one_along), np.abs(other_along)) > margin),
        dtype=bool,
    )


def crossings_at(
    vertices: np.ndarray,
    faces: np.ndarray,
    active: np.ndarray,
    cancelled: CancelToken | None = None,
    *,
    progress: Callable[[float], None] | None = None,
    longest: float | None = None,
    nearby: np.ndarray | None = None,
) -> Crossings:
    """Die Paare, die sich schneiden und an denen ein Dreieck aus ``active`` beteiligt ist.

    Vollständig wie :func:`crossing_face_pairs` für genau diese Paare, aber
    nur dort gesucht: Ein Formschritt fragte die ganze Suche über den
    gemeinsamen Hüllquader aller bewegten Punkte, und sechs kleine Züge an
    einer Kugel aus 327 680 Dreiecken kosteten 29 bis 32 Sekunden statt 0,22
    (RM-419). Die Partner kommen aus Kästen um die aktiven Dreiecke
    (:func:`boxes_around`), die Kandidaten aus dem Würfelabstand der Mitten
    (:func:`_active_pairs`); vor der genauen Prüfung trennen
    :func:`_separated` und :func:`_touching_apart`.

    ``longest`` ist eine Schranke für die längste Kante, wenn der Aufrufer
    sie kennt (:func:`faces_touching`); ``nearby`` die Dreiecke, unter denen
    die Partner liegen, wenn er sie schon gesucht hat — mehr schadet nicht,
    weniger wäre falsch. ``progress`` bekommt den geprüften Anteil,
    ``cancelled`` wird zwischen den Blöcken gefragt und wirft
    ``OperationCancelled``.
    """
    faces = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    vertices = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    active = np.asarray(active, dtype=bool)
    empty = np.zeros(0, dtype=np.int64)
    nothing = Crossings(empty, empty, np.zeros(0, dtype=bool), True)
    if not active.any():
        return nothing
    firsts: list[np.ndarray] = []
    seconds: list[np.ndarray] = []
    flats: list[np.ndarray] = []
    try:
        _check(cancelled)
        chosen = np.flatnonzero(active)
        if longest is None:
            low, high = face_bounds(vertices, faces)
            longest = float(np.max(high - low))
        low, high = face_bounds(vertices, faces[chosen])
        groups = box_groups(low, high)
        boxes = [(box_low, box_high) for box_low, box_high, _members in groups]
        if nearby is None:
            nearby = faces_touching(vertices, faces, boxes, longest)
        near_low, near_high = face_bounds(vertices, faces[nearby])
        for done, (box_low, box_high, members) in enumerate(groups):
            _check(cancelled)
            if progress is not None:
                progress(done / len(groups))
            inside = np.all(near_low <= box_high + EPS_GEOM, axis=1) & np.all(
                near_high >= box_low - EPS_GEOM, axis=1
            )
            sub = np.union1d(nearby[inside], chosen[members])
            found = _crossings_in(vertices, faces, sub, active, box_high - box_low, cancelled)
            if found is not None:
                firsts.append(found[0])
                seconds.append(found[1])
                flats.append(found[2])
    except _CancelledError:
        raise OperationCancelled from None
    if progress is not None:
        progress(1.0)
    if not firsts:
        return nothing
    first = np.concatenate(firsts).astype(np.int64)
    second = np.concatenate(seconds).astype(np.int64)
    # Zusammengelegte Kästen dürfen sich überdecken: jedes Paar einmal.
    _keys, unique = np.unique(
        np.minimum(first, second) * len(faces) + np.maximum(first, second), return_index=True
    )
    return Crossings(first[unique], second[unique], np.concatenate(flats)[unique], True)


def _crossings_in(
    vertices: np.ndarray,
    faces: np.ndarray,
    sub: np.ndarray,
    active: np.ndarray,
    extent: np.ndarray,
    cancelled: CancelToken | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Die schneidenden Paare mit einem aktiven Dreieck unter den Dreiecken ``sub``
    eines Flecks (:func:`crossings_at`), Nummern im ganzen Netz.

    Der Kehrplan kommt aus der Lage des Flecks statt aus einer Stichprobe:
    entlang seiner längsten Ausdehnung, in Scheiben quer dazu. Ein Fleck ist
    ein Stück Haut, und so liegt jedes Dreieck nur bei seinen Nachbarn; ein
    gemeinsamer Plan für sechs verschieden liegende Flecken zählte an der
    Kugel das Siebenfache an Paaren.
    """
    surface = _surface(vertices, faces[sub])
    if surface is None:
        return None
    live = active[sub][surface.kept]
    if not live.any():
        return None
    axes = np.argsort(-np.asarray(extent), kind="stable")
    width = 2.0 * float(np.median(surface.high[:, axes[1]] - surface.low[:, axes[1]]))
    plan = _Plan(int(axes[0]), int(axes[1]), width) if width > EPS_GEOM else _Plan(int(axes[0]))
    firsts: list[np.ndarray] = []
    seconds: list[np.ndarray] = []
    flats: list[np.ndarray] = []
    for first, second in _candidates(surface, cancelled, _Search(), plan):
        mine = live[first] | live[second]
        one, other = first[mine], second[mine]
        apart = _touching_apart(surface, one, other)
        one, other = one[~apart], other[~apart]
        separated, _searched = _separated(surface, one, other)
        one, other = one[~separated], other[~separated]
        crossed, coplanar = crossing_pairs(
            surface.triangles[one],
            surface.triangles[other],
            surface.faces[one],
            surface.faces[other],
            with_coplanar=True,
        )
        if np.any(crossed):
            firsts.append(sub[surface.kept[one[crossed]]])
            seconds.append(sub[surface.kept[other[crossed]]])
            flats.append(coplanar[crossed])
    if not firsts:
        return None
    return np.concatenate(firsts), np.concatenate(seconds), np.concatenate(flats)
