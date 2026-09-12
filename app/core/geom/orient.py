"""Geometrische Druckorientierungen und ihre günstige Vorauswahl (§28.2)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.core.build_area import placement_offset
from app.core.deferred import trimesh
from app.core.errors import CANCEL, CHOOSE_PRINTER, SPLIT_MODEL, GeometryError
from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, rotation, translation
from app.core.knowledge.rules import OVERHANG_LIMIT_DEGREES
from app.core.types import CancelToken, Finding, PrinterProfile, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

#: Wie viele Kandidatenrichtungen über die sechs Achsrichtungen hinaus
#: angesehen werden.
MAX_FACE_CANDIDATES = 12

#: Zielgrenze je Projektionsmatrix; eine einzelne größere Lage bleibt einzeln.
MAX_PROJECTION_VALUES = 1_000_000


class NoFittingOrientationError(GeometryError):
    """Keine der geprüften Lagen passt; Teilung kann diesen Kandidaten verwerfen."""

    default_title = _(
        "Keine geprüfte Lage passt in den Druckbereich. "
        "Wählen Sie einen anderen Drucker oder teilen Sie das Modell."
    )
    default_suggestions = (SPLIT_MODEL, CHOOSE_PRINTER, CANCEL)


@dataclass(frozen=True, slots=True)
class Orientation:
    """Ein Kandidat und was für ihn spricht."""

    direction: Vec3
    """Die Flächennormale, die am Ende nach unten zeigte."""
    footprint: float
    """Fläche, die auf der Platte aufläge, in mm²."""
    overhang: float
    """Fläche, die Stützen bräuchte, in mm²."""
    height: float

    @property
    def score(self) -> float:
        """Große Aufstandsfläche, wenig Überhang, flache Bauhöhe — in dieser
        Reihenfolge."""
        return self.footprint * 2.0 - self.overhang - self.height * 10.0


@dataclass(slots=True)
class OrientResult:
    mesh: MeshData
    chosen: Orientation
    findings: list[Finding]
    transform: np.ndarray = field(default_factory=lambda: np.eye(4))
    """Die starre Bewegung, die den Körper in diese Lage gebracht hat.

    Ohne sie war *Druckoptimal ausrichten* die einzige bewegende Operation, die
    schwieg: Die Zuordnung (§21.2) muss danach raten, welches Merkmal welches
    ist, und bei einer Drehung um neunzig Grad rät sie falsch. Merkmalskennungen
    wechseln, und jede Passung, die auf eine davon zeigt, zeigt danach ins
    Leere.
    """


def _largest_normals(normals: np.ndarray, areas: np.ndarray, limit: int) -> list[Vec3]:
    """Gruppiert ebene Flächen, bewahrt aber ihre ungerundete Richtung."""
    unique, inverse = np.unique(np.round(normals, 6), axis=0, return_inverse=True)
    grouped = np.bincount(inverse, weights=areas, minlength=len(unique))
    weighted = np.column_stack(
        [
            np.bincount(inverse, weights=normals[:, axis] * areas, minlength=len(unique))
            for axis in range(3)
        ]
    )
    # unique ist bereits lexikographisch geordnet. Die stabile Flächensortierung
    # erhält diese Reihenfolge bei gleichen Flächensummen.
    order = np.argsort(-grouped, kind="stable")
    found: list[Vec3] = []
    for index in order[:limit]:
        normal = weighted[index]
        length = float(np.linalg.norm(normal))
        if length > EPS_GEOM:
            unit = normal / length
            found.append((float(unit[0]), float(unit[1]), float(unit[2])))
    return found


def candidates(mesh: MeshData, *, hull_limit: int = 200) -> list[Vec3]:
    """Achsen, tragende Körperflächen und flächengeordnete konvexe Hüllnormalen.

    Die Hülle verwendet sortierte eindeutige Punkte ohne Zufallsstörung.
    Ihre Normalen sind auch bei konkaven oder organischen Körpern geometrisch
    begründet; die tatsächliche Auflage beurteilt erst die Schichtanalyse.
    """
    found: list[Vec3] = [
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
    ]
    body = mesh.raw
    if not len(body.faces):
        return found

    normals = np.asarray(body.face_normals, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)
    found.extend(_largest_normals(normals, areas, MAX_FACE_CANDIDATES))
    vertices = np.unique(np.asarray(body.vertices, dtype=float), axis=0)
    if len(vertices) < 4:
        return found
    from scipy.spatial import ConvexHull, QhullError

    try:
        hull = ConvexHull(vertices)
    except QhullError:
        # Ein flaches oder entartetes Netz hat keine dreidimensionale Hülle.
        # Seine eigenen Flächen und Achsen bleiben trotzdem prüfbar.
        return found
    triangles = vertices[hull.simplices]
    hull_areas = (
        np.linalg.norm(
            np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
        )
        / 2.0
    )
    found.extend(_largest_normals(hull.equations[:, :3], hull_areas, max(1, hull_limit)))
    return found


def evaluate_direction(mesh: MeshData, direction: Vec3) -> Orientation:
    """Wie der Körper aussähe, stünde er auf dieser Fläche."""
    return _evaluate_directions(mesh, [direction])[0]


def _evaluate_directions(
    mesh: MeshData, directions: list[Vec3], cancelled: CancelToken | None = None
) -> list[Orientation]:
    """Bewertet dieselben Lagen in speicherbegrenzten gemeinsamen Projektionen."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    body = mesh.raw
    normals = np.asarray(body.face_normals, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)
    vertices = np.asarray(body.vertices)
    referenced = body.referenced_vertices
    if not referenced.all():
        vertices = vertices[referenced]
    centres = np.asarray(body.triangles_center)
    # Mehrere Lagen nur bis zur Grenze gemeinsam projizieren. Ist schon eine
    # Lage größer, bleibt sie einzeln. Einzelabfragen nutzen denselben Weg.
    batch_size = max(
        1, min(len(directions), MAX_PROJECTION_VALUES // max(len(vertices), len(normals), 1))
    )
    threshold = -math.cos(math.radians(OVERHANG_LIMIT_DEGREES))
    scored: list[Orientation] = []
    for start in range(0, len(directions), batch_size):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        batch = directions[start : start + batch_size]
        verticals = np.asarray([rotation_to_down(direction)[2, :3] for direction in batch])
        vertex_heights = verticals @ vertices.T
        normal_heights = verticals @ normals.T
        centre_heights = verticals @ centres.T
        bottom = vertex_heights.min(axis=1)
        height = vertex_heights.max(axis=1) - bottom
        flat_bottom = (normal_heights < -0.999) & (centre_heights < bottom[:, None] + 0.05)
        downward = normal_heights < threshold
        for index, direction in enumerate(batch):
            scored.append(
                Orientation(
                    direction=direction,
                    footprint=float(areas[flat_bottom[index]].sum()),
                    overhang=float(areas[downward[index] & ~flat_bottom[index]].sum()),
                    height=float(height[index]),
                )
            )
    return scored


def ranked_orientations(
    mesh: MeshData,
    *,
    limit: int | None = None,
    cancelled: CancelToken | None = None,
    printer: PrinterProfile | None = None,
    margin: float = 0.0,
) -> list[Orientation]:
    """Grundflächen nach der billigen Heuristik, beste zuerst.

    Die Schichtanalyse benutzt diese Liste als Vorauswahl: Nur wenige Lagen
    werden danach wirklich geschnitten. Darum ist die Reihenfolge vollständig
    bestimmt — auch bei gleichem Score entscheidet die Richtung und nicht die
    zufällige Reihenfolge eines Sortierverfahrens.

    Doppelte Richtungen fallen vorher heraus. Achsen stehen sowohl fest in der
    Liste als auch unter den größten Flächennormalen; sie ein zweites Mal zu
    prüfen ändert kein Urteil und kostet auf einem dichten Netz spürbar Zeit.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    directions: list[Vec3] = []
    for direction in candidates(mesh):
        if any(math.dist(direction, previous) <= EPS_GEOM for previous in directions):
            continue
        directions.append(direction)

    scored = _evaluate_directions(mesh, directions, cancelled)

    ranked = sorted(
        scored,
        key=lambda entry: (
            -entry.score,
            -entry.footprint,
            entry.overhang,
            entry.height,
            entry.direction,
        ),
    )
    selected: list[Orientation] = []
    for entry in ranked:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if (
            printer is not None
            and fitting_transform(mesh, entry.direction, printer, margin=margin) is None
        ):
            continue
        selected.append(entry)
        # Erst die günstige Reihenfolge bestimmen: Für eine begrenzte
        # Vorauswahl müssen schlechtere Lagen nicht mehr platziert werden.
        if limit is not None and len(selected) >= max(1, limit):
            break
    return selected


def rotation_to_down(direction: Vec3) -> np.ndarray:
    """Die Drehung, die ``direction`` auf -Z bringt.

    Öffentlich, weil die Schichtanalyse sie mitbenutzt: ``slice.orientation``
    trug sie bis zum 24.08.2026 als wortgleiche Kopie, Zeile für Zeile dieselbe
    — und damit dieselbe Rechnung an zwei Stellen, von denen nur eine gepflegt
    worden wäre. Sie gehört hierher, denn hier stehen die Kandidatenrichtungen,
    die sie dreht.
    """
    source = np.asarray(direction, dtype=float)
    length = float(np.linalg.norm(source))
    if length <= EPS_GEOM:
        return np.eye(4)
    source = source / length
    target = np.array([0.0, 0.0, -1.0])

    axis = np.cross(source, target)
    if float(np.linalg.norm(axis)) <= EPS_GEOM:
        if float(np.dot(source, target)) > 0:
            return np.eye(4)
        return np.asarray(
            trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]), dtype=float
        )
    angle = math.acos(float(np.clip(np.dot(source, target), -1.0, 1.0)))
    return np.asarray(trimesh.transformations.rotation_matrix(angle, axis), dtype=float)


def print_transform(mesh: MeshData, direction: Vec3) -> np.ndarray:
    """Die eine Matrix, die den Körper auf diese Fläche stellt: erst drehen,
    dann aufs Bett setzen.

    Als **eine** Bewegung und nicht als zwei, weil genau das der Wert ist, den
    eine Operation melden muss (``OpResult.transform``, §21.2). Zwei
    nacheinander angewandte Matrizen ergeben dasselbe Netz und keine Auskunft.
    Benutzt auch die Schichtanalyse-Suche über die Operation — sie dreht mit
    denselben zwei Schritten, hat aber nur die Richtung zurückgegeben.
    """
    turn = rotation_to_down(direction)
    lifted = apply(mesh, turn)
    offset = (
        mesh.bounds.centre[0] - lifted.bounds.centre[0],
        mesh.bounds.centre[1] - lifted.bounds.centre[1],
        -lifted.bounds.minimum[2],
    )
    return np.asarray(translation(offset) @ turn, dtype=float)


def fitting_transform(
    mesh: MeshData, direction: Vec3, printer: PrinterProfile, *, margin: float = 0.0
) -> np.ndarray | None:
    """Eine passende Lage dieser Grundfläche, auch um 90° auf dem Bett gedreht."""
    initial = print_transform(mesh, direction)
    for yaw in (0.0, 90.0):
        turn = rotation("z", yaw) @ initial
        turned = apply(mesh, turn)
        # Eine Drehung in der Platte bewahrt denselben sinnvollen Mittelpunkt.
        centre = translation(
            (
                mesh.bounds.centre[0] - turned.bounds.centre[0],
                mesh.bounds.centre[1] - turned.bounds.centre[1],
                0.0,
            )
        )
        turn = centre @ turn
        moved = apply(mesh, turn)
        offset = placement_offset(moved, printer, margin=margin)
        if offset is not None:
            return np.asarray(translation(offset) @ turn, dtype=float)
    return None


def orient_for_print(
    mesh: MeshData,
    *,
    cancelled: CancelToken | None = None,
    printer: PrinterProfile | None = None,
    margin: float = 0.0,
) -> OrientResult:
    """Dreht den Körper in die Lage, die der Heuristik am besten gefällt."""
    scored = ranked_orientations(mesh, cancelled=cancelled, printer=printer, margin=margin)
    if not scored:
        raise NoFittingOrientationError()
    best = scored[0]
    matrix = (
        fitting_transform(mesh, best.direction, printer, margin=margin)
        if printer is not None
        else print_transform(mesh, best.direction)
    )
    assert matrix is not None
    turned = apply(mesh, matrix)

    findings = [
        Finding(
            code="orient.heuristic",
            severity="info",
            message=_(
                "Ausrichtung über eine Normalen-Heuristik gewählt — die Schichtanalyse "
                "urteilt später genauer."
            ),
            values={
                "footprint": round(best.footprint, 1),
                "overhang": round(best.overhang, 1),
                "candidates": len(scored),
            },
        )
    ]
    if best.overhang > best.footprint:
        findings.append(
            Finding(
                code="orient.support_likely",
                severity="warning",
                message=_("Auch in der besten Lage bleibt viel Überhang — Stützen sind nötig."),
            )
        )
    return OrientResult(mesh=turned, chosen=best, findings=findings, transform=matrix)
