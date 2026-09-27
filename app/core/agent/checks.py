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

from collections import Counter
from typing import Final, cast

from app.core.scene.evaluate import EvaluationResult
from app.core.types import Finding, Mesh, ObjectId, Scene, SceneObject
from app.i18n import _, tr

#: Volumenverhältnis, außerhalb dessen eine Änderung erwähnenswert ist. Eine
#: Boolesche Op darf einen Körper legitim halbieren; ein Faktor zehn in
#: irgendeine Richtung ist ein Ausrutscher.
VOLUME_FACTOR = 10.0

#: Codes, die die Prüfung aus der Auswertung durchreicht, weil sie genau das
#: sagen, wonach §26.5 fragt.
#:
#: Die beiden letzten kamen aus einem Chatlauf: „5 mm mittig durch" ergab ein
#: Loch an der Ecke, weil das Modell den Quader ab dem Ursprung wähnte statt um
#: ihn herum. Der Befund dazu entstand — und blieb im Prüfbericht liegen, denn
#: was hier nicht steht, sieht das Modell nie. Es schrieb danach „Das Loch ist
#: durchgehend und mittig positioniert", und niemand widersprach. Ein Werkzeug,
#: das den Körper nur streift oder ganz verfehlt, ist genau die Sorte Fehler,
#: die ein zweiter Aufruf beheben kann — wenn er davon erfährt.
PASSED_THROUGH = (
    "perceive.orphaned",
    "feature.orphaned",
    "bore.over_the_edge",
    # Dieselbe Sorte Fehler eine Stufe weiter: Das Werkzeug hat den Körper
    # nicht gestreift, sondern zerlegt (Fund des Reviews, 13.09.2026).
    "bore.splits_the_body",
    "boolean.without_effect",
    # Und zwei Schritte, die gar nichts getan haben (Messung 14.09.2026). Der
    # erste ist der Fall, den ein zweiter Aufruf behebt: Das Ziel lag über der
    # vorhandenen Dreieckszahl, eine kleinere Zahl gibt ihm etwas zu tun. Beim
    # zweiten kann das Modell nichts nachbessern — ein Skelett setzt nur der
    # Nutzer —, und genau deshalb muss es davon erfahren: Sonst schreibt es
    # „der Arm ist jetzt angewinkelt" über einen Körper, der unverändert
    # dasteht.
    "mesh.already_below_target",
    "pose.no_armature",
)

#: Der Satz der Auswertung über einen zerfallenen Körper. Nach einer Operation,
#: die gewollt lose Teile ablegt, ist er das Urteil über den Träger und ersetzt
#: den eigenen Teilevergleich (:func:`check`); sonst sagt ``agent.components_grew``
#: dasselbe, und das Modell läse es zweimal.
BODY_SPLIT: Final = "feature.body_split"


