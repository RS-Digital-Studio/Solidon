"""Muster: viele gleiche Zellen auf einer Fläche, ein Merkmal (§21.1, §25).

**Ein Wabenmuster ist keine Sammlung von Flächen.** Am Schraubendreherhalter
eines Kunden (22.09.2026) fand die Erkennung 1 199 ebene Flächen — 1 170 davon
die Wände von 195 sechseckigen Zellen, 9 mm Schlüsselweite, 20 mm tief, in
einem Gitter mit 10,4 mm Teilung. Im Objektbaum standen sie gefaltet als
„Flächen", und nichts daran sagte, dass es ein Muster ist, geschweige denn,
welches. Solidon **erzeugt** dieselben Muster
(``geom.texture_ops.apply_texture``: Rippe, Welle, Rändel gerade und über
Kreuz, Wabe, Noppe, Voronoi, Rauschen), konnte sie aber nicht lesen — und was
es liest, kann es ändern und entfernen.

Dieselbe Bauart wie beim Langloch (:mod:`app.core.perceive.slots`) und beim
Gewinde: Was aus vielen Einpassungen zusammenwächst, wird am **Netz** gemessen
und verschluckt die Formen, aus denen es besteht. Der Unterschied ist die
Zahl: Ein Muster entsteht nicht aus zwei Nachbarn, sondern aus vielen Zellen.

**Was eine Zelle ist.** Ein zusammenhängendes Stück kleiner Merkmale, das nur
an eine große ebene Fläche grenzt — bei einem sechseckigen Loch die sechs
Wände, bei einer geprägten Raute vier Wände und ein Boden, bei einer Noppe die
Sackbohrung samt Boden, bei einer erhabenen Rippe zwei lange Wände, zwei
Stirnwände und die Krone. Die ebene Fläche, in der die Zelle mündet, ist ihr
**Träger**; grenzt sie an zwei parallele Träger, geht sie durch. Woraus die
Zelle besteht, ist am Netz gemessen und nicht angenommen: Die Tiefe ist die
Ausdehnung entlang der Trägernormalen, die Mündung sind die Ecken in der
Trägerebene, und ob die Zelle vertieft oder erhaben ist, sagt die Seite, auf
der sie liegt.

**Was ein Muster daraus macht, ist die Menge.** Entweder ein **Gitter**:
mindestens :data:`MIN_CELLS` deckungsgleiche Zellen auf demselben Träger,
deren Mitten in gleichen Abständen liegen — die Teilung ist der Abstand zum
nächsten Nachbarn, und er ist an neun von zehn Zellen derselbe. Oder eine
**Streuung**: mindestens :data:`MIN_SCATTER` Zellen gleicher Tiefe auf
demselben Träger ohne Gitter — Voronoi und Rauschen haben keine Teilung, aber
eine Dichte, und die ist ihre Teilung. Zellen, die am Rand des Feldes
angeschnitten sind (ein erzeugtes Muster endet an seinem Rechteck), gehören
dazu, sobald sie im Feld und auf demselben Träger liegen — als ``partial``
gezählt, nicht als Zelle. Ein Rauschen braucht mehr Flecken als ein
Voronoi-Feld (:data:`MIN_NOISE`): Ein Schild mit zwei Dutzend erhabenen
Buchstaben ist sonst nicht davon zu unterscheiden.

**Wo die Grenze zu den Bohrungen liegt** (Entscheidung RM-207): Eine runde
Zelle ist nur dann eine Noppe, wenn sie **blind** und **flach** ist (höchstens
:data:`ROUND_DEPTH` mal so tief wie breit), mindestens
:data:`MIN_ROUND_CELLS` Geschwister hat und mit ihnen im **Wabengitter**
liegt — dem einzigen, in dem ``apply_texture`` Noppen setzt
(:data:`_GENERATOR_LATTICE`). Ein Lochblech mit 81 durchgehenden Bohrungen
bleibt 81 Bohrungen, ein Feld von zwölf Magnettaschen zwölf Taschen, und 25
Magnettaschen in fünf Reihen zu fünf bleiben es auch — an allen gelten die
Bohrungshandlungen, und die nähme ein Muster ihnen weg. Sechseckige Löcher
haben keine solchen Handlungen und werden deshalb auch durchgehend zum
Muster: Genau das ist der Halter. Und was zwar ein Gitter ist, aber keines,
das Solidon so zeichnet — Sechsecke im Quadratraster —, heißt ``other``:
entfernbar, nicht neu setzbar.

**Ein Träger kann ein Zylinder sein** — ein Rändel um einen Griff,
``apply_texture`` mit ``wrap="cylinder"``. Gemessen wird dann in seiner
**Abwicklung** (:class:`Frame`): Umfang und Achse sind die zwei Achsen, der
Abstand zum Radius die Höhe, und dieselbe Rechnung findet dieselben Zellen
wie auf der Ebene. Der Zylinder ist ein ``pin`` der Erkennung, groß genug,
um Träger zu sein; die Naht seiner Abwicklung fällt in die größte Lücke
zwischen den Zellen. Entfernen und Ändern biegen ihre Körper um dieselbe
Achse zurück.
"""

from __future__ import annotations

import dataclasses
import functools
import math
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, NamedTuple

import numpy as np

from app.core import units
from app.core.geom.mesh import (
    MeshData,
    periodic_sin_cos,
    stable_arctan2,
    unique_edges,
)
from app.core.types import Feature, FeatureId, MeasureSource, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

#: Ab wie vielen deckungsgleichen Zellen ein Gitter ein Muster ist.
#:
#: Neun — drei mal drei, das kleinste Gitter in zwei Richtungen. Vier
#: Befestigungslöcher in den Ecken einer Platte liegen zu viert auf einem
#: Rechteck, sechs Taschen in einem Sortierkasten zu sechst in zwei Reihen,
#: und beides meint der Kunde noch einzeln: An jeder Wand geht „Fläche
#: versetzen", im Muster gehen die Wände auf. Die Zahl ist gewählt, nicht
#: gemessen — sie trennt die Absicht („ein Muster") von der Anzahl.
MIN_CELLS: Final = 9

#: Ab wie vielen Streifen eine Reihe ein Muster ist. Sechs: Eine Reihe hat
#: nur eine Richtung, und sechs Rippen auf einem Griff sind schon ein Rändel —
#: bei 4 mm Teilung reichen sie über 24 mm, mehr Griff hat mancher Stift nicht.
MIN_STRIPS: Final = 6

#: Ab wie vielen runden Zellen ein Gitter aus Noppen ein Muster ist.
#:
#: Zwanzig, und mehr als bei den eckigen, weil runde Zellen sonst Bohrungen
#: sind und Bohrungen ihre eigenen Handlungen haben. Eine Noppentextur aus
#: ``apply_texture`` hat auf dem kleinsten sinnvollen Feld (10 mal 10 mm bei
#: 2 mm Teilung) rund fünfundzwanzig; eine Reihe Magnettaschen hat selten
#: mehr als zwölf. Dazwischen liegt die Grenze, und sie ist eine Wahl.
MIN_ROUND_CELLS: Final = 20

#: Ab wie vielen Zellen eine Streuung ohne Gitter ein Muster ist.
#:
#: Vierundzwanzig: Ein Voronoi-Feld aus ``apply_texture`` hat je Quadrat der
#: Teilung eine Zelle, also auf 40 mal 30 mm bei 4 mm Teilung fünfundsiebzig;
#: ein Sortierkasten mit verschieden geformten Fächern hat ein Dutzend. Die
#: Fächer bleiben Flächen, das Feld wird ein Muster.
MIN_SCATTER: Final = 24

#: Ab wie vielen Streuflecken ein Rauschen ein Muster ist — mehr als bei
#: Voronoi, weil ein Rauschen nichts hat, woran man es sonst erkennte: Ein
#: Schild mit 24 erhabenen Buchstaben in einer Zeile sah in der Korpusprobe
#: (22.09.2026, ``Bitte_im_Sitzen.3mf``) genauso aus — gleich tief, verstreut,
#: ein Drittel Deckung. Ein Rauschen aus ``apply_texture`` hat bei seiner
#: Vorgabe (2 mm Teilung auf 40 mal 30) über hundert Flecken.
MIN_NOISE: Final = 40

#: Ab wie vielen Zellen eine **ausdrückliche** Zusammenfassung ein Muster ist
#: (:func:`grouped_pattern`, RM-504). Zwei: Eine Zelle allein hat keine
#: Teilung, und alles darüber hat der Kunde selbst gewählt. Die Schwellen
#: darüber gelten der Erkennung ohne Erzeugerwissen und bleiben, wie sie sind —
#: drei Magnettaschen sind ohne Wahl drei Taschen.
LEAST_GROUPED_CELLS: Final = 2

#: Womit die Kennung eines ausdrücklich zusammengefassten Musters beginnt. Die
#: Auswertung hängt die Kennung des Schritts an (``grouped_<Schritt>``), wie
#: ``texture_<Schritt>`` bei einer selbst aufgebrachten Textur: Eine
#: Nummernfolge verschöbe Folgebezüge, sobald eine frühere Zusammenfassung
#: wegfällt, und ``pattern_<n>`` gehört der Erkennung.
GROUPED_PREFIX: Final = "grouped"

#: Wie viele der Zellen ihren nächsten Nachbarn in der Teilung haben müssen.
#:
#: Neun von zehn: Die Zellen am Rand eines Feldes haben weniger Nachbarn,
#: aber denselben Abstand zum nächsten; was fehlt, sind Ausreißer, wo das
#: Gitter eine Bohrung ausspart und die Zelle dahinter weiter weg liegt.
REGULAR_SHARE: Final = 0.9

#: Eine fehlende Zelle darf den Nachbarschaftsverbund nicht zerreißen.
#: Bis zur übernächsten Zelle bleiben Raster verbunden; erst größere Lücken
#: trennen Felder. Die anschließende Gitterprüfung behält ihre volle Strenge.
FIELD_NEIGHBOUR_STEPS: Final = 2

#: Wie weit ein Nachbarabstand von der Teilung abweichen darf — und zwei
#: Zellen in Tiefe, Breite und Mündungsfläche voneinander, um dieselbe zu
#: sein. Ein Zwanzigstel: Ein Netz aus einem Slicer-Export rundet auf
#: Tausendstel, ein Netz aus einem Scan gar nicht, und ein Kunde, der eine
#: Zelle ändert, ändert sie nicht um fünf Prozent.
SAME_MEASURE: Final = 0.05

#: Die feste Weltrichtung, nach der unter gleichen Zellen gewählt wird —
#: welche Lücke eines ganz umlaufenden Musters die Naht seiner Abwicklung
#: trägt, welche von gleich nahen Zellen sein Anker ist (RM-275).
#:
#: Um einen Zylinder herum sind alle Zellen gleich, und nichts am Muster
#: sagt, wo es beginnt; entscheiden kann nur etwas außerhalb davon. Bis zum
#: 27.09.2026 war es die erste Ebenenachse: Die Naht lag ihr gegenüber, und
#: am Gewürzdeckel lag dort genau eine Mulde — welcher Seite sie zufiel,
#: entschied das Vorzeichen einer Summe nahe null, und nach einem Schritt weit
#: weg stand die Mitte des Musters eine Zelle weiter. Jede Wahl auf einem
#: Kreis kippt irgendwo; die Kippe gehört dorthin, wo ein konstruiertes Muster
#: nicht liegt. Konstruiert wird in runden Winkeln zu den Weltachsen, und
#: diese Richtung (1, φ, φ²) mit dem Goldenen Schnitt φ steht zu keiner
#: Weltachse und keiner Ebene aus zwei davon in einem runden Winkel — um Z
#: und um X projiziert unter 58,28 Grad, um Y unter 69,09 Grad.
_GOLDEN: Final = (1.0 + math.sqrt(5.0)) / 2.0
_GOLDEN_LENGTH: Final = math.sqrt(1.0 + _GOLDEN**2 + _GOLDEN**4)
SEAM_DIRECTION: Final[tuple[float, float, float]] = (
    1.0 / _GOLDEN_LENGTH,
    _GOLDEN / _GOLDEN_LENGTH,
    _GOLDEN**2 / _GOLDEN_LENGTH,
)

#: Ab welcher Richtungsänderung eine Ecke des Mündungsumrisses zählt — fünf
#: Grad; alles darunter ist eine Naht zwischen zwei Dreiecken derselben Kante.
CORNER_DEGREES: Final = 5.0

#: Wie eng die Richtungen zum nächsten Nachbarn beieinander liegen müssen,
#: nachdem sie auf die Symmetrie des Gitters gefaltet sind — drei Grad.
SAME_DIRECTION_DEGREES: Final = 3.0

#: Ab welchem Verhältnis von Länge zu Breite eine Zelle ein Streifen ist —
#: eine Rippe oder eine Welle. Zwei: Ein Sechseck misst über Eck das
#: 1,15-Fache seiner Schlüsselweite, eine Raute des Kreuzrändels das
#: 1,41-Fache; beides ist kein Streifen.
RIB_ASPECT: Final = 2.0

#: Wie tief eine runde Zelle höchstens sein darf, als Vielfaches ihrer Breite,
#: um eine Noppe zu sein und keine Bohrung. Das Doppelte: Die kleinsten
#: Streuflecken des Rauschens (``texture_ops._noise``) sind 0,15 Teilungen
#: im Radius und drei Schichten tief — bei 2 mm Teilung 0,6 breit und 0,6
#: tief. Eine Kernbohrung für M3 ist 2,5 breit und 8 tief, das Dreifache.
ROUND_DEPTH: Final = 2.0

#: Ab wie vielen Ecken ein Umriss rund ist — zwölf, das Zwölfeck ist der
#: gröbste Kreis, den ``units.circle_point`` zeichnet.
ROUND_CORNERS: Final = 12

#: Wie viel der Wandfläche eines Streifens parallel zu seiner Achse stehen
#: muss, damit er eine Rippe ist und keine Welle. Vier Fünftel: Die
#: Stirnwände einer Rippe sind ihr Zehntel, die Wände einer Welle schwingen
#: alle.
STRAIGHT_SHARE: Final = 0.8

#: Ab welcher Deckung Streuzellen ein Voronoi-Feld sind statt Rauschen. Die
#: Hälfte: Voronoi-Zellen füllen ihr Feld bis auf die Wände dazwischen,
#: Streuflecken lassen den größeren Teil frei.
VORONOI_COVERAGE: Final = 0.5

#: Welche Merkmalsarten eine Zelle bilden — alles Kleine, das keine Sammelform
#: mit eigener Bedeutung ist. Langloch, Gewinde und Einschluss bleiben, was sie
#: sind; eine offene Kante ist ein Defekt.
CELL_KINDS: Final[frozenset[str]] = frozenset(
    {"face", "hole", "pin", "fillet", "curved_face", "cone", "sphere", "torus"}
)

#: Was der Kunde als Zelle wählen kann (:func:`grouped_pattern`) — dieselben
#: Arten wie in der Erkennung, dazu das offene Langloch, das eine am Rand
#: angeschnittene Zelle ist (:func:`_cell_material`).
GROUPABLE_KINDS: Final[tuple[str, ...]] = (*sorted(CELL_KINDS), "slot")

#: Welche Zellarten rund sind, wenn ihre Mitglieder es sagen.
ROUND_KINDS: Final[frozenset[str]] = frozenset({"hole", "pin", "sphere"})

#: Welche Merkmalsarten Träger eines Musters sein können, wenn sie groß genug
#: sind: eine ebene Fläche — oder ein Zylinder, um den es läuft.
CARRIER_KINDS: Final[frozenset[str]] = frozenset({"face", "pin"})

#: Die Muster, die eine Zelle benennen kann — die Namen aus
#: ``geom.texture_ops.PATTERNS``, damit *Merkmal ändern* dieselbe Operation
#: mit demselben Namen ruft, die das Muster erzeugt hätte. ``other`` ist ein
#: Gitter gleicher Zellen, deren Umriss keines davon ist.
STYLES: Final[tuple[str, ...]] = (
    "rib",
    "wave",
    "knurl_straight",
    "knurl_diamond",
    "hexagon",
    "dimple",
    "voronoi",
    "noise",
    "other",
)

#: Mit welchem Muster von ``apply_texture`` ein gelesener Stil neu gezeichnet
#: wird — jeder außer ``other``, und jeder unter seinem eigenen Namen.
GENERATOR_OF: Final[dict[str, str]] = {style: style for style in STYLES if style != "other"}

#: Um wie viel Grad das Gitter eines Musters gegen sein Feld gedreht liegt,
#: so wie ``texture_ops`` es zeichnet: Beim Kreuzrändel liegen die nächsten
#: Nachbarn diagonal, beim geraden Rändel laufen die Rippen unter 45 Grad.
_LATTICE_OFFSET: Final[dict[str, float]] = {"knurl_diamond": 45.0, "knurl_straight": 45.0}

#: Was die Teilung von ``apply_texture`` mit dem Nachbarabstand zu tun hat.
#:
#: Bei Wabe und Rippe ist die Teilung der Abstand zum nächsten Nachbarn. Beim
#: Kreuzrändel setzt ``texture_ops._diamonds`` die Rauten versetzt in halben
#: Teilungen — der nächste Nachbar liegt diagonal, im Abstand Teilung/√2.
#: Gemeldet wird die Teilung, mit der man das Muster neu erzeugt.
_PITCH_PER_SPACING: Final[dict[str, float]] = {"knurl_diamond": math.sqrt(2.0)}

#: In welchem Gitter ``apply_texture`` einen Stil zeichnet — und nur in dem
#: lässt er sich unter diesem Namen neu zeichnen. Ein Sechseck im
#: Quadratraster ist ein Gitter, das Solidon so nicht setzt (``other``); und
#: runde Zellen außerhalb des Wabengitters sind keine Noppen, sondern
#: Bohrungen im Raster — 25 Magnettaschen in fünf Reihen zu fünf behalten
#: ihre Bohrungshandlungen (Entscheidung RM-207, siehe den Modulkopf).
_GENERATOR_LATTICE: Final[dict[str, str]] = {
    "rib": "linear",
    "wave": "linear",
    "knurl_straight": "linear",
    "knurl_diamond": "square",
    "hexagon": "hexagonal",
    "dimple": "hexagonal",
}

#: Um welche Winkel das Feld gegen die gemessene Gitterrichtung gedreht sein
#: kann, ohne dass man es dem Gitter ansieht: Ein Wabengitter sieht alle
#: sechzig Grad gleich aus, das Feld darum nicht — eine Wabe unter neunzig
#: Grad gezeichnet meldet dieselbe Gitterrichtung wie eine unter dreißig.
#: Entscheiden tut die kleinste Hülle, denn ein Feld endet an seinem Rechteck.
_LATTICE_TURNS: Final[dict[str, tuple[float, ...]]] = {"hexagonal": (0.0, 60.0, 120.0)}

#: Die zwei Streifenstile, die nur ihre Wände unterscheiden — deckungsgleich
#: heißt bei ihnen: gleiche Breite auf demselben Träger, nicht gleiche Wand.
_STRIPS: Final[frozenset[str]] = frozenset({"rib", "wave"})


@dataclass(frozen=True, slots=True, eq=False)
class Cell:
    """Eine Zelle, am Netz gemessen — noch ohne Urteil, ob sie zu einem Muster gehört."""

    members: tuple[FeatureId, ...]
    face_indices: tuple[int, ...]
    carrier: tuple[FeatureId, ...]
    """Die Trägerfläche — die vordere bei einer durchgehenden Zelle."""
    frame: Frame
    """Die Abwicklung des Trägers, in der die Zelle gemessen ist."""
    normal: np.ndarray
    """Die Normale des Trägers an der Zelle — am Zylinder die radiale Richtung."""
    lift: float
    """Wo die Mündung in der Höhe der Abwicklung liegt."""
    centre: np.ndarray
    """Der Schwerpunkt der Mündung, in der Welt."""
    outline: np.ndarray
    """Die konvexe Hülle der Mündung, in den Achsen der Abwicklung."""
    flat_centre: np.ndarray
    """Der Schwerpunkt der Mündung, in denselben Achsen."""
    axis: np.ndarray
    """Die Richtung der längsten Umrisskante, in denselben Achsen — die Achse eines Streifens."""
    depth: float
    width: float
    """Die kleinste Breite der Mündung — Schlüsselweite eines Sechsecks, Stegbreite einer Rippe."""
    length: float
    """Die größte Ausdehnung der Mündung."""
    mouth_area: float
    corners: int
    round: bool
    raised: bool
    through: bool
    clipped: bool
    """Ein Rand des Körpers schneidet die Zelle an — sie ist ein Stück, kein Ganzes."""
    style: str
    straight: float
    """Welcher Anteil der Wandfläche parallel zur Achse steht — die Rippenfrage eines Streifens."""
    wall_area: float
    """Die Wandfläche, mit der ``straight`` gewichtet wird, wenn eine Reihe entscheidet."""


@dataclass(frozen=True, slots=True, eq=False)
class EdgePiece:
    """Ein Stück, das an mehr als einen Träger quer zueinander grenzt.

    Das ist entweder eine Ecke des Körpers — oder eine Zelle, die der Rand
    der Platte anschneidet, weil ein Feld bis zum Rand gezeichnet dort
    endet. Welcher der Träger ihre Mündung ist, weiß erst das Muster, zu dem
    sie gehört: sein Träger. Deshalb bleibt sie ungemessen, bis eines fragt.
    """

    indices: np.ndarray
    carriers: tuple[FeatureId, ...]


@dataclass(frozen=True, slots=True)
class Pattern:
    """Ein erkanntes Muster mit allem, was das Merkmal trägt."""

    style: str
    cells: tuple[Cell, ...]
    partial: tuple[Cell, ...]
    carrier: tuple[FeatureId, ...]
    frame: Frame
    """Die Abwicklung des Trägers — Feld, Mitte und Richtung liegen darin."""
    normal: Vec3
    """Die Normale des Trägers in der Mitte des Feldes."""
    direction: Vec3
    """Die Gitterrichtung in der Welt — zum nächsten Nachbarn, quer zu einer Rippe."""
    centre: Vec3
    """Die Mitte des Feldes, auf dem Träger."""
    pitch: float
    lattice: str
    lattice_angle: float
    """Die Gitterrichtung gegen die erste Ebenenachse in Grad — woraus ``direction`` entsteht."""
    width: float
    height: float
    angle: float
    """Die Drehung des Feldes gegen die erste Ebenenachse in Grad — für ``apply_texture``."""
    coverage: str
    """``whole_face``, wenn die Zellen den Träger bis an seinen Rand füllen, sonst ``rectangle``."""

    @property
    def face_indices(self) -> tuple[int, ...]:
        """Alle Dreiecke aller Zellen, ganze und angeschnittene."""
        return tuple(
            sorted(set().union(*(cell.face_indices for cell in (*self.cells, *self.partial))))
        )

    @property
    def members(self) -> frozenset[FeatureId]:
        """Die Merkmale, aus denen das Muster besteht — sie verschwinden aus dem Baum."""
        return frozenset(name for cell in (*self.cells, *self.partial) for name in cell.members)


