"""Druckvorbereitung: Bohrungen, Teilen, Anordnen, Kollisionen (Bauplan §25,
§18.6).

Drei Regeln aus der Regelsammlung (§39) leben hier, weil sie sonst genau hier
vergessen würden:

* eine Bohrung wird größer gebohrt als nominal, denn FDM druckt Löcher zu
  eng — und der Betrag kommt aus dem kalibrierten Materialprofil, nie aus
  einem Literal (AGENTS.md Regel 7);
* durchgehende Werkzeuge reichen über den Körper hinaus; eine Blindbohrung
  endet dagegen genau an ihrer eingegebenen Tiefe und ragt nur an der Mündung
  um :data:`BOOLEAN_OVERLAP` über die Fläche, damit nie zwei Flächen
  zusammenfallen;
* was den Bauraum verlässt, wird gemeldet, nicht still skaliert.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

import numpy as np
from shapely import get_coordinates
from shapely.affinity import translate as shift_polygon
from shapely.geometry import box

from app.core import units
from app.core.build_area import (
    fits_on_bed,
    fits_xy,
    footprint,
    placement_offset,
    printable_area,
    printable_height,
)
from app.core.deferred import trimesh
from app.core.errors import (
    ARRANGE_ON_BED,
    CORRECT_INPUT,
    PROGRAMMING_ERRORS,
    SHOW_HISTORY,
    ValidationError,
)
from app.core.geom import kernel_process, lathe, transform
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    BooleanKind,
    boolean,
    shared_volume,
    without_effect,
)
from app.core.geom.measure import surface_gap
from app.core.geom.mesh import MeshData, as_mesh_data, concatenated, ray_hit_distances
from app.core.geom.section import AXIS_NORMALS, SectionPlane, check_cut_contact, cut
from app.core.geom.transform import Axis, translation
from app.core.knowledge.print_settings import is_slender
from app.core.knowledge.profiles import resolve_tolerance
from app.core.registry import param
from app.core.types import (
    BoundingBox,
    CancelToken,
    Finding,
    Mesh,
    ObjectId,
    ParamPlacement,
    PlaneFrame,
    Profile,
    Quality,
    Scene,
    SceneObject,
    Severity,
    SolverInfo,
    Vec3,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM, format_length, format_volume, is_close
from app.i18n import TranslatableText, _

if TYPE_CHECKING:  # pragma: no cover - nur für die Typprüfung
    from app.core.sketch.profile import Profile as SketchProfile

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
    cutting_tool: MeshData | None = None
    """Das tatsächliche Werkzeug für die Prüfung benachbarter Hohlräume."""


def bore_geometry_error(value: str | None = None) -> ValidationError:
    """Ein unbrauchbares Bohrungsmerkmal braucht eine neue Erkennung."""
    return ValidationError(
        field="at_feature",
        detail=_(
            "Diese erkannte Bohrung enthält keine verwendbaren Geometriedaten. "
            "Lassen Sie die Merkmale neu erkennen und wählen Sie sie danach erneut."
        ),
        value=value,
        constraint="no_geometry",
    )


def compensation_findings(nominal: float, cut: float, compensate: bool) -> list[Finding]:
    """Der Hinweis, dass eine Bohrung um die Materialtoleranz gewachsen ist.

    **Einmal für alle drei Bohrungswege.** Der Befund stand bis zum 04.09.2026
    dreifach im Baum: hier ausgeschrieben, in ``brep.ops`` ausgeschrieben, und
    in ``prepare_ops`` als Funktion, deren eigener Docstring „wortgleich mit
    den anderen Bohrungswegen" sagte — mit genau einem Aufrufer. Der Satz
    selbst ist ein übersetzter Oberflächentext, und eine Änderung an ihm hätte
    drei Stellen und sechs Kataloge treffen müssen.

    Leer heißt: nichts zu melden. Ohne Kompensation gibt es keinen Hinweis, und
    ein Maß, das sich nicht messbar geändert hat, ist keine Vergrößerung
    (Regel 6 — verglichen wird über :func:`~app.core.units.is_close`).
    """
    if not compensate or is_close(cut, nominal):
        return []
    return [
        Finding(
            code="bore.compensated",
            severity="info",
            message=_("Die Bohrung wurde um die Materialtoleranz vergrößert."),
            values={"nominal": format_length(nominal), "cut": format_length(cut)},
        )
    ]


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


class HasComponents(Protocol):
    """Was :func:`split_findings` von einem Körper braucht: seine Teilezahl.

    Dieselbe Bauart wie :class:`HasBounds`, aus demselben Grund — ``MeshData``
    und der exakte ``Solid`` tragen beide ``component_count``.
    """

    @property
    def component_count(self) -> int: ...


def over_the_edge(
    mesh: HasBounds,
    position: Vec3,
    axis: Axis,
    diameter: float,
    *,
    body: MeshData | None = None,
    reach: float | None = None,
    along: float = 0.0,
) -> list[Finding]:
    """Ragt die Bohrung seitlich über den Körper hinaus?

    „Nichts abgetragen" gibt es seit je (:func:`without_effect`); dies ist der
    Fall dazwischen, und er ist der gefährlichere: es wird etwas abgetragen,
    also schweigt jede Prüfung, und heraus kommt eine Bohrung mit offener
    Flanke. Der Agent hat ihn gebaut — auf „5 mm mittig durch" kam die Ecke,
    weil das Modell mit einem Quader ab dem Ursprung rechnete statt mit einem
    um ihn herum. Abgetragen wurde ein Viertel, und die Antwort lautete
    trotzdem „durchgehend und mittig".

    Gemessen wird zuerst am Hüllquader. Innerhalb der Hülle trifft eine
    Bohrung, die ins Leere geht, einen Hohlraum — den kann sie treffen sollen
    —, gar nichts, dann greift ``without_effect`` — **oder eine Seite, die
    schmaler ist als die Hülle** (RM-249): Dafür fragt ``reach`` mit ``body``
    am Netz nach (:func:`over_the_edge_along`).
    """
    direction = [0.0, 0.0, 0.0]
    direction[AXIS_INDEX[axis]] = 1.0
    vector: Vec3 = (direction[0], direction[1], direction[2])
    return over_the_edge_along(
        mesh, position, vector, diameter, body=body, reach=reach, along=along
    )


#: Wie fein die Mündung abgetastet wird, wenn der Hüllquader Verdacht meldet.
#:
#: Zwölf Punkte auf dem Kreis und Schritte von einem halben Radius in die Tiefe:
#: Weniger übersieht eine Kante, die zwischen zwei Punkten hindurchläuft, mehr
#: kostet nur Zeit an einer Frage, die im Regelfall gar nicht gestellt wird.
_RIM_POINTS: Final = 12
_RIM_STEPS: Final = 16


@dataclass(frozen=True, slots=True)
class OpeningSpace:
    """Der Raum einer Öffnung, die ein Zug überdeckt, ohne sie vorher zu schließen.

    **Gefragt wird nach der Kante am Körper ohne die alte Öffnung**
    (``prepare_ops._edge_findings``: am gefüllten Körper vor dem Schnitt). Wer ein
    Langloch an derselben Stelle weiterzieht, schließt es nicht erst — der neue
    Umriss enthält den alten (``prepare_ops.slot_hole``, ``closes_the_old``).
    Der Kranz um ein Bogenende liegt dann zur Hälfte in der alten Öffnung, und
    an einer schrägen Platte sah diese Luft unter der tiefen Seite der Mündung
    hindurch ins Freie: „über die Kante" an einem Langloch mitten in der
    Fläche, an beiden Kernen (RM-411). Was in diesem Raum liegt, zählt für die
    Frage als Material, wie am gefüllten Körper, ohne einen Stopfen zu rechnen.

    ``axis`` und ``direction`` sind Einheitsvektoren, ``direction`` quer zu
    ``axis``; ``travel`` ist der Weg zwischen den Bogenmitten, null für eine
    runde Bohrung; ``half_depth`` die halbe Länge entlang der Achse.
    """

    centre: Vec3
    axis: Vec3
    direction: Vec3
    travel: float
    radius: float
    half_depth: float

    def holds(self, points: np.ndarray) -> np.ndarray:
        """Welche Punkte im Raum der Öffnung liegen, ihre Wand eingeschlossen.

        Elementweise, ohne BLAS (RM-187): Die Antwort entscheidet, welche Proben
        der Kantenfrage zählen.
        """
        relative = np.asarray(points, dtype=float) - np.asarray(self.centre, dtype=float)
        height = transform.along(relative, self.axis)
        across = relative - height[:, None] * np.asarray(self.axis, dtype=float)
        sideways = np.clip(
            transform.along(across, self.direction), -self.travel / 2.0, self.travel / 2.0
        )
        apart = across - sideways[:, None] * np.asarray(self.direction, dtype=float)
        distance = apart[:, 0] * apart[:, 0] + apart[:, 1] * apart[:, 1] + apart[:, 2] * apart[:, 2]
        reach = self.radius + EPS_GEOM
        return np.asarray(
            (np.abs(height) <= self.half_depth + EPS_GEOM) & (distance <= reach * reach)
        )


def _flank_is_open(
    body: MeshData,
    position: Vec3,
    unit: Any,
    radius: float,
    old_opening: OpeningSpace | None = None,
) -> bool:
    """Ob die Bohrung wirklich eine offene Flanke hinterlässt.

    Was in ``old_opening`` liegt, zählt als Material (:class:`OpeningSpace`).

    Gefragt wird an der Sache und nicht am Hüllquader: Eine Bohrung, die
    irgendwo auf ihrer Länge **ringsum** Material hat, reißt dort nicht auf.
    Abgetastet wird ein Kranz von Punkten auf dem Bohrungsumfang, entlang der
    Achse in beide Richtungen — liegt er an einer einzigen Tiefe vollständig
    im Material, ist die Flanke geschlossen.

    **Warum in beide Richtungen.** Die Aufrufer geben verschiedene Vektoren:
    die Flächennormale (die vom Material weg zeigt), die Achse eines erkannten
    Merkmals, eine Hauptachse. Welche Seite „hinein" ist, weiß diese Funktion
    nicht — und sie muss es nicht, denn die Frage gilt der ganzen Länge.

    **Innen und außen entscheidet** :func:`~app.core.geom.mesh.on_surface`,
    nicht ``trimesh.contains``: Das führt durch ``rtree``, und das Paket darf
    diesen Prozess nicht betreten (der Grund steht an ``on_surface``). Der
    nächste Oberflächenpunkt und die Normale seines Dreiecks tragen dieselbe
    Auskunft — zeigt der Weg vom Netz zum Punkt in die Normale, liegt er
    draußen. Über ``ray_hit_distances`` ginge es **nicht**: Ein Treffer auf
    einer geteilten Kante zählt dort mehrfach, und damit trägt die Parität
    nicht.
    """
    from app.core.geom.mesh import on_surface

    reach = float(np.linalg.norm(np.asarray(body.bounds.maximum) - np.asarray(body.bounds.minimum)))
    if reach <= EPS_GEOM or radius <= EPS_GEOM:
        return True
    axis = np.asarray(unit, dtype=float)
    rim = _rim_around(axis, radius)
    step = reach / _RIM_STEPS
    depths = np.concatenate(
        (np.arange(1, _RIM_STEPS + 1) * step, np.arange(1, _RIM_STEPS + 1) * -step)
    )
    samples = np.asarray(position, dtype=float) + rim[None, :, :] + depths[:, None, None] * axis
    flat = samples.reshape(-1, 3)
    closest, _distance, triangle = on_surface(body.raw, flat, index=surface_index_of(body))
    normals = np.asarray(body.raw.face_normals)[triangle]
    outward = np.einsum("ij,ij->i", flat - closest, normals)
    solid = outward <= EPS_GEOM
    if old_opening is not None:
        solid = solid | old_opening.holds(flat)
    inside = solid.reshape(len(depths), _RIM_POINTS)
    return not bool(inside.all(axis=1).any())


def surface_index_of(mesh: MeshData) -> Any:
    """Der Suchbaum für :func:`app.core.geom.mesh.on_surface` — einmal je Körper.

    Die Mündungs- und Kantenproben fragen eine Handvoll Punkte, der Baum
    darunter kennt alle Dreiecke: am Gartenschlauchhalter 0,2 s für den Aufbau,
    je Bohrung neu (RM-181). Gemerkt wird er in den Merkern der Erkennung,
    nicht im Cache des Netzes (``features.WHOLE_BODY_ANSWERS``, acht über alle
    Körper), und er geht mit seinem Körper.
    """
    from app.core.geom.mesh import surface_index
    from app.core.perceive.features import remembered

    return remembered("surface_index", mesh.raw, (), lambda: surface_index(mesh.raw))


def _inside_material(body: MeshData, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Welche Punkte im Material liegen oder auf seiner Oberfläche — dieselbe
    Probe wie in :func:`_flank_is_open`, mit dem gemerkten Suchbaum. Dazu je
    Punkt die Normale der nächsten Fläche."""
    from app.core.geom.mesh import on_surface

    closest, _distance, triangle = on_surface(body.raw, points, index=surface_index_of(body))
    normals = np.asarray(body.raw.face_normals, dtype=float)[triangle]
    offset = points - closest
    outward = (
        offset[:, 0] * normals[:, 0] + offset[:, 1] * normals[:, 1] + offset[:, 2] * normals[:, 2]
    )
    return np.asarray(outward <= EPS_GEOM), normals


def _open_to_the_outside(body: MeshData, points: np.ndarray, across: np.ndarray) -> list[str]:
    """Die Achsen, zu denen Punkte außerhalb des Materials **frei** liegen: Ein
    Strahl von ihnen quer zur Bohrung nach außen trifft den Körper nicht mehr.

    Ein Punkt in einer Nachbarbohrung oder einem eingeschlossenen Hohlraum
    trifft die Wand dahinter und zählt nicht — dort ist die Flanke in den
    Nachbarn offen, und das sagt der Nachbarbefund (RM-249).
    """
    from app.core.geom.mesh import ray_hits_batch

    if not len(points):
        return []
    lengths = np.sqrt(across[:, 0] ** 2 + across[:, 1] ** 2 + across[:, 2] ** 2)
    directions = across / np.maximum(lengths, EPS_GEOM)[:, None]
    distances, _hit = ray_hits_batch(
        np.asarray(body.raw.triangles, dtype=float), points, directions
    )
    free = directions[~np.isfinite(distances)]
    return [name for index, name in enumerate("xyz") if bool(np.any(np.abs(free[:, index]) > 0.5))]


def _flank_opens_within(
    body: MeshData,
    position: Vec3,
    unit: Any,
    radius: float,
    reach: float,
    old_opening: OpeningSpace | None = None,
) -> list[str]:
    """Die Achsen, zu denen eine Bohrung **innerhalb der Hülle** seitlich aus dem
    Körper tritt — leer, wo sie das nicht tut.

    **Der Hüllquader urteilt nur über das, was über ihn hinausragt** (RM-249,
    26.09.2026). An der Lochplatte ``pegboard-gs-100-v2`` reicht die Platte auf
    Höhe der oberen Schraubbohrung nur bis x ≈ 13,6, ihre Hülle bis x = 20: Eine
    Kopie der Bohrung bei x = 12 lief mit der Zylindersenkung Ø 10 bis x = 17
    über die Seite, und keiner der beiden Kerne sagte etwas. Gefragt wird
    deshalb am Netz, über die eigene Länge der Bohrung — ``reach`` in beide
    Richtungen entlang der Achse, an der Stelle selbst und an einem Viertel,
    der Hälfte und drei Vierteln davon. Es zählen nur Tiefen, an denen die
    Bohrung schneidet — die Achse oder ein Punkt ihres Kranzes im Material; die
    übrigen sind Luft vor oder hinter dem Körper. Bei x = 14 liegt die Achse
    schon neben der Platte, und die Bohrung trägt trotzdem ein Stück ihrer
    Seite ab. Von den Punkten in Luft zählt nur, was nach außen frei liegt
    (:func:`_open_to_the_outside`).

    **Ringsum Material an einer Tiefe schließt keine andere** (Durchsicht
    0.5.1, BOHRUNG-01). Hier stand die Regel aus :func:`_flank_is_open`: Liegt
    der Kranz an einer Tiefe ganz im Material, ist die Flanke geschlossen. An
    einer abgesetzten Stelle stimmt das nicht — eine Bohrung Ø 6 lief im
    oberen Absatz eines Blocks 2 mm aus dessen Seite (57 mm² Seitenfläche
    fort) und hatte darunter in der Grundplatte ringsum Material; Bohren,
    Versetzen und Verdoppeln schwiegen an beiden Kernen. Gefragt wird deshalb
    je Punkt, **und nur ein Punkt vor einer Seitenfläche zählt**: Die nächste
    Fläche muss entlang der Bohrung stehen (:data:`_SIDE_FACE`). Ein Punkt vor
    einer Mündungsfläche — der Kranz einer gekippten Bohrung, der über die
    schräge Fläche ragt — liegt vor der Öffnung und nicht neben der Wand; und
    die Seitenfläche umläuft die Achse nicht (:data:`_AROUND_THE_AXIS`), sonst
    liegt der Punkt in einer weiteren Aussparung um die Bohrung. Die
    Aufrufer geben ``position`` als Mitte der Bohrung und ``reach`` als halbe
    Länge, damit keine Tiefe vor der Mündung liegt. Was in ``old_opening``
    liegt, zählt als Material (:class:`OpeningSpace`).
    """
    if reach <= EPS_GEOM or radius <= EPS_GEOM:
        return []
    axis = np.asarray(unit, dtype=float)
    axis = axis / math.hypot(float(axis[0]), float(axis[1]), float(axis[2]))
    rim = _rim_around(axis, radius)
    depths = reach * np.asarray(_WITHIN_DEPTHS, dtype=float)
    centres = np.asarray(position, dtype=float) + depths[:, None] * axis
    samples = centres[:, None, :] + rim[None, :, :]
    probes = np.vstack([centres, samples.reshape(-1, 3)])
    inside, normals = _inside_material(body, probes)
    if old_opening is not None:
        inside = inside | old_opening.holds(probes)
    ring = inside[len(depths) :].reshape(len(depths), _RIM_POINTS)
    facing = normals[len(depths) :].reshape(len(depths), _RIM_POINTS, 3)
    cutting = inside[: len(depths)] | ring.any(axis=1)
    if not bool(cutting.any()):
        return []
    along = np.abs(
        facing[:, :, 0] * axis[0] + facing[:, :, 1] * axis[1] + facing[:, :, 2] * axis[2]
    )
    # Und sie ist keine Wand um die Bohrung herum, die zur Achse zeigt — die
    # einer weiteren Aussparung, in der der Kranz liegt. Am
    # Gartenschlauchhalter lagen Punkte des Kranzes einer Zylindersenkung vor
    # ihrer schrägen Mündung in einer solchen Aussparung (Normale zur Achse
    # hin, Kosinus -0,96 bis -1) und hießen „über die Kante"; die Enden einer
    # Klammer (Besenhalter, -0,52) sind dagegen eine offene Seite.
    outward = (
        facing[:, :, 0] * rim[None, :, 0]
        + facing[:, :, 1] * rim[None, :, 1]
        + facing[:, :, 2] * rim[None, :, 2]
    ) / radius
    side = (along < _SIDE_FACE) & (outward > -_AROUND_THE_AXIS)
    rows, columns = np.nonzero(cutting[:, None] & ~ring & side)
    return _open_to_the_outside(body, samples[rows, columns], rim[columns])


#: Ab wann die nächste Fläche eines Punkts im Kranz eine Seitenfläche ist und
#: keine Mündungsfläche (:func:`_flank_opens_within`) — als Betrag des Kosinus
#: zwischen ihrer Normale und der Bohrungsachse. Eine Seitenwand steht entlang
#: der Bohrung (0), die Mündung einer um 30° gekippten quer zu ihr (0,87);
#: die Hälfte trennt Flächen bis 60° Neigung gegen die Achse als Mündung.
_SIDE_FACE: Final = 0.5

#: Ab wann eine Seitenfläche eine Wand um die Bohrung herum ist, die zur Achse
#: zeigt (:func:`_flank_opens_within`) — als Kosinus zwischen ihrer Normale
#: und der Richtung von der Achse zum Punkt, negativ genommen: Eine
#: umlaufende Wand steht bei -1, das Ende einer Klammer quer dazu bei 0.
_AROUND_THE_AXIS: Final = 0.7


