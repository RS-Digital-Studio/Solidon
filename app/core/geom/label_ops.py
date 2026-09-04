"""Text und Logos auf einer Fläche (Bauplan §25, Kategorie „Beschriftung").

Ein Teil mit seiner Größe darauf, ein Deckel mit dem, was in die Box gehört,
eine Halterung mit dem Datum ihres Drucks: der häufigste Grund, warum Leute
ein Modellierprogramm verlassen und ein zweites öffnen. Es braucht kein
zweites.

Die Buchstaben kommen als Umrisse aus der Schrift, nicht als nachgezeichnetes
Bild — die Kanten bleiben also in jeder Größe sauber, und ein erhabener
Buchstabe hat eine ebene Oberseite statt einer Treppe. Alles danach ist
dieselbe Vereinigung oder Differenz, die jeder andere Baustein auch
benutzt (§24.1).

Die andere Hälfte ist ein Logo, und das kommt als SVG durch dieselbe Tür: Ein
Umriss ist ein Umriss, ob ihn eine Schrift gezeichnet hat oder Inkscape.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Final, Literal, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom.attributes import with_slot
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    BooleanKind,
    boolean,
    fell_apart,
    without_effect,
)
from app.core.geom.mesh import MeshData, as_mesh_data, concatenated
from app.core.geom.transform import apply, rotation, translation
from app.core.log import get_logger
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.types import (
    MAX_SLOTS,
    BaseParams,
    Finding,
    MaterialSlot,
    OpContext,
    OpResult,
    SceneObject,
    Vec3,
)
from app.core.units import DEGREE_UNIT, EPS_GEOM, format_volume
from app.i18n import _

_log = get_logger(__name__)

Placement = Literal["raised", "engraved"]

#: Ab welchem Anteil der Buchstaben, der **nicht** über der Fläche steht, die
#: Schrift als versenkt gilt. Die Hälfte: Eine Schrift, die halb im Körper
#: steckt, ist keine Beschriftung mehr — und eine, die zu einem Zehntel
#: eintaucht, kann eine gewollte Prägung auf schräger Fläche sein.
LABEL_BURIED_SHARE: Final = 0.5

#: Die Schriften, die immer da sind. matplotlib bringt DejaVu selbst mit, eine
#: Beschriftung sieht also auf jedem Rechner gleich aus — eine Systemschrift,
#: die es auf einem Rechner gibt und auf dem nächsten nicht, ist ein Projekt,
#: das sich unterschiedlich öffnet.
FONTS: tuple[str, ...] = ("DejaVu Sans", "DejaVu Serif", "DejaVu Sans Mono")

#: Erklärungen, die beide Beschriftungs-Operationen teilen.
_WHERE = _("Wo die Schrift sitzt. Eine angeklickte Fläche trägt Ort und Richtung selbst ein.")
_WHERE_MORE = _("Weitere Achse des Orts — siehe Position X.")
_FACING = _(
    "Richtung, in die die Schrift zeigt. Aus einer angeklickten Fläche kommt sie "
    "von selbst; von Hand ist 0/0/1 nach oben."
)
_FACING_MORE = _("Weitere Achse der Richtung — siehe Normale X.")
_SIZE = _("Höhe der Großbuchstaben. Unter drei Millimetern verliert der Druck die Form.")
_FONT = _("DejaVu liegt bei, damit ein Projekt auf jedem Rechner gleich aussieht.")

#: Darunter sind die Buchstaben dünner als eine Düse und drucken als Schmierer.
MIN_SIZE = 3.0


def outlines(text: str, size: float, font: str = FONTS[0]) -> list[Any]:
    """Die Buchstaben als Polygone, in Millimetern, auf dem Ursprung sitzend."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import unary_union

    path = TextPath((0.0, 0.0), text, size=size, prop=FontProperties(family=font))
    rings = [np.asarray(entry, dtype=float) for entry in path.to_polygons()]
    rings = [entry for entry in rings if len(entry) >= 4]
    if not rings:
        return []

    # Ein Buchstabe wie „o" kommt als zwei Ringe, und welcher das Loch ist,
    # folgt aus der Enthaltung, nicht aus der Reihenfolge des Zeichnens.
    shapes = [ShapelyPolygon(entry).buffer(0) for entry in rings]
    solid = None
    for shape in sorted(shapes, key=lambda entry: -entry.area):
        solid = shape if solid is None else solid.symmetric_difference(shape)
    merged = unary_union([solid]) if solid is not None else None
    if merged is None or merged.is_empty:
        return []
    return [entry for entry in getattr(merged, "geoms", [merged]) if entry.area > EPS_GEOM]


