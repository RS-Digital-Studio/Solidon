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
from typing import Any, Literal

import numpy as np
import trimesh

from app.core.errors import PROGRAMMING_ERRORS
from app.core.geom.boolean import boolean, shared_volume, without_effect
from app.core.geom.mesh import MeshData, concatenated, on_surface
from app.core.geom.section import SectionPlane, cut
from app.core.geom.transform import Axis, translation
from app.core.knowledge.profiles import resolve_tolerance
from app.core.types import BoundingBox, Finding, Mesh, Profile, Quality, SolverInfo, Vec3
from app.core.units import EPS_GEOM, format_length, format_volume
from app.i18n import TranslatableText, _

#: §39: Boolesche Ops überlappen immer leicht, nie teilen sie exakt eine Fläche.
BOOLEAN_OVERLAP = 0.01

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
    solver: SolverInfo
    diameter: float
    """Der wirklich geschnittene Durchmesser, samt Materialkompensation."""
    findings: list[Finding]


def bore_diameter(nominal: float, profile: Profile, compensate: bool) -> float:
    """Nominal plus was das Material frisst, aus dem Profil (§39, §28.3)."""
    if not compensate:
        return nominal
    return nominal + resolve_tolerance("auto:", "thread", profile)


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
        direction[AXIS_INDEX[axis]] = into_the_body(mesh, axis, position)
        offset = offset + direction * (height / 2.0)
    cylinder.apply_translation(offset)

    outcome = boolean("difference", [mesh, MeshData.of(cylinder)], quality=quality, seed=seed)
    findings = list(outcome.findings)
    # Eine Bohrung, die den Körper nicht getroffen hat, sagt das (§2.7).
    nothing = without_effect(mesh, outcome.mesh, "difference")
    if nothing is not None:
        findings.append(nothing)
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
    quality: Quality = "fine",
) -> BoreResult:
    """Bricht die Mündung einer Bohrung mit einem Kegel, damit ein
    Schraubenkopf bündig sitzt (§25).

    Der Winkel ist der volle Kopfwinkel — 90 Grad bei einer metrischen
    Senkkopfschraube. Geschnitten wird der Kegel, den dieser Kopf beschreibt —
    darum folgt die Tiefe aus dem Durchmesser, statt abgefragt zu werden.
    """
    depth = diameter / 2.0 / math.tan(math.radians(angle / 2.0))
    cone = trimesh.creation.cone(radius=diameter / 2.0, height=depth, sections=BORE_SECTIONS)
    # Der Kegel kommt auf seiner Basis stehend heraus, Spitze nach oben. Eine
    # Senkung ist andersherum: am weitesten an der Fläche, enger werdend ins
    # Material. Umgedreht läuft er von null abwärts, was genau das ist — und
    # er wird um die Überlappung angehoben, damit die zwei Flächen nicht
    # zusammenfallen (§39).
    cone.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))
    cone.apply_translation([0.0, 0.0, BOOLEAN_OVERLAP])
    cone.apply_transform(_axis_alignment(axis))
    cone.apply_translation(np.asarray(position, dtype=float))

    outcome = boolean("difference", [mesh, MeshData.of(cone)], quality=quality)
    return BoreResult(
        mesh=outcome.mesh,
        solver=outcome.solver,
        diameter=diameter,
        findings=list(outcome.findings),
    )


def plug(
    mesh: MeshData,
    *,
    position: Vec3,
    axis: Axis,
    diameter: float,
    depth: float = 0.0,
    quality: Quality = "fine",
) -> BoreResult:
    """Füllt eine Bohrung wieder auf (§25, „verschließen").

    Etwas größer als das Loch, das er füllt — ein Stopfen exakt in Bohrungsgröße
    trifft sie in einer zusammenfallenden Fläche, dem einen Ding, das eine
    Boolesche Op zuverlässig bricht (§39, ``boolean_overlap``).
    """
    height = depth if depth > EPS_GEOM else _through_length(mesh, axis)
    cylinder = trimesh.creation.cylinder(
        radius=diameter / 2.0 + BOOLEAN_OVERLAP, height=height, sections=BORE_SECTIONS
    )
    cylinder.apply_transform(_axis_alignment(axis))
    cylinder.apply_translation(np.asarray(position, dtype=float))

    # Erst verschneiden: der Stopfen darf nicht aus dem Körper herauswachsen,
    # den er füllt.
    inner = boolean("intersection", [mesh.replacing(cylinder), _shell(mesh)], quality=quality)
    outcome = boolean("union", [mesh, inner.mesh], quality=quality)
    return BoreResult(
        mesh=outcome.mesh,
        solver=outcome.solver,
        diameter=diameter,
        findings=list(outcome.findings),
    )


