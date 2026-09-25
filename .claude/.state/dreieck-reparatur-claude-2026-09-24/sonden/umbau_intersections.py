"""Einmalig: intersections.py — Paare mit Koplanar-Kennung, gefiltertes Budget,
Fortschritt, keine einsum-Entscheidungen (Durchsicht 24.09.2026)."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/intersections.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    assert text.count(old) == count, (text.count(old), old[:90])
    text = text.replace(old, new)


swap(
    """  danach als Feld. Nichts wird gekappt: Das
  Budget ``max_pairs`` gibt es nur für die Karte, die ehrlich sagt, was sie
  gefunden hat; der Bereichstest prüft jedes Paar.""",
    """  danach als Feld. Nichts wird gekappt: Das
  Budget ``max_pairs`` gibt es nur für Karte und Reparatur, die ehrlich sagen,
  was sie gefunden haben; der Bereichstest prüft jedes Paar. **Gezählt werden
  die Paare nach diesem Filter** (Durchsicht 24.09.2026): Sie kosten die
  Rechenzeit, rund zwei Mikrosekunden je Paar. Die Rohpaare des Sweeps sagten
  darüber wenig — ein Besenhalter mit langen Splitterdreiecken brachte 22
  Millionen davon für 3,2 Millionen echte Kandidaten, ein Spiderman 49 für 6.""",
)
swap(
    '''Nullflächen haben keine Oberfläche, die etwas durchdringen könnte, und gehen
vorher heraus.
"""
''',
    '''Nullflächen haben keine Oberfläche, die etwas durchdringen könnte, und gehen
vorher heraus.

**Gerechnet wird ohne** ``np.einsum`` (RM-187): Ob ein Paar sich schneidet,
entscheidet über das Ergebnis einer Reparatur, und ``einsum`` darf auf ARM
mit FMA runden. Die Skalarprodukte stehen als Grundrechenarten
(:func:`_dot_rows`, :func:`_dot_grid`).
"""
''',
)
swap(
    """from collections.abc import Iterator
from dataclasses import dataclass
""",
    """from collections.abc import Callable, Iterator
from dataclasses import dataclass
""",
)
swap(
    '''class _CancelledError(Exception):
    """Abbruch mitten in einer Stufe — die Aufrufer übersetzen ihn."""
''',
    '''class _CancelledError(Exception):
    """Abbruch mitten in einer Stufe — die Aufrufer übersetzen ihn."""


def _dot_rows(points: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Je Paar ``k`` und Ecke ``v`` das Skalarprodukt ``points[k, v] · direction[k]``.

    ``points`` ist ``(k, v, 3)``, ``direction`` ``(k, 3)`` — elementweise, ohne
    BLAS und ohne ``einsum`` (RM-187).
    """
    return (
        points[:, :, 0] * direction[:, None, 0]
        + points[:, :, 1] * direction[:, None, 1]
        + points[:, :, 2] * direction[:, None, 2]
    )


