"""The input stage (Bauplan §17.1).

Every loaded file walks the same six steps, in this order:

1. determine the unit — STL carries none, so a heuristic decides and **asks when
   it is not sure** instead of assuming;
2. weld vertices with a tolerance scaled to the model size;
3. remove degenerate triangles (zero area, needles, duplicates);
4. unify normals and check the orientation;
5. count components and **report** small parts instead of silently deleting them;
6. find the centre of mass and **offer** to place the model on the bed.

Everything the stage did lands in ``IngestInfo`` and in findings, so the report
(§17.3) and the digest can say what was changed on the way in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData, face_components
from app.core.log import get_logger
from app.core.types import Finding, IngestInfo, ProgressFn
from app.core.units import EPS_GEOM, LengthUnit, to_mm, weld_tolerance
from app.i18n import _

_log = get_logger(__name__)

#: Import limits (§32). A clear message beats a memory overflow.
MAX_TRIANGLES: Final = 20_000_000
MAX_FILE_BYTES: Final = 512 * 1024 * 1024

#: Above this the input stage says something. Not a limit — the one above is
#: an order of magnitude higher — but the size where the analysis stops being
#: able to help: the maps refuse at 120 000 and the feature detection at
#: 200 000 (§31). A community model of two million triangles is a normal thing
#: to be handed, and it should say what it is rather than just be slow.
HEAVY_TRIANGLES: Final = 500_000

#: What a printable part usually measures across, in millimetres.
PLAUSIBLE_MIN_MM: Final = 10.0
PLAUSIBLE_MAX_MM: Final = 300.0

#: Units a file might have been written in, most likely first.
CANDIDATE_UNITS: Final[tuple[LengthUnit, ...]] = ("mm", "cm", "in", "m")

#: A component below this share of the largest one counts as a stray fragment.
SMALL_COMPONENT_SHARE: Final = 0.001


@dataclass(frozen=True, slots=True)
class UnitGuess:
    """What the heuristic found. ``unit`` is None when it is not sure (§17.1)."""

    unit: LengthUnit | None
    candidates: tuple[LengthUnit, ...]
    diagonal: float

    @property
    def certain(self) -> bool:
        return self.unit is not None


def detect_unit(diagonal: float) -> UnitGuess:
    """Guess the unit of a file from the size of its bounding box.

    Exactly one plausible reading wins. Several plausible readings mean the
    question goes to the user — that is Leitprinzip 6, not politeness.
    """
    if diagonal <= EPS_GEOM:
        return UnitGuess(unit=None, candidates=CANDIDATE_UNITS, diagonal=diagonal)
    plausible = tuple(
        unit
        for unit in CANDIDATE_UNITS
        if PLAUSIBLE_MIN_MM <= to_mm(diagonal, unit) <= PLAUSIBLE_MAX_MM
    )
    if len(plausible) == 1:
        return UnitGuess(unit=plausible[0], candidates=plausible, diagonal=diagonal)
    return UnitGuess(unit=None, candidates=plausible or CANDIDATE_UNITS, diagonal=diagonal)


def check_limits(payload_size: int, triangle_count: int) -> None:
    """Refuse oversized input with a clear message rather than running out of memory."""
    if payload_size > MAX_FILE_BYTES:
        raise ValidationError(
            field="file",
            detail=_("Die Datei ist größer, als diese Anwendung verarbeitet."),
            constraint="file_too_large",
            values={"size": payload_size, "limit": MAX_FILE_BYTES},
        )
    if triangle_count > MAX_TRIANGLES:
        raise ValidationError(
            field="file",
            detail=_("Das Modell hat mehr Dreiecke, als diese Anwendung verarbeitet."),
            constraint="too_many_triangles",
            values={"triangles": triangle_count, "limit": MAX_TRIANGLES},
        )


@dataclass(frozen=True, slots=True)
class IngestResult:
    """The normalised mesh plus what happened to it."""

    mesh: MeshData
    info: IngestInfo
    findings: tuple[Finding, ...] = ()


def _silent(fraction: float, text: str) -> None:
    return None


def normalise(
    mesh: MeshData,
    unit: LengthUnit,
    *,
    weld: bool = True,
    remove_degenerate: bool = True,
    unify_normals: bool = True,
    place_on_bed: bool = False,
    progress: ProgressFn = _silent,
) -> IngestResult:
    """Run the six steps and report what they did."""
    findings: list[Finding] = []
    body: trimesh.Trimesh = mesh.raw.copy()
    scale = to_mm(1.0, unit)

    # 1 — unit. The only place besides display where a conversion happens (§11.1).
    progress(0.0, str(_("Einheit anwenden")))
    if abs(scale - 1.0) > EPS_GEOM:
        body.apply_scale(scale)
        findings.append(
            Finding(
                code="ingest.scaled",
                severity="info",
                message=_("Die Datei wurde in Millimeter umgerechnet."),
                values={"unit": unit, "scale": scale},
            )
        )

    diagonal = float(np.linalg.norm(body.extents)) if len(body.faces) else 0.0

    # 2 — weld vertices, with a tolerance that follows the model size.
    welded = False
    if weld and len(body.faces):
        progress(0.2, str(_("Punkte verschweißen")))
        before = len(body.vertices)
        tolerance = weld_tolerance(diagonal)
        body.merge_vertices(digits_vertex=_digits_for(tolerance))
        welded = len(body.vertices) < before
        if welded:
            findings.append(
                Finding(
                    code="ingest.welded",
                    severity="info",
                    message=_("Doppelte Punkte wurden verschweißt."),
                    values={"removed": before - len(body.vertices)},
                )
            )

    # 3 — degenerate triangles: zero area, needles, duplicates.
    removed = 0
    if remove_degenerate and len(body.faces):
        progress(0.4, str(_("Entartete Dreiecke entfernen")))
        before = len(body.faces)
        body.update_faces(body.nondegenerate_faces(height=EPS_GEOM))
        body.update_faces(body.unique_faces())
        body.remove_unreferenced_vertices()
        removed = before - len(body.faces)
        if removed:
            findings.append(
                Finding(
                    code="ingest.degenerate_removed",
                    severity="warning",
                    message=_("Entartete Dreiecke wurden entfernt."),
                    values={"removed": removed},
                )
            )

    # 4 — normals and orientation.
    if unify_normals and len(body.faces):
        progress(0.6, str(_("Normalen vereinheitlichen")))
        was_volume = float(body.volume)
        trimesh.repair.fix_winding(body)
        if body.is_watertight:
            trimesh.repair.fix_inversion(body)
        if was_volume < 0.0 <= float(body.volume):
            findings.append(
                Finding(
                    code="ingest.normals_flipped",
                    severity="info",
                    message=_("Die Ausrichtung der Flächen wurde korrigiert."),
                )
            )

    # 5 — components. Small ones are reported, never dropped silently.
    progress(0.8, str(_("Komponenten zählen")))
    components = _count_components(body, findings)

    # 6 — position. Placing on the bed is offered, not enforced.
    if place_on_bed and len(body.faces):
        progress(0.9, str(_("Auf das Bett setzen")))
        body.apply_translation((0.0, 0.0, -float(body.bounds[0][2])))

    if len(body.faces) > HEAVY_TRIANGLES:
        # §31: far past what the analysis can serve. Not refused — the limit for
        # that is an order of magnitude higher (§17.1) — but said out loud, with
        # the way out, because a model this size makes every later step slow and
        # the maps refuse themselves anyway.
        findings.append(
            Finding(
                code="ingest.very_large",
                severity="warning",
                message=_(
                    "Dieses Modell ist sehr fein vernetzt. Analysekarten und "
                    "Merkmalserkennung lehnen ab; „Netz → Dezimieren“ hilft."
                ),
                values={"triangles": len(body.faces), "comfortable": HEAVY_TRIANGLES},
            )
        )

    if not body.is_watertight and len(body.faces):
        findings.append(
            Finding(
                code="ingest.not_watertight",
                severity="warning",
                message=_("Das Modell ist nicht geschlossen."),
                values={"open_edges": _open_edge_count(body)},
            )
        )

    progress(1.0, "")
    _log.info(
        "ingested mesh: %d triangles, unit %s, %d components", len(body.faces), unit, components
    )
    return IngestResult(
        mesh=mesh.replacing(body),
        info=IngestInfo(
            unit=unit,
            scale=scale,
            welded=welded,
            removed_triangles=removed,
            components=components,
        ),
        findings=tuple(findings),
    )


def _open_edge_count(body: trimesh.Trimesh) -> int:
    """Edges belonging to a single triangle. Counted directly, without a graph library."""
    single = trimesh.grouping.group_rows(body.edges_sorted, require_count=1)
    return len(single)


def _digits_for(tolerance: float) -> int:
    """Merge tolerance expressed the way trimesh wants it: decimal places."""
    if tolerance <= 0.0:
        return 8
    return max(0, min(12, round(float(-np.log10(tolerance)))))


def _count_components(body: trimesh.Trimesh, findings: list[Finding]) -> int:
    pieces = face_components(body)
    if len(pieces) <= 1:
        return len(pieces)
    sizes = [float(body.area_faces[piece].sum()) for piece in pieces]
    largest = max(sizes)
    small = [size for size in sizes if size < largest * SMALL_COMPONENT_SHARE]
    findings.append(
        Finding(
            code="ingest.multiple_components",
            severity="info",
            message=_("Das Modell besteht aus mehreren Teilen."),
            values={"components": len(pieces)},
        )
    )
    if small:
        findings.append(
            Finding(
                code="ingest.small_components",
                severity="warning",
                message=_("Es gibt sehr kleine Einzelteile. Gelöscht wurde nichts."),
                values={"count": len(small)},
            )
        )
    return len(pieces)
