"""Die Materialslots durch eine Operation hindurch behalten (Bauplan §20).

„Boolesche Operationen dürfen die Slot-Zuweisung nicht verlieren." Sie
verlieren sie aber — eine Boolesche Op baut die Dreiecke neu, und die, die
herauskommen, sind nicht die, die hineingingen. Also wird die Zuweisung
übertragen: jedes neue Dreieck fragt, auf welchem der alten es sitzt, und nimmt
dessen Slot.

Nächste Fläche, nicht nächster Eckpunkt: ein Dreieck sitzt auf einer
Oberfläche, und die Oberfläche ist es, die die Farbe trägt. Neue Schnittflächen
gehören zu keiner der alten Oberflächen — sie bekommen den Slot, den die
Operation ihnen zuweisen soll, und per Vorgabe ist das der des Körpers, der
geschnitten wird.

Welche Oberflächen als „alt" zählen, entscheidet der Aufrufer, und das zählt:
ein Körper, den die Operation entfernt hat, ist keine Farbquelle — wie nah
seine ehemalige Haut auch an der neuen liegt.

**Nach der Voxelstufe läuft die Übertragung immer** (§20). Diese Stufe ersetzt
die Vernetzung vollständig — alles von vorher Behaltene wäre Unsinn, der
zufällig die richtige Länge hat.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import numpy as np

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData, as_mesh_data, refined_units, remember_refined_units
from app.core.log import get_logger
from app.core.types import CancelToken, Mesh

_log = get_logger(__name__)

#: Wie weit ein neues Dreieck von einer alten Oberfläche sitzen darf und noch
#: als auf ihr liegend zählt, relativ zur Modelldiagonale. Darüber hinaus ist
#: es eine Schnittfläche.
NEAR_LIMIT = 0.002

#: Slot, den eine Fläche bekommt, die zu keiner Oberfläche der Eingaben
#: gehört.
DEFAULT_CUT_SLOT = 0


def transfer(
    result: MeshData,
    sources: list[MeshData],
    *,
    cut_slot: int = DEFAULT_CUT_SLOT,
    tolerance: float | None = None,
) -> MeshData:
    """Gibt jedem Dreieck von ``result`` den Slot der Oberfläche, auf der es liegt.

    Ohne Slots irgendwo in den Eingaben wird nichts übertragen und nichts
    erfunden: ein Körper mit einem Material bleibt ein Körper mit einem
    Material.

    ``tolerance`` ist, wie weit ein Dreieck von einer alten Oberfläche sitzen
    darf und noch als auf ihr liegend zählt. Sie muss der Stufe folgen, die das
    Netz erzeugt hat: ein Voxel-Ergebnis ist überall um einen halben Voxel
    getreppt, und mit der Toleranz einer exakten Booleschen Op gemessen verlöre
    es seine Farbe an die eigene Treppe.
    """
    if not any(mesh.slots for mesh in sources):
        return result
    body = result.raw
    if not len(body.faces):
        return result

    centres = np.asarray(body.triangles_center, dtype=float)
    slots = np.full(len(centres), cut_slot, dtype=np.int32)
    distance = np.full(len(centres), np.inf)
    limit = tolerance if tolerance is not None else max(result.bounds.diagonal, 1.0) * NEAR_LIMIT

    index = _candidates(sources, centres, limit, cut_slot)
    if index.size:
        points = centres[index]
        for mesh in sources:
            if not mesh.slots:
                continue
            found, offset = _nearest(mesh, points)
            closer = offset < distance[index]
            slots[index[closer]] = found[closer]
            distance[index[closer]] = offset[closer]

    slots[distance > limit] = cut_slot

    carried = int(np.count_nonzero(distance <= limit))
    _log.info("carried %d of %d face slots", carried, len(slots))
    return MeshData(raw=body, slots=tuple(int(entry) for entry in slots))


def _candidates(
    sources: list[MeshData], centres: np.ndarray, limit: float, cut_slot: int
) -> np.ndarray:
    """Die Dreiecke, für die sich die Suche überhaupt lohnen kann.

    Ein Dreieck bekommt am Ende entweder den Slot seiner nächsten Quelle oder
    — wenn keine innerhalb ``limit`` liegt — den Schnittslot. Liegt es zu
    keiner Quelle nah, die einen *anderen* Slot als den Schnittslot trägt,
    steht sein Ergebnis damit schon fest: der Schnittslot. Ob eine Quelle,
    die ohnehin nur den Schnittslot trägt, näher liegt oder nicht, ändert
    daran nichts.

    Das ist keine Näherung, sondern derselbe Wert auf kürzerem Weg — und der
    kürzere Weg ist hier der ganze Unterschied. ``limit`` sind zwei Tausendstel
    der Modelldiagonale, bei der Dose aus dem Beispielprojekt also zwei Zehntel
    Millimeter; die Beschriftung darauf sind sechshundert Dreiecke neben
    vierzigtausend. Gesucht wurde trotzdem für alle vierzigtausend, gegen beide
    Quellen: sechseinhalb der siebeneinhalb Sekunden, die eine Auswertung
    kostete, und einhundertdreizehntausend Anfragen an einen ``rtree``-Index,
    der auf dieser Maschine in etwa jedem zwanzigsten Lauf danebengriff —
    inzwischen ist er ganz ersetzt (:func:`app.core.geom.mesh.on_surface`),
    und der Vorfilter bleibt trotzdem: weniger fragen ist weiter schneller.

    Gemessen wird gegen den Hüllquader der Quelle und nicht gegen ihre
    Oberfläche: das ist genau die Frage, die ohne Index zu beantworten ist,
    und sie schließt nie etwas aus, das die Oberfläche noch erreichen würde.
    """
    coloured = [mesh for mesh in sources if mesh.slots and set(mesh.slots) != {int(cut_slot)}]
    if not coloured:
        return np.empty(0, dtype=np.intp)

    near = np.zeros(len(centres), dtype=bool)
    for mesh in coloured:
        low, high = np.asarray(mesh.raw.bounds, dtype=float)
        gap = np.maximum(np.maximum(low - centres, centres - high), 0.0)
        near |= np.sqrt((gap * gap).sum(axis=1)) <= limit
    return np.flatnonzero(near)


def _nearest(mesh: MeshData, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Für jeden Punkt: der Slot des nächsten Dreiecks, und wie weit es weg war.

    Abstand zur *Oberfläche*, nicht zum nächsten Dreiecksmittelpunkt. Eine
    Boolesche Op teilt eine große Fläche in viele kleine, und deren Mittelpunkte
    landen weit von dem der Fläche entfernt, aus der sie kamen — so gemessen
    verlöre ein Körper seine Farbe an die eigene Neuvernetzung.
    """
    from app.core.geom.mesh import on_surface

    slots = np.asarray(mesh.slots, dtype=np.int32)
    _closest, distance, triangle = on_surface(mesh.raw, points)
    return slots[triangle], distance


