"""Every part as an operation (Bauplan §24.1, §10).

A part is declared once and becomes an operation from that declaration —
menu entry, dialog, command line, agent tool and catalogue entry all follow
(Leitprinzip 3). Nothing here is written per part; adding a part to the library
adds it everywhere.

The operation takes the part's own parameters plus where it goes: position,
axis, angle. A subtractive part is cut out of the body, an additive one is
joined to it, and which of the two it is comes from the declaration — the user
does not have to know that a nut trap is a hole and a rib is not.

The play a fit needs is not written into the part either. A part declares
``play`` and leaves it at zero; here it is filled from the calibrated material
profile (AGENTS.md rule 7), which is what lets a later calibration reach old
projects.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app.core.errors import Action, AppError
from app.core.geom.boolean import BooleanKind, boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.transform import rotation, translation
from app.core.knowledge.parts.registry import PARTS, PartRegistry, PartSpec
from app.core.log import get_logger
from app.core.registry import Registry, op_params, param, register_op
from app.core.types import (
    BaseParams,
    Feature,
    OpContext,
    OpResult,
    PartResult,
    Profile,
    SceneObject,
    Vec3,
)
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Name of the parameter a part uses for the tolerance it needs. Zero means
#: "take it from the material profile" (§28.3).
PLAY_FIELD = "play"

#: Placement parameters every part operation gains on top of its own.
_PLACEMENT: tuple[tuple[str, str, Any], ...] = (
    ("x", "float", param(title=_("Position X"), default=0.0, unit="mm")),
    ("y", "float", param(title=_("Position Y"), default=0.0, unit="mm")),
    ("z", "float", param(title=_("Position Z"), default=0.0, unit="mm")),
    (
        "axis",
        "str",
        param(
            title=_("Achse"),
            default="z",
            choices=("x", "y", "z"),
            placement="advanced",
            doc=_("Richtung, in die der Baustein zeigt."),
        ),
    ),
    (
        "angle",
        "float",
        param(
            title=_("Drehung"),
            default=0.0,
            unit="grad",
            minimum=-360.0,
            maximum=360.0,
            placement="advanced",
        ),
    ),
    (
        "at_feature",
        "str",
        param(
            title=_("An Merkmal"),
            kind="feature",
            default="",
            doc=_(
                "Name eines erkannten Merkmals, zum Beispiel hole_1. Dann zählt "
                "dessen Ort, und die Position darüber wird als Versatz gerechnet."
            ),
        ),
    ),
)


def op_name(part: str) -> str:
    """``screw_hole`` becomes ``insert_screw_hole`` — one namespace, no clashes."""
    return f"insert_{part}"


def build_params(spec: PartSpec) -> type[BaseParams]:
    """The part's parameters plus where it goes, as one schema (§10)."""
    namespace: dict[str, Any] = {"__annotations__": {}}
    for entry in spec.params.fields():
        namespace["__annotations__"][entry.name] = entry.type
        namespace[entry.name] = (
            dataclasses.field(default=entry.default, metadata=entry.metadata)
            if entry.default is not dataclasses.MISSING
            else dataclasses.field(metadata=entry.metadata)
        )
    for name, annotation, declaration in _PLACEMENT:
        namespace["__annotations__"][name] = annotation
        namespace[name] = declaration

    made = type(f"{_camel(spec.name)}OpParams", (BaseParams,), namespace)
    return op_params(made)


def _camel(name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))


def register_all(
    parts: PartRegistry | None = None, registry: Registry | None = None
) -> tuple[str, ...]:
    """Declare one operation per part. Returns the operation names."""
    source = parts or PARTS
    made: list[str] = []
    for spec in source.all():
        name = op_name(spec.name)
        target = registry or None
        if (target or _default_registry()).has(name):
            continue
        _register_one(spec, build_params(spec), registry)
        made.append(name)
    _log.info("registered %d part operations", len(made))
    return tuple(made)


def _default_registry() -> Registry:
    from app.core.registry import REGISTRY

    return REGISTRY


def _register_one(spec: PartSpec, params: type[BaseParams], registry: Registry | None) -> None:
    title = _title_for(spec)

    @register_op(
        name=op_name(spec.name),
        title=title,
        category="parts",
        params=params,
        consumes=1,
        produces=1,
        applies_to=["face"] if spec.subtractive else [],
        touches_features=True,
        doc=spec.doc or title,
        registry=registry,
    )
    def run(ctx: OpContext, _spec: PartSpec = spec) -> OpResult:
        return insert(ctx, _spec)


def _title_for(spec: PartSpec) -> TranslatableText | str:
    return spec.title


