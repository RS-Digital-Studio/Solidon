"""Nachbau als neue registrierte Operationsfolge (Bauplan §42, CAD-Konzept §13.5).

Ein Vorschlag rechnet ausschließlich in einem eigenen Dokument. Die Merkmale
liefern Kandidaten; erst ein unabhängiger Vergleich der vollständigen Form
entscheidet, ob ein Kandidat übernommen werden darf.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from itertools import pairwise, product
from typing import Any, Final

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
    Point2,
    Profile,
    ProgressFn,
    SceneObject,
    SketchElement,
    SourceAccess,
    Transaction,
    Vec3,
)
from app.core.units import (
    EPS_GEOM,
    dot3,
    exact_cos_degrees,
    exact_sin,
    exact_sin_degrees,
    plane_axes,
)
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
    offset_mm: float = EPS_GEOM,
) -> set[str]:
    """Eine kleine unbekannte Stufe verschwindet nicht im erlaubten Formbudget.

    Jede begrenzte ebene Teilfläche braucht eine überlappende Fläche in
    derselben gerichteten Ebene. Die Formgrenze erlaubt keine fehlenden
    Taschenböden, auch unterhalb des lokalen Abstandsbudgets. Dieselbe Ebene
    heißt: höchstens ``offset_mm`` daneben. Eine Skizze, die aus dem
    Querschnitt einer STL entsteht, trägt deren einfache Genauigkeit — am
    Wandhalter lagen ihre Ebenen 5,4 µm neben den Flächen des Netzes.
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
            and abs(dot3(np.asarray(plane.params["centre"]) - centre, normal)) <= offset_mm
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
        if np.any(overlap <= EPS_GEOM * EPS_GEOM) or _uncovered(
            source_area, target_area, boundary_mm, offset_mm
        ):
            unexplained.add(feature.id)
    return unexplained


