"""Druckvorbereitung: Bohrungen, Teilen, Anordnen, Kollisionen (Bauplan §25,
§18.6).

Drei Regeln aus der Regelsammlung (§39) leben hier, weil sie sonst genau hier
vergessen würden:

* eine Bohrung wird größer gebohrt als nominal, denn FDM druckt Löcher zu
  eng — und der Betrag kommt aus dem kalibrierten Materialprofil, nie aus
  einem Literal (AGENTS.md Regel 7);
* Boolesche Schnitte überlappen immer um einen hundertstel Millimeter, damit
  nie zwei Flächen zusammenfallen;
* was den Bauraum verlässt, wird gemeldet, nicht still skaliert.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CORRECT_INPUT, PROGRAMMING_ERRORS
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    BooleanKind,
    boolean,
    shared_volume,
    without_effect,
)
from app.core.geom.mesh import MeshData, concatenated, on_surface, ray_hit_distances
from app.core.geom.section import SectionPlane, cut
from app.core.geom.transform import Axis, translation
from app.core.knowledge.profiles import resolve_tolerance
from app.core.types import (
    BoundingBox,
    Finding,
    Mesh,
    ObjectId,
    Profile,
    Quality,
    Severity,
    SolverInfo,
    Vec3,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM, format_length, format_volume
from app.i18n import TranslatableText, _

#: Segmente, aus denen ein Bohrzylinder gebaut wird. Fein genug, dass das
#: gedruckte Loch rund ist, grob genug, um die Dreieckszahl nicht zu sprengen.
BORE_SECTIONS = 48

#: Welche Spalte einer Koordinate zu welcher Achse gehört.
AXIS_INDEX: dict[Axis, int] = {"x": 0, "y": 1, "z": 2}

#: Was die Position einer Bohrung bedeutet: ihre Mündung oder ihre Mitte.
BoreAnchor = Literal["mouth", "centre"]


@dataclass(slots=True)
class BoreResult:
    mesh: MeshData
    solver: SolverInfo | None
    diameter: float
    """Der wirklich geschnittene Durchmesser, samt Materialkompensation."""
    findings: list[Finding]


def bore_diameter(nominal: float, profile: Profile, compensate: bool) -> float:
    """Nominal plus was das Material frisst, aus dem Profil (§39, §28.3)."""
    if not compensate:
        return nominal
    return nominal + resolve_tolerance("auto:", "thread", profile)


class HasBounds(Protocol):
    """Was :func:`over_the_edge` von einem Körper braucht — und mehr nicht.

    Dasselbe Muster wie ``HasVolume`` bei ``without_effect``: ``MeshData`` und
    der exakte ``Solid`` haben nichts gemeinsam außer diesem Wert, und für die
    Frage „ragt die Bohrung hinaus" genügt er beiden. Die Prüfung lag deshalb
    nur am Netz-Zwilling — nicht weil der exakte Kern sie nicht könnte,
    sondern weil die Signatur ein ``MeshData`` verlangte.
    """

    @property
    def bounds(self) -> BoundingBox: ...


def over_the_edge(mesh: HasBounds, position: Vec3, axis: Axis, diameter: float) -> list[Finding]:
    """Ragt die Bohrung seitlich über den Körper hinaus?

    „Nichts abgetragen" gibt es seit je (:func:`without_effect`); dies ist der
    Fall dazwischen, und er ist der gefährlichere: es wird etwas abgetragen,
    also schweigt jede Prüfung, und heraus kommt eine Bohrung mit offener
    Flanke. Der Agent hat ihn gebaut — auf „5 mm mittig durch" kam die Ecke,
    weil das Modell mit einem Quader ab dem Ursprung rechnete statt mit einem
    um ihn herum. Abgetragen wurde ein Viertel, und die Antwort lautete
    trotzdem „durchgehend und mittig".

    Gemessen am Hüllquader und nicht an der wirklichen Form: eine Bohrung, die
    innerhalb der Hülle liegt und trotzdem ins Leere geht, trifft entweder
    einen Hohlraum — den kann sie treffen sollen — oder gar nichts, und dann
    greift ``without_effect``.
    """
    direction = [0.0, 0.0, 0.0]
    direction[AXIS_INDEX[axis]] = 1.0
    vector: Vec3 = (direction[0], direction[1], direction[2])
    return over_the_edge_along(mesh, position, vector, diameter)


def over_the_edge_along(
    mesh: HasBounds,
    position: Vec3,
    direction: Vec3,
    diameter: float,
) -> list[Finding]:
    """Die Kantenprüfung für eine freie Bohrungsrichtung.

    Erkannte Bohrungen dürfen schräg liegen. Der seitliche Radius erscheint
    dann in allen drei Koordinaten, jeweils als Projektion der Kreisscheibe.
    Eine Rundung auf die nächste Hauptachse wäre genau die CAD-Arbeit, die der
    Klick auf ein erkanntes Merkmal vermeiden soll.
    """
    vector = np.asarray(direction, dtype=float)
    length = float(np.linalg.norm(vector))
    if length <= EPS_GEOM:
        return []
    unit = vector / length
    radius = diameter / 2.0
    lower, upper = mesh.bounds.minimum, mesh.bounds.maximum
    over: list[str] = []
    for index, name in enumerate("xyz"):
        extent = radius * math.sqrt(max(0.0, 1.0 - float(unit[index]) ** 2))
        if extent <= EPS_GEOM:
            continue
        outside = (
            position[index] - extent < lower[index] - EPS_GEOM
            or position[index] + extent > upper[index] + EPS_GEOM
        )
        if outside:
            over.append(name)
    if not over:
        return []
    return [
        Finding(
            code="bore.over_the_edge",
            severity="warning",
            message=_(
                "Die Bohrung ragt seitlich über den Körper hinaus — sie trägt nur "
                "teilweise ab und lässt eine offene Flanke zurück."
            ),
            values={"axes": ", ".join(over), "diameter": format_length(diameter)},
        )
    ]


def resize_bore(
    mesh: MeshData,
    *,
    position: Vec3,
    direction: Vec3,
    previous_diameter: float,
    diameter: float,
    depth: float,
    through: bool,
    profile: Profile,
    compensate: bool = False,
    quality: Quality = "fine",
    seed: int | None = None,
) -> BoreResult:
    """Ändert eine erkannte zylindrische Bohrung in genau einem Booleschritt.

    Größer heißt: einen weiteren Zylinder abtragen. Kleiner heißt nicht
    „Stopfen und danach neu bohren", sondern einen Ring in die vorhandene
    Bohrung einsetzen. Damit bleiben Mittelpunkt, freie Achse und Tiefe aus
    dem erkannten Merkmal die einzige Geometriequelle; der Kunde trägt nur den
    neuen Durchmesser ein.

    ``compensate`` steht hier absichtlich auf ``False``. Der Ausgangswert im
    Dialog ist ein **gemessenes** Maß und kein Nenndurchmesser. Wer ihn
    unverändert bestätigt, darf nicht allein durch eine noch einmal
    aufgeschlagene Materialtoleranz eine andere Bohrung bekommen.
    """
    cut_diameter = bore_diameter(diameter, profile, compensate)
    if abs(cut_diameter - previous_diameter) <= EPS_GEOM:
        return BoreResult(
            mesh=mesh,
            solver=None,
            diameter=cut_diameter,
            findings=[
                Finding(
                    code="bore.resize_unchanged",
                    severity="info",
                    message=_("Die Bohrung hat bereits diesen Durchmesser."),
                    values={"diameter": format_length(cut_diameter)},
                )
            ],
        )

    vector = np.asarray(direction, dtype=float)
    length = float(np.linalg.norm(vector))
    if length <= EPS_GEOM:
        raise ValueError("a bore direction must not be zero")
    unit = vector / length
    grows = cut_diameter > previous_diameter
    # Nur ein abziehendes Werkzeug darf über beide Mündungen hinausragen.
    # Beim Verkleinern wird der Ring vereinigt; dieselbe Zugabe würde dann an
    # beiden Außenseiten als tastbarer Kragen Teil des Modells werden.
    height = depth + (BOOLEAN_OVERLAP * 2.0 if through and grows else 0.0)
    if height <= EPS_GEOM:
        raise ValueError("a detected bore must have a positive depth")
    to_world = np.asarray(
        trimesh.geometry.align_vectors(np.array([0.0, 0.0, 1.0]), unit),
        dtype=float,
    )
    to_world[:3, 3] = np.asarray(position, dtype=float)
    to_local = np.linalg.inv(to_world)
    local_body = mesh.raw.copy()
    local_body.apply_transform(to_local)
    local_mesh = mesh.replacing(local_body)

    kind: BooleanKind
    if grows:
        tool = trimesh.creation.cylinder(
            radius=cut_diameter / 2.0,
            height=height,
            sections=BORE_SECTIONS,
        )
        kind = "difference"
    else:
        # Der Außenrand greift um dieselbe zentrale Überlappung ins Material,
        # die alle Booleschen Bohrwerkzeuge benutzen. Ohne sie berührte der
        # Ring die alte Bohrungswand nur und die Vereinigung wäre undefiniert.
        tool = trimesh.creation.annulus(
            r_min=cut_diameter / 2.0,
            r_max=previous_diameter / 2.0 + BOOLEAN_OVERLAP,
            height=height,
            sections=BORE_SECTIONS,
        )
        kind = "union"
    # Im Koordinatensystem der Bohrung rechnen. Ein schräger Zylinder ist
    # geometrisch nicht schwieriger als ein senkrechter, numerisch aber schon:
    # an der gedrehten Korpusplatte zerlegte der direkte Mesh-Kern 97 Grad der
    # neuen Wand in Keile und die Erkennung nannte sie danach „Verrundung".
    # Lokal steht die Achse exakt auf Z; zurückgedreht wird erst das fertige
    # Ergebnis. Das ändert keine Maße und bewahrt die freie Richtung.
    outcome = boolean(kind, [local_mesh, MeshData.of(tool)], quality=quality, seed=seed)
    world_body = outcome.mesh.raw.copy()
    world_body.apply_transform(to_world)
    resized = outcome.mesh.replacing(world_body)
    findings = list(outcome.findings)
    nothing = without_effect(mesh, resized, kind, profile)
    if nothing is not None:
        findings.append(nothing)
    unit_vector: Vec3 = (float(unit[0]), float(unit[1]), float(unit[2]))
    findings.extend(over_the_edge_along(mesh, position, unit_vector, cut_diameter))
    if compensate and abs(cut_diameter - diameter) > EPS_GEOM:
        findings.append(
            Finding(
                code="bore.compensated",
                severity="info",
                message=_("Die Bohrung wurde um die Materialtoleranz vergrößert."),
                values={"nominal": format_length(diameter), "cut": format_length(cut_diameter)},
            )
        )
    return BoreResult(
        mesh=resized,
        solver=outcome.solver,
        diameter=cut_diameter,
        findings=findings,
    )


def drill(
    mesh: MeshData,
    *,
    position: Vec3,
    axis: Axis,
    diameter: float,
    depth: float = 0.0,
    anchor: BoreAnchor = "mouth",
    profile: Profile,
    compensate: bool = True,
    quality: Quality = "fine",
    seed: int | None = None,
) -> BoreResult:
    """Schneidet eine zylindrische Bohrung. Tiefe null bohrt ganz durch.

    ``anchor`` sagt, was die Position bedeutet. ``mouth`` ist, was jemand
    meint, der eine Fläche anklickt: dort fängt die Bohrung an und geht von da
    ins Material. ``centre`` legt die Mitte der Bohrung auf die Position —
    das taten alle Bohrungen bis Formatversion 7, und ein Klick auf die
    Oberseite bohrte darum nur halb so tief wie verlangt.

    Für eine durchgehende Bohrung macht es keinen Unterschied: „durch" ist
    „durch", und der Zylinder ist lang genug, um von jeder Position aus in
    beide Richtungen hinauszureichen.
    """
    cut_diameter = bore_diameter(diameter, profile, compensate)
    through = depth <= EPS_GEOM
    height = _through_length(mesh, axis) * 2.0 if through else depth
    cylinder = trimesh.creation.cylinder(
        radius=cut_diameter / 2.0, height=height + BOOLEAN_OVERLAP * 2, sections=BORE_SECTIONS
    )
    cylinder.apply_transform(_axis_alignment(axis))
    offset = np.asarray(position, dtype=float)
    if not through and anchor == "mouth":
        direction = np.zeros(3)
        direction[AXIS_INDEX[axis]] = _into_the_material(mesh, axis, position)
        offset = offset + direction * (height / 2.0)
    cylinder.apply_translation(offset)

    outcome = boolean("difference", [mesh, MeshData.of(cylinder)], quality=quality, seed=seed)
    findings = list(outcome.findings)
    # Eine Bohrung, die den Körper nicht getroffen hat, sagt das (§2.7).
    nothing = without_effect(mesh, outcome.mesh, "difference", profile)
    if nothing is not None:
        findings.append(nothing)
    findings.extend(over_the_edge(mesh, position, axis, cut_diameter))
    if compensate and abs(cut_diameter - diameter) > EPS_GEOM:
        findings.append(
            Finding(
                code="bore.compensated",
                severity="info",
                message=_("Die Bohrung wurde um die Materialtoleranz vergrößert."),
                values={
                    "nominal": format_length(diameter),
                    "cut": format_length(cut_diameter),
                },
            )
        )
    return BoreResult(
        mesh=outcome.mesh, solver=outcome.solver, diameter=cut_diameter, findings=findings
    )


def countersink(
    mesh: MeshData,
    *,
    position: Vec3,
    axis: Axis,
    diameter: float,
    angle: float = 90.0,
    anchor: BoreAnchor = "mouth",
    profile: Profile | None = None,
    quality: Quality = "fine",
) -> BoreResult:
    """Bricht die Mündung einer Bohrung mit einem Kegel, damit ein
    Schraubenkopf bündig sitzt (§25).

    Der Winkel ist der volle Kopfwinkel — 90 Grad bei einer metrischen
    Senkkopfschraube. Geschnitten wird der Kegel, den dieser Kopf beschreibt —
    darum folgt die Tiefe aus dem Durchmesser, statt abgefragt zu werden.

    **Wohin der Kegel enger wird, folgt aus dem Körper und nicht aus der
    Achse.** Bis zum 25.08.2026 stand die Richtung je Achse fest: entlang Z und
    X in die eine, entlang Y in die andere. An drei der sechs Flächen eines
    Quaders lag der Kegel damit außen in der Luft und trug 0,55 statt 76,8 mm³
    ab — ohne einen Befund, denn abgetragen wurde die Überlappung, und die ist
    mehr als nichts. Gefragt wird jetzt, auf welcher Seite von ``position`` das
    Material liegt (:func:`open_sides`).

    ``anchor`` sagt, was die Position bedeutet — dieselben zwei Werte wie beim
    Bohren, weil die Frage dieselbe ist. ``mouth`` heißt: sie darf irgendwo in
    der Bohrung liegen, gesenkt wird an deren Mündung. Das ist der Fall, den
    eine angeklickte Bohrung erzeugt — sie meldet ihre **Mitte**, und ein Kegel
    dort ist ein Hohlraum mitten im Material statt einer Fase am Rand.
    ``centre`` nimmt die Position wörtlich, für den, der sie eintippt.
    """
    depth = diameter / 2.0 / math.tan(math.radians(angle / 2.0))
    at = np.asarray(position, dtype=float)
    sides = open_sides(mesh, axis, tuple(at))
    # Eine Mündung, zwei Mündungen, keine: bei genau einer ist sie gefunden,
    # sonst entscheidet dieselbe Hüllquader-Regel wie beim Bohren.
    outward = sides[0] if len(sides) == 1 else -into_the_body(mesh, axis, tuple(at))
    findings: list[Finding] = []
    if anchor == "mouth" and sides:
        at = _at_the_mouth(mesh, axis, at, diameter, outward)
    if not sides and _inside_the_bounds(mesh, at):
        # Weder vorwärts noch rückwärts kommt der Strahl heraus: hier ist
        # Material, keine Bohrung. Der Kegel schneidet dann einen Hohlraum, den
        # niemand je zu sehen bekommt — genau der Fall, für den ``anchor`` da
        # ist, nur ohne Bohrung, an die man ihn hängen könnte.
        findings.append(
            Finding(
                code="bore.sink_buried",
                severity="warning",
                message=_(
                    "An dieser Stelle liegt Material und keine Bohrungsmündung — die "
                    "Senkung würde ein Hohlraum im Teil. Position auf eine Fläche oder "
                    "in eine Bohrung legen."
                ),
                values={"diameter": format_length(diameter)},
            )
        )

    narrows = np.zeros(3)
    narrows[AXIS_INDEX[axis]] = -outward

    cone = trimesh.creation.cone(radius=diameter / 2.0, height=depth, sections=BORE_SECTIONS)
    # Der Kegel kommt auf seiner Basis stehend heraus, Spitze nach oben. Eine
    # Senkung ist andersherum: am weitesten an der Fläche, enger werdend ins
    # Material. Umgedreht läuft er von null abwärts, was genau das ist — und
    # er wird um die Überlappung angehoben, damit die zwei Flächen nicht
    # zusammenfallen (§39).
    cone.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))
    cone.apply_translation([0.0, 0.0, BOOLEAN_OVERLAP])
    cone.apply_transform(trimesh.geometry.align_vectors(np.array([0.0, 0.0, -1.0]), narrows))
    cone.apply_translation(at)

    outcome = boolean("difference", [mesh, MeshData.of(cone)], quality=quality)
    findings = [*outcome.findings, *findings]
    # Dieselbe Auskunft wie beim Bohren: eine Senkung neben dem Körper sagt es
    # (§2.7). Sie war der eigentliche Schaden an der festen Richtung — der
    # Kegel lag daneben, und niemand erfuhr davon.
    nothing = without_effect(mesh, outcome.mesh, "difference", profile)
    if nothing is not None:
        findings.append(nothing)
    return BoreResult(
        mesh=outcome.mesh,
        solver=outcome.solver,
        diameter=diameter,
        findings=findings,
    )


def open_sides(mesh: MeshData, axis: Axis, position: Vec3) -> tuple[float, ...]:
    """In welche Richtungen entlang der Achse von hier aus kein Material mehr
    kommt — als Vorzeichen, also ``()``, ``(-1,)``, ``(1,)`` oder ``(-1, 1)``.

    Gemessen mit zwei Strahlen entlang der Achse, exakt und ohne Raumindex
    (:func:`app.core.geom.mesh.ray_hit_distances`). Der Unterschied zu
    :func:`into_the_body` ist der Bezug: dort entscheidet die Hälfte des
    Hüllquaders, hier der Körper selbst. Für eine Position **in** einer Bohrung
    ist das der ganze Punkt — die Bohrungsachse trifft kein Dreieck, also sagt
    der Strahl, wo es hinausgeht.

    Die drei Antworten unterscheiden drei Lagen, und sie auseinanderzuhalten
    ist der Zweck: eine offene Seite ist eine Sackbohrung und nennt ihre
    Mündung; zwei offene Seiten sind eine durchgehende Bohrung — oder eine
    Position weit neben dem Körper; keine offene Seite heißt Material
    ringsum. Wer nur nach „einer" Richtung fragt, hält die durchgehende
    Bohrung für vergraben.
    """
    triangles = np.asarray(mesh.raw.triangles, dtype=float)
    if not len(triangles):
        return ()
    origin = np.asarray(position, dtype=float)
    found: list[float] = []
    for sign in (-1.0, 1.0):
        direction = np.zeros(3)
        direction[AXIS_INDEX[axis]] = sign
        hits = ray_hit_distances(triangles, origin, direction)
        # Ein Treffer im Rechenrauschen ist die Fläche, auf der die Position
        # selbst liegt — sonst wäre jede angeklickte Oberseite „zu".
        if not len(hits) or float(np.max(hits)) <= EPS_GEOM:
            found.append(sign)
    return tuple(found)


def _inside_the_bounds(mesh: MeshData, position: np.ndarray) -> bool:
    """Liegt die Position überhaupt im Hüllquader des Körpers?

    Trennt die zwei Fälle, in denen :func:`open_sides` keine **eine** Richtung
    nennt: mitten im Material (beide Richtungen zu) und weit daneben (beide
    offen, weil der Strahl den Körper gar nicht kreuzt). Nur der erste ist eine
    vergrabene Senkung; der zweite trägt nichts ab und wird von
    :func:`without_effect` gemeldet.
    """
    low, high = mesh.bounds.minimum, mesh.bounds.maximum
    return all(
        low[index] - EPS_GEOM <= position[index] <= high[index] + EPS_GEOM for index in range(3)
    )


def _at_the_mouth(
    mesh: MeshData, axis: Axis, position: np.ndarray, diameter: float, outward: float
) -> np.ndarray:
    """Schiebt die Position entlang der Achse bis zur **nächsten**
    Materialgrenze in Richtung ``outward``.

    Gemessen an den Eckpunkten **um die Achse herum**: Eine Bohrung bringt ihre
    Wand mit, und deren äußerster Ring ist die Mündung. Gesucht wird innerhalb
    des Senkungsradius — weit genug für die Wand einer Bohrung, die unter den
    Schraubenkopf passt.

    **Die nächste Grenze, nicht die weiteste.** Bis zum 26.08.2026 wurde der
    weiteste Eckpunkt genommen, und der ist nur dort die Mündung, wo neben der
    Bohrung nichts steht. Gemessen an einer Platte 40 x 40 x 10 mit einem Dom
    Ø 8 x 6 hoch daneben — Mitte bei x = 8, also 1,5 mm Wand zur Bohrung Ø 5 —:
    Der Klick auf die Mündung (0, 0, 10) landete bei (0, 0, 16), der
    Domoberseite. Herausgebissen wurde ein Kubikmillimeter **aus dem Dom**, die
    Bohrung blieb ohne Fase, und einen Befund gab es nicht, denn abgetragen
    wurde ja etwas. Der Docstring versprach hier einmal, „eng genug" zu suchen,
    „um die Nachbarbohrung nicht mitzunehmen" — der Nachbar wurde bevorzugt
    mitgenommen.

    **Beide Hälften der Regel tragen, einzeln keine.** Die Mündung, auf die
    jemand klickt, liegt auf Klickhöhe, und ein striktes „davor" schloss genau
    sie aus: In der Auswahl standen dann *nur* fremde Punkte, und der nächste
    war derselbe wie der weiteste (gemessen: beide Male 16,0). Erst zusammen mit
    „auf gleicher Höhe zählt mit" wird aus der nächsten Grenze die Mündung — wer
    schon auf ihr steht, wird nicht mehr verschoben.

    Findet sich nichts, bleibt die Position, wo sie ist: Wer eine Fläche
    anklickt, hat die Mündung schon getroffen, und eine Position ohne Bohrung
    darunter zu verschieben wäre Raten (Regel 21).

    **Was diese Suche nicht leistet.** Sie sieht Eckpunkte und nicht die
    Bohrwand, weiß also nicht, wem eine Grenze gehört. Liegt fremde Geometrie im
    Senkungsradius **tiefer** als die Mündung — eine Tasche daneben, eine
    Querbohrung durch die Bohrung —, wird deren Grenze die nächste, und der
    Kegel sitzt zu tief. An vierzehn Lagen gemessen trifft die nächste Grenze
    elf, die weiteste acht und die nächste ohne den Gleichstand sechs; sauber
    trennen ließe sich der Rest nur über den Bohrungsradius, und den kennt eine
    Senkung nicht.
    """
    index = AXIS_INDEX[axis]
    points = np.asarray(mesh.raw.vertices, dtype=float)
    if not len(points):
        return position
    offset = points - position
    offset[:, index] = 0.0
    near = np.linalg.norm(offset, axis=1) <= diameter / 2.0
    # Nicht „davor", sondern „nicht dahinter": Material auf Klickhöhe ist die
    # Mündung, auf der die Position bereits steht.
    ahead = near & ((points[:, index] - position[index]) * outward > -EPS_GEOM)
    if not ahead.any():
        return position
    along = points[ahead, index]
    moved = position.copy()
    moved[index] = float(np.min(along) if outward > 0.0 else np.max(along))
    return moved


def plug(
    mesh: MeshData,
    *,
    position: Vec3,
    axis: Axis,
    diameter: float,
    depth: float = 0.0,
    anchor: BoreAnchor = "mouth",
    profile: Profile | None = None,
    compensate: bool = True,
    quality: Quality = "fine",
) -> BoreResult:
    """Füllt eine Bohrung wieder auf (§25, „verschließen").

    Etwas größer als das Loch, das er füllt — ein Stopfen exakt in Bohrungsgröße
    trifft sie in einer zusammenfallenden Fläche, dem einen Ding, das eine
    Boolesche Op zuverlässig bricht (§39, ``boolean_overlap``).

    **„Etwas größer" heißt größer als das *geschnittene* Loch, nicht als das
    genannte.** ``compensate`` bedeutet hier dasselbe wie beim Bohren und steht
    aus demselben Grund per Vorgabe an: :func:`drill` weitet die Bohrung um den
    Wert aus dem Materialprofil (:func:`bore_diameter`, §39, Regel 7), und ein
    Stopfen, der nur das Nennmaß plus die Überlappung kennt, ist damit **enger
    als das Loch, das er zumachen soll**. Gemessen an einem 20er Würfel mit
    einer Bohrung Ø 6 im PETG-Profil: gebohrt 6,20 mm, gefüllt 6,02 mm, übrig
    ein Ringspalt von 1,72 mm² über die ganze Bohrungslänge — 34,45 mm³, die
    niemand meldete. Der Körper war wasserdicht, einteilig und hatte in jedem
    Querschnitt ein Loch.

    Ohne ``profile`` bleibt es beim Nennmaß: Wer keinen Drucker kennt, soll
    keinen erfinden (Regel 7).

    ``anchor`` bedeutet dasselbe wie beim Bohren, und aus demselben Grund: Wer
    eine Mündung anklickt und dort eine Tiefe von 6 mm einträgt, meint sechs
    Millimeter **ins Material**. Auf die Position zentriert füllte der Stopfen
    davon die Hälfte, ragte drei Millimeter aus dem Teil heraus und meldete
    nichts — die Bohrung blieb zur Hälfte offen. Bei einem durchgehenden
    Stopfen macht es keinen Unterschied.
    """
    through = depth <= EPS_GEOM
    # Wie beim Bohren: ein durchgehender Stopfen ist doppelt so lang wie der
    # Körper, damit er von jeder Position aus in beide Richtungen hinausreicht —
    # ``_shell`` schneidet den Überstand ohnehin weg. Zentriert auf die Mündung
    # füllte die einfache Länge nur die Hälfte und ließ die Bohrung offen.
    height = _through_length(mesh, axis) * 2.0 if through else depth
    filled = diameter if profile is None else bore_diameter(diameter, profile, compensate)
    cylinder = trimesh.creation.cylinder(
        radius=filled / 2.0 + BOOLEAN_OVERLAP, height=height, sections=BORE_SECTIONS
    )
    cylinder.apply_transform(_axis_alignment(axis))
    offset = np.asarray(position, dtype=float)
    if not through and anchor == "mouth":
        direction = np.zeros(3)
        direction[AXIS_INDEX[axis]] = _into_the_material(mesh, axis, position)
        offset = offset + direction * (height / 2.0)
    cylinder.apply_translation(offset)

    # Erst verschneiden: der Stopfen darf nicht aus dem Körper herauswachsen,
    # den er füllt.
    inner = boolean("intersection", [mesh.replacing(cylinder), shell(mesh)], quality=quality)
    outcome = boolean("union", [mesh, inner.mesh], quality=quality)
    findings = list(outcome.findings)
    # Dieselbe Auskunft wie beim Bohren, nur andersherum: ein Stopfen an einer
    # Stelle ohne Bohrung ändert nichts, und das stand nirgends. Zurück blieb
    # ein Schritt im Verlauf und ein unveränderter Körper.
    nothing = without_effect(mesh, outcome.mesh, "union", profile)
    if nothing is not None:
        findings.append(nothing)
    return BoreResult(
        mesh=outcome.mesh,
        solver=outcome.solver,
        diameter=filled,
        findings=findings,
    )


def shell(mesh: MeshData) -> MeshData:
    """Der Körper als Volumen zum Beschneiden — die konvexe Hülle ist nah
    genug.

    Ein Stopfen wird auf die Außenseite des Teils zurückgeschnitten, und dafür
    ist die Hülle die richtige Form: sie greift nie in einen Hohlraum hinein,
    ein Stopfen kann also nie einen füllen. Umgekehrt ist sie eine **Obermenge**
    des Körpers: Verschneiden nimmt nur weg, was ganz außerhalb des Teils
    liegt, und kann deshalb keinen echten Hohlraum ungefüllt lassen.

    Öffentlich, seit ``prepare_ops`` denselben Schnitt braucht: Vier Stellen
    dort haben einen Hohlraum gefüllt, ohne ihn zu beschneiden (siehe
    ``_filling``).
    """
    return mesh.replacing(mesh.raw.convex_hull)


def _through_length(mesh: MeshData, axis: Axis) -> float:
    """Lang genug, um den ganzen Körper entlang dieser Achse zu durchqueren."""
    size = mesh.bounds.size
    index = AXIS_INDEX[axis]
    return float(size[index]) + BOOLEAN_OVERLAP * 4


def into_the_body(mesh: MeshData, axis: Axis, position: Vec3) -> float:
    """Wohin es von dieser Position aus ins Material geht: -1 oder +1.

    Ein Werkzeug, das an der Mündung ansetzt, muss wissen, auf welcher Seite
    der Körper liegt. Entschieden wird an der Mitte der **Materialsäule an
    genau dieser Stelle** — von der nächsten Fläche unter der Position bis zur
    nächsten darüber, gemessen mit zwei Strahlen.

    **Nicht am ganzen Hüllquader**, und das ist der Zwilling des Senkungsfixes
    eine Ebene weiter: Diese Auskunft ist der Rückfall, wenn :func:`open_sides`
    nicht genau eine offene Seite nennt (mitten im Material, oder zwei offene
    Seiten). An der Hälfte des Hüllquaders gemessen hob ein hoher Nachbar — ein
    Dom, ein Steg — die Mitte über die angeklickte Fläche, und die feste
    Halbierung zeigte nach oben in die Luft. Die Säule an Ort und Stelle hängt
    nur am Material, das dort wirklich steht.

    Trifft die Achse an dieser Stelle ein Loch — die Mitte einer durchgehenden
    Bohrung —, kommt keiner der beiden Strahlen zurück, und dann bleibt der
    Hüllquader die einzige Auskunft; welche der zwei Mündungen gemeint ist, ist
    dort ohnehin nicht zu entscheiden.
    """
    index = AXIS_INDEX[axis]
    triangles = np.asarray(mesh.raw.triangles, dtype=float)
    origin = np.asarray(position, dtype=float)
    up = np.zeros(3)
    up[index] = 1.0
    above = ray_hit_distances(triangles, origin, up)
    below = ray_hit_distances(triangles, origin, -up)
    if len(above) and len(below):
        local_high = float(position[index]) + float(np.min(above))
        local_low = float(position[index]) - float(np.min(below))
        return -1.0 if position[index] >= (local_low + local_high) / 2.0 else 1.0
    low = float(mesh.bounds.minimum[index])
    high = float(mesh.bounds.maximum[index])
    return -1.0 if position[index] >= (low + high) / 2.0 else 1.0


def _into_the_material(mesh: MeshData, axis: Axis, position: Vec3) -> float:
    """Wohin es von der Mündung aus ins Material geht — am Körper gemessen, nicht
    am Hüllquader.

    Derselbe Griff wie bei der Senkung (:func:`countersink`, seit dem
    25.08.2026): Bei genau einer offenen Seite (:func:`open_sides`) ist die
    Bohrungsmündung gefunden, und ins Material geht es ihr entgegen. Sonst —
    mitten im Material oder weit neben dem Körper — bleibt die Hüllquader-Hälfte
    (:func:`into_the_body`) die einzige Auskunft.

    Der Unterschied trägt an einem gestuften Teil: Wer die Oberseite einer Stufe
    anklickt, die unter der Mitte des Hüllquaders liegt, meint das Material
    darunter — die Hüllquader-Hälfte allein zeigte dort nach oben, in die Luft,
    und Bohrung wie Stopfen setzten daneben an.
    """
    sides = open_sides(mesh, axis, position)
    if len(sides) == 1:
        return -sides[0]
    return into_the_body(mesh, axis, position)


def _axis_alignment(axis: Axis) -> np.ndarray:
    """Zylinder werden entlang Z gebaut; auf die gewünschte Achse drehen."""
    if axis == "z":
        return np.eye(4)
    angle = math.radians(90.0)
    direction = (0.0, 1.0, 0.0) if axis == "x" else (1.0, 0.0, 0.0)
    return np.asarray(trimesh.transformations.rotation_matrix(angle, direction), dtype=float)


def split_at_plane(mesh: MeshData, plane: SectionPlane) -> tuple[MeshData, MeshData, list[Finding]]:
    """Schneidet einen Körper in zwei, beide Hälften geschlossen (§18.2, §25)."""
    first = cut(mesh, plane)
    second = cut(mesh, plane.flipped())
    findings: list[Finding] = []
    if not (first.capped and second.capped):
        findings.append(
            Finding(
                code="split.uncapped",
                severity="warning",
                message=_("Die Schnittflächen konnten nicht geschlossen werden."),
            )
        )
    return first.mesh, second.mesh, findings


#: Über wie viele Druckplatten eine Szene verteilt werden darf. Keine
#: technische Grenze — jenseits davon will, wer druckt, ein zweites Projekt
#: statt einer Liste, die niemand mehr überblickt.
MAX_PLATES = 12


def compensate_elephant_foot(
    mesh: MeshData,
    profile: Profile,
    height: float = 0.6,
    amount: float | None = None,
    *,
    quality: Quality = "fine",
) -> tuple[MeshData, list[Finding], SolverInfo | None]:
    """Zieht die ersten Schichten um das ein, was die erste Schicht
    auseinanderläuft (§25, §28.3).

    Der Wert kommt aus dem Materialprofil, nie aus einer Schätzung (Regel 7):
    eine Kalibrierung misst ihn, und ein Teil von vor dieser Kalibrierung
    bekommt ihn, sobald sich das Profil ändert.

    Eine gerade Stufe, keine Schräge — genau das tut auch die
    „Elefantenfuß-Kompensation" eines Slicers. Eine Schräge bräuchte einen
    Loft, und der Mesh-Kern hat keinen; der B-Rep-Kern könnte es exakt (§30)
    und muss nicht, denn das gedruckte Ergebnis ist dasselbe.
    """
    from shapely.geometry import Polygon as ShapelyPolygon

    from app.core.slice.analysis import cross_section

    value = profile.material.elephant_foot if amount is None else amount
    if value <= EPS_GEOM:
        return mesh, [], None

    bottom = float(mesh.bounds.minimum[2])
    section = cross_section(mesh, bottom + height / 2.0)
    if section is None or section.is_empty:
        return mesh, [], None

    pulled = section.buffer(-value)
    if pulled.is_empty:
        return (
            mesh,
            [
                Finding(
                    code="prepare.foot_too_small",
                    severity="warning",
                    message=_("Die Aufstandsfläche ist zu klein, um sie noch einzuziehen."),
                    values={"amount_mm": round(value, 3)},
                )
            ],
            None,
        )

    # Was weg muss: der Ring zwischen dem echten Umriss und dem eingezogenen,
    # über die Höhe der ersten Schichten.
    ring = section.difference(pulled)
    if ring.is_empty:
        return mesh, [], None
    parts = [
        trimesh.creation.extrude_polygon(entry, height=height + BOOLEAN_OVERLAP)
        for entry in getattr(ring, "geoms", [ring])
        if isinstance(entry, ShapelyPolygon) and entry.area > EPS_GEOM
    ]
    if not parts:
        return mesh, [], None

    collar = concatenated(parts)
    collar.apply_translation([0.0, 0.0, bottom - BOOLEAN_OVERLAP / 2.0])
    outcome = boolean("difference", [mesh, mesh.replacing(collar)], quality=quality)
    findings = list(outcome.findings)
    findings.append(
        Finding(
            code="prepare.elephant_foot",
            severity="info",
            message=_("Die ersten Schichten wurden um den Elefantenfuß eingezogen."),
            values={"amount_mm": round(value, 3), "height_mm": round(height, 2)},
        )
    )
    return outcome.mesh, findings, outcome.solver


@dataclass(frozen=True, slots=True)
class Arrangement:
    """Wo die Körper gelandet sind, und auf welcher Platte."""

    meshes: list[MeshData]
    plates: list[int]
    findings: list[Finding] = field(default_factory=list)

    @property
    def plate_count(self) -> int:
        return max(self.plates, default=0) + 1 if self.plates else 0


#: Wie nah zwei Rechtecke sich kommen dürfen, bevor Rundung die Antwort
#: entscheidet. Die Kandidatenpunkte entstehen aus derselben Rechnung, die sie
#: prüft — ohne diese Schwelle verwirft ein letztes Bit den Platz, den es
#: gerade selbst ausgerechnet hat.
_TOUCH = 1e-9


@dataclass(frozen=True, slots=True)
class _Slot:
    """Ein belegtes Rechteck in der Aufsicht.

    ``back`` ist die **hintere** Kante, also das größere y: Die Vorderansicht
    des Viewports blickt aus ``-y`` (``app.ui.viewport.VIEWS``), und §29 packt
    von hinten nach vorne.
    """

    left: float
    back: float
    width: float
    depth: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def front(self) -> float:
        return self.back - self.depth


def _apart(one: _Slot, other: _Slot, spacing: float) -> bool:
    """Halten diese beiden den Abstand — in irgendeiner Richtung?

    Es genügt eine: Zwei Teile nebeneinander brauchen den Abstand zwischen
    ihren Seiten, nicht zusätzlich zwischen ihren Tiefen.
    """
    return (
        one.right + spacing <= other.left + _TOUCH
        or other.right + spacing <= one.left + _TOUCH
        or other.back + spacing <= one.front + _TOUCH
        or one.back + spacing <= other.front + _TOUCH
    )


def _candidates(
    taken: list[_Slot], first: tuple[float, float], spacing: float
) -> list[tuple[float, float]]:
    """Die Stellen, an denen ein Körper anliegen kann, hinterste zuerst.

    Kandidaten sind die leere Ecke und je belegtem Rechteck zwei: rechts
    daneben bei gleicher Hinterkante, und davor bei gleicher linker Kante. Mehr
    braucht es nicht — eine dicht gepackte Lage liegt an einem Nachbarn oder am
    Rand an, und diese Liste hält jede solche Ecke.
    """
    points = {first}
    for slot in taken:
        points.add((slot.right + spacing, slot.back))
        points.add((slot.left, slot.front - spacing))
    return sorted(points, key=lambda point: (-point[1], point[0]))


def _beyond_the_edge(
    taken: list[_Slot], size: Vec3, first: tuple[float, float], spacing: float
) -> _Slot:
    """Wohin mit einem Körper, für den weder Platz noch Platte übrig ist.

    Überlappungsfrei bleibt es trotzdem: gesucht wird dieselbe hinterste, dann
    linkeste Stelle, nur ohne die Randbedingung. Was hinausragt, meldet
    :func:`check_build_volume` — mit der Zahl, um die es hinausragt.
    """
    for corner_x, corner_y in _candidates(taken, first, spacing):
        spot = _Slot(corner_x, corner_y, size[0], size[1])
        if all(_apart(spot, other, spacing) for other in taken):
            return spot
    return _Slot(first[0], first[1], size[0], size[1])


def arrange_on_bed(
    meshes: list[MeshData],
    profile: Profile,
    spacing: float = 5.0,
    plates: int = 1,
    object_ids: Sequence[ObjectId] | None = None,
) -> Arrangement:
    """Legt jeden Körper an die hinterste, dann linkeste freie Stelle (§29).

    Bewusst vorhersagbar: Die Regel steht in einem Satz, sie braucht keinen
    Startwert und kein Gewicht, und wer die Reihenfolge der Körper kennt, kann
    das Ergebnis nachvollziehen. Zweimal dasselbe gerechnet kommt zweimal
    dasselbe heraus (§15.1).

    **Warum nicht in Zeilen.** Bis zum 22.08.2026 lief es zeilenweise, und das
    verschenkte über jedem flachen Teil einen Streifen von der Tiefe des
    tiefsten Teils derselben Zeile — 52 Teile brauchten sieben Platten. Eine
    andere Sortierung verschiebt diesen Streifen nur; gemessen wurde es, und
    nach Tiefe sortiert wurde es nicht besser. Der Fehler saß in der Struktur
    und nicht in der Reihenfolge (Bauplan §29). Gemessen an 52 gemischten
    Teilen auf einem 256er Bett: fünf Platten zeilenweise, **drei** ohne Zeilen.

    ``spacing`` ist der Abstand zwischen zwei Körpern, **nicht** zwischen ihren
    Plattenhaftungen. Ein Brim von 5 mm steht auf beiden Seiten über, also
    braucht es dort 10 mm, wo hier 5 stehen. Die Anordnung kann das nicht von
    allein wissen: sie ist eine Operation und damit Teil des Dokuments,
    während die Haftung eine Druckeinstellung ist und zum Slicer reist (§15.5).
    Wer beides zusammenbringt, ist die Oberfläche — und wenn es nicht reicht,
    sagt es :func:`app.core.export.writer.check_adhesion_clearance` mit der
    Zahl, die gebraucht würde.

    Was nicht passt, kommt auf die nächste Platte — bis zu ``plates`` davon.
    Mehr Teile als Platten sind kein Fehler zum Verstecken: die letzte Platte
    nimmt den Rest, und der Bericht sagt, dass sie übervoll ist — denn ein
    Teil, das still aus einer Anordnung fällt, ist ein Teil, das nie gedruckt
    wird.

    Der Aufwand wächst mit dem Quadrat der Teilezahl; für die Größenordnung, um
    die es geht — Dutzende Körper auf einer Platte — bleibt das weit unter dem
    Budget für eine Anordnung (§31).
    """
    width, depth, _height = profile.printer.build_volume
    arranged: list[MeshData] = []
    assigned: list[int] = []
    findings: list[Finding] = []

    left_edge = -width / 2.0 + spacing
    back_edge = depth / 2.0 - spacing
    right_edge = width / 2.0 - spacing
    front_edge = -depth / 2.0 + spacing
    corner = (left_edge, back_edge)

    plate = 0
    taken: list[_Slot] = []

    def place(size: Vec3) -> _Slot | None:
        """Die hinterste, dann linkeste Stelle, an die dieser Körper passt."""
        for corner_x, corner_y in _candidates(taken, corner, spacing):
            spot = _Slot(corner_x, corner_y, size[0], size[1])
            fits = (
                spot.left >= left_edge - _TOUCH
                and spot.right <= right_edge + _TOUCH
                and spot.back <= back_edge + _TOUCH
                and spot.front >= front_edge - _TOUCH
            )
            if fits and all(_apart(spot, other, spacing) for other in taken):
                return spot
        return None

    for mesh in meshes:
        size = mesh.bounds.size
        spot = place(size)
        # **Nur weiterblättern, wenn auf dieser Platte schon etwas liegt.**
        #
        # Ein Körper, der tiefer ist als das Bett, passt auch auf eine leere
        # Platte nicht — und wanderte dann auf die nächste, die genauso wenig
        # hilft. Gemessen an zwei Sockeln von 231 mm Tiefe auf einem 220er Bett
        # und zwei Platten: beide landeten auf Platte 2, aufeinandergestapelt
        # und über den Rand hinaus, während Platte 1 leer blieb. Bei drei
        # Platten blieb sie es auch. Wo nichts liegt, ist die nächste Platte
        # kein besserer Ort — der Befund aus :func:`check_build_volume` sagt
        # stattdessen, was wirklich hilft: teilen, verkleinern, anderes Profil.
        if spot is None and taken and plate + 1 < plates:
            plate += 1
            taken = []
            spot = place(size)
        if spot is None:
            spot = _beyond_the_edge(taken, size, corner, spacing)

        target = (
            spot.left + size[0] / 2.0,
            spot.back - size[1] / 2.0,
            mesh.bounds.size[2] / 2.0,
        )
        offset = tuple(target[index] - mesh.bounds.centre[index] for index in range(3))
        body = mesh.raw.copy()
        body.apply_transform(translation((offset[0], offset[1], offset[2])))
        arranged.append(mesh.replacing(body))
        assigned.append(plate)
        taken.append(spot)

    findings.extend(check_build_volume(arranged, profile, assigned, object_ids))
    if plate + 1 >= plates and _overfull(arranged, assigned, profile, spacing):
        findings.append(
            Finding(
                code="arrange.needs_more_plates",
                severity="warning",
                message=_("Auf so viele Platten passt das nicht — eine mehr würde helfen."),
                values={"plates": plates},
                # **Der Rat stand da, der Weg dorthin nicht.** Im Prüfbericht
                # hatte dieser Befund keinen Knopf: `panels.actions_for` liest
                # zuerst `suggestions`, dann seine Tabelle, dann eine Regel für
                # Codes mit dem Präfix ``op.`` — und dieser Code hat keines.
                # Der Kunde las, was hülfe, und konnte es nicht anklicken
                # (Regel 17 im Bericht statt im Dialog, Fund 3d-druck-81).
                #
                # *Eingabe korrigieren* und kein eigener Knopf „eine Platte
                # mehr": Er öffnet den Schritt, und dort **steht** die Zahl.
                # Ein Knopf, der sie still erhöht, nähme dem Kunden die
                # Entscheidung ab und ließe ihn im Unklaren, wo sie liegt —
                # zumal die Vorgabe seit `9e35bc28` schon jede erlaubte Platte
                # nutzt und dieser Befund nur noch kommt, wenn auch zwölf nicht
                # reichen. Dass die Kennung des Schritts am Befund hängt und
                # der Knopf damit greift, ist gemessen: ``op_id`` wird in
                # ``evaluate`` nachgetragen.
                suggestions=(CORRECT_INPUT,),
            )
        )
    return Arrangement(meshes=arranged, plates=assigned, findings=findings)


def _overfull(meshes: list[MeshData], plates: list[int], profile: Profile, spacing: float) -> bool:
    """Steht auf der letzten Platte etwas über sie hinaus — und **läge es auf
    einer eigenen Platte anders?**

    Der Rat „eine Platte mehr würde helfen" hilft nur, wenn das Gedränge das
    Problem ist. Liegt auf der letzten Platte ein einziger Körper und passt
    trotzdem nicht, dann passt er auf keine: gemessen an einem Sockel von
    231 mm Tiefe auf einem 220er Bett, der bei einer, zwei und drei Platten
    denselben falschen Vorschlag bekam. Ein Vorschlag, der nichts löst, ist
    schlimmer als keiner (Regel 17) — hier sagt stattdessen
    :func:`check_build_volume`, was wirklich hilft.
    """
    last = max(plates, default=0)
    on_last = [mesh for mesh, plate in zip(meshes, plates, strict=True) if plate == last]
    if sum(_fits_alone(mesh, profile, spacing) for mesh in on_last) < 2:
        return False
    return bool(check_build_volume(on_last, profile))


def _fits_alone(mesh: MeshData, profile: Profile, spacing: float) -> bool:
    """Passt dieser Körper auf ein leeres Bett — an seinen Maßen gemessen?

    Nicht an seinem Ort: wo er gerade liegt, entscheidet die Anordnung, und die
    ist genau die Frage. Was hier zählt, ist, ob eine eigene Platte ihm
    überhaupt etwas nützen könnte.

    **Mit dem Abstand, mit dem angeordnet wird.** Ohne ihn hieße „passt allein"
    etwas anderes als „würde allein passend gelegt": ein Teil in genau
    Bettgröße passt roh und ragt nach dem Anordnen dennoch über den Rand — der
    Rat wäre dann wieder einer, der nichts löst. In Z gibt es keinen Abstand;
    dort steht der Körper auf der Platte.
    """
    size = mesh.bounds.size
    room = tuple(profile.printer.build_volume)
    needed = (size[0] + 2.0 * spacing, size[1] + 2.0 * spacing, size[2])
    return all(needed[index] <= room[index] + EPS_GEOM for index in range(3))


def check_build_volume(
    meshes: Sequence[Mesh],
    profile: Profile,
    plates: list[int] | None = None,
    object_ids: Sequence[ObjectId] | None = None,
    *,
    about_to_write: bool = False,
) -> list[Finding]:
    """Was über den Bauraum hinaussteht, wird gemeldet, nie still skaliert.

    ``about_to_write`` sagt, dass gleich eine Datei entsteht — dann wiegt eine
    falsche Lage so schwer wie eine falsche Größe, siehe :func:`_severity_for`.
    Vorgabe ist ``False``: Der Editor fragt dieselbe Frage in einem
    Zusammenhang, in dem ein Klick sie beantwortet.

    ``object_ids`` trägt den Befund an seinen Körper. Ohne sie stand dort nur
    der laufende Index, und ein Bericht, der nicht sagt, **welches** Teil zu
    groß ist, kann auch nichts dagegen anbieten: Die drei Handlungen zum
    Bauraum (teilen, verkleinern, anderes Profil) hingen an einer Ausnahme,
    die niemand warf.

    Geprüft je Platte: zwei Objekte an derselben Stelle auf verschiedenen
    Platten sind kein Problem, und eine volle Platte neben einer leeren auch
    nicht.

    Gefragt wird nur nach dem Hüllquader, also steht hier das Protokoll und
    nicht ``MeshData``: ein exakter Körper aus dem B-Rep-Kern hat einen
    Bauraum wie jeder andere, und eine zu enge Annotation hätte ihn
    stillschweigend übersprungen.
    """
    width, depth, height = profile.printer.build_volume
    allowed = BoundingBox((-width / 2.0, -depth / 2.0, 0.0), (width / 2.0, depth / 2.0, height))
    findings: list[Finding] = []

    for index, mesh in enumerate(meshes):
        bounds = mesh.bounds
        over = [
            max(limit_low - low, high - limit_high, 0.0)
            for low, high, limit_low, limit_high in zip(
                bounds.minimum, bounds.maximum, allowed.minimum, allowed.maximum, strict=True
            )
        ]
        outside = [axis for axis, excess in enumerate(over) if excess > EPS_GEOM]
        # Die Kennung des Körpers, wenn der Aufrufer eine mitgibt — dann löst
        # der Bericht sie zum Namen auf. Der laufende Index steht nur noch als
        # Notnagel da, wo es keine gibt: Er ist kein Kundentext, und er
        # **verhinderte** obendrein die Namensauflösung — die Berichtszeile
        # setzt den Objektnamen nur ein, wenn ``values`` kein ``object`` trägt
        # (Roberts Foto vom 30.08.2026: „— 0 · 10,00 mm" statt „cube_clean").
        object_id = (
            object_ids[index] if object_ids is not None and index < len(object_ids) else None
        )
        if outside:
            values: dict[str, Any] = {
                "axes": ", ".join("xyz"[axis] for axis in outside),
                # Wie weit — sonst steht dort eine Warnung, die zwischen einem
                # Zehntel Millimeter und einem halben Modell nicht unterscheidet.
                "excess": format_length(max(over)),
            }
            if object_id is None:
                values["object"] = index
            if plates is not None and index < len(plates):
                values["plate"] = plates[index] + 1
            code, message = _verdict_for(bounds, allowed, outside, profile.printer.extrusion_width)
            findings.append(
                Finding(
                    code=code,
                    severity=_severity_for(bounds, allowed, about_to_write),
                    message=message,
                    object_id=object_id,
                    values=values,
                )
            )
        elif _floats(bounds, index, meshes, plates):
            floating: dict[str, Any] = {"gap": format_length(float(bounds.minimum[2]))}
            if object_id is None:
                floating["object"] = index
            findings.append(
                Finding(
                    code="arrange.above_bed",
                    severity="info",
                    message=_("Ein Objekt schwebt über dem Druckbett."),
                    object_id=object_id,
                    values=floating,
                )
            )
    return findings


def _floats(
    bounds: BoundingBox,
    index: int,
    meshes: Sequence[Mesh],
    plates: list[int] | None,
) -> bool:
    """Hängt dieser Körper in der Luft — ohne etwas unter sich?

    Das Gegenstück zu ``arrange.below_bed``, und es fehlte: Ein Körper, der
    **unter** der Platte steckt, wurde seit je gemeldet; einer, der darüber
    schwebt, gar nicht, solange er in den Bauraum passte. Gemessen am 24.08.2026
    an zwei Millimetern und an hundertvierzig: in beiden Fällen kein Befund,
    kein Knopf, kein Wort. Robert hatte genau den Fall („einmal als es in der
    Luft war") und musste den Weg im Menü selbst suchen.

    **Wer etwas unter sich hat, schwebt nicht.** Ein Deckel auf einer Dose, ein
    Teil auf einer Grundplatte, jede Baugruppe aus einer 3MF: Dort ist die Lücke
    zum Bett gewollt, und eine Meldung wäre falsch. Gefragt wird nach dem
    Hüllquader und nicht nach der Geometrie — die genaue Frage („liegt er
    wirklich auf?") beantwortet die Schichtanalyse mit ihrer Inselerkennung, und
    die kostet Sekunden (§31). Hier genügt die billige Richtung: Wer in x und y
    mit niemandem überlappt, dessen Oberkante bis zu seiner Unterkante reicht,
    hat nichts unter sich.

    Nur auf derselben Platte: Zwei Platten liegen in der Szene an derselben
    Stelle, weil jede einzeln gedruckt wird (§25) — ein Körper auf Platte 2
    trägt keinen auf Platte 1.

    Die Grenze ist ``EPS_DISPLAY`` und keine Materialtoleranz (Regel 7): Die
    Frage ist nicht, wie fest etwas aufliegt, sondern ob ein Spalt **da** ist.
    Ein Hundertstelmillimeter ist im Fenster dasselbe Bild und rechnerisch
    Rundung; darüber hängt der Körper.
    """
    gap = float(bounds.minimum[2])
    if gap <= EPS_DISPLAY:
        return False
    plate = plates[index] if plates is not None and index < len(plates) else 0
    for other, mesh in enumerate(meshes):
        if other == index:
            continue
        if plates is not None and other < len(plates) and plates[other] != plate:
            continue
        below = mesh.bounds
        if below.maximum[2] < gap - EPS_DISPLAY:
            continue
        overlaps = all(
            below.minimum[axis] < bounds.maximum[axis] - EPS_DISPLAY
            and below.maximum[axis] > bounds.minimum[axis] + EPS_DISPLAY
            for axis in (0, 1)
        )
        if overlaps:
            return False
    return True


def _severity_for(
    bounds: BoundingBox, allowed: BoundingBox, about_to_write: bool = False
) -> Severity:
    """Wiegt die Platzierungsfrage leichter als die Größenfrage — **außer, wenn
    die Datei gleich entsteht.**

    Beides stand einmal als Warnung da, und dadurch warnte fast jede geladene
    Datei: ein heruntergeladenes Teil ist meist um den Ursprung zentriert und
    steckt damit zur Hälfte unter der Platte. Dreizehn Warnungen bei vierzehn
    Dateien sind keine Warnung mehr, sondern Grundrauschen — und die eine
    Datei, die wirklich zu groß ist, geht darin unter.

    Die Trennlinie ist, ob das Teil nach dem Aufsetzen hineinpasst. Wenn ja,
    ist es eine Frage der Lage: ein Klick behebt sie, und das ist ein Hinweis.
    Wenn nein, hilft kein Verschieben, und die Warnung bleibt.

    **Beim Schreiben kippt diese Rechnung**, denn ihre Voraussetzung fällt weg:
    „ein Klick behebt sie" gilt, solange noch geklickt werden kann. Entsteht die
    Datei jetzt, ist der Klick nicht passiert. Gemessen an einer Platte in
    Bettkoordinaten, wie sie aus einer fremden 3MF kommt: PrusaSlicer weigert
    sich („All objects are outside of the print volume"), die Orca-Familie
    ordnet still neu an, und **CuraEngine schreibt eine Druckdatei, die neben
    der Platte druckt** — es prüft den Bauraum nicht. Solidon hatte den Befund,
    und er stand als Hinweis zwischen zwei Dutzend anderen.

    Gesperrt wird trotzdem nichts: §29 sagt „ein Bericht, keine Sperre". Wer
    trotzdem drucken will, kann das — er weiß dann nur, was er tut.
    """
    fits = all(
        size <= limit + EPS_GEOM for size, limit in zip(bounds.size, allowed.size, strict=True)
    )
    return "info" if fits and not about_to_write else "warning"


def _verdict_for(
    bounds: BoundingBox, allowed: BoundingBox, outside: Sequence[int], margin: float = 0.0
) -> tuple[str, TranslatableText]:
    """Kennung und Satz zu dem Fall, der tatsächlich vorliegt.

    „Steht über den Bauraum hinaus" liest sich als „zu groß", und beim
    häufigsten Fall von Weg 1 ist das falsch: ein heruntergeladenes Teil ist
    meist um den Ursprung zentriert, liegt also zur Hälfte unter der
    Druckplatte. Wer den Satz wörtlich nimmt, sucht das Skalieren, obwohl ein
    Aufsetzen genügt — ein Achtelmillimeter Text, der jemanden auf die falsche
    Fährte schickt.

    **Die Kennung unterscheidet jetzt mit.** Sie tat es nicht, und damit ging
    der Unterschied genau dort verloren, wo er gebraucht wird: Der Prüfbericht
    hängt seine anklickbaren Handlungen an ``Finding.code`` (§2.7), also bot er
    dem Teil unter der Platte *Modell teilen* und *Auf den Bauraum
    verkleinern* an — die beiden Antworten, vor denen der Absatz hier warnt.
    Was hilft, ist ein Klick auf *Auf das Bett setzen*; und dass ein Klick
    genügt, ist der Grund, aus dem dieser Fall überhaupt nur ein Hinweis ist
    (:func:`_severity_for`).
    """
    only_below = all(
        allowed.minimum[axis] - bounds.minimum[axis] > bounds.maximum[axis] - allowed.maximum[axis]
        for axis in outside
    )
    if not _fits_at_all(bounds, allowed, margin):
        return "arrange.out_of_build_volume", _("Ein Objekt steht über den Bauraum hinaus.")
    if tuple(outside) == (2,) and only_below:
        return "arrange.below_bed", _("Ein Objekt steckt unter dem Druckbett.")
    if tuple(outside) == (2,):
        # Nur nach oben hinaus, und das heißt: es schwebt, und zwar so hoch,
        # dass es oben herausragt. „Liegt außerhalb des Druckbetts" war hier
        # doppelt irre — in x und y liegt es genau richtig, und angeboten wurde
        # *Auf dem Bett anordnen*, das beides verschiebt, wo ein Absenken
        # genügt. Dieselbe Unterscheidung wie eine Zeile darüber, nur in die
        # andere Richtung.
        return "arrange.above_bed", _("Ein Objekt schwebt über dem Druckbett.")
    return "arrange.off_the_plate", _("Ein Objekt liegt außerhalb des Druckbetts.")


def _fits_at_all(bounds: BoundingBox, allowed: BoundingBox, margin: float) -> bool:
    """Passt der Körper in den Bauraum — gleich, wo er gerade liegt?

    Das ist die Frage, an der die drei Fälle auseinandergehen, und
    :func:`_severity_for` stellt sie seit je. :func:`_verdict_for` tat es
    nicht: Es fragte, über **welche Seite** ein Körper hinaussteht, und nannte
    alles „über den Bauraum hinaus", was nicht nach unten hing.

    **Damit traf es den häufigsten Fall von Weg 1 falsch.** Eine 3MF aus
    Bambu Studio, Orca oder Elegoo führt Bettkoordinaten: Gemessen an einer
    heruntergeladenen Ente liegen die drei Körper bei x 83 bis 216, y 43 bis
    113 — auf einem 256er Bett um den Ursprung ist das rechts draußen. Der
    größte ist 132 mm breit und passt dreimal; was fehlt, ist ein Klick auf
    *Auf dem Bett anordnen*. Angeboten wurden *Modell teilen*, *Auf den Bauraum
    verkleinern* und *Anderen Drucker wählen* — drei Handlungen, von denen
    keine hilft, dreimal, gleich beim Öffnen.

    Der Rand ist eine Bahnbreite: Ein Körper, der genau so breit ist wie das
    Bett, hat seine äußere Wand zur Hälfte daneben, und kein Anordnen holt sie
    zurück. Deshalb ist das kein Grenzwert für den Geschmack, sondern das Maß
    der Bahn (Regel 7).
    """
    return all(
        size + margin <= limit for size, limit in zip(bounds.size, allowed.size, strict=True)
    )


#: Welche Felder eines Befunds Indizes in die geprüfte Liste sind. ``object``
#: kommt von der Bauraumprüfung, ``a`` und ``b`` von der Kollisionsprüfung.
_INDEX_FIELDS = ("object", "a", "b")


def named_for(findings: list[Finding], entries: Sequence[Any]) -> list[Finding]:
    """Ersetzt die Indizes eines Befunds durch Namen und setzt den Körper.

    Die Prüfungen bekommen eine Liste von Netzen und kennen darum nur deren
    Reihenfolge. Der Bericht las das als „Zwei Objekte überschneiden sich" —
    bei zwei Körpern ist klar, welche gemeint sind, bei zwanzig steht man davor
    und sucht. Wer die Kennungen hat, trägt sie nach; das ist der Aufrufer,
    denn er hat die Szene.
    """
    import dataclasses

    named: list[Finding] = []
    for finding in findings:
        values = dict(finding.values)
        first: Any = None
        for field_name in _INDEX_FIELDS:
            index = values.get(field_name)
            if not isinstance(index, int | float) or not 0 <= int(index) < len(entries):
                continue
            entry = entries[int(index)]
            values[field_name] = entry.name
            if first is None:
                first = entry.id
        named.append(
            dataclasses.replace(finding, object_id=finding.object_id or first, values=values)
        )
    return named


def check_collisions(meshes: list[MeshData], clearance: float = 0.0) -> list[Finding]:
    """Überschneiden sich zwei Körper wirklich (§18.6)?

    Zwei Stufen, weil die billige Antwort oft genug falsch ist, um zu zählen.
    Erst die Quader: sie schließen fast jedes Paar umsonst aus. Was das
    übersteht, wird richtig gefragt — zwei Teile, die ineinandergreifen, haben
    überlappende Quader und berühren sich nirgends, und ein Bericht, der das
    Kollision nennt, ist ein Bericht, den Leute zu ignorieren lernen.

    Wo die exakte Antwort nicht zu haben ist — ein offener Körper hat kein
    Innen —, bleibt der Quader stehen, und der Befund sagt, welcher von beiden
    es ist.
    """
    findings: list[Finding] = []
    for first in range(len(meshes)):
        for second in range(first + 1, len(meshes)):
            if not _boxes_overlap(meshes[first].bounds, meshes[second].bounds, clearance):
                continue

            exact = _really_overlap(meshes[first], meshes[second], clearance)
            if exact is False:
                # Quader überlappen, Körper berühren sich nicht. Das ist eine
                # Baugruppe, kein Problem — und es für jedes Paar eines
                # Produkts zu sagen, wäre das Rauschen, das einen Bericht
                # unlesbar macht.
                continue
            values: dict[str, Any] = {
                "a": first,
                "b": second,
                "checked": "exact" if exact is not None else "box",
            }
            if exact is not None and meshes[first].is_watertight and meshes[second].is_watertight:
                # Wie viel — ein Streifschuss von einem Kubikmillimeter ist
                # etwas anderes als zwei Teile, die zur Hälfte ineinander
                # stecken, und der Bericht sagte für beides dasselbe.
                shared = shared_volume(meshes[first].raw, meshes[second].raw)
                if shared > EPS_GEOM:
                    values["shared"] = format_volume(shared)
            findings.append(
                Finding(
                    code="arrange.collision",
                    severity="warning",
                    message=_("Zwei Objekte überschneiden sich."),
                    values=values,
                )
            )
    return findings


def _really_overlap(first: MeshData, second: MeshData, clearance: float) -> bool | None:
    """Teilen sich die Körper Volumen, oder kommen sie sich näher als
    ``clearance``?

    ``None``, wenn sich das nicht entscheiden lässt — ein offener Körper hat
    kein Innen, und eines zu raten machte aus einer Warnung eine Lüge.

    :func:`shared_volume` fragt den Kern direkt, statt durch die Rückfallkette
    aus §17.2 zu gehen, und zählt bloßes Berühren als nichts — zwei Teile
    nebeneinander auf der Platte stehen sich nicht im Weg.
    """
    if not (first.is_watertight and second.is_watertight):
        return None

    if shared_volume(first.raw, second.raw) > EPS_GEOM:
        return True
    if clearance <= EPS_GEOM:
        return False

    # Auseinander, aber vielleicht nicht weit genug. Gemessen ab der
    # Oberfläche — das ist es, was ein Abstand auf der Platte bedeutet.
    try:
        _closest, distance, _face = on_surface(
            first.raw, np.asarray(second.raw.vertices, dtype=float)
        )
    except PROGRAMMING_ERRORS:
        raise
    except Exception:  # eine Abstandsanfrage an einen kaputten Körper scheitert auf eigene Arten
        return False
    return bool(len(distance)) and float(np.min(distance)) < clearance


def _boxes_overlap(first: BoundingBox, second: BoundingBox, clearance: float) -> bool:
    for axis in range(3):
        if first.maximum[axis] + clearance <= second.minimum[axis]:
            return False
        if second.maximum[axis] + clearance <= first.minimum[axis]:
            return False
    return True
