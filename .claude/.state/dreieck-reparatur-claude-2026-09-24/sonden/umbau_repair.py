"""Einmalig: repair() neu fassen, Budget der Durchdringungssuche, Füllrunden."""

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str) -> None:
    global text
    assert text.count(old) == 1, old[:80]
    text = text.replace(old, new, 1)


# --- Füllrunden -------------------------------------------------------------
start = text.index("def _filled_with_count(mesh: MeshData) -> tuple[MeshData, bool, int]:")
end = text.index("def fill_holes(mesh: MeshData, stitch: bool = True)")
text = (
    text[:start]
    + '''def _filled_rounds(mesh: MeshData) -> _Filled:
    """Der Ringfüller in Runden, bis kein Ring mehr aufgeht (:data:`FILL_ROUNDS`).

    Gezählt wird über alle Runden; was ohne Dicke offen blieb, sagt die letzte
    — diese Ringe kommen jede Runde wieder und bleiben jede Runde offen.
    """
    if not open_edge_count(mesh):
        return _Filled(mesh)
    working = mesh
    closed = 0
    wide = 0
    widest: tuple[float, float, float] | None = None
    widest_span = 0.0
    last = _Filled(mesh)
    for _round in range(FILL_ROUNDS):
        last = _fill_loops(working)
        working = last.mesh
        closed += last.closed
        wide += last.wide
        if last.widest is not None and last.widest_span > widest_span:
            widest, widest_span = last.widest, last.widest_span
        if not last.closed:
            break
    return _Filled(
        working,
        closed=closed,
        wide=wide,
        flat_edges=last.flat_edges,
        flat_area=last.flat_area,
        widest=widest,
        widest_span=widest_span,
    )


def _filled_with_count(mesh: MeshData) -> tuple[MeshData, bool, int]:
    """Wie :func:`fill_holes` ohne Vernähen, aber mit der Zahl der großen
    Öffnungen für den Bericht."""
    filled = _filled_rounds(mesh)
    return filled.mesh, filled.closed > 0, filled.wide


'''
    + text[end:]
)

# --- Budget der Durchdringungssuche -------------------------------------------
swap(
    '''#: Wie viele Dreieckspaare die Durchdringungssuche höchstens prüft.
#:
#: Die Karte hat ein Interaktionsbudget (§18.4, §31), und die Suche ist im
#: schlechtesten Fall quadratisch — ein Netz aus lauter deckungsgleichen
#: Flächen erzeugt beliebig viele Paare. Zwei Millionen Paare rechnet numpy in
#: Bruchteilen einer Sekunde; darüber bricht die Suche ab und meldet, was sie
#: bis dahin gefunden hat. Eine unvollständige Markierung ist dabei ehrlich:
#: Was dasteht, ist wirklich eine Durchdringung.
MAX_INTERSECTION_PAIRS: Final = 2_000_000
''',
    '''#: Wie viele Sweep-Paare die Durchdringungssuche mindestens prüft.
#:
#: Die Suche ist im schlechtesten Fall quadratisch — ein Netz aus lauter
#: deckungsgleichen Flächen erzeugt beliebig viele Paare —, und darüber bricht
#: sie ab und meldet, was sie bis dahin gefunden hat. Eine unvollständige
#: Markierung ist dabei ehrlich: Was dasteht, ist wirklich eine Durchdringung.
MAX_INTERSECTION_PAIRS: Final = 2_000_000

#: Und wie viele je Dreieck (Durchsicht 24.09.2026). Eine feste Zahl riss an
#: gewöhnlichen Teilen: Ein Besteckkorb mit 8 672 Dreiecken bringt wegen seiner
#: langen Splitterdreiecke 2,7 Millionen Sweep-Paare, ein Besenhalter mit
#: 59 740 schon 22 Millionen, ein Baum mit 166 400 acht Millionen — alle ohne
#: eine Durchdringung. Jede Reparatur daran warnte „unvollständig", die
#: Netzfehlerkarte zeigte das ganze Modell als ungeprüft, und eine richtige
#: Vereinigung (Bohrhalter, 69 Schalen) wurde verworfen, weil ihre Nachprüfung
#: knapp über zwei Millionen lag. Gemessen am Korpus liegen gewöhnliche Netze
#: bei 50 bis 400 Paaren je Dreieck; das Budget wächst deshalb mit dem Netz
#: und bleibt für den quadratischen Fall trotzdem linear.
INTERSECTION_PAIRS_PER_TRIANGLE: Final = 512


def intersection_budget(triangles: int) -> int:
    """Wie viele Sweep-Paare die Durchdringungssuche an diesem Netz prüft."""
    return max(MAX_INTERSECTION_PAIRS, INTERSECTION_PAIRS_PER_TRIANGLE * triangles)
''',
)
swap(
    '''    Die Suche deckelt sich an :data:`MAX_INTERSECTION_PAIRS` Kandidaten des
    Sweeps; was sie bis dahin fand, schneidet wirklich.
    """
    from app.core.geom.intersections import crossing_faces

    body = mesh.raw
    found, complete = crossing_faces(
        body.vertices, body.faces, cancelled, max_pairs=MAX_INTERSECTION_PAIRS
    )
    if not complete:
        _log.info("self-intersection search stopped after %d pairs", MAX_INTERSECTION_PAIRS)
    return found, complete
''',
    '''    Die Suche deckelt sich an :func:`intersection_budget` Kandidaten des
    Sweeps; was sie bis dahin fand, schneidet wirklich.
    """
    from app.core.geom.intersections import crossing_faces

    body = mesh.raw
    budget = intersection_budget(len(body.faces))
    found, complete = crossing_faces(body.vertices, body.faces, cancelled, max_pairs=budget)
    if not complete:
        _log.info("self-intersection search stopped after %d pairs", budget)
    return found, complete


def _intersections_resolvable(mesh: MeshData) -> str | None:
    """Warum sich die Überschneidungen hier nicht auflösen lassen — ``None``, wenn doch.

    Dieselbe Vorprüfung wie :func:`resolve_self_intersections`, damit der
    Bericht nur zum Auflösen rät, wo es tragen kann: ``"open"`` (offen oder
    verzweigt), ``"winding"`` (Außenseiten zeigen gegeneinander), ``"flat"``
    (kein Volumen), ``"cavity"`` (eine Innenschale, deren Zuordnung nicht
    belegt ist).
    """
    if not mesh.is_watertight:
        return "open"
    if not mesh.raw.is_winding_consistent:
        return "winding"
    if not mesh.volume > 0.0:
        return "flat"
    for faces in face_components(mesh.raw):
        piece = MeshData.of(
            cast(trimesh.Trimesh, mesh.raw.submesh([faces], append=True, repair=False))
        )
        if not _has_volume(piece):
            return "cavity"
    return None
''',
)

# --- repair() -----------------------------------------------------------------
start = text.index("def repair(\n    mesh: MeshData,")
end = text.index("@dataclass(frozen=True)\nclass _EdgeTable:")
text = text[:start] + Path(__file__).with_name("repair_neu.py.txt").read_text(encoding="utf-8") + "\n\n" + text[end:]
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