def _shell(mesh: MeshData) -> MeshData:
    """Der Körper als Volumen zum Beschneiden — die konvexe Hülle ist nah
    genug.

    Ein Stopfen wird auf die Außenseite des Teils zurückgeschnitten, und dafür
    ist die Hülle die richtige Form: sie greift nie in einen Hohlraum hinein,
    ein Stopfen kann also nie einen füllen.
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
    der Körper liegt. Entschieden wird an der Hälfte des Hüllquaders: wer die
    obere Fläche anklickt, meint nach unten, wer die untere anklickt, nach
    oben. Für eine angeklickte Fläche ist das eindeutig — und mehr als eine
    angeklickte Fläche gibt es an dieser Stelle nicht zu entscheiden.
    """
    index = AXIS_INDEX[axis]
    low = float(mesh.bounds.minimum[index])
    high = float(mesh.bounds.maximum[index])
    return -1.0 if position[index] >= (low + high) / 2.0 else 1.0


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
    mesh: MeshData, profile: Profile, height: float = 0.6, amount: float | None = None
) -> tuple[MeshData, list[Finding]]:
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
        return mesh, []

    bottom = float(mesh.bounds.minimum[2])
    section = cross_section(mesh, bottom + height / 2.0)
    if section is None or section.is_empty:
        return mesh, []

    pulled = section.buffer(-value)
    if pulled.is_empty:
        return mesh, [
            Finding(
                code="prepare.foot_too_small",
                severity="warning",
                message=_("Die Aufstandsfläche ist zu klein, um sie noch einzuziehen."),
                values={"amount_mm": round(value, 3)},
            )
        ]

    # Was weg muss: der Ring zwischen dem echten Umriss und dem eingezogenen,
    # über die Höhe der ersten Schichten.
    ring = section.difference(pulled)
    if ring.is_empty:
        return mesh, []
    parts = [
        trimesh.creation.extrude_polygon(entry, height=height + BOOLEAN_OVERLAP)
        for entry in getattr(ring, "geoms", [ring])
        if isinstance(entry, ShapelyPolygon) and entry.area > EPS_GEOM
    ]
    if not parts:
        return mesh, []

    collar = concatenated(parts)
    collar.apply_translation([0.0, 0.0, bottom - BOOLEAN_OVERLAP / 2.0])
    outcome = boolean("difference", [mesh, mesh.replacing(collar)])
    findings = list(outcome.findings)
    findings.append(
        Finding(
            code="prepare.elephant_foot",
            severity="info",
            message=_("Die ersten Schichten wurden um den Elefantenfuß eingezogen."),
            values={"amount_mm": round(value, 3), "height_mm": round(height, 2)},
        )
    )
    return outcome.mesh, findings


@dataclass(frozen=True, slots=True)
class Arrangement:
    """Wo die Körper gelandet sind, und auf welcher Platte."""

    meshes: list[MeshData]
    plates: list[int]
    findings: list[Finding] = field(default_factory=list)

    @property
    def plate_count(self) -> int:
        return max(self.plates, default=0) + 1 if self.plates else 0


