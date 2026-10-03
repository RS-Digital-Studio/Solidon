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

import dataclasses
import hashlib
import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import numpy as np

from app.core import units
from app.core.geom.mesh import MeshData
from app.core.perceive.surfaces import PATCH_BLOCK, clipped_patches, planar_patch
from app.core.types import Feature, FeatureId, MeasureSource, SurfacePatch, Vec3
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
PARALLEL_AXES: float = units.exact_cos_degrees(0.5)

#: Wie gleich zwei Radien sein müssen, bezogen auf den größeren.
#:
#: Ein Prozent. Dieselbe Begründung wie oben — die Einpassung eines
#: 180-Grad-Bogens trifft den Radius auf ein Zehntausendstel genau; ein Prozent
#: lässt Raum für ein grobes Netz und trennt trotzdem Ø 5 von Ø 5,1.
SAME_RADIUS: float = 0.01

#: Wie weit die Normale eines Dreiecks von der Achse wegzeigen muss, damit es
#: zum **Mantel** gehört. Ein Grad: Deckel und Boden stehen senkrecht darauf
#: und fallen damit heraus, eine leicht schief tesselierte Flanke nicht.
ACROSS_THE_AXIS: float = units.exact_cos_degrees(89.0)

#: Wieviel eine Flanke von der Ebene abweichen darf, die sie sein soll —
#: als Anteil des Radius. Zwei Prozent decken die Sehne, zu der ein Netz den
#: Übergang zwischen Bogen und Flanke abtastet.
_FLANK_TOLERANCE: float = 0.02

#: Wie breit quer zur Mittellinie ein Mantel höchstens sein kann, um noch ein
#: Langloch zu sein — in Radien. **Eine Beweisgrenze, keine Toleranz.** Auf
#: dem Flankenweg liegen alle Ecken des Mantels um höchstens zwei Prozent
#: neben dem Radius, die Breite ist also rund zwei Radien. Auf dem Stadionweg
#: müssen beide Bögen — Halbkreise vom Radius des Paars — auf der Kontur
#: liegen; eine Kontur mit dem doppelten Radius oder mehr trägt einen
#: Halbkreis nicht innerhalb ihrer zwei Prozent, und ihre Breite wäre vier
#: Radien. Acht lassen beiden Wegen doppelten Abstand: Wer breiter ist, gibt
#: ``None``, und :func:`_wider_than_a_slot` spart ihm die Flutung.
_WIDER_THAN_ANY_SLOT: Final = 8.0


def _half_sphere_directions() -> np.ndarray:
    """Dreizehn feste Richtungen, eine je Gegenpaar der 26 Nachbarn einer Gitterzelle."""
    raw = np.array(
        [vector for vector in itertools.product((-1.0, 0.0, 1.0), repeat=3) if vector > (0.0,) * 3]
    )
    return np.asarray(raw / np.linalg.norm(raw, axis=1)[:, None], dtype=float)


#: Aus wie vielen Dreiecken eines Mantelstücks höchstens die Breitenschätzung
#: liest — jedes k-te der aufsteigend nummerierten. Eine Rechengrenze: Die
#: Auswahl bleibt eine Auswahl wirklicher Ecken, die Schätzung bleibt eine
#: untere Schranke, und eine schwächere Schranke kostet nur die Abkürzung.
_EXTENT_SAMPLE: Final = 4096

#: Die Richtungen, in denen :class:`_Components` die äußersten Ecken eines
#: Mantelstücks sucht — die Auswahl, an der :func:`_wider_than_a_slot` seine
#: Breite nach unten schätzt. Wie gut die Schätzung ist, ändert nichts an
#: ihrer Richtigkeit: Eine Auswahl wirklicher Ecken ist nie breiter als alle.
_EXTENT_DIRECTIONS: Final = _half_sphere_directions()


#: Was je Achse einmal gerechnet wird: die Quermaske, die Mantelstücke, der
#: Speicher, welcher Bogen an welches Stück grenzt — und je Bogen der von ihm
#: aus geflutete Mantel samt den Ecken seiner Flankenflächen
#: (:class:`_Reach`).
#:
#: **Alle gehören zusammen und nicht nebeneinander.** Die Nummern in den
#: Mantelstücken bedeuten für eine andere Achse etwas anderes; ein
#: Bogenspeicher daneben gab einem Paar die Etiketten einer fremden Achse
#: zurück und verlor dabei ein echtes Langloch. Dasselbe gilt für die Flutung:
#: Sie läuft über die Quermaske, und die hängt an der Achse.
class _Shells(NamedTuple):
    """Quermaske, Mantelstücke und die zwei Speicher einer Achse (siehe oben)."""

    across: np.ndarray
    """Je Fläche, ob sie quer zur Achse steht — ein Feld, keine Liste: Eine
    Liste aus Wahrheitswerten kostet je Fläche acht Byte, und am
    Beckenreiniger mit 701 900 Dreiecken gab es 28 verschiedene Masken."""
    labels: _Components
    touched: dict[int, frozenset[int]]
    reached: dict[int, _Reach]


