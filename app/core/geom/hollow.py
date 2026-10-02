"""Aushöhlen, mit den Entlüftungen, die es druckbar machen (Bauplan §25).

Ein massives Teil ist Material und Stunden, die niemand braucht. Es
auszuhöhlen ist eine gute Idee mit einer Bedingung: Harz und ungeschmolzenes
Pulver beiseite — ein FDM-Druck mit geschlossenem Hohlraum sperrt Luft ein,
und die erste Brücke darüber sackt durch. Die Entlüftung ist hier also keine
Option — sie ist die zweite Hälfte der Operation, und die Vorgabe.

Wie die Innenwand gefunden wird: der Körper kommt auf dasselbe Raster wie die
Analysekarten (§18.4), das Raster wird um die Wandstärke erodiert — mit einer
Kugel als Strukturelement, sonst steht die Wand nur an achsparallelen Flächen
(:func:`_ball`) —, und was übrig bleibt, wird neu vernetzt. Das ist die
Voxelstufe aus §17.2 mit ihrer Genauigkeit und ihrer Ehrlichkeit — die Wand
stimmt auf einen halben Rasterschritt, und der Bericht sagt es.

Ein Versatz auf den Dreiecken selbst wäre exakt und faltete sich an jeder
konkaven Ecke ein — genau dort, wo ein hohles Teil die Wand am nötigsten
braucht.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Final, NoReturn

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import (
    CORRECT_INPUT,
    PROGRAMMING_ERRORS,
    BooleanFailedError,
    NotManifoldError,
)
from app.core.geom import kernel_process, lathe
from app.core.geom.boolean import BooleanOutcome, boolean, deepest
from app.core.geom.mesh import MeshData, concatenated
from app.core.geom.repair import open_edge_count
from app.core.log import get_logger
from app.core.types import (
    CancelToken,
    Finding,
    Profile,
    ProgressFn,
    Quality,
    SolverInfo,
    Vec3,
)
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie fein das Raster ist, relativ zur stehenbleibenden Wand. Ein Drittel der
#: Wand heißt: die Wand stimmt auf ein Sechstel ihrer selbst.
PITCH_SHARE = 1.0 / 3.0

#: Nie feiner als das — ein Raster aus hundert Millionen Zellen hilft niemandem.
MIN_PITCH = 0.3

#: Wie weit die Entlüftung in den Hohlraum hineinragt, damit sie den Boden
#: sicher durchstößt. Ein Marching-Cubes-Rand liegt auf einen halben
#: Rasterschritt genau; der feinste Rasterschritt ist ``MIN_PITCH`` = 0,3 mm
#: (an dünnen Wänden), ein Millimeter Überstand deckt ihn und die halben
#: Schritte gröberer Raster sicher. In fünf Körpern gemessen bricht sie durch.
VENT_BREAKTHROUGH = 1.0

#: Vorgabe-Durchmesser der Entlüftung. Weit genug, damit Luft entweicht, eng
#: genug, dass das Loch danach nicht verschlossen werden muss.
VENT_DIAMETER = 4.0

#: In wie viele Facetten die Entlüftungsbohrung zerfällt.
#:
#: Die Zahl stand bis zum 17.09.2026 nirgends: Der Aufruf ließ ``sections``
#: weg und bekam die Vorgabe von ``trimesh.creation.cylinder``. Sie bestimmt
#: aber die Geometrie, die der Kunde bekommt, und gehört deshalb hierher und
#: nicht in eine fremde Bibliothek. Der Wert ist der bisherige — die
#: Umstellung soll nichts am Ergebnis ändern.
VENT_SECTIONS = 32


@dataclass(slots=True)
class HollowResult:
    """Der hohle Körper, und was dazu zu sagen war."""

    mesh: MeshData
    removed: float = 0.0
    """Volumen, das entfernt wurde, in mm³."""
    vents: tuple[Vec3, ...] = ()
    findings: list[Finding] = field(default_factory=list)
    solver: SolverInfo | None = None
    """Die Rückfallstufe, auf der das Ergebnis zustande kam (§17.2).

    Aushöhlen fährt bis zu sechs Boolesche Schnitte — den Hohlraum, die
    Öffnung und je einen pro Entlüftung. Gemeldet hat es keine einzige Stufe,
    und damit stand im Bericht nichts darüber, ob die Wandstärke aus einem
    exakten Schnitt kommt oder aus einer Voxelnäherung."""


@dataclass(frozen=True, slots=True)
class Opening:
    """Eine gewählte ebene Fläche, die beim Aushöhlen offen bleibt (P6.3).

    ``triangles`` sind die Dreiecksnummern der Fläche im Netz, das ausgehöhlt
    wird; ``name`` ihre Merkmalskennung, damit ein Befund sagen kann, welche
    Öffnung gemeint ist.
    """

    triangles: tuple[int, ...]
    name: str = ""


def opening_plane(mesh: MeshData, triangles: tuple[int, ...]) -> tuple[Vec3, Vec3] | None:
    """Mitte und Normale einer ebenen Öffnungsfläche — ``None``, wenn sie nicht eben ist.

    Die Normale ist das flächengewichtete Mittel der Dreiecksnormalen und zeigt
    aus dem Material heraus. Eben heißt: Jede Ecke liegt höchstens
    ``FLAT_ENOUGH_FOR_A_TOOL`` neben der Ebene durch die Mitte. Am Netz öffnet
    nur eine ebene Fläche; eine gewölbte hat keinen Querschnitt, an dem die
    Öffnung als Umriss entsteht (Absage mit Weg in der Operation).
    """
    from app.core.geom.faces import FLAT_ENOUGH_FOR_A_TOOL

    raw = mesh.raw
    chosen = np.asarray(triangles, dtype=np.int64)
    if not chosen.size or int(chosen.max()) >= len(raw.faces) or int(chosen.min()) < 0:
        return None
    corners = np.asarray(raw.triangles, dtype=np.float64)[chosen]
    crossed = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    summed = crossed.sum(axis=0)
    length = float(np.linalg.norm(summed))
    if length <= EPS_GEOM:
        return None
    normal = summed / length
    points = corners.reshape(-1, 3)
    centre = points.mean(axis=0)
    if float(np.abs((points - centre) @ normal).max()) > FLAT_ENOUGH_FOR_A_TOOL:
        return None
    return (
        (float(centre[0]), float(centre[1]), float(centre[2])),
        (float(normal[0]), float(normal[1]), float(normal[2])),
    )


def hollow(
    mesh: MeshData,
    wall: float,
    *,
    vents: int = 1,
    vent_diameter: float = VENT_DIAMETER,
    open_top: bool = False,
    open_towards: Vec3 | None = None,
    openings: tuple[Opening, ...] = (),
    outward: bool = False,
    quality: Quality = "fine",
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> HollowResult:
    """Lässt eine Wand von ``wall`` Millimetern stehen und nimmt den Rest
    heraus.

    ``open_top`` nimmt zusätzlich die Decke über dem Hohlraum weg. Damit ist
    das Ergebnis eine Dose statt eines geschlossenen Körpers, und *Deckel
    erzeugen* findet die Öffnung, die es verlangt — der Weg dorthin führte
    sonst über zwei Zylinder und eine Differenz.

    ``open_towards`` öffnet stattdessen in **diese** Richtung (RM-087): die
    Vorderseite eines Puppenhauses, die Seite eines Regals. Eine Achsrichtung
    als Vektor — das Raster ist achsparallel, und die Öffnung ist der letzte
    Querschnitt des Hohlraums in dieser Richtung, durchgezogen bis über den
    Rand. Gesetzt schlägt es ``open_top``; beides ist dieselbe Sache mit
    anderer Richtung, und eine offene Seite braucht so wenig eine
    Entlüftung wie eine offene Decke.

    ``openings`` sind gewählte ebene Flächen, die offen bleiben (P6.3) — jede
    in ihrer eigenen Ebene, auch schräg. Gesetzt gehen sie vor ``open_top``
    und ``open_towards``; die Operation lässt die Mischung mit ``open_towards``
    nicht zu und legt die Oberseite bei ``open_top`` als Fläche dazu.

    ``outward`` lässt die Wand außen wachsen: Der Körper selbst wird der
    Hohlraum, die Wand legt sich mit einer Kugel als Werkzeug um ihn — runde
    Stöße wie am exakten Kern (``GeomAbs_Arc``). Ohne beides ist es der Weg,
    den gespeicherte Schritte immer gegangen sind, und er rechnet unverändert.
    """
    if wall <= EPS_GEOM:
        raise ValueError("a wall thickness has to be positive")
    direction: Vec3 | None = open_towards if open_towards is not None else None
    if direction is None and open_top:
        direction = (0.0, 0.0, 1.0)
    # **Ein Wächter für jede Boolesche** (RM-170): Reißt die Kette an einem
    # nicht geschlossenen Körper, ist die offene Hülle der Grund, gleich an
    # welchem Schnitt — Hohlraum, Öffnung, Entlüftung, Wand außen. Er steht
    # hier einmal und nicht in jedem Helfer; die Prüfung über den Syntaxbaum
    # (``test_the_hull_is_named_at_every_boolean_of_the_hollowing``) folgt den
    # Aufrufen bis in die Helfer.
    try:
        if openings:
            return _hollow_with_openings(
                mesh,
                wall,
                openings,
                outward=outward,
                quality=quality,
                progress=progress,
                cancelled=cancelled,
            )
        if outward:
            return _hollow_outward(
                mesh,
                wall,
                vents=vents,
                vent_diameter=vent_diameter,
                direction=direction,
                quality=quality,
                progress=progress,
                cancelled=cancelled,
            )
        return _hollow_inward(
            mesh,
            wall,
            vents=vents,
            vent_diameter=vent_diameter,
            direction=direction,
            quality=quality,
            progress=progress,
            cancelled=cancelled,
        )
    except BooleanFailedError as failure:
        _the_hull_or_the_chain(mesh, failure)


def _hollow_inward(
    mesh: MeshData,
    wall: float,
    *,
    vents: int,
    vent_diameter: float,
    direction: Vec3 | None,
    quality: Quality,
    progress: ProgressFn | None,
    cancelled: CancelToken | None,
) -> HollowResult:
    """Der Weg, den gespeicherte Schritte immer gegangen sind: Wand innen,
    geschlossen, oben oder zu einer Achsrichtung offen, mit Entlüftungen.

    Unverändert aus :func:`hollow` herausgelöst (P6.3) — die goldenen Volumina
    in ``tests/test_hollow_faces.py`` halten ihn auf dem Stand davor.
    """
    # §15.6: Aushöhlen rastert einen ganzen Körper und fährt danach bis zu sechs
    # Boolesche Schnitte. Das dauert an einem gescannten Teil Minuten, und bis
    # hierher erfuhr niemand davon — weder wie weit es ist noch dass man
    # abbrechen kann. Gemeldet wird zwischen den Stufen: eine Stufe selbst ist
    # ein nativer Aufruf und kooperativ nicht zu unterbrechen (dieselbe Grenze
    # wie in :func:`app.core.geom.boolean.boolean`).
    _step(progress, cancelled, 0.05, _("Raster aufbauen"))
    field = _inner_field(mesh, wall)
    cavity = _meshed(field[0], field[1], field[2], mesh) if field is not None else None
    if cavity is None or cavity.triangle_count == 0:
        return HollowResult(
            mesh=mesh,
            findings=[too_thin(wall)],
        )

    before = mesh.volume
    _step(progress, cancelled, 0.4, _("Hohlraum ausschneiden"))
    outcome = boolean("difference", [mesh, cavity], quality=quality, cancelled=cancelled)
    enclosed = _enclosed_cavity(mesh, cavity, outcome, before, quality, cancelled)
    body = outcome.mesh
    findings = [*outcome.findings, *enclosed.findings]
    stages: list[SolverInfo | None] = [outcome.solver, enclosed.solver]

    if direction is not None and field is not None:
        opening = _mouth(field[0], direction)
        tool = _meshed(opening, field[1], field[2], mesh) if opening is not None else None
        if tool is None:
            findings.append(
                Finding(
                    code="hollow.no_opening",
                    severity="warning",
                    message=_(
                        "Die Öffnung ließ sich nicht schneiden — der Hohlraum reicht "
                        "nicht bis unter die Wand, die geöffnet werden soll."
                    ),
                    # Regel 17: Die Öffnung wählt man im Schritt neu.
                    suggestions=(CORRECT_INPUT,),
                )
            )
        else:
            opened = boolean("difference", [body, tool], quality=quality, cancelled=cancelled)
            body = opened.mesh
            findings.extend(opened.findings)
            stages.append(opened.solver)

    placed: tuple[Vec3, ...] = ()
    # Eine offene Dose ist ihre eigene Entlüftung. Ein Loch im Boden wäre dort
    # kein Schutz vor der durchsackenden Decke, sondern ein Loch im Boden.
    if vents > 0 and direction is None:
        body, placed, drilled, said = _drill_vents(
            body, cavity, field, vents, vent_diameter, quality, progress, cancelled
        )
        stages.extend(drilled)
        findings.extend(said)

    removed = before - body.volume
    _log.info("hollowed out %.1f mm³ behind a %.2f mm wall", removed, wall)
    values: dict[str, float | int | str] = {
        "removed_cm3": round(removed / 1000.0, 1),
        "vents": len(placed),
        # Wohin geöffnet wurde, als Wort — „+z" für die Decke, „-y"
        # für die Vorderseite. Ohne Öffnung steht dort nichts.
        "opening": _direction_name(direction) if direction is not None else "",
    }
    findings.extend(
        _raster_findings(wall, values, opened=body if vents > 0 or direction is not None else None)
    )
    return HollowResult(
        mesh=replace(body, cavity=enclosed.mesh),
        removed=removed,
        vents=placed,
        findings=findings,
        solver=deepest(stages),
    )


def _outer_field(mesh: MeshData, wall: float) -> tuple[np.ndarray, np.ndarray, Vec3, float]:
    """Das Raster des Körpers und seine um die Wand gewachsene Hülle (Wand außen).

    Zurück kommen der Körper selbst — er ist außen der Hohlraum —, die Hülle,
    der Ursprung und die Weite. Das Raster wird vorher um die Wand und zwei
    Zellen erweitert: ``solid_field`` lässt ringsum nur eine leere Zelle, und
    eine Kugel von ``steps`` Zellen fiele sonst vom Rand. Gewachsen wird mit
    derselben Kugel, mit der innen erodiert wird (:func:`_ball`) — die Stöße
    werden damit rund, wie am exakten Kern.
    """
    from scipy import ndimage

    from app.core.perceive.maps import solid_field

    steps, pitch = erosion_steps(wall)
    field = solid_field(mesh, pitch)
    margin = steps + 2
    body = np.pad(field.filled, margin)
    grown = ndimage.binary_dilation(body, structure=_ball(steps))
    origin = np.asarray(field.origin, dtype=float) - margin * pitch
    return body, grown, (float(origin[0]), float(origin[1]), float(origin[2])), pitch


def _hollow_outward(
    mesh: MeshData,
    wall: float,
    *,
    vents: int,
    vent_diameter: float,
    direction: Vec3 | None,
    quality: Quality,
    progress: ProgressFn | None,
    cancelled: CancelToken | None,
) -> HollowResult:
    """Die Wand wächst außen: Der Körper wird zum Hohlraum (P6.3).

    Die Hülle ist das um die Wand gewachsene Raster, neu vernetzt; der Körper
    selbst geht exakt als Innenseite hinein. Eine Öffnung nach ``direction``
    nimmt die Wand über dem äußersten Querschnitt des Körpers weg, um die
    Wand in der Ebene verbreitert (:func:`_outward_mouth`) — der Rand bleibt
    bündig mit der Fläche, über die geöffnet wird.
    """
    _step(progress, cancelled, 0.05, _("Raster aufbauen"))
    inner, grown, origin, pitch = _outer_field(mesh, wall)
    outer = _meshed(grown, origin, pitch, mesh)
    if outer is None:
        return HollowResult(mesh=mesh, findings=[too_thin(wall)])
    before = mesh.volume
    _step(progress, cancelled, 0.4, _("Wand legen"))
    outcome = boolean("difference", [outer, mesh], quality=quality, cancelled=cancelled)
    body = outcome.mesh
    findings = list(outcome.findings)
    stages: list[SolverInfo | None] = [outcome.solver]
    if direction is not None:
        steps, _pitch = erosion_steps(wall)
        opening = _outward_mouth(inner, direction, steps)
        tool = _meshed(opening, origin, pitch, mesh) if opening is not None else None
        if tool is not None:
            opened = boolean("difference", [body, tool], quality=quality, cancelled=cancelled)
            body = opened.mesh
            findings.extend(opened.findings)
            stages.append(opened.solver)
    placed: tuple[Vec3, ...] = ()
    if vents > 0 and direction is None:
        body, placed, drilled, said = _drill_vents(
            body,
            mesh,
            (inner, origin, pitch),
            vents,
            vent_diameter,
            quality,
            progress,
            cancelled,
        )
        stages.extend(drilled)
        findings.extend(said)
    values: dict[str, float | int | str] = {
        "material_cm3": round(body.volume / 1000.0, 1),
        "vents": len(placed),
        "opening": _direction_name(direction) if direction is not None else "",
    }
    findings.extend(
        _raster_findings(wall, values, opened=body if vents > 0 or direction is not None else None)
    )
    _log.info("hollowed %.1f mm³ outwards behind a %.2f mm wall", before, wall)
    return HollowResult(
        mesh=replace(body, cavity=MeshData.of(mesh.raw.copy())),
        removed=before - body.volume,
        vents=placed,
        findings=findings,
        solver=deepest(stages),
    )


def _outward_mouth(body: np.ndarray, direction: Vec3, steps: int) -> np.ndarray | None:
    """Das Raster der Öffnung bei Wand außen: der äußerste Querschnitt des
    Körpers in ``direction``, in der Ebene um die Wand verbreitert, jenseits
    davon bis an den Rand des Rasters.

    Verbreitert, weil die gewachsene Hülle an den Kanten rund über den
    Querschnitt hinausgreift: Ohne das stünde um die Öffnung ein Wulst von
    Wandhöhe, wo der exakte Kern den Rand bündig in der Ebene lässt. Jenseits
    des äußersten Querschnitts liegt vom Körper nichts mehr — was dort von
    der Hülle steht, gehört zu dieser Öffnung.
    """
    from scipy import ndimage

    axis = int(np.argmax(np.abs(np.asarray(direction, dtype=float))))
    forward = float(direction[axis]) > 0.0
    seen = np.moveaxis(body, axis, -1)
    opening = np.zeros_like(body)
    written = np.moveaxis(opening, axis, -1)
    if not forward:
        seen = seen[..., ::-1]
        written = written[..., ::-1]
    levels = np.flatnonzero(seen.any(axis=(0, 1)))
    if not len(levels):
        return None
    top = int(levels[-1])
    reach = np.arange(-steps, steps + 1)
    disk = (reach[:, None] ** 2 + reach[None, :] ** 2) <= steps**2
    wider = ndimage.binary_dilation(seen[..., top], structure=disk)
    written[..., top] = seen[..., top]
    written[..., top + 1 :] = wider[..., None]
    return opening if opening.any() else None


def _hollow_with_openings(
    mesh: MeshData,
    wall: float,
    openings: tuple[Opening, ...],
    *,
    outward: bool,
    quality: Quality,
    progress: ProgressFn | None,
    cancelled: CancelToken | None,
) -> HollowResult:
    """Aushöhlen mit gewählten ebenen Öffnungsflächen (P6.3).

    Die Wand entsteht wie ohne Öffnung (innen erodiert, außen gewachsen);
    danach schneidet je Fläche ein Werkzeug die Wand über ihr weg
    (:func:`_opening_tool`). Eine Fläche, unter der kein Hohlraum liegt, bleibt
    zu, und der Befund ``hollow.opening_misses`` nennt sie. Ein offener
    Hohlraum braucht keine Entlüftung.
    """
    _steps, pitch = erosion_steps(wall)
    before = mesh.volume
    _step(progress, cancelled, 0.05, _("Raster aufbauen"))
    stages: list[SolverInfo | None] = []
    findings: list[Finding] = []
    if outward:
        _inner, grown, origin, pitch = _outer_field(mesh, wall)
        outer = _meshed(grown, origin, pitch, mesh)
        if outer is None:
            return HollowResult(mesh=mesh, findings=[too_thin(wall)])
        cavity = MeshData.of(mesh.raw.copy())
        _step(progress, cancelled, 0.4, _("Wand legen"))
        outcome = boolean("difference", [outer, mesh], quality=quality, cancelled=cancelled)
    else:
        field = _inner_field(mesh, wall)
        found = _meshed(field[0], field[1], field[2], mesh) if field is not None else None
        if found is None or found.triangle_count == 0:
            return HollowResult(mesh=mesh, findings=[too_thin(wall)])
        cavity = found
        _step(progress, cancelled, 0.4, _("Hohlraum ausschneiden"))
        outcome = boolean("difference", [mesh, cavity], quality=quality, cancelled=cancelled)
    body = outcome.mesh
    findings.extend(outcome.findings)
    stages.append(outcome.solver)
    opened = 0
    for index, opening in enumerate(openings, start=1):
        _step(progress, cancelled, 0.5 + 0.4 * index / len(openings), _("Öffnungen schneiden"))
        tools = _opening_tool(mesh, cavity, opening, wall, pitch, outward=outward)
        if not tools:
            findings.append(_opening_misses(opening))
            continue
        for tool in tools:
            cut = boolean("difference", [body, tool], quality=quality, cancelled=cancelled)
            body = cut.mesh
            findings.extend(cut.findings)
            stages.append(cut.solver)
        opened += 1
    values: dict[str, float | int | str] = {"vents": 0, "openings": opened}
    if outward:
        values["material_cm3"] = round(body.volume / 1000.0, 1)
    else:
        values["removed_cm3"] = round((before - body.volume) / 1000.0, 1)
    findings.extend(_raster_findings(wall, values, opened=body))
    return HollowResult(
        mesh=replace(body, cavity=cavity),
        removed=before - body.volume,
        findings=findings,
        solver=deepest(stages),
    )


def _opening_misses(opening: Opening) -> Finding:
    """Unter dieser Fläche liegt kein Hohlraum — sie bleibt zu."""
    from app.core.errors import CHANGE_SELECTION, CORRECT_INPUT

    return Finding(
        code="hollow.opening_misses",
        severity="warning",
        message=_(
            "Unter dieser Fläche liegt kein Hohlraum, sie bleibt geschlossen. Dort ist "
            "das Teil dünner als zwei Wände — eine dünnere Wand oder eine andere "
            "Fläche wählen."
        ),
        feature_ids=(opening.name,) if opening.name else (),
        suggestions=(CORRECT_INPUT, CHANGE_SELECTION),
    )


def _opening_tool(
    mesh: MeshData,
    cavity: MeshData,
    opening: Opening,
    wall: float,
    pitch: float,
    *,
    outward: bool,
) -> list[MeshData]:
    """Die Werkzeuge, die die Wand über einer gewählten ebenen Fläche wegnehmen.

    Gerechnet in dem Bezugssystem, in dem die Fläche nach oben schaut
    (``autosplit.upright_normal``): Ihr Umriss ist dort die Vereinigung ihrer
    Dreiecke in der Ebene.

    **Innen** ist die Öffnung der Teil des Umrisses, unter dem der Hohlraum
    liegt — der Schnitt des Hohlraums eine Wand und eine Rasterweite unter
    der Fläche. Das Werkzeug reicht von dort bis eine Rasterweite über die
    Fläche: Der Hohlraum liegt auf einen halben Rasterschritt genau, die
    Wand darüber ist damit sicher durch. Eine Stelle, unter der das Teil
    dünner ist als zwei Wände, hat dort keinen Hohlraum und bleibt zu.

    **Außen** ist der Körper der Hohlraum, die Öffnung also der ganze Umriss.
    Über den **nach außen** gehenden Kanten der Fläche greift die gewachsene
    Hülle rund über den Umriss hinaus; ein zweites Werkzeug nimmt dort alles
    oberhalb der Flächenebene weg — der Rand bleibt bündig wie am exakten
    Kern. An einer nach innen gehenden Kante steigt die Nachbarwand über die
    Ebene; ihre Wand bleibt stehen.
    """
    import shapely
    from shapely.geometry import LineString, Polygon

    from app.core.geom.autosplit import sections_across, upright_normal

    plane = opening_plane(mesh, opening.triangles)
    if plane is None:
        return []
    _centre, normal = plane
    turn = upright_normal(normal)
    back = np.linalg.inv(turn)
    rotation = turn[:3, :3]
    raw = mesh.raw
    chosen = np.asarray(opening.triangles, dtype=np.int64)
    corners = np.asarray(raw.triangles, dtype=np.float64)[chosen] @ rotation.T
    level = float(corners[..., 2].mean())
    outline = shapely.union_all([Polygon(triangle[:, :2]) for triangle in corners]).buffer(0)
    if outline.is_empty:
        return []
    reach = wall + pitch
    if not outward:
        section = sections_across(cavity, normal, np.array([level - reach]))[0]
        if section is None or section.is_empty:
            return []
        region = outline.intersection(section)
        tool = _prism(region, level - reach, level + pitch, back, pitch)
        return [tool] if tool is not None else []
    tools = []
    below = _prism(outline, level - pitch, level + reach, back, pitch)
    if below is not None:
        tools.append(below)
    ring = [
        LineString(segment).buffer(reach)
        for segment in _outgoing_edges(mesh, chosen, rotation, level)
    ]
    if ring:
        rim = _prism(shapely.union_all(ring), level, level + reach, back, pitch)
        if rim is not None:
            tools.append(rim)
    return tools


def _outgoing_edges(
    mesh: MeshData, chosen: np.ndarray, rotation: np.ndarray, level: float
) -> list[np.ndarray]:
    """Die Randkanten der Fläche, hinter denen der Körper nach unten weggeht.

    Im aufgerichteten Bezugssystem, als Strecken in der Ebene. Eine Kante ist
    eine Randkante, wenn nur ein Dreieck der Fläche an ihr liegt; ob sie nach
    außen geht, sagt das Nachbardreieck jenseits von ihr: liegt seine Mitte
    unter der Flächenebene, fällt der Körper dort ab. Liegt sie darüber, steigt
    eine Wand auf, und deren eigene Wand bleibt stehen.
    """
    from app.core.geom.faces import FLAT_ENOUGH_FOR_A_TOOL

    raw = mesh.raw
    inside = np.zeros(len(raw.faces), dtype=bool)
    inside[chosen] = True
    pairs = np.asarray(raw.face_adjacency, dtype=np.int64)
    edges = np.asarray(raw.face_adjacency_edges, dtype=np.int64)
    if not len(pairs):
        return []
    crossing = inside[pairs[:, 0]] != inside[pairs[:, 1]]
    vertices = np.asarray(raw.vertices, dtype=np.float64) @ rotation.T
    centres = np.asarray(raw.triangles_center, dtype=np.float64) @ rotation.T
    found = []
    for (first, second), edge in zip(pairs[crossing], edges[crossing], strict=True):
        other = second if inside[first] else first
        if centres[other, 2] > level + FLAT_ENOUGH_FOR_A_TOOL:
            continue
        found.append(vertices[edge][:, :2])
    return found


def _prism(
    region: object, bottom: float, top: float, back: np.ndarray, pitch: float
) -> MeshData | None:
    """Ein Umriss als Prisma von ``bottom`` bis ``top``, zurück in die Welt gedreht.

    Splitter unter einer Rasterzelle Fläche fallen weg — sie entstehen, wo der
    Schnitt des Hohlraums den Umriss nur an seinem Rasterrand berührt, und
    schnitten eine Kerbe statt einer Öffnung.
    """
    from shapely.geometry import MultiPolygon, Polygon

    parts: list[Polygon] = []
    if isinstance(region, Polygon):
        parts = [region]
    elif isinstance(region, MultiPolygon):
        parts = list(region.geoms)
    elif hasattr(region, "geoms"):
        parts = [part for part in region.geoms if isinstance(part, Polygon)]
    bodies = []
    for part in parts:
        if part.is_empty or part.area < pitch * pitch:
            continue
        body = trimesh.creation.extrude_polygon(part, height=top - bottom)
        body.apply_translation((0.0, 0.0, bottom))
        body.apply_transform(back)
        bodies.append(body)
    if not bodies:
        return None
    joined = bodies[0] if len(bodies) == 1 else concatenated(bodies)
    return MeshData.of(joined)


def _drill_vents(
    body: MeshData,
    cavity: MeshData,
    field: tuple[np.ndarray, Vec3, float] | None,
    vents: int,
    vent_diameter: float,
    quality: Quality,
    progress: ProgressFn | None,
    cancelled: CancelToken | None,
) -> tuple[MeshData, tuple[Vec3, ...], list[SolverInfo | None], list[Finding]]:
    """Die Entlüftungen eines geschlossenen Hohlraums — und was dabei zu sagen war.

    Eine Stelle für die Wand innen und die Wand außen: ``field`` ist das
    Raster des **Hohlraums** (innen der eingezogene Körper, außen der Körper
    selbst), ``cavity`` sein Netz. Gebohrt wird von unten durch die Wand bis
    über den höchsten Boden des Hohlraums (:func:`_vent`).
    """
    _step(progress, cancelled, 0.8, _("Entlüftungen bohren"))
    drilled_body, placed, drilled = _vent(
        body, cavity, vent_diameter, vents, quality, progress, cancelled, field=field
    )
    findings: list[Finding] = []
    if not placed:
        findings.append(
            Finding(
                code="hollow.no_vent",
                severity="warning",
                message=_(
                    "Es war keine Stelle für eine Entlüftung zu finden — "
                    "ein geschlossener Hohlraum drückt beim Drucken die Decke hoch."
                ),
                # Regel 17: Wandstärke und Entlüftung stehen im Schritt.
                suggestions=(CORRECT_INPUT,),
            )
        )
    elif len(placed) < vents:
        # Weniger, als verlangt, und das wird gesagt: Der Hohlraum ist
        # offen, aber wer drei Entlüftungen eingetragen hat, soll nicht
        # im Bericht nachzählen müssen, dass es eine wurde.
        findings.append(
            Finding(
                code="hollow.fewer_vents",
                severity="info",
                message=_(
                    "Am Boden des Hohlraums war nur Platz für {placed} von {wanted} "
                    "Entlüftungen. Der Hohlraum ist offen.",
                    placed=len(placed),
                    wanted=vents,
                ),
                values={"placed": len(placed), "wanted": vents},
            )
        )
    return drilled_body, placed, drilled, findings


def _raster_findings(
    wall: float, values: dict[str, float | int | str], *, opened: MeshData | None = None
) -> list[Finding]:
    """Ausgehöhlt — und was das Raster dabei zugesagt hat.

    Eine Stelle für alle drei Netzwege (bisheriger Weg, Wand außen, gewählte
    Öffnungen): ``hollow.done`` mit dem, was die Erosion wirklich abgetragen
    hat, und ``hollow.coarse_grid``, wenn das Raster die Wand nicht treffen
    kann. ``values`` sind die Werte, die nur der jeweilige Weg kennt.

    ``opened`` ist der fertige Körper, wenn der Hohlraum offen sein soll — über
    eine Öffnung oder eine Entlüftung. Dann sagt ``hollow.closed_cavities``,
    wenn Teile des Innenraums trotzdem geschlossen geblieben sind: An einem
    Tischorganizer aus dem Kundenkorpus blieben neben dem geöffneten Fach
    weitere Hohlräume zu, und kein Satz nannte sie (Sonde vom 23.09.2026).
    """
    steps, pitch = erosion_steps(wall)
    findings = [
        Finding(
            code="hollow.done",
            severity="info",
            message=_("Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters."),
            values={
                "wall_mm": round(wall, 2),
                # Was die Erosion wirklich weggenommen hat, und wie weit der
                # Rasterrand daneben liegen kann. Der Sollwert allein war
                # keine Auskunft: Er stand auch dort, wo das Raster ihn gar
                # nicht treffen konnte.
                "eroded_mm": round(steps * pitch, 3),
                "tolerance_mm": round(pitch / 2.0, 3),
                **values,
            },
        )
    ]
    worst = abs(steps * pitch - wall) + pitch / 2.0
    if worst > wall * PITCH_SHARE / 2.0 + EPS_GEOM:
        # Unter ``MIN_PITCH`` kommt das Raster nicht, also verfehlt eine dünne
        # Wand das Versprechen „ein Sechstel" — bei 0,5 mm um das Dreifache.
        # Das gehört gesagt (§2.7), mit dem Handgriff, der es behebt: Der Wert
        # steht im Dialog, und eine dickere Wand ist ein Zahlendreher weit weg.
        findings.append(
            Finding(
                code="hollow.coarse_grid",
                severity="warning",
                message=_(
                    "Für diese Wandstärke ist das Raster zu grob — die stehende Wand "
                    "kann spürbar dicker werden als eingetragen. Eine Wand ab einem "
                    "Millimeter trifft das Raster genau."
                ),
                values={
                    "wall_mm": round(wall, 2),
                    "eroded_mm": round(steps * pitch, 3),
                    "worst_case_mm": round(worst, 3),
                    # Die strukturelle Grenze als Zahl: ab hier trifft das Raster.
                    "fair_wall_mm": round(3.0 * MIN_PITCH, 2),
                },
                # Regel 17: Die Wandstärke, die der Satz nennt, steht im Schritt.
                suggestions=(CORRECT_INPUT,),
            )
        )
    if opened is not None:
        closed = _closed_cavities(opened, pitch)
        if closed:
            findings.append(
                Finding(
                    code="hollow.closed_cavities",
                    severity="warning",
                    message=_(
                        "Nicht jeder Hohlraum ist offen: Teile des Innenraums bleiben "
                        "geschlossen und drücken beim Drucken die Decke hoch. Weitere "
                        "Öffnungen oder Entlüftungen setzen."
                    ),
                    values={
                        "count": len(closed),
                        "closed_cm3": round(sum(closed) / 1000.0, 2),
                    },
                    suggestions=(CORRECT_INPUT,),
                )
            )
    return findings


def _closed_cavities(body: MeshData, pitch: float) -> list[float]:
    """Die Volumina der geschlossenen Hohlräume im fertigen Körper, in mm³.

    Ein geschlossener Hohlraum ist eine Schale des Netzes mit negativem
    Volumen — nach innen gerichtet, ohne Verbindung zur Außenhaut. Kleiner
    als zwei Rasterzellen zählt nicht: Solche Schalen entstehen, wo das
    Raster an einer dünnen Stelle eine Zelle einschließt, und sind kein
    Hohlraum, den jemand ausdrucken würde.
    """
    least = 8.0 * pitch**3
    pieces = body.raw.split(only_watertight=False)
    return [-float(piece.volume) for piece in pieces if float(piece.volume) < -least]


def below_printable_wall(wall: float, profile: Profile | None) -> Finding | None:
    """Ist die Wand dünner, als der Drucker sie legen kann?

    **Beide Zwillinge trugen dafür eine Zahl, und beide waren falsch.** Im
    Schema stand ``minimum=0.4`` am Netz und ``minimum=0.2`` am exakten Kern —
    Zahlenkonstanten für eine Toleranz, also ein Verstoß gegen Regel 7 in
    seiner reinsten Form. Aufgefallen ist es an der Abweichung; der eigentliche
    Fund ist, dass auch die 0,4 nur **zufällig** stimmt, nämlich für eine
    0,4er Düse. Gemessen am Centauri mit 0,42 mm Bahnbreite sind zwei
    Extrusionsbreiten **0,84 mm** — die Schemagrenze ließ dort das Doppelte an
    zu dünner Wand durch, ohne ein Wort.

    Ein Schema-Minimum kann das nicht leisten: Es steht zur Deklarationszeit
    fest, das Profil kommt erst mit dem Auftrag. Also fragt die Operation, und
    zwar die Regel selbst (``Profile.minimum_wall_thickness``, §39) statt einer
    Kopie davon.

    Ein Befund und kein Fehler: Die Geometrie entsteht ja — sie ist nur nicht
    druckbar, und das ist eine Aussage über den Drucker, nicht über den Körper.
    Wer denselben Körper auf einer feineren Düse fährt, hat kein Problem.
    """
    # **Ohne Drucker keine Aussage.** Dieselbe Regel wie bei
    # ``boolean.without_effect`` nebenan („ein Aufrufer, der keinen Drucker
    # kennt, soll keinen erfinden"): Die Grenze *ist* der Drucker, also gibt es
    # sie ohne ihn nicht. Der Fall kommt vor — ein direkter Aufruf der
    # Operation ohne Profil, wie ihn Tests und die Kommandozeile bauen —, und
    # er wäre bis zum 27.08.2026 in einem AttributeError geendet: Die alte
    # Zahlenkonstante brauchte kein Profil, diese Frage schon.
    if profile is None:
        return None
    least = profile.minimum_wall_thickness
    if wall >= least - EPS_GEOM:
        return None
    # Dieselbe Frage, zwei Verfahren: Bei Resin gibt es keine Düse, die eine
    # Bahn legt — die Wand bricht beim Waschen oder reißt von der Folie. Ein
    # eigener Code, damit der Befundkatalog eines Resin-Projekts keine Düse
    # nennt (Resin-Konzept B4).
    if profile.printer.is_resin:
        return Finding(
            code="hollow.wall_below_minimum",
            severity="warning",
            message=_("Die Wand ist dünner, als dieser Drucker sie stehen lässt."),
            values={"wall_mm": round(wall, 2), "least_mm": round(least, 2)},
            # Regel 17: Die Wandstärke steht im Schritt.
            suggestions=(CORRECT_INPUT,),
        )
    return Finding(
        code="hollow.wall_below_nozzle",
        severity="warning",
        message=_("Die Wand ist dünner, als der Drucker sie legen kann."),
        values={"wall_mm": round(wall, 2), "least_mm": round(least, 2)},
        # Regel 17: Die Wandstärke steht im Schritt.
        suggestions=(CORRECT_INPUT,),
    )


#: Wie weit das entfernte Volumen vom Werkzeugvolumen abweichen darf, damit
#: der Hohlraum als ganz im Körper liegend gilt — ein Millionstel, also weit
#: unter jeder Fertigungstoleranz und weit über dem Rundungsrauschen einer
#: exakten Booleschen Rechnung (gemessen an vier Körpern: die Abweichung lag
#: bei 10⁻¹² bis 10⁻⁹ des Werkzeugvolumens).
ENCLOSED_TOLERANCE: Final = 1e-6

#: Die Stufen der Rückfallkette, deren Volumen man trauen darf. Die
#: Voxelstufe rundet auf ihr Raster; dort sagt ein Volumenvergleich nichts.
EXACT_STAGES: Final[frozenset[str]] = frozenset({"direct", "welded", "jittered"})


def _enclosed_cavity(
    mesh: MeshData,
    cavity: MeshData,
    outcome: BooleanOutcome,
    before: float,
    quality: Quality,
    cancelled: CancelToken | None,
) -> BooleanOutcome:
    """Der eingeschlossene Hohlraum — gerechnet nur, wenn er nicht das Werkzeug ist.

    **Der Regelfall ist, dass er es ist.** Das Werkzeug entsteht aus der um
    die Wandstärke geschrumpften Hülle und liegt damit ganz im Körper; der
    Schnitt gibt es dann Dreieck für Dreieck zurück (gemessen am 22.09.2026:
    26 968 Dreiecke hinein, 26 968 heraus). Er kostete trotzdem 1,16 von
    5,7 Sekunden am Baum mit 197 120 Dreiecken, ein Fünftel der Operation.

    Gefragt wird deshalb zuerst das **Volumen**: Hat die Differenz genau so
    viel weggenommen, wie das Werkzeug misst, lag es ganz innen. Das gilt nur
    für die exakten Stufen der Rückfallkette — die Voxelstufe rundet auf ihr
    Raster, und ein Vergleich sagte dort nichts. Wo die Antwort nicht
    eindeutig ist, wird geschnitten wie bisher: ein Hohlraum, der die Wand
    durchbricht, ist kleiner als sein Werkzeug, und genau das muss der
    Prüfbericht sehen.
    """
    strategy = outcome.solver.strategy if outcome.solver is not None else None
    if strategy in EXACT_STAGES and outcome.solver is not None:
        removed = before - outcome.mesh.volume
        volume = cavity.volume
        if volume > EPS_GEOM and abs(removed - volume) <= ENCLOSED_TOLERANCE * volume:
            return BooleanOutcome(mesh=cavity, findings=[], solver=outcome.solver)
    return boolean("intersection", [mesh, cavity], quality=quality, cancelled=cancelled)


def hollowed(wall: float, removed_mm3: float) -> Finding:
    """Ausgehöhlt — und wie viel dabei herausgekommen ist.

    Das Gegenstück zu :func:`too_thin`, und aus demselben Grund geteilt: Beide
    Kerne haben den Fall, und für den Kunden ist es dieselbe Auskunft.

    **Der Erfolgsfall war der letzte, in dem die Zwillinge auseinanderliefen.**
    Nach dem Fix vom 27.08.2026 meldeten beide dieselben Warnungen; gefahren
    mit einer Wandstärke, die *funktioniert*, sagte der Netz-Zwilling
    ``hollow.done`` mit seinen Zahlen und der exakte schwieg. Gerade dort
    zählt die Auskunft am meisten: Wie viel Material weg ist, ist der Grund,
    aus dem man aushöhlt.

    **Weniger Werte als der Netz-Zwilling, und das ist kein Mangel.** Dort
    stehen zusätzlich ``eroded_mm``, ``tolerance_mm`` und ``vents`` — sie
    beschreiben das Raster und die Entlüftungen, und beides hat der exakte
    Kern nicht (Konzept §10.1, die Tabelle des Aushöhlens). Eine Null dafür wäre eine
    Aussage über etwas, das es nicht gibt.
    """
    return Finding(
        code="hollow.done",
        severity="info",
        message=_("Ausgehöhlt."),
        values={"wall_mm": round(wall, 2), "removed_cm3": round(removed_mm3 / 1000.0, 1)},
    )


def too_thin(wall: float) -> Finding:
    """Für diese Wandstärke bleibt kein Hohlraum übrig.

    Geteilt, weil **beide Kerne** denselben Fall haben: Das Netz merkt es am
    leeren Hohlraumnetz, der exakte am unveränderten Volumen — und für den
    Kunden ist es dieselbe Auskunft. Bis zum 27.08.2026 hatte nur das Netz sie;
    ``shell_exact`` gab in keinem einzigen von dreizehn gemessenen
    Wandstärkenfällen einen Befund zurück, obwohl von 15 bis 50 Millimetern
    nur ein einziger Wert überhaupt etwas bewirkt. Zwei wörtliche Kopien des
    Satzes wären zwei Stellen, an denen er auseinanderläuft.
    """
    return Finding(
        code="hollow.too_thin",
        severity="warning",
        message=_("Für diese Wandstärke bleibt kein Hohlraum übrig."),
        values={"wall_mm": round(wall, 2)},
        # Regel 17: Die Wandstärke steht im Schritt.
        suggestions=(CORRECT_INPUT,),
    )


def has_room_inside(mesh: MeshData, wall: float) -> bool:
    """Bleibt nach einer Wand von ``wall`` innen überhaupt ein Hohlraum?

    Die Frage des Rasters, für den exakten Kern gestellt, wenn OpenCASCADE
    keinen Körper liefert: Ist hier kein Platz, war die Wand zu dick; ist
    Platz, schneiden sich an dieser Form die Innenwände (P6.3).
    """
    return _inner_field(mesh, wall) is not None


def _inner_field(mesh: MeshData, wall: float) -> tuple[np.ndarray, Vec3, float] | None:
    """Das Raster des Körpers, eingezogen um die Wandstärke.

    Getrennt von der Vernetzung, weil zwei Dinge daraus entstehen: der
    Hohlraum, der herausgeschnitten wird, und die Öffnung, die ihn nach oben
    freilegt. Zweimal zu rastern wäre derselbe Lauf über dieselben Dreiecke.
    """
    from scipy import ndimage

    from app.core.perceive.maps import solid_field

    steps, pitch = erosion_steps(wall)
    field = solid_field(mesh, pitch)
    inner = ndimage.binary_erosion(field.filled, structure=_ball(steps))
    if not inner.any():
        return None
    return inner, field.origin, pitch


def _ball(steps: int) -> np.ndarray:
    """Das Strukturelement der Erosion: eine Kugel von ``steps`` Zellen Radius.

    **Die Vorgabe von ``binary_erosion`` ist das Kreuz**, und ``steps`` Kreuze
    hintereinander sind eine Kugel der L1-Norm — ein Oktaeder. Senkrecht zu
    einer 45°-Fläche reicht der nur ``steps · pitch / √2`` weit, und genau so
    dünn blieb dort die Wand: Am 40er Würfel, um 45° um Z gedreht, standen bei
    3 mm Vorgabe 2,371 mm — außerhalb der Toleranz, die der Befund nennt,
    während die waagerechte Decke mit 3,5 mm richtig war. Der Fehler wuchs mit
    der Wand und war an keiner achsparallelen Fläche zu sehen; an einer Kugel
    lag er über die ganze Oberfläche (2,60 statt 3,0 mm).
    Eine Kugel als Strukturelement misst in jede Richtung gleich weit.

    Gerechnet in ganzen Zellen und nicht in Millimetern: ``steps`` ist eine
    ganze Zahl, ``offset² ≤ steps²`` damit eine Ganzzahlrechnung ohne
    Rundungsfrage. Ein Radius in Millimetern legte die Zelle, die genau auf ihm
    liegt, auf ein letztes Bit — und die achsparallele Wand hinge an dessen
    Vorzeichen, also an einem Sprung um einen ganzen Rasterschritt.

    Eine euklidische Distanztransformation (``distance_transform_edt``) rechnet
    dasselbe und ist gemessen worden: gleiches Ergebnis, aber an einem
    300³-Raster 1323 MB Spitze gegen 27 MB und 2,5 s gegen 1,0 s. Sie legt
    ihren Abstandswert für jede Zelle ab; hier wird nur die Schwelle gebraucht.
    """
    reach = np.arange(-steps, steps + 1)
    offsets = np.stack(np.meshgrid(reach, reach, reach, indexing="ij"))
    return np.asarray((offsets**2).sum(axis=0) <= steps**2)


def erosion_steps(wall: float) -> tuple[int, float]:
    """Wie oft erodiert wird und mit welcher Rasterweite.

    Eine Zeile Rechnung, und trotzdem eine eigene Funktion: :func:`hollow`
    **meldet** diese zwei Zahlen, und sie müssen dieselben sein, mit denen
    gerechnet wurde. Zweimal hingeschrieben wären sie beim ersten Nachbessern
    an einer Stelle andere.

    Die Weite ist ein Drittel der Wand, aber nie feiner als ``MIN_PITCH``. Die
    strukturelle Grenze ist damit ``3 * MIN_PITCH`` = 0,9 mm: darüber geht die
    Wand in ganzen Schritten auf und stimmt auf ein Sechstel; darunter greift
    ``MIN_PITCH``, und die ±1/6-Zusage hält nicht mehr — 0,8 mm werden drei
    Schritte à 0,3, also 0,9 mm Erosion, und 0,5 mm werden zwei Schritte à 0,3,
    also 0,6 mm (+30 %). Das ist kein Fehler, den man wegrunden kann — ein
    feineres Raster **wäre** genauer und ist ausdrücklich nicht gewollt.

    Der Versuch, es andersherum zu rechnen (erst die Schrittzahl, dann
    ``wall / steps``), ist gemessen worden und war schlechter: Er trifft die
    Wand rechnerisch exakt und macht dafür das Raster gröber, und die
    Unschärfe des Rasterrandes wächst schneller, als die Rundung einbringt —
    an einem 40er Würfel mit 0,5 mm Wand von 30 % auf 50 % Abweichung. Und das
    feinere Raster kostet Speicher: gemessen ``wall / 3`` gegen den Bestand
    +325 MB (3,4-fach) am 40er Würfel, +898 MB (4,2-fach) am 100-mm-Teil,
    +1354 auf 2326 MB an ``dense_1m`` — der Grund für die feste Untergrenze.

    Was bleibt, gehört deshalb in den Befund und nicht in eine Rundung:
    ``steps * pitch`` ist der Betrag, der wirklich abgetragen wird, und
    ``pitch / 2`` die Unschärfe darüber hinaus.
    """
    pitch = max(wall * PITCH_SHARE, MIN_PITCH)
    return max(1, round(wall / pitch)), pitch


def _meshed(matrix: np.ndarray, origin: Vec3, pitch: float, like: MeshData) -> MeshData | None:
    """Ein Rasterkörper als Netz, an seinem Platz."""
    body = trimesh.voxel.ops.matrix_to_marching_cubes(matrix=matrix, pitch=pitch)
    body.apply_translation(np.asarray(origin, dtype=float))
    return like.replacing(body) if len(body.faces) else None


def _mouth(matrix: np.ndarray, direction: Vec3 = (0.0, 0.0, 1.0)) -> np.ndarray | None:
    """Das Raster der Öffnung: der äußerste Querschnitt des Hohlraums in
    ``direction``, in dieser Richtung durchgezogen.

    Der äußerste und nicht die Vereinigung aller — eine Dose soll ihre Decke
    verlieren, nicht ihre Schulter. Wo der Hohlraum nach oben zuläuft, wird die
    Öffnung entsprechend enger; das ist bei einer Kugel wenig sinnvoll und bei
    allem, was wie ein Behälter aussieht, genau richtig.

    Bis an den Rand des Rasters, und der liegt ringsum eine Zelle außerhalb
    des Körpers (``solid_field`` legt ihn dort hin). Damit ragt das Werkzeug
    hinaus, statt eine Fläche mit dem Deckel zu teilen (§39).

    Die Richtung ist eine der sechs Achsrichtungen; welche, entscheidet die
    betragsgrößte Komponente. Gerechnet wird auf einer **Sicht** des Rasters,
    deren letzte Achse die Öffnungsrichtung ist — ``moveaxis`` und das
    Umdrehen kopieren nichts, und die Schreibzugriffe landen im Ergebnis.
    """
    axis = int(np.argmax(np.abs(np.asarray(direction, dtype=float))))
    forward = float(direction[axis]) > 0.0
    seen = np.moveaxis(matrix, axis, -1)
    opening = np.zeros_like(matrix)
    written = np.moveaxis(opening, axis, -1)
    if not forward:
        seen = seen[..., ::-1]
        written = written[..., ::-1]
    levels = np.flatnonzero(seen.any(axis=(0, 1)))
    if not len(levels):
        return None
    top = int(levels[-1])
    written[..., top:] = seen[..., top][..., None]
    return opening if opening.any() else None


def _direction_name(direction: Vec3) -> str:
    """``+z``, ``-y`` — die Achsrichtung als kurzes Wort für den Bericht."""
    axis = int(np.argmax(np.abs(np.asarray(direction, dtype=float))))
    return ("+" if float(direction[axis]) > 0.0 else "-") + "xyz"[axis]


def _step(
    progress: ProgressFn | None, cancelled: CancelToken | None, fraction: float, text: object
) -> None:
    """Ein Schritt weiter — und die Frage, ob es noch gewollt ist (§15.6)."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if progress is not None:
        progress(fraction, str(text))


