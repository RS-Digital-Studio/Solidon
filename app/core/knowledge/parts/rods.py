"""Steckhülse und Stangenverbinder (Bauplan §24.1, Gruppe „Struktur“).

Hier liegt der Stangenverbinder: eine Aufnahme für eine runde Stange mit
Anschlag, als einzelne Steckhülse oder als Zwei-, Drei- und Vierwegeverbinder
aus derselben Aufnahme. Er kommt aus dem Dateiaudit (RM-184, Familie 5): Das
Pflanzen-Ständerset baut sieben Systemteile aus einer einzigen Hülse — Stab
Ø 16, Einstecktiefe 42, Wand 3, innerer Anschlag, Klemmschraube —, und keiner
der vorhandenen Bausteine (Passstift, Rohrschelle, Kabelclip) ersetzt diese
gemeinsame Stabaufnahme.

**Eine Aufnahme, alle Bauformen.** Stabmaß, Spiel, Wand, Einstecktiefe und
Klemmschraube gelten für jede Hülse eines Verbinders gleich; wer das Stabmaß
als Projektparameter anlegt (Vorlage), ändert damit jede Aufnahme jedes
Verbinders im Projekt zugleich — die Abnahme aus dem Audit.
"""

from __future__ import annotations

import math
from typing import Final, cast

from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, result, subtract, union
from app.core.knowledge.parts.registry import (
    FeatureRequirement,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.knowledge.parts.shapes import Form
from app.core.registry import op_params, param, play_param
from app.core.types import BaseParams, Feature, FeatureId, PartResult, Vec3
from app.i18n import TranslatableText, _

ROD_CONNECTOR_ADDED = PartChange(
    version="1",
    date="2026-10-04",
    reason="Steckhülse und Stangenverbinder aus dem Dateiaudit (RM-184, Pflanzen-Ständerset).",
)

#: Die Bauformen, in der Reihenfolge ihrer Wegezahl. Jede ist eine Liste von
#: Richtungen, in die eine Aufnahme zeigt; waagerechte Aufnahmen liegen mit
#: ihrer Unterseite auf der Fläche, die senkrechte steht auf dem Knoten.
ROD_LAYOUTS: Final[dict[str, tuple[Vec3, ...]]] = {
    "sleeve": ((0.0, 0.0, 1.0),),
    "straight": ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
    "elbow": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "tee": ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "corner_3d": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "cross": ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)),
}

#: Die Klemmschrauben: ein Kernloch quer durch die Wand, in das die Schraube
#: ihr Gewinde selbst schneidet und dann gegen die Stange drückt. Das Maß ist
#: ``tap`` aus der Normteiltabelle. Mehr als M5 trägt eine Hülse dieser Wand
#: nicht: Die Schraube schneidet ihr Gewinde in eine Wand von 1,2 bis 8 mm. Das
#: ist die eine Größenreihe, die nicht der Tabelle folgt (RM-578), und ihr Grund
#: ist die Wand, nicht der Bereichstest.
ROD_SCREWS: Final = (
    "none",
    *(size for size in ("M3", "M4", "M5") if size in standards.screw_sizes()),
)

ROD_SCREW_TOO_THICK = _(
    "Die Klemmschraube ist dicker als die Stange und drückte neben sie. Eine kleinere "
    "Schraube oder eine dickere Stange wählen."
)


@op_params
class RodConnectorParams(BaseParams):
    layout: str = param(
        title=_("Bauform"),
        default="corner_3d",
        choices=tuple(ROD_LAYOUTS),
        doc=_(
            "Eine Steckhülse allein oder ein Verbinder aus zwei, drei oder vier gleichen "
            "Aufnahmen: gerade, im Winkel, als T-Stück, als Raumecke oder als Kreuz."
        ),
    )
    rod: float = param(
        title=_("Stab"),
        default=16.0,
        unit="mm",
        minimum=4.0,
        maximum=50.0,
        doc=_(
            "Außendurchmesser der Stange, an ihr gemessen. Das Spiel aus dem Materialprofil "
            "kommt dazu; ein unrunder Stab wird an seiner dicksten Stelle gemessen."
        ),
    )
    depth: float = param(
        title=_("Einstecktiefe"),
        default=42.0,
        unit="mm",
        minimum=8.0,
        maximum=100.0,
        doc=_(
            "Wie tief die Stange in jede Aufnahme gesteckt wird, bis sie am Anschlag ansteht. "
            "Tiefer hält gegen Kippen."
        ),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=3.0,
        unit="mm",
        minimum=1.2,
        maximum=8.0,
        doc=_("Material um die Stange und zwischen den Anschlägen."),
        placement="advanced",
    )
    screw: str = param(
        title=_("Klemmschraube"),
        default="none",
        choices=ROD_SCREWS,
        doc=_(
            "Ein Kernloch quer durch jede Aufnahme. Die Schraube schneidet ihr Gewinde selbst "
            "und klemmt die Stange; ohne steckt sie nur."
        ),
        placement="advanced",
    )
    play: float = play_param()


