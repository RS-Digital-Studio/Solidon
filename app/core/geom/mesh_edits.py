"""Örtliche Schritte am geschlossenen Dreiecksnetz: zusammenlegen, tauschen, teilen.

Drei Schritte, mit denen sich ein Netz verbessern lässt, ohne den Körper zu
ändern, den es beschreibt — jeder an einer einzelnen Kante:

* **Zusammenlegen** (:func:`collapse_short`): Die Halbkante ``v → w`` fällt weg,
  ``v`` geht in ``w`` auf. Es entsteht keine neue Koordinate; jede Ecke danach
  ist eine von vorher. Das räumt die Nadeln weg, die Marching Cubes neben eine
  Rasterecke legt (``blend``), und — nur innerhalb einer Ebene — die
  überzähligen Punkte, die das Teilen in einer großen Fläche hinterlässt.
* **Tauschen** (:func:`flip_in_planes`): Zwei Dreiecke, die **in einer Ebene**
  liegen, bekommen die andere Diagonale ihres Vierecks. Die Fläche bleibt
  dieselbe; nur ihre Aufteilung ändert sich.
* **Teilen** (:func:`split_long`): Eine zu lange Kante wird in der Mitte geteilt,
  beide Nachbardreiecke mit ihr. Der neue Punkt liegt auf der Kante, also auf
  der Oberfläche.

**Warum hier und nicht im Netzkern.** ``manifold3d`` teilt mit
``refine_to_length`` jede Kante auf die verlangte Länge, zieht im Inneren eines
Dreiecks aber Kanten, die länger sein können (``mesh_ops.uniform``), und sein
``simplify(0)`` legt eine ebene Fläche ohne jede Längengrenze zu Fächern
zusammen — an der Figur aus Weg 4 Kanten von 29 mm bei verlangten 1,2 (RM-671).
Die Schritte hier halten beides: Sie fragen vorher nach der Länge, und nur die
Ebene erlaubt einen Schritt, der sonst die Form berührte.

**In Runden unabhängiger Schritte.** Zwei Schritte derselben Runde teilen kein
Dreieck, auch nicht die Nachbarn, deren Halbkanten sie umhängen; dann ist jede
Prüfung einer Runde gültig, gleich in welcher Reihenfolge die Runde
ausgeführt wird. Wer zuerst darf, entscheidet eine feste Rangfolge (Länge, dann
Nummer der Halbkante) — dasselbe Netz gibt immer dasselbe Ergebnis. Die
nächste Runde fragt nur dort neu, wo sich etwas geändert hat oder ein
Kandidat warten musste.

**Plattformgleich** (``geom/CLAUDE.md``): Grundrechenarten, Wurzel und
Kreuzprodukt, nichts aus BLAS.

Das Netz ist geschlossen und gleichsinnig gewickelt; was das nicht ist, gibt
:func:`surface_of` als ``None`` zurück, und der Aufrufer lässt es, wie es ist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from app.core.geom.mesh import row_dots
from app.core.types import CancelToken

#: Wie viele Halbkanten ein Ring um eine Ecke höchstens hat, damit sie
#: zusammengelegt werden darf. Darüber — der Scheitel eines CAD-Fächers trägt
#: hundert Dreiecke — bleibt die Ecke stehen: Ein Ring dieser Größe ist keine
#: Nadel und kein überzähliger Punkt.
RING_LIMIT: Final = 64

#: Ab wann ein Viereck die andere Diagonale verdient: Summe der Kotangenten
#: der beiden gegenüberliegenden Winkel unter minus diesem Wert (Delaunay).
#: Nicht null — vier Punkte auf einem Kreis, wie im Quadrat jeder
#: Marching-Cubes-Wand, kippten sonst in jeder Runde hin und her.
DELAUNAY_MARGIN: Final = 1e-9

#: Höchstzahl der Runden je Schritt. Eine Absicherung, keine Erwartung:
#: Die Nadeln einer Verschmelzung sind nach zwölf bis zwanzig Runden fort.
EDIT_ROUNDS: Final = 64


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
    """Welche Kandidaten ihre Dreiecke und Ecken für sich haben.

    ``faces`` nennt je Kandidat die Dreiecke, die sein Schritt ändert oder
    deren Halbkanten er umhängt, ``corners`` die Ecken, die dabei einen
    Nachbarn verlieren (``-1`` ist leer); gewinnt, wer bei jedem davon den
    kleinsten Rang hat. Ohne die Ecken verlöre eine Ecke mit vier Nachbarn
    in einer Runde zwei und hinge danach an zwei Dreiecken.
    """
    groups = np.concatenate(
        (faces, np.where(corners >= 0, corners + len(surface.faces), -1)), axis=1
    )
    big = np.iinfo(np.int64).max
    best = np.full(len(surface.faces) + len(surface.vertices), big, dtype=np.int64)
    filled = groups >= 0
    owners = np.broadcast_to(rank[:, None], groups.shape)
    np.minimum.at(best, groups[filled], owners[filled])
    lowest = np.where(filled, best[np.where(filled, groups, 0)], big)
    return np.asarray(lowest.min(axis=1) == rank)


def _rank(*keys: np.ndarray) -> np.ndarray:
    """Rang nach den Schlüsseln, der letzte zuerst (wie ``np.lexsort``)."""
    order = np.lexsort(keys)
    rank = np.empty(len(order), dtype=np.int64)
    rank[order] = np.arange(len(order), dtype=np.int64)
    return rank


def _lengths(points: np.ndarray, first: np.ndarray, second: np.ndarray) -> np.ndarray:
    delta = points[second] - points[first]
    return np.sqrt(row_dots(delta, delta))


def _unit_normals(surface: Surface, faces: np.ndarray) -> np.ndarray:
    corners = surface.vertices[surface.faces[faces]]
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    size = np.sqrt(row_dots(cross, cross))
    normals = np.zeros_like(cross)
    usable = size > 0.0
    normals[usable] = cross[usable] / size[usable, None]
    return normals


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


def _edges_once(surface: Surface, halves: np.ndarray) -> np.ndarray:
    """Je Kante eine Halbkante, die kleinere Nummer — auch wenn nur ein Dreieck wartet."""
    return np.unique(np.minimum(halves, surface.partner[halves]))


def _connected(surface: Surface, first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Ob zwischen ``first[i]`` und ``second[i]`` schon eine Kante liegt — im ganzen Netz.

    Gefragt wird an allen lebenden Dreiecken, die eine der ersten Ecken
    tragen, nicht nur an der Auswahl: Eine Kante, die es außerhalb schon
    gibt, gäbe es nach dem Tausch zweimal.
    """
    if not len(first):
        return np.zeros(0, dtype=bool)
    width = len(surface.vertices)
    marked = np.zeros(width, dtype=bool)
    marked[first] = True
    rows = np.flatnonzero(surface.alive & marked[surface.faces].any(axis=1))
    corners = surface.faces[rows]
    starts = corners.reshape(-1)
    ends = np.roll(corners, -1, axis=1).reshape(-1)
    known = np.unique(np.minimum(starts, ends) * width + np.maximum(starts, ends))
    wanted = np.minimum(first, second) * width + np.maximum(first, second)
    if not len(known):
        return np.zeros(len(wanted), dtype=bool)
    place = np.minimum(np.searchsorted(known, wanted), len(known) - 1)
    return np.asarray(known[place] == wanted)


