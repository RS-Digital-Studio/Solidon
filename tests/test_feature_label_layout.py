"""Dichte Merkmalsnamen bleiben lesbar, ohne ihre auswählbaren Ziele zu verlieren."""

from itertools import combinations

import numpy as np
import pytest
import trimesh
from PySide6.QtCore import QSize
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import MeshData
from app.core.geom.section import SectionPlane
from app.core.scene import EvaluationResult
from app.core.types import Feature, LayerInfo, Scene, SceneObject
from app.ui.labels import feature_label
from app.ui.viewport import Viewport, layout_feature_labels
from tests.render_fakes import RecordingRenderer


def overlaps(first: tuple, second: tuple) -> bool:
    """Ob zwei Lesefelder mehr als ihren Rand gemeinsam haben."""
    return (
        first[0] < second[2]
        and first[2] > second[0]
        and first[1] < second[3]
        and first[3] > second[1]
    )


def test_dense_automatic_names_never_overlap() -> None:
    """Hundert nahe Ziele bleiben Ziele, aber ihre Namen werden nicht übereinandergemalt."""
    placed = layout_feature_labels(
        [(300.0, 200.0)] * 100, [(110.0, 30.0)] * 100, [2] * 100, (0.0, 0.0, 600.0, 400.0)
    )
    assert 0 < len(placed) < 100
    assert not any(overlaps(first[1], second[1]) for first, second in combinations(placed, 2))


def test_selection_and_hover_take_priority_over_automatic_names() -> None:
    """Die zuletzt eingefügten expliziten Ziele bekommen zuerst lesbare Plätze."""
    placed = layout_feature_labels(
        [(300.0, 200.0)] * 50, [(110.0, 30.0)] * 50, [2] * 48 + [0, 1], (0.0, 0.0, 600.0, 400.0)
    )
    assert [index for index, _rect in placed][:2] == [48, 49]
    assert not any(overlaps(first[1], second[1]) for first, second in combinations(placed, 2))


def test_names_stay_clear_of_window_edges_and_overlay_cards() -> None:
    """Ein expliziter Anker darf hinter einer Karte liegen, sein Name nicht."""
    room = (180.0, 12.0, 650.0, 360.0)
    card = (280.0, 12.0, 500.0, 90.0)
    placed = layout_feature_labels(
        [(20.0, 20.0), (640.0, 355.0), (380.0, 45.0)], [(130.0, 35.0)] * 3, [0, 1, 2], room, [card]
    )
    assert {index for index, _rect in placed} >= {0, 1}
    for _index, rect in placed:
        assert room[0] <= rect[0] < rect[2] <= room[2]
        assert room[1] <= rect[1] < rect[3] <= room[3]
        assert not overlaps(rect, card)


def dense_view() -> tuple[Viewport, RecordingRenderer]:
    """Ein enges Bündel aus vielen unterscheidbaren Namen ohne Erkennungsheuristik."""
    features = {
        f"hole_{number}": Feature(
            id=f"hole_{number}",
            kind="hole",
            provenance="detected",
            params={"centre": (0.0, 0.0, 2.0), "diameter": float(number), "axis": (0.0, 0.0, 1.0)},
        )
        for number in range(1, 81)
    }
    result = EvaluationResult(
        scene=Scene(
            objects={
                "body": SceneObject(
                    id="body",
                    name="Prüfkörper",
                    mesh=MeshData(trimesh.creation.box()),
                    features=features,
                ),
            }
        )
    )
    view = Viewport()
    view.show_scene(result)
    view._selected = "body"
    renderer = RecordingRenderer(size=(1000, 700))
    view.renderer = renderer
    view.set_feature_overlay(True)
    return view, renderer


def boxes_of(view: Viewport, renderer: RecordingRenderer) -> list[tuple]:
    """Die vom Vertrag projizierten Textfelder einschließlich ihres Leseabstands."""
    item = renderer.item_of("features")
    boxes = []
    for point, text in zip(item.points, item.texts, strict=True):
        x, y, _depth = renderer.world_to_display(tuple(point))
        width, height = view._feature_label_sizes[text]
        boxes.append((x - width / 2, y - height / 2, x + width / 2, y + height / 2))
    return boxes


def test_dense_overlay_keeps_every_marker_and_the_selected_and_hovered_name(
    qt_app: QApplication,
) -> None:
    view, renderer = dense_view()
    view.select_feature("hole_80")
    view._hovered_object, view._hovered_feature = "body", "hole_79"
    view._redraw_features()
    markers = renderer.item_of("feature-markers")
    labels = renderer.item_of("features")
    assert len(markers.points) == 80
    assert 2 <= len(labels.texts) < 80
    features = view._result.scene.objects["body"].features
    assert feature_label("hole_80", features["hole_80"]) in labels.texts
    assert feature_label("hole_79", features["hole_79"]) in labels.texts
    assert view.selected_feature == "hole_80"
    assert not markers.pickable and not renderer.item_of("feature-label-leaders").pickable
    assert not renderer.pick_calls, "Textplatzierung darf keine Geometrietreffer berechnen"
    assert not any(
        overlaps(first, second) for first, second in combinations(boxes_of(view, renderer), 2)
    )


