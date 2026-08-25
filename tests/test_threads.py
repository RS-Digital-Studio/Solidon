"""Gewinde, die sich wirklich zusammenschrauben lassen (§24.3, §25, §40).

Ein Gewinde ist die eine Form, deren zwei Hälften sich nicht getrennt
beurteilen lassen: jede für sich sieht aus wie ein Gewinde, ist wasserdicht und
hat die richtigen Außenmaße — und das Paar greift trotzdem nicht. Genau das ist
passiert: die Mutter wurde auf den Außendurchmesser gebohrt statt auf den Kern,
es blieb also nichts stehen, woran der Gang der Schraube hätte halten können,
und sie fiel glatt hindurch. An M6 gemessen: Kamm bei r = 2,925, Loch beginnend
bei r = 3,075.

Alles hier wird darum am *Paar* gemessen: das Material des einen muss ins Tal
des anderen reichen, und der Spalt dazwischen muss das Spiel sein, nach dem
gefragt wurde — nicht mehr, nicht weniger.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.geom.mesh import Mesh, as_mesh_data
from app.core.knowledge.parts.fasteners import ThreadParams, printed_thread
from app.core.knowledge.parts.shapes import RIDGE_SHARE

#: Wo die Radien gemessen werden: innerhalb der Gewindelänge, abseits der
#: Endkappen, die auf der Achse sitzen und einen Radius von null meldeten.
BAND = (3.0, 9.0)


def radii(body: Mesh, low: float = BAND[0], high: float = BAND[1]) -> tuple[float, float]:
    """Kleinster und größter Abstand von der Achse, im gegebenen Höhenband.

    Das Band gilt im **eigenen** Lagebereich des Körpers: Ein Innengewinde
    liegt seit accac66c unter seiner Mündung (§24.1, Werkzeuglage), sein
    Material also bei negativem z. Gemessen wird die Gewindeform, nicht die
    Lage — deshalb wird das Band an die Unterkante des Körpers angelegt,
    und die Radienvergleiche der Tests bleiben, was sie waren.
    """
    points = np.asarray(as_mesh_data(body).raw.vertices)
    floor = float(points[:, 2].min())
    inside = points[(points[:, 2] > floor + low) & (points[:, 2] < floor + high)]
    lengths = np.linalg.norm(inside[:, :2], axis=1)
    lengths = lengths[lengths > 1e-9]
    return float(lengths.min()), float(lengths.max())


def pair(size: str = "M6", play: float = 0.15, length: float = 12.0):
    male = printed_thread(ThreadParams(size=size, length=length, internal=False, play=play))
    female = printed_thread(ThreadParams(size=size, length=length, internal=True, play=play))
    return male, female


def test_a_screw_and_its_nut_interlock() -> None:
    """Die Regression: beide Hälften waren richtig und das Paar war es nicht.

    Die Mutter ist ein *Werkzeug*, ihre Zahlen sind also das Loch, das sie
    hinterlässt. Ihr Material beginnt dort, wo ihre Bohrung beginnt, und das
    muss im Tal der Schraube liegen — sonst dreht die Schraube frei in einem
    glatten Loch.
    """
    male, female = pair()

    screw_core, screw_crest = radii(male.mesh)
    hole_core, hole_crest = radii(female.mesh)

    assert hole_core > screw_core, "the nut has to reach into the valley of the screw"
    assert hole_crest > screw_crest, "and clear its crest"


def test_the_gap_is_the_play_that_was_asked_for() -> None:
    """Nicht mehr: ein Gewinde mit einem halben Millimeter Luft hält nichts."""
    male, female = pair(play=0.15)

    screw_core, screw_crest = radii(male.mesh)
    hole_core, hole_crest = radii(female.mesh)

    assert hole_core - screw_core == pytest.approx(0.15, abs=0.01)
    assert hole_crest - screw_crest == pytest.approx(0.15, abs=0.01)


def test_without_play_the_two_meet_exactly() -> None:
    male, female = pair(play=0.0)

    assert radii(male.mesh)[1] == pytest.approx(radii(female.mesh)[1], abs=0.01)


def test_the_ridge_is_as_deep_as_the_pitch_says() -> None:
    """§24.3: die Tiefe ist ein Anteil der Steigung, und alle drei Nutzer
    teilen ihn.
    """
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
    """§24.3: ein Baustein, der nicht wasserdicht ist, ist kein Baustein."""
    male, female = pair()

    assert as_mesh_data(male.mesh).is_watertight
    assert as_mesh_data(female.mesh).is_watertight


def test_the_screw_stays_under_its_nominal_diameter() -> None:
    """Eine M6, die 6,2 misst, geht nicht durch ein 6-mm-Loch."""
    male, _female = pair(size="M6", play=0.15)

    assert radii(male.mesh)[1] * 2.0 == pytest.approx(6.0 - 0.15, abs=0.01)
