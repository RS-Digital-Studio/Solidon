"""Der Deckel einer gekrümmten Mündung: die Fläche um den Rand, über das Loch fortgesetzt.

Wer einen Hohlraum füllt — beim Versetzen, Kippen und Entfernen einer Bohrung
—, schließt ihn an seiner Mündung mit einem Deckel. Liegt der Rand in einer
Ebene, ist das ein ebener Fächer. Liegt er in einer gekrümmten Fläche, war es
bis zur Durchsicht 0.5.1 ein Fächer vom Mittelpunkt des Rands (RM-248), und der
liegt auf der mittleren Höhe des Rands statt auf der Fläche: Unter einer
Zylindersenkung Ø 10 in einer Unterseite, die ein Zylinder R 40 ist, blieb beim
Versetzen eine Mulde von 4,9 mm³ am Netz und 4,0 mm³ am exakten Körper; in der
Hohlkehle des Gartenschlauchhalters stand derselbe Fächer umgekehrt als Beule
von 26 mm³ über der Fläche, weil die Fläche dort nach innen gewölbt ist.

**Die Fläche wird gemessen, nicht geschätzt** (:func:`mouth_surface`): Die
Ausgleichsebene des Rands gibt den Rahmen, und die Fläche außerhalb des Rands
— bis :data:`MOUTH_REACH` seines Radius weit — wird als Höhenfeld über ihr
abgetastet, und zwar an den Facetten selbst, auf einem Raster: Ein Netz aus
langen Streifen trägt im Ring um das Loch kaum eine Ecke, aber überall eine
Facette. Darauf wird ein Polynom dritten Grades eingepasst
(:data:`MOUTH_DEGREE`), in Grundrechenarten (``math.fsum`` und Gauß mit
Spaltenpivot, RM-187): Seine Höhe entscheidet über jede Ecke des Deckels.
Die Facetten und nicht die Ecken, weil der Deckel bündig mit dem Netz liegen
muss, das um ihn herum steht — eine glatte Fläche durch die Ecken läge an einem
Zylinder R 40 mit Streifen von 4 mm um zwei Drittel ihres Durchhangs über den
Facetten.

**Und wo keine glatte Fläche ist, gibt es keinen fortgesetzten Deckel.** Weicht
das Polynom im Mittel oder am Rand um mehr als ``units.MAX_FACET_SAG`` von der
Fläche ab, beschreibt es sie nicht, und die Funktion gibt ``None``: Der
Aufrufer bleibt beim Fächer. Das ist die Mündung mit eigener Rundung an der
Lochplatte ``pegboard-gs-100-v2`` (Rundung R ≈ 1 mm um die Zylindersenkung,
gemessen 0,21 mm im Mittel): Die Rundung gehört nicht zur Kette, bleibt beim
Versetzen stehen, und eine Fläche, die sie fortsetzte, liefe als Kuppe oder
Trichter ins Loch. Ebenso ein Rand, um den die Fläche nicht ringsum steht.

Der Netzkern baut daraus ein Gitter (:func:`cap_grid`), der exakte eine
Füllung mit Stützpunkten auf dem Polynom (:func:`support_points`), wo der Rand
nicht auf einer einzigen Fläche liegt, deren Träger unter dem Loch weiterläuft
(``brep.edit.solid_from_faces``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from app.core import units
from app.core.geom import transform
from app.core.geom.mesh import MeshData

#: Wie weit um den Rand die Fläche abgetastet wird — als Anteil seines Radius.
#: Ein halber Radius hält die Anpassung örtlich: Am Zylinder R 40 unter einer
#: Senkung Ø 10 wich eine Quadrik dort im Mittel 2,6 µm von den Facetten ab,
#: über einen ganzen Radius 4,7 µm.
MOUTH_REACH: Final = 0.5

#: Rasterpunkte und Deckelringe je Radius. Zwölf geben am Rand Ø 10 Proben im
#: Abstand von 0,4 mm und einen Deckel aus rund 400 Punkten.
MOUTH_GRID: Final = 12

#: Ab welchem Anteil seiner Normalen entlang der Achse des Rands ein Dreieck zur
#: Fläche um die Mündung zählt: steiler als 60° ist es eine Wand — die einer
#: benachbarten Bohrung oder einer Stufe —, und die liegt nicht in der Fläche.
SURFACE_FACING: Final = 0.5

#: In wie vielen Richtungen um den Rand die Fläche stehen muss — in jedem Achtel
#: (:func:`_octants`). Eine Anpassung, die auf einer Seite keine Probe hat,
#: setzt die Fläche dort fort, wo es keine gibt — an einer Mündung über der
#: Kante eines Teils.
MOUTH_SECTORS: Final = 8

#: Bis zu welchem Grad das Polynom der Fläche reicht. Drei und nicht zwei: Die
#: Quadrik trifft einen Zylinder genau, aber keinen Übergang — an einer Platte,
#: deren Unterseite tangential von der Ebene in einen Zylinder R 40 übergeht,
#: lag sie am Rand einer Senkung Ø 10 bis 0,049 mm neben der Fläche, das
#: Polynom dritten Grades 0,011; am Gartenschlauchhalter 0,028 gegen 0,008.
MOUTH_DEGREE: Final = 3

#: Wie oft höchstens angepasst wird, bis die Proben feststehen, die zur Fläche
#: des Rands gehören. Nach einem Durchgang ohne Änderung ist Schluss; an der
#: Rinne R 40 mit der Kante im Ring war das der fünfte (572, 545, 534, 532,
#: 531 Proben). Wer danach noch tauscht, schwingt, und findet keine Fläche.
MOUTH_ROUNDS: Final = 16

#: Welcher Anteil der Proben im Ring auf der angepassten Fläche liegen muss —
#: bis auf die Facettengrenze. Darunter ist sie nicht die Fläche um den Rand.
MOUTH_SHARE: Final = 0.5

#: Wie viele Dreiecke die Vorauswahl je Durchgang prüft; begrenzt den Speicher
#: an großen Netzen (ein Dreieck sind neun Gleitkommazahlen).
_CHUNK: Final = 262_144


@dataclass(frozen=True, slots=True)
class MouthSurface:
    """Die Fläche um einen Mündungsrand als Höhe über seiner Ausgleichsebene.

    ``u``/``v`` zählen von ``middle`` aus, der Flächenmitte des Rands in der
    Ebene; ``w`` von ``origin`` aus entlang ``w_axis``. Das Polynom rechnet in
    ``u``/``v`` durch ``radius`` (Kondition). ``rim_*`` ist der geordnete Rand,
    ``rim_error`` seine Höhe über dem Polynom.
    """

    origin: NDArray[np.float64]
    u_axis: NDArray[np.float64]
    v_axis: NDArray[np.float64]
    w_axis: NDArray[np.float64]
    middle: tuple[float, float]
    radius: float
    coefficients: tuple[float, ...]
    rim_u: NDArray[np.float64]
    rim_v: NDArray[np.float64]
    rim_error: NDArray[np.float64]

    def heights(self, u: NDArray[np.float64], v: NDArray[np.float64]) -> NDArray[np.float64]:
        """Die Höhe der angepassten Fläche über (u, v), von ``middle`` aus gezählt."""
        return _fitted(
            self.coefficients,
            np.asarray(u, dtype=np.float64) / self.radius,
            np.asarray(v, dtype=np.float64) / self.radius,
        )

    def points(
        self, u: NDArray[np.float64], v: NDArray[np.float64], w: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """Punkte im Raum zu (u, v, w) — elementweise, auf jeder Maschine dieselben Bits."""
        first = np.asarray(u, dtype=np.float64) + self.middle[0]
        second = np.asarray(v, dtype=np.float64) + self.middle[1]
        height = np.asarray(w, dtype=np.float64)
        return np.asarray(
            self.origin[None, :]
            + first[:, None] * self.u_axis[None, :]
            + second[:, None] * self.v_axis[None, :]
            + height[:, None] * self.w_axis[None, :]
        )


def mouth_surface(
    mesh: MeshData, excluded: NDArray[np.int64], rim: NDArray[np.float64]
) -> MouthSurface | None:
    """Die Fläche um den geordneten Rand ``rim`` — oder ``None``, wo keine glatte ist.

    ``excluded`` sind die Dreiecke des Hohlraums: Sie liegen innerhalb des Rands
    und gehören nicht zur Fläche, die über ihm weiterläuft. ``None`` auch, wenn
    der Rand um seine Mitte nicht sternförmig ist — der Deckel entsteht aus
    verkleinerten Kopien des Rands.
    """
    ordered = np.asarray(rim, dtype=np.float64)
    if len(ordered) < 3:
        return None
    centre, normal, _spread = units.plane_fit(ordered.tolist())
    axes = units.plane_axes(normal)
    if axes is None:
        return None
    origin = np.asarray(centre, dtype=np.float64)
    u_axis, v_axis = (np.asarray(axis, dtype=np.float64) for axis in axes)
    w_axis = np.asarray(normal, dtype=np.float64)
    offsets = ordered - origin
    ru = transform.along(offsets, u_axis)
    rv = transform.along(offsets, v_axis)
    rw = transform.along(offsets, w_axis)
    middle = _area_middle(ru, rv)
    if middle is None:
        return None
    du, dv = ru - middle[0], rv - middle[1]
    turn = du * np.roll(dv, -1) - np.roll(du, -1) * dv
    if not (bool(np.all(turn > 0.0)) or bool(np.all(turn < 0.0))):
        return None
    radius = float(np.sqrt(du * du + dv * dv).max())
    if radius <= units.EPS_GEOM:
        return None
    step = radius / MOUTH_GRID
    outer = radius * (1.0 + MOUTH_REACH)
    count = math.ceil(outer / step)
    offsets_1d = np.arange(-count, count + 1, dtype=np.float64) * step
    grid_u = np.repeat(offsets_1d, len(offsets_1d))
    grid_v = np.tile(offsets_1d, len(offsets_1d))
    reach = np.sqrt(grid_u * grid_u + grid_v * grid_v)
    wanted = (reach <= outer) & ~_inside(du, dv, grid_u, grid_v)
    heights = _facet_heights(
        mesh,
        excluded,
        origin,
        (u_axis, v_axis, w_axis),
        middle,
        offsets_1d,
        outer,
    )
    found = wanted & np.isfinite(heights)
    su, sv, sw = grid_u[found], grid_v[found], heights[found]
    # **Die Fläche, in der der Rand liegt, und nicht jede im Ring** (Durchsicht
    # 0.5.1): Liegt eine Kante im Ring — an einer Rinne R 40 in der ebenen
    # Unterseite 1,3 mm neben dem Rand —, zog die Ebene dahinter das Polynom
    # über der ganzen Öffnung um 1 mm³ aus der Rinne. Was nach einer Anpassung
    # um mehr als die Facettengrenze neben ihr liegt, gehört zu einer anderen
    # Fläche und fällt heraus; angepasst wird neu, bis sich nichts mehr ändert.
    kept = np.ones(len(su), dtype=bool)
    coefficients: tuple[float, ...] | None = None
    for _round in range(MOUTH_ROUNDS):
        if (
            int(kept.sum()) < 3 * len(_terms(su[:1], sv[:1]))
            or len(np.unique(_octants(su[kept], sv[kept]))) < MOUTH_SECTORS
        ):
            return None
        coefficients = _polynomial(su[kept] / radius, sv[kept] / radius, sw[kept])
        if coefficients is None:
            return None
        residual = sw - _fitted(coefficients, su / radius, sv / radius)
        within = np.abs(residual) <= units.MAX_FACET_SAG
        if bool(np.array_equal(within, kept)):
            break
        kept = within
    else:
        # Wer nach allen Durchgängen noch Proben tauscht, findet keine Fläche.
        return None
    # Trägt die angepasste Fläche nicht wenigstens die Hälfte des Rings, steht
    # um den Rand keine Fläche, sondern mehrere — dann gibt es nichts fortzusetzen.
    if coefficients is None or int(kept.sum()) < MOUTH_SHARE * len(su):
        return None
    surface = MouthSurface(
        origin=origin,
        u_axis=u_axis,
        v_axis=v_axis,
        w_axis=w_axis,
        middle=middle,
        radius=radius,
        coefficients=coefficients,
        rim_u=du,
        rim_v=dv,
        rim_error=rw - _fitted(coefficients, du / radius, dv / radius),
    )
    if float(np.abs(surface.rim_error).max()) > units.MAX_FACET_SAG:
        return None
    return surface


def cap_grid(surface: MouthSurface) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Die inneren Punkte des Deckels und seine Dreiecke.

    Die Randpunkte tragen die Nummern ``0 … n-1`` in der Reihenfolge des Rands,
    die neuen folgen dahinter. Die Ringe sind verkleinerte Kopien des Rands, je
    Ring mit weniger Punkten, und liegen auf dem Polynom; den Unterschied des
    Rands zu ihm (höchstens ``MAX_FACET_SAG``) nimmt das äußerste Band auf. Die
    Dreiecke laufen in der Richtung des Rands; der Aufrufer dreht sie, wo sein
    Ausschnitt andersherum gewickelt ist.
    """
    rim_count = len(surface.rim_u)
    points: list[NDArray[np.float64]] = []
    triangles: list[tuple[int, int, int]] = []
    previous = list(range(rim_count))
    previous_param = np.arange(rim_count, dtype=np.float64) / rim_count
    next_index = rim_count
    for step in range(1, MOUTH_GRID):
        shrink = 1.0 - step / MOUTH_GRID
        ring_u, ring_v = _shrunk_rim(surface, max(6, math.ceil(rim_count * shrink)), shrink)
        indices = list(range(next_index, next_index + len(ring_u)))
        next_index += len(ring_u)
        points.append(surface.points(ring_u, ring_v, surface.heights(ring_u, ring_v)))
        param = np.arange(len(ring_u), dtype=np.float64) / len(ring_u)
        triangles.extend(_zipper(previous, previous_param, indices, param))
        previous, previous_param = indices, param
    zero = np.zeros(1, dtype=np.float64)
    points.append(surface.points(zero, zero, surface.heights(zero, zero)))
    for index in range(len(previous)):
        triangles.append((previous[index], previous[(index + 1) % len(previous)], next_index))
    return np.vstack(points), np.asarray(triangles, dtype=np.int64)


