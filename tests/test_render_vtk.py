"""Die Renderer hinter der 3D-Ansicht, gemessen am Bild (§18, §35).

Kein Fenster, keine Attrappe: Jeder Test baut einen Renderer ohne Fenster auf,
stellt etwas hinein und liest Bildpunkte oder Picks zurück. Was hier grün
ist, hat VTK beziehungsweise pygfx wirklich gezeichnet — die Fensterseite
(Qt-Widget, Zeiger) prüft ``test_ui.py`` am gebauten Fenster.

**Jeder Test läuft über beide Renderer** (``BACKENDS``): Der Vertrag ist erst
dann einer, wenn dasselbe Bild auf beiden entsteht. Fehlt pygfx ein
wgpu-Adapter (eine CI ohne Grafikkarte), fällt dieser Zweig als Skip aus,
nicht still — der Grund steht am Skip.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest

from app.ui.render.api import (
    AxesMarkerStyle,
    CameraPose,
    CellColours,
    LabelStyle,
    Renderer,
    SurfaceStyle,
    hex_of,
    rgb,
)
from app.ui.render.vtk_renderer import VtkRenderer

SIZE = (400, 300)
BACKGROUND = "#101418"
BACKGROUND_RGB = tuple(round(part * 255) for part in rgb(BACKGROUND))

#: Wie weit ein gemessener Bildpunkt von der Sollfarbe abweichen darf. pygfx
#: rechnet in linearem Licht und zurück; das kostet je Kanal eine Stufe.
COLOUR_SLACK = 2


def _gfx_missing() -> str | None:
    """Warum der pygfx-Zweig hier nicht laufen kann — oder ``None``."""
    try:
        import wgpu

        adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    except Exception as problem:  # kein Paket, kein Treiber, kein Adapter
        return str(problem) or type(problem).__name__
    return None if adapter is not None else "kein wgpu-Adapter"


GFX_MISSING = _gfx_missing()
BACKENDS = [
    "vtk",
    pytest.param(
        "gfx", marks=pytest.mark.skipif(GFX_MISSING is not None, reason=f"pygfx: {GFX_MISSING}")
    ),
]


def make_renderer(backend: str, size: tuple[int, int] = SIZE) -> Renderer:
    """Ein Renderer ohne Fenster — VTK oder pygfx, nach Namen."""
    if backend == "gfx":
        from app.ui.render.gfx_renderer import GfxRenderer

        return GfxRenderer(offscreen=True, size=size)
    return VtkRenderer(offscreen=True, size=size)


def same(pixel: np.ndarray, expected: tuple[int, ...], slack: int = COLOUR_SLACK) -> bool:
    """Ob ein Bildpunkt die Farbe trägt — bis auf die Stufe, die Gamma kostet."""
    return all(
        abs(int(have) - int(want)) <= slack for have, want in zip(pixel, expected, strict=True)
    )


def cube(edge: float = 20.0, origin: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple:
    """Ein geschlossener Würfel mit zwölf Dreiecken, Normalen nach außen."""
    base = np.array(
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]],
        dtype=float,
    )
    faces = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],
            [4, 5, 6],
            [4, 6, 7],
            [0, 1, 5],
            [0, 5, 4],
            [1, 2, 6],
            [1, 6, 5],
            [2, 3, 7],
            [2, 7, 6],
            [3, 0, 4],
            [3, 4, 7],
        ]
    )
    return base * edge + np.asarray(origin, dtype=float), faces


def plate(z: float, size: float = 40.0) -> tuple:
    """Eine ebene Platte aus zwei Dreiecken in der Höhe ``z``."""
    return (
        np.array([[0, 0, z], [size, 0, z], [size, size, z], [0, size, z]], dtype=float),
        np.array([[0, 1, 2], [0, 2, 3]]),
    )


def bright(image: np.ndarray, threshold: int = 100) -> np.ndarray:
    """Maske der Bildpunkte, die deutlich heller sind als der Hintergrund."""
    return image.sum(axis=2) > threshold


@pytest.fixture(params=BACKENDS)
def renderer(request: pytest.FixtureRequest) -> Iterator[Renderer]:
    view = make_renderer(request.param)
    view.set_background(BACKGROUND)
    try:
        yield view
    finally:
        view.close()


def look_down(view: Renderer, bounds: tuple) -> None:
    """Die Kamera senkrecht von oben auf einen Quader, mit Qt-Oben nach +y."""
    centre = ((bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, bounds[5])
    view.set_camera_pose(
        CameraPose((centre[0], centre[1], centre[2] + 200.0), centre, (0.0, 1.0, 0.0))
    )
    view.reset_camera(bounds)


def test_a_surface_is_drawn_where_the_camera_looks_and_nowhere_else(
    renderer: Renderer,
) -> None:
    vertices, faces = cube()
    body = renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle(colour="#b9c4d0"))
    renderer.set_camera_pose(CameraPose((60.0, -80.0, 50.0), (10.0, 10.0, 10.0), (0.0, 0.0, 1.0)))
    renderer.reset_camera(body.bounds())
    image = renderer.screenshot()
    assert image.shape == (SIZE[1], SIZE[0], 3) and image.dtype == np.uint8
    assert same(image[5, 5], BACKGROUND_RGB), "die Ecke zeigt den Hintergrund"
    assert image[150, 200].sum() > sum(BACKGROUND_RGB) + 60, "die Mitte zeigt den Körper"
    assert renderer.background() == BACKGROUND


def test_a_pick_in_the_middle_hits_the_body_and_a_pick_beside_it_hits_nothing(
    renderer: Renderer,
) -> None:
    vertices, faces = cube()
    body = renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle())
    renderer.set_camera_pose(CameraPose((60.0, -80.0, 50.0), (10.0, 10.0, 10.0), (0.0, 0.0, 1.0)))
    renderer.reset_camera(body.bounds())
    renderer.render()
    hit = renderer.pick_surface(200, 150)
    assert hit is not None and hit.item is body
    assert 0 <= hit.cell < 12
    low_x, high_x, _low_y, _high_y, low_z, high_z = body.bounds()
    assert low_x - 1e-6 <= hit.point[0] <= high_x + 1e-6
    assert low_z - 1e-6 <= hit.point[2] <= high_z + 1e-6
    assert renderer.pick_surface(3, 3) is None
    assert renderer.pick_item(200, 150) is body
    assert renderer.pick_item(3, 3) is None


def test_the_pick_list_decides_who_may_be_hit(renderer: Renderer) -> None:
    """Eine Platte vor dem Würfel fängt jeden Klick — außer sie steht nicht
    auf der Liste. Genau so hält der Bewegungsgriff seine Pfeile aus der
    Auswahl heraus (§18.11)."""
    vertices, faces = cube()
    body = renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle())
    cover_vertices, cover_faces = plate(z=25.0)
    cover = renderer.add_surface(cover_vertices, cover_faces, name="cover", style=SurfaceStyle())
    look_down(renderer, (-5.0, 45.0, -5.0, 45.0, 0.0, 25.0))
    renderer.render()
    x, y, _depth = renderer.world_to_display((10.0, 10.0, 20.0))
    everything = renderer.pick_surface(x, y)
    assert everything is not None and everything.item is cover
    listed = renderer.pick_surface(x, y, among=[body])
    assert listed is not None and listed.item is body


def test_visibility_colour_and_opacity_reach_the_pixels(renderer: Renderer) -> None:
    vertices, faces = plate(z=0.0)
    body = renderer.add_surface(
        vertices, faces, name="plate", style=SurfaceStyle(colour="#ffffff", lighting=False)
    )
    look_down(renderer, body.bounds())
    assert same(renderer.screenshot()[150, 200], (255, 255, 255))
    body.set_colour("#ff0000")
    assert body.colour() == "#ff0000"
    assert same(renderer.screenshot()[150, 200], (255, 0, 0))
    body.set_opacity(0.5)
    blended = renderer.screenshot()[150, 200]
    assert 100 < blended[0] < 200 and blended[1] < 30, (
        "halb durchsichtig mischt mit dem Hintergrund"
    )
    body.set_visible(False)
    assert not body.visible()
    assert same(renderer.screenshot()[150, 200], BACKGROUND_RGB)
    body.set_visible(True)
    renderer.remove(body)
    assert same(renderer.screenshot()[150, 200], BACKGROUND_RGB)


def test_display_coordinates_count_like_qt_from_the_top_left(renderer: Renderer) -> None:
    """Ein Punkt, der in der Welt oben liegt, hat im Bild die kleinere y-Zahl —
    Qt-Zählung, nicht VTKs. Und der Weg zurück trifft denselben Weltpunkt."""
    vertices, faces = plate(z=0.0)
    body = renderer.add_surface(vertices, faces, name="plate", style=SurfaceStyle())
    look_down(renderer, body.bounds())
    renderer.render()
    high_x, high_y, high_depth = renderer.world_to_display((20.0, 35.0, 0.0))
    low_x, low_y, _low_depth = renderer.world_to_display((20.0, 5.0, 0.0))
    assert high_y < low_y, "y wächst nach unten"
    assert abs(high_x - low_x) < 1e-6
    width, height = renderer.view_size()
    assert (width, height) == SIZE
    assert 0 <= high_y < height and 0 <= high_x < width
    back = renderer.display_to_world(high_x, high_y, high_depth)
    assert back is not None and np.allclose(back, (20.0, 35.0, 0.0), atol=1e-3)
    assert 0.0 < renderer.focal_depth() < 1.0


def test_the_image_is_stored_top_down(renderer: Renderer) -> None:
    """Eine Platte in der oberen Bildhälfte liegt in den ersten Zeilen des
    Feldes — VTK legt sein Bild von unten ab, das Bild hier beginnt oben."""
    vertices, faces = plate(z=0.0)
    renderer.add_surface(
        vertices, faces, name="plate", style=SurfaceStyle(colour="#ffffff", lighting=False)
    )
    # Blick von oben, Bild-Oben zeigt nach +y; die Kamera steht über y = 60,
    # also liegt die Platte (0..40) in der unteren Bildhälfte.
    renderer.set_camera_pose(CameraPose((20.0, 60.0, 200.0), (20.0, 60.0, 0.0), (0.0, 1.0, 0.0)))
    renderer.set_parallel_projection(True)
    renderer.set_parallel_scale(60.0)
    image = renderer.screenshot()
    upper = bright(image[: SIZE[1] // 2]).sum()
    lower = bright(image[SIZE[1] // 2 :]).sum()
    assert lower > 0 and upper == 0, (upper, lower)


def test_cell_colours_categorical_and_mapped(renderer: Renderer) -> None:
    vertices, faces = plate(z=0.0)
    slots = renderer.add_surface(
        vertices,
        faces,
        name="slots",
        style=SurfaceStyle(colour="#ffffff", lighting=False),
        cell_colours=CellColours(
            np.array([0, 1]), colormap=("#00ff00", "#0000ff"), limits=(0, 1), categorical=True
        ),
    )
    look_down(renderer, slots.bounds())
    image = renderer.screenshot()
    # Dreieck 0 liegt unten rechts (0,0)-(40,0)-(40,40), Dreieck 1 oben links.
    lower_right = image[int(SIZE[1] * 0.6), int(SIZE[0] * 0.6)]
    upper_left = image[int(SIZE[1] * 0.4), int(SIZE[0] * 0.4)]
    assert same(lower_right, (0, 255, 0))
    assert same(upper_left, (0, 0, 255))
    renderer.remove(slots)

    graded = renderer.add_surface(
        vertices,
        faces,
        name="map",
        style=SurfaceStyle(colour="#ffffff", lighting=False),
        cell_colours=CellColours(
            np.array([0.0, 1.0]), colormap=("#000000", "#ffffff"), limits=(0.0, 1.0)
        ),
    )
    look_down(renderer, graded.bounds())
    image = renderer.screenshot()
    assert same(image[int(SIZE[1] * 0.6), int(SIZE[0] * 0.6)], (0, 0, 0))
    assert same(image[int(SIZE[1] * 0.4), int(SIZE[0] * 0.4)], (255, 255, 255))
    renderer.remove(graded)

    direct = renderer.add_surface(
        vertices,
        faces,
        name="rgb",
        style=SurfaceStyle(colour="#ffffff", lighting=False),
        cell_colours=CellColours(np.array([[1.0, 0.0, 0.0], [1.0, 1.0, 0.0]])),
    )
    look_down(renderer, direct.bounds())
    image = renderer.screenshot()
    assert same(image[int(SIZE[1] * 0.6), int(SIZE[0] * 0.6)], (255, 0, 0))
    assert same(image[int(SIZE[1] * 0.4), int(SIZE[0] * 0.4)], (255, 255, 0))


def test_labels_are_drawn_in_the_overlay_and_follow_their_anchors(renderer: Renderer) -> None:
    labels = renderer.add_labels(
        np.array([[20.0, 20.0, 42.0]]),
        ["Mitte"],
        name="labels",
        style=LabelStyle(text_colour="#ffffff", font_size=18, bold=True),
    )
    look_down(renderer, (0.0, 40.0, 0.0, 40.0, 30.0, 42.0))
    first = renderer.screenshot()
    assert bright(first).sum() > 50, "die Beschriftung zeichnet Text"
    first_centre = np.argwhere(bright(first)).mean(axis=0)
    labels.update_labels(np.array([[5.0, 5.0, 42.0]]), ["Ecke"])
    second = renderer.screenshot()
    second_centre = np.argwhere(bright(second)).mean(axis=0)
    assert second_centre[0] > first_centre[0] + 30, "unten links im Bild heißt größeres y"
    assert second_centre[1] < first_centre[1] - 30
    labels.set_visible(False)
    assert bright(renderer.screenshot()).sum() == 0


def test_a_line_kept_in_front_stays_visible_inside_a_body(renderer: Renderer) -> None:
    """Ein Maß läuft durch das Material — und war dort weg (Robert,
    03.09.2026). ``keep_in_front`` holt es nach vorn, ohne den Körper zu
    verändern."""
    vertices, faces = cube()
    renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle(colour="#404040"))
    look_down(renderer, (0.0, 20.0, 0.0, 20.0, 0.0, 20.0))
    hidden = renderer.add_lines(
        np.array([[0.0, 10.0, 10.0], [20.0, 10.0, 10.0]]), name="inside", colour="#ffff00", width=4
    )
    image = renderer.screenshot()
    x, y, _depth = renderer.world_to_display((10.0, 10.0, 10.0))
    without = image[round(y), round(x)]
    assert without[2] < 100 and not (without[0] > 200 and without[1] > 200), "im Material verdeckt"
    renderer.remove(hidden)
    renderer.add_lines(
        np.array([[0.0, 10.0, 10.0], [20.0, 10.0, 10.0]]),
        name="front",
        colour="#ffff00",
        width=4,
        keep_in_front=True,
    )
    with_front = renderer.screenshot()[round(y), round(x)]
    assert with_front[0] > 200 and with_front[1] > 200 and with_front[2] < 80, with_front


def test_points_are_drawn_as_dots_of_screen_size(renderer: Renderer) -> None:
    dots = renderer.add_points(
        np.array([[20.0, 20.0, 0.0]]), name="dots", colour="#ff00ff", size=12.0
    )
    look_down(renderer, (0.0, 40.0, 0.0, 40.0, 0.0, 1.0))
    mask = bright(renderer.screenshot())
    assert 30 < mask.sum() < 400, "ein Punkt von zwölf Bildpunkten Durchmesser"
    dots.set_colour("#00ff00")
    image = renderer.screenshot()
    x, y, _depth = renderer.world_to_display((20.0, 20.0, 0.0))
    assert same(image[round(y), round(x)], (0, 255, 0))


def test_translucent_bodies_blend_the_same_whichever_order_they_were_added(
    renderer: Renderer,
) -> None:
    """Zwei durchscheinende Körper hintereinander mischen sich reihenfolge-
    unabhängig — gemessen an VTK 9.6.2, ohne Fenster wie mit PyVista.

    Der Viewport hängt seine Aktoren bis heute von hinten nach vorn um
    (``_order_by_depth``), weil ein Bild vom 03.09.2026 an der Einfüge-
    reihenfolge hing. Dieser Test hält fest, was der Renderer hier tut: Beide
    Reihenfolgen ergeben dasselbe Bild, und beide Körper sind darin — Rot wie
    Blau tragen bei. Ändert eine VTK-Fassung das, wird er rot, und dann
    braucht der Viewport seine Umhängung wieder.
    """
    base, faces = cube()
    near = renderer.add_surface(
        base + np.array([0.0, -40.0, 0.0]),
        faces,
        name="near",
        style=SurfaceStyle(colour="#0000ff", opacity=0.45),
    )
    far = renderer.add_surface(
        base + np.array([0.0, 40.0, 0.0]),
        faces,
        name="far",
        style=SurfaceStyle(colour="#ff0000", opacity=0.45),
    )
    renderer.set_camera_pose(CameraPose((10.0, -200.0, 10.0), (10.0, 0.0, 10.0), (0.0, 0.0, 1.0)))
    renderer.reset_camera((0.0, 20.0, -40.0, 60.0, 0.0, 20.0))
    renderer.set_draw_order([near, far])
    first = renderer.screenshot()
    renderer.set_draw_order([far, near])
    second = renderer.screenshot()
    assert int((first != second).any(axis=2).sum()) == 0, "die Reihenfolge ändert nichts"
    # Die Reihenfolge selbst kommt trotzdem an — bei VTK als Reihenfolge der
    # Props; pygfx sortiert Durchscheinendes selbst von hinten nach vorn.
    if isinstance(renderer, VtkRenderer):
        props = list(renderer.renderer.GetViewProps())
        assert [props.index(item.actor) for item in (far, near)] == sorted(
            props.index(item.actor) for item in (far, near)
        )
    centre = first[150, 200].astype(int)
    assert centre[0] > 60 and centre[2] > 60 and centre[1] < 30, centre


def test_moving_a_body_moves_bounds_pick_and_pixels(renderer: Renderer) -> None:
    vertices, faces = cube()
    body = renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle())
    look_down(renderer, (-30.0, 50.0, -30.0, 50.0, 0.0, 20.0))
    renderer.render()
    before = body.bounds()
    body.set_position((30.0, 0.0, 0.0))
    assert body.position() == (30.0, 0.0, 0.0)
    after = body.bounds()
    assert after[0] == pytest.approx(before[0] + 30.0) and after[1] == pytest.approx(
        before[1] + 30.0
    )
    assert body.centre() == pytest.approx((40.0, 10.0, 10.0))
    assert body.length() == pytest.approx(np.sqrt(3.0) * 20.0)
    x, y, _depth = renderer.world_to_display((10.0, 10.0, 20.0))
    assert renderer.pick_surface(x, y) is None, "wo der Körper war, ist nichts mehr"
    x, y, _depth = renderer.world_to_display((40.0, 10.0, 20.0))
    hit = renderer.pick_surface(x, y)
    assert hit is not None and hit.item is body

    body.set_position((0.0, 0.0, 0.0))
    matrix = np.eye(4)
    matrix[:3, 3] = (0.0, 25.0, 0.0)
    body.set_matrix(matrix)
    assert np.allclose(body.matrix(), matrix)
    assert body.centre() == pytest.approx((10.0, 35.0, 10.0))

    body.set_matrix(np.eye(4))
    body.update_points(vertices + np.array([0.0, 0.0, 5.0]))
    assert body.bounds()[4] == pytest.approx(5.0) and body.bounds()[5] == pytest.approx(25.0)
    with pytest.raises(ValueError):
        body.update_points(vertices[:4])


def test_camera_pose_projection_and_dolly(renderer: Renderer) -> None:
    vertices, faces = cube()
    body = renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle())
    pose = CameraPose((100.0, -100.0, 80.0), (10.0, 10.0, 10.0), (0.0, 0.0, 1.0))
    renderer.set_camera_pose(pose)
    read = renderer.camera_pose()
    assert read.position == pytest.approx(pose.position)
    assert read.focal_point == pytest.approx(pose.focal_point)
    assert np.dot(read.view_up, (0.0, 0.0, 1.0)) > 0.5
    assert not renderer.parallel_projection()
    assert renderer.view_angle() > 0.0
    distance_before = np.linalg.norm(np.subtract(read.position, read.focal_point))
    renderer.dolly(2.0)
    after = renderer.camera_pose()
    distance_after = np.linalg.norm(np.subtract(after.position, after.focal_point))
    assert distance_after == pytest.approx(distance_before / 2.0)

    renderer.set_parallel_projection(True)
    assert renderer.parallel_projection()
    renderer.set_parallel_scale(50.0)
    renderer.dolly(2.0)
    assert renderer.parallel_scale() == pytest.approx(25.0)
    renderer.reset_camera(body.bounds())
    renderer.reset_clipping_range()
    assert renderer.parallel_scale() > 0.0


def test_quality_switches_and_the_axes_marker_survive_without_a_window(
    renderer: Renderer,
) -> None:
    """FXAA und SSAO laufen ohne Fenster durch; das Achsenkreuz braucht einen
    Interactor und bleibt ohne Fenster still — kein Absturz, kein Bild."""
    vertices, faces = cube()
    renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle())
    look_down(renderer, (0.0, 20.0, 0.0, 20.0, 0.0, 20.0))
    plain = renderer.screenshot()
    renderer.set_anti_aliasing(True)
    renderer.set_ambient_occlusion(True, radius=5.0, bias=0.05)
    styled = renderer.screenshot()
    assert styled.shape == plain.shape
    renderer.set_ambient_occlusion(False, radius=5.0, bias=0.05)
    renderer.set_axes_marker(AxesMarkerStyle())
    renderer.place_axes_marker((0.0, 0.0, 0.2, 0.2))
    renderer.set_axes_marker(None)
    assert renderer.screenshot().shape == plain.shape


def test_colours_travel_as_hex_in_both_directions() -> None:
    assert rgb("#ff8000") == pytest.approx((1.0, 128 / 255, 0.0))
    assert rgb("#fff") == (1.0, 1.0, 1.0)
    assert hex_of((1.0, 0.5, 0.0)) == "#ff8000"
    assert hex_of((2.0, -1.0, 0.25)) == "#ff0040"
    with pytest.raises(ValueError):
        rgb("white")
    with pytest.raises(ValueError):
        rgb("#12345")


@pytest.mark.parametrize("backend", BACKENDS)
def test_labels_render_in_a_fresh_interpreter(backend: str) -> None:
    """Beschriftungen zeichnen auch in einem Interpreter, der nur den Renderer
    holt — so, wie die Anwendung ohne PyVista starten wird.

    In der Suite hat irgendein Import davor die Schriftmaschine längst
    geladen; hier lädt sie nur, was der Renderer selbst mitbringt.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    module, name = {
        "vtk": ("vtk_renderer", "VtkRenderer"),
        "gfx": ("gfx_renderer", "GfxRenderer"),
    }[backend]
    script = "\n".join(
        [
            "import numpy as np",
            "from app.ui.render.api import CameraPose, LabelStyle",
            f"from app.ui.render.{module} import {name}",
            f"view = {name}(offscreen=True, size=(200, 150))",
            "view.set_background('#000000')",
            "view.add_labels(np.array([[0.0, 0.0, 0.0]]), ['Mitte'], name='l', "
            "style=LabelStyle(font_size=18))",
            "view.set_camera_pose(CameraPose((0.0, 0.0, 100.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))",
            "print(int((view.screenshot().sum(axis=2) > 100).sum()))",
            "view.close()",
        ]
    )
    root = Path(__file__).resolve().parent.parent
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PYTHONPATH": str(root)},
    )
    assert done.returncode == 0, done.stderr[-800:]
    assert int(done.stdout.strip().splitlines()[-1]) > 50, done.stdout