def arrange_on_bed(
    meshes: list[MeshData], profile: Profile, spacing: float = 5.0, plates: int = 1
) -> Arrangement:
    """Legt die Körper in einer Reihe auf die Platte, dann in Zeilen
    umbrechend (§25).

    Bewusst einfach: ein Regal-Packen, das jeder vorhersagen kann, schlägt ein
    kluges, das Teile aus Gründen verschiebt, die niemand sieht.

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
    """
    width, depth, _height = profile.printer.build_volume
    arranged: list[MeshData] = []
    assigned: list[int] = []
    findings: list[Finding] = []

    plate = 0
    cursor_x = -width / 2.0 + spacing
    cursor_y = -depth / 2.0 + spacing
    row_depth = 0.0

    for mesh in meshes:
        size = mesh.bounds.size
        if cursor_x + size[0] > width / 2.0 - spacing:
            cursor_x = -width / 2.0 + spacing
            cursor_y += row_depth + spacing
            row_depth = 0.0
        if cursor_y + size[1] > depth / 2.0 - spacing and plate + 1 < plates:
            plate += 1
            cursor_x = -width / 2.0 + spacing
            cursor_y = -depth / 2.0 + spacing
            row_depth = 0.0

        target = (
            cursor_x + size[0] / 2.0,
            cursor_y + size[1] / 2.0,
            mesh.bounds.size[2] / 2.0,
        )
        offset = tuple(target[index] - mesh.bounds.centre[index] for index in range(3))
        body = mesh.raw.copy()
        body.apply_transform(translation((offset[0], offset[1], offset[2])))
        arranged.append(mesh.replacing(body))
        assigned.append(plate)

        cursor_x += size[0] + spacing
        row_depth = max(row_depth, size[1])

    findings.extend(check_build_volume(arranged, profile, assigned))
    if plate + 1 >= plates and _overfull(arranged, assigned, profile):
        findings.append(
            Finding(
                code="arrange.needs_more_plates",
                severity="warning",
                message=_("Auf so viele Platten passt das nicht — eine mehr würde helfen."),
                values={"plates": plates},
            )
        )
    return Arrangement(meshes=arranged, plates=assigned, findings=findings)


def _overfull(meshes: list[MeshData], plates: list[int], profile: Profile) -> bool:
    """Steht auf der letzten Platte etwas über sie hinaus?"""
    last = max(plates, default=0)
    on_last = [mesh for mesh, plate in zip(meshes, plates, strict=True) if plate == last]
    return bool(check_build_volume(on_last, profile))


def check_build_volume(
    meshes: Sequence[Mesh], profile: Profile, plates: list[int] | None = None
) -> list[Finding]:
    """Was über den Bauraum hinaussteht, wird gemeldet, nie still skaliert.

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
        if outside:
            values: dict[str, Any] = {
                "object": index,
                "axes": ", ".join("xyz"[axis] for axis in outside),
                # Wie weit — sonst steht dort eine Warnung, die zwischen einem
                # Zehntel Millimeter und einem halben Modell nicht unterscheidet.
                "excess": format_length(max(over)),
            }
            if plates is not None and index < len(plates):
                values["plate"] = plates[index] + 1
            findings.append(
                Finding(
                    code="arrange.out_of_build_volume",
                    severity="warning",
                    message=_message_for(bounds, allowed, outside),
                    values=values,
                )
            )
    return findings


def _message_for(
    bounds: BoundingBox, allowed: BoundingBox, outside: Sequence[int]
) -> TranslatableText:
    """Der Satz, der zum tatsächlichen Fall passt.

    „Steht über den Bauraum hinaus" liest sich als „zu groß", und beim
    häufigsten Fall von Weg 1 ist das falsch: ein heruntergeladenes Teil ist
    meist um den Ursprung zentriert, liegt also zur Hälfte unter der
    Druckplatte. Wer den Satz wörtlich nimmt, sucht das Skalieren, obwohl ein
    Aufsetzen genügt — ein Achtelmillimeter Text, der jemanden auf die falsche
    Fährte schickt.
    """
    only_below = all(
        allowed.minimum[axis] - bounds.minimum[axis] > bounds.maximum[axis] - allowed.maximum[axis]
        for axis in outside
    )
    if not only_below:
        return _("Ein Objekt steht über den Bauraum hinaus.")
    if tuple(outside) == (2,):
        return _("Ein Objekt steckt unter der Druckplatte.")
    return _("Ein Objekt liegt außerhalb der Druckplatte.")


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