def support_points(surface: MouthSurface) -> NDArray[np.float64]:
    """Stützpunkte im Inneren des Rands auf dem Polynom — für eine Füllung am exakten Kern.

    Drei verkleinerte Kopien des Rands (Viertel, Hälfte, drei Viertel) mit
    acht, sechzehn und vierundzwanzig Punkten und die Mitte: genug, dass die
    Füllung der Fläche folgt, ohne dass jeder Punkt eine eigene Beule zieht.
    """
    rings = []
    for shrink, count in ((0.25, 8), (0.5, 16), (0.75, 24)):
        ring_u, ring_v = _shrunk_rim(surface, count, shrink)
        rings.append(surface.points(ring_u, ring_v, surface.heights(ring_u, ring_v)))
    zero = np.zeros(1, dtype=np.float64)
    rings.append(surface.points(zero, zero, surface.heights(zero, zero)))
    return np.vstack(rings)


def _octants(u: NDArray[np.float64], v: NDArray[np.float64]) -> NDArray[np.int64]:
    """Die Achtel der Ebene um die Mitte — über Vorzeichen und Beträge, ohne
    Winkelfunktion (RM-187: eine Entscheidung darf nicht an ``arctan2`` hängen)."""
    return np.asarray(
        4 * (v < 0.0).astype(np.int64)
        + 2 * (u < 0.0).astype(np.int64)
        + (np.abs(u) < np.abs(v)).astype(np.int64)
    )


