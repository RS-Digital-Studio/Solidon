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
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

import numpy as np
from shapely import get_coordinates
from shapely.affinity import translate as shift_polygon
from shapely.geometry import box

from app.core.build_area import (
    fits_xy,
    footprint,
    placement_offset,
    printable_area,
    printable_height,
)
from app.core.deferred import trimesh
from app.core.errors import CORRECT_INPUT, PROGRAMMING_ERRORS, ValidationError
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    BooleanKind,
    boolean,
    shared_volume,
    without_effect,
)
from app.core.geom.measure import surface_gap
from app.core.geom.mesh import MeshData, as_mesh_data, concatenated, ray_hit_distances
from app.core.geom.section import SectionPlane, cut
from app.core.geom.transform import Axis, translation
from app.core.knowledge.profiles import resolve_tolerance
from app.core.types import (
    BoundingBox,
    Finding,
    Mesh,
    ObjectId,
    PlaneFrame,
    Profile,
    Quality,
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


def over_the_edge(
    mesh: HasBounds,
    position: Vec3,
    axis: Axis,
    diameter: float,
    *,
    body: MeshData | None = None,
) -> list[Finding]:
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
    return over_the_edge_along(mesh, position, vector, diameter, body=body)


#: Wie fein die Mündung abgetastet wird, wenn der Hüllquader Verdacht meldet.
#:
#: Zwölf Punkte auf dem Kreis und Schritte von einem halben Radius in die Tiefe:
#: Weniger übersieht eine Kante, die zwischen zwei Punkten hindurchläuft, mehr
#: kostet nur Zeit an einer Frage, die im Regelfall gar nicht gestellt wird.
_RIM_POINTS: Final = 12
_RIM_STEPS: Final = 16


def _flank_is_open(body: MeshData, position: Vec3, unit: Any, radius: float) -> bool:
    """Ob die Bohrung wirklich eine offene Flanke hinterlässt.

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
    # Zwei Vektoren quer zur Achse — der Kranz liegt in ihrer Ebene.
    helper = np.array([0.0, 0.0, 1.0]) if abs(float(axis[2])) < 0.9 else np.array([1.0, 0.0, 0.0])
    first = np.cross(axis, helper)
    first /= float(np.linalg.norm(first))
    second = np.cross(axis, first)
    angles = np.linspace(0.0, 2.0 * math.pi, _RIM_POINTS, endpoint=False)
    rim = radius * (np.cos(angles)[:, None] * first + np.sin(angles)[:, None] * second)
    step = reach / _RIM_STEPS
    depths = np.concatenate(
        (np.arange(1, _RIM_STEPS + 1) * step, np.arange(1, _RIM_STEPS + 1) * -step)
    )
    samples = np.asarray(position, dtype=float) + rim[None, :, :] + depths[:, None, None] * axis
    flat = samples.reshape(-1, 3)
    closest, _distance, triangle = on_surface(body.raw, flat)
    normals = np.asarray(body.raw.face_normals)[triangle]
    outward = np.einsum("ij,ij->i", flat - closest, normals)
    inside = (outward <= EPS_GEOM).reshape(len(depths), _RIM_POINTS)
    return not bool(inside.all(axis=1).any())


def over_the_edge_along(
    mesh: HasBounds,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    *,
    body: MeshData | None = None,
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
    if body is not None and not _flank_is_open(body, position, unit, radius):
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
    length = float(np.linalg.norm(vector))
    if not math.isfinite(length) or length <= EPS_GEOM:
        raise bore_geometry_error()
    unit = vector / length
    grows = cut_diameter > previous_diameter
    # Nur ein abziehendes Werkzeug darf über beide Mündungen hinausragen.
    # Beim Verkleinern wird der Ring vereinigt; dieselbe Zugabe würde dann an
    # beiden Außenseiten als tastbarer Kragen Teil des Modells werden.
    height = depth + (BOOLEAN_OVERLAP * 2.0 if through and grows else 0.0)
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
    findings.extend(over_the_edge_along(mesh, position, unit_vector, cut_diameter, body=mesh))
    findings.extend(compensation_findings(diameter, cut_diameter, compensate))
    return BoreResult(
        mesh=resized,
        solver=outcome.solver,
        diameter=cut_diameter,
        findings=findings,
    )


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
    quality: Quality = "fine",
    seed: int | None = None,
    overlap: float = FEATURE_OVERLAP,
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

    ``overlap`` ist die Zugabe auf den Durchmesser, die den Werkzeugkörper von
    der alten Bohrungswand fernhält (:data:`FEATURE_OVERLAP`). Der Aufrufer
    entscheidet, ob es sie braucht: An einer **runden** Bohrung legte sich der
    Körper ohne sie entlang zweier Linien an die Wand; an einem Langloch, das
    schon eines ist, gibt es diese Wand nicht mehr — dort liegen nur die
    Flanken aufeinander, und die rechnet ``manifold3d`` robust (gemessen
    11.09.2026, Stufe ``direct`` über drei Züge). Mit der Zugabe wuchs die
    Breite dagegen bei **jedem** Zug: 5,2057, 5,2213, 5,2371 an einem Loch,
    das 5,1901 gemessen war.
    """
    from app.core.geom.sketch_solid import extrude_profile
    from app.core.sketch.planes import frame_of

    travel = slot_travel(diameter=diameter, length=length)
    if travel <= EPS_GEOM:
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
    span = float(np.linalg.norm(vector))
    if not math.isfinite(span) or span <= EPS_GEOM:
        raise bore_geometry_error()
    if not math.isfinite(depth) or depth <= EPS_GEOM:
        raise bore_geometry_error()
    unit = vector / span
    axis: Vec3 = (float(unit[0]), float(unit[1]), float(unit[2]))
    frame = frame_of(axis, position)
    # **Derselbe Rahmenbau wie beim Bohren, und trotzdem nicht immer dieselbe
    # Zahl.** ``frame_of`` spiegelt seine erste Achse, wenn die Normale kippt
    # (das Kreuzprodukt aus Z und ihr) — und ``drill`` bekommt die Normale der
    # **Fläche**, die Erkennung dagegen eine Achse, deren größte Komponente sie
    # auf positiv normiert. Gemessen an derselben Platte mit 45 Grad: von oben
    # gebohrt 45 Grad, von unten gebohrt 135; an der erkannten Bohrung beide
    # Male 45. Der Winkel zählt hier also gegen den Rahmen der **gemessenen**
    # Achse und ist damit seitenunabhängig — was richtig ist, denn eine
    # erkannte Bohrung hat zwei Mündungen, und welche gemeint ist, hat niemand
    # gesagt (Regel 21).
    to_world = np.eye(4)
    to_world[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    to_world[:3, 3] = np.asarray(position, dtype=float)
    to_local = np.linalg.inv(to_world)
    local_body = mesh.raw.copy()
    local_body.apply_transform(to_local)

    # Nur ein durchgehendes Loch darf über beide Mündungen hinausragen. Bei
    # einer Blindbohrung bliebe der Boden sonst nicht, wo er gemessen wurde —
    # dieselbe Abwägung wie in :func:`resize_bore`.
    height = depth + (BOOLEAN_OVERLAP * 2.0 if through else 0.0)
    tool = extrude_profile(
        slot_profile(
            radius=(diameter + overlap) / 2.0,
            travel=travel,
            angle_deg=angle_deg,
        ),
        height,
        PlaneFrame(
            origin=(0.0, 0.0, -height / 2.0),
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 1.0, 0.0),
            normal=(0.0, 0.0, 1.0),
        ),
    )
    outcome = boolean(
        "difference",
        [mesh.replacing(local_body), MeshData.of(tool)],
        quality=quality,
        seed=seed,
    )
    world_body = outcome.mesh.raw.copy()
    world_body.apply_transform(to_world)
    slotted = outcome.mesh.replacing(world_body)
    findings = list(outcome.findings)
    nothing = without_effect(mesh, slotted, "difference", profile)
    if nothing is not None:
        findings.append(nothing)
    findings.extend(
        edge_findings(
            mesh,
            position=position,
            frame=frame,
            diameter=diameter,
            travel=travel,
            angle_deg=angle_deg,
        )
    )
    return BoreResult(
        mesh=slotted,
        solver=outcome.solver,
        diameter=diameter,
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
        transition = (wide_radius - radius) / math.tan(math.radians(transition_angle / 2.0))
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

#: Wenn jemand ein vorhandenes Langloch **kürzer** einträgt.
#:
#: Der Satz oben deckt den ersten Zug, dieser den zweiten — und der Fall ist
#: der unauffälligere von beiden. Gemessen an einem Langloch von 20,016 mm,
#: auf das jemand 12 einträgt: Abgetragen werden 1,14 mm³, nämlich der
#: Toleranzrand ringsum, und das ist ein Vielfaches der Schwelle, unterhalb
#: derer :func:`without_effect` „hat nichts bewirkt" sagt. Also schwieg sie.
#: Im Verlauf stand ein Schritt, am Teil hatte sich nichts geändert, und die
#: eingetragene Zahl war spurlos verschwunden.
#:
#: Warum es nicht geht, gehört in den Satz: Die Operation schneidet, und
#: Material kommt nicht zurück.
#:
#: **Ohne geschweifte Klammern**, und das ist keine Stilfrage: Ein
#: ``{platzhalter}`` in ``AppError.detail`` bleibt dem Kunden wörtlich stehen —
#: ``dialogs.show_details`` zeigt den Satz, wie er ist, und hängt die ``values``
#: als eigene Zeilen darunter. Die beiden Längen stehen deshalb dort.
SLOT_NOT_SHORTER: Final = _(
    "Dieses Langloch ist bereits länger als die eingetragene Länge. Eine Operation schneidet "
    "nur weg — Material kommt nicht zurück. Tragen Sie eine größere Länge ein, oder nehmen "
    "Sie über Strg+Z den Schritt zurück, mit dem das Langloch entstanden ist."
)


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
    turn = math.radians(angle_deg % 180.0)
    cosine, sine = math.cos(turn), math.sin(turn)

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


def edge_findings(
    mesh: HasBounds,
    *,
    position: Vec3,
    frame: PlaneFrame,
    diameter: float,
    travel: float,
    angle_deg: float,
    body: MeshData | None = None,
) -> list[Finding]:
    """Die Kantenwarnung für eine runde Bohrung — und für beide Enden eines Langlochs.

    Ein Langloch steckt in der Mitte tief im Material und reißt trotzdem an
    einem Ende auf; wer nur die Mitte fragt, hört davon nichts. Gemeldet wird
    höchstens einmal: Zwei gleichlautende Sätze über dasselbe Loch sagen nichts
    Zweites und sind der Lärm, nach dem niemand mehr in den Bericht sieht.
    """
    if body is None and isinstance(mesh, MeshData):
        body = mesh
    if travel <= EPS_GEOM:
        return over_the_edge_along(mesh, position, frame.normal, diameter, body=body)
    for end in slot_ends(position, frame, travel, angle_deg):
        found = over_the_edge_along(mesh, end, frame.normal, diameter, body=body)
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
    turn = math.radians(angle_deg)
    along = np.asarray(frame.x_axis, dtype=float) * math.cos(turn) + np.asarray(
        frame.y_axis, dtype=float
    ) * math.sin(turn)
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
        return MeshData.of(trimesh.creation.revolve(outline, sections=BORE_SECTIONS))
    radius = outline[1][0]
    cylinder = trimesh.creation.cylinder(
        radius=radius,
        height=depth + mouth_overlap,
        sections=BORE_SECTIONS,
    )
    cylinder.apply_translation((0.0, 0.0, (mouth_overlap - depth) / 2.0))
    return MeshData.of(cylinder)


def _restore_drill_end_planes(
    body: trimesh.Trimesh,
    original_vertices: np.ndarray,
    world_to_local: np.ndarray,
    planes: tuple[float, float],
) -> None:
    """Nur Float64-Transformationsrauschen an den bekannten Werkzeugenden bereinigen.

    Vier Produkte, ihre Summation und der Ebenenvergleich werden konservativ
    durch gamma_8 begrenzt. Die Schranke folgt je Eckpunkt aus den Beträgen
    der wirklichen Matrixterme; sie ist weder Materialzugabe noch geometrische
    Schweißtoleranz. Ein darüber hinausgehender Abstand bleibt unangetastet.
    """
    unit_roundoff = np.finfo(np.float64).eps / 2.0
    gamma = 8.0 * unit_roundoff / (1.0 - 8.0 * unit_roundoff)
    magnitude = np.abs(original_vertices) @ np.abs(world_to_local[2, :3]) + abs(
        float(world_to_local[2, 3])
    )
    vertices = np.asarray(body.vertices, dtype=np.float64).copy()
    changed = False
    for plane in planes:
        close = np.abs(vertices[:, 2] - plane) <= gamma * (magnitude + abs(plane))
        if bool(np.any(close)):
            vertices[close, 2] = plane
            changed = True
    if changed:
        body.vertices = vertices


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
    Achse: ``slot_angle`` zählt gegen die x-Achse aus
    :func:`app.core.sketch.planes.frame_of`, und der achsparallele Zweig
    weiter unten kennt diesen Rahmen nicht — derselbe Winkel bedeutete dort
    eine andere Richtung.

    **Der Rahmen hängt an der Normalen, also an der Seite, von der aus gebohrt
    wird.** Gemessen an derselben Platte: 45 Grad von oben ergeben 45 Grad,
    45 Grad von unten ergeben 135 — ``frame_of`` spiegelt seine erste Achse mit
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
    length = float(np.linalg.norm(direction))
    if length <= EPS_GEOM and (widening_diameter > EPS_GEOM or travel > EPS_GEOM):
        direction[AXIS_INDEX[axis]] = -_into_the_material(mesh, axis, position)
        length = 1.0
    if length > EPS_GEOM:
        from app.core.sketch.planes import frame_of

        outward = direction / length
        frame = frame_of((float(outward[0]), float(outward[1]), float(outward[2])), position)
        to_world = np.eye(4)
        to_world[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
        to_world[:3, 3] = position
        world_to_local = np.linalg.inv(to_world)
        local_body = mesh.raw.copy()
        local_body.apply_transform(world_to_local)
        if through:
            low, high = float(local_body.bounds[0, 2]), float(local_body.bounds[1, 2])
            if widening_diameter > EPS_GEOM and anchor == "mouth":
                height, mouth = -low + BOOLEAN_OVERLAP, 0.0
            else:
                height = high - low + BOOLEAN_OVERLAP * 2.0
                mouth = high + BOOLEAN_OVERLAP
        else:
            height, mouth = depth, depth / 2.0 if anchor == "centre" else 0.0
        _restore_drill_end_planes(
            local_body,
            np.asarray(mesh.raw.vertices, dtype=np.float64),
            world_to_local,
            (mouth, mouth - height),
        )
        tool = drill_tool(
            diameter=diameter,
            depth=height,
            profile=profile,
            compensate=compensate,
            widening_diameter=widening_diameter,
            widening_depth=widening_depth,
            transition_angle=transition_angle,
            slot_length=slot_length,
            slot_angle=slot_angle,
        )
        cylinder = tool.raw.copy()
        cylinder.apply_translation((0.0, 0.0, mouth))
        outcome = boolean(
            "difference",
            [mesh.replacing(local_body), MeshData.of(cylinder)],
            quality=quality,
            seed=seed,
        )
        world_body = outcome.mesh.raw.copy()
        world_body.apply_transform(to_world)
        result = outcome.mesh.replacing(world_body)
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
            )
        )
        findings.extend(compensation_findings(diameter, cut_diameter, compensate))
        return BoreResult(result, outcome.solver, cut_diameter, findings)
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
    if through:
        # Symmetrisch über beide Seiten hinaus: Mitte auf die Position.
        cylinder.apply_translation((0.0, 0.0, height / 2.0))
        cylinder.apply_transform(alignment)
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
            cylinder.apply_transform(
                trimesh.transformations.rotation_matrix(math.pi, (1.0, 0.0, 0.0))
            )
        cylinder.apply_transform(alignment)
        along = np.zeros(3)
        along[AXIS_INDEX[axis]] = into
        offset = np.asarray(position, dtype=float)
        if anchor == "centre":
            # Historischer Anker: die Position ist die Mitte der Bohrlänge.
            offset = offset - along * (height / 2.0)
        cylinder.apply_translation(offset)

    outcome = boolean("difference", [mesh, MeshData.of(cylinder)], quality=quality, seed=seed)
    findings = list(outcome.findings)
    # Eine Bohrung, die den Körper nicht getroffen hat, sagt das (§2.7).
    nothing = without_effect(mesh, outcome.mesh, "difference", profile)
    if nothing is not None:
        findings.append(nothing)
    findings.extend(over_the_edge(mesh, position, axis, cut_diameter, body=mesh))
    findings.extend(compensation_findings(diameter, cut_diameter, compensate))
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
    """
    first = cut(mesh, plane)
    second = cut(mesh, plane.flipped())
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
    arranged: list[MeshData], assigned: list[int], area: Any, allowed: Any
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
    """
    left_edge, front_edge, right_edge, back_edge = area.bounds
    middle = ((left_edge + right_edge) / 2.0, (front_edge + back_edge) / 2.0)
    span = (right_edge - left_edge, back_edge - front_edge)
    moved = list(arranged)
    for plate in sorted(set(assigned)):
        members = [index for index, at in enumerate(assigned) if at == plate]
        low = np.min([arranged[index].bounds.minimum[:2] for index in members], axis=0)
        high = np.max([arranged[index].bounds.maximum[:2] for index in members], axis=0)
        along = [
            middle[axis] - (float(low[axis]) + float(high[axis])) / 2.0
            if float(high[axis]) - float(low[axis]) <= span[axis] + _TOUCH
            else 0.0
            for axis in (0, 1)
        ]
        shift = (along[0], along[1])
        if abs(shift[0]) < _TOUCH and abs(shift[1]) < _TOUCH:
            continue
        whole = box(low[0] + shift[0], low[1] + shift[1], high[0] + shift[0], high[1] + shift[1])
        if not allowed.covers(whole) and not all(
            _fits_after_shift(arranged[index], shift, allowed) for index in members
        ):
            continue
        for index in members:
            body = arranged[index].raw.copy()
            body.apply_transform(translation((shift[0], shift[1], 0.0)))
            moved[index] = arranged[index].replacing(body)
    return moved


def arrange_on_bed(
    meshes: list[MeshData],
    profile: Profile,
    spacing: float = 5.0,
    plates: int = 1,
    object_ids: Sequence[ObjectId] | None = None,
    *,
    margin: float | None = None,
    occupied: Sequence[tuple[MeshData, int]] = (),
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

    plate = 0
    taken: list[_Slot] = list(held.get(0, ()))

    def place(mesh: MeshData) -> _Slot | None:
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

    for mesh in meshes:
        size = mesh.bounds.size
        spot = place(mesh)
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
            taken = list(held.get(plate, ()))
            spot = place(mesh)
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

    # Gepackt ist in der Ecke, gelegt wird in der Mitte — und geprüft wird
    # danach, damit Bauraumbefunde die Lage nennen, die der Kunde sieht. Wo
    # fremde Körper liegen bleiben, gehört die Mitte ihnen mit; dort wird die
    # gepackte Lage nicht mehr verschoben.
    if not occupied:
        arranged = _into_the_middle(arranged, assigned, area, allowed)

    findings.extend(check_build_volume(arranged, profile, assigned, object_ids, margin=edge_margin))
    if plate + 1 >= plates and _overfull(arranged, assigned, profile, edge_margin):
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
    return bool(check_build_volume(on_last, profile, margin=spacing))


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
    return placement_offset(mesh, profile.printer, margin=spacing) is not None


def back_onto_bed(
    mesh: Mesh,
    others: Sequence[MeshData],
    profile: Profile,
    *,
    spacing: float = 5.0,
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
    zwei Millimeter zurück und nicht quer über die Platte gelegt. Erst wenn
    dort ein anderer Körper steht, wird neu eingeordnet.

    **Und nur auf der eigenen Platte.** ``others`` sind die Körper, die diese
    Platte teilen; um sie herum wird gesucht. Ein Plattenwechsel hinter dem
    Rücken des Kunden findet nicht statt: Ist auf seiner Platte nichts frei,
    bleibt der Körper, wo er ist, und :func:`check_build_volume` sagt es wie
    bisher. Eine Heilung, die schweigend die Platte wechselt, wäre ein Teil,
    das der Kunde beim Drucken nicht wiederfindet.

    Der Versatz ist rein waagerecht. Die Höhe hat *Auf das Bett setzen*, und
    ein bewusst angehobener Körper — für einen Booleschen Schnitt etwa — darf
    davon nicht heruntergezogen werden.

    Auch innerhalb der Druckfläche kann der alte Handzug nach einer
    Größenänderung in einen Nachbarn führen. Die Bettbindung hält deshalb
    beide Bedingungen: innerhalb der Fläche und ohne Überschneidung.
    """
    area = printable_area(profile.printer)
    body = as_mesh_data(mesh)
    inside = fits_xy(body, area)
    if inside and not _runs_into(body, (0.0, 0.0, 0.0), others):
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
            message=(
                _("Der Körper überschnitt sich mit einem anderen Teil und wurde neu eingeordnet.")
                if inside
                else _(
                    "Der Körper passte an seiner Stelle nicht mehr auf die "
                    "Druckfläche und wurde neu eingeordnet."
                )
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
    moved.apply_transform(translation(offset))
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

    Offene Körper haben kein Innen: Wo :func:`shared_volume` nichts entscheiden
    kann, bleibt die Prüfung stumm, statt eine Zahl zu erfinden.
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
                message=_("Die Teile überschneiden sich in ihrer Endlage."),
                values={"shared": format_volume(end)},
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
        distance = surface_gap(first, second, clearance)
    except PROGRAMMING_ERRORS:
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
