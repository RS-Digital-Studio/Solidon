"""Gebündelte Formen rechnen Bit für Bit wie ihre Schleife (RM-544, Gebündelt rechnen).

``shapes.thread_body`` legte jede Ecke des Gangs Ring für Ring in Python an,
``shapes.rounded_box`` jede Sehne seiner Ecken; beide rechnen jetzt über Felder.
Ein Bit Unterschied in einer Ecke wüchse durch die Boolesche Kette zu einem
anderen Netz (RM-187) und machte jeden Bereichsnachweis und jedes gespeicherte
Projekt ungültig. Deshalb steht hier der alte Weg wörtlich als Orakel, und
verglichen werden Ecken und Dreiecke als Bytes — an der Form selbst und an
jedem Baustein, der sie baut, an mehreren Ecken seines Bereichs.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts import shapes
from app.core.units import EPS_GEOM, MAX_FACET_SAG, exact_cos, exact_sin


def _loop_thread_body(
    diameter: float,
    pitch: float,
    height: float,
    *,
    depth: float | None = None,
    segments: int = shapes.SEGMENTS,
    internal: bool = False,
    profile: shapes.ThreadProfile = "flat",
    starts: int = 1,
    left: bool = False,
    taper: float = 0.0,
    reference: float = 0.0,
) -> MeshData:
    """Der Gang Ring für Ring, wie ``shapes.thread_body`` ihn bis RM-544 baute."""
    lead = starts * pitch
    steps = max(round(height / lead), 1) * segments
    outline = shapes.ridge_profile(diameter, pitch, depth=depth, internal=internal, profile=profile)
    angles = np.linspace(0.0, 2.0 * math.pi * height / lead, steps + 1)
    up = np.array([0.0, 0.0, 1.0])
    blocks: list[np.ndarray] = []
    for course in range(starts):
        heights = np.linspace(0.0, height, steps + 1) + course * pitch
        rings = []
        for angle, level in zip(angles, heights, strict=True):
            direction = np.array([exact_cos(angle), exact_sin(angle), 0.0])
            if taper:
                rings.append(
                    [
                        direction * (radial + taper * (level + axial - reference))
                        + up * (level + axial)
                        for radial, axial in outline
                    ]
                )
            else:
                rings.append(
                    [direction * radial + up * (level + axial) for radial, axial in outline]
                )
        blocks.append(np.array([point for ring in rings for point in ring], dtype=float))

    per_ring = len(outline)
    ring_count = steps + 1
    block = ring_count * per_ring + (0 if per_ring == 4 else 2)
    vertices_list: list[np.ndarray] = []
    faces: list[list[int]] = []
    for course, points in enumerate(blocks):
        offset = course * block
        if per_ring != 4:
            first_ring = points[:per_ring]
            last_ring = points[-per_ring:]
            points = np.vstack([points, first_ring.mean(axis=0), last_ring.mean(axis=0)])
        vertices_list.append(points)
        for index in range(ring_count - 1):
            base = offset + index * per_ring
            following = base + per_ring
            for corner in range(per_ring):
                first = base + corner
                second = base + (corner + 1) % per_ring
                third = following + (corner + 1) % per_ring
                fourth = following + corner
                faces.append([first, second, third])
                faces.append([first, third, fourth])
        start_ring = [offset + corner for corner in range(per_ring)]
        last = offset + (ring_count - 1) * per_ring
        end_ring = [last + corner for corner in range(per_ring)]
        if per_ring == 4:
            faces.extend(_loop_cap(start_ring, flip=True))
            faces.extend(_loop_cap(end_ring, flip=False))
        else:
            centres = offset + ring_count * per_ring
            faces.extend(_loop_fan(start_ring, centres, flip=True))
            faces.extend(_loop_fan(end_ring, centres + 1, flip=False))

    vertices = np.vstack(vertices_list) if len(vertices_list) > 1 else vertices_list[0]
    if left:
        vertices = vertices * np.array([1.0, -1.0, 1.0])
        faces = [list(reversed(face)) for face in faces]
    body = trimesh.Trimesh(vertices=vertices, faces=np.array(faces, dtype=np.int64), process=True)
    trimesh.repair.fix_normals(body, multibody=starts > 1)
    return MeshData.of(body)


def _loop_cap(indices: list[int], flip: bool) -> list[list[int]]:
    first, second, third, fourth = indices
    faces = [[first, second, third], [first, third, fourth]]
    return [list(reversed(face)) for face in faces] if flip else faces


def _loop_fan(indices: list[int], centre: int, flip: bool) -> list[list[int]]:
    faces = [
        [centre, indices[corner], indices[(corner + 1) % len(indices)]]
        for corner in range(len(indices))
    ]
    return [list(reversed(face)) for face in faces] if flip else faces


def _loop_rounded_box(width: float, depth: float, height: float, radius: float) -> Any:
    """Der gerundete Quader Sehne für Sehne, wie ``shapes.rounded_box`` ihn bis RM-544 baute."""
    if radius <= EPS_GEOM or shapes.building_exact():
        return _original_rounded_box(width, depth, height, radius)
    import manifold3d

    count = 4
    while radius * (1 - exact_cos(math.pi / (4 * count))) > MAX_FACET_SAG:
        count += 1
    vertices: list[tuple[float, float]] = []
    for quadrant, (cx, cy) in enumerate(shapes.rounded_corners(width, depth, radius)):
        for angle in np.linspace(quadrant * math.pi / 2, (quadrant + 1) * math.pi / 2, count + 1):
            point = (cx + radius * exact_cos(angle), cy + radius * exact_sin(angle))
            if not vertices or math.dist(point, vertices[-1]) > EPS_GEOM:
                vertices.append(point)
    built = manifold3d.CrossSection([vertices]).extrude(height).to_mesh64()
    return MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(built.vert_properties[:, :3], copy=True),
            faces=np.array(built.tri_verts, copy=True),
            process=False,
        )
    )


_original_rounded_box = shapes.rounded_box


def _bytes(mesh: Any) -> tuple[bytes, bytes]:
    raw = as_mesh_data(mesh).raw
    return (
        np.ascontiguousarray(raw.vertices, dtype=np.float64).tobytes(),
        np.ascontiguousarray(raw.faces, dtype=np.int64).tobytes(),
    )


@pytest.mark.parametrize(
    "case",
    [
        {"diameter": 8.0, "pitch": 1.25, "height": 6.0},
        {"diameter": 8.0, "pitch": 1.25, "height": 6.0, "internal": True},
        {"diameter": 20.955, "pitch": 1.814, "height": 9.0, "profile": "whitworth"},
        {
            "diameter": 20.955,
            "pitch": 1.814,
            "height": 9.0,
            "profile": "whitworth",
            "internal": True,
        },
        {"diameter": 21.2, "pitch": 1.814, "height": 7.0, "profile": "npt"},
        {"diameter": 24.0, "pitch": 2.0, "height": 12.0, "starts": 3, "segments": 96},
        {"diameter": 30.0, "pitch": 2.309, "height": 9.0, "profile": "whitworth", "starts": 2},
        {"diameter": 10.0, "pitch": 1.5, "height": 6.0, "left": True},
        {"diameter": 10.0, "pitch": 1.5, "height": 6.0, "left": True, "starts": 2},
        {"diameter": 21.0, "pitch": 1.814, "height": 8.0, "taper": 0.03125, "reference": 3.0},
        {"diameter": 16.0, "pitch": 2.0, "height": 6.0, "depth": 0.5},
        {"diameter": 120.0, "pitch": 3.0, "height": 9.0, "segments": 144},
    ],
    ids=[
        "M8",
        "M8-innen",
        "G1/2",
        "G1/2-innen",
        "NPT",
        "dreigaengig",
        "whitworth-zweigaengig",
        "links",
        "links-zweigaengig",
        "kegel",
        "tiefe",
        "weit",
    ],
)
def test_the_ridge_is_the_mesh_its_loop_built_bit_for_bit(case: dict[str, Any]) -> None:
    """Jede Schalterstellung des Gangs: Profil, innen, Gänge, links, Kegel, Tiefe, Sehnen."""
    assert _bytes(shapes.thread_body(**case)) == _bytes(_loop_thread_body(**case))


#: Größte Zahl von Gangecken einer Bausteinecke im Vergleich; das Orakel rechnet
#: je Station zwei Reihen in ``decimal``.
_CHEAP_POINTS = 6000


def _cheap_corners(name: str, count: int) -> list[dict[str, Any]]:
    """Ecken aus dem Bereichsnachweis, eigenes Maß und Tabellengrößen getrennt verteilt."""
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE, thread_of, thread_points
    from app.core.knowledge.parts.range_check import LIBRARY_MAX_CORNERS, _pinned, corners

    spec = PARTS.get(name)
    cheap = []
    for values in corners(spec.params, LIBRARY_MAX_CORNERS, _pinned(spec)):
        dims = thread_of(spec.params(**values))
        reach = float(values.get("length", dims.nominal))
        if dims.starts * thread_points(dims.nominal, dims.pitch, reach, dims.profile) <= (
            _CHEAP_POINTS
        ):
            cheap.append(values)
    own = [values for values in cheap if values["size"] == CUSTOM_SIZE]
    table = [values for values in cheap if values["size"] != CUSTOM_SIZE]
    return [
        values for group in (own, table) for values in group[:: max(1, len(group) // count)][:count]
    ]


def _built_both_ways(
    monkeypatch: pytest.MonkeyPatch, name: str, values: dict[str, Any], form: str, loop: Any
) -> tuple[Any, Any]:
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get(name)

    def build() -> Any:
        try:
            return _bytes(spec.fn(spec.params(**values)).mesh)
        except Exception as error:  # eine Absage muss auf beiden Wegen dieselbe sein
            return type(error).__name__, str(error)

    bundled = build()
    with monkeypatch.context() as patched:
        patched.setattr(shapes, form, loop)
        looped = build()
    return bundled, looped


@pytest.mark.parametrize("name", ["printed_thread", "printed_screw", "printed_nut", "threaded_rod"])
def test_every_thread_part_builds_its_old_mesh_at_its_corners(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Je Gewindebaustein Ecken des Bereichs, rechts und links: das Netz der Schleife."""
    chosen = _cheap_corners(name, 4)
    assert len(chosen) >= 6, chosen
    for values in chosen:
        for left in (False, True):
            corner = {**values, "left_hand": left}
            bundled, looped = _built_both_ways(
                monkeypatch, name, corner, "thread_body", _loop_thread_body
            )
            assert bundled == looped, corner


@pytest.mark.parametrize("name", ["organizer_tray", "organizer_rim"])
def test_every_rounded_part_builds_its_old_mesh_at_its_corners(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Wanne und Rand an jeder Ecke ihres Bereichs: dasselbe Netz wie Sehne für Sehne."""
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.range_check import LIBRARY_MAX_CORNERS, _pinned, corners

    spec = PARTS.get(name)
    rounded = [
        values
        for values in corners(spec.params, LIBRARY_MAX_CORNERS, _pinned(spec))
        if values["radius"] > 0.0
    ]
    assert rounded
    for values in rounded:
        bundled, looped = _built_both_ways(
            monkeypatch, name, values, "rounded_box", _loop_rounded_box
        )
        assert bundled == looped, values
