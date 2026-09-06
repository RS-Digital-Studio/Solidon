"""Kleine Gegenproben für die geometrischen Kundenwege des Gesamtreviews."""

import importlib
from dataclasses import replace

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.geom.transform import decompose_transform, rotation, scaling, translation
from app.core.sketch import solver
from app.core.sketch.edit import extend
from app.core.sketch.planes import feature_plane
from app.core.sketch.serialize import sketch_to_text
from app.core.sketch.shapes import rectangle
from app.core.types import Sketch, SketchConstraint, SketchElement


def test_g05_mesh_pocket_on_an_offset_face() -> None:
    """Die gewählte Fläche legt die Tasche in beiden Kernen an dieselbe Stelle."""
    from tests.test_sketch_ops import run

    load_operations()
    entry = run("create_brep_box", width=40.0, depth=30.0, height=20.0).outputs[0]
    entry.id = "obj_1"
    face_id = max(entry.features, key=lambda key: entry.features[key].params["centre"][2])
    sketch = replace(rectangle(6.0, 6.0), plane=feature_plane(entry.id, face_id))
    text = sketch_to_text(sketch)
    for source in (entry, replace(entry, kind="mesh", mesh=MeshData.of(entry.mesh.raw.copy()))):
        result = run("sketch_pocket", source, sketch=text, depth=4.0)
        assert source.mesh.volume - result.outputs[0].mesh.volume == pytest.approx(144.0)


def test_g06_all_box_face_normals_point_outwards() -> None:
    """Auch umgekehrt orientierte OCC-Flächen liefern die äußere Normale."""
    from tests.test_sketch_ops import run

    load_operations()
    entry = run("create_brep_box", width=40.0, depth=30.0, height=20.0).outputs[0]
    for face in entry.features.values():
        normal = np.asarray(face.params["normal"])
        away = np.asarray(face.params["centre"]) - entry.mesh.bounds.centre
        assert np.dot(normal, away) > 0.0


def test_g06_dragging_the_left_face_changes_the_left_side() -> None:
    """Die unveränderte UI-Projektion muss tatsächlich die gewählte Seite ziehen."""
    from tests.test_sketch_ops import run

    load_operations()
    entry = run("create_brep_box", width=40.0, depth=30.0, height=20.0).outputs[0]
    entry.id = "obj_1"
    face = min(entry.features.values(), key=lambda feature: feature.params["centre"][0])
    normal = face.params["normal"]
    distance = float(np.dot(normal, (-5.0, 0.0, 0.0)))
    result = run("push_face", entry, nx=normal[0], ny=normal[1], nz=normal[2], distance=distance)
    assert result.outputs[0].mesh.bounds.minimum[0] == pytest.approx(-25.0)
    assert result.outputs[0].mesh.bounds.maximum[0] == pytest.approx(20.0)
    assert result.outputs[0].mesh.volume == pytest.approx(27000.0)


@pytest.mark.parametrize(
    "kind,points",
    [
        ("circle", ((0.0, 0.0), (5.0, 0.0))),
        ("arc", ((0.0, 0.0), (5.0, 0.0), (0.0, 5.0))),
        ("spline", ((0.0, 0.0), (5.0, 0.0), (8.0, 2.0))),
        ("point", ((0.0, 0.0),)),
    ],
)
def test_g07_extending_other_elements_preserves_the_sketch(kind, points) -> None:
    """Ein ungeeigneter Treffer darf weder Element noch Bedingungen zerstören."""
    sketch = Sketch(
        "plane:xy",
        elements=(SketchElement(kind, points), SketchElement("line", ((12.0, -5.0), (12.0, 5.0)))),
        constraints=(SketchConstraint("fixed", (0,)),),
    )
    with pytest.raises(ValidationError) as failure:
        extend(sketch, 0, (5.0, 0.0))
    assert failure.value.suggestions
    assert sketch.elements[0].kind == kind
    assert len(sketch.constraints) == 1


