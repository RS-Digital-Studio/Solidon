"""Einmalig: Review R9/R10/R11 — Ringzuordnung ohne quadratische Python-Schleifen,
mit Abbruch, und ``np.hypot`` durch Grundrechenarten ersetzt."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, (text.count(old), old[:100])
    text = text.replace(old, new)


# --- _band_between nimmt Mitte und Normale entgegen, rechnet ohne hypot ------
swap(
    '''    owner_of: dict[tuple[int, int], int],
    centroids: np.ndarray,
) -> np.ndarray | None:
    """Der Mantel zwischen zwei Ringen, wenn sie die Enden einer fehlenden Wand sind.
''',
    '''    owner_of: dict[tuple[int, int], int],
    centroids: np.ndarray,
    shape_a: tuple[np.ndarray, np.ndarray] | None = None,
    shape_b: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray | None:
    """Der Mantel zwischen zwei Ringen, wenn sie die Enden einer fehlenden Wand sind.
''',
)
swap(
    '''    Ob das Band danach eine Kante überbelegt oder etwas durchdringt, prüft der
    Füller; dann deckelt er wie bisher. Gerechnet wird mit Grundrechenarten
    und ohne Winkelfunktionen (RM-187).
    """
    count = len(first)
    if count != len(second) or count < 3:
        return None
    ring_a, ring_b = points[first], points[second]
    centre_a = np.asarray(units.exact_centre(ring_a.tolist()), dtype=np.float64)
    centre_b = np.asarray(units.exact_centre(ring_b.tolist()), dtype=np.float64)
    normal_a = _ring_normal(ring_a, centre_a)
    normal_b = _ring_normal(ring_b, centre_b)
    if normal_a is None or normal_b is None:
        return None
    offset = centre_b - centre_a
    length = math.hypot(float(offset[0]), float(offset[1]), float(offset[2]))
    if length <= tolerance:
        return None
    axis = offset / length
    across = np.cross(normal_a, normal_b)
    if math.hypot(*(float(value) for value in across)) > BAND_PARALLEL:
        return None
    along_axis = np.cross(normal_a, axis)
    if math.hypot(*(float(value) for value in along_axis)) > BAND_PARALLEL:
        return None
''',
    '''    Ob das Band danach eine Kante überbelegt oder etwas durchdringt, prüft der
    Füller; dann deckelt er wie bisher. Gerechnet wird mit Grundrechenarten
    und ohne Winkelfunktionen (RM-187). ``shape_a``/``shape_b`` reichen Mitte
    und Normale herein, die :func:`_fill_jobs` je Ring schon kennt — an 400
    Ringen rechnete die Paarung sie sonst 79 800-mal neu (Review R9,
    24.09.2026).
    """
    count = len(first)
    if count != len(second) or count < 3:
        return None
    ring_a, ring_b = points[first], points[second]
    if shape_a is None:
        centre_a = np.asarray(units.exact_centre(ring_a.tolist()), dtype=np.float64)
        normal_a = _ring_normal(ring_a, centre_a)
    else:
        centre_a, normal_a = shape_a
    if shape_b is None:
        centre_b = np.asarray(units.exact_centre(ring_b.tolist()), dtype=np.float64)
        normal_b = _ring_normal(ring_b, centre_b)
    else:
        centre_b, normal_b = shape_b
    if normal_a is None or normal_b is None:
        return None
    offset = centre_b - centre_a
    length = _length(offset)
    if length <= tolerance:
        return None
    axis = offset / length
    if _length(np.cross(normal_a, normal_b)) > BAND_PARALLEL:
        return None
    if _length(np.cross(normal_a, axis)) > BAND_PARALLEL:
        return None
''',
)
swap(
    '''    radius_a = np.hypot(flat_a[:, 0], flat_a[:, 1])
    radius_b = np.hypot(flat_b[:, 0], flat_b[:, 1])
''',
    '''    # ``np.sqrt`` über Grundrechenarten statt ``np.hypot``: Das ist eine
    # Bibliotheksfunktion der Plattform, und am Radius hängt, ob ein Band
    # entsteht (Review R11, RM-187).
    radius_a = np.sqrt(flat_a[:, 0] * flat_a[:, 0] + flat_a[:, 1] * flat_a[:, 1])
    radius_b = np.sqrt(flat_b[:, 0] * flat_b[:, 0] + flat_b[:, 1] * flat_b[:, 1])
''',
)
swap(
    '''def _band_between(
    points: np.ndarray,''',
    '''def _length(vector: np.ndarray) -> float:
    """Die Länge eines Raumvektors über Grundrechenarten und ``sqrt`` (RM-187)."""
    x, y, z = (float(value) for value in vector)
    return math.sqrt(x * x + y * y + z * z)


def _band_between(
    points: np.ndarray,''',
)

# --- _fill_jobs: Abbruch, Vorauswahl, geteilte Formdaten ---------------------
swap(
    '''    owner_of: dict[tuple[int, int], int] | None = None,
    centroids: np.ndarray | None = None,
) -> list[_FillJob]:
    """Die Ringe, die zusammen eine Fläche mit Löchern begrenzen, als eine Füllung.
