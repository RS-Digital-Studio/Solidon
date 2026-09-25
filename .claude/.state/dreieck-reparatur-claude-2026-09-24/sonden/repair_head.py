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

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Final, cast

import numpy as np

from app.core import units
from app.core.deferred import trimesh
from app.core.errors import PROGRAMMING_ERRORS
from app.core.geom.attributes import transfer
from app.core.geom.mesh import MeshData, face_components, stable_normals, unique_edges
from app.core.geom.transform import along
from app.core.log import get_logger
from app.core.types import CancelToken, Finding
from app.core.units import EPS_GEOM, format_length, weld_digits, weld_tolerance
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
    kept = np.arange(before, dtype=np.int64)
    nondegenerate = np.asarray(body.nondegenerate_faces(height=EPS_GEOM))
    kept = kept[np.flatnonzero(nondegenerate) if nondegenerate.dtype == bool else nondegenerate]
    body.update_faces(nondegenerate)
    unique = np.asarray(body.unique_faces())
    kept = kept[np.flatnonzero(unique) if unique.dtype == bool else unique]
    body.update_faces(unique)
    body.remove_unreferenced_vertices()
    slots = tuple(mesh.slots[int(index)] for index in kept) if mesh.slots else ()
    return MeshData.of(body, slots=slots), before - len(body.faces)


def remove_doubled_faces(mesh: MeshData) -> tuple[MeshData, int]:
    """Deckungsgleiche Dreiecke aufräumen: gegenläufige Paare ganz, gleich
    umlaufende Kopien bis auf eine.

    Zwei gegenläufige Dreiecke mit denselben Ecken sind eine Tasche ohne Volumen. Wer nur
    eine Kopie streicht, lässt die übrigen Kanten des Paares mit je einer
    Fläche zurück und reißt zwei Ränder auf; das Paar zu streichen schließt
    das Netz. Genau das trennt diesen Schritt von ``unique_faces`` in
    :func:`remove_degenerate_faces`, das die erste Kopie behält.

    Gemessen am 16.09.2026 an einer heruntergeladenen Waschschüssel mit
    215 074 Dreiecken: eine verzweigte Kante, an der vier Flächen hängen, zwei
    davon deckungsgleich.

    * Nur eine Kopie entfernt: 2 offene Ränder, weiter verzweigt, offen.
    * Das Paar entfernt: 0 Ränder, 0 Verzweigungen, **geschlossen** — und das
      Volumen auf drei Nachkommastellen unverändert (401,869 cm³).

    **Eine Tasche ist ein gegenläufiges Paar** (nachgemessen am 23.09.2026:
    die zwei Flächen der Waschschüssel laufen gegeneinander um). Zwei **gleich**
    umlaufende Kopien sind keine Tasche, sondern dieselbe Fläche doppelt
    geschrieben — von ihnen bleibt eine. Je Gruppe deckungsgleicher Dreiecke
    heben sich gegenläufige paarweise auf; bleibt danach eine Richtung übrig,
    bleibt von ihr genau ein Dreieck. Drei deckungsgleiche sind damit, wie
    zuvor, eine Tasche *und* eine Fläche.

    **Und nie ein ganzes Teil.** Eine Schale, die ein Export zweimal schrieb,
    ist lauter Paare; fiele jedes, bliebe von ihr nichts — *Reparieren* gab an
    einer doppelt geschriebenen Kugel null Dreiecke zurück. Verschwände ein
    zusammenhängendes Teil vollständig, behält es je Gruppe ihr erstes Dreieck.
    """
    body = mesh.raw.copy()
    before = len(body.faces)
    if not before:
        return mesh, 0
    ordered = np.sort(body.faces, axis=1)
    _unique, inverse, counts = np.unique(ordered, axis=0, return_inverse=True, return_counts=True)
    inverse = np.asarray(inverse).reshape(-1)
    # **Je Gruppe ihre Mitglieder in Flächenreihenfolge, als Feld.** Hier lief
    # eine Schleife über die Gruppen, und jede suchte ihre Mitglieder über alle
    # Dreiecke: An einem Netz, das seine Dreiecke doppelt trägt — ein Export,
    # der dieselbe Schale zweimal schrieb —, war das eine Gruppe je Dreieck
    # und damit quadratisch (100 000 Paare: zwanzig Milliarden Vergleiche,
    # Review 22.09.2026). Was bleibt, entscheidet der Umlauf (Docstring).
    order = np.argsort(inverse, kind="stable")
    group_of = inverse[order]
    faces = np.asarray(body.faces, dtype=np.int64)
    # Umlaufsinn gegenüber der sortierten Folge: gerade Permutation heißt
    # derselbe Umlauf, ungerade der entgegengesetzte.
    swaps = (
        (faces[:, 0] > faces[:, 1]).astype(np.int64)
        + (faces[:, 0] > faces[:, 2])
        + (faces[:, 1] > faces[:, 2])
    )
    forward = swaps % 2 == 0
    ahead = np.bincount(inverse, weights=forward, minlength=len(counts)).astype(np.int64)
    behind = counts - ahead
    # Bleibt eine Richtung übrig, bleibt ihr erstes Dreieck; sonst keines.
    survives = (counts > 1) & (ahead != behind)
    majority = ahead > behind
    candidate = survives[group_of] & (forward[order] == majority[group_of])
    first = np.full(len(counts), -1, dtype=np.int64)
    positions = np.flatnonzero(candidate)
    first[group_of[positions][::-1]] = positions[::-1]
    keep = counts[inverse] == 1
    keep[order[first[first >= 0]]] = True
    if not keep.all():
        # Kein zusammenhängendes Teil verschwindet ganz: Dort war es keine
        # Tasche, sondern das Teil selbst, zweimal geschrieben. Zusammen
        # hängt, was Ecken teilt — über Kanten allein zerfiele es, denn
        # ``face_adjacency`` lässt jede Kante mit mehr als zwei Flächen aus,
        # und an einer Doppelung hat jede Kante vier.
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components

        corners = len(body.vertices)
        links = coo_matrix(
            (
                np.ones(2 * len(faces), dtype=np.int8),
                (
                    np.concatenate([faces[:, 0], faces[:, 1]]),
                    np.concatenate([faces[:, 1], faces[:, 2]]),
                ),
            ),
            shape=(corners, corners),
        )
        pieces, label = connected_components(links, directed=False)
        piece_of = np.asarray(label)[faces[:, 0]]
        kept_in = np.bincount(piece_of, weights=keep, minlength=pieces)
        lost = np.flatnonzero(np.isin(piece_of, np.flatnonzero(kept_in == 0)))
        if len(lost):
            _groups, chosen = np.unique(inverse[lost], return_index=True)
            keep[lost[chosen]] = True
    dropped = int((~keep).sum())
    if not dropped:
        return mesh, 0
    kept_slots = (
        tuple(mesh.slots[int(index)] for index in np.flatnonzero(keep)) if mesh.slots else ()
    )
    body.update_faces(keep)
    body.remove_unreferenced_vertices()
    return MeshData.of(body, slots=kept_slots), dropped


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
    # Gelesen wird am Netz selbst: Die Rechnung darunter baut ein neues und
    # ändert am alten nichts — eine Kopie am Anfang kostete am 1,2-M-Netz
    # bei jedem Aufruf ein Zehntel einer Sekunde, auch ohne einen Rand.
    body = mesh.raw
    boundary = _edge_table(mesh).rows(1)
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

    # Nur die geteilten Dreiecke werden Listen — eine Python-Liste je Dreieck
    # des ganzen Netzes kostete an 1,2 Millionen über eine Sekunde.
    all_faces = np.asarray(body.faces, dtype=np.int64)
    kept = np.ones(len(all_faces), dtype=bool)
    added: list[list[int]] = []
    added_from: list[int] = []
    for face_index, cuts in splits.items():
        first, second, vertex = cuts[0]
        face = [int(entry) for entry in all_faces[face_index]]
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

    rebuilt = np.vstack([all_faces[kept], np.asarray(added, dtype=np.int64)])
    # Flächenattribute gehören zur Fläche, nicht zu ihrer ursprünglichen
    # Dreiecksaufteilung. Wird ein Dreieck geteilt, erben beide Hälften seine
    # Herkunft — sonst verliert ausgerechnet die Reparatur die Zuordnung von
    # B-Rep-Fläche zu Viewport-Markierung (und ebenso jedes spätere Attribut).
    face_attributes: dict[str, Any] = {}
    for name, values in body.face_attributes.items():
        array = np.asarray(values)
        # Fremde Netze dürfen auch skalare Metadaten tragen. Nur ein Wert je
        # Fläche kann beim Teilen eindeutig mit der Fläche weiterreisen.
        if array.ndim == 0 or len(array) != len(all_faces):
            continue
        face_attributes[name] = np.concatenate([array[kept], array[added_from]], axis=0)
    stitched = trimesh.Trimesh(
        vertices=body.vertices,
        faces=rebuilt,
        face_attributes=face_attributes,
        process=False,
    )
    slots: tuple[int, ...] = ()
    if mesh.slots:
        original = np.asarray(mesh.slots, dtype=np.int64)
        slots = tuple(int(slot) for slot in np.concatenate([original[kept], original[added_from]]))
    _log.info("stitched %d T-junction(s)", len(added) // 2)
    return MeshData.of(stitched, slots=slots), len(added) // 2


def _lies_on(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> bool:
    """Liegt der Punkt auf der Strecke — zwischen den Enden, nicht dahinter?"""
    # ``math.hypot`` und ``units.dot3`` statt BLAS (RM-187): Ob ein Punkt auf
    # der Kante sitzt, entscheidet, welches Dreieck geteilt wird.
    along = end - start
    length = math.hypot(float(along[0]), float(along[1]), float(along[2]))
    if length <= EPS_GEOM:
        return False
    offset = point - start
    travelled = units.dot3(offset, along) / (length * length)
    if not (ON_EDGE_TOLERANCE < travelled < 1.0 - ON_EDGE_TOLERANCE):
        return False
    aside = offset - travelled * along
    distance = math.hypot(float(aside[0]), float(aside[1]), float(aside[2]))
    return distance <= ON_EDGE_TOLERANCE * max(length, 1.0)


def _slots_after_fill(source: MeshData, body: trimesh.Trimesh) -> tuple[int, ...]:
    """Behält alte Slots und leitet neue Deckflächen von ihrem Rand ab."""
    if not source.slots:
        return ()
    old_faces = np.asarray(source.raw.faces, dtype=np.int64)
    new_faces = np.asarray(body.faces, dtype=np.int64)
    if len(new_faces) < len(old_faces) or not np.array_equal(
        new_faces[: len(old_faces)], old_faces
    ):
        return transfer(MeshData.of(body), [source]).slots

    slots = list(source.slots)
    edge_slots: dict[tuple[int, int], list[int]] = {}
    for face, slot in zip(old_faces, slots, strict=True):
        for start, end in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            key = (min(int(start), int(end)), max(int(start), int(end)))
            edge_slots.setdefault(key, []).append(slot)

    fallback_counts = Counter(slots)
    fallback = min(fallback_counts, key=lambda slot: (-fallback_counts[slot], slot))
    for face in new_faces[len(old_faces) :]:
        neighbours: list[int] = []
        edges = ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))
        for start, end in edges:
            key = (min(int(start), int(end)), max(int(start), int(end)))
            neighbours.extend(edge_slots.get(key, ()))
        counts = Counter(neighbours)
        slot = min(counts, key=lambda entry: (-counts[entry], entry)) if counts else fallback
        slots.append(slot)
        for start, end in edges:
            key = (min(int(start), int(end)), max(int(start), int(end)))
            edge_slots.setdefault(key, []).append(slot)
    return tuple(slots)


