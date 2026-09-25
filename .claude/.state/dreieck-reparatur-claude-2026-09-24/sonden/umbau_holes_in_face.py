"""Einmalig: repair.py — Ringe einer Ebene als eine Fläche mit Löchern füllen (B4)."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    assert text.count(old) == count, (text.count(old), old[:90])
    text = text.replace(old, new)


# --- Ohrenschneiden: doppelte Ecken der Brücke sind keine Einschlüsse --------
swap(
    """        suspects = np.flatnonzero(reflex & alive)
        suspects = suspects[(suspects != first) & (suspects != third)]""",
    """        suspects = np.flatnonzero(reflex & alive)
        # Eine Ecke, die ein Ohr selbst trägt, liegt nicht in ihm — auch ihre
        # zweite Kopie an einer Lochbrücke nicht (:func:`_bridged_holes`).
        suspects = suspects[
            (ids[suspects] != ids[first])
            & (ids[suspects] != ids[corner])
            & (ids[suspects] != ids[third])
        ]""",
)
swap(
    """    xs = flat[:, 0]
    ys = flat[:, 1]
""",
    """    xs = flat[:, 0]
    ys = flat[:, 1]
    ids = np.asarray(loop, dtype=np.int64)
""",
)

# --- Die Fläche mit Löchern ---------------------------------------------------
swap(
    '''@dataclass(frozen=True, slots=True)
class _RingFill:''',
    '''def _plane_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Zwei Richtungen in der Ebene zu ``normal`` — dieselbe Wahl wie beim Ohrenschneiden."""
    basis_u = np.cross(normal, (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0))
    length = math.hypot(float(basis_u[0]), float(basis_u[1]), float(basis_u[2]))
    if length <= EPS_GEOM:
        return None
    basis_u = basis_u / length
    return basis_u, np.cross(normal, basis_u)