def carry_refined_units(result: MeshData, sources: Sequence[MeshData]) -> None:
    """Der Ursprung je Dreieck vor *Kanten verfeinern* durch eine Boolesche Operation (R1).

    ``geom.mesh.refined_units`` sagt je Dreieck, aus welchem Dreieck vor der
    Teilung es stammt, und die Erkennung zählt die Stücke eines Ursprungs als
    eines. Eine Boolesche Operation baut ein neues Netz — **aber jedes
    Dreieck, das sie nicht berührt hat, übernimmt der Kern bitgleich** (samt
    seiner drei Ecken; gemessen an ``manifold3d`` 3.5.3: 1 122 von 1 282
    Dreiecken nach einer Bohrung in einen fein geteilten Quader). An diesen
    Dreiecken hängt der Ursprung weiter; alles, was der Schnitt neu gebaut
    hat, zählt für sich (``-1``), wie am ungeteilten Netz.

    Der Weg über gleiche Ecken und nicht über die Nummern, die der Kern
    mitführen kann (``face_id``): Mit eigenen Nummern je Dreieck vernetzt der
    Kern angeschnittene Flächen anders (1 390 statt 1 282 Dreiecke am selben
    Quader), und ein Netz ohne Teilung bekäme so ein anderes Ergebnis als
    bisher. Hier bleibt die Rechnung dieselbe, und gesucht wird nur, wenn ein
    Eingang einen Ursprung trägt.

    Mehrere Eingänge mit Ursprung behalten verschiedene Nummern. Das Ergebnis
    muss frisch gebaut sein (``geom.mesh.remember_refined_units``).
    """
    body = result.raw
    carried = [(mesh.raw, refined_units(mesh.raw)) for mesh in sources]
    if not len(body.faces) or all(units is None for _raw, units in carried):
        return
    found = np.full(len(body.faces), -1, dtype=np.int64)
    offset = 0
    for raw, units in carried:
        if units is None:
            continue
        match = _same_triangles(raw, body)
        taken = (match >= 0) & (found < 0)
        own = units[match[taken]]
        found[taken] = np.where(own >= 0, own + offset, -1)
        offset += int(units.max()) + 1
    remember_refined_units(body, found)


