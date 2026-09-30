"""B-Rep-Operationen (Bauplan §30, §25, §10).

Angemeldet wie jede andere Operation, damit sie von einer Stelle aus Menü,
Palette, Kommandozeile und Agent erreichen (§10). Anders ist nur eines: ohne
den Kern laufen sie nicht — und sie sagen das mit einem Satz, nicht mit einer
Importspur (§36).

Die Kategorie heißt „Formgebung", nicht nach dem Kern: wer eine Verrundung
sucht, sucht sie neben Fase, Schale und Formschräge — nicht unter einem
Kernel-Namen, den er nie gewählt hat. Nur die beiden Umwandlungen wohnen unter
„Netz": die eine endet dort, die andere beginnt dort (P4.0).
"""

from __future__ import annotations

import dataclasses
import math
from typing import Final, Literal, cast

import numpy as np

from app.core.brep import edit, from_mesh, profiles
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, require
from app.core.errors import (
    CANCEL,
    CORRECT_INPUT,
    DECIMATE_MESH,
    REPAIR_AND_RETRY,
    GeometryError,
    NeedsSolidError,
    NotManifoldError,
    UserError,
    ValidationError,
)
from app.core.geom.boolean import NOTHING_LEFT_DETAIL, NOTHING_LEFT_TITLE, without_effect
from app.core.geom.hollow import below_printable_wall, hollowed, too_thin
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.ops import as_transform
from app.core.geom.prepare import (
    bore_diameter,
    compensation_findings,
    drill_outline,
    over_the_edge,
    over_the_edge_along,
    slot_ends,
    slot_frame,
    slot_profile,
    slot_travel,
    split_findings,
)
from app.core.geom.prepare_ops import DrillParams, bore_shape
from app.core.geom.primitive_ops import (
    ANCHORS,
    PositionedPrimitiveParams,
    placement_transform,
    tube_fits_the_ring,
)
from app.core.geom.transform import Axis
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.types import (
    BaseParams,
    CancelToken,
    Feature,
    Finding,
    OpContext,
    OpResult,
    PlaneFrame,
    Profile,
    SceneObject,
    Vec3,
)
from app.core.units import EPS_GEOM, MAX_FACET_SAG, is_close
from app.i18n import TranslatableText, _


@op_params
class BrepBoxParams(PositionedPrimitiveParams):
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
    # Derselbe Bezugspunkt wie am Netz-Zwilling (P2.8): Seit der exakte Quader
    # der sichtbare ist, darf ihm kein Feld fehlen, das der Kunde hatte.
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="centre",
        choices=ANCHORS,
        placement="advanced",
        doc=_("Mittig auf dem Ursprung oder mit der Ecke darauf."),
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
    # Dieselbe Lage wie beim Netz-Zwilling: Position, Richtung und Bezugspunkt
    # sind Felder beider Dialoge, und der Tausch zwischen den Kernen behält sie.
    body = edit.box(params.width, params.depth, params.height)
    matrix = np.asarray(placement_transform(params), dtype=float)
    if str(params.anchor) == "corner":
        # Bezugspunkt und Lage sind eine Bewegung, nicht zwei: erst die Ecke
        # auf den Ursprung, dann die Lage — als eine Matrix, damit der Körper
        # einmal geprüft und kopiert wird statt zweimal.
        shift = np.eye(4)
        shift[:3, 3] = (params.width / 2.0, params.depth / 2.0, 0.0)
        matrix = matrix @ shift
    solid = edit.transformed(body, as_transform(matrix), cancelled=ctx.cancelled)
    return OpResult(
        outputs=[_object(params.name or str(_("Quader")), solid, cancelled=ctx.cancelled)]
    )


@op_params
class BrepCylinderParams(PositionedPrimitiveParams):
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
    solid = edit.transformed(
        edit.cylinder(params.diameter, params.height),
        placement_transform(params),
        cancelled=ctx.cancelled,
    )
    return OpResult(
        outputs=[_object(params.name or str(_("Zylinder")), solid, cancelled=ctx.cancelled)]
    )


