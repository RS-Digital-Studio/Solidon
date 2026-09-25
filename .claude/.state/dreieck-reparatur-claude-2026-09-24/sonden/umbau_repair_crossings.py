"""Einmalig: repair.py — Merker der Durchdringungssuche, Schalenfrage,
Nachprüfung im Schnittbereich, Fortschritt (B18/B11/B4-Rest/B3-Rest)."""

from __future__ import annotations

from pathlib import Path

path = Path("app/core/geom/repair.py")
text = path.read_text(encoding="utf-8")


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    assert text.count(old) == count, (text.count(old), old[:90])
    text = text.replace(old, new)


# --- Budget ------------------------------------------------------------------
swap(
    """#: Wie viele Sweep-Paare die Durchdringungssuche mindestens prüft.
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
    \"\"\"Wie viele Sweep-Paare die Durchdringungssuche an diesem Netz prüft.\"\"\"
    return max(MAX_INTERSECTION_PAIRS, INTERSECTION_PAIRS_PER_TRIANGLE * triangles)
""",
    """#: Wie viele Kandidatenpaare die Durchdringungssuche mindestens prüft —
#: gezählt nach dem Achsenfilter, also die Paare, die wirklich Rechenzeit
#: kosten (rund zwei Mikrosekunden je Paar).
#:
#: Die Suche ist im schlechtesten Fall quadratisch — ein Netz aus lauter
#: deckungsgleichen Flächen erzeugt beliebig viele Paare —, und darüber bricht
#: sie ab und meldet, was sie bis dahin gefunden hat. Eine unvollständige
#: Markierung ist dabei ehrlich: Was dasteht, ist wirklich eine Durchdringung.
MAX_INTERSECTION_PAIRS: Final = 2_000_000

#: Und wie viele je Dreieck (Durchsicht 24.09.2026). Eine feste Zahl riss an
#: gewöhnlichen Teilen, und gezählt wurden die Rohpaare des Sweeps: Ein
#: Besteckkorb mit 8 672 Dreiecken brachte 2,7 Millionen davon, und jede
#: Reparatur daran warnte „unvollständig". Nach dem Achsenfilter sind es
#: 0,8 Millionen; organische Netze liegen dort bei sechs bis sieben Paaren je
#: Dreieck (Spiderman 885 570 Dreiecke: 5,9 Millionen, Drache 2,33 Millionen:
#: 14,5 Millionen), und zwölf lassen jedem vollständig Luft. Wer lange
#: Splitterdreiecke trägt (Besenhalter: 54 je Dreieck), endet nach dem Sockel
#: von zwei Millionen mit einem Hinweis statt nach neun Sekunden. Das
#: Fünfhundertfache, das hier einen Nachmittag stand, ließ die Netzfehlerkarte
#: am Besenhalter 8 und am Spiderman 12 Sekunden rechnen.
INTERSECTION_PAIRS_PER_TRIANGLE: Final = 12


def intersection_budget(triangles: int) -> int:
    \"\"\"Wie viele gefilterte Kandidatenpaare die Durchdringungssuche an diesem Netz prüft.\"\"\"
    return max(MAX_INTERSECTION_PAIRS, INTERSECTION_PAIRS_PER_TRIANGLE * triangles)
""",
)