def _same_triangles(source: Any, result: Any) -> np.ndarray:
    """Je Dreieck von ``result`` ein Dreieck von ``source`` mit denselben drei Ecken, sonst ``-1``.

    Dieselben Ecken heißt bitgleich: Zwei Punkte gelten nur dann als einer,
    wenn alle drei Koordinaten gleich sind. Beide Punktlisten werden
    gemeinsam sortiert, gleiche Orte bekommen eine Nummer, und ein Dreieck ist
    sein aufsteigend geordnetes Nummerntripel — als eine Zahl, solange drei
    Nummern in 63 Bit passen, sonst als Zeile. Gesucht wird sortiert, nicht je
    Dreieck: an 405 304 Dreiecken des geteilten Screen-Covers nach einer
    Bohrung 0,10 s, als Zeilensortierung 0,16 s (die Boolesche selbst 0,6 s;
    gemessen unter der Last der Durchsicht 0.5.1).
    """
    return _same_triangles_at(source, result, *_places(source, result))


def _places(source: Any, result: Any) -> tuple[np.ndarray, np.ndarray]:
    """Je Ecke beider Netze die Nummer ihres Orts — bitgleiche Koordinaten, dieselbe Nummer.

    Beide Punktlisten werden gemeinsam sortiert; zurück kommen die Nummern der
    Ecken von ``source`` und die von ``result``.
    """
    before = np.asarray(source.vertices, dtype=np.float64)
    after = np.asarray(result.vertices, dtype=np.float64)
    points = np.concatenate((before, after))
    order = np.lexsort((points[:, 2], points[:, 1], points[:, 0]))
    ordered = points[order]
    fresh = np.ones(len(points), dtype=bool)
    fresh[1:] = (ordered[1:] != ordered[:-1]).any(axis=1)
    place = np.empty(len(points), dtype=np.int64)
    place[order] = np.cumsum(fresh) - 1
    return place[: len(before)], place[len(before) :]


