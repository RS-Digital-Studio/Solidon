"""Funktionale Gruppen — Merkmale, die gemeinsam eine Aufgabe tragen (RM-184).

``features.py`` sagt, was eine Fläche ist, ``relations.py``, ob zwei Merkmale
zusammengehören. Diese Datei sagt, welche Merkmale **gemeinsam eine Funktion**
tragen: eine Kammer aus Boden und Wänden, ein Gewinde mit Einlauf und
Schulter, die Nocken eines Bajonetts, die Nut einer Dichtung, die Augen eines
Scharniers, die Buchstaben einer Schrift, die Aufnahmen eines Steckverbinders.
Der Dateiaudit vom 15.09.2026 (§7) hat sie an echten Modellen verlangt: Die
Einzelmerkmale waren da, ihre gemeinsame Bedeutung nicht.

**Benannt wird nur, was Geometrie und Nachbarschaft belegen** (Audit §7:
„Eine gekrümmte Fläche allein ist keine Feder, ein Ring allein kein
Gewinde"). Jede Gruppe nennt ihren Nachweis (:data:`GroupEvidence`); was nur
ein Verdacht ist, trägt ``suggested`` und wird angeboten, nicht behauptet.

**Eine Gruppe ändert nichts an der Erkennung.** Sie liest die fertige
Merkmalsliste und das Netz, vergibt keine Kennung, benennt kein Merkmal um und
gerät nicht in den Merkmalsabdruck. Darum verliert der Korpus durch sie nichts:
Dieselben Merkmale stehen da wie vorher, die Gruppe steht darüber.

**Nur erkannte Merkmale.** Was ein Baustein gebaut hat, gehört schon seinem
Schritt (der Objektbaum hängt es unter ihn); eine zweite Gruppierung daneben
wäre ein zweiter Name für dieselbe Sache.

**Plattformgleich**, weil eine Gruppe zwischen Flächen entscheidet
(``kern.md``): Skalarprodukte elementweise, Winkel über
:func:`units.exact_atan2_degrees`, kein BLAS.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Final, Literal, get_args

import numpy as np

from app.core.geom.mesh import MeshData, face_components, stable_normals
from app.core.types import CancelToken, Feature, FeatureId
from app.core.units import EPS_GEOM, exact_atan2_degrees, match_tolerance, plane_axes
from app.i18n import _

GroupKind = Literal["chamber", "channel", "thread", "closure", "hinge", "lettering", "socket"]
"""Die sieben Gruppen aus dem Dateiaudit (§7), in der Reihenfolge des Baums."""

GROUP_KINDS: Final[tuple[str, ...]] = get_args(GroupKind)

GroupEvidence = Literal[
    "floor_and_walls",
    "open_rim",
    "open_side",
    "two_walls",
    "ring_walls",
    "ring_chamber",
    "ribbed_passage",
    "coaxial_thread",
    "rotational_lugs",
    "rotational_notches",
    "collinear_eyes",
    "eye_on_axis",
    "flat_parts_on_a_carrier",
    "relief_on_a_carrier",
    "blind_bore_with_stop",
]
"""Welcher Befund eine Gruppe trägt — ein Satz je Wert in :func:`evidence_texts`."""

GroupRole = Literal[
    "floor",
    "wall",
    "blend",
    "ledge",
    "thread",
    "core",
    "run_in",
    "shoulder",
    "lug",
    "notch",
    "eye",
    "pin",
    "letter",
    "socket",
    "stop",
    "passage",
    "rib",
]
"""Die Rolle eines Merkmals in seiner Gruppe."""

#: Wie weit eine Fläche aus der Richtung des Bodens kippen darf und trotzdem
#: noch Boden heißt — und ab wann sie Wand ist. Kosinus gegen die Bodennormale.
FLOOR_ALIGNED: Final[float] = 0.98
WALL_UPRIGHT: Final[float] = 0.5

#: Unter dieser Bodennormalen-Komponente zeigt ein Dreieck zurück zum Boden:
#: eine Decke oder ein Hinterschnitt — dort endet die Kammer. Ein leicht
#: überhängender Entformungswinkel (bis gut zehn Grad) gehört noch dazu.
FACING_BACK: Final[float] = -0.2

#: Wie genau zwei Böden auf derselben Höhe liegen müssen, um Nachbarkammern
#: zu sein (Besteckkorb: sechs Fächer auf derselben Bodenhöhe).
SAME_LEVEL: Final[float] = 0.05

#: An wie vielen Bodendreiecken gefragt wird, ob über dem Boden Luft ist.
OPEN_RAYS: Final[int] = 5

#: Mindestmaße einer Kammer: flacher als ein Viertelmillimeter ist eine Stufe
#: der Oberfläche, und unter vier Quadratmillimetern Boden kein Raum, den man
#: bemaßt. Beide Zahlen liegen weit unter dem kleinsten Fall des Audits (die
#: Dichtnut am Wasserfalldeckel, 1,2 mm tief).
MIN_CHAMBER_DEPTH: Final[float] = 0.25
MIN_FLOOR_AREA: Final[float] = 4.0

#: Wie viel Wandfläche eine Seite tragen muss, um als Seite zu zählen — als
#: Anteil der ganzen Wandfläche. Eine Kammer ist ringsum geschlossen, wenn alle
#: vier Seiten zählen; ein Kanal hat genau zwei gegenüberliegende.
SIDE_SHARE: Final[float] = 0.04

#: Welcher Anteil des Bodenrands an Wand stoßen muss: ringsum bei Kammer und
#: Nut (bis auf kleine Unterbrechungen), drei Seiten bei der offenen Tasche, die
#: zwei langen Seiten beim Kanal.
ENCLOSED_RING: Final[float] = 0.9
ENCLOSED_SIDE: Final[float] = 0.6
ENCLOSED_TROUGH: Final[float] = 0.5

#: Ab wann ein ringförmiger Raum keine Nut mehr ist, sondern eine Kammer:
#: tiefer als doppelt so breit (der Ringraum des Filterkäfigs, 22 auf 87 mm).
RING_CHAMBER_RATIO: Final[float] = 2.0

#: Ab wann ein Wandstück zu einer Seite gehört: Kosinus seiner waagerechten
#: Normalen gegen die Seitenrichtung (unter 45 Grad).
SIDE_ALIGNED: Final[float] = 0.7

#: Ab wie vielen Stellungen ein Kranz ein Verschluss ist. Zwei gleiche Hälften
#: hat jedes gespiegelte Teil (der Griffsteg am Kartuschendeckel) — erst drei
#: gleichmäßig verteilte Stellungen sind eine Absicht.
MIN_CLOSURE_POSITIONS: Final[int] = 3

#: Wann ein Kranz gleichmäßig ist: Die Mitten der Stücke dürfen um zwei Grad
#: vom gleichen Abstand abweichen, die Flächensumme je Stück um ein Viertel.
STATION_SPACING_DEGREES: Final[float] = 2.0
STATION_AREA_SPREAD: Final[float] = 0.25

#: Bis zu wie vielen Wiederholungen ein Kranz ein Verschluss ist. Bajonette und
#: Rastungen haben zwei bis sechs Stellungen; mehr gleiche Stücke um eine Achse
#: sind ein Gitter, ein Rändel oder ein Lochkreis (51 Schlitze am Filterkäfig).
MOST_CLOSURE_POSITIONS: Final[int] = 6

#: Wie viel tiefer als weit eine Sackbohrung sein muss, um eine Steckaufnahme
#: zu sein. Eine Magnettasche ist flacher als breit, ein Schraubenloch am
#: Wasserfalldeckel (Ø 4,5 auf 5 mm) knapp tiefer; die Hülse des
#: Stangenverbinders (Ø 16,9 auf 36 mm) liegt mit 2,1 weit darüber.
SOCKET_DEPTH_RATIO: Final[float] = 1.5

#: Wie groß eine Aufnahme gegen den Körper höchstens ist (Durchmesser zur
#: Diagonale). Der Stangenverbinder liegt bei 0,18, der Innenraum des
#: Gewürzbehälters bei 0,41 und der des Filterkäfigs bei 0,52.
SOCKET_BODY_SHARE: Final[float] = 0.35

#: Wie klein ein einzelnes Scharnierauge gegen den Körper ist (Durchmesser und
#: Länge zur Diagonale); das Kernrohr eines Käfigs ist kein Auge.
EYE_BODY_SHARE: Final[float] = 0.25

#: Wie flach ein Teil sein muss, um ein Buchstabe zu sein: Höhe über dem Träger
#: höchstens so viel wie seine halbe Breite in der Ebene.
LETTER_FLATNESS: Final[float] = 0.5
#: Erhabene oder vertiefte Schrift: Buchstabenoberseiten höchstens ein
#: Zwanzigstel des Trägers, 0,2 bis 5 mm über oder unter ihm, auf einer Höhe
#: bis auf ein Hundertstel Millimeter, ab fünf Stück, und verschieden groß
#: (Streuung der Flächen mindestens ein Zehntel ihres Mittels).
LETTER_SHARE: Final[float] = 0.05
LETTER_RELIEF: Final[tuple[float, float]] = (0.2, 5.0)
LETTER_LEVEL: Final[float] = 0.01
RELIEF_LETTERS: Final[int] = 5
LETTER_VARIETY: Final[float] = 0.1

#: Ab so vielen gleich hohen flachen Teilen auf einem Träger ist es Schrift.
MIN_LETTERS: Final[int] = 3

#: Ein Buchstabe füllt seine konvexe Hülle nicht: Fläche zu Hüllfläche unter
#: 0,8 — ein „S“, „3“ oder „B“ liegt um 0,5, Kreis, Quadrat und Noppe bei 1.
#: Mindestens die Hälfte der Buchstaben einer Schrift ist so geformt („i“ und
#: „l“ sind es nicht; am WC-Schild sind es 15 von 24 Oberseiten).
GLYPH_SOLIDITY: Final[float] = 0.8
GLYPH_SHARE: Final[float] = 0.5

#: Schrift hat viele Formen: mindestens fünf verschiedene Buchstaben (Fläche
#: auf zwei Prozent, Füllung auf drei Hundertstel gleich heißt dieselbe
#: Form). Ein Raster wiederholt wenige — die Kreuze einer Spielplatte, die
#: Noppen einer Box; das WC-Schild hat 16 Formen unter 24 Oberseiten.
GLYPH_SHAPES: Final[int] = 5


@dataclass(frozen=True, slots=True)
class GroupMeasure:
    """Ein Maß der Gruppe — gemessen, nie vorgegeben."""

    name: str
    value: float
    unit: str
    """``mm``, ``°`` oder leer für eine Anzahl."""


@dataclass(frozen=True, slots=True)
class FunctionalGroup:
    """Merkmale, die gemeinsam eine Funktion tragen, mit Nachweis und Maßen."""

    kind: GroupKind
    variant: str
    """Die Bauart innerhalb der Art: ``closed``/``open_rim``/``open_side``
    (Kammer), ``groove``/``trough``/``passage`` (Kanal), ``outer``/``inner``
    (Gewinde), ``bayonet``/``detent`` (Verschluss), ``separate``
    (Schrift aus eigenen Teilen) — der Name im Baum hängt daran."""
    anchor: FeatureId
    """Das Merkmal, das für die Gruppe steht: Boden, Gewinde, Bohrung."""
    members: tuple[FeatureId, ...]
    roles: tuple[tuple[FeatureId, GroupRole], ...]
    measures: tuple[GroupMeasure, ...]
    evidence: GroupEvidence
    suggested: bool = False
    """Ein Verdacht, kein Befund — angeboten, nicht behauptet (Audit §7)."""
    count: int = 1
    """Wie viele gleiche Einheiten: Nocken, Augen, Aufnahmen, Buchstaben."""
    shared: bool = False
    """Die Wände gehören auch einer Nachbarkammer — gemeinsam ändern geht nicht."""
    planar_rim: bool = False
    """Die Kammer endet oben an einem ebenen Rand — Bedingung fürs Ändern."""

    @property
    def key(self) -> str:
        """Kennung der Gruppe: Art und Anker, stabil wie die Merkmalsnummer."""
        return f"{self.kind}:{self.anchor}"

    def measure(self, name: str) -> float | None:
        """Der Wert eines Maßes, oder ``None``."""
        return next((entry.value for entry in self.measures if entry.name == name), None)

    def role_of(self, feature_id: FeatureId) -> GroupRole | None:
        """Die Rolle eines Mitglieds."""
        return next((role for member, role in self.roles if member == feature_id), None)


def evidence_texts() -> dict[GroupEvidence, str]:
    """Ein Satz je Nachweis — für Baum, Merkmalfenster und Steckbrief dieselben.

    Zur Laufzeit übersetzt, weil die Sprache wechseln kann.
    """
    from app.i18n import tr

    return {
        "floor_and_walls": tr("Boden und Wände umschließen eine Öffnung."),
        "open_rim": tr(
            "Boden und Wände umschließen eine Öffnung; Rand oder Wände sind durchbrochen."
        ),
        "open_side": tr("Boden und Wände bilden eine an einer Seite offene Tasche."),
        "two_walls": tr("Boden und zwei gegenüberliegende Wände bilden einen offenen Kanal."),
        "ring_walls": tr("Boden und zwei umlaufende Wände bilden eine geschlossene Nut."),
        "ring_chamber": tr("Boden, Außen- und Innenwand umschließen einen ringförmigen Raum."),
        "ribbed_passage": tr("Ein durchgehender Kanal trägt Rippen auf derselben Achse."),
        "coaxial_thread": tr(
            "Gewinde, Einlauf und Schulter liegen auf derselben Achse und grenzen aneinander."
        ),
        "rotational_lugs": tr("Gleiche Nocken oder Wege wiederholen sich um dieselbe Achse."),
        "rotational_notches": tr("Gleiche Rastmulden wiederholen sich um dieselbe Achse."),
        "collinear_eyes": tr(
            "Augen mit gleicher Bohrung liegen auf einer Achse, mit Spalt dazwischen."
        ),
        "eye_on_axis": tr(
            "Ein Auge mit Bohrung auf einer Achse — vermutlich eine Scharnierhälfte."
        ),
        "relief_on_a_carrier": tr(
            "Verschieden große Flächen liegen auf gleicher Höhe über einer Trägerfläche."
        ),
        "flat_parts_on_a_carrier": tr(
            "Gleich hohe flache Teile liegen auf derselben Trägerfläche."
        ),
        "blind_bore_with_stop": tr("Eine Sackbohrung, tiefer als weit, mit flachem Anschlag."),
    }


def functional_title(group: FunctionalGroup) -> str:
    """Der Name der Gruppe im Baum, ohne Nummer."""
    from app.i18n import tr

    titles = {
        # Mit Kontext: „Kammer“ allein ist im Katalog die Druckkammer.
        ("chamber", "closed"): tr("Kammer", context="Merkmalsgruppe"),
        ("chamber", "open_rim"): tr("Tasche mit offenem Rand"),
        ("chamber", "open_side"): tr("Offene Tasche"),
        ("chamber", "ring"): tr("Ringkammer"),
        ("channel", "groove"): tr("Nut"),
        ("channel", "trough"): tr("Kanal"),
        ("channel", "passage"): tr("Anschluss mit Durchgang"),
        ("thread", "outer"): tr("Gewinde mit Einlauf"),
        ("thread", "inner"): tr("Innengewinde mit Einlauf"),
        ("closure", "bayonet"): tr("Bajonett"),
        ("closure", "detent"): tr("Rastung"),
        ("hinge", "axis"): tr("Scharnierachse"),
        ("hinge", "half"): tr("Scharnierauge"),
        ("lettering", "separate"): tr("Schriftzug"),
        ("lettering", "raised"): tr("Schriftzug erhaben"),
        ("lettering", "engraved"): tr("Schriftzug vertieft"),
        ("socket", "blind"): tr("Steckaufnahme"),
    }
    return titles.get((group.kind, group.variant), tr("Gruppe"))


def measure_titles() -> dict[str, str]:
    """Die Beschriftung je Maß einer Gruppe."""
    from app.i18n import tr

    return {
        "width": tr("Breite innen"),
        "length": tr("Länge innen"),
        "depth": tr("Tiefe"),
        "diameter": tr("Durchmesser"),
        "pitch": tr("Steigung"),
        "turns": tr("Windungen"),
        "thread_length": tr("Gewindelänge"),
        "count": tr("Anzahl"),
        "spacing": tr("Winkelabstand"),
        "radius": tr("Radius"),
        "height": tr("Höhe"),
        "gap": tr("Spalt zwischen den Augen"),
        "ribs": tr("Rippen"),
        "rib_diameter": tr("Rippen-Ø"),
    }


# --- Der Einstieg -------------------------------------------------------------


def functional_groups(
    features: Mapping[FeatureId, Feature],
    mesh: MeshData | None = None,
    *,
    cancelled: CancelToken | None = None,
) -> tuple[FunctionalGroup, ...]:
    """Alle funktionalen Gruppen eines Körpers, in der Reihenfolge des Baums.

    Ohne Netz bleiben die Gruppen, die nur Merkmalsmaße brauchen (Gewinde,
    Scharnier, Aufnahme, Verschluss); Kammer, Kanal und Schrift lesen das Netz.
    Ein Merkmal steht in höchstens einer Gruppe: Wer zuerst belegt ist, behält
    es — Gewinde vor Aufnahme vor Scharnier vor Verschluss vor Schrift vor
    Kammer.

    **Einmal je Körper und Merkmalsliste** (``features.remembered``): Baum,
    Merkmalfenster, Steckbrief und die Operation fragen dieselbe Antwort, und
    eine Kopie für den Arbeiter liest sie mit (``SHARED_ANSWERS`` — die Gruppen
    sind unveränderliche Zahlen und Namen).
    """
    if mesh is None or not mesh.triangle_count:
        return _computed(features, None, cancelled)
    from app.core.perceive.features import remembered

    answer: tuple[FunctionalGroup, ...] = remembered(
        "functional_groups",
        mesh.raw,
        (),
        lambda: _computed(features, mesh, cancelled),
        extra=_features_key(features),
        check_cancelled=cancelled.raise_if_cancelled if cancelled is not None else None,
    )
    return answer


def _features_key(features: Mapping[FeatureId, Feature]) -> tuple[object, ...]:
    """Was die Antwort bestimmt: je Merkmal Art, Herkunft, Dreiecke und Maße."""

    def frozen(value: object) -> object:
        if isinstance(value, (list, tuple)):
            return tuple(frozen(entry) for entry in value)
        if isinstance(value, dict):
            return tuple(sorted((str(key), frozen(entry)) for key, entry in value.items()))
        return value

    return tuple(
        (
            name,
            feature.kind,
            feature.provenance,
            feature.created_by,
            feature.face_indices,
            frozen(dict(feature.params)),
        )
        for name, feature in sorted(features.items())
    )


def _computed(
    features: Mapping[FeatureId, Feature],
    mesh: MeshData | None,
    cancelled: CancelToken | None,
) -> tuple[FunctionalGroup, ...]:
    detected = {
        name: feature
        for name, feature in features.items()
        if feature.provenance == "detected" and feature.created_by is None
    }
    if not detected:
        return ()
    diagonal = _diagonal(detected, mesh)
    tolerance = match_tolerance(diagonal)
    found: list[FunctionalGroup] = []
    taken: set[FeatureId] = set()

    def take(groups: Iterable[FunctionalGroup]) -> None:
        for group in groups:
            if taken.isdisjoint(group.members):
                found.append(group)
                taken.update(group.members)

    take(_threads(detected, tolerance))
    _check(cancelled)
    take(_sockets(detected, tolerance, diagonal))
    take(_hinges(detected, tolerance, diagonal))
    _check(cancelled)
    take(_passages(detected, tolerance))
    take(_closures(detected, tolerance))
    _check(cancelled)
    if mesh is not None and mesh.triangle_count:
        surface = _Surface.of(mesh)
        pieces = face_components(mesh.raw, cancelled=cancelled)
        part_of = np.zeros(len(surface.corner_ids), dtype=np.int64)
        for number, piece in enumerate(pieces):
            part_of[piece] = number
        take(_relief_lettering(detected, surface, part_of, tolerance))
        take(_lettering(detected, mesh, surface, pieces, tolerance))
        _check(cancelled)
        take(_chambers(detected, surface, tolerance, cancelled))
    order = {kind: index for index, kind in enumerate(GROUP_KINDS)}
    return tuple(sorted(found, key=lambda group: (order[group.kind], _id_key(group.anchor))))


@dataclass(frozen=True, slots=True)
class ChamberRegion:
    """Was eine Kammer am Netz ist: ihre Dreiecke, ihr Boden, ihre Lage.

    Die Operation *Kammer ändern* liest daraus das Werkzeug; die Gruppe selbst
    trägt nur Namen und Maße.
    """

    group: FunctionalGroup
    triangles: np.ndarray
    floor: np.ndarray
    normal: Vec
    origin: Vec
    axes: tuple[Vec, Vec]


def chamber_region(
    features: Mapping[FeatureId, Feature],
    mesh: MeshData,
    member: FeatureId,
    *,
    cancelled: CancelToken | None = None,
) -> ChamberRegion | None:
    """Die Kammer, die Nut oder der Kanal eines Merkmals — oder ``None``."""
    group = group_of(member, functional_groups(features, mesh, cancelled=cancelled))
    if group is None or group.kind not in ("chamber", "channel") or group.variant == "passage":
        return None
    surface = _Surface.of(mesh)
    floor_feature = features[group.anchor]
    triangles = np.asarray(floor_feature.face_indices, dtype=np.int64)
    # Dieselben Merkmale wie die Suche (:func:`_computed`): Ein Merkmal aus einem
    # Baustein gehört keiner Gruppe und begrenzt keine Wanderung.
    detected = {
        name: feature
        for name, feature in features.items()
        if feature.provenance == "detected" and feature.created_by is None
    }
    tolerance = match_tolerance(_diagonal(detected, mesh))
    lookup = _Lookup.of(detected, surface)
    region = _flood(group.anchor, floor_feature, triangles, surface, lookup, tolerance)
    if region is None:
        return None
    normals = surface.normals[region.triangles]
    areas = surface.areas[region.triangles]
    facing = (
        normals[:, 0] * region.normal[0]
        + normals[:, 1] * region.normal[1]
        + normals[:, 2] * region.normal[2]
    )
    walls = np.abs(facing) < WALL_UPRIGHT
    axes = _dominant_axes(normals[walls], areas[walls], region.normal)
    if axes is None:
        return None
    return ChamberRegion(group, region.triangles, triangles, region.normal, region.origin, axes)


def reason_against_group(group: FunctionalGroup) -> str | None:
    """Warum diese Gruppe sich nicht als Ganzes ändern lässt — oder ``None``.

    Dieselbe Frage für Merkmalfenster und Operation: Was das Fenster anbietet,
    rechnet die Operation auch.
    """
    if group.kind not in ("chamber", "channel") or group.variant == "passage":
        return str(NOT_A_CHAMBER)
    if group.shared:
        return str(
            _(
                "Diese Kammer teilt ihre Wände mit einer Nachbarkammer. Ändern Sie eine "
                "Wand einzeln über „Fläche versetzen“."
            )
        )
    if group.variant in ("open_rim", "open_side"):
        return str(
            _(
                "Rand oder Wände dieser Tasche sind durchbrochen, oder eine Seite ist offen — "
                "als Ganzes lässt sie sich nicht strecken. Ändern Sie eine Wand über „Fläche "
                "versetzen“."
            )
        )
    if group.kind == "chamber" and not group.planar_rim:
        return str(
            _(
                "Der Rand dieser Kammer liegt nicht auf einer Höhe. Ändern Sie eine Wand "
                "über „Fläche versetzen“."
            )
        )
    return None


NOT_A_CHAMBER = _(
    "Dieses Merkmal gehört weder zu einer erkannten Kammer noch zu einer Nut oder einem "
    "Kanal. Wählen Sie den Boden oder eine Wand einer Kammer."
)


def group_of(feature_id: FeatureId, groups: Sequence[FunctionalGroup]) -> FunctionalGroup | None:
    """Die Gruppe, in der ein Merkmal steht — oder keine."""
    return next((group for group in groups if feature_id in group.members), None)


def numbered_titles(groups: Sequence[FunctionalGroup]) -> dict[str, str]:
    """Der Name je Gruppe im Baum: „Kammer 1", „Kammer 2", „Gewinde mit Einlauf"."""
    counts: dict[str, int] = {}
    for group in groups:
        title = functional_title(group)
        counts[title] = counts.get(title, 0) + 1
    seen: dict[str, int] = {}
    named: dict[str, str] = {}
    for group in groups:
        title = functional_title(group)
        if counts[title] > 1:
            seen[title] = seen.get(title, 0) + 1
            named[group.key] = f"{title} {seen[title]}"
        else:
            named[group.key] = title
    return named


