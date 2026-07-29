"""What a clicked feature means for an operation's parameters (Bauplan §18.5, §25).

§25 asks for "put a part at a recognised feature". Recognising them was P3 and
placing them was P5 — but the two were never joined up: the feature was
selectable in the tree and in the view, and the dialog that opened next knew
nothing about it. Anybody wanting a bore in the face they had just clicked typed
its coordinates in by hand, off the analysis card.

This is where the two meet, and in the core rather than in the window because it
is a rule about geometry and parameters, not about widgets — testable without Qt,
and available to any surface that grows a selection later. Today the window is
the only caller: the command line has no selection, and the agent works from the
digest (§26.1), which is why the position of every feature is written into that
digest rather than derived here a second time.

Nothing here changes the document. The values become ordinary parameters of the
operation, so the stack stays a pure function of what is written in it (§11) —
a selection is a state of the surface and has no business in a project file.
Which is also why an operation that wants to *check* the feature takes its name
as a parameter instead: ``at_feature`` is in the file, and the operation looks it
up whenever the scene is computed.
"""

from __future__ import annotations

from typing import Any

from app.core.log import get_logger
from app.core.registry import OperationSpec
from app.core.types import Feature, Vec3

_log = get_logger(__name__)

#: The parameter a part uses to name the feature it belongs at. Where an
#: operation has it, that is the whole answer: the position beside it counts as
#: an offset from the feature, so it stays at zero.
FEATURE_FIELD = "at_feature"

#: Position, in the order the parameters are named everywhere.
POSITION = ("x", "y", "z")

#: A free direction, for the operations that take one (§25, lettering).
NORMAL = ("nx", "ny", "nz")

#: How dominant one component has to be before the direction counts as an axis.
#: Below this the feature stands at an angle, and naming an axis for it would be
#: a rounding somebody has to notice afterwards.
AXIS_CLARITY = 0.9


def values_for(spec: OperationSpec, feature: Feature) -> dict[str, Any]:
    """The parameters this feature suggests for this operation.

    Only what the feature says for certain: where it is and which way it looks.
    Not its size — a countersink takes the diameter of the screw head, not of
    the bore it sits on, and a helpfully filled-in 5,2 there would be a wrong
    number that looks like a measured one.
    """
    names = {entry.name for entry in spec.params.spec()}
    if FEATURE_FIELD in names:
        return {FEATURE_FIELD: feature.id}

    values: dict[str, Any] = {}
    centre = _vector(feature.params.get("centre"))
    if centre is not None:
        for name, value in zip(POSITION, centre, strict=True):
            if name in names:
                values[name] = round(float(value), 4)

    direction = _vector(feature.params.get("normal")) or _vector(feature.params.get("axis"))
    if direction is not None:
        for name, value in zip(NORMAL, direction, strict=True):
            if name in names:
                values[name] = round(float(value), 4)
        axis = dominant_axis(direction)
        if axis is not None and "axis" in names and _allows(spec, "axis", axis):
            values["axis"] = axis

    _log.info("feature %s suggests %d parameter(s) for %s", feature.id, len(values), spec.name)
    return values


def dominant_axis(direction: Vec3) -> str | None:
    """``x``, ``y`` or ``z`` when the direction really is one, else ``None``."""
    length = sum(value * value for value in direction) ** 0.5
    if length <= 0.0:
        return None
    shares = [abs(value) / length for value in direction]
    best = max(range(3), key=lambda index: shares[index])
    return "xyz"[best] if shares[best] >= AXIS_CLARITY else None


def faces_up(feature: Feature) -> bool:
    """Does this face lie flat and look upward?

    Not merely flat, which is what this asked before and was too generous: the
    ceiling of a cavity is flat too, and it points down. Chosen as the height of
    an opening it built a lid inside the box, at 26,9 of 30 millimetres, without
    a word — because a cut below that plane does meet the wall, so nothing looked
    wrong to any of the steps that followed.

    Everything that closes an opening reaches downward from it: the plate sits on
    the rim and the collar goes into the cavity. A face looking down would need
    all of that mirrored, and building it on the guess that somebody meant that
    is worse than saying which face is wanted.
    """
    normal = _vector(feature.params.get("normal"))
    return normal is not None and dominant_axis(normal) == "z" and normal[2] > 0.0


def _allows(spec: OperationSpec, name: str, value: str) -> bool:
    """Is this one of the choices the parameter offers?"""
    for entry in spec.params.spec():
        if entry.name == name:
            return not entry.choices or value in entry.choices
    return False


def _vector(value: object) -> Vec3 | None:
    if not isinstance(value, list | tuple) or len(value) != 3:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None
