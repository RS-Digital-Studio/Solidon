"""Die Orientierungssuche über der Schichtanalyse (Bauplan §22.3, §40)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.orient import AXES, Orientation, orient_for_print, ranked_orientations
from app.core.geom.transform import apply, place_on_bed, rotation
from app.core.ingest.loader import normalise
from app.core.scene import CancelSignal
from app.core.slice.analysis import slice_body
from app.core.slice.orientation import (
    FINALISTS,
    SUPPORT_FINALISTS,
    best_face_candidate,
    judge,
    search,
)
from app.core.types import Profile
from tests.helpers import at_the_start_rule

MESHES = Path(__file__).parent / "data" / "meshes"


def corpus(name: str) -> MeshData:
    return place_on_bed(normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh)


def test_geometric_candidates_include_new_convex_hull_normals():
    import numpy as np

    from app.core.geom.orient import candidates

    first = trimesh.creation.box(extents=(10, 10, 10))
    second = first.copy()
    second.apply_translation((20, 20, 20))
    mesh = MeshData.of(trimesh.util.concatenate((first, second)))
    found = candidates(mesh)
    assert any(np.count_nonzero(np.abs(direction) > 0.1) == 2 for direction in found)
    assert found == candidates(mesh)


def test_a_large_footing_does_not_hide_a_centre_of_mass_outside_it(profile):
    pillar = trimesh.creation.box(extents=(10, 10, 30))
    pillar.apply_translation((0, 0, 15))
    arm = trimesh.creation.box(extents=(80, 10, 5))
    arm.apply_translation((35, 0, 32.5))
    mesh = MeshData.of(trimesh.boolean.union((pillar, arm)))
    result = judge(mesh, (0, 0, -1), 1.0, profile.printer.layer_height / 2.0)
    assert result.first_layer_area > profile.smallest_first_layer
    assert not result.stable


@pytest.mark.parametrize("organic", [False, True])
def test_shortlist_matches_the_fully_sliced_geometric_candidates(organic, profile):
    from app.core.geom.orient import candidates
    from app.core.slice.orientation import best_of

    if organic:
        raw = trimesh.creation.icosphere(subdivisions=1, radius=12)
        raw.apply_scale((1.0, 0.7, 1.5))
        mesh = MeshData.of(raw)
    else:
        mesh = corpus("plate_holes.stl")
    result = search(mesh, profile=profile, count=80)
    full = best_of(
        [
            judge(mesh, direction, 1.0, profile.printer.layer_height / 2.0)
            for direction in dict.fromkeys(candidates(mesh, hull_limit=80))
        ],
        profile.smallest_first_layer,
    )
    assert result.best.support_volume <= full.support_volume * 1.05 + 1e-6
    # Zwei Listen Finalisten — nach Heuristik und nach geschätztem Stützraum
    # (RM-190) —, die Achsen und die Ausgangslage; nie das ganze Feld.
    assert result.tried <= FINALISTS + SUPPORT_FINALISTS + 1 + len(AXES)


@pytest.mark.parametrize(
    ("supports", "standing_indices", "expected_indices"),
    [
        pytest.param(
            (50.0, 30.0, 100.0, 10.0, 25.0, 60.0), (0, 4, 5), (0, 1, 4), id="cheaper-rest-pose"
        ),
        pytest.param(
            (100.0, 200.0, 50.0, 10.0, 25.0, 300.0), (2, 4, 5), (0, 2, 4), id="keep-standing-tail"
        ),
        pytest.param(
            (100.0, 200.0, 50.0, 10.0, 25.0, 300.0),
            (0, 1, 2, 4, 5),
            (0, 1, 2),
            id="all-selected-stand",
        ),
    ],
)
def test_limited_ranking_keeps_a_cheaper_standing_candidate_from_the_rest(
    monkeypatch: pytest.MonkeyPatch,
    supports: tuple[float, ...],
    standing_indices: tuple[int, ...],
    expected_indices: tuple[int, ...],
) -> None:
    """Ein günstiger Stand aus dem Rest verdrängt keine vorhandene Standlage."""
    from app.core.geom import orient

    directions = [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, -1.0),
    ]
    footprints = (100.0, 80.0, 60.0, 10.0, 9.0, 8.0)
    scored = [
        orient.Orientation(direction, footprints[index], 0.0, 0.0, supports[index])
        for index, direction in enumerate(directions)
    ]
    monkeypatch.setattr(orient, "candidates", lambda _mesh: directions)
    monkeypatch.setattr(orient, "evaluate_directions", lambda *_args, **_kwargs: scored)

    checked: list[tuple[float, float, float]] = []

    def standing(entry: orient.Orientation) -> bool:
        checked.append(entry.direction)
        return directions.index(entry.direction) in standing_indices

    result = ranked_orientations(MeshData.of(trimesh.creation.box()), limit=3, standing=standing)

    assert [entry.direction for entry in result] == [
        directions[index] for index in expected_indices
    ]
    assert directions[5] not in checked, "teurer geschätzte Reste müssen nicht geprüft werden"


def test_contact_selection_matches_brute_force_at_both_tolerance_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die vektorisierte Vorauswahl behält nur Dreiecke am Toleranzband."""
    import numpy as np

    from app.core.slice import orientation
    from app.core.units import EPS_GEOM

    plane = 0.2

    def cuboid(x: float, low: float, high: float) -> trimesh.Trimesh:
        raw = trimesh.creation.box(extents=(1.0, 1.0, high - low))
        raw.apply_translation((x, 0.0, (low + high) / 2.0))
        return raw

    parts = [
        cuboid(0.0, 0.0, 1.0),
        cuboid(10.0, plane - 0.05 - 2.0 * EPS_GEOM, plane - 2.0 * EPS_GEOM),
        cuboid(20.0, plane - 0.05 - 2.5 * EPS_GEOM, plane - 2.5 * EPS_GEOM),
        cuboid(30.0, plane + 2.0 * EPS_GEOM, plane + 0.05 + 2.0 * EPS_GEOM),
        cuboid(40.0, plane + 2.5 * EPS_GEOM, plane + 0.05 + 2.5 * EPS_GEOM),
    ]
    body = MeshData.of(trimesh.util.concatenate(parts))
    seen_groups: set[int] = set()

    def capture_band(mesh: MeshData, heights: np.ndarray, **_kwargs: Any):
        assert heights.tolist() == [plane]
        triangles = np.asarray(mesh.raw.vertices)[np.asarray(mesh.raw.faces)]
        seen_groups.update(
            int(round(float(triangle[:, 0].mean() / 10.0)) * 10) for triangle in triangles
        )
        from shapely.geometry import Polygon

        return [Polygon(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))]

    monkeypatch.setattr(orientation, "cross_sections", capture_band)
    contact, centre = orientation._contact(body, np.eye(4), plane)

    # Die Sollmenge entsteht durch einen vollständigen Dreieckslauf, nicht
    # durch dieselbe vektorisierte Auswahl wie im Produktcode.
    reference_groups: set[int] = set()
    vertices = np.asarray(body.raw.vertices, dtype=float)
    for face in np.asarray(body.raw.faces, dtype=np.int64):
        triangle = vertices[face]
        if (
            float(triangle[:, 2].min()) <= plane + 2.0 * EPS_GEOM
            and float(triangle[:, 2].max()) >= plane - 2.0 * EPS_GEOM
        ):
            reference_groups.add(int(round(float(triangle[:, 0].mean() / 10.0)) * 10))

    assert reference_groups == {0, 10, 30}, "die beiden exakten Ränder zählen, außen nicht"
    assert seen_groups == reference_groups
    assert contact is not None
    assert np.isfinite(centre).all()


