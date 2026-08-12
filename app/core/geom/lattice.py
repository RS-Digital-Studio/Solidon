"""Gitterstrukturen als Füllung im Modell (Konzept P15 §7, Bauplan §25).

Der Slicer füllt mit Gitter, was er für innen hält. Er kennt weder die
Lastrichtung noch die Stelle, an der es dünn sein darf, und seine Füllung
existiert erst im G-Code — sie überlebt keinen Export, keine zweite Maschine
und keinen Slicerwechsel.

Eine Füllung im Modell ist echte Geometrie: sie reist im 3MF mit, sie steht im
Steckbrief als Zahl, und sie ist dieselbe, egal wer sie schneidet. Wer ein Teil
weitergibt, gibt die Füllung mit.

**Kein G-Code-Slicer** (§22.5). Das hier entsteht *vor* dem Slicer und ersetzt
ihn nicht: der Slicer legt weiterhin die Bahnen, er findet nur schon Material
vor, wo sonst sein eigenes Muster hingekommen wäre.

Der Gyroid wird als Isofläche seiner Gleichung gerechnet, Wabe und Würfelgitter
als Prismen — dieselbe Unterscheidung wie bei den Texturen: was eine geschlossene
Formel hat, bekommt sie, und was aus Flächen besteht, wird aus Flächen gebaut.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import replace
from typing import Final, cast

import numpy as np
import trimesh

from app.core.errors import CORRECT_INPUT, ValidationError
from app.core.geom.mesh import MeshData, concatenated
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, OpContext, OpResult, Profile, Vec3
from app.i18n import _

_log = get_logger(__name__)

#: Die Strukturen, die es gibt — ein Auswahlwert, keine drei Menüeinträge (E11).
STRUCTURES: Final[tuple[str, ...]] = ("gyroid", "honeycomb", "cubic")

#: Wie fein das Gitter für den Gyroid abgetastet wird, je Zelle. Zehn Schritte
#: treffen die Fläche gut genug für einen Druck; darüber wächst nur die Datei.
SAMPLES_PER_CELL: Final = 10

#: Wie viele Abtastpunkte eine Achse höchstens bekommt. Ein großer Körper mit
#: feinen Zellen sprengt sonst den Speicher, bevor irgendetwas entsteht.
MAX_SAMPLES: Final = 160


def _gyroid(box: tuple[Vec3, Vec3], cell: float, wall: float) -> MeshData | None:
    """Die Gyroid-Fläche, zu einer Wand aufgedickt.

    ``sin x·cos y + sin y·cos z + sin z·cos x = 0`` ist die Minimalfläche; was
    zwischen ``-t`` und ``+t`` liegt, ist die Wand darum. Sie teilt den Raum in
    zwei Hälften, die beide zusammenhängen — deshalb bleibt beim Drucken nichts
    eingeschlossen, und deshalb ist der Gyroid die Struktur, die Slicer für
    tragende Füllungen anbieten.
    """
    from skimage import measure

    low = np.asarray(box[0], dtype=float)
    high = np.asarray(box[1], dtype=float)
    size = high - low
    counts = np.clip(np.ceil(size / cell * SAMPLES_PER_CELL).astype(int), 4, MAX_SAMPLES)
    axes = [np.linspace(low[axis], high[axis], counts[axis]) for axis in range(3)]
    grid = np.meshgrid(*axes, indexing="ij")
    scale = 2.0 * math.pi / cell
    x, y, z = (value * scale for value in grid)
    field = np.sin(x) * np.cos(y) + np.sin(y) * np.cos(z) + np.sin(z) * np.cos(x)

    # Die Wand ist der Bereich **zwischen** den beiden Isoflächen: alles, wo
    # der Betrag des Feldes unter der Schwelle liegt. Als ``|field| - level``
    # geschrieben ist ihre Oberfläche wieder eine einzige Isofläche bei null —
    # und damit ein geschlossenes Volumen.
    #
    # Der erste Versuch nahm die beiden Flächen bei ``+level`` und ``-level``
    # einzeln und legte sie zusammen. Das sind zwei offene Flächen, kein
    # Körper; die Boolesche Operation fiel auf die Voxelstufe zurück, und der
    # Kasten wurde von außen 40,18 statt 40 Millimeter groß.
    level = wall * scale / 2.0
    step = tuple(float(size[axis] / max(counts[axis] - 1, 1)) for axis in range(3))

    # **Der Rand muss zu sein.** Marching Cubes zeichnet nur, wo das Feld sein
    # Vorzeichen wechselt; am Rand des Abtastgitters endet die Fläche einfach,
    # und das Ergebnis ist offen. Ein offenes Netz fällt in der Booleschen
    # Rückfallkette bis auf die Voxelstufe durch, und die machte den Kasten von
    # außen 40,18 statt 40 Millimeter groß.
    #
    # Eine Lage „außen“ ringsherum schließt es: dort ist der Wert positiv, das
    # Vorzeichen wechselt, und die Fläche macht den Deckel selbst.
    walled = np.pad(np.abs(field) - level, 1, constant_values=abs(level) + 1.0)
    try:
        points, faces, _normals, _values = measure.marching_cubes(walled, 0.0, spacing=step)
    except (ValueError, RuntimeError):
        return None
    # Die Polsterung verschiebt den Ursprung um einen Schritt je Achse zurück.
    origin = low - np.asarray(step, dtype=float)
    built = trimesh.Trimesh(vertices=points + origin, faces=faces, process=True)
    built.fix_normals()
    return MeshData.of(built)


def _honeycomb(box: tuple[Vec3, Vec3], cell: float, wall: float) -> MeshData | None:
    """Sechseckige Zellen, senkrecht durchgehend — die klassische Wabe.

    Sie trägt in der Ebene ihrer Zellen am besten und ist quer dazu weich; wer
    eine Platte aussteift, nimmt sie, wer einen Klotz füllt, den Gyroid.
    """
    from shapely.geometry import Polygon
    from shapely.geometry import box as shapely_box
    from shapely.ops import unary_union

    low = np.asarray(box[0], dtype=float)
    high = np.asarray(box[1], dtype=float)
    radius = cell / 2.0
    step_y = cell * math.sqrt(3.0) / 2.0
    rings = []
    row = 0
    y = low[1] - cell
    while y <= high[1] + cell:
        offset = (cell / 2.0) if row % 2 else 0.0
        x = low[0] - cell + offset
        while x <= high[0] + cell:
            corners = [
                (
                    x + radius * math.cos(math.pi / 6.0 + index * math.pi / 3.0),
                    y + radius * math.sin(math.pi / 6.0 + index * math.pi / 3.0),
                )
                for index in range(6)
            ]
            cellwall = Polygon(corners).buffer(0).difference(Polygon(corners).buffer(-wall))
            if not cellwall.is_empty and cellwall.area > 0.0:
                rings.append(cellwall)
            x += cell
        y += step_y
        row += 1
    if not rings:
        return None
    # Auf den Bereich beschneiden: gebaut wird eine Zelle über den Rand hinaus,
    # damit am Rand keine halbe Zelle fehlt — stehen bleiben darf sie nicht.
    # Ohne diesen Schnitt füllte die Wabe 133 % ihres eigenen Quaders, und eine
    # Füllung dichter als ein Vollkörper ist keine.
    field = shapely_box(float(low[0]), float(low[1]), float(high[0]), float(high[1]))
    joined = unary_union(rings).intersection(field)
    shapes = list(getattr(joined, "geoms", [joined]))
    height = float(high[2] - low[2])
    parts = [
        trimesh.creation.extrude_polygon(shape, height=height)
        for shape in shapes
        if shape.geom_type == "Polygon" and shape.area > 0.0
    ]
    if not parts:
        return None
    body = concatenated(parts)
    body.apply_translation((0.0, 0.0, float(low[2])))
    return MeshData.of(body)


def _cubic(box: tuple[Vec3, Vec3], cell: float, wall: float) -> MeshData | None:
    """Ein Würfelgitter aus Stäben entlang der drei Achsen.

    Die einfachste Struktur, und die einzige, die in allen drei Richtungen
    gleich trägt. Sie ist steifer als die Wabe und schwerer als der Gyroid.
    """
    low = np.asarray(box[0], dtype=float)
    high = np.asarray(box[1], dtype=float)
    size = high - low
    bars = []
    for axis in range(3):
        first, second = [other for other in range(3) if other != axis]
        for offset_a in np.arange(low[first], high[first] + cell, cell):
            for offset_b in np.arange(low[second], high[second] + cell, cell):
                extents = [wall, wall, wall]
                extents[axis] = float(size[axis])
                centre = [0.0, 0.0, 0.0]
                centre[axis] = float((low[axis] + high[axis]) / 2.0)
                centre[first] = float(offset_a)
                centre[second] = float(offset_b)
                bars.append(trimesh.creation.box(extents=extents).apply_translation(centre))
    if not bars:
        return None
    return MeshData.of(concatenated(bars))


def build(structure: str, box: tuple[Vec3, Vec3], cell: float, wall: float) -> MeshData | None:
    """Die Füllung für einen Quader, mittig darin.

    Gibt ``None`` zurück, wenn nichts entsteht — bei einem Bereich, der kleiner
    ist als eine Zelle, ist das kein Fehler, sondern die Antwort.
    """
    if structure not in STRUCTURES:
        raise ValidationError(
            "structure",
            _("Diese Struktur gibt es nicht."),
            value=structure,
            constraint="known_structure",
        )
    if cell <= 0.0 or wall <= 0.0:
        raise ValidationError("cell", _("Dieses Maß muss größer als null sein."), value=cell)
    if structure == "gyroid":
        return _gyroid(box, cell, wall)
    if structure == "honeycomb":
        return _honeycomb(box, cell, wall)
    return _cubic(box, cell, wall)


def check_printable(wall: float, cell: float, profile: Profile) -> None:
    """Ob diese Füllung auf dieser Maschine entsteht (E1).

    Zwei Fragen, beide ohne Rechnung zu beantworten: ist der Steg breit genug,
    um gedruckt zu werden, und bleibt zwischen den Stegen noch ein Hohlraum.
    Eine Füllung, deren Stege so dick sind wie ihre Zellen, ist ein Vollkörper
    mit mehr Dreiecken.
    """
    minimum = profile.minimum_wall_thickness
    if wall < minimum:
        raise ValidationError(
            "wall",
            _(
                "Diese Stege sind dünner als zwei Extrusionsbahnen und werden nicht "
                "gedruckt. Was hier mindestens nötig ist, steht in „minimum_mm“."
            ),
            value=wall,
            constraint="minimum_wall",
            values={"minimum_mm": round(minimum, 2)},
            suggestions=[replace(CORRECT_INPUT, label=_("Stege verstärken"))],
        )
    if wall >= cell * 0.5:
        raise ValidationError(
            "cell",
            _(
                "Die Stege sind mindestens halb so dick wie ihre Zelle — daraus wird "
                "ein Vollkörper mit mehr Dreiecken statt einer Füllung."
            ),
            value=cell,
            constraint="cell_size",
            suggestions=[replace(CORRECT_INPUT, label=_("Zelle vergrößern"))],
        )


# --- die Operation (Bauplan §25, Kategorie „Oberfläche") -------------------------


@op_params
class LatticeParams(BaseParams):
    structure: str = param(
        title=_("Struktur"),
        default="gyroid",
        choices=STRUCTURES,
        doc=_(
            "Gyroid trägt in alle Richtungen und schließt nichts ein, die Wabe "
            "steift eine Platte aus, das Würfelgitter ist am steifsten und am "
            "schwersten."
        ),
    )
    cell: float = param(
        title=_("Zellgröße"),
        default=8.0,
        unit="mm",
        minimum=1.0,
        doc=_("Von Zelle zu Zelle. Kleiner heißt mehr Stege und mehr Material."),
    )
    wall: float = param(
        title=_("Stegstärke"),
        default=1.0,
        unit="mm",
        minimum=0.1,
        doc=_(
            "Wie dick die Stege werden. Unter zwei Extrusionsbahnen druckt sie "
            "die Maschine nicht — dann sagt die Operation es, statt es zu "
            "versuchen."
        ),
    )


@register_op(
    name="lattice_fill",
    title=_("Gitter füllen"),
    category="surface",
    params=LatticeParams,
    consumes=1,
    produces=1,
    doc=_(
        "Füllt den Hohlraum eines ausgehöhlten Körpers mit einer Gitterstruktur "
        "als echte Geometrie. Sie reist im 3MF mit und ist dieselbe, egal wer "
        "das Teil schneidet."
    ),
    caveat=_(
        "Nicht für Teile, die dicht sein müssen: Ein Gitter hat Hohlräume, und Wasser "
        "findet sie. Für tragende Teile erst die Wandstärke erhöhen — eine Füllung "
        "ersetzt keine Wand."
    ),
)
def lattice_fill(ctx: OpContext) -> OpResult:
    """Die Füllung in den Hohlraum legen.

    Der Hohlraum ist, was zwischen der Außenhaut und dem Vollkörper darüber
    fehlt: gerechnet als Differenz aus der konvexen Hülle des Körpers und dem
    Körper selbst — nein, einfacher und richtiger: die Struktur wird über den
    ganzen Hüllquader gebaut und dann mit dem Körper verschnitten. Was im
    Material liegt, verschwindet in der Vereinigung; was im Hohlraum liegt,
    bleibt und trägt.
    """
    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import as_mesh_data

    params = cast(LatticeParams, ctx.params)
    check_printable(params.wall, params.cell, ctx.profile)

    source = ctx.inputs[0]
    body = as_mesh_data(source.mesh)
    cavity = _cavity_bounds(body)
    if cavity is None:
        raise ValidationError(
            "structure",
            _(
                "Dieser Körper hat keinen Hohlraum — eine Füllung hätte keinen Platz. "
                "Erst aushöhlen, dann füllen."
            ),
            value=params.structure,
            constraint="no_cavity",
            suggestions=[replace(CORRECT_INPUT, label=_("Erst aushöhlen"))],
        )

    grid = build(params.structure, cavity, params.cell, params.wall)
    if grid is None:
        raise ValidationError(
            "cell",
            _("Der Hohlraum ist kleiner als eine Zelle — daraus entsteht keine Füllung."),
            value=params.cell,
            constraint="cavity_too_small",
            suggestions=[replace(CORRECT_INPUT, label=_("Zelle verkleinern"))],
        )

    # Erst auf den Hohlraum beschneiden, dann anfügen: eine Struktur, die durch
    # die Außenwand stößt, wäre außen sichtbar und innen unbrauchbar.
    inside = boolean("intersection", [grid, _inner(body)], quality=ctx.quality, allow_empty=True)
    if inside.mesh.triangle_count == 0:
        raise ValidationError(
            "cell",
            _("Der Hohlraum ist kleiner als eine Zelle — daraus entsteht keine Füllung."),
            value=params.cell,
            constraint="cavity_too_small",
            suggestions=[replace(CORRECT_INPUT, label=_("Zelle verkleinern"))],
        )
    filled = boolean("union", [body, inside.mesh], quality=ctx.quality)

    _log.info("filled with %r, cell %.1f", params.structure, params.cell)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=filled.mesh, features={})],
        solver=filled.solver,
        findings=[
            Finding(
                code="lattice.filled",
                severity="info",
                message=_("Der Hohlraum trägt jetzt eine Gitterstruktur."),
            )
        ],
    )


def _cavity_bounds(body: MeshData) -> tuple[Vec3, Vec3] | None:
    """Der Hüllquader des Hohlraums, oder ``None`` bei einem Vollkörper.

    Ein Vollkörper hat genau eine Schale; ein ausgehöhlter hat zwei, und die
    innere ist der Hohlraum. ``trimesh`` trennt sie über die zusammenhängenden
    Teile der Oberfläche — die innere Schale ist die, die ganz in der äußeren
    liegt.
    """
    parts = body.raw.split(only_watertight=False)
    if len(parts) < 2:
        return None
    outer = max(parts, key=lambda part: float(np.prod(part.extents)))
    inner = [part for part in parts if part is not outer]
    if not inner:
        return None
    low = np.min([part.bounds[0] for part in inner], axis=0)
    high = np.max([part.bounds[1] for part in inner], axis=0)
    return (
        (float(low[0]), float(low[1]), float(low[2])),
        (float(high[0]), float(high[1]), float(high[2])),
    )


def _inner(body: MeshData) -> MeshData:
    """Der Hohlraum als Körper — das, was beim Aushöhlen herausgenommen wurde."""
    parts = body.raw.split(only_watertight=False)
    outer = max(parts, key=lambda part: float(np.prod(part.extents)))
    inner = [part for part in parts if part is not outer]
    joined = concatenated(inner)
    joined.fix_normals()
    return body.replacing(joined)
