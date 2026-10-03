"""Gespeicherte Auswahlregionen als reproduzierbare Erkennungsaufträge (§21)."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData
from app.core.perceive.local import detect_local, local_error
from app.core.perceive.matching import MatchResult, apply_mapping
from app.core.perceive.patterns import without_pattern_cells
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, OpContext, OpResult
from app.core.units import EPS_GEOM
from app.i18n import _, tr


@op_params
class DetectRegionParams(BaseParams):
    radius: float = param(
        title=_("Suchradius"),
        default=10.0,
        minimum=EPS_GEOM,
        unit="mm",
        doc=_("In diesem Umkreis werden vollständige Merkmale auf dem Originalmodell gesucht."),
    )
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("X-Koordinate der gewählten Stelle am Originalmodell."),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Y-Koordinate der gewählten Stelle am Originalmodell."),
    )
    z: float = param(
        title=_("Z"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Z-Koordinate der gewählten Stelle am Originalmodell."),
    )
    nx: float = param(
        title=_("Richtung X"),
        default=0.0,
        placement="advanced",
        doc=_("X-Anteil der Richtung der Fläche an der gewählten Stelle."),
    )
    ny: float = param(
        title=_("Richtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Y-Anteil der Richtung der Fläche an der gewählten Stelle."),
    )
    nz: float = param(
        title=_("Richtung Z"),
        default=1.0,
        placement="advanced",
        doc=_("Z-Anteil der Richtung der Fläche an der gewählten Stelle."),
    )
    seed_face: int = param(
        title=_("Originaldreieck"),
        default=-1,
        minimum=-1,
        placement="advanced",
        doc=_("Geprüfter Hinweis auf das gewählte Originaldreieck; -1 sucht über die Stelle."),
    )


@register_op(
    name="detect_region",
    # Ein örtliches Muster ersetzt seine zuvor einzeln erkannten Zellflächen.
    cache_version="2",
    title=_("Merkmale an dieser Stelle erkennen"),
    category="holes",
    params=DetectRegionParams,
    consumes=1,
    produces=1,
    requires_kind="mesh",
    touches_features=False,
    doc=_(
        "Erkennt vollständige Merkmale in einem ausgewählten Bereich, auch an sehr großen Netzen."
    ),
)
def detect_region(ctx: OpContext) -> OpResult:
    """Geometrie und Attribute bleiben gleich; nur geprüfte Merkmale kommen hinzu."""
    source = ctx.inputs[0]
    if not isinstance(source.mesh, MeshData):
        raise local_error("seed")
    params = cast(DetectRegionParams, ctx.params)
    point, normal = (params.x, params.y, params.z), (params.nx, params.ny, params.nz)
    ctx.progress(0.0, tr("Merkmale an dieser Stelle erkennen"))
    result = detect_local(
        source.mesh,
        point,
        normal=normal,
        radius=params.radius,
        seed_faces=(params.seed_face,) if params.seed_face >= 0 else (),
        check_cancelled=ctx.cancelled.raise_if_cancelled,
    )
    answered = {}
    if result.reason == "ambiguous_seed":
        choices = [
            tr("Fläche {number}").format(number=index + 1)
            for index in range(len(result.seed_choices))
        ]
        choice = ctx.ask(tr("Welche der übereinanderliegenden Flächen ist gemeint?"), choices)
        if choice not in choices:
            raise OperationCancelled
        face = result.seed_choices[choices.index(choice)]
        answered["seed_face"] = face
        result = detect_local(
            source.mesh,
            point,
            normal=normal,
            radius=params.radius,
            seed_faces=(face,),
            check_cancelled=ctx.cancelled.raise_if_cancelled,
        )
    if not result.complete:
        raise local_error(result.reason or "no_feature")
    # Wiederholte Suche an denselben Originalflächen erzeugt keinen Zwilling.
    # Untersuchte andere Stellen reservieren alle bisherigen Kennungen weiter.
    mapping: dict[str, str] = {}
    assigned: set[str] = set()
    for name, existing in source.features.items():
        for identifier, feature in result.features.items():
            if (
                identifier not in assigned
                and existing.kind == feature.kind
                and set(existing.face_indices) == set(feature.face_indices)
            ):
                mapping[name] = identifier
                assigned.add(identifier)
                break
    renamed = apply_mapping(
        result.features,
        MatchResult(
            mapping=mapping, orphaned=tuple(set(source.features) | set(source.reserved_feature_ids))
        ),
        previous=source.features,
    )
    # Bereits belegte Texturen behalten ihre Herkunft und ihren Feldumfang.
    # Ein neuer, nur teilweise überlappender Fund darf sie nicht überdecken.
    occupied = {
        index
        for feature in source.features.values()
        if feature.kind == "pattern" and feature.recognised
        for index in feature.face_indices
    }
    renamed = {
        name: feature
        for name, feature in renamed.items()
        if name in source.features
        or feature.kind != "pattern"
        or occupied.isdisjoint(feature.face_indices)
    }
    features = without_pattern_cells({**renamed, **source.features})
    ctx.cancelled.raise_if_cancelled()
    ctx.progress(1.0, tr("Merkmale an dieser Stelle erkennen"))
    return OpResult(outputs=[replace(source, features=features)], answered=answered)
