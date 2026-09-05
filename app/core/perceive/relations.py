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
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.log import get_logger
from app.core.perceive.features import SINK_AXIS_LIMIT, SINK_FIT_LIMIT
from app.core.types import Feature, FeatureId
from app.core.units import EPS_GEOM

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
    feature: Feature, features: Mapping[FeatureId, Feature]
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
    feature: Feature, features: Mapping[FeatureId, Feature]
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