#: Wo :func:`_flank_opens_within` entlang der Achse fragt, in Anteilen von
#: ``reach``: an der Stelle selbst und je ein Viertel, die Hälfte und drei
#: Viertel in beide Richtungen.
_WITHIN_DEPTHS: Final = (0.0, 0.25, -0.25, 0.5, -0.5, 0.75, -0.75)


def over_the_edge_along(
    mesh: HasBounds,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    *,
    body: MeshData | None = None,
    reach: float | None = None,
    along: float = 0.0,
    old_opening: OpeningSpace | None = None,
) -> list[Finding]:
    """Die Kantenprüfung für eine freie Bohrungsrichtung.

    Erkannte Bohrungen dürfen schräg liegen. Der seitliche Radius erscheint
    dann in allen drei Koordinaten, jeweils als Projektion der Kreisscheibe.
    Eine Rundung auf die nächste Hauptachse wäre genau die CAD-Arbeit, die der
    Klick auf ein erkanntes Merkmal vermeiden soll.

    **Der Hüllquader ist die Vorauswahl, nicht das Urteil** (09.09.2026).
    Allein gemessen meldete er jede Bohrung auf eine gekrümmte Außenfläche:
    Wer auf den Scheitel eines Zylinders, einer Kugel oder eines Rings zeigt,
    setzt die Mündung genau auf den Rand der Hülle, und die Kreisscheibe ragt
    rechnerisch darüber hinaus — obwohl sie ringsum im Material sitzt.
    Gemessen an drei Körpern: Zylinder Ø 30 (239,76 mm³ abgetragen), Kugel
    Ø 40 (319,75 mm³) und Torus R20/r6 (177,07 mm³), alle drei danach
    wasserdicht und einteilig, alle drei mit dieser Warnung (Befund Robert,
    09.09.2026: „das Bohrung setzen über den Viewport ist noch ziemlich
    buggy").

    Eine Warnung, die bei jedem runden Teil kommt, ist der Lärm, nach dem
    niemand mehr in den Prüfbericht sieht. Wo ein Netz vorliegt, entscheidet
    deshalb :func:`_flank_is_open`; ohne eines — der exakte Kern reicht einen
    ``Solid`` herein — bleibt es beim Hüllquader, und der ist dort zu streng
    und nie zu milde.

    **Und wo die Scheibe im Hüllquader bleibt, entscheidet mit ``reach`` das
    Netz** (RM-249): ``reach`` ist die Länge der Bohrung von ``position`` aus —
    an ihrer Mündung ihre Tiefe, an ihrer Mitte die halbe
    (:func:`_flank_opens_within`). Ohne ``reach`` bleibt es beim Hüllquader.
    ``along`` ist der Weg von ``position`` zur Mitte der Bohrung entlang
    ``direction``: Wer an der Mündung fragt, gibt die halbe Tiefe ins Material
    mit, und ``reach`` ist dann die halbe Länge. Sonst lägen die Tiefen vor der
    Mündung in der Luft davor, wo neben einer Wand Material steht, das die
    Bohrung nie berührt (Durchsicht 0.5.1, BOHRUNG-01). ``old_opening`` ist der
    Raum einer alten Öffnung, die der Schnitt überdeckt, ohne dass sie vorher
    geschlossen wurde (:class:`OpeningSpace`).
    """
    vector = np.asarray(direction, dtype=float)
    # ``math.hypot`` statt ``np.linalg.norm``: Letzteres geht durch BLAS, und
    # dessen Ergebnis haengt von der Maschine ab (RM-187). Hier normiert es
    # eine Richtung, aus der gleich eine Drehmatrix fuer das ganze Netz wird.
    length = math.hypot(float(vector[0]), float(vector[1]), float(vector[2]))
    if length <= EPS_GEOM:
        return []
    unit = vector / length
    radius = diameter / 2.0
    over = _axes_over(mesh, position, unit, radius)
    if not over:
        if body is None or reach is None:
            return []
        middle = np.asarray(position, dtype=float) + unit * along
        within = _flank_opens_within(
            body,
            (float(middle[0]), float(middle[1]), float(middle[2])),
            unit,
            radius,
            reach,
            old_opening,
        )
        return [_edge_finding(diameter, within)] if within else []
    if body is not None and not _flank_is_open(body, position, unit, radius, old_opening):
        return []
    return [_edge_finding(diameter, over)]


def mouth_over_the_edge(
    body: MeshData,
    position: Vec3,
    inward: Vec3,
    diameter: float,
    *,
    cone: tuple[Vec3, float] | None = None,
) -> list[Finding]:
    """Ob eine **Mündung** an dieser Stelle aufreißt — die Frage für den Austritt
    einer gekippten Bohrung.

    :func:`over_the_edge_along` fragt die ganze Länge und ist zufrieden, wenn
    der Kranz **irgendwo** ringsum im Material liegt; eine um 60° gedrehte
    Bohrung durch eine 20 mm starke Platte steckt in der Mitte tief im
    Material und tritt unten trotzdem 2,3 mm neben der Platte aus (Fund des
    Reviews, 15.09.2026). Hier zählt nur der Abschnitt **unmittelbar hinter der
    Mündung**, bis einen halben Radius tief: Liegt der Kranz dort an keiner
    Tiefe vollständig im Material, ist die Flanke an dieser Mündung offen. Eine
    gerade Bohrung in eine ebene oder gewölbte Fläche hat den Kranz nach einem
    halben Radius rundum im Material und meldet nichts — die um 60° gedrehte
    Bohrung nicht: Ihre Wand tritt bis 2,3 mm hinter dem Austritt aus der
    Seitenfläche, und ab drei Millimetern läge sie wieder ringsum im Material,
    was :func:`_flank_is_open` über die ganze Länge zufriedenstellte.

    ``inward`` zeigt von der Mündung in den Körper.

    **Der Kranz liegt in der Fläche, aus der die Bohrung kommt** (22.09.2026).
    Hier stand der Kreis quer zur Achse, und der passt nur zu einer Mündung
    quer zur Achse: Eine schräge Bohrung mündet als Ellipse in einer ebenen
    Platte, und ihr Querkreis ragt dort an der hohen Seite über die Fläche —
    an einer um 45° gekippten Bohrung mitten in einer 10-mm-Platte auch einen
    halben Radius tief noch um 1,1 mm. Jede schräge Bohrung, die versetzt oder
    gedreht wurde, meldete damit „über die Kante". Der Kranz ist deshalb die
    Mündungsellipse in der getroffenen Fläche, einen viertel und einen halben
    Radius entlang der Achse ins Material geschoben; die um 60° gedrehte
    Bohrung, die unten neben der Platte austritt, hat ihre Ellipse dort zur
    Hälfte in der Luft und meldet es weiter.

    **Eine Senkung mündet mit ihrem Kegel, nicht mit einem Zylinder**
    (``cone``: Spitze und halber Öffnungswinkel; Durchsicht seit 0.5.0,
    25.09.2026). Ihr Kranz ist der Schnitt des Kegels mit der Mündungsfläche —
    je Mantellinie von der Spitze bis in die Fläche, nicht parallel zur Achse.
    Gekippt liegt eine Flanke flach, und der Schnitt reicht weit über den
    Kreis hinaus: An einer Platte 30 x 24 x 12 schnitt eine um 30° gekippte
    Senkbohrung Ø 10 22,6 mm² aus der Seitenfläche, an beiden Kernen, und der
    Kreis sah ringsum Material; von einer Kante weg gekippt, meldete er eine
    offene Flanke, die es nicht gab. Ohne Mündungsfläche bleibt es beim Kreis.
    """
    vector = np.asarray(inward, dtype=float)
    length = float(np.linalg.norm(vector))
    radius = diameter / 2.0
    if length <= EPS_GEOM or radius <= EPS_GEOM:
        return []
    unit = vector / length
    section = None if cone is None else _cone_section(body, position, unit, cone)
    if section is not None:
        mouth, rim, over = section
        if not over:
            return []
    else:
        over = _axes_over(body, position, unit, radius)
        if not over:
            return []
        rim = _rim_around(unit, radius)
        mouth = np.asarray(position, dtype=float)
        face = _mouth_face(body, mouth, unit)
        if face is not None:
            mouth, normal = face
            # Je Kranzpunkt entlang der Achse bis in die Ebene der Mündungsfläche.
            rim = rim - np.outer((rim @ normal) / float(normal @ unit), unit)
    from app.core.geom.mesh import on_surface

    depths = radius * np.asarray(_MOUTH_DEPTHS, dtype=float)
    samples = mouth + rim[None, :, :] + depths[:, None, None] * unit
    flat = samples.reshape(-1, 3)
    closest, _distance, triangle = on_surface(body.raw, flat, index=surface_index_of(body))
    normals = np.asarray(body.raw.face_normals)[triangle]
    outward = np.einsum("ij,ij->i", flat - closest, normals)
    inside = (outward <= EPS_GEOM).reshape(len(depths), _RIM_POINTS)
    if bool(inside.all(axis=1).any()):
        return []
    return [_edge_finding(diameter, over)]