def test_a_gradient_background_runs_from_bottom_to_top(renderer: Renderer) -> None:
    renderer.set_background("#000000", top="#ffffff")
    image = renderer.screenshot()
    assert image[5, 200].sum() > image[-6, 200].sum() + 300, "oben hell, unten dunkel"
    assert renderer.background() == "#000000", "gemeldet wird die untere Farbe"
    renderer.set_background(BACKGROUND)
    image = renderer.screenshot()
    assert same(image[5, 200], BACKGROUND_RGB) and tuple(image[-6, 200]) == BACKGROUND_RGB


def test_the_headlight_brightens_the_faces_that_look_at_the_camera(
    renderer: Renderer,
) -> None:
    """Das Frontlicht ist das eine Licht aus Kamerarichtung (`ansicht.md`,
    „Zwei Werte hängen am Thema"); seine Stärke muss im Bild ankommen —
    auch dann, wenn VTK es noch gar nicht angelegt hat."""
    vertices, faces = cube()
    renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle(colour="#b9c4d0"))
    renderer.set_camera_pose(CameraPose((60.0, -80.0, 50.0), (10.0, 10.0, 10.0), (0.0, 0.0, 1.0)))
    renderer.reset_camera((0.0, 20.0, 0.0, 20.0, 0.0, 20.0))
    renderer.set_headlight(0.2)
    dim = int(renderer.screenshot()[150, 200].sum())
    renderer.set_headlight(1.0)
    lit = int(renderer.screenshot()[150, 200].sum())
    assert lit > dim + 60, (dim, lit)


