"""Der Bewegungsgriff am echten Renderer ohne Fenster (§18.11).

Keine Attrappe: Der Griff steht an einem Würfel im pygfx-Renderer, die Gesten
kommen als Zeigerereignisse an den Bildpunkten, auf die der Renderer die
Pfeilspitzen und Ringe wirklich projiziert. Was der Zug bewegt, steht danach
in der Matrix des Körpers — und die ist gemessen, nicht behauptet.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest

from app.ui.render.api import CameraPose, PointerEvent, Renderer, SurfaceStyle
from app.ui.render.gizmo import (
    AXIS_COLOURS,
    HIGHLIGHT,
    Gizmo,
    closest_axis_parameter,
    normal_frame,
    ray_plane_hit,
    rotation_matrix,
)
from tests.helpers import cube_surface as cube
from tests.test_render_contract import make_renderer

SIZE = (600, 450)


@pytest.fixture
def scene(require_graphics_adapter: None) -> Iterator[tuple[Renderer, object, Gizmo, list]]:
    renderer = make_renderer(SIZE)
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
    renderer: Renderer, gizmo: Gizmo, axis: int, share: float = 0.7
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


@pytest.mark.parametrize("kind", ["gizmo", "scale", "slot"])
def test_leaving_a_handle_removes_the_highlight_from_the_drawn_frame(
    scene: tuple, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leave zeichnet den geänderten Griff sofort; der Test fordert kein Bild an."""
    from app.ui.scale_widget import ScaleHandle
    from app.ui.slot_handle import SlotHandle

    renderer, body, gizmo, _releases = scene
    handle = gizmo
    if kind == "gizmo":
        x, y = arrow_tip_pixel(renderer, gizmo, 2)
    else:
        gizmo.remove()
        if kind == "scale":
            handle = ScaleHandle(
                renderer, body, scale=0.4, colour="#00c0ff", release_callback=lambda factor: None
            )
            point = handle.grip_position
        else:
            handle = SlotHandle(
                renderer,
                centre=(10.0, 10.0, 20.0),
                axis=(0.0, 0.0, 1.0),
                diameter=6.0,
                length=10.0,
                angle=0.0,
                knob_size=5.0,
                colour="#ff9f1c",
                release_callback=lambda length, angle: None,
            )
            point = handle.knobs[0].centre()
        x, y, _depth = renderer.world_to_display(point)
    renderer.render()
    plain = np.asarray(renderer._renderer.snapshot()).copy()
    draws: list[bool] = []
    real_render = renderer.render

    def render() -> None:
        draws.append(True)
        real_render()

    monkeypatch.setattr(renderer, "render", render)
    try:
        handle.handle(hover(x, y))
        highlighted = np.asarray(renderer._renderer.snapshot()).copy()
        assert not np.array_equal(plain, highlighted), "the pointer must reach the handle"
        count = len(draws)
        handle.handle(PointerEvent("leave", 0, 0))
        cleared = np.asarray(renderer._renderer.snapshot()).copy()
        assert np.array_equal(plain, cleared), "the last drawn frame still shows the highlight"
        assert len(draws) == count + 1
        handle.handle(PointerEvent("leave", 0, 0))
        assert len(draws) == count + 1, "an unchanged handle needs no further frame"
        handle.handle(hover(x, y))
        assert handle.handle(press(x, y))
        count = len(draws)
        handle.handle(PointerEvent("leave", 0, 0))
        assert handle.pressing, "leaving the canvas must not interrupt a drag"
        assert len(draws) == count
    finally:
        handle.remove()


@pytest.mark.parametrize("rotation", [True, False])
def test_dragging_an_arrow_moves_the_body_along_its_axis_only(scene: tuple, rotation: bool) -> None:
    """Ein reiner Platzierungsgriff bietet nur übernehmbare Verschiebungen an."""
    renderer, body, previous, releases = scene
    previous.remove()
    gizmo = Gizmo(renderer, body, scale=0.4, rotation=rotation, release_callback=releases.append)
    renderer.render()
    assert len(gizmo.items) == (6 if rotation else 3)
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
    gizmo.remove()


