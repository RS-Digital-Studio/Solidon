"""Einzelmerkmale ausdrücklich als Muster zusammenfassen (RM-504).

Unter den Erkennungsschwellen (``patterns.MIN_CELLS`` und Geschwister) ist ein
importiertes Feld ohne Erzeugerwissen mehrdeutig: acht Waben, drei Rillen, ein
Ornament aus ungleichen Zellen. Die Schwellen bleiben, denn eine Absenkung
nähme Funktionsbohrungen, Magnettaschen und Schrift mit. Stattdessen fasst
*Als Muster zusammenfassen* gewählte Einzelmerkmale zu einem Muster — als
Schritt im Verlauf, mit stabiler Kennung, Undo, Projektdatei und Rückweg für
alte Zellbezüge.

Die Sollwerte kommen aus der Konstruktion: die Wabenplatte des Halters
(Schlüsselweite 9 mm, Teilung 10,4 mm, 20 mm dick) aus
``tests/test_pattern_features.honeycomb_plate``, hier mit acht Zellen — eine
unter ``MIN_CELLS``.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pytest
import trimesh
from shapely.geometry import Polygon

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive import patterns
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import (
    Feature,
    FeatureId,
    Finding,
    OpContext,
    PrinterProfile,
    Profile,
    Scene,
    SceneObject,
)
from tests.test_pattern_features import (
    HOLDER_PITCH,
    HOLDER_THICKNESS,
    HOLDER_WIDTH,
    bored_plate,
    hexagon,
    honeycomb_plate,
)

PROFILE = Profile(
    printer=PrinterProfile(id="test", title="Test", build_volume=(220.0, 220.0, 250.0)),
    material=None,
)

#: Acht Waben in zwei Reihen zu vier — eine weniger, als die Erkennung braucht.
COLUMNS, ROWS = 4, 2


def run(op: str, entry: SceneObject, **params: object) -> tuple[SceneObject, list[Finding]]:
    """Eine Operation fahren — ohne Neuerkennung danach, die übernimmt die Auswertung."""
    load_operations()
    spec = REGISTRY.get(op)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}, parameters={}),
            inputs=[entry],
            params=spec.params(**params),
            profile=PROFILE,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, options: options[0],
            cancelled=NeverCancelled(),
        )
    )
    return result.outputs[0], list(result.findings)


def kinds(features: Mapping[FeatureId, Feature]) -> dict[str, int]:
    counted: dict[str, int] = {}
    for feature in features.values():
        counted[feature.kind] = counted.get(feature.kind, 0) + 1
    return counted


def cell_walls(features: Mapping[FeatureId, Feature]) -> list[FeatureId]:
    """Die Wände der Waben: senkrechte Flächen, viel kleiner als die Plattenseiten."""
    return sorted(
        name
        for name, feature in features.items()
        if feature.kind == "face"
        and abs(float(feature.params["normal"][2])) < 0.5
        and float(feature.params["area"]) < HOLDER_WIDTH * HOLDER_THICKNESS
    )


def small_honeycomb() -> tuple[SceneObject, int]:
    mesh, count = honeycomb_plate(columns=COLUMNS, rows=ROWS)
    assert count == patterns.MIN_CELLS - 1
    return SceneObject(id="obj_1", name="Wabenplatte", mesh=mesh, features=detect(mesh)), count


def only_grouped(features: Mapping[FeatureId, Feature]) -> Feature:
    found = [feature for feature in features.values() if feature.kind == "pattern"]
    assert len(found) == 1, [feature.id for feature in found]
    assert found[0].params.get("grouped") is True
    return found[0]


# --- Was zusammengefasst wird ------------------------------------------------------


def test_eight_chosen_honeycomb_cells_become_one_pattern_with_the_holders_numbers() -> None:
    """Acht Waben sind ohne Wahl acht mal sechs Flächen — gewählt ein Wabenmuster."""
    entry, count = small_honeycomb()
    assert "pattern" not in kinds(entry.features), "ohne Wahl bleibt die Erkennung unverändert"
    walls = cell_walls(entry.features)
    assert len(walls) == count * 6
    out, findings = run("group_pattern", entry, at_features=tuple(walls))
    pattern = only_grouped(out.features)
    params = pattern.params
    assert params["style"] == "hexagon" and params["lattice"] == "hexagonal"
    assert params["count"] == count and params["partial"] == 0
    assert math.isclose(params["pitch"], HOLDER_PITCH, abs_tol=1e-3)
    assert math.isclose(params["cell_width"], HOLDER_WIDTH, abs_tol=1e-3)
    assert math.isclose(params["cell_depth"], HOLDER_THICKNESS, abs_tol=1e-3)
    assert params["through"] is True and params["mode"] == "engraved"
    assert pattern.provenance == "generated" and pattern.recognised
    assert kinds(out.features) == {"face": 6, "pattern": 1}
    assert out.mesh is entry.mesh, "die Geometrie bleibt"
    assert set(walls) <= set(out.reserved_feature_ids), "die alten Namen bleiben vergeben"
    (grouped,) = [finding for finding in findings if finding.code == "group_pattern.grouped"]
    assert set(grouped.feature_ids) == set(walls)
    assert grouped.severity == "info"


def test_one_wall_of_each_cell_brings_the_whole_cell() -> None:
    """Gewählt wird die Zelle über ein Merkmal; ihre übrigen Wände gehören von selbst dazu."""
    entry, count = small_honeycomb()
    walls = cell_walls(entry.features)
    by_cell: dict[tuple[float, float], FeatureId] = {}
    for name in walls:
        centre = entry.features[name].params["centre"]
        # Die Mitte der Wand liegt höchstens eine halbe Schlüsselweite neben
        # der Zellmitte; das Raster der Teilung trennt die Zellen.
        key = (
            round(float(centre[0]) / (HOLDER_PITCH / 2.0)),
            round(float(centre[1]) / (HOLDER_PITCH / 2.0)),
        )
        by_cell.setdefault(key, name)
    out, _findings = run("group_pattern", entry, at_features=tuple(sorted(by_cell.values())))
    assert only_grouped(out.features).params["count"] == count
    assert kinds(out.features) == {"face": 6, "pattern": 1}


def test_unequal_cells_of_an_ornament_become_a_foreign_pattern() -> None:
    """Ungleiche Zellen ohne Gitter sind ein fremdes Feld: entfernbar, nicht neu zu zeichnen."""
    body = trimesh.creation.box(extents=(60.0, 30.0, 6.0))
    square = trimesh.creation.box(extents=(6.0, 6.0, 2.0))
    square.apply_translation((-18.0, 0.0, 3.0))
    triangle = trimesh.creation.extrude_polygon(
        Polygon([(0.0, -3.0), (4.0, 3.0), (-4.0, 3.0)]), height=2.0
    )
    triangle.apply_translation((18.0, 0.0, 2.0))
    six = hexagon(5.0, 2.0, (0.0, 0.0, 2.0))
    tools = MeshData.of(trimesh.util.concatenate([square, triangle, six.raw]))
    mesh = boolean(
        "difference", [MeshData.of(body), tools], quality="fine", cancelled=NeverCancelled()
    ).mesh
    found = detect(mesh)
    assert "pattern" not in kinds(found)
    pockets = sorted(
        name
        for name, feature in found.items()
        if feature.kind == "face" and float(feature.params["area"]) < 60.0
    )
    entry = SceneObject(id="obj_1", name="Ornament", mesh=mesh, features=found)
    out, _findings = run("group_pattern", entry, at_features=tuple(pockets))
    pattern = only_grouped(out.features)
    assert pattern.params["style"] == "other"
    assert pattern.params["lattice"] == "none"
    assert pattern.params["count"] == 3
    assert pattern.params["mode"] == "engraved"
    assert math.isclose(pattern.params["cell_depth"], 1.0, abs_tol=1e-6)
    assert kinds(out.features) == {"face": 6, "pattern": 1}


# --- Was nicht zusammengefasst wird -------------------------------------------------


def refusal(entry: SceneObject, chosen: Sequence[FeatureId]) -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        run("group_pattern", entry, at_features=tuple(chosen))
    error = caught.value
    assert error.suggestions, "jede Absage nennt einen Weg (Regel 17)"
    assert error.detail, "und einen Satz"
    return error


def test_a_single_cell_is_not_a_pattern() -> None:
    """Eine gewählte Wand bringt ihre Zelle mit — und eine Zelle hat keine Teilung."""
    entry, _count = small_honeycomb()
    assert refusal(entry, cell_walls(entry.features)[:1]).constraint == "group_too_few"


def test_chosen_core_holes_stay_bores() -> None:
    """Tiefe runde Löcher bleiben Bohrungen — auch gewählt; ihre Handlungen bleiben.

    Kernlöcher Ø 2 mm, 5 mm tief: tiefer als ``ROUND_DEPTH`` mal so breit,
    also keine Noppe (``patterns._measure_cell``).
    """
    mesh = bored_plate(3, 1, 2.0, 5.0)
    found = detect(mesh)
    holes = sorted(name for name, feature in found.items() if feature.kind == "hole")
    assert len(holes) == 3
    entry = SceneObject(id="obj_1", name="Lochleiste", mesh=mesh, features=found)
    error = refusal(entry, holes)
    assert error.constraint == "group_bores"
    assert set(error.values["features"]) == set(holes)


def test_shallow_pockets_become_a_pattern_only_when_chosen() -> None:
    """Zwölf flache Taschen bleiben ohne Wahl zwölf Bohrungen, gewählt ein Muster.

    Ø 4 mm, 2 mm tief, im Raster von 6 mm: flach genug für eine Noppe, aber zu
    wenige und im falschen Gitter für die Erkennung. Wer sie ausdrücklich
    zusammenfasst, bekommt ein fremdes Feld — ``other``, denn
    ``apply_texture`` setzt Noppen nur im Wabengitter.
    """
    mesh = bored_plate(4, 3, 4.0, 2.0)
    found = detect(mesh)
    holes = sorted(name for name, feature in found.items() if feature.kind == "hole")
    assert len(holes) == 12 and "pattern" not in kinds(found)
    entry = SceneObject(id="obj_1", name="Taschen", mesh=mesh, features=found)
    out, _findings = run("group_pattern", entry, at_features=tuple(holes))
    pattern = only_grouped(out.features)
    assert pattern.params["count"] == 12
    # Welche Gitterrichtung die Nachbarsuche bei gleich weiten Nachbarn nimmt,
    # sagt ``_grid_of``; ein Noppengitter von ``apply_texture`` ist es nicht.
    assert pattern.params["lattice"] != "hexagonal" and pattern.params["style"] == "other"
    # Die Taschen liegen im Raster von 6 mm (``bored_plate``).
    assert math.isclose(pattern.params["pitch"], 6.0, abs_tol=1e-3)
    assert "hole" not in kinds(out.features)


def test_the_carrier_itself_is_not_a_cell() -> None:
    entry, _count = small_honeycomb()
    top = max(
        (name for name, feature in entry.features.items() if feature.kind == "face"),
        key=lambda name: float(entry.features[name].params["centre"][2]),
    )
    walls = cell_walls(entry.features)
    assert refusal(entry, [top, *walls]).constraint == "group_not_a_cell"


def test_cells_on_two_faces_are_two_patterns() -> None:
    body = trimesh.creation.box(extents=(60.0, 30.0, 10.0))
    pockets = [hexagon(5.0, 2.0, (x, 0.0, z)).raw for x in (-15.0, 0.0, 15.0) for z in (4.0, -6.0)]
    mesh = boolean(
        "difference",
        [MeshData.of(body), MeshData.of(trimesh.util.concatenate(pockets))],
        quality="fine",
        cancelled=NeverCancelled(),
    ).mesh
    found = detect(mesh)
    walls = sorted(
        name
        for name, feature in found.items()
        if feature.kind == "face" and float(feature.params["area"]) < 30.0
    )
    entry = SceneObject(id="obj_1", name="Zwei Seiten", mesh=mesh, features=found)
    assert refusal(entry, walls).constraint == "group_two_carriers"


def test_detection_without_a_choice_is_unchanged() -> None:
    """Die geteilte Zellenlesung gibt der Erkennung dieselben Muster wie zuvor."""
    mesh, count = honeycomb_plate()
    found = detect(mesh)
    (pattern,) = [feature for feature in found.values() if feature.kind == "pattern"]
    assert pattern.params["count"] == count
    assert pattern.params.get("grouped") is None and pattern.provenance == "detected"


# --- Entfernen --------------------------------------------------------------------


def test_removing_a_grouped_pattern_fills_every_cell() -> None:
    entry, count = small_honeycomb()
    out, _findings = run("group_pattern", entry, at_features=tuple(cell_walls(entry.features)))
    pattern = only_grouped(out.features)
    removed, findings = run("remove_feature", out, at_feature=pattern.id)
    cell_area = 3.0 * math.sqrt(3.0) / 2.0 * (HOLDER_WIDTH / math.sqrt(3.0)) ** 2
    expected = entry.mesh.volume + count * cell_area * HOLDER_THICKNESS
    assert math.isclose(removed.mesh.volume, expected, rel_tol=1e-6)
    assert any(finding.code == "remove_feature.gone" for finding in findings)
    assert kinds(detect(as_mesh_data(removed.mesh))) == {"face": 6}


# --- Durch den Verlauf --------------------------------------------------------------


def test_a_grouped_pattern_lives_through_steps_save_cache_and_undo(
    tmp_path: Path,
) -> None:
    """Der Schritt trägt die Kennung, Folgeschritte das Muster, alte Zellbezüge halten an."""
    from app.core.geom.mesh import MeshCodec
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.hashing import feature_digest
    from app.core.scene.project import ProjectSources, load, new_project, save
    from app.core.types import Source

    load_operations()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    mesh, count = honeycomb_plate(columns=COLUMNS, rows=ROWS)
    project = new_project()
    project.sources["src_1"] = mesh.raw.export(file_type="stl")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/waben.stl", sha256=""
    )
    history = History(project.document)
    history.apply(
        "Wabenplatte laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    directory = tmp_path / "cache"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))

    def inspect(item=project, result_cache=cache):  # type: ignore[no-untyped-def]
        result = evaluate(
            item.document,
            profile,
            sources=ProjectSources(item),
            cache=result_cache,
            ask=lambda _question, choices: choices[0],
        )
        assert result.complete, result.scene.report.findings
        return result.scene.objects["obj_1"], result

    loaded, _result = inspect()
    walls = cell_walls(loaded.features)
    assert len(walls) == count * 6
    history.apply(
        "Als Muster zusammenfassen",
        [OperationDraft(op="group_pattern", inputs=("obj_1",), params={"at_features": walls})],
    )
    step = project.document.ops[-1].id
    grouped, result = inspect()
    name = f"{patterns.GROUPED_PREFIX}_{step}"
    assert set(grouped.features) == {name, *(n for n in loaded.features if n not in walls)}
    pattern = grouped.features[name]
    assert pattern.created_by == step and pattern.params["count"] == count
    assert set(walls) <= set(grouped.reserved_feature_ids)
    assert not any(
        finding.code == "perceive.orphaned" for finding in result.scene.report.findings
    ), "der angesagte Weggang der Zellen ist kein Verlust"

    # Ein Folgeschritt bewegt den Körper; das Muster reist unter demselben Namen.
    history.apply(
        "Verschieben",
        [
            OperationDraft(
                op="translate_object", inputs=("obj_1",), params={"dx": 5.0, "dy": 0.0, "dz": 0.0}
            )
        ],
    )
    moved, _result = inspect()
    assert moved.features[name].params["count"] == count
    shift = np.asarray(moved.features[name].params["centre"]) - np.asarray(pattern.params["centre"])
    assert np.allclose(shift, (5.0, 0.0, 0.0), atol=1e-6)
    assert not set(walls) & set(moved.features)

    # Speichern, leerer und Plattencache geben dieselbe Auswahl.
    reopened = load(save(project, tmp_path / "waben.p3d"))
    assert inspect(reopened, ResultCache())[0].features == moved.features
    disk = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    from_disk = inspect(reopened, disk)[0]
    assert {n: feature_digest(f, n) for n, f in from_disk.features.items()} == {
        n: feature_digest(f, n) for n, f in moved.features.items()
    }

    # Undo nimmt erst die Bewegung, dann die Zusammenfassung zurück.
    history.undo()
    assert inspect()[0].features == grouped.features
    history.undo()
    assert set(walls) <= set(inspect()[0].features)
    history.redo()
    assert inspect()[0].features == grouped.features
    history.redo()

    # Ein alter Bezug auf eine einzelne Wand färbt nicht das ganze Muster.
    History(reopened.document).apply(
        "Alte Wabenwand färben",
        [
            OperationDraft(
                op="paint_slot",
                inputs=("obj_1",),
                params={"at_feature": walls[0], "slot": 1, "colour": "#CC2233"},
            )
        ],
    )
    blocked = evaluate(
        reopened.document, profile, sources=ProjectSources(reopened), cache=ResultCache()
    )
    assert not blocked.complete
    assert blocked.stopped_at == reopened.document.ops[-1].id
    assert any(
        finding.severity == "error" and finding.suggestions
        for finding in blocked.scene.report.findings
    )


def test_the_grouping_carries_to_both_halves_of_a_split() -> None:
    """Eine Ebene durch das Feld gibt beiden Hälften ihre Zellen mit, wie einer Textur."""
    from app.core.geom import prepare_ops
    from app.core.geom.section import SectionPlane

    entry, _count = small_honeycomb()
    out, _findings = run("group_pattern", entry, at_features=tuple(cell_walls(entry.features)))
    pattern = only_grouped(out.features)
    plane = SectionPlane(normal=(1.0, 0.0, 0.0), position=0.0)
    first, second = prepare_ops._features_after_split(dict(out.features), plane, out.mesh)
    assert pattern.id in first and pattern.id in second
    assert dataclasses.asdict(first[pattern.id]) == dataclasses.asdict(pattern)


def test_changing_a_grouped_pattern_keeps_its_name_and_its_cells() -> None:
    """*Merkmal ändern* zeichnet die Zellen neu; das Muster bindet sich an die neuen.

    Acht Waben liegen unter der Mindestzahl: Ohne Bindung an die neu
    gezeichneten Zellen fände die Erkennung danach nur Einzelflächen, und der
    Name des Schritts verlöre seine Zellen. Sollwert aus der Eingabe: blind,
    10 mm tief, in der 20 mm dicken Platte.
    """
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    mesh, count = honeycomb_plate(columns=COLUMNS, rows=ROWS)
    project = new_project()
    project.sources["src_1"] = mesh.raw.export(file_type="stl")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/waben.stl", sha256=""
    )
    history = History(project.document)
    history.apply(
        "Wabenplatte laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )

    def inspect() -> SceneObject:
        result = evaluate(
            project.document,
            profile,
            sources=ProjectSources(project),
            ask=lambda _question, choices: choices[0],
        )
        assert result.complete, result.scene.report.findings
        return result.scene.objects["obj_1"]

    walls = cell_walls(inspect().features)
    history.apply(
        "Als Muster zusammenfassen",
        [OperationDraft(op="group_pattern", inputs=("obj_1",), params={"at_features": walls})],
    )
    name = f"{patterns.GROUPED_PREFIX}_{project.document.ops[-1].id}"
    history.apply(
        "Tiefe ändern",
        [
            OperationDraft(
                op="resize_feature",
                inputs=("obj_1",),
                params={"at_feature": name, "cell_depth": HOLDER_THICKNESS / 2.0},
            )
        ],
    )
    changed = inspect()
    pattern = changed.features[name]
    assert pattern.params["grouped"] is True and pattern.params["count"] == count
    assert pattern.params["through"] is False
    assert math.isclose(pattern.params["cell_depth"], HOLDER_THICKNESS / 2.0, abs_tol=1e-3)
    assert pattern.face_indices
    assert kinds(changed.features) == {"face": 6, "pattern": 1}
    # Die Umrisse bleiben; jede Zelle ist halb gefüllt.
    cell_area = 3.0 * math.sqrt(3.0) / 2.0 * (HOLDER_WIDTH / math.sqrt(3.0)) ** 2
    expected = mesh.volume + count * cell_area * HOLDER_THICKNESS / 2.0
    assert math.isclose(as_mesh_data(changed.mesh).volume, expected, rel_tol=1e-6)
