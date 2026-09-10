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
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.types import Feature, FeatureId, Vec3
from app.core.units import EPS_GEOM

if TYPE_CHECKING:  # pragma: no cover - nur für die Typprüfung
    from app.core.perceive.features import CylinderFit

#: Wie parallel zwei Achsen sein müssen, um dieselbe zu sein.
#:
#: Ein halbes Grad, und die Zahl beschreibt das **Netz** und keine Fertigung:
#: Die zwei Halbzylinder eines Langlochs sind aus demselben Werkzeug
#: geschnitten, ihre Achsen also exakt parallel; was übrig bleibt, ist die
#: Einpassung an einem tesselierten Bogen. Gemessen liegt sie bei 1e-9.
_PARALLEL: float = math.cos(math.radians(0.5))

#: Wie gleich zwei Radien sein müssen, bezogen auf den größeren.
#:
#: Ein Prozent. Dieselbe Begründung wie oben — die Einpassung eines
#: 180-Grad-Bogens trifft den Radius auf ein Zehntausendstel genau; ein Prozent
#: lässt Raum für ein grobes Netz und trennt trotzdem Ø 5 von Ø 5,1.
_SAME_RADIUS: float = 0.01

#: Wie weit die Normale eines Dreiecks von der Achse wegzeigen muss, damit es
#: zum **Mantel** gehört. Ein Grad: Deckel und Boden stehen senkrecht darauf
#: und fallen damit heraus, eine leicht schief tesselierte Flanke nicht.
_ACROSS: float = math.cos(math.radians(89.0))

#: Wieviel eine Flanke von der Ebene abweichen darf, die sie sein soll —
#: als Anteil des Radius. Zwei Prozent decken die Sehne, zu der ein Netz den
#: Übergang zwischen Bogen und Flanke abtastet.
_FLANK_TOLERANCE: float = 0.02


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
    """
    slots = find_slots(mesh, fillets, check_cancelled=check_cancelled)
    if not slots:
        return dict(found)

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
    return kept


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
    Innenverrundungen, und das ist quadratisch: An einer Platte mit 48
    verrundeten Taschen (13 070 Dreiecke, 192 Bögen, 18 336 Paare) kostet sie
    2,0 s — über der Schwelle, ab der §2.8 einen Abbruch verlangt, und das
    schon weit unter den 200 000 Dreiecken aus §31.
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
            slot = _slot_from(body, normals, graph, candidates[first], candidates[second])
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
    both = np.concatenate((neighbours, neighbours[:, ::-1]))
    order = np.argsort(both[:, 0], kind="stable")
    sorted_edges = both[order]
    starts = np.searchsorted(sorted_edges[:, 0], np.arange(count + 1))
    return starts, np.ascontiguousarray(sorted_edges[:, 1])


def _slot_from(
    body: Any,
    normals: np.ndarray,
    graph: tuple[np.ndarray, np.ndarray],
    first: tuple[int, CylinderFit, list[int]],
    second: tuple[int, CylinderFit, list[int]],
) -> Slot | None:
    """Ob diese zwei Zylinderausschnitte ein Langloch sind — und welches."""
    index_a, fit_a, patch_a = first
    index_b, fit_b, patch_b = second

    radius = (float(fit_a.radius) + float(fit_b.radius)) / 2.0
    if abs(float(fit_a.radius) - float(fit_b.radius)) > _SAME_RADIUS * max(
        float(fit_a.radius), float(fit_b.radius)
    ):
        return None

    axis_a = _unit(fit_a.axis)
    axis_b = _unit(fit_b.axis)
    if axis_a is None or axis_b is None or abs(float(axis_a @ axis_b)) < _PARALLEL:
        return None
    # Die gemeinsame Achse, aus beiden gemittelt: Das Vorzeichen der zweiten
    # richtet sich nach der ersten, sonst hebt eine gegenläufig eingepasste
    # Achse die andere auf.
    axis = _unit(axis_a + (axis_b if float(axis_a @ axis_b) > 0.0 else -axis_b))
    if axis is None:
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

    faces = _connected_shell(normals, graph, axis, patch_a, patch_b)
    if faces is None:
        return None

    centre = (centre_a + centre_b) / 2.0
    if not _flanks_are_flat(body, faces, set(patch_a) | set(patch_b), centre, across, radius):
        return None

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
        diameter=radius * 2.0,
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
    normals: np.ndarray,
    graph: tuple[np.ndarray, np.ndarray],
    axis: np.ndarray,
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
    hier gelesen und nicht gebaut. Was diesem Paar gehört, ist die Maske
    ``allowed``; sie wird beim **Betreten** einer Fläche gefragt, und damit hat
    jede gelaufene Kante beide Enden im Erlaubten, genau wie vorher.
    """
    across = np.abs(normals @ axis) <= _ACROSS
    if not bool(across.any()):
        return None
    allowed = np.array(across, dtype=bool)
    allowed[np.asarray(patch_a, dtype=int)] = True
    allowed[np.asarray(patch_b, dtype=int)] = True

    starts, targets = graph
    goal = {int(face) for face in patch_b}
    seen: set[int] = {int(face) for face in patch_a}
    stack = list(seen)
    while stack:
        face = stack.pop()
        for neighbour in targets[starts[face] : starts[face + 1]].tolist():
            if neighbour not in seen and allowed[neighbour]:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen if goal <= seen else None


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
