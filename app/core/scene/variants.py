"""Der Variantengenerator (Bauplan §28.3, §25 Kategorie „Varianten").

Dieselbe Operationskette mit einem durchgestuften Parameter, in einem Zug:
vier Läufe mit 0,10 / 0,15 / 0,20 / 0,25 mm Spiel, beschriftet und
angeordnet. Ein Druck, und danach ist der Wert entschieden.

„Mit Projektparametern ist das ein Aufruf, keine Sonderfunktion" — und genau
so ist es gebaut. Nichts hier weiß etwas über Passungen oder Spiel; es dreht
an einer Zahl, die schon ein Parameter ist (§13), und wertet denselben Stapel
noch einmal aus.

Die Varianten sind mit Absicht **kein** Schritt auf dem Stapel. Sie sind ein
Druckauftrag, kein Konstruktionsschritt: zurück kommt eine Szene zum
Exportieren, und das Projekt bleibt exakt, wie es war.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field

from app.core.errors import ValidationError
from app.core.geom.mesh import as_mesh_data
from app.core.geom.transform import apply, translation
from app.core.log import get_logger
from app.core.scene.evaluate import evaluate
from app.core.types import (
    CancelToken,
    Document,
    Finding,
    ObjectId,
    Profile,
    ProgressFn,
    Quality,
    Report,
    Scene,
    SceneObject,
    SourceAccess,
)
from app.i18n import _, tr

_log = get_logger(__name__)


def _silent(fraction: float, text: str) -> None:
    """Kein Fortschritt gewünscht — der Vorgabewert von ``build``."""


#: Abstand zwischen zwei Varianten auf der Platte, in Millimetern.
DEFAULT_GAP = 8.0

#: Mehr als das ist kein Kalibrierdruck mehr, sondern eine Platte voller
#: Vermutungen (§28.3 nennt vier).
MAX_VARIANTS = 12


@dataclass(slots=True)
class Variant:
    """Ein Lauf mit einem Wert."""

    value: float
    objects: dict[ObjectId, SceneObject] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    complete: bool = True


@dataclass(slots=True)
class VariantSet:
    """Alles, was der Generator erzeugt hat, bereit zum Export."""

    parameter: str
    variants: list[Variant] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return bool(self.variants) and all(entry.complete for entry in self.variants)

    def scene(self, profile: Profile) -> Scene:
        """Der ganze Lauf als eine Szene — angeordnet, benannt nach den Werten."""
        objects: dict[ObjectId, SceneObject] = {}
        for entry in self.variants:
            objects.update(entry.objects)
        return Scene(objects=objects, profile=profile, report=Report(tuple(self.findings)))


def build(
    document: Document,
    profile: Profile,
    *,
    parameter: str,
    first: float,
    step: float,
    count: int = 4,
    gap: float = DEFAULT_GAP,
    quality: Quality = "draft",
    sources: SourceAccess | None = None,
    progress: ProgressFn = _silent,
    cancelled: CancelToken | None = None,
) -> VariantSet:
    """Wertet denselben Stapel ``count``-mal mit gestuftem Parameter aus.

    ``progress`` und ``cancelled`` gehen an jede einzelne Auswertung durch und
    tragen zusammen §2.8: Zwölf Auswertungen sind über zwei Sekunden, und über
    zwei Sekunden gehören Fortschritt und ein Abbrechen dazu. Beides gab es
    hier nicht — die Oberfläche stand still, bis der letzte Lauf durch war, und
    zwar im Qt-Hauptthread.

    Der Anteil, den ``progress`` meldet, ist der über alle Läufe: Lauf drei von
    vier bei halber Kette meldet 0,625. Ein Balken, der viermal von null
    hochläuft, sagt weniger als keiner.

    Abgebrochen wird **zwischen** den Läufen und innerhalb eines Laufes: Die
    Auswertung prüft den Token selbst, und die Prüfung hier davor spart den
    Aufbau des nächsten Dokuments. Was bis dahin fertig war, kommt zurück —
    ein halber Satz ist kein Kalibrierdruck, und wer abbricht, weiß das.
    """
    if parameter not in document.parameters:
        raise ValidationError(
            field="parameter",
            detail=_("Diesen Projektparameter gibt es nicht."),
            values={"requested": parameter, "known": ", ".join(sorted(document.parameters))},
        )
    if not 1 <= count <= MAX_VARIANTS:
        raise ValidationError(
            field="count",
            detail=_("So viele Varianten ergeben keinen Kalibrierdruck mehr."),
            constraint="range",
            values={"count": count, "maximum": MAX_VARIANTS},
        )

    made = VariantSet(parameter=parameter)
    offset = 0.0

    for index in range(count):
        if cancelled is not None and cancelled.is_cancelled:
            _log.info("variants cancelled after %d of %d", index, count)
            break
        value = first + step * index
        working = copy.deepcopy(document)
        working.parameters[parameter] = dataclasses.replace(
            working.parameters[parameter], value=value, expression=""
        )

        def onward(share: float, text: str, done: int = index) -> None:
            """Der Anteil über alle Läufe, nicht der des einzelnen."""
            progress((done + max(0.0, min(1.0, share))) / count, text)

        result = evaluate(
            working,
            profile,
            quality=quality,
            sources=sources,
            progress=onward,
            cancelled=cancelled,
        )
        variant = Variant(value=value, complete=result.complete)
        variant.findings.extend(result.scene.report.findings)

        if not result.complete:
            made.findings.append(
                Finding(
                    code="variants.stopped",
                    severity="error",
                    message=_("Eine Variante ließ sich nicht rechnen."),
                    values={"parameter": parameter, "value": round(value, 3)},
                )
            )
            made.variants.append(variant)
            continue

        width = _place(variant, result.scene, index, value, offset, gap)
        offset += width + gap
        made.variants.append(variant)

    _log.info("built %d variants of %s", len(made.variants), parameter)
    return made


def _place(
    variant: Variant,
    scene: Scene,
    index: int,
    value: float,
    offset: float,
    gap: float,
) -> float:
    """Rückt einen Lauf aus dem Weg des vorigen und benennt ihn nach seinem
    Wert."""
    width = 0.0
    for object_id, entry in scene.objects.items():
        mesh = as_mesh_data(entry.mesh)
        size = mesh.bounds.size
        width = max(width, float(size[0]))
        moved = apply(mesh, translation((offset - float(mesh.bounds.minimum[0]), 0.0, 0.0)))
        name = f"{entry.name} {tr('Variante')} {value:g}"
        variant.objects[f"{object_id}_v{index + 1}"] = dataclasses.replace(
            entry, id=f"{object_id}_v{index + 1}", name=name, mesh=moved
        )
    return width


def values(first: float, step: float, count: int) -> tuple[float, ...]:
    """Die Werte, die ein Lauf benutzen würde — für den Dialog und die
    Beschriftung."""
    return tuple(round(first + step * index, 4) for index in range(count))
