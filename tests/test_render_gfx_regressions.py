"""GFX-Vertragsfehler aus dem Vergleich echter Importmodelle (§18).

Die Zusagen werden am gezeichneten Bild, an echten Picks und am Lebenszyklus
der dargestellten Objekte geprüft.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import numpy as np
import pytest

from app.ui.render.api import AxesMarkerStyle, CameraPose, CellColours, LabelStyle, SurfaceStyle
from app.ui.render.gfx_renderer import GfxLabels, GfxRenderer
from tests.test_render_contract import GFX_MISSING, cube, look_down, plate

pytestmark = pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")


@pytest.fixture
def renderer() -> Iterator[GfxRenderer]:
    view = GfxRenderer(offscreen=True, size=(400, 300))
    try:
        yield view
    finally:
        view.close()


def test_closing_a_renderer_twice_keeps_another_renderer_drawable(renderer: GfxRenderer) -> None:
    """Ein Sprachfenster gibt nur seine eigenen Grafikressourcen frei."""
    other = GfxRenderer(offscreen=True, size=(160, 120))
    try:
        item = other.add_surface(*cube(), name="body", style=SurfaceStyle(lighting=False))
        look_down(other, item.bounds())
        before = other.screenshot()
        assert before.max() > 0
        renderer.close()
        renderer.close()
        assert np.array_equal(other.screenshot(), before)
    finally:
        other.close()


def test_selection_and_background_changes_keep_filament_face_colours(renderer: GfxRenderer) -> None:
    """Die Auswahlfarbe und ein helles Thema dürfen gespeicherte Flächenfarben nicht ersetzen."""
    item = renderer.add_surface(
        *plate(0),
        name="coloured",
        style=SurfaceStyle(lighting=False),
        cell_colours=CellColours(
            np.array([0, 1]), colormap=("#ff0000", "#0000ff"), limits=(0, 1), categorical=True
        ),
    )
    look_down(renderer, item.bounds())
    before = renderer.screenshot()
    red = (before[:, :, 0] > 240) & (before[:, :, 1] < 10) & (before[:, :, 2] < 10)
    blue = (before[:, :, 2] > 240) & (before[:, :, 0] < 10) & (before[:, :, 1] < 10)
    assert red.sum() > 100 and blue.sum() > 100
    item.set_colour("#ffff00")
    renderer.set_background("#eeeeee")
    after = renderer.screenshot()
    assert np.array_equal(after[red | blue], before[red | blue])


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


@pytest.mark.parametrize(
    "initial,backface,expected",
    [
        (1.0, None, (0.16, 0.0, 1.0)),
        (0.8, 0.4, (0.08, 0.0, 0.5)),
        (0.0, 0.4, (0.064, 0.0, 0.4)),
    ],
)
def test_backface_opacity_follows_item_changes(
    renderer: GfxRenderer,
    initial: float,
    backface: float | None,
    expected: tuple[float, ...],
) -> None:
    """Dämpfen und Wiederherstellen gelten auch der anders gefärbten Innenwand."""
    from dataclasses import replace

    style = SurfaceStyle(
        colour="#b9c4d0",
        opacity=initial,
        backface_colour="#8b3a3a",
        backface_opacity=backface,
        lighting=False,
        show_edges=True,
    )
    item = renderer.add_surface(*cube(), name="body", style=style)
    look_down(renderer, item.bounds())
    for opacity, back_opacity in zip((0.16, 0.0, 1.0), expected, strict=True):
        item.set_opacity(opacity)
        actual = renderer.screenshot()
        item.set_visible(False)
        reference = renderer.add_surface(
            *cube(),
            name="reference",
            style=replace(style, opacity=opacity, backface_opacity=back_opacity),
        )
        fresh = renderer.screenshot()
        renderer.remove(reference)
        item.set_visible(True)
        assert np.abs(actual.astype(int) - fresh.astype(int)).max() <= 1
        assert item.objects[1].material.opacity == pytest.approx(back_opacity)
        alpha_mode = "auto" if back_opacity >= 1.0 else "weighted_blend"
        assert item.objects[1].material.alpha_mode == alpha_mode


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


@pytest.mark.parametrize("lighting", [False, True])
@pytest.mark.parametrize("opacity", [0.95, 1.0])
def test_coplanar_surface_stays_visible_but_obeys_occlusion_after_camera_turns(
    renderer: GfxRenderer, lighting: bool, opacity: float
) -> None:
    """Koplanare Markierungen bleiben sichtbar, ohne durch Vorderkörper zu scheinen."""
    renderer.set_background("#777777")
    renderer.add_surface(
        *plate(0, 40), name="floor", style=SurfaceStyle(colour="#ffffff", lighting=False)
    )
    points, triangles = plate(0, 24)
    points += np.array([8.0, 8.0, 0.0])
    marking = renderer.add_surface(
        points,
        triangles,
        name="marking",
        style=SurfaceStyle(
            colour="#0000ff",
            opacity=opacity,
            lighting=lighting,
            ambient=1.0,
            coplanar_overlay=True,
        ),
    )
    cover_points, cover_triangles = cube(40)
    cover_points[:, 2] = 1.0 + cover_points[:, 2] / 40.0
    cover = renderer.add_surface(
        cover_points,
        cover_triangles,
        name="cover",
        style=SurfaceStyle(colour="#ffffff", lighting=False),
    )
    samples = [(float(x), float(y), 0.0) for x in range(10, 31, 2) for y in range(10, 31, 2)]
    for parallel in (True, False):
        renderer.set_parallel_projection(parallel)
        for position in ((20, 20, 100), (65, -55, 60), (-40, 60, 70)):
            cover.set_visible(False)
            renderer.set_camera_pose(CameraPose(position, (20, 20, 0), (0, 1, 0)))
            renderer.reset_camera((0, 40, 0, 40, 0, 2))
            image = renderer.screenshot()
            pixels = [renderer.world_to_display(point) for point in samples]
            colours = np.array([image[int(y), int(x)] for x, y, _depth in pixels], dtype=int)
            assert np.all(colours[:, 2] > colours[:, :2].max(axis=1) + 80), (
                "every interior pixel of a coplanar marking must remain blue"
            )
            x, y, _depth = renderer.world_to_display((20, 20, 0))
            hit = renderer.pick_surface(x, y, among=[marking])
            assert hit is not None and hit.item is marking
            assert hit.point[2] == pytest.approx(0.0, abs=1e-10)
            cover.set_visible(True)
            covered = renderer.screenshot().astype(int)
            assert not np.any(covered[:, :, 2] > covered[:, :, :2].max(axis=2) + 80), (
                "the marking must stay hidden behind the foreground body"
            )
    assert marking.bounds() == pytest.approx((8, 32, 8, 32, 0, 0))
    np.testing.assert_array_equal(marking.objects[0].geometry.positions.data, points)


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


def test_the_vertex_normals_are_computed_once_and_not_per_shader(
    renderer: GfxRenderer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Körper mit Kanten rechnete seine Normalen zweimal.

    Fläche und Kantengitter hängen an derselben ``gfx.Geometry`` — aber jeder
    Shader fragt seine Bindungen selbst an, und ohne mitgegebene Normalen
    rechnet pygfx sie dabei jedes Mal neu. Gezählt am Tetraeder vor dem Fix:
    ohne Kanten ein Lauf, mit Kanten zwei. Am 3,15-Millionen-Dreiecke-Netz
    kostet ein Lauf rund 0,7 Sekunden, und die Darstellungsart „Massiv mit
    Kanten" zahlte ihn doppelt.

    Gezählt wird der Aufruf, nicht die Zeit: Eine Zahl bleibt auch unter
    Fremdlast wahr.
    """
    import pygfx.renderers.wgpu.shaders.meshshader as meshshader

    calls = 0
    original = meshshader.normals_from_vertices

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(meshshader, "normals_from_vertices", counted)

    body = renderer.add_surface(*cube(), name="body", style=SurfaceStyle(show_edges=True))
    look_down(renderer, body.bounds())
    renderer.render()

    assert calls == 0, "pygfx rechnet Normalen, obwohl add_surface sie mitgibt"
    assert renderer._items, "der Körper steht in der Szene"