class _Components:
    """Die zusammenhängenden Mantelstücke einer Quermaske — je Fläche eine Nummer.

    ``of[face]`` ist die Nummer des Stücks, ``-1`` für eine Fläche, die nicht
    quer steht. Dazu die Flächen je Stück, einmal nach Nummer sortiert: Wer die
    Flächen einiger Stücke braucht (:func:`_reach_of`), schneidet sie aus
    diesem Feld, statt über den ganzen Körper zu fragen.
    """

    __slots__ = ("extremes", "of", "order", "sorted_labels")

    def __init__(self, labels: np.ndarray) -> None:
        self.of = labels
        order = np.argsort(labels, kind="stable")
        order = order[labels[order] >= 0]
        self.order = order
        self.sorted_labels = labels[order]
        self.extremes: dict[int, np.ndarray] = {}

    def extreme_points(self, label: int, triangles: np.ndarray) -> np.ndarray:
        """Die äußersten Ecken eines Stücks in dreizehn festen Richtungen — je Stück einmal.

        Eine **Auswahl wirklicher Ecken**: Ihre Ausdehnung in einer Richtung
        ist nie größer als die des ganzen Stücks, also eine untere Schranke
        (:func:`_wider_than_a_slot`).
        """
        found = self.extremes.get(label)
        if found is None:
            faces = self.faces_of(frozenset((label,)))
            # Auch eine Auswahl der Dreiecke bleibt eine Auswahl wirklicher
            # Ecken: An einer Seitenwand mit 300 000 Dreiecken reicht jedes
            # k-te, um zu sehen, dass sie breiter ist als ein Langloch.
            step = -(-len(faces) // _EXTENT_SAMPLE)
            corners = triangles[faces[::step]].reshape(-1, 3)
            # Je Richtung eine zusammenhängende Zeile: ``argmax`` längs der
            # ersten Achse eines (n, 13)-Felds sprang durch den Speicher und
            # kostete an der Seitenwand des Beckenreinigers 118 ms je Stück.
            projected = _EXTENT_DIRECTIONS @ corners.T
            chosen = np.unique(np.concatenate((projected.argmax(axis=1), projected.argmin(axis=1))))
            found = corners[chosen]
            self.extremes[label] = found
        return found

    def faces_of(self, labels: frozenset[int]) -> np.ndarray:
        """Alle Flächen dieser Stücke, aufsteigend."""
        if not labels:
            return np.zeros(0, dtype=np.int64)
        wanted = np.fromiter(sorted(labels), dtype=np.int64, count=len(labels))
        starts = np.searchsorted(self.sorted_labels, wanted, side="left")
        ends = np.searchsorted(self.sorted_labels, wanted, side="right")
        parts = [self.order[start:end] for start, end in zip(starts, ends, strict=True)]
        return np.sort(np.concatenate(parts)) if parts else np.zeros(0, dtype=np.int64)


@dataclass(frozen=True, slots=True)
class _Reach:
    """Was ein Bogen an seiner Achse erreicht — einmal gerechnet, für jedes Paar gelesen.

    **Der Grund ist gemessen, und er ist der Unterschied zwischen zwei Minuten
    und zwei Sekunden.** An einem Hemmungsrad mit 531 Verrundungen
    (``REMONTOIRE ESCAPEMENT-06``, 19 870 Dreiecke, 15.09.2026) stehen 140
    Hohlkehlen der Zahnfüße auf **einer** Achse und grenzen an **ein**
    Mantelstück: den ganzen Umfang des Rades, 6 460 querstehende Flächen. Die
    Vorprüfung :func:`_shares_a_shell` ließ deshalb jedes der 9 751 Paare
    durch, und für jedes lief :func:`_connected_shell` denselben Umfang neu ab
    — 63 Millionen Nachbarschaftsbesuche, 62 Sekunden. Danach suchte
    ``max(..., key=lambda face: body.area_faces[face])`` die größte Flanke, je
    Paar über dieselben 6 460 Flächen und je Fläche durch den Cache von
    trimesh: weitere 35 Sekunden. Der Stadionfit über denselben Mantel kam
    hinzu. Zusammen 122 von 124 Sekunden der ganzen Erkennung.

    Nichts davon hängt am **Paar**. Die Flutung von einem Bogen aus über die
    querstehenden Flächen ist dieselbe, gleich welcher zweite Bogen gefragt
    wird; die Flanken ohne den ersten Bogen sind es ebenso. Was dem Paar
    gehört, ist allein der zweite Bogen — und der wird je Paar herausgenommen,
    nicht der Rest je Paar neu gebaut.
    """

    faces: np.ndarray
    """Der Mantel, der von diesem Bogen aus über querstehende Flächen erreichbar
    ist, den Bogen selbst eingeschlossen — aufsteigend. **Geteilt, nicht
    kopiert** — wer ihn bekommt, liest ihn und ändert ihn nicht."""
    rest: np.ndarray
    """Die Flächen des Mantels ohne den Bogen, sortiert — die Flanken, aus
    Sicht dieses Bogens."""
    corners: np.ndarray
    """Die Ecken dieser Flächen, je Fläche drei Zeilen, in der Reihenfolge von
    ``rest``."""
    stadiums: dict[int, Any] = field(default_factory=dict)
    """Der Stadionfit über den ganzen Mantel, je gewählter Leitflanke einmal —
    der Fit liest den Mantel und die Richtung dieser Flanke, sonst nichts."""


#: Welche Arten ein Langloch verschluckt, wenn eines gefunden wird.
#:
#: Dieselbe Menge und derselbe Grund wie bei der Wendel
#: (:data:`app.core.perceive.features._SWALLOWED_BY_A_HELIX`): die eingepassten
#: Grundformen, die **im Mantel** liegen und dort nichts mehr bezeichnen. Die
#: zwei Bögen sind der Regelfall; ein feines Netz kann daneben eine Kuppe oder
#: einen Kegelstumpf einpassen, und auch der gehört zum Loch.
#:
#: ``face`` steht seit dem 15.09.2026 dabei, und zwar für die **Flanken**: Am
#: Drehteil eines Minigolf-Satzes (152 000 Dreiecke) standen die zwei ebenen
#: Flanken eines Langlochs je einmal als Fläche und einmal als Teil des
#: Langlochs im Baum — ein Klick auf die Flanke bot *Bohren* an einer Wand, die
#: dem Langloch gehört. Der **Boden** eines Sacklangloch bleibt eine Fläche,
#: ohne Ausnahme im Text: Seine Normale zeigt entlang der Achse, er liegt gar
#: nicht im Mantel, und verschluckt wird nur, was vollständig im Mantel liegt.
SWALLOWED_BY_A_SLOT: Final[frozenset[str]] = frozenset(
    {"hole", "pin", "cone", "sphere", "torus", "fillet", "face"}
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
    diameter_source: MeasureSource = "fit"
    """Breite aus einem Stadionfit oder aus dem Abstand der wirklichen Flanken."""
    surface_patches: tuple[SurfacePatch, ...] = ()
    """Einzeln belegte Enden und Flanken, keine gemittelte Ersatzfläche."""

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
    slots.extend(slots_from_stadiums(mesh, stadiums, check_cancelled=check_cancelled))
    # Nach Position sortiert, damit die Nummer nicht daran hängt, über welchen
    # der zwei Wege ein Langloch gekommen ist (§21.2) — und bei gleicher Mitte
    # nach Maß, Tiefe und Richtung, zuletzt nach den Ecken: dieselbe Regel wie
    # für jede andere Nummer (:func:`app.core.perceive.features.numbering_order`).
    # Zwei gekreuzte Langlöcher teilen die Mitte, und dann entschied die
    # Reihenfolge, in der die Suche sie fand.
    from app.core.perceive.features import NUMBERING_DIGITS, _corner_key, numbering_order

    order = numbering_order(
        len(slots),
        (
            (lambda index: slots[index].centre, NUMBERING_DIGITS),
            (lambda index: (slots[index].diameter, slots[index].length), NUMBERING_DIGITS),
            (lambda index: (slots[index].depth,), NUMBERING_DIGITS),
            (lambda index: positive_axis(slots[index].direction), NUMBERING_DIGITS),
        ),
        lambda index: _corner_key(mesh.raw, np.asarray(slots[index].face_indices)),
    )
    slots = [slots[index] for index in order]
    # **Was beide Wege finden, ist ein Langloch** (Durchsicht 0.5.1,
    # BOHRUNG-05). Ein Mantel kann als Paar von Bögen und zugleich als Mantel
    # aus einem Stück gelesen werden; an einem entlang seiner Richtung
    # versetzten Langloch kamen so zwei mit denselben 138 Dreiecken heraus, und
    # die Auswertung fand für das versetzte keinen eindeutigen Zwilling — im Baum
    # stand es danach unter neuem Namen. Behalten wird das erste in der
    # Nummernfolge.
    distinct: set[frozenset[int]] = set()
    unique = []
    for slot in slots:
        faces = frozenset(int(index) for index in slot.face_indices)
        if faces in distinct:
            continue
        distinct.add(faces)
        unique.append(slot)
    slots = unique

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
            measure_sources={
                "diameter": slot.diameter_source,
                "length": "fit",
                "travel": "fit",
                "axis": "fit",
                "direction": "fit",
                "centre": "fit",
                "depth": "facets",
            },
            params={
                "diameter": slot.diameter,
                "length": slot.length,
                "travel": slot.travel,
                "axis": slot.axis,
                "direction": slot.direction,
                "centre": slot.centre,
                "depth": slot.depth,
                "through": slot.through,
            },
            face_indices=slot.face_indices,
            surface_patches=slot.surface_patches,
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
        # Derselbe geprüfte Konturfit liefert Kreis und Achse. Eine zweite
        # Einpassung über alle Ecken würde Flanken- und Sehnenpunkte wieder
        # als Kreisecken zählen und das Werkzeugmaß beim Öffnen verändern.
        radius = float(fit.radius)
        if radius <= tolerance:
            continue
        chosen, rim, has_flanks, arc_faces = _open_slot_shell(
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
        if not _reaches_through(
            body, mouth + normal * reach / 2.0, normal, axis, 0.0, reach, patch=chosen
        ):
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
        # Native Auskünfte stammen von den Originalflächen. Der hier bereits
        # akzeptierte Konturfit ergänzt ausschließlich deren unbelegten Anteil.
        native = clipped_patches(
            tuple(
                part
                for feature in kept.values()
                for part in feature.surface_patches
                if part.source == "native"
            ),
            selected,
            check_cancelled=check_cancelled,
        )
        native_faces = {index for part in native for index in part.face_indices}
        arc_indices = sorted(selected.intersection(arc_faces) - native_faces)
        parts = list(native)
        if arc_indices:
            parts.append(_arc_surface(fit.centre, fit.axis, fit.radius, arc_indices))
        parts.extend(
            _flank_surfaces(
                mesh,
                sorted(selected - set(arc_faces) - native_faces),
                centre,
                np.cross(axis, direction),
                check_cancelled=check_cancelled,
            )
        )
        kept = {
            key: feature
            for key, feature in kept.items()
            if not (
                feature.kind in SWALLOWED_BY_A_SLOT
                and feature.face_indices
                and selected.issuperset(feature.face_indices)
            )
        }
        sources: dict[str, MeasureSource] = {
            "diameter": "fit",
            "length": "fit",
            "travel": "fit",
            "axis": "fit",
            "direction": "fit",
            "centre": "fit",
            "depth": "facets",
            "arc_centre": "fit",
            "mouth_centre": "fit",
            "opening_normal": "facets",
        }
        params: dict[str, Any] = {
            "diameter": radius * 2.0,
            "length": radius * 2.0 + travel,
            "travel": travel,
            "axis": tuple(float(v) for v in axis),
            "direction": tuple(float(v) for v in direction),
            "centre": tuple(float(v) for v in middle),
            "depth": depth,
            "through": _reaches_through(body, centre, axis, direction, 0.0, depth, patch=indices),
            "open": True,
            "arc_centre": tuple(float(v) for v in centre),
            "mouth_centre": tuple(float(v) for v in mouth),
            "opening_normal": tuple(float(v) for v in normal),
        }
        kept[name] = Feature(
            id=name,
            kind="slot",
            provenance="detected",
            face_indices=indices,
            surface_patches=tuple(parts),
            measure_sources=sources,
            params=params,
        )
        covered.update(indices)
    return kept


def _scalar(value: float | Vec3) -> float:
    """Ein Trägermaß als Zahl; ein Vektor an dieser Stelle ist kein Radius."""
    return float(value) if isinstance(value, int | float) else math.nan


def native_open_slot_measures(feature: Feature) -> Feature:
    """Was ein nativer Träger belegt, trägt das offene Langloch auch als Maß — und nur das.

    Am exakten Kern kommt ein offenes Langloch über denselben Netzweg wie am
    Netz, und bis zum 20.09.2026 hieß jedes seiner Maße ``fit``, obwohl der
    Bogen als nativer Zylinder mit exaktem Radius und exakter Achse im
    Träger stand (P1.5, „keine pauschale Hochstufung"). Gelesen werden die
    **endgültigen** Träger, die ``brep.features_of`` zuletzt anhängt — native
    Originalflächen zuerst, der Netzfit nur für den unbelegten Rest. Deshalb
    einzeln:

    * Gibt es Zylinderträger und ist keiner davon ein Fit, deckt der native
      Mantel den ganzen Bogen: Durchmesser, Achse und Bogenmitte kommen aus
      ihm — der Radius exakt, die Achse im Sinn der gemessenen, die Mitte als
      Lot der gemessenen Mitte auf seine Achslinie. Zwei native Zylinder mit
      verschiedener Achse belegen nichts.
    * Gibt es Ebenenträger und ist keiner davon aus Facetten, liegen alle
      Flanken in nativen Ebenen; stehen die quer zur Achse und parallel
      zueinander, kommt die Richtung aus ihrer Normale, im Sinn der gemessenen.
    * Mündung, Weg, Länge und Tiefe hängen am Rand des Netzes und bleiben,
      was sie sind. Am reinen Netz gibt es keinen nativen Träger, und nichts
      ändert sich.
    """
    if feature.kind != "slot" or not feature.params.get("open") or not feature.surface_patches:
        return feature
    cylinders = [part for part in feature.surface_patches if part.kind == "cylinder"]
    planes = [part for part in feature.surface_patches if part.kind == "plane"]
    params: dict[str, Any] = dict(feature.params)
    sources: dict[str, MeasureSource] = dict(feature.measure_sources)
    axis = np.asarray(params["axis"], dtype=float)
    direction = np.asarray(params["direction"], dtype=float)
    centre = np.asarray(params["arc_centre"], dtype=float)
    travel = float(params["travel"])
    exact_axis = axis
    if cylinders and all(part.source == "native" for part in cylinders):
        first = cylinders[0]
        first_axis = np.asarray(first.params["axis"], dtype=float)
        first_radius = _scalar(first.params["radius"])
        agree = all(
            abs(float(np.asarray(part.params["axis"], dtype=float) @ first_axis)) >= PARALLEL_AXES
            and abs(_scalar(part.params["radius"]) - first_radius) <= first_radius * SAME_RADIUS
            for part in cylinders[1:]
        )
        # **Und der Träger muss den gemessenen Bogen treffen** — dieselbe
        # Achse im Vertrag von :data:`PARALLEL_AXES`, derselbe Radius im
        # Vertrag von :data:`SAME_RADIUS`. Bis zum 21.09.2026 genügte ein
        # Skalarprodukt ungleich null (Regel 6): Ein nativer Zylinder, der
        # um zwei Grad kippt oder anderthalb Millimeter größer ist, hätte
        # das Langloch als exakt beschriftet.
        measured_radius = float(params["diameter"]) / 2.0
        if (
            agree
            and abs(float(first_axis @ axis)) >= PARALLEL_AXES
            and abs(first_radius - measured_radius) <= measured_radius * SAME_RADIUS
        ):
            exact_axis = first_axis if float(first_axis @ axis) > 0.0 else -first_axis
            exact_axis = exact_axis / float(np.linalg.norm(exact_axis))
            origin = np.asarray(first.params["centre"], dtype=float)
            arc = origin + float((centre - origin) @ exact_axis) * exact_axis
            params["diameter"] = first_radius * 2.0
            params["length"] = first_radius * 2.0 + travel
            params["axis"] = tuple(float(v) for v in exact_axis)
            params["arc_centre"] = tuple(float(v) for v in arc)
            sources.update(diameter="native", axis="native", arc_centre="native")
    if planes and travel > EPS_GEOM and all(part.source == "native" for part in planes):
        across = math.sqrt(max(0.0, 1.0 - PARALLEL_AXES * PARALLEL_AXES))
        normals = [np.asarray(part.params["axis"], dtype=float) for part in planes]
        upright = all(abs(float(normal @ exact_axis)) <= across for normal in normals)
        parallel = all(abs(float(normal @ normals[0])) >= PARALLEL_AXES for normal in normals[1:])
        if upright and parallel:
            along = np.cross(exact_axis, normals[0])
            length = float(np.linalg.norm(along))
            if length > EPS_GEOM:
                along = along / length
                if float(along @ direction) < 0.0:
                    along = -along
                params["direction"] = tuple(float(v) for v in along)
                sources["direction"] = "native"
    if params == dict(feature.params) and sources == dict(feature.measure_sources):
        return feature
    return dataclasses.replace(feature, params=params, measure_sources=sources)


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
) -> tuple[np.ndarray, np.ndarray, bool, set[int]]:
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
    return selected, incident[first != second], not arc_faces.issuperset(chosen), arc_faces


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


def slots_from_stadiums(
    mesh: MeshData,
    stadiums: Sequence[tuple[Any, list[int]]],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Slot]:
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
        if check_cancelled is not None:
            check_cancelled()
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
                    body, centre, axis, direction, float(fit.travel), float(fit.depth), patch=patch
                ),
                face_indices=tuple(sorted(int(face) for face in patch)),
                swallowed=(),
                surface_patches=_stadium_surfaces(
                    mesh, fit, patch, check_cancelled=check_cancelled
                ),
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

    **Fits unter der Erkennungsauflösung siebt der Aufrufer aus**, so wie bei
    :func:`app.core.perceive.features.detect_fillets`: ``detect`` reicht
    ``_fillets_worth_naming`` herein, und dort steht die Frage einmal
    (``_too_small_to_make``). Wer die rohe Liste übergibt, bekommt auch
    Langlöcher unter dieser Auflösung, unabhängig von ihrer Herstellbarkeit.

    **Das Netz muss verschweißt sein.** Die Prüfung läuft über die
    Flächennachbarschaft, und eine roh geladene STL hat keine (siehe
    :func:`app.core.geom.mesh.face_components`). ``detect`` schweißt vorher
    über ``_one_body``; wer diese Funktion allein ruft, tut dasselbe.

    ``check_cancelled`` darf ``OperationCancelled`` werfen (§2.8), geprüft je
    Bogen der äußeren Schleife. Die Suche geht über die Paare von
    Innenverrundungen in fester Reihenfolge; **einzeln geprüft wird aber nur,
    wer überhaupt in Frage kommt** (:class:`_PairPlan`) — der Rest gäbe
    ``None`` und ändert nichts. Der Abbruch gehört zum gesamten Erkennungslauf,
    unabhängig davon, wie schnell dieser Teilschritt an einem einzelnen
    Prüfkörper ist. Der Ganzkörpertest mit vielen Taschen in
    ``tests/test_performance.py`` misst diesen Weg.
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
    neighbours = np.asarray(body.face_adjacency, dtype=np.int64)
    if not len(neighbours):
        return []
    # Flächeninhalte und Ecken einmal aus dem Cache von trimesh, nicht je Paar
    # und schon gar nicht je Fläche — siehe :class:`_Reach`.
    areas = np.asarray(body.area_faces, dtype=float)
    triangles = np.asarray(body.triangles, dtype=float)
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
    # :func:`_shells_for`. Die Nachbarschaftspaare reisen mit, weil die
    # Mantelstücke daraus als Zusammenhangskomponenten entstehen.
    masks: dict[bytes, _Shells] = {}
    axes = {index: _unit(fit.axis) for index, fit, _patch in candidates}
    plan = _PairPlan(candidates, axes, normals, graph, masks, neighbours)

    found: list[Slot] = []
    taken: set[int] = set()
    for first in range(len(candidates)):
        if check_cancelled is not None:
            check_cancelled()
        if candidates[first][0] in taken:
            continue
        for second in plan.partners(first):
            if candidates[second][0] in taken:
                continue
            slot = _slot_from(
                body,
                normals,
                areas,
                triangles,
                graph,
                masks,
                candidates[first],
                candidates[second],
                axes,
                check_cancelled=check_cancelled,
                pairs=neighbours,
            )
            if slot is not None:
                found.append(slot)
                taken.update(slot.swallowed)
                break
    return found


#: Auf wie viele Stellen die Achsen gerundet werden, um Bögen desselben
#: Werkzeugs zu einer Gruppe zu fassen (:class:`_PairPlan`). Eine
#: Rechengrenze, keine Toleranz: Die Gruppe darf nur, was ihr Randabstand
#: beweist, und wo er es nicht tut, wird jedes Paar einzeln gefragt.
_AXIS_GROUP_DIGITS: Final = 6

#: Wie weit eine Paarachse höchstens von der Achse ihrer Gruppe abliegen darf,
#: bevor die Rundung auf neun Stellen im Maskenspeicher (:func:`_shells_for`)
#: einen Eintrag einer anderen Achse liefert — mit Rechenreserve. Eine
#: Beweisgrenze für die Vorauswahl, keine Geometrietoleranz.
_KEY_SLACK: Final = 1e-8


class _PairPlan:
    """Welche zweiten Bögen für einen ersten überhaupt ein Langloch ergeben können.

    **Die Suche prüfte jedes Paar einzeln, und das war quadratisch** — an
    einer Taschenplatte mit 200 Taschen 319 600 Paare für 800 Bögen, gemessen
    3,6 s von 6,5 (22.09.2026). Zwei Vorfragen beantwortet diese Klasse für
    alle zweiten Bögen auf einmal, und beide lehnen nur ab, was
    :func:`_slot_from` auch ablehnen würde — die Antwort ist dieselbe, nur
    ohne den Umweg:

    * **Radius und Achse** als Feld: dieselbe Rechnung wie im Einzelweg für
      den Radius (Stelle für Stelle dieselben Gleitkommaschritte), und für die
      Achse eine Reserve unter :data:`PARALLEL_AXES` — den genauen Vergleich
      stellt der Einzelweg danach selbst.
    * **Das gemeinsame Mantelstück** in einer Gruppe gleichgerichteter Bögen:
      Liegt jede Flächennormale weit genug von der Querschwelle
      (:data:`ACROSS_THE_AXIS`) entfernt — weiter, als jede Paarachse der
      Gruppe von ihrer Gruppenachse abweicht —, ist die Quermaske für alle
      Paare dieselbe, und damit die Mantelstücke. Zwei Bögen ohne gemeinsames
      Stück hätten dann in :func:`_shares_a_shell` ``False`` bekommen. Fehlt
      dieser Beleg (eine Wand mit Formschräge nahe 89 Grad), fragt jedes Paar
      der Gruppe wie bisher selbst.

    Die Reihenfolge bleibt: Die zweiten Bögen kommen aufsteigend, und wer
    übersprungen wird, hätte ``None`` ergeben — der erste Treffer ist also
    derselbe, und ``taken`` wächst gleich.
    """

    def __init__(
        self,
        candidates: Sequence[tuple[int, Any, Sequence[int]]],
        axes: Mapping[int, np.ndarray | None],
        normals: np.ndarray,
        graph: tuple[np.ndarray, np.ndarray],
        masks: dict[bytes, _Shells],
        pairs: np.ndarray,
    ) -> None:
        count = len(candidates)
        self.radii = np.array([float(fit.radius) for _index, fit, _patch in candidates])
        valid = np.array([axes[index] is not None for index, _fit, _patch in candidates])
        self.valid = valid
        self.axes = np.array(
            [
                axes[index] if axes[index] is not None else np.zeros(3)
                for index, _fit, _patch in candidates
            ],
            dtype=float,
        )
        # Je Bogen seine Gruppe (``-1``: keine) und, wo die Gruppe belegt ist,
        # die Positionen der Bögen, mit denen er ein Mantelstück teilt.
        self.group = np.full(count, -1, dtype=np.int64)
        self.partners_in_group: dict[int, np.ndarray] = {}
        keys: dict[tuple[float, ...], list[int]] = {}
        for position in np.flatnonzero(valid).tolist():
            key = tuple(np.round(self.axes[position], _AXIS_GROUP_DIGITS).tolist())
            keys.setdefault(key, []).append(position)
        cosine = float(ACROSS_THE_AXIS)
        for number, members in enumerate(keys.values()):
            if len(members) < 2:
                continue
            reference = self.axes[members[0]]
            spread = float(np.linalg.norm(self.axes[members] - reference, axis=1).max())
            # Jede Paarachse liegt höchstens um die doppelte Streuung neben der
            # Gruppenachse; der Maskenspeicher kann dazu eine Achse liefern, die
            # auf neun Stellen gleich ist.
            reach = 2.0 * spread + _KEY_SLACK
            margin = float(np.min(np.abs(np.abs(normals @ reference) - cosine)))
            if margin <= 2.0 * reach:
                continue
            shells = _shells_for(normals, reference, graph, masks, pairs)
            owners: dict[int, list[int]] = {}
            touched_of: dict[int, frozenset[int]] = {}
            for position in members:
                index, _fit, patch = candidates[position]
                touched = _shells_touched(shells.labels, graph, patch, index, shells.touched)
                touched_of[position] = touched
                for label in touched:
                    owners.setdefault(label, []).append(position)
            for position in members:
                self.group[position] = number
                around: set[int] = set()
                for label in touched_of[position]:
                    around.update(owners[label])
                self.partners_in_group[position] = np.fromiter(
                    sorted(around), dtype=np.int64, count=len(around)
                )

    def partners(self, first: int) -> list[int]:
        """Die zweiten Bögen für diesen ersten, aufsteigend — nur, wer in Frage kommt."""
        seconds = np.arange(first + 1, len(self.radii), dtype=np.int64)
        if not len(seconds) or not self.valid[first]:
            return []
        radius = self.radii[first]
        others = self.radii[seconds]
        # Dieselbe Bedingung wie in :func:`_slot_from`, Stelle für Stelle.
        keep = np.abs(radius - others) <= SAME_RADIUS * np.maximum(radius, others)
        keep &= self.valid[seconds]
        keep &= np.abs(self.axes[seconds] @ self.axes[first]) >= PARALLEL_AXES - _KEY_SLACK
        group = self.group[first]
        if group >= 0:
            outside = self.group[seconds] != group
            keep &= outside | np.isin(seconds, self.partners_in_group[first])
        return [int(second) for second in seconds[keep]]


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
    areas: np.ndarray,
    triangles: np.ndarray,
    graph: tuple[np.ndarray, np.ndarray],
    masks: dict[bytes, _Shells],
    first: tuple[int, CylinderFit, list[int]],
    second: tuple[int, CylinderFit, list[int]],
    axes: Mapping[int, np.ndarray | None],
    *,
    check_cancelled: Callable[[], None] | None = None,
    pairs: np.ndarray | None = None,
) -> Slot | None:
    """Ob diese zwei Zylinderausschnitte ein Langloch sind — und welches.

    ``masks`` sammelt je Achse, was nur an ihr hängt — siehe
    :func:`_shells_for` und :class:`_Reach`. ``areas`` und ``triangles`` sind
    die Felder des ganzen Netzes, einmal geholt; ``pairs`` die
    Nachbarschaftspaare, aus denen die Mantelstücke entstehen.
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
    shells = _shells_for(normals, axis, graph, masks, pairs)
    across_mask, labels, touched, reached = shells
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
    # Ein Mantel, schon an einer Auswahl seiner Ecken breiter als jedes
    # Langloch, wird nicht geflutet (:func:`_wider_than_a_slot`).
    if _wider_than_a_slot(labels, touched[index_a], triangles, across, radius):
        return None

    own = reached.get(index_a)
    if own is None:
        own = _reach_of(shells, graph, patch_a, index_a, triangles)
        reached[index_a] = own
    faces = _connected_shell(across_mask, graph, patch_a, patch_b, reach=own)
    if faces is None:
        return None
    # Die Flanken aus Sicht dieses Paars: der geflutete Mantel ohne beide
    # Bögen. Ist der Mantel der gespeicherte, fehlt darin nur noch der zweite
    # Bogen, und der wird herausgenommen statt der Rest neu gesammelt.
    goal = np.fromiter((int(face) for face in patch_b), dtype=np.int64, count=len(patch_b))
    shared_reach = faces is own.faces
    if shared_reach:
        kept = ~np.isin(own.rest, goal, assume_unique=True)
        flank_indices = own.rest[kept]
        flank_corners = own.corners[np.repeat(kept, 3)]
    else:
        arcs = np.unique(np.concatenate((np.asarray(patch_a, dtype=np.int64), goal)))
        flank_indices = np.setdiff1d(faces, arcs, assume_unique=True)
        flank_corners = triangles[flank_indices].reshape(-1, 3)

    centre = (centre_a + centre_b) / 2.0
    diameter_source: MeasureSource = "fit"
    if not _corners_are_flanks(flank_corners, centre, across, radius):
        # Grobe Bogenflecken können Tangentenstücke mittragen und ihre
        # Nachbarn noch Bogenreste. Dann gilt der vorhandene Formnachweis
        # für den ganzen Mantel; die Fitgrenze wird nicht aufgeweitet.
        from app.core.perceive.features import STADIUM_TOLERANCE, fit_stadium

        if not len(flank_indices):
            return None
        flank = int(flank_indices[int(np.argmax(areas[flank_indices]))])
        along_flank = _unit(np.cross(axis, normals[flank]))
        if along_flank is None:
            return None
        # **Die Leitrichtung zeigt von Bogen zu Bogen, gleich welche Flanke sie
        # liefert.** Zwei Flanken haben entgegengesetzte Normalen, und bei
        # gleich großen Dreiecken entschied bisher die Reihenfolge einer Menge,
        # welche zuerst kam — und damit das Vorzeichen der Langlochrichtung.
        # Die Richtung von der ersten zur zweiten Bogenmitte ist dieselbe
        # Auskunft, die der glatte Weg oben gibt; hier gilt sie auch.
        if float(along_flank @ direction) < 0.0:
            along_flank = -along_flank
        # Derselbe Mantel und dieselbe Leitflanke ergeben denselben Fit — je
        # Bogen und Flanke einmal gerechnet, nicht je Paar (:class:`_Reach`).
        # **Auch die Absage wird gemerkt:** ``None`` ist am Hemmungsrad die
        # Regel, und ein Speicher, der ``None`` für „nicht gerechnet" hält,
        # rechnete 19 397 von 19 397 Fits neu — 27 s statt 2.
        if shared_reach and flank in own.stadiums:
            stadium = own.stadiums[flank]
        else:
            stadium = fit_stadium(
                body,
                faces.tolist(),
                direction_hint=(
                    float(along_flank[0]),
                    float(along_flank[1]),
                    float(along_flank[2]),
                ),
            )
            if shared_reach:
                own.stadiums[flank] = stadium
        if stadium is None or not stadium.good or not stadium.inward:
            return None
        # **Der Fit über den ganzen Mantel darf die Breite nicht unter das
        # Maß der Bögen drücken.** Er ist hier, weil die Bögen grob sind und
        # ihre Flanken deshalb nicht glatt aussehen — nicht, weil eine andere
        # Form gesucht wäre. Gemessen am Rahmen eines Schreibtisch-Organizers
        # (MakerWorld, 15.09.2026): zwei Bögen an den Enden einer 97 mm
        # langen, fast ebenen Wand, und der Stadionfit fand ein Stadion mit
        # Radius 0,003 mm — im Objektbaum stand „Langloch 0,01 auf 97,17 mm“.
        # Der Rückstand des Fits ist auf seinen Radius bezogen; ein Radius,
        # der um mehr als diese Toleranz unter dem der Bögen liegt,
        # beschreibt nicht dasselbe Loch.
        if stadium.radius < radius * (1.0 - STADIUM_TOLERANCE):
            return None
        centre = np.asarray(stadium.centre, dtype=float)
        axis = np.asarray(stadium.axis, dtype=float)
        direction = np.asarray(stadium.direction, dtype=float)
        travel = stadium.travel
        diameter = stadium.radius * 2.0
        parts = _stadium_surfaces(
            MeshData.of(body), stadium, faces.tolist(), check_cancelled=check_cancelled
        )
    else:
        # Die bereits geprüften ebenen Flanken tragen die wirkliche Breite.
        # Ihr Abstand bleibt auch nach erneutem Schneiden derselbe und muss
        # nicht aus zwei nur angenähert gleichen Kreisradien entstehen.
        flank_distances = (flank_corners - centre) @ across
        diameter = float(np.ptp(flank_distances))
        diameter_source = "facets"
        parts = (
            _arc_surface(fit_a.centre, fit_a.axis, fit_a.radius, patch_a),
            _arc_surface(fit_b.centre, fit_b.axis, fit_b.radius, patch_b),
            *_flank_surfaces(
                MeshData.of(body), flank_indices, centre, across, check_cancelled=check_cancelled
            ),
        )

    corners = triangles[faces].reshape(-1, 3) - centre
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
        through=_reaches_through(body, middle, axis, direction, travel, depth, patch=faces),
        face_indices=tuple(faces.tolist()),
        swallowed=(index_a, index_b),
        diameter_source=diameter_source,
        surface_patches=parts,
    )


def _point(vector: np.ndarray) -> Vec3:
    """Kernwerte ohne Anzeigerundung in den Trägervertrag übernehmen."""
    return float(vector[0]), float(vector[1]), float(vector[2])


def _arc_surface(centre: Vec3, axis: Vec3, radius: float, indices: Sequence[int]) -> SurfacePatch:
    """Das tatsächlich angenommene Ende behalten, auch wenn das Langlochmaße mittelt."""
    return SurfacePatch(
        "cylinder",
        {"centre": centre, "axis": axis, "radius": radius},
        tuple(int(index) for index in indices),
        "fit",
    )


def _flank_surfaces(
    mesh: MeshData,
    indices: Sequence[int] | np.ndarray,
    centre: np.ndarray,
    across: np.ndarray,
    *,
    check_cancelled: Callable[[], None] | None,
) -> tuple[SurfacePatch, ...]:
    """Die zwei wirklichen Flanken nachweisen; ein leicht gekrümmter Rest bleibt unbekannt."""
    if check_cancelled is not None:
        check_cancelled()
    if not len(indices):
        return ()
    numbers = np.asarray(indices, dtype=np.int64)
    body = mesh.raw
    sides = (np.asarray(body.triangles_center)[numbers] - centre) @ across
    result = []
    for mask in (sides < 0.0, sides > 0.0):
        chosen = numbers[mask]
        if not len(chosen):
            continue
        first = int(chosen[np.argmax(np.asarray(body.area_faces)[chosen])])
        origin = np.asarray(body.triangles_center[first])
        normal = np.asarray(body.face_normals[first])
        planar: list[int] = []
        for start in range(0, len(chosen), PATCH_BLOCK):
            if check_cancelled is not None:
                check_cancelled()
            block = chosen[start : start + PATCH_BLOCK]
            corners = np.asarray(body.vertices)[np.asarray(body.faces)[block]]
            on_plane = np.max(np.abs((corners - origin) @ normal), axis=1) <= EPS_GEOM
            planar.extend(int(index) for index in block[on_plane])
        part = planar_patch(
            mesh,
            planar,
            _point(body.triangles_center[first]),
            _point(body.face_normals[first]),
            check_cancelled=check_cancelled,
        )
        if part is not None:
            result.append(part)
    return tuple(result)


def _stadium_surfaces(
    mesh: MeshData,
    fit: Any,
    indices: Sequence[int],
    *,
    check_cancelled: Callable[[], None] | None,
) -> tuple[SurfacePatch, ...]:
    """Den fertigen Stadionfit an seinen geraden Nähten in Teilträger aufteilen.

    Ein Dreieck über einer Naht bekommt keinen geratenen Besitzer. Die
    Formparameter kommen vollständig aus der bereits akzeptierten Einpassung.
    """
    if check_cancelled is not None:
        check_cancelled()
    centre, axis, direction = (
        np.asarray(value, dtype=float) for value in (fit.centre, fit.axis, fit.direction)
    )
    across = np.cross(axis, direction)
    numbers = np.asarray(indices, dtype=np.int64)
    half = float(fit.travel) / 2.0
    # EPS_GEOM deckt ausschließlich Rundungsfehler genau auf der vorhandenen
    # Naht ab. Überschneidende Besitzer werden unten ausdrücklich verworfen.
    groups: list[list[int]] = [[], [], [], []]
    for start in range(0, len(numbers), PATCH_BLOCK):
        if check_cancelled is not None:
            check_cancelled()
        block = numbers[start : start + PATCH_BLOCK]
        triangles = np.asarray(mesh.raw.vertices)[np.asarray(mesh.raw.faces)[block]]
        along = (triangles - centre) @ direction
        sides = (triangles - centre) @ across
        left = np.max(along, axis=1) <= -half + EPS_GEOM
        right = np.min(along, axis=1) >= half - EPS_GEOM
        middle = (np.min(along, axis=1) >= -half - EPS_GEOM) & (
            np.max(along, axis=1) <= half + EPS_GEOM
        )
        masks = (
            left,
            right,
            middle & (np.max(sides, axis=1) < 0.0),
            middle & (np.min(sides, axis=1) > 0.0),
        )
        membership = sum(mask.astype(np.int8) for mask in masks)
        for members, mask in zip(groups, masks, strict=True):
            members.extend(int(face) for face in block[mask & (membership == 1)])
    result = []
    for index, group in enumerate(groups):
        if check_cancelled is not None:
            check_cancelled()
        selected = tuple(group)
        if not selected:
            continue
        sign = -1.0 if index % 2 == 0 else 1.0
        if index < 2:
            result.append(
                _arc_surface(
                    _point(centre + sign * half * direction), fit.axis, float(fit.radius), selected
                )
            )
        else:
            result.append(
                SurfacePatch(
                    "plane",
                    {
                        "centre": _point(centre + sign * float(fit.radius) * across),
                        "axis": _point(across),
                    },
                    selected,
                    "fit",
                )
            )
    return tuple(result)


def _unit(vector: Any) -> np.ndarray | None:
    """Ein Einheitsvektor, oder nichts, wenn er keine Länge hat."""
    value = np.asarray(vector, dtype=float)
    length = float(np.linalg.norm(value))
    if not math.isfinite(length) or length <= EPS_GEOM:
        return None
    return value / length


def _reach_of(
    shells: _Shells,
    graph: tuple[np.ndarray, np.ndarray],
    patch: Sequence[int],
    index: int,
    triangles: np.ndarray,
) -> _Reach:
    """Was ein Bogen an dieser Achse erreicht — die Hälfte der Paarprüfung, die
    nicht am Paar hängt (:class:`_Reach`).

    **Aus den Mantelstücken, nicht aus einem Lauf** (22.09.2026). Der Lauf
    darf querstehende Flächen und den Bogen selbst betreten; was er erreicht,
    ist der Bogen samt jedem Mantelstück, an das eine seiner Flächen grenzt —
    genau die Stücke, die :func:`_shells_touched` ohnehin nennt. Der
    Tiefenlauf in Python kostete am Beckenreiniger (701 900 Dreiecke, 47
    Innenbögen) 24 der 49 Sekunden eines Profils der Langlochsuche; die
    Stücke liegen nach Nummer sortiert bereit (:class:`_Components`).
    """
    own = np.unique(np.asarray(patch, dtype=np.int64))
    touched = _shells_touched(shells.labels, graph, patch, index, shells.touched)
    faces = np.union1d(own, shells.labels.faces_of(touched))
    rest = np.setdiff1d(faces, own, assume_unique=True)
    corners = triangles[rest].reshape(-1, 3) if len(rest) else np.empty((0, 3), dtype=float)
    return _Reach(faces=faces, rest=rest, corners=corners)


def _wider_than_a_slot(
    labels: _Components,
    touched: frozenset[int],
    triangles: np.ndarray,
    across: np.ndarray,
    radius: float,
) -> bool:
    """Ob die Mantelstücke am ersten Bogen quer zur Mittellinie breiter sind als jedes Langloch.

    Der Mantel eines Paars enthält jedes Stück, an das der erste Bogen grenzt;
    ist schon eine Auswahl ihrer Ecken quer zur Mittellinie breiter als
    :data:`_WIDER_THAN_ANY_SLOT` Radien, ist es der Mantel erst recht, und
    weder Flanken- noch Stadionweg ergäben ein Langloch — die Antwort wäre
    dieselbe, nur nach der Flutung. Der Anlass (22.09.2026): Am Beckenreiniger
    mit 701 900 Dreiecken grenzen 47 Innenbögen an **eine** Seitenwand, und
    jedes Paar flutete sie, vereinigte sie mit seinem Bogen und prüfte ihre
    Ecken als Flanken — 5,4 und 0,7 der 10 Sekunden, die nach dem Umbau der
    Mantelstücke noch übrig waren.
    """
    if not touched:
        return False
    points = np.concatenate([labels.extreme_points(label, triangles) for label in sorted(touched)])
    reach = points @ across
    return float(reach.max() - reach.min()) > _WIDER_THAN_ANY_SLOT * radius


def _flooded(
    across: np.ndarray,
    graph: tuple[np.ndarray, np.ndarray],
    seeds: set[int],
    allowed: set[int],
    seen: set[int],
) -> set[int]:
    """Der Tiefenlauf über querstehende Flächen und ``allowed``, von ``seeds``
    aus, in ``seen`` hinein — nur noch für den seltenen Weg, auf dem ein
    zweiter Bogen nicht ganz im Mantel des ersten liegt
    (:func:`_connected_shell`)."""
    starts, targets = graph
    stack = list(seeds)
    while stack:
        face = stack.pop()
        for neighbour in targets[starts[face] : starts[face + 1]].tolist():
            if neighbour not in seen and (across[neighbour] or neighbour in allowed):
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def _adjacent_faces(graph: tuple[np.ndarray, np.ndarray], faces: np.ndarray) -> np.ndarray:
    """Die Nachbarflächen gewählter Flächen, je Fläche in ihrer Reihenfolge, mit Wiederholungen."""
    starts, targets = graph
    counts = starts[faces + 1] - starts[faces]
    offsets = np.repeat(starts[faces] - np.cumsum(counts) + counts, counts)
    return np.asarray(targets[offsets + np.arange(int(counts.sum()))], dtype=np.int64)


def _connected_shell(
    across: np.ndarray,
    graph: tuple[np.ndarray, np.ndarray],
    patch_a: Sequence[int],
    patch_b: Sequence[int],
    *,
    reach: _Reach | None = None,
) -> np.ndarray | None:
    """Der Mantel, der beide Bögen verbindet, aufsteigend — oder nichts.

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
    Bogenflecken.

    ``reach`` ist der Mantel vom ersten Bogen aus (:class:`_Reach`). **Die
    Antwort ist dieselbe wie die des Laufs, und zwar genau:** Der Lauf darf
    querstehende Flächen und die zwei Bögen betreten. Alles, was er ohne den
    zweiten Bogen erreicht, steht in ``reach``; liegt der zweite Bogen
    vollständig darin, kann von ihm aus nichts Neues erreichbar sein — seine
    querstehenden Nachbarn stehen schon darin, und andere darf der Lauf nur
    betreten, wenn sie zu einem der Bögen gehören. Dann ist die Antwort
    ``reach.faces`` selbst, **geteilt und nicht kopiert**. Liegt er nicht
    vollständig darin, läuft der Rest von den Bogenflächen aus weiter, die an
    ``reach`` grenzen — genau die, über die der ursprüngliche Lauf ihn als
    Erstes betreten hätte.
    """
    goal = np.unique(np.asarray(patch_b, dtype=np.int64))
    goal_set = set(goal.tolist())
    own_a = {int(face) for face in patch_a}
    if reach is None:
        seen = _flooded(across, graph, own_a, own_a | goal_set, set(own_a))
        return _sorted_faces(seen) if goal_set <= seen else None
    base = reach.faces
    inside = np.isin(goal, base, assume_unique=True)
    if bool(inside.all()):
        return base
    starts, _targets = graph
    counts = starts[goal + 1] - starts[goal]
    beside = np.isin(_adjacent_faces(graph, goal), base)
    owners = np.repeat(np.arange(len(goal)), counts)
    touching = np.zeros(len(goal), dtype=bool)
    np.logical_or.at(touching, owners, beside)
    seeds = set(goal[inside | touching].tolist())
    if not seeds:
        return None
    seen = _flooded(across, graph, seeds, own_a | goal_set, set(base.tolist()) | seeds)
    return _sorted_faces(seen) if goal_set <= seen else None


def _sorted_faces(faces: set[int]) -> np.ndarray:
    """Eine Menge von Flächen als aufsteigendes Feld."""
    return np.fromiter(sorted(faces), dtype=np.int64, count=len(faces))


def _shell_labels(across: np.ndarray, pairs: np.ndarray) -> _Components:
    """Die zusammenhängenden Mantelstücke einer Achse, je Fläche eine Nummer.

    Flächen, die nicht quer stehen, bekommen ``-1``. Zwei Bögen können nur
    dann ein Langloch sein, wenn sie an **dasselbe** Stück grenzen — und das
    steht damit fest, ohne für jedes Paar zu laufen (:func:`_shares_a_shell`).

    **Als Zusammenhangskomponenten des Quergraphen, nicht als Lauf in
    Python** (22.09.2026). Der Lauf besuchte jede querstehende Fläche einzeln
    und kostete am Beckenreiniger (701 900 Dreiecke) je Maske 0,7 s — bei 28
    verschiedenen Masken 20 der 49 Sekunden eines Profils. Dieselbe Zerlegung
    rechnet ``scipy`` in C; die Nummern sind andere, und das ist gleichgültig:
    Gefragt wird nur, ob zwei Flächen dieselbe tragen.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    count = len(across)
    inner = pairs[across[pairs[:, 0]] & across[pairs[:, 1]]]
    graph = coo_matrix(
        (np.ones(len(inner), dtype=np.int8), (inner[:, 0], inner[:, 1])), shape=(count, count)
    )
    _number, labels = connected_components(graph, directed=False)
    return _Components(np.where(across, np.asarray(labels, dtype=np.int64), -1))


