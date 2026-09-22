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

**Was hier nicht erkannt wird:** Muster auf gewölbten Trägern — ein Rändel
um einen Griff (``apply_texture`` mit ``wrap="cylinder"``). Der Träger ist
dort ein Zylinder, und das Gitter liegt in seiner Abwicklung; das steht im
Register als eigener Punkt.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import numpy as np

from app.core import units
from app.core.geom.mesh import MeshData
from app.core.types import Feature, FeatureId, Vec3
from app.core.units import EPS_GEOM

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

#: Wie viele der Zellen ihren nächsten Nachbarn in der Teilung haben müssen.
#:
#: Neun von zehn: Die Zellen am Rand eines Feldes haben weniger Nachbarn,
#: aber denselben Abstand zum nächsten; was fehlt, sind Ausreißer, wo das
#: Gitter eine Bohrung ausspart und die Zelle dahinter weiter weg liegt.
REGULAR_SHARE: Final = 0.9

#: Wie weit ein Nachbarabstand von der Teilung abweichen darf — und zwei
#: Zellen in Tiefe, Breite und Mündungsfläche voneinander, um dieselbe zu
#: sein. Ein Zwanzigstel: Ein Netz aus einem Slicer-Export rundet auf
#: Tausendstel, ein Netz aus einem Scan gar nicht, und ein Kunde, der eine
#: Zelle ändert, ändert sie nicht um fünf Prozent.
SAME_MEASURE: Final = 0.05

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

#: Welche Zellarten rund sind, wenn ihre Mitglieder es sagen.
ROUND_KINDS: Final[frozenset[str]] = frozenset({"hole", "pin", "sphere"})

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
    normal: np.ndarray
    lift: float
    """Wo die Trägerebene entlang der Normalen liegt."""
    centre: np.ndarray
    """Der Schwerpunkt der Mündung, in der Trägerebene."""
    outline: np.ndarray
    """Die konvexe Hülle der Mündung, in den Ebenenachsen zur Normalen (``_plane_axes``)."""
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
    normal: Vec3
    direction: Vec3
    """Die Gitterrichtung in der Welt — zum nächsten Nachbarn, quer zu einer Rippe."""
    centre: Vec3
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
        kept[name] = _feature_of(name, pattern)
    return kept


