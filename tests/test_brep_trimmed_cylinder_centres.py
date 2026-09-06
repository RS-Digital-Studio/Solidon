"""Exakte Mittelpunkte ungleich getrimmter Zylinderflächen, und ob ein Loch durchgeht.

Der Anlass ist die Teppichklammer aus der Durchsicht vom 05.09.2026 (Datei 19):
Ihre Bohrung tritt schräg aus, der Flächenschwerpunkt des Mantels lag 0,026 mm
neben und 0,2 mm über der Achsmitte, und ``resize_hole`` baute daraus einen
Schneidzylinder, der nicht koaxial war — die Tessellation ging auf.
"""

from __future__ import annotations

import math

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_Transform,
)
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,
    BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakePrism,
)
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from app.core.brep import edit
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, available
from app.core.types import Feature
from app.core.units import EPS_GEOM

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")


def _sloped_bore() -> Solid:
    """Ein Prisma, dessen obere Fläche die Bohrungswand schräg beschneidet."""
    outline = BRepBuilderAPI_MakePolygon()
    for point in (
        (-10.0, -10.0, 0.0),
        (10.0, -10.0, 0.0),
        (10.0, -10.0, 15.0),
        (-10.0, -10.0, 5.0),
    ):
        outline.Add(gp_Pnt(*point))
    outline.Close()
    face = BRepBuilderAPI_MakeFace(outline.Wire()).Face()
    wedge = Solid(BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 20.0, 0.0)).Shape())
    return edit.bore(
        wedge,
        position=(0.0, 0.0, 15.0),
        axis="z",
        diameter=6.0,
    )


def _plate() -> Solid:
    return Solid(BRepPrimAPI_MakeBox(gp_Pnt(-10.0, -10.0, 0.0), 20.0, 20.0, 10.0).Shape())


def _only_hole(solid: Solid) -> Feature:
    holes = [feature for feature in features_of(solid).values() if feature.kind == "hole"]
    assert len(holes) == 1, sorted(features_of(solid))
    return holes[0]


def test_a_trimmed_cylinder_uses_its_axis_and_v_span_for_the_centre() -> None:
    """Der Flächenschwerpunkt wandert zur längeren Seite des schrägen Keils.

    Die Bohrungsachse tut das nicht. Ihr unterer Rand liegt bei Z=0, der höchste
    Punkt ihres schrägen oberen Randes bei Z=11,5. Die Mitte der vollständigen
    Zylinderfläche ist deshalb der Achspunkt Z=5,75.
    """
    solid = _sloped_bore()
    hole = _only_hole(solid)

    assert hole.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=EPS_GEOM)
    assert hole.params["depth"] == pytest.approx(11.5, abs=EPS_GEOM)
    assert hole.params["centre"] == pytest.approx((0.0, 0.0, 5.75), abs=EPS_GEOM)
    assert solid.is_closed
    assert solid.is_watertight


def test_a_rotated_trimmed_cylinder_does_not_use_world_bounds() -> None:
    """Die V-Mitte reist mit der freien Achse und bleibt vom Welt-Hüllquader frei."""
    angle = math.radians(31.0)
    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 1.0, 0.0)), angle)
    rotated = Solid(BRepBuilderAPI_Transform(_sloped_bore().shape, transform, True).Shape())

    hole = _only_hole(rotated)
    expected_axis = (math.sin(angle), 0.0, math.cos(angle))
    expected_centre = tuple(value * 5.75 for value in expected_axis)

    assert hole.params["depth"] == pytest.approx(11.5, abs=EPS_GEOM)
    assert hole.params["axis"] == pytest.approx(expected_axis, abs=EPS_GEOM)
    assert hole.params["centre"] == pytest.approx(expected_centre, abs=EPS_GEOM)
    assert rotated.is_closed
    assert rotated.is_watertight


def test_resizing_a_sloped_bore_keeps_the_body_closed_and_the_hole_coaxial() -> None:
    """Der Weg der Teppichklammer: Ø 6 → Ø 7 am schrägen Austritt.

    Mit dem Schwerpunkt als Mitte war der Schneidzylinder nicht koaxial, und
    das Ergebnis trug eine offene Tessellation. Mit der Achsmitte bleibt der
    Körper geschlossen, und die neue Bohrung liegt auf derselben Achse.
    """
    solid = _sloped_bore()
    hole = _only_hole(solid)

    resized = edit.resize_bore(
        solid,
        position=hole.params["centre"],
        direction=hole.params["axis"],
        previous_diameter=float(hole.params["diameter"]),
        diameter=7.0,
        depth=float(hole.params["depth"]),
    )
    wider = _only_hole(resized)

    assert resized.is_closed
    assert resized.is_watertight
    assert wider.params["diameter"] == pytest.approx(7.0, abs=EPS_GEOM)
    assert wider.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=EPS_GEOM)
    assert wider.params["centre"][:2] == pytest.approx((0.0, 0.0), abs=EPS_GEOM)
    assert wider.params["through"] is True


def test_an_exact_hole_says_whether_it_goes_through() -> None:
    """Dasselbe Wort wie auf der Netzseite — der Steckbrief liest es.

    Durch eine Platte, schräg hinaus und quer durch den Schenkel eines
    U-Profils geht es hindurch; ein ebener Boden, die Spitze eines Bohrers und
    eine Kegelsenkung über einem Sackloch schließen. Die Spitze ist der Fall,
    den ein Schnitt der Achse mit der Nachbarfläche übersieht — sie ist in
    der Parametrisierung ein entarteter Punkt.
    """
    plate = _plate()
    through = edit.bore(plate, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0)
    blind = edit.bore(plate, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, depth=5.0)

    shaft = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(0.0, 0.0, 5.0), gp_Dir(0.0, 0.0, 1.0)), 3.0, 10.0
    ).Shape()
    tip = BRepPrimAPI_MakeCone(
        gp_Ax2(gp_Pnt(0.0, 0.0, 5.0), gp_Dir(0.0, 0.0, -1.0)),
        3.0,
        0.0,
        3.0 / math.tan(math.radians(59.0)),
    ).Shape()
    drilled = Solid(BRepAlgoAPI_Cut(plate.shape, BRepAlgoAPI_Fuse(shaft, tip).Shape()).Shape())

    deeper = edit.bore(plate, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, depth=6.0)
    sink = BRepPrimAPI_MakeCone(
        gp_Ax2(gp_Pnt(0.0, 0.0, 10.0), gp_Dir(0.0, 0.0, -1.0)), 5.0, 3.0, 2.0
    ).Shape()
    countersunk = Solid(BRepAlgoAPI_Cut(deeper.shape, sink).Shape())

    channel = Solid(
        BRepAlgoAPI_Cut(
            BRepPrimAPI_MakeBox(gp_Pnt(-10.0, -10.0, 0.0), 20.0, 20.0, 30.0).Shape(),
            BRepPrimAPI_MakeBox(gp_Pnt(-8.0, -10.0, 5.0), 16.0, 20.0, 30.0).Shape(),
        ).Shape()
    )
    across_a_leg = edit.bore(
        channel, position=(-10.0, 0.0, 15.0), axis="x", diameter=6.0, depth=2.0
    )

    assert _only_hole(through).params["through"] is True
    assert _only_hole(_sloped_bore()).params["through"] is True
    assert _only_hole(across_a_leg).params["through"] is True
    assert _only_hole(blind).params["through"] is False
    assert _only_hole(drilled).params["through"] is False
    assert _only_hole(countersunk).params["through"] is False