def test_the_frame_of_a_direction_is_right_handed_and_ends_on_it() -> None:
    """Der Rahmen einer Fläche: dritte Achse ist ihre Richtung, alle drei rechtshändig."""
    for normal in ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.6, 0.0, 0.8)):
        frame = normal_frame(normal)
        assert np.allclose(frame[2], normal)
        assert np.allclose(np.linalg.norm(frame, axis=1), 1.0)
        assert np.allclose(np.cross(frame[0], frame[1]), frame[2]), normal


def test_the_grip_of_a_face_is_one_arrow_along_the_face_and_no_ring(scene: tuple) -> None:
    """An einer Fläche nur, was sie kann: ein Pfeil entlang ihrer Richtung.

    Die Handbuchbilder zeigten an der gewählten Oberseite drei Pfeile und drei
    Ringe, und beim Loslassen zählte nur der Weg entlang der Richtung — was
    quer oder im Kreis gezogen wurde, verfiel still. Gemessen an einer schrägen
    Richtung, denn an einer Weltachse fiele ein Rahmen aus Weltachsen nicht auf.
    """
    renderer, body, previous, releases = scene
    previous.remove()
    normal = (0.0, -0.6, 0.8)
    gizmo = Gizmo(
        renderer,
        body,
        scale=0.4,
        axes=normal_frame(normal),
        rotation=False,
        arrows=(2,),
        release_callback=releases.append,
    )
    renderer.render()
    try:
        assert len(gizmo.items) == 1, "ein Pfeil, kein Ring"
        assert gizmo.items[0].colour() == AXIS_COLOURS[2]
        x, y = arrow_tip_pixel(renderer, gizmo, 2)
        gizmo.handle(hover(x, y))
        assert gizmo.handle(press(x, y)), "der Pfeil nimmt die Geste"
        far = np.asarray(gizmo.origin) + gizmo.axes[2] * gizmo._arrow_length * 1.5
        fx, fy, _depth = renderer.world_to_display((float(far[0]), float(far[1]), float(far[2])))
        assert gizmo.handle(move(fx, fy))
        shift = body.matrix()[:3, 3]
        assert float(np.linalg.norm(shift)) > 2.0, shift
        direction = shift / np.linalg.norm(shift)
        assert np.allclose(direction, normal, atol=1e-6), "der Zug geht entlang der Fläche"
        assert gizmo.handle(release(fx, fy))
        assert len(releases) == 1
        # Neben dem einen Pfeil ist nichts zu greifen — dort lag vorher ein Ring.
        gizmo.handle(hover(5, 5))
        assert not gizmo.handle(press(5, 5))
    finally:
        gizmo.remove()


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


def test_the_scale_cube_scales_the_body_about_its_centre(scene: tuple) -> None:
    """Das dritte Drittel von §18.11: Der Würfel auf der Raumdiagonale
    skaliert gleichmäßig um die Mitte des Körpers — doppelt so weit vom
    Zentrum gezogen heißt doppelt so groß, und die Mitte bleibt, wo sie war."""
    from app.ui.scale_widget import HOVER_COLOUR, ScaleHandle

    renderer, body, _gizmo, _releases = scene
    centre = np.asarray(body.centre())
    factors: list[float] = []
    seen: list[float] = []
    handle = ScaleHandle(
        renderer,
        body,
        scale=0.4,
        colour="#00c0ff",
        release_callback=factors.append,
        interact_callback=seen.append,
    )
    renderer.render()
    gx, gy, _depth = renderer.world_to_display(handle.grip_position)
    cx, cy, _depth = renderer.world_to_display(tuple(float(v) for v in centre))  # type: ignore[arg-type]
    handle.handle(hover(gx, gy))
    assert handle.item.colour() == HOVER_COLOUR, "der Würfel leuchtet unter dem Zeiger"
    assert handle.handle(press(gx, gy))
    fx, fy = cx + 2.0 * (gx - cx), cy + 2.0 * (gy - cy)
    assert handle.handle(move(fx, fy))
    matrix = body.matrix()
    factor = matrix[0, 0]
    assert factor == pytest.approx(2.0, abs=0.15), factor
    assert matrix[1, 1] == pytest.approx(factor) and matrix[2, 2] == pytest.approx(factor)
    assert np.allclose(matrix @ np.append(centre, 1.0), np.append(centre, 1.0), atol=1e-6)
    assert seen and seen[-1] == pytest.approx(factor)
    assert handle.handle(release(fx, fy))
    assert factors == [pytest.approx(factor)]
    assert not handle.pressing
    handle.handle(hover(5, 5))
    assert handle.item.colour() == "#00c0ff"
    assert not handle.handle(press(5, 5)), "neben dem Würfel gehört die Geste niemandem"
    handle.remove()