#: Ab welchem Anteil an der Oberfläche eine geschlossene Öffnung eine Warnung
#: wert ist. **Gefüllt wird sie trotzdem** (Entscheidung Robert, 22.09.2026:
#: „alles bei der Reparatur beheben"), denn der Kunde will drucken, und ein
#: Loch, das die Reparatur stehen lässt, hilft ihm nicht — aber er soll wissen,
#: dass dort eine Fläche entstanden ist, die im Modell nicht war, und den
#: Schritt mit Strg+Z zurücknehmen können.
#:
#: **Als Verbot taugte die Zahl nicht**, und der Körper, der es zeigt, ist der
#: schlichteste: Ein Würfel aus zwölf Dreiecken trägt je Dreieck neun Prozent
#: seiner Oberfläche. Ein einziges fehlendes Dreieck läge damit über jeder
#: Schwelle, die eine fehlende Wand ausschließen soll — und genau das ist ein
#: Loch, wie es kleiner nicht geht.
FILL_LOOP_SHARE: Final = 0.05

#: Wie viele Randkanten der Füller höchstens verkettet. Darüber ist das Netz
#: kein Körper mit Löchern mehr, sondern eine Dreieckssuppe — dann sagt der
#: Bericht das, statt eine halbe Stunde lang Ringe zu bauen. Dieselbe
#: Größenordnung wie :data:`MAX_STITCH_EDGES`, aus demselben Grund.
MAX_FILL_EDGES: Final = 65536

#: Wie oft die Verzweigungsauflösung höchstens durchläuft. Eine Fläche, die an
#: zwei verzweigten Kanten hing, löst beim Fallen eine dritte aus; drei
#: Durchgänge reichten am ganzen Korpus (die Katze braucht zwei), und jeder
#: weitere kostet einen Gang über alle Kanten.
BRANCHING_ROUNDS: Final = 4

#: Wie oft der Ringfüller höchstens durchläuft, aus demselben Grund wie
#: :data:`BRANCHING_ROUNDS`: Ein geschlossener Ring legt den nächsten frei.
FILL_ROUNDS: Final = 4


