"""Vorhandene analytische Teilträger prüfen und mit ihrer Originalhaut nachführen."""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Sequence
from dataclasses import replace
from numbers import Real
from typing import TYPE_CHECKING, Final, cast

import numpy as np

from app.core.types import SurfacePatch, Transform, Vec3
from app.core.units import EPS_GEOM

if TYPE_CHECKING:
    from app.core.geom.mesh import MeshData

#: Arbeitsspeicher und Abbruchabstand des Eckennachweises, keine Formtoleranz.
PATCH_BLOCK: Final = 16_384

_KEYS: Final = {
    "plane": frozenset(("centre", "axis")),
    "cylinder": frozenset(("centre", "axis", "radius")),
    "cone": frozenset(("apex", "axis", "half_angle")),
    "sphere": frozenset(("centre", "radius")),
    "torus": frozenset(("centre", "axis", "ring_radius", "tube_radius")),
}


def _check(check_cancelled: Callable[[], None] | None) -> None:
    if check_cancelled is not None:
        check_cancelled()


def _number(value: object) -> bool:
    return (
        not isinstance(value, (bool, np.bool_)) and isinstance(value, Real) and math.isfinite(value)
    )


def _vector(value: object) -> np.ndarray | None:
    if not isinstance(value, tuple) or len(value) != 3 or not all(_number(v) for v in value):
        return None
    return np.asarray(value, dtype=np.float64)


def _point(vector: np.ndarray) -> Vec3:
    return float(vector[0]), float(vector[1]), float(vector[2])


