"""Einmalig: Review R5 — die Bilanz der flachen Ringe am Endstand zählen."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, (text.count(old), old[:100])
    text = text.replace(old, new)


swap(
    '''    spanned: float
    centre: np.ndarray
    edges: int


@dataclass(frozen=True, slots=True)
class _Filled:''',
    '''    spanned: float
    centre: np.ndarray
    edges: int
    #: Die Randkanten des Auftrags über ihre Ecklagen — sie überstehen das
    #: Neunummerieren, mit dem spätere Schritte Ecken wegräumen.
    rim_keys: frozenset[tuple[tuple[float, ...], tuple[float, ...]]] = frozenset()


def _edge_key(
    first: np.ndarray, second: np.ndarray
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Eine Kante über die Lage ihrer Ecken, unabhängig von der Richtung."""
    one = tuple(float(value) for value in first)
    other = tuple(float(value) for value in second)
    return (one, other) if one <= other else (other, one)


@dataclass(frozen=True, slots=True)
class _Filled:''',
)
swap(
    '''    flat_edges: int = 0
    flat_area: float = 0.0
    #: Mitte und Fläche der größten geschlossenen Öffnung.''',
    '''    flat_edges: int = 0
    flat_area: float = 0.0
    #: Je offen gebliebenem Auftrag seine Randkanten und seine Fläche — damit
    #: sich die Bilanz am Endstand neu zählen lässt (:func:`_flat_still_open`).
    flat: tuple[tuple[frozenset[tuple[tuple[float, ...], tuple[float, ...]]], float], ...] = ()
    #: Mitte und Fläche der größten geschlossenen Öffnung.''',
)
swap(
    '''                spanned=spanned,
                centre=centre,
                edges=sum(len(rim) for rim in job.rims),
            )
        )
''',
    '''                spanned=spanned,
                centre=centre,
                edges=sum(len(rim) for rim in job.rims),
                rim_keys=frozenset(
                    _edge_key(points[rim[position]], points[rim[(position + 1) % len(rim)]])
                    for rim in job.rims
                    for position in range(len(rim))
                ),
            )
        )
''',
)
swap(
    '''    flat_edges = sum(records[index].edges for index in flat)
    flat_area = sum(records[index].spanned for index in flat)
''',
    '''    flat_edges = sum(records[index].edges for index in flat)
    flat_area = sum(records[index].spanned for index in flat)
    flat_rings = tuple((records[index].rim_keys, records[index].spanned) for index in sorted(flat))
''',
)
swap(
    '''        flat_edges=flat_edges,
        flat_area=flat_area,
        widest=None
''',
    '''        flat_edges=flat_edges,
        flat_area=flat_area,
        flat=flat_rings,
        widest=None
''',
)
swap(
    '''        flat_edges=last.flat_edges,
        flat_area=last.flat_area,
        widest=widest,
        widest_span=widest_span,
    )
''',
    '''        flat_edges=last.flat_edges,
        flat_area=last.flat_area,
        flat=last.flat,
        widest=widest,
        widest_span=widest_span,
    )


def _flat_still_open(mesh: MeshData, filled: _Filled) -> tuple[int, float]:
    """Randkanten und Fläche der flachen Ringe, die am Endstand noch offen sind.

    **Die Bilanz des Füllers gilt dem Netz, das er sah** (Review R5,
    24.09.2026). Danach fallen lose Splitter weg (:func:`remove_open_splinters`),
    und ihre Ringe standen weiter in der Bilanz: An einem Würfel mit zwanzig
    losen Dreiecken hieß es „Ein Teil des Modells ist eine Fläche ohne Dicke"
    über einem geschlossenen Würfel, und neben einem offenen Fenster wurden
    dessen Ränder abgezogen, bis der Befund über das Fenster ganz fehlen
    konnte. Gezählt wird deshalb, was vom Ring noch als offene Kante dasteht.
    """
    if not filled.flat:
        return 0, 0.0
    points = np.asarray(mesh.raw.vertices, dtype=np.float64)
    rows = _edge_table(mesh).rows(1)
    pairs = np.asarray(mesh.raw.edges, dtype=np.int64)[rows]
    open_keys = {_edge_key(points[first], points[second]) for first, second in pairs.tolist()}
    edges = 0
    area = 0.0
    for keys, spanned in filled.flat:
        if keys and keys <= open_keys:
            edges += len(keys)
            area += spanned
    return edges, area
''',
)
swap(
    '''    total_area = result.mesh.area
    sheet = filled.flat_area >= SMALL_COMPONENT_SHARE * total_area and filled.flat_edges > 0
    if sheet:
        result.findings.append(
            Finding(
                code="repair.no_thickness",
                severity="warning",
                message=_("Das Modell ist eine Fläche ohne Dicke.")
                if filled.flat_area >= 0.5 * total_area
                else _("Ein Teil des Modells ist eine Fläche ohne Dicke."),
                values={"open_edges": filled.flat_edges},
''',
    '''    total_area = result.mesh.area
    flat_edges, flat_area = _flat_still_open(result.mesh, filled)
    sheet = flat_area >= SMALL_COMPONENT_SHARE * total_area and flat_edges > 0
    if sheet:
        result.findings.append(
            Finding(
                code="repair.no_thickness",
                severity="warning",
                message=_("Das Modell ist eine Fläche ohne Dicke.")
                if flat_area >= 0.5 * total_area
                else _("Ein Teil des Modells ist eine Fläche ohne Dicke."),
                values={"open_edges": flat_edges},
''',
)
swap(
    '''        open_edges = max(0, open_edges - filled.flat_edges)
''',
    '''        open_edges = max(0, open_edges - flat_edges)
''',
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