def test_polylines_chain_exactly_the_points_they_are_told_to(renderer: Renderer) -> None:
    """Eine Skizzenkurve ist eine Kette, ein Raster sind Paare — `polylines`
    sagt je Kette, wie viele Punkte sie hat, und dazwischen wird nichts
    verbunden."""
    points = np.array(
        [
            [0.0, 20.0, 0.0],
            [20.0, 20.0, 0.0],
            [20.0, 0.0, 0.0],
            [30.0, 40.0, 0.0],
            [40.0, 40.0, 0.0],
        ]
    )
    renderer.add_lines(points, name="chains", colour="#ffff00", width=4, polylines=[3, 2])
    look_down(renderer, (0.0, 40.0, 0.0, 40.0, 0.0, 1.0))
    image = renderer.screenshot()

    def lit(world: tuple[float, float, float]) -> bool:
        x, y, _depth = renderer.world_to_display(world)
        patch = image[round(y) - 2 : round(y) + 3, round(x) - 2 : round(x) + 3]
        return bool((patch[:, :, 0] > 200).any() and (patch[:, :, 1] > 200).any())

    assert lit((20.0, 10.0, 0.0)), "zweites Glied der Kette"
    assert lit((35.0, 40.0, 0.0)), "das Paar dahinter"
    assert not lit((25.0, 20.0, 0.0)), "zwischen Kette und Paar liegt nichts"


