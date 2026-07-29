"""Threads that actually screw together (§24.3, §25, §40).

A thread is the one shape whose two halves cannot be judged separately: each of
them on its own looks like a thread, is watertight and has the right outer
dimensions, and the pair still does not grip. That is what happened — the nut
was bored to the major diameter instead of to the core, so nothing was left
standing for the ridge of the screw to hold on to and it dropped straight
through. Measured on M6: crest at r = 2,925, hole beginning at r = 3,075.

Everything here is therefore measured on the *pair*: the material of the one
has to reach into the valley of the other, and the gap between them has to be
the clearance that was asked for — not more, not less.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.geom.mesh import Mesh, as_mesh_data
from app.core.knowledge.parts.fasteners import ThreadParams, printed_thread
from app.core.knowledge.parts.shapes import RIDGE_SHARE

#: Where the radii are measured: inside the threaded length, clear of the end
#: caps, which sit on the axis and would report a radius of zero.
BAND = (3.0, 9.0)


def radii(body: Mesh, low: float = BAND[0], high: float = BAND[1]) -> tuple[float, float]:
    """Smallest and largest distance from the axis, in the given band of height."""
    points = np.asarray(as_mesh_data(body).raw.vertices)
    inside = points[(points[:, 2] > low) & (points[:, 2] < high)]
    lengths = np.linalg.norm(inside[:, :2], axis=1)
    lengths = lengths[lengths > 1e-9]
    return float(lengths.min()), float(lengths.max())


def pair(size: str = "M6", play: float = 0.15, length: float = 12.0):
    male = printed_thread(ThreadParams(size=size, length=length, internal=False, play=play))
    female = printed_thread(ThreadParams(size=size, length=length, internal=True, play=play))
    return male, female


def test_a_screw_and_its_nut_interlock() -> None:
    """The regression: both halves were right and the pair was not.

    The nut is a *cutter*, so its numbers are the hole it leaves. Its material
    begins where its bore does, and that has to be inside the valley of the
    screw — otherwise the screw turns freely in a smooth hole.
    """
    male, female = pair()

    screw_core, screw_crest = radii(male.mesh)
    hole_core, hole_crest = radii(female.mesh)

    assert hole_core > screw_core, "the nut has to reach into the valley of the screw"
    assert hole_crest > screw_crest, "and clear its crest"


def test_the_gap_is_the_play_that_was_asked_for() -> None:
    """Not more: a thread with half a millimetre of air holds nothing."""
    male, female = pair(play=0.15)

    screw_core, screw_crest = radii(male.mesh)
    hole_core, hole_crest = radii(female.mesh)

    assert hole_core - screw_core == pytest.approx(0.15, abs=0.01)
    assert hole_crest - screw_crest == pytest.approx(0.15, abs=0.01)


def test_without_play_the_two_meet_exactly() -> None:
    male, female = pair(play=0.0)

    assert radii(male.mesh)[1] == pytest.approx(radii(female.mesh)[1], abs=0.01)


def test_the_ridge_is_as_deep_as_the_pitch_says() -> None:
    """§24.3: the depth is a share of the pitch, and all three users share it."""
    male, _female = pair(size="M6")
    core, crest = radii(male.mesh)

    assert crest - core == pytest.approx(1.0 * RIDGE_SHARE, abs=0.01), "M6 has a pitch of 1 mm"


def test_a_finer_thread_has_a_shallower_ridge() -> None:
    coarse, _ = pair(size="M8")
    fine, _ = pair(size="M3")

    coarse_depth = radii(coarse.mesh)[1] - radii(coarse.mesh)[0]
    fine_depth = radii(fine.mesh)[1] - radii(fine.mesh)[0]

    assert coarse_depth > fine_depth


def test_both_halves_are_closed_bodies() -> None:
    """§24.3: a part that is not watertight is not a part."""
    male, female = pair()

    assert as_mesh_data(male.mesh).is_watertight
    assert as_mesh_data(female.mesh).is_watertight


def test_the_screw_stays_under_its_nominal_diameter() -> None:
    """An M6 that measures 6,2 does not go through a 6 mm hole."""
    male, _female = pair(size="M6", play=0.15)

    assert radii(male.mesh)[1] * 2.0 == pytest.approx(6.0 - 0.15, abs=0.01)
