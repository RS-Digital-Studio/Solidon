"""Raum- und Plattenvorlage (Bauplan §24.1, Gruppe „Struktur“).

Hier liegen Raumboden, Raumwand und Fensterscheibe: flach gedruckte Platten, die mit
Nut und Feder zu einem Raum mit offener Front gesteckt werden — Boden,
Rückwand, zwei Seitenwände, dazu Tür- und Fensteröffnungen und die
Fensterscheibe als passender Einsatz. Sie kommen aus dem Dateiaudit (RM-184,
Puppenhaus: Raum 240 mm, Wand 3 bis 4 mm, Türen 200 mm hoch und 90 breit,
Fenster 100 breit und 120 hoch, „flach gedruckte Panels, gesteckt, keine
Magnete“).

**Ein Raum ist ein Projekt, keine Platte.** Ein Baustein ist ein Körper; der
Raum besteht aus vier oder fünf. Gekoppelt werden sie über die gemeinsamen
Maße: Wer Raumlänge, Raumtiefe, Raumhöhe und Wandstärke als Projektparameter
anlegt (alle drei Bausteine sind Vorlagen) und jede Platte daran bindet, ändert mit
einem Raummaß Boden, Wände, Nuten und Öffnungen zugleich.

**Der Bezug aller Platten:** Raumlänge und Raumtiefe sind Außenmaße der Wände.
Die Rückwand steht auf der hinteren Nut des Bodens, die Seitenwände auf den
seitlichen und stoßen mit einer Feder in die Nuten der Rückwand. Federn sind
eine halbe Wand dick und mittig, Nuten um das Spiel breiter und eine halbe Wand
tief. Boden und Rückwand stehen hinten und seitlich um eine Wandstärke über
die Wandaußenseiten (:data:`SKIRT_SHARE`): Neben einer mittigen Nut bliebe
sonst bei dünner Wand und großem Spiel kein Material bis zur Kante.
"""

from __future__ import annotations

from typing import Final, cast

from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import face, result, subtract, union
from app.core.knowledge.parts.registry import FeatureRequirement, PartChange, register_part
from app.core.knowledge.parts.shapes import Form
from app.core.registry import op_params, param, play_param
from app.core.registry.params import ZERO_NONE
from app.core.types import BaseParams, Feature, FeatureId, PartResult
from app.core.units import EPS_GEOM
from app.i18n import TranslatableText, _

ROOM_PANELS_ADDED = PartChange(
    version="1",
    date="2026-10-04",
    reason="Raum- und Plattenvorlage aus dem Dateiaudit (RM-184, Puppenhaus).",
)


#: Wie weit Boden und Rückwand über die Wandaußenseiten hinausstehen, als Anteil
#: der Wand. Eine Nut auf der Mittellinie einer Wand liegt ein Viertel der Wand
#: weniger das halbe Spiel vor deren Außenseite, die Deckennut unten (eine ganze
#: Wand breit) nur das halbe Spiel; bei 2 mm Wand und 1 mm Spiel bliebe dort
#: kein Material bis zur Kante. Mit einer Wand Überstand bleibt neben jeder Nut
#: mindestens eine Wand weniger das halbe Spiel.
SKIRT_SHARE: Final = 1.0


