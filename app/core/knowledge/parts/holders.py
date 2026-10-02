"""Halter für Gegenstände an Wand, Lochwand und Plattenkante (RM-399, Bauplan §24.1).

Vier Vorlagen, eine je Form: **U-Form** (ein eckiger Gegenstand, von drei
Seiten gefasst), **rund** (Ring oder Becher), **Gabel** (zwei Zinken mit rundem
Grund) und **Ablage** (L-Form, mit Rand Z-Form). Jede steht frei, entsteht in
einem Schritt (``standalone``) und bietet an, ihre Maße als Projektparameter
anzulegen (``template``) — danach dreht die Parameterleiste „denselben Halter,
anderes Maß".

**Vier Bausteine und nicht einer mit einer Formwahl, aus zwei Gründen.** Der
Bereichstest fährt das volle kartesische Produkt aller Grenzen und weist mehr
als ``range_check.MAX_CORNERS`` (512) ab, ohne zu rechnen (§24.3: keine
Stichprobe). Vier Formen mal eckig oder rund mal vier Befestigungen mal Boden
mal sechs Maße wären 8192 Ecken; je Form sind es 256 oder 512. Und der Kunde
ohne CAD-Kenntnisse erkennt seinen Halter im Katalog an vier Vorschaubildern
schneller als an einem Auswahlfeld mit den Buchstaben U, L und Z.

**Gemeinsam ist die Rückwand und ihre Befestigung** (:func:`_assembled`). Die
Rückwand liegt bei ``y ∈ [-t, 0]`` an der Wand, ihre Vorderseite ``y = 0`` ist
die Linie, an der der Gegenstand beginnt; Z ist oben, wie der Halter hängt,
und der Halter steht mit ``z = 0`` auf dem Druckbett. Die Befestigung kommt
aus den vorhandenen Bausteinen und der Normteiltabelle, nie aus einer Zahl
hier: Schlüsselloch und Haken mit den Vorgaben von ``keyhole`` und
``pegboard_hook``, die Schraubenlöcher mit Senkung aus ``screw_hole`` in der
Größe des Wandhalters. Die Rückwand wächst nur, wenn die Befestigung mehr
Platz braucht, als die Halteform ihr lässt — dieselbe Regel wie beim
Wandhalter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final, Protocol, cast

from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, form_of, result, subtract, union
from app.core.knowledge.parts.fasteners import ScrewHoleParams, screw_hole
from app.core.knowledge.parts.mounting import (
    HEAD_CLEARANCE,
    KeyholeParams,
    PegboardHookParams,
    WallMountParams,
    keyhole,
    pegboard_hook,
)
from app.core.knowledge.parts.registry import (
    FeatureRequirement,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.knowledge.parts.shapes import Form
from app.core.registry import op_params, param, play_param
from app.core.types import BaseParams, Feature, FeatureId, PartResult, Vec3
from app.core.units import EPS_GEOM, MAX_FACET_SAG
from app.i18n import TranslatableText, _

HOLDER_ADDED: Final = PartChange(
    version="1",
    date="2026-10-02",
    reason=(
        "Halter-Vorlage aus RM-399: U-Form, rund, Gabel und Ablage mit Schlüsselloch, "
        "Schraublöchern, Lochwand-Haken oder Klemme (Vorgabe Robert, 02.10.2026)."
    ),
)

#: Ein schmaler Halter bekommt ein Schlüsselloch in der Mitte, statt für zwei
#: breiter zu werden (RM-443). Nur Halter mit Schlüsselloch, deren Rückwand
#: schmaler ist als zwei Löcher mit Rand, ändern sich.
ONE_KEYHOLE_WHEN_NARROW: Final = PartChange(
    version="22",
    date="2026-10-02",
    reason=(
        "Die Vorlage setzte immer zwei Schlüssellöcher und machte schmale Halter dafür "
        "breiter, als eingetragen: Modell 1 aus dem Korpus wurde 24,7 statt 20 mm breit."
    ),
    effect=_(
        "Ein schmaler Halter mit Schlüsselloch behält seine Breite und hängt an einem "
        "Schlüsselloch in der Mitte statt an zwei."
    ),
)

#: Die vier Befestigungen, in jedem Halter dieselben.
MOUNTS: Final = ("keyhole", "screws", "pegboard", "clamp")

#: Das Schlüsselloch mit den Vorgaben seines Bausteins — Schraube, Einhängeweg,
#: Tiefe und Kopftiefe kommen von dort, das Spiel aus dem Profil des Halters.
KEYHOLE: Final = KeyholeParams()

#: Die Haken mit den Vorgaben ihres Bausteins: zwei nebeneinander im Raster,
#: mit Rastzunge, ohne eigene Platte — die Rückwand des Halters trägt sie.
HOOKS: Final = PegboardHookParams()


def _largest_play(params: type[BaseParams]) -> float:
    """Die Obergrenze des Spiels, die ein eingebundener Baustein selbst erklärt."""
    return min(
        float(entry.maximum)
        for entry in params.spec()
        if entry.name == "play" and entry.maximum is not None
    )


#: Das Spiel jedes Halters reicht höchstens so weit, wie Haken und Schlüsselloch
#: es selbst zulassen — sonst bauten sie hier außerhalb ihres geprüften Bereichs.
HOOKS_PLAY: Final = min(_largest_play(PegboardHookParams), _largest_play(KeyholeParams))

#: Die Schraube der Schraublöcher, dieselbe wie beim Wandhalter.
SCREW_SIZE: Final = WallMountParams().size

#: Wo der Kreis eines runden Sitzes höchstens von seiner Sehne abweicht. Der
#: Netzkern legt die Ecken auf den Kreis; mit den üblichen 48 Ecken läge die
#: Sehne eines Rings von 100 mm 0,11 mm innen, an zwei Seiten zusammen mehr als
#: das ganze Spiel des Profils.
_SAG: Final = MAX_FACET_SAG

_MOUNT_DOC: Final = _(
    "Wie der Halter befestigt wird: zwei Schlüssellöcher auf der Rückseite (an einem "
    "schmalen Halter eines in der Mitte), zwei Laschen mit gesenkten Schraublöchern, "
    "zwei Haken für die Lochwand oder eine "
    "Klemme, die über eine Plattenkante greift. Schrauben- und Lochwandmaße "
    "kommen aus der Normteiltabelle."
)

_CAVEAT: Final = _(
    "Mit Lochwand-Haken auf der Seite liegend drucken: Die Rastzunge federt nur "
    "über ihre Schichten, nicht quer zu ihnen. Die Klemme sitzt stramm, weil ihr "
    "Spalt genau die eingetragene Plattenstärke hat."
)


class _Fastened(Protocol):
    """Was jeder Halter für seine Rückwand angibt."""

    @property
    def mount(self) -> str: ...

    @property
    def wall(self) -> float: ...

    @property
    def play(self) -> float: ...

    @property
    def board(self) -> float: ...


def _mount_param(default: str) -> Any:
    return param(title=_("Befestigung"), default=default, choices=MOUNTS, doc=_MOUNT_DOC)


def _board_param() -> Any:
    return param(
        title=_("Plattenstärke"),
        default=18.0,
        unit="mm",
        minimum=3.0,
        maximum=60.0,
        depends_on=("mount", ("clamp",)),
        doc=_(
            "Wie dick die Platte ist, über die die Klemme greift — Regalboden, "
            "Tischplatte, Tür. Der Spalt hat genau dieses Maß."
        ),
    )


def _wall_param() -> Any:
    return param(
        title=_("Wandstärke"),
        default=3.0,
        unit="mm",
        minimum=1.2,
        maximum=8.0,
        placement="advanced",
        doc=_(
            "Dicke von Wänden, Boden und Rückwand. Für schwere Gegenstände dicker "
            "wählen; unter zwei Millimetern gibt der Halter nach."
        ),
    )


def _height_param(default: float, doc: TranslatableText) -> Any:
    return param(title=_("Höhe"), default=default, unit="mm", minimum=10.0, maximum=300.0, doc=doc)


def _size_param(title: TranslatableText, default: float, doc: TranslatableText) -> Any:
    return param(title=title, default=default, unit="mm", minimum=5.0, maximum=300.0, doc=doc)


def _requirements(*shape: FeatureRequirement) -> tuple[FeatureRequirement, ...]:
    """Die Merkmale der Halteform und die der jeweils gewählten Befestigung."""
    return (
        FeatureRequirement("plate"),
        *shape,
        FeatureRequirement("keyhole", when="mount", equals="keyhole"),
        FeatureRequirement("bore", when="mount", equals="screws"),
        FeatureRequirement("hook", when="mount", equals="pegboard"),
        FeatureRequirement("latch", when="mount", equals="pegboard"),
        FeatureRequirement("clamp", when="mount", equals="clamp"),
    )


#: Die Mindestwand gilt überall außer an der Rastzunge der Haken: Sie ist mit
#: zwei Bahnen absichtlich biegsam (``pegboard_hook`` sagt dasselbe).
_WALL: Final = WallRequirement(
    parameter="wall",
    reason="Die Rastzunge der Lochwand-Haken ist absichtlich biegsam.",
    when="mount",
    equals="pegboard",
)


# --- Rückwand und Befestigung ---------------------------------------------------------


def _segments(radius: float) -> int:
    """Ecken eines Kreises, dessen Sehnen höchstens ``_SAG`` innen liegen."""
    if radius <= _SAG:
        return shapes.SEGMENTS
    step = 2.0 * math.acos(1.0 - _SAG / radius)
    return max(shapes.SEGMENTS, math.ceil(2.0 * math.pi / step))


def _block(x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Form:
    """Ein Quader zwischen zwei Grenzen je Achse."""
    body = shapes.box(x[1] - x[0], y[1] - y[0], z[1] - z[0])
    return shapes.moved(body, ((x[0] + x[1]) / 2.0, (y[0] + y[1]) / 2.0, z[0]))


def _onto_back(form: Form) -> Form:
    """Ein Flächenbaustein auf die Rückseite: sein +Z wird -Y, sein Oben (-Y) wird +Z.

    Schlüsselloch und Haken bauen ihre Mündung bei ``z = 0`` und wachsen in
    ihr eigenes ``-Z`` (das Loch) oder ``+Z`` (der Haken); ihr Oben ist ``-Y``
    (``PartSpec.keeps_up``). Erst um Z halb herum, dann um X: ein Punkt
    ``(x, y, z)`` landet bei ``(-x, -z, -y)``.
    """
    return shapes.turned(shapes.turned(form, 180.0), 90.0, (1.0, 0.0, 0.0))


def _back_point(point: Any) -> Vec3:
    """Derselbe Weg für einen Punkt oder eine Richtung wie :func:`_onto_back`."""
    x, y, z = (float(value) for value in point)
    return (-x, -z, -y)


def _countersink_depth(size: str) -> float:
    """Wie tief die 90-Grad-Senkung von ``screw_hole`` reicht — dieselbe Rechnung.

    Eine 90-Grad-Senkung ist halb so tief, wie der Kopf breiter ist als das
    Loch. ``test_the_holder_plate_holds_the_whole_countersink_and_the_keyhole``
    vergleicht die Zahl mit dem Merkmal ``countersink_1``, das ``screw_hole``
    meldet.
    """
    screw = standards.screw(size)
    return (screw.countersink - screw.clearance) / 2.0


def _keyhole_width(play: float) -> float:
    """Wie breit das Schlüsselloch ist: der Kopf mit Kopfspiel und Profilspiel."""
    return standards.screw(KEYHOLE.size).head + HEAD_CLEARANCE + play


def _keyholes(width: float, play: float, wall: float) -> int:
    """Wie viele Schlüssellöcher in eine Rückwand dieser Breite passen: zwei oder eines.

    **Die Zahl folgt der Breite, nicht umgekehrt** (RM-443). Zwei Löcher
    nebeneinander mit einer Wandstärke Rand außen und zwischen ihnen halten
    den Halter gegen Verdrehen; passen sie nicht, sitzt eines in der Mitte —
    so hängt auch Modell 1 aus dem Korpus (20 mm breit). Vorher setzte die
    Vorlage immer zwei und machte die Rückwand dafür breiter als den Halter,
    24,7 statt 20 mm. Was der Kunde als Maß einträgt, ist das Maß.
    """
    pair = 2.0 * _keyhole_width(play) + 3.0 * wall
    return 2 if width >= pair - EPS_GEOM else 1


@dataclass(frozen=True, slots=True)
class _Plate:
    """Die Rückwand: wie breit, hoch und dick sie wird."""

    width: float
    height: float
    thickness: float
    keyholes: int = 0
    """Wie viele Schlüssellöcher sie trägt — null bei jeder anderen Befestigung."""


def _thickness(mount: str, wall: float) -> float:
    """Die Rückwand trägt vor jeder Aussparung noch eine volle Wandstärke."""
    if mount == "keyhole":
        return wall + KEYHOLE.depth
    if mount == "screws":
        return wall + _countersink_depth(SCREW_SIZE)
    return wall


def _ear(wall: float) -> float:
    """Die Lasche neben der Halteform: Senkung plus eine Wandstärke je Seite."""
    return standards.screw(SCREW_SIZE).countersink + 2.0 * wall


def _varied[P: BaseParams](params: P, **changes: Any) -> P:
    """Derselbe Parametersatz eines anderen Bausteins mit einzelnen geänderten Werten."""
    values = {entry.name: getattr(params, entry.name) for entry in type(params).spec()}
    values.update(changes)
    return type(params)(**values)


def _hooks(play: float) -> tuple[Form, dict[FeatureId, Feature]]:
    """Die beiden Lochwand-Haken, schon auf die Rückseite gedreht."""
    produced = pegboard_hook(_varied(HOOKS, play=play))
    return _onto_back(form_of(produced)), dict(produced.features)


def _plate(params: _Fastened, width: float, height: float, hooks: Form | None) -> _Plate:
    """Die Rückwand für eine Halteform dieser Breite und Mindesthöhe.

    Sie ist mindestens so breit und hoch wie die Halteform und wächst nur,
    wo die Befestigung mehr braucht: ein Schlüsselloch mit Rand, wenn die
    Halteform schmaler ist (zwei, wo sie passen, :func:`_keyholes`), zwei
    Laschen mit Senkung neben der Halteform, zwei Haken im Raster der
    Lochwand.
    """
    wall = params.wall
    thickness = _thickness(params.mount, wall)
    if params.mount == "keyhole":
        across = _keyhole_width(params.play)
        length = across + KEYHOLE.drop
        wide = max(width, across + 2.0 * wall)
        return _Plate(
            wide,
            max(height, length + 2.0 * wall),
            thickness,
            _keyholes(wide, params.play, wall),
        )
    if params.mount == "screws":
        countersink = standards.screw(SCREW_SIZE).countersink
        return _Plate(width + 2.0 * _ear(wall), max(height, countersink + 2.0 * wall), thickness)
    if params.mount == "pegboard" and hooks is not None:
        size = hooks.bounds.size
        return _Plate(
            max(width, size[0] + 2.0 * wall), max(height, size[2] + 2.0 * wall), thickness
        )
    return _Plate(width, height, thickness)


def _plate_features(plate: _Plate, mount: str, wall: float) -> tuple[FeatureId, Feature]:
    """Die Rückseite der Rückwand, die an Wand, Lochwand oder Platte anliegt."""
    covered = wall if mount == "clamp" else 0.0
    exposed = plate.height - covered
    return face(
        "plate_1",
        plate.width * exposed,
        (0.0, -plate.thickness, exposed / 2.0),
        (0.0, -1.0, 0.0),
    )


def _assembled(
    params: _Fastened,
    plate: _Plate,
    *,
    width: float,
    solids: list[Form],
    cavities: list[Form],
    features: list[tuple[FeatureId, Feature]],
    hooks: tuple[Form, dict[FeatureId, Feature]] | None,
) -> PartResult:
    """Rückwand, Halteform und Befestigung zu einem Körper.

    ``width`` ist die Außenbreite der Halteform — neben ihr sitzen die
    Laschen der Schraublöcher. Vereinigt wird zuerst, abgezogen danach: Der
    Hohlraum der Halteform und die Werkzeuge der Befestigung schneiden durch
    alles, was davor zusammenkam.
    """
    wall, t = params.wall, plate.thickness
    body: list[Form] = [
        shapes.moved(shapes.box(plate.width, t, plate.height), (0.0, -t / 2.0, 0.0))
    ]
    body.extend(solids)
    cutters = list(cavities)
    mounted: list[tuple[FeatureId, Feature]] = [_plate_features(plate, params.mount, wall)]

    if params.mount == "keyhole":
        tool = _onto_back(form_of(keyhole(_varied(KEYHOLE, play=params.play))))
        across = _keyhole_width(params.play)
        entrance = plate.height / 2.0 - KEYHOLE.drop / 2.0
        sides = (-1.0, 1.0) if plate.keyholes == 2 else (0.0,)
        for index, x in enumerate(sides, start=1):
            offset = x * (plate.width / 2.0 - wall - across / 2.0)
            cutters.append(shapes.moved(tool, (offset, -t, entrance)))
            mounted.append(
                bore(
                    f"keyhole_{index}",
                    standards.screw(KEYHOLE.size).clearance,
                    (offset, -t + KEYHOLE.depth / 2.0, entrance + KEYHOLE.drop),
                    depth=KEYHOLE.depth,
                    axis=(0.0, 1.0, 0.0),
                )
            )
    elif params.mount == "screws":
        screw = standards.screw(SCREW_SIZE)
        tool = form_of(
            screw_hole(
                _varied(
                    ScrewHoleParams(),
                    size=SCREW_SIZE,
                    depth=t + 2.0 * BOOLEAN_OVERLAP,
                    countersink=True,
                    washer=False,
                    head_room=0.0,
                )
            )
        )
        # Die Mündung vorn, ein Haar vor der Fläche, die Bohrung nach hinten
        # durch die Lasche: Der Schraubenkopf liegt vorn in der Senkung.
        tool = shapes.turned(tool, -90.0, (1.0, 0.0, 0.0))
        ear = _ear(wall)
        for index, x in enumerate((-1.0, 1.0), start=1):
            offset = x * (width / 2.0 + ear / 2.0)
            cutters.append(shapes.moved(tool, (offset, BOOLEAN_OVERLAP, plate.height / 2.0)))
            mounted.append(
                bore(
                    f"bore_{index}",
                    screw.clearance,
                    (offset, -t / 2.0, plate.height / 2.0),
                    depth=t,
                    axis=(0.0, 1.0, 0.0),
                    through=True,
                )
            )
    elif params.mount == "pegboard" and hooks is not None:
        form, hook_features = hooks
        # Die Haken sitzen oben an der Rückwand, eine Wandstärke unter ihrer
        # Kante; unten liegt der Halter an der Lochwand an. Ein Haar tief in
        # der Rückwand, wie jeder aufgesetzte Baustein (``ops._place``).
        lift = plate.height - wall - form.bounds.maximum[2]
        shift = (0.0, -t + BOOLEAN_OVERLAP, lift)
        body.append(shapes.moved(form, shift))
        for name, feature in hook_features.items():
            centre = _back_point(feature.params["centre"])
            mounted.append(
                face(
                    name,
                    float(feature.params["area"]),
                    (centre[0] + shift[0], centre[1] + shift[1], centre[2] + shift[2]),
                    _back_point(feature.params["normal"]),
                )
            )
    elif params.mount == "clamp":
        # Ein Bügel oben auf der Rückwand und ein hinterer Schenkel so tief wie
        # sie: Dazwischen steckt die Platte, der Spalt hat ihre Stärke.
        rear = -(t + params.board + wall)
        body.append(
            _block(
                (-plate.width / 2.0, plate.width / 2.0),
                (rear, -t / 2.0),
                (plate.height - wall, plate.height),
            )
        )
        body.append(
            _block(
                (-plate.width / 2.0, plate.width / 2.0),
                (rear, -(t + params.board)),
                (0.0, plate.height),
            )
        )
        mounted.append(
            face(
                "clamp_1",
                plate.width * (plate.height - wall),
                (0.0, -(t + params.board), (plate.height - wall) / 2.0),
                (0.0, 1.0, 0.0),
            )
        )

    joined = union(*body)
    if cutters:
        joined = subtract(joined, *cutters)
    return result(joined, *mounted, *features)


def _prepared(params: _Fastened) -> tuple[Form, dict[FeatureId, Feature]] | None:
    """Die Haken, wenn die Befestigung welche hat — gebaut einmal, gemessen und gesetzt."""
    return _hooks(params.play) if params.mount == "pegboard" else None


# --- U-Form -------------------------------------------------------------------------


@op_params
class HolderUParams(BaseParams):
    width: float = _size_param(
        _("Breite"), 40.0, _("Breite des Gegenstands. Das Spiel aus dem Materialprofil kommt dazu.")
    )
    depth: float = _size_param(
        _("Tiefe"),
        30.0,
        _("Wie weit der Gegenstand von der Wand absteht. Das Spiel kommt dazu."),
    )
    height: float = _height_param(
        40.0,
        _("Höhe der Wände. Die Rückwand wächst, wenn die Befestigung mehr Platz braucht."),
    )
    mount: str = _mount_param("keyhole")
    board: float = _board_param()
    floor: bool = param(
        title=_("Boden"),
        default=False,
        doc=_(
            "Schließt den Halter unten: Aus der U-Form wird ein Köcher, aus dem Ring ein Becher."
        ),
    )
    wall: float = _wall_param()
    play: float = play_param(maximum=HOOKS_PLAY)


@register_part(
    name="holder_u",
    title=_("Halter U-Form"),
    group="mounting",
    params=HolderUParams,
    standalone=True,
    template=True,
    at_face=False,
    features=("plate", "front", "floor", "keyhole", "bore", "hook", "latch", "clamp"),
    feature_requirements=_requirements(
        FeatureRequirement("front"), FeatureRequirement("floor", when="floor")
    ),
    wall=_WALL,
    doc=_(
        "Halter für einen eckigen Gegenstand: Drei Wände fassen ihn, die Rückwand ist die "
        "vierte. Mit Boden wird ein Köcher daraus. Befestigt mit Schlüsselloch, "
        "Schraublöchern, Lochwand-Haken oder Klemme."
    ),
    caveat=_CAVEAT,
    changes=[HOLDER_ADDED, ONE_KEYHOLE_WHEN_NARROW],
)
def holder_u(raw: BaseParams) -> PartResult:
    params = cast(HolderUParams, raw)
    wall = params.wall
    inner_width, inner_depth = params.width + params.play, params.depth + params.play
    outer_width, outer_depth = inner_width + 2.0 * wall, inner_depth + wall
    hooks = _prepared(params)
    plate = _plate(params, outer_width, params.height, hooks[0] if hooks else None)
    # Ein Block, aus dem der Innenraum geschnitten wird, und nicht drei Wände
    # und ein Boden, die vereinigt werden: Vier Quader mit gemeinsamen Ebenen
    # hinterließen an der Ecke 5 auf 300 auf 300 mm einen Splitter von 300 zu 1 in
    # der Deckfläche, der seine Nachbarwand schnitt. Der Block reicht eine halbe
    # Rückwand tief in sie hinein, damit er mit ihr verschmilzt. Geschnitten
    # wird, bevor die Rückwand dazukommt — sonst streifte der Innenraum ihre
    # Vorderseite, wo sie über die Wände hinausragt.
    bottom = wall if params.floor else -BOOLEAN_OVERLAP
    block = _block(
        (-outer_width / 2.0, outer_width / 2.0),
        (-plate.thickness / 2.0, outer_depth),
        (0.0, params.height),
    )
    inside = _block(
        (-inner_width / 2.0, inner_width / 2.0),
        (0.0, inner_depth),
        (bottom, params.height + BOOLEAN_OVERLAP),
    )
    solids = [subtract(block, inside)]
    features = [
        face(
            "front_1",
            outer_width * params.height,
            (0.0, outer_depth, params.height / 2.0),
            (0.0, 1.0, 0.0),
        )
    ]
    if params.floor:
        features.append(face("floor_1", inner_width * inner_depth, (0.0, inner_depth / 2.0, wall)))
    return _assembled(
        params,
        plate,
        width=outer_width,
        solids=solids,
        cavities=[],
        features=features,
        hooks=hooks,
    )


# --- rund: Ring oder Becher ---------------------------------------------------------


@op_params
class HolderRingParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=70.0,
        unit="mm",
        minimum=5.0,
        maximum=250.0,
        doc=_("Durchmesser des Gegenstands. Das Spiel aus dem Materialprofil kommt dazu."),
    )
    height: float = _height_param(
        40.0,
        _("Höhe des Rings. Die Rückwand wächst, wenn die Befestigung mehr Platz braucht."),
    )
    mount: str = _mount_param("screws")
    board: float = _board_param()
    floor: bool = param(
        title=_("Boden"),
        default=True,
        doc=_(
            "Schließt den Halter unten: Aus der U-Form wird ein Köcher, aus dem Ring ein Becher."
        ),
    )
    wall: float = _wall_param()
    play: float = play_param(maximum=HOOKS_PLAY)


def ring_centre(diameter: float, play: float, wall: float) -> float:
    """Wie weit die Mitte des Rings vor der Rückwand liegt.

    Eine halbe Wandstärke Steg zwischen Rückwand und Gegenstand: So berührt der
    Innenkreis die Ebene der Rückwand nicht, und der Außenkreis taucht nur eine
    halbe Wand tief in sie ein — nie bis an ihre Rückseite, die mindestens eine
    Wand dick ist. Berührende Kreise und Ebenen sind die Stellen, an denen eine
    Boolesche Operation entartet.
    """
    return (diameter + play) / 2.0 + wall / 2.0


@register_part(
    name="holder_ring",
    title=_("Halter rund"),
    group="mounting",
    params=HolderRingParams,
    standalone=True,
    template=True,
    at_face=False,
    features=("plate", "seat", "floor", "keyhole", "bore", "hook", "latch", "clamp"),
    feature_requirements=_requirements(
        FeatureRequirement("seat"), FeatureRequirement("floor", when="floor")
    ),
    wall=_WALL,
    doc=_(
        "Ring um einen runden Gegenstand — Flasche, Dose, Föhn. Mit Boden wird ein "
        "Becher daraus. Befestigt mit Schlüsselloch, Schraublöchern, Lochwand-Haken "
        "oder Klemme."
    ),
    caveat=_CAVEAT,
    changes=[HOLDER_ADDED, ONE_KEYHOLE_WHEN_NARROW],
)
def holder_ring(raw: BaseParams) -> PartResult:
    params = cast(HolderRingParams, raw)
    wall = params.wall
    inner = (params.diameter + params.play) / 2.0
    outer = inner + wall
    centre = ring_centre(params.diameter, params.play, wall)
    hooks = _prepared(params)
    plate = _plate(params, 2.0 * outer, params.height, hooks[0] if hooks else None)
    segments = _segments(outer)
    ring = shapes.moved(
        shapes.cylinder(2.0 * outer, params.height, segments=segments), (0.0, centre, 0.0)
    )
    bottom = wall if params.floor else -BOOLEAN_OVERLAP
    cavity = shapes.moved(
        shapes.cylinder(2.0 * inner, params.height + BOOLEAN_OVERLAP - bottom, segments=segments),
        (0.0, centre, bottom),
    )
    seat_bottom = max(bottom, 0.0)
    features = [
        bore(
            "seat_1",
            2.0 * inner,
            (0.0, centre, (seat_bottom + params.height) / 2.0),
            depth=params.height - seat_bottom,
            through=not params.floor,
        )
    ]
    if params.floor:
        features.append(face("floor_1", math.pi * inner**2, (0.0, centre, wall)))
    return _assembled(
        params,
        plate,
        width=2.0 * outer,
        solids=[ring],
        cavities=[cavity],
        features=features,
        hooks=hooks,
    )


# --- Gabel --------------------------------------------------------------------------


@op_params
class HolderForkParams(BaseParams):
    width: float = _size_param(
        _("Breite"),
        25.0,
        _(
            "Breite oder Durchmesser des Stiels, der zwischen die Zinken kommt. Das "
            "Spiel aus dem Materialprofil kommt dazu."
        ),
    )
    depth: float = _size_param(
        _("Tiefe"),
        25.0,
        _(
            "Wie weit die Zinken von der Rückwand reichen — bei einem runden Stiel "
            "sein Durchmesser. Mindestens die halbe Breite."
        ),
    )
    height: float = _height_param(
        15.0,
        _("Höhe der Zinken. Die Rückwand wächst, wenn die Befestigung mehr Platz braucht."),
    )
    mount: str = _mount_param("pegboard")
    board: float = _board_param()
    wall: float = _wall_param()
    play: float = play_param(maximum=HOOKS_PLAY)


FORK_TOO_SHALLOW: Final = _(
    "Die Zinken reichen nicht über die Mitte des Stiels hinaus. Die Tiefe vergrößern "
    "oder die Breite verkleinern."
)


def _fork_too_shallow(raw: BaseParams) -> TranslatableText | None:
    """Die erklärte Bedingung der Gabel: Die Zinken reichen über die Mitte des Grunds."""
    params = cast(HolderForkParams, raw)
    if params.depth + params.play <= (params.width + params.play) / 2.0:
        return FORK_TOO_SHALLOW
    return None


@register_part(
    name="holder_fork",
    title=_("Halter Gabel"),
    group="mounting",
    params=HolderForkParams,
    standalone=True,
    template=True,
    at_face=False,
    features=("plate", "prong", "keyhole", "bore", "hook", "latch", "clamp"),
    feature_requirements=_requirements(FeatureRequirement("prong")),
    wall=_WALL,
    feasible=_fork_too_shallow,
    doc=_(
        "Zwei Zinken mit rundem Grund, vorn offen: Der Stiel wird von vorn eingeschoben, "
        "der Kopf liegt oben auf — Besen, Schlauch, Werkzeug. Befestigt mit Schlüsselloch, "
        "Schraublöchern, Lochwand-Haken oder Klemme."
    ),
    caveat=_CAVEAT,
    changes=[HOLDER_ADDED, ONE_KEYHOLE_WHEN_NARROW],
)
def holder_fork(raw: BaseParams) -> PartResult:
    params = cast(HolderForkParams, raw)
    if _fork_too_shallow(params) is not None:
        raise ValidationError(
            "depth",
            FORK_TOO_SHALLOW,
            constraint="feasible",
            values={"depth": params.depth, "width": params.width},
        )
    wall = params.wall
    radius = (params.width + params.play) / 2.0
    reach = params.depth + params.play
    outer_width = 2.0 * (radius + wall)
    hooks = _prepared(params)
    plate = _plate(params, outer_width, params.height, hooks[0] if hooks else None)
    block = _block(
        (-outer_width / 2.0, outer_width / 2.0),
        (-plate.thickness / 2.0, reach),
        (0.0, params.height),
    )
    # Der Grund ist ein Halbkreis, dessen Rand die Ebene der Rückwand innen
    # berührt; das Langloch läuft vorn ganz aus dem Block heraus.
    length = reach + BOOLEAN_OVERLAP + radius
    slot = shapes.slot(
        2.0 * radius, length, params.height + 2.0 * BOOLEAN_OVERLAP, segments=_segments(radius)
    )
    cavity = shapes.moved(shapes.turned(slot, 90.0), (0.0, length / 2.0, -BOOLEAN_OVERLAP))
    prong = (radius + reach) / 2.0
    features = [
        face(
            f"prong_{index}",
            wall * (reach - radius),
            (side * (radius + wall / 2.0), prong, params.height),
        )
        for index, side in enumerate((-1.0, 1.0), start=1)
    ]
    return _assembled(
        params,
        plate,
        width=outer_width,
        solids=[block],
        cavities=[cavity],
        features=features,
        hooks=hooks,
    )


# --- Ablage: L-Form, mit Rand Z-Form ------------------------------------------------


@op_params
class HolderShelfParams(BaseParams):
    width: float = _size_param(
        _("Breite"), 60.0, _("Breite des Gegenstands. Das Spiel aus dem Materialprofil kommt dazu.")
    )
    depth: float = _size_param(
        _("Tiefe"),
        40.0,
        _("Wie tief der Gegenstand auf der Ablage steht, bis zum Rand. Das Spiel kommt dazu."),
    )
    height: float = _height_param(
        50.0,
        _(
            "Höhe der Rückwand bis zur Oberseite der Ablage. Sie wächst, wo die Stütze "
            "unter der Ablage oder die Befestigung mehr braucht."
        ),
    )
    lip: float = param(
        title=_("Rand"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_(
            "Wie hoch der Rand vorn über die Ablage steht. Null ist die L-Form; mit Rand "
            "wird es die Z-Form, von der nichts herunterrutscht."
        ),
    )
    mount: str = _mount_param("screws")
    board: float = _board_param()
    wall: float = _wall_param()
    play: float = play_param(maximum=HOOKS_PLAY)


def shelf_front(depth: float, play: float, wall: float, lip: float) -> float:
    """Wo die Ablage vorn endet: am Gegenstand, mit Rand eine Wandstärke weiter."""
    return depth + play + (wall if lip > 0.0 else 0.0)


@register_part(
    name="holder_shelf",
    title=_("Halter Ablage"),
    group="mounting",
    params=HolderShelfParams,
    standalone=True,
    template=True,
    at_face=False,
    features=("plate", "shelf", "lip", "keyhole", "bore", "hook", "latch", "clamp"),
    feature_requirements=_requirements(
        FeatureRequirement("shelf"),
        FeatureRequirement("lip", unless="lip", unless_equals=0.0),
    ),
    wall=_WALL,
    doc=_(
        "Ablage oben an einer Rückwand, mit einer Stütze unter 45 Grad, die ohne "
        "Stützmaterial druckt. Ohne Rand ist es die L-Form, mit Rand die Z-Form. "
        "Befestigt mit Schlüsselloch, Schraublöchern, Lochwand-Haken oder Klemme."
    ),
    caveat=_CAVEAT,
    changes=[HOLDER_ADDED, ONE_KEYHOLE_WHEN_NARROW],
)
def holder_shelf(raw: BaseParams) -> PartResult:
    """Rückwand nach unten, Ablage oben, Rand nach oben — von der Seite ein L oder ein Z.

    **Die Stütze ist die Bedingung dafür, dass der Halter so druckt, wie er
    hängt.** Eine Ablage, die waagerecht aus der Rückwand ragt, hängt beim
    Drucken in der Luft; unter ihr steigt deshalb eine Schräge unter 45 Grad
    von der Rückwand bis zur Vorderkante. Die Rückwand ist mindestens so hoch
    wie diese Schräge plus die Ablage — sonst würde die Schräge flacher und
    bräuchte selbst Stützmaterial.
    """
    params = cast(HolderShelfParams, raw)
    wall = params.wall
    inner_width = params.width + params.play
    inner_depth = params.depth + params.play
    front = shelf_front(params.depth, params.play, wall, params.lip)
    hooks = _prepared(params)
    plate = _plate(
        params, inner_width, max(params.height, front + wall), hooks[0] if hooks else None
    )
    top = plate.height
    start = top - wall - front
    outline: list[tuple[float, float]] = [
        (-plate.thickness / 2.0, start),
        (0.0, start),
        (front, top - wall),
    ]
    if params.lip > 0.0:
        outline += [(front, top + params.lip), (inner_depth, top + params.lip), (inner_depth, top)]
    else:
        outline.append((front, top))
    outline.append((-plate.thickness / 2.0, top))
    console = shapes.prism_across(outline, inner_width)
    features = [face("shelf_1", inner_width * inner_depth, (0.0, inner_depth / 2.0, top))]
    if params.lip > 0.0:
        features.append(
            face("lip_1", inner_width * wall, (0.0, inner_depth + wall / 2.0, top + params.lip))
        )
    return _assembled(
        params,
        plate,
        width=inner_width,
        solids=[console],
        cavities=[],
        features=features,
        hooks=hooks,
    )