def label_solid(shapes: list[Any], depth: float) -> MeshData | None:
    """Ein Körper aus den Umrissen, stehend auf Z = 0."""
    parts = [
        trimesh.creation.extrude_polygon(shape, height=depth)
        for shape in shapes
        if shape.area > EPS_GEOM
    ]
    if not parts:
        return None
    return MeshData.of(concatenated(parts))


#: Ab welcher z-Komponente eine Normale als waagerecht gilt — dann gibt es
#: kein „oben" auf der Fläche, und die Ausrichtung bleibt die der Ebene.
UPRIGHT_LIMIT: Final = 1.0 - 1e-6


def place(body: MeshData, position: Vec3, normal: Vec3, angle: float = 0.0) -> MeshData:
    """Legt eine Beschriftung, die auf +Z steht, auf eine Fläche mit der
    gegebenen Normalen — **aufrecht, wie man sie liest.**

    Bis zum 02.09.2026 richtete allein ``align_vectors`` die Normale aus und
    ließ die Drehung *um* sie dem Zufall der gewählten Rotation: Auf der
    Vorderseite der Beispieldose lag „SOLIDON3D" quer, die Leserichtung auf
    der Welt-z-Achse (gemessen: 4,5 mm breit, 35 mm hoch). Wer eine
    Seitenwand beschriftet, hätte jedes Mal den Winkel nachgedreht.

    Auf einer Fläche, die nicht Decke oder Boden ist, steht der Text jetzt so,
    dass seine Zeile waagerecht liegt und sein Oben nach oben zeigt — für
    einen Betrachter, der von außen auf die Fläche sieht, liest er von links
    nach rechts. Decke und Boden behalten ihre Lage: Dort gibt es kein
    „oben", und ``angle`` ist der Weg, den Text zu drehen.
    """
    placed = body
    if angle:
        placed = apply(placed, rotation("z", angle))

    direction = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(direction))
    if length > EPS_GEOM:
        outward = direction / length
        if abs(float(outward[2])) < UPRIGHT_LIMIT:
            # Rechts ist, was Welt-z und Normale aufspannen; oben liegt in der
            # Fläche und zeigt nach Welt-oben. Spalten der Matrix: wohin die
            # Text-Achsen x, y, z gehen.
            right = np.cross([0.0, 0.0, 1.0], outward)
            right /= np.linalg.norm(right)
            up = np.cross(outward, right)
            matrix = np.eye(4)
            matrix[:3, 0] = right
            matrix[:3, 1] = up
            matrix[:3, 2] = outward
        else:
            matrix = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], outward)
        turned = placed.raw.copy()
        turned.apply_transform(matrix)
        placed = placed.replacing(turned)
    return apply(placed, translation(position))


