"""Der gemeinsame druckgleich-Vergleich (Bauplan §11.2, ``tests/print_equal.py``).

Jedes Kriterium hat einen Fall, der es rot macht, und einen, der es grün
lässt: Ein Vergleich, der nie Nein sagt, belegt keine Beschleunigung. Die
Grenze selbst ist ``units.PRINT_LIMIT`` (2,5 µm, ein Vierzigstel der kleinsten
Düse); die Sollwerte hier stehen als Formel daneben.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core import examples
from app.core.geom.mesh import MeshData, read_mesh
from app.core.knowledge import profiles
from app.core.scene import evaluate
from app.core.scene.project import ProjectSources
from app.core.scene.project import load as load_project
from app.core.types import (
    Feature,
    Finding,
    MaterialSlot,
    Report,
    Scene,
    SceneObject,
    SolverInfo,
)
from app.core.units import PRINT_LIMIT, SMALLEST_NOZZLE
from tests import print_equal
from tests.print_equal import ResultShot, compare, health_of, shot

MESHES = Path(__file__).parent / "data" / "meshes"


def _cube() -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(20.0, 20.0, 20.0))


def _result(body: trimesh.Trimesh, **extra: Any) -> SimpleNamespace:
    """Ein Ergebnis mit einem Würfel, einem Merkmal, einem Befund und einer Rückfallstufe."""
    slots = extra.pop("slot_indices", ())
    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "diameter": 5.0,
            "centre": (0.0, 0.0, 10.0),
            "axis": (0.0, 0.0, 1.0),
            "angle": 90.0,
            "through": True,
        },
        face_indices=extra.pop("face_indices", (0, 1)),
        measure_sources={"diameter": "fit"},
    )
    obj = SceneObject(
        id="obj_1",
        name="Würfel",
        mesh=MeshData.of(body, slots=tuple(slots)),
        features={"hole_1": feature},
        material_slots=[
            MaterialSlot(0, "PLA", (1.0, 0.0, 0.0)),
            MaterialSlot(1, "PETG", (0.0, 0.0, 1.0)),
        ],
    )
    finding = Finding(
        code="scene.thin_walls",
        severity="warning",
        message="Die Wand ist 0,40 mm dünn.",
        object_id="obj_1",
        values={"thickness": 0.4},
        location=(1.0, 2.0, 3.0),
    )
    return SimpleNamespace(
        scene=Scene(objects={"obj_1": obj}, report=Report(findings=(finding,))),
        solvers={2: SolverInfo(strategy="direct", attempted=("direct",))},
        answers={},
        matches={},
        completed=(1, 2),
        stopped_at=None,
    )


@pytest.fixture(scope="module")
def cube_shot() -> ResultShot:
    return shot(_result(_cube()))


def test_the_limit_is_a_fortieth_of_the_smallest_nozzle() -> None:
    """Die Grenze kommt aus dem Kern, nicht aus diesem Modul (§11.2)."""
    assert print_equal.print_limit() == PRINT_LIMIT
    assert math.isclose(PRINT_LIMIT, SMALLEST_NOZZLE / 40)


def test_the_same_result_is_print_equal_without_any_deviation(cube_shot: ResultShot) -> None:
    """Der Kontrollfall: zweimal dasselbe ist druckgleich, Abweichung genau null."""
    verdict = compare(cube_shot, shot(_result(_cube())))

    assert verdict.print_equal, verdict.report()
    assert verdict.largest == 0.0
    assert not verdict.unchecked, verdict.report()
    assert {export.format for export in cube_shot.bodies[0].exports} == {"stl", "3mf", "obj"}


def test_a_saved_shot_reads_back_as_the_same(cube_shot: ResultShot, tmp_path: Path) -> None:
    """Ein Stand wird in einem Baum aufgenommen und in einem anderen verglichen."""
    restored = print_equal.load(print_equal.save(cube_shot, tmp_path / "vorher"))

    verdict = compare(cube_shot, restored)

    assert verdict.print_equal, verdict.report()
    assert verdict.largest == 0.0
    assert restored.bodies[0].features[0].params == cube_shot.bodies[0].features[0].params
    assert restored.solvers == cube_shot.solvers
    assert restored.bodies[0].health == cube_shot.bodies[0].health
    # Gegenprobe: Auch das gelesene Abbild sieht einen Unterschied.
    moved = dataclasses.replace(restored.bodies[0], name="anders")
    assert not compare(dataclasses.replace(restored, bodies=(moved,)), cube_shot).print_equal


@pytest.mark.parametrize(("shift", "equal"), [(0.4, True), (0.9, True), (1.6, False)])
def test_a_corner_moved_by_more_than_the_limit_is_not_print_equal(
    cube_shot: ResultShot, shift: float, equal: bool
) -> None:
    """Maß und Lage: der Würfel um ``shift`` mal die Grenze angehoben.

    Der Körper selbst weicht genau so weit ab — unter der Grenze als Schranke
    über die Ecken, darüber gemessen; die STL-Rundreise rundet die Ecken bei
    10 mm zusätzlich auf das float32-Raster (Abstand 2⁻²⁰ mm).
    """
    body = _cube()
    vertices = np.array(body.vertices)
    vertices[:, 2] += shift * PRINT_LIMIT
    moved = trimesh.Trimesh(vertices=vertices, faces=body.faces, process=False)

    verdict = compare(cube_shot, shot(_result(moved)))

    assert verdict.print_equal is equal, verdict.report()
    own = {where: gap for gap, where in verdict.deviations}["obj_1 (Fläche)"]
    assert math.isclose(own, shift * PRINT_LIMIT, rel_tol=1e-9)
    assert abs(verdict.largest - shift * PRINT_LIMIT) <= 2.0**-20
    assert not verdict.discrete and not verdict.worse


#: Die sechs Seiten eines Würfels als Vierecke, Ecke ``i`` bei ``(x, y, z)`` aus den Bits von ``i``.
_QUADS = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))


def _quad_cube(diagonal: int) -> trimesh.Trimesh:
    """Ein Würfel 20 mm, jede Seite über die erste (0) oder die zweite (1) Diagonale geteilt."""
    corners = np.array([[(i >> 2) & 1, (i >> 1) & 1, i & 1] for i in range(8)], dtype=float)
    faces = []
    for a, b, c, d in _QUADS:
        faces += [[a, b, c], [a, c, d]] if diagonal == 0 else [[a, b, d], [b, c, d]]
    body = trimesh.Trimesh(vertices=corners * 20.0 - 10.0, faces=faces, process=False)
    trimesh.repair.fix_normals(body)
    return body


def test_another_triangulation_of_the_same_surface_is_print_equal() -> None:
    """Dreiecksfolge und Diagonalen dürfen sich ändern; gemessen wird der Abstand der Flächen.

    Jede Seite über die andere Diagonale geteilt, die Dreiecke umgekehrt
    nummeriert, das Merkmal auf dieselbe Seite umgezählt (Dreiecke 0 und 1
    vorher, die letzten zwei nachher).
    """
    first = _quad_cube(0)
    second = _quad_cube(1)
    reordered = trimesh.Trimesh(
        vertices=second.vertices, faces=np.asarray(second.faces)[::-1], process=False
    )
    last = len(reordered.faces) - 1

    verdict = compare(shot(_result(first)), shot(_result(reordered, face_indices=(last, last - 1))))

    assert verdict.print_equal, verdict.report()
    assert verdict.largest < 1e-12
    # Gegenprobe: Dieselbe Umzählung ohne die Merkmalsdreiecke mitzunehmen trifft
    # eine andere Seite — deren Mitte liegt 20 mm daneben.
    elsewhere = compare(shot(_result(first)), shot(_result(reordered, face_indices=(0, 1))))
    assert not elsewhere.print_equal
    assert math.isclose(elsewhere.largest, 10.0 * math.sqrt(2.0), rel_tol=1e-9), elsewhere.report()


def test_corners_rounded_to_single_precision_stay_print_equal_on_a_corpus_mesh() -> None:
    """Die float32-Sonde als Test: Ecken einfach genau gerundet, um 192 mm vom Ursprung.

    Zwischen 128 und 256 mm ist der float32-Abstand 2⁻¹⁶ mm; gerundet wird
    höchstens um die Hälfte je Achse, also höchstens √3 · 2⁻¹⁷ mm je Ecke.
    """
    loaded = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl").raw
    vertices = np.asarray(loaded.vertices, dtype=np.float64)
    vertices += 192.0 - (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    assert vertices.min() >= 128.0 and vertices.max() < 256.0
    exact = trimesh.Trimesh(vertices=vertices, faces=loaded.faces, process=False)
    narrowed = trimesh.Trimesh(
        vertices=vertices.astype(np.float32).astype(np.float64),
        faces=loaded.faces,
        process=False,
    )
    before = shot(
        SimpleNamespace(
            scene=Scene(
                objects={"obj_1": SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(exact))}
            )
        ),
        exports=(),
    )
    after = shot(
        SimpleNamespace(
            scene=Scene(
                objects={
                    "obj_1": SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(narrowed))
                }
            )
        ),
        exports=(),
    )

    verdict = compare(before, after)

    assert verdict.print_equal, verdict.report()
    assert 0.0 < verdict.largest <= math.sqrt(3.0) * 2.0**-17


def _changed(base: ResultShot, change: str) -> ResultShot:
    """``base`` mit genau einer diskreten Änderung."""
    body = base.bodies[0]
    feature = body.features[0]
    finding = dict(base.findings[0])
    if change == "object order":
        twin = dataclasses.replace(body, id="obj_2")
        return dataclasses.replace(base, bodies=(twin, body))
    if change == "object name":
        return dataclasses.replace(base, bodies=(dataclasses.replace(body, name="Quader"),))
    if change == "plate":
        return dataclasses.replace(base, bodies=(dataclasses.replace(body, plate=1),))
    if change == "material slots":
        slots = body.material_slots[:1]
        return dataclasses.replace(base, bodies=(dataclasses.replace(body, material_slots=slots),))
    if change == "slot of a triangle":
        indices = np.zeros(len(body.faces), dtype=np.int64)
        indices[3] = 1
        return dataclasses.replace(base, bodies=(dataclasses.replace(body, slot_indices=indices),))
    if change in (
        "feature id",
        "feature kind",
        "feature triangles",
        "feature through",
        "feature gone",
    ):
        renamed = {
            "feature id": dataclasses.replace(feature, id="hole_2"),
            "feature kind": dataclasses.replace(feature, kind="pin"),
            "feature triangles": dataclasses.replace(
                feature, face_indices=np.array([0, 2], dtype=np.int64)
            ),
            "feature through": dataclasses.replace(
                feature, params={**feature.params, "through": False}
            ),
        }.get(change)
        features = () if renamed is None else (renamed,)
        return dataclasses.replace(base, bodies=(dataclasses.replace(body, features=features),))
    if change == "finding code":
        finding["code"] = "scene.thin_skins"
        return dataclasses.replace(base, findings=(finding,))
    if change == "finding severity":
        finding["severity"] = "error"
        return dataclasses.replace(base, findings=(finding,))
    if change == "finding gone":
        return dataclasses.replace(base, findings=())
    if change == "solver stage":
        return dataclasses.replace(base, solvers=((2, "welded", ("direct", "welded"), None),))
    if change == "answers":
        return dataclasses.replace(base, answers='{"3": {"unit": "inch"}}')
    if change == "question":
        return dataclasses.replace(base, questions=(("Welche Einheit?", ("mm", "inch")),))
    if change == "closed after weld":
        health = dataclasses.replace(body.health, closed_after_weld=False)
        return dataclasses.replace(base, bodies=(dataclasses.replace(body, health=health),))
    if change in ("export name", "export colours", "export unit", "export gone"):
        export = body.exports[1]
        part = export.parts[0]
        changed_export = {
            "export name": dataclasses.replace(
                export, parts=(dataclasses.replace(part, name="Körper 1"),)
            ),
            "export colours": dataclasses.replace(
                export, parts=(dataclasses.replace(part, colours=()),)
            ),
            "export unit": dataclasses.replace(export, unit="inch"),
        }.get(change)
        kept = (body.exports[0],) + (() if changed_export is None else (changed_export,))
        return dataclasses.replace(
            base, bodies=(dataclasses.replace(body, exports=kept + body.exports[2:]),)
        )
    raise AssertionError(change)


@pytest.mark.parametrize(
    "change",
    [
        "object order",
        "object name",
        "plate",
        "material slots",
        "slot of a triangle",
        "feature id",
        "feature kind",
        "feature triangles",
        "feature through",
        "feature gone",
        "finding code",
        "finding severity",
        "finding gone",
        "solver stage",
        "answers",
        "question",
        "closed after weld",
        "export name",
        "export colours",
        "export unit",
        "export gone",
    ],
)
def test_every_discrete_change_is_named(cube_shot: ResultShot, change: str) -> None:
    """Je diskretes Kriterium ein Fall, der es rot macht — und das Urteil nennt ihn."""
    assert cube_shot.bodies[0].exports[1].format == "3mf"

    verdict = compare(cube_shot, _changed(cube_shot, change))

    assert not verdict.print_equal
    assert verdict.discrete, verdict.report()


def test_a_number_in_a_question_may_move_in_its_last_digit(cube_shot: ResultShot) -> None:
    """Die letzte Anzeigestelle darf wandern (§11.2); der Wortlaut nicht."""
    before = dataclasses.replace(cube_shot, questions=(("Ist das Teil 177,80 mm groß?", ("ja",)),))
    after = dataclasses.replace(cube_shot, questions=(("Ist das Teil 177,81 mm groß?", ("ja",)),))
    other = dataclasses.replace(cube_shot, questions=(("Ist das Teil 177,80 in groß?", ("ja",)),))

    assert compare(before, after).print_equal
    assert not compare(before, other).print_equal


@pytest.mark.parametrize(
    ("key", "value", "gap"),
    [
        # Länge direkt.
        ("diameter", 5.0 + 0.001, 0.001),
        ("diameter", 5.0 + 0.005, 0.005),
        # Lage als Abstand zweier Punkte.
        ("centre", (0.0, 0.003, 10.004), 0.005),
        # Richtung über den Hebel der Diagonale (√3 · 20 mm).
        ("axis", (0.0, 1e-4, 1.0), 1e-4 * math.sqrt(3.0) * 20.0),
        # Grad, über denselben Hebel.
        ("angle", 90.0 + 1e-3, math.radians(1e-3) * math.sqrt(3.0) * 20.0),
    ],
)
def test_feature_numbers_count_as_the_shift_they_mean_in_print(
    cube_shot: ResultShot, key: str, value: Any, gap: float
) -> None:
    body = cube_shot.bodies[0]
    feature = body.features[0]
    params = {**feature.params, key: list(value) if isinstance(value, tuple) else value}
    changed = dataclasses.replace(
        cube_shot,
        bodies=(
            dataclasses.replace(body, features=(dataclasses.replace(feature, params=params),)),
        ),
    )

    verdict = compare(cube_shot, changed)

    assert math.isclose(verdict.largest, gap, rel_tol=1e-6), verdict.report()
    assert verdict.print_equal is (gap <= PRINT_LIMIT)
    assert not verdict.discrete


def test_a_finding_value_and_place_count_as_lengths(cube_shot: ResultShot) -> None:
    finding = dict(cube_shot.findings[0])
    finding["values"] = {"thickness": 0.4 + 0.001}
    finding["location"] = [1.0, 2.0, 3.0 + 0.004]

    verdict = compare(cube_shot, dataclasses.replace(cube_shot, findings=(finding,)))

    assert math.isclose(verdict.largest, 0.004, rel_tol=1e-9)
    assert not verdict.discrete and not verdict.print_equal


def test_an_area_and_a_volume_count_as_the_shift_over_their_rim() -> None:
    """Eine Fläche ändert sich bei einer Verschiebung d um höchstens Umfang · d."""
    verdict = print_equal.Verdict(PRINT_LIMIT)
    radius = 10.0
    area = math.pi * radius * radius
    grown = math.pi * (radius + 0.002) ** 2
    print_equal.compare_values("area", area, grown, lever=1.0, where="a", verdict=verdict)
    reach = 2 * math.pi * (radius + 0.002)
    assert math.isclose(verdict.largest, (grown - area) / reach, rel_tol=1e-9)
    assert math.isclose(verdict.largest, 0.002, rel_tol=1e-3)

    verdict = print_equal.Verdict(PRINT_LIMIT)
    volume = 4.0 / 3.0 * math.pi * radius**3
    swollen = 4.0 / 3.0 * math.pi * (radius + 0.002) ** 3
    print_equal.compare_values("volume", volume, swollen, lever=1.0, where="v", verdict=verdict)
    assert math.isclose(verdict.largest, 0.002, rel_tol=1e-3)


def test_a_mesh_with_a_hole_is_worse_and_no_longer_closed_in_the_slicer(
    cube_shot: ResultShot,
) -> None:
    body = _cube()
    opened = trimesh.Trimesh(vertices=body.vertices, faces=body.faces[1:], process=False)

    verdict = compare(cube_shot, shot(_result(opened, face_indices=(0,)), exports=()))

    assert any("open_edges 0 → 3" in entry for entry in verdict.worse), verdict.report()
    assert any("dicht nach dem Verschweißen True → False" in entry for entry in verdict.worse)


def test_a_degenerate_triangle_makes_the_mesh_worse(cube_shot: ResultShot) -> None:
    body = _cube()
    vertices = np.vstack([body.vertices, [[10.0, 10.0, 10.0]]])
    faces = np.vstack([body.faces, [[0, 0, len(vertices) - 1]]])
    flat = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    verdict = compare(cube_shot, shot(_result(flat), exports=()))

    assert any(entry.endswith("degenerate 0 → 1") for entry in verdict.worse), verdict.report()


def test_a_crossing_makes_the_mesh_worse() -> None:
    """Zwei Würfel, die sich durchdringen, gegen zwei, die nebeneinander stehen."""
    apart = trimesh.util.concatenate([_cube(), _cube().apply_translation((30.0, 0.0, 0.0))])
    inside = trimesh.util.concatenate([_cube(), _cube().apply_translation((10.0, 5.0, 5.0))])

    before = health_of(np.asarray(apart.vertices), np.asarray(apart.faces), weld=False)
    after = health_of(np.asarray(inside.vertices), np.asarray(inside.faces), weld=False)
    first = SimpleNamespace(
        scene=Scene(
            objects={"obj_1": SceneObject(id="obj_1", name="Paar", mesh=MeshData.of(apart))}
        )
    )
    second = SimpleNamespace(
        scene=Scene(
            objects={"obj_1": SceneObject(id="obj_1", name="Paar", mesh=MeshData.of(inside))}
        )
    )

    assert before.crossings == 0 and after.crossings is not None and after.crossings > 0
    verdict = compare(shot(first, exports=(), weld=False), shot(second, exports=(), weld=False))
    assert any("Selbstdurchdringung 0 →" in entry for entry in verdict.worse), verdict.report()


def test_a_triangle_soup_is_open_by_index_but_closed_after_the_weld() -> None:
    """Dicht heißt dicht im Slicer: Eine STL-Suppe hat lauter offene Kanten und ist doch dicht."""
    body = _cube()
    soup = trimesh.Trimesh(
        vertices=np.asarray(body.vertices)[np.asarray(body.faces).reshape(-1)],
        faces=np.arange(3 * len(body.faces)).reshape(-1, 3),
        process=False,
    )

    health = health_of(np.asarray(soup.vertices), np.asarray(soup.faces), crossings=False)

    assert health.open_edges == 36
    assert health.closed_after_weld is True


def test_unchecked_parts_are_named_not_passed(cube_shot: ResultShot) -> None:
    """Was nicht geprüft wurde, steht im Urteil — ein stilles Grün belegt nichts."""
    quick = shot(_result(_cube()), crossings=False, weld=False)

    verdict = compare(cube_shot, quick)

    assert verdict.print_equal
    assert len(verdict.unchecked) == 2


def test_a_round_trip_that_moves_the_body_counts_as_a_deviation(cube_shot: ResultShot) -> None:
    body = cube_shot.bodies[0]
    stl = body.exports[0]
    part = stl.parts[0]
    shifted = dataclasses.replace(part, vertices=part.vertices + np.array([0.0, 0.0, 0.01]))
    changed = dataclasses.replace(
        body, exports=(dataclasses.replace(stl, parts=(shifted,)), *body.exports[1:])
    )

    verdict = compare(cube_shot, dataclasses.replace(cube_shot, bodies=(changed,)))

    assert math.isclose(verdict.largest, 0.01, rel_tol=1e-6)
    assert verdict.where == "obj_1.stl[0]"


def test_an_example_project_is_print_equal_to_itself_with_slots_and_round_trip() -> None:
    """Am echten Weg: Beispielprojekt laden, auswerten, zweimal aufnehmen.

    Das zweifarbige Schild trägt zwei Slots und erkannte Merkmale; die
    Rundreise läuft durch STL, 3MF und OBJ. Zwei Auswertungen desselben
    Stands sind bitgleich (§15.1), also ist die Abweichung genau null.
    """
    project = load_project(examples.directory() / "schild-zweifarbig.p3d")
    profile = profiles.make_profile(
        project.document.printer or "centauri-carbon-2", project.document.material or "petg"
    )
    results = [
        evaluate(project.document, profile, sources=ProjectSources(project)) for _ in range(2)
    ]
    shots = [shot(result, crossings=False) for result in results]

    verdict = compare(*shots)

    assert verdict.print_equal, verdict.report()
    assert verdict.largest == 0.0
    assert any(len(set(body.slot_indices.tolist())) > 1 for body in shots[0].bodies)
    assert any(body.features for body in shots[0].bodies)
    assert all(body.health.closed_after_weld for body in shots[0].bodies)


def test_the_tool_compares_two_folders_and_fails_on_a_difference(
    cube_shot: ResultShot, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``tools/check_print_equal.py compare``: Exit 0 bei druckgleich, 1 bei einem Unterschied."""
    from tools import check_print_equal

    renamed = dataclasses.replace(
        cube_shot, bodies=(dataclasses.replace(cube_shot.bodies[0], name="Quader"),)
    )
    for folder, result in (("vorher", cube_shot), ("nachher", cube_shot), ("anders", renamed)):
        (tmp_path / folder).mkdir()
        print_equal.save(result, tmp_path / folder / "wuerfel")

    same = check_print_equal.main(["compare", str(tmp_path / "vorher"), str(tmp_path / "nachher")])
    other = check_print_equal.main(["compare", str(tmp_path / "vorher"), str(tmp_path / "anders")])

    assert (same, other) == (0, 1)
    assert "NICHT druckgleich" in capsys.readouterr().out
