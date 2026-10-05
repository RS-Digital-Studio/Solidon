"""Ein Konturdeckel mit Scharnier oder Stift (RM-184, Dateiaudit §6).

*Deckel erzeugen* nimmt die Kontur der Öffnung, wie sie ist — rund, eckig,
geteilt. Was das Audit am Klappdeckel für ein Three-Sixty-Glas zeigte, war der
zweite Schritt, den bisher jeder von Hand machte: eine Achse an einer Seite,
zwei Hälften darum und ein Kragen, der beim Aufklappen nicht an der Wand
hängen bleibt. Hier stehen die drei Dinge, die *Deckel erzeugen* dafür
zusätzlich rechnet; gebaut wird mit den Scharnieren der Bibliothek
(``barrel_hinge``, ``hinge_eye``), nicht mit einer neuen Grundform.

* **Die Lage** (:func:`layout`): Die Achse liegt parallel zur gewählten Seite
  der Öffnung, um das halbe Spiel neben der Außenwand und um das halbe Spiel
  über dem Rand — so berührt weder der Deckel die Augen am Gehäuse noch umgekehrt.
* **Der Kragen** (:func:`collar_keeps`): Ein Punkt des Deckels läuft beim
  Öffnen auf einem Kreis um die Achse. Die Oberkante der Gegenwand liegt im
  Abstand ``√(W² + a²)`` von ihr (``W`` waagerecht, ``a`` die Höhe der Achse
  über dem Rand); was vom Kragen weiter draußen liegt, träfe sie. Der Kragen
  bleibt deshalb innerhalb dieses Radius, abschnittsweise längs der Achse, denn
  bei einer runden Öffnung rückt die Gegenwand zu den Enden hin näher.
* **Die Augen** (:func:`hinge_parts`): mitgedruckt die beiden Hälften des
  Bolzenscharniers, sonst drei Augen — zwei am Gehäuse, eines am Deckel — mit
  einer Bohrung für einen Stift, den *Stift für Bohrung* dazu baut.

Gerechnet wird in einem Rahmen, in dem die Öffnung nach oben und die
Scharnierseite nach +y zeigt; :func:`spin_of` dreht dorthin, um ganze
Vierteldrehungen, damit kein Rundungsfehler entsteht.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from itertools import pairwise
from typing import Any, Final, cast

import numpy as np

from app.core.errors import CANCEL, CHANGE_SELECTION, CORRECT_INPUT, GeometryError, ValidationError
from app.core.geom import transform
from app.core.geom.mesh import MeshData
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, pin
from app.core.knowledge.parts.mechanics import (
    BarrelHingeParams,
    HingeEyeParams,
    barrel_hinge,
    hinge_eye,
)
from app.core.knowledge.profiles import for_object
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.registry.params import ZERO_AUTOMATIC, ZERO_FROM_PROFILE, validate
from app.core.types import (
    BaseParams,
    CancelToken,
    Feature,
    Finding,
    OpContext,
    OpResult,
    SceneObject,
    Vec3,
)
from app.core.units import EPS_GEOM
from app.i18n import _

#: Die Arten: kein Scharnier, ein mitgedrucktes Bolzenscharnier, drei Augen mit Stift.
HINGES: Final = ("none", "barrel", "loose_pin")

#: Die Seite der Öffnung, an der die Achse liegt — im aufgerichteten Rahmen:
#: hinten ist +y, rechts +x.
HINGE_SIDES: Final = ("hinge_back", "hinge_front", "hinge_left", "hinge_right")

#: Um wie viel Grad um Z gedreht wird, damit die Scharnierseite nach +y zeigt.
_SPIN: Final = {
    "hinge_back": 0.0,
    "hinge_right": 90.0,
    "hinge_front": 180.0,
    "hinge_left": -90.0,
}

#: Die Merkmale, an denen die Passung des Scharniers hängt; dieselben Namen wie
#: am Klappdeckel des Behälters, denn es ist dieselbe Sache.
HINGE_PIN_FEATURE: Final = "lid_hinge_pin"
HINGE_HOLE_FEATURE: Final = "lid_hinge_hole"

#: Das Merkmal am Stift, den *Stift für Bohrung* baut.
BORE_PIN_FEATURE: Final = "bore_pin"

#: In wie viele Abschnitte längs der Achse der Kragen beschnitten wird. Je
#: Abschnitt gilt der engste Abstand zur Gegenwand; mehr Abschnitte lassen an
#: einer runden Öffnung mehr Kragen stehen, kosten aber Stufen im Werkzeug.
KEEP_STATIONS: Final = 24

#: Auf welches Raster die Radien des Kragenraums abgerundet werden — unter
#: jeder Druckauflösung, und abgerundet heißt: nie näher an der Wand.
KEEP_GRID: Final = 0.05

_X: Final[Vec3] = (1.0, 0.0, 0.0)
_Z: Final[Vec3] = (0.0, 0.0, 1.0)


def spin_of(side: str) -> float:
    """Der Winkel um Z, der diese Seite nach +y dreht."""
    return _SPIN[side]


def spun(geometry: Any, degrees: float) -> Any:
    """Eine shapely-Geometrie um den Ursprung gedreht — um ganze Vierteldrehungen exakt."""
    from shapely import affinity

    quarter = round(degrees / 90.0) % 4
    cosine, sine = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[quarter]
    return affinity.affine_transform(geometry, [cosine, -sine, sine, cosine, 0.0, 0.0])


@dataclasses.dataclass(frozen=True, slots=True)
class HingeLayout:
    """Wo das Scharnier im Scharnierrahmen liegt und wie groß es ist."""

    centre_x: float
    """Die Mitte des Scharniers längs der Achse."""
    axis_y: float
    axis_z: float
    radius: float
    """Außenradius der Augen: halber Stift, halbes Spiel, Wand."""
    gap: float
    """Halbes Spiel aus dem Materialprofil — radial wie axial."""
    width: float
    """Gesamtbreite über alle Augen."""
    reach: float
    """Wie weit eine Lasche von der Achse zum Teil reicht."""
    rim: float
    """Die Höhe des Rands, auf dem der Deckel liegt."""
    wall_from: float
    """Wo die Lasche am Gehäuse beginnt: die Hohlraumkante an dieser Seite."""

    @property
    def axis(self) -> Vec3:
        return (self.centre_x, self.axis_y, self.axis_z)


def layout(
    outline: Any,
    cavities: Sequence[Any],
    *,
    z: float,
    bottom: float,
    width: float,
    pin_diameter: float,
    wall: float,
    clearance: float,
) -> HingeLayout:
    """Die Lage der Achse an der +y-Seite der Öffnung, oder die Absage, warum nicht.

    ``outline`` und ``cavities`` sind Umriss und Hohlräume am Rand, schon im
    Scharnierrahmen; ``bottom`` ist die Unterkante des Gehäuses.
    """
    from shapely.geometry import box as shapely_box
    from shapely.ops import unary_union

    gap = clearance / 2.0
    radius = pin_diameter / 2.0 + gap + wall
    low_x, _low_y, high_x, _high_y = outline.bounds
    edge = high_x - low_x
    if width > edge + EPS_GEOM:
        raise ValidationError(
            field="hinge_width",
            detail=_(
                "Das Scharnier ist breiter als diese Seite der Öffnung. Verringern Sie "
                "die Scharnierbreite oder wählen Sie eine längere Seite."
            ),
            values={"width": width, "edge": round(edge, 3)},
            constraint="hinge_width",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    centre_x = (low_x + high_x) / 2.0
    slab = shapely_box(centre_x - width / 2.0, -1e6, centre_x + width / 2.0, 1e6)
    edge_y = outline.intersection(slab).bounds[3]
    holes = unary_union(list(cavities)).intersection(slab)
    wall_from = holes.bounds[3] if not holes.is_empty else edge_y - wall
    reach = 2.0 * radius + gap
    hanging = reach - radius - gap
    if z - hanging < bottom - EPS_GEOM:
        raise ValidationError(
            field="hinge_pin",
            detail=_(
                "Das Gehäuse ist zu niedrig für Augen dieser Größe. Nehmen Sie einen "
                "dünneren Stift oder eine dünnere Scharnierwand."
            ),
            values={"height": round(z - bottom, 3), "needed": round(hanging, 3)},
            constraint="hinge_size",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return HingeLayout(
        centre_x=centre_x,
        axis_y=edge_y + radius + gap,
        axis_z=z + radius + gap,
        radius=radius,
        gap=gap,
        width=width,
        reach=reach,
        rim=z,
        wall_from=wall_from,
    )


def _lowest_y(polygon: Any, x: float) -> float | None:
    """Die unterste Stelle des Polygons auf der Senkrechten bei ``x`` — die Gegenwand."""
    from shapely.geometry import LineString

    low_y, high_y = polygon.bounds[1], polygon.bounds[3]
    cut = polygon.intersection(LineString([(x, low_y - 1.0), (x, high_y + 1.0)]))
    return None if cut.is_empty else float(cut.bounds[1])


def keep_profile(footprint: Any, hinge: HingeLayout) -> list[tuple[float, float]]:
    """Der Umriss des Raums, in dem ein Kragen beim Öffnen frei bleibt — (Radius, Lage längs X).

    Je Abschnitt der Achse der kleinste Radius bis zur Oberkante der
    Gegenwand, abzüglich des halben Spiels. Gemessen an den Abschnittsenden
    und an jeder Ecke des Grundrisses dazwischen, denn dort ist die Wand am
    nächsten.
    """
    low_x, _low_y, high_x, _high_y = footprint.bounds
    rise = hinge.axis_z - hinge.rim
    corners = sorted({float(x) for x, _y in footprint.exterior.coords})
    stations = [
        low_x + (high_x - low_x) * index / KEEP_STATIONS for index in range(KEEP_STATIONS + 1)
    ]
    radii: list[float] = []
    for start, end in pairwise(stations):
        probes = [start, end, *(x for x in corners if start < x < end)]
        walls = [y for y in (_lowest_y(footprint, x) for x in probes) if y is not None]
        if not walls:
            radii.append(radii[-1] if radii else hinge.axis_y - low_x)
            continue
        across = hinge.axis_y - max(walls)
        reach = math.sqrt(across * across + rise * rise) - hinge.gap
        # Abgerundet auf ein Raster: Zwei Nachbarn, die sich nur in der
        # letzten Stelle unterscheiden, gäben eine Stufe ohne Höhe, an der der
        # exakte Schnitt mit dem Kragen leer ausging (gemessen am runden Glas).
        radii.append(max(math.floor(reach / KEEP_GRID) * KEEP_GRID, KEEP_GRID))
    outline: list[tuple[float, float]] = [(0.0, stations[0] - 1.0)]
    for index, radius in enumerate(radii):
        begin = stations[0] - 1.0 if index == 0 else stations[index]
        if outline[-1][0] != radius:
            outline.append((radius, begin))
        if index == len(radii) - 1:
            outline.append((radius, stations[-1] + 1.0))
        elif radii[index + 1] != radius:
            outline.append((radius, stations[index + 1]))
    outline.append((0.0, stations[-1] + 1.0))
    return outline


def collar_keep(footprint: Any, hinge: HingeLayout) -> shapes.Form:
    """Der Drehkörper um die Achse, mit dem ein Kragen geschnitten wird — im aktuellen Kern."""
    body = shapes.revolved(keep_profile(footprint, hinge))
    body = shapes.turned(body, 90.0, (0.0, 1.0, 0.0))
    return shapes.moved(body, (0.0, hinge.axis_y, hinge.axis_z))


def barrel_halves(
    pin_diameter: float,
    width: float,
    reach: float,
    wall: float,
    gap: float,
    *,
    cancelled: CancelToken | None = None,
) -> list[shapes.Form]:
    """Die zwei Hälften des Bolzenscharniers aus der Bibliothek, nach X sortiert.

    Links die mit dem angeformten Bolzen, rechts die mit der Bohrung — so
    teilen sie der Klappdeckel des Behälters und der Konturdeckel.
    """
    hinge = barrel_hinge(
        validate(
            BarrelHingeParams,
            {"pin": pin_diameter, "width": width, "reach": reach, "wall": wall, "play": gap},
        )
    ).mesh
    halves: list[shapes.Form]
    if isinstance(hinge, MeshData):
        halves = [MeshData.of(part) for part in hinge.raw.split(only_watertight=False)]
    else:
        from app.core.brep.edit import separated_solids
        from app.core.brep.kernel import Solid

        if not isinstance(hinge, Solid):
            raise TypeError("a constructed hinge must be a mesh or an exact solid")
        halves = [part for part, _faces in separated_solids(hinge, cancelled=cancelled)]
    if len(halves) != 2:
        raise GeometryError(
            detail=_(
                "Das Scharnier besteht nicht aus zwei getrennten Teilen. "
                "Prüfen Sie das Materialspiel."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    halves.sort(key=lambda form: form.bounds.minimum[0])
    return halves


def _hanging(eye: shapes.Form, hinge: HingeLayout, x: float) -> shapes.Form:
    """Ein Auge mit Lasche, die vom Rand nach unten am Gehäuse hängt."""
    eye = shapes.moved(eye, (0.0, -hinge.reach, -hinge.radius))
    eye = shapes.turned(eye, 90.0, _X)
    return shapes.moved(eye, (x, hinge.axis_y, hinge.axis_z))


def _lying(eye: shapes.Form, hinge: HingeLayout, x: float) -> shapes.Form:
    """Ein Auge mit Lasche, die waagerecht über den Rand in den Deckel reicht."""
    return shapes.moved(eye, (x, hinge.axis_y - hinge.reach, hinge.axis_z - hinge.radius))


def _tab(hinge: HingeLayout, x: float, width: float) -> shapes.Form:
    """Der Steg unter einem Gehäuseauge: von der Hohlraumkante bis hinter die Achse."""
    height = hinge.reach - hinge.radius - hinge.gap
    depth = hinge.axis_y + hinge.radius - hinge.wall_from
    block = shapes.box(width, depth, height)
    return shapes.moved(block, (x, hinge.wall_from + depth / 2.0, hinge.rim - height))


def hinge_parts(
    kind: str,
    hinge: HingeLayout,
    *,
    pin_diameter: float,
    wall: float,
    clearance: float,
    cancelled: CancelToken | None = None,
) -> tuple[list[shapes.Form], list[shapes.Form]]:
    """Was ans Gehäuse und was an den Deckel kommt, im Scharnierrahmen.

    Gebaut im Kern, den der Aufrufer mit ``shapes.building`` gewählt hat.
    """
    if kind == "barrel":
        left, right = barrel_halves(
            pin_diameter, hinge.width, hinge.reach, wall, hinge.gap, cancelled=cancelled
        )
        half = (hinge.width - hinge.gap) / 2.0
        housing_x = hinge.centre_x - (hinge.width - half) / 2.0
        return (
            [_hanging(left, hinge, hinge.centre_x), _tab(hinge, housing_x, half)],
            [_lying(right, hinge, hinge.centre_x)],
        )
    knuckle = (hinge.width - 2.0 * hinge.gap) / 3.0
    eye = hinge_eye(
        validate(
            HingeEyeParams,
            {
                "pin": pin_diameter,
                "width": knuckle,
                "reach": hinge.reach,
                "wall": wall,
                "play": clearance,
            },
        )
    ).mesh
    eye = cast(shapes.Form, eye)
    step = knuckle + hinge.gap
    housing: list[shapes.Form] = []
    for x in (hinge.centre_x - step, hinge.centre_x + step):
        housing.extend((_hanging(eye, hinge, x), _tab(hinge, x, knuckle)))
    return housing, [_lying(eye, hinge, hinge.centre_x)]


def hinge_features(
    kind: str, hinge: HingeLayout, *, pin_diameter: float, clearance: float
) -> tuple[dict[str, Feature], dict[str, Feature]]:
    """Die benannten Merkmale an Gehäuse und Deckel, im Scharnierrahmen.

    Mitgedruckt trägt das Gehäuse den Bolzen und der Deckel die Bohrung darum,
    wie am Klappdeckel des Behälters. Mit Stift trägt der Deckel die Bohrung,
    und ``span`` sagt *Stift für Bohrung*, wie lang der Stift über alle drei
    Augen wird.
    """
    if kind == "barrel":
        half = (hinge.width - hinge.gap) / 2.0
        return (
            dict([pin(HINGE_PIN_FEATURE, pin_diameter, hinge.axis, length=hinge.width, axis=_X)]),
            dict(
                [
                    bore(
                        HINGE_HOLE_FEATURE,
                        pin_diameter + clearance,
                        hinge.axis,
                        depth=half,
                        axis=_X,
                        through=True,
                    )
                ]
            ),
        )
    knuckle = (hinge.width - 2.0 * hinge.gap) / 3.0
    key, hole = bore(
        HINGE_HOLE_FEATURE,
        pin_diameter + clearance,
        hinge.axis,
        depth=knuckle,
        axis=_X,
        through=True,
    )
    hole = dataclasses.replace(hole, params={**hole.params, "span": hinge.width})
    return {}, {key: hole}


# --- Stift für Bohrung ------------------------------------------------------------


@op_params
class PinForBoreParams(BaseParams):
    at_feature: str = param(
        title=_("Bohrung"),
        kind="feature",
        default="",
        feature_kinds=("hole",),
        doc=_("Die Bohrung, in die der Stift kommt — am Klappdeckel die Bohrung des Scharniers."),
    )
    length: float = param(
        title=_("Länge"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=500.0,
        doc=_("Null nimmt die Länge der Bohrung, am Scharnier die Breite über alle Augen."),
        zero_text=ZERO_AUTOMATIC,
    )
    clearance: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_(
            "Um so viel ist der Stift dünner als die Bohrung. "
            "Null heißt: der Wert aus dem Materialprofil."
        ),
        zero_text=ZERO_FROM_PROFILE,
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)


def _hole_of(source: SceneObject, name: str) -> Feature:
    """Die Bohrung, in die der Stift soll — oder die Absage, warum es keine ist."""
    feature = source.features.get(name)
    if feature is None or feature.kind != "hole":
        raise ValidationError(
            field="at_feature",
            detail=_("Ein Stift braucht eine Bohrung. Wählen Sie eine Bohrung an diesem Teil."),
            value=name,
            constraint="not_a_hole",
            values={"known": ", ".join(sorted(source.features))},
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    return feature


def _along(body: shapes.Form, axis: Vec3, centre: Vec3) -> shapes.Form:
    """Einen entlang Z gebauten, um null zentrierten Körper auf die Achse durch ``centre`` legen."""
    direction = np.asarray(axis, dtype=float)
    index = int(np.argmax(np.abs(direction)))
    aligned = abs(abs(float(direction[index])) - 1.0) <= EPS_GEOM
    if aligned and index == 2:
        turned = body if direction[2] > 0.0 else shapes.turned(body, 180.0, _X)
    elif aligned:
        # Achsparallel um ganze Vierteldrehungen, ohne Rundungsfehler.
        degrees = 90.0 if direction[index] > 0.0 else -90.0
        turned = shapes.turned(body, degrees, (0.0, 1.0, 0.0) if index == 0 else (-1.0, 0.0, 0.0))
    else:
        matrix = transform.rotation_between(_Z, (axis[0], axis[1], axis[2]))
        if isinstance(body, MeshData):
            turned = transform.apply(body, np.asarray(matrix, dtype=float))
        else:
            from app.core.brep import edit

            rows = cast(Any, tuple(tuple(float(v) for v in row) for row in matrix))
            turned = edit.transformed(cast(Any, body), rows)
    return shapes.moved(turned, centre)


@register_op(
    name="pin_for_bore",
    title=_("Stift für Bohrung"),
    category="holes",
    params=PinForBoreParams,
    consumes=1,
    produces=2,
    keeps_inputs=1,
    applies_to=["hole"],
    doc=_(
        "Baut einen losen Stift, der in diese Bohrung passt: dünner um das Spiel aus "
        "dem Materialprofil, so lang wie die Bohrung. Am Klappdeckel mit Stift ist "
        "es die Achse durch alle drei Augen."
    ),
)
def pin_for_bore(ctx: OpContext) -> OpResult:
    """Ein Stift als eigener Körper, in der Bohrung stehend (RM-184, Audit §6).

    Der Stift hängt am Merkmal, nicht an Zahlen: Ändert sich der Deckelschritt
    (Breite, Stiftmaß), folgt der Stift beim nächsten Rechnen.
    """
    params = cast(PinForBoreParams, ctx.params)
    source = ctx.inputs[0]
    hole = _hole_of(source, params.at_feature)
    clearance = params.clearance or for_object(ctx.profile, source).material.clearance
    diameter = float(hole.params.get("diameter", 0.0)) - clearance
    length = params.length or float(
        hole.params.get("span", 0.0) or hole.params.get("depth", 0.0) or 0.0
    )
    if diameter <= EPS_GEOM:
        raise ValidationError(
            field="clearance",
            detail=_("Das Spiel ist so groß wie die Bohrung. Verringern Sie das Spiel."),
            values={"bore": hole.params.get("diameter"), "clearance": clearance},
            constraint="positive",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if length <= EPS_GEOM:
        raise ValidationError(
            field="length",
            detail=_("Die Bohrung nennt keine Länge. Tragen Sie die Länge des Stifts ein."),
            values={"feature": hole.id},
            constraint="positive",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    centre = tuple(float(value) for value in hole.params["centre"])
    axis = tuple(float(value) for value in hole.params.get("axis", _Z))
    with shapes.building(cast(Any, "brep" if source.kind == "brep" else "mesh")):
        body = shapes.moved(shapes.cylinder(diameter, length), (0.0, 0.0, -length / 2.0))
        body = _along(body, (axis[0], axis[1], axis[2]), (centre[0], centre[1], centre[2]))
    features = dict(
        [
            pin(
                BORE_PIN_FEATURE,
                diameter,
                (centre[0], centre[1], centre[2]),
                length=length,
                axis=(axis[0], axis[1], axis[2]),
            )
        ]
    )
    if source.kind == "brep":
        from app.core.brep.features import features_of

        features = {**features_of(cast(Any, body), cancelled=ctx.cancelled), **features}
    return OpResult(
        outputs=[
            source,
            SceneObject(
                id="",
                name=params.name or _("Stift"),
                mesh=body,
                kind=source.kind,
                material=source.material,
                features=features,
            ),
        ],
        findings=[
            Finding(
                code="pin_for_bore.made",
                severity="info",
                message=_(
                    "Der Stift ist {diameter} dick, {length} lang und steht noch in der Bohrung. "
                    "„Auf dem Bett anordnen“ legt ihn ab.",
                    diameter=_format(diameter),
                    length=_format(length),
                ),
                values={"diameter_mm": round(diameter, 3), "length_mm": round(length, 3)},
            )
        ],
    )


def _format(value: float) -> str:
    from app.core.units import format_length

    return format_length(value)
