"""Operationen für die Druckvorbereitung (Bauplan §25).

Bohren, Teilen, Anordnen und die Kollisionsprüfung. Die letzte ändert gar
keine Geometrie — sie meldet nur, und das ist eine völlig gute Sache für eine
Operation, wenn die Alternative eine Überraschung am Drucker ist.
"""

from __future__ import annotations

import dataclasses
from functools import lru_cache
from typing import cast

import trimesh

from app.core.errors import InternalError, ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.hollow import VENT_DIAMETER, hollow
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.orient import orient_for_print
from app.core.geom.pins import PIN_COUNT, PIN_MAX, PinnedPair, add_pins, plan_pins
from app.core.geom.prepare import (
    MAX_PLATES,
    Arrangement,
    BoreAnchor,
    arrange_on_bed,
    check_build_volume,
    check_collisions,
    compensate_elephant_foot,
    countersink,
    drill,
    named_for,
    plug,
    split_at_plane,
)
from app.core.geom.section import AXIS_NORMALS, SectionPlane
from app.core.geom.transform import Axis, place_on_bed
from app.core.knowledge.profiles import for_object, material
from app.core.registry import VARIABLE, op_params, param, register_op
from app.core.slice.orientation import DEFAULT_CANDIDATES, search
from app.core.types import BaseParams, Finding, OpContext, OpResult
from app.core.units import DEGREE_UNIT, EPS_GEOM
from app.i18n import _

_AXES = tuple(AXIS_NORMALS)

#: Erklärungen, die für jede Bohrung dieselben sind. Einmal geschrieben, damit
#: dieselbe Zahl nicht an drei Stellen unterschiedlich erklärt wird.
_WHERE_X = _(
    "Mitte der Bohrung im Koordinatensystem des Objekts. Eine angeklickte "
    "Fläche trägt die drei Werte selbst ein."
)
_WHERE_Y = _("Zweite Achse der Position — siehe Position X.")
_WHERE_Z = _("Dritte Achse der Position — siehe Position X.")
_ALONG = _(
    "Richtung, in die gebohrt wird. Z ist senkrecht von oben, X und Y bohren durch eine Seitenwand."
)

#: Was die Position bedeutet. „mouth" ist die Vorgabe, weil eine angeklickte
#: Fläche die Mündung ist und nicht die Mitte des Lochs dahinter; „centre" gibt
#: es, weil Dateien bis Formatversion 6 es so gemeint haben.
_ANCHORS = ("mouth", "centre")

#: Was ein Verbinder sein kann. Die ersten drei sind Querschnitte: dieselbe
#: Rechnung, ein anderes Vieleck. Rund ist die Vorgabe und der einfachste
#: Druck; die kantigen sichern gegen Verdrehen, der Schwalbenschwanz zusätzlich
#: gegen Auseinanderziehen quer zur Naht.
#:
#: Der Schnapper ist kein Querschnitt, sondern ein Mechanismus mit eigenem
#: Baustein (``snap_connector``) — er steht hier trotzdem in derselben Liste,
#: weil er für den Nutzer dieselbe Entscheidung ist: *womit* halten die Hälften
#: zusammen. Wo eine Naht ihm zu schmal ist, wird rund daraus, und der
#: Prüfbericht sagt es (``split.snap_too_small``).
CONNECTOR_SHAPES = ("round", "hex", "dovetail", "snap")

_CONNECTOR_DOC = _(
    "Womit die Hälften zusammenhalten. Rund druckt am saubersten und braucht "
    "zwei Stück gegen Verdrehen; Sechskant und Schwalbenschwanz halten schon "
    "einzeln, der Schwalbenschwanz auch gegen Auseinanderziehen. Der Schnapper "
    "rastet ein und hält ohne Kleber — er braucht eine Naht, die mindestens "
    "5,4 mm hergibt."
)


#: Was eine Hälfte von der anderen unterscheidet, sobald verstiftet wurde,
#: und das Zeichen davor.
_HALF_MARK = " · "
_PIN_NOTE = _("Stifte")
_BORE_NOTE = _("Löcher")


@lru_cache(maxsize=1)
def _own_notes() -> frozenset[str]:
    """Die beiden Zusätze in jeder ausgelieferten Sprache.

    Gebraucht, um den *eigenen* Zusatz von einem fremden Namensteil zu
    unterscheiden. Ein bloßes Abschneiden am letzten „ · " war zu grob:
    „Halter · Sonderanfertigung" verlor beim Teilen sein zweites Wort —
    stiller Verlust an einem Namen, den jemand selbst vergeben hat.

    Über alle Sprachen und nicht nur über die aktive, weil ein Teil auf
    Deutsch geteilt und danach auf Englisch weitergeteilt werden kann. Ohne
    das stapelten sich zwei Zusätze in zwei Sprachen.

    Gemerkt, und das ist keine vorbeugende Optimierung: Der Aufruf liest fünf
    Katalogdateien und kostet gemessen 9,6 ms — für den Vergleich von zwei
    Wörtern, einmal je Schnitt. Die Antwort hängt an den ausgelieferten
    Dateien und nicht an der eingestellten Sprache, kann also nicht veralten.
    """
    from app.i18n.catalog import available_languages, read_catalog

    notes = {str(_PIN_NOTE), str(_BORE_NOTE), _PIN_NOTE.msgid, _BORE_NOTE.msgid}
    for language in available_languages():
        catalog = read_catalog(language)
        for note in (_PIN_NOTE, _BORE_NOTE):
            translated = catalog.get(note.msgid)
            if translated:
                notes.add(translated)
    return frozenset(notes)


