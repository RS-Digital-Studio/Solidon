"""The variant generator (Bauplan §28.3, §25 category "Varianten").

The same operation chain with one parameter stepped through, in one go: four
runs with 0.10 / 0.15 / 0.20 / 0.25 mm of play, labelled and arranged. One
print, and afterwards the value is settled.

"With project parameters this is one call, not a special function" — and that
is exactly how it is built. Nothing here knows anything about fits or play; it
turns a number that is already a parameter (§13) and evaluates the same stack
again.

The variants are deliberately **not** a step on the stack. They are a print run,
not a modelling step: what comes back is a scene to export, and the project is
left exactly as it was.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field

from app.core.errors import ValidationError
from app.core.geom.mesh import as_mesh_data
from app.core.geom.transform import apply, translation
from app.core.log import get_logger
from app.core.scene.evaluate import evaluate
from app.core.types import (
    Document,
    Finding,
    ObjectId,
    Profile,
    Quality,
    Report,
    Scene,
    SceneObject,
    SourceAccess,
)
from app.i18n import _, tr

_log = get_logger(__name__)

#: Gap between two variants on the plate, in millimetres.
DEFAULT_GAP = 8.0

#: More than this is not a calibration print any more, it is a plate full of
#: guesses (§28.3 names four).
MAX_VARIANTS = 12


@dataclass(slots=True)
class Variant:
    """One run with one value."""

    value: float
    objects: dict[ObjectId, SceneObject] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    complete: bool = True


@dataclass(slots=True)
class VariantSet:
    """Everything the generator produced, ready to export."""

    parameter: str
    variants: list[Variant] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return bool(self.variants) and all(entry.complete for entry in self.variants)

    def scene(self, profile: Profile) -> Scene:
        """The whole run as one scene — arranged, named after their values."""
        objects: dict[ObjectId, SceneObject] = {}
        for entry in self.variants:
            objects.update(entry.objects)
        return Scene(objects=objects, profile=profile, report=Report(tuple(self.findings)))


def build(
    document: Document,
    profile: Profile,
    *,
    parameter: str,
    first: float,
    step: float,
    count: int = 4,
    gap: float = DEFAULT_GAP,
    quality: Quality = "draft",
    sources: SourceAccess | None = None,
) -> VariantSet:
    """Evaluate the same stack ``count`` times with a stepped parameter."""
    if parameter not in document.parameters:
        raise ValidationError(
            field="parameter",
            detail=_("Diesen Projektparameter gibt es nicht."),
            values={"requested": parameter, "known": ", ".join(sorted(document.parameters))},
        )
    if not 1 <= count <= MAX_VARIANTS:
        raise ValidationError(
            field="count",
            detail=_("So viele Varianten ergeben keinen Kalibrierdruck mehr."),
            constraint="range",
            values={"count": count, "maximum": MAX_VARIANTS},
        )

    made = VariantSet(parameter=parameter)
    offset = 0.0

    for index in range(count):
        value = first + step * index
        working = copy.deepcopy(document)
        working.parameters[parameter] = dataclasses.replace(
            working.parameters[parameter], value=value, expression=""
        )

        result = evaluate(working, profile, quality=quality, sources=sources)
        variant = Variant(value=value, complete=result.complete)
        variant.findings.extend(result.scene.report.findings)

        if not result.complete:
            made.findings.append(
                Finding(
                    code="variants.stopped",
                    severity="error",
                    message=_("Eine Variante ließ sich nicht rechnen."),
                    values={"parameter": parameter, "value": round(value, 3)},
                )
            )
            made.variants.append(variant)
            continue

        width = _place(variant, result.scene, index, value, offset, gap)
        offset += width + gap
        made.variants.append(variant)

    _log.info("built %d variants of %s", len(made.variants), parameter)
    return made


def _place(
    variant: Variant,
    scene: Scene,
    index: int,
    value: float,
    offset: float,
    gap: float,
) -> float:
    """Move one run out of the way of the previous one and name it after its value."""
    width = 0.0
    for object_id, entry in scene.objects.items():
        mesh = as_mesh_data(entry.mesh)
        size = mesh.bounds.size
        width = max(width, float(size[0]))
        moved = apply(mesh, translation((offset - float(mesh.bounds.minimum[0]), 0.0, 0.0)))
        name = f"{entry.name} {tr('Variante')} {value:g}"
        variant.objects[f"{object_id}_v{index + 1}"] = dataclasses.replace(
            entry, id=f"{object_id}_v{index + 1}", name=name, mesh=moved
        )
    return width


def values(first: float, step: float, count: int) -> tuple[float, ...]:
    """The values a run would use — for the dialog and for the label."""
    return tuple(round(first + step * index, 4) for index in range(count))