def _rod_reason(params: RodConnectorParams) -> TranslatableText | None:
    """Die erklärte Bedingung: Die Klemmschraube trifft die Stange und nicht daneben."""
    if params.screw == "none":
        return None
    return ROD_SCREW_TOO_THICK if standards.screw(params.screw).tap >= params.rod else None


def rod_hub(params: RodConnectorParams) -> float:
    """Die halbe Kantenlänge des Knotens, in dem sich die Aufnahmen treffen.

    Eine halbe Wand größer als die Aufnahmen: So steht keine Außenfläche einer
    Aufnahme bündig oder tangential an einer Knotenfläche — beides sind die
    Stellen, an denen eine Boolesche Vereinigung entartet (§39) —, und die
    Anschläge zweier rechtwinkliger Aufnahmen liegen √2 · 1,5 Wände
    auseinander statt sich zu schneiden. Im Quellskript des Ständersets begann
    die Bohrung 6 mm hinter der Mitte bei 8,45 mm Bohrungsradius: Die Enden
    zweier Stangen in der Ecke stießen ineinander.
    """
    return (params.rod + params.play) / 2.0 + 1.5 * params.wall


def _lying(diameter: float, length: float) -> Form:
    """Ein Zylinder entlang +X, auf der Achse beginnend — beide Kerne drehen exakt um 90 Grad."""
    return shapes.turned(shapes.cylinder(diameter, length), 90.0, (0.0, 1.0, 0.0))


def _turn_of(direction: Vec3) -> float:
    """Der Winkel um Z, der +X auf eine waagerechte Richtung dreht — nur rechte Winkel."""
    return {(1, 0): 0.0, (0, 1): 90.0, (-1, 0): 180.0, (0, -1): 270.0}[
        (round(direction[0]), round(direction[1]))
    ]