def test_a_click_on_the_grip_moves_nothing_and_reports_nothing(scene: tuple) -> None:
    """Ein Klick ohne Weg ist kein Zug — auch mit dem Zittern, das Klicken hat.

    Dieselbe Schwelle wie im Navigator und an den Langlochknöpfen
    (``CLICK_SLACK``, ``kamera.md``: „Ein Klick ist ein Klick, auch mit
    Zittern“). Bis zum 27.09.2026 verschob der Griff sein Ziel schon beim
    ersten Bildpunkt und meldete beim Loslassen die Matrix als Zug; am
    Wabenhalter band der Klick auf die Mitte der gewählten Bohrung damit den
    Maßentwurf, und die Nachbarbohrung ließ sich nicht mehr wählen
    (Durchsicht 0.5.1, rest-auswahl).
    """
    renderer, body, gizmo, releases = scene
    x, y = arrow_tip_pixel(renderer, gizmo, 2)
    gizmo.handle(hover(x, y))
    assert gizmo.handle(press(x, y)), "der Druck gehört dem Griff"
    assert gizmo.handle(move(x + 3, y - 3)), "und das Zittern auch"
    assert np.allclose(body.matrix(), np.eye(4)), "ein Klick verschiebt nichts"
    assert not gizmo.dragging, "drei Bildpunkte sind noch ein Klick"
    assert gizmo.handle(release(x + 3, y - 3))
    assert releases == [], "und meldet keinen Zug"
    assert not gizmo.pressing and not gizmo.dragging

    # Gegenprobe: über die Schwelle hinaus ist es ein Zug — gerechnet von der
    # Stelle des Drückens aus, nicht von der Schwelle.
    far = np.asarray(gizmo.origin) + gizmo.axes[2] * gizmo._arrow_length * 1.5
    fx, fy, _depth = renderer.world_to_display((float(far[0]), float(far[1]), float(far[2])))
    gizmo.handle(hover(x, y))
    assert gizmo.handle(press(x, y))
    assert gizmo.handle(move(fx, fy))
    assert gizmo.dragging
    shift = body.matrix()[:3, 3]
    assert shift[2] > 5.0 and abs(shift[0]) < 1e-6 and abs(shift[1]) < 1e-6, shift
    assert gizmo.handle(move(x, y)), "zurück an den Anfang"
    assert np.allclose(body.matrix(), np.eye(4), atol=1e-6), "steht wieder, wo er stand"
    assert gizmo.handle(move(fx, fy))
    assert gizmo.handle(release(fx, fy))
    assert len(releases) == 1 and np.allclose(releases[0], body.matrix())


def _dispatching_view(started: list[bool], navigated: list[object], **handles: object) -> object:
    """Die Vorfahrt der Ansicht ohne Fenster: nur, was ``_dispatch_pointer`` liest."""
    from types import SimpleNamespace

    state = SimpleNamespace(
        _placement_grip=None,
        _preview_gizmo=None,
        _gizmo=None,
        _scale_handle=None,
        _slot_handle=None,
        _slot_borrowed=False,
        _blocked_cavity_slot_pull=False,
        _pending_cavity_slot_pull=None,
        _block_unsupported_cavity_slot_pull=lambda _event: False,
        _placement_pointer=lambda _event: False,
        _placement_resume=None,
        placementDragStarted=SimpleNamespace(emit=lambda: started.append(True)),
        _queue_feature_label_layout=lambda: None,
        _pull_at_the_hole=lambda _event: False,
        _note_pointer=lambda _x, _y: None,
        _forget_pointer=lambda: None,
        _navigator=SimpleNamespace(handle=navigated.append),
    )
    for name, value in handles.items():
        setattr(state, name, value)
    return state