def _feature_of(name: str, pattern: Pattern) -> Feature:
    """Das Merkmal aus dem Fund — jede Zahl am Netz gemessen (``facets``)."""
    first = pattern.cells[0]
    depth = float(np.median([cell.depth for cell in pattern.cells]))
    width = float(np.median([cell.width for cell in pattern.cells]))
    return Feature(
        id=name,
        kind="pattern",
        provenance="detected",
        measure_sources={
            "pitch": "facets",
            "cell_width": "facets",
            "cell_depth": "facets",
            "centre": "facets",
            "normal": "facets",
            "direction": "facets",
            "width": "facets",
            "height": "facets",
            "area": "facets",
        },
        params={
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
        },
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
    nearest = min(pattern.cells, key=lambda cell: float(np.linalg.norm(cell.centre - centre)))
    return _vec(nearest.centre)


def find_patterns(
    mesh: MeshData,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Pattern]:
    """Alle Muster an diesem Körper, nach Lage sortiert (§21.2)."""
    body = mesh.raw
    triangle_count = len(body.faces)
    owned = {
        name: feature
        for name, feature in found.items()
        if feature.face_indices and (feature.kind in CELL_KINDS or feature.kind == "face")
    }
    faces = {name: feature for name, feature in owned.items() if feature.kind == "face"}
    if triangle_count == 0 or len(faces) < 2:
        return []
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
    # und der Träger ist höchstens die größte ebene Fläche des Körpers.
    largest = max(float(faces[name].params.get("area", 0.0)) for name in faces)
    limit = largest / MIN_CELLS
    small = np.array(
        [
            areas[index] <= limit and owned[name].kind in CELL_KINDS
            for index, name in enumerate(names)
        ]
    )
    candidate_features = np.flatnonzero(small)
    if len(candidate_features) < MIN_CELLS:
        return []
    # **Auch, was kein Merkmal ist, kann Zellwand sein.** Die Wände einer
    # Welle sind acht schmale Streifen je Periode, und die Flächensuche nennt
    # sie nicht; die Wände eines Voronoi-Felds stehen zur Hälfte ohne Namen
    # da. Eine Zelle besteht aus allem Kleinen zwischen ihren Trägern — was
    # kein Träger und keine Sammelform ist, gehört dazu.
    candidate = (owner < 0) | np.isin(owner, candidate_features)
    carrier_feature = np.array(
        [owned[name].kind == "face" and not small[index] for index, name in enumerate(names)]
    )
    if check_cancelled is not None:
        check_cancelled()

    cells, pieces = _cells(
        body, owned, names, owner, candidate, carrier_feature, check_cancelled=check_cancelled
    )
    if len(cells) < min(MIN_CELLS, MIN_STRIPS):
        return []
    if check_cancelled is not None:
        check_cancelled()

    carriers = {
        name: _carrier_outline(body, faces[name]) for name in {cell.carrier[0] for cell in cells}
    }
    measure = _CellMeasure(body, owned, names, owner)
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
    patterns.sort(key=lambda pattern: tuple(round(value, 3) for value in pattern.centre))
    return patterns


def _least_cells(cell: Cell) -> int:
    """Wie viele Geschwister diese Zelle braucht — runde mehr als eckige, Streifen weniger."""
    if cell.round:
        return MIN_ROUND_CELLS
    if cell.style in {"rib", "wave"}:
        return MIN_STRIPS
    return MIN_CELLS


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
    owned: Mapping[FeatureId, Feature],
    names: Sequence[FeatureId],
    owner: np.ndarray,
    candidate: np.ndarray,
    carrier_feature: np.ndarray,
    *,
    check_cancelled: Callable[[], None] | None,
) -> tuple[list[Cell], list[EdgePiece]]:
    """Zusammenhängende Stücke aus Kandidatenmerkmalen, am Netz vermessen.

    Dazu die Randstücke (:class:`EdgePiece`), die an Träger quer zueinander
    grenzen — vermessen werden sie erst, wenn ein Muster sie an seinem
    Träger als angeschnittene Zellen fragt.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

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

    measure = _CellMeasure(body, owned, names, owner)
    normals = measure.normals
    cells: list[Cell] = []
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
        carrier = _carriers_of(owners, names, normals)
        if carrier is None:
            # Träger quer zueinander: eine Ecke — oder eine Zelle am Rand.
            pieces.append(EdgePiece(indices, tuple(names[int(index)] for index in owners)))
            continue
        cell = measure(indices, carrier)
        if cell is not None:
            cells.append(cell)
    return cells, pieces


class _CellMeasure:
    """Das Netz einmal gelesen, dann je Zelle gemessen — auch später für die Randstücke."""

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

    def __call__(
        self, indices: np.ndarray, carrier: tuple[FeatureId, ...], *, clipped: bool = False
    ) -> Cell | None:
        return _measure_cell(
            indices,
            self.owner,
            self.names,
            self.owned,
            self.triangles,
            self.points,
            self.triangle_normals,
            self.triangle_areas,
            self.normals,
            carrier,
            clipped=clipped,
        )


def _carriers_of(
    owners: np.ndarray,
    names: Sequence[FeatureId],
    normals: Mapping[FeatureId, np.ndarray],
) -> tuple[FeatureId, ...] | None:
    """Die Träger einer ganzen Zelle: einer, oder zwei einander gegenüber.

    Alles andere — Träger quer zueinander — ist kein Fall für hier: eine
    Ecke des Körpers, oder eine Zelle, die der Rand anschneidet. Die bleibt
    ein :class:`EdgePiece`, bis ein Muster sie an seinem Träger fragt.
    """
    if owners.size > 2:
        return None
    first = normals[names[int(owners[0])]]
    if float(np.linalg.norm(first)) < EPS_GEOM:
        return None
    if owners.size == 2:
        second = normals[names[int(owners[1])]]
        if float(np.linalg.norm(second)) < EPS_GEOM:
            return None
        alignment = float(first @ second) / (
            float(np.linalg.norm(first)) * float(np.linalg.norm(second))
        )
        if alignment > -1.0 + SAME_MEASURE:
            return None
    return tuple(names[int(index)] for index in owners)


def _measure_cell(
    indices: np.ndarray,
    owner: np.ndarray,
    names: Sequence[FeatureId],
    owned: Mapping[FeatureId, Feature],
    triangles: np.ndarray,
    points: np.ndarray,
    triangle_normals: np.ndarray,
    triangle_areas: np.ndarray,
    normals: Mapping[FeatureId, np.ndarray],
    carrier: tuple[FeatureId, ...],
    *,
    clipped: bool = False,
) -> Cell | None:
    """Tiefe, Mündung, Seite und Umriss einer Zelle."""
    # Nur, was ein Merkmal besitzt: Ein unbesessenes Dreieck trägt -1, und
    # ``names[-1]`` wäre das letzte Merkmal der Liste — die kleinste Fläche
    # des Körpers, die dann mit dem Muster aus dem Baum verschwände, auch
    # wenn sie an einer Tasche am anderen Ende der Platte liegt.
    members = tuple(
        sorted({names[int(index)] for index in np.unique(owner[indices]) if index >= 0})
    )
    first = normals[carrier[0]]
    if float(np.linalg.norm(first)) < EPS_GEOM:
        return None
    through = False
    if len(carrier) == 2:
        second = normals[carrier[1]]
        # Zwei Träger sind nur dann eine durchgehende Zelle, wenn sie
        # einander gegenüberliegen; sonst ist es eine Ecke.
        if float(first @ second) > -1.0 + SAME_MEASURE:
            return None
        through = True
        carrier = _front_carrier(carrier, normals, owned)
        first = normals[carrier[0]]
    normal = first / float(np.linalg.norm(first))
    corners = points[triangles[indices]].reshape(-1, 3)
    # Die Trägerebene liegt dort, wo die Zelle mündet: an ihren äußersten
    # Punkten entlang der Normalen, denn die Zelle liegt ganz auf einer Seite.
    heights = corners @ normal
    top, bottom = float(heights.max()), float(heights.min())
    depth = top - bottom
    if depth <= EPS_GEOM:
        return None
    # Eine durchgehende Zelle ist ein Loch — vertieft, ohne Frage. Ihre Wände
    # liegen symmetrisch zwischen beiden Trägern, und ein Mittel darüber
    # entschiede nach Rundungsrauschen.
    centroids = points[triangles[indices]].mean(axis=1) @ normal
    raised = not through and float(centroids.mean()) > (top + bottom) / 2.0
    plane = bottom if raised else top
    mouth = corners[np.abs(heights - plane) <= _flat_tolerance(depth)]
    if len(mouth) < 3:
        return None
    x_axis, y_axis = _plane_axes(normal)
    # In den Ebenenachsen, aber vom Weltursprung aus — so liegen die Umrisse
    # aller Zellen eines Trägers im selben Blatt und lassen sich vergleichen.
    hull = _convex_hull(np.column_stack((mouth @ x_axis, mouth @ y_axis)))
    if hull is None:
        return None
    width, length = _calipers(hull)
    if width <= EPS_GEOM:
        return None
    area = _polygon_area(hull)
    corner_count = _corner_count(hull)
    flat_centre = _polygon_centroid(hull)
    centre = x_axis * flat_centre[0] + y_axis * flat_centre[1] + normal * plane
    is_round = corner_count >= ROUND_CORNERS or any(
        owned[name].kind in ROUND_KINDS for name in members
    )
    if is_round and (through or depth > width * ROUND_DEPTH * (1.0 + SAME_MEASURE)):
        # Eine runde Zelle, die durchgeht oder tief ist, ist eine Bohrung und
        # bleibt eine — siehe den Modulkopf.
        return None
    axis = _longest_edge(hull)
    straight, wall_area = _straight_share(
        indices, triangle_normals, triangle_areas, normal, axis, x_axis, y_axis
    )
    return Cell(
        members=members,
        face_indices=tuple(int(index) for index in indices),
        carrier=carrier,
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
        style=_style_of(hull, corner_count, width, length, is_round, straight=straight),
        straight=straight,
        wall_area=wall_area,
    )


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
    ranked = sorted(
        carrier,
        key=lambda name: (
            -round(float(normals[name][2]), 6),
            -float(owned[name].params.get("area", 0.0)),
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
    keine Skizze (``tests/test_core_package_direction.py``).
    """
    axes = units.plane_axes((float(normal[0]), float(normal[1]), float(normal[2])))
    if axes is None:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
    return np.asarray(axes[0], dtype=float), np.asarray(axes[1], dtype=float)


