"""Die gewählte Bohrung bleibt samt Rand lesbar, ihre Griffe treffbar (FD-70).

Im finalen Lauf deckten an der gewählten Ø-5,2-Bohrung zwei Knopfzylinder
den Rand und drei Pfeile die Öffnung — die ungewählten Bohrungen daneben waren
besser zu erkennen. Die Knöpfe stehen deshalb außen am Rand, und die Pfeile
beginnen hinter den Knöpfen; Treffergeometrie, Zug und Spitze bleiben.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.ui.render.api import PointerEvent, SurfaceStyle
from app.ui.render.gizmo import MOST_CLEARED_SHARE, Gizmo
from app.ui.slot_handle import KNOB_RADIUS_SHARE, SlotHandle
from tests.render_fakes import RecordingRenderer

BORE = 5.2


def _handle(renderer: RecordingRenderer, length: float = BORE, angle: float = 0.0) -> SlotHandle:
    return SlotHandle(
        renderer,
        centre=(0.0, 0.0, 2.0),
        axis=(0.0, 0.0, 1.0),
        diameter=BORE,
        length=length,
        angle=angle,
        knob_size=BORE,
        colour="#ff9f1c",
        release_callback=lambda _length, _angle: None,
    )


def _in_plane(points: np.ndarray) -> np.ndarray:
    """Abstand der Punkte von der Bohrachse (z), in der Mündungsebene."""
    return np.hypot(points[:, 0], points[:, 1])


@pytest.mark.parametrize(("length", "angle"), [(BORE, 0.0), (14.0, 30.0), (BORE, 135.0)])
def test_the_knobs_stand_outside_the_opening(length: float, angle: float) -> None:
    """Kein Knopf ragt in die Öffnung; jeder berührt ihren Scheitel von außen."""
    renderer = RecordingRenderer()
    handle = _handle(renderer, length, angle)
    radius = handle._knob_size * KNOB_RADIUS_SHARE
    turn = math.radians(angle)
    along = np.array([math.cos(turn), math.sin(turn), 0.0])
    for index, knob in enumerate(handle.knobs):
        points = np.asarray(knob.points, dtype=float)
        side = along if index == 0 else -along
        # Gegen die Mittellinie gemessen: Die Projektion auf die Längsrichtung
        # beginnt am Scheitel, nie davor.
        assert (points @ side).min() >= length / 2.0 - 1e-6
        centre = np.asarray(handle.knob_centres[index], dtype=float)
        assert float(centre @ side) == pytest.approx(length / 2.0 + radius)
        assert np.ptp(points[:, :2], axis=0).max() == pytest.approx(2.0 * radius, rel=0.02)


def test_the_drag_still_measures_from_the_rim() -> None:
    """Am Knopf gegriffen und auf x = 12 gezogen, ist das Langloch 24 lang.

    Der Knopf steht außen, der Zug rechnet weiter vom Scheitel: Er wandert um
    den Weg der Hand, gleich wo die Hand ihn traf.
    """
    renderer = RecordingRenderer(size=(800, 600), scale=10.0)
    taken: list[tuple[float, float]] = []
    handle = SlotHandle(
        renderer,
        centre=(0.0, 0.0, 5.0),
        axis=(0.0, 0.0, 1.0),
        diameter=6.0,
        length=6.0,
        angle=0.0,
        knob_size=6.0,
        colour="#ff9f1c",
        release_callback=lambda length, angle: taken.append((length, angle)),
    )
    centre = renderer.world_to_display(handle.knob_centres[0])
    x, y = round(centre[0]), round(centre[1])
    renderer.item_picks[(x, y)] = handle.knobs[0]
    handle.handle(PointerEvent("move", x, y))
    assert handle.handle(PointerEvent("press", x, y, button="left"))
    shift = 12.0 - handle.knob_seats[0][0]
    target = renderer.world_to_display((handle.knob_centres[0][0] + shift, 0.0, 5.0))
    handle.handle(PointerEvent("move", round(target[0]), round(target[1])))
    handle.handle(PointerEvent("release", round(target[0]), round(target[1]), button="left"))
    assert taken and taken[0][0] == pytest.approx(24.0, abs=0.05)
    # Die Knöpfe gehen mit: außen am neuen Scheitel.
    for index, knob in enumerate(handle.knobs):
        drawn = np.asarray(handle._built_seats[index]) + np.asarray(knob.position())
        assert np.allclose(drawn, handle.knob_centres[index], atol=1e-9)


def test_the_clearance_reaches_past_the_knobs() -> None:
    """Wer Platz um den Griff freihält, hält auch die äußeren Knöpfe frei."""
    renderer = RecordingRenderer()
    handle = _handle(renderer, 14.0, 0.0)
    centre, reach = handle.clearance
    for knob in handle.knobs:
        points = np.asarray(knob.points, dtype=float) - np.asarray(centre)
        # In der Mündungsebene gemessen: Die Reichweite ist ein Radius um die Achse.
        assert _in_plane(points).max() <= reach + 1e-6


def _arrow_points(renderer: RecordingRenderer) -> list[np.ndarray]:
    return [
        np.asarray(renderer.item_of(f"gizmo:arrow:{index}").points, dtype=float)
        for index in range(3)
    ]


@pytest.mark.parametrize("clear", [0.0, 4.0, 100.0])
def test_the_arrows_begin_behind_the_cleared_hub_and_keep_their_tips(clear: float) -> None:
    """Die Pfeile lassen die Nabe frei; Spitze und Reichweite bleiben, wo sie waren."""
    renderer = RecordingRenderer()
    target = renderer.add_surface(
        np.array([[-10.0, -10.0, 0.0], [10.0, -10.0, 0.0], [10.0, 10.0, 0.0]]),
        np.array([[0, 1, 2]]),
        name="body",
        style=SurfaceStyle(colour="#777777"),
    )
    plain = Gizmo(renderer, target, origin=(0.0, 0.0, 0.0), scale=1.0, rotation=False)
    tips = [points @ np.eye(3)[index] for index, points in enumerate(_arrow_points(renderer))]
    reach = plain.reach
    plain.remove()
    gizmo = Gizmo(renderer, target, origin=(0.0, 0.0, 0.0), scale=1.0, rotation=False, clear=clear)
    freed = min(clear, MOST_CLEARED_SHARE * gizmo.arrow_length)
    for index, points in enumerate(_arrow_points(renderer)):
        along = points @ np.eye(3)[index]
        assert along.min() == pytest.approx(freed, abs=1e-9)
        assert along.max() == pytest.approx(tips[index].max())
    assert gizmo.reach == pytest.approx(reach)
    assert gizmo.fits(target, rotation=False, scale=1.0, clear=clear)
    assert not gizmo.fits(target, rotation=False, scale=1.0, clear=clear + 2.0)
