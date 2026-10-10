"""Vorhandene analytische Teilträger prüfen und mit ihrer Originalhaut nachführen."""

from __future__ import annotations

import functools
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
    return _valid_numbers(patch) and _valid_indices(
        patch, face_count, allowed_indices, check_cancelled
    )


def _valid_numbers(patch: SurfacePatch) -> bool:
    """Der Zahlenvertrag eines Teilträgers: Art, Quelle, Werte — ohne die Dreiecksnummern."""
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
    return not (
        patch.kind == "torus"
        and float(cast(float, patch.params["ring_radius"]))
        <= float(cast(float, patch.params["tube_radius"]))
    )


def _valid_indices(
    patch: SurfacePatch,
    face_count: int | None,
    allowed_indices: Collection[int] | None,
    check_cancelled: Callable[[], None] | None,
) -> bool:
    """Wirkliche, eindeutige Dreiecksnummern innerhalb der Grenzen."""
    # **Die Dreiecksnummern werden blockweise als Feld geprüft**, nicht eine je
    # Schleifenrunde: An der Lochplatte mit 204 000 Dreiecken kostete die
    # Schleife über die 51 712 Nummern einer Deckfläche zwölf Millisekunden je
    # Fläche, und jede Fläche wird bei einer Erkennung mehrfach gefragt
    # (gemessen am 21.09.2026). Die Arten der Einträge zählt ``type`` in C —
    # ein Wahrheitswert wird von ``np.asarray`` sonst still zur Eins.
    kinds = set(map(type, patch.face_indices))
    if any(
        issubclass(kind, (bool, np.bool_)) or not issubclass(kind, (int, np.integer))
        for kind in kinds
    ):
        return False
    numbers = np.asarray(patch.face_indices, dtype=np.int64)
    allowed = (
        np.fromiter(allowed_indices, dtype=np.int64, count=len(allowed_indices))
        if allowed_indices is not None
        else None
    )
    for start in range(0, len(numbers), PATCH_BLOCK):
        _check(check_cancelled)
        block = numbers[start : start + PATCH_BLOCK]
        if bool(np.any(block < 0)) or (
            face_count is not None and bool(np.any(block >= face_count))
        ):
            return False
        if allowed is not None and not bool(np.all(np.isin(block, allowed))):
            return False
    _check(check_cancelled)
    return len(np.unique(numbers)) == len(numbers)


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
    numbers = np.asarray(indices, dtype=np.int64)
    vertices = np.asarray(raw.vertices)
    faces = np.asarray(raw.faces)
    areas = np.asarray(raw.area_faces)
    for start in range(0, len(numbers), PATCH_BLOCK):
        _check(check_cancelled)
        part = numbers[start : start + PATCH_BLOCK]
        triangles = vertices[faces[part]]
        distances = np.einsum("ijk,k->ij", triangles - origin, axis)
        if not np.all(np.isfinite(distances)) or np.any(np.abs(distances) > EPS_GEOM):
            return None
        if np.any(areas[part] <= 0.0):
            return None
    _check(check_cancelled)
    return replace(
        patch,
        params={"centre": centre, "axis": _point(axis)},
        face_indices=tuple(numbers.tolist()),
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


@functools.lru_cache(maxsize=32)
def _frame(key: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool] | None:
    """Was :func:`transformed_patches` an der Abbildung selbst prüft — einmal je Abbildung.

    Gefragt wird sie je Merkmal mit derselben Matrix: am Eiffelturm 14 634-mal
    je Verschieben, mit Singulärwertzerlegung und zwei ``allclose`` jedes Mal
    (RM-568). Dieselben Rechnungen auf denselben Zahlen, die Felder nur
    lesbar, weil sie geteilt werden.
    """
    matrix = np.frombuffer(key, dtype=np.float64).reshape(4, 4).copy()
    if not np.all(np.isfinite(matrix)):
        return None
    if not np.allclose(matrix[3], (0.0, 0.0, 0.0, 1.0), rtol=0.0, atol=EPS_GEOM):
        return None
    linear = matrix[:3, :3]
    scales = np.linalg.svd(linear, compute_uv=False)
    if scales[-1] <= 0.0:
        return None
    uniform = bool(np.allclose(scales, scales[0], rtol=0.0, atol=EPS_GEOM))
    for shared in (matrix, linear, scales):
        shared.flags.writeable = False
    return matrix, linear, scales, uniform


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
    if matrix.shape != (4, 4):
        return ()
    frame = _frame(np.ascontiguousarray(matrix).tobytes())
    if frame is None:
        return ()
    matrix, linear, scales, uniform = frame
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
        # Die Dreiecksnummern sind dieselben, eben geprüft; neu zu prüfen ist nur,
        # was die Abbildung geändert hat (RM-636): Die Nummernprüfung sortierte
        # je Teilträger alle Nummern ein zweites Mal, bei jedem Verschieben.
        _check(check_cancelled)
        if _valid_numbers(moved):
            result.append(moved)
    _check(check_cancelled)
    return tuple(result)