def boundary_loops(mesh: MeshData) -> list[list[int]]:
    """Die Randkanten zu Ringen verkettet — je Ring seine Eckennummern, in
    Umlaufrichtung.

    Eine Randkante gehört zu genau einem Dreieck; in einem Netz ohne
    Verzweigungen am Rand trifft an jeder Randecke genau eine Kante herein und
    eine heraus, und die Kette schließt sich. Wo das nicht gilt — eine Ecke,
    an der drei Ränder zusammenlaufen —, wird die Kette an dieser Ecke
    abgebrochen und nicht geraten (Regel 21): Der Ring bleibt ungefüllt, und
    der Bericht sagt, wie viele Kanten offen blieben.

    **Verkettet wird ungerichtet.** Der Rand eines Dreiecks läuft ``a → b``,
    und in einem einheitlich gewickelten Netz läuft der Ring ihm entgegen —
    nur ist die Wicklung an dieser Stelle der Kette noch nicht einheitlich
    (``unify_normals`` kommt danach, und es braucht ein geschlossenes Netz, um
    gut zu arbeiten). Gemessen an einer heruntergeladenen Katze: Von 75
    Randkanten ließen sich gerichtet 60 verketten; bei den übrigen 15 zeigten
    zwei Kanten in dieselbe Ecke, weil dort eine Fläche falsch herum liegt.
    Ungerichtet sind es alle — jede Randecke trägt genau zwei Randkanten, und
    der Ring ist eindeutig. Wohin ein Dreieck über dem Ring zeigt, entscheidet
    ``unify_normals`` danach für das ganze Netz.
    """
    body = mesh.raw
    single = _edge_table(mesh).rows(1)
    if not len(single) or len(single) > MAX_FILL_EDGES:
        return []
    directed = np.asarray(body.edges, dtype=np.int64)[single]
    neighbours: dict[int, list[int]] = {}
    for start, end in directed.tolist():
        neighbours.setdefault(int(start), []).append(int(end))
        neighbours.setdefault(int(end), []).append(int(start))
    # Eine Randecke mit mehr als zwei Randkanten ist eine Sanduhr: Dort laufen
    # zwei Ränder zusammen, und welcher zu welchem gehört, ist nicht ablesbar.
    # Sie wird nicht geraten (Regel 21) — ihre Ringe bleiben offen, und der
    # Bericht nennt die Kanten.
    # Die Richtung kommt aus dem Dreieck an der ersten Kante: Läuft sein Rand
    # ``a → b``, läuft der Ring ``b → a``, und ein Dreieck über dem Ring zeigt
    # nach außen wie sein Nachbar. Wo die Wicklung uneinheitlich ist, hat sie
    # ``unify_normals`` danach ohnehin zu richten — aber wo sie stimmt, soll
    # die Füllung sie nicht verderben: Ein falsch herum geschlossener Würfel
    # meldet die Hälfte seines Volumens.
    forward = {(int(start), int(end)) for start, end in directed.tolist()}
    seen: set[int] = set()
    loops: list[list[int]] = []
    for first in neighbours:
        if first in seen or len(neighbours[first]) != 2:
            continue
        loop = [first]
        seen.add(first)
        node = neighbours[first][0]
        while node != first:
            if node in seen or len(neighbours.get(node, ())) != 2:
                loop = []
                break
            seen.add(node)
            loop.append(node)
            options = neighbours[node]
            node = options[0] if options[0] != loop[-2] else options[1]
        if len(loop) >= 3:
            if (loop[0], loop[1]) in forward:
                loop.reverse()
            loops.append(loop)
    return loops


def split_pinched_vertices(mesh: MeshData) -> tuple[MeshData, int]:
    """Ecken auftrennen, in denen zwei Ränder zusammenlaufen.

    Eine Randecke trägt normalerweise genau zwei Randkanten — eine herein,
    eine hinaus —, und der Ring um ein Loch ist damit eindeutig. Wo vier
    zusammenlaufen, berühren sich zwei Löcher in einem Punkt: eine Sanduhr.
    Die Verkettung kann dort nicht entscheiden, welcher Rand zu welchem
    gehört, und lässt beide offen (Regel 21).

    Auflösbar ist es ohne Raten, denn die **Flächen** wissen es: Die Dreiecke
    an der Ecke zerfallen in Fächer, die sich über gemeinsame Kanten
    berühren. Jeder Fächer bekommt seine eigene Kopie der Ecke — am selben
    Ort, also ändert sich nichts an der Form —, und danach hat jede Kopie
    ihre zwei Randkanten. Gemessen an einer heruntergeladenen Katze mit
    452 314 Dreiecken: drei solche Ecken, und mit ihnen schließen sich die
    letzten fünfzehn Randkanten.
    """
    body = mesh.raw
    single = _edge_table(mesh).rows(1)
    if not len(single) or len(single) > MAX_FILL_EDGES:
        return mesh, 0
    border = np.asarray(body.edges, dtype=np.int64)[single]
    corners, counts = np.unique(border.ravel(), return_counts=True)
    pinched = corners[counts > 2]
    if not len(pinched):
        return mesh, 0

    faces = np.asarray(body.faces, dtype=np.int64).copy()
    points = np.asarray(body.vertices, dtype=float)
    # Die Dreiecke je Sanduhr-Ecke einmal gesucht, nicht je Ecke über alle
    # Dreiecke: An einem gescannten Netz mit tausend solcher Ecken waren das
    # tausend Durchgänge über eine Million Dreiecke. Die Menge ändert sich im
    # Lauf nicht — eine Ersetzung tauscht nur die gerade bearbeitete Ecke aus.
    hit_rows, hit_columns = np.nonzero(np.isin(faces, pinched))
    hit_corners = faces[hit_rows, hit_columns]
    order = np.lexsort((hit_rows, hit_corners))
    hit_rows, hit_corners = hit_rows[order], hit_corners[order]
    extra: list[np.ndarray] = []
    split = 0
    for corner in pinched.tolist():
        low, high = np.searchsorted(hit_corners, [corner, corner + 1])
        rows = np.unique(hit_rows[low:high])
        if len(rows) < 2:
            continue
        # Die Fächer: Flächen, die sich an dieser Ecke eine Kante teilen,
        # gehören zusammen. Gesucht wird über die zwei anderen Ecken je Fläche.
        groups: list[set[int]] = []
        for row in rows.tolist():
            others = {int(value) for value in faces[row] if int(value) != corner}
            touching = [index for index, group in enumerate(groups) if group & others]
            if not touching:
                groups.append(set(others) | {-row - 1})
                continue
            first = touching[0]
            groups[first] |= others | {-row - 1}
            for other in reversed(touching[1:]):
                groups[first] |= groups.pop(other)
        if len(groups) < 2:
            continue
        # Der erste Fächer behält die Ecke; jeder weitere bekommt eine Kopie.
        for group in groups[1:]:
            replacement = len(points) + len(extra)
            extra.append(points[corner])
            for marker in group:
                if marker >= 0:
                    continue
                row = -marker - 1
                faces[row] = np.where(faces[row] == corner, replacement, faces[row])
            split += 1

    if not split:
        return mesh, 0
    vertices = np.vstack([points, np.asarray(extra, dtype=float)])
    opened = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    # Die Flächen sind dieselben, nur ihre Ecken sind neu nummeriert — also
    # reist auch ihre Farbe unverändert mit (§20, und der Grund steht bei
    # :func:`_carried_colours`).
    _carried_colours(body, opened, np.arange(len(faces), dtype=np.int64))
    _log.info("split %d pinched vertex fan(s)", split)
    return MeshData.of(opened, slots=mesh.slots), split


def _carried_colours(source: trimesh.Trimesh, target: trimesh.Trimesh, origin: np.ndarray) -> None:
    """Die Flächenfarben des Ausgangs auf das reparierte Netz, Fläche für Fläche.

    **Ein Netz, das seine Farben verliert, verliert seine Filamente** (§20).
    Ein erzeugter Körper kommt farbig aus dem Generator (PLY je Fläche), und
    *Farben zu Filamenten* liest genau diese Werte; ein neu gebautes
    ``trimesh.Trimesh`` hat sie nicht, und aus zwei Filamenten wurde eines.
    ``origin`` sagt je neuer Fläche, von welcher alten sie erbt —
    ``len(source.faces)`` für eine, die es vorher nicht gab.
    """
    visual = getattr(source, "visual", None)
    colours = getattr(visual, "face_colors", None) if visual is not None else None
    if colours is None:
        return
    colours = np.asarray(colours)
    if colours.ndim != 2 or len(colours) != len(source.faces):
        return
    # Eine neue Fläche ohne Vorbild bekommt die häufigste Farbe des Körpers —
    # sie liegt in einer Wand, die es schon gab.
    fallback = colours[0]
    taken = np.where(
        (origin < len(colours))[:, None], colours[np.minimum(origin, len(colours) - 1)], fallback
    )
    # ``visual`` ist entweder ``ColorVisuals`` oder ``TextureVisuals``; nur das
    # erste kennt Flächenfarben, und nur dorthin gehören sie.
    if hasattr(target.visual, "face_colors"):
        target.visual.face_colors = taken  # type: ignore[union-attr]