def test_g09_circle_gauges_count_towards_the_dense_budget(monkeypatch) -> None:
    """Schon zwei freie Kreise brauchen eine 2×8-Matrix für ihren Rang."""
    sketch = Sketch(
        "plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (1.0, 0.0))),
            SketchElement("circle", ((4.0, 0.0), (5.0, 0.0))),
        ),
    )
    monkeypatch.setattr(solver, "MAX_JACOBIAN_BYTES", 64)
    with pytest.raises(ValidationError) as failure:
        solver.solve_sketch(sketch)
    assert failure.value.constraint == "too_large"


@pytest.mark.parametrize("axis", ["x", "y", "z"])
@pytest.mark.parametrize("angle", [-180.0, -120.0, -90.1, 90.1, 120.0, 180.0])
def test_g11_gizmo_rotation_roundtrips_past_ninety_degrees(axis, angle) -> None:
    """Achse und Winkel müssen dieselbe sichtbare Drehung rekonstruieren."""
    matrix = translation((1.0, 2.0, 3.0)) @ rotation(axis, angle) @ scaling((1.5,) * 3)
    steps = decompose_transform(matrix)
    rebuilt = (
        translation(steps.offset) @ rotation(steps.axis, steps.angle) @ scaling((steps.scale,) * 3)
    )
    np.testing.assert_allclose(rebuilt, matrix, atol=1e-10)


def test_g12_equal_face_counts_do_not_prove_equal_material_assignment() -> None:
    """Eine halbierte Box hat wieder zwölf Dreiecke, aber andere Flächen."""
    bo = importlib.import_module("app.core.geom.boolean")
    raw = trimesh.creation.box(extents=(10.0,) * 3)
    source = MeshData.of(raw, tuple(1 if normal[0] < -0.5 else 0 for normal in raw.face_normals))
    tool = trimesh.creation.box(extents=(10.0, 20.0, 20.0))
    tool.apply_translation((5.0, 0.0, 0.0))
    result = bo.boolean("difference", [source, MeshData.of(tool)], cut_slot=2).mesh
    assert result.triangle_count == source.triangle_count
    for slot, normal in zip(result.slots, result.raw.face_normals, strict=True):
        assert slot == (1 if normal[0] < -0.5 else 2 if normal[0] > 0.5 else 0)


def test_g13_voxel_cell_budget_does_not_overflow(monkeypatch) -> None:
    """Nur die Arithmetik läuft; die eigentliche Rasterallokation ist gesperrt."""
    bo = importlib.import_module("app.core.geom.boolean")
    raw = trimesh.creation.box(extents=(1.0,) * 3)
    far = raw.copy()
    far.apply_translation((104857.6,) * 3)

    def forbidden(*args):
        pytest.fail("budget must reject before raster allocation")

    monkeypatch.setattr(bo, "_rasterise", forbidden)
    assert bo._voxel("union", [MeshData.of(raw), MeshData.of(far)]) is None


def test_g14_same_volume_and_bounds_still_show_a_moved_hole() -> None:
    """Die Differenzansicht muss beide Lochpositionen sichtbar machen."""
    from app.core.geom.boolean import boolean
    from app.core.geom.difference import compare_scenes
    from tests.test_difference import scene_with

    plate = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 2.0)))

    def cut(x):
        tool = trimesh.creation.box(extents=(2.0, 2.0, 4.0))
        tool.apply_translation((x, 0.0, 0.0))
        return boolean("difference", [plate, MeshData.of(tool)]).mesh

    difference = compare_scenes(scene_with(obj_1=cut(-4.0)), scene_with(obj_1=cut(4.0)))
    assert difference.added_volume == pytest.approx(8.0)
    assert difference.removed_volume == pytest.approx(8.0)


