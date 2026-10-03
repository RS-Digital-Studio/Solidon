"""Selbst aufgebrachte Texturen bleiben durch Verlauf und Projekt eine Auswahl."""

from __future__ import annotations

import json
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshCodec, as_mesh_data
from app.core.perceive.features import forget_cache
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import DiskCache, ResultCache
from app.core.scene.project import Project, ProjectSources, load, new_project, save
from app.core.types import Feature, OpId, Profile, SceneObject, Source
from tests.helpers import exact_kernel


def _plate() -> tuple[Project, History]:
    """Die Korpusplatte 80 × 50 × 8 besitzt vier unabhängige Bohrungen Ø 5,2."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = (Path(__file__).parent / "data/meshes/plate_holes.stl").read_bytes()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate.stl", sha256=""
    )
    history = History(project.document)
    history.apply(
        "Lochplatte laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    return project, history


def _texture(history: History, *, object_id: str = "obj_1", **overrides: Any) -> OpId:
    """Ein kleines mittiges Feld endet weit vor den vier Korpusbohrungen."""
    history.apply(
        "Textur aufbringen",
        [
            OperationDraft(
                op="apply_texture",
                inputs=(object_id,),
                params={
                    "pattern": "rib",
                    "width": 12.0,
                    "height": 10.0,
                    "pitch": 3.0,
                    "depth": 0.6,
                    "z": 4.0,
                    **overrides,
                },
                seed=17,
            )
        ],
    )
    return history.operations[-1].id


def _run(project: Project, profile: Profile, cache: ResultCache | None = None) -> SceneObject:
    result = evaluate(project.document, profile, sources=ProjectSources(project), cache=cache)
    assert result.complete, result
    assert len(result.scene.objects) == 1
    return next(iter(result.scene.objects.values()))


def _patterns(body: SceneObject, count: int) -> dict[str, Feature]:
    """Die Textur besitzt echte Dreiecke; ihre Kinder sind keine zweite Auswahl."""
    groups = {
        name: feature
        for name, feature in body.features.items()
        if feature.kind == "pattern" and feature.recognised
    }
    assert len(groups) == count, [(f.id, f.kind) for f in body.features.values()]
    mesh = as_mesh_data(body.mesh)
    for group in groups.values():
        assert group.provenance == "generated"
        assert group.created_by is not None
        assert group.face_indices
        assert min(group.face_indices) >= 0
        assert max(group.face_indices) < mesh.triangle_count
        selected = set(group.face_indices)
        for other in body.features.values():
            if other.recognised and other.id != group.id:
                assert not selected.intersection(other.face_indices), (
                    group.id,
                    other.id,
                    other.kind,
                )
    return groups


def _snapshot(groups: dict[str, Feature]) -> str:
    """Der fachliche Inhalt bleibt gleich, auch wenn JSON Tupel als Listen liest."""
    return json.dumps({name: asdict(feature) for name, feature in groups.items()}, sort_keys=True)


def _bores_and_faces_remain(body: SceneObject) -> None:
    """Eine Textur darf weder die vier Bohrungen noch die freie Unterseite schlucken."""
    holes = [f for f in body.features.values() if f.kind == "hole" and f.recognised]
    assert len(holes) == 4
    assert all(f.params["diameter"] == pytest.approx(5.2, abs=1e-4) for f in holes)
    assert any(
        f.kind == "face" and f.recognised and f.params["normal"][2] < -0.99
        for f in body.features.values()
    )


@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_a_texture_survives_edit_undo_redo_and_project_cache(
    mode: str, profile: Profile, tmp_path: Path
) -> None:
    """Bearbeiten trifft die ganze Textur; Änderung und Rückweg überleben eine Datei."""
    project, history = _plate()
    texture_id = _texture(history, mode=mode)
    directory = tmp_path / "cache"

    def fresh_cache() -> ResultCache:
        return ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))

    cache = fresh_cache()
    original = _run(project, profile, cache)
    original_groups = _patterns(original, 1)
    _bores_and_faces_remain(original)
    assert next(iter(original_groups.values())).created_by == texture_id
    warm = _run(project, profile, cache)
    assert _patterns(warm, 1) == original_groups
    assert cache.statistics.hits > 0

    history.undo()
    bare = _run(project, profile, cache)
    _patterns(bare, 0)
    _bores_and_faces_remain(bare)
    history.redo()
    assert _patterns(_run(project, profile, cache), 1) == original_groups

    step = history.operations[-1]
    history.change_params(step.id, {**step.params, "depth": 1.0})
    changed = _run(project, profile, cache)
    changed_groups = _patterns(changed, 1)
    assert changed_groups.keys() == original_groups.keys()
    if mode == "raised":
        assert changed.mesh.volume > original.mesh.volume
        assert changed.mesh.bounds.maximum[2] == pytest.approx(5.0)
    else:
        assert changed.mesh.volume < original.mesh.volume
        assert changed.mesh.bounds.maximum[2] == pytest.approx(4.0)
    _bores_and_faces_remain(changed)

    opened = load(save(project, tmp_path / "texture.solidon"))
    disk_cache = fresh_cache()
    reopened = _run(opened, profile, disk_cache)
    assert _snapshot(_patterns(reopened, 1)) == _snapshot(changed_groups)
    assert disk_cache.statistics.disk_hits > 0
    assert reopened.mesh.volume == pytest.approx(changed.mesh.volume)
    forget_cache()
    assert _snapshot(_patterns(_run(opened, profile, ResultCache()), 1)) == _snapshot(
        changed_groups
    )

    reopened_history = History(opened.document)
    reopened_history.undo()
    undone = _run(opened, profile, disk_cache)
    assert _snapshot(_patterns(undone, 1)) == _snapshot(original_groups)
    assert undone.mesh.volume == pytest.approx(original.mesh.volume)
    reopened_history.redo()
    assert _snapshot(_patterns(_run(opened, profile, disk_cache), 1)) == _snapshot(changed_groups)


@pytest.mark.parametrize("placement", ["neighbour", "touching", "overlap", "opposite"])
@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_two_same_style_textures_keep_separate_producers(
    placement: str, mode: str, profile: Profile
) -> None:
    """Gleiche Rippen sind zwei bearbeitbare Felder, auch am selben Körper."""
    project, history = _plate()
    distance = {"neighbour": 9.0, "touching": 6.0, "overlap": 3.0, "opposite": 0.0}[placement]
    first_id = _texture(history, x=-distance, mode=mode)
    first = _run(project, profile)
    first_group = next(iter(_patterns(first, 1).values()))
    other = {"z": -4.0, "nz": -1.0} if placement == "opposite" else {"x": distance}
    second_id = _texture(history, mode=mode, **other)
    body = _run(project, profile)
    groups = _patterns(body, 2)
    assert {f.created_by for f in groups.values()} == {first_id, second_id}
    assert groups[first_group.id].created_by == first_id
    _bores_and_faces_remain(body)

    second_step = history.operations[-1]
    history.change_params(second_id, {**second_step.params, "depth": 1.2})
    changed = _run(project, profile)
    changed_groups = _patterns(changed, 2)
    assert changed_groups.keys() == groups.keys()
    unchanged = changed_groups[first_group.id]
    assert unchanged.created_by == first_id
    before_points = body.mesh.raw.triangles[list(groups[first_group.id].face_indices)]
    after_points = changed.mesh.raw.triangles[list(unchanged.face_indices)]
    if placement != "overlap":
        assert np.min(after_points, axis=(0, 1)) == pytest.approx(
            np.min(before_points, axis=(0, 1))
        )
        assert np.max(after_points, axis=(0, 1)) == pytest.approx(
            np.max(before_points, axis=(0, 1))
        )


@pytest.mark.parametrize(
    ("operation", "params", "matrix"),
    [
        (
            "translate_object",
            {"dx": 7.0, "dy": -3.0, "dz": 5.0},
            [[1.0, 0.0, 0.0, 7.0], [0.0, 1.0, 0.0, -3.0], [0.0, 0.0, 1.0, 5.0]],
        ),
        (
            "rotate_object",
            {"axis": "x", "angle": 90.0, "about": "origin"},
            [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
        ),
        (
            "scale_object",
            {"factor": 2.0, "about": "origin"},
            [[2.0, 0.0, 0.0, 0.0], [0.0, 2.0, 0.0, 0.0], [0.0, 0.0, 2.0, 0.0]],
        ),
        (
            "mirror_object",
            {"axis": "z", "about": "origin"},
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0]],
        ),
        (
            "scale_object",
            {"fx": 2.0, "fy": 3.0, "fz": 4.0, "about": "origin"},
            [[2.0, 0.0, 0.0, 0.0], [0.0, 3.0, 0.0, 0.0], [0.0, 0.0, 4.0, 0.0]],
        ),
    ],
)
def test_transformations_keep_the_texture_on_its_triangles(
    operation: str, params: dict[str, Any], matrix: list[list[float]], profile: Profile
) -> None:
    """Verschieben, Kippen und Skalieren bewegen die vollständige belegte Textur."""
    project, history = _plate()
    texture_id = _texture(history)
    original = _run(project, profile)
    original_group = next(iter(_patterns(original, 1).values()))
    points = original.mesh.raw.triangles[list(original_group.face_indices)].reshape(-1, 3)
    transform = np.asarray(matrix)
    expected = points @ transform[:, :3].T + transform[:, 3]
    history.apply(
        "Körper bewegen",
        [
            OperationDraft(
                op=operation,
                inputs=("obj_1",),
                params={
                    **params,
                    **({} if operation == "mirror_object" else {"keep_on_bed": False}),
                },
            )
        ],
    )
    moved = _run(project, profile)
    moved_groups = _patterns(moved, 1)
    assert moved_groups.keys() == {original_group.id}
    actual_group = moved_groups[original_group.id]
    assert actual_group.created_by == texture_id
    expected_centre = (
        transform[:, :3] @ np.asarray(original_group.params["centre"]) + transform[:, 3]
    )
    expected_normal = transform[:, :3] @ np.asarray(original_group.params["normal"])
    expected_normal /= np.linalg.norm(expected_normal)
    assert actual_group.params["centre"] == pytest.approx(expected_centre)
    assert actual_group.params["normal"] == pytest.approx(expected_normal)
    if operation == "scale_object" and "factor" in params:
        for dimension in ("pitch", "cell_depth", "width", "height"):
            assert actual_group.params[dimension] == pytest.approx(
                original_group.params[dimension] * 2.0
            )
    elif operation == "scale_object":
        # Ein verzerrtes Muster darf die alten Maße nicht als Messung ausgeben.
        for dimension in ("pitch", "cell_depth", "width", "height"):
            if dimension in actual_group.measure_sources:
                assert actual_group.params[dimension] != pytest.approx(
                    original_group.params[dimension]
                )
    actual = moved.mesh.raw.triangles[list(actual_group.face_indices)].reshape(-1, 3)
    assert actual.min(axis=0) == pytest.approx(expected.min(axis=0))
    assert actual.max(axis=0) == pytest.approx(expected.max(axis=0))
    assert moved.mesh.volume == pytest.approx(
        original.mesh.volume * abs(np.linalg.det(transform[:, :3]))
    )
    history.undo()
    assert _patterns(_run(project, profile), 1) == {original_group.id: original_group}


@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_painting_the_texture_tracks_its_edited_producer(mode: str, profile: Profile) -> None:
    """Ein Filament färbt die ganze Textur und folgt einer geänderten Teilung."""
    project, history = _plate()
    texture_id = _texture(history, mode=mode)
    first = _run(project, profile)
    group = next(iter(_patterns(first, 1).values()))
    history.apply(
        "Textur färben",
        [
            OperationDraft(
                op="paint_slot",
                inputs=("obj_1",),
                params={"at_feature": group.id, "slot": 1, "colour": "#CC2233"},
            )
        ],
    )
    texture_step = next(step for step in history.operations if step.id == texture_id)
    for pitch in (3.0, 4.0):
        if pitch > 3.0:
            history.change_params(texture_id, {**texture_step.params, "pitch": pitch})
        body = _run(project, profile)
        texture = _patterns(body, 1)[group.id]
        slots = np.asarray(body.mesh.slots)
        selected = np.asarray(texture.face_indices)
        assert np.all(slots[selected] == 1)
        unselected = np.ones(len(slots), dtype=bool)
        unselected[selected] = False
        assert np.all(slots[unselected] == 0)
        _bores_and_faces_remain(body)


@pytest.mark.parametrize("inside", [False, True])
@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_a_later_bore_is_independent_even_inside_the_texture(
    inside: bool, mode: str, profile: Profile
) -> None:
    """Eine neue Bohrung bleibt wählbar; ihr Umfang gehört nicht den Rippen."""
    project, history = _plate()
    texture_id = _texture(history, mode=mode)
    first_group = next(iter(_patterns(_run(project, profile), 1).values()))
    x = 0.0 if inside else 20.0
    history.apply(
        "Nachträglich bohren",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={
                    "diameter": 3.0,
                    "x": x,
                    "y": 0.0,
                    "z": 4.6,
                    "depth": 10.0,
                    "compensate": False,
                },
            )
        ],
    )
    body = _run(project, profile)
    group = _patterns(body, 1)[first_group.id]
    assert group.created_by == texture_id
    new_holes = [
        f
        for f in body.features.values()
        if f.kind == "hole" and f.recognised and f.params["diameter"] == pytest.approx(3.0)
    ]
    assert len(new_holes) == 1, [
        (f.id, f.kind, f.recognised, f.params) for f in body.features.values() if f.kind == "hole"
    ]
    assert new_holes[0].params["centre"][0] == pytest.approx(x)
    assert new_holes[0].face_indices
    assert len([f for f in body.features.values() if f.kind == "hole" and f.recognised]) == 5


@pytest.mark.parametrize("extent", ["part", "all"])
@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_cutting_away_texture_never_leaves_stale_selectable_triangles(
    extent: str, mode: str, profile: Profile
) -> None:
    """Abtrag halbiert das Feld oder entfernt es samt seiner Auswahl vollständig."""
    project, history = _plate()
    texture_id = _texture(history, mode=mode)
    original = _run(project, profile)
    first_group = next(iter(_patterns(original, 1).values()))
    history.apply(
        "Textur abschneiden",
        [
            OperationDraft(
                op="cut_away",
                inputs=("obj_1",),
                params={
                    "axis": "x",
                    "position": 0.0 if extent == "part" else 10.0,
                    "keep": "above",
                },
            )
        ],
    )
    body = _run(project, profile)
    groups = _patterns(body, 1 if extent == "part" else 0)
    if extent == "part":
        remaining = groups[first_group.id]
        assert remaining.created_by == texture_id
        points = body.mesh.raw.triangles[list(remaining.face_indices)].reshape(-1, 3)
        assert points[:, 0].min() >= -1e-6
        assert points[:, 0].max() <= 6.0 + 1e-6
    assert body.mesh.is_watertight
    history.undo()
    assert _patterns(_run(project, profile), 1) == {first_group.id: first_group}


@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_splitting_through_the_texture_keeps_a_group_on_both_pieces(
    mode: str, profile: Profile
) -> None:
    """Beide Hälften behalten ihren Anteil am Texturschritt mit gültiger Auswahl."""
    project, history = _plate()
    texture_id = _texture(history, mode=mode)
    original = _run(project, profile)
    original_group = next(iter(_patterns(original, 1).values()))
    original_area = original.mesh.raw.area_faces[list(original_group.face_indices)].sum()
    history.apply(
        "Durch die Textur teilen",
        [
            OperationDraft(
                op="split_pinned",
                inputs=("obj_1",),
                params={"axis": "x", "position": 0.0, "pins": 0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, result
    assert len(result.scene.objects) == 2
    area = 0.0
    for piece in result.scene.objects.values():
        group = next(iter(_patterns(piece, 1).values()))
        assert group.created_by == texture_id
        assert piece.mesh.is_watertight
        area += piece.mesh.raw.area_faces[list(group.face_indices)].sum()
    assert area == pytest.approx(original_area)


def test_the_texture_survives_the_exact_conversion_round_trip(profile: Profile) -> None:
    """Echte Flächen und zurück: dieselbe Textur bleibt am selben Erzeugerschritt."""
    exact_kernel()
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Kleine Platte",
        [OperationDraft(op="create_box", params={"width": 12.0, "depth": 10.0, "height": 4.0})],
    )
    texture_id = _texture(history, width=8.0, height=6.0)
    original = _run(project, profile)
    group = next(iter(_patterns(original, 1).values()))
    original_points = original.mesh.raw.triangles[list(group.face_indices)].reshape(-1, 3)
    for operation, kind in (("mesh_to_exact", "brep"), ("brep_to_mesh", "mesh")):
        history.apply("Körper umwandeln", [OperationDraft(op=operation, inputs=("obj_1",))])
        body = _run(project, profile)
        assert body.kind == kind
        converted = _patterns(body, 1)[group.id]
        assert converted.created_by == texture_id
        mesh = as_mesh_data(body.mesh)
        points = mesh.raw.triangles[list(converted.face_indices)].reshape(-1, 3)
        assert points.min(axis=0) == pytest.approx(original_points.min(axis=0))
        assert points.max(axis=0) == pytest.approx(original_points.max(axis=0))
        assert mesh.volume == pytest.approx(original.mesh.volume)
        assert mesh.is_watertight


@pytest.mark.parametrize("boundary", ["triangles", "features"])
def test_generated_texture_remains_selectable_with_bounded_recognition(
    boundary: str, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Begrenzte Fremdformerkennung verliert keine selbst erzeugte Textur."""
    evaluation = import_module("app.core.scene.evaluate")
    limit = "FEATURE_LIMIT_TRIANGLES" if boundary == "triangles" else "FEATURE_LIMIT_COUNT"
    monkeypatch.setattr(evaluation, limit, 1)
    forget_cache()
    project, history = _plate()
    asked = []

    def decline(question: str, choices: list[Any]) -> Any:
        asked.append(question)
        return choices[0]

    loaded = evaluate(project.document, profile, sources=ProjectSources(project), ask=decline)
    assert loaded.complete, loaded
    history.record_matches(loaded.matches)
    if boundary == "triangles":
        assert len(asked) == 1
        assert any(f.code == "perceive.too_large" for f in loaded.scene.report.findings)
    else:
        assert any(f.code == "perceive.too_many" for f in loaded.scene.report.findings)
    texture_id = _texture(history)
    body = _run(project, profile)
    group = next(iter(_patterns(body, 1).values()))
    assert group.created_by == texture_id