def test_the_search_slices_each_direction_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Achsen stehen fest und als Flächennormalen in derselben Kandidatenliste.

    Eine zweite Schichtanalyse derselben Lage kann das Ergebnis nicht ändern;
    sie machte die Suche nur langsamer.
    """
    from app.core.slice import orientation

    seen = []

    def record(
        _mesh: MeshData,
        direction: tuple[float, float, float],
        _height: float,
        _footing: float | None = None,
        *,
        overhang_angle: float | None = None,
    ):
        seen.append(direction)
        return orientation.Candidate(direction, float(len(seen)), 1.0, 1.0)

    monkeypatch.setattr(
        orientation,
        "face_candidates",
        lambda _mesh, **_kwargs: [(0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
    )
    monkeypatch.setattr(orientation, "judge", record)

    result = orientation.search(MeshData.of(trimesh.creation.box()), count=2)

    assert seen == [(0.0, 0.0, -1.0), (1.0, 0.0, 0.0)]
    assert result.tried == len(seen)


def test_a_tilted_plate_is_laid_down_again() -> None:
    tilted = apply(corpus("plate_holes.stl"), rotation("x", 40.0))
    found = search(tilted, count=48)

    assert found.mesh.bounds.size[2] == pytest.approx(8.0, abs=1.0), "flat on the plate"
    # ``tried`` zählt seit dem 06.09.2026 die **geschnittenen** Lagen — die
    # Suche prüft alle Richtungen an den Flächennormalen und schneidet nur
    # die Finalisten. Die geprüfte Menge steht im Befund.
    assert found.findings[0].values["candidates"] >= 6, (
        "geometric candidates include the axes without requiring random directions"
    )
    assert found.tried <= FINALISTS + 1 + len(AXES), (
        "geschnitten wird nur, was vorn liegt, und die Achsen"
    )


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

    Gemessen an der Startregel; mit den 60 Grad des Centauri wählen beide
    Suchen dieselbe liegende Lage (22 mm hoch, 84 statt 215 mm³ Stütze), und
    der Vergleich prüfte zwei Winkel statt eine Standfläche.
    """
    profile = at_the_start_rule(profile)
    body = bar()

    ohne = search(body, count=60)
    mit = search(body, count=60, profile=profile)

    assert mit.best.first_layer_area >= profile.smallest_first_layer, (
        "mit Profil steht die gewählte Lage"
    )
    assert mit.best.height <= ohne.best.height, "und sie liegt, statt zu kippeln"
    # **Ohne Profil gewinnt keine Kante mehr, und das ist gewollt.** Bis zum
    # 06.09.2026 verglich die Suche nur Stützvolumen; ohne Profil fehlte ihr
    # die Standflächenschranke, und sie wählte eine Lage mit 0,1 mm² erster
    # Schicht. Seit die Vorauswahl nach Standfläche gegen Überhang sortiert,
    # kommt eine solche Lage gar nicht mehr unter die Finalisten. Der Test
    # hielt die alte Schwäche als Kontrast fest; er hält jetzt fest, dass sie
    # weg ist.
    assert ohne.best.first_layer_area > profile.smallest_first_layer, (
        "auch ohne Profil steht die Lage — die Vorauswahl sortiert nach Standfläche"
    )


def test_search_passes_the_profile_footing_limit_to_the_final_choice(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Echte Geometriekandidaten; nur ihre teuren Schnittkennzahlen sind kontrolliert.

    Die Lage mit dem geringsten Stützbedarf steht unter der Profilgrenze. Erreicht diese
    Grenze die abschließende Wahl nicht, gewinnen beide Suchen dieselbe Lage.
    """
    from app.core.slice import orientation

    body = MeshData.of(trimesh.creation.box(extents=(10.0, 20.0, 30.0)))
    baseline = (0.0, 0.0, -1.0)
    standing = (1.0, 0.0, 0.0)
    floor = profile.smallest_first_layer
    measured = []

    def controlled_judge(
        _mesh: MeshData,
        direction: tuple[float, float, float],
        _height: float,
        _footing: float | None = None,
        *,
        overhang_angle: float | None = None,
        line_width: float | None = None,
    ) -> orientation.Candidate:
        measured.append(direction)
        if direction == baseline:
            return orientation.Candidate(direction, 1.0, floor / 2.0, 30.0)
        if direction == standing:
            return orientation.Candidate(direction, 2.0, floor * 2.0, 10.0)
        return orientation.Candidate(direction, 10.0, floor * 3.0, 20.0)

    monkeypatch.setattr(orientation, "judge", controlled_judge)

    without_profile = search(body, count=6)
    with_profile = search(body, count=6, profile=profile)

    assert baseline in measured and standing in measured
    assert without_profile.best.direction == baseline
    assert with_profile.best.direction == standing
    assert without_profile.best.first_layer_area < floor
    assert with_profile.best.first_layer_area >= floor
    assert without_profile.mesh.bounds.size[2] == pytest.approx(30.0)
    assert with_profile.mesh.bounds.size[2] == pytest.approx(10.0)


def test_the_floor_only_ranks_and_never_refuses(profile: Profile) -> None:
    """Ein Körper, dessen **jede** Lage unter der Grenze bleibt, wird nicht
    abgelehnt — dann tragen alle Kandidaten dieselbe Antwort, und es bleibt
    beim alten Vergleich. Gesagt wird es trotzdem.
    """
    tiny = place_on_bed(MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=2.0)))

    found = search(tiny, count=24, profile=profile)

    assert found.mesh is not None, "eine Antwort kommt in jedem Fall"
    assert found.best.first_layer_area < profile.smallest_first_layer
    assert "orient.no_footing" in {finding.code for finding in found.findings}


def test_a_real_footing_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst stünde der Satz unter jeder Suche."""
    found = search(corpus("plate_holes.stl"), count=24, profile=profile)

    assert "orient.no_footing" not in {finding.code for finding in found.findings}


def test_the_search_beats_the_heuristic_where_it_counts() -> None:
    """§40: die Suche über 200 Kandidaten findet weniger Stützen als die
    P2-Heuristik.
    """
    body = corpus("island_tower.stl")

    heuristic = orient_for_print(body).mesh
    searched = search(body, count=200).mesh

    heuristic_support = slice_body(heuristic, 1.0).support_volume
    searched_support = slice_body(searched, 1.0).support_volume

    assert searched_support <= heuristic_support, (
        f"the search found {searched_support:.0f} mm3, the heuristic {heuristic_support:.0f}"
    )


def test_the_result_says_what_it_saved() -> None:
    body = apply(corpus("plate_holes.stl"), rotation("y", 55.0))
    found = search(body, count=64)

    assert found.findings and found.findings[0].code == "orient.searched"
    assert found.findings[0].source == "internal", "§22.5: never mixed with G-code"
    assert found.findings[0].values["candidates"] >= found.tried, (
        "geprüft wird mehr, als geschnitten wird"
    )
    assert found.findings[0].values["sliced"] == found.tried
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
        search(corpus("cube_clean.stl"), count=500, cancelled=signal)


def test_the_search_reports_progress() -> None:
    seen: list[float] = []
    search(
        MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 10.0))),
        count=12,
        progress=lambda fraction, text: seen.append(fraction),
    )

    assert seen and seen[-1] == pytest.approx(1.0)