def _check(cancelled: CancelToken | None) -> None:
    if cancelled is not None:
        cancelled.raise_if_cancelled()


def _id_key(identifier: FeatureId) -> tuple[str, int]:
    """``hole_10`` nach ``hole_9`` — die Nummer zählt, nicht der Text."""
    stem, _sep, number = identifier.rpartition("_")
    return (stem, int(number)) if number.isdigit() else (identifier, 0)


def _diagonal(features: Mapping[FeatureId, Feature], mesh: MeshData | None) -> float:
    """Die Körperdiagonale — der Maßstab der Toleranz."""
    if mesh is not None and mesh.triangle_count:
        low = np.asarray(mesh.bounds.minimum, dtype=float)
        high = np.asarray(mesh.bounds.maximum, dtype=float)
        span = high - low
        return math.sqrt(float(span[0] * span[0] + span[1] * span[1] + span[2] * span[2]))
    centres = [_vector(feature.params.get("centre")) for feature in features.values()]
    points = [centre for centre in centres if centre is not None]
    if len(points) < 2:
        return 100.0
    span3 = [
        max(point[i] for point in points) - min(point[i] for point in points) for i in range(3)
    ]
    return max(math.sqrt(sum(value * value for value in span3)), 1.0)


# --- Kleine Geometrie über Merkmalsmaße --------------------------------------

Vec = tuple[float, float, float]


def _vector(raw: object) -> Vec | None:
    if not isinstance(raw, (tuple, list)) or len(raw) != 3:
        return None
    try:
        values = (float(raw[0]), float(raw[1]), float(raw[2]))
    except TypeError, ValueError:
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    return values


def _unit(raw: object) -> Vec | None:
    vector = _vector(raw)
    if vector is None:
        return None
    length = math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2])
    if length <= EPS_GEOM:
        return None
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scaled(a: Vec, factor: float) -> Vec:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def _length(a: Vec) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _number(feature: Feature, name: str) -> float | None:
    raw = feature.params.get(name)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    value = float(raw)
    return value if math.isfinite(value) else None


@dataclass(frozen=True, slots=True)
class _Axis:
    """Eine Achse aus einem Rundmerkmal: Richtung, Punkt, Durchmesser, Spanne."""

    feature: FeatureId
    kind: str
    direction: Vec
    point: Vec
    diameter: float
    depth: float

    def along(self, point: Vec) -> float:
        return _dot(_sub(point, self.point), self.direction)

    def off(self, point: Vec) -> float:
        """Abstand eines Punkts von der Achsgeraden."""
        relative = _sub(point, self.point)
        along = _dot(relative, self.direction)
        across = _sub(relative, _scaled(self.direction, along))
        return _length(across)

    def parallel(self, other: _Axis, tolerance: float = 1e-3) -> bool:
        return abs(abs(_dot(self.direction, other.direction)) - 1.0) <= tolerance

    def collinear(self, other: _Axis, distance: float) -> bool:
        return self.parallel(other) and self.off(other.point) <= distance


def _axis(name: FeatureId, feature: Feature) -> _Axis | None:
    direction = _unit(feature.params.get("axis"))
    point = _vector(feature.params.get("centre"))
    diameter = _number(feature, "diameter")
    if direction is None or point is None or diameter is None or diameter <= EPS_GEOM:
        return None
    depth = _number(feature, "depth") or _number(feature, "length") or 0.0
    return _Axis(name, feature.kind, direction, point, diameter, max(depth, 0.0))


