"""Was **zusammen** gehört: Nachbarschaften zwischen erkannten Merkmalen
(Bauplan §21.1, §21.2).

``features.py`` beantwortet „was ist das hier" — eine Bohrung, ein Zapfen, eine
Verrundung. Diese Datei beantwortet die Frage danach, und es ist eine andere:
**gehören zwei davon zusammen, und was folgt daraus?** Eine Senkung über einer
Bohrung ist keine zweite Bohrung; ein Zapfen um eine Bohrung ist ein Rohr mit
einer Wand. Wer eines von beiden ändert, ändert das andere mit — und genau das
sagte ihm bisher niemand.

**Warum ein eigenes Modul.** ``features.py`` ist mit 2200 Zeilen das größte
Modul des Kerns, und die Nachbarschaften werden nicht bei einer bleiben:
Senkung über Bohrung, Rohr, Bohrungsraster, Bohrung durch zwei Wände. Vier
davon dort einzuhängen hieße, eine Datei weiter wachsen zu lassen, die schon
heute niemand am Stück liest. Die Erkennung einzelner Merkmale und die Frage,
wie sie zueinander stehen, sind zwei Aufgaben (Vereinbarung 3d-druck-f9 /
3d-druck-11, 04.09.2026).

**Die Richtung der Importe ist einseitig:** Diese Datei liest ``features.py``,
nie umgekehrt. Sie benutzt dessen Schwellen (:data:`SINK_AXIS_LIMIT`,
:data:`SINK_FIT_LIMIT`) und nicht eigene — zwei Achsenprüfungen mit zwei Zahlen
wären zwei Antworten auf dieselbe Frage.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray

from app.core.deferred import cKDTree, trimesh
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.perceive.actions import ACTION_ORDER, feature_value_source
from app.core.perceive.features import EPS_ANGLE, SINK_AXIS_LIMIT, SINK_FIT_LIMIT, _one_body
from app.core.registry import REGISTRY
from app.core.types import Feature, FeatureId
from app.core.units import EPS_DISPLAY, EPS_GEOM

_log = get_logger(__name__)

#: Wie viel zwei koaxiale Merkmale sich längs überdecken müssen, damit das eine
#: **im** anderen steckt und nicht an seiner Mündung sitzt — als Anteil des
#: kürzeren der beiden.
#:
#: **Was diese Zahl trennt, ist gemessen und nicht das, was zuerst plausibel
#: klang.** Eine Senkung scheidet schon eine Bedingung früher aus: Ein Kegel
#: führt keine ``depth``, und ohne sie lässt sich keine Überdeckung rechnen.
#: Die erste Fassung dieses Kommentars nannte die Senkung als den Fall, den
#: diese Schwelle trennt — die Gegenprobe hat es widerlegt: Mit
#: ausgebauter Bedingung blieben alle Tests grün, weil keiner sie erreichte.
#:
#: Der Fall, den sie wirklich trennt, ist ein **koaxialer Zapfen über einer
#: Bohrung**: eine Platte mit Sackloch Ø 16 auf fünf Millimetern und darauf,
#: auf derselben Achse, ein Zapfen Ø 28. Vier Bedingungen treffen zu — gleiche
#: Achse, Mitten auf einer Linie, der Zapfen weiter, genau einer ein Hohlraum.
#: Er umgibt die Bohrung trotzdem nicht: Zwischen beiden liegen fünf
#: Millimeter massives Material. Ohne diese Zahl stünde dort eine Wand von
#: 6 mm, die es nirgends gibt.
#:
#: Beide echten Fälle liegen weit von ihr entfernt: Am Besenhalter
#: (``broomholdervcd_d35mm.stl``) überdecken sich die Bohrung Ø 34,00 und der
#: Zapfen Ø 40,80 über 27,0 von 27,2 mm, also zu **99 Prozent**; der Zapfen
#: über dem Sackloch zu **null**. Die Hälfte liegt dazwischen und ist keine
#: knappe Wahl.
SLEEVE_OVERLAP = 0.5


@dataclass(frozen=True, slots=True)
class Sleeve:
    """Eine Bohrung und das Material, das sie umgibt — ein Rohr.

    Die Wandstärke ist der Grund, aus dem es diese Auskunft gibt: Sie steht in
    keinem der beiden Merkmale, sie entsteht erst aus ihrem Verhältnis. Wer den
    Innendurchmesser um vier Millimeter vergrößert, nimmt der Wand zwei — und
    unter der Mindestwandstärke des Materials ist das Teil nicht mehr druckbar,
    ohne dass sich an einer einzelnen Zahl etwas Auffälliges gezeigt hätte.
    """

    bore: FeatureId
    """Die Bohrung — der Hohlraum innen."""
    wall: FeatureId
    """Das Merkmal, das sie umgibt — Materie, kein zweiter Hohlraum."""
    bore_diameter: float
    outer_diameter: float
    overlap: float
    """Wie weit die beiden sich längs der Achse überdecken, als Anteil des
    kürzeren — die Zahl, die das Rohr von der Senkung trennt."""

    @property
    def thickness(self) -> float:
        """Die Wand zwischen beiden, in Millimetern.

        Der halbe Unterschied der Durchmesser, denn beide sind koaxial: Was
        außen dazukommt, verteilt sich auf zwei Seiten.
        """
        return (self.outer_diameter - self.bore_diameter) / 2.0


FeatureGroupEvidence = Literal[
    "same_target_dimensions",
    "complete_surface_patch",
    "parallel_axes",
    "shared_boundary_role",
    "translation_consistent",
]
"""Welcher geometrische Nachweis eine Sammelgruppe trägt."""

FeatureGroupReason = Literal[
    "selected_feature_unavailable",
    "action_not_applicable",
    "ambiguous_cavity_chain",
    "cavity_topology_unavailable",
    "dimensions_unavailable",
    "complete_shape_unavailable",
    "orientation_unavailable",
    "relative_position_unavailable",
]
"""Warum eine mögliche Zugehörigkeit nicht sicher entschieden werden konnte."""


@dataclass(frozen=True, slots=True)
class FeatureGroupMember:
    """Ein Ziel der Sammelhandlung und der vollständig zugehörige Umfang."""

    target: FeatureId
    scope: tuple[FeatureId, ...]


@dataclass(frozen=True, slots=True)
class FeatureGroupUncertainty:
    """Merkmale, deren Zugehörigkeit der Kern nicht behaupten darf."""

    feature_ids: tuple[FeatureId, ...]
    reason: FeatureGroupReason


@dataclass(frozen=True, slots=True)
class FeatureActionGroup:
    """Die belegte, für genau eine Operation geeignete Sammelgruppe.

    ``members`` steht in kanonischer ID-Reihenfolge und enthält das gewählte
    Merkmal, wenn dessen Umfang sicher ist. Die Oberfläche kann es für ihren
    bisherigen Signalvertrag an die erste Stelle stellen; die Kernauskunft
    selbst bleibt dadurch unabhängig davon, von welchem Mitglied sie gefragt
    wurde.
    """

    id: str
    action: str
    selected: FeatureId
    members: tuple[FeatureGroupMember, ...] = ()
    evidence: tuple[FeatureGroupEvidence, ...] = ()
    uncertain: tuple[FeatureGroupUncertainty, ...] = ()


def axis_of(feature: Feature) -> Any | None:
    """Die Achse eines Merkmals als Einheitsvektor, oder nichts."""
    raw = feature.params.get("axis")
    if raw is None:
        return None
    axis = np.asarray(raw, dtype=float)
    length = float(np.linalg.norm(axis))
    if axis.shape != (3,) or length <= EPS_GEOM:
        return None
    return axis / length


def centre_of(feature: Feature) -> Any | None:
    """Die Mitte eines Merkmals, oder nichts."""
    raw = feature.params.get("centre")
    if raw is None:
        return None
    centre = np.asarray(raw, dtype=float)
    return centre if centre.shape == (3,) else None


def is_a_cavity(feature: Feature) -> bool:
    """Ist dieses Merkmal ein Hohlraum oder Materie?

    Wortgleich mit ``prepare_ops._feature_is_a_cavity``, und das bleibt
    absichtlich so: Der Kern der Wahrnehmung darf die Geometrieschicht nicht
    importieren. Ändert sich die Regel, ändert sie sich an beiden Stellen —
    ``tests/test_features.py`` hält sie zusammen.
    """
    if feature.kind == "hole":
        return True
    if feature.kind == "pin":
        return False
    return bool(feature.params.get("recess", False))


def sleeve_at(feature: Feature, features: Mapping[FeatureId, Feature]) -> Sleeve | None:
    """Das Rohr, zu dem dieses Merkmal gehört — von welcher Seite man auch kommt.

    **Beide Seiten, und das ist keine Bequemlichkeit.** Der Kunde klickt
    entweder auf die Bohrung oder auf den Zapfen; eine Auskunft, die nur eine
    der beiden Richtungen kennt, ist an der anderen Hälfte der Klicks stumm.
    Gemessen am Besenhalter: ``hole_2`` Ø 34,00 und ``pin_1`` Ø 40,80 stehen
    beide im Objektbaum, beide lassen sich anklicken, und beide ändern dieselbe
    Wand von 3,40 mm.

    Fünf Bedingungen, vier davon dieselben wie bei
    ``features.widening_at_the_mouth`` — mit Absicht, denn es ist dieselbe
    Frage nach der Achse:

    * dieselbe Achsrichtung (:data:`SINK_AXIS_LIMIT`),
    * die Mitten auf **einer** Linie und nicht bloß parallel
      (:data:`SINK_FIT_LIMIT`),
    * der eine weiter als der andere,
    * genau einer von beiden ist ein Hohlraum — zwei Bohrungen ineinander gibt
      es nicht, und zwei Zapfen ineinander wären ein Körper und kein Rohr,
    * und sie überdecken sich **längs** (:data:`SLEEVE_OVERLAP`). Ein Zapfen
      über einer Bohrung ist koaxial, weiter und aus Materie — und umgibt sie
      trotzdem nicht.

    ``None``, wo es keinen Partner gibt oder die Zahlen für die Frage nicht
    reichen — ein Merkmal ohne Achse, ohne Mitte, ohne Durchmesser oder ohne
    Tiefe. Nicht geraten wird hier so wenig wie sonst (Regel 21): Ohne Tiefe
    lässt sich die Überdeckung nicht messen, und ohne sie wäre jede Senkung ein
    Rohr.
    """
    axis = axis_of(feature)
    centre = centre_of(feature)
    diameter = float(feature.params.get("diameter") or 0.0)
    depth = float(feature.params.get("depth") or 0.0)
    if axis is None or centre is None or diameter <= EPS_GEOM or depth <= EPS_GEOM:
        return None

    inside = is_a_cavity(feature)
    best: Sleeve | None = None
    for candidate in features.values():
        if candidate.id == feature.id or is_a_cavity(candidate) == inside:
            continue
        other_axis = axis_of(candidate)
        other_centre = centre_of(candidate)
        other_diameter = float(candidate.params.get("diameter") or 0.0)
        other_depth = float(candidate.params.get("depth") or 0.0)
        if other_axis is None or other_centre is None:
            continue
        if other_diameter <= EPS_GEOM or other_depth <= EPS_GEOM:
            continue
        # Die Höhlung muss die engere sein. Andersherum steckt der Zapfen in
        # der Bohrung, und das ist kein Rohr, sondern ein Stift in einem Loch —
        # eine Passung, keine Wand.
        if inside and other_diameter <= diameter:
            continue
        if not inside and other_diameter >= diameter:
            continue
        if abs(float(axis @ other_axis)) < math.cos(math.radians(SINK_AXIS_LIMIT)):
            continue
        # Alle Lagewerte werden aus Sicht der Bohrung gerechnet. Sie ist bei
        # beiden Aufrufrichtungen dasselbe Merkmal; die Achsen dürfen innerhalb
        # der Erkennungsschwelle leicht voneinander abweichen, und dann würden
        # zwei wechselnde Bezugsachsen sonst zwei verschiedene Überdeckungen
        # liefern.
        bore_axis = axis if inside else other_axis
        bore_centre = centre if inside else other_centre
        wall_centre = other_centre if inside else centre
        bore_depth = depth if inside else other_depth
        wall_depth = other_depth if inside else depth
        offset = wall_centre - bore_centre
        along = float(offset @ bore_axis)
        across = offset - along * bore_axis
        bore_radius = (diameter if inside else other_diameter) / 2.0
        across_limit = bore_radius * SINK_FIT_LIMIT
        if float(np.linalg.norm(across)) > across_limit:
            continue

        share = _overlap(along, bore_depth, wall_depth)
        if share < SLEEVE_OVERLAP:
            continue
        bore_diameter = diameter if inside else other_diameter
        outer_diameter = other_diameter if inside else diameter
        found = Sleeve(
            bore=feature.id if inside else candidate.id,
            wall=candidate.id if inside else feature.id,
            bore_diameter=bore_diameter,
            outer_diameter=outer_diameter,
            overlap=share,
        )
        # **Die dünnste Wand gewinnt.** Stehen mehrere Hüllen um dieselbe
        # Bohrung — ein Rohr in einem Rohr —, ist die innerste diejenige, die
        # als Erste zu dünn wird. Eine beliebige davon zu nennen hieße, die
        # Aussage vom Zufall der Reihenfolge abhängig zu machen.
        if best is None or found.thickness < best.thickness:
            best = found

    if best is not None:
        _log.debug("sleeve %s in %s: wall %.2f mm", best.bore, best.wall, best.thickness)
    return best


def _overlap(along: float, depth: float, other_depth: float) -> float:
    """Wie weit zwei Strecken auf derselben Achse sich überdecken — als Anteil
    der kürzeren.

    Beide Merkmale werden um ihre Mitte gemessen (``centre`` ± halbe Tiefe);
    ``along`` ist der Abstand der Mitten längs der Achse. Der Anteil der
    kürzeren und nicht der längeren: Eine kurze Buchse in einem langen Rohr
    steckt vollständig darin, und dass das Rohr darüber hinausragt, ändert
    daran nichts.
    """
    shorter = min(depth, other_depth)
    if shorter <= EPS_GEOM:
        return 0.0
    reach = (depth + other_depth) / 2.0 - abs(along)
    return max(0.0, min(reach, shorter)) / shorter


def widening_at_the_mouth(
    feature: Feature, features: Mapping[FeatureId, Feature], *, mesh: MeshData | None = None
) -> Feature | None:
    """Das Merkmal, das sich über der Öffnung dieses Merkmals aufweitet — die
    Senkung über einer Bohrung.

    **Warum es diese Auskunft braucht.** ``resize_hole`` und
    ``resize_feature`` ändern genau ein Merkmal. An einer Bohrung mit Senkung
    heißt das: Die Bohrung wächst, die Senkung bleibt stehen, und im Teil
    entsteht eine Stufe, die niemand gewollt hat — ohne einen Satz darüber.
    Gemeldet von Robert am 04.09.2026 an einem heruntergeladenen Halter, und
    ``geom.prepare_ops._feature_body`` sagt seit dem 03.09.2026 im Docstring, was
    fehlt: „Bis Solidon die Nachbarschaft kennt, ist die Absage die richtige
    Antwort." Das hier ist die Nachbarschaft.

    **Vier Bedingungen, und keine davon ist geraten** — die Schwellen sind
    dieselben, mit denen die Erkennung schon heute entscheidet, ob zwei
    Flächen zu einer Bohrung gehören (:data:`SINK_AXIS_LIMIT`,
    :data:`SINK_FIT_LIMIT`):

    * dieselbe Achsrichtung,
    * die Mitten auf **einer** Linie und nicht bloß parallel — zwei Bohrungen
      nebeneinander haben dieselbe Richtung und sind trotzdem zwei,
    * die Mitte des Nachbarn liegt auf der Strecke der Bohrung (mit derselben
      Toleranz an beiden Enden), denn eine Senkung sitzt an einer ihrer
      Mündungen und nicht drei Zentimeter daneben,
    * er ist **weiter** — eine Senkung, die enger wäre als ihre Bohrung, gibt
      es nicht; ohne diese Bedingung fände eine durchgehende Bohrung ihre
      eigene Fortsetzung in der nächsten Wand,
    * und er ist ebenfalls ein **Hohlraum**. Das war der eine Fehlgriff der
      ersten Fassung, und zwar an Roberts eigenem Halter: Die Bohrung Ø 34
      steckt im Zapfen Ø 40,80, beide auf derselben Achse, und die Mitte des
      Zapfens liegt in ihrer Strecke. Ein Zapfen ist aber Materie und keine
      Aufweitung einer Öffnung — er umgibt die Bohrung, er mündet nicht in
      sie. Gefragt wird wie in ``prepare_ops._feature_is_a_cavity``: ``hole``
      immer, ``pin`` nie, und bei Kegel und Kugel entscheidet ``recess``.

    Gemessen an ``broomholdervcd_d35mm.stl`` (Robert, 04.09.2026):
    ``hole_1`` Ø 5,44 mit Mitte (-49,60 | 31,28 | 0) und ``cone_1`` Ø 8,16 mit
    Mitte (-49,60 | 28,56 | 0), beide auf der Achse (0 | -1 | 0). Der Abstand
    längs ist 2,72 mm und damit genau die Tiefe der Bohrung; quer ist er null.
    Dasselbe am zweiten Paar. An der Platte des Korpus (vier Bohrungen ohne
    Senkung) findet die Funktion nichts.

    ``None``, wo es keinen Nachbarn gibt oder die Zahlen für die Frage nicht
    reichen — ein Merkmal ohne Achse, ohne Tiefe oder ohne Durchmesser.
    """
    if mesh is not None:
        chain = cavity_chain_at(feature, features, mesh)
        if chain is None or len(chain) != 2 or chain[0].id != feature.id:
            return None
        return chain[1]
    axis = axis_of(feature)
    centre = centre_of(feature)
    diameter = float(feature.params.get("diameter") or 0.0)
    depth = float(feature.params.get("depth") or 0.0)
    if axis is None or centre is None or diameter <= EPS_GEOM:
        return None
    if not is_a_cavity(feature):
        return None

    radius = diameter / 2.0
    across_limit = radius * SINK_FIT_LIMIT
    found: Feature | None = None
    widest = diameter
    for candidate in features.values():
        if candidate.id == feature.id:
            continue
        other_axis = axis_of(candidate)
        other_centre = centre_of(candidate)
        other_diameter = float(candidate.params.get("diameter") or 0.0)
        if other_axis is None or other_centre is None or other_diameter <= widest:
            continue
        if not is_a_cavity(candidate):
            continue
        if abs(float(axis @ other_axis)) < math.cos(math.radians(SINK_AXIS_LIMIT)):
            continue
        offset = other_centre - centre
        along = float(offset @ axis)
        across = offset - along * axis
        if float(np.linalg.norm(across)) > across_limit:
            continue
        if not -across_limit <= abs(along) <= depth + across_limit:
            continue
        found = candidate
        widest = other_diameter
    return found


def bore_and_widening_at(
    feature: Feature, features: Mapping[FeatureId, Feature], *, mesh: MeshData | None = None
) -> tuple[Feature, Feature] | None:
    """Bohrung und Aufweitung, gleich welche der beiden gewählt ist.

    :func:`widening_at_the_mouth` beantwortet die Beziehung absichtlich von
    der Bohrung aus. Für eine Bedienhandlung reicht eine Richtung nicht: Im
    Objektbaum lassen sich die Bohrung und ihre Senkung anklicken, und beide
    meinen beim Versetzen denselben Hohlraum.

    Von der Aufweitung zurück wird nur eine **eindeutige** Bohrung geliefert.
    Treffen mehrere zu, bleibt die Antwort ``None`` — welche davon mitgehen
    soll, darf die Reihenfolge im Wörterbuch nicht entscheiden (Regel 21).
    """
    if mesh is not None:
        chain = cavity_chain_at(feature, features, mesh)
        return (chain[0], chain[1]) if chain is not None and len(chain) == 2 else None
    widening = widening_at_the_mouth(feature, features)
    if widening is not None:
        return feature, widening

    candidates = [
        candidate
        for candidate in features.values()
        if (found := widening_at_the_mouth(candidate, features)) is not None
        and found.id == feature.id
    ]
    if len(candidates) != 1:
        return None
    return candidates[0], feature


def _coaxial(first: Feature, second: Feature) -> bool:
    """Dieselbe Achslinie mit den bereits geltenden Einpassungsschranken."""
    axis, other_axis = axis_of(first), axis_of(second)
    centre, other_centre = centre_of(first), centre_of(second)
    if axis is None or other_axis is None or centre is None or other_centre is None:
        return False
    if abs(float(axis @ other_axis)) < math.cos(math.radians(SINK_AXIS_LIMIT)):
        return False
    radius = (
        min(
            float(first.params.get("diameter") or 0.0),
            float(second.params.get("diameter") or 0.0),
        )
        / 2.0
    )
    offset = other_centre - centre
    lateral = max(
        float(np.linalg.norm(offset - (offset @ axis) * axis)),
        float(np.linalg.norm(offset - (offset @ other_axis) * other_axis)),
    )
    return radius > EPS_GEOM and lateral <= radius * SINK_FIT_LIMIT


def _boundary_rings(
    body: trimesh.Trimesh, feature: Feature
) -> list[frozenset[tuple[int, int]]] | None:
    """Geschlossene Randringe in der echten, gemeinsam verschweißten Topologie."""
    indices = np.asarray(feature.face_indices, dtype=np.int64)
    return _face_boundary_rings(body, indices)


def _face_boundary_rings(
    body: trimesh.Trimesh, indices: NDArray[np.int64]
) -> list[frozenset[tuple[int, int]]] | None:
    """Die geschlossenen Randkomponenten eines zusammenhängenden Flächenausschnitts."""
    if not len(indices) or indices.min() < 0 or indices.max() >= len(body.faces):
        return None
    faces = np.asarray(body.faces)[indices]
    edges = np.sort(np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1)
    unique, count = np.unique(edges, axis=0, return_counts=True)
    if (count > 2).any():
        return None
    boundary = unique[count == 1]
    if not len(boundary):
        return None
    vertices, degrees = np.unique(boundary, return_counts=True)
    if (degrees != 2).any():
        return None
    rings = []
    for component in trimesh.graph.connected_components(boundary, nodes=vertices, engine="scipy"):
        if len(component) < 3:
            return None
        selected = np.isin(boundary[:, 0], component)
        rings.append(frozenset((int(a), int(b)) for a, b in boundary[selected]))
    return rings


def cavity_chain_at(
    feature: Feature, features: Mapping[FeatureId, Feature], mesh: MeshData
) -> tuple[Feature, ...] | None:
    """Der eindeutige zusammenhängende Hohlraum, von jedem Abschnitt aus.

    Dieselbe Auskunft wie für den Baum: Eine Winkelgrenze ist nicht transitiv.
    Gegen die gewählte Achse vorzufiltern könnte das letzte Kettenglied
    ausschließen, obwohl alle direkten Nachbarn zusammenpassen. Verbunden
    wird ausschließlich über vollständig gemeinsame Ringe; Abstände und
    Einfügereihenfolge ersetzen diese Verbindung nicht.
    """
    chain, _touches_other = cavity_chain_state_at(feature, features, mesh)
    return chain


def cavity_chain_state_at(
    feature: Feature, features: Mapping[FeatureId, Feature], mesh: MeshData
) -> tuple[tuple[Feature, ...] | None, bool]:
    """Die Kette und ob der gewählte Abschnitt einen anderen Rand berührt.

    Die zweite Auskunft trennt eine sicher einzelne Bohrung von einer
    mehrdeutigen oder ungültigen Kette. Beide liefern keine Kette, aber nur die
    einzelne darf eine Geometrieoperation allein verschieben. Auch bei drei
    Besitzern desselben Randrings bleibt die Berührung erhalten, obwohl daraus
    absichtlich keine Verbindung gewählt wird.
    """
    if feature.kind not in {"hole", "cone"} or not is_a_cavity(feature):
        return None, False
    candidates = {
        identifier: candidate
        for identifier, candidate in features.items()
        if candidate.kind in {"hole", "cone"} and is_a_cavity(candidate)
    }
    if feature.id not in candidates:
        return None, False
    graph, invalid, touching = _cavity_links(candidates, mesh)
    return _ordered_cavity(feature.id, candidates, graph, invalid), feature.id in touching


def cavity_chains(
    features: Mapping[FeatureId, Feature], mesh: MeshData
) -> tuple[tuple[Feature, ...], ...]:
    """Alle eindeutigen Ketten, mit genau einer Randringbildung je Merkmal."""
    candidates = {
        identifier: feature
        for identifier, feature in features.items()
        if feature.kind in {"hole", "cone"} and is_a_cavity(feature)
    }
    if len(candidates) < 2:
        return ()
    graph, invalid, _touching = _cavity_links(candidates, mesh)
    found = []
    seen: set[FeatureId] = set()
    for identifier in candidates:
        if identifier in seen:
            continue
        chain = _ordered_cavity(identifier, candidates, graph, invalid)
        if chain is not None:
            found.append(chain)
            seen.update(feature.id for feature in chain)
    return tuple(sorted(found, key=lambda chain: (*chain[0].params["centre"], chain[0].id)))


def _cavity_links(
    candidates: Mapping[FeatureId, Feature], mesh: MeshData
) -> tuple[dict[FeatureId, set[FeatureId]], set[FeatureId], set[FeatureId]]:
    """Gemeinsame Randringe einmal bilden; doppelte Belegung bleibt ungültig."""
    body = _one_body(mesh).raw
    owners: dict[frozenset[tuple[int, int]], list[FeatureId]] = {}
    invalid: set[FeatureId] = set()
    touching: set[FeatureId] = set()
    with body._cache:
        for identifier, candidate in candidates.items():
            rings = _boundary_rings(body, candidate)
            if rings is None or candidate.id != identifier:
                invalid.add(identifier)
                continue
            for ring in rings:
                owners.setdefault(ring, []).append(identifier)
    graph: dict[FeatureId, set[FeatureId]] = {identifier: set() for identifier in candidates}
    connections = [
        *owners.values(),
        *(adjacent for adjacent, _faces in _shoulder_connections(body, owners, candidates)),
    ]
    for adjacent in connections:
        if len(adjacent) < 2:
            continue
        touching.update(adjacent)
        if len(adjacent) != 2:
            invalid.update(adjacent)
            continue
        first, second = adjacent
        if (
            second in graph[first]
            or not _coaxial(candidates[first], candidates[second])
            or not set(candidates[first].face_indices).isdisjoint(candidates[second].face_indices)
        ):
            invalid.update(adjacent)
        graph[first].add(second)
        graph[second].add(first)
    return graph, invalid, touching


def _shoulder_connections(
    body: trimesh.Trimesh,
    owners: Mapping[frozenset[tuple[int, int]], list[FeatureId]],
    candidates: Mapping[FeatureId, Feature],
) -> list[tuple[list[FeatureId], tuple[int, ...]]]:
    """Eine ebene Ringschulter verbindet nur ihre zwei vollständig belegten Ränder.

    Weder bloße Koaxialität noch Abstand überbrücken Material. Die verbindende
    Netzfläche muss zusammenhängend und eben sein und genau zwei geschlossene
    Randringe besitzen, die vollständig zu den Hohlraumabschnitten gehören.
    Doppelte Besitzer werden weitergereicht, damit der Graph mehrdeutig bleibt.
    """
    if len(candidates) < 2 or not owners:
        return []
    # Nur Facetten unmittelbar an einem belegten Rand untersuchen. Auf einer
    # Freiform liegen sonst Tausende winzige Facetten an denselben Eckpunkten,
    # für die eine eigene Rand-Komponentensuche nichts beitragen kann.
    edges = np.asarray([edge for ring in owners for edge in ring], dtype=np.int64)
    edge_codes = edges[:, 0] * len(body.vertices) + edges[:, 1]
    neighbours = np.sort(np.asarray(body.face_adjacency_edges), axis=1)
    neighbour_codes = neighbours[:, 0] * len(body.vertices) + neighbours[:, 1]
    adjacent_faces = np.asarray(body.face_adjacency)[np.isin(neighbour_codes, edge_codes)]
    starts = np.zeros(len(body.faces), dtype=bool)
    starts[adjacent_faces.ravel()] = True
    for identifier in {identifier for adjacent in owners.values() for identifier in adjacent}:
        starts[list(candidates[identifier].face_indices)] = False
    connections = []
    for facet in body.facets:
        indices = np.asarray(facet, dtype=np.int64)
        if not starts[indices].any():
            continue
        faces = np.asarray(body.faces)[indices]
        rings = _face_boundary_rings(body, indices)
        if rings is None or len(rings) != 2 or any(ring not in owners for ring in rings):
            continue
        normal = np.asarray(body.face_normals)[indices[0]]
        points = np.asarray(body.vertices)[np.unique(faces)]
        if np.max(np.abs((points - points[0]) @ normal)) > EPS_GEOM:
            continue
        adjacent = [identifier for ring in rings for identifier in owners[ring]]
        # Eine seitliche Fläche ist kein Absatz quer durch eine Bohrung.
        if any(
            (axis := axis_of(candidates[identifier])) is None
            or abs(float(np.dot(axis, normal))) < math.cos(math.radians(SINK_AXIS_LIMIT))
            for identifier in adjacent
        ):
            continue
        connections.append((adjacent, tuple(int(index) for index in indices)))
    return connections


def cavity_surface_indices(mesh: MeshData, features: Iterable[Feature]) -> tuple[int, ...]:
    """Die belegten Hohlraumflächen einschließlich ihrer ebenen Ringschultern.

    Der Aufrufer übergibt die zuvor ermittelte vollständige Kette. Zusätzliche
    Flächen kommen nur hinzu, wenn ihre beiden Randringe eindeutig zu zwei
    verschiedenen, koaxialen Abschnitten gehören. So benutzt die Bearbeitung
    dieselben echten Schulterflächen wie die Erkennung des Zusammenhangs.
    """
    body = _one_body(mesh).raw
    candidates = {feature.id: feature for feature in features}
    owners: dict[frozenset[tuple[int, int]], list[FeatureId]] = {}
    indices: set[int] = set()
    for identifier, feature in candidates.items():
        rings = _boundary_rings(body, feature)
        if rings is None:
            return ()
        indices.update(feature.face_indices)
        for ring in rings:
            owners.setdefault(ring, []).append(identifier)
    for adjacent, faces in _shoulder_connections(body, owners, candidates):
        if len(adjacent) != 2 or len(set(adjacent)) != 2:
            continue
        first, second = (candidates[identifier] for identifier in adjacent)
        if _coaxial(first, second) and set(first.face_indices).isdisjoint(second.face_indices):
            indices.update(faces)
    return tuple(sorted(indices))


def _ordered_cavity(
    selected: FeatureId,
    candidates: Mapping[FeatureId, Feature],
    graph: Mapping[FeatureId, set[FeatureId]],
    invalid: set[FeatureId],
) -> tuple[Feature, ...] | None:
    """Den einfachen Pfad von der eindeutigen engen Bohrung aus lesen."""
    connected: set[FeatureId] = set()
    waiting = [selected]
    while waiting:
        identifier = waiting.pop()
        if identifier not in connected:
            connected.add(identifier)
            waiting.extend(graph[identifier] - connected)
    if len(connected) < 2 or connected & invalid:
        return None
    ends = [identifier for identifier in connected if len(graph[identifier]) == 1]
    if len(ends) != 2 or any(len(graph[identifier]) > 2 for identifier in connected):
        return None
    bores = sorted(
        (
            candidates[identifier]
            for identifier in connected
            if candidates[identifier].kind == "hole"
        ),
        key=lambda candidate: float(candidate.params.get("diameter") or 0.0),
    )
    if not bores or bores[0].id not in ends:
        return None
    if (
        len(bores) > 1
        and abs(float(bores[1].params["diameter"]) - float(bores[0].params["diameter"])) <= EPS_GEOM
    ):
        return None
    ordered = [bores[0].id]
    while len(ordered) < len(connected):
        following = graph[ordered[-1]] - set(ordered)
        if len(following) != 1:
            return None
        ordered.append(next(iter(following)))
    return tuple(candidates[identifier] for identifier in ordered)


_Comparison = Literal["same", "different", "unavailable"]
_POSE_PARAMETERS = frozenset({"axis", "centre", "normal", "position"})
_DIAGNOSTIC_PARAMETERS = frozenset({"residual"})


@dataclass(frozen=True, slots=True)
class _SurfacePatch:
    """Ein echter Flächenausschnitt und seine Prüfstellen."""

    points: NDArray[np.float64]
    edge_lengths: NDArray[np.float64]


@dataclass(slots=True)
class _FeatureGroupContext:
    """Nur während einer Auswahl wiederverwendete geometrische Nachweise."""

    features: Mapping[FeatureId, Feature]
    mesh: MeshData
    scopes: dict[FeatureId, tuple[Feature, ...]]
    topology_uncertain: dict[FeatureId, FeatureGroupReason]
    patches: dict[tuple[FeatureId, ...], _SurfacePatch | None]
    comparisons: dict[
        tuple[tuple[FeatureId, ...], tuple[FeatureId, ...]],
        tuple[_Comparison, FeatureGroupReason | None],
    ]


def alike_for_action(
    action: str,
    selected: FeatureId,
    features: Mapping[FeatureId, Feature],
    mesh: MeshData,
) -> FeatureActionGroup:
    """Die Gruppe für eine einzelne registrierte Merkmalshandlung."""
    return alike_for_actions((action,), selected, features, mesh)[0]


def alike_for_actions(
    actions: Iterable[str],
    selected: FeatureId,
    features: Mapping[FeatureId, Feature],
    mesh: MeshData,
) -> tuple[FeatureActionGroup, ...]:
    """Mehrere Handlungsgruppen mit einer gemeinsamen Topologieauskunft.

    Die Reihenfolge entspricht ``actions``. Der Kontext lebt nur für diesen
    Aufruf; ein anderer Mesh- oder Merkmalsstand kann daher keinen veralteten
    Randgraphen erben.
    """
    requested = tuple(actions)
    if not requested:
        return ()
    scopes: dict[FeatureId, tuple[Feature, ...]] = {}
    topology_uncertain: dict[FeatureId, FeatureGroupReason] = {}
    feature = features.get(selected)
    if feature is not None and feature.kind in {"hole", "cone"} and is_a_cavity(feature):
        scopes, topology_uncertain = _feature_group_topology(features, mesh)
    context = _FeatureGroupContext(
        features=features,
        mesh=mesh,
        scopes=scopes,
        topology_uncertain=topology_uncertain,
        patches={},
        comparisons={},
    )
    return tuple(_alike_for_action(action, selected, context) for action in requested)


def _alike_for_action(
    action: str,
    selected: FeatureId,
    context: _FeatureGroupContext,
) -> FeatureActionGroup:
    """Die für ``action`` nachweislich gleichartigen Merkmale.

    Die Operation bestimmt, welche Maße den Vergleich tragen. Ändert ihr
    Schema ein gemessenes Längenmaß des Merkmals, wird genau dieses Zielmaß
    verglichen. Versetzen, Drehen, Verdoppeln und Entfernen ändern kein solches
    Maß; dort muss deshalb die vollständige Form übereinstimmen.

    Ein Hohlraumabschnitt wird nie aus seiner belegten Randringkette gelöst:
    Nur dieselbe Rolle in einer Kette mit derselben Artenfolge ist ein Ziel,
    und :attr:`FeatureGroupMember.scope` bewahrt die ganze Kette. Unvollständige
    Topologie wird mit einem Reason-Code ausgewiesen statt ergänzt.
    """
    features = context.features
    feature = features.get(selected)
    if feature is None:
        return _empty_feature_group(action, selected, "selected_feature_unavailable")
    if not REGISTRY.has(action) or not any(action in row for row in ACTION_ORDER):
        return _empty_feature_group(action, selected, "action_not_applicable")
    spec = REGISTRY.get(action)
    if feature.kind not in spec.applies_to:
        return _empty_feature_group(action, selected, "action_not_applicable")

    scopes = context.scopes
    topology_uncertain = context.topology_uncertain
    selected_uncertain = topology_uncertain.get(selected)
    if selected_uncertain is not None:
        return _empty_feature_group(action, selected, selected_uncertain)

    selected_scope = scopes.get(selected, (feature,))
    selected_role = _role_of(selected, selected_scope)
    target_dimensions = _target_dimensions(spec, feature)
    complete_shape = not target_dimensions
    ready = _group_comparison(
        feature,
        selected_scope,
        selected_role,
        feature,
        selected_scope,
        selected_role,
        target_dimensions,
        context,
        complete_shape=complete_shape,
    )
    if ready[0] != "same":
        ready_reason = ready[1] or "dimensions_unavailable"
        return _empty_feature_group(action, selected, ready_reason)

    members: list[FeatureGroupMember] = []
    uncertain: dict[FeatureId, FeatureGroupReason] = {}
    for identifier in sorted(features):
        candidate = features[identifier]
        if candidate.kind != feature.kind or candidate.kind not in spec.applies_to:
            continue
        topology_reason = topology_uncertain.get(identifier)
        candidate_scope = scopes.get(identifier, (candidate,))
        candidate_role = _role_of(identifier, candidate_scope)
        if topology_reason is not None:
            comparison, comparison_reason = _target_comparison(
                feature, candidate, target_dimensions, complete_shape=complete_shape
            )
            if comparison == "same":
                uncertain[identifier] = topology_reason
            elif comparison == "unavailable":
                uncertain[identifier] = comparison_reason or topology_reason
            continue

        comparison, comparison_reason = _group_comparison(
            feature,
            selected_scope,
            selected_role,
            candidate,
            candidate_scope,
            candidate_role,
            target_dimensions,
            context,
            complete_shape=complete_shape,
        )
        if comparison == "same":
            members.append(
                FeatureGroupMember(
                    target=identifier,
                    scope=tuple(part.id for part in candidate_scope),
                )
            )
        elif comparison == "unavailable":
            uncertain[identifier] = comparison_reason or "dimensions_unavailable"

    stable_members = tuple(sorted(members, key=lambda member: member.target))
    stable_uncertain = tuple(
        FeatureGroupUncertainty(feature_ids=(identifier,), reason=uncertain[identifier])
        for identifier in sorted(uncertain)
    )
    evidence: list[FeatureGroupEvidence] = [
        "complete_surface_patch" if complete_shape else "same_target_dimensions"
    ]
    if feature.kind != "sphere":
        evidence.append("parallel_axes")
    if len(selected_scope) > 1:
        evidence.append("shared_boundary_role")
        if complete_shape and len(stable_members) > 1:
            evidence.append("translation_consistent")
    identifiers = ",".join(member.target for member in stable_members) or selected
    return FeatureActionGroup(
        id=f"{action}:{identifiers}",
        action=action,
        selected=selected,
        members=stable_members,
        evidence=tuple(evidence),
        uncertain=stable_uncertain,
    )


def _empty_feature_group(
    action: str, selected: FeatureId, reason: FeatureGroupReason
) -> FeatureActionGroup:
    """Eine begründete Absage ohne behaupteten Sammelumfang."""
    return FeatureActionGroup(
        id=f"{action}:{selected}",
        action=action,
        selected=selected,
        uncertain=(FeatureGroupUncertainty(feature_ids=(selected,), reason=reason),),
    )


def _feature_group_topology(
    features: Mapping[FeatureId, Feature], mesh: MeshData
) -> tuple[dict[FeatureId, tuple[Feature, ...]], dict[FeatureId, FeatureGroupReason]]:
    """Ketten und unklare Hohlräume aus genau einer Randringbildung."""
    candidates = {
        identifier: feature
        for identifier, feature in features.items()
        if feature.kind in {"hole", "cone"} and is_a_cavity(feature)
    }
    if not candidates:
        return {}, {}
    graph, invalid, touching = _cavity_links(candidates, mesh)
    scopes: dict[FeatureId, tuple[Feature, ...]] = {}
    for identifier in sorted(candidates):
        if identifier in scopes:
            continue
        chain = _ordered_cavity(identifier, candidates, graph, invalid)
        if chain is not None:
            scopes.update((part.id, chain) for part in chain)

    uncertain: dict[FeatureId, FeatureGroupReason] = {}
    for identifier in sorted(candidates):
        if identifier in scopes:
            continue
        if identifier in touching:
            uncertain[identifier] = "ambiguous_cavity_chain"
        elif identifier in invalid:
            uncertain[identifier] = "cavity_topology_unavailable"
    return scopes, uncertain


def _role_of(identifier: FeatureId, scope: tuple[Feature, ...]) -> int | None:
    """Die Stelle in der belegten Kette; einzelne Merkmale haben keine."""
    if len(scope) == 1:
        return None
    return next((index for index, part in enumerate(scope) if part.id == identifier), None)


def _target_dimensions(spec: Any, feature: Feature) -> tuple[str, ...]:
    """Gemessene Längen, die diese Operation tatsächlich ändert."""
    dimensions = set()
    for entry in spec.params.spec():
        source = feature_value_source(entry.name)
        if source is None:
            continue
        key, index = source
        if (
            index is None
            and entry.unit == "mm"
            and key in feature.params
            and _is_number(feature.params[key])
        ):
            dimensions.add(key)
    return tuple(sorted(dimensions))


def _group_comparison(
    reference: Feature,
    reference_scope: tuple[Feature, ...],
    reference_role: int | None,
    candidate: Feature,
    candidate_scope: tuple[Feature, ...],
    candidate_role: int | None,
    target_dimensions: tuple[str, ...],
    context: _FeatureGroupContext,
    *,
    complete_shape: bool,
) -> tuple[_Comparison, FeatureGroupReason | None]:
    """Eine mögliche Zugehörigkeit mit ihrem gegebenenfalls fehlenden Beleg."""
    if (len(reference_scope) > 1) != (len(candidate_scope) > 1):
        return "different", None
    if len(reference_scope) > 1:
        if tuple(part.kind for part in reference_scope) != tuple(
            part.kind for part in candidate_scope
        ):
            return "different", None
        if reference_role != candidate_role:
            return "different", None
    if complete_shape:
        key = (
            tuple(feature.id for feature in reference_scope),
            tuple(feature.id for feature in candidate_scope),
        )
        if key not in context.comparisons:
            context.comparisons[key] = _complete_shape_comparison(
                reference_scope, candidate_scope, context
            )
        return context.comparisons[key]
    return _target_comparison(reference, candidate, target_dimensions, complete_shape=False)


def _target_comparison(
    reference: Feature,
    candidate: Feature,
    target_dimensions: tuple[str, ...],
    *,
    complete_shape: bool,
) -> tuple[_Comparison, FeatureGroupReason | None]:
    """Maß und Achse des gewählten Rollenabschnitts vergleichen."""
    dimensions = (
        _dimension_comparison(reference, candidate)
        if complete_shape
        else _dimension_comparison(reference, candidate, target_dimensions)
    )
    if dimensions == "unavailable":
        return dimensions, "dimensions_unavailable"
    if dimensions == "different":
        return dimensions, None
    orientation = _orientation_comparison(reference, candidate)
    if orientation == "unavailable":
        return orientation, "orientation_unavailable"
    return orientation, None


def _complete_shape_comparison(
    reference: tuple[Feature, ...],
    candidate: tuple[Feature, ...],
    context: _FeatureGroupContext,
) -> tuple[_Comparison, FeatureGroupReason | None]:
    """Zwei vollständige Flächenausschnitte auf dieselbe Verschiebung prüfen."""
    if len(reference) != len(candidate):
        return "different", None
    offsets = []
    for first, second in zip(reference, candidate, strict=True):
        comparison, reason = _target_comparison(first, second, (), complete_shape=True)
        if comparison != "same":
            return comparison, reason
        first_centre, second_centre = centre_of(first), centre_of(second)
        if first_centre is None or second_centre is None:
            return "unavailable", "relative_position_unavailable"
        offsets.append(second_centre - first_centre)
    if any(float(np.linalg.norm(offset - offsets[0])) > EPS_DISPLAY for offset in offsets[1:]):
        return "different", None
    reference_patch = _surface_patch(reference, context)
    candidate_patch = _surface_patch(candidate, context)
    if reference_patch is None or candidate_patch is None:
        return "unavailable", "complete_shape_unavailable"
    if not _same_surface_patch(reference_patch, candidate_patch):
        return "different", None
    return "same", None


def _surface_patch(
    scope: tuple[Feature, ...], context: _FeatureGroupContext
) -> _SurfacePatch | None:
    """Den einmal gebildeten Flächennachweis eines Umfangs lesen."""
    key = tuple(feature.id for feature in scope)
    if key not in context.patches:
        context.patches[key] = _build_surface_patch(scope, context.mesh)
    return context.patches[key]


def _build_surface_patch(scope: tuple[Feature, ...], mesh: MeshData) -> _SurfacePatch | None:
    """Flächenproben eines Umfangs, relativ zu seinem ersten Mittelpunkt.

    Die Eckpunkte bilden die Lage und Abdeckung ab; die drei Kantenlängen
    jedes Dreiecks bewahren zusätzlich die örtliche Vernetzung. Flächenindex
    und Reihenfolge tragen keine Bedeutung; die Geometrie selbst schon.
    """
    centre = centre_of(scope[0])
    indices = np.unique(
        np.fromiter(
            (index for feature in scope for index in feature.face_indices),
            dtype=np.int64,
        )
    )
    body = _one_body(mesh).raw
    if (
        centre is None
        or not len(indices)
        or int(indices.min()) < 0
        or int(indices.max()) >= len(body.faces)
    ):
        return None
    triangles = np.asarray(body.triangles, dtype=np.float64)[indices] - centre
    if not np.isfinite(triangles).all():
        return None
    points = np.unique(triangles.reshape(-1, 3), axis=0)
    edges = np.sort(
        np.linalg.norm(triangles - np.roll(triangles, 1, axis=1), axis=2),
        axis=1,
    )
    order = np.lexsort((edges[:, 2], edges[:, 1], edges[:, 0]))
    return _SurfacePatch(
        points=cast(NDArray[np.float64], points),
        edge_lengths=cast(NDArray[np.float64], edges[order]),
    )


def _same_surface_patch(reference: _SurfacePatch, candidate: _SurfacePatch) -> bool:
    """Punktabdeckung und Dreiecksformen stimmen innerhalb der Auflösung."""
    reference_edges = cKDTree(reference.edge_lengths)
    candidate_edges = cKDTree(candidate.edge_lengths)
    edges_to_candidate = candidate_edges.query(reference.edge_lengths, p=np.inf)[0]
    edges_to_reference = reference_edges.query(candidate.edge_lengths, p=np.inf)[0]
    if (
        float(np.max(edges_to_candidate, initial=0.0)) > EPS_DISPLAY
        or float(np.max(edges_to_reference, initial=0.0)) > EPS_DISPLAY
    ):
        return False
    reference_tree = cKDTree(reference.points)
    candidate_tree = cKDTree(candidate.points)
    to_candidate = candidate_tree.query(reference.points)[0]
    to_reference = reference_tree.query(candidate.points)[0]
    return bool(
        float(np.max(to_candidate, initial=0.0)) <= EPS_DISPLAY
        and float(np.max(to_reference, initial=0.0)) <= EPS_DISPLAY
    )


def _dimension_comparison(
    reference: Feature, candidate: Feature, keys: tuple[str, ...] | None = None
) -> _Comparison:
    """Formmaße mit der bereits geltenden Anzeigeauflösung vergleichen."""
    selected = tuple(sorted(_shape_parameters(reference) | _shape_parameters(candidate)))
    if keys is not None:
        selected = keys
    if not selected:
        return "unavailable"
    for key in selected:
        if key not in reference.params or key not in candidate.params:
            return "unavailable"
        same = _same_parameter(key, reference.params[key], candidate.params[key])
        if same is None:
            return "unavailable"
        if not same:
            return "different"
    return "same"


def _shape_parameters(feature: Feature) -> set[str]:
    """Skalare Formwerte ohne Pose und Einpassungsdiagnose."""
    return {
        key
        for key, value in feature.params.items()
        if key not in _POSE_PARAMETERS
        and key not in _DIAGNOSTIC_PARAMETERS
        and isinstance(value, (bool, int, float, str))
    }


def _orientation_comparison(reference: Feature, candidate: Feature) -> _Comparison:
    """Achslose Kugeln oder zwei mit der Erkennungsschranke parallele Achsen."""
    if reference.kind == candidate.kind == "sphere":
        return "same"
    axis, other_axis = axis_of(reference), axis_of(candidate)
    if axis is None or other_axis is None:
        return "unavailable"
    aligned = abs(float(axis @ other_axis)) >= math.cos(math.radians(SINK_AXIS_LIMIT))
    return "same" if aligned else "different"


def _same_parameter(key: str, first: Any, second: Any) -> bool | None:
    """Zwei gemessene Skalare, ohne einen neuen Zahlenwert einzuführen."""
    if isinstance(first, bool) or isinstance(second, bool):
        return first == second if isinstance(first, bool) and isinstance(second, bool) else None
    if _is_number(first) and _is_number(second):
        one, two = float(first), float(second)
        if not math.isfinite(one) or not math.isfinite(two):
            return None
        tolerance = EPS_ANGLE if key == "angle" else EPS_DISPLAY
        return abs(one - two) <= tolerance
    if isinstance(first, str) and isinstance(second, str):
        return first == second
    return None


def _is_number(value: Any) -> bool:
    """Ein skalarer Zahlenwert, aber kein Wahrheitswert."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)
