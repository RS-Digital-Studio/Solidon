"""Langlöcher: zwei Halbzylinder, zwei Flanken, ein Merkmal (§21.1).

**Ein Langloch ist keine Grundform.** Die Einpassung findet darin zwei
Zylinderausschnitte und nennt sie folgerichtig *Verrundungen* — an einem Netz
sind sie genau das: Bögen von 180 Grad. Gemessen an einer Platte mit einem
Langloch Ø 5 auf 20 mm Länge stehen ohne diese Datei zwei ``fillet`` im
Objektbaum und kein Loch: Der Kunde sieht zwei Rundungen, wo eine Öffnung ist,
und die Handlungen an einer Bohrung stehen an keiner von beiden.

Dieselbe Lage wie beim Gewinde, und deshalb dieselbe Bauart wie
:mod:`app.core.perceive.helix`: Was aus mehreren Einpassungen zusammenwächst,
wird hier am **Netz** gemessen und verschluckt die Formen, aus denen es
besteht. Der Unterschied zur Wendel ist, dass ein Langloch nicht aus einer
Bewegung entsteht, sondern aus einer Nachbarschaft — zwei Halbzylinder
zusammen mit den zwei ebenen Flanken zwischen ihnen, und **nur** diesen.

**Gefragt wird topologisch und nicht an einer Kennzahl.** Zwei gleich große
Verrundungen mit paralleler Achse gibt es an jeder verrundeten Kante eines
Quaders; was ein Langloch daraus macht, ist der geschlossene Mantel dazwischen.
Läuft er über etwas anderes als die zwei Flanken, ist es keines — und dann
bleiben die Verrundungen, was sie waren.

**Und ein zweiter Einstieg, für den Mantel aus einem Stück** (RM-155): Ein
knapp aufgezogenes Langloch — der Weg unter rund fünf Prozent des
Durchmessers — zerfällt der Einpassung nicht in zwei Bögen, weil seine
Flanken für die Krümmungstrennung zu schmal sind, und ein Zylinder passt auch
nicht mehr. Dann kommt der ganze Fleck als Stadion
(:class:`app.core.perceive.features.StadiumFit`), und hier wird daraus
dasselbe Merkmal. Solidon schneidet seit dem 11.09.2026 nicht mehr so knapp;
ein eingelesenes Netz kommt trotzdem dorthin.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.types import Feature, FeatureId, Vec3
from app.core.units import EPS_GEOM, positive_axis, weld_tolerance

if TYPE_CHECKING:  # pragma: no cover - nur für die Typprüfung
    from app.core.perceive.features import CylinderFit

#: Wie parallel zwei Achsen sein müssen, um dieselbe zu sein.
#:
#: **Öffentlich, weil der exakte Kern dieselbe Frage stellt**
#: (:mod:`app.core.brep.features`) — dieselben drei Toleranzen, an einer
#: Stelle hergeleitet und dort importiert; ``tests/test_shared_constants.py``
#: hält das ein.
#:
#: Ein halbes Grad, und die Zahl beschreibt das **Netz** und keine Fertigung:
#: Die zwei Halbzylinder eines Langlochs sind aus demselben Werkzeug
#: geschnitten, ihre Achsen also exakt parallel; was übrig bleibt, ist die
#: Einpassung an einem tesselierten Bogen. Gemessen liegt sie bei 1e-9.
PARALLEL_AXES: float = math.cos(math.radians(0.5))

#: Wie gleich zwei Radien sein müssen, bezogen auf den größeren.
#:
#: Ein Prozent. Dieselbe Begründung wie oben — die Einpassung eines
#: 180-Grad-Bogens trifft den Radius auf ein Zehntausendstel genau; ein Prozent
#: lässt Raum für ein grobes Netz und trennt trotzdem Ø 5 von Ø 5,1.
SAME_RADIUS: float = 0.01

#: Wie weit die Normale eines Dreiecks von der Achse wegzeigen muss, damit es
#: zum **Mantel** gehört. Ein Grad: Deckel und Boden stehen senkrecht darauf
#: und fallen damit heraus, eine leicht schief tesselierte Flanke nicht.
ACROSS_THE_AXIS: float = math.cos(math.radians(89.0))

#: Wieviel eine Flanke von der Ebene abweichen darf, die sie sein soll —
#: als Anteil des Radius. Zwei Prozent decken die Sehne, zu der ein Netz den
#: Übergang zwischen Bogen und Flanke abtastet.
_FLANK_TOLERANCE: float = 0.02

#: Was je Achse einmal gerechnet wird: die Quermaske, die Mantelstücke und
#: der Speicher, welcher Bogen an welches Stück grenzt.
#:
#: **Die drei gehören zusammen und nicht nebeneinander.** Die Nummern in
#: den Mantelstücken bedeuten für eine andere Achse etwas anderes; ein
#: Bogenspeicher daneben gab einem Paar die Etiketten einer fremden Achse
#: zurück und verlor dabei ein echtes Langloch.
_Shells = tuple[list[bool], list[int], dict[int, frozenset[int]]]


#: Welche Arten ein Langloch verschluckt, wenn eines gefunden wird.
#:
#: Dieselbe Menge und derselbe Grund wie bei der Wendel
#: (:data:`app.core.perceive.features._SWALLOWED_BY_A_HELIX`): die eingepassten
#: Grundformen, die **im Mantel** liegen und dort nichts mehr bezeichnen. Die
#: zwei Bögen sind der Regelfall; ein feines Netz kann daneben eine Kuppe oder
#: einen Kegelstumpf einpassen, und auch der gehört zum Loch.
#:
#: ``face`` steht bewusst nicht dabei. Der **Boden** eines Sacklangloch ist
#: eine echte Fläche, und seine Normale zeigt entlang der Achse — er liegt gar
#: nicht im Mantel und bliebe ohnehin stehen. Ihn aufzunehmen hieße nur, eine
#: Ausnahme zu formulieren, die nie greift.
SWALLOWED_BY_A_SLOT: Final[frozenset[str]] = frozenset(
    {"hole", "pin", "cone", "sphere", "torus", "fillet"}
)


@dataclass(frozen=True, slots=True)
class Slot:
    """Ein gemessenes Langloch — und die zwei Einpassungen, aus denen es kam."""

    centre: Vec3
    """Die Mitte, auf halber Länge und halber Tiefe."""
    axis: Vec3
    """Die Richtung, in die gebohrt wurde."""
    direction: Vec3
    """Die Richtung der Mittellinie, senkrecht zur Achse."""
    diameter: float
    """Die Breite — der Durchmesser der beiden Enden."""
    travel: float
    """Der Weg zwischen den beiden Bogenmittelpunkten."""
    depth: float
    """Wie tief das Loch reicht, entlang der Achse."""
    through: bool
    face_indices: tuple[int, ...]
    """Der ganze Mantel: beide Bögen und beide Flanken."""
    swallowed: tuple[int, ...]
    """Welche Einpassungen aus der übergebenen Liste darin aufgehen."""

    @property
    def length(self) -> float:
        """Die Gesamtlänge über beide runden Enden — was im Dialog steht."""
        return self.travel + self.diameter


def slots_instead_of_half_bores(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    fillets: Sequence[tuple[Any, list[int]]],
    *,
    stadiums: Sequence[tuple[Any, list[int]]] = (),
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Ersetzt die Bögen eines Langlochs durch das Langloch.

    Der eine Aufruf, den :func:`app.core.perceive.features.detect` braucht —
    dieselbe Bauart wie ``_threads_instead_of_phantoms`` dort: suchen,
    einsetzen, verschlucken.

    **Verschluckt wird über die Flächen und nicht über die Reihenfolge.** Die
    Nummern in ``fillets`` sind nicht zugesagt die Nummern der ``fillet_N``:
    Es sind zwei Aufrufe mit derselben Liste, keine gemeinsame Zählung, und
    was zwischen ihnen einmal ein Fleck mehr oder weniger ist, verschöbe jede
    Zuordnung über den Index. Über die Flächen gefragt, gibt es diesen Fall
    nicht.

    ``stadiums`` sind die Mäntel aus einem Stück
    (:class:`app.core.perceive.features.StadiumFit`) — dieselbe Merkmalsart,
    ein anderer Weg dorthin; siehe den Kopf dieser Datei.
    """
    slots = find_slots(mesh, fillets, check_cancelled=check_cancelled)
    slots.extend(slots_from_stadiums(mesh, stadiums))
    # Nach Position sortiert, damit die Nummer nicht daran hängt, über welchen
    # der zwei Wege ein Langloch gekommen ist (§21.2).
    slots.sort(key=lambda slot: tuple(round(value, 3) for value in slot.centre))

    covered: set[int] = set()
    for slot in slots:
        covered.update(slot.face_indices)
    kept = {
        name: feature
        for name, feature in found.items()
        if not (
            feature.kind in SWALLOWED_BY_A_SLOT
            and feature.face_indices
            and covered.issuperset(feature.face_indices)
        )
    }
    for number, slot in enumerate(slots, start=1):
        name = f"slot_{number}"
        kept[name] = Feature(
            id=name,
            kind="slot",
            provenance="detected",
            params={
                "diameter": round(slot.diameter, 4),
                "length": round(slot.length, 4),
                "travel": round(slot.travel, 4),
                "axis": slot.axis,
                "direction": slot.direction,
                "centre": slot.centre,
                "depth": round(slot.depth, 4),
                "through": slot.through,
            },
            face_indices=slot.face_indices,
        )
    return open_slots_instead_of_fillets(mesh, kept, fillets, check_cancelled=check_cancelled)