def test_camera_resize_and_cards_refresh_layout_without_rebuilding_geometry(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view, renderer = dense_view()
    view.select_feature("hole_80")
    original = renderer.world_to_display
    projected = []

    def project(point: tuple) -> tuple:
        projected.append(point)
        return original(point)

    monkeypatch.setattr(renderer, "world_to_display", project)
    view._draw()
    assert not projected, "eine unveränderte Ansicht benutzt ihr letztes Layout"
    view.set_camera_pose((120.0, -100.0, 80.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    assert projected, "der gemeinsame Kameraweg muss die Plätze erneut prüfen"
    projected.clear()
    renderer.size = (800, 500)
    view.resizeEvent(QResizeEvent(QSize(800, 500), QSize(1000, 700)))
    qt_app.processEvents()
    assert projected, "Resize muss das Layout auch ohne Szenenaufbau erneuern"
    view.set_zone_margins(160, 140, 80)
    qt_app.processEvents()
    for left, top, right, bottom in boxes_of(view, renderer):
        assert left >= 160 and right <= 660
        assert top >= 0 and bottom <= 420
    assert not renderer.meshes
    assert not renderer.pick_calls


def test_layout_retains_the_real_world_anchors(qt_app: QApplication) -> None:
    view, renderer = dense_view()
    before = renderer.item_of("feature-markers").points.copy()
    view.set_zone_margins(300, 100)
    qt_app.processEvents()
    assert np.array_equal(renderer.item_of("feature-markers").points, before)
    assert np.allclose(before[:, 2], 2.0)


@pytest.mark.parametrize("connected", [False, True])
@pytest.mark.parametrize("mode", ["layer", "section", "slab"])
def test_clipped_face_anchor_stays_on_one_real_remaining_piece(
    qt_app: QApplication, connected: bool, mode: str
) -> None:
    """Das Mittel zweier Arme ist Luft, auch wenn es innerhalb der Schnittebene liegt."""
    rectangles = [(-4.0, -2.0, 0.0, 2.0), (2.0, 4.0, 0.0, 2.0)]
    if connected:
        rectangles.append((-2.0, 2.0, 0.0, 0.25))
    vertices = []
    faces = []
    for left, right, bottom, top in rectangles:
        start = len(vertices)
        vertices.extend(((left, 0, bottom), (right, 0, bottom), (right, 0, top), (left, 0, top)))
        faces.extend(((start, start + 1, start + 2), (start, start + 2, start + 3)))
    raw = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    feature = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"centre": (0.0, 0.0, 1.2), "normal": (0.0, -1.0, 0.0)},
        face_indices=tuple(range(len(faces))),
    )
    entry = SceneObject(id="body", name="Arme", mesh=MeshData(raw), features={feature.id: feature})
    view = Viewport()
    view.show_scene(EvaluationResult(scene=Scene(objects={entry.id: entry})))
    if mode == "layer":
        view._layer = LayerInfo(
            z=1.0, contours=(), area=0, overhang_area=0, islands=(), min_width=0
        )
    else:
        view._section = SectionPlane.along("z", 1.5)
        if mode == "slab":
            view._slice_thickness = 0.5
    before = raw.vertices.copy()
    anchor = view._feature_label_anchor(entry, feature.id, feature, explicit=mode != "layer")
    assert anchor is not None
    x, y, z = anchor
    assert y == pytest.approx(0.0)
    assert any(
        left - 1e-9 <= x <= right + 1e-9 and bottom - 1e-9 <= z <= top + 1e-9
        for left, right, bottom, top in rectangles
    ), "face marker must touch a real part of the U, not the empty space between its arms"
    if mode == "layer":
        assert z == pytest.approx(1.0)
    elif mode == "slab":
        assert 1.0 - 1e-9 <= z <= 1.5 + 1e-9
    else:
        assert z <= 1.5 + 1e-9
    assert np.array_equal(raw.vertices, before)


def test_a_bore_marker_keeps_its_axis_in_the_visible_slice(qt_app: QApplication) -> None:
    """Die neue Flächenregel darf eine Bohrungsachse nicht auf die Innenwand versetzen."""
    raw = trimesh.creation.cylinder(radius=2.0, height=4.0)
    sides = tuple(int(index) for index in np.flatnonzero(np.abs(raw.face_normals[:, 2]) < 0.5))
    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 4.0},
        face_indices=sides,
    )
    entry = SceneObject(
        id="body", name="Bohrung", mesh=MeshData(raw), features={feature.id: feature}
    )
    view = Viewport()
    view.show_scene(EvaluationResult(scene=Scene(objects={entry.id: entry})))
    view._layer = LayerInfo(z=0.0, contours=(), area=0, overhang_area=0, islands=(), min_width=0)
    anchor = view._feature_label_anchor(entry, feature.id, feature, explicit=False)
    assert anchor is not None and np.allclose(anchor, (0.0, 0.0, 0.0))


