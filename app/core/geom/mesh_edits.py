"""Örtliche Schritte am geschlossenen Dreiecksnetz: zusammenlegen und teilen.

Zwei Schritte, mit denen sich ein Netz verbessern lässt, ohne den Körper zu
ändern, den es beschreibt — jeder an einer einzelnen Kante:

* **Zusammenlegen** (:func:`collapse_short`): Die Halbkante ``v → w`` fällt weg,
  ``v`` geht in ``w`` auf. Es entsteht keine neue Koordinate; jede Ecke danach
  ist eine von vorher. Das räumt die Nadeln weg, die Marching Cubes neben eine
  Rasterecke legt (``blend``).
* **Teilen** (:func:`split_long`): Eine zu lange Kante wird in der Mitte geteilt,
  beide Nachbardreiecke mit ihr. Der neue Punkt liegt auf der Kante, also auf
  der Oberfläche.

**Warum das Teilen hier und nicht im Netzkern.** ``manifold3d`` teilt mit
``refine_to_length`` jede Kante auf die verlangte Länge, zieht im Inneren eines
Dreiecks aber Kanten, die länger sein können (``mesh_ops.uniform``). Ein
zweiter Durchgang im Kern kostete am Wedge-Lock 0,9 s gegen 0,085 s für das
Teilen hier und hielt die Kante trotzdem nicht (Review-Fix F zu RM-671).

**Das Zusammenlegen in Runden unabhängiger Schritte.** Zwei Schritte derselben
Runde teilen kein Dreieck, auch nicht die Nachbarn, deren Halbkanten sie
umhängen; dann ist jede Prüfung einer Runde gültig, gleich in welcher
Reihenfolge die Runde ausgeführt wird. Wer zuerst darf, entscheidet eine feste,
über das Netz gestreute Rangfolge (:func:`_scattered`), und gewählt wird, bis
kein freier Kandidat mehr übrig ist (:func:`_claimed`) — dasselbe Netz gibt
immer dasselbe Ergebnis. Die nächste Runde fragt nur dort neu, wo sich etwas
geändert hat oder ein Kandidat warten musste.

**Plattformgleich** (``geom/CLAUDE.md``): Grundrechenarten, Wurzel und
Kreuzprodukt, nichts aus BLAS.

Das Netz ist geschlossen und gleichsinnig gewickelt; was das nicht ist, gibt
:func:`surface_of` als ``None`` zurück, und der Aufrufer lässt es, wie es ist.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Final

import numpy as np

from app.core.geom.mesh import row_dots
from app.core.types import CancelToken

#: Wie viele Halbkanten ein Ring um eine Ecke höchstens hat, damit sie
#: zusammengelegt werden darf. Darüber — der Scheitel eines CAD-Fächers trägt
#: hundert Dreiecke — bleibt die Ecke stehen: Ein Ring dieser Größe ist keine
#: Nadel und kein überzähliger Punkt.
RING_LIMIT: Final = 64

#: Die Staffel der Ringbreiten in :func:`_collapsible` — reine Rechenordnung, am
#: Ergebnis ändert sie nichts. Die meisten Ecken eines geteilten Netzes haben
#: sechs Nachbarn, wenige an Fächern bis :data:`RING_LIMIT`.
RING_BANDS: Final = (8, 16, 32, RING_LIMIT)

#: Höchstzahl der Runden des Zusammenlegens. Eine Absicherung, keine
#: Erwartung: Die Nadeln einer Verschmelzung sind nach zwölf bis zwanzig Runden fort.
EDIT_ROUNDS: Final = 64

#: Höchstzahl der Durchgänge von :func:`split_long` — eine Absicherung: Nach dem
#: Teilen im Kern liegen die längsten Kanten beim Doppelten des Verlangten, und
#: jeder Durchgang halbiert sie.
SPLIT_PASSES: Final = 32

#: Höchstzahl der Wahlgänge je Runde in :func:`_claimed` — eine Absicherung:
#: Jeder Wahlgang nimmt mindestens den Kandidaten mit dem kleinsten Rang, und
#: bei gestreuter Rangfolge ist nach wenigen keiner mehr frei.
CLAIM_PASSES: Final = 32


@dataclass
class Surface:
    """Ein geschlossenes Netz als Halbkanten — die Arbeitsform der Schritte.

    Halbkante ``3·f + k`` läuft in Dreieck ``f`` von Ecke ``k`` zu Ecke
    ``k + 1``. ``partner`` ist die gegenläufige Halbkante, ``-1`` am Rand der
    Auswahl ``active``: Nur aktive Dreiecke werden angefasst, und nur dort ist
    die Nachbarschaft bekannt. Gelöschte Dreiecke bleiben stehen
    (``alive``), bis :meth:`arrays` das Netz zurückgibt — so bleiben die
    Nummern einer Runde gültig.
    """

    vertices: np.ndarray
    faces: np.ndarray
    partner: np.ndarray
    alive: np.ndarray
    active: np.ndarray
    valence: np.ndarray
    #: Arbeitsfelder von :func:`_claimed`, je Dreieck und Ecke ein Platz: einmal
    #: angelegt und nach jedem Wahlgang nur dort zurückgesetzt, wo er schrieb —
    #: sonst kostete jeder Wahlgang ein Feld über das ganze Netz.
    best: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64), repr=False)
    taken: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool), repr=False)

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """Ecken und Dreiecke ohne Gelöschtes, in der Reihenfolge von vorher."""
        faces = self.faces[self.alive]
        used = np.zeros(len(self.vertices), dtype=bool)
        used[faces.reshape(-1)] = True
        index = np.cumsum(used) - 1
        return np.array(self.vertices[used]), np.asarray(index[faces], dtype=np.int64)


def surface_of(
    vertices: np.ndarray, faces: np.ndarray, active: np.ndarray | None = None
) -> Surface | None:
    """Das Netz mit seinen Halbkanten — ``None``, wenn es verzweigt oder falsch herum hängt.

    ``active`` wählt die Dreiecke, an denen gearbeitet werden darf; ihre
    Halbkanten bekommen ihre Partner, alle anderen ``-1``. Eine Kante mit
    drei Dreiecken oder zwei gleichsinnigen Halbkanten heißt: kein
    geschlossener, gleichsinnig gewickelter Körper — dort wäre jeder Schritt
    geraten.
    """
    points = np.array(vertices, dtype=np.float64, copy=True)
    corners = np.array(faces, dtype=np.int64, copy=True).reshape(-1, 3)
    count = len(corners)
    chosen = (
        np.ones(count, dtype=bool) if active is None else np.array(active, dtype=bool, copy=True)
    )
    partner = np.full(3 * count, -1, dtype=np.int64)
    halves = np.flatnonzero(np.repeat(chosen, 3))
    flat = corners.reshape(-1)
    tails = flat[halves]
    heads = flat[_next(halves)]
    if bool(np.any(tails == heads)):
        return None
    width = len(points)
    codes = np.minimum(tails, heads) * width + np.maximum(tails, heads)
    order = np.argsort(codes, kind="stable")
    ordered = codes[order]
    starts = np.flatnonzero(np.concatenate(([True], ordered[1:] != ordered[:-1])))
    lengths = np.diff(np.concatenate((starts, [len(ordered)])))
    if bool(np.any(lengths > 2)):
        return None
    pairs = starts[lengths == 2]
    one = halves[order[pairs]]
    other = halves[order[pairs + 1]]
    if not np.array_equal(flat[one], flat[_next(other)]):
        return None
    partner[one] = other
    partner[other] = one
    valence = np.bincount(flat, minlength=width).astype(np.int64)
    return Surface(points, corners, partner, np.ones(count, dtype=bool), chosen, valence)


def around(faces: np.ndarray, wanted: np.ndarray) -> np.ndarray:
    """Die Dreiecke ``wanted`` und jedes, das eine Ecke mit ihnen teilt.

    So viel muss aktiv sein, damit die Ringe ihrer Ecken ganz sind — das
    Zusammenlegen fragt sie (:func:`collapse_short`).
    """
    corners = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    marked = np.zeros(int(corners.max(initial=-1)) + 1, dtype=bool)
    marked[corners[np.asarray(wanted, dtype=bool)].reshape(-1)] = True
    return np.asarray(marked[corners].any(axis=1))


def _next(halves: np.ndarray) -> np.ndarray:
    return np.asarray(halves - halves % 3 + (halves % 3 + 1) % 3)


def _prev(halves: np.ndarray) -> np.ndarray:
    return np.asarray(halves - halves % 3 + (halves % 3 + 2) % 3)


def _rings(surface: Surface, start: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Die Halbkanten, die an derselben Ecke beginnen wie ``start`` — einmal herum.

    Zurück kommt ein Feld ``(k, Länge)`` mit ``-1`` aufgefüllt und je Zeile,
    ob der Ring sich geschlossen hat. Er schließt sich nicht am Rand der
    Auswahl und nicht über :data:`RING_LIMIT`.
    """
    rows = len(start)
    ring = np.full((rows, RING_LIMIT), -1, dtype=np.int64)
    current = np.array(start, dtype=np.int64, copy=True)
    walking = np.ones(rows, dtype=bool)
    closed = np.zeros(rows, dtype=bool)
    used = 0
    for step in range(RING_LIMIT):
        if not walking.any():
            break
        ring[walking, step] = current[walking]
        used = step + 1
        following = surface.partner[_prev(np.where(walking, current, 0))]
        broken = walking & (following < 0)
        walking &= ~broken
        home = walking & (following == start)
        closed |= home
        walking &= ~home
        current = np.where(walking, following, current)
    return ring[:, :used], closed