def _pairs_of(graph: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    """Die Nachbarschaftspaare zurück aus der Nachbarschaft — jede Naht zweimal."""
    starts, targets = graph
    sources = np.repeat(np.arange(len(starts) - 1, dtype=np.int64), np.diff(starts))
    return np.column_stack((sources, np.asarray(targets, dtype=np.int64)))


def _shells_touched(
    labels: _Components,
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
        found = labels.of[_adjacent_faces(graph, np.asarray(patch, dtype=np.int64))]
        ready = frozenset(np.unique(found[found >= 0]).tolist())
        cache[index] = ready
    return ready


def _shares_a_shell(
    labels: _Components,
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
    pairs: np.ndarray | None = None,
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

    Die Mantelstücke aus :func:`_shell_labels` kommen im selben Zug, weil sie
    an derselben Achse hängen — und **der Bogenspeicher liegt daneben im
    selben Eintrag**: Seine Nummern sind die aus ``labels``, und die bedeuten
    für eine andere Achse etwas anderes. ``pairs`` sind die
    Nachbarschaftspaare, aus denen die Stücke entstehen; ohne sie werden sie
    aus ``graph`` zurückgewonnen.
    """
    key = np.round(np.ascontiguousarray(axis, dtype=float), 9).tobytes()
    ready = cache.get(key)
    if ready is None:
        # **Und hinter der Achse steht die Maske selbst als Schlüssel.** An
        # einer eingelesenen STL streuen die Bogenachsen nicht im letzten Bit,
        # sondern in der sechsten Stelle — am Hemmungsrad aus :class:`_Reach`
        # waren es 221 verschiedene Achsen für 531 Bögen, und für jede liefen
        # Mantelstücke und Flutungen neu, obwohl 221-mal dieselbe Maske
        # herauskam. Alles hier hängt nur an ihr; zwei Achsen mit derselben
        # Maske bekommen deshalb denselben Eintrag. Damit ein Maskenschlüssel
        # nie wie ein Achsenschlüssel aussieht, trägt er eine Marke vorn — ein
        # Netz mit genau 24 Dreiecken ist nichts Seltenes. Der Schlüssel ist
        # der Abdruck der Maske und nicht die Maske: 28 Masken zu je 701 900
        # Bytes hielt der Speicher am Beckenreiniger sonst als Schlüssel fest.
        crossing = np.abs(normals @ axis) <= ACROSS_THE_AXIS
        mask_key = b"mask:" + hashlib.blake2b(crossing.tobytes(), digest_size=16).digest()
        ready = cache.get(mask_key)
        if ready is None:
            if pairs is None:
                pairs = _pairs_of(graph)
            ready = _Shells(crossing, _shell_labels(crossing, pairs), {}, {})
            cache[mask_key] = ready
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
    corners = np.asarray(body.triangles, dtype=float)[rest].reshape(-1, 3)
    return _corners_are_flanks(corners, centre, across, radius)


def _corners_are_flanks(
    corners: np.ndarray, centre: np.ndarray, across: np.ndarray, radius: float
) -> bool:
    """Dieselbe Frage wie :func:`_flanks_are_flat`, an den schon gesammelten
    Ecken der Flanken — leer heißt: keine Flanke, also nein."""
    if not len(corners):
        return False
    distance = np.abs((corners - centre) @ across)
    return bool(np.all(np.abs(distance - radius) <= _FLANK_TOLERANCE * radius))


def _reaches_through(
    body: Any,
    centre: np.ndarray,
    axis: np.ndarray,
    direction: np.ndarray,
    travel: float,
    depth: float,
    *,
    patch: Sequence[int] | np.ndarray | None = None,
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
    # Ein separat eingelesener Stift kann vor der Mündung stehen. Er ändert
    # nicht die Topologie des Langlochs im Träger. Echte Böden und Stege sind
    # mit seinen Mantelflächen verbunden; nur deren Komponenten zählen.
    corners = np.asarray(body.triangles, dtype=float)
    if patch is not None and len(patch):
        from app.core.geom.mesh import face_components

        groups = face_components(body)
        if len(groups) > 1:
            selected = np.zeros(len(body.faces), dtype=bool)
            selected[np.asarray(patch, dtype=np.intp)] = True
            carriers = [group for group in groups if bool(selected[group].any())]
            corners = corners[np.concatenate(carriers)]
    corners = corners - centre
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
