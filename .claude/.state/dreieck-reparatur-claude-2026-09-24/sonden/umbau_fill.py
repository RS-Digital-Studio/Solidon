"""Einmalig: den Ringfüller auf Datensätze mit Flächenprüfung umbauen."""

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, old[:80]
    text = text.replace(old, new, 1)


swap(
    '''def fill_boundary_loops(mesh: MeshData) -> tuple[MeshData, int, int]:
    """Schließt jeden Randring, der ein Loch ist — und lässt stehen, was eine
    fehlende Wand ist.
''',
    '''@dataclass(frozen=True, slots=True)
class _RingFill:
    """Die Füllung eines Rings, bevor sie ins Netz kommt.

    ``pieces`` nennt die Fächermitte als ``-1``; ihre Nummer steht erst fest,
    wenn klar ist, welche Füllungen bleiben.
    """

    pieces: np.ndarray
    origins: tuple[int, ...]
    middle: np.ndarray | None
    wide: bool
    spanned: float
    centre: np.ndarray
    edges: int


@dataclass(frozen=True, slots=True)
class _Filled:
    """Was ein Durchgang des Ringfüllers getan und gelassen hat."""

    mesh: MeshData
    closed: int = 0
    wide: int = 0
    #: Randkanten und Fläche der Teile, die offen blieben, weil ihre Füllung
    #: nur eine Doppelfläche ohne Volumen ergäbe.
    flat_edges: int = 0
    flat_area: float = 0.0
    #: Mitte und Fläche der größten geschlossenen Öffnung.
    widest: tuple[float, float, float] | None = None
    widest_span: float = 0.0


def _assembled(
    mesh: MeshData, records: Sequence[_RingFill], slots: np.ndarray | None
) -> MeshData:
    """Das Netz mit den Füllungen ``records``; Farben und Slots vom Nachbarn am Ring."""
    body = mesh.raw
    points = np.asarray(body.vertices, dtype=float)
    middles = [record.middle for record in records if record.middle is not None]
    vertices = np.vstack([points, np.asarray(middles, dtype=float)]) if middles else points
    added: list[np.ndarray] = []
    origin: list[int] = []
    next_middle = len(points)
    for record in records:
        pieces = record.pieces
        if record.middle is not None:
            pieces = np.where(pieces < 0, next_middle, pieces)
            next_middle += 1
        added.append(pieces)
        origin.extend(record.origins)
    faces = np.vstack([np.asarray(body.faces, dtype=np.int64), *added])
    patched = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    # Die alten Flächen behalten ihre Farbe, die neuen erben die ihres Nachbarn
    # am Ring — wie die Materialslots darüber (§20).
    carried = np.asarray(origin, dtype=np.int64)
    _carried_colours(
        body, patched, np.concatenate([np.arange(len(body.faces), dtype=np.int64), carried])
    )
    slot_values: tuple[int, ...] = ()
    if slots is not None and len(slots) == len(body.faces):
        slot_values = tuple(int(value) for value in np.concatenate([slots, slots[carried]]))
    return MeshData.of(patched, slots=slot_values)


def _flat_fills(patched: MeshData, first_new: int, owners: np.ndarray) -> set[int]:
    """Welche Füllungen einen Teil schließen, der danach kein Volumen hat.

    **Eine Fläche ohne Dicke wird nicht zum Körper erklärt** (Entscheidung
    Robert, 24.09.2026). Ihr Rand ist ein Ring, und ihn zu schließen legt eine
    zweite Fläche deckungsgleich auf die erste: dicht nach der Kantenzählung,
    Volumen null, und jedes Dreieck durchdringt sein Gegenüber. Danach war
    *Offene Fläche schließen* gesperrt, weil der Körper „schon geschlossen“
    war — und ein loses Einzeldreieck wurde zum Kleinstteil, das die Reparatur
    selbst gebaut hatte. Gemessen wird je Teil die Dicke ``|V| / A``; unter
    ``EPS_GEOM`` bleibt der Ring offen. Die Summen laufen über ``np.cross``
    und Grundrechenarten (RM-187).
    """
    body = patched.raw
    components = face_components(body)
    labels = np.empty(len(body.faces), dtype=np.int64)
    for index, faces in enumerate(components):
        labels[faces] = index
    triangles = np.asarray(body.triangles, dtype=np.float64)
    crossed = np.cross(triangles[:, 1], triangles[:, 2])
    products = (
        triangles[:, 0, 0] * crossed[:, 0]
        + triangles[:, 0, 1] * crossed[:, 1]
        + triangles[:, 0, 2] * crossed[:, 2]
    )
    volume = np.bincount(labels, weights=products, minlength=len(components)) / 6.0
    area = np.bincount(labels, weights=np.asarray(body.area_faces), minlength=len(components))
    flat = np.flatnonzero(np.abs(volume) <= EPS_GEOM * area)
    if not len(flat):
        return set()
    return {int(owner) for owner in owners[np.isin(labels[first_new:], flat)]}


def fill_boundary_loops(mesh: MeshData) -> tuple[MeshData, int, int]:
    """Schließt jeden Randring, der ein Loch ist — und lässt stehen, was eine
    fehlende Wand ist.
''',
)

