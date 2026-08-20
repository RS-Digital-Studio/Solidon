"""Ein Deckel für eine Öffnung (Bauplan §25, §14).

Die häufigste zweite Hälfte eines Teils. Jemand hat eine Box — hier
modelliert, heruntergeladen oder gescannt — und braucht etwas, das sie
verschließt. Von Hand heißt das: den Hohlraum ausmessen, ihn einen Tick
kleiner nachzeichnen, und am Drucker herausfinden, um wie viel der Tick
falsch war.

Der Hohlraum wird nicht gemessen, er wird genommen: ein Schnitt durch die
Wand auf Höhe der Öffnung liefert die Außenkontur und das Loch darin, und der
Kragen ist dieses Loch, geschrumpft um das Spiel aus dem Materialprofil
(§12). Die Zahl, die entscheidet, ob der Deckel passt, ist also dieselbe, die
die Passungsprüfung benutzt — und eine Materialkalibrierung (§28.3) erreicht
einen Deckel, der vor ihr gebaut wurde.
"""

from __future__ import annotations

import dataclasses
from typing import Any, cast

import trimesh

from app.core.errors import ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import BOOLEAN_OVERLAP
from app.core.knowledge.parts.build import face
from app.core.knowledge.parts.shapes import RIDGE_SHARE, thread_body
from app.core.knowledge.profiles import for_object
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.scene.placement import faces_up
from app.core.slice.analysis import cross_section
from app.core.types import BaseParams, Feature, Finding, OpContext, OpResult, SceneObject
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie weit unter dem Rand der Schnitt genommen wird. Exakt an der Oberkante
#: trifft ein Schnitt das Ende der Wand und liefert eine Linie statt eines
#: Rings; einen Zehntelmillimeter tiefer ist er sicher im Material.
BELOW_RIM = 0.1

#: Darunter ist ein Hohlraum eine Bohrung, keine Öffnung — 100 mm² sind ein
#: Loch von elf Millimetern, und niemand steckt einen Deckelkragen in ein
#: Schraubenloch. Darüber zählt jeder Ring, auch ein kleines Fach neben einem
#: großen: ein Schlitz von zwölf Millimetern im Quadrat nimmt einen Kragen
#: bestens, und Hohlräume gegeneinander statt gegen eine Größe zu messen
#: würfe ihn weg.
MIN_CAVITY = 100.0

#: Wie der Kragen zu seinem Maß kommt — und warum hier keine Zahl mehr steht.
#:
#: Es stand eine: ``COLLAR_RELIEF = 0.2``, „damit der Deckel nicht auf dem
#: Kragen sitzt statt auf dem Rand". Das ist eine Zahlenkonstante für eine
#: Toleranz, und genau die verbietet Regel 7 — sie untergräbt die
#: Kalibrierung (§28.3): Wer sein Material misst und 0,15 mm einträgt, bekam
#: trotzdem 0,55 mm Luft je Seite.
#:
#: Dass der Kragen nicht klemmt, ist die Aufgabe des Gleitspiels aus dem
#: Materialprofil. Dafür ist es da, und dafür wird es gemessen.
#:
#: **Und es ist ein Durchmessermaß**, wie überall sonst im Haus: Ein
#: Passstift bekommt seine Bohrung als ``diameter + play``
#: (``knowledge/parts/mechanics.py``), und die Passungsprüfung rechnet
#: ``hole_diameter - pin_diameter`` (``scene/fits.py``). Der Kragen wurde als
#: einziger radial eingezogen — der Deckel bekam damit das doppelte Spiel,
#: und die Passung des Beispiels „Dose mit Deckel" meldete bei jedem Öffnen
#: 0,90 mm statt 0,25 mm.

#: Die beiden Merkmale, die ein Deckel und seine Schachtel teilen. Sie tragen
#: feste Namen, weil eine Passung auf Namen zeigt und nicht auf Geometrie
#: (§14): der Ablauf kann das Paar damit anlegen, bevor irgendetwas gerechnet
#: ist. Ohne sie gäbe es nichts, worauf ein ``Fit`` verweisen könnte — und
#: genau deshalb trug ein Deckel bisher keine Passung.
COLLAR_FEATURE = "lid_collar"
CAVITY_FEATURE = "lid_cavity"


def _area_of(cavities: list[Any]) -> float:
    """Wie viel Öffnung der Kragen ausfüllt."""
    return float(sum(cavity.area for cavity in cavities))


