"""Primitive und OpenSCAD-Körper (Bauplan §25, Kategorie „Boolesch").

Säule A beginnt hier: ohne einen Weg, einen ersten Körper in eine leere Szene
zu setzen, hat „bau mir eine Halterung" nichts, worauf es stehen könnte. Drei
Primitive genügen dafür — alles andere ist eine Boolesche Op daraus und ein
Baustein aus der Bibliothek, und genau diese Reihenfolge verlangt die
Regelsammlung (§39: Bausteine vor Primitiven).

Der OpenSCAD-Körper ist die Rückfallebene (§24.1) und bleibt optional: der
Quelltext wird vor dem Lauf geprüft (§32), und ohne Installation sagt die
Operation das, statt auf halbem Weg zu scheitern.
"""

from __future__ import annotations

from typing import cast

import numpy as np

from app.core.backends import openscad
from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.repair import merge_vertices
from app.core.geom.transform import apply, translation
from app.core.knowledge.parts.build import face
from app.core.knowledge.parts.shapes import SEGMENTS, box, cylinder
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.types import (
    BaseParams,
    Feature,
    Finding,
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
    return OpResult(outputs=[_object(params.name or _("Quader"), mesh, params.height)])


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
    return OpResult(outputs=[_object(params.name or _("Zylinder"), mesh, params.height)])


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
    return OpResult(outputs=[_object(params.name or _("Kugel"), mesh, params.diameter)])


@op_params
class ScadParams(BaseParams):
    source: str = param(
        title=_("Quelltext"),
        default="",
        doc=_("OpenSCAD-Quelltext. Wird vor dem Lauf geprüft."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_from_scad",
    title=_("OpenSCAD-Teil anheften"),
    category="primitive",
    params=ScadParams,
    consumes=0,
    produces=1,
    doc=_(
        "Baut einen Körper aus OpenSCAD-Quelltext. Rückfallebene für Formen, für die "
        "es keinen Baustein gibt — braucht eine Installation und wird vorher geprüft."
    ),
    caveat=_(
        "Die letzte Wahl, nicht die erste. Was ein Baustein oder der exakte Kern kann, "
        "wird nicht als Quelltext geschrieben — das Ergebnis ist genauer, bleibt im "
        "Verlauf änderbar und braucht kein installiertes OpenSCAD."
    ),
)
def create_from_scad(ctx: OpContext) -> OpResult:
    """§24.1: die Rückfallebene. Die Prüfung aus §32 läuft, bevor irgendetwas
    ausgeführt wird.
    """
    params = cast(ScadParams, ctx.params)
    if not params.source.strip():
        raise ValidationError(
            field="source",
            detail=_("Ohne Quelltext gibt es nichts anzulegen."),
            constraint="empty",
        )
    result = openscad.render(params.source)
    # OpenSCAD schreibt STL, und STL kennt keine gemeinsamen Punkte: jedes
    # Dreieck bringt seine eigenen drei mit. Über ``load`` verschweißt die
    # Eingangsstufe sie (§17.1) und sagt es; dieser Weg ging daran vorbei, und
    # ein Ø-12-Zylinder kam als 252 lose Dreiecke in der Szene an. Bemerkt hat
    # das erst die nächste boolesche Operation, die ihn retten musste.
    mesh, removed = merge_vertices(read_mesh(result.stl, ".stl"))
    # **Kein `_()` hier: „OpenSCAD" ist ein Eigenname.** Er heißt in jeder
    # Sprache so, und ein Katalogeintrag, der ihn auf sich selbst abbildet,
    # ist eine Zeile, die fünfmal gepflegt werden muss und nie etwas tut.
    entry = _object(params.name or "OpenSCAD", mesh, float(mesh.bounds.size[2]))
    findings = list(result.findings)
    if removed:
        findings.append(
            Finding(
                code="ingest.welded",
                severity="info",
                message=_("Doppelte Punkte wurden verschweißt."),
                values={"removed": removed},
            )
        )
    return OpResult(outputs=[entry], findings=findings)


def _object(name: TranslatableText | str, mesh: MeshData, height: float) -> SceneObject:
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
