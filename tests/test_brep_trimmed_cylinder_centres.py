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


@pytest.mark.parametrize("recess", [False, True])
@pytest.mark.parametrize("normal_index", [0, 1])
def test_full_cylinder_material_side_includes_the_surface_handedness(
    recess: bool, normal_index: int
) -> None:
    """Eine geometrisch gleiche Rundwand bleibt trotz anderer Parametrisierung innen/außen."""
    import json
    from dataclasses import replace
    from pathlib import Path

    from app.core.brep import profiles
    from app.core.sketch import shapes
    from app.core.sketch.planes import frame_of
    from app.core.sketch.profile import profile_of
    from app.core.sketch.solver import solve_sketch

    case = json.loads(
        (Path(__file__).parent / "data/brep_cylinder_orientation.json").read_text(encoding="utf-8")
    )
    normal = tuple(case["normals"][normal_index])
    bottom = 0.0 if normal_index == 0 else case["stock"][2]
    frame = replace(frame_of((0.0, 0.0, 1.0), (0.0, 0.0, bottom)), normal=normal)
    tool = profiles.extrude(
        profile_of(solve_sketch(shapes.circle(case["diameter"]))), case["depth"], frame=frame
    )
    body = edit.boolean("difference", [edit.box(*case["stock"]), tool]) if recess else tool
    expected_volume = math.pi * (case["diameter"] / 2.0) ** 2 * case["depth"]
    if recess:
        expected_volume = math.prod(case["stock"]) - expected_volume
    assert body.is_closed and body.is_watertight
    assert body.volume == pytest.approx(expected_volume, abs=EPS_GEOM)
    curved = [feature for feature in features_of(body).values() if feature.kind != "face"]
    assert len(curved) == 1
    assert curved[0].kind == ("hole" if recess else "pin")
    assert curved[0].params["diameter"] == pytest.approx(case["diameter"], abs=EPS_GEOM)
    assert curved[0].params["depth"] == pytest.approx(case["depth"], abs=EPS_GEOM)
    if recess:
        assert curved[0].params["through"] is False


@pytest.mark.parametrize("recess", [False, True])
@pytest.mark.parametrize("mirrored", [False, True])
@pytest.mark.parametrize("widening", [False, True])
def test_a_cones_material_side_survives_an_indirect_surface_frame(
    recess: bool, mirrored: bool, widening: bool
) -> None:
    """Spiegelung ändert die Parametrisierung, nicht Senkung oder massiven Kegel."""
    import json
    from pathlib import Path

    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.GeomAbs import GeomAbs_Cone
    from OCP.TopAbs import TopAbs_IN

    case = json.loads(
        (Path(__file__).parent / "data/brep_cylinder_orientation.json").read_text(encoding="utf-8")
    )
    cone = case["cone"]
    radii = cone["radii"] if widening else list(reversed(cone["radii"]))
    height = cone["height"]
    bottom = case["stock"][2] - height
    tool = BRepPrimAPI_MakeCone(
        gp_Ax2(gp_Pnt(0.0, 0.0, bottom), gp_Dir(0.0, 0.0, 1.0)), *radii, height
    ).Shape()
    if mirrored:
        transform = gp_Trsf()
        transform.SetMirror(gp_Ax2(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(*cone["mirror_normal"])))
        tool = BRepBuilderAPI_Transform(tool, transform, True).Shape()
    solid = Solid(tool)
    if recess:
        solid = edit.boolean("difference", [edit.box(*case["stock"]), solid])
    volume = math.pi * height / 3.0 * (radii[0] ** 2 + radii[0] * radii[1] + radii[1] ** 2)
    expected_volume = math.prod(case["stock"]) - volume if recess else volume
    assert solid.is_closed and solid.is_watertight
    assert solid.volume == pytest.approx(expected_volume, abs=EPS_GEOM)

    classifier = BRepClass3d_SolidClassifier(solid.shape)
    classifier.Perform(gp_Pnt(0.0, 0.0, bottom + height / 2.0), EPS_GEOM)
    assert (classifier.State() == TopAbs_IN) is not recess
    curved = [
        BRepAdaptor_Surface(face)
        for face in solid.faces()
        if BRepAdaptor_Surface(face).GetType() == GeomAbs_Cone
    ]
    assert len(curved) == 1
    assert curved[0].Cone().Position().Direct() is not mirrored
    features = [feature for feature in features_of(solid).values() if feature.kind == "cone"]
    assert len(features) == 1
    assert features[0].params["recess"] is recess
    assert features[0].params["diameter"] == pytest.approx(2.0 * max(radii), abs=EPS_GEOM)
    assert features[0].params["angle"] == pytest.approx(
        math.degrees(2.0 * math.atan(abs(radii[1] - radii[0]) / height)), abs=EPS_GEOM
    )


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