def valid_patch(
    patch: SurfacePatch,
    *,
    face_count: int | None = None,
    allowed_indices: Collection[int] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Nur vollständige Zahlenverträge und wirkliche, eindeutige Dreiecksnummern zulassen."""
    _check(check_cancelled)
    if patch.kind not in _KEYS or patch.source not in {"native", "facets", "fit"}:
        return False
    if set(patch.params) != _KEYS[patch.kind] or not patch.face_indices:
        return False
    for name, value in patch.params.items():
        if name in {"centre", "apex", "axis"}:
            vector = _vector(value)
            if vector is None:
                return False
            if name == "axis" and not 0.0 < math.hypot(*vector) < math.inf:
                return False
        elif not _number(value) or not float(cast(float, value)) > 0.0:
            return False
    if patch.kind == "cone" and float(cast(float, patch.params["half_angle"])) >= math.pi / 2.0:
        return False
    if patch.kind == "torus" and float(cast(float, patch.params["ring_radius"])) <= float(
        cast(float, patch.params["tube_radius"])
    ):
        return False
    allowed = (
        allowed_indices
        if isinstance(allowed_indices, (set, frozenset))
        else set(allowed_indices)
        if allowed_indices is not None
        else None
    )
    seen: set[int] = set()
    for position, index in enumerate(patch.face_indices):
        if position % PATCH_BLOCK == 0:
            _check(check_cancelled)
        if (
            isinstance(index, (bool, np.bool_))
            or not isinstance(index, (int, np.integer))
            or index < 0
            or index in seen
            or (face_count is not None and index >= face_count)
            or (allowed is not None and index not in allowed)
        ):
            return False
        seen.add(index)
    return True


def planar_patch(
    mesh: MeshData,
    indices: Sequence[int] | np.ndarray,
    centre: Vec3,
    normal: Vec3,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> SurfacePatch | None:
    """Alle Originalecken gegen die bereits gewählte Ebene prüfen, ohne sie neu einzupassen."""
    _check(check_cancelled)
    patch = SurfacePatch("plane", {"centre": centre, "axis": normal}, tuple(indices), "facets")
    if not valid_patch(patch, face_count=mesh.triangle_count, check_cancelled=check_cancelled):
        return None
    axis = np.asarray(normal, dtype=np.float64)
    axis /= math.hypot(*axis)
    origin = np.asarray(centre, dtype=np.float64)
    raw = mesh.raw
    for start in range(0, len(indices), PATCH_BLOCK):
        _check(check_cancelled)
        part = list(indices[start : start + PATCH_BLOCK])
        triangles = np.asarray(raw.vertices)[np.asarray(raw.faces)[part]]
        distances = np.einsum("ijk,k->ij", triangles - origin, axis)
        if not np.all(np.isfinite(distances)) or np.any(np.abs(distances) > EPS_GEOM):
            return None
        if np.any(np.asarray(raw.area_faces)[part] <= 0.0):
            return None
    _check(check_cancelled)
    return replace(
        patch,
        params={"centre": centre, "axis": _point(axis)},
        face_indices=tuple(int(index) for index in indices),
    )


def clipped_patches(
    patches: Sequence[SurfacePatch],
    indices: Collection[int],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[SurfacePatch, ...]:
    """Nur den tatsächlichen Anteil übernehmen, ohne verschiedene Träger zu mitteln."""
    _check(check_cancelled)
    allowed = indices if isinstance(indices, (set, frozenset)) else set(indices)
    result = []
    for patch in patches:
        if not valid_patch(patch, check_cancelled=check_cancelled):
            continue
        selected: list[int] = []
        for start in range(0, len(patch.face_indices), PATCH_BLOCK):
            _check(check_cancelled)
            selected.extend(
                index
                for index in patch.face_indices[start : start + PATCH_BLOCK]
                if index in allowed
            )
        if selected:
            result.append(
                patch
                if len(selected) == len(patch.face_indices)
                else replace(patch, face_indices=tuple(selected))
            )
    _check(check_cancelled)
    return tuple(result)


def reindexed_patches(
    patches: Sequence[SurfacePatch],
    index_map: Sequence[int] | np.ndarray,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[SurfacePatch, ...]:
    """Ausschnittsdreiecke über die belegte Reihenfolge auf das Original zurückführen."""
    _check(check_cancelled)
    result = []
    for patch in patches:
        if not valid_patch(patch, face_count=len(index_map), check_cancelled=check_cancelled):
            continue
        selected: list[int] = []
        for start in range(0, len(patch.face_indices), PATCH_BLOCK):
            _check(check_cancelled)
            selected.extend(
                index_map[index] for index in patch.face_indices[start : start + PATCH_BLOCK]
            )
        # Keine negativen Nummern und keine ungültige Mehrfachzuordnung reparieren.
        mapped = replace(patch, face_indices=tuple(selected))
        if valid_patch(mapped, check_cancelled=check_cancelled):
            result.append(replace(mapped, face_indices=tuple(int(index) for index in selected)))
    return tuple(result)


def radial_scales(linear: np.ndarray, axis: np.ndarray) -> tuple[float, float] | None:
    """Vorhandener Kreis-Erhaltungsnachweis: radiale Gleichheit und orthogonale Achse."""
    direction = axis / math.hypot(*axis)
    _u, _s, vectors = np.linalg.svd(direction.reshape(1, 3))
    radial = linear @ vectors[1:].T
    factors = np.linalg.svd(radial, compute_uv=False)
    along = linear @ direction
    if not (
        np.allclose(factors, factors[0], rtol=0.0, atol=EPS_GEOM)
        and (np.abs(along @ radial) <= EPS_GEOM).all()
    ):
        return None
    return float(factors[0]), float(np.linalg.norm(along))


def transformed_patches(
    patches: Sequence[SurfacePatch],
    transform: Transform | np.ndarray,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[SurfacePatch, ...]:
    """Nur analytisch erhaltene Teilträger mitführen; eine Ellipse bleibt kein Kreis."""
    _check(check_cancelled)
    if not patches:
        return ()
    matrix = np.asarray(transform, dtype=np.float64)
    if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
        return ()
    if not np.allclose(matrix[3], (0.0, 0.0, 0.0, 1.0), rtol=0.0, atol=EPS_GEOM):
        return ()
    linear = matrix[:3, :3]
    scales = np.linalg.svd(linear, compute_uv=False)
    if scales[-1] <= 0.0:
        return ()
    uniform = bool(np.allclose(scales, scales[0], rtol=0.0, atol=EPS_GEOM))
    result = []
    for patch in patches:
        if not valid_patch(patch, check_cancelled=check_cancelled):
            continue
        params = dict(patch.params)
        point_key = "apex" if patch.kind == "cone" else "centre"
        origin = np.asarray(params[point_key], dtype=np.float64)
        params[point_key] = _point(linear @ origin + matrix[:3, 3])
        axis = np.asarray(params["axis"], dtype=np.float64) if "axis" in params else None
        if axis is not None:
            direction = np.linalg.solve(linear.T, axis) if patch.kind == "plane" else linear @ axis
            direction /= math.hypot(*direction)
            params["axis"] = _point(direction)
        if patch.kind != "plane":
            if uniform:
                radial, axial = float(scales[0]), float(scales[0])
            elif patch.kind in {"cylinder", "cone"} and axis is not None:
                factors = radial_scales(linear, axis)
                if factors is None:
                    continue
                radial, axial = factors
            else:
                continue
            for name in ("radius", "ring_radius", "tube_radius"):
                if name in params:
                    params[name] = float(cast(float, params[name])) * radial
            if patch.kind == "cone" and not uniform:
                params["half_angle"] = math.atan(
                    math.tan(float(cast(float, params["half_angle"]))) * radial / axial
                )
        moved = replace(patch, params=params)
        if valid_patch(moved, check_cancelled=check_cancelled):
            result.append(moved)
    _check(check_cancelled)
    return tuple(result)
