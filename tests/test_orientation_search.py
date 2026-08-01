"""Die Orientierungssuche über der Schichtanalyse (Bauplan §22.3, §40)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.orient import orient_for_print
from app.core.geom.transform import apply, place_on_bed, rotation
from app.core.ingest.loader import normalise
from app.core.scene import CancelSignal
from app.core.slice.analysis import slice_body
from app.core.slice.orientation import judge, sample_directions, search

MESHES = Path(__file__).parent / "data" / "meshes"


def corpus(name: str) -> MeshData:
    return place_on_bed(normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh)


def test_the_sampling_covers_the_sphere() -> None:
    directions = sample_directions(200, seed=1)

    assert len(directions) == 200
    for direction in directions:
        assert abs(math.sqrt(sum(value**2 for value in direction)) - 1.0) < 1e-9
    assert min(d[2] for d in directions) < -0.9, "downwards is covered"
    assert max(d[2] for d in directions) > 0.9, "upwards too"


def test_the_seed_decides_the_sampling() -> None:
    """§11.3: ohne den gespeicherten Startwert suchte dieselbe Datei nicht
    gleich.
    """
    assert sample_directions(50, seed=7) == sample_directions(50, seed=7)
    assert sample_directions(50, seed=7) != sample_directions(50, seed=8)


def test_a_tilted_plate_is_laid_down_again() -> None:
    tilted = apply(corpus("plate_holes.stl"), rotation("x", 40.0))
    found = search(tilted, count=48, seed=3)

    assert found.mesh.bounds.size[2] == pytest.approx(8.0, abs=1.0), "flat on the plate"
    assert found.tried > 48, "the sampling plus the face normals plus the starting position"


def test_the_search_beats_the_heuristic_where_it_counts() -> None:
    """§40: die Suche über 200 Kandidaten findet weniger Stützen als die
    P2-Heuristik.
    """
    body = corpus("island_tower.stl")

    heuristic = orient_for_print(body).mesh
    searched = search(body, count=200, seed=11).mesh

    heuristic_support = slice_body(heuristic, 1.0).support_volume
    searched_support = slice_body(searched, 1.0).support_volume

    assert searched_support <= heuristic_support, (
        f"the search found {searched_support:.0f} mm3, the heuristic {heuristic_support:.0f}"
    )


def test_the_result_says_what_it_saved() -> None:
    body = apply(corpus("plate_holes.stl"), rotation("y", 55.0))
    found = search(body, count=64, seed=5)

    assert found.findings and found.findings[0].code == "orient.searched"
    assert found.findings[0].source == "internal", "§22.5: never mixed with G-code"
    assert found.findings[0].values["candidates"] == found.tried
    assert found.improvement >= 0.0


def test_judging_one_direction_reports_the_real_numbers() -> None:
    body = corpus("plate_holes.stl")
    lying = judge(body, (0.0, 0.0, -1.0), 1.0)
    on_edge = judge(body, (1.0, 0.0, 0.0), 1.0)

    assert lying.first_layer_area > on_edge.first_layer_area
    assert lying.height < on_edge.height


def test_the_search_can_be_cancelled() -> None:
    """§2.8: hunderte Kandidaten brauchen Sekunden, es darf also nichts
    blockieren.
    """
    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        search(corpus("cube_clean.stl"), count=500, seed=1, cancelled=signal)


def test_the_search_reports_progress() -> None:
    seen: list[float] = []
    search(
        MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 10.0))),
        count=12,
        seed=1,
        progress=lambda fraction, text: seen.append(fraction),
    )

    assert seen and seen[-1] == pytest.approx(1.0)
