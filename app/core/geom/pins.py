"""Passstifte über eine Trennebene (Bauplan §25, §14).

Ein geteiltes Teil, das nur geklebt wird, lässt dem, der es hält, eine
Aufgabe: die Hälften auszurichten, während der Kleber greift. Zwei Stifte
nehmen diese Aufgabe ab — und sie sind der Grund, warum Auto Split überhaupt
lohnt.

Wo die Stifte hinkommen, entscheidet sich auf der Schnittfläche, nicht am
Hüllquader: das Schnittpolygon wird um Stiftradius plus Wand eingezogen, und
was übrig bleibt, ist, wo auf beiden Seiten Material ist. Zwei Stifte entlang
der langen Richtung dieses Bereichs — einer ließe die Hälften verdrehen.

Das Spiel ist hier keine Zahl. Es kommt aus dem Materialprofil (AGENTS.md
Regel 7), damit eine spätere Kalibrierung Teile erreicht, die vor ihr geteilt
wurden — und das Passungspaar hält den Verweis fest, nicht den Wert (§14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np

from app.core.geom.autosplit import Candidate, sections_along, upright
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, rotation, translation
from app.core.knowledge.parts.registry import PARTS
from app.core.log import get_logger
from app.core.types import Feature, FeatureId, Finding, Profile, Vec3
from app.i18n import _

_log = get_logger(__name__)

#: Wie viele Stifte eine Naht bekommt. Ein Stift ist ein Scharnier, drei sind
#: ein Toleranzproblem.
PIN_COUNT = 2

#: Stiftdurchmesser relativ zur kürzeren Seite der Schnittfläche, und der
#: Bereich, in dem er gehalten wird. Dünne Stifte scheren ab, dicke schwächen
#: das Teil, in dem sie sitzen.
PIN_RELATIVE = 0.12
PIN_MIN = 3.0
PIN_MAX = 8.0

#: Wie tief ein Stift in jeder Hälfte sitzt, relativ zu seinem Durchmesser.
PIN_DEPTH_FACTOR = 1.5

#: Material, das um einen Stift stehen bleiben muss. Darunter bricht die
#: Bohrung aus.
PIN_WALL = 1.6

#: Zusatztiefe der Bohrung über den Stift hinaus, damit die Hälften auf der
#: Fläche schließen und nicht auf dem Stiftende.
BORE_RELIEF = 0.4


@dataclass(frozen=True, slots=True)
class PinPlan:
    """Wo die Stifte hinkommen, und wie groß sie sind."""

    positions: tuple[Vec3, ...]
    diameter: float
    length: float
    axis: str
    findings: tuple[Finding, ...] = ()

    @property
    def count(self) -> int:
        return len(self.positions)


@dataclass(slots=True)
class PinnedPair:
    """Beide Hälften nach dem Verstiften, mit den Merkmalen, die ein
    Passungspaar braucht."""

    first: MeshData
    second: MeshData
    pin_features: dict[FeatureId, Feature] = field(default_factory=dict)
    bore_features: dict[FeatureId, Feature] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


def plan_pins(
    mesh: MeshData, candidate: Candidate, *, count: int = PIN_COUNT, wall: float = PIN_WALL
) -> PinPlan:
    """Sucht Platz für Stifte auf der Schnittfläche von ``candidate``.

    Liefert einen Plan ohne Positionen, wenn die Fläche zu klein ist — eine
    Naht ohne Stifte klebt immer noch, ein Stift, der aus der Wand ausbricht,
    nicht.
    """
    section = sections_along(mesh, cast(Any, candidate.axis), np.array([candidate.position]))[0]
    if section is None or section.is_empty:
        return PinPlan((), 0.0, 0.0, candidate.axis, (_no_face(),))

    largest = max(getattr(section, "geoms", (section,)), key=lambda entry: entry.area)
    diameter = _diameter(largest)
    inset = largest.buffer(-(diameter / 2.0 + wall))
    if inset.is_empty:
        return PinPlan((), 0.0, 0.0, candidate.axis, (_too_small(diameter, wall),))

    room = max(getattr(inset, "geoms", (inset,)), key=lambda entry: entry.area)
    points = _spread(room, count)
    length = diameter * PIN_DEPTH_FACTOR * 2.0
    return PinPlan(
        positions=tuple(_in_world(point, candidate) for point in points),
        diameter=diameter,
        length=length,
        axis=candidate.axis,
    )


def _diameter(section: Any) -> float:
    """Aus der schmalsten Richtung der Fläche, gehalten im nutzbaren Bereich."""
    low_x, low_y, high_x, high_y = section.bounds
    narrow = min(high_x - low_x, high_y - low_y)
    return float(min(PIN_MAX, max(PIN_MIN, narrow * PIN_RELATIVE)))


def _spread(room: Any, count: int) -> list[tuple[float, float]]:
    """Punkte, verteilt entlang der langen Richtung des nutzbaren Bereichs.

    Entlang der *langen* Richtung mit Absicht: zwei Stifte dicht beieinander
    halten gegen Verdrehen etwa so gut wie einer.
    """
    from shapely.geometry import Point
    from shapely.ops import nearest_points

    low_x, low_y, high_x, high_y = room.bounds
    horizontal = (high_x - low_x) >= (high_y - low_y)
    span = (low_x, high_x) if horizontal else (low_y, high_y)
    fixed = (low_y + high_y) / 2.0 if horizontal else (low_x + high_x) / 2.0

    points: list[tuple[float, float]] = []
    for index in range(count):
        along = span[0] + (span[1] - span[0]) * (2 * index + 1) / (2 * count)
        candidate = Point(along, fixed) if horizontal else Point(fixed, along)
        if not room.contains(candidate):
            candidate = nearest_points(room, candidate)[0]
        points.append((float(candidate.x), float(candidate.y)))
    return points


def _in_world(point: tuple[float, float], candidate: Candidate) -> Vec3:
    """Ein Punkt des Schnitts zurück in Weltkoordinaten.

    Der Schnitt wurde mit aufgerichteter Schnittachse genommen, der Rückweg
    ist also dieselbe Drehung, invertiert — keine Tabelle von
    Vorzeichenwechseln, die für drei Achsen gleichzeitig stimmen muss.
    """
    turned = np.array([point[0], point[1], candidate.position, 1.0])
    back = np.linalg.inv(upright(cast(Any, candidate.axis))) @ turned
    return (float(back[0]), float(back[1]), float(back[2]))


def add_pins(
    first: MeshData,
    second: MeshData,
    plan: PinPlan,
    profile: Profile,
    *,
    play: float | None = None,
) -> PinnedPair:
    """Setzt die Stifte in die eine Hälfte und die Bohrungen in die andere.

    ``first`` trägt die Stifte. Welche Hälfte das ist, ist mechanisch egal —
    wichtig ist, dass die beiden auseinandergehalten werden, denn das
    Passungspaar benennt je eine (§14).
    """
    pair = PinnedPair(first=first, second=second, findings=list(plan.findings))
    if not plan.count:
        return pair

    clearance = profile.material.clearance if play is None else play
    pin_body = _part("dowel", diameter=plan.diameter, length=plan.length, kind="pin", play=0.0)
    bore_body = _part(
        "dowel",
        diameter=plan.diameter,
        length=plan.length / 2.0 + BORE_RELIEF,
        kind="bore",
        play=clearance,
    )

    for index, position in enumerate(plan.positions, start=1):
        placed_pin = _upright(pin_body, plan.axis, position, -plan.length / 2.0)
        placed_bore = _upright(bore_body, plan.axis, position, 0.0)

        pair.first = boolean("union", [pair.first, placed_pin]).mesh
        pair.second = boolean("difference", [pair.second, placed_bore]).mesh

        axis_vector = _axis_vector(plan.axis)
        pair.pin_features[f"pin_{index}"] = Feature(
            id=f"pin_{index}",
            kind="pin",
            provenance="generated",
            params={
                "diameter": round(plan.diameter, 4),
                "centre": position,
                "axis": axis_vector,
                "depth": round(plan.length / 2.0, 4),
            },
        )
        pair.bore_features[f"bore_{index}"] = Feature(
            id=f"bore_{index}",
            kind="hole",
            provenance="generated",
            params={
                "diameter": round(plan.diameter + clearance, 4),
                "centre": position,
                "axis": axis_vector,
                "depth": round(plan.length / 2.0 + BORE_RELIEF, 4),
            },
        )

    _log.info("pinned a seam with %d pin(s) of %.1f mm", plan.count, plan.diameter)
    return pair


def _part(name: str, **values: Any) -> MeshData:
    """Ein Körper aus der Bibliothek. Bausteine vor Primitiven (§39), auch hier."""
    from app.core.geom.mesh import as_mesh_data

    spec = PARTS.get(name)
    return as_mesh_data(spec.fn(spec.params(**values)).mesh)


def _upright(body: MeshData, axis: str, position: Vec3, offset: float) -> MeshData:
    """Legt einen Baustein, der auf +Z steht, entlang der Schnittachse und
    schiebt ihn an seinen Platz."""
    placed = body
    if axis == "x":
        placed = apply(placed, rotation("y", 90.0))
    elif axis == "y":
        placed = apply(placed, rotation("x", -90.0))

    shift = [0.0, 0.0, 0.0]
    shift["xyz".index(axis)] = offset
    target = (position[0] + shift[0], position[1] + shift[1], position[2] + shift[2])
    return apply(placed, translation(target))


def _axis_vector(axis: str) -> Vec3:
    vector = [0.0, 0.0, 0.0]
    vector["xyz".index(axis)] = 1.0
    return (vector[0], vector[1], vector[2])


def _no_face() -> Finding:
    return Finding(
        code="split.no_cut_face",
        severity="warning",
        message=_("An der Trennebene war keine Schnittfläche zu finden."),
    )


def _too_small(diameter: float, wall: float) -> Finding:
    return Finding(
        code="split.face_too_small",
        severity="warning",
        message=_("Die Schnittfläche ist für Passstifte zu klein — geklebt hält sie trotzdem."),
        values={"diameter_mm": round(diameter, 2), "wall_mm": round(wall, 2)},
    )
