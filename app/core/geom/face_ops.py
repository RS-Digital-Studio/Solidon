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

from app.core.geom.faces import (
    draft_walls,
    gone_face_error,
    push_face,
    pushed_features,
    tangent_faces_finding,
)
from app.core.geom.mesh import as_mesh_data
from app.core.registry import op_params, param, register_op
from app.core.types import (
    BaseParams,
    Feature,
    FeatureContinuation,
    FeatureRef,
    OpContext,
    OpResult,
    SceneObject,
)
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
            "Welche Fläche wandert. Beim Anklicken steht sie hier. Ohne Angabe "
            "gilt nur an einem exakten Körper der ältere Richtungsweg: Dann "
            "wandert jede Fläche, die in die angegebene Richtung zeigt."
        ),
    )
    nx: float = param(
        title=_("Richtung X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Der ältere Weg, und nur für gespeicherte Schritte: Ohne gewählte "
            "Fläche wandert an einem exakten Körper jede, die hierhin "
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
    # 5: Nachbarwände bleiben eine Fläche, und alle Namen reisen mit (23.09.2026).
    cache_version="5",
    title=_("Fläche versetzen"),
    category="shaping",
    params=PushFaceParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    doc=_(
        "Greift eine Fläche und verschiebt sie senkrecht zu sich selbst; die "
        "Nachbarwände wachsen mit. Der Weg, eine Wand zu ändern, ohne die "
        "Operation zu suchen, die sie erzeugt hat — bei einem importierten "
        "Modell gibt es keine."
    ),
    caveat=_(
        "An einer gewölbten Fläche, denn sie hat keine einzelne Richtung. Dort das Merkmal über "
        "seine Maße ändern."
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
    outcome = push_face(body, chosen, params.distance, quality=ctx.quality, cancelled=ctx.cancelled)
    # Die Merkmale reisen mit, die versetzte Fläche und ihre gewachsenen
    # Nachbarn an ihrem neuen Ort (:func:`faces.pushed_features`) — die
    # Auswertung findet sie dort wieder, statt sie zu verwaisen.
    carried = {
        name: dataclasses.replace(feature, face_indices=(), surface_patches=())
        for name, feature in source.features.items()
    }
    carried.update(pushed_features(body, source.features, chosen, params.distance))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features=carried)],
        solver=outcome.solver,
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in outcome.findings],
    )


#: Die Entformungsrichtungen — die sechs Achsen am Druckbett. In die gewählte
#: hinein wird das Teil schmaler (P6.4).
PULL_DIRECTIONS: dict[str, tuple[float, float, float]] = {
    "pull_up": (0.0, 0.0, 1.0),
    "pull_down": (0.0, 0.0, -1.0),
    "pull_right": (1.0, 0.0, 0.0),
    "pull_left": (-1.0, 0.0, 0.0),
    "pull_back": (0.0, 1.0, 0.0),
    "pull_front": (0.0, -1.0, 0.0),
}

#: Wo die neutrale Ebene liegt: am Anfang des Teils in Entformungsrichtung, an
#: ihrem Ende oder auf einer Höhe dazwischen.
NEUTRAL_PLANES: tuple[str, ...] = ("neutral_start", "neutral_end", "neutral_height")