@register_part(
    name="rod_connector",
    play_inside=True,
    title=_("Steckhülse und Stangenverbinder"),
    group="structure",
    params=RodConnectorParams,
    standalone=True,
    template=True,
    features=("socket", "stop", "screw"),
    feature_requirements=(
        FeatureRequirement("socket"),
        FeatureRequirement("stop"),
        FeatureRequirement("screw", unless="screw", unless_equals="none"),
    ),
    wall=WallRequirement.from_parameter("wall"),
    feasible=lambda raw: _rod_reason(cast(RodConnectorParams, raw)),
    doc=_(
        "Aufnahmen für runde Stangen mit festem Anschlag. Eine Steckhülse allein oder ein "
        "Verbinder mit zwei, drei oder vier gleichen Aufnahmen für Rankgerüste, Gestelle "
        "und Rahmen. Stabmaß, Einstecktiefe und Klemmschraube gelten für jede Aufnahme."
    ),
    caveat=_(
        "Für unrunde oder schwankende Stäbe ohne Klemmschraube, denn die Aufnahme ist rund. "
        "Bambus an der dicksten Stelle messen."
    ),
    changes=[ROD_CONNECTOR_ADDED],
)
def rod_connector(raw: BaseParams) -> PartResult:
    """Vierkantige Aufnahmen mit runder Bohrung um einen Knoten, unten flach.

    **Vierkant außen, rund innen.** Eine waagerechte runde Hülse hätte unten
    einen Überhang bis zur Berührungslinie mit dem Druckbett und bräuchte
    Stützen; vierkantig liegt jede waagerechte Aufnahme mit ihrer ganzen
    Unterseite auf, und die engste Wand neben der Bohrung ist genau die
    eingetragene Wandstärke. Die Steckhülse allein steht senkrecht auf ihrem
    Boden, der eine Wand dick ist.

    **Der Anschlag ist die Knotenfläche** (bei der Hülse ihr Boden): Die
    Bohrung beginnt dort, und die Stange steht an ihr an. Die Klemmschraube
    sitzt in der Mitte der Einstecktiefe, bei waagerechten Aufnahmen von oben
    — ein senkrechtes Loch, das ohne Stütze druckt.
    """
    params = cast(RodConnectorParams, raw)
    reason = _rod_reason(params)
    if reason is not None:
        raise ValidationError("screw", reason, constraint="feasible")
    bore_diameter = params.rod + params.play
    outer = bore_diameter + 2.0 * params.wall
    half = outer / 2.0
    tap = standards.screw(params.screw).tap if params.screw != "none" else 0.0
    features: list[tuple[FeatureId, Feature]] = []
    cutters: list[Form] = []

    if params.layout == "sleeve":
        floor = params.wall
        body = shapes.box(outer, outer, floor + params.depth)
        cutters.append(
            shapes.moved(
                shapes.cylinder(bore_diameter, params.depth + BOOLEAN_OVERLAP), (0, 0, floor)
            )
        )
        mid = floor + params.depth / 2.0
        features.extend(_socket(1, bore_diameter, params.depth, (0.0, 0.0, mid), (0.0, 0.0, 1.0)))
        features.append(_stop(1, bore_diameter, (0.0, 0.0, floor), (0.0, 0.0, 1.0)))
        if tap:
            cutters.append(shapes.moved(_lying(tap, half + BOOLEAN_OVERLAP), (0.0, 0.0, mid)))
            features.append(_screw(1, tap, (half / 2.0, 0.0, mid), (1.0, 0.0, 0.0), half))
        return result(subtract(body, *cutters), *features)

    hub = rod_hub(params)
    axis_height = half
    sockets: list[Form] = [shapes.moved(shapes.box(2.0 * hub, 2.0 * hub, 2.0 * hub), (0, 0, 0))]
    for index, direction in enumerate(ROD_LAYOUTS[params.layout], start=1):
        if direction[2] > 0.5:
            # Senkrecht auf dem Knoten: von seiner Mitte bis eine Einstecktiefe
            # über seine Oberseite, damit die Aufnahme im Knoten verankert ist.
            top = 2.0 * hub
            column = shapes.box(outer, outer, top + params.depth - axis_height)
            sockets.append(shapes.moved(column, (0.0, 0.0, axis_height)))
            cutters.append(
                shapes.moved(
                    shapes.cylinder(bore_diameter, params.depth + BOOLEAN_OVERLAP), (0.0, 0.0, top)
                )
            )
            mid = top + params.depth / 2.0
            features.extend(_socket(index, bore_diameter, params.depth, (0.0, 0.0, mid), direction))
            features.append(_stop(index, bore_diameter, (0.0, 0.0, top), direction))
            if tap:
                cutters.append(shapes.moved(_lying(tap, half + BOOLEAN_OVERLAP), (0.0, 0.0, mid)))
                features.append(_screw(index, tap, (half / 2.0, 0.0, mid), (1.0, 0.0, 0.0), half))
            continue
        turn = _turn_of(direction)
        length = hub + params.depth
        arm = shapes.moved(shapes.box(length, outer, outer), (length / 2.0, 0.0, 0.0))
        sockets.append(shapes.turned(arm, turn))
        hole = shapes.moved(
            _lying(bore_diameter, params.depth + BOOLEAN_OVERLAP), (hub, 0.0, axis_height)
        )
        cutters.append(shapes.turned(hole, turn))
        mid = hub + params.depth / 2.0
        centre = (direction[0] * mid, direction[1] * mid, axis_height)
        features.extend(_socket(index, bore_diameter, params.depth, centre, direction))
        stop = (direction[0] * hub, direction[1] * hub, axis_height)
        features.append(_stop(index, bore_diameter, stop, direction))
        if tap:
            drilled = shapes.moved(
                shapes.cylinder(tap, half + BOOLEAN_OVERLAP), (mid, 0.0, axis_height)
            )
            cutters.append(shapes.turned(drilled, turn))
            features.append(
                _screw(
                    index,
                    tap,
                    (centre[0], centre[1], axis_height + half / 2.0),
                    (0.0, 0.0, 1.0),
                    half,
                )
            )
    return result(subtract(union(*sockets), *cutters), *features)


def _socket(
    index: int, diameter: float, depth: float, centre: Vec3, axis: Vec3
) -> list[tuple[FeatureId, Feature]]:
    """Die Aufnahme als benannte Bohrung — an ihr richtet sich eine Passung aus."""
    return [bore(f"socket_{index}", diameter, centre, depth=depth, axis=axis)]


def _stop(index: int, diameter: float, centre: Vec3, normal: Vec3) -> tuple[FeatureId, Feature]:
    """Der Anschlag am Grund der Aufnahme, zur Mündung gerichtet."""
    return face(f"stop_{index}", math.pi * diameter * diameter / 4.0, centre, normal)


def _screw(
    index: int, diameter: float, centre: Vec3, axis: Vec3, length: float
) -> tuple[FeatureId, Feature]:
    """Das Kernloch der Klemmschraube, von der Achse bis durch die Wand."""
    return bore(f"screw_{index}", diameter, centre, depth=length, axis=axis, through=True)