def _overlapping_plates() -> tuple[Project, History]:
    """Zwei Quader überlappen von x = −6 bis 6; ihre Außenenden liegen bei ±14."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    for x in (-4.0, 4.0):
        history.apply(
            "Versetzte Platte",
            [
                OperationDraft(
                    op="create_box",
                    params={"width": 20.0, "depth": 16.0, "height": 4.0, "x": x},
                )
            ],
        )
    return project, history


def _source_textures(project: Project, profile: Profile) -> dict[str, Feature]:
    """Jede Eingabetextur besitzt eine feste Kennung ihres Erzeugerschritts."""
    result = evaluate(project.document, profile)
    assert result.complete, result
    groups = {
        object_id: next(iter(_patterns(body, 1).values()))
        for object_id, body in result.scene.objects.items()
    }
    assert len(groups) == 2
    assert len({group.created_by for group in groups.values()}) == 2
    for group in groups.values():
        assert group.id == f"texture_{group.created_by}"
    return groups


@pytest.mark.parametrize("operation", ["union_objects", "intersect_objects"])
@pytest.mark.parametrize("reverse", [False, True])
def test_boolean_keeps_both_texture_producers_in_each_input_order(
    operation: str, reverse: bool, profile: Profile
) -> None:
    """Vereinigung und Schnitt behalten beide belegten Texturen in jeder Eingangsfolge."""
    project, history = _overlapping_plates()
    for object_id, sign in (("obj_1", -1.0), ("obj_2", 1.0)):
        if operation == "union_objects":
            field = {"x": 10.0 * sign, "width": 6.0, "height": 6.0, "mode": "raised"}
        else:
            field = {"y": 3.0 * sign, "width": 8.0, "height": 4.0, "mode": "engraved"}
        _texture(history, object_id=object_id, **field)
    before = _source_textures(project, profile)
    inputs = ("obj_2", "obj_1") if reverse else ("obj_1", "obj_2")
    history.apply("Körper verknüpfen", [OperationDraft(op=operation, inputs=inputs, seed=23)])
    body = _run(project, profile)
    assert body.mesh.is_watertight
    after = _patterns(body, 2)
    assert set(after) == {before[inputs[0]].id, f"{inputs[1]}.{before[inputs[1]].id}"}
    assert {group.created_by for group in after.values()} == {
        group.created_by for group in before.values()
    }
    for group in after.values():
        producer = next(old for old in before.values() if old.created_by == group.created_by)
        assert group.params["centre"] == pytest.approx(producer.params["centre"])
        assert group.params["mode"] == producer.params["mode"]
        points = body.mesh.raw.triangles[list(group.face_indices)].reshape(-1, 3)
        if operation == "union_objects":
            assert points[:, 0].min() >= producer.params["centre"][0] - 3.0 - 1e-6
            assert points[:, 0].max() <= producer.params["centre"][0] + 3.0 + 1e-6
        else:
            assert points[:, 1].min() >= producer.params["centre"][1] - 2.0 - 1e-6
            assert points[:, 1].max() <= producer.params["centre"][1] + 2.0 + 1e-6


@pytest.mark.parametrize("reverse", [False, True])
def test_difference_never_adopts_the_cutters_texture_as_its_own(
    reverse: bool, profile: Profile
) -> None:
    """Die Gravur des Werkzeugs formt den Schnitt, ihre Herkunft gehört nicht dem Rest."""
    project, history = _overlapping_plates()
    outside_id = _texture(history, x=-10.0, width=6.0, height=6.0)
    cutter_id = _texture(
        history,
        object_id="obj_2",
        mode="engraved",
        x=-6.0,
        z=2.0,
        nx=-1.0,
        nz=0.0,
        width=6.0,
        height=3.0,
    )
    before = _source_textures(project, profile)
    inputs = ("obj_2", "obj_1") if reverse else ("obj_1", "obj_2")
    history.apply(
        "Werkzeug abziehen",
        [OperationDraft(op="subtract_objects", inputs=inputs, seed=23)],
    )
    body = _run(project, profile)
    assert body.mesh.is_watertight
    groups = _patterns(body, 0 if reverse else 1)
    assert {group.created_by for group in groups.values()} == (set() if reverse else {outside_id})
    assert not any(group.created_by == cutter_id for group in groups.values())
    if not reverse:
        group = next(iter(groups.values()))
        assert group.params["centre"] == pytest.approx(before["obj_1"].params["centre"])
        points = body.mesh.raw.triangles[list(group.face_indices)].reshape(-1, 3)
        assert points[:, 0].max() <= -7.0 + 1e-6


@pytest.mark.parametrize("additional_field", [False, True])
def test_a_following_paint_keeps_its_texture_when_an_earlier_texture_disappears(
    additional_field: bool, profile: Profile, tmp_path: Path
) -> None:
    """Eine wegfallende frühere Textur darf spätere Verweise nicht neu nummerieren.

    Mit zwei Feldern führte Umnummerieren zum fehlenden Ziel; mit drei Feldern
    traf derselbe gespeicherte Verweis still das falsche Feld. Der Erzeuger und
    die wirklich gefärbten Dreiecke entscheiden, unabhängig vom Namen der Gruppe.
    """
    project, history = _overlapping_plates()
    disappearing_id = _texture(history, mode="engraved", x=-10.0, width=6.0, height=6.0)
    target_id = _texture(
        history,
        object_id="obj_2",
        mode="engraved",
        x=10.0,
        y=-4.0 if additional_field else 0.0,
        width=6.0,
        height=4.0 if additional_field else 6.0,
    )
    if additional_field:
        _texture(
            history,
            object_id="obj_2",
            mode="engraved",
            x=10.0,
            y=4.0,
            width=6.0,
            height=4.0,
        )
    history.apply(
        "Platten vereinigen",
        [OperationDraft(op="union_objects", inputs=("obj_1", "obj_2"), seed=23)],
    )
    cache = ResultCache()
    count = 3 if additional_field else 2
    groups = _patterns(_run(project, profile, cache), count)
    target = next(group for group in groups.values() if group.created_by == target_id)
    history.apply(
        "Zweite Textur färben",
        [
            OperationDraft(
                op="paint_slot",
                inputs=("obj_1",),
                params={"at_feature": target.id, "slot": 1, "colour": "#CC2233"},
            )
        ],
    )
    baseline = evaluate(project.document, profile, cache=cache)
    assert baseline.complete, baseline
    history.record_matches(baseline.matches)

    def assert_target_painted(current: Project, current_cache: ResultCache, expected: int) -> None:
        """Ausschließlich Dreiecke des gewählten Erzeugers tragen das Filament."""
        body = _run(current, profile, current_cache)
        current_groups = _patterns(body, expected)
        chosen = next(group for group in current_groups.values() if group.created_by == target_id)
        assert chosen.id == target.id
        slots = np.asarray(body.mesh.slots)
        assert len(slots) == body.mesh.triangle_count
        selected = np.zeros(len(slots), dtype=bool)
        selected[list(chosen.face_indices)] = True
        assert np.all(slots[selected] == 1), [
            (group.id, group.created_by) for group in current_groups.values()
        ]
        assert np.all(slots[~selected] == 0)

    assert_target_painted(project, cache, count)
    disappearing = history.operation(disappearing_id)
    history.change_params(disappearing_id, {**disappearing.params, "x": -100.0})
    assert_target_painted(project, cache, count - 1)
    opened = load(save(project, tmp_path / "texture-reference.solidon"))
    assert_target_painted(opened, ResultCache(), count - 1)
    history.undo()
    assert_target_painted(project, cache, count)


def test_three_textures_on_one_body_never_shift_a_saved_paint_to_the_third(
    profile: Profile,
) -> None:
    """Eine wirkungslose erste Gravur darf die zweite nicht zur dritten Auswahl machen."""
    project, history = _plate()
    creators = [
        _texture(history, mode="engraved", x=x, width=8.0, height=6.0) for x in (-12.0, 0.0, 12.0)
    ]
    cache = ResultCache()
    groups = _patterns(_run(project, profile, cache), 3)
    target = next(group for group in groups.values() if group.created_by == creators[1])
    history.apply(
        "Mittlere Textur färben",
        [
            OperationDraft(
                op="paint_slot",
                inputs=("obj_1",),
                params={"at_feature": target.id, "slot": 1, "colour": "#CC2233"},
            )
        ],
    )
    baseline = evaluate(project.document, profile, sources=ProjectSources(project), cache=cache)
    assert baseline.complete, baseline
    history.record_matches(baseline.matches)
    first = history.operation(creators[0])
    history.change_params(first.id, {**first.params, "x": -100.0})
    body = _run(project, profile, cache)
    remaining = _patterns(body, 2)
    assert {group.created_by for group in remaining.values()} == set(creators[1:])
    middle = next(group for group in remaining.values() if group.created_by == creators[1])
    third = next(group for group in remaining.values() if group.created_by == creators[2])
    slots = np.asarray(body.mesh.slots)
    assert np.all(slots[list(middle.face_indices)] == 1), [
        (group.id, group.created_by, sorted(set(slots[list(group.face_indices)])))
        for group in remaining.values()
    ]
    assert np.all(slots[list(third.face_indices)] == 0)
    assert middle.id == target.id


@pytest.mark.parametrize(
    ("style", "width", "height", "old_kind"),
    [
        ("rib", 12.0, 10.0, "face"),
        ("dimple", 12.0, 10.0, "pin"),
        ("dimple", 30.0, 20.0, "pattern"),
        ("voronoi", 30.0, 20.0, "pattern"),
    ],
)
def test_an_old_cell_or_pattern_reference_stops_until_a_new_selection(
    style: str,
    width: float,
    height: float,
    old_kind: str,
    profile: Profile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alte Zellkennungen werden beim Öffnen weder zur ganzen noch zu einer fremden Textur."""
    from app.core.geom import texture_ops

    project, history = _plate()
    _texture(history, pattern=style, width=width, height=height, pitch=3.0)
    current = _run(project, profile)
    texture = next(iter(_patterns(current, 1).values()))
    with monkeypatch.context() as legacy:
        # Vor der Gruppierung lieferte die Texturop nur das Netz; die Erkennung
        # erzeugte daraus Einzelzellen oder ein heuristisches pattern_N.
        legacy.setattr(texture_ops, "_texture_feature", lambda *args: None)
        previous = _run(project, profile)
        old = next(
            feature
            for feature in previous.features.values()
            if feature.kind == old_kind
            and set(feature.face_indices).intersection(texture.face_indices)
        )
        history.apply(
            "Frühere Texturzelle färben",
            [
                OperationDraft(
                    op="paint_slot",
                    inputs=(previous.id,),
                    params={"at_feature": old.id, "slot": 1, "colour": "#CC2233"},
                )
            ],
        )
        before = evaluate(project.document, profile, sources=ProjectSources(project))
        assert before.complete
        history.record_matches(before.matches)
        path = save(project, tmp_path / "legacy-texture-selection.solidon")

    opened = load(path)
    paint = opened.document.ops[-1]
    stopped = evaluate(opened.document, profile, sources=ProjectSources(opened))
    assert not stopped.complete
    assert stopped.stopped_at == paint.id
    body = next(iter(stopped.scene.objects.values()))
    assert old.id not in body.features
    selectable = next(iter(_patterns(body, 1).values()))
    assert selectable.id != old.id

    History(opened.document).change_params(paint.id, {**paint.params, "at_feature": selectable.id})
    selected = _run(opened, profile)
    group = next(iter(_patterns(selected, 1).values()))
    slots = np.asarray(selected.mesh.slots)
    chosen = np.zeros(len(slots), dtype=bool)
    chosen[list(group.face_indices)] = True
    assert np.any(chosen) and np.any(~chosen)
    assert np.all(slots[chosen] == 1)
    assert np.all(slots[~chosen] == 0)