def test_backfaces_take_their_own_colour_opacity_or_vanish(renderer: Renderer) -> None:
    """Eine Bohrungsmarkierung zeigt ihre Innenwand von beiden Öffnungen
    durchscheinend (`ansicht.md`); die Druckplatte wirft ihre Rückseite weg,
    damit man von unten hindurchsieht."""
    vertices, faces = plate(z=0.0)
    body = renderer.add_surface(
        vertices,
        faces,
        name="plate",
        style=SurfaceStyle(
            colour="#ffffff", lighting=False, backface_colour="#ff0000", backface_opacity=0.4
        ),
    )
    look_down(renderer, body.bounds())
    assert same(renderer.screenshot()[150, 200], (255, 255, 255)), "von oben die Vorderseite"
    renderer.set_camera_pose(CameraPose((20.0, 20.0, -200.0), (20.0, 20.0, 0.0), (0.0, 1.0, 0.0)))
    renderer.reset_camera(body.bounds())
    below = renderer.screenshot()[150, 200].astype(int)
    assert 60 < below[0] < 200 and below[1] < 40 and below[2] < 40, (
        f"von unten die Rückseite, halb durchscheinend: {below}"
    )
    renderer.remove(body)
    culled = renderer.add_surface(
        vertices,
        faces,
        name="bed",
        style=SurfaceStyle(colour="#ffffff", lighting=False, cull_backfaces=True),
    )
    renderer.reset_camera(culled.bounds())
    assert same(renderer.screenshot()[150, 200], BACKGROUND_RGB), "die Rückseite ist weg"


