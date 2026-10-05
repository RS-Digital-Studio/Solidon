"""Nachbau als neue registrierte Operationsfolge (Bauplan §42, CAD-Konzept §13.5).

Ein Vorschlag rechnet ausschließlich in einem eigenen Dokument. Die Merkmale
liefern Kandidaten; erst ein unabhängiger Vergleich der vollständigen Form
entscheidet, ob ein Kandidat übernommen werden darf.
"""

from __future__ import annotations

import math
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field, replace
from itertools import pairwise, product
from typing import Any

import numpy as np

from app.core.errors import CANCEL, UserError, ValidationError
from app.core.geom.difference import SurfaceDistanceBound, surface_distance_bound
from app.core.geom.mesh import MeshData, as_mesh_data, face_components, signed_volume, unique_edges
from app.core.geom.transform import along, turned
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.scene.evaluate import SOURCE_KINDS, EvaluationResult, evaluate
from app.core.scene.history import History, OperationDraft, change_for
from app.core.scene.serialise import document_to_data
from app.core.types import (
    CancelToken,
    Document,
    DocumentChange,
    Feature,
    Finding,
    Parameter,
    Profile,
    ProgressFn,
    SceneObject,
    SourceAccess,
    Transaction,
)
from app.core.units import EPS_GEOM, dot3, exact_cos_degrees, exact_sin, plane_axes
from app.i18n import TranslatableText, _


@dataclass(frozen=True, slots=True)
class RebuildBudget:
    """Ausdrücklich gewählte Form- und Volumengrenze; kein Fertigungsspiel.

    Ein Zehntel des lokalen Budgets bleibt für die zusätzliche Tessellation
    des Kandidaten reserviert. Der übrige Anteil wird am gesamten Netz geprüft.
    Die Facettierung der Quelldatei ist Teil der gemessenen Formabweichung;
    sie wird weder korrigiert noch mit der Materialtoleranz verrechnet.
    """

    local_mm: float
    volume_relative: float

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.local_mm)
            or self.local_mm <= 10.0 * EPS_GEOM
            or not math.isfinite(self.volume_relative)
            or not 0.0 < self.volume_relative < 1.0
        ):
            raise ValidationError(
                "tolerance",
                _(
                    "Geben Sie eine positive Formgrenze und eine Volumengrenze "
                    "unter 100 Prozent ein."
                ),
            )

    @property
    def tessellation_mm(self) -> float:
        return self.local_mm / 10.0


