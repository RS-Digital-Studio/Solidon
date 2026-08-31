"""Netze reparieren (Bauplan §25, §17.2).

Heruntergeladene Modelle sind auf eine Handvoll wiederkehrender Arten kaputt:
offene Kanten, Nadeln, doppelte Flächen, lose Fragmente, umgedrehte Normalen,
Selbstdurchdringungen. Jede wird hier für sich behandelt, und jede meldet,
was sie getan hat — der Bericht muss sagen können, was geändert wurde, und
der Agent muss wissen, worauf er steht (§17.3).

Nichts repariert still: eine Operation, die Geometrie ändert, sagt es in
ihren Befunden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import PROGRAMMING_ERRORS
from app.core.geom.mesh import MeshData, face_components
from app.core.log import get_logger
from app.core.types import Finding
from app.core.units import EPS_GEOM, weld_digits, weld_tolerance
from app.i18n import _

_log = get_logger(__name__)

#: Eine Komponente unter diesem Anteil der größten zählt als loses Fragment.
SMALL_COMPONENT_SHARE = 0.001


@dataclass(slots=True)
class RepairResult:
    """Der reparierte Körper, plus was jeder Schritt wirklich getan hat."""

    mesh: MeshData
    findings: list[Finding] = field(default_factory=list)
    changed: bool = False
    """Ob **irgendein** Schritt am Netz etwas verändert hat.

    Nicht „ist jetzt dicht": Ein Netz mit zwei Löchern, von denen nur eines zu
    überbrücken war, ist verändert und bleibt offen. Beides zugleich zu melden
    ist richtig; „nichts zu reparieren" daneben wäre der Widerspruch."""


def merge_vertices(mesh: MeshData, tolerance: float | None = None) -> tuple[MeshData, int]:
    """Verschweißt zusammenfallende Punkte. Liefert den Körper und wie viele
    Eckpunkte verschwunden sind."""
    body = mesh.raw.copy()
    before = len(body.vertices)
    limit = tolerance if tolerance is not None else weld_tolerance(mesh.bounds.diagonal)
    body.merge_vertices(digits_vertex=weld_digits(limit))
    return mesh.replacing(body), before - len(body.vertices)


def remove_degenerate_faces(mesh: MeshData) -> tuple[MeshData, int]:
    """Null-Flächen-Dreiecke, Nadeln und Duplikate."""
    body = mesh.raw.copy()
    before = len(body.faces)
    body.update_faces(body.nondegenerate_faces(height=EPS_GEOM))
    body.update_faces(body.unique_faces())
    body.remove_unreferenced_vertices()
    return mesh.replacing(body), before - len(body.faces)


def unify_normals(mesh: MeshData) -> tuple[MeshData, bool]:
    """Macht den Umlaufsinn einheitlich und stülpt den Körper nötigenfalls
    nach außen."""
    body = mesh.raw.copy()
    before = float(body.volume)
    trimesh.repair.fix_winding(body)
    if body.is_watertight:
        trimesh.repair.fix_inversion(body)
    return mesh.replacing(body), abs(float(body.volume) - before) > EPS_GEOM


#: Wie weit ein Punkt neben einer Kante sitzen darf und noch als auf ihr
#: liegend zählt. Eine T-Kreuzung stammt aus einem exakten Split im
#: Quell-CAD — die Abweichung ist Rechenrauschen, kein Spalt.
ON_EDGE_TOLERANCE = 1e-4

#: Über so vielen offenen Kanten ist ein Körper kein Modell mit einem Defekt,
#: sondern ein Modell in Stücken — und jeden Randpunkt mit jeder Randkante zu
#: paaren hört auf, die richtige Art zu sein, eine Minute zu verbringen.
MAX_STITCH_EDGES = 4096


