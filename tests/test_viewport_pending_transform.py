"""Treffer gehören zum sichtbaren Aktor, während die nächste Darstellung vorbereitet wird."""

import numpy as np
import pytest
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import MeshData
from app.core.geom.section import SectionPlane
from app.core.scene import EvaluationResult
from app.core.types import Feature, Scene, SceneObject
from app.ui.render.api import Pick
from app.ui.viewport import Viewport
from tests.render_fakes import RecordingRenderer


def two_bodies(*, plates: bool = False) -> EvaluationResult:
    """Zwei getrennte Aktoren mit einer axialen Zielhilfe am jeweiligen Ort."""
    objects = {}
    for index, (name, x) in enumerate((("left", -20.0), ("right", 20.0))):
        raw = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
        raw.apply_translation((x, 0.0, 0.0))
        sides = tuple(int(face) for face in np.flatnonzero(np.abs(raw.face_normals[:, 2]) < 0.5))
        feature = Feature(
            id="hole_1",
            kind="hole",
            provenance="detected",
            params={"centre": (x, 0.0, 0.0), "diameter": 2.0, "axis": (0.0, 0.0, 1.0)},
            face_indices=sides,
        )
        objects[name] = SceneObject(
            id=name,
            name=name,
            mesh=MeshData(raw),
            plate=index if plates else 0,
            features={feature.id: feature},
        )
    return EvaluationResult(scene=Scene(objects=objects))