@op_params
class DraftParams(BaseParams):
    angle: float = param(
        title=_("Winkel"),
        default=2.0,
        unit=DEGREE_UNIT,
        minimum=0.1,
        maximum=30.0,
        doc=_(
            "Um wie viel Grad die Flächen angestellt werden. An der neutralen Ebene "
            "behält das Teil sein Maß, in Entformungsrichtung wird es schmaler."
        ),
    )
    # **P6.4 — Formschräge an gewählten Flächen.** Ohne Auswahl, nach oben und
    # neutral unten ist es das Anstellen aller senkrechten Wände — die
    # Bedeutung jedes gespeicherten Schritts.
    faces: tuple[str, ...] = param(
        title=_("Flächen"),
        default=(),
        kind="features",
        doc=_(
            "Welche Flächen angestellt werden. Ohne Auswahl alle Wände, die in "
            "Entformungsrichtung stehen — bei „nach oben“ alle senkrechten."
        ),
    )
    direction: str = param(
        title=_("Entformungsrichtung"),
        default="pull_up",
        choices=tuple(PULL_DIRECTIONS),
        doc=_(
            "In welche Richtung das Teil schmaler wird — die Richtung, in die die Form "
            "abgezogen wird."
        ),
    )
    neutral: str = param(
        title=_("Neutrale Ebene"),
        default="neutral_start",
        choices=NEUTRAL_PLANES,
        placement="advanced",
        doc=_(
            "Wo das Teil sein Maß behält: am Anfang der Entformungsrichtung — bei „nach "
            "oben“ unten —, an ihrem Ende oder auf einer gewählten Höhe."
        ),
    )
    neutral_height: float = param(
        title=_("Höhe der neutralen Ebene"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_(
            "Wie weit die neutrale Ebene vom Anfang des Teils entfernt liegt, gemessen in "
            "Entformungsrichtung. Darunter wird das Teil breiter, darüber schmaler."
        ),
        depends_on=("neutral", ("neutral_height",)),
    )


@register_op(
    name="draft_faces",
    # 5: gewählte Flächen, Richtung und neutrale Ebene (P6.4); am Netz treffen
    # die angestellten Wände sich an Innenecken wie am exakten Körper, und ein
    # exakter Körper, den die Prüfung ablehnt, wird abgesagt (23.09.2026).
    cache_version="5",
    title=_("Formschräge anstellen"),
    category="shaping",
    params=DraftParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    also_on_body=True,
    doc=_(
        "Stellt gewählte Flächen um einen Winkel an, oder alle Wände in "
        "Entformungsrichtung — zum Entformen, oder damit ein Stapelbehälter sich "
        "stapeln lässt."
    ),
    # RM-230: Schließt eine liegende Rundung ohne Knick an eine Wand an, sagen
    # beide Kerne vor der Rechnung ab (``faces.DRAFT_BESIDE_A_ROUND``).
    caveat=_(
        "Wenn an den Wänden unten oder oben Rundungen liegen. Dann nur Wände ohne Rundung wählen."
    ),
)
def draft_faces(ctx: OpContext) -> OpResult:
    params = cast(DraftParams, ctx.params)
    source = ctx.inputs[0]
    pull = PULL_DIRECTIONS[params.direction]
    chosen = [_drafted_face(source, name) for name in params.faces]
    level = _neutral_level(source, pull, params)

    if source.kind == "brep":
        from app.core.brep import profiles
        from app.core.brep.features import features_of
        from app.core.brep.ops import brep_input

        exact, body = brep_input(ctx)
        selected: tuple[int, ...] | None = None
        if chosen:
            ctx.cancelled.raise_if_cancelled()
            selected = tuple(
                sorted(
                    {
                        index
                        for feature in chosen
                        for index in body.complete_faces_of_triangles(feature.face_indices)
                    }
                )
            )
        solid, added = profiles.draft_faces(
            body,
            params.angle,
            direction=pull,
            neutral=level,
            selected_faces=selected,
            cancelled=ctx.cancelled,
        )
        return OpResult(
            outputs=[
                dataclasses.replace(
                    exact,
                    mesh=solid,
                    kind="brep",
                    features=features_of(solid, cancelled=ctx.cancelled),
                )
            ],
            findings=(
                [dataclasses.replace(tangent_faces_finding(added), object_id=source.id)]
                if chosen and added
                else []
            ),
        )

    outcome = draft_walls(
        as_mesh_data(source.mesh),
        params.angle,
        walls=chosen or None,
        direction=pull,
        neutral=level,
        quality=ctx.quality,
        cancelled=ctx.cancelled,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={})],
        solver=outcome.solver,
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in outcome.findings],
    )


def _drafted_face(source: SceneObject, name: str) -> Feature:
    """Ein gewähltes Flächenmerkmal — oder der Satz, warum es keines ist."""
    feature = source.features.get(name)
    if feature is None:
        raise gone_face_error() if name else _no_face()
    return feature


