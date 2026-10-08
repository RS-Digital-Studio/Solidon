"""Das Gegenstück, das in eine Bohrung passt: Schaft, Senk- oder Zylinderkopf, Gewinde (RM-536).

*Stift für Bohrung* baute bis RM-536 einen glatten Zylinder, so lang wie die
Bohrung. Trug die Bohrung eine Senkung, eine Ansenkung oder ein Innengewinde,
blieb das unbeachtet; der Kunde wollte „dafür auch das passende Gegenstück“
(Fragebogen S-20261006-5be329). Hier steht, wie es entsteht:

* **Der Hohlraum** (:func:`cavity_of`): die Kette an der Mündung aus
  ``perceive.relations.cavity_chain_state_at`` — Bohrung, Senkung, Ansenkung,
  in der Reihenfolge nach außen —, als Abschnitte entlang der Achse. Ein
  Innengewinde ersetzt die Bohrung, die es geschnitten hat
  (``insert_printed_thread`` nimmt das Merkmal ``hole`` heraus, gemessen): Am
  Gewinde gewählt, schließen sich die gleichachsigen Senkungen und Ansenkungen
  an seiner Mündung an.
* **Der Umriss** (:func:`outline`): jeder Abschnitt um das halbe Spiel nach
  innen versetzt, senkrecht zu seiner Wand — der Schaft um ``Spiel/2``, die
  Flanke des Senkkopfs ebenso, die Ringschulter einer Ansenkung axial. Wo zwei
  versetzte Wände sich treffen, liegt die Ecke des Stifts auf beiden; an einer
  offenen Mündung endet er bündig, vor Material (Sacklochboden, verdeckte
  Mündung) mit demselben Abstand.
* **Das Gewinde** kommt aus dem Gewindebaustein (``fasteners.printed_thread``)
  in der Größe, die das Gegenstück eines vorhandenen Gewindes bekommt
  (``counterpart.thread_values_for``), mit dem Spiel des Profils. Seine Gänge
  werden in die Gänge der Bohrung gedreht (:func:`thread_turn`): Der Stift
  steht in der Bohrung, und ohne die gemessene Lage stünde sein Gang im Gang
  des Trägers.

Gerechnet wird in einem Rahmen, dessen Z-Achse die Achse ist und nach außen
zeigt, zur Mündung mit dem Kopf; ``s`` ist die Lage entlang dieser Achse vom
Ursprung des Hohlraums aus.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from app.core.errors import CANCEL, CHANGE_SELECTION, CORRECT_INPUT, ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.geom.mesh import MeshData, as_mesh_data, ray_hit_distances
from app.core.types import Feature, FeatureId, Finding, is_a_cavity
from app.core.units import EPS_GEOM, MAX_FACET_SAG
from app.i18n import _

#: Die zwei Formen des Stifts: passend zur Bohrung (mit Kopf und Gewinde, wo
#: die Bohrung sie trägt) oder der glatte Zylinder von vor RM-536.
TO_THE_BORE: Final = "to_the_bore"
PLAIN_PIN: Final = "plain_pin"
PIN_SHAPES: Final = (TO_THE_BORE, PLAIN_PIN)

#: Wie weit zwei Abschnitte einer Kette entlang der Achse auseinander liegen
#: dürfen, um als aneinandergrenzend zu gelten. Die Kette selbst ist über
#: gemeinsame Randringe belegt; ihre Kennzahlen kommen aus Einpassungen, und
#: ein Netz trifft die Ebene einer Stufe auf seine Facettengrenze.
SECTION_REACH: Final = 2.0 * MAX_FACET_SAG

#: Wie viele Lagen je Steigung die Drehung des Gewindes in die Gänge der
#: Bohrung absucht — ein Halbgrad, an M6 1,4 µm entlang der Achse.
TURN_STEPS: Final = 720

#: Ab so vielen Ecken je Seite wird für die Lage der Gänge ausgedünnt — jede
#: k-te, in fester Folge.
TURN_SAMPLES: Final = 20000

TWO_HEADS: Final = _(
    "Die Bohrung weitet sich an beiden Enden. Ein Stift mit Kopf käme nur von einer Seite "
    "hinein. Wählen Sie unter „Weitere Einstellungen“ die Form „Glatter Stift“."
)
CHAIN_UNREADABLE: Final = _(
    "Welche Senkung oder Ansenkung zu dieser Bohrung gehört, lässt sich hier nicht "
    "eindeutig lesen. Wählen Sie unter „Weitere Einstellungen“ die Form „Glatter Stift“."
)
NARROWING_MOUTH: Final = _(
    "Die Mündung dieser Bohrung ist enger als die Bohrung selbst. Ein passender Stift käme "
    "nicht hinein. Wählen Sie unter „Weitere Einstellungen“ die Form „Glatter Stift“."
)
NARROW_ABOVE_THREAD: Final = _(
    "Zwischen Gewinde und Mündung ist die Bohrung enger als das Gewinde. Ein Gewindestift "
    "käme nicht hinein. Wählen Sie unter „Weitere Einstellungen“ die Form „Glatter Stift“."
)
NOT_AN_INNER_THREAD: Final = _(
    "Ein Stift gehört in ein Innengewinde, dieses ist ein Außengewinde. Wählen Sie eine "
    "Bohrung oder ein Innengewinde."
)
PLAIN_NEEDS_A_BORE: Final = _(
    "Ein glatter Stift gehört in eine Bohrung, nicht in ein Gewinde. Wählen Sie die Form "
    "„Passend zur Bohrung“."
)
TOO_LONG_FOR_THE_BORE: Final = _(
    "So lang reicht der Stift durch den Boden der Bohrung. Tragen Sie höchstens die "
    "Tiefe ein, die darunter steht, oder null für die ganze Bohrung."
)
CLEARANCE_TOO_LARGE: Final = _(
    "Mit diesem Spiel bleibt vom Stift an einer Stelle nichts stehen. Verringern Sie das Spiel."
)


@dataclass(frozen=True, slots=True)
class Section:
    """Ein Abschnitt des Hohlraums entlang der Achse: Zylinder oder sich weitender Kegel.

    ``inner`` ist der Halbmesser am inneren Ende (``start``), ``outer`` am
    äußeren (``end``). ``shoulder`` sagt, dass er mit einer Ringstufe auf den
    Abschnitt davor folgt; ``virtual`` steht am Gewindebereich, dessen Umriss
    nicht versetzt wird, sondern innerhalb des Gewindekerns bleibt.
    ``misfit`` ist, wie weit seine Wand der Achse näher kommen kann, weil sein
    Merkmal nur fast gleichachsig sitzt (:func:`_misfit`).
    """

    start: float
    end: float
    inner: float
    outer: float
    feature: FeatureId = ""
    shoulder: bool = False
    virtual: bool = False
    misfit: float = 0.0

    @property
    def cone(self) -> bool:
        return self.outer > self.inner + EPS_GEOM

    @property
    def half_angle(self) -> float:
        """Der halbe Öffnungswinkel in Bogenmaß; null am Zylinder."""
        length = self.end - self.start
        if not self.cone or length <= EPS_GEOM:
            return 0.0
        return math.atan2(self.outer - self.inner, length)


@dataclass(frozen=True, slots=True)
class ThreadZone:
    """Wo das Innengewinde entlang der Achse liegt, und welches Gegenstück es bekommt."""

    start: float
    end: float
    nominal: float
    pitch: float
    values: Mapping[str, Any]
    feature: FeatureId
    #: Was das Gegenstück über die Wahl seines Maßes sagt
    #: (``counterpart.thread_size_note``) — der Stift sagt dasselbe (Review P2, G4).
    note: Finding | None = None


@dataclass(frozen=True, slots=True)
class Cavity:
    """Der Hohlraum, in den der Stift soll, in seinem eigenen Rahmen.

    ``axis`` zeigt nach außen, zur Mündung mit dem Kopf; ``sections`` reichen
    von innen nach außen, ohne Lücke — ohne Gewinde zuerst die Bohrung, mit
    Gewinde nur, was über ihm liegt.
    """

    origin: NDArray[np.float64]
    axis: NDArray[np.float64]
    sections: tuple[Section, ...]
    thread: ThreadZone | None = None

    @property
    def low(self) -> float:
        """Das innere Ende des Hohlraums."""
        if self.thread is not None:
            return self.thread.start
        return self.sections[0].start

    @property
    def high(self) -> float:
        """Die Mündung."""
        if self.sections:
            return self.sections[-1].end
        assert self.thread is not None
        return self.thread.end

    @property
    def widenings(self) -> tuple[Section, ...]:
        """Was sich über dem Schaft oder dem Gewinde weitet: Senkung und Ansenkung."""
        return self.sections if self.thread is not None else self.sections[1:]


#: Die Auswege jeder Absage über die Kette: anders wählen, die Form ändern, lassen.
_WAYS: Final = (CORRECT_INPUT, CHANGE_SELECTION, CANCEL)


def _unreadable(value: str, **values: Any) -> ValidationError:
    """Die Kette lässt sich nicht eindeutig lesen."""
    return ValidationError(
        field="at_feature",
        detail=CHAIN_UNREADABLE,
        value=value,
        constraint="chain_unreadable",
        values=values or None,
        suggestions=_WAYS,
    )


def _narrowing(value: str, **values: Any) -> ValidationError:
    """Die Mündung ist enger als die Bohrung."""
    return ValidationError(
        field="at_feature",
        detail=NARROWING_MOUTH,
        value=value,
        constraint="narrowing_mouth",
        values=values or None,
        suggestions=_WAYS,
    )


def _two_heads(value: str, **values: Any) -> ValidationError:
    """Die Bohrung weitet sich an beiden Enden."""
    return ValidationError(
        field="at_feature",
        detail=TWO_HEADS,
        value=value,
        constraint="two_heads",
        values=values or None,
        suggestions=_WAYS,
    )


def _narrow_above(value: str, **values: Any) -> ValidationError:
    """Über dem Gewinde ist die Bohrung enger."""
    return ValidationError(
        field="at_feature",
        detail=NARROW_ABOVE_THREAD,
        value=value,
        constraint="narrow_above_thread",
        values=values or None,
        suggestions=_WAYS,
    )


def _unit(vector: Any) -> NDArray[np.float64]:
    values = np.asarray(vector, dtype=np.float64).reshape(3)
    length = math.sqrt(float(values[0] ** 2 + values[1] ** 2 + values[2] ** 2))
    return values / length


def _along(point: Any, origin: NDArray[np.float64], axis: NDArray[np.float64]) -> float:
    """Die Lage eines Punkts entlang der Achse — elementweise, auf jeder Maschine gleich."""
    offset = np.asarray(point, dtype=np.float64).reshape(3) - origin
    return float(offset[0] * axis[0] + offset[1] * axis[1] + offset[2] * axis[2])


def _beside(point: Any, origin: NDArray[np.float64], axis: NDArray[np.float64]) -> float:
    """Wie weit ein Punkt neben der Achse liegt."""
    offset = np.asarray(point, dtype=np.float64).reshape(3) - origin
    along = float(offset[0] * axis[0] + offset[1] * axis[1] + offset[2] * axis[2])
    lateral = offset - along * axis
    return math.sqrt(float(lateral[0] ** 2 + lateral[1] ** 2 + lateral[2] ** 2))


def _coaxial(
    feature: Feature, origin: NDArray[np.float64], axis: NDArray[np.float64], radius: float
) -> bool:
    """Ob ein Merkmal auf derselben Achse sitzt wie die Bohrung mit dem Halbmesser ``radius``.

    **Dieselben Schwellen wie die Kettenerkennung** (Review P2 Bausteine, G3):
    Richtung innerhalb von ``SINK_AXIS_LIMIT``, Mitte höchstens
    ``radius · SINK_FIT_LIMIT`` quer zur Achse (``perceive.relations``). Eine
    Kette, die die Erkennung als Senkbohrung liest, liest der Stift ebenso;
    eigene, engere Schwellen sagten an einem Fremdnetz „lässt sich nicht
    eindeutig lesen“ zu einer Kette, die der Bericht eben noch nannte.
    """
    from app.core.perceive.features import SINK_AXIS_LIMIT, SINK_FIT_LIMIT
    from app.core.units import exact_cos_degrees

    centre = feature.params.get("centre")
    direction = feature.params.get("axis")
    if centre is None or direction is None:
        return False
    other = _unit(direction)
    cosine = abs(float(axis[0] * other[0] + axis[1] * other[1] + axis[2] * other[2]))
    return (
        cosine >= exact_cos_degrees(SINK_AXIS_LIMIT)
        and _beside(centre, origin, axis) <= radius * SINK_FIT_LIMIT
    )


def _misfit(
    feature: Feature, section: Section, origin: NDArray[np.float64], axis: NDArray[np.float64]
) -> float:
    """Wie weit die Wand dieses Glieds der Achse näher kommen kann, als sein Abschnitt sagt.

    Die Kette nimmt ein Glied bis ``SINK_AXIS_LIMIT`` und ``r · SINK_FIT_LIMIT``
    als gleichachsig (:func:`_coaxial`), gedreht wird der Stift aber um die
    Achse der Bohrung. Eine Senkung 0,15 mm daneben kam dem Kopf auf einer
    Seite um so viel näher, und von 0,125 mm halbem Spiel blieben 0,05 mm
    (Review P2 N7). Gerechnet werden der Versatz der Mitte und die Neigung
    über die Länge des Glieds: Eine Bohrung kippt um ihre Mitte, ein Kegel um
    seine Mündung. :func:`_offset` nimmt den Abschnitt um so viel enger.
    """
    centre = feature.params.get("centre")
    direction = feature.params.get("axis")
    if centre is None:
        return 0.0
    beside = _beside(centre, origin, axis)
    tilt = 0.0
    if direction is not None:
        other = _unit(direction)
        cosine = min(1.0, abs(float(axis[0] * other[0] + axis[1] * other[1] + axis[2] * other[2])))
        length = section.end - section.start
        lever = length / 2.0 if feature.kind == "hole" else length
        tilt = lever * math.sqrt(max(0.0, 1.0 - cosine * cosine))
    misfit = beside + tilt
    return misfit if misfit > EPS_GEOM else 0.0


def _hole_section(
    feature: Feature, origin: NDArray[np.float64], axis: NDArray[np.float64]
) -> Section:
    middle = _along(feature.params["centre"], origin, axis)
    half = float(feature.params.get("depth", 0.0)) / 2.0
    radius = float(feature.params["diameter"]) / 2.0
    return Section(middle - half, middle + half, radius, radius, feature.id)


def _cone_section(
    feature: Feature, inner: float, origin: NDArray[np.float64], axis: NDArray[np.float64]
) -> Section | None:
    """Eine Senkung, die sich vom Halbmesser ``inner`` bis zu ihrer Mündung weitet.

    Der Kegel nennt seine Mündung (``centre`` auf der Deckfläche, ``diameter``)
    und den vollen Öffnungswinkel; das innere Ende folgt aus dem Halbmesser,
    auf dem er sitzt. ``None``, wo er sich nicht nach außen weitet.
    """
    angle = float(feature.params.get("angle", 0.0))
    if feature.params.get("narrowing") or not EPS_GEOM < angle < 180.0 - EPS_GEOM:
        return None
    mouth = _along(feature.params["centre"], origin, axis)
    outer = float(feature.params["diameter"]) / 2.0
    if outer <= inner + EPS_GEOM:
        return None
    length = (outer - inner) / math.tan(math.radians(angle / 2.0))
    return Section(mouth - length, mouth, inner, outer, feature.id)


def _chained(
    chain: Sequence[Feature],
    origin: NDArray[np.float64],
    axis: NDArray[np.float64],
    value: str,
    radius: float,
) -> list[Section]:
    """Die Abschnitte einer Kettenseite, von der Bohrung aus nach außen, ohne Lücke.

    Die Kette ist über gemeinsame Randringe belegt; ihre Kennzahlen kommen aus
    Einpassungen und treffen die Ebene einer Stufe nur auf die Facettengrenze.
    Jeder Abschnitt beginnt deshalb genau am Ende des vorigen, ein Kegel mit
    seinem eigenen Winkel von seiner Mündung aus.
    """
    sections: list[Section] = []
    for member in chain:
        if not _coaxial(member, origin, axis, radius):
            raise _unreadable(value)
        if member.kind == "hole":
            section = _hole_section(member, origin, axis)
        elif member.kind == "cone" and sections:
            found = _cone_section(member, sections[-1].outer, origin, axis)
            if found is None:
                raise _narrowing(value)
            section = found
        else:
            raise _unreadable(value)
        section = replace(section, misfit=_misfit(member, section, origin, axis))
        if sections:
            section = _following(sections[-1], section, value)
        sections.append(section)
    return sections


def _following(previous: Section, section: Section, value: str) -> Section:
    """``section``, an das Ende von ``previous`` gesetzt — mit Stufe, wo es weiter wird."""
    if abs(section.start - previous.end) > SECTION_REACH or section.end <= previous.end:
        raise _unreadable(value)
    inner = section.outer - (section.end - previous.end) * math.tan(section.half_angle)
    if inner < previous.outer - SECTION_REACH:
        raise _narrowing(value)
    shoulder = inner > previous.outer + SECTION_REACH
    return Section(
        previous.end,
        section.end,
        inner,
        section.outer,
        section.feature,
        shoulder,
        misfit=section.misfit,
    )


def cavity_of(
    feature: Feature,
    features: Mapping[FeatureId, Feature],
    body: Any,
) -> Cavity:
    """Der Hohlraum an einer gewählten Bohrung oder einem gewählten Innengewinde."""
    from app.core.perceive.relations import cavity_chain_state_at, cavity_sides

    mesh = as_mesh_data(body)
    if feature.kind == "thread":
        return _at_a_thread(feature, features, mesh)
    state = cavity_chain_state_at(feature, features, mesh)
    if state.chain is None and state.touches_other:
        raise _unreadable(feature.id, reason=state.reason)
    chain = state.chain or (feature,)
    sides = [side for side in cavity_sides(chain) if len(side) > 1]
    if len(sides) > 1:
        raise _two_heads(feature.id)
    side = sides[0] if sides else (chain[0],)
    bore = side[0]
    origin = np.asarray(bore.params["centre"], dtype=np.float64).reshape(3)
    axis = _unit(bore.params.get("axis", (0.0, 0.0, 1.0)))
    if len(side) > 1 and _along(side[-1].params["centre"], origin, axis) < 0.0:
        axis = -axis
    radius = float(bore.params["diameter"]) / 2.0
    sections = _chained(side, origin, axis, feature.id, radius)
    for candidate in features.values():
        if (
            candidate.kind == "thread"
            and candidate.params.get("internal")
            and _coaxial(candidate, origin, axis, radius)
        ):
            zone = _thread_zone(candidate, origin, axis)
            bore_part = sections[0]
            if zone.end > bore_part.start + EPS_GEOM and zone.start < bore_part.end - EPS_GEOM:
                return _threaded_bore(origin, axis, sections, zone, feature.id)
    return Cavity(origin, axis, tuple(sections), None)


def _thread_zone(
    feature: Feature, origin: NDArray[np.float64], axis: NDArray[np.float64]
) -> ThreadZone:
    """Wo ein Innengewinde entlang der Achse liegt, mit dem Maß seines Gegenstücks."""
    from app.core.counterpart import thread_size_note, thread_values_for
    from app.core.knowledge.parts.fasteners import thread_measure

    refuse_thread(feature)
    values = thread_values_for(feature)
    nominal, pitch = thread_measure(
        str(values["size"]), float(values.get("diameter", 0.0)), float(values.get("pitch", 0.0))
    )
    middle = _along(feature.params["centre"], origin, axis)
    half = float(feature.params.get("length", 0.0)) / 2.0
    if half <= EPS_GEOM:
        raise ValidationError(
            field="at_feature",
            detail=_("Das Gewinde nennt keine Länge. Tragen Sie die Länge des Stifts ein."),
            value=feature.id,
            constraint="positive",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return ThreadZone(
        middle - half,
        middle + half,
        nominal,
        pitch,
        dict(values),
        feature.id,
        thread_size_note(feature),
    )


def refuse_thread(feature: Feature) -> None:
    """Dieselben Absagen wie das Gegenstück zum Gewinde — links-, mehrgängig, kegelig —,
    dazu das Außengewinde, das keinen Stift aufnimmt."""
    from app.core.counterpart import refuse_unmatched_thread

    if not feature.params.get("internal"):
        raise ValidationError(
            field="at_feature",
            detail=NOT_AN_INNER_THREAD,
            value=feature.id,
            constraint="not_a_bore",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    refuse_unmatched_thread(feature)


def root_radius(zone: ThreadZone, clearance: float) -> float:
    """Der Halbmesser, bis zu dem der Umriss im Gewindebereich reicht: im Kern des Bolzens.

    Der Bolzen hat seinen Kern zwei Gangtiefen unter dem Nennmaß minus Spiel
    (``shapes.RIDGE_SHARE``, wie der Gewindebaustein); der Umriss bleibt um die
    Zugabe der Booleschen Kette darin, damit sich keine zwei Mäntel decken.
    """
    from app.core.knowledge.parts import shapes

    core = zone.nominal - 2.0 * zone.pitch * shapes.RIDGE_SHARE - clearance
    return core / 2.0 - BOOLEAN_OVERLAP


def _threaded_bore(
    origin: NDArray[np.float64],
    axis: NDArray[np.float64],
    sections: list[Section],
    zone: ThreadZone,
    value: str,
) -> Cavity:
    """Eine Bohrung mit Innengewinde auf ihrer Achse: Das Gewinde ersetzt den Schaft.

    Was unter dem Gewinde liegt, gehört nicht zum Stift — er endet mit dem
    Gewinde, wie eine Schraube. Darüber darf nur liegen, was mindestens so weit
    ist wie das Gewinde; durch eine engere Bohrung käme es nicht.
    """
    above: list[Section] = []
    for section in sections:
        if section.end <= zone.end + EPS_GEOM:
            continue
        start = max(section.start, zone.end)
        inner = section.outer - (section.end - start) * math.tan(section.half_angle)
        if not above and not section.cone and inner < zone.nominal / 2.0 - SECTION_REACH:
            raise _narrow_above(value)
        above.append(replace(section, start=start, inner=inner))
    return Cavity(origin, axis, tuple(above), zone)


def _at_a_thread(feature: Feature, features: Mapping[FeatureId, Feature], mesh: MeshData) -> Cavity:
    """Der Hohlraum an einem gewählten Innengewinde: das Gewinde und, was sich an ihm weitet.

    Ein Gewinde, das ``insert_printed_thread`` in eine Bohrung schnitt, steht
    an ihrer Stelle; die Kette aus ``cavity_chain_state_at`` beginnt an einer
    Bohrung und findet hier keine (an ``plate_countersunk.stl`` mit M6 gemessen:
    ``cone_1`` ohne Kette). Gesucht werden deshalb die gleichachsigen
    Senkungen und Ansenkungen, die an einem Ende des Gewindes ansetzen, und
    von dort weiter nach außen. Weitet sich keines, liegt die Mündung am
    offenen Ende; ist es keines, gilt die Richtung des Gewindes.
    """
    origin = np.asarray(feature.params["centre"], dtype=np.float64).reshape(3)
    axis = _unit(feature.params.get("axis", (0.0, 0.0, 1.0)))
    zone = _thread_zone(feature, origin, axis)
    others = [
        candidate
        for candidate in features.values()
        if candidate.id != feature.id
        and candidate.kind in {"hole", "cone"}
        and is_a_cavity(candidate)
        and _coaxial(candidate, origin, axis, float(feature.params["diameter"]) / 2.0)
    ]
    up = _walk(others, zone, origin, axis)
    down = _walk(others, zone, origin, -axis)
    if up and down:
        raise _two_heads(feature.id)
    if down or (not up and _closed_beyond(mesh, origin, axis, zone.end)):
        axis, sections = -axis, down
    else:
        sections = up
    return Cavity(origin, axis, tuple(sections), zone)


def _walk(
    others: Sequence[Feature],
    zone: ThreadZone,
    origin: NDArray[np.float64],
    axis: NDArray[np.float64],
) -> list[Section]:
    """Was sich am Ende ``+axis`` des Gewindes weitet, von dort nach außen.

    Das Gewinde sitzt mittig auf dem Ursprung, sein Ende liegt also in beiden
    Richtungen bei der halben Länge. Ein Abschnitt schließt an, wenn er dort
    beginnt (auf die halbe Steigung — so weit läuft der Gang aus) und nicht
    enger ist als das Gewinde.
    """
    sections: list[Section] = []
    reach = (zone.end - zone.start) / 2.0
    inner = zone.nominal / 2.0
    used: set[str] = set()
    while True:
        found: Section | None = None
        for candidate in others:
            if candidate.id in used:
                continue
            if candidate.kind == "hole":
                section = _hole_section(candidate, origin, axis)
            else:
                mouth = _along(candidate.params["centre"], origin, axis)
                angle = float(candidate.params.get("angle", 0.0))
                if candidate.params.get("narrowing") or not EPS_GEOM < angle < 180.0 - EPS_GEOM:
                    continue
                if mouth <= reach + EPS_GEOM:
                    continue
                outer = float(candidate.params["diameter"]) / 2.0
                start = outer - (mouth - reach) * math.tan(math.radians(angle / 2.0))
                section = Section(reach, mouth, start, outer, candidate.id)
            if abs(section.start - reach) > max(SECTION_REACH, zone.pitch / 2.0):
                continue
            if section.end <= reach + EPS_GEOM or section.inner < inner - zone.pitch:
                continue
            shoulder = section.inner > inner + SECTION_REACH
            found = Section(
                reach,
                section.end,
                section.inner,
                section.outer,
                section.feature,
                shoulder,
                misfit=_misfit(candidate, section, origin, axis),
            )
            break
        if found is None:
            return sections
        used.add(found.feature)
        sections.append(found)
        reach, inner = found.end, found.outer


def _closed_beyond(
    mesh: MeshData, origin: NDArray[np.float64], axis: NDArray[np.float64], end: float
) -> bool:
    """Ob hinter diesem Ende des Hohlraums gleich Material liegt."""
    return material_gap(mesh, origin, axis, end, 1.0, MAX_FACET_SAG) <= MAX_FACET_SAG


def material_gap(
    mesh: MeshData,
    origin: NDArray[np.float64],
    axis: NDArray[np.float64],
    end: float,
    way: float,
    inside: float,
) -> float:
    """Wie weit hinter einem Ende des Hohlraums auf der Achse das Material beginnt.

    Gefragt wird von einem Punkt ``inside`` vor dem Ende aus, entlang der
    Achse nach außen (``way`` = +1) oder innen (-1). Ohne Treffer ist es offen
    (unendlich): eine Mündung oder ein Durchgang.
    """
    direction = axis * way
    start = origin + axis * (end - way * inside)
    hits = ray_hit_distances(np.asarray(mesh.raw.triangles, dtype=np.float64), start, direction)
    if hits.size == 0:
        return math.inf
    return float(np.min(hits)) - inside


def room_beyond(
    mesh: MeshData,
    origin: NDArray[np.float64],
    axis: NDArray[np.float64],
    end: float,
    way: float,
    beyond: float,
) -> float:
    """Wie weit der Hohlraum ``beyond`` hinter einem Ende quer zur Achse reicht.

    Acht Strahlen von der Achse nach außen; der kürzeste zählt. Ohne Treffer
    ist es unendlich: Luft.
    """
    triangles = np.asarray(mesh.raw.triangles, dtype=np.float64)
    helper = np.array([1.0, 0.0, 0.0]) if abs(float(axis[0])) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = np.cross(axis, helper)
    first = first / math.sqrt(float(first[0] ** 2 + first[1] ** 2 + first[2] ** 2))
    second = np.cross(axis, first)
    start = origin + axis * (end + way * beyond)
    nearest = math.inf
    for step in range(8):
        angle = step * math.pi / 4.0
        direction = first * math.cos(angle) + second * math.sin(angle)
        hits = ray_hit_distances(triangles, start, direction)
        if hits.size:
            nearest = min(nearest, float(np.min(hits)))
    return nearest


@dataclass(frozen=True, slots=True)
class _Line:
    """Der versetzte Rand eines Abschnitts: ``r = a + b · s`` von ``start`` bis ``end``."""

    start: float
    end: float
    a: float
    b: float
    shoulder: bool

    def at(self, s: float) -> float:
        return self.a + self.b * s


def _offset(section: Section, gap: float, root: float) -> _Line:
    """Ein Abschnitt, senkrecht zu seiner Wand um ``gap`` nach innen versetzt."""
    if section.virtual:
        return _Line(section.start, section.end, root, 0.0, False)
    half = section.half_angle
    slope = math.tan(half)
    # Senkrecht zur Flanke heißt im Halbmesser ``gap / cos``: am Zylinder genau
    # ``gap``, an einer 90°-Senkung √2 · gap. Eine Wand, die quer näher kommt,
    # nimmt den Halbmesser um ``misfit`` enger (:func:`_misfit`).
    a = section.inner - section.start * slope - gap / math.cos(half) - section.misfit
    return _Line(section.start, section.end, a, slope, section.shoulder)


def outline(
    sections: Sequence[Section], low: float, high: float, gap: float, root: float = 0.0
) -> list[tuple[float, float]]:
    """Der Umriss des Stifts als ``(r, s)`` von unten nach oben — für ``shapes.revolved``.

    Jeder Abschnitt um ``gap`` nach innen versetzt (:func:`_offset`). Zwischen
    zwei Abschnitten ohne Stufe liegt die Ecke im Schnitt beider versetzter
    Wände; an einer Ringstufe steigt der Umriss um ``gap`` über die Stufe und
    springt dort auf den weiten Abschnitt. Beides hält überall mindestens
    ``gap`` Abstand zur Wand: Die Ecke über einer vorspringenden Kante liegt
    weiter weg als ``gap``, die in einer einspringenden genau so weit.
    """
    lines = [_offset(section, gap, root) for section in sections]
    bottom = min(low, lines[0].start)
    points: list[tuple[float, float]] = [(lines[0].at(bottom), bottom)]
    for previous, following in pairwise(lines):
        if following.shoulder:
            step = previous.end + gap
            points.append((previous.at(step), step))
            points.append((following.at(step), step))
            continue
        if abs(previous.b - following.b) <= EPS_GEOM:
            meet = previous.end
        else:
            meet = (following.a - previous.a) / (previous.b - following.b)
            meet = min(max(meet, previous.start - gap), following.end)
        points.append((previous.at(meet), meet))
    top = max(high, lines[-1].end)
    points.append((lines[-1].at(top), top))
    return _clipped(points, low, high)


def _clipped(
    points: list[tuple[float, float]], low: float, high: float
) -> list[tuple[float, float]]:
    """Der Rand zwischen ``low`` und ``high``, geschlossen über die Achse."""
    inside = [(r, s) for r, s in points if low + EPS_GEOM < s < high - EPS_GEOM]
    result = [(0.0, low), (_radius_at(points, low, upper=True), low)]
    result.extend(inside)
    result.extend([(_radius_at(points, high, upper=False), high), (0.0, high)])
    if any(r <= EPS_GEOM for r, _s in result[1:-1]):
        raise ValidationError(
            field="clearance",
            detail=CLEARANCE_TOO_LARGE,
            constraint="positive",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return result


def _radius_at(points: list[tuple[float, float]], s: float, *, upper: bool) -> float:
    """Der Halbmesser des Rands bei ``s``; an einer Stufe genau dort der obere oder untere."""
    for (r0, s0), (r1, s1) in pairwise(points):
        if s0 - EPS_GEOM <= s <= s1 + EPS_GEOM:
            if s1 - s0 <= EPS_GEOM:
                if upper:
                    continue
                return r0
            return r0 + (r1 - r0) * (s - s0) / (s1 - s0)
    return points[-1][0] if s >= points[-1][1] else points[0][0]


def _samples(
    vertices: NDArray[np.float64],
    origin: NDArray[np.float64],
    axis: NDArray[np.float64],
    pitch: float,
    low: float,
    high: float,
    reach: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Die Ecken eines Gewindes als (Gangphase, Halbmesser).

    Ein Gewinde ist unter einer Schraubung um die Achse in sich selbst
    überführt; jeder Punkt seiner Fläche liegt auf dem Profil ``r(u)`` mit
    ``u = s - Steigung · θ / 2π`` (rechtsgängig). Elementweise gerechnet wie
    ``mesh.ray_hits``, damit die gewählte Drehung auf jeder Maschine dieselbe ist.
    """
    helper = np.array([1.0, 0.0, 0.0]) if abs(float(axis[0])) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = np.cross(axis, helper)
    first = first / math.sqrt(float(first[0] ** 2 + first[1] ** 2 + first[2] ** 2))
    second = np.cross(axis, first)
    offset = np.asarray(vertices, dtype=np.float64) - origin
    s = offset[:, 0] * axis[0] + offset[:, 1] * axis[1] + offset[:, 2] * axis[2]
    x = offset[:, 0] * first[0] + offset[:, 1] * first[1] + offset[:, 2] * first[2]
    y = offset[:, 0] * second[0] + offset[:, 1] * second[1] + offset[:, 2] * second[2]
    r = np.sqrt(x * x + y * y)
    keep = (s > low) & (s < high) & (r < reach)
    if int(np.count_nonzero(keep)) > TURN_SAMPLES:
        chosen = np.flatnonzero(keep)
        keep = np.zeros_like(keep)
        keep[chosen[:: math.ceil(chosen.size / TURN_SAMPLES)]] = True
    phase = np.mod(s[keep] - pitch * np.arctan2(y[keep], x[keep]) / (2.0 * math.pi), pitch)
    return phase, r[keep]