def _straight_share(
    indices: np.ndarray,
    triangle_normals: np.ndarray,
    triangle_areas: np.ndarray,
    normal: np.ndarray,
    axis: np.ndarray,
    x_axis: np.ndarray,
    y_axis: np.ndarray,
) -> tuple[float, float]:
    """Welcher Anteil der Wandfläche parallel zur Streifenachse steht — und wie viel Wand es ist.

    Wände sind die Dreiecke quer zum Träger; parallel zur Achse heißt: ihre
    Normale steht senkrecht auf ihr. Eine Rippe hat das an ihren zwei langen
    Wänden, eine Welle nirgends. Die Wandfläche kommt mit, weil eine Reihe
    von Streifen als Ganzes entscheidet, ob sie Rippen sind (``_lattice_of``):
    Ein kurzer, am Feldrand schräg abgeschnittener Streifen hat mehr Stirn
    als Flanke und sähe allein wie eine Welle aus.
    """
    normals_here = triangle_normals[indices]
    walls = np.abs(normals_here @ normal) < 0.5
    if not walls.any():
        return 1.0, 0.0
    axis_world = x_axis * axis[0] + y_axis * axis[1]
    parallel = np.abs(normals_here[walls] @ axis_world) <= math.sin(math.radians(CORNER_DEGREES))
    total = float(triangle_areas[indices][walls].sum())
    if total <= EPS_GEOM:
        return 1.0, 0.0
    return float(triangle_areas[indices][walls][parallel].sum()) / total, total


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


