"""Die Suche nach einer Druckorientierung (Bauplan §22.3, §28.2).

Dafür gibt es den Analyse-Schneider eigentlich. Extern zu schneiden hieß, drei
bis fünf Kandidaten beurteilen zu können; intern zu schneiden heißt hunderte —
und das Urteil ist echtes Stützvolumen statt einer Faustregel über
Flächennormalen.

Die Abtastung ist über einen gespeicherten Startwert randomisiert (§11.3): eine
rein regelmäßige Abtastung bevorzugte systematisch symmetrische Körper, und
ohne den Startwert suchte dieselbe Datei nicht zweimal gleich.

Die Suche ist unterbrechbar. Zweihundert Kandidaten brauchen Sekunden, keine
Millisekunden, und §2.8 sagt, dass nichts das Fenster blockieren darf.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.geom.orient import candidates as face_candidates
from app.core.geom.transform import apply, place_on_bed
from app.core.log import get_logger
from app.core.slice.analysis import slice_body
from app.core.types import CancelToken, Finding, ProgressFn, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Schichthöhe für die Suche. Gröber als beim Druck: die Rangfolge bewegt
#: sich darunter kaum, und genau das hält hunderte Kandidaten
#: bezahlbar (§31).
SEARCH_LAYER_HEIGHT = 1.0

#: Vorgabeanzahl der versuchten Richtungen.
DEFAULT_CANDIDATES = 200


#: Stützvolumen innerhalb dieses Anteils voneinander zählen als gleich gut,
#: und dann entscheidet die Grundfläche. Ohne die Toleranz suchte das
#: Vernetzungsrauschen die Orientierung aus.
SUPPORT_TIE = 0.05


@dataclass(frozen=True, slots=True)
class Candidate:
    """Eine Richtung, beurteilt danach, was sie zu drucken kostete."""

    direction: Vec3
    support_volume: float
    first_layer_area: float
    height: float


def better(candidate: Candidate, current: Candidate) -> bool:
    """Weniger Stützen gewinnt; erst bei Gleichstand entscheidet die
    Grundfläche (§22.2).

    Mit Absicht lexikografisch statt als gewichtete Summe: eine große
    Aufstandsfläche darf sich nie an echtem Stützmaterial vorbeikaufen.
    """
    reference = max(candidate.support_volume, current.support_volume, EPS_GEOM)
    if abs(candidate.support_volume - current.support_volume) > reference * SUPPORT_TIE:
        return candidate.support_volume < current.support_volume
    return candidate.first_layer_area > current.first_layer_area


@dataclass(slots=True)
class SearchResult:
    """Der Gewinner, das Feld, gegen das er gewann, und was dem Nutzer zu
    sagen ist.
    """

    mesh: MeshData
    best: Candidate
    tried: int
    baseline: Candidate
    """Wie der Körper vorher stand — damit der Gewinn belegt und nicht behauptet wird."""
    findings: list[Finding]

    @property
    def improvement(self) -> float:
        """Wie viel Stützvolumen gegenüber der Ausgangslage gespart wird, in mm³."""
        return max(0.0, self.baseline.support_volume - self.best.support_volume)


def sample_directions(count: int, seed: int | None = None) -> list[Vec3]:
    """Gleichmäßig über die Kugel verteilte Richtungen, gedreht um einen
    gesetzten Versatz.
    """
    generator = np.random.default_rng(seed or 0)
    offset = float(generator.random())
    golden = math.pi * (3.0 - math.sqrt(5.0))

    found: list[Vec3] = []
    for index in range(max(1, count)):
        z = 1.0 - 2.0 * (index + offset) / max(count, 1)
        z = float(np.clip(z, -1.0, 1.0))
        radius = math.sqrt(max(0.0, 1.0 - z * z))
        angle = golden * index
        found.append((radius * math.cos(angle), radius * math.sin(angle), z))
    return found


def judge(mesh: MeshData, direction: Vec3, layer_height: float) -> Candidate:
    """Dreht den Körper, bis ``direction`` nach unten zeigt, dann schneiden und
    zählen."""
    turned = place_on_bed(apply(mesh, _rotation_to_down(direction)))
    # §28.2: die Suche liest eine Zahl daraus. Strukturbreiten an einem
    # Körper zu messen, der gleich wieder gedreht wird, ist Arbeit, die
    # niemand ansieht.
    result = slice_body(turned, layer_height, detail="support")
    return Candidate(
        direction=direction,
        support_volume=result.support_volume,
        first_layer_area=result.first_layer_area,
        height=turned.bounds.size[2],
    )


def _rotation_to_down(direction: Vec3) -> np.ndarray:
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


def search(
    mesh: MeshData,
    *,
    count: int = DEFAULT_CANDIDATES,
    seed: int | None = None,
    layer_height: float = SEARCH_LAYER_HEIGHT,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> SearchResult:
    """Probiert viele Orientierungen und behält die, die am wenigsten Stützen
    braucht."""
    baseline = judge(mesh, (0.0, 0.0, -1.0), layer_height)
    best = baseline
    tried = 1

    # Die Flächennormalen kommen mit: die beste Orientierung hat meist eine
    # ebene Fläche auf der Platte, und eine gleichmäßige Abtastung der Kugel
    # trifft eine exakte Achse nur zufällig.
    directions = [*face_candidates(mesh), *sample_directions(count, seed)]
    for index, direction in enumerate(directions, start=1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if progress is not None:
            progress(index / max(len(directions), 1), str(_("Ausrichtung suchen")))

        candidate = judge(mesh, direction, layer_height)
        tried += 1
        if better(candidate, best):
            best = candidate

    turned = place_on_bed(apply(mesh, _rotation_to_down(best.direction)))
    findings = [
        Finding(
            code="orient.searched",
            severity="info",
            message=_("Ausrichtung über die Schichtanalyse gesucht."),
            values={
                "candidates": tried,
                "support": round(best.support_volume / 1000.0, 2),
                "saved": round((baseline.support_volume - best.support_volume) / 1000.0, 2),
            },
            source="internal",
        )
    ]
    _log.info(
        "orientation search: %d candidates, support %.1f mm3 (was %.1f)",
        tried,
        best.support_volume,
        baseline.support_volume,
    )
    return SearchResult(mesh=turned, best=best, tried=tried, baseline=baseline, findings=findings)
