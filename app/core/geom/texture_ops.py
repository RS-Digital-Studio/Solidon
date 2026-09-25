"""Oberflächentexturen als echte Geometrie (Konzept P15 §7, Bauplan §25).

Rändel für den Griff, Wabe und Rippe fürs Aussehen, Voronoi und Rauschen für
eine Fläche, der man das Werkzeug nicht ansehen soll. Alles davon entsteht als
**Körper**, nicht als Bild auf einer Fläche: was der Slicer bekommt, ist das,
was man sieht.

**Exakte Gitter, kein abgetastetes Höhenfeld.** Die Muster hier sind Polygone,
deren Ecken auf den Knicklinien des Musters liegen — ein Rändel druckt damit
scharfe Rauten. Wer dieselbe Form über ein Höhenfeld abtastet, bekommt an
jeder Kante die Auflösung des Rasters und damit gerundeten Brei; das ist der
Grund, warum SindriCAD es genauso macht, und ein guter.

**Und die Prüfung, die dort niemand hat** (E1): eine Rille, die schmaler ist
als die Düse, wird nicht gedruckt — sie verschwindet. Eine Prägung flacher als
eine Schicht ebenso. Beides steht im Druckerprofil, es braucht keine neue
Rechnung, nur die Frage an der richtigen Stelle.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Final, cast

import numpy as np

from app.core import units
from app.core.errors import CORRECT_INPUT, Action, ValidationError, require_positive
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import (
    BaseParams,
    Finding,
    OpContext,
    OpResult,
    PrinterProfile,
    SceneObject,
    Vec3,
)
from app.core.units import DEGREE_UNIT, EPS_GEOM, format_length, is_close
from app.i18n import _

_log = get_logger(__name__)

#: Die Muster, die es gibt. Ein Auswahlwert einer Operation, keine acht
#: Menüeinträge (Konzept P15, E11).
PATTERNS: Final[tuple[str, ...]] = (
    "rib",
    "wave",
    "knurl_straight",
    "knurl_diamond",
    "hexagon",
    "dimple",
    "voronoi",
    "noise",
)

#: Wie breit ein Steg im Verhältnis zur Teilung ist. Die Hälfte heißt: Steg und
#: Rille gleich breit — das druckt am saubersten, weil beide dieselbe Grenze
#: haben und keiner vor dem anderen ausfällt.
LAND_SHARE: Final = 0.5

#: Wie groß eine Wabenzelle im Verhältnis zu ihrer Teilung wird. Etwas unter
#: eins, damit zwischen den Zellen eine Wand stehen bleibt statt einer Kante.
HEX_FILL: Final = 0.85

#: Wie groß eine Noppe im Verhältnis zu ihrer Teilung wird — aus demselben
#: Grund unter eins. Bis zum 22.09.2026 war ihr Durchmesser die Teilung
#: selbst: Die Noppen berührten sich in Punkten, die Deckfläche zerfiel in
#: Inseln, und ein um 90 Grad gedrehtes Noppenfeld las die Erkennung als
#: 35 Bohrungen, 5 Langlöcher und 16 Rundungen statt als ein Muster.
DIMPLE_FILL: Final = 0.8

#: Wie fein eine Welle in Segmente zerfällt. Acht Stützstellen je Periode ist
#: die Grenze, unter der man die Ecken sieht — darüber wächst nur die Datei.
WAVE_STEPS: Final = 8

#: Wie viele Zellen eine Voronoi-Fläche höchstens bekommt. Darüber dauert die
#: Triangulierung länger als das Drucken.
MAX_CELLS: Final = 4000


def _grid_positions(width: float, height: float, pitch: float) -> tuple[np.ndarray, np.ndarray]:
    """Rasterlinien, die das Feld sicher überdecken.

    Eine halbe Teilung Zugabe an jeder Seite: sonst endet das Muster vor dem
    Rand, und die Fläche hat einen Saum, den niemand bestellt hat.
    """
    columns = np.arange(-width / 2.0 - pitch, width / 2.0 + pitch * 1.5, pitch)
    rows = np.arange(-height / 2.0 - pitch, height / 2.0 + pitch * 1.5, pitch)
    return columns, rows


def _clip(shapes: list[Any], width: float, height: float) -> list[Any]:
    """Auf das Feld beschneiden. Was ganz draußen liegt, fällt weg."""
    from shapely.geometry import box

    field = box(-width / 2.0, -height / 2.0, width / 2.0, height / 2.0)
    kept: list[Any] = []
    for shape in shapes:
        cut = shape.intersection(field)
        if cut.is_empty or cut.area <= 0.0:
            continue
        # Ein Schnitt kann eine Form in mehrere zerlegen.
        parts = list(getattr(cut, "geoms", [cut]))
        kept.extend(part for part in parts if part.geom_type == "Polygon" and part.area > 0.0)
    return kept


def _ribs(
    width: float, height: float, pitch: float, diagonal: float = 0.0, share: float = LAND_SHARE
) -> list[Any]:
    """Parallele Stege, wahlweise gedreht — die Grundlage von Rippe und Rändel."""
    from shapely import affinity
    from shapely.geometry import box

    land = pitch * share
    # Über die Diagonale hinaus, damit auch gedreht nichts fehlt.
    reach = math.hypot(width, height)
    columns = np.arange(-reach, reach + pitch, pitch)
    strips = [box(float(x), -reach, float(x) + land, reach) for x in columns]
    if diagonal:
        strips = [affinity.rotate(strip, diagonal, origin=(0.0, 0.0)) for strip in strips]
    return _clip(strips, width, height)


def _waves(width: float, height: float, pitch: float, share: float = LAND_SHARE) -> list[Any]:
    """Wellen: sinusförmige Bänder statt flachgedeckelter Stege.

    Der Unterschied zu Rippen ist genau dieser — SindriCAD hatte beide Muster
    getrennt benannt und beide als dasselbe Trapez gezeichnet, bis es jemandem
    auffiel. Hier ist die Welle eine Sinuslinie mit acht Stützstellen je
    Periode, gegen die flachen Prismen der Rippe.
    """
    from shapely.geometry import Polygon

    land = pitch * share
    amplitude = pitch / 4.0
    # Das Raster ist an der Periode verankert, damit auch ihre Maxima und
    # Minima getroffen werden. Eine feste Punktzahl aliasierte hohe Felder
    # bis zur geraden Rippe; die Feldgrenze beschneidet erst danach.
    step = pitch / WAVE_STEPS
    last = math.ceil((height / 2.0 + pitch) / step)
    points = (2 * last + 1) * (math.ceil(width / pitch) + 4) * 2
    if points > MAX_CELLS * WAVE_STEPS * 2:
        raise ValidationError(
            "pitch",
            _(
                "Das Wellenmuster wird mit dieser Teilung zu dicht. Die Teilung vergrößern oder "
                "eine kleinere Fläche wählen."
            ),
            value=pitch,
            constraint="pattern_size",
        )
    steps = np.arange(-last, last + 1, dtype=float) * step
    offsets = amplitude * np.sin(2.0 * math.pi * steps / pitch)
    shapes: list[Any] = []
    columns, _rows = _grid_positions(width, height, pitch)
    for centre in columns:
        left = [(float(centre + shift), float(y)) for y, shift in zip(steps, offsets, strict=True)]
        right = [
            (float(centre + shift + land), float(y))
            for y, shift in zip(steps, offsets, strict=True)
        ]
        shapes.append(Polygon([*left, *reversed(right)]))
    return _clip(shapes, width, height)


def _hexagons(width: float, height: float, pitch: float, fill: float = HEX_FILL) -> list[Any]:
    """Wabe: versetzte Sechsecke, flache Seite oben."""
    from shapely.geometry import Polygon

    radius = pitch / 2.0 * fill
    step_y = pitch * math.sqrt(3.0) / 2.0
    shapes: list[Any] = []
    row = 0
    y = -height / 2.0 - step_y
    while y <= height / 2.0 + step_y:
        offset = (pitch / 2.0) if row % 2 else 0.0
        x = -width / 2.0 - pitch + offset
        while x <= width / 2.0 + pitch:
            corners = [
                (
                    # Die (2i+1)-te Ecke eines Zwoelfecks ist genau
                    # ``pi/6 + i*pi/3`` — aus Ganzzahlen und damit auf jeder
                    # Maschine dieselbe Zahl (RM-187).
                    x + radius * units.circle_point(12, 2 * index + 1)[0],
                    y + radius * units.circle_point(12, 2 * index + 1)[1],
                )
                for index in range(6)
            ]
            shapes.append(Polygon(corners))
            x += pitch
        y += step_y
        row += 1
    return _clip(shapes, width, height)


def _diamonds(width: float, height: float, pitch: float, share: float = LAND_SHARE) -> list[Any]:
    """Kreuzrändel: Rauten im versetzten Raster.

    **Nicht** zwei gekreuzte Stegsätze übereinandergelegt — das gibt ein
    Gitter, das die ganze Fläche bedeckt, und geprägt wäre es eine Platte mit
    Fugen statt eines Griffs. Ein Rändel besteht aus dem, was zwischen zwei
    Rillensätzen stehen bleibt: Rauten. Die werden hier direkt gebaut, mit
    ihren vier Ecken auf den Knicklinien — exakt, wie der Modulkopf es
    verspricht, und in beiden Richtungen brauchbar: erhaben stehen sie hervor,
    vertieft sind sie Mulden.
    """
    from shapely.geometry import Polygon

    half = pitch / 2.0 * share * math.sqrt(2.0)
    shapes: list[Any] = []
    row = 0
    y = -height / 2.0 - pitch
    while y <= height / 2.0 + pitch:
        offset = (pitch / 2.0) if row % 2 else 0.0
        x = -width / 2.0 - pitch + offset
        while x <= width / 2.0 + pitch:
            shapes.append(Polygon([(x - half, y), (x, y - half), (x + half, y), (x, y + half)]))
            x += pitch
        y += pitch / 2.0
        row += 1
    return _clip(shapes, width, height)


def _dimples(width: float, height: float, pitch: float, fill: float = DIMPLE_FILL) -> list[Any]:
    """Noppen: runde Erhebungen im Raster, versetzt wie eine Wabe."""
    from shapely.geometry import Point

    radius = pitch / 2.0 * fill
    step_y = pitch * math.sqrt(3.0) / 2.0
    shapes: list[Any] = []
    row = 0
    y = -height / 2.0 - step_y
    while y <= height / 2.0 + step_y:
        offset = (pitch / 2.0) if row % 2 else 0.0
        x = -width / 2.0 - pitch + offset
        while x <= width / 2.0 + pitch:
            shapes.append(Point(x, y).buffer(radius, quad_segs=8))
            x += pitch
        y += step_y
        row += 1
    return _clip(shapes, width, height)


def _scattered(width: float, height: float, pitch: float, seed: int) -> np.ndarray:
    """Streupunkte mit gespeichertem Startwert (Regel 9).

    Ein eigener Generator statt des globalen Zufalls: dasselbe Modell mit
    demselben Startwert muss gleich herauskommen, sonst beschreibt die Datei
    das Teil nicht mehr (§11.3).
    """
    rng = np.random.default_rng(seed)
    count = min(MAX_CELLS, max(4, int(width * height / (pitch * pitch))))
    return rng.uniform(
        low=(-width / 2.0 - pitch, -height / 2.0 - pitch),
        high=(width / 2.0 + pitch, height / 2.0 + pitch),
        size=(count, 2),
    )


def _voronoi(width: float, height: float, pitch: float, seed: int) -> list[Any]:
    """Voronoi-Zellen um Streupunkte — organisch, aber reproduzierbar."""
    from shapely.geometry import MultiPoint, Polygon
    from shapely.ops import voronoi_diagram

    points = MultiPoint([tuple(row) for row in _scattered(width, height, pitch, seed)])
    cells = voronoi_diagram(points, tolerance=0.0)
    # Etwas geschrumpft, damit zwischen den Zellen eine Wand steht und nicht
    # nur eine Kante — sonst verschmilzt das Muster beim Drucken zu einer
    # Fläche.
    shrunk = [
        cell.buffer(-pitch * 0.08)
        for cell in cells.geoms
        if isinstance(cell, Polygon) and cell.area > 0.0
    ]
    return _clip([cell for cell in shrunk if not cell.is_empty and cell.area > 0.0], width, height)


def _noise(width: float, height: float, pitch: float, seed: int) -> list[Any]:
    """Rauschen: Streuflecken unterschiedlicher Größe, ohne erkennbares Raster."""
    from shapely.geometry import Point

    rng = np.random.default_rng(seed)
    centres = _scattered(width, height, pitch, seed)
    radii = rng.uniform(pitch * 0.15, pitch * 0.45, size=len(centres))
    blobs = [
        Point(float(x), float(y)).buffer(float(radius), quad_segs=6)
        for (x, y), radius in zip(centres, radii, strict=True)
    ]
    return _clip(blobs, width, height)


def pattern_shapes(
    pattern: str,
    width: float,
    height: float,
    pitch: float,
    seed: int = 0,
    *,
    cell: float | None = None,
    wall: float = 0.0,
) -> list[Any]:
    """Die Polygone eines Musters, mittig um den Ursprung in der XY-Ebene.

    Die Umrisse sind exakt — sie werden gleich zu Prismen und danach zu einem
    Körper, nicht zu einem Bild.

    ``cell`` ist die Breite einer Zelle, wie die Erkennung sie misst
    (``perceive.patterns``: Schlüsselweite der Wabe, Breite von Rippe und
    Raute, Durchmesser der Noppe, Breite des Wellenbands über seine
    Amplitude). Ohne Angabe gilt der Anteil, den das Muster von sich aus
    hat — so entsteht ein gelesenes Muster mit seinen eigenen Zellen wieder,
    nicht mit denen der Vorgabe; der Halter mit 9 mm Waben bei 10,4 Teilung
    bekäme sonst 7,7 mm Waben und Wände von 2,7 statt 1,4 mm. Voronoi und
    Rauschen kennen keine Zellbreite: Ihre Zellen sind so groß, wie die Dichte
    sie macht. ``wall`` ist die schmalste Wand, die zwischen zwei Zellen
    bleiben muss — die Düse, wenn eine Maschine bekannt ist; die Zellbreite
    wird darauf begrenzt (:func:`_cell_share`).
    """
    if pattern not in PATTERNS:
        raise ValidationError(
            "pattern",
            _("Dieses Muster gibt es nicht."),
            value=pattern,
            constraint="known_pattern",
        )
    require_positive("pitch", pitch)
    require_positive("width", width)
    require_positive("height", height)
    share = _cell_share(pattern, pitch, cell, wall)
    if pattern == "rib":
        return _ribs(width, height, pitch, share=share)
    if pattern == "wave":
        return _waves(width, height, pitch, share=share)
    if pattern == "knurl_straight":
        return _ribs(width, height, pitch, diagonal=45.0, share=share)
    if pattern == "knurl_diamond":
        return _diamonds(width, height, pitch, share=share)
    if pattern == "hexagon":
        return _hexagons(width, height, pitch, fill=share)
    if pattern == "dimple":
        return _dimples(width, height, pitch, fill=share)
    if pattern == "voronoi":
        return _voronoi(width, height, pitch, seed)
    return _noise(width, height, pitch, seed)


#: Wie viele Wände eine Teilung mindestens misst, damit neben einer Zelle von
#: Wandbreite noch eine Wand steht — je Stil, aus derselben Rechnung wie
#: :func:`_max_share`. Rippe, Rändel, Wabe und Noppe: Zelle plus Wand. Die
#: Welle trägt ihre Amplitude von einer Viertelteilung zweimal in der Zelle
#: und kommt mit vier Dritteln aus. Die Raute des Kreuzrändels hat ihre Rille
#: zum Nachbarn der nächsten Reihe, eine halbe Diagonale weiter: 2·√2.
_PITCH_PER_WALL: Final[dict[str, float]] = {
    "wave": 4.0 / 3.0,
    "knurl_diamond": 2.0 * math.sqrt(2.0),
}

#: Wie nah eine Zelle an ihren Nachbarn heranreichen darf, als Anteil des
#: Abstands zwischen ihnen — knapp darunter, sonst stünde zwischen zwei
#: Zellen keine Wand mehr, sondern eine Kante, und das Muster zerfiele beim
#: Drucken zu einer Fläche.
MAX_CELL_SHARE: Final = 0.98


def _max_share(pattern: str, pitch: float, wall: float) -> float:
    """Der größte Anteil, bei dem zwischen zwei Zellen noch eine Wand steht.

    Zwei Grenzen, die engere gilt. Die eine ist die Geometrie: Der Abstand
    zweier Zellen ist ``1 - MAX_CELL_SHARE`` ihres Nachbarabstands, sonst
    berühren sie sich. Die andere ist die Maschine: ``wall`` ist die
    schmalste Wand, die sie druckt (E1, die Düse) — null heißt: nur die
    Geometrie fragt.

    Je Muster anders gerechnet, weil der Anteil je Muster etwas anderes
    misst — die Umkehrung der Erzeuger oben: Bei Rippe, Rändel und Welle ist
    die Rille ``1 - share`` Teilungen breit. Die Wabe misst über die Flächen
    nur ``√3/2`` ihres ``fill`` — Sechsecke mit ``fill = 2/√3`` füllten das
    Gitter lückenlos. Die Noppe ist ``fill`` Teilungen breit. Und beim
    Kreuzrändel berühren sich die Rauten schon bei ``1/√2``: Ihre halbe
    Diagonale ist ``share·Teilung/√2``, die Nachbarn in der Reihe liegen eine
    Teilung auseinander, die in der nächsten Reihe eine halbe Diagonale
    weiter — deren Rille ist die schmalere, um ``√2``. Ein Anteil von 0,98
    ließe dort alle Rauten zu einer Fläche verschmelzen (gemessen am
    22.09.2026: 253 Rauten, ein Umriss).
    """
    open_share = min(MAX_CELL_SHARE, 1.0 - wall / pitch)
    if pattern == "hexagon":
        return open_share * 2.0 / math.sqrt(3.0)
    if pattern == "knurl_diamond":
        return min(MAX_CELL_SHARE, 1.0 - math.sqrt(2.0) * wall / pitch) / math.sqrt(2.0)
    return open_share


def _cell_share(pattern: str, pitch: float, cell: float | None, wall: float = 0.0) -> float:
    """Der Anteil an der Teilung, der diese Zellbreite ergibt — je Muster anders gerechnet.

    Die Umkehrung dessen, was die Erzeuger oben aus dem Anteil machen: Die
    Rippe ist ``share`` Teilungen breit, die Raute des Kreuzrändels ebenso
    (ihre Seite ist ``share``·Teilung), die Noppe ``fill`` Teilungen, die
    Wabe misst über die Flächen ``√3·fill``·Teilung/2, das Wellenband trägt
    neben dem Steg zweimal die Amplitude von einer Viertelteilung. Eine Breite, die
    keine Wand mehr ließe — keine geometrisch, oder keine, die die Maschine
    druckt (``wall``) —, wird auf :func:`_max_share` begrenzt; eine, die
    nichts ließe, wird abgewiesen.
    """
    if wall > 0.0:
        needed = wall * _PITCH_PER_WALL.get(pattern, 2.0)
        if pitch < needed and not is_close(pitch, needed):
            # Neben der Wand bleibt keine Zelle — oder umgekehrt. Bis zum
            # 22.09.2026 kam hier eine negative Zellbreite heraus (-0,1 mm bei
            # Teilung 0,3 und Düse 0,4), und die Absage danach sprach von der
            # Zellbreite statt von der Teilung.
            raise ValidationError(
                "pitch",
                # Die nötige Teilung steht in den Einzelheiten als „Nötig"; ein
                # Verweis auf „needed_mm" nannte einen Schlüssel, den der Kunde
                # nie sieht (Durchsicht 0.5.0).
                _("Bei dieser Teilung haben Zelle und Wand nebeneinander keinen Platz."),
                value=pitch,
                constraint="minimum",
                values={"needed_mm": math.ceil(needed * 100.0) / 100.0, "wall_mm": wall},
                suggestions=[replace(CORRECT_INPUT, label=_("Teilung vergrößern"))],
            )
    if cell is None:
        return {"hexagon": HEX_FILL, "dimple": DIMPLE_FILL}.get(pattern, LAND_SHARE)
    require_positive("cell_width", cell)
    if pattern == "hexagon":
        share = 2.0 * cell / (math.sqrt(3.0) * pitch)
    elif pattern == "wave":
        share = (cell - pitch / 2.0) / pitch
    else:
        share = cell / pitch
    if share <= 0.0:
        raise ValidationError(
            "cell_width",
            _("Eine Zelle dieser Breite bleibt bei dieser Teilung nicht übrig."),
            value=cell,
            constraint="minimum",
            suggestions=[replace(CORRECT_INPUT, label=_("Zellbreite vergrößern"))],
        )
    return min(share, _max_share(pattern, pitch, wall))


def cell_width_for(
    pattern: str, pitch: float, cell: float | None, *, wall: float = 0.0
) -> float | None:
    """Die Zellbreite, die dieses Muster bei dieser Teilung wirklich bekommt.

    Die Umkehrung von :func:`_cell_share` nach der Begrenzung: Wer 9 mm
    Waben bei 6 mm Teilung verlangt, bekommt so breite, wie die Teilung
    zulässt — bei einer Wand von ``wall`` dazwischen, der Düse — und soll
    das lesen, nicht raten. Voronoi und Rauschen haben keine Zellbreite und
    geben ``None``.
    """
    if pattern in {"voronoi", "noise"}:
        return None
    share = _cell_share(pattern, pitch, cell, wall)
    if pattern == "hexagon":
        return share * math.sqrt(3.0) * pitch / 2.0
    if pattern == "wave":
        return share * pitch + pitch / 2.0
    return share * pitch


def narrowest_structure(pattern: str, pitch: float, cell: float | None = None) -> float:
    """Die schmalste Stelle eines Musters — Steg oder Rille, je nachdem, was schmaler ist.

    Je Stil anders, denn je Stil liegt die Rille woanders: Bei Rippe, gerader
    Rändel und Welle ist sie ``1 - share`` Teilungen breit (die Wellenbänder
    schwingen gemeinsam), beim Kreuzrändel liegt der Nachbar der nächsten
    Reihe eine halbe Diagonale weiter — ``Teilung/√2 - share·Teilung``, bei
    der Vorgabe ein Fünftel der Teilung, nicht die Hälfte —, bei der Wabe
    ``Teilung - Schlüsselweite``, bei der Noppe ``Teilung - Durchmesser``.
    Voronoi-Zellen stehen ``0,16`` Teilungen auseinander (``_voronoi``
    schrumpft jede um ``0,08``), die Streuflecken des Rauschens sind
    mindestens ``0,3`` Teilungen breit und dürfen sich berühren. Und die Zelle
    selbst zählt mit: Ein Steg schmaler als die Düse wird ebenso wenig
    gedruckt wie eine Rille.
    """
    if pattern == "voronoi":
        return 0.16 * pitch
    if pattern == "noise":
        return 0.3 * pitch
    share = _cell_share(pattern, pitch, cell)
    width = cell_width_for(pattern, pitch, cell) or pitch * share
    if pattern == "knurl_diamond":
        groove = pitch / math.sqrt(2.0) - share * pitch
    elif pattern in {"hexagon", "dimple"}:
        groove = pitch - width
    else:
        groove = pitch * (1.0 - share)
    return max(min(groove, width), 0.0)


def check_printable(
    pattern: str,
    pitch: float,
    depth: float,
    printer: PrinterProfile,
    *,
    cell: float | None = None,
) -> None:
    """Ob dieses Muster auf dieser Maschine überhaupt entsteht (E1).

    Zwei Fragen, beide beantwortbar, ohne etwas zu rechnen:

    * Ist die schmalste Struktur breiter als das kleinste Detail des Druckers
      — die Düse bei FDM, der Bildpunkt bei Resin? Was schmaler ist, wird
      nicht gedruckt — es verschwindet, und das Teil kommt glatt heraus. Wo
      sie liegt, weiß :func:`narrowest_structure` je Stil — bis zum 22.09.2026
      galt für alle acht die halbe Teilung, und die Rille des Kreuzrändels ist
      ein Fünftel.
    * Ist die Prägung tiefer als eine Schicht? Was flacher ist, fällt beim
      Runden der Schichthöhe weg.

    Ein Fehler nennt beides Mal, was jetzt möglich ist (Regel 17): die Zahl,
    die passen würde, steht in der Meldung.
    """
    narrowest = narrowest_structure(pattern, pitch, cell)
    detail = printer.smallest_detail
    # Gleich breit ist breit genug: Die Wand, die ``cell_width_for`` auf das
    # kleinste Detail begrenzt hat, kommt hier als ``pitch - width`` zurück —
    # um ein Rundungsrauschen unter dem Detail, und das ist kein Befund.
    if narrowest < detail and not is_close(narrowest, detail):
        # Die Teilung, bei der dieselbe Stelle so breit wie das kleinste
        # Detail wäre — alles am Muster wächst mit der Teilung.
        needed = pitch * detail / max(narrowest, EPS_GEOM)
        raise ValidationError(
            "pitch",
            # Wie groß die Teilung mindestens sein muss, steht in den
            # Einzelheiten als „Nötig" — nicht als Schlüssel im Satz
            # (Durchsicht 0.5.0).
            _(
                "Bei dieser Teilung sind die Stege schmaler als ein Bildpunkt — sie "
                "werden nicht belichtet."
            )
            if printer.is_resin
            else _(
                "Bei dieser Teilung sind die Stege schmaler als die Düse — sie werden "
                "nicht gedruckt."
            ),
            value=pitch,
            constraint="nozzle_width",
            values={"needed_mm": round(needed, 2), "nozzle_mm": detail},
            suggestions=[replace(CORRECT_INPUT, label=_("Teilung vergrößern"))],
        )
    if depth < printer.layer_height:
        raise ValidationError(
            "depth",
            _("Diese Prägung ist flacher als eine Schicht und verschwindet beim Drucken."),
            value=depth,
            constraint="layer_height",
            values={"layer_mm": printer.layer_height},
            suggestions=[replace(CORRECT_INPUT, label=_("Tiefe vergrößern"))],
        )


# --- die Operation (Bauplan §25, Kategorie „Oberfläche") -------------------------


@op_params
class TextureParams(BaseParams):
    coverage: str = param(
        title=_("Bereich"),
        default="rectangle",
        choices=("rectangle", "whole_face"),
        doc=_(
            "Ein rechteckiges Musterfeld oder die ganze gewählte Fläche bis zum Rand. "
            "Bohrungen bleiben frei."
        ),
    )
    face: str = param(
        title=_("Fläche"),
        default="",
        kind="feature",
        depends_on=("coverage", ("whole_face",)),
        doc=_("Die gewählte ebene Fläche begrenzt das Muster einschließlich ihrer Aussparungen."),
    )
    pattern: str = param(
        title=_("Muster"),
        default="knurl_diamond",
        choices=PATTERNS,
        doc=_(
            "Welches Muster aufgebracht wird. Rändel gibt Griff, Wabe und Rippe "
            "sind Zierde, Voronoi und Rauschen verstecken die Schichtlinien."
        ),
    )
    width: float = param(
        title=_("Breite"),
        default=40.0,
        unit="mm",
        minimum=0.5,
        doc=_("Wie breit das Musterfeld auf der Fläche wird."),
        depends_on=("coverage", ("rectangle",)),
    )
    height: float = param(
        title=_("Höhe"),
        default=30.0,
        unit="mm",
        minimum=0.5,
        doc=_("Wie hoch das Musterfeld wird. Es sitzt mittig auf dem gewählten Ort."),
        depends_on=("coverage", ("rectangle",)),
    )
    pitch: float = param(
        title=_("Teilung"),
        default=2.0,
        unit="mm",
        minimum=0.1,
        doc=_(
            "Abstand von Steg zu Steg. Die Stege sind halb so breit; liegen sie "
            "unter der Düse, wird das Muster nicht gedruckt und die Operation "
            "sagt es, statt es zu versuchen."
        ),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.6,
        unit="mm",
        minimum=0.02,
        doc=_(
            "Wie hoch das Muster steht oder wie tief es einschneidet. Flacher als "
            "eine Schicht verschwindet es beim Drucken."
        ),
    )
    mode: str = param(
        title=_("Art"),
        default="raised",
        choices=("raised", "engraved"),
        # **Er sagt die Richtung, und die braucht mehr als die Boolesche
        # Operation.** Die Tiefenstufe der Flächenplatzierung fragt hier,
        # ob ein Zug nach unten überhaupt etwas abträgt; bei ``raised``
        # vergrößerte sie sonst einen Wert, der nach außen geht.
        subtractive_on=("engraved",),
        doc=_(
            "Erhaben legt das Muster auf die Fläche, vertieft schneidet es hinein. "
            "Ein vertieftes Rändel greift sich anders als ein erhabenes — welches "
            "besser ist, entscheidet die Hand."
        ),
    )
    wrap: str = param(
        title=_("Auflegen"),
        default="flat",
        choices=("flat", "cylinder"),
        placement="advanced",
        depends_on=("coverage", ("rectangle",)),
        doc=_(
            "Flach auf eine Ebene oder umlaufend um einen Zylinder. Ein Rändel "
            "gehört um den Griff, nicht als Fleck darauf."
        ),
    )
    wrap_diameter: float = param(
        title=_("Durchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_(
            "Der Durchmesser, um den das Muster läuft. Nur beim Umlaufen. Eine "
            "angeklickte Zylinderfläche trägt ihn selbst ein."
        ),
        depends_on=("wrap", ("cylinder",)),
    )
    angle: float = param(
        title=_("Drehung"),
        default=0.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        placement="advanced",
        # Um einen Zylinder wird mit Winkel null gebogen (``texture_tool``).
        # Ausgrauen geht nicht über ``depends_on`` — beim Muster bis zum Rand
        # gilt die Drehung, und dort ist ``wrap`` gar nicht wirksam —, also
        # sagt es der Satz, und die Operation meldet es (``texture.angle_on_wrap``).
        doc=_(
            "Dreht das Muster in der Fläche. Um einen Zylinder läuft es entlang des "
            "Umfangs, die Drehung wirkt dort nicht."
        ),
    )
    x: float = param(
        title=_("Position X"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Mitte des Feldes. Eine angeklickte Fläche trägt den Wert selbst ein."),
        depends_on=("coverage", ("rectangle",)),
    )
    y: float = param(
        title=_("Position Y"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Zweite Achse der Position — siehe Position X."),
        depends_on=("coverage", ("rectangle",)),
    )
    z: float = param(
        title=_("Position Z"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Höhe der Fläche, auf die das Muster kommt."),
        depends_on=("coverage", ("rectangle",)),
    )
    nx: float = param(
        title=_("Richtung X"),
        default=0.0,
        placement="advanced",
        doc=_("Normale der Fläche. Aus einer angeklickten Fläche kommt sie mit."),
        depends_on=("coverage", ("rectangle",)),
    )
    ny: float = param(
        title=_("Richtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Zweite Achse der Richtung — siehe Richtung X."),
        depends_on=("coverage", ("rectangle",)),
    )
    nz: float = param(
        title=_("Richtung Z"),
        default=1.0,
        placement="advanced",
        doc=_("Dritte Achse der Richtung. Vorgabe ist nach oben."),
        depends_on=("coverage", ("rectangle",)),
    )


def _fell_apart(before: Any, after: Any, mode: str) -> Finding | None:
    """Ist der Körper unter dem Muster in Stücke zerfallen? (Regel 17)

    **Der Fall, den die Durchmesserprüfung nicht sieht.** Läuft das Muster um
    einen Zylinder, der *kleiner* ist als der Körper, ragt nichts hinaus —
    :func:`_wrap_beyond_body` schweigt zu Recht. Es liegt dann aber *innerhalb*
    der Fläche, berührt sie nirgends, und die Vereinigung legt Hunderte lose
    Stücke daneben. Gemessen am ⌀75-Deckel der Galerie-Dose mit dem gealterten
    ``wrap_diameter`` von 65,3: **553 Komponenten**, wo eine war — wasserdicht,
    mit plausiblem Volumen, und auf dem Vorschaubild ein glatter Deckel. Was
    fehlte, sah aus wie eine Gestaltungsentscheidung.

    **Die Teilezahl lügt nicht**, und deshalb prüft sie und nicht die
    Abweichung: Sie ist binär statt toleranzbehaftet und fängt beide
    Richtungen — 760 Teile beim zu großen Wickelzylinder, 553 beim zu kleinen.
    Dieselbe Bauart wie ``parts._hanging_loose``, und aus demselben Grund: Eine
    nachgerechnete Fläche stimmt und der Körper zerfällt trotzdem.

    Nur bei **erhabenem** Muster: Ein vertieftes schneidet, und Schneiden darf
    teilen — bei manchen Mustern ist das der Zweck.
    """
    from app.core.geom.boolean import fell_apart

    return fell_apart(
        before,
        after,
        applies=mode == "raised",
        code="texture.fell_apart",
        message=lambda loose: _(
            "Das Muster hängt nicht am Körper: Es liegt in {loose} losen Stücken "
            "daneben und würde einzeln gedruckt. Meist ist der Durchmesser des "
            "Wickelzylinders veraltet — klicken Sie die Zylinderfläche neu an.",
            loose=loose,
        ),
    )


def _wrap_beyond_body(body: Any, wrap_diameter: float) -> Finding | None:
    """Läuft das Muster um einen Zylinder, den der Körper gar nicht hat? (Regel 17)

    **Der Wickeldurchmesser wird einmal abgelesen und altert dann.** Der Dialog
    trägt ihn ein, wenn man eine Zylinderfläche anklickt — von da an steht eine
    Zahl im Schritt, und die weiß nichts davon, dass der Körper danach kleiner
    geworden ist. In einem parametrischen Projekt ist das der Normalfall: Wer
    einen Projektparameter ändert, ändert die Geometrie und nicht die
    abgelesenen Zahlen in den Schritten darüber.

    Gemessen an der Galerie-Dose am 30.08.2026: Ihr Rezept trägt
    ``wrap_diameter = 65.3`` als feste Zahl — den Deckeldurchmesser bei einer
    Dose von 60 mm. Stellt der Kunde sie auf 50 mm, wofür ein Projektparameter
    da ist, läuft die Rändelung um einen Zylinder, der zehn Millimeter breiter
    ist als der Deckel, und steht 11,5 mm über dessen Rand. Der Druck gelingt
    und ist Ausschuss. Gemeldet hat das nichts: kein Fehler, kein Befund, kein
    Hinweis.

    **Gemeldet wird nur, was hinausragen muss**, nicht jede Abweichung: Ein
    Muster auf einer kleinen Zylinderfläche eines großen Körpers hat
    berechtigterweise einen kleineren Wickeldurchmesser als dessen Hüllquader.
    Umgekehrt geht es nicht — ein Zylinder, der breiter ist als der ganze
    Körper, kann keine seiner Flächen sein.

    Ein Befund und kein Fehler: Wer ein Muster bewusst überstehen lässt, darf
    das. Er soll es nur nicht versehentlich tun.
    """
    size = body.bounds.size
    widest = max(size[0], size[1])
    if wrap_diameter <= widest + EPS_GEOM:
        return None
    return Finding(
        code="texture.wrap_beyond_body",
        severity="warning",
        message=_(
            "Das Muster läuft um einen Zylinder, der breiter ist als der Körper — "
            "es steht über dessen Rand hinaus. Klicken Sie die Zylinderfläche neu "
            "an, damit der Durchmesser wieder zum Körper passt."
        ),
        values={
            "wrap_diameter_mm": round(wrap_diameter, 3),
            "body_diameter_mm": round(widest, 3),
        },
    )


#: Die Muster aus Streifen — ihre Zelle ist so lang wie das Feld, und ob sie
#: ganz ist, sagt das Feld, nicht die Zelle.
STRIP_PATTERNS: Final[frozenset[str]] = frozenset({"rib", "wave", "knurl_straight"})

#: Wie weit sich ein Muster entlang der ersten Feldachse wiederholt, in
#: Teilungen: Die Stege des geraden Rändels laufen unter 45 Grad, und quer zu
#: ihnen liegt die Teilung — entlang der Achse ist es die Diagonale.
_PERIOD_ALONG_X: Final[dict[str, float]] = {"knurl_straight": math.sqrt(2.0)}


def wrap_pitch(pattern: str, pitch: float, diameter: float, width: float) -> float:
    """Die Teilung, mit der ein Muster um den ganzen Umfang aufgeht.

    Ein Feld, das den Umfang erreicht, endet an der Naht, und dort trifft
    seine letzte Zelle auf seine erste. Der Umfang geht selten in Teilungen
    auf; bis zum 22.09.2026 überlagerten sich dort zwei versetzte Spalten zu
    Klumpen, die keine Zelle mehr waren — die Erkennung ließ sie aus, das
    Entfernen ließ sie stehen. Deshalb rückt die Teilung auf den nächsten
    Teiler des Umfangs: um höchstens eine halbe Periode auf die Zahl der
    Perioden, bei 31 auf Ø 30 ein Prozent. Ein Feld, das nicht herumreicht,
    behält seine Teilung; Voronoi und Rauschen haben keine.
    """
    if pattern in {"voronoi", "noise"} or diameter <= EPS_GEOM or pitch <= EPS_GEOM:
        return pitch
    circumference = math.pi * diameter
    if width < circumference - EPS_GEOM:
        return pitch
    factor = _PERIOD_ALONG_X.get(pattern, 1.0)
    count = max(1, round(circumference / (pitch * factor)))
    return circumference / count / factor


def _one_turn(shapes: list[Any], circumference: float, period: float) -> list[Any]:
    """Von einem Feld, das weiter als der Umfang reicht, jede Zelle genau einmal — ganz.

    Am Umfang angeschnittene Zellen sind die Falle der Naht: Zwei Hälften, an
    ``±π·R`` getrennt und dort wieder aufeinandergebogen, verschweißt die
    Boolesche Rechnung nicht zuverlässig — am Wabenmuster blieb eine Haut
    von 16 mm² zwischen den Halbzellen stehen und teilte den Stift in zwei
    (22.09.2026). Deshalb wird nicht geschnitten, sondern gewählt: Ein
    Fenster von einer Umfangslänge, und jede Zelle, deren Mitte darin liegt,
    bleibt ganz — auch die, die über das Fensterende hinausreicht, denn ihr
    Gegenstück am anderen Ende fällt heraus. Die Fensterkanten liegen eine
    Viertelperiode neben einer Zellmitte: Die Mitten stehen in halben
    Perioden, und keine fällt auf eine Kante.
    """
    if not shapes:
        return shapes
    centres = np.array([shape.centroid.x for shape in shapes], dtype=float)
    nearest = float(centres[int(np.argmin(np.abs(centres + circumference / 2.0)))])
    start = nearest - period / 4.0
    return [
        shape
        for shape, x in zip(shapes, centres, strict=True)
        if start <= x < start + circumference
    ]


def sagitta(diameter: float, pitch: float) -> float:
    """Wie weit die Sehne unter dem Bogen zurückbleibt.

    Ein Musterelement ist nach dem Biegen ein gerades Stück auf einem runden
    Körper. Zwischen seinen Enden klafft in der Mitte genau dieser Abstand —
    bei 2,5 mm Teilung auf zwanzig Millimeter Durchmesser sind es acht
    Hundertstel, also mehr als die Überlappung, mit der die Vereinigung
    gerechnet hätte.

    Gemessen an der Teilung und nicht am einzelnen Element: die Teilung ist die
    Obergrenze für die Breite jedes Elements, und eine Rechnung je Element
    hieße, das Feld dafür auseinanderzunehmen.
    """
    radius = diameter / 2.0
    if radius <= EPS_GEOM:
        return 0.0
    half = min(pitch / 2.0, radius)
    return radius - math.sqrt(max(0.0, radius * radius - half * half))


#: Wie weit die Sehnen eines um einen Zylinder gebogenen Körpers unter dem
#: Bogen liegen dürfen — ein Viertel dessen, was der Kern beim Tessellieren
#: zulässt, damit ein Boden auf dem Zylinder und die Facetten des Körpers
#: zusammen unter der Einpassungstoleranz eines Stifts bleiben.
BEND_SAG: Final = units.MAX_FACET_SAG / 4.0


def refined_for_bending(body: MeshData, radius: float, sag: float = BEND_SAG) -> MeshData:
    """Jede Kante so kurz, dass sie um diesen Radius gebogen dem Bogen folgt.

    Der exakte Netzkern teilt (``mesh_ops.refined``): konform, jede Schale
    bleibt geschlossen — ``trimesh`` ließe an der Naht zwischen verschieden
    oft geteilten Flächen offene Kanten zurück. Die Kantenlänge folgt aus
    der Sehnenabweichung ``sag`` und dem Radius: :data:`BEND_SAG`, oder die
    der Facetten des Trägers, wenn der gebogene Körper Teil seines Mantels
    wird — ein Stopfen, der die Zellen füllt, muss so fein sein wie der
    Mantel um ihn, sonst passt auf den Mantel danach kein Zylinder mehr.
    """
    from app.core.geom.mesh_ops import refined

    sag = min(max(sag, BEND_SAG / 4.0), BEND_SAG)
    edge = 2.0 * math.sqrt(max(2.0 * radius * sag - sag**2, EPS_GEOM))
    return refined(body, edge)


def wrapped(body: MeshData, diameter: float) -> MeshData:
    """Biegt ein flaches Musterfeld um einen Zylinder.

    Die x-Richtung des Feldes wird zum Umfang, y zur Zylinderachse, z bleibt die
    Prägungshöhe: ein Punkt landet bei Winkel ``x / radius`` auf dem Radius
    ``radius + z``. Damit läuft ein Rändel wirklich um den Griff, statt als
    ebenes Feld darauf zu kleben und ihn nur in der Mitte zu treffen — das war
    der Grund, warum ein Griff bis hierhin nicht texturierbar war.

    Die Achse zeigt danach nach Z, und deshalb bedeutet die Richtung
    ``(nx, ny, nz)`` beim Umlaufen die **Achse** des Zylinders statt der
    Normalen einer Fläche: ``place`` dreht Z dorthin. Für den stehenden Griff
    ist das die Vorgabe, und niemand muss etwas eintragen.

    Gebogen werden die Ecken — und damit die Flächen dazwischen dem Zylinder
    folgen, teilt der exakte Kern vorher jede Kante des Feldes, bis ihre Sehne
    höchstens :data:`BEND_SAG` unter dem Bogen hängt (:func:`refined_for_bending`;
    die Diagonalen im Inneren einer Fläche bis zum Dreifachen, siehe
    ``mesh_ops.refined``).
    Bis zum 22.09.2026 blieben die Elemente gerade: Der Boden einer Rille war
    in der Mitte um die Sehnenabweichung tiefer als an den Rändern, die Krone
    einer Raute flach, und die Wände zweier Nachbarn kippten gegeneinander.

    Ein Feld breiter als der Umfang endet an der Naht — ``texture_tool``
    schneidet die Elemente dort ab, bevor sie hierherkommen. Bis zum
    22.09.2026 lief es mehrfach herum und überlagerte sich selbst; die
    Vereinigung räumte das auf, aber zu Klumpen, die keine Zelle mehr waren.
    """
    import numpy as np
    import trimesh

    if diameter <= EPS_GEOM:
        raise ValidationError(
            "diameter",
            _("Zum Umlaufen fehlt der Durchmesser des Zylinders."),
            value=diameter,
            constraint="needs_diameter",
            suggestions=[
                Action(
                    id="texture.pick_cylinder",
                    label=_("Eine Zylinderfläche anklicken"),
                    primary=True,
                ),
                Action(id="texture.wrap_flat", label=_("Flach auflegen statt umlaufend")),
            ],
        )
    radius = diameter / 2.0
    body = refined_for_bending(body, radius)
    points = np.asarray(body.raw.vertices, dtype=float)
    theta = points[:, 0] / radius
    reach = radius + points[:, 2]
    turned = np.column_stack((reach * np.cos(theta), reach * np.sin(theta), points[:, 1]))
    return MeshData.of(trimesh.Trimesh(vertices=turned, faces=body.raw.faces, process=False))


def _face_texture_tool(source: SceneObject, params: TextureParams, seed: int) -> MeshData:
    """Schneidet Musterpolygone am tatsächlichen Flächenumriss samt Lochrändern ab."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from app.core.errors import CANCEL, CHANGE_SELECTION, GeometryError
    from app.core.geom.face_ops import _chosen_face, _no_face
    from app.core.geom.faces import FLAT_ENOUGH_FOR_A_TOOL, _triangles_of, face_normal
    from app.core.geom.mesh import as_mesh_data
    from app.core.sketch.planes import frame_of

    feature = _chosen_face(source, params.face)
    if feature is None:
        raise _no_face()
    mesh = as_mesh_data(source.mesh)
    indices = _triangles_of(mesh, feature)
    normal = face_normal(feature)
    corners = np.asarray(mesh.raw.triangles)[indices]
    origin = corners.reshape((-1, 3)).mean(axis=0)
    frame = frame_of(normal, cast(Vec3, tuple(origin)))
    basis = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    radians = math.radians(params.angle)
    turn = np.array(
        [
            [math.cos(radians), -math.sin(radians), 0.0],
            [math.sin(radians), math.cos(radians), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    basis = basis @ turn
    local = (corners - origin) @ basis
    if np.max(np.abs(local[:, :, 2])) > FLAT_ENOUGH_FOR_A_TOOL:
        raise GeometryError(
            detail=_("Für ein Muster bis zum Rand wählen Sie eine ebene Fläche."),
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    outline = unary_union([Polygon(triangle[:, :2]) for triangle in local])
    return tool_in_outline(
        outline,
        basis,
        cast(Vec3, tuple(float(value) for value in origin)),
        pattern=params.pattern,
        pitch=params.pitch,
        depth=params.depth,
        mode=params.mode,
        seed=seed,
    )


def tool_in_outline(
    outline: Any,
    basis: np.ndarray,
    origin: Vec3,
    *,
    pattern: str,
    pitch: float,
    depth: float,
    mode: str,
    seed: int = 0,
    cell: float | None = None,
    wall: float = 0.0,
    whole_cells: bool = False,
    anchor: tuple[float, float] | None = None,
) -> MeshData:
    """Der Werkzeugkörper eines Musters, am Umriss abgeschnitten, in Weltkoordinaten.

    ``outline`` ist ein ``shapely``-Umriss in den Achsen von ``basis`` mit
    ``origin`` als Nullpunkt — die Fläche samt ihren Aussparungen beim Muster
    bis zum Rand. Das Werkzeug selbst baut :func:`flat_tool`; hier wird es
    auf die Ebene gelegt. Ein gelesenes Muster legt es beim Ändern selbst ab
    (``perceive.patterns.Field.placed``) — auf eine Ebene oder um einen
    Zylinder —, mit demselben flachen Werkzeug.
    """
    from app.core.geom.transform import apply

    body = flat_tool(
        outline,
        pattern=pattern,
        pitch=pitch,
        depth=depth,
        mode=mode,
        seed=seed,
        cell=cell,
        wall=wall,
        whole_cells=whole_cells,
        anchor=anchor,
    )
    matrix = np.eye(4)
    matrix[:3, :3] = basis
    matrix[:3, 3] = np.asarray(origin, dtype=float)
    return apply(body, matrix)


def flat_tool(
    outline: Any,
    *,
    pattern: str,
    pitch: float,
    depth: float,
    mode: str,
    seed: int = 0,
    cell: float | None = None,
    wall: float = 0.0,
    whole_cells: bool = False,
    anchor: tuple[float, float] | None = None,
    clearance: float = 0.0,
    around: float = 0.0,
) -> MeshData:
    """Der Werkzeugkörper eines Musters, am Umriss abgeschnitten, in dessen Achsen.

    ``around`` ist der Umfang, wenn der Umriss einmal um einen Zylinder
    reicht: Dann wird das Muster über mehr als eine Runde gezeichnet und je
    Zelle einmal gewählt (:func:`_one_turn`), und der Umriss gilt periodisch —
    eine Zelle über der Naht wird nicht an ihr geschnitten.

    Die Fläche liegt bei ``z = 0``: Erhaben steht das Werkzeug darüber und
    reicht um den Überlapp hinein, vertieft steht es darunter und reicht um
    den Überlapp heraus. ``clearance`` verlängert dieses Hineinreichen — um
    einen Zylinder um die Sehnenabweichung seiner Facetten, sonst träfe ein
    Boden, der bündig mit dem Radius läge, die Facetten nur an ihren Ecken.

    ``whole_cells`` lässt nur Zellen zu, die ganz im Umriss liegen — und um
    eine halbe Wand vom Rand entfernt, damit die Außenwand so dick wird wie
    die Wände zwischen den Zellen: Eine durchgehende Zelle, die der Rand
    anschneidet, wäre eine Kerbe in der Seitenwand — der Halter mit seinen
    196 Waben hat keine, und er soll nach dem Ändern der Teilung auch keine
    bekommen.

    ``anchor`` ist ein Punkt in den Achsen des Umrisses, auf den eine Zelle
    genau zu liegen kommt: Die Mitte einer gelesenen Zelle, damit ein Muster
    mit neuer Tiefe an derselben Stelle steht wie vorher, statt am Feldrand
    neu zu beginnen.
    """
    from shapely import affinity
    from shapely.ops import unary_union

    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.geom.label_ops import label_solid
    from app.core.geom.transform import apply, translation

    low_x, low_y, high_x, high_y = outline.bounds
    centre_x, centre_y = (low_x + high_x) / 2.0, (low_y + high_y) / 2.0
    # Mit Anker das Feld um eine Teilung je Seite größer als der Umriss: Die
    # Erzeuger schneiden am Feldrand ab, und der Anker rückt das Raster um
    # bis zu eine halbe Teilung — eine am Feldrand halbierte Zelle läge danach
    # ganz im Umriss und gälte als ganze (Review, 22.09.2026: halbe Sechsecke
    # als Durchbrüche). Ohne Anker bleibt das Feld der Umriss, denn die Lage
    # des Rasters hängt an der Feldgröße, und ``apply_texture`` zeichnet mit
    # derselben Fassung dasselbe Bild.
    margin = 2.0 * pitch if anchor is not None else 0.0
    period = pitch * _PERIOD_ALONG_X.get(pattern, 1.0)
    if around > 0.0:
        margin = 2.0 * (period + high_y - low_y)
    shapes = pattern_shapes(
        pattern,
        high_x - low_x + margin,
        high_y - low_y + margin,
        pitch,
        seed,
        cell=cell,
        wall=wall,
    )
    shift_x, shift_y = centre_x, centre_y
    if anchor is not None and shapes:
        # Die Zelle, die dem Anker am nächsten liegt, kommt genau auf ihn —
        # höchstens eine halbe Teilung Weg, und alle anderen rücken mit.
        nearest = min(
            shapes,
            key=lambda shape: (
                (shape.centroid.x + centre_x - anchor[0]) ** 2
                + (shape.centroid.y + centre_y - anchor[1]) ** 2
            ),
        )
        shift_x = anchor[0] - nearest.centroid.x
        shift_y = anchor[1] - nearest.centroid.y
    shapes = [affinity.translate(shape, shift_x, shift_y) for shape in shapes]
    if around > 0.0:
        shapes = _one_turn(shapes, around, period)
        # Der Umriss gilt periodisch: Eine Zelle, die über sein Ende
        # hinausreicht, findet ihn dahinter wieder.
        outline = unary_union(
            [outline, affinity.translate(outline, around), affinity.translate(outline, -around)]
        )
    clipped: list[Any] = []
    wall = max(pitch - cell, 0.0) if cell is not None else 0.0
    inside = outline.buffer(-wall / 2.0) if whole_cells and wall > EPS_GEOM else outline
    for moved in shapes:
        if whole_cells:
            if inside.contains(moved):
                clipped.append(moved)
            continue
        cut = moved.intersection(outline)
        clipped.extend(
            part
            for part in getattr(cut, "geoms", [cut])
            if part.geom_type == "Polygon" and part.area > EPS_GEOM
        )
    # Streuflecken dürfen überlappen. Vor dem Extrudieren zusammenführen,
    # damit ihre Innenwände keine zusätzlichen geschlossenen Schalen bilden.
    # Projektion und Schnitt erzeugen gelegentlich doppelte Randpunkte mit
    # rein numerischem Abstand. Ohne Bereinigung werden daraus Nullhäute.
    merged = unary_union(clipped).simplify(EPS_GEOM, preserve_topology=True)
    regions = [
        part
        for part in getattr(merged, "geoms", [merged])
        if part.geom_type == "Polygon" and part.area > EPS_GEOM
    ]
    body = label_solid(regions, depth + BOOLEAN_OVERLAP + clearance)
    if body is None:
        raise ValidationError(
            "pattern",
            _("Aus diesem Muster entstand nichts — die Teilung passt nicht ins Feld."),
            value=pattern,
            constraint="no_shapes",
        )
    lift = -BOOLEAN_OVERLAP - clearance if mode == "raised" else -depth
    return apply(body, translation((0.0, 0.0, lift)))


def _merged(shapes: list[Any]) -> list[Any]:
    """Überlappende Umrisse zu einem, bevor sie Prismen werden.

    Die Streuflecken des Rauschens dürfen sich überlappen — als Umriss. Als
    zwei Prismen übereinander waren sie ein Werkzeug, das sich selbst
    durchdringt, und die Differenz damit ließ auf der Deckfläche doppelte
    Dreiecke zurück: 2 773 Dreiecke mit 2 908 mm² auf einer Fläche von
    1 200 (gemessen am 22.09.2026, Rauschen mit 2 mm Teilung auf 40 mal 30).
    Die Flächensuche fand diese Deckfläche nicht mehr, und die Erkennung
    damit kein Muster. Der Weg über die ganze Fläche führte dieselben
    Umrisse längst zusammen; hier fehlte es.
    """
    from shapely.ops import unary_union

    merged = unary_union(shapes).simplify(EPS_GEOM, preserve_topology=True)
    return [
        part
        for part in getattr(merged, "geoms", [merged])
        if part.geom_type == "Polygon" and part.area > EPS_GEOM
    ]


def texture_tool(source: SceneObject, params: TextureParams, seed: int = 0) -> MeshData:
    """Der Werkzeugkörper für Vorschau und Operation, bereits in Weltkoordinaten."""
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.geom.label_ops import label_solid, place
    from app.core.geom.transform import apply, translation

    if params.coverage == "whole_face":
        return _face_texture_tool(source, params, seed)
    pitch = params.pitch
    circumference = math.pi * params.wrap_diameter
    around = params.wrap == "cylinder" and params.width >= circumference - EPS_GEOM
    if params.wrap == "cylinder":
        pitch = wrap_pitch(params.pattern, pitch, params.wrap_diameter, params.width)
    period = pitch * _PERIOD_ALONG_X.get(params.pattern, 1.0)
    shapes = pattern_shapes(
        params.pattern,
        # Umlaufend über mehr als eine Runde gezeichnet und dann je Zelle
        # gewählt (:func:`_one_turn`): So weit über den Umfang hinaus, dass
        # keine gewählte Zelle vom Feldrand angeschnitten ist — ein Steg
        # unter 45 Grad reicht eine halbe Feldhöhe zur Seite.
        circumference + 2.0 * (period + params.height) if around else params.width,
        params.height,
        pitch,
        # Der Startwert kommt aus dem Kontext, nicht aus einem eigenen Feld
        # (Regel 9): der Stapel führt ihn, die Kommandozeile bietet ihn für
        # jede nicht-deterministische Operation ohnehin an, und ein zweiter
        # daneben wäre eine zweite Wahrheit — die CLI hat genau daran
        # gemerkt, dass es einen zu viel gab.
        seed=seed,
    )
    if around:
        shapes = _one_turn(shapes, circumference, period)
    if not shapes:
        raise ValidationError(
            "pattern",
            _("Aus diesem Muster entstand nichts — die Teilung passt nicht ins Feld."),
            value=params.pattern,
            constraint="no_shapes",
        )

    # Um einen Zylinder reicht das Werkzeug um die Sehnenabweichung der
    # Facetten weiter hinein (erhaben) beziehungsweise heraus (vertieft): Die
    # Facetten des Körpers hängen unter dem Radius, und ein Boden bündig mit
    # ihm träfe sie nur an den Ecken — die Vereinigung fände eine Berührung
    # statt einer gemeinsamen Fläche, der Schnitt ließe die Rille an den
    # Enden zu (32 Rillen um ein Rohr, 32 Lufteinschlüsse, 22.09.2026). Die
    # Tiefe selbst bleibt, was verlangt war: Bis zum selben Tag rückte der
    # Boden einer Rille um dieselbe Abweichung hinauf, aus 0,8 mm wurden 0,725.
    clearance = sagitta(params.wrap_diameter, pitch) if params.wrap == "cylinder" else 0.0
    body = label_solid(_merged(shapes), params.depth + BOOLEAN_OVERLAP + clearance)
    if body is None:
        raise ValidationError(
            "pattern",
            _("Aus diesem Muster entstand nichts — die Teilung passt nicht ins Feld."),
            value=params.pattern,
            constraint="no_shapes",
        )

    # Erhaben steht die Tiefe über der Fläche, nur die Überlappung reicht
    # hinein; vertieft andersherum — sonst nähme der Schnitt die Überlappung
    # weg und ließe das Muster als Kratzer zurück.
    lift = -BOOLEAN_OVERLAP - clearance if params.mode == "raised" else -params.depth
    body = apply(body, translation((0.0, 0.0, lift)))
    if params.wrap == "cylinder":
        body = wrapped(body, params.wrap_diameter)
        placed = place(body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz), 0.0)
    else:
        placed = place(
            body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz), params.angle
        )

    return placed


@register_op(
    name="apply_texture",
    result_kind="mesh",
    # 2 seit dem 22.09.2026: Die Noppen der Vorgabe berühren sich nicht mehr
    # (``DIMPLE_FILL``) — dieselben Werte zeichnen ein anderes Bild.
    cache_version="2",
    title=_("Textur aufbringen"),
    category="surface",
    params=TextureParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    touches_features=True,
    deterministic=False,
    doc=_(
        "Prägt ein Muster als echte Geometrie auf eine Fläche — Rändel für den "
        "Griff, Wabe oder Rippe fürs Aussehen. Was der Slicer bekommt, ist das, "
        "was man sieht."
    ),
)
def apply_texture(ctx: OpContext) -> OpResult:
    """Ein Muster auf eine Fläche, erhaben oder vertieft.

    Der Weg ist derselbe wie bei der Beschriftung (§25): Umrisse werden zu
    Prismen, die Prismen auf die Fläche gelegt, und danach entscheidet eine
    Boolesche Operation, ob sie stehen oder fehlen. Was hier dazukommt, ist die
    Frage davor — ob das Muster auf dieser Maschine überhaupt entsteht.
    """
    import dataclasses

    from app.core.geom.boolean import BooleanKind, boolean, without_effect
    from app.core.geom.mesh import as_mesh_data

    params = cast(TextureParams, ctx.params)
    # Um einen Zylinder wird mit der Teilung gezeichnet, die im Umfang aufgeht
    # (``wrap_pitch``) — bis zu einer halben Periode kleiner als verlangt.
    # Geprüft wird die gezeichnete: Bis zum 22.09.2026 fragte die Prüfung die
    # verlangte, und Stege knapp über der Düse kamen knapp darunter heraus.
    drawn_pitch = (
        wrap_pitch(params.pattern, params.pitch, params.wrap_diameter, params.width)
        if params.coverage == "rectangle" and params.wrap == "cylinder"
        else params.pitch
    )
    # §9: das Profil gehört zum Kontext und ist immer da — eine Prüfung darauf
    # wäre eine Frage, deren Antwort der Vertrag schon gibt.
    check_printable(params.pattern, drawn_pitch, params.depth, ctx.profile.printer)

    source = ctx.inputs[0]
    placed = texture_tool(source, params, ctx.seed or 0)

    kind: BooleanKind = "union" if params.mode == "raised" else "difference"
    body_mesh = as_mesh_data(source.mesh)
    outcome = boolean(
        kind,
        [body_mesh, placed],
        quality=ctx.quality,
        cut_slot=0,
        cancelled=ctx.cancelled,
    )

    # Ein Muster, das den Körper nicht erreicht hat, sagt das (§2.7) — dieselbe
    # Auskunft wie bei der Beschriftung, die aus denselben Bausteinen entsteht;
    # der Fix von ``label_text`` hatte den Nachbarn übersehen.
    findings = list(outcome.findings)
    nothing = without_effect(body_mesh, outcome.mesh, kind, ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    apart = _fell_apart(body_mesh, outcome.mesh, params.mode)
    if apart is not None:
        findings.append(apart)
    # Vor der Verzweigung gelesen: Die Drehung wirkt überall außer um einen
    # Zylinder (``texture_tool``), und die Meldung darunter ist ihre einzige
    # Lesestelle in dieser Funktion. Stünde sie allein im Zweig, hielte die
    # Prüfung auf bedingte Felder (``test_a_field_without_effect_says_so``) den
    # Winkel für wirksam **nur** um den Zylinder — das Gegenteil.
    turned = not is_close(params.angle % 360.0, 0.0)
    if params.coverage == "rectangle" and params.wrap == "cylinder":
        if turned:
            findings.append(
                Finding(
                    code="texture.angle_on_wrap",
                    severity="info",
                    message=_(
                        "Die Drehung wirkt nur auf einer Fläche. Um einen Zylinder läuft "
                        "das Muster entlang des Umfangs."
                    ),
                    values={"angle": round(params.angle, 3)},
                )
            )
        beyond = _wrap_beyond_body(body_mesh, params.wrap_diameter)
        if beyond is not None:
            findings.append(beyond)
        pitch = drawn_pitch
        if not is_close(pitch, params.pitch):
            # Gezählt wird entlang des Umfangs: Beim geraden Rändel liegt dort
            # die Diagonale der Teilung (``_PERIOD_ALONG_X``) — quer zu den
            # Stegen gezählt stand bis zum 22.09.2026 „99 Teilungen", wo 70
            # Stege herumlaufen.
            period = pitch * _PERIOD_ALONG_X.get(params.pattern, 1.0)
            findings.append(
                Finding(
                    code="texture.pitch_wrapped",
                    severity="info",
                    message=_(
                        "Die Teilung ist auf {pitch} gerückt, damit das Muster um den Umfang "
                        "aufgeht — {count} Teilungen um Ø {diameter}.",
                        pitch=format_length(pitch),
                        count=round(math.pi * params.wrap_diameter / period),
                        diameter=format_length(params.wrap_diameter),
                    ),
                    values={
                        "pitch_mm": round(pitch, 4),
                        "requested_mm": round(params.pitch, 4),
                        "diameter_mm": round(params.wrap_diameter, 3),
                    },
                )
            )

    _log.info("textured with %r, %s", params.pattern, params.mode)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={})],
        solver=outcome.solver,
        findings=findings,
    )