def test_the_face_shortlist_is_decided_by_real_support(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Flächenheuristik darf vorauswählen, aber nicht das Ergebnis spielen."""
    from app.core.slice import orientation

    directions = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)]
    coarse = [
        Orientation(direction, 100.0 - index, 0.0, 10.0)
        for index, direction in enumerate(directions)
    ]
    support = {directions[0]: 1000.0, directions[1]: 10.0, directions[2]: 0.0}
    seen: list[tuple[float, float, float]] = []
    monkeypatch.setattr(orientation, "ranked_orientations", lambda *_args, **_kwargs: coarse)

    def record(
        _mesh: MeshData,
        direction: tuple[float, float, float],
        _height: float,
        _footing: float | None = None,
        *,
        overhang_angle: float | None = None,
        line_width: float | None = None,
    ) -> orientation.Candidate:
        seen.append(direction)
        return orientation.Candidate(direction, support[direction], 100.0, 10.0)

    monkeypatch.setattr(orientation, "judge", record)

    chosen = best_face_candidate(MeshData.of(trimesh.creation.box()), count=2, profile=profile)

    assert seen == directions[:2], "nur die feste Vorauswahl wird geschnitten"
    assert chosen.direction == directions[1], "danach entscheidet das echte Stützvolumen"


def test_a_bounded_shortlist_keeps_its_last_place_for_a_pose_that_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drei fast gleiche Kantenlagen vorn, die stehenden weit hinten.

    So sah die Vorauswahl an einer Auto-Split-Hälfte mit Stift bei 60 Grad
    Überhanggrenze aus: Richtungen unter einem Grad auseinander, keine mit
    Auflage, liegende Lagen, die rollen, und die Lage auf dem Stift auf Rang 62.
    Stehen zwei, bekommt den Platz die mit dem kleineren geschätzten Stützraum,
    nicht die der Heuristik: Am Balken reihte sie das ferne Ende (254 883 mm³
    geschätzt) knapp vor die Schnittfläche (6 419 mm³).
    """
    from app.core.geom import orient

    edge = [(0.850, -0.526, 0.003), (0.850, -0.526, -0.011), (0.851, -0.526, 0.019)]
    ranked = [
        *(
            Orientation(direction, 0.0, 5.8, 158.7 + index, 138.0)
            for index, direction in enumerate(edge)
        ),
        Orientation((0.0, 0.0, 1.0), 0.0, 500.0, 160.0, 500.0),
        Orientation((0.0, 1.0, 0.0), 47.2, 4965.2, 160.0, 40_000.0),
        Orientation((1.0, 0.0, 0.0), 72.4, 4929.0, 172.0, 254_883.0),
        Orientation((0.0, 0.0, -1.0), 80.0, 6000.0, 172.0, 6_419.0),
    ]
    asked: list[tuple[float, float, float]] = []

    def wide(entry: Orientation) -> bool:
        """Steht auf dem Stift und auf der Schnittfläche; liegend rollt sie."""
        asked.append(entry.direction)
        return entry.direction in {(1.0, 0.0, 0.0), (0.0, 0.0, -1.0)}

    monkeypatch.setattr(orient, "candidates", lambda _mesh: [entry.direction for entry in ranked])
    monkeypatch.setattr(orient, "evaluate_directions", lambda *_args, **_kwargs: ranked)
    body = MeshData.of(trimesh.creation.box())

    assert [entry.direction for entry in ranked_orientations(body, limit=3)] == edge
    kept = ranked_orientations(body, limit=3, standing=wide)
    assert [entry.direction for entry in kept] == [*edge[:2], (0.0, 0.0, -1.0)], (
        "der letzte Platz geht an die stehende Lage mit dem kleinsten Stützraum"
    )
    expected_checks = {*edge, (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)}
    assert set(asked) == expected_checks, "gefragt wird bis die günstigste stehende Lage feststeht"
    assert len(asked) == len(expected_checks), "jede Lage wird höchstens einmal geprüft"
    assert ranked_orientations(body, standing=wide) == ranked_orientations(body), (
        "ohne Grenze der Zahl bleibt die Rangliste, wie sie ist"
    )
    assert ranked_orientations(body, limit=2, standing=lambda _entry: True) == ranked[:2]


def _half_with_pin() -> MeshData:
    """Eine Auto-Split-Hälfte im Kleinen: halbes gestrecktes Ellipsoid, ein
    Zapfen mitten auf der Schnittfläche.

    Die einzige Lage, die steht, ist die auf dem Zapfen; die Schnittfläche
    hängt dann über. Mit 60 Grad Überhanggrenze wird sie, leicht gekippt,
    druckbar, und die Heuristik zieht jede Kippung auf eine Kante vor.
    """
    import math

    ellipsoid = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    ellipsoid.apply_scale((3.0, 1.0, 1.0))
    half = ellipsoid.slice_plane((5.0, 0.0, 0.0), (-1.0, 0.0, 0.0), cap=True)
    pin = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=32)
    pin.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))
    pin.apply_translation((7.0, 0.0, 0.0))
    return MeshData.of(trimesh.boolean.union([half, pin], engine="manifold"))