@op_params
class LabelParams(BaseParams):
    text: str = param(
        title=_("Text"),
        # **Kein Vorgabewert, und das ist die Aussage.** Mit ``default=""``
        # meldete das Schema den Parameter als *freiwillig* — an drei
        # Oberflächen zugleich: Der Agent durfte die Operation ohne Text
        # vorschlagen, die Kommandozeile ihn weglassen, und der Dialog bot
        # Übernehmen an, um danach abzulehnen (Regel 19). Ohne Vorgabe steht
        # die Pflicht im Schema, wo alle drei sie lesen. Der Satz der
        # Operation bleibt die zweite Hürde: Der Dialog übergibt jedes Feld,
        # auch das leere, also greift er wie bisher.
        doc=_("Was daraufstehen soll."),
    )
    size: float = param(
        title=_("Schriftgröße"),
        default=8.0,
        unit="mm",
        minimum=MIN_SIZE,
        maximum=200.0,
        doc=_SIZE,
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=10.0,
        # **Drei Schichten sind der Wert, der stimmt.** 0,6 mm bei 0,2 mm
        # Schichthöhe deckt erhaben wie vertieft; wer daran dreht, tut es
        # einmal für einen Sonderfall. §2.4 will vorn „die zwei bis drei Werte,
        # die man tatsächlich ändert" — und das sind hier der Text, die Größe
        # und die Art.
        placement="advanced",
        doc=_("Wie weit erhaben oder wie tief eingelassen."),
    )
    mode: str = param(
        title=_("Art"),
        default="raised",
        choices=("raised", "engraved"),
        doc=_("Erhaben druckt sich besser, vertieft bleibt beim Schleifen erhalten."),
    )
    slot: int = param(
        title=_("Filament"),
        default=0,
        minimum=0,
        maximum=MAX_SLOTS - 1,
        # Ein Farbwechsel setzt einen zweiten Filamentstrang voraus. Wer ihn
        # hat, sucht ihn gezielt; wer einfarbig druckt — das ist die Mehrheit —
        # hat hier ein Feld ohne Wirkung vor sich (§2.4).
        placement="advanced",
        kind="filament",
        doc=_(
            "Legt die Schrift in einen eigenen Slot — der 3MF-Export macht daraus "
            "den Farbwechsel, ohne zweite Datei."
        ),
    )
    font: str = param(
        title=_("Schrift"),
        default=FONTS[0],
        choices=FONTS,
        placement="advanced",
        doc=_("DejaVu liegt bei, damit ein Projekt auf jedem Rechner gleich aussieht."),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_MORE, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_MORE, placement="advanced"
    )
    nx: float = param(title=_("Normale X"), default=0.0, placement="advanced", doc=_FACING)
    ny: float = param(title=_("Normale Y"), default=0.0, placement="advanced", doc=_FACING_MORE)
    nz: float = param(title=_("Normale Z"), default=1.0, placement="advanced", doc=_FACING_MORE)
    angle: float = param(
        title=_("Drehung"),
        default=0.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        placement="advanced",
        doc=_("Dreht die Schrift in der Fläche, auf der sie liegt."),
    )


def _fell_apart(before: Any, after: Any, mode: str) -> Finding | None:
    """Ist die Schrift neben dem Körper liegengeblieben? (Regel 17)

    **Der Fall, den der Kommentar an der Aufrufstelle seit jeher beschreibt**
    und den niemand prüfte: „Erhaben ist es schlimmer als graviert: die
    Buchstaben stehen dann als eigene Komponente neben dem Teil und reisen bis
    in den Export mit." Gemessen am 31.08.2026 an einer Platte 40 auf 30 mit
    einer Beschriftung 200 mm daneben: **drei Komponenten**, wo eine war —
    Platte und zwei Lettern, wasserdicht, mit plausiblem Volumen, und kein
    Befund dazu.

    :func:`without_effect` fängt das **nicht**, und das ist kein Versehen,
    sondern seine Bauart: Es misst, ob sich das Volumen geändert hat. Bei
    erhabener Schrift ändert es sich — die Buchstaben kommen ja hinzu, nur eben
    daneben. Die Volumenfrage ist damit beantwortet und die falsche gestellt.

    **Die Teilezahl lügt nicht.** Dieselbe Bauart wie
    ``texture_ops._fell_apart`` und ``parts._hanging_loose``, samt derselben
    Ausnahme: Ein graviertes Muster schneidet, und Schneiden darf teilen.
    """
    # Der Satz ist parallel zu dem der Textur gebaut: Der Kunde erkennt die
    # Familie am Wortlaut, nicht am Befundcode — den sieht er nie.
    return fell_apart(
        before,
        after,
        applies=mode == "raised",
        code="label.fell_apart",
        message=_(
            "Die Schrift hängt nicht am Körper: Sie liegt in {loose} losen Stücken "
            "daneben und würde einzeln gedruckt. Meist steht sie neben der Fläche, "
            "auf die sie soll — klicken Sie die Fläche an, dann trägt sie Ort und "
            "Richtung selbst ein."
        ),
    )


