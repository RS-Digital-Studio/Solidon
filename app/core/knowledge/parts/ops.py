"""Jeder Baustein als Operation (Bauplan §24.1, §10).

Ein Baustein wird einmal deklariert und wird aus dieser Deklaration eine
Operation — Menüeintrag, Dialog, Kommandozeile, Agentenwerkzeug und
Katalogeintrag folgen alle daraus (Leitprinzip 3). Nichts hier ist je Baustein
geschrieben; einen Baustein zur Bibliothek hinzuzufügen fügt ihn überall hinzu.

Die Operation nimmt die eigenen Parameter des Bausteins plus den Ort, an den er
gehört: Position, Achse, Winkel. Ein abziehender Baustein wird aus dem Körper
geschnitten, ein hinzufügender mit ihm vereint, und welcher von beiden es ist,
kommt aus der Deklaration — der Nutzer muss nicht wissen, dass eine
Mutternfalle ein Loch ist und eine Rippe nicht.

Das Spiel, das eine Passung braucht, steht auch nicht im Baustein. Ein Baustein
deklariert ``play`` und lässt es auf null; hier wird es aus dem kalibrierten
Materialprofil gefüllt (AGENTS.md Regel 7) — und genau das lässt eine spätere
Kalibrierung alte Projekte erreichen.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app.core.errors import Action, AppError
from app.core.geom.boolean import BooleanKind, boolean, without_effect
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import BOOLEAN_OVERLAP
from app.core.geom.transform import rotation, translation
from app.core.knowledge.parts.registry import PARTS, PartRegistry, PartSpec
from app.core.log import get_logger
from app.core.registry import Registry, op_params, param, register_op
from app.core.types import (
    BaseParams,
    Feature,
    OpContext,
    OpResult,
    PartResult,
    Profile,
    SceneObject,
    Vec3,
)
from app.core.units import DEGREE_UNIT
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Name des Parameters, den ein Baustein für die Toleranz benutzt, die er
#: braucht. Null heißt: aus dem Profil füllen.
PLAY_FIELD = "play"

#: Ortsangaben, die jede Baustein-Operation zusätzlich zu ihren eigenen bekommt.
#: Die Erklärungen stehen hier und nicht bei den achtzehn Bausteinen: dieselbe
#: Zahl bedeutet überall dasselbe, und einmal geschrieben kann sie nicht an
#: siebzehn Stellen anders lauten.
#:
#: **Die drei Koordinaten liegen hinten** (Konzept P15 §5): sie sind bei jedem
#: Baustein dieselben und sagen nichts über ihn — vorn standen damit drei
#: Felder, die vom eigentlichen Maß ablenken. Wer eine Fläche angeklickt hat,
#: bekommt sie ohnehin eingetragen; wer den Baustein danach bewegt, nimmt das
#: Gizmo (§18.11). ``at_feature`` bleibt vorn, denn das ist die fachliche
#: Frage „wohin" und keine abgelesene Zahl.
_PLACEMENT: tuple[tuple[str, str, Any], ...] = (
    (
        "x",
        "float",
        param(
            title=_("Position X"),
            default=0.0,
            unit="mm",
            placement="advanced",
            doc=_(
                "Wo der Baustein sitzt, gemessen im Koordinatensystem des Objekts. "
                "Eine angeklickte Fläche trägt den Wert selbst ein."
            ),
        ),
    ),
    (
        "y",
        "float",
        param(
            title=_("Position Y"),
            default=0.0,
            unit="mm",
            placement="advanced",
            doc=_("Zweite Achse der Position — siehe Position X."),
        ),
    ),
    (
        "z",
        "float",
        param(
            title=_("Position Z"),
            default=0.0,
            unit="mm",
            placement="advanced",
            doc=_("Höhe über der Grundfläche des Objekts."),
        ),
    ),
    (
        "axis",
        "str",
        param(
            title=_("Achse"),
            default="z",
            choices=("x", "y", "z"),
            placement="advanced",
            doc=_("Richtung, in die der Baustein zeigt."),
        ),
    ),
    (
        "angle",
        "float",
        param(
            title=_("Drehung"),
            default=0.0,
            unit=DEGREE_UNIT,
            minimum=-360.0,
            maximum=360.0,
            placement="advanced",
            doc=_(
                "Dreht den Baustein um seine eigene Achse. Wichtig bei allem, was "
                "nicht rund ist — eine Mutternfalle muss zur Wand passen, durch die "
                "die Mutter eingeschoben wird."
            ),
        ),
    ),
    (
        "at_feature",
        "str",
        param(
            title=_("An Merkmal"),
            kind="feature",
            default="",
            doc=_(
                "Name eines erkannten Merkmals, zum Beispiel hole_1. Dann zählt "
                "dessen Ort, und die Position darüber wird als Versatz gerechnet."
            ),
        ),
    ),
)


def op_name(part: str) -> str:
    """``screw_hole`` wird ``insert_screw_hole`` — ein Namensraum, keine
    Kollisionen.
    """
    return f"insert_{part}"


def build_params(spec: PartSpec) -> type[BaseParams]:
    """Die Parameter des Bausteins plus den Ort, an den er gehört, als ein
    Schema (§10).
    """
    namespace: dict[str, Any] = {"__annotations__": {}}
    for entry in spec.params.fields():
        namespace["__annotations__"][entry.name] = entry.type
        namespace[entry.name] = (
            dataclasses.field(default=entry.default, metadata=entry.metadata)
            if entry.default is not dataclasses.MISSING
            else dataclasses.field(metadata=entry.metadata)
        )
    for name, annotation, declaration in _PLACEMENT:
        namespace["__annotations__"][name] = annotation
        namespace[name] = declaration

    made = type(f"{_camel(spec.name)}OpParams", (BaseParams,), namespace)
    return op_params(made)


def _camel(name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))


def register_all(
    parts: PartRegistry | None = None, registry: Registry | None = None
) -> tuple[str, ...]:
    """Deklariert eine Operation je Baustein. Gibt die Operationsnamen zurück."""
    source = parts or PARTS
    made: list[str] = []
    for spec in source.all():
        name = op_name(spec.name)
        target = registry or None
        if (target or _default_registry()).has(name):
            continue
        _register_one(spec, build_params(spec), registry)
        made.append(name)
    _log.info("registered %d part operations", len(made))
    return tuple(made)


def _default_registry() -> Registry:
    from app.core.registry import REGISTRY

    return REGISTRY


def _register_one(spec: PartSpec, params: type[BaseParams], registry: Registry | None) -> None:
    title = _title_for(spec)

    @register_op(
        name=op_name(spec.name),
        title=title,
        category="parts",
        params=params,
        consumes=1,
        produces=1,
        applies_to=["face"] if spec.subtractive else [],
        touches_features=True,
        doc=spec.doc or title,
        registry=registry,
    )
    def run(ctx: OpContext, _spec: PartSpec = spec) -> OpResult:
        return insert(ctx, _spec)


def _title_for(spec: PartSpec) -> TranslatableText | str:
    return spec.title


def insert(ctx: OpContext, spec: PartSpec) -> OpResult:
    """Baut den Baustein, setzt ihn an seinen Platz und vereint oder schneidet."""
    source = ctx.inputs[0]
    values = _part_values(spec, ctx.params, ctx.profile)
    produced = spec.fn(spec.params(**values))

    anchor = _anchor(source, ctx.params)
    # Ein aufgesetzter Baustein sinkt ein Hundertstel ein. Zwei Volumen, die
    # sich nur in einer Fläche berühren, sind das eine, woran eine boolesche
    # Operation zuverlässig scheitert (§39) — die Rastnase steht mit 6 mal 1 mm
    # auf, und heraus kam ein wasserdichtes Netz aus zwei Komponenten, beim
    # nächsten Bohren drei. Die breiteren Bausteine fielen nie auf, weil
    # manifold sie verschmolz; die Frage ist für alle dieselbe und steht darum
    # hier und nicht in jedem einzelnen. Ein subtraktiver braucht es nicht: sein
    # Werkzeug reicht ohnehin über die Fläche hinaus.
    sink = 0.0 if spec.subtractive else BOOLEAN_OVERLAP
    placed = _place(as_mesh_data(produced.mesh), ctx.params, anchor, sink)
    body = as_mesh_data(source.mesh)
    kind: BooleanKind = "difference" if spec.subtractive else "union"
    outcome = boolean(kind, [body, placed], quality=ctx.quality)

    features = dict(source.features)
    features.update(_placed_features(produced, spec, ctx.params, anchor, sink))

    # Ein Baustein, der den Körper nicht getroffen hat, sagt das. Hier und
    # nicht in jedem einzelnen: die Frage ist für alle dieselbe, und die
    # Antwort steht im Volumen (§2.7).
    nothing = without_effect(body, as_mesh_data(outcome.mesh), kind)

    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features=features)],
        solver=outcome.solver,
        findings=[*outcome.findings, *produced.findings, *([nothing] if nothing else [])],
    )


def _part_values(spec: PartSpec, params: Any, profile: Profile | None) -> dict[str, Any]:
    """Die eigenen Parameter des Bausteins aus denen der Operation, mit dem
    eingefüllten Spiel.
    """
    wanted = {entry.name for entry in spec.params.fields()}
    values = {name: getattr(params, name) for name in wanted if hasattr(params, name)}
    if PLAY_FIELD in values and not values[PLAY_FIELD] and profile is not None:
        # Regel 7: die Toleranz ist ein Verweis ins Materialprofil, nie eine Zahl
        # in der Datei.
        values[PLAY_FIELD] = profile.material.clearance
    return values


def _anchor(source: SceneObject, params: Any) -> Vec3:
    """Wohin der Baustein kommt: an ein benanntes Merkmal, oder an den
    Ursprung (§25).

    §25 verlangt „einen Baustein an ein erkanntes Merkmal setzen". Der Name
    genügt dafür — es ist derselbe Name, den der Nutzer angeklickt und über den
    der Agent gesprochen hat (§18.5), und ein Merkmal, das nicht da ist, sagt
    das, statt den Baustein irgendwo Plausiblem abzusetzen.
    """
    name = str(getattr(params, "at_feature", "") or "")
    if not name:
        return (0.0, 0.0, 0.0)

    feature = source.features.get(name)
    if feature is None:
        raise AppError(
            _("Dieses Merkmal gibt es an diesem Objekt nicht."),
            detail=f"unknown feature {name!r}",
            values={"feature": name, "known": ", ".join(sorted(source.features))},
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie das Merkmal im Objektbaum aus.")),
            ),
        )
    centre = feature.params.get("centre", (0.0, 0.0, 0.0))
    return (float(centre[0]), float(centre[1]), float(centre[2]))


def _place(
    mesh: MeshData, params: Any, anchor: Vec3 = (0.0, 0.0, 0.0), sink: float = 0.0
) -> MeshData:
    from app.core.geom.transform import apply

    axis = getattr(params, "axis", "z")
    angle = float(getattr(params, "angle", 0.0))
    body = mesh
    if sink:
        # In seinem **eigenen** System, vor jeder Drehung: dort zeigt +Z aus
        # dem Träger heraus, also geht -Z hinein, gleich an welche Achse er
        # danach gelegt wird.
        body = apply(body, translation((0.0, 0.0, -sink)))
    if axis != "z":
        # Den Baustein so umlegen, dass sein eigenes +Z entlang der gewählten Achse
        # zeigt.
        body = apply(body, rotation("y", 90.0) if axis == "x" else rotation("x", -90.0))
    if angle:
        body = apply(body, rotation(axis, angle))  # type: ignore[arg-type]
    offset = (
        float(getattr(params, "x", 0.0)) + anchor[0],
        float(getattr(params, "y", 0.0)) + anchor[1],
        float(getattr(params, "z", 0.0)) + anchor[2],
    )
    return apply(body, translation(offset))


def _placed_features(
    produced: PartResult,
    spec: PartSpec,
    params: Any,
    anchor: Vec3 = (0.0, 0.0, 0.0),
    sink: float = 0.0,
) -> dict[str, Feature]:
    """Die Merkmale des Bausteins, mitbewegt und so benannt, dass sie nicht
    kollidieren können.

    ``bore_1`` des dritten eingefügten Bausteins überschriebe sonst das des
    ersten. Bausteinname und Position machen es eindeutig, ohne einen Zähler zu
    erfinden, den niemand vorhersagen kann.
    """
    from app.core.perceive.matching import moved_features

    matrix = _matrix(params, anchor, sink)
    moved = moved_features(dict(produced.features), matrix)
    return {
        f"{spec.name}_{name}": dataclasses.replace(feature, id=f"{spec.name}_{name}")
        for name, feature in moved.items()
    }


def _matrix(params: Any, anchor: Vec3 = (0.0, 0.0, 0.0), sink: float = 0.0) -> Any:
    import numpy as np

    from app.core.geom.ops import as_transform

    axis = getattr(params, "axis", "z")
    angle = float(getattr(params, "angle", 0.0))
    matrix = np.eye(4)
    if sink:
        matrix = translation((0.0, 0.0, -sink)) @ matrix
    if axis != "z":
        matrix = (rotation("y", 90.0) if axis == "x" else rotation("x", -90.0)) @ matrix
    if angle:
        matrix = rotation(axis, angle) @ matrix  # type: ignore[arg-type]
    matrix = (
        translation(
            (
                float(getattr(params, "x", 0.0)) + anchor[0],
                float(getattr(params, "y", 0.0)) + anchor[1],
                float(getattr(params, "z", 0.0)) + anchor[2],
            )
        )
        @ matrix
    )
    return as_transform(matrix)
