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
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, cast

import numpy as np

from app.core import units
from app.core.deferred import trimesh
from app.core.errors import (
    GIVE_THICKNESS,
    LEAVE_OPEN,
    PROGRAMMING_ERRORS,
    RESOLVE_INTERSECTIONS,
    SHOW_LOCATION,
    SHOW_LOCATIONS,
    SPLIT_BODIES,
    OperationCancelled,
)
from app.core.geom.attributes import transfer
from app.core.geom.intersections import Crossings
from app.core.geom.mesh import (
    EdgeTable,
    MeshData,
    carry_appended_edges,
    edge_table,
    face_components,
    signed_volume,
    stable_areas,
    triple_products,
    without_faces,
)
from app.core.geom.transform import along
from app.core.log import get_logger
from app.core.types import CancelToken, Finding, ProgressFn, SolverInfo
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
    solver: SolverInfo | None = None


def used_vertex_count(body: trimesh.Trimesh) -> int:
    """Wie viele Ecken ein Dreieck benutzt — unbenutzte zählen nicht."""
    used = np.zeros(len(body.vertices), dtype=bool)
    used[np.asarray(body.faces, dtype=np.int64).ravel()] = True
    return int(np.count_nonzero(used))


def merge_vertices(mesh: MeshData, tolerance: float | None = None) -> tuple[MeshData, int]:
    """Verschweißt zusammenfallende Punkte. Liefert den Körper und wie viele
    Eckpunkte **zusammengelegt** wurden.

    Unbenutzte Ecken zählen nicht mit: trimesh räumt sie beim Verschweißen
    weg, und eine einzige davon meldete „Doppelte Punkte wurden verschweißt"
    samt voller Neuerkennung über einem Netz, an dem sich nichts geändert
    hatte (Durchsicht 24.09.2026).
    """
    body = mesh.raw.copy()
    before = used_vertex_count(body)
    limit = tolerance if tolerance is not None else weld_tolerance(mesh.bounds.diagonal)
    body.merge_vertices(digits_vertex=weld_digits(limit))
    return mesh.replacing(body), before - used_vertex_count(body)


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
    # Nur gelesen; die Kopie mit abgeleiteter Kantenzählung baut ``without_faces``.
    body = mesh.raw
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
    return MeshData.of(without_faces(body, keep), slots=kept_slots), dropped


def wind_consistently(body: trimesh.Trimesh) -> None:
    """Dreht Dreiecke, bis jede Nachbarkante in beiden Dreiecken gegenläufig ist.

    Dieselbe Frage wie ``trimesh.repair.fix_winding``, **nur nicht je Paar in
    Python** (Befund B12 der Durchsicht 24.09.2026): trimesh prüft jede
    Baumkante mit eigenen NumPy-Aufrufen, und an der Gähnenden Katze mit
    452 316 Dreiecken kostete der Import allein damit 13 bis 23 s. Hier sagt
    die Kantentabelle für alle Paare auf einmal, ob sie gleich herum laufen,
    ``scipy.sparse.csgraph`` legt den Breitenbaum, und jedes Dreieck folgt
    seinem Vorgänger darin.

    **Je Teil wird die kleinere Hälfte gedreht**, nicht alles nach einem
    Startdreieck. trimesh behielt die Richtung des ersten Dreiecks, das es
    fand; lag gerade das verkehrt, drehte es den Rest des Teils um, und ein
    offenes Netz kam innen-außen an. Die Mehrheit ist die bessere Auskunft
    darüber, wo außen gemeint war; bei Gleichstand bleibt das erste Dreieck
    der Nachbarschaftsliste, wie es ist. Ein geschlossenes Teil richtet
    danach ohnehin :func:`turn_shells_outward` nach außen.

    Auf einem widersprüchlichen Kreis — eine gekreuzte Naht — gibt es keine
    einheitliche Lösung; dort entscheidet der Baum, und der Bericht nennt die
    übrigen Kanten (:func:`crossed_edge_faces`). Nur ganze Zahlen, keine
    Plattformfrage (RM-187). Das Netz wird dabei verändert.
    """
    if not len(body.faces):
        return
    # Die Kantenzählung legt den Umlaufsinn in trimeshs Cache — sonst gruppierte
    # trimesh für diese eine Frage alle Kanten ein zweites Mal (RM-224).
    edge_table(body)
    if body.is_winding_consistent:
        return
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import breadth_first_order, connected_components

    faces = np.asarray(body.faces, dtype=np.int64)
    pairs = np.asarray(body.face_adjacency, dtype=np.int64)
    shared = np.asarray(body.face_adjacency_edges, dtype=np.int64)
    if not len(pairs):
        return
    count = len(faces)
    span = count + 1

    def forward(which: np.ndarray) -> np.ndarray:
        """Läuft die gemeinsame Kante in diesen Dreiecken von ihrer ersten Ecke zur zweiten?"""
        rows = faces[which]
        at = np.argmax(rows == shared[:, :1], axis=1)
        return np.asarray(rows[np.arange(len(rows)), (at + 1) % 3] == shared[:, 1])

    alike = forward(pairs[:, 0]) == forward(pairs[:, 1])
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(span, span))
    parts, found = connected_components(graph, directed=False)
    # ``csgraph`` antwortet in ``int32``; die Kantennummer unten braucht 64 Bit.
    labels = np.asarray(found, dtype=np.int64)
    listed = pairs.ravel()
    _seen, first = np.unique(labels[listed], return_index=True)
    starts = listed[first]
    # Ein gemeinsamer Wurzelknoten über allen Starts: ein Baum, ein Lauf.
    rows = np.concatenate([pairs[:, 0], np.full(len(starts), count)])
    columns = np.concatenate([pairs[:, 1], starts])
    tree = coo_matrix((np.ones(len(rows)), (rows, columns)), shape=(span, span))
    order, parent = breadth_first_order(
        tree.tocsr(), count, directed=False, return_predecessors=True
    )
    nodes = np.asarray(order[1:], dtype=np.int64)
    above = np.asarray(parent, dtype=np.int64)[nodes]
    # Je Baumkante, ob ihre zwei Dreiecke gleich herum laufen — über eine
    # sortierte Kantennummer statt eines Wörterbuchs mit einer Zeile je Paar.
    keys = np.minimum(pairs[:, 0], pairs[:, 1]) * span + np.maximum(pairs[:, 0], pairs[:, 1])
    sort = np.argsort(keys, kind="stable")
    inner = above != count
    wanted = np.minimum(above, nodes) * span + np.maximum(above, nodes)
    same = np.zeros(len(nodes), dtype=bool)
    same[inner] = alike[sort][np.searchsorted(keys[sort], wanted[inner])]
    # Gleich herum gelaufen heißt: umdrehen — relativ zum Vorgänger, der im
    # Breitenbaum immer vorher dran ist.
    flipped = [False] * span
    for node, up, differs in zip(nodes.tolist(), above.tolist(), same.tolist(), strict=True):
        flipped[node] = flipped[up] != differs
    turn = np.asarray(flipped[:count], dtype=bool)
    reached = np.zeros(count, dtype=bool)
    reached[nodes] = True
    own = labels[:count]
    mostly = np.bincount(own[turn], minlength=parts) * 2 > np.bincount(
        own[reached], minlength=parts
    )
    turn = turn != (mostly[own] & reached)
    if turn.any():
        changed = faces.copy()
        changed[turn] = changed[turn][:, ::-1]
        body.faces = changed


def unify_normals(mesh: MeshData) -> tuple[MeshData, bool]:
    """Macht den Umlaufsinn einheitlich und stülpt den Körper nötigenfalls
    nach außen.

    Die Kopie nimmt den Cache mit (RM-224): Kantenzählung, Umlaufsinn und
    Teilezerlegung des Netzes stehen dort schon, und ohne ihn rechnete dieser
    Schritt am Piratenschiff beides ein zweites Mal — 0,8 s. Dreht er
    Dreiecke, verfällt der Cache der Kopie mit ihrer Geometrie.
    """
    body = mesh.raw.copy(include_cache=True)
    before = np.asarray(body.faces).copy()
    wind_consistently(body)
    if body.is_watertight:
        turn_shells_outward(body)
    # Eine umgedrehte Fläche kann denselben Volumenbeitrag haben. Ob der
    # Umlauf korrigiert wurde, sagt ausschließlich die Reihenfolge der Ecken.
    return mesh.replacing(body), not np.array_equal(body.faces, before)


def _shell_volumes(body: trimesh.Trimesh, labels: np.ndarray, count: int) -> np.ndarray:
    """Das eingeschlossene Volumen je Schale, nahe an der Schale gerechnet.

    Jede Schale bezieht sich auf ihre eigene erste Ecke, nicht auf den
    Ursprung (Befund B16, 24.09.2026): Weit draußen bestand das Volumen eines
    kleinen Teils sonst aus Rundung, und sein Vorzeichen entschied, ob es
    umgestülpt wird. Das Spatprodukt rechnet :func:`mesh.triple_products`
    elementweise (RM-187).
    """
    triangles = np.asarray(body.triangles, dtype=np.float64)
    if not len(triangles):
        return np.zeros(count)
    _shells, first = np.unique(labels, return_index=True)
    anchors = np.zeros((count, 3))
    anchors[labels[first]] = triangles[first, 0]
    products = triple_products(triangles - anchors[labels][:, None, :])
    return np.bincount(labels, weights=products, minlength=count) / 6.0


#: Wie viele Hüllquadervergleiche :meth:`_Shells.containers_of` auf einmal als
#: Feld hält — ein Megabyte je Vergleich, gleich wie viele Teile der Körper hat.
_SHELL_BLOCK: Final = 1 << 20


