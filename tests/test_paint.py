"""The brush (Bauplan §20, "Bemalen").

The whole feature is one sentence — put a slot on the faces around a point —
and one hard part: stopping at edges. Without that the colour goes round the
corner onto the back of the part, and cleaning that up costs more than the
painting saved. So that is what most of this file measures.
"""

from __future__ import annotations

import pytest
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.geom.attributes import counts, used_slots
from app.core.geom.mesh import MeshData
from app.core.geom.paint import EDGE_ANGLE, brush
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject
from app.ui.paint_bar import PaintBar


def plate() -> MeshData:
    body = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    body.apply_translation((0.0, 0.0, 5.0))
    return MeshData.of(body)


def ball(subdivisions: int = 3) -> MeshData:
    return MeshData.of(trimesh.creation.icosphere(subdivisions=subdivisions, radius=20.0))


def run(op: str, entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


# --- the edge -------------------------------------------------------------------


def test_the_brush_stops_at_an_edge_however_wide_it_is() -> None:
    """The point of the whole thing: a radius alone paints round the corner."""
    painted = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1)

    assert counts(painted) == {0: 10, 1: 2}, "the top face, and nothing else"


def test_a_wide_enough_angle_paints_over_everything() -> None:
    painted = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1, edge_angle=180.0)

    assert used_slots(painted) == (1,)


def test_on_a_smooth_surface_the_radius_is_what_decides() -> None:
    """A sphere has no edges — so the brush is a circle again, as expected."""
    sphere = ball()

    small = counts(brush(sphere, (0.0, 0.0, 20.0), radius=5.0, slot=1)).get(1, 0)
    large = counts(brush(sphere, (0.0, 0.0, 20.0), radius=12.0, slot=1)).get(1, 0)

    assert 0 < small < large < sphere.triangle_count


def test_painting_does_not_move_a_single_point() -> None:
    """§20: the slot is an attribute. Colour is not geometry."""
    before = plate()

    painted = brush(before, (0.0, 0.0, 10.0), radius=20.0, slot=2)

    assert painted.raw is before.raw
    assert painted.volume == before.volume


def test_a_second_stroke_does_not_undo_the_first() -> None:
    once = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1)

    twice = brush(once, (0.0, 0.0, 0.0), radius=1000.0, slot=2)

    assert used_slots(twice) == (0, 1, 2), "top, bottom and the sides in between"


# --- as an operation ------------------------------------------------------------


def test_painting_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())

    result = run("paint_slot", entry, profile, slot=1, radius=1000.0, z=10.0, name="Rot")

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1)
    assert [slot.name for slot in output.material_slots] == ["Rot"]
    assert [finding.code for finding in result.findings] == ["colour.painted"]


def test_a_stroke_that_hits_nothing_says_so(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())

    result = run("paint_slot", entry, profile, slot=1, radius=0.5, x=500.0, y=500.0, z=500.0)

    assert result.outputs[0] is entry, "nothing changed, so nothing is replaced"
    assert [finding.code for finding in result.findings] == ["colour.nothing_painted"]


def test_the_slot_keeps_the_name_it_was_given(profile: Profile) -> None:
    """A second stroke into the same slot must not rename it."""
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())
    first = run("paint_slot", entry, profile, slot=1, radius=1000.0, z=10.0, name="Rot").outputs[0]

    second = run("paint_slot", first, profile, slot=1, radius=1000.0, z=0.0).outputs[0]

    assert [slot.name for slot in second.material_slots] == ["Rot"]


# --- the bar --------------------------------------------------------------------


def test_the_bar_is_off_until_somebody_switches_it_on(qt_app: QApplication) -> None:
    """Painting a model somebody meant to turn is not a mistake an undo covers."""
    bar = PaintBar()

    assert not bar.painting


def test_the_bar_reports_being_switched(qt_app: QApplication) -> None:
    bar = PaintBar()
    seen: list[bool] = []
    bar.paintingToggled.connect(seen.append)

    bar.active.setChecked(True)

    assert seen == [True]
    assert bar.painting


def test_the_bar_hands_over_what_a_stroke_is_made_of(qt_app: QApplication) -> None:
    bar = PaintBar()
    bar.slot.setValue(3)
    bar.radius.setValue(7.5)

    assert bar.values() == {"slot": 3, "radius": 7.5, "edge_angle": pytest.approx(EDGE_ANGLE)}


def test_stopping_switches_it_off(qt_app: QApplication) -> None:
    bar = PaintBar()
    bar.active.setChecked(True)

    bar.stop()

    assert not bar.painting
