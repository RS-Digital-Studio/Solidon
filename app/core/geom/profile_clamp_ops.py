"""Vier gekoppelte Profilklemmteile und Ersatz der getrennten Einlagen (§24, §25)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, cast

import numpy as np

from app.core import expressions
from app.core.errors import ValidationError
from app.core.geom.attributes import counts, transfer
from app.core.geom.boolean import BooleanKind, boolean, deepest
from app.core.geom.mesh import as_mesh_data
from app.core.geom.sketch_solid import outline_points
from app.core.geom.transform import apply as moved_mesh
from app.core.knowledge import profiles, standards
from app.core.knowledge.parts import profile_clamps as clamps
from app.core.registry import NAME_DOC, op_params, param, register_op, validate
from app.core.types import (
    BaseParams,
    Feature,
    Finding,
    OpContext,
    OpResult,
    PartResult,
    Profile,
    SceneObject,
    SolverInfo,
    Transform,
)
from app.core.units import DEGREE_UNIT, EPS_GEOM
from app.i18n import TranslatableText, _

ROLES = ("shell_lower", "shell_upper", "liner_lower", "liner_upper")
BINDING = "profile_clamp"
FRAME_Y = "profile_clamp_y"


@op_params
class CounterProfileParams(BaseParams):
    profile_shape: str = param(
        title=_("Profilform"),
        default="round",
        choices=("round", "ellipse", "drawn"),
        doc=_("Gemessener runder, ovaler oder selbst gezeichneter Profilquerschnitt."),
    )
    diameter: float = param(
        title=_("Profildurchmesser"),
        default=16.0,
        minimum=2.0,
        maximum=250.0,
        unit="mm",
        depends_on=("profile_shape", ("round",)),
        doc=_("Gemessener Außendurchmesser des runden Gegenprofils."),
    )
    width: float = param(
        title=_("Profilbreite"),
        default=47.0,
        minimum=2.0,
        maximum=250.0,
        unit="mm",
        depends_on=("profile_shape", ("ellipse",)),
        doc=_("Gesamte Breite der ausdrücklich gewählten Ellipse."),
    )
    height: float = param(
        title=_("Profilhöhe"),
        default=32.0,
        minimum=2.0,
        maximum=250.0,
        unit="mm",
        depends_on=("profile_shape", ("ellipse",)),
        doc=_("Gesamte Höhe der ausdrücklich gewählten Ellipse."),
    )
    counter_sketch: str = param(
        title=_("Gegenkontur"),
        kind="sketch",
        default="",
        required=True,
        depends_on=("profile_shape", ("drawn",)),
        doc=_(
            "Eine geschlossene Gegenkontur ohne Innenlöcher. Ihre Maßausdrücke bleiben erhalten."
        ),
    )
    clamp_material: str = param(
        title=_("Material der Schalen"),
        kind="material",
        default="",
        required=True,
        doc=_("Materialprofil beider Schalen; wählen Sie es ausdrücklich aus."),
    )
    liner_material: str = param(
        title=_("Material der Einlagen"),
        kind="material",
        default="",
        required=True,
        doc=_("Eigenes Materialprofil beider Einlagen für Spiel, Übermaß und Mindestwand."),
    )


@op_params
class ProfileClampSetParams(CounterProfileParams):
    depth: float = param(
        title=_("Klemmtiefe"),
        default=40.0,
        minimum=16.0,
        maximum=80.0,
        unit="mm",
        doc=_("Länge der Schalen entlang des Profils."),
    )
    liner_thickness: float = param(
        title=_("Einlagenstärke"),
        default=2.0,
        minimum=1.0,
        maximum=5.0,
        unit="mm",
        placement="advanced",
        doc=_("Normale Wandstärke zwischen Gegenprofil und Außensitz."),
    )
    wall: float = param(
        title=_("Schalenwand"),
        default=4.0,
        minimum=2.0,
        maximum=8.0,
        unit="mm",
        placement="advanced",
        doc=_("Normaler Abstand vom Sitz zur Außenkontur."),
    )
    joint_gap: float = param(
        title=_("Teilungsspalt"),
        default=1.0,
        minimum=0.5,
        maximum=2.0,
        unit="mm",
        placement="advanced",
        doc=_("Abstand der Schalen in der noch nicht angezogenen Montagelage."),
    )
    flange_width: float = param(
        title=_("Bundbreite"),
        default=1.2,
        minimum=0.8,
        maximum=4.0,
        unit="mm",
        placement="advanced",
        doc=_("Überstand des vorderen Anschlagbundes über die Einlagenaußenkontur."),
    )
    flange_height: float = param(
        title=_("Bundhöhe"),
        default=1.5,
        minimum=1.0,
        maximum=4.0,
        unit="mm",
        placement="advanced",
        doc=_("Axiale Stärke des vorderen Anschlagbundes."),
    )
    rear_relief: float = param(
        title=_("Freiraum hinten"),
        default=2.0,
        minimum=1.0,
        maximum=4.0,
        unit="mm",
        placement="advanced",
        doc=_("Verkürzt den Einlagenkern gegenüber der Schale."),
    )
    split_angle: float = param(
        title=_("Winkel der Trennebene"),
        default=0.0,
        minimum=-180.0,
        maximum=180.0,
        unit=DEGREE_UNIT,
        placement="advanced",
        doc=_("Dreht die Teilung innerhalb des gemessenen Profilquerschnitts."),
    )
    split_offset: float = param(
        title=_("Versatz der Trennebene"),
        default=0.0,
        minimum=-125.0,
        maximum=125.0,
        unit="mm",
        placement="advanced",
        doc=_("Verschiebt die Teilung; beide Hälften müssen zusammenhängend montierbar bleiben."),
    )
    screw_size: str = param(
        title=_("Schraubengröße"),
        default="M4",
        choices=("M4",),
        placement="advanced",
        doc=_("Zwei Schrauben und Muttern mit Aufnahmen aus der Normteiltabelle."),
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)


@op_params
class ReplaceProfileLinersParams(CounterProfileParams):
    minimum_wall: float = param(
        title=_("Mindestwand der Einlage"),
        default=2.0,
        minimum=1.0,
        maximum=5.0,
        unit="mm",
        placement="advanced",
        doc=_("Verbleibende Mindestwand zwischen neuer Gegenkontur und vorhandenem Sitz."),
    )


def _invalid(message: TranslatableText, field: str = "counter_sketch") -> ValidationError:
    return ValidationError(field=field, constraint="profile_clamp", detail=message)


def _points(section: Any) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in list(clamps.polygon_of(section).exterior.coords)[:-1]]


def _section(points: Sequence[Sequence[float]]) -> Any:
    from app.core.sketch.profile import Profile as SketchProfile
    from app.core.sketch.profile import ProfileSegment

    xy = [(float(point[0]), float(point[1])) for point in points]
    profile = SketchProfile(
        segments=tuple(
            ProfileSegment("line", point, xy[(index + 1) % len(xy)])
            for index, point in enumerate(xy)
        )
    )
    return clamps.section_of(profile)


def _counter(ctx: OpContext, p: CounterProfileParams) -> Any:
    from app.core.sketch.profile import Profile as SketchProfile
    from app.core.sketch.profile import profile_of
    from app.core.sketch.serialize import resolve_sketch_values, sketch_from_text
    from app.core.sketch.solver import solve_sketch

    ctx.cancelled.raise_if_cancelled()
    if p.profile_shape == "drawn":
        if not p.counter_sketch:
            raise _invalid(_("Zeichnen oder wählen Sie zuerst die Gegenkontur."))
        values = expressions.resolve(ctx.scene.parameters)
        text = resolve_sketch_values(p.counter_sketch, values)
        solved = profile_of(solve_sketch(sketch_from_text(text)))
        return clamps.section_of(solved)
    if p.profile_shape not in {"round", "ellipse"}:
        raise _invalid(
            _("Wählen Sie ein rundes, ovales oder gezeichnetes Profil."), "profile_shape"
        )
    rx, ry = (
        (p.diameter / 2.0,) * 2 if p.profile_shape == "round" else (p.width / 2.0, p.height / 2.0)
    )
    reference = outline_points(
        SketchProfile(circle=((0.0, 0.0), max(rx, ry))),
        max_sag=clamps.CONTOUR_SAG,
        check_cancelled=ctx.cancelled.raise_if_cancelled,
    )
    count = 4 * math.ceil(len(reference) / 4)
    return _section(
        [
            (rx * math.cos(math.tau * i / count), ry * math.sin(math.tau * i / count))
            for i in range(count)
        ]
    )


def _materials(ctx: OpContext, p: CounterProfileParams) -> tuple[Profile, Profile]:
    if not p.clamp_material.strip() or not p.liner_material.strip():
        raise _invalid(_("Wählen Sie das Material der Schalen und der Einlagen."), "liner_material")
    hard = Profile(ctx.profile.printer, profiles.material(p.clamp_material))
    soft = Profile(ctx.profile.printer, profiles.material(p.liner_material))
    if hard.material.clearance < 0.0 or soft.material.clearance < 0.0 or soft.material.press > 0.0:
        raise _invalid(
            _("Prüfen Sie Spiel und Übermaß der gewählten Materialprofile."), "liner_material"
        )
    return hard, soft


def _settings(p: ProfileClampSetParams) -> dict[str, Any]:
    return {
        name: getattr(p, name)
        for name in (
            "depth",
            "wall",
            "liner_thickness",
            "joint_gap",
            "flange_width",
            "flange_height",
            "rear_relief",
            "split_angle",
            "split_offset",
            "screw_size",
        )
    }


def _wall_rules(settings: Mapping[str, Any], hard: Profile, soft: Profile) -> None:
    if float(settings["wall"]) < hard.minimum_wall_thickness - EPS_GEOM:
        raise _invalid(
            _("Vergrößern Sie die Schalenwand auf die Mindestwand des gewählten Druckprofils."),
            "wall",
        )
    if (
        min(float(settings["liner_thickness"]), float(settings["flange_height"]))
        < soft.minimum_wall_thickness - EPS_GEOM
    ):
        raise _invalid(
            _(
                "Vergrößern Sie Einlagenstärke und Bundhöhe auf die Mindestwand "
                "des gewählten Druckprofils."
            ),
            "liner_thickness",
        )
    play = max(hard.material.clearance, soft.material.clearance)
    if float(settings["flange_width"]) - play / 2.0 < soft.minimum_wall_thickness - EPS_GEOM:
        raise _invalid(
            _("Der Anschlagbund trägt zu wenig auf der Schale. Vergrößern Sie die Bundbreite."),
            "flange_width",
        )


def _shell_params(
    settings: Mapping[str, Any], half: str, hard: Profile
) -> clamps.ProfileClampShellParams:
    return validate(
        clamps.ProfileClampShellParams,
        {
            # Der Bauteilbauer erhält seine bereits gelöste gemeinsame Kontur
            # separat. Dieser Satz trägt nur die übrigen Konstruktionsmaße.
            **{entry.name: entry.default for entry in clamps.ProfileClampShellParams.spec()},
            "depth": settings["depth"],
            "wall": settings["wall"],
            "half": half,
            "joint_gap": settings["joint_gap"],
            "flange_height": settings["flange_height"],
            "split_angle": settings["split_angle"],
            "split_offset": settings["split_offset"],
            "screw_size": settings["screw_size"],
            "play": hard.material.clearance,
        },
    )


def _liner_params(
    settings: Mapping[str, Any], half: str, soft: Profile
) -> clamps.ProfileClampLinerParams:
    return validate(
        clamps.ProfileClampLinerParams,
        {
            **{entry.name: entry.default for entry in clamps.ProfileClampLinerParams.spec()},
            "depth": settings["depth"],
            "liner_thickness": settings["liner_thickness"],
            "half": half,
            "flange_width": settings["flange_width"],
            "flange_height": settings["flange_height"],
            "rear_relief": settings["rear_relief"],
            "split_angle": settings["split_angle"],
            "split_offset": settings["split_offset"],
            "play": soft.material.clearance,
            "grip": -soft.material.press,
        },
    )


def _bound_part(part: PartResult, binding: dict[str, Any], role: str) -> PartResult:
    front = part.features["front"]
    own = {**binding, "role": role, "anchor": list(front.params["centre"])}
    features = {
        **part.features,
        "front": replace(
            front,
            params={
                **front.params,
                BINDING: own,
                FRAME_Y: (0.0, 1.0, 0.0),
            },
        ),
    }
    return replace(part, features=features)


def _findings(settings: Mapping[str, Any], hard: Profile, soft: Profile) -> list[Finding]:
    screw = standards.screw(settings["screw_size"])
    nut = standards.nut(settings["screw_size"])
    ear = max(screw.head_height, nut.height) + settings["wall"] + settings["joint_gap"] / 2
    length = 2 * ear - screw.head_height
    return [
        Finding(
            code="profile_clamp.material_fit",
            severity="info",
            message=_(
                "Sitzspiel {clearance} mm gesamt, Übermaß am Gegenprofil {press} mm gesamt. "
                "Prüfen Sie den Sitz mit den gewählten Materialien.",
                clearance=max(hard.material.clearance, soft.material.clearance),
                press=-soft.material.press,
            ),
            values={
                "clearance": max(hard.material.clearance, soft.material.clearance),
                "press": -soft.material.press,
            },
        ),
        Finding(
            code="profile_clamp.hardware",
            severity="info",
            message=_(
                "Montage: zwei {size}-Schrauben, mindestens {length} mm unter dem Kopf, "
                "und passende Muttern. Einlagen von der Bundseite einschieben; "
                "waagrechte Schraubenlöcher beim Druck auf Stützen prüfen.",
                size=settings["screw_size"],
                length=length,
            ),
            values={"size": settings["screw_size"], "length": length},
        ),
    ]


@register_op(
    name="create_profile_clamp_set",
    title=_("Profilklemme mit Einlagen"),
    category="primitive",
    params=ProfileClampSetParams,
    consumes=0,
    produces=4,
    touches_features=True,
    material_params=("clamp_material", "liner_material"),
    doc=_(
        "Erzeugt zwei verschraubbare Schalen und zwei getrennte, austauschbare Einlagen "
        "aus einer gemeinsamen Gegenkontur."
    ),
)
def create_profile_clamp_set(ctx: OpContext) -> OpResult:
    """Eine gespeicherte Kontur und zwei Materialrollen erzeugen alle vier Körper."""
    p = cast(ProfileClampSetParams, ctx.params)
    hard, soft = _materials(ctx, p)
    settings = _settings(p)
    _wall_rules(settings, hard, soft)
    counter = _counter(ctx, p)
    inside = clamps.offset_section(counter, soft.material.press / 2.0)
    outside = clamps.offset_section(inside, p.liner_thickness)
    seat = clamps.offset_section(
        outside, max(hard.material.clearance, soft.material.clearance) / 2.0
    )
    binding = {
        "version": 1,
        "settings": settings,
        "counter": _points(counter),
        "outside": _points(outside),
        "seat": _points(seat),
        "seat_clearance": max(hard.material.clearance, soft.material.clearance),
        "liner_clearance": soft.material.clearance,
        "counter_press": soft.material.press,
        "clamp_material": hard.material.id,
        "liner_material": soft.material.id,
    }
    names = (_("Untere Schale"), _("Obere Schale"), _("Untere Einlage"), _("Obere Einlage"))
    outputs, solvers, findings = [], [], _findings(settings, hard, soft)
    for index, role in enumerate(ROLES):
        ctx.cancelled.raise_if_cancelled()
        half = "lower" if role.endswith("lower") else "upper"
        if role.startswith("shell"):
            built, solver = clamps.build_shell(
                _shell_params(settings, half, hard),
                seat,
                quality=ctx.quality,
                cancelled=ctx.cancelled,
            )
            solvers.append(solver)
            material = hard.material.id
        else:
            built = clamps.build_liner(
                _liner_params(settings, half, soft),
                counter,
                outside=outside,
                cancelled=ctx.cancelled,
            )
            material = soft.material.id
        part = _bound_part(built, binding, role)
        name = _("{name} · {role}", name=p.name, role=names[index]) if p.name else names[index]
        outputs.append(
            SceneObject(id="", name=name, mesh=part.mesh, features=part.features, material=material)
        )
        findings.extend(part.findings)
        ctx.progress((index + 1) / len(ROLES), str(_("Profilklemme aufbauen")))
    return OpResult(outputs=outputs, solver=deepest(solvers), findings=findings)


def _seat_error() -> ValidationError:
    return _invalid(
        _(
            "Der vorhandene Klemmensitz ist nicht mehr eindeutig belegt. "
            "Wählen Sie die vier zusammengehörigen Teile oder erzeugen Sie eine neue Klemme."
        )
    )


def _binding(source: SceneObject, role: str) -> tuple[Feature, Mapping[str, Any]]:
    matches = [
        feature
        for feature in source.features.values()
        if isinstance(feature.params.get(BINDING), Mapping)
        and feature.params[BINDING].get("role") == role
    ]
    if len(matches) != 1 or not matches[0].face_indices:
        raise _seat_error()
    feature = matches[0]
    binding = feature.params[BINDING]
    if binding.get("version") != 1:
        raise _seat_error()
    return feature, binding


def _frame(feature: Feature, binding: Mapping[str, Any]) -> np.ndarray:
    try:
        x = np.asarray(feature.params["direction"], dtype=float)
        y = np.asarray(feature.params[FRAME_Y], dtype=float)
        z = -np.asarray(feature.params["normal"], dtype=float)
        linear = np.column_stack((x, y, z))
        if linear.shape != (3, 3) or not np.allclose(
            linear.T @ linear, np.eye(3), atol=EPS_GEOM, rtol=0
        ):
            raise _seat_error()
        frame = np.eye(4)
        frame[:3, :3] = linear
        frame[:3, 3] = np.asarray(feature.params["centre"]) - linear @ np.asarray(binding["anchor"])
        if not np.isfinite(frame).all():
            raise _seat_error()
        return frame
    except (KeyError, TypeError, ValueError) as exc:
        raise _seat_error() from exc


def _end_planes(
    source: SceneObject, body: Any, front: Feature, settings: Mapping[str, Any]
) -> None:
    """Die beiden wirklichen Stirnflächen müssen die gespeicherte Sitztiefe begrenzen.

    Ein längerer Sitz enthält den alten Prüfstreifen vollständig. Erst seine
    Endflächen unterscheiden deshalb eine axiale Skalierung von einer
    unveränderten Schale; Metadatenhöhen allein leisten diesen Nachweis nicht.
    """
    back = source.features.get("back")
    if back is None:
        raise _seat_error()
    heights = (settings["flange_height"], settings["flange_height"] + settings["depth"])
    for feature, height, sign in zip((front, back), heights, (-1.0, 1.0), strict=True):
        indices = np.asarray(feature.face_indices, dtype=np.int64)
        if (
            feature.kind != "face"
            or not len(indices)
            or indices.min() < 0
            or indices.max() >= body.triangle_count
        ):
            raise _seat_error()
        if (
            np.max(np.abs(body.raw.triangles[indices, :, 2] - height)) > EPS_GEOM
            or np.max(np.abs(body.raw.face_normals[indices, 2] - sign)) > EPS_GEOM
        ):
            raise _seat_error()


def _check_liner_frame(
    source: SceneObject,
    binding: Mapping[str, Any],
    frame: np.ndarray,
    half: str,
    soft: Profile,
    ctx: OpContext,
) -> list[SolverInfo]:
    """Jeden eigenen Einlagenrahmen an seiner vollständigen Konstruktion belegen.

    Angeordnete Teile dürfen verschiedene starre Rahmen tragen. Eine skalierte
    oder umgeformte Einlage rechtfertigt ihren alten Rahmen nicht mehr.
    Die damals tatsächlich angewandten Zugaben stehen am Ergebnis und werden
    unabhängig von der heutigen Materialkalibrierung nachgeprüft.
    """
    params = validate(
        clamps.ProfileClampLinerParams,
        {
            **_liner_params(binding["settings"], half, soft).as_dict(),
            "play": float(binding["liner_clearance"]),
            "grip": -float(binding["counter_press"]),
        },
    )
    expected = as_mesh_data(
        clamps.build_liner(
            params,
            _section(binding["counter"]),
            outside=_section(binding["outside"]),
            cancelled=ctx.cancelled,
        ).mesh
    )
    actual = moved_mesh(as_mesh_data(source.mesh), np.linalg.inv(frame))
    budget = EPS_GEOM * (expected.area + actual.area)
    solvers = []
    for first, second in ((expected, actual), (actual, expected)):
        difference = boolean(
            "difference", [first, second], allow_empty=True, cancelled=ctx.cancelled
        )
        if (
            difference.solver.strategy not in {"direct", "welded"}
            or abs(difference.mesh.volume) > budget
        ):
            raise _seat_error()
        solvers.append(difference.solver)
    return solvers


@register_op(
    name="replace_profile_liners",
    title=_("Einlagen für neues Profil"),
    category="parts",
    params=ReplaceProfileLinersParams,
    consumes=4,
    produces=4,
    keeps_inputs=4,
    touches_features=True,
    material_params=("clamp_material", "liner_material"),
    doc=_(
        "Ersetzt beide Einlagen für eine neue Gegenkontur und prüft den unveränderten Sitz "
        "beider vorhandenen Schalen."
    ),
)
def replace_profile_liners(ctx: OpContext) -> OpResult:
    """Beide aktuellen Sitze über ihre ganze Tiefe prüfen, danach nur die Einlagen ersetzen."""
    from app.core.perceive.matching import moved_features

    p = cast(ReplaceProfileLinersParams, ctx.params)
    hard, soft = _materials(ctx, p)
    if len(ctx.inputs) != len(ROLES):
        raise _seat_error()
    known = [_binding(source, role) for source, role in zip(ctx.inputs, ROLES, strict=True)]
    base = known[0][1]
    common_keys = ("seat", "clamp_material")
    if any(any(binding.get(key) != base.get(key) for key in common_keys) for _, binding in known):
        raise _seat_error()
    if known[1][1].get("settings") != base.get("settings"):
        raise _seat_error()
    # Nur die verlangte Einlagenmindestwand darf ein vorheriger Ersatz
    # geändert haben. Gleiche XY-Sitze allein verbinden keine verschiedenen
    # Tiefen, Bünde oder Teilungsebenen zu derselben Vierergruppe.
    for _feature, binding in known[2:]:
        local = binding.get("settings", {})
        if any(
            local.get(key) != value
            for key, value in base["settings"].items()
            if key != "liner_thickness"
        ):
            raise _seat_error()
    if any(source.material != hard.material.id for source in ctx.inputs[:2]):
        raise _invalid(
            _("Wählen Sie für die Schalen ihr tatsächlich zugewiesenes Material."), "clamp_material"
        )
    frames = [_frame(feature, binding) for feature, binding in known]
    settings = {**base["settings"], "liner_thickness": p.minimum_wall}
    _wall_rules(settings, hard, soft)
    seat = _section(base["seat"])
    solvers = []
    for index, half in enumerate(("lower", "upper")):
        body = moved_mesh(as_mesh_data(ctx.inputs[index].mesh), np.linalg.inv(frames[index]))
        _end_planes(ctx.inputs[index], body, known[index][0], settings)
        empty, wall = clamps.seat_probes(
            _shell_params(settings, half, hard), seat, strip=hard.minimum_wall_thickness
        )
        probes: tuple[tuple[BooleanKind, list[Any]], ...] = (
            ("intersection", [body, empty]),
            ("difference", [wall, body]),
        )
        for kind, meshes in probes:
            result = boolean(
                kind, meshes, quality="fine", allow_empty=True, cancelled=ctx.cancelled
            )
            solvers.append(result.solver)
            budget = EPS_GEOM * (empty.raw.area if kind == "intersection" else wall.raw.area)
            if (
                result.solver.strategy not in {"direct", "welded"}
                or abs(result.mesh.volume) > budget
            ):
                raise _seat_error()
    counter = _counter(ctx, p)
    for index, half in enumerate(("lower", "upper"), start=2):
        solvers.extend(
            _check_liner_frame(ctx.inputs[index], known[index][1], frames[index], half, soft, ctx)
        )
    clearance = max(hard.material.clearance, soft.material.clearance)
    same_clearance = math.isclose(
        clearance, float(base["seat_clearance"]), abs_tol=EPS_GEOM, rel_tol=0
    )
    outside = (
        _section(base["outside"])
        if same_clearance
        else clamps.offset_section(seat, -clearance / 2.0)
    )
    outer_points = base["outside"] if same_clearance else _points(outside)
    binding = {
        **base,
        "settings": settings,
        "counter": _points(counter),
        "outside": outer_points,
        "seat_clearance": clearance,
        "liner_clearance": soft.material.clearance,
        "counter_press": soft.material.press,
        "liner_material": soft.material.id,
    }
    outputs = list(ctx.inputs[:2])
    findings = _findings(settings, hard, soft)
    released_filaments = False
    for index, half in enumerate(("lower", "upper"), start=2):
        part = clamps.build_liner(
            _liner_params(settings, half, soft), counter, outside=outside, cancelled=ctx.cancelled
        )
        part = _bound_part(part, binding, ROLES[index])
        mesh = moved_mesh(as_mesh_data(part.mesh), frames[index])
        source = ctx.inputs[index]
        slots = source.material_slots
        if source.material == soft.material.id:
            old_mesh = as_mesh_data(source.mesh)
            previous = counts(old_mesh)
            cut_slot = max(previous, key=lambda key: (previous[key], -key))
            mesh = transfer(mesh, [old_mesh], cut_slot=cut_slot)
        else:
            released_filaments |= bool(slots or as_mesh_data(source.mesh).slots)
            slots = []
        outputs.append(
            replace(
                source,
                mesh=mesh,
                features=moved_features(
                    part.features,
                    cast(
                        Transform,
                        tuple(tuple(float(value) for value in row) for row in frames[index]),
                    ),
                ),
                material=soft.material.id,
                material_slots=list(slots),
            )
        )
        findings.extend(part.findings)
        ctx.progress((index - 1) / 2.0, str(_("Einlagen erneuern")))
    if released_filaments:
        findings.append(
            Finding(
                code="profile_clamp.filament_reassign",
                severity="info",
                message=_(
                    "Weisen Sie den neuen Einlagen ein Filament für das gewählte Material zu."
                ),
            )
        )
    return OpResult(
        outputs=outputs, solver=deepest(solvers) or SolverInfo("direct"), findings=findings
    )