@pytest.mark.parametrize("overhang_limit", [45.0, 60.0])
def test_auto_splits_shortlist_finds_the_pose_on_the_pin(
    profile: Profile, overhang_limit: float
) -> None:
    """Bei 45 Grad stand die Lage auf dem Zapfen in der Vorauswahl, bei 60
    fiel sie heraus, und Auto Split bewertete die Naht mit „unbekannt“."""
    import dataclasses

    from app.core.geom.autosplit import SUPPORT_ORIENTATION_CANDIDATES
    from app.core.slice.orientation import stands

    limited = dataclasses.replace(
        profile, printer=dataclasses.replace(profile.printer, overhang_limit=overhang_limit)
    )
    body = _half_with_pin()
    heuristic = ranked_orientations(
        body,
        limit=SUPPORT_ORIENTATION_CANDIDATES,
        printer=limited.printer,
        overhang_limit=overhang_limit,
    )
    if overhang_limit == 60.0:
        footing = limited.printer.layer_height / 2.0
        judged = [
            judge(
                body,
                entry.direction,
                1.0,
                footing,
                overhang_angle=overhang_limit,
                line_width=limited.printer.extrusion_width,
            )
            for entry in heuristic
        ]
        assert not any(stands(pose, limited.smallest_first_layer) for pose in judged), (
            "Voraussetzung: vorn steht bei 60 Grad keine Lage"
        )

    chosen = best_face_candidate(body, count=SUPPORT_ORIENTATION_CANDIDATES, profile=limited)

    assert stands(chosen, limited.smallest_first_layer)
    assert chosen.direction == (1.0, 0.0, 0.0)


def test_the_face_shortlist_can_be_cancelled(profile: Profile) -> None:
    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        best_face_candidate(corpus("cube_clean.stl"), count=3, profile=profile, cancelled=signal)


def test_the_face_shortlist_stops_before_the_real_slice(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.slice import orientation

    signal = CancelSignal()
    coarse = [Orientation((0.0, 0.0, -1.0), 1.0, 1.0, 1.0)]

    def rank_and_cancel(*_args: object, **_kwargs: object) -> list[Orientation]:
        signal.cancel()
        return coarse

    monkeypatch.setattr(orientation, "ranked_orientations", rank_and_cancel)

    with pytest.raises(OperationCancelled):
        best_face_candidate(corpus("cube_clean.stl"), count=1, profile=profile, cancelled=signal)


def test_an_already_cancelled_shortlist_does_not_collect_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.geom import orient

    signal = CancelSignal()
    signal.cancel()
    monkeypatch.setattr(
        orient,
        "candidates",
        lambda _mesh: pytest.fail("nach dem Abbruch wurden noch Kandidaten gesammelt"),
    )

    with pytest.raises(OperationCancelled):
        ranked_orientations(corpus("cube_clean.stl"), cancelled=signal)


def test_the_face_shortlist_stops_after_a_real_slice(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.slice import orientation

    signal = CancelSignal()
    directions = [(0.0, 0.0, -1.0)]
    coarse = [
        Orientation(direction, 2.0 - index, 1.0, 1.0) for index, direction in enumerate(directions)
    ]
    seen: list[tuple[float, float, float]] = []
    monkeypatch.setattr(orientation, "ranked_orientations", lambda *_args, **_kwargs: coarse)

    def judge_and_cancel(
        _mesh: MeshData,
        direction: tuple[float, float, float],
        _height: float,
        _footing: float | None = None,
        *,
        overhang_angle: float | None = None,
        line_width: float | None = None,
    ) -> orientation.Candidate:
        seen.append(direction)
        signal.cancel()
        return orientation.Candidate(direction, 0.0, 10.0, 1.0)

    monkeypatch.setattr(orientation, "judge", judge_and_cancel)

    with pytest.raises(OperationCancelled):
        best_face_candidate(corpus("cube_clean.stl"), count=1, profile=profile, cancelled=signal)
    assert seen == directions[:1]


def test_the_full_search_stops_after_the_baseline_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.slice import orientation

    signal = CancelSignal()
    seen: list[tuple[float, float, float]] = []

    def judge_and_cancel(
        _mesh: MeshData,
        direction: tuple[float, float, float],
        _height: float,
        _footing: float | None = None,
        *,
        overhang_angle: float | None = None,
        line_width: float | None = None,
    ) -> orientation.Candidate:
        seen.append(direction)
        signal.cancel()
        return orientation.Candidate(direction, 0.0, 10.0, 1.0)

    monkeypatch.setattr(orientation, "judge", judge_and_cancel)

    with pytest.raises(OperationCancelled):
        search(corpus("cube_clean.stl"), count=1, cancelled=signal)
    assert seen == [(0.0, 0.0, -1.0)]


# --- Der Sieger hängt am Körper, nicht an der Reihenfolge -----------------------


def test_the_winner_does_not_depend_on_the_order_of_the_field() -> None:
    """Der paarweise Vergleich war nicht transitiv (§22.3).

    Die Fünf-Prozent-Toleranz ist der Grund: Zwischen A und B liegen vier
    Prozent, zwischen B und C fünf, zwischen A und C neun. A schlägt C,
    C schlägt B, B schlägt A — und je nachdem, in welcher Reihenfolge die
    Abtastung die drei liefert, gewinnt ein anderer. Damit hing die empfohlene
    Lage an der Abtastung statt am Teil.
    """
    from itertools import permutations

    from app.core.slice.orientation import Candidate, best_of

    a = Candidate((0.0, 0.0, -1.0), 100.0, 10.0, 5.0)
    b = Candidate((1.0, 0.0, 0.0), 104.0, 30.0, 5.0)
    c = Candidate((0.0, 1.0, 0.0), 109.0, 50.0, 5.0)

    gewinner = {best_of(list(feld)).direction for feld in permutations((a, b, c))}

    assert gewinner == {b.direction}, "das kleinste Stützvolumen, darin die größte Fläche"


def test_a_pose_that_cannot_stand_is_still_ruled_out_first(profile: Profile) -> None:
    """Und die Reihenfolge der Kriterien bleibt: Stand vor Stützvolumen."""
    from app.core.slice.orientation import Candidate, best_of

    kippelig = Candidate((0.0, 0.0, -1.0), 1.0, 0.1, 5.0)
    stehend = Candidate((1.0, 0.0, 0.0), 500.0, 2000.0, 5.0)

    assert best_of([kippelig, stehend], profile.smallest_first_layer) is stehend
    assert best_of([stehend, kippelig], profile.smallest_first_layer) is stehend
    assert best_of([kippelig, stehend]) is kippelig, "ohne Grenze zählt nur das Stützvolumen"


def test_a_ball_never_stands_no_matter_how_coarse_the_search_is(profile: Profile) -> None:
    """Die Aufstandsfläche hing an der Suchauflösung (§22.3).

    Eine Kugel mit R = 20 steht bei 1,0 mm Suchschichthöhe auf 54 mm², bei
    0,2 mm auf 4,6 — und die Grenze des Druckers liegt mit 17,6 mm² dazwischen.
    Dieselbe Kugel bekam damit einmal ``orient.no_footing`` und einmal nicht,
    je nachdem, wie grob gesucht wurde.
    """
    ball = place_on_bed(MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0)))

    found = search(ball, count=24, profile=profile)

    assert found.best.first_layer_area < profile.smallest_first_layer
    assert "orient.no_footing" in {finding.code for finding in found.findings}