def half_names(base: str, *, pinned: bool) -> tuple[str, str]:
    """Wie die beiden Stücke heißen.

    „A" und „B" allein beantworten die Frage nicht, die man beim Zusammenbauen
    hat — und beim Export ist der Dateiname die einzige Auskunft darüber,
    welches der beiden Teile die Stifte trägt. Deshalb steht sie im Namen.

    Ein **eigener** Zusatz wird ersetzt, nicht ergänzt: Wer eine Hälfte noch
    einmal teilt, bekommt sonst „Halter A · Stifte A · Stifte". Der
    Buchstabenpfad bleibt dabei stehen — er zeigt, aus welchem Stück welches
    geworden ist. Ein fremder Namensteil hinter demselben Zeichen bleibt, wo
    er ist (:func:`_own_notes`).
    """
    stem = base
    head, mark, tail = base.rpartition(_HALF_MARK)
    if mark and tail in _own_notes():
        stem = head
    if not pinned:
        return f"{stem} A", f"{stem} B"
    return (
        f"{stem} A{_HALF_MARK}{_PIN_NOTE}",
        f"{stem} B{_HALF_MARK}{_BORE_NOTE}",
    )


@op_params
class DrillParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        doc=_(
            "Nenndurchmesser der Bohrung. Für eine Schraube gibt es *Schraubenloch* "
            "in den Bausteinen — dort kommen die Maße aus der Normteiltabelle."
        ),
    )
    x: float = param(title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X)
    y: float = param(title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y)
    z: float = param(title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z)
    axis: str = param(title=_("Achse"), default="z", choices=_AXES, doc=_ALONG)
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_("Null bohrt durch das ganze Teil."),
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="mouth",
        choices=_ANCHORS,
        placement="advanced",
        doc=_(
            "Was die Position bedeutet: die Mündung, an der die Bohrung anfängt, "
            "oder ihre Mitte. Bei einer durchgehenden Bohrung ändert es nichts."
        ),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=True,
        placement="advanced",
        doc=_("Vergrößert die Bohrung um den Wert aus dem Materialprofil."),
    )


@register_op(
    name="drill_hole",
    title=_("Bohrung setzen"),
    category="holes",
    params=DrillParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    touches_features=True,
    deterministic=False,
    shortcut="Ctrl+B",
    doc=_("Bohrt ein rundes Loch — auf Wunsch um die Materialtoleranz vergrößert."),
)
def drill_hole(ctx: OpContext) -> OpResult:
    params = cast(DrillParams, ctx.params)
    source = ctx.inputs[0]
    result = drill(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        depth=params.depth,
        anchor=cast(BoreAnchor, params.anchor),
        profile=ctx.profile,
        compensate=params.compensate,
        quality=ctx.quality,
        seed=ctx.seed,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class SplitPlaneParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        doc=_("Senkrecht zu welcher Achse geschnitten wird. Z legt einen waagerechten Schnitt."),
    )
    position: float = param(
        title=_("Position"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wo die Schnittebene liegt, auf dieser Achse gemessen. Die Zahl bleibt "
            "änderbar: ein Doppelklick auf den Schritt verschiebt den Schnitt."
        ),
    )


def _both_halves_or_stop(first: MeshData, second: MeshData, position: float) -> None:
    """Hält an, wenn die Ebene den Körper gar nicht getroffen hat.

    Ohne das kam eine Hälfte mit null Dreiecken heraus, und der Stapel legte
    sie als Objekt an: ein Eintrag im Baum, den man ansehen, umbenennen und
    exportieren kann und der nichts ist. Der Fall ist häufiger als er klingt —
    der Dialog belegt ``position = 0`` vor, und ein Körper steht mit seiner
    Unterseite oft genau dort.
    """
    if first.triangle_count and second.triangle_count:
        return
    raise ValidationError(
        field="position",
        detail=_("Diese Ebene teilt das Objekt nicht."),
        value=position,
        constraint="no_split",
    )