def _centre_of(cavities: list[Any], z: float) -> tuple[float, float, float]:
    """Die Mitte der Öffnung, auf Höhe des Schnitts.

    Bei mehreren Fächern der flächengewichtete Schwerpunkt — es ist eine
    Passung über die ganze Öffnung, nicht eine je Fach.
    """
    total = _area_of(cavities)
    if total <= EPS_GEOM:
        return (0.0, 0.0, z)
    x = sum(cavity.centroid.x * cavity.area for cavity in cavities) / total
    y = sum(cavity.centroid.y * cavity.area for cavity in cavities) / total
    return (float(x), float(y), float(z))


def _narrowest(cavities: list[Any]) -> float:
    """Die engste Weite der Öffnung — das Maß, an dem eine Passung hängt.

    Ein Deckel klemmt nicht an der Fläche, sondern an der schmalsten Stelle:
    dort sitzt der Kragen am nächsten an der Wand. Genommen wird die kürzere
    Seite des Hüllrechtecks, bei mehreren Fächern die kleinste davon.
    """
    widths: list[float] = []
    for cavity in cavities:
        left, bottom, right, top = cavity.bounds
        widths.append(min(right - left, top - bottom))
    return float(min(widths)) if widths else 0.0


def _measurable(
    identifier: str, area: float, centre: tuple[float, float, float], width: float
) -> tuple[str, Feature]:
    """Ein Flächenmerkmal, das zusätzlich seine Weite kennt.

    Ohne die Weite ist die Passung zwar eingetragen, aber nicht prüfbar:
    ``fits.check`` sucht bei einer Spielpassung zwei Durchmesser und meldet
    sonst „lässt sich nicht messen". Eine Passung, die nur dasteht, ist die
    halbe Zusicherung — sie wirkt auf den Slicer und sagt nichts darüber, ob
    der Deckel passt.
    """
    key, feature = face(identifier, area, centre)
    params = dict(feature.params)
    params["diameter"] = round(width, 4)
    return key, dataclasses.replace(feature, params=params)


def _with_cavity(source: SceneObject, cavities: list[Any], z: float) -> dict[str, Any]:
    """Die Merkmale der Schachtel plus dem, auf das der Deckel passt.

    Die Öffnung war bis hierher namenlos: die Erkennung sieht einen Hohlraum,
    aber kein Merkmal, das eine Passung benennen könnte. Der Deckel weiß es
    besser — er hat gerade hineingeschnitten.
    """
    features = dict(source.features)
    key, feature = _measurable(
        CAVITY_FEATURE, _area_of(cavities), _centre_of(cavities, z), _narrowest(cavities)
    )
    features[key] = feature
    return features


def opening(mesh: MeshData, z: float) -> tuple[Any, list[Any]]:
    """Der Wandring auf dieser Höhe, als gefüllter Umriss plus was darin offen
    ist.

    Der Schnitt selbst ist ein Ring — Wandmaterial mit dem Hohlraum als Loch.
    Der Deckel soll dieses Loch *bedecken*, also kommt als Umriss der
    aufgefüllte Ring zurück; den Schnitt zu nehmen, wie er ist, ergäbe einen
    Deckel mit herausgeschnittener Öffnung.

    Wirft, wenn es nichts zu schließen gibt: ein Körper, der hier massiv ist,
    hat keine Öffnung, und ein Deckel darüber wäre eine auf einen Block
    geklebte Platte.
    """
    from shapely.ops import unary_union

    section = cross_section(mesh, z)
    if section is None or section.is_empty:
        raise ValidationError(
            field="z",
            detail=_("Auf dieser Höhe schneidet die Ebene den Körper nicht."),
            value=round(z, 2),
            constraint="no_section",
        )

    parts = list(getattr(section, "geoms", [section]))
    cavities = [ring for part in parts for ring in _holes_of(part) if ring.area >= MIN_CAVITY]
    if not cavities:
        raise ValidationError(
            field="z",
            detail=_("Der Körper ist auf dieser Höhe massiv — es gibt nichts zu verschließen."),
            value=round(z, 2),
            constraint="no_cavity",
        )
    return unary_union([_filled(part) for part in parts]), cavities


def _filled(part: Any) -> Any:
    from shapely.geometry import Polygon as ShapelyPolygon

    return ShapelyPolygon(part.exterior)


def _holes_of(part: Any) -> list[Any]:
    from shapely.geometry import Polygon as ShapelyPolygon

    return [ShapelyPolygon(ring) for ring in getattr(part, "interiors", [])]