def _the_hull_or_the_chain(mesh: MeshData, failure: BooleanFailedError) -> NoReturn:
    """Warum eine Boolesche des Aushöhlens riss: die offene Hülle, oder die Kette.

    **Eine offene Hülle ist der Grund, nicht die Kette** (RM-170). An
    ``generated_figure.stl`` — Weg 3, nach dem Import nicht wasserdicht, 18
    offene Kanten — scheiterten alle Stufen, und die Meldung sagte „Auch die
    letzte Rückfallstufe hat kein brauchbares Ergebnis geliefert". Wahr, aber
    ohne den Weg: Nach *Reparieren* geht das Aushöhlen an derselben Figur in
    0,16 s durch (gemessen 14.09.2026). Der Satz nennt die Hülle, und die
    Handlung „Reparieren und erneut versuchen" steht wie bei jedem
    Geometriefehler dabei — auch im Band der Vorschau, wo man die Zahl noch
    ändern kann.

    **An allen drei Booleschen**, nicht nur an den ersten zwei: Die Kette kommt
    an mancher offenen Stelle durch, und dann reißt erst der Deckelschnitt oder
    die Entlüftung — an demselben nicht geschlossenen Körper, mit derselben
    Ursache (Review 14.09.2026). Vorher geprüft wird nicht: Eine Absage vor
    dem Versuch nähme der Kette genau die Fälle, die sie schafft.
    """
    if not mesh.is_watertight:
        raise NotManifoldError(
            detail=_(
                "Der Körper ist nicht geschlossen — ein Hohlraum braucht eine "
                "dichte Hülle. Erst reparieren, dann aushöhlen."
            ),
            open_edges=open_edge_count(mesh),
        ) from failure
    raise failure