def _shrunk_rim(
    surface: MouthSurface, count: int, shrink: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """``count`` Punkte gleichmäßig im Umlauf des Rands, um ``shrink`` zur Mitte gezogen."""
    rim_count = len(surface.rim_u)
    positions = np.arange(count, dtype=np.float64) * (rim_count / count)
    low = np.floor(positions).astype(np.int64) % rim_count
    high = (low + 1) % rim_count
    part = positions - np.floor(positions)
    ring_u = (surface.rim_u[low] * (1.0 - part) + surface.rim_u[high] * part) * shrink
    ring_v = (surface.rim_v[low] * (1.0 - part) + surface.rim_v[high] * part) * shrink
    return ring_u, ring_v


def _zipper(
    outer: list[int],
    outer_param: NDArray[np.float64],
    inner: list[int],
    inner_param: NDArray[np.float64],
) -> list[tuple[int, int, int]]:
    """Zwei geschlossene Züge gleicher Laufrichtung zu einem Band nähen.

    Vorgerückt wird auf dem Zug, dessen nächster Punkt im Umlauf früher liegt —
    so bleibt jedes Dreieck schmal, gleich wie viele Punkte die Züge tragen.
    """
    triangles: list[tuple[int, int, int]] = []
    outer_count, inner_count = len(outer), len(inner)
    i = j = 0
    while i < outer_count or j < inner_count:
        a, b = outer[i % outer_count], outer[(i + 1) % outer_count]
        c, d = inner[j % inner_count], inner[(j + 1) % inner_count]
        next_outer = float(outer_param[i + 1]) if i + 1 < outer_count else 1.0
        next_inner = float(inner_param[j + 1]) if j + 1 < inner_count else 1.0
        if j >= inner_count or (i < outer_count and next_outer <= next_inner):
            triangles.append((a, b, c))
            i += 1
        else:
            triangles.append((a, d, c))
            j += 1
    return triangles


def _area_middle(u: NDArray[np.float64], v: NDArray[np.float64]) -> tuple[float, float] | None:
    """Die Flächenmitte eines geschlossenen Zugs in der Ebene — nicht der Mittelwert
    seiner Punkte: Die Vernetzung setzt sie dort dichter, wo der Rand sich krümmt,
    und am Zylinder R 40 lag deren Mittel 0,26 mm neben der Achse der Bohrung."""
    count = len(u)
    cross: list[float] = []
    first: list[float] = []
    second: list[float] = []
    for index in range(count):
        au, av = float(u[index]), float(v[index])
        bu, bv = float(u[(index + 1) % count]), float(v[(index + 1) % count])
        term = au * bv - bu * av
        cross.append(term)
        first.append((au + bu) * term)
        second.append((av + bv) * term)
    area = math.fsum(cross) / 2.0
    if abs(area) <= units.EPS_GEOM:
        return None
    return math.fsum(first) / (6.0 * area), math.fsum(second) / (6.0 * area)


def _inside(
    polygon_u: NDArray[np.float64],
    polygon_v: NDArray[np.float64],
    u: NDArray[np.float64],
    v: NDArray[np.float64],
) -> NDArray[np.bool_]:
    """Welche Punkte der geschlossene Zug umschließt — gerade-ungerade gezählt."""
    result = np.zeros(len(u), dtype=bool)
    count = len(polygon_u)
    for index in range(count):
        au, av = float(polygon_u[index]), float(polygon_v[index])
        bu, bv = float(polygon_u[(index + 1) % count]), float(polygon_v[(index + 1) % count])
        if av == bv:
            continue
        crosses = (av > v) != (bv > v)
        at = au + (v - av) * ((bu - au) / (bv - av))
        result ^= crosses & (u < at)
    return result


def _facet_heights(
    mesh: MeshData,
    excluded: NDArray[np.int64],
    origin: NDArray[np.float64],
    axes: tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]],
    middle: tuple[float, float],
    offsets: NDArray[np.float64],
    outer: float,
) -> NDArray[np.float64]:
    """Die Höhe der Facette über jedem Rasterpunkt — ``nan``, wo keine darüber liegt.

    Das Raster ist ``offsets`` mal ``offsets`` um ``middle`` (u zuerst). Zählt
    nur, was Fläche ist (:data:`SURFACE_FACING`) und nicht zum Hohlraum gehört;
    liegen zwei Facetten über demselben Punkt, gilt die nähere an der Ebene des
    Rands — die Fläche, in der er liegt, nicht die Rückseite eines dünnen Teils.
    """
    u_axis, v_axis, w_axis = axes
    raw = mesh.raw
    vertices = np.asarray(raw.vertices, dtype=np.float64)
    faces = np.asarray(raw.faces, dtype=np.int64)
    size = len(offsets)
    heights = np.full(size * size, np.nan)
    # Die Vorauswahl über den Hüllquader: ein Würfel um den Rand, groß genug für
    # den Ring und eine Höhe bis zu seinem Radius über der Ebene.
    corner = abs(middle[0]) + abs(middle[1]) + 2.0 * outer
    kept: list[NDArray[np.int64]] = []
    for start in range(0, len(faces), _CHUNK):
        chunk = vertices[faces[start : start + _CHUNK]]
        low, high = chunk.min(axis=1), chunk.max(axis=1)
        hit = np.all((low <= origin + corner) & (high >= origin - corner), axis=1)
        kept.append(np.nonzero(hit)[0] + start)
    candidates = np.concatenate(kept) if kept else np.zeros(0, dtype=np.int64)
    candidates = candidates[~np.isin(candidates, excluded)]
    if not len(candidates):
        return heights
    triangles = vertices[faces[candidates]] - origin
    tu = transform.along(triangles, u_axis) - middle[0]
    tv = transform.along(triangles, v_axis) - middle[1]
    tw = transform.along(triangles, w_axis)
    normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    length = np.sqrt(
        normal[:, 0] * normal[:, 0] + normal[:, 1] * normal[:, 1] + normal[:, 2] * normal[:, 2]
    )
    facing = np.zeros(len(candidates), dtype=bool)
    usable = length > 0.0
    facing[usable] = (
        np.abs(transform.along(normal[usable], w_axis)) >= SURFACE_FACING * length[usable]
    )
    tu, tv, tw = tu[facing], tv[facing], tw[facing]
    if not len(tu):
        return heights
    first, step = float(offsets[0]), float(offsets[1] - offsets[0])
    column_low = np.clip(np.ceil((tu.min(axis=1) - first) / step), 0, size).astype(np.int64)
    column_high = np.clip(np.floor((tu.max(axis=1) - first) / step), -1, size - 1).astype(np.int64)
    row_low = np.clip(np.ceil((tv.min(axis=1) - first) / step), 0, size).astype(np.int64)
    row_high = np.clip(np.floor((tv.max(axis=1) - first) / step), -1, size - 1).astype(np.int64)
    columns = np.maximum(column_high - column_low + 1, 0)
    rows = np.maximum(row_high - row_low + 1, 0)
    pairs = columns * rows
    total = int(pairs.sum())
    if total == 0:
        return heights
    which = np.repeat(np.arange(len(tu)), pairs)
    inside_block = np.arange(total) - np.repeat(np.cumsum(pairs) - pairs, pairs)
    column = column_low[which] + inside_block // rows[which]
    row = row_low[which] + inside_block % rows[which]
    pu, pv = offsets[column], offsets[row]
    au, bu, cu = tu[which, 0], tu[which, 1], tu[which, 2]
    av, bv, cv = tv[which, 0], tv[which, 1], tv[which, 2]
    determinant = (bv - cv) * (au - cu) + (cu - bu) * (av - cv)
    valid = determinant != 0.0
    safe = np.where(valid, determinant, 1.0)
    first_weight = ((bv - cv) * (pu - cu) + (cu - bu) * (pv - cv)) / safe
    second_weight = ((cv - av) * (pu - cu) + (au - cu) * (pv - cv)) / safe
    third_weight = 1.0 - first_weight - second_weight
    # Ein Rasterpunkt genau auf einer Kante gehört beiden Nachbarn; welcher ihn
    # bekommt, ist gleich, solange es einer tut.
    edge = -1e-12
    hit = valid & (first_weight >= edge) & (second_weight >= edge) & (third_weight >= edge)
    if not bool(hit.any()):
        return heights
    level = (
        first_weight[hit] * tw[which[hit], 0]
        + second_weight[hit] * tw[which[hit], 1]
        + third_weight[hit] * tw[which[hit], 2]
    )
    cell = (column[hit] * size + row[hit]).astype(np.int64)
    order = np.lexsort((np.abs(level), cell))
    cell, level = cell[order], level[order]
    first_of_cell = np.r_[True, cell[1:] != cell[:-1]]
    heights[cell[first_of_cell]] = level[first_of_cell]
    return heights