def _buried(letters: Any, before: Any, after: Any, mode: str) -> Finding | None:
    """Steckt die Schrift im Körper, statt auf ihm zu stehen? (Regel 17)

    **Der dritte Fall derselben Auskunft**, gemessen am 02.09.2026 am
    Beispiel „Dose mit Deckel": Die Beschriftung stand ohne Ort und Richtung
    in der Operation, also bei (0, 0, 0) mit der Vorgabe-Normalen nach oben —
    und das ist der Boden einer Dose, die auf dem Bett steht. Die Buchstaben
    wurden erhaben nach **oben** gebaut, also ins Material hinein, die
    Vereinigung änderte nichts Sichtbares, und übrig blieb die Überlappung
    von einem Hundertstel unter dem Boden: Die Dose war 40,01 statt 40,00
    hoch, das Teil stand auf einer unsichtbaren Schrift, und kein Befund
    sagte es. :func:`without_effect` schwieg, weil das Volumen sich änderte
    (um die Überlappung), :func:`_fell_apart` schwieg, weil nichts danebenlag.

    Gemessen wird deshalb, wie viel von den Buchstaben **über der Fläche**
    ankommt: die Volumenzunahme gegen das Volumen der gesetzten Schrift. Bleibt
    weniger als :data:`LABEL_BURIED_SHARE`, steckt sie im Körper. Nur erhaben —
    graviert nimmt Material weg, und dort ist im Körper genau der richtige Ort.
    """
    if mode != "raised":
        return None
    expected = float(letters.volume)
    if expected <= EPS_GEOM:
        return None
    shown = max(float(after.volume) - float(before.volume), 0.0)
    if shown >= LABEL_BURIED_SHARE * expected:
        return None
    return Finding(
        code="label.buried",
        severity="warning",
        message=_(
            "Die Schrift steckt im Körper: Von {expected} Buchstaben stehen nur {shown} "
            "über der Fläche, der Rest liegt im Material und ist unsichtbar. Meist zeigt "
            "die Richtung in den Körper hinein oder der Punkt liegt in ihm — klicken Sie "
            "die Fläche an, dann trägt sie Ort und Richtung selbst ein."
        ),
        values={
            "expected": format_volume(expected),
            "shown": format_volume(shown),
        },
    )


@register_op(
    name="label_text",
    title=_("Text aufbringen"),
    category="label",
    params=LabelParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    doc=_(
        "Setzt Text erhaben oder vertieft auf eine Fläche. Die Schrift wird als "
        "Umriss verarbeitet, nicht als Bild — die Kanten bleiben in jeder Größe sauber."
    ),
)
def label_text(ctx: OpContext) -> OpResult:
    params = cast(LabelParams, ctx.params)
    source = ctx.inputs[0]
    if not params.text.strip():
        raise ValidationError(
            field="text",
            detail=_("Ohne Text gibt es nichts aufzubringen."),
            constraint="empty",
        )

    shapes = outlines(params.text, params.size, params.font)
    if not shapes:
        raise ValidationError(
            field="text",
            detail=_("Aus diesem Text ließ sich keine Form bilden."),
            value=params.text,
            constraint="no_outline",
        )

    mode = cast(Placement, params.mode)
    depth = params.depth + BOOLEAN_OVERLAP
    body = label_solid(shapes, depth)
    if body is None:
        raise ValidationError(
            field="text",
            detail=_("Aus diesem Text ließ sich keine Form bilden."),
            constraint="no_outline",
        )

    # Zentriert auf dem angeklickten Punkt, nicht dort beginnend: eine
    # Beschriftung wächst um ihren Ort herum, und genau das erwartet, wer eine
    # anbringt.
    #
    # Wohin sie reicht, hängt an der Art. Erhaben: die Tiefe steht über der
    # Fläche, nur die Überlappung reicht hinein. Graviert: die Tiefe reicht
    # hinein, nur die Überlappung steht über — sonst nimmt der Schnitt die
    # Überlappung weg und lässt die Buchstaben als Kratzer zurück.
    middle = body.bounds.centre
    lift = -BOOLEAN_OVERLAP if mode == "raised" else -params.depth
    body = apply(body, translation((-middle[0], -middle[1], lift)))

    placed = place(
        body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz), params.angle
    )
    body_mesh = as_mesh_data(source.mesh)
    slots = list(source.material_slots)
    if params.slot and mode == "raised":
        # §20: die Buchstaben tragen einen eigenen Slot in die Vereinigung,
        # und die Attributübertragung der Booleschen Op bringt ihn auf der
        # anderen Seite wieder heraus. Das macht aus einer zweifarbigen
        # Beschriftung eine Datei statt zwei.
        placed = with_slot(placed, params.slot)
        if not body_mesh.slots:
            body_mesh = with_slot(body_mesh, 0)
        slots = _with_slot_named(slots, params.slot)

    kind: BooleanKind = "union" if mode == "raised" else "difference"
    outcome = boolean(kind, [body_mesh, placed], quality=ctx.quality, cut_slot=0)

    # Eine Beschriftung, die den Körper nicht erreicht hat, sagt das (§2.7).
    #
    # Die Auskunft gab es überall sonst — beim Bohren, beim Stopfen, bei jedem
    # Baustein, bei der Skizzentasche —, und hier nicht: gemessen an einem
    # Rahmen, dessen Hüllquader in der Mitte hohl ist, kam „BASIS" graviert mit
    # unverändertem Volumen und unveränderter Dreieckszahl zurück, und der
    # Prüfbericht hatte dazu keine Zeile. Erhaben ist es schlimmer als
    # graviert: die Buchstaben stehen dann als eigene Komponente neben dem
    # Teil und reisen bis in den Export mit.
    nothing = without_effect(body_mesh, outcome.mesh, kind, ctx.profile)
    # **Und die zweite Hälfte derselben Auskunft.** ``without_effect`` fragt
    # nach dem Volumen und schweigt deshalb genau dann, wenn die Schrift
    # danebenfällt statt zu fehlen — dort ist Volumen dazugekommen.
    apart = _fell_apart(body_mesh, outcome.mesh, mode)
    # **Und die dritte Hälfte.** Weder danebengefallen noch wirkungslos, sondern
    # im Körper verschwunden — die Volumenfrage, aber gegen die Schrift gehalten.
    buried = _buried(placed, body_mesh, outcome.mesh, mode)

    _log.info("labelled with %r, %s", params.text, mode)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={}, material_slots=slots)],
        solver=outcome.solver,
        findings=[
            *outcome.findings,
            *([nothing] if nothing is not None else []),
            *([apart] if apart is not None else []),
            *([buried] if buried is not None else []),
        ],
    )