@op_params
class BrepConeParams(PositionedPrimitiveParams):
    """Dieselben Felder wie ``ConeParams`` am Netz, ohne ``segments`` — ein Kegel des
    exakten Kerns hat keine Segmente."""

    bottom_diameter: float = param(
        title=_("Unterer Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        doc=_("Durchmesser auf dem Druckbett. Null macht diese Seite zur Spitze."),
    )
    top_diameter: float = param(
        title=_("Oberer Durchmesser"),
        default=10.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        doc=_("Durchmesser an der Oberseite. Null macht diese Seite zur Spitze."),
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
    name="create_brep_cone",
    title=_("Kegel anlegen"),
    category="primitive",
    params=BrepConeParams,
    consumes=0,
    produces=1,
    doc=_(
        "Legt einen Kegel oder Kegelstumpf mit einer echten Kegelfläche an, stehend auf dem "
        "Druckbett — an seine Kanten lassen sich später Fasen und Verrundungen setzen."
    ),
)
def create_brep_cone(ctx: OpContext) -> OpResult:
    params = cast(BrepConeParams, ctx.params)
    require()
    if params.bottom_diameter <= EPS_GEOM and params.top_diameter <= EPS_GEOM:
        raise ValidationError(
            "bottom_diameter",
            _("Mindestens einer der beiden Durchmesser muss größer als null sein."),
            value=params.bottom_diameter,
            constraint="range",
        )
    # Zwei gleiche Radien sind für ``BRepPrimAPI_MakeCone`` ein Fehler
    # (``Standard_DomainError``), für den Kunden ein Zylinder — der Netz-Zwilling
    # baut ihn, ohne zu fragen, und die Vorgaben 20/10 liegen einen Tastendruck
    # davon entfernt (Review, 21.09.2026).
    body = (
        edit.cylinder(params.bottom_diameter, params.height)
        if is_close(params.bottom_diameter, params.top_diameter)
        else edit.cone(params.bottom_diameter, params.top_diameter, params.height)
    )
    solid = edit.transformed(body, placement_transform(params), cancelled=ctx.cancelled)
    fallback = (
        _("Kegel")
        if params.bottom_diameter <= EPS_GEOM or params.top_diameter <= EPS_GEOM
        else _("Kegelstumpf")
    )
    return OpResult(outputs=[_object(params.name or str(fallback), solid, cancelled=ctx.cancelled)])


@op_params
class BrepSphereParams(PositionedPrimitiveParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Die Kugel sitzt auf dem Druckbett auf."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_brep_sphere",
    title=_("Kugel anlegen"),
    category="primitive",
    params=BrepSphereParams,
    consumes=0,
    produces=1,
    doc=_("Legt eine Kugel mit einer echten Kugelfläche an, aufsitzend auf dem Druckbett."),
)
def create_brep_sphere(ctx: OpContext) -> OpResult:
    params = cast(BrepSphereParams, ctx.params)
    require()
    solid = edit.transformed(
        edit.moved(edit.sphere(params.diameter), (0.0, 0.0, params.diameter / 2.0)),
        placement_transform(params),
        cancelled=ctx.cancelled,
    )
    return OpResult(
        outputs=[_object(params.name or str(_("Kugel")), solid, cancelled=ctx.cancelled)]
    )


@op_params
class BrepTorusParams(PositionedPrimitiveParams):
    outer_diameter: float = param(
        title=_("Außendurchmesser"),
        default=40.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Gesamter Durchmesser von Außenkante zu Außenkante."),
    )
    tube_diameter: float = param(
        title=_("Schnurstärke"),
        default=8.0,
        unit="mm",
        minimum=0.1,
        maximum=500.0,
        doc=_("Durchmesser des runden Ringquerschnitts."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_brep_torus",
    title=_("Ring anlegen"),
    category="primitive",
    params=BrepTorusParams,
    consumes=0,
    produces=1,
    doc=_(
        "Legt einen Ring mit einer echten Ringfläche an, liegend auf dem Druckbett — der "
        "Querschnitt bleibt auch beim Vergrößern wirklich rund."
    ),
)
def create_brep_torus(ctx: OpContext) -> OpResult:
    params = cast(BrepTorusParams, ctx.params)
    require()
    tube_fits_the_ring(params.outer_diameter, params.tube_diameter)
    minor = params.tube_diameter / 2.0
    solid = edit.transformed(
        edit.torus(
            (0.0, 0.0, minor),
            (0.0, 0.0, 1.0),
            params.outer_diameter - params.tube_diameter,
            params.tube_diameter,
        ),
        placement_transform(params),
        cancelled=ctx.cancelled,
    )
    return OpResult(
        outputs=[_object(params.name or str(_("Ring")), solid, cancelled=ctx.cancelled)]
    )


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
        "Schritt."
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
    solid = profiles.shell_open_top(body, params.wall, cancelled=ctx.cancelled)
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
    return OpResult(outputs=[_replaced(source, solid, cancelled=ctx.cancelled)], findings=findings)


@op_params
class ThreadParams(PositionedPrimitiveParams):
    """Der Bolzen trägt dieselben sieben Lagefelder wie die Grundkörper.

    Er verbraucht nichts und erzeugt einen Körper — dasselbe wie der exakte
    Quader und der exakte Zylinder daneben —, stand aber als einziger Erzeuger
    des Menüs *Erzeugen* ohne Ort, Richtung und Drehung da. Der Griff an der
    Vorschau hängt genau daran (``placement_flow._grips_its_preview``): Ohne
    Felder, in die ein Zug schreiben kann, bewegte er ein Bild, das beim
    nächsten Neuzeichnen zurückspränge (Robert, 09.09.2026: „alle Körper, die
    man über Erzeugen setzen kann").
    """

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
    # Dieselbe Lage wie bei Quader und Zylinder daneben: Der Bolzen wächst
    # vom Ursprung nach oben, und die Platzierung setzt ihn dorthin, wo der
    # Dialog oder der Griff an der Vorschau ihn hinstellt.
    placement = placement_transform(params)
    matrix = np.asarray(placement, dtype=float)
    solid = edit.transformed(
        profiles.threaded_rod(
            params.diameter, params.pitch, params.length, cancelled=ctx.cancelled
        ),
        placement,
        cancelled=ctx.cancelled,
    )
    # Der Erzeuger kennt den Gang genau; die analytischen Einzelflächen allein
    # beschreiben seine Steigung nicht. Die ebenen Anschnitte bleiben separat
    # auswählbar, der übrige Mantel gehört zum benannten Gewinde — und der
    # Leser für eingelesene Gewinde muss ihn nicht erst suchen
    # (``features_of(known_threads=…)``).
    #
    # **Eben sind genau die zwei Schnittflächen des Quaders**, mit dem
    # ``threaded_rod`` den Bolzen auf Länge schneidet: Ihr Träger ist eine
    # ``Geom_Plane``, jede Gangfläche eine Regelfläche, und die Platzierung
    # ist eine Ähnlichkeit, die Trägerarten erhält. Gefragt wird deshalb die
    # Art des nativen Trägers wie in ``canonical.horizontal_area``, nicht der
    # Beweis der Trägerprüfung — der ging über jede Gangfläche, am
    # M3 x 0,5 x 60 363 Flächen und 0,47 s für zwei bekannte Antworten
    # (Review 23.09.2026).
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    ends = {
        triangle
        for index, face in enumerate(solid.faces())
        if BRepAdaptor_Surface(face, False).GetType() == GeomAbs_Plane
        for triangle in solid.triangles_of_face(index)
    }
    # **Das Merkmal beschreibt dieselbe Lage wie der Körper.** Mitte und Achse
    # gingen als feste Zahlen ein — richtig, solange der Bolzen immer im
    # Ursprung stand und nach +Z zeigte. Seit er eine Lage hat, müssen sie
    # durch dieselbe Matrix wie seine Dreiecke: Sonst benennt das Gewinde eine
    # Achse, an der nichts liegt, und eine Passung dagegen zielt ins Leere.
    middle = matrix @ (0.0, 0.0, params.length / 2.0, 1.0)
    centre = (float(middle[0]), float(middle[1]), float(middle[2]))
    pointing = matrix[:3, :3] @ (0.0, 0.0, 1.0)
    axis = (float(pointing[0]), float(pointing[1]), float(pointing[2]))
    thread = Feature(
        id="thread_1",
        kind="thread",
        provenance="generated",
        params={
            "diameter": params.diameter,
            "pitch": params.pitch,
            # profiles.threaded_rod folgt (Winkel, Höhe) = (2π, Steigung).
            "handedness": "right",
            "length": params.length,
            "centre": centre,
            "axis": axis,
            "internal": False,
        },
        face_indices=tuple(index for index in range(solid.triangle_count) if index not in ends),
    )
    entry = SceneObject(
        id="",
        name=params.name or str(_("Gewindebolzen")),
        mesh=solid,
        kind="brep",
        features=features_of(solid, cancelled=ctx.cancelled, known_threads=(thread,)),
    )
    return OpResult(outputs=[entry])


@register_op(
    name="drill_brep_hole",
    requires_kind="brep",
    # 1: ein Langloch zählt seinen Winkel gegen ``prepare.slot_frame`` (30.09.2026).
    cache_version="1",
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
    from app.core.knowledge.profiles import for_object

    params = cast(DrillParams, ctx.params)
    source, body = brep_input(ctx)
    profile = for_object(ctx.profile, source)
    cut = bore_diameter(params.diameter, profile, params.compensate)
    normal = (params.nx, params.ny, params.nz)
    if not all(math.isfinite(value) for value in normal):
        raise ValidationError("nx", _("Wählen Sie eine endliche Richtung für die Bohrung."))
    shape = bore_shape(params, within=body)
    if shape.slot_length > EPS_GEOM:
        solid, normal = _slotted_bore(body, params, profile)
    elif math.hypot(*normal) > EPS_GEOM or abs(shape.widening_diameter) > EPS_GEOM:
        solid, normal = _profiled_bore(body, params, profile)
    else:
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
    # Am Zwilling gefragt, nicht am exakten Integral (Durchsicht 0.5.1,
    # BOHRUNG-10): An einer BSpline-Rundung kostet es eine halbe Minute.
    if solid.face_count == 0 or as_mesh_data(solid).volume <= EPS_GEOM:
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
    nothing = without_effect(body, solid, "difference", profile)
    if nothing is not None:
        findings.append(nothing)
    # **Und der Fall dazwischen**, der laut Docstring von ``over_the_edge`` der
    # gefährlichere ist: Es wird etwas abgetragen, also schweigt jede Prüfung,
    # und heraus kommt eine Bohrung mit offener Flanke. Gemessen fehlte er dem
    # exakten Zwilling in sechs von sechs Fällen, bei geometrisch identischem
    # Ergebnis — nicht weil der Kern ihn nicht könnte, sondern weil die
    # Signatur ein ``MeshData`` verlangte. Sie fragt jetzt nach dem, was sie
    # wirklich braucht, und ``Solid`` trägt seinen Hüllquader.
    # Die halbe Länge der Bohrung um ihre Mitte (RM-249); durchgehend der
    # ganze Körper. Am Mündungsanker liegt die Mitte eine halbe Tiefe im
    # Material — gegen die Normale der Fläche, an einer Hauptachse in die
    # Hälfte des Hüllquaders, in die ``edit.bore`` bohrt (Durchsicht 0.5.1,
    # BOHRUNG-01: vor der Mündung gefragt, stand dort Material einer Wand
    # daneben, das die Bohrung nie berührt).
    position = (params.x, params.y, params.z)
    way = [0.0, 0.0, 0.0]
    if math.hypot(*normal) > EPS_GEOM:
        size = math.hypot(*normal)
        way = [value / size for value in normal]
    else:
        way["xyz".index(params.axis)] = 1.0
    reach = params.depth / 2.0
    along = 0.0
    if params.depth <= EPS_GEOM:
        # Durchgehend: die Ausdehnung des Körpers entlang der Achse, um ihre
        # Mitte — wie am Netz (``prepare.drill``). Mit der Hüllendiagonale lagen
        # die Tiefen elf Millimeter auseinander und übersprangen einen Absatz.
        low, high = body.bounds.minimum, body.bounds.maximum
        reach = sum(abs(w) * (b - a) for w, a, b in zip(way, low, high, strict=True)) / 2.0
        along = sum(
            w * ((a + b) / 2.0 - p) for w, a, b, p in zip(way, low, high, position, strict=True)
        )
    elif params.anchor == "mouth":
        if math.hypot(*normal) > EPS_GEOM:
            along = -params.depth / 2.0
        else:
            index = "xyz".index(params.axis)
            into = -1.0 if position[index] >= body.bounds.centre[index] else 1.0
            along = into * params.depth / 2.0
    if shape.slot_length > EPS_GEOM:
        # Ein Langloch steckt in der Mitte tief im Material und reißt trotzdem
        # an einem Ende auf — gefragt wird deshalb an beiden Bogenmittelpunkten
        # und gemeldet höchstens einmal, wie im Netz-Zwilling; im Rahmen des
        # Schnitts (``slot_frame``).
        travel = slot_travel(diameter=params.diameter, length=shape.slot_length)
        for end in slot_ends(
            (params.x, params.y, params.z),
            slot_frame(normal, (params.x, params.y, params.z)),
            travel,
            shape.slot_angle,
        ):
            found = over_the_edge_along(
                body, end, normal, cut, body=as_mesh_data(body), reach=reach, along=along
            )
            if found:
                findings.extend(found)
                break
    elif math.hypot(*normal) > EPS_GEOM:
        findings.extend(
            over_the_edge_along(
                body,
                (params.x, params.y, params.z),
                normal,
                cut,
                body=as_mesh_data(body),
                reach=reach,
                along=along,
            )
        )
    else:
        findings.extend(
            over_the_edge(
                body,
                (params.x, params.y, params.z),
                cast(Axis, params.axis),
                cut,
                body=as_mesh_data(body),
                reach=reach,
                along=along,
            )
        )
    findings.extend(split_findings(body, solid))
    findings.extend(compensation_findings(params.diameter, cut, params.compensate))
    return OpResult(outputs=[_replaced(source, solid, cancelled=ctx.cancelled)], findings=findings)


def _bore_span(
    body: Solid, params: DrillParams, widening_diameter: float, *, slotted: bool = False
) -> tuple[PlaneFrame, float, float]:
    """Rahmen, Werkzeuglänge und Mündungslage einer exakten Bohrung.

    Geteilt zwischen dem Rotationskörper und dem Langloch, weil beide dieselbe
    Frage haben: Wohin zeigt die Bohrung, wie lang muss das Werkzeug sein, und
    wo liegt seine Mündung. Nur der Körper dazwischen ist ein anderer — und am
    Langloch der Rahmen des Winkels (``slotted``: :func:`slot_frame`).
    """
    from itertools import product

    from app.core.sketch.planes import frame_of

    position = (params.x, params.y, params.z)
    normal = (params.nx, params.ny, params.nz)
    if math.hypot(*normal) <= EPS_GEOM:
        index = "xyz".index(params.axis)
        values = [0.0, 0.0, 0.0]
        values[index] = 1.0 if position[index] >= body.bounds.centre[index] else -1.0
        normal = (values[0], values[1], values[2])
    frame = slot_frame(normal, position) if slotted else frame_of(normal, position)
    if params.depth <= EPS_GEOM:
        box = body.bounds
        corners = product(*zip(box.minimum, box.maximum, strict=True))
        projected = [
            sum((point[i] - position[i]) * frame.normal[i] for i in range(3)) for point in corners
        ]
        low, high = min(projected), max(projected)
        if widening_diameter > EPS_GEOM and params.anchor == "mouth":
            height, mouth = -low, 0.0
        else:
            height, mouth = high - low, high
    else:
        height = params.depth
        mouth = height / 2.0 if params.anchor == "centre" else 0.0
    return frame, height, mouth


def _profiled_bore(body: Solid, params: DrillParams, profile: Profile) -> tuple[Solid, Vec3]:
    """Legt das gemeinsame Profil mit seiner Mündung auf die gewählte Fläche."""
    position = (params.x, params.y, params.z)
    shape = bore_shape(params)
    frame, height, mouth = _bore_span(body, params, shape.widening_diameter)
    outline = drill_outline(
        diameter=params.diameter,
        depth=height,
        profile=profile,
        compensate=params.compensate,
        widening_diameter=shape.widening_diameter,
        widening_depth=shape.widening_depth,
        transition_angle=params.transition_angle,
    )
    frame = dataclasses.replace(
        frame, origin=cast(Vec3, tuple(position[i] + mouth * frame.normal[i] for i in range(3)))
    )
    return edit.bore_profile(body, outline, frame), frame.normal


def _slotted_bore(body: Solid, params: DrillParams, profile: Profile) -> tuple[Solid, Vec3]:
    """Das Langloch des exakten Kerns — derselbe Umriss, als Prisma statt als Netz.

    **Aufgezogen wird vom Boden zur Mündung**, nicht umgekehrt: ``extrude``
    verlangt eine positive Höhe, und ein Rahmen mit umgekehrter Normale wäre
    linkshändig — der Winkel des Langlochs drehte darin in die andere Richtung
    als im Netz-Kern. Dieselbe Ebene und dieselbe Höhe, nur ein anderer
    Ursprung, und beide Kerne meinen mit ``slot_angle`` dasselbe.
    """
    from app.core.brep.profiles import extrude

    position = (params.x, params.y, params.z)
    shape = bore_shape(params)
    frame, height, mouth = _bore_span(body, params, 0.0, slotted=True)
    travel = slot_travel(diameter=params.diameter, length=shape.slot_length)
    radius = bore_diameter(params.diameter, profile, params.compensate) / 2.0
    floor = dataclasses.replace(
        frame,
        origin=cast(
            Vec3, tuple(position[i] + (mouth - height) * frame.normal[i] for i in range(3))
        ),
    )
    tool = extrude(
        slot_profile(radius=radius, travel=travel, angle_deg=shape.slot_angle),
        height,
        frame=floor,
    )
    return edit.boolean("difference", [body, tool]), frame.normal


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
    result_kind="mesh",
    cache_version="2",
    requires_kind="brep",
    title=_("Flächenbearbeitung beenden"),
    category="mesh",
    params=ToMeshParams,
    consumes=1,
    produces=1,
    doc=_(
        "Wandelt die exakte Geometrie in ein Dreiecksnetz um. Weitere Bearbeitungen "
        "wie Fasen und Verrundungen rechnen am Netz. Rückgängig stellt den exakten "
        "Körper wieder her."
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
    # tessellate besitzt seine Arbeitskopie; ein weiterer Solid würde hier
    # dieselbe Eingabe vor der eigentlichen Vernetzung unnötig doppelt kopieren.
    mesh = body.to_mesh(deflection=params.deflection)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh, kind="mesh", features={})],
        findings=[converted_finding(source, mesh)],
    )


CONVERTED_NOTICE = _(
    "Die exakten Flächen und Kanten sind jetzt feste Dreiecke. Weitere "
    "Bearbeitungen rechnen am Netz. Rückgängig stellt den exakten Körper wieder her."
)


def converted_finding(source: SceneObject, mesh: MeshData) -> Finding:
    """Eine beabsichtigte Vernetzung benennt den Verlust der exakten Geometrie."""
    return Finding(
        code="brep.converted",
        severity="info",
        message=CONVERTED_NOTICE,
        object_id=source.id,
        values={"triangles": mesh.triangle_count},
    )


@op_params
class MeshToExactParams(BaseParams):
    # **Vorn, und das einzige Feld** — aus demselben Grund wie die Feinheit
    # der Gegenrichtung: Wer an einem gescannten oder neu vernetzten Modell
    # zu viel als Dreiecke zurückbekommt, muss wissen, dass er die Grenze
    # weiter stellen kann.
    tolerance: float = param(
        title=_("Erlaubte Abweichung"),
        default=from_mesh.DEFAULT_TOLERANCE,
        unit="mm",
        minimum=0.001,
        maximum=0.2,
        placement="front",
        doc=_(
            "Wie weit eine Ecke des Netzes neben ihrer Fläche liegen darf. Größer nimmt grobe "
            "Netze auf."
        ),
    )


#: Was die Leiste während der Umwandlung sagt — je Stufe von ``convert``.
_STAGES: dict[str, TranslatableText] = {
    "regions": _("Flächen zuordnen …"),
    "edges": _("Kanten bestimmen …"),
    "faces": _("Flächen bauen …"),
    "body": _("Körper schließen …"),
    "measure": _("Abweichung messen …"),
}


@register_op(
    name="mesh_to_exact",
    result_kind="brep",
    cache_version="1",
    requires_kind="mesh",
    title=_("In Flächen und Kanten umwandeln"),
    category="mesh",
    params=MeshToExactParams,
    consumes=1,
    produces=1,
    doc=_(
        "Macht aus einem Dreiecksnetz einen Körper mit echten Flächen und Kanten — Ebenen, "
        "Zylinder, Kegel, Kugeln und Ringe. Danach geht STEP, und Bohrungen, Kanten und "
        "Flächen lassen sich bearbeiten; einen Konstruktionsverlauf hat er nicht. Was auf "
        "keiner erkannten Fläche liegt, bleibt ebene Dreiecke; der Prüfbericht nennt Anteil "
        "und Abweichung."
    ),
    # Wann sie die falsche Wahl ist (Vertrag von ``caveat``), nicht ihre Grenze —
    # die steht im doc-Satz davor.
    caveat=_(
        "Nicht für organische Formen wie Figuren oder Scans: Ihre freie Form bleibt "
        "Dreiecke. Zum Drucken und für STL oder 3MF ist die Umwandlung nicht nötig."
    ),
)
def mesh_to_exact(ctx: OpContext) -> OpResult:
    """P4.0: das Netz als Körper mit analytischen Flächen, ohne Verlauf.

    Die Gegenrichtung zu :func:`brep_to_mesh` und wie sie ein Schritt im
    Stapel: Das Netz bleibt im Schritt davor, ein Undo holt es zurück (§30).
    Die Arbeit tut :func:`app.core.brep.from_mesh.convert`; hier werden ihre
    Absagen zu Sätzen mit Handlung (Regel 17) und ihre Messungen zu Befunden.

    ``ctx.quality`` ändert hier **bewusst nichts**. Das Ergebnis ist ein
    exakter Körper; eine Entwurfsfassung wäre ein anderer Körper mit anderen
    Flächen, und alles, was danach an ihm rechnet, hinge an der Stufe. Auch
    die Messung bleibt gleich — eine Abweichung, die beim Umschalten auf
    „Fein“ anders hieße, wäre keine Auskunft.
    """
    from app.core.perceive.features import detect

    params = cast(MeshToExactParams, ctx.params)
    require()
    source = ctx.inputs[0]
    if isinstance(source.mesh, Solid):
        raise UserError(
            _("Der Körper hat bereits echte Flächen und Kanten."),
            _("Seine Flächen und Kanten lassen sich direkt bearbeiten."),
            suggestions=(CANCEL,),
            values={"name": source.name},
            object_id=source.id,
        )
    mesh = as_mesh_data(source.mesh)
    ctx.progress(0.0, str(_STAGES["regions"]))
    # Dieselbe Erkennung wie die Auswertung — ihr Merker liefert sie, wenn der
    # Körper schon untersucht ist. ``source.features`` genügt nicht: In der
    # Vorschau eines Dialogs erkennt die Auswertung nur, was ein späterer
    # Schritt braucht, und die Umwandlung braucht alles.
    features = detect(mesh, check_cancelled=ctx.cancelled.raise_if_cancelled)

    def progress(fraction: float, stage: str) -> None:
        ctx.progress(0.05 + 0.95 * fraction, str(_STAGES.get(stage, _STAGES["faces"])))

    try:
        conversion = from_mesh.convert(
            mesh,
            features,
            tolerance=params.tolerance,
            cancelled=ctx.cancelled,
            progress=progress,
        )
    except from_mesh.OpenSurfaceError as problem:
        raise NotManifoldError(
            _("Das Netz ist nicht dicht. Reparieren Sie es, dann lässt es sich umwandeln."),
            suggestions=(REPAIR_AND_RETRY, CANCEL),
            object_id=source.id,
        ) from problem
    except from_mesh.ConversionRefusedError as refusal:
        raise _refusal(refusal, source) from refusal
    output = _replaced(source, conversion.solid, cancelled=ctx.cancelled)
    return OpResult(outputs=[output], findings=conversion_findings(source, conversion, params))


def _refusal(refusal: from_mesh.ConversionRefusedError, source: SceneObject) -> GeometryError:
    """Die Absage der Umwandlung als Satz mit Handlung (Regel 17)."""
    if refusal.reason == "freeform":
        return GeometryError(
            _("Dieses Modell ist zum größten Teil freie Form."),
            _(
                "Kaum ein Dreieck liegt auf einer erkennbaren Fläche, und jedes würde eine "
                "eigene. Freie Formen bleiben besser ein Netz; mit weniger Dreiecken geht die "
                "Umwandlung trotzdem."
            ),
            suggestions=(DECIMATE_MESH, CANCEL),
            values={
                "triangles": refusal.values.get("triangles", 0),
                "limit": from_mesh.MAX_FREEFORM_FACES,
            },
            object_id=source.id,
        )
    return GeometryError(
        _("Aus den erkannten Flächen ließ sich kein geschlossener Körper bauen."),
        _(
            "Die Flächen schließen an ihren Rändern nicht dicht. Eine größere erlaubte "
            "Abweichung oder eine Reparatur des Netzes kann helfen."
        ),
        suggestions=(CORRECT_INPUT, REPAIR_AND_RETRY, CANCEL),
        values={"reason": refusal.reason},
        object_id=source.id,
    )


#: Ab welcher Abweichung die Umwandlung mehr als eine Auskunft ist: die
#: Sehnenhöhe, mit der der exakte Kern selbst tesselliert. Weicht der Körper
#: weiter vom Netz ab, sind entweder die Dreiecke des Netzes gröber als das,
#: was Solidon selbst ausgibt (ein Ring aus 48 mal 24 Vierecken: 0,1 mm), oder
#: eine Fläche liegt daneben — beides will der Kunde sehen, bevor er das Teil
#: als STEP weitergibt.
DEVIATION_NOTICE: Final = MAX_FACET_SAG


def conversion_findings(
    source: SceneObject, conversion: from_mesh.Conversion, params: MeshToExactParams
) -> list[Finding]:
    """Was die Umwandlung gebaut und gemessen hat — drei Befunde, jeder mit Zahl."""
    kinds = dict(conversion.faces)
    # Je Flächenart eine Zahl, und nur die, die vorkommen: „Kugeln: 0“ an
    # einer Platte ist keine Auskunft.
    values = {
        "faces": sum(kinds.values()),
        "planes": kinds.get("plane", 0),
        "cylinders": kinds.get("cylinder", 0),
        "cones": kinds.get("cone", 0),
        "spheres": kinds.get("sphere", 0),
        "tori": kinds.get("torus", 0),
        "triangles": kinds.get("facet", 0),
    }
    findings = [
        Finding(
            code="brep.from_mesh",
            severity="info",
            message=_(
                "Das Netz ist jetzt ein Körper mit echten Flächen und Kanten, ohne "
                "Konstruktionsverlauf. Das Netz bleibt im Schritt davor."
            ),
            object_id=source.id,
            values={key: value for key, value in values.items() if value},
        )
    ]
    if conversion.freeform_triangles:
        findings.append(
            Finding(
                code="brep.from_mesh.freeform",
                severity="warning",
                message=_(
                    "Ein Teil der Oberfläche passt auf keine erkannte Fläche und bleibt ebene "
                    "Dreiecke, wie im Netz."
                ),
                object_id=source.id,
                values={
                    "share_percent": round(100.0 * conversion.freeform_share, 2),
                    "triangles": conversion.freeform_triangles,
                },
            )
        )
    worst = max(conversion.mesh_to_body, conversion.body_to_mesh)
    findings.append(
        Finding(
            code="brep.from_mesh.deviation",
            severity="warning" if worst > DEVIATION_NOTICE else "info",
            message=(
                _(
                    "Der Körper weicht stellenweise deutlich vom Netz ab — meist schneiden grobe "
                    "Dreiecke eine Rundung ab. Die Karte „Formabweichung“ zeigt, wo."
                )
                if worst > DEVIATION_NOTICE
                else _(
                    "Körper und Netz liegen dicht beieinander. Die Karte „Formabweichung“ zeigt "
                    "die Abweichung Stelle für Stelle."
                )
            ),
            object_id=source.id,
            location=conversion.worst,
            values={
                "deviation_mm": round(worst, 4),
                "mesh_to_body_mm": round(conversion.mesh_to_body, 4),
                "body_to_mesh_mm": round(conversion.body_to_mesh, 4),
                "tolerance_mm": params.tolerance,
            },
        )
    )
    if conversion.inner_walls:
        findings.append(
            Finding(
                code="brep.from_mesh.inner_walls",
                severity="info",
                message=_(
                    "Das Netz hatte Wände im Inneren, etwa eine nicht verschmolzene Naht. Der "
                    "Körper übernimmt sie nicht; außen ändert sich nichts."
                ),
                object_id=source.id,
                values={"triangles": conversion.inner_walls},
            )
        )
    if conversion.rejected:
        findings.append(
            Finding(
                code="brep.from_mesh.rejected",
                severity="info",
                message=_(
                    "Einige erkannte Merkmale lagen nicht genau genug auf ihrer Fläche; ihre "
                    "Dreiecke gehören jetzt zu Nachbarflächen oder bleiben Dreiecke."
                ),
                object_id=source.id,
                feature_ids=tuple(name for name, _distance in conversion.rejected),
                values={"count": len(conversion.rejected)},
            )
        )
    return findings


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
                "Der Körper besteht aus festen Dreiecken. Dieses Werkzeug braucht echte "
                "Flächen und Kanten: „In Flächen und Kanten umwandeln“ macht sie aus dem "
                "Netz, eine ältere Grundform bekommt sie im Verlauf über „Mit echten "
                "Flächen und Kanten rechnen“."
            ),
            values={"name": source.name, "field": "in", "constraint": "needs_brep"},
            object_id=source.id,
        )
    return source, source.mesh


def _object(name: str, solid: Solid, *, cancelled: CancelToken) -> SceneObject:
    return SceneObject(
        id="", name=name, mesh=solid, kind="brep", features=features_of(solid, cancelled=cancelled)
    )


def _replaced(source: SceneObject, solid: Solid, *, cancelled: CancelToken) -> SceneObject:
    return dataclasses.replace(
        source, mesh=solid, kind="brep", features=features_of(solid, cancelled=cancelled)
    )


__all__ = [
    "brep_to_mesh",
    "create_brep_box",
    "create_brep_cone",
    "create_brep_cylinder",
    "create_brep_sphere",
    "create_brep_torus",
    "drill_brep_hole",
    "mesh_to_exact",
    "shell_exact",
    "thread_exact",
]
