"""Der VTK-Renderer hinter der 3D-Ansicht, gemessen am Bild (§18, §35).

Kein Fenster, keine Attrappe: Jeder Test baut den Renderer ohne Fenster auf,
stellt etwas hinein und liest Bildpunkte oder Picks zurück. Was hier grün
ist, hat VTK wirklich gezeichnet — die Fensterseite (Qt-Widget, Zeiger)
prüft ``test_ui.py`` am gebauten Fenster.
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
    SurfaceStyle,
    hex_of,
    rgb,
)
from app.ui.render.vtk_renderer import VtkRenderer

SIZE = (400, 300)
BACKGROUND = "#101418"
BACKGROUND_RGB = tuple(round(part * 255) for part in rgb(BACKGROUND))


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


@pytest.fixture
def renderer() -> Iterator[VtkRenderer]:
    view = VtkRenderer(offscreen=True, size=SIZE)
    view.set_background(BACKGROUND)
    try:
        yield view
    finally:
        view.close()


def look_down(view: VtkRenderer, bounds: tuple) -> None:
    """Die Kamera senkrecht von oben auf einen Quader, mit Qt-Oben nach +y."""
    centre = ((bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, bounds[5])
    view.set_camera_pose(
        CameraPose((centre[0], centre[1], centre[2] + 200.0), centre, (0.0, 1.0, 0.0))
    )
    view.reset_camera(bounds)


def test_a_surface_is_drawn_where_the_camera_looks_and_nowhere_else(
    renderer: VtkRenderer,
) -> None:
    vertices, faces = cube()
    body = renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle(colour="#b9c4d0"))
    renderer.set_camera_pose(CameraPose((60.0, -80.0, 50.0), (10.0, 10.0, 10.0), (0.0, 0.0, 1.0)))
    renderer.reset_camera(body.bounds())
    image = renderer.screenshot()
    assert image.shape == (SIZE[1], SIZE[0], 3) and image.dtype == np.uint8
    assert tuple(image[5, 5]) == BACKGROUND_RGB, "die Ecke zeigt den Hintergrund"
    assert image[150, 200].sum() > sum(BACKGROUND_RGB) + 60, "die Mitte zeigt den Körper"
    assert renderer.background() == BACKGROUND


def test_a_pick_in_the_middle_hits_the_body_and_a_pick_beside_it_hits_nothing(
    renderer: VtkRenderer,
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


def test_the_pick_list_decides_who_may_be_hit(renderer: VtkRenderer) -> None:
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


def test_visibility_colour_and_opacity_reach_the_pixels(renderer: VtkRenderer) -> None:
    vertices, faces = plate(z=0.0)
    body = renderer.add_surface(
        vertices, faces, name="plate", style=SurfaceStyle(colour="#ffffff", lighting=False)
    )
    look_down(renderer, body.bounds())
    assert tuple(renderer.screenshot()[150, 200]) == (255, 255, 255)
    body.set_colour("#ff0000")
    assert body.colour() == "#ff0000"
    assert tuple(renderer.screenshot()[150, 200]) == (255, 0, 0)
    body.set_opacity(0.5)
    blended = renderer.screenshot()[150, 200]
    assert 100 < blended[0] < 200 and blended[1] < 30, (
        "halb durchsichtig mischt mit dem Hintergrund"
    )
    body.set_visible(False)
    assert not body.visible()
    assert tuple(renderer.screenshot()[150, 200]) == BACKGROUND_RGB
    body.set_visible(True)
    renderer.remove(body)
    assert tuple(renderer.screenshot()[150, 200]) == BACKGROUND_RGB


def test_display_coordinates_count_like_qt_from_the_top_left(renderer: VtkRenderer) -> None:
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


def test_the_image_is_stored_top_down(renderer: VtkRenderer) -> None:
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


def test_cell_colours_categorical_and_mapped(renderer: VtkRenderer) -> None:
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
    assert tuple(lower_right) == (0, 255, 0)
    assert tuple(upper_left) == (0, 0, 255)
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
    assert tuple(image[int(SIZE[1] * 0.6), int(SIZE[0] * 0.6)]) == (0, 0, 0)
    assert tuple(image[int(SIZE[1] * 0.4), int(SIZE[0] * 0.4)]) == (255, 255, 255)
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
    assert tuple(image[int(SIZE[1] * 0.6), int(SIZE[0] * 0.6)]) == (255, 0, 0)
    assert tuple(image[int(SIZE[1] * 0.4), int(SIZE[0] * 0.4)]) == (255, 255, 0)


def test_labels_are_drawn_in_the_overlay_and_follow_their_anchors(renderer: VtkRenderer) -> None:
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


def test_a_line_kept_in_front_stays_visible_inside_a_body(renderer: VtkRenderer) -> None:
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


def test_points_are_drawn_as_dots_of_screen_size(renderer: VtkRenderer) -> None:
    dots = renderer.add_points(
        np.array([[20.0, 20.0, 0.0]]), name="dots", colour="#ff00ff", size=12.0
    )
    look_down(renderer, (0.0, 40.0, 0.0, 40.0, 0.0, 1.0))
    mask = bright(renderer.screenshot())
    assert 30 < mask.sum() < 400, "ein Punkt von zwölf Bildpunkten Durchmesser"
    dots.set_colour("#00ff00")
    image = renderer.screenshot()
    x, y, _depth = renderer.world_to_display((20.0, 20.0, 0.0))
    assert tuple(image[round(y), round(x)]) == (0, 255, 0)


def test_translucent_bodies_blend_the_same_whichever_order_they_were_added(
    renderer: VtkRenderer,
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
    # Die Reihenfolge selbst kommt trotzdem an — als Reihenfolge der Props.
    props = list(renderer.renderer.GetViewProps())
    assert [props.index(item.actor) for item in (far, near)] == sorted(
        props.index(item.actor) for item in (far, near)
    )
    centre = first[150, 200].astype(int)
    assert centre[0] > 60 and centre[2] > 60 and centre[1] < 30, centre


def test_moving_a_body_moves_bounds_pick_and_pixels(renderer: VtkRenderer) -> None:
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


def test_camera_pose_projection_and_dolly(renderer: VtkRenderer) -> None:
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
    renderer: VtkRenderer,
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


def test_labels_render_in_a_fresh_interpreter() -> None:
    """Beschriftungen zeichnen auch in einem Interpreter, der nur den Renderer
    holt — so, wie die Anwendung ohne PyVista starten wird.

    In der Suite hat irgendein Import davor die Schriftmaschine längst
    geladen; hier lädt sie nur, was der Renderer selbst mitbringt.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = "\n".join(
        [
            "import numpy as np",
            "from app.ui.render.api import CameraPose, LabelStyle",
            "from app.ui.render.vtk_renderer import VtkRenderer",
            "view = VtkRenderer(offscreen=True, size=(200, 150))",
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