def thread_turn(
    carrier: NDArray[np.float64],
    pin: NDArray[np.float64],
    origin: NDArray[np.float64],
    axis: NDArray[np.float64],
    zone: tuple[float, float],
    pitch: float,
    reach: float,
) -> tuple[float, float] | None:
    """Um wie viel Grad der Bolzen um die Achse zu drehen ist, damit er in den Gängen sitzt.

    ``carrier`` und ``pin`` sind die Ecken von Träger und Bolzen in der Welt.
    Beide Profile werden als ``r(u)`` gelesen (:func:`_samples`); gesucht ist
    die Verschiebung ``δ`` der Phase, bei der der Bolzen überall am weitesten
    innerhalb der Bohrung bleibt. Eine Drehung um ``φ`` verschiebt die Phase um
    ``-φ · Steigung / 360``. Zurück kommen die Drehung und der kleinste Abstand
    im Halbmesser; ``None``, wo an einer Seite keine Ecken liegen.
    """
    start, end = zone
    inset = pitch if end - start > 3.0 * pitch else 0.2 * (end - start)
    low, high = start + inset, end - inset
    around, outer = _samples(carrier, origin, axis, pitch, low, high, reach)
    phase, radius = _samples(pin, origin, axis, pitch, low, high, reach)
    if around.size < 8 or phase.size < 8:
        return None
    order = np.argsort(around, kind="stable")
    around, outer = around[order], outer[order]
    order = np.argsort(phase, kind="stable")
    phase, radius = phase[order], radius[order]
    shifts = np.arange(TURN_STEPS, dtype=np.float64) * (pitch / TURN_STEPS)
    best_gap = -math.inf
    best_shift = 0.0
    for shift in shifts:
        wall = np.interp(np.mod(phase + shift, pitch), around, outer, period=pitch)
        bolt = np.interp(np.mod(around - shift, pitch), phase, radius, period=pitch)
        gap = min(float(np.min(wall - radius)), float(np.min(outer - bolt)))
        if gap > best_gap + EPS_GEOM:
            best_gap, best_shift = gap, float(shift)
    return -360.0 * best_shift / pitch, best_gap