def stitch_t_junctions(mesh: MeshData) -> tuple[MeshData, int]:
    """Schließt Spalte, wo ein Punkt auf einer Kante sitzt, die nichts von ihm
    weiß.

    Der Defekt, an den der Lochfüller nicht herankommt — und der, den ein
    echter Download mitbringt. Ein Eiffelturm mit 312 000 Dreiecken hatte
    genau einen: drei offene Kanten über drei Punkten bei ``y=117,63,
    z=42,5`` und x von 100,910, 104,763 und 106,690 — 3,853 + 1,927 = 5,780,
    kollinear bis zur letzten Stelle. Kein Loch, eine **T-Kreuzung**: die
    lange Kante wurde beim Bau der Nachbarfläche von einem Punkt geteilt, und
    der Fläche auf der anderen Seite hat es nie jemand gesagt.
    ``trimesh.repair.fill_holes`` lehnt ab, und zu Recht — ein Dreieck über
    drei kollinearen Punkten hat keine Fläche, und einen Körper mit einer
    Fläche zu schließen, die nicht da ist, ist kein Schließen.

    Was wirklich passt: der anderen Fläche den Punkt geben, der ihr fehlt —
    die Fläche an der langen Kante wird am aufsitzenden Punkt in zwei
    geteilt. Keine neue Geometrie, keine verschobene Oberfläche, und die zwei
    neuen Dreiecke haben die Fläche, die das alte hatte.

    Liefert den Körper und wie viele Flächen geteilt wurden.
    """
    body = mesh.raw.copy()
    boundary = trimesh.grouping.group_rows(body.edges_sorted, require_count=1)
    if not len(boundary) or len(boundary) > MAX_STITCH_EDGES:
        return mesh, 0

    edges = body.edges_sorted[boundary]
    points = np.asarray(body.vertices, dtype=float)
    candidates = np.unique(edges)

    # Welche Fläche welche Randkante trägt: edges_sorted läuft drei je Fläche,
    # in Flächenreihenfolge — der Zeilenindex durch drei ist also die Fläche.
    owner = {
        (int(edges[index][0]), int(edges[index][1])): int(boundary[index] // 3)
        for index in range(len(edges))
    }

    # Vorfilter statt vollständiger Paarung: jede Randkante gegen jeden
    # Randpunkt waren bei 2 100 offenen Kanten elf Sekunden, am eigenen
    # Deckel hochgerechnet vierzig — und `repair()` zahlte sie doppelt. Der
    # Baum liefert je Kante nur die Punkte, die ihrem Mittelpunkt näher
    # liegen als die halbe Kantenlänge plus Toleranz; weiter draußen kann
    # nichts auf der Strecke sitzen.
    from scipy.spatial import cKDTree

    tree = cKDTree(points[candidates])
    starts, ends = points[edges[:, 0]], points[edges[:, 1]]
    centres = (starts + ends) / 2.0
    lengths = np.linalg.norm(ends - starts, axis=1)
    radii = lengths / 2.0 + ON_EDGE_TOLERANCE * np.maximum(lengths, 1.0)
    nearby = tree.query_ball_point(centres, radii)

    splits: dict[int, list[tuple[int, int, int]]] = {}
    for index in range(len(edges)):
        edge = (int(edges[index][0]), int(edges[index][1]))
        face_index = owner[edge]
        start, end = points[edge[0]], points[edge[1]]
        for position in nearby[index]:
            vertex = int(candidates[position])
            if vertex in edge:
                continue
            if _lies_on(points[vertex], start, end):
                splits.setdefault(face_index, []).append((edge[0], edge[1], vertex))
                break

    if not splits:
        return mesh, 0

    faces = [list(map(int, face)) for face in body.faces]
    kept = np.ones(len(faces), dtype=bool)
    added: list[list[int]] = []
    added_from: list[int] = []
    for face_index, cuts in splits.items():
        first, second, vertex = cuts[0]
        face = faces[face_index]
        third = next((entry for entry in face if entry not in (first, second)), None)
        if third is None:
            continue
        # Den Umlaufsinn der Fläche behalten, damit die zwei Hälften dahin
        # schauen, wohin das Ganze schaute.
        position = face.index(first)
        forward = face[(position + 1) % 3] == second
        head, tail = (first, second) if forward else (second, first)
        kept[face_index] = False
        added.extend([[head, vertex, third], [vertex, tail, third]])
        added_from.extend([face_index, face_index])

    if not added:
        return mesh, 0

    rebuilt = np.vstack([np.asarray(body.faces)[kept], np.asarray(added, dtype=np.int64)])
    # Flächenattribute gehören zur Fläche, nicht zu ihrer ursprünglichen
    # Dreiecksaufteilung. Wird ein Dreieck geteilt, erben beide Hälften seine
    # Herkunft — sonst verliert ausgerechnet die Reparatur die Zuordnung von
    # B-Rep-Fläche zu Viewport-Markierung (und ebenso jedes spätere Attribut).
    face_attributes: dict[str, Any] = {}
    for name, values in body.face_attributes.items():
        array = np.asarray(values)
        # Fremde Netze dürfen auch skalare Metadaten tragen. Nur ein Wert je
        # Fläche kann beim Teilen eindeutig mit der Fläche weiterreisen.
        if array.ndim == 0 or len(array) != len(faces):
            continue
        face_attributes[name] = np.concatenate([array[kept], array[added_from]], axis=0)
    stitched = trimesh.Trimesh(
        vertices=body.vertices,
        faces=rebuilt,
        face_attributes=face_attributes,
        process=False,
    )
    _log.info("stitched %d T-junction(s)", len(added) // 2)
    return mesh.replacing(stitched), len(added) // 2


def _lies_on(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> bool:
    """Liegt der Punkt auf der Strecke — zwischen den Enden, nicht dahinter?"""
    along = end - start
    length = float(np.linalg.norm(along))
    if length <= EPS_GEOM:
        return False
    offset = point - start
    travelled = float(np.dot(offset, along)) / (length * length)
    if not (ON_EDGE_TOLERANCE < travelled < 1.0 - ON_EDGE_TOLERANCE):
        return False
    distance = float(np.linalg.norm(offset - travelled * along))
    return distance <= ON_EDGE_TOLERANCE * max(length, 1.0)


def fill_holes(mesh: MeshData, stitch: bool = True) -> tuple[MeshData, bool]:
    """Schließt offene Kanten. Nur kleine Löcher — eine fehlende Wand kann
    trimesh nicht überbrücken.

    Das Vernähen läuft zuerst: eine T-Kreuzung sieht aus wie ein Loch und ist
    keines, und der Füller lässt sie exakt, wie er sie fand (siehe
    :func:`stitch_t_junctions`). ``stitch=False`` ist für Aufrufer, die das
    Vernähen selbst schon gefahren haben — ``repair()`` zahlte es sonst
    doppelt, gemessener Faktor 2,1.

    **Das zweite Rückgabestück heißt „es wurde gefüllt", nicht „es ist jetzt
    dicht".** Der Unterschied ist ein Netz mit zwei Löchern, von denen eines
    zu groß zum Überbrücken ist: Das kleine wurde geschlossen, das Netz blieb
    offen, und die alte Antwort war ``False``. Der Bericht meldete daraufhin
    beides zugleich — „an diesem Netz war nichts zu reparieren" und „das
    Modell ist weiterhin nicht geschlossen" —, und wer das las, konnte den
    Widerspruch nicht auflösen, weil beide Sätze auf ihre Art stimmten.
    Gemessen wird an den offenen Kanten: weniger offene Kanten als vorher heißt
    gefüllt, ob dicht oder nicht. Ob das Netz danach dicht ist, sagt
    ``MeshData.is_watertight`` — der Aufrufer hat das Netz ja in der Hand.
    """
    body = mesh.raw.copy()
    if body.is_watertight:
        return mesh, False
    before = open_edge_count(mesh)
    if stitch:
        stitched, _seams = stitch_t_junctions(mesh.replacing(body))
        body = stitched.raw.copy()
        if body.is_watertight:
            return mesh.replacing(body), True
    trimesh.repair.fill_holes(body)
    filled = mesh.replacing(body)
    return filled, open_edge_count(filled) < before


def remove_small_components(
    mesh: MeshData, share: float = SMALL_COMPONENT_SHARE
) -> tuple[MeshData, int]:
    """Wirft lose Fragmente — aber nur auf Nachfrage, nie beim
    Hereinkommen (§17.1)."""
    pieces = face_components(mesh.raw)
    if len(pieces) <= 1:
        return mesh, 0
    areas = [float(mesh.raw.area_faces[piece].sum()) for piece in pieces]
    largest = max(areas)
    keep = [piece for piece, area in zip(pieces, areas, strict=True) if area >= largest * share]
    if len(keep) == len(pieces):
        return mesh, 0

    body = mesh.raw.copy()
    mask = np.zeros(len(body.faces), dtype=bool)
    for piece in keep:
        mask[piece] = True
    body.update_faces(mask)
    body.remove_unreferenced_vertices()
    return mesh.replacing(body), len(pieces) - len(keep)


def resolve_self_intersections(mesh: MeshData) -> tuple[MeshData, bool]:
    """Lässt den Kern den Körper neu aufbauen; manifold3d normalisiert
    Selbstdurchdringungen.

    Eine Vereinigung eines Körpers mit sich selbst ist auf dem Papier ein
    Leerlauf und in der Praxis ein Aufräumen.

    **An einem Netz, das kein Volumen ist, kann das nicht gehen, und vorher
    wurde es trotzdem versucht.** Die Booleschen Kerne rechnen mit Volumina;
    der Aufruf endete in „Not all meshes are volumes!" — einer Fremdmeldung im
    Protokoll, die niemand liest. Gefunden beim Öffnen von
    ``weg3-generiert-aufbereiten``, also am Beispielprojekt für genau diesen
    Fall.

    **Gefragt wird nach ``is_volume`` und nicht nach ``is_watertight``**, und
    der Unterschied ist der ganze Fund: Nach dem Löcherschließen war das
    Beispiel wasserdicht und trotzdem kein Volumen, weil die Wicklung noch
    nicht einheitlich war — das richtet erst :func:`unify_normals`. Eine
    Vorprüfung auf „wasserdicht" hätte den Aufruf also durchgelassen und
    dieselbe Fremdmeldung erzeugt.

    Teuer ist das nicht: ``is_volume`` prüft wasserdicht, Wicklung und
    Volumen > 0 auf derselben Kantentabelle, die die Kette ohnehin aufbaut —
    gemessen 0,1 bis 0,2 ms an dieser Stelle.
    """
    if not mesh.raw.is_volume:
        return mesh, False
    try:
        rebuilt = trimesh.boolean.union([mesh.raw, mesh.raw])
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # pragma: no cover - kernspezifisch
        _log.warning("could not resolve self-intersections: %s", problem)
        return mesh, False
    if rebuilt is None or not len(rebuilt.faces):
        return mesh, False
    return mesh.replacing(rebuilt), True


def repair(
    mesh: MeshData,
    *,
    weld: bool = True,
    degenerate: bool = True,
    normals: bool = True,
    holes: bool = True,
    small_components: bool = False,
    self_intersections: bool = False,
) -> RepairResult:
    """Führt die gewünschten Schritte in der Reihenfolge aus, die jeden
    einzelnen billiger macht."""
    result = RepairResult(mesh=mesh)

    if weld:
        result.mesh, removed = merge_vertices(result.mesh)
        if removed:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.welded",
                    severity="info",
                    message=_("Doppelte Punkte wurden verschweißt."),
                    values={"removed": removed},
                )
            )

    if degenerate:
        result.mesh, removed = remove_degenerate_faces(result.mesh)
        if removed:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.degenerate_removed",
                    severity="info",
                    message=_("Entartete Dreiecke wurden entfernt."),
                    values={"removed": removed},
                )
            )

    if small_components:
        result.mesh, dropped = remove_small_components(result.mesh)
        if dropped:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.components_removed",
                    severity="warning",
                    message=_("Kleinstteile wurden gelöscht."),
                    values={"removed": dropped},
                )
            )

    if holes:
        # Getrennt gemeldet, weil es ein anderer Defekt mit anderer Antwort
        # ist: eine Naht ist eine Fläche, der ein Punkt fehlte, ein Loch eine
        # Fläche, die fehlte. Wer den Bericht liest, erkennt, ob sein Modell
        # eine Lücke hatte oder nur einen Buchhaltungsfehler.
        open_before = open_edge_count(result.mesh)
        result.mesh, seams = stitch_t_junctions(result.mesh)
        if seams:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.t_junctions",
                    severity="info",
                    message=_("Kanten mit einem Punkt darauf wurden vernäht."),
                    values={"seams": seams},
                )
            )

        # `stitch=False`: das Vernähen ist gerade gelaufen — es erneut zu
        # zahlen war der gemessene Faktor 2,1 auf dem Normalfall „Reparieren
        # an einem heruntergeladenen Modell".
        result.mesh, closed = fill_holes(result.mesh, stitch=False)
        open_after = open_edge_count(result.mesh)
        if closed:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.holes_filled",
                    severity="info",
                    message=_(
                        "{closed} von {total} offenen Kanten geschlossen; "
                        "{remaining} bleiben offen.",
                        closed=open_before - open_after,
                        total=open_before,
                        remaining=open_after,
                    ),
                    values={"before": open_before, "after": open_after},
                )
            )

    if normals:
        result.mesh, flipped = unify_normals(result.mesh)
        if flipped:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.normals_flipped",
                    severity="info",
                    message=_("Die Ausrichtung der Flächen wurde korrigiert."),
                )
            )

    # **Zuletzt, und das ist der Fund.** Der Schritt stand vor dem
    # Löcherschließen und konnte dort nie arbeiten: Er braucht ein Volumen, und
    # eines wird das Netz erst durch Schließen *und* Normalen richten. Gemessen
    # am Beispielprojekt ``weg3-generiert-aufbereiten``: vor dem Schließen kein
    # Volumen, nach dem Schließen wasserdicht aber die Wicklung uneinheitlich,
    # erst nach ``unify_normals`` beides — und dann wirkt er.
    if self_intersections:
        # **Was nicht getan wurde, gehört in den Bericht** (§2.7). Wer ihn
        # liest, soll nicht annehmen, dass geprüft wurde, was übersprungen
        # wurde.
        no_volume = not result.mesh.raw.is_volume
        result.mesh, rebuilt = resolve_self_intersections(result.mesh)
        if rebuilt:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.self_intersections",
                    severity="info",
                    message=_("Selbstdurchdringungen wurden aufgelöst."),
                )
            )
        elif no_volume:
            result.findings.append(
                Finding(
                    code="repair.self_intersections_skipped",
                    severity="info",
                    message=_(
                        "Selbstdurchdringungen wurden nicht geprüft, weil der Körper offen ist. "
                        "Die Defektkarte zeigt die Stellen, die zuerst geschlossen werden müssen."
                    ),
                )
            )

    if not result.mesh.is_watertight:
        result.findings.append(
            Finding(
                code="repair.still_open",
                severity="warning",
                # Der frühere Folgesatz schickte den Nutzer im Kreis:
                # „Kanten verfeinern schließt es" — diese Operation weist ein
                # offenes Netz zurück und empfiehlt wieder Reparieren. Die
                # ehrliche Grenze erklärt, warum der Rest bleibt; die
                # Oberfläche führt von dort zu den betroffenen Stellen (§2.7).
                message=_(
                    "Die Reparatur schließt kleine Löcher, kann fehlende Wände aber nicht ersetzen."
                ),
                values={"open_edges": open_edge_count(result.mesh)},
            )
        )
    return result


def open_edge_count(mesh: MeshData) -> int:
    """Kanten, die zu genau einem Dreieck gehören — das Maß von „offen"."""
    single = trimesh.grouping.group_rows(mesh.raw.edges_sorted, require_count=1)
    return len(single)