def test_a_pending_explosion_uses_the_still_visible_offset(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    result = two_bodies()
    view.show_scene(result)
    actor = view._actors["right"]
    monkeypatch.setattr(view._scene_leash, "start", lambda worker: None)
    view._section = SectionPlane.along("z", 3.0)
    view.set_explosion(1.0)
    assert view._scene_worker is not None and view._actors["right"] is actor
    assert np.linalg.norm(view._view_offset(result.scene.objects["right"], result)) > 1.0
    renderer.picks[(30, 40)] = Pick((20.0, 0.0, 2.0), actor, 0)
    point = view._world_at(30, 40)
    assert point is not None and np.allclose(view._from_view(point), (20.0, 0.0, 2.0))
    aimed = view._bore_aim((20.0, 0.0, 10.0), (0.0, 0.0, -1.0), float("inf"), view_space=True)
    assert aimed is not None and np.isclose(aimed[0], 20.0)
    through = view._through_aim((20.0, 0.0, 10.0), (0.0, 0.0, -1.0), view_space=True)
    assert through is not None and np.isclose(through[0], 20.0)
    view._scene_worker = None


def test_a_failed_plate_rebuild_keeps_the_visible_actor_pickable(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    result = two_bodies(plates=True)
    view.show_scene(result)
    actor = view._actors["left"]
    monkeypatch.setattr(view._scene_leash, "start", lambda worker: None)
    monkeypatch.setattr(view._scene_leash, "hold_until_done", lambda worker: None)
    view._section = SectionPlane.along("z", 3.0)
    view.set_plate(1)
    worker = view._scene_worker
    assert worker is not None
    view._scene_crashed(view._scene_generation, "Der Prüf-Arbeiter beendet sich ohne neues Bild.")
    view._scene_worker_done(worker)
    assert view._scene_worker is None and view._actors["left"] is actor
    renderer.picks[(30, 40)] = Pick((-20.0, 0.0, 2.0), actor, 0)
    point = view._world_at(30, 40)
    assert point is not None and np.allclose(view._from_view(point), (-20.0, 0.0, 2.0))
    assert view._object_at((-20.0, 0.0, 2.0)) == "left"
    view.select("left")
    view.select_feature("hole_1")
    assert len(renderer.item_of("feature-patch").points) > 0
    assert len(renderer.item_of("features").texts) == 1
    assert np.allclose(renderer.item_of("feature-markers").points[:, 0], -20.0)


@pytest.mark.parametrize("gesture", ["move", "scale"])
def test_feature_marks_follow_the_body_matrix_and_the_next_scene(
    qt_app: QApplication,
    gesture: str,
) -> None:
    """Gizmo und Skalierwürfel bewegen nur das Bild, samt Merkmalen und Auswahlfläche."""
    view = Viewport()
    renderer = RecordingRenderer(size=(1000, 700))
    view.renderer = renderer
    result = two_bodies()
    view.show_scene(result)
    view.select("right")
    view.select_feature("hole_1")
    actor = view._actors["right"]
    originals = tuple(view._feature_label_data)
    vertices = result.scene.objects["right"].mesh.raw.vertices.copy()
    matrix = np.eye(4)
    if gesture == "move":
        matrix[:3, 3] = (8.0, 6.0, 2.0)
        # Der Gizmo meldet die Matrix vor dem Anwenden, der Skalierwürfel danach.
        view._on_gizmo_interacted(matrix)
        actor.set_matrix(matrix)
        expected = (28.0, 6.0, 2.0)
    else:
        matrix[:3, :3] *= 1.5
        actor.set_matrix(matrix)
        view._on_scale_interacted(1.5)
        expected = (30.0, 0.0, 0.0)
    qt_app.processEvents()
    assert np.allclose(renderer.item_of("feature-markers").points, [expected])
    assert np.allclose(renderer.item_of("feature-label-leaders").points[0], expected)
    assert np.allclose(view._feature_patch.matrix(), matrix)
    assert tuple(view._feature_label_data) == originals
    assert np.array_equal(result.scene.objects["right"].mesh.raw.vertices, vertices)

    # Auch eine Kamerabewegung mitten in der Vorschau benutzt den bewegten Anker.
    view.set_camera_pose((120.0, -100.0, 80.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    assert np.allclose(renderer.item_of("feature-label-leaders").points[0], expected)
    view.show_scene(result)
    assert view._actors["right"] is not actor
    assert np.allclose(renderer.item_of("feature-markers").points, [(20.0, 0.0, 0.0)])
    assert np.allclose(view._feature_patch.matrix(), np.eye(4))


def test_free_body_drag_and_undo_move_marker_label_leader_and_selection_together(
    qt_app: QApplication,
) -> None:
    """Der gemeinsame Renderaufruf zeigt den Zug sofort; Rücknahme lässt keine Marke zurück."""
    view = Viewport()
    renderer = RecordingRenderer(size=(1000, 700))
    # Der Cursorweg braucht ein echtes QWidget, der Renderer weiterhin keine GPU.
    renderer.widget = view
    view.renderer = renderer
    view.show_scene(two_bodies())
    view.select("right")
    view.select_feature("hole_1")
    before = renderer.item_of("feature-markers").points.copy()
    texts = renderer.item_of("features").points.copy()
    originals = tuple(view._feature_label_data)
    assert view.begin_body_drag_at((20.0, 0.0, 0.0))
    view.continue_body_drag_at((28.0, 6.0))
    offset = np.asarray((8.0, 6.0, 0.0))
    assert np.allclose(renderer.item_of("feature-markers").points, before + offset)
    assert np.allclose(renderer.item_of("features").points, texts + offset)
    assert np.allclose(renderer.item_of("feature-label-leaders").points[0], (28.0, 6.0, 0.0))
    assert view._feature_patch.position() == (8.0, 6.0, 0.0)
    assert tuple(view._feature_label_data) == originals
    view._undo_body_preview()
    qt_app.processEvents()
    assert np.allclose(renderer.item_of("feature-markers").points, before)
    assert np.allclose(renderer.item_of("features").points, texts)
    assert view._feature_patch.position() == (0.0, 0.0, 0.0)


def test_a_label_clamped_to_the_edge_keeps_its_leader_attached(qt_app: QApplication) -> None:
    """Ein am Bildrand feststehender Name darf seinen weiterbewegten Anker nicht verlieren."""
    view = Viewport()
    renderer = RecordingRenderer(size=(1000, 700))
    view.renderer = renderer
    view.show_scene(two_bodies())
    view.select("right")
    view.select_feature("hole_1")
    actor = view._actors["right"]
    actor.set_position((500.0, 0.0, 0.0))
    view._draw()
    text_position = renderer.item_of("features").points.copy()
    actor.set_position((600.0, 0.0, 0.0))
    view._draw()
    assert np.allclose(renderer.item_of("features").points, text_position)
    assert np.allclose(renderer.item_of("feature-label-leaders").points[0], (620.0, 0.0, 0.0))


def test_free_body_drag_keeps_every_selected_contour_with_its_body(qt_app: QApplication) -> None:
    """Getrennte Konturen teilen den tatsächlichen Versatz, auch ohne Merkmalsanzeige."""
    view = Viewport()
    renderer = RecordingRenderer()
    renderer.widget = view
    view.renderer = renderer
    result = two_bodies()
    view.show_scene(result)
    view.select("right", more=("left",))
    assert not view._feature_label_data
    originals = {
        owner: renderer.item_of(f"edges:{owner}").points.copy() for owner in ("left", "right")
    }
    # Unterschiedliche tatsächliche Ausgangspositionen dürfen nicht durch einen
    # gemeinsamen, aus den Dokumentdaten berechneten Versatz ersetzt werden.
    view._actors["right"].set_position((2.0, 1.0, 3.0))
    view._actors["left"].set_position((-1.0, 4.0, 2.0))
    assert view.begin_body_drag_at((20.0, 0.0, 0.0))
    view.continue_body_drag_at((28.0, 6.0))
    for owner, expected in (("right", (10.0, 7.0, 3.0)), ("left", (7.0, 10.0, 2.0))):
        edge = renderer.item_of(f"edges:{owner}")
        assert edge.position() == expected
        assert edge.position() == view._actors[owner].position()
        assert np.array_equal(edge.points, originals[owner])

    view._undo_body_preview()
    qt_app.processEvents()
    for owner, expected in (("right", (2.0, 1.0, 3.0)), ("left", (-1.0, 4.0, 2.0))):
        assert renderer.item_of(f"edges:{owner}").position() == expected
    old_edges = [renderer.item_of(f"edges:{owner}") for owner in ("left", "right")]
    view.show_scene(result)
    for owner, old_edge in zip(("left", "right"), old_edges, strict=True):
        edge = renderer.item_of(f"edges:{owner}")
        assert edge is not old_edge and old_edge in renderer.removed
        assert edge.position() == (0.0, 0.0, 0.0)
        assert np.allclose(edge.matrix(), np.eye(4))


@pytest.mark.parametrize("gesture", ["move", "turn", "scale"])
def test_body_transform_contours_follow_without_feature_labels(
    qt_app: QApplication, gesture: str
) -> None:
    """Jeder Körpergriff hält getrennte Konturen an derselben Matrix und Position."""
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    result = two_bodies()
    view.show_scene(result)
    view.select("right")
    view.set_gizmo(True)
    assert not view._feature_label_data and view._feature_patch is None
    actor = view._actors["right"]
    edge = renderer.item_of("edges:right")
    original_points = edge.points.copy()
    original_vertices = result.scene.objects["right"].mesh.raw.vertices.copy()
    actor.set_position((3.0, -2.0, 1.0))
    matrix = np.eye(4)
    if gesture == "move":
        matrix[:3, 3] = (8.0, 6.0, 2.0)
    elif gesture == "turn":
        matrix[:2, :2] = ((0.0, -1.0), (1.0, 0.0))
    else:
        matrix[:3, :3] *= 1.5
    before_renders = renderer.renders
    if gesture == "scale":
        actor.set_matrix(matrix)
        view._on_scale_interacted(1.5)
    else:
        view._on_gizmo_interacted(matrix)
        # Der Gizmo zeichnet direkt nach dem Rückruf: Die Kontur muss ihre
        # Matrix bereits besitzen, bevor ein Timer ein zweites Bild zeichnete.
        assert np.allclose(edge.matrix(), matrix)
        actor.set_matrix(matrix)
    assert np.allclose(edge.matrix(), matrix)
    assert renderer.renders == before_renders
    assert not view._feature_layout_timer.isActive()
    qt_app.processEvents()
    assert np.allclose(edge.matrix(), matrix)
    assert edge.position() == actor.position()
    assert np.allclose(renderer.item_of("edges:left").matrix(), np.eye(4))
    assert renderer.item_of("edges:left").position() == (0.0, 0.0, 0.0)
    assert np.array_equal(edge.points, original_points)
    assert np.array_equal(result.scene.objects["right"].mesh.raw.vertices, original_vertices)

    # Rücknahme stellt über denselben Anzeigeabgleich alle Teile zurück.
    actor.set_matrix(np.eye(4))
    actor.set_position((0.0, 0.0, 0.0))
    view._draw()
    assert np.allclose(edge.matrix(), np.eye(4))
    assert edge.position() == (0.0, 0.0, 0.0)


def test_unchanged_camera_layout_does_not_mutate_contour_actors(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kamerabilder mit unveränderter Körpervorschau setzen keine Aktorwerte neu."""
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    view.show_scene(two_bodies())
    view.select("right")
    view._actors["right"].set_position((4.0, 3.0, 2.0))
    view._draw()
    changed = []
    for owner in ("left", "right"):
        edge = renderer.item_of(f"edges:{owner}")
        monkeypatch.setattr(edge, "set_matrix", lambda value: changed.append("matrix"))
        monkeypatch.setattr(edge, "set_position", lambda value: changed.append("position"))
    view.set_camera_pose((120.0, -100.0, 80.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    view._layout_feature_labels()
    assert not changed


def test_same_feature_id_on_two_bodies_keeps_both_exact_patches(qt_app: QApplication) -> None:
    """Zwei hole_1 sind zwei Ziele; keines darf durch die nackte Kennung verschwinden."""
    view = Viewport()
    renderer = RecordingRenderer(size=(1000, 700))
    view.renderer = renderer
    view.show_scene(two_bodies())
    view.select_feature_refs([("right", "hole_1"), ("left", "hole_1"), ("right", "hole_1")])
    assert view._selected == "right" and view._selected_more == ("left",)
    assert view.selected_feature is None and view.selection_depth() == 2
    assert view.highlighted_feature_refs() == (("right", "hole_1"), ("left", "hole_1"))
    assert view.highlighted_objects() == ()
    assert set(view._feature_patches) == {"left", "right"}
    assert view._feature_patch is view._feature_patches["right"]
    assert view._feature_patches["right"].points[:, 0].min() > 0.0
    assert view._feature_patches["left"].points[:, 0].max() < 0.0
    assert view._feature_label_owners == ["right", "left"]
    assert [priority for _point, _text, priority in view._feature_label_data] == [0, 0]

    # Das bereits gewählte Paar erhält keine zweite Hoverfläche.
    view._hovered_object, view._hovered_feature = "left", "hole_1"
    view._redraw_hover_patch()
    assert view._hover_patch is None


def test_feature_refs_validate_and_keep_the_single_body_adapter(qt_app: QApplication) -> None:
    """Ungültige Paare werden nicht geraten; der bisherige Einzelkörperweg bleibt erhalten."""
    view = Viewport()
    view.renderer = RecordingRenderer()
    view.show_scene(two_bodies())
    view.select_feature_refs([("missing", "hole_1"), ("right", "missing"), ("left", "hole_1")])
    assert view._selected == "left" and view._selected_more == ()
    assert view.selected_feature == "hole_1"
    assert view.highlighted_feature_refs() == (("left", "hole_1"),)
    view.select_features([])
    assert view._selected == "left" and not view.highlighted_feature_refs()
    assert not view._feature_patches
    view.select_features(["hole_1", "hole_1"])
    assert view.selected_feature == "hole_1"
    assert view.highlighted_feature_refs() == (("left", "hole_1"),)


def test_feature_refs_follow_each_body_preview_and_section(qt_app: QApplication) -> None:
    """Paarflächen behalten getrennte Aktormatrizen und denselben Schichtbeschnitt."""
    view = Viewport()
    renderer = RecordingRenderer()
    renderer.widget = view
    view.renderer = renderer
    view.show_scene(two_bodies())
    view.select_feature_refs([("right", "hole_1"), ("left", "hole_1")])
    view._section = SectionPlane.along("z", 0.5)
    view._redraw_features()
    assert all(patch.points[:, 2].max() <= 0.5 + 1e-9 for patch in view._feature_patches.values())
    matrix = np.eye(4)
    matrix[:3, :3] *= 1.5
    view._actors["left"].set_matrix(matrix)
    view._actors["right"].set_position((7.0, 4.0, 1.0))
    view._draw()
    assert np.allclose(view._feature_patches["left"].matrix(), matrix)
    assert view._feature_patches["left"].position() == (0.0, 0.0, 0.0)
    assert np.allclose(view._feature_patches["right"].matrix(), np.eye(4))
    assert view._feature_patches["right"].position() == (7.0, 4.0, 1.0)


def test_new_scene_prunes_full_refs_and_body_selection_drops_old_pair(qt_app: QApplication) -> None:
    """Löschung und Abwahl lassen keine Auswahlfläche am falschen Körper zurück."""
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    result = two_bodies()
    view.show_scene(result)
    view.select_feature_refs([("right", "hole_1"), ("left", "hole_1")])
    old_patches = tuple(view._feature_patches.values())
    only_left = EvaluationResult(scene=Scene(objects={"left": result.scene.objects["left"]}))
    view.show_scene(only_left)
    assert view._selected == "left" and view._selected_more == ()
    assert view.selected_feature == "hole_1"
    assert view.highlighted_feature_refs() == (("left", "hole_1"),)
    assert set(view._feature_patches) == {"left"}
    assert all(patch in renderer.removed for patch in old_patches)
    view.show_scene(result)
    view.select_feature_refs([("right", "hole_1"), ("left", "hole_1")])
    view.select("left")
    assert not view.highlighted_feature_refs()
    assert not view._feature_patches