def collapse_short(
    surface: Surface,
    shortest: float,
    *,
    flat: float | None = None,
    longest: float | None = None,
    cancelled: CancelToken | None = None,
) -> int:
    """Legt Kanten unter ``shortest`` zusammen; zurück kommt, wie viele.

    Die Halbkante ``v → w`` fällt weg, ``v`` geht in ``w`` auf — mit ``w``s
    Koordinate, also ohne neue. Gültig ist ein Schritt, wenn

    * beide Ringe geschlossen sind und ``v`` und ``w`` genau die zwei Ecken
      gemeinsam haben, die ihren Dreiecken gegenüberliegen (sonst risse die
      Oberfläche oder bekäme eine dritte Fläche an einer Kante),
    * diese beiden danach noch drei Nachbarn haben und ``w`` auch,
    * kein Dreieck um ``v`` dabei umklappt,
    * mit ``flat``: alle Dreiecke um ``v`` in einer Ebene liegen (Abstand
      jeder Nachbarecke zur Ebene höchstens ``flat``) — dann deckt der Fächer
      um ``w`` dieselbe Fläche, und die Form bleibt, wie sie war,
    * mit ``longest``: keine neue Kante länger wird.
    """
    done = 0
    pending = np.array(surface.active & surface.alive, copy=True)
    for _round in range(EDIT_ROUNDS):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        halves = _candidate_halves(surface, pending)
        flat_faces = surface.faces.reshape(-1)
        tails = flat_faces[halves]
        heads = flat_faces[_next(halves)]
        length = _lengths(surface.vertices, tails, heads)
        short = length < shortest
        if not short.any():
            break
        h = halves[short]
        g = surface.partner[h]
        v, w, length = tails[short], heads[short], length[short]
        ring_v, closed_v = _rings(surface, h)
        ring_w, closed_w = _rings(surface, g)
        c = flat_faces[_next(_next(h))]
        d = flat_faces[_next(_next(g))]
        valence = surface.valence
        valid = closed_v & closed_w
        valid &= (valence[c] >= 4) & (valence[d] >= 4) & (valence[v] + valence[w] >= 7)
        valid &= _link_holds(surface, ring_v, ring_w)
        valid &= _keeps_its_faces(surface, h, g, v, w, ring_v, flat, longest)
        star = np.concatenate(
            (np.where(ring_v >= 0, ring_v // 3, -1), np.where(ring_w >= 0, ring_w // 3, -1)),
            axis=1,
        )
        pending = np.zeros(len(surface.faces), dtype=bool)
        if not valid.any():
            break
        idx = np.flatnonzero(valid)
        rank = _rank(h[idx], length[idx])
        corners = np.column_stack((v[idx], w[idx], c[idx], d[idx]))
        won = _claimed(surface, star[idx], corners, rank)
        chosen = idx[won]
        waiting = star[idx[~won]]
        pending[waiting[waiting >= 0]] = True
        _apply_collapses(surface, h[chosen], g[chosen], ring_v[chosen], c[chosen], d[chosen])
        touched = star[chosen]
        pending[touched[touched >= 0]] = True
        pending &= surface.alive
        done += len(chosen)
    return done


def _link_holds(surface: Surface, ring_v: np.ndarray, ring_w: np.ndarray) -> np.ndarray:
    """Ob ``v`` und ``w`` genau zwei Nachbarn gemeinsam haben.

    Jeder Nachbar steht in seinem Ring genau einmal; nach dem Sortieren der
    beiden Ringe zusammen ist jede doppelte Zahl ein gemeinsamer Nachbar.
    ``v`` und ``w`` selbst stehen je im anderen Ring und zählen nicht.
    """
    flat_faces = surface.faces.reshape(-1)
    rows = len(ring_v)
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
    return np.asarray(twice.sum(axis=1) == 2) if rows else np.zeros(0, dtype=bool)


def _keeps_its_faces(
    surface: Surface,
    h: np.ndarray,
    g: np.ndarray,
    v: np.ndarray,
    w: np.ndarray,
    ring_v: np.ndarray,
    flat: float | None,
    longest: float | None,
) -> np.ndarray:
    """Ob die Dreiecke um ``v`` den Schritt ``v → w`` überstehen (siehe :func:`collapse_short`)."""
    rows = len(h)
    if not rows:
        return np.zeros(0, dtype=bool)
    flat_faces = surface.faces.reshape(-1)
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
    if longest is not None:
        others = flat_faces[_next(ring_v[moving])]
        good &= _lengths(surface.vertices, w[owner], others) <= longest
    if flat is not None:
        # Bezug ist das Dreieck der Kante selbst; ohne Fläche hat es keine Ebene.
        normal = _unit_normals(surface, h // 3)
        others = flat_faces[_next(np.maximum(ring_v, 0))]
        offset = surface.vertices[others] - surface.vertices[v][:, None, :]
        apart = np.abs(
            offset[..., 0] * normal[:, None, 0]
            + offset[..., 1] * normal[:, None, 1]
            + offset[..., 2] * normal[:, None, 2]
        )
        level = np.where(filled, apart <= flat, True).all(axis=1)
        level &= row_dots(normal, normal) > 0.0
        # Und jedes Dreieck des Rings zeigt dieselbe Seite — auch die zwei, die wegfallen.
        every = np.broadcast_to(np.arange(rows)[:, None], ring_v.shape)[filled]
        aligned = row_dots(_unit_normals(surface, faces[filled]), normal[every]) > 0.0
        np.logical_and.at(level, every, aligned)
        good_flat = level
    else:
        good_flat = np.ones(rows, dtype=bool)
    result = np.ones(rows, dtype=bool)
    np.logical_and.at(result, owner, good)
    return np.asarray(result & good_flat)


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


def flip_in_planes(
    surface: Surface,
    flat: float,
    *,
    longest: float | None = None,
    only_long: bool = False,
    cancelled: CancelToken | None = None,
) -> int:
    """Tauscht Diagonalen zweier Dreiecke in einer Ebene; zurück kommt, wie viele.

    Getauscht wird nur, wo die vierte Ecke höchstens ``flat`` neben der Ebene
    des anderen Dreiecks liegt, beide gleich herum zeigen und das Viereck
    konvex ist — dann decken die neuen Dreiecke genau die alten. Ohne
    ``only_long`` nach Delaunay (die Summe der gegenüberliegenden Winkel über
    180 Grad), mit ``only_long`` jede Kante über ``longest``, deren andere
    Diagonale kürzer ist. Mit ``longest`` wird keine neue Kante länger.
    """
    done = 0
    pending = np.array(surface.active & surface.alive, copy=True)
    for _round in range(EDIT_ROUNDS):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        halves = _edges_once(surface, _candidate_halves(surface, pending))
        pending = np.zeros(len(surface.faces), dtype=bool)
        if not len(halves):
            break
        flat_faces = surface.faces.reshape(-1)
        h = halves
        g = surface.partner[h]
        a = flat_faces[h]
        b = flat_faces[_next(h)]
        c = flat_faces[_next(_next(h))]
        d = flat_faces[_next(_next(g))]
        points = surface.vertices
        side = _lengths(points, a, b)
        if only_long and longest is not None:
            keep = side > longest
            h, g, a, b, c, d, side = (
                h[keep],
                g[keep],
                a[keep],
                b[keep],
                c[keep],
                d[keep],
                side[keep],
            )
        across = _lengths(points, c, d)
        first = _unit_normals(surface, h // 3)
        second = _unit_normals(surface, g // 3)
        valid = c != d
        valid &= np.abs(row_dots(points[d] - points[a], first)) <= flat
        valid &= np.abs(row_dots(points[c] - points[a], second)) <= flat
        valid &= row_dots(first, second) > 0.0
        new_first = np.cross(points[a] - points[c], points[d] - points[c])
        new_second = np.cross(points[b] - points[d], points[c] - points[d])
        valid &= (row_dots(new_first, first) > 0.0) & (row_dots(new_second, first) > 0.0)
        valid &= (surface.valence[a] >= 4) & (surface.valence[b] >= 4)
        if longest is not None:
            valid &= across <= longest
        if only_long:
            valid &= across < side
            gain = across - side
        else:
            gain = _cotangents(points, a, b, c, d)
            valid &= gain < -DELAUNAY_MARGIN
        idx = np.flatnonzero(valid)
        if len(idx):
            idx = idx[~_connected(surface, c[idx], d[idx])]
        if not len(idx):
            break
        groups = np.column_stack(
            (
                h[idx] // 3,
                g[idx] // 3,
                surface.partner[_next(h[idx])] // 3,
                surface.partner[_prev(h[idx])] // 3,
                surface.partner[_next(g[idx])] // 3,
                surface.partner[_prev(g[idx])] // 3,
            )
        )
        groups = np.where(groups >= 0, groups, -1)
        rank = _rank(h[idx], gain[idx])
        won = _claimed(surface, groups, np.column_stack((a[idx], b[idx])), rank)
        chosen = idx[won]
        waiting = groups[~won]
        pending[waiting[waiting >= 0]] = True
        _apply_flips(surface, h[chosen], g[chosen])
        touched = groups[won]
        pending[touched[touched >= 0]] = True
        done += len(chosen)
    return done


def _cotangents(
    points: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray
) -> np.ndarray:
    """Die Summe der Kotangenten an ``c`` und ``d`` — negativ heißt: andere Diagonale."""
    ca, cb = points[a] - points[c], points[b] - points[c]
    da, db = points[a] - points[d], points[b] - points[d]
    at_c = np.cross(ca, cb)
    at_d = np.cross(da, db)
    sine_c = np.sqrt(row_dots(at_c, at_c))
    sine_d = np.sqrt(row_dots(at_d, at_d))
    with np.errstate(divide="ignore", invalid="ignore"):
        total = row_dots(ca, cb) / sine_c + row_dots(da, db) / sine_d
    return np.asarray(np.where(np.isfinite(total), total, np.inf))


def _apply_flips(surface: Surface, h: np.ndarray, g: np.ndarray) -> None:
    """Tauscht unabhängige Diagonalen: (a, b, c) und (b, a, d) werden (c, a, d) und (d, b, c)."""
    flat_faces = surface.faces.reshape(-1)
    a = flat_faces[h]
    b = flat_faces[_next(h)]
    c = flat_faces[_next(_next(h))]
    d = flat_faces[_next(_next(g))]
    bc = surface.partner[_next(h)]
    ca = surface.partner[_prev(h)]
    ad = surface.partner[_next(g)]
    db = surface.partner[_prev(g)]
    first = h // 3
    second = g // 3
    surface.faces[first] = np.column_stack((c, a, d))
    surface.faces[second] = np.column_stack((d, b, c))
    base_first = 3 * first
    base_second = 3 * second
    _pair(surface, base_first, ca)
    _pair(surface, base_first + 1, ad)
    _pair(surface, base_first + 2, base_second + 2)
    _pair(surface, base_second, db)
    _pair(surface, base_second + 1, bc)
    np.subtract.at(surface.valence, a, 1)
    np.subtract.at(surface.valence, b, 1)
    np.add.at(surface.valence, c, 1)
    np.add.at(surface.valence, d, 1)


def _pair(surface: Surface, one: np.ndarray, other: np.ndarray) -> None:
    """Macht zwei Halbkanten zu Partnern; ``-1`` bleibt unbekannt."""
    surface.partner[one] = other
    known = other >= 0
    surface.partner[other[known]] = one[known]


def split_long(surface: Surface, longest: float, *, cancelled: CancelToken | None = None) -> int:
    """Teilt Kanten über ``longest`` in der Mitte; zurück kommt, wie viele.

    Längste Kante zuerst (Rivara): Geteilt wird eine Kante, die in **beiden**
    Dreiecken eine längste ist. Die längste des ganzen Netzes ist das immer,
    also geht es in jeder Runde voran, und die Winkel der Teile werden nicht
    beliebig spitz. Der neue Punkt ist die Mitte der Kante und liegt damit auf
    der Oberfläche.
    """
    done = 0
    pending = np.array(surface.active & surface.alive, copy=True)
    for _round in range(EDIT_ROUNDS):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        halves = _edges_once(surface, _candidate_halves(surface, pending))
        pending = np.zeros(len(surface.faces), dtype=bool)
        if not len(halves):
            break
        flat_faces = surface.faces.reshape(-1)
        points = surface.vertices
        side = _lengths(points, flat_faces[halves], flat_faces[_next(halves)])
        long_side = side > longest
        if not long_side.any():
            break
        twins = surface.partner[halves]
        # Die längste Seite beider Dreiecke jeder Kante, auch des wartenden.
        faces = np.unique(np.concatenate((halves // 3, twins // 3)))
        all_sides = _face_halves(faces).reshape(-1)
        lengths = _lengths(points, flat_faces[all_sides], flat_faces[_next(all_sides)])
        widest = np.zeros(len(surface.faces), dtype=np.float64)
        widest[faces] = lengths.reshape(-1, 3).max(axis=1)
        terminal = long_side & (side >= widest[halves // 3]) & (side >= widest[twins // 3])
        idx = np.flatnonzero(terminal)
        if not len(idx):
            break
        h = halves[idx]
        g = twins[idx]
        groups = np.column_stack(
            (
                h // 3,
                g // 3,
                surface.partner[_next(h)] // 3,
                surface.partner[_prev(h)] // 3,
                surface.partner[_next(g)] // 3,
                surface.partner[_prev(g)] // 3,
            )
        )
        groups = np.where(groups >= 0, groups, -1)
        rank = _rank(h, -side[idx])
        won = _claimed(surface, groups, np.empty((len(h), 0), dtype=np.int64), rank)
        waiting = groups[~won]
        pending[waiting[waiting >= 0]] = True
        touched = groups[won]
        pending[touched[touched >= 0]] = True
        added = _apply_splits(surface, h[won], g[won])
        pending = np.concatenate((pending, np.ones(added, dtype=bool)))
        done += int(won.sum())
    return done


def _apply_splits(surface: Surface, h: np.ndarray, g: np.ndarray) -> int:
    """Teilt unabhängige Kanten in der Mitte; zurück kommt die Zahl neuer Dreiecke."""
    count = len(h)
    if not count:
        return 0
    flat_faces = surface.faces.reshape(-1)
    a = flat_faces[h]
    b = flat_faces[_next(h)]
    c = flat_faces[_next(_next(h))]
    d = flat_faces[_next(_next(g))]
    bc = surface.partner[_next(h)]
    ca = surface.partner[_prev(h)]
    ad = surface.partner[_next(g)]
    db = surface.partner[_prev(g)]
    middle = len(surface.vertices) + np.arange(count, dtype=np.int64)
    halfway = (surface.vertices[a] + surface.vertices[b]) / 2.0
    surface.vertices = np.concatenate((surface.vertices, halfway))
    surface.valence = np.concatenate((surface.valence, np.full(count, 4, dtype=np.int64)))
    np.add.at(surface.valence, c, 1)
    np.add.at(surface.valence, d, 1)
    first = h // 3
    second = g // 3
    third = len(surface.faces) + np.arange(count, dtype=np.int64)
    fourth = third + count
    surface.faces[first] = np.column_stack((a, middle, c))
    surface.faces[second] = np.column_stack((b, middle, d))
    surface.faces = np.concatenate(
        (surface.faces, np.column_stack((middle, b, c)), np.column_stack((middle, a, d)))
    )
    surface.partner = np.concatenate((surface.partner, np.full(6 * count, -1, dtype=np.int64)))
    surface.alive = np.concatenate((surface.alive, np.ones(2 * count, dtype=bool)))
    surface.active = np.concatenate((surface.active, np.ones(2 * count, dtype=bool)))
    one, two, three, four = 3 * first, 3 * second, 3 * third, 3 * fourth
    # (a, m, c): a→m mit (m, a, d)·m→a, m→c mit (m, b, c)·c→m, c→a wie vorher.
    _pair(surface, one, four)
    _pair(surface, one + 1, three + 2)
    _pair(surface, one + 2, ca)
    # (m, b, c): m→b mit (b, m, d)·b→m, b→c wie vorher.
    _pair(surface, three, two)
    _pair(surface, three + 1, bc)
    # (b, m, d): m→d mit (m, a, d)·d→m, d→b wie vorher.
    _pair(surface, two + 1, four + 2)
    _pair(surface, two + 2, db)
    # (m, a, d): a→d wie vorher.
    _pair(surface, four + 1, ad)
    return 2 * count
