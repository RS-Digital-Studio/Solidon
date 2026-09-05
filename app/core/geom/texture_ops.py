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
)
from app.core.units import DEGREE_UNIT, EPS_GEOM
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
    require_positive("pitch", pitch)
    require_positive("width", width)
    require_positive("height", height)
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
    wrap: str = param(
        title=_("Auflegen"),
        default="flat",
        choices=("flat", "cylinder"),
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
        doc=_("Dreht das Muster in der Fläche."),
        depends_on=("wrap", ("flat",)),
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
        message=_(
            "Das Muster hängt nicht am Körper: Es liegt in {loose} losen Stücken "
            "daneben und würde einzeln gedruckt. Meist ist der Durchmesser des "
            "Wickelzylinders veraltet — klicken Sie die Zylinderfläche neu an."
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

    Verbogen wird das fertige Feld, nicht jedes Element einzeln. Die Prismen
    eines Musters sind klein gegen den Umfang, ihre Kanten bleiben also gerade
    genug; ein Element, das über einen nennenswerten Teil des Umfangs liefe,
    wäre kein Muster mehr, sondern ein Bauteil.

    Ein Feld breiter als der Umfang läuft mehrfach herum und überlagert sich
    selbst. Das wird nicht abgeschnitten: die Boolesche Vereinigung danach räumt
    es auf, und eine Abweisung hieße, jemanden zum Rechnen zu zwingen, wo die
    Anwendung es kann.
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
    points = np.asarray(body.raw.vertices, dtype=float)
    theta = points[:, 0] / radius
    reach = radius + points[:, 2]
    turned = np.column_stack((reach * np.cos(theta), reach * np.sin(theta), points[:, 1]))
    return MeshData.of(trimesh.Trimesh(vertices=turned, faces=body.raw.faces, process=False))


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

    from app.core.geom.boolean import BOOLEAN_OVERLAP, BooleanKind, boolean, without_effect
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
    body = label_solid(shapes, params.depth + BOOLEAN_OVERLAP)
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
    lift = -BOOLEAN_OVERLAP if params.mode == "raised" else -params.depth
    if params.wrap == "cylinder":
        # Ein gebogenes Prisma behält seinen **ebenen** Boden: die Sehne unter
        # dem Bogen. In der Mitte des Elements steht der Boden damit über der
        # Zylinderfläche, und die Vereinigung fände dort keine gemeinsame
        # Fläche, sondern eine Berührung. Der Ausgleich ist die
        # Sehnenabweichung selbst.
        lift -= sagitta(params.wrap_diameter, params.pitch)
    body = apply(body, translation((0.0, 0.0, lift)))
    if params.wrap == "cylinder":
        body = wrapped(body, params.wrap_diameter)
        placed = place(body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz), 0.0)
    else:
        placed = place(
            body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz), params.angle
        )

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
    if params.wrap == "cylinder":
        beyond = _wrap_beyond_body(body_mesh, params.wrap_diameter)
        if beyond is not None:
            findings.append(beyond)

    _log.info("textured with %r, %s", params.pattern, params.mode)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={})],
        solver=outcome.solver,
        findings=findings,
    )
