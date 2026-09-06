"""GFX-Vertragsfehler aus dem Vergleich echter Importmodelle (§18).

Die Zusagen werden am gezeichneten Bild, an echten Picks und am Lebenszyklus
der dargestellten Objekte geprüft.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import numpy as np
import pytest

from app.ui.render.api import AxesMarkerStyle, CameraPose, LabelStyle, SurfaceStyle
from app.ui.render.gfx_renderer import GfxLabels, GfxRenderer
from tests.test_render_vtk import GFX_MISSING, cube, look_down, plate

pytestmark = pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")


@pytest.fixture
def renderer() -> Iterator[GfxRenderer]:
    view = GfxRenderer(offscreen=True, size=(400, 300))
    try:
        yield view
    finally:
        view.close()


def test_initial_style_is_readable_and_nonpickable_surface_does_not_cover(
    renderer: GfxRenderer,
) -> None:
    body = renderer.add_surface(*cube(), name="body", style=SurfaceStyle())
    cover = renderer.add_surface(
        *plate(25), name="cover", style=SurfaceStyle(opacity=0.4, pickable=False)
    )
    look_down(renderer, body.bounds())
    assert cover.opacity() == pytest.approx(0.4)
    assert not cover.pickable()
    hit = renderer.pick_surface(200, 150)
    assert hit is not None and hit.item is body


def test_surface_edges_follow_the_surface_opacity(renderer: GfxRenderer) -> None:
    item = renderer.add_surface(
        *cube(),
        name="body",
        style=SurfaceStyle(
            colour="#0000ff", edge_colour="#ffffff", show_edges=True, lighting=False
        ),
    )
    look_down(renderer, item.bounds())
    assert renderer.screenshot().max() > 200
    item.set_opacity(0)
    assert renderer.screenshot().max() == 0


def test_surface_edges_are_a_wireframe_over_the_same_geometry(renderer: GfxRenderer) -> None:
    """Kein Linienpuffer je Kante: Das Drahtgitter teilt die Geometrie und folgt ihr."""
    vertices, faces = cube()
    item = renderer.add_surface(
        vertices,
        faces,
        name="body",
        style=SurfaceStyle(
            colour="#0000ff", edge_colour="#ffffff", show_edges=True, lighting=False
        ),
    )
    edges = item.edge_line
    assert edges is not None and edges.material.wireframe
    assert edges.geometry is item.objects[0].geometry
    assert not edges.material.pick_write
    look_down(renderer, item.bounds())
    image = renderer.screenshot()
    white = np.all(image[:, :, :3] > 200, axis=2)
    blue = (image[:, :, 2] > 200) & (image[:, :, 0] < 60)
    assert np.count_nonzero(white) > 50, "the edges must be visible over the face"
    assert np.count_nonzero(blue) > np.count_nonzero(white), "the face stays a face"
    item.update_points(np.asarray(vertices, dtype=float) + np.asarray((8.0, 0.0, 0.0)))
    assert edges.geometry is item.objects[0].geometry
    moved = renderer.screenshot()
    assert not np.array_equal(moved, image)
    assert np.count_nonzero(np.all(moved[:, :, :3] > 200, axis=2)) > 50


def test_zero_opacity_foreground_does_not_capture_the_visible_body(renderer: GfxRenderer) -> None:
    body = renderer.add_surface(*cube(), name="body", style=SurfaceStyle())
    renderer.add_surface(*plate(25), name="invisible", style=SurfaceStyle(opacity=0))
    look_down(renderer, body.bounds())
    hit = renderer.pick_surface(200, 150)
    assert hit is not None and hit.item is body


@pytest.mark.parametrize("kind", ["lines", "points"])
def test_nonpickable_marks_leave_the_surface_reachable(renderer: GfxRenderer, kind: str) -> None:
    body = renderer.add_surface(*cube(), name="body", style=SurfaceStyle())
    if kind == "lines":
        mark = renderer.add_lines(
            np.array([[0, 10, 25], [20, 10, 25]]), name="mark", colour="#ff0000", width=50
        )
    else:
        mark = renderer.add_points(np.array([[10, 10, 25]]), name="mark", colour="#ff0000", size=50)
    look_down(renderer, body.bounds())
    assert not mark.pickable()
    hit = renderer.pick_surface(200, 150)
    assert hit is not None and hit.item is body


@pytest.mark.parametrize("kind", ["lines", "points", "polylines"])
def test_moving_marks_updates_the_image_and_bounds(renderer: GfxRenderer, kind: str) -> None:
    points = np.array([[0, 0, 0], [20, 0, 0], [0, 10, 0], [20, 10, 0]], dtype=float)
    if kind == "points":
        item = renderer.add_points(points, name="mark", colour="#ffffff", size=10)
    else:
        item = renderer.add_lines(
            points,
            name="mark",
            colour="#ffffff",
            width=8,
            polylines=[2, 2] if kind == "polylines" else None,
        )
    look_down(renderer, (0, 40, 0, 30, 0, 0))
    before = renderer.screenshot()
    item.update_points(points + np.array([10, 10, 0]))
    assert item.bounds() == pytest.approx((10, 30, 10, 20, 0, 0))
    assert np.count_nonzero(before != renderer.screenshot()) > 100
    with pytest.raises(ValueError):
        item.update_points(points[:1])


def test_rebuilt_labels_remain_pickable_and_release_all_registration(
    renderer: GfxRenderer,
) -> None:
    label = renderer.add_labels(
        np.array([[0, 0, 0]]),
        ["Maß"],
        name="label",
        style=LabelStyle(pickable=True, show_points=True, point_size=20),
    )
    look_down(renderer, (-20, 20, -20, 20, 0, 0))
    for index in range(3):
        label.update_labels(np.array([[0, 0, 0]]), [f"Maß {index}"])
        assert renderer.pick_item(200, 150) is label
    renderer.remove(label)
    assert not renderer._items, "rebuilt text must not keep obsolete registrations alive"
    assert not renderer._label_items


def test_empty_label_layout_with_background_can_be_rebuilt(renderer: GfxRenderer) -> None:
    label = renderer.add_labels(
        np.array([[0, 0, 0]]), [""], name="label", style=LabelStyle(background="#0000ff")
    )
    assert renderer.screenshot().shape == (300, 400, 3)
    label.update_labels(np.array([[0, 0, 0]]), ["Maß"])
    assert renderer.screenshot().shape == (300, 400, 3)


def test_forced_opaque_surface_keeps_its_colour_after_opacity_change(
    renderer: GfxRenderer,
) -> None:
    item = renderer.add_surface(
        *cube(),
        name="body",
        style=SurfaceStyle(colour="#ff0000", opacity=0.2, lighting=False, force_opaque=True),
    )
    look_down(renderer, item.bounds())
    assert renderer.screenshot()[150, 200, 0] >= 250
    item.set_opacity(0.1)
    assert renderer.screenshot()[150, 200, 0] >= 250


def test_surface_tolerance_reaches_a_nearby_edge(renderer: GfxRenderer) -> None:
    item = renderer.add_surface(*plate(0, 20), name="plate", style=SurfaceStyle())
    look_down(renderer, item.bounds())
    x, y, _depth = renderer.world_to_display((20, 10, 0))
    assert renderer.pick_surface(x + 2, y, tolerance=0) is None
    hit = renderer.pick_surface(x + 2, y, tolerance=0.01)
    assert hit is not None and hit.item is item
    assert hit.point[0] <= 20.0


def test_pick_pass_is_reused_until_scene_camera_or_image_changes(
    renderer: GfxRenderer, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = renderer.add_surface(*cube(), name="body", style=SurfaceStyle())
    look_down(renderer, item.bounds())
    calls = 0
    original = renderer._renderer.render

    def count(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(renderer._renderer, "render", count)
    assert renderer.pick_item(200, 150) is item
    first = calls
    assert renderer.pick_item(210, 150) is item
    assert calls == first, "pointer movement alone must reuse the existing pick pass"
    item.set_visible(False)
    assert renderer.pick_item(200, 150) is None
    assert calls == first + 1
    item.set_visible(True)
    assert renderer.pick_item(200, 150) is item
    renderer.dolly(1.1)
    assert renderer.pick_item(200, 150) is item
    assert calls == first + 3
    renderer.screenshot()
    drawn = calls
    assert renderer.pick_item(200, 150) is item
    assert calls == drawn + 1, "the ordinary frame replaces the pick buffer"


def test_pick_filter_and_position_do_not_reuse_stale_hits(renderer: GfxRenderer) -> None:
    body = renderer.add_surface(*cube(), name="body", style=SurfaceStyle())
    look_down(renderer, body.bounds())
    assert renderer.pick_surface(200, 150) is not None
    assert renderer.pick_surface(200, 150, among=[]) is None
    assert renderer.pick_surface(200, 150, among=[body]) is not None
    body.set_position((100, 0, 0))
    assert renderer.pick_surface(200, 150) is None
    body.set_position((0, 0, 0))
    assert renderer.pick_surface(200, 150) is not None
    renderer.remove(body)
    assert renderer.pick_surface(200, 150) is None


def test_empty_pick_does_not_read_sixteen_individual_neighbours(
    renderer: GfxRenderer, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    original = renderer._renderer.get_pick_info

    def count(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(renderer._renderer, "get_pick_info", count)
    assert renderer.pick_item(200, 150) is None
    assert calls == 1


@pytest.mark.parametrize("size", [(0, 0), (0, 300), (400, 0)])
def test_zero_sized_canvas_has_no_pick_and_does_not_submit_gpu_work(
    renderer: GfxRenderer, monkeypatch: pytest.MonkeyPatch, size: tuple[int, int]
) -> None:
    monkeypatch.setattr(renderer._canvas, "get_physical_size", lambda: size)

    def unexpected(*args, **kwargs):
        pytest.fail("a zero-sized canvas must not render or read GPU data")

    monkeypatch.setattr(renderer._renderer, "render", unexpected)
    monkeypatch.setattr(renderer._renderer, "get_pick_info", unexpected)
    monkeypatch.setattr(renderer._renderer._blender, "get_texture", unexpected)
    assert renderer.pick_surface(1, 1) is None
    assert renderer.pick_item(1, 1) is None


def test_ambient_highlight_changes_with_the_object_colour(renderer: GfxRenderer) -> None:
    item = renderer.add_surface(
        *cube(), name="body", style=SurfaceStyle(colour="#ff0000", ambient=1.0)
    )
    look_down(renderer, item.bounds())
    item.set_colour("#00ff00")
    pixel = renderer.screenshot()[150, 200]
    assert pixel[1] > 100 and pixel[0] < 5 and pixel[2] < 5


def test_surface_pick_keeps_submillimetre_precision_on_large_triangles(
    renderer: GfxRenderer,
) -> None:
    item = renderer.add_surface(*plate(0, 200), name="plate", style=SurfaceStyle())
    look_down(renderer, item.bounds())
    expected = (137.251234, 58.178765, 0.0)
    x, y, _depth = renderer.world_to_display(expected)
    hit = renderer.pick_surface(x, y, tolerance=0)
    assert hit is not None
    assert hit.point == pytest.approx(expected, abs=1e-7)


def _occlusion_scene(renderer: GfxRenderer) -> None:
    renderer.add_surface(*plate(0, 40), name="floor", style=SurfaceStyle(lighting=False))
    renderer.add_surface(*cube(10, (15, 15, 0)), name="body", style=SurfaceStyle(lighting=False))
    renderer.set_camera_pose(CameraPose((55, -60, 50), (20, 20, 0), (0, 0, 1)))
    renderer.reset_camera((0, 40, 0, 40, 0, 10))


@pytest.mark.parametrize("parallel", [False, True])
def test_occlusion_darkens_contacts_and_switches_off_without_changing_picks(
    renderer: GfxRenderer, parallel: bool
) -> None:
    _occlusion_scene(renderer)
    renderer.set_parallel_projection(parallel)
    before = renderer.screenshot()
    before_pick = renderer.pick_surface(200, 150)
    renderer.set_ambient_occlusion(True, radius=8, bias=0.05)
    shaded = renderer.screenshot()
    darkened = before.astype(int).sum(axis=2) - shaded.astype(int).sum(axis=2)
    assert np.count_nonzero(darkened > 5) > 50, "the contact must actually become darker"
    assert np.array_equal(before[before.sum(axis=2) == 0], shaded[before.sum(axis=2) == 0])
    after_pick = renderer.pick_surface(200, 150)
    assert before_pick is not None and after_pick is not None
    assert after_pick.point == pytest.approx(before_pick.point)
    assert after_pick.item is before_pick.item
    renderer.set_ambient_occlusion(False, radius=8, bias=0.05)
    assert np.array_equal(before, renderer.screenshot())


def test_occlusion_leaves_flat_surfaces_marks_and_axes_unshaded(renderer: GfxRenderer) -> None:
    item = renderer.add_surface(*plate(0), name="flat", style=SurfaceStyle(lighting=False))
    look_down(renderer, item.bounds())
    before = renderer.screenshot()
    renderer.set_ambient_occlusion(True, radius=8, bias=0.05)
    assert np.array_equal(before, renderer.screenshot()), "a flat plate must not shade itself"
    renderer.remove(item)
    _occlusion_scene(renderer)
    renderer.add_lines(
        np.array([[0, 20, 0], [40, 20, 0]]),
        name="mark",
        colour="#ff0000",
        width=5,
        keep_in_front=True,
    )
    renderer.add_labels(
        np.array([[20, 20, 0]]),
        ["Maß"],
        name="label",
        style=LabelStyle(text_colour="#00ff00", background="#0000ff"),
    )
    renderer.set_axes_marker(AxesMarkerStyle())
    renderer.set_ambient_occlusion(False, radius=8, bias=0.05)
    before = renderer.screenshot()
    renderer.set_ambient_occlusion(True, radius=8, bias=0.05)
    after = renderer.screenshot()
    marks = (before[:, :, 0] > 245) & (before[:, :, 1] < 5) & (before[:, :, 2] < 5)
    labels = (before[:, :, 1] > 200) & (before[:, :, 0] < 40) & (before[:, :, 2] < 40)
    assert marks.sum() > 20 and labels.sum() > 10
    assert np.array_equal(before[marks | labels], after[marks | labels])
    assert np.array_equal(before[240:, :80], after[240:, :80]), "axes are drawn after occlusion"


def test_occlusion_honours_bias_and_transparent_only_scenes(renderer: GfxRenderer) -> None:
    _occlusion_scene(renderer)
    before = renderer.screenshot()
    renderer.set_ambient_occlusion(True, radius=8, bias=10)
    assert np.array_equal(before, renderer.screenshot())
    for item in set(renderer._items.values()):
        item.set_opacity(0.4)
    renderer.set_ambient_occlusion(False, radius=8, bias=0.05)
    before = renderer.screenshot()
    renderer.set_ambient_occlusion(True, radius=8, bias=0.05)
    assert np.array_equal(before, renderer.screenshot())


def test_occlusion_smoothing_keeps_material_boundaries_and_is_deterministic(
    renderer: GfxRenderer,
) -> None:
    left, triangles = plate(0, 20)
    right = left + np.array([20.0, 0.0, 0.0])
    for name, points, colour in (("left", left, "#ff0000"), ("right", right, "#0000ff")):
        renderer.add_surface(
            points, triangles, name=name, style=SurfaceStyle(colour=colour, lighting=False)
        )
    renderer.add_surface(*cube(5, (17.5, 7.5, 0)), name="body", style=SurfaceStyle(lighting=False))
    renderer.set_camera_pose(CameraPose((40, -45, 40), (20, 10, 0), (0, 0, 1)))
    renderer.reset_camera((0, 40, 0, 20, 0, 5))
    before = renderer.screenshot()
    renderer.set_ambient_occlusion(True, radius=8, bias=0.05)
    shaded = renderer.screenshot()
    pure_red = (before[:, :, 0] == 255) & (before[:, :, 1:].sum(axis=2) == 0)
    pure_blue = (before[:, :, 2] == 255) & (before[:, :, :2].sum(axis=2) == 0)
    assert np.count_nonzero(pure_red & (shaded[:, :, 0] < 250)) > 20
    assert np.count_nonzero(pure_blue & (shaded[:, :, 2] < 250)) > 20
    assert np.count_nonzero(shaded[pure_red, 1:]) == 0, "AO must never blur the material colours"
    assert np.count_nonzero(shaded[pure_blue, :2]) == 0
    assert np.array_equal(shaded, renderer.screenshot()), "a resting view must not acquire noise"


def test_coplanar_line_has_no_depth_fighting_and_stays_hidden_behind_a_body(
    renderer: GfxRenderer,
) -> None:
    renderer.set_background("#777777")
    renderer.add_surface(
        *plate(0, 40), name="floor", style=SurfaceStyle(colour="#ffffff", lighting=False)
    )
    renderer.add_lines(np.array([[3, 20, 0], [37, 20, 0]]), name="edge", colour="#000000", width=4)
    renderer.set_camera_pose(CameraPose((55, -60, 50), (20, 20, 0), (0, 0, 1)))
    renderer.reset_camera((0, 40, 0, 40, 0, 5))
    image = renderer.screenshot()
    pixels = [renderer.world_to_display((float(x), 20, 0)) for x in np.linspace(5, 35, 60)]
    values = np.array([image[int(y), int(x)].sum(dtype=int) for x, y, _depth in pixels])
    assert np.count_nonzero(values < 100) >= 57, "the visible edge must form one continuous line"
    renderer.add_surface(
        *plate(1, 40), name="cover", style=SurfaceStyle(colour="#ffffff", lighting=False)
    )
    covered = renderer.screenshot()
    assert np.count_nonzero(covered.sum(axis=2) == 0) == 0, "a hidden edge must stay hidden"


def test_label_field_uses_glyph_width_and_keeps_the_anchor_dot_free(renderer: GfxRenderer) -> None:
    style = LabelStyle(
        text_colour="#00ff00",
        background="#0000ff",
        margin=4,
        show_points=True,
        point_colour="#ff0000",
        point_size=10,
    )
    label = renderer.add_labels(np.array([[0, 0, 0]]), ["iiiiii"], name="label", style=style)
    look_down(renderer, (-20, 20, -20, 20, 0, 0))
    narrow = renderer.screenshot()
    label.update_labels(np.array([[0, 0, 0]]), ["WWWWWW"])
    wide = renderer.screenshot()
    blue_narrow = narrow[:, :, 2] > 200
    blue_wide = wide[:, :, 2] > 200
    assert np.ptp(np.where(blue_wide)[1]) > 2 * np.ptp(np.where(blue_narrow)[1])
    assert wide[150, 200, 0] > 240 and wide[150, 200, 1:].sum() < 5
    green = (wide[:, :, 1] > 200) & (wide[:, :, 0] < 10)
    assert np.where(green)[1].min() > 205 and np.where(green)[0].max() < 145


def test_label_layout_moves_existing_glyphs_fields_and_dots(renderer: GfxRenderer) -> None:
    label = renderer.add_labels(
        np.array([[0, 0, 0]]),
        ["Versetztes Maß"],
        name="label",
        style=LabelStyle(
            text_colour="#00ff00",
            background="#0000ff",
            margin=4,
            show_points=True,
            point_colour="#ff0000",
            point_size=10,
        ),
    )
    look_down(renderer, (-20, 20, -20, 20, 0, 0))
    before = renderer.screenshot()
    objects = tuple(label.objects)
    field_geometries = tuple(field.geometry for field in label.fields)
    field_buffers = tuple(field.geometry.positions for field in label.fields)
    registrations = dict(renderer._items)
    label.update_labels(np.array([[10, 0, 0]]), ["Versetztes Maß"])
    assert tuple(label.objects) == objects, "camera layout must reuse the existing GPU objects"
    assert renderer._items == registrations
    after = renderer.screenshot()
    assert not np.array_equal(before, after)
    x, y, _ = renderer.world_to_display((10, 0, 0))
    assert after[int(y), int(x), 0] > 240 and after[int(y), int(x), 1:].sum() < 5
    assert after[150, 200].sum() == 0, "the old anchor and label must be gone"
    assert np.count_nonzero((after[:, :, 1] > 200) & (after[:, :, 0] < 10)) > 20
    assert np.count_nonzero(after[:, :, 2] > 200) > 20
    renderer.dolly(1.1)
    renderer.screenshot()
    assert tuple(field.geometry for field in label.fields) == field_geometries
    assert tuple(field.geometry.positions for field in label.fields) == field_buffers


@pytest.mark.parametrize("background", [None, "#0000ff"])
def test_changing_label_set_reuses_occurrences_and_releases_registration_without_gpu(
    monkeypatch, background
) -> None:
    """Ein Sichtsatzwechsel erzeugt nur neue Namen; ausgeschiedene Paare ruhen verborgen."""

    class Root:
        """Kleine Szenengruppe ohne Grafikgerät."""

        def __init__(self):
            self.children = []

        def add(self, *objects):
            for obj in objects:
                if obj in self.children:
                    self.children.remove(obj)
                self.children.append(obj)

        def remove(self, obj):
            self.children.remove(obj)

    class Object:
        """Identität, Pickkennung, Sichtbarkeit und Ortswert reichen für diesen Lebenszyklus."""

        def __init__(self):
            self.id = id(self)
            self.visible = True
            self.local = SimpleNamespace(position=None)
            self.material = SimpleNamespace(color=None, opacity=None)

    created = []

    def create(anchor, text):
        created.append(text)
        return Object(), Object() if background else None

    labels = GfxLabels("labels", Root(), LabelStyle(background=background))
    monkeypatch.setattr(labels, "_new_label", create)
    view = GfxRenderer.__new__(GfxRenderer)
    view._scene = Root()
    view._items = {}
    view._pick_objects = {}
    view._label_items = []
    view._scene_revision = 0
    view._pick_key = None
    view._register(labels)
    labels.update_labels(np.zeros((3, 3)), ["A", "A", "B"])
    first, duplicate, third = labels.texts
    fields = list(labels.fields)
    labels.update_labels(np.arange(12).reshape(4, 3), ["B", "A", "C", "A"])
    assert created == ["A", "A", "B", "C"]
    assert labels.texts[0] is third and labels.texts[1] is first
    assert labels.texts[3] is duplicate
    if background:
        assert labels.fields[0] is fields[2] and labels.fields[3] is fields[1]
    assert labels.root.children == labels.objects
    registered = dict(view._items)
    labels._field_state = ("previous",)
    labels.update_labels(np.arange(12).reshape(4, 3), ["A", "A", "C", "B"])
    assert view._items == registered
    assert labels._field_state is None
    assert labels.texts[:2] == [first, duplicate]
    assert labels.root.children == labels.objects
    labels.update_labels(np.ones((2, 3)), ["A", "C"])
    assert created == ["A", "A", "B", "C"]
    assert id(third) not in view._items and id(duplicate) not in view._items
    assert third.id not in view._pick_objects and duplicate.id not in view._pick_objects
    assert set(view._items) == {id(obj) for obj in labels.objects}
    # Ausgeschiedene Paare bleiben verborgen im Baum, ohne Pickregistrierung.
    assert third in labels.root.children and duplicate in labels.root.children
    assert not third.visible and not duplicate.visible
    assert all(obj.visible for obj in labels.objects)
    labels.update_labels(np.empty((0, 3)), [])
    assert labels.objects == labels.texts == labels.fields == []
    assert not view._items and not view._pick_objects
    assert labels.root.children and not any(obj.visible for obj in labels.root.children)
    labels.update_labels(np.zeros((2, 3)), ["A", "B"])
    assert created == ["A", "A", "B", "C"], "a resting name returns without new glyphs"
    assert labels.texts[0] in (first, duplicate) and labels.texts[1] is third
    assert all(obj.visible for obj in labels.objects)
    assert set(view._items) == {id(obj) for obj in labels.objects}
    view.remove(labels)
    assert not view._items and not view._pick_objects and not view._label_items


def test_changing_label_set_keeps_pixels_style_dots_and_pickability(renderer: GfxRenderer) -> None:
    """Gehaltene Texte und neue Texte erscheinen mit demselben aktuellen Stil."""
    style = LabelStyle(
        font_size=14,
        background="#0000ff",
        show_points=True,
        point_colour="#ff0000",
        point_size=12,
        pickable=True,
    )
    labels = renderer.add_labels(
        np.array([[-10, 0, 0], [10, 0, 0]]), ["A", "B"], name="labels", style=style
    )
    look_down(renderer, (-25, 25, -20, 20, 0, 0))
    renderer.screenshot()
    kept, discarded = labels.texts
    field = labels.fields[0]
    geometry = field.geometry
    dots = labels.dots
    labels.set_colour("#00ff00")
    labels.set_opacity(0.5)
    labels.update_labels(np.array([[0, 0, 0], [15, 0, 0], [-15, 0, 0]]), ["A", "C", "A"])
    assert labels.texts[0] is kept and labels.fields[0] is field
    assert labels.fields[0].geometry is geometry and labels.dots is dots
    assert id(discarded) not in renderer._items
    for text in labels.texts:
        assert text.material.opacity == pytest.approx(0.5)
        assert tuple(text.material.color)[:3] == pytest.approx((0, 1, 0))
        assert text.material.pick_write
    for anchor in labels.anchors:
        x, y, _ = renderer.world_to_display(anchor)
        assert renderer.pick_item(x, y) is labels
    reused_image = renderer.screenshot()
    reference = renderer.add_labels(
        labels.anchors.copy(), list(labels.labels), name="reference", style=style
    )
    reference.set_colour("#00ff00")
    reference.set_opacity(0.5)
    labels.set_visible(False)
    assert np.array_equal(reused_image, renderer.screenshot())
    renderer.remove(reference)
    labels.set_visible(True)
    labels.set_pickable(False)
    labels.update_labels(np.array([[0, 0, 0], [15, 0, 0]]), ["A", "D"])
    assert not any(obj.material.pick_write for obj in labels.objects)
    x, y, _ = renderer.world_to_display((0, 0, 0))
    assert renderer.pick_item(x, y) is None
    labels.update_labels(np.empty((0, 3)), [])
    assert labels.dots is None and not renderer._items and not renderer._pick_objects
    assert renderer.screenshot().max() == 0


def test_occlusion_resizes_and_preserves_transparent_depth_and_markers(
    renderer: GfxRenderer,
) -> None:
    _occlusion_scene(renderer)
    front = renderer.add_surface(
        *plate(12, 40),
        name="front",
        style=SurfaceStyle(colour="#0000ff", opacity=0.25, lighting=False),
    )
    renderer.add_surface(
        *plate(-1, 40),
        name="hidden",
        style=SurfaceStyle(colour="#ff0000", opacity=0.5, lighting=False),
    )
    renderer.add_lines(
        np.array([[0, 20, 0], [40, 20, 0]]),
        name="mark",
        colour="#00ff00",
        width=5,
        keep_in_front=True,
    )
    renderer.set_ambient_occlusion(True, radius=8, bias=0.05)
    for width, height in ((320, 240), (640, 360), (400, 300)):
        renderer._canvas.set_logical_size(width, height)
        image = renderer.screenshot()
        assert image.shape == (height, width, 3)
        hit = renderer.pick_surface(width / 2, height / 2, among=[front])
        assert hit is not None and hit.item is front
        assert np.count_nonzero((image[:, :, 1] > 245) & (image[:, :, 0] < 5)) > 20
        front.set_visible(False)
        without_front = renderer.screenshot()
        assert np.count_nonzero(image != without_front) > 100
        front.set_visible(True)


@pytest.mark.parametrize("parallel", [False, True])
def test_reset_camera_fits_a_narrow_view(renderer: GfxRenderer, parallel: bool) -> None:
    renderer._canvas.set_logical_size(200, 600)
    vertices, faces = cube(20)
    item = renderer.add_surface(vertices, faces, name="body", style=SurfaceStyle())
    renderer.set_parallel_projection(parallel)
    look_down(renderer, item.bounds())
    projected = np.array([renderer.world_to_display(tuple(point)) for point in vertices])
    assert projected[:, 0].min() >= 0 and projected[:, 0].max() <= 200
    assert projected[:, 1].min() >= 0 and projected[:, 1].max() <= 600


@pytest.mark.parametrize("size", [(400, 300), (200, 600)])
def test_projection_roundtrip_keeps_the_focal_plane_scale(
    renderer: GfxRenderer, size: tuple[int, int]
) -> None:
    renderer._canvas.set_logical_size(*size)
    item = renderer.add_surface(*plate(0, 40), name="plate", style=SurfaceStyle())
    look_down(renderer, item.bounds())
    before = renderer.world_to_display((30, 20, 0))[:2]
    vertical_angle = renderer.view_angle()
    renderer.set_parallel_projection(True)
    assert renderer.view_angle() == pytest.approx(vertical_angle)
    assert renderer.world_to_display((30, 20, 0))[:2] == pytest.approx(before)
    renderer.set_parallel_projection(False)
    assert renderer.world_to_display((30, 20, 0))[:2] == pytest.approx(before)


@pytest.mark.parametrize("parallel", [False, True])
def test_projection_queries_keep_cached_matrices_until_size_or_pose_changes(
    renderer: GfxRenderer, monkeypatch: pytest.MonkeyPatch, parallel: bool
) -> None:
    """Viele Merkmalsanker teilen die Projektion; Resize und Kamerazug bleiben wirksam."""
    item = renderer.add_surface(*plate(0, 40), name="plate", style=SurfaceStyle())
    look_down(renderer, item.bounds())
    renderer.set_parallel_projection(parallel)
    point = (30.0, 20.0, 0.0)
    original_size = renderer._camera.set_view_size
    sizes = []

    def set_size(width: float, height: float) -> None:
        sizes.append((width, height))
        original_size(width, height)

    monkeypatch.setattr(renderer._camera, "set_view_size", set_size)
    before = renderer.world_to_display(point)
    sizes.clear()
    matrix = renderer._camera.camera_matrix
    for _ in range(10):
        assert renderer.world_to_display(point) == pytest.approx(before)
        assert renderer.display_to_world(*before) == pytest.approx(point)
        assert renderer._camera.camera_matrix is matrix
    assert sizes == []

    renderer._canvas.set_logical_size(200, 600)
    resized = renderer.world_to_display(point)
    assert sizes == [(200.0, 600.0)]
    assert renderer._camera.camera_matrix is not matrix
    assert resized[:2] != pytest.approx(before[:2])
    assert renderer.world_to_display((20, 20, 0))[:2] == pytest.approx((100, 300))
    assert renderer.display_to_world(*resized) == pytest.approx(point)

    pose = renderer.camera_pose()
    shift = np.array([4, 0, 0])
    renderer.set_camera_pose(
        CameraPose(
            tuple(np.asarray(pose.position) + shift),
            tuple(np.asarray(pose.focal_point) + shift),
            pose.view_up,
        )
    )
    moved = renderer.world_to_display(point)
    assert moved[:2] != pytest.approx(resized[:2])
    assert renderer.display_to_world(*moved) == pytest.approx(point)
    assert sizes == [(200.0, 600.0)]