def _neutral_level(
    source: SceneObject, pull: tuple[float, float, float], params: DraftParams
) -> float:
    """Die Lage der neutralen Ebene entlang der Entformungsrichtung.

    Der Anfang ist die kleinste Lage des Körpers entlang der Richtung, das
    Ende die größte; eine Höhe zählt vom Anfang aus. Gemessen am Hüllquader,
    denn die Richtung ist eine Achse.
    """
    bounds = source.mesh.bounds
    corners = [bounds.minimum, bounds.maximum]
    along = [sum(a * b for a, b in zip(corner, pull, strict=True)) for corner in corners]
    start, end = min(along), max(along)
    if params.neutral == "neutral_end":
        return float(end)
    if params.neutral == "neutral_height":
        return float(start + params.neutral_height)
    return float(start)


def _chosen_face(source: SceneObject, name: str) -> Feature | None:
    """Das benannte Flächenmerkmal — oder ``None`` für den älteren Weg."""
    if not name:
        return None
    feature = source.features.get(name)
    if feature is None:
        raise gone_face_error()
    if feature.kind != "face":
        raise _no_face()
    return feature


def _no_face() -> Exception:
    """Der Satz, wenn keine Fläche benannt ist (Regel 17)."""
    from app.core.errors import CANCEL, CHANGE_SELECTION, GeometryError

    return GeometryError(
        detail=_("Für diese Handlung ist keine Fläche gewählt — klicken Sie eine im Bild an."),
        suggestions=(CHANGE_SELECTION, CANCEL),
    )


def _on_a_solid(ctx: OpContext, params: PushFaceParams, chosen: Feature | None) -> OpResult:
    """Der exakte Weg — träge geholt, weil OpenCASCADE optional ist (§36)."""
    from app.core.brep import profiles
    from app.core.brep.features import features_of
    from app.core.brep.ops import brep_input

    source, body = brep_input(ctx)
    direction = (params.nx, params.ny, params.nz)
    selected_faces: tuple[int, ...] | None = None
    if chosen is not None:
        ctx.cancelled.raise_if_cancelled()
        selected_faces = body.complete_faces_of_triangles(chosen.face_indices)
        ctx.cancelled.raise_if_cancelled()
    moved = profiles.push_faces(
        body, direction, params.distance, selected_faces=selected_faces, cancelled=ctx.cancelled
    )
    if chosen is None:
        # ``features_of`` wie bei jeder anderen B-Rep-Op: Mit ``features={}``
        # hatte der Körper nach „Fläche versetzen" keine anklickbaren Flächen
        # mehr — „Auf dieser Fläche zeichnen", die exakte Bohrung und jede
        # Passung liefen ins Leere (Gesamtreview D-5).
        return OpResult(
            outputs=[
                dataclasses.replace(
                    source, mesh=moved, features=features_of(moved, cancelled=ctx.cancelled)
                )
            ]
        )
    # **Mit der gewählten Fläche sagt die Operation, wo sie jetzt liegt** —
    # und wo ihre Nachbarn gewachsen sind (``faces.pushed_features``). Die
    # native Erkennung nummeriert frisch; ohne diese Erwartung trug
    # ``face_3`` vorher die Oberseite und danach einen Streifen der
    # Vorderseite (gemessen 23.09.2026). Belegt wird wie bei den
    # Hohlraumhandlungen (``_exact_features_after``).
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare_ops import _exact_features_after

    expected = pushed_features(as_mesh_data(body), source.features, chosen, params.distance)
    features, continued, _lost = _exact_features_after(
        source, moved, expected=list(expected.values()), cancelled=ctx.cancelled
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=moved, kind="brep", features=features)],
        feature_continuations=(
            tuple(
                FeatureContinuation(FeatureRef(source.id, old_id), new_id)
                for old_id, new_id in continued
            ),
        ),
    )


__all__ = [
    "NEUTRAL_PLANES",
    "PULL_DIRECTIONS",
    "DraftParams",
    "PushFaceParams",
    "draft_faces",
    "push_face_op",
]