def _polygon_centroid(polygon: np.ndarray) -> np.ndarray:
    """Der Flächenschwerpunkt eines geschlossenen Umrisses — nicht das Mittel seiner Ecken.

    Am Rand eines Feldes ist eine Zelle abgeschnitten; das Mittel ihrer Ecken
    wanderte dann zur Schnittkante, der Schwerpunkt bleibt, wo die Fläche ist.
    """
    x, y = polygon[:, 0], polygon[:, 1]
    cross = x * np.roll(y, -1) - np.roll(x, -1) * y
    doubled = float(cross.sum())
    if abs(doubled) <= EPS_GEOM:
        return polygon.mean(axis=0)
    return np.array(
        [
            float(((x + np.roll(x, -1)) * cross).sum() / (3.0 * doubled)),
            float(((y + np.roll(y, -1)) * cross).sum() / (3.0 * doubled)),
        ]
    )


def _longest_edge(polygon: np.ndarray) -> np.ndarray:
    """Die Richtung der längsten Kante, als Einheitsvektor."""
    edges = np.roll(polygon, -1, axis=0) - polygon
    longest = edges[int(np.argmax(np.linalg.norm(edges, axis=1)))]
    return np.asarray(longest / max(float(np.linalg.norm(longest)), EPS_GEOM), dtype=float)


