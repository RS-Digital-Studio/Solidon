"""Eine gespeicherte Operation für Dichtnut, getrennte Dichtung und Gegenfläche."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import numpy as np

from app.core.errors import CHOOSE_PRINTER, ValidationError
from app.core.geom.boolean import BooleanOutcome, boolean, deepest
from app.core.geom.contours import offset_section, polygons_of, section_of
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.seal import (
    _SEAL_SAG,
    _band,
    _mesh,
    match_opening,
    opening_choices,
    polygon_profile,
    seal_geometry,
    support_geometry,
)
from app.core.knowledge import profiles
from app.core.registry import op_params, param, register_op
from app.core.sketch.planes import feature_plane, frame_for_plane
from app.core.sketch.profile import Profile as SketchProfile
from app.core.sketch.profile import profile_of
from app.core.sketch.serialize import sketch_from_text
from app.core.types import (
    BaseParams,
    Feature,
    FeatureRef,
    Finding,
    OpContext,
    OpResult,
    PlaneFrame,
    SceneObject,
    Transform,
    Vec3,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM
from app.i18n import TranslatableText, _


@op_params
class CreateSealParams(BaseParams):
    path_sketch: str = param(
        title=_("Dichtweg"),
        kind="sketch",
        default="",
        doc=_("Ein geschlossener gezeichneter Verlauf oder eine ausdrücklich gewählte Öffnung."),
    )
    groove_width: float = param(
        title=_("Nutbreite"),
        default=3.0,
        minimum=0.1,
        maximum=100.0,
        unit="mm",
        doc=_("Gesamte Breite der Nut quer zum Dichtweg."),
    )
    groove_depth: float = param(
        title=_("Nuttiefe"),
        default=2.0,
        minimum=0.1,
        maximum=100.0,
        unit="mm",
        doc=_("Tiefe unter der Trägerfläche; Boden und Seitenwände werden am Körper geprüft."),
    )
    section: str = param(
        title=_("Dichtquerschnitt"),
        default="rectangle",
        choices=("rectangle", "round"),
        doc=_("Rechteckige Dichtung oder runde Schnur entlang desselben geschlossenen Wegs."),
    )
    protrusion: float = param(
        title=_("Überstand"),
        default=0.4,
        minimum=0,
        maximum=100.0,
        unit="mm",
        doc=_(
            "Unverformte Höhe über der Nutmündung; zusammen mit der Nuttiefe "
            "ergibt sie die Dichtungshöhe."
        ),
    )
    gasket_width: float = param(
        title=_("Dichtungsbreite"),
        default=2.6,
        minimum=0.1,
        maximum=100.0,
        unit="mm",
        depends_on=("section", ("rectangle",)),
        doc=_("Breite des rechteckigen Querschnitts quer zum Dichtweg."),
    )
    body_material: str = param(
        title=_("Material des Trägers"),
        kind="material",
        default="",
        required=True,
        doc=_("Das ausdrücklich gewählte Material bestimmt die erforderliche Restwand."),
    )
    gasket_material: str = param(
        title=_("Material der Dichtung"),
        kind="material",
        default="",
        required=True,
        doc=_(
            "Eigenes Material der getrennten Dichtung; es verändert die eingegebenen Maße nicht."
        ),
    )
    offset: float = param(
        title=_("Seitlicher Versatz"),
        default=0.0,
        minimum=-1000.0,
        maximum=1000.0,
        unit="mm",
        placement="advanced",
        doc=_("Positiv verschiebt den ganzen Dichtweg nach außen, negativ nach innen."),
    )
    support_feature: str = param(
        title=_("Trägerfläche"),
        default="",
        targets_feature=True,
        placement="advanced",
        doc=_("Ebene Fläche des Trägers, deren geschlossene Öffnung verwendet wird."),
    )
    opening_signature: str = param(
        title=_("Gewählte Öffnung"),
        default="",
        placement="advanced",
        doc=_("Gespeicherte geometrische Wahl innerhalb der Trägerfläche."),
    )
    counterface: str = param(
        title=_("Gegenfläche"),
        default="",
        targets_feature=True,
        placement="advanced",
        doc=_(
            "Optionaler geometrischer Bezug: diese ebene Fläche muss "
            "den ganzen Dichtring überdecken."
        ),
    )


def _invalid(field: str, detail: TranslatableText) -> ValidationError:
    return ValidationError(field=field, constraint="seal_geometry", detail=detail)


def _reference(text: str, field: str) -> FeatureRef:
    try:
        return FeatureRef.parse(text)
    except ValueError as problem:
        raise _invalid(
            field, _("Wählen Sie eine vorhandene Fläche zusammen mit ihrem Körper.")
        ) from problem


def _matrix(frame: PlaneFrame) -> np.ndarray:
    result = np.eye(4)
    result[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    result[:3, 3] = frame.origin
    return result


def _placed(mesh: MeshData, frame: PlaneFrame) -> MeshData:
    raw = mesh.raw.copy()
    raw.apply_transform(_matrix(frame))
    return mesh.replacing(raw)


def _polygon_in_frame(polygon: Any, before: PlaneFrame, after: PlaneFrame) -> Any:
    from shapely.ops import transform

    matrix = np.linalg.inv(_matrix(after)) @ _matrix(before)

    def point(x: Any, y: Any, z: Any = None) -> tuple[Any, Any]:
        return (
            matrix[0, 0] * x + matrix[0, 1] * y + matrix[0, 3],
            matrix[1, 0] * x + matrix[1, 1] * y + matrix[1, 3],
        )

    return transform(point, polygon)


def _path(
    ctx: OpContext, p: CreateSealParams, findings: list[Finding]
) -> tuple[SketchProfile, PlaneFrame, str, dict[str, Any]]:
    from app.core.sketch.ops import _solved_drawing

    if p.path_sketch and (p.support_feature or p.opening_signature):
        raise _invalid(
            "path_sketch", _("Wählen Sie entweder eine Zeichnung oder eine Öffnung als Dichtweg.")
        )
    if p.path_sketch:
        plane = sketch_from_text(p.path_sketch).plane
        frame = frame_for_plane(plane, ctx.scene.objects.values())
        if frame is None:
            raise _invalid(
                "path_sketch", _("Wählen Sie eine vorhandene Zeichenebene für den Dichtweg.")
            )
        if plane.startswith("plane:"):
            vertices = as_mesh_data(ctx.inputs[0].mesh).raw.vertices
            top = float(np.max(vertices @ frame.normal))
            frame = replace(frame, origin=cast(Vec3, tuple(top * np.asarray(frame.normal))))
        return profile_of(_solved_drawing(ctx, p.path_sketch, findings)), frame, plane, {}
    ref = _reference(p.support_feature, "support_feature")
    choices = opening_choices(ctx.inputs[0], ref, check_cancelled=ctx.cancelled.raise_if_cancelled)
    if not choices:
        raise _invalid(
            "support_feature",
            _(
                "Diese Fläche hat keine geschlossene Öffnung. Zeichnen Sie einen "
                "Dichtweg oder wählen Sie eine andere Fläche."
            ),
        )
    selected = match_opening(choices, p.opening_signature) if p.opening_signature else None
    answered: dict[str, Any] = {}
    if selected is None:
        labels = [
            str(
                _(
                    "Kontur {number}: {area} mm², Mitte {x} / {y} mm",
                    number=i + 1,
                    area=f"{c.area:.2f}",
                    x=f"{c.centre[0]:.2f}",
                    y=f"{c.centre[1]:.2f}",
                )
            )
            for i, c in enumerate(choices)
        ]
        answer = ctx.ask(str(_("Welche geschlossene Öffnung soll den Dichtweg bestimmen?")), labels)
        if answer not in labels:
            raise _invalid(
                "opening_signature", _("Wählen Sie eine der angezeigten Konturen für den Dichtweg.")
            )
        selected = choices[labels.index(answer)]
        answered["opening_signature"] = selected.signature
    return selected.profile, selected.frame, feature_plane(ref.object_id, ref.feature_id), answered


def _thicker_than_shown(volume: float, area: float) -> bool:
    """Ob ein Rest- oder Kollisionsvolumen über der Anzeigegrenze liegt.

    Gemessen wird die mittlere Dicke über der Bezugsfläche, nicht das Volumen
    allein: Die Dichtung steht auf dem Nutboden, und zwei Flächen, die am
    geraden Träger exakt aufeinanderliegen, durchdringen sich nach einer
    Drehung um Nanometer — auf Linux bei einer anderen Achse als auf Windows.
    Was unter ``EPS_DISPLAY`` liegt, zeigt kein Maß und druckt kein Drucker;
    das ist keine Überschneidung, sondern die Fließkommarechnung.
    """
    return volume > EPS_DISPLAY * area


def _measured_boolean(
    ctx: OpContext, kind: str, first: MeshData, second: MeshData
) -> BooleanOutcome:
    from app.core.geom.boolean import BooleanKind

    outcome = boolean(
        cast(BooleanKind, kind),
        [first, second],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        allow_empty=True,
    )
    if outcome.solver.strategy not in ("direct", "welded"):
        raise _invalid(
            "groove_width",
            _(
                "Die Restwand lässt sich an diesem Netz nicht genau genug bestätigen. "
                "Reparieren Sie den Träger oder ändern Sie den Dichtweg."
            ),
        )
    return outcome


def _named_floor(
    output: SceneObject, frame: PlaneFrame, footprint: Any, depth: float
) -> SceneObject:
    from shapely import contains_xy

    mesh = as_mesh_data(output.mesh)
    inverse = np.linalg.inv(_matrix(frame))
    centres = mesh.raw.triangles_center @ inverse[:3, :3].T + inverse[:3, 3]
    normals = mesh.raw.face_normals @ np.asarray(frame.normal)
    mask = (
        (np.abs(centres[:, 2] + depth) <= EPS_GEOM)
        & (normals > 1 - EPS_GEOM)
        & contains_xy(footprint.buffer(EPS_GEOM), centres[:, 0], centres[:, 1])
    )
    indices = np.flatnonzero(mask)
    if not len(indices):
        raise _invalid(
            "groove_depth",
            _(
                "Der Nutboden wurde nicht eindeutig gefunden. "
                "Ändern Sie den Dichtweg oder die Tiefe."
            ),
        )
    area = mesh.raw.area_faces[indices]
    centre = np.average(mesh.raw.triangles_center[indices], weights=area, axis=0)
    feature = Feature(
        "groove_floor",
        "face",
        "generated",
        {
            "area": float(area.sum()),
            "centre": tuple(float(v) for v in centre),
            "normal": frame.normal,
        },
        face_indices=tuple(int(i) for i in indices),
        recognised=False,
    )
    return replace(output, features={**output.features, feature.id: feature})


def _body_material(
    ctx: OpContext, output: SceneObject, material: str, findings: list[Finding]
) -> SceneObject:
    """Farbflächen erhalten; fremde Filamentprofile beim Materialwechsel lösen.

    Die gemeinsame Taschenoperation überträgt Dreiecksattribute bereits mit
    ``attributes.transfer``. Hier ändern sich ausschließlich Slotbindungen,
    niemals ihre Farbe, Kennung oder die Zuordnung der bemalten Dreiecke.
    """
    old = profiles.for_object(ctx.profile, ctx.inputs[0]).material.id
    slots = list(output.material_slots)
    if old != material:
        released = False
        for index, slot in enumerate(slots):
            known = profiles.material_id_for_type(slot.material_type or "")
            if known != material and (slot.material or slot.material_type):
                slots[index] = replace(slot, material=None, material_type=None)
                released = True
        if released:
            findings.append(
                Finding(
                    code="seal.filament_reassign",
                    severity="info",
                    message=_(
                        "Der Träger hat ein anderes Material. Farben bleiben erhalten; "
                        "weisen Sie den betroffenen Farbbereichen passende Filamente zu."
                    ),
                )
            )
    return replace(output, material=material, material_slots=slots)


def _counterface(
    ctx: OpContext, p: CreateSealParams, frame: PlaneFrame, footprint: Any, gasket: MeshData
) -> list[Finding]:
    if not p.counterface:
        return []
    ref = _reference(p.counterface, "counterface")
    source = ctx.scene.objects.get(ref.object_id)
    if source is None or source.id == ctx.inputs[0].id:
        raise _invalid(
            "counterface", _("Wählen Sie eine Gegenfläche an einem anderen vorhandenen Körper.")
        )
    other_frame, surface, _topology = support_geometry(
        source, ref, check_cancelled=ctx.cancelled.raise_if_cancelled
    )
    if np.dot(frame.normal, other_frame.normal) > -1 + EPS_GEOM:
        raise _invalid(
            "counterface",
            _(
                "Die Gegenfläche muss parallel sein und zur Dichtung zeigen. "
                "Richten Sie den Gegenkörper aus."
            ),
        )
    projected = _polygon_in_frame(surface, other_frame, frame)
    if not projected.buffer(EPS_GEOM).covers(footprint):
        raise _invalid(
            "counterface",
            _(
                "Die Gegenfläche überdeckt den Dichtring nicht vollständig. "
                "Vergrößern oder verschieben Sie die Gegenfläche."
            ),
        )
    gap = float(np.dot(np.asarray(other_frame.origin) - frame.origin, frame.normal))
    if gap < -EPS_GEOM:
        raise _invalid(
            "counterface",
            _(
                "Die Gegenfläche liegt unter der Nutmündung. "
                "Verschieben Sie den Gegenkörper über den Träger."
            ),
        )
    overlap = p.protrusion - gap
    intersection = _measured_boolean(ctx, "intersection", gasket, as_mesh_data(source.mesh))
    return [
        Finding(
            code="seal.counterface",
            severity="warning" if overlap <= EPS_GEOM else "info",
            message=_(
                "Gegenfläche geometrisch geprüft: Abstand {gap} mm, unverformte "
                "Überdeckung {overlap} mm. Das belegt keine Dichtheit.",
                gap=f"{gap:.3f}",
                overlap=f"{overlap:.3f}",
            ),
            values={
                "gap_mm": gap,
                "overlap_mm": overlap,
                "intersection_mm3": intersection.mesh.volume,
            },
        )
    ]


@register_op(
    name="create_seal",
    title=_("Dichtnut mit Dichtung"),
    category="prepare",
    params=CreateSealParams,
    consumes=1,
    produces=2,
    keeps_inputs=1,
    reads_other_bodies=True,
    touches_features=True,
    material_params=("body_material", "gasket_material"),
    applies_to=["face"],
    doc=_(
        "Schneidet eine geprüfte Dichtnut und erzeugt dazu eine getrennte Dichtung "
        "mit eigenem Material."
    ),
)
def create_seal(ctx: OpContext) -> OpResult:
    from app.core.knowledge.parts.seals import seal_features
    from app.core.perceive.matching import moved_features
    from app.core.sketch.ops import cut_regions
    from app.core.slice.analysis import cross_section

    p = cast(CreateSealParams, ctx.params)
    ctx.cancelled.raise_if_cancelled()
    if ctx.profile is None:
        raise ValidationError(
            "body_material",
            _("Wählen Sie einen Drucker für die Restwandprüfung."),
            suggestions=[CHOOSE_PRINTER],
        )
    body_profile = replace(ctx.profile, material=profiles.material(p.body_material))
    gasket_profile = replace(ctx.profile, material=profiles.material(p.gasket_material))
    effective_width = p.groove_depth + p.protrusion if p.section == "round" else p.gasket_width
    if (
        min(effective_width, p.groove_depth + p.protrusion)
        < gasket_profile.minimum_wall_thickness - EPS_GEOM
    ):
        raise _invalid(
            "gasket_width",
            _(
                "Der Dichtquerschnitt ist für dieses Material zu dünn. "
                "Vergrößern Sie Breite oder Höhe."
            ),
        )
    findings: list[Finding] = []
    path, frame, plane, answered = _path(ctx, p, findings)
    ctx.progress(0.1, str(_("Dichtweg und Restwand prüfen")))
    geometry = seal_geometry(
        path,
        groove_width=p.groove_width,
        groove_depth=p.groove_depth,
        protrusion=p.protrusion,
        gasket_width=p.gasket_width,
        section=p.section,
        offset=p.offset,
        check_cancelled=ctx.cancelled.raise_if_cancelled,
    )
    section = offset_section(section_of(path, max_sag=_SEAL_SAG), p.offset, max_sag=_SEAL_SAG)
    band = _band(section, p.groove_width, ctx.cancelled.raise_if_cancelled)
    footprint = polygons_of(band)[0]
    wall = body_profile.minimum_wall_thickness
    envelope = _band(section, p.groove_width + 2 * wall, ctx.cancelled.raise_if_cancelled)
    envelope_mesh = _placed(
        _mesh(envelope.extrude(p.groove_depth + wall).translate((0, 0, -p.groove_depth - wall))),
        frame,
    )
    missing = _measured_boolean(ctx, "difference", envelope_mesh, as_mesh_data(ctx.inputs[0].mesh))
    if _thicker_than_shown(missing.mesh.volume, envelope_mesh.raw.area):
        raise _invalid(
            "groove_depth",
            _(
                "Unter oder neben der Nut bleibt zu wenig Material. Verkleinern Sie "
                "Breite oder Tiefe oder verschieben Sie den Dichtweg."
            ),
        )
    cut_frame = frame_for_plane(plane, ctx.scene.objects.values())
    assert cut_frame is not None
    cut_polygon = _polygon_in_frame(footprint, frame, cut_frame)
    ctx.progress(0.45, str(_("Dichtnut schneiden")))
    cut = cut_regions(
        ctx, [polygon_profile(cut_polygon)], plane, depth=p.groove_depth, through=False
    )
    body = _named_floor(
        _body_material(ctx, cut.outputs[0], p.body_material, findings),
        frame,
        footprint,
        p.groove_depth,
    )
    gasket_mesh = _placed(geometry.gasket, frame)
    collision = _measured_boolean(ctx, "intersection", as_mesh_data(body.mesh), gasket_mesh)
    if _thicker_than_shown(collision.mesh.volume, gasket_mesh.raw.area):
        raise _invalid(
            "gasket_width",
            _(
                "Die unverformte Dichtung überschneidet den Träger. Verkleinern Sie "
                "den Querschnitt oder vergrößern Sie die Nut."
            ),
        )
    features = moved_features(
        seal_features(geometry.gasket, gasket=True, rounded=p.section == "round"),
        cast(Transform, tuple(tuple(float(v) for v in row) for row in _matrix(frame))),
    )
    gasket = SceneObject(
        "", _("Dichtung"), gasket_mesh, features=features, material=p.gasket_material
    )
    gasket_footprint = cross_section(
        geometry.gasket, -p.groove_depth + (p.groove_depth + p.protrusion) / 2
    )
    assert gasket_footprint is not None
    findings.extend(_counterface(ctx, p, frame, gasket_footprint, gasket_mesh))
    findings.append(
        Finding(
            code="seal.uncompressed",
            severity="info",
            message=_(
                "Die Dichtung ist unverformt dargestellt. Maße und Restwand sind "
                "geometrisch geprüft; eine Dichtwirkung ist damit nicht nachgewiesen."
            ),
            values={"nominal_side_clearance_mm": geometry.clearance, "required_wall_mm": wall},
        )
    )
    return OpResult(
        outputs=[body, gasket],
        solver=deepest((cut.solver, missing.solver, collision.solver)),
        findings=[*findings, *cut.findings],
        answered=answered,
    )