def test_a_click_on_the_placement_grip_does_not_bind_the_draft(scene: tuple) -> None:
    """Erst der Zug beginnt den Entwurf (``placementDragStarted``), nicht der Druck.

    Die Ansicht meldete den Beginn beim Drücken; der Fluss band daraus den
    Maßentwurf (``QuietHost.begin_edit``), und ``_quiet_selection_allowed``
    hielt danach jede andere Auswahl fest — gemessen am Wabenhalter: nach
    einem Klick auf die Mitte von ``hole_4`` blieb ``hole_4`` gewählt, gleich
    wohin geklickt wurde, und die Statuszeile verlangte, eine Änderung zu
    übernehmen, die es nicht gab (Sonde
    ``konzepte/nachweise-release-0.5.1/sonden/rest-auswahl/scenario_repro.py``).
    """
    from app.ui.viewport import Viewport

    renderer, body, gizmo, releases = scene
    started: list[bool] = []
    navigated: list[object] = []
    view = _dispatching_view(started, navigated, _placement_grip=gizmo)
    x, y = arrow_tip_pixel(renderer, gizmo, 2)
    for event in (hover(x, y), press(x, y), move(x + 3, y - 3), release(x + 3, y - 3)):
        Viewport._dispatch_pointer(view, event)  # type: ignore[arg-type]
    assert started == [], "ein Klick ohne Weg beginnt nichts"
    assert releases == [] and np.allclose(body.matrix(), np.eye(4)), "und bewegt nichts"
    assert not gizmo.pressing

    far = np.asarray(gizmo.origin) + gizmo.axes[2] * gizmo._arrow_length * 1.5
    fx, fy, _depth = renderer.world_to_display((float(far[0]), float(far[1]), float(far[2])))
    Viewport._dispatch_pointer(view, hover(x, y))  # type: ignore[arg-type]
    Viewport._dispatch_pointer(view, press(x, y))  # type: ignore[arg-type]
    assert started == [], "auch der Druck vor dem Zug nicht"
    Viewport._dispatch_pointer(view, move(fx, fy))  # type: ignore[arg-type]
    assert started == [True], "der Zug beginnt ihn, einmal"
    Viewport._dispatch_pointer(view, move(fx, fy - 5))  # type: ignore[arg-type]
    Viewport._dispatch_pointer(view, release(fx, fy - 5))  # type: ignore[arg-type]
    assert started == [True] and len(releases) == 1
    assert all(event.kind == "move" and not event.buttons for event in navigated), (
        "an die Kamera ging nur die freie Bewegung"
    )


def test_a_click_into_the_chosen_hole_does_not_bind_the_draft(scene: tuple) -> None:
    """Derselbe Grundsatz am Loch selbst: Der Druck ins gewählte Loch leiht
    sich die Langlochknöpfe (``_pull_at_the_hole``) — und meldete den Beginn,
    solange die Maße im Bild standen, schon beim Drücken."""
    from app.ui.slot_handle import SlotHandle
    from app.ui.viewport import Viewport

    renderer, _body, gizmo, _releases = scene
    gizmo.remove()
    proposals: list[tuple[float, float]] = []
    handle = SlotHandle(
        renderer,
        centre=(10.0, 10.0, 20.0),
        axis=(0.0, 0.0, 1.0),
        diameter=6.0,
        length=6.0,
        angle=0.0,
        knob_size=5.0,
        colour="#ff9f1c",
        release_callback=lambda length, angle: proposals.append((length, angle)),
    )
    started: list[bool] = []
    view = _dispatching_view(
        started,
        [],
        _slot_handle=handle,
        _pull_at_the_hole=lambda event: handle.take_press(event, 0),
    )
    x, y, _depth = renderer.world_to_display((10.0, 10.0, 20.0))
    for event in (press(x, y), move(x + 2, y + 2), release(x + 2, y + 2)):
        Viewport._dispatch_pointer(view, event)  # type: ignore[arg-type]
    assert started == [] and proposals == [], "ein Klick ins Loch beginnt nichts"
    assert not handle.pressing

    Viewport._dispatch_pointer(view, press(x, y))  # type: ignore[arg-type]
    assert started == []
    Viewport._dispatch_pointer(view, move(x + 60, y))  # type: ignore[arg-type]
    assert started == [True], "der Zug zum Langloch beginnt den Entwurf"
    Viewport._dispatch_pointer(view, release(x + 60, y))  # type: ignore[arg-type]
    assert started == [True] and len(proposals) == 1
    handle.remove()