def _loop_fan(loop: list[int], middle: int) -> np.ndarray:
    """Der Fächer über einen Punkt in der Ringmitte.

    Er erfindet einen Punkt, aber keinen Ort: Die Mitte liegt in der Ebene der
    Ecken, die das Loch umgeben. Dafür sind **alle** seine inneren Kanten neu
    — er kann keine Kante treffen, die schon zwei Flächen trägt, und ist
    deshalb die Antwort für jeden Ring, dessen Ecken anderswo bereits
    verbunden sind (gemessen an einer heruntergeladenen Katze: acht von
    fünfzehn Ringen).
    """
    return np.asarray(
        [[loop[index], loop[(index + 1) % len(loop)], middle] for index in range(len(loop))],
        dtype=np.int64,
    )


def _loop_triangles(points: np.ndarray, loop: list[int]) -> np.ndarray:
    """Dreiecke über einem Randring, in seiner Umlaufrichtung.

    Drei Ecken sind ein Dreieck. Darüber wird in der Ausgleichsebene des Rings
    geohrt (*ear clipping*): Wer eine Ecke findet, deren Dreieck im Inneren
    liegt und keine andere Ecke einschließt, schneidet sie ab. Das Verfahren
    ist für jeden einfachen Ring vollständig; bleibt es stecken — ein Ring,
    der sich in seiner Ebene selbst schneidet, weil das Loch stark gewölbt ist
    —, tritt der Fächer über die Ringmitte an seine Stelle. Er erfindet einen
    Punkt, aber keinen Ort: Die Mitte liegt in der Ebene der Ecken, die das
    Loch umgeben.
    """
    ring = points[loop]
    if len(loop) == 3:
        return np.asarray([loop], dtype=np.int64)

    # **Die Ebene des Rings nach Newell, nicht über eine SVD** (RM-187,
    # 22.09.2026). Die SVD ging durch LAPACK und durfte die Normale mit
    # beiden Vorzeichen liefern — Accelerate auf dem Mac, OpenBLAS sonst —,
    # und das Vorzeichen entschied, in welcher Richtung geohrt wurde: Dasselbe
    # Loch bekam beim Import auf jeder Plattform andere Dreiecke. Newells
    # Flächenvektor, die Summe der Kreuzprodukte aufeinanderfolgender Ecken,
    # braucht nur Grundrechenarten, summiert exakt (``math.fsum``), und seine
    # Richtung folgt dem Umlauf des Rings —
    # derselben Frage, die das Ohren danach stellt.
    centre = np.asarray(units.exact_centre(ring.tolist()), dtype=np.float64)
    local = ring - centre
    following = np.roll(local, -1, axis=0)
    crosses = np.cross(local, following)
    newell = np.array([math.fsum(crosses[:, axis].tolist()) for axis in range(3)])
    size = math.hypot(float(newell[0]), float(newell[1]), float(newell[2]))
    if size <= EPS_GEOM * EPS_GEOM:
        return np.zeros((0, 3), dtype=np.int64)
    normal = newell / size
    basis_u = np.cross(normal, (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0))
    length = math.hypot(float(basis_u[0]), float(basis_u[1]), float(basis_u[2]))
    if length <= EPS_GEOM:
        return np.zeros((0, 3), dtype=np.int64)
    basis_u = basis_u / length
    basis_v = np.cross(normal, basis_u)
    flat = np.column_stack((along(local, basis_u), along(local, basis_v)))
    # Ein Ring, der gegen den Uhrzeigersinn läuft, hat positive Fläche; sonst
    # spiegelt das Ohren die Innen-Außen-Frage.
    ahead = np.roll(flat, -1, axis=0)
    signed = float((flat[:, 0] * ahead[:, 1] - flat[:, 1] * ahead[:, 0]).sum()) / 2.0
    order = list(range(len(loop))) if signed >= 0.0 else list(reversed(range(len(loop))))

    def inside(first: int, second: int, third: int) -> bool:
        """Liegt eine andere Ecke im Dreieck (first, second, third)?"""
        corners = flat[[first, second, third]]
        edges = np.roll(corners, -1, axis=0) - corners
        others = [index for index in order if index not in (first, second, third)]
        if not others:
            return False
        offsets = flat[others][:, None, :] - corners[None, :, :]
        side = edges[None, :, 0] * offsets[:, :, 1] - edges[None, :, 1] * offsets[:, :, 0]
        return bool(np.any(np.all(side >= -EPS_GEOM, axis=1)))

    ears: list[list[int]] = []
    rest = list(order)
    stuck = 0
    while len(rest) > 3 and stuck <= len(rest):
        first, second, third = rest[0], rest[1], rest[2]
        corners = flat[[first, second, third]]
        first_edge = corners[1] - corners[0]
        second_edge = corners[2] - corners[1]
        turn = float(first_edge[0] * second_edge[1] - first_edge[1] * second_edge[0])
        if turn > EPS_GEOM and not inside(first, second, third):
            ears.append([loop[first], loop[second], loop[third]])
            rest.pop(1)
            stuck = 0
        else:
            rest.append(rest.pop(0))
            stuck += 1
    if len(rest) == 3 and stuck <= len(rest):
        ears.append([loop[rest[0]], loop[rest[1]], loop[rest[2]]])
        return np.asarray(ears, dtype=np.int64)

    # Der Fächer über die Mitte, mit einer Ecke mehr: Sie steht am Ende der
    # Punktliste, und der Aufrufer hängt sie an.
    return _loop_fan(loop, len(points))