def _dot_grid(axes: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Je Paar ``k`` jede Achse ``e`` gegen jede Ecke ``v`` in der Ebene: ``(k, e, v)``."""
    return (
        axes[:, :, None, 0] * points[:, None, :, 0] + axes[:, :, None, 1] * points[:, None, :, 1]
    )
''',
)
swap(
    '''@dataclass(slots=True)
class _Search:
    """Wie weit die Kandidatensuche kam — ``complete`` fällt nur mit ``max_pairs``."""

    max_pairs: int | None = None
    complete: bool = True
''',
    '''@dataclass(slots=True)
class _Search:
    """Wie weit die Kandidatensuche kam — ``complete`` fällt nur mit ``max_pairs``.

    ``progress`` bekommt den Anteil der Sweep-Einträge, die schon durchlaufen
    sind — eine Zahl zwischen null und eins, je Block einmal.
    """

    max_pairs: int | None = None
    complete: bool = True
    progress: Callable[[float], None] | None = None
''',
)
swap(
    """    counts = entries.counts
    total = np.cumsum(counts)
    positions = np.arange(len(counts))
    counted = 0
    begin = 0
    while begin < len(counts):
        _check(cancelled)""",
    """    counts = entries.counts
    total = np.cumsum(counts)
    overall = float(total[-1]) if len(total) else 0.0
    positions = np.arange(len(counts))
    counted = 0
    begin = 0
    while begin < len(counts):
        _check(cancelled)
        if search.progress is not None and overall > 0.0:
            search.progress(float(total[begin - 1]) / overall if begin else 0.0)""",
)
swap(
    """        amount = int(size.sum())
        if not amount:
            continue
        counted += amount
        if search.max_pairs is not None and counted > search.max_pairs:
            search.complete = False
            return
        left = np.repeat(block, size)""",
    """        amount = int(size.sum())
        if not amount:
            continue
        left = np.repeat(block, size)""",
)
swap(
    """        first, second = first[~apart], second[~apart]
        for start in range(0, len(first), PAIR_BLOCK):""",
    """        first, second = first[~apart], second[~apart]
        counted += len(first)
        if search.max_pairs is not None and counted > search.max_pairs:
            search.complete = False
            return
        for start in range(0, len(first), PAIR_BLOCK):""",
)
swap(
    """    projection = np.einsum("kvd,kd->kv", triangle, direction)
    span = np.linalg.norm""",
    """    projection = _dot_rows(triangle, direction)
    span = np.linalg.norm""",
)
swap(
    """        first_projection = np.einsum("ked,kvd->kev", axes, first_2d)
        second_projection = np.einsum("ked,kvd->kev", axes, second_2d)""",
    """        first_projection = _dot_grid(axes, first_2d)
        second_projection = _dot_grid(axes, second_2d)""",
)
swap(
    '''def crossing_pairs(
    first: np.ndarray, second: np.ndarray, first_faces: np.ndarray, second_faces: np.ndarray
) -> np.ndarray:
    """Je Paar, ob die zwei Dreiecke einander über ihre gemeinsamen Punkte hinaus schneiden.

    ``first`` und ``second`` sind ``(m, 3, 3)``, ``*_faces`` die Eckennummern
    je Dreieck ``(m, 3)`` — nur für die doppelte Zelle gebraucht.
    """
    count = len(first)
    hit = np.zeros(count, dtype=bool)
    if not count:
        return hit''',
    '''def crossing_pairs(
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
        return (hit, flat) if with_coplanar else hit''',
)
swap(
    """    close = np.einsum("mabk,mabk->mab", difference, difference) <= EPS_GEOM * EPS_GEOM""",
    """    close = (
        difference[..., 0] * difference[..., 0]
        + difference[..., 1] * difference[..., 1]
        + difference[..., 2] * difference[..., 2]
    ) <= EPS_GEOM * EPS_GEOM""",
)
swap(
    """    first_distance = (
        np.einsum("kvd,kd->kv", first - second[:, 0, None, :], second_normal)
        / second_length[:, None]
    )
    second_distance = (
        np.einsum("kvd,kd->kv", second - first[:, 0, None, :], first_normal) / first_length[:, None]
    )""",
    """    first_distance = (
        _dot_rows(first - second[:, 0, None, :], second_normal) / second_length[:, None]
    )
    second_distance = _dot_rows(second - first[:, 0, None, :], first_normal) / first_length[:, None]""",
)
swap(
    """    flat = possible & coplanar
    if np.any(flat):""",
    """    flat = possible & coplanar
    if np.any(flat):""",
)
swap(
    """    steep = np.flatnonzero(possible & ~coplanar)
    if not len(steep):
        return hit""",
    """    steep = np.flatnonzero(possible & ~coplanar)
    if not len(steep):
        return (hit, flat) if with_coplanar else hit""",
)
swap(
    """    projection = np.einsum("kvd,kd->kv", first[steep], unit)
    shared_low""",
    """    projection = _dot_rows(first[steep], unit)
    shared_low""",
)
swap(
    '''    hit[steep] = np.where(shared.any(axis=1), beyond, True)
    return hit


def _pairs_that_cross(
    surface: _Surface, cancelled: CancelToken | None, search: _Search
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Je Kandidatenblock die Paare, die sich wirklich schneiden (Nummern im Netz)."""
    for first, second in _candidates(surface, cancelled, search):
        _check(cancelled)
        crossed = crossing_pairs(
            surface.triangles[first],
            surface.triangles[second],
            surface.faces[first],
            surface.faces[second],
        )
        if np.any(crossed):
            yield surface.kept[first[crossed]], surface.kept[second[crossed]]''',
    '''    hit[steep] = np.where(shared.any(axis=1), beyond, True)
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
            yield surface.kept[first[crossed]], surface.kept[second[crossed]], coplanar[crossed]''',
)
swap(
    '''def crossing_faces(
    vertices: np.ndarray,
    faces: np.ndarray,
    cancelled: CancelToken | None = None,
    *,
    max_pairs: int | None = None,
) -> tuple[tuple[int, ...], bool]:
    """Die Dreiecke, die ein anderes schneiden — und ob die Suche vollständig war.

    ``max_pairs`` begrenzt die Kandidaten des Sweeps; darüber endet die Suche
    und meldet mit ``False``, dass sie nicht alles gesehen hat. Was sie bis
    dahin gefunden hat, schneidet wirklich.
    """
    surface = _surface(vertices, faces)
    if surface is None:
        return (), True
    hit: set[int] = set()
    search = _Search(max_pairs=max_pairs)
    try:
        for first, second in _pairs_that_cross(surface, cancelled, search):
            hit.update(int(index) for index in first)
            hit.update(int(index) for index in second)
    except _CancelledError:
        raise OperationCancelled from None
    return tuple(sorted(hit)), search.complete''',
    '''@dataclass(frozen=True, slots=True)
class Crossings:
    """Die Paare, die sich schneiden, und ob die Suche alles gesehen hat.

    ``first`` und ``second`` nennen die Dreiecke im Eingangsnetz, ``coplanar``
    je Paar, ob beide in derselben Ebene liegen.
    """

    first: np.ndarray
    second: np.ndarray
    coplanar: np.ndarray
    complete: bool

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
    if not firsts:
        return Crossings(empty, empty, np.zeros(0, dtype=bool), search.complete)
    return Crossings(
        np.concatenate(firsts).astype(np.int64),
        np.concatenate(seconds).astype(np.int64),
        np.concatenate(flats),
        search.complete,
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
    return found.faces, found.complete''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
