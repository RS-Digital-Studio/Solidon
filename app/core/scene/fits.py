"""Fits between features (Bauplan §14).

Objects are otherwise independent, and a mistake only shows up at assembly —
when the pin does not go into the hole and the print is already made. A fit ties
two features together and is checked on every evaluation.

The tolerance is a reference into the material profile, never a number in the
file (§12, AGENTS.md rule 7). That is what makes calibration (§28.3) reach
projects that were built before it.
"""

from __future__ import annotations

from app.core.knowledge.profiles import resolve_tolerance
from app.core.log import get_logger
from app.core.types import Feature, FeatureRef, Finding, Fit, FitKind, Profile, Scene
from app.core.units import EPS_DISPLAY, format_length
from app.i18n import _

_log = get_logger(__name__)

#: How far the actual gap may differ from the profile value before it is a finding.
FIT_TOLERANCE = EPS_DISPLAY * 5


def resolve(scene: Scene, reference: FeatureRef) -> Feature | None:
    """The feature a fit points at, or None when it is gone."""
    entry = scene.objects.get(reference.object_id)
    if entry is None:
        return None
    return entry.features.get(reference.feature_id)


def diameter_of(feature: Feature) -> float | None:
    value = feature.params.get("diameter")
    return float(value) if value is not None else None


def check(scene: Scene, profile: Profile) -> list[Finding]:
    """Check every fit in the scene. Violations are never silent (§14)."""
    findings: list[Finding] = []
    for fit in scene.fits:
        findings.extend(_check_one(scene, fit, profile))
    return findings


def _check_one(scene: Scene, fit: Fit, profile: Profile) -> list[Finding]:
    first = resolve(scene, fit.a)
    second = resolve(scene, fit.b)
    if first is None or second is None:
        return [
            Finding(
                code="fit.missing_feature",
                severity="error",
                message=_("Eine Passung verweist auf ein Merkmal, das es nicht mehr gibt."),
                values={"fit": fit.name, "a": str(fit.a), "b": str(fit.b)},
            )
        ]

    if fit.kind == "flush":
        return []

    hole, pin = _sort_by_kind(first, second)
    hole_diameter = diameter_of(hole)
    pin_diameter = diameter_of(pin)
    if hole_diameter is None or pin_diameter is None:
        return [
            Finding(
                code="fit.not_measurable",
                severity="warning",
                message=_("Diese Passung lässt sich nicht messen — es fehlt ein Durchmesser."),
                values={"fit": fit.name},
            )
        ]

    wanted = resolve_tolerance(fit.tolerance, fit.kind, profile)
    actual = hole_diameter - pin_diameter
    if abs(actual - wanted) <= FIT_TOLERANCE:
        return []

    return [
        Finding(
            code="fit.violated",
            severity="warning",
            message=_(_message_for(fit.kind, actual, wanted)),
            values={
                "fit": fit.name,
                "actual": format_length(actual),
                "expected": format_length(wanted),
            },
        )
    ]


def _sort_by_kind(first: Feature, second: Feature) -> tuple[Feature, Feature]:
    """The hole first, the pin second — whichever way round they were written."""
    if first.kind == "hole":
        return first, second
    if second.kind == "hole":
        return second, first
    # Neither is a hole: the larger diameter plays the part.
    return (
        (first, second)
        if (diameter_of(first) or 0.0) >= (diameter_of(second) or 0.0)
        else (second, first)
    )


def _message_for(kind: FitKind, actual: float, wanted: float) -> str:
    if actual < wanted:
        return "Die Passung sitzt enger als vorgesehen."
    return "Die Passung sitzt loser als vorgesehen."


def add(scene_fits: list[Fit], fit: Fit) -> list[Fit]:
    """Add a pair, replacing one of the same name (§25, agent tool ``add_fit``)."""
    kept = [entry for entry in scene_fits if entry.name != fit.name]
    kept.append(fit)
    _log.info("fit %s: %s to %s", fit.name, fit.a, fit.b)
    return kept


def remove(scene_fits: list[Fit], name: str) -> list[Fit]:
    return [entry for entry in scene_fits if entry.name != name]