@pytest.mark.parametrize("mode", ["raised", "engraved"])
@pytest.mark.parametrize("through", [False, True])
def test_editing_texture_history_keeps_explicit_bore_coordinates(
    mode: str, through: bool, profile: Profile
) -> None:
    """Eine höhere Krone versetzt eine spätere Sackbohrung mit festen Koordinaten nicht.

    Der sichtbare Verlaufsweg kann die Mündung ausdrücklich mitverschieben.
    Gleiche Zugabe zu Start und Tiefe erhält dabei den vorhandenen Blindboden.
    """
    import math

    import trimesh

    from app.core.units import EPS_GEOM

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = trimesh.creation.cylinder(
        radius=10.0, height=20.0, sections=96
    ).export(file_type="stl")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/shaft.stl", sha256=""
    )
    history = History(project.document)
    history.apply(
        "Zylinder laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    texture_id = _texture(
        history,
        mode=mode,
        width=9.0,
        height=7.0,
        pitch=4.0,
        z=0.0,
        wrap="cylinder",
        wrap_diameter=20.0,
    )
    direction = np.asarray((math.cos(0.1), math.sin(0.1), 0.0))
    lift = 0.6 if mode == "raised" else 0.0
    start = (10.0 + lift) * direction
    bore_params = {
        "diameter": 1.0,
        "compensate": False,
        "x": float(start[0]),
        "y": float(start[1]),
        "z": 0.0,
        "nx": float(direction[0]),
        "ny": float(direction[1]),
        "nz": 0.0,
        "depth": 0.0 if through else 2.0 + lift,
    }
    history.apply(
        "Radial bohren",
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params=bore_params)],
    )
    bore_id = history.operations[-1].id
    original_bore_params = dict(history.operation(bore_id).params)
    before = _run(project, profile)
    old_holes = [feature for feature in before.features.values() if feature.kind == "hole"]
    assert len(old_holes) == 1
    assert old_holes[0].params["through"] is through

    history.change_params(texture_id, {**history.operation(texture_id).params, "depth": 0.9})
    fixed_coordinates = _run(project, profile)
    assert history.operation(bore_id).params == original_bore_params
    _patterns(fixed_coordinates, 1)

    added = 0.3 if mode == "raised" else 0.0
    adjusted = {
        **original_bore_params,
        "x": float(start[0] + added * direction[0]),
        "y": float(start[1] + added * direction[1]),
        "depth": 0.0 if through else bore_params["depth"] + added,
    }
    history.change_params(bore_id, adjusted)
    corrected = _run(project, profile)
    assert corrected.mesh.is_watertight
    holes = [feature for feature in corrected.features.values() if feature.kind == "hole"]
    assert len(holes) == 1
    assert holes[0].params["through"] is through
    assert holes[0].face_indices
    if mode == "raised" and not through:
        # Der feste alte Start liegt nach der Erhöhung unter der Krone.
        # Erst die ausdrücklich angepasste spätere Bohrung öffnet sie ganz.
        assert fixed_coordinates.mesh.volume > corrected.mesh.volume + 0.1
    else:
        assert fixed_coordinates.mesh.volume == pytest.approx(corrected.mesh.volume, abs=EPS_GEOM)
    if not through:
        for hole in (old_holes[0], holes[0]):
            bottom = float(np.dot(np.asarray(hole.params["centre"]), direction)) - 0.5 * float(
                hole.params["depth"]
            )
            assert bottom == pytest.approx(8.0, abs=EPS_GEOM)
