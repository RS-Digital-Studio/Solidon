"""Primitive (Bauplan §25, Kategorie „Boolesch").

Säule A beginnt hier: ohne einen Weg, einen ersten Körper in eine leere Szene
zu setzen, hat „bau mir eine Halterung" nichts, worauf es stehen könnte.
Quader, Zylinder, Kegel, Kugel und Ring decken die analytischen Grundformen;
Zusammengesetztes entsteht daraus über Boolesche Ops oder als Baustein aus der
Bibliothek. Die Regelsammlung priorisiert geeignete Bausteine vor dem Aufbau
einzelner Primitive (§39).

**Hier stand bis zum 26.08.2026 auch der OpenSCAD-Körper.** Er war die
Rückfallebene aus §24.1, für Formen, die kein Baustein und kein Primitiv
hergab. Seit die Skizzen im Haus sind (§30.1: extrudieren, aufziehen, drehen,
ziehen, austragen), gibt es diese Formen nicht mehr — der Testfall, der einmal
*der* OpenSCAD-Fall war, verbietet ihn seit P13 ausdrücklich. Was blieb, war
die einzige Stelle im Programm, die fremden Quelltext ausführt, mitsamt der
Prüfung aus §32, einer Installationshürde und einem Werkzeug im Auftrag des
Agenten. Entfernt auf Entscheidung von Robert; `to_scad()` als *Ausgabe* eines
Bausteins bleibt (`knowledge/parts/scad.py`), denn die braucht nichts davon.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, cast

import numpy as np

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, translation
from app.core.knowledge.parts.build import face
from app.core.knowledge.parts.shapes import SEGMENTS, box, cone, cylinder
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.sketch.planes import frame_of
from app.core.types import (
    BaseParams,
    Feature,
    OpContext,
    OpResult,
    Quality,
    SceneObject,
    Transform,
    Vec3,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM, is_greater, is_zero
from app.i18n import TranslatableText, _

_ANCHORS = ("centre", "corner")

_POSITION_X_DOC = _("Verschiebt den bisherigen Bezugspunkt des Körpers entlang X.")
_POSITION_MORE_DOC = _("Weitere Achse des Orts — siehe Position X.")
_NORMAL_X_DOC = _("Richtung der lokalen Z-Achse. 0/0/0 behält die bisherige Ausrichtung nach oben.")
_NORMAL_MORE_DOC = _("Weitere Achse der Richtung — siehe Normale X.")

#: Ab wann eine Normale als senkrecht gilt (:func:`top_face_of`). Der Kosinus
#: von einem Grad — enger wäre eine Frage an die Rechengenauigkeit, weiter
#: zählte die oberste Segmentreihe einer Kugel als Deckfläche.
FLAT_ENOUGH = 0.9998

#: Wie fein die Kugel höchstens wird. Der Regler heißt „Segmente" und geht bis
#: 128; seine Zahl ging als **Unterteilungstiefe** in die Icosphere, und die
#: wächst mit ``20 · 4ⁿ``. Bei 128 waren das 20 971 520 Dreiecke — kein
#: langsamer Körper, sondern eine angehaltene Sitzung: Jeder Schritt danach
#: rechnet, speichert und zeichnet sie wieder. Fünf Unterteilungen sind 20 480
#: Dreiecke; das ist bei einer 20-mm-Kugel eine Kantenlänge von 0,3 mm und
#: damit feiner, als ein Drucker sie legt. Der Regler bleibt bei 128, weil
#: gespeicherte Projekte ihn dort stehen haben — er wird nur nicht mehr
#: geglaubt, und sein ``doc`` sagt das.
MAX_SPHERE_SUBDIVISIONS = 5


def _round_segments(segments: int, quality: Quality) -> int:
    """Im Entwurf gröber, aber immer mit Punkten auf den vier Hauptachsen.

    Ohne das Viererraster unterschreitet ein Ring bei etwa 31 Segmenten sein
    eingetragenes Außenmaß und schwebt knapp über dem Druckbett: keine Stützstelle
    liegt dann auf X, Y oder unten. Die Obergrenzen der beiden Schemata sind durch
    vier teilbar, daher bleibt das Aufrunden innerhalb ihres Bereichs.
    """
    wanted = segments if quality == "fine" else max(8, segments // 2)
    return ((wanted + 3) // 4) * 4


def primitive_local_tool(name: str, values: Mapping[str, Any], quality: Quality) -> MeshData:
    """Baut einen validierten Grundkörper an seinem bisherigen lokalen Bezugspunkt.

    Operation und Oberflächenvorschau rufen dieselbe Funktion auf. Platz und
    Richtung gehören ausdrücklich nicht hierher: Der lokale Körper steht auf
    +Z, und genau eine Rahmenmatrix legt ihn danach in die Szene.
    """
    if name == "create_box":
        mesh = box(float(values["width"]), float(values["depth"]), float(values["height"]))
        if str(values["anchor"]) == "corner":
            mesh = apply(
                mesh,
                translation((float(values["width"]) / 2.0, float(values["depth"]) / 2.0, 0.0)),
            )
        return mesh
    if name == "create_cylinder":
        return cylinder(
            float(values["diameter"]),
            float(values["height"]),
            segments=int(values["segments"]),
        )
    if name == "create_cone":
        bottom_diameter = float(values["bottom_diameter"])
        top_diameter = float(values["top_diameter"])
        if is_zero(bottom_diameter) and is_zero(top_diameter):
            raise ValidationError(
                "bottom_diameter",
                _("Mindestens einer der beiden Durchmesser muss größer als null sein."),
                value=bottom_diameter,
                constraint="range",
            )
        return cone(
            bottom_diameter,
            top_diameter,
            float(values["height"]),
            segments=_round_segments(int(values["segments"]), quality),
        )
    if name == "create_sphere":
        import trimesh

        diameter = float(values["diameter"])
        body = trimesh.creation.icosphere(
            subdivisions=min(
                MAX_SPHERE_SUBDIVISIONS,
                max(1, int(values["segments"]) // 12),
            ),
            radius=diameter / 2.0,
        )
        body.apply_translation([0.0, 0.0, diameter / 2.0])
        return MeshData.of(body)
    if name == "create_torus":
        import trimesh

        outer_diameter = float(values["outer_diameter"])
        tube_diameter = float(values["tube_diameter"])
        if not is_greater(outer_diameter, 2.0 * tube_diameter):
            raise ValidationError(
                "tube_diameter",
                _(
                    "Die Schnurstärke ist für diesen Außendurchmesser zu groß — sie muss kleiner "
                    "als dessen Hälfte sein."
                ),
                value=tube_diameter,
                constraint="crosses_axis",
                values={"maximum_mm": outer_diameter / 2.0},
            )
        minor_radius = tube_diameter / 2.0
        segments = _round_segments(int(values["segments"]), quality)
        body = trimesh.creation.torus(
            major_radius=(outer_diameter - tube_diameter) / 2.0,
            minor_radius=minor_radius,
            major_sections=segments,
            minor_sections=segments,
        )
        body.apply_translation([0.0, 0.0, minor_radius])
        return MeshData.of(body)
    raise ValueError(f"unknown mesh primitive: {name}")


@op_params
class PositionedPrimitiveParams(BaseParams):
    """Gemeinsamer freier Bezugspunkt und lokale Z-Richtung.

    Öffentlich, weil der exakte Kern dieselben sechs Felder trägt
    (``brep.ops``): Die Zwillingspaare aus ``MENU_TWINS`` sind dieselbe
    Handlung in zwei Rechenkernen, und ein Umschalten darf den Körper nicht
    in den Ursprung zurückstellen.
    """

    x: float = param(
        title=_("Position X"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_POSITION_X_DOC,
    )
    y: float = param(
        title=_("Position Y"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_POSITION_MORE_DOC,
    )
    z: float = param(
        title=_("Position Z"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_POSITION_MORE_DOC,
    )
    nx: float = param(
        title=_("Normale X"),
        default=0.0,
        placement="advanced",
        doc=_NORMAL_X_DOC,
    )
    ny: float = param(
        title=_("Normale Y"),
        default=0.0,
        placement="advanced",
        doc=_NORMAL_MORE_DOC,
    )
    nz: float = param(
        title=_("Normale Z"),
        default=0.0,
        placement="advanced",
        doc=_NORMAL_MORE_DOC,
    )


@op_params
class BoxParams(PositionedPrimitiveParams):
    width: float = param(
        title=_("Breite"),
        default=40.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        # Das Beispiel hieß ``=breite*2``, und genau so tippt es niemand
        # zweimal: Der Auswerter antwortet „Unbekannter Name im Ausdruck.
        # Parameter werden mit @ geschrieben." Ein Beispiel, das der eigene
        # Auswerter ablehnt, ist schlechter als keines — es schickt jemanden
        # los, der die Hilfe gelesen hat.
        doc=_("Ausdehnung in X. Darf ein Ausdruck sein, etwa =@breite*2."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=30.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in Y."),
    )
    height: float = param(
        title=_("Höhe"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in Z, also nach oben."),
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="centre",
        choices=_ANCHORS,
        placement="advanced",
        doc=_("Mittig auf dem Ursprung oder mit der Ecke darauf."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_box",
    title=_("Quader anlegen"),
    category="primitive",
    params=BoxParams,
    consumes=0,
    produces=1,
    # „Erst in der Bausteinbibliothek suchen" stand hier und richtete sich an
    # das Sprachmodell — eine Regel aus rules.toml, gelandet in dem Feld, das
    # der Nutzer im Dialog liest. Wer auf „Quader anlegen" klickt, hat sich
    # entschieden; die Regel steht dort, wo sie hingehört, und gilt weiter.
    doc=_("Legt einen Quader an, mittig auf dem Druckbett oder auf einer Ecke."),
)
def create_box(ctx: OpContext) -> OpResult:
    params = cast(BoxParams, ctx.params)
    mesh = primitive_local_tool("create_box", params.as_dict(), ctx.quality)
    return OpResult(outputs=[_object(params.name or _("Quader"), mesh, params)])


@op_params
class CylinderParams(PositionedPrimitiveParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Der Zylinder steht auf dem Druckbett."),
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Höhe nach oben, von der Standfläche aus."),
    )
    segments: int = param(
        title=_("Segmente"),
        default=SEGMENTS,
        minimum=8,
        maximum=256,
        placement="advanced",
        doc=_("Mehr Segmente heißt runder und langsamer."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_cylinder",
    title=_("Zylinder anlegen"),
    category="primitive",
    params=CylinderParams,
    consumes=0,
    produces=1,
    doc=_("Legt einen Zylinder an, stehend auf dem Druckbett."),
)
def create_cylinder(ctx: OpContext) -> OpResult:
    params = cast(CylinderParams, ctx.params)
    mesh = primitive_local_tool("create_cylinder", params.as_dict(), ctx.quality)
    return OpResult(outputs=[_object(params.name or _("Zylinder"), mesh, params)])


@op_params
class ConeParams(PositionedPrimitiveParams):
    bottom_diameter: float = param(
        title=_("Unterer Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        doc=_("Durchmesser auf dem Druckbett. Null macht diese Seite zur Spitze."),
    )
    top_diameter: float = param(
        title=_("Oberer Durchmesser"),
        default=10.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        doc=_("Durchmesser an der Oberseite. Null macht diese Seite zur Spitze."),
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Höhe nach oben, von der Standfläche aus."),
    )
    segments: int = param(
        title=_("Segmente"),
        default=SEGMENTS,
        minimum=8,
        maximum=256,
        placement="advanced",
        doc=_("Mehr Segmente heißt runder und langsamer."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_cone",
    title=_("Kegel anlegen"),
    category="primitive",
    params=ConeParams,
    consumes=0,
    produces=1,
    doc=_("Legt einen Kegel oder Kegelstumpf stehend auf dem Druckbett an."),
)
def create_cone(ctx: OpContext) -> OpResult:
    params = cast(ConeParams, ctx.params)
    mesh = primitive_local_tool("create_cone", params.as_dict(), ctx.quality)
    fallback = (
        _("Kegel")
        if is_zero(params.bottom_diameter) or is_zero(params.top_diameter)
        else _("Kegelstumpf")
    )
    return OpResult(outputs=[_object(params.name or fallback, mesh, params)])


@op_params
class SphereParams(PositionedPrimitiveParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Die Kugel sitzt auf dem Druckbett auf."),
    )
    segments: int = param(
        title=_("Segmente"),
        default=32,
        minimum=8,
        maximum=128,
        placement="advanced",
        doc=_(
            "Mehr Segmente heißt runder und langsamer — ab 60 ist die Kugel so rund, wie sie wird."
        ),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_sphere",
    title=_("Kugel anlegen"),
    category="primitive",
    params=SphereParams,
    consumes=0,
    produces=1,
    doc=_("Legt eine Kugel an, aufsitzend auf dem Druckbett."),
)
def create_sphere(ctx: OpContext) -> OpResult:
    params = cast(SphereParams, ctx.params)
    mesh = primitive_local_tool("create_sphere", params.as_dict(), ctx.quality)
    return OpResult(outputs=[_object(params.name or _("Kugel"), mesh, params)])


@op_params
class TorusParams(PositionedPrimitiveParams):
    outer_diameter: float = param(
        title=_("Außendurchmesser"),
        default=40.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Gesamter Durchmesser von Außenkante zu Außenkante."),
    )
    tube_diameter: float = param(
        title=_("Schnurstärke"),
        default=8.0,
        unit="mm",
        minimum=0.1,
        maximum=500.0,
        doc=_("Durchmesser des runden Ringquerschnitts."),
    )
    segments: int = param(
        title=_("Segmente"),
        default=SEGMENTS,
        minimum=8,
        maximum=128,
        placement="advanced",
        doc=_("Mehr Segmente machen Ring und Querschnitt runder und verlangsamen die Berechnung."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_torus",
    title=_("Ring anlegen"),
    category="primitive",
    params=TorusParams,
    consumes=0,
    produces=1,
    doc=_("Legt einen geschlossenen runden Ring aufsitzend auf dem Druckbett an."),
)
def create_torus(ctx: OpContext) -> OpResult:
    params = cast(TorusParams, ctx.params)
    mesh = primitive_local_tool("create_torus", params.as_dict(), ctx.quality)
    return OpResult(outputs=[_object(params.name or _("Ring"), mesh, params)])


def placement_transform(params: PositionedPrimitiveParams) -> Transform:
    """Legt den lokalen Bezugspunkt und +Z in die gespeicherte freie Lage.

    Eine Matrix für beide Kerne: Das Netz legt sie auf seine Dreiecke, der
    exakte Kern gibt sie an ``brep.edit.transformed`` — so stehen Zwillinge
    nach dem Umschalten an derselben Stelle.
    """
    position = (float(params.x), float(params.y), float(params.z))
    direction = (float(params.nx), float(params.ny), float(params.nz))
    if not all(math.isfinite(value) for value in (*position, *direction)):
        raise ValidationError(
            "x",
            _(
                "Position und Richtung müssen aus endlichen Zahlen bestehen. "
                "Geben Sie gültige Werte ein."
            ),
            constraint="not_finite",
        )

    length = math.hypot(*direction)
    if not length:
        matrix = translation(position)
    else:
        normal = tuple(float(value / length) for value in direction)
        frame = frame_of(cast(Vec3, normal), position)
        matrix = np.eye(4)
        matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
        matrix[:3, 3] = position

    from app.core.geom.ops import as_transform

    return as_transform(matrix)


def _object(
    name: TranslatableText | str,
    mesh: MeshData,
    params: PositionedPrimitiveParams,
) -> SceneObject:
    """Ein frischer Körper mit dem einen Merkmal, das er ehrlich versprechen
    kann: seiner Oberseite.

    **Der Name darf übersetzbar sein, und der Rückfall ist es.** Wer eine
    Grundform ohne eigenen Namen anlegt, bekam bis zum 22.08.2026 „Quader",
    „Zylinder" oder „Kugel" — auch auf Englisch, Spanisch und in drei weiteren
    Sprachen. Das waren feste Zeichenketten mitten im Kern, und sie standen
    danach im Objektbaum, in der Kopfzeile und im Steckbrief.

    Ein :class:`TranslatableText` löst sich bei jeder Anzeige neu auf; da die
    Szene ohnehin aus dem Stapel gerechnet wird (§15.1) und Objektnamen nicht
    in der Projektdatei stehen, wandert er mit der Sprachumstellung mit — genau
    wie es soll. Was **nicht** mitwandern darf, ist der Exportdateiname, und
    dafür gibt es :func:`app.i18n.source_text`.
    """
    transform = placement_transform(params)
    placed = apply(mesh, np.asarray(transform))
    area, centre = top_face_of(mesh)
    features: dict[str, Feature] = (
        dict([face("face_top", area, centre, (0.0, 0.0, 1.0))]) if area > EPS_GEOM else {}
    )
    if features:
        from app.core.perceive.matching import moved_features

        features = moved_features(features, transform)
    return SceneObject(id="", name=name, mesh=placed, features=features)


def top_face_of(mesh: MeshData) -> tuple[float, Vec3]:
    """Die ebene Oberseite: ihre Fläche und ihre Mitte — oder Fläche null.

    **Gemessen an den Dreiecken, nicht am Hüllquader.** Vorher stand hier
    ``size[0] * size[1]``, also die Grundfläche des Quaders um den Körper. Beim
    Quader stimmt das; beim Zylinder Ø 20 meldete das Merkmal 400 mm² statt
    314, und bei der Kugel behauptete es eine ebene Deckfläche, die es
    überhaupt nicht gibt — ein Merkmal, auf das man klicken, an dem man
    ausrichten und gegen das man eine Passung prüfen kann, mit einer Zahl, die
    niemand nachgemessen hat.

    Gezählt wird, was oben liegt **und** nach oben schaut: Dreiecke, deren
    Normale innerhalb eines Grades senkrecht steht und die an der Oberkante des
    Körpers sitzen. Die Kugel hat davon keines und bekommt darum kein Merkmal —
    das ist die richtige Antwort und keine Lücke.
    """
    body = mesh.raw
    if not len(body.faces):
        return 0.0, (0.0, 0.0, 0.0)
    normals = np.asarray(body.face_normals, dtype=float)
    centres = np.asarray(body.triangles_center, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)
    top = float(mesh.bounds.maximum[2])
    # Die Dreiecksmitte einer ebenen Deckfläche liegt in ihrer Ebene; ein
    # Zehntelmillimeter Spiel deckt das Rechenrauschen einer Drehung ab.
    flat = (normals[:, 2] > FLAT_ENOUGH) & (centres[:, 2] > top - EPS_DISPLAY)
    if not flat.any():
        return 0.0, (0.0, 0.0, 0.0)
    area = float(areas[flat].sum())
    middle = (areas[flat, None] * centres[flat]).sum(axis=0) / area
    return area, (float(middle[0]), float(middle[1]), top)