def open_slots_instead_of_fillets(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    fillets: Sequence[tuple[Any, list[int]]],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Erkennt angeschnittene Rundbohrungen und Langlöcher an einem ebenen Außenrand.

    Die Rundwand darf über tangentiale Flanken weiterlaufen. Ihre beiden
    offenen Ränder müssen an derselben Außenebene enden; eine verrundete
    Taschenecke erfüllt diesen Vertrag nicht. Die Länge beschreibt den
    kleinsten vollständigen Werkzeugumriss bis zur Mündung, nicht einen
    geratenen zweiten Bogen außerhalb des Körpers.
    """
    body = mesh.raw
    normals = np.asarray(body.face_normals)
    triangles = np.asarray(body.triangles)
    adjacency = np.asarray(body.face_adjacency)
    edges = np.asarray(body.face_adjacency_edges)
    vertices = np.asarray(body.vertices)
    tolerance = weld_tolerance(mesh.bounds.diagonal)
    kept = dict(found)
    if not fillets or not len(adjacency):
        return kept
    starts, order = _neighbourhood_order(adjacency, len(normals))
    graph = starts, order % len(adjacency)
    covered = {face for f in kept.values() if f.kind == "slot" for face in f.face_indices}
    for fit, patch in fillets:
        if check_cancelled is not None:
            check_cancelled()
        if not fit.inward or not patch or covered.intersection(patch):
            continue
        axis = np.asarray(positive_axis(fit.axis))
        centre = np.asarray(fit.centre)
        # Der Vorfit misst Facettenschwerpunkte. Für Flankentangenz und das
        # Werkzeugmaß zählt der Kreis durch die tatsächlichen Eckpunkte.
        arc_points = vertices[np.unique(np.asarray(body.faces)[patch])] - centre
        radial = arc_points - np.outer(arc_points @ axis, axis)
        u = radial[0] / np.linalg.norm(radial[0])
        v = np.cross(axis, u)
        flat = np.column_stack((radial @ u, radial @ v))
        solved, _, rank, _ = np.linalg.lstsq(
            np.column_stack((2.0 * flat, np.ones(len(flat)))),
            np.sum(flat * flat, axis=1),
            rcond=None,
        )
        if rank != 3:
            continue
        radius = math.sqrt(max(0.0, float(solved[2] + solved[:2] @ solved[:2])))
        centre = centre + solved[0] * u + solved[1] * v
        if radius <= tolerance:
            continue
        chosen, rim, has_flanks = _open_slot_shell(
            triangles,
            normals,
            adjacency,
            graph,
            patch,
            centre,
            axis,
            radius,
            tolerance,
            check_cancelled=check_cancelled,
        )
        vectors = vertices[edges[rim, 1]] - vertices[edges[rim, 0]]
        lengths = np.linalg.norm(vectors, axis=1)
        axial = np.abs(vectors @ axis) >= PARALLEL_AXES * lengths
        boundary = rim[axial & (lengths > tolerance)]
        if len(boundary) < 2:
            continue
        neighbours = adjacency[boundary]
        outside = np.where(np.isin(neighbours[:, 0], chosen), neighbours[:, 1], neighbours[:, 0])
        normal = normals[outside[0]]
        points = vertices[edges[boundary]].reshape(-1, 3)
        if np.any(normals[outside] @ normal < PARALLEL_AXES) or np.ptp(points @ normal) > tolerance:
            continue
        # Genau zwei verschiedene Randlinien, auch bei längs unterteilten Wänden.
        projected = points - np.outer(points @ axis, axis)
        unique = np.unique(np.round(projected / tolerance).astype(np.int64), axis=0)
        if len(unique) != 2:
            continue
        corners = triangles[chosen].reshape(-1, 3)
        low, high = float(np.min(corners @ axis)), float(np.max(corners @ axis))
        depth = high - low
        centre = centre + ((low + high) / 2.0 - float(centre @ axis)) * axis
        mouth = points.mean(axis=0)
        mouth += (float(centre @ axis) - float(mouth @ axis)) * axis
        # Zwei Flanken eines Kreuzlochs liegen ebenfalls in einer Ebene.
        # Hinter ihrer vermeintlichen Mündung liegt aber wieder Material.
        reach = mesh.bounds.diagonal * 2.0
        if not _reaches_through(body, mouth + normal * reach / 2.0, normal, axis, 0.0, reach):
            continue
        travel = float(np.linalg.norm(mouth - centre)) if has_flanks else 0.0
        direction = (mouth - centre) / travel if travel > tolerance else normal
        middle = centre + direction * travel / 2.0
        indices = tuple(int(face) for face in chosen)
        selected = set(indices)
        number = 1
        while f"slot_{number}" in kept:
            number += 1
        name = f"slot_{number}"
        kept = {
            key: feature
            for key, feature in kept.items()
            if not (
                feature.kind in SWALLOWED_BY_A_SLOT
                and feature.face_indices
                and selected.issuperset(feature.face_indices)
            )
        }
        kept[name] = Feature(
            id=name,
            kind="slot",
            provenance="detected",
            face_indices=indices,
            params={
                "diameter": radius * 2.0,
                "length": radius * 2.0 + travel,
                "travel": travel,
                "axis": tuple(float(v) for v in axis),
                "direction": tuple(float(v) for v in direction),
                "centre": tuple(float(v) for v in middle),
                "depth": depth,
                "through": _reaches_through(body, centre, axis, direction, 0.0, depth),
                "open": True,
                "arc_centre": tuple(float(v) for v in centre),
                "mouth_centre": tuple(float(v) for v in mouth),
                "opening_normal": tuple(float(v) for v in normal),
            },
        )
        covered.update(indices)
    return kept


def _open_slot_shell(
    triangles: np.ndarray,
    normals: np.ndarray,
    adjacency: np.ndarray,
    graph: tuple[np.ndarray, np.ndarray],
    patch: Sequence[int],
    centre: np.ndarray,
    axis: np.ndarray,
    radius: float,
    tolerance: float,
    *,
    check_cancelled: Callable[[], None] | None,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Erweitert den Bogen nur über erreichbare Flanken und weitere Kreisfacetten.

    Jede besuchte Fläche wird einmal geometrisch geprüft. Abgelehnte Nachbarn
    bleiben als Grenze bekannt; ferne Dreiecke bekommen weder eine Maske noch
    ein eigenes Koordinatenfeld für diesen Bogen.
    """
    chosen = set(patch)
    visited = set(patch)
    frontier = np.asarray(sorted(chosen), dtype=np.int64)
    _allowed, on_arc = _open_slot_candidates(
        triangles[frontier], normals[frontier], centre, axis, radius, tolerance
    )
    arc_faces = set(frontier[on_arc])
    incident_rows = []
    while len(frontier):
        if check_cancelled is not None:
            check_cancelled()
        incident = _adjacent_rows(graph, frontier)
        incident_rows.append(incident)
        neighbours = np.unique(adjacency[incident])
        candidates = np.asarray(
            [face for face in neighbours if face not in visited], dtype=np.int64
        )
        if not len(candidates):
            break
        visited.update(candidates)
        allowed, on_arc = _open_slot_candidates(
            triangles[candidates], normals[candidates], centre, axis, radius, tolerance
        )
        frontier = candidates[allowed]
        chosen.update(frontier)
        arc_faces.update(candidates[on_arc])
    selected = np.asarray(sorted(chosen), dtype=np.int64)
    incident = np.unique(np.concatenate(incident_rows))
    first = np.isin(adjacency[incident, 0], selected)
    second = np.isin(adjacency[incident, 1], selected)
    return selected, incident[first != second], not arc_faces.issuperset(chosen)


def _open_slot_candidates(
    triangles: np.ndarray,
    normals: np.ndarray,
    centre: np.ndarray,
    axis: np.ndarray,
    radius: float,
    tolerance: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Dieselben Tangenz- und Kreisbedingungen an einer lokalen Nachbarmenge."""
    relative = triangles - centre
    distances = np.einsum("ijk,ik->ij", relative, normals)
    tangent = (np.abs(normals @ axis) <= ACROSS_THE_AXIS) & (
        np.max(np.abs(distances + radius), axis=1) <= tolerance
    )
    radial = relative - np.outer((relative @ axis).ravel(), axis).reshape(relative.shape)
    on_arc = (np.max(np.abs(np.linalg.norm(radial, axis=2) - radius), axis=1) <= tolerance) & (
        np.einsum("ij,ij->i", radial.mean(axis=1), normals) < 0.0
    )
    return tangent | on_arc, on_arc


def slots_from_stadiums(mesh: MeshData, stadiums: Sequence[tuple[Any, list[int]]]) -> list[Slot]:
    """Aus jedem eingepassten Stadion das Langloch, das es ist.

    Die Einpassung hat Achse, Mittellinie, Radius, Weg und Tiefe schon gemessen
    (:func:`app.core.perceive.features.fit_stadium`); was hier dazukommt, ist
    die Frage nach dem Durchgang — dieselbe wie beim Bogenpaar
    (:func:`_reaches_through`) — und die Form, die der Objektbaum liest.
    ``swallowed`` bleibt leer: Es gibt keine Bögen, die darin aufgehen; die
    Flächen sind der Fleck selbst.
    """
    body = mesh.raw
    found: list[Slot] = []
    for fit, patch in stadiums:
        centre = np.asarray(fit.centre, dtype=float)
        axis = np.asarray(fit.axis, dtype=float)
        direction = np.asarray(fit.direction, dtype=float)
        found.append(
            Slot(
                centre=(float(centre[0]), float(centre[1]), float(centre[2])),
                axis=(float(axis[0]), float(axis[1]), float(axis[2])),
                direction=(float(direction[0]), float(direction[1]), float(direction[2])),
                diameter=float(fit.radius) * 2.0,
                travel=float(fit.travel),
                depth=float(fit.depth),
                through=_reaches_through(
                    body, centre, axis, direction, float(fit.travel), float(fit.depth)
                ),
                face_indices=tuple(sorted(int(face) for face in patch)),
                swallowed=(),
            )
        )
    return found


def find_slots(
    mesh: MeshData,
    fillets: Sequence[tuple[Any, list[int]]],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Slot]:
    """Sucht in den eingepassten Zylinderausschnitten die Paare, die ein
    Langloch bilden.

    ``fillets`` ist die Liste aus :func:`app.core.perceive.features._fitted` —
    Einpassung und Dreiecksfleck. Gebraucht werden davon nur die nach innen
    gerichteten: Ein Langloch ist ein Hohlraum, und eine außen liegende Rundung
    kann keiner sein.

    **Was zu klein für ein Werkzeug ist, siebt der Aufrufer aus**, so wie bei
    :func:`app.core.perceive.features.detect_fillets`: ``detect`` reicht
    ``_fillets_worth_naming`` herein, und dort steht die Frage einmal
    (``_too_small_to_make``). Wer die rohe Liste übergibt, bekommt auch
    Langlöcher, die kein Bohrer je gemacht hat.

    **Das Netz muss verschweißt sein.** Die Prüfung läuft über die
    Flächennachbarschaft, und eine roh geladene STL hat keine (siehe
    :func:`app.core.geom.mesh.face_components`). ``detect`` schweißt vorher
    über ``_one_body``; wer diese Funktion allein ruft, tut dasselbe.

    ``check_cancelled`` darf ``OperationCancelled`` werfen (§2.8), geprüft je
    Bogen der äußeren Schleife. Die Suche geht über **alle Paare** von
    Innenverrundungen; ihre Zahl wächst quadratisch mit der Bogenzahl. Der
    Abbruch gehört zum gesamten Erkennungslauf, unabhängig davon, wie schnell
    dieser Teilschritt an einem einzelnen Prüfkörper ist. Der Ganzkörpertest
    mit vielen Taschen in ``tests/test_performance.py`` misst diesen Weg.
    """
    body = mesh.raw
    candidates = [
        (index, fit, patch)
        for index, (fit, patch) in enumerate(fillets)
        if getattr(fit, "inward", False) and float(getattr(fit, "radius", 0.0)) > EPS_GEOM
    ]
    if len(candidates) < 2:
        return []

    normals = np.asarray(body.face_normals, dtype=float)
    neighbours = np.asarray(body.face_adjacency, dtype=int)
    if not len(neighbours):
        return []
    # **Die Nachbarschaft wird einmal gebaut und nicht je Paar.** Sie hing im
    # ersten Anlauf in :func:`_connected_shell` und wurde damit für jedes Paar
    # neu aus der Kantenliste zusammengesetzt — eine Python-Schleife über
    # sämtliche Nachbarschaften des Netzes. Gemessen an einer Platte mit
    # sechzehn verrundeten Taschen (4364 Dreiecke, 64 Innenverrundungen, 2016
    # Paare): ``detect`` stieg von 64,5 ms auf 3568 ms, Faktor 55, und über
    # sechs der acht Sekunden standen in dieser einen Schleife. Die Kantenliste
    # ändert sich zwischen zwei Paaren nicht; was sich ändert, ist allein die
    # Maske, und die fragt der Lauf jetzt beim Betreten einer Fläche.
    graph = _neighbourhood(neighbours, len(normals))

    # Quermaske, Mantelstücke und Bogenspeicher hängen allein an der Achse und
    # werden deshalb über alle Paare geteilt — der Grund steht bei
    # :func:`_shells_for`.
    masks: dict[bytes, _Shells] = {}
    axes = {index: _unit(fit.axis) for index, fit, _patch in candidates}

    found: list[Slot] = []
    taken: set[int] = set()
    for first in range(len(candidates)):
        if check_cancelled is not None:
            check_cancelled()
        if candidates[first][0] in taken:
            continue
        for second in range(first + 1, len(candidates)):
            if candidates[second][0] in taken:
                continue
            slot = _slot_from(
                body, normals, graph, masks, candidates[first], candidates[second], axes
            )
            if slot is not None:
                found.append(slot)
                taken.update(slot.swallowed)
                break
    return found


def _neighbourhood(neighbours: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray]:
    """Die Flächennachbarschaft als Anfangsindex und Zielliste.

    Zwei Felder statt eines Wörterbuchs: Die Nachbarn der Fläche ``face``
    stehen in ``targets[starts[face] : starts[face + 1]]``. Gebaut wird das in
    NumPy und nicht in einer Schleife — bei 200 000 Dreiecken sind es rund
    300 000 Kanten, und die einzeln in Python anzufassen kostet mehr als die
    ganze Erkennung darf (§31).
    """
    starts, order = _neighbourhood_order(neighbours, count)
    targets = np.concatenate((neighbours[:, 1], neighbours[:, 0]))
    return starts, np.ascontiguousarray(targets[order])


def _neighbourhood_order(neighbours: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray]:
    """Dieselbe stabile Flächenordnung für Nachbarflächen und Nachbarkanten."""
    sources = np.concatenate((neighbours[:, 0], neighbours[:, 1]))
    order = np.argsort(sources, kind="stable")
    starts = np.searchsorted(sources[order], np.arange(count + 1))
    return starts, order


def _adjacent_rows(graph: tuple[np.ndarray, np.ndarray], faces: np.ndarray) -> np.ndarray:
    """Die Nachbarschaftszeilen gewählter Flächen, ohne Schleife über das ganze Netz."""
    starts, rows = graph
    counts = starts[faces + 1] - starts[faces]
    offsets = np.repeat(starts[faces] - np.cumsum(counts) + counts, counts)
    return np.unique(rows[offsets + np.arange(int(counts.sum()))])


def _slot_from(
    body: Any,
    normals: np.ndarray,
    graph: tuple[np.ndarray, np.ndarray],
    masks: dict[bytes, _Shells],
    first: tuple[int, CylinderFit, list[int]],
    second: tuple[int, CylinderFit, list[int]],
    axes: Mapping[int, np.ndarray | None],
) -> Slot | None:
    """Ob diese zwei Zylinderausschnitte ein Langloch sind — und welches.

    ``masks`` sammelt je Achse, was nur an ihr hängt — siehe
    :func:`_shells_for`.
    """
    index_a, fit_a, patch_a = first
    index_b, fit_b, patch_b = second

    radius = (float(fit_a.radius) + float(fit_b.radius)) / 2.0
    if abs(float(fit_a.radius) - float(fit_b.radius)) > SAME_RADIUS * max(
        float(fit_a.radius), float(fit_b.radius)
    ):
        return None

    axis_a = axes[index_a]
    axis_b = axes[index_b]
    if axis_a is None or axis_b is None or abs(float(axis_a @ axis_b)) < PARALLEL_AXES:
        return None
    # Die gemeinsame Achse, aus beiden gemittelt: Das Vorzeichen der zweiten
    # richtet sich nach der ersten, sonst hebt eine gegenläufig eingepasste
    # Achse die andere auf.
    axis = _unit(axis_a + (axis_b if float(axis_a @ axis_b) > 0.0 else -axis_b))
    if axis is None:
        return None

    # Getrennte Mantelstücke scheiden vor der Richtungsrechnung aus. Die
    # topologische Antwort hängt nur an der Achse, nicht an der Mittellinie.
    across_mask, labels, touched = _shells_for(normals, axis, graph, masks)
    if not _shares_a_shell(labels, graph, (index_a, patch_a), (index_b, patch_b), touched):
        return None

    centre_a = np.asarray(fit_a.centre, dtype=float)
    centre_b = np.asarray(fit_b.centre, dtype=float)
    between = centre_b - centre_a
    # Was entlang der Achse liegt, ist Versatz in der Tiefe und nicht die
    # Mittellinie — zwei Bohrungen übereinander sind kein Langloch.
    sideways = between - float(between @ axis) * axis
    travel = float(np.linalg.norm(sideways))
    if travel <= EPS_GEOM:
        return None
    direction = sideways / travel
    across = np.cross(axis, direction)

    faces = _connected_shell(across_mask, graph, patch_a, patch_b)
    if faces is None:
        return None

    centre = (centre_a + centre_b) / 2.0
    if not _flanks_are_flat(body, faces, set(patch_a) | set(patch_b), centre, across, radius):
        # Grobe Bogenflecken können Tangentenstücke mittragen und ihre
        # Nachbarn noch Bogenreste. Dann gilt der vorhandene Formnachweis
        # für den ganzen Mantel; die Fitgrenze wird nicht aufgeweitet.
        from app.core.perceive.features import fit_stadium

        flank_faces = faces - set(patch_a) - set(patch_b)
        if not flank_faces:
            return None
        flank = max(flank_faces, key=lambda face: float(body.area_faces[face]))
        along_flank = _unit(np.cross(axis, normals[flank]))
        if along_flank is None:
            return None
        stadium = fit_stadium(
            body,
            sorted(faces),
            direction_hint=(float(along_flank[0]), float(along_flank[1]), float(along_flank[2])),
        )
        if stadium is None or not stadium.good or not stadium.inward:
            return None
        centre = np.asarray(stadium.centre, dtype=float)
        axis = np.asarray(stadium.axis, dtype=float)
        direction = np.asarray(stadium.direction, dtype=float)
        travel = stadium.travel
        diameter = stadium.radius * 2.0
    else:
        # Die Zylinderanpassung misst Dreiecksschwerpunkte, also innerhalb des
        # Kreisbogens. Die Breite tragen dagegen die bereits geprüften ebenen
        # Flanken: Ihr Abstand bleibt auch nach erneutem Schneiden derselbe.
        flank_indices = sorted(faces - set(patch_a) - set(patch_b))
        flank_points = np.asarray(body.triangles, dtype=float)[flank_indices].reshape(-1, 3)
        flank_distances = (flank_points - centre) @ across
        diameter = float(np.ptp(flank_distances))

    corners = np.asarray(body.triangles, dtype=float)[list(faces)].reshape(-1, 3) - centre
    along_axis = corners @ axis
    depth = float(along_axis.max() - along_axis.min())
    if depth <= EPS_GEOM:
        return None
    middle = centre + float(along_axis.max() + along_axis.min()) / 2.0 * axis

    return Slot(
        centre=(float(middle[0]), float(middle[1]), float(middle[2])),
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        direction=(float(direction[0]), float(direction[1]), float(direction[2])),
        diameter=diameter,
        travel=travel,
        depth=depth,
        through=_reaches_through(body, middle, axis, direction, travel, depth),
        face_indices=tuple(sorted(faces)),
        swallowed=(index_a, index_b),
    )


def _unit(vector: Any) -> np.ndarray | None:
    """Ein Einheitsvektor, oder nichts, wenn er keine Länge hat."""
    value = np.asarray(vector, dtype=float)
    length = float(np.linalg.norm(value))
    if not math.isfinite(length) or length <= EPS_GEOM:
        return None
    return value / length


def _connected_shell(
    across: list[bool],
    graph: tuple[np.ndarray, np.ndarray],
    patch_a: Sequence[int],
    patch_b: Sequence[int],
) -> set[int] | None:
    """Der Mantel, der beide Bögen verbindet — oder nichts.

    Gelaufen wird nur über Dreiecke, deren Normale **quer** zur Achse steht:
    Deckel, Boden und die Flächen ringsum stehen senkrecht darauf und sind
    keine Wand des Lochs. Endet der Lauf, ohne den zweiten Bogen erreicht zu
    haben, hängen die beiden nicht zusammen — dann sind es zwei Rundungen und
    kein Langloch.

    ``graph`` ist die Nachbarschaft des ganzen Netzes aus
    :func:`_neighbourhood` — sie gilt für alle Paare, und deshalb wird sie
    hier gelesen und nicht gebaut.

    ``across`` sagt je Fläche, ob sie quer zur Achse steht — sie kommt von
    außen, weil sie **allein an der Achse hängt** und nicht am Paar; alle
    Bögen eines Langlochs teilen sie. Was diesem Paar gehört, sind die zwei
    Bogenflecken, und die stehen als Menge daneben statt in einer Kopie.
    """
    starts, targets = graph
    arcs = {int(face) for face in patch_a} | {int(face) for face in patch_b}
    goal = {int(face) for face in patch_b}
    seen: set[int] = {int(face) for face in patch_a}
    stack = list(seen)
    while stack:
        face = stack.pop()
        for neighbour in targets[starts[face] : starts[face + 1]].tolist():
            if neighbour not in seen and (across[neighbour] or neighbour in arcs):
                seen.add(neighbour)
                stack.append(neighbour)
    return seen if goal <= seen else None


def _shell_labels(across: list[bool], graph: tuple[np.ndarray, np.ndarray]) -> list[int]:
    """Die zusammenhängenden Mantelstücke einer Achse, je Fläche eine Nummer.

    Flächen, die nicht quer stehen, bekommen ``-1``. Zwei Bögen können nur
    dann ein Langloch sein, wenn sie an **dasselbe** Stück grenzen — und das
    steht damit fest, ohne für jedes Paar zu laufen (:func:`_shares_a_shell`).
    """
    starts, targets = graph
    labels = [-1] * len(across)
    running = 0
    for seed in range(len(across)):
        if not across[seed] or labels[seed] >= 0:
            continue
        labels[seed] = running
        stack = [seed]
        while stack:
            face = stack.pop()
            for neighbour in targets[starts[face] : starts[face + 1]].tolist():
                if across[neighbour] and labels[neighbour] < 0:
                    labels[neighbour] = running
                    stack.append(neighbour)
        running += 1
    return labels


def _shells_touched(
    labels: list[int],
    graph: tuple[np.ndarray, np.ndarray],
    patch: Sequence[int],
    index: int,
    cache: dict[int, frozenset[int]],
) -> frozenset[int]:
    """An welche Mantelstücke dieser Bogen grenzt — je Bogen einmal gefragt.

    **Auch das gehört dem Bogen und nicht dem Paar.** Der erste Anlauf der
    Vorprüfung rechnete es beidseitig je Paar aus und war damit wieder
    quadratisch, nur billiger: An der Platte mit 64 Taschen wären es 65 280
    Durchgänge über die Nachbarschaft von Flecken, die sich zu 256
    unterschiedlichen zusammenfassen lassen. Der Bogen hat eine Nummer, die
    über den ganzen Lauf gilt (die Stelle in ``fillets``), und die ist der
    Schlüssel.

    **Der Speicher gehört dabei der Achse und nicht dem Lauf**, und das ist
    keine Feinheit: Die Nummern in ``labels`` kommen aus
    :func:`_shell_labels` und bedeuten für eine andere Achse etwas anderes.
    Ein Speicher über den ganzen Lauf gab einem Paar die Etiketten einer
    fremden Achse zurück — gemessen an einem verjüngten Klotz (Wand 0,85 bis
    1,0 Grad aus der Senkrechten) mit zwei Langlöchern, von denen das zweite
    um 0,4 Grad kippt: zwei gefunden vorher, **eines** danach. Er liegt
    deshalb in :func:`_shells_for` neben ``across`` und ``labels``, unter
    demselben Schlüssel (Fund der Nachkontrolle, 11.09.2026).
    """
    ready = cache.get(index)
    if ready is None:
        starts, targets = graph
        ready = frozenset(
            labels[neighbour]
            for face in patch
            for neighbour in targets[starts[face] : starts[face + 1]].tolist()
            if labels[neighbour] >= 0
        )
        cache[index] = ready
    return ready


def _shares_a_shell(
    labels: list[int],
    graph: tuple[np.ndarray, np.ndarray],
    first: tuple[int, Sequence[int]],
    second: tuple[int, Sequence[int]],
    cache: dict[int, frozenset[int]],
) -> bool:
    """Grenzen beide Bögen an dasselbe Mantelstück?

    **Die Vorprüfung, die den quadratischen Teil bezahlbar macht.** Ohne sie
    lief für jedes Paar ein Tiefenlauf, auch für zwei Bögen in verschiedenen
    Taschen desselben Bauteils, zwischen denen es gar keinen gemeinsamen
    Mantel gibt. Gemessen an einer Platte mit 64 verrundeten Taschen (256
    Innenverrundungen, 32 640 Paare) waren das 32 640 Läufe, von denen 384
    überhaupt eine Chance hatten — gezählt.

    **Sie lehnt nur ab, was auch der Lauf abgelehnt hätte.** Erreicht er den
    zweiten Bogen, ist er über querstehende Flächen dorthin gekommen, und die
    liegen dann in einem Stück. Der einzige andere Weg wäre ein unmittelbarer
    Kontakt der beiden Bogenflecken — dann ist ``faces`` genau
    ``patch_a | patch_b``, und :func:`_flanks_are_flat` lehnt mit leerem
    ``rest`` ab. Beide Wege enden gleich.
    """
    index_a, patch_a = first
    index_b, patch_b = second
    touched = _shells_touched(labels, graph, patch_a, index_a, cache)
    if not touched:
        return False
    return bool(touched & _shells_touched(labels, graph, patch_b, index_b, cache))


def _shells_for(
    normals: np.ndarray,
    axis: np.ndarray,
    graph: tuple[np.ndarray, np.ndarray],
    cache: dict[bytes, _Shells],
) -> _Shells:
    """Quermaske und Mantelstücke einer Achse — je Achse einmal gerechnet.

    **Der teuerste Posten der Langlochsuche stand hier, und er war es zweimal
    umsonst.** ``np.abs(normals @ axis) <= ACROSS_THE_AXIS`` lief in
    :func:`_connected_shell` je **Paar** über das ganze Netz, dazu eine
    Vollkopie als ``allowed``. Beides hängt nur an der Achse, und die teilen
    sich alle Bögen eines Langlochs: An einer Platte mit sechzehn verrundeten
    Taschen (64 Innenverrundungen, 2016 Paare) wurde dieselbe Maske
    zweitausendmal gebaut, und ``find_slots`` kostete 190 ms bei 4366
    Dreiecken — ein Anteil, der mit dem **Netz** wächst, obwohl der Lauf davon
    nur einen Bruchteil der Flächen anfasst. An einem Netz von der Größe aus
    §31 mit ebenso vielen Bögen reißt das die Sekunde um ein Mehrfaches; der
    Prüfkörper aus §31 selbst trägt keine Innenverrundungen und läuft hier gar
    nicht durch.

    **Der naheliegende Griff daneben war der falsche**, und er ist gemessen
    worden: die Querprüfung je betretener Fläche zu rechnen statt vorher für
    alle. Das sieht nach weniger Arbeit aus und war dreimal so teuer (532 ms) —
    ein numpy-Skalarzugriff kostet mehr als das vektorisierte Produkt über
    tausende Zeilen. Die Rechnung bleibt also vektorisiert; gespart wird ihre
    **Wiederholung**.

    **Der Schlüssel ist die gerundete Achse, und die Rundung ist der ganze
    Gewinn.** Hier standen die rohen Bytes, mit der Begründung, zwei Achsen im
    letzten Bit sollten lieber zwei Einträge bekommen, als dass eine Fläche
    dicht an der Schwelle die Maske des Nachbarn erbt. Das war für einen
    **achsparallel** liegenden Körper richtig und für jeden anderen falsch:
    Gemessen an derselben Platte mit 16 Taschen, um 0,5 Grad gekippt, kamen
    **1817 verschiedene Achsen** auf 2016 Paare — der Speicher traf nie, und
    weil er dabei je Eintrag zwei Listen über alle Flächen hielt, stieg der
    Spitzenspeicher von 0,7 auf 138 MB und die Laufzeit von 190 auf 1795 ms.
    Der vermeintliche Schutz hat also nichts geschützt und den Fall, für den
    die Sache gebaut ist, zehnmal teurer gemacht (Fund der Nachkontrolle,
    11.09.2026).

    Auf neun Stellen gerundet sind es **zwei** Achsen statt 1817 — bei jeder
    gemessenen Kippung von einem halben bis fünfundvierzig Grad. Das ist keine
    Glückszahl: Die Einpassungen zweier Bögen desselben Werkzeugs unterscheiden
    sich nur im Rechenrauschen, und das liegt bei 1e-9 (die Zahl steht an
    :data:`PARALLEL_AXES`). Gegen die Schwelle :data:`ACROSS_THE_AXIS` — der Kosinus von
    89 Grad, rund 0,0175 — ist eine Achsenabweichung von 1e-9 sechs
    Größenordnungen zu klein, um eine Fläche über die Grenze zu heben.

    ``tolist()`` einmal, weil der Lauf danach einzeln fragt und eine
    Python-Liste dort schneller antwortet als ein numpy-Feld. Die Mantelstücke
    aus :func:`_shell_labels` kommen im selben Zug, weil sie an derselben Achse
    hängen — und **der Bogenspeicher liegt daneben im selben Eintrag**: Seine
    Nummern sind die aus ``labels``, und die bedeuten für eine andere Achse
    etwas anderes.
    """
    key = np.round(np.ascontiguousarray(axis, dtype=float), 9).tobytes()
    ready = cache.get(key)
    if ready is None:
        across = (np.abs(normals @ axis) <= ACROSS_THE_AXIS).tolist()
        ready = (across, _shell_labels(across, graph), {})
        cache[key] = ready
    return ready


def _flanks_are_flat(
    body: Any,
    faces: set[int],
    arcs: set[int],
    centre: np.ndarray,
    across: np.ndarray,
    radius: float,
) -> bool:
    """Ob alles zwischen den Bögen eine der zwei ebenen Flanken ist.

    **Die strenge Hälfte der Prüfung.** Zwei Bohrungen, die zufällig über eine
    dritte Fläche zusammenhängen, kämen sonst als Langloch heraus. Eine Flanke
    liegt genau einen Radius von der Mittellinie entfernt und parallel zu ihr;
    was weiter draußen liegt oder schräg steht, gehört nicht dazu.
    """
    rest = [face for face in faces if face not in arcs]
    if not rest:
        return False
    corners = np.asarray(body.triangles, dtype=float)[rest].reshape(-1, 3) - centre
    distance = np.abs(corners @ across)
    return bool(np.all(np.abs(distance - radius) <= _FLANK_TOLERANCE * radius))


def _reaches_through(
    body: Any,
    centre: np.ndarray,
    axis: np.ndarray,
    direction: np.ndarray,
    travel: float,
    depth: float,
) -> bool:
    """Ob man durch das Langloch hindurchsieht.

    Dieselbe Frage wie bei einer runden Bohrung
    (:func:`app.core.perceive.features._is_through`) und dieselbe Bauart — in
    der Projektion senkrecht zur Achse, ohne Strahlwurf und ohne Raumindex.
    Gefragt wird aber nach einer **Strecke** statt nach einem Punkt: Ein Steg
    quer über der Mitte verschließt ein Langloch, ohne über einem seiner
    Bogenmittelpunkte zu liegen.

    **Und die Strecke wird nicht abgetastet, sondern geschnitten.** Hier stand
    eine Abtastung in Schritten von einem halben Radius, begründet mit
    „schmaler als jedes Stück Material, das ein Drucker legen kann" — das war
    falsch: Bei Ø 5 sind das 1,25 mm, eine Extrusionsbahn ist 0,42 mm breit.
    Gemessen an einem Langloch Ø 5 auf 40 mm mit einer Brücke darin: 0,5 mm
    und 1,0 mm Brücke kamen als „Durchgang" zurück, 1,3 mm nicht — wer zwischen
    zwei Abtastpunkte fällt, ist unsichtbar. Die exakte Frage ist nicht teurer:
    Ein Dreieck verschließt die Mittellinie genau dann, wenn es einen ihrer
    zwei Endpunkte überdeckt **oder** eine seiner Kanten sie schneidet. Beides
    ist ein Durchgang über alle Dreiecke, und es braucht keine Schwelle —
    :mod:`app.core.perceive.slots` kennt kein Materialprofil und soll auch
    keines erfinden (Regel 7).

    Gezählt wird wie beim runden Zwilling nur, was **im Abschnitt des Lochs**
    entlang der Achse liegt: Der gegenüberliegende Schenkel eines U-Profils
    steht in der Projektion über der Öffnung und verschließt sie trotzdem
    nicht.

    Gerufen wird die Schwester dort nicht: ``features`` liest dieses Modul, und
    die Gegenrichtung schlösse den Kreis.
    """
    corners = np.asarray(body.triangles, dtype=float) - centre
    along = corners @ axis
    reach = (along.min(axis=1) <= depth / 2.0 + EPS_GEOM) & (
        along.max(axis=1) >= -depth / 2.0 - EPS_GEOM
    )
    corners = corners[reach]
    if not len(corners):
        return True

    flat = np.stack([corners @ direction, corners @ np.cross(axis, direction)], axis=-1)
    reach_x = travel / 2.0
    if _covers(flat, np.array([-reach_x, 0.0])) or _covers(flat, np.array([reach_x, 0.0])):
        return False
    return not _crosses(flat, reach_x)


def _covers(flat: np.ndarray, point: np.ndarray) -> bool:
    """Ob eines der projizierten Dreiecke diesen Punkt überdeckt."""
    first, second, third = flat[:, 0] - point, flat[:, 1] - point, flat[:, 2] - point

    def turn(edge: np.ndarray, towards: np.ndarray) -> np.ndarray:
        # Von Hand, weil ``np.cross`` seit NumPy 2 nur noch dreidimensional
        # rechnet — dieselbe Zeile wie in ``features._is_through``.
        return np.asarray(edge[:, 0] * towards[:, 1] - edge[:, 1] * towards[:, 0], dtype=float)

    side_a = turn(second - first, -first)
    side_b = turn(third - second, -second)
    side_c = turn(first - third, -third)
    inside = ((side_a >= 0.0) & (side_b >= 0.0) & (side_c >= 0.0)) | (
        (side_a <= 0.0) & (side_b <= 0.0) & (side_c <= 0.0)
    )
    return bool(inside.any())


def _crosses(flat: np.ndarray, reach: float) -> bool:
    """Ob eine Dreieckskante die Mittellinie schneidet.

    Die Mittellinie liegt in dieser Projektion auf ``y = 0`` zwischen
    ``-reach`` und ``+reach`` — dafür ist die erste Achse gerade ihre Richtung.
    Eine Kante kreuzt sie, wenn ihre beiden Enden auf verschiedenen Seiten
    liegen und der Schnittpunkt zwischen den Enden der Strecke sitzt. Zusammen
    mit den zwei Endpunkten aus :func:`_covers` ist das die vollständige
    Antwort: Ein Dreieck, das die Strecke berührt, ohne einen Endpunkt zu
    überdecken, muss sie durchqueren.
    """
    for start, end in ((0, 1), (1, 2), (2, 0)):
        first, second = flat[:, start], flat[:, end]
        below, above = first[:, 1], second[:, 1]
        # Kanten, die auf der Linie liegen, haben keinen Vorzeichenwechsel und
        # tragen hier nichts bei — sie gehören zu einem Dreieck, dessen zwei
        # andere Kanten sie haben, oder zu einer Fläche, die nichts verschließt.
        span = above - below
        crossing = np.sign(below) != np.sign(above)
        crossing &= np.abs(span) > EPS_GEOM
        if not bool(crossing.any()):
            continue
        share = -below[crossing] / span[crossing]
        touch = first[crossing, 0] + share * (second[crossing, 0] - first[crossing, 0])
        if bool(np.any((touch >= -reach - EPS_GEOM) & (touch <= reach + EPS_GEOM))):
            return True
    return False
