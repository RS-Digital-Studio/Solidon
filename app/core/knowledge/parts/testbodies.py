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
from typing import Any, cast

from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, compound, face, pin, result, subtract, union
from app.core.knowledge.parts.registry import (
    FACE_GIVES_DIRECTION,
    FACE_ON_THE_BODY,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.knowledge.parts.shapes import Form
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.core.units import DEGREE_UNIT
from app.i18n import TranslatableText, _

WALL_LADDER_SEPARATE_STEPS = PartChange(
    version="15",
    date="2026-09-06",
    reason="Breitere Messwände überlappten ihre Nachbarn.",
    effect=_(
        "Jede Stufe bleibt einzeln messbar; die Sockelbreite wächst um alle Wandstärken und "
        "Zwischenräume."
    ),
)

OVERHANG_FROM_VERTICAL = PartChange(
    version="15",
    date="2026-09-06",
    reason="Die angegebene Senkrechte war durch vertauschte Sinus- und Kosinusanteile zur "
    "Waagerechten geworden.",
    effect=_(
        "Jede Rampe hat ihren eingetragenen Winkel zur Senkrechten. Kombinationen mit einem "
        "letzten Winkel ab 90 Grad werden vor dem Bauen erklärt."
    ),
)

OVERHANG_FAN_BOUNDED = PartChange(
    version="20",
    date="2026-09-22",
    reason="Breite und Auskraglänge hatten keine Obergrenze; der Bereichstest prüfte sie "
    "deshalb nur an ihrer Untergrenze.",
    effect=_(
        "Breite je Stufe höchstens 50 mm, Auskraglänge höchstens 100 mm. Ein Fächer "
        "darüber wird mit Hinweis auf die Grenze abgewiesen; darunter ändert sich nichts."
    ),
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
    effect=_(
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
    effect=_(
        "Jede Stufe trägt so viele eingravierte Striche wie ihre Nummer; Maße, "
        "Spiele und Höhe bleiben unverändert."
    ),
)

FIT_LADDER_CAN_BE_ASSEMBLED = PartChange(
    version="16",
    date="2026-09-08",
    reason="Zapfen und Bohrungen waren auf derselben starren Platte und nicht ineinander steckbar.",
    effect=_(
        "Zwei getrennte, nummerierte Leisten lassen sich zum Messen zusammenstecken. "
        "Zapfendurchmesser und Spielstufen bleiben erhalten; die Grundplatte wird geteilt."
    ),
)

FIT_LADDER_FACE_AT_RAIL_CENTRE = PartChange(
    version="18",
    date="2026-09-12",
    reason="Der Flächenbezug lag um die Gravurtiefe vom Leistenrand versetzt statt in der Mitte.",
    effect=_(
        "Die benannte Fläche liegt mittig auf der Zapfenleiste. Daran ausgerichtete "
        "Folgeschritte verschieben sich; Leisten, Zapfen, Bohrungen und Spielmaße bleiben gleich."
    ),
)

#: Höhe der eingravierten Beschriftungen. Zwei Schichten zu 0,2 mm — lesbar,
#: billig.
LABEL_DEPTH = 0.4


def size_for_fit_ladder(diameter: float) -> dict[str, Any]:
    """Die Leiter prüft den Durchmesser, den das Teil wirklich hat (§28.3).

    **Der doc-Satz des Feldes sagte es seit je** — „am besten der, den das Teil
    braucht" — und niemand belegte ihn vor: Wer eine Bohrung anklickte und den
    Prüfkörper öffnete, bekam die Vorgabe 6,0 und musste den gemessenen Wert
    von Hand abschreiben. Eine Leiter für 6 mm sagt über eine Ø 4,2-Verbindung
    nichts: Das Spiel, bei dem ein Zapfen gerade noch gleitet, hängt am
    Durchmesser.

    **Gerundet auf ein Hundertstel, und das ist keine Toleranz, sondern eine
    Anzeige.** Die Erkennung misst 5,1873…; eine Leiter, die das als Nennmaß
    trägt, behauptet eine Genauigkeit, die kein Drucker einlöst — und der Wert
    steht danach in der Beschriftung, die jemand liest. Der Kern rechnet
    weiterhin mit dem ungerundeten Netz (Regel 6); gerundet wird der
    **Vorschlag** an den Dialog.

    Anders als bei Buchse, Mutternfalle oder Gewinde (:mod:`fasteners`) gibt es
    hier keine Normreihe, aus der die passende Größe folgt: Ein Prüfkörper
    misst, was da ist, statt es einer Tabelle zuzuordnen.
    """
    return {"diameter": round(float(diameter), 2)}


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
    standalone=True,
    # Ein Prüfkörper wird gedruckt und gemessen, nicht angebaut (§24.3).
    at_face=False,
    params=FitLadderParams,
    at_hole_values=size_for_fit_ladder,
    bodies=2,
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
        FIT_LADDER_CAN_BE_ASSEMBLED,
        FIT_LADDER_FACE_AT_RAIL_CENTRE,
    ],
)
def fit_ladder(raw: BaseParams) -> PartResult:
    params = cast(FitLadderParams, raw)
    largest_bore = params.diameter + params.first + params.step * (params.steps - 1)
    spacing = max(params.diameter * 2.2, largest_bore * 1.5, params.steps * 1.4 + 2.8)
    base_height = 3.0
    width = spacing * params.steps + spacing
    # Beide Leisten bleiben beim Druck getrennt und passen beim Fügen exakt
    # übereinander. Der breite freie Zwischenraum gehört zum Prüfkörperlayout.
    rail_depth = max(spacing, largest_bore + 8.0)
    rail_offset = (rail_depth + spacing * 0.2) / 2.0
    pin_y, bore_y = -rail_offset, rail_offset
    rails = {
        y: shapes.moved(shapes.box(width, rail_depth, base_height), (0.0, y, 0.0))
        for y in (pin_y, bore_y)
    }
    features = [face("face_1", width * rail_depth, (0.0, pin_y, base_height))]
    studs: list[Form] = []
    holes: list[Form] = []
    labels: dict[float, list[Form]] = {pin_y: [], bore_y: []}

    for index in range(params.steps):
        play = params.first + params.step * index
        x = -width / 2.0 + spacing * (index + 1)

        stud = shapes.cylinder(params.diameter, params.height)
        studs.append(shapes.moved(stud, (x, pin_y, base_height)))
        features.append(
            pin(
                f"pin_{index + 1}",
                params.diameter,
                (x, pin_y, base_height + params.height / 2.0),
                length=params.height,
            )
        )

        hole = shapes.cylinder(params.diameter + play, base_height + 2.0 * BOOLEAN_OVERLAP)
        holes.append(shapes.moved(hole, (x, bore_y, -BOOLEAN_OVERLAP)))
        features.append(
            bore(
                f"bore_{index + 1}",
                params.diameter + play,
                (x, bore_y, base_height / 2.0),
                depth=base_height,
                through=True,
            )
        )
        for y in (pin_y, bore_y):
            labels[y].append(
                _label(index + 1, (x, y + largest_bore / 2.0 + 2.0, base_height - LABEL_DEPTH))
            )

    # Zwei Leisten, die getrennt gedruckt werden: je Leiste ein Körper, zusammen
    # ein Verbund (``bodies=2``) — keine Vereinigung, die nichts vereinigt.
    pins = subtract(union(rails[pin_y], *studs), *labels[pin_y])
    bores = subtract(rails[bore_y], *holes, *labels[bore_y])
    return result(compound(pins, bores), *features)


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
    standalone=True,
    # Ein Prüfkörper wird gedruckt und gemessen, nicht angebaut (§24.3).
    at_face=False,
    params=WallLadderParams,
    features=["face"],
    wall=WallRequirement.from_parameter("extrusion"),
    doc=_(
        "Wände von einer bis mehreren Extrusionsbreiten. Zeigt, ab wann der Drucker "
        "wirklich noch Material legt — die Grundlage für die Mindestwandstärke."
    ),
    changes=[FIRST_RELEASE, FACE_GIVES_DIRECTION, WALL_LADDER_SEPARATE_STEPS, FACE_ON_THE_BODY],
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
        # Die freie Oberseite des Sockels, mitten in der ersten Lücke — unter
        # den Wänden liegt keine Fläche.
        face(
            "face_1",
            (width - sum(thicknesses)) * params.length,
            (-width / 2.0 + gap / 2.0, 0.0, base_height),
        ),
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
    # Beide Maße hatten bis zum 22.09.2026 keine Obergrenze: Der Bereichstest
    # fuhr sie deshalb nur an ihrer Untergrenze, und ein Tippfehler baute einen
    # Fächer von Metern. Die Grenzen sind großzügig — ein Prüfkörper, der mehr
    # braucht, prüft etwas anderes als den Überhang.
    width: float = param(
        title=_("Breite je Stufe"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=50.0,
        doc=_("Breite einer einzelnen Fläche. Schmaler spart Zeit, breiter zeigt mehr."),
    )
    length: float = param(
        title=_("Auskraglänge"),
        default=15.0,
        unit="mm",
        minimum=3.0,
        maximum=100.0,
        doc=_("Wie weit jede Fläche frei hinaussteht. Zu kurz verzeiht der Drucker alles."),
    )


FAN_OVER_THE_TOP = _(
    "Der letzte Winkel erreicht oder überschreitet 90 Grad. Weniger Stufen, eine "
    "kleinere Schrittweite oder einen kleineren Anfangswinkel wählen."
)


def _fan_over_the_top(params: OverhangFanParams) -> TranslatableText | None:
    """Die erklärte Bedingung des Fächers: Anfang, Schritt und Stufen zusammen unter 90 Grad.

    Jede Grenze für sich ist erfüllbar (80 Grad, 30 Grad Schritt, zehn Stufen),
    zusammen ergäben sie 350 Grad — kein Überhang mehr, sondern ein Rückwärts.
    """
    last = params.first + params.step * (params.steps - 1)
    return FAN_OVER_THE_TOP if last >= 90.0 else None


@register_part(
    name="overhang_fan",
    title=_("Überhangfächer"),
    group="calibration",
    standalone=True,
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
    changes=[FIRST_RELEASE, FACE_GIVES_DIRECTION, OVERHANG_FROM_VERTICAL, OVERHANG_FAN_BOUNDED],
    feasible=lambda raw: _fan_over_the_top(cast(OverhangFanParams, raw)),
)
def overhang_fan(raw: BaseParams) -> PartResult:
    params = cast(OverhangFanParams, raw)
    last = params.first + params.step * (params.steps - 1)
    over = _fan_over_the_top(params)
    if over is not None:
        raise ValidationError("steps", over, constraint="feasible", values={"last_angle": last})
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


def _ramp(width: float, reach: float, rise: float) -> Form:
    """Ein Keil, der über nichts hinauslehnt — die Form, aus der ein
    Überhangtest besteht.

    Ein Seitenriss mit zwei Auswertern (P2.7): unten die Kante, oben der
    Auslauf um ``reach`` — dieselbe Form wie der Anlauf einer Rippe.
    """
    return shapes.prism_across([(0.0, 0.0), (reach, rise), (0.0, rise)], width)


def _label(step: int, position: tuple[float, float, float]) -> Form:
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
    # Getrennte Striche sind getrennte Körper: ein Verbund, kein vereinigter Block.
    return compound(*bars)