def _claimed(
    surface: Surface, faces: np.ndarray, corners: np.ndarray, rank: np.ndarray
) -> np.ndarray:
    """Welche Kandidaten ihre Dreiecke und Ecken für sich haben — so viele wie frei sind.

    ``faces`` nennt je Kandidat die Dreiecke, die sein Schritt ändert oder
    deren Halbkanten er umhängt, ``corners`` die Ecken, die dabei einen
    Nachbarn verlieren (``-1`` ist leer); gewinnt, wer bei jedem davon den
    kleinsten Rang hat. Ohne die Ecken verlöre eine Ecke mit vier Nachbarn
    in einer Runde zwei und hinge danach an zwei Dreiecken.

    **Gewählt wird nach**, bis kein Kandidat mehr frei ist: Wer einem Gewinner
    nichts wegnimmt, tritt im nächsten Wahlgang gegen die Übrigen an. Ein
    einziger Wahlgang nahm am Besenhalter aus ``F:\\3D Dateien`` je Runde 2 %
    der gültigen Schritte; alle anderen warteten und wurden in der nächsten
    Runde neu geprüft (RM-671).
    """
    groups = np.concatenate(
        (faces, np.where(corners >= 0, corners + len(surface.faces), -1)), axis=1
    )
    filled = groups >= 0
    groups = np.where(filled, groups, 0)
    width = len(surface.faces) + len(surface.vertices)
    big = np.iinfo(np.int64).max
    if len(surface.best) != width:
        surface.best = np.full(width, big, dtype=np.int64)
        surface.taken = np.zeros(width, dtype=bool)
    best, taken = surface.best, surface.taken
    won = np.zeros(len(rank), dtype=bool)
    free = np.arange(len(rank), dtype=np.int64)
    for _pass in range(CLAIM_PASSES):
        if not len(free):
            break
        mine, filled_mine = groups[free], filled[free]
        owners = np.broadcast_to(rank[free, None], mine.shape)
        places = mine[filled_mine]
        np.minimum.at(best, places, owners[filled_mine])
        lowest = np.where(filled_mine, best[mine], big).min(axis=1)
        best[places] = big
        winners = lowest == rank[free]
        won[free[winners]] = True
        taken[mine[winners][filled_mine[winners]]] = True
        # Wer etwas berührt, das ein Gewinner nimmt, wartet — die Gewinner selbst auch.
        free = free[~(taken[mine] & filled_mine).any(axis=1)]
    taken[groups[won][filled[won]]] = False
    return won