def _uncovered(source_area: Any, target_area: Any, boundary_mm: float, offset_mm: float) -> bool:
    """Ob von einer Quellfläche mehr fehlt als eine Nadel der Dreiecksteilung.

    Am Besenhalter blieb von einem Boden mit 45,8 mm² eine Nadel von
    2,65·10⁻⁶ mm² ungedeckt — 0,02 mm lang, schmaler als die Genauigkeit,
    mit der zwei Ebenen dieselbe heißen. Ein Rest zählt, sobald er im Mittel
    mindestens ``offset_mm`` breit ist; ein fehlender schmaler Taschenboden
    bleibt damit ein Befund.
    """
    import shapely

    missing = shapely.difference(source_area, target_area.buffer(boundary_mm))
    return any(
        2.0 * float(part.area) / float(part.length) >= offset_mm for part in _areas_of(missing)
    )


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
    """Die vertieften Kegel auf der Achse einer Bohrung — Kandidaten ihrer Senkung.

    Gleichgerichtet heißt innerhalb des Winkels, in dem die Erkennung
    Richtungen gleich nennt (``EPS_ANGLE``): Beide Achsen sind eingepasst, und
    an einer STL aus dem exakten Kern standen Bohrung und Senkung um mehr als
    ``EPS_GEOM`` schief zueinander — die Senkung blieb ohne Bohrung.
    """
    from app.core.perceive.features import EPS_ANGLE

    params = feature.params
    axis = np.array(params["axis"], dtype=float, copy=True)
    axis /= math.sqrt(dot3(axis, axis))
    centre = np.asarray(params["centre"], dtype=float)
    parallel = exact_cos_degrees(EPS_ANGLE)
    cones = []
    for cone in features:
        if cone.kind != "cone" or not cone.params.get("recess", False):
            continue
        cone_axis = np.array(cone.params["axis"], dtype=float, copy=True)
        cone_axis /= math.sqrt(dot3(cone_axis, cone_axis))
        displacement = np.asarray(cone.params["centre"], dtype=float) - centre
        if (
            abs(dot3(cone_axis, axis)) >= parallel
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


#: Wie viele Achsen der Profilkörper versucht, die prismatischste zuerst.
PROFILE_AXES: Final = 2

#: Welcher Anteil der Oberfläche längs oder quer zu einer Achse stehen muss,
#: damit sie die Achse eines Profilkörpers sein kann.
PRISMATIC_SHARE: Final = 0.5


#: Wie weit Querschnittsfläche mal Länge vom Volumen eines Stücks abweichen
#: darf, das als Prisma gilt (Anteil). Größere Abweichungen fängt die
#: unabhängige Formprüfung ohnehin; diese Schranke spart nur aussichtslose
#: Auswertungen.
PRISM_SLACK: Final = 0.02


def _prismatic(
    source: SceneObject, mesh: MeshData, budget: RebuildBudget, cancelled: CancelToken
) -> list[tuple[list[OperationDraft], set[str], SceneObject]]:
    """Ein Profilkörper längs einer Achse, dazu die Prismen, die ihm fehlen oder zu viel sind.

    Für Teile, deren Seiten nicht alle längs einer Richtung laufen: Am
    Besenhalter aus Roberts Test (0.5.2) stehen 82 Rundungen und alle Wände
    längs der Plattenachse, quer dazu aber Fasen, Rundungen und gesenkte
    Schraubenlöcher. Geschnitten wird das Netz selbst, nicht der P4.0-Körper:
    Dessen Flächen schließen nur innerhalb ihrer Toleranzen aneinander, und an
    20 Teilen des Korpus entsteht er gar nicht.

    Je Achse (:func:`_prism_axes`) und Höhe wird der Querschnitt über die
    ganze Länge gezogen; die Höhe mit dem kleinsten Unterschied zum Körper
    gewinnt. Der Unterschied zerfällt in Stücke, die abgezogen oder
    aufgesetzt werden — jedes ein Prisma längs einer Richtung des Teils
    (:func:`_prism_piece`) —, und was kein Prisma ist, aber in einer
    erkannten Bohrung samt Senkung liegt, wird gebohrt, ohne Kompensation
    (CAD-Konzept §13.5). Bleibt ein Stück ohne Erklärung, gibt es an dieser
    Höhe keinen Vorschlag. Querschnitte werden Skizzen aus Strecken, Bögen
    und Kreisen (:func:`app.core.sketch.traced.traced_loop`); ob der Aufbau
    dieselbe Form ergibt, entscheidet wie immer die unabhängige Formprüfung.
    """
    features = tuple(source.features.values())
    plans: list[tuple[list[OperationDraft], set[str], SceneObject]] = []
    for axis in _prism_axes(mesh, features)[:PROFILE_AXES]:
        cancelled.raise_if_cancelled()
        drafts = _profile_plan(mesh, features, axis, budget, cancelled)
        if drafts:
            plans.append(
                (drafts, {feature.id for feature in features if feature.kind != "face"}, source)
            )
    return plans


def _prism_axes(mesh: MeshData, features: tuple[Feature, ...]) -> list[np.ndarray]:
    """Richtungen, längs derer der Körper am ehesten ein Prisma ist — beste zuerst.

    Gezählt wird die Oberfläche, die längs der Richtung (Wände) oder quer zu
    ihr (Deckel) steht. Kandidaten sind die Weltachsen und die Normalen und
    Achsen der erkannten Merkmale; gleich gute behalten diese Folge.
    """
    from app.core.perceive.features import EPS_ANGLE

    normals = np.asarray(mesh.raw.face_normals, dtype=np.float64)
    areas = np.asarray(mesh.raw.area_faces, dtype=np.float64)
    total = float(areas.sum())
    if total <= EPS_GEOM:
        return []
    parallel = exact_cos_degrees(EPS_ANGLE)
    across = exact_sin(math.radians(EPS_ANGLE))
    candidates = [np.eye(3)[index] for index in range(3)]
    for feature in features:
        vector = feature.params.get("normal" if feature.kind == "face" else "axis")
        if vector is None:
            continue
        axis = np.array(vector, dtype=float, copy=True)
        length = math.sqrt(dot3(axis, axis))
        if length > EPS_GEOM:
            candidates.append(axis / length)
    distinct: list[np.ndarray] = []
    for axis in candidates:
        if not any(abs(dot3(axis, known)) >= parallel for known in distinct):
            distinct.append(axis)
    scored = []
    for axis in distinct:
        facing = np.abs(along(normals, axis))
        share = float(areas[(facing >= parallel) | (facing <= across)].sum()) / total
        if share >= PRISMATIC_SHARE:
            scored.append((share, axis))
    scored.sort(key=lambda entry: -entry[0])
    return [axis for _share, axis in scored]


def _profile_plan(
    mesh: MeshData,
    features: tuple[Feature, ...],
    axis: np.ndarray,
    budget: RebuildBudget,
    cancelled: CancelToken,
) -> list[OperationDraft]:
    """Die Schritte eines Profilkörpers längs ``axis`` — oder keine.

    Zwischen zwei Deckelhöhen ist der Querschnitt eines Prismas überall
    gleich (:func:`_layers`). Ändert er sich innerhalb der Schicht — eine
    Fase, eine Senkung, eine Querrundung —, trägt die Schicht die Vereinigung
    ihrer Querschnitte, und nur dort zerfällt der Überschuss in Stücke
    (:func:`_pieces_as_steps`).

    **Gebaut wird abziehend**: ein Körper aus dem Umriss aller Schichten
    über die ganze Länge, dann je Schicht die Luft daneben. Gestapelte
    Schichten zu vereinigen ging am Besenhalter schief: Zwei Schichten mit
    fast, aber nicht genau gleichen Wänden ließ OpenCASCADE als getrennte
    Körper stehen, und das Netz war nicht mehr dicht. Die Luft einer Schicht
    verliert ihre Splitter (:func:`_opened`) und reicht, wo sie an den Rand
    stößt, über ihn hinaus; so liegt kein Werkzeug auf einer Wand des Umrisses.
    """
    origin = np.asarray(mesh.bounds.centre, dtype=np.float64)
    depth = along(np.asarray(mesh.raw.vertices, dtype=np.float64) - origin, axis)
    low, high = float(depth.min()), float(depth.max())
    height = high - low
    if height <= budget.local_mm:
        return []
    foot = origin + axis * low
    x_axis, y_axis = _frame_axes(axis, foot)
    local = _in_frame(mesh, foot, x_axis, y_axis, axis)
    # Querbohrungen und Senkungen stehen in keinem Querschnitt: Eine Schicht
    # durch sie bekäme eine Kerbe, die später ein Prisma ausschneidet und die
    # Bohrung dann zum zweiten Mal — beide Flächen lagen fast aufeinander.
    # Im Querschnitt sind sie deshalb gefüllt und werden am Ende gebohrt.
    from app.core.perceive.features import EPS_ANGLE

    drilled: list[Feature] = []
    fills: list[MeshData] = []
    parallel = exact_cos_degrees(EPS_ANGLE)
    for feature in features:
        if feature.kind != "hole":
            continue
        across = abs(dot3(np.asarray(feature.params["axis"], dtype=float), axis)) < parallel
        if not across and len(_sinks_of(feature, features, budget.local_mm)) != 1:
            continue
        tool = _drill_tool(feature, features, budget, beyond=False)
        if tool is None:
            continue
        drilled.append(feature)
        fills.append(_in_frame(tool, foot, x_axis, y_axis, axis))
    layers = _layers(local, height, budget, cancelled, fills=fills)
    if not layers:
        return []
    import shapely

    outline = shapely.union_all([section for _lower, _upper, section, _varying in layers])
    # Taschen quer zur Achse ebenso: gefüllt in den Schichten, am Ende in
    # einem Zug abgezogen (:func:`_cross_pockets`).
    frame = (foot, x_axis, y_axis, axis)
    pockets, pocket_cuts = _cross_pockets(
        local, outline, height, frame, fills, mesh, features, budget, cancelled
    )
    if pockets:
        fills = [*fills, *pockets]
        layers = _layers(local, height, budget, cancelled, fills=fills)
        if not layers:
            return []
        outline = shapely.union_all([section for _lower, _upper, section, _varying in layers])
    beyond = budget.local_mm * 10.0
    around = outline.buffer(beyond, join_style="mitre")
    # Nur die Luft im Umriss: Wo die Schicht dieselbe Wand hat wie der
    # Umriss, schneidet nichts.
    airs = [
        _opened(shapely.difference(outline, section), budget)
        for _lower, _upper, section, _varying in layers
    ]
    base = _extrusion(foot, x_axis, y_axis, height, _traced(outline, budget), "obj_1")
    if base is None:
        return []
    steps: list[OperationDraft] = [base]
    for first, last, column in _columns(airs, budget):
        # Wo die Säule an den Rand reicht, steht das Werkzeug über ihn hinaus,
        # in keiner ihrer Schichten aber in deren Material.
        reach = column.buffer(budget.local_mm)
        for index in range(first, last + 1):
            reach = shapely.intersection(reach, shapely.difference(around, layers[index][2]))
        elements = _traced(reach, budget)
        lower, upper = layers[first][0], layers[last][1]
        # Am Boden und an der Decke reicht die Luft über den Körper hinaus,
        # sonst lägen ihre Deckel genau auf seinen.
        bottom = lower - beyond if first == 0 else lower
        top = upper + beyond if last == len(layers) - 1 else upper
        step = _extrusion(foot + axis * bottom, x_axis, y_axis, top - bottom, elements, "obj_2")
        if step is None:
            return []
        steps.extend(
            (step, OperationDraft("subtract_objects", ("obj_1", "obj_2"), outputs=("obj_1",)))
        )
    for lower, upper, section, changing in layers:
        if changing is None:
            continue
        cancelled.raise_if_cancelled()
        # Zuerst der Überschuss über den ganzen Querschnitt. Hängen seine
        # Stücke über Splitter ohne Dicke zusammen — am Wandhalter die vier
        # Fasenkeile über die Wände von Bohrung und Ring —, ist das Ganze kein
        # Prisma. Dann rückt der Querschnitt an den Wänden, die sich in der
        # Schicht nicht ändern, um ein Viertel der Formgrenze ein: Dort
        # entstehen die Splitter, und dort ist nichts abzuziehen.
        inset = budget.local_mm / 4.0
        narrowed = shapely.intersection(
            section,
            shapely.union(
                section.buffer(-inset, join_style="mitre"),
                changing.buffer(inset, join_style="mitre"),
            ),
        )
        for region in (section, narrowed):
            attempt = list(drilled)
            excess = _excess(region, lower, upper, local, fills, cancelled)
            cuts = (
                None
                if excess is None
                else _pieces_as_steps(
                    *((part, "subtract_objects") for part in excess),
                    source=mesh,
                    frame=frame,
                    features=features,
                    budget=budget,
                    cancelled=cancelled,
                    drilled=attempt,
                )
            )
            if cuts is not None:
                break
        if cuts is None:
            return []
        drilled[:] = attempt
        steps.extend(cuts)
    steps.extend(pocket_cuts)
    steps.extend(_drilled(feature, features, budget.local_mm)[0] for feature in drilled)
    return steps


def _excess(
    region: Any,
    lower: float,
    upper: float,
    local: MeshData,
    fills: Sequence[MeshData],
    cancelled: CancelToken,
) -> list[MeshData] | None:
    """Was das Prisma von ``region`` über ``lower`` bis ``upper`` mehr hat als der Körper.

    Ohne die Füllungen der Bohrungen und Taschen, die später gebohrt und
    abgezogen werden; ``None``, wenn das Netz nicht rechnet. Das Prisma liegt
    ganz in seiner Schicht; was es vom Körper außerhalb nicht berührt,
    ändert die Differenz nicht.
    """
    prisms = _extruded(region, lower, upper)
    if prisms is None:
        return None
    excess: list[MeshData] = []
    for prism in prisms:
        part: MeshData | None = _apart(prism, local, cancelled)
        for fill in fills:
            part = _apart(part, fill, cancelled) if part is not None else None
        if part is None:
            return None
        excess.append(part)
    return excess


def _cross_pockets(
    local: MeshData,
    outline: Any,
    height: float,
    frame: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    fills: Sequence[MeshData],
    source: MeshData,
    features: tuple[Feature, ...],
    budget: RebuildBudget,
    cancelled: CancelToken,
) -> tuple[list[MeshData], list[OperationDraft]]:
    """Luft im Umriss, die ein Prisma quer zur Achse ist: als Füllung und als Abzug.

    Die Schrift auf der Rückseite des Besenhalters ist 0,68 mm tief und
    steht längs der Plattenachse in Dutzenden Schichten, mal als Säule, mal
    als Reststück. Wo zwei Werkzeuge in einer Schicht aneinanderstießen,
    lagen ihre Böden oder Wände deckungsgleich, und der exakte Kern ließ eine
    offene Naht stehen. Quer zur Achse ist jeder Buchstabe ein Prisma — ein
    Werkzeug, das ganz im Material beginnt. Zurück kommen die Taschen in
    Zeichenkoordinaten (sie füllen die Querschnitte wie eine Querbohrung) und
    ihre Abzüge. **Auch ein Strich, der längs der Achse ein Prisma ist**: Die
    Säulen teilten ihn über drei Schichten in zwei Werkzeuge mit
    deckungsgleichem Boden, und der zweite Abzug blieb ohne Wirkung.

    **Gesucht wird im eingerückten Umriss**: Wo der Umriss auf einer Wand des
    Körpers liegt, hinterlässt die Differenz Splitter ohne Dicke, und über sie
    hing jede Tasche an der übrigen Luft. Die Füllung reicht danach längs der
    Tasche bis an den Umriss.
    """
    from app.core.errors import GeometryError
    from app.core.geom.boolean import boolean
    from app.core.perceive.features import EPS_ANGLE

    inset = budget.local_mm / 4.0
    searched = _extruded(outline.buffer(-inset, join_style="mitre"), inset, height - inset)
    bounds = _extruded(outline, 0.0, height)
    if searched is None or bounds is None:
        return [], []
    foot, x_axis, y_axis, axis = frame
    parallel = exact_cos_degrees(EPS_ANGLE)
    sideways = [
        direction
        for direction in _directions(frame, features)
        if abs(dot3(direction, axis)) < parallel
    ]
    pockets: list[MeshData] = []
    cuts: list[OperationDraft] = []
    for prism in searched:
        air: MeshData | None = _apart(prism, local, cancelled)
        for fill in fills:
            air = _apart(air, fill, cancelled) if air is not None else None
        if air is None:
            continue
        for piece in _pieces(air, cancelled):
            cancelled.raise_if_cancelled()
            if not _substantial(piece, budget):
                continue
            world = _in_world(piece, frame)
            for direction in sideways:
                found = _as_prism(world, direction, budget, cancelled)
                if found is None or not _walled(found, direction, source, budget, cancelled):
                    continue
                step = _prism_step(found, direction, source, budget, cancelled)
                along_pocket = _extruded(found[4], -budget.local_mm, found[3] + budget.local_mm)
                if step is None or along_pocket is None:
                    continue
                prism_frame = (found[0], found[1], found[2], direction)
                filled = [
                    _in_frame(
                        MeshData.of(_in_world(part.raw, prism_frame)), foot, x_axis, y_axis, axis
                    )
                    for part in along_pocket
                ]
                try:
                    clipped = [
                        boolean(
                            "intersection", [part, limit], allow_empty=True, cancelled=cancelled
                        ).mesh
                        for part in filled
                        for limit in bounds
                    ]
                except GeometryError:
                    continue
                pockets.extend(part for part in clipped if len(part.raw.faces))
                cuts.extend(
                    (
                        step,
                        OperationDraft("subtract_objects", ("obj_1", "obj_2"), outputs=("obj_1",)),
                    )
                )
                break
    return pockets, cuts


def _walled(
    found: tuple[np.ndarray, np.ndarray, np.ndarray, float, Any],
    direction: np.ndarray,
    source: MeshData,
    budget: RebuildBudget,
    cancelled: CancelToken,
) -> bool:
    """Ob ringsum Material steht: eine Vertiefung, keine Ecke, die nach außen offen ist.

    Eine gerundete Plattenecke ist quer zur Achse auch ein Prisma, aber zur
    Seite offen; sie bleibt den Schichten, die sie immer schon trugen.
    """
    import shapely

    from app.core.slice.analysis import cross_sections

    foot, x_axis, y_axis, span, section = found
    local = _in_frame(source, foot, x_axis, y_axis, direction)
    (middle,) = cross_sections(local, [span / 2.0], cancelled=cancelled)
    if middle is None or middle.is_empty:
        return False
    rim = shapely.difference(section.buffer(budget.local_mm), section)
    return bool(_opened(shapely.difference(rim, middle), budget).is_empty)


def _directions(
    frame: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray], features: tuple[Feature, ...]
) -> list[np.ndarray]:
    """Wonach ein Stück ein Prisma sein darf: Achsen des Plans und der Merkmale."""
    _foot, x_axis, y_axis, axis = frame
    directions = [axis, x_axis, y_axis]
    for feature in features:
        vector = feature.params.get("normal" if feature.kind == "face" else "axis")
        if vector is not None:
            direction = np.array(vector, dtype=float, copy=True)
            length = math.sqrt(dot3(direction, direction))
            if length > EPS_GEOM:
                directions.append(direction / length)
    return directions