def _same_triangles_at(
    source: Any, result: Any, place_before: np.ndarray, place_after: np.ndarray
) -> np.ndarray:
    """:func:`_same_triangles` mit den Ortsnummern aus :func:`_places`."""
    old = np.sort(place_before[np.asarray(source.faces, dtype=np.int64)], axis=1)
    new = np.sort(place_after[np.asarray(result.faces, dtype=np.int64)], axis=1)
    if not len(old) or not len(new):
        return np.full(len(new), -1, dtype=np.int64)
    distinct = int(max(place_before.max(initial=-1), place_after.max(initial=-1))) + 1
    if distinct < _CODE_LIMIT:
        # Drei Nummern als eine Zahl; der stabile Sortierlauf lässt bei gleichen
        # Dreiecken im Eingang das erste vorn stehen.
        old_codes = (old[:, 0] * distinct + old[:, 1]) * distinct + old[:, 2]
        new_codes = (new[:, 0] * distinct + new[:, 1]) * distinct + new[:, 2]
        ranking = np.argsort(old_codes, kind="stable")
        ranked = old_codes[ranking]
        spot = np.minimum(np.searchsorted(ranked, new_codes), len(ranked) - 1)
        return np.where(ranked[spot] == new_codes, ranking[spot], -1)
    rows = np.concatenate((old, new))
    # Bei gleichen Ecken steht das alte Dreieck vorn: Die Herkunft sortiert mit.
    late = np.concatenate((np.zeros(len(old), dtype=np.int64), np.ones(len(new), dtype=np.int64)))
    order = np.lexsort((late, rows[:, 2], rows[:, 1], rows[:, 0]))
    ordered_rows = rows[order]
    start = np.ones(len(rows), dtype=bool)
    start[1:] = (ordered_rows[1:] != ordered_rows[:-1]).any(axis=1)
    first = np.maximum.accumulate(np.where(start, np.arange(len(rows)), 0))
    leader = order[first]
    match = np.full(len(rows), -1, dtype=np.int64)
    match[order] = np.where(leader < len(old), leader, -1)
    return match[len(old) :]


#: Bis zu wie vielen verschiedenen Punkten drei Punktnummern als eine Zahl in
#: ``int64`` passen: ``2 097 151³`` liegt knapp unter ``2⁶³``.
_CODE_LIMIT: Final = 2_097_151


def in_source_layout(result: MeshData, sources: Sequence[MeshData]) -> MeshData:
    """Das Ergebnis einer Booleschen in der Darstellung seiner Eingänge (RM-261).

    ``manifold3d`` übernimmt jedes Dreieck, das der Schnitt nicht berührt,
    mit denselben drei Ecken — **aber nicht in derselben Darstellung**: Es
    nummeriert die Ecken neu und beginnt ein Dreieck an einer anderen Ecke.
    Gemessen am Gartenschlauchhalter nach *Merkmal verschieben*: 385 522 von
    391 850 Dreiecken übernommen, davon 101 110 mit derselben Eckenfolge und
    185 387 mit derselben Normale Bit für Bit. Die Erkennung summiert in der
    Reihenfolge der Ecken und rechnet die Normale aus der Eckenfolge; an jedem
    Fleck verschoben sich deshalb die letzten Stellen, und an einer Schwelle
    kippte ein Merkmal weit weg vom Schritt (eine Verrundung 113 mm von der
    Bohrung ging in einem Kegel auf). Ein Merker über die Körpergrenze
    (``perceive.features``, :data:`~app.core.perceive.features.GEOMETRY_KEYED_ANSWERS`)
    traf so nie.

    Hier bekommt jedes übernommene Dreieck die Eckenfolge seines Vorbilds, und
    die übernommenen Ecken stehen in der Reihenfolge ihres Eingangs; neue
    Ecken folgen dahinter in der Reihenfolge des Kerns. **Die Dreiecksfolge
    bleibt die des Kerns** — an ihr hängen die Nummern der Merkmale —, und
    keine Koordinate ändert sich: Es wird nur umnummeriert und gedreht, wie
    der Eingang es vorgab. Zwischen zwei Ergebnissen des Kerns blieb die
    Darstellung auch vorher schon stehen (gemessen: jede Ecke, jede
    Eckenfolge, jede Stützpunktlesung gleich); neu ist sie ab dem ersten
    Schritt nach dem Laden. Weil der Kern danach die Darstellung des Eingangs
    liest, vernetzt er neue Schnittflächen mitunter anders als ohne sie — am
    Korpus vier bis fünf von 250 Körpern je Schritt, am
    Schraubendreherhalter vier Dreiecke mehr nach dem Versetzen einer
    Bohrung, dieselbe Form.

    Gleich heißt bitgleich (:func:`_places`). Mehrere Eingänge gelten in ihrer
    Reihenfolge; ein Dreieck, das in keiner Drehung auf seinem Vorbild liegt
    (umgekehrter Umlauf, entartet), bleibt, wie der Kern es lieferte.
    """
    body = result.raw
    faces = np.asarray(body.faces, dtype=np.int64)
    if not len(faces):
        return result
    corners = faces.copy()
    unset = np.iinfo(np.int64).max
    rank = np.full(len(body.vertices), unset, dtype=np.int64)
    taken = np.zeros(len(faces), dtype=bool)
    offset = 0
    turns = np.arange(3)
    for source in sources:
        raw = source.raw
        model = np.asarray(raw.faces, dtype=np.int64)
        if len(model):
            place_before, place_after = _places(raw, body)
            match = _same_triangles_at(raw, body, place_before, place_after)
            rows = np.flatnonzero((match >= 0) & ~taken)
            wanted = place_before[model[match[rows]]]
            given = place_after[faces[rows]]
            turn = np.full(len(rows), -1, dtype=np.int64)
            for shift in turns.tolist():
                fits = (turn < 0) & np.all(given[:, (turns + shift) % 3] == wanted, axis=1)
                turn[fits] = shift
            kept = turn >= 0
            rows, turn = rows[kept], turn[kept]
            corners[rows] = faces[rows][np.arange(len(rows))[:, None], (turns + turn[:, None]) % 3]
            np.minimum.at(rank, corners[rows].ravel(), model[match[rows]].ravel() + offset)
            taken[rows] = True
        offset += len(raw.vertices)
    if not taken.any():
        return result
    order = np.argsort(
        np.where(rank < unset, rank, offset + np.arange(len(rank), dtype=np.int64)), kind="stable"
    )
    if np.array_equal(order, np.arange(len(order))) and np.array_equal(corners, faces):
        return result
    renumbered = np.empty(len(order), dtype=np.int64)
    renumbered[order] = np.arange(len(order))
    vertices = np.asarray(body.vertices, dtype=np.float64)[order]
    return result.replacing(trimesh.Trimesh(vertices, renumbered[corners], process=False))