def fill_boundary_loops(mesh: MeshData) -> tuple[MeshData, int, int]:
    """Schließt jeden Randring, der ein Loch ist — und lässt stehen, was eine
    fehlende Wand ist.

    Der Unterschied zu ``trimesh.repair.fill_holes``, das bis zum 22.09.2026
    an dieser Stelle stand: Jenes schließt Ringe aus drei und vier Kanten und
    lehnt alles darüber ab (sein Fächer gilt nur für konvexe Ränder, und es
    weiß nicht, ob der Rand konvex ist). Ein Modell aus dem Netz hat aber
    Ringe aus fünf, zwanzig, hundert Kanten, und die blieben offen — beim
    Kunden stand danach „Die Reparatur schließt kleine Löcher, kann fehlende
    Wände aber nicht ersetzen" über einem Loch von drei Millimetern.

    Zurück kommt der Körper, wie viele Ringe geschlossen wurden und wie viele
    davon groß genug für eine Warnung waren (:data:`FILL_LOOP_SHARE`). Die
    Materialslots der neuen Dreiecke erben vom Nachbarn am Ring (§20).
    """
    # **Erst die Sanduhren, dann die Ringe.** Zwei Löcher, die sich eine Ecke
    # teilen, geben dort vier Randkanten, und die Kette bricht ab: Am
    # zweifach unterteilten Würfel bleiben zwei fehlende Dreiecke ungefüllt,
    # solange die Ecke nicht aufgetrennt ist.
    mesh, _pinched = split_pinched_vertices(mesh)
    loops = boundary_loops(mesh)
    if not loops:
        return mesh, 0, 0

    body = mesh.raw
    points = np.asarray(body.vertices, dtype=float)
    limit = float(body.area) * FILL_LOOP_SHARE
    # Welcher Slot an welcher Randkante hängt: Die neuen Dreiecke bekommen
    # den ihres Nachbarn, damit eine geschlossene Tasche nicht in einer
    # anderen Farbe dasteht als die Wand um sie herum.
    single = _edge_table(mesh).rows(1)
    slots = np.asarray(mesh.slots, dtype=np.int64) if mesh.slots else None
    slot_at: dict[tuple[int, int], int] = {}
    neighbour_of: dict[tuple[int, int], int] = {}
    directed = np.asarray(body.edges, dtype=np.int64)[single]
    for row, (start, end) in enumerate(directed.tolist()):
        owner = int(single[row]) // 3
        neighbour_of[(int(end), int(start))] = owner
        if slots is not None and len(slots) == len(body.faces):
            slot_at[(int(end), int(start))] = int(slots[owner])

    # **Wie viele Nachbarn jede Kante schon hat.** Eine Füllung, die ein
    # Dreieck auf eine Kante mit zwei Nachbarn legt, macht aus einem Loch eine
    # Verzweigung — gemessen an einer heruntergeladenen Katze: 15 Ringe
    # geschlossen, neun Kanten mit drei Flächen entstanden. Die Ecken eines
    # Randrings sind oft schon anders verbunden, als der Ring nahelegt.
    #
    # Gezählt werden nur Kanten zwischen Ringecken: Nur solche kann eine
    # Füllung treffen — ihre Dreiecke nutzen Ringecken und, beim Fächer, eine
    # neue Mitte. Hier stand ein Wörterbuch über **alle** Kanten, in Python
    # gebaut: am 1,2-M-Netz dreieinhalb Millionen Einträge je Durchgang und
    # drei Sekunden.
    table = _edge_table(mesh)
    ringed = np.unique(np.concatenate([np.asarray(loop, dtype=np.int64) for loop in loops]))
    between = np.isin(table.unique[:, 0], ringed) & np.isin(table.unique[:, 1], ringed)
    taken: dict[tuple[int, int], int] = {
        (int(first), int(second)): int(count)
        for (first, second), count in zip(
            table.unique[between].tolist(), table.counts[between].tolist(), strict=True
        )
    }

    added: list[np.ndarray] = []
    added_slots: list[int] = []
    extra_points: list[np.ndarray] = []
    filled = 0
    too_wide = 0
    blocked = 0
    for loop in loops:
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
        wide_here = spanned > limit
        # Erst die Ohren, und wenn ihre Sehnen an Kanten stoßen, die schon zwei
        # Flächen tragen, der Fächer über die Mitte: Seine inneren Kanten sind
        # immer neu.
        chosen: np.ndarray | None = None
        needs_middle = False
        for attempt in (_loop_triangles(points, loop), _loop_fan(loop, len(points))):
            if not len(attempt):
                continue
            middle_here = bool(int(attempt.max()) >= len(points))
            pieces = (
                np.where(attempt == len(points), len(points) + len(extra_points), attempt)
                if middle_here
                else attempt
            )
            # Keine Fläche auf eine Kante, die schon zwei trägt — und keine zweimal.
            wanted: dict[tuple[int, int], int] = {}
            for piece in pieces.tolist():
                for index in range(3):
                    key = (int(piece[index]), int(piece[(index + 1) % 3]))
                    edge = (min(key), max(key))
                    wanted[edge] = wanted.get(edge, 0) + 1
            if any(taken.get(edge, 0) + count > 2 for edge, count in wanted.items()):
                continue
            for edge, count in wanted.items():
                taken[edge] = taken.get(edge, 0) + count
            chosen = pieces
            needs_middle = middle_here
            break
        if chosen is None:
            blocked += 1
            continue
        pieces = chosen
        if needs_middle:
            extra_points.append(centre)
        added.append(pieces)
        if wide_here:
            too_wide += 1
        for piece in pieces.tolist():
            neighbour = slot_at.get((int(piece[0]), int(piece[1])))
            added_slots.append(neighbour if neighbour is not None else 0)
        filled += 1

    if not added:
        return mesh, 0, 0

    vertices = (
        np.vstack([points, np.asarray(extra_points, dtype=float)]) if extra_points else points
    )
    faces = np.vstack([np.asarray(body.faces, dtype=np.int64), np.vstack(added)])
    patched = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    # Die alten Flächen behalten ihre Farbe, die neuen erben die ihres Nachbarn
    # am Ring — wie die Materialslots darüber (§20).
    origin = np.concatenate(
        [
            np.arange(len(body.faces), dtype=np.int64),
            np.fromiter(
                (
                    neighbour_of.get((int(piece[0]), int(piece[1])), len(body.faces))
                    for group in added
                    for piece in group.tolist()
                ),
                dtype=np.int64,
                count=sum(len(group) for group in added),
            ),
        ]
    )
    _carried_colours(body, patched, origin)
    slot_values: tuple[int, ...] = ()
    if slots is not None and len(slots) == len(body.faces):
        slot_values = tuple(int(value) for value in (*slots.tolist(), *added_slots))
    _log.info(
        "filled %d boundary loop(s), %d of them wide, %d would branch", filled, too_wide, blocked
    )
    return MeshData.of(patched, slots=slot_values), filled, too_wide


def resolve_branching_edges(mesh: MeshData) -> tuple[MeshData, int]:
    """Kanten, an denen mehr als zwei Flächen zusammenlaufen, wieder zu Kanten
    mit zwei Flächen machen.

    Das zweite Maß von „nicht geschlossen" (:func:`branching_edge_count`), und
    das, für das es bis zum 22.09.2026 keine Handlung gab: Der Bericht sagte
    „An einer Kante treffen mehr als zwei Flächen zusammen — das ist kein
    Loch, sondern eine Verzweigung", und danach stand der Kunde allein da.

    **Was dort wirklich liegt, ist übereinandergeklapptes Material.** Gemessen
    an Roberts Waschschüssel (215 073 Dreiecke, eine verzweigte Kante) und an
    einer heruntergeladenen Katze (452 314 Dreiecke, 27 verzweigte Kanten):
    An jeder dieser Kanten stehen zwei Flächen mit **null Grad** zueinander —
    zwei Dreiecke, die aufeinanderliegen, ohne deckungsgleich zu sein (sonst
    hätte :func:`remove_doubled_faces` sie gefangen) — und eine dritte, die die
    echte Wand ist. Die Flächen sind winzig: 0,0003 mm² neben 0,27 mm².

    Entfernt wird deshalb je Kante die **kleinste** anliegende Fläche, und nur
    so viele, bis die Kante zwei Nachbarn hat. Das Ergebnis wird gemessen, nicht
    geglaubt: Wird die Verzweigungszahl nicht kleiner oder reißt das Netz weiter
    auf, als die entfernten Dreiecke erklären, bleibt der Schritt aus. Was er
    öffnet, schließt der Ringfüller danach — deshalb steht er vor ihm.

    **Und er läuft mehrmals**: Eine Fläche, die zwei verzweigte Kanten trug,
    löst beim Fallen eine dritte aus. Gemessen an einer heruntergeladenen Katze
    mit 452 314 Dreiecken: 27 Verzweigungen im ersten Durchgang, 11 im zweiten,
    danach keine mehr.
    """
    total = 0
    for _round in range(BRANCHING_ROUNDS):
        mesh, resolved = _resolve_branching_once(mesh)
        if not resolved:
            break
        total += resolved
    return mesh, total