def _segments_cross(
    start: np.ndarray, end: np.ndarray, firsts: np.ndarray, seconds: np.ndarray
) -> bool:
    """Ob die Strecke ``start``–``end`` eine der Strecken ``firsts``–``seconds``
    im Inneren schneidet (in der Ebene; gemeinsame Endpunkte zählen nicht)."""
    if not len(firsts):
        return False

    def side(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
        return (b[..., 0] - a[..., 0]) * (c[..., 1] - a[..., 1]) - (b[..., 1] - a[..., 1]) * (
            c[..., 0] - a[..., 0]
        )

    first = side(start, end, firsts)
    second = side(start, end, seconds)
    third = side(firsts, seconds, start)
    fourth = side(firsts, seconds, end)
    margin = EPS_GEOM * EPS_GEOM
    proper = (first * second < -margin) & (third * fourth < -margin)
    return bool(proper.any())


def _bridged_holes(
    points: np.ndarray, outer: list[int], holes: list[list[int]], normal: np.ndarray
) -> list[int] | None:
    """Ein Außenring mit seinen Lochringen als ein Ring — über je eine Brücke.

    Jedes Loch wird an der Ecke mit der größten Lage entlang der ersten
    Ebenenrichtung an die nächste Ecke des bisherigen Rings gehängt, deren
    Verbindung keine Kante schneidet; die Brücke wird hin und zurück gelaufen.
    Das Ohrenschneiden schließt den so entstandenen Ring wie jeden anderen.
    ``None``, wenn für ein Loch keine Brücke frei ist.
    """
    basis = _plane_basis(normal)
    if basis is None:
        return None
    basis_u, basis_v = basis

    def flat(ids: list[int]) -> np.ndarray:
        local = points[ids]
        return np.column_stack((along(local, basis_u), along(local, basis_v)))

    polygon = list(outer)
    pending = sorted(holes, key=lambda hole: -float(flat(hole)[:, 0].max()))
    for position, hole in enumerate(pending):
        hole_flat = flat(hole)
        start = int(np.lexsort((hole_flat[:, 1], -hole_flat[:, 0]))[0])
        anchor = hole_flat[start]
        polygon_flat = flat(polygon)
        # Die Kanten, die eine Brücke nicht kreuzen darf: der bisherige Ring
        # und alle Löcher, auch die noch nicht angehängten.
        rings = [polygon, *pending[position:]]
        firsts = np.vstack([flat(ring) for ring in rings])
        seconds = np.vstack([np.roll(flat(ring), -1, axis=0) for ring in rings])
        distance = np.hypot(polygon_flat[:, 0] - anchor[0], polygon_flat[:, 1] - anchor[1])
        bridge: int | None = None
        for candidate in np.argsort(distance, kind="stable").tolist():
            target = polygon_flat[candidate]
            touching = (
                (np.hypot(firsts[:, 0] - target[0], firsts[:, 1] - target[1]) <= EPS_GEOM)
                | (np.hypot(seconds[:, 0] - target[0], seconds[:, 1] - target[1]) <= EPS_GEOM)
                | (np.hypot(firsts[:, 0] - anchor[0], firsts[:, 1] - anchor[1]) <= EPS_GEOM)
                | (np.hypot(seconds[:, 0] - anchor[0], seconds[:, 1] - anchor[1]) <= EPS_GEOM)
            )
            if not _segments_cross(anchor, target, firsts[~touching], seconds[~touching]):
                bridge = int(candidate)
                break
        if bridge is None:
            return None
        around = hole[start:] + hole[:start]
        polygon = (
            polygon[: bridge + 1] + around + [hole[start], polygon[bridge]] + polygon[bridge + 1 :]
        )
    return polygon


@dataclass(frozen=True, slots=True)
class _FillJob:
    """Was eine Füllung schließt: ein Ring — oder ein Außenring mit Löchern.

    ``loop`` ist der Ring, der geohrt wird, ``rims`` die Randringe, die er
    schließt, der Außenring zuerst.
    """

    loop: list[int]
    rims: tuple[list[int], ...]


def _fill_jobs(points: np.ndarray, loops: list[list[int]], tolerance: float) -> list[_FillJob]:
    """Die Ringe, die zusammen eine Fläche mit Löchern begrenzen, als eine Füllung.

    **Fehlt einer Platte die ganze Oberseite, ist das eine Fläche mit Löchern,
    nicht fünf Scheiben** (Befund B4 der Durchsicht 24.09.2026). Der Füller
    schloss den Außenrand und jede Bohrungsmündung für sich: Die große Scheibe
    lag über den Mündungen, jede Mündung bekam zusätzlich einen Deckel — 570
    Durchdringungen, und aus vier Durchgangsbohrungen wurden Sacklöcher.

    Zusammen gehören Ringe, die ganz in derselben Ebene liegen (``tolerance``)
    und von denen einer im anderen liegt, mit gegenläufigem Umlauf: So laufen
    Außenrand und Löcher einer fehlenden Fläche. Alles andere bleibt ein Ring
    für sich.
    """
    from shapely.geometry import Point, Polygon

    shapes: list[tuple[np.ndarray, np.ndarray, float] | None] = []
    for loop in loops:
        ring = points[loop]
        centre = np.asarray(units.exact_centre(ring.tolist()), dtype=np.float64)
        normal = _ring_normal(ring, centre)
        if normal is None or len(loop) < 3:
            shapes.append(None)
            continue
        offsets = np.abs(along(ring - centre, normal))
        if float(offsets.max()) > tolerance:
            shapes.append(None)
            continue
        crossed = np.cross(ring - centre, np.roll(ring, -1, axis=0) - centre)
        area = float(along(crossed, normal).sum()) / 2.0
        shapes.append((centre, normal, area))

    holes_of: dict[int, list[int]] = {}
    taken: set[int] = set()
    order = sorted(
        (index for index, shape in enumerate(shapes) if shape is not None),
        key=lambda index: -cast(tuple[np.ndarray, np.ndarray, float], shapes[index])[2],
    )
    for outer in order:
        if outer in taken:
            continue
        centre, normal, _area = cast(tuple[np.ndarray, np.ndarray, float], shapes[outer])
        basis = _plane_basis(normal)
        if basis is None:
            continue
        basis_u, basis_v = basis
        outline = points[loops[outer]] - centre
        region = Polygon(np.column_stack((along(outline, basis_u), along(outline, basis_v))))
        if not region.is_valid:
            continue
        for other in order:
            if other == outer or other in taken:
                continue
            other_centre, other_normal, _other_area = cast(
                tuple[np.ndarray, np.ndarray, float], shapes[other]
            )
            if float(units.dot3(other_normal, normal)) > -1.0 + 1e-9:
                continue  # nicht gegenläufig in derselben Ebene
            if abs(float(units.dot3(other_centre - centre, normal))) > tolerance:
                continue
            probe = points[loops[other][0]] - centre
            spot = Point(float(units.dot3(probe, basis_u)), float(units.dot3(probe, basis_v)))
            if region.contains(spot):
                holes_of.setdefault(outer, []).append(other)
                taken.add(other)

    jobs: list[tuple[int, _FillJob]] = []
    merged: set[int] = set()
    for outer, holes in holes_of.items():
        normal = cast(tuple[np.ndarray, np.ndarray, float], shapes[outer])[1]
        loop = _bridged_holes(points, loops[outer], [loops[hole] for hole in holes], normal)
        if loop is None:
            continue
        jobs.append(
            (outer, _FillJob(loop=loop, rims=(loops[outer], *(loops[hole] for hole in holes))))
        )
        merged.update([outer, *holes])
    jobs.extend(
        (index, _FillJob(loop=loop, rims=(loop,)))
        for index, loop in enumerate(loops)
        if index not in merged
    )
    return [job for _index, job in sorted(jobs, key=lambda item: item[0])]


@dataclass(frozen=True, slots=True)
class _RingFill:''',
)

# --- Der Füller geht über Aufträge, nicht über Ringe --------------------------
swap(
    """    records: list[_RingFill] = []
    blocked = 0
    for loop in loops:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        ring = points[loop]
        # Die Fläche des Rings, gemessen über sein Umlaufintegral — dieselbe
        # Zahl, die ein Dreiecksnetz über dem Ring hätte.
        # Die Mitte wird beim Fächer ein echter Eckpunkt — über
        # ``exact_centre`` auf jeder Maschine dieselbe (RM-187).
        centre = np.asarray(units.exact_centre(ring.tolist()), dtype=np.float64)
        spanned = (
            float(
                np.linalg.norm(
                    np.cross(ring - centre, np.roll(ring, -1, axis=0) - centre), axis=1
                ).sum()
            )
            / 2.0
        )
        wide_here = spanned > limit""",
    """    records: list[_RingFill] = []
    blocked = 0
    jobs = _fill_jobs(
        points, loops, max(10.0 * EPS_GEOM, weld_tolerance(float(mesh.bounds.diagonal)))
    )
    for job in jobs:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        loop = job.loop
        ring = points[job.rims[0]]
        # Die Fläche des Rings, gemessen über sein Umlaufintegral — dieselbe
        # Zahl, die ein Dreiecksnetz über dem Ring hätte; bei einer Fläche mit
        # Löchern ohne die Löcher.
        # Die Mitte wird beim Fächer ein echter Eckpunkt — über
        # ``exact_centre`` auf jeder Maschine dieselbe (RM-187).
        centre = np.asarray(units.exact_centre(ring.tolist()), dtype=np.float64)
        spanned = 0.0
        for number, rim in enumerate(job.rims):
            points_of_rim = points[rim]
            middle_of_rim = np.asarray(
                units.exact_centre(points_of_rim.tolist()), dtype=np.float64
            )
            area_of_rim = (
                float(
                    np.linalg.norm(
                        np.cross(
                            points_of_rim - middle_of_rim,
                            np.roll(points_of_rim, -1, axis=0) - middle_of_rim,
                        ),
                        axis=1,
                    ).sum()
                )
                / 2.0
            )
            spanned += area_of_rim if number == 0 else -area_of_rim
        wide_here = spanned > limit""",
)
swap(
    """        chosen: np.ndarray | None = None
        needs_middle = False
        for attempt in (
            _loop_triangles(points, loop, taken, cancelled),
            _loop_fan(loop, len(points)),
        ):""",
    """        chosen: np.ndarray | None = None
        needs_middle = False
        # Eine Fläche mit Löchern bekommt keinen Fächer: Er deckte die Löcher.
        attempts = [_loop_triangles(points, loop, taken, cancelled)]
        if len(job.rims) == 1:
            attempts.append(_loop_fan(loop, len(points)))
        for attempt in attempts:
            if len(job.rims) > 1 and len(attempt) and int(attempt.max()) >= len(points):
                continue""",
)
swap(
    """        fallback = neighbour_of[(min(loop[0], loop[1]), max(loop[0], loop[1]))]""",
    """        first_rim = job.rims[0]
        fallback = neighbour_of[
            (min(first_rim[0], first_rim[1]), max(first_rim[0], first_rim[1]))
        ]""",
)
swap(
    """                middle=centre if needs_middle else None,
                wide=wide_here,
                spanned=spanned,
                centre=centre,
                edges=len(loop),""",
    """                middle=centre if needs_middle else None,
                wide=wide_here,
                spanned=spanned,
                centre=centre,
                edges=sum(len(rim) for rim in job.rims),""",
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
