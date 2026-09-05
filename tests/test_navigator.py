"""Die Kameraführung ohne Renderer: Gesten hinein, Kamera und Rückrufe heraus.

Der Navigator ersetzt den VTK-Interaktionsstil der 3D-Ansicht. Was er tut,
lässt sich ohne Fenster prüfen — mit einem Renderer-Doppel, das nur die
Kamera und eine einfache Parallelprojektion kennt. Jeder Test hier stellt
eine Zusage, die vorher hinter einer Wache lag, die offscreen nie fiel.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pytest

from app.ui.render.api import (
    AxesMarkerStyle,
    Bounds,
    CameraPose,
    CellColours,
    Colour,
    Item,
    LabelsItem,
    LabelStyle,
    Pick,
    PointerEvent,
    Renderer,
    SurfaceStyle,
)
from app.ui.render.navigator import (
    CLICK_SLACK,
    DOLLY_BASE,
    DOLLY_MOTION_FACTOR,
    WHEEL_STEP,
    Navigator,
    NavigatorCallbacks,
    is_click,
    navigation_action,
    turntable_camera,
)

SIZE = (400, 300)


class _FlatRenderer(Renderer):
    """Ein Renderer-Doppel mit Kamera und Parallelprojektion, sonst nichts.

    Die Projektion ist absichtlich einfach: Bild-x läuft entlang „rechts“
    (Blickrichtung mal Oben), Bild-y entlang Oben nach unten, die Skala
    kommt aus ``parallel_scale`` wie bei VTK (halbe Bildhöhe in Weltmaß).
    """

    def __init__(self) -> None:
        self.widget = None
        self.pose = CameraPose((0.0, -100.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        self.scale = 50.0
        self.parallel = True
        self.renders = 0

    # Inhalt — hier nicht gebraucht.
    def add_surface(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        name: str,
        style: SurfaceStyle,
        cell_colours: CellColours | None = None,
    ) -> Item:
        raise NotImplementedError

    def add_lines(
        self,
        points: np.ndarray,
        *,
        name: str,
        colour: Colour,
        width: float = 2.0,
        pickable: bool = False,
        keep_in_front: bool = False,
        connected: bool = False,
    ) -> Item:
        raise NotImplementedError

    def add_points(
        self,
        points: np.ndarray,
        *,
        name: str,
        colour: Colour,
        size: float = 8.0,
        pickable: bool = False,
        keep_in_front: bool = False,
    ) -> Item:
        raise NotImplementedError

    def add_labels(
        self, points: np.ndarray, texts: Sequence[str], *, name: str, style: LabelStyle
    ) -> LabelsItem:
        raise NotImplementedError

    def remove(self, item: Item) -> None:
        raise NotImplementedError

    def set_draw_order(self, items: Sequence[Item]) -> None:
        raise NotImplementedError

    # Kamera
    def camera_pose(self) -> CameraPose:
        return self.pose

    def set_camera_pose(self, pose: CameraPose) -> None:
        self.pose = pose

    def parallel_projection(self) -> bool:
        return self.parallel

    def set_parallel_projection(self, parallel: bool) -> None:
        self.parallel = parallel

    def parallel_scale(self) -> float:
        return self.scale

    def set_parallel_scale(self, scale: float) -> None:
        self.scale = scale

    def view_angle(self) -> float:
        return 30.0

    def dolly(self, factor: float) -> None:
        if self.parallel:
            self.scale /= factor
            return
        position = np.asarray(self.pose.position)
        focal = np.asarray(self.pose.focal_point)
        moved = focal + (position - focal) / factor
        self.pose = CameraPose(
            tuple(float(v) for v in moved), self.pose.focal_point, self.pose.view_up
        )  # type: ignore[arg-type]

    def reset_camera(self, bounds: Bounds | None = None) -> None:
        return

    def reset_clipping_range(self) -> None:
        return

    def view_size(self) -> tuple[int, int]:
        return SIZE

    def _frame(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        forward = np.asarray(self.pose.focal_point) - np.asarray(self.pose.position)
        forward = forward / np.linalg.norm(forward)
        up = np.asarray(self.pose.view_up, dtype=float)
        right = np.cross(forward, up)
        right = right / np.linalg.norm(right)
        up = np.cross(right, forward)
        return forward, right, up

    def world_to_display(self, point: tuple[float, float, float]) -> tuple[float, float, float]:
        _forward, right, up = self._frame()
        offset = np.asarray(point) - np.asarray(self.pose.focal_point)
        per_pixel = 2.0 * self.scale / SIZE[1]
        x = SIZE[0] / 2.0 + float(np.dot(offset, right)) / per_pixel
        y = SIZE[1] / 2.0 - float(np.dot(offset, up)) / per_pixel
        return (x, y, 0.5)

    def display_to_world(
        self, x: float, y: float, depth: float
    ) -> tuple[float, float, float] | None:
        _forward, right, up = self._frame()
        per_pixel = 2.0 * self.scale / SIZE[1]
        point = (
            np.asarray(self.pose.focal_point)
            + right * (x - SIZE[0] / 2.0) * per_pixel
            + up * (SIZE[1] / 2.0 - y) * per_pixel
        )
        return (float(point[0]), float(point[1]), float(point[2]))

    def pick_surface(
        self, x: float, y: float, *, among: Sequence[Item] | None = None, tolerance: float = 0.005
    ) -> Pick | None:
        return None

    def pick_item(self, x: float, y: float) -> Item | None:
        return None

    def render(self) -> None:
        self.renders += 1

    def screenshot(self) -> np.ndarray:
        return np.zeros((SIZE[1], SIZE[0], 3), dtype=np.uint8)

    def set_background(self, colour: Colour) -> None:
        return

    def background(self) -> Colour:
        return "#000000"

    def set_anti_aliasing(self, enabled: bool) -> None:
        return

    def set_ambient_occlusion(self, enabled: bool, *, radius: float, bias: float) -> None:
        return

    def set_axes_marker(self, style: AxesMarkerStyle | None) -> None:
        return

    def place_axes_marker(self, corner: tuple[float, float, float, float]) -> None:
        return

    def add_pointer_listener(self, listener: Callable[[PointerEvent], None]) -> int:
        return 1

    def remove_pointer_listener(self, token: int) -> None:
        return

    def close(self) -> None:
        return


class _Log:
    """Zeichnet jeden Rückruf auf — so viel, wie der Test fragen will."""

    def __init__(self, *, sculpting: bool = False, body: bool = False) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.sculpting = sculpting
        self.body = body

    def callbacks(self) -> NavigatorCallbacks:
        return NavigatorCallbacks(
            on_context=lambda x, y: self.calls.append(("context", x, y)),
            on_pick=lambda x, y: self.calls.append(("pick", x, y)),
            on_cursor=lambda role: self.calls.append(("cursor", role)),
            on_paint=lambda x, y, fresh: self.calls.append(("paint", x, y, fresh)),
            is_sculpting=lambda: self.sculpting,
            on_body_drag=self._body_drag,
            on_rotate_start=lambda: self.calls.append(("rotate_start",)),
            on_camera=lambda: self.calls.append(("camera",)),
            on_tilt=lambda step: self.calls.append(("tilt", step)),
            on_end=lambda: self.calls.append(("end",)),
        )

    def _body_drag(self, phase: str, x: int, y: int) -> bool:
        self.calls.append(("body", phase, x, y))
        return self.body

    def kinds(self) -> list[str]:
        return [str(call[0]) for call in self.calls]


def press(x: int, y: int, button: str = "left", shift: bool = False) -> PointerEvent:
    return PointerEvent("press", x, y, button, frozenset([button]), shift)  # type: ignore[arg-type]


def move(x: int, y: int, button: str = "left", shift: bool = False) -> PointerEvent:
    return PointerEvent("move", x, y, None, frozenset([button]), shift)  # type: ignore[arg-type]


def release(x: int, y: int, button: str = "left", shift: bool = False) -> PointerEvent:
    return PointerEvent("release", x, y, button, frozenset(), shift)  # type: ignore[arg-type]


def wheel(x: int, y: int, delta: int) -> PointerEvent:
    return PointerEvent("wheel", x, y, delta=delta)


@pytest.fixture
def scene() -> tuple[_FlatRenderer, _Log]:
    return _FlatRenderer(), _Log()


def test_the_table_says_what_each_button_does() -> None:
    assert navigation_action("solidon", "left", False) == "pan"
    assert navigation_action("solidon", "right", False) == "rotate"
    assert navigation_action("solidon", "middle", False) == "tilt"
    assert navigation_action("slicer", "left", False) == "select"
    assert navigation_action("slicer", "left", True) == "pan"
    assert navigation_action("cad", "right", False) == "zoom"
    assert navigation_action("orbit", "left", False) == "rotate"
    assert is_click((10, 10), (10 + CLICK_SLACK, 10))
    assert not is_click((10, 10), (10 + CLICK_SLACK + 1, 10))
    assert not is_click(None, (10, 10))


def test_a_click_picks_and_a_drag_does_not(scene: tuple[_FlatRenderer, _Log]) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "slicer", log.callbacks())
    navigator.handle(press(100, 100))
    navigator.handle(move(103, 102))
    navigator.handle(release(103, 102))
    assert ("pick", 103, 102) in log.calls
    log.calls.clear()
    navigator.handle(press(100, 100))
    navigator.handle(move(140, 100))
    navigator.handle(release(140, 100))
    assert "pick" not in log.kinds(), "ein Zug wählt nicht"
    assert renderer.pose.focal_point == (0.0, 0.0, 0.0), "links wählt im Slicer-Schema nur"


def test_left_pans_and_still_selects_in_the_solidon_scheme(
    scene: tuple[_FlatRenderer, _Log],
) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "solidon", log.callbacks())
    navigator.handle(press(200, 150))
    navigator.handle(release(200, 150))
    assert ("pick", 200, 150) in log.calls
    assert renderer.pose.focal_point == (0.0, 0.0, 0.0)
    log.calls.clear()

    navigator.handle(press(200, 150))
    navigator.handle(move(250, 150))
    navigator.handle(release(250, 150))
    # 50 Bildpunkte nach rechts: Der Weltpunkt unter dem Zeiger bleibt unter
    # dem Zeiger, also wandert die Kamera nach links — um 50 mal die
    # Weltbreite eines Bildpunkts (2 * 50 / 300 mm).
    per_pixel = 2.0 * 50.0 / SIZE[1]
    assert renderer.pose.focal_point[0] == pytest.approx(-50 * per_pixel)
    assert renderer.pose.position[0] == pytest.approx(-50 * per_pixel)
    assert renderer.pose.position[1] == pytest.approx(-100.0)
    assert "pick" not in log.kinds()
    assert log.kinds().count("end") == 1
    assert [call for call in log.calls if call[0] == "cursor"] == [
        ("cursor", "panning"),
        ("cursor", None),
    ]
    assert renderer.renders >= 1


def test_the_turntable_keeps_the_view_upright(scene: tuple[_FlatRenderer, _Log]) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "solidon", log.callbacks())
    navigator.handle(press(200, 150, "right"))
    for step in range(1, 11):
        navigator.handle(move(200 + 12 * step, 150 - 6 * step, "right"))
    navigator.handle(release(320, 90, "right"))
    up = np.asarray(renderer.pose.view_up)
    forward = np.asarray(renderer.pose.focal_point) - np.asarray(renderer.pose.position)
    # Kein Rollen: Das Oben bleibt in der Ebene aus Welt-Hochachse und Blick.
    sideways = np.cross(forward, (0.0, 0.0, 1.0))
    assert abs(float(np.dot(up, sideways))) < 1e-6
    assert float(np.linalg.norm(np.asarray(renderer.pose.position))) == pytest.approx(100.0)
    assert renderer.pose.focal_point == (0.0, 0.0, 0.0), "gedreht wird um den Blickpunkt"
    assert ("rotate_start",) in log.calls
    assert log.kinds().count("end") == 1
    assert "context" not in log.kinds(), "ein Zug öffnet kein Menü"


def test_turntable_camera_matches_the_direct_call(scene: tuple[_FlatRenderer, _Log]) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "orbit", log.callbacks())
    expected = turntable_camera((0.0, -100.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 40, 20, SIZE)
    navigator.handle(press(100, 100))
    # Qt zählt y nach unten: 20 Bildpunkte nach oben sind y - 20.
    navigator.handle(move(140, 80))
    navigator.handle(release(140, 80))
    assert renderer.pose.position == pytest.approx(expected[0])
    assert renderer.pose.view_up == pytest.approx(expected[1])


def test_a_wheel_step_keeps_the_point_under_the_pointer(
    scene: tuple[_FlatRenderer, _Log],
) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "solidon", log.callbacks())
    before = renderer.display_to_world(320, 60, 0.5)
    navigator.handle(wheel(320, 60, 1))
    assert renderer.scale == pytest.approx(50.0 / (1.0 + WHEEL_STEP))
    after = renderer.display_to_world(320, 60, 0.5)
    assert after == pytest.approx(before, abs=1e-9)
    assert ("camera",) in log.calls
    navigator.handle(wheel(320, 60, -1))
    assert renderer.scale == pytest.approx(50.0)


def test_tilt_reports_steps_upwards_positive(scene: tuple[_FlatRenderer, _Log]) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "solidon", log.callbacks())
    navigator.handle(press(200, 150, "middle"))
    navigator.handle(move(200, 130, "middle"))
    navigator.handle(move(200, 135, "middle"))
    navigator.handle(release(200, 135, "middle"))
    assert [call for call in log.calls if call[0] == "tilt"] == [("tilt", 20), ("tilt", -5)]
    assert ("rotate_start",) in log.calls
    assert "end" not in log.kinds(), "das Kippen meldet sich je Schritt selbst"
    assert renderer.pose == CameraPose((0.0, -100.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def test_a_drag_on_the_chosen_body_moves_the_body_not_the_camera(
    scene: tuple[_FlatRenderer, _Log],
) -> None:
    renderer, log = scene
    log.body = True
    navigator = Navigator(renderer, "solidon", log.callbacks())
    navigator.handle(press(200, 150))
    assert log.calls == [("body", "ready", 200, 150)]
    navigator.handle(move(204, 152))
    assert len(log.calls) == 1, "innerhalb der Klickschwelle beginnt kein Zug"
    navigator.handle(move(230, 150))
    assert log.calls[1] == ("body", "start", 200, 150), "gestartet wird von der Stelle des Drückens"
    assert log.calls[2] == ("body", "move", 230, 150)
    navigator.handle(release(230, 150))
    assert log.calls[-1] == ("body", "end", 230, 150)
    assert "pick" not in log.kinds()
    assert renderer.pose.focal_point == (0.0, 0.0, 0.0), "die Kamera blieb stehen"


def test_a_click_on_the_chosen_body_still_picks(scene: tuple[_FlatRenderer, _Log]) -> None:
    renderer, log = scene
    log.body = True
    navigator = Navigator(renderer, "solidon", log.callbacks())
    navigator.handle(press(200, 150))
    navigator.handle(release(202, 151))
    assert ("pick", 202, 151) in log.calls
    assert "start" not in [call[1] for call in log.calls if call[0] == "body"]


def test_painting_takes_the_left_button_while_sculpting(
    scene: tuple[_FlatRenderer, _Log],
) -> None:
    renderer, log = scene
    log.sculpting = True
    navigator = Navigator(renderer, "solidon", log.callbacks())
    navigator.handle(press(100, 100))
    navigator.handle(move(110, 100))
    navigator.handle(release(110, 100))
    assert [call for call in log.calls if call[0] == "paint"] == [
        ("paint", 100, 100, True),
        ("paint", 110, 100, False),
    ]
    assert "pick" not in log.kinds(), "der Klickpfad malte denselben Punkt ein zweites Mal"
    assert renderer.pose.focal_point == (0.0, 0.0, 0.0)
    log.calls.clear()
    navigator.handle(press(100, 100, shift=True))
    navigator.handle(move(150, 100, shift=True))
    navigator.handle(release(150, 100, shift=True))
    assert "paint" not in log.kinds(), "Umschalt behält die Kamera"
    assert renderer.pose.focal_point[0] != 0.0


def test_a_right_click_opens_the_menu_only_without_a_drag(
    scene: tuple[_FlatRenderer, _Log],
) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "slicer", log.callbacks())
    navigator.handle(press(120, 80, "right"))
    navigator.handle(release(121, 80, "right"))
    assert ("context", 121, 80) in log.calls
    log.calls.clear()
    navigator.handle(press(120, 80, "right"))
    navigator.handle(move(170, 80, "right"))
    navigator.handle(release(170, 80, "right"))
    assert "context" not in log.kinds()
    assert ("end",) in log.calls


def test_dragging_with_the_zoom_button_zooms_like_the_trackball(
    scene: tuple[_FlatRenderer, _Log],
) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "cad", log.callbacks())
    navigator.handle(press(200, 150, "right"))
    navigator.handle(move(200, 75, "right"))
    navigator.handle(release(200, 75, "right"))
    expected = DOLLY_BASE ** (DOLLY_MOTION_FACTOR * 75.0 / (SIZE[1] / 2.0))
    assert renderer.scale == pytest.approx(50.0 / expected)
    assert [call for call in log.calls if call[0] == "cursor"] == [
        ("cursor", "zoom"),
        ("cursor", None),
    ]


def test_a_scheme_switch_takes_effect_on_the_next_press(
    scene: tuple[_FlatRenderer, _Log],
) -> None:
    renderer, log = scene
    navigator = Navigator(renderer, "slicer", log.callbacks())
    assert navigator.scheme == "slicer"
    navigator.set_scheme("orbit")
    navigator.handle(press(200, 150))
    navigator.handle(move(240, 150))
    navigator.handle(release(240, 150))
    assert renderer.pose.position != (0.0, -100.0, 0.0), "im Orbit-Schema dreht links"
    assert ("rotate_start",) in log.calls
