"""Einmalig: repair.py — eine fehlende Wand zwischen zwei Ringen als Band (B4-Rest)."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    assert text.count(old) == count, (text.count(old), old[:90])
    text = text.replace(old, new)


swap(
    '''    loop: list[int]
    rims: tuple[list[int], ...]


def _fill_jobs(points: np.ndarray, loops: list[list[int]], tolerance: float) -> list[_FillJob]:''',
    '''    loop: list[int]
    rims: tuple[list[int], ...]
    band: np.ndarray | None = None
    """Die fertigen Dreiecke eines Mantels zwischen zwei Ringen (:func:`_band_between`)."""


#: Wie weit zwei Richtungen voneinander abweichen dürfen und noch als parallel
#: gelten — als Sinus des Winkels, rund ein Hundertstel Grad. Ein CAD-Export
#: legt die Mündungen einer Bohrung exakt parallel; eine Zufallsgleichheit
#: zweier Löcher trifft diese Grenze nicht.
BAND_PARALLEL: Final = 1e-4


def _band_between(
    points: np.ndarray,
    first: list[int],
    second: list[int],
    tolerance: float,
    owner_of: dict[tuple[int, int], int],
    centroids: np.ndarray,
) -> np.ndarray | None:
    """Der Mantel zwischen zwei Ringen, wenn sie die Enden einer fehlenden Wand sind.

    **Fehlt die Wand einer Bohrung, sind ihre Mündungen zwei Ringe, und beide
    zu deckeln macht die Bohrung zu** (Befund B4 der Durchsicht 24.09.2026:
    Lochplatte 4 → 3 Bohrungen; fehlt der Kegel einer Senkung, bekam die
    Bohrung darunter einen Deckel). Ein Band zwischen den Ringen stellt die
    Wand wieder her. Gebaut wird es nur, wo die Ringe das belegen:

    * beide eben, in parallelen Ebenen, die Verbindung ihrer Mitten entlang
      der Normale (koaxial),
    * gleich viele Ecken, und jede Ecke des einen hat ihr Gegenüber im anderen
      in derselben Richtung um die Achse, im selben Abstand oder um denselben
      Maßstab — ein Prisma oder ein Kegelstumpf,
    * die Umlaufrichtungen passen zu einem Mantel,
    * **und keine Nachbarfläche eines Rings liegt auf der Seite zum anderen
      Ring hin.** Beim Rohr ohne Deckel, beim Kasten ohne Boden und Deckel und
      bei zwei Löchern an den Polen einer Kugel verbinden die vorhandenen
      Wände die Ringe schon — dort gehören Deckel hin, und ein Band wäre ein
      Tunnel.

    Ob das Band danach eine Kante überbelegt oder etwas durchdringt, prüft der
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
    basis = _plane_basis(axis)
    if basis is None:
        return None
    basis_u, basis_v = basis
    local_a, local_b = ring_a - centre_a, ring_b - centre_b
    if float(np.abs(along(local_a, axis)).max()) > tolerance:
        return None
    if float(np.abs(along(local_b, axis)).max()) > tolerance:
        return None
    flat_a = np.column_stack((along(local_a, basis_u), along(local_a, basis_v)))
    flat_b = np.column_stack((along(local_b, basis_u), along(local_b, basis_v)))
    radius_a = np.hypot(flat_a[:, 0], flat_a[:, 1])
    radius_b = np.hypot(flat_b[:, 0], flat_b[:, 1])
    if float(radius_a.min()) <= tolerance or float(radius_b.min()) <= tolerance:
        return None
    scale = math.fsum(radius_b.tolist()) / math.fsum(radius_a.tolist())
    direction_a = flat_a / radius_a[:, None]
    direction_b = flat_b / radius_b[:, None]
    dots = (
        direction_a[:, 0, None] * direction_b[None, :, 0]
        + direction_a[:, 1, None] * direction_b[None, :, 1]
    )
    match = np.argmax(dots, axis=1)
    if len(np.unique(match)) != count:
        return None
    if float(dots[np.arange(count), match].min()) < 1.0 - BAND_PARALLEL * BAND_PARALLEL:
        return None
    reach = max(tolerance, BAND_PARALLEL * float(radius_b.max()))
    if float(np.abs(radius_b[match] - scale * radius_a).max()) > reach:
        return None
    # Der Mantel läuft über jede Randkante in der Richtung ihres Rings; das
    # geht nur, wenn der zweite Ring gegenläufig um die Achse läuft.
    step = (match[(np.arange(count) + 1) % count] - match) % count
    if not bool(np.all(step == count - 1)):
        return None
    for ring, centre, toward in ((first, centre_a, axis), (second, centre_b, -axis)):
        faces: list[int] = []
        for index in range(count):
            edge = (min(ring[index], ring[(index + 1) % count]), max(ring[index], ring[(index + 1) % count]))
            owner = owner_of.get(edge)
            if owner is None:
                return None
            faces.append(owner)
        side = along(centroids[np.asarray(faces, dtype=np.int64)] - centre, toward)
        if float(side.max()) > tolerance:
            return None
    band: list[list[int]] = []
    for index in range(count):
        here, there = int(match[index]), int(match[(index + 1) % count])
        band.append([first[index], first[(index + 1) % count], second[there]])
        band.append([first[index], second[there], second[here]])
    return np.asarray(band, dtype=np.int64)