def test_g17_wall_scale_remains_ordered_when_every_wall_exceeds_the_cap(profile) -> None:
    """Gedeckelte Wandkarten brauchen dieselben Grenzen in Bild und Legende.

    Bis zum 06.09.2026 prüfte der Test nur die Ordnung der drei Zahlen. Der
    Befund war aber, dass Bild und Legende verschiedene Skalen zeigten — also
    gehört hierher, wo die Skala beginnt, wo der Deckel liegt und dass die
    Legende den Deckel auch nennt.
    """
    import math

    from app.core.perceive.maps import WALL_SCALE_FACTOR, wall_thickness_map

    mesh = MeshData.of(trimesh.creation.box(extents=(20.0,) * 3))
    minimum = profile.minimum_wall_thickness
    result = wall_thickness_map(mesh, minimum=minimum)
    known = [value for value in result.values if not math.isnan(value)]
    assert max(known) > minimum * WALL_SCALE_FACTOR, "der Würfel muss den Deckel überschreiten"
    assert result.low == 0.0
    assert result.high == pytest.approx(minimum * WALL_SCALE_FACTOR)
    assert result.threshold == minimum
    assert result.low < result.threshold < result.high
    assert result.note == (
        "Untergrenze sind zwei Extrusionsbreiten. Die Skala endet weit darüber; "
        "alles Dickere trägt dieselbe Farbe."
    )


@pytest.mark.parametrize("angle", [15.0, 45.0, 105.0, 225.0])
def test_g03_small_holes_near_the_circular_rim_stay_holes(angle) -> None:
    """Ein inskribiertes Zwölfeck darf den Rand eines Kreises nicht ersetzen."""
    import math

    from app.core.sketch.profile import regions_of
    from tests.test_sketch_ops import run

    load_operations()
    centre = (9.5 * math.cos(math.radians(angle)), 9.5 * math.sin(math.radians(angle)))
    sketch = Sketch(
        "plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("circle", (centre, (centre[0] + 0.3, centre[1]))),
        ),
    )
    regions = regions_of(solver.solve_sketch(sketch))
    assert len(regions) == 1 and len(regions[0].holes) == 1
    result = run("sketch_extrude", sketch=sketch_to_text(sketch), height=2.0)
    assert result.outputs[0].mesh.volume == pytest.approx(math.pi * (100.0 - 0.09) * 2.0)


@pytest.mark.parametrize(
    "centre,radius", [((-6.0, 0.0), 5.0), ((5.0, 0.0), 5.0), ((0.0, 0.0), 10.0)]
)
def test_g04_crossing_touching_and_duplicate_rings_are_rejected(centre, radius) -> None:
    """Aus mehrdeutigen Randringen darf kein ungültiger Körper entstehen."""
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    sketch = Sketch(
        "plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("circle", (centre, (centre[0] + radius, centre[1]))),
        ),
    )
    with pytest.raises(GeometryError) as failure:
        regions_of(solver.solve_sketch(sketch))
    assert failure.value.suggestions


def test_g08_exact_spline_matches_every_preview_sample() -> None:
    """Beide Wege benutzen dieselben kubischen Stücke, auch zwischen den Punkten."""
    from app.core.brep.profiles import _lift_xy, _spline_curve
    from app.core.sketch.profile import _along_spline

    points = ((0.0, 0.0), (2.0, 6.0), (7.0, -3.0), (11.0, 2.0))
    curve = _spline_curve(points, _lift_xy)
    preview = _along_spline(points)
    for index, point in enumerate(preview):
        parameter = curve.FirstParameter() + (
            curve.LastParameter() - curve.FirstParameter()
        ) * index / (len(preview) - 1)
        actual = curve.Value(parameter)
        np.testing.assert_allclose((actual.X(), actual.Y()), point, atol=1e-9)


def test_g04_crossing_line_and_circle_boundaries_are_rejected() -> None:
    """Die Grenzprüfung gilt auch zwischen verschiedenen Kurvenarten."""
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    square = rectangle(8.0, 8.0)
    sketch = replace(
        square, elements=(*square.elements, SketchElement("circle", ((4.0, 0.0), (7.0, 0.0))))
    )
    with pytest.raises(GeometryError, match="schneiden oder berühren"):
        regions_of(solver.solve_sketch(sketch))


