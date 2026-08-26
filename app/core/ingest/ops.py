"""Die ``load``-Operation (Bauplan §17.1).

Die Eingangsstufe ist eine Operation, kein versteckter Vorbereitungsschritt:
ihre Parameter bleiben im Stapel sichtbar und lassen sich nachträglich ändern.
Dieselbe Datei mit einer anderen Einheit zu laden ist darum eine
Parameteränderung, kein neuer Import.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from app.core.errors import InternalError, ValidationError
from app.core.export import threemf
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.geom.transform import apply, scaling, translation
from app.core.ingest import outline
from app.core.ingest.loader import (
    IngestResult,
    check_limits,
    check_unpacked,
    detect_unit,
    normalise,
)
from app.core.registry import VARIABLE, op_params, param, register_op
from app.core.types import (
    BaseParams,
    BoundingBox,
    Finding,
    MaterialSlot,
    OpContext,
    OpResult,
    SceneObject,
    Vec3,
)
from app.core.units import LengthUnit, format_length, is_zero, to_mm
from app.i18n import _

_UNIT_CHOICES = ("auto", "mm", "cm", "in", "m")

#: Was eine 3MF über sich sagt, ausgedrückt in dem, was der Kern kennt (§11.1):
#: eine seiner vier Einheiten und ein Faktor davor, wo das Format feiner
#: unterteilt.
#:
#: Mikrometer und Fuß sind der Grund für den Faktor. Beide sind gültige
#: 3MF-Einheiten, keine der vier Antworten der Einheitenfrage trifft sie, und
#: eine Datei in Mikrometern ließ sich damit nur falsch importieren. Fuß geht
#: exakt in zwölf Zoll auf — der Faktor kostet also keine Genauigkeit, er
#: benennt sie.
_DECLARED_UNITS: dict[str, tuple[LengthUnit, float | None]] = {
    "micron": ("mm", 0.001),
    "millimeter": ("mm", None),
    "centimeter": ("cm", None),
    "inch": ("in", None),
    "foot": ("in", 12.0),
    "meter": ("m", None),
}


@op_params
class LoadParams(BaseParams):
    source: str = param(
        title=_("Quelle"),
        kind="source",
        doc=_("Die eingebettete oder verknüpfte Datei im Projekt."),
    )
    unit: str = param(
        title=_("Einheit"),
        default="auto",
        choices=_UNIT_CHOICES,
        doc=_("STL kennt keine Einheit. Automatisch heißt: schätzen, im Zweifel nachfragen."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        doc=_("Leer übernimmt den Dateinamen."),
    )
    place_on_bed: bool = param(
        title=_("Auf das Bett setzen"),
        default=False,
        doc=_("Setzt das Modell mit seiner Unterseite auf Z = 0."),
    )
    weld: bool = param(
        title=_("Punkte verschweißen"),
        default=True,
        placement="advanced",
        doc=_(
            "Führt Punkte zusammen, die praktisch aufeinanderliegen — der häufigste "
            "Grund, warum ein STL aus lauter Einzelteilen zu bestehen scheint."
        ),
    )
    remove_degenerate: bool = param(
        title=_("Entartete Dreiecke entfernen"),
        default=True,
        placement="advanced",
        doc=_("Dreiecke ohne Fläche. Sie stören jede spätere Rechnung und tragen nichts."),
    )
    unify_normals: bool = param(
        title=_("Normalen vereinheitlichen"),
        default=True,
        placement="advanced",
        doc=_("Richtet aus, wo außen ist. Ohne das erscheinen Flächen dunkel oder fehlen."),
    )


@register_op(
    name="load",
    title=_("Modell laden"),
    category="import",
    params=LoadParams,
    consumes=0,
    produces=VARIABLE,
    doc=_(
        "Liest eine Modelldatei, rechnet sie in Millimeter um und bereinigt sie. "
        "Eine 3MF-Baugruppe kommt als mehrere Objekte an, nicht als ein Klumpen."
    ),
)
def load(ctx: OpContext) -> OpResult:
    params = cast(LoadParams, ctx.params)
    if ctx.sources is None:
        raise InternalError(
            detail="the load operation was called without access to the project sources",
            values={"source": params.source},
        )

    source = ctx.sources.describe(params.source)
    payload = ctx.sources.read(params.source)
    check_limits(len(payload), 0)

    suffix = Path(source.path).suffix
    if suffix.lower() == ".3mf":
        # Vor dem Parsen, nicht danach: die gepackte Größe sagt bei einem
        # Container nichts — 2,6 MB wurden beim Lesen zu 1,08 GB (§32).
        check_unpacked(payload)
        # Und die Dreiecke ebenso vor dem Parsen. read_objects hebt gleich das
        # ganze XML in den Speicher, rund das Zwölffache der entpackten Größe;
        # die Grenze weiter unten (nach read_objects) käme dafür zu spät.
        # scan_assembly zählt streamend, in beschränktem Speicher.
        check_limits(len(payload), threemf.scan_assembly(payload)[1])
    stem = Path(source.path).stem
    parts = threemf.read_objects(payload) if suffix.lower() == ".3mf" else []
    if not parts:
        mesh = read_mesh(payload, suffix)
        mesh, slots = _colour_groups(payload, suffix, mesh)
        parts = [threemf.Part(name=params.name or stem, mesh=mesh, slots=tuple(slots))]
    elif params.name and len(parts) == 1:
        parts = [dataclasses.replace(parts[0], name=params.name)]

    check_limits(len(payload), sum(part.mesh.triangle_count for part in parts))

    # Eine Einheit für die ganze Datei. Je Körper zu entscheiden ließe zwei
    # Teile einer Baugruppe in verschiedenen Maßstäben herauskommen, und
    # die Frage, die §17.1 dem Nutzer stellt, gilt der Datei, nicht jedem
    # Körper darin.
    # Der größte Körper der Datei stellt die Frage: seine Diagonale entscheidet
    # die Heuristik, und seine Kantenmaße sind das, was die Rückfrage zeigt.
    biggest = max((part.mesh.bounds for part in parts), key=lambda bounds: bounds.diagonal)
    # **Erst die Datei, dann die Heuristik, dann die Frage.** Eine 3MF trägt
    # ihre Einheit im ``unit``-Attribut, und solange sie ungelesen blieb, wurde
    # über eine Datei gerätselt, die die Antwort mitbrachte. Was im Stapel
    # steht, geht weiter vor: Wer die Einheit von Hand setzt, korrigiert auch
    # eine Datei, die sich irrt.
    stated = _stated_unit(payload, suffix) if params.unit == "auto" else None
    findings: list[Finding] = []
    if stated is not None:
        declared, unit, factor = stated
        # Nicht aufgeschrieben: Die Datei sagt es beim nächsten Mal wieder, und
        # ein Faktor (Mikrometer, Fuß) ließe sich im Parameter gar nicht
        # ausdrücken — er ginge bei der nächsten Auswertung verloren.
        answered: dict[str, str] = {}
        if factor is not None:
            parts = [
                dataclasses.replace(part, mesh=apply(part.mesh, scaling((factor, factor, factor))))
                for part in parts
            ]
            findings.append(
                Finding(
                    code="ingest.declared_unit",
                    severity="info",
                    message=_("Die Datei nennt ihre Einheit selbst; sie wurde umgerechnet."),
                    values={"unit": declared, "scale": factor},
                )
            )
    else:
        unit = _unit_for(ctx, params, biggest)
        # §15.7: Wurde die Einheit erfragt, wird sie aufgeschrieben. Ohne das
        # käme die Frage bei jeder Auswertung wieder — und mit einem Cache, der
        # länger lebt als die Sitzung, käme sie irgendwann *nicht* wieder, und
        # der Nutzer bekäme eine Annahme, ohne sie zu sehen (Regel 21).
        answered = {"unit": str(unit)} if params.unit == "auto" else {}

    outputs: list[SceneObject] = []
    for index, part in enumerate(parts):
        ctx.progress(index / len(parts), str(_("Modell laden")))
        result: IngestResult = normalise(
            part.mesh,
            unit,
            weld=params.weld,
            remove_degenerate=params.remove_degenerate,
            unify_normals=params.unify_normals,
            # Jeden Körper für sich auf Z = 0 abzusetzen nähme einem Gehäuse den
            # Deckel ab und stapelte die Teile aufeinander. Eine Baugruppe geht
            # deshalb **gemeinsam** aufs Bett, unten nach der Schleife — nicht
            # gar nicht.
            place_on_bed=params.place_on_bed and len(parts) == 1,
            progress=ctx.progress,
        )
        outputs.append(
            SceneObject(id="", name=part.name, mesh=result.mesh, material_slots=list(part.slots))
        )
        findings.extend(
            _named(result.findings, part.name) if len(parts) > 1 else list(result.findings)
        )

    if params.place_on_bed and len(outputs) > 1:
        outputs = _group_on_bed(outputs, findings)

    if len(parts) > 1:
        findings.append(
            Finding(
                code="load.assembly",
                severity="info",
                message=_("Die Datei enthält mehrere Körper — sie kommen als eigene Objekte an."),
                values={"parts": len(parts), "file": stem},
            )
        )
    return OpResult(outputs=outputs, findings=findings, answered=answered)


def _named(findings: Sequence[Finding], name: str) -> list[Finding]:
    """Sagt, um welchen Körper einer Baugruppe es bei einem Befund geht."""
    return [
        dataclasses.replace(entry, values={**entry.values, "object": name}) for entry in findings
    ]


@op_params
class LoadOutlineParams(BaseParams):
    source: str = param(
        title=_("Quelle"),
        kind="source",
        doc=_("Die eingebettete SVG- oder DXF-Datei im Projekt."),
    )
    height: float = param(
        title=_("Höhe"),
        default=3.0,
        unit="mm",
        minimum=0.1,
        maximum=500.0,
        doc=_("Wie weit die Zeichnung in die Höhe gezogen wird."),
    )
    width: float = param(
        title=_("Breite"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        doc=_("Auf diese Breite skalieren. Null nimmt die Zahlen der Datei als Millimeter."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer übernimmt den Dateinamen."),
    )


@register_op(
    name="load_outline",
    title=_("Zeichnung extrudieren"),
    category="import",
    params=LoadOutlineParams,
    consumes=0,
    produces=1,
    doc=_(
        "Liest eine SVG- oder DXF-Zeichnung und gibt ihr eine Höhe. Innenliegende "
        "Konturen werden zu Löchern."
    ),
)
def load_outline(ctx: OpContext) -> OpResult:
    """§25: zwei Dimensionen plus eine Dicke, ohne Umweg über Blender."""
    params = cast(LoadOutlineParams, ctx.params)
    if ctx.sources is None:
        raise InternalError(
            detail="load_outline was called without access to the project sources",
            values={"source": params.source},
        )

    source = ctx.sources.describe(params.source)
    payload = ctx.sources.read(params.source)
    check_limits(len(payload), 0)

    result = outline.extrude(payload, Path(source.path).suffix, params.height, params.width)
    name = params.name or Path(source.path).stem
    return OpResult(
        outputs=[SceneObject(id="", name=name, mesh=result.mesh)],
        findings=[
            Finding(
                code="ingest.extruded",
                severity="info",
                message=_("Aus der Zeichnung wurde ein Körper."),
                values={
                    "contours": result.contours,
                    "drawn_width": round(result.width, 2),
                    "height_mm": round(params.height, 2),
                },
            )
        ],
    )


def _colour_groups(
    payload: bytes, suffix: str, mesh: MeshData
) -> tuple[MeshData, list[MaterialSlot]]:
    """§20, Importseite: 3MF trägt einen Slot je Dreieck, und der bleibt.

    Alles andere behält sein Verhalten — STL hat keine Farbe, und eine Textur
    wird zu Slots, wenn der Nutzer danach fragt, nicht auf dem Weg hinein.
    """
    if suffix.lower() != ".3mf":
        return mesh, []
    groups = threemf.read(payload, mesh.triangle_count)
    if groups is None:
        return mesh, []
    return MeshData(raw=mesh.raw, slots=groups.slots), list(groups.materials)


def _group_on_bed(outputs: list[SceneObject], findings: list[Finding]) -> list[SceneObject]:
    """Setzt eine Baugruppe **als Ganzes** auf Z = 0 (§17.1, Schritt 6).

    Der Haken war für eine Baugruppe wirkungslos, und zwar stillschweigend:
    Wer ihn setzte, bekam eine Datei, die lag, wo sie lag, ohne ein Wort
    darüber. Der Grund dafür war richtig — jeden Körper einzeln abzusetzen
    stapelte Gehäuse, Deckel und Tülle aufeinander —, die Folgerung nicht: Was
    zusammengehört, wird zusammen verschoben, und dann ist der tiefste Punkt
    der Gruppe der, der auf null kommt.

    Steht die Gruppe schon unten, geschieht nichts und wird nichts gemeldet:
    ein Befund über eine Verschiebung um null wäre Lärm.
    """
    lowest = min(float(as_mesh_data(entry.mesh).bounds.minimum[2]) for entry in outputs)
    if is_zero(lowest):
        return outputs

    lift = translation((0.0, 0.0, -lowest))
    moved = [
        dataclasses.replace(entry, mesh=apply(as_mesh_data(entry.mesh), lift)) for entry in outputs
    ]
    findings.append(
        Finding(
            code="load.assembly_on_bed",
            severity="info",
            message=_(
                "Die Baugruppe wurde als Ganzes auf das Bett gesetzt — die Teile behalten "
                "ihre Lage zueinander."
            ),
            values={"amount": format_length(-lowest)},
        )
    )
    return moved


def _stated_unit(payload: bytes, suffix: str) -> tuple[str, LengthUnit, float | None] | None:
    """Was die Datei selbst über ihre Einheit sagt (§17.1).

    Zurück kommt ihr eigenes Wort dafür, die Einheit des Kerns dazu und der
    Faktor, wo das Format feiner unterteilt. Das eigene Wort, weil es in den
    Befund gehört: „foot" ist die Auskunft, „in mal zwölf" ist die Rechnung.

    Nur 3MF sagt etwas: STL, OBJ und PLY tragen keine Einheit, und STEP geht
    einen anderen Weg. ``None`` heißt „schweigt" — dann entscheidet die
    Heuristik, und im Zweifel der Nutzer.
    """
    if suffix.lower() != ".3mf":
        return None
    declared = threemf.declared_unit(payload)
    known = _DECLARED_UNITS.get(declared or "")
    return (declared or "", *known) if known is not None else None


def unit_question(size: Vec3, candidates: Sequence[LengthUnit]) -> str:
    """Die Einheitenfrage — mit der Folge jeder Antwort daneben (§17.1).

    Gefragt wurde „In welcher Einheit ist diese Datei gespeichert?", und zur
    Wahl standen zwei Wörter: „cm" und „in". Wer eine fremde Datei
    herunterlädt, weiß das nicht — die Einheit steht in keinem STL. Was er
    weiß, ist, wie groß das Teil sein soll. Also steht jetzt neben jeder
    Antwort, wie groß das Modell mit ihr wäre; die Frage wird damit von einer
    Wissensfrage zu einer, die man ansehen kann.

    Anhalten und fragen bleibt richtig (Leitprinzip 6) — eine Frage, die
    niemand beantworten kann, ist aber nur die halbe Regel.
    """
    lines = [str(_("In welcher Einheit ist diese Datei gespeichert?"))]
    for unit in candidates:
        measures = " × ".join(format_length(to_mm(value, unit), with_unit=False) for value in size)
        lines.append(f"{unit}: {measures} mm")
    return "\n".join(lines)


def _unit_for(ctx: OpContext, params: LoadParams, bounds: BoundingBox) -> LengthUnit:
    """Nimmt die gespeicherte Einheit — oder lässt die Heuristik laufen und
    fragt, wenn sie sich nicht sicher ist.
    """
    if params.unit != "auto":
        return cast(LengthUnit, params.unit)

    guess = detect_unit(bounds.diagonal)
    if guess.unit is not None:
        return guess.unit

    choices = [str(unit) for unit in guess.candidates]
    answer = ctx.ask(
        unit_question(bounds.size, guess.candidates),
        choices,
    )
    if answer not in choices:
        raise ValidationError(
            field="unit",
            detail=_("Diese Einheit steht nicht zur Auswahl."),
            value=answer,
            constraint="choices",
            values={"choices": choices},
        )
    return cast(LengthUnit, answer)