def _round_axes(features: Mapping[FeatureId, Feature]) -> list[_Axis]:
    found: list[_Axis] = []
    for name in sorted(features, key=_id_key):
        feature = features[name]
        if feature.kind in ("hole", "pin", "cone", "thread", "fillet", "torus"):
            axis = _axis(name, feature)
            if axis is not None:
                found.append(axis)
    return found


# --- Gewinde mit Einlauf ----------------------------------------------------


def _threads(features: Mapping[FeatureId, Feature], tolerance: float) -> list[FunctionalGroup]:
    """Ein Gewinde und was auf seiner Achse an ihm hängt (Audit §7, Fall 179).

    Kern ist der Zylinder unter den Gängen (Zapfen außen, Bohrung innen),
    Einlauf ein Kegel an einem Ende, Schulter eine Fläche quer zur Achse an
    einem Ende innerhalb des Gewindedurchmessers plus zwei Gangtiefen. Alles
    andere auf derselben Achse — der Becherraum, ein Hals weiter oben — gehört
    nicht dazu.
    """
    groups: list[FunctionalGroup] = []
    axes = _round_axes(features)
    for name in sorted(features, key=_id_key):
        thread = features[name]
        if thread.kind != "thread":
            continue
        axis = _axis(name, thread)
        pitch = _number(thread, "pitch")
        length = _number(thread, "length")
        if axis is None or pitch is None or length is None or length <= EPS_GEOM:
            continue
        depth = _number(thread, "depth") or pitch * 0.6
        start = -length / 2.0
        end = length / 2.0
        reach = max(pitch, tolerance)
        shoulder_reach = max(pitch / 2.0, tolerance)
        roles: list[tuple[FeatureId, GroupRole]] = [(name, "thread")]
        inner = bool(thread.params.get("internal", False))
        for other in axes:
            if other.feature == name or not other.collinear(axis, max(tolerance, depth)):
                continue
            centre = axis.along(other.point)
            half = other.depth / 2.0
            if other.kind in ("pin", "hole"):
                overlaps = centre + half >= start + tolerance and centre - half <= end - tolerance
                close = abs(other.diameter - axis.diameter) <= 2.0 * depth + 2.0 * tolerance
                if overlaps and close:
                    roles.append((other.feature, "core"))
            elif other.kind == "cone":
                at_an_end = min(abs(centre - start), abs(centre - end)) <= reach + other.depth
                close = abs(other.diameter - axis.diameter) <= 4.0 * depth + 2.0 * tolerance
                if at_an_end and close:
                    roles.append((other.feature, "run_in"))
        for face_name in sorted(features, key=_id_key):
            face = features[face_name]
            if face.kind != "face":
                continue
            normal = _unit(face.params.get("normal"))
            middle = _vector(face.params.get("centre"))
            if (
                normal is None
                or middle is None
                or abs(_dot(normal, axis.direction)) < FLOOR_ALIGNED
            ):
                continue
            along = axis.along(middle)
            if min(abs(along - start), abs(along - end)) > shoulder_reach:
                continue
            if axis.off(middle) > axis.diameter / 2.0 + 2.0 * depth:
                continue
            roles.append((face_name, "shoulder"))
        turns = length / pitch
        measures = (
            GroupMeasure("diameter", axis.diameter, "mm"),
            GroupMeasure("pitch", pitch, "mm"),
            GroupMeasure("thread_length", length, "mm"),
            GroupMeasure("turns", round(turns, 2), ""),
        )
        groups.append(
            FunctionalGroup(
                kind="thread",
                variant="inner" if inner else "outer",
                anchor=name,
                members=tuple(member for member, _role in roles),
                roles=tuple(roles),
                measures=measures,
                evidence="coaxial_thread",
            )
        )
    return groups


# --- Steckaufnahme mit Anschlag ---------------------------------------------


def _sockets(
    features: Mapping[FeatureId, Feature], tolerance: float, diagonal: float
) -> list[FunctionalGroup]:
    """Sackbohrungen, tiefer als weit, mit flachem Anschlag am Grund.

    Gleich weite Aufnahmen eines Körpers sind **eine** Gruppe: Ihr Gegenstück
    ist derselbe Stab (Audit, Pflanzen-Ständerset: Ecke, T und Kreuz aus
    derselben Hülse) — wer das Stabmaß ändert, meint jede.
    """
    found: list[tuple[_Axis, FeatureId]] = []
    for name in sorted(features, key=_id_key):
        hole = features[name]
        if hole.kind != "hole" or hole.params.get("through", True):
            continue
        axis = _axis(name, hole)
        if axis is None or axis.depth < SOCKET_DEPTH_RATIO * axis.diameter:
            continue
        if axis.diameter > SOCKET_BODY_SHARE * diagonal:
            # Der Innenraum eines Bechers ist tiefer als weit und hat einen
            # Boden — eine Aufnahme ist er nicht (Filterkäfig Ø 75 in Ø 79).
            continue
        stop = _stop_of(axis, features, tolerance)
        if stop is not None:
            found.append((axis, stop))
    groups: list[FunctionalGroup] = []
    used: set[FeatureId] = set()
    for axis, _stop in found:
        if axis.feature in used:
            continue
        same = [
            (other, stop)
            for other, stop in found
            if other.feature not in used and abs(other.diameter - axis.diameter) <= tolerance
        ]
        roles: list[tuple[FeatureId, GroupRole]] = []
        for other, stop in same:
            used.add(other.feature)
            roles.append((other.feature, "socket"))
            roles.append((stop, "stop"))
        depths = [other.depth for other, _stop in same]
        groups.append(
            FunctionalGroup(
                kind="socket",
                variant="blind",
                anchor=axis.feature,
                members=tuple(member for member, _role in roles),
                roles=tuple(roles),
                measures=(
                    GroupMeasure("diameter", axis.diameter, "mm"),
                    GroupMeasure("depth", min(depths), "mm"),
                    GroupMeasure("count", float(len(same)), ""),
                ),
                evidence="blind_bore_with_stop",
                count=len(same),
            )
        )
    return groups


def _stop_of(
    axis: _Axis, features: Mapping[FeatureId, Feature], tolerance: float
) -> FeatureId | None:
    """Die ebene Fläche am Grund einer Sackbohrung, quer zur Achse."""
    best: tuple[float, FeatureId] | None = None
    for name in sorted(features, key=_id_key):
        face = features[name]
        if face.kind != "face":
            continue
        normal = _unit(face.params.get("normal"))
        centre = _vector(face.params.get("centre"))
        if normal is None or centre is None:
            continue
        if abs(_dot(normal, axis.direction)) < FLOOR_ALIGNED:
            continue
        if axis.off(centre) > axis.diameter / 2.0:
            continue
        along = abs(axis.along(centre))
        distance = abs(along - axis.depth / 2.0)
        if distance > max(tolerance, 0.02 * axis.depth):
            continue
        if best is None or distance < best[0]:
            best = (distance, name)
    return best[1] if best is not None else None


# --- Scharnier --------------------------------------------------------------


def _hinges(
    features: Mapping[FeatureId, Feature], tolerance: float, diagonal: float
) -> list[FunctionalGroup]:
    """Augen mit gleicher Bohrung auf einer Achse, getrennt durch Spalte.

    Zwei durchgehende Bohrungen gleichen Durchmessers auf einer Geraden, deren
    Spannen sich nicht überdecken, sind die Augen einer Scharnierhälfte — der
    Spalt dazwischen ist der Platz für das Gegenauge (Audit, Glasdeckel:
    Ring mit zwei äußeren Augen, Deckel mit dem mittleren). **Jedes Auge
    braucht seinen Knöchel** (:func:`_knuckle`): Gegenüberliegende Löcher in
    einer Kugelwand oder ein Schraubloch durch zwei Wände liegen auch auf einer
    Geraden. Ein einzelnes Auge mit Knöchel ist nur ein Verdacht, und nur, wenn
    seine Achse quer zur größten Fläche des Körpers liegt — eine Bohrung durch
    einen Deckel ist keine Scharnierhälfte.
    """
    holes = [
        axis
        for axis in _round_axes(features)
        if axis.kind == "hole" and features[axis.feature].params.get("through", False)
    ]
    rounds = [
        axis
        for axis in _round_axes(features)
        if axis.kind == "pin"
        or (axis.kind == "fillet" and not features[axis.feature].params.get("recess"))
    ]
    main_normal = _largest_face_normal(features)
    groups: list[FunctionalGroup] = []
    used: set[FeatureId] = set()
    for axis in holes:
        if axis.feature in used:
            continue
        row = [
            other
            for other in holes
            if other.feature not in used
            and abs(other.diameter - axis.diameter) <= tolerance
            and axis.collinear(other, max(tolerance, axis.diameter * 0.05))
        ]
        row.sort(key=lambda other: axis.along(other.point))
        spans = [
            (
                axis.along(other.point) - other.depth / 2.0,
                axis.along(other.point) + other.depth / 2.0,
            )
            for other in row
        ]
        gaps = [later[0] - earlier[1] for earlier, later in pairwise(spans)]
        knuckles = [_knuckle(other, rounds, used, tolerance) for other in row]
        if (
            len(row) >= 2
            and all(gap > tolerance for gap in gaps)
            and all(knuckle is not None for knuckle in knuckles)
        ):
            used.update(other.feature for other in row)
            roles: list[tuple[FeatureId, GroupRole]] = [(other.feature, "eye") for other in row]
            for knuckle in knuckles:
                if knuckle is not None and knuckle.feature not in used:
                    used.add(knuckle.feature)
                    roles.append((knuckle.feature, "eye"))
            groups.append(
                FunctionalGroup(
                    kind="hinge",
                    variant="axis",
                    anchor=row[0].feature,
                    members=tuple(member for member, _role in roles),
                    roles=tuple(roles),
                    measures=(
                        GroupMeasure("diameter", axis.diameter, "mm"),
                        GroupMeasure("count", float(len(row)), ""),
                        GroupMeasure("gap", min(gaps), "mm"),
                    ),
                    evidence="collinear_eyes",
                    count=len(row),
                )
            )
            continue
        eye = _knuckle(axis, rounds, used, tolerance)
        across = (
            main_normal is None or abs(_dot(axis.direction, main_normal)) <= 1.0 - FLOOR_ALIGNED
        )
        if (
            eye is not None
            and len(row) == 1
            and across
            and axis.depth >= 0.5 * axis.diameter
            and eye.diameter <= EYE_BODY_SHARE * diagonal
            and eye.depth <= EYE_BODY_SHARE * diagonal
        ):
            used.add(axis.feature)
            groups.append(
                FunctionalGroup(
                    kind="hinge",
                    variant="half",
                    anchor=axis.feature,
                    members=(axis.feature, eye.feature),
                    roles=((axis.feature, "eye"), (eye.feature, "eye")),
                    measures=(
                        GroupMeasure("diameter", axis.diameter, "mm"),
                        GroupMeasure("count", 1.0, ""),
                    ),
                    evidence="eye_on_axis",
                    suggested=True,
                )
            )
    return groups


def _knuckle(
    eye: _Axis, rounds: Sequence[_Axis], used: set[FeatureId], tolerance: float
) -> _Axis | None:
    """Der Knöchel um ein Auge: eine koaxiale äußere Rundung derselben Spanne.

    Weiter als die Bohrung, höchstens dreimal so weit, an derselben Stelle der
    Achse und nicht länger als dreimal ihr Durchmesser — sonst ist es ein Rohr
    oder ein Rundkörper, durch den eine Bohrung führt (Glasdeckel: Ø 3,4 in
    Ø 8,4 auf 8 mm; Werkzeugbox: Ø 3,2 in Ø 9 auf 6 mm).
    """
    reach = max(tolerance, eye.diameter * 0.05)
    for outer in rounds:
        if outer.feature in used or not outer.collinear(eye, reach):
            continue
        if not eye.diameter + 2.0 * tolerance < outer.diameter <= 3.0 * eye.diameter:
            continue
        if abs(eye.along(outer.point) - eye.along(eye.point)) > max(eye.depth, outer.depth) / 2.0:
            continue
        if abs(outer.depth - eye.depth) > max(tolerance, 0.1 * eye.depth):
            continue
        if outer.depth > 3.0 * outer.diameter:
            continue
        return outer
    return None


def _largest_face_normal(features: Mapping[FeatureId, Feature]) -> Vec | None:
    """Die Richtung der größten ebenen Fläche — gleich große nach Nummer."""
    best: tuple[float, Vec] | None = None
    for name in sorted(features, key=_id_key):
        feature = features[name]
        if feature.kind != "face":
            continue
        normal = _unit(feature.params.get("normal"))
        area = _number(feature, "area")
        if normal is None or area is None:
            continue
        if best is None or area > best[0]:
            best = (area, normal)
    return best[1] if best is not None else None


# --- Anschluss mit Durchgang (Schlauchtülle) --------------------------------


def _passages(features: Mapping[FeatureId, Feature], tolerance: float) -> list[FunctionalGroup]:
    """Ein Durchgang mit mehreren koaxialen Zapfenabschnitten außen.

    Die Tülle des Wasserfalls (Audit, Fall 096) zerfiel in eine Bohrung und
    elf Zapfen: Flansch, Schaft und vier Rippen. Gemeinsam sind sie ein
    Anschluss mit freiem Durchgang; erst ab drei Abschnitten, sonst ist es ein
    Rohr mit Bund.
    """
    axes = _round_axes(features)
    groups: list[FunctionalGroup] = []
    used: set[FeatureId] = set()
    for axis in axes:
        if axis.kind != "hole" or axis.feature in used:
            continue
        if not features[axis.feature].params.get("through", False):
            continue
        ribs = [
            other
            for other in axes
            if other.kind == "pin"
            and other.feature not in used
            and other.diameter > axis.diameter + 2.0 * tolerance
            and axis.collinear(other, max(tolerance, axis.diameter * 0.05))
            and abs(axis.along(other.point)) <= axis.depth / 2.0 + tolerance
        ]
        if len(ribs) < 3:
            continue
        diameters = sorted({round(rib.diameter, 2) for rib in ribs})
        used.add(axis.feature)
        used.update(rib.feature for rib in ribs)
        roles: list[tuple[FeatureId, GroupRole]] = [(axis.feature, "passage")]
        roles.extend((rib.feature, "rib") for rib in ribs)
        groups.append(
            FunctionalGroup(
                kind="channel",
                variant="passage",
                anchor=axis.feature,
                members=tuple(member for member, _role in roles),
                roles=tuple(roles),
                measures=(
                    GroupMeasure("diameter", axis.diameter, "mm"),
                    GroupMeasure("length", axis.depth, "mm"),
                    GroupMeasure("ribs", float(len(ribs)), ""),
                    GroupMeasure("rib_diameter", diameters[-1], "mm"),
                ),
                evidence="ribbed_passage",
                count=len(ribs),
            )
        )
    return groups


