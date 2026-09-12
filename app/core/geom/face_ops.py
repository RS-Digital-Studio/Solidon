"""Fläche versetzen und Formschräge — **eine** Handlung, zwei Rechenkerne.

Dieselbe Bauart wie :mod:`app.core.geom.edge_ops`, und aus demselben Grund
(Entscheidung Robert, 10.09.2026: „alles soll immer bearbeitbar sein, egal ob
importiert Format egal und beim selbst zeichnen"): Der Rumpf fragt
``SceneObject.kind`` und wählt danach den Rechenweg. Beide Operationen trugen
bis dahin ein ``requires_kind="brep"`` und waren an jedem eingelesenen STL
ausgegraut.

**Und ``push_face`` hat dabei seinen Parameter gewechselt.** Es nahm eine
*Richtung* entgegen und bewegte jede Fläche, deren Normale dorthin zeigte — an
einer Treppe wanderten damit alle Stufen zugleich, gemessen 24000,0 mm³ statt
21000,0, während der Kunde eine einzelne angeklickt hatte (Befund Robert,
10.09.2026: „fläche versetzen ergibt doch keinen sinn oder wo ist das
sinnvoll?"). Gemeint ist die **gewählte** Fläche, und die benennt jetzt ein
Merkmalsverweis.

Die Richtungsfelder bleiben trotzdem stehen, auf der Rückseite des Dialogs: Aus
``nx/ny/nz`` lässt sich keine Fläche zurückrechnen, ohne die Szene zu kennen —
eine Migration kann das nicht (§16), und ein gespeicherter Schritt von gestern
soll dasselbe tun wie gestern.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from app.core.geom.faces import draft_vertical, face_normal, push_face
from app.core.geom.mesh import as_mesh_data
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Feature, OpContext, OpResult, SceneObject, Vec3
from app.core.units import DEGREE_UNIT
from app.i18n import _


@op_params
class PushFaceParams(BaseParams):
    distance: float = param(
        title=_("Weg"),
        default=2.0,
        unit="mm",
        doc=_(
            "Wie weit die Fläche wandert. Positiv nach außen, negativ hinein — "
            "dasselbe Werkzeug für beides."
        ),
    )
    face: str = param(
        title=_("Fläche"),
        default="",
        kind="feature",
        doc=_(
            "Welche Fläche wandert. Beim Anklicken steht sie hier; ohne Angabe "
            "gelten die Richtungsfelder, und dann wandert jede Fläche, die "
            "dorthin zeigt."
        ),
    )
    nx: float = param(
        title=_("Richtung X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Der ältere Weg, und nur für gespeicherte Schritte: Ohne gewählte "
            "Fläche wandert an einem exakten Körper jede, deren Normale hierhin "
            "zeigt — an einer Treppe also jede Stufe."
        ),
    )
    ny: float = param(
        title=_("Richtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Zweite Achse der Richtung — siehe Richtung X."),
    )
    nz: float = param(
        title=_("Richtung Z"),
        default=1.0,
        placement="advanced",
        doc=_("Dritte Achse der Richtung. Vorgabe ist nach oben."),
    )


@register_op(
    name="push_face",
    cache_version="2",
    title=_("Fläche versetzen"),
    category="shaping",
    params=PushFaceParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    doc=_(
        "Greift eine Fläche und verschiebt sie entlang ihrer Normalen; die "
        "Nachbarwände wachsen mit. Der Weg, eine Wand zu ändern, ohne die "
        "Operation zu suchen, die sie erzeugt hat — bei einem importierten "
        "Modell gibt es keine."
    ),
    caveat=_(
        "Nur an einer ebenen Fläche. Eine gewölbte hat keine eine Richtung, "
        "entlang der sie wandern könnte; dort hilft, das Merkmal über seine "
        "Maße zu ändern."
    ),
    shortcut="Q",
)
def push_face_op(ctx: OpContext) -> OpResult:
    from app.core.geom.prepare_ops import _reject_oversized

    params = cast(PushFaceParams, ctx.params)
    source = ctx.inputs[0]
    chosen = _chosen_face(source, params.face)
    _reject_oversized("distance", abs(params.distance), source.mesh, kind="length")

    if source.kind == "brep":
        return _on_a_solid(ctx, params, chosen)

    body = as_mesh_data(source.mesh)
    if chosen is None:
        raise _no_face()
    outcome = push_face(body, chosen, params.distance)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={})],
        solver=outcome.solver,
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in outcome.findings],
    )


@op_params
class DraftParams(BaseParams):
    angle: float = param(
        title=_("Winkel"),
        default=2.0,
        unit=DEGREE_UNIT,
        minimum=0.1,
        maximum=30.0,
        doc=_(
            "Um wie viel Grad die senkrechten Flächen angestellt werden. Die "
            "Standfläche behält ihr Maß, nach oben wird der Körper schmaler."
        ),
    )


@register_op(
    name="draft_faces",
    cache_version="2",
    title=_("Formschräge anstellen"),
    category="shaping",
    params=DraftParams,
    consumes=1,
    produces=1,
    doc=_(
        "Stellt alle senkrechten Flächen um einen Winkel an — zum Entformen, "
        "oder damit ein Stapelbehälter sich stapeln lässt."
    ),
)
def draft_faces(ctx: OpContext) -> OpResult:
    params = cast(DraftParams, ctx.params)
    source = ctx.inputs[0]

    if source.kind == "brep":
        from app.core.brep import profiles
        from app.core.brep.features import features_of
        from app.core.brep.ops import brep_input

        exact, body = brep_input(ctx)
        solid = profiles.draft_vertical(body, params.angle)
        return OpResult(
            outputs=[
                dataclasses.replace(exact, mesh=solid, kind="brep", features=features_of(solid))
            ]
        )

    outcome = draft_vertical(as_mesh_data(source.mesh), params.angle)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={})],
        solver=outcome.solver,
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in outcome.findings],
    )


def _chosen_face(source: SceneObject, name: str) -> Feature | None:
    """Das benannte Flächenmerkmal — oder ``None`` für den älteren Weg."""
    if not name:
        return None
    feature = source.features.get(name)
    if feature is None or feature.kind != "face":
        raise _no_face()
    return feature


def _no_face() -> Exception:
    """Der Satz, wenn keine Fläche benannt ist (Regel 17)."""
    from app.core.errors import GeometryError

    return GeometryError(
        detail=_("Für diese Handlung ist keine Fläche gewählt — klicken Sie eine im Bild an."),
    )


def _on_a_solid(ctx: OpContext, params: PushFaceParams, chosen: Feature | None) -> OpResult:
    """Der exakte Weg — träge geholt, weil OpenCASCADE optional ist (§36)."""
    from app.core.brep import profiles
    from app.core.brep.features import features_of
    from app.core.brep.ops import brep_input

    source, body = brep_input(ctx)
    direction = (params.nx, params.ny, params.nz)
    centre: Vec3 | None = None
    if chosen is not None:
        direction = face_normal(chosen)
        spot = chosen.params.get("centre")
        if spot is not None:
            measured = [float(value) for value in spot]
            centre = (measured[0], measured[1], measured[2])
    moved = profiles.push_faces(body, direction, params.distance, centre=centre)
    # ``features_of`` wie bei jeder anderen B-Rep-Op: Mit ``features={}``
    # hatte der Körper nach „Fläche versetzen" keine anklickbaren Flächen
    # mehr — „Auf dieser Fläche zeichnen", die exakte Bohrung und jede
    # Passung liefen ins Leere (Gesamtreview D-5).
    return OpResult(outputs=[dataclasses.replace(source, mesh=moved, features=features_of(moved))])


__all__ = ["DraftParams", "PushFaceParams", "draft_faces", "push_face_op"]
