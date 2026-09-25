"""Einmalig: repair.py — kleine Ringe nach dem kleinsten Knick füllen (B3 Erkennung)."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    assert text.count(old) == count, (text.count(old), old[:90])
    text = text.replace(old, new)


swap(
    '''@dataclass(frozen=True, slots=True)
class _RingFill:''',
    '''#: Bis zu wie vielen Ecken ein Ring über alle Triangulierungen gefüllt wird.
#: Die Suche kostet die dritte Potenz der Eckenzahl; bei sechzehn sind es
#: rund viertausend Schritte, und darüber sind Ringe selten so klein, dass
#: eine einzelne Dreieckslage die Form einer Rundung trägt.
SMOOTH_FILL_CORNERS: Final = 16


def _unit_normals(triangles: np.ndarray) -> np.ndarray:
    """Einheitsnormalen der Dreiecke ``(n, 3, 3)`` — Nullflächen bekommen null."""
    raw = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    size = np.sqrt(raw[:, 0] * raw[:, 0] + raw[:, 1] * raw[:, 1] + raw[:, 2] * raw[:, 2])
    return np.divide(raw, size[:, None], out=np.zeros_like(raw), where=size[:, None] > 0.0)


def _smoothest_fill(
    points: np.ndarray,
    loop: list[int],
    owner_of: dict[tuple[int, int], int],
    face_normals: np.ndarray,
    taken: dict[tuple[int, int], int],
) -> np.ndarray | None:
    """Die Füllung eines kleinen Rings mit dem kleinsten größten Knick.

    **Das erste gültige Ohr ist nicht das richtige** (Befund B3 der
    Erkennungsdurchsicht, 24.09.2026). An einer fächerförmig vernetzten
    Verrundung R 3 fehlten zwei Dreiecke; das Ohrenschneiden legte eines quer
    über den Bogen, und die Erkennung las danach R 2,773. Gewählt wird wie bei
    Liepa (2003) über alle Triangulierungen des Rings: zuerst der kleinste
    größte Knick gegen die Nachbarn — am Rand die Fläche daneben, innen das
    Nachbardreieck derselben Füllung —, bei Gleichstand die kleinste Fläche.
    Der Knick ist ``1 − cos``, gerechnet über Kreuzprodukte und
    Grundrechenarten (RM-187). Sehnen, die im Netz schon Kanten sind, bleiben
    gesperrt wie beim Ohrenschneiden. ``None``, wenn es keine gibt.
    """
    count = len(loop)
    if count < 4 or count > SMOOTH_FILL_CORNERS:
        return None
    corners = points[loop]
    infinite = (math.inf, math.inf)

    def rim_normal(first: int, second: int) -> np.ndarray | None:
        edge = (min(loop[first], loop[second]), max(loop[first], loop[second]))
        owner = owner_of.get(edge)
        return None if owner is None else face_normals[owner]

    # Normalen und Flächen aller Tripel i < m < k in einem Feld, danach nur
    # noch Nachschlagen — die Suche selbst rechnet mit Python-Zahlen.
    triples = np.asarray(
        [
            (first, middle, last)
            for first in range(count)
            for middle in range(first + 1, count)
            for last in range(middle + 1, count)
        ],
        dtype=np.int64,
    )
    spans = corners[triples]
    crossed = np.cross(spans[:, 1] - spans[:, 0], spans[:, 2] - spans[:, 0])
    sizes = np.sqrt(
        crossed[:, 0] * crossed[:, 0] + crossed[:, 1] * crossed[:, 1] + crossed[:, 2] * crossed[:, 2]
    )
    units_of = np.divide(
        crossed, sizes[:, None], out=np.zeros_like(crossed), where=sizes[:, None] > 0.0
    )
    table = {
        (int(a), int(b), int(c)): (tuple(float(v) for v in units_of[row]), float(sizes[row]) / 2.0)
        for row, (a, b, c) in enumerate(triples.tolist())
    }

    def normal_of(first: int, middle: int, last: int) -> tuple[float, ...]:
        return table[(first, middle, last)][0]

    def bend(normal: tuple[float, ...], other: np.ndarray | tuple[float, ...] | None) -> float:
        if other is None:
            return 0.0
        return 1.0 - (
            normal[0] * float(other[0]) + normal[1] * float(other[1]) + normal[2] * float(other[2])
        )

    def chord_free(first: int, last: int) -> bool:
        if (last - first) % count in (1, count - 1):
            return True
        chord = (min(loop[first], loop[last]), max(loop[first], loop[last]))
        return taken.get(chord, 0) < 1

    # best[i][k]: (größter Knick, Fläche) der besten Füllung des Teilrings
    # i … k; choice[i][k]: die mittlere Ecke ihres Dreiecks über der Sehne i-k.
    best: list[list[tuple[float, float]]] = [[infinite] * count for _ in range(count)]
    choice = [[-1] * count for _ in range(count)]
    for first in range(count - 1):
        best[first][first + 1] = (0.0, 0.0)

    def triangle_normal(first: int, last: int) -> tuple[float, ...] | None:
        middle = choice[first][last]
        return None if middle < 0 else normal_of(first, middle, last)

    for span in range(2, count):
        for first in range(count - span):
            last = first + span
            if not chord_free(first, last):
                continue
            for middle in range(first + 1, last):
                left, right = best[first][middle], best[middle][last]
                if left[0] == math.inf or right[0] == math.inf:
                    continue
                normal = normal_of(first, middle, last)
                neighbour_left = (
                    rim_normal(first, middle) if middle == first + 1 else triangle_normal(first, middle)
                )
                neighbour_right = (
                    rim_normal(middle, last) if last == middle + 1 else triangle_normal(middle, last)
                )
                worst = max(left[0], right[0], bend(normal, neighbour_left), bend(normal, neighbour_right))
                if last - first == count - 1:
                    worst = max(worst, bend(normal, rim_normal(last, first)))
                area = table[(first, middle, last)][1]
                candidate = (worst, left[1] + right[1] + area)
                if candidate < best[first][last]:
                    best[first][last] = candidate
                    choice[first][last] = middle
    if choice[0][count - 1] < 0:
        return None
    pieces: list[list[int]] = []
    pending = [(0, count - 1)]
    while pending:
        first, last = pending.pop()
        if last - first < 2:
            continue
        middle = choice[first][last]
        pieces.append([loop[first], loop[middle], loop[last]])
        pending.extend([(first, middle), (middle, last)])
    return np.asarray(pieces, dtype=np.int64)


@dataclass(frozen=True, slots=True)
class _RingFill:''',
)

swap(
    '''    triangles_now = np.asarray(body.triangles, dtype=np.float64)
    centroids = (triangles_now[:, 0] + triangles_now[:, 1] + triangles_now[:, 2]) / 3.0''',
    '''    triangles_now = np.asarray(body.triangles, dtype=np.float64)
    centroids = (triangles_now[:, 0] + triangles_now[:, 1] + triangles_now[:, 2]) / 3.0
    face_normals = _unit_normals(triangles_now)''',
)
swap(
    '''        else:
            attempts = [_loop_triangles(points, loop, taken, cancelled)]
            if len(job.rims) == 1:
                attempts.append(_loop_fan(loop, len(points)))''',
    '''        else:
            attempts = []
            if len(job.rims) == 1:
                # Ein kleiner Ring zuerst über alle Triangulierungen, nach dem
                # kleinsten Knick (:func:`_smoothest_fill`).
                smooth = _smoothest_fill(points, loop, neighbour_of, face_normals, taken)
                if smooth is not None:
                    attempts.append(smooth)
            attempts.append(_loop_triangles(points, loop, taken, cancelled))
            if len(job.rims) == 1:
                attempts.append(_loop_fan(loop, len(points)))''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