@register_op(
    name="split_plane",
    title=_("An Ebene teilen"),
    category="prepare",
    params=SplitPlaneParams,
    consumes=1,
    produces=2,
    doc=_("Teilt ein Objekt an einer Ebene in zwei Hälften mit geschlossenen Schnittflächen."),
)
def split_plane(ctx: OpContext) -> OpResult:
    params = cast(SplitPlaneParams, ctx.params)
    source = ctx.inputs[0]
    plane = SectionPlane(normal=AXIS_NORMALS[cast(Axis, params.axis)], position=params.position)
    first, second, findings = split_at_plane(as_mesh_data(source.mesh), plane)
    _both_halves_or_stop(first, second, params.position)
    # Über dieselbe Namensbildung wie das verstiftete Teilen, obwohl hier nie
    # Stifte entstehen: Wer eine Hälfte „Halter A · Stifte" hier weiterteilt,
    # bekäme sonst „Halter A · Stifte A" — einen Zusatz, der von der Naht des
    # *vorigen* Schnitts spricht und an dieser nichts zu suchen hat.
    first_name, second_name = half_names(source.name, pinned=False)
    return OpResult(
        outputs=[
            dataclasses.replace(source, mesh=first, name=first_name),
            dataclasses.replace(source, mesh=second, name=second_name, features={}),
        ],
        findings=findings,
    )


@op_params
class CountersinkParams(BaseParams):
    diameter: float = param(
        title=_("Kopfdurchmesser"),
        default=8.4,
        unit="mm",
        minimum=0.5,
        maximum=100.0,
        doc=_(
            "Durchmesser des Schraubenkopfes, nicht der Bohrung darunter. Eine "
            "angeklickte Bohrung trägt ihn deshalb bewusst nicht ein."
        ),
    )
    angle: float = param(
        title=_("Winkel"),
        default=90.0,
        unit=DEGREE_UNIT,
        minimum=30.0,
        maximum=170.0,
        # Hinten, weil 90 Grad die Norm ist und nicht eine Wahl: Der eigene
        # doc-Satz sagt es. Damit hat die Senkung dieselbe Vorderseite wie
        # `drill_hole` und `plug_hole` — Durchmesser, Position, Achse — und war
        # vorher die einzige Operation mit sechs Werten und leerer Rückseite
        # (§2.4: vorn die zwei bis drei, die man tatsächlich ändert).
        placement="advanced",
        doc=_("Voller Kopfwinkel — 90 Grad bei metrischen Senkschrauben."),
    )
    x: float = param(title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X)
    y: float = param(title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y)
    z: float = param(title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z)
    axis: str = param(title=_("Achse"), default="z", choices=_AXES, doc=_ALONG)


@register_op(
    name="countersink_hole",
    title=_("Senken"),
    category="holes",
    params=CountersinkParams,
    consumes=1,
    produces=1,
    applies_to=["hole"],
    doc=_("Senkt die Mündung einer Bohrung an, damit ein Schraubenkopf bündig sitzt."),
)
def countersink_hole(ctx: OpContext) -> OpResult:
    params = cast(CountersinkParams, ctx.params)
    source = ctx.inputs[0]
    result = countersink(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        angle=params.angle,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class PlugParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        doc=_("Durchmesser der Bohrung, die zugemacht wird — etwas mehr schadet nicht."),
    )
    x: float = param(title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X)
    y: float = param(title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y)
    z: float = param(title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z)
    axis: str = param(title=_("Achse"), default="z", choices=_AXES, doc=_ALONG)
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Null füllt durch das ganze Teil."),
    )


@register_op(
    name="plug_hole",
    title=_("Bohrung verschließen"),
    category="holes",
    params=PlugParams,
    consumes=1,
    produces=1,
    applies_to=["hole"],
    doc=_("Füllt eine Bohrung wieder auf — etwa wenn ein fremdes Teil eine zu viel hat."),
)
def plug_hole(ctx: OpContext) -> OpResult:
    params = cast(PlugParams, ctx.params)
    source = ctx.inputs[0]
    result = plug(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        depth=params.depth,
        profile=ctx.profile,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features={})],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class HollowParams(BaseParams):
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.4,
        maximum=50.0,
        doc=_("Was stehen bleibt. Zwei Extrusionsbreiten sind das Minimum."),
    )
    open_top: bool = param(
        title=_("Oben öffnen"),
        default=False,
        doc=_(
            "Nimmt die Decke über dem Hohlraum weg. Aus dem hohlen Körper wird "
            "eine Dose, und *Deckel erzeugen* findet die Öffnung, die es braucht."
        ),
    )
    vents: int = param(
        title=_("Entlüftungen"),
        default=1,
        minimum=0,
        maximum=6,
        doc=_(
            "Null heißt geschlossener Hohlraum — beim FDM-Druck drückt der die "
            "Decke hoch. Eine offene Dose braucht keine."
        ),
    )
    vent_diameter: float = param(
        title=_("Entlüftungsdurchmesser"),
        default=VENT_DIAMETER,
        unit="mm",
        minimum=1.0,
        maximum=20.0,
        placement="advanced",
        doc=_("Weite der Öffnungen. Groß genug, dass nicht verbrauchtes Material herauskommt."),
    )


