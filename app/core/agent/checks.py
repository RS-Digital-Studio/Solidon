"""The check that runs after every operation of a proposal (Bauplan §26.5).

Watertight, volume plausible, no unexpected components, no orphaned references,
no violated fits — and the finding goes back into the context. Without that the
agent proposes a second operation on a body its first one already broke.

The checks are deliberately blunt. They are not a quality judgement, they are a
tripwire: something happened here that the model should know about before it
carries on.
"""

from __future__ import annotations

from app.core.scene.evaluate import EvaluationResult
from app.core.types import Finding, Mesh, ObjectId, Scene, SceneObject
from app.i18n import _

#: Volume ratio outside which a change is worth mentioning. A boolean can halve
#: a body legitimately; a factor of ten in either direction is a slip.
VOLUME_FACTOR = 10.0

#: Codes the check passes through from the evaluation, because they say exactly
#: what §26.5 asks about.
PASSED_THROUGH = ("perceive.orphaned", "feature.orphaned", "fit.violated", "fit.missing_feature")


def check(result: EvaluationResult, before: Scene | None = None) -> list[Finding]:
    """What the agent has to know about the state its operation produced."""
    findings: list[Finding] = []
    scene = result.scene

    if result.stopped_at is not None:
        findings.append(
            Finding(
                code="agent.stopped",
                severity="error",
                message=_("Die Auswertung hält bei dieser Operation an."),
                op_id=result.stopped_at,
            )
        )

    for object_id, entry in scene.objects.items():
        findings.extend(_check_object(object_id, entry, before))

    findings.extend(finding for finding in scene.report.findings if finding.code in PASSED_THROUGH)
    return findings


def _check_object(object_id: ObjectId, entry: SceneObject, before: Scene | None) -> list[Finding]:
    mesh = entry.mesh

    findings: list[Finding] = []
    if not mesh.is_watertight:
        findings.append(
            Finding(
                code="agent.not_watertight",
                severity="warning",
                message=_("Dieses Objekt ist nicht mehr geschlossen."),
                object_id=object_id,
            )
        )

    earlier = before.objects.get(object_id) if before is not None else None
    if earlier is not None:
        findings.extend(_compare(object_id, earlier, mesh))
    return findings


def _compare(object_id: ObjectId, earlier: SceneObject, mesh: Mesh) -> list[Finding]:
    findings: list[Finding] = []
    old_mesh = earlier.mesh

    old_volume = float(old_mesh.volume)
    new_volume = float(mesh.volume)
    if old_volume > 0.0 and new_volume > 0.0:
        ratio = new_volume / old_volume
        if ratio > VOLUME_FACTOR or ratio < 1.0 / VOLUME_FACTOR:
            findings.append(
                Finding(
                    code="agent.volume_jumped",
                    severity="warning",
                    message=_("Das Volumen hat sich unerwartet stark geändert."),
                    object_id=object_id,
                    values={"before": round(old_volume, 1), "after": round(new_volume, 1)},
                )
            )

    if mesh.component_count > old_mesh.component_count:
        findings.append(
            Finding(
                code="agent.components_grew",
                severity="warning",
                message=_("Das Objekt zerfällt jetzt in mehr Teile als vorher."),
                object_id=object_id,
                values={"before": old_mesh.component_count, "after": mesh.component_count},
            )
        )
    return findings


def as_lines(findings: list[Finding]) -> str:
    """The findings as the tool result the model reads."""
    if not findings:
        return str(_("Prüfung ohne Befund."))
    return "\n".join(f"{finding.code}: {finding.message}" for finding in findings)