def _resolve_branching_once(mesh: MeshData) -> tuple[MeshData, int]:
    """Ein Durchgang von :func:`resolve_branching_edges`."""
    body = mesh.raw
    table = _edge_table(mesh)
    branching = int(np.count_nonzero(table.counts > 2))
    if not branching:
        return mesh, 0

    # Je verzweigter Kante ihre Dreiecke — als Feld und nicht als Liste je
    # Kante (``group_rows`` über alle Kanten kostete am 1,2-M-Netz Sekunden).
    # Ein Dreieck zählt je Kante einmal, auch wenn es entartet zwei seiner
    # Kanten auf dieselbe legt.
    rows = np.flatnonzero(table.counts[table.inverse] > 2)
    edges = table.inverse[rows]
    faces = rows // 3
    pairs = np.unique(edges * len(body.faces) + faces)
    edges, faces = pairs // len(body.faces), pairs % len(body.faces)
    # Zwei Nachbarn darf die Kante behalten; alles darüber geht, kleinste
    # Fläche zuerst — bei gleicher Fläche die kleinere Nummer, wie zuvor.
    _normals, areas = stable_normals(body)
    order = np.lexsort((faces, areas[faces], edges))
    edges, faces = edges[order], faces[order]
    first = np.searchsorted(edges, edges, side="left")
    rank = np.arange(len(edges)) - first
    size = np.searchsorted(edges, edges, side="right") - first
    doomed = np.unique(faces[rank < size - 2])
    if not len(doomed):
        return mesh, 0

    keep = np.ones(len(body.faces), dtype=bool)
    keep[doomed] = False
    trimmed = body.copy()
    trimmed.update_faces(keep)
    trimmed.remove_unreferenced_vertices()
    slots: tuple[int, ...] = ()
    if mesh.slots and len(mesh.slots) == len(body.faces):
        slots = tuple(int(value) for value in np.asarray(mesh.slots, dtype=np.int64)[keep])
    candidate = MeshData.of(trimmed, slots=slots)
    # **Die Probe:** Die Verzweigung muss weg sein, und das Netz darf dabei
    # nicht mehr aufreißen, als der Ringfüller danach wieder schließt. Ein
    # Dreieck weniger heißt bis zu drei offene Kanten mehr — mehr als das ist
    # kein Auflösen, sondern ein Loch.
    opened = open_edge_count(candidate) - open_edge_count(mesh)
    if branching_edge_count(candidate) >= branching or opened > 3 * len(doomed):
        return mesh, 0
    _log.info("resolved %d branching edge(s) by dropping %d face(s)", branching, len(doomed))
    return candidate, branching


def _filled_with_count(mesh: MeshData) -> tuple[MeshData, bool, int]:
    """Wie :func:`fill_holes` ohne Vernähen, aber mit der Zahl der großen
    Öffnungen für den Bericht."""
    before = open_edge_count(mesh)
    if not before:
        return mesh, False, 0
    working = mesh
    wide = 0
    for _round in range(FILL_ROUNDS):
        working, closed_loops, wide_here = fill_boundary_loops(working)
        wide += wide_here
        if not closed_loops:
            break
    return working, open_edge_count(working) < before, wide


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
    working = mesh
    body = working.raw.copy()
    if body.is_watertight:
        return mesh, False
    if stitch:
        working, _seams = stitch_t_junctions(working)
        body = working.raw.copy()
        if body.is_watertight:
            return working, True
    # **Der eigene Ringfüller, nicht der von trimesh.** Jener schließt Ringe
    # aus drei und vier Kanten, lehnt alles darüber ab (sein Fächer gilt nur
    # für konvexe Ränder, und er weiß nicht, ob der Rand konvex ist) — und er
    # prüft nicht, ob die Ecken des Rings schon anders verbunden sind: An
    # einer heruntergeladenen Katze machte er aus zwei Löchern zwei
    # Verzweigungen. :func:`fill_boundary_loops` verkettet die Ränder selbst,
    # ohrt sie in ihrer Ausgleichsebene und legt keine Fläche auf eine Kante,
    # die schon zwei trägt.
    filled, worked, _wide = _filled_with_count(working)
    return filled, worked


def remove_hollow_shells(mesh: MeshData) -> tuple[MeshData, int]:
    """Wirft Komponenten ohne **Dicke** — Flächenpaare, die nichts umschließen.

    Nicht dasselbe wie :func:`remove_small_components`, und der Unterschied
    ist die Messgröße: Dort entscheidet die **Fläche** gegen die größte
    Komponente, hier das **Volumen** gegen null. Eine Haut aus vier Dreiecken
    kann fast einen Quadratmillimeter Fläche haben und umschließt trotzdem
    nichts; ein legitimes kleines Bauteil hat immer ein Volumen.

    **Der Fall, für den es das gibt:** Ein Verrundungswerkzeug liegt mit
    beiden Flanken genau in den Körperflächen — das ist keine Zugabe, die man
    weglassen könnte, sondern die Form der Sache. Läuft es dabei über eine
    schon verrundete, also facettierte Fläche, bleiben an einzelnen Ecken
    Flächenpaare ohne Dicke stehen. Gemessen an einer zweimal verrundeten
    Platte: zwei Häute zu vier Dreiecken, 0,9485 mm² Fläche, Volumen null, an
    zwei diagonal gegenüberliegenden Ecken. Der Körper war danach wasserdicht
    und trug sein richtiges Volumen — ``body_count`` sagte trotzdem drei, und
    genau das meldet der Prüfbericht dem Kunden als zerfallenen Körper.

    Gerechnet wird das Volumen je Komponente über den Divergenzsatz und nicht
    über ein Teilnetz: Das kostet einen Durchgang statt einer Kopie je Teil,
    und die Materialslots (§20) bleiben dabei an ihren Dreiecken.
    """
    pieces = face_components(mesh.raw)
    if len(pieces) <= 1:
        return mesh, 0
    corners = mesh.raw.vertices[mesh.raw.faces]
    # Elementweise statt ``np.einsum`` (FMA auf ARM, RM-187): Am Betrag
    # entscheidet sich, ob eine Schale bleibt.
    crossed = np.cross(corners[:, 0], corners[:, 1])
    signed = (
        crossed[:, 0] * corners[:, 2, 0]
        + crossed[:, 1] * corners[:, 2, 1]
        + crossed[:, 2] * corners[:, 2, 2]
    ) / 6.0
    keep = [piece for piece in pieces if abs(float(signed[piece].sum())) > EPS_GEOM]
    if len(keep) == len(pieces) or not keep:
        return mesh, 0

    body = mesh.raw.copy()
    mask = np.zeros(len(body.faces), dtype=bool)
    for piece in keep:
        mask[piece] = True
    body.update_faces(mask)
    body.remove_unreferenced_vertices()
    slots = (
        tuple(slot for slot, kept in zip(mesh.slots, mask, strict=True) if kept)
        if mesh.slots
        else ()
    )
    return MeshData.of(body, slots=slots), len(pieces) - len(keep)


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
    slots = (
        tuple(slot for slot, kept in zip(mesh.slots, mask, strict=True) if kept)
        if mesh.slots
        else ()
    )
    return MeshData.of(body, slots=slots), len(pieces) - len(keep)


#: Wie viele Dreieckspaare die Durchdringungssuche höchstens prüft.
#:
#: Die Karte hat ein Interaktionsbudget (§18.4, §31), und die Suche ist im
#: schlechtesten Fall quadratisch — ein Netz aus lauter deckungsgleichen
#: Flächen erzeugt beliebig viele Paare. Zwei Millionen Paare rechnet numpy in
#: Bruchteilen einer Sekunde; darüber bricht die Suche ab und meldet, was sie
#: bis dahin gefunden hat. Eine unvollständige Markierung ist dabei ehrlich:
#: Was dasteht, ist wirklich eine Durchdringung.
MAX_INTERSECTION_PAIRS: Final = 2_000_000