class _Shells:
    """Die Schalen eines Netzes: Dreiecke, Volumen, Hüllquader — einmal gelesen.

    Eine umhüllende Schale wird beim ersten Strahl gegen sie ausgeschnitten und
    behält danach Dreiecke und Hüllquader (Befund B19 der Durchsicht
    24.09.2026): Vorher kopierte jede Innenschale die ganze Außenschale neu,
    und 300 Hohlräume in 331 280 Dreiecken kosteten 7,2 s. Ob eine Schale in
    einer anderen liegt, fragt derselbe Strahl wie die Hohlraumerkennung
    (``perceive.features._point_inside_shell``). Die Hüllquader entstehen je
    Dreieck und werden je Schale zusammengefasst, ohne Kopie der Ecken
    (Review R20).
    """

    def __init__(self, body: trimesh.Trimesh) -> None:
        self.components = face_components(body)
        count = len(self.components)
        labels = np.empty(len(body.faces), dtype=np.int64)
        for index, members in enumerate(self.components):
            labels[members] = index
        self.triangles = np.asarray(body.triangles, dtype=np.float64)
        self.volumes = _shell_volumes(body, labels, count)
        self.low = np.full((count, 3), np.inf)
        self.high = np.full((count, 3), -np.inf)
        if count > 1:
            np.minimum.at(self.low, labels, self.triangles.min(axis=1))
            np.maximum.at(self.high, labels, self.triangles.max(axis=1))
        self._outer: dict[int, tuple[np.ndarray, tuple[np.ndarray, np.ndarray]]] = {}

    def containers_of(
        self, inners: Sequence[int]
    ) -> Iterator[tuple[int, list[tuple[int, bool | None]]]]:
        """Je Schale aus ``inners`` die Schalen, in denen sie liegt, mit der Antwort des Strahls.

        ``True`` ist belegt, ``None`` sagt der Strahl nicht; wer sicher außen
        liegt, fehlt. Vorab sieben die Hüllquader — **blockweise als Feld und
        nicht je Schale** (Review 25.09.2026): Ein Durchgang je Schale über alle
        anderen waren an 16 000 getrennten Würfeln quadratisch viele kleine
        Feldaufrufe, 18,6 s für :func:`turn_shells_outward` und 24,9 s für
        :func:`parts_inside_parts`. Kandidaten, Reihenfolge und Strahlen sind
        dieselben.
        """
        wanted = np.asarray(inners, dtype=np.int64)
        rows = max(1, _SHELL_BLOCK // max(1, len(self.low)))
        for start in range(0, len(wanted), rows):
            block = wanted[start : start + rows]
            boxed = np.ones((len(block), len(self.low)), dtype=bool)
            for axis in range(3):
                boxed &= self.low[None, :, axis] <= self.low[block, None, axis]
                boxed &= self.high[None, :, axis] >= self.high[block, None, axis]
            for row, inner in enumerate(block.tolist()):
                found: list[tuple[int, bool | None]] = []
                for other in np.flatnonzero(boxed[row]).tolist():
                    if other == inner:
                        continue
                    answer = self.inside(inner, other)
                    if answer is not False:
                        found.append((other, answer))
                yield inner, found

    def inside(self, inner: int, outer: int) -> bool | None:
        """Liegt ``inner`` in ``outer``? ``None``, wenn der Strahl es nicht entscheidet."""
        from app.core.perceive.features import _point_inside_shell, _triangle_bounds

        if outer not in self._outer:
            shell = self.triangles[self.components[outer]]
            self._outer[outer] = (shell, _triangle_bounds(shell))
        shell, bounds = self._outer[outer]
        point = self.triangles[self.components[inner][0], 0]
        return _point_inside_shell(point, shell, bounds)


def turn_shells_outward(body: trimesh.Trimesh) -> bool:
    """Richtet an einem geschlossenen Netz jeden freien Körper samt Inhalt nach außen.

    **Das Vorzeichen des ganzen Körpers reicht nicht** (Durchsicht
    24.09.2026). Bis dahin wurde nur umgestülpt, wenn das Gesamtvolumen
    negativ war: Zwei getrennte Würfel, einer davon innen-außen verkehrt,
    haben zusammen das Volumen null, und die Reparatur sagte „nichts zu
    reparieren" über einem Teil, das jeder Slicer je nach Füllregel als Loch
    liest.

    **Und eine Umkehr gilt dem Baum, nicht allem** (Review R3): Eine Schale,
    die in keiner anderen liegt, ist Material und muss positiv sein. Ist sie
    negativ, dreht sie sich um — und mit ihr alles, was belegt in ihr liegt,
    denn ein ganzer Hohlkörper verkehrt herum hat außen minus und innen plus.
    Ein richtiger Hohlkörper daneben bleibt, wie er ist; vorher kippte die
    Gesamtumkehr seinen Hohlraum mit, und ein korrektes Modell kam
    mehrdeutig heraus. Was dazwischen liegt — eine positive Schale im
    Material einer positiven —, kann ein verkehrter Hohlraum oder ein
    doppeltes Teil sein; das wird nicht geraten (Regel 21), sondern gemeldet
    (:func:`parts_inside_parts`).

    Sagt der Strahl nicht, ob eine Schale frei steht, gilt sie als umschlossen
    und bleibt unberührt. Liefert, ob etwas umgedreht wurde. Das Netz wird
    dabei verändert.
    """
    if not len(body.faces):
        return False
    shells = _Shells(body)
    count = len(shells.components)
    if count == 1:
        # Ein Körper braucht keinen Strahl (Review R20): sein Vorzeichen sagt alles.
        if shells.volumes[0] < 0.0:
            body.invert()
            return True
        return False
    if bool(np.all(shells.volumes >= 0.0)):
        # Lauter richtig gewickelte Teile auch nicht: Gedreht wird nur eine
        # freie negative Schale samt Inhalt (Review 25.09.2026).
        return False
    inside_of = [found for _inner, found in shells.containers_of(range(count))]
    # Je Schale, was belegt in ihr liegt — einmal gesammelt statt je Wurzel
    # über alle Schalen gesucht.
    members_of: list[list[int]] = [[] for _ in range(count)]
    for member, found in enumerate(inside_of):
        for other, answer in found:
            if answer:
                members_of[other].append(member)
    turn = np.zeros(count, dtype=bool)
    for root in range(count):
        if inside_of[root] or shells.volumes[root] >= 0.0:
            continue
        turn[root] = True
        turn[members_of[root]] = True
    if not turn.any():
        return False
    faces = np.asarray(body.faces, dtype=np.int64).copy()
    for index in np.flatnonzero(turn).tolist():
        members = shells.components[index]
        faces[members] = faces[members][:, ::-1]
    body.faces = faces
    return True


def parts_inside_parts(body: trimesh.Trimesh) -> list[tuple[float, float, float]]:
    """Die Mitten der Schalen, die nach außen zeigen und im Material einer anderen liegen.

    Der Rest von Befund B9 der Durchsicht 24.09.2026: Ein Würfel mit falsch
    herum gewickelter Innenschale hatte 9 000 statt 7 000 mm³, und nichts sagte
    es. Ob die innere Schale ein Hohlraum ist, der verkehrt steht, oder ein
    doppeltes Teil, weiß nur der Kunde (Regel 21); Slicer drucken die Stelle je
    nach Füllregel hohl oder voll.

    **Im Material, nicht nur innen** (Review R4): Eine Kugel, die frei in einem
    Hohlraum liegt — eine Rassel, ein Teil im Käfig —, liegt in zwei Schalen,
    der positiven außen und der negativen des Hohlraums, und dort ist Luft; jede
    Füllregel druckt sie voll. Gezählt wird deshalb die Summe der Vorzeichen
    aller belegt umschließenden Schalen: ab eins liegt die Schale im Material.
    Gefragt nach :func:`turn_shells_outward`, am geschlossenen Netz.
    """
    if not len(body.faces):
        return []
    shells = _Shells(body)
    positive = np.flatnonzero(shells.volumes > 0.0)
    if len(positive) < 2:
        return []
    places = []
    for index, found in shells.containers_of(positive.tolist()):
        depth = sum(1 if shells.volumes[other] > 0.0 else -1 for other, answer in found if answer)
        if depth >= 1:
            middle = (shells.low[index] + shells.high[index]) / 2.0
            places.append((float(middle[0]), float(middle[1]), float(middle[2])))
    return places


#: Wie viele Dreieckspaare das Einlesen höchstens prüft, ob die Teile eines
#: Körpers ineinanderstecken (:func:`parts_that_cross`). Die Frage wählt nur
#: den Satz und die Knöpfe am Befund; wo das Budget nicht reicht, bleibt der
#: schlichte Satz, und *Reparieren* sucht vollständig.
CROSSING_PARTS_PAIRS: Final = 200_000

#: Über so vielen Teilen fragt das Einlesen nicht nach — eine Dreieckssuppe
#: hat Hunderte, und keine Antwort darauf ändert, was der Kunde tut.
CROSSING_PARTS_MAX: Final = 256

#: Wie viele Kandidaten der Vorfilter entlang einer Achse je Block erzeugt.
CROSSING_BLOCK: Final = 65_536


def parts_that_cross(
    body: trimesh.Trimesh,
    pieces: Sequence[np.ndarray] | None = None,
    cancelled: CancelToken | None = None,
    *,
    max_pairs: int = CROSSING_PARTS_PAIRS,
) -> tuple[float, float, float] | None:
    """Wo zwei Teile des Körpers einander durchdringen — oder ``None``.

    Befund A5 der Bedienweg-Durchsicht (24.09.2026): Zwei ineinandergeschobene
    Würfel kamen als „Das Modell besteht aus mehreren Teilen" mit *In
    Einzelteile zerlegen* an — die Handlung, die aus einem Teil zwei
    überlappende macht. Dass sie ineinanderstecken, erfuhr der Kunde erst beim
    Reparieren.

    **Nur eine quer durchdringende Wand zählt.** Zwei Teile, die sich an einer
    Fläche berühren, stecken nicht ineinander, und ein Kettenglied mit Spiel
    um das nächste hat überlappende Hüllquader und keine einzige gemeinsame
    Stelle. Geprüft werden nur Paare aus zwei **verschiedenen** Teilen, deren
    Dreiecke im Überlapp der Hüllquader beider Teile liegen, mit der
    Schnittprüfung der Reparatur (:func:`~app.core.geom.intersections.crossing_pairs`)
    — und die Suche hört beim ersten Treffer auf. Über alle Dreiecke gefragt
    kostete sie am Korpus ``F:\\3D Dateien`` 14 der 96 Sekunden aller Importe,
    am Piratenschiff eine Sekunde je Körper, fast alles für Paare innerhalb
    eines Teils. Reicht das Budget (:data:`CROSSING_PARTS_PAIRS`) nicht, heißt
    die Antwort ``None`` — kein Satz, der mehr behauptet, als gesucht wurde.
    Die Vorfrage wählt nur Satz und Knöpfe, sie rechnet keine Geometrie.
    """
    pieces = face_components(body) if pieces is None else pieces
    if not 2 <= len(pieces) <= CROSSING_PARTS_MAX:
        return None
    vertices = np.asarray(body.vertices, dtype=np.float64)
    faces = np.asarray(body.faces, dtype=np.int64)
    triangles = vertices[faces]
    low = triangles.min(axis=1)
    high = triangles.max(axis=1)
    part_low = np.array([low[piece].min(axis=0) for piece in pieces])
    part_high = np.array([high[piece].max(axis=0) for piece in pieces])
    reach = EPS_GEOM
    touching = np.all(part_low[:, None, :] <= part_high[None, :, :] + reach, axis=2) & np.all(
        part_low[None, :, :] <= part_high[:, None, :] + reach, axis=2
    )
    firsts, seconds = np.nonzero(np.triu(touching, 1))
    budget = max_pairs
    for one, other in zip(firsts.tolist(), seconds.tolist(), strict=True):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        box_low = np.maximum(part_low[one], part_low[other]) - reach
        box_high = np.minimum(part_high[one], part_high[other]) + reach
        near: list[np.ndarray] = []
        for number in (one, other):
            piece = np.asarray(pieces[number], dtype=np.int64)
            inside = np.all(low[piece] <= box_high, axis=1) & np.all(high[piece] >= box_low, axis=1)
            near.append(piece[inside])
        if not len(near[0]) or not len(near[1]):
            continue
        found, spent = _first_crossing_between(
            triangles, faces, low, high, near[0], near[1], budget
        )
        if found is not None:
            middle = (triangles[found[0]].mean(axis=0) + triangles[found[1]].mean(axis=0)) / 2.0
            return (float(middle[0]), float(middle[1]), float(middle[2]))
        budget -= spent
        if budget <= 0:
            return None
    return None


def _first_crossing_between(
    triangles: np.ndarray,
    faces: np.ndarray,
    low: np.ndarray,
    high: np.ndarray,
    one: np.ndarray,
    other: np.ndarray,
    budget: int,
) -> tuple[tuple[int, int] | None, int]:
    """Das erste Paar aus ``one`` und ``other``, das quer durchdringt, und wie viele geprüft wurden.

    Ein Durchlauf entlang X über die nach ihrer Untergrenze sortierten
    Dreiecke von ``other``; was sich auch in Y und Z überdeckt, geht blockweise
    in die Schnittprüfung. Über dem Budget kommt ``None`` zurück, wie ohne Fund.
    """
    from app.core.geom.intersections import crossing_pairs

    order = other[np.argsort(low[other, 0], kind="stable")]
    starts = low[order, 0]
    back = float((high[other, 0] - low[other, 0]).max()) + EPS_GEOM
    begin = np.searchsorted(starts, low[one, 0] - back, side="left")
    end = np.searchsorted(starts, high[one, 0] + EPS_GEOM, side="right")
    counts = (end - begin).astype(np.int64)
    if int(counts.sum()) > 20 * budget:
        # Ein langes Dreieck im anderen Teil macht aus dem Vorfilter alle
        # Paare; das Budget wäre ohnehin gerissen.
        return None, budget
    total = np.cumsum(counts)
    spent = 0
    position = 0
    while position < len(one):
        before = int(total[position - 1]) if position else 0
        stop = int(np.searchsorted(total, before + CROSSING_BLOCK, side="right"))
        stop = min(max(stop, position + 1), len(one))
        size = counts[position:stop]
        amount = int(size.sum())
        rows = np.arange(position, stop)
        position = stop
        if not amount:
            continue
        left = np.repeat(rows, size)
        steps = np.arange(amount) - np.repeat(np.cumsum(size) - size, size)
        first = one[left]
        second = order[begin[left] + steps]
        overlap = np.all(low[first] <= high[second] + EPS_GEOM, axis=1) & np.all(
            low[second] <= high[first] + EPS_GEOM, axis=1
        )
        first, second = first[overlap], second[overlap]
        spent += len(first)
        if spent > budget:
            return None, spent
        if not len(first):
            continue
        hit, flat = crossing_pairs(
            triangles[first], triangles[second], faces[first], faces[second], with_coplanar=True
        )
        across = np.flatnonzero(np.asarray(hit) & ~np.asarray(flat))
        if len(across):
            index = int(across[0])
            return (int(first[index]), int(second[index])), spent
    return None, spent


def parts_can_be_merged(mesh: MeshData) -> bool:
    """Ob *Überschneidungen auflösen* an diesem Körper tragen kann.

    Dieselbe Vorprüfung wie beim Reparieren (:func:`_intersections_resolvable`),
    ohne die Eigenkreuzung einer Schale — die kennt nur die volle Suche. Sonst
    böte der Befund einen Knopf an, der in der nächsten Warnung endet.
    """
    return _intersections_resolvable(mesh) is None


def part_inside_finding(places: Sequence[tuple[float, float, float]], components: int) -> Finding:
    """Der Befund zu :func:`parts_inside_parts` — derselbe aus Import und Reparatur.

    ``components`` ist die Teilezahl des Körpers; *In Einzelteile zerlegen*
    plant daraus seine Ausgänge.
    """
    return Finding(
        code="repair.part_inside",
        severity="warning",
        message=_(
            "{parts} Teile liegen ganz in einem anderen. Slicer drucken sie je nach "
            "Einstellung hohl oder voll.",
            parts=len(places),
        )
        if len(places) > 1
        else _(
            "Ein Teil liegt ganz in einem anderen. Slicer drucken es je nach Einstellung "
            "hohl oder voll."
        ),
        values={"parts": len(places), "components": components},
        location=places[0],
        # Zerlegt, ist das innere Teil ein eigener Körper: wählbar, löschbar
        # oder als Hohlraum abziehbar (Review R13). Welche der drei Antworten
        # stimmt, sagt der Kunde, nicht die Reparatur (Regel 21).
        suggestions=(SPLIT_BODIES,),
    )


#: Wie weit ein Punkt neben einer Kante sitzen darf und noch als auf ihr
#: liegend zählt. Eine T-Kreuzung stammt aus einem exakten Split im
#: Quell-CAD — die Abweichung ist Rechenrauschen, kein Spalt.
ON_EDGE_TOLERANCE = 1e-4

#: Über so vielen offenen Kanten ist ein Körper kein Modell mit einem Defekt,
#: sondern ein Modell in Stücken — und jeden Randpunkt mit jeder Randkante zu
#: paaren hört auf, die richtige Art zu sein, eine Minute zu verbringen.
MAX_STITCH_EDGES = 4096

#: Wie oft das Vernähen höchstens nachfasst. Ein Durchgang teilt jede Fläche
#: an höchstens einem Punkt; eine lange Kante neben einer fein geteilten
#: Nachbarfläche trägt aber mehrere. Mit einem Durchgang blieb dort ein
#: Spalt über kollinearen Punkten stehen, und der Lochfüller schloss ihn mit
#: Dreiecken ohne Fläche (Sonde 24.09.2026: drei Punkte auf einer Kante, vier
#: Nullflächen im reparierten Würfel). Jeder Durchgang verkürzt die Liste der
#: aufsitzenden Punkte; die Zahl ist nur die Schranke dafür.
STITCH_ROUNDS = 64


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

    Sitzen mehrere Punkte auf derselben Kante, wird nachgefasst, bis keiner
    mehr übrig ist (:data:`STITCH_ROUNDS`).

    Liefert den Körper und wie viele Flächen geteilt wurden.
    """
    working = mesh
    total = 0
    for _round in range(STITCH_ROUNDS):
        working, seams = _stitched_once(working)
        if not seams:
            break
        total += seams
    return working, total


def _stitched_once(mesh: MeshData) -> tuple[MeshData, int]:
    """Ein Durchgang des Vernähens: jede Fläche höchstens an einem Punkt."""
    # Gelesen wird am Netz selbst: Die Rechnung darunter baut ein neues und
    # ändert am alten nichts — eine Kopie am Anfang kostete am 1,2-M-Netz
    # bei jedem Aufruf ein Zehntel einer Sekunde, auch ohne einen Rand.
    body = mesh.raw
    table = _edge_table(mesh)
    boundary = table.rows(1)
    if not len(boundary) or len(boundary) > MAX_STITCH_EDGES:
        return mesh, 0

    # Die Kanten der Zählung sind sortiert wie ``edges_sorted``; die Zeilen
    # darüber zu holen spart, sie an einem abgeleiteten Netz neu zu sortieren.
    edges = table.unique[table.inverse[boundary]]
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
    _carried_colours(
        body,
        stitched,
        np.concatenate([np.flatnonzero(kept), np.asarray(added_from, dtype=np.int64)]),
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

    Das gilt, wo die Fächer verschiedene Blätter sind — zwei Kegel, Spitze an
    Spitze. Liegen beide Löcher in **einer** Fläche und berühren sich dort,
    trägt jede Kopie je eine Kante beider Löcher; :func:`_hole_rings` legt die
    Kopien dann wieder zusammen.
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


def _simple_cycles(walk: list[int]) -> list[list[int]]:
    """Ein geschlossener Umlauf, der Ecken mehrfach besucht, als einfache Ringe.

    Jede Rückkehr zu einer schon besuchten Ecke schneidet die Schlaufe seit
    ihrem letzten Besuch als eigenen Ring ab; die Umlaufrichtung bleibt die
    des Ganzen. Aus der Acht ``V a b V c d`` werden ``V a b`` und ``V c d``.
    """
    stack: list[int] = []
    position: dict[int, int] = {}
    cycles: list[list[int]] = []
    for vertex in walk:
        start = position.get(vertex)
        if start is None:
            position[vertex] = len(stack)
            stack.append(vertex)
            continue
        cycle = stack[start:]
        for inner in stack[start + 1 :]:
            del position[inner]
        del stack[start + 1 :]
        if len(cycle) >= 3:
            cycles.append(cycle)
    if len(stack) >= 3:
        cycles.append(stack)
    return cycles


def _hole_rings(mesh: MeshData) -> tuple[MeshData, list[list[int]]]:
    """Das Netz und die Ringe, die :func:`fill_boundary_loops` schließt.

    **Erst die Sanduhren, dann die Ringe.** Zwei Löcher, die sich eine Ecke
    teilen, geben dort vier Randkanten, und die Kette bricht ab; aufgetrennt
    (:func:`split_pinched_vertices`) hat jede Kopie ihre zwei.

    **Und wo die Kopie beide Löcher trägt, wird sie zurückgenommen.** Liegen
    die zwei Löcher in derselben Fläche, stehen um die Ecke zwei Fächer im
    Wechsel mit ihnen, und jeder Fächer grenzt an beide: Der Ring lief als
    Acht durch beide Kopien, kein Ohr passte, und der Fächer über die Mitte
    faltete sich über der Ecke (Durchsicht 24.09.2026: `plate_holes.stl` ohne
    zwei Deckdreiecke mit gemeinsamer Ecke — dicht gemeldet, sieben
    Durchdringungen, die Deckfläche fehlte danach in der Erkennung). Solche
    Kopien werden wieder eine Ecke, und jede Schlaufe der Acht wird ihr
    eigener Ring — hier genau die zwei fehlenden Dreiecke.

    **Erkannt wird die Acht an der Lage, nicht an einer Liste der Kopien.**
    Eine Kopie steht bitgleich am Ort ihrer Ecke; derselbe Ort zweimal in
    einem Ring ist dieselbe Ecke, gleich ob die Kopie von hier stammt, von
    einem Aufrufer, der schon aufgetrennt hat, oder aus einer Datei mit
    unverschweißten Doppelpunkten. Zwei Kopien in **verschiedenen** Ringen
    bleiben getrennt — das ist die Sanduhr, für die das Auftrennen da ist.
    """
    split, _count = split_pinched_vertices(mesh)
    loops = boundary_loops(split)
    if not loops:
        return split, loops
    points = np.asarray(split.raw.vertices, dtype=float)
    # Welche Ecken zusammengehören: alle, die derselbe Ring am selben Ort
    # besucht. Über eine Vereinigungsmenge, weil zwei Ringe durch dieselbe
    # Ecke dieselben Kopien in anderer Reihenfolge nennen können.
    parent: dict[int, int] = {}

    def root(vertex: int) -> int:
        while parent.get(vertex, vertex) != vertex:
            vertex = parent[vertex]
        return vertex

    for loop in loops:
        first: dict[tuple[float, ...], int] = {}
        for vertex in loop:
            place = tuple(points[vertex].tolist())
            if place in first:
                if root(vertex) != root(first[place]):
                    parent[root(vertex)] = root(first[place])
            else:
                first[place] = vertex
    if not parent:
        return split, loops

    body = split.raw
    faces = np.asarray(body.faces, dtype=np.int64)
    mapping = np.arange(len(body.vertices), dtype=np.int64)
    for vertex in parent:
        mapping[vertex] = root(vertex)
    faces = mapping[faces]
    # Die zurückgenommenen Kopien stehen am Ende der Punktliste und sind
    # danach unbenutzt; sie fallen, und die übrigen rücken nach.
    used = np.zeros(len(body.vertices), dtype=bool)
    used[faces.ravel()] = True
    renumber = np.cumsum(used) - 1
    joined = trimesh.Trimesh(
        vertices=np.asarray(body.vertices, dtype=float)[used],
        faces=renumber[faces],
        process=False,
    )
    _carried_colours(body, joined, np.arange(len(faces), dtype=np.int64))
    rings = [
        [int(renumber[mapping[vertex]]) for vertex in ring]
        for loop in loops
        for ring in _simple_cycles([int(mapping[vertex]) for vertex in loop])
    ]
    _log.info("rejoined %d pinched vertex cop(ies) whose rings touched", len(parent))
    return MeshData.of(joined, slots=split.slots), rings


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


def _ring_normal(ring: np.ndarray, centre: np.ndarray) -> np.ndarray | None:
    """Die Normale der Ebene, in der ein Randring liegt — ``None`` ohne Fläche.

    **Nach Newell, nicht über eine SVD** (RM-187, 22.09.2026). Die SVD ging
    durch LAPACK und durfte die Normale mit beiden Vorzeichen liefern —
    Accelerate auf dem Mac, OpenBLAS sonst —, und das Vorzeichen entschied, in
    welcher Richtung geohrt wurde: Dasselbe Loch bekam beim Import auf jeder
    Plattform andere Dreiecke. Newells Flächenvektor, die Summe der
    Kreuzprodukte aufeinanderfolgender Ecken, braucht nur Grundrechenarten,
    summiert exakt (``math.fsum``), und seine Richtung folgt dem Umlauf des
    Rings — derselben Frage, die das Ohren und die Faltprobe stellen.
    """
    local = ring - centre
    crosses = np.cross(local, np.roll(local, -1, axis=0))
    newell = np.array([math.fsum(crosses[:, axis].tolist()) for axis in range(3)])
    size = math.hypot(float(newell[0]), float(newell[1]), float(newell[2]))
    if size <= EPS_GEOM * EPS_GEOM:
        return None
    return newell / size


def _folds(corners: np.ndarray, normal: np.ndarray) -> bool:
    """Ob eine Füllung sich über dem Ring faltet.

    Jedes Dreieck muss in die Richtung des Rings zeigen: Sein Flächenvektor
    gegen die Ringnormale ist seine Fläche im Grundriss, und die ist für ein
    Ohr per Bau positiv. Der Fächer über die Mitte hat diese Zusage nicht —
    ein Ring, der von seiner Mitte aus nicht ganz zu sehen ist, bekommt
    Dreiecke, die rückwärts über ihre Nachbarn klappen: dicht, und doch eine
    Durchdringung, die der Bericht als geschlossenes Loch zählte. ``corners``
    ist ``(n, 3, 3)``.
    """
    area = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    facing = area[:, 0] * normal[0] + area[:, 1] * normal[1] + area[:, 2] * normal[2]
    return bool(np.any(facing <= EPS_GEOM * EPS_GEOM))


#: Nach wie vielen Ohren das Ohrenschneiden nach dem Abbruch fragt. Ein Ohr
#: kostet einen Feldvergleich gegen die übrigen Reflexecken; tausend davon
#: sind an einem gewellten Ring von 8 000 Kanten ein Bruchteil einer Sekunde.
EARS_PER_CANCEL_CHECK: Final = 1000


def _loop_triangles(
    points: np.ndarray,
    loop: list[int],
    taken: dict[tuple[int, int], int] | None = None,
    cancelled: CancelToken | None = None,
) -> np.ndarray:
    """Dreiecke über einem Randring, in seiner Umlaufrichtung.

    Drei Ecken sind ein Dreieck. Darüber wird in der Ausgleichsebene des Rings
    geohrt (*ear clipping*): Wer eine Ecke findet, deren Dreieck im Inneren
    liegt und keine andere Ecke einschließt, schneidet sie ab. Das Verfahren
    ist für jeden einfachen Ring vollständig; bleibt es stecken — ein Ring,
    der sich in seiner Ebene selbst schneidet, weil das Loch stark gewölbt ist
    —, tritt der Fächer über die Ringmitte an seine Stelle. Er erfindet einen
    Punkt, aber keinen Ort: Die Mitte liegt in der Ebene der Ecken, die das
    Loch umgeben.

    **Ein Ohr, dessen Sehne im Netz schon eine Kante ist, wird übersprungen**
    wie ein reflexes (``taken``, Durchsicht 24.09.2026). Die Ecken eines
    Randrings sind oft anderswo verbunden; bis dahin prüfte erst die fertige
    Füllung die Kanten, verwarf alle Ohren und fiel auf den Fächer — der an
    einer abgeschnittenen Kugelschale rückwärts klappte, und das Loch blieb
    offen, obwohl 92 gültige Ohren es schlossen.

    **Und es kostet linear viele Feldvergleiche, nicht quadratisch viele
    Listen.** Die Ecken hängen in einer verketteten Liste, und ob ein Ohr eine
    andere Ecke einschließt, fragt es nur die Reflexecken: Eine konvexe Ecke
    kann in keinem Ohr liegen, ohne dass eine reflexe darin liegt. Vorher baute
    jeder Versuch eine Liste über alle Ringecken — ein gewellter Ring aus
    8 000 Kanten kostete 12,8 s, und der Abbruch griff erst danach. Jetzt
    fragt die Schleife alle :data:`EARS_PER_CANCEL_CHECK` Versuche nach
    ``cancelled``.
    """
    ring = points[loop]
    count = len(loop)
    if count == 3:
        return np.asarray([loop], dtype=np.int64)

    centre = np.asarray(units.exact_centre(ring.tolist()), dtype=np.float64)
    normal = _ring_normal(ring, centre)
    if normal is None:
        return np.zeros((0, 3), dtype=np.int64)
    local = ring - centre
    # Dieselbe Ebenenbasis wie die Lochbrücken (:func:`_bridged_holes`) — eine
    # Rechnung, nicht zwei Fassungen, die ein Kommentar zusammenhält.
    basis = _plane_basis(normal)
    if basis is None:
        return np.zeros((0, 3), dtype=np.int64)
    basis_u, basis_v = basis
    flat = np.column_stack((along(local, basis_u), along(local, basis_v)))
    # Ein Ring, der gegen den Uhrzeigersinn läuft, hat positive Fläche; sonst
    # spiegelt das Ohren die Innen-Außen-Frage.
    ahead = np.roll(flat, -1, axis=0)
    signed = float((flat[:, 0] * ahead[:, 1] - flat[:, 1] * ahead[:, 0]).sum()) / 2.0
    order = np.arange(count) if signed >= 0.0 else np.arange(count)[::-1]
    # Nachfolger und Vorgänger in der Umlaufrichtung des Ohrens.
    after = np.empty(count, dtype=np.int64)
    before = np.empty(count, dtype=np.int64)
    after[order] = np.roll(order, -1)
    before[order] = np.roll(order, 1)
    xs = flat[:, 0]
    ys = flat[:, 1]
    ids = np.asarray(loop, dtype=np.int64)

    def turn(corner: int) -> float:
        """Wie stark der Ring an ``corner`` nach links abbiegt."""
        first, third = int(before[corner]), int(after[corner])
        return float(
            (xs[corner] - xs[first]) * (ys[third] - ys[corner])
            - (ys[corner] - ys[first]) * (xs[third] - xs[corner])
        )

    # Reflex heißt hier: nicht sicher konvex. Auch eine gerade Ecke kann in
    # einem Ohr liegen, und eine konvexe wird nie reflex, solange geohrt wird.
    reflex = np.zeros(count, dtype=bool)
    for corner in range(count):
        reflex[corner] = turn(corner) <= EPS_GEOM
    alive = np.ones(count, dtype=bool)

    def is_ear(corner: int) -> bool:
        if reflex[corner]:
            return False
        first, third = int(before[corner]), int(after[corner])
        if taken is not None:
            chord = (min(loop[first], loop[third]), max(loop[first], loop[third]))
            if taken.get(chord, 0) >= 1:
                return False
        suspects = np.flatnonzero(reflex & alive)
        # Eine Ecke, die ein Ohr selbst trägt, liegt nicht in ihm — auch ihre
        # zweite Kopie an einer Lochbrücke nicht (:func:`_bridged_holes`).
        suspects = suspects[
            (ids[suspects] != ids[first])
            & (ids[suspects] != ids[corner])
            & (ids[suspects] != ids[third])
        ]
        if not len(suspects):
            return True
        corners = ((first, corner), (corner, third), (third, first))
        inside = np.ones(len(suspects), dtype=bool)
        for start, end in corners:
            edge_x = xs[end] - xs[start]
            edge_y = ys[end] - ys[start]
            inside &= edge_x * (ys[suspects] - ys[start]) - edge_y * (xs[suspects] - xs[start]) >= (
                -EPS_GEOM
            )
        return not bool(inside.any())

    ears: list[list[int]] = []
    remaining = count
    current = int(order[0])
    failures = 0
    attempts = 0
    while remaining > 3 and failures <= remaining:
        attempts += 1
        if cancelled is not None and attempts % EARS_PER_CANCEL_CHECK == 0:
            cancelled.raise_if_cancelled()
        if is_ear(current):
            first, third = int(before[current]), int(after[current])
            ears.append([loop[first], loop[current], loop[third]])
            alive[current] = False
            after[first] = third
            before[third] = first
            remaining -= 1
            for neighbour in (first, third):
                if reflex[neighbour]:
                    reflex[neighbour] = turn(neighbour) <= EPS_GEOM
            # Weiter mit der Ecke dahinter, nicht zurück zur davor: Mit
            # gesperrten Sehnen bleibt die Rückwärtsfolge an einer
            # abgeschnittenen Kugelschale stecken, die Vorwärtsfolge nicht.
            current = third
            failures = 0
        else:
            current = int(after[current])
            failures += 1
    if remaining == 3:
        last = current
        ears.append([loop[int(before[last])], loop[last], loop[int(after[last])]])
        return np.asarray(ears, dtype=np.int64)

    # Der Fächer über die Mitte, mit einer Ecke mehr: Sie steht am Ende der
    # Punktliste, und der Aufrufer hängt sie an.
    return _loop_fan(loop, len(points))


def _plane_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Zwei Richtungen in der Ebene zu ``normal`` — für Ohren, Lochbrücken und Mantel dieselbe."""
    basis_u = np.cross(normal, (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0))
    length = math.hypot(float(basis_u[0]), float(basis_u[1]), float(basis_u[2]))
    if length <= EPS_GEOM:
        return None
    basis_u = basis_u / length
    return basis_u, np.cross(normal, basis_u)


def _segments_cross(
    start: np.ndarray, end: np.ndarray, firsts: np.ndarray, seconds: np.ndarray
) -> bool:
    """Ob die Strecke von ``start`` nach ``end`` eine der Strecken ``firsts``, ``seconds``
    im Inneren schneidet (in der Ebene; gemeinsame Endpunkte zählen nicht)."""
    if not len(firsts):
        return False

    def side(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
        return np.asarray(
            (b[..., 0] - a[..., 0]) * (c[..., 1] - a[..., 1])
            - (b[..., 1] - a[..., 1]) * (c[..., 0] - a[..., 0])
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

    def apart(spots: np.ndarray, spot: np.ndarray) -> np.ndarray:
        """Abstände in der Ebene über Grundrechenarten und ``sqrt``, nicht ``np.hypot``.

        Das rundet je Plattform verschieden, und am Abstand hängt, welche Ecke
        die Brücke bekommt — damit die Dreiecke der Fläche (RM-187, Review R11).
        """
        across = spots[:, 0] - spot[0]
        down = spots[:, 1] - spot[1]
        return np.asarray(np.sqrt(across * across + down * down))

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
        distance = apart(polygon_flat, anchor)
        bridge: int | None = None
        for candidate in np.argsort(distance, kind="stable").tolist():
            target = polygon_flat[candidate]
            touching = (
                (apart(firsts, target) <= EPS_GEOM)
                | (apart(seconds, target) <= EPS_GEOM)
                | (apart(firsts, anchor) <= EPS_GEOM)
                | (apart(seconds, anchor) <= EPS_GEOM)
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
    band: np.ndarray | None = None
    """Die fertigen Dreiecke eines Mantels zwischen zwei Ringen (:func:`_band_between`)."""


#: Wie weit zwei Richtungen voneinander abweichen dürfen und noch als parallel
#: gelten — als Sinus des Winkels, rund ein Hundertstel Grad. Ein CAD-Export
#: legt die Mündungen einer Bohrung exakt parallel; eine Zufallsgleichheit
#: zweier Löcher trifft diese Grenze nicht.
BAND_PARALLEL: Final = 1e-4


def _length(vector: np.ndarray) -> float:
    """Die Länge eines Raumvektors über Grundrechenarten und ``sqrt`` (RM-187)."""
    x, y, z = (float(value) for value in vector)
    return math.sqrt(x * x + y * y + z * z)


def _band_between(
    points: np.ndarray,
    first: list[int],
    second: list[int],
    tolerance: float,
    owner_of: dict[tuple[int, int], int],
    centroids: np.ndarray,
    shape_a: tuple[np.ndarray, np.ndarray] | None = None,
    shape_b: tuple[np.ndarray, np.ndarray] | None = None,
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
    basis = _plane_basis(axis)
    if basis is None:
        return None
    basis_u, basis_v = basis
    local_a, local_b = ring_a - centre_a, ring_b - centre_b
    if float(np.abs(along(local_a, axis)).max()) > tolerance:
        return None
    if float(np.abs(along(local_b, axis)).max()) > tolerance:
        return None
    # **Erst die Nachbarn, dann die Ecken** (Review 25.09.2026). Ob die
    # vorhandenen Wände die Ringe schon verbinden, kostet eine Frage je
    # Randkante; die Paarung darunter hält jede Ecke gegen jede. Sie lief
    # zuerst, und am offenen Rohr mit 4 096 Teilungen kostete sie 3,0 s und
    # 411 MB für einen Mantel, den diese Probe danach verwarf.
    for ring, centre, toward in ((first, centre_a, axis), (second, centre_b, -axis)):
        faces: list[int] = []
        for index in range(count):
            edge = (
                min(ring[index], ring[(index + 1) % count]),
                max(ring[index], ring[(index + 1) % count]),
            )
            owner = owner_of.get(edge)
            if owner is None:
                return None
            faces.append(owner)
        side = along(centroids[np.asarray(faces, dtype=np.int64)] - centre, toward)
        if float(side.max()) > tolerance:
            return None
    flat_a = np.column_stack((along(local_a, basis_u), along(local_a, basis_v)))
    flat_b = np.column_stack((along(local_b, basis_u), along(local_b, basis_v)))
    # ``np.sqrt`` über Grundrechenarten statt ``np.hypot``: Das ist eine
    # Bibliotheksfunktion der Plattform, und am Radius hängt, ob ein Band
    # entsteht (Review R11, RM-187).
    radius_a = np.sqrt(flat_a[:, 0] * flat_a[:, 0] + flat_a[:, 1] * flat_a[:, 1])
    radius_b = np.sqrt(flat_b[:, 0] * flat_b[:, 0] + flat_b[:, 1] * flat_b[:, 1])
    if float(radius_a.min()) <= tolerance or float(radius_b.min()) <= tolerance:
        return None
    scale = math.fsum(radius_b.tolist()) / math.fsum(radius_a.tolist())
    direction_a = flat_a / radius_a[:, None]
    direction_b = flat_b / radius_b[:, None]
    match = _nearest_directions(direction_a, direction_b)
    if len(np.unique(match)) != count:
        return None
    # Dieselben zwei Produkte und dieselbe Summe wie in der Paarung — bitgleich.
    matched = direction_a[:, 0] * direction_b[match, 0] + direction_a[:, 1] * direction_b[match, 1]
    if float(matched.min()) < 1.0 - BAND_PARALLEL * BAND_PARALLEL:
        return None
    reach = max(tolerance, BAND_PARALLEL * float(radius_b.max()))
    if float(np.abs(radius_b[match] - scale * radius_a).max()) > reach:
        return None
    # Der Mantel läuft über jede Randkante in der Richtung ihres Rings; das
    # geht nur, wenn der zweite Ring gegenläufig um die Achse läuft.
    step = (match[(np.arange(count) + 1) % count] - match) % count
    if not bool(np.all(step == count - 1)):
        return None
    band: list[list[int]] = []
    for index in range(count):
        here, there = int(match[index]), int(match[(index + 1) % count])
        band.append([first[index], first[(index + 1) % count], second[there]])
        band.append([first[index], second[there], second[here]])
    return np.asarray(band, dtype=np.int64)


#: Wie viele Skalarprodukte :func:`_nearest_directions` auf einmal als Feld
#: hält — zwei Megabyte je Zwischenfeld, gleich wie fein die Ringe sind.
_DIRECTION_BLOCK: Final = 1 << 18


def _nearest_directions(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Je Richtung aus ``first`` die Nummer der ähnlichsten aus ``second``.

    Beide sind ``(n, 2)`` und von Einheitslänge. Dasselbe wie ``argmax`` über
    das volle Feld der Skalarprodukte, Zeile für Zeile — nur in Blöcken, statt
    das Feld aus Ecken mal Ecken anzulegen: An zwei Ringen zu je 2 048 Ecken
    waren das drei Felder zu 33 MB (Review 25.09.2026). Gleichstände
    entscheidet wie dort die kleinere Nummer.
    """
    rows = max(1, _DIRECTION_BLOCK // max(1, len(second)))
    match = np.empty(len(first), dtype=np.int64)
    for start in range(0, len(first), rows):
        part = first[start : start + rows]
        dots = part[:, 0, None] * second[None, :, 0] + part[:, 1, None] * second[None, :, 1]
        match[start : start + rows] = np.argmax(dots, axis=1)
    return match


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
    cancelled: CancelToken | None = None,
) -> list[_FillJob]:
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
        centre, normal, _area = cast(tuple[np.ndarray, np.ndarray, float], shapes[outer])
        basis = _plane_basis(normal)
        if basis is None:
            continue
        basis_u, basis_v = basis
        outline = points[loops[outer]] - centre
        region = Polygon(np.column_stack((along(outline, basis_u), along(outline, basis_v))))
        if not region.is_valid:
            continue
        for candidate in near.tolist():
            other = order[candidate]
            if other == outer or other in taken:
                continue
            other_centre, other_normal, _other_area = known[candidate]
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
        bridged = _bridged_holes(points, loops[outer], [loops[hole] for hole in holes], normal)
        if bridged is None:
            continue
        jobs.append(
            (outer, _FillJob(loop=bridged, rims=(loops[outer], *(loops[hole] for hole in holes))))
        )
        merged.update([outer, *holes])
    # Zwei übrige Ringe, die die Enden einer fehlenden Wand sind, werden ein
    # Mantel (:func:`_band_between`).
    if owner_of is not None and centroids is not None:
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
                offset[:, 0] * offset[:, 0]
                + offset[:, 1] * offset[:, 1]
                + offset[:, 2] * offset[:, 2]
            )
            sideways = np.cross(offset, normal)
            fits = (
                (length > tolerance)
                & (np.sqrt(np.sum(across * across, axis=1)) <= loose)
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
    return [job for _index, job in sorted(jobs, key=lambda item: item[0])]


#: Bis zu wie vielen Ecken ein Ring über alle Triangulierungen gefüllt wird.
#: Die Suche kostet die dritte Potenz der Eckenzahl; bei 32 sind es rund
#: 5 500 Schritte, gemessen 10 ms je Ring. Ein Viertel der Wand einer Bohrung
#: Ø 5,2 mit 48 Teilungen hat 26 Ecken und kommt damit als Wand zurück, bei
#: sechzehn als flacher Deckel quer durch die Bohrung (24.09.2026). Eine
#: halbe Wand bleibt flach: Dort ist die flache Schließung kleiner als der
#: halbe Mantel, und welche gemeint war, sagt nur die Form der Restwand.
SMOOTH_FILL_CORNERS: Final = 32


def _unit_normals(triangles: np.ndarray) -> np.ndarray:
    """Einheitsnormalen der Dreiecke ``(n, 3, 3)`` — Nullflächen bekommen null."""
    raw = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    size = np.sqrt(raw[:, 0] * raw[:, 0] + raw[:, 1] * raw[:, 1] + raw[:, 2] * raw[:, 2])
    return np.asarray(
        np.divide(raw, size[:, None], out=np.zeros_like(raw), where=size[:, None] > 0.0)
    )


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
    Der Knick ist eins minus der Kosinus, gerechnet über Kreuzprodukte und
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
        crossed[:, 0] * crossed[:, 0]
        + crossed[:, 1] * crossed[:, 1]
        + crossed[:, 2] * crossed[:, 2]
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
                    rim_normal(first, middle)
                    if middle == first + 1
                    else triangle_normal(first, middle)
                )
                neighbour_right = (
                    rim_normal(middle, last)
                    if last == middle + 1
                    else triangle_normal(middle, last)
                )
                worst = max(
                    left[0], right[0], bend(normal, neighbour_left), bend(normal, neighbour_right)
                )
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
    #: Die Randkanten des Auftrags über ihre Ecklagen — sie überstehen das
    #: Neunummerieren, mit dem spätere Schritte Ecken wegräumen.
    rim_keys: frozenset[tuple[tuple[float, ...], tuple[float, ...]]] = frozenset()


def _edge_key(first: np.ndarray, second: np.ndarray) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Eine Kante über die Lage ihrer Ecken, unabhängig von der Richtung."""
    one = tuple(float(value) for value in first)
    other = tuple(float(value) for value in second)
    return (one, other) if one <= other else (other, one)


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
    #: Je offen gebliebenem Auftrag seine Randkanten und seine Fläche — damit
    #: sich die Bilanz am Endstand neu zählen lässt (:func:`_flat_still_open`).
    flat: tuple[tuple[frozenset[tuple[tuple[float, ...], tuple[float, ...]]], float], ...] = ()
    #: Mitte und Fläche der größten geschlossenen Öffnung.
    widest: tuple[float, float, float] | None = None
    widest_span: float = 0.0
    #: Die großen Öffnungen, die auf Wunsch offen blieben (*Offen lassen*,
    #: ``keep_wide``) — je Auftrag Randkanten, Fläche und Mitte, damit der
    #: Bericht am Endstand zählen kann, was davon noch offen ist.
    kept: tuple[
        tuple[frozenset[tuple[tuple[float, ...], tuple[float, ...]]], float, tuple[float, ...]],
        ...,
    ] = ()


def _assembled(mesh: MeshData, records: Sequence[_RingFill], slots: np.ndarray | None) -> MeshData:
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
    # Angehängt, nicht umgebaut: Die Kantenzählung kommt aus der alten (RM-224).
    carry_appended_edges(body, patched)
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
    ``EPS_GEOM`` bleibt der Ring offen. Das Volumen je Teil kommt aus
    :func:`_shell_volumes`, nahe am Teil und elementweise (RM-187).
    """
    body = patched.raw
    components = face_components(body)
    labels = np.empty(len(body.faces), dtype=np.int64)
    for index, faces in enumerate(components):
        labels[faces] = index
    volume = _shell_volumes(body, labels, len(components))
    area = np.bincount(labels, weights=np.asarray(body.area_faces), minlength=len(components))
    flat = np.flatnonzero(np.abs(volume) <= EPS_GEOM * area)
    if not len(flat):
        return set()
    return {int(owner) for owner in owners[np.isin(labels[first_new:], flat)]}


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
    filled = _fill_loops(mesh)
    return filled.mesh, filled.closed, filled.wide


def _fill_loops(
    mesh: MeshData, cancelled: CancelToken | None = None, *, keep_wide: bool = False
) -> _Filled:
    """:func:`fill_boundary_loops` mit allem, was der Bericht darüber sagt.

    ``cancelled`` wird je Ring und innerhalb des Ohrenschneidens gefragt.
    ``keep_wide`` lässt die Ringe über :data:`FILL_LOOP_SHARE` offen und
    schließt nur die kleinen — der Rückweg *Offen lassen* an der großen
    Öffnung (RM-241): Eine Vase bleibt offen, ihre Risse gehen trotzdem zu.
    """
    # Sanduhren aufgetrennt, Achten in ihre Schlaufen zerlegt (:func:`_hole_rings`).
    mesh, loops = _hole_rings(mesh)
    if not loops:
        return _Filled(mesh)

    body = mesh.raw
    points = np.asarray(body.vertices, dtype=float)
    limit = float(body.area) * FILL_LOOP_SHARE
    # Welcher Slot an welcher Randkante hängt: Die neuen Dreiecke bekommen
    # den ihres Nachbarn, damit eine geschlossene Tasche nicht in einer
    # anderen Farbe dasteht als die Wand um sie herum.
    single = _edge_table(mesh).rows(1)
    slots = np.asarray(mesh.slots, dtype=np.int64) if mesh.slots else None
    neighbour_of: dict[tuple[int, int], int] = {}
    directed = np.asarray(body.edges, dtype=np.int64)[single]
    for row, (start, end) in enumerate(directed.tolist()):
        owner = int(single[row]) // 3
        neighbour_of[(min(int(start), int(end)), max(int(start), int(end)))] = owner

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

    records: list[_RingFill] = []
    kept: list[
        tuple[frozenset[tuple[tuple[float, ...], tuple[float, ...]]], float, tuple[float, ...]]
    ] = []
    blocked = 0
    triangles_now = np.asarray(body.triangles, dtype=np.float64)
    centroids = (triangles_now[:, 0] + triangles_now[:, 1] + triangles_now[:, 2]) / 3.0
    face_normals = _unit_normals(triangles_now)
    faces_now = np.asarray(body.faces, dtype=np.int64)
    jobs = _fill_jobs(
        points,
        loops,
        max(10.0 * EPS_GEOM, weld_tolerance(float(mesh.bounds.diagonal))),
        neighbour_of,
        centroids,
        cancelled,
    )
    position = 0
    while position < len(jobs):
        job = jobs[position]
        position += 1
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
            middle_of_rim = np.asarray(units.exact_centre(points_of_rim.tolist()), dtype=np.float64)
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
        wide_here = spanned > limit
        rim_keys = frozenset(
            _edge_key(points[rim[position]], points[rim[(position + 1) % len(rim)]])
            for rim in job.rims
            for position in range(len(rim))
        )
        if keep_wide and wide_here:
            kept.append((rim_keys, spanned, tuple(float(value) for value in centre)))
            continue
        normal = _ring_normal(ring, centre)
        # Mit der Mitte als letzter Ecke, damit die Faltprobe auch den Fächer
        # an seinen wirklichen Punkten misst.
        reachable = np.vstack([points, centre[None, :]])
        # Erst die Ohren, und wenn ihre Sehnen an Kanten stoßen, die schon zwei
        # Flächen tragen, der Fächer über die Mitte: Seine inneren Kanten sind
        # immer neu. Keiner von beiden, wenn er sich faltet (:func:`_folds`) —
        # dann bleibt der Ring offen und der Bericht sagt es.
        chosen: np.ndarray | None = None
        needs_middle = False
        # Eine Fläche mit Löchern bekommt keinen Fächer: Er deckte die Löcher.
        # Ein Mantel ist fertig und wird nur geprüft.
        if job.band is not None:
            attempts = [job.band]
        else:
            attempts = []
            if len(job.rims) == 1:
                # Ein kleiner Ring zuerst über alle Triangulierungen, nach dem
                # kleinsten Knick (:func:`_smoothest_fill`).
                smooth = _smoothest_fill(points, loop, neighbour_of, face_normals, taken)
                if smooth is not None:
                    attempts.append(smooth)
            attempts.append(_loop_triangles(points, loop, taken, cancelled))
            if len(job.rims) == 1:
                attempts.append(_loop_fan(loop, len(points)))
        for attempt in attempts:
            if len(job.rims) > 1 and len(attempt) and int(attempt.max()) >= len(points):
                continue
            if job.band is not None:
                if _band_crosses(points, faces_now, attempt, cancelled):
                    continue
            elif not len(attempt) or normal is None or _folds(reachable[attempt], normal):
                continue
            middle_here = bool(int(attempt.max()) >= len(points))
            pieces = np.where(attempt == len(points), -1, attempt) if middle_here else attempt
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
            if job.band is not None:
                # Kein Mantel — dann werden die zwei Ringe gedeckelt wie bisher.
                jobs.extend(_FillJob(loop=rim, rims=(rim,)) for rim in job.rims)
                continue
            blocked += 1
            continue
        pieces = chosen
        origins: list[int] = []
        # Jede Seite zählt: Nach dem ersten Ohr beginnt ein Dreieck oft an
        # einer neuen Diagonale. Die bisherige erste-Kante-Abfrage gab ihm
        # Slot 0 und die Farbe des ersten, womöglich ganz anderen Bauteils.
        #
        # **Die eigene Randkante vor der geerbten Diagonale** (Durchsicht
        # 24.09.2026): Eine Diagonale erbt den Slot ihres ersten Dreiecks, und
        # stand sie vorn, gewann sie gegen die Randkante daneben — an einem
        # zweifarbigen Loch trugen vier von sechzehn Fülldreiecken einen Slot,
        # den keine ihrer Randkanten trug, eine Farbnaht quer durch den Deckel.
        # Liegen an einem Dreieck zwei Randkanten verschiedener Nachbarn, gilt
        # die längere.
        first_rim = job.rims[0]
        fallback = neighbour_of[(min(first_rim[0], first_rim[1]), max(first_rim[0], first_rim[1]))]
        inherited: dict[tuple[int, int], int] = {}
        for piece in pieces.tolist():
            edges = [
                (
                    min(piece[index], piece[(index + 1) % 3]),
                    max(piece[index], piece[(index + 1) % 3]),
                )
                for index in range(3)
            ]
            # Randkanten verbinden immer zwei Ringecken, nie die Fächermitte.
            own = [edge for edge in edges if edge in neighbour_of]
            if own:
                longest = max(
                    own,
                    key=lambda edge: math.dist(points[edge[0]].tolist(), points[edge[1]].tolist()),
                )
                neighbour = neighbour_of[longest]
            else:
                neighbour = next((inherited[edge] for edge in edges if edge in inherited), fallback)
            origins.append(neighbour)
            for edge in edges:
                if edge not in neighbour_of:
                    inherited.setdefault(edge, neighbour)
        records.append(
            _RingFill(
                pieces=pieces,
                origins=tuple(origins),
                middle=centre if needs_middle else None,
                wide=wide_here,
                spanned=spanned,
                centre=centre,
                edges=sum(len(rim) for rim in job.rims),
                rim_keys=rim_keys,
            )
        )

    if not records:
        return _Filled(mesh, kept=tuple(kept))

    patched = _assembled(mesh, records, slots)
    owners = np.repeat(
        np.arange(len(records), dtype=np.int64), [len(record.pieces) for record in records]
    )
    flat = _flat_fills(patched, len(body.faces), owners)
    flat_edges = sum(records[index].edges for index in flat)
    flat_area = sum(records[index].spanned for index in flat)
    flat_rings = tuple((records[index].rim_keys, records[index].spanned) for index in sorted(flat))
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
        flat=flat_rings,
        widest=None
        if widest is None
        else (float(widest.centre[0]), float(widest.centre[1]), float(widest.centre[2])),
        widest_span=0.0 if widest is None else widest.spanned,
        kept=tuple(kept),
    )


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
    count = len(body.faces)
    keys, first_row = np.unique(table.inverse[rows] * count + rows // 3, return_index=True)
    edges, faces, rows = keys // count, keys % count, rows[first_row]
    # **Welche zwei bleiben** (Durchsicht 24.09.2026). Bis dahin fiel je Kante
    # die kleinste Fläche, und zwei Fälle gingen daran verloren: Eine Flosse
    # — ein Dreieck, das an einer Würfelkante hängt und sonst frei in der Luft
    # steht — war größer als die Würfelfläche daneben, also fiel die Wand, und
    # der Würfel verlor ein Achtel seines Volumens. Und wo sich zwei Schalen an
    # einer Naht berühren, blieben oft zwei Flächen, die die Kante gleich herum
    # laufen; das Netz war danach nicht mehr einheitlich auszurichten.
    # Bleiben darf deshalb zuerst, was nicht halb offen hängt (weniger
    # Randkanten), dann das Größere; und die zweite Fläche läuft die Kante
    # gegen die erste, wo es eine solche gibt.
    loose = (table.counts[table.inverse] == 1).reshape(-1, 3).sum(axis=1)[faces]
    directed = np.asarray(body.edges, dtype=np.int64)[rows]
    forward = directed[:, 0] < directed[:, 1]
    order = np.lexsort((faces, -stable_areas(body, faces), loose, edges))
    edges, faces, forward = edges[order], faces[order], forward[order]
    starts = np.flatnonzero(np.r_[True, edges[1:] != edges[:-1]])
    ends = np.r_[starts[1:], len(edges)]
    dropped: list[int] = []
    for start, end in zip(starts.tolist(), ends.tolist(), strict=True):
        partner = next(
            (index for index in range(start + 1, end) if forward[index] != forward[start]),
            start + 1,
        )
        dropped.extend(int(faces[index]) for index in range(start + 1, end) if index != partner)
    doomed = np.unique(np.asarray(dropped, dtype=np.int64))
    if not len(doomed):
        return mesh, 0

    keep = np.ones(len(body.faces), dtype=bool)
    keep[doomed] = False
    trimmed = without_faces(body, keep)
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


def _filled_rounds(
    mesh: MeshData, cancelled: CancelToken | None = None, *, keep_wide: bool = False
) -> _Filled:
    """Der Ringfüller in Runden, bis kein Ring mehr aufgeht (:data:`FILL_ROUNDS`).

    Gezählt wird über alle Runden; was ohne Dicke oder auf Wunsch offen blieb,
    sagt die letzte — diese Ringe kommen jede Runde wieder und bleiben jede
    Runde offen.
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
        last = _fill_loops(working, cancelled, keep_wide=keep_wide)
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
        flat=last.flat,
        widest=widest,
        widest_span=widest_span,
        kept=last.kept,
    )


def _kept_still_open(
    mesh: MeshData, filled: _Filled
) -> tuple[int, int, tuple[float, float, float] | None]:
    """Wie viele der auf Wunsch offen gelassenen Öffnungen am Endstand offen sind.

    Zurück kommen die Zahl der Öffnungen, ihre Randkanten und die Mitte der
    größten — dieselbe Bilanz am Endstand wie bei :func:`_flat_still_open`.
    """
    if not filled.kept:
        return 0, 0, None
    points = np.asarray(mesh.raw.vertices, dtype=np.float64)
    rows = _edge_table(mesh).rows(1)
    pairs = np.asarray(mesh.raw.edges, dtype=np.int64)[rows]
    open_keys = {_edge_key(points[first], points[second]) for first, second in pairs.tolist()}
    still = [entry for entry in filled.kept if entry[0] and entry[0] <= open_keys]
    if not still:
        return 0, 0, None
    widest = max(still, key=lambda entry: entry[1])[2]
    return len(still), sum(len(entry[0]) for entry in still), (widest[0], widest[1], widest[2])


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


def _filled_with_count(mesh: MeshData) -> tuple[MeshData, bool, int]:
    """Wie :func:`fill_holes` ohne Vernähen, aber mit der Zahl der großen
    Öffnungen für den Bericht."""
    filled = _filled_rounds(mesh)
    return filled.mesh, filled.closed > 0, filled.wide


def fill_holes(mesh: MeshData, stitch: bool = True) -> tuple[MeshData, bool]:
    """Schließt offene Kanten — über den eigenen Ringfüller, in der Reihenfolge
    von :func:`_fill_loops`: Band, Fläche mit Löchern, glatteste
    Triangulierung, Ohren, Fächer. Auch eine fehlende Wand kommt so zurück;
    eine Fläche ohne Dicke bleibt offen (RM-224: Hier stand bis zum
    25.09.2026 „nur kleine Löcher", aus der Zeit von trimeshs Füller).

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

    **Nahe an jeder Schale, nicht am Ursprung** (:func:`_shell_volumes`,
    Review 25.09.2026). Hier stand dieselbe Summe über den Ursprung, die
    Befund B16 an den anderen Stellen ersetzt hat: Zehn Meter vom Ursprung
    bestand das Volumen einer Haut aus Rundung, lag über ``EPS_GEOM``, und die
    Haut blieb stehen.
    """
    pieces = face_components(mesh.raw)
    if len(pieces) <= 1:
        return mesh, 0
    labels = np.empty(len(mesh.raw.faces), dtype=np.int64)
    for index, piece in enumerate(pieces):
        labels[piece] = index
    volumes = _shell_volumes(mesh.raw, labels, len(pieces))
    keep = [
        piece
        for piece, volume in zip(pieces, volumes.tolist(), strict=True)
        if abs(volume) > EPS_GEOM
    ]
    if len(keep) == len(pieces) or not keep:
        return mesh, 0

    mask = np.zeros(len(mesh.raw.faces), dtype=bool)
    for piece in keep:
        mask[piece] = True
    body = without_faces(mesh.raw, mask)
    slots = (
        tuple(slot for slot, kept in zip(mesh.slots, mask, strict=True) if kept)
        if mesh.slots
        else ()
    )
    return MeshData.of(body, slots=slots), len(pieces) - len(keep)


def remove_open_splinters(
    mesh: MeshData, share: float = SMALL_COMPONENT_SHARE
) -> tuple[MeshData, int]:
    """Wirft lose, offene Splitter — Teile, die kein Loch haben, sondern keines
    schließen können.

    **Ein Splitter ist kein Blatt** (Durchsicht 24.09.2026). Ein einzelnes
    Dreieck neben einer Figur schloss die Lochfüllung bis dahin mit seiner
    eigenen Rückseite — eine Tasche ohne Volumen, die der Bericht danach als
    Kleinstteil führte. Seit eine Fläche ohne Dicke offen bleibt (Entscheidung
    Robert), bliebe der Splitter offen, und jede Boolesche Operation daran
    scheiterte: *Reparieren und erneut versuchen* hätte das Aushöhlen der
    erzeugten Figur aus Weg 3 nie durchgebracht. Gedruckt würde er ohnehin
    nicht. Was als Fläche zählt, entscheidet dieselbe Grenze wie bei den
    Kleinstteilen, gegen das größte Teil gemessen; ein Blatt darüber bleibt und
    bekommt seinen Befund. Geschlossene Teile fasst die Funktion nie an.
    """
    pieces = face_components(mesh.raw)
    if len(pieces) <= 1:
        return mesh, 0
    open_faces = np.zeros(len(mesh.raw.faces), dtype=bool)
    open_faces[_edge_table(mesh).rows(1) // 3] = True
    areas = [float(mesh.raw.area_faces[piece].sum()) for piece in pieces]
    largest = max(areas)
    doomed = [
        piece
        for piece, area in zip(pieces, areas, strict=True)
        if area < largest * share and bool(open_faces[piece].any())
    ]
    if not doomed:
        return mesh, 0
    mask = np.ones(len(mesh.raw.faces), dtype=bool)
    for piece in doomed:
        mask[piece] = False
    body = without_faces(mesh.raw, mask)
    slots = (
        tuple(slot for slot, kept in zip(mesh.slots, mask, strict=True) if kept)
        if mesh.slots
        else ()
    )
    return MeshData.of(body, slots=slots), len(doomed)


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

    mask = np.zeros(len(mesh.raw.faces), dtype=bool)
    for piece in keep:
        mask[piece] = True
    body = without_faces(mesh.raw, mask)
    slots = (
        tuple(slot for slot, kept in zip(mesh.slots, mask, strict=True) if kept)
        if mesh.slots
        else ()
    )
    return MeshData.of(body, slots=slots), len(pieces) - len(keep)


#: Wie viele genaue Paarprüfungen die Durchdringungssuche mindestens bezahlt
#: — rund zwei Mikrosekunden je Prüfung. Gezählt wird nach dem Achsenfilter;
#: ein Paar, das die Trennprüfung davor verwirft, kostet einen Bruchteil
#: (``intersections.SEPARATION_COST``).
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
#: Splitterdreiecke trägt (Besenhalter: 54 je Dreieck), endete bis zur
#: Trennprüfung (RM-244) nach dem Sockel von zwei Millionen mit einem Hinweis;
#: seither trennt sie dort 92 Prozent der Paare, und die Suche kommt nach
#: fünf Sekunden ans Ende. Das
#: Fünfhundertfache, das hier einen Nachmittag stand, ließ die Netzfehlerkarte
#: am Besenhalter 8 und am Spiderman 12 Sekunden rechnen.
INTERSECTION_PAIRS_PER_TRIANGLE: Final = 12


def intersection_budget(triangles: int) -> int:
    """Wie viele genaue Paarprüfungen die Durchdringungssuche an diesem Netz bezahlt."""
    return max(MAX_INTERSECTION_PAIRS, INTERSECTION_PAIRS_PER_TRIANGLE * triangles)


def self_intersecting_faces(
    mesh: MeshData, cancelled: CancelToken | None = None
) -> tuple[int, ...]:
    """Belegte Durchdringungen; für Entwarnungen auch den Prüfstatus lesen."""
    return self_intersection_check(mesh, cancelled)[0]


def crossings_of(
    mesh: MeshData,
    cancelled: CancelToken | None = None,
    progress: Callable[[float], None] | None = None,
    *,
    budget: int | None = None,
) -> Crossings:
    """Die Paare, die sich schneiden — einmal je Netz, im Cache des Netzes.

    **Reparatur, Vorschau und Netzfehlerkarte fragen dasselbe Netz** (Befund
    B11 der Durchsicht 24.09.2026): Die Suche kostet am Drachen 27 Sekunden,
    und jede Stelle rechnete sie für sich. Der Merker verfällt mit der
    Geometrie wie die Kantentabelle; ein Ergebnis mit kleinerem Budget gilt nur,
    wenn es vollständig war. ``budget`` weicht nur für die Netzfehlerkarte von
    :func:`intersection_budget` ab: Sie ist eine Anzeige mit drei Sekunden aus
    §31 und zeigt Ungeprüftes als unbekannt.
    """
    from app.core.geom.intersections import crossing_face_pairs

    body = mesh.raw
    if budget is None:
        budget = intersection_budget(len(body.faces))
    cache = getattr(body, "_cache", None)
    if cache is not None:
        cache.verify()
        # ``in`` und Index, nicht ``get``: trimeshs Cache kennt kein ``get``.
        if "solidon_crossings" in cache:
            known_budget, known = cache["solidon_crossings"]
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


def self_intersection_check(
    mesh: MeshData, cancelled: CancelToken | None = None
) -> tuple[tuple[int, ...], bool]:
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

    Die Suche deckelt sich an :func:`intersection_budget` Kandidatenpaaren;
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


def _intersections_resolvable(mesh: MeshData, crossings: Crossings | None = None) -> str | None:
    """Warum sich die Überschneidungen hier nicht auflösen lassen — ``None``, wenn doch.

    Dieselbe Vorprüfung wie :func:`resolve_self_intersections`, damit der
    Bericht nur zum Auflösen rät, wo es tragen kann: ``"open"`` (offen oder
    verzweigt), ``"winding"`` (Außenseiten zeigen gegeneinander),
    ``"inverted"`` (innen und außen vertauscht), ``"flat"`` (kein Volumen),
    ``"self"`` (eine Schale kreuzt sich selbst, :func:`_crossing_shape`),
    ``"cavity"`` (eine Innenschale, deren Zuordnung nicht belegt ist).
    **Verkehrt ist nicht flach** (Review R21): Ein umgestülpter Körper hieß
    „ohne Volumen", und dafür gab es keinen Befund.
    """
    if not mesh.is_watertight:
        return "open"
    if not mesh.raw.is_winding_consistent:
        return "winding"
    volume = signed_volume(mesh.raw)
    if abs(volume) <= EPS_GEOM * mesh.area:
        return "flat"
    if volume < 0.0:
        return "inverted"
    if (
        crossings is not None
        and len(crossings.first)
        and _crossing_shape(mesh, crossings) == "self"
    ):
        return "self"
    for faces in face_components(mesh.raw):
        piece = MeshData.of(
            cast(trimesh.Trimesh, mesh.raw.submesh([faces], append=True, repair=False))
        )
        if not _has_volume(piece):
            return "cavity"
    return None


def _has_volume(mesh: MeshData) -> bool:
    """Dichtheit, Wicklung und positives Volumen — nahe am Körper gerechnet (B16)."""
    return mesh.is_watertight and mesh.raw.is_winding_consistent and signed_volume(mesh.raw) > 0.0


def resolve_self_intersections(
    mesh: MeshData,
    cancelled: CancelToken | None = None,
    *,
    checked_faces: tuple[int, ...] | None = None,
    budget: int | None = None,
) -> tuple[MeshData, bool]:
    """Überlappende positive Schalen vereinigen und das Ergebnis nachprüfen.

    Die Selbstvereinigung des bereits durchdrungenen Gesamtnetzes schnitt
    das gemeinsame Volumen heraus. Getrennte Außenhüllen werden deshalb als
    getrennte Operanden an denselben Float64-Kern wie reguläre Boolesche
    Operationen gegeben. Innenschalen bleiben unangetastet: Ihre Zuordnung
    zu überlappenden Außenhüllen ist damit nicht belegt.

    Nur die direkte Stufe ist erlaubt. Bleiben Schnitte oder ist die
    Nachprüfung unvollständig, kommt der unveränderte Eingang zurück.
    ``checked_faces`` ist ohne Wirkung und bleibt für ältere Aufrufer: Die
    Prüfung desselben Netzes merkt sich das Netz selbst (:func:`crossings_of`).

    ``budget`` ist das Budget, mit dem der Aufrufer schon gesucht hat
    (:func:`crossings_of`). **Ohne es suchte das Auflösen ein zweites Mal**
    (Review 25.09.2026): Über der Kartengrenze hält sich die Diagnose an den
    Sockel, ihre unvollständige Antwort galt für das mitwachsende Budget
    nicht, und die volle Suche, die der Sockel sparen sollte, lief doch.

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
    crossings = crossings_of(mesh, cancelled, budget=budget)
    if not len(crossings.first) or _crossing_shape(mesh, crossings) == "self":
        return mesh, False
    pieces = [
        MeshData.of(cast(trimesh.Trimesh, mesh.raw.submesh([faces], append=True, repair=False)))
        for faces in face_components(mesh.raw)
    ]
    if not all(_has_volume(piece) for piece in pieces):
        return mesh, False
    operands = pieces if len(pieces) > 1 else [mesh, mesh]
    try:
        rebuilt = boolean("union", operands, stages=("direct",), cancelled=cancelled).mesh
    except PROGRAMMING_ERRORS:
        raise
    except OperationCancelled:
        raise
    except Exception as problem:  # pragma: no cover - kernspezifisch
        _log.warning("could not resolve self-intersections: %s", problem)
        return mesh, False
    if not _has_volume(rebuilt):
        return mesh, False
    if _still_crosses(mesh, crossings, rebuilt, cancelled):
        return mesh, False
    # **Die Farben reisen mit, wie die Slots.** Der Kern baut das Netz neu, und
    # ein neu gebautes ``trimesh.Trimesh`` hat keine Flächenfarben — ein
    # erzeugter Körper kommt aber farbig aus dem Generator, und *Farben zu
    # Filamenten* liest genau diese Werte (§20). Bis zum 22.09.2026 fiel das
    # nicht auf, weil dieser Schritt an einem offenen Netz gar nicht lief;
    # seit die Kette auch fehlende Wände schließt, läuft er — und aus zwei
    # Filamenten wurde eines. Zugeordnet wird über die nächste alte Fläche,
    # genau wie ``transfer`` es für die Slots tut.
    resolved = transfer(rebuilt, [mesh])
    _carried_colours(mesh.raw, resolved.raw, _nearest_old_face(mesh.raw, resolved.raw))
    return resolved, True


def _still_crosses(
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
    wide_holes: bool = True,
    small_components: bool = False,
    self_intersections: bool = False,
    inspect_intersections: bool = False,
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
) -> RepairResult:
    """Führt die gewünschten Schritte in der Reihenfolge aus, die jeden
    einzelnen billiger macht.

    ``inspect_intersections`` ergänzt die Diagnose am ausdrücklichen
    Reparaturschritt. Die automatische Importaufbereitung schließt nur die
    offenen Stellen und bietet keine Einstellungen dieses Schritts an.
    ``self_intersections`` prüft auch ohne den Diagnoseschalter.
    ``wide_holes=False`` schließt nur die kleinen Löcher und lässt die großen
    Öffnungen offen (*Offen lassen*, RM-241); der Bericht sagt, was offen
    blieb, mit Ort und dem Weg zur Wandstärke.

    **Die Sätze sprechen die Wörter des Kunden** (Durchsicht 24.09.2026):
    Loch, Lücke, leere und doppelte Dreiecke, überzählige Flächen,
    Außenseiten, Überschneidungen — nicht Kante, Naht, entartet, verzweigt
    oder Selbstdurchdringung. Gezählt werden Stellen, nicht Randkanten: Ein
    Rohrende sind 48 Kanten und eine offene Stelle.
    """
    result = RepairResult(mesh=mesh)
    if cancelled is not None:
        cancelled.raise_if_cancelled()

    if weld:
        candidate, removed = merge_vertices(result.mesh)
        # Dieselbe Zusicherung wie beim Import: nahe Punkte können zu zwei
        # getrennten Schalen gehören. Das Zusammenlegen darf deren Kanten
        # nicht zu nichtmannigfaltigen Verbindungen machen.
        if removed and _tears_it_further(result.mesh, candidate):
            # **Was stehen bleibt, ist keine Zeile im Bericht** (Bedienweg A4,
            # 25.09.2026): Geschehen ist nichts, und der Kunde kann nichts tun —
            # am Korpus ``F:\3D Dateien`` stand der Satz an 41 beziehungsweise 23
            # von 485 Körpern. Das Protokoll behält ihn für den Support.
            _log.info("weld skipped: merging %d points would tear the mesh", removed)
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
                    message=_("Doppelte Dreiecke wurden entfernt."),
                    values={"removed": doubled},
                )
            )

        candidate, removed = remove_degenerate_faces(result.mesh)
        # Auch ein flaches Dreieck kann zwei Nachbarflächen topologisch
        # verbinden. Ein geschlossener Eingang bleibt einschließlich seiner
        # Materialzuweisungen erhalten, wenn das Entfernen ihn öffnen würde.
        if removed and _tears_it_further(result.mesh, candidate):
            # **Was stehen bleibt, ist keine Zeile im Bericht** (Bedienweg A4,
            # 25.09.2026): Geschehen ist nichts, und der Kunde kann nichts tun —
            # am Korpus ``F:\3D Dateien`` stand der Satz an 41 beziehungsweise 23
            # von 485 Körpern. Das Protokoll behält ihn für den Support.
            _log.info("degenerate kept: removing %d triangles would tear the mesh", removed)
        elif removed:
            result.mesh = candidate
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.degenerate_removed",
                    severity="info",
                    message=_("Leere Dreiecke wurden entfernt."),
                    values={"removed": removed},
                )
            )

    if small_components:
        result.mesh, dropped = remove_small_components(result.mesh)
        if dropped:
            result.changed = True
            # Ein Hinweis und keine Warnung: Der Kunde hat genau das verlangt,
            # und Strg+Z holt die Teile zurück. Die Teilezahl danach reist mit,
            # damit „besteht aus mehreren Teilen" am Endstand fallen kann.
            result.findings.append(
                Finding(
                    code="repair.components_removed",
                    severity="info",
                    message=_("{removed} Kleinstteile wurden entfernt.", removed=dropped)
                    if dropped > 1
                    else _("Ein Kleinstteil wurde entfernt."),
                    values={"removed": dropped},
                )
            )

    filled = _Filled(result.mesh)
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
                        "Überzählige Flächen an {edges} Kanten wurden entfernt.",
                        edges=unbranched,
                    )
                    if unbranched > 1
                    else _("Eine überzählige Fläche an einer Kante wurde entfernt."),
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
                    message=_("Lücken an Nähten wurden geschlossen."),
                    values={"seams": seams},
                )
            )

        # **Gezählt wird erst nach dem Vernähen.** Vorher gezählt, schrieb die
        # Meldung die vernähten Kanten dem Löcherschließen zu. Die Naht hat
        # ihre eigene Zeile darüber. `_filled_rounds` vernäht nicht noch
        # einmal — es erneut zu zahlen war der gemessene Faktor 2,1.
        open_before = open_edge_count(result.mesh)
        filled = _filled_rounds(result.mesh, cancelled, keep_wide=not wide_holes)
        result.mesh = filled.mesh
        open_after = open_edge_count(result.mesh)
        if filled.wide:
            # **Eine große Öffnung wird geschlossen und gesagt** — mit dem Ort
            # der größten, damit der Klick auf die Zeile dorthin fliegt, und
            # mit dem Rückweg: Wer die Fläche nicht wollte, lässt den Schritt
            # ohne Lochfüllen rechnen (Entscheidung Robert, 24.09.2026).
            result.findings.append(
                Finding(
                    code="repair.wide_hole_filled",
                    severity="warning",
                    message=_(
                        "{walls} große Öffnungen wurden mit neuen Flächen geschlossen.",
                        walls=filled.wide,
                    )
                    if filled.wide > 1
                    else _("Eine große Öffnung wurde mit einer neuen Fläche geschlossen."),
                    values={"walls": filled.wide},
                    location=filled.widest,
                    suggestions=(SHOW_LOCATION, LEAVE_OPEN),
                )
            )
        if filled.closed:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.holes_filled",
                    severity="info",
                    message=_("{holes} Löcher wurden geschlossen.", holes=filled.closed)
                    if filled.closed > 1
                    else _("Ein Loch wurde geschlossen."),
                    values={"holes": filled.closed, "before": open_before, "after": open_after},
                )
            )
        # Was danach noch als winziges offenes Teil dasteht, ist ein Splitter
        # und kein Loch (:func:`remove_open_splinters`).
        result.mesh, splinters = remove_open_splinters(result.mesh)
        if splinters:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.splinters_removed",
                    severity="info",
                    message=_("{removed} lose Splitter wurden entfernt.", removed=splinters)
                    if splinters > 1
                    else _("Ein loser Splitter wurde entfernt."),
                    values={"removed": splinters},
                )
            )

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if normals:
        result.mesh, flipped = unify_normals(result.mesh)
        # **Angeglichen heißt einheitlich — sonst sagt es der Bericht.** Wo
        # zwei Schalen sich an einer Naht berühren, bleiben Kanten, die beide
        # Nachbarn gleich herum laufen; ``fix_winding`` kann sie nicht richten,
        # und ein solcher Körper ist für jede Boolesche Operation kein Volumen.
        # „Angeglichen" steht dann nicht daneben: Beide Sätze zugleich
        # widersprachen einander (Durchsicht 24.09.2026, Röhre mit
        # gespiegelter Naht).
        crossed = _crossed_edge_count(result.mesh)
        if flipped:
            result.changed = True
        if flipped and not crossed:
            result.findings.append(
                Finding(
                    code="repair.normals_flipped",
                    severity="info",
                    message=_("Die Außenseiten wurden angeglichen."),
                )
            )
        if crossed:
            result.findings.append(
                Finding(
                    code="repair.normals_inconsistent",
                    severity="warning",
                    message=_(
                        "An {edges} Kanten zeigen die Außenseiten gegeneinander.", edges=crossed
                    )
                    if crossed > 1
                    else _("An einer Kante zeigen die Außenseiten gegeneinander."),
                    values={"edges": crossed},
                    suggestions=(SHOW_LOCATIONS,),
                )
            )

    # **Zuletzt, und das ist der Fund.** Der Schritt stand vor dem
    # Löcherschließen und konnte dort nie arbeiten: Er braucht ein Volumen, und
    # eines wird das Netz erst durch Schließen *und* Außenseiten angleichen.
    if self_intersections or inspect_intersections:
        _intersection_findings(
            result, self_intersections=self_intersections, cancelled=cancelled, progress=progress
        )

    # **Ein Teil im Teil wird gemeldet, nicht geraten** (Befund B9 der
    # Durchsicht 24.09.2026, :func:`parts_inside_parts`). Erst hier: Das
    # Vereinigen darüber kann es aufgelöst haben.
    if normals and result.mesh.is_watertight and result.mesh.component_count > 1:
        nested = parts_inside_parts(result.mesh.raw)
        if nested:
            result.findings.append(part_inside_finding(nested, result.mesh.component_count))

    # **Eine Fläche ohne Dicke ist kein Loch** (Entscheidung Robert,
    # 24.09.2026): Ihr Rand bleibt offen, und der Bericht sagt, was hilft.
    # Ein loses Splitterdreieck ist dagegen ein Kleinstteil und kein
    # Befund dieser Art — gemeldet wird erst ab dem Anteil, ab dem ein
    # Einzelteil nicht mehr „sehr klein" heißt.
    total_area = result.mesh.area
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
                suggestions=(GIVE_THICKNESS, SHOW_LOCATIONS),
            )
        )

    # **Was auf Wunsch offen blieb, ist kein Fehlschlag** (RM-241): Der Satz
    # „ließen sich nicht sicher schließen" wäre falsch, denn niemand hat es
    # versucht. Offen ist das Modell trotzdem, und gedruckt wird eine offene
    # Fläche erst mit einer Wand — deshalb *Dicke geben* vorn.
    kept_openings, kept_edges, kept_at = _kept_still_open(result.mesh, filled)
    if kept_openings:
        result.findings.append(
            Finding(
                code="repair.wide_hole_kept",
                severity="warning",
                message=_("{openings} große Öffnungen bleiben offen.", openings=kept_openings)
                if kept_openings > 1
                else _("Eine große Öffnung bleibt offen."),
                values={"openings": kept_openings, "open_edges": kept_edges},
                location=kept_at,
                suggestions=(GIVE_THICKNESS, SHOW_LOCATIONS),
            )
        )

    open_edges = open_edge_count(result.mesh)
    branching = branching_edge_count(result.mesh)
    if sheet:
        # Die Ränder der Fläche ohne Dicke hat der Befund darüber schon genannt.
        open_edges = max(0, open_edges - flat_edges)
    # Ebenso die Ränder, die auf Wunsch offen blieben.
    open_edges = max(0, open_edges - kept_edges)
    if open_edges or branching:
        # **Zwei Gründe, und sie verlangen verschiedene Sätze.** „Offen" stimmt
        # für Ränder; ein Netz kann aber null davon haben und trotzdem kein
        # Volumen einschließen, weil an einer Kante drei Flächen zusammenlaufen
        # (Waschschüssel, 16.09.2026). Der frühere Folgesatz schickte den
        # Kunden im Kreis; die Oberfläche führt von hier zu den Stellen (§2.7).
        places = _open_places(result.mesh) if open_edges else 0
        result.findings.append(
            Finding(
                code="repair.still_branching" if branching else "repair.still_open",
                severity="warning",
                message=_still_open_text(places, open_edges, branching),
                values={"open_edges": open_edges, "branching_edges": branching, "holes": places}
                if branching
                else {"open_edges": open_edges, "holes": places},
            )
        )
    return result


def _still_open_text(places: int, open_edges: int, branching: int) -> Any:
    """Der Satz über das, was die Reparatur nicht sicher beheben konnte."""
    if branching and open_edges:
        return _(
            "Offene Stellen und überzählige Flächen an {edges} Kanten ließen sich nicht "
            "sicher beheben.",
            edges=branching,
        )
    if branching:
        return (
            _(
                "An {edges} Kanten hängen überzählige Flächen, die sich nicht sicher "
                "entfernen ließen.",
                edges=branching,
            )
            if branching > 1
            else _(
                "An einer Kante hängt eine überzählige Fläche, die sich nicht sicher "
                "entfernen ließ."
            )
        )
    if places > 1:
        return _("{holes} offene Stellen ließen sich nicht sicher schließen.", holes=places)
    if places == 1:
        return _("Eine offene Stelle ließ sich nicht sicher schließen.")
    return _("Offene Stellen ließen sich nicht sicher schließen.")


def _open_places(mesh: MeshData) -> int:
    """Wie viele offene Stellen ein Netz hat — Ringe, nicht Randkanten.

    Null, wo sich die Ränder nicht zu Ringen verketten lassen; der Satz sagt
    dann „offene Stellen" ohne Zahl.
    """
    return len(_hole_rings(mesh)[1])


def crossed_edge_faces(mesh: MeshData) -> np.ndarray:
    """Die Dreiecke an Kanten, deren zwei Flächen in derselben Richtung laufen.

    Dort zeigen die Außenseiten gegeneinander. Je solcher Kante stehen beide
    Dreiecke in der Liste, in der Reihenfolge der Kanten; der Bericht zählt
    die Kanten, die Netzfehlerkarte färbt die Dreiecke.
    """
    table = _edge_table(mesh)
    rows = table.rows(2)
    if not len(rows):
        return np.zeros(0, dtype=np.int64)
    directed = np.asarray(mesh.raw.edges, dtype=np.int64)[rows]
    forward = directed[:, 0] < directed[:, 1]
    edge = table.inverse[rows]
    order = np.argsort(edge, kind="stable")
    rows, forward = rows[order], forward[order]
    # Je Kante zwei Zeilen nebeneinander; gleiche Richtung heißt verkehrt.
    wrong = forward[0::2] == forward[1::2]
    pairs = np.column_stack((rows[0::2][wrong], rows[1::2][wrong])) // 3
    return np.asarray(pairs.ravel(), dtype=np.int64)


def _crossed_edge_count(mesh: MeshData) -> int:
    """Kanten mit zwei Flächen, die beide in derselben Richtung laufen.

    ``is_winding_consistent`` sagt nur ja oder nein, der Bericht braucht die Zahl.
    """
    return len(crossed_edge_faces(mesh)) // 2


def _search_progress(progress: ProgressFn | None) -> Callable[[float], None] | None:
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
) -> None:
    """Überschneidungen suchen, wo gewünscht auflösen, und sagen, was geschah.

    **Gesagt wird nur, was es gibt.** Ohne einen Fund steht keine Zeile da —
    auch nicht „übersprungen": Ein Satz über einen Schritt, der nichts zu tun
    gehabt hätte, schickt den Kunden auf eine Suche. Und zum Auflösen geraten
    wird nur, wo es tragen kann (:func:`_intersections_resolvable`); sonst
    endete der Rat in der nächsten Warnung (Durchsicht 24.09.2026: vier von
    zwölf Körpern des Korpus). **Und jede gefundene Überschneidung hat eine
    Zeile** (Review R21): Ein Körper ohne Volumen oder verkehrt herum bekam
    keine, und danach hieß es „nichts zu reparieren".

    **Gesucht wird so weit, wie es trägt** (Review R12): Am offenen oder
    gegeneinander gewickelten Netz löst die Reparatur ohnehin nichts auf, und
    über der Kartengrenze (``perceive.maps.MAP_LIMIT_TRIANGLES``) wuchs das
    Budget mit dem Netz — am Drachen 70 s für „nichts zu tun". Dort gilt der
    Sockel von :data:`MAX_INTERSECTION_PAIRS`; was die Suche nicht erreicht,
    sagt der Hinweis „vorzeitig beendet".
    """
    from app.core.perceive.maps import MAP_LIMIT_TRIANGLES

    mesh = result.mesh
    searchable = mesh.is_watertight and mesh.raw.is_winding_consistent
    budget = (
        None
        if searchable and mesh.triangle_count <= MAP_LIMIT_TRIANGLES
        else MAX_INTERSECTION_PAIRS
    )
    crossings = crossings_of(mesh, cancelled, _search_progress(progress), budget=budget)
    found, complete = crossings.faces, crossings.complete
    if not found:
        if not complete:
            result.findings.append(
                Finding(
                    code="repair.self_intersections_incomplete",
                    severity="info",
                    message=_(
                        "Die Suche nach Überschneidungen wurde vorzeitig beendet; es kann "
                        "welche geben."
                    ),
                )
            )
        return
    blocked = _intersections_resolvable(result.mesh, crossings)
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
        # Mit demselben Budget: Sonst suchte das Auflösen über der Kartengrenze
        # ein zweites Mal, mit dem mitwachsenden Budget.
        result.mesh, rebuilt = resolve_self_intersections(result.mesh, cancelled, budget=budget)
        if rebuilt:
            result.changed = True
            result.solver = SolverInfo(strategy="direct", attempted=("direct",))
            result.findings.append(
                Finding(
                    code="repair.self_intersections",
                    severity="info",
                    message=_("Überschneidungen wurden aufgelöst."),
                    values={"parts": result.mesh.component_count},
                )
            )
            if not complete:
                # Aufgelöst ist, was gefunden war; was die Suche nicht erreicht
                # hat, bleibt ungesehen (Review R16).
                result.findings.append(
                    Finding(
                        code="repair.self_intersections_incomplete",
                        severity="info",
                        message=_(
                            "Die Suche nach Überschneidungen wurde vorzeitig beendet; es kann "
                            "weitere geben."
                        ),
                    )
                )
            return
    if blocked == "self":
        pass
    elif not self_intersections or blocked == "flat":
        result.findings.append(
            Finding(
                code="repair.self_intersections_detected",
                severity="warning",
                message=_("Teile des Modells überschneiden sich."),
                suggestions=(RESOLVE_INTERSECTIONS, SHOW_LOCATIONS)
                if blocked is None
                else (SHOW_LOCATIONS,),
            )
        )
    elif blocked in ("open", "winding", "inverted"):
        result.findings.append(
            Finding(
                code="repair.self_intersections_skipped",
                severity="warning",
                message=_(
                    "Überschneidungen lassen sich erst an einem geschlossenen Modell auflösen."
                )
                if blocked == "open"
                else _(
                    "Überschneidungen lassen sich nicht auflösen, solange Außenseiten "
                    "gegeneinander zeigen."
                )
                if blocked == "winding"
                else _(
                    "Überschneidungen lassen sich nicht auflösen, solange innen und außen "
                    "vertauscht sind."
                ),
                # Der Grund steht im Satz; als Wert stünde er als Kennung
                # („open") im Tooltip (Regel 20).
                suggestions=(SHOW_LOCATIONS,),
            )
        )
    else:
        # Übrig ist der Fall, den die Vereinigung nicht sicher lösen konnte.
        result.findings.append(
            Finding(
                code="repair.self_intersections_unresolved",
                severity="warning",
                message=_(
                    "Die Überschneidungen ließen sich nicht sicher auflösen. Viele Slicer "
                    "drucken solche Stellen trotzdem richtig."
                ),
                suggestions=(SHOW_LOCATIONS,),
            )
        )
    if not complete:
        result.findings.append(
            Finding(
                code="repair.self_intersections_incomplete",
                severity="info",
                message=_(
                    "Die Suche nach Überschneidungen wurde vorzeitig beendet; es kann "
                    "weitere geben."
                ),
            )
        )


def _edge_table(mesh: MeshData) -> EdgeTable:
    """Die Kantenzählung eines Netzes — :func:`app.core.geom.mesh.edge_table`.

    Sie wohnt in :mod:`app.core.geom.mesh` (RM-224): Dort fragen sie auch die
    Teilezerlegung und die Dichtheit, und eine Zählung je Netz reicht für alle.

    **Eine Zählung statt einer je Frage** (Review 22.09.2026). Offene Ränder,
    Verzweigungen, Randringe und Sanduhren fragten je ``group_rows`` über alle
    Kanten, die Reparatur beim Import eines offenen Netzes achtzehnmal: An
    der Piratenschiff-Baugruppe (1,2 Millionen Dreiecke) kosteten diese
    Zählungen allein elf der fünfundzwanzig Sekunden.
    """
    return edge_table(mesh.raw)


def is_closed(body: trimesh.Trimesh) -> bool:
    """``is_watertight`` über die Kantenzählung — die Tabelle bleibt für die Reparatur liegen.

    Der Import fragt ein Netz zuerst, ob es dicht ist, und repariert es danach;
    über trimesh gefragt wäre das eine Gruppierung aller Kanten mehr (RM-224).
    """
    if len(body.faces):
        edge_table(body)
    return bool(body.is_watertight)


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