@op_params
class LabelBodyParams(BaseParams):
    text: str = param(title=_("Text"), doc=_("Was der Körper sagen soll."))
    size: float = param(
        title=_("Schriftgröße"),
        default=8.0,
        unit="mm",
        minimum=MIN_SIZE,
        maximum=200.0,
        doc=_SIZE,
    )
    depth: float = param(
        title=_("Dicke"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=50.0,
        doc=_("Wie dick die Buchstaben werden. Zum Aufkleben reichen wenige Zehntel."),
    )
    font: str = param(
        title=_("Schrift"),
        default=FONTS[0],
        choices=FONTS,
        placement="advanced",
        doc=_FONT,
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_MORE, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_MORE, placement="advanced"
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=NAME_DOC,
    )


@register_op(
    name="create_label",
    title=_("Schriftzug als Körper"),
    category="label",
    params=LabelBodyParams,
    consumes=0,
    produces=1,
    doc=_(
        "Legt einen Schriftzug als eigenes Objekt an — für den Zweifarbendruck "
        "mit zwei Dateien und für Buchstaben, die aufgeklebt werden."
    ),
)
def create_label(ctx: OpContext) -> OpResult:
    """§25: dieselben Umrisse, für sich stehend statt auf einem Teil.

    Zwei Farben gibt es auf beiden Wegen: dieser hier als zweite Datei für
    einen Drucker, der das Filament von Hand wechselt, und ``label_text`` mit
    einem Slot für eine Maschine, die die Gruppen aus einer 3MF liest (§20).
    Was besser ist, hängt am Drucker — darum gibt es beides.
    """
    params = cast(LabelBodyParams, ctx.params)
    if not params.text.strip():
        raise ValidationError(
            field="text",
            detail=_("Ohne Text gibt es nichts anzulegen."),
            constraint="empty",
        )

    shapes = outlines(params.text, params.size, params.font)
    body = label_solid(shapes, params.depth) if shapes else None
    if body is None:
        raise ValidationError(
            field="text",
            detail=_("Aus diesem Text ließ sich keine Form bilden."),
            value=params.text,
            constraint="no_outline",
        )

    middle = body.bounds.centre
    placed = apply(
        body,
        translation((params.x - middle[0], params.y - middle[1], params.z)),
    )
    return OpResult(
        outputs=[SceneObject(id="", name=params.name or params.text.strip()[:20], mesh=placed)]
    )


def _with_slot_named(slots: list[MaterialSlot], index: int) -> list[MaterialSlot]:
    """Fügt den Slot an, in den die Schrift kommt; ein schon benannter bleibt."""
    known = {entry.index: entry for entry in slots}
    known.setdefault(0, MaterialSlot(index=0, name=str(_("Körper"))))
    known.setdefault(index, MaterialSlot(index=index, name=str(_("Schrift"))))
    return [known[key] for key in sorted(known)]