def self_intersecting_faces(
    mesh: MeshData, cancelled: CancelToken | None = None
) -> tuple[int, ...]:
    """Welche Dreiecke durch andere Dreiecke desselben Netzes laufen (§18.4).

    **Eine Durchdringung ist räumlich und nicht topologisch** — und genau
    deshalb fand die Netzfehlerkarte sie nicht (RM-143). Offene und verzweigte
    Kanten stehen in der Kantentabelle; zwei Wände, die einander schneiden,
    haben dagegen lauter saubere Kanten mit je zwei Flächen, und die Tabelle
    sagt dazu nichts. `broken_selfint.stl` ist der Fall: zwei Quader, die
    durcheinanderlaufen, jede Kante in Ordnung.

    Gerechnet wird in ``geom.intersections``, derselben Rechnung, mit der der
    Bereichstest eines Bausteins fragt (RM-206): Sweep-and-Prune entlang der
    günstigsten Achse, dann je Paar als Feld. **Zwei Fälle kamen damit dazu,
    die der Möller-Trumbore-Test hier nicht sah:** zwei Dreiecke, die in
    derselben Ebene übereinanderliegen — keine Kante durchstößt dort eine
    Fläche —, und ein Paar, das sich eine Ecke teilt und trotzdem durch das
    andere läuft. Nachbarn zählen weiter nicht: Was zwei Dreiecke an Kante
    oder Ecke teilen, ist Berührung. Verglichen wird über die **Eckpunkte**
    innerhalb ``EPS_GEOM``, nicht über die Indizes — ein eingelesenes STL
    trägt dieselbe Ecke oft mehrfach.

    Die Suche deckelt sich an :data:`MAX_INTERSECTION_PAIRS` Kandidaten des
    Sweeps; was sie bis dahin fand, schneidet wirklich.
    """
    from app.core.geom.intersections import crossing_faces

    body = mesh.raw
    found, complete = crossing_faces(
        body.vertices, body.faces, cancelled, max_pairs=MAX_INTERSECTION_PAIRS
    )
    if not complete:
        _log.info("self-intersection search stopped after %d pairs", MAX_INTERSECTION_PAIRS)
    return found


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
    # **Die Farben reisen mit, wie die Slots.** Der Kern baut das Netz neu, und
    # ein neu gebautes ``trimesh.Trimesh`` hat keine Flächenfarben — ein
    # erzeugter Körper kommt aber farbig aus dem Generator, und *Farben zu
    # Filamenten* liest genau diese Werte (§20). Bis zum 22.09.2026 fiel das
    # nicht auf, weil dieser Schritt an einem offenen Netz gar nicht lief;
    # seit die Kette auch fehlende Wände schließt, läuft er — und aus zwei
    # Filamenten wurde eines. Zugeordnet wird über die nächste alte Fläche,
    # genau wie ``transfer`` es für die Slots tut.
    resolved = transfer(MeshData.of(rebuilt), [mesh])
    _carried_colours(mesh.raw, resolved.raw, _nearest_old_face(mesh.raw, resolved.raw))
    return resolved, True


def _nearest_old_face(source: trimesh.Trimesh, target: trimesh.Trimesh) -> np.ndarray:
    """Je neuer Fläche die alte, die ihrem Schwerpunkt am nächsten liegt."""
    from app.core.geom.mesh import on_surface

    _spot, _distance, face = on_surface(source, np.asarray(target.triangles_center, dtype=float))
    return np.asarray(face, dtype=np.int64)