def _block(x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> Form:
    """Ein Quader zwischen zwei Grenzen je Achse — der Rahmen von ``shapes.box``."""
    box = shapes.box(x[1] - x[0], y[1] - y[0], z[1] - z[0])
    return shapes.moved(box, ((x[0] + x[1]) / 2.0, (y[0] + y[1]) / 2.0, z[0]))


def tongue_length(wall: float, play: float) -> float:
    """Wie weit eine Feder vorsteht: eine halbe Wand, weniger das halbe Spiel zum Nutgrund."""
    return wall / 2.0 - play / 2.0


def groove_width(wall: float, play: float) -> float:
    """Wie breit eine Nut ist: die halbe Wand der Feder und das ganze Spiel."""
    return wall / 2.0 + play


# --- Raumboden ------------------------------------------------------------------------

FLOOR_TOO_THIN = _(
    "Der Boden ist zu dünn für seine Nuten: Er braucht mindestens eine Wandstärke, mit "
    "Nuten auf beiden Seiten anderthalb. Einen dickeren Boden oder dünnere Wände wählen."
)
STAIRWELL_TOO_LARGE = _(
    "Die Treppenöffnung ist größer als der Raum: Neben ihr müssen zwei Wandstärken Boden "
    "bleiben. Eine kleinere Öffnung oder einen größeren Raum wählen."
)


@op_params
class RoomFloorParams(BaseParams):
    length: float = param(
        title=_("Raumlänge"),
        default=240.0,
        unit="mm",
        minimum=60.0,
        maximum=400.0,
        doc=_("Außenmaß von Seitenwand zu Seitenwand; so lang ist auch die Rückwand."),
    )
    depth: float = param(
        title=_("Raumtiefe"),
        default=240.0,
        unit="mm",
        minimum=60.0,
        maximum=400.0,
        doc=_("Außenmaß von der offenen Front bis zur Außenseite der Rückwand."),
    )
    thickness: float = param(
        title=_("Bodenstärke"),
        default=4.0,
        unit="mm",
        minimum=2.0,
        maximum=12.0,
        doc=_("Dicke der Bodenplatte."),
        placement="advanced",
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=4.0,
        unit="mm",
        minimum=2.0,
        maximum=10.0,
        doc=_("Dicke der Wände, die auf diesem Boden stehen. Danach richten sich die Nuten."),
        placement="advanced",
    )
    ceiling: bool = param(
        title=_("Zwischendecke"),
        default=False,
        doc=_(
            "Nuten auch auf der Unterseite: Der Boden liegt dann als Decke auf den Wänden "
            "des Raums darunter."
        ),
    )
    stairwell: bool = param(
        title=_("Treppenöffnung"),
        default=False,
        doc=_("Eine Öffnung an der linken Wand, die hinten an der Rückwand endet."),
        placement="advanced",
    )
    stair_width: float = param(
        title=_("Öffnungsbreite"),
        default=100.0,
        unit="mm",
        placement="advanced",
        minimum=20.0,
        maximum=200.0,
        depends_on=("stairwell", (True,)),
        doc=_("Breite der Treppenöffnung quer zur Seitenwand."),
    )
    stair_length: float = param(
        title=_("Öffnungslänge"),
        default=200.0,
        unit="mm",
        placement="advanced",
        minimum=20.0,
        maximum=300.0,
        depends_on=("stairwell", (True,)),
        doc=_("Länge der Treppenöffnung entlang der Seitenwand."),
    )
    play: float = play_param()


def _floor_reason(params: RoomFloorParams) -> TranslatableText | None:
    """Die erklärten Bedingungen: Material unter den Nuten und Platz um die Treppe."""
    needed = 1.5 * params.wall if params.ceiling else params.wall
    if params.thickness < needed - EPS_GEOM:
        return FLOOR_TOO_THIN
    if params.stairwell and (
        params.stair_width > params.length - 4.0 * params.wall
        or params.stair_length > params.depth - 4.0 * params.wall
    ):
        return STAIRWELL_TOO_LARGE
    return None


@register_part(
    name="room_floor",
    title=_("Raumboden"),
    group="structure",
    params=RoomFloorParams,
    standalone=True,
    template=True,
    at_face=False,
    features=("floor", "groove", "ceiling"),
    feature_requirements=(
        FeatureRequirement("floor"),
        FeatureRequirement("groove"),
        FeatureRequirement("ceiling", when="ceiling"),
    ),
    feasible=lambda raw: _floor_reason(cast(RoomFloorParams, raw)),
    doc=_(
        "Die Bodenplatte eines Raums mit offener Front. Sie trägt Nuten für Rückwand und beide "
        "Seitenwände, wahlweise auch unten als Zwischendecke und mit Treppenöffnung. "
        "Zusammen mit der Raumwand eine Raumvorlage aus flach gedruckten Platten."
    ),
    caveat=_(
        "Steckt ohne Magnete und ohne lose Kleinteile, hält aber erst verklebt fest. Für "
        "ein Spielhaus jede Nut verkleben."
    ),
    changes=[ROOM_PANELS_ADDED],
)
def room_floor(raw: BaseParams) -> PartResult:
    """Die Platte liegt in X und Y mittig auf Z = 0; die offene Front ist -Y.

    Die hintere Nut läuft über die ganze Länge, die seitlichen von der Front
    bis in die hintere — die Rückwand steht vor den Seitenwänden. Die
    Treppenöffnung liegt zwei Wandstärken neben der linken Nut und endet zwei
    Wandstärken vor der hinteren.
    """
    params = cast(RoomFloorParams, raw)
    reason = _floor_reason(params)
    if reason is not None:
        raise ValidationError("thickness", reason, constraint="feasible")
    length, depth, wall = params.length, params.depth, params.wall
    thickness = params.thickness
    skirt = SKIRT_SHARE * wall
    half_x, half_y = length / 2.0, depth / 2.0
    back = half_y - wall / 2.0
    side = half_x - wall / 2.0
    plate_x = half_x + skirt
    cutters: list[Form] = []
    features: list[tuple[FeatureId, Feature]] = [
        face("floor_1", length * depth, (0.0, 0.0, thickness)),
    ]
    for index, (width, deep, z) in enumerate(
        (
            (groove_width(wall, params.play), wall / 2.0, thickness - wall / 2.0),
            (wall + params.play, wall / 2.0, -BOOLEAN_OVERLAP),
        )
    ):
        if index and not params.ceiling:
            break
        name = "groove" if index == 0 else "ceiling"
        top = z + deep + BOOLEAN_OVERLAP if index == 0 else wall / 2.0
        floor_level = z if index == 0 else wall / 2.0
        span = (z, top)
        cutters.append(
            _block((-plate_x - 1.0, plate_x + 1.0), (back - width / 2.0, back + width / 2.0), span)
        )
        for sign in (-1.0, 1.0):
            centre = sign * side
            cutters.append(
                _block((centre - width / 2.0, centre + width / 2.0), (-half_y - 1.0, back), span)
            )
        normal = (0.0, 0.0, 1.0) if index == 0 else (0.0, 0.0, -1.0)
        run = back + half_y
        middle = (back - half_y) / 2.0
        features.extend(
            [
                face(f"{name}_1", 2.0 * plate_x * width, (0.0, back, floor_level), normal),
                face(f"{name}_2", run * width, (-side, middle, floor_level), normal),
                face(f"{name}_3", run * width, (side, middle, floor_level), normal),
            ]
        )
    if params.stairwell:
        left = -half_x + 2.0 * wall
        rear = back - wall / 2.0 - 2.0 * wall
        cutters.append(
            _block(
                (left, left + params.stair_width),
                (rear - params.stair_length, rear),
                (-1.0, thickness + 1.0),
            )
        )
    plate = _block((-plate_x, plate_x), (-half_y, half_y + skirt), (0.0, thickness))
    return result(subtract(plate, *cutters), *features)


# --- Raumwand ---------------------------------------------------------------------------

ROOM_ROLES: Final = ("room_back", "room_side")
OPENING_KINDS: Final = ("window", "door")

OPENING_TOO_LARGE = _(
    "Die Öffnung ist zu groß für diese Wand: Daneben, darüber und darunter müssen zwei "
    "Wandstärken stehen bleiben. Eine kleinere Öffnung oder eine größere Wand wählen."
)


@op_params
class RoomWallParams(BaseParams):
    role: str = param(
        title=_("Platte"),
        default="room_back",
        choices=ROOM_ROLES,
        doc=_(
            "Die Rückwand mit Nuten für die Seitenwände oder eine Seitenwand mit Feder zur "
            "Rückwand."
        ),
    )
    width: float = param(
        title=_("Raummaß"),
        default=240.0,
        unit="mm",
        minimum=40.0,
        maximum=400.0,
        doc=_(
            "Bei der Rückwand die Raumlänge, bei der Seitenwand die Raumtiefe — dieselbe Zahl "
            "wie am Raumboden. Die Seitenwand ist um die Rückwand kürzer."
        ),
    )
    height: float = param(
        title=_("Raumhöhe"),
        default=240.0,
        unit="mm",
        minimum=40.0,
        maximum=400.0,
        doc=_("Höhe der Wand über dem Boden."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=4.0,
        unit="mm",
        minimum=2.0,
        maximum=10.0,
        doc=_("Dicke der Platte; Federn und Nuten richten sich danach."),
        placement="advanced",
    )
    opening: str = param(
        title=_("Öffnung"),
        default="window",
        choices=OPENING_KINDS,
        doc=_(
            "Ein Fenster mittig in der Wand mit Falz für die Scheibe oder eine Tür, die am "
            "Boden beginnt."
        ),
        placement="advanced",
    )
    opening_width: float = param(
        title=_("Öffnungsbreite"),
        default=100.0,
        unit="mm",
        minimum=0.0,
        maximum=200.0,
        doc=_("Breite von Fenster oder Tür. Null heißt: keine Öffnung."),
        placement="advanced",
        zero_text=ZERO_NONE,
    )
    opening_height: float = param(
        title=_("Öffnungshöhe"),
        default=120.0,
        unit="mm",
        minimum=10.0,
        maximum=300.0,
        doc=_("Höhe von Fenster oder Tür."),
        placement="advanced",
    )
    play: float = play_param()


def _panel_width(params: RoomWallParams) -> float:
    """Die Plattenbreite ohne Feder.

    Die Seitenwand endet an der Innenseite der Rückwand; die Rückwand steht an
    beiden Enden um den Überstand des Bodens über die Seitenwände hinaus.
    """
    if params.role == "room_side":
        return params.width - params.wall
    return params.width + 2.0 * SKIRT_SHARE * params.wall


def _wall_reason(params: RoomWallParams) -> TranslatableText | None:
    """Die erklärte Bedingung: Um die Öffnung bleiben zwei Wandstärken stehen."""
    if params.opening_width <= EPS_GEOM:
        return None
    margin = 2.0 * params.wall
    if (_panel_width(params) - params.opening_width) / 2.0 < margin + params.play:
        return OPENING_TOO_LARGE
    if params.opening == "door":
        rest = params.height - params.opening_height
    else:
        rest = (params.height - params.opening_height) / 2.0
    if rest < margin:
        return OPENING_TOO_LARGE
    return None


@register_part(
    name="room_wall",
    title=_("Raumwand"),
    group="structure",
    params=RoomWallParams,
    standalone=True,
    template=True,
    at_face=False,
    features=("wall", "tongue", "groove", "opening", "rebate"),
    feature_requirements=(
        FeatureRequirement("wall"),
        FeatureRequirement("tongue"),
        FeatureRequirement("groove", when="role", equals="room_back"),
        # Null Öffnungsbreite heißt keine Öffnung — und dann auch kein Falz.
        FeatureRequirement("opening", unless="opening_width", unless_equals=0.0),
        FeatureRequirement(
            "rebate", when="opening", equals="window", unless="opening_width", unless_equals=0.0
        ),
    ),
    feasible=lambda raw: _wall_reason(cast(RoomWallParams, raw)),
    doc=_(
        "Eine Wandplatte für den Raumboden. Rückwand mit Nuten für die Seitenwände oder "
        "Seitenwand mit Feder zur Rückwand, beide mit Feder zum Boden und wahlweise einem "
        "Fenster mit Falz oder einer Tür. Die Scheibe dazu ist der Baustein Fensterscheibe."
    ),
    caveat=_(
        "Flach drucken, die Innenseite mit Nuten und Falz nach oben. Die rechte Seitenwand "
        "ist die gespiegelte linke; das Fenster hat seinen Falz dann außen."
    ),
    changes=[ROOM_PANELS_ADDED],
)
def room_wall(raw: BaseParams) -> PartResult:
    """Eine Platte, wie sie gedruckt wird: X entlang der Wand, Y nach oben, Z die Dicke.

    Die Innenseite liegt oben (Z = Wandstärke). Die Feder am Fuß reicht unter
    Y = 0; bei der Seitenwand steht eine zweite an der Rückkante (+X) über. Die
    Rückwand trägt auf ihrer Innenseite an beiden Enden eine Nut über die
    ganze Höhe. Eine Tür beginnt am Fuß und schneidet auch die Feder, ein
    Fenster sitzt mittig und hat innen einen Falz von einer Wandstärke, in den
    die Scheibe mit dem Spiel passt.
    """
    params = cast(RoomWallParams, raw)
    reason = _wall_reason(params)
    if reason is not None:
        raise ValidationError("opening_width", reason, constraint="feasible")
    wall, play, height = params.wall, params.play, params.height
    width = _panel_width(params)
    half = width / 2.0
    reach = tongue_length(wall, play)
    thick = (wall / 4.0, 3.0 * wall / 4.0)
    solids: list[Form] = [
        _block((-half, half), (0.0, height), (0.0, wall)),
        _block((-half, half), (-reach, BOOLEAN_OVERLAP), thick),
    ]
    features: list[tuple[FeatureId, Feature]] = [
        face("tongue_1", width * wall / 2.0, (0.0, -reach, wall / 2.0), (0.0, -1.0, 0.0)),
    ]
    # Die Innenseite: ihre Fläche ohne Nuten, Falz und Tür, ihre Mitte auf ihr —
    # unter dem Fenster, über der Tür, sonst in der Wandmitte.
    inner_area = width * height
    inner_centre = height / 2.0
    cutters: list[Form] = []
    if params.role == "room_side":
        solids.append(_block((half - BOOLEAN_OVERLAP, half + reach), (0.0, height), thick))
        features.append(
            face(
                "tongue_2",
                height * wall / 2.0,
                (half + reach, height / 2.0, wall / 2.0),
                (1.0, 0.0, 0.0),
            )
        )
    else:
        slot = groove_width(wall, play)
        for index, sign in enumerate((-1.0, 1.0), start=1):
            centre = sign * (half - SKIRT_SHARE * wall - wall / 2.0)
            cutters.append(
                _block(
                    (centre - slot / 2.0, centre + slot / 2.0),
                    (-reach - 1.0, height + 1.0),
                    (wall / 2.0, wall + 1.0),
                )
            )
            features.append(
                face(f"groove_{index}", slot * height, (centre, height / 2.0, wall / 2.0))
            )
            inner_area -= slot * height
    if params.opening_width > EPS_GEOM:
        opening_half = params.opening_width / 2.0
        if params.opening == "door":
            low, high = -reach - 1.0, params.opening_height
            inner_area -= params.opening_width * params.opening_height
            inner_centre = (high + height) / 2.0
            lintel = (wall, wall / 2.0)
        else:
            low = (height - params.opening_height) / 2.0
            high = low + params.opening_height
            cutters.append(
                _block(
                    (-opening_half - wall, opening_half + wall),
                    (low - wall, high + wall),
                    (wall / 2.0, wall + 1.0),
                )
            )
            rebate = (params.opening_width + 2.0 * wall) * (params.opening_height + 2.0 * wall)
            inner_area -= rebate
            inner_centre = (low - wall) / 2.0
            lintel = (wall / 2.0, wall / 4.0)
            features.append(
                face(
                    "rebate_1",
                    rebate - params.opening_width * params.opening_height,
                    (0.0, low - wall / 2.0, wall / 2.0),
                )
            )
        cutters.append(_block((-opening_half, opening_half), (low, high), (-1.0, wall + 1.0)))
        # Die Unterseite des Sturzes — beim Fenster unter dem Falz nur eine halbe Wand.
        features.append(
            face(
                "opening_1",
                params.opening_width * lintel[0],
                (0.0, high, lintel[1]),
                (0.0, -1.0, 0.0),
            )
        )
    features.append(face("wall_1", inner_area, (0.0, inner_centre, wall)))
    body = union(*solids)
    return result(subtract(body, *cutters) if cutters else body, *features)


# --- Fensterscheibe -------------------------------------------------------------------


@op_params
class RoomPaneParams(BaseParams):
    opening_width: float = param(
        title=_("Öffnungsbreite"),
        default=100.0,
        unit="mm",
        minimum=10.0,
        maximum=200.0,
        doc=_("Breite des Fensters — dieselbe Zahl wie an der Raumwand."),
    )
    opening_height: float = param(
        title=_("Öffnungshöhe"),
        default=120.0,
        unit="mm",
        minimum=10.0,
        maximum=300.0,
        doc=_("Höhe des Fensters — dieselbe Zahl wie an der Raumwand."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=4.0,
        unit="mm",
        minimum=2.0,
        maximum=10.0,
        doc=_("Dicke der Wand mit dem Fenster. Die Scheibe ist halb so dick und füllt den Falz."),
    )
    play: float = play_param()


@register_part(
    name="room_pane",
    title=_("Fensterscheibe"),
    group="structure",
    params=RoomPaneParams,
    standalone=True,
    template=True,
    at_face=False,
    features=("pane",),
    doc=_(
        "Die Scheibe zum Fenster einer Raumwand. Sie ist so groß wie der Falz weniger das "
        "Spiel und halb so dick wie die Wand. Zum Beispiel aus durchscheinendem Filament "
        "drucken und von innen einkleben."
    ),
    caveat=_(
        "Für ein Spielhaus fest einkleben, nicht lose einlegen: Eine lose Scheibe ist ein "
        "Kleinteil."
    ),
    changes=[ROOM_PANELS_ADDED],
)
def room_pane(raw: BaseParams) -> PartResult:
    """Die Scheibe, flach auf Z = 0, in X und Y mittig — sie liegt so im Falz wie gedruckt.

    Der Falz der Raumwand ist eine Wand breiter als die Öffnung auf jeder
    Seite und eine halbe Wand tief; die Scheibe füllt ihn bis auf das Spiel.
    Größer als die Öffnung um zwei Falzbreiten, kann sie nicht hindurchfallen.
    """
    params = cast(RoomPaneParams, raw)
    wall, play = params.wall, params.play
    pane_width = params.opening_width + 2.0 * wall - play
    pane_height = params.opening_height + 2.0 * wall - play
    return result(
        shapes.box(pane_width, pane_height, wall / 2.0),
        face("pane_1", pane_width * pane_height, (0.0, 0.0, wall / 2.0)),
    )
