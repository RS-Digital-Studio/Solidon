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
ausgeführt wird. Wer zuerst darf, entscheidet eine feste, über das Netz
gestreute Rangfolge (:func:`_scattered`), und gewählt wird, bis kein freier
Kandidat mehr übrig ist (:func:`_claimed`) — dasselbe Netz gibt immer dasselbe
Ergebnis. Die nächste Runde fragt nur dort neu, wo sich etwas geändert hat
oder ein Kandidat warten musste.

**Plattformgleich** (``geom/CLAUDE.md``): Grundrechenarten, Wurzel und
Kreuzprodukt, nichts aus BLAS.

Das Netz ist geschlossen und gleichsinnig gewickelt; was das nicht ist, gibt
:func:`surface_of` als ``None`` zurück, und der Aufrufer lässt es, wie es ist.
"""

from __future__ import annotations

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

#: Ab wann ein Viereck die andere Diagonale verdient: Summe der Kotangenten
#: der beiden gegenüberliegenden Winkel unter minus diesem Wert (Delaunay).
#: Nicht null — vier Punkte auf einem Kreis, wie im Quadrat jeder
#: Marching-Cubes-Wand, kippten sonst in jeder Runde hin und her.
DELAUNAY_MARGIN: Final = 1e-9

#: Höchstzahl der Runden je Schritt. Eine Absicherung, keine Erwartung:
#: Die Nadeln einer Verschmelzung sind nach zwölf bis zwanzig Runden fort.
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


def sharp_triangles(
    first: np.ndarray, second: np.ndarray, third: np.ndarray, squared_cosine: float
) -> np.ndarray:
    """Ob ein Dreieck eine Ecke hat, deren Kosinus im Quadrat über ``squared_cosine`` liegt."""
    return triangle_shapes(first, second, third, squared_cosine)[1]


def triangle_shapes(
    first: np.ndarray, second: np.ndarray, third: np.ndarray, squared_cosine: float
) -> tuple[np.ndarray, np.ndarray]:
    """Je Dreieck das Quadrat seiner längsten Seite und ob es spitz ist (:func:`sharp_triangles`).

    Ohne Wurzel und ohne Winkelfunktion (``kern.md``): Eine Ecke ist spitz, wenn
    das Skalarprodukt ihrer Seiten positiv ist und sein Quadrat über
    ``squared_cosine`` mal dem Produkt der quadrierten Seitenlängen liegt. Die
    Ecken kommen als drei Felder ``(k, 3)``.
    """
    sides = (second - first, third - second, first - third)
    squared = [row_dots(side, side) for side in sides]
    sharp = np.zeros(len(first), dtype=bool)
    for corner in range(3):
        out, back = sides[corner], sides[corner - 1]
        lean = -row_dots(out, back)
        sharp |= (lean > 0.0) & (
            lean * lean > squared_cosine * squared[corner] * squared[corner - 1]
        )
    return np.maximum(np.maximum(squared[0], squared[1]), squared[2]), sharp


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
    """Je Kante eine Halbkante, die kleinere Nummer — auch wenn nur ein Dreieck wartet.

    Über eine Markierung je Halbkante, nicht über ``np.unique``: Das rechnete an
    drei Millionen Kanten drei Sekunden, die Markierung einen Bruchteil davon,
    in derselben aufsteigenden Folge.
    """
    seen = np.zeros(len(surface.partner), dtype=bool)
    seen[np.minimum(halves, surface.partner[halves])] = True
    return np.flatnonzero(seen)


def _near(faces: np.ndarray, alive: np.ndarray | None, wanted: np.ndarray) -> np.ndarray:
    """Die lebenden Dreiecke mit einer Ecke der Dreiecke ``wanted`` — als Nummern.

    Ein Tausch fragt, ob es seine neue Kante schon gibt, auch außerhalb der
    Auswahl (:func:`_joined`); eine Kante an einer Ecke der Auswahl liegt in
    einem dieser Dreiecke. Getauscht wird nur in der Auswahl, ihre Ecken bleiben
    dieselben, also gilt die Liste für alle Runden. Alle Dreiecke in jeder Runde
    zu lesen kostete an einer CAD-Seitenablage aus ``F:\\3D Dateien`` (600 000
    Dreiecke, 26 Runden) 0,55 s.
    """
    marked = np.zeros(int(faces.max(initial=-1)) + 1, dtype=bool)
    marked[faces[wanted].reshape(-1)] = True
    touching = marked[faces[:, 0]] | marked[faces[:, 1]] | marked[faces[:, 2]]
    if alive is not None:
        touching &= alive
    return np.flatnonzero(touching)


def _joined(faces: np.ndarray, first: np.ndarray, second: np.ndarray, width: int) -> np.ndarray:
    """Ob zwischen ``first[i]`` und ``second[i]`` schon eine Kante in einem der ``faces`` liegt.

    Eine solche Kante liegt in einem Dreieck mit einer ersten **und** einer
    zweiten Ecke, und sie verbindet die beiden; nur solche Kanten werden
    sortiert. ``width`` ist die Zahl der Ecken.
    """
    if not len(first):
        return np.zeros(0, dtype=bool)
    starting = np.zeros(width, dtype=bool)
    starting[first] = True
    ending = np.zeros(width, dtype=bool)
    ending[second] = True
    candidates = faces[starting[faces[:, 0]] | starting[faces[:, 1]] | starting[faces[:, 2]]]
    ends_too = ending[candidates[:, 0]] | ending[candidates[:, 1]] | ending[candidates[:, 2]]
    corners = candidates[ends_too]
    starts = corners.reshape(-1)
    ends = np.roll(corners, -1, axis=1).reshape(-1)
    bridging = (starting[starts] & ending[ends]) | (starting[ends] & ending[starts])
    starts, ends = starts[bridging], ends[bridging]
    known = np.sort(np.minimum(starts, ends) * width + np.maximum(starts, ends))
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
    sharp: float | None = None,
    asked: np.ndarray | None = None,
    cancelled: CancelToken | None = None,
) -> int:
    """Legt Kanten unter ``shortest`` zusammen; zurück kommt, wie viele.

    Die Halbkante ``v → w`` fällt weg, ``v`` geht in ``w`` auf — mit ``w``s
    Koordinate, also ohne neue. Gültig ist ein Schritt, wenn

    * beide Ringe geschlossen sind, jeder um seine Ecke ganz herum, und ``v``
      und ``w`` genau die zwei Ecken gemeinsam haben, die ihren Dreiecken
      gegenüberliegen (sonst risse die Oberfläche oder bekäme eine dritte
      Fläche an einer Kante),
    * diese beiden danach noch drei Nachbarn haben und ``w`` auch,
    * kein Dreieck um ``v`` dabei umklappt,
    * mit ``flat``: alle Dreiecke um ``v`` in einer Ebene liegen (Abstand
      jeder Nachbarecke zur Ebene höchstens ``flat``) — dann deckt der Fächer
      um ``w`` dieselbe Fläche, und die Form bleibt, wie sie war,
    * mit ``longest``: keine neue Kante länger wird,
    * mit ``sharp`` (Quadrat eines Kosinus, :func:`sharp_triangles`): danach
      weniger spitze Dreiecke um ``v`` stehen als vorher — der Schritt räumt
      eine Nadel weg, statt nur Punkte zu sparen.

    ``asked`` nennt die Dreiecke, deren Kanten die erste Runde fragt; ohne sind
    es alle aktiven. Geprüft wird vom Billigen zum Teuren: erst Länge, Wertigkeit
    und — mit ``flat`` — die Lage der vierten Ecke, dann der Ring um ``v``, und
    nur, wer das alles besteht, bekommt den Ring um ``w``.
    """
    done = 0
    pending = np.array(surface.active & surface.alive, copy=True)
    if asked is not None:
        pending &= np.asarray(asked, dtype=bool)
    for _round in range(EDIT_ROUNDS):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if sharp is None:
            halves = _candidate_halves(surface, pending)
        else:
            halves = _needle_sides(surface, pending, sharp)
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
        if flat is not None:
            keep &= _level_with(surface, h, d, g, flat)
        h, g, v, w, c, d = (part[keep] for part in (h, g, v, w, c, d))
        if not len(h):
            break
        rows, ring_v, ring_w = _collapsible(surface, h, g, v, w, c, d, flat, longest, sharp)
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
    surface: Surface,
    h: np.ndarray,
    g: np.ndarray,
    v: np.ndarray,
    w: np.ndarray,
    c: np.ndarray,
    d: np.ndarray,
    flat: float | None,
    longest: float | None,
    sharp: float | None,
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
        keep &= _keeps_its_faces(
            surface, h[rows], g[rows], v[rows], w[rows], ring_v, flat, longest, sharp
        )
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


def _needle_sides(surface: Surface, pending: np.ndarray, sharp: float) -> np.ndarray:
    """Die kürzeste Seite jedes spitzen Dreiecks unter ``pending``, in beiden Richtungen.

    Zusammengelegt verschwindet mit ihr die Nadel; jede andere Kante eines
    spitzen Dreiecks ließe es stehen oder machte ein Nachbardreieck zur Nadel.
    Gleich lange Seiten entscheidet ihr Platz im Dreieck, die erste zuerst.
    """
    faces = np.flatnonzero(pending & surface.alive & surface.active)
    corners = surface.vertices[surface.faces[faces]]
    needles = sharp_triangles(corners[:, 0], corners[:, 1], corners[:, 2], sharp)
    faces, corners = faces[needles], corners[needles]
    sides = np.roll(corners, -1, axis=1) - corners
    squared = np.column_stack([row_dots(sides[:, k], sides[:, k]) for k in range(3)])
    halves = 3 * faces + np.argmin(squared, axis=1)
    twins = surface.partner[halves]
    known = twins >= 0
    halves, twins = halves[known], twins[known]
    usable = surface.alive[twins // 3] & surface.active[twins // 3]
    return np.unique(np.concatenate((halves[usable], twins[usable])))


def _level_with(
    surface: Surface, h: np.ndarray, d: np.ndarray, g: np.ndarray, flat: float
) -> np.ndarray:
    """Ob die Ecke ``d`` hinter der Kante in der Ebene des Dreiecks von ``h`` liegt.

    Eine Vorprüfung für ``flat`` in :func:`collapse_short`, ohne Ring: ``d`` ist
    ein Nachbar von ``v``, das Dreieck von ``g`` liegt im Ring um ``v``. Liegt
    eines davon schief, scheitert die volle Prüfung in :func:`_keeps_its_faces`
    ohnehin — beide fragen :func:`_in_plane` und :func:`_facing_along`.
    """
    normal = _unit_normals(surface, h // 3)
    offset = surface.vertices[d] - surface.vertices[surface.faces.reshape(-1)[h]]
    level = _in_plane(offset, normal, flat) & _facing_along(normal, normal)
    return np.asarray(level & _facing_along(_unit_normals(surface, g // 3), normal))


def _in_plane(offset: np.ndarray, normal: np.ndarray, flat: float) -> np.ndarray:
    """Ob ``offset`` höchstens ``flat`` aus der Ebene mit der Einheitsnormale ``normal`` ragt.

    Die Ebenenfrage beim Zusammenlegen, an einer Ecke (:func:`_level_with`) wie
    am ganzen Ring (:func:`_keeps_its_faces`, ``normal[:, None, :]``): eine
    Rechnung, damit die Vorprüfung nie anders antwortet als die volle (Review F).
    """
    return np.asarray(np.abs(row_dots(offset, normal)) <= flat)


def _facing_along(normals: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Ob ``normals`` zur selben Seite zeigen wie ``normal`` — ohne Fläche zeigt keine dorthin."""
    return np.asarray(row_dots(normals, normal) > 0.0)


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
    surface: Surface,
    h: np.ndarray,
    g: np.ndarray,
    v: np.ndarray,
    w: np.ndarray,
    ring_v: np.ndarray,
    flat: float | None,
    longest: float | None,
    sharp: float | None = None,
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
    if sharp is not None:
        # Spitz vorher: jedes Dreieck des Rings, auch die zwei, die wegfallen;
        # spitz danach: die verschobenen.
        every = np.broadcast_to(np.arange(rows)[:, None], ring_v.shape)[filled]
        old = surface.vertices[surface.faces[faces[filled]]]
        was = np.bincount(
            every, sharp_triangles(old[:, 0], old[:, 1], old[:, 2], sharp), minlength=rows
        )
        now = np.bincount(
            owner, sharp_triangles(moved[:, 0], moved[:, 1], moved[:, 2], sharp), minlength=rows
        )
        fewer = now < was
    else:
        fewer = np.ones(rows, dtype=bool)
    if flat is not None:
        # Bezug ist das Dreieck der Kante selbst; ohne Fläche hat es keine Ebene.
        normal = _unit_normals(surface, h // 3)
        others = flat_faces[_next(np.maximum(ring_v, 0))]
        offset = surface.vertices[others] - surface.vertices[v][:, None, :]
        level = np.where(filled, _in_plane(offset, normal[:, None, :], flat), True).all(axis=1)
        level &= _facing_along(normal, normal)
        # Und jedes Dreieck des Rings zeigt dieselbe Seite — auch die zwei, die wegfallen.
        every = np.broadcast_to(np.arange(rows)[:, None], ring_v.shape)[filled]
        aligned = _facing_along(_unit_normals(surface, faces[filled]), normal[every])
        np.logical_and.at(level, every, aligned)
        good_flat = level
    else:
        good_flat = np.ones(rows, dtype=bool)
    result = np.ones(rows, dtype=bool)
    np.logical_and.at(result, owner, good)
    return np.asarray(result & good_flat & fewer)


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


def _flippable(
    points: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray, flat: float
) -> np.ndarray:
    """Ob (a, b, c) und (b, a, d) ihre Diagonale tauschen dürfen, ohne die Form zu ändern.

    Die vierte Ecke liegt höchstens ``flat`` neben der Ebene des anderen
    Dreiecks, beide zeigen gleich herum, und das Viereck ist konvex — dann
    decken (c, a, d) und (d, b, c) genau die alten. Ohne Einheitsnormale: Der
    Abstand zur Ebene wird quadriert mit dem Quadrat der Normalenlänge
    verglichen, die Richtungen nur nach ihrem Vorzeichen; ein Dreieck ohne
    Fläche zeigt nirgendwohin und tauscht nicht.
    """
    return _flippable_at(points[a], points[b], points[c], points[d], c != d, flat)


def _flippable_at(
    at_a: np.ndarray,
    at_b: np.ndarray,
    at_c: np.ndarray,
    at_d: np.ndarray,
    distinct: np.ndarray,
    flat: float,
) -> np.ndarray:
    """:func:`_flippable` an schon gelesenen Ecken; ``distinct``: ob c und d verschieden sind."""
    valid, first = _coplanar(at_a, at_b, at_c, at_d, flat)
    valid &= distinct
    new_first = np.cross(at_a - at_c, at_d - at_c)
    new_second = np.cross(at_b - at_d, at_c - at_d)
    valid &= (row_dots(new_first, first) > 0.0) & (row_dots(new_second, first) > 0.0)
    return np.asarray(valid)


def _coplanar(
    at_a: np.ndarray, at_b: np.ndarray, at_c: np.ndarray, at_d: np.ndarray, flat: float
) -> tuple[np.ndarray, np.ndarray]:
    """Ob (a, b, c) und (b, a, d) auf ``flat`` genau in einer Ebene liegen und gleich herum zeigen.

    Zurück kommt dazu die ungekürzte Normale des ersten Dreiecks. Ohne Fläche
    zeigt ein Dreieck nirgendwohin und liegt in keiner Ebene.
    """
    first = np.cross(at_b - at_a, at_c - at_a)
    second = np.cross(at_a - at_b, at_d - at_b)
    return _level_pair(at_a, at_c, at_d, first, second, flat), first


def _level_pair(
    at_a: np.ndarray,
    at_c: np.ndarray,
    at_d: np.ndarray,
    first: np.ndarray,
    second: np.ndarray,
    flat: float,
) -> np.ndarray:
    """:func:`_coplanar` mit den Normalen ``first`` von (a, b, c) und ``second`` von (b, a, d).

    Ungekürzt, wie ``np.cross`` sie gibt. Eine Rechnung für den Tausch und für
    :func:`plane_measures`, das die Normale je Dreieck einmal rechnet: Was eine
    Ebene ist, entscheidet hier, nicht an zwei Stellen (Review F).
    """
    tolerance = flat * flat
    beside = row_dots(at_d - at_a, first)
    level = beside * beside <= tolerance * row_dots(first, first)
    beside = row_dots(at_c - at_a, second)
    level &= beside * beside <= tolerance * row_dots(second, second)
    level &= row_dots(first, second) > 0.0
    return np.asarray(level)


def plane_measures(
    vertices: np.ndarray, faces: np.ndarray, flat: float
) -> tuple[np.ndarray, np.ndarray]:
    """Je Dreieck zwei Maße seiner Ebene: ihre Breite und die mittlere Fläche ihrer Dreiecke.

    Eine Ebene sind die Dreiecke, die über Kanten zusammenhängen und auf
    ``flat`` genau in einer Ebene liegen — dieselbe Frage wie vor einem Tausch
    (:func:`_level_pair`), nur mit der Normale jedes Dreiecks einmal gerechnet.
    Ihre Breite ist zweimal ihre Fläche durch ihren Umfang: Ein Streifen der
    Breite ``b`` hat die Breite ``b``, eine Kreisscheibe ihren Radius. Eine
    Kante mit mehr oder weniger als zwei Dreiecken trennt.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    points = np.asarray(vertices, dtype=np.float64)
    corners = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    count = len(corners)
    tails = corners.reshape(-1)
    heads = np.roll(corners, -1, axis=1).reshape(-1)
    opposite = np.roll(corners, -2, axis=1).reshape(-1)
    width = len(points)
    codes = np.minimum(tails, heads) * width + np.maximum(tails, heads)
    order = np.argsort(codes, kind="stable")
    ordered = codes[order]
    starts = np.flatnonzero(np.concatenate(([True], ordered[1:] != ordered[:-1])))
    sizes = np.diff(np.concatenate((starts, [len(ordered)])))
    pairs = starts[sizes == 2]
    one, other = order[pairs], order[pairs + 1]
    a, c, d = tails[one], opposite[one], opposite[other]
    first, second = one // 3, other // 3
    normals = np.cross(
        points[corners[:, 1]] - points[corners[:, 0]], points[corners[:, 2]] - points[corners[:, 0]]
    )
    squared = row_dots(normals, normals)
    inner = (tails[other] == heads[one]) & (heads[other] == a) & (c != d)
    inner &= _level_pair(points[a], points[c], points[d], normals[first], normals[second], flat)
    joined_one, joined_other = one[inner], other[inner]
    graph = coo_matrix(
        (np.ones(len(joined_one)), (joined_one // 3, joined_other // 3)), shape=(count, count)
    )
    _number, labels = connected_components(graph, directed=False)
    outer = np.ones(3 * count, dtype=bool)
    outer[joined_one] = False
    outer[joined_other] = False
    rim = np.flatnonzero(outer)
    sides = points[heads[rim]] - points[tails[rim]]
    area = np.bincount(labels, weights=np.sqrt(squared) / 2.0)
    around = np.bincount(
        labels[rim // 3], weights=np.sqrt(row_dots(sides, sides)), minlength=len(area)
    )
    breadth = np.full(len(area), np.inf)
    np.divide(2.0 * area, around, out=breadth, where=around > 0.0)
    mean = area / np.bincount(labels, minlength=len(area))
    return np.asarray(breadth[labels]), np.asarray(mean[labels])


def flip_long(
    vertices: np.ndarray,
    faces: np.ndarray,
    longest: float,
    flat: float,
    *,
    suspects: np.ndarray | None = None,
    cancelled: CancelToken | None = None,
) -> tuple[np.ndarray, int]:
    """Tauscht jede Kante über ``longest`` gegen die kürzere Diagonale, wo das die Form hält.

    Zurück kommen die Dreiecke in derselben Folge und wie viele getauscht
    wurden. Getauscht wird wie in :func:`flip_in_planes` nur in einer Ebene
    (:func:`_flippable`), und die neue Diagonale ist kürzer als die alte und
    nicht über ``longest``. ``suspects`` nennt die Dreiecke, die eine zu lange
    Seite haben können; eine zu lange Kante hat beide unter ihnen.

    **Ohne Halbkanten, als Feldrechnung**: Je Runde werden die zu langen Seiten
    gepaart, alle geprüft und je Dreieck höchstens ein Tausch genommen, die
    längste Kante zuerst. An der Kugel aus §31 lagen nach dem Teilen im Kern
    245 760 solche Kanten im Inneren der geteilten Dreiecke; über die Runden
    mit Halbkanten kostete ihr Tausch 2,4 s.
    """
    points = np.asarray(vertices, dtype=np.float64)
    corners = np.array(faces, dtype=np.int64, copy=True).reshape(-1, 3)
    rows = np.flatnonzero(
        np.ones(len(corners), dtype=bool) if suspects is None else np.asarray(suspects, dtype=bool)
    )
    valence = np.bincount(corners.reshape(-1), minlength=len(points)).astype(np.int64)
    limit = longest * longest
    width = len(points)
    done = 0
    for _round in range(EDIT_ROUNDS):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        picked = corners[rows]
        delta = points[np.roll(picked, -1, axis=1)] - points[picked]
        row, side = np.nonzero(row_dots(delta, delta) > limit)
        if not len(row):
            break
        face = rows[row]
        tail, head = picked[row, side], picked[row, (side + 1) % 3]
        codes = np.minimum(tail, head) * width + np.maximum(tail, head)
        order = np.argsort(codes, kind="stable")
        ordered = codes[order]
        twin = np.flatnonzero(ordered[1:] == ordered[:-1])
        alone = (twin == 0) | (ordered[np.maximum(twin - 1, 0)] != ordered[twin])
        alone &= (twin + 2 >= len(ordered)) | (
            ordered[np.minimum(twin + 2, len(ordered) - 1)] != ordered[twin]
        )
        one, other = order[twin[alone]], order[twin[alone] + 1]
        f, g = face[one], face[other]
        a, b = tail[one], head[one]
        c = picked[row[one], (side[one] + 2) % 3]
        d = picked[row[other], (side[other] + 2) % 3]
        at_a, at_b, at_c, at_d = points[a], points[b], points[c], points[d]
        across = at_c - at_d
        span = at_b - at_a
        reach = row_dots(across, across)
        length = row_dots(span, span)
        valid = (tail[other] == b) & (head[other] == a)
        valid &= (valence[a] >= 4) & (valence[b] >= 4)
        valid &= (reach <= limit) & (reach < length)
        valid &= _flippable_at(at_a, at_b, at_c, at_d, c != d, flat)
        idx = np.flatnonzero(valid)
        if len(idx):
            idx = idx[~_joined(corners, c[idx], d[idx], width)]
        if not len(idx):
            break
        rank = _rank(codes[one][idx], -length[idx])
        best = np.full(len(corners), np.iinfo(np.int64).max, dtype=np.int64)
        np.minimum.at(best, f[idx], rank)
        np.minimum.at(best, g[idx], rank)
        won = (best[f[idx]] == rank) & (best[g[idx]] == rank)
        chosen, rank = idx[won], rank[won]
        # Jeder Tausch nimmt a und b einen Nachbarn. Fiele eine Ecke dabei in einer
        # Runde unter drei, tauscht an ihr nur der mit dem kleinsten Rang.
        losing = np.bincount(np.concatenate((a[chosen], b[chosen])), minlength=width)
        short = valence - losing < 3
        if short.any():
            first_rank = np.full(width, np.iinfo(np.int64).max, dtype=np.int64)
            np.minimum.at(first_rank, a[chosen], rank)
            np.minimum.at(first_rank, b[chosen], rank)
            keep = ~short[a[chosen]] | (first_rank[a[chosen]] == rank)
            keep &= ~short[b[chosen]] | (first_rank[b[chosen]] == rank)
            chosen = chosen[keep]
        # Gefragt wird in der nächsten Runde nur, wo noch eine lange Seite stehen
        # kann: an einem ungetauschten Dreieck mit langer Seite, und an einem
        # getauschten, das eine lange Außenseite des Vierecks erbt.
        long_sides = np.zeros(corners.shape, dtype=bool)
        long_sides[face, side] = True
        pending = np.zeros(len(corners), dtype=bool)
        pending[face] = True
        first_side, other_side = side[one][chosen], side[other][chosen]
        f, g = f[chosen], g[chosen]
        pending[f] = long_sides[f, (first_side + 2) % 3] | long_sides[g, (other_side + 1) % 3]
        pending[g] = long_sides[g, (other_side + 2) % 3] | long_sides[f, (first_side + 1) % 3]
        rows = np.flatnonzero(pending)
        a, b, c, d = a[chosen], b[chosen], c[chosen], d[chosen]
        corners[f] = np.column_stack((c, a, d))
        corners[g] = np.column_stack((d, b, c))
        np.subtract.at(valence, a, 1)
        np.subtract.at(valence, b, 1)
        np.add.at(valence, c, 1)
        np.add.at(valence, d, 1)
        done += len(chosen)
    return corners, done


def flip_in_planes(
    surface: Surface,
    flat: float,
    *,
    longest: float | None = None,
    asked: np.ndarray | None = None,
    cancelled: CancelToken | None = None,
) -> int:
    """Tauscht Diagonalen zweier Dreiecke in einer Ebene nach Delaunay; zurück kommt, wie viele.

    Getauscht wird, wo die Summe der gegenüberliegenden Winkel über 180 Grad
    liegt und das Viereck es formtreu erlaubt (:func:`_flippable`). Mit
    ``longest`` wird keine neue Kante länger.

    ``asked`` nennt die Dreiecke, deren Kanten die erste Runde fragt; ohne sind
    es alle aktiven. Zuerst gefragt wird Delaunay — daran scheitern die meisten.
    """
    done = 0
    pending = np.array(surface.active & surface.alive, copy=True)
    if asked is not None:
        pending &= np.asarray(asked, dtype=bool)
    near = _near(surface.faces, surface.alive, surface.active & surface.alive)
    for _round in range(EDIT_ROUNDS):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        halves = _edges_once(surface, _candidate_halves(surface, pending))
        pending = np.zeros(len(surface.faces), dtype=bool)
        if not len(halves):
            break
        flat_faces = surface.faces.reshape(-1)
        points = surface.vertices
        h = halves
        g = surface.partner[h]
        a = flat_faces[h]
        b = flat_faces[_next(h)]
        c = flat_faces[_next(_next(h))]
        d = flat_faces[_next(_next(g))]
        gain = _cotangents(points, a, b, c, d)
        better = gain < -DELAUNAY_MARGIN
        h, g, a, b, c, d, gain = (
            h[better],
            g[better],
            a[better],
            b[better],
            c[better],
            d[better],
            gain[better],
        )
        valid = (surface.valence[a] >= 4) & (surface.valence[b] >= 4)
        valid &= _flippable(points, a, b, c, d, flat)
        if longest is not None:
            valid &= _lengths(points, c, d) <= longest
        idx = np.flatnonzero(valid)
        if len(idx):
            idx = idx[~_joined(surface.faces[near], c[idx], d[idx], len(surface.vertices))]
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
        rank = _rank(_scattered(h[idx]))
        won = _claimed(surface, groups, np.column_stack((a[idx], b[idx])), rank)
        chosen = idx[won]
        # Wer verliert, wird mit seinen zwei Dreiecken neu gefragt; was ein Gewinner
        # ändert oder umhängt, ganz.
        pending[groups[~won][:, :2].reshape(-1)] = True
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


def split_long(
    vertices: np.ndarray,
    faces: np.ndarray,
    longest: float,
    *,
    suspects: np.ndarray | None = None,
    cancelled: CancelToken | None = None,
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
    alle. Gemessen werden im ersten Durchgang nur sie, danach nur die neuen
    Teile — eine zu lange Kante hat beide Dreiecke unter den Verdächtigen.
    Zurück kommen Ecken, Dreiecke und je Dreieck seine Nummer im Eingang,
    ``-1`` für ein geteiltes: Wer über die Dreiecke schon etwas weiß, muss nur
    an den neuen nachmessen.
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
        rows = np.flatnonzero(asked)
        heads = np.roll(corners[rows], -1, axis=1)
        delta = points[heads] - points[corners[rows]]
        found = row_dots(delta, delta) > limit
        if not found.any():
            break
        marked = np.zeros(corners.shape, dtype=bool)
        marked[rows] = found
        width = len(points)
        tails, ends = corners[rows][found], heads[found]
        codes = np.minimum(tails, ends) * width + np.maximum(tails, ends)
        unique, inverse = np.unique(codes, return_inverse=True)
        first, second = unique // width, unique % width
        middles = np.full(corners.shape, -1, dtype=np.int64)
        middles[marked] = width + np.asarray(inverse, dtype=np.int64).reshape(-1)
        points = np.concatenate((points, (points[first] + points[second]) / 2.0))
        unsplit = np.flatnonzero(~marked.any(axis=1))
        corners = _split_by_pattern(points, corners, middles)
        origin = np.concatenate(
            (origin[unsplit], np.full(len(corners) - len(unsplit), -1, dtype=np.int64))
        )
        asked = np.zeros(len(corners), dtype=bool)
        asked[len(unsplit) :] = True
    return points, corners, origin


def _split_by_pattern(points: np.ndarray, corners: np.ndarray, middles: np.ndarray) -> np.ndarray:
    """Jedes Dreieck nach seinen geteilten Seiten (``middles`` je Seite, ``-1`` ungeteilt).

    Seite ``k`` läuft von Ecke ``k`` zu ``k + 1``. Eine geteilte Seite halbiert
    das Dreieck zur Gegenecke; zwei trennen die Ecke zwischen ihnen ab, und das
    Viereck daneben teilt seine kürzere Diagonale; drei ergeben vier ähnliche
    Dreiecke. Die Umlaufrichtung bleibt, die ungeteilten Dreiecke stehen vorn.
    """
    marked = middles >= 0
    count = marked.sum(axis=1)
    pieces = [corners[count == 0]]
    lone = np.flatnonzero(count == 1)
    if len(lone):
        turn = (np.argmax(marked[lone], axis=1)[:, None] + np.arange(3)) % 3
        a, b, c = np.take_along_axis(corners[lone], turn, axis=1).T
        middle = np.take_along_axis(middles[lone], turn, axis=1)[:, 0]
        pieces += [np.column_stack((a, middle, c)), np.column_stack((middle, b, c))]
    pair = np.flatnonzero(count == 2)
    if len(pair):
        # Die ungeteilte Seite wird Seite 2: Die Ecke b liegt zwischen beiden geteilten.
        turn = ((np.argmin(marked[pair], axis=1) + 1)[:, None] + np.arange(3)) % 3
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
    return np.concatenate(pieces)