def _tears_it_further(before: MeshData, after: MeshData) -> bool:
    """Ob ein Schritt mehr offene Ränder hinterlässt, als er vorgefunden hat.

    **Gefragt wird „wird es schlechter", nicht „war es heil".** Bis zum
    16.09.2026 stand hier ``before.is_watertight and not after.is_watertight``,
    und damit griff der Schutz ausgerechnet dort nicht, wo etwas zu schützen
    war: An einem Netz, das schon offen ist, durfte jeder Schritt es weiter
    aufreißen.

    Gemessen an einer heruntergeladenen Waschschüssel: null offene Ränder,
    eine verzweigte Kante — ``is_watertight`` also falsch, der Schutz aus. Das
    Entfernen **eines** entarteten Dreiecks riss zwei Ränder auf, die
    anschließend niemand mehr schloss, und der Kunde bekam ein Modell zurück,
    das kaputter war als vorher.

    **Beide Maße zählen, und zwar zusammen.** Ein Schritt kann ein Netz
    verschlechtern, ohne einen einzigen Rand zu erzeugen: Zwei geschlossene
    Schalen, die sich berühren, werden beim Verschweißen zu einer verzweigten —
    null Ränder vorher, null nachher, und trotzdem kein Volumenkörper mehr.
    Genau diesen Fall hält ``test_repair_preserves_closed_topology`` fest.

    Gewogen wird die **Summe** und nicht jedes Maß für sich. Ein Schritt, der
    10 116 offene Ränder eines rohen STL schließt und dabei zwei Verzweigungen
    hinterlässt, ist eine Verbesserung; die strengere Lesart verbot ihn und
    ließ ``generated_figure.stl`` unverschweißt liegen — ohne Volumen, und die
    Normalenprüfung danach rechnete durch null.
    """
    return open_edge_count(after) + branching_edge_count(after) > open_edge_count(
        before
    ) + branching_edge_count(before)


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
        candidate, removed = merge_vertices(result.mesh)
        # Dieselbe Zusicherung wie beim Import: nahe Punkte können zu zwei
        # getrennten Schalen gehören. Das Zusammenlegen darf deren Kanten
        # nicht zu nichtmannigfaltigen Verbindungen machen.
        if removed and _tears_it_further(result.mesh, candidate):
            result.findings.append(
                Finding(
                    code="repair.weld_skipped",
                    severity="info",
                    message=_(
                        "Doppelte Punkte blieben stehen — sie zu verschweißen hätte das "
                        "Netz weiter aufgerissen."
                    ),
                    values={
                        "tolerance": format_length(weld_tolerance(result.mesh.bounds.diagonal))
                    },
                )
            )
        elif removed:
            result.mesh = candidate
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
        # **Vor den entarteten Dreiecken, und das ist die Reihenfolge, auf die
        # es ankommt.** ``remove_degenerate_faces`` ruft ``unique_faces`` und
        # behält damit von zwei deckungsgleichen Dreiecken eines — die Tasche
        # ohne Volumen wird zur offenen Stelle. Fällt das Paar vorher, ist für
        # den Schritt danach nichts mehr zu tun.
        candidate, doubled = remove_doubled_faces(result.mesh)
        if doubled and not _tears_it_further(result.mesh, candidate):
            result.mesh = candidate
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.doubled_removed",
                    severity="info",
                    message=_("Deckungsgleiche Dreiecke wurden paarweise entfernt."),
                    values={"removed": doubled},
                )
            )

        candidate, removed = remove_degenerate_faces(result.mesh)
        # Auch ein flaches Dreieck kann zwei Nachbarflächen topologisch
        # verbinden. Ein geschlossener Eingang bleibt einschließlich seiner
        # Materialzuweisungen erhalten, wenn das Entfernen ihn öffnen würde.
        if removed and _tears_it_further(result.mesh, candidate):
            result.findings.append(
                Finding(
                    code="repair.degenerate_kept",
                    severity="info",
                    message=_(
                        "Entartete Dreiecke blieben stehen — sie zu entfernen hätte das "
                        "Netz weiter aufgerissen."
                    ),
                    values={"kept": removed},
                )
            )
        elif removed:
            result.mesh = candidate
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
        # **Zuerst die Verzweigungen, dann die Löcher.** Eine Kante mit drei
        # Nachbarn ist kein Loch, und der Füller kann sie nicht sehen; was das
        # Auflösen öffnet, schließt er dagegen gleich mit.
        result.mesh, unbranched = resolve_branching_edges(result.mesh)
        if unbranched:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.branching_resolved",
                    severity="info",
                    message=_(
                        "An {edges} Kanten lagen Flächen übereinander — die überzähligen "
                        "wurden entfernt.",
                        edges=unbranched,
                    )
                    if unbranched > 1
                    else _(
                        "An einer Kante lagen Flächen übereinander — die überzählige wurde "
                        "entfernt."
                    ),
                    values={"edges": unbranched},
                )
            )

        # Getrennt gemeldet, weil es ein anderer Defekt mit anderer Antwort
        # ist: eine Naht ist eine Fläche, der ein Punkt fehlte, ein Loch eine
        # Fläche, die fehlte. Wer den Bericht liest, erkennt, ob sein Modell
        # eine Lücke hatte oder nur einen Buchhaltungsfehler.
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

        # **Gezählt wird erst nach dem Vernähen.** Vorher gezählt, schrieb die
        # Meldung die vernähten Kanten dem Löcherschließen zu — „von 400
        # offenen Kanten geschlossen" über einem Modell, dessen Löcher gar
        # nicht so groß waren. Die Naht hat ihre eigene Zeile darüber.
        open_before = open_edge_count(result.mesh)
        # `stitch=False`: das Vernähen ist gerade gelaufen — es erneut zu
        # zahlen war der gemessene Faktor 2,1 auf dem Normalfall „Reparieren
        # an einem heruntergeladenen Modell".
        result.mesh, closed, wide_holes = _filled_with_count(result.mesh)
        open_after = open_edge_count(result.mesh)
        if wide_holes:
            # **Eine große Öffnung wird geschlossen und gesagt.** Dort ist eine
            # Fläche entstanden, die im Modell nicht war — beim halben Würfel
            # ist das der ganze Deckel. Wer das nicht wollte, nimmt den Schritt
            # mit Strg+Z zurück; wer es wollte, druckt.
            result.findings.append(
                Finding(
                    code="repair.wide_hole_filled",
                    severity="warning",
                    message=_(
                        "{walls} große Öffnungen wurden geschlossen — prüfen Sie, ob dort "
                        "wirklich eine Fläche hingehört.",
                        walls=wide_holes,
                    )
                    if wide_holes > 1
                    else _(
                        "Eine große Öffnung wurde geschlossen — prüfen Sie, ob dort wirklich "
                        "eine Fläche hingehört."
                    ),
                    values={"walls": wide_holes},
                )
            )
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
        # **Zwei Gründe, und sie verlangen verschiedene Sätze.** „Fehlende
        # Wände" stimmt für offene Ränder; ein Netz kann aber null davon haben
        # und trotzdem kein Volumen einschließen, weil an einer Kante drei
        # Flächen zusammenlaufen. Gemessen am 16.09.2026 an einer
        # heruntergeladenen Waschschüssel: null Ränder, eine verzweigte Kante
        # — und der Bericht sprach von fehlenden Wänden. Wer danach nach einem
        # Loch sucht, findet keines und hält die Anwendung für kaputt.
        open_edges = open_edge_count(result.mesh)
        branching = branching_edge_count(result.mesh)
        result.findings.append(
            Finding(
                code="repair.still_branching" if branching else "repair.still_open",
                severity="warning",
                # Der frühere Folgesatz schickte den Nutzer im Kreis:
                # „Kanten verfeinern schließt es" — diese Operation weist ein
                # offenes Netz zurück und empfiehlt wieder Reparieren. Die
                # ehrliche Grenze erklärt, warum der Rest bleibt; die
                # Oberfläche führt von dort zu den betroffenen Stellen (§2.7).
                message=_(
                    "An {edges} Kanten liegen weiterhin Flächen übereinander, und an "
                    "{open_edges} Stellen ist das Netz offen.",
                    edges=branching,
                    open_edges=open_edges,
                )
                if branching and open_edges
                else _(
                    "An einer Kante treffen mehr als zwei Flächen zusammen — das ist kein "
                    "Loch, sondern eine Verzweigung."
                )
                if branching == 1
                else _(
                    "An {edges} Kanten treffen mehr als zwei Flächen zusammen — das sind "
                    "keine Löcher, sondern Verzweigungen.",
                    edges=branching,
                )
                if branching
                else _(
                    "Die Reparatur schließt kleine Löcher, kann fehlende Wände aber nicht ersetzen."
                ),
                values={"open_edges": open_edges, "branching_edges": branching}
                if branching
                else {"open_edges": open_edges},
            )
        )
    return result


@dataclass(frozen=True)
class _EdgeTable:
    """Die Kanten eines Netzes, einmal gezählt: ``inverse`` ordnet jede Zeile
    von ``edges_sorted`` (drei je Dreieck, in Dreiecksreihenfolge) ihrer
    Kante zu, ``counts`` sagt je Kante, wie viele Dreiecke sie tragen."""

    unique: np.ndarray
    inverse: np.ndarray
    counts: np.ndarray

    def rows(self, count: int) -> np.ndarray:
        """Die Zeilen der Kanten mit genau ``count`` Dreiecken, aufsteigend."""
        return np.flatnonzero(self.counts[self.inverse] == count)


def _edge_table(mesh: MeshData) -> _EdgeTable:
    """Die Kantenzählung eines Netzes — einmal je Netz, im Cache des Netzes.

    **Eine Zählung statt einer je Frage** (Review 22.09.2026). Offene Ränder,
    Verzweigungen, Randringe und Sanduhren fragten je ``group_rows`` über alle
    Kanten, die Reparatur beim Import eines offenen Netzes achtzehnmal: An
    der Piratenschiff-Baugruppe (1,2 Millionen Dreiecke) kosteten diese
    Zählungen allein elf der fünfundzwanzig Sekunden. Gezählt wird über eine
    Kantennummer (:func:`app.core.geom.mesh.unique_edges`); der Cache verfällt
    mit der Geometrie, und jede Reparaturstufe baut ein neues Netz.
    """
    body = mesh.raw
    cache = getattr(body, "_cache", None)
    if cache is not None:
        cache.verify()
        if "solidon_edge_table" in cache:
            return cast(_EdgeTable, cache["solidon_edge_table"])
    unique, inverse, counts = unique_edges(
        np.asarray(body.edges_sorted, dtype=np.int64), return_inverse=True, return_counts=True
    )
    table = _EdgeTable(unique=unique, inverse=inverse, counts=counts)
    if cache is not None:
        cache["solidon_edge_table"] = table
    return table


def open_edge_count(mesh: MeshData) -> int:
    """Kanten, die zu genau einem Dreieck gehören — das Maß von „offen"."""
    return int(np.count_nonzero(_edge_table(mesh).counts == 1))


def branching_edge_count(mesh: MeshData) -> int:
    """Kanten, an denen **mehr als zwei** Dreiecke hängen.

    Das zweite Maß von „nicht geschlossen", und das seltener genannte: Ein
    Netz kann null offene Ränder haben und trotzdem kein Volumen einschließen,
    weil an einer Kante drei Flächen zusammenlaufen. ``is_watertight`` meldet
    dann „offen", die Randzählung sagt null, und ohne diese Auskunft steht der
    Kunde vor einem Widerspruch.

    Gemessen am 16.09.2026 an einer heruntergeladenen Waschschüssel mit
    215 074 Dreiecken: **null** offene Ränder, **eine** verzweigte Kante — und
    der Prüfbericht sprach von fehlenden Wänden.
    """
    return int(np.count_nonzero(_edge_table(mesh).counts > 2))