def ray_hits_along(
    triangles: np.ndarray,
    origin: Any,
    direction: Any,
    *,
    minimum_travel: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """:func:`~app.core.geom.mesh.ray_hits` für einen einzelnen Strahl an einem
    großen Netz — mit denselben Treffern, aber nur gegen die Dreiecke gerechnet,
    deren Schatten quer zum Strahl seinen Weg umschließt.

    **Ein Strahl gegen alle Dreiecke war die teuerste Zeile beim Versetzen**
    (Durchsicht 0.5.1): Die Austritte der Achse (``prepare_ops._axis_exits``)
    und der Mündungspunkt (:func:`_mouth_face`) schossen am
    Gartenschlauchhalter (392 532 Dreiecke) je Strahl 0,15 s Möller-Trumbore
    über das ganze Netz, fast eine Sekunde je Schritt. Ein Dreieck, das der
    Strahl trifft, enthält den Treffer; in der Ebene quer zum Strahl liegt der
    Treffer auf dem Fußpunkt des Ursprungs, und dieser Punkt liegt dann im
    Rechteck, das das Dreieck dort wirft. Die Vorauswahl fragt genau das,
    mit :data:`~app.core.units.EPS_GEOM` Spiel — weit über dem baryzentrischen
    Rand von ``ray_hits``. Gerechnet wird jedes ausgewählte Dreieck mit
    denselben Zahlen wie im Vollvergleich, und die Nummern kommen in derselben
    Reihenfolge zurück: gleiche Bits, gleicher erster Treffer (RM-187). Die
    Projektion ist elementweise, ohne BLAS.
    """
    from app.core.geom.mesh import ray_hits

    triangles = np.asarray(triangles, dtype=np.float64)
    if len(triangles) < _ALONG_ABOVE:
        return ray_hits(triangles, origin, direction, minimum_travel=minimum_travel)
    start = np.asarray(origin, dtype=np.float64).reshape(3)
    way = np.asarray(direction, dtype=np.float64).reshape(3)
    length = math.hypot(float(way[0]), float(way[1]), float(way[2]))
    if length <= EPS_GEOM:
        return ray_hits(triangles, origin, direction, minimum_travel=minimum_travel)
    ring = _rim_around(way / length, 1.0)
    first, second = ring[0], ring[len(ring) // 4]
    keep = np.ones(len(triangles), dtype=bool)
    for across in (first, second):
        # Der Fußpunkt des Ursprungs als Zahl statt als Feld: Die Vorauswahl
        # ist ein Sieb mit Spiel, kein Treffer, und ein Rundungsunterschied
        # von 1e-14 gegen ``EPS_GEOM`` entscheidet nichts.
        foot = units.dot3(start, across)
        shade = (
            triangles[:, :, 0] * across[0]
            + triangles[:, :, 1] * across[1]
            + triangles[:, :, 2] * across[2]
        )
        keep &= (shade.min(axis=1) <= foot + EPS_GEOM) & (shade.max(axis=1) >= foot - EPS_GEOM)
    chosen = np.flatnonzero(keep)
    distances, hit = ray_hits(triangles[chosen], start, way, minimum_travel=minimum_travel)
    return distances, chosen[hit]


#: Ab wie vielen Dreiecken :func:`ray_hits_along` vorauswählt; darunter kostet
#: die Projektion mehr, als sie spart.
_ALONG_ABOVE: Final = 20_000


def _mouth_face(
    body: MeshData, position: np.ndarray, inward: np.ndarray
) -> tuple[np.ndarray, np.ndarray] | None:
    """Wo die Achse von ``position`` aus in den Körper eintritt: Punkt und Flächennormale.

    Gemessen mit einem Strahl, exakt und ohne Raumindex
    (:func:`~app.core.geom.mesh.ray_hits`), angesetzt einen Radius vor der
    Stelle, damit eine Mündung, die genau auf ihr liegt, getroffen wird.
    ``None``, wo der Strahl nichts trifft oder die Fläche fast längs der Achse
    liegt — dann bleibt es beim Kreis quer zur Achse.
    """
    triangles = np.asarray(body.raw.triangles, dtype=float)
    if not len(triangles):
        return None
    back = float(body.bounds.diagonal) * 1e-3 + EPS_DISPLAY
    start = position - inward * back
    distances, hit = ray_hits_along(triangles, start, inward)
    if not len(distances):
        return None
    first = int(np.argmin(distances))
    normal = np.asarray(body.raw.face_normals[int(hit[first])], dtype=float)
    if abs(float(normal @ inward)) <= 0.1:
        return None
    return start + inward * float(distances[first]), normal


def _cone_section(
    body: MeshData, position: Vec3, unit: np.ndarray, cone: tuple[Vec3, float]
) -> tuple[np.ndarray, np.ndarray, list[str]] | None:
    """Der Schnitt eines Senkungskegels mit seiner Mündungsfläche: Mündungspunkt,
    Kranz relativ zu ihm und die Achsen, über deren Hüllquader er ragt.

    ``cone`` ist die Spitze und der halbe Öffnungswinkel in Grad, ``unit``
    die Achse in den Körper. Je Punkt des Kranzes eine Mantellinie, von der
    Spitze nach außen bis in die Ebene der Mündungsfläche. Zwei der Linien
    liegen in der Ebene aus Achse und Flächennormale, denn dort reicht ein
    gekippter Kegel am weitesten: flach auf der einen, steil auf der anderen
    Seite. ``None``, wo die Fläche fehlt, die Spitze nicht hinter ihr liegt
    oder eine Mantellinie die Fläche nie erreicht — dann bleibt es beim Kreis.
    Gerechnet elementweise und mit den Winkelfunktionen aus ``units``
    (RM-187): Aus dem Kranz wird ein Befund.
    """
    face = _mouth_face(body, np.asarray(position, dtype=float), unit)
    if face is None:
        return None
    mouth, normal = face
    apex, half_angle = cone
    tip = np.asarray(apex, dtype=float)
    across = normal - unit * units.dot3(normal, unit)
    width = math.hypot(float(across[0]), float(across[1]), float(across[2]))
    if width <= EPS_GEOM:
        # Die Achse steht senkrecht auf der Fläche: Jede Richtung ist gleich.
        directions = _rim_around(unit, 1.0)
    else:
        first = across / width
        second = np.cross(unit, first)
        table = np.asarray(units.circle_cos_sin(_RIM_POINTS), dtype=float)
        directions = table[:, 0][:, None] * first + table[:, 1][:, None] * second
    lines = directions * units.exact_sin_degrees(half_angle) - unit * units.exact_cos_degrees(
        half_angle
    )
    rise = lines[:, 0] * normal[0] + lines[:, 1] * normal[1] + lines[:, 2] * normal[2]
    height = units.dot3(mouth - tip, normal)
    if height <= EPS_GEOM or not bool(np.all(rise > EPS_GEOM)):
        return None
    points = tip + lines * (height / rise)[:, None]
    lower = np.asarray(body.bounds.minimum, dtype=float)
    upper = np.asarray(body.bounds.maximum, dtype=float)
    over = [
        name
        for index, name in enumerate("xyz")
        if bool(np.any(points[:, index] < lower[index] - EPS_GEOM))
        or bool(np.any(points[:, index] > upper[index] + EPS_GEOM))
    ]
    return mouth, points - mouth, over


#: An welchen Tiefen hinter einer Mündung :func:`mouth_over_the_edge` den Kranz
#: abfragt — in Vielfachen des Radius, bis einen halben Radius tief. Tiefer
#: gefragt wäre die Antwort die von :func:`_flank_is_open`: irgendwo ringsum
#: Material, also geschlossen — auch an einer Mündung, die aufgerissen ist.
_MOUTH_DEPTHS: Final = (0.25, 0.5)


def _axes_over(mesh: HasBounds, position: Vec3, unit: Any, radius: float) -> list[str]:
    """Die Achsen, entlang derer die Mündungsscheibe über den Hüllquader ragt."""
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
    return over


def _rim_around(unit: Any, radius: float) -> np.ndarray:
    """Ein Kranz von :data:`_RIM_POINTS` Punkten auf dem Umfang quer zur Achse."""
    axis = np.asarray(unit, dtype=float)
    helper = np.array([0.0, 0.0, 1.0]) if abs(float(axis[2])) < 0.9 else np.array([1.0, 0.0, 0.0])
    first = np.cross(axis, helper)
    first /= float(np.linalg.norm(first))
    second = np.cross(axis, first)
    # Der Kranz ist ein regelmaessiges Vieleck; seine Ecken kommen aus
    # Ganzzahlen und sind damit auf jeder Maschine dieselben (RM-187).
    table = np.asarray(units.circle_cos_sin(_RIM_POINTS), dtype=float)
    return np.asarray(radius * (table[:, 0][:, None] * first + table[:, 1][:, None] * second))


def _edge_finding(diameter: float, over: list[str]) -> Finding:
    """Der eine Satz für eine Bohrung über der Kante — von jeder Stelle gleich."""
    return Finding(
        code="bore.over_the_edge",
        severity="warning",
        message=_(
            "Die Bohrung ragt seitlich über den Körper hinaus — sie trägt nur "
            "teilweise ab und lässt eine offene Flanke zurück."
        ),
        values={"axes": ", ".join(over), "diameter": format_length(diameter)},
        # Regel 17: Der Knopf öffnet den Schritt, dessen Stelle über den Rand führt.
        suggestions=(CORRECT_INPUT,),
    )


def split_findings(before: HasComponents, after: HasComponents) -> list[Finding]:
    """Ein Schnitt, der den Körper zerlegt, sagt das — nicht nur „über die Kante".

    Gemessen am 11.09.2026 und am 13.09.2026 nachgestellt: Ein Langloch von
    100 mm durch einen 20-mm-Würfel ließ zwei Teile zurück, und der Bericht
    sprach von einer offenen Flanke — die schlechtere Auskunft, nicht die
    fehlende (Fund des Reviews). Die Teilezahl liegt an beiden Kernen vor,
    und sie lügt nicht.
    """
    was, now = before.component_count, after.component_count
    if now <= was:
        return []
    return [
        Finding(
            code="bore.splits_the_body",
            severity="warning",
            message=_(
                "Die Bohrung schneidet den Körper ganz durch — er zerfällt in mehrere "
                "Teile. Verkürzen Sie die Länge oder versetzen Sie die Bohrung."
            ),
            values={"count": now},
            # Regel 17: Länge oder Stelle, die der Satz nennt, stehen im Schritt.
            suggestions=(CORRECT_INPUT,),
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
    end_planes: tuple[SectionPlane, ...] = (),
    cancelled: CancelToken | None = None,
    object_id: ObjectId | None = None,
) -> BoreResult:
    """Ändert eine erkannte zylindrische Bohrung in genau einem Booleschritt.

    Größer heißt: einen weiteren Zylinder abtragen. Ein kleinerer Durchmesser
    erzeugt hier einen Füllring. Der Operationsweg darf einen topologisch
    belegten Hohlraum zuvor schließen und mit ``previous_diameter=0`` neu
    schneiden. Das vermeidet nahezu koplanare Füllflächen am Sacklochboden.
    Mittelpunkt, freie Achse und Tiefe kommen aus dem erkannten Merkmal;
    ``end_planes`` begrenzen den Werkzeugkörper an seinen wirklichen Rändern.

    ``compensate`` steht hier absichtlich auf ``False``. Der Ausgangswert im
    Dialog ist ein **gemessenes** Maß und kein Nenndurchmesser. Wer ihn
    unverändert bestätigt, darf nicht allein durch eine noch einmal
    aufgeschlagene Materialtoleranz eine andere Bohrung bekommen.
    """
    if not math.isfinite(depth) or depth <= EPS_GEOM:
        raise bore_geometry_error()
    cut_diameter = bore_diameter(diameter, profile, compensate)
    if is_close(cut_diameter, previous_diameter):
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
    # ``math.hypot`` statt ``np.linalg.norm``: Letzteres geht durch BLAS, und
    # dessen Ergebnis haengt von der Maschine ab (RM-187). Hier normiert es
    # eine Richtung, aus der gleich eine Drehmatrix fuer das ganze Netz wird.
    length = math.hypot(float(vector[0]), float(vector[1]), float(vector[2]))
    if not math.isfinite(length) or length <= EPS_GEOM:
        raise bore_geometry_error()
    unit = vector / length
    grows = cut_diameter > previous_diameter
    # Nur ein abziehendes Werkzeug darf über beide Mündungen hinausragen.
    # Beim Verkleinern wird der Ring vereinigt; dieselbe Zugabe würde dann an
    # beiden Außenseiten als tastbarer Kragen Teil des Modells werden.
    height = depth + (BOOLEAN_OVERLAP * 2.0 if through and grows else 0.0)
    to_world = np.asarray(
        transform.rotation_between(np.array([0.0, 0.0, 1.0]), unit),
        dtype=float,
    )
    to_world[:3, 3] = np.asarray(position, dtype=float)

    kind: BooleanKind
    if grows:
        tool = lathe.cylinder(
            radius=cut_diameter / 2.0,
            height=height,
            sections=BORE_SECTIONS,
        )
        kind = "difference"
    else:
        # Das umschriebene Vieleck erreicht auch bei großen Bohrungen die
        # alte Wand. Die zentrale Überlappung allein deckt seine Sehnenlücke
        # nicht für jeden Radius und jede fremde Winkelunterteilung ab.
        tool = lathe.annulus(
            r_min=cut_diameter / 2.0,
            r_max=previous_diameter / (2.0 * units.inscribed_ratio(BORE_SECTIONS))
            + BOOLEAN_OVERLAP,
            height=height,
            sections=BORE_SECTIONS,
        )
        kind = "union"
    capped: list[tuple[np.ndarray, SectionPlane]] = []
    if end_planes:
        # Die beiden Randebenen begrenzen jeden Umfangspunkt einzeln. Eine
        # senkrechte Werkzeugkappe auf Höhe des höchsten alten Randpunkts
        # ließe beim Vergrößern einer schrägen Mündung eine Materiallippe
        # stehen. An einem Sacklochboden bleibt die gemessene Ebene erhalten.
        vertices = np.asarray(tool.vertices, dtype=float).copy()
        upper = vertices[:, 2] > 0.0
        turn = to_world[:3, :3]
        for plane in end_planes:
            # **Elementweise, nicht über ``@`` und ``np.dot``** (RM-187): Beide
            # gehen durch BLAS, und dessen Rundung hängt an der Maschine —
            # hier wird aus dem Ergebnis die Höhe jeder Werkzeugecke.
            normal = tuple(
                units.dot3((turn[0, column], turn[1, column], turn[2, column]), plane.normal)
                for column in range(3)
            )
            if abs(normal[2]) <= EPS_GEOM:
                raise bore_geometry_error()
            position_in_bore = plane.position - units.dot3(plane.normal, position)
            selected = upper if normal[2] > 0.0 else ~upper
            vertices[selected, 2] = (
                position_in_bore
                - (vertices[selected, 0] * normal[0] + vertices[selected, 1] * normal[1])
            ) / normal[2]
            capped.append((selected, plane))
        tool.vertices = vertices
    # **Das Werkzeug wandert in die Welt, nicht der Körper in den Rahmen**
    # (RM-274, der Weg aus RM-187). Bis zur Durchsicht 0.5.1 lag hier der ganze
    # Körper im Rahmen der Bohrung und danach wieder in der Welt, und die
    # Rundung beider Wege versetzte jede Ecke, die der Schnitt nicht berührt.
    # Die Kappen auf den gemessenen Randebenen legt :func:`_onto_planes` in der
    # Welt so genau auf ihre Ebene, wie ``float`` es erlaubt — eine
    # achsparallele Mündung trifft sie damit Bit für Bit.
    transform.moved(tool, to_world)
    if capped:
        tool.vertices = _onto_planes(np.asarray(tool.vertices, dtype=np.float64), capped)
    outcome = boolean(
        kind,
        [mesh, MeshData.of(tool)],
        quality=quality,
        seed=seed,
        cancelled=cancelled,
        object_ids=(object_id, None),
    )
    resized = outcome.mesh
    findings = list(outcome.findings)
    nothing = without_effect(mesh, resized, kind, profile)
    if nothing is not None:
        findings.append(nothing)
    unit_vector: Vec3 = (float(unit[0]), float(unit[1]), float(unit[2]))
    findings.extend(
        over_the_edge_along(mesh, position, unit_vector, cut_diameter, body=mesh, reach=depth / 2.0)
    )
    findings.extend(split_findings(mesh, resized))
    findings.extend(compensation_findings(diameter, cut_diameter, compensate))
    return BoreResult(
        mesh=resized,
        solver=outcome.solver,
        diameter=cut_diameter,
        findings=findings,
        cutting_tool=MeshData.of(tool) if grows else None,
    )


def _onto_planes(
    vertices: np.ndarray, capped: Sequence[tuple[np.ndarray, SectionPlane]]
) -> np.ndarray:
    """Die gewählten Ecken genau auf ihre Ebene legen, entlang der steilsten Weltachse.

    Ein Werkzeug, dessen Kappe im Rahmen der Bohrung auf einer Randebene lag,
    liegt nach dem Weg in die Welt nur bis auf die Rundung darauf. Aufgelöst
    wird nach der Koordinate, in der die Ebene am steilsten steht: Bei einer
    achsparallelen Ebene ist das genau ihre Lage, die Kappe fällt Bit für Bit
    in die Fläche des Körpers; bei einer schrägen rückt die Ecke um weniger als
    eine Rundung. Grundrechenarten in fester Folge (RM-187).
    """
    placed = np.array(vertices, dtype=np.float64, copy=True)
    for selected, plane in capped:
        normal = [float(value) for value in plane.normal]
        steepest = max(range(3), key=lambda index: abs(normal[index]))
        others = [index for index in range(3) if index != steepest]
        rest = (
            placed[selected, others[0]] * normal[others[0]]
            + placed[selected, others[1]] * normal[others[1]]
        )
        placed[selected, steepest] = (float(plane.position) - rest) / normal[steepest]
    return placed


#: Wieviel größer der Körper gebaut wird, der ein gemessenes Merkmal ausfüllt,
#: abträgt oder auseinanderzieht — am **Durchmesser**, wie jedes Maß im Haus.
#:
#: **Die Zahl stand bis zum 10.09.2026 zweimal da**, hier und als
#: ``SLOT_OVERLAP`` daneben, beide 0,02 und beide mit dem Vermerk „dieselbe
#: Zahl, derselbe Grund". Genau diese Form hat ``BOOLEAN_OVERLAP`` schon
#: einmal gekostet (siehe dort): Zwei Stellen, die gleich bleiben *müssen*,
#: bleiben es nicht.
#:
#: **Und der Grund ist nicht der, der lange dabeistand.** Koplanare Flächen
#: rechnet ``manifold3d`` robust — neun Lagen mit 0,05, 0,01 und 0,0 liefen
#: alle über Stufe 1 (gemessen 27.08.2026, ``boolean.BOOLEAN_OVERLAP``). Was
#: die Zugabe hier wirklich verhindert, ist ein **Tangentialkontakt**: Der
#: Langlochkörper legte sich sonst entlang zweier Linien an die alte
#: Bohrungswand, und die zwei Bögen säßen exakt darauf. Beim Ausfüllen eines
#: Merkmals ist es dieselbe Lage, nur andersherum.
#:
#: Nebenbei deckt sie das Vieleck, zu dem ein Umriss abgetastet wird: bei Ø 5
#: sind das 2,4 Mikrometer am Radius gegen 10 Mikrometer Zugabe am Radius —
#: der Vergleich gilt für beide dieselbe Größe, und das ist nicht
#: selbstverständlich (``.claude/rules/operationen.md``, „Toleranzen sind
#: Durchmessermaße").
FEATURE_OVERLAP: Final = 0.02


def slot_bore(
    mesh: MeshData,
    *,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
    through: bool,
    length: float,
    angle_deg: float,
    profile: Profile,
    overlap: float,
    quality: Quality = "fine",
    seed: int | None = None,
    cancelled: CancelToken | None = None,
    object_id: ObjectId | None = None,
    old_opening: OpeningSpace | None = None,
) -> BoreResult:
    """Zieht eine erkannte Bohrung zu einem Langloch auseinander.

    Ein Schritt und eine Boolesche: Der Langlochkörper deckt die vorhandene
    Bohrung mit ab, also ist alles, was übrig bleibt, das seitlich neu
    abgetragene Material. ``position``, ``direction``, ``diameter`` und
    ``depth`` kommen aus dem erkannten Merkmal und werden nicht verändert —
    eingetragen hat der Kunde nur Länge und Richtung.

    **Die Materialtoleranz bleibt hier draußen.** ``diameter`` ist ein
    *gemessenes* Maß und kein Nenndurchmesser; sie ein zweites Mal
    aufzuschlagen machte aus einer Formänderung eine Maßänderung. Dieselbe
    Entscheidung wie bei :func:`resize_bore`.

    ``overlap`` ist eine Zugabe auf den Durchmesser, und **der Aufrufer sagt
    sie**, wie am exakten Zwilling :func:`app.core.brep.edit.slot_bore` —
    eine Vorgabe gibt es nicht. Bis zum 29.09.2026 stand hier
    :data:`FEATURE_OVERLAP`: Sie hielt den Körper von einer runden Bohrungswand
    fern, an der er sich sonst entlang zweier Linien anlegte. Seit jeder Zug
    die alte Öffnung vorher schließt, gibt es diese Wand nicht mehr, und jeder
    Aufrufer gibt ``0.0`` — mit der Zugabe wuchs die Breite bei **jedem** Zug
    (gemessen 11.09.2026: 5,2057, 5,2213, 5,2371 an einem Loch, das 5,1901
    gemessen war). ``BoreResult.diameter`` nennt den geschnittenen Durchmesser,
    samt Zugabe; bis dahin meldete es ``diameter``.

    **Und eine Länge gleich dem Durchmesser schneidet rund** (24.09.2026): So
    kommt ein Langloch, das bis auf seine Breite zurückgezogen wurde, wieder
    als Bohrung heraus — mit demselben 48-Eck (:data:`BORE_SECTIONS`), mit dem
    jede Bohrung am Netz geschnitten wird. Der Aufrufer schließt die alte
    Öffnung vorher; hier wird nur geschnitten.
    """
    from app.core.geom.sketch_solid import extrude_profile

    round_bore = is_close(length, diameter)
    travel = 0.0 if round_bore else slot_travel(diameter=diameter, length=length)
    if travel <= EPS_GEOM and not round_bore:
        # Nur eine Länge von null kommt hier an — ``slot_travel`` liest sie als
        # „rund" und lehnt alles andere unter der Grenze selbst ab. Der Satz
        # verspricht die Mindestlänge darunter; also steht sie auch hier.
        raise ValidationError(
            field="slot_length",
            constraint="slot_proportion",
            detail=SLOT_TOO_SHORT,
            value=length,
            values={"shortest": format_length(shortest_slot(diameter))},
        )
    vector = np.asarray(direction, dtype=float)
    # ``math.hypot`` statt ``np.linalg.norm`` (BLAS, RM-187): Aus der Länge
    # wird die Achse, und aus der Achse der Rahmen des Werkzeugs.
    span = math.hypot(float(vector[0]), float(vector[1]), float(vector[2]))
    if not math.isfinite(span) or span <= EPS_GEOM:
        raise bore_geometry_error()
    if not math.isfinite(depth) or depth <= EPS_GEOM:
        raise bore_geometry_error()
    unit = vector / span
    axis: Vec3 = (float(unit[0]), float(unit[1]), float(unit[2]))
    # Der Rahmen des Winkels (:func:`slot_frame`): Eine gemessene Achse im
    # Rauschen neben einer Hauptachse zählt gegen die Hauptachse.
    frame = slot_frame(axis, position)
    # **Derselbe Rahmenbau wie beim Bohren, und trotzdem nicht immer dieselbe
    # Zahl.** Der Rahmen spiegelt seine erste Achse, wenn die Normale kippt
    # (das Kreuzprodukt aus Z und ihr) — und ``drill`` bekommt die Normale der
    # **Fläche**, die Erkennung dagegen eine Achse, deren größte Komponente sie
    # auf positiv normiert. Gemessen an derselben Platte mit 45 Grad: von oben
    # gebohrt 45 Grad, von unten gebohrt 135; an der erkannten Bohrung beide
    # Male 45. Der Winkel zählt hier also gegen den Rahmen der **gemessenen**
    # Achse und ist damit seitenunabhängig — was richtig ist, denn eine
    # erkannte Bohrung hat zwei Mündungen, und welche gemeint ist, hat niemand
    # gesagt (Regel 21).

    # Nur ein durchgehendes Loch darf über beide Mündungen hinausragen. Bei
    # einer Blindbohrung bliebe der Boden sonst nicht, wo er gemessen wurde —
    # dieselbe Abwägung wie in :func:`resize_bore`. Ein Ende, das in einer
    # Fläche mit Luft dahinter liegt — die Mündung —, reicht dagegen um die
    # Zugabe hinaus (:func:`_open_ends`): Das Werkzeug liegt in der Welt, und
    # dort trifft es eine schräge Fläche nicht genau.
    height = depth + (BOOLEAN_OVERLAP * 2.0 if through else 0.0)
    radius = (diameter + overlap) / 2.0
    below = above = False
    if not through:
        reach = radius + travel / 2.0
        below, above = _open_ends(
            mesh,
            _heights(mesh, frame),
            frame,
            ((-height / 2.0, -1.0, reach), (height / 2.0, 1.0, reach)),
        )
    low = -height / 2.0 - (BOOLEAN_OVERLAP if below else 0.0)
    high = height / 2.0 + (BOOLEAN_OVERLAP if above else 0.0)
    if round_bore:
        tool = lathe.cylinder(radius=radius, height=high - low, sections=BORE_SECTIONS)
        if below or above:
            tool.apply_translation((0.0, 0.0, (high + low) / 2.0))
    else:
        tool = extrude_profile(
            slot_profile(radius=radius, travel=travel, angle_deg=angle_deg),
            high - low,
            PlaneFrame(
                origin=(0.0, 0.0, low),
                x_axis=(1.0, 0.0, 0.0),
                y_axis=(0.0, 1.0, 0.0),
                normal=(0.0, 0.0, 1.0),
            ),
        )
    # **Das Werkzeug wandert in die Welt, nicht der Körper in den Rahmen**
    # (RM-274): derselbe Umbau wie beim Bohren, und aus demselben Grund — der
    # Hin- und Rückweg des ganzen Körpers versetzte jede Ecke, die das
    # Langloch nicht berührt.
    transform.moved(tool, _in_world(frame))
    outcome = boolean(
        "difference",
        [mesh, MeshData.of(tool)],
        quality=quality,
        seed=seed,
        cancelled=cancelled,
        object_ids=(object_id, None),
    )
    slotted = outcome.mesh
    findings = list(outcome.findings)
    nothing = without_effect(mesh, slotted, "difference", profile)
    if nothing is not None:
        findings.append(nothing)
    findings.extend(
        edge_findings(
            mesh,
            position=position,
            frame=frame,
            diameter=diameter + overlap,
            travel=travel,
            angle_deg=angle_deg,
            reach=depth / 2.0,
            old_opening=old_opening,
        )
    )
    findings.extend(split_findings(mesh, slotted))
    return BoreResult(
        mesh=slotted,
        solver=outcome.solver,
        diameter=diameter + overlap,
        findings=findings,
    )


def drill_outline(
    *,
    diameter: float,
    depth: float,
    profile: Profile,
    compensate: bool = True,
    widening_diameter: float = 0.0,
    widening_depth: float = 0.0,
    transition_angle: float = 90.0,
    mouth_overlap: float = 0.0,
) -> list[tuple[float, float]]:
    """Gemeinsamer Schneidkörper zwischen Mündung null und exakt -depth.

    Der Boden liegt exakt bei ``-depth`` — eine Blindbohrung ist so tief, wie
    sie eingegeben wurde, auch beim historischen Mittenanker. An der Mündung
    darf der Aufrufer mit ``mouth_overlap`` über null hinausreichen: Endet das
    Werkzeug genau auf der angeklickten Fläche, fallen zwei Flächen zusammen,
    und genau davor schützt :data:`BOOLEAN_OVERLAP` in der Rückfallkette. Die
    Zugabe schneidet Luft und ändert kein Maß. Durchgangsaufrufer wählen
    ausdrücklich eine Tiefe über die Körpergrenze hinaus; Vorschau und
    Operation teilen den Körper.
    """
    if not math.isfinite(mouth_overlap) or mouth_overlap < 0.0:
        raise ValidationError(
            field="depth",
            detail=_("Die Mündungszugabe des Werkzeugs muss null oder positiv sein."),
            constraint="positive",
        )
    if not math.isfinite(depth) or depth <= EPS_GEOM:
        raise ValidationError(
            field="depth",
            detail=_("Wählen Sie eine positive Bohrtiefe für den Werkzeugkörper."),
            constraint="positive",
        )
    radius = bore_diameter(diameter, profile, compensate) / 2.0
    if (
        not math.isfinite(widening_diameter)
        or widening_diameter < 0.0
        or widening_diameter > EPS_GEOM
    ):
        if (
            not all(
                math.isfinite(value)
                for value in (widening_diameter, widening_depth, transition_angle)
            )
            or widening_diameter <= diameter + EPS_GEOM
            or widening_depth < 0.0
            or not 0.0 < transition_angle <= 180.0
        ):
            raise ValidationError(
                field="widening_diameter",
                constraint="minimum",
                detail=_(
                    "Die Aufweitung muss breiter als die Bohrung sein. "
                    "Prüfen Sie Durchmesser, Tiefe und Übergangswinkel."
                ),
            )
        wide_radius = bore_diameter(widening_diameter, profile, compensate) / 2.0
        # Die Länge des Übergangs über den Kotangens aus den exakten
        # Winkelfunktionen (RM-187), nicht über ``math.tan``: Aus ihr wird ein
        # Ring des Werkzeugs, und ``math.tan`` rundet je Mathematikbibliothek
        # anders. Bei 180 Grad ist der Kosinus genau null, die Schulter flach.
        half = transition_angle / 2.0
        transition = (
            (wide_radius - radius) * units.exact_cos_degrees(half) / units.exact_sin_degrees(half)
        )
        if widening_depth + transition >= depth - EPS_GEOM:
            raise ValidationError(
                field="depth",
                constraint="maximum",
                detail=_(
                    "Aufweitung und Übergang reichen tiefer als die Bohrung. "
                    "Vergrößern Sie die Bohrtiefe oder verkleinern Sie die Aufweitung."
                ),
            )
        # Ein geschlossener Rotationskörper erhält gemeinsame Ringe zwischen
        # engem Schaft, Übergang und Aufweitung auch nach dem Booleschen Schnitt.
        outline = [
            (0.0, -depth),
            (radius, -depth),
            (radius, -widening_depth - transition),
            (wide_radius, -widening_depth),
            (wide_radius, mouth_overlap),
            (0.0, mouth_overlap),
            (0.0, -depth),
        ]
        return outline
    return [
        (0.0, -depth),
        (radius, -depth),
        (radius, mouth_overlap),
        (0.0, mouth_overlap),
        (0.0, -depth),
    ]


#: Ein Langloch trägt keine Aufweitung — die Absage, die beide Kerne teilen.
#:
#: Eine Senkung über einem Langloch wäre entweder rund, dann säße ein
#: Schraubenkopf nur in der Mitte versenkt, oder selbst ein Langloch, und dann
#: bliebe offen, welche der beiden Längen gemeint ist. Solange die Frage nicht
#: gestellt ist, wird sie nicht geraten (Regel 21).
SLOT_AND_WIDENING: Final = _(
    "Ein Langloch und eine Aufweitung gehen nicht zusammen. Setzen Sie die "
    "Aufweitung auf null, oder lassen Sie die Bohrung rund."
)

#: Was ein Langloch von einer runden Bohrung unterscheidet — und die Grenze,
#: unterhalb derer es keines ist.
#:
#: **Nicht derselbe Satz wie bei der Skizzen-Grundform**, obwohl es hier lange
#: so dastand: :func:`app.core.sketch.shapes.slot` sagt „länger als breit —
#: sonst ist es ein Kreis". Dort zeichnet jemand einen Umriss, hier bohrt
#: jemand ein Loch, und die Wörter, die er dabei benutzt, sind andere. Gleich
#: ist der **Bau** des Satzes, und das genügt: erst die Bedingung, dann was
#: sonst daraus wird.
SLOT_TOO_SHORT: Final = _(
    "Ein Langloch muss deutlich länger sein als sein Durchmesser — sonst ist es eine runde "
    "Bohrung. Tragen Sie mindestens die Länge ein, die darunter steht."
)

#: Der kleinste Weg zwischen den Bogenmitten, im Maß des Durchmessers.
#:
#: **Zehn Prozent, und das ist das Doppelte einer Messung** (11.09.2026,
#: Raster über Ø 2 bis Ø 40 in beiden Qualitätsstufen). Gemessen wurde, wo die
#: Merkmalserkennung kippt, und sie kippt in zwei Stufen: Unterhalb von rund
#: **fünf Prozent** des Durchmessers hält sie den Mantel für einen Zylinder und
#: nennt das Ergebnis eine **Bohrung**; in einem schmalen Streifen darüber
#: passt weder ein Zylinder noch ein Bogenpaar, und dann steht **gar kein**
#: Merkmal mehr da — kein Eintrag im Objektbaum, keine Maße im Bild, nichts zum
#: Anklicken (Robert, 11.09.2026: „es gibt noch Fälle, wo das Langloch keine
#: Maße im Viewport hat, nicht wählbar ist, im Objektbaum verschwindet").
#:
#: Die Grenze skaliert mit dem Durchmesser, weil die Tesselierung es tut: Ø 5
#: kippt bei 0,25 mm, Ø 12 bei 0,55, Ø 20 bei 1,0, Ø 40 bei 1,8 — in jedem Fall
#: rund fünf Prozent, und in der groben Qualitätsstufe dieselben Zahlen. Das
#: Doppelte davon hält Abstand, auch wenn die Materialtoleranz den
#: geschnittenen Durchmesser noch etwas hebt; das Dreifache nähme einem
#: Langloch Ø 40 sechs Millimeter Verschiebeweg ab, ohne dafür etwas zu geben.
#:
#: **Und darum steht die Zahl hier und nicht in der Oberfläche.** Bis zum
#: 11.09.2026 hatte der Griff im Bild seine eigene (``1.05``) und der Kern
#: seine (``Durchmesser + ε``) — der Griff rastete also genau dort, wo die
#: Erkennung kippt. Eine Grenze an zwei Stellen, und die Geste endete im toten
#: Streifen.
SLOT_SHORTEST_SHARE: Final = 1.10

#: Wie weit der Weg in absoluten Millimetern mindestens reichen muss.
#:
#: Bei kleinen Durchmessern ist der Anteil oben nicht die bindende Grenze: Ø 2
#: kippt gemessen zwischen 0,15 und 0,20 mm, und zehn Prozent davon wären 0,2 —
#: die Grenze selbst. Drei Zehntel halten denselben Abstand wie oben, ohne dass
#: die Zahl vom Durchmesser abhinge.
SLOT_SHORTEST_TRAVEL: Final = 0.3


def shortest_slot(diameter: float) -> float:
    """Die kürzeste Gesamtlänge, bei der ein Langloch noch eines ist.

    Die Antwort auf :data:`SLOT_SHORTEST_SHARE` und
    :data:`SLOT_SHORTEST_TRAVEL` in einer Zahl — gerechnet gegen den
    **gemessenen** Durchmesser, denn gegen ihn misst auch die Erkennung.

    Beide Kerne fragen hier, und die Oberfläche fragt ebenfalls: Der Griff im
    Bild (``app.ui.slot_handle``) rastet an dieser Länge, damit eine Geste
    nicht in einer Absage endet — und nicht in dem Streifen, in dem das
    Merkmal ganz verschwindet.
    """
    return diameter + max(SLOT_SHORTEST_TRAVEL, diameter * (SLOT_SHORTEST_SHARE - 1.0))


def is_round_length(length: float, width: float) -> bool:
    """Ob eine Langlochlänge die runde Bohrung meint: genau ihre Breite.

    Zwischen der Breite und :func:`shortest_slot` gibt es keine Länge — dort
    ist das Loch weder rund noch ein Langloch, das die Erkennung hält. Genau
    die Breite aber ist eine Form, die es gibt, und wer ein Langloch bis dorthin
    zurückzieht, meint die Bohrung, aus der es kam (Robert, 24.09.2026: „wenn
    man ein langloch so zieht, dass es wieder eine normale Bohrung wäre, sollte
    es kurz einrasten"). Gerechnet auf die halbe Anzeigestufe: Wer die Breite
    einträgt, die das Feld zeigt, meint sie.

    Griff, Felder und beide Kerne fragen hier — eine zweite Fassung der Frage
    rastete an einer anderen Stelle, als die Operation annimmt.
    """
    return math.isfinite(length) and abs(length - width) < EPS_DISPLAY / 2.0


def slot_travel(*, diameter: float, length: float, widening_diameter: float = 0.0) -> float:
    """Wie lang die Mittellinie eines Langlochs ist — null heißt: rund bohren.

    ``length`` ist die Gesamtlänge über alles, wie sie im Dialog steht;
    zurück kommt der Weg zwischen den beiden Bogenmittelpunkten. Das ist
    genau der Weg, den eine Schraube im fertigen Loch zurücklegen kann.

    **Gerechnet wird gegen den nominalen Durchmesser, nicht gegen den
    geschnittenen.** Die Materialtoleranz weitet das Loch überall, also auch an
    beiden Enden; hielte man stattdessen die Gesamtlänge fest, nähme jeder
    Druck dem Kunden ein Stück des Verschiebewegs ab, den er ausgerechnet hat.

    Hier steht auch der Ausschluss, den beide Kerne einhalten
    (:data:`SLOT_AND_WIDENING`) — er gehört an eine Stelle und nicht in zwei.
    """
    if not math.isfinite(length) or length <= EPS_GEOM:
        return 0.0
    if widening_diameter > EPS_GEOM:
        raise ValidationError(
            field="slot_length",
            constraint="conflict",
            detail=SLOT_AND_WIDENING,
        )
    shortest = shortest_slot(diameter)
    if length < shortest - EPS_GEOM:
        raise ValidationError(
            field="slot_length",
            constraint="slot_proportion",
            detail=SLOT_TOO_SHORT,
            value=length,
            values={"shortest": format_length(shortest)},
        )
    return length - diameter


def slot_profile(*, radius: float, travel: float, angle_deg: float = 0.0) -> SketchProfile:
    """Der Umriss eines Langlochs: zwei Halbkreise über einer Mittellinie.

    ``radius`` ist der halbe **geschnittene** Durchmesser — die Materialtoleranz
    hat der Aufrufer bereits aufgeschlagen. ``travel`` ist die Mittellinie aus
    :func:`slot_travel`; die Gesamtlänge des Umrisses ist ``travel + 2 * radius``.

    ``angle_deg`` dreht die Mittellinie gegen die x-Achse des Rahmens, auf dem
    der Umriss später aufgezogen wird. Beide Kerne ziehen ihn auf denselben
    Rahmen — der Winkel bedeutet damit in beiden dasselbe, und das ist der
    Grund, warum es diese eine Funktion gibt statt zweier Konstruktionen.

    Zurück kommt ein Skizzenumriss und kein Netz: Der Netz-Kern zieht ihn über
    :func:`app.core.geom.sketch_solid.extrude_profile` auf, der exakte über
    :func:`app.core.brep.profiles.extrude`, und dort bleiben die Enden echte
    Zylinderflächen statt abgetasteter Sehnen.
    """
    from app.core.sketch.profile import Profile as SketchOutline
    from app.core.sketch.profile import ProfileSegment

    if not math.isfinite(radius) or radius <= EPS_GEOM:
        raise ValidationError(
            field="diameter",
            constraint="positive",
            detail=_("Ein Langloch braucht einen positiven Durchmesser."),
        )
    if not math.isfinite(travel) or travel <= EPS_GEOM:
        raise ValidationError(
            field="slot_length",
            constraint="slot_proportion",
            detail=SLOT_TOO_SHORT,
            values={"shortest": format_length(shortest_slot(radius * 2.0))},
        )
    half = travel / 2.0
    # Ein Stadion ist nach einer halben Drehung derselbe Umriss. Gleiche
    # Formen beginnen an denselben Punkten, damit auch ihre Facettierung
    # und anschließende Schnitte übereinstimmen.
    turn = angle_deg % 180.0
    cosine, sine = units.exact_cos_degrees(turn), units.exact_sin_degrees(turn)

    def turned(x: float, y: float) -> tuple[float, float]:
        return (x * cosine - y * sine, x * sine + y * cosine)

    lower_left = turned(-half, -radius)
    lower_right = turned(half, -radius)
    right_apex = turned(half + radius, 0.0)
    upper_right = turned(half, radius)
    upper_left = turned(-half, radius)
    left_apex = turned(-half - radius, 0.0)
    # Gegen den Uhrzeigersinn, damit die Fläche positiv orientiert ist: untere
    # Flanke, rechter Bogen, obere Flanke, linker Bogen. Der Scheitel ist der
    # Punkt **auf** der Kurve, den ``ProfileSegment`` für einen Bogen verlangt.
    return SketchOutline(
        segments=(
            ProfileSegment("line", lower_left, lower_right),
            ProfileSegment("arc", lower_right, upper_right, via=right_apex),
            ProfileSegment("line", upper_right, upper_left),
            ProfileSegment("arc", upper_left, lower_left, via=left_apex),
        )
    )


#: Ab welchem Unterschied ein Zug nicht mehr in Richtung des bestehenden
#: Langlochs geht — und bis zu welchem Abstand eine gemessene Achse als die
#: Hauptachse gilt, neben der sie steht (:func:`slot_frame`).
#:
#: **Ein halbes Grad, und die Zahl ist gemessen.** Hier standen erst fünf Grad
#: mit der Begründung, darunter setze die Erkennung beide Züge wieder zu einem
#: Langloch zusammen. Das war geraten und falsch: An einem Langloch Ø 6 auf
#: 20 mm, auf 28 mm nachgezogen, bleibt es bis 0,5 Grad **ein** Merkmal und
#: zerfällt bei 0,75 Grad in zwei Verrundungen, bei einem Grad in vier.
#:
#: Wo genau es kippt, hängt von Länge und Breite ab — und deshalb steht die
#: Zahl hier gerade **nicht** dafür. Sie deckt, was ``slot_angle_of`` an
#: Rundung erzeugt, und sonst nichts; alles darüber ist eine Richtungsänderung
#: und wird gesagt. Für den Rahmen gilt dieselbe Aussage von der anderen Seite:
#: Das Messrauschen einer Achse lag an echten Netzen bei 4e-8 rad bis 0,07°
#: (29.09.2026), weit darunter; eine Achse, die weiter geneigt ist, hat jemand
#: so gewollt.
SLOT_ACROSS_LIMIT: Final = 0.5

#: Der Kegel um ±X, ±Y und ±Z, in dem :func:`slot_frame` eine Achse als diese
#: Hauptachse liest. Heute derselbe halbe Grad wie die Drehschwelle darüber,
#: aber eine **eigene** Zahl (RM-325): Wer die Schwelle nachstellt, darf damit
#: nicht den Rahmen verschieben, gegen den gespeicherte Winkel zählen.
#: **Eine Änderung braucht eine Migration** — jeder gespeicherte Langlochwinkel
#: an einer Achse im Kegelrand meinte danach eine andere Richtung.
SLOT_FRAME_CONE: Final = 0.5


def slot_frame(axis: Vec3, origin: Vec3) -> PlaneFrame:
    """Der Rahmen, gegen den der Winkel eines Langlochs zählt — beim Schneiden an
    beiden Kernen, beim Nachmessen, am Griff und in der Vorschau.

    **Warum nicht :func:`app.core.sketch.planes.frame_of`.** Dessen erste Achse
    ist das Kreuzprodukt aus Z und der Achse, bis ``units.PLANE_PARALLEL``
    (1e-9) neben Z. An einer **gemessenen** Achse bestimmt dort das Rauschen der
    Einpassung, wohin sie zeigt: Gemessen am 29.09.2026 an
    ``carpet-corner-clip.step``, vernetzt, zeigte dasselbe Langloch (in der Welt
    90°) im Feld -168,5°, 132,0° und 91,8° bei den Feinheiten 0,01, 0,02 und
    0,05, exakt 90°; am Besenhalter (Achsen 4e-8 rad neben Z) zeigte Winkel 0 an
    sechs Bohrungen auf 53° und 127°. Ein gespeicherter Winkel drehte das
    Langloch damit nach jeder Änderung eines früheren Schritts in eine andere
    Richtung.

    **Innerhalb von** :data:`SLOT_FRAME_CONE` **neben ±X, ±Y oder ±Z gilt die
    Achse als diese Hauptachse** (Entscheidung 30.09.2026): Die erste
    Rahmenachse kommt aus der Hauptachse (``units.plane_axes``) und wird gegen
    die gemessene Achse gestellt, die zweite ist das Kreuzprodukt aus Achse und
    erster. Eine exakte Hauptachse und eine Achse außerhalb des Kegels bekommen
    genau den Rahmen von ``frame_of`` — dort zählt der Winkel weiter gegen das
    Kreuzprodukt aus Z und Achse, die waagerechte Richtung der Fläche.
    ``plane_axes`` selbst bleibt, wie es ist: Es trägt auch die Skizzenebenen.

    Plattformgleich: Grundrechenarten, ``math.hypot``, ``units.dot3`` und der
    Sinus aus ``units.exact_sin_degrees`` (RM-187).
    """
    from app.core.sketch.planes import frame_of

    x, y, z = (float(axis[0]), float(axis[1]), float(axis[2]))
    span = math.hypot(x, y, z)
    if not math.isfinite(span) or span <= EPS_GEOM:
        return frame_of(axis, origin)
    unit = (x / span, y / span, z / span)
    main = max(range(3), key=lambda index: abs(unit[index]))
    beside = math.hypot(*(unit[index] for index in range(3) if index != main))
    if beside == 0.0 or beside > units.exact_sin_degrees(SLOT_FRAME_CONE):
        return frame_of(axis, origin)
    principal = [0.0, 0.0, 0.0]
    principal[main] = 1.0 if unit[main] > 0.0 else -1.0
    axes = units.plane_axes(principal)
    if axes is None:  # pragma: no cover - eine Hauptachse hat immer Länge eins
        return frame_of(axis, origin)
    first = axes[0]
    along = units.dot3(first, unit)
    across = (first[0] - along * unit[0], first[1] - along * unit[1], first[2] - along * unit[2])
    reach = math.hypot(*across)
    x_axis = (across[0] / reach, across[1] / reach, across[2] / reach)
    second = (
        unit[1] * x_axis[2] - unit[2] * x_axis[1],
        unit[2] * x_axis[0] - unit[0] * x_axis[2],
        unit[0] * x_axis[1] - unit[1] * x_axis[0],
    )
    width = math.hypot(*second)
    y_axis = (second[0] / width, second[1] / width, second[2] / width)
    return PlaneFrame(
        origin=(float(origin[0]), float(origin[1]), float(origin[2])),
        x_axis=x_axis,
        y_axis=y_axis,
        normal=unit,
    )


def slot_angle_from_measured_frame(axis: Vec3, angle_deg: float) -> float:
    """Ein gespeicherter Langlochwinkel aus der Zeit vor :func:`slot_frame`, im Rahmen von heute.

    Bis Format 38 zählte der Winkel gegen ``frame_of`` der Achse. Hier wird die
    Richtung, die dieser Rahmen mit ``angle_deg`` meinte, im Rahmen von
    :func:`slot_frame` gelesen — an derselben Achse dieselbe Richtung in der
    Welt, also derselbe Schnitt wie gespeichert. Außerhalb des Kegels um eine
    Hauptachse sind beide Rahmen gleich, und der Winkel bleibt (bis auf die
    Rundung) derselbe. Zurück kommt ein Winkel in ``(-180, 180]``.

    Zwei Leser: die Migration 38 → 39 für *Bohrung setzen* (die Normale steht
    im Schritt) und *Zum Langloch ziehen* bei der Auswertung (die Achse gibt
    erst die Erkennung). Plattformgleich über ``units.exact_cos_degrees``,
    ``exact_sin_degrees`` und ``exact_atan2_degrees``.
    """
    from app.core.sketch.planes import frame_of

    old = frame_of(axis, (0.0, 0.0, 0.0))
    new = slot_frame(axis, (0.0, 0.0, 0.0))
    cosine = units.exact_cos_degrees(angle_deg)
    sine = units.exact_sin_degrees(angle_deg)
    world = tuple(cosine * old.x_axis[index] + sine * old.y_axis[index] for index in range(3))
    return units.exact_atan2_degrees(units.dot3(world, new.y_axis), units.dot3(world, new.x_axis))


def edge_findings(
    mesh: HasBounds,
    *,
    position: Vec3,
    frame: PlaneFrame,
    diameter: float,
    travel: float,
    angle_deg: float,
    body: MeshData | None = None,
    reach: float | None = None,
    along: float = 0.0,
    old_opening: OpeningSpace | None = None,
) -> list[Finding]:
    """Die Kantenwarnung für eine runde Bohrung — und für beide Enden eines Langlochs.

    ``reach`` ist die Länge der Bohrung von ``position`` aus, in beide
    Richtungen (:func:`over_the_edge_along`, RM-249); ``along`` der Weg von
    ``position`` zu ihrer Mitte entlang der Normalen des Rahmens;
    ``old_opening`` eine alte Öffnung, die der Schnitt überdeckt, ohne dass sie
    geschlossen wurde (:class:`OpeningSpace`).

    Ein Langloch steckt in der Mitte tief im Material und reißt trotzdem an
    einem Ende auf; wer nur die Mitte fragt, hört davon nichts. Gemeldet wird
    höchstens einmal: Zwei gleichlautende Sätze über dasselbe Loch sagen nichts
    Zweites und sind der Lärm, nach dem niemand mehr in den Bericht sieht.
    """
    if body is None and isinstance(mesh, MeshData):
        body = mesh
    if travel <= EPS_GEOM:
        return over_the_edge_along(
            mesh,
            position,
            frame.normal,
            diameter,
            body=body,
            reach=reach,
            along=along,
            old_opening=old_opening,
        )
    for end in slot_ends(position, frame, travel, angle_deg):
        found = over_the_edge_along(
            mesh,
            end,
            frame.normal,
            diameter,
            body=body,
            reach=reach,
            along=along,
            old_opening=old_opening,
        )
        if found:
            return found
    return []


def slot_ends(
    position: Vec3, frame: PlaneFrame, travel: float, angle_deg: float
) -> tuple[Vec3, Vec3]:
    """Die beiden Bogenmittelpunkte eines Langlochs im Raum.

    Jede Prüfung, die für eine runde Bohrung an ihrer Mitte fragt, muss beim
    Langloch an beiden Enden fragen: Dort liegt es am weitesten außen, und dort
    reißt eine Flanke auf, während die Mitte noch tief im Material steckt.
    """
    # Dieselben exakten Winkelfunktionen wie :func:`slot_profile` (RM-187) —
    # die Enden, an denen geprüft wird, liegen dort, wo geschnitten wird.
    along = np.asarray(frame.x_axis, dtype=float) * units.exact_cos_degrees(angle_deg) + np.asarray(
        frame.y_axis, dtype=float
    ) * units.exact_sin_degrees(angle_deg)
    centre = np.asarray(position, dtype=float)
    first = centre - along * (travel / 2.0)
    second = centre + along * (travel / 2.0)
    return (
        (float(first[0]), float(first[1]), float(first[2])),
        (float(second[0]), float(second[1]), float(second[2])),
    )


def drill_tool(
    *,
    diameter: float,
    depth: float,
    profile: Profile,
    compensate: bool = True,
    widening_diameter: float = 0.0,
    widening_depth: float = 0.0,
    transition_angle: float = 90.0,
    mouth_overlap: float = 0.0,
    slot_length: float = 0.0,
    slot_angle: float = 0.0,
) -> MeshData:
    """Vernetzt das gemeinsame analytische Bohrungsprofil für Vorschau und Mesh-Kern.

    ``slot_length`` über null macht daraus ein Langloch: derselbe Radius,
    dieselbe Tiefe, nur auseinandergezogen entlang :func:`slot_travel`.
    """
    outline = drill_outline(
        diameter=diameter,
        depth=depth,
        profile=profile,
        compensate=compensate,
        widening_diameter=widening_diameter,
        widening_depth=widening_depth,
        transition_angle=transition_angle,
        mouth_overlap=mouth_overlap,
    )
    travel = slot_travel(diameter=diameter, length=slot_length, widening_diameter=widening_diameter)
    if travel > EPS_GEOM:
        from app.core.geom.sketch_solid import extrude_profile

        # Der Umriss liegt an der Mündung und wird nach unten aufgezogen —
        # genau die Spanne, die ``drill_outline`` beschreibt: von
        # ``mouth_overlap`` bis ``-depth``.
        body = extrude_profile(
            slot_profile(radius=outline[1][0], travel=travel, angle_deg=slot_angle),
            -(depth + mouth_overlap),
            PlaneFrame(
                origin=(0.0, 0.0, mouth_overlap),
                x_axis=(1.0, 0.0, 0.0),
                y_axis=(0.0, 1.0, 0.0),
                normal=(0.0, 0.0, 1.0),
            ),
        )
        return MeshData.of(body)
    if widening_diameter > EPS_GEOM:
        return MeshData.of(lathe.revolve(outline, sections=BORE_SECTIONS))
    radius = outline[1][0]
    cylinder = lathe.cylinder(
        radius=radius,
        height=depth + mouth_overlap,
        sections=BORE_SECTIONS,
    )
    cylinder.apply_translation((0.0, 0.0, (mouth_overlap - depth) / 2.0))
    return MeshData.of(cylinder)


def _in_world(frame: PlaneFrame) -> np.ndarray:
    """Die Matrix, die ein Werkzeug aus dem Rahmen einer Bohrung in die Welt legt."""
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    matrix[:3, 3] = np.asarray(frame.origin, dtype=np.float64)
    return matrix


def _heights(mesh: MeshData, frame: PlaneFrame) -> np.ndarray:
    """Die Lage jeder Ecke entlang der Achse eines Rahmens, gemessen von seinem Ursprung.

    Elementweise (:func:`transform.along`), nicht über ``@``: Aus ihr werden
    Werkzeuglänge und Endebenen, und die sollen auf jeder Maschine dieselben
    sein (RM-187).
    """
    offset = np.asarray(mesh.raw.vertices, dtype=np.float64) - np.asarray(
        frame.origin, dtype=np.float64
    )
    return transform.along(offset, frame.normal)


def _open_ends(
    mesh: MeshData,
    heights: np.ndarray,
    frame: PlaneFrame,
    ends: Sequence[tuple[float, float, float]],
) -> tuple[bool, ...]:
    """Je Ende eines abziehenden Werkzeugs: liegt es in einer Körperfläche mit Luft dahinter?

    ``heights`` ist :func:`_heights` desselben Rahmens; ``ends`` nennt je Ende
    seine Lage entlang ``frame.normal``, wohin es blickt (+1 in Richtung der
    Normalen, -1 dagegen) und wie weit das Werkzeug dort von der Achse reicht.

    **Das ist die Endebene des Bohrungsgebiets in Weltlage** (RM-274). Solange
    der Körper im Rahmen der Bohrung lag, legte die Bereinigung Ecken im
    Float64-Rauschen einer Endebene genau auf sie, und der Kern schnitt eine
    Fläche dort bündig weg. Ein Werkzeug in Weltlage trifft eine schräge Fläche
    nicht genau, und bündig davor lässt die Differenz eine Haut stehen
    (gemessen: eine Platte um 17,5° gedreht, Boden in der Unterseite bei 33°,
    jede float32-Fläche). Wer hier ``True`` bekommt, reicht dieses Ende um
    :data:`BOOLEAN_OVERLAP` in die Luft dahinter — das Ergebnis ist dasselbe
    wie bündig und genau.

    In der Fläche heißt: Alle drei Ecken eines Dreiecks liegen näher an der
    Endebene als ``units.weld_tolerance`` — zwei Orte, die das Verschweißen für
    einen hält, und weit über der float32-Rundung einer STL. Gefragt werden nur
    Dreiecke, die in die Ebene gelegt näher als die Reichweite an der Achse
    liegen. **Luft dahinter nur, wenn alle von ihnen vom Werkzeug weg zeigen**;
    zeigt eines zum Werkzeug hin, endet dort Material (ein Boden, auf den das
    Werkzeug trifft), und das Ende bleibt, wo es ist — jede Zugabe wäre dort
    ein Maßfehler.
    """
    raw = mesh.raw
    vertices = np.asarray(raw.vertices, dtype=np.float64)
    faces = np.asarray(raw.faces, dtype=np.int64)
    band = units.weld_tolerance(mesh.bounds.diagonal)
    offset = vertices - np.asarray(frame.origin, dtype=np.float64)
    across = transform.along(offset, frame.x_axis)
    up = transform.along(offset, frame.y_axis)
    answers: list[bool] = []
    for height, facing, reach in ends:
        near = np.abs(heights - height) <= band
        flat = faces[near[faces].all(axis=1)]
        if len(flat):
            flat = flat[_near_the_axis(across, up, flat, reach)]
        if not len(flat):
            answers.append(False)
            continue
        corners = vertices[flat]
        normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        away = transform.along(normals, frame.normal) * facing
        away = away[away != 0.0]
        answers.append(bool(len(away)) and bool(np.all(away > 0.0)))
    return tuple(answers)


def _near_the_axis(
    across: np.ndarray, up: np.ndarray, faces: np.ndarray, reach: float
) -> np.ndarray:
    """Welche Dreiecke, in die Ebene quer zur Achse gelegt, die Scheibe um sie berühren.

    ``across`` und ``up`` sind die Lagen der Ecken entlang der beiden anderen
    Achsen des Rahmens. Berührt heißt: Die Achse liegt im Dreieck, oder eine
    seiner Kanten kommt ihr näher als ``reach``. Grundrechenarten, elementweise.
    """
    first = np.stack((across[faces[:, 0]], up[faces[:, 0]]), axis=1)
    second = np.stack((across[faces[:, 1]], up[faces[:, 1]]), axis=1)
    third = np.stack((across[faces[:, 2]], up[faces[:, 2]]), axis=1)

    def side(start: np.ndarray, end: np.ndarray) -> np.ndarray:
        turn = (end[:, 0] - start[:, 0]) * -start[:, 1] - (end[:, 1] - start[:, 1]) * -start[:, 0]
        return np.asarray(turn)

    def gap(start: np.ndarray, end: np.ndarray) -> np.ndarray:
        step = end - start
        length = step[:, 0] * step[:, 0] + step[:, 1] * step[:, 1]
        along = -(start[:, 0] * step[:, 0] + start[:, 1] * step[:, 1])
        share = np.clip(along / np.where(length > 0.0, length, 1.0), 0.0, 1.0)
        x = start[:, 0] + share * step[:, 0]
        y = start[:, 1] + share * step[:, 1]
        return np.asarray(x * x + y * y)

    turns = (side(first, second), side(second, third), side(third, first))
    inside = ((turns[0] >= 0.0) & (turns[1] >= 0.0) & (turns[2] >= 0.0)) | (
        (turns[0] <= 0.0) & (turns[1] <= 0.0) & (turns[2] <= 0.0)
    )
    nearest = np.minimum(np.minimum(gap(first, second), gap(second, third)), gap(third, first))
    return np.asarray(inside | (nearest <= reach * reach))


def drill(
    mesh: MeshData,
    *,
    position: Vec3,
    axis: Axis,
    normal: Vec3 = (0.0, 0.0, 0.0),
    diameter: float,
    depth: float = 0.0,
    widening_diameter: float = 0.0,
    widening_depth: float = 0.0,
    transition_angle: float = 90.0,
    anchor: BoreAnchor = "mouth",
    profile: Profile,
    compensate: bool = True,
    quality: Quality = "fine",
    seed: int | None = None,
    slot_length: float = 0.0,
    slot_angle: float = 0.0,
    cancelled: CancelToken | None = None,
    object_id: ObjectId | None = None,
) -> BoreResult:
    """Schneidet eine Bohrung mit optionaler Aufweitung. Tiefe null bohrt ganz durch.

    ``anchor`` sagt, was die Position bedeutet. ``mouth`` ist, was jemand
    meint, der eine Fläche anklickt: dort fängt die Bohrung an und geht von da
    ins Material. ``centre`` legt die Mitte der Bohrung auf die Position —
    das taten alle Bohrungen bis Formatversion 7, und ein Klick auf die
    Oberseite bohrte darum nur halb so tief wie verlangt.

    Eine gerade durchgehende Bohrung reicht von jeder Position aus in beide
    Richtungen hinaus. Ihre Aufweitung beginnt dagegen an der Mündung; auf
    einer abgestuften Fläche verschiebt der höchste Nachbar diesen Bezug nicht.

    ``slot_length`` über null zieht die Bohrung zu einem Langloch auseinander.
    Ein Langloch geht **immer** über den Rahmen, auch bei einer achsparallelen
    Achse: ``slot_angle`` zählt gegen die x-Achse aus :func:`slot_frame` — für
    eine Normale knapp neben einer Hauptachse gegen die der Hauptachse —, und
    der achsparallele Zweig weiter unten kennt diesen Rahmen nicht; derselbe
    Winkel bedeutete dort eine andere Richtung.

    **Der Rahmen hängt an der Normalen, also an der Seite, von der aus gebohrt
    wird.** Gemessen an derselben Platte: 45 Grad von oben ergeben 45 Grad,
    45 Grad von unten ergeben 135 — der Rahmen spiegelt seine erste Achse mit
    der Normalen. Für den Kunden ist das die richtige Antwort, weil er die
    Fläche anklickt und die Vorschau sieht; wer die Zahl von hier zu
    :func:`slot_bore` überträgt, bekommt an einer von unten gebohrten Bohrung
    die gespiegelte Lage (der Kommentar dort sagt, warum das so bleibt).
    """
    cut_diameter = bore_diameter(diameter, profile, compensate)
    travel = slot_travel(diameter=diameter, length=slot_length, widening_diameter=widening_diameter)
    through = depth <= EPS_GEOM
    direction = np.asarray(normal, dtype=np.float64)
    if not np.isfinite(direction).all():
        raise ValidationError(
            field="nx", detail=_("Wählen Sie eine endliche Richtung für die Bohrung.")
        )
    # ``math.hypot`` statt ``np.linalg.norm`` (BLAS, RM-187): Aus der Länge
    # wird die Richtung, und aus der Richtung der Rahmen des Werkzeugs.
    length = math.hypot(float(direction[0]), float(direction[1]), float(direction[2]))
    if length <= EPS_GEOM and (widening_diameter > EPS_GEOM or travel > EPS_GEOM):
        direction = np.asarray(drill_outward_axis(mesh, axis, position), dtype=np.float64)
        length = 1.0
    if length > EPS_GEOM:
        from app.core.sketch.planes import frame_of

        outward = direction / length
        pointing = (float(outward[0]), float(outward[1]), float(outward[2]))
        # Ein Langloch zählt seinen Winkel gegen :func:`slot_frame`; eine runde
        # Bohrung ist um ihre Achse gleich, ihr Vieleck bleibt, wo es war.
        frame = (
            slot_frame(pointing, position) if travel > EPS_GEOM else frame_of(pointing, position)
        )
        # **Das Werkzeug wandert in die Welt, nicht der Körper in den Rahmen**
        # (RM-274). Bis zur Durchsicht 0.5.1 lag hier der ganze Körper für den
        # Schnitt im Rahmen der Bohrung und danach wieder in der Welt; die
        # Rundung von Hin- und Rückweg versetzte Ecken, die der Schnitt nie
        # berührt — am Gartenschlauchhalter 17 490 außerhalb eines Lochs von
        # Ø 3 mm und 2 mm Tiefe, und der Merker über die Körpergrenze rechnete
        # danach 1 078 statt 79 Fragen neu. Gemessen wird im Rahmen nur entlang
        # der Achse, und das elementweise.
        heights = _heights(mesh, frame)
        if through:
            low, high = float(heights.min()), float(heights.max())
            if widening_diameter > EPS_GEOM and anchor == "mouth":
                height, mouth = -low + BOOLEAN_OVERLAP, 0.0
            else:
                height = high - low + BOOLEAN_OVERLAP * 2.0
                mouth = high + BOOLEAN_OVERLAP
        else:
            height, mouth = depth, depth / 2.0 if anchor == "centre" else 0.0
        # **Die Enden des Werkzeugs** (die Endebenen des Bohrungsgebiets). Ein
        # Ende, das in einer Körperfläche mit Luft dahinter liegt — die Mündung
        # in der angeklickten Fläche, ein Boden in der Unterseite —, reicht um
        # die Zugabe darüber (:func:`_open_ends`); bündig ließ der Weg über den
        # Rahmen an einer schrägen float32-Fläche eine Haut in der Mündung
        # stehen. Ein Blindboden im Material und eine im Material eingegebene
        # Mündung bleiben genau, wo sie sind; ein durchgehendes Werkzeug reicht
        # ohnehin über den Körper hinaus.
        radius = cut_diameter / 2.0 + travel / 2.0
        top_radius = (
            bore_diameter(widening_diameter, profile, compensate) / 2.0
            if widening_diameter > EPS_GEOM
            else radius
        )
        below = above = False
        if not through:
            below, above = _open_ends(
                mesh, heights, frame, ((mouth - height, -1.0, radius), (mouth, 1.0, top_radius))
            )
        elif widening_diameter > EPS_GEOM and anchor == "mouth":
            (above,) = _open_ends(mesh, heights, frame, ((mouth, 1.0, top_radius),))
        tool = drill_tool(
            diameter=diameter,
            depth=height + (BOOLEAN_OVERLAP if below else 0.0),
            profile=profile,
            compensate=compensate,
            widening_diameter=widening_diameter,
            widening_depth=widening_depth,
            transition_angle=transition_angle,
            mouth_overlap=BOOLEAN_OVERLAP if above else 0.0,
            slot_length=slot_length,
            slot_angle=slot_angle,
        )
        cylinder = tool.raw.copy()
        cylinder.apply_translation((0.0, 0.0, mouth))
        transform.moved(cylinder, _in_world(frame))
        outcome = boolean(
            "difference",
            [mesh, MeshData.of(cylinder)],
            quality=quality,
            seed=seed,
            cancelled=cancelled,
            object_ids=(object_id, None),
        )
        result = outcome.mesh
        findings = list(outcome.findings)
        nothing = without_effect(mesh, result, "difference", profile)
        if nothing is not None:
            findings.append(nothing)
        findings.extend(
            edge_findings(
                mesh,
                position=position,
                frame=frame,
                diameter=cut_diameter,
                travel=travel,
                angle_deg=slot_angle,
                # Die Bohrung liegt im Rahmen zwischen ``mouth - height`` und
                # ``mouth``; gefragt wird um ihre Mitte, über die halbe Länge.
                reach=height / 2.0,
                along=mouth - height / 2.0,
            )
        )
        findings.extend(split_findings(mesh, result))
        findings.extend(compensation_findings(diameter, cut_diameter, compensate))
        # Das Werkzeug im Weltraum, für die Nachbarprüfung des Aufrufers —
        # ``resize_hole`` versetzt eine Bohrung über diesen Weg, und bis zum
        # 22.09.2026 blieb ohne Werkzeug die aufgerissene Nachbarwand ungesagt.
        return BoreResult(
            result, outcome.solver, cut_diameter, findings, cutting_tool=MeshData.of(cylinder)
        )
    height = _through_length(mesh, axis) * 2.0 if through else depth
    cylinder = drill_tool(
        diameter=diameter,
        depth=height,
        profile=profile,
        compensate=compensate,
        widening_diameter=widening_diameter,
        widening_depth=widening_depth,
        transition_angle=transition_angle,
        # Durchgehend reicht das Werkzeug ohnehin über beide Seiten hinaus.
        # Am Mündungsanker liegt die Position auf der Fläche — dort braucht
        # die Boolesche die Zugabe, der Boden bleibt bei der Tiefe. Der
        # historische Mittenanker kennt keine Fläche: Seine Mündungsebene
        # kann mitten im Material liegen, und eine Zugabe dort wäre ein
        # tieferes Loch, kein Schutz.
        mouth_overlap=BOOLEAN_OVERLAP if not through and anchor == "mouth" else 0.0,
    ).raw.copy()
    alignment = _axis_alignment(axis)
    # Wo die Mitte der Bohrung liegt, von der Stelle aus entlang der Achse —
    # für die Kantenfrage unten.
    to_the_middle = 0.0
    if through:
        # Symmetrisch über beide Seiten hinaus: Mitte auf die Position.
        cylinder.apply_translation((0.0, 0.0, height / 2.0))
        transform.moved(cylinder, alignment)
        cylinder.apply_translation(np.asarray(position, dtype=float))
    else:
        # Das Werkzeug ist nicht mehr symmetrisch: Mündung bei null mit
        # Zugabe darüber, Boden exakt bei -height. Die Mündung muss aus dem
        # Material heraus zeigen — und ``_axis_alignment`` legt die lokale
        # z-Achse je nach Achse auf +x, -y oder +z. Also nachsehen, wohin
        # sie zeigt, und das Werkzeug um seine Querachse drehen, wenn die
        # Zugabe sonst am Boden läge (gemessen 06.09.2026 an der y-Achse).
        into = _into_the_material(mesh, axis, position)
        local_z = alignment[:3, :3] @ np.array([0.0, 0.0, 1.0])
        if float(np.sign(local_z[AXIS_INDEX[axis]])) == into:
            transform.moved(cylinder, transform.rotation("x", 180.0))
        transform.moved(cylinder, alignment)
        along = np.zeros(3)
        along[AXIS_INDEX[axis]] = into
        offset = np.asarray(position, dtype=float)
        if anchor == "centre":
            # Historischer Anker: die Position ist die Mitte der Bohrlänge.
            offset = offset - along * (height / 2.0)
        else:
            to_the_middle = into * height / 2.0
        cylinder.apply_translation(offset)

    outcome = boolean(
        "difference",
        [mesh, MeshData.of(cylinder)],
        quality=quality,
        seed=seed,
        cancelled=cancelled,
        object_ids=(object_id, None),
    )
    findings = list(outcome.findings)
    # Eine Bohrung, die den Körper nicht getroffen hat, sagt das (§2.7).
    nothing = without_effect(mesh, outcome.mesh, "difference", profile)
    if nothing is not None:
        findings.append(nothing)
    # Um die Mitte der Bohrung, über ihre halbe Länge: am Mündungsanker liegt
    # sie eine halbe Tiefe im Material, sonst an der Stelle selbst.
    findings.extend(
        over_the_edge(
            mesh,
            position,
            axis,
            cut_diameter,
            body=mesh,
            reach=height / 2.0,
            along=to_the_middle,
        )
    )
    findings.extend(split_findings(mesh, outcome.mesh))
    findings.extend(compensation_findings(diameter, cut_diameter, compensate))
    return BoreResult(
        mesh=outcome.mesh,
        solver=outcome.solver,
        diameter=cut_diameter,
        findings=findings,
        cutting_tool=MeshData.of(cylinder),
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
    cancelled: CancelToken | None = None,
    object_id: ObjectId | None = None,
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
    placement = sink_placement(mesh, axis, position, diameter, anchor)
    at = np.asarray(placement.position, dtype=float)
    outward = placement.outward
    findings: list[Finding] = list(placement.findings)

    narrows = np.zeros(3)
    narrows[AXIS_INDEX[axis]] = -outward

    # Über ``lathe`` (RM-187): ``trimesh.creation.cone`` nimmt seine Ecken aus
    # ``np.cos``, und das rechnet je CPU anders.
    cone = lathe.revolve([[0.0, 0.0], [diameter / 2.0, 0.0], [0.0, depth]], sections=BORE_SECTIONS)
    # Der Kegel kommt auf seiner Basis stehend heraus, Spitze nach oben. Eine
    # Senkung ist andersherum: am weitesten an der Fläche, enger werdend ins
    # Material. Umgedreht läuft er von null abwärts, was genau das ist — und
    # er wird um die Überlappung angehoben, damit die zwei Flächen nicht
    # zusammenfallen (§39). Die halbe Drehung ist exakt (``transform.rotation``).
    transform.moved(cone, transform.rotation("x", 180.0))
    cone.apply_translation([0.0, 0.0, BOOLEAN_OVERLAP])
    transform.moved(cone, transform.rotation_between(np.array([0.0, 0.0, -1.0]), narrows))
    cone.apply_translation(at)

    outcome = boolean(
        "difference",
        [mesh, MeshData.of(cone)],
        quality=quality,
        cancelled=cancelled,
        object_ids=(object_id, None),
    )
    findings = [*outcome.findings, *findings]
    # Dieselbe Auskunft wie beim Bohren: eine Senkung neben dem Körper sagt es
    # (§2.7). Sie war der eigentliche Schaden an der festen Richtung — der
    # Kegel lag daneben, und niemand erfuhr davon.
    nothing = without_effect(mesh, outcome.mesh, "difference", profile)
    if nothing is not None:
        findings.append(nothing)
    # **Und wie beim Bohren die Kante** (22.09.2026): Der Kegel ist an der
    # Mündung so weit wie der Schraubenkopf, und nahe einer Außenwand reißt er
    # sie auf. Jeder andere Weg, der einen Hohlraum setzt, fragte das seit dem
    # 15.09.2026; das Senken nicht.
    findings.extend(
        mouth_over_the_edge(
            mesh,
            (float(at[0]), float(at[1]), float(at[2])),
            (float(narrows[0]), float(narrows[1]), float(narrows[2])),
            diameter,
        )
    )
    return BoreResult(
        mesh=outcome.mesh,
        solver=outcome.solver,
        diameter=diameter,
        findings=findings,
    )


@dataclass(frozen=True, slots=True)
class SinkPlacement:
    """Wo eine Senkung wirklich ansetzt: die Mündung, die Richtung nach außen, die Befunde."""

    position: Vec3
    outward: float
    findings: tuple[Finding, ...]


def sink_placement(
    mesh: MeshData, axis: Axis, position: Vec3, diameter: float, anchor: BoreAnchor
) -> SinkPlacement:
    """Die Platzierung einer Senkung — für beide Kerne dieselbe Antwort.

    :func:`countersink` schneidet damit am Netz, ``geom.prepare_ops`` am exakten
    Körper; gemessen wird in beiden Fällen am Netz, denn die Frage nach
    Mündung und Materialseite stellt sich mit Strahlen, und der Zwilling eines
    exakten Körpers hat dieselben. Eine Mündung, zwei Mündungen, keine: bei
    genau einer ist sie gefunden, sonst entscheidet dieselbe Hüllquader-Regel
    wie beim Bohren (:func:`into_the_body`).
    """
    at = np.asarray(position, dtype=float)
    sides = open_sides(mesh, axis, tuple(at))
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
                # Regel 17: Die Stelle, die der Satz nennt, steht im Schritt.
                suggestions=(CORRECT_INPUT,),
            )
        )
    return SinkPlacement((float(at[0]), float(at[1]), float(at[2])), outward, tuple(findings))


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
    cancelled: CancelToken | None = None,
    object_id: ObjectId | None = None,
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
    centre, height = plug_placement(mesh, axis, position, depth, anchor)
    filled = diameter if profile is None else bore_diameter(diameter, profile, compensate)
    cylinder = lathe.cylinder(
        radius=filled / 2.0 + BOOLEAN_OVERLAP, height=height, sections=BORE_SECTIONS
    )
    transform.moved(cylinder, _axis_alignment(axis))
    cylinder.apply_translation(np.asarray(centre, dtype=float))

    # Erst verschneiden: der Stopfen darf nicht aus dem Körper herauswachsen,
    # den er füllt.
    inner = boolean(
        "intersection",
        [mesh.replacing(cylinder), shell(mesh)],
        quality=quality,
        cancelled=cancelled,
    )
    outcome = boolean(
        "union",
        [mesh, inner.mesh],
        quality=quality,
        cancelled=cancelled,
        object_ids=(object_id, None),
    )
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


def plug_placement(
    mesh: MeshData, axis: Axis, position: Vec3, depth: float, anchor: BoreAnchor
) -> tuple[Vec3, float]:
    """Mitte und Länge eines Stopfens aus Zahlen — für beide Kerne dieselbe Antwort.

    Wie beim Bohren: ein durchgehender Stopfen ist doppelt so lang wie der
    Körper, damit er von jeder Position aus in beide Richtungen hinausreicht —
    die Hülle schneidet den Überstand ohnehin weg. Zentriert auf die Mündung
    füllte die einfache Länge nur die Hälfte und ließ die Bohrung offen. Und
    ``mouth`` heißt: die Tiefe geht von der Position aus ins Material
    (:func:`_into_the_material`), nicht zur Hälfte hinaus.
    """
    through = depth <= EPS_GEOM
    height = _through_length(mesh, axis) * 2.0 if through else depth
    offset = np.asarray(position, dtype=float)
    if not through and anchor == "mouth":
        direction = np.zeros(3)
        direction[AXIS_INDEX[axis]] = _into_the_material(mesh, axis, position)
        offset = offset + direction * (height / 2.0)
    return (float(offset[0]), float(offset[1]), float(offset[2])), height


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


def drill_outward_axis(mesh: MeshData, axis: Axis, position: Vec3) -> Vec3:
    """Die vom Netzkern bei einer Nullnormalen gewählte Außenrichtung."""
    direction = [0.0, 0.0, 0.0]
    direction[AXIS_INDEX[axis]] = -_into_the_material(mesh, axis, position)
    return (direction[0], direction[1], direction[2])


def drill_outward_axis_from_bounds(axis: Axis, position: Vec3, centre: Vec3) -> Vec3:
    """Die gemeinsame Hüllmittenentscheidung des exakten Bohrkerns."""
    index = AXIS_INDEX[axis]
    direction = [0.0, 0.0, 0.0]
    direction[index] = 1.0 if position[index] >= centre[index] else -1.0
    return (direction[0], direction[1], direction[2])


def _axis_alignment(axis: Axis) -> np.ndarray:
    """Zylinder werden entlang Z gebaut; auf die gewünschte Achse drehen."""
    if axis == "z":
        return np.eye(4)
    # Ein rechter Winkel aus den exakten Winkelfunktionen (RM-187): Mit
    # ``math.radians(90)`` trug jede Ecke des gedrehten Zylinders 6·10⁻¹⁷.
    return np.asarray(transform.rotation("y" if axis == "x" else "x", 90.0), dtype=float)


def split_at_plane(mesh: MeshData, plane: SectionPlane) -> tuple[MeshData, MeshData, list[Finding]]:
    """Schneidet einen Körper in zwei, beide Hälften geschlossen (§18.2, §25).

    **Der Befund nennt die Ursache, nicht nur das Ergebnis.** „Die
    Schnittflächen konnten nicht geschlossen werden" stand hier bis zum
    10.09.2026 allein da, und ein Kunde konnte daraus nichts machen: Es klang
    nach einem Fehler des Schnitts, und gesucht wurde folglich am Schnitt. Der
    Schnitt kann aber gar nichts dafür — ``SectionResult.capped`` ist genau
    ``is_watertight`` der **Eingabe** (siehe ``section._apply``), also war das
    Modell schon vorher offen. Ein offenes Netz lässt sich nicht ehrlich
    deckeln; der Schnitt zeigt es trotzdem und sagt jetzt, woran es liegt und
    was zu tun ist (Regel 17).

    Eine erst durch den Schnitt entstandene Berührlinie ist eine andere
    Ursache: :func:`section.check_cut_contact` sagt diese Lage vor jeder
    Folgerechnung ab, ohne den Eingang als offen auszugeben.
    """
    first = cut(mesh, plane)
    second = cut(mesh, plane.flipped())
    check_cut_contact(first, plane.position)
    check_cut_contact(second, plane.position)
    findings: list[Finding] = []
    if not (first.capped and second.capped):
        findings.append(
            Finding(
                code="split.uncapped",
                severity="warning",
                message=_(
                    "Die Schnittflächen bleiben offen: Das Modell ist schon vor dem "
                    "Schnitt nicht geschlossen. Reparieren Sie es und teilen Sie danach erneut."
                ),
            )
        )
    return first.mesh, second.mesh, findings


#: Höchstzahl eines ausdrücklich begrenzten Anordnungsauftrags (§29).
#: Importe ergänzen nach §17.1 die vorhandenen Platten ohne diese Grenze.
MAX_PLATES = 12

#: Die Luft zwischen zwei Teilen, die *Auf dem Bett anordnen* vorgibt — und die
#: ein weiteres Modell beim Einlesen bekommt (§17.1, Schritt 6). Eine Stelle,
#: damit beide Wege denselben Abstand halten.
ARRANGE_SPACING: Final = 5.0


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
                    # Regel 17: Der Einzug steht im Schritt und lässt sich dort kleiner wählen.
                    suggestions=(CORRECT_INPUT,),
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


def _fits_after_shift(mesh: MeshData, shift: tuple[float, float], allowed: Any) -> bool:
    """Liegt dieser Körper auch verschoben noch auf der freigegebenen Fläche?

    Dieselben zwei Stufen wie in ``place``: erst das Rechteck, und nur wenn das
    nicht genügt, die tatsächliche Projektion. Ein Ring um eine Sperrzone
    scheitert am Rechteck und besteht an seiner Kontur.
    """
    low, high = mesh.bounds.minimum, mesh.bounds.maximum
    rectangle = box(low[0] + shift[0], low[1] + shift[1], high[0] + shift[0], high[1] + shift[1])
    if allowed.covers(rectangle):
        return True
    moved = shift_polygon(footprint(mesh), xoff=shift[0], yoff=shift[1])
    return bool(allowed.covers(moved))


def _into_the_middle(
    arranged: list[MeshData],
    assigned: list[int],
    area: Any,
    allowed: Any,
    bed: Any | None = None,
) -> list[MeshData]:
    """Schiebt jede Platte als Ganzes in die Mitte der freigegebenen Fläche.

    **Gepackt wird in der Ecke, gelegt wird in der Mitte** (Robert,
    09.09.2026: „startpunkt mitte zum ausrichten gut, orientiere dich an den
    verschiedenen slicern"). Jeder Slicer daneben — ElegooSlicer, Orca, Bambu
    Studio, PrusaSlicer — legt seine Teile mittig; Solidon legte sie nach
    hinten links, weil dort die Packregel aus §29 ihre Ecke hat. Auf einem
    256er Bett standen zwei Türme damit bei x -123 und y 123, während drei
    Viertel der Fläche leer blieben.

    Das **Verfahren** bleibt unangetastet, und das ist der Grund für diese
    Bauart: §29 verlangt bei einer Änderung des Packverfahrens eine neue
    Abnahme an denselben Referenzteilen — Plattenzahl, Kollisionsfreiheit,
    Mindestabstände, Reproduzierbarkeit. Eine gemeinsame Verschiebung ändert
    keines davon, denn sie bewegt alle Körper einer Platte um denselben Betrag.

    Zwei Grenzen, beide notwendig:

    * **Je Achse nur, was hineinpasst.** Ist eine Platte breiter als die
      Fläche, bliebe von der Mitte aus auf beiden Seiten etwas draußen statt
      auf einer; die Befunde aus :func:`check_build_volume` wären damit andere,
      ohne dass jemand etwas gewonnen hätte.
    * **Und nur, wenn die Mitte wirklich frei ist.** ``place`` prüft jede
      einzelne Lage gegen die freigegebene Fläche; eine nachträgliche
      Verschiebung geht an dieser Prüfung vorbei. Ein Drucker mit einer
      Sperrzone in der Mitte bekäme sonst Teile hineingeschoben — dort bleibt
      die Platte, wo sie gepackt wurde.

    **Was nur ohne den Rand passt, liegt mittig auf dem Bett** (RM-229,
    Durchsicht 0.5.1). ``bed`` ist die Druckfläche ohne Rand. Eine Platte, die
    in einer Achse breiter ist als die Fläche mit Rand, aber nicht breiter als
    das Bett, wird in dieser Achse auf die Mitte des Betts gelegt: Der Rand
    wird auf beiden Seiten gleich schmal, statt auf der einen Seite zu bleiben
    und auf der anderen über die Kante zu ragen. Gemessen am K1 (Bett 220,
    Abstand 5): ein Quader von 216 mm lag bei x -105…111, 1 mm über der Kante,
    und mittig passt er mit 2 mm je Seite. Geprüft wird diese Lage dann gegen
    das Bett; was dort nicht frei ist (eine Sperrzone), bleibt, wo es liegt.
    :func:`check_build_volume` sagt den schmaleren Rand als Hinweis.
    """
    left_edge, front_edge, right_edge, back_edge = area.bounds
    middle = ((left_edge + right_edge) / 2.0, (front_edge + back_edge) / 2.0)
    span = (right_edge - left_edge, back_edge - front_edge)
    if bed is not None and not bed.is_empty:
        bed_left, bed_front, bed_right, bed_back = bed.bounds
        bed_middle = ((bed_left + bed_right) / 2.0, (bed_front + bed_back) / 2.0)
        bed_span = (bed_right - bed_left, bed_back - bed_front)
        bed_allowed = bed.buffer(EPS_GEOM, join_style="mitre")
    else:
        bed_middle, bed_span, bed_allowed = middle, span, allowed
    moved = list(arranged)
    for plate in sorted(set(assigned)):
        members = [index for index, at in enumerate(assigned) if at == plate]
        low = np.min([arranged[index].bounds.minimum[:2] for index in members], axis=0)
        high = np.max([arranged[index].bounds.maximum[:2] for index in members], axis=0)
        along = [0.0, 0.0]
        narrower = False
        for axis in (0, 1):
            extent = float(high[axis]) - float(low[axis])
            centre = (float(low[axis]) + float(high[axis])) / 2.0
            if extent <= span[axis] + _TOUCH:
                along[axis] = middle[axis] - centre
            elif extent <= bed_span[axis] + _TOUCH:
                along[axis] = bed_middle[axis] - centre
                narrower = True
        limit = bed_allowed if narrower else allowed
        shift = (along[0], along[1])
        if abs(shift[0]) < _TOUCH and abs(shift[1]) < _TOUCH:
            continue
        whole = box(low[0] + shift[0], low[1] + shift[1], high[0] + shift[0], high[1] + shift[1])
        if not limit.covers(whole) and not all(
            _fits_after_shift(arranged[index], shift, limit) for index in members
        ):
            continue
        for index in members:
            body = arranged[index].raw.copy()
            transform.moved(body, translation((shift[0], shift[1], 0.0)))
            moved[index] = arranged[index].replacing(body)
    return moved


def arrange_on_bed(
    meshes: list[MeshData],
    profile: Profile,
    spacing: float = ARRANGE_SPACING,
    plates: int = 1,
    object_ids: Sequence[ObjectId] | None = None,
    *,
    margin: float | None = None,
    occupied: Sequence[tuple[MeshData, int]] = (),
    centre_slender: bool = False,
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

    **Jeder Körper kommt auf die erste Platte, auf der er Platz hat**, und
    erst wenn keine belegte ihn nimmt, wird die nächste angefangen — bis zu
    ``plates`` davon. Bis zum 29.09.2026 blätterte die Anordnung nur vorwärts:
    War ein großes Teil auf eine neue Platte gewandert, sah keine Platte davor
    mehr ein Teil. Robert fand es am Minigolf-Satz („warum werden die nicht
    auf eine platte was passt ausgerichtet?"): Drehscheibe und vier Stangen
    lagen neben dem Bett, während auf den ersten beiden Platten Platz war, und
    mit zwölf erlaubten Platten wurden es sechs statt vier. Dieselbe
    Plattenfolge befolgt :func:`first_free_spot` für ein einzelnes neues
    Modell; auf der Platte sucht es dort die Stelle nächst der Mitte.

    Mehr Teile als Platten sind kein Fehler zum Verstecken: die letzte Platte
    nimmt den Rest, und der Bericht sagt, dass sie übervoll ist — denn ein
    Teil, das still aus einer Anordnung fällt, ist ein Teil, das nie gedruckt
    wird.

    ``occupied`` nennt Körper, die **liegen bleiben** — mit der Platte, auf der
    sie liegen. Ihr Platz ist belegt, und um sie herum wird angeordnet. Das
    braucht, wer nur einen Teil der Szene anordnet: *Druckoptimal ausrichten*
    dreht so viele Körper, wie gewählt sind, und legte sie sonst genau dorthin,
    wo ein nicht gewählter schon steht (Befund Robert, 09.09.2026). Eine Platte
    mit solchen Körpern wird **nicht** zentriert — die Mitte gehört der ganzen
    Platte, und die kennt nur, wer sie ganz anordnet.

    Der Aufwand wächst mit dem Quadrat der Teilezahl; für die Größenordnung, um
    die es geht — Dutzende Körper auf einer Platte — bleibt das weit unter dem
    Budget für eine Anordnung (§31).
    """
    # Ohne ausdrücklichen Auftragsrand bleibt der bisherige Anordnungsrand.
    # Er ist eine Nutzereinstellung, keine vermutete Maschinensperre.
    edge_margin = spacing if margin is None else margin
    area = printable_area(profile.printer, margin=edge_margin)
    allowed = area.buffer(EPS_GEOM, join_style="mitre")
    arranged: list[MeshData] = []
    assigned: list[int] = []
    findings: list[Finding] = []

    left_edge, front_edge, right_edge, back_edge = (
        area.bounds if not area.is_empty else printable_area(profile.printer).bounds
    )
    corner = (left_edge, back_edge)

    # Was liegen bleibt, belegt seinen Platz — je Platte, denn zwei Teile an
    # derselben Stelle auf verschiedenen Platten treffen sich nie.
    held: dict[int, list[_Slot]] = {}
    for mesh, at in occupied:
        low, high = mesh.bounds.minimum, mesh.bounds.maximum
        held.setdefault(at, []).append(
            _Slot(float(low[0]), float(high[1]), float(high[0] - low[0]), float(high[1] - low[1]))
        )

    # Die angefangenen Platten, jede mit dem, was auf ihr liegt.
    opened: list[list[_Slot]] = [list(held.get(0, ()))]

    def place(mesh: MeshData, taken: list[_Slot]) -> _Slot | None:
        """Die hinterste, dann linkeste Stelle, an die dieser Körper passt."""
        size = mesh.bounds.size
        if size[2] > printable_height(profile.printer) + EPS_GEOM:
            return None
        points = set(_candidates(taken, corner, spacing))
        # Auch an einem Sperreck kann die erste freie Lage beginnen.
        xs = {left_edge}
        ys = {back_edge}
        for x, y in get_coordinates(area):
            xs.update((float(x), float(x - size[0])))
            ys.update((float(y), float(y + size[1])))
        points.update((x, y) for x in xs for y in ys)
        projected = None
        for corner_x, corner_y in sorted(points, key=lambda point: (-point[1], point[0])):
            spot = _Slot(corner_x, corner_y, size[0], size[1])
            fits = (
                spot.left >= left_edge - _TOUCH
                and spot.right <= right_edge + _TOUCH
                and spot.back <= back_edge + _TOUCH
                and spot.front >= front_edge - _TOUCH
            )
            if not fits or not all(_apart(spot, other, spacing) for other in taken):
                continue
            rectangle = box(spot.left, spot.front, spot.right, spot.back)
            if allowed.covers(rectangle):
                return spot
            if projected is None:
                projected = footprint(mesh)
            moved = shift_polygon(
                projected,
                xoff=spot.left - mesh.bounds.minimum[0],
                yoff=spot.front - mesh.bounds.minimum[1],
            )
            if allowed.covers(moved):
                return spot
        return None

    def settle(mesh: MeshData) -> tuple[int, _Slot | None]:
        """Die erste Platte mit Platz und die Stelle darauf — oder keine Stelle.

        **Eine leere Platte nimmt den Körper, auch wenn er nicht passt.** Ein
        Körper, der tiefer ist als das Bett, passt auch auf eine leere Platte
        nicht — und wanderte dann auf die nächste, die genauso wenig hilft.
        Gemessen an zwei Sockeln von 231 mm Tiefe auf einem 220er Bett und zwei
        Platten: beide landeten auf Platte 2, aufeinandergestapelt und über den
        Rand hinaus, während Platte 1 leer blieb. Wo nichts liegt, ist die
        nächste Platte kein besserer Ort — der Befund aus
        :func:`check_build_volume` sagt stattdessen, was wirklich hilft:
        teilen, verkleinern, anderes Profil. Sind alle erlaubten Platten
        angefangen, bleibt der Körper bei der letzten.
        """
        index = 0
        while index < len(opened) or len(opened) < plates:
            if index == len(opened):
                opened.append(list(held.get(index, ())))
            spot = place(mesh, opened[index])
            if spot is not None or not opened[index]:
                return index, spot
            index += 1
        return len(opened) - 1, None

    for mesh in meshes:
        size = mesh.bounds.size
        plate, spot = settle(mesh)
        taken = opened[plate]
        if spot is None:
            spot = _beyond_the_edge(taken, size, corner, spacing)

        target = (
            spot.left + size[0] / 2.0,
            spot.back - size[1] / 2.0,
            mesh.bounds.size[2] / 2.0,
        )
        offset = tuple(target[index] - mesh.bounds.centre[index] for index in range(3))
        body = mesh.raw.copy()
        transform.moved(body, translation((offset[0], offset[1], offset[2])))
        arranged.append(mesh.replacing(body))
        assigned.append(plate)
        taken.append(spot)

    # Gepackt ist in der Ecke, gelegt wird in der Mitte — und geprüft wird
    # danach, damit Bauraumbefunde die Lage nennen, die der Kunde sieht. Wo
    # fremde Körper liegen bleiben, gehört die Mitte ihnen mit; dort wird die
    # gepackte Lage nicht mehr verschoben.
    if not occupied:
        arranged = _into_the_middle(
            arranged, assigned, area, allowed, printable_area(profile.printer)
        )

    if centre_slender:
        arranged = _slender_nearer_the_middle(arranged, assigned, area, allowed, spacing, occupied)

    findings.extend(check_build_volume(arranged, profile, assigned, object_ids, margin=edge_margin))
    if len(opened) >= plates and _overfull(arranged, assigned, profile, edge_margin):
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


def _slender_nearer_the_middle(
    arranged: list[MeshData],
    assigned: list[int],
    area: Any,
    allowed: Any,
    spacing: float,
    occupied: Sequence[tuple[MeshData, int]],
) -> list[MeshData]:
    """Verbessert freie Mittellagen auf derselben Platte, ohne Nachbarn zu verschieben.

    Es gilt dieselbe Schlankheit wie im Druckrat. Die bestehende Belegung
    entscheidet über Plattenzahl und Reihenfolge; eine gleich gute oder nicht
    sicher freie Mittellage bleibt unverändert. Sperrzonen und feste Körper
    begrenzen dieselbe Suche wie beim Hinzufügen eines Modells.
    """
    if area.is_empty:
        return arranged
    left, front, right, back = area.bounds
    centre = ((left + right) / 2.0, (front + back) / 2.0)
    moved = list(arranged)
    for index, original in enumerate(arranged):
        if not is_slender(original.bounds) or not fits_xy(original, area):
            continue
        plate = assigned[index]
        neighbours = [
            mesh for at, mesh in enumerate(moved) if at != index and assigned[at] == plate
        ]
        neighbours.extend(mesh for mesh, at in occupied if at == plate)
        taken = [
            _Slot(mesh.bounds.minimum[0], mesh.bounds.maximum[1], *mesh.bounds.size[:2])
            for mesh in neighbours
        ]
        spot = _nearest_the_middle(original.bounds.size, taken, area, allowed, spacing)
        if spot is None:
            continue
        before = original.bounds.centre
        after = (spot.left + spot.width / 2.0, spot.back - spot.depth / 2.0)
        old_distance = math.hypot(before[0] - centre[0], before[1] - centre[1])
        new_distance = math.hypot(after[0] - centre[0], after[1] - centre[1])
        if new_distance >= old_distance - _TOUCH:
            continue
        body = original.raw.copy()
        transform.moved(body, translation((after[0] - before[0], after[1] - before[1], 0.0)))
        moved[index] = original.replacing(body)
    return moved


def first_free_spot(
    body: BoundingBox,
    profile: Profile,
    occupied: Sequence[tuple[BoundingBox, int]],
    *,
    spacing: float = ARRANGE_SPACING,
    plates: int | None = None,
    avoid: Collection[int] = (),
) -> tuple[Vec3, int, bool]:
    """Wohin ein weiteres Modell kommt, ohne dass etwas anderes sich bewegt (§17.1, §29).

    **Der Anlass** (Robert, 28.09.2026: „wenn wir ein weiteres modell
    hinzufügen zu einem schon vorhandenen landet es immer außerhalb, obwohl auf
    den anderen platten noch platz ist"). Ein weiteres Modell blieb an seinen
    Dateikoordinaten, und die liegen selten dort, wo auf dem Bett Platz ist.

    Platte für Platte in ihrer Reihenfolge wie :func:`arrange_on_bed`, auf der
    ersten mit Platz an die freie Stelle, die der Plattenmitte am nächsten
    liegt (:func:`_nearest_the_middle`, Entscheidung zu RM-306), mit
    ``spacing`` zu jedem Nachbarn und zum Rand. Bis RM-306 war es die
    hinterste, dann linkeste Stelle der Anordnung, und ein zweites Modell
    stand in der Ecke statt neben dem ersten. Was schon liegt (``occupied``,
    Grenzen und Platte), bleibt liegen und belegt seinen Platz auf seiner
    Platte. Eine leere Platte nimmt das Modell immer; mittig liegt es dort in
    jeder Achse, in der es auf die Fläche passt (:func:`_into_the_middle`).
    Passt es auf keine belegte Platte, kommt es auf die nächste (§17.1), auch
    hinter der zwölften. Nur ein ausdrücklich begrenzter Auftrag setzt
    ``plates``; ist keine mehr erlaubt, liegt es neben der letzten, ohne
    Überschneidung. ``avoid`` nennt Platten mit fremdem Filament.

    ``body`` sind die Grenzen des ganzen Modells: Eine Baugruppe wird als
    Ganzes gelegt, die Teile behalten ihre Lage zueinander. Gelegt wird ein
    Quader aus diesen Grenzen, nie die Form — der Platz eines Quaders ist nie
    zu knapp bemessen, und für einen exakten Körper muss nichts vernetzt werden.
    Zurück kommen der Versatz, der das Modell dorthin legt und **aufsetzt**,
    die Platte und ob **nur die Grenze der Plattenzahl** es über die
    Druckfläche hinaus stehen lässt: Es passte auf ein leeres Bett, aber keine
    erlaubte Platte hatte Platz. Ein Modell, das auf kein Bett passt, ist
    kein Platzmangel — das sagt die Bauraumprüfung (Review N6). Gerechnet wird
    einmal: :func:`placed_at_free_spot` hält die Stelle im Schritt fest.
    """

    def block(bounds: BoundingBox) -> MeshData:
        # Eine flache Fläche ist in einer Achse null breit; ein Quader braucht
        # in jeder Achse etwas, sonst hat er keine Seiten.
        low = [float(value) for value in bounds.minimum]
        high = [max(float(bounds.maximum[axis]), low[axis] + EPS_GEOM) for axis in range(3)]
        return MeshData.of(trimesh.creation.box(bounds=[low, high]))

    moving = block(body)
    size = moving.bounds.size
    area = printable_area(profile.printer, margin=spacing)
    allowed = area.buffer(EPS_GEOM, join_style="mitre")
    low = moving.bounds.minimum
    last = max((plate for _bounds, plate in occupied), default=-1)
    final = last + 1 if plates is None else min(last + 1, max(plates, 1) - 1)
    plate = 0
    while True:
        if plate in avoid and plate < final:
            plate += 1
            continue
        standing = [bounds for bounds, at in occupied if at == plate]
        if not standing:
            # Eine leere Platte nimmt es mittig, wie die Anordnung.
            placed = arrange_on_bed([moving], profile, spacing, plates=1).meshes[0]
            break
        taken = [
            _Slot(
                float(bounds.minimum[0]),
                float(bounds.maximum[1]),
                float(bounds.maximum[0] - bounds.minimum[0]),
                float(bounds.maximum[1] - bounds.minimum[1]),
            )
            for bounds in standing
        ]
        spot = (
            _nearest_the_middle(size, taken, area, allowed, spacing)
            if size[2] <= printable_height(profile.printer) + EPS_GEOM
            else None
        )
        if spot is not None:
            shift = (float(spot.left - low[0]), float(spot.front - low[1]), -float(body.minimum[2]))
            return shift, plate, False
        if plate == final:
            # Keine erlaubte Platte hat Platz: neben die letzte, ohne
            # Überschneidung — so, wie die Anordnung es täte.
            held = [(block(bounds), 0) for bounds in standing]
            placed = arrange_on_bed([moving], profile, spacing, plates=1, occupied=held).meshes[0]
            break
        plate += 1
    shift = (
        float(placed.bounds.minimum[0] - low[0]),
        float(placed.bounds.minimum[1] - low[1]),
        -float(body.minimum[2]),
    )
    crowded = (
        bool(standing)
        and not fits_on_bed(placed, profile.printer)
        and _fits_alone(moving, profile, spacing)
    )
    return shift, plate, crowded


#: Wie viele Kandidaten :func:`_nearest_the_middle` auf einmal gegen die
#: liegenden Körper prüft. Nur eine Speichergrenze: Die Kandidaten kommen der
#: Nähe nach, die erste freie entscheidet, und meist liegt sie im ersten Block.
_SPOT_BATCH: Final = 4096

#: Wie viele freie Kandidaten auf einmal gegen eine Fläche mit Sperrzone
#: geprüft werden — die Fläche zu fragen kostet je Rechteck mehr als der
#: Abstand zu allen Nachbarn zusammen.
_SPOT_BITE: Final = 64


def _nearest_the_middle(
    size: Vec3, taken: Sequence[_Slot], area: Any, allowed: Any, spacing: float
) -> _Slot | None:
    """Die freie Stelle, deren Mitte der Plattenmitte am nächsten liegt (RM-306).

    **Der Anlass** (Robert, 09.09.2026: „startpunkt mitte"; Entscheidung zu
    RM-306): Ein weiteres Modell kam an die hinterste, dann linkeste freie
    Stelle — auf dem 256er Bett 113 mm links und 113 mm hinter einem mittigen
    ersten, am Rand des Bildes und weit weg von der Hand. Nahe der Mitte steht
    es im Bild und ist zu erreichen.

    **Die Kandidaten sind exakt, kein Raster.** Erlaubt ist eine Mitte, deren
    Rechteck in der Fläche liegt und jedem liegenden Rechteck um ``spacing``
    ausweicht. Die nächste solche Mitte ist die Plattenmitte selbst oder liegt
    auf dem Rand des Erlaubten — und der besteht aus achsparallelen Strecken:
    den Seiten jedes Nachbarn, um Abstand und halbe Größe hinausgerückt, den
    Seiten der Fläche und den Ecken ihrer Kontur (Sperrzonen). Der nächste
    Punkt einer solchen Strecke ist ihr Fußpunkt (eine Koordinate der Mitte)
    oder ein Endpunkt (zwei Randlinien). Alle Paare aus diesen Linien und der
    Mitte enthalten also die nächste Stelle. Nur eine schräge Kontur — ein
    rundes Bett — hat Randpunkte dazwischen; für sie kommt ein Raster im
    Schritt des Abstands dazu, damit ein Modell dort höchstens einen halben
    Abstand weiter liegt als nötig.

    Bei gleicher Entfernung entscheidet, was der Kunde in der Vorderansicht
    besser sieht: neben dem Vorhandenen statt dahinter oder davor, dann rechts
    (Leserichtung), dann hinten. Vektorisiert und blockweise der Nähe nach
    geprüft, damit es auch neben Dutzenden Körpern beim Einlesen nicht zählt.
    """
    import shapely

    if area.is_empty:
        return None
    left_edge, front_edge, right_edge, back_edge = area.bounds
    half = (size[0] / 2.0, size[1] / 2.0)
    middle = ((left_edge + right_edge) / 2.0, (front_edge + back_edge) / 2.0)
    reach = (
        (left_edge + half[0], right_edge - half[0]),
        (front_edge + half[1], back_edge - half[1]),
    )
    if any(start > end + _TOUCH for start, end in reach):
        return None
    sides = np.array(
        [[slot.left, slot.right, slot.front, slot.back] for slot in taken], dtype=float
    ).reshape(-1, 4)
    corners = get_coordinates(area)
    lines: list[np.ndarray] = []
    for axis in (0, 1):
        start, end = reach[axis]
        parts = [
            np.array([middle[axis], start, end]),
            corners[:, axis] - half[axis],
            corners[:, axis] + half[axis],
            sides[:, 2 * axis] - spacing - half[axis],
            sides[:, 2 * axis + 1] + spacing + half[axis],
        ]
        if spacing > 0.0:
            count = math.ceil(max(end - middle[axis], middle[axis] - start) / spacing)
            parts.append(middle[axis] + spacing * np.arange(-count, count + 1))
        values = np.concatenate(parts)
        values = values[(values >= start - _TOUCH) & (values <= end + _TOUCH)]
        lines.append(np.unique(np.clip(values, min(start, end), max(start, end))))
    across, along = (grid.ravel() for grid in np.meshgrid(lines[0], lines[1]))
    off_x, off_y = across - middle[0], along - middle[1]
    order = np.lexsort(
        (
            -along,
            -across,
            np.round(np.abs(off_y) / EPS_GEOM),
            np.round(np.hypot(off_x, off_y) / EPS_GEOM),
        )
    )
    plain = bool(area.equals(box(*area.bounds)))
    for first in range(0, len(order), _SPOT_BATCH):
        chosen = order[first : first + _SPOT_BATCH]
        left = across[chosen] - half[0]
        right = across[chosen] + half[0]
        front = along[chosen] - half[1]
        back = along[chosen] + half[1]
        free = np.all(
            (right[:, None] + spacing <= sides[None, :, 0] + _TOUCH)
            | (sides[None, :, 1] + spacing <= left[:, None] + _TOUCH)
            | (sides[None, :, 3] + spacing <= front[:, None] + _TOUCH)
            | (back[:, None] + spacing <= sides[None, :, 2] + _TOUCH),
            axis=1,
        )
        hits = np.flatnonzero(free)
        # Die Fläche fragt nur, wer bis hierher frei ist, und das in kleinen
        # Bissen: Meist ist schon der erste Kandidat der richtige.
        for start in range(0, hits.size, _SPOT_BITE):
            bite = hits[start : start + _SPOT_BITE]
            if not plain:
                rectangles = shapely.box(left[bite], front[bite], right[bite], back[bite])
                bite = bite[shapely.covers(allowed, rectangles)]
            if bite.size:
                index = int(bite[0])
                return _Slot(float(left[index]), float(back[index]), size[0], size[1])
    return None


def standing_in(scene: Scene, ignore: Collection[ObjectId] = ()) -> list[tuple[BoundingBox, int]]:
    """Was in der Szene liegen bleibt: Grenzen und Platte jedes Körpers.

    ``ignore`` nennt die Körper, die gerade gelegt werden — *Auf Maß bringen*
    ersetzt seinen Eingang, und der belegt keinen Platz neben sich selbst.
    """
    return [
        (entry.mesh.bounds, entry.plate)
        for key, entry in scene.objects.items()
        if key not in ignore
    ]


#: Die Felder, in denen ein Schritt seine freie Stelle festhält (§17.1,
#: Schritt 6). Solange sie leer sind, liest ``free_spot`` die Szene
#: (``ParamSpec.answered_by``); danach nie wieder.
SPOT_FIELDS: Final = ("spot_x", "spot_y")

#: Die Grenze der Felder ``spot_x``/``spot_y`` in beide Richtungen, in mm.
#: Weit gefasst, denn gefüllt werden sie von der Suche, nicht vom Kunden: Die
#: Plattenreihe und ein Modell, das auf kein Bett passt, liegen weit draußen,
#: und eine Stelle, die ihr eigenes Feld abwiese, hielte die Kette am
#: Ladeschritt an (Review N3: 2,5 m lang, Mitte bei 1127 mm).
SPOT_LIMIT: Final = 100_000.0


def free_spot_param(doc: TranslatableText, placement: ParamPlacement = "front") -> Any:
    """Der Schalter *An eine freie Stelle legen* — an Ladeschritt und *Auf Maß bringen*."""
    return param(
        title=_("An eine freie Stelle legen"),
        default=False,
        reads_scene=True,
        answered_by=SPOT_FIELDS,
        placement=placement,
        doc=doc,
    )


def spot_param(axis: Literal["x", "y"]) -> Any:
    """Eine Achse der festgehaltenen Stelle: die Mitte des Modells in der Aufsicht."""
    return param(
        title=_("Mitte X") if axis == "x" else _("Mitte Y"),
        default=None,
        optional=True,
        unit="mm",
        minimum=-SPOT_LIMIT,
        maximum=SPOT_LIMIT,
        placement="advanced",
        depends_on=("free_spot", (True,)),
        doc=_(
            "Wo die Mitte des Modells liegt. Die freie Stelle wird einmal gesucht und "
            "hier festgehalten; leer sucht sie neu."
        ),
    )


def spot_plate_param() -> Any:
    """Die Platte der festgehaltenen Stelle, gezählt wie im Plattenwähler."""
    return param(
        title=_("Platte"),
        default=1,
        minimum=1,
        placement="advanced",
        depends_on=("free_spot", (True,)),
        doc=_("Auf welcher Druckplatte das Modell liegt."),
    )


@dataclass(frozen=True, slots=True)
class FreeSpot:
    """Wohin ein Schritt sein Modell legt — und was er darüber sagt."""

    offset: Vec3
    """Der Versatz der ganzen Gruppe: zur Stelle und aufgesetzt."""
    plate: int
    """Um so viele Platten rückt jedes Teil; ohne Plattenaufteilung die Platte."""
    answered: dict[str, float | int]
    """Die frisch gerechnete Stelle für ``OpResult.answered``; leer, wenn sie
    schon im Schritt stand."""
    findings: list[Finding]


def filament_groups(profile: Profile, objects: Sequence[SceneObject]) -> dict[str, int] | None:
    """Die bestehenden Filamentgruppen der Anordnung, wenn Düsen fehlen (§29).

    Ein Teil mit mehreren Filamenten bleibt zusammen; seine erste Spule
    bestimmt die Gruppe. Identität und Reihenfolge kommen aus der Übergabe.
    """
    from app.core.export.writer import plates_by_material

    groups = plates_by_material(list(objects))
    if len(set(groups.values())) <= max(1, profile.printer.nozzles):
        return None
    return groups


def _foreign_filament_plates(
    profile: Profile, standing: Sequence[SceneObject], incoming: Sequence[SceneObject]
) -> set[int]:
    """Welche belegten Platten ein ungeteilter Import nicht dazunehmen kann."""
    from app.core.export.threemf import (
        AssemblyPart,
        SlotKey,
        assembly_slots,
        slot_identity,
        slots_for_object,
    )
    from app.core.geom.attributes import used_slots

    def filaments(entry: SceneObject) -> set[SlotKey]:
        mesh = as_mesh_data(entry.mesh)
        active = set(used_slots(mesh))
        part = AssemblyPart(mesh=mesh, slots=slots_for_object(entry))
        return {slot_identity(slot) for slot in assembly_slots(part) if slot.index in active}

    # Beim Import zählen alle tatsächlich benutzten Spulen, auch innerhalb
    # eines Körpers. Alte Deklarationen ohne Flächen brauchen keine Düse.
    # Die bestehende Anordnungsgruppierung bleibt für gespeicherte Schritte.
    arriving = {key for entry in incoming for key in filaments(entry)}
    on_plate: dict[int, set[SlotKey]] = {}
    for entry in standing:
        on_plate.setdefault(entry.plate, set()).update(filaments(entry))
    return {
        plate
        for plate, present in on_plate.items()
        if present != arriving and len(present | arriving) > max(1, profile.printer.nozzles)
    }


def placed_at_free_spot(
    group: BoundingBox,
    profile: Profile,
    scene: Scene,
    *,
    spot: tuple[float | None, float | None, int],
    ignore: Collection[ObjectId] = (),
    keep_layout: bool = False,
    objects: Sequence[SceneObject] = (),
) -> FreeSpot:
    """Die freie Stelle, **einmal gerechnet und dann festgehalten** (§17.1, §15.7).

    Entscheidung Robert: Die Stelle wird beim ersten Laden gerechnet und im
    Schritt festgehalten, auf demselben Weg wie die beantwortete Einheitenfrage
    (``OpResult.answered``). Danach bleibt das Modell liegen, wie in jedem
    Slicer — wird davor etwas gelöscht oder geändert oder der Drucker
    gewechselt, wandert es nicht, und eine Bohrung daran trifft weiter.

    ``spot`` ist die festgehaltene Mitte in X und Y und die Platte (ab 1); mit
    beiden Achsen gesetzt wird nur dorthin gelegt und aufgesetzt, ohne die Szene
    zu lesen. ``keep_layout`` gilt einer Datei mit mehreren Platten: Sie behält
    ihre Aufteilung und rückt hinter die letzte belegte Platte.
    """
    centre = (float(group.centre[0]), float(group.centre[1]))
    seat = -float(group.minimum[2])
    spot_x, spot_y, spot_plate = spot
    if spot_x is not None and spot_y is not None:
        target, plate = (spot_x, spot_y), max(spot_plate, 1) - 1
        return FreeSpot((target[0] - centre[0], target[1] - centre[1], seat), plate, {}, [])
    findings: list[Finding] = []
    if keep_layout:
        plate = max((at for _bounds, at in standing_in(scene, ignore)), default=-1) + 1
        target = centre
        if plate:
            findings.append(
                Finding(
                    code="arrange.plates_behind",
                    severity="info",
                    message=_(
                        "Die Platten der Datei kommen hinter die vorhandenen, ab Platte {number}.",
                        number=plate + 1,
                    ),
                    values={"plate": plate + 1},
                )
            )
    else:
        standing = [entry for key, entry in scene.objects.items() if key not in ignore]
        avoid = _foreign_filament_plates(profile, standing, objects) if objects else set()
        shift, plate, crowded = first_free_spot(
            group, profile, [(entry.mesh.bounds, entry.plate) for entry in standing], avoid=avoid
        )
        target = (centre[0] + shift[0], centre[1] + shift[1])
        moved = plate > 0 or not (is_close(shift[0], 0.0) and is_close(shift[1], 0.0))
        if crowded:
            findings.append(
                Finding(
                    code="arrange.no_free_spot",
                    severity="warning",
                    message=_(
                        "Auf keiner Druckplatte war Platz für das Modell; es liegt auf "
                        "Platte {number} und steht über die Druckfläche hinaus.",
                        number=plate + 1,
                    ),
                    values={"plate": plate + 1},
                    suggestions=(ARRANGE_ON_BED,),
                )
            )
        elif moved:
            findings.append(
                Finding(
                    code="arrange.free_spot",
                    severity="info",
                    message=_(
                        "Das Modell kam an die freie Stelle, die der Mitte von Platte "
                        "{number} am nächsten liegt.",
                        number=plate + 1,
                    ),
                    values={"plate": plate + 1},
                )
            )
    return FreeSpot(
        (target[0] - centre[0], target[1] - centre[1], seat),
        plate,
        {"spot_x": target[0], "spot_y": target[1], "spot_plate": plate + 1},
        findings,
    )


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
    # Ein einzelner Körper ist nie Gedränge — und ohne diese Zeile fragte
    # :func:`_fits_alone` über seine Probeanordnung wieder hierher.
    if len(on_last) < 2 or sum(_fits_alone(mesh, profile, spacing) for mesh in on_last) < 2:
        return False
    # Ein schmalerer Rand ist kein Gedränge: Das Teil liegt ganz auf dem Bett.
    return any(
        finding.code != "arrange.narrow_margin"
        for finding in check_build_volume(on_last, profile, margin=spacing)
    )


def _fits_alone(mesh: MeshData, profile: Profile, spacing: float) -> bool:
    """Läge dieser Körper allein auf einem leeren Bett ganz auf der Druckfläche?

    Nicht an seinem Ort: wo er gerade liegt, entscheidet die Anordnung, und die
    ist genau die Frage. Was hier zählt, ist, ob eine eigene Platte ihm
    überhaupt etwas nützen könnte.

    **Gefragt wird die Anordnung selbst**, nicht ein Maß daneben: „passt
    allein" heißt „würde allein passend gelegt". Bis zum 29.09.2026 stand hier
    die Fläche mit vollem Rand — richtig, solange ein Teil, das nur ohne ihn
    passte, in der Packecke über die Kante ragte. Seit RM-229 legt die
    Anordnung es mittig mit schmalerem Rand, eine eigene Platte hilft ihm also,
    und der Rat fehlte: Am Minigolf-Satz blieb ein Rumpf von 245 mm Tiefe auf
    dem 256er Bett neben der dritten Platte liegen, ohne dass der Bericht die
    vierte nannte. Dieselbe Frage stellt :func:`first_free_spot`, wenn es
    entscheidet, ob nur die Plattengrenze ein Modell draußen lässt.
    """
    return fits_on_bed(
        arrange_on_bed([mesh], profile, spacing, plates=1).meshes[0], profile.printer
    )


def back_onto_bed(
    mesh: Mesh,
    others: Sequence[MeshData],
    profile: Profile,
    *,
    spacing: float = ARRANGE_SPACING,
) -> tuple[Vec3, list[Finding]]:
    """Der XY-Versatz zu einem freien Platz auf der Druckfläche (§29).

    **Der Anlass** (Robert, 12.09.2026: „wenn ich die Schriftgröße änder passt
    das Druckoptimal ausrichten nicht mehr"). Ein Zug am Gizmo speichert einen
    *Weg*, gemeint war ein *Platz*: Solange sich davor nichts ändert, ist das
    dasselbe. Ändert der Kunde einen Parameter weiter oben, ordnet *Druckoptimal
    ausrichten* neu an — der Körper startet woanders, derselbe Weg wird trotzdem
    daraufgerechnet, und er landet neben dem Bett. Gemessen an einem Schriftzug
    *Solidon3D*, dessen Größe von 100 auf 130 mm ging: ein Buchstabe 70,41 mm
    außerhalb, und aufräumen musste der Kunde von Hand.

    **So wenig bewegen wie nötig.** Erst wird zurückgeschoben — die kürzeste
    Strecke, die den Körper wieder ganz auf die Fläche bringt (das kann
    :func:`placement_offset` bereits, es sortiert seine Kandidaten nach
    Entfernung). Wer ein Teil zwei Millimeter über den Rand zieht, bekommt es um
    zwei Millimeter zurück und nicht quer über die Platte gelegt. Steht an der
    kürzesten Stelle ein anderer Körper, wird stattdessen neu eingeordnet —
    **das gilt aber nur dem Weg zurück**, nicht einer Überschneidung an sich
    (der Absatz am Ende sagt, warum).

    **Und nur auf der eigenen Platte.** ``others`` sind die Körper, die diese
    Platte teilen; um sie herum wird gesucht. Ein Plattenwechsel hinter dem
    Rücken des Kunden findet nicht statt: Ist auf seiner Platte nichts frei,
    bleibt der Körper, wo er ist, und :func:`check_build_volume` sagt es wie
    bisher. Eine Heilung, die schweigend die Platte wechselt, wäre ein Teil,
    das der Kunde beim Drucken nicht wiederfindet.

    Der Versatz ist rein waagerecht. Die Höhe hat *Auf das Bett setzen*, und
    ein bewusst angehobener Körper — für einen Booleschen Schnitt etwa — darf
    davon nicht heruntergezogen werden.

    **Und zwei Körper, die einander durchdringen, bleiben stehen** (Befund
    Robert, 18.09.2026: „beim bewegen und einer Kollision werden die Körper
    versetzt, vllt will man sie aber zusammenhieben zum verschmelzen, so
    nicht möglich"). Bis dahin hielt diese Bindung **zwei** Bedingungen —
    innerhalb der Fläche *und* ohne Überschneidung —, und damit war das
    Zusammenschieben zweier Teile über den Griff nicht mehr zu machen: Wer
    sie ineinanderzog, bekam sie auseinandergeschoben, bevor er *Vereinigen*
    oder *Weich verschmelzen* anklicken konnte. Zwei Körper am selben Ort
    sind eine **Absicht**; ein Körper neben dem Bett ist es nie. Gemeldet
    wird die Überschneidung weiterhin — `check_collisions` und
    `scene.evaluate.check_bodies_in_one_place` sagen es, ohne etwas zu
    bewegen.
    """
    area = printable_area(profile.printer)
    body = as_mesh_data(mesh)
    if fits_xy(body, area):
        return (0.0, 0.0, 0.0), []

    nudge = placement_offset(body, profile.printer)
    if nudge is not None:
        offset = (nudge[0], nudge[1], 0.0)
        if not _runs_into(body, offset, others):
            return offset, [
                Finding(
                    code="transform.nudged_onto_bed",
                    severity="info",
                    message=_(
                        "Der Körper ragte über die Druckfläche hinaus und wurde zurückgeschoben."
                    ),
                    values={"distance": format_length(math.hypot(nudge[0], nudge[1]), "mm")},
                )
            ]

    arrangement = arrange_on_bed(
        [body],
        profile,
        spacing,
        plates=1,
        occupied=[(other, 0) for other in others],
    )
    placed = arrangement.meshes[0]
    # Die Befunde der Anordnung bleiben hier: Sie beschreiben einen Probelauf
    # mit einem einzigen Körper und einer einzigen Platte, nicht die Szene.
    if not fits_xy(placed, area):
        return (0.0, 0.0, 0.0), []
    offset = (
        float(placed.bounds.centre[0] - body.bounds.centre[0]),
        float(placed.bounds.centre[1] - body.bounds.centre[1]),
        0.0,
    )
    # Die Suche legt auf Z=0; die tatsächliche Korrektur bewahrt die Höhe.
    # Nur diese endgültige Lage darf als kollisionsfrei gemeldet werden.
    if _runs_into(body, offset, others):
        return (0.0, 0.0, 0.0), []
    return offset, [
        Finding(
            code="transform.rearranged_on_bed",
            severity="info",
            # Nur ein Grund, seit die Überschneidung keinen mehr abgibt: Wer
            # hier ankommt, lag außerhalb der Fläche — innerhalb kehrt die
            # Funktion oben um.
            message=_(
                "Der Körper passte an seiner Stelle nicht mehr auf die "
                "Druckfläche und wurde neu eingeordnet."
            ),
        )
    ]


def _runs_into(body: MeshData, offset: Vec3, others: Sequence[MeshData]) -> bool:
    """Steckt der Körper an der neuen Stelle in einem seiner Nachbarn?

    Paarweise gegen den einen Körper und nicht ``check_collisions`` über die
    ganze Liste: Die Nachbarn untereinander sind nicht die Frage, und ihre
    Befunde gehören nicht in diese Operation.
    """
    moved = body.raw.copy()
    transform.moved(moved, translation(offset))
    shifted = body.replacing(moved)
    return any(check_collisions([shifted, other]) for other in others)


def check_build_volume(
    meshes: Sequence[Mesh],
    profile: Profile,
    plates: list[int] | None = None,
    object_ids: Sequence[ObjectId] | None = None,
    *,
    about_to_write: bool = False,
    margin: float = 0.0,
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
    area = printable_area(profile.printer, margin=margin)
    left, front, right, back = (
        area.bounds if not area.is_empty else printable_area(profile.printer).bounds
    )
    allowed = BoundingBox((left, front, 0.0), (right, back, printable_height(profile.printer)))
    bed = printable_area(profile.printer) if margin > 0.0 else area
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
        if (
            margin > 0.0
            and outside
            and 2 not in outside
            and not _fits_at_all(bounds, allowed, 0.0)
            and fits_xy(mesh, bed)
        ):
            # **Auf dem Bett, nur der Rand ist schmaler** (RM-229): Das Teil
            # passt mit dem gewählten Rand nirgends hin, liegt aber ganz auf
            # der Druckfläche — :func:`_into_the_middle` hat es dorthin gelegt.
            # „Steht über den Bauraum hinaus" wäre falsch und schickte den
            # Kunden zum Verkleinern; was fehlt, ist der Rand, und wie viel
            # davon bleibt, steht dabei.
            bed_left, bed_front, bed_right, bed_back = bed.bounds
            narrow: dict[str, Any] = {
                "margin": max(
                    0.0,
                    min(
                        float(bounds.minimum[0]) - bed_left,
                        bed_right - float(bounds.maximum[0]),
                        float(bounds.minimum[1]) - bed_front,
                        bed_back - float(bounds.maximum[1]),
                    ),
                )
            }
            if object_id is None:
                narrow["object"] = index
            if plates is not None and index < len(plates):
                narrow["plate"] = plates[index] + 1
            findings.append(
                Finding(
                    code="arrange.narrow_margin",
                    severity="info",
                    message=_("Ein Objekt passt nur mit schmalerem Rand auf die Druckfläche."),
                    object_id=object_id,
                    values=narrow,
                )
            )
            continue
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
            code, message = _verdict_for(bounds, allowed, outside)
            findings.append(
                Finding(
                    code=code,
                    severity=_severity_for(bounds, allowed, about_to_write),
                    message=message,
                    object_id=object_id,
                    values=values,
                )
            )
        elif not fits_xy(mesh, area):
            movable = placement_offset(mesh, profile.printer, margin=margin) is not None
            values = {"margin": margin}
            if object_id is None:
                values["object"] = index
            if plates is not None and index < len(plates):
                values["plate"] = plates[index] + 1
            findings.append(
                Finding(
                    code="arrange.off_the_plate" if movable else "arrange.out_of_build_volume",
                    severity="info" if movable and not about_to_write else "warning",
                    message=_("Ein Objekt liegt außerhalb der freigegebenen Druckfläche."),
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


def check_join_path(
    moving: MeshData,
    fixed: MeshData,
    direction: Vec3,
    distance: float,
    *,
    steps: int = 24,
) -> list[Finding]:
    """Kommt das Teil dorthin, wo es hingehört — oder nur die Endlage stimmt?

    :func:`check_collisions` beantwortet eine Frage über **einen Zustand**: Wo
    stehen die Körper sich im Weg? Ein gefügtes Teil hat aber zwei Fragen, und
    die zweite ist die, an der ein Entwurf scheitert, nachdem die erste grün
    war: **Gelangt es überhaupt in diese Lage?**

    Der Anlass ist eine Rinne, deren Segmente sich nicht zusammenstecken
    ließen (08.09.2026). Gerechnet war die Passung in der Breite; in der Höhe
    stießen zwei Böden stirnseitig aufeinander, und der Zapfen kam keinen
    Millimeter hinein. Am gedruckten Teil hat es eine Minute gedauert, das zu
    sehen — am Bildschirm hatte es niemand gefragt.

    ``moving`` steht in seiner **Endlage**; von dort wird es um ``distance``
    entgegen ``direction`` zurückgesetzt und in ``steps`` Schritten wieder
    herangeführt. Gemessen wird an jeder Stelle das geteilte Volumen mit
    ``fixed``.

    Zwei Befunde, und die Unterscheidung zwischen ihnen ist der Kern:

    * **Die Endlage ist besetzt** — die Teile passen dort nicht zusammen. Das
      ist eine Sperre, gleich was auf dem Weg geschah.
    * **Die Endlage ist frei, unterwegs war sie es nicht** — dann muss auf dem
      Weg etwas ausweichen. Bei einer Schnappverbindung ist das ihre Bauart
      und richtig; das Maß dazu sagt, wie weit sich etwas aufbiegen muss.

    Was hier **nicht** entschieden wird, ist, ob dieses Ausweichen das
    Material aushält — dafür fehlen dem Materialprofil die mechanischen
    Kennwerte. Die Zahl steht im Befund, damit sie jemand gegen die
    Federrechnung halten kann.

    **Und ein freier Weg wird gesagt, nicht erschlossen** (§2.7). Bis zum
    13.09.2026 kam bei freiem Weg eine leere Liste zurück, und der
    Prüfbericht zeigte nach *Fügeweg prüfen* genau das, was vorher dastand —
    der Kunde hatte eine Prüfung ausgelöst und musste aus dem Fehlen eines
    Fehlers schließen, dass der Weg frei ist. ``join.clear`` nennt Strecke,
    Richtung und Schrittzahl, damit die Antwort im Bericht steht.

    Offene Körper haben kein Innen: Wo :func:`shared_volume` nichts entscheiden
    kann, bleibt die Prüfung stumm, statt eine Zahl zu erfinden — dort gilt
    der ``caveat`` der Operation.
    """
    if not (moving.is_watertight and fixed.is_watertight):
        return []
    if steps < 1 or distance <= EPS_GEOM:
        return []

    way = np.asarray(direction, dtype=float)
    length = float(np.linalg.norm(way))
    if length <= EPS_GEOM:
        return []
    way = way / length

    findings: list[Finding] = []
    end = shared_volume(moving.raw, fixed.raw)
    if end > EPS_GEOM:
        return [
            Finding(
                code="join.blocked",
                severity="error",
                message=_(
                    "Die Teile überschneiden sich schon in ihrer Endlage. Geben Sie "
                    "einem der beiden Spiel, dann prüft Solidon den Weg dorthin."
                ),
                values={"shared": format_volume(end)},
                # Regel 17: Das Maß, das Spiel gibt, steht in einem früheren
                # Schritt — der Verlauf zeigt ihn.
                suggestions=(SHOW_HISTORY,),
            )
        ]

    # Rückwärts vom Ziel: Schritt ``steps`` ist die Endlage, Schritt 0 der
    # Anfang. Der Anfang selbst wird nicht gemessen — dort stehen die Teile
    # noch auseinander, und ein Treffer wäre eine Aussage über die Lage, aus
    # der jemand startet, nicht über das Fügen.
    worst = 0.0
    worst_at = 0.0
    for step in range(1, steps):
        back = distance * (steps - step) / steps
        probe = moving.raw.copy()
        probe.apply_translation(-way * back)
        shared = shared_volume(probe, fixed.raw)
        if shared > worst:
            worst = shared
            worst_at = back

    if worst > EPS_GEOM:
        findings.append(
            Finding(
                code="join.interference",
                severity="info",
                message=_("Auf dem Fügeweg müssen sich die Teile aneinander vorbeidrücken."),
                values={"shared": format_volume(worst), "at": round(worst_at, 2)},
            )
        )
    else:
        axis = _axis_name(way)
        findings.append(
            Finding(
                code="join.clear",
                severity="info",
                message=_(
                    "Der Fügeweg ist frei: {length} entlang {axis}, in {steps} Schritten "
                    "keine Überschneidung.",
                    length=format_length(distance),
                    axis=axis,
                    steps=steps,
                ),
                values={"length_mm": distance, "axis": axis, "steps": steps},
            )
        )
    return findings


def _axis_name(way: np.ndarray) -> str:
    """Eine Richtung, wie der Kunde sie liest: ``X``, ``-Z`` — oder der Vektor.

    Die Operation schiebt immer entlang einer Hauptachse, und so steht es im
    Befund. Ein freier Vektor aus dem Kern wird mit seinen Komponenten
    genannt, statt auf die nächste Achse gerundet zu werden.
    """
    for axis, normal in AXIS_NORMALS.items():
        # ``rtol=0.0``: Sonst trägt ``allclose`` numpys Vorgabe von 1e-5 mit,
        # und die Schranke wäre nicht EPS_GEOM, sondern EPS_GEOM plus 1e-5.
        if np.allclose(way, normal, rtol=0.0, atol=EPS_GEOM):
            return axis.upper()
        if np.allclose(way, -np.asarray(normal), rtol=0.0, atol=EPS_GEOM):
            return f"-{axis.upper()}"
    # ``round`` vor dem ``+ 0.0``: Eine Komponente von -1e-9 schriebe sich
    # sonst als „-0.00" — dieselbe Regel wie in ``units.format_length``.
    return "(" + " | ".join(f"{round(float(value), 2) + 0.0:.2f}" for value in way) + ")"


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
        distance = surface_gap(first, second, clearance)
    except (*PROGRAMMING_ERRORS, *kernel_process.NOT_A_KERNEL_FAILURE):
        raise
    except Exception:  # eine Abstandsanfrage an einen kaputten Körper scheitert auf eigene Arten
        return None
    return distance < clearance if distance is not None else None


def _boxes_overlap(first: BoundingBox, second: BoundingBox, clearance: float) -> bool:
    for axis in range(3):
        if first.maximum[axis] + clearance <= second.minimum[axis]:
            return False
        if second.maximum[axis] + clearance <= first.minimum[axis]:
            return False
    return True
