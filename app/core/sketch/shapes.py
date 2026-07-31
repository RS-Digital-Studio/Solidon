"""Die Grundformen (Bauplan §30.1, Ausgabestufe eins).

Rechteck, Langloch, Kreis und Vieleck als fertige Skizzen: exakt konstruierte
Punkte plus die Bedingungen, die die Maße tragen. Dialog, CLI und Agent
erzeugen Skizzen ausschließlich hierüber — nie über rohe Punktlisten
(Leitprinzip 5). Der Solver bestätigt die Konstruktion, statt sie zu suchen:
der Startzustand ist bereits die Lösung, ein Lauf kostet Mikrosekunden.

Alle Formen liegen mittig um den Ursprung; wo eine Form hingehört, entscheidet
die Operation, die sie verbraucht.
"""

from __future__ import annotations

import math

from app.core.errors import ValidationError
from app.core.types import Sketch, SketchConstraint, SketchElement
from app.i18n import _

#: Die Grundformen, die jede Skizzen-Op anbietet — eine Quelle für alle Dialoge.
SHAPE_CHOICES: tuple[str, ...] = ("rectangle", "slot", "circle", "polygon")


def rectangle(length: float, width: float) -> Sketch:
    """Ein Rechteck, Länge in X, Breite in Y.

    Flache Punktindizes: unten (0, 1), rechts (2, 3), oben (4, 5), links (6, 7).
    """
    _positive("length", length)
    _positive("width", width)
    half_l, half_w = length / 2.0, width / 2.0
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((-half_l, -half_w), (half_l, -half_w))),
            SketchElement("line", ((half_l, -half_w), (half_l, half_w))),
            SketchElement("line", ((half_l, half_w), (-half_l, half_w))),
            SketchElement("line", ((-half_l, half_w), (-half_l, -half_w))),
        ),
        constraints=(
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("coincident", (3, 4)),
            SketchConstraint("coincident", (5, 6)),
            SketchConstraint("coincident", (7, 0)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("vertical", (2, 3)),
            SketchConstraint("horizontal", (4, 5)),
            SketchConstraint("vertical", (6, 7)),
            SketchConstraint("distance", (0, 1), _number(length)),
            SketchConstraint("distance", (2, 3), _number(width)),
            SketchConstraint("fixed", (0,)),
        ),
    )


def slot(length: float, width: float) -> Sketch:
    """Ein Langloch: Gesamtlänge in X, Breite in Y, halbrunde Enden.

    Punkte: untere Linie (0, 1), rechter Bogen (2 Mitte, 3 Anfang, 4 Ende),
    obere Linie (5, 6), linker Bogen (7 Mitte, 8 Anfang, 9 Ende). Beide Bögen
    laufen gegen den Uhrzeigersinn.
    """
    _positive("length", length)
    _positive("width", width)
    if length <= width:
        raise ValidationError(
            "length",
            _("Ein Langloch muss länger als breit sein — sonst ist es ein Kreis."),
            value=length,
            constraint="slot_proportion",
        )
    radius = width / 2.0
    half_s = (length - width) / 2.0
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((-half_s, -radius), (half_s, -radius))),
            SketchElement("arc", ((half_s, 0.0), (half_s, -radius), (half_s, radius))),
            SketchElement("line", ((half_s, radius), (-half_s, radius))),
            SketchElement("arc", ((-half_s, 0.0), (-half_s, radius), (-half_s, -radius))),
        ),
        constraints=(
            # Bewusst ohne Horizontal-Bedingungen auf den Flanken: zusammen mit
            # Koinzidenzen, Radien und Mittenabstand wären sie in der
            # symmetrischen Lage linear abhängig, und der Solver lehnt einen
            # überbestimmten Satz ab — zu Recht, auch bei den eigenen Formen.
            SketchConstraint("coincident", (1, 3)),
            SketchConstraint("coincident", (4, 5)),
            SketchConstraint("coincident", (6, 8)),
            SketchConstraint("coincident", (9, 0)),
            SketchConstraint("horizontal", (7, 2)),
            SketchConstraint("distance", (7, 2), _number(length - width)),
            SketchConstraint("distance", (2, 3), _number(width / 2.0)),
            SketchConstraint("distance", (7, 8), _number(width / 2.0)),
            SketchConstraint("fixed", (2,)),
        ),
    )


def circle(diameter: float) -> Sketch:
    """Ein Kreis um den Ursprung. Punkte: Mitte (0), Randpunkt (1)."""
    _positive("diameter", diameter)
    return Sketch(
        plane="plane:xy",
        elements=(SketchElement("circle", ((0.0, 0.0), (diameter / 2.0, 0.0))),),
        constraints=(
            SketchConstraint("distance", (0, 1), _number(diameter / 2.0)),
            SketchConstraint("fixed", (0,)),
        ),
    )


def polygon(diameter: float, corners: int) -> Sketch:
    """Ein regelmäßiges Vieleck, Durchmesser über die Ecken, eine Kante unten.

    ``corners`` Linien; Punktindizes je Linie ``(2·k, 2·k + 1)``.
    """
    _positive("diameter", diameter)
    if not 3 <= corners <= 64:
        raise ValidationError(
            "corners",
            _("Ein Vieleck braucht zwischen drei und vierundsechzig Ecken."),
            value=corners,
            constraint="corner_count",
        )
    radius = diameter / 2.0
    side = 2.0 * radius * math.sin(math.pi / corners)
    # Die erste Ecke so gelegt, dass die erste Kante unten waagerecht liegt.
    start_angle = -math.pi / 2.0 - math.pi / corners
    vertices = [
        (
            radius * math.cos(start_angle + 2.0 * math.pi * k / corners),
            radius * math.sin(start_angle + 2.0 * math.pi * k / corners),
        )
        for k in range(corners)
    ]
    elements = tuple(
        SketchElement("line", (vertices[k], vertices[(k + 1) % corners])) for k in range(corners)
    )
    constraints: list[SketchConstraint] = []
    for k in range(corners):
        constraints.append(SketchConstraint("coincident", (2 * k + 1, (2 * k + 2) % (2 * corners))))
        constraints.append(SketchConstraint("distance", (2 * k, 2 * k + 1), _number(side)))
    constraints.append(SketchConstraint("horizontal", (0, 1)))
    constraints.append(SketchConstraint("fixed", (0,)))
    return Sketch(plane="plane:xy", elements=elements, constraints=tuple(constraints))


def _number(value: float) -> str:
    """Ein Maß als Ausdruck der Grammatik (§13) — immer dezimal, nie ``1e-05``."""
    return format(float(value), ".9f")


def _positive(field: str, value: float) -> None:
    if value <= 0.0:
        raise ValidationError(
            field,
            _("Dieses Maß muss größer als null sein."),
            value=value,
            constraint="positive",
        )