# --- Suche mit Merker und Fortschritt ----------------------------------------
swap(
    '''def self_intersecting_faces(
    mesh: MeshData, cancelled: CancelToken | None = None
) -> tuple[int, ...]:
    """Belegte Durchdringungen; für Entwarnungen auch den Prüfstatus lesen."""
    return self_intersection_check(mesh, cancelled)[0]
''',
    '''def self_intersecting_faces(
    mesh: MeshData, cancelled: CancelToken | None = None
) -> tuple[int, ...]:
    """Belegte Durchdringungen; für Entwarnungen auch den Prüfstatus lesen."""
    return self_intersection_check(mesh, cancelled)[0]


def crossings_of(
    mesh: MeshData,
    cancelled: CancelToken | None = None,
    progress: Callable[[float], None] | None = None,
) -> Crossings:
    """Die Paare, die sich schneiden — einmal je Netz, im Cache des Netzes.

    **Reparatur, Vorschau und Netzfehlerkarte fragen dasselbe Netz** (Befund
    B11 der Durchsicht 24.09.2026): Die Suche kostet am Drachen 27 Sekunden,
    und jede Stelle rechnete sie für sich. Der Merker verfällt mit der
    Geometrie wie die Kantentabelle; ein Ergebnis mit kleinerem Budget gilt nur,
    wenn es vollständig war.
    """
    from app.core.geom.intersections import crossing_face_pairs

    body = mesh.raw
    budget = intersection_budget(len(body.faces))
    cache = getattr(body, "_cache", None)
    if cache is not None:
        cache.verify()
        remembered = cache.get("solidon_crossings") if "solidon_crossings" in cache else None
        if remembered is not None:
            known_budget, known = remembered
            if known.complete or known_budget >= budget:
                return cast(Crossings, known)
    found = crossing_face_pairs(
        body.vertices, body.faces, cancelled, max_pairs=budget, progress=progress
    )
    if not found.complete:
        _log.info("self-intersection search stopped after %d pairs", budget)
    if cache is not None:
        cache["solidon_crossings"] = (budget, found)
    return found
''',
)
swap(
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
''',
    '''    Die Suche deckelt sich an :func:`intersection_budget` Kandidatenpaaren;
    was sie bis dahin fand, schneidet wirklich. Das Ergebnis merkt sich das
    Netz (:func:`crossings_of`).
    """
    found = crossings_of(mesh, cancelled)
    return found.faces, found.complete


def _crossing_shape(mesh: MeshData, crossings: Crossings) -> str:
    """Was sich schneidet: ``"shells"`` — verschiedene Schalen überlappen —,
    ``"overlay"`` — Flächen liegen deckungsgleich übereinander — oder
    ``"self"`` — eine Schale läuft durch sich selbst.

    **Nur die ersten zwei löst die Vereinigung** (Befund B18 der Durchsicht
    24.09.2026). Die Eigenkreuzung einer einzigen Schale ließ sich am ganzen
    Korpus nicht auflösen — Achterröhre, Spiderman, Piratenschiff —, und der
    Versuch kostete dort 13 bis 49 Sekunden, bevor „ließen sich nicht sicher
    auflösen" kam. Gefragt wird deshalb vorher: Liegt ein schräges Paar in
    derselben Schale, ist es eine Eigenkreuzung.
    """
    labels = np.empty(len(mesh.raw.faces), dtype=np.int64)
    for index, faces in enumerate(face_components(mesh.raw)):
        labels[faces] = index
    same_shell = labels[crossings.first] == labels[crossings.second]
    if bool(np.any(same_shell & ~crossings.coplanar)):
        return "self"
    return "overlay" if bool(np.all(same_shell)) else "shells"
''',
)

# --- Vorprüfung --------------------------------------------------------------
swap(
    '''def _intersections_resolvable(mesh: MeshData) -> str | None:
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
        return "flat"''',
    '''def _intersections_resolvable(mesh: MeshData, crossings: Crossings | None = None) -> str | None:
    """Warum sich die Überschneidungen hier nicht auflösen lassen — ``None``, wenn doch.

    Dieselbe Vorprüfung wie :func:`resolve_self_intersections`, damit der
    Bericht nur zum Auflösen rät, wo es tragen kann: ``"open"`` (offen oder
    verzweigt), ``"winding"`` (Außenseiten zeigen gegeneinander), ``"flat"``
    (kein Volumen), ``"self"`` (eine Schale kreuzt sich selbst,
    :func:`_crossing_shape`), ``"cavity"`` (eine Innenschale, deren Zuordnung
    nicht belegt ist).
    """
    if not mesh.is_watertight:
        return "open"
    if not mesh.raw.is_winding_consistent:
        return "winding"
    if not mesh.volume > 0.0:
        return "flat"
    if crossings is not None and len(crossings.first):
        if _crossing_shape(mesh, crossings) == "self":
            return "self"''',
)

# --- Auflösung: Merker, Schalenfrage, Nachprüfung im Schnittbereich ----------
swap(
    '''    Nur die direkte Stufe ist erlaubt. Bleiben Schnitte oder ist die
    Nachprüfung unvollständig, kommt der unveränderte Eingang zurück.
    ``checked_faces`` übernimmt eine unmittelbar zuvor gelaufene Prüfung
    desselben Netzes, damit die Reparatur die Kandidatensuche nicht doppelt fährt.
    """
    from app.core.geom.boolean import boolean

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not _has_volume(mesh):
        return mesh, False
    if checked_faces is None:
        checked_faces, _complete = self_intersection_check(mesh, cancelled)
    if not checked_faces:
        return mesh, False''',
    '''    Nur die direkte Stufe ist erlaubt. Bleiben Schnitte oder ist die
    Nachprüfung unvollständig, kommt der unveränderte Eingang zurück.
    ``checked_faces`` ist ohne Wirkung und bleibt für ältere Aufrufer: Die
    Prüfung desselben Netzes merkt sich das Netz selbst (:func:`crossings_of`).

    **Nachgeprüft wird, wo geschnitten wurde** (Befund B18 der Durchsicht
    24.09.2026). Die Vereinigung zerlegt nur Dreiecke, die schnitten; was
    außerhalb ihres Hüllquaders liegt, stammt unverändert aus schnittfreien
    Eingängen und kann nichts schneiden, was es vorher nicht schnitt. Bis
    dahin lief nach jeder Vereinigung eine zweite vollständige Suche.
    """
    from app.core.geom.boolean import boolean

    del checked_faces
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not _has_volume(mesh):
        return mesh, False
    crossings = crossings_of(mesh, cancelled)
    if not len(crossings.first) or _crossing_shape(mesh, crossings) == "self":
        return mesh, False''',
)
swap(
    '''    if not _has_volume(rebuilt):
        return mesh, False
    remaining, complete = self_intersection_check(rebuilt, cancelled)
    if remaining or not complete:
        return mesh, False''',
    '''    if not _has_volume(rebuilt):
        return mesh, False
    if _still_crosses(mesh, crossings, rebuilt, cancelled):
        return mesh, False''',
)
swap(
    '''def _nearest_old_face(source: trimesh.Trimesh, target: trimesh.Trimesh) -> np.ndarray:''',
    '''def _still_crosses(
    before: MeshData, crossings: Crossings, after: MeshData, cancelled: CancelToken | None
) -> bool:
    """Ob das Ergebnis einer Vereinigung dort noch schneidet, wo vorher geschnitten wurde.

    Geprüft werden die Dreiecke des Ergebnisses, deren Hüllquader den der
    alten Schnittdreiecke berührt — um die Schweißtoleranz erweitert. Eine
    unvollständige Suche zählt als „schneidet noch": Erfolg wird nur gemeldet,
    wenn er belegt ist.
    """
    from app.core.geom.intersections import crossing_face_pairs

    old = np.asarray(before.raw.triangles, dtype=np.float64)[np.asarray(crossings.faces)]
    margin = weld_tolerance(before.bounds.diagonal) + EPS_GEOM
    low = old.reshape(-1, 3).min(axis=0) - margin
    high = old.reshape(-1, 3).max(axis=0) + margin
    triangles = np.asarray(after.raw.triangles, dtype=np.float64)
    near = np.flatnonzero(
        np.all(triangles.max(axis=1) >= low, axis=1) & np.all(triangles.min(axis=1) <= high, axis=1)
    )
    if len(near) < 2:
        return False
    faces = np.asarray(after.raw.faces, dtype=np.int64)[near]
    found = crossing_face_pairs(
        after.raw.vertices, faces, cancelled, max_pairs=intersection_budget(len(near))
    )
    return bool(len(found.first)) or not found.complete


def _nearest_old_face(source: trimesh.Trimesh, target: trimesh.Trimesh) -> np.ndarray:''',
)

# --- Befunde -----------------------------------------------------------------
swap(
    '''    found, complete = self_intersection_check(result.mesh, cancelled)
    if not found:
        if not complete:''',
    '''    crossings = crossings_of(result.mesh, cancelled, _search_progress(progress))
    found, complete = crossings.faces, crossings.complete
    if not found:
        if not complete:''',
)
swap(
    '''    blocked = _intersections_resolvable(result.mesh)
    if self_intersections and blocked is None:
        result.mesh, rebuilt = resolve_self_intersections(
            result.mesh, cancelled, checked_faces=found
        )''',
    '''    blocked = _intersections_resolvable(result.mesh, crossings)
    if blocked == "self":
        # Eine Eigenkreuzung löst die Vereinigung nicht — kein Versuch, kein
        # Rat dazu, gleich wie der Schritt eingestellt ist.
        result.findings.append(
            Finding(
                code="repair.self_crossing",
                severity="warning",
                message=_(
                    "Die Oberfläche kreuzt sich selbst. Viele Slicer drucken solche Stellen "
                    "trotzdem richtig."
                ),
                suggestions=(SHOW_LOCATIONS,),
            )
        )
    elif self_intersections and blocked is None:
        if progress is not None:
            progress(1.0, str(_("Überschneidungen auflösen")))
        result.mesh, rebuilt = resolve_self_intersections(result.mesh, cancelled)''',
)
swap(
    '''    if not self_intersections:
        result.findings.append(
            Finding(
                code="repair.self_intersections_detected",''',
    '''    if blocked == "self":
        pass
    elif not self_intersections:
        result.findings.append(
            Finding(
                code="repair.self_intersections_detected",''',
)
swap(
    '''def _intersection_findings(
    result: RepairResult, *, self_intersections: bool, cancelled: CancelToken | None
) -> None:''',
    '''def _search_progress(progress: ProgressFn | None) -> Callable[[float], None] | None:
    """Der Fortschritt der Suche als Satz, den der Kunde liest."""
    if progress is None:
        return None
    text = str(_("Überschneidungen suchen"))
    return lambda fraction: progress(fraction, text)


def _intersection_findings(
    result: RepairResult,
    *,
    self_intersections: bool,
    cancelled: CancelToken | None,
    progress: ProgressFn | None = None,
) -> None:''',
)
swap(
    '''    self_intersections: bool = False,
    inspect_intersections: bool = False,
    cancelled: CancelToken | None = None,
) -> RepairResult:''',
    '''    self_intersections: bool = False,
    inspect_intersections: bool = False,
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
) -> RepairResult:''',
)
swap(
    '''        _intersection_findings(result, self_intersections=self_intersections, cancelled=cancelled)''',
    '''        _intersection_findings(
            result, self_intersections=self_intersections, cancelled=cancelled, progress=progress
        )''',
)
swap(
    """from collections.abc import Sequence
""",
    """from collections.abc import Callable, Sequence
""",
)
swap(
    """from app.core.types import CancelToken, Finding, SolverInfo
""",
    """from app.core.types import CancelToken, Finding, ProgressFn, SolverInfo
""",
)
swap(
    """from app.core.geom.attributes import transfer
""",
    """from app.core.geom.attributes import transfer
from app.core.geom.intersections import Crossings
""",
)
path.write_text(text, encoding="utf-8", newline="\n")
print("ok")
