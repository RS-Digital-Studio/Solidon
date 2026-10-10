"""Weiches Verschmelzen zweier Körper (Bauplan §25, Konzept P16 Entscheidung N).

Die gewöhnliche Vereinigung stößt zwei Oberflächen aneinander und lässt in
jeder Innenecke eine scharfe Kehle stehen. Gedruckt ist genau dort die
Sollbruchstelle.

**Verrunden erreicht sie inzwischen** — der Vorbehalt „Verrundungen auf
Mesh-Kanten" ist am 10.09.2026 gefallen, und die Naht ist ein gewöhnlicher
Kantenzug: An einer Platte mit aufgesetzter Rippe kommen aus ``edges_of``
24 Züge, vier davon konkav. Es ist trotzdem etwas anderes. Eine Verrundung
legt einen festen Radius an eine **gewählte** Kante, nachdem die Vereinigung
schon gerechnet ist; sie kennt nur noch das Ergebnis. Diese Operation lässt
den Übergang aus **beiden** Körpern zugleich entstehen — niemand wählt eine
Kante, und wo die Naht keine saubere Linie hergibt, gibt es trotzdem einen
Übergang.

Deshalb rechnet diese Operation anders als alle anderen booleschen. Statt
Flächen zu schneiden legt sie beide Körper als **Abstandsfeld** auf ein
gemeinsames Raster, mischt die zwei Felder weich ineinander und zieht die neue
Oberfläche als Isofläche daraus. Der Übergang entsteht dabei nicht als
nachträgliche Verrundung, sondern als das, was das gemischte Feld ohnehin
beschreibt.

Der Preis ist ein Rasterverfahren: Was zwischen zwei Rasterpunkten liegt, wird
interpoliert, und scharfe Kanten der Ausgangskörper werden weicher, als sie
waren. Das wird ausgewiesen, nicht verschwiegen — genau wie die Voxelstufe der
Rückfallkette es tut (§17.3).
"""

from __future__ import annotations

import dataclasses
import functools
import math
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final, cast

import numpy as np

from app.core.deferred import cKDTree, trimesh
from app.core.errors import (
    CORRECT_INPUT,
    Action,
    NotManifoldError,
    ValidationError,
)
from app.core.geom import mesh_edits
from app.core.geom.mesh import (
    MeshData,
    as_mesh_data,
    row_dots,
    stable_normals,
    stable_vertex_normals,
    unique_edges,
)
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.registry.params import ZERO_NONE
from app.core.types import (
    BaseParams,
    CancelToken,
    Finding,
    OpContext,
    OpResult,
    ProgressFn,
)
from app.i18n import _

_log = get_logger(__name__)

#: Wie viele Rasterpunkte sich noch rechnen lassen. Darüber ist nicht die
#: Maschine zu langsam, sondern die Rasterweite falsch gewählt — die Meldung
#: sagt genau das und nennt die Weite, die noch geht.
MAX_SAMPLES: Final = 12_000_000

#: Wie weit das Raster über die Körper hinausreicht, in Rasterweiten. Der
#: Wulst wächst über die Hülle der Ausgangskörper hinaus, und Marching Cubes
#: braucht ringsherum eine Lage, in der das Feld eindeutig außen ist.
MARGIN_CELLS: Final = 3.0

#: Um wie viel Zelle das Raster gegenüber den Körpern versetzt liegt.
#:
#: Kein Beiwerk: Ein achsparalleler Quader mit runden Maßen legt seine Flächen
#: sonst genau auf die Rasterpunkte. Dort ist das Abstandsfeld exakt null,
#: Marching Cubes findet keinen Vorzeichenwechsel und spannt entartete
#: Dreiecke auf — gemessen an einem 40x30x20-Quader: 793 Bruchstücke statt
#: eines Körpers, und drei Prozent zu viel Volumen. Der Wert ist mit Absicht
#: kein einfacher Bruch; eine halbe Zelle träfe bei halben Maßen wieder.
GRID_OFFSET: Final = 0.37

#: Wie viel gröber das Raster im Entwurf ist. Anders als bei den
#: Vernetzungsoperationen ist die Rasterweite hier keine Zusage über das
#: Ergebnis, sondern der Preis für seine Genauigkeit — und im Entwurf wird
#: iteriert, nicht abgenommen.
DRAFT_FACTOR: Final = 2.0

