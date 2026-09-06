"""Prüfkörper für die Kalibrierung (Bauplan §28.3).

Drei davon, und jeder beantwortet genau eine Frage, die ein Druckerprofil
stellt:

* die **Toleranzleiter** — Stifte und Bohrungen mit gestaffeltem Spiel: welcher
  Spalt gleitet und welcher klemmt;
* die **Wandstärkenleiter** — Wände von einer bis mehreren Extrusionsbreiten: wo
  der Drucker aufhört, Material abzulegen;
* der **Überhangfächer** — Flächen von senkrecht bis fast flach: wo Stützen
  wirklich nötig werden.

Einmal gedruckt, gemessen, und die Werte gehen ins Materialprofil (§28.3) — von
dort erreichen sie jedes bestehende Projekt, denn Toleranzen im Stapel sind
Verweise (§12).

Die Körper tragen ihre Nummern als eingravierte Striche — so viele, wie die
Stufe zählt —, denn eine gedruckte Leiter ohne Beschriftung ist am nächsten
Morgen ein Rätsel. Keine Schrift und nichts Erhabenes: Eine Schrift wäre eine
Abhängigkeit, und ein aufgesetztes Zeichen bräuchte Stützen, wo es übersteht.
"""

from __future__ import annotations

import math
from typing import cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.geom.mesh import MeshData
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, pin, result, subtract, union
from app.core.knowledge.parts.registry import (
    FACE_GIVES_DIRECTION,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.core.units import DEGREE_UNIT
from app.i18n import _

WALL_LADDER_SEPARATE_STEPS = PartChange(
    version="15",
    date="2026-09-06",
    reason="Breitere Messwände überlappten ihre Nachbarn.",
    effect="Jede Stufe bleibt einzeln messbar; die Sockelbreite wächst um alle Wandstärken und "
    "Zwischenräume.",
)

OVERHANG_FROM_VERTICAL = PartChange(
    version="15",
    date="2026-09-06",
    reason="Die angegebene Senkrechte war durch vertauschte Sinus- und Kosinusanteile zur "
    "Waagerechten geworden.",
    effect="Jede Rampe hat ihren eingetragenen Winkel zur Senkrechten. Kombinationen mit einem "
    "letzten Winkel ab 90 Grad werden vor dem Bauen erklärt.",
)

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Testkörper für die Selbstkalibrierung (§28.3)."
)

FIT_LADDER_KEEPS_EACH_PAIR_SEPARATE = PartChange(
    version="13",
    date="2026-08-31",
    reason=(
        "Großes Spiel konnte bei kleinem Nenndurchmesser benachbarte Bohrungen "
        "verbinden und die Grundplatte zerlegen."
    ),
    effect=(
        "Abstand und Plattentiefe richten sich jetzt auch nach der größten "
        "Bohrung; Nennmaße, Spielstufen und Höhe bleiben unverändert."
    ),
)

FIT_LADDER_NUMBERS_ITS_STEPS = PartChange(
    version="14",
    date="2026-09-02",
    reason=(
        "Die Beschriftung zählte die letzte Ziffer des Spiels statt der Stufe: "
        "bei der Vorgabe trugen Stufe 1 und 3 dieselben Striche, bei Schritt "
        "0,10 alle vier."
    ),
    effect=(
        "Jede Stufe trägt so viele eingravierte Striche wie ihre Nummer; Maße, "
        "Spiele und Höhe bleiben unverändert."
    ),
)

#: Höhe der eingravierten Beschriftungen. Zwei Schichten zu 0,2 mm — lesbar,
#: billig.
LABEL_DEPTH = 0.4


