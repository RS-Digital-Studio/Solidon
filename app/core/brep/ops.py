"""B-Rep-Operationen (Bauplan §30, §25, §10).

Angemeldet wie jede andere Operation, damit sie von einer Stelle aus Menü,
Palette, Kommandozeile und Agent erreichen (§10). Anders ist nur eines: ohne
den Kern laufen sie nicht — und sie sagen das mit einem Satz, nicht mit einer
Importspur (§36).

Die Kategorie heißt „Formgebung", nicht nach dem Kern: wer eine Verrundung
sucht, sucht sie neben Fase, Schale und Formschräge — nicht unter einem
Kernel-Namen, den er nie gewählt hat. Nur die Umwandlung wohnt unter „Netz",
weil sie dort endet.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Literal, cast

from app.core.brep import edit, profiles, step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, require
from app.core.errors import (
    CANCEL,
    CORRECT_INPUT,
    GeometryError,
    InternalError,
    NeedsSolidError,
    ValidationError,
)
from app.core.geom.boolean import NOTHING_LEFT_DETAIL, NOTHING_LEFT_TITLE, without_effect
from app.core.geom.hollow import below_printable_wall, hollowed, too_thin
from app.core.geom.prepare import bore_diameter, compensation_findings, over_the_edge
from app.core.geom.prepare_ops import DrillParams
from app.core.geom.transform import Axis
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.types import BaseParams, Finding, OpContext, OpResult, SceneObject
from app.core.units import DEGREE_UNIT, EPS_GEOM, is_close
from app.i18n import _

_CHOICES = edit.EDGE_CHOICES

#: Dieselbe Auswahl bei Verrundung und Fase — deshalb steht der Satz einmal hier.
_CHOICE_DOC = _("Welche Kanten gemeint sind — senkrechte, waagerechte, oben, unten oder alle.")


@op_params
class BrepBoxParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=40.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in X."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=30.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in Y."),
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in Z, also nach oben."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_brep_box",
    title=_("Quader anlegen"),
    category="primitive",
    params=BrepBoxParams,
    consumes=0,
    produces=1,
    doc=_(
        "Legt einen Quader mit echten Kanten an — an sie lassen sich später "
        "Fasen und Verrundungen setzen."
    ),
)
def create_brep_box(ctx: OpContext) -> OpResult:
    params = cast(BrepBoxParams, ctx.params)
    require()
    solid = edit.box(params.width, params.depth, params.height)
    return OpResult(outputs=[_object(params.name or str(_("Quader")), solid)])


@op_params
class BrepCylinderParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Der Kreis bleibt auch beim Vergrößern wirklich rund."),
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Höhe nach oben, von der Standfläche aus."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_brep_cylinder",
    title=_("Zylinder anlegen"),
    category="primitive",
    params=BrepCylinderParams,
    consumes=0,
    produces=1,
    # **Der Vorteil gehört in den Satz, nicht in die Abkürzung.** „B-Rep" sagt
    # einem Kunden nichts; was er wissen will, ist, was er damit kann. Der
    # Quader nebenan sagte es, der Zylinder nicht.
    doc=_(
        "Legt einen Zylinder mit echten Kanten an, stehend auf dem Druckbett — an sie lassen "
        "sich später Fasen und Verrundungen setzen."
    ),
)
def create_brep_cylinder(ctx: OpContext) -> OpResult:
    params = cast(BrepCylinderParams, ctx.params)
    require()
    solid = edit.cylinder(params.diameter, params.height)
    return OpResult(outputs=[_object(params.name or str(_("Zylinder")), solid)])


@op_params
class LoadStepParams(BaseParams):
    source: str = param(
        title=_("Quelle"),
        kind="source",
        doc=_("Die eingebettete STEP-Datei im Projekt."),
    )
    name: str = param(title=_("Name"), default="", doc=_("Leer übernimmt den Dateinamen."))


@register_op(
    name="load_step",
    title=_("STEP laden"),
    category="import",
    params=LoadStepParams,
    consumes=0,
    produces=1,
    doc=_(
        "Liest eine STEP-Datei mit einzeln bearbeitbaren Flächen und Kanten. "
        "STEP trägt seine Einheit selbst — die Einheitenfrage entfällt."
    ),
)
def load_step(ctx: OpContext) -> OpResult:
    params = cast(LoadStepParams, ctx.params)
    require()
    if ctx.sources is None:
        raise InternalError(
            detail="load_step was called without access to the project sources",
            values={"source": params.source},
        )

    source = ctx.sources.describe(params.source)
    if not step.is_step(Path(source.path).suffix):
        raise ValidationError(
            field="source",
            detail=_("Diese Datei ist keine STEP-Datei."),
            value=source.path,
            constraint="not_step",
        )

    solid = step.read(ctx.sources.read(params.source))
    name = params.name or Path(source.path).stem
    entry = _object(name, solid)
    return OpResult(
        outputs=[entry],
        findings=[
            Finding(
                code="brep.loaded",
                severity="info",
                message=_("Flächen und Kanten lassen sich einzeln weiterbearbeiten."),
                values={"faces": solid.face_count, "edges": solid.edge_count},
            )
        ],
    )


@op_params
class FilletParams(BaseParams):
    radius: float = param(
        title=_("Radius"),
        default=2.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_(
            "Radius der Verrundung. Größer als das dünnste angrenzende Material "
            "geht nicht — dann hat der Kern keinen Platz mehr."
        ),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=_CHOICES,
        doc=_("Welche Kanten gemeint sind — senkrechte, waagerechte, oben, unten oder alle."),
    )


@register_op(
    name="fillet_edges",
    requires_kind="brep",
    title=_("Verrunden"),
    category="shaping",
    params=FilletParams,
    consumes=1,
    produces=1,
    doc=_("Verrundet eine bearbeitbare Kante als echte Kurve statt als Folge gerader Abschnitte."),
)
def fillet_edges(ctx: OpContext) -> OpResult:
    params = cast(FilletParams, ctx.params)
    source, body = brep_input(ctx)
    solid = edit.fillet(body, params.radius, cast(edit.EdgeChoice, params.edges))
    return OpResult(outputs=[_replaced(source, solid)])


@op_params
class ChamferParams(BaseParams):
    distance: float = param(
        title=_("Breite"),
        default=1.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_("Wie weit die Fase die Kante zurücknimmt, auf jeder der beiden Flächen."),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=_CHOICES,
        doc=_CHOICE_DOC,
    )


@register_op(
    name="chamfer_edges",
    requires_kind="brep",
    title=_("Fase anbringen"),
    category="shaping",
    params=ChamferParams,
    consumes=1,
    produces=1,
    doc=_("Schrägt bearbeitbare Kanten unter 45 Grad ab."),
)
def chamfer_edges(ctx: OpContext) -> OpResult:
    params = cast(ChamferParams, ctx.params)
    source, body = brep_input(ctx)
    solid = edit.chamfer(body, params.distance, cast(edit.EdgeChoice, params.edges))
    return OpResult(outputs=[_replaced(source, solid)])


@op_params
class ShellParams(BaseParams):
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.2,
        maximum=50.0,
        doc=_(
            "Wie dick die stehenbleibende Wand wird. Mehr als der halbe "
            "Körper geht nicht — dann bleibt innen nichts zum Aushöhlen."
        ),
    )


@register_op(
    name="shell_exact",
    requires_kind="brep",
    title=_("Aushöhlen"),
    category="shaping",
    params=ShellParams,
    consumes=1,
    produces=1,
    doc=_(
        "Höhlt einen Körper mit bearbeitbaren Flächen auf die gewählte Wandstärke "
        "aus und lässt die Oberseite offen — ein Kasten aus einem Quader, in einem "
        "Schritt. Für geschlossenes Aushöhlen mit Entlüftung die Option abwählen."
    ),
    # Der Entlüftungshinweis der Netz-Operation gilt hier nicht: Die Oberseite
    # bleibt offen, es entsteht kein eingeschlossener Hohlraum. Der zweite Satz
    # gilt sehr wohl — wie dünn die Wand wird, entscheidet die Wandstärke und
    # nicht der Rechenkern.
    caveat=_(
        "Nicht bei Teilen, die Kräfte aufnehmen — eine dünne Hülle bricht anders "
        "als ein gefüllter Körper."
    ),
)
def shell_exact(ctx: OpContext) -> OpResult:
    params = cast(ShellParams, ctx.params)
    source, body = brep_input(ctx)
    solid = profiles.shell_open_top(body, params.wall)
    # **Der Zwilling meldete fünf Dinge, dieser keines.** Gemessen über
    # dreizehn Wandstärken an einem Quader 40x30x20: Bei 15 mm kam ein Körper
    # mit Nullspalt zurück — unverändertes Volumen und nicht mehr wasserdicht
    # —, zwischen 16 und 50 passierte in fast allen Fällen gar nichts, und
    # gesagt wurde nie etwas. OCCT gibt bei zu großem negativem Offset die
    # Eingangsform zurück, ohne zu werfen; ein einziger Wert (20 mm) landete
    # überhaupt in einer Ausnahme.
    #
    # Derselbe Befund wie im Netz und aus derselben Quelle (``hollow.too_thin``):
    # Für den Kunden ist es dieselbe Auskunft, gleich woran der Kern es merkt.
    findings: list[Finding] = []
    if is_close(solid.volume, body.volume) or not solid.is_watertight:
        findings.append(too_thin(params.wall))
    else:
        # **Und der Erfolgsfall, der als letzter auseinanderlief.** Nach dem
        # Fix oben meldeten beide Kerne dieselben Warnungen; mit einer
        # Wandstärke, die funktioniert, sagte das Netz ``hollow.done`` und
        # dieser schwieg. Wie viel Material weg ist, ist der Grund, aus dem
        # man aushöhlt — dieselbe Quelle wie beim Zwilling (``hollowed``).
        findings.append(hollowed(params.wall, body.volume - solid.volume))
    # Dieselbe Frage wie beim Netz-Zwilling, aus derselben Quelle: Trägt der
    # Drucker diese Wand? Im Schema stand hier ``minimum=0.2`` und dort 0.4 —
    # zwei Zahlen für eine Regel, die im Profil steht (§39, Regel 7).
    thin = below_printable_wall(params.wall, ctx.profile)
    if thin is not None:
        findings.append(thin)
    return OpResult(outputs=[_replaced(source, solid)], findings=findings)


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
    requires_kind="brep",
    title=_("Formschräge anstellen"),
    category="shaping",
    params=DraftParams,
    consumes=1,
    produces=1,
    doc=_(
        "Stellt alle senkrechten, einzeln bearbeitbaren Flächen um einen Winkel "
        "an — zum Entformen, oder damit ein Stapelbehälter sich stapeln lässt."
    ),
)
def draft_faces(ctx: OpContext) -> OpResult:
    params = cast(DraftParams, ctx.params)
    source, body = brep_input(ctx)
    solid = profiles.draft_vertical(body, params.angle)
    return OpResult(outputs=[_replaced(source, solid)])


@op_params
class ThreadParams(BaseParams):
    diameter: float = param(
        title=_("Nenndurchmesser"),
        default=10.0,
        unit="mm",
        minimum=2.0,
        maximum=100.0,
        doc=_("Außendurchmesser über die Gewindespitzen — das Maß, das M10 meint."),
    )
    pitch: float = param(
        title=_("Steigung"),
        default=1.5,
        unit="mm",
        minimum=0.25,
        maximum=8.0,
        doc=_(
            "Höhenzuwachs je Umdrehung. Grob gedruckte Gewinde wollen eine "
            "grobe Steigung — unter einem Millimeter druckt kaum ein Drucker sauber."
        ),
    )
    length: float = param(
        title=_("Länge"),
        default=12.0,
        unit="mm",
        minimum=1.0,
        maximum=500.0,
        doc=_("Gewindelänge vom Druckbett nach oben, mindestens zwei Gänge."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="thread_exact",
    title=_("Schraube erstellen"),
    # „primitive" und nicht „shaping": Der Bolzen verbraucht nichts und
    # erzeugt einen Körper — dasselbe wie der exakte Quader und der exakte
    # Zylinder daneben. Unter *Ändern → Formgebung* war er der einzige
    # Eintrag, der auf einer leeren Szene anklickbar blieb, während alle
    # sechs Nachbarn ausgegraut waren: ein Erzeugen im Ändern-Menü.
    category="primitive",
    params=ThreadParams,
    consumes=0,
    produces=1,
    doc=_(
        "Ein Bolzen mit echtem helikalem Außengewinde und bearbeitbaren Flächen, "
        "den der STEP-Export trägt. Mit Spiel vergrößert und von einem Körper "
        "abgezogen wird daraus das Innengewinde."
    ),
)
def thread_exact(ctx: OpContext) -> OpResult:
    params = cast(ThreadParams, ctx.params)
    require()
    solid = profiles.threaded_rod(params.diameter, params.pitch, params.length)
    return OpResult(outputs=[_object(params.name or str(_("Gewindebolzen")), solid)])


@register_op(
    name="drill_brep_hole",
    requires_kind="brep",
    title=_("Bohrung setzen"),
    category="holes",
    params=DrillParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    touches_features=True,
    doc=_(
        "Bohrt ein rundes Loch und lässt Flächen und Kanten einzeln bearbeitbar — "
        "Fase, Verrundung und der STEP-Export bleiben danach möglich."
    ),
)
def drill_brep_hole(ctx: OpContext) -> OpResult:
    """Die Bohrung des exakten Kerns.

    **Warum es sie gibt.** Ein exakter Quader und eine Bohrung darin waren
    bisher nicht zusammen zu haben: Die erste Bohrung machte aus dem B-Rep ein
    Netz, und damit fielen Fase, Verrundung, Formschräge, Fläche versetzen,
    exaktes Aushöhlen, Tasche schneiden und der STEP-Export aus. Der Ausweg
    war, jeden Schritt ab dort zurückzunehmen. Eine Bohrung ist die häufigste
    Operation überhaupt — ohne sie endete der exakte Zweig nach einem Schritt.

    **Das Schema ist wörtlich das der Mesh-Bohrung**, und zwar dasselbe Objekt
    und keine Kopie. Nur so trägt ``change_kernel`` einen Schritt von einem
    Kern in den anderen, ohne dass sich die Bohrung ändert (§15.4): Wortgleiche
    Schemata laufen beim nächsten Nachbessern auseinander, dasselbe nicht.

    **Anders als der Zwilling ist sie deterministisch.** ``drill_hole`` trägt
    ``deterministic=False``, weil die Rückfallkette aus §17.2 einen Startwert
    braucht. Hier gibt es keine Kette — zwei B-Rep-Volumen sind sich einig, was
    innen ist, und wo der Schnitt scheitert, ist die Antwort ein Fehler statt
    eines gröberen Versuchs.
    """
    params = cast(DrillParams, ctx.params)
    source, body = brep_input(ctx)
    cut = bore_diameter(params.diameter, ctx.profile, params.compensate)
    solid = edit.bore(
        body,
        position=(params.x, params.y, params.z),
        axis=cast(Literal["x", "y", "z"], params.axis),
        diameter=cut,
        depth=params.depth,
        anchor=cast(Literal["mouth", "centre"], params.anchor),
    )
    # **Und zuerst: ist überhaupt noch ein Körper da?** Ein Werkzeug, das den
    # Körper vollständig deckt, lässt OCCT sauber durchrechnen und nichts
    # übrig — null Volumen, null Flächen, nicht wasserdicht. Bis zum
    # 27.08.2026 kam das als Erfolg zurück: Im Objektbaum stand ein Objekt mit
    # Namen, das man anklicken, umbenennen und **speichern** konnte, und der
    # Prüfbericht sagte kein Wort. Gemeldet hätte es erst der Export.
    #
    # Der Netz-Zwilling wirft an dieser Stelle seit je, mit genau diesem Satz
    # (``boolean.py``, Ende der Rückfallkette) — er ist deshalb von dort
    # geteilt und nicht ein zweites Mal geschrieben. ``without_effect``
    # darunter fängt den Fall nicht: Es prüft auf *nichts abgetragen*, hier
    # wurde *alles* abgetragen.
    if solid.volume <= EPS_GEOM or solid.face_count == 0:
        raise GeometryError(
            title=NOTHING_LEFT_TITLE,
            detail=NOTHING_LEFT_DETAIL,
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    findings: list[Finding] = []
    # **Wer Boolesches rechnet, fragt danach — ohne Ausnahme.** Der
    # Netz-Zwilling meldete eine Bohrung, die den Körper verfehlt; dieser hier
    # schwieg, obwohl er dieselbe Differenz rechnet. Gemessen an einem exakten
    # Quader mit einer Bohrung weit daneben: Volumen vorher wie nachher, keine
    # Zeile im Bericht. ``Solid`` trägt sein ``volume``, also braucht es dafür
    # keine Vernetzung.
    nothing = without_effect(body, solid, "difference", ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    # **Und der Fall dazwischen**, der laut Docstring von ``over_the_edge`` der
    # gefährlichere ist: Es wird etwas abgetragen, also schweigt jede Prüfung,
    # und heraus kommt eine Bohrung mit offener Flanke. Gemessen fehlte er dem
    # exakten Zwilling in sechs von sechs Fällen, bei geometrisch identischem
    # Ergebnis — nicht weil der Kern ihn nicht könnte, sondern weil die
    # Signatur ein ``MeshData`` verlangte. Sie fragt jetzt nach dem, was sie
    # wirklich braucht, und ``Solid`` trägt seinen Hüllquader.
    findings.extend(
        over_the_edge(
            body,
            (params.x, params.y, params.z),
            cast(Axis, params.axis),
            cut,
        )
    )
    findings.extend(compensation_findings(params.diameter, cut, params.compensate))
    return OpResult(outputs=[_replaced(source, solid)], findings=findings)


@op_params
class ToMeshParams(BaseParams):
    # **Vorn, obwohl es eine Feinheit ist.** Es ist das einzige Feld dieser
    # Operation, und hinten ergab das einen Dialog aus einem Satz und einem
    # leeren Aufklapper — nichts zu entscheiden, und trotzdem OK klicken.
    # Vor allem aber ist die Umwandlung unumkehrbar (siehe doc): Wer mit
    # 0,05 mm umwandelt und danach merkt, dass es zu grob war, muss den
    # Schritt zurücknehmen — und dafür muss er wissen, dass es die
    # Einstellung überhaupt gibt.
    deflection: float = param(
        title=_("Feinheit"),
        default=0.05,
        unit="mm",
        minimum=0.001,
        maximum=1.0,
        placement="front",
        doc=_("Wie weit die Dreiecke von der echten Fläche abweichen dürfen."),
    )


@register_op(
    name="brep_to_mesh",
    requires_kind="brep",
    title=_("Flächenbearbeitung beenden"),
    category="mesh",
    params=ToMeshParams,
    consumes=1,
    produces=1,
    doc=_(
        "Macht aus den einzeln bearbeitbaren Flächen feste Dreiecke. Danach lassen "
        "sich einzelne Kanten nicht mehr fasen oder verrunden; Rückgängig stellt "
        "den vorherigen Zustand wieder her."
    ),
)
def brep_to_mesh(ctx: OpContext) -> OpResult:
    """§30: die Einbahntür — und ein Schritt im Stapel, damit sie sich
    zurücknehmen lässt.

    Zurückgenommen von einem Undo, nicht von einer Rekonstruktion: die
    Operation bleibt im Verlauf, und sie zu entfernen bringt den exakten
    Körper zurück, weil der Stapel neu gerechnet und nicht geflickt wird.
    """
    params = cast(ToMeshParams, ctx.params)
    source, body = brep_input(ctx)
    mesh = Solid(shape=body.shape, deflection=params.deflection).to_mesh()
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh, kind="mesh", features={})],
        findings=[
            Finding(
                code="brep.converted",
                severity="info",
                message=_(
                    "Flächen und Kanten sind jetzt feste Dreiecke und nicht mehr einzeln "
                    "bearbeitbar. Rückgängig stellt den vorherigen Zustand wieder her."
                ),
                object_id=source.id,
                values={"triangles": mesh.triangle_count},
            )
        ],
    )


def brep_input(ctx: OpContext) -> tuple[SceneObject, Solid]:
    """Die Eingabe und ihr exakter Körper — oder ein klarer Satz, wenn es ein
    Netz ist (§33.1).

    Kein ``ValidationError``: dessen Titel lautet „Ein Wert liegt außerhalb des
    zulässigen Bereichs", und hier ist kein Wert außerhalb eines Bereichs —
    hier hat der Körper die falsche Art. Im Prüfbericht stand deshalb eine
    Fehlermeldung über Zahlen an einer Stelle, an der keine Zahl schuld war.

    **Öffentlich und einmal**, seit dem 04.09.2026: ``sketch.ops`` trug eine
    wortgleiche Kopie mitsamt eigenem Katalogeintrag in sechs Sprachen. Die
    beiden Sätze waren schon auseinandergelaufen — der hiesige nannte das
    Aushöhlen nicht, obwohl ``hollow_object`` genau der Weg ist, auf dem ein
    exakter Körper zum Netz wird (aufgefallen an ``puppenhaus_fertig``). Der
    umfassendere Satz hat gewonnen.
    """
    require()
    source = ctx.inputs[0]
    if not isinstance(source.mesh, Solid):
        raise NeedsSolidError(
            # Ohne Platzhalter: TranslatableText löst nur den Katalog auf und
            # formatiert nicht — ein „{name}" stünde dem Nutzer wörtlich da.
            # Der Name reist wie überall in ``values``.
            detail=_(
                "Der gewählte Körper besteht bereits aus festen Dreiecken. Dieses "
                "Werkzeug braucht einzeln bearbeitbare Flächen und Kanten. Aktiviere "
                "dafür bei einer Grundform oder beim Aushöhlen „Flächen und Kanten "
                "später bearbeiten“ oder öffne eine STEP-Datei."
            ),
            values={"name": source.name, "field": "in", "constraint": "needs_brep"},
            object_id=source.id,
        )
    return source, source.mesh


def _object(name: str, solid: Solid) -> SceneObject:
    return SceneObject(id="", name=name, mesh=solid, kind="brep", features=features_of(solid))


def _replaced(source: SceneObject, solid: Solid) -> SceneObject:
    return dataclasses.replace(source, mesh=solid, kind="brep", features=features_of(solid))


__all__ = [
    "brep_to_mesh",
    "chamfer_edges",
    "create_brep_box",
    "create_brep_cylinder",
    "draft_faces",
    "drill_brep_hole",
    "fillet_edges",
    "load_step",
    "shell_exact",
    "thread_exact",
]
