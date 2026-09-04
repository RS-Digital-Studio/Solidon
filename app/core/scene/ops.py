"""Szenen-Operationen (Bauplan §25, Kategorie „Szene").

Sie fassen keine Geometrie an: sie benennen, kopieren und ordnen, was schon da
ist. Trotzdem laufen sie über Register und Stapel wie jede andere Operation —
„keine Geometrieänderung außerhalb einer Op" (AGENTS.md Regel 2) ist nur
glaubwürdig, wenn auch die billigen Fälle sich daran halten.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import replace
from typing import Any, cast

from app.core.errors import CORRECT_INPUT, SPLIT_MODEL, ValidationError
from app.core.geom.mesh import as_mesh_data
from app.core.registry import VARIABLE, op_params, param, register_op
from app.core.types import BaseParams, OpContext, OpResult, SceneObject
from app.core.units import DEGREE_UNIT, EPS_GEOM, is_close
from app.i18n import TranslatableText, _, tr


@op_params
class RenameObjectParams(BaseParams):
    name: str = param(title=_("Name"), doc=_("Neuer Name des Objekts."))


@register_op(
    name="rename_object",
    title=_("Objekt umbenennen"),
    category="scene",
    params=RenameObjectParams,
    consumes=1,
    produces=1,
    shortcut="F2",
    doc=_("Gibt einem Objekt einen anderen Namen. Die Geometrie bleibt unberührt."),
)
def rename_object(ctx: OpContext) -> OpResult:
    params = cast(RenameObjectParams, ctx.params)
    source = ctx.inputs[0]
    return OpResult(outputs=[dataclasses.replace(source, name=params.name)])


@register_op(
    name="delete_object",
    title=_("Objekt entfernen"),
    category="scene",
    params=BaseParams,
    consumes=1,
    produces=0,
    shortcut="Del",
    doc=_(
        "Nimmt ein Objekt aus der Szene. Der Schritt steht im Verlauf, ein "
        "Rückgängig holt es also zurück."
    ),
)
def delete_object(ctx: OpContext) -> OpResult:
    """§25: etwas wieder loswerden, ohne den Import zurückzunehmen.

    Eine Operation, die nichts erzeugt — und deshalb keine Ausnahme von
    Regel 3, sondern ihr genauester Fall: sie ändert kein Objekt, sie gibt
    keines zurück. Die Auswertung räumt jeden Eingang weg, der nicht wieder
    herauskommt, also braucht es dafür keinen Sonderweg.

    Was danach noch auf den Körper zeigt, findet ihn nicht mehr: der Stapel
    lehnt eine spätere Operation auf ihm beim Anlegen ab, und eine, die schon
    dasteht, hält die Kette an (§15.2). Beides ist besser als ein Objekt, das
    heimlich weiterlebt, weil ein Schritt darunter es noch braucht.
    """
    return OpResult(outputs=[])


#: Wie viele Exemplare eines Teils in einer Szene stehen dürfen. Eine Platte
#: mit zehn Clips ist ein gewöhnlicher Auftrag; hundert sind schon ein
#: Belastungstest fürs Anordnen, und eine Zahl darüber ist ein Tippfehler,
#: keine Bestellung.
MAX_COPIES = 100


@op_params
class DuplicateObjectParams(BaseParams):
    count: int = param(
        title=_("Anzahl"),
        default=2,
        minimum=1,
        maximum=MAX_COPIES,
        doc=_(
            "Wie viele Ausfertigungen es danach gibt. Zwei ist eine Kopie — die "
            "Stückzahl steht damit im Stapel und nicht im Dateinamen."
        ),
    )
    name: str = param(
        title=_("Name der Kopie"),
        default="",
        doc=_("Leer lässt den Namen aus dem Original ableiten."),
    )


@register_op(
    name="duplicate_object",
    title=_("Objekt duplizieren"),
    category="scene",
    params=DuplicateObjectParams,
    consumes=1,
    produces=VARIABLE,
    produces_from="count",
    shortcut="Ctrl+D",
    doc=_(
        "Legt weitere Ausfertigungen des Objekts an. Alle bleiben getrennt, und "
        "die Stückzahl steht als Zahl im Stapel."
    ),
)
def duplicate_object(ctx: OpContext) -> OpResult:
    """§25: „x10" im Dateinamen ist eine Stückzahl, die niemand mehr ändern kann.

    Hier ist es ein Schritt mit einer Zahl darin statt neun Duplikaten, die
    hinterher niemand mehr lesen kann — und das Anordnen verteilt, was dabei
    herauskommt, über die Platten (§25).
    """
    params = cast(DuplicateObjectParams, ctx.params)
    source = ctx.inputs[0]
    outputs = [source]
    for index in range(2, max(params.count, 1) + 1):
        outputs.append(
            dataclasses.replace(
                source,
                name=_copy_name(source.name, params.name, index, params.count),
                features=dict(source.features),
                material_slots=list(source.material_slots),
            )
        )
    # Dass die Kopie auf dem Original landet, meldet nicht diese Operation,
    # sondern die Auswertung am Endstand (``check_bodies_in_one_place``): Wer
    # danach anordnet, hat sie längst getrennt, und ein Satz von hier stünde
    # dann als überholte Warnung im Bericht.
    return OpResult(outputs=outputs)


def _copy_name(original: TranslatableText | str, chosen: str, index: int, count: int) -> str:
    """Namen, die auseinanderbleiben, ohne ein Rätsel zu werden.

    Eine Kopie heißt „Teil (Kopie)", wie eh und je. Mehrere werden nummeriert,
    denn zehn Objekte namens „Teil (Kopie)" sind eine Liste aus einem Ding,
    zehnmal.

    **Der Name der Kopie ist wörtlich, auch wenn der des Originals übersetzbar
    war.** Kopieren ist eine Handlung des Nutzers, und was dabei entsteht,
    gehört ihm — dieselbe Regel wie bei einem Transaktionstitel, den er selbst
    getippt hat (``title_translatable``, §4.1). Genommen wird die Fassung, die
    er beim Kopieren **gesehen** hat; sie wandert danach nicht mehr mit der
    Sprache, und das ist richtig so: Sonst hieße seine Kopie morgen anders.
    """
    base = chosen or f"{original} ({tr('Kopie')})"
    return base if count <= 2 else f"{base} {index - 1}"


# --- Muster (Bauplan §25, Kategorie „Transformation") ---------------------------


#: Wie viele Kopien ein Muster höchstens legt. Dieselbe Zahl und derselbe
#: Grund wie beim Duplizieren: darüber ist es ein Tippfehler.
MAX_PATTERN = MAX_COPIES


@op_params
class PatternParams(BaseParams):
    kind: str = param(
        title=_("Art"),
        default="linear",
        choices=("linear", "circular"),
        doc=_(
            "Linear reiht die Kopien entlang einer Richtung auf, kreisförmig legt "
            "sie um eine Achse. Eine Operation, zwei Arten — nicht zwei Einträge."
        ),
    )
    count: int = param(
        title=_("Anzahl"),
        default=4,
        minimum=1,
        maximum=MAX_PATTERN,
        doc=_(
            "Wie viele Ausfertigungen es danach gibt, das Original mitgezählt. "
            "Eine einzige ist kein Muster."
        ),
    )
    spacing: float = param(
        title=_("Abstand"),
        default=20.0,
        unit="mm",
        minimum=0.0,
        doc=_("Von Mitte zu Mitte, bei der linearen Art. Kreisförmig zählt der Winkel."),
        depends_on=("kind", ("linear",)),
    )
    angle: float = param(
        title=_("Winkel"),
        default=360.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        doc=_(
            "Über welchen Bogen die Kopien verteilt werden. Volle 360 Grad "
            "schließen den Kranz, ohne dass zwei Kopien aufeinanderfallen."
        ),
        depends_on=("kind", ("circular",)),
    )
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=("x", "y", "z"),
        placement="advanced",
        doc=_("Um welche Achse der Kranz läuft. Sie geht durch den Ursprung."),
        depends_on=("kind", ("circular",)),
    )
    dx: float = param(
        title=_("Richtung X"),
        default=1.0,
        placement="advanced",
        doc=_("Richtung der linearen Reihe. Ohne Richtung lägen alle Kopien übereinander."),
        depends_on=("kind", ("linear",)),
    )
    dy: float = param(
        title=_("Richtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Zweite Achse der Richtung — siehe Richtung X."),
        depends_on=("kind", ("linear",)),
    )
    dz: float = param(
        title=_("Richtung Z"),
        default=0.0,
        placement="advanced",
        doc=_("Dritte Achse der Richtung — siehe Richtung X."),
        depends_on=("kind", ("linear",)),
    )


@register_op(
    name="pattern",
    # Nicht „Muster": Das Wort heißt in dieser Anwendung schon etwas anderes —
    # *Textur aufbringen* hat einen Parameter „Muster", und der meint Rändel
    # und Wabe. Ein Menüeintrag und ein Feld mit demselben Wort für zwei
    # verschiedene Sachen sind eine Verwechslung, auf die man wartet.
    title=_("Kopien in Reihe oder Kreis"),
    category="transform",
    params=PatternParams,
    consumes=1,
    produces=VARIABLE,
    produces_from="count",
    doc=_(
        "Legt Kopien in einer Reihe oder auf einem Kreis an — ein Lochbild, ein "
        "Kranz Schraubdome, eine Reihe Clips. Ein Schritt mit einer Zahl darin "
        "statt neun gleicher Schritte im Stapel."
    ),
)
def pattern(ctx: OpContext) -> OpResult:
    """Muster am Körper, linear oder kreisförmig.

    Geprüft wird **vor** dem Kopieren, ob das Ergebnis noch auf die Platte
    passt (E1): dreißig Kopien im Abstand zwanzig sind sechshundert
    Millimeter, und das zu sagen ist billiger als dreißig Körper, die niemand
    drucken kann.
    """
    from app.core.geom.transform import Axis, apply, rotation, translation

    params = cast(PatternParams, ctx.params)
    source = ctx.inputs[0]
    if params.count < 2:
        raise ValidationError(
            "count",
            _("Ein Muster braucht mindestens zwei Ausfertigungen."),
            value=params.count,
            constraint="pattern_count",
        )

    if params.kind == "linear":
        direction = (params.dx, params.dy, params.dz)
        length = math.sqrt(sum(value * value for value in direction))
        if length <= EPS_GEOM:
            raise ValidationError(
                "dx",
                _("Ohne Richtung lägen alle Kopien übereinander."),
                value=length,
                constraint="no_direction",
            )
        unit: tuple[float, float, float] = (
            direction[0] / length,
            direction[1] / length,
            direction[2] / length,
        )
        _check_volume(ctx, source, params.spacing * (params.count - 1), unit)
        steps = [
            translation(
                (
                    unit[0] * params.spacing * index,
                    unit[1] * params.spacing * index,
                    unit[2] * params.spacing * index,
                )
            )
            for index in range(params.count)
        ]
    else:
        # Ein voller Kranz teilt durch die Zahl, ein Teilbogen durch die
        # Zwischenräume — sonst fielen bei 360 Grad die erste und die letzte
        # Kopie aufeinander.
        full = is_close(abs(params.angle), 360.0)
        divisor = params.count if full else max(params.count - 1, 1)
        steps = [
            rotation(cast(Axis, params.axis), params.angle * index / divisor)
            for index in range(params.count)
        ]
        # Die Bauraumprüfung galt nur der Reihe: Der Kranz meldete stattdessen
        # acht Einzelwarnungen der Auswertung, ohne die zwei
        # Handlungsvorschläge (Fund des Gesamtreviews vom 25.08.2026). Die
        # Hülle aller gedrehten Kopien ist über die acht Quaderecken je
        # Schritt billig exakt genug.
        _check_ring_volume(ctx, source, steps)

    outputs = [
        dataclasses.replace(
            source,
            name=_copy_name(source.name, "", index + 1, params.count) if index else source.name,
            mesh=apply(as_mesh_data(source.mesh), step) if index else source.mesh,
            features={} if index else dict(source.features),
            material_slots=list(source.material_slots),
        )
        for index, step in enumerate(steps)
    ]
    return OpResult(outputs=outputs)


def _check_ring_volume(ctx: OpContext, source: SceneObject, steps: list[Any]) -> None:
    """Ob der Kranz noch auf die Platte passt — die Hülle aller Kopien.

    Dieselbe Auskunft wie bei der Reihe, mit denselben zwei
    Handlungsvorschlägen: gerechnet über die acht Ecken des Hüllquaders,
    durch jede Schrittmatrix gedreht.
    """
    import numpy as np

    volume = ctx.profile.printer.build_volume
    bounds = as_mesh_data(source.mesh).bounds
    corners = np.array(
        [
            (x, y, z, 1.0)
            for x in (bounds.minimum[0], bounds.maximum[0])
            for y in (bounds.minimum[1], bounds.maximum[1])
            for z in (bounds.minimum[2], bounds.maximum[2])
        ]
    )
    moved = np.vstack([(np.asarray(step) @ corners.T).T[:, :3] for step in steps])
    needed_size = moved.max(axis=0) - moved.min(axis=0)
    for axis in range(3):
        needed = float(needed_size[axis])
        if needed > volume[axis] + EPS_GEOM:
            raise ValidationError(
                "count",
                _(
                    "So viele Kopien reichen über den Bauraum hinaus. Wie weit, steht "
                    "in „needed_mm“; was die Maschine kann, in „volume_mm“."
                ),
                value=needed,
                constraint="build_volume",
                values={"needed_mm": round(needed, 1), "volume_mm": round(volume[axis], 1)},
                suggestions=[
                    replace(CORRECT_INPUT, label=_("Anzahl oder Abstand verringern")),
                    SPLIT_MODEL,
                ],
            )


def _check_volume(
    ctx: OpContext, source: SceneObject, reach: float, unit: tuple[float, float, float]
) -> None:
    """Ob die Reihe noch auf die Platte passt (E1).

    Gemessen an der Ausdehnung, die dazukommt: die Kopien wandern entlang der
    Richtung, also wächst der Bauraumbedarf in jeder Achse um den Anteil, den
    die Richtung dort hat.
    """
    volume = ctx.profile.printer.build_volume
    size = as_mesh_data(source.mesh).bounds.size
    for axis in range(3):
        needed = size[axis] + abs(unit[axis]) * reach
        if needed > volume[axis] + EPS_GEOM:
            raise ValidationError(
                "count",
                _(
                    "So viele Kopien reichen über den Bauraum hinaus. Wie weit, steht "
                    "in „needed_mm“; was die Maschine kann, in „volume_mm“."
                ),
                value=needed,
                constraint="build_volume",
                values={"needed_mm": round(needed, 1), "volume_mm": round(volume[axis], 1)},
                suggestions=[
                    replace(CORRECT_INPUT, label=_("Anzahl oder Abstand verringern")),
                    SPLIT_MODEL,
                ],
            )