def _polygon_area(polygon: np.ndarray) -> float:
    """Schnürsenkel — die Fläche eines geschlossenen Umrisses."""
    x, y = polygon[:, 0], polygon[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)


def _calipers(polygon: np.ndarray) -> tuple[float, float]:
    """Kleinste und größte Breite eines konvexen Umrisses.

    Die kleinste: je Kante der größte Abstand einer Ecke von ihrer Geraden,
    davon das Minimum — die Schlüsselweite eines Sechsecks, die Seite einer
    Raute, die Breite einer Rippe. Die größte: der weiteste Eckenabstand.
    """
    edges = np.roll(polygon, -1, axis=0) - polygon
    lengths = np.linalg.norm(edges, axis=1)
    keep = lengths > EPS_GEOM
    if not keep.any():
        return 0.0, 0.0
    normals = np.column_stack((-edges[keep, 1], edges[keep, 0])) / lengths[keep, None]
    distances = (polygon[None, :, :] - polygon[keep][:, None, :]) * normals[:, None, :]
    width = float(np.abs(distances.sum(axis=2)).max(axis=1).min())
    spread = polygon[:, None, :] - polygon[None, :, :]
    length = float(np.linalg.norm(spread, axis=2).max())
    return width, length


def _corner_count(polygon: np.ndarray) -> int:
    """Wie viele echte Ecken der Umriss hat — Nähte gerader Kanten zählen nicht."""
    edges = np.roll(polygon, -1, axis=0) - polygon
    angles = np.arctan2(edges[:, 1], edges[:, 0])
    steps = np.diff(np.append(angles, angles[0]))
    turns = np.degrees(np.abs((steps + math.pi) % (2 * math.pi) - math.pi))
    return int(np.count_nonzero(turns > CORNER_DEGREES))