@pytest.mark.parametrize("organic", [False, True])
def test_the_same_body_gets_the_same_pose_twice(organic: bool, profile: Profile) -> None:
    """Gleiche Eingaben, gleiche Kandidaten, gleiche Lage — die Abnahme von RM-139.

    Die Kandidaten kommen aus der konvexen Hülle über sortierte Punkte, die
    Abtastung mit Zufallsrichtungen steht nicht mehr im Weg, und der Sieger
    hängt nicht an der Reihenfolge des Feldes. Jedes davon hat seinen Test;
    hier steht der Satz, den alle drei zusammen versprechen: Zwei Läufe über
    denselben Körper geben dieselbe Richtung, dieselbe Matrix und dieselben
    Zahlen — an einer Platte mit Bohrungen wie an einem organischen Körper
    (Regel 9 greift nicht, weil es keinen Zufall gibt; deshalb auch kein
    ``seed``).
    """
    import numpy as np

    if organic:
        raw = trimesh.creation.icosphere(subdivisions=1, radius=12)
        raw.apply_scale((1.0, 0.7, 1.5))
        mesh = MeshData.of(raw)
    else:
        mesh = corpus("plate_holes.stl")

    first = search(mesh, profile=profile, count=80)
    second = search(mesh, profile=profile, count=80)

    assert first.best.direction == second.best.direction
    assert first.best.support_volume == second.best.support_volume
    assert first.tried == second.tried
    assert np.array_equal(first.transform, second.transform)
    assert np.array_equal(first.mesh.raw.vertices, second.mesh.raw.vertices)


# --- der Stand wird am Original gemessen, nicht am Ersatznetz (§22.2) ---------------


def _flared_sleeve() -> MeshData:
    """Eine Hülse, Wand 2 mm, unten mit 63° nach außen aufgeweitet — die
    Bauart des Gitterbechers vom 20.09.2026 ohne sein Gitter, nur steiler
    als die Überhanggrenze. Mit der weiten Öffnung nach unten trägt sie sich
    selbst; mit der engen nach unten hängt die Aufweitung oben über."""
    profile = [(30.0, 0.0), (32.0, 0.0), (22.0, 5.0), (22.0, 30.0), (20.0, 30.0), (20.0, 5.0)]
    return place_on_bed(MeshData.of(trimesh.creation.revolve(profile, sections=96)))


def _with_a_rough_wide_rim(mesh: MeshData) -> MeshData:
    """Dasselbe Netz, nur der weite Rand um drei Zehntel verzittert — was
    eine Ausdünnung aus einem schmalen flachen Rand macht."""
    import numpy as np

    body = mesh.raw.copy()
    vertices = np.asarray(body.vertices, dtype=float).copy()
    # Nur der weite Rand hat Punkte jenseits von r = 28 — in jeder Lage.
    rim = np.hypot(vertices[:, 0], vertices[:, 1]) > 28.0
    vertices[rim, 2] += 0.3 * np.sin(np.arange(int(rim.sum())) * 1.7)
    body.vertices = vertices
    return MeshData.of(body)


def test_the_footing_is_measured_on_the_original(profile: Profile) -> None:
    """Der Gitterbecher: 94 990 Dreiecke, ein Rand 2 mm breit. Auf 20 000
    Dreiecke ausgedünnt stand er mit dem Rand nach unten auf 5 mm², am
    Original auf 594 — und die Suche verwarf die Lage, die ohne Stützen
    druckt, weil sie am Ersatznetz nicht stehen konnte."""
    sleeve = _flared_sleeve()
    rough = _with_a_rough_wide_rim(sleeve)
    footing = profile.printer.layer_height / 2.0

    alone = judge(rough, (0.0, 0.0, -1.0), 1.0, footing)
    with_original = judge(rough, (0.0, 0.0, -1.0), 1.0, footing, footing_mesh=sleeve)

    assert alone.first_layer_area < profile.smallest_first_layer, (
        "am verzitterten Rand steht die Hülse nicht"
    )
    assert with_original.first_layer_area > 300.0, "am Original steht sie auf dem ganzen Ring"
    assert with_original.stable


