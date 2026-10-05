"""Verschlüsse, die man dreht: Bajonett und Rastdrehscheibe (Bauplan §24.1, Gruppe „Mechanik“).

Hier liegen zwei Paare aus dem Dateiaudit (RM-184):

* das **Bajonett** — eine Aufnahme mit L-Schlitzen und ein Kragen mit Nocken,
  erst axial eingesetzt, dann über den Drehweg bis zum Anschlag geschlossen
  (Familie 3, Filterkäfig: drei Nocken, 6 mm breit und 3,5 mm hoch,
  Einführtiefe 6 mm, Drehweg 13°);
* die **Rastdrehscheibe mit federnder Nabe** — eine Führung mit Pilzzapfen,
  Rastmulden und tastbaren Marken und eine Scheibe mit Fenster, drei
  tangentialen Federarmen und einer Rastzunge (Familie 4, Gewürzdeckel:
  Scheibe Ø 32 und 3 mm dick, Arme 1,1 mm, Zapfen Ø 6, drei Stellungen).

Beide Paare stehen in **einem** Baustein mit ``kind``: Die Hälften teilen jedes
Maß unter demselben Namen, und ein Paar aus zwei Aufrufen desselben Bausteins
kann nicht auseinanderlaufen. Gebaut wird jede Hälfte in ihrem eigenen Rahmen
auf Z = 0; wie sie zusammengehören, sagen die Docstrings und prüft
``tests/test_parts.py`` in Einbaulage über den ganzen Weg.
"""

from __future__ import annotations

import math
from typing import Final, cast