def _terms(x: NDArray[np.float64], y: NDArray[np.float64]) -> list[NDArray[np.float64]]:
    """Die Glieder des Polynoms in (x, y) bis :data:`MOUTH_DEGREE`, in fester Folge."""
    terms = [np.ones_like(x)]
    for degree in range(1, MOUTH_DEGREE + 1):
        for power in range(degree, -1, -1):
            term = np.ones_like(x)
            for _factor in range(power):
                term = term * x
            for _factor in range(degree - power):
                term = term * y
            terms.append(term)
    return terms


def _polynomial(
    x: NDArray[np.float64], y: NDArray[np.float64], z: NDArray[np.float64]
) -> tuple[float, ...] | None:
    """Das Polynom ``z(x, y)`` bis :data:`MOUTH_DEGREE` nach kleinsten Quadraten.

    Normalgleichungen mit ``math.fsum`` über einzeln gerundete Produkte, gelöst
    mit Gauß und Spaltenpivot in Pythons ``float`` — kein LAPACK, keine BLAS-Summe
    (RM-187): Die Koeffizienten setzen jede Ecke des Deckels.
    """
    terms = _terms(x, y)
    matrix = [[math.fsum((first * second).tolist()) for second in terms] for first in terms]
    right = [math.fsum((term * z).tolist()) for term in terms]
    solution = _solved(matrix, right)
    return None if solution is None else tuple(solution)