@register_op(
    name="hollow_object",
    title=_("Aushöhlen"),
    category="prepare",
    params=HollowParams,
    consumes=1,
    produces=1,
    doc=_(
        "Höhlt ein Objekt aus und setzt Entlüftungen. Spart Material und Zeit; "
        "die Wandstärke stimmt im Rahmen des Rasters."
    ),
    caveat=_(
        "Nicht ohne Entlüftung, wenn im Slicer Stützen entstehen: Der Hohlraum füllt "
        "sich sonst mit Material, das niemand mehr herausbekommt. Und nicht bei "
        "Teilen, die Kräfte aufnehmen — eine dünne Hülle bricht anders als ein "
        "gefüllter Körper."
    ),
    shortcut="Ctrl+H",
)
def hollow_object(ctx: OpContext) -> OpResult:
    params = cast(HollowParams, ctx.params)
    source = ctx.inputs[0]
    result = hollow(
        as_mesh_data(source.mesh),
        params.wall,
        vents=params.vents,
        vent_diameter=params.vent_diameter,
        open_top=params.open_top,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features={})],
        # Die Geometriefunktion kennt keine Kennungen — sie rechnet auf einem
        # Netz. Verorten kann die Operation, und sie muss es: zwei ausgehöhlte
        # Körper meldeten zweimal denselben Satz, und im Bericht standen zwei
        # Zeilen, die aussahen wie ein Fehler in der Anwendung.
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in result.findings],
    )


@op_params
class ElephantFootParams(BaseParams):
    height: float = param(
        title=_("Höhe"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=5.0,
        doc=_("Über wie viel Höhe eingezogen wird — etwa die ersten drei Schichten."),
    )
    amount: float = param(
        title=_("Betrag"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )


@register_op(
    name="compensate_first_layer",
    title=_("Elefantenfuß ausgleichen"),
    category="prepare",
    params=ElephantFootParams,
    consumes=1,
    produces=1,
    doc=_(
        "Zieht die ersten Schichten um den Betrag ein, um den sie beim Drucken "
        "breitlaufen. Der Wert kommt aus dem Materialprofil."
    ),
)
def compensate_first_layer(ctx: OpContext) -> OpResult:
    params = cast(ElephantFootParams, ctx.params)
    source = ctx.inputs[0]
    if ctx.profile is None:
        raise InternalError(detail="the elephant foot compensation needs a profile")

    mesh, findings = compensate_elephant_foot(
        as_mesh_data(source.mesh),
        # Das Auseinanderlaufen gehört zum Material, und dieser Körper ist
        # vielleicht nicht im Material des Projekts (§12) — eine TPU-Dichtung
        # läuft weiter als das PETG um sie herum.
        for_object(ctx.profile, source),
        height=params.height,
        amount=params.amount or None,
    )
    return OpResult(outputs=[dataclasses.replace(source, mesh=mesh)], findings=findings)


@op_params
class MaterialParams(BaseParams):
    material: str = param(
        title=_("Material"),
        default="",
        doc=_("Kennung eines Materialprofils, etwa „tpu-95a“. Leer heißt: das des Projekts."),
    )


@register_op(
    name="set_material",
    title=_("Material festlegen"),
    category="prepare",
    params=MaterialParams,
    consumes=1,
    produces=1,
    doc=_(
        "Gibt diesem Körper ein eigenes Material. Toleranzen, Schwund und "
        "Elefantenfuß werden dann damit gerechnet und nicht mit dem des Projekts."
    ),
)
def set_material(ctx: OpContext) -> OpResult:
    """§12: eine Szene, mehr als ein Material.

    Ein Gehäuse in PETG mit einer Dichtung in TPU ist ein Projekt und zwei
    Materialien. Ohne das würden Spiel, Schrumpf und erste Schicht der Dichtung
    aus dem Material des Gehäuses gerechnet — Zahlen, die nicht ungefähr sind,
    sondern falsch, und falsch in der Richtung, die einen Druck zu Ausschuss
    macht.

    Die Kennung wird hier geprüft statt als feste Liste angeboten: zu den
    bekannten Materialien gehören die eigenen Profile des Nutzers, und die
    erscheinen, nachdem dieses Modul importiert wurde.
    """
    params = cast(MaterialParams, ctx.params)
    source = ctx.inputs[0]
    chosen = params.material.strip()
    if chosen:
        material(chosen)  # wirft mit der Liste der bekannten, wenn es keines ist

    return OpResult(
        outputs=[dataclasses.replace(source, material=chosen or None)],
        findings=[
            Finding(
                code="prepare.material",
                severity="info",
                message=_("Dieser Körper wird in einem eigenen Material gerechnet."),
                values={"object": source.name, "material": chosen or "-"},
            )
        ]
        if chosen
        else [],
    )


@op_params
class TestPieceParams(BaseParams):
    size: float = param(
        title=_("Kantenlänge"),
        default=20.0,
        unit="mm",
        minimum=2.0,
        maximum=200.0,
        doc=_("Wie groß der Ausschnitt wird. Groß genug, dass die Passung Material hat."),
    )
    x: float = param(
        title=_("Position X"),
        default=0.0,
        unit="mm",
        doc=_("Mitte des Ausschnitts — die Stelle, um die es geht."),
    )
    y: float = param(title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y)
    z: float = param(title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z)
    on_bed: bool = param(
        title=_("Auf das Bett setzen"),
        default=True,
        doc=_("Legt das Prüfstück flach hin, damit es ohne Stützen druckt."),
    )


@register_op(
    name="test_piece",
    title=_("Prüfstück erzeugen"),
    category="prepare",
    params=TestPieceParams,
    consumes=1,
    produces=1,
    applies_to=["hole", "pin", "face"],
    doc=_(
        "Schneidet einen Würfel um eine Stelle heraus, um sie zu drucken und "
        "auszuprobieren — zwei Minuten statt zwei Stunden."
    ),
)
def test_piece(ctx: OpContext) -> OpResult:
    """§28.3, aus der Praxis: eine Passung prüft man am Ausschnitt, nicht am Teil.

    Der Ausschnitt ist eine Verschneidung mit einem Würfel — heraus kommt also
    die echte Geometrie mit den echten Toleranzen, keine nachgebaute Näherung
    davon. Ein Prüfstück, das anders druckt als das Teil, für das es steht,
    wäre schlechter als gar kein Test.
    """
    params = cast(TestPieceParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    window = trimesh.creation.box(extents=(params.size, params.size, params.size))
    window.apply_translation((params.x, params.y, params.z))
    # Ein Fenster über leerem Raum ist eine Antwort, keine gescheiterte
    # Operation: ohne ``allow_empty`` probierte die Kette drei weitere Stufen
    # und würfe dann — und der Nutzer läse etwas über den Voxel-Solver statt
    # über das Loch, auf das er gezielt hat.
    outcome = boolean(
        "intersection", [mesh, mesh.replacing(window)], quality=ctx.quality, allow_empty=True
    )

    piece = outcome.mesh
    if not piece.triangle_count or abs(piece.volume) <= EPS_GEOM:
        raise ValidationError(
            field="size",
            detail=_("An dieser Stelle ist kein Material — der Ausschnitt bleibt leer."),
            constraint="empty",
            values={"size_mm": round(params.size, 2)},
        )
    if params.on_bed:
        piece = place_on_bed(piece)

    share = abs(piece.volume) / max(abs(mesh.volume), EPS_GEOM)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=piece,
                name=f"{source.name} {_('Prüfstück').translate()}",
                features={},
            )
        ],
        solver=outcome.solver,
        findings=[
            *outcome.findings,
            Finding(
                code="prepare.test_piece",
                severity="info",
                message=_("Ein Ausschnitt zum Ausprobieren — die Maße sind die des Teils."),
                object_id=source.id,
                values={"share_percent": round(share * 100.0, 1), "size_mm": params.size},
            ),
        ],
    )