def test_a_label_background_grows_with_its_margin(renderer: Renderer) -> None:
    def red_area(margin: int) -> int:
        labels = renderer.add_labels(
            np.array([[20.0, 20.0, 0.0]]),
            ["Maß"],
            name="label",
            style=LabelStyle(
                text_colour="#ffffff", font_size=14, background="#ff0000", margin=margin
            ),
        )
        look_down(renderer, (0.0, 40.0, 0.0, 40.0, 0.0, 1.0))
        image = renderer.screenshot()
        renderer.remove(labels)
        return int(((image[:, :, 0] > 200) & (image[:, :, 1] < 80) & (image[:, :, 2] < 80)).sum())

    tight = red_area(0)
    wide = red_area(8)
    assert tight > 0, "der Kasten zeichnet"
    assert wide > tight * 1.3, (tight, wide)


def test_what_is_drawn_in_front_is_picked_in_front(renderer: Renderer) -> None:
    """Der Skalierwürfel an einem würfelförmigen Körper liegt in dessen
    Hüllquader; ``keep_in_front`` zeichnet ihn davor, und der Zeiger muss ihn
    dort auch finden — der Zell-Picker allein sähe zuerst die Körperfläche."""
    vertices, faces = cube()
    body = renderer.add_surface(vertices, faces, name="body", style=SurfaceStyle())
    inside_vertices, inside_faces = plate(z=15.0, size=4.0)
    inside_vertices += np.array([8.0, 8.0, 0.0])
    grip = renderer.add_surface(
        inside_vertices,
        inside_faces,
        name="grip",
        style=SurfaceStyle(colour="#00c0ff", lighting=False, keep_in_front=True),
    )
    look_down(renderer, (0.0, 20.0, 0.0, 20.0, 0.0, 20.0))
    renderer.render()
    x, y, _depth = renderer.world_to_display((10.0, 10.0, 15.0))
    assert same(renderer.screenshot()[round(y), round(x)], (0, 192, 255)), "im Bild vorn"
    assert renderer.pick_item(x, y) is grip, "und deshalb auch beim Picken vorn"
    grip.set_visible(False)
    assert renderer.pick_item(x, y) is body
    grip.set_visible(True)
    renderer.remove(grip)
    plain = renderer.add_surface(
        inside_vertices, inside_faces, name="plain", style=SurfaceStyle(colour="#00c0ff")
    )
    renderer.render()
    assert renderer.pick_item(x, y) is body, "ohne keep_in_front gewinnt die Fläche davor"
    assert plain is not None