#: Bis zu wie vielen Rasterpunkten der Entwurf fein rechnet (RM-379). Gröber
#: wurde vorher immer, und die Figur im Fenster wich bis 2 mm vom Export ab,
#: ohne dass jemand es sagte. Gemessen am Leistungsfall aus §31 (zwei
#: gekreuzte Rohre Ø 20, Übergang 6, Raster 1 mm): rund 243 000 Punkte in
#: 1,5 s — eine Wartezeit, die beim Formen noch trägt. Darüber greift der
#: Entwurfsfaktor, und der Befund ``blend.draft`` sagt es.
DRAFT_SAMPLES: Final = 250_000

#: Ab wie vielen Dreiecken beider Eingänge die Oberfläche im Budget mitzählt
#: (RM-427). Die Abstandsfelder kosten nicht nur je Rasterpunkt, sondern mit
#: der Oberfläche: gemessen (Review 02.10., ``v5g_rm379_schwer``) bei 241 200
#: Punkten an 81 920 Dreiecken 0,75 s, bei 244 800 Punkten an 327 680
#: Dreiecken 3,8 s — gegen 0,9 s mit dem Entwurfsfaktor. Bis hierher zählen
#: nur die Rasterpunkte; darüber wiegt jeder Punkt so viel mehr, wie die
#: Oberfläche größer ist.
DRAFT_SURFACE: Final = 100_000

#: Wie viele Rasterpunkte auf einmal gegen den Baum gefragt werden. Groß genug,
#: dass der Aufruf über alle Kerne sich lohnt — jeder startet seine Fäden neu,
#: und in Portionen zu 32 768 Punkten kostete das Starten an zwei gekreuzten
#: Rohren mehr als die Suche —, klein genug für einen Abbruch in einem
#: Sekundenbruchteil (§15.6).
FIELD_CHUNK: Final = 400_000

#: Wie viele Rasterpunkte auf einmal gegen ihre Bewerber gerechnet werden: Die
#: Paare aus Punkt und Dreieck einer Portion belegen so einige zehn Megabyte.
PAIR_CHUNK: Final = 32_768

#: Auf wie vielen Fäden die Paare einer Portion rechnen. NumPy gibt den
#: Interpreter-Lock in den Feldern frei; mehr Fäden hießen mehr gleichzeitige
#: Zwischenfelder, nicht mehr Tempo (wie ``orient.PROJECTION_WORKERS``).
PAIR_WORKERS: Final = 4

#: Wie viele der nächsten Stützpunkte ihr Dreieck als Bewerber stellen. Der
#: nächste Punkt der Oberfläche liegt auf einem Dreieck, dessen Stützpunkte
#: höchstens eine Rasterweite von ihm entfernt sind; unter den acht nächsten
#: ist eines davon (geprüft gegen :func:`app.core.geom.mesh.on_surface` in
#: ``test_blend.py``).
NEAREST_SAMPLES: Final = 8

#: Bis zu welcher Länge, in Rasterweiten, eine Kante aus Marching Cubes eine
#: Nadel ist und zusammengelegt wird (RM-671).
#:
#: Läuft die Fläche dicht an einem Rasterpunkt vorbei, legt Marching Cubes auf
#: jede Rasterkante daneben eine Ecke: ein Büschel dicht beieinander, mit den
#: fernen Ecken über Dreiecke von wenigen Grad verbunden. Gemessen an Kugel auf
#: Zylinder (Raster 1): 11,6 der 11,8 % Splitter sind solche Nadeln, ihre
#: kürzeste Kante im Median 0,07 Raster. Bis v0.4.2 gab es sie kaum, weil das
#: Feld zum nächsten Stützpunkt maß und nahe der Fläche nie null wurde (0,014
#: statt 0,245 % der Rasterpunkte unter 0,05 mm) — um den Preis welliger Wände.
#: Unter 0,2 Raster zusammengelegt bleiben 1,3 % Splitter, und die Fläche wandert
#: dabei höchstens 0,09 Raster; 0,1 ließe 5,3 %, 0,3 wandert 0,11.
NEEDLE: Final = 0.2

#: Wie nah an null ein Rasterwert liegen darf, in Rasterweiten; was näher liegt,
#: gilt als knapp außen (RM-671).
#:
#: Ein Wert nahe null legt die Ecke aus Marching Cubes auf den Rasterpunkt, und
#: zwar für jede Kante dort — in einfacher Genauigkeit auf denselben Ort. Das
#: Verschweißen kneift die Fläche dann zu Kanten mit vier oder sechs Dreiecken.
#: Gemessen an der Grundfigur aus Rumpf, Kopf und Armen: im zweiten Schritt elf
#: Werte unter 1e-9, das Netz danach offen. Ein Tausendstel Raster löst jede
#: solche Ecke vom Rasterpunkt und verschiebt die Fläche höchstens so weit nach
#: innen — nie unter das Bett, und unter ``PRINT_LIMIT`` bis zu einem Raster
#: von 2,5 mm.
CLEAR_OF_ZERO: Final = 1e-3


