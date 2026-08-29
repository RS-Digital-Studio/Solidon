"""Primitive (Bauplan §25, Kategorie „Boolesch").

Säule A beginnt hier: ohne einen Weg, einen ersten Körper in eine leere Szene
zu setzen, hat „bau mir eine Halterung" nichts, worauf es stehen könnte. Drei
Primitive genügen dafür — alles andere ist eine Boolesche Op daraus und ein
Baustein aus der Bibliothek, und genau diese Reihenfolge verlangt die
Regelsammlung (§39: Bausteine vor Primitiven).

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

from typing import cast

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, translation
from app.core.knowledge.parts.build import face
from app.core.knowledge.parts.shapes import SEGMENTS, box, cylinder
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.types import (
    BaseParams,
    Feature,
    OpContext,
    OpResult,
    SceneObject,
    Vec3,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM
from app.i18n import TranslatableText, _

_ANCHORS = ("centre", "corner")

#: Ab wann eine Normale als senkrecht gilt (:func:`top_face_of`). Der Kosinus
#: von einem Grad — enger wäre eine Frage an die Rechengenauigkeit, weiter
#: zählte die oberste Segmentreihe einer Kugel als Deckfläche.
FLAT_ENOUGH = 0.9998


@op_params
class BoxParams(BaseParams):
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
    doc=_("Legt einen Quader an, mittig auf Z = 0 oder auf einer Ecke."),
)
def create_box(ctx: OpContext) -> OpResult:
    params = cast(BoxParams, ctx.params)
    mesh = box(params.width, params.depth, params.height)
    if params.anchor == "corner":
        mesh = apply(mesh, translation((params.width / 2.0, params.depth / 2.0, 0.0)))
    return OpResult(outputs=[_object(params.name or _("Quader"), mesh)])


@op_params
class CylinderParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Der Zylinder steht auf Z = 0."),
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
    doc=_("Legt einen Zylinder an, stehend auf Z = 0."),
)
def create_cylinder(ctx: OpContext) -> OpResult:
    params = cast(CylinderParams, ctx.params)
    mesh = cylinder(params.diameter, params.height, segments=params.segments)
    return OpResult(outputs=[_object(params.name or _("Zylinder"), mesh)])


@op_params
class SphereParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Die Kugel sitzt auf Z = 0 auf."),
    )
    segments: int = param(
        title=_("Segmente"),
        default=32,
        minimum=8,
        maximum=128,
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
    name="create_sphere",
    title=_("Kugel anlegen"),
    category="primitive",
    params=SphereParams,
    consumes=0,
    produces=1,
    doc=_("Legt eine Kugel an, aufsitzend auf Z = 0."),
)
def create_sphere(ctx: OpContext) -> OpResult:
    import trimesh

    params = cast(SphereParams, ctx.params)
    body = trimesh.creation.icosphere(
        subdivisions=max(1, params.segments // 12), radius=params.diameter / 2.0
    )
    body.apply_translation([0.0, 0.0, params.diameter / 2.0])
    mesh = MeshData.of(body)
    return OpResult(outputs=[_object(params.name or _("Kugel"), mesh)])


def _object(name: TranslatableText | str, mesh: MeshData) -> SceneObject:
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
    area, centre = top_face_of(mesh)
    features: dict[str, Feature] = (
        dict([face("face_top", area, centre, (0.0, 0.0, 1.0))]) if area > EPS_GEOM else {}
    )
    return SceneObject(id="", name=name, mesh=mesh, features=features)


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