swap(
    '''    Zurück kommt der Körper, wie viele Ringe geschlossen wurden und wie viele
    davon groß genug für eine Warnung waren (:data:`FILL_LOOP_SHARE`). Die
    Materialslots der neuen Dreiecke erben vom Nachbarn am Ring (§20).
    """
    # Sanduhren aufgetrennt, Achten in ihre Schlaufen zerlegt (:func:`_hole_rings`).
    mesh, loops = _hole_rings(mesh)
    if not loops:
        return mesh, 0, 0
''',
    '''    Zurück kommt der Körper, wie viele Ringe geschlossen wurden und wie viele
    davon groß genug für eine Warnung waren (:data:`FILL_LOOP_SHARE`). Die
    Materialslots der neuen Dreiecke erben vom Nachbarn am Ring (§20).
    """
    filled = _fill_loops(mesh)
    return filled.mesh, filled.closed, filled.wide


def _fill_loops(mesh: MeshData) -> _Filled:
    """:func:`fill_boundary_loops` mit allem, was der Bericht darüber sagt."""
    # Sanduhren aufgetrennt, Achten in ihre Schlaufen zerlegt (:func:`_hole_rings`).
    mesh, loops = _hole_rings(mesh)
    if not loops:
        return _Filled(mesh)
''',
)

swap(
    '''    added: list[np.ndarray] = []
    added_from: list[int] = []
    extra_points: list[np.ndarray] = []
    filled = 0
    too_wide = 0
    blocked = 0
    for loop in loops:''',
    '''    records: list[_RingFill] = []
    blocked = 0
    for loop in loops:''',
)

swap(
    '''            middle_here = bool(int(attempt.max()) >= len(points))
            pieces = (
                np.where(attempt == len(points), len(points) + len(extra_points), attempt)
                if middle_here
                else attempt
            )''',
    '''            middle_here = bool(int(attempt.max()) >= len(points))
            pieces = np.where(attempt == len(points), -1, attempt) if middle_here else attempt''',
)

swap(
    '''        pieces = chosen
        if needs_middle:
            extra_points.append(centre)
        added.append(pieces)
        if wide_here:
            too_wide += 1
        # Jede Seite zählt''',
    '''        pieces = chosen
        origins: list[int] = []
        # Jede Seite zählt''',
)

swap(
    '''            neighbour = next(
                (neighbour_of[edge] for edge in edges if edge in neighbour_of), fallback
            )
            added_from.append(neighbour)
            for edge in edges:
                neighbour_of.setdefault(edge, neighbour)
        filled += 1
''',
    '''            neighbour = next(
                (neighbour_of[edge] for edge in edges if edge in neighbour_of), fallback
            )
            origins.append(neighbour)
            for edge in edges:
                neighbour_of.setdefault(edge, neighbour)
        records.append(
            _RingFill(
                pieces=pieces,
                origins=tuple(origins),
                middle=centre if needs_middle else None,
                wide=wide_here,
                spanned=spanned,
                centre=centre,
                edges=len(loop),
            )
        )
''',
)

start = text.index("    if not added:\n        return mesh, 0, 0\n")
end = text.index("def resolve_branching_edges(")
text = (
    text[:start]
    + '''    if not records:
        return _Filled(mesh)

    patched = _assembled(mesh, records, slots)
    owners = np.repeat(
        np.arange(len(records), dtype=np.int64), [len(record.pieces) for record in records]
    )
    flat = _flat_fills(patched, len(body.faces), owners)
    flat_edges = sum(records[index].edges for index in flat)
    flat_area = sum(records[index].spanned for index in flat)
    if flat:
        records = [record for index, record in enumerate(records) if index not in flat]
        patched = _assembled(mesh, records, slots) if records else mesh
    wide = [record for record in records if record.wide]
    widest = max(wide, key=lambda record: record.spanned, default=None)
    _log.info(
        "filled %d boundary loop(s), %d wide, %d would branch, %d left open without thickness",
        len(records),
        len(wide),
        blocked,
        len(flat),
    )
    return _Filled(
        patched,
        closed=len(records),
        wide=len(wide),
        flat_edges=flat_edges,
        flat_area=flat_area,
        widest=None if widest is None else tuple(float(value) for value in widest.centre),
        widest_span=0.0 if widest is None else widest.spanned,
    )


'''
    + text[end:]
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