@op_params
class FitLadderParams(BaseParams):
    diameter: float = param(
        title=_("Nenndurchmesser"),
        default=6.0,
        unit="mm",
        minimum=2.0,
        maximum=30.0,
        doc=_(
            "Durchmesser von Zapfen und Bohrung. Am besten der, den das Teil "
            "später wirklich benutzt — Spiel verhält sich nicht über alle Größen gleich."
        ),
    )
    steps: int = param(
        title=_("Stufen"),
        default=4,
        minimum=2,
        maximum=8,
        doc=_("Wie viele Paare gedruckt werden. Vier reichen meistens, um den Wert einzugrenzen."),
    )
    first: float = param(
        title=_("Kleinstes Spiel"),
        default=0.10,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        doc=_("Womit die Leiter anfängt. Die erste Stufe darf ruhig zu stramm sein."),
    )
    step: float = param(
        title=_("Schrittweite"),
        default=0.05,
        unit="mm",
        minimum=0.01,
        maximum=0.5,
        doc=_("Um wie viel das Spiel von Stufe zu Stufe wächst."),
    )
    height: float = param(
        title=_("Höhe"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=40.0,
        doc=_("Höhe der Zapfen. Höher heißt länger drucken, aber ehrlicher fügen."),
    )


@register_part(
    name="fit_ladder",
    title=_("Toleranz-Testkörper"),
    group="calibration",
    # Ein Prüfkörper wird gedruckt und gemessen, nicht angebaut (§24.3).
    at_face=False,
    params=FitLadderParams,
    features=["pin", "bore", "face"],
    wall=WallRequirement.not_applicable(
        "Der Kalibrierkörper vermisst diese Druckgrenze und darf sie deshalb unterschreiten."
    ),
    doc=_(
        "Zapfen und Bohrungen mit gestaffeltem Spiel. Einmal drucken, ausprobieren, "
        "und der Wert steht — er gehört danach ins Materialprofil, nicht ins Modell."
    ),
    changes=[
        FIRST_RELEASE,
        FACE_GIVES_DIRECTION,
        FIT_LADDER_KEEPS_EACH_PAIR_SEPARATE,
        FIT_LADDER_NUMBERS_ITS_STEPS,
    ],
)
def fit_ladder(raw: BaseParams) -> PartResult:
    params = cast(FitLadderParams, raw)
    largest_bore = params.diameter + params.first + params.step * (params.steps - 1)
    spacing = max(params.diameter * 2.2, largest_bore * 1.5)
    base_height = 3.0
    width = spacing * params.steps + spacing
    base = shapes.box(width, spacing * 2.4, base_height)

    bodies = [base]
    features = [face("face_1", width * spacing * 2.4, (0.0, 0.0, base_height))]
    cutters = []

    for index in range(params.steps):
        play = params.first + params.step * index
        x = -width / 2.0 + spacing * (index + 1)

        stud = shapes.cylinder(params.diameter, params.height)
        bodies.append(shapes.moved(stud, (x, -spacing * 0.6, base_height)))
        features.append(
            pin(
                f"pin_{index + 1}",
                params.diameter,
                (x, -spacing * 0.6, base_height + params.height / 2.0),
                length=params.height,
            )
        )

        hole = shapes.cylinder(params.diameter + play, base_height + 2.0 * BOOLEAN_OVERLAP)
        cutters.append(shapes.moved(hole, (x, spacing * 0.6, -BOOLEAN_OVERLAP)))
        features.append(
            bore(
                f"bore_{index + 1}",
                params.diameter + play,
                (x, spacing * 0.6, base_height / 2.0),
                depth=base_height,
                through=True,
            )
        )
        cutters.append(_label(index + 1, (x, 0.0, base_height - LABEL_DEPTH)))

    body = subtract(union(*bodies), *cutters)
    return result(body, *features)


@op_params
class WallLadderParams(BaseParams):
    extrusion: float = param(
        title=_("Extrusionsbreite"),
        default=0.42,
        unit="mm",
        minimum=0.2,
        maximum=1.2,
        doc=_(
            "Wie breit dieser Drucker eine Bahn legt — meist etwas mehr als der "
            "Düsendurchmesser. Jede Stufe der Leiter ist eine Bahn dicker als die davor."
        ),
    )
    steps: int = param(
        title=_("Stufen"),
        default=6,
        minimum=2,
        maximum=10,
        doc=_("Wie viele Wände nebeneinander stehen, jede eine Extrusionsbreite dicker."),
    )
    height: float = param(
        title=_("Höhe"),
        default=15.0,
        unit="mm",
        minimum=3.0,
        maximum=60.0,
        doc=_("Höhe der Wände. Hoch genug, dass eine zu dünne Wand auch wirklich umfällt."),
    )
    length: float = param(
        title=_("Länge"),
        default=25.0,
        unit="mm",
        minimum=5.0,
        maximum=120.0,
        doc=_("Länge jeder Wand."),
    )


@register_part(
    name="wall_ladder",
    title=_("Wandstärkenleiter"),
    group="calibration",
    # Ein Prüfkörper wird gedruckt und gemessen, nicht angebaut (§24.3).
    at_face=False,
    params=WallLadderParams,
    features=["face"],
    wall=WallRequirement.from_parameter("extrusion"),
    doc=_(
        "Wände von einer bis mehreren Extrusionsbreiten. Zeigt, ab wann der Drucker "
        "wirklich noch Material legt — die Grundlage für die Mindestwandstärke."
    ),
    changes=[FIRST_RELEASE, FACE_GIVES_DIRECTION, WALL_LADDER_SEPARATE_STEPS],
)
def wall_ladder(raw: BaseParams) -> PartResult:
    params = cast(WallLadderParams, raw)
    base_height = 2.0
    gap = params.extrusion * 6.0
    thicknesses = [params.extrusion * (index + 1) for index in range(params.steps)]
    width = sum(thicknesses) + gap * (params.steps + 1)

    base = shapes.box(width, params.length, base_height)
    bodies = [base]
    left = -width / 2.0 + gap
    for thickness in thicknesses:
        x = left + thickness / 2.0
        wall = shapes.box(thickness, params.length, params.height)
        bodies.append(shapes.moved(wall, (x, 0.0, base_height)))
        left += thickness + gap

    body = union(*bodies)
    return result(
        body,
        face("face_1", width * params.length, (0.0, 0.0, base_height)),
    )


@op_params
class OverhangFanParams(BaseParams):
    first: float = param(
        title=_("Kleinster Winkel"),
        default=20.0,
        unit=DEGREE_UNIT,
        minimum=5.0,
        maximum=80.0,
        doc=_("Die steilste Fläche, gemessen gegen die Senkrechte. Kleiner heißt steiler."),
    )
    step: float = param(
        title=_("Schrittweite"),
        default=10.0,
        unit=DEGREE_UNIT,
        minimum=2.0,
        maximum=30.0,
        doc=_("Um wie viel Grad jede Fläche flacher wird als die vorige."),
    )
    steps: int = param(
        title=_("Stufen"),
        default=6,
        minimum=2,
        maximum=10,
        doc=_("Wie viele Winkel geprüft werden."),
    )
    width: float = param(
        title=_("Breite je Stufe"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        doc=_("Breite einer einzelnen Fläche. Schmaler spart Zeit, breiter zeigt mehr."),
    )
    length: float = param(
        title=_("Auskraglänge"),
        default=15.0,
        unit="mm",
        minimum=3.0,
        doc=_("Wie weit jede Fläche frei hinaussteht. Zu kurz verzeiht der Drucker alles."),
    )


@register_part(
    name="overhang_fan",
    title=_("Überhangfächer"),
    group="calibration",
    # Ein Prüfkörper wird gedruckt und gemessen, nicht angebaut (§24.3).
    at_face=False,
    params=OverhangFanParams,
    features=["face"],
    wall=WallRequirement.not_applicable(
        "Der Kalibrierkörper vermisst diese Druckgrenze und darf sie deshalb unterschreiten."
    ),
    doc=_(
        "Flächen von steil bis flach. Zeigt, ab welchem Winkel dieser Drucker mit "
        "diesem Material wirklich Stützen braucht — statt der Faustregel 45 Grad."
    ),
    changes=[FIRST_RELEASE, FACE_GIVES_DIRECTION, OVERHANG_FROM_VERTICAL],
)
def overhang_fan(raw: BaseParams) -> PartResult:
    params = cast(OverhangFanParams, raw)
    last = params.first + params.step * (params.steps - 1)
    if last >= 90.0:
        raise ValidationError(
            "steps",
            _(
                "Der letzte Winkel erreicht oder überschreitet 90 Grad. Weniger Stufen, eine "
                "kleinere Schrittweite oder einen kleineren Anfangswinkel wählen."
            ),
            values={"last_angle": last},
        )
    base_height = 3.0
    total = params.width * params.steps
    depth = 6.0
    base = shapes.box(total, depth, base_height)
    bodies = [base]
    # Die Rampen beginnen im Sockel und reichen ein Haar in ihn hinein: eine
    # Form, die nur berührt, ist eine Form, die abfällt (§39).
    start = depth / 2.0 - 1.0

    for index in range(params.steps):
        degrees = params.first + params.step * index
        angle = math.radians(degrees)
        x = -total / 2.0 + params.width * (index + 0.5)
        reach = params.length * math.sin(angle)
        rise = params.length * math.cos(angle)
        bodies.append(
            shapes.moved(
                _ramp(params.width, reach, rise), (x, start, base_height - BOOLEAN_OVERLAP)
            )
        )

    body = union(*bodies)
    return result(body, face("face_1", total * depth, (0.0, 0.0, base_height)))


def _ramp(width: float, reach: float, rise: float) -> MeshData:
    """Ein Keil, der über nichts hinauslehnt — die Form, aus der ein
    Überhangtest besteht.
    """
    points = np.array(
        [
            [-width / 2.0, 0.0, 0.0],
            [width / 2.0, 0.0, 0.0],
            [width / 2.0, reach, rise],
            [-width / 2.0, reach, rise],
            [-width / 2.0, 0.0, rise],
            [width / 2.0, 0.0, rise],
        ],
        dtype=float,
    )
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 5, 1],
            [4, 1, 0],
            [3, 2, 5],
            [3, 5, 4],
            [1, 5, 2],
            [0, 3, 4],
        ],
        dtype=np.int64,
    )
    body = trimesh.Trimesh(vertices=points, faces=faces, process=True)
    trimesh.repair.fix_normals(body)
    return MeshData.of(body)


