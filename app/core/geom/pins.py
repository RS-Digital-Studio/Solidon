"""Passstifte über eine Trennebene (Bauplan §25, §14).

Ein geteiltes Teil, das nur geklebt wird, lässt dem, der es hält, eine
Aufgabe: die Hälften auszurichten, während der Kleber greift. Zwei Stifte
nehmen diese Aufgabe ab — und sie sind der Grund, warum Auto Split überhaupt
lohnt.

Wo die Stifte hinkommen, entscheidet sich auf der Schnittfläche, nicht am
Hüllquader: das Schnittpolygon wird um Stiftradius plus Wand eingezogen, und
was übrig bleibt, ist, wo *quer zur Naht* Platz ist. Zwei Stifte entlang der
langen Richtung dieses Bereichs — einer ließe die Hälften verdrehen.

**Quer ist nicht tief.** Die Schnittfläche sagt nichts darüber, wie weit das
Material hinter ihr reicht, und bei einem hohlen Teil — also genau bei dem, das
man teilt — ist beides grundverschieden. Die Trennwand eines Besteckkorbs
liefert eine Fläche von 180 auf 120 mm und dahinter anderthalb Millimeter
Material, dann kommt das Fach. Ein Stift, der sich nur nach der Fläche richtet,
steht mit zehn Millimetern im Fach, und seine Bohrung geht durch die Wand. Die
Tiefe wird deshalb an jeder Stelle gemessen (:func:`_material_depth`); der
Stift wird auf das gekürzt, was trägt, und wo nicht einmal das bleibt, entsteht
keiner und der Prüfbericht sagt warum.

Das Spiel ist hier keine Zahl. Es kommt aus dem Materialprofil (AGENTS.md
Regel 7), damit eine spätere Kalibrierung Teile erreicht, die vor ihr geteilt
wurden — und das Passungspaar hält den Verweis fest, nicht den Wert (§14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core.geom.autosplit import sections_across, upright_normal
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.geom.section import SectionPlane
from app.core.geom.transform import apply, translation
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.registry import PARTS
from app.core.log import get_logger
from app.core.types import Feature, FeatureId, Finding, Profile, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie viele Stifte eine Naht bekommt. Ein Stift ist ein Scharnier, drei sind
#: ein Toleranzproblem.
PIN_COUNT = 2

#: Stiftdurchmesser relativ zur kürzeren Seite der Schnittfläche, und der
#: Bereich, in dem er gehalten wird. Dünne Stifte scheren ab, dicke schwächen
#: das Teil, in dem sie sitzen.
PIN_RELATIVE = 0.12
PIN_MIN = 3.0
PIN_MAX = 8.0

#: Wie tief ein Stift in jeder Hälfte sitzt, relativ zu seinem Durchmesser.
PIN_DEPTH_FACTOR = 1.5

#: Wie tief er mindestens sitzen muss, ebenfalls relativ zum Durchmesser.
#:
#: Die Grenze, unterhalb derer ein Stift nichts mehr führt: Ein Zapfen, der
#: kürzer ist als er dick, richtet die Hälften nicht aus, sondern schert beim
#: Fügen ab — und eine Naht ohne Stift klebt besser als eine mit einem
#: abgebrochenen darin. Wo weniger Material steht, entsteht deshalb keiner.
PIN_MIN_ENGAGEMENT = 0.75

#: Der Schnappverbinder unter den Querschnitten — er ist keiner, sondern ein
#: eigener Baustein, und beide Stellen, die ihn erkennen müssen, lesen hier.
SNAP = "snap"

#: Wie weit ein Federarm mindestens herausstehen muss. Zehn zu eins ist das
#: Verhältnis, das ein Arm zum Federn braucht (``SNAP_RATIO``), und zwei
#: Außenwände einer 0,4er Düse sind das Dünnste, was tragend gedruckt wird —
#: acht Millimeter ist das Produkt. Die Planung vergibt ``1,5 · Ø`` an Länge,
#: ein Schnapper braucht also eine Naht, die mindestens 5,4 mm Durchmesser
#: hergibt.
SNAP_MIN_REACH = 8.0

#: Material, das um einen Stift stehen bleiben muss. Darunter bricht die
#: Bohrung aus.
PIN_WALL = 1.6

#: Zusatztiefe der Bohrung über den Stift hinaus, damit die Hälften auf der
#: Fläche schließen und nicht auf dem Stiftende. Der Schnappverbinder braucht
#: dieselbe Zahl und kann sie hier nicht holen — sie wohnt deshalb bei den
#: Grundformen, unter beiden.
BORE_RELIEF = shapes.SEAT_RELIEF


@dataclass(frozen=True, slots=True)
class PinPlan:
    """Wo die Stifte hinkommen, und wie groß sie sind."""

    positions: tuple[Vec3, ...]
    diameter: float
    length: float
    normal: Vec3
    """Richtung, in der die Stifte stehen — die Normale der Trennebene.

    Sie war lange ein Achsenbuchstabe, und das reichte, solange nur Auto Split
    verstiftete: dessen Ebenen stehen immer quer zu x, y oder z. Eine
    gezeichnete Trennlinie steht schief, und ein Stift, der dann entlang der
    nächstgelegenen Achse aufgestellt wird, steht nicht senkrecht auf der
    Fläche, in der er sitzt — er schert beim Fügen.
    """
    shape: str = "round"
    """Querschnitt der Stifte — ``round``, ``hex`` oder ``dovetail``.

    Rund braucht zwei Stück gegen Verdrehen, die kantigen halten schon
    einzeln. Welcher es ist, entscheidet der Nutzer; die Planung sucht in
    jedem Fall Platz für einen Kreis dieses Durchmessers, und was
    hineingelegt wird, passt dann hinein."""
    findings: tuple[Finding, ...] = ()

    @property
    def count(self) -> int:
        return len(self.positions)


@dataclass(slots=True)
class PinnedPair:
    """Beide Hälften nach dem Verstiften, mit den Merkmalen, die ein
    Passungspaar braucht."""

    first: MeshData
    second: MeshData
    pin_features: dict[FeatureId, Feature] = field(default_factory=dict)
    bore_features: dict[FeatureId, Feature] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


def plan_pins(
    mesh: MeshData,
    plane: SectionPlane,
    *,
    count: int = PIN_COUNT,
    wall: float = PIN_WALL,
    shape: str = "round",
) -> PinPlan:
    """Sucht Platz für Stifte auf der Schnittfläche von ``plane``.

    Zwei Fragen, zwei Richtungen: Ist die Fläche breit genug, und steht hinter
    ihr genug Material? Die erste beantwortet der Puffer, die zweite ein
    Strahlenpaar je Stelle. Reicht die Tiefe für den Durchmesser nicht, den die
    Fläche hergäbe, wird der Stift dünner und kürzer, statt zu entfallen.

    Liefert einen Plan ohne Positionen, wenn beides nicht zusammengeht — eine
    Naht ohne Stifte klebt immer noch, ein Stift, der aus der Wand ausbricht,
    nicht.
    """
    normal = _unit(plane.normal)
    section = sections_across(mesh, normal, np.array([plane.position]))[0]
    if section is None or section.is_empty:
        return PinPlan((), 0.0, 0.0, normal, shape, (_no_face(),))

    largest = max(getattr(section, "geoms", (section,)), key=lambda entry: entry.area)
    diameter = _diameter(largest)
    seats = _seat(mesh, largest, plane, normal, diameter, count, wall)
    if seats is None:
        return PinPlan((), 0.0, 0.0, normal, shape, (_too_small(diameter, wall),))

    # Die Fläche nennt eine obere Schranke für den Durchmesser, die Tiefe eine
    # zweite. Wo die zweite kleiner ist, wird der Stift dünner statt zu
    # entfallen: Einbindung und Durchmesser hängen aneinander
    # (:data:`PIN_MIN_ENGAGEMENT`), und ein dünnerer braucht weniger. Gemessen
    # wird an der *tiefsten* Stelle — sie bestimmt, was überhaupt möglich ist;
    # welche Stellen es dann mittragen, entscheidet sich danach.
    thickest = max((raw for _point, _usable, raw in seats), default=0.0)
    deepest = max((usable for _point, usable, _raw in seats), default=0.0)
    if deepest < diameter * PIN_MIN_ENGAGEMENT:
        thinner = deepest / PIN_MIN_ENGAGEMENT
        if thinner < PIN_MIN:
            needed = PIN_MIN * PIN_MIN_ENGAGEMENT + BORE_RELIEF + wall
            return PinPlan(
                (), 0.0, 0.0, normal, shape, (_seam_too_thin(diameter, thickest, needed),)
            )
        diameter = thinner
        seats = _seat(mesh, largest, plane, normal, diameter, count, wall)
        if seats is None:
            return PinPlan((), 0.0, 0.0, normal, shape, (_too_small(diameter, wall),))

    # Fließkomma: Nach dem Verdünnen ist die Einbindung genau die gemessene
    # Tiefe, und ein Vergleich auf Gleichheit entschiede dort ein letztes Bit.
    enough = diameter * PIN_MIN_ENGAGEMENT - EPS_GEOM
    seated = [(point, usable) for point, usable, _raw in seats if usable >= enough]
    if not seated:
        # Nach dem Verdünnen stehen die Stellen woanders — der Befund nennt die
        # Tiefe, die dort gemessen wurde, und nicht die vom ersten Anlauf.
        thickest = max((raw for _point, _usable, raw in seats), default=thickest)
        needed = diameter * PIN_MIN_ENGAGEMENT + BORE_RELIEF + wall
        return PinPlan((), 0.0, 0.0, normal, shape, (_seam_too_thin(diameter, thickest, needed),))

    # Der Stift ist so lang, wie die dünnste seiner Stellen trägt — alle
    # teilen sich einen Körper, und der längste gemeinsame Nenner ist der
    # kleinste. Länger als vorgesehen wird er nie: ein Stift, der die halbe
    # Wand durchmisst, schwächt sie mehr, als er hilft.
    reach = min(diameter * PIN_DEPTH_FACTOR, min(usable for _point, usable in seated))
    points = tuple(point for point, _usable in seated)
    length = reach * 2.0

    if shape == SNAP and length / 2.0 < SNAP_MIN_REACH:
        # Ein Federarm braucht eine Mindestlänge, sonst federt er nicht,
        # sondern bricht — und die Länge, die hier zu vergeben ist, hängt am
        # Durchmesser. Statt einen zu kurzen Arm zu bauen, der beim ersten
        # Zusammenstecken abreißt, kommt der Verbinder rund heraus, und der
        # Befund sagt warum. Das ist die Stelle, an der Regel 21 gilt: lieber
        # etwas anderes tun und es sagen, als stillschweigend etwas Untaugliches
        # liefern.
        shape = "round"
        findings = [_too_thin_for_snap(diameter)]
    else:
        findings = []

    return PinPlan(
        positions=points,
        diameter=diameter,
        length=length,
        normal=normal,
        shape=shape,
        findings=tuple(findings),
    )


def _unit(normal: Vec3) -> Vec3:
    """Die Richtung auf Länge eins. Alles hier rechnet mit Einheitsnormalen —
    die Ebenenlage ist sonst ein Vielfaches ihrer selbst."""
    vector = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(vector))
    if length <= EPS_GEOM:
        return (0.0, 0.0, 1.0)
    vector = vector / length
    return (float(vector[0]), float(vector[1]), float(vector[2]))


def _diameter(section: Any) -> float:
    """Aus der schmalsten Richtung der Fläche, gehalten im nutzbaren Bereich."""
    low_x, low_y, high_x, high_y = section.bounds
    narrow = min(high_x - low_x, high_y - low_y)
    return float(min(PIN_MAX, max(PIN_MIN, narrow * PIN_RELATIVE)))


def _spread(room: Any, count: int) -> list[tuple[float, float]]:
    """Punkte, verteilt entlang der langen Richtung des nutzbaren Bereichs.

    Entlang der *langen* Richtung mit Absicht: zwei Stifte dicht beieinander
    halten gegen Verdrehen etwa so gut wie einer.
    """
    from shapely.geometry import Point
    from shapely.ops import nearest_points

    low_x, low_y, high_x, high_y = room.bounds
    horizontal = (high_x - low_x) >= (high_y - low_y)
    span = (low_x, high_x) if horizontal else (low_y, high_y)
    fixed = (low_y + high_y) / 2.0 if horizontal else (low_x + high_x) / 2.0

    points: list[tuple[float, float]] = []
    for index in range(count):
        along = span[0] + (span[1] - span[0]) * (2 * index + 1) / (2 * count)
        candidate = Point(along, fixed) if horizontal else Point(fixed, along)
        if not room.contains(candidate):
            candidate = nearest_points(room, candidate)[0]
        points.append((float(candidate.x), float(candidate.y)))
    return points


def _seat(
    mesh: MeshData,
    section: Any,
    plane: SectionPlane,
    normal: Vec3,
    diameter: float,
    count: int,
    wall: float,
) -> list[tuple[Vec3, float, float]] | None:
    """Wo Stifte dieses Durchmessers stünden, wie tief sie dort fassen, und wie
    viel Material überhaupt da ist.

    Zwei Schranken, zwei Richtungen: Quer zur Naht zieht der Puffer die Fläche
    um Stiftradius plus Wand ein — bleibt nichts übrig, gibt es keinen Platz
    (``None``). Längs misst :func:`_material_depth`, und davon geht ab, was
    hinter der Bohrung stehen bleiben muss: der Freistich, um den sie tiefer
    reicht als der Stift, und eine Wandstärke, damit sie nicht auf der anderen
    Seite herauskommt.

    Zurück kommen beide Zahlen. Die Einbindung ist die, mit der gerechnet wird;
    die rohe Tiefe ist die, die in den Befund gehört — wer liest, dass 1,5 mm
    nicht reichen, sucht seine Wand, und die ist 3 mm dick.
    """
    inset = section.buffer(-(diameter / 2.0 + wall))
    if inset.is_empty:
        return None
    room = max(getattr(inset, "geoms", (inset,)), key=lambda entry: entry.area)
    placed = [_in_world(point, plane.position, normal) for point in _spread(room, count)]
    seats: list[tuple[Vec3, float, float]] = []
    for point in placed:
        raw = _material_depth(mesh, point, normal)
        seats.append((point, raw - BORE_RELIEF - wall, raw))
    return seats


def _material_depth(mesh: MeshData, point: Vec3, normal: Vec3) -> float:
    """Wie weit von der Naht aus Material steht — die dünnere der zwei Seiten.

    Zwei Strahlen vom Nahtpunkt aus, einer in jede Richtung; gezählt wird der
    erste Austritt. Zurück kommt der kleinere der beiden Wege, denn der Stift
    sitzt in **beiden** Hälften, und die dünnere entscheidet.

    Null, wenn ein Strahl nichts trifft: Dann steht dort kein Material, und ein
    Stift hätte nichts, worin er sitzt. Das ist kein Sonderfall, sondern der
    Normalfall bei einer Naht, die neben dem Hohlraum durch die Wand läuft.
    """
    body = mesh.raw
    origin = np.asarray(point, dtype=float)
    direction = np.asarray(normal, dtype=float)
    both: list[float] = []
    for sign in (1.0, -1.0):
        hits, _rays, _faces = body.ray.intersects_location(
            ray_origins=origin.reshape(1, 3),
            ray_directions=(direction * sign).reshape(1, 3),
        )
        if len(hits) == 0:
            return 0.0
        distances = np.linalg.norm(np.asarray(hits, dtype=float) - origin, axis=1)
        # Der Punkt liegt auf der Trennebene und damit oft genau auf einer
        # Kante des Schnitts; ein Treffer im Abstand null ist er selbst.
        ahead = distances[distances > EPS_GEOM]
        if not len(ahead):
            return 0.0
        both.append(float(ahead.min()))
    return min(both)


def _in_world(point: tuple[float, float], position: float, normal: Vec3) -> Vec3:
    """Ein Punkt des Schnitts zurück in Weltkoordinaten.

    Der Schnitt wurde mit aufgerichteter Trennrichtung genommen, der Rückweg
    ist also dieselbe Drehung, invertiert — keine Tabelle von
    Vorzeichenwechseln, die für drei Achsen gleichzeitig stimmen muss, und
    für eine schiefe Richtung gäbe es sie ohnehin nicht.
    """
    turned = np.array([point[0], point[1], position, 1.0])
    back = np.linalg.inv(upright_normal(normal)) @ turned
    return (float(back[0]), float(back[1]), float(back[2]))


def add_pins(
    first: MeshData,
    second: MeshData,
    plan: PinPlan,
    profile: Profile,
    *,
    play: float | None = None,
) -> PinnedPair:
    """Setzt die Stifte in die eine Hälfte und die Bohrungen in die andere.

    ``first`` trägt die Stifte. Welche Hälfte das ist, ist mechanisch egal —
    wichtig ist, dass die beiden auseinandergehalten werden, denn das
    Passungspaar benennt je eine (§14).
    """
    pair = PinnedPair(first=first, second=second, findings=list(plan.findings))
    if not plan.count:
        return pair

    clearance = profile.material.clearance if play is None else play
    if plan.shape == SNAP:
        # Der Schnapper ist ein eigener Baustein und kein Querschnitt: Arm mit
        # Haken auf der einen, Tasche mit Rastkante auf der anderen Seite.
        #
        # Er sitzt auch anders. Ein Passstift steckt zur Hälfte in seiner
        # eigenen Hälfte, deshalb bekommt er die volle Länge und einen Versatz
        # nach hinten. Ein Federarm wächst aus der Wand — sein Fuß *ist* die
        # Nahtfläche, an der er angeschweißt wird. Beide Körper stehen deshalb
        # auf der Naht und reichen gleich weit hinein.
        reach = plan.length / 2.0
        pin_body = _part("snap_connector", diameter=plan.diameter, length=reach, kind="pin")
        bore_body = _part(
            "snap_connector",
            diameter=plan.diameter,
            length=reach,
            kind="bore",
            play=clearance,
        )
        pin_offset = 0.0
    else:
        pin_body = _part(
            "dowel",
            diameter=plan.diameter,
            length=plan.length,
            kind="pin",
            shape=plan.shape,
            play=0.0,
        )
        bore_body = _part(
            "dowel",
            diameter=plan.diameter,
            length=plan.length / 2.0 + BORE_RELIEF,
            kind="bore",
            shape=plan.shape,
            play=clearance,
        )
        pin_offset = -plan.length / 2.0

    for index, position in enumerate(plan.positions, start=1):
        placed_pin = _along_normal(pin_body, plan.normal, position, pin_offset)
        placed_bore = _along_normal(bore_body, plan.normal, position, 0.0)

        pair.first = boolean("union", [pair.first, placed_pin]).mesh
        pair.second = boolean("difference", [pair.second, placed_bore]).mesh

        axis_vector = plan.normal
        pair.pin_features[f"pin_{index}"] = Feature(
            id=f"pin_{index}",
            kind="pin",
            provenance="generated",
            params={
                "diameter": round(plan.diameter, 4),
                "centre": position,
                "axis": axis_vector,
                "depth": round(plan.length / 2.0, 4),
            },
        )
        pair.bore_features[f"bore_{index}"] = Feature(
            id=f"bore_{index}",
            kind="hole",
            provenance="generated",
            params={
                "diameter": round(plan.diameter + clearance, 4),
                "centre": position,
                "axis": axis_vector,
                "depth": round(plan.length / 2.0 + BORE_RELIEF, 4),
            },
        )

    _log.info("pinned a seam with %d pin(s) of %.1f mm", plan.count, plan.diameter)
    return pair


def _part(name: str, **values: Any) -> MeshData:
    """Ein Körper aus der Bibliothek. Bausteine vor Primitiven (§39), auch hier."""
    from app.core.geom.mesh import as_mesh_data

    spec = PARTS.get(name)
    return as_mesh_data(spec.fn(spec.params(**values)).mesh)


def _along_normal(body: MeshData, normal: Vec3, position: Vec3, offset: float) -> MeshData:
    """Legt einen Baustein, der auf +Z steht, in die Trennrichtung und schiebt
    ihn an seinen Platz.

    Gedreht wird mit derselben Matrix wie der Schnitt, nur andersherum: was
    :func:`upright_normal` auf +Z legt, kommt hier von +Z zurück. Drei
    Sonderfälle für drei Achsen standen hier vorher und waren für eine schiefe
    Ebene nicht zu ergänzen.
    """
    turn = np.linalg.inv(upright_normal(normal))
    placed = MeshData.of(body.raw.copy().apply_transform(turn))
    direction = np.asarray(normal, dtype=float)
    target = np.asarray(position, dtype=float) + direction * offset
    return apply(placed, translation((float(target[0]), float(target[1]), float(target[2]))))


def _no_face() -> Finding:
    return Finding(
        code="split.no_cut_face",
        severity="warning",
        message=_("An der Trennebene war keine Schnittfläche zu finden."),
    )


def _too_thin_for_snap(diameter: float) -> Finding:
    """Die Naht gibt keinen Federarm her — es wurde rund verstiftet."""
    return Finding(
        code="split.snap_too_small",
        severity="info",
        message=_(
            "Für einen Schnappverbinder ist die Naht zu schmal — er wäre zu kurz zum "
            "Federn. Es sind runde Stifte geworden; zum Zusammenstecken hilft Kleber."
        ),
        values={"diameter_mm": round(diameter, 2), "needed_mm": round(SNAP_MIN_REACH, 2)},
    )


def _seam_too_thin(diameter: float, found: float, needed: float) -> Finding:
    """Die Fläche wäre groß genug, das Material hinter ihr ist es nicht.

    Der Unterschied zu :func:`_too_small` steckt in der Richtung und gehört
    deshalb in einen eigenen Befund: Dort ist die Naht zu schmal, hier ist sie
    zu dünn. Wer die eine Meldung für die andere liest, sucht an der falschen
    Stelle — bei einem Kasten ist die Naht so breit wie die ganze Wand.
    """
    return Finding(
        code="split.seam_too_thin",
        severity="warning",
        message=_(
            "Hinter der Trennfläche steht zu wenig Material für einen Stift — er "
            "stünde im Hohlraum, und seine Bohrung ginge durch die Wand. Getrennt "
            "wurde trotzdem; geklebt hält die Naht."
        ),
        values={
            "diameter_mm": round(diameter, 2),
            "depth_mm": round(found, 2),
            "needed_mm": round(needed, 2),
        },
    )


def _too_small(diameter: float, wall: float) -> Finding:
    return Finding(
        code="split.face_too_small",
        severity="warning",
        message=_("Die Schnittfläche ist für Passstifte zu klein — geklebt hält sie trotzdem."),
        values={"diameter_mm": round(diameter, 2), "wall_mm": round(wall, 2)},
    )