@dataclass(frozen=True, slots=True)
class RebuildCheck:
    accepted: bool
    reason: str
    volume_relative: float
    surface: SurfaceDistanceBound | None = None
    unexplained: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RebuildCandidate:
    drafts: tuple[OperationDraft, ...]
    result: SceneObject
    check: RebuildCheck
    _checked_drafts: tuple[OperationDraft, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # OperationDraft.params ist eine veränderliche Zuordnung. Die spätere
        # Übernahme muss genau die Folge verwenden, die den Vergleich bestand.
        object.__setattr__(self, "_checked_drafts", deepcopy(self.drafts))


@dataclass(frozen=True, slots=True)
class RebuildProposal:
    source: SceneObject
    budget: RebuildBudget
    candidates: tuple[RebuildCandidate, ...]
    document_mark: dict[str, Any]
    failures: tuple[Finding, ...] = ()

    @property
    def accepted(self) -> tuple[RebuildCandidate, ...]:
        return tuple(entry for entry in self.candidates if entry.check.accepted)


def _shells(mesh: MeshData, cancelled: CancelToken) -> tuple[tuple[int, int], ...]:
    """Zusammenhang, Hohlräume und Gattung je orientierter Schale."""
    result = []
    for indices in face_components(mesh.raw, cancelled=cancelled):
        cancelled.raise_if_cancelled()
        faces = np.asarray(mesh.raw.faces)[indices]
        vertices = np.unique(faces).size
        edges = np.sort(faces[:, ((0, 1), (1, 2), (2, 0))].reshape(-1, 2), axis=1)
        euler = int(vertices - len(unique_edges(edges)[0]) + len(faces))
        triangles = np.asarray(mesh.raw.triangles)[indices]
        from app.core.geom.mesh import triple_products

        volume = math.fsum(triple_products(triangles - triangles[0, 0]).tolist()) / 6.0
        result.append((1 if volume > EPS_GEOM else -1, euler))
    return tuple(sorted(result))


def check_shape(
    source: MeshData,
    candidate: SceneObject,
    budget: RebuildBudget,
    *,
    cancelled: CancelToken | None = None,
) -> RebuildCheck:
    """Prüft den tatsächlich gebauten Körper, unabhängig von seiner Konstruktion."""
    from app.core.brep.kernel import Solid
    from app.core.brep.profiles import is_sound

    token = cancelled or NeverCancelled()
    token.raise_if_cancelled()
    body = candidate.mesh
    if not isinstance(body, Solid) or not is_sound(body) or not body.is_watertight:
        return RebuildCheck(False, "invalid", math.inf)
    measured = body.to_mesh(deflection=budget.tessellation_mm)
    if _shells(source, token) != _shells(measured, token):
        return RebuildCheck(False, "topology", math.inf)
    reference_volume = signed_volume(source.raw)
    if reference_volume <= EPS_GEOM:
        return RebuildCheck(False, "invalid_source", math.inf)
    relative = abs(body.volume - reference_volume) / reference_volume
    if relative > budget.volume_relative:
        return RebuildCheck(False, "volume", relative)
    surface = surface_distance_bound(
        source,
        measured,
        permitted_mm=budget.local_mm - budget.tessellation_mm,
        cancelled=token,
    )
    if not surface.within_limit:
        return RebuildCheck(
            False,
            "surface" if surface.lower_mm > surface.permitted_mm else "incomplete",
            relative,
            surface,
        )
    return RebuildCheck(True, "accepted", relative, surface)


def _position(point: np.ndarray, axis: np.ndarray | None = None) -> dict[str, float]:
    result = dict(zip(("x", "y", "z"), map(float, point), strict=True))
    if axis is not None:
        result.update(zip(("nx", "ny", "nz"), map(float, axis), strict=True))
    return result


def _unexplained_planes(
    source: SceneObject,
    candidate: SceneObject,
    cancelled: CancelToken,
    boundary_mm: float = EPS_GEOM,
) -> set[str]:
    """Eine kleine unbekannte Stufe verschwindet nicht im erlaubten Formbudget.

    Jede begrenzte ebene Teilfläche braucht eine überlappende Fläche in
    derselben gerichteten Ebene. Die Formgrenze erlaubt keine fehlenden
    Taschenböden, auch unterhalb des lokalen Abstandsbudgets.
    """
    import shapely

    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.perceive.features import EPS_ANGLE

    body = candidate.mesh
    if not isinstance(body, Solid):
        return {feature.id for feature in source.features.values() if feature.kind == "face"}
    planes = [
        feature
        for feature in features_of(body, cancelled=cancelled).values()
        if feature.kind == "face"
    ]
    original_triangles = np.asarray(as_mesh_data(source.mesh).raw.triangles)
    candidate_triangles = np.asarray(as_mesh_data(body).raw.triangles)
    unexplained = set()
    for feature in source.features.values():
        cancelled.raise_if_cancelled()
        if feature.kind != "face":
            continue
        normal = np.asarray(feature.params["normal"], dtype=float)
        centre = np.asarray(feature.params["centre"], dtype=float)
        matching = [
            plane
            for plane in planes
            if dot3(normal, plane.params["normal"]) >= exact_cos_degrees(EPS_ANGLE)
            and abs(dot3(np.asarray(plane.params["centre"]) - centre, normal)) <= EPS_GEOM
        ]
        indices = [index for plane in matching for index in plane.face_indices]
        if not indices or not feature.face_indices:
            unexplained.add(feature.id)
            continue
        # Dieselbe unendliche Ebene an einer anderen Tasche ist kein Beleg.
        # Verglichen werden die begrenzten Flächen einschließlich ihrer Löcher.
        axes = plane_axes(tuple(normal))
        if axes is None:
            unexplained.add(feature.id)
            continue
        frame = np.array((*axes, normal))
        before = turned(original_triangles[list(feature.face_indices)] - centre, frame)
        after = turned(candidate_triangles[indices] - centre, frame)
        source_area = shapely.union_all(shapely.polygons(before[:, :, :2]))
        target_area = shapely.union_all(shapely.polygons(after[:, :, :2]))
        # Gekrümmte Innenränder dürfen innerhalb des ausdrücklichen Formbudgets
        # von ihren Facetten abweichen. Jede zusammenhängende Quellfläche muss
        # trotzdem an ihrer tatsächlichen Stelle erhalten bleiben, auch wenn
        # sie schmaler als dieses Budget ist.
        pieces = shapely.get_parts(source_area)
        overlap = shapely.area(shapely.intersection(pieces, target_area))
        if np.any(overlap <= EPS_GEOM * EPS_GEOM) or not target_area.buffer(boundary_mm).covers(
            source_area
        ):
            unexplained.add(feature.id)
    return unexplained


def _single(feature: Feature) -> OperationDraft | None:
    """Ein ganzes Rundteil ist ein Kandidat, nicht bereits eine Formentscheidung."""
    params = feature.params
    if params.get("recess", False):
        return None
    centre = np.asarray(params.get("centre"), dtype=float)
    axis = np.asarray(params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
    if feature.kind == "pin":
        height = float(params["depth"])
        return OperationDraft(
            "create_brep_cylinder",
            params={
                "diameter": params["diameter"],
                "height": height,
                **_position(centre - axis * height / 2.0, axis),
            },
            outputs=("obj_1",),
        )
    if feature.kind == "torus":
        tube = float(params["tube_diameter"])
        return OperationDraft(
            "create_brep_torus",
            params={
                "outer_diameter": float(params["diameter"]) + tube,
                "tube_diameter": tube,
                **_position(centre - axis * tube / 2.0, axis),
            },
            outputs=("obj_1",),
        )
    if feature.kind == "sphere":
        diameter = float(params["diameter"])
        return OperationDraft(
            "create_brep_sphere",
            params={
                "diameter": diameter,
                **_position(centre - np.array((0.0, 0.0, diameter / 2.0))),
            },
            outputs=("obj_1",),
        )
    return None


def _oriented_basis(source: SceneObject) -> np.ndarray | None:
    """Orthogonaler Kandidatenrahmen aus tatsächlich erkannten Außenebenen."""
    from app.core.perceive.features import EPS_ANGLE

    planes = sorted(
        (
            feature
            for feature in source.features.values()
            if feature.kind == "face" and not feature.params.get("inner")
        ),
        key=lambda feature: -float(feature.params.get("area", 0.0)),
    )
    if len(planes) < 2:
        return None
    z = np.array(planes[0].params["normal"], dtype=float, copy=True)
    z /= math.sqrt(dot3(z, z))
    for feature in planes[1:]:
        x = np.array(feature.params["normal"], dtype=float, copy=True)
        if abs(dot3(x, z)) > exact_sin(math.radians(EPS_ANGLE)):
            continue
        x -= z * dot3(x, z)
        x /= math.sqrt(dot3(x, x))
        basis = np.column_stack((x, np.cross(z, x), z))
        # Eine Achsenvertauschung beschreibt denselben bereits geprüften Quader.
        if np.all(np.max(np.abs(basis), axis=0) > 1.0 - EPS_GEOM):
            return None
        return basis
    return None


def _sinks_of(feature: Feature, features: tuple[Feature, ...], tolerance: float) -> list[Feature]:
    """Die vertieften Kegel auf der Achse einer Bohrung — Kandidaten ihrer Senkung."""
    params = feature.params
    axis = np.array(params["axis"], dtype=float, copy=True)
    axis /= math.sqrt(dot3(axis, axis))
    centre = np.asarray(params["centre"], dtype=float)
    cones = []
    for cone in features:
        if cone.kind != "cone" or not cone.params.get("recess", False):
            continue
        cone_axis = np.asarray(cone.params["axis"], dtype=float)
        displacement = np.asarray(cone.params["centre"], dtype=float) - centre
        if (
            math.hypot(*np.cross(cone_axis, axis)) < EPS_GEOM
            and math.hypot(*np.cross(displacement, axis)) <= tolerance
        ):
            cones.append(cone)
    return cones


def _drilled(
    feature: Feature, features: tuple[Feature, ...], tolerance: float
) -> tuple[OperationDraft, set[str]]:
    """Ein erkanntes Loch als Abzug: Bohrung oder Langloch, mit eindeutiger Senkung.

    Fertigungskompensation bleibt aus (CAD-Konzept §13.5). Zurück kommen der
    Schritt und die Merkmale, die er erklärt.
    """
    from app.core.geom.prepare_ops import slot_angle_of

    params = feature.params
    axis = np.array(params["axis"], dtype=float, copy=True)
    axis /= math.sqrt(dot3(axis, axis))
    centre = np.asarray(params["centre"], dtype=float)
    hole_depth = float(params["depth"])
    mouth = centre + axis * hole_depth / 2.0
    hole_params: dict[str, Any] = {
        "diameter": params["diameter"],
        "compensate": False,
        "depth": 0.0 if params.get("through", False) else hole_depth,
        **_position(mouth, axis),
    }
    explained = {feature.id}
    if feature.kind == "slot":
        hole_params.update(
            slotted=True,
            slot_length=params["length"],
            slot_angle=slot_angle_of(feature, tuple(axis)),
        )
    else:
        cones = _sinks_of(feature, features, tolerance)
        if len(cones) == 1:
            cone = cones[0]
            cone_axis = np.asarray(cone.params["axis"], dtype=float)
            cone_mouth = np.asarray(cone.params["centre"], dtype=float)
            hole_params.update(
                widening_diameter=cone.params["diameter"],
                widening_depth=0.0,
                transition_angle=cone.params["angle"],
                **_position(
                    cone_mouth,
                    cone_axis,
                ),
            )
            if not params.get("through", False):
                # Die Bohrtiefe beginnt an der Mündung der Senkung. Der
                # erkannte Zylindermantel beginnt erst unter ihrem Kegel.
                floor = centre - cone_axis * hole_depth / 2.0
                hole_params["depth"] = dot3(cone_mouth - floor, cone_axis)
            explained.add(cone.id)
    return OperationDraft("drill_brep_hole", ("obj_1",), hole_params), explained


def _boxed(
    source: SceneObject,
    tolerance: float,
    basis: np.ndarray | None = None,
) -> tuple[list[OperationDraft], set[str]]:
    from app.core.geom.primitive_ops import placement_values_of

    bounds = source.mesh.bounds
    centre = np.asarray(bounds.centre)
    centre[2] = bounds.minimum[2]
    width, depth, height = bounds.size
    placement = _position(centre)
    if basis is not None:
        vertices = np.asarray(as_mesh_data(source.mesh).raw.vertices)
        origin = np.asarray(bounds.centre)
        local = turned(vertices - origin, basis.T)
        low, high = local.min(axis=0), local.max(axis=0)
        width, depth, height = map(float, high - low)
        foot = (low + high) / 2.0
        foot[2] = low[2]
        matrix = np.eye(4)
        matrix[:3, :3] = basis
        matrix[:3, 3] = origin + turned(foot, basis)
        placement = placement_values_of(matrix)
    drafts = [
        OperationDraft(
            "create_brep_box",
            params={
                "width": width,
                "depth": depth,
                "height": height,
                **placement,
            },
            outputs=("obj_1",),
        )
    ]
    explained: set[str] = set()
    features = tuple(source.features.values())
    for feature in features:
        if feature.kind not in {"hole", "slot"}:
            continue
        draft, claimed = _drilled(feature, features, tolerance)
        drafts.append(draft)
        explained |= claimed
    for feature in features:
        if feature.kind != "sphere" or not feature.params.get("recess", False):
            continue
        diameter = float(feature.params["diameter"])
        centre = np.asarray(feature.params["centre"], dtype=float)
        drafts.extend(
            (
                OperationDraft(
                    "create_brep_sphere",
                    params={
                        "diameter": diameter,
                        **_position(centre - np.array((0.0, 0.0, diameter / 2.0))),
                    },
                    outputs=("obj_2",),
                ),
                OperationDraft("subtract_objects", ("obj_1", "obj_2"), outputs=("obj_1",)),
            )
        )
        explained.add(feature.id)
    return drafts, explained


def _without_holes(
    solid: Any, holes: list[Feature], sinks: dict[str, Feature], cancelled: CancelToken
) -> Any:
    """Der Körper ohne die genannten Löcher und ihre Senkungen — oder ``None``.

    Die Nachbarflächen laufen über die Öffnung weiter (``edit.defeatured``),
    wie beim Schließen eines Lochs.
    """
    from app.core.brep import edit

    triangles = [index for feature in holes for index in feature.face_indices]
    triangles.extend(
        index
        for feature in holes
        if feature.id in sinks
        for index in sinks[feature.id].face_indices
    )
    native = solid.faces_of_triangles(triangles) if triangles else ()
    return edit.defeatured(solid, native, cancelled=cancelled) if native else None


def _layered(
    source: SceneObject, tolerance: float, cancelled: CancelToken
) -> list[tuple[list[OperationDraft], set[str], SceneObject]]:
    """Echte Querschnitte zwischen ebenen Stufen werden bearbeitbare Skizzen.

    Die Seiten müssen entlang einer gemeinsamen Richtung verlaufen. Der
    Schnitt kommt aus P4.0; die abschließende Formprüfung bleibt unabhängig.
    Keine Schicht überbrückt eine ungemessene Stufe oder füllt einen Innenrand.

    Zapfen, Rundungen und Löcher längs der Richtung stehen im Querschnitt als
    Bögen und Innenränder. Was er nicht trägt, wird danach gebohrt, ohne
    Kompensation (CAD-Konzept §13.5): Bohrungen und Langlöcher quer zur
    Richtung und jede Bohrung mit Senkung.
    Geschnitten wird dafür der Körper ohne diese Löcher, sonst zöge ein
    Querschnitt durch eine Querbohrung sie über die ganze Schicht. Eine
    Rundungsecke und ein Kegel ohne seine Bohrung stehen in keinem Querschnitt.
    """
    from app.core.brep.kernel import Solid
    from app.core.brep.section import plane_section
    from app.core.perceive.features import EPS_ANGLE
    from app.core.sketch.planes import frame_for_plane, frame_of, through_plane
    from app.core.sketch.serialize import sketch_to_text
    from app.core.types import Sketch, SketchConstraint, SketchElement

    if not isinstance(source.mesh, Solid):
        return []
    features = tuple(source.features.values())
    if any(
        feature.kind not in {"face", "pin", "hole", "slot", "fillet", "cone"}
        for feature in features
    ):
        return []
    sinks = {
        feature.id: cones[0]
        for feature in features
        if feature.kind == "hole" and len(cones := _sinks_of(feature, features, tolerance)) == 1
    }
    sunk = {cone.id for cone in sinks.values()}
    if any(
        (feature.kind == "fillet" and "axis" not in feature.params)
        or (feature.kind == "cone" and feature.id not in sunk)
        for feature in features
    ):
        return []
    parallel = exact_cos_degrees(EPS_ANGLE)
    perpendicular = exact_sin(math.radians(EPS_ANGLE))
    axes: list[np.ndarray] = []
    for feature in features:
        vector = feature.params.get("normal" if feature.kind == "face" else "axis")
        if vector is None:
            continue
        axis = np.array(vector, dtype=float, copy=True)
        axis /= math.sqrt(dot3(axis, axis))
        if any(abs(dot3(axis, previous)) >= parallel for previous in axes):
            continue
        axes.append(axis)
    plans = []
    origin = np.asarray(source.mesh.bounds.centre)
    vertices = np.asarray(source.mesh.to_mesh().raw.vertices)
    for axis in axes:
        cancelled.raise_if_cancelled()
        levels = []
        drilled: list[Feature] = []
        for feature in features:
            params = feature.params
            if feature.kind == "face":
                facing = abs(dot3(axis, params["normal"]))
                if facing >= parallel:
                    levels.append(dot3(np.asarray(params["centre"]) - origin, axis))
                elif facing > perpendicular:
                    break
            elif feature.kind == "cone":
                # Eine Senkung reist mit ihrer Bohrung.
                continue
            elif feature.kind in {"hole", "slot"}:
                facing = abs(dot3(axis, params["axis"]))
                if facing >= parallel and feature.id not in sinks:
                    continue
                if perpendicular < facing < parallel:
                    break
                drilled.append(feature)
            elif abs(dot3(axis, params["axis"])) < parallel:
                break
        else:
            body = source.mesh
            if drilled:
                body = _without_holes(source.mesh, drilled, sinks, cancelled)
                if body is None:
                    continue
            projection = along(vertices - origin, axis)
            levels.extend((float(projection.min()), float(projection.max())))
            distinct: list[float] = []
            for level in sorted(levels):
                if not distinct or level - distinct[-1] > EPS_GEOM:
                    distinct.append(level)
            drafts: list[OperationDraft] = []
            for lower, upper in pairwise(distinct):
                cancelled.raise_if_cancelled()
                foot = origin + axis * lower
                initial = frame_of(tuple(axis), tuple(foot))
                plane = through_plane(
                    (
                        initial.origin,
                        tuple(foot + initial.x_axis),
                        tuple(foot + initial.y_axis),
                    )
                )
                frame = frame_for_plane(plane)
                if frame is None:
                    break
                curves = plane_section(
                    body,
                    tuple(foot + axis * ((upper - lower) / 2.0)),
                    frame.x_axis,
                    frame.y_axis,
                    cancelled=cancelled,
                )
                if not curves:
                    continue
                if any(curve.kind == "spline" for curve in curves):
                    break
                elements = tuple(SketchElement(curve.kind, curve.points) for curve in curves)
                constraints = tuple(
                    SketchConstraint("fixed", (point,))
                    for point in range(sum(len(element.points) for element in elements))
                )
                sketch = Sketch(plane, elements, constraints)
                identifier = "obj_1" if not drafts else "obj_2"
                drafts.append(
                    OperationDraft(
                        "sketch_extrude",
                        params={"height": upper - lower, "sketch": sketch_to_text(sketch)},
                        outputs=(identifier,),
                    )
                )
                if identifier == "obj_2":
                    drafts.append(
                        OperationDraft("union_objects", ("obj_1", "obj_2"), outputs=("obj_1",))
                    )
            else:
                if drafts:
                    drafts.extend(_drilled(feature, features, tolerance)[0] for feature in drilled)
                    plans.append(
                        (
                            drafts,
                            {feature.id for feature in features if feature.kind != "face"},
                            source,
                        )
                    )
    return sorted(plans, key=lambda plan: len(plan[0]))


def _supported_box(source: SceneObject, basis: np.ndarray) -> OperationDraft | None:
    """Die größten gegenüberliegenden Stützebenen bestimmen ein Grundvolumen."""
    from app.core.geom.primitive_ops import placement_values_of
    from app.core.perceive.features import EPS_ANGLE

    planes = [feature for feature in source.features.values() if feature.kind == "face"]
    parallel = exact_cos_degrees(EPS_ANGLE)
    origin = np.asarray(source.mesh.bounds.centre)
    low: list[float] = []
    high: list[float] = []
    for axis in basis.T:
        for sign, bounds in ((-1, low), (1, high)):
            choices = [
                feature
                for feature in planes
                if sign * dot3(axis, feature.params["normal"]) >= parallel
            ]
            if not choices:
                return None
            plane = max(choices, key=lambda feature: float(feature.params.get("area", 0.0)))
            bounds.append(dot3(np.asarray(plane.params["centre"]) - origin, axis))
    size = np.asarray(high) - low
    if np.any(size <= EPS_GEOM):
        return None
    foot = (np.asarray(low) + high) / 2.0
    foot[2] = low[2]
    matrix = np.eye(4)
    matrix[:3, :3] = basis
    matrix[:3, 3] = origin + turned(foot, basis)
    return OperationDraft(
        "create_brep_box",
        params={
            "width": float(size[0]),
            "depth": float(size[1]),
            "height": float(size[2]),
            **placement_values_of(matrix),
        },
        outputs=("obj_1",),
    )


def _built(
    drafts: list[OperationDraft], document: Document, profile: Profile, cancelled: CancelToken
) -> EvaluationResult:
    candidate = Document(document.format_version, document.app_version)
    History(candidate).apply(_("Modell nachbauen"), drafts)
    return evaluate(candidate, profile, cancelled=cancelled, detect_features=False)


def _post_options(
    feature: Feature, step: OperationDraft, source: SceneObject, budget: RebuildBudget
) -> list[tuple[OperationDraft, Feature | None]]:
    """Ein sichtbarer Zapfen kann durch eine belegte Hohlkehle verkürzt sein."""
    from app.core.perceive.features import EPS_ANGLE

    options: list[tuple[OperationDraft, Feature | None]] = [(step, None)]
    if feature.kind != "pin":
        return options
    centre = np.asarray(feature.params["centre"], dtype=float)
    axis = np.asarray(feature.params["axis"], dtype=float)
    radius = float(feature.params["diameter"]) / 2.0
    depth = float(feature.params["depth"])
    for throat in source.features.values():
        if throat.kind != "torus" or not throat.params.get("recess", False):
            continue
        round_radius = float(throat.params["tube_diameter"]) / 2.0
        round_centre = np.asarray(throat.params["centre"], dtype=float)
        delta = centre - round_centre
        if (
            abs(dot3(axis, throat.params["axis"])) < exact_cos_degrees(EPS_ANGLE)
            or math.hypot(*(delta - axis * dot3(delta, axis))) > budget.local_mm
            or abs(float(throat.params["diameter"]) / 2.0 - round_radius - radius) > budget.local_mm
        ):
            continue
        for plane in source.features.values():
            if plane.kind != "face":
                continue
            normal = np.asarray(plane.params["normal"], dtype=float)
            origin = np.asarray(plane.params["centre"], dtype=float)
            distance = dot3(centre - origin, normal)
            extension = distance - depth / 2.0
            if (
                abs(dot3(axis, normal)) < exact_cos_degrees(EPS_ANGLE)
                or abs(dot3(round_centre - origin, normal) - round_radius) > budget.local_mm
                or extension <= EPS_GEOM
                or abs(extension - round_radius) > budget.local_mm
            ):
                continue
            options.append(
                (
                    replace(
                        step,
                        params={
                            **step.params,
                            "height": depth + extension,
                            **_position(centre - normal * distance, normal),
                        },
                    ),
                    throat,
                )
            )
    return options


def _composed(
    source: SceneObject,
    document: Document,
    profile: Profile,
    budget: RebuildBudget,
    cancelled: CancelToken,
) -> list[tuple[list[OperationDraft], set[str], SceneObject]]:
    """Ein Grundvolumen mit aufgesetzten Rundkörpern als weiterer Kandidat.

    Ein Zapfen ist weder automatisch der ganze Körper noch automatisch ein
    Auftrag. Beide Rollen erhalten eine echte Konstruktion und müssen die
    vollständige Formprüfung bestehen.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle

    from app.core.brep.edit import edge_key, edges_of
    from app.core.brep.kernel import Solid
    from app.core.perceive.features import EPS_ANGLE

    additions = [
        (feature, step)
        for feature in source.features.values()
        if (step := _single(feature)) is not None
    ]
    if not additions:
        return []
    basis = _oriented_basis(source)
    base = _supported_box(source, np.eye(3) if basis is None else basis)
    if base is None:
        return []
    drafts, explained = _boxed(source, budget.local_mm, basis)
    drafts[0] = base
    pending = [(drafts, explained, source)]
    for feature, step in additions:
        growing = []
        for option, throat in _post_options(feature, step, source, budget):
            for steps, known, form in pending:
                cancelled.raise_if_cancelled()
                joined = [
                    *steps,
                    replace(option, outputs=("obj_2",)),
                    OperationDraft("union_objects", ("obj_1", "obj_2"), outputs=("obj_1",)),
                ]
                if throat is None:
                    growing.append((joined, known | {feature.id}, form))
                    continue
                result = _built(joined, document, profile, cancelled)
                if not result.complete or "obj_1" not in result.scene.objects:
                    continue
                body = result.scene.objects["obj_1"].mesh
                if not isinstance(body, Solid):
                    continue
                foot = tuple(option.params[name] for name in ("x", "y", "z"))
                normal = tuple(option.params[name] for name in ("nx", "ny", "nz"))
                radius = float(feature.params["diameter"]) / 2.0
                for edge in edges_of(body):
                    curve = BRepAdaptor_Curve(edge.edge)
                    if curve.GetType() != GeomAbs_Circle:
                        continue
                    circle = curve.Circle()
                    if (
                        math.dist(circle.Location().Coord(), foot) <= budget.local_mm
                        and abs(circle.Radius() - radius) <= budget.local_mm
                        and abs(dot3(circle.Axis().Direction().Coord(), normal))
                        >= exact_cos_degrees(EPS_ANGLE)
                        and abs(edge.length - math.tau * radius) <= math.tau * budget.local_mm
                    ):
                        growing.append(
                            (
                                [
                                    *joined,
                                    OperationDraft(
                                        "fillet_edges",
                                        ("obj_1",),
                                        {
                                            "radius": float(throat.params["tube_diameter"]) / 2.0,
                                            "edges": "named",
                                            "edge_keys": edge_key(edge),
                                        },
                                    ),
                                ],
                                known | {feature.id, throat.id},
                                form,
                            )
                        )
        pending = growing
    return pending


def _rounded(
    source: SceneObject,
    document: Document,
    profile: Profile,
    budget: RebuildBudget,
    cancelled: CancelToken,
) -> list[tuple[list[OperationDraft], set[str], SceneObject]]:
    """Belegte Kanten gemeinsam runden und ihre kugeligen Übergänge nachweisen."""
    from app.core.brep.edit import edge_key, edges_of
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.perceive.features import EPS_ANGLE

    fillets = [
        feature
        for feature in source.features.values()
        if feature.kind == "fillet" and not feature.params.get("recess", False)
    ]
    straight = [feature for feature in fillets if "axis" in feature.params]
    if not straight:
        return []
    basis = _oriented_basis(source)
    base = _supported_box(source, np.eye(3) if basis is None else basis)
    if base is None:
        return []
    drafts, explained = _boxed(source, budget.local_mm, basis)
    drafts[0] = base
    pending = [(drafts, explained, source)]
    groups: list[list[Feature]] = []
    for feature in straight:
        group = next(
            (
                group
                for group in groups
                if abs(float(group[0].params["diameter"]) - float(feature.params["diameter"]))
                <= EPS_GEOM
            ),
            None,
        )
        if group is None:
            groups.append([feature])
        else:
            group.append(feature)
    for group in groups:
        cancelled.raise_if_cancelled()
        radius = float(group[0].params["diameter"]) / 2.0
        growing = []
        for steps, known, form in pending:
            result = _built(steps, document, profile, cancelled)
            if not result.complete or "obj_1" not in result.scene.objects:
                continue
            body = result.scene.objects["obj_1"].mesh
            if not isinstance(body, Solid):
                continue
            choices = []
            edges = edges_of(body)
            for feature in group:
                axis = np.asarray(feature.params["axis"], dtype=float)
                centre = np.asarray(feature.params["centre"], dtype=float)
                length = float(feature.params["length"])
                matching = []
                for edge in edges:
                    delta = centre - np.asarray(edge.middle)
                    axial = dot3(delta, axis)
                    # Eckrundungen kürzen den sichtbaren Zylindermantel. Sein
                    # Abschnitt muss auf der längeren Grundkante liegen;
                    # quer bleibt der geometrische Abstand sqrt(2) * Radius.
                    if (
                        abs(dot3(edge.direction, axis)) >= exact_cos_degrees(EPS_ANGLE)
                        and abs(axial) + length / 2.0 <= edge.length / 2.0 + budget.local_mm
                        and abs(math.hypot(*(delta - axis * axial)) - math.sqrt(2.0) * radius)
                        <= budget.local_mm
                    ):
                        matching.append(edge_key(edge))
                choices.append(matching)
            # Gleich passende Kanten bleiben getrennte Kandidaten. Zusammen
            # anschließende Rundungen desselben Radius werden in einer Op
            # gebaut, damit der Kern die kugeligen Ecken gemeinsam erzeugt.
            seen = set()
            for combination in product(*choices):
                cancelled.raise_if_cancelled()
                keys = tuple(sorted(set(combination)))
                if len(keys) != len(group) or keys in seen:
                    continue
                seen.add(keys)
                growing.append(
                    (
                        [
                            *steps,
                            OperationDraft(
                                "fillet_edges",
                                ("obj_1",),
                                {"radius": radius, "edges": "named", "edge_keys": " ".join(keys)},
                            ),
                        ],
                        known | {feature.id for feature in group},
                        form,
                    )
                )
        pending = growing
    corners = [feature for feature in fillets if "axis" not in feature.params]
    if corners:
        for steps, known, _form in pending:
            result = _built(steps, document, profile, cancelled)
            if not result.complete or "obj_1" not in result.scene.objects:
                continue
            body = result.scene.objects["obj_1"].mesh
            if not isinstance(body, Solid):
                continue
            actual = [
                feature
                for feature in features_of(body, cancelled=cancelled).values()
                if feature.kind == "fillet"
                and "axis" not in feature.params
                and not feature.params.get("recess", False)
            ]
            for corner in corners:
                matches = [
                    feature
                    for feature in actual
                    if math.dist(feature.params["centre"], corner.params["centre"])
                    <= budget.local_mm
                    and abs(float(feature.params["diameter"]) - float(corner.params["diameter"]))
                    <= EPS_GEOM
                ]
                if len(matches) == 1:
                    known.add(corner.id)
    return pending


def propose(
    document: Document,
    object_id: str,
    profile: Profile,
    *,
    sources: SourceAccess,
    budget: RebuildBudget,
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
) -> RebuildProposal:
    """Erzeugt und prüft Kandidaten, ohne den ursprünglichen Verlauf zu ändern."""
    token = cancelled or NeverCancelled()
    token.raise_if_cancelled()
    document = deepcopy(document)
    document_mark = document_to_data(document)
    if progress is not None:
        progress(0.0, str(_("Modell nachbauen")))
    original = evaluate(document, profile, sources=sources, cancelled=token)
    if not original.complete or object_id not in original.scene.objects:
        raise UserError(
            _("Der Nachbau braucht ein vollständig berechnetes Modell."),
            _("Beheben Sie zuerst den angehaltenen Schritt und starten Sie den Nachbau erneut."),
            suggestions=(CANCEL,),
        )
    source = original.scene.objects[object_id]
    mesh = as_mesh_data(source.mesh)
    if not mesh.is_watertight or not mesh.raw.is_winding_consistent:
        raise UserError(
            _("Der Nachbau braucht ein geschlossenes Modell mit eindeutiger Innenseite."),
            _("Reparieren Sie das Modell und starten Sie den Nachbau erneut."),
            suggestions=(CANCEL,),
        )
    from app.core.brep import from_mesh
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.geom.repair import self_intersection_check

    crossed, complete = self_intersection_check(mesh, token)
    if crossed or not complete:
        raise UserError(
            _("Die Ausgangsform ist noch nicht vollständig als überschneidungsfrei geprüft."),
            _("Reparieren Sie das Modell und starten Sie den Nachbau erneut."),
            suggestions=(CANCEL,),
        )
    if progress is not None:
        progress(0.1, str(_("Modell nachbauen")))
    # P4.0 liefert die begrenzten analytischen Flächen als Kandidatenquelle.
    # Die unabhängige Abnahme unten vergleicht weiterhin mit dem Originalnetz.
    if isinstance(source.mesh, Solid):
        recovered = source.mesh
    else:
        try:
            recovered = from_mesh.convert(
                mesh,
                source.features,
                tolerance=from_mesh.DEFAULT_TOLERANCE,
                cancelled=token,
            ).solid
        except from_mesh.ConversionRefusedError as error:
            raise UserError(
                _("Aus den erkannten Flächen ließ sich kein geschlossener Körper bauen."),
                _("Reparieren Sie das Modell und starten Sie den Nachbau erneut."),
                suggestions=(CANCEL,),
            ) from error
    recovered_source = replace(
        source, mesh=recovered, features=features_of(recovered, cancelled=token)
    )
    forms = [recovered_source]
    original_kinds = Counter(
        feature.kind for feature in source.features.values() if feature.kind != "face"
    )
    recovered_kinds = Counter(
        feature.kind for feature in recovered_source.features.values() if feature.kind != "face"
    )
    if original_kinds - recovered_kinds:
        # P4.0 kann einen erkannten Träger wegen seiner Randkurve als Facetten
        # behalten. Der ursprüngliche Fit bleibt ein weiterer Kandidat; nur
        # die unabhängige vollständige Formprüfung darf ihn freigeben.
        forms.append(source)
    plans: list[tuple[list[OperationDraft], set[str], SceneObject]] = []
    for form in forms:
        # Ein Rundteil allein ist nur ein Vorschlag, wenn es das ganze Teil
        # ist. Neben weiteren Merkmalen fällt es an der Formprüfung immer
        # durch und kostet eine Auswertung: Am Besenhalter aus Roberts Test
        # (0.5.2) standen zwölf einzelne Zylinder für sechs Zapfen in der Liste.
        rounds = [feature for feature in form.features.values() if feature.kind != "face"]
        if len(rounds) == 1 and (step := _single(rounds[0])) is not None:
            plans.append(([step], {rounds[0].id}, form))
        drafts, explained = _boxed(form, budget.local_mm)
        plans.append((drafts, explained, form))
        basis = _oriented_basis(form)
        if basis is not None:
            drafts, explained = _boxed(form, budget.local_mm, basis)
            plans.append((drafts, explained, form))
    candidates: list[RebuildCandidate] = []
    failures: list[Finding] = []

    def assess(drafts: list[OperationDraft], explained: set[str], form: SceneObject) -> None:
        token.raise_if_cancelled()
        result = _built(drafts, document, profile, token)
        if not result.complete or "obj_1" not in result.scene.objects:
            failures.extend(
                finding for finding in result.scene.report.findings if finding.severity == "error"
            )
            return
        body = result.scene.objects["obj_1"]
        check = check_shape(mesh, body, budget, cancelled=token)
        # Erklärt sein muss, was die Formprüfung besteht. Ein Kandidat, der an
        # ihr scheitert, behält ihren Grund; seine Merkmale zu erkennen kostete
        # am Winkel mit Querbohrungen sechs Sekunden für nichts.
        if check.accepted:
            relevant = {feature.id for feature in form.features.values() if feature.kind != "face"}
            unexplained = tuple(
                sorted(
                    (relevant - explained)
                    | _unexplained_planes(form, body, token, boundary_mm=budget.local_mm)
                )
            )
            if unexplained:
                check = RebuildCheck(
                    False, "unexplained", check.volume_relative, check.surface, unexplained
                )
        candidates.append(RebuildCandidate(tuple(drafts), body, check))

    for index, (drafts, explained, form) in enumerate(plans):
        if progress is not None:
            progress(0.2 + 0.4 * index / len(plans), str(REGISTRY.get(drafts[0].op).title))
        assess(drafts, explained, form)
    if not any(candidate.check.accepted for candidate in candidates):
        if not isinstance(source.mesh, Solid) and not any(form is source for form in forms):
            forms.append(source)
        plans = [
            plan for form in forms for plan in _composed(form, document, profile, budget, token)
        ]
        plans.extend(
            plan for form in forms for plan in _rounded(form, document, profile, budget, token)
        )
        plans.extend(_layered(recovered_source, budget.local_mm, token))
        for index, (drafts, explained, form) in enumerate(plans):
            if progress is not None:
                progress(0.6 + 0.4 * index / len(plans), str(REGISTRY.get(drafts[0].op).title))
            assess(drafts, explained, form)
            if candidates and candidates[-1].check.accepted:
                break
    if progress is not None:
        progress(1.0, str(_("Modell nachbauen")))
    token.raise_if_cancelled()
    return RebuildProposal(source, budget, tuple(candidates), document_mark, tuple(failures))


@dataclass(frozen=True, slots=True)
class RebuildApplication:
    """Vollständig ausgewertete Übernahme samt sichtbaren Attributverlusten."""

    proposal: RebuildProposal
    drafts: tuple[OperationDraft, ...]
    changes: DocumentChange
    result: SceneObject
    losses: tuple[TranslatableText, ...]
    checked_document: dict[str, Any]


def _require_current(document: Document, proposal: RebuildProposal) -> None:
    if document_to_data(document) != proposal.document_mark:
        raise UserError(
            _("Das Modell hat sich seit der Nachbauprüfung geändert."),
            _("Starten Sie den Nachbau erneut, damit der Vergleich zum aktuellen Modell gehört."),
            suggestions=(CANCEL,),
        )


def prepare_application(
    document: Document,
    proposal: RebuildProposal,
    candidate: RebuildCandidate,
    profile: Profile,
    *,
    sources: SourceAccess,
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
) -> RebuildApplication:
    """Plant die eine Transaktion, einschließlich benannter Maße und Attributfolgen.

    Der neue Körper bekommt eine neue Kennung. Alte Merkmalsnamen werden
    dadurch nie auf eine ähnlich benannte neue Fläche umgebogen. Quellen und
    geschützte Merkmale am ursprünglichen Körper bleiben für Undo erhalten.
    Nicht übertragbare Bezüge werden vor der Übernahme ausdrücklich genannt.
    """
    from app.core.brep.step import hex_colour

    _require_current(document, proposal)
    if candidate.drafts != candidate._checked_drafts:
        raise UserError(
            _("Die Nachbaufolge wurde nach ihrer Prüfung verändert."),
            _("Starten Sie den Nachbau erneut, damit der Vergleich zum aktuellen Modell gehört."),
            suggestions=(CANCEL,),
        )
    if not any(candidate is item for item in proposal.accepted):
        raise UserError(
            _("Dieser Nachbau hat die Formprüfung nicht bestanden."),
            _("Behalten Sie das ursprüngliche Modell oder prüfen Sie einen anderen Nachbau."),
            suggestions=(CANCEL,),
        )
    token = cancelled or NeverCancelled()
    token.raise_if_cancelled()
    if progress is not None:
        progress(0.0, str(_("Modell nachbauen")))
    source = proposal.source
    first = History(document).next_object_id()
    start = int(first.removeprefix("obj_"))
    object_map = {"obj_1": first}
    drafts: list[OperationDraft] = []
    parameters: dict[str, Parameter] = {}
    for index, draft in enumerate(candidate.drafts, 1):
        token.raise_if_cancelled()
        for identifier in draft.outputs or ():
            if identifier not in object_map:
                object_map[identifier] = f"obj_{start + len(object_map)}"
        specs = {entry.name: entry for entry in REGISTRY.get(draft.op).params.spec()}
        values = dict(draft.params)
        for key, value in tuple(values.items()):
            spec = specs[key]
            if spec.unit != "mm" or isinstance(value, bool) or not isinstance(value, int | float):
                continue
            name = f"rebuild_{first}_{index}_{key}"
            while name in document.parameters or name in parameters:
                name += "_new"
            parameters[name] = Parameter(
                name,
                float(value),
                title=spec.title,
                minimum=spec.minimum,
                maximum=spec.maximum,
            )
            values[key] = f"=@{name}"
        drafts.append(
            OperationDraft(
                draft.op,
                tuple(object_map[item] for item in draft.inputs),
                values,
                tuple(object_map[item] for item in draft.outputs) if draft.outputs else None,
            )
        )
    drafts.append(OperationDraft("rename_object", (first,), {"name": str(source.name)}))
    if source.material is not None:
        drafts.append(OperationDraft("set_material", (first,), {"material": source.material}))
    if source.plate:
        drafts.append(
            OperationDraft(
                "translate_object", (first,), {"plate": source.plate + 1, "keep_on_bed": False}
            )
        )
    losses: list[TranslatableText] = []
    used = set(source.mesh.slot_indices)
    if len(used) == 1:
        slot = next((slot for slot in source.material_slots if slot.index in used), None)
        if slot is not None:
            colours = (() if slot.colour is None else (slot.colour,)) + slot.extra_colours
            drafts.append(
                OperationDraft(
                    "assign_slot",
                    (first,),
                    {
                        "slot": slot.index,
                        "name": str(slot.name),
                        "colour": " ".join(hex_colour(*colour) for colour in colours),
                        "material_type": slot.material_type or "",
                        "slicer_profile": slot.material or "",
                    },
                )
            )
    elif used:
        losses.append(
            _("Die Filamentzuweisung einzelner Flächen wird nicht auf den Nachbau übertragen.")
        )
    if document.protected.get(source.id):
        losses.append(_("Geschützte Sichtflächen müssen am Nachbau erneut gewählt werden."))
    fits = tuple(
        fit for fit in document.fits if source.id not in (fit.a.object_id, fit.b.object_id)
    )
    if len(fits) != len(document.fits):
        losses.append(
            _("Passungen zum ursprünglichen Modell werden entfernt und müssen neu angelegt werden.")
        )
    visual = as_mesh_data(source.mesh).raw.visual
    if (visual is not None and visual.kind == "texture") or any(
        feature.params.get("texture") for feature in source.features.values()
    ):
        losses.append(_("Oberflächentexturen werden nicht auf den Nachbau übertragen."))
    drafts.append(OperationDraft("delete_object", (source.id,)))
    changes = change_for(
        document, parameters=parameters, fits=fits if len(fits) != len(document.fits) else None
    )
    trial = deepcopy(document)
    History(trial).apply(_("Modell nachbauen"), drafts, changes=changes)

    def report_progress(value: float, label: str) -> None:
        if progress is not None:
            progress(0.1 + 0.7 * value, label)

    evaluated = evaluate(
        trial,
        profile,
        sources=sources,
        cancelled=token,
        progress=report_progress,
    )
    if not evaluated.complete or first not in evaluated.scene.objects:
        raise UserError(
            _("Die Nachbaufolge lässt sich noch nicht vollständig berechnen."),
            _("Behalten Sie das ursprüngliche Modell und prüfen Sie die vorgeschlagenen Maße."),
            suggestions=(CANCEL,),
        )
    result = evaluated.scene.objects[first]
    if progress is not None:
        progress(0.8, str(_("Modell nachbauen")))
    checked = check_shape(as_mesh_data(source.mesh), result, proposal.budget, cancelled=token)
    if not checked.accepted:
        raise UserError(
            _("Dieser Nachbau hat die Formprüfung nicht bestanden."),
            _("Behalten Sie das ursprüngliche Modell oder prüfen Sie einen anderen Nachbau."),
            suggestions=(CANCEL,),
        )
    if progress is not None:
        progress(1.0, str(_("Modell nachbauen")))
    token.raise_if_cancelled()
    return RebuildApplication(
        proposal, tuple(drafts), changes, result, tuple(losses), document_to_data(trial)
    )


def commit(
    history: History,
    application: RebuildApplication,
    *,
    accept_losses: bool = False,
    sources: SourceAccess | None = None,
) -> Transaction:
    """Übernimmt ausschließlich den vollständig geprüften Stand als einen Schritt."""
    _require_current(history.document, application.proposal)
    # Verknüpfte Dateien können sich auch ohne Änderung des Dokuments ändern.
    # Derselbe Quellenvertrag wie bei der Auswertung prüft ihren Inhalt direkt
    # vor der Übernahme erneut; eingebettete Inhalte gehören zum Dokument.
    linked = {
        value
        for operation in history.document.ops
        if operation.suppressed is None
        for spec in REGISTRY.get(operation.op).params.spec()
        if spec.kind in SOURCE_KINDS
        and isinstance(value := operation.params.get(spec.name), str)
        and value in history.document.sources
        and not history.document.sources[value].embedded
    }
    for identifier in sorted(linked):
        if (
            sources is None
            or sources.identity(identifier) != history.document.sources[identifier].sha256
        ):
            raise UserError(
                _("Das Modell hat sich seit der Nachbauprüfung geändert."),
                _(
                    "Starten Sie den Nachbau erneut, damit der Vergleich "
                    "zum aktuellen Modell gehört."
                ),
                suggestions=(CANCEL,),
            )
    if application.losses and not accept_losses:
        raise UserError(
            _("Prüfen Sie vor dem Übernehmen die Folgen für Filamente und Bezüge."),
            _("Bestätigen Sie die angezeigten Folgen oder behalten Sie das ursprüngliche Modell."),
            suggestions=(CANCEL,),
        )
    trial = deepcopy(history.document)
    History(trial).apply(_("Modell nachbauen"), application.drafts, changes=application.changes)
    if document_to_data(trial) != application.checked_document:
        raise UserError(
            _("Die Nachbaufolge wurde nach ihrer Prüfung verändert."),
            _("Starten Sie den Nachbau erneut, damit der Vergleich zum aktuellen Modell gehört."),
            suggestions=(CANCEL,),
        )
    return history.apply(_("Modell nachbauen"), application.drafts, changes=application.changes)
