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

from app.core.errors import CORRECT_INPUT, ValidationError
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, OpContext, OpResult, PrinterProfile
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


def _ribs(width: float, height: float, pitch: float, diagonal: float = 0.0) -> list[Any]:
    """Parallele Stege, wahlweise gedreht — die Grundlage von Rippe und Rändel."""
    from shapely import affinity
    from shapely.geometry import box

    land = pitch * LAND_SHARE
    # Über die Diagonale hinaus, damit auch gedreht nichts fehlt.
    reach = math.hypot(width, height)
    columns = np.arange(-reach, reach + pitch, pitch)
    strips = [box(float(x), -reach, float(x) + land, reach) for x in columns]
    if diagonal:
        strips = [affinity.rotate(strip, diagonal, origin=(0.0, 0.0)) for strip in strips]
    return _clip(strips, width, height)


def _waves(width: float, height: float, pitch: float) -> list[Any]:
    """Wellen: sinusförmige Bänder statt flachgedeckelter Stege.

    Der Unterschied zu Rippen ist genau dieser — SindriCAD hatte beide Muster
    getrennt benannt und beide als dasselbe Trapez gezeichnet, bis es jemandem
    auffiel. Hier ist die Welle eine Sinuslinie mit acht Stützstellen je
    Periode, gegen die flachen Prismen der Rippe.
    """
    from shapely.geometry import Polygon

    land = pitch * LAND_SHARE
    amplitude = pitch / 4.0
    steps = np.linspace(-height / 2.0 - pitch, height / 2.0 + pitch, WAVE_STEPS * 8)
    shapes: list[Any] = []
    columns, _rows = _grid_positions(width, height, pitch)
    for centre in columns:
        offsets = amplitude * np.sin(2.0 * math.pi * steps / pitch)
        left = [(float(centre + shift), float(y)) for y, shift in zip(steps, offsets, strict=True)]
        right = [
            (float(centre + shift + land), float(y))
            for y, shift in zip(steps, offsets, strict=True)
        ]
        shapes.append(Polygon([*left, *reversed(right)]))
    return _clip(shapes, width, height)


def _hexagons(width: float, height: float, pitch: float) -> list[Any]:
    """Wabe: versetzte Sechsecke, flache Seite oben."""
    from shapely.geometry import Polygon

    radius = pitch / 2.0 * HEX_FILL
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
                    x + radius * math.cos(math.pi / 6.0 + index * math.pi / 3.0),
                    y + radius * math.sin(math.pi / 6.0 + index * math.pi / 3.0),
                )
                for index in range(6)
            ]
            shapes.append(Polygon(corners))
            x += pitch
        y += step_y
        row += 1
    return _clip(shapes, width, height)


def _diamonds(width: float, height: float, pitch: float) -> list[Any]:
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

    half = pitch / 2.0 * LAND_SHARE * math.sqrt(2.0)
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


def _dimples(width: float, height: float, pitch: float) -> list[Any]:
    """Noppen: runde Erhebungen im Raster, versetzt wie eine Wabe."""
    from shapely.geometry import Point

    radius = pitch / 2.0 * LAND_SHARE * 2.0
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
    pattern: str, width: float, height: float, pitch: float, seed: int = 0
) -> list[Any]:
    """Die Polygone eines Musters, mittig um den Ursprung in der XY-Ebene.

    Die Umrisse sind exakt — sie werden gleich zu Prismen und danach zu einem
    Körper, nicht zu einem Bild.
    """
    if pattern not in PATTERNS:
        raise ValidationError(
            "pattern",
            _("Dieses Muster gibt es nicht."),
            value=pattern,
            constraint="known_pattern",
        )
    if pitch <= 0.0 or width <= 0.0 or height <= 0.0:
        raise ValidationError("pitch", _("Dieses Maß muss größer als null sein."), value=pitch)
    if pattern == "rib":
        return _ribs(width, height, pitch)
    if pattern == "wave":
        return _waves(width, height, pitch)
    if pattern == "knurl_straight":
        return _ribs(width, height, pitch, diagonal=45.0)
    if pattern == "knurl_diamond":
        return _diamonds(width, height, pitch)
    if pattern == "hexagon":
        return _hexagons(width, height, pitch)
    if pattern == "dimple":
        return _dimples(width, height, pitch)
    if pattern == "voronoi":
        return _voronoi(width, height, pitch, seed)
    return _noise(width, height, pitch, seed)


