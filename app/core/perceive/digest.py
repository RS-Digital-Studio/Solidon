"""The scene digest for the agent (Bauplan §23).

What the agent gets to see, in words: objects with their dimensions, features
with their names, the parameters, the current selection, the stack in short
form. The agent refers to these names and never to coordinates (Leitprinzip 5),
so this text is the vocabulary the whole conversation runs on.

It is written for reading. A wall of JSON would carry the same facts and be
harder to reason about — for the model as much as for the person checking what
the model was told.
"""

from __future__ import annotations

from app.core.types import Document, Feature, ObjectId, Scene, SceneObject
from app.core.units import format_length, round_display
from app.i18n import tr


def digest(
    scene: Scene,
    document: Document | None = None,
    selection: tuple[ObjectId, str] | None = None,
) -> str:
    """The whole scene in the form §23 describes."""
    lines: list[str] = [_scene_line(scene)]

    if scene.parameters:
        values = " · ".join(
            f"{name}={round_display(parameter.value):g} {parameter.unit}"
            for name, parameter in scene.parameters.items()
        )
        lines.append(f"{tr('Parameter')}: {values}")

    if selection is not None:
        object_id, feature_id = selection
        lines.append(f"{tr('Auswahl')}: {object_id}" + (f" · {feature_id}" if feature_id else ""))

    for object_id, entry in scene.objects.items():
        lines.extend(_object_lines(object_id, entry))

    lines.extend(_finding_lines(scene))
    if document is not None:
        lines.extend(_stack_lines(document))
    return "\n".join(lines)


def _scene_line(scene: Scene) -> str:
    profile = scene.profile
    printer = profile.printer.id if profile else "-"
    material = profile.material.id if profile else "-"
    state = ""
    if profile is not None:
        state = f" ({tr('kalibriert') if profile.material.calibrated else tr('Startwert')})"
    return (
        f"{tr('Szene')}: {len(scene.objects)} {tr('Objekte')}, "
        f"{tr('Drucker')} {printer}, {tr('Material')} {material}{state}"
    )


def _object_lines(object_id: ObjectId, entry: SceneObject) -> list[str]:
    size = entry.mesh.bounds.size
    closed = tr("geschlossen") if entry.mesh.is_watertight else tr("offen")
    on_bed = tr("auf Bett") if abs(entry.mesh.bounds.minimum[2]) < 0.05 else ""
    facts = [
        f"{size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm",
        f"{entry.mesh.volume / 1000.0:.1f} cm³",
        closed,
    ]
    if on_bed:
        facts.append(on_bed)
    if entry.material:
        # Only when it differs from the project's — the scene line already says
        # that one, and repeating it on every body would be noise (§26.1).
        facts.append(entry.material)

    lines = [f'{object_id}  "{entry.name}"  ' + ", ".join(facts)]
    for feature_id, feature in entry.features.items():
        lines.append("  " + _feature_line(feature_id, feature))
    return lines


def _feature_line(feature_id: str, feature: Feature) -> str:
    """One feature, with where it is.

    The position was missing here, and it made the digest a description the agent
    could not act on: it read the diameter and the axis of a bore and had nothing
    to say where the bore was. For "put a part at hole_1" the name suffices, and
    for "drill beside it" it does not. The surface has known the position since it
    can be clicked (§18.5) — the agent sees only this text (§26.1).
    """
    params = feature.params
    at = _place(params.get("centre"))
    if feature.kind == "hole":
        axis = _axis_name(params.get("axis", (0.0, 0.0, 1.0)))
        through = tr("Durchgang") if params.get("through") else tr("Sackloch")
        return (
            f"{feature_id}  Ø {format_length(float(params.get('diameter', 0.0)))}, "
            f"{tr('Achse')} {axis}, {through}{at}"
        )
    if feature.kind == "face":
        normal = _axis_name(params.get("normal", (0.0, 0.0, 1.0)))
        return (
            f"{feature_id}  {tr('planar')} {float(params.get('area', 0.0)):.0f} mm², "
            f"{tr('Normale')} {normal}{at}"
        )
    if feature.kind == "edge_loop":
        return f"{feature_id}  {params.get('open_edges', 0)} {tr('offene Kanten')}"
    return f"{feature_id}  {feature.kind}{at}"


def _place(centre: object) -> str:
    """``, bei (25, -15, 8)`` — or nothing, for a feature that has no place."""
    if not isinstance(centre, list | tuple) or len(centre) != 3:
        return ""
    try:
        numbers = ", ".join(f"{float(value):g}" for value in centre)
    except (TypeError, ValueError):
        return ""
    return f", {tr('bei')} ({numbers})"


def _axis_name(vector: tuple[float, float, float]) -> str:
    """Turn a direction into something readable: +Z rather than (0, 0, 1)."""
    names = ("X", "Y", "Z")
    largest = max(range(3), key=lambda index: abs(vector[index]))
    sign = "+" if vector[largest] >= 0 else "-"
    return f"{sign}{names[largest]}"


def _finding_lines(scene: Scene) -> list[str]:
    """Warnings and notes belong in the digest — the agent has to know what it
    is standing on (§17.3, §26.1)."""
    lines: list[str] = []
    for finding in scene.report.findings:
        if finding.severity == "info":
            continue
        marker = tr("Warnung") if finding.severity == "warning" else tr("Fehler")
        lines.append(f"  {marker.lower()} {finding.message}")
    return lines


def _stack_lines(document: Document) -> list[str]:
    if not document.transactions:
        return []
    parts = []
    for transaction in document.transactions:
        numbers = ", ".join(str(entry) for entry in transaction.ops)
        by = tr("Agent") if transaction.origin.by == "agent" else tr("Nutzer")
        parts.append(f'{transaction.id} "{transaction.title}" ({tr("Ops")} {numbers}, {by})')
    return [f"{tr('Verlauf')}: " + " · ".join(parts)]
