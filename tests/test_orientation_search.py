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
from app.core.types import Profile

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


def test_the_search_slices_each_direction_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Achsen stehen fest und als Flächennormalen in derselben Kandidatenliste.

    Eine zweite Schichtanalyse derselben Lage kann das Ergebnis nicht ändern;
    sie machte die Suche nur langsamer.
    """
    from app.core.slice import orientation

    seen = []

    def record(_mesh: MeshData, direction: tuple[float, float, float], _height: float):
        seen.append(direction)
        return orientation.Candidate(direction, float(len(seen)), 1.0, 1.0)

    monkeypatch.setattr(
        orientation,
        "face_candidates",
        lambda _mesh: [(0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
    )
    monkeypatch.setattr(
        orientation,
        "sample_directions",
        lambda _count, _seed: [(0.0, 0.0, -1.0), (1.0, 0.0, 0.0)],
    )
    monkeypatch.setattr(orientation, "judge", record)

    result = orientation.search(MeshData.of(trimesh.creation.box()), count=2)

    assert seen == [(0.0, 0.0, -1.0), (1.0, 0.0, 0.0)]
    assert result.tried == len(seen)


def test_a_tilted_plate_is_laid_down_again() -> None:
    tilted = apply(corpus("plate_holes.stl"), rotation("x", 40.0))
    found = search(tilted, count=48, seed=3)

    assert found.mesh.bounds.size[2] == pytest.approx(8.0, abs=1.0), "flat on the plate"
    assert found.tried > 48, "the sampling plus the face normals plus the starting position"


def bar() -> MeshData:
    """Eine lange gefaste Prismenstange — die Form, an der der Fund entstand.

    22 auf 12 im Querschnitt, 140 lang, unten 1,2 mm gefast und oben 6 mm. Auf
    die **Fasen** kommt es an: Ein glatter Quader hat in jeder Lage eine ebene
    Fläche unten, und die gewinnt von selbst. Mit ihnen stehen die Flanken in
    einer diagonalen Lage 47° zur Waagerechten — gerade steiler als die
    Stützschwelle, also selbsttragend und ohne Stützmaterial. Genau diese Lage
    hat die Suche gewählt, und sie steht auf einer Kante.

    Nachgebaut aus einer Querstange, die ein Kunde heruntergeladen hatte.
    """
    from shapely.geometry import Polygon

    outline = Polygon(
        [
            (-9.8, 0.0),
            (9.8, 0.0),
            (11.0, 1.2),
            (11.0, 6.0),
            (5.0, 12.0),
            (-5.0, 12.0),
            (-11.0, 6.0),
            (-11.0, 1.2),
        ]
    )
    bar_body = trimesh.creation.extrude_polygon(outline, height=140.0)
    # Und die zwei Sechskantzapfen an den Enden. **Auf sie kommt es genauso
    # an:** Sie stehen quer heraus, kosten in der liegenden Lage Stützmaterial
    # und in der diagonalen keines — ohne sie gewinnt die liegende Lage von
    # selbst, und der Fund lässt sich nicht nachstellen.
    pins = [
        trimesh.creation.cylinder(radius=4.0734, height=9.0, sections=6, transform=matrix)
        for matrix in (
            trimesh.transformations.translation_matrix((0.0, 0.0, 140.0)),
            trimesh.transformations.translation_matrix((0.0, 0.0, 0.0)),
        )
    ]
    whole = trimesh.boolean.union([bar_body, *pins])
    return place_on_bed(MeshData.of(whole))


def test_a_pose_that_cannot_stand_never_wins(profile: Profile) -> None:
    """Ein paar Kubikmillimeter Stützmaterial dürfen keine Lage kaufen, die
    nicht stehen kann (§22.2).

    Gemessen an der nachgebauten Verbinderstange: die Suche wählte eine
    diagonale Lage mit 0,6 mm³ Stütze und **0,1 mm²** erster Schicht gegen die
    liegende mit 11,1 mm³ und 1424 mm². Der Vergleich war richtig, die Zahl
    auch — nur ist ein Hundertstel Quadratmillimeter kein Stand.
    """
    body = bar()

    ohne = search(body, count=60, seed=0)
    mit = search(body, count=60, seed=0, profile=profile)

    assert ohne.best.first_layer_area < profile.smallest_first_layer, (
        "ohne Profil gewinnt weiter die Kante"
    )
    assert mit.best.first_layer_area >= profile.smallest_first_layer
    assert mit.best.support_volume > ohne.best.support_volume, (
        "der Stand kostet Stützmaterial — das ist der Preis und der Sinn"
    )
    assert mit.best.height < ohne.best.height, "und sie liegt, statt zu kippeln"


def test_the_floor_only_ranks_and_never_refuses(profile: Profile) -> None:
    """Ein Körper, dessen **jede** Lage unter der Grenze bleibt, wird nicht
    abgelehnt — dann tragen alle Kandidaten dieselbe Antwort, und es bleibt
    beim alten Vergleich. Gesagt wird es trotzdem.
    """
    tiny = place_on_bed(MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=2.0)))

    found = search(tiny, count=24, seed=5, profile=profile)

    assert found.mesh is not None, "eine Antwort kommt in jedem Fall"
    assert found.best.first_layer_area < profile.smallest_first_layer
    assert "orient.no_footing" in {finding.code for finding in found.findings}


def test_a_real_footing_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst stünde der Satz unter jeder Suche."""
    found = search(corpus("plate_holes.stl"), count=24, seed=5, profile=profile)

    assert "orient.no_footing" not in {finding.code for finding in found.findings}


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