def check_printable(pattern: str, pitch: float, depth: float, printer: PrinterProfile) -> None:
    """Ob dieses Muster auf dieser Maschine überhaupt entsteht (E1).

    Zwei Fragen, beide beantwortbar, ohne etwas zu rechnen:

    * Ist die schmalste Struktur breiter als die Düse? Was schmaler ist, wird
      nicht gedruckt — es verschwindet, und das Teil kommt glatt heraus.
    * Ist die Prägung tiefer als eine Schicht? Was flacher ist, fällt beim
      Runden der Schichthöhe weg.

    Ein Fehler nennt beides Mal, was jetzt möglich ist (Regel 17): die Zahl,
    die passen würde, steht in der Meldung.
    """
    narrowest = pitch * LAND_SHARE
    if narrowest < printer.nozzle_diameter:
        needed = printer.nozzle_diameter / LAND_SHARE
        raise ValidationError(
            "pitch",
            _(
                "Bei dieser Teilung sind die Stege schmaler als die Düse — sie werden "
                "nicht gedruckt. Die Teilung muss mindestens so groß sein wie in "
                "„needed_mm“ angegeben."
            ),
            value=pitch,
            constraint="nozzle_width",
            values={"needed_mm": round(needed, 2), "nozzle_mm": printer.nozzle_diameter},
            suggestions=[replace(CORRECT_INPUT, label=_("Teilung vergrößern"))],
        )
    if depth < printer.layer_height:
        raise ValidationError(
            "depth",
            _(
                "Diese Prägung ist flacher als eine Schicht und verschwindet beim "
                "Drucken. Die Schichthöhe steht in „layer_mm“."
            ),
            value=depth,
            constraint="layer_height",
            values={"layer_mm": printer.layer_height},
            suggestions=[replace(CORRECT_INPUT, label=_("Tiefe vergrößern"))],
        )


# --- die Operation (Bauplan §25, Kategorie „Oberfläche") -------------------------


#: Wie weit die Prägung in den Körper hineinreicht, damit die Vereinigung eine
#: gemeinsame Fläche hat statt einer Berührung. Dieselbe Zahl und derselbe
#: Grund wie bei der Beschriftung.
OVERLAP: Final = 0.05


@op_params
class TextureParams(BaseParams):
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
    )
    height: float = param(
        title=_("Höhe"),
        default=30.0,
        unit="mm",
        minimum=0.5,
        doc=_("Wie hoch das Musterfeld wird. Es sitzt mittig auf dem gewählten Ort."),
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
        doc=_(
            "Erhaben legt das Muster auf die Fläche, vertieft schneidet es hinein. "
            "Ein vertieftes Rändel greift sich anders als ein erhabenes — welches "
            "besser ist, entscheidet die Hand."
        ),
    )
    angle: float = param(
        title=_("Drehung"),
        default=0.0,
        unit="grad",
        minimum=-360.0,
        maximum=360.0,
        placement="advanced",
        doc=_("Dreht das Muster in der Fläche."),
    )
    x: float = param(
        title=_("Position X"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Mitte des Feldes. Eine angeklickte Fläche trägt den Wert selbst ein."),
    )
    y: float = param(
        title=_("Position Y"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Zweite Achse der Position — siehe Position X."),
    )
    z: float = param(
        title=_("Position Z"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Höhe der Fläche, auf die das Muster kommt."),
    )
    nx: float = param(
        title=_("Richtung X"),
        default=0.0,
        placement="advanced",
        doc=_("Normale der Fläche. Aus einer angeklickten Fläche kommt sie mit."),
    )
    ny: float = param(
        title=_("Richtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Zweite Achse der Richtung — siehe Richtung X."),
    )
    nz: float = param(
        title=_("Richtung Z"),
        default=1.0,
        placement="advanced",
        doc=_("Dritte Achse der Richtung. Vorgabe ist nach oben."),
    )


@register_op(
    name="apply_texture",
    title=_("Textur aufbringen"),
    category="surface",
    params=TextureParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
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

    from app.core.geom.boolean import BooleanKind, boolean
    from app.core.geom.label_ops import label_solid, place
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.transform import apply, translation

    params = cast(TextureParams, ctx.params)
    # §9: das Profil gehört zum Kontext und ist immer da — eine Prüfung darauf
    # wäre eine Frage, deren Antwort der Vertrag schon gibt.
    check_printable(params.pattern, params.pitch, params.depth, ctx.profile.printer)

    shapes = pattern_shapes(
        params.pattern,
        params.width,
        params.height,
        params.pitch,
        # Der Startwert kommt aus dem Kontext, nicht aus einem eigenen Feld
        # (Regel 9): der Stapel führt ihn, die Kommandozeile bietet ihn für
        # jede nicht-deterministische Operation ohnehin an, und ein zweiter
        # daneben wäre eine zweite Wahrheit — die CLI hat genau daran
        # gemerkt, dass es einen zu viel gab.
        seed=ctx.seed or 0,
    )
    if not shapes:
        raise ValidationError(
            "pattern",
            _("Aus diesem Muster entstand nichts — die Teilung passt nicht ins Feld."),
            value=params.pattern,
            constraint="no_shapes",
        )

    source = ctx.inputs[0]
    body = label_solid(shapes, params.depth + OVERLAP)
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
    lift = -OVERLAP if params.mode == "raised" else -params.depth
    body = apply(body, translation((0.0, 0.0, lift)))
    placed = place(
        body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz), params.angle
    )

    kind: BooleanKind = "union" if params.mode == "raised" else "difference"
    outcome = boolean(kind, [as_mesh_data(source.mesh), placed], quality=ctx.quality, cut_slot=0)

    _log.info("textured with %r, %s", params.pattern, params.mode)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={})],
        solver=outcome.solver,
        findings=outcome.findings,
    )