def _vent(
    body: MeshData,
    cavity: MeshData,
    diameter: float,
    count: int,
    quality: Quality,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
    *,
    field: tuple[np.ndarray, Vec3, float] | None = None,
) -> tuple[MeshData, tuple[Vec3, ...], list[SolverInfo | None]]:
    """Bohrt vom Hohlraum nach unten durch den Boden.

    Nach unten mit Absicht: eine Entlüftung in der Bodenfläche sitzt auf der
    Druckplatte, wo sie weder zu sehen noch im Weg ist, und die Luft entweicht
    in der Richtung, in der der Druck wächst.

    **Und nur nach unten** — das stand hier von Anfang an und stimmte nicht.
    Der Bohrer war so lang wie der ganze Körper plus vier Millimeter und lag
    mittig darüber: Er kam zwei Millimeter unter dem Boden heraus **und zwei
    über der Decke**. Aus „einer Entlüftung im Boden" wurde ein durchgehendes
    Loch, und eine Dose, die zu bleiben hatte, war oben offen. Jetzt endet er
    im Hohlraum, einen Millimeter über dessen Boden.

    **Und dort, wo der Hohlraum ist** (22.09.2026). Die Stellen lagen auf einer
    Linie durch die Mitte des Hüllquaders des Hohlraums, und die Bohrer endeten
    einen Millimeter über seinem tiefsten Punkt — an einem Ring lag die Mitte
    im Loch, an einem L im freien Winkel, an einer Kugel lag der Boden neben
    der Mitte höher. Der Bohrer traf Luft oder Wand, gezählt wurde er trotzdem,
    und der Hohlraum blieb geschlossen. Die Stellen kommen jetzt aus dem Raster
    des Hohlraums (:func:`_vent_spots`): nur wo der ganze Bohrerquerschnitt
    unter Hohlraum liegt, der Bohrer reicht bis über den höchsten Boden unter
    ihm, und eine Entlüftung zählt erst, wenn sie Material abgetragen hat.
    """
    from app.core.geom.transform import apply, translation

    outside = body.bounds
    stages: list[SolverInfo | None] = []
    if field is not None:
        spots = _vent_spots(field, diameter, count)
    else:
        spots = _spots_on_a_line(cavity, count)

    drilled = body
    placed: list[Vec3] = []
    # Von zwei Millimetern unter dem Boden bis knapp in den Hohlraum hinein.
    bottom = float(outside.minimum[2]) - 2.0
    for index, (x, y, floor) in enumerate(spots, start=1):
        _step(progress, cancelled, 0.8 + 0.15 * index / len(spots), _("Entlüftungen bohren"))
        top = floor + VENT_BREAKTHROUGH
        height = top - bottom
        if height <= EPS_GEOM:
            continue
        # 32 Sektionen standen hier nie im Quelltext — sie waren die Vorgabe
        # von ``trimesh.creation.cylinder``. Jetzt stehen sie da, denn eine
        # Zahl, die das Ergebnis bestimmt, gehört nicht in eine fremde
        # Bibliothek (17.09.2026, RM-187).
        tool = lathe.cylinder(radius=diameter / 2.0, height=height, sections=VENT_SECTIONS)
        tool = apply(MeshData.of(tool), translation((x, y, bottom + height / 2.0)))
        try:
            outcome = boolean("difference", [drilled, tool], quality=quality, cancelled=cancelled)
        except (*PROGRAMMING_ERRORS, *kernel_process.NOT_A_KERNEL_FAILURE):
            raise
        except Exception as problem:  # eine Entlüftung, die nicht geht, ist nicht fatal
            _log.info("vent at %s failed: %s", (x, y), problem)
            continue
        if drilled.volume - outcome.mesh.volume <= EPS_GEOM:
            # Nichts abgetragen heißt: kein Loch — und keine Entlüftung.
            continue
        drilled = outcome.mesh
        placed.append((float(x), float(y), 0.0))
        stages.append(outcome.solver)
    return drilled, tuple(placed), stages


