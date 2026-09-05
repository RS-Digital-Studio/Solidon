"""Der Bewegungsgriff am echten Renderer ohne Fenster (§18.11).

Keine Attrappe: Der Griff steht an einem Würfel im VTK-Renderer, die Gesten
kommen als Zeigerereignisse an den Bildpunkten, auf die der Renderer die
Pfeilspitzen und Ringe wirklich projiziert. Was der Zug bewegt, steht danach
in der Matrix des Körpers — und die ist gemessen, nicht behauptet.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest

from app.ui.render.api import CameraPose, PointerEvent, SurfaceStyle
from app.ui.render.gizmo import (
    AXIS_COLOURS,
    HIGHLIGHT,
    Gizmo,
    closest_axis_parameter,
    ray_plane_hit,
    rotation_matrix,
)
from app.ui.render.vtk_renderer import VtkRenderer
from tests.test_render_vtk import cube

SIZE = (600, 450)


@pytest.fixture
def scene() -> Iterator[tuple[VtkRenderer, object, Gizmo, list]]:
    renderer = VtkRenderer(offscreen=True, size=SIZE)
    renderer.set_background("#101418")
    vertices, faces = cube(20.0)
    body = renderer.add_surface(vertices, faces, name="cube", style=SurfaceStyle())
    # Schräg von oben, wie die Isometrie der Anwendung — alle drei Pfeile
    # zeigen in verschiedene Bildrichtungen.
    renderer.set_camera_pose(CameraPose((90.0, -110.0, 80.0), (10.0, 10.0, 10.0), (0.0, 0.0, 1.0)))
    renderer.reset_camera((-30.0, 50.0, -30.0, 50.0, -30.0, 50.0))
    renderer.render()
    releases: list[np.ndarray] = []
    gizmo = Gizmo(renderer, body, scale=0.4, release_callback=releases.append)
    renderer.render()
    try:
        yield renderer, body, gizmo, releases
    finally:
        gizmo.remove()
        renderer.close()


def press(x: float, y: float) -> PointerEvent:
    return PointerEvent("press", round(x), round(y), "left", frozenset(["left"]))


def move(x: float, y: float) -> PointerEvent:
    return PointerEvent("move", round(x), round(y), None, frozenset(["left"]))


def release(x: float, y: float) -> PointerEvent:
    return PointerEvent("release", round(x), round(y), "left", frozenset())


def hover(x: float, y: float) -> PointerEvent:
    return PointerEvent("move", round(x), round(y))


def arrow_tip_pixel(
    renderer: VtkRenderer, gizmo: Gizmo, axis: int, share: float = 0.7
) -> tuple[float, float]:
    """Der Bildpunkt eines Punkts auf dem Schaft der Achse ``axis``."""
    origin = np.asarray(gizmo.origin)
    point = origin + gizmo.axes[axis] * gizmo._arrow_length * share
    x, y, _depth = renderer.world_to_display((float(point[0]), float(point[1]), float(point[2])))
    return x, y


def test_the_ray_helpers_agree_with_geometry() -> None:
    assert closest_axis_parameter(
        (0.0, -10.0, 3.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)
    ) == pytest.approx(0.0)
    assert closest_axis_parameter(
        (5.0, -10.0, 3.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)
    ) == pytest.approx(5.0)
    assert (
        closest_axis_parameter((5.0, -10.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        is None
    )
    hit = ray_plane_hit((0.0, 0.0, 10.0), (0.0, 0.0, -1.0), (0.0, 0.0, 2.0), (0.0, 0.0, 1.0))
    assert hit is not None and np.allclose(hit, (0.0, 0.0, 2.0))
    assert (
        ray_plane_hit((0.0, 0.0, 10.0), (1.0, 0.0, 0.0), (0.0, 0.0, 2.0), (0.0, 0.0, 1.0)) is None
    )
    turned = rotation_matrix((0.0, 0.0, 1.0), (10.0, 0.0, 0.0), 90.0) @ np.array(
        [20.0, 0.0, 0.0, 1.0]
    )
    assert np.allclose(turned[:3], (10.0, 10.0, 0.0))


def test_hovering_an_arrow_highlights_it_and_nothing_else(scene: tuple) -> None:
    renderer, _body, gizmo, _releases = scene
    x, y = arrow_tip_pixel(renderer, gizmo, 2)
    gizmo.handle(hover(x, y))
    colours = [item.colour() for item in gizmo.items]
    assert colours[2] == HIGHLIGHT
    assert colours[0] == AXIS_COLOURS[0] and colours[1] == AXIS_COLOURS[1]
    gizmo.handle(hover(5, 5))
    assert [item.colour() for item in gizmo.items][2] == AXIS_COLOURS[2]


def test_dragging_an_arrow_moves_the_body_along_its_axis_only(scene: tuple) -> None:
    renderer, body, gizmo, releases = scene
    x, y = arrow_tip_pixel(renderer, gizmo, 2)
    gizmo.handle(hover(x, y))
    assert gizmo.handle(press(x, y)), "der Griff nimmt die Geste"
    # Weiter die z-Achse hinauf, im Bild also nach oben.
    far = np.asarray(gizmo.origin) + gizmo.axes[2] * gizmo._arrow_length * 1.5
    fx, fy, _depth = renderer.world_to_display((float(far[0]), float(far[1]), float(far[2])))
    assert gizmo.handle(move(fx, fy))
    matrix = body.matrix()
    shift = matrix[:3, 3]
    assert shift[2] > 5.0, shift
    assert abs(shift[0]) < 1e-6 and abs(shift[1]) < 1e-6, "nur entlang der Achse"
    assert np.allclose(matrix[:3, :3], np.eye(3))
    assert gizmo.handle(release(fx, fy))
    assert len(releases) == 1 and np.allclose(releases[0], matrix)
    assert not gizmo.pressing


def test_dragging_a_ring_turns_the_body_about_its_axis(scene: tuple) -> None:
    renderer, body, gizmo, releases = scene
    origin = np.asarray(gizmo.origin)
    # Ein Punkt auf dem z-Ring (in der xy-Ebene), ein zweiter um 60 Grad weiter.
    start = origin + np.array([gizmo._ring_radius, 0.0, 0.0])
    angle = np.radians(60.0)
    end = origin + np.array([np.cos(angle), np.sin(angle), 0.0]) * gizmo._ring_radius
    sx, sy, _d = renderer.world_to_display(tuple(float(v) for v in start))  # type: ignore[arg-type]
    ex, ey, _d = renderer.world_to_display(tuple(float(v) for v in end))  # type: ignore[arg-type]
    gizmo.handle(hover(sx, sy))
    assert gizmo._selected == ("ring", 2), gizmo._selected
    assert gizmo.handle(press(sx, sy))
    assert gizmo.handle(move(ex, ey))
    matrix = body.matrix()
    turned = matrix[:3, :3] @ np.array([1.0, 0.0, 0.0])
    measured = np.degrees(np.arctan2(turned[1], turned[0]))
    assert measured == pytest.approx(60.0, abs=2.0)
    assert np.allclose(matrix[:3, :3] @ np.array([0.0, 0.0, 1.0]), (0.0, 0.0, 1.0), atol=1e-6)
    # Gedreht um den Ursprung des Griffs: er bleibt, wo er war.
    assert np.allclose(matrix @ np.append(origin, 1.0), np.append(origin, 1.0), atol=1e-6)
    gizmo.handle(release(ex, ey))
    assert len(releases) == 1


def test_the_interact_callback_may_correct_the_matrix(scene: tuple) -> None:
    renderer, body, gizmo, _releases = scene
    gizmo.remove()
    seen: list[np.ndarray] = []

    def magnet(matrix: np.ndarray) -> np.ndarray:
        seen.append(matrix.copy())
        fixed = matrix.copy()
        fixed[:3, 3] = (0.0, 0.0, 7.0)
        return fixed

    gizmo = Gizmo(renderer, body, scale=0.4, interact_callback=magnet)
    x, y = arrow_tip_pixel(renderer, gizmo, 2)
    gizmo.handle(hover(x, y))
    gizmo.handle(press(x, y))
    gizmo.handle(move(x, y - 40))
    assert seen, "der Zwischenstand kam an"
    assert np.allclose(body.matrix()[:3, 3], (0.0, 0.0, 7.0)), "die berichtigte Matrix gilt"
    gizmo.handle(release(x, y - 40))
    gizmo.remove()


def test_a_press_beside_the_handles_belongs_to_nobody(scene: tuple) -> None:
    _renderer, body, gizmo, _releases = scene
    gizmo.handle(hover(5, 5))
    assert not gizmo.handle(press(5, 5))
    assert not gizmo.handle(move(50, 50))
    assert np.allclose(body.matrix(), np.eye(4))
    gizmo.remove()
    assert gizmo.items == ()