def test_unlit_and_prepared_surfaces_need_no_normal_computation(
    renderer: GfxRenderer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine unbeleuchtete Fläche rechnet keine Normalen, eine vorbereitete übernimmt sie.

    Die Markierung einer Senkbohrung mit 196 608 Dreiecken rechnete je
    Auswahl 180 ms Normalen, die ihr unbeleuchtetes Material nie liest; und
    ein neuer Körper rechnete sie im Qt-Hauptthread, obwohl ein Arbeiter sie
    vorbereiten kann (RM-203, 22.09.2026). Gezählt wird der Aufruf.
    """
    import pygfx.renderers.wgpu.shaders.meshshader as meshshader
    import pygfx.utils as pygfx_utils

    calls = 0
    original = pygfx_utils.normals_from_vertices

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(pygfx_utils, "normals_from_vertices", counted)
    monkeypatch.setattr(meshshader, "normals_from_vertices", counted)

    vertices, faces = cube()
    renderer.add_surface(vertices, faces, name="mark", style=SurfaceStyle(lighting=False))
    assert calls == 0, "eine unbeleuchtete Fläche braucht keine Normale"

    prepared = GfxRenderer.surface_normals(vertices, faces)
    assert calls == 1 and prepared is not None and prepared.shape == (len(vertices), 3)
    body = renderer.add_surface(
        vertices, faces, name="body", style=SurfaceStyle(), normals=prepared
    )
    look_down(renderer, body.bounds())
    renderer.render()
    assert calls == 1, "vorbereitete Normalen werden übernommen, nicht neu gerechnet"

    renderer.add_surface(vertices, faces, name="wrong", style=SurfaceStyle(), normals=prepared[:1])
    assert calls == 2, "passen sie nicht, rechnet der Renderer selbst"


def _lit_scene(view: GfxRenderer) -> None:
    """Ein beleuchteter Würfel schräg von oben, mit Achsenkreuz — alle drei Lichtarten."""
    view.add_surface(*plate(0, 40), name="floor", style=SurfaceStyle())
    view.add_surface(*cube(10, (15, 15, 0)), name="body", style=SurfaceStyle(colour="#d08040"))
    view.set_axes_marker(AxesMarkerStyle())
    view.set_camera_pose(CameraPose((55, -60, 50), (20, 20, 0), (0, 0, 1)))
    view.reset_camera((0, 40, 0, 40, 0, 10))


def test_the_steady_light_draws_the_stock_image_without_turning_each_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Das eigene gerichtete Licht gibt dasselbe Bild und dreht sich nicht je Bild.

    pygfx richtet ein gerichtetes Licht bei jedem Durchgang über ``look_at``
    neu aus; bei sechs Lichtern und zwei Durchgängen kostete das 7,6 von
    13 ms Rechenzeit je Bild (Profiler, 22.09.2026). Die Richtung braucht nur
    ein Licht, das Schatten wirft, und das tut hier keines. Verglichen wird
    mit einem Renderer, der pygfx' eigenes Licht bekommt.
    """
    import pygfx as gfx

    from app.ui.render import gfx_renderer as module

    turns = 0
    original = gfx.WorldObject.look_at

    def counted(self: object, *args: object, **kwargs: object) -> object:
        nonlocal turns
        if isinstance(self, gfx.DirectionalLight):
            turns += 1
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(gfx.WorldObject, "look_at", counted)

    steady = GfxRenderer(offscreen=True, size=(400, 300))
    try:
        _lit_scene(steady)
        steady.screenshot()
        turns = 0
        image = steady.screenshot()
        assert turns == 0, f"{turns} Drehungen in einem Bild"
    finally:
        steady.close()

    monkeypatch.setattr(
        module, "_directional_light", lambda colour, power: gfx.DirectionalLight(colour, power)
    )
    stock = GfxRenderer(offscreen=True, size=(400, 300))
    try:
        _lit_scene(stock)
        stock.screenshot()
        turns = 0
        reference = stock.screenshot()
        assert turns > 0, "die Gegenprobe muss drehen, sonst misst der Zähler nichts"
    finally:
        stock.close()
    difference = np.abs(image.astype(int) - reference.astype(int))
    assert difference.max() <= 1, f"Abweichung bis {difference.max()} Stufen"
    assert image.max() > 100, "das Bild ist beleuchtet"


def test_a_moving_frame_draws_the_light_occlusion_and_the_still_frame_the_full_one(
    renderer: GfxRenderer,
) -> None:
    """Im Zug zeichnet die Verdeckung leichter; das stehende Bild ist unverändert.

    RM-200: Vier Richtungen mit zwei Schritten und eine Glättung über drei
    mal drei Bildpunkte, solange gezogen wird. Die Fuge bleibt dabei dunkel,
    und wer loslässt, bekommt Bild für Bild dasselbe wie vorher.
    """
    _occlusion_scene(renderer)
    plain = renderer.screenshot()
    renderer.set_ambient_occlusion(True, radius=8, bias=0.05)
    still = renderer.screenshot()
    assert not renderer.frame_was_reduced()

    renderer.set_interacting(True)
    moving = renderer.screenshot()
    assert renderer.frame_was_reduced()
    darkened = plain.astype(int).sum(axis=2) - moving.astype(int).sum(axis=2)
    assert np.count_nonzero(darkened > 5) > 50, "auch im Zug ist die Fuge dunkel"
    assert not np.array_equal(still, moving), "die leichte Stufe zeichnet wirklich anders"

    renderer.set_interacting(False)
    assert np.array_equal(renderer.screenshot(), still)
    assert not renderer.frame_was_reduced()

    renderer.set_ambient_occlusion(False, radius=8, bias=0.05)
    renderer.set_interacting(True)
    renderer.screenshot()
    assert not renderer.frame_was_reduced(), "ohne Verdeckung gibt es nichts nachzuzeichnen"


def test_the_axes_letters_stay_inside_their_field(renderer: GfxRenderer) -> None:
    """Die Buchstaben des Achsenkreuzes sind in jeder Blickrichtung ganz zu sehen.

    Mit perspektivischer Achsenkamera standen sie am Feldrand oder dahinter:
    In der Vorderansicht fehlten X und Z vollständig, in der Iso-Ansicht war
    Z angeschnitten (gemessen ohne Fenster, 06.09.2026) — und ein halber
    Buchstabe sieht aus wie ein Grafikfehler. Gemessen wird in dem Feld, das
    der Viewport der Anzeige gibt, in sechs Blickrichtungen: Kein weißer
    Bildpunkt liegt auf dem Feldrand, jeder Buchstabe hat welche im Feld —
    und das Kreuz füllt das Feld in jeder Richtung, auch schräg von oben,
    wo ein fester Ausschnitt es um ein Fünftel schrumpfen ließe.
    """
    from app.ui.viewport import orientation_corner

    width, height = 400, 300
    renderer.set_background("#202428")
    renderer.set_axes_marker(AxesMarkerStyle())
    left, bottom, right, top = orientation_corner(width, height)
    renderer.place_axes_marker((left, bottom, right, top))
    x0, x1 = round(left * width), round(right * width)
    y0, y1 = round((1.0 - top) * height), round((1.0 - bottom) * height)
    letters = [child for child in renderer._axes_scene.children if type(child).__name__ == "Text"]
    assert len(letters) == 3

    def white_in_field() -> np.ndarray:
        field = renderer.screenshot()[y0:y1, x0:x1]
        return field.min(axis=2) > 200

    poses = {
        "iso": ((100.0, -100.0, 80.0), (0.0, 0.0, 1.0)),
        "oben": ((0.0, 0.0, 100.0), (0.0, 1.0, 0.0)),
        "vorn": ((0.0, -100.0, 0.0), (0.0, 0.0, 1.0)),
        "rechts": ((100.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        "flach": ((100.0, -100.0, 25.0), (0.0, 0.0, 1.0)),
        "von unten": ((70.0, -100.0, -40.0), (0.0, 0.0, 1.0)),
    }
    for name, (position, up) in poses.items():
        renderer.set_camera_pose(CameraPose(position, (0.0, 0.0, 0.0), up))
        for letter in letters:
            letter.visible = False
        field = renderer.screenshot()[y0:y1, x0:x1].astype(int)
        coloured = (np.abs(field - np.array([0x20, 0x24, 0x28])).sum(axis=2) > 40) & ~(
            field.min(axis=2) > 200
        )
        rows, cols = np.nonzero(coloured)
        centre = (y1 - y0) / 2.0
        reach = np.hypot(rows + 0.5 - centre, cols + 0.5 - centre).max()
        assert reach >= 0.8 * centre, f"{name}: the arrows fill only {reach:.0f} of {centre:.0f} px"
        without = white_in_field().sum()
        for letter in letters:
            letter.visible = True
            white = white_in_field()
            letter.visible = False
            assert white.sum() - without >= 12, f"{name}: a letter is missing from the field"
            edge = white[0].any() or white[-1].any() or white[:, 0].any() or white[:, -1].any()
            assert not edge, f"{name}: a letter touches the edge of the field"
        for letter in letters:
            letter.visible = True


@pytest.mark.parametrize("kind", ["press", "move", "release"])
def test_public_pointer_delivery_uses_the_renderers_normal_event_path(renderer, kind):
    """Weitergereichte Qt-Ereignisse bewahren Tasten, Modifikatoren und Koordinaten."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    types = {
        "press": QEvent.Type.MouseButtonPress,
        "move": QEvent.Type.MouseMove,
        "release": QEvent.Type.MouseButtonRelease,
    }
    events = []
    renderer.add_pointer_listener(events.append)
    event = QMouseEvent(
        types[kind],
        QPointF(12.0, 23.0),
        QPointF(112.0, 223.0),
        Qt.MouseButton.RightButton if kind != "move" else Qt.MouseButton.NoButton,
        Qt.MouseButton.RightButton,
        Qt.ShiftModifier | Qt.ControlModifier,
    )
    renderer.deliver_pointer(kind, event)
    assert len(events) == 1
    delivered = events[0]
    assert (delivered.kind, delivered.x, delivered.y) == (kind, 12, 23)
    assert delivered.button == ("right" if kind != "move" else None)
    assert delivered.buttons == frozenset({"right"})
    assert delivered.shift and delivered.ctrl and not delivered.alt
    assert event.isAccepted()


@pytest.mark.parametrize("far_origin", [False, True])
def test_draw_order_beats_the_distance_of_the_origin_in_the_overlay(
    renderer: GfxRenderer, far_origin: bool
) -> None:
    """Von zwei Flächen vor dem Material liegt die mit der kleineren Ordnung unten.

    pygfx sortiert die Deckschicht nach dem Abstand des Objektursprungs zur
    Kamera; die Maßtinte hat ihren Ursprung in der Welt, ein Knopf seinen an
    der Bohrung. Ob die Tinte über oder unter dem Knopf lag, hing damit davon
    ab, wo die Platte im Bauraum steht (Review 21.09.2026). ``draw_order``
    entscheidet vorher: in beiden Lagen des Knopfs liegt die Tinte unten.
    """
    from tests.test_render_contract import same

    plate_vertices, plate_faces = plate(0.0, 40.0)
    ink = renderer.add_surface(
        plate_vertices,
        plate_faces,
        name="ink",
        style=SurfaceStyle(
            colour="#ff0000", lighting=False, pickable=False, keep_in_front=True, draw_order=-1
        ),
    )
    # Der Knopf: dieselbe Fläche, aber mit eigenem Ursprung — einmal näher an
    # der Kamera als der Weltursprung, einmal weit dahinter. Ohne
    # ``draw_order`` liegt er in der zweiten Lage unter der Tinte (gemessen:
    # Rot statt Blau in der Bildmitte).
    shift = (0.0, 0.0, -600.0 if far_origin else 5.0)
    knob = renderer.add_surface(
        plate_vertices - np.asarray(shift),
        plate_faces,
        name="knob",
        style=SurfaceStyle(colour="#0000ff", lighting=False, pickable=False, keep_in_front=True),
    )
    knob.set_position(shift)
    look_down(renderer, ink.bounds())
    image = renderer.screenshot()
    height, width = image.shape[:2]
    centre = image[height // 2, width // 2, :3]
    assert same(tuple(int(value) for value in centre), (0, 0, 255)), (
        f"der Knopf liegt über der Tinte, gleich wo sein Ursprung steht: {centre}"
    )


@pytest.mark.parametrize("parallel", [False, True])
def test_display_to_world_is_affine_in_a_fixed_depth(renderer: GfxRenderer, parallel: bool) -> None:
    """Drei Bildpunkte in einer Tiefe legen alle anderen fest — die Maßtinte rechnet so.

    Die Tiefenebene liegt parallel zum Bild, und dort bildet die Projektion
    linear ab — perspektivisch wie orthografisch. `_Dimensions.refresh` holt
    deshalb drei Weltpunkte und rechnet den Rest; hier steht die Zusage des
    Vertrags an einer schräg stehenden Kamera.
    """
    renderer.set_parallel_projection(parallel)
    renderer.set_camera_pose(CameraPose((70.0, -90.0, 55.0), (10.0, 12.0, 8.0), (0.0, 0.0, 1.0)))
    renderer.reset_camera((-20.0, 40.0, -20.0, 40.0, -20.0, 40.0))
    depth = 0.5
    step = 256.0
    basis = [
        renderer.display_to_world(x, y, depth) for x, y in ((0.0, 0.0), (step, 0.0), (0.0, step))
    ]
    assert all(point is not None for point in basis)
    origin = np.asarray(basis[0], dtype=float)
    along_x = (np.asarray(basis[1], dtype=float) - origin) / step
    along_y = (np.asarray(basis[2], dtype=float) - origin) / step
    rng = np.random.default_rng(21)
    width, height = renderer.view_size()
    for x, y in rng.uniform((0.0, 0.0), (width, height), size=(24, 2)):
        direct = renderer.display_to_world(float(x), float(y), depth)
        assert direct is not None
        derived = origin + x * along_x + y * along_y
        assert np.allclose(direct, derived, atol=1e-6 * max(1.0, float(np.abs(direct).max()))), (
            f"{(x, y)}: {direct} gegen {derived}"
        )


def test_held_frames_arrive_as_one_after_the_release(qt_app: object, renderer: GfxRenderer) -> None:
    """Angehaltene Bilder kommen als eines, und die Frist endet das Anhalten (RM-232).

    Angehalten wird auch, was vor dem Anhalten bestellt war: rendercanvas ruft
    dann ``_frame``, und dort bleibt es bestellt. Wer das Bild jetzt verlangt
    (``render_now``), bekommt es auch aus einem Anhalten heraus.
    """
    import time

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QWidget

    stand_in = QWidget()
    ordered: list[object] = []
    drawn: list[int] = []
    renderer.widget = stand_in
    renderer._canvas.request_draw = lambda function=None: ordered.append(function)  # type: ignore[method-assign]
    renderer._draw = lambda: drawn.append(1)  # type: ignore[method-assign]
    try:
        renderer.hold_frames(60_000)
        renderer.render()
        renderer.render()
        renderer._frame()
        assert ordered == [] and drawn == [], "angehalten, auch was schon bestellt war"
        renderer.release_frames()
        assert len(ordered) == 1, "drei Bestellungen, ein Bild"
        renderer._frame()
        assert drawn == [1]
        renderer.release_frames()
        assert len(ordered) == 1, "ein zweites Freigeben bestellt nichts"

        renderer.hold_frames(1)
        renderer.render()
        deadline = time.monotonic() + 5.0
        while renderer._frames_held and time.monotonic() < deadline:
            QCoreApplication.processEvents()
            time.sleep(0.005)
        assert not renderer._frames_held and len(ordered) == 2, "die Frist endet das Anhalten"

        renderer.hold_frames(60_000)
        renderer.render_now()
        assert not renderer._frames_held and len(ordered) == 3, "jetzt heißt jetzt"
    finally:
        renderer.release_frames()
        renderer.widget = None
        stand_in.deleteLater()


# --- Wiederkehr abgeräumter Überlagerungen (RM-232, 27.09.2026) -----------------------

_MARKING = SurfaceStyle(
    colour="#ff8800",
    opacity=0.6,
    backface_colour="#ff8800",
    backface_opacity=0.6,
    lighting=False,
    pickable=True,
)


def _ring_patch(count: int, radius: float) -> tuple[np.ndarray, np.ndarray]:
    """Ein Fächer aus ``count`` Dreiecken um den Ursprung — verschieden groß je Merkmal."""
    angles = np.linspace(0.0, 2.0 * np.pi, count + 1)
    rim = np.column_stack([radius * np.cos(angles), radius * np.sin(angles), np.zeros(count + 1)])
    vertices = np.vstack([[0.0, 0.0, 0.0], rim])
    faces = np.array([[0, index + 1, index + 2] for index in range(count)])
    return vertices, faces


def _add(view: GfxRenderer, kind: str, size: int) -> object:
    """Ein Element der Bauart ``kind`` — ``size`` bestimmt, wie viel es trägt."""
    if kind == "surface":
        return view.add_surface(*_ring_patch(size, 4.0 + size / 4.0), name="mark", style=_MARKING)
    points = np.array(
        [[4.0 * index - 20.0, 3.0 * (index % 3) - 6.0, 0.0] for index in range(2 * size)]
    )
    if kind == "points":
        return view.add_points(points, name="mark", colour="#ffffff", size=9, keep_in_front=True)
    if kind == "labels":
        return view.add_labels(
            points[:size],
            [f"Bohrung {index}" for index in range(size)],
            name="mark",
            style=LabelStyle(background="#0000ff", show_points=True, point_size=8),
        )
    return view.add_lines(
        points,
        name="mark",
        colour="#ffffff",
        width=4,
        connected=kind == "connected",
        polylines=[size, size] if kind == "chains" else None,
    )


def _objects(item: object) -> list[object]:
    if isinstance(item, GfxLabels):
        return [*item.objects, *(label for _text, label, _field in item._idle)]
    return list(item.objects)  # type: ignore[attr-defined]


@pytest.mark.parametrize("kind", ["surface", "pairs", "connected", "chains", "points", "labels"])
def test_a_removed_overlay_returns_with_its_objects_and_draws_like_a_fresh_one(
    renderer: GfxRenderer, kind: str
) -> None:
    """Abgeräumt, kleiner wieder angelegt: dieselben pygfx-Objekte, dasselbe Bild.

    Die Ansicht baut ihre Überlagerungen je Klick neu, und jedes neue Objekt
    kostete seine Pipeline im nächsten Bild (RM-232). Kommt ein Element
    gleicher Bauart zurück, trägt es die Objekte des abgeräumten — und das
    Bild muss Punkt für Punkt das eines frischen Renderers sein, der nur das
    neue Element kennt. Erst größer, dann kleiner: So bleibt Platz in den
    Puffern übrig, und der darf nirgends zu sehen sein.
    """
    fresh = GfxRenderer(offscreen=True, size=(400, 300))
    try:
        for view in (renderer, fresh):
            view.set_background("#101418")
            look_down(view, (-30.0, 30.0, -20.0, 20.0, 0.0, 0.0))
        first = _add(renderer, kind, 12)
        renderer.screenshot()
        kept = _objects(first)
        renderer.remove(first)  # type: ignore[arg-type]
        again = _add(renderer, kind, 5)
        assert again is not first
        if kind == "labels":
            assert set(map(id, _objects(again))) <= set(map(id, kept)), "keine neuen Glyphen"
        else:
            assert _objects(again) == kept, "dieselben Objekte, keine neue Pipeline"
            assert again.filled is not None  # type: ignore[attr-defined]
        reference = _add(fresh, kind, 5)
        assert again.bounds() == pytest.approx(reference.bounds())  # type: ignore[attr-defined]
        image = renderer.screenshot()
        assert image.max() > 0
        assert np.array_equal(image, fresh.screenshot())
        # Das abgeräumte Element hält nichts mehr, woran man drehen könnte.
        first.set_visible(False)  # type: ignore[attr-defined]
        assert np.array_equal(renderer.screenshot(), image)
    finally:
        fresh.close()


def test_a_returned_surface_moves_picks_and_refuses_a_wrong_count(renderer: GfxRenderer) -> None:
    """Punkte tauschen, Picks und Hüllquader folgen — wie beim frischen Element."""
    first = renderer.add_surface(*_ring_patch(24, 20.0), name="mark", style=_MARKING)
    renderer.remove(first)
    vertices, faces = _ring_patch(8, 10.0)
    surface = renderer.add_surface(vertices, faces, name="mark", style=_MARKING)
    assert surface.filled == len(vertices)  # type: ignore[attr-defined]
    look_down(renderer, (-30.0, 30.0, -20.0, 20.0, 0.0, 0.0))
    hit = renderer.pick_surface(200, 150)
    assert hit is not None and hit.item is surface
    assert surface.bounds() == pytest.approx((-10.0, 10.0, -10.0, 10.0, 0.0, 0.0), abs=1e-5)
    surface.update_points(vertices + np.array([15.0, 0.0, 0.0]))
    assert surface.bounds() == pytest.approx((5.0, 25.0, -10.0, 10.0, 0.0, 0.0), abs=1e-5)
    assert renderer.pick_surface(200, 150) is None, "der Fächer liegt nicht mehr am Ursprung"
    x, y, _depth = renderer.world_to_display((20.0, 1.0, 0.0))
    hit = renderer.pick_surface(x, y)
    assert hit is not None and hit.item is surface
    assert hit.point == pytest.approx((20.0, 1.0, 0.0), abs=0.3)
    with pytest.raises(ValueError):
        surface.update_points(vertices[:3])


def test_only_what_still_looks_as_built_returns(renderer: GfxRenderer) -> None:
    """Umgefärbtes, Beleuchtetes, Zellfarben und Kapazität entstehen immer frisch."""
    recoloured = renderer.add_points(np.zeros((3, 3)), name="mark", colour="#ffffff")
    recoloured.set_colour("#ff0000")
    renderer.remove(recoloured)
    assert renderer.add_points(np.zeros((2, 3)), name="mark", colour="#ffffff").objects[0] not in (
        recoloured.objects
    )
    lit = renderer.add_surface(*cube(), name="body", style=SurfaceStyle())
    renderer.remove(lit)
    assert renderer.add_surface(*cube(), name="body", style=SurfaceStyle()).objects != lit.objects
    ink = renderer.add_lines(np.zeros((4, 3)), name="ink", colour="#ffffff", capacity=8)
    renderer.remove(ink)
    again = renderer.add_lines(np.zeros((4, 3)), name="ink", colour="#ffffff", capacity=8)
    assert again.objects != ink.objects
    assert not renderer._recycled.get(("points", "#ffffff", 8.0, False, False))


def test_waiting_overlays_are_bounded_and_go_with_the_renderer(renderer: GfxRenderer) -> None:
    """Höchstens drei je Bauart warten, ein zweites Abräumen legt nichts doppelt hin."""
    from app.ui.render import gfx_renderer

    items = [
        renderer.add_points(np.zeros((index + 1, 3)), name="mark", colour="#ffffff")
        for index in range(5)
    ]
    for item in items:
        renderer.remove(item)
    renderer.remove(items[-1])
    waiting = renderer._recycled[("points", "#ffffff", 8.0, False, False)]
    assert len(waiting) == gfx_renderer.RECYCLE_PER_KIND == 3
    assert list(waiting) == items[2:]
    assert renderer._recycled_bytes == sum(item.waiting_bytes for item in waiting)
    smallest = list(items[3].objects)
    reused = renderer.add_points(np.zeros((4, 3)), name="mark", colour="#ffffff")
    assert reused.objects == smallest, "das kleinste, in das die Punkte passen"
    assert items[3].objects == [], "das alte hält nichts mehr"
    renderer.close()
    assert not renderer._recycled and not renderer._recycle_order
    assert renderer._recycled_bytes == 0


def test_pointer_events_do_not_ask_the_gpu_for_a_pick(
    renderer: GfxRenderer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesten der Leinwand lösen kein Zurücklesen des Pickpuffers aus (RM-232).

    pygfx' ``WgpuRenderer`` verteilt Leinwandereignisse von sich aus an
    pygfx-Objekte und liest dafür je Ereignis den Pickpuffer zurück — vor
    dem nächsten Bild, synchron. Niemand hier hört darauf; gepickt wird nur,
    wenn die Ansicht fragt.
    """
    asked: list[object] = []
    monkeypatch.setattr(
        type(renderer._renderer),
        "get_pick_info",
        lambda self, position: asked.append(position) or {"world_object": None},
    )
    renderer.add_surface(*cube(), name="body", style=SurfaceStyle(lighting=False))
    renderer.screenshot()
    for kind in ("pointer_down", "pointer_move", "pointer_up"):
        renderer._canvas.submit_event(
            {
                "event_type": kind,
                "x": 200.0,
                "y": 150.0,
                "button": 1,
                "buttons": (1,),
                "modifiers": (),
                "ntouches": 0,
                "touches": {},
                "time_stamp": 0.0,
            }
        )
    renderer._canvas._events.flush()
    renderer.screenshot()
    assert asked == []