def check(
    result: EvaluationResult, before: Scene | None = None, *, separate_parts: bool = False
) -> list[Finding]:
    """Was der Agent über den Zustand wissen muss, den seine Operation
    erzeugt hat.

    ``separate_parts`` sagt, dass die Operation gewollt ein loses Teil neben
    ihren Träger gelegt hat (``OperationSpec.leaves_separate_parts`` — eine
    gedruckte Schraube, Mutter oder separate Dichtung). Dann ist „mehr Teile
    als vorher" die Absicht und kein Stolperdraht; ob der **Träger** zerfallen
    ist, hat die Operation selbst beurteilt, und ihr Befund
    ``feature.body_split`` geht an das Modell. Bis zur Durchsicht 0.5.1 las
    es nach jeder gedruckten Schraube „Das Objekt zerfällt jetzt in mehr
    Teile als vorher".
    """
    findings: list[Finding] = []
    scene = result.scene
    reasons: list[Finding] = []

    if result.stopped_at is not None:
        # Der Grund steht im Bericht, an derselben Operation — und er ist das
        # Einzige, womit das Modell etwas anfangen kann. „Die Auswertung hält
        # an" allein sagt nicht, *warum*: gemessen an `pocket_plate` rief das
        # Modell danach viermal dieselbe Operation mit anderen Zahlen auf,
        # während der Bericht die ganze Zeit „Der gewählte Körper ist ein Netz"
        # sagte. Mit dem Satz wechselt es stattdessen den Körpertyp.
        reasons = [entry for entry in scene.report.findings if entry.op_id == result.stopped_at]
        findings.append(
            Finding(
                code="agent.stopped",
                severity="error",
                message=_("Die Auswertung hält bei dieser Operation an."),
                op_id=result.stopped_at,
            )
        )
        findings.extend(reasons)

    for object_id, entry in scene.objects.items():
        findings.extend(_check_object(object_id, entry, before, count_parts=not separate_parts))

    findings.extend(
        finding
        for finding in scene.report.findings
        if (
            finding.code in PASSED_THROUGH
            or finding.code.startswith("fit.")
            or (
                (finding.converts_exact_body or (separate_parts and finding.code == BODY_SPLIT))
                and (before is None or finding not in before.report.findings)
            )
        )
        and finding not in reasons
    )
    return findings


def _check_object(
    object_id: ObjectId, entry: SceneObject, before: Scene | None, *, count_parts: bool = True
) -> list[Finding]:
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
        findings.extend(_compare(object_id, earlier, mesh, count_parts=count_parts))
    return findings


def _compare(
    object_id: ObjectId, earlier: SceneObject, mesh: Mesh, *, count_parts: bool = True
) -> list[Finding]:
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

    if count_parts and mesh.component_count > old_mesh.component_count:
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


def as_lines(findings: list[Finding], *, include_severity: bool = False) -> str:
    """Die Befunde als das Werkzeugergebnis, das das Modell liest.

    Verlorene Formdetails ohne Verweis meldet die Auswertung einmal je Körper
    und Schritt, ihre Zahl in ``values["count"]`` (fehlt bei genau einem) und
    ihre Kennungen in ``values["feature"]``. Im Werkzeugergebnis werden sie
    je Körper und Schritt gezählt — auch wortgleiche Einzelbefunde, wie sie
    ein Vorschlag von Hand tragen kann: Hunderte gleiche Sätze verdrängen
    sonst gerade den nächsten andersartigen Befund, auf den das Modell
    reagieren soll.
    """
    if not findings:
        return str(_("Prüfung ohne Befund."))

    def key(finding: Finding) -> tuple[object, ...]:
        return (
            finding.code,
            finding.severity,
            str(finding.message),
            finding.source,
            finding.object_id,
            finding.op_id,
        )

    counts: Counter[tuple[object, ...]] = Counter()
    for finding in findings:
        if finding.code in ("perceive.orphaned", "perceive.mended"):
            counts[key(finding)] += int(cast(float, finding.values.get("count", 1)))
    emitted: set[tuple[object, ...]] = set()
    lines: list[str] = []
    for finding in findings:
        prefix = f"{finding.severity}: " if include_severity else ""
        if finding.code not in ("perceive.orphaned", "perceive.mended"):
            lines.append(f"{prefix}{finding.code}: {finding.message}")
            continue

        identity = key(finding)
        if identity in emitted:
            continue
        emitted.add(identity)
        amount = counts[identity]
        context: list[str] = []
        if finding.object_id is not None:
            context.append(f"{tr('Körper')} {finding.object_id}")
        if finding.op_id is not None:
            context.append(f"{tr('Schritt')} {finding.op_id}")
        suffix = f" — {' · '.join(context)}" if context else ""
        count = f"{amount} \N{MULTIPLICATION SIGN} " if amount > 1 else ""
        lines.append(f"{prefix}{finding.code}: {count}{finding.message}{suffix}")
    return "\n".join(lines)
