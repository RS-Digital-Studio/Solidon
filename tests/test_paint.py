"""Der Pinsel (Bauplan §20, „Bemalen").

Das ganze Feature ist ein Satz — einen Slot auf die Flächen um einen Punkt
legen — und ein schwerer Teil: an Kanten anhalten. Ohne das läuft die Farbe um
die Ecke auf die Rückseite des Teils, und das aufzuräumen kostet mehr, als das
Malen gespart hat. Also misst der größte Teil dieser Datei genau das.
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


# --- die Kante ------------------------------------------------------------------


def test_the_brush_stops_at_an_edge_however_wide_it_is() -> None:
    """Der Punkt der ganzen Sache: ein Radius allein malt um die Ecke."""
    painted = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1)

    assert counts(painted) == {0: 10, 1: 2}, "the top face, and nothing else"


def test_a_wide_enough_angle_paints_over_everything() -> None:
    painted = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1, edge_angle=180.0)

    assert used_slots(painted) == (1,)


def test_on_a_smooth_surface_the_radius_is_what_decides() -> None:
    """Eine Kugel hat keine Kanten — der Pinsel ist also wieder ein Kreis, wie
    erwartet.
    """
    sphere = ball()

    small = counts(brush(sphere, (0.0, 0.0, 20.0), radius=5.0, slot=1)).get(1, 0)
    large = counts(brush(sphere, (0.0, 0.0, 20.0), radius=12.0, slot=1)).get(1, 0)

    assert 0 < small < large < sphere.triangle_count


def test_painting_does_not_move_a_single_point() -> None:
    """§20: der Slot ist ein Attribut. Farbe ist keine Geometrie."""
    before = plate()

    painted = brush(before, (0.0, 0.0, 10.0), radius=20.0, slot=2)

    assert painted.raw is before.raw
    assert painted.volume == before.volume


def test_a_second_stroke_does_not_undo_the_first() -> None:
    once = brush(plate(), (0.0, 0.0, 10.0), radius=1000.0, slot=1)

    twice = brush(once, (0.0, 0.0, 0.0), radius=1000.0, slot=2)

    assert used_slots(twice) == (0, 1, 2), "top, bottom and the sides in between"


# --- Als Operation ---------------------------------------------------------------


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
    """Ein zweiter Strich in denselben Slot darf ihn nicht umbenennen."""
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())
    first = run("paint_slot", entry, profile, slot=1, radius=1000.0, z=10.0, name="Rot").outputs[0]

    second = run("paint_slot", first, profile, slot=1, radius=1000.0, z=0.0).outputs[0]

    assert [slot.name for slot in second.material_slots] == ["Rot"]


# --- die Leiste -----------------------------------------------------------------


def test_the_bar_is_off_until_somebody_switches_it_on(qt_app: QApplication) -> None:
    """Ein Modell zu bemalen, das jemand drehen wollte, ist kein Fehler, den
    ein Undo deckt.
    """
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