def test_leaders_reach_the_visible_field_inside_the_collision_reserve(
    qt_app: QApplication,
) -> None:
    """Auch kleinere Rendererschriften werden an ihr Feld angeschlossen, nicht an den Freiraum."""
    view, renderer = dense_view()
    view.select_feature("hole_80")
    labels = renderer.item_of("features")
    leaders = renderer.item_of("feature-label-leaders").points.reshape(-1, 2, 3)
    assert len(leaders) == len(labels.texts)
    for (_start, end), point, text in zip(leaders, labels.points, labels.texts, strict=True):
        centre = np.asarray(renderer.world_to_display(tuple(point))[:2])
        finish = np.asarray(renderer.world_to_display(tuple(end))[:2])
        # Die Schrift eines Backends darf kleiner sein als die konservative
        # Kollisionsbox. Der Anschluss muss trotzdem das sichtbare Feld erreichen.
        half_field = np.asarray(view._feature_label_sizes[text]) * 0.3
        assert np.all(np.abs(finish - centre) <= half_field)
    assert labels.style.background_opacity == pytest.approx(1.0)
    assert not labels.style.pickable


@pytest.mark.parametrize("line_first", [True, False])
def test_gfx_label_field_covers_its_leader_without_covering_picks(line_first: bool) -> None:
    """Die Verbindung erreicht das Textfeld; darin bleiben Feld und Schrift unverdeckt."""
    from app.ui.render.api import CameraPose, LabelStyle, SurfaceStyle
    from app.ui.render.gfx_renderer import GfxRenderer
    from tests.test_render_contract import GFX_MISSING

    if GFX_MISSING is not None:
        pytest.skip(f"pygfx: {GFX_MISSING}")
    renderer = GfxRenderer(offscreen=True, size=(400, 300))
    try:
        body = renderer.add_surface(
            np.asarray([[-20, -15, -1], [20, -15, -1], [20, 15, -1], [-20, 15, -1]], dtype=float),
            np.asarray([[0, 1, 2], [0, 2, 3]]),
            name="body",
            style=SurfaceStyle(colour="#777777", lighting=False),
        )

        def line() -> None:
            """Eine klar erkennbare Verbindung bis in die Mitte des Felds zeichnen."""
            renderer.add_lines(
                np.asarray([[-12, 0, 0], [6, 0, 0]], dtype=float),
                name="leader",
                colour="#ff0000",
                width=3,
                keep_in_front=True,
                pickable=False,
            )

        if line_first:
            line()
        renderer.add_labels(
            np.asarray([[6, 0, 0]], dtype=float),
            ["Merkmal"],
            name="label",
            style=LabelStyle(
                text_colour="#00ff00",
                background="#0000ff",
                background_opacity=1.0,
                margin=4,
                show_points=False,
                always_visible=True,
                pickable=False,
            ),
        )
        if not line_first:
            line()
        renderer.set_camera_pose(CameraPose((0, 0, 50), (0, 0, 0), (0, 1, 0)))
        renderer.set_parallel_projection(True)
        renderer.set_parallel_scale(15)
        image = renderer.screenshot()
        red = (image[:, :, 0] > 200) & (image[:, :, 1:].max(axis=2) < 40)
        blue = (image[:, :, 2] > 200) & (image[:, :, :2].max(axis=2) < 40)
        green = (image[:, :, 1] > 200) & (image[:, :, 0] < 40)
        assert np.count_nonzero(red) > 50, "the leader must remain visible outside the field"
        assert np.count_nonzero(green) > 10, "the text must remain visible above its field"
        ys, xs = np.where(blue)
        assert len(xs) > 20
        assert not np.any(red[ys.min() + 2 : ys.max() - 1, xs.min() + 3 : xs.max() - 2])
        row = round(renderer.world_to_display((6, 0, 0))[1])
        assert np.any(red[row - 1 : row + 2, xs.min() - 3 : xs.min() + 1])
        for point in ((6, 0, 0), (-6, 0, 0)):
            x, y, _depth = renderer.world_to_display(point)
            hit = renderer.pick_surface(x, y)
            assert hit is not None and hit.item is body
    finally:
        renderer.close()