def _band_crosses(
    points: np.ndarray, faces: np.ndarray, band: np.ndarray, cancelled: CancelToken | None
) -> bool:
    """Ob ein Mantel etwas durchdringt, das schon da ist — geprüft in seiner Umgebung.

    Eine unvollständige Suche zählt als „durchdringt": Gebaut wird nur, was
    belegt ist.
    """
    from app.core.geom.intersections import crossing_face_pairs

    corners = points[band]
    low = corners.reshape(-1, 3).min(axis=0) - EPS_GEOM
    high = corners.reshape(-1, 3).max(axis=0) + EPS_GEOM
    triangles = points[faces]
    near = np.flatnonzero(
        np.all(triangles.max(axis=1) >= low, axis=1) & np.all(triangles.min(axis=1) <= high, axis=1)
    )
    combined = np.vstack([faces[near], band])
    found = crossing_face_pairs(
        points, combined, cancelled, max_pairs=intersection_budget(len(combined))
    )
    first_band = len(near)
    involved = (found.first >= first_band) | (found.second >= first_band)
    return bool(involved.any()) or not found.complete


def _fill_jobs(
    points: np.ndarray,
    loops: list[list[int]],
    tolerance: float,
    owner_of: dict[tuple[int, int], int] | None = None,
    centroids: np.ndarray | None = None,
) -> list[_FillJob]:''',
)

swap(
    '''        merged.update([outer, *holes])
    jobs.extend(
        (index, _FillJob(loop=loop, rims=(loop,)))
        for index, loop in enumerate(loops)
        if index not in merged
    )
    return [job for _index, job in sorted(jobs, key=lambda item: item[0])]''',
    '''        merged.update([outer, *holes])
    # Zwei übrige Ringe, die die Enden einer fehlenden Wand sind, werden ein
    # Mantel (:func:`_band_between`).
    if owner_of is not None and centroids is not None:
        single = [
            index for index in range(len(loops)) if index not in merged and shapes[index] is not None
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
                jobs.append(
                    (first, _FillJob(loop=[], rims=(loops[first], loops[second]), band=band))
                )
                merged.update([first, second])
                break
    jobs.extend(
        (index, _FillJob(loop=loop, rims=(loop,)))
        for index, loop in enumerate(loops)
        if index not in merged
    )
    return [job for _index, job in sorted(jobs, key=lambda item: item[0])]''',
)

swap(
    '''    jobs = _fill_jobs(
        points, loops, max(10.0 * EPS_GEOM, weld_tolerance(float(mesh.bounds.diagonal)))
    )
    for job in jobs:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        loop = job.loop''',
    '''    triangles_now = np.asarray(body.triangles, dtype=np.float64)
    centroids = (triangles_now[:, 0] + triangles_now[:, 1] + triangles_now[:, 2]) / 3.0
    faces_now = np.asarray(body.faces, dtype=np.int64)
    jobs = _fill_jobs(
        points,
        loops,
        max(10.0 * EPS_GEOM, weld_tolerance(float(mesh.bounds.diagonal))),
        neighbour_of,
        centroids,
    )
    position = 0
    while position < len(jobs):
        job = jobs[position]
        position += 1
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        loop = job.loop''',
)
swap(
    '''            spanned += area_of_rim if number == 0 else -area_of_rim
        wide_here = spanned > limit''',
    '''            spanned += area_of_rim if number == 0 else -area_of_rim
        if job.band is not None:
            corners = points[job.band]
            spanned = (
                float(
                    np.linalg.norm(
                        np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]),
                        axis=1,
                    ).sum()
                )
                / 2.0
            )
            centre = (
                centre
                + np.asarray(units.exact_centre(points[job.rims[1]].tolist()), dtype=np.float64)
            ) / 2.0
        wide_here = spanned > limit''',
)
swap(
    '''        # Eine Fläche mit Löchern bekommt keinen Fächer: Er deckte die Löcher.
        attempts = [_loop_triangles(points, loop, taken, cancelled)]
        if len(job.rims) == 1:
            attempts.append(_loop_fan(loop, len(points)))
        for attempt in attempts:
            if len(job.rims) > 1 and len(attempt) and int(attempt.max()) >= len(points):
                continue
            if not len(attempt) or normal is None or _folds(reachable[attempt], normal):
                continue''',
    '''        # Eine Fläche mit Löchern bekommt keinen Fächer: Er deckte die Löcher.
        # Ein Mantel ist fertig und wird nur geprüft.
        if job.band is not None:
            attempts = [job.band]
        else:
            attempts = [_loop_triangles(points, loop, taken, cancelled)]
            if len(job.rims) == 1:
                attempts.append(_loop_fan(loop, len(points)))
        for attempt in attempts:
            if len(job.rims) > 1 and len(attempt) and int(attempt.max()) >= len(points):
                continue
            if job.band is not None:
                if _band_crosses(points, faces_now, attempt, cancelled):
                    continue
            elif not len(attempt) or normal is None or _folds(reachable[attempt], normal):
                continue''',
)
swap(
    '''        if chosen is None:
            blocked += 1
            continue
        pieces = chosen''',
    '''        if chosen is None:
            if job.band is not None:
                # Kein Mantel — dann werden die zwei Ringe gedeckelt wie bisher.
                jobs.extend(_FillJob(loop=rim, rims=(rim,)) for rim in job.rims)
                continue
            blocked += 1
            continue
        pieces = chosen''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