# --- Bajonett und Rastung ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Piece:
    """Eine kleine Fläche um eine Achse, in Zylinderkoordinaten."""

    feature: FeatureId
    area: float
    radius: float
    height: float
    angle: float
    radial: float
    tangential: float
    axial: float
    centre: Vec


def _closures(features: Mapping[FeatureId, Feature], tolerance: float) -> list[FunctionalGroup]:
    """Gleiche Stücke aus kleinen Flächen, drei- bis sechsmal um eine Rundachse.

    Gelesen wird je Achse eines Rundmerkmals: Die kleinen Flächen im Bereich
    ihrer Durchmesser werden zu **Stücken** gebündelt — was nahe beieinander
    liegt, ist eine Nocke, ein Weg oder eine Mulde. Ein Verschluss sind drei
    bis sechs Stücke auf demselben Radius und derselben Höhe, jedes aus
    **mindestens zwei Flächen**: Eine Nocke hat Oberseite und Flanken, ein
    Drehweg Boden und Dach, eine Mulde Grund und Seiten. Eine einzelne
    wiederholte Fläche ist noch kein Verschluss (Audit §7).

    Bajonett heißt es, wenn die Stücke gleichmäßig verteilt und gleich groß
    sind und jedes eine Fläche quer zur Achse trägt, die über den Rundkörper
    hinaussteht, in seine Wand hineinreicht oder Boden und Dach eines Wegs
    zeigt. Sonst ist es eine Rastung — deren Stellungen dürfen ungleich
    verteilt und verschieden breit sein (Gewürzdeckel: 0°, 122,5°, 240°).
    """
    axes = [axis for axis in _round_axes(features) if axis.kind in ("hole", "pin")]
    seen_axes: list[_Axis] = []
    groups: list[FunctionalGroup] = []
    used: set[FeatureId] = set()
    planes = _Planes.of(features)
    fillets = [
        (name, features[name])
        for name in sorted(features, key=_id_key)
        if features[name].kind == "fillet" and features[name].params.get("recess")
    ]
    for axis in axes:
        if any(axis.collinear(other, tolerance) for other in seen_axes):
            continue
        seen_axes.append(axis)
        coaxial = [other for other in axes if other.collinear(axis, tolerance)]
        largest = max(other.diameter for other in coaxial) / 2.0
        smallest = min(other.diameter for other in coaxial) / 2.0
        # **Die Toleranz eines Rings misst sich an seinem Rundkörper, nicht an
        # der Platte**: Auf einem Druckbett mit zwölf Deckeln (300 mm
        # Diagonale) lagen Rastfedern 5 mm neben der Achse unter viermal der
        # Plattentoleranz, und Klötze auf 6,5 bis 14 mm galten als „ein
        # Radius“. Allein gelesen hatte dasselbe Teil die richtige Rastung.
        near = min(tolerance, match_tolerance(2.0 * largest))
        # **Und ein Verschluss sitzt am Rundkörper, nicht irgendwo auf seiner
        # Achse**: Was entlang der Achse weiter vom Körper entfernt liegt, als
        # zwei Flächen einer Nocke auseinander sein dürfen (``_lumps``), gehört
        # nicht dazu — am Eiffelturm hätten sonst die vier Streben 10 mm unter
        # der Spitzenbohrung eine Rastung ergeben.
        reach = max(4.0 * near, 0.2 * largest)
        spans = [
            (
                axis.along(other.point) - other.depth / 2.0,
                axis.along(other.point) + other.depth / 2.0,
            )
            for other in coaxial
        ]
        span = (min(low for low, _high in spans) - reach, max(high for _low, high in spans) + reach)
        pieces = _pieces_around(axis, planes, used, largest, near, span)
        group = _rotational_group(axis, pieces, smallest, largest, near)
        if group is None:
            mantles = [other.diameter / 2.0 for other in coaxial]
            group = _round_notches(axis, fillets, used, mantles, near, span)
        if group is not None:
            used.update(group.members)
            groups.append(group)
    return groups


@dataclass(frozen=True, slots=True)
class _Planes:
    """Die ebenen Flächen eines Körpers, einmal gelesen — nach Nummer geordnet.

    Je Fläche Name, Mitte, Normale und Inhalt als Zahlen und dieselben Werte
    als Felder: Die Felder sieben vor (eine Obermenge mit Zugabe), die Zahlen
    entscheiden — so bleibt jede Antwort dieselbe wie aus der Schleife über
    alle Merkmale.
    """

    names: tuple[FeatureId, ...]
    centres: tuple[Vec, ...]
    normals: tuple[Vec, ...]
    areas: tuple[float, ...]
    centre_array: np.ndarray
    normal_array: np.ndarray
    area_array: np.ndarray

    @classmethod
    def of(cls, features: Mapping[FeatureId, Feature]) -> _Planes:
        rows = [
            (name, centre, normal, area)
            for name in sorted(features, key=_id_key)
            if features[name].kind == "face"
            and (centre := _vector(features[name].params.get("centre"))) is not None
            and (normal := _unit(features[name].params.get("normal"))) is not None
            and (area := _number(features[name], "area")) is not None
        ]
        return cls(
            names=tuple(row[0] for row in rows),
            centres=tuple(row[1] for row in rows),
            normals=tuple(row[2] for row in rows),
            areas=tuple(row[3] for row in rows),
            centre_array=np.asarray([row[1] for row in rows], dtype=np.float64).reshape(-1, 3),
            normal_array=np.asarray([row[2] for row in rows], dtype=np.float64).reshape(-1, 3),
            area_array=np.asarray([row[3] for row in rows], dtype=np.float64),
        )


def _pieces_around(
    axis: _Axis,
    planes: _Planes,
    used: set[FeatureId],
    largest: float,
    tolerance: float,
    span: tuple[float, float],
) -> list[_Piece]:
    """Die kleinen ebenen Flächen neben der Achse, in Zylinderkoordinaten.

    Klein heißt: höchstens ein Zwanzigstel der Mantelfläche des größten
    Rundkörpers auf der Achse — Nocken, Wege und Mulden, nicht Boden und
    Deckel. Neben heißt auch: innerhalb ``span`` entlang der Achse.
    """
    reference = plane_axes(axis.direction)
    if reference is None:
        return []
    first, second = reference
    biggest = math.pi * 2.0 * largest * max(axis.depth, largest) / 20.0
    pieces: list[_Piece] = []
    if not planes.names:
        return pieces
    # Vorsieb über alle Flächen zugleich, mit Zugabe — entschieden wird unten
    # an denselben Zahlen wie zuvor.
    relative_all = planes.centre_array - np.asarray(axis.point, dtype=np.float64)
    along_all = (
        relative_all[:, 0] * axis.direction[0]
        + relative_all[:, 1] * axis.direction[1]
        + relative_all[:, 2] * axis.direction[2]
    )
    across_all = relative_all - along_all[:, None] * np.asarray(axis.direction, dtype=np.float64)
    radius_all = np.sqrt(
        across_all[:, 0] * across_all[:, 0]
        + across_all[:, 1] * across_all[:, 1]
        + across_all[:, 2] * across_all[:, 2]
    )
    slack = 1e-9 * max(1.0, largest, abs(span[0]), abs(span[1]))
    near = np.flatnonzero(
        (planes.area_array <= biggest * (1.0 + 1e-12))
        & (radius_all > 4.0 * tolerance - slack)
        & (radius_all <= largest * 1.25 + tolerance + slack)
        & (along_all >= span[0] - slack)
        & (along_all <= span[1] + slack)
    )
    for position in near.tolist():
        name = planes.names[position]
        if name in used:
            continue
        centre = planes.centres[position]
        normal = planes.normals[position]
        area = planes.areas[position]
        if area > biggest:
            continue
        relative = _sub(centre, axis.point)
        height = _dot(relative, axis.direction)
        across = _sub(relative, _scaled(axis.direction, height))
        radius = _length(across)
        if radius <= 4.0 * tolerance or radius > largest * 1.25 + tolerance:
            continue
        if not span[0] <= height <= span[1]:
            continue
        outward = _scaled(across, 1.0 / radius)
        sideways = (
            axis.direction[1] * outward[2] - axis.direction[2] * outward[1],
            axis.direction[2] * outward[0] - axis.direction[0] * outward[2],
            axis.direction[0] * outward[1] - axis.direction[1] * outward[0],
        )
        angle = exact_atan2_degrees(_dot(across, second), _dot(across, first))
        pieces.append(
            _Piece(
                feature=name,
                area=area,
                radius=radius,
                height=height,
                angle=angle % 360.0,
                radial=_dot(normal, outward),
                tangential=_dot(normal, sideways),
                axial=_dot(normal, axis.direction),
                centre=centre,
            )
        )
    return pieces


@dataclass(frozen=True, slots=True)
class _Lump:
    """Benachbarte kleine Flächen: eine Nocke, ein Weg, eine Mulde."""

    pieces: tuple[_Piece, ...]
    angle: float
    span: float
    radius: float
    height: float
    area: float


def _rotational_group(
    axis: _Axis,
    pieces: list[_Piece],
    smallest: float,
    largest: float,
    tolerance: float,
) -> FunctionalGroup | None:
    """Die Stücke, die sich auf einem Ring um die Achse wiederholen — oder keine."""
    lumps = [
        lump
        for lump in _lumps(_without_patterns(pieces, tolerance), largest, tolerance)
        if len(lump.pieces) >= 2 and lump.span <= 90.0
    ]
    ring = _largest_ring(lumps, tolerance)
    count = len(ring)
    if not MIN_CLOSURE_POSITIONS <= count <= MOST_CLOSURE_POSITIONS:
        return None
    ordered = sorted(ring, key=lambda lump: lump.angle)
    pitch = 360.0 / count
    steps = [later.angle - earlier.angle for earlier, later in pairwise(ordered)]
    steps.append(ordered[0].angle + 360.0 - ordered[-1].angle)
    even = all(abs(step - pitch) <= STATION_SPACING_DEGREES for step in steps)
    areas = [lump.area for lump in ordered]
    alike = max(areas) <= (1.0 + STATION_AREA_SPREAD) * min(areas)
    every_axial = all(
        any(abs(piece.axial) >= FLOOR_ALIGNED for piece in lump.pieces) for lump in ordered
    )
    outward = any(
        piece.radial >= 0.9 and piece.radius >= largest - tolerance
        for lump in ordered
        for piece in lump.pieces
    )
    inward = any(
        piece.radial <= -0.9 and piece.radius <= smallest + tolerance
        for lump in ordered
        for piece in lump.pieces
    )
    roof = all(_floor_and_roof(lump.pieces) for lump in ordered)
    bayonet = even and alike and every_axial and (outward or inward or roof)
    members = tuple(
        piece.feature
        for lump in ordered
        for piece in sorted(lump.pieces, key=lambda entry: _id_key(entry.feature))
    )
    # Keine „Höhe“: Die Spanne der Flächenmitten entlang der Achse ist weder
    # die Höhe einer Nocke noch die eines Wegs (am Kartuschendeckel 0,25 mm
    # bei 0,6 mm hohen Nocken) — eine Zahl, die etwas anderes misst, als ihr
    # Name sagt, steht nicht da.
    measures = [
        GroupMeasure("count", float(count), ""),
        GroupMeasure("radius", max(lump.radius for lump in ordered), "mm"),
    ]
    if even:
        measures.insert(1, GroupMeasure("spacing", pitch, "°"))
    return FunctionalGroup(
        kind="closure",
        variant="bayonet" if bayonet else "detent",
        anchor=axis.feature,
        members=(axis.feature, *members),
        roles=(
            (axis.feature, "core"),
            *((member, "lug" if bayonet else "notch") for member in members),
        ),
        measures=tuple(measures),
        evidence="rotational_lugs" if bayonet else "rotational_notches",
        count=count,
    )


