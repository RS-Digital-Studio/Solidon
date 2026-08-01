"""Die Prüfung nach jeder Operation eines Vorschlags (Bauplan §26.5).

Wasserdicht, Volumen plausibel, keine unerwarteten Komponenten, keine
verwaisten Verweise, keine verletzten Passungen — und der Befund geht zurück
in den Kontext. Ohne das schlägt der Agent eine zweite Operation auf einem
Körper vor, den seine erste schon kaputtgemacht hat.

Die Prüfungen sind mit Absicht grob. Sie sind kein Qualitätsurteil, sie sind
ein Stolperdraht: hier ist etwas passiert, das das Modell wissen sollte, bevor
es weitermacht.
"""

from __future__ import annotations

from app.core.scene.evaluate import EvaluationResult
from app.core.types import Finding, Mesh, ObjectId, Scene, SceneObject
from app.i18n import _

#: Volumenverhältnis, außerhalb dessen eine Änderung erwähnenswert ist. Eine
#: Boolesche Op darf einen Körper legitim halbieren; ein Faktor zehn in
#: irgendeine Richtung ist ein Ausrutscher.
VOLUME_FACTOR = 10.0

#: Codes, die die Prüfung aus der Auswertung durchreicht, weil sie genau das
#: sagen, wonach §26.5 fragt.
PASSED_THROUGH = ("perceive.orphaned", "feature.orphaned", "fit.violated", "fit.missing_feature")


def check(result: EvaluationResult, before: Scene | None = None) -> list[Finding]:
    """Was der Agent über den Zustand wissen muss, den seine Operation
    erzeugt hat.
    """
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
    """Die Befunde als das Werkzeugergebnis, das das Modell liest."""
    if not findings:
        return str(_("Prüfung ohne Befund."))
    return "\n".join(f"{finding.code}: {finding.message}" for finding in findings)
