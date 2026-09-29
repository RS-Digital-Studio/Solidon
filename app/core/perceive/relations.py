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
from typing import Any, Final, Literal, NamedTuple, cast

import numpy as np
from numpy.typing import NDArray

from app.core import units
from app.core.deferred import cKDTree, trimesh
from app.core.geom.mesh import MeshData, unique_edges
from app.core.log import get_logger
from app.core.perceive.actions import ACTION_ORDER, feature_value_source
from app.core.perceive.features import (
    CURVATURE_LIMIT,
    EPS_ANGLE,
    SINK_AXIS_LIMIT,
    SINK_FIT_LIMIT,
    _large_facet_faces,
    _neighbour_index,
    _one_body,
    axis_of,
    centre_of,
    remembered,
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


def group_evidence_texts() -> dict[FeatureGroupEvidence, str]:
    """Ein Satz je Nachweis einer Sammelgruppe — für Panel und Steckbrief dieselben.

    Zur Laufzeit übersetzt, nicht beim Import: Die Sprache kann wechseln.
    ``test_feature_panel`` hält die Schlüssel mit :data:`FeatureGroupEvidence`
    deckungsgleich; ein neuer Wert dort ist sonst ein ``KeyError`` mitten in
    der Merkmalsauswahl. Bis zum 20.09.2026 standen die Sätze im Panel; seit
    der Steckbrief sie auch liest (P1.5), stehen sie hier einmal.
    """
    from app.i18n import tr

    return {
        "same_target_dimensions": tr("Gleiches Ausgangsmaß für diese Änderung."),
        "complete_surface_patch": tr("Die vollständige bearbeitete Form stimmt überein."),
        "parallel_axes": tr("Die Achsen sind parallel ausgerichtet."),
        "shared_boundary_role": tr("Die Merkmale haben dieselbe Rolle in ihrer Bohrungskette."),
        "translation_consistent": tr("Die zugehörigen Abschnitte liegen gleich zueinander."),
    }


def group_reason_texts() -> dict[FeatureGroupReason, str]:
    """Ein Satz je Grund, warum ein Merkmal nicht sicher dazugehört — siehe
    :func:`group_evidence_texts`."""
    from app.i18n import tr

    return {
        "selected_feature_unavailable": tr("Das gewählte Merkmal ist nicht mehr vorhanden."),
        "action_not_applicable": tr("Diese Handlung passt nicht zu den weiteren Merkmalen."),
        "ambiguous_cavity_chain": tr("Die zugehörigen Bohrungsabschnitte sind nicht eindeutig."),
        "cavity_topology_unavailable": tr(
            "Die Verbindung der Bohrungsabschnitte ist nicht sicher erkannt."
        ),
        "dimensions_unavailable": tr("Die benötigten Maße sind nicht sicher erkannt."),
        "complete_shape_unavailable": tr("Die vollständige Form ist nicht sicher vergleichbar."),
        "orientation_unavailable": tr("Die Ausrichtung ist nicht sicher erkannt."),
        "relative_position_unavailable": tr(
            "Die Lage der zugehörigen Abschnitte ist nicht sicher erkannt."
        ),
    }


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

    Die letzte Zeile ist ein gebauter Fall und kein gemessener Kunde. Eine
    **Obergrenze** war sie nur, solange ``scene.evaluate.FEATURE_LIMIT_COUNT``
    bei tausend stand: Mit fünftausend (22.09.2026) kostete halb Hohlraum,
    halb Materie als Paarung jede gegen jede **22 Sekunden** — nach jeder
    Auswertung und im Steckbrief im Hauptfaden (Review 22.09.2026). Seither
    wählt :func:`_all_sleeves` die Kandidaten über die Mitten vor: Ein Rohr
    liegt mit seiner Mitte höchstens ``r · SINK_FIT_LIMIT`` quer und eine
    halbe Summe der Tiefen längs von der Bohrungsmitte entfernt, und ein
    ``cKDTree`` über die Zapfenmitten gibt je Bohrung nur diese zurück; die
    Paarprüfung selbst bleibt dieselbe. Was echte Modelle mitbringen, liegt
    ohnehin zwei Größenordnungen darunter: über die zwanzig Netze des Korpus
    gemessen sind es höchstens **16** Merkmale.
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
    if abs(float(one.axis @ other.axis)) < units.exact_cos_degrees(SINK_AXIS_LIMIT):
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
    """Alle belegten Rohrpaare, mit einmal gelesenen Maßen je Merkmal.

    Gepaart wird nur, was nach Lage überhaupt ein Rohr sein kann: Der Mantel
    muss mit seiner Mitte innerhalb von ``r · SINK_FIT_LIMIT`` quer und einer
    halben Summe beider Tiefen längs zur Bohrungsmitte liegen, sonst gibt
    :func:`_sleeve_between` ohnehin nichts zurück (``reach``,
    :func:`_overlap`). Die Kugel um die Bohrungsmitte mit der Summe beider
    Schranken enthält deshalb jeden Partner; die längste Manteltiefe steht
    für alle, damit ein Baum die Frage für alle Bohrungen zugleich beantwortet.
    Die Reihenfolge der Kandidaten bleibt die der Merkmale — bei gleicher
    Wandstärke entscheidet sie, wie bisher.
    """
    measured = [entry for entry in map(_measured, features.values()) if entry is not None]
    hollow = [entry for entry in measured if entry.inside]
    solid = [entry for entry in measured if not entry.inside]
    if not hollow or not solid:
        return
    tree = cKDTree(np.asarray([entry.centre for entry in solid], dtype=float))
    longest = max(entry.depth for entry in solid)
    centres = np.asarray([entry.centre for entry in hollow], dtype=float)
    radii = np.asarray(
        [
            entry.diameter / 2.0 * SINK_FIT_LIMIT + (entry.depth + longest) / 2.0 + EPS_GEOM
            for entry in hollow
        ],
        dtype=float,
    )
    for bore, near in zip(hollow, tree.query_ball_point(centres, radii), strict=True):
        for index in sorted(near):
            found = _sleeve_between(bore, solid[index])
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


def ring_in_order(ring: Iterable[tuple[int, int]]) -> list[int]:
    """Die Ecken eines geschlossenen Randrings in Laufrichtung.

    :func:`boundary_rings` liefert jeden Ring als Kantenmenge; wer ihn als Zug
    braucht — den Sockel unter einem Merkmal, die Ränder eines Rings, die
    Kontur einer Fläche in der Skizze —, liest ihn hier. Beginnt an der
    kleinsten Ecke.

    **Eine Stelle für alle Leser** (RM-188 P3.4): Die Reihenfolge stand bis
    zum 23.09.2026 privat in ``geom.prepare_ops``, und die Flächenkontur der
    Skizze hätte sie ein zweites Mal gebraucht.
    """
    neighbours: dict[int, list[int]] = {}
    for a, b in ring:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    if not neighbours:
        return []
    first = min(neighbours)
    ordered = [first]
    previous, current = -1, first
    while len(ordered) <= len(neighbours):
        following = next((value for value in neighbours[current] if value != previous), None)
        if following is None or following == first:
            break
        ordered.append(following)
        previous, current = current, following
    return ordered


def _face_boundary_rings(
    body: trimesh.Trimesh, indices: NDArray[np.int64]
) -> list[frozenset[tuple[int, int]]] | None:
    """Die geschlossenen Randkomponenten eines zusammenhängenden Flächenausschnitts."""
    if not len(indices) or indices.min() < 0 or indices.max() >= len(body.faces):
        return None
    faces = np.asarray(body.faces)[indices]
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    unique, count = unique_edges(edges, return_counts=True)
    if (count > 2).any():
        return None
    boundary = unique[count == 1]
    if not len(boundary):
        return None
    vertices, inverse, degrees = np.unique(boundary, return_inverse=True, return_counts=True)
    if (degrees != 2).any():
        return _rings_through_a_shared_corner(body, indices, boundary, vertices, degrees)
    # **Die Komponenten in der Nummerierung des Rands, nicht des Körpers.**
    # ``trimesh.graph.connected_components`` legt je Aufruf Felder über alle
    # Ecken des Körpers an. ``_shoulder_connections`` fragt je ebener Facette
    # am Hohlraum — am Gartenschlauchhalter 2 091-mal über 196 000 Ecken, 2,4
    # von 3,4 s des ersten Klicks, im Qt-Hauptthread (RM-181, 23.09.2026).
    # Die Reihenfolge bleibt dieselbe: scipy vergibt die Nummern nach der
    # kleinsten Ecke einer Komponente, und ``vertices`` ist aufsteigend.
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    local = np.asarray(inverse, dtype=np.int64).reshape(boundary.shape)
    size = len(vertices)
    graph = coo_matrix(
        (np.ones(len(local), dtype=np.int8), (local[:, 0], local[:, 1])), shape=(size, size)
    )
    number, labels = connected_components(graph, directed=False)
    rings = []
    for label in range(number):
        component = vertices[labels == label]
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
        # **Begonnen wird an der geteilten Ecke, wo es eine gibt.** Ein Lauf,
        # der mitten in einem Lappen anfängt, endet auch dort; geschnitten
        # wird aber an der Ecke, und der erste und der letzte Teil wären dann
        # zwei Hälften desselben Lappens. Gemessen am nachgestellten Netz:
        # Von der Ecke aus kommen die zwei Kreise heraus, von irgendwo aus
        # ein Lappen mit beiden Randhöhen darin.
        start = next(
            (edge for edge in remaining if shared & {edge[0], edge[1]}),
            next(iter(remaining)),
        )
        ring = [start]
        remaining.discard(start)
        # Weg **von** der geteilten Ecke, damit der Lauf erst an ihr endet.
        ahead = start[1] if start[0] in shared else start[0]
        edge = start
        while True:
            following = _next_boundary_edge(edge, ahead, remaining, partner, shared)
            if following is None:
                break
            edge, ahead = following
            ring.append(edge)
            remaining.discard(edge)
        if len(ring) < 3:
            return None
        rings.extend(_lobes_of(ring, shared))
    return rings or None


def _lobes_of(ring: list[tuple[int, int]], shared: set[int]) -> list[frozenset[tuple[int, int]]]:
    """Ein Rand, der zweimal durch dieselbe Ecke läuft, ist zwei Ränder.

    **Die Acht ist die Gestalt, in der der Mac-Fall auftritt** (17.09.2026).
    Der Fächer verbindet dort oben und unten: Der Mantel der Senkung berührt
    sich in einem Punkt, und der Lauf kommt als **ein** geschlossener Zug
    zurück, der diesen Punkt zweimal besucht. Für die Nachbarschaft sind aber
    die beiden Lappen gemeint — der obere und der untere Kreis —, und genau
    die vergleicht ``_shoulder_connections`` mit dem Rand ihrer Schulter.

    Geschnitten wird deshalb an jedem zweiten Besuch einer geteilten Ecke.
    Ein Zug, der sie nur einmal berührt, bleibt ein Ring: Dort ist nichts zu
    trennen, und ein Lappen von zwei Kanten wäre kein Rand.
    """
    if not shared:
        return [frozenset(ring)]
    lobes: list[frozenset[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for edge in ring:
        current.append(edge)
        # Geschnitten wird **hinter** der Kante, die in die geteilte Ecke läuft
        # — dort schließt sich der Lappen.
        if len(current) > 2 and shared & {edge[0], edge[1]}:
            lobes.append(frozenset(current))
            current = []
    if current:
        if lobes:
            # Der Rest gehört an den Anfang: Der Lauf hat mitten in einem
            # Lappen begonnen, und dessen zwei Hälften sind einer.
            lobes[0] = frozenset(lobes[0] | frozenset(current))
        else:
            lobes.append(frozenset(current))
    return [lobe for lobe in lobes if len(lobe) >= 3] or [frozenset(ring)]


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
    return cavity_chain_state_at(feature, features, mesh).chain


class CavityState(NamedTuple):
    """Was ein Hohlraum von seinen Nachbarn weiß — die eine Auskunft für alle Verbraucher.

    ``chain`` ist die eindeutige Kette, deren Abschnitt das Merkmal ist, oder
    ``None``. ``touches_other`` heißt: **nicht sicher einzeln** — ein fremder
    Rand ist berührt, oder die Ränder des Merkmals lassen sich nicht lesen;
    nur ohne beides darf eine Geometrieoperation den Hohlraum allein
    verschieben. Warum, sagt ``reason`` mit demselben Wort wie der Gruppenweg
    (:func:`_feature_group_topology`): ``ambiguous_cavity_chain`` für die
    Berührung ohne Kette, ``cavity_topology_unavailable`` für Ränder, die
    keine Ringe ergeben (veraltete Flächennummern, eine Naht mit drei
    Dreiecken, ein Fleck ohne Rand). Bis zum 20.09.2026 fiel der zweite Fall
    im Einzelweg auf ``(None, False)`` — „steht allein" — und nur der
    Gruppenweg kannte ihn (P1.5).
    """

    chain: tuple[Feature, ...] | None
    touches_other: bool
    reason: FeatureGroupReason | None


def cavity_is_shared(state: CavityState) -> bool:
    """Ob ein Hohlraum anderen Abschnitten gehört — die eine Bedingung für alle.

    Eine Kette heißt, das Merkmal ist ein Abschnitt von mehreren (eine Kette
    hat immer mindestens zwei Glieder, :func:`_ordered_cavity`); ein berührter
    fremder Rand heißt, die Nachbarschaft ist da und nur nicht eindeutig —
    und unlesbare Ränder zählen dazu (:class:`CavityState`). Beides zusammen
    entscheidet, ob *Zum Langloch ziehen*, *Merkmal drehen* und *Merkmal
    verdoppeln* absagen und ob das Merkmalfenster ihre Zeile vorher grau
    stellt. Bis zum 14.09.2026 stand die Bedingung an zwei Stellen wörtlich
    gleich — und nichts wurde rot, wenn eine sich löste.
    """
    return state.touches_other or state.chain is not None


def cavity_chain_state_at(
    feature: Feature, features: Mapping[FeatureId, Feature], mesh: MeshData
) -> CavityState:
    """Die Kette, ob der gewählte Abschnitt sicher einzeln ist, und der Grund.

    Die zweite Auskunft trennt eine sicher einzelne Bohrung von einer
    mehrdeutigen oder unlesbaren Kette. Beide liefern keine Kette, aber nur
    die einzelne darf eine Geometrieoperation allein verschieben. Auch bei
    drei Besitzern desselben Randrings bleibt die Berührung erhalten, obwohl
    daraus absichtlich keine Verbindung gewählt wird.
    """
    if feature.kind not in {"hole", "cone"} or not is_a_cavity(feature):
        return CavityState(None, False, None)
    candidates = {
        identifier: candidate
        for identifier, candidate in features.items()
        if candidate.kind in {"hole", "cone"} and is_a_cavity(candidate)
    }
    if feature.id not in candidates:
        return CavityState(None, False, None)
    graph, invalid, touching = _cavity_links(candidates, mesh)
    chain = _ordered_cavity(feature.id, candidates, graph, invalid)
    if chain is not None:
        return CavityState(chain, feature.id in touching, None)
    if feature.id in touching:
        return CavityState(None, True, "ambiguous_cavity_chain")
    # Unlesbar sind Ränder, die das Merkmal **beansprucht** und die keine Ringe
    # ergeben. Ein erzeugtes Merkmal ohne Flächennummern beansprucht keine —
    # es kennt seine Form aus den Zahlen, und die Operation geht diesen Weg
    # (``test_surface_placement``: ``hole_9`` mit ``provenance="generated"``).
    if feature.id in invalid and feature.face_indices:
        return CavityState(None, True, "cavity_topology_unavailable")
    return CavityState(None, False, None)


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

    **Und keine Lage.** Bis zum 22.09.2026 standen Achse und Mitte mit im
    Schlüssel; damit war der Eintrag nach jedem Verschieben wertlos, obwohl
    die Antwort — welche Ringe welche Merkmale teilen — an der Lage nicht
    hängt: Gelesen werden Dreiecksnummern, und Achsen nur im Verhältnis
    zueinander. Am selben Netz meinen gleiche Flächen dieselbe Geometrie, und
    ``geom.transform.apply`` reicht den Eintrag an die bewegte Kopie weiter.
    """
    return tuple(
        (name, candidate.kind, hash(tuple(candidate.face_indices)))
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
    # **Eine angeschnittene Bohrung an einer fremden Höhlung ist berührt.**
    # Ihre Schnittlinien sind kein Ring; über die Ringe fände sie keinen
    # Nachbarn — und stünde als sicher einzeln da, obwohl ihr Mantel in die
    # Nachbarbohrung mündet (P1.5, Gegenfall 2). Berührt heißt hier wie bei
    # drei Ringbesitzern: keine Kette, kein eigener Körper.
    touching.update(_cut_open_neighbours(body, candidates))
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


def _cut_open_neighbours(
    body: trimesh.Trimesh, candidates: Mapping[FeatureId, Feature]
) -> set[FeatureId]:
    """Angeschnittene Kandidaten und die, deren Dreiecke sie an der Schnittlinie berühren."""
    partial = [
        identifier
        for identifier, candidate in candidates.items()
        if candidate.params.get("partial") and candidate.face_indices
    ]
    if not partial or not len(body.face_adjacency):
        return set()
    names = list(candidates)
    owner = np.full(len(body.faces), -1, dtype=np.int64)
    for number, identifier in enumerate(names):
        indices = np.asarray(candidates[identifier].face_indices, dtype=np.int64)
        if len(indices) and indices.min() >= 0 and indices.max() < len(body.faces):
            owner[indices] = number
    pairs = np.asarray(body.face_adjacency, dtype=np.int64)
    first, second = owner[pairs[:, 0]], owner[pairs[:, 1]]
    cut = {names.index(identifier) for identifier in partial}
    touching: set[FeatureId] = set()
    across = (first != second) & (first >= 0) & (second >= 0)
    for one, other in zip(first[across].tolist(), second[across].tolist(), strict=True):
        if one in cut or other in cut:
            touching.add(names[one])
            touching.add(names[other])
    return touching


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
    near = [
        indices
        for facet in body.facets
        if starts[(indices := np.asarray(facet, dtype=np.int64))].any()
    ]
    for indices in _only_owned_rims(body, near, edge_codes):
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


def _only_owned_rims(
    body: trimesh.Trimesh,
    facets: Sequence[NDArray[np.int64]],
    owned: NDArray[np.int64],
) -> list[NDArray[np.int64]]:
    """Die Facetten, deren Rand ganz aus belegten Ringkanten besteht — in ihrer Reihenfolge.

    Eine notwendige Bedingung für :func:`_shoulder_connections`, in einem Zug
    über alle Facetten statt je Facette: Eine Schulter hat genau zwei belegte
    Ringe als Rand. Trägt eine Facette eine Randkante, die in keinem belegten
    Ring liegt, ist der Ring dieser Kante kein belegter, und die volle Prüfung
    ließe die Facette fallen. Ebenso eine ohne Rand und eine, in der mehr als
    zwei ihrer Dreiecke eine Kante teilen — dort gibt
    :func:`_face_boundary_rings` ``None``. Gezählt wird wie dort: die Kanten
    je Zeile sortiert, eine Kante mit Zähler eins ist Rand.

    **Warum überhaupt.** Am Gartenschlauchhalter (392 532 Dreiecke) fragte
    der erste Klick 2 091 Facetten am Hohlraum einzeln nach ihren Ringen, jede
    mit dem festen Aufwand einer Komponentensuche — 1,7 von 3,0 s im
    Qt-Hauptthread (RM-181, 23.09.2026). Übrig bleiben die wenigen, an denen
    sich die Ringsuche lohnt; welche davon Schultern sind, entscheidet
    unverändert die volle Prüfung.
    """
    if not facets:
        return []
    lengths = np.fromiter((len(indices) for indices in facets), dtype=np.int64, count=len(facets))
    labels = np.repeat(np.arange(len(facets), dtype=np.int64), lengths)
    faces = np.asarray(body.faces, dtype=np.int64)[np.concatenate(facets)]
    edges = np.sort(np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1)
    codes = edges[:, 0] * len(body.vertices) + edges[:, 1]
    owners = np.tile(labels, 3)
    order = np.lexsort((codes, owners))
    codes, owners = codes[order], owners[order]
    first = np.ones(len(codes), dtype=bool)
    first[1:] = (codes[1:] != codes[:-1]) | (owners[1:] != owners[:-1])
    runs = np.flatnonzero(first)
    counts = np.diff(np.append(runs, len(codes)))
    run_codes, run_owners = codes[runs], owners[runs]
    rim = counts == 1
    rejected = np.zeros(len(facets), dtype=bool)
    rejected[run_owners[counts > 2]] = True
    rejected[run_owners[rim & ~np.isin(run_codes, owned)]] = True
    bounded = np.zeros(len(facets), dtype=bool)
    bounded[run_owners[rim]] = True
    return [
        indices for indices, kept in zip(facets, bounded & ~rejected, strict=True) if bool(kept)
    ]


#: Ein Dreieck, das kein Merkmal beansprucht.
NO_OWNER: Final[int] = -1
#: Ein Dreieck, das zwei Merkmale beanspruchen, ohne dass eines im anderen liegt.
CONTESTED: Final[int] = -2


def cell_owner_table(
    features: Mapping[FeatureId, Feature], face_count: int
) -> tuple[tuple[FeatureId, ...], NDArray[np.int32]]:
    """Je Dreieck die Nummer des Merkmals, dem es gehört — für den Klick im Bild.

    Beansprucht ein Dreieck nur ein Merkmal, gehört es ihm. Beanspruchen es
    zwei, entscheidet die **Verschachtelung**: Liegen alle Flächen des einen
    in denen des anderen, ist das eine ein Teil des anderen, und der Klick auf
    das Teil meint das Teil — der Zapfen auf der Insel in einem Lufteinschluss,
    dessen Oberfläche zur vollständigen Auswahl des Einschlusses gehört. Das
    innerste gewinnt. Überlappen sich zwei, ohne dass eines im anderen liegt,
    ist das ein Widerspruch der Erkennung und kein Fall für eine Reihenfolge:
    Die Zelle trägt :data:`CONTESTED`, und der Viewport fällt auf den
    Ortsfang zurück, statt den alphabetisch ersten zu nehmen (P1.5,
    Durchsicht der Verbraucher; am Korpus teilt heute kein Dreieck zwei
    Merkmale, gemessen 20.09.2026 über 32 Dateien).

    Nummern außerhalb des Körpers werden übergangen; die Reihenfolge der
    Merkmale ist ohne Bedeutung, das Ergebnis dasselbe.
    """
    ids = tuple(features)
    cells = np.full(face_count, NO_OWNER, dtype=np.int32)
    arrays: list[np.ndarray] = []
    sets: dict[int, set[int]] = {}

    def members(number: int) -> set[int]:
        """Die Flächenmenge eines Merkmals — erst gebaut, wenn zwei sich überlappen.

        Der Viewport fragt die Tabelle im Hauptfaden; eine Menge aus Python-
        Zahlen je Merkmal kostete an einem Körper mit 400 000 Dreiecken rund
        100 ms für Merkmale, die kein Dreieck teilen (gemessen 21.09.2026).
        """
        if number not in sets:
            sets[number] = {int(index) for index in arrays[number]}
        return sets[number]

    for number, feature in enumerate(features.values()):
        indices = np.asarray(feature.face_indices, dtype=np.int64)
        indices = indices[(indices >= 0) & (indices < face_count)]
        arrays.append(indices)
        previous = cells[indices]
        free = previous == NO_OWNER
        cells[indices[free]] = number
        clashing = previous[(previous >= 0) & ~free]
        if not len(clashing):
            continue
        own = members(number)
        for other in np.unique(clashing):
            shared = indices[previous == other]
            theirs = members(int(other))
            if own < theirs:
                cells[shared] = number
            elif theirs < own:
                continue
            else:
                cells[shared] = CONTESTED
    return ids, cells


def _shape_key(features: Iterable[Feature]) -> tuple[Any, ...]:
    """Woran eine Flächenauskunft hängt: Kennung, Art, Dreiecke, Achse und Mitte je Merkmal.

    Der Schlüssel der Merker unten — dieselben Dreiecke unter einem anderen
    Namen oder mit anderer Achse sind eine andere Frage.
    """
    return tuple(
        (
            str(feature.id),
            feature.kind,
            tuple(feature.face_indices),
            tuple(float(value) for value in feature.params["axis"])
            if "axis" in feature.params
            else None,
            tuple(float(value) for value in feature.params["centre"])
            if "centre" in feature.params
            else None,
        )
        for feature in features
    )


def cavity_surface_indices(
    mesh: MeshData, features: Iterable[Feature], *, mouth_blends: bool = False
) -> tuple[int, ...]:
    """Die belegten Hohlraumflächen einschließlich ihrer ebenen Ringschultern.

    Der Aufrufer übergibt die zuvor ermittelte vollständige Kette. Zusätzliche
    Flächen kommen nur hinzu, wenn ihre beiden Randringe eindeutig zu zwei
    verschiedenen, koaxialen Abschnitten gehören. So benutzt die Bearbeitung
    dieselben echten Schulterflächen wie die Erkennung des Zusammenhangs.

    ``mouth_blends`` nimmt auch die gerundete Mündungskante einer Kette mit
    Schulter dazu (:func:`_blended_cavity_faces`, RM-259) — für die Wege, auf
    denen der ganze Hohlraum reist oder geht: Versetzen, Verdoppeln, Muster
    und Entfernen. Ändern und Kippen schneiden aus Profilen und Kennzahlen neu,
    die eine Rundung nicht kennen; ein Stopfen samt Rundung ließe dort eine
    Haut über der neuen Mündung stehen (gemessen am Nachbau mit Rundung R 1,
    ``m21_aendern``). Dort bleibt die Rundung, wie sie war.

    Gemerkt je Körper und Kette (:func:`features.remembered`): Ansicht,
    Merkmalfenster und die Frage nach dem eigenen Körper stellen sie nach
    jedem Klick nacheinander — an der Lochplatte mit 360 000 Dreiecken je
    0,11 s (gemessen am 22.09.2026), und alle lesen dieselbe Antwort.
    """
    body = _one_body(mesh).raw
    candidates = {feature.id: feature for feature in features}
    answer: tuple[int, ...] = remembered(
        "cavity_surface",
        body,
        (),
        lambda: _cavity_surface_indices_read(body, candidates, mouth_blends=mouth_blends),
        # Nach Kennung sortiert: Die Antwort hängt nicht an der Reihenfolge,
        # in der Ansicht und Merkmalfenster die Kette nennen.
        extra=(mouth_blends, _shape_key(candidates[name] for name in sorted(candidates))),
    )
    return answer


def _cavity_surface_indices_read(
    body: trimesh.Trimesh, candidates: Mapping[FeatureId, Feature], *, mouth_blends: bool = False
) -> tuple[int, ...]:
    """Der Rumpf von :func:`cavity_surface_indices` — die Antwort merkt sich die Hülle."""
    owners: dict[frozenset[tuple[int, int]], list[FeatureId]] = {}
    indices = {index for feature in candidates.values() for index in feature.face_indices}
    if not indices or min(indices) < 0 or max(indices) >= len(body.faces):
        return ()
    indices = _blended_cavity_faces(body, candidates, indices, mouth_blends=mouth_blends)
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
    body: trimesh.Trimesh,
    candidates: Mapping[FeatureId, Feature],
    indices: set[int],
    *,
    mouth_blends: bool = False,
) -> set[int]:
    """Tangentiale Innenübergänge bis zu den beiden äußeren Randringen ergänzen.

    Ein kleiner gerundeter Eintritt hat häufig kein eigenes Merkmal. Seine
    Fläche gehört trotzdem zur Bohrung: Sie ist glatt verbunden, zeigt zur
    selben Achse und endet gemeinsam mit der Wand in zwei vollständigen Ringen.
    Ebene Böden und Außenseiten bleiben außerhalb dieses Flächenausschnitts.

    **Gesucht wird ab der Wand, nicht im ganzen Netz** (RM-232): Glatt über
    eine Naht verbunden und keine große ebene Fläche, außer sie gehört selbst
    zur Wand — dieselben Stücke, die die Zusammenhangskomponenten des ganzen
    Netzes lieferten, über den Nachbarindex des Körpers
    (``features._neighbour_index``). Diese legten je Bohrung Felder und
    Komponenten über alle Dreiecke an, und die Markierung zahlte das beim
    ersten Klick im Hauptfaden: an der dichten Platte 15 von 25 ms je Bohrung.
    """
    bore = next((feature for feature in candidates.values() if feature.kind == "hole"), None)
    if bore is None or (axis := axis_of(bore)) is None or (centre := centre_of(bore)) is None:
        return indices
    neighbours, seams = _neighbour_index(body)
    if not neighbours.shape[1]:
        return indices
    large = _large_facet_faces(body)
    angles = np.asarray(body.face_adjacency_angles)
    reached = set(indices)
    frontier = np.fromiter(sorted(indices), dtype=np.int64, count=len(indices))
    while len(frontier):
        near, seam = neighbours[frontier].reshape(-1), seams[frontier].reshape(-1)
        near = near[(near >= 0) & (np.degrees(angles[np.maximum(seam, 0)]) < CURVATURE_LIMIT)]
        fresh = [
            index
            for index in np.unique(near).tolist()
            if index not in reached and (index in indices or index not in large)
        ]
        reached.update(fresh)
        frontier = np.asarray(fresh, dtype=np.int64)
    expanded = np.asarray(sorted(reached), dtype=np.int64)
    extra = np.asarray([index for index in expanded if index not in indices], dtype=np.int64)
    if not len(extra):
        return indices
    # Elementweise statt über ``@`` und ``einsum`` (RM-187): Am Vorzeichen
    # hängt, ob der Übergang zur Wand gehört.
    towards = np.asarray(centre, dtype=np.float64) - np.asarray(body.triangles_center)[extra]
    direction = np.asarray(axis, dtype=np.float64)
    along = (
        towards[:, 0] * direction[0] + towards[:, 1] * direction[1] + towards[:, 2] * direction[2]
    )
    towards = towards - along[:, None] * direction
    normals = np.asarray(body.face_normals)[extra]
    inward = (
        towards[:, 0] * normals[:, 0]
        + towards[:, 1] * normals[:, 1]
        + towards[:, 2] * normals[:, 2]
    )
    if bool(np.any(inward < -EPS_GEOM)):
        return indices
    rings = _face_boundary_rings(body, expanded)
    if not mouth_blends:
        if rings is None or len(rings) != 2:
            return indices
        return {int(index) for index in expanded}
    # **So viele Randringe wie vorher, nicht zwei** (RM-259, Durchsicht 0.5.1):
    # Ein Übergang ersetzt den Rand, an dem er beginnt, durch seinen äußeren —
    # mehr ändert sich nicht. Eine Kette mit Zylindersenkung hat vor ihren
    # Schultern (:func:`_shoulder_connections`, die erst danach dazukommen)
    # vier Ringe, und die gerundete Mündungskante unter der Senkung fiel
    # deshalb heraus: Beim Versetzen blieb an der alten Stelle eine Mulde von
    # 1 mm, an der neuen deckte eine Haut die Senkung zu.
    before = _face_boundary_rings(body, np.asarray(sorted(indices), dtype=np.int64))
    if rings is None or len(rings) != (2 if before is None else len(before)):
        return indices
    # **Und nah an der Wand** — ein Übergang ist schmal. Eine Bohrung am Grund
    # einer glatten Mulde erreichte sonst über die Flut die ganze Mulde.
    if not _near_the_wall(body, candidates, extra, axis, centre):
        return indices
    return {int(index) for index in expanded}


def _near_the_wall(
    body: trimesh.Trimesh,
    candidates: Mapping[FeatureId, Feature],
    extra: NDArray[np.int64],
    axis: Any,
    centre: Any,
) -> bool:
    """Ob ein ergänzter Übergang (``extra``) nah an der Wand bleibt: keine seiner
    Ecken weiter von der Achse als das Doppelte des weitesten Abschnitts.

    Eine gerundete oder gefaste Mündungskante reicht so weit, wie ihre Rundung
    breit ist — an der Lochplatte gs-100 1 mm über eine Senkung Ø 10. Was die
    Flut darüber hinaus erreicht, ist die Fläche, in die die Bohrung mündet, und
    die gehört nicht zum Hohlraum. Elementweise gerechnet (RM-187).
    """
    radii = [float(feature.params.get("diameter") or 0.0) / 2.0 for feature in candidates.values()]
    widest = max(radii, default=0.0)
    if widest <= EPS_GEOM:
        return False
    corners = np.asarray(body.vertices, dtype=np.float64)[
        np.unique(np.asarray(body.faces, dtype=np.int64)[extra])
    ]
    offset = corners - np.asarray(centre, dtype=np.float64)
    direction = np.asarray(axis, dtype=np.float64)
    along = offset[:, 0] * direction[0] + offset[:, 1] * direction[1] + offset[:, 2] * direction[2]
    across = offset - along[:, None] * direction
    distance = (
        across[:, 0] * across[:, 0] + across[:, 1] * across[:, 1] + across[:, 2] * across[:, 2]
    )
    limit = 2.0 * widest
    return bool(np.all(distance <= limit * limit))


def cavity_blend_indices(mesh: MeshData, features: Iterable[Feature]) -> tuple[int, ...]:
    """Die Dreiecke eines Hohlraums, die keinem seiner Abschnitte gehören und
    keine Schulter sind — seine glatten Übergänge, etwa die gerundete Kante an
    der Mündung (:func:`_blended_cavity_faces`).

    Der exakte Kern fragt danach, ob die Kette ganz aus ihren Profilen gebaut
    werden kann: Ein Profil kennt die Rundung nicht, und ein Stopfen daraus
    ließ an der alten Stelle die Mulde der Rundung stehen (RM-259). Nicht
    gemerkt — gefragt wird je Kettenhandlung einmal, nicht je Klick.
    """
    body = _one_body(mesh).raw
    candidates = {feature.id: feature for feature in features}
    own = {index for feature in candidates.values() for index in feature.face_indices}
    if not own or min(own) < 0 or max(own) >= len(body.faces):
        return ()
    return tuple(sorted(_blended_cavity_faces(body, candidates, set(own), mouth_blends=True) - own))


def _ordered_cavity(
    selected: FeatureId,
    candidates: Mapping[FeatureId, Feature],
    graph: Mapping[FeatureId, set[FeatureId]],
    invalid: set[FeatureId],
) -> tuple[Feature, ...] | None:
    """Den einfachen Pfad von der eindeutigen engen Bohrung aus lesen.

    **Die Bohrung steht vorn, dahinter je Seite ihre Erweiterungen nach
    außen** (RM-245, 25.09.2026). Bis dahin musste die engste Bohrung ein Ende
    des Pfads sein. An allen vier Lochplatten aus ``F:\\3D Dateien`` weitet
    sich aber jede Schraubbohrung an beiden Enden — hinten eine
    Zylindersenkung Ø 10, vorn eine Fase Ø 7 —, der Graph war sauber, und
    trotzdem sagten Kippen, Versetzen und Verdoppeln an allen neun ab: „geht
    in einen anderen Hohlraum über". Dasselbe an jeder beidseitig gefasten
    Durchgangsbohrung.

    Liegt die Bohrung in der Mitte, folgen auf sie erst die Abschnitte der
    einen, dann die der anderen Seite, jede Folge von der Bohrung weg
    geordnet; welche Seite zuerst kommt, entscheidet ihre Bauart
    (:func:`_side_order`), damit zwei gleiche Bohrungen dieselbe Kette
    ergeben. Wo die Stücke eines Pfads nicht eindeutig auf einer Seite der
    Bohrungsmitte liegen, gibt es keine Kette — :func:`cavity_sides` liest
    die Seiten an genau dieser Lage wieder heraus.
    """
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
    if not bores:
        return None
    if (
        len(bores) > 1
        and abs(float(bores[1].params["diameter"]) - float(bores[0].params["diameter"])) <= EPS_GEOM
    ):
        return None
    bore = bores[0].id
    sides: list[list[FeatureId]] = []
    for first in sorted(graph[bore]):
        side = [first]
        while len(following := graph[side[-1]] - {bore, *side}) == 1:
            side.append(next(iter(following)))
        if following:
            return None
        sides.append(side)
    if sum(len(side) for side in sides) + 1 != len(connected):
        return None
    arranged = _side_order(candidates, sides)
    ordered = (
        candidates[bore],
        *(candidates[identifier] for side in arranged for identifier in side),
    )
    split = _sides_of(ordered)
    if split is None or [[part.id for part in side[1:]] for side in split] != [
        list(side) for side in arranged
    ]:
        return None
    return ordered


def _side_order(
    candidates: Mapping[FeatureId, Feature], sides: Sequence[Sequence[FeatureId]]
) -> list[Sequence[FeatureId]]:
    """Die zwei Seiten einer Bohrung in einer Reihenfolge, die ihre Bauart
    festlegt und nicht die gemessene Achsrichtung.

    Die Achse einer erkannten Bohrung trägt ein beliebiges Vorzeichen; zwei
    gleiche Schraubbohrungen derselben Platte ergäben sonst Ketten mit
    vertauschten Seiten, und die Gruppenauskunft vergleicht Ketten Glied für
    Glied (:func:`_group_comparison`). Zuerst die längere Folge, dann nach den
    Arten ihrer Abschnitte, dann die weitere Mündung.
    """
    return sorted(
        sides,
        key=lambda side: (
            -len(side),
            tuple(candidates[identifier].kind for identifier in side),
            -float(candidates[side[-1]].params.get("diameter") or 0.0),
        ),
    )


def cavity_sides(chain: Sequence[Feature]) -> tuple[tuple[Feature, ...], ...]:
    """Die Erweiterungsfolgen einer Kette, jede mit der Bohrung vorn und nach
    außen geordnet — eine, oder zwei, wo sich die Bohrung an beiden Enden
    weitet (RM-245).

    Eine Kette aus :func:`_ordered_cavity` beginnt mit ihrer engsten Bohrung.
    Welche der folgenden Abschnitte auf welcher Seite liegen, sagt ihre Lage
    entlang der Bohrungsachse; :func:`_ordered_cavity` lässt nur Ketten zu, an
    denen diese Lage eindeutig ist. Eine Kette von einem Glied hat eine Seite:
    sich selbst.
    """
    return _sides_of(chain) or (tuple(chain),)


def _sides_of(chain: Sequence[Feature]) -> tuple[tuple[Feature, ...], ...] | None:
    """:func:`cavity_sides`, oder ``None``, wo die Lage die Seiten nicht trennt.

    Getrennt wird an der Stelle, an der die Abschnitte von einer Seite der
    Bohrungsmitte auf die andere wechseln. Ein Abschnitt, dessen Mitte
    innerhalb von :data:`~app.core.units.EPS_GEOM` auf der Bohrungsmitte liegt,
    gehört keiner Seite, und eine zweite Rückkehr hieße, die Seiten liegen
    durcheinander.
    """
    if len(chain) < 2:
        return (tuple(chain),)
    bore = chain[0]
    axis, centre = axis_of(bore), centre_of(bore)
    if axis is None or centre is None:
        return None
    signs = []
    for section in chain[1:]:
        where = centre_of(section)
        if where is None:
            return None
        along = units.dot3(where - centre, axis)
        if abs(along) <= EPS_GEOM:
            return None
        signs.append(along > 0.0)
    changes = [index for index in range(1, len(signs)) if signs[index] != signs[index - 1]]
    if not changes:
        return (tuple(chain),)
    if len(changes) > 1:
        return None
    split = changes[0] + 1
    return ((bore, *chain[1:split]), (bore, *chain[split:]))


_Comparison = Literal["same", "different", "unavailable"]
_POSE_PARAMETERS = frozenset({"axis", "centre", "normal", "position"})
_DIAGNOSTIC_PARAMETERS = frozenset(
    {
        "residual",
        "fit_error",
        "radial_min",
        "radial_max",
        "local_search_radius",
        "profile_clamp",
        "profile_clamp_y",
    }
)


@dataclass(frozen=True)
class _SurfacePatch:
    """Ein echter Flächenausschnitt: seine Dreiecke, seine Ecken und ihr Suchbaum.

    ``points`` sind die verschiedenen Ecken relativ zur Merkmalsmitte,
    ``triangles`` die Dreiecke in denselben Koordinaten und ``corners`` je
    Dreieck die drei Nummern in ``points``. Daraus entsteht bei Bedarf die
    Nachbarschaft Ecke → Dreiecke (:attr:`incidence`), mit der ein Punkt
    seine nächsten Dreiecke findet, ohne alle zu messen.
    """

    points: NDArray[np.float64]
    triangles: NDArray[np.float64]
    corners: NDArray[np.int64]

    @cached_property
    def points_tree(self) -> Any:
        """Den räumlichen Suchbaum für alle Vergleiche dieses Ausschnitts teilen."""
        return cKDTree(self.points)

    @cached_property
    def incidence(self) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
        """Je Ecke die Dreiecke, die sie tragen — als Zeilenanfänge und Mitglieder."""
        corner = self.corners.ravel()
        order = np.argsort(corner, kind="stable")
        members = (order // 3).astype(np.int64)
        counts = np.bincount(corner, minlength=len(self.points))
        starts = np.concatenate(([0], np.cumsum(counts))).astype(np.int64)
        return starts, members


#: Wie viele nächste Ecken der Gegenfläche ein Punkt befragt, bevor er den
#: Abstand zu deren Dreiecken misst. Der Fächer um eine Ecke hat selten mehr
#: als sechs Dreiecke; acht Ecken decken das enthaltende Dreieck auch dort,
#: wo die Vernetzung ungleichmäßig ist. Wer trotzdem außerhalb liegt, fragt
#: einmal mit dem Vierfachen nach, bevor er als verschieden gilt.
NEAREST_CORNERS: Final[int] = 8


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

    Die Reihenfolge entspricht ``actions``. Der Randgraph lebt nur für diesen
    Aufruf; die Flächenausschnitte und ihre Vergleiche hängen am Körper und
    an Dreiecken, Achsen und Mitten der Merkmale (:func:`_shape_key`) — ein
    anderer Mesh- oder Merkmalsstand kann so keine veraltete Antwort erben,
    und Merkmalfenster, Steckbrief und Ansicht lesen dieselbe.
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
    *,
    op: str = "",
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

    **Ein Maß, das leer „bleibt" heißt, reist nur, wenn es geändert wurde**
    (``op`` nennt die Operation, 23.09.2026). Die Tiefe von *Bohrung ändern*
    steht im Merkmalfenster mit dem gemessenen Wert des gewählten Lochs; wer
    nur den Durchmesser einer Gruppe ändert, meint nicht, dass alle Löcher
    dessen Tiefe bekommen. Unverändert steht sie für die übrigen Mitglieder
    deshalb leer — jedes behält seine eigene —, geändert gilt sie allen.
    """
    named = tuple(params.get(axis) for axis in _PLACE_AXES)
    anchor = _centre_of(features.get(picked))
    untouched = _unchanged_optional_measures(op, params, features.get(picked))
    result: dict[FeatureId, dict[str, Any]] = {}
    for member in members:
        if member == picked:
            result[member] = {**params, "at_feature": member}
            continue
        values = {key: value for key, value in params.items() if key not in _PLACE_AXES}
        values.update(dict.fromkeys(untouched))
        values["at_feature"] = member
        centre = _centre_of(features.get(member))
        if anchor is not None and centre is not None:
            for axis, value, own, base in zip(_PLACE_AXES, named, centre, anchor, strict=True):
                if value is not None:
                    values[axis] = own + (float(value) - base)
        result[member] = values
    return result


def _optional_measures(spec: Any) -> tuple[str, ...]:
    """Die Längenfelder, die leer „bleibt, wie es ist" heißen und ein gemessenes Maß lesen."""
    return tuple(
        entry.name
        for entry in spec.params.spec()
        if getattr(entry, "optional", False)
        and entry.unit == "mm"
        and (source := feature_value_source(entry.name)) is not None
        and source[1] is None
    )


def _unchanged_optional_measures(
    op: str, params: Mapping[str, Any], picked: Feature | None
) -> tuple[str, ...]:
    """Welche dieser Felder am gewählten Merkmal unverändert stehen.

    Verglichen auf eine halbe Anzeigestelle — das Feld zeigt das gemessene
    Maß gerundet, und wer es stehen lässt, ändert es nicht.
    """
    from app.core.registry import REGISTRY
    from app.core.units import EPS_DISPLAY

    if not op or picked is None or not REGISTRY.has(op):
        return ()
    unchanged = []
    for name in _optional_measures(REGISTRY.get(op)):
        value = params.get(name)
        source = feature_value_source(name, picked)
        measured = picked.params.get(source[0]) if source is not None else None
        if value is None or measured is None or not _is_number(measured):
            continue
        if abs(float(value) - float(measured)) <= EPS_DISPLAY / 2.0:
            unchanged.append(name)
    return tuple(unchanged)


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
    """Gemessene Maße, die diese Operation tatsächlich setzt.

    Längen — und am Langloch seine Richtung: *Zum Langloch ziehen* trägt sie
    als Winkel in sein Feld (``actions.feature_value_source``), und dieselbe
    Zahl geht an jedes Mitglied. Eine Gruppe, die sie nicht vergleicht, dreht
    beim Übernehmen jedes anders liegende Langloch still mit.
    """
    dimensions = set()
    for entry in spec.params.spec():
        source = feature_value_source(entry.name, feature)
        # Ein Feld, das leer „bleibt" heißt, ist kein Ausgangsmaß der Gruppe:
        # Unverändert behält jedes Mitglied das eigene (:func:`params_for_members`).
        if source is None or getattr(entry, "optional", False):
            continue
        key, index = source
        if index is not None or key not in feature.params:
            continue
        value = feature.params[key]
        if (entry.unit == "mm" and _is_number(value)) or (
            entry.unit == units.DEGREE_UNIT and _is_direction(value)
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
    # Der Vergleich zweier Ausschnitte wird je Körper gemerkt: Das Merkmal-
    # fenster fragt ihn bei jedem Klick für jede Handlung, der Steckbrief
    # noch einmal — an der Lochplatte mit 360 000 Dreiecken 0,47 s je Klick
    # für vier Bohrungen (gemessen am 22.09.2026). **Und ungeordnet:** Der
    # Vergleich prüft beide Richtungen, Bohrung 2 gegen 1 ist dieselbe Frage
    # wie 1 gegen 2 — an der dichten Platte kostete jede 10 ms (RM-232).
    same: bool = remembered(
        "same_surface_patch",
        _one_body(context.mesh).raw,
        (),
        lambda: _same_surface_patch(reference_patch, candidate_patch),
        extra=frozenset((_shape_key(reference), _shape_key(candidate))),
    )
    if not same:
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
    """Die Dreiecke eines Umfangs, relativ zu seinem ersten Mittelpunkt.

    Flächenindex, Reihenfolge und Unterteilung tragen keine Bedeutung; die
    Fläche selbst schon. Bis zum 20.09.2026 hielt der Ausschnitt auch die
    drei Kantenlängen jedes Dreiecks, und der Vergleich verlangte dieselbe
    Vernetzung — eine unveränderte ebene Fläche, an einer Kopie nur feiner
    unterteilt, galt als „verschieden" (P1.5, Durchsicht der Verbraucher).
    """
    body = _one_body(mesh).raw
    patch: _SurfacePatch | None = remembered(
        "surface_patch",
        body,
        (),
        lambda: _read_surface_patch(scope, body),
        extra=_shape_key(scope),
    )
    return patch


def _read_surface_patch(scope: tuple[Feature, ...], body: trimesh.Trimesh) -> _SurfacePatch | None:
    """Der Rumpf von :func:`_build_surface_patch` — Ausschnitt samt Suchbaum bleiben gemerkt."""
    centre = centre_of(scope[0])
    indices = np.unique(
        np.fromiter(
            (index for feature in scope for index in feature.face_indices),
            dtype=np.int64,
        )
    )
    if (
        centre is None
        or not len(indices)
        or int(indices.min()) < 0
        or int(indices.max()) >= len(body.faces)
    ):
        return None
    # Die Ecken über ihre Nummern im Netz zusammengelegt, nicht über ihre
    # Koordinaten: ``np.unique`` über Zeilen sortiert Strukturen und kostete
    # an 36 000 Ecken 150 ms je Bohrung — ein Klick auf eine von vier
    # Bohrungen zahlte das vierfach im Hauptthread (gemessen am 22.09.2026).
    # Das Netz ist hier bereits ``_one_body``, also verschweißt; zwei Nummern
    # an derselben Stelle wären zwei Ecken im Suchbaum, und das ist erlaubt.
    corners = np.asarray(body.faces, dtype=np.int64)[indices]
    used, inverse = np.unique(corners.ravel(), return_inverse=True)
    points = np.asarray(body.vertices, dtype=np.float64)[used] - centre
    if not np.isfinite(points).all():
        return None
    inverse = np.asarray(inverse, dtype=np.int64).reshape(-1, 3)
    return _SurfacePatch(
        points=cast(NDArray[np.float64], points),
        triangles=cast(NDArray[np.float64], points[inverse]),
        corners=inverse,
    )


def _same_surface_patch(reference: _SurfacePatch, candidate: _SurfacePatch) -> bool:
    """Zwei Ausschnitte sind dieselbe Fläche, wenn jeder auf dem anderen liegt.

    Gemessen wird der Abstand jeder Ecke des einen zur **Fläche** des anderen,
    in beide Richtungen — nicht zu dessen Ecken und nicht über Kantenlängen.
    Eine feinere Unterteilung setzt ihre neuen Ecken auf die alten Dreiecke
    und bleibt damit dieselbe Fläche; eine Kalotte liegt auf ihrer Kugel, aber
    die Kugel nicht auf der Kalotte, und die Gegenrichtung sagt „verschieden".
    Die Toleranz ist :data:`units.MAX_FACET_SAG`: Zwei Tessellierungen
    derselben Rundung liegen höchstens um die Sehnenhöhe auseinander, und
    kleiner als die Anzeigeauflösung wäre für eine Fläche aus Dreiecken keine
    Auskunft, sondern Zufall. Die Maße selbst vergleicht davor
    :func:`_dimension_comparison` mit :data:`EPS_DISPLAY`.

    **Erst die Ecken, dann die Dreiecke.** Eine Ecke, die näher als die
    Sehnenhöhe an einer Ecke der Gegenfläche liegt, liegt erst recht so nah an
    deren Fläche — für sie ist die Frage beantwortet, ohne ein Dreieck zu
    messen. Vier Bohrungen desselben Musters tragen dieselbe Vernetzung, dort
    trifft das jede Ecke, und der Vergleich kostet eine Baumabfrage statt
    300 000 Punkt-Dreieck-Paare: An der unterteilten Lochplatte 1,6 s je
    Klick auf eine Bohrung, im Qt-Hauptthread (gemessen am 22.09.2026). Nur
    was weiter weg liegt — eine andere Unterteilung derselben Fläche — geht
    den Weg über die Dreiecke.

    **Und davor die Hüllquader.** Liegt jede Ecke des einen Ausschnitts
    höchstens um die Sehnenhöhe neben den Dreiecken des anderen, liegt sie
    auch höchstens so weit neben deren Hüllquader — also stimmen beide
    Hüllquader in jeder Richtung bis auf die Sehnenhöhe überein. Das ist eine
    notwendige Bedingung und kein Urteil: Wer sie verfehlt, ist verschieden,
    ohne dass ein Dreieck gemessen wird. An den 20 Wülsten von
    ``build_tray_v3.step`` kostete ein Klick 180 ms, fast alles in
    Vergleichen, die am Ende „verschieden" sagten (RM-181, 22.09.2026).
    """
    reach = units.MAX_FACET_SAG + EPS_GEOM
    if bool(
        np.any(np.abs(reference.points.min(axis=0) - candidate.points.min(axis=0)) > reach)
        or np.any(np.abs(reference.points.max(axis=0) - candidate.points.max(axis=0)) > reach)
    ):
        return False
    for own, other in ((reference, candidate), (candidate, reference)):
        to_corners = np.asarray(other.points_tree.query(own.points, k=1)[0], dtype=np.float64)
        unsettled = np.flatnonzero(to_corners > units.MAX_FACET_SAG)
        if not len(unsettled):
            continue
        remaining = own.points[unsettled]
        distances = _distance_to_surface(remaining, other, NEAREST_CORNERS)
        outside = distances > units.MAX_FACET_SAG
        if outside.any():
            distances[outside] = _distance_to_surface(
                remaining[outside], other, NEAREST_CORNERS * 4
            )
            if bool((distances > units.MAX_FACET_SAG).any()):
                return False
    return True


def _distance_to_surface(
    points: NDArray[np.float64], patch: _SurfacePatch, neighbours: int
) -> NDArray[np.float64]:
    """Der Abstand jedes Punkts zu den Dreiecken um seine nächsten Ecken.

    Die Kandidaten kommen aus dem Eckensuchbaum und der Nachbarschaft
    Ecke → Dreiecke; gemessen wird dann einmal vektorisiert über alle
    Paare (``trimesh.triangles.closest_point``) und je Punkt das Minimum
    genommen. Ein Punkt, dessen nächstes Dreieck an keiner der befragten Ecken
    hängt, bekommt einen zu großen Abstand — der Aufrufer fragt dann mit mehr
    Ecken nach.
    """
    if not len(points):
        return np.zeros(0, dtype=np.float64)
    count = min(neighbours, len(patch.points))
    nearest = np.asarray(patch.points_tree.query(points, k=count)[1], dtype=np.int64)
    nearest = nearest.reshape(len(points), count)
    starts, members = patch.incidence
    corners = nearest.ravel()
    begin, end = starts[corners], starts[corners + 1]
    lengths = end - begin
    total = int(lengths.sum())
    if total == 0:
        return np.full(len(points), np.inf, dtype=np.float64)
    point_ids = np.repeat(np.repeat(np.arange(len(points)), count), lengths)
    slots = np.arange(total) - np.repeat(np.cumsum(lengths) - lengths, lengths)
    triangle_ids = members[np.repeat(begin, lengths) + slots]
    pairs = np.unique(point_ids * len(patch.triangles) + triangle_ids)
    point_ids, triangle_ids = pairs // len(patch.triangles), pairs % len(patch.triangles)
    closest = trimesh.triangles.closest_point(  # type: ignore[no-untyped-call]
        patch.triangles[triangle_ids], points[point_ids]
    )
    measured = np.linalg.norm(closest - points[point_ids], axis=1)
    best = np.full(len(points), np.inf, dtype=np.float64)
    np.minimum.at(best, point_ids, measured)
    return best


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
    aligned = abs(float(axis @ other_axis)) >= units.exact_cos_degrees(SINK_AXIS_LIMIT)
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
    if _is_direction(first) and _is_direction(second):
        # Eine Richtung ohne Vorzeichen — ein Langloch entlang d ist dasselbe
        # wie entlang -d —, verglichen mit derselben Winkelauflösung wie der
        # Öffnungswinkel eines Kegels.
        along = np.asarray(first, dtype=float)
        other = np.asarray(second, dtype=float)
        lengths = float(np.linalg.norm(along)) * float(np.linalg.norm(other))
        if not math.isfinite(lengths) or lengths <= EPS_GEOM:
            return None
        return abs(float(along @ other)) / lengths >= units.exact_cos_degrees(EPS_ANGLE)
    return None


def _is_number(value: Any) -> bool:
    """Ein skalarer Zahlenwert, aber kein Wahrheitswert."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_direction(value: Any) -> bool:
    """Drei Zahlen — eine Richtung im Raum, wie sie ein Langloch trägt."""
    return (
        isinstance(value, (tuple, list))
        and len(value) == 3
        and all(_is_number(component) for component in value)
    )