@op_params
class SplitPinnedParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        doc=_("Senkrecht zu welcher Achse geschnitten wird. Z legt einen waagerechten Schnitt."),
    )
    position: float = param(
        title=_("Position"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wo die Schnittebene liegt, auf dieser Achse gemessen. Die Zahl bleibt "
            "änderbar: ein Doppelklick auf den Schritt verschiebt den Schnitt."
        ),
    )
    pins: int = param(
        title=_("Passstifte"),
        default=PIN_COUNT,
        minimum=0,
        maximum=6,
        doc=_("Null heißt: nur schneiden. Zwei halten die Hälften gegen Verdrehen."),
    )
    shape: str = param(
        title=_("Stiftform"),
        default="round",
        choices=CONNECTOR_SHAPES,
        placement="advanced",
        doc=_CONNECTOR_DOC,
    )
    diameter: float = param(
        title=_("Stiftdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=PIN_MAX,
        placement="advanced",
        doc=_("Null heißt: aus der Schnittfläche ableiten."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )


@register_op(
    name="split_pinned",
    # Nicht mehr „Teilen und verstiften": Seit *An Ebene teilen* als Zwilling
    # unter diesem Eintrag lebt (MENU_TWINS), ist es die eine Zeile für beides
    # — mit Stiften und ohne. Ein Titel, der die Stifte verspricht, wäre für
    # die Hälfte der Fälle falsch; das Feld *Passstifte* sagt, welcher gilt.
    title=_("Teilen"),
    category="prepare",
    params=SplitPinnedParams,
    consumes=1,
    produces=2,
    doc=_(
        "Teilt ein Objekt an einer Ebene, auf Wunsch mit Passstiften in der "
        "Schnittfläche. Das Spiel kommt aus dem Materialprofil; null Stifte heißt: "
        "nur schneiden."
    ),
    caveat=_(
        "Nicht bei Teilen, deren Schnittfläche sichtbar bleibt: Die Naht liegt an "
        "einer Ebene und ist es danach auch. Wo sie stören würde, lieber die Lage "
        "ändern oder eine Stelle wählen, an der ohnehin eine Kante läuft."
    ),
)
def split_pinned(ctx: OpContext) -> OpResult:
    """§25: der Schnitt und die Stifte in einem Schritt, denn sie gehören
    zusammen.

    Eine Naht ohne Stifte ist eine Naht, die jemand von Hand ausrichten muss,
    während der Kleber greift; ein Stift ohne Naht ist nichts. Beides in einer
    Operation heißt außerdem: ein Undo nimmt das Ganze zurück.
    """
    params = cast(SplitPinnedParams, ctx.params)
    plane = SectionPlane(normal=AXIS_NORMALS[cast(Axis, params.axis)], position=params.position)
    return _cut_and_pin(
        ctx,
        plane,
        pins=params.pins,
        shape=params.shape,
        diameter=params.diameter,
        play=params.play,
    )


def _cut_and_pin(
    ctx: OpContext,
    plane: SectionPlane,
    *,
    pins: int,
    shape: str,
    diameter: float,
    play: float,
) -> OpResult:
    """Der gemeinsame Teil von *Teilen und verstiften* und *An Linie trennen*.

    Die beiden unterscheiden sich einzig darin, **woher die Ebene kommt** —
    aus einer Achse und einer Zahl oder aus zwei angeklickten Punkten. Alles
    danach ist dasselbe, und zweimal geschrieben wäre es beim ersten Nachbessern
    an einer Stelle anders.
    """
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    first, second, findings = split_at_plane(mesh, plane)
    _both_halves_or_stop(first, second, plane.position)

    plan = plan_pins(mesh, plane, count=pins, shape=shape) if pins else None
    if plan is not None and diameter:
        plan = dataclasses.replace(plan, diameter=diameter)

    pair = (
        # Beide Hälften kommen aus diesem einen Körper, das Spiel ist also das
        # seines Materials.
        add_pins(first, second, plan, for_object(ctx.profile, source), play=play or None)
        if plan is not None and ctx.profile is not None
        else PinnedPair(first=first, second=second)
    )

    first_name, second_name = half_names(source.name, pinned=bool(pair.pin_features))
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=pair.first,
                name=first_name,
                features={**source.features, **pair.pin_features},
            ),
            dataclasses.replace(
                source,
                mesh=pair.second,
                name=second_name,
                features=dict(pair.bore_features),
            ),
        ],
        findings=[*findings, *pair.findings],
    )