def _round_notches(
    axis: _Axis,
    fillets: Sequence[tuple[FeatureId, Feature]],
    used: set[FeatureId],
    mantles: Sequence[float],
    tolerance: float,
    span: tuple[float, float],
) -> FunctionalGroup | None:
    """Gleiche runde Rastmulden in einem Mantel der Achse — eine Rastung.

    Eine Mulde ist eine eingetiefte Rundung (``fillet`` mit ``recess``),
    parallel zur Achse, deren Mitte nicht weiter als ihr eigener Radius vom
    Mantel eines Rundkörpers derselben Achse liegt: Der Kragen des
    Gewürzdeckels trägt drei davon (Korpus ``recognition_spice_base``: R 1,1
    auf r 16 im Innenmantel r 16,4). Eine Mulde ist eine einzige Rundfläche
    und damit kein Stück aus mehreren Flächen wie bei :func:`_rotational_group`;
    die Gruppe verlangt dafür gleiche Mulden — gleicher Radius, gleicher
    Abstand zur Achse — in drei bis sechs Stellungen. Mehr sind ein Rändel.
    """
    reference = plane_axes(axis.direction)
    if reference is None or not mantles:
        return None
    first, second = reference
    found: list[tuple[FeatureId, float, float, float]] = []
    for name, feature in fillets:
        if name in used:
            continue
        direction = _unit(feature.params.get("axis"))
        centre = _vector(feature.params.get("centre"))
        size = _number(feature, "radius")
        if direction is None or centre is None or size is None:
            continue
        if abs(_dot(direction, axis.direction)) < FLOOR_ALIGNED:
            continue
        relative = _sub(centre, axis.point)
        height = _dot(relative, axis.direction)
        if not span[0] <= height <= span[1]:
            continue
        across = _sub(relative, _scaled(axis.direction, height))
        radius = _length(across)
        if radius <= 4.0 * tolerance:
            continue
        if not any(abs(radius - mantle) <= size + tolerance for mantle in mantles):
            continue
        angle = exact_atan2_degrees(_dot(across, second), _dot(across, first)) % 360.0
        found.append((name, angle, radius, size))
    best: list[tuple[FeatureId, float, float, float]] = []
    for _name, _angle, radius, size in found:
        alike = [
            entry
            for entry in found
            if abs(entry[3] - size) <= max(tolerance, 0.02 * size)
            and abs(entry[2] - radius) <= max(4.0 * tolerance, 0.03 * radius)
        ]
        if len(alike) > len(best):
            best = alike
    count = len(best)
    if not MIN_CLOSURE_POSITIONS <= count <= MOST_CLOSURE_POSITIONS:
        return None
    ordered = sorted(best, key=lambda entry: entry[1])
    pitch = 360.0 / count
    steps = [later[1] - earlier[1] for earlier, later in pairwise(ordered)]
    steps.append(ordered[0][1] + 360.0 - ordered[-1][1])
    even = all(abs(step - pitch) <= STATION_SPACING_DEGREES for step in steps)
    measures = [
        GroupMeasure("count", float(count), ""),
        GroupMeasure("radius", sum(entry[2] for entry in ordered) / count, "mm"),
    ]
    if even:
        measures.insert(1, GroupMeasure("spacing", pitch, "°"))
    notches = tuple(sorted((entry[0] for entry in ordered), key=_id_key))
    return FunctionalGroup(
        kind="closure",
        variant="detent",
        anchor=axis.feature,
        members=(axis.feature, *notches),
        roles=((axis.feature, "core"), *((member, "notch") for member in notches)),
        measures=tuple(measures),
        evidence="rotational_notches",
        count=count,
    )


def _without_patterns(pieces: Sequence[_Piece], tolerance: float) -> list[_Piece]:
    """Ohne Flächen, die sich öfter als ein Verschluss wiederholen.

    Gleiche Flächen (Fläche auf zwei Prozent, Lage und Richtung im Zylinder)
    in mehr als :data:`MOST_CLOSURE_POSITIONS` Exemplaren sind ein Muster —
    die 51 Schlitze des Filterkäfigs, ein Rändel, ein Lochkreis. Sie würden die
    Nocken eines Verschlusses daneben über ihre Nachbarschaft zu einem Ring
    verbinden.
    """
    classes: list[list[_Piece]] = []
    for piece in sorted(pieces, key=lambda entry: (-entry.area, _id_key(entry.feature))):
        for members in classes:
            model = members[0]
            if (
                abs(piece.area - model.area) <= 0.02 * model.area
                and abs(piece.radius - model.radius) <= tolerance
                and abs(piece.height - model.height) <= tolerance
                and abs(piece.radial - model.radial) <= 0.02
                and abs(abs(piece.tangential) - abs(model.tangential)) <= 0.02
                and abs(piece.axial - model.axial) <= 0.02
            ):
                members.append(piece)
                break
        else:
            classes.append([piece])
    return [
        piece
        for members in classes
        if len(members) <= MOST_CLOSURE_POSITIONS * 2
        for piece in members
    ]