def with_slot(mesh: MeshData, slot: int) -> MeshData:
    """Ein Slot für den ganzen Körper — wo eine Farbe von Hand zugewiesen wird."""
    return MeshData(
        raw=mesh.raw,
        slots=tuple([int(slot)] * len(mesh.raw.faces)),
        cavity=mesh.cavity,
        cavity_open=mesh.cavity_open,
    )


def with_slots(mesh: Mesh, slots: tuple[int, ...], *, cancelled: CancelToken | None = None) -> Mesh:
    """Ändert ausschließlich Filamentattribute und erhält die Bauart des Körpers."""
    from dataclasses import replace

    from app.core.brep.kernel import Solid

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if isinstance(mesh, Solid):
        return mesh.with_triangle_slots(slots, cancelled=cancelled)
    return replace(as_mesh_data(mesh), slots=slots)


def validate_full_faces(mesh: Mesh, indices: tuple[int, ...]) -> None:
    """Exakte Teilflächen dürfen beim nächsten Vernetzen nicht heimlich wachsen."""
    from app.core.brep.kernel import Solid

    if isinstance(mesh, Solid):
        mesh.complete_faces_of_triangles(indices)


def counts(mesh: MeshData) -> dict[int, int]:
    """Wie viele Dreiecke in welchem Slot sitzen. Liest der Prüfbericht und
    der Export."""
    if not mesh.slots:
        return {0: len(mesh.raw.faces)}
    values, amounts = np.unique(np.asarray(mesh.slots), return_counts=True)
    return {int(value): int(amount) for value, amount in zip(values, amounts, strict=True)}


def used_slots(mesh: MeshData) -> tuple[int, ...]:
    return tuple(sorted(counts(mesh)))