def _style_of(
    hull: np.ndarray,
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
    if length >= RIB_ASPECT * width:
        return "rib" if straight >= STRAIGHT_SHARE else "wave"
    sides = _side_lengths(hull)
    if corners == 6 and len(sides) == 6 and _all_alike(sides):
        return "hexagon"
    if corners == 4 and len(sides) == 4:
        diagonals = (
            float(np.linalg.norm(hull[2] - hull[0])),
            float(np.linalg.norm(hull[3] - hull[1])),
        )
        if _all_alike(sides) and _all_alike(diagonals):
            return "knurl_diamond"
    return "other"


def _side_lengths(hull: np.ndarray) -> tuple[float, ...]:
    """Die Seiten des Umrisses zwischen echten Ecken."""
    edges = np.roll(hull, -1, axis=0) - hull
    angles = np.arctan2(edges[:, 1], edges[:, 0])
    lengths = np.linalg.norm(edges, axis=1)
    sides: list[float] = []
    running = 0.0
    for index in range(len(hull)):
        running += float(lengths[index])
        step = angles[(index + 1) % len(hull)] - angles[index]
        turn = abs((step + math.pi) % (2 * math.pi) - math.pi)
        if math.degrees(turn) > CORNER_DEGREES:
            sides.append(running)
            running = 0.0
    if running > EPS_GEOM and sides:
        sides[0] += running
    return tuple(sides)


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
    large = [group for group in groups if len(group) >= _least_cells(group[0])]
    large.sort(key=len, reverse=True)
    return large


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


def _rows_of(group: Sequence[Cell]) -> tuple[str, float, float] | None:
    """Die Reihe der Streifen: Teilung quer zu ihrer Achse.

    Die Mitten schräg abgeschnittener Streifen wandern entlang des Streifens;
    was bleibt, ist ihr Abstand **quer** dazu, und der ist die Teilung.
    Gemessen an den Kanten, die der Achse folgen — nicht am Schwerpunkt, der
    an einem fünfeckig abgeschnittenen Streifen neben der Mittellinie liegt.
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
    if len(steps) < MIN_STRIPS - 1:
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
    along[along] = np.abs(edges[along] @ axis) / lengths[along] >= math.cos(
        math.radians(CORNER_DEGREES)
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
        ((lattice_angle - offset + turn) % 180.0, style)
        for turn in _LATTICE_TURNS.get(lattice, (0.0,))
    ]
    if style == "rib":
        turned = (lattice_angle - _LATTICE_OFFSET["knurl_straight"]) % 180.0
        boxes.append((turned, "knurl_straight"))
    chosen = min(
        ((*_box(outlines, angle), angle, name) for angle, name in boxes),
        key=lambda box: round(box[0], 6),
    )
    _area, width, height, middle, angle, style = chosen
    x_axis, y_axis = _plane_axes(first.normal)
    centre = x_axis * middle[0] + y_axis * middle[1] + first.normal * first.lift
    radians = math.radians(lattice_angle)
    direction = x_axis * math.cos(radians) + y_axis * math.sin(radians)
    return Pattern(
        style=style,
        cells=tuple(cells),
        partial=tuple(partial),
        carrier=first.carrier,
        normal=_vec(first.normal),
        direction=_vec(direction),
        centre=_vec(centre),
        pitch=pitch,
        lattice=lattice,
        lattice_angle=lattice_angle,
        width=width,
        height=height,
        angle=angle,
        coverage="rectangle",
    )


def _box(outlines: np.ndarray, angle: float) -> tuple[float, float, float, np.ndarray]:
    """Die Hülle aller Umrisse in einem um ``angle`` gedrehten Rechteck.

    Zurück kommen Fläche, Breite, Höhe und Mitte — die Mitte in den Achsen der
    Ebene, nicht des Rechtecks.
    """
    along = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
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
    x_axis, y_axis = _plane_axes(np.asarray(pattern.normal, dtype=float))
    along = np.array([math.cos(math.radians(pattern.angle)), math.sin(math.radians(pattern.angle))])
    across = np.array([-along[1], along[0]])
    centre = np.asarray(pattern.centre, dtype=float)
    middle = np.array([float(centre @ x_axis), float(centre @ y_axis)])
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
    x_axis, y_axis = _plane_axes(np.asarray(pattern.normal, dtype=float))
    flat = np.column_stack((carrier_points @ x_axis, carrier_points @ y_axis))
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
    x_axis, y_axis = _plane_axes(first.normal)
    centre = x_axis * middle[0] + y_axis * middle[1] + first.normal * first.lift
    return Pattern(
        style=style,
        cells=tuple(cells),
        partial=tuple(partial),
        carrier=first.carrier,
        normal=_vec(first.normal),
        direction=_vec(x_axis),
        centre=_vec(centre),
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
    """Die Mündung einer Zelle, als Umriss in der Trägerebene, und ihre Tiefe."""

    polygon: Any
    """``shapely.Polygon`` in den Ebenenachsen zur Normalen (``_plane_axes``)."""
    depth: float


def mouths_of(mesh: MeshData, feature: Feature) -> list[Mouth]:
    """Die Mündungen aller Zellen eines Musters, am Netz nachgezeichnet.

    Je Zelle die Randkanten ihrer Dreiecke, die in der Trägerebene liegen,
    zu einem Ring verkettet — das ist ihr Umriss, exakt und ohne Annahme
    über die Form. Eine Zelle, deren Ring sich nicht schließt, fällt aus;
    der Aufrufer sieht das an der Zahl.
    """
    from shapely.geometry import Polygon
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
    length = float(np.linalg.norm(normal))
    if length <= EPS_GEOM:
        return []
    normal = normal / length
    lift = float(np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float) @ normal)
    x_axis, y_axis = _plane_axes(normal)
    raised = feature.params.get("mode") == "raised"
    triangles = np.asarray(body.faces, dtype=np.int64)[indices]
    points = np.asarray(body.vertices, dtype=float)
    heights = points @ normal
    mouths: list[Mouth] = []
    for component in _components(body, indices):
        chosen = triangles[component]
        corners = np.unique(chosen)
        span = heights[corners]
        depth = float(span.max() - span.min())
        if depth <= EPS_GEOM:
            continue
        plane = float(span.min()) if raised else float(span.max())
        if abs(plane - lift) > _flat_tolerance(depth) + units.MAX_FACET_SAG:
            continue
        rim = _rim_edges(chosen)
        on_plane = np.abs(heights[rim] - plane) <= _flat_tolerance(depth)
        rim = rim[on_plane.all(axis=1)]
        loops = _loops(rim)
        if not loops:
            # Zwei Streuflecken, die sich in einem Punkt berühren, haben dort
            # eine Ecke mit vier Kanten, und der Ring schließt sich nicht.
            # Dann die konvexe Hülle: Sie deckt die Zelle und darüber hinaus
            # nur, was beim Füllen schon Material und beim Abtragen Luft ist.
            hull = _convex_hull(
                np.column_stack((points[rim.ravel()] @ x_axis, points[rim.ravel()] @ y_axis))
            )
            if hull is not None:
                mouths.append(Mouth(polygon=Polygon(hull), depth=depth))
            continue
        for loop in loops:
            flat = np.column_stack((points[loop] @ x_axis, points[loop] @ y_axis))
            polygon = make_valid(Polygon(flat))
            for part in getattr(polygon, "geoms", [polygon]):
                if part.geom_type == "Polygon" and part.area > EPS_GEOM:
                    mouths.append(Mouth(polygon=part, depth=depth))
    return mouths


def plug_for(mesh: MeshData, feature: Feature) -> MeshData | None:
    """Der Körper, der die Zellen eines Musters füllt oder abträgt.

    Je Mündung ein Prisma über die Tiefe der Zelle: vertieft von der
    Trägerebene ins Material, erhaben von ihr weg, und **bündig mit der
    Ebene**. Um den Überlapp der Booleschen Rechnung verlängert ist nur das
    ferne Ende — an der Ebene ließe ein Überlapp eine Haut von einem
    Hundertstel stehen beziehungsweise fehlen, und die Erkennung fände danach
    ein Muster von einem Hundertstel Tiefe (gemessen am 22.09.2026: 56 Zellen,
    3,2 mm³). Die Vereinigung füllt eine vertiefte Zelle genau — was das
    Prisma sonst noch deckt, ist schon Material —, die Differenz trägt eine
    erhabene bis auf die Ebene ab.
    """
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.geom.mesh import concatenated

    mouths = mouths_of(mesh, feature)
    if not mouths:
        return None
    normal = np.asarray(feature.params.get("normal", (0.0, 0.0, 1.0)), dtype=float)
    normal = normal / float(np.linalg.norm(normal))
    lift = float(np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float) @ normal)
    raised = feature.params.get("mode") == "raised"
    # Eine durchgehende Zelle mündet auf beiden Seiten in eine Fläche; ihr
    # Prisma ist auf beiden bündig — ein Überlapp stünde als Haut auf der
    # Rückseite (195 Sechsecke von einem Hundertstel am Halter, 22.09.2026).
    through = bool(feature.params.get("through", False))
    x_axis, y_axis = _plane_axes(normal)
    parts = []
    for mouth in mouths:
        height = mouth.depth if through else mouth.depth + BOOLEAN_OVERLAP
        prism = _extruded(mouth.polygon, height)
        if prism is None:
            continue
        start = lift if raised else lift - height
        matrix = np.eye(4)
        matrix[:3, :3] = np.column_stack((x_axis, y_axis, normal))
        matrix[:3, 3] = normal * start
        prism.apply_transform(matrix)
        parts.append(prism)
    if not parts:
        return None
    return MeshData.of(concatenated(parts))


def carrier_of(feature: Feature, features: Mapping[FeatureId, Feature]) -> Feature | None:
    """Die Trägerfläche eines Musters — gefunden über ihre Ebene, nicht über einen Namen.

    Ein Verweis auf ``face_2`` in den Parametern alterte: Die Zuordnung
    benennt Merkmale um (§21.2), den Verweis nicht. Die Ebene altert nicht:
    Der Träger ist die größte ebene Fläche mit derselben Normalen, deren
    Mitte in der Ebene des Musters liegt.
    """
    normal = np.asarray(feature.params.get("normal", (0.0, 0.0, 1.0)), dtype=float)
    normal = normal / max(float(np.linalg.norm(normal)), EPS_GEOM)
    lift = float(np.asarray(feature.params.get("centre", (0.0, 0.0, 0.0)), dtype=float) @ normal)
    depth = float(feature.params.get("cell_depth", 0.0))
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
        if best is None or float(candidate.params.get("area", 0.0)) > float(
            best.params.get("area", 0.0)
        ):
            best = candidate
    return best


def field_outline(
    mesh: MeshData, feature: Feature, features: Mapping[FeatureId, Feature]
) -> tuple[Any, np.ndarray, Vec3]:
    """Der Umriss, in dem ein Muster neu gezeichnet wird — samt Achsen und Nullpunkt.

    In den Achsen des Feldes: die erste liegt in der Gitterrichtung, wie
    ``apply_texture`` sie mit ``angle`` dreht, der Nullpunkt ist die Mitte des
    Musters. Ein Muster über die ganze Fläche bekommt den Umriss seines
    Trägers samt den Mündungen seiner Zellen — das ist die Fläche, wie sie
    nach dem Füllen aussieht, mit ihren echten Aussparungen. Ein Muster in
    einem Feld bekommt sein Rechteck, **geschnitten mit dem Träger**: Die
    Hülle eines um 30 Grad gedrehten Wabengitters ragt an den Ecken über die
    Platte hinaus, und eine Zelle dort schnitte die Seitenwand an.
    """
    from shapely import affinity
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union

    params = feature.params
    normal = np.asarray(params.get("normal", (0.0, 0.0, 1.0)), dtype=float)
    normal = normal / max(float(np.linalg.norm(normal)), EPS_GEOM)
    centre = np.asarray(params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
    angle = float(params.get("angle", 0.0))
    x_axis, y_axis = _plane_axes(normal)
    radians = math.radians(angle)
    along = x_axis * math.cos(radians) + y_axis * math.sin(radians)
    across = -x_axis * math.sin(radians) + y_axis * math.cos(radians)
    basis = np.column_stack((along, across, normal))
    origin: Vec3 = (float(centre[0]), float(centre[1]), float(centre[2]))
    width = float(params.get("width", 0.0))
    height = float(params.get("height", 0.0))
    field = box(-width / 2.0, -height / 2.0, width / 2.0, height / 2.0)
    carrier = carrier_of(feature, features)
    if carrier is None or not carrier.face_indices:
        return field, basis, origin
    body = mesh.raw
    indices = np.asarray(carrier.face_indices, dtype=np.int64)
    indices = indices[(indices >= 0) & (indices < len(body.faces))]
    corners = np.asarray(body.triangles, dtype=float)[indices]
    local = (corners - centre) @ basis
    pieces = [Polygon(triangle[:, :2]) for triangle in local]
    shift = (-float(centre @ x_axis), -float(centre @ y_axis))
    for mouth in mouths_of(mesh, feature):
        moved = affinity.translate(mouth.polygon, *shift)
        pieces.append(affinity.rotate(moved, -angle, origin=(0.0, 0.0)))
    outline = unary_union(pieces).buffer(0.0)
    if params.get("coverage") != "whole_face":
        outline = outline.intersection(field)
    if outline.is_empty or outline.area <= EPS_GEOM:
        return field, basis, origin
    return outline, basis, origin


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
    return [np.flatnonzero(labels == label) for label in range(count)]


def _rim_edges(triangles: np.ndarray) -> np.ndarray:
    """Die Kanten, die genau ein Dreieck des Ausschnitts haben."""
    edges = np.vstack((triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]))
    ordered = np.sort(edges, axis=1)
    unique, counts = np.unique(ordered, axis=0, return_counts=True)
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
