"""Prüfkörper für die Kalibrierung (Bauplan §28.3).

Drei davon, und jeder beantwortet genau eine Frage, die ein Druckerprofil
stellt:

* die **Toleranzleiter** — Stifte und Bohrungen mit gestaffeltem Spiel: welcher
  Spalt gleitet und welcher klemmt;
* die **Wandstärkenleiter** — Wände von einer bis sechs Extrusionsbreiten: wo
  der Drucker aufhört, Material abzulegen;
* der **Überhangfächer** — Flächen von senkrecht bis fast flach: wo Stützen
  wirklich nötig werden.

Einmal gedruckt, gemessen, und die Werte gehen ins Materialprofil (§28.3) — von
dort erreichen sie jedes bestehende Projekt, denn Toleranzen im Stapel sind
Verweise (§12).

Die Körper tragen ihre Zahlen als erhabene Schrift, denn eine gedruckte Leiter
ohne Beschriftung ist am nächsten Morgen ein Rätsel.
"""

from __future__ import annotations

import math
from typing import cast

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, pin, result, subtract, union
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.core.units import DEGREE_UNIT
from app.i18n import _

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Testkörper für die Selbstkalibrierung (§28.3)."
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
    params=FitLadderParams,
    features=["pin", "bore"],
    doc=_(
        "Zapfen und Bohrungen mit gestaffeltem Spiel. Einmal drucken, ausprobieren, "
        "und der Wert steht — er gehört danach ins Materialprofil, nicht ins Modell."
    ),
    changes=[FIRST_RELEASE],
)
def fit_ladder(raw: BaseParams) -> PartResult:
    params = cast(FitLadderParams, raw)
    spacing = params.diameter * 2.2
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

        hole = shapes.cylinder(params.diameter + play, base_height + 2.0 * shapes.OVERLAP)
        cutters.append(shapes.moved(hole, (x, spacing * 0.6, -shapes.OVERLAP)))
        features.append(
            bore(
                f"bore_{index + 1}",
                params.diameter + play,
                (x, spacing * 0.6, base_height / 2.0),
                depth=base_height,
                through=True,
            )
        )
        cutters.append(_label(f"{play:.2f}", (x, 0.0, base_height - LABEL_DEPTH)))

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
    params=WallLadderParams,
    features=["face"],
    doc=_(
        "Wände von einer bis mehreren Extrusionsbreiten. Zeigt, ab wann der Drucker "
        "wirklich noch Material legt — die Grundlage für die Mindestwandstärke."
    ),
    changes=[FIRST_RELEASE],
)
def wall_ladder(raw: BaseParams) -> PartResult:
    params = cast(WallLadderParams, raw)
    base_height = 2.0
    gap = params.extrusion * 6.0
    width = gap * (params.steps + 1)

    base = shapes.box(width, params.length, base_height)
    bodies = [base]
    for index in range(params.steps):
        thickness = params.extrusion * (index + 1)
        x = -width / 2.0 + gap * (index + 1)
        wall = shapes.box(thickness, params.length, params.height)
        bodies.append(shapes.moved(wall, (x, 0.0, base_height)))

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
    params=OverhangFanParams,
    features=["face"],
    doc=_(
        "Flächen von steil bis flach. Zeigt, ab welchem Winkel dieser Drucker mit "
        "diesem Material wirklich Stützen braucht — statt der Faustregel 45 Grad."
    ),
    changes=[FIRST_RELEASE],
)
def overhang_fan(raw: BaseParams) -> PartResult:
    params = cast(OverhangFanParams, raw)
    base_height = 3.0
    total = params.width * params.steps
    depth = 6.0
    base = shapes.box(total, depth, base_height)
    bodies = [base]
    # Die Rampen beginnen im Sockel und reichen ein Haar in ihn hinein: eine
    # Form, die nur berührt, ist eine Form, die abfällt (§39).
    start = depth / 2.0 - 1.0

    for index in range(params.steps):
        # Über 85 Grad liegt eine Rampe flach und faltet sich in ihre Nachbarin.
        # Der deklarierte Bereich erlaubt die Kombination, also hält der Baustein
        # die Grenze selbst ein.
        degrees = min(params.first + params.step * index, 85.0)
        angle = math.radians(degrees)
        x = -total / 2.0 + params.width * (index + 0.5)
        reach = params.length * math.cos(angle)
        rise = params.length * math.sin(angle)
        bodies.append(
            shapes.moved(_ramp(params.width, reach, rise), (x, start, base_height - shapes.OVERLAP))
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


def _label(text: str, position: tuple[float, float, float]) -> MeshData:
    """Die Zahl als eingravierter Strichcode aus Ziffern.

    Keine Schrift: eine Schrift ist eine Abhängigkeit, eine Lizenzfrage und ein
    Rendering-Problem zugleich (§36). Gebraucht wird hier nur, vier Stufen
    auseinanderzuhalten, und so viele kleine Striche wie die Stufennummer tun
    das auf dem Druckbett.
    """
    count = max(1, round(float(text.replace(",", ".")) * 100) % 10 or 10)
    bars = []
    for index in range(count):
        bar = shapes.box(0.8, 3.0, LABEL_DEPTH + shapes.OVERLAP)
        bars.append(
            shapes.moved(bar, (position[0] + index * 1.4 - count * 0.7, position[1], position[2]))
        )
    return union(*bars)