def plane_of(source: SceneObject, name: str, stated: float) -> float:
    """Die Höhe, auf der die Öffnung liegt: aus der gewählten Fläche, oder aus
    der Zahl.

    Eine Fläche schlägt die Zahl, denn sie ist die spezifischere von beiden —
    die Zahl fällt auf die Oberkante des Körpers zurück, was eine Vermutung
    ist, während eine Fläche das ist, was jemand angeklickt hat. Beide stehen
    in der Datei — die Antwort hängt also nicht davon ab, was beim
    Wiederöffnen des Projekts gerade ausgewählt ist (§11).

    Eine Fläche, die nicht nach oben schaut, wird abgewiesen statt als Höhe
    gelesen. Jede Fläche hat einen Mittelpunkt mit einem Z darin, und die
    Decke eines Hohlraums einen, der im Teil liegt — als Öffnungshöhe
    genommen setzte er den Deckel mitten in die Box, auf 26,9 von 30
    Millimetern, und weiter unten fiel es niemandem auf, weil ein Schnitt
    unter dieser Ebene die Wand ja trifft.
    """
    if not name:
        return stated or float(source.mesh.bounds.maximum[2])

    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            value=name,
            constraint="unknown_feature",
            values={"known": ", ".join(sorted(source.features))},
        )
    if feature.kind != "face":
        raise ValidationError(
            field="at_feature",
            detail=_("Ein Deckel braucht eine Fläche, kein anderes Merkmal."),
            value=name,
            constraint="not_a_face",
            values={"kind": feature.kind},
        )
    if not faces_up(feature):
        raise ValidationError(
            field="at_feature",
            detail=_("Diese Fläche zeigt nicht nach oben — eine Öffnung für einen Deckel schon."),
            value=name,
            constraint="not_upright",
        )
    centre = feature.params.get("centre") or (0.0, 0.0, 0.0)
    return float(centre[2])


def build(
    outline: Any,
    cavities: list[Any],
    *,
    thickness: float,
    collar: float,
    clearance: float,
    z: float,
) -> MeshData:
    """Platte plus Kragen, stehend auf dem Rand der Öffnung.

    Die Platte deckt den ganzen Umriss ab, damit sie aussieht wie die Box, zu
    der sie gehört. Der Kragen greift in jeden Hohlraum hinab — eine
    unterteilte Box bekommt einen je Fach, denn genau das hält den Deckel vom
    Verdrehen ab.
    """
    plates = [
        trimesh.creation.extrude_polygon(piece, height=thickness)
        for piece in getattr(outline, "geoms", [outline])
    ]
    for plate in plates:
        plate.apply_translation((0.0, 0.0, z))

    bodies = list(plates)
    for cavity in cavities if collar > EPS_GEOM else []:
        # Halbes Spiel je Seite, denn ``clearance`` ist ein Durchmessermaß.
        shrunk = cavity.buffer(-clearance / 2.0, join_style=2)
        if shrunk.is_empty or shrunk.area <= EPS_GEOM:
            continue
        for piece in getattr(shrunk, "geoms", [shrunk]):
            body = trimesh.creation.extrude_polygon(piece, height=collar)
            body.apply_translation((0.0, 0.0, z - collar))
            bodies.append(body)

    if len(bodies) == 1:
        return MeshData.of(bodies[0])
    joined = MeshData.of(bodies[0])
    for entry in bodies[1:]:
        joined = boolean("union", [joined, MeshData.of(entry)]).mesh
    return joined


@op_params
class LidParams(BaseParams):
    thickness: float = param(
        title=_("Deckelstärke"),
        default=2.4,
        unit="mm",
        minimum=0.4,
        maximum=50.0,
        doc=_("Wie dick die Deckelplatte wird — der Kragen darunter kommt aus dem Hohlraum."),
    )
    collar: float = param(
        title=_("Kragentiefe"),
        default=4.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_("Wie weit der Kragen in die Öffnung reicht. Null heißt: flacher Deckel ohne Kragen."),
    )
    at_feature: str = param(
        title=_("An Fläche"),
        kind="feature",
        default="",
        doc=_(
            "Name einer erkannten Fläche, etwa face_1 — dann liegt die Öffnung in "
            "deren Ebene. Wird beim Anklicken im Fenster eingetragen."
        ),
    )
    z: float = param(
        title=_("Höhe der Öffnung"),
        default=0.0,
        unit="mm",
        doc=_("Null nimmt die Oberkante des Körpers. Eine gewählte Fläche geht vor."),
    )
    clearance: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_("Null heißt: der Wert aus dem Materialprofil."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Solidon vergibt einen."),
    )