def _lumps(pieces: Sequence[_Piece], largest: float, tolerance: float) -> list[_Lump]:
    """Flächen, deren Mitten nahe beieinander liegen, als ein Stück.

    Nahe heißt: höchstens ein Fünftel des Radius auseinander, wenigstens vier
    Modelltoleranzen. Die Flächen einer Nocke liegen wenige Millimeter
    zusammen, zwei Nocken auf 120 Grad weit auseinander; die 51 Schlitze des
    Filterkäfigs hängen über ihre Nachbarn zu einem Ring zusammen und fallen
    an ihrer Spanne heraus.
    """
    if not pieces:
        return []
    link = max(4.0 * tolerance, 0.2 * largest)
    parent = list(range(len(pieces)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for first in range(len(pieces)):
        for second in range(first + 1, len(pieces)):
            if _length(_sub(pieces[first].centre, pieces[second].centre)) <= link:
                root_a, root_b = find(first), find(second)
                if root_a != root_b:
                    parent[max(root_a, root_b)] = min(root_a, root_b)
    bundles: dict[int, list[_Piece]] = {}
    for index, piece in enumerate(pieces):
        bundles.setdefault(find(index), []).append(piece)
    lumps: list[_Lump] = []
    for members in bundles.values():
        weight = sum(piece.area for piece in members)
        reference = members[0].angle
        offsets = [_signed_angle(piece.angle, reference) for piece in members]
        centre_angle = (
            (reference + sum(o * p.area for o, p in zip(offsets, members, strict=True)) / weight)
            % 360.0
            if weight > 0.0
            else reference
        )
        spread = [_signed_angle(piece.angle, centre_angle) for piece in members]
        lumps.append(
            _Lump(
                pieces=tuple(sorted(members, key=lambda entry: _id_key(entry.feature))),
                angle=centre_angle,
                span=max(spread) - min(spread),
                radius=sum(piece.radius * piece.area for piece in members) / weight
                if weight > 0.0
                else 0.0,
                height=sum(piece.height * piece.area for piece in members) / weight
                if weight > 0.0
                else 0.0,
                area=weight,
            )
        )
    return sorted(lumps, key=lambda lump: (lump.angle, lump.pieces[0].feature))


def _largest_ring(lumps: Sequence[_Lump], tolerance: float) -> list[_Lump]:
    """Die meisten Stücke auf gleichem Radius und gleicher Höhe."""
    best: list[_Lump] = []
    for lump in lumps:
        reach = max(4.0 * tolerance, 0.03 * lump.radius)
        ring = [
            other
            for other in lumps
            if abs(other.radius - lump.radius) <= reach and abs(other.height - lump.height) <= reach
        ]
        if len(ring) > len(best):
            best = ring
    return best


def _floor_and_roof(pieces: Sequence[_Piece]) -> bool:
    """Boden und Dach eines Drehwegs: Querflächen, die einander ansehen."""
    axial = [piece.axial for piece in pieces if abs(piece.axial) >= FLOOR_ALIGNED]
    return any(value > 0 for value in axial) and any(value < 0 for value in axial)


def _signed_angle(angle: float, centre: float) -> float:
    difference = (angle - centre) % 360.0
    return difference - 360.0 if difference > 180.0 else difference


# --- Kammer, Tasche, Nut, Kanal ---------------------------------------------


@dataclass(slots=True)
class _Surface:
    """Das Netz als Dreiecke mit Nachbarschaft und Kantenknick — einmal je Körper.

    ``neighbours``/``convex`` stehen je Dreieck in einem Stück (CSR):
    ``starts[t]`` bis ``starts[t + 1]``. Konvex heißt, die Oberfläche knickt
    von außen gesehen nach außen weg — dort endet eine Kammer. Gemessen wird
    der Abstand der fremden Ecke zur eigenen Ebene, in beiden Richtungen; ist
    einer davon deutlich negativ, gilt die Kante als konvex.
    """

    points: np.ndarray
    corner_ids: np.ndarray
    normals: np.ndarray
    areas: np.ndarray
    starts: np.ndarray
    neighbours: np.ndarray
    convex: np.ndarray
    lengths: np.ndarray
    owner: dict[int, FeatureId]

    @classmethod
    def of(cls, mesh: MeshData) -> _Surface:
        body = mesh.raw
        vertices = np.asarray(body.vertices, dtype=np.float64)
        faces = np.asarray(body.faces, dtype=np.int64)
        normals, areas = stable_normals(body)
        normals = np.asarray(normals, dtype=np.float64)
        areas = np.asarray(areas, dtype=np.float64)
        count = len(faces)
        edges = np.stack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=1).reshape(
            -1, 2
        )
        ordered = np.sort(edges, axis=1)
        width = int(vertices.shape[0]) + 1
        codes = ordered[:, 0] * width + ordered[:, 1]
        order = np.argsort(codes, kind="stable")
        sorted_codes = codes[order]
        same_next = sorted_codes[1:] == sorted_codes[:-1]
        starts_of_run = np.flatnonzero(np.concatenate(([True], ~same_next)))
        run_lengths = np.diff(np.concatenate((starts_of_run, [len(order)])))
        pairs_at = starts_of_run[run_lengths == 2]
        first = order[pairs_at] // 3
        second = order[pairs_at + 1] // 3
        edge_vertices = ordered[order[pairs_at]]
        convex_pair = _convex_pairs(vertices, faces, normals, first, second, edge_vertices)
        keep = first != second
        first, second, convex_pair = first[keep], second[keep], convex_pair[keep]
        edge_vertices = edge_vertices[keep]
        delta = vertices[edge_vertices[:, 1]] - vertices[edge_vertices[:, 0]]
        edge_length = np.sqrt(
            delta[:, 0] * delta[:, 0] + delta[:, 1] * delta[:, 1] + delta[:, 2] * delta[:, 2]
        )
        sources = np.concatenate((first, second))
        targets = np.concatenate((second, first))
        flags = np.concatenate((convex_pair, convex_pair))
        spans = np.concatenate((edge_length, edge_length))
        sort = np.argsort(sources, kind="stable")
        sources, targets, flags, spans = sources[sort], targets[sort], flags[sort], spans[sort]
        starts = np.searchsorted(sources, np.arange(count + 1), side="left").astype(np.int64)
        return cls(
            points=vertices,
            corner_ids=faces,
            normals=normals,
            areas=areas,
            starts=starts,
            neighbours=targets.astype(np.int64),
            convex=flags.astype(bool),
            lengths=spans.astype(np.float64),
            owner={},
        )

    def around(self, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Nachbarn der Dreiecke: (von, nach, konvex) als flache Felder."""
        positions = self._positions(triangles)
        sources = np.repeat(triangles, self.starts[triangles + 1] - self.starts[triangles])
        return sources, self.neighbours[positions], self.convex[positions]

    def enclosure(
        self, floor: np.ndarray, region: np.ndarray, holes: np.ndarray | None = None
    ) -> float:
        """Welcher Anteil des Bodenrands an Wänden des Bereichs liegt — nach Länge.

        Eine Kammer und eine Nut sind ringsum von Wand umgeben, ein Kanal an zwei
        langen Seiten; ein Ring mit ein paar Buckeln darauf (Rastkragen) ist es
        kaum, und eine Stirnfläche mit angrenzenden Schlitzflanken auch nicht.

        ``holes`` nennt die Dreiecke von Bohrungen und Langlöchern: Ihre Ränder
        im Boden sind Löcher im Boden, keine Öffnung der Kammer (Besteckkorb:
        zwölf Ablauflöcher je Fach).
        """
        positions = self._positions(floor)
        targets = self.neighbours[positions]
        inside_floor = np.zeros(len(self.corner_ids), dtype=bool)
        inside_floor[floor] = True
        in_region = np.zeros(len(self.corner_ids), dtype=bool)
        in_region[region] = True
        outward = ~inside_floor[targets]
        if holes is not None:
            outward &= ~holes[targets]
        total = float(self.lengths[positions][outward].sum())
        if total <= EPS_GEOM:
            return 0.0
        walled = outward & in_region[targets] & ~self.convex[positions]
        return float(self.lengths[positions][walled].sum()) / total

    def unbent_share(self, floor: np.ndarray, holes: np.ndarray) -> float:
        """Der Anteil des Bodenrands, an dem die Fläche nicht nach außen knickt.

        Die obere Schranke von :meth:`enclosure` — dieselbe Rechnung mit allen
        Dreiecken als Bereich. Liegt sie unter einer Schwelle, liegt jede
        Umschließung darunter.
        """
        positions = self._positions(floor)
        if not positions.size:
            return 0.0
        targets = self.neighbours[positions]
        outward = ~np.isin(targets, floor) & ~holes[targets]
        total = float(self.lengths[positions][outward].sum())
        if total <= EPS_GEOM:
            return 0.0
        unbent = outward & ~self.convex[positions]
        return float(self.lengths[positions][unbent].sum()) / total

    def _positions(self, triangles: np.ndarray) -> np.ndarray:
        starts = self.starts[triangles]
        counts = self.starts[triangles + 1] - starts
        total = int(counts.sum())
        if not total:
            return np.zeros(0, dtype=np.int64)
        offsets = np.repeat(starts - np.concatenate(([0], np.cumsum(counts)[:-1])), counts)
        return np.asarray(np.arange(total, dtype=np.int64) + offsets, dtype=np.int64)


def _convex_pairs(
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray,
    first: np.ndarray,
    second: np.ndarray,
    edge_vertices: np.ndarray,
) -> np.ndarray:
    """Ob die Kante zwischen zwei Dreiecken nach außen knickt — elementweise."""
    span = max(float(np.max(vertices.max(axis=0) - vertices.min(axis=0))), 1.0)
    tolerance = max(1e-4, 1e-6 * span)
    opposite_second = faces[second].sum(axis=1) - edge_vertices.sum(axis=1)
    opposite_first = faces[first].sum(axis=1) - edge_vertices.sum(axis=1)
    origin = vertices[edge_vertices[:, 0]]
    towards_second = vertices[opposite_second] - origin
    towards_first = vertices[opposite_first] - origin
    lean_second = (towards_second * normals[first]).sum(axis=1)
    lean_first = (towards_first * normals[second]).sum(axis=1)
    return np.asarray((lean_second < -tolerance) | (lean_first < -tolerance))


#: Je Dreieck sein Kästchen quer zu einer Strahlrichtung: die beiden Achsen
#: quer zu ihr, je Achse kleinste und größte Lage, die höchste Lage entlang
#: der Richtung und die Zugabe gegen Rundung (:meth:`_Lookup.boxes`).
_Boxes = tuple[Vec, Vec, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]


@dataclass(slots=True)
class _Lookup:
    """Was die Kammersuche je Körper einmal nachschlägt, statt es je Boden zu rechnen.

    ``owner_id`` nennt je Dreieck den Platz seines Merkmals in ``names`` (-1:
    keines; bei zweien das erste nach Nummer, wie :func:`_triangle_owner`),
    ``face_owned`` und ``holes`` die Dreiecke ebener Flächen und der Bohrungen,
    Langlöcher, Kegel und Muster, ``centres`` die Dreiecksmitten. ``marks`` und
    ``own`` sind Merkfelder: Wer sie setzt, setzt sie zurück.
    """

    names: list[FeatureId]
    index_of: dict[FeatureId, int]
    owner_id: np.ndarray
    face_owned: np.ndarray
    holes: np.ndarray
    centres: np.ndarray
    marks: np.ndarray
    own: np.ndarray
    rays: dict[Vec, _Boxes | None]

    @classmethod
    def of(cls, features: Mapping[FeatureId, Feature], surface: _Surface) -> _Lookup:
        count = len(surface.corner_ids)
        names = sorted(features, key=_id_key)
        index_of = {name: position for position, name in enumerate(names)}
        owner_id = np.full(count, -1, dtype=np.int64)
        for index, name in _triangle_owner(features).items():
            if 0 <= index < count:
                owner_id[index] = index_of[name]
        kinds = [features[name].kind for name in names]
        is_face = np.asarray([kind == "face" for kind in kinds] + [False], dtype=bool)
        is_hole = np.asarray(
            [kind in ("hole", "slot", "cone", "pattern") for kind in kinds] + [False], dtype=bool
        )
        # Der Platz -1 zeigt auf den angehängten letzten Eintrag: kein Merkmal.
        return cls(
            names=names,
            index_of=index_of,
            owner_id=owner_id,
            face_owned=is_face[owner_id],
            holes=is_hole[owner_id],
            centres=surface.points[surface.corner_ids].mean(axis=1),
            marks=np.zeros(count, dtype=bool),
            own=np.zeros(count, dtype=bool),
            rays={},
        )

    def owner_of(self, triangle: int) -> FeatureId | None:
        index = int(self.owner_id[triangle])
        return self.names[index] if index >= 0 else None

    def boxes(self, surface: _Surface, direction: Vec) -> _Boxes | None:
        """Je Dreieck sein Kästchen quer zur Richtung und seine höchste Lage entlang ihr.

        Einmal je Richtung — die Böden eines Körpers teilen meist wenige.
        ``margin`` ist großzügig gegen jede Rundung: Ein Dreieck, dessen
        Kästchen den Strahl um mehr verfehlt, trifft ihn auch genau gerechnet
        nicht.
        """
        if direction in self.rays:
            return self.rays[direction]
        frame = plane_axes(direction)
        if frame is None:
            self.rays[direction] = None
            return None
        first, second = frame
        points = surface.points
        along_u = points[:, 0] * first[0] + points[:, 1] * first[1] + points[:, 2] * first[2]
        along_v = points[:, 0] * second[0] + points[:, 1] * second[1] + points[:, 2] * second[2]
        along_h = (
            points[:, 0] * direction[0] + points[:, 1] * direction[1] + points[:, 2] * direction[2]
        )
        corners = surface.corner_ids
        u = along_u[corners]
        v = along_v[corners]
        h = along_h[corners]
        scale = float(np.abs(points).max()) if len(points) else 1.0
        margin = 1e-6 * max(1.0, scale)
        answer: _Boxes = (
            first,
            second,
            u.min(axis=1),
            u.max(axis=1),
            v.min(axis=1),
            v.max(axis=1),
            h.max(axis=1),
            margin,
        )
        self.rays[direction] = answer
        return answer


@dataclass(frozen=True, slots=True)
class _Region:
    """Was von einem Boden aus ohne Außenknick erreichbar ist."""

    floor: FeatureId
    triangles: np.ndarray
    other_floors: frozenset[FeatureId]
    normal: Vec
    origin: Vec
    ceiling: float
    """Fläche der Gegenflächen, die dem Boden zugewandt am Bereich anliegen."""


def _chambers(
    features: Mapping[FeatureId, Feature],
    surface: _Surface,
    tolerance: float,
    cancelled: CancelToken | None,
) -> list[FunctionalGroup]:
    """Kammer, Tasche, Nut und Kanal — ein Boden und die Wände um ihn.

    Vom Boden aus wird über Kanten gewandert, die nicht nach außen knicken; ein
    Dreieck, das zum Boden zurückschaut (Decke, Hinterschnitt), beendet den Weg,
    ebenso ein zweiter Boden auf **derselben** Höhe — dort beginnt eine
    Nachbarkammer, und die Wände dazwischen gehören beiden (``shared``). Was die
    Wanderung erreicht, wird nach seinen Seiten beurteilt: vier Seiten sind eine
    Kammer, zwei gegenüberliegende ein Kanal, ein Boden mit Loch und Wänden
    nach innen und außen eine Nut.
    """
    lookup = _Lookup.of(features, surface)
    floors = [
        name
        for name in sorted(
            features, key=lambda key: (-(_number(features[key], "area") or 0.0), _id_key(key))
        )
        if features[name].kind == "face"
        and (_number(features[name], "area") or 0.0) >= MIN_FLOOR_AREA
        and _unit(features[name].params.get("normal")) is not None
        and features[name].face_indices
    ]
    # **Jeder Boden wandert, und gewählt wird nach Rang, nicht nach Fläche.**
    # Eine Innenwand ist größer als der Boden darunter und wandert über ihn
    # hinweg; als Boden gelesen wird sie höchstens eine offene Tasche, der
    # wirkliche Boden eine geschlossene Kammer (1x1-bin). Überdecken sich zwei
    # Bereiche, gewinnt die geschlossenere Form, dann der größere Boden.
    candidates: list[tuple[int, float, str, FunctionalGroup, np.ndarray]] = []
    for name in floors:
        _check(cancelled)
        triangles = np.asarray(features[name].face_indices, dtype=np.int64)
        if triangles.size == 0 or triangles.max() >= len(surface.corner_ids):
            continue
        # **Erst der Rand, dann die Wanderung.** Was die Bewertung als
        # Umschließung zählt, ist nie mehr als der Anteil des Bodenrands, an dem
        # die Fläche nicht nach außen knickt — liegt schon der unter dem
        # kleinsten Maß, das eine Kammer, eine Nut oder ein Kanal verlangt,
        # wird nicht gewandert. Eine Schranke, keine Schätzung: Kein Boden fällt
        # hier heraus, der später eine Gruppe ergäbe.
        if surface.unbent_share(triangles, lookup.holes) < ENCLOSED_TROUGH:
            continue
        region = _flood(name, features[name], triangles, surface, lookup, tolerance)
        if region is None:
            continue
        group = _judged(region, features, surface, lookup, tolerance)
        if group is None:
            continue
        area = float(surface.areas[triangles].sum())
        candidates.append((_CHAMBER_RANK[group.variant], area, name, group, region.triangles))
    candidates.sort(key=lambda entry: (-entry[0], -entry[1], _id_key(entry[2])))
    claimed = np.zeros(len(surface.corner_ids), dtype=bool)
    groups: list[FunctionalGroup] = []
    for _rank, _area, _name, group, triangles in candidates:
        if claimed[triangles].any():
            continue
        groups.append(group)
        claimed[triangles] = True
    return groups


#: Wie geschlossen eine Form ist — die geschlossenere gewinnt eine Überdeckung.
_CHAMBER_RANK: Final[dict[str, int]] = {
    "closed": 6,
    "ring": 6,
    "groove": 5,
    "open_rim": 4,
    "trough": 3,
    "open_side": 2,
}


def _triangle_owner(features: Mapping[FeatureId, Feature]) -> dict[int, FeatureId]:
    owner: dict[int, FeatureId] = {}
    for name in sorted(features, key=_id_key):
        for index in features[name].face_indices:
            owner.setdefault(int(index), name)
    return owner


def _flood(
    name: FeatureId,
    floor: Feature,
    triangles: np.ndarray,
    surface: _Surface,
    lookup: _Lookup,
    tolerance: float,
) -> _Region | None:
    """Was vom Boden aus ohne Außenknick erreichbar ist — gerechnet nur am Bereich.

    Ausrichtung und Höhe je Dreieck entstehen an der Front der Wanderung, nicht
    für den ganzen Körper; die Merkfelder (``lookup.marks``, ``lookup.own``)
    setzt sie am Ende zurück. Elementweise dieselbe Rechnung wie über alle
    Dreiecke — dieselben Bereiche.
    """
    normal = _unit(floor.params.get("normal"))
    if normal is None:
        return None
    corners = surface.points[surface.corner_ids[triangles]].reshape(-1, 3)
    origin_array = corners.mean(axis=0)
    origin = (float(origin_array[0]), float(origin_array[1]), float(origin_array[2]))
    normals = surface.normals
    centres = lookup.centres
    # **Ein zweiter Boden ist eine ebene Fläche auf derselben Höhe**, nicht
    # jedes flache Dreieck: Die ersten Facetten einer Bodenrundung zeigen fast
    # nach oben und liegen unter der Modelltoleranz über dem Boden — als
    # „Nachbarboden" gelesen, hielten sie die Wanderung am Bodenrand an
    # (1x1-bin: keine Kammer). Dieselbe Höhe heißt bis auf ein Zwanzigstel
    # Millimeter, nicht bis auf die Zuordnungstoleranz.
    level = min(tolerance, SAME_LEVEL)
    floor_index = lookup.index_of.get(name, -1)
    marks = lookup.marks
    own = lookup.own
    reached: list[np.ndarray] = [triangles]
    facing_back: list[np.ndarray] = []
    others: set[FeatureId] = set()
    marks[triangles] = True
    own[triangles] = True
    try:
        frontier = triangles
        while frontier.size:
            _sources, targets, convex = surface.around(frontier)
            facing = (
                normals[targets, 0] * normal[0]
                + normals[targets, 1] * normal[1]
                + normals[targets, 2] * normal[2]
            )
            facing_back.append(targets[facing <= -FLOOR_ALIGNED])
            keep = ~convex & ~marks[targets]
            fresh = targets[keep]
            facing = facing[keep]
            heights = (
                (centres[fresh, 0] - origin[0]) * normal[0]
                + (centres[fresh, 1] - origin[1]) * normal[1]
                + (centres[fresh, 2] - origin[2]) * normal[2]
            )
            same_floor = (
                (facing >= FLOOR_ALIGNED)
                & (np.abs(heights) <= level)
                & lookup.face_owned[fresh]
                & (lookup.owner_id[fresh] != floor_index)
            )
            foreign = same_floor & ~own[fresh]
            for index in np.unique(fresh[foreign]).tolist():
                neighbour = lookup.owner_of(int(index))
                if neighbour is not None and neighbour != name:
                    others.add(neighbour)
            fresh = np.unique(fresh[(facing >= FACING_BACK) & ~foreign])
            marks[fresh] = True
            reached.append(fresh)
            frontier = fresh
        region = np.unique(np.concatenate(reached))
    finally:
        for touched in reached:
            marks[touched] = False
        own[triangles] = False
    if region.size == triangles.size:
        return None
    ceiling = np.unique(np.concatenate(facing_back)) if facing_back else region[:0]
    return _Region(
        name, region, frozenset(others), normal, origin, float(surface.areas[ceiling].sum())
    )


def _judged(
    region: _Region,
    features: Mapping[FeatureId, Feature],
    surface: _Surface,
    lookup: _Lookup,
    tolerance: float,
) -> FunctionalGroup | None:
    """Ob das Erreichte eine Kammer, eine Nut oder ein Kanal ist — oder nichts."""
    normal = region.normal
    triangles = region.triangles
    normals = surface.normals[triangles]
    areas = surface.areas[triangles]
    facing = normals[:, 0] * normal[0] + normals[:, 1] * normal[1] + normals[:, 2] * normal[2]
    walls = np.abs(facing) < WALL_UPRIGHT
    wall_area = float(areas[walls].sum())
    if wall_area <= EPS_GEOM:
        return None
    corners = surface.points[surface.corner_ids[triangles]].reshape(-1, 3)
    origin = region.origin
    heights = (
        (corners[:, 0] - origin[0]) * normal[0]
        + (corners[:, 1] - origin[1]) * normal[1]
        + (corners[:, 2] - origin[2]) * normal[2]
    )
    depth = float(heights.max())
    if depth < MIN_CHAMBER_DEPTH or float(heights.min()) < -tolerance * 4.0:
        return None
    floor_triangles = np.asarray(features[region.floor].face_indices, dtype=np.int64)
    floor_area = float(surface.areas[floor_triangles].sum())
    if region.ceiling >= 0.5 * floor_area:
        # Eine Gegenfläche über dem Boden: ein Schlitz oder Durchgang, keine
        # Öffnung nach oben (die Schlitzflanken des Filterkäfigs, Fall 162).
        return None
    enclosed = surface.enclosure(floor_triangles, triangles, lookup.holes)
    if enclosed < ENCLOSED_TROUGH:
        # Weniger umschließt keine der Formen unten; der Strahl darunter ist
        # die teuerste Frage und kommt erst nach den billigen.
        return None
    members = _members_of(triangles, lookup, features)
    if not members or all(
        features[member].kind in ("hole", "slot", "thread")
        for member in members
        if member != region.floor
    ):
        return None
    if any(
        features[member].kind in ("hole", "slot") for member in members if member != region.floor
    ) and _round_only(members, region.floor, features):
        return None
    if not _open_above(surface, lookup, floor_triangles, normal):
        # Über dem Boden steht Material: Eine Innenwand eines Rings, als Boden
        # gelesen, sieht die gegenüberliegende Wand (Deckelring eckig, Fall 145).
        return None
    axes = _dominant_axes(normals[walls], areas[walls], normal)
    if axes is None:
        return None
    first, second = axes
    sides = _side_shares(normals[walls], areas[walls], normal, first, second)
    full = [share >= SIDE_SHARE for share in sides]
    loops = _boundary_loops(
        surface, np.asarray(features[region.floor].face_indices, dtype=np.int64)
    )
    roles = tuple(
        (member, _chamber_role(member, region.floor, features, normal)) for member in members
    )
    planar_rim = _planar_rim(surface, triangles, region.origin, normal, depth, tolerance)
    # **Die Innenmaße liest die Wand, nicht alles Erreichte**: Ein Auslass am
    # Boden führt die Wanderung bis auf die Lippe davor (Wasserfall), und deren
    # Ecken gehören nicht zum Innenmaß der Kammer.
    wall_corners = surface.points[surface.corner_ids[triangles[walls]]].reshape(-1, 3)
    u_extent = _extent(wall_corners, first)
    v_extent = _extent(wall_corners, second)
    if (
        loops >= 2
        and enclosed >= ENCLOSED_RING
        and _faces_both_ways(normals[walls], surface, triangles[walls], region.origin, normal)
    ):
        floor_area = _number(features[region.floor], "area") or 0.0
        perimeter = _floor_perimeter(
            surface, np.asarray(features[region.floor].face_indices, dtype=np.int64)
        )
        width = 2.0 * floor_area / perimeter if perimeter > EPS_GEOM else 0.0
        ring = depth > RING_CHAMBER_RATIO * width
        return FunctionalGroup(
            kind="chamber" if ring else "channel",
            variant="ring" if ring else "groove",
            anchor=region.floor,
            members=tuple(members),
            roles=roles,
            measures=(
                GroupMeasure("width", width, "mm"),
                GroupMeasure("depth", depth, "mm"),
            ),
            evidence="ring_walls" if not ring else "ring_chamber",
            shared=bool(region.other_floors),
            planar_rim=planar_rim,
        )
    count = sum(full)
    if (
        count == 2
        and ((full[0] and full[1]) or (full[2] and full[3]))
        and enclosed >= ENCLOSED_TROUGH
    ):
        across, along = (first, second) if full[0] else (second, first)
        return FunctionalGroup(
            kind="channel",
            variant="trough",
            anchor=region.floor,
            members=tuple(members),
            roles=roles,
            measures=(
                GroupMeasure("width", _extent(wall_corners, across), "mm"),
                GroupMeasure("depth", depth, "mm"),
                GroupMeasure("length", _extent(corners, along), "mm"),
            ),
            evidence="two_walls",
            shared=bool(region.other_floors),
            planar_rim=False,
        )
    if count < 3 or enclosed < ENCLOSED_SIDE:
        return None
    variant = "open_side"
    evidence: GroupEvidence = "open_side"
    if count == 4 and enclosed >= ENCLOSED_RING:
        # Ringsum Wand: geschlossen, wenn der Rand eben ist, sonst unterbrochen.
        # Ein Auslass am Boden (Wasserfall: 150 auf 4 mm in der Vorderwand)
        # lässt den Bodenrand offen — das bleibt eine offene Tasche.
        variant, evidence = (
            ("closed", "floor_and_walls") if planar_rim else ("open_rim", "open_rim")
        )
    return FunctionalGroup(
        kind="chamber",
        variant=variant,
        anchor=region.floor,
        members=tuple(members),
        roles=roles,
        measures=(
            GroupMeasure("width", u_extent, "mm"),
            GroupMeasure("length", v_extent, "mm"),
            GroupMeasure("depth", depth, "mm"),
        ),
        evidence=evidence,
        shared=bool(region.other_floors),
        suggested=bool(region.other_floors),
        planar_rim=planar_rim,
    )


def _open_above(surface: _Surface, lookup: _Lookup, floor: np.ndarray, normal: Vec) -> bool:
    """Ob über dem Boden Luft ist: Strahlen von den größten Bodendreiecken.

    Eine Kammer ist nach oben offen; ein Strahl von ihrem Boden entlang der
    Bodennormalen verlässt den Körper, ohne eine Fläche zu treffen. Gefragt
    wird an bis zu fünf Bodendreiecken (die größten, gleich große nach
    Nummer), und die Mehrheit entscheidet — eine Lippe über einem Teil des
    Bodens schließt die Kammer nicht. Elementweise gerechnet (Möller-Trumbore),
    plattformgleich.

    **Geprüft wird nur, was der Strahl erreichen kann**: Je Richtung liegen die
    Dreiecke einmal als Kästchen quer zu ihr vor (:meth:`_Lookup.boxes`); wessen
    Kästchen den Strahl nicht enthält, kann ihn nicht treffen. Die genaue
    Prüfung an den übrigen ist dieselbe Rechnung wie über alle Dreiecke.
    """
    if not len(floor):
        return False
    order = np.lexsort((floor, -surface.areas[floor]))
    chosen = floor[order[:OPEN_RAYS]]
    direction = np.asarray(normal, dtype=np.float64)
    boxes = lookup.boxes(surface, normal)
    if boxes is None:
        return False
    first_axis, second_axis, low_u, high_u, low_v, high_v, top, margin = boxes
    open_count = 0
    for triangle in chosen.tolist():
        start = surface.points[surface.corner_ids[triangle]].mean(axis=0) + direction * 1e-4
        at_u = float(start[0] * first_axis[0] + start[1] * first_axis[1] + start[2] * first_axis[2])
        at_v = float(
            start[0] * second_axis[0] + start[1] * second_axis[1] + start[2] * second_axis[2]
        )
        at_h = float(start[0] * direction[0] + start[1] * direction[1] + start[2] * direction[2])
        near = np.flatnonzero(
            (low_u <= at_u + margin)
            & (high_u >= at_u - margin)
            & (low_v <= at_v + margin)
            & (high_v >= at_v - margin)
            & (top >= at_h - margin)
        )
        near = near[near != triangle]
        if not _ray_hits(surface, near, start, direction):
            open_count += 1
    return open_count * 2 > len(chosen)


def _ray_hits(
    surface: _Surface, candidates: np.ndarray, start: np.ndarray, direction: np.ndarray
) -> bool:
    """Ob der Strahl eines der Dreiecke trifft — Möller-Trumbore, elementweise."""
    if not candidates.size:
        return False
    corners = surface.points[surface.corner_ids[candidates]]
    first = corners[:, 0]
    edge_a = corners[:, 1] - first
    edge_b = corners[:, 2] - first
    cross_b = np.stack(
        (
            direction[1] * edge_b[:, 2] - direction[2] * edge_b[:, 1],
            direction[2] * edge_b[:, 0] - direction[0] * edge_b[:, 2],
            direction[0] * edge_b[:, 1] - direction[1] * edge_b[:, 0],
        ),
        axis=1,
    )
    determinant = (edge_a * cross_b).sum(axis=1)
    usable = np.abs(determinant) > 1e-12
    inverse = np.where(usable, 1.0 / np.where(usable, determinant, 1.0), 0.0)
    offset = start - first
    u = (offset * cross_b).sum(axis=1) * inverse
    cross_a = np.stack(
        (
            offset[:, 1] * edge_a[:, 2] - offset[:, 2] * edge_a[:, 1],
            offset[:, 2] * edge_a[:, 0] - offset[:, 0] * edge_a[:, 2],
            offset[:, 0] * edge_a[:, 1] - offset[:, 1] * edge_a[:, 0],
        ),
        axis=1,
    )
    v = (cross_a * direction).sum(axis=1) * inverse
    t = (edge_b * cross_a).sum(axis=1) * inverse
    hit = usable & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0) & (t > 1e-6)
    return bool(hit.any())


def _round_only(
    members: Sequence[FeatureId], floor: FeatureId, features: Mapping[FeatureId, Feature]
) -> bool:
    """Ob die Wände nur aus Bohrung oder Langloch bestehen — ein Sackloch, keine Kammer."""
    rest = [member for member in members if member != floor]
    return bool(rest) and all(
        features[member].kind in ("hole", "slot", "cone", "fillet") for member in rest
    )


def _members_of(
    triangles: np.ndarray, lookup: _Lookup, features: Mapping[FeatureId, Feature]
) -> list[FeatureId]:
    """Merkmale, deren Dreiecke überwiegend im Bereich liegen — und ihr erstes darin."""
    owners = lookup.owner_id[triangles]
    counted = np.bincount(owners[owners >= 0], minlength=len(lookup.names))
    inside = lookup.marks
    inside[triangles] = True
    try:
        members = [
            name
            for name, hits in (
                (lookup.names[index], int(counted[index])) for index in np.flatnonzero(counted)
            )
            if hits * 2 >= len(features[name].face_indices)
            and all(bool(inside[int(index)]) for index in features[name].face_indices[:1])
        ]
    finally:
        inside[triangles] = False
    return members


def _chamber_role(
    member: FeatureId, floor: FeatureId, features: Mapping[FeatureId, Feature], normal: Vec
) -> GroupRole:
    if member == floor:
        return "floor"
    feature = features[member]
    if feature.kind == "face":
        own = _unit(feature.params.get("normal"))
        if own is not None and _dot(own, normal) >= FLOOR_ALIGNED:
            return "ledge"
        return "wall"
    return "blend"


def _dominant_axes(normals: np.ndarray, areas: np.ndarray, floor: Vec) -> tuple[Vec, Vec] | None:
    """Die zwei Wandrichtungen in der Bodenebene — aus der Vierfachwinkel-Mittelung.

    Über cos 4θ und sin 4θ gemittelt, damit gegenüberliegende und senkrechte
    Wände dieselbe Achse stärken; die Richtung kommt über zwei Halbwinkel
    zurück — nur Wurzeln, keine Winkelfunktion (``kern.md``). Runde Wände ohne
    Vorzugsrichtung nehmen die Achsen der Bodenebene selbst.
    """
    frame = plane_axes(floor)
    if frame is None:
        return None
    e1, e2 = frame
    c = normals[:, 0] * e1[0] + normals[:, 1] * e1[1] + normals[:, 2] * e1[2]
    s = normals[:, 0] * e2[0] + normals[:, 1] * e2[1] + normals[:, 2] * e2[2]
    reach = np.sqrt(c * c + s * s)
    usable = reach > 1e-9
    if not usable.any():
        return frame
    c = c[usable] / reach[usable]
    s = s[usable] / reach[usable]
    weights = areas[usable]
    cos2 = c * c - s * s
    sin2 = 2.0 * c * s
    cos4 = cos2 * cos2 - sin2 * sin2
    sin4 = 2.0 * sin2 * cos2
    total_c = float((cos4 * weights).sum())
    total_s = float((sin4 * weights).sum())
    size = math.sqrt(total_c * total_c + total_s * total_s)
    if size <= 1e-6 * float(weights.sum()):
        return frame
    half_c, half_s = _half_angle(total_c / size, total_s / size)
    quarter_c, quarter_s = _half_angle(half_c, half_s)
    first = (
        e1[0] * quarter_c + e2[0] * quarter_s,
        e1[1] * quarter_c + e2[1] * quarter_s,
        e1[2] * quarter_c + e2[2] * quarter_s,
    )
    second = (
        floor[1] * first[2] - floor[2] * first[1],
        floor[2] * first[0] - floor[0] * first[2],
        floor[0] * first[1] - floor[1] * first[0],
    )
    return first, second


def _half_angle(cosine: float, sine: float) -> tuple[float, float]:
    """Kosinus und Sinus des halben Winkels, auf dem Ast mit positivem Kosinus."""
    half_c = math.sqrt(max(0.0, (1.0 + cosine) / 2.0))
    if half_c <= 1e-12:
        return 0.0, 1.0
    return half_c, sine / (2.0 * half_c)


def _side_shares(
    normals: np.ndarray, areas: np.ndarray, floor: Vec, first: Vec, second: Vec
) -> list[float]:
    """Anteil der Wandfläche, der in die vier Seitenrichtungen schaut (u, -u, v, -v)."""
    total = float(areas.sum())
    along_first = normals[:, 0] * first[0] + normals[:, 1] * first[1] + normals[:, 2] * first[2]
    along_second = normals[:, 0] * second[0] + normals[:, 1] * second[1] + normals[:, 2] * second[2]
    flat = np.sqrt(along_first * along_first + along_second * along_second)
    flat = np.where(flat > 1e-9, flat, 1.0)
    along_first = along_first / flat
    along_second = along_second / flat
    del floor
    return [
        float(areas[along_first >= SIDE_ALIGNED].sum()) / total,
        float(areas[along_first <= -SIDE_ALIGNED].sum()) / total,
        float(areas[along_second >= SIDE_ALIGNED].sum()) / total,
        float(areas[along_second <= -SIDE_ALIGNED].sum()) / total,
    ]


def _extent(points: np.ndarray, direction: Vec) -> float:
    along = points[:, 0] * direction[0] + points[:, 1] * direction[1] + points[:, 2] * direction[2]
    return float(along.max() - along.min())


def _boundary_edges(surface: _Surface, triangles: np.ndarray) -> np.ndarray:
    """Die Kanten, die genau ein Dreieck der Menge trägt."""
    faces = surface.corner_ids[triangles]
    edges = np.stack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]), axis=1).reshape(-1, 2)
    ordered = np.sort(edges, axis=1)
    width = int(surface.points.shape[0]) + 1
    codes = ordered[:, 0] * width + ordered[:, 1]
    _unique, first, counts = np.unique(codes, return_index=True, return_counts=True)
    return np.asarray(ordered[first[counts == 1]])


def _boundary_loops(surface: _Surface, triangles: np.ndarray) -> int:
    """Wie viele geschlossene Randringe eine Dreiecksmenge hat."""
    edges = _boundary_edges(surface, triangles)
    if not len(edges):
        return 0
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        root = node
        while parent.get(root, root) != root:
            root = parent[root]
        while parent.get(node, node) != root:
            parent[node], node = root, parent[node]
        return root

    for a, b in edges.tolist():
        root_a, root_b = find(int(a)), find(int(b))
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)
    return len({find(int(node)) for node in np.unique(edges).tolist()})


def _floor_perimeter(surface: _Surface, triangles: np.ndarray) -> float:
    edges = _boundary_edges(surface, triangles)
    if not len(edges):
        return 0.0
    delta = surface.points[edges[:, 1]] - surface.points[edges[:, 0]]
    return float(
        np.sqrt(
            delta[:, 0] * delta[:, 0] + delta[:, 1] * delta[:, 1] + delta[:, 2] * delta[:, 2]
        ).sum()
    )


def _faces_both_ways(
    normals: np.ndarray, surface: _Surface, wall_triangles: np.ndarray, origin: Vec, floor: Vec
) -> bool:
    """Ob Wände zur Mitte **und** von ihr weg schauen — die Innenwand einer Nut."""
    centres = surface.points[surface.corner_ids[wall_triangles]].mean(axis=1)
    towards = np.asarray(origin, dtype=float) - centres
    along = towards[:, 0] * floor[0] + towards[:, 1] * floor[1] + towards[:, 2] * floor[2]
    towards = towards - along[:, None] * np.asarray(floor, dtype=float)
    lean = (normals * towards).sum(axis=1)
    return bool((lean > 0).any() and (lean < 0).any())


def _planar_rim(
    surface: _Surface,
    triangles: np.ndarray,
    origin: Vec,
    normal: Vec,
    depth: float,
    tolerance: float,
) -> bool:
    """Ob der obere Rand des Bereichs auf **einer** Höhe liegt.

    Gezählt werden die Randecken über dem Boden; Löcher im Boden selbst (ihre
    Ränder liegen auf Bodenhöhe) gehören nicht zum Rand der Öffnung. Liegt jede
    übrige Randecke auf der vollen Tiefe, ist der Rand eben — sonst ist er
    unterbrochen (Auffangwanne, Fall 267), und das gemeinsame Ändern sagt ab.
    """
    edges = _boundary_edges(surface, triangles)
    if not len(edges):
        return False
    points = surface.points[np.unique(edges)]
    heights = (
        (points[:, 0] - origin[0]) * normal[0]
        + (points[:, 1] - origin[1]) * normal[1]
        + (points[:, 2] - origin[2]) * normal[2]
    )
    level = max(tolerance * 2.0, 1e-3)
    above = heights[heights > level]
    if not len(above):
        return False
    return bool(float(np.abs(above - depth).max()) <= level)


# --- Schrift auf einer Trägerfläche ------------------------------------------


def _relief_lettering(
    features: Mapping[FeatureId, Feature],
    surface: _Surface,
    part_of: np.ndarray,
    tolerance: float,
) -> list[FunctionalGroup]:
    """Erhabene oder vertiefte Schrift, mit ihrem Träger verschmolzen.

    Das WC-Schild (Fall 247) trägt „Bitte im Sitzen“ 0,7 mm über der Platte, in
    einem Körper: Die Buchstabenoberseiten sind kleine Flächen parallel zur
    Platte, alle auf derselben Höhe darüber, und verschieden groß — wie Glyphen
    eben sind. Vier gleiche Füße auf einer Platte sind keine Schrift: Ihre
    Oberseiten sind gleich groß. Zur Schrift gehören dann auch die Seiten
    zwischen Platte und Oberseite und die Innenräume der Buchstaben (ein „e“
    hat einen), die sonst als winzige Taschen dastünden.
    """
    table = _Planes.of(features)
    planes = list(zip(table.names, table.normals, table.centres, table.areas, strict=True))
    if len(planes) < MIN_LETTERS + 1:
        return []
    groups: list[FunctionalGroup] = []
    used: set[FeatureId] = set()

    def part(name: FeatureId) -> int:
        indices = features[name].face_indices
        return int(part_of[int(indices[0])]) if indices else -1

    for carrier, normal, origin, carrier_area in sorted(planes, key=lambda entry: -entry[3]):
        if carrier in used:
            continue
        carrier_part = part(carrier)
        # Vorsieb mit Zugabe über alle Flächen zugleich; entschieden wird an
        # denselben Zahlen wie in der Schleife über alle.
        small = np.flatnonzero(
            (table.area_array <= LETTER_SHARE * carrier_area * (1.0 + 1e-12))
            & (
                table.normal_array[:, 0] * normal[0]
                + table.normal_array[:, 1] * normal[1]
                + table.normal_array[:, 2] * normal[2]
                >= FLOOR_ALIGNED - 1e-9
            )
        )
        if len(small) < RELIEF_LETTERS:
            continue
        levels: dict[float, list[tuple[FeatureId, float]]] = {}
        for position in small.tolist():
            name, other, centre, area = planes[position]
            if name == carrier or name in used or area > LETTER_SHARE * carrier_area:
                continue
            if part(name) != carrier_part:
                # Eine eigene Schale auf dem Träger ist getrennte Schrift
                # (:func:`_lettering`), keine vertiefte.
                continue
            if _dot(other, normal) < FLOOR_ALIGNED:
                continue
            height = _dot(_sub(centre, origin), normal)
            if not LETTER_RELIEF[0] <= abs(height) <= LETTER_RELIEF[1]:
                continue
            key = round(height / max(LETTER_LEVEL, EPS_GEOM)) * LETTER_LEVEL
            levels.setdefault(key, []).append((name, area))
        for height, tops in sorted(levels.items(), key=lambda entry: -len(entry[1])):
            if len(tops) < RELIEF_LETTERS:
                continue
            areas = [area for _name, area in tops]
            mean = sum(areas) / len(areas)
            spread = math.sqrt(sum((area - mean) * (area - mean) for area in areas) / len(areas))
            if spread < LETTER_VARIETY * mean:
                continue
            outlines = [
                surface.points[np.unique(surface.corner_ids[list(features[name].face_indices)])]
                for name, _area in tops
            ]
            if not _reads_as_text(outlines, areas, normal):
                continue
            members = _relief_members(features, tops, normal, origin, height, carrier, tolerance)
            if not members:
                continue
            used.update(members)
            letter: GroupRole = "letter"
            roles = tuple((member, letter) for member in members)
            groups.append(
                FunctionalGroup(
                    kind="lettering",
                    variant="raised" if height > 0 else "engraved",
                    anchor=members[0],
                    members=members,
                    roles=roles,
                    measures=(
                        GroupMeasure("count", float(len(tops)), ""),
                        GroupMeasure("height", abs(height), "mm"),
                    ),
                    evidence="relief_on_a_carrier",
                    count=len(tops),
                )
            )
            break
    return groups


def _reads_as_text(outlines: Sequence[np.ndarray], areas: Sequence[float], normal: Vec) -> bool:
    """Ob Flächen auf einer Ebene wie Buchstaben aussehen.

    ``outlines`` sind die Eckpunkte je Buchstabe, ``areas`` ihre Fläche in der
    Ebene. Die Hülle rechnet GEOS — keine Wahl hängt an einer letzten Stelle:
    Buchstaben liegen weit unter :data:`GLYPH_SOLIDITY`, Noppen und Kreise bei
    1, und gleiche Formen sind bis auf Rundung gleich.
    """
    from shapely.geometry import MultiPoint

    frame = plane_axes(normal)
    if frame is None or len(outlines) < MIN_LETTERS:
        return False
    first, second = frame
    shapes: list[tuple[float, float]] = []
    for points, area in zip(outlines, areas, strict=True):
        u = points[:, 0] * first[0] + points[:, 1] * first[1] + points[:, 2] * first[2]
        v = points[:, 0] * second[0] + points[:, 1] * second[1] + points[:, 2] * second[2]
        hull = float(MultiPoint(np.column_stack((u, v))).convex_hull.area)
        shapes.append((area, area / hull if hull > EPS_GEOM else 1.0))
    shaped = sum(1 for _area, filled in shapes if filled < GLYPH_SOLIDITY)
    if shaped < GLYPH_SHARE * len(shapes):
        return False
    kinds: list[tuple[float, float]] = []
    for area, filled in sorted(shapes):
        if not any(
            abs(area - known) <= 0.02 * known and abs(filled - fill) <= 0.03
            for known, fill in kinds
        ):
            kinds.append((area, filled))
    return len(kinds) >= GLYPH_SHAPES


def _facing(surface: _Surface, triangles: np.ndarray, direction: Vec) -> np.ndarray:
    """Welche der Dreiecke in die Richtung schauen — die Oberseite eines Teils."""
    normals = surface.normals[triangles]
    along = (
        normals[:, 0] * direction[0] + normals[:, 1] * direction[1] + normals[:, 2] * direction[2]
    )
    return np.asarray(along >= FLOOR_ALIGNED)


def _relief_members(
    features: Mapping[FeatureId, Feature],
    tops: Sequence[tuple[FeatureId, float]],
    normal: Vec,
    origin: Vec,
    height: float,
    carrier: FeatureId,
    tolerance: float,
) -> tuple[FeatureId, ...]:
    """Oberseiten, Seiten und Innenräume der Buchstaben über dem Träger."""
    chosen = {name for name, _area in tops}
    centres = [_vector(features[name].params.get("centre")) for name in chosen]
    points = [centre for centre in centres if centre is not None]
    low = [min(point[axis] for point in points) for axis in range(3)]
    high = [max(point[axis] for point in points) for axis in range(3)]
    margin = max(tolerance, abs(height)) * 4.0
    band = (min(0.0, height) - tolerance, max(0.0, height) + tolerance)
    for name in sorted(features, key=_id_key):
        if name in chosen or name == carrier:
            continue
        feature = features[name]
        centre = _vector(feature.params.get("centre"))
        if centre is None:
            continue
        if any(
            centre[axis] < low[axis] - margin or centre[axis] > high[axis] + margin
            for axis in range(3)
        ):
            continue
        along = _dot(_sub(centre, origin), normal)
        if not band[0] <= along <= band[1]:
            continue
        own = _unit(feature.params.get("normal"))
        if feature.kind == "face" and own is not None and _dot(own, normal) >= FLOOR_ALIGNED:
            # Ein Innenraum auf Trägerhöhe — klein, sonst ist es der Träger selbst.
            area = _number(feature, "area") or 0.0
            if abs(along) <= tolerance and area <= LETTER_SHARE * (
                _number(features[carrier], "area") or 0.0
            ):
                chosen.add(name)
            continue
        if feature.kind in ("face", "curved_face", "fillet") and (
            own is None or abs(_dot(own, normal)) < WALL_UPRIGHT
        ):
            chosen.add(name)
    return tuple(sorted(chosen, key=_id_key))


# --- Schrift aus eigenen Teilen ---------------------------------------------


def _lettering(
    features: Mapping[FeatureId, Feature],
    mesh: MeshData,
    surface: _Surface,
    pieces: Sequence[np.ndarray],
    tolerance: float,
) -> list[FunctionalGroup]:
    """Gleich hohe, flache Teile auf einer gemeinsamen Ebene — eine Beschriftung.

    Die 68 Schriftteile des Drillholders (Fall 303) und die Buchstaben des
    Screen-Covers sind eigene Schalen. Ein Teil zählt als Buchstabe, wenn es
    flach ist (Höhe höchstens halb so groß wie seine Breite in der Ebene) und
    mindestens zwei weitere dieselbe Höhe und dieselbe Grundebene haben. Das
    größte Teil ist der Träger, kein Buchstabe.
    """
    if len(pieces) < MIN_LETTERS + 1:
        return []
    owner = _triangle_owner(features)
    vertices = np.asarray(mesh.raw.vertices, dtype=np.float64)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    sizes = [float(surface.areas[piece].sum()) for piece in pieces]
    carrier = int(np.argmax(sizes))
    groups: list[FunctionalGroup] = []
    for axis_index in range(3):
        flat: list[tuple[int, float, float]] = []
        for index, piece in enumerate(pieces):
            if index == carrier:
                continue
            points = vertices[np.unique(faces[piece])]
            low = points.min(axis=0)
            high = points.max(axis=0)
            height = float(high[axis_index] - low[axis_index])
            spread = [float(high[k] - low[k]) for k in range(3) if k != axis_index]
            if height <= EPS_GEOM or height > LETTER_FLATNESS * max(spread):
                continue
            if height > LETTER_RELIEF[1]:
                # Ein 25 mm hohes Teil ist kein Buchstabe, auch wenn es breit ist.
                continue
            flat.append((index, float(low[axis_index]), height))
        if len(flat) < MIN_LETTERS:
            continue
        flat.sort(
            key=lambda entry: (
                round(entry[1] / max(tolerance, EPS_GEOM)),
                round(entry[2] / max(tolerance, EPS_GEOM)),
                entry[0],
            )
        )
        clusters: list[list[tuple[int, float, float]]] = []
        for entry in flat:
            if (
                clusters
                and abs(entry[1] - clusters[-1][0][1]) <= tolerance * 2.0
                and abs(entry[2] - clusters[-1][0][2]) <= max(tolerance * 2.0, 0.02 * entry[2])
            ):
                clusters[-1].append(entry)
            else:
                clusters.append([entry])
        direction: Vec = (
            1.0 if axis_index == 0 else 0.0,
            1.0 if axis_index == 1 else 0.0,
            1.0 if axis_index == 2 else 0.0,
        )
        for cluster in clusters:
            if len(cluster) < MIN_LETTERS:
                continue
            outlines = [vertices[np.unique(faces[pieces[index]])] for index, _low, _h in cluster]
            footprints = [
                float(
                    surface.areas[pieces[index]][_facing(surface, pieces[index], direction)].sum()
                )
                for index, _low, _h in cluster
            ]
            mean = sum(footprints) / len(footprints)
            variety = math.sqrt(
                sum((area - mean) * (area - mean) for area in footprints) / len(footprints)
            )
            if mean <= EPS_GEOM or variety < LETTER_VARIETY * mean:
                # Gleiche Teile sind ein Satz Teile, keine Schrift (zehn Clips).
                continue
            if not _reads_as_text(outlines, footprints, direction):
                continue
            triangles = np.concatenate([pieces[index] for index, _low, _height in cluster])
            members = sorted(
                {owner[int(index)] for index in triangles.tolist() if int(index) in owner},
                key=_id_key,
            )
            if not members:
                continue
            groups.append(
                FunctionalGroup(
                    kind="lettering",
                    variant="separate",
                    anchor=members[0],
                    members=tuple(members),
                    roles=tuple((member, "letter") for member in members),
                    measures=(
                        GroupMeasure("count", float(len(cluster)), ""),
                        GroupMeasure("height", cluster[0][2], "mm"),
                    ),
                    evidence="flat_parts_on_a_carrier",
                    count=len(cluster),
                )
            )
    return groups


__all__ = [
    "GROUP_KINDS",
    "NOT_A_CHAMBER",
    "ChamberRegion",
    "FunctionalGroup",
    "GroupEvidence",
    "GroupKind",
    "GroupMeasure",
    "GroupRole",
    "chamber_region",
    "evidence_texts",
    "functional_groups",
    "functional_title",
    "group_of",
    "measure_titles",
    "numbered_titles",
    "reason_against_group",
]