def test_g08_the_old_crossing_interpolation_is_a_valid_drawn_outline() -> None:
    """Dieser Umriss kreuzte nur die fremde Interpolation, nicht die Vorschau."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    from app.core.sketch.profile import regions_of, signed_area
    from tests.test_sketch_ops import run

    points = ((-10.0, -5.0), (0.0, 5.0), (-6.0, 0.0), (-9.0, 0.0))
    sketch = Sketch(
        "plane:xy",
        elements=(SketchElement("spline", points), SketchElement("line", (points[-1], points[0]))),
    )
    profile = regions_of(solver.solve_sketch(sketch))[0]
    result = run("sketch_extrude", sketch=sketch_to_text(sketch), height=2.0).outputs[0].mesh
    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.volume == pytest.approx(abs(signed_area(profile)) * 2.0)


def _feature_run(name, entry, profile, **params):
    """Derselbe registrierte Aufruf wie im Merkmalsdialog."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    load_operations()
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=1,
            progress=lambda *_: None,
            ask=lambda _, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_an_absurd_diameter_is_rejected_before_any_tool_is_built(profile) -> None:
    """Die Durchmesserfelder haben keine feste Obergrenze (ein gemessenes Maß darf
    nicht geklemmt werden), aber ein Werkzeug von tausend Metern baut niemand."""
    from app.core.geom.prepare import drill
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    base = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))
    bored = drill(
        base,
        position=(0.0, 0.0, 10.0),
        axis="z",
        diameter=8.0,
        depth=0.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject("obj_1", "Platte", bored, features=detect(bored))
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    with pytest.raises(ValidationError) as caught:
        _feature_run("resize_hole", entry, profile, at_feature=hole.id, diameter=1_000_000.0)
    assert caught.value.field == "diameter"
    assert caught.value.constraint == "maximum"
    # Ein großes, aber echtes Maß geht weiter durch.
    result = _feature_run("resize_hole", entry, profile, at_feature=hole.id, diameter=30.0)
    assert result.outputs


def test_g34_shallow_wide_hole_copy_preserves_depth(profile) -> None:
    """Der Durchmesser ist kein Ersatz für die gemessene Sacklochtiefe."""
    from app.core.geom.prepare import drill
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    base = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))
    bored = drill(
        base,
        position=(-15.0, 0.0, 10.0),
        axis="z",
        diameter=12.0,
        depth=2.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject("obj_1", "Platte", bored, features=detect(bored))
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    copied = _feature_run(
        "duplicate_feature",
        entry,
        profile,
        at_feature=hole.id,
        x=15.0,
        y=0.0,
        z=float(hole.params["centre"][2]),
    ).outputs[0]
    assert bored.volume - copied.mesh.volume == pytest.approx(base.volume - bored.volume, rel=0.02)


def test_g38_sideways_move_into_a_thicker_wall_reports_lost_throughness(profile) -> None:
    """Eine seitliche Bewegung kann den Durchgang genauso verlieren wie eine axiale."""
    from app.core.geom.boolean import boolean
    from app.core.geom.prepare import drill
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    base = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    base.apply_translation((0.0, 0.0, 5.0))
    raised = trimesh.creation.box(extents=(30.0, 40.0, 20.0))
    raised.apply_translation((15.0, 0.0, 10.0))
    stepped = boolean("union", [MeshData.of(base), MeshData.of(raised)]).mesh
    bored = drill(
        stepped,
        position=(-15.0, 0.0, 10.0),
        axis="z",
        diameter=6.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject("obj_1", "Stufenplatte", bored, features=detect(bored))
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    assert hole.params["through"]
    moved = _feature_run(
        "move_feature",
        entry,
        profile,
        at_feature=hole.id,
        x=15.0,
        y=0.0,
        z=float(hole.params["centre"][2]),
    )
    assert any(finding.code == "move_feature.no_longer_through" for finding in moved.findings)
    assert moved.outputs[0].features[hole.id].params["through"] is False


def test_g35_removed_highest_id_stays_reserved_after_an_intermediate_op_and_cache(
    profile, tmp_path
) -> None:
    """Entfernen, Verschieben und erneutes Kopieren bleiben auch mit Plattencache eindeutig."""
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import ProjectSources, new_project

    project = new_project(profile.printer.id, profile.material.id)
    history = History(project.document)
    history.apply(
        "Platte",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 40.0, "height": 10.0})],
    )
    for x in (-25.0, 0.0, 25.0):
        history.apply(
            "Bohrung",
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=("obj_1",),
                    params={"x": x, "z": 10.0, "diameter": 6.0, "compensate": False},
                )
            ],
        )
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources)
    assert before.complete
    holes = sorted(
        name
        for name, feature in before.scene.objects["obj_1"].features.items()
        if feature.kind == "hole"
    )
    assert len(holes) == 3
    history.apply(
        "Entfernen",
        [OperationDraft(op="remove_feature", inputs=("obj_1",), params={"at_feature": holes[-1]})],
    )
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 1.0})],
    )
    cache = ResultCache(disk=DiskCache(MeshCodec(), directory=tmp_path / "cache"))
    removed = evaluate(project.document, profile, sources=sources, cache=cache)
    assert removed.complete
    entry = removed.scene.objects["obj_1"]
    history.apply(
        "Kopieren",
        [
            OperationDraft(
                op="duplicate_feature",
                inputs=("obj_1",),
                params={
                    "at_feature": holes[0],
                    "x": -12.0,
                    "y": 0.0,
                    "z": entry.features[holes[0]].params["centre"][2],
                },
            )
        ],
    )
    replay_cache = ResultCache(disk=DiskCache(MeshCodec(), directory=tmp_path / "cache"))
    replayed = evaluate(
        project.document,
        profile,
        sources=sources,
        cache=replay_cache,
    )
    assert replayed.complete
    assert replay_cache.statistics.disk_hits > 0
    copied = replayed.scene.objects["obj_1"]
    assert holes[-1] not in copied.features
    assert "hole_4" in copied.features
    assert holes[-1] in copied.reserved_feature_ids