@register_op(
    name="create_lid",
    title=_("Deckel erzeugen"),
    category="parts",
    params=LidParams,
    consumes=1,
    produces=2,
    applies_to=["face"],
    doc=_(
        "Erzeugt zu einer Öffnung einen passenden Deckel mit Kragen. Der Hohlraum "
        "wird aus dem Körper geschnitten, nicht nachgemessen — das Spiel kommt aus "
        "dem Materialprofil."
    ),
)
def create_lid(ctx: OpContext) -> OpResult:
    """§25: die zweite Hälfte jeder Box.

    Der Deckel bleibt, wo die Öffnung ist, statt aufs Bett zu springen. Ob er
    die Box schließt, ist die Frage, die jemand in diesem Moment hat, und das
    sieht man nur an Ort und Stelle; das Anordnen für den Druck ist eine
    eigene Operation und kennt auch jeden anderen Körper.
    """
    params = cast(LidParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    z = plane_of(source, params.at_feature, params.z)
    outline, cavities = opening(mesh, z - BELOW_RIM)

    clearance = params.clearance
    if not clearance:
        if ctx.profile is None:
            raise ValidationError(
                field="clearance",
                detail=_("Ohne Profil muss das Spiel angegeben werden."),
                constraint="no_profile",
            )
        clearance = for_object(ctx.profile, source).material.clearance

    body = build(
        outline,
        cavities,
        thickness=params.thickness,
        collar=params.collar,
        clearance=clearance,
        z=z,
    )

    _log.info("lid over %d cavities at z=%.2f, clearance %.2f", len(cavities), z, clearance)
    # Das Gehäuse bleibt der erste Ausgang: eine Op mit consumes=1 ersetzt im
    # Stapel ihre Eingabe durch ihre Ausgaben — mit nur dem Deckel als Ausgang
    # fraß „Deckel erzeugen" das Gehäuse. Die Op-Tests riefen die Funktion
    # direkt auf und sahen es nie; der Ende-zu-Ende-Weg von P13 sah es sofort.
    return OpResult(
        outputs=[
            dataclasses.replace(source, features=_with_cavity(source, cavities, z)),
            SceneObject(
                id="",
                name=params.name or f"{source.name} {_('Deckel').translate()}",
                mesh=body,
                material=source.material,
                features=dict(
                    [
                        _measurable(
                            COLLAR_FEATURE,
                            _area_of(cavities),
                            _centre_of(cavities, z),
                            # Der Kragen ist genau um Spiel und Entlastung
                            # schmaler als die Öffnung — beidseitig, also
                            # zweimal. Dieselbe Rechnung, die ``build`` mit
                            # ``buffer`` an der Kontur macht.
                            _narrowest(cavities) - clearance,
                        )
                    ]
                ),
            ),
        ],
        findings=[
            Finding(
                code="parts.lid",
                severity="info",
                message=_("Deckel erzeugt — das Spiel kommt aus dem Materialprofil."),
                values={
                    "cavities": len(cavities),
                    "clearance_mm": round(clearance, 3),
                    "z_mm": round(z, 2),
                },
            )
        ],
    )


# --- Der Drehdeckel --------------------------------------------------------------

#: Steigung eines gedruckten Grobgewindes. Grob mit Absicht: ein Glasdeckel
#: wird von Hand gedreht, und eine halbe Umdrehung soll ihn schließen — einen
#: feinen Grat rundet die Düse weg, bis nichts mehr greift.
DEFAULT_PITCH = 3.0

#: Um wie viel die Gewindeschürze des Deckels höher ist als der Hals, damit
#: der Deckel auf dem Rand aufsetzt und nicht auf dem Gewindeende.
SKIRT_RELIEF = 0.6

#: Segmente um einen gedrehten Körper. Gröber, und ein „runder" Hals ist ein
#: Vieleck, an dem der Deckel hakt.
NECK_SECTIONS = 96


def neck_diameters(outline: Any, cavities: list[Any]) -> tuple[float, float]:
    """Außen- und Bohrungsdurchmesser eines Halses, der zu dieser Öffnung passt.

    Beide kommen von der schmaleren Seite, nicht aus einem eingepassten Kreis:
    bei einer runden Öffnung *ist* das der Durchmesser, bei einer eckigen der
    größte runde Hals, den die Wand noch tragen kann. Ein Kreis durch die
    Ecken eines Quadrats stünde über dessen Seiten hinaus.
    """
    left, bottom, right, top = outline.bounds
    widest = max(cavities, key=lambda ring: ring.area)
    inner_left, inner_bottom, inner_right, inner_top = widest.bounds
    return (
        float(min(right - left, top - bottom)),
        float(min(inner_right - inner_left, inner_top - inner_bottom)),
    )


def _pipe(outer: float, inner: float, height: float, z: float) -> MeshData:
    """Ein Materialring, stehend auf ``z``, ganz durchgehend offen."""
    shell = trimesh.creation.cylinder(radius=outer / 2.0, height=height, sections=NECK_SECTIONS)
    shell.apply_translation((0.0, 0.0, z + height / 2.0))
    if inner <= EPS_GEOM:
        return MeshData.of(shell)
    bore = trimesh.creation.cylinder(
        radius=inner / 2.0, height=height + 2.0 * BOOLEAN_OVERLAP, sections=NECK_SECTIONS
    )
    bore.apply_translation((0.0, 0.0, z + height / 2.0))
    return boolean("difference", [MeshData.of(shell), MeshData.of(bore)], quality="fine").mesh


def _lifted(body: MeshData, z: float) -> MeshData:
    raised = body.raw.copy()
    raised.apply_translation((0.0, 0.0, z))
    return body.replacing(raised)


@op_params
class ScrewLidParams(BaseParams):
    height: float = param(
        title=_("Gewindehöhe"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=100.0,
        doc=_("Wie hoch der Gewindehals wird. Zwei Umdrehungen halten, drei sitzen fest."),
    )
    pitch: float = param(
        title=_("Steigung"),
        default=DEFAULT_PITCH,
        unit="mm",
        minimum=1.0,
        maximum=10.0,
        doc=_("Grob, damit der Drucker sie auflöst und eine halbe Drehung schließt."),
    )
    thickness: float = param(
        title=_("Deckelstärke"),
        default=2.4,
        unit="mm",
        minimum=0.8,
        maximum=50.0,
        doc=_("Dicke der Deckelplatte über dem Gewinde."),
    )
    wall: float = param(
        title=_("Wandstärke des Deckels"),
        default=2.4,
        unit="mm",
        minimum=0.8,
        maximum=20.0,
        doc=_(
            "Dicke des Rands, der das Gewinde trägt. Zu dünn reißt beim Aufschrauben "
            "entlang der Schichten auf."
        ),
    )
    neck: float = param(
        title=_("Halsdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=400.0,
        placement="advanced",
        doc=_("Null nimmt die schmalere Seite der Öffnung."),
    )
    at_feature: str = param(
        title=_("An Fläche"),
        kind="feature",
        default="",
        doc=_(
            "Name einer erkannten Fläche, etwa face_1 — dann liegt die Öffnung in "
            "deren Ebene. Wird beim Anklicken im Fenster eingetragen."
        ),
    )
    z: float = param(
        title=_("Höhe der Öffnung"),
        default=0.0,
        unit="mm",
        doc=_("Null nimmt die Oberkante des Körpers. Eine gewählte Fläche geht vor."),
    )
    clearance: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_("Null heißt: der Wert aus dem Materialprofil."),
    )


@register_op(
    name="screw_lid",
    title=_("Drehdeckel erzeugen"),
    category="parts",
    params=ScrewLidParams,
    consumes=1,
    produces=2,
    applies_to=["face"],
    doc=_(
        "Setzt einen Gewindehals auf die Öffnung und erzeugt den passenden "
        "Schraubdeckel. Beide Gewinde kommen aus derselben Steigung, das Spiel "
        "aus dem Materialprofil."
    ),
)
def screw_lid(ctx: OpContext) -> OpResult:
    """§25: der Zwilling des eingeschobenen Deckels.

    Zwei Paare im Modellkorpus sind genau das und nichts anderes:
    ``gewuerzbehaelter_body`` neben ``deckel_dreh``, und ``kartuschen_kaefig``
    neben ``kartuschen_deckel``. Die Bausteinbibliothek hat ein Gewinde, aber
    nur in den metrischen Schraubengrößen M2 bis M8 — ein Glashals von vierzig
    Millimetern mit grober Steigung lag ganz außerhalb ihrer Reichweite.

    Beide Hälften kommen aus einer Operation, weil sie eine Entscheidung
    sind. Ein Hals mit der einen Steigung und ein Deckel mit einer anderen
    sind nicht zwei Fehler — es ist der eine Fehler, der am leichtesten
    passiert, wenn die Hälften getrennt entstehen.
    """
    params = cast(ScrewLidParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    z = plane_of(source, params.at_feature, params.z)
    outline, cavities = opening(mesh, z - BELOW_RIM)

    clearance = params.clearance
    if not clearance:
        if ctx.profile is None:
            raise ValidationError(
                field="clearance",
                detail=_("Ohne Profil muss das Spiel angegeben werden."),
                constraint="no_profile",
            )
        clearance = for_object(ctx.profile, source).material.clearance

    major, bore = neck_diameters(outline, cavities)
    if params.neck:
        major = params.neck

    ridge = params.pitch * RIDGE_SHARE
    core = major - 2.0 * ridge

    if core - bore <= EPS_GEOM:
        raise ValidationError(
            field="pitch",
            detail=_("Die Wand ist für diese Steigung zu dünn — das Gewinde hätte keinen Kern."),
            constraint="too_coarse",
            values={"neck_mm": round(major, 2), "bore_mm": round(bore, 2)},
        )

    # Der Kern trägt den Gang, ist also zwei Gangtiefen schmaler als das
    # Gewinde breit: auf einen Hals mit vollem Durchmesser vereinigt säße der
    # Gang im Material und änderte gar nichts.
    neck = _pipe(core, bore, params.height, z)
    turns = _lifted(thread_body(major, params.pitch, params.height), z)
    threaded = boolean("union", [mesh, neck], quality=ctx.quality).mesh
    threaded = boolean("union", [threaded, turns], quality=ctx.quality).mesh

    lid = _screw_cap(major, params, clearance)

    _log.info("screw lid: neck %.2f, pitch %.2f, clearance %.2f", major, params.pitch, clearance)
    return OpResult(
        outputs=[
            dataclasses.replace(source, mesh=threaded, features={}),
            SceneObject(
                id="",
                name=f"{source.name} {_('Drehdeckel').translate()}",
                mesh=lid,
                material=source.material,
            ),
        ],
        findings=[
            Finding(
                code="parts.screw_lid",
                severity="info",
                message=_("Gewindehals und Deckel erzeugt — beide mit derselben Steigung."),
                values={
                    "neck_mm": round(major, 2),
                    "pitch_mm": round(params.pitch, 2),
                    "clearance_mm": round(clearance, 3),
                },
            )
        ],
    )


def _screw_cap(major: float, params: ScrewLidParams, clearance: float) -> MeshData:
    """Der Deckel: eine Kappe, deren Innenseite das Gegenstück zum
    Halsgewinde trägt.

    Gebohrt auf den *Kern*-Durchmesser plus Spiel, nicht auf den
    Außendurchmesser. Das ist der ganze Unterschied zwischen Deckel und
    Hülse: auf den Außendurchmesser gebohrt bleibt nichts stehen, woran der
    Gang des Halses halten könnte, und der Deckel rutscht glatt ab. Dieselbe
    Regel wie bei der Mutter der Bausteinbibliothek, aus demselben Grund.

    Das offene Ende steht auf Z = 0 — so druckt er ohne jede Stütze.
    """
    skirt = params.height + SKIRT_RELIEF
    inside = major - 2.0 * params.pitch * RIDGE_SHARE + clearance
    outer = major + 2.0 * clearance + 2.0 * params.wall

    body = trimesh.creation.cylinder(
        radius=outer / 2.0, height=skirt + params.thickness, sections=NECK_SECTIONS
    )
    body.apply_translation((0.0, 0.0, (skirt + params.thickness) / 2.0))

    # Die zwei Formen, mit denen ein Gewindeloch geschnitten wird: die Bohrung
    # auf Kerndurchmesser, und die Nut, die von ihr bis zum Außendurchmesser
    # reicht.
    hollow = trimesh.creation.cylinder(
        radius=inside / 2.0, height=skirt + BOOLEAN_OVERLAP, sections=NECK_SECTIONS
    )
    hollow.apply_translation((0.0, 0.0, (skirt + BOOLEAN_OVERLAP) / 2.0 - BOOLEAN_OVERLAP))
    groove = thread_body(inside, params.pitch, skirt, internal=True)

    cutter = boolean("union", [MeshData.of(hollow), groove], quality="fine").mesh
    return boolean("difference", [MeshData.of(body), cutter], quality="fine").mesh