def test_the_search_stands_a_sleeve_on_its_wide_rim_despite_the_proxy(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dieselbe Falle eine Stufe früher: Die Vorauswahl bewertete jede Lage
    am Ersatznetz, und ein Rand ohne Standfläche kam nie unter die
    Finalisten. Achsen und tragende Flächen werden deshalb am Original
    bewertet, der Rest bleibt am Ersatznetz."""
    from app.core.slice import orientation

    # Enge Öffnung unten: die Aufweitung hängt oben über. Das Ersatznetz
    # steht im selben Rahmen wie der Körper, den die Suche bekommt.
    upside_down = place_on_bed(apply(_flared_sleeve(), rotation("x", 180.0)))
    rough = _with_a_rough_wide_rim(upside_down)
    monkeypatch.setattr(orientation, "search_proxy", lambda _mesh: rough)

    found = search(upside_down, count=24, profile=profile)

    assert found.best.direction == (0.0, 0.0, 1.0), "gedreht: der weite Rand kommt nach unten"
    assert found.best.first_layer_area > 300.0
    assert found.best.support_volume < found.baseline.support_volume  # type: ignore[union-attr]


def _umbrella() -> MeshData:
    """Das Schirmdach des Getränkehalters (RM-190), aus den Maßen seines Skripts.

    Roberts eigener Entwurf (``F:\\3D Dateien\\3D Drucker\\02_Getraenkehalter``,
    ``Getraenkehalter_mit_Schirm.py``): ein flaches Kegeldach mit Rand, Nabe,
    Gleitbohrung, einer Aussparung hinten und acht Lüftungslöchern — hier mit
    denselben Maßen neu gebaut, nicht aus der Datei gelesen.
    """
    import numpy as np

    from app.core.geom import lathe
    from app.core.geom.boolean import boolean

    radius, wall, skirt, apex, hub = 101.0, 2.4, 92.0, 130.0, 8.0
    outline = [
        (radius, 0.0),
        (radius, skirt),
        (hub, apex),
        (hub, apex - 3.0),
        (radius - wall, skirt - 1.0),
        (radius - wall, 0.0),
        (radius, 0.0),
    ]

    def standing(body: trimesh.Trimesh, x: float, y: float, bottom: float, top: float):
        body.vertices = np.asarray(body.vertices) + np.array([x, y, (bottom + top) / 2.0])
        return MeshData.of(body)

    canopy = MeshData.of(lathe.revolve(outline, sections=96))
    sleeve = standing(lathe.cylinder(8.0, 48.0, sections=96), 0.0, 0.0, apex - 48.0, apex)
    canopy = boolean("union", [canopy, sleeve]).mesh
    notch = trimesh.creation.box(extents=(60.0, 67.0, 45.0))
    notch.apply_translation((0.0, -81.5, 17.5))
    cuts = [
        standing(lathe.cylinder(6.15, 50.0, sections=96), 0.0, 0.0, apex - 49.0, apex + 1.0),
        MeshData.of(notch),
    ]
    for step in range(8):
        angle = step * 45.0
        from app.core.units import exact_cos_degrees, exact_sin_degrees

        cuts.append(
            standing(
                lathe.cylinder(1.5, 40.0, sections=96),
                40.0 * exact_cos_degrees(angle),
                40.0 * exact_sin_degrees(angle),
                95.0,
                135.0,
            )
        )
    return boolean("difference", [canopy, *cuts]).mesh


def test_the_umbrella_is_not_left_upside_down() -> None:
    """RM-190: *Druckoptimal ausrichten* ließ den Schirm kopfüber liegen.

    Gemessen am 23.09.2026 an Roberts Getränkehalter: Kopfüber braucht das
    Dach 459 cm³ Stützraum, um 22 Grad gekippt 164 cm³ bei elfmal so viel
    Standfläche — aber die Suche schnitt nur ihre acht Finalisten, und die
    wählt die Vorauswahl nach der **Fläche** der Überhänge. Das flache Dach
    hängt gekippt über mehr Fläche, nur tiefer; die gute Lage stand in der
    Vorauswahl auf Rang 123 bis 138 von 204. Dieselbe Lücke an Mast und
    Halter desselben Entwurfs.

    Verglichen wird mit der Lage, die die Suche bis dahin wählte, gemessen mit
    demselben Schnitt — keine Zahl aus dem Prüfling.
    """
    from app.core.knowledge import profiles
    from app.core.slice.orientation import SEARCH_LAYER_HEIGHT, stands

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    body = _umbrella()
    footing = profile.printer.layer_height / 2.0
    upside_down = judge(
        body,
        (0.0, 0.0, 1.0),
        SEARCH_LAYER_HEIGHT,
        footing,
        overhang_angle=profile.overhang_limit_degrees,
    )

    found = search(body, count=200, profile=profile)

    assert stands(found.best, profile.smallest_first_layer)
    assert found.best.support_volume < 0.5 * upside_down.support_volume, (
        f"{found.best.direction}: {found.best.support_volume:.0f} mm³ "
        f"gegen {upside_down.support_volume:.0f} mm³ kopfüber"
    )


def _standing_shaft() -> MeshData:
    """Ein Schaft wie im Minigolf-Satz, 19,2 x 19,2 x 200 mm, stehend. So braucht
    er nach der Regel der Druckvorschläge keine Stütze."""
    return place_on_bed(MeshData.of(trimesh.creation.box(extents=(19.2, 19.2, 200.0))))


def _judged_like_the_minigolf_shafts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der grobe Schnitt urteilt wie an Roberts Schäften (28.09.2026): stehend
    0,51 cm³ Stützraum auf 368 mm², liegend 0,26 cm³ auf 3 840 mm² — liegend
    gewinnt nach Stützraum und Standfläche. Wie der Körper im Druckraster
    urteilt, bleibt dem echten Netz (:func:`orientation.stays`)."""
    from app.core.slice import orientation

    def judged(
        _mesh: MeshData,
        direction: tuple[float, float, float],
        _height: float,
        _footing: float | None = None,
        **_kwargs: Any,
    ) -> orientation.Candidate:
        standing = direction == (0.0, 0.0, -1.0)
        area = 368.0 if standing else 3840.0
        return orientation.Candidate(
            direction,
            510.0 if standing else 260.0,
            area,
            200.0 if standing else 19.2,
            footing=area,
        )

    monkeypatch.setattr(orientation, "judge", judged)


def test_a_shaft_that_stands_without_support_keeps_standing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Roberts Minigolf-Satz (28.09.2026): Die Schäfte kamen stehend und wurden
    stehend gedruckt. Die Suche legte sie hin, weil liegend weniger Stützraum
    blieb — der liegende Gewinner brauchte aber selbst Stütze, und die
    stehende Lage nach der Regel der Druckvorschläge keine."""
    from app.core.knowledge import profiles

    _judged_like_the_minigolf_shafts(monkeypatch)

    found = search(_standing_shaft(), profile=profiles.make_profile("centauri-carbon-2", "pla"))

    assert found.best.direction == (0.0, 0.0, -1.0)
    # Und der Prüfbericht sagt, warum sich nichts gedreht hat — „gesucht“
    # allein ließ den Kunden vor einem unveränderten Teil stehen (N5). Die
    # groben Stützzahlen der Suche stehen nicht daneben: Sie widersprächen
    # dem Satz, denn geurteilt hat der Schnitt im Druckraster.
    (said,) = found.findings
    assert said.code == "orient.kept"
    assert str(said.message) == "Die Lage bleibt: Das Teil steht und braucht keine Stütze."
    assert "support" not in said.values and "saved" not in said.values


def test_a_part_that_needs_support_standing_is_still_turned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenprobe zum Schaft: Dasselbe grobe Urteil, aber stehend braucht
    der Körper Stütze — ein T auf seinem Stiel, der Kragarm 35 mm frei. Dann
    gewinnt die Suche wie bisher."""
    from app.core.knowledge import profiles

    stem = trimesh.creation.box(extents=(10.0, 10.0, 40.0))
    stem.apply_translation((0.0, 0.0, 20.0))
    arm = trimesh.creation.box(extents=(80.0, 10.0, 5.0))
    arm.apply_translation((0.0, 0.0, 42.5))
    tee = place_on_bed(MeshData.of(trimesh.boolean.union([stem, arm])))
    _judged_like_the_minigolf_shafts(monkeypatch)

    found = search(tee, profile=profiles.make_profile("centauri-carbon-2", "pla"))

    assert found.best.direction != (0.0, 0.0, -1.0)


def test_a_plate_on_its_edge_is_laid_flat_although_it_stands() -> None:
    """Die Gegenseite der Schäfte (Durchsicht 0.5.1): Eine Platte auf ihrer
    Kante steht und braucht keine Stütze — flach liegend aber genauso wenig,
    und dort steht sie zehnmal breiter und ist in einem Zehntel der Schichten
    gedruckt. Die gelieferte Lage bleibt nur gegen einen Gewinner, der selbst
    Stütze braucht."""
    from app.core.knowledge import profiles

    on_edge = place_on_bed(apply(corpus("plate_holes.stl"), rotation("y", 90.0)))
    assert on_edge.bounds.size[2] > 70.0, "die Vorbedingung: sie steht auf der Kante"

    found = search(on_edge, profile=profiles.make_profile("centauri-carbon-2", "pla"))

    assert found.mesh.bounds.size[2] < 10.0, "flach"


def _spy_on_stays(monkeypatch: pytest.MonkeyPatch) -> list[MeshData]:
    """Die Netze, an denen :func:`orientation.stays` urteilt."""
    from app.core.slice import orientation

    seen: list[MeshData] = []
    real = orientation.stays

    def spy(mesh: MeshData, *args: Any, **kwargs: Any) -> bool:
        seen.append(mesh)
        return real(mesh, *args, **kwargs)

    monkeypatch.setattr(orientation, "stays", spy)
    return seen


def test_the_kept_pose_is_judged_on_the_original_mesh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Durchsicht 0.5.1, N2: ``stays`` urteilte am Ersatznetz der Suche. Die
    Ausdünnung erfindet Inseln und Überhänge und verschluckt andere — an vier
    von dreißig Körpern des Minigolf-Satzes urteilte es anders als das
    Original und der Prüfbericht. Der Schaft hier ist fein genug, dass die
    Suche ihn ausdünnt; sonst wäre Ersatznetz gleich Original und der Test
    prüfte nichts."""
    from app.core.knowledge import profiles
    from app.core.slice.orientation import search_proxy

    fine = _standing_shaft().raw
    while len(fine.faces) <= 40_000:
        fine = fine.subdivide()
    body = MeshData.of(fine)
    assert search_proxy(body) is not body, "die Suche dünnt aus"
    _judged_like_the_minigolf_shafts(monkeypatch)
    seen = _spy_on_stays(monkeypatch)

    found = search(body, profile=profiles.make_profile("centauri-carbon-2", "pla"))

    assert seen and all(mesh is body for mesh in seen)
    assert found.best.direction == (0.0, 0.0, -1.0)


def test_a_pose_the_coarse_slice_settles_costs_no_fine_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N2, die Zeit: Die Frage nach dem Stützbedarf im Druckraster kostet einen
    vollen Schnitt. Sie kam vor der Suche an jeden stehenden Körper, auch an
    den, den der grobe Schnitt schon behielt — den Rundschaft v17 18,3 statt
    1,3 s. Ein Klotz auf seiner größten Fläche braucht sie nicht."""
    from app.core.knowledge import profiles

    block = place_on_bed(MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 10.0))))
    seen = _spy_on_stays(monkeypatch)

    found = search(block, profile=profiles.make_profile("centauri-carbon-2", "pla"))

    assert found.best.direction == (0.0, 0.0, -1.0)
    assert seen == []