def test_cavity_follows_transforms_cache_budget_and_object_identity(tmp_path) -> None:
    """Der exakte Innenraum muss dieselbe Lage und Cacheidentität behalten."""
    import json

    from app.core.geom.mesh import MeshCodec
    from app.core.geom.transform import apply
    from app.core.scene.cache import CachedResult, DiskCache, ResultCache
    from app.core.scene.hashing import object_hash
    from app.core.types import SceneObject

    body = MeshData.of(trimesh.creation.box(extents=(10.0,) * 3))
    cavity = MeshData.of(trimesh.creation.box(extents=(8.0,) * 3))
    source = replace(body, cavity=cavity)
    matrix = translation((11.0, 4.0, 3.0)) @ rotation("y", 120.0) @ scaling((1.0, 2.0, 3.0))
    moved = apply(source, matrix)
    assert moved.cavity is not None
    np.testing.assert_allclose(moved.cavity.raw.vertices, apply(cavity, matrix).raw.vertices)
    cached = CachedResult(objects=(SceneObject("obj_1", "Hohlkörper", moved),))
    assert cached.cost == body.triangle_count + cavity.triangle_count
    disk = DiskCache(MeshCodec(), directory=tmp_path / "cache")
    disk.put("cavity", cached)
    restored = disk.get("cavity")
    assert restored is not None
    np.testing.assert_allclose(
        restored.objects[0].mesh.cavity.raw.vertices, moved.cavity.raw.vertices
    )
    assert object_hash("op", 0, cavity=cavity) != object_hash("op", 0, cavity=moved.cavity)
    assert object_hash("op", 0) != object_hash("op", 0, cavity=cavity)
    memory = ResultCache(triangle_budget=36)
    memory.put("one", cached)
    memory.put("two", cached)
    assert memory.statistics.evictions == 1
    metadata = next((tmp_path / "cache").rglob("objects.json"))
    old = json.loads(metadata.read_text(encoding="utf-8"))
    old.pop("format_version")
    metadata.write_text(json.dumps(old), encoding="utf-8")
    assert disk.get("cavity") is None