@op_params
class SplitLineParams(BaseParams):
    """Die Trennebene aus einer gezeichneten Linie.

    Was der Nutzer tut, ist zwei Punkte anklicken; was gespeichert wird, ist
    die Ebene, die daraus folgt. Beides ist dieselbe Angabe — nur ist die
    Ebene die, die sich hinterher noch verschieben lässt, und ein Punktpaar
    wäre eine Zahlenkolonne, an der niemand etwas nachbessert.
    """

    position: float = param(
        title=_("Lage"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wie weit die Trennebene vom Nullpunkt entfernt liegt, in Trennrichtung "
            "gemessen. Die gezeichnete Linie trägt die Zahl ein; nachträglich "
            "verschiebt sie den Schnitt, ohne ihn zu drehen."
        ),
    )
    pins: int = param(
        title=_("Passstifte"),
        default=PIN_COUNT,
        minimum=0,
        maximum=6,
        doc=_(
            "Stifte auf der einen Hälfte, Bohrungen auf der anderen — sie halten die "
            "Teile beim Kleben in Deckung. Null heißt: nur trennen."
        ),
    )
    normal_x: float = param(
        title=_("Trennrichtung X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Richtung, in der die Ebene steht. Die gezeichnete Linie trägt sie ein — "
            "von Hand gesetzt ergeben die drei Zahlen zusammen einen Pfeil senkrecht "
            "zur Schnittfläche."
        ),
    )
    normal_y: float = param(
        title=_("Trennrichtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Zweite Achse der Trennrichtung — siehe Trennrichtung X."),
    )
    normal_z: float = param(
        title=_("Trennrichtung Z"),
        default=1.0,
        placement="advanced",
        doc=_("Dritte Achse der Trennrichtung — siehe Trennrichtung X."),
    )
    shape: str = param(
        title=_("Stiftform"),
        default="round",
        choices=CONNECTOR_SHAPES,
        placement="advanced",
        doc=_CONNECTOR_DOC,
    )
    diameter: float = param(
        title=_("Stiftdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=PIN_MAX,
        placement="advanced",
        doc=_("Null heißt: aus der Schnittfläche ableiten."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )


@register_op(
    name="split_line",
    title=_("An gezeichneter Linie trennen"),
    category="prepare",
    params=SplitLineParams,
    consumes=1,
    produces=2,
    icon="split",
    doc=_(
        "Trennt ein Objekt entlang einer im Bild gezeichneten Linie und setzt auf "
        "Wunsch Passstifte in die Schnittfläche."
    ),
    caveat=_(
        "Der Schnitt ist eine Ebene, keine Kurve: Die Linie legt fest, wo und wie "
        "schräg getrennt wird, und die Ebene läuft von dort gerade durch das Teil. "
        "Wer um eine Rundung herum trennen will, teilt zweimal."
    ),
)
def split_line(ctx: OpContext) -> OpResult:
    """§25: derselbe Schnitt wie *Teilen und verstiften*, nur mit einer Ebene,
    die nicht an einer Achse hängt.

    Zwei Punkte auf dem Körper und die Blickrichtung spannen sie auf — das ist
    die Rechnung, die das Fenster macht, bevor es hier ankommt. Hier steht nur
    noch die fertige Ebene, und das ist Absicht: Eine Operation, die von der
    Kamerastellung abhinge, wäre beim zweiten Auswerten eine andere (§11.2).
    """
    params = cast(SplitLineParams, ctx.params)
    normal = (params.normal_x, params.normal_y, params.normal_z)
    if _length(normal) <= EPS_GEOM:
        raise ValidationError(
            field="normal_z",
            detail=_("Ohne Trennrichtung gibt es keine Ebene."),
            value=0.0,
            constraint="no_normal",
        )
    return _cut_and_pin(
        ctx,
        SectionPlane(normal=normal, position=params.position),
        pins=params.pins,
        shape=params.shape,
        diameter=params.diameter,
        play=params.play,
    )


def _length(vector: tuple[float, float, float]) -> float:
    return float(sum(entry * entry for entry in vector) ** 0.5)


@op_params
class OrientParams(BaseParams):
    thorough: bool = param(
        title=_("Gründlich suchen"),
        default=True,
        doc=_(
            "Rechnet hunderte Lagen mit der Schichtanalyse durch. "
            "Aus heißt: schnelle Heuristik über die Flächen."
        ),
    )
    candidates: int = param(
        title=_("Kandidaten"),
        default=DEFAULT_CANDIDATES,
        minimum=8,
        maximum=2000,
        placement="advanced",
        doc=_(
            "Wie viele Lagen durchgerechnet werden. Mehr findet feinere "
            "Verbesserungen und dauert entsprechend länger."
        ),
        depends_on=("thorough", (True,)),
    )


@register_op(
    name="orient_for_print",
    title=_("Druckoptimal ausrichten"),
    category="transform",
    params=OrientParams,
    consumes=1,
    produces=1,
    deterministic=False,
    doc=_("Sucht die Lage mit dem geringsten Stützbedarf."),
)
def orient_for_print_op(ctx: OpContext) -> OpResult:
    """Gründlich heißt, die Schichtanalyse urteilt; sonst tut es die
    P2-Heuristik.
    """
    params = cast(OrientParams, ctx.params)
    mesh = as_mesh_data(ctx.inputs[0].mesh)

    if params.thorough:
        found = search(
            mesh,
            count=params.candidates,
            seed=ctx.seed,
            profile=ctx.profile,
            progress=ctx.progress,
            cancelled=ctx.cancelled,
        )
        return OpResult(
            outputs=[dataclasses.replace(ctx.inputs[0], mesh=found.mesh)],
            findings=found.findings,
        )

    result = orient_for_print(mesh)
    return OpResult(
        outputs=[dataclasses.replace(ctx.inputs[0], mesh=result.mesh)],
        findings=result.findings,
    )


@op_params
class ArrangeParams(BaseParams):
    spacing: float = param(
        title=_("Abstand"),
        default=5.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_(
            "Luft zwischen den Teilen. Genug, dass ein Elefantenfuß zwei Teile "
            "nicht am Rand zusammenwachsen lässt."
        ),
    )
    plates: int = param(
        title=_("Druckplatten"),
        default=1,
        minimum=1,
        maximum=MAX_PLATES,
        doc=_("Passt nicht alles auf eine Platte, wandert der Rest auf die nächste."),
    )
    by_material: bool = param(
        title=_("Nach Filament trennen"),
        default=False,
        doc=_(
            "Legt Teile aus verschiedenen Filamenten auf verschiedene Platten. "
            "Zwei Filamente auf einer Platte kosten je gemeinsamer Schicht "
            "einen Wechsel samt Spülgang."
        ),
    )


def _arranged_by_material(ctx: OpContext, params: ArrangeParams) -> Arrangement:
    """Erst nach Filament gruppieren, dann jede Gruppe für sich anordnen.

    Den Vorschlag rechnet :func:`app.core.export.writer.plates_by_material`
    schon lange — er war nur von nirgends aus erreichbar. Hier wird er zu einer
    Handlung, und zwar als Umschalter an der bestehenden Operation statt als
    zweite daneben: es ist dieselbe Handlung mit einer anderen Vorgabe, wer
    neben wem liegt.

    Jede Gruppe bekommt ihre eigenen Platten, hintereinander weg. Die Grenze
    aus ``plates`` gilt dabei für die ganze Szene, nicht je Gruppe — sonst
    hätte ein Projekt mit drei Filamenten unversehens dreimal so viele
    Platten, wie jemand eingestellt hat.
    """
    from app.core.export.writer import plates_by_material

    groups = plates_by_material(list(ctx.inputs))
    order: list[int] = []
    for entry in ctx.inputs:
        group = groups[entry.id]
        if group not in order:
            order.append(group)

    meshes: dict[str, MeshData] = {}
    assigned: dict[str, int] = {}
    findings: list[Finding] = []
    next_plate = 0

    for group in order:
        members = [entry for entry in ctx.inputs if groups[entry.id] == group]
        # Sind die Platten aufgebraucht, teilt sich diese Gruppe die letzte mit
        # der vorigen — dieselbe Regel, die `arrange_on_bed` innerhalb einer
        # Gruppe befolgt: die letzte Platte nimmt den Rest, und der Bericht
        # sagt, dass sie übervoll ist. Ein Teil, das still aus der Anordnung
        # fiele, wäre ein Teil, das nie gedruckt wird.
        start = min(next_plate, params.plates - 1)
        arranged = arrange_on_bed(
            [as_mesh_data(entry.mesh) for entry in members],
            ctx.profile,
            params.spacing,
            params.plates - start,
        )
        findings.extend(arranged.findings)
        for entry, mesh, plate in zip(members, arranged.meshes, arranged.plates, strict=True):
            meshes[entry.id] = mesh
            assigned[entry.id] = start + plate
        next_plate = start + arranged.plate_count

    return Arrangement(
        meshes=[meshes[entry.id] for entry in ctx.inputs],
        plates=[assigned[entry.id] for entry in ctx.inputs],
        findings=findings,
    )


@register_op(
    name="arrange_bed",
    title=_("Auf dem Bett anordnen"),
    category="scene",
    params=ArrangeParams,
    consumes=0,
    produces=VARIABLE,
    whole_scene=True,
    doc=_("Legt alle Objekte nebeneinander auf das Druckbett."),
    shortcut="Ctrl+Shift+O",
)
def arrange_bed(ctx: OpContext) -> OpResult:
    params = cast(ArrangeParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    if params.by_material:
        result = _arranged_by_material(ctx, params)
    else:
        result = arrange_on_bed(meshes, ctx.profile, params.spacing, params.plates)
    findings = list(result.findings)

    # Kollisionen werden je Platte geprüft: zwei Teile an derselben Stelle auf
    # verschiedenen Platten treffen sich nie.
    #
    # **Und mit Namen.** ``check_collisions`` kennt nur die Reihenfolge seiner
    # Liste und schreibt sie in den Befund; ohne ``named_for`` stand im Bericht
    # „Zwei Objekte überschneiden sich — 0 · 1". Hier war es doppelt irre, denn
    # die Liste ist je Platte gefiltert: die 1 der zweiten Platte ist nicht das
    # zweite Objekt der Szene. Die Einträge werden deshalb mitgefiltert und
    # zusammen weitergegeben. Die Zwillings-Op darunter macht es seit je so.
    for plate in range(result.plate_count):
        on_plate = [
            (mesh, entry)
            for mesh, entry, at in zip(result.meshes, ctx.inputs, result.plates, strict=True)
            if at == plate
        ]
        findings.extend(
            named_for(
                check_collisions([mesh for mesh, _entry in on_plate]),
                [entry for _mesh, entry in on_plate],
            )
        )

    return OpResult(
        outputs=[
            dataclasses.replace(entry, mesh=mesh, plate=plate)
            for entry, mesh, plate in zip(ctx.inputs, result.meshes, result.plates, strict=True)
        ],
        findings=findings,
    )


@op_params
class CollisionParams(BaseParams):
    clearance: float = param(
        title=_("Mindestabstand"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        doc=_(
            "Ab wann zwei Teile als zu nah gelten. Null meldet nur echte "
            "Überschneidungen; ein Wert darüber meldet auch knappe Stellen."
        ),
    )


@register_op(
    name="check_collisions",
    title=_("Kollisionen prüfen"),
    category="scene",
    params=CollisionParams,
    consumes=0,
    produces=VARIABLE,
    whole_scene=True,
    doc=_("Meldet Überschneidungen und was über den Bauraum hinaussteht."),
)
def check_collisions_op(ctx: OpContext) -> OpResult:
    params = cast(CollisionParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    findings = check_collisions(meshes, params.clearance)
    findings.extend(check_build_volume(meshes, ctx.profile))
    # Ändert nichts: die Objekte gehen unberührt hindurch, die Befunde sind das
    # Ergebnis.
    return OpResult(outputs=list(ctx.inputs), findings=named_for(findings, ctx.inputs))