def _vec3(values: np.ndarray) -> Vec3:
    """Drei Zahlen eines Felds als Punkt oder Richtung."""
    return (float(values[0]), float(values[1]), float(values[2]))


def _frame_axes(axis: np.ndarray, foot: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Die Zeichenrichtungen einer Skizze quer zu ``axis`` — dieselben wie ihre Ebene."""
    from app.core.sketch.planes import frame_of

    frame = frame_of(_vec3(axis), _vec3(foot))
    return np.asarray(frame.x_axis, dtype=np.float64), np.asarray(frame.y_axis, dtype=np.float64)


def _in_frame(
    mesh: MeshData, foot: np.ndarray, x_axis: np.ndarray, y_axis: np.ndarray, axis: np.ndarray
) -> MeshData:
    """Das Netz in Zeichenkoordinaten: ``x``/``y`` der Skizze, ``z`` die Länge der Achse."""
    import trimesh

    shifted = np.asarray(mesh.raw.vertices, dtype=np.float64) - foot
    local = np.column_stack((along(shifted, x_axis), along(shifted, y_axis), along(shifted, axis)))
    return MeshData.of(
        trimesh.Trimesh(vertices=local, faces=np.asarray(mesh.raw.faces), process=False)
    )


def _layers(
    local: MeshData,
    height: float,
    budget: RebuildBudget,
    cancelled: CancelToken,
    *,
    fills: Sequence[MeshData] = (),
) -> list[tuple[float, float, Any, Any]]:
    """Die Schichten zwischen den Deckelhöhen: Grenzen, Querschnitt, was sich ändert.

    Das Letzte ist ``None`` für ein Prisma, sonst der Bereich, den nicht
    jeder Querschnitt der Schicht trägt (ohne Splitter).

    Eine Schicht, deren Querschnitt in der Mitte, den Vierteln und nahe den
    Rändern derselbe ist, ist ein Prisma. Sonst trägt sie die Vereinigung
    von siebzehn Querschnitten — so steht der Körper ganz im Profil, und
    was zu viel ist, wird abgezogen. Gleiche Nachbarschichten werden eine.
    Leer, wenn eine Schicht keinen Querschnitt hat.

    **Gleich heißt: kein Stück mit echter Breite dazwischen** (:func:`_same`).
    Eine Grenze über die ganze Fläche des Unterschieds, gemessen am Umfang,
    ließ am Besenhalter die 0,68 mm tiefe Schrift auf der Rückseite in einer
    Nachbarschicht verschwinden: Sie war kleiner als ein Hundertstel mal
    763 mm Umfang.
    """
    import shapely

    from app.core.perceive.features import EPS_ANGLE
    from app.core.slice.analysis import cross_sections

    normals = np.asarray(local.raw.face_normals, dtype=np.float64)
    levels = np.asarray(local.raw.triangles_center, dtype=np.float64)[:, 2]
    capped = np.abs(normals[:, 2]) >= exact_cos_degrees(EPS_ANGLE)
    # Eine Schicht ist mindestens so dick wie die dünnste Extrusion und die
    # Formgrenze; eine dünnere geht in der Schicht darunter auf, die dann
    # die Vereinigung beider Querschnitte trägt. Am Besenhalter lagen zwei
    # Deckel 0,038 mm auseinander, und die Extrusion lehnte die Höhe ab.
    thinnest = max(budget.local_mm, _thinnest_extrusion())
    marks = [0.0]
    for level in np.sort(levels[capped]).tolist():
        if level - marks[-1] >= thinnest and height - level >= thinnest:
            marks.append(float(level))
    marks.append(height)
    layers: list[tuple[float, float, Any, Any]] = []
    for lower, upper in pairwise(marks):
        cancelled.raise_if_cancelled()
        span = upper - lower
        samples = [lower + span * share for share in (0.5, 0.25, 0.75, 0.05, 0.95)]
        sections = [
            _straightened(section)
            for section in _filled(
                cross_sections(local, samples, cancelled=cancelled), fills, samples
            )
            if section is not None and not section.is_empty
        ]
        if len(sections) != len(samples):
            return []
        middle = sections[0]
        varying = not all(_same(middle, other, budget) for other in sections[1:])
        section, changing = middle, None
        if varying:
            heights = [lower + span * (index + 0.5) / 17 for index in range(17)]
            dense = [
                _straightened(entry)
                for entry in _filled(
                    cross_sections(local, heights, cancelled=cancelled), fills, heights
                )
                if entry is not None and not entry.is_empty
            ]
            if len(dense) != len(heights):
                return []
            every = [*dense, *sections]
            section = shapely.union_all(every)
            # Geöffnet, nicht nur nach mittlerer Breite gesiebt: Am Wandhalter
            # hing ein Band von Tausendsteln längs der ganzen Leiste an den
            # Fasen und verband sie zu einem Stück.
            reach = budget.local_mm / 8.0
            changing = shapely.MultiPolygon(
                _areas_of(
                    shapely.difference(section, shapely.intersection_all(every))
                    .buffer(-reach, join_style="mitre")
                    .buffer(reach, join_style="mitre")
                )
            )
        if (
            layers
            and changing is None
            and layers[-1][3] is None
            and _same(layers[-1][2], section, budget)
        ):
            layers[-1] = (layers[-1][0], upper, layers[-1][2], None)
            continue
        layers.append((lower, upper, section, changing))
    return layers


def _columns(airs: list[Any], budget: RebuildBudget) -> list[tuple[int, int, Any]]:
    """Die Luft der Schichten als Säulen: je Säule erste und letzte Schicht und ihre Fläche.

    Eine Wand, die durch mehrere Schichten läuft, entsteht so aus einem
    Werkzeug. Je Schicht ein eigenes ließ dieselbe Wand mehrmals nachzeichnen,
    jedes Mal um Tausendstel anders — am Besenhalter Stufen an den Zapfen,
    die der Kern nicht mehr vernetzte. Von unten nach oben: Eine Säule wächst
    in die nächste Schicht, solange dort ein gemeinsamer Teil bleibt, und
    schrumpft dabei auf ihn; was eine Schicht darüber hinaus an Luft hat, wird
    eine eigene Säule.
    """
    import shapely

    remaining = [_opened(air, budget) for air in airs]
    columns: list[tuple[int, int, Any]] = []
    for first in range(len(remaining)):
        while not remaining[first].is_empty:
            column, last = remaining[first], first
            for later in range(first + 1, len(remaining)):
                common = _opened(shapely.intersection(column, remaining[later]), budget)
                if common.is_empty:
                    break
                column, last = common, later
            columns.append((first, last, column))
            for index in range(first, last + 1):
                remaining[index] = _opened(shapely.difference(remaining[index], column), budget)
    return columns


def _filled(sections: list[Any], fills: Sequence[MeshData], heights: list[float]) -> list[Any]:
    """Die Querschnitte mit den Bohrungen, die später gebohrt werden, als Material."""
    import shapely

    from app.core.slice.analysis import cross_sections

    if not fills:
        return sections
    filled = list(sections)
    for fill in fills:
        for index, extra in enumerate(cross_sections(fill, heights)):
            if extra is not None and not extra.is_empty and filled[index] is not None:
                filled[index] = shapely.union(filled[index], extra)
    return filled


def _straightened(section: Any) -> Any:
    """Der Schnitt ohne die Punkte, die auf der Geraden ihrer Nachbarn liegen.

    Eine Ebene quer durch eine senkrechte Wand trifft ihre senkrechten Kanten
    in jeder Höhe in denselben Punkten, ihre Diagonalen aber je Höhe woanders.
    Ohne diese Punkte trägt dieselbe Wand in jeder Schicht dieselben Ecken,
    und Vereinigung und Differenz zweier Schichten treffen sie genau. Mit
    ihnen standen am Besenhalter zwischen zwei Schichten Stufen von einem
    Zehntausendstel, die der Kern nicht mehr vernetzte, und die Vereinigung
    einer wechselnden Schicht trug 270 000 Ecken. Die Schranke ist die
    Auflösung einer STL in einfacher Genauigkeit an diesem Ort.
    """
    import shapely

    reach = max(abs(value) for value in section.bounds)
    return shapely.simplify(section, 4.0 * float(np.spacing(np.float32(reach))))


def _same(first: Any, second: Any, budget: RebuildBudget) -> bool:
    """Ob zwei Querschnitte dieselbe Form haben: Was sie trennt, sind nur Splitter."""
    return bool(_opened(first.symmetric_difference(second), budget).is_empty)


def _opened(region: Any, budget: RebuildBudget) -> Any:
    """Die Fläche ohne Splitter: Stücke, deren mittlere Breite unter einem
    Viertel der Formgrenze liegt, fallen weg.

    Wo eine Schicht fast dieselbe Wand hat wie der Umriss aller Schichten,
    bleibt zwischen beiden ein Streifen von Hundertsteln. Ein Werkzeug dieser
    Breite träfe die Wand fast deckungsgleich, und genau daran scheitert der
    exakte Kern. Gemessen wird je Stück ``2 · Fläche / Umfang``; ein Versatz
    nach innen und außen hätte dasselbe gesagt, lief an den Schichten des
    Besenhalters aber minutenlang.
    """
    import shapely

    kept = [
        part
        for part in _areas_of(region)
        if 2.0 * float(part.area) / float(part.length) >= budget.local_mm / 4.0
    ]
    return shapely.MultiPolygon(kept)


def _areas_of(section: Any) -> list[Any]:
    """Die Flächenstücke einer Geometrie; Linien und Punkte einer Berührung fallen weg."""
    import shapely

    return [
        part
        for part in shapely.get_parts(section)
        if part.geom_type == "Polygon" and part.area > EPS_GEOM * EPS_GEOM
    ]


def _thinnest_extrusion() -> float:
    """Die kleinste Höhe, die *Skizze extrudieren* annimmt — aus ihrem Register."""
    specs = getattr(REGISTRY.get("sketch_extrude").params, "__param_spec__", ())
    return next(
        (float(spec.minimum) for spec in specs if spec.name == "height" and spec.minimum),
        EPS_GEOM,
    )


def _extruded(section: Any, lower: float, upper: float) -> list[MeshData] | None:
    """Jedes Stück des Querschnitts von ``lower`` bis ``upper`` gezogen, in Zeichenkoordinaten.

    Stück für Stück: Zwei Stücke, die sich in einer Ecke berühren, teilten
    zusammen eine Kante mit vier Flächen, und das Netz wäre nicht dicht.
    """
    import trimesh

    bodies = []
    for part in _areas_of(section):
        # Fast doppelte Ecken aus dem Raster zerlegt die Dreiecksteilung nicht dicht.
        body = trimesh.creation.extrude_polygon(
            part.simplify(EPS_GEOM, preserve_topology=True), height=upper - lower
        )
        if not body.is_watertight:
            return None
        body.apply_translation((0.0, 0.0, lower))
        bodies.append(MeshData.of(body))
    return bodies or None


def _apart(first: MeshData, second: MeshData, cancelled: CancelToken) -> MeshData | None:
    """Was von ``first`` außerhalb von ``second`` liegt — ``None``, wenn das Netz nicht rechnet."""
    from app.core.errors import GeometryError
    from app.core.geom.boolean import boolean

    try:
        return boolean("difference", [first, second], allow_empty=True, cancelled=cancelled).mesh
    except GeometryError:
        return None


def _pieces_as_steps(
    *residuals: tuple[MeshData, str],
    source: MeshData,
    frame: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    features: tuple[Feature, ...],
    budget: RebuildBudget,
    cancelled: CancelToken,
    drilled: list[Feature],
) -> list[OperationDraft] | None:
    """Jedes Reststück als Prisma oder Bohrung — ``None``, sobald eines keines ist.

    Die Bohrungen kommen in ``drilled`` dazu, jede einmal; gebohrt wird erst,
    wenn alle Schichten zerlegt sind, denn eine Querbohrung kreuzt mehrere.

    Ein Stück, das kein Prisma ist, darf eine erkannte Bohrung samt Senkung
    berühren: Ohne deren Werkzeug (:func:`_drill_tool`) muss jedes übrige
    Teilstück ein Prisma sein, und die Bohrung wird gebohrt. Am Besenhalter
    lief eine gewölbte Stirnfläche über beide Schraubenlöcher, und erst ohne
    Löcher zerfiel ihr Rest in Prismen längs der Leiste.
    """
    directions = _directions(frame, features)
    holes = [feature for feature in features if feature.kind in {"hole", "slot"}]
    steps: list[OperationDraft] = []
    for residual, joining in residuals:
        for piece in _pieces(residual, cancelled):
            cancelled.raise_if_cancelled()
            if not _substantial(piece, budget):
                continue
            world = _in_world(piece, frame)
            found = _prism_piece(world, directions, source, budget, cancelled)
            if found is not None:
                steps.extend(
                    (found, OperationDraft(joining, ("obj_1", "obj_2"), outputs=("obj_1",)))
                )
                continue
            if joining == "union_objects":
                return None
            near = [hole for hole in holes if _touches(world, hole, features, budget)]
            tools = [tool for hole in near if (tool := _drill_tool(hole, features, budget))]
            if not near or len(tools) != len(near):
                return None
            rest: MeshData | None = MeshData.of(world)
            for tool in tools:
                rest = _apart(rest, tool, cancelled) if rest is not None else None
            if rest is None:
                return None
            for part in _pieces(rest, cancelled):
                if not _substantial(part, budget):
                    continue
                cut = _prism_piece(part, directions, source, budget, cancelled)
                if cut is None:
                    return None
                steps.extend((cut, OperationDraft(joining, ("obj_1", "obj_2"), outputs=("obj_1",))))
            drilled.extend(hole for hole in near if hole not in drilled)
    return steps


def _substantial(piece: Any, budget: RebuildBudget) -> bool:
    """Ob ein Stück mehr ist als ein Splitter, der in der Formgrenze verschwindet.

    Wo Profilkörper und Netz dieselbe Wand haben, hinterlässt die Differenz
    Tausende Splitter ohne Dicke, und eine leicht gewölbte Stirnfläche wie am
    Besenhalter einen Streifen von 0,013 mm. Abgezogen hätte ihn der exakte
    Kern als fast deckungsgleiche Fläche, und die Boolesche Rechnung scheiterte.
    Gemessen wird die mittlere Dicke ``2 · Volumen / Oberfläche``; unter einem
    Viertel der Formgrenze bleibt auch die größte Dicke eines Keils (die
    doppelte mittlere) innerhalb der Grenze, die die unabhängige Formprüfung
    danach misst.
    """
    area = float(piece.area)
    return area > EPS_GEOM and 2.0 * float(piece.volume) / area >= budget.local_mm / 4.0


def _in_world(piece: Any, frame: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]) -> Any:
    """Ein Stück aus Zeichenkoordinaten zurück in die Welt."""
    import trimesh

    foot, x_axis, y_axis, axis = frame
    vertices = np.asarray(piece.vertices, dtype=np.float64)
    return trimesh.Trimesh(
        vertices=foot
        + vertices[:, :1] * x_axis
        + vertices[:, 1:2] * y_axis
        + vertices[:, 2:3] * axis,
        faces=np.asarray(piece.faces),
        process=False,
    )


def _touches(
    world: Any, hole: Feature, features: tuple[Feature, ...], budget: RebuildBudget
) -> bool:
    """Ob das Stück in den Zylinder einer Bohrung samt Senkung reicht."""
    params = hole.params
    axis = np.array(params["axis"], dtype=float, copy=True)
    axis /= math.sqrt(dot3(axis, axis))
    widest = float(params["diameter"])
    for cone in _sinks_of(hole, features, budget.local_mm):
        widest = max(widest, float(cone.params["diameter"]))
    shifted = np.asarray(world.vertices, dtype=np.float64) - np.asarray(
        params["centre"], dtype=float
    )
    axial = along(shifted, axis)
    radial = shifted - axial[:, None] * axis
    reach = float(params.get("depth", 0.0)) / 2.0 + widest
    inside = (np.sqrt((radial * radial).sum(axis=1)) <= widest / 2.0 + budget.local_mm) & (
        np.abs(axial) <= reach
    )
    return bool(inside.any())


def _drill_tool(
    hole: Feature, features: tuple[Feature, ...], budget: RebuildBudget, *, beyond: bool = True
) -> MeshData | None:
    """Was die Bohrung samt eindeutiger Senkung wegnimmt, als Netz — etwas weiter als sie.

    Gedreht aus seinem Längsschnitt (Radius gegen Tiefe ab der Mündung), um
    ein Zehntel der Formgrenze weiter: Die Facetten der gebohrten Wand liegen
    innerhalb des Kreises, und was das Werkzeug mehr nimmt, ist Luft. Mit
    ``beyond`` reicht es über beide Enden hinaus; ohne endet es an Mündung
    und Grund — so füllt es die Bohrung, ohne über den Körper zu stehen.
    """
    import trimesh

    params = hole.params
    axis = np.array(params["axis"], dtype=float, copy=True)
    axis /= math.sqrt(dot3(axis, axis))
    centre = np.asarray(params["centre"], dtype=float)
    radius = float(params["diameter"]) / 2.0 + budget.tessellation_mm
    half = float(params.get("depth", 0.0)) / 2.0
    if half <= EPS_GEOM:
        return None
    margin = budget.local_mm if beyond else 0.0
    cones = _sinks_of(hole, features, budget.local_mm)
    if len(cones) == 1:
        mouth = np.asarray(cones[0].params["centre"], dtype=float)
        inward = axis if dot3(centre - mouth, axis) >= 0.0 else -axis
        far = dot3(centre - mouth, inward) + half
        wide = float(cones[0].params["diameter"]) / 2.0 + budget.tessellation_mm
        opening = float(cones[0].params["angle"]) / 2.0
        if not 0.0 < opening < 90.0 or wide <= radius:
            return None
        sink = (wide - radius) * exact_cos_degrees(opening) / exact_sin_degrees(opening)
        profile = [
            (0.0, -margin),
            (wide, -margin),
            (wide, 0.0),
            (radius, sink),
            (radius, far + margin),
            (0.0, far + margin),
        ]
    else:
        mouth = centre - axis * half
        inward = axis
        profile = [
            (0.0, -margin),
            (radius, -margin),
            (radius, 2.0 * half + margin),
            (0.0, 2.0 * half + margin),
        ]
    body = trimesh.creation.revolve(np.asarray(profile, dtype=np.float64), sections=128)
    if not body.is_watertight:
        return None
    x_axis, y_axis = _frame_axes(inward, mouth)
    local = np.asarray(body.vertices, dtype=np.float64)
    placed = trimesh.Trimesh(
        vertices=mouth + local[:, :1] * x_axis + local[:, 1:2] * y_axis + local[:, 2:3] * inward,
        faces=np.asarray(body.faces),
        process=False,
    )
    if float(placed.volume) < 0.0:
        placed.invert()
    return MeshData.of(placed)


def _pieces(body: MeshData, cancelled: CancelToken) -> list[Any]:
    """Die zusammenhängenden Stücke eines Netzes, jedes für sich."""
    raw = body.raw
    if not len(raw.faces):
        return []
    return [
        raw.submesh([faces], append=True) for faces in face_components(raw, cancelled=cancelled)
    ]


def _prism_piece(
    piece: Any,
    directions: list[np.ndarray],
    source: MeshData,
    budget: RebuildBudget,
    cancelled: CancelToken,
) -> OperationDraft | None:
    """Das Stück als Extrusion seines Querschnitts längs einer der Richtungen — oder ``None``.

    Ein Prisma hat überall denselben Querschnitt: in der Mitte, bei einem
    Fünftel und bei vier Fünfteln gleich groß, und Fläche mal Länge gibt
    sein Volumen. ``piece`` liegt in Weltkoordinaten. Abgezogen wird es mit
    einem Werkzeug, das über das Stück hinaus in die Luft reicht
    (:func:`_cut_reach`).
    """
    for direction in directions:
        found = _as_prism(piece, direction, budget, cancelled)
        if found is None:
            continue
        step = _prism_step(found, direction, source, budget, cancelled)
        if step is not None:
            return step
    return None


def _prism_step(
    found: tuple[np.ndarray, np.ndarray, np.ndarray, float, Any],
    direction: np.ndarray,
    source: MeshData,
    budget: RebuildBudget,
    cancelled: CancelToken,
) -> OperationDraft | None:
    """Das Werkzeug eines Prismas aus :func:`_as_prism`, so weit es reichen darf."""
    foot, x_axis, y_axis, span, section = found
    below, above, outline = _cut_reach(
        section, source, (foot, x_axis, y_axis, direction), span, budget, cancelled
    )
    return _extrusion(
        foot - direction * below,
        x_axis,
        y_axis,
        span + below + above,
        _traced(outline, budget),
        "obj_2",
    )


def _as_prism(
    piece: Any, direction: np.ndarray, budget: RebuildBudget, cancelled: CancelToken
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, Any] | None:
    """Ob das Stück ein Prisma längs ``direction`` ist — Fuß, Zeichenachsen, Länge, Querschnitt.

    Ein Prisma hat überall denselben Querschnitt: in der Mitte, bei einem
    Fünftel und bei vier Fünfteln gleich groß, und Fläche mal Länge gibt
    sein Volumen. ``piece`` liegt in Weltkoordinaten.
    """
    import trimesh

    from app.core.slice.analysis import cross_sections

    world = np.asarray(piece.vertices, dtype=np.float64)
    volume = float(piece.volume)
    centre = (world.min(axis=0) + world.max(axis=0)) / 2.0
    reach = along(world - centre, direction)
    low, high = float(reach.min()), float(reach.max())
    span = high - low
    if span <= budget.tessellation_mm:
        return None
    foot = centre + direction * low
    x_axis, y_axis = _frame_axes(direction, foot)
    shifted = world - foot
    local = MeshData.of(
        trimesh.Trimesh(
            vertices=np.column_stack(
                (along(shifted, x_axis), along(shifted, y_axis), along(shifted, direction))
            ),
            faces=np.asarray(piece.faces),
            process=False,
        )
    )
    sections = [
        section
        for section in cross_sections(
            local, [span * 0.5, span * 0.2, span * 0.8], cancelled=cancelled
        )
        if section is not None and not section.is_empty
    ]
    if len(sections) != 3:
        return None
    areas = [float(section.area) for section in sections]
    if abs(areas[0] * span - volume) > PRISM_SLACK * volume or any(
        abs(area - areas[0]) > PRISM_SLACK * areas[0] for area in areas[1:]
    ):
        return None
    return foot, x_axis, y_axis, span, sections[0]


def _cut_reach(
    section: Any,
    source: MeshData,
    frame: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    span: float,
    budget: RebuildBudget,
    cancelled: CancelToken,
) -> tuple[float, float, Any]:
    """Wie weit ein Abzug über sein Stück hinausreicht: nach unten, nach oben, zur Seite.

    Das Stück grenzt dort an den Körper, wo vorher eine Wand des Profils
    stand. Ein Werkzeug genau bis dahin läge auf dieser Wand, und an solchen
    fast deckungsgleichen Flächen scheitert der exakte Kern. Zur Seite reicht
    es deshalb um die Formgrenze weiter, nur nicht in das Material des Körpers
    über die Länge des Stücks; an den Enden um das Zehnfache, wo dahinter
    kein Material steht. **Bleibt ein Ende stehen, reicht die Seite nicht über
    das Material dahinter**: Dort liegt der Deckel des Werkzeugs auf einer
    Fläche, die ein anderes Werkzeug schon freigelegt hat — am Besenhalter der
    Grund der Schrift, und die beiden deckungsgleichen Stücke ließ der Kern
    als offene Naht stehen.
    """
    import shapely

    from app.core.slice.analysis import cross_sections

    foot, x_axis, y_axis, direction = frame
    local = _in_frame(source, foot, x_axis, y_axis, direction)
    beyond = budget.local_mm * 10.0
    inside = [span * (index + 0.5) / 8.0 for index in range(8)]
    behind = budget.local_mm / 2.0
    found = cross_sections(
        local,
        [*inside, -beyond / 2.0, span + beyond / 2.0, -behind, span + behind],
        cancelled=cancelled,
    )
    material = shapely.union_all(
        [entry for entry in found[: len(inside)] if entry is not None and not entry.is_empty]
    )
    outline = shapely.difference(section.buffer(budget.local_mm), material)
    if outline.is_empty:
        outline = section

    def open_at(entry: Any) -> bool:
        return entry is None or float(shapely.intersection(entry, outline).area) <= EPS_GEOM

    ends = (open_at(found[-4]), open_at(found[-3]))
    below, above = (beyond if open_end else 0.0 for open_end in ends)
    closed = [
        entry
        for entry, open_end in zip(found[-2:], ends, strict=True)
        if not open_end and entry is not None and not entry.is_empty
    ]
    if closed:
        outline = shapely.union(section, shapely.difference(outline, shapely.union_all(closed)))
    return below, above, outline


def _apart_at_touches(rings: list[list[Any]], step: float) -> list[list[Point2]]:
    """Ringe ohne gemeinsamen Punkt: Ein zweites Vorkommen rückt um ``step`` nach innen.

    Ein gültiges Polygon darf ein Loch haben, das seinen Rand in einem Punkt
    berührt, und zwei Teile dürfen sich in einer Ecke treffen. Die Skizze
    liest dort eine Verzweigung und nimmt den Umriss nicht an („Der Umriss
    verzweigt sich“, am Wandhalter quer zur Leiste). Das zweite Vorkommen
    rückt deshalb um einen Bruchteil der Formgrenze zur Mitte seiner Nachbarn.
    """
    seen: set[Point2] = set()
    result: list[list[Point2]] = []
    for ring in rings:
        points: list[Point2] = [(float(point[0]), float(point[1])) for point in ring]
        moved = list(points)
        for index, point in enumerate(points):
            if point not in seen:
                seen.add(point)
                continue
            before, after = points[index - 1], points[(index + 1) % len(points)]
            middle = ((before[0] + after[0]) / 2.0, (before[1] + after[1]) / 2.0)
            reach = math.dist(point, middle)
            if reach > EPS_GEOM:
                share = min(step / reach, 0.5)
                moved[index] = (
                    point[0] + (middle[0] - point[0]) * share,
                    point[1] + (middle[1] - point[1]) * share,
                )
        result.append(moved)
    return result


def _extrusion(
    foot: np.ndarray,
    x_axis: np.ndarray,
    y_axis: np.ndarray,
    height: float,
    elements: Sequence[SketchElement],
    output: str,
) -> OperationDraft | None:
    """Fertig nachgezeichnete Elemente als feste Skizze auf der Ebene durch ``foot``,
    gezogen um ``height``."""
    from app.core.sketch.planes import through_plane
    from app.core.sketch.serialize import sketch_to_text
    from app.core.types import Sketch, SketchConstraint

    if not elements:
        return None
    plane = through_plane((_vec3(foot), _vec3(foot + x_axis), _vec3(foot + y_axis)))
    constraints = tuple(
        SketchConstraint("fixed", (point,))
        for point in range(sum(len(element.points) for element in elements))
    )
    return OperationDraft(
        "sketch_extrude",
        params={
            "height": height,
            "sketch": sketch_to_text(Sketch(plane, tuple(elements), constraints)),
        },
        outputs=(output,),
    )


def _traced(section: Any, budget: RebuildBudget) -> tuple[SketchElement, ...]:
    """Ein Querschnitt als Strecken, Bögen und Kreise, Ring für Ring."""
    from app.core.sketch.traced import traced_loop

    parts = _areas_of(section)
    rings = [list(ring.coords)[:-1] for part in parts for ring in (part.exterior, *part.interiors)]
    return tuple(
        element
        for ring in _apart_at_touches(rings, budget.tessellation_mm / 10.0)
        for element in traced_loop(
            ring,
            budget.tessellation_mm,
            sag=budget.local_mm / 2.0,
            shortest=budget.local_mm / 4.0,
        )
    )


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


#: Welcher Anteil der Oberfläche sich selbst durchdringen darf, ohne dass der
#: Nachbau anhält. Aus CAD exportierte Netze kreuzen sich oft an einer Naht in
#: vier bis achtzig Dreiecken; am Korpus hielt das 16 Körper an, darunter
#: Minigolfteile und eine Kehle am Zapfen (0,07 % der Fläche). Form und
#: Volumen ändert so wenig nichts, was die unabhängige Prüfung nicht sähe.
CROSSING_SHARE: Final = 0.001


def _crossing_share(mesh: MeshData, crossed: tuple[int, ...]) -> float:
    """Welcher Anteil der Oberfläche auf Dreiecken liegt, die andere durchdringen."""
    if not crossed:
        return 0.0
    areas = np.asarray(mesh.raw.area_faces, dtype=np.float64)
    total = float(areas.sum())
    return float(areas[list(crossed)].sum()) / total if total > 0.0 else 1.0


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
    if not complete or _crossing_share(mesh, crossed) > CROSSING_SHARE:
        raise UserError(
            _("Die Ausgangsform ist noch nicht vollständig als überschneidungsfrei geprüft."),
            _("Reparieren Sie das Modell und starten Sie den Nachbau erneut."),
            suggestions=(CANCEL,),
        )
    if progress is not None:
        progress(0.1, str(_("Modell nachbauen")))
    # P4.0 liefert die begrenzten analytischen Flächen als Kandidatenquelle.
    # Die unabhängige Abnahme unten vergleicht weiterhin mit dem Originalnetz.
    # Ohne P4.0-Körper bleiben die Wege am Netz: Grundkörper aus seinen
    # Merkmalen und der Profilkörper aus seinen Querschnitten. An 20 Teilen
    # des Korpus entstand kein P4.0-Körper, und der Nachbau sagte dort ab,
    # bevor er einen Weg versucht hatte.
    recovered: Solid | None
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
        except from_mesh.ConversionRefusedError:
            recovered = None
    recovered_source = (
        None
        if recovered is None
        else replace(source, mesh=recovered, features=features_of(recovered, cancelled=token))
    )
    forms = [source] if recovered_source is None else [recovered_source]
    original_kinds = Counter(
        feature.kind for feature in source.features.values() if feature.kind != "face"
    )
    recovered_kinds = Counter(
        feature.kind for feature in forms[0].features.values() if feature.kind != "face"
    )
    if recovered_source is not None and original_kinds - recovered_kinds:
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
                    | _unexplained_planes(
                        form,
                        body,
                        token,
                        boundary_mm=budget.local_mm,
                        offset_mm=budget.tessellation_mm / 10.0,
                    )
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
        if recovered_source is not None:
            plans.extend(_layered(recovered_source, budget.local_mm, token))
        for index, (drafts, explained, form) in enumerate(plans):
            if progress is not None:
                progress(0.6 + 0.3 * index / len(plans), str(REGISTRY.get(drafts[0].op).title))
            assess(drafts, explained, form)
            if candidates and candidates[-1].check.accepted:
                break
    if not any(candidate.check.accepted for candidate in candidates):
        # Der Profilkörper zuletzt: Er rechnet Boolesche am Netz, bevor er
        # einen Plan hat, und trägt, was die Wege davor nicht tragen.
        if progress is not None:
            progress(0.9, str(_("Modell nachbauen")))
        for drafts, explained, form in _prismatic(source, mesh, budget, token):
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