def insert(ctx: OpContext, spec: PartSpec) -> OpResult:
    """Build the part, put it where it belongs, and join or cut it."""
    source = ctx.inputs[0]
    values = _part_values(spec, ctx.params, ctx.profile)
    produced = spec.fn(spec.params(**values))

    anchor = _anchor(source, ctx.params)
    placed = _place(as_mesh_data(produced.mesh), ctx.params, anchor)
    body = as_mesh_data(source.mesh)
    kind: BooleanKind = "difference" if spec.subtractive else "union"
    outcome = boolean(kind, [body, placed], quality=ctx.quality)

    features = dict(source.features)
    features.update(_placed_features(produced, spec, ctx.params, anchor))

    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features=features)],
        solver=outcome.solver,
        findings=[*outcome.findings, *produced.findings],
    )


def _part_values(spec: PartSpec, params: Any, profile: Profile | None) -> dict[str, Any]:
    """The part's own parameters out of the operation's, with the play filled in."""
    wanted = {entry.name for entry in spec.params.fields()}
    values = {name: getattr(params, name) for name in wanted if hasattr(params, name)}
    if PLAY_FIELD in values and not values[PLAY_FIELD] and profile is not None:
        # Rule 7: the tolerance is a reference into the material profile, never
        # a number in the file.
        values[PLAY_FIELD] = profile.material.clearance
    return values


def _anchor(source: SceneObject, params: Any) -> Vec3:
    """Where the part goes: at a named feature, or at the origin (§25).

    §25 asks for "put a part at a recognised feature". The name is enough for
    that — it is the same name the user clicked and the agent spoke about
    (§18.5), and a feature that is not there says so instead of landing the part
    somewhere plausible.
    """
    name = str(getattr(params, "at_feature", "") or "")
    if not name:
        return (0.0, 0.0, 0.0)

    feature = source.features.get(name)
    if feature is None:
        raise AppError(
            _("Dieses Merkmal gibt es an diesem Objekt nicht."),
            detail=f"unknown feature {name!r}",
            values={"feature": name, "known": ", ".join(sorted(source.features))},
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie das Merkmal im Objektbaum aus.")),
            ),
        )
    centre = feature.params.get("centre", (0.0, 0.0, 0.0))
    return (float(centre[0]), float(centre[1]), float(centre[2]))


def _place(mesh: MeshData, params: Any, anchor: Vec3 = (0.0, 0.0, 0.0)) -> MeshData:
    from app.core.geom.transform import apply

    axis = getattr(params, "axis", "z")
    angle = float(getattr(params, "angle", 0.0))
    body = mesh
    if axis != "z":
        # Lay the part over so its own +Z points along the chosen axis.
        body = apply(body, rotation("y", 90.0) if axis == "x" else rotation("x", -90.0))
    if angle:
        body = apply(body, rotation(axis, angle))  # type: ignore[arg-type]
    offset = (
        float(getattr(params, "x", 0.0)) + anchor[0],
        float(getattr(params, "y", 0.0)) + anchor[1],
        float(getattr(params, "z", 0.0)) + anchor[2],
    )
    return apply(body, translation(offset))


def _placed_features(
    produced: PartResult, spec: PartSpec, params: Any, anchor: Vec3 = (0.0, 0.0, 0.0)
) -> dict[str, Feature]:
    """The part's features, moved with it and named so they cannot collide.

    ``bore_1`` of the third inserted part would otherwise overwrite the first
    one's. The part name and the position make it unique without inventing a
    counter that nobody can predict.
    """
    from app.core.perceive.matching import moved_features

    matrix = _matrix(params, anchor)
    moved = moved_features(dict(produced.features), matrix)
    return {
        f"{spec.name}_{name}": dataclasses.replace(feature, id=f"{spec.name}_{name}")
        for name, feature in moved.items()
    }


def _matrix(params: Any, anchor: Vec3 = (0.0, 0.0, 0.0)) -> Any:
    import numpy as np

    from app.core.geom.ops import as_transform

    axis = getattr(params, "axis", "z")
    angle = float(getattr(params, "angle", 0.0))
    matrix = np.eye(4)
    if axis != "z":
        matrix = (rotation("y", 90.0) if axis == "x" else rotation("x", -90.0)) @ matrix
    if angle:
        matrix = rotation(axis, angle) @ matrix  # type: ignore[arg-type]
    matrix = (
        translation(
            (
                float(getattr(params, "x", 0.0)) + anchor[0],
                float(getattr(params, "y", 0.0)) + anchor[1],
                float(getattr(params, "z", 0.0)) + anchor[2],
            )
        )
        @ matrix
    )
    return as_transform(matrix)
