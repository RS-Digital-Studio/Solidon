"""Eine Druckorientierung wählen (Bauplan §25, P2).

Eine Heuristik über Flächennormalen, und offen als solche benannt: sie sucht
eine ebene Fläche zum Aufstehen und zählt, wie viel überhinge. In P3 ersetzt
die Schichtanalyse (§22) sie — dann werden hunderte Drehungen an echtem
Stützvolumen gemessen statt an einer Faustregel.

Bis dahin ist die Faustregel ehrlich darüber, was sie ist: der Befund sagt,
welcher Kandidat gewann und mit welchem Abstand.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, translation
from app.core.knowledge.rules import OVERHANG_LIMIT_DEGREES
from app.core.types import Finding, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

#: Wie viele Kandidatenrichtungen über die sechs Achsrichtungen hinaus
#: angesehen werden.
MAX_FACE_CANDIDATES = 12


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


def candidates(mesh: MeshData) -> list[Vec3]:
    """Sechs Achsrichtungen plus die Normalen der größten ebenen Flächen."""
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
    rounded = np.round(normals, 3)
    unique, inverse = np.unique(rounded, axis=0, return_inverse=True)
    grouped = np.zeros(len(unique))
    np.add.at(grouped, inverse, areas)

    for index in np.argsort(grouped)[::-1][:MAX_FACE_CANDIDATES]:
        normal = unique[index]
        length = float(np.linalg.norm(normal))
        if length > EPS_GEOM:
            unit = normal / length
            found.append((float(unit[0]), float(unit[1]), float(unit[2])))
    return found


def evaluate_direction(mesh: MeshData, direction: Vec3) -> Orientation:
    """Wie der Körper aussähe, stünde er auf dieser Fläche."""
    turned = apply(mesh, rotation_to_down(direction))
    body = turned.raw
    normals = np.asarray(body.face_normals, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)

    downward = normals[:, 2] < -math.cos(math.radians(OVERHANG_LIMIT_DEGREES))
    flat_bottom = (normals[:, 2] < -0.999) & (
        np.asarray(body.triangles_center)[:, 2] < body.bounds[0][2] + 0.05
    )
    return Orientation(
        direction=direction,
        footprint=float(areas[flat_bottom].sum()),
        overhang=float(areas[downward & ~flat_bottom].sum()),
        height=float(turned.bounds.size[2]),
    )


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
    return np.asarray(translation((0.0, 0.0, -lifted.bounds.minimum[2])) @ turn, dtype=float)


def orient_for_print(mesh: MeshData) -> OrientResult:
    """Dreht den Körper in die Lage, die der Heuristik am besten gefällt."""
    scored = [evaluate_direction(mesh, direction) for direction in candidates(mesh)]
    best = max(scored, key=lambda entry: entry.score)
    matrix = print_transform(mesh, best.direction)
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