@dataclasses.dataclass(frozen=True)
class _Surface:
    """Ein Eingang, wie das Abstandsfeld ihn befragt — einmal gebaut je Verschmelzung.

    Je Dreieck die Ecken, die Einheitsnormale (null ohne Fläche) und je Seite
    ``k`` (Ecke ``k`` nach ``k + 1``) das Kreuzprodukt aus Normale und Seite, das ins
    Dreieck zeigt. Je Kante ihre Ecken (kleinere Nummer zuerst), der Weg von
    der ersten zur zweiten und die Summe der Normalen ihrer Dreiecke; je Ecke
    die winkelgewichtete Normale. Dazu die Stützpunkte zum Suchen: die Mitten
    der auf die Rasterweite geteilten Dreiecke, je mit ihrem Dreieck.
    """

    vertices: np.ndarray
    corners: np.ndarray
    normals: np.ndarray
    flat: np.ndarray
    inward: np.ndarray
    sides: np.ndarray
    ends: np.ndarray
    spans: np.ndarray
    scales: np.ndarray
    side_normals: np.ndarray
    corner_normals: np.ndarray
    owners: np.ndarray
    tree: Any

    @classmethod
    def of(cls, mesh: MeshData, spacing: float) -> _Surface:
        """Baut die Befragung; die Stützpunkte liegen dichter als das Raster.

        Deterministisch geteilt, nicht zufällig abgetastet: Ein Startwert wäre
        hier eine Streuzahl in einer Operation, die ohne auskommt (Regel 9).
        """
        raw = mesh.raw
        vertices = np.asarray(raw.vertices, dtype=np.float64)
        faces = np.asarray(raw.faces, dtype=np.int64)
        corners = vertices[faces]
        normals, areas = stable_normals(raw)
        inward = np.cross(normals[:, None, :], np.roll(corners, -1, axis=1) - corners)
        directed = np.stack((faces.reshape(-1), np.roll(faces, -1, axis=1).reshape(-1)), axis=1)
        ends, inverse = unique_edges(directed, return_inverse=True)
        sides = inverse.reshape(-1, 3)
        spans = vertices[ends[:, 1]] - vertices[ends[:, 0]]
        squared = row_dots(spans, spans)
        scales = np.zeros(len(ends), dtype=np.float64)
        np.divide(1.0, squared, out=scales, where=squared > 0.0)
        side_normals = np.zeros((len(ends), 3), dtype=np.float64)
        np.add.at(side_normals, sides.reshape(-1), np.repeat(normals, 3, axis=0))
        dense, pieces, owners = trimesh.remesh.subdivide_to_size(
            vertices, faces, max_edge=spacing, return_index=True
        )
        piece_corners = np.asarray(dense, dtype=np.float64)[np.asarray(pieces, dtype=np.int64)]
        samples = (piece_corners[:, 0] + piece_corners[:, 1] + piece_corners[:, 2]) / 3.0
        return cls(
            vertices=vertices,
            corners=corners,
            normals=normals,
            flat=np.asarray(areas > 0.0),
            inward=inward,
            sides=sides,
            ends=ends,
            spans=spans,
            scales=scales,
            side_normals=side_normals,
            corner_normals=stable_vertex_normals(raw),
            owners=np.asarray(owners, dtype=np.int64),
            tree=cKDTree(samples),
        )

    def signed(self, points: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        """Der Abstand je Punkt zum nächsten seiner Bewerber, positiv innen.

        ``candidates`` nennt je Punkt Dreiecke, auch doppelt; jedes wird einmal
        gerechnet. Gewinnt der kleinste Abstand, bei Gleichstand das Dreieck
        mit der kleineren Nummer — am Ergebnis ändert das nichts, denn zwei
        Dreiecke, die denselben nächsten Punkt teilen, rechnen ihn über
        dieselbe Kante oder Ecke in derselben Folge.
        """
        ordered = np.sort(candidates, axis=1)
        fresh = np.ones(ordered.shape, dtype=bool)
        fresh[:, 1:] = ordered[:, 1:] != ordered[:, :-1]
        rows, columns = np.nonzero(fresh)
        squared, inside = self._to_triangles(points[rows], ordered[rows, columns])
        starts = np.flatnonzero(np.concatenate(([True], rows[1:] != rows[:-1])))
        best = np.minimum.reduceat(squared, starts)
        place = np.where(squared == best[rows], np.arange(len(squared)), len(squared))
        winner = np.minimum.reduceat(place, starts)
        distance = np.sqrt(best)
        return np.asarray(np.where(inside[winner], distance, -distance))

    def _to_triangles(self, points: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Quadrierter Abstand je Punkt zu seinem Dreieck, und ob der Punkt innen liegt.

        Fällt der Punkt senkrecht ins Dreieck, ist es der Abstand zur Ebene, und
        das Vorzeichen sagt die Flächennormale. Sonst liegt der nächste Punkt
        auf einer Seite: gerechnet je Kante von ihrer kleineren Eckennummer aus,
        damit beide Nachbardreiecke dieselben Bits liefern, und das Vorzeichen
        sagt die Normale dessen, was getroffen ist — die Summe beider
        Flächennormalen an einer Kante, die winkelgewichtete an einer Ecke.
        Diese Pseudonormalen ordnen jeden Punkt eines geschlossenen Netzes
        richtig zu (Bærentzen und Aanæs, 2005); eine Flächennormale allein
        kippt neben einer Kante, und eine gemittelte Eckennormale stand an der
        Deckkante eines Zylinders 45 Grad schräg und ließ ihn acht Millimeter
        ins Leere wachsen.

        Nur Grundrechenarten, Kreuzprodukt und Wurzel (``kern.md``): Auf jeder
        Maschine dieselben Bits.
        """
        corners = self.corners[faces]
        from_first = points - corners[:, 0]
        plane = row_dots(from_first, self.normals[faces])
        within = self.flat[faces].copy()
        within &= row_dots(from_first, self.inward[faces, 0]) >= 0.0
        within &= row_dots(points - corners[:, 1], self.inward[faces, 1]) >= 0.0
        within &= row_dots(points - corners[:, 2], self.inward[faces, 2]) >= 0.0
        nearest = np.full(len(points), np.inf)
        facing = np.zeros(len(points))
        for side in range(3):
            edge = self.sides[faces, side]
            first = self.ends[edge, 0]
            second = self.ends[edge, 1]
            span = self.spans[edge]
            start = self.vertices[first]
            along = np.clip(row_dots(points - start, span) * self.scales[edge], 0.0, 1.0)
            spot = start + along[:, None] * span
            at_end = along >= 1.0
            spot[at_end] = self.vertices[second[at_end]]
            offset = points - spot
            squared = row_dots(offset, offset)
            normal = np.where(
                (along <= 0.0)[:, None],
                self.corner_normals[first],
                np.where(at_end[:, None], self.corner_normals[second], self.side_normals[edge]),
            )
            closer = squared < nearest
            nearest = np.where(closer, squared, nearest)
            facing = np.where(closer, row_dots(offset, normal), facing)
        squared = np.where(within, plane * plane, nearest)
        facing = np.where(within, plane, facing)
        return np.asarray(squared), np.asarray(facing < 0.0)


def distance_field(
    mesh: MeshData,
    grid: np.ndarray,
    spacing: float,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> np.ndarray:
    """Abstand zur Oberfläche für jeden Rasterpunkt: positiv innen, negativ außen.

    **Zum nächsten Punkt auf dem Dreieck, nicht zu seiner Ebene** (RM-671).
    Von v0.4.4 bis v0.5.3 maß das Feld zur Ebene des nächsten Stützpunkts.
    An einer ebenen Wand ist das exakt — der Anlass, davor maß es zum
    Stützpunkt selbst, und vor einer Wand fiel der Weg wellig mit der Periode
    der Wolke aus (Befund Robert, 18.09.2026: 67 koplanare Streifen in einer
    Wand). Neben einer Kante unterschätzt die Ebene aber und springt, wo der
    nächste Stützpunkt vom Deckel auf den Mantel wechselt: an einem Zylinder
    Ø 20 bis 1,9 mm Fehler in vier Millimetern Abstand. Der Abstand zum
    Dreieck ist an der Wand ebenso exakt und überall stetig. Die Splitter des
    Verfahrens kamen nicht von dem Sprung — mit dem exakten Feld sind es
    gleich viele —, sondern aus Marching Cubes selbst (:data:`NEEDLE`).
    Bewerber sind die Dreiecke der :data:`NEAREST_SAMPLES` nächsten
    Stützpunkte; gerechnet wird je Paar in :meth:`_Surface.signed`.

    **Das Vorzeichen kommt aus der Normale, nicht aus einem Strahl** und
    nicht aus einem Belegungsgitter: ``Trimesh.contains`` lief über
    ``rtree``, das nicht mehr im Prozess ist, und ``voxelized().fill()`` misst
    ab Zellmitte, an einer Kugel mit 25 mm Radius acht Prozent zu viel Volumen.

    **In Portionen, damit ein Abbruch ankommt** (§15.6): Ein einziger
    ``query`` über zehn Millionen Rasterpunkte ist ein nativer Aufruf und
    kooperativ nicht zu unterbrechen. ``workers=-1`` lastet die Kerne
    innerhalb einer Portion aus, bei identischem Ergebnis; die Paare einer
    Portion rechnen auf bis zu :data:`PAIR_WORKERS` Fäden, jede Teilportion in
    ihren eigenen Abschnitt des Felds — Element für Element dieselbe Rechnung,
    auf welchem Faden sie läuft.
    """
    surface = _Surface.of(mesh, spacing)
    count = min(NEAREST_SAMPLES, len(surface.owners))
    field = np.empty(len(grid), dtype=float)
    workers = max(1, min(PAIR_WORKERS, os.cpu_count() or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(grid), FIELD_CHUNK):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            block = np.asarray(grid[start : start + FIELD_CHUNK], dtype=np.float64)
            _away, near = surface.tree.query(block, k=count, workers=-1)
            candidates = surface.owners[np.asarray(near, dtype=np.int64).reshape(len(block), count)]
            part = functools.partial(
                _signed_part,
                surface,
                field[start : start + len(block)],
                block,
                candidates,
                cancelled,
            )
            list(pool.map(part, range(0, len(block), PAIR_CHUNK)))
            if progress is not None:
                done = min(start + FIELD_CHUNK, len(grid)) / max(len(grid), 1)
                progress(done, str(_("Abstandsfeld rechnen")))
    return field


def _signed_part(
    surface: _Surface,
    into: np.ndarray,
    block: np.ndarray,
    candidates: np.ndarray,
    cancelled: CancelToken | None,
    first: int,
) -> None:
    """Eine Teilportion von :func:`distance_field` — schreibt nur ihren eigenen Abschnitt."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    last = first + PAIR_CHUNK
    into[first:last] = surface.signed(block[first:last], candidates[first:last])


def _share(progress: ProgressFn | None, offset: float) -> ProgressFn | None:
    """Die zweite Hälfte des Balkens für den zweiten Körper.

    Zwei Abstandsfelder, ein Fortschritt: Ohne die Verschiebung liefe der
    Balken zweimal von null bis eins, und das liest sich wie ein Neustart.
    """
    if progress is None:
        return None
    return lambda fraction, text: progress(offset + fraction / 2.0, text)


def _smooth_maximum(first: np.ndarray, second: np.ndarray, radius: float) -> np.ndarray:
    """Die weiche Vereinigung zweier Felder — innen ist positiv, also Maximum.

    Ohne Radius das gewöhnliche Maximum, und damit die gewöhnliche
    Vereinigung. Mit Radius wird zwischen beiden Feldern über eine Breite von
    ``radius`` überblendet und das Ergebnis in der Mitte um ``radius/4``
    angehoben; genau dort, wo beide Flächen sich treffen, wächst deshalb
    Material nach.
    """
    if radius <= 0.0:
        return np.asarray(np.maximum(first, second), dtype=float)
    share = np.clip(0.5 + 0.5 * (first - second) / radius, 0.0, 1.0)
    blended = second * (1.0 - share) + first * share
    return np.asarray(blended + radius * share * (1.0 - share), dtype=float)


def _inside_the_hull(points: np.ndarray, first: MeshData, second: MeshData) -> np.ndarray:
    """Abstand zur Hülle beider Eingänge, positiv innen — exakt an jeder Seite des Quaders.

    **Das Ergebnis endet an der Hülle der Eingänge** (F5, RM-671; Entscheidung
    Koordinator, 10.10.2026). Wo beide Felder gleich sind, hebt
    :func:`_smooth_maximum` das Feld um bis zu ein Viertel des Übergangs. An
    Flächen, die bei beiden Körpern bündig liegen — beide Böden auf dem Bett,
    beide Deckel, beide Seiten —, wuchs das Ergebnis so über die Eingänge
    hinaus: an zwei versetzten Quadern 40 x 30 x 10 bis 1,69 mm unter das
    Bett und 16 575,6 statt 14 400 mm³, obwohl sie keine Kehle haben. Eine Kehle
    liegt immer innerhalb der Hülle, also schneidet die Hülle nur die Beulen.
    """
    low = np.minimum(first.raw.bounds[0], second.raw.bounds[0])
    high = np.maximum(first.raw.bounds[1], second.raw.bounds[1])
    return np.asarray(np.minimum((points - low).min(axis=1), (high - points).min(axis=1)))


def _in_double(field: np.ndarray, found: np.ndarray) -> np.ndarray:
    """Die Ecken aus Marching Cubes in doppelter Genauigkeit, in Rasterschritten.

    ``skimage`` rechnet die Lage auf der Rasterkante in einfacher Genauigkeit
    und gibt ``float32`` zurück — eine Ecke trug so je nach Rasterlage bis zu
    einige Mikrometer Rundung, und ein Unterschied in der letzten Stelle des
    Felds kam nie an (Regel 6). Je Ecke ist eine Koordinate gebrochen, die
    beiden anderen sind ganze Rasterindizes: Die Kante ist damit bekannt, und
    die Lage darauf folgt aus den beiden Feldwerten wie in Marching Cubes,
    ``t = f0 / (f0 - f1)``. Fällt eine Ecke auf einen Rasterpunkt, bleibt sie dort.
    """
    index = np.asarray(found, dtype=np.float64)
    base = np.floor(index)
    fraction = index - base
    rows = np.arange(len(index))
    axis = np.argmax(fraction, axis=1)
    on_point = fraction[rows, axis] <= 0.0
    low = base.astype(np.int64)
    high = low.copy()
    high[rows, axis] += 1
    high = np.minimum(high, np.asarray(field.shape, dtype=np.int64) - 1)
    near = field[low[:, 0], low[:, 1], low[:, 2]]
    far = field[high[:, 0], high[:, 1], high[:, 2]]
    usable = ~on_point & (np.abs(near - far) > 0.0)
    share = np.zeros(len(index), dtype=np.float64)
    np.divide(near, near - far, out=share, where=usable)
    exact = base.copy()
    exact[rows, axis] += share
    return exact


def _without_needles(
    body: trimesh.Trimesh, grid: float, cancelled: CancelToken | None
) -> trimesh.Trimesh:
    """Legt die Nadeln aus Marching Cubes zusammen (:data:`NEEDLE`).

    Eine Ecke geht dabei in einer anderen auf, die schon auf der Fläche des
    Rasterverfahrens liegt; neue Koordinaten entstehen keine, und kein Dreieck
    klappt um (:func:`app.core.geom.mesh_edits.collapse_short`). Aktiv sind
    nur die Dreiecke um die kurzen Kanten (:func:`~app.core.geom.mesh_edits.around`).
    Ein Netz, das die Halbkanten dort nicht tragen (verzweigt oder falsch
    gewickelt), bleibt, wie es ist.
    """
    vertices = np.asarray(body.vertices, dtype=np.float64)
    faces = np.asarray(body.faces, dtype=np.int64)
    corners = vertices[faces]
    sides = np.roll(corners, -1, axis=1) - corners
    shortest = NEEDLE * grid
    wanted = (row_dots(sides, sides) < shortest * shortest).any(axis=1)
    if not wanted.any():
        return body
    surface = mesh_edits.surface_of(vertices, faces, mesh_edits.around(faces, wanted))
    if surface is None or not mesh_edits.collapse_short(surface, shortest, cancelled=cancelled):
        return body
    vertices, faces = surface.arrays()
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _too_fine(wanted: int, grid: float) -> ValidationError:
    """Sagt, welche Rasterweite noch ginge.

    Die Zahl kennt nur die Operation: Halbieren der Weite verachtfacht die
    Rasterpunkte, also lässt sich die erreichbare Weite ausrechnen. Aufgerundet
    auf zwei Stellen, damit der Vorschlag nicht die Zahl nennt, die er gerade
    abgelehnt hat.
    """
    reachable = math.ceil(grid * (wanted / MAX_SAMPLES) ** (1.0 / 3.0) * 100.0) / 100.0
    return ValidationError(
        field="grid",
        detail=_("Diese Rasterweite ergäbe mehr Punkte, als sich noch rechnen lassen."),
        value=grid,
        constraint="maximum",
        values={"samples": wanted, "limit": MAX_SAMPLES, "reachable": reachable},
        suggestions=(
            Action(id="use_reachable", label=_("Die feinste Rasterweite nehmen, die noch geht.")),
            Action(id="smaller_bodies", label=_("Die Körper einzeln verschmelzen.")),
        ),
    )


def _grid(
    first: MeshData, second: MeshData, radius: float, grid: float
) -> tuple[np.ndarray, tuple[int, ...]]:
    """Prüft die Eingänge vor Ursprung und Punktzahl je Achse des gemeinsamen Rasters."""
    for source in (first, second):
        if not source.raw.is_watertight or source.volume <= 0.0:
            raise NotManifoldError(
                detail=_(
                    "Dieser Körper umschließt kein Volumen — ohne ein Innen gibt es kein "
                    "Abstandsfeld und keinen weichen Übergang. Erst reparieren, dann noch "
                    "einmal."
                ),
                open_edges=int(len(source.raw.edges_unique) * 2 - len(source.raw.faces) * 3),
            )

    margin = radius + grid * MARGIN_CELLS
    low = np.minimum(first.raw.bounds[0], second.raw.bounds[0]) - margin + grid * GRID_OFFSET
    high = np.maximum(first.raw.bounds[1], second.raw.bounds[1]) + margin
    return low, tuple(math.ceil(value) + 1 for value in (high - low) / grid)


def draft_grid(first: MeshData, second: MeshData, radius: float, grid: float) -> float:
    """Die Rasterweite für den Entwurf: die feine, solange sie im Budget bleibt.

    Gröber nur, wo die feine Weite :data:`DRAFT_SAMPLES` übersteigt (RM-379),
    die Punkte gewogen mit der Oberfläche über :data:`DRAFT_SURFACE` (RM-427).
    Dieselbe Regel gilt für jede Operation mit Entwurfsfaktor; heute hat ihn
    nur diese — Kegel und Ring rechnen im Entwurf so fein wie beim Export.
    """
    _low, shape = _grid(first, second, radius, grid)
    surface = first.triangle_count + second.triangle_count
    weight = max(1.0, surface / DRAFT_SURFACE)
    if int(np.prod(shape)) * weight <= DRAFT_SAMPLES:
        return grid
    return grid * DRAFT_FACTOR


def blend_bodies(
    first: MeshData,
    second: MeshData,
    radius: float,
    grid: float,
    *,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> MeshData:
    """Beide Körper über ein gemeinsames Abstandsfeld weich vereinigen.

    ``progress`` und ``cancelled`` reichen bis in die Feldrechnung hinein und
    nicht nur bis vor sie: Dort liegt die Zeit, und ein Abbruch, der erst
    danach greift, ist keiner (§15.6).
    """
    low, shape = _grid(first, second, radius, grid)
    margin = radius + grid * MARGIN_CELLS
    wanted = int(np.prod(shape))
    if wanted > MAX_SAMPLES:
        raise _too_fine(wanted, grid)

    axes = [low[axis] + np.arange(shape[axis]) * grid for axis in range(3)]
    points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)

    merged = _smooth_maximum(
        distance_field(first, points, grid, progress=_share(progress, 0.0), cancelled=cancelled),
        distance_field(second, points, grid, progress=_share(progress, 0.5), cancelled=cancelled),
        radius,
    )
    merged = np.minimum(merged, _inside_the_hull(points, first, second))
    clear = CLEAR_OF_ZERO * grid
    merged = np.where(np.abs(merged) < clear, -clear, merged)
    if cancelled is not None:
        cancelled.raise_if_cancelled()

    # **Der Rand muss zu sein**, wie beim Gitter (`lattice.py`): Marching Cubes
    # zeichnet nur, wo das Feld sein Vorzeichen wechselt. Endet die Fläche am
    # Rand des Rasters, ist das Ergebnis offen — und ein offenes Netz fällt in
    # jeder folgenden booleschen Operation bis auf die Voxelstufe durch.
    field = np.pad(merged.reshape(shape), 1, constant_values=-(margin + grid))
    from skimage import measure

    found, faces, _normals, _values = measure.marching_cubes(field, 0.0)
    # Die Polsterung verschiebt den Ursprung um einen Schritt je Achse zurück.
    vertices = low + (_in_double(field, found) - 1.0) * grid
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    body.fix_normals()
    body = _without_needles(body, grid, cancelled)
    _log.info(
        "blended %d and %d triangles into %d over %d samples",
        first.triangle_count,
        second.triangle_count,
        len(body.faces),
        wanted,
    )
    return first.replacing(body)


# --- operation --------------------------------------------------------------------


@op_params
class BlendParams(BaseParams):
    radius: float = param(
        title=_("Übergang"),
        default=3.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        doc=_(
            "Wie breit die Kehle zwischen beiden Körpern zuwächst. Null gibt die "
            "gewöhnliche Vereinigung. Einen Spalt überbrückt er ab etwa dem Dreifachen "
            "seiner Breite."
        ),
        zero_text=ZERO_NONE,
    )
    grid: float = param(
        title=_("Rasterweite"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=10.0,
        doc=_(
            "Wie fein gerechnet wird. Kleiner heißt genauer und deutlich langsamer — "
            "Kanten unter dieser Weite gehen verloren."
        ),
    )


@register_op(
    name="blend_union",
    result_kind="mesh",
    # Das Abstandsfeld misst seit dem 18.09.2026 zur Ebene des nächsten
    # Dreiecks statt zu seiner Mitte (siehe :func:`distance_field`). Ein
    # Ergebnis aus dem Cache trüge sonst weiter die gewellten Wände. 3 seit dem
    # 22.09.2026: Die Filamente beider Körper kommen mit (:func:`_with_filaments`).
    # 4: Auch die Entwurfsplanung prüft die Eingänge vor Bounds und Punktbudget.
    # 6: Das Feld misst zum nächsten Punkt auf dem Dreieck, das Ergebnis endet an
    # der Hülle der Eingänge, und die Ecken stehen in doppelter Genauigkeit (RM-671).
    cache_version="6",
    title=_("Weich verschmelzen"),
    category="boolean",
    params=BlendParams,
    consumes=2,
    produces=1,
    keeps_inputs=1,
    doc=_(
        "Vereinigt zwei Körper mit einem fließenden Übergang statt einer scharfen Kehle. "
        "Für Griffe, Verstrebungen und alles, was gedruckt nicht an der Innenecke reißen soll."
    ),
    caveat=_(
        "An Teilen, deren Maße zählen, denn scharfe Kanten werden auf dem Raster weicher. Für "
        "eine Passung normal vereinigen."
    ),
)
def blend_union(ctx: OpContext) -> OpResult:
    """Zwei Körper hinein, einer heraus — mit einem Wulst in der Naht."""
    params = cast(BlendParams, ctx.params)
    first, second = (as_mesh_data(entry.mesh) for entry in ctx.inputs[:2])
    grid = (
        draft_grid(first, second, params.radius, params.grid)
        if ctx.quality == "draft"
        else params.grid
    )

    merged = blend_bodies(
        first,
        second,
        params.radius,
        grid,
        progress=ctx.progress,
        cancelled=ctx.cancelled,
    )
    merged = _with_filaments(merged, first, second, params.radius + grid)

    findings = [
        Finding(
            code="blend.rastered",
            severity="info",
            message=_(
                "Der Übergang wurde auf einem Raster gerechnet — Kanten, die feiner "
                "sind als das Raster, sind dabei weicher geworden."
            ),
            object_id=ctx.inputs[0].id,
            values={"grid_mm": round(grid, 3), "radius_mm": round(params.radius, 3)},
        )
    ]
    if grid > params.grid:
        findings.append(
            Finding(
                code="blend.draft",
                severity="info",
                message=_(
                    "Im Fenster rechnet der Übergang in Entwurfsauflösung, damit das Formen "
                    "flüssig bleibt. Export und Druckvorbereitung rechnen fein."
                ),
                object_id=ctx.inputs[0].id,
                values={"grid_mm": round(grid, 3)},
            )
        )
    if merged.component_count > 1:
        findings.append(
            Finding(
                code="blend.still_apart",
                severity="warning",
                message=_(
                    "Die Körper liegen weiter auseinander, als der Übergang breit ist, und "
                    "bleiben unverbunden."
                ),
                object_id=ctx.inputs[0].id,
                values={"components": merged.component_count},
                # Regel 17: Die Breite des Übergangs steht im Schritt.
                suggestions=(CORRECT_INPUT,),
            )
        )
    from app.core.geom.ops import _material_slots_after_boolean

    return OpResult(
        outputs=[
            dataclasses.replace(
                ctx.inputs[0],
                mesh=merged,
                features={},
                material_slots=_material_slots_after_boolean(ctx, "union", merged),
            )
        ],
        findings=findings,
    )


def _with_filaments(merged: MeshData, first: MeshData, second: MeshData, reach: float) -> MeshData:
    """Die Filamente beider Körper auf die neue Oberfläche übertragen (§20).

    Das Rasterverfahren baut eine ganz neue Oberfläche, und
    :meth:`MeshData.replacing` lässt eine Slotliste fallen, die nicht mehr zur
    Dreieckszahl passt — bis zum 22.09.2026 kam jedes verschmolzene Teil
    einfarbig in Slot 0 heraus. Dieselbe Pflicht wie nach der Voxelstufe der
    Rückfallkette: Wer neu vernetzt, überträgt die Slots neu
    (``attributes.transfer``).

    ``reach`` ist, wie weit ein Dreieck von einer alten Oberfläche liegen darf
    und ihr Filament noch bekommt: Die Kehle wächst um bis zu ``radius`` aus
    der Naht, das Raster verschiebt jede Wand um bis zu eine Weite. Was
    weiter liegt, bekommt das häufigste Filament des ersten Körpers — er ist
    der, dessen Name und Material bleiben.
    """
    from app.core.geom.attributes import counts, transfer

    if not first.slots and not second.slots:
        return merged
    usual = counts(first)
    fallback = max(usual, key=lambda slot: (usual[slot], -slot))
    return transfer(merged, [first, second], cut_slot=fallback, tolerance=reach)