def _vent_spots(
    field: tuple[np.ndarray, Vec3, float], diameter: float, count: int
) -> list[tuple[float, float, float]]:
    """Wo Entlüftungen den Hohlraum sicher treffen: Stelle und Boden darüber.

    Gerechnet am eingezogenen Raster, aus dem der Hohlraum entsteht. Eine
    Stelle taugt, wenn der ganze Bohrerquerschnitt unter Hohlraum liegt
    (die Grundfläche des Hohlraums, um den Bohrerradius eingezogen). Ihr Boden
    ist der **höchste** Boden unter diesem Querschnitt — bis dorthin muss der
    Bohrer reichen, sonst bleibt an einer Seite eine Haut. Genommen werden die
    tiefsten Stellen, und mehrere so weit voneinander wie möglich; weniger,
    als verlangt, wenn der Hohlraum nicht mehr getrennte Stellen hergibt.
    """
    from scipy import ndimage

    inner, origin, pitch = field
    footprint = inner.any(axis=2)
    if not footprint.any():
        return []
    reach = max(1, math.ceil(diameter / 2.0 / pitch))
    offsets = np.arange(-reach, reach + 1)
    disk = (offsets[:, None] ** 2 + offsets[None, :] ** 2) <= reach**2
    usable = ndimage.binary_erosion(footprint, structure=disk)
    if not usable.any():
        return []
    lowest = np.argmax(inner, axis=2)
    highest_floor = ndimage.maximum_filter(
        np.where(footprint, lowest, np.iinfo(np.int64).max // 2), footprint=disk, mode="nearest"
    )
    cells = np.argwhere(usable)
    floors = highest_floor[usable]
    # Der tiefste Boden und alles, was höchstens einen Bohrerdurchmesser
    # darüber liegt — dort ist der Weg durch den Boden am kürzesten, und die
    # Öffnung sitzt unten, wo sie auf der Druckplatte liegt.
    band = floors <= floors.min() + 2 * reach
    cells, floors = cells[band], floors[band]
    middle = cells.mean(axis=0)
    first = int(np.lexsort((np.linalg.norm(cells - middle, axis=1), floors))[0])
    chosen = [first]
    gaps = np.linalg.norm(cells - cells[first], axis=1)
    while len(chosen) < count:
        candidate = int(np.argmax(gaps))
        if gaps[candidate] * pitch < diameter * 2.0:
            break
        chosen.append(candidate)
        gaps = np.minimum(gaps, np.linalg.norm(cells - cells[candidate], axis=1))
    spots = []
    for index in chosen:
        i, j = cells[index]
        # Die Zellmitte liegt auf dem Gitterpunkt; die Hohlraumgrenze liegt
        # eine halbe Zelle unter der ersten gefüllten.
        spots.append(
            (
                float(origin[0] + i * pitch),
                float(origin[1] + j * pitch),
                float(origin[2] + (floors[index] - 0.5) * pitch),
            )
        )
    return spots


def _spots_on_a_line(cavity: MeshData, count: int) -> list[tuple[float, float, float]]:
    """Der alte Weg ohne Raster: entlang X über die Mitte des Hohlraums verteilt."""
    inside = cavity.bounds
    if inside.size[2] <= EPS_GEOM:
        return []
    return [
        (
            float(inside.minimum[0] + inside.size[0] * (2 * index + 1) / (2 * count)),
            float(inside.centre[1]),
            float(inside.minimum[2]),
        )
        for index in range(count)
    ]
