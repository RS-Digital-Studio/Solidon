"""Schlauchtülle und Kanalnaht (Bauplan §24.1, Gruppe „Kabel und Schläuche“).

Hier liegen zwei Bausteine aus dem Dateiaudit (RM-184), die etwas
weiterleiten, ohne dass der Durchgang schrumpfen darf:

* die **Schlauchtülle** — Bund, Schaft und Widerhaken um einen freien
  Durchgang, der durch die Wand des Trägers weitergeht (Familie 2, Pool-
  Wasserfall: Tülle mit Bund und vier Ringen um eine Bohrung von 24 mm);
* die **Kanalnaht** — eine Verbindung zweier Rinnensegmente gleichen
  Querschnitts, außen als überlappende Hülse oder innen als Einlage mit Rampe
  (Familie 8, CC2-Auffangrinne: Überlappung 18 mm, Rampe 8 mm, Wange 1,2 mm).

Beide sagen, was sie mit dem Durchgang tun: Die Tülle hält ihn über die ganze
Länge offen, die Hülse lässt den Kanal unverändert, und die Einlage nennt in
einem Befund, wie weit sie ihn verengt.
"""

from __future__ import annotations

import math
from typing import Final, cast

from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, intersect, pin, result, subtract
from app.core.knowledge.parts.closures import upright
from app.core.knowledge.parts.registry import (
    FeatureRequirement,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.registry import op_params, param, play_param
from app.core.types import BaseParams, Feature, FeatureId, Finding, PartResult, Point2
from app.core.units import format_length
from app.i18n import TranslatableText, _

HOSE_BARB_ADDED = PartChange(
    version="1",
    date="2026-10-04",
    reason="Schlauchtülle aus dem Dateiaudit (RM-184, Pool-Wasserfall).",
)

CHANNEL_JOINT_ADDED = PartChange(
    version="1",
    date="2026-10-04",
    reason="Kanalnaht mit Überlappung und Rampe aus dem Dateiaudit (RM-184, Auffangrinne).",
)

#: Steigung der Rückseite eines Widerhakens: 45 Grad, wie die Halteflanke
#: jedes stützenfrei gedruckten Hakens. Die Anlaufschräge zur Spitze ist
#: mindestens doppelt so lang wie der Überstand hoch (:data:`BARB_LEAD`).
BARB_LEAD: Final = 2.0

BARB_TOO_DENSE = _(
    "Die Widerhaken stehen zu dicht: Jeder braucht das Dreifache seines Überstands an "
    "Länge. Weniger Widerhaken, einen kleineren Überstand oder einen längeren Schaft wählen."
)
BARB_NO_PASSAGE = _(
    "Die Wand lässt keinen Durchgang: Er muss mindestens eine Wand weit sein. Einen "
    "größeren Schlauch oder eine dünnere Wand wählen."
)


@op_params
class HoseBarbParams(BaseParams):
    hose: float = param(
        title=_("Schlauch innen"),
        default=12.0,
        unit="mm",
        minimum=3.0,
        maximum=50.0,
        doc=_(
            "Innendurchmesser des Schlauchs. So dick ist der Schaft, die Widerhaken stehen "
            "darüber hinaus."
        ),
    )
    grip: float = param(
        title=_("Überstand"),
        default=1.0,
        unit="mm",
        minimum=0.3,
        maximum=3.0,
        doc=_(
            "Wie weit jeder Widerhaken je Seite über den Schlauch hinaussteht. Mehr hält "
            "fester und lässt sich schwerer aufschieben."
        ),
        placement="advanced",
    )
    count: int = param(
        title=_("Widerhaken"),
        default=3,
        minimum=1,
        maximum=6,
        doc=_("Wie viele Widerhaken hintereinander auf dem Schaft sitzen."),
        placement="advanced",
    )
    length: float = param(
        title=_("Schaftlänge"),
        default=24.0,
        unit="mm",
        minimum=5.0,
        maximum=80.0,
        doc=_("Wie weit der Schlauch aufgeschoben wird, vom Bund bis zur Spitze."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=1.5,
        unit="mm",
        minimum=0.8,
        maximum=6.0,
        doc=_("Wand zwischen Durchgang und Schaft. Der Durchgang ist um zwei Wände enger."),
        placement="advanced",
    )
    collar: float = param(
        title=_("Bundhöhe"),
        default=3.0,
        unit="mm",
        minimum=1.0,
        maximum=10.0,
        doc=_(
            "Der Bund am Fuß, an dem der Schlauch ansteht und eine Schelle Platz findet. Er "
            "ist eine Wand breiter als die Widerhaken."
        ),
        placement="advanced",
    )
    through: float = param(
        title=_("Trägerwand"),
        default=3.0,
        unit="mm",
        minimum=0.5,
        maximum=30.0,
        doc=_(
            "Wie dick die Wand ist, auf der die Tülle sitzt. So tief geht der Durchgang "
            "hinein, damit er auf der anderen Seite offen ist."
        ),
    )


def _barb_reason(params: HoseBarbParams) -> TranslatableText | None:
    """Die erklärten Bedingungen: Platz für jede Anlaufschräge und ein offener Durchgang."""
    if params.length / params.count < (1.0 + BARB_LEAD) * params.grip:
        return BARB_TOO_DENSE
    if params.hose - 2.0 * params.wall < params.wall:
        return BARB_NO_PASSAGE
    return None


def _require_barb(params: HoseBarbParams) -> None:
    reason = _barb_reason(params)
    if reason is not None:
        field = "count" if reason is BARB_TOO_DENSE else "wall"
        raise ValidationError(field, reason, constraint="feasible")


def hose_barb_outline(params: HoseBarbParams) -> tuple[Point2, ...]:
    """Der halbe Längsschnitt der Tülle von der Achse aus: Bund und Sägezahn der Widerhaken.

    Radius nach außen, Höhe nach oben; um die Achse gedreht ergibt er den
    vollen Körper, aus dem danach der Durchgang gebohrt wird. Jeder
    Widerhaken steigt von der Schaftoberfläche unter 45 Grad bis zum Kamm und
    läuft von dort flach zur Spitze hin aus: Der Schlauch gleitet über die
    flache Seite auf und hängt an der steilen.

    Der Bund beginnt ein Hundertstel unter null, damit die Tülle nicht nur
    Fläche an Fläche auf ihrem Träger steht (§39).
    """
    shaft = params.hose / 2.0
    crest = shaft + params.grip
    flange = crest + params.wall
    base = params.collar
    pitch = params.length / params.count
    points: list[Point2] = [
        (0.0, -BOOLEAN_OVERLAP),
        (flange, -BOOLEAN_OVERLAP),
        (flange, base),
        (shaft, base),
    ]
    for index in range(params.count):
        start = base + index * pitch
        points.append((crest, start + params.grip))
        points.append((shaft, start + pitch))
    points.append((0.0, base + params.length))
    return tuple(points)


def hose_barb_body(raw: BaseParams) -> PartResult:
    """Die Tülle selbst — vor dem Schnitt mit dem Träger vereinigt (``host_add``).

    Ihre Merkmale nennt der Baustein (:func:`hose_barb`), nicht der Aufbau: Er
    beschreibt Durchgang und Schaft als Ganzes, vom Träger bis zur Spitze.
    """
    params = cast(HoseBarbParams, raw)
    _require_barb(params)
    top = params.collar + params.length
    passage = shapes.moved(
        shapes.cylinder(params.hose - 2.0 * params.wall, top + 4.0 * BOOLEAN_OVERLAP),
        (0.0, 0.0, -2.0 * BOOLEAN_OVERLAP),
    )
    return result(subtract(shapes.revolved(hose_barb_outline(params)), passage))


@register_part(
    name="hose_barb",
    title=_("Schlauchtülle"),
    group="routing",
    params=HoseBarbParams,
    subtractive=True,
    host_add=hose_barb_body,
    features=("passage", "barb"),
    wall=WallRequirement.not_applicable(
        "Der Baustein ist der abtragende Durchgang durch die Trägerwand; die Tülle selbst "
        "entsteht als Trägeraufbau und wird über ihre Wandstärke geprüft."
    ),
    feasible=lambda raw: _barb_reason(cast(HoseBarbParams, raw)),
    doc=_(
        "Eine Tülle zum Aufschieben eines Schlauchs. Bund, Schaft und Widerhaken sitzen um einen "
        "freien Durchgang, der durch die Wand des Teils weitergeht. Alles in einem Schritt, "
        "ohne Kleben."
    ),
    caveat=_(
        "Für Leitungen unter Druck, dort hilft eine gekaufte Verschraubung. Dicht wird die Tülle "
        "erst mit einer Schlauchschelle am Bund."
    ),
    changes=[HOSE_BARB_ADDED],
)
def hose_barb(raw: BaseParams) -> PartResult:
    """Der Durchgang durch die Trägerwand, unter der Mündung (§24.1).

    Die Tülle selbst wächst als Trägeraufbau (:func:`hose_barb_body`) auf der
    Fläche; dieser Schnitt öffnet danach die Wand darunter, bis ein
    Hundertstel über die Fläche, damit Tüllendurchgang und Wanddurchgang ein
    Kanal sind.
    """
    params = cast(HoseBarbParams, raw)
    _require_barb(params)
    passage = params.hose - 2.0 * params.wall
    cutter = shapes.moved(
        shapes.cylinder(passage, params.through + 2.0 * BOOLEAN_OVERLAP),
        (0.0, 0.0, -params.through - BOOLEAN_OVERLAP),
    )
    # Ein Durchgang, kein Stückwerk: Das Merkmal reicht von der Rückseite der
    # Trägerwand bis zur Spitze der Tülle. Der Schaft, auf den der Schlauch
    # geschoben wird, ist der Zapfen der Passung zum Schlauch.
    top = params.collar + params.length
    return result(
        cutter,
        bore(
            "passage_1",
            passage,
            (0.0, 0.0, (top - params.through) / 2.0),
            depth=top + params.through,
            through=True,
        ),
        pin(
            "barb_1",
            params.hose,
            (0.0, 0.0, params.collar + params.length / 2.0),
            length=params.length,
        ),
    )


# --- Kanalnaht ---------------------------------------------------------------------

CHANNEL_STYLES: Final = ("outer_sleeve", "inner_insert")

CHANNEL_TOO_NARROW = _(
    "Die Kanalwand lässt keinen Kanal: Breite und Höhe müssen mehr als zwei Wände "
    "betragen. Eine dünnere Kanalwand oder einen größeren Kanal wählen."
)
CHANNEL_INSERT_TOO_THICK = _(
    "Die Einlage füllt den Kanal: Neben und über ihren Wänden bliebe weniger als eine "
    "Nahtwand frei. Eine dünnere Nahtwand oder einen größeren Kanal wählen."
)


@op_params
class ChannelJointParams(BaseParams):
    style: str = param(
        title=_("Bauart"),
        default="outer_sleeve",
        choices=CHANNEL_STYLES,
        doc=_(
            "Außen umgreift eine Hülse beide Segmente und lässt den Kanal unverändert. Innen "
            "liegt eine Einlage auf beiden Böden; sie braucht keinen Platz neben der Rinne, "
            "verengt den Kanal aber um ihre Wand."
        ),
    )
    width: float = param(
        title=_("Kanalbreite"),
        default=44.0,
        unit="mm",
        minimum=10.0,
        maximum=200.0,
        doc=_("Außenbreite der Rinnensegmente, an ihnen gemessen."),
    )
    height: float = param(
        title=_("Kanalhöhe"),
        default=27.0,
        unit="mm",
        minimum=5.0,
        maximum=100.0,
        doc=_("Außenhöhe der Segmente vom Boden bis zur Oberkante der Seitenwand."),
    )
    wall: float = param(
        title=_("Kanalwand"),
        default=2.0,
        unit="mm",
        minimum=0.8,
        maximum=6.0,
        doc=_("Wand- und Bodenstärke der Segmente — so tief ist der Anschlag in der Mitte."),
        placement="advanced",
    )
    overlap: float = param(
        title=_("Überlappung"),
        default=18.0,
        unit="mm",
        minimum=5.0,
        maximum=60.0,
        doc=_("Wie weit jedes Segment in die Naht greift."),
        placement="advanced",
    )
    thickness: float = param(
        title=_("Nahtwand"),
        default=1.2,
        unit="mm",
        minimum=0.8,
        maximum=6.0,
        doc=_("Wandstärke der Hülse oder der Einlage."),
        placement="advanced",
    )
    ramp: float = param(
        title=_("Rampenlänge"),
        default=8.0,
        unit="mm",
        minimum=1.0,
        maximum=40.0,
        depends_on=("style", ("inner_insert",)),
        doc=_(
            "Über diese Länge läuft die Einlage am oberen Ende flach aus, damit nichts an "
            "ihrer Kante hängen bleibt."
        ),
        placement="advanced",
    )
    play: float = play_param()


def _channel_reason(params: ChannelJointParams) -> TranslatableText | None:
    """Die erklärten Bedingungen: ein Kanal im Segment und Platz für die Einlage darin."""
    if min(params.width, params.height) <= 2.0 * params.wall:
        return CHANNEL_TOO_NARROW
    if params.style == "inner_insert":
        # Der Kanal in der Einlage: Segmentkanal ohne Spiel und ohne zwei Nahtwände in
        # der Breite, ohne den Einlageboden in der Höhe — beides mindestens eine Nahtwand.
        free_width = params.width - 2.0 * params.wall - params.play - 2.0 * params.thickness
        free_height = params.height - params.wall - params.thickness
        if min(free_width, free_height) < params.thickness:
            return CHANNEL_INSERT_TOO_THICK
    return None


def _require_channel(params: ChannelJointParams) -> None:
    reason = _channel_reason(params)
    if reason is not None:
        raise ValidationError("wall", reason, constraint="feasible")


#: Wie dick die Einlage an der Spitze ihrer Rampe ausläuft, als Anteil ihrer
#: Wand. Eine Schneide von null legt kein Slicer; ein Drittel der Wand ist bei
#: der Rinne aus dem Audit (1,2 mm) genau die Kante von 0,4 mm, mit der sie
#: gedruckt wurde und hielt.
RAMP_EDGE_SHARE: Final = 1.0 / 3.0


@register_part(
    name="channel_joint",
    play_inside=True,
    title=_("Kanalnaht"),
    group="routing",
    params=ChannelJointParams,
    standalone=True,
    at_face=False,
    features=("channel", "seat", "stop", "ramp"),
    feature_requirements=(
        FeatureRequirement("channel"),
        FeatureRequirement("seat", when="style", equals="outer_sleeve"),
        FeatureRequirement("stop", when="style", equals="outer_sleeve"),
        FeatureRequirement("ramp", when="style", equals="inner_insert"),
    ),
    wall=WallRequirement(
        parameter="thickness",
        reason="Die Einlage läuft an ihrer Rampe funktionsbedingt auf ein Drittel ihrer Wand "
        "aus; ihre Wände werden an der Nahtwand im Geometrietest gemessen.",
        when="style",
        equals="inner_insert",
    ),
    feasible=lambda raw: _channel_reason(cast(ChannelJointParams, raw)),
    doc=_(
        "Verbindet zwei Rinnensegmente mit gleichem Querschnitt. Außen als Hülse mit "
        "Anschlag in der Mitte, der die Stoßfuge im Querschnitt der Rinne schließt; innen "
        "als Einlage mit Rampe für Rinnen ohne Platz an der Seite."
    ),
    caveat=_(
        "Wenn die Segmente einrasten sollen, denn die Naht hält sie nur in Flucht. Dafür eine "
        "Rastnase je Segment setzen."
    ),
    changes=[CHANNEL_JOINT_ADDED],
)
def channel_joint(raw: BaseParams) -> PartResult:
    """Die Naht liegt entlang X, offen nach oben; die Rinne fließt in +X.

    **Außen:** eine U-Hülse, in die beide Segmente von den Enden her greifen.
    In der Mitte bleibt ein Steg im Querschnitt eines Segments stehen — Boden
    so hoch und Seiten so dick wie die Kanalwand. Er ist der Anschlag für
    beide Segmente und füllt zugleich die Stoßfuge, ohne in den Kanal zu
    ragen: Die Rinne behält ihren Querschnitt über die Naht.

    **Innen:** eine U-Einlage, die auf beiden Böden liegt und an beiden
    Seitenwänden anliegt. Am oberen Ende (-X) laufen Boden und Seiten über die
    Rampenlänge auf ein Drittel ihrer Wand aus (:data:`RAMP_EDGE_SHARE`), am
    unteren fällt sie nur ab. Wie weit sie den Kanal verengt, sagt ein Befund.
    """
    params = cast(ChannelJointParams, raw)
    _require_channel(params)
    if params.style == "outer_sleeve":
        return _outside_sleeve(params)
    return _inside_insert(params)


def _outside_sleeve(params: ChannelJointParams) -> PartResult:
    wall = params.wall
    inner = params.width + params.play
    outer = inner + 2.0 * params.thickness
    floor = params.thickness
    stop = params.thickness
    length = 2.0 * params.overlap + stop
    top = floor + params.height
    body = shapes.box(length, outer, top)
    pocket_length = params.overlap + BOOLEAN_OVERLAP
    pocket = shapes.box(pocket_length, inner, params.height + BOOLEAN_OVERLAP)
    reach = stop / 2.0 + pocket_length / 2.0
    channel_width = params.width - 2.0 * wall
    channel = shapes.box(
        stop + 2.0 * BOOLEAN_OVERLAP, channel_width, params.height - wall + BOOLEAN_OVERLAP
    )
    shaped = subtract(
        body,
        shapes.moved(pocket, (reach, 0.0, floor)),
        shapes.moved(pocket, (-reach, 0.0, floor)),
        shapes.moved(channel, (0.0, 0.0, floor + wall)),
    )
    seat_area = params.overlap * inner
    features: list[tuple[FeatureId, Feature]] = [
        face("channel_1", stop * channel_width, (0.0, 0.0, floor + wall)),
        face("seat_1", seat_area, (-reach + BOOLEAN_OVERLAP / 2.0, 0.0, floor)),
        face("seat_2", seat_area, (reach - BOOLEAN_OVERLAP / 2.0, 0.0, floor)),
        face(
            "stop_1",
            _segment_section(params),
            (-stop / 2.0, 0.0, floor + wall / 2.0),
            (-1.0, 0.0, 0.0),
        ),
        face(
            "stop_2",
            _segment_section(params),
            (stop / 2.0, 0.0, floor + wall / 2.0),
            (1.0, 0.0, 0.0),
        ),
    ]
    return result(shaped, *features)


def _segment_section(params: ChannelJointParams) -> float:
    """Die Querschnittsfläche eines Segments — so groß ist jede Anschlagfläche."""
    channel = (params.width - 2.0 * params.wall) * (params.height - params.wall)
    return params.width * params.height - channel


def _inside_insert(params: ChannelJointParams) -> PartResult:
    """Ein Block, aus dem der Kanal geschnitten wird — kein Zusammensetzen dünner Teile.

    Der Kanal in der Einlage ist der Schnitt zweier Prismen: im Seitenriss alles
    über dem Boden, der am oberen Ende als Rampe auf die Kante ausläuft, und im
    Grundriss alles zwischen den Wänden, die zur Rampe hin genauso auslaufen.
    Beide Verläufe sind dieselbe Gerade, also ist ihr Schnitt genau der
    Kanal. Aus Boden und zwei Wänden vereinigt ließ manifold an breiten
    Einlagen Dreiecke zurück, die einander schnitten (Bereichslauf, 200 mm).
    """
    thickness = params.thickness
    width = params.width - 2.0 * params.wall - params.play
    height = params.height - params.wall
    length = 2.0 * params.overlap
    ramp = min(params.ramp, params.overlap)
    edge = thickness * RAMP_EDGE_SHARE
    start, end = -length / 2.0, length / 2.0
    before, after = start - 2.0, end + 2.0
    block = shapes.box(length, width, height)
    # Seitenriss (X entlang der Naht, Z nach oben), quer über die ganze Breite.
    above_floor: list[Point2] = [
        (before, edge),
        (start, edge),
        (start + ramp, thickness),
        (after, thickness),
        (after, height + 1.0),
        (before, height + 1.0),
    ]
    over = shapes.turned(shapes.prism_across(above_floor, width + 2.0), -90.0)
    # Grundriss: zwischen den Wänden, die zur Rampe hin auf die Kante auslaufen.
    inner, narrow = width / 2.0 - edge, width / 2.0 - thickness
    between_walls: list[Point2] = [
        (before, -inner),
        (start, -inner),
        (start + ramp, -narrow),
        (after, -narrow),
        (after, narrow),
        (start + ramp, narrow),
        (start, inner),
        (before, inner),
    ]
    between = shapes.moved(upright(between_walls, height + 2.0), (0.0, 0.0, -1.0))
    body = subtract(block, intersect(over, between))
    channel_width = width - 2.0 * thickness
    channel_height = height - thickness
    finding = Finding(
        code="parts.channel_narrowed",
        severity="info",
        message=_(
            "Die Einlage verengt den Kanal an der Naht auf {width} Breite und {height} Höhe "
            "(im Segment {segment_width} und {segment_height}).",
            width=format_length(channel_width),
            height=format_length(channel_height),
            segment_width=format_length(params.width - 2.0 * params.wall),
            segment_height=format_length(params.height - params.wall),
        ),
        values={
            "width_mm": channel_width,
            "height_mm": channel_height,
        },
    )
    produced = result(
        body,
        face("channel_1", (length - ramp) * channel_width, (ramp / 2.0, 0.0, thickness)),
        face(
            "ramp_1",
            ramp * channel_width,
            (start + ramp / 2.0, 0.0, (thickness + edge) / 2.0),
            _ramp_normal(ramp, thickness - edge),
        ),
    )
    produced.findings.append(finding)
    return produced


def _ramp_normal(run: float, rise: float) -> tuple[float, float, float]:
    length = math.hypot(run, rise)
    return (-rise / length, 0.0, run / length)
