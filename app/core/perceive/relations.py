"""Was **zusammen** gehört: Nachbarschaften zwischen erkannten Merkmalen
(Bauplan §21.1, §21.2).

``features.py`` beantwortet „was ist das hier" — eine Bohrung, ein Zapfen, eine
Verrundung. Diese Datei beantwortet die Frage danach, und es ist eine andere:
**gehören zwei davon zusammen, und was folgt daraus?** Eine Senkung über einer
Bohrung ist keine zweite Bohrung; ein Zapfen um eine Bohrung ist ein Rohr mit
einer Wand. Wer eines von beiden ändert, ändert das andere mit — und genau das
sagte ihm bisher niemand.

**Warum ein eigenes Modul.** Die Erkennung einzelner Merkmale und ihre
Beziehungen sind getrennte Aufgaben. Senkungen über Bohrungen, Rohre,
Bohrungsraster und Hohlraumketten lesen die Merkmalsgeometrie und ergänzen
ihre Nachbarschaft; sie verändern die Erkennung selbst nicht.

**Die Richtung der Importe ist einseitig:** Diese Datei liest ``features.py``,
nie umgekehrt. Sie benutzt dessen Schwellen (:data:`SINK_AXIS_LIMIT`,
:data:`SINK_FIT_LIMIT`) und nicht eigene — zwei Achsenprüfungen mit zwei Zahlen
wären zwei Antworten auf dieselbe Frage.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Final, Literal, cast

import numpy as np
from numpy.typing import NDArray

from app.core.deferred import cKDTree, trimesh
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.perceive.actions import ACTION_ORDER, feature_value_source
from app.core.perceive.features import (
    CURVATURE_LIMIT,
    EPS_ANGLE,
    SINK_AXIS_LIMIT,
    SINK_FIT_LIMIT,
    _large_facet_faces,
    _one_body,
    axis_of,
    centre_of,
    sits_at_the_mouth_of,
)
from app.core.registry import REGISTRY
from app.core.types import Feature, FeatureId, is_a_cavity
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
    bore_travel: float = 0.0
    """Wie weit die Mittellinie der Höhlung wandert — null bei einer Bohrung.

    Ein Langloch hat keine gleichmäßige Wand: Was an den Flanken steht, fehlt
    an den Enden, und zwar um den halben Weg. Die Zahl gehört deshalb zum
    Rohr und nicht zur Höhlung allein — erst zusammen mit dem Außendurchmesser
    wird daraus eine Wandstärke."""
    centreline_reach: float | None = None
    """Weiteste Entfernung der Höhlungsmittellinie von der Mantelachse.

    Beinhaltet den gemessenen Querversatz und beim Langloch die Richtung
    seiner Enden. Ohne diesen Messwert gilt der zentrische Bezug."""

    @property
    def thickness(self) -> float:
        """Die Wand zwischen beiden, in Millimetern — an der dünnsten Stelle.

        Vom halben Unterschied der Durchmesser geht die weiteste Entfernung
        der Höhlungsmittellinie zur Mantelachse ab. Bei einer zentrischen
        Bohrung ist sie null, beim zentrischen Langloch der halbe Weg:
        Gemessen an einem Zapfen Ø 20 mit einem Langloch Ø 8 auf 14 mm stehen
        an den Flanken 6 mm und an den Enden 3. Wandstärke ist druckkritisch —
        die dickere der beiden Zahlen zu nennen wäre schlimmer als zu
        schweigen (RM-152).
        """
        reach = self.bore_travel / 2.0 if self.centreline_reach is None else self.centreline_reach
        return (self.outer_diameter - self.bore_diameter) / 2.0 - reach


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


@dataclass(frozen=True, slots=True)
class _Measured:
    """Die fünf Angaben, aus denen ein Rohr entsteht — einmal gelesen.

    ``axis_of`` und ``centre_of`` bauen je ein Numpy-Array. Wer sie für jedes
    Paar neu ruft, zahlt sie quadratisch — und die Wandprüfung läuft nach
    *jeder* Auswertung (RM-127). Gemessen am 12.09.2026, einmal gelesen gegen
    je Paar gelesen:

    ======================================  ========  =======
    Körper                                  vorher    nachher
    ======================================  ========  =======
    500 Bohrungen, 5 Zapfen                  25,8 ms   1,7 ms
    234 Merkmale, davon 200 Rundungen         2,3 ms   0,2 ms
    500 Bohrungen, 500 koaxiale Zapfen      2087 ms    476 ms
    ======================================  ========  =======

    Die letzte Zeile ist ein gebauter Fall und kein gemessener Kunde — sie
    steht hier als **Obergrenze**: Oberhalb von
    ``scene.evaluate.FEATURE_LIMIT_COUNT`` (tausend) hängt die Auswertung gar
    keine Merkmale mehr ein, und schlimmer als halb Hohlraum und halb Materie
    wird die Paarung nicht. Was echte Modelle mitbringen, liegt zwei
    Größenordnungen darunter: über die zwanzig Netze des Korpus gemessen sind
    es höchstens **16** Merkmale.
    """

    feature: Feature
    axis: Any
    centre: Any
    diameter: float
    depth: float
    inside: bool


def _measured(feature: Feature) -> _Measured | None:
    """``None``, wo die Zahlen für die Frage nicht reichen — ein Merkmal ohne
    Achse, ohne Mitte, ohne Durchmesser oder ohne Tiefe. Geraten wird nichts
    (Regel 21): Ohne Tiefe lässt sich die Überdeckung nicht messen, und ohne
    sie wäre jede Senkung ein Rohr.
    """
    axis = axis_of(feature)
    centre = centre_of(feature)
    diameter = float(feature.params.get("diameter") or 0.0)
    depth = float(feature.params.get("depth") or 0.0)
    if axis is None or centre is None or diameter <= EPS_GEOM or depth <= EPS_GEOM:
        return None
    return _Measured(feature, axis, centre, diameter, depth, is_a_cavity(feature))


def _sleeve_between(one: _Measured, other: _Measured) -> Sleeve | None:
    """Die eine Regel, nach der aus zwei Merkmalen ein Rohr wird.

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

    **Die Reihenfolge der Prüfungen ist gemessen und nicht beliebig**: Der
    Durchmesservergleich ist ein Fließkommavergleich und wirft die Hälfte aller
    Paare weg, bevor die erste Matrixrechnung läuft.
    """
    if one.inside == other.inside:
        return None
    # Die Höhlung muss die engere sein. Andersherum steckt der Zapfen in der
    # Bohrung, und das ist kein Rohr, sondern ein Stift in einem Loch — eine
    # Passung, keine Wand.
    if one.inside and other.diameter <= one.diameter:
        return None
    if not one.inside and other.diameter >= one.diameter:
        return None
    if abs(float(one.axis @ other.axis)) < math.cos(math.radians(SINK_AXIS_LIMIT)):
        return None
    # Alle Lagewerte werden aus Sicht der Bohrung gerechnet. Sie ist bei beiden
    # Aufrufrichtungen dasselbe Merkmal; die Achsen dürfen innerhalb der
    # Erkennungsschwelle leicht voneinander abweichen, und dann würden zwei
    # wechselnde Bezugsachsen sonst zwei verschiedene Überdeckungen liefern.
    bore = one if one.inside else other
    wall = other if one.inside else one
    offset = wall.centre - bore.centre
    along = float(offset @ bore.axis)
    across = offset - along * bore.axis
    reach = float(np.linalg.norm(across))
    if reach > bore.diameter / 2.0 * SINK_FIT_LIMIT:
        return None

    share = _overlap(along, bore.depth, wall.depth)
    if share < SLEEVE_OVERLAP:
        return None
    travel = float(bore.feature.params.get("travel") or 0.0)
    if travel > EPS_GEOM:
        raw_direction = bore.feature.params.get("direction")
        if raw_direction is None:
            if reach > EPS_GEOM:
                return None
            reach = travel / 2.0
        else:
            direction = np.asarray(raw_direction, dtype=float)
            direction = direction - float(direction @ bore.axis) * bore.axis
            length = float(np.linalg.norm(direction))
            if length <= EPS_GEOM:
                return None
            end = direction * (travel / (2.0 * length))
            reach = max(float(np.linalg.norm(across + end)), float(np.linalg.norm(across - end)))
    found = Sleeve(
        bore=bore.feature.id,
        wall=wall.feature.id,
        bore_diameter=bore.diameter,
        outer_diameter=wall.diameter,
        overlap=share,
        # **Der Weg gehört der Höhlung**, nicht dem Merkmal, das gerade gefragt
        # wurde: Von außen geklickt ist das Langloch der Kandidat, und eine
        # Bohrung trägt gar keinen.
        bore_travel=travel,
        centreline_reach=reach,
    )
    # **Ein Langloch, das länger ist als sein Mantel, hat keine Wand, sondern
    # eine offene Flanke.** Bei einer runden Bohrung fängt das schon der
    # Durchmesservergleich oben ab; beim Langloch entscheidet die Gesamtlänge,
    # und die steht erst hier zur Verfügung.
    return None if found.thickness <= EPS_GEOM else found


def sleeve_at(feature: Feature, features: Mapping[FeatureId, Feature]) -> Sleeve | None:
    """Das Rohr, zu dem dieses Merkmal gehört — von welcher Seite man auch kommt.

    **Beide Seiten, und das ist keine Bequemlichkeit.** Der Kunde klickt
    entweder auf die Bohrung oder auf den Zapfen; eine Auskunft, die nur eine
    der beiden Richtungen kennt, ist an der anderen Hälfte der Klicks stumm.
    Gemessen am Besenhalter: ``hole_2`` Ø 34,00 und ``pin_1`` Ø 40,80 stehen
    beide im Objektbaum, beide lassen sich anklicken, und beide ändern dieselbe
    Wand von 3,40 mm.

    Was ein Rohr ausmacht, steht in :func:`_sleeve_between`; hier steht nur,
    dass alle Kandidaten gefragt werden. Wer dieselbe Frage für einen **ganzen
    Körper** stellt, nimmt :func:`sleeves_of` für jede Merkmalszeile oder
    :func:`thinnest_sleeve` für das Minimum — dieselbe Regel, ein Durchgang.

    ``None``, wo es keinen Partner gibt oder die Zahlen für die Frage nicht
    reichen.
    """
    mine = _measured(feature)
    if mine is None:
        return None
    best: Sleeve | None = None
    for candidate in features.values():
        if candidate.id == feature.id:
            continue
        theirs = _measured(candidate)
        if theirs is None:
            continue
        found = _sleeve_between(mine, theirs)
        # **Die dünnste Wand gewinnt.** Stehen mehrere Hüllen um dieselbe
        # Bohrung — ein Rohr in einem Rohr —, ist die innerste diejenige, die
        # als Erste zu dünn wird. Eine beliebige davon zu nennen hieße, die
        # Aussage vom Zufall der Reihenfolge abhängig zu machen.
        if found is not None and (best is None or found.thickness < best.thickness):
            best = found

    if best is not None:
        _log.debug("sleeve %s in %s: wall %.2f mm", best.bore, best.wall, best.thickness)
    return best


def _all_sleeves(features: Mapping[FeatureId, Feature]) -> Iterable[Sleeve]:
    """Alle belegten Rohrpaare, mit einmal gelesenen Maßen je Merkmal."""
    measured = [entry for entry in map(_measured, features.values()) if entry is not None]
    hollow = [entry for entry in measured if entry.inside]
    solid = [entry for entry in measured if not entry.inside]
    for bore in hollow:
        for wall in solid:
            found = _sleeve_between(bore, wall)
            if found is not None:
                yield found


def sleeves_of(features: Mapping[FeatureId, Feature]) -> dict[FeatureId, Sleeve]:
    """Die dünnste belegte Wand an jedem Merkmal, in einem gemeinsamen Durchgang.

    Der Steckbrief nennt beide Seiten eines Rohrs. Ein Paar wird deshalb nur
    einmal geprüft, sein Ergebnis aber bei Bohrung und Mantel eingeordnet.
    Bei gleicher Wandstärke gilt wie bei :func:`sleeve_at` die Reihenfolge
    der Merkmale; Maße oder Zuordnungen werden nicht anders bewertet.
    """
    result: dict[FeatureId, Sleeve] = {}
    for sleeve in _all_sleeves(features):
        for identifier in (sleeve.bore, sleeve.wall):
            previous = result.get(identifier)
            if previous is None or sleeve.thickness < previous.thickness:
                result[identifier] = sleeve
    return result


def thinnest_sleeve(features: Mapping[FeatureId, Feature]) -> Sleeve | None:
    """Die dünnste Wand eines ganzen Körpers, in einem Durchgang (RM-127).

    Dieselbe Regel wie :func:`sleeve_at` und dieselbe Funktion dahinter — der
    Unterschied ist die Zahl der Fragen. Wer ``sleeve_at`` für jedes Merkmal
    ruft, liest die vier Zahlen jedes Kandidaten n-mal; hier werden sie einmal
    gelesen, und gepaart wird nur Hohlraum gegen Materie.

    Gebraucht wird das, weil die Wandprüfung nach **jeder** Auswertung läuft
    (``scene.evaluate.check_thin_walls``). Die Zahlen dazu stehen bei
    :class:`_Measured`; der Kern davon ist, dass ein Körper mit fünfhundert
    Bohrungen von 25,8 auf 1,7 Millisekunden fällt.
    """
    return min(_all_sleeves(features), key=lambda entry: entry.thickness, default=None)


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

    **Die Bedingungen stehen bei den Schwellen**, nach denen sie fragen:
    :func:`app.core.perceive.features.sits_at_the_mouth_of` prüft Achse, Lage,
    Weite und Hohlraumeigenschaft eines Paares. Hier bleibt, was diese
    Funktion allein ausmacht — die **Suche** unter allen Merkmalen und die
    Wahl der weitesten passenden. Seit dem 10.09.2026 fragt der
    Freiformfilter dieselbe Bedingung aus der Gegenrichtung; zwei Fassungen
    davon wären zwei Antworten auf dieselbe Frage.

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
    found: Feature | None = None
    widest = float(feature.params.get("diameter") or 0.0)
    for candidate in features.values():
        if candidate.id == feature.id:
            continue
        other_diameter = float(candidate.params.get("diameter") or 0.0)
        if other_diameter <= widest or not sits_at_the_mouth_of(feature, candidate):
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
    return (
        axis is not None
        and other_axis is not None
        and abs(float(axis @ other_axis)) >= math.cos(math.radians(SINK_AXIS_LIMIT))
        and _axis_lines_agree(first, second)
    )


def _axis_lines_agree(first: Feature, second: Feature) -> bool:
    """Die gemessenen Lagen passen beiderseits zum selben Hohlraum.

    Ein vollständig geteilter Rand beweist die Verbindung unabhängig vom
    Winkel zweier Fits. Gerade ungleich unterteilte, schräge Kegelränder
    verschieben die geschätzte Achse. Die Lageprüfung bleibt erhalten: Eine
    veraltete Merkmalsmitte neben dem Hohlraum ist keine brauchbare Zuordnung.
    """
    axis, other_axis = axis_of(first), axis_of(second)
    centre, other_centre = centre_of(first), centre_of(second)
    if axis is None or other_axis is None or centre is None or other_centre is None:
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


def boundary_rings(
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
        return _rings_through_a_shared_corner(body, indices, boundary, vertices, degrees)
    rings = []
    for component in trimesh.graph.connected_components(boundary, nodes=vertices, engine="scipy"):
        if len(component) < 3:
            return None
        selected = np.isin(boundary[:, 0], component)
        rings.append(frozenset((int(a), int(b)) for a, b in boundary[selected]))
    return rings


def _rings_through_a_shared_corner(
    body: trimesh.Trimesh,
    indices: NDArray[np.int64],
    boundary: NDArray[np.int64],
    vertices: NDArray[np.int64],
    degrees: NDArray[np.int64],
) -> list[frozenset[tuple[int, int]]] | None:
    """Zwei Ränder, die sich eine Ecke teilen — getrennt am Dreiecksfächer.

    **Der Fall ist plattformabhängig und gemessen** (17.09.2026). Dieselbe
    Verkleinerung einer gesenkten Bohrung liefert hier ein Netz mit 1178
    Dreiecken und auf dem Mac der CI eines mit 1176: Die Boolesche Operation
    trianguliert anders, und der Mantel der Senkung läuft dort durch **einen**
    Punkt, in dem oberer und unterer Rand zusammenstoßen. Über den Knotengraphen
    verschmelzen beide Ringe zu einem, ``connected_components`` liefert eine
    Komponente statt zweier, und ohne zwei Ringe gibt es keine Schulter, keine
    Nachbarschaft und keine Bohrungskette. Die Senkung war auf dem Mac erkannt
    und trotzdem nicht mit ihrer Bohrung zu bearbeiten.

    **Getrennt wird an den Dreiecken, nicht am Knoten.** Um die geteilte Ecke
    liegen die Dreiecke des Ausschnitts in Fächern; jeder Fächer beginnt und
    endet an genau einer Randkante, und diese beiden gehören zusammen. Das ist
    dieselbe Auskunft, die eine Umlaufrichtung gäbe, nur ohne sie — und sie ist
    eindeutig, solange jeder Fächer wirklich zwei Randkanten trägt. Sonst
    bleibt es bei ``None``: Ein Rand, der sich nicht auflösen lässt, ist keine
    Nachbarschaft, und geraten wird nicht (Regel 21).
    """
    shared = {int(node) for node in vertices[degrees > 2]}
    if any(int(degree) % 2 for degree in degrees) or not shared:
        return None
    partner: dict[tuple[int, int], tuple[int, int]] = {}
    faces = np.asarray(body.faces)
    for corner in shared:
        fan_edges = _fan_pairs(faces, indices, corner, boundary)
        if fan_edges is None:
            return None
        partner.update(fan_edges)

    remaining = {(int(a), int(b)) for a, b in boundary}
    rings: list[frozenset[tuple[int, int]]] = []
    while remaining:
        start = next(iter(remaining))
        ring = [start]
        remaining.discard(start)
        # ``ahead`` ist der Knoten, auf den der Lauf zugeht — die Richtung ist
        # am Anfang beliebig, ein Ring schließt sich in beiden.
        edge, ahead = start, start[1]
        while True:
            following = _next_boundary_edge(edge, ahead, remaining, partner, shared)
            if following is None:
                break
            edge, ahead = following
            ring.append(edge)
            remaining.discard(edge)
        if len(ring) < 3:
            return None
        rings.append(frozenset(ring))
    return rings or None


def _fan_pairs(
    faces: NDArray[np.int64],
    indices: NDArray[np.int64],
    corner: int,
    boundary: NDArray[np.int64],
) -> dict[tuple[int, int], tuple[int, int]] | None:
    """Welche zwei Randkanten an dieser Ecke zu demselben Dreiecksfächer gehören."""
    at_corner = [int(face) for face in indices if corner in faces[face]]
    if not at_corner:
        return None
    # Zwei Dreiecke liegen im selben Fächer, wenn sie eine Kante an der Ecke teilen.
    links: dict[int, set[int]] = {face: set() for face in at_corner}
    by_edge: dict[tuple[int, int], list[int]] = {}
    for face in at_corner:
        for other in faces[face]:
            if int(other) == corner:
                continue
            by_edge.setdefault((corner, int(other)), []).append(face)
    for shared_faces in by_edge.values():
        if len(shared_faces) != 2:
            continue
        first, second = shared_faces
        links[first].add(second)
        links[second].add(first)

    border = {(int(a), int(b)) for a, b in boundary if corner in (int(a), int(b))}
    pairs: dict[tuple[int, int], tuple[int, int]] = {}
    seen: set[int] = set()
    for face in at_corner:
        if face in seen:
            continue
        fan, stack = set(), [face]
        while stack:
            current = stack.pop()
            if current in fan:
                continue
            fan.add(current)
            stack.extend(links[current] - fan)
        seen |= fan
        ends = [
            edge
            for edge in border
            if any({edge[0], edge[1]} <= {int(value) for value in faces[member]} for member in fan)
        ]
        if len(ends) != 2:
            return None
        pairs[ends[0]] = ends[1]
        pairs[ends[1]] = ends[0]
    return pairs or None


def _next_boundary_edge(
    edge: tuple[int, int],
    ahead: int,
    remaining: set[tuple[int, int]],
    partner: dict[tuple[int, int], tuple[int, int]],
    shared: set[int],
) -> tuple[tuple[int, int], int] | None:
    """Die nächste Randkante des Rings — an einer geteilten Ecke über den Fächer.

    **Der Fächer entscheidet nur, wo er gebraucht wird**: wenn der Lauf auf die
    geteilte Ecke **zugeht**. Dieselbe Kante hängt auch mit ihrem anderen Ende
    dort, und wer das nicht unterscheidet, springt beim Weglaufen zurück.
    """
    if ahead in shared:
        following = partner.get(edge)
        if following is None or following not in remaining:
            return None
        return following, (following[1] if following[0] == ahead else following[0])
    for candidate in remaining:
        if ahead in candidate:
            return candidate, (candidate[1] if candidate[0] == ahead else candidate[0])
    return None


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


def cavity_is_shared(chain: tuple[Feature, ...] | None, touches_other: bool) -> bool:
    """Ob ein Hohlraum anderen Abschnitten gehört — die eine Bedingung für alle.

    Eine Kette heißt, das Merkmal ist ein Abschnitt von mehreren (eine Kette
    hat immer mindestens zwei Glieder, :func:`_ordered_cavity`); ein berührter
    fremder Rand heißt, die Nachbarschaft ist da und nur nicht eindeutig.
    Beides zusammen entscheidet, ob *Zum Langloch ziehen*, *Merkmal drehen*
    und *Merkmal verdoppeln* absagen und ob das Merkmalfenster ihre Zeile
    vorher grau stellt. Bis zum 14.09.2026 stand die Bedingung an zwei
    Stellen wörtlich gleich — und nichts wurde rot, wenn eine sich löste.
    """
    return touches_other or chain is not None


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


def _candidate_key(candidates: Mapping[FeatureId, Feature]) -> tuple[Any, ...]:
    """Woran eine gemerkte Antwort hängt — die Namen genügen dafür nicht.

    Zwei Merkmalsmengen desselben Körpers können dieselben Namen tragen und
    verschiedene Flächen meinen: Ein veralteter Netzausschnitt trägt die
    Kennung weiter, und aus ihm darf keine Kette werden
    (``test_invalid_face_indices_do_not_connect_a_cavity``). Der Schlüssel
    nennt deshalb, was die Rechnung liest — Art, Flächen und die Achslinie.

    Die Flächen gehen als Hash ein, nicht als Liste: Ein Merkmal trägt
    tausende Nummern, und der Schlüssel soll billiger sein als die Rechnung,
    die er spart.
    """
    return tuple(
        (
            name,
            candidate.kind,
            hash(tuple(candidate.face_indices)),
            repr(candidate.params.get("axis")),
            repr(candidate.params.get("centre")),
        )
        for name, candidate in sorted(candidates.items())
    )


def _cavity_links(
    candidates: Mapping[FeatureId, Feature], mesh: MeshData
) -> tuple[dict[FeatureId, set[FeatureId]], set[FeatureId], set[FeatureId]]:
    """Gemeinsame Randringe einmal bilden; doppelte Belegung bleibt ungültig.

    **Einmal je Netz und Kandidatenmenge**, abgelegt im Cache des Netzes wie
    :attr:`MeshData.component_count` — er verfällt mit dessen Geometrie, und
    ein eigenes Feld gibt es an der eingefrorenen Klasse nicht. Der Grund ist
    gemessen (16.09.2026, Robert: „bei einer auswahl oder hover effekt stockt
    es auch noch sehr"): Ein Klick auf ein Merkmal von ``Auto-washer.stl``
    (180 128 Dreiecke, 170 Merkmale) kostete **402 ms** im Qt-Hauptthread,
    davon 447 ms in dieser Funktion über zwei Aufrufe — drei Wege fragen sie
    je Auswahl (:func:`cavity_chain_state_at`, :func:`cavity_chains`,
    :func:`_feature_group_topology`), und jeder bildete die Randringe aller
    462 Flächen neu.

    Der Schlüssel nennt die Kandidaten, weil die Antwort nur für sie gilt;
    dass alle drei Wege dieselbe Menge bilden, ist heute wahr und morgen eine
    Annahme.
    """
    body = _one_body(mesh).raw
    cache = getattr(body, "_cache", None)
    key = ("solidon_cavity_links", _candidate_key(candidates))
    if cache is not None:
        cache.verify()
        # Kein ``cache.get``: trimeshs ``Cache`` ist kein Wörterbuch und hat
        # keines (gemessen, ``AttributeError``).
        found = cache[key[0]] if key[0] in cache else None  # noqa: SIM401
        if found is not None and found[0] == key[1]:
            kept_graph, kept_invalid, kept_touching = found[1]
            return (
                {name: set(linked) for name, linked in kept_graph.items()},
                set(kept_invalid),
                set(kept_touching),
            )
    owners: dict[frozenset[tuple[int, int]], list[FeatureId]] = {}
    invalid: set[FeatureId] = set()
    touching: set[FeatureId] = set()
    with body._cache:
        for identifier, candidate in candidates.items():
            rings = boundary_rings(body, candidate)
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
            or not _axis_lines_agree(candidates[first], candidates[second])
            or not set(candidates[first].face_indices).isdisjoint(candidates[second].face_indices)
        ):
            invalid.update(adjacent)
        graph[first].add(second)
        graph[second].add(first)
    if cache is not None:
        # Als unveränderliche Kopie: Der Aufrufer bekommt seine eigene und
        # darf sie umbauen, ohne dem nächsten die Antwort zu verändern.
        cache[key[0]] = (
            key[1],
            (
                {name: frozenset(linked) for name, linked in graph.items()},
                frozenset(invalid),
                frozenset(touching),
            ),
        )
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
        # Ein schräger, vollständig belegter Ring bleibt dagegen eine Schulter;
        # deren Neigung muss nicht mit den geschätzten Zylinderachsen übereinstimmen.
        if any(
            (axis := axis_of(candidates[identifier])) is None
            or abs(float(np.dot(axis, normal))) <= EPS_GEOM
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
    indices = {index for feature in candidates.values() for index in feature.face_indices}
    if not indices or min(indices) < 0 or max(indices) >= len(body.faces):
        return ()
    indices = _blended_cavity_faces(body, candidates, indices)
    for identifier, feature in candidates.items():
        rings = boundary_rings(body, feature)
        if rings is None:
            # Eine Krümmungstrennung kann einzelne Randdreiecke zurücklassen.
            # Der vollständige, belegte Übergang besitzt trotzdem saubere Ringe.
            complete = _face_boundary_rings(body, np.asarray(sorted(indices), dtype=np.int64))
            if complete is None or len(complete) != 2:
                return ()
            continue
        for ring in rings:
            owners.setdefault(ring, []).append(identifier)
    for adjacent, faces in _shoulder_connections(body, owners, candidates):
        if len(adjacent) != 2 or len(set(adjacent)) != 2:
            continue
        first, second = (candidates[identifier] for identifier in adjacent)
        if _axis_lines_agree(first, second) and set(first.face_indices).isdisjoint(
            second.face_indices
        ):
            indices.update(faces)
    return tuple(sorted(indices))


def _blended_cavity_faces(
    body: trimesh.Trimesh, candidates: Mapping[FeatureId, Feature], indices: set[int]
) -> set[int]:
    """Tangentiale Innenübergänge bis zu den beiden äußeren Randringen ergänzen.

    Ein kleiner gerundeter Eintritt hat häufig kein eigenes Merkmal. Seine
    Fläche gehört trotzdem zur Bohrung: Sie ist glatt verbunden, zeigt zur
    selben Achse und endet gemeinsam mit der Wand in zwei vollständigen Ringen.
    Ebene Böden und Außenseiten bleiben außerhalb dieses Flächenausschnitts.
    """
    bore = next((feature for feature in candidates.values() if feature.kind == "hole"), None)
    if bore is None or (axis := axis_of(bore)) is None or (centre := centre_of(bore)) is None:
        return indices
    allowed = np.ones(len(body.faces), dtype=bool)
    allowed[list(_large_facet_faces(body))] = False
    allowed[list(indices)] = True
    pairs = np.asarray(body.face_adjacency, dtype=np.int64)
    if not len(pairs):
        return indices
    smooth = np.degrees(np.asarray(body.face_adjacency_angles)) < CURVATURE_LIMIT
    pairs = pairs[smooth & allowed[pairs[:, 0]] & allowed[pairs[:, 1]]]
    if not len(pairs):
        return indices
    labels = trimesh.graph.connected_component_labels(  # type: ignore[no-untyped-call]
        pairs, node_count=len(body.faces)
    )
    expanded = np.flatnonzero(np.isin(labels, labels[list(indices)]))
    extra = np.asarray([index for index in expanded if index not in indices], dtype=np.int64)
    if not len(extra):
        return indices
    towards = np.asarray(centre) - np.asarray(body.triangles_center)[extra]
    direction = np.asarray(axis)
    towards -= np.outer(towards @ direction, direction)
    inward = np.einsum("ij,ij->i", towards, np.asarray(body.face_normals)[extra])
    if bool(np.any(inward < -EPS_GEOM)):
        return indices
    rings = _face_boundary_rings(body, expanded)
    if rings is None or len(rings) != 2:
        return indices
    return {int(index) for index in expanded}


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
_DIAGNOSTIC_PARAMETERS = frozenset(
    {"residual", "local_search_radius", "profile_clamp", "profile_clamp_y"}
)


@dataclass(frozen=True)
class _SurfacePatch:
    """Ein echter Flächenausschnitt und seine nur bei Bedarf gebildeten Suchbäume."""

    points: NDArray[np.float64]
    edge_lengths: NDArray[np.float64]

    @cached_property
    def points_tree(self) -> Any:
        """Den räumlichen Suchbaum für alle Vergleiche dieses Ausschnitts teilen."""
        return cKDTree(self.points)

    @cached_property
    def edges_tree(self) -> Any:
        """Die Dreiecksformen einmal indizieren, bevor die Punktabdeckung folgt."""
        return cKDTree(self.edge_lengths)


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


#: Die drei Felder, die eine Stelle nennen — und deshalb nie an ein anderes
#: Merkmal reisen (:func:`params_for_members`).
_PLACE_AXES: Final = ("x", "y", "z")


def params_for_members(
    params: Mapping[str, Any],
    picked: FeatureId,
    members: Sequence[FeatureId],
    features: Mapping[FeatureId, Feature],
) -> dict[FeatureId, dict[str, Any]]:
    """Die Werte einer Handlung für jedes Mitglied ihrer Gruppe.

    Maße reisen unverändert: Ein Durchmesser gilt jeder Bohrung gleich. **Eine
    Stelle reist nicht.** ``x``, ``y`` und ``z`` nennen einen Ort, und derselbe
    Ort für sechs Bohrungen legte sie übereinander (Robert, 16.09.2026: „alle
    sind übereinander") — das Merkmalfenster trägt die Stelle beim Ändern
    einer Bohrung mit, und bis hierher gab das Fenster sie an jedes Mitglied
    weiter. Jedes Mitglied behält deshalb seine eigene gemessene Mitte; was
    am gewählten Merkmal gegenüber seiner Mitte verschoben wurde, geht als
    **Versatz** mit — *Merkmal verschieben* für alle heißt so „alle um
    dasselbe", und ohne Verschiebung bleibt jedes, wo es ist. Genannt wird je
    Mitglied nur, was am gewählten genannt war; eine ungenannte Achse bleibt
    ungenannt (RM-154). Ein Mitglied ohne gemessene Mitte bekommt keine
    Stelle. Das gewählte Merkmal bekommt seine Werte, wie sie sind.
    """
    named = tuple(params.get(axis) for axis in _PLACE_AXES)
    anchor = _centre_of(features.get(picked))
    result: dict[FeatureId, dict[str, Any]] = {}
    for member in members:
        if member == picked:
            result[member] = {**params, "at_feature": member}
            continue
        values = {key: value for key, value in params.items() if key not in _PLACE_AXES}
        values["at_feature"] = member
        centre = _centre_of(features.get(member))
        if anchor is not None and centre is not None:
            for axis, value, own, base in zip(_PLACE_AXES, named, centre, anchor, strict=True):
                if value is not None:
                    values[axis] = own + (float(value) - base)
        result[member] = values
    return result


def _centre_of(feature: Feature | None) -> tuple[float, float, float] | None:
    """Die gemessene Mitte eines Merkmals — oder nichts, wenn es keine trägt."""
    if feature is None:
        return None
    centre = feature.params.get("centre")
    if not isinstance(centre, tuple | list) or len(centre) != 3:
        return None
    try:
        return (float(centre[0]), float(centre[1]), float(centre[2]))
    except TypeError, ValueError:
        return None


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
        source = feature_value_source(entry.name, feature)
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
    if reference.kind == candidate.kind == "fillet" and is_a_cavity(reference) != is_a_cavity(
        candidate
    ):
        return "different", None
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
    edges_to_candidate = candidate.edges_tree.query(reference.edge_lengths, p=np.inf)[0]
    edges_to_reference = reference.edges_tree.query(candidate.edge_lengths, p=np.inf)[0]
    if (
        float(np.max(edges_to_candidate, initial=0.0)) > EPS_DISPLAY
        or float(np.max(edges_to_reference, initial=0.0)) > EPS_DISPLAY
    ):
        return False
    to_candidate = candidate.points_tree.query(reference.points)[0]
    to_reference = reference.points_tree.query(candidate.points)[0]
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