def _label(step: int, position: tuple[float, float, float]) -> MeshData:
    """Die Stufennummer als eingravierter Strichcode: ``step`` Striche.

    Keine Schrift: eine Schrift ist eine Abhängigkeit, eine Lizenzfrage und ein
    Rendering-Problem zugleich (§36). Gebraucht wird hier nur, vier Stufen
    auseinanderzuhalten, und so viele kleine Striche wie die Stufennummer tun
    das auf dem Druckbett.

    **Gezählt wurde bis zum 02.09.2026 die letzte Ziffer des Spiels** — nicht
    die Stufe, obwohl der Satz darüber sie seit je verspricht: 0,10 gab zehn
    Striche, 0,15 fünf, 0,20 wieder zehn. Mit der Vorgabe der Leiter (0,10 mm,
    Schritt 0,05 mm) trugen Stufe eins und drei dieselbe Zahl und Stufe zwei
    und vier ebenfalls; mit Schrittweite 0,10 mm waren alle vier gleich. Auf
    einem Körper, dessen einziger Zweck es ist, Spiele auseinanderzuhalten,
    ist das keine Ungenauigkeit, sondern der Verlust der Messung: Wer die
    gedruckte Leiter in die Hand nimmt, kann die passende Stufe nicht mehr
    benennen.

    Die Stufennummer statt des Werts, und zwar aus zwei Gründen: Sie ist
    eindeutig, und sie bleibt es für jede Kombination aus erstem Spiel und
    Schrittweite. Welches Spiel zu welcher Stufe gehört, sagt der Dialog, aus
    dem der Körper kommt.
    """
    count = max(1, int(step))
    bars = []
    for index in range(count):
        bar = shapes.box(0.8, 3.0, LABEL_DEPTH + BOOLEAN_OVERLAP)
        bars.append(
            shapes.moved(bar, (position[0] + index * 1.4 - count * 0.7, position[1], position[2]))
        )
    return union(*bars)