def _fitted(
    coefficients: tuple[float, ...], x: NDArray[np.float64], y: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Die Höhe des Polynoms — Glied für Glied in fester Folge summiert."""
    total = np.zeros_like(np.asarray(x, dtype=np.float64))
    for coefficient, term in zip(coefficients, _terms(x, y), strict=True):
        total = total + coefficient * term
    return total


def _solved(matrix: list[list[float]], right: list[float]) -> list[float] | None:
    """Ein lineares Gleichungssystem, Gauß mit Spaltenpivot — ``None``, wenn es singulär ist."""
    size = len(right)
    rows = [[*matrix[index], right[index]] for index in range(size)]
    scale = max(abs(value) for row in rows for value in row[:size])
    if scale <= 0.0:
        return None
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: (abs(rows[row][column]), -row))
        if abs(rows[pivot][column]) <= scale * 1e-12:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for row in range(column + 1, size):
            factor = rows[row][column] / rows[column][column]
            if factor == 0.0:
                continue
            for entry in range(column, size + 1):
                rows[row][entry] -= factor * rows[column][entry]
    solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        rest = math.fsum(
            [rows[row][size]]
            + [-rows[row][entry] * solution[entry] for entry in range(row + 1, size)]
        )
        solution[row] = rest / rows[row][row]
    return solution