from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, intersect, pin, result, subtract, union
from app.core.knowledge.parts.mechanics import SNAP_RATIO
from app.core.knowledge.parts.registry import (
    FeatureRequirement,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.knowledge.parts.shapes import Form
from app.core.registry import op_params, param, play_param
from app.core.types import BaseParams, Feature, FeatureId, PartResult, Point2, Vec3
from app.core.units import (
    DEGREE_UNIT,
    EPS_GEOM,
    exact_atan2_degrees,
    exact_cos,
    exact_sin,
    inscribed_ratio,
)
from app.i18n import TranslatableText, _

BAYONET_ADDED = PartChange(
    version="1",
    date="2026-10-04",
    reason="Bajonettpaar aus dem Dateiaudit (RM-184, Filterkäfig).",
)

DETENT_DISC_ADDED = PartChange(
    version="1",
    date="2026-10-04",
    reason="Rastdrehscheibe mit federnder Nabe aus dem Dateiaudit (RM-184, Gewürzdeckel).",
)


# --- Formen aus Grundriss und Sektor ----------------------------------------------------


def upright(outline: list[Point2], height: float) -> Form:
    """Ein Grundriss in XY, von Z = 0 bis ``height`` aufgezogen — in beiden Kernen.

    ``shapes.prism_across`` zieht einen Umriss aus YZ quer über X auf; eine
    Vierteldrehung um Y legt diese Achse nach -Z. Deshalb wird der Umriss mit
    vertauschten Koordinaten gezeichnet und danach um die halbe Höhe gehoben.
    Beide Kerne drehen um 90 Grad exakt.
    """
    swapped = [(y, x) for x, y in outline]
    prism = shapes.turned(shapes.prism_across(swapped, height), 90.0, (0.0, 1.0, 0.0))
    return shapes.moved(prism, (0.0, 0.0, height / 2.0))


def wedge(reach: float, start: float, end: float, height: float) -> Form:
    """Ein Tortenstück von der Achse bis über ``reach`` hinaus, von ``start`` bis ``end`` Grad.

    Die Kanten sind gerade: zwei radiale Ebenen und außen ein Vieleck, dessen
    Sehnen alle außerhalb von ``reach`` liegen. Mit einem Ring geschnitten
    entsteht ein Ringsektor, dessen Bögen die des Rings bleiben — exakt im
    exakten Kern, mit derselben Facettierung am Netz.
    """
    steps = max(1, math.ceil((end - start) / 30.0))
    step = (end - start) / steps
    radius = reach / exact_cos(math.radians(step / 2.0)) + 1.0
    outline: list[Point2] = [(0.0, 0.0)]
    for index in range(steps + 1):
        angle = math.radians(start + index * step)
        outline.append((radius * exact_cos(angle), radius * exact_sin(angle)))
    return upright(outline, height)


def ring(outer: float, inner: float, height: float) -> Form:
    """Ein Rohrstück auf Z = 0, Radien gegeben — ohne Innenradius ein voller Zylinder.

    Ein Kragen, dessen Wand bis zur Achse reicht, ist ein Stopfen; ein Zylinder
    vom Durchmesser null als Werkzeug wäre kein Körper, und die Boolesche
    Kette fiele Stufe um Stufe durch (Bereichslauf, Kragen Ø 12 mit 6 mm Wand).
    """
    if inner <= EPS_GEOM:
        return shapes.cylinder(2.0 * outer, height)
    return subtract(
        shapes.cylinder(2.0 * outer, height),
        shapes.moved(shapes.cylinder(2.0 * inner, height + 2.0), (0.0, 0.0, -1.0)),
    )


def sector(outer: float, inner: float, start: float, end: float, height: float) -> Form:
    """Ein Ringsektor zwischen zwei Radien und zwei Winkeln (Grad), auf Z = 0."""
    return intersect(ring(outer, inner, height), wedge(outer, start, end, height))


def radial_box(near: float, far: float, width: float, height: float, angle: float) -> Form:
    """Ein Quader quer zur Achse: radial von ``near`` bis ``far``, ``width`` breit, gedreht."""
    box = shapes.moved(shapes.box(far - near, width, height), ((near + far) / 2.0, 0.0, 0.0))
    return shapes.turned(box, angle)


def _half_angle(half_width: float, radius: float) -> float:
    """Der halbe Öffnungswinkel einer Sehne der halben Breite ``half_width`` am Radius, in Grad.

    Über den Arkustangens des Kerns statt ``math.asin``: Dieser Winkel geht in
    die Ecken der Schlitze, und eine Winkelfunktion der Plattform gäbe auf jeder
    Maschine eine andere letzte Stelle (Regel in ``kern.md``).
    """
    if half_width >= radius:
        return 90.0
    return exact_atan2_degrees(half_width, math.sqrt(radius * radius - half_width * half_width))


def ring_width(width: float) -> float:
    """Wie weit zwei Kreise auseinanderliegen müssen, damit dazwischen ``width`` Wand steht.

    Exakt ist ein Kreis ein Kreis, und die Wand ist die Differenz der Radien.
    Am Netz ist er ein Vieleck aus ``SEGMENTS`` Ecken; zwischen zwei gleich
    ausgerichteten liegt nur ihr Abstand mal ``cos(π / SEGMENTS)``. Wie am
    Scharnierauge wird dort um den Kehrwert verbreitert, zwei
    Geometrietoleranzen halten die Boolesche Rundung im Maß.
    """
    if shapes.building_exact():
        return width
    return (width + 2.0 * EPS_GEOM) / inscribed_ratio(shapes.SEGMENTS)


def polar(radius: float, degrees: float, z: float = 0.0) -> Vec3:
    """Ein Punkt in Zylinderkoordinaten — mit den plattformgleichen Winkelfunktionen."""
    angle = math.radians(degrees)
    return (radius * exact_cos(angle), radius * exact_sin(angle), z)


# --- Bajonett ---------------------------------------------------------------------------

BAYONET_KINDS: Final = ("socket", "plug")

BAYONET_CROWDED = _(
    "Die Nocken und ihr Drehweg passen nicht nebeneinander: Zwischen zwei Schlitzen bliebe "
    "weniger als eine Wand. Weniger Nocken, schmalere Nocken oder einen kürzeren Drehweg "
    "wählen."
)


@op_params
class BayonetParams(BaseParams):
    kind: str = param(
        title=_("Hälfte"),
        default="socket",
        choices=BAYONET_KINDS,
        doc=_(
            "Die Aufnahme mit den L-Schlitzen oder der Kragen mit den Nocken. Beide aus "
            "denselben Maßen setzen, dann passen sie zusammen."
        ),
    )
    diameter: float = param(
        title=_("Durchmesser"),
        default=24.0,
        unit="mm",
        minimum=12.0,
        maximum=150.0,
        doc=_(
            "Außendurchmesser des Kragens. Die Aufnahme ist innen um das Spiel aus dem "
            "Materialprofil weiter."
        ),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=1.2,
        maximum=6.0,
        doc=_("Wand von Aufnahme und Kragen, und mindestens so breit bleibt jeder Steg."),
        placement="advanced",
    )
    lugs: int = param(
        title=_("Nocken"),
        default=3,
        minimum=2,
        maximum=4,
        doc=_("Wie viele Nocken gleichmäßig verteilt sitzen. Drei stehen wie ein Dreibein."),
    )
    lug_width: float = param(
        title=_("Nockenbreite"),
        default=6.0,
        unit="mm",
        minimum=2.0,
        maximum=20.0,
        doc=_("Breite jeder Nocke entlang des Umfangs."),
        placement="advanced",
    )
    lug_height: float = param(
        title=_("Nockenhöhe"),
        default=3.5,
        unit="mm",
        minimum=1.5,
        maximum=10.0,
        placement="advanced",
        doc=_("Höhe jeder Nocke entlang der Achse — so viel Material hält gegen Zug."),
    )
    entry: float = param(
        title=_("Einstecktiefe"),
        default=6.0,
        unit="mm",
        minimum=2.0,
        maximum=30.0,
        doc=_(
            "Wie tief der Kragen axial einfährt, bevor er gedreht wird; so viel Wand steht "
            "über dem Drehschlitz."
        ),
        placement="advanced",
    )
    turn: float = param(
        title=_("Drehweg"),
        default=13.0,
        unit=DEGREE_UNIT,
        minimum=5.0,
        maximum=60.0,
        doc=_("Wie weit gedreht wird, bis die Nocke am Ende des Schlitzes ansteht."),
        placement="advanced",
    )
    play: float = play_param()


def bayonet_frame(params: BayonetParams) -> dict[str, float]:
    """Die Maße, auf die sich beide Hälften einigen müssen — eine Rechnung für beide.

    ``bore`` ist der Innenradius der Aufnahme, ``outer`` ihr Außenradius, und
    bis dorthin reicht auch jede Nocke. Der Drehschlitz liegt eine Wand über
    dem Fuß der Aufnahme und ist um das Spiel höher als die Nocke; über ihm
    stehen bis zum Rand ``entry`` weniger das halbe Spiel. ``margin`` ist der
    halbe Öffnungswinkel des Einführschlitzes am Innenradius, ``web`` der
    Steg zwischen zwei Schlitzen als Bogen am Innenradius.
    """
    bore_radius = (params.diameter + params.play) / 2.0
    outer = bore_radius + params.wall
    slot_bottom = params.wall
    slot_top = slot_bottom + params.lug_height + params.play
    rim = slot_top + params.entry - params.play / 2.0
    half_slot = (params.lug_width + params.play) / 2.0
    margin = _half_angle(half_slot, bore_radius)
    spacing = 360.0 / params.lugs
    web = math.radians(spacing - params.turn - 2.0 * margin) * bore_radius
    return {
        "bore": bore_radius,
        "outer": outer,
        "slot_bottom": slot_bottom,
        "slot_top": slot_top,
        "rim": rim,
        "margin": margin,
        "spacing": spacing,
        "web": web,
        "collar": params.entry + params.lug_height,
    }


def _bayonet_reason(params: BayonetParams) -> TranslatableText | None:
    """Die erklärte Bedingung: Zwischen zwei L-Schlitzen bleibt eine Wand stehen."""
    frame = bayonet_frame(params)
    half_slot = (params.lug_width + params.play) / 2.0
    if half_slot >= frame["bore"] or frame["web"] < params.wall:
        return BAYONET_CROWDED
    return None


@register_part(
    name="bayonet",
    title=_("Bajonettverschluss"),
    group="mechanics",
    params=BayonetParams,
    standalone=True,
    features=("socket", "stop", "collar", "lug"),
    feature_requirements=(
        FeatureRequirement("socket", when="kind", equals="socket"),
        FeatureRequirement("stop", when="kind", equals="socket"),
        FeatureRequirement("collar", when="kind", equals="plug"),
        FeatureRequirement("lug", when="kind", equals="plug"),
    ),
    wall=WallRequirement.from_parameter("wall"),
    feasible=lambda raw: _bayonet_reason(cast(BayonetParams, raw)),
    doc=_(
        "Ein Verschluss zum Einsetzen und Drehen: Die Aufnahme trägt L-Schlitze durch ihre "
        "Wand, der Kragen die passenden Nocken. Axial einsetzen, um den Drehweg drehen, am "
        "Ende des Schlitzes steht die Nocke an. Beide Hälften aus denselben Maßen setzen."
    ),
    caveat=_(
        "Wenn der Verschluss dicht sein oder Rütteln aushalten muss. Dafür braucht er eine "
        "Dichtung und eine Rastung."
    ),
    changes=[BAYONET_ADDED],
)
def bayonet(raw: BaseParams) -> PartResult:
    """Aufnahme oder Kragen, beide auf Z = 0 stehend und nach oben wachsend.

    **Die Aufnahme** ist ein Rohr bis ``rim``. Je Nocke schneidet ein
    Einführschlitz vom Rand bis unter den Drehschlitz durch die Wand, und der
    Drehschlitz läuft von dort um ``turn`` Grad gegen den Uhrzeigersinn
    (von oben gesehen) weiter. Sein geschlossenes Ende ist der Anschlag.

    **Der Kragen** ist ein Rohr von Einstecktiefe plus Nockenhöhe; die
    Nocken sitzen an seinem freien Ende und reichen bis zum Außenradius der
    Aufnahme. Umgedreht auf die Aufnahme gesetzt, liegt sein Fuß auf ihrem
    Rand, und jede Nocke steht mit dem halben Spiel über und unter sich im
    Drehschlitz.
    """
    params = cast(BayonetParams, raw)
    reason = _bayonet_reason(params)
    if reason is not None:
        raise ValidationError("lugs", reason, constraint="feasible")
    frame = bayonet_frame(params)
    features: list[tuple[FeatureId, Feature]] = []
    if params.kind == "socket":
        return _bayonet_socket(params, frame)
    return _bayonet_plug(params, frame, features)


def _bayonet_socket(params: BayonetParams, frame: dict[str, float]) -> PartResult:
    bore_radius, outer, rim = frame["bore"], frame["outer"], frame["rim"]
    slot_bottom, slot_top = frame["slot_bottom"], frame["slot_top"]
    body = ring(outer, bore_radius, rim)
    cutters: list[Form] = []
    features: list[tuple[FeatureId, Feature]] = [
        bore("socket_1", 2.0 * bore_radius, (0.0, 0.0, rim / 2.0), depth=rim, through=True)
    ]
    slot_height = slot_top - slot_bottom
    for index in range(params.lugs):
        angle = index * frame["spacing"]
        entry = radial_box(
            0.0, outer + 1.0, params.lug_width + params.play, rim - slot_bottom + 1.0, angle
        )
        cutters.append(shapes.moved(entry, (0.0, 0.0, slot_bottom)))
        end = angle + params.turn + frame["margin"]
        turn = wedge(outer, angle - frame["margin"], end, slot_height)
        cutters.append(shapes.moved(turn, (0.0, 0.0, slot_bottom)))
        middle = (bore_radius + outer) / 2.0
        # Das Ende des Drehschlitzes, zum Schlitz hin gerichtet: dort steht die
        # Nocke an, wenn der Verschluss zu ist.
        normal = polar(1.0, end - 90.0)
        features.append(
            face(
                f"stop_{index + 1}",
                params.wall * slot_height,
                polar(middle, end, slot_bottom + slot_height / 2.0),
                normal,
            )
        )
    return result(subtract(body, *cutters), *features)


def _bayonet_plug(
    params: BayonetParams, frame: dict[str, float], features: list[tuple[FeatureId, Feature]]
) -> PartResult:
    radius = params.diameter / 2.0
    length = frame["collar"]
    body = ring(radius, radius - params.wall, length)
    lugs: list[Form] = []
    near = radius - params.wall / 2.0
    features.append(pin("collar_1", params.diameter, (0.0, 0.0, length / 2.0), length=length))
    for index in range(params.lugs):
        angle = index * frame["spacing"]
        lug = radial_box(near, frame["outer"], params.lug_width, params.lug_height, angle)
        lugs.append(shapes.moved(lug, (0.0, 0.0, params.entry)))
        # Die Haltefläche: Sie liegt zum Fuß des Kragens hin und trägt gegen den
        # Rand des Drehschlitzes, wenn am Deckel gezogen wird.
        features.append(
            face(
                f"lug_{index + 1}",
                params.lug_width * (frame["outer"] - radius),
                polar((radius + frame["outer"]) / 2.0, angle, params.entry),
                (0.0, 0.0, -1.0),
            )
        )
    return result(union(body, *lugs), *features)


# --- Rastdrehscheibe ----------------------------------------------------------------------

DETENT_KINDS: Final = ("base", "disc")

DETENT_PLAY_TOO_LARGE = _(
    "Das Spiel ist so groß wie die Federarmstärke: Arme und Rastnase griffen ins Leere. "
    "Stärkere Federarme wählen."
)
DETENT_TOO_SMALL = _(
    "Zapfen, Federnabe und Rastzunge lassen in dieser Scheibe kein Fenster frei. Einen "
    "größeren Durchmesser, einen dünneren Zapfen oder schwächere Federarme wählen."
)
DETENT_WINDOW_TOO_WIDE = _(
    "Das Fenster ist breiter als der Abstand zweier Stellungen; eine Stellung gäbe die "
    "Öffnung der nächsten mit frei. Ein schmaleres Fenster oder weniger Stellungen wählen."
)
DETENT_MARKS_CROWDED = _(
    "Die tastbaren Marken der Stellungen liefen auf dem Kragen ineinander. Weniger "
    "Stellungen, einen größeren Durchmesser oder schwächere Federarme wählen."
)

#: Wie weit zwei Rippen einer Stellungsmarke auseinanderstehen, in Rippenbreiten:
#: eine Rippe, anderthalb Rippen Lücke — mit dem Finger einzeln zu zählen.
MARK_PITCH: Final = 2.5

#: Drei Federarme, gleichmäßig verteilt, je über diesen Winkel — die Bauart aus
#: dem Gewürzdeckel, an dem 85 Grad bei 120 Grad Teilung druckbar und spürbar
#: rasteten.
HUB_ARMS: Final = 3
HUB_ARM_SPAN: Final = 85.0


@op_params
class DetentDiscParams(BaseParams):
    kind: str = param(
        title=_("Hälfte"),
        default="base",
        choices=DETENT_KINDS,
        doc=_(
            "Die Führung mit Zapfen, Rastmulden und Öffnungen oder die Drehscheibe mit "
            "Fenster, Federnabe und Rastzunge. Beide aus denselben Maßen setzen."
        ),
    )
    diameter: float = param(
        title=_("Durchmesser"),
        default=32.0,
        unit="mm",
        minimum=16.0,
        maximum=120.0,
        doc=_("Durchmesser der Drehscheibe; die Führung ist um ihren Kragen größer."),
    )
    thickness: float = param(
        title=_("Dicke"),
        default=3.0,
        unit="mm",
        minimum=1.6,
        maximum=6.0,
        doc=_("Dicke der Scheibe; so dick sind auch Boden und Kragen der Führung."),
        placement="advanced",
    )
    positions: int = param(
        title=_("Stellungen"),
        default=3,
        minimum=2,
        maximum=4,
        doc=_(
            "Wie viele Raststellungen gleichmäßig verteilt sind. In der ersten ist alles "
            "zu, jede weitere gibt eine Öffnung frei."
        ),
    )
    window: float = param(
        title=_("Fensterwinkel"),
        default=60.0,
        unit=DEGREE_UNIT,
        minimum=10.0,
        maximum=120.0,
        doc=_("Wie weit das Fenster der Scheibe und jede Öffnung der Führung reicht."),
        placement="advanced",
    )
    post: float = param(
        title=_("Zapfen"),
        default=6.0,
        unit="mm",
        minimum=3.0,
        maximum=12.0,
        doc=_("Durchmesser des mittigen Zapfens, über dessen Kopf die Federnabe schnappt."),
        placement="advanced",
    )
    arm: float = param(
        title=_("Federarmstärke"),
        default=1.1,
        unit="mm",
        minimum=0.8,
        maximum=2.0,
        doc=_(
            "Stärke der Federarme an der Nabe und der Rastzunge am Rand. Der Kopf und die "
            "Rastnase stehen eine halbe Armstärke über."
        ),
        placement="advanced",
    )
    play: float = play_param()


def detent_frame(params: DetentDiscParams) -> dict[str, float]:
    """Alle Radien und Winkel, auf die sich Führung und Scheibe einigen müssen.

    Von innen nach außen: Zapfen und Kopf, Federarme mit ihrem Federraum,
    ein Steg von einer Armstärke, das Fenster, ein zweiter Steg, der Schlitz
    hinter der Rastzunge, die Zunge selbst. Der Kopf und die Nase stehen um
    ``catch`` (eine halbe Armstärke) über; so weit federn Arme und Zunge aus.
    Die Führung trägt um den Rand der Scheibe einen Kragen mit Mulden, deren
    Grund eine Scheibendicke vor seiner Außenseite liegt.
    """
    arm, play = params.arm, params.play
    catch = arm / 2.0
    # Jede Federarm- und Stegbreite liegt zwischen zwei Kreisen.
    ring = ring_width(arm)
    radius = params.diameter / 2.0
    post = params.post / 2.0
    arm_inner = post + play / 2.0
    arm_outer = arm_inner + ring
    hub = arm_outer + catch
    window_inner = hub + ring
    tongue_inner = radius - ring
    tongue_slot = tongue_inner - (catch + play)
    window_outer = tongue_slot - ring
    nose = catch + play / 2.0
    guide = radius + play / 2.0
    notch = nose + play / 2.0
    collar = radius + notch + params.thickness
    spacing = 360.0 / params.positions
    return {
        "catch": catch,
        "radius": radius,
        "post": post,
        "head": post + catch,
        "arm_inner": arm_inner,
        "arm_outer": arm_outer,
        "hub": hub,
        "window_inner": window_inner,
        "window_outer": window_outer,
        "tongue_inner": tongue_inner,
        "tongue_slot": tongue_slot,
        "nose": nose,
        "guide": guide,
        "notch": notch,
        "collar": collar,
        "spacing": spacing,
        # Die Marken liegen auf dem Kragen hinter den Mulden.
        "mark_inner": radius + notch,
        "mark_middle": (radius + notch + collar) / 2.0,
    }


def _detent_reason(params: DetentDiscParams) -> TranslatableText | None:
    """Die erklärten Bedingungen zwischen Spiel, Radien, Fenster und Marken."""
    frame = detent_frame(params)
    if params.arm <= params.play:
        return DETENT_PLAY_TOO_LARGE
    if frame["window_outer"] - frame["window_inner"] < params.arm:
        return DETENT_TOO_SMALL
    gap = math.radians(frame["spacing"] - params.window) * frame["window_inner"]
    if gap < params.arm:
        return DETENT_WINDOW_TOO_WIDE
    group = ((params.positions - 1) * MARK_PITCH + 1.0) * params.arm
    room = math.radians(frame["spacing"]) * frame["mark_middle"] - MARK_PITCH * params.arm
    if group > room:
        return DETENT_MARKS_CROWDED
    return None


@register_part(
    name="detent_disc",
    title=_("Rastdrehscheibe"),
    group="mechanics",
    params=DetentDiscParams,
    standalone=True,
    at_face=False,
    features=("post", "guide", "detent", "hub", "nose", "grip"),
    feature_requirements=(
        FeatureRequirement("post", when="kind", equals="base"),
        FeatureRequirement("guide", when="kind", equals="base"),
        FeatureRequirement("detent", when="kind", equals="base"),
        FeatureRequirement("hub", when="kind", equals="disc"),
        FeatureRequirement("nose", when="kind", equals="disc"),
        FeatureRequirement("grip", when="kind", equals="disc"),
    ),
    wall=WallRequirement.from_parameter("arm"),
    feasible=lambda raw: _detent_reason(cast(DetentDiscParams, raw)),
    doc=_(
        "Ein Drehverschluss mit Raststellungen, etwa für einen Streudeckel. Die Führung "
        "trägt Zapfen, Kragen mit Rastmulden, tastbare Marken und je Stellung eine Öffnung, "
        "die Scheibe ein Fenster, eine federnde Nabe und eine Rastzunge. Die Scheibe wird von "
        "oben aufgeklipst und ist wieder lösbar."
    ),
    caveat=_(
        "Wenn der Deckel dicht schließen muss, denn die Scheibe liegt nur auf. Beide Teile "
        "liegend drucken."
    ),
    changes=[DETENT_DISC_ADDED],
)
def detent_disc(raw: BaseParams) -> PartResult:
    """Führung oder Drehscheibe, beide auf Z = 0, mit gemeinsamem Winkelbezug.

    **Der Winkelbezug:** Die Rastnase der Scheibe und ihr Griffsteg zeigen
    nach 180 Grad, das Fenster nach 0 Grad. Die Führung trägt bei
    ``180 + k · Teilung`` die Mulde der Stellung ``k`` samt ``k + 1``
    tastbaren Rippen, bei ``k · Teilung`` (``k ≥ 1``) eine Öffnung von der
    Größe des Fensters. In Stellung null liegt das Fenster über geschlossenem
    Boden.

    **Die Scheibe sitzt auf dem Boden der Führung** (Z = Dicke) und wird von
    oben über den Pilzkopf geklipst; die drei tangentialen Arme federn dabei
    um ``catch`` aus. Die Rastzunge am Rand ist durch einen Schlitz frei
    geschnitten und federt beim Drehen nach innen.
    """
    params = cast(DetentDiscParams, raw)
    reason = _detent_reason(params)
    if reason is not None:
        raise ValidationError("diameter", reason, constraint="feasible")
    frame = detent_frame(params)
    if params.kind == "base":
        return _detent_base(params, frame)
    return _detent_rotor(params, frame)


def _detent_base(params: DetentDiscParams, frame: dict[str, float]) -> PartResult:
    thickness = params.thickness
    collar_height = thickness + params.play
    floor = shapes.cylinder(2.0 * frame["collar"], thickness)
    collar = shapes.moved(
        ring(frame["collar"], frame["guide"], collar_height + BOOLEAN_OVERLAP),
        (0.0, 0.0, thickness - BOOLEAN_OVERLAP),
    )
    # Der Kopf beginnt um das halbe Spiel über der aufgesetzten Scheibe; seine
    # Halteflanke steigt unter 45 Grad um ``catch``, der Einführkegel darüber
    # läuft ebenso steil auf den halben Zapfenradius zu.
    head_base = 2.0 * thickness + params.play / 2.0
    stem, head, tip = frame["post"], frame["head"], frame["post"] / 2.0
    flank = head_base + frame["catch"]
    crown = flank + head - tip
    post = shapes.revolved(
        [
            (0.0, thickness - BOOLEAN_OVERLAP),
            (stem, thickness - BOOLEAN_OVERLAP),
            (stem, head_base),
            (head, flank),
            (tip, crown),
            (0.0, crown),
        ]
    )
    marks: list[Form] = []
    cutters: list[Form] = []
    features: list[tuple[FeatureId, Feature]] = [
        pin(
            "post_1",
            params.post,
            (0.0, 0.0, (thickness + head_base) / 2.0),
            length=head_base - thickness,
        ),
        bore(
            "guide_1",
            2.0 * frame["guide"],
            (0.0, 0.0, thickness + collar_height / 2.0),
            depth=collar_height,
        ),
    ]
    top = thickness + collar_height
    for index in range(params.positions):
        angle = 180.0 + index * frame["spacing"]
        notch = shapes.cylinder(2.0 * frame["notch"], collar_height + BOOLEAN_OVERLAP)
        centre = polar(frame["radius"], angle)
        # Die Mulde beginnt auf dem Boden: Darunter ist er voll, darüber fehlt der Kragen.
        cutters.append(shapes.moved(notch, (centre[0], centre[1], thickness)))
        features.append(
            bore(
                f"detent_{index + 1}",
                2.0 * frame["notch"],
                polar(frame["radius"], angle, thickness + collar_height / 2.0),
                depth=collar_height,
            )
        )
        pitch = math.degrees(MARK_PITCH * params.arm / frame["mark_middle"])
        for rib in range(index + 1):
            offset = (rib - index / 2.0) * pitch
            mark = radial_box(
                frame["mark_inner"],
                frame["collar"],
                params.arm,
                params.arm + BOOLEAN_OVERLAP,
                angle + offset,
            )
            marks.append(shapes.moved(mark, (0.0, 0.0, top - BOOLEAN_OVERLAP)))
        if index:
            opening = sector(
                frame["window_outer"],
                frame["window_inner"],
                index * frame["spacing"] - params.window / 2.0,
                index * frame["spacing"] + params.window / 2.0,
                thickness + 2.0 * BOOLEAN_OVERLAP,
            )
            cutters.append(shapes.moved(opening, (0.0, 0.0, -BOOLEAN_OVERLAP)))
    body = subtract(union(floor, collar, post, *marks), *cutters)
    return result(body, *features)


def _detent_rotor(params: DetentDiscParams, frame: dict[str, float]) -> PartResult:
    thickness = params.thickness
    radius = frame["radius"]
    disc = shapes.cylinder(2.0 * radius, thickness)
    tall = thickness + 2.0 * BOOLEAN_OVERLAP
    lowered = (0.0, 0.0, -BOOLEAN_OVERLAP)
    nose_angle = _half_angle(frame["nose"], radius)
    clear = math.degrees(params.arm / radius)
    free_end = 180.0 + nose_angle + clear
    span = math.degrees(SNAP_RATIO * params.arm / radius)
    slot = frame["catch"] + params.play
    cutters: list[Form] = [
        shapes.moved(shapes.cylinder(2.0 * frame["hub"], tall), lowered),
        shapes.moved(
            sector(
                frame["window_outer"],
                frame["window_inner"],
                -params.window / 2.0,
                params.window / 2.0,
                tall,
            ),
            lowered,
        ),
        # Der Schlitz hinter der Rastzunge und ihr freies Ende.
        shapes.moved(
            sector(
                frame["tongue_inner"],
                frame["tongue_slot"],
                free_end - span,
                free_end + math.degrees(slot / radius),
                tall,
            ),
            lowered,
        ),
        shapes.moved(
            radial_box(
                frame["tongue_slot"] - BOOLEAN_OVERLAP,
                radius + 1.0,
                slot,
                tall,
                free_end + math.degrees(slot / (2.0 * radius)),
            ),
            lowered,
        ),
    ]
    added: list[Form] = []
    for index in range(HUB_ARMS):
        start = index * 360.0 / HUB_ARMS
        added.append(
            sector(
                frame["arm_outer"],
                frame["arm_inner"],
                start,
                start + HUB_ARM_SPAN,
                thickness,
            )
        )
        # Der Steg, der den Arm an seinem festen Ende mit der Scheibe verbindet.
        added.append(
            radial_box(
                frame["arm_inner"] + params.arm / 2.0,
                frame["hub"] + params.arm / 2.0,
                params.arm,
                thickness,
                start + math.degrees(params.arm / (2.0 * frame["arm_outer"])),
            )
        )
    nose_centre = polar(radius, 180.0)
    added.append(shapes.moved(shapes.cylinder(2.0 * frame["nose"], thickness), nose_centre))
    # Der Griffsteg zeigt auf die Rastnase und damit auf die Marke der Stellung.
    grip = radial_box(
        frame["window_inner"],
        frame["window_outer"],
        2.0 * params.arm,
        thickness + BOOLEAN_OVERLAP,
        180.0,
    )
    added.append(shapes.moved(grip, (0.0, 0.0, thickness - BOOLEAN_OVERLAP)))
    body = union(subtract(disc, *cutters), *added)
    grip_length = frame["window_outer"] - frame["window_inner"]
    return result(
        body,
        bore(
            "hub_1",
            2.0 * frame["arm_inner"],
            (0.0, 0.0, thickness / 2.0),
            depth=thickness,
            through=True,
        ),
        pin("nose_1", 2.0 * frame["nose"], polar(radius, 180.0, thickness / 2.0), length=thickness),
        face(
            "grip_1",
            2.0 * params.arm * grip_length,
            polar((frame["window_inner"] + frame["window_outer"]) / 2.0, 180.0, 2.0 * thickness),
        ),
    )