def patterns_instead_of_cells(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Ersetzt die Zellen eines Musters durch das Muster.

    Der eine Aufruf, den :func:`app.core.perceive.features.detect` braucht —
    dieselbe Bauart wie ``slots_instead_of_half_bores``: suchen, einsetzen,
    verschlucken. Verschluckt wird über die Merkmalsnamen: Jedes Merkmal, das
    ganz in einer Zelle aufgeht, verschwindet aus dem Baum; die Träger bleiben.
    """
    patterns = find_patterns(mesh, found, check_cancelled=check_cancelled)
    if not patterns:
        return dict(found)
    swallowed: set[FeatureId] = set()
    for pattern in patterns:
        swallowed.update(pattern.members)
    kept = {name: feature for name, feature in found.items() if name not in swallowed}
    for number, pattern in enumerate(patterns, start=1):
        name = f"pattern_{number}"
        kept[name] = feature_of_pattern(name, pattern)
    return kept


def bound_to_its_surface(feature: Feature) -> bool:
    """Ob dieses Muster seine Herkunft trägt und an seine Oberfläche gebunden wird.

    Zwei Arten tun das: die selbst aufgebrachte Textur (``texture``) und die
    ausdrücklich zusammengefassten Einzelzellen (``grouped``, RM-504). Beide
    belegt nicht die Erkennung, sondern ein Schritt im Verlauf; ihre Dreiecke
    bindet jeder Folgeschritt neu an die verbliebene Oberfläche
    (:func:`rebound_textures`), auch unter den Erkennungsschwellen.
    """
    return feature.kind == "pattern" and bool(
        feature.params.get("texture") or feature.params.get("grouped")
    )


def without_pattern_cells(found: Mapping[FeatureId, Feature]) -> dict[FeatureId, Feature]:
    """Faltet nur vollständig belegte Einzelmerkmale eines vorhandenen Musters.

    Ein Merkmal zwischen zwei Mustern oder mit einem Rest außerhalb bleibt
    unverändert: Seine Maße gelten dem ganzen Merkmal, nicht einem Ausschnitt.
    """
    patches = [
        set(feature.face_indices)
        for feature in found.values()
        if feature.kind == "pattern" and feature.recognised
    ]
    return {
        name: feature
        for name, feature in found.items()
        if feature.kind == "pattern"
        or not feature.face_indices
        or not any(set(feature.face_indices) <= patch for patch in patches)
    }


def surface_triangles(
    mesh: MeshData,
    surface: MeshData,
    indices: Sequence[int] | None = None,
    *,
    candidates: Sequence[int] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[int, ...]:
    """Bindet ausschließlich vollständig belegte Dreiecke an die alte Oberfläche.

    Zwei Hüllquaderbäume begrenzen die Suche auf überdeckende Dreiecke. In der
    Dreiecksebene muss deren Vereinigung die gesamte neue Fläche abdecken;
    einzelne Proben könnten ein Loch zwischen ihren Punkten übersehen.
    """
    from collections import defaultdict

    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from app.core.geom.box_pairs import BoxTree, box_pairs_between
    from app.core.geom.mesh import stable_normals
    from app.core.geom.transform import along

    old = np.asarray(surface.raw.triangles, dtype=float)
    triangles = np.asarray(mesh.raw.triangles, dtype=float)
    selected = np.arange(len(old)) if indices is None else np.asarray(indices, dtype=np.int64)
    selected = selected[(selected >= 0) & (selected < len(old))]
    chosen = (
        np.arange(len(triangles)) if candidates is None else np.asarray(candidates, dtype=np.int64)
    )
    if not len(selected) or not len(chosen):
        return ()
    tolerance = units.weld_tolerance(max(mesh.bounds.diagonal, surface.bounds.diagonal))
    old_low, old_high = old.min(axis=1), old.max(axis=1)
    low, high = triangles.min(axis=1), triangles.max(axis=1)
    within = (low[chosen] <= old_high[selected].max(axis=0) + tolerance).all(axis=1)
    within &= (high[chosen] >= old_low[selected].min(axis=0) - tolerance).all(axis=1)
    chosen = chosen[within]
    if not len(chosen):
        return ()
    first = BoxTree(chosen, low - tolerance, high + tolerance)
    second = BoxTree(selected, old_low, old_high)
    normals = stable_normals(mesh.raw)[0]
    proven: set[int] = set()
    partners: dict[int, list[int]] = defaultdict(list)
    for current, previous in box_pairs_between(first, second):
        if check_cancelled is not None:
            check_cancelled()
        here, there = triangles[current], old[previous]
        offset = there - here[:, :1]
        axes = normals[current]
        distances = (
            offset[:, :, 0] * axes[:, None, 0]
            + offset[:, :, 1] * axes[:, None, 1]
            + offset[:, :, 2] * axes[:, None, 2]
        )
        coplanar = (np.abs(distances) <= tolerance).all(axis=1)
        current, previous = current[coplanar], previous[coplanar]
        here, there = here[coplanar], there[coplanar]
        edge_normal = np.cross(there[:, 1] - there[:, 0], there[:, 2] - there[:, 0])
        normal_length = np.sqrt((edge_normal * edge_normal).sum(axis=1))
        inside = normal_length > EPS_GEOM
        for corner in range(3):
            edge = there[:, (corner + 1) % 3] - there[:, corner]
            side = np.cross(edge[:, None], here - there[:, corner, None])
            signed = (
                side[:, :, 0] * edge_normal[:, None, 0]
                + side[:, :, 1] * edge_normal[:, None, 1]
                + side[:, :, 2] * edge_normal[:, None, 2]
            )
            margin = tolerance * normal_length * np.sqrt((edge * edge).sum(axis=1))
            inside &= (signed >= -margin[:, None]).all(axis=1)
        proven.update(int(index) for index in current[inside])
        for index, partner in zip(current, previous, strict=True):
            partners[int(index)].append(int(partner))
    found = list(proven)
    for number, (index, nearby) in enumerate(sorted(partners.items())):
        if check_cancelled is not None and number % 128 == 0:
            check_cancelled()
        if index in proven:
            continue
        normal = normals[index]
        corners = old[nearby]
        distances = along(corners - triangles[index, 0], normal)
        coplanar = corners[(np.abs(distances) <= tolerance).all(axis=1)]
        if not len(coplanar):
            continue
        axes = np.arange(3) != int(np.argmax(np.abs(normal)))
        area = Polygon(triangles[index][:, axes])
        cover = unary_union([Polygon(piece[:, axes]) for piece in coplanar])
        if cover.buffer(tolerance, join_style=2).covers(area):
            found.append(index)
    return tuple(sorted(found))


def bound_texture(mesh: MeshData, feature: Feature, indices: Sequence[int]) -> Feature:
    """Erneuert Zellzahl und Oberflächenbeleg einer ausdrücklich erzeugten Textur."""
    from app.core.perceive.features import _one_body

    body = _one_body(mesh).raw
    selected = np.asarray(indices, dtype=np.int64)
    count = len(_components(body, selected)) if len(selected) else 0
    params = {**feature.params, "count": count}
    if feature.params.get("grouped"):
        # Zusammengefasste Zellen zählen wie ein erkanntes Muster: ganze Zellen
        # und angeschnittene getrennt. Was ein Folgeschritt wegnimmt, geht
        # zuerst von den ganzen ab — welche es war, sagt die Zahl nicht.
        partial = min(int(feature.params.get("partial", 0)), count)
        params.update(count=count - partial, partial=partial)
    sources = {**feature.measure_sources, "count": "facets"}
    if len(selected) and (params.get("carrier") != "cylinder" or "carrier_diameter" in sources):
        frame = frame_for(feature)
        points = np.asarray(body.vertices)[np.unique(np.asarray(body.faces)[selected])]
        _flat, heights = frame.developed(points)
        level = float(frame.developed(np.asarray(params["centre"]))[1][0])
        params["cell_depth"] = float(
            heights.max() - level if params.get("mode") == "raised" else level - heights.min()
        )
        sources["cell_depth"] = "facets"
        if frame.kind == "plane" and params.get("mode") == "engraved":
            from app.core.geom.mesh import stable_normals
            from app.core.geom.transform import along

            normals = stable_normals(body)[0][selected]
            params["through"] = not bool(np.any(along(normals, frame.normal) > 1.0 - EPS_GEOM))
    return dataclasses.replace(
        feature,
        face_indices=tuple(int(index) for index in selected),
        recognised=True,
        params=params,
        measure_sources=sources,
        surface_patches=(),
    )


def rebound_textures(
    mesh: MeshData,
    known: Mapping[FeatureId, Feature],
    source: MeshData | None,
    *,
    proven: frozenset[FeatureId] = frozenset(),
    movement: Any = None,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Bindet erzeugte Texturen beider Körperarten an ihre verbliebene Oberfläche.

    Dazu gehören ausdrücklich zusammengefasste Zellen (:func:`bound_to_its_surface`):
    Auch sie belegt ein Schritt, nicht die Erkennung. ``proven`` nennt
    ausschließlich bereits am Ergebnis belegte Indizes. Alle übrigen benötigen
    ihre Dreiecke im Eingangsnetz, gegebenenfalls bewegt.
    """
    if source is not None and movement is not None:
        from app.core.geom.transform import apply

        source = apply(source, movement)
    result = {}
    for name, feature in known.items():
        if not bound_to_its_surface(feature):
            continue
        if name in proven:
            indices = feature.face_indices
        elif source is not None:
            indices = surface_triangles(
                mesh, source, feature.face_indices, check_cancelled=check_cancelled
            )
        else:
            indices = ()
        if indices:
            result[name] = bound_texture(mesh, feature, indices)
    return result


def without_texture_cells(
    found: Mapping[FeatureId, Feature],
    textures: Mapping[FeatureId, Feature],
    *,
    mesh: MeshData | None = None,
) -> dict[FeatureId, Feature]:
    """Texturdreiecke haben einen Eigentümer; übrige Trägerdreiecke bleiben erhalten."""
    owned = {index for feature in textures.values() for index in feature.face_indices}
    kept: dict[FeatureId, Feature] = {}
    for name, feature in found.items():
        remaining = tuple(index for index in feature.face_indices if index not in owned)
        if len(remaining) == len(feature.face_indices):
            kept[name] = feature
        elif remaining:
            from app.core.perceive.surfaces import clipped_patches

            rest = dataclasses.replace(
                feature,
                face_indices=remaining,
                surface_patches=clipped_patches(feature.surface_patches, remaining),
            )
            if mesh is not None and feature.kind == "face":
                from app.core.geom.mesh import stable_areas
                from app.core.perceive.features import _facet_centre

                selected = np.asarray(remaining, dtype=np.int64)
                area = float(stable_areas(mesh.raw, selected).sum())
                centre = _vec(_facet_centre(mesh.raw, selected))
                rest = dataclasses.replace(
                    rest,
                    params={**rest.params, "area": area, "centre": centre},
                    measure_sources={**rest.measure_sources, "area": "facets", "centre": "facets"},
                )
            elif mesh is not None and feature.kind == "pattern":
                rest = bound_texture(mesh, rest, remaining)
            kept[name] = rest
    return kept


def feature_of_pattern(name: str, pattern: Pattern) -> Feature:
    """Das Merkmal aus dem Fund — jede Zahl am Netz gemessen (``facets``)."""
    first = pattern.cells[0]
    depth = float(np.median([cell.depth for cell in pattern.cells]))
    width = float(np.median([cell.width for cell in pattern.cells]))
    sources: dict[str, MeasureSource] = {
        "pitch": "facets",
        "cell_width": "facets",
        "cell_depth": "facets",
        "centre": "facets",
        "normal": "facets",
        "direction": "facets",
        "width": "facets",
        "height": "facets",
        "area": "facets",
    }
    params: dict[str, Any] = {
        "style": pattern.style,
        "lattice": pattern.lattice,
        "count": len(pattern.cells),
        "partial": len(pattern.partial),
        "pitch": pattern.pitch,
        "cell_width": width,
        "cell_depth": depth,
        "mode": "raised" if first.raised else "engraved",
        "through": first.through,
        "centre": pattern.centre,
        "normal": pattern.normal,
        "direction": pattern.direction,
        "width": pattern.width,
        "height": pattern.height,
        "angle": pattern.angle,
        "coverage": pattern.coverage,
        "anchor": _anchor_of(pattern),
        "area": pattern.width * pattern.height,
        "carrier": pattern.frame.kind,
    }
    if pattern.frame.kind == "cylinder":
        # Achse und Durchmesser des Zylinders, um den es läuft — aus der
        # Einpassung des Stifts, wie bei ihm selbst. Die Mitte liegt auf dem
        # Zylinder, die Normale zeigt dort radial: Aus beiden entsteht die
        # Abwicklung wieder (:func:`frame_for`), mit der Naht gegenüber.
        params["carrier_axis"] = _vec(pattern.frame.normal)
        params["carrier_diameter"] = 2.0 * pattern.frame.radius
        sources["carrier_axis"] = "fit"
        sources["carrier_diameter"] = "fit"
    return Feature(
        id=name,
        kind="pattern",
        provenance="detected",
        measure_sources=sources,
        params=params,
        face_indices=pattern.face_indices,
    )


def _anchor_of(pattern: Pattern) -> Vec3:
    """Die Mitte der ganzen Zelle, die der Mitte des Musters am nächsten liegt.

    Beim Neuzeichnen setzt ``texture_ops.tool_in_outline`` eine Zelle genau
    hierhin: Sonst begänne das Gitter am Feldrand neu, die Zellen rückten um
    einen Bruchteil der Teilung, und aus sechs Rippen wurden fünf und zwei
    Stummel — bei unveränderter Teilung (Review, 22.09.2026).
    """
    centre = np.asarray(pattern.centre, dtype=float)
    distances = [float(np.linalg.norm(cell.centre - centre)) for cell in pattern.cells]
    # **Gleich nahe Zellen unterscheidet die Rundung nicht** (RM-275): Hat das
    # Feld eine gerade Zellenzahl, liegt seine Mitte zwischen zwei oder vier
    # Zellen, und die nächste war die mit dem kleineren Rundungsrest — nach
    # einem Schritt weit weg eine andere. Unter den gleich nahen entscheidet
    # die feste Weltrichtung, wie für die Naht.
    reach = min(distances) + SAME_MEASURE * pattern.pitch
    tied = [
        cell for cell, distance in zip(pattern.cells, distances, strict=True) if distance <= reach
    ]
    towards = np.asarray(SEAM_DIRECTION, dtype=float)
    chosen = max(tied, key=lambda cell: float((cell.centre - centre) @ towards))
    return _vec(chosen.centre)


@dataclass(frozen=True, slots=True)
class _CellReading:
    """Die Zellen eines Körpers, einmal gelesen — für die Erkennung und für die Zusammenfassung."""

    body: Any
    owned: Mapping[FeatureId, Feature]
    measure: _CellMeasure
    cells: list[Cell]
    pieces: list[EdgePiece]


def find_patterns(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Pattern]:
    """Alle Muster an diesem Körper, nach Lage sortiert (§21.2)."""
    reading = _read_cells(mesh, found, check_cancelled=check_cancelled)
    if reading is None:
        return []
    body, owned, measure = reading.body, reading.owned, reading.measure
    cells, pieces = reading.cells, reading.pieces
    if len(cells) < min(MIN_CELLS, MIN_STRIPS) and len(pieces) < MIN_STRIPS:
        return []
    if check_cancelled is not None:
        check_cancelled()

    carriers = {
        name: _carrier_outline(body, owned[name])
        for name in {cell.carrier[0] for cell in cells}
        | {name for piece in pieces for name in piece.carriers if owned[name].kind == "pin"}
    }
    patterns: list[Pattern] = []
    taken: set[int] = set()
    for candidates in _congruent_groups(cells):
        if check_cancelled is not None:
            check_cancelled()
        # Was ein größeres Muster schon als angeschnittene Zelle genommen hat,
        # bildet kein eigenes — die sieben gleich abgeschnittenen Sechsecke am
        # Rand eines Feldes sind sein Saum und kein zweites Gitter.
        group = [cell for cell in candidates if id(cell) not in taken]
        if not group or len(group) < _least_cells(group[0]):
            continue
        pattern = _lattice_of(group)
        if pattern is None:
            continue
        if pattern == "bores":
            # Runde Zellen in einem Gitter, das keine Noppentextur ist:
            # Bohrungen im Raster. Sie bleiben Bohrungen — und sie stehen
            # auch keiner Streuung mehr zur Verfügung, denn ein Rauschen
            # hat kein Raster.
            taken.update(id(cell) for cell in group)
            continue
        patterns.append(_absorb(pattern, cells, pieces, measure, taken, carriers))
    for group in _scatter_groups([cell for cell in cells if id(cell) not in taken]):
        if check_cancelled is not None:
            check_cancelled()
        pattern = _scatter_of(group)
        if pattern is None:
            continue
        patterns.append(_absorb(pattern, cells, pieces, measure, taken, carriers))
    patterns.extend(_rim_patterns(pieces, measure, taken, carriers, owned))
    # Nach der Mitte, und wo zwei Muster sie teilen — zwei Lochkreise um
    # dieselbe Achse —, nach Teilung, Feld und Zellenzahl, zuletzt nach den
    # Ecken: dieselbe Regel wie für jede andere Nummer
    # (:func:`app.core.perceive.features.numbering_order`).
    from app.core.perceive.features import NUMBERING_DIGITS, _corner_key, numbering_order

    order = numbering_order(
        len(patterns),
        (
            (lambda index: patterns[index].centre, NUMBERING_DIGITS),
            (
                lambda index: (
                    patterns[index].pitch,
                    patterns[index].width,
                    patterns[index].height,
                ),
                NUMBERING_DIGITS,
            ),
            (
                lambda index: (len(patterns[index].cells), len(patterns[index].partial)),
                NUMBERING_DIGITS,
            ),
        ),
        lambda index: _corner_key(body, np.asarray(patterns[index].face_indices)),
    )
    return [patterns[index] for index in order]


def _read_cells(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    chosen: Collection[FeatureId] = frozenset(),
    check_cancelled: Callable[[], None] | None = None,
) -> _CellReading | None:
    """Die Zellen und Randstücke dieses Körpers, am Netz vermessen — oder ``None``.

    ``chosen`` sind Merkmale, die der Kunde ausdrücklich als Zellen gewählt
    hat (:func:`grouped_pattern`): Sie gelten als Zellmaterial, gleich wie groß
    sie sind, und tragen deshalb keine Zelle. Alles andere entscheidet dieselbe
    Regel wie in der Erkennung — eine Zelle ist, was klein zwischen ihren
    Trägern liegt —, und ohne ``chosen`` ist das die Erkennung, Bit für Bit.
    """
    body = mesh.raw
    triangle_count = len(body.faces)
    owned = {
        name: feature
        for name, feature in found.items()
        if feature.face_indices and (_cell_material(feature) or feature.kind == "face")
    }
    # Träger ist eine große ebene Fläche — oder ein großer Zylinder: Ein
    # Rändel läuft um einen Griff, und der ist für die Erkennung ein Stift.
    if triangle_count == 0 or not any(feature.kind in CARRIER_KINDS for feature in owned.values()):
        return None
    # Jedes Dreieck kennt sein Merkmal; -1 heißt: gehört zu keinem.
    names = list(owned)
    owner = np.full(triangle_count, -1, dtype=np.int64)
    triangle_areas = np.asarray(body.area_faces, dtype=float)
    areas = np.zeros(len(names), dtype=float)
    for index, name in enumerate(names):
        indices = np.asarray(owned[name].face_indices, dtype=np.int64)
        indices = indices[(indices >= 0) & (indices < triangle_count)]
        owner[indices] = index
        areas[index] = float(triangle_areas[indices].sum())
    # **Kandidat ist, was klein ist.** Eine Zelle hat höchstens den
    # MIN_CELLS-ten Teil ihres Trägers, sonst gäbe es nicht MIN_CELLS davon —
    # und der Träger ist höchstens die größte Trägerfläche des Körpers.
    largest = max(
        areas[index] for index, name in enumerate(names) if owned[name].kind in CARRIER_KINDS
    )
    limit = largest / MIN_CELLS
    small = np.array(
        [
            name in chosen or (areas[index] <= limit and _cell_material(owned[name]))
            for index, name in enumerate(names)
        ]
    )
    # Ein Stift, der mit einem zweiten die Achse teilt und in Streifen
    # zerfällt, ist Boden oder Kopf der Zellen und kein Träger
    # (:func:`_cell_floors`).
    for index in _cell_floors(body, owned, names, small):
        small[index] = True
    candidate_features = np.flatnonzero(small)
    measure = _CellMeasure(body, owned, names, owner)
    # **Ein Stift als Träger nimmt beim Einpassen Wandstücke mit** — kleine
    # Dreiecke quer zum Mantel, die keine ebene Fläche wurden und über die
    # Nachbarschaft in seinen Fleck gerieten. Sie gehören der Zelle: Was
    # nicht auf dem Zylinder liegt, ist kein Träger. Mit ihnen im Stift
    # zerfiel eine Rille nach dem Ändern in drei Stücke (22.09.2026).
    centroids = np.asarray(body.triangles_center, dtype=float)
    for index, name in enumerate(names):
        if owned[name].kind != "pin" or small[index]:
            continue
        frame = measure.frame_of(name)
        if frame is None:
            continue
        own = np.flatnonzero(owner == index)
        _flat, heights = frame.developed(centroids[own])
        owner[own[np.abs(heights) > units.MAX_FACET_SAG]] = -1
    # **Und umgekehrt: Was auf einem Träger liegt, ist Träger** — auch ohne
    # Namen. Eine Boolesche Rechnung lässt auf dem Mantel Splitter, die kein
    # Merkmal nahm; als Zellmaterial verbanden sie zwei Waben zu einer Zelle
    # mit acht Ecken, die zu keinem Gitter passte (22.09.2026). Gemessen an
    # der Mitte des Dreiecks, nicht an seiner Normalen: Die eines Splitters
    # zeigt irgendwohin. Eine Wand liegt mit ihrer Mitte ein Drittel der
    # Tiefe unter dem Träger — und was flacher ist als das, ist keine Zelle.
    unowned = np.flatnonzero(owner < 0)
    if len(unowned):
        for index, name in enumerate(names):
            if owned[name].kind not in CARRIER_KINDS or small[index]:
                continue
            frame = measure.frame_of(name)
            if frame is None:
                continue
            # Die Höhe des Trägers: Am Zylinder ist sie der Radius selbst, die
            # Mitte eines Stifts liegt auf seiner Achse. Auf der Ebene die
            # Mitte der Fläche.
            level = 0.0
            if frame.kind == "plane":
                centre = np.asarray(owned[name].params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
                level = float(frame.developed(centre)[1][0])
            _flat, heights = frame.developed(centroids[unowned])
            on_carrier = np.abs(heights - level) <= max(frame.sag, units.MAX_FACET_SAG / 4.0)
            owner[unowned[on_carrier]] = index
            unowned = unowned[~on_carrier]
            if len(unowned) == 0:
                break
    # **Auch, was kein Merkmal ist, kann Zellwand sein.** Die Wände einer
    # Welle sind acht schmale Streifen je Periode, und die Flächensuche nennt
    # sie nicht; die Wände eines Voronoi-Felds stehen zur Hälfte ohne Namen
    # da. Eine Zelle besteht aus allem Kleinen zwischen ihren Trägern — was
    # kein Träger und keine Sammelform ist, gehört dazu.
    candidate = (owner < 0) | np.isin(owner, candidate_features)
    # **Gezählt wird das Zellmaterial, nicht die Merkmale darunter.** Hier
    # stand die Frage, ob es wenigstens MIN_CELLS kleine Merkmale gibt — vor
    # den zwei Schritten darüber, die dem Stift sein Wandmaterial nehmen. Ein
    # Kreuzrändel um einen Griff besteht aus Dreiecken ohne Namen: Nach dem
    # Ändern auf 4 mm lagen sie im Stift, sieben Verrundungen standen daneben,
    # und die Suche endete, bevor sie die Zellen sah (Fund aus „formops",
    # 23.09.2026).
    if not bool(candidate.any()):
        return None
    carrier_feature = np.array(
        [owned[name].kind in CARRIER_KINDS and not small[index] for index, name in enumerate(names)]
    )
    if check_cancelled is not None:
        check_cancelled()

    cells, pieces = _cells(
        body, measure, candidate, carrier_feature, check_cancelled=check_cancelled
    )
    return _CellReading(body=body, owned=owned, measure=measure, cells=cells, pieces=pieces)


def grouped_pattern(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    chosen: Collection[FeatureId],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Pattern:
    """Das Muster aus ausdrücklich gewählten Einzelmerkmalen (RM-504).

    **Die Wahl ersetzt die Mindestzahl, nicht die Messung.** Unter den
    Schwellen der Erkennung ist ein Feld ohne Erzeugerwissen mehrdeutig —
    vier Waben, drei Rillen, ein Ornament aus ungleichen Zellen —, und eine
    pauschale Absenkung nähme Funktionsbohrungen, Magnettaschen und Schrift
    mit. Hier hat der Kunde gesagt, was zusammengehört. Was eine Zelle ist,
    sagt trotzdem dieselbe Lesung wie in der Erkennung (:func:`_read_cells`):
    alles Kleine zwischen ihren Trägern, auch ungewählte Wände, die an einer
    gewählten Zelle hängen.

    **Gemessen wird wie ein erkanntes Muster**: Liegen deckungsgleiche Zellen
    in einem Gitter, bekommt das Muster Stil, Gitter und Teilung — einen
    Stil von ``apply_texture`` nur in dessen Gitter. Sonst ist es ein fremdes
    Feld (``other``), entfernbar und nicht neu zu zeichnen. Runde tiefe oder
    durchgehende Zellen sind Bohrungen und bleiben es; sie behalten ihre
    Handlungen, und für mehrere gleiche gibt es *Auf alle anwenden*.

    Was nicht geht, sagt ein Satz mit Rückweg (Regel 17): zu wenige Zellen,
    ein Merkmal ohne Zelle auf einer Fläche, eine Bohrung, zwei Träger oder
    erhabene neben vertieften Zellen.
    """
    wanted = frozenset(chosen)
    usable = {
        name
        for name in wanted
        if name in found and _cell_material(found[name]) and found[name].face_indices
    }
    if usable != wanted:
        raise group_refusal("not_a_cell", wanted - usable)
    reading = _read_cells(mesh, found, chosen=wanted, check_cancelled=check_cancelled)
    if reading is None:
        raise group_refusal("not_a_cell", wanted)
    measure = reading.measure
    if check_cancelled is not None:
        check_cancelled()

    cells = [cell for cell in reading.cells if wanted.intersection(cell.members)]
    pieces = [
        piece
        for piece in reading.pieces
        if wanted.intersection(
            measure.names[int(index)]
            for index in np.unique(measure.owner[piece.indices])
            if index >= 0
        )
    ]
    carriers = {cell.carrier[0] for cell in cells}
    if not cells and pieces:
        # Lauter Randstücke um einen Stift — die Riffelung eines Deckels
        # (:func:`_rim_patterns`): gemessen am gemeinsamen Stift als ganze Zellen.
        common = set.intersection(*(set(piece.carriers) for piece in pieces))
        pins = sorted(name for name in common if reading.owned[name].kind == "pin")
        if pins:
            pin = pins[0]
            if pin not in measure.seamed:
                measure.seam_between(pin, [piece.indices for piece in pieces])
            cells = [
                cell for piece in pieces if (cell := measure(piece.indices, (pin,))) is not None
            ]
            pieces = []
            carriers = {pin}
    if len(carriers) > 1:
        raise group_refusal("two_carriers", wanted)
    clipped: list[Cell] = []
    if carriers:
        carrier = next(iter(carriers))
        for piece in pieces:
            if carrier not in piece.carriers:
                continue
            cell = measure(piece.indices, (carrier,), clipped=True)
            if cell is not None:
                clipped.append(cell)
    covered = {name for cell in (*cells, *clipped) for name in cell.members}
    missing = wanted - covered
    if missing:
        # Bohrung heißt hier, was ``_measure_cell`` als Bohrung stehen lässt:
        # durchgehend oder tiefer als ``ROUND_DEPTH`` mal so breit. Eine flache
        # Mulde, die an keiner Fläche mündet, ist kein Bohrungsfall — sie
        # bekommt den Satz über die fehlende Zelle.
        bores = {name for name in missing if _a_bore(found[name])}
        if bores:
            raise group_refusal("bores", bores)
        raise group_refusal("not_a_cell", missing)
    whole = [cell for cell in cells if not cell.clipped]
    clipped.extend(cell for cell in cells if cell.clipped)
    if len(whole) < LEAST_GROUPED_CELLS:
        raise group_refusal("too_few", wanted)
    first = whole[0]
    if any(cell.raised != first.raised or cell.through != first.through for cell in whole):
        raise group_refusal("two_sides", wanted)

    pattern: Pattern | None = None
    if all(_same_cell(first, cell) for cell in whole[1:]):
        if first.style in _STRIPS:
            found_rows = _rows_of(whole, least=LEAST_GROUPED_CELLS)
            walls = sum(cell.wall_area for cell in whole)
            straight = (
                sum(cell.straight * cell.wall_area for cell in whole) / walls
                if walls > 0.0
                else 1.0
            )
            style = "rib" if straight >= STRAIGHT_SHARE else "wave"
        else:
            found_rows = _grid_of(np.array([cell.flat_centre for cell in whole], dtype=float))
            style = first.style
        if found_rows is not None:
            lattice, angle, spacing = found_rows
            expected = _GENERATOR_LATTICE.get(style)
            if expected is not None and expected != lattice:
                style = "other"
            pitch = spacing * _PITCH_PER_SPACING.get(style, 1.0)
            pattern = _field(first, whole, (), lattice, angle, pitch, style)
    if pattern is None:
        pattern = _scatter_field(first, whole, (), "other")
    if clipped:
        pattern = _with_partial(pattern, clipped)
    return _with_coverage(pattern, _carrier_outline(reading.body, reading.owned[first.carrier[0]]))


def _a_bore(feature: Feature) -> bool:
    """Ob dieses runde Merkmal nach der Regel der Zellen eine Bohrung bleibt.

    Dieselbe Grenze wie :func:`_measure_cell`: durchgehend, oder tiefer als
    :data:`ROUND_DEPTH` mal so breit. Ohne gemessene Tiefe bleibt eine Bohrung
    eine Bohrung — im Zweifel bleibt ein Merkmal, was es war.
    """
    if feature.kind not in ROUND_KINDS:
        return False
    if feature.params.get("through"):
        return True
    depth, diameter = feature.params.get("depth"), feature.params.get("diameter")
    if not isinstance(depth, int | float) or not isinstance(diameter, int | float):
        return feature.kind == "hole"
    return float(depth) > float(diameter) * ROUND_DEPTH * (1.0 + SAME_MEASURE)


def group_refusal(reason: str, names: Collection[FeatureId]) -> Any:
    """Die Absage einer Zusammenfassung (:func:`grouped_pattern`) — Satz und Weg.

    Zwei Sätze, der zweite ist der Weg; ``values["features"]`` nennt die
    Merkmale, an denen es liegt, damit die Oberfläche sie zeigen kann. Die
    Beschränkung trägt den Grund (``group_<Grund>``), wie ``local_error``
    ihn für die örtliche Suche trägt.
    """
    from app.core.errors import CANCEL, CORRECT_INPUT, ValidationError

    values = {"features": tuple(sorted(names))}
    suggestions = (CORRECT_INPUT, CANCEL)
    refusals = {
        "too_few": ValidationError(
            field="at_features",
            constraint="group_too_few",
            detail=_(
                "Ein Muster braucht mindestens zwei Zellen. Wählen Sie im Objektbaum weitere "
                "gleiche Merkmale dazu."
            ),
            values=values,
            suggestions=suggestions,
        ),
        "not_a_cell": ValidationError(
            field="at_features",
            constraint="group_not_a_cell",
            detail=_(
                "Mindestens ein gewähltes Merkmal liegt nicht als Zelle auf einer Fläche. "
                "Nehmen Sie es aus der Auswahl."
            ),
            values=values,
            suggestions=suggestions,
        ),
        "bores": ValidationError(
            field="at_features",
            constraint="group_bores",
            detail=_(
                "Bohrungen bleiben Bohrungen und behalten ihre eigenen Handlungen. Nehmen Sie "
                "sie aus der Auswahl."
            ),
            values=values,
            suggestions=suggestions,
        ),
        "two_carriers": ValidationError(
            field="at_features",
            constraint="group_two_carriers",
            detail=_(
                "Die gewählten Zellen liegen auf verschiedenen Flächen. Fassen Sie die Zellen "
                "jeder Fläche einzeln zusammen."
            ),
            values=values,
            suggestions=suggestions,
        ),
        "two_sides": ValidationError(
            field="at_features",
            constraint="group_two_sides",
            detail=_(
                "Erhabene und vertiefte Zellen sind zwei Muster. Fassen Sie beide getrennt "
                "zusammen."
            ),
            values=values,
            suggestions=suggestions,
        ),
    }
    return refusals[reason]


def _cell_floors(
    body: Any,
    owned: Mapping[FeatureId, Feature],
    names: Sequence[FeatureId],
    small: np.ndarray,
) -> list[int]:
    """Welche großen Stifte Böden oder Köpfe von Zellen sind und keine Träger.

    **Vertiefte Rillen um einen Griff haben einen Boden, und der ist wieder
    ein Zylinder** — derselbe für alle Rillen, eine Tiefe unter dem Mantel.
    Die Einpassung legt seine Streifen zu einem Stift zusammen, und der ist
    so groß wie der Mantel selbst: Bei Rillen mit Teilung 5,9 um Ø 30 standen
    ein Stift Ø 30 und einer Ø 28,4 nebeneinander, jede Rille berührte beide,
    und die Suche fand null Zellen und sechzehn Randstücke (Fund aus
    „formops", 23.09.2026). Dasselbe gilt für die Köpfe erhabener Rippen.

    Getrennt wird am Zusammenhang: Der Träger reicht über das Feld hinaus
    und hängt als **ein** Stück zusammen, die Böden sind so viele Streifen,
    wie es Rillen gibt. Von zwei Stiften um dieselbe Achse ist deshalb der
    zersplitterte Zellmaterial — mindestens :data:`MIN_STRIPS` Stücke und
    mehr als der andere. Reicht das Muster über die ganze Länge, zerfallen
    beide gleich; dann lässt die Geometrie beide Lesarten zu (vertiefte
    Rillen auf dem äußeren Zylinder, erhabene Rippen auf dem inneren), und
    Träger ist der äußere — der Durchmesser, den der Griff hat.
    """
    import trimesh

    pins = [
        index
        for index, name in enumerate(names)
        if owned[name].kind == "pin" and not small[index] and owned[name].face_indices
    ]
    if len(pins) < 2:
        return []
    adjacency = np.asarray(body.face_adjacency, dtype=np.int64)
    pieces: dict[int, int] = {}
    for index in pins:
        faces = np.asarray(owned[names[index]].face_indices, dtype=np.int64)
        inside = adjacency[np.isin(adjacency, faces).all(axis=1)]
        pieces[index] = len(
            trimesh.graph.connected_components(inside, nodes=faces, min_len=1, engine="scipy")
        )
    floors: set[int] = set()
    for position, first in enumerate(pins):
        for second in pins[position + 1 :]:
            one, other = owned[names[first]].params, owned[names[second]].params
            axis = np.asarray(one.get("axis", (0.0, 0.0, 0.0)), dtype=float)
            if abs(float(axis @ np.asarray(other.get("axis", (0.0, 0.0, 0.0)), dtype=float))) < (
                1.0 - SAME_MEASURE
            ):
                continue
            radius = float(one.get("diameter", 0.0)) / 2.0
            offset = np.asarray(other.get("centre", (0.0, 0.0, 0.0)), dtype=float) - np.asarray(
                one.get("centre", (0.0, 0.0, 0.0)), dtype=float
            )
            beside = offset - axis * float(offset @ axis)
            if float(np.linalg.norm(beside)) > SAME_MEASURE * radius + units.MAX_FACET_SAG:
                continue
            if max(pieces[first], pieces[second]) < MIN_STRIPS:
                continue
            if pieces[first] != pieces[second]:
                floors.add(first if pieces[first] > pieces[second] else second)
                continue
            inner = float(one.get("diameter", 0.0)) < float(other.get("diameter", 0.0))
            floors.add(first if inner else second)
    return sorted(floors)


def _cell_material(feature: Feature) -> bool:
    """Ob dieses Merkmal Teil einer Zelle sein kann.

    Die Arten aus :data:`CELL_KINDS` — und ein **offenes** Langloch: Eine Noppe,
    die der Rand der Platte anschneidet, ist für die Langlochsuche ein zum
    Rand offener Ausschnitt (§21.1), und die läuft vor dem Muster. Im Feld
    eines Musters ist so ein Ausschnitt eine angeschnittene Zelle; ein
    geschlossenes Langloch bleibt, was es ist.
    """
    return feature.kind in CELL_KINDS or (
        feature.kind == "slot" and bool(feature.params.get("open", False))
    )


def _least_cells(cell: Cell) -> int:
    """Wie viele Geschwister diese Zelle braucht — runde mehr als eckige, Streifen weniger."""
    if cell.round:
        return MIN_ROUND_CELLS
    if cell.style in {"rib", "wave"}:
        return MIN_STRIPS
    return MIN_CELLS


def _rim_patterns(
    pieces: Sequence[EdgePiece],
    measure: _CellMeasure,
    taken: set[int],
    carriers: Mapping[FeatureId, np.ndarray],
    owned: Mapping[FeatureId, Feature],
) -> list[Pattern]:
    """Muster aus lauter Randstücken um einen Stift — die Riffelung eines Deckels.

    **Reicht jede Zelle bis an eine Stirnfläche, gibt es keine ganze.** Die
    Mulden um den Rand eines Schraubdeckels, die Rippen eines Knopfes über
    seine ganze Höhe: Jede grenzt an den Stift und an eine Stirnfläche, ist
    damit ein Randstück (:class:`EdgePiece`) und wartet auf ein Muster, das
    sie an seinem Träger nachmisst — und das es ohne ganze Zellen nie gibt.
    Am Deckel des Gewürzregals aus dem Korpus: 24 Mulden um Ø 40, sieben
    Zellen, 25 Randstücke und kein Muster (23.09.2026).

    Gemessen wird jedes Stück an seinem Stift als ganze Zelle — der Schnitt
    durch die Stirnfläche ist dort die Gestalt der Zelle und kein Feldrand —,
    und danach gilt dieselbe Frage wie für jede Zellgruppe: deckungsgleich,
    mindestens so viele wie ihr Stil verlangt, im Gitter.
    """
    from app.core.geom.transform import along

    around: dict[FeatureId, list[EdgePiece]] = {}
    spans: dict[FeatureId, tuple[np.ndarray, float, float]] = {}
    for piece in pieces:
        if id(piece) in taken:
            continue
        for name in piece.carriers:
            if owned[name].kind != "pin":
                continue
            if name not in spans:
                axis = np.asarray(owned[name].params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
                first, last = _axial_span(
                    measure.points,
                    measure.triangles[np.asarray(owned[name].face_indices, dtype=np.int64)],
                    axis,
                )
                spans[name] = (axis, first, last)
            axis, low, high = spans[name]
            reach = along(measure.points[measure.triangles[piece.indices]].reshape(-1, 3), axis)
            # Nur, was in der Länge des Stifts liegt: Eine Rippe, die über die
            # Stirnfläche hinausragt, lässt sich dort weder stopfen noch
            # abnehmen — entfernt blieben ihre Stummel stehen.
            if reach.min() < low - units.MAX_FACET_SAG or reach.max() > high + units.MAX_FACET_SAG:
                continue
            around.setdefault(name, []).append(piece)
    found: list[Pattern] = []
    for name in sorted(around):
        group = around[name]
        if len(group) < MIN_STRIPS:
            continue
        # Die Naht zwischen die Stücke, wie zwischen ganze Zellen
        # (:meth:`_CellMeasure.seam_between`) — sonst lag sie der ersten
        # Ebenenachse gegenüber und schnitt am Gewürzdeckel eine Mulde, die
        # nach dem Vorzeichen einer Summe nahe null der einen oder der
        # anderen Seite zufiel (RM-275).
        if name not in measure.seamed:
            measure.seam_between(name, [piece.indices for piece in group])
        measured = [(piece, measure(piece.indices, (name,))) for piece in group]
        cells = [cell for _piece, cell in measured if cell is not None]
        for candidates in _congruent_groups(cells):
            fresh = [cell for cell in candidates if id(cell) not in taken]
            if not fresh or len(fresh) < _least_cells(fresh[0]):
                continue
            pattern = _lattice_of(fresh)
            if pattern is None or pattern == "bores":
                continue
            found.append(_absorb(pattern, cells, (), measure, taken, carriers))
            chosen = {id(cell) for cell in (*pattern.cells, *pattern.partial)}
            taken.update(id(piece) for piece, cell in measured if id(cell) in chosen)
    return found


def _absorb(
    pattern: Pattern,
    cells: Sequence[Cell],
    pieces: Sequence[EdgePiece],
    measure: _CellMeasure,
    taken: set[int],
    carriers: Mapping[FeatureId, np.ndarray],
) -> Pattern:
    """Angeschnittene Zellen dazunehmen, die Deckung bestimmen, alles als vergeben merken.

    Angeschnitten heißt zweierlei: vom Rand des **Feldes** (eine Zelle mit
    fremdem Umriss auf demselben Träger) oder vom Rand des **Körpers** (ein
    Randstück, das auch an eine Seitenfläche grenzt — gemessen mit dem
    Träger dieses Musters als Mündung). Beide zählen als ``partial``.
    """
    chosen = {id(cell) for cell in (*pattern.cells, *pattern.partial)}
    leftovers = [
        cell
        for cell in cells
        if id(cell) not in taken and id(cell) not in chosen and _belongs_to(cell, pattern)
    ]
    for piece in pieces:
        if id(piece) in taken or pattern.carrier[0] not in piece.carriers:
            continue
        cell = measure(piece.indices, pattern.carrier, clipped=True)
        if cell is not None and _belongs_to(cell, pattern):
            leftovers.append(cell)
            taken.add(id(piece))
    if leftovers:
        pattern = _with_partial(pattern, leftovers)
    pattern = _with_coverage(pattern, carriers[pattern.carrier[0]])
    taken.update(chosen)
    taken.update(id(cell) for cell in leftovers)
    return pattern


# --- Zellen ---------------------------------------------------------------------


def _cells(
    body: Any,
    measure: _CellMeasure,
    candidate: np.ndarray,
    carrier_feature: np.ndarray,
    *,
    check_cancelled: Callable[[], None] | None,
) -> tuple[list[Cell], list[EdgePiece]]:
    """Zusammenhängende Stücke aus Kandidatenmerkmalen, am Netz vermessen.

    Dazu die Randstücke (:class:`EdgePiece`), die an Träger quer zueinander
    grenzen — vermessen werden sie erst, wenn ein Muster sie an seinem
    Träger als angeschnittene Zellen fragt. Auf einem Zylinder liegt vor dem
    Messen die Naht der Abwicklung fest (:meth:`_CellMeasure.seam_between`):
    Wo sie aufreißt, entscheiden alle Stücke des Trägers zusammen.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    owned, names, owner = measure.owned, measure.names, measure.owner
    adjacency = np.asarray(body.face_adjacency, dtype=np.int64)
    if adjacency.size == 0:
        return [], []
    triangle_count = len(body.faces)
    inside = candidate[adjacency[:, 0]] & candidate[adjacency[:, 1]]
    inner = adjacency[inside]
    graph = coo_matrix(
        (np.ones(len(inner), dtype=np.int8), (inner[:, 0], inner[:, 1])),
        shape=(triangle_count, triangle_count),
    )
    labels = connected_components(graph, directed=False)[1]
    labels = np.where(candidate, labels, -1)
    # Die Nähte nach draußen: genau eine Seite gehört zu einer Zelle.
    crossing = candidate[adjacency[:, 0]] != candidate[adjacency[:, 1]]
    border = adjacency[crossing]
    if len(border) == 0:
        return [], []
    cell_side = np.where(candidate[border[:, 0]], border[:, 0], border[:, 1])
    outside = np.where(candidate[border[:, 0]], border[:, 1], border[:, 0])
    border_label = labels[cell_side]
    order = np.argsort(border_label, kind="stable")
    border_label, outside = border_label[order], outside[order]
    starts = np.searchsorted(border_label, np.unique(border_label))
    ends = np.append(starts[1:], len(border_label))
    outside_of = {
        int(border_label[start]): outside[start:end]
        for start, end in zip(starts, ends, strict=True)
    }

    whole: list[tuple[np.ndarray, tuple[FeatureId, ...]]] = []
    pieces: list[EdgePiece] = []
    present = np.flatnonzero(candidate)
    by_label = np.argsort(labels[present], kind="stable")
    sorted_labels = labels[present][by_label]
    cell_labels, first_rows = np.unique(sorted_labels, return_index=True)
    last_rows = np.append(first_rows[1:], len(sorted_labels))
    for label, start, end in zip(cell_labels, first_rows, last_rows, strict=True):
        if check_cancelled is not None:
            check_cancelled()
        neighbours = outside_of.get(int(label))
        if neighbours is None or len(neighbours) == 0:
            continue
        owners = np.unique(owner[neighbours])
        # Eine Zelle grenzt nur an ihre Träger — große ebene Flächen. Sonst
        # ist es eine Wand neben einer Bohrung und kein Muster.
        if owners.size == 0 or int(owners.min()) < 0 or not carrier_feature[owners].all():
            continue
        indices = np.sort(present[by_label[start:end]])
        carrier = _carriers_of(owners, names, owned, measure.normals)
        if carrier is None:
            # Träger quer zueinander: eine Ecke — oder eine Zelle am Rand.
            pieces.append(EdgePiece(indices, tuple(names[int(index)] for index in owners)))
            continue
        whole.append((indices, carrier))
    cylinders = sorted({carrier[0] for _, carrier in whole if owned[carrier[0]].kind == "pin"})
    for name in cylinders:
        measure.seam_between(name, [indices for indices, carrier in whole if carrier[0] == name])
    cells: list[Cell] = []
    for indices, carrier in whole:
        if check_cancelled is not None:
            check_cancelled()
        cell = measure(indices, carrier)
        if cell is not None:
            cells.append(cell)
    return cells, pieces


class _CellMeasure:
    """Das Netz einmal gelesen, dann je Zelle gemessen — auch später für die Randstücke.

    Je Träger eine Abwicklung (:class:`Frame`), einmal gebaut: die Ebene
    einer Fläche, oder der Zylinder eines Stifts mit seiner Naht.
    """

    def __init__(
        self,
        body: Any,
        owned: Mapping[FeatureId, Feature],
        names: Sequence[FeatureId],
        owner: np.ndarray,
    ) -> None:
        self.owned = owned
        self.names = names
        self.owner = owner
        self.triangles = np.asarray(body.faces, dtype=np.int64)
        self.points = np.asarray(body.vertices, dtype=float)
        self.triangle_normals = np.asarray(body.face_normals, dtype=float)
        self.triangle_areas = np.asarray(body.area_faces, dtype=float)
        self.normals = {
            name: np.asarray(feature.params.get("normal", (0.0, 0.0, 0.0)), dtype=float)
            for name, feature in owned.items()
            if feature.kind == "face"
        }
        self.frames: dict[FeatureId, Frame] = {}
        self.seamed: set[FeatureId] = set()
        """Die Zylinder, deren Naht schon zwischen Zellen gelegt ist (:meth:`seam_between`)."""

    def __call__(
        self, indices: np.ndarray, carrier: tuple[FeatureId, ...], *, clipped: bool = False
    ) -> Cell | None:
        through = False
        if len(carrier) == 2:
            first, second = self.normals.get(carrier[0]), self.normals.get(carrier[1])
            if first is None or second is None:
                return None
            # Zwei Träger sind nur dann eine durchgehende Zelle, wenn sie
            # einander gegenüberliegen; sonst ist es eine Ecke.
            if float(first @ second) > -1.0 + SAME_MEASURE:
                return None
            through = True
            carrier = _front_carrier(carrier, self.normals, self.owned)
        frame = self.frame_of(carrier[0])
        if frame is None:
            return None
        return _measure_cell(
            indices,
            self.owner,
            self.names,
            self.owned,
            self.triangles,
            self.points,
            self.triangle_normals,
            self.triangle_areas,
            frame,
            carrier,
            through=through,
            clipped=clipped,
        )

    def frame_of(self, name: FeatureId) -> Frame | None:
        """Die Abwicklung dieses Trägers — beim ersten Mal gebaut, danach dieselbe."""
        frame = self.frames.get(name)
        if frame is None:
            frame = self._frame_for(name, reference=None)
            if frame is not None:
                self.frames[name] = frame
        return frame

    def _frame_for(self, name: FeatureId, reference: np.ndarray | None) -> Frame | None:
        feature = self.owned[name]
        if feature.kind == "pin":
            axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 0.0)), dtype=float)
            radius = float(feature.params.get("diameter", 0.0)) / 2.0
            if float(np.linalg.norm(axis)) < EPS_GEOM or radius <= EPS_GEOM:
                return None
            axis = axis / float(np.linalg.norm(axis))
            if reference is None:
                reference = _plane_axes(axis)[0]
            frame = Frame.cylinder(
                axis,
                np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float),
                radius,
                reference=reference,
                sag=0.0,
            )
            indices = np.asarray(feature.face_indices, dtype=np.int64)
            sag = _facet_sag(frame, self.points, self.triangles[indices])
            return dataclasses.replace(frame, sag=sag)
        normal = self.normals.get(name)
        if normal is None or float(np.linalg.norm(normal)) < EPS_GEOM:
            return None
        return Frame.plane(normal)

    def seam_between(self, name: FeatureId, pieces: Sequence[np.ndarray]) -> None:
        """Die Naht eines Zylinders in die größte Lücke zwischen diesen Stücken legen.

        Ein Feld, das nicht ganz herumläuft, darf nicht an der Naht in zwei
        Hälften zerfallen — dann fände die Gittersuche zwei Felder, und das
        Rechteck um beide wäre der ganze Umfang. Die Lücke ist am Winkel der
        Stücke gemessen; bei einem ganz umlaufenden Feld ist jede Lücke eine
        Wand breit, und die Naht liegt dann in einer davon — in welcher, sagt
        :func:`_seam_reference`, nicht die Rundung.
        """
        frame = self._frame_for(name, reference=None)
        if frame is None or frame.kind != "cylinder" or not pieces:
            return
        centroids = np.array(
            [self.points[self.triangles[indices]].reshape(-1, 3).mean(axis=0) for indices in pieces]
        )
        flat, _heights = frame.developed(centroids)
        reference = _seam_reference(flat[:, 0] / frame.radius, _seam_toward(frame))
        x_axis = frame.x_axis * math.cos(reference) + frame.y_axis * math.sin(reference)
        seamed = self._frame_for(name, reference=x_axis)
        if seamed is not None:
            self.frames[name] = seamed
            self.seamed.add(name)


def _seam_toward(frame: Frame) -> float:
    """Unter welchem Winkel der Abwicklung :data:`SEAM_DIRECTION` liegt.

    Gemessen an der Welt, nicht an der Achse: Dieselbe Richtung, um die
    andersherum eingepasste Achse abgewickelt, liegt an derselben Stelle des
    Mantels. Steht die Achse genau in dieser Richtung, gilt die erste Achse.
    """
    towards = np.asarray(SEAM_DIRECTION, dtype=float)
    across = towards - frame.normal * float(towards @ frame.normal)
    if float(np.linalg.norm(across)) < EPS_GEOM:
        return 0.0
    return math.atan2(float(across @ frame.y_axis), float(across @ frame.x_axis))


def _seam_reference(angles: np.ndarray, toward: float) -> float:
    """Der Winkel, dem die Naht gegenüberliegen soll: die Mitte der größten Lücke plus π.

    **Gleich große Lücken unterscheidet die Rundung nicht** (RM-275). Ein ganz
    umlaufendes Muster hat nur solche, und die größte war die mit dem
    größten Rundungsrest — am Gewürzdeckel nach einem Schritt weit weg eine
    andere, und die Mitte des Musters sprang um eine Zelle. Gleich groß heißt
    bis auf :data:`SAME_MEASURE` der größten; unter ihnen trägt die Naht die
    Lücke, deren Mitte ``toward`` am nächsten liegt (:data:`SEAM_DIRECTION`).
    Ein Feld, das nicht ganz herumläuft, hat eine Lücke, die größer ist als
    alle anderen, und die Naht liegt wie zuvor in ihr.
    """
    ordered = np.sort(np.mod(angles, 2.0 * math.pi))
    gaps = np.diff(np.append(ordered, ordered[0] + 2.0 * math.pi))
    middles = ordered + gaps / 2.0
    candidates = np.flatnonzero(gaps >= float(gaps.max()) * (1.0 - SAME_MEASURE))
    away = np.abs((middles[candidates] - toward + math.pi) % (2.0 * math.pi) - math.pi)
    chosen = int(candidates[int(np.argmin(away))])
    return float(middles[chosen]) + math.pi


def _carriers_of(
    owners: np.ndarray,
    names: Sequence[FeatureId],
    owned: Mapping[FeatureId, Feature],
    normals: Mapping[FeatureId, np.ndarray],
) -> tuple[FeatureId, ...] | None:
    """Die Träger einer ganzen Zelle: einer, oder zwei ebene einander gegenüber.

    Alles andere — Träger quer zueinander, ein Zylinder neben einer Fläche —
    ist kein Fall für hier: eine Ecke des Körpers, oder eine Zelle, die der
    Rand anschneidet. Die bleibt ein :class:`EdgePiece`, bis ein Muster sie
    an seinem Träger fragt.
    """
    if owners.size > 2:
        return None
    carrier = tuple(names[int(index)] for index in owners)
    if any(owned[name].kind != "face" for name in carrier):
        return carrier if len(carrier) == 1 else None
    first = normals[carrier[0]]
    if float(np.linalg.norm(first)) < EPS_GEOM:
        return None
    if owners.size == 2:
        second = normals[carrier[1]]
        if float(np.linalg.norm(second)) < EPS_GEOM:
            return None
        alignment = float(first @ second) / (
            float(np.linalg.norm(first)) * float(np.linalg.norm(second))
        )
        if alignment > -1.0 + SAME_MEASURE:
            return None
    return carrier


def _measure_cell(
    indices: np.ndarray,
    owner: np.ndarray,
    names: Sequence[FeatureId],
    owned: Mapping[FeatureId, Feature],
    triangles: np.ndarray,
    points: np.ndarray,
    triangle_normals: np.ndarray,
    triangle_areas: np.ndarray,
    frame: Frame,
    carrier: tuple[FeatureId, ...],
    *,
    through: bool = False,
    clipped: bool = False,
) -> Cell | None:
    """Tiefe, Mündung, Seite und Umriss einer Zelle — in der Abwicklung ihres Trägers."""
    # Nur, was ein Merkmal besitzt: Ein unbesessenes Dreieck trägt -1, und
    # ``names[-1]`` wäre das letzte Merkmal der Liste — die kleinste Fläche
    # des Körpers, die dann mit dem Muster aus dem Baum verschwände, auch
    # wenn sie an einer Tasche am anderen Ende der Platte liegt.
    corners = points[triangles[indices]].reshape(-1, 3)
    # Der Träger liegt dort, wo die Zelle mündet: an ihren äußersten Punkten
    # in der Höhe der Abwicklung, denn die Zelle liegt ganz auf einer Seite.
    flat, heights = frame.developed(corners)
    top, bottom = float(heights.max()), float(heights.min())
    depth = top - bottom
    # Flacher als die Facettenabweichung ist keine Zelle, sondern Netz: der
    # Saum, den ein Stopfen um einen Zylinder auf den Facetten lässt, die
    # Haut einer nicht ganz bündigen Rechnung. Eine gedruckte Zelle ist
    # mindestens eine Schicht tief, und die ist ein Vielfaches davon.
    if depth <= units.MAX_FACET_SAG:
        return None
    # Eine durchgehende Zelle ist ein Loch — vertieft, ohne Frage. Ihre Wände
    # liegen symmetrisch zwischen beiden Trägern, und ein Mittel darüber
    # entschiede nach Rundungsrauschen. Sonst entscheidet die Seite, auf der
    # die Fläche der Zelle liegt: mit den Dreiecksflächen gewichtet, denn die
    # Wände sind am Fuß in viele kleine Dreiecke zerschnitten, wo sie die
    # Facetten eines Zylinders treffen — ungewichtet zog das 413 erhabene
    # Rauten eines Kreuzrändels unter die Mitte (22.09.2026).
    centroids = frame.developed(points[triangles[indices]].mean(axis=1))[1]
    weights = triangle_areas[indices]
    level = float(centroids @ weights / max(float(weights.sum()), EPS_GEOM))
    raised = not through and level > (top + bottom) / 2.0
    plane = bottom if raised else top
    # Am Zylinder liegen die Ecken der Mündung auf seinen Facetten, und die
    # hängen um ihre Sehnenabweichung unter dem Radius: so weit gehört zur Mündung.
    tolerance = _flat_tolerance(depth) + frame.sag
    # Ein Dreieck, das mit allen drei Ecken auf dem Träger liegt, ist keine
    # Wand und kein Boden, sondern Träger: ein Splitter, den eine Boolesche
    # Rechnung auf dem Mantel ließ und den kein Merkmal nahm. Als Teil der
    # Zelle zöge er ihre Mündung breit — 1,52 mm Rillen maßen 2,09
    # (22.09.2026). Die Zelle selbst hat auf dem Träger keine Fläche: Sie
    # mündet dort.
    lid = (np.abs(heights.reshape(-1, 3) - plane) <= tolerance).all(axis=1)
    if lid.any():
        indices = indices[~lid]
        if len(indices) == 0:
            return None
        flat = flat.reshape(-1, 3, 2)[~lid].reshape(-1, 2)
        heights = heights.reshape(-1, 3)[~lid].ravel()
    members = tuple(
        sorted({names[int(index)] for index in np.unique(owner[indices]) if index >= 0})
    )
    mouth = flat[np.abs(heights - plane) <= tolerance]
    if len(mouth) < 3:
        return None
    # In den Achsen der Abwicklung, aber vom Weltursprung beziehungsweise
    # von der Achse aus — so liegen die Umrisse aller Zellen eines Trägers im
    # selben Blatt und lassen sich vergleichen.
    hull = _convex_hull(mouth)
    if hull is None:
        return None
    outline = _Outline.of(hull)
    width, length = outline.calipers()
    if width <= EPS_GEOM:
        return None
    area = outline.area
    corner_count = outline.corners
    flat_centre = outline.centroid
    centre = frame.world(flat_centre, plane)[0]
    normal = frame.normal_at(flat_centre)
    is_round = corner_count >= ROUND_CORNERS or any(
        _round_member(owned[name], frame) for name in members
    )
    if is_round and (through or depth > width * ROUND_DEPTH * (1.0 + SAME_MEASURE)):
        # Eine runde Zelle, die durchgeht oder tief ist, ist eine Bohrung und
        # bleibt eine — siehe den Modulkopf.
        return None
    axis = outline.longest_edge
    straight, wall_area = _straight_share(
        indices, triangle_normals, triangle_areas, normal, frame.tangent(flat_centre, axis)
    )
    return Cell(
        members=members,
        face_indices=tuple(int(index) for index in indices),
        carrier=carrier,
        frame=frame,
        normal=normal,
        lift=plane,
        centre=centre,
        outline=hull,
        flat_centre=flat_centre,
        axis=axis,
        depth=depth,
        width=width,
        length=length,
        mouth_area=area,
        corners=corner_count,
        round=is_round,
        raised=raised,
        through=through,
        clipped=clipped,
        style=_style_of(outline, corner_count, width, length, is_round, straight=straight),
        straight=straight,
        wall_area=wall_area,
    )


def _round_member(feature: Feature, frame: Frame) -> bool:
    """Ob dieses Mitglied die Zelle rund macht — ein Zapfen, eine Mulde, eine Kugel.

    Um einen Zylinder nicht, wenn es dessen Achse teilt: Die Krone einer
    erhabenen Raute ist um den Träger gebogen und passt als Zylinderstück
    mit derselben Achse — ein ``pin`` der Erkennung, aber kein Zapfen. Siebzig
    Rauten hießen so Noppen (22.09.2026).
    """
    if feature.kind not in ROUND_KINDS:
        return False
    if frame.kind == "cylinder" and feature.kind in {"hole", "pin"}:
        axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 0.0)), dtype=float)
        if abs(float(axis @ frame.normal)) >= 1.0 - SAME_MEASURE:
            return False
    return True


def _front_carrier(
    carrier: tuple[FeatureId, ...],
    normals: Mapping[FeatureId, np.ndarray],
    owned: Mapping[FeatureId, Feature],
) -> tuple[FeatureId, ...]:
    """Welche der zwei Seiten einer durchgehenden Zelle die Vorderseite ist.

    Die nach oben weisende — in Drucklage ist das die Seite, die man sieht;
    bei gleicher Neigung die größere Fläche. Eine Regel, keine Messung, und
    deshalb steht sie hier und nicht in einer Zahl.
    """
    from app.core.perceive.features import AREA_DIGITS

    # Die Fläche gerundet wie im Nummernschlüssel: Zwei gleich große Seiten
    # unterscheiden sich im Netz in der zwölften Stelle, und dann entschiede
    # diese Stelle statt des Namens.
    ranked = sorted(
        carrier,
        key=lambda name: (
            -round(float(normals[name][2]), 6),
            -round(float(owned[name].params.get("area", 0.0)), AREA_DIGITS),
            name,
        ),
    )
    return (ranked[0],)


def _flat_tolerance(depth: float) -> float:
    """Wie weit ein Punkt neben der Trägerebene liegen darf, um in ihr zu sein."""
    return max(units.MAX_FACET_SAG, depth * SAME_MEASURE * 0.2)


def _plane_axes(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Zwei Achsen in der Ebene — dieselbe Wahl wie ``sketch.planes.frame_of``.

    Über ``units.plane_axes``, nicht über die Skizze: Die Wahrnehmung liest
    keine Skizze (``tests/test_core_package_direction.py``). Gemerkt je
    Normale: Alle Zellen eines Trägers fragen dieselbe.
    """
    return _plane_axes_of((float(normal[0]), float(normal[1]), float(normal[2])))


@functools.lru_cache(maxsize=64)
def _plane_axes_of(normal: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray]:
    axes = units.plane_axes(normal)
    if axes is None:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
    return np.asarray(axes[0], dtype=float), np.asarray(axes[1], dtype=float)


def _straight_share(
    indices: np.ndarray,
    triangle_normals: np.ndarray,
    triangle_areas: np.ndarray,
    normal: np.ndarray,
    axis_world: np.ndarray,
) -> tuple[float, float]:
    """Welcher Anteil der Wandfläche parallel zur Streifenachse steht — und wie viel Wand es ist.

    Wände sind die Dreiecke quer zum Träger; parallel zur Achse heißt: ihre
    Normale steht senkrecht auf ihr. Eine Rippe hat das an ihren zwei langen
    Wänden, eine Welle nirgends. Die Wandfläche kommt mit, weil eine Reihe
    von Streifen als Ganzes entscheidet, ob sie Rippen sind (``_lattice_of``):
    Ein kurzer, am Feldrand schräg abgeschnittener Streifen hat mehr Stirn
    als Flanke und sähe allein wie eine Welle aus. ``axis_world`` ist die
    Streifenachse in der Welt — am Zylinder die Tangente an der Zelle.
    """
    normals_here = triangle_normals[indices]
    walls = np.abs(normals_here @ normal) < 0.5
    if not walls.any():
        return 1.0, 0.0
    parallel = np.abs(normals_here[walls] @ axis_world) <= units.exact_sin_degrees(CORNER_DEGREES)
    total = float(triangle_areas[indices][walls].sum())
    if total <= EPS_GEOM:
        return 1.0, 0.0
    return float(triangle_areas[indices][walls][parallel].sum()) / total, total


# --- Die Abwicklung des Trägers ----------------------------------------------------


class FacetPolygon(NamedTuple):
    """Das Vieleck eines Zylinderträgers im Querschnitt: seine Facetten und ihre Ecken.

    Je Facette der Winkel ihrer Normalen um die Achse (aufsteigend, im
    Bogenmaß), ihr Abstand von der Achse und ``corners``: wie weit hinter
    ihrer Normalen sie an die nächste Facette stößt (:func:`_facet_corners`).
    Die Ecke liegt am **Schnitt** der beiden Facetten, nicht auf der
    Winkelhalbierenden — dort lägen zwei Facetten mit verschiedenem Abstand um
    dessen Unterschied auseinander.
    """

    angles: np.ndarray
    offsets: np.ndarray
    corners: np.ndarray


class EndPlane(NamedTuple):
    """Eine Stirnfläche des Trägers in der Welt: ``normal · p = offset``."""

    normal: np.ndarray
    offset: float


@dataclass(frozen=True, slots=True, eq=False)
class Frame:
    """Die Abwicklung eines Trägers: zwei Achsen darin, eine Höhe darüber.

    Auf einer **Ebene** sind die Achsen die Ebenenachsen zur Normalen
    (``units.plane_axes``, vom Weltursprung aus), die Höhe der Abstand zur
    Ebene — so vergleichen sich die Umrisse aller Zellen eines Trägers im
    selben Blatt. Um einen **Zylinder** — ein Rändel um einen Griff,
    ``apply_texture`` mit ``wrap="cylinder"`` — sind es Umfang und Achse:
    Ein Punkt liegt bei ``u = R·θ`` und ``v`` entlang der Achse, die Höhe ist
    sein Abstand zum Radius. Dieselbe Rechnung misst dieselbe Zelle auf
    beiden, und das Gitter liegt in der Abwicklung, wo ``texture_ops.wrapped``
    es hingelegt hat. Was in der Abwicklung gerade ist, ist um den Zylinder
    gebogen: :meth:`placed` biegt einen flachen Körper zurück.

    Die Naht der Abwicklung liegt der ersten Achse gegenüber (``θ = ±π``).
    Bei der Erkennung wählt :func:`_seam_reference` die erste Achse so, dass
    die Naht in die größte Lücke zwischen den Zellen fällt — bei gleich großen
    in die an :data:`SEAM_DIRECTION`, auch um Randstücke. Ein gelesenes
    Muster trägt danach seine Normale als erste Achse: Die Naht liegt seiner
    Mitte gegenüber, und ein Feld, das nicht ganz herumläuft, hat dort seine
    Lücke (:func:`frame_for`).
    """

    kind: str
    """``plane`` oder ``cylinder``."""
    normal: np.ndarray
    """Die Normale der Ebene — oder die Achse des Zylinders."""
    x_axis: np.ndarray
    y_axis: np.ndarray
    origin: np.ndarray
    """Ein Punkt auf der Achse; bei der Ebene der Weltursprung."""
    radius: float = 0.0
    sag: float = 0.0
    """Wie weit die Facetten des Trägers unter seiner Fläche liegen — null bei der Ebene."""
    facets: FacetPolygon | None = None
    """Die Facettenebenen eines Zylinders: Winkel um die Achse, sortiert, Abstände und Ecken.

    Ein Netz hat keinen Kreis, es hat ein Vieleck. Wer einen Körper auf den
    Mantel legt — den Stopfen, der eine Zelle füllt —, legt ihn auf dieses
    Vieleck (:meth:`world` mit ``faceted``), nicht auf den Kreis: Bündig mit
    dem Kreis stünde er zwischen zwei Ecken um die Sehnenabweichung über der
    Facette, und die Stufe am Rand hätte Wände quer zur Achse — hundert
    Dreiecke von 0,7 mm², und der Mantel war danach kein Zylinder mehr
    (22.09.2026). ``None``, wenn der Träger nicht bekannt oder nicht in
    Facetten gelesen ist.
    """
    span: tuple[float, float] | None = None
    """Wie weit der Träger entlang der Achse reicht, in der zweiten Achse der Abwicklung.

    Am Zylinder von Stirnfläche zu Stirnfläche (:func:`_axial_span`) — dort
    endet ein Stopfen, der eine Zelle füllt. ``None``, wenn der Träger nicht
    bekannt ist.
    """
    ends: tuple[EndPlane | None, EndPlane | None] | None = None
    """Die Stirnflächen an beiden Enden von :attr:`span`, wie die Erkennung sie gemessen hat.

    Ein Stopfen, der durch eine Stirnfläche läuft, endet **in** ihr
    (:meth:`world` mit ``faceted``), nicht quer zur gemessenen Achse: Die steht
    an einer STL um ihr Rauschen schräg — fern vom Ursprung 1,9·10⁻⁸ rad —,
    und ein Stopfenende quer zu ihr lag an der Unterseite eines Deckels bis
    4·10⁻⁷ mm neben ihr. Unter jeder Rille blieb danach eine eigene Fläche
    stehen (RM-404). ``None`` je Ende, an dem keine ebene Stirnfläche steht.
    """

    @classmethod
    def plane(cls, normal: np.ndarray) -> Frame:
        unit = np.asarray(normal, dtype=float)
        unit = unit / max(math.hypot(*unit), EPS_GEOM)
        x_axis, y_axis = _plane_axes(unit)
        return cls(kind="plane", normal=unit, x_axis=x_axis, y_axis=y_axis, origin=np.zeros(3))

    @classmethod
    def cylinder(
        cls,
        axis: np.ndarray,
        origin: np.ndarray,
        radius: float,
        *,
        reference: np.ndarray,
        sag: float,
    ) -> Frame:
        """Um diese Achse, mit ``reference`` als erster Achse — quer zur Achse gestellt."""
        unit = np.asarray(axis, dtype=float)
        unit = unit / max(math.hypot(*unit), EPS_GEOM)
        x_axis = np.asarray(reference, dtype=float)
        x_axis = x_axis - unit * units.dot3(x_axis, unit)
        length = math.hypot(*x_axis)
        x_axis = _plane_axes(unit)[0] if length < EPS_GEOM else x_axis / length
        return cls(
            kind="cylinder",
            normal=unit,
            x_axis=x_axis,
            y_axis=np.cross(unit, x_axis),
            origin=np.asarray(origin, dtype=float),
            radius=radius,
            sag=sag,
        )

    @property
    def clearance(self) -> float:
        """Um wie viel ein Werkzeug über die Fläche hinausreichen muss, um sie sicher zu treffen.

        Auf der Ebene um nichts. Am Zylinder um die Sehnenabweichung seiner
        Facetten und die des zurückgebogenen Werkzeugs
        (``texture_ops.BEND_SAG``): Ein Boden, der bündig mit dem Radius
        läge, träfe die Facetten nur an ihren Ecken.
        """
        if self.kind == "plane":
            return 0.0
        from app.core.geom.texture_ops import BEND_SAG

        return self.sag + BEND_SAG

    def developed(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Punkte in die Abwicklung: ``(n, 2)`` Lage und ``(n,)`` Höhe.

        Am Zylinder um das Mittel der Punkte abgewickelt: Eine Zelle über
        der Naht bleibt ein Stück, ihre Punkte liegen dann jenseits von
        ``±π·R`` — im Blatt des Trägers an derselben Stelle. Wer viele Zellen
        auf einmal fragt, fragt sie deshalb einzeln.
        """
        from app.core.geom.transform import along as lying_along

        points = np.atleast_2d(np.asarray(points, dtype=float))
        if self.kind == "plane":
            flat = np.column_stack(
                (lying_along(points, self.x_axis), lying_along(points, self.y_axis))
            )
            return flat, lying_along(points, self.normal)
        # Lagen, Winkel und Mitte ohne BLAS und ohne die Winkelfunktionen der
        # Plattform (RM-187): Die Abwicklung wird zu Geometrie, wenn ein Muster
        # neu gezeichnet oder ein Stopfen auf den Mantel gelegt wird.
        offset = points - self.origin
        along = lying_along(offset, self.normal)
        radial = offset - np.outer(along, self.normal)
        reach = np.linalg.norm(radial, axis=1)
        cosines, sines = lying_along(radial, self.x_axis), lying_along(radial, self.y_axis)
        theta = stable_arctan2(sines, cosines)
        middle = float(stable_arctan2(float(sines.sum()), float(cosines.sum())))
        theta = middle + (theta - middle + math.pi) % (2.0 * math.pi) - math.pi
        return np.column_stack((theta * self.radius, along)), reach - self.radius

    def world(
        self, flat: np.ndarray, height: np.ndarray | float, *, faceted: bool = False
    ) -> np.ndarray:
        """Punkte der Abwicklung zurück in die Welt: ``(n, 3)``.

        Mit ``faceted`` liegt die Höhe null auf den Facetten des Trägers
        statt auf seinem Kreis (:attr:`facets`); ohne bekannte Facetten
        bleibt es der Kreis. Ein Punkt an einem Ende von :attr:`span` liegt
        dann auch in der Stirnfläche dort (:attr:`ends`).
        """
        flat = np.atleast_2d(np.asarray(flat, dtype=float))
        heights = np.broadcast_to(np.asarray(height, dtype=float), (len(flat),))
        if self.kind == "plane":
            return (
                np.outer(flat[:, 0], self.x_axis)
                + np.outer(flat[:, 1], self.y_axis)
                + np.outer(heights, self.normal)
            )
        theta = flat[:, 0] / self.radius
        sines, cosines = periodic_sin_cos(theta)
        radial = np.outer(cosines, self.x_axis) + np.outer(sines, self.y_axis)
        base = self._facet_radius(theta) if faceted else self.radius
        points = (
            self.origin + np.outer(flat[:, 1], self.normal) + radial * (base + heights)[:, None]
        )
        return self._onto_the_ends(points, flat[:, 1]) if faceted else points

    def _onto_the_ends(self, points: np.ndarray, levels: np.ndarray) -> np.ndarray:
        """Punkte an einem Ende von :attr:`span` entlang der Achse in die Stirnfläche dort.

        Am Ende heißt: auf ``EPS_GEOM`` genau dort, wo :func:`_within_span` den
        Umriss des Stopfens abschneidet. Entlang der Achse, nicht senkrecht zur
        Stirnfläche — so bleibt ein Punkt auf seiner Facette, denn die Facetten
        laufen parallel zur Achse.
        """
        if self.ends is None or self.span is None:
            return points
        from app.core.geom.transform import along

        placed = np.array(points, dtype=float)
        for end, edge in zip(self.ends, self.span, strict=True):
            if end is None:
                continue
            chosen = np.abs(levels - edge) <= EPS_GEOM
            facing = units.dot3(end.normal, self.normal)
            if not chosen.any() or abs(facing) <= EPS_GEOM:
                continue
            reach = (end.offset - along(placed[chosen], end.normal)) / facing
            placed[chosen] = placed[chosen] + reach[:, None] * self.normal[None, :]
        return placed

    def _facet_borders(self, along: np.ndarray) -> np.ndarray:
        """Die Facettengrenzen als Lagen in der Abwicklung, so weit ``along`` reicht.

        Eine Grenze liegt an der Ecke zweier Facetten (:attr:`FacetPolygon.corners`).
        Über die Naht hinaus fortgesetzt: Eine Zelle über der Naht liegt in
        der Abwicklung jenseits von ``±π·R``, und dort liegen dieselben
        Facetten noch einmal.
        """
        if self.facets is None or len(along) == 0:
            return np.zeros(0)
        angles, _offsets, corners = self.facets
        borders = angles + corners if len(angles) > 1 else np.zeros(0)
        turns = np.concatenate([borders - 2.0 * math.pi, borders, borders + 2.0 * math.pi])
        positions = turns * self.radius
        low, high = float(along.min()), float(along.max())
        return positions[(positions > low + EPS_GEOM) & (positions < high - EPS_GEOM)]

    def _facet_radius(self, theta: np.ndarray) -> np.ndarray | float:
        """Der Abstand der Facette von der Achse an diesen Winkeln — der Kreis, wo keine ist.

        Die Facette eines Punktes ist die, in deren Abschnitt zwischen ihren
        beiden Ecken er liegt (:attr:`FacetPolygon.corners`). Liegt ihre
        Normale weiter als eine Facettenbreite weg, deckt der Träger den
        Winkel nicht, und es gilt der Kreis.
        """
        if self.facets is None:
            return self.radius
        angles, offsets, corners = self.facets
        wrapped = (theta + math.pi) % (2.0 * math.pi) - math.pi
        after = np.searchsorted(angles, wrapped) % len(angles)
        before = (after - 1) % len(angles)
        past = (wrapped - angles[before]) % (2.0 * math.pi)
        chosen = np.where(past >= corners[before], after, before)
        gap = np.abs((angles[chosen] - wrapped + math.pi) % (2.0 * math.pi) - math.pi)
        step = float(np.median(np.diff(angles))) if len(angles) > 1 else math.pi
        away = periodic_sin_cos(wrapped - angles[chosen])[1]
        base = offsets[chosen] / np.maximum(away, EPS_GEOM)
        return np.where(gap <= step, base, self.radius)

    def normal_at(self, flat: np.ndarray) -> np.ndarray:
        """Die Normale des Trägers an dieser Stelle der Abwicklung."""
        if self.kind == "plane":
            return self.normal
        theta = float(flat[0]) / self.radius
        return self.x_axis * units.exact_cos(theta) + self.y_axis * units.exact_sin(theta)

    def tangent(self, flat: np.ndarray, direction: np.ndarray) -> np.ndarray:
        """Eine Richtung der Abwicklung als Richtung in der Welt, an dieser Stelle."""
        if self.kind == "plane":
            return self.x_axis * float(direction[0]) + self.y_axis * float(direction[1])
        theta = float(flat[0]) / self.radius
        around = -self.x_axis * units.exact_sin(theta) + self.y_axis * units.exact_cos(theta)
        return around * float(direction[0]) + self.normal * float(direction[1])

    def placed(self, body: Any, *, faceted: bool = False) -> Any:
        """Ein flacher Körper aus der Abwicklung in die Welt — am Zylinder gebogen.

        Gebogen werden die Ecken; damit auch die Flächen dazwischen dem
        Zylinder folgen, teilt der exakte Netzkern vorher jede Kante
        (``texture_ops.refined_for_bending`` — dieselbe Teilung, mit der
        ``apply_texture`` sein Feld um den Zylinder legt). ``faceted`` legt
        die Höhe null auf die Facetten des Trägers (:attr:`facets`).
        """
        import trimesh

        if self.kind == "cylinder":
            from app.core.geom.texture_ops import refined_for_bending

            body = refined_for_bending(MeshData.of(body), self.radius, self.sag).raw
            if faceted and self.facets is not None:
                # Geteilt an jeder Facettengrenze: Ein Dreieck, das über eine
                # reichte, läge mit seinen Ecken auf zwei Ebenen und mit seiner
                # Mitte unter beiden — eine Delle von der Sehnenabweichung,
                # und die Vereinigung ließe ihre Kante als Stufe stehen.
                body = _split_along(body, self._facet_borders(np.asarray(body.vertices)[:, 0]))
        vertices = np.asarray(body.vertices, dtype=float)
        turned = self.world(vertices[:, :2], vertices[:, 2], faceted=faceted)
        return trimesh.Trimesh(
            vertices=turned, faces=np.asarray(body.faces, dtype=np.int64), process=False
        )


def _split_along(body: Any, positions: np.ndarray) -> Any:
    """Ein flacher Körper, an jeder dieser Lagen der ersten Achse geteilt — konform.

    Jede Kante, die eine Lage kreuzt, bekommt genau einen neuen Punkt auf ihr,
    und beide Dreiecke an der Kante teilen ihn (:func:`_cut_at`): Der Körper
    bleibt geschlossen, und jedes Dreieck liegt danach ganz auf einer Seite
    jeder Lage. Gerechnet werden nur Grundrechenarten (RM-187).

    **Keine Boolesche Rechnung dafür.** Hier stand ``split_by_plane`` mit einem
    ``batch_boolean``, das die Stücke wieder zusammenfügte. Geht eine Lage
    durch eine Ecke oder ulp-nah an ihr vorbei, treffen die zwei Schnittflächen
    nicht Bit für Bit aufeinander, und die Vereinigung ließ Finnen stehen —
    zwei deckungsgleiche Dreiecke mit entgegengesetzter Normale —, aus denen
    ``manifold3d`` beim nächsten Einlesen einen Keil verwarf. Das trifft jede
    Zelle, die mittig auf einer Kante des Vielecks sitzt, denn dort setzt
    ``refined_for_bending`` eine Ecke genau auf die Facettengrenze: Nach dem
    Entfernen von 48 Taschen um einen Griff Ø 30 standen vier Hohlräume von
    0,03 bis 0,06 mm³ im Körper (23.09.2026). Solange die Facettenwinkel auf
    sechs Stellen gerundet waren, lag die Lage zufällig 10⁻⁶ mm neben der Ecke.
    """
    import trimesh

    if len(positions) == 0:
        return body
    vertices = np.array(body.vertices, dtype=np.float64)
    faces = np.array(body.faces, dtype=np.int64)
    for position in np.sort(np.asarray(positions, dtype=np.float64)):
        vertices, faces = _cut_at(vertices, faces, float(position))
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _cut_at(
    vertices: np.ndarray, faces: np.ndarray, position: float
) -> tuple[np.ndarray, np.ndarray]:
    """Die Dreiecke, die die Lage ``x = position`` kreuzen, an ihr geteilt.

    Eine Ecke, die höchstens ``EPS_GEOM`` neben der Lage liegt, liegt auf ihr —
    dieselbe Grenze, mit der :meth:`Frame._facet_borders` eine Lage am Rand des
    Körpers verwirft; sonst entstünden Splitter ohne Breite. Ein Dreieck mit
    einer Ecke auf der Lage wird zu zweien, eines mit einer Ecke allein auf
    ihrer Seite zu dreien, und die Umlaufrichtung bleibt. Der Punkt auf einer
    Kante wird einmal gerechnet, von der Ecke vor der Lage zu der dahinter, und
    liegt genau auf ihr: Zwei Kanten mit denselben Ecken bekommen denselben
    Punkt, gleich wie ihre Ecken nummeriert sind.
    """
    side = vertices[:, 0] - position
    touching = np.abs(side) <= EPS_GEOM
    if touching.any():
        vertices = vertices.copy()
        vertices[touching, 0] = position
        side = np.where(touching, 0.0, side)
    sign = np.sign(side).astype(np.int64)
    corner_signs = sign[faces]
    crossing = (corner_signs.min(axis=1) < 0) & (corner_signs.max(axis=1) > 0)
    if not crossing.any():
        return vertices, faces
    crossed = faces[crossing]
    signs = corner_signs[crossing]
    # Die besondere Ecke nach vorn: die auf der Lage — oder die allein auf
    # ihrer Seite, deren Vorzeichen dem der Summe entgegensteht.
    total = signs.sum(axis=1)
    special = np.where(total == 0, 0, -np.sign(total))
    first = np.argmax(signs == special[:, None], axis=1)
    rolled = crossed[np.arange(len(crossed))[:, None], (first[:, None] + np.arange(3)) % 3]
    pointed = rolled[total == 0]
    alone = rolled[total != 0]
    edges, inverse = unique_edges(
        np.concatenate((pointed[:, [1, 2]], alone[:, [0, 1]], alone[:, [0, 2]])),
        return_inverse=True,
    )
    before = side[edges[:, 0]] < 0.0
    low = np.where(before, edges[:, 0], edges[:, 1])
    high = np.where(before, edges[:, 1], edges[:, 0])
    share = side[low] / (side[low] - side[high])
    points = vertices[low] + share[:, None] * (vertices[high] - vertices[low])
    points[:, 0] = position
    new = len(vertices) + inverse
    middle = new[: len(pointed)]
    towards_one = new[len(pointed) : len(pointed) + len(alone)]
    towards_two = new[len(pointed) + len(alone) :]
    triangles = np.concatenate(
        (
            faces[~crossing],
            np.column_stack((pointed[:, 0], pointed[:, 1], middle)),
            np.column_stack((pointed[:, 0], middle, pointed[:, 2])),
            np.column_stack((alone[:, 0], towards_one, towards_two)),
            np.column_stack((towards_one, alone[:, 1], alone[:, 2])),
            np.column_stack((towards_one, alone[:, 2], towards_two)),
        )
    )
    return np.concatenate((vertices, points)), triangles


def _facet_sag(frame: Frame, points: np.ndarray, triangles: np.ndarray) -> float:
    """Wie weit die Facetten eines Trägers unter seiner Fläche hängen.

    Gemessen an den Kantenmitten seiner Dreiecke: Die Ecken liegen auf dem
    Zylinder, die Sehnen dazwischen darunter. Null auf einer Ebene.
    """
    if frame.kind == "plane" or len(triangles) == 0:
        return 0.0
    corners = points[triangles]
    midpoints = np.concatenate(
        [
            (corners[:, 0] + corners[:, 1]) / 2.0,
            (corners[:, 1] + corners[:, 2]) / 2.0,
            (corners[:, 2] + corners[:, 0]) / 2.0,
        ]
    )
    _flat, heights = frame.developed(midpoints)
    return max(0.0, -float(heights.min()))


#: Wie genau gefundene Facetten auf einem regelmäßigen Vieleck liegen müssen,
#: damit die fehlenden ergänzt werden — als Anteil des Facettenschritts.
_REGULAR_FACETS: Final = 0.01

#: Wie genau eine Ecke aus einer STL auf ihrer Fläche liegt, relativ zur
#: größten Koordinate des Körpers: das Achtfache der Rundung eines
#: ``float32``, in dem jede binäre STL ihre Ecken speichert (2⁻²³). Dieselbe
#: Zahl wie ``brep.from_mesh.PLANAR_SPAN``. Die feste Grenze ``EPS_GEOM``
#: (1 nm) riss schon ab 16 mm Koordinate, wo das Raster 1,9 nm misst (RM-404).
FACET_RASTER_SHARE: Final = 8.0 * 2.0**-23


def facet_tolerance(points: np.ndarray) -> float:
    """Die Auflösung, in der die Ecken dieses Körpers gespeichert sein können.

    Aus den heutigen Koordinaten und nicht aus der Datei: Ein späteres
    Aufsetzen verschiebt die Ecken in doppelter Genauigkeit, ihre Rundung von
    damals bleibt. Der Faktor acht deckt dabei auch einen Körper, der vorher
    deutlich weiter vom Ursprung lag. Danach fragen die Ausrichtung der
    Facetten (``prepare_ops._aligned_facets``) und ob eine Fläche die
    Stirnfläche des Trägers ist (:func:`_end_planes`).
    """
    reach = float(np.max(np.abs(points))) if len(points) else 0.0
    return max(EPS_GEOM, FACET_RASTER_SHARE * reach)


def cylinder_facet_groups(
    frame: Frame,
    normals: np.ndarray,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Mantelfacetten nach Normalen gruppieren, auch über die Winkelnaht hinweg.

    Ausrichtung und Musterstopfen lesen dieselben Gruppen. Die Winkel sind
    plattformgleich gerechnet; benachbarte Normalen unter ``EPS_ANGLE``
    gehören wie in der Ebenenerkennung zur selben Facette.
    """
    from app.core.geom.transform import along
    from app.core.perceive.features import EPS_ANGLE

    if check_cancelled is not None:
        check_cancelled()
    radial = np.flatnonzero(np.abs(along(normals, frame.normal)) < 0.5)
    degrees = []
    for index in radial:
        if check_cancelled is not None:
            check_cancelled()
        normal = normals[index]
        degrees.append(
            units.exact_atan2_degrees(
                units.dot3(normal, frame.y_axis), units.dot3(normal, frame.x_axis)
            )
        )
    if not degrees:
        return np.empty(0), []
    angles = np.asarray(degrees, dtype=np.float64)
    order = np.argsort(angles, kind="stable")
    ordered = angles[order]
    starts = np.flatnonzero(np.r_[True, np.diff(ordered) > EPS_ANGLE])
    groups = list(np.split(radial[order], starts[1:]))
    if len(groups) > 1 and ordered[0] + 360.0 - ordered[-1] <= EPS_ANGLE:
        groups[0] = np.concatenate((groups[0], groups[-1]))
        groups.pop()
        starts = starts[:-1]
    return ordered[starts] * (math.pi / 180.0), groups


@dataclass(frozen=True, slots=True, eq=False)
class FacetLine:
    """Eine Mantelfacette im Querschnitt: die Ausgleichsgerade ihrer Ecken, quer zur Achse.

    Die Facette ist achsparallel gelesen, denn so legt der Stopfen sich auf
    sie (:meth:`Frame.world`). Eine Ebene durch alle Ecken stand an einer STL
    bis 10⁻⁷ rad gegen die Achse geneigt; auf sie ausgerichtet lag der Mantel
    an den Stirnenden bis 1,5·10⁻⁶ mm neben dem Stopfen (RM-404).
    """

    angle: float
    """Der Winkel der Normalen um die Achse, im Bogenmaß gegen die erste Achse der Abwicklung."""
    normal: tuple[float, float]
    """Die Normale nach außen, in den beiden Achsen der Abwicklung quer zur Achse."""
    offset: float
    """Der Abstand der Facette von der Achse."""
    vertices: np.ndarray
    """Die Ecken der Facette, als Nummern im Körper."""
    residual: float
    """Wie weit die fernste Ecke quer zur Achse neben der Geraden liegt."""
    extent: float
    """Wie weit die fernste Ecke quer zur Achse von der Mitte der Ecken liegt."""


def cylinder_facet_lines(
    frame: Frame,
    points: np.ndarray,
    triangles: np.ndarray,
    normals: np.ndarray,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[FacetLine | None]:
    """Die Facetten eines Zylinderträgers als Geraden quer zur Achse, in der Folge der Gruppen.

    **Ausrichtung und Stopfen lesen hier dieselbe Facette** — die Ausrichtung
    (``prepare_ops._aligned_facets``) legt die Ecken auf diese Geraden, der
    Stopfen (:func:`_facet_planes`) liest sie danach am ausgerichteten Körper
    wieder und bekommt dieselben bis auf die Rundung. Gelesen wird aus allen
    Ecken der Gruppe (:func:`cylinder_facet_groups`), nicht aus einem
    Dreieck: Ein Dreieck einer STL trägt das Rauschen seiner drei Ecken.

    ``points`` sind die Ecken des Körpers, ``triangles`` und ``normals`` die
    Dreiecke des Trägers. ``None`` steht für eine Gruppe, deren Ecken quer zur
    Achse in einen Punkt fallen — sie belegt keine Gerade. Gerechnet wird
    plattformgleich: Summen über NumPys paarweise Summe, Wurzeln, der Winkel
    über :func:`units.exact_atan2_degrees`.
    """
    _angles, groups = cylinder_facet_groups(frame, normals, check_cancelled=check_cancelled)
    corners = np.asarray(triangles, dtype=np.int64)
    positions = np.asarray(points, dtype=np.float64)
    lines: list[FacetLine | None] = []
    for group in groups:
        if check_cancelled is not None:
            check_cancelled()
        vertices = np.unique(corners[group].ravel())
        lines.append(_facet_line(frame, positions[vertices], vertices))
    return lines


def _facet_line(frame: Frame, positions: np.ndarray, vertices: np.ndarray) -> FacetLine | None:
    """Die Ausgleichsgerade dieser Ecken im Querschnitt — oder ``None`` ohne Ausdehnung.

    Der kleinste Ausgleich senkrecht zur Geraden über die symmetrische
    2x2-Streumatrix: Ihr kleinerer Eigenwert und dessen Eigenrichtung in
    geschlossener Form, aus Grundrechenarten und Wurzeln (RM-187).
    """
    from app.core.geom.transform import along

    relative = positions - frame.origin
    first_axis = along(relative, frame.x_axis)
    second_axis = along(relative, frame.y_axis)
    count = len(vertices)
    middle_x = float(np.sum(first_axis)) / count
    middle_y = float(np.sum(second_axis)) / count
    dx = first_axis - middle_x
    dy = second_axis - middle_y
    xx = float(np.sum(dx * dx))
    yy = float(np.sum(dy * dy))
    xy = float(np.sum(dx * dy))
    half = (xx - yy) / 2.0
    least = (xx + yy) / 2.0 - math.hypot(half, xy)
    # Jede Zeile der Matrix minus Eigenwert steht senkrecht auf der gesuchten
    # Richtung; um einen rechten Winkel gedreht, ist sie diese Richtung — die
    # Normale der Geraden. Die längere der beiden ist die genauere.
    first = (xy, least - xx)
    second = (least - yy, xy)
    x, y = first if math.hypot(*first) >= math.hypot(*second) else second
    length = math.hypot(x, y)
    if length <= 0.0:
        return None
    x, y = x / length, y / length
    if x * middle_x + y * middle_y < 0.0:
        x, y = -x, -y
    return FacetLine(
        angle=units.exact_atan2_degrees(y, x) * (math.pi / 180.0),
        normal=(x, y),
        offset=x * middle_x + y * middle_y,
        vertices=vertices,
        residual=float(np.max(np.abs(dx * x + dy * y))),
        extent=float(np.max(np.sqrt(dx * dx + dy * dy))),
    )


def _facet_planes(
    frame: Frame, points: np.ndarray, triangles: np.ndarray, normals: np.ndarray
) -> FacetPolygon | None:
    """Die Facettenebenen eines Zylinderträgers: Winkel um die Achse, Abstand von ihr, Ecken.

    Jede Facette ist eine Ebene, und ihre Dreiecke teilen eine Normale — auch
    nach einer Booleschen Rechnung, die den Streifen in Stücke geschnitten
    hat. Gelesen wird sie als Gerade quer zur Achse aus allen ihren Ecken
    (:func:`cylinder_facet_lines`), wie die Ausrichtung sie vor dem Schließen
    gelegt hat. ``None``, wenn der Träger keine Facetten hat, die sich so
    lesen lassen.
    """
    if frame.kind == "plane" or len(triangles) == 0:
        return None
    # **Dieselbe Facette, solange die Normalen um weniger als ``EPS_ANGLE``
    # auseinanderliegen** — die Grenze, unter der die Erkennung zwei Dreiecke
    # koplanar nennt, und über Ketten statt gerundet. Hier stand eine Rundung
    # auf sechs Stellen: Die Dreiecke einer Facette fielen auf zwei Seiten
    # ihrer Grenzen, und eine STL mit vier Nachkommastellen trägt in einer
    # Facette Normalen, die 6·10⁻⁵ rad auseinanderliegen. Der Rand eines
    # Schraubdeckels hatte so 159 „Facetten" statt 72, der Median ihrer
    # Schritte war null, und der Stopfen lag auf dem Kreis (23.09.2026).
    lines = [
        line for line in cylinder_facet_lines(frame, points, triangles, normals) if line is not None
    ]
    if len(lines) < 3:
        return None
    lines.sort(key=lambda line: line.angle)
    angles, offsets = _regular_polygon(
        np.array([line.angle for line in lines], dtype=np.float64),
        np.array([line.offset for line in lines], dtype=np.float64),
    )
    return FacetPolygon(angles, offsets, _facet_corners(angles, offsets))


def _regular_polygon(angles: np.ndarray, offsets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Die Facetten eines regelmäßigen Vielecks — auch die, die ein Muster weggeschnitten hat.

    **Wo eine Rille durch die ganze Höhe geht, fehlt ihre Facette im Träger.**
    Am Rand eines Schraubdeckels sind es 24 Mulden über je 1 bis 2 Facetten;
    ohne sie legte :meth:`Frame._facet_radius` den Stopfen auf die Ebene der
    Nachbarfacette oder den Kreis, der Rand war danach kein Vieleck mehr, und
    nach dem Entfernen standen 103 Flächen, wo ein Zylinder war (23.09.2026).
    Liegen alle gefundenen Facetten auf einem regelmäßigen Vieleck — jede
    höchstens :data:`_REGULAR_FACETS` Schritte neben ihrem Platz, alle mit
    demselben Abstand von der Achse —, kommen die fehlenden an ihren Platz,
    mit dem Median der gemessenen Abstände; sonst bleibt es bei den gefundenen.

    **Die gefundenen bleiben, wie sie gemessen sind.** Bis RM-404 kam das ganze
    Vieleck aus dem Raster, und der Stopfen lag um das Rauschen der STL neben
    dem Mantel, den die Ausrichtung auf seine gemessenen Facetten gelegt hatte.
    """
    steps = np.diff(np.r_[angles, angles[0] + 2.0 * math.pi])
    step = float(np.min(steps))
    if step <= EPS_GEOM:
        return angles, offsets
    count = round(2.0 * math.pi / step)
    if count <= len(angles) or count > 4096:
        return angles, offsets
    spacing = 2.0 * math.pi / count
    slots = (angles - angles[0]) / spacing
    if float(np.max(np.abs(slots - np.round(slots)))) > _REGULAR_FACETS:
        return angles, offsets
    if float(offsets.max() - offsets.min()) > _REGULAR_FACETS * spacing * float(offsets.mean()):
        return angles, offsets
    missing = np.setdiff1d(np.arange(count), np.round(slots).astype(np.int64) % count)
    grid = angles[0] + spacing * missing
    grid = (grid + math.pi) % (2.0 * math.pi) - math.pi
    completed = np.concatenate((angles, grid))
    distances = np.concatenate((offsets, np.full(len(missing), float(np.median(offsets)))))
    order = np.argsort(completed, kind="stable")
    return completed[order], distances[order]


def _facet_corners(angles: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    """Je Facette, wie weit hinter ihrer Normalen sie an die nächste stößt — im Bogenmaß.

    Zwei Facetten im Winkel ``d`` mit den Abständen ``a`` und ``b`` schneiden
    sich ``t`` hinter der ersten Normalen, mit
    ``tan t = (b - a·cos d) / (a·sin d)``; bei gleichem Abstand ist das die
    Winkelhalbierende. Wo sich zwei nicht vor der Achse treffen (``d`` ab
    einem halben Umlauf) oder der Schnitt außerhalb ihres Winkels läge, bleibt
    es bei der Halbierenden. Kosinus, Sinus und Arkustangens sind
    plattformgleich (``units``).
    """
    count = len(angles)
    gaps = np.asarray((np.roll(angles, -1) - angles) % (2.0 * math.pi), dtype=np.float64)
    corners: np.ndarray = gaps / 2.0
    for index in range(count if count > 1 else 0):
        gap = float(gaps[index])
        if gap <= 0.0 or gap >= math.pi:
            continue
        first = float(offsets[index])
        second = float(offsets[(index + 1) % count])
        if first <= 0.0:
            continue
        ratio = (second - first * units.exact_cos(gap)) / (first * units.exact_sin(gap))
        corner = units.exact_atan_degrees(ratio) * (math.pi / 180.0)
        if 0.0 < corner < gap:
            corners[index] = corner
    return corners


def frame_for(
    feature: Feature,
    mesh: MeshData | None = None,
    features: Mapping[FeatureId, Feature] | None = None,
) -> Frame:
    """Die Abwicklung eines gelesenen Musters, aus seinen Parametern.

    Ein Muster auf einer Ebene trägt seine Normale; eines um einen Zylinder
    dazu Achse und Durchmesser (``carrier_axis``, ``carrier_diameter``), und
    seine Mitte liegt auf dem Zylinder. Die Normale dort ist die erste Achse
    der Abwicklung — die Naht liegt der Mitte gegenüber. Die Facetten des
    Trägers hängen um ihre Sehnenabweichung unter dem Zylinder; die ist am
    Träger gemessen, wenn er zu finden ist, sonst so groß, wie der Kern beim
    Tessellieren zulässt.
    """
    params = feature.params
    normal = np.asarray(params.get("normal", (0.0, 0.0, 1.0)), dtype=float)
    if params.get("carrier") != "cylinder":
        return Frame.plane(normal)
    axis = np.asarray(params.get("carrier_axis", (0.0, 0.0, 1.0)), dtype=float)
    axis = axis / max(math.hypot(*axis), EPS_GEOM)
    radius = float(params.get("carrier_diameter", 0.0)) / 2.0
    normal = normal - axis * units.dot3(normal, axis)
    normal = normal / max(math.hypot(*normal), EPS_GEOM)
    centre = np.asarray(params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
    frame = Frame.cylinder(
        axis, centre - normal * radius, radius, reference=normal, sag=units.MAX_FACET_SAG
    )
    if mesh is None or features is None:
        return frame
    carrier = carrier_of(feature, features)
    if carrier is None or not carrier.face_indices:
        return frame
    body = mesh.raw
    indices = np.asarray(carrier.face_indices, dtype=np.int64)
    indices = indices[(indices >= 0) & (indices < len(body.faces))]
    triangles = np.asarray(body.faces, dtype=np.int64)[indices]
    points = np.asarray(body.vertices, dtype=float)
    sag = _facet_sag(frame, points, triangles)
    from app.core.geom.mesh import stable_normals

    facets = _facet_planes(frame, points, triangles, stable_normals(body)[0][indices])
    from app.core.geom.transform import along

    low, high = _axial_span(points, triangles, frame.normal)
    level = float(along(frame.origin, frame.normal))
    span = (low - level, high - level)
    corners = points[np.unique(triangles)]
    reach = along(corners, frame.normal)
    rims = (corners[int(np.argmin(reach))], corners[int(np.argmax(reach))])
    return dataclasses.replace(
        frame,
        sag=sag,
        facets=facets,
        span=span,
        ends=_end_planes(frame, features, span, rims, facet_tolerance(points)),
    )


def _end_planes(
    frame: Frame,
    features: Mapping[FeatureId, Feature],
    span: tuple[float, float],
    rims: tuple[np.ndarray, np.ndarray],
    tolerance: float,
) -> tuple[EndPlane | None, EndPlane | None]:
    """Die ebenen Stirnflächen an beiden Enden des Trägers, so wie die Erkennung sie gemessen hat.

    Eine Stirnfläche ist eine ebene Fläche quer zur Achse — gekippt höchstens
    um :data:`SAME_MEASURE`, wie :func:`_cylinder_carrier_of` Achsen
    vergleicht —, deren Mitte auf ``MAX_FACET_SAG`` genau am Ende des Trägers
    liegt, wie :func:`_through_the_ends` fragt, was dort liegt. Und der Mantel
    endet in ihr: Die äußerste Ecke des Trägers an diesem Ende (``rims``)
    liegt auf ihrer Ebene, so genau, wie die Datei runden kann
    (``tolerance``, :func:`facet_tolerance`) — eine Fläche hinter einer
    schmalen Fase ist nicht das Ende des Mantels, und ein Stopfen bis dorthin
    legte Material über die Fase. Von mehreren gilt die größte, gerundet wie
    im Nummernschlüssel (:func:`carrier_of`).
    """
    from app.core.perceive.features import AREA_DIGITS

    found: list[tuple[float, EndPlane] | None] = [None, None]
    for candidate in features.values():
        if candidate.kind != "face" or not candidate.face_indices:
            continue
        normal = np.asarray(candidate.params.get("normal", (0.0, 0.0, 0.0)), dtype=float)
        if abs(units.dot3(normal, frame.normal)) < 1.0 - SAME_MEASURE:
            continue
        centre = np.asarray(candidate.params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
        level = units.dot3(centre - frame.origin, frame.normal)
        plane = EndPlane(normal, units.dot3(normal, centre))
        area = round(float(candidate.params.get("area", 0.0)), AREA_DIGITS)
        for index, (edge, rim) in enumerate(zip(span, rims, strict=True)):
            best = found[index]
            if (
                abs(level - edge) <= units.MAX_FACET_SAG
                and abs(units.dot3(normal, rim) - plane.offset) <= tolerance
                and (best is None or area > best[0])
            ):
                found[index] = (area, plane)
    return (
        None if found[0] is None else found[0][1],
        None if found[1] is None else found[1][1],
    )


def _axial_span(points: np.ndarray, triangles: np.ndarray, axis: np.ndarray) -> tuple[float, float]:
    """Wie weit ein Stift entlang seiner Achse reicht — von Stirnfläche zu Stirnfläche.

    Gemessen an den Ecken seiner Dreiecke, in Weltlage entlang ``axis`` und
    ohne BLAS (``transform.along``, RM-187). Dieselbe Länge fragen die Suche
    nach Randmustern (:func:`_rim_patterns`: was darin liegt, ist eine Zelle)
    und der Stopfen (:attr:`Frame.span`: dort endet er).
    """
    from app.core.geom.transform import along

    reach = along(points[np.asarray(triangles, dtype=np.int64)].reshape(-1, 3), axis)
    return float(reach.min()), float(reach.max())


def _carrier_outline(body: Any, carrier: Feature) -> np.ndarray:
    """Alle Ecken einer Trägerfläche — um zu sehen, ob ein Feld sie ganz füllt."""
    indices = np.asarray(carrier.face_indices, dtype=np.int64)
    points = np.asarray(body.vertices, dtype=float)
    return np.asarray(points[np.unique(np.asarray(body.faces)[indices])], dtype=float)


# --- Umrisse --------------------------------------------------------------------


def _convex_hull(flat: np.ndarray) -> np.ndarray | None:
    """Die konvexe Hülle in der Ebene, gegen den Uhrzeigersinn, ohne Doppelpunkte.

    Andrews Kette statt ``scipy.spatial.ConvexHull``: Qhull legt unter Windows
    je Aufruf eine Temporärdatei an, und 6 645 Zellen eines Rändels kosteten
    so 1,5 s allein im Öffnen von Dateien (Profil vom 22.09.2026, 3,8 von
    6,9 s in der Hülle). Eine Zelle hat ein Dutzend Ecken; die Kette braucht
    dafür Mikrosekunden.
    """
    rounded = np.round(flat, 6)
    order = np.lexsort((rounded[:, 1], rounded[:, 0]))
    points = rounded[order]
    keep = np.ones(len(points), dtype=bool)
    keep[1:] = np.any(points[1:] != points[:-1], axis=1)
    points = points[keep]
    if len(points) < 3:
        return None

    def cross(origin: np.ndarray, first: np.ndarray, second: np.ndarray) -> float:
        return float(
            (first[0] - origin[0]) * (second[1] - origin[1])
            - (first[1] - origin[1]) * (second[0] - origin[0])
        )

    lower: list[np.ndarray] = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper: list[np.ndarray] = []
    for point in points[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        return None
    return np.asarray(hull, dtype=float)


@dataclass(frozen=True, slots=True, eq=False)
class _Outline:
    """Ein konvexer Umriss, einmal vermessen — Kanten, Längen, Winkel und was daraus folgt.

    Fünf Fragen an denselben Umriss — Fläche, Schwerpunkt, Ecken, Breiten,
    längste Kante — rollten ihn fünfmal; an 6 645 Zellen war das ein Drittel
    der Messung (22.09.2026). Jetzt einmal.
    """

    points: np.ndarray
    edges: np.ndarray
    lengths: np.ndarray
    angles: np.ndarray

    @classmethod
    def of(cls, polygon: np.ndarray) -> _Outline:
        edges = np.roll(polygon, -1, axis=0) - polygon
        return cls(
            points=polygon,
            edges=edges,
            lengths=np.linalg.norm(edges, axis=1),
            angles=np.arctan2(edges[:, 1], edges[:, 0]),
        )

    @property
    def area(self) -> float:
        """Schnürsenkel — die Fläche des geschlossenen Umrisses."""
        x, y = self.points[:, 0], self.points[:, 1]
        return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)

    @property
    def centroid(self) -> np.ndarray:
        """Der Flächenschwerpunkt — nicht das Mittel der Ecken.

        Am Rand eines Feldes ist eine Zelle abgeschnitten; das Mittel ihrer
        Ecken wanderte dann zur Schnittkante, der Schwerpunkt bleibt, wo die
        Fläche ist.
        """
        x, y = self.points[:, 0], self.points[:, 1]
        next_x, next_y = np.roll(x, -1), np.roll(y, -1)
        cross = x * next_y - next_x * y
        doubled = float(cross.sum())
        if abs(doubled) <= EPS_GEOM:
            return self.points.mean(axis=0)
        return np.array(
            [
                float(((x + next_x) * cross).sum() / (3.0 * doubled)),
                float(((y + next_y) * cross).sum() / (3.0 * doubled)),
            ]
        )

    @property
    def longest_edge(self) -> np.ndarray:
        """Die Richtung der längsten Kante, als Einheitsvektor."""
        longest = self.edges[int(np.argmax(self.lengths))]
        return np.asarray(longest / max(float(np.linalg.norm(longest)), EPS_GEOM), dtype=float)

    @property
    def turns(self) -> np.ndarray:
        """Die Richtungsänderung an jeder Ecke, in Grad."""
        steps = np.diff(np.append(self.angles, self.angles[0]))
        return np.degrees(np.abs((steps + math.pi) % (2 * math.pi) - math.pi))

    @property
    def corners(self) -> int:
        """Wie viele echte Ecken der Umriss hat — Nähte gerader Kanten zählen nicht."""
        return int(np.count_nonzero(self.turns > CORNER_DEGREES))

    def corner_points(self) -> np.ndarray:
        """Die echten Ecken selbst, in der Reihenfolge des Umrisses.

        Nicht die ersten Punkte des Umrisses: Der Fuß einer Raute um einen
        Zylinder trägt an jeder Facettenkante des Trägers einen weiteren
        Punkt, und ``hull[2] - hull[0]`` war dann keine Diagonale mehr — 312
        Rauten eines Kreuzrändels hießen ``other`` (22.09.2026).
        """
        at = (np.flatnonzero(self.turns > CORNER_DEGREES) + 1) % len(self.points)
        return np.asarray(self.points[at], dtype=float)

    def calipers(self) -> tuple[float, float]:
        """Kleinste und größte Breite des konvexen Umrisses.

        Die kleinste: je Kante der größte Abstand einer Ecke von ihrer
        Geraden, davon das Minimum — die Schlüsselweite eines Sechsecks, die
        Seite einer Raute, die Breite einer Rippe. Die größte: der weiteste
        Eckenabstand.
        """
        keep = self.lengths > EPS_GEOM
        if not keep.any():
            return 0.0, 0.0
        polygon = self.points
        normals = (
            np.column_stack((-self.edges[keep, 1], self.edges[keep, 0])) / self.lengths[keep, None]
        )
        distances = (polygon[None, :, :] - polygon[keep][:, None, :]) * normals[:, None, :]
        width = float(np.abs(distances.sum(axis=2)).max(axis=1).min())
        spread = polygon[:, None, :] - polygon[None, :, :]
        length = float(np.linalg.norm(spread, axis=2).max())
        return width, length

    def sides(self) -> tuple[float, ...]:
        """Die Seiten des Umrisses zwischen echten Ecken."""
        turns = self.turns
        sides: list[float] = []
        running = 0.0
        for index in range(len(self.points)):
            running += float(self.lengths[index])
            if turns[index] > CORNER_DEGREES:
                sides.append(running)
                running = 0.0
        if running > EPS_GEOM and sides:
            sides[0] += running
        return tuple(sides)


def _style_of(
    outline: _Outline,
    corners: int,
    width: float,
    length: float,
    is_round: bool,
    *,
    straight: float,
) -> str:
    """Welches Muster dieser Umriss ist — nach Ecken, Seiten und Wänden.

    Rund ist eine Noppe. Ein Streifen ist eine Rippe, wenn seine Wände gerade
    stehen, sonst eine Welle — am Rand des Feldes ist er schräg abgeschnitten
    und hat dann fünf oder sechs Ecken, seine Breite bleibt dieselbe. Sechs
    gleiche Seiten sind eine Wabe. Vier gleiche Seiten mit gleichen Diagonalen
    eine Raute des Kreuzrändels — ein auf die Spitze gestelltes Quadrat, so
    baut ``texture_ops._diamonds`` es. Alles andere ist ein Gitter aus etwas,
    das Solidon so nicht erzeugt.
    """
    if is_round:
        return "dimple"
    # Ein Dreieck hat kein Paar gegenüberliegender Streifenflanken. Als
    # angeschnittener Rand darf es zu einem belegten Feld gehören, aber
    # allein seine Länge belegt keine Welle (etwa in einem Sternornament).
    if corners >= 4 and length >= RIB_ASPECT * width:
        return "rib" if straight >= STRAIGHT_SHARE else "wave"
    sides = outline.sides()
    if corners == 6 and len(sides) == 6 and _all_alike(sides):
        return "hexagon"
    if corners == 4 and len(sides) == 4:
        points = outline.corner_points()
        diagonals = (
            float(np.linalg.norm(points[2] - points[0])),
            float(np.linalg.norm(points[3] - points[1])),
        )
        if _all_alike(sides) and _all_alike(diagonals):
            return "knurl_diamond"
    return "other"


def _all_alike(values: Sequence[float]) -> bool:
    """Ob alle Werte innerhalb von :data:`SAME_MEASURE` beieinander liegen."""
    largest = max(values)
    return largest > EPS_GEOM and (largest - min(values)) <= SAME_MEASURE * largest


# --- Gruppen und Gitter ---------------------------------------------------------


def _same_cell(one: Cell, two: Cell) -> bool:
    """Ob zwei Zellen deckungsgleich sind — Träger, Seite, Umriss und Maße."""
    if one.clipped or two.clipped:
        return False
    if one.carrier != two.carrier or one.raised != two.raised or one.through != two.through:
        return False
    strips = one.style in _STRIPS
    # Rippe und Welle sind dieselbe Zelle mit anderen Wänden; ob eine Reihe
    # Rippen oder Wellen sind, entscheidet die Reihe (``_lattice_of``), nicht
    # der einzelne Streifen — ein kurz abgeschnittener sähe sonst anders aus
    # als seine langen Nachbarn, und die Reihe zerfiele in zwei.
    if (two.style in _STRIPS) != strips or (not strips and one.style != two.style):
        return False
    if strips:
        alignment = abs(float(one.axis[0] * two.axis[0] + one.axis[1] * two.axis[1]))
        if alignment < units.exact_cos_degrees(SAME_DIRECTION_DEGREES):
            return False
    measures = [(one.depth, two.depth), (one.width, two.width)]
    if not strips:
        # Die Länge eines Streifens ist die des Feldes, nicht seine eigene —
        # und schräg abgeschnitten hat er so viele Ecken, wie der Rand ihm lässt.
        if one.corners != two.corners:
            return False
        measures.extend([(one.length, two.length), (one.mouth_area, two.mouth_area)])
    return all(abs(a - b) <= SAME_MEASURE * max(a, b, EPS_GEOM) for a, b in measures)


def _congruent_groups(cells: Sequence[Cell]) -> list[list[Cell]]:
    """Gruppen deckungsgleicher Zellen, die größte zuerst — ab ihrer Mindestzahl."""
    groups: list[list[Cell]] = []
    for cell in sorted(cells, key=lambda cell: (cell.carrier, -cell.mouth_area)):
        for group in groups:
            if _same_cell(group[0], cell):
                group.append(cell)
                break
        else:
            groups.append([cell])
    large = [
        nearby
        for group in groups
        if len(group) >= _least_cells(group[0])
        for nearby in _nearby_groups(group)
        if len(nearby) >= _least_cells(nearby[0])
    ]
    large.sort(key=len, reverse=True)
    return large


def _nearby_groups(group: Sequence[Cell]) -> list[list[Cell]]:
    """Trennt gleichartige Felder außerhalb ihrer örtlichen Nachbarschaft.

    Bei Streifen gilt der Abstand der Mündungsränder: Ihre Mitten wandern
    beim schrägen Anschnitt. Sonst gilt der Mittelpunktabstand, damit ein
    Raster länglicher Taschen nicht allein wegen ihrer Form in Reihen
    zerfällt. Erst danach wird jede Gruppe als Gitter geprüft.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from shapely import STRtree
    from shapely.geometry import Point, Polygon

    outlines = [
        Polygon(cell.outline) if cell.style in _STRIPS else Point(cell.flat_centre)
        for cell in group
    ]
    tree = STRtree(outlines)
    nearest, distances = tree.query_nearest(outlines, exclusive=True, return_distance=True)
    if not len(distances):
        return [list(group)]
    gaps = np.full(len(group), np.inf)
    np.minimum.at(gaps, nearest[0], distances)
    widths = np.asarray([cell.width if cell.style in _STRIPS else 0.0 for cell in group])
    reach = np.maximum(
        EPS_GEOM,
        (gaps * FIELD_NEIGHBOUR_STEPS + widths * (FIELD_NEIGHBOUR_STEPS - 1))
        * (1.0 + SAME_MEASURE),
    )
    pairs = tree.query(outlines, predicate="dwithin", distance=reach)
    # Nachbarn müssen sich gegenseitig erreichen: Eine vereinzelte Zelle
    # überbrückt mit ihrem großen Abstand keine Lücke zum belegten Feld.
    links = set(zip(pairs[0].tolist(), pairs[1].tolist(), strict=True))
    mutual = [(one, two) for one, two in sorted(links) if (two, one) in links]
    first, second = zip(*mutual, strict=True)
    graph = coo_matrix(
        (np.ones(len(mutual), dtype=np.int8), (first, second)),
        shape=(len(group), len(group)),
    )
    count, labels = connected_components(graph, directed=False)
    groups: list[list[Cell]] = [[] for _ in range(count)]
    for cell, label in zip(group, labels, strict=True):
        groups[int(label)].append(cell)
    return groups


def _lattice_of(group: Sequence[Cell]) -> Pattern | Literal["bores"] | None:
    """Ob diese Zellen in einem Gitter liegen — und welches Muster das ist.

    Der Stil kommt von der Zelle, das Gitter von der Menge, und beides muss
    zusammenpassen: ``apply_texture`` zeichnet jeden Stil in genau einem
    Gitter (:data:`_GENERATOR_LATTICE`). Sechsecke im Quadratraster sind ein
    Gitter, das Solidon so nicht zeichnet (``other``) — entfernbar, nicht
    neu setzbar. Runde Zellen außerhalb des Wabengitters sind **Bohrungen im
    Raster** und kein Muster; zurück kommt dann ``"bores"``, damit der
    Aufrufer sie auch keiner Streuung mehr gibt. Eine Reihe von Streifen
    entscheidet als Ganzes, ob sie Rippen oder Wellen sind — gewichtet mit
    der Wandfläche, damit die langen Streifen zählen und nicht die Stummel
    am Feldrand.
    """
    first = group[0]
    style = first.style
    if style in _STRIPS:
        found = _rows_of(group)
        walls = sum(cell.wall_area for cell in group)
        straight = (
            sum(cell.straight * cell.wall_area for cell in group) / walls if walls > 0.0 else 1.0
        )
        style = "rib" if straight >= STRAIGHT_SHARE else "wave"
    else:
        found = _grid_of(np.array([cell.flat_centre for cell in group], dtype=float))
    if found is None:
        return None
    lattice, angle, spacing = found
    expected = _GENERATOR_LATTICE.get(style)
    if expected is not None and expected != lattice:
        if first.round:
            return "bores"
        style = "other"
    pitch = spacing * _PITCH_PER_SPACING.get(style, 1.0)
    return _field(first, group, (), lattice, angle, pitch, style)


def _grid_of(flat: np.ndarray) -> tuple[str, float, float] | None:
    """Gitterart, Richtung und Nachbarabstand aus den nächsten Nachbarn."""
    from scipy.spatial import KDTree

    distances, neighbours = KDTree(flat).query(flat, k=2)
    nearest = distances[:, 1]
    spacing = float(np.median(nearest))
    if spacing <= EPS_GEOM:
        return None
    regular = np.abs(nearest - spacing) <= SAME_MEASURE * spacing
    if float(regular.mean()) < REGULAR_SHARE:
        return None
    vectors = flat[neighbours[:, 1]] - flat
    angles = np.degrees(np.arctan2(vectors[regular, 1], vectors[regular, 0]))
    lattice, angle = _fold_directions(angles)
    if lattice is None:
        return None
    return lattice, angle, spacing


def _rows_of(group: Sequence[Cell], *, least: int = MIN_STRIPS) -> tuple[str, float, float] | None:
    """Die Reihe der Streifen: Teilung quer zu ihrer Achse.

    Die Mitten schräg abgeschnittener Streifen wandern entlang des Streifens;
    was bleibt, ist ihr Abstand **quer** dazu, und der ist die Teilung.
    Gemessen an den Kanten, die der Achse folgen — nicht am Schwerpunkt, der
    an einem fünfeckig abgeschnittenen Streifen neben der Mittellinie liegt.
    ``least`` ist die Zahl der Streifen, ab der eine Reihe zählt; weniger als
    :data:`MIN_STRIPS` nur, wo der Kunde die Streifen selbst gewählt hat
    (:func:`grouped_pattern`).
    """
    axes = np.array([cell.axis for cell in group], dtype=float)
    # Achsen gleichrichten, sonst hebt sich das Mittel auf.
    axes[axes @ axes[0] < 0.0] *= -1.0
    axis = axes.mean(axis=0)
    length = float(np.linalg.norm(axis))
    if length <= EPS_GEOM:
        return None
    axis /= length
    deviation = np.degrees(np.arccos(np.clip(axes @ axis, -1.0, 1.0)))
    if float(deviation.max()) > SAME_DIRECTION_DEGREES:
        return None
    across = np.array([-axis[1], axis[0]])
    positions = np.sort(np.array([_strip_position(cell, axis, across) for cell in group]))
    steps = np.diff(positions)
    steps = steps[steps > EPS_GEOM]
    if len(steps) < least - 1 or not len(steps):
        return None
    spacing = float(np.median(steps))
    regular = np.abs(steps - spacing) <= SAME_MEASURE * spacing
    if float(regular.mean()) < REGULAR_SHARE:
        return None
    angle = round(math.degrees(math.atan2(float(across[1]), float(across[0]))), 6) % 180.0
    return "linear", 0.0 if angle >= 180.0 - 1e-6 else angle, spacing


def _strip_position(cell: Cell, axis: np.ndarray, across: np.ndarray) -> float:
    """Wo die Mittellinie eines Streifens quer zu seiner Achse liegt."""
    edges = np.roll(cell.outline, -1, axis=0) - cell.outline
    lengths = np.linalg.norm(edges, axis=1)
    along = lengths > EPS_GEOM
    along[along] = np.abs(edges[along] @ axis) / lengths[along] >= units.exact_cos_degrees(
        CORNER_DEGREES
    )
    if not along.any():
        return float(cell.flat_centre @ across)
    # Die zwei Randlinien des Streifens sind die äußersten Kanten; ihre Mitte
    # ist die Mittellinie — nicht ein Mittel über Kantenlängen, das an einem
    # abgeschnittenen Streifen zur längeren Kante zöge.
    midpoints = (cell.outline[along] + np.roll(cell.outline, -1, axis=0)[along]) / 2.0
    offsets = midpoints @ across
    return float(offsets.min() + offsets.max()) / 2.0


def _fold_directions(angles: np.ndarray) -> tuple[str | None, float]:
    """Die Richtungen zum nächsten Nachbarn auf die Symmetrie des Gitters gefaltet.

    Ein Wabengitter hat sechs Nachbarn in Schritten von 60 Grad, ein
    Quadratgitter vier in 90, eine Reihe zwei in 180. Gefaltet auf den
    kleinsten Schritt, bei dem alle Richtungen zusammenfallen, bleibt eine —
    die des Gitters. Fällt keine, ist es kein Gitter. Vom engsten zum
    weitesten Schritt: Eine Reihe fiele auch unter 60 Grad zusammen, ein
    Wabengitter nie unter 180.
    """
    for lattice, period in (("linear", 180.0), ("square", 90.0), ("hexagonal", 60.0)):
        folded = np.radians(angles % period) * (360.0 / period)
        mean = math.atan2(float(np.sin(folded).mean()), float(np.cos(folded).mean()))
        spread = np.degrees(np.abs((folded - mean + math.pi) % (2 * math.pi) - math.pi)) / (
            360.0 / period
        )
        if float(spread.max()) <= SAME_DIRECTION_DEGREES:
            angle = round(math.degrees(mean) / (360.0 / period), 6) % period
            return lattice, 0.0 if angle >= period - 1e-6 else angle
    return None, 0.0


def _field(
    first: Cell,
    cells: Sequence[Cell],
    partial: Sequence[Cell],
    lattice: str,
    lattice_angle: float,
    pitch: float,
    style: str,
) -> Pattern:
    """Das Feld um alle Zellen — so gedreht, wie ``apply_texture`` es zeichnen würde.

    Mehrere Lagen kommen infrage, und die kleinste Hülle entscheidet, denn
    ein Feld endet an seinem Rechteck: das Feld in den Achsen des Gitters;
    bei Rippen dazu das um 45 Grad gedrehte — ein gerades Rändel liegt in
    einem geraden Feld, seine Rippen darin unter 45 Grad, und das gilt unter
    jedem Winkel des Feldes, nicht nur unter null. Nur die eine Drehung, nicht
    auch die andere: ``texture_ops._ribs`` dreht die Stege um plus 45 Grad,
    und das Feld um minus 45 zur Gitterrichtung zeichnete sie gespiegelt. Bei einem
    Wabengitter kommen die um 60 und 120 Grad gedrehten Lagen dazu, weil das
    Gitter alle sechzig Grad gleich aussieht und das Feld nicht
    (:data:`_LATTICE_TURNS`). ``style`` ist der Stil der Zelle — ``rib``, nie
    ``knurl_straight``: Das Rändel ist eine Lage der Rippe, und die wird hier
    gewählt.
    """
    outlines = np.vstack([cell.outline for cell in (*cells, *partial)])
    offset = _LATTICE_OFFSET.get(style, 0.0)
    boxes = [
        (_turn(lattice_angle - offset + turn), style)
        for turn in _LATTICE_TURNS.get(lattice, (0.0,))
    ]
    if style == "rib":
        boxes.append((_turn(lattice_angle - _LATTICE_OFFSET["knurl_straight"]), "knurl_straight"))
    chosen = min(
        ((*_box(outlines, angle), angle, name) for angle, name in boxes),
        key=lambda box: round(box[0], 6),
    )
    _area, width, height, middle, angle, style = chosen
    frame = first.frame
    radians = math.radians(lattice_angle)
    direction = frame.tangent(middle, np.array([math.cos(radians), math.sin(radians)]))
    return Pattern(
        style=style,
        cells=tuple(cells),
        partial=tuple(partial),
        carrier=first.carrier,
        frame=frame,
        normal=_vec(frame.normal_at(middle)),
        direction=_vec(direction),
        centre=_vec(_field_centre(first, middle)),
        pitch=pitch,
        lattice=lattice,
        lattice_angle=lattice_angle,
        width=width,
        height=height,
        angle=angle,
        coverage="rectangle",
    )


def _turn(angle: float) -> float:
    """Ein Winkel als Drehung eines Feldes: zwischen null und 180 Grad, und 179,9994 ist null.

    Die Gitterrichtung kommt auf sechs Stellen gerundet aus der Faltung, und
    44,9994 minus 45 Grad Versatz ist knapp unter null — als 179,9994 Grad
    gemeldet drehte das ein Feld scheinbar um eine halbe Drehung.
    """
    turned = angle % 180.0
    return 0.0 if turned >= 180.0 - 1e-3 else turned


def _field_centre(first: Cell, middle: np.ndarray) -> np.ndarray:
    """Die Mitte des Feldes in der Welt — auf der Trägerebene, oder auf dem Zylinder.

    Am Zylinder genau auf dem Radius, nicht in der Höhe der ersten Mündung:
    Aus Mitte und Normale entsteht die Abwicklung wieder (:func:`frame_for`),
    und die Achse liegt dann um den Radius dahinter.
    """
    lift = first.lift if first.frame.kind == "plane" else 0.0
    return np.asarray(first.frame.world(middle, lift)[0], dtype=float)


def _box(outlines: np.ndarray, angle: float) -> tuple[float, float, float, np.ndarray]:
    """Die Hülle aller Umrisse in einem um ``angle`` gedrehten Rechteck.

    Zurück kommen Fläche, Breite, Höhe und Mitte — die Mitte in den Achsen der
    Ebene, nicht des Rechtecks.
    """
    along = np.array([units.exact_cos_degrees(angle), units.exact_sin_degrees(angle)])
    across = np.array([-along[1], along[0]])
    reach_u = outlines @ along
    reach_v = outlines @ across
    width = float(reach_u.max() - reach_u.min())
    height = float(reach_v.max() - reach_v.min())
    middle = (
        along * float(reach_u.max() + reach_u.min()) / 2.0
        + across * float(reach_v.max() + reach_v.min()) / 2.0
    )
    return width * height, width, height, middle


def _belongs_to(cell: Cell, pattern: Pattern) -> bool:
    """Ob eine übrige Zelle ein angeschnittenes Stück dieses Musters ist.

    Derselbe Träger, dieselbe Seite und Tiefe, nicht größer als eine ganze
    Zelle, und ihre Mitte liegt im Feld — so sehen die Zellen am Rand eines
    erzeugten Musters aus, die das Rechteck abgeschnitten hat. Mehr wird
    nicht verlangt: Ihr Umriss ist gerade das, was fehlt.
    """
    first = pattern.cells[0]
    if cell.carrier != first.carrier or cell.raised != first.raised:
        return False
    if abs(cell.depth - first.depth) > SAME_MEASURE * max(cell.depth, first.depth):
        return False
    largest = max(member.mouth_area for member in pattern.cells)
    if cell.mouth_area > largest * (1.0 + SAME_MEASURE):
        return False
    along = np.array(
        [units.exact_cos_degrees(pattern.angle), units.exact_sin_degrees(pattern.angle)]
    )
    across = np.array([-along[1], along[0]])
    middle = pattern.frame.developed(np.asarray(pattern.centre, dtype=float))[0][0]
    offset = cell.flat_centre - middle
    return (
        abs(float(offset @ along)) <= pattern.width / 2.0 + pattern.pitch
        and abs(float(offset @ across)) <= pattern.height / 2.0 + pattern.pitch
    )


def _with_partial(pattern: Pattern, leftovers: Sequence[Cell]) -> Pattern:
    """Das Muster um seine angeschnittenen Zellen erweitert — das Feld wächst mit."""
    if pattern.lattice == "none":
        return _scatter_field(pattern.cells[0], pattern.cells, leftovers, pattern.style)
    # Mit dem Stil der Zelle, nicht der Lage: ``_field`` wählt das Rändel
    # am gewachsenen Feld selbst noch einmal, und der Stil folgt der Lage.
    shape = "rib" if pattern.style == "knurl_straight" else pattern.style
    return _field(
        pattern.cells[0],
        pattern.cells,
        leftovers,
        pattern.lattice,
        pattern.lattice_angle,
        pattern.pitch,
        shape,
    )


def _with_coverage(pattern: Pattern, carrier_points: np.ndarray) -> Pattern:
    """Ob das Feld den Träger bis an seinen Rand füllt.

    Gemessen in den Achsen des Feldes: Reichen die Zellen in beiden
    Richtungen bis auf eine halbe Teilung an die äußersten Ecken des Trägers,
    ist das Muster über die ganze Fläche gelegt — ``apply_texture`` nennt das
    ``whole_face`` und schneidet am Flächenumriss ab, nicht an einem Rechteck.
    Zwei Teilungen waren zu großzügig (Review, 22.09.2026): Ein blindes Feld
    34 auf 24 auf der 40-auf-30-Platte galt als ganze Fläche, und ein
    Neuzeichnen mit weiterer Teilung kerbte die Seitenwände an.
    """
    flat, _heights = pattern.frame.developed(carrier_points)
    _area, width, height, _middle = _box(flat, pattern.angle)
    reach = pattern.pitch / 2.0
    whole = width - pattern.width <= reach and height - pattern.height <= reach
    return dataclasses.replace(pattern, coverage="whole_face" if whole else "rectangle")


# --- Streuungen -----------------------------------------------------------------


def _scatter_groups(cells: Sequence[Cell]) -> list[list[Cell]]:
    """Zellen gleicher Tiefe und Seite auf demselben Träger — ohne Anspruch auf Gleichheit."""
    groups: list[list[Cell]] = []
    for cell in sorted(cells, key=lambda cell: (cell.carrier, cell.depth)):
        if cell.clipped:
            continue
        for group in groups:
            first = group[0]
            if (
                first.carrier == cell.carrier
                and first.raised == cell.raised
                and first.through == cell.through
                and abs(first.depth - cell.depth) <= SAME_MEASURE * max(first.depth, cell.depth)
            ):
                group.append(cell)
                break
        else:
            groups.append([cell])
    large = [group for group in groups if len(group) >= MIN_SCATTER]
    large.sort(key=len, reverse=True)
    return large


def _scatter_of(group: Sequence[Cell]) -> Pattern | None:
    """Voronoi oder Rauschen: ein Feld ohne Gitter, mit einer Dichte statt einer Teilung."""
    if any(cell.through for cell in group):
        return None
    round_share = sum(1 for cell in group if cell.round) / len(group)
    pattern = _scatter_field(group[0], group, (), "noise" if round_share >= 0.5 else "voronoi")
    if pattern.style == "noise" and len(group) < MIN_NOISE:
        return None
    return pattern


def _scatter_field(
    first: Cell, cells: Sequence[Cell], partial: Sequence[Cell], style: str
) -> Pattern:
    """Das Feld einer Streuung, in den Achsen der Ebene — und ihre Dichte als Teilung."""
    outlines = np.vstack([cell.outline for cell in (*cells, *partial)])
    area, width, height, middle = _box(outlines, 0.0)
    covered = sum(cell.mouth_area for cell in (*cells, *partial))
    if style == "voronoi" and area > EPS_GEOM and covered / area < VORONOI_COVERAGE:
        style = "noise"
    count = len(cells) + len(partial)
    pitch = math.sqrt(area / count) if count else 0.0
    frame = first.frame
    return Pattern(
        style=style,
        cells=tuple(cells),
        partial=tuple(partial),
        carrier=first.carrier,
        frame=frame,
        normal=_vec(frame.normal_at(middle)),
        direction=_vec(frame.tangent(middle, np.array([1.0, 0.0]))),
        centre=_vec(_field_centre(first, middle)),
        pitch=pitch,
        lattice="none",
        lattice_angle=0.0,
        width=width,
        height=height,
        angle=0.0,
        coverage="rectangle",
    )


def _vec(values: np.ndarray) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))


# --- Die Zellen als Körper: für Entfernen und Ändern --------------------------


@dataclass(frozen=True, slots=True)
class Mouth:
    """Die Mündung einer Zelle, als Umriss in der Abwicklung des Trägers, und ihre Tiefe."""

    polygon: Any
    """``shapely.Polygon`` in den Achsen der Abwicklung (:func:`frame_for`)."""
    depth: float


def mouths_of(
    mesh: MeshData,
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None = None,
) -> list[Mouth]:
    """Die Mündungen aller Zellen eines Musters, am Netz nachgezeichnet.

    Je Zelle die Randkanten ihrer Dreiecke, die auf dem Träger liegen, zu
    einem Ring verkettet — das ist ihr Umriss, exakt und ohne Annahme über
    die Form. Eine Zelle, deren Ring sich nicht schließt, fällt aus; der
    Aufrufer sieht das an der Zahl. Mit ``features`` ist der Träger zu
    finden, und am Zylinder dessen Facettenabweichung (:func:`frame_for`).
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    # Dasselbe geschweißte Netz wie die Erkennung — eine STL kennt keine
    # gemeinsamen Ecken, und ohne sie hat kein Dreieck einen Nachbarn. Die
    # Dreiecke behalten dabei ihren Platz, die Nummern des Merkmals gelten.
    from app.core.perceive.features import _one_body

    body = _one_body(mesh).raw
    indices = np.asarray(feature.face_indices, dtype=np.int64)
    triangle_count = len(body.faces)
    indices = indices[(indices >= 0) & (indices < triangle_count)]
    if indices.size == 0:
        return []
    normal = np.asarray(feature.params.get("normal", (0.0, 0.0, 1.0)), dtype=float)
    if float(np.linalg.norm(normal)) <= EPS_GEOM:
        return []
    frame = frame_for(feature, mesh, features)
    lift = float(
        frame.developed(np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float))[1][
            0
        ]
    )
    raised = feature.params.get("mode") == "raised"
    triangles = np.asarray(body.faces, dtype=np.int64)[indices]
    points = np.asarray(body.vertices, dtype=float)
    mouths: list[Mouth] = []
    for component in _components(body, indices):
        chosen = triangles[component]
        corners = np.unique(chosen)
        # Je Zelle abgewickelt — am Zylinder bleibt so eine Zelle über der
        # Naht ein Stück (:meth:`Frame.developed`).
        flat, span = frame.developed(points[corners])
        if feature.params.get("texture") and frame.kind == "plane":
            # Am Rand endet eine Zelle offen; ihre Wände haben dort keinen
            # geschlossenen Mündungsring. Der Boden beziehungsweise die Krone
            # belegt trotzdem den vollständigen, auch konkaven Fußabdruck.
            local = np.searchsorted(corners, chosen)
            footprints = [Polygon(piece) for piece in flat[local]]
            rim_rows = np.searchsorted(corners, _rim_edges(chosen))
            on_mouth = np.abs(span[rim_rows] - lift) <= units.weld_tolerance(mesh.bounds.diagonal)
            mouth_loops = _loops(rim_rows[on_mouth.all(axis=1)])
            if mouth_loops:
                # Ein schräger Schnitt kann einen Zellboden halb entfernen.
                # Der geschlossene obere Rand belegt trotzdem die ganze Zelle.
                footprints = [Polygon(flat[loop]) for loop in mouth_loops]
            footprint = unary_union([piece for piece in footprints if piece.area > EPS_GEOM])
            depth = float(span.max() - lift if raised else lift - span.min())
            if depth > units.weld_tolerance(mesh.bounds.diagonal) and not footprint.is_empty:
                for piece in getattr(footprint, "geoms", [footprint]):
                    if piece.geom_type == "Polygon" and piece.area > EPS_GEOM:
                        mouths.append(Mouth(polygon=piece, depth=depth))
                continue
        depth = float(span.max() - span.min())
        if depth <= EPS_GEOM:
            continue
        plane = float(span.min()) if raised else float(span.max())
        if abs(plane - lift) > _flat_tolerance(depth) + units.MAX_FACET_SAG:
            continue
        rows = np.searchsorted(corners, _rim_edges(chosen))
        on_plane = np.abs(span[rows] - plane) <= _flat_tolerance(depth) + frame.sag
        rim = rows[on_plane.all(axis=1)]
        loops = _loops(rim)
        if not loops:
            # Zwei Streuflecken, die sich in einem Punkt berühren, haben dort
            # eine Ecke mit vier Kanten, und der Ring schließt sich nicht.
            # Dann die konvexe Hülle: Sie deckt die Zelle und darüber hinaus
            # nur, was beim Füllen schon Material und beim Abtragen Luft ist.
            hull = _convex_hull(flat[rim.ravel()])
            if hull is not None:
                mouths.append(Mouth(polygon=Polygon(hull), depth=depth))
            continue
        for loop in loops:
            polygon = make_valid(Polygon(flat[loop]))
            for part in getattr(polygon, "geoms", [polygon]):
                if part.geom_type == "Polygon" and part.area > EPS_GEOM:
                    mouths.append(Mouth(polygon=part, depth=depth))
    return mouths


def plug_for(
    mesh: MeshData,
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None = None,
) -> MeshData | None:
    """Der Körper, der die Zellen eines Musters füllt oder abträgt.

    Je Mündung ein Prisma über die Tiefe der Zelle: vertieft vom Träger ins
    Material, erhaben von ihm weg, und **bündig mit dem Träger**. Um den
    Überlapp der Booleschen Rechnung verlängert ist nur das ferne Ende — am
    Träger ließe ein Überlapp eine Haut von einem Hundertstel stehen
    beziehungsweise fehlen, und die Erkennung fände danach ein Muster von
    einem Hundertstel Tiefe (gemessen am 22.09.2026: 56 Zellen, 3,2 mm³). Die
    Vereinigung füllt eine vertiefte Zelle genau — was das Prisma sonst noch
    deckt, ist schon Material —, die Differenz trägt eine erhabene bis auf
    den Träger ab. Um einen Zylinder wird das Prisma zurückgebogen
    (:meth:`Frame.placed`); was dann noch zwischen Facetten und Bogen liegt,
    ist kleiner als die Einpassung des Stifts.
    """
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.geom.mesh import concatenated

    mouths = mouths_of(mesh, feature, features)
    if not mouths:
        return None
    frame = frame_for(feature, mesh, features)
    lift = float(
        frame.developed(np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float))[1][
            0
        ]
    )
    raised = feature.params.get("mode") == "raised"
    # Eine durchgehende Zelle mündet auf beiden Seiten in eine Fläche; ihr
    # Prisma ist auf beiden bündig — ein Überlapp stünde als Haut auf der
    # Rückseite (195 Sechsecke von einem Hundertstel am Halter, 22.09.2026).
    through = bool(feature.params.get("through", False))
    # **Ein vertiefter Stopfen endet an den Stirnflächen des Stifts**
    # (:attr:`Frame.span`). Eine Zelle, die durch eine läuft — die Mulden
    # eines Schraubdeckels, Rillen oben offen —, hat dort keine Wand, die der
    # Saum decken müsste, und was über die Stirnfläche ragte, legte die
    # Vereinigung als Stufe an: 31 Kerben mit je einer eigenen Fläche und
    # 1,7 mm³ zu viel (23.09.2026). Ein erhabener Stopfen darf hinausreichen —
    # die Differenz trägt dort nur Luft ab.
    span = frame.span if frame.kind == "cylinder" and not raised else None
    parts = []
    for mouth in mouths:
        reach = frame.clearance
        if frame.kind == "cylinder":
            # Dazu die Sehne eines Bodens, der flach blieb: Ein Werkzeug, das
            # nur an den Ecken gebogen wurde, hat seinen Boden in der Mitte
            # der Zelle um so viel tiefer als am Rand.
            low, _low_v, high, _high_v = mouth.polygon.bounds
            reach += (high - low) ** 2 / (8.0 * frame.radius)
        height = mouth.depth if through else mouth.depth + BOOLEAN_OVERLAP + reach
        polygon = _mouth_with_margin(mouth, frame)
        middle = float(polygon.centroid.x)
        for piece in _within_span(polygon, span):
            prism = _extruded(piece, height)
            if prism is None:
                continue
            if (
                frame.kind == "cylinder"
                and not raised
                and not through
                and not feature.params.get("texture")
            ):
                _widened_towards_the_axis(prism, middle, height, frame.radius)
            if feature.params.get("texture") and frame.kind == "cylinder":
                # Der gemessene Mantel begrenzt diesen Stopfen anschließend
                # exakt. Der zusätzliche Hub deckt die Sehne seiner gebogenen
                # Dreiecke auf beiden Seiten der Trägerfacette.
                prism.apply_scale((1.0, 1.0, (height + frame.clearance) / height))
                bottom = lift - frame.clearance if raised else lift - height
            else:
                bottom = lift if raised else lift - height
            prism.apply_translation((0.0, 0.0, bottom))
            parts.append(prism)
    if not parts:
        return None
    return MeshData.of(frame.placed(concatenated(parts), faceted=True))


def cylinder_envelope(
    mesh: MeshData, feature: Feature, features: Mapping[FeatureId, Feature]
) -> MeshData | None:
    """Der belegte facettierte Träger als Grenze eines erzeugten Texturstopfens."""
    from shapely.geometry import Polygon

    frame = frame_for(feature, mesh, features)
    if frame.facets is None or frame.span is None:
        return None
    angles, _offsets, corners = frame.facets
    theta = angles + corners
    radius = frame._facet_radius(theta)
    polygon = Polygon(np.column_stack((np.cos(theta) * radius, np.sin(theta) * radius)))
    body = _extruded(polygon, frame.span[1] - frame.span[0])
    if body is None:
        return None
    local = np.asarray(body.vertices, dtype=float)
    levels = local[:, 2] + frame.span[0]
    points = (
        frame.origin
        + local[:, 0, None] * frame.x_axis
        + local[:, 1, None] * frame.y_axis
        + levels[:, None] * frame.normal
    )
    body.vertices = frame._onto_the_ends(points, levels)
    return MeshData.of(body)


def carrier_of(feature: Feature, features: Mapping[FeatureId, Feature]) -> Feature | None:
    """Der Träger eines Musters — gefunden über seine Lage, nicht über einen Namen.

    Ein Verweis auf ``face_2`` in den Parametern alterte: Die Zuordnung
    benennt Merkmale um (§21.2), den Verweis nicht. Die Lage altert nicht:
    Auf einer Ebene ist der Träger die größte ebene Fläche mit derselben
    Normalen, deren Mitte in der Ebene des Musters liegt; um einen Zylinder
    der Stift mit derselben Achse und demselben Durchmesser, durch dessen
    Achse die des Musters läuft.
    """
    from app.core.perceive.features import AREA_DIGITS

    params = feature.params
    if params.get("carrier") == "cylinder":
        return _cylinder_carrier_of(feature, features)
    normal = np.asarray(params.get("normal", (0.0, 0.0, 1.0)), dtype=float)
    normal = normal / max(float(np.linalg.norm(normal)), EPS_GEOM)
    lift = float(np.asarray(params.get("centre", (0.0, 0.0, 0.0)), dtype=float) @ normal)
    depth = float(params.get("cell_depth", 0.0))
    best: Feature | None = None
    for candidate in features.values():
        if candidate.kind != "face" or not candidate.face_indices:
            continue
        other = np.asarray(candidate.params.get("normal", (0.0, 0.0, 0.0)), dtype=float)
        if float(other @ normal) < 1.0 - SAME_MEASURE:
            continue
        centre = np.asarray(candidate.params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
        if abs(float(centre @ normal) - lift) > _flat_tolerance(depth) + units.MAX_FACET_SAG:
            continue
        # Gerundet wie im Nummernschlüssel: Bei zwei gleich großen Flächen
        # bleibt die mit der kleineren Nummer, nicht die mit der größeren
        # zwölften Stelle — am exakten Kern stand die Fläche schon immer
        # ungerundet im Merkmal.
        if best is None or round(float(candidate.params.get("area", 0.0)), AREA_DIGITS) > round(
            float(best.params.get("area", 0.0)), AREA_DIGITS
        ):
            best = candidate
    return best


def _cylinder_carrier_of(feature: Feature, features: Mapping[FeatureId, Feature]) -> Feature | None:
    """Der Stift, um den ein Muster läuft: gleiche Achse, gleicher Durchmesser, die Achse trifft."""
    frame = frame_for(feature)
    diameter = 2.0 * frame.radius
    best: Feature | None = None
    for candidate in features.values():
        if candidate.kind != "pin" or not candidate.face_indices:
            continue
        axis = np.asarray(candidate.params.get("axis", (0.0, 0.0, 0.0)), dtype=float)
        if abs(float(axis @ frame.normal)) < 1.0 - SAME_MEASURE:
            continue
        other = float(candidate.params.get("diameter", 0.0))
        if abs(other - diameter) > SAME_MEASURE * max(other, diameter, EPS_GEOM):
            continue
        centre = np.asarray(candidate.params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
        offset = centre - frame.origin
        beside = offset - frame.normal * float(offset @ frame.normal)
        if float(np.linalg.norm(beside)) > SAME_MEASURE * frame.radius + units.MAX_FACET_SAG:
            continue
        if best is None or len(candidate.face_indices) > len(best.face_indices):
            best = candidate
    return best


@dataclass(frozen=True, slots=True)
class Field:
    """Wo ein Muster neu gezeichnet wird — und der Weg von dort zurück in die Welt.

    ``outline`` liegt in den Achsen des Feldes: die erste in der
    Gitterrichtung, wie ``apply_texture`` sie mit ``angle`` dreht, der
    Nullpunkt in der Mitte des Musters. :meth:`flat` bringt einen Weltpunkt
    dorthin (den Anker), :meth:`placed` einen flachen Werkzeugkörper zurück —
    auf die Ebene gelegt oder um den Zylinder gebogen.
    """

    outline: Any
    frame: Frame
    middle: np.ndarray
    """Die Mitte des Musters in der Abwicklung."""
    angle: float
    """Die Drehung des Feldes gegen die erste Achse der Abwicklung, in Grad."""
    level: float = 0.0
    """Die Höhe des Trägers in der Abwicklung — die Ebene liegt nicht im Ursprung."""
    around: float = 0.0
    """Der Umfang, wenn das Feld einmal um den Zylinder reicht — sonst null."""

    def _turn(self) -> np.ndarray:
        radians = math.radians(self.angle)
        return np.array(
            [
                [math.cos(radians), -math.sin(radians)],
                [math.sin(radians), math.cos(radians)],
            ]
        )

    def flat(self, point: Vec3) -> tuple[float, float]:
        """Ein Weltpunkt in den Achsen des Feldes."""
        developed = self.frame.developed(np.asarray(point, dtype=float))[0][0] - self.middle
        local = self._turn().T @ developed
        return float(local[0]), float(local[1])

    def placed(self, tool: MeshData, *, beyond: float = 0.0) -> MeshData:
        """Ein flacher Körper aus den Achsen des Feldes in die Welt.

        ``beyond`` legt die Deckel des Werkzeugs, die an einer Stirnfläche
        des Trägers enden, mindestens so weit dahinter (:func:`_through_the_ends`).
        Ein Schneidwerkzeug, das bündig mit ihr endet, ließ dort Häute ohne
        Dicke stehen: Neu gezeichnete Rillen eines Deckels, die durch seinen
        Rand laufen, hatten eine Finne in der Stirnfläche, und die Erkennung las
        die Rille nicht mehr (23.09.2026). Ein Werkzeug, das vereinigt wird,
        bekommt keinen Überstand — dort legte er Material über der Stirnfläche
        an.
        """
        import trimesh

        vertices = np.asarray(tool.raw.vertices, dtype=float)
        developed = vertices[:, :2] @ self._turn().T + self.middle
        if beyond > 0.0 and self.frame.span is not None:
            developed = _through_the_ends(
                developed,
                vertices[:, 2],
                np.asarray(tool.raw.faces, dtype=np.int64),
                self.frame.span,
                beyond,
            )
        flat = trimesh.Trimesh(
            vertices=np.column_stack((developed, vertices[:, 2] + self.level)),
            faces=np.asarray(tool.raw.faces, dtype=np.int64),
            process=False,
        )
        return MeshData.of(self.frame.placed(flat))


def _through_the_ends(
    developed: np.ndarray,
    heights: np.ndarray,
    faces: np.ndarray,
    span: tuple[float, float],
    beyond: float,
) -> np.ndarray:
    """Die Deckel eines Werkzeugs mindestens um ``beyond`` hinter die Stirnfläche legen.

    Ein Deckel ist ein Dreieck quer zur Achse — höchstens ``CORNER_DEGREES``
    gekippt, die Eckenregel dieses Moduls —, dessen Ecken alle an der
    Stirnfläche liegen (auf ``MAX_FACET_SAG`` genau, dieselbe Grenze, mit der
    :func:`_rim_patterns` fragt, was in der Länge des Stifts liegt) oder
    jenseits davon. Nur die rücken; eine Rautenecke knapp unter der Stirnfläche
    gehört zu schrägen Wänden und bleibt, wo sie ist — mit ihr verschoben
    schnitt sie Kerben von Hundertsteln in die Stirnfläche. Gemessen wird ab
    der Stirnfläche, nicht ab dem nur angenähert dort liegenden Werkzeugende.
    ``developed`` ist
    die Lage in der Abwicklung, ``heights`` die Höhe darüber.
    """
    corners = np.column_stack((developed, heights))[faces]
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    across = (lengths > EPS_GEOM) & (
        np.abs(normals[:, 1]) >= units.exact_cos_degrees(CORNER_DEGREES) * lengths
    )
    moved = np.array(developed, dtype=float)
    for edge, outward in ((span[1], 1.0), (span[0], -1.0)):
        at_end = (outward * (corners[:, :, 1] - edge) >= -units.MAX_FACET_SAG).all(axis=1)
        chosen = np.unique(faces[across & at_end])
        moved[chosen, 1] = outward * np.maximum(outward * moved[chosen, 1], outward * edge + beyond)
    return moved


def field_outline(mesh: MeshData, feature: Feature, features: Mapping[FeatureId, Feature]) -> Field:
    """Der Umriss, in dem ein Muster neu gezeichnet wird — samt dem Weg zurück in die Welt.

    Ein Muster über die ganze Fläche bekommt den Umriss seines Trägers samt
    den Mündungen seiner Zellen — das ist die Fläche, wie sie nach dem Füllen
    aussieht, mit ihren echten Aussparungen. Ein Muster in einem Feld bekommt
    sein Rechteck, **geschnitten mit dem Träger**: Die Hülle eines um 30 Grad
    gedrehten Wabengitters ragt an den Ecken über die Platte hinaus, und eine
    Zelle dort schnitte die Seitenwand an. Um einen Zylinder endet der Umriss
    an der Naht der Abwicklung: Was darüber hinausreichte, käme beim
    Zurückbiegen ein zweites Mal auf dieselbe Stelle.
    """
    from shapely import affinity
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union

    params = feature.params
    frame = frame_for(feature, mesh, features)
    centre = np.asarray(params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
    developed, levels = frame.developed(centre)
    middle, level = developed[0], float(levels[0])
    angle = float(params.get("angle", 0.0))
    width = float(params.get("width", 0.0))
    height = float(params.get("height", 0.0))
    field = box(-width / 2.0, -height / 2.0, width / 2.0, height / 2.0)
    carrier = carrier_of(feature, features)
    if carrier is None or not carrier.face_indices:
        return Field(field, frame, middle, angle, level)
    body = mesh.raw
    indices = np.asarray(carrier.face_indices, dtype=np.int64)
    indices = indices[(indices >= 0) & (indices < len(body.faces))]
    corners = np.asarray(body.triangles, dtype=float)[indices]
    flat = frame.developed(corners.reshape(-1, 3))[0].reshape(-1, 3, 2) - middle
    if frame.kind == "cylinder":
        # Erst jede Ecke auf das Blatt um die Mitte, dann je Dreieck um seine
        # erste Ecke: Eines über der Naht bleibt ein Dreieck und wird kein
        # Band um den ganzen Umfang.
        around = 2.0 * math.pi * frame.radius
        half = around / 2.0
        flat[:, :, 0] = (flat[:, :, 0] + half) % around - half
        relative = flat[:, :, 0] - flat[:, :1, 0]
        flat[:, :, 0] -= around * np.round(relative / around)
    pieces = [Polygon(triangle) for triangle in flat]
    if frame.kind == "cylinder":
        # Ein Dreieck über der Naht liegt auf beiden Seiten des Blatts — als
        # eines gezählt fehlte sein Stück jenseits der Naht, und der Umriss
        # endete 0,64 mm vor ihr (22.09.2026: ein Steg über der Naht mit
        # einem Loch in der Mitte).
        crossing = (flat[:, :, 0].max(axis=1) > half) | (flat[:, :, 0].min(axis=1) < -half)
        for triangle in flat[crossing]:
            pieces.append(Polygon(triangle + np.array([around, 0.0])))
            pieces.append(Polygon(triangle - np.array([around, 0.0])))
    circumference = 2.0 * math.pi * frame.radius
    around = 0.0
    if frame.kind == "cylinder":
        # Ein Feld, das einmal herumreicht, endet an keiner Kante: Beim
        # Neuzeichnen gilt der Umriss periodisch, und die Naht schneidet
        # keine Zelle (``texture_ops.flat_tool``). Nur ungedreht — so legt
        # ``apply_texture`` ein Feld um einen Zylinder.
        pitch = float(params.get("pitch", 0.0))
        if width >= circumference - pitch and _turn(angle) <= SAME_DIRECTION_DEGREES:
            around = circumference
    for mouth in mouths_of(mesh, feature, features):
        # Derselbe Umriss, den der Stopfen füllt. Eine Zelle am Stirnrand
        # liefert sonst einen gezackten Mündungsrand innerhalb der glatten
        # gefüllten Fläche. Das neue Werkzeug schnitte dort Nullhäute ab.
        moved = affinity.translate(
            _mouth_with_margin(mouth, frame), -float(middle[0]), -float(middle[1])
        )
        pieces.append(moved)
        if frame.kind == "cylinder":
            # Eine Zelle über der Naht liegt auf beiden Seiten des Blatts.
            pieces.append(affinity.translate(moved, circumference))
            pieces.append(affinity.translate(moved, -circumference))
    # Geschlossen, nicht nur vereinigt: Wo Mündung und Trägerdreieck um ein
    # Rundungsrauschen auseinanderliegen, bleibt in der Vereinigung ein Schlitz
    # ohne Fläche, und ein Schnitt danach zerlegte den Umriss in 65 Stücke —
    # mit einem Schlitz mitten im neuen Steg (22.09.2026).
    outline = (
        unary_union(pieces).buffer(units.MAX_FACET_SAG / 10.0).buffer(-units.MAX_FACET_SAG / 10.0)
    )
    if frame.kind == "cylinder":
        half = circumference / 2.0
        reach = float(np.abs(flat[:, :, 1]).max()) + height
        outline = _solid(outline.intersection(box(-half, -reach, half, reach)))
    outline = affinity.rotate(outline, -angle, origin=(0.0, 0.0))
    if around:
        # Über den ganzen Umfang gilt nur die Höhe des Feldes als Grenze.
        outline = _solid(
            outline.intersection(box(-circumference, -height / 2.0, circumference, height / 2.0))
        )
    elif params.get("coverage") != "whole_face":
        outline = _solid(outline.intersection(field))
    if outline.is_empty or outline.area <= EPS_GEOM:
        return Field(field, frame, middle, angle, level, around)
    return Field(outline, frame, middle, angle, level, around)


def _solid(geometry: Any) -> Any:
    """Nur die Flächen eines Schnittergebnisses — Linien und Punkte am Rand fallen weg."""
    from shapely.ops import unary_union

    parts = [
        part
        for part in getattr(geometry, "geoms", [geometry])
        if part.geom_type == "Polygon" and part.area > EPS_GEOM
    ]
    return unary_union(parts) if parts else geometry


def _widened_towards_the_axis(prism: Any, middle: float, height: float, radius: float) -> None:
    """Den Boden eines vertieften Stopfens um einen Zylinder so weit wie die Tasche dort.

    In der Abwicklung ist ein Millimeter **im Umfang** in der Tiefe ``d`` unter
    dem Mantel ``R / (R - d)`` Millimeter breit: Eine Tasche mit **parallelen**
    Wänden — gefräst, aus einer fremden Datei — wird zum Boden hin breiter,
    eine mit radialen Wänden (so biegt ``apply_texture``) bleibt gleich. Bis
    zum 22.09.2026 blieb der Stopfen ein gerades Prisma über der Mündung; an
    48 Taschen 3 auf 5 mm um einen Griff Ø 30 standen danach 96 eingeschlossene
    Hohlräume von je 0,07 mm³ am Taschenboden. Der Boden wird deshalb um die
    Mitte der Mündung (``middle``, die erste Achse der Abwicklung) um diesen
    Faktor gestreckt. Was er dabei mehr deckt, ist Material unter dem Mantel —
    die Vereinigung ändert dort nichts.

    **Nur im Umfang:** Entlang der Achse ist eine Tasche in jeder Tiefe gleich
    lang. Bis zum 23.09.2026 streckte der Boden in beiden Achsen, und eine
    Zelle, die durch eine Stirnfläche läuft, ragte mit einem Keil über sie
    hinaus — 31 Rillen um einen Griff Ø 30 legten beim Entfernen 10,9 mm³
    Material über der Stirnfläche an.

    ``prism`` steht auf Z = 0 (der Boden) bis ``height`` (die Mündung) und wird
    an Ort und Stelle geändert.
    """
    if radius <= height + EPS_GEOM:
        return
    factor = radius / (radius - height)
    vertices = np.array(prism.vertices, dtype=float)
    floor = vertices[:, 2] <= EPS_GEOM
    vertices[floor, 0] = middle + (vertices[floor, 0] - middle) * factor
    prism.vertices = vertices


def _mouth_with_margin(mouth: Mouth, frame: Frame) -> Any:
    """Der Mündungsumriss, den der Stopfen und danach das neue Muster benutzen.

    Um den Zylinder deckt der Saum die verschieden fein gebogenen Sehnen von
    Stopfen und Zellwand. Ohne ihn kreuzten sie einander: Die Differenz ließ
    Splitter stehen, die Vereinigung Muster von einem Hundertstel Tiefe.
    Auf einer Ebene fällt die Mündung bereits exakt auf ihre Wand.
    Das Neuzeichnen liest denselben Saum: Was der Stopfen dort füllt, gehört
    anschließend zur Trägerfläche und ist keine Aussparung im Feld.
    """
    margin = 0.0 if frame.kind == "plane" else 2.0 * frame.clearance
    return mouth.polygon.buffer(margin, join_style="mitre") if margin > 0.0 else mouth.polygon


def _within_span(polygon: Any, span: tuple[float, float] | None) -> list[Any]:
    """Die Stücke eines Umrisses zwischen den Stirnflächen — oder der Umriss selbst.

    Geschnitten wird nur, wo er über eine hinausreicht: Jede andere Zelle
    behält ihren Umriss Bit für Bit. Das Rechteck reicht in der ersten Achse
    um die eigene Breite über den Umriss hinaus, damit keine seiner Kanten auf
    einer Ecke liegt.
    """
    from shapely.geometry import box

    if span is None:
        return [polygon]
    left, bottom, right, top = polygon.bounds
    if bottom >= span[0] and top <= span[1]:
        return [polygon]
    width = right - left
    clipped = polygon.intersection(box(left - width, span[0], right + width, span[1]))
    return [
        part
        for part in getattr(clipped, "geoms", [clipped])
        if part.geom_type == "Polygon" and part.area > EPS_GEOM
    ]


def _extruded(polygon: Any, height: float) -> Any:
    """Ein Prisma über einem Umriss, stehend auf Z = 0 — oder nichts."""
    import trimesh

    try:
        return trimesh.creation.extrude_polygon(polygon, height=height)
    except ValueError, IndexError:
        return None


def _components(body: Any, indices: np.ndarray) -> list[np.ndarray]:
    """Die zusammenhängenden Stücke dieser Dreiecke — als Positionen in ``indices``."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    position = np.full(len(body.faces), -1, dtype=np.int64)
    position[indices] = np.arange(len(indices))
    adjacency = np.asarray(body.face_adjacency, dtype=np.int64)
    inside = (position[adjacency[:, 0]] >= 0) & (position[adjacency[:, 1]] >= 0)
    pairs = position[adjacency[inside]]
    graph = coo_matrix(
        (np.ones(len(pairs), dtype=np.int8), (pairs[:, 0], pairs[:, 1])),
        shape=(len(indices), len(indices)),
    )
    count, labels = connected_components(graph, directed=False)
    # Einmal sortiert statt je Stück über alle Etiketten gefragt: das war
    # Stückzahl mal Dreieckszahl, an einem Kreuzrändel mit 434 Zellen die
    # Hälfte der Mündungssuche. Stabil sortiert, also je Stück aufsteigend wie
    # bisher.
    order = np.argsort(labels, kind="stable")
    bounds = np.searchsorted(labels[order], np.arange(count + 1))
    return [order[bounds[label] : bounds[label + 1]] for label in range(count)]


def _rim_edges(triangles: np.ndarray) -> np.ndarray:
    """Die Kanten, die genau ein Dreieck des Ausschnitts haben.

    Über ``geom.mesh.unique_edges`` und nicht ``np.unique(…, axis=0)`` — die
    Frage fällt je Zelle, und dort gilt die Regel aus ``kern.md``.
    """
    edges = np.vstack((triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]))
    unique, counts = unique_edges(edges, return_counts=True)
    return np.asarray(unique[counts == 1], dtype=np.int64)


def _loops(edges: np.ndarray) -> list[np.ndarray]:
    """Kanten zu geschlossenen Ringen verketten; offene Ketten fallen aus."""
    if len(edges) < 3:
        return []
    neighbours: dict[int, list[int]] = {}
    for start, end in edges.tolist():
        neighbours.setdefault(start, []).append(end)
        neighbours.setdefault(end, []).append(start)
    if any(len(links) != 2 for links in neighbours.values()):
        return []
    seen: set[int] = set()
    loops: list[np.ndarray] = []
    for first in neighbours:
        if first in seen:
            continue
        loop = [first]
        seen.add(first)
        previous, current = first, neighbours[first][0]
        while current != first:
            loop.append(current)
            seen.add(current)
            links = neighbours[current]
            previous, current = current, links[1] if links[0] == previous else links[0]
        if len(loop) >= 3:
            loops.append(np.asarray(loop, dtype=np.int64))
    return loops