''',
    '''    owner_of: dict[tuple[int, int], int] | None = None,
    centroids: np.ndarray | None = None,
    cancelled: CancelToken | None = None,
) -> list[_FillJob]:
    """Die Ringe, die zusammen eine Fläche mit Löchern begrenzen, als eine Füllung.
''',
)
swap(
    '''    und von denen einer im anderen liegt, mit gegenläufigem Umlauf: So laufen
    Außenrand und Löcher einer fehlenden Fläche. Alles andere bleibt ein Ring
    für sich.
    """
    from shapely.geometry import Point, Polygon

    shapes: list[tuple[np.ndarray, np.ndarray, float] | None] = []
    for loop in loops:
''',
    '''    und von denen einer im anderen liegt, mit gegenläufigem Umlauf: So laufen
    Außenrand und Löcher einer fehlenden Fläche. Alles andere bleibt ein Ring
    für sich.

    **Beide Paarungen sieben zuerst über ganze Felder** (Review R9,
    24.09.2026): Jeder Ring gegen jeden, je Paar in Python, kostete an einer
    Kugel mit 1 500 fehlenden Dreiecken 78 s statt 0,06 s — beim Import, ohne
    Abbruch. Die Vorauswahl ist weiter als die genaue Prüfung danach und
    entscheidet nie selbst; ``cancelled`` wird je Ring gefragt.
    """
    from shapely.geometry import Point, Polygon

    def check() -> None:
        if cancelled is not None:
            cancelled.raise_if_cancelled()

    shapes: list[tuple[np.ndarray, np.ndarray, float] | None] = []
    for number, loop in enumerate(loops):
        if number % 256 == 0:
            check()
''',
)
swap(
    '''    holes_of: dict[int, list[int]] = {}
    taken: set[int] = set()
    order = sorted(
        (index for index, shape in enumerate(shapes) if shape is not None),
        key=lambda index: -cast(tuple[np.ndarray, np.ndarray, float], shapes[index])[2],
    )
    for outer in order:
        if outer in taken:
            continue
''',
    '''    holes_of: dict[int, list[int]] = {}
    taken: set[int] = set()
    order = sorted(
        (index for index, shape in enumerate(shapes) if shape is not None),
        key=lambda index: -cast(tuple[np.ndarray, np.ndarray, float], shapes[index])[2],
    )
    known = [cast(tuple[np.ndarray, np.ndarray, float], shapes[index]) for index in order]
    centres = np.asarray([shape[0] for shape in known], dtype=np.float64).reshape(-1, 3)
    normals = np.asarray([shape[1] for shape in known], dtype=np.float64).reshape(-1, 3)
    for position, outer in enumerate(order):
        if outer in taken:
            continue
        check()
        # Vorauswahl: gegenläufig und in derselben Ebene, mit weiterer Schwelle
        # als die genaue Prüfung darunter.
        facing = (
            normals[:, 0] * normals[position, 0]
            + normals[:, 1] * normals[position, 1]
            + normals[:, 2] * normals[position, 2]
        )
        apart = centres - centres[position]
        height = (
            apart[:, 0] * normals[position, 0]
            + apart[:, 1] * normals[position, 1]
            + apart[:, 2] * normals[position, 2]
        )
        near = np.flatnonzero((facing < -1.0 + 1e-6) & (np.abs(height) <= 2.0 * tolerance))
        if not len(near):
            continue
''',
)
swap(
    '''        for other in order:
            if other == outer or other in taken:
                continue
            other_centre, other_normal, _other_area = cast(
                tuple[np.ndarray, np.ndarray, float], shapes[other]
            )
''',
    '''        for candidate in near.tolist():
            other = order[candidate]
            if other == outer or other in taken:
                continue
            other_centre, other_normal, _other_area = known[candidate]
''',
)
swap(
    '''    if owner_of is not None and centroids is not None:
        single = [
            index
            for index in range(len(loops))
            if index not in merged and shapes[index] is not None
        ]
        for position, first in enumerate(single):
            if first in merged:
                continue
            for second in single[position + 1 :]:
                if second in merged or len(loops[second]) != len(loops[first]):
                    continue
                band = _band_between(
                    points, loops[first], loops[second], tolerance, owner_of, centroids
                )
                if band is None:
                    continue
''',
    '''    if owner_of is not None and centroids is not None:
        single = [
            index
            for index in range(len(loops))
            if index not in merged and shapes[index] is not None
        ]
        # Vorauswahl je Paar über ganze Felder: gleich viele Ecken, parallele
        # Ebenen, Mitten entlang der Normale — dieselben Bedingungen wie in
        # :func:`_band_between`, doppelt so weit gefasst.
        counts = np.asarray([len(loops[index]) for index in single], dtype=np.int64)
        single_shapes = [cast(tuple[np.ndarray, np.ndarray, float], shapes[i]) for i in single]
        ring_centres = np.asarray([s[0] for s in single_shapes], dtype=np.float64).reshape(-1, 3)
        ring_normals = np.asarray([s[1] for s in single_shapes], dtype=np.float64).reshape(-1, 3)
        loose = 2.0 * BAND_PARALLEL
        for position, first in enumerate(single):
            if first in merged:
                continue
            check()
            later = np.arange(position + 1, len(single))
            later = later[counts[later] == counts[position]]
            if not len(later):
                continue
            normal = ring_normals[position]
            across = np.cross(ring_normals[later], normal)
            offset = ring_centres[later] - ring_centres[position]
            length = np.sqrt(
                offset[:, 0] * offset[:, 0] + offset[:, 1] * offset[:, 1] + offset[:, 2] * offset[:, 2]
            )
            sideways = np.cross(offset, normal)
            fits = (
                (length > tolerance)
                & (
                    np.sqrt(np.sum(across * across, axis=1)) <= loose
                )
                & (np.sqrt(np.sum(sideways * sideways, axis=1)) <= loose * np.maximum(length, 1.0))
            )
            for candidate in later[fits].tolist():
                second = single[candidate]
                if second in merged:
                    continue
                band = _band_between(
                    points,
                    loops[first],
                    loops[second],
                    tolerance,
                    owner_of,
                    centroids,
                    (ring_centres[position], normal),
                    (ring_centres[candidate], ring_normals[candidate]),
                )
                if band is None:
                    continue
''',
)
swap(
    '''    jobs = _fill_jobs(
        points,
        loops,
        max(10.0 * EPS_GEOM, weld_tolerance(float(mesh.bounds.diagonal))),
        neighbour_of,
        centroids,
    )
''',
    '''    jobs = _fill_jobs(
        points,
        loops,
        max(10.0 * EPS_GEOM, weld_tolerance(float(mesh.bounds.diagonal))),
        neighbour_of,
        centroids,
        cancelled,
    )
''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