def _rank(*keys: np.ndarray) -> np.ndarray:
    """Rang nach den Schlüsseln, der letzte zuerst (wie ``np.lexsort``)."""
    order = np.lexsort(keys)
    rank = np.empty(len(order), dtype=np.int64)
    rank[order] = np.arange(len(order), dtype=np.int64)
    return rank


def _scattered(numbers: np.ndarray) -> np.ndarray:
    """Eine feste, über das Netz gestreute Reihenfolge der Nummern (``splitmix64``).

    Nach Länge oder Nummer allein liegen Nachbarn in einem Streifen der Reihe
    nach, und je Wahlgang gewinnt nur das eine Ende; gestreut gewinnt in jedem
    Ausschnitt einer. Ganzzahlig, also auf jeder Plattform dieselbe Folge.
    """
    mixed = np.asarray(numbers, dtype=np.uint64) + np.uint64(0x9E3779B97F4A7C15)
    mixed = (mixed ^ (mixed >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    mixed = (mixed ^ (mixed >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return np.asarray(mixed ^ (mixed >> np.uint64(31)))


def _lengths(points: np.ndarray, first: np.ndarray, second: np.ndarray) -> np.ndarray:
    delta = points[second] - points[first]
    return np.sqrt(row_dots(delta, delta))


def _face_halves(faces: np.ndarray) -> np.ndarray:
    """Die drei Halbkanten je Dreieck, ``(k, 3)``."""
    return np.asarray(3 * faces[:, None] + np.arange(3, dtype=np.int64)[None, :])


def _candidate_halves(surface: Surface, pending: np.ndarray) -> np.ndarray:
    """Die Halbkanten der lebenden, aktiven Dreiecke aus ``pending`` mit bekanntem Partner."""
    faces = np.flatnonzero(pending & surface.alive & surface.active)
    halves = _face_halves(faces).reshape(-1)
    twins = surface.partner[halves]
    known = twins >= 0
    halves, twins = halves[known], twins[known]
    twin_faces = twins // 3
    usable = surface.alive[twin_faces] & surface.active[twin_faces]
    return np.asarray(halves[usable])


def collapse_short(
    surface: Surface, shortest: float, *, cancelled: CancelToken | None = None
) -> int:
    """Legt Kanten unter ``shortest`` zusammen; zurück kommt, wie viele.

    Die Halbkante ``v → w`` fällt weg, ``v`` geht in ``w`` auf — mit ``w``s
    Koordinate, also ohne neue. Gültig ist ein Schritt, wenn

    * beide Ringe geschlossen sind, jeder um seine Ecke ganz herum, und ``v``
      und ``w`` genau die zwei Ecken gemeinsam haben, die ihren Dreiecken
      gegenüberliegen (sonst risse die Oberfläche oder bekäme eine dritte
      Fläche an einer Kante),
    * diese beiden danach noch drei Nachbarn haben und ``w`` auch,
    * kein Dreieck um ``v`` dabei umklappt.

    Geprüft wird vom Billigen zum Teuren: erst Länge und Wertigkeit, dann der
    Ring um ``v``, und nur, wer das besteht, bekommt den Ring um ``w``.
    """
    done = 0
    pending = np.array(surface.active & surface.alive, copy=True)
    for _round in range(EDIT_ROUNDS):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        halves = _candidate_halves(surface, pending)
        pending = np.zeros(len(surface.faces), dtype=bool)
        flat_faces = surface.faces.reshape(-1)
        length = _lengths(surface.vertices, flat_faces[halves], flat_faces[_next(halves)])
        h = halves[length < shortest]
        if not len(h):
            break
        g = surface.partner[h]
        v, w = flat_faces[h], flat_faces[_next(h)]
        c, d = flat_faces[_next(_next(h))], flat_faces[_next(_next(g))]
        valence = surface.valence
        keep = (valence[v] <= RING_LIMIT) & (valence[w] <= RING_LIMIT)
        keep &= (valence[c] >= 4) & (valence[d] >= 4) & (valence[v] + valence[w] >= 7)
        h, g, v, w, c, d = (part[keep] for part in (h, g, v, w, c, d))
        if not len(h):
            break
        rows, ring_v, ring_w = _collapsible(surface, h, g, v, w)
        if not len(rows):
            break
        h, g, v, w, c, d = (part[rows] for part in (h, g, v, w, c, d))
        star = np.concatenate(
            (np.where(ring_v >= 0, ring_v // 3, -1), np.where(ring_w >= 0, ring_w // 3, -1)),
            axis=1,
        )
        length = _lengths(surface.vertices, v, w)
        # Kürzere Viertel von ``shortest`` zuerst, darin gestreut.
        quarter = np.minimum(np.floor(length * (4.0 / shortest)), 3.0)
        won = _claimed(surface, star, np.column_stack((v, w, c, d)), _rank(_scattered(h), quarter))
        # Wer verliert, wird mit seinen zwei Dreiecken neu gefragt; was ein Gewinner
        # ändert, mit seinem ganzen Stern.
        pending[h[~won] // 3] = True
        pending[g[~won] // 3] = True
        _apply_collapses(surface, h[won], g[won], ring_v[won], c[won], d[won])
        touched = star[won]
        pending[touched[touched >= 0]] = True
        pending &= surface.alive
        done += int(won.sum())
    return done


def _collapsible(
    surface: Surface, h: np.ndarray, g: np.ndarray, v: np.ndarray, w: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Die Prüfungen am Ring (:func:`collapse_short`): wer besteht, und die Ringe um v und w.

    Gestaffelt nach der Wertigkeit (:data:`RING_BANDS`): Ein Ringfeld ist so
    breit wie der längste Ring darin, und eine Ecke mit sechzig Nachbarn machte
    sonst jede Zeile sechzig breit — am Würfel aus dem Download-Korpus rechneten
    120 000 Zeilen 58 Spalten, bei sechs Nachbarn im Mittel. Das Ergebnis hängt
    an der Staffelung nicht: Jede Zeile wird für sich geprüft.
    """
    valence = surface.valence
    bands = np.searchsorted(np.asarray(RING_BANDS), np.maximum(valence[v], valence[w]))
    found: list[np.ndarray] = []
    around_v: list[np.ndarray] = []
    around_w: list[np.ndarray] = []
    for band in np.unique(bands):
        rows = np.flatnonzero(bands == band)
        ring_v, closed_v = _rings(surface, h[rows])
        keep = closed_v & ((ring_v >= 0).sum(axis=1) == valence[v[rows]])
        keep &= _keeps_its_faces(surface, h[rows], g[rows], w[rows], ring_v)
        rows, ring_v = rows[keep], ring_v[keep]
        ring_w, closed_w = _rings(surface, g[rows])
        keep = closed_w & ((ring_w >= 0).sum(axis=1) == valence[w[rows]])
        keep &= _link_holds(surface, ring_v, ring_w)
        found.append(rows[keep])
        around_v.append(ring_v[keep])
        around_w.append(ring_w[keep])
    return np.concatenate(found), _stacked(around_v), _stacked(around_w)


def _stacked(rings: list[np.ndarray]) -> np.ndarray:
    """Ringfelder verschiedener Breite untereinander, rechts mit ``-1`` aufgefüllt."""
    width = max(ring.shape[1] for ring in rings)
    return np.concatenate(
        [np.pad(ring, ((0, 0), (0, width - ring.shape[1])), constant_values=-1) for ring in rings]
    )


def _link_holds(surface: Surface, ring_v: np.ndarray, ring_w: np.ndarray) -> np.ndarray:
    """Ob ``v`` und ``w`` genau zwei Nachbarn gemeinsam haben.

    Jeder Nachbar steht in seinem Ring genau einmal; nach dem Sortieren der
    beiden Ringe zusammen ist jede doppelte Zahl ein gemeinsamer Nachbar.
    ``v`` und ``w`` selbst stehen je im anderen Ring und zählen nicht.
    """
    flat_faces = surface.faces.reshape(-1)
    rows = len(ring_v)
    if not rows:
        return np.zeros(0, dtype=bool)
    around_v = np.where(ring_v >= 0, flat_faces[_next(np.maximum(ring_v, 0))], -1)
    around_w = np.where(ring_w >= 0, flat_faces[_next(np.maximum(ring_w, 0))], -1)
    v = flat_faces[ring_v[:, 0]]
    w = flat_faces[ring_w[:, 0]]
    around_v = np.where(around_v == w[:, None], -1, around_v)
    around_w = np.where(around_w == v[:, None], -1, around_w)
    both = np.concatenate((around_v, around_w), axis=1)
    # Leere Plätze bekommen je Zeile verschiedene negative Zahlen, damit sie
    # nicht als gemeinsam zählen.
    fill = -1 - np.arange(both.shape[1], dtype=np.int64)[None, :]
    both = np.where(both >= 0, both, fill)
    both.sort(axis=1)
    twice = (both[:, 1:] == both[:, :-1]) & (both[:, 1:] >= 0)
    return np.asarray(twice.sum(axis=1) == 2)


def _keeps_its_faces(
    surface: Surface, h: np.ndarray, g: np.ndarray, w: np.ndarray, ring_v: np.ndarray
) -> np.ndarray:
    """Ob die Dreiecke um ``v`` den Schritt ``v → w`` überstehen, ohne umzuklappen."""
    rows = len(h)
    if not rows:
        return np.zeros(0, dtype=bool)
    filled = ring_v >= 0
    faces = np.where(filled, ring_v // 3, -1)
    gone = (faces == (h // 3)[:, None]) | (faces == (g // 3)[:, None])
    moving = filled & ~gone
    owner = np.broadcast_to(np.arange(rows)[:, None], ring_v.shape)[moving]
    face = faces[moving]
    corners = surface.vertices[surface.faces[face]]
    before = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    # Die Halbkante des Rings beginnt an v: ihr Platz im Dreieck ist der von v.
    slot = ring_v[moving] % 3
    moved = corners.copy()
    moved[np.arange(len(face)), slot] = surface.vertices[w[owner]]
    after = np.cross(moved[:, 1] - moved[:, 0], moved[:, 2] - moved[:, 0])
    good = (row_dots(before, after) > 0.0) & (row_dots(after, after) > 0.0)
    result = np.ones(rows, dtype=bool)
    np.logical_and.at(result, owner, good)
    return result


def _apply_collapses(
    surface: Surface,
    h: np.ndarray,
    g: np.ndarray,
    ring_v: np.ndarray,
    c: np.ndarray,
    d: np.ndarray,
) -> None:
    """Führt unabhängige Kollapse aus: ``v`` wird in seinen Dreiecken zu ``w``."""
    flat_faces = surface.faces.reshape(-1)
    v = flat_faces[h]
    w = flat_faces[_next(h)]
    x = surface.partner[_next(h)]
    y = surface.partner[_prev(h)]
    z = surface.partner[_next(g)]
    u = surface.partner[_prev(g)]
    filled = ring_v >= 0
    owner = np.broadcast_to(np.arange(len(h))[:, None], ring_v.shape)[filled]
    flat_faces[ring_v[filled]] = w[owner]
    surface.alive[h // 3] = False
    surface.alive[g // 3] = False
    surface.partner[x] = y
    surface.partner[y] = x
    surface.partner[z] = u
    surface.partner[u] = z
    gained = surface.valence[v] - 4
    surface.valence[v] = 0
    np.add.at(surface.valence, w, gained)
    np.subtract.at(surface.valence, c, 1)
    np.subtract.at(surface.valence, d, 1)


#: Wie weit unter dem Vierfachen des Grenzquadrats eine geteilte Seite liegen muss,
#: damit ihre Hälften sicher kurz genug sind (:func:`split_long`). Die Mitte
#: entsteht in doppelter Genauigkeit; ein Milliardstel deckt deren Rundung um
#: Größenordnungen ab und kostet nur Seiten, die fast genau doppelt so lang sind.
HALF_SAFE: Final = 1.0 - 1e-9

#: Je Ecke eines Dreiecks die nächste — Seite ``k`` läuft von Ecke ``k`` zu dieser.
_AHEAD: Final = np.array([1, 2, 0])

#: Ab wie vielen Dreiecken :func:`split_long` seine Seiten auf Fäden misst, in
#: Portionen dieser Größe. Das Messen liest je Dreieck neun Zahlen verstreut aus
#: den Ecken und war am Wedge-Lock gut ein Drittel des Teilens; NumPy gibt dabei
#: die Sperre frei. Jede Portion schreibt nur ihren Abschnitt, Element für
#: Element gleich gerechnet — das Ergebnis hängt nicht an der Zahl der Fäden
#: (``tests/test_platform_identity.py``, ``_THREADED``).
MEASURE_CHUNK: Final = 65_536
MEASURE_WORKERS: Final = 4


def split_long(
    vertices: np.ndarray,
    faces: np.ndarray,
    longest: float,
    *,
    suspects: np.ndarray | None = None,
    cancelled: CancelToken | None = None,
    measured: list[int] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Teilt jede Kante über ``longest`` in der Mitte — alle zugleich, bis keine mehr darüber liegt.

    Je Durchgang werden die zu langen Kanten markiert und in der Mitte geteilt;
    beide Dreiecke an der Kante teilen die neue Ecke, und sie liegt auf der
    Kante, also auf der Oberfläche. Jedes Dreieck zerfällt nach dem Muster
    seiner markierten Seiten (:func:`_split_by_pattern`). Ohne Runden und ohne
    Halbkanten: An der Kugel aus §31 (2,46 Mio. Dreiecke nach dem Teilen im
    Kern) brauchte die Fassung mit Runden je Kante 4,9 s, wo ein Durchgang über
    die Felder genügt. :data:`SPLIT_PASSES` ist eine Absicherung; jeder
    Durchgang halbiert die markierten Kanten.

    ``suspects`` nennt die Dreiecke, die zu lang sein können; ohne sind es
    alle. Gemessen werden im ersten Durchgang nur sie, danach nur neue Teile,
    die noch zu lang sein können — eine zu lange Kante hat beide Dreiecke
    unter den Verdächtigen. Ein Dreieck mit genau einer zu langen Seite bis zur
    doppelten Grenze zerfällt in zwei, deren Seiten höchstens die halbe lange
    Seite, eine der beiden alten oder die Mittellinie sind, und die ist bei
    zwei Seiten bis zur Grenze und einer darüber kürzer als √3/2 der Grenze:
    Diese Teile werden nicht noch einmal gemessen (:data:`HALF_SAFE`). Am
    Quader 100 x 80 x 60 auf 0,5 mm maß der zweite Durchgang sonst alle
    709 760 Teile und kostete so viel wie der erste (Review-Fix F).

    Zurück kommen Ecken, Dreiecke und je Dreieck seine Nummer im Eingang,
    ``-1`` für ein geteiltes: Wer über die Dreiecke schon etwas weiß, muss nur
    an den neuen nachmessen. ``measured`` bekommt je Durchgang die Zahl der
    gemessenen Dreiecke — die Arbeit, die ein Test zählt.
    """
    points = np.asarray(vertices, dtype=np.float64)
    corners = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    origin = np.arange(len(corners), dtype=np.int64)
    asked = (
        np.ones(len(corners), dtype=bool)
        if suspects is None
        else np.asarray(suspects, dtype=bool).copy()
    )
    limit = longest * longest
    for _pass in range(SPLIT_PASSES):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        # Jedes Feld einmal gelesen: Ecken der gefragten Dreiecke, ihre Punkte, Seiten.
        rows = None if asked.all() else np.flatnonzero(asked)
        picked = corners if rows is None else corners[rows]
        if measured is not None:
            measured.append(len(picked))
        heads = picked[:, _AHEAD]
        squared = _side_squares(points, picked)
        found = squared > limit
        hits = found.sum(axis=1)
        if not hits.any():
            break
        # Einfach geteilt bis zur doppelten Grenze: Die Teile sind sicher kurz genug.
        lone = np.flatnonzero(hits == 1)
        lone_short = np.zeros(len(picked), dtype=bool)
        lone_short[lone] = squared[lone][found[lone]] <= 4.0 * limit * HALF_SAFE
        if rows is None:
            marked, settled, count = found, lone_short, hits
        else:
            marked = np.zeros(corners.shape, dtype=bool)
            marked[rows] = found
            settled = np.zeros(len(corners), dtype=bool)
            settled[rows] = lone_short
            count = np.zeros(len(corners), dtype=hits.dtype)
            count[rows] = hits
        width = len(points)
        tails, ends = picked[found], heads[found]
        codes = np.minimum(tails, ends) * width + np.maximum(tails, ends)
        unique, inverse = np.unique(codes, return_inverse=True)
        first, second = unique // width, unique % width
        middles = np.full(corners.shape, -1, dtype=np.int64)
        middles[marked] = width + np.asarray(inverse, dtype=np.int64).reshape(-1)
        points = np.concatenate((points, (points[first] + points[second]) / 2.0))
        unsplit = np.flatnonzero(count == 0)
        corners, again = _split_by_pattern(points, corners, middles, settled, count)
        origin = np.concatenate(
            (origin[unsplit], np.full(len(corners) - len(unsplit), -1, dtype=np.int64))
        )
        asked = np.zeros(len(corners), dtype=bool)
        asked[len(unsplit) :] = again
    return points, corners, origin


def _side_squares(points: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Je Dreieck die Quadrate seiner drei Seiten, Seite ``k`` von Ecke ``k`` zur nächsten.

    Über :data:`MEASURE_CHUNK` Dreiecken auf bis zu :data:`MEASURE_WORKERS` Fäden.
    """
    workers = max(1, min(MEASURE_WORKERS, os.cpu_count() or 1))
    if len(corners) <= MEASURE_CHUNK or workers < 2:
        return _side_squares_of(points, corners)
    squared = np.empty(corners.shape, dtype=np.float64)

    def part(start: int) -> None:
        end = start + MEASURE_CHUNK
        squared[start:end] = _side_squares_of(points, corners[start:end])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(part, range(0, len(corners), MEASURE_CHUNK)))
    return squared


def _side_squares_of(points: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """:func:`_side_squares` für eine Portion, auf einem Faden."""
    at_corners = points[corners]
    delta = at_corners[:, _AHEAD] - at_corners
    return row_dots(delta, delta)


def _split_by_pattern(
    points: np.ndarray,
    corners: np.ndarray,
    middles: np.ndarray,
    settled: np.ndarray,
    count: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Jedes Dreieck nach seinen geteilten Seiten (``middles`` je Seite, ``-1`` ungeteilt).

    Seite ``k`` läuft von Ecke ``k`` zu ``k + 1``. Eine geteilte Seite halbiert
    das Dreieck zur Gegenecke; zwei trennen die Ecke zwischen ihnen ab, und das
    Viereck daneben teilt seine kürzere Diagonale; drei ergeben vier ähnliche
    Dreiecke. Die Umlaufrichtung bleibt, die ungeteilten Dreiecke stehen vorn.
    Zurück kommt dazu je Teil, ob es noch zu lang sein kann — nein nur für die
    beiden Hälften eines Dreiecks, das ``settled`` nennt (:func:`split_long`).
    ``count`` ist je Dreieck die Zahl seiner geteilten Seiten.
    """
    pieces = [corners[count == 0]]
    again: list[np.ndarray] = []
    lone = np.flatnonzero(count == 1)
    if len(lone):
        turn = (np.argmax(middles[lone] >= 0, axis=1)[:, None] + np.arange(3)) % 3
        a, b, c = np.take_along_axis(corners[lone], turn, axis=1).T
        middle = np.take_along_axis(middles[lone], turn, axis=1)[:, 0]
        pieces += [np.column_stack((a, middle, c)), np.column_stack((middle, b, c))]
        open_again = ~settled[lone]
        again += [open_again, open_again]
    pair = np.flatnonzero(count == 2)
    if len(pair):
        # Die ungeteilte Seite wird Seite 2: Die Ecke b liegt zwischen beiden geteilten.
        turn = ((np.argmin(middles[pair] >= 0, axis=1) + 1)[:, None] + np.arange(3)) % 3
        a, b, c = np.take_along_axis(corners[pair], turn, axis=1).T
        halves = np.take_along_axis(middles[pair], turn, axis=1)
        near, far = halves[:, 0], halves[:, 1]
        across = points[far] - points[a]
        other = points[c] - points[near]
        from_a = row_dots(across, across) <= row_dots(other, other)
        pieces += [
            np.column_stack((near, b, far)),
            np.where(
                from_a[:, None], np.column_stack((a, near, far)), np.column_stack((a, near, c))
            ),
            np.where(
                from_a[:, None], np.column_stack((a, far, c)), np.column_stack((near, far, c))
            ),
        ]
        again += [np.ones(len(pair), dtype=bool)] * 3
    full = np.flatnonzero(count == 3)
    if len(full):
        a, b, c = corners[full].T
        ab, bc, ca = middles[full].T
        pieces += [
            np.column_stack((a, ab, ca)),
            np.column_stack((ab, b, bc)),
            np.column_stack((ca, bc, c)),
            np.column_stack((ab, bc, ca)),
        ]
        again += [np.ones(len(full), dtype=bool)] * 4
    return np.concatenate(pieces), (np.concatenate(again) if again else np.zeros(0, dtype=bool))