def test_a_winner_a_hair_beside_the_delivered_pose_costs_no_fine_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N2, ``obj_30`` des Minigolf-Satzes: Seine Bodenfläche zeigt 0,0114 Grad
    neben der Ausgangslage und gewann über den Gleichstand im Stützraum mit
    4,5 mm² mehr Standfläche. Eine andere Lage ist das nicht — die Kippung
    hebt keine Stelle um eine Schicht —, der Vergleich der Richtungen nannte
    sie aber eine und fragte :func:`orientation.stays`: 2,2 s für ein Nein.
    Wie ``obj_30`` braucht das T hier stehend Stütze."""
    from app.core.knowledge import profiles
    from app.core.slice import orientation

    stem = trimesh.creation.box(extents=(10.0, 10.0, 40.0))
    stem.apply_translation((0.0, 0.0, 20.0))
    arm = trimesh.creation.box(extents=(80.0, 10.0, 5.0))
    arm.apply_translation((0.0, 0.0, 42.5))
    tee = MeshData.of(trimesh.boolean.union([stem, arm]))
    body = place_on_bed(apply(tee, rotation("x", 0.01)))
    delivered = (0.0, 0.0, -1.0)

    def judged(
        _mesh: MeshData,
        direction: tuple[float, float, float],
        _height: float,
        _footing: float | None = None,
        **_kwargs: Any,
    ) -> orientation.Candidate:
        upright = direction[2] < -0.999
        support = (510.0 if direction == delivered else 500.0) if upright else 5000.0
        area = (368.0 if direction == delivered else 370.0) if upright else 3840.0
        return orientation.Candidate(direction, support, area, 200.0, footing=area)

    monkeypatch.setattr(orientation, "judge", judged)
    seen = _spy_on_stays(monkeypatch)

    found = search(body, profile=profiles.make_profile("centauri-carbon-2", "pla"))

    assert found.best.direction != delivered, "die Vorbedingung: die gekippte Bodenfläche gewinnt"
    assert found.mesh.bounds.size[2] > 40.0, "und das T steht"
    assert seen == []


def _pool_holder() -> MeshData:
    """Der Getränkehalter für den Poolrand (RM-190), aus den Maßen seines Skripts.

    Roberts eigener Entwurf (``Getraenkehalter_Pool_ThreeSixty.py``): ein
    ovaler Sattel über das Rahmenrohr, ein Arm, ein Tablett mit Steg und zwei
    Becher mit Abfluss — hier mit denselben Maßen neu gebaut.
    """
    import numpy as np
    import shapely.geometry as sg
    from shapely.affinity import scale

    from app.core.geom.boolean import boolean
    from app.core.units import exact_cos_degrees, exact_sin_degrees

    rail_w, rail_h, clear, wall, width, opening = 47.0, 32.0, 1.4, 5.0, 45.0, 150.0
    flat, corner, pocket_wall, depth, bottom, drain, gap = 84.0, 20.0, 3.5, 80.0, 4.0, 42.0, 12.0
    rx_in, ry_in = (rail_w + clear) / 2.0, (rail_h + clear) / 2.0
    rx_out, ry_out = rx_in + wall, ry_in + wall
    r_out = max(rx_out, ry_out)
    out_flat = flat + 2.0 * pocket_wall
    out_half = out_flat / 2.0
    cup_dx = out_half + gap / 2.0
    cup_y = r_out + 8.0 + out_half

    def block(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> MeshData:
        body = trimesh.creation.box(extents=(x1 - x0, y1 - y0, z1 - z0))
        body.apply_translation(((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0))
        return MeshData.of(body)

    def rounded(size: float, radius: float, z0: float, z1: float, x: float, y: float) -> MeshData:
        h = size / 2.0 - radius
        square = sg.Polygon([(-h, -h), (h, -h), (h, h), (-h, h)]).buffer(
            radius, quad_segs=24, join_style="round"
        )
        body = trimesh.creation.extrude_polygon(square, height=z1 - z0)
        body.apply_translation((x, y, z0))
        return MeshData.of(body)

    def drum(radius: float, z0: float, z1: float, x: float, y: float) -> MeshData:
        from app.core.geom import lathe

        body = lathe.cylinder(radius, z1 - z0, sections=64)
        body.vertices = np.asarray(body.vertices) + np.array([x, y, (z0 + z1) / 2.0])
        return MeshData.of(body)

    circle = sg.Point(0.0, 0.0).buffer(1.0, quad_segs=96)
    ring = scale(circle, rx_out, ry_out).difference(scale(circle, rx_in, ry_in))
    reach = r_out + 3.0
    steps = [270.0 - opening / 2.0 + opening * index / 59.0 for index in range(60)]
    wedge = [(0.0, 0.0)] + [
        (exact_cos_degrees(angle) * reach, exact_sin_degrees(angle) * reach) for angle in steps
    ]
    hook = trimesh.creation.extrude_polygon(ring.difference(sg.Polygon(wedge)), height=width)
    hook.apply_transform(
        np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=float)
    )
    hook.apply_translation((-width / 2.0, 0.0, 0.0))

    parts = [
        MeshData.of(hook),
        block(-width / 2.0, width / 2.0, 18.0, 42.0, -6.0, 24.0),
        block(-(cup_dx + out_half), cup_dx + out_half, 30.0, 72.0, -6.0, 0.0),
        block(-cup_dx, cup_dx, 60.0, 108.0, -6.0, 0.0),
    ]
    cavities = []
    for x in (-cup_dx, cup_dx):
        parts.append(rounded(out_flat, corner + pocket_wall, -depth, 0.0, x, cup_y))
        cavities.append(rounded(flat, corner, -(depth - bottom), 2.0, x, cup_y))
        cavities.append(drum(drain / 2.0, -depth - 2.0, -depth + bottom + 1.0, x, cup_y))
    solid = boolean("union", parts).mesh
    return boolean("difference", [solid, *cavities]).mesh


def _line_holding_footing(body: MeshData, direction, profile: Profile) -> float:
    """Wie viel der Aufstandsfläche eine Linie tragen kann — sie, um eine halbe
    Linienbreite nach innen versetzt."""
    from app.core.geom.orient import rotation_to_down
    from app.core.slice.orientation import _contact

    contact, _centre = _contact(
        body, rotation_to_down(direction), profile.printer.layer_height / 2.0
    )
    if contact is None:
        return 0.0
    return float(contact.buffer(-profile.printer.extrusion_width / 2.0, join_style="mitre").area)


def test_a_knife_edge_is_no_footing() -> None:
    """Ein Quader auf seiner Kante: 20 mm² Aufstand, aber kein Strich darauf druckbar.

    Die Kante berührt das Bett in halber Schichthöhe als Streifen von
    2 x 0,1 mm Breite — mehr Fläche als die kleinste Aufstandsfläche
    (``smallest_first_layer``), und doch schmaler als eine Linie. Stehen heißt:
    Die erste Schicht lässt sich drucken.
    """
    import math

    from app.core.knowledge import profiles
    from app.core.slice.orientation import SEARCH_LAYER_HEIGHT, stands

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    beam = MeshData.of(trimesh.creation.box(extents=(100.0, 40.0, 40.0)))
    edge = (0.0, -math.sqrt(0.5), -math.sqrt(0.5))

    on_edge = judge(
        beam,
        edge,
        SEARCH_LAYER_HEIGHT,
        profile.printer.layer_height / 2.0,
        line_width=profile.printer.extrusion_width,
    )
    lying = judge(
        beam,
        (0.0, 0.0, -1.0),
        SEARCH_LAYER_HEIGHT,
        profile.printer.layer_height / 2.0,
        line_width=profile.printer.extrusion_width,
    )

    assert on_edge.first_layer_area >= profile.smallest_first_layer, "sonst prüft das nichts"
    assert not stands(on_edge, profile.smallest_first_layer)
    assert stands(lying, profile.smallest_first_layer)


@pytest.mark.parametrize("workers", [None, 3], ids=["host", "three-workers"])
def test_the_pool_holder_does_not_stand_on_a_knife_edge(
    workers: int | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-190, die Kehrseite: Wer mehr Lagen schneidet, findet auch Kanten.

    Mit der Schätzung des Stützraums in der Vorauswahl fand die Suche am
    Getränkehalter eine um 48 Grad gekippte Lage mit 93 statt 326 cm³
    Stützraum — auf drei Kanten, zusammen 36 mm², und keine davon so breit
    wie eine Linie (am 23.09.2026 gemessen: um eine halbe Linienbreite nach
    innen versetzt bleibt nichts). Die kleinste Aufstandsfläche galt der
    Summe, nicht dem, was sich drucken lässt.
    """
    from app.core.knowledge import profiles
    from app.core.slice import analysis

    if workers is not None:
        # Drei Arbeiter halten größere Säulengruppen als der Entwicklungs-PC:
        # So wird der räumliche Index auch dort unter Parallelität benutzt.
        monkeypatch.setattr(analysis, "_workers", lambda limit: min(limit, workers))

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    holder = _pool_holder()

    found = search(holder, count=200, profile=profile)

    assert _line_holding_footing(holder, found.best.direction, profile) >= (
        profile.smallest_first_layer
    ), f"{found.best.direction} steht auf {found.best.first_layer_area:.1f} mm²"
