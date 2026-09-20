"""Analytische Träger in NURBS bleiben erkennbar und auf der Originalform bearbeitbar."""

from __future__ import annotations

import math
from collections import Counter
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.brep import edit, step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, available
from app.core.units import EPS_GEOM

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")


def _plate() -> Solid:
    """40 × 30 × 10 mm, durchgehende Bohrung Ø6 auf der Z-Achse."""
    return edit.cut_bore(
        edit.box(40.0, 30.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=20.0,
    )


def _nurbs(solid: Solid) -> Solid:
    """Die gleiche gültige Topologie mit rationalen B-Spline-Trägerflächen."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    return Solid(BRepBuilderAPI_NurbsConvert(solid.shape, True).Shape())


@pytest.mark.parametrize("representation", ["analytic", "nurbs", "step"])
@pytest.mark.parametrize("placed", [False, True])
def test_a_nurbs_plate_keeps_its_planes_and_editable_bore(
    representation: str, placed: bool
) -> None:
    """Ø6 → Ø8 behält Achse, Außenmaße und echte Flächenwahl auch nach STEP und Spiegelung."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    source = _plate()
    transform = np.eye(4)
    if placed:
        transform = trimesh.transformations.rotation_matrix(math.radians(31.0), (1.0, 2.0, 3.0))
        transform[:3, 0] *= -1.0
        transform[:3, 3] = (17.0, -9.0, 13.0)
        source = edit.transformed(source, transform)
    if representation != "analytic":
        source = _nurbs(source)
    if representation == "step":
        source = step.read(step.write(source))
    assert BRepCheck_Analyzer(source.shape).IsValid()
    assert source.is_closed and source.solid_count == 1
    assert source.volume == pytest.approx(12000.0 - 90.0 * math.pi, abs=EPS_GEOM)

    assert source.area == pytest.approx(3800.0 + 42.0 * math.pi, abs=EPS_GEOM)
    original_bounds = source.bounds

    found = features_of(source)
    assert Counter(feature.kind for feature in found.values()) == {"face": 6, "hole": 1}
    hole = next(feature for feature in found.values() if feature.kind == "hole")
    expected_centre = transform @ np.array((0.0, 0.0, 5.0, 1.0))
    assert hole.params["diameter"] == pytest.approx(6.0, abs=EPS_GEOM)
    assert hole.params["depth"] == pytest.approx(10.0, abs=EPS_GEOM)
    assert hole.params["centre"] == pytest.approx(expected_centre[:3], abs=EPS_GEOM)
    assert hole.params["axis"] == pytest.approx(transform[:3, 2], abs=EPS_GEOM)
    assert hole.params["through"] is True
    assert len(source.faces_of_triangles(hole.face_indices)) == 1
    assert sorted(
        feature.params["area"] for feature in found.values() if feature.kind == "face"
    ) == (
        pytest.approx(
            [300.0, 300.0, 400.0, 400.0, 1200.0 - 9.0 * math.pi, 1200.0 - 9.0 * math.pi],
            abs=EPS_GEOM,
        )
    )

    resized = edit.resize_bore(
        source,
        position=hole.params["centre"],
        direction=hole.params["axis"],
        previous_diameter=hole.params["diameter"],
        diameter=8.0,
        depth=hole.params["depth"],
    )
    assert BRepCheck_Analyzer(resized.shape).IsValid()
    assert resized.is_closed and resized.solid_count == 1
    assert resized.volume == pytest.approx(12000.0 - 160.0 * math.pi, abs=EPS_GEOM)
    wider = next(feature for feature in features_of(resized).values() if feature.kind == "hole")
    assert wider.params["diameter"] == pytest.approx(8.0, abs=EPS_GEOM)
    assert wider.params["axis"] == pytest.approx(hole.params["axis"], abs=EPS_GEOM)
    assert wider.params["centre"] == pytest.approx(hole.params["centre"], abs=EPS_GEOM)
    assert wider.params["through"] is True
    assert source.bounds == original_bounds
    assert source.volume == pytest.approx(12000.0 - 90.0 * math.pi, abs=EPS_GEOM)


def _reparameterized_cylinder_face(turn: float, exchanged: bool, inward: bool) -> Any:
    """Ein Zylinder mit nichtlinearer Höhenparametrisierung und fremden UV-Einheiten."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.collections import Array1_double
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopoDS import TopoDS

    source = Solid(
        BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(4.0, -7.0, 3.0), gp_Dir(0.0, 0.0, 1.0)), 3.0, 8.0, turn
        ).Shape()
    )
    face = next(
        face for face in source.faces() if BRepAdaptor_Surface(face).GetType() == GeomAbs_Cylinder
    )
    nurbs = TopoDS.Face(BRepBuilderAPI_NurbsConvert(face, True).Shape())
    surface = BRep_Tool.Surface_s(nurbs).Copy()
    surface.IncreaseDegree(surface.UDegree(), 2)
    for row in range(1, surface.NbUPoles() + 1):
        point = surface.Pole(row, 2)
        point.SetZ(3.8)
        surface.SetPole(row, 2, point)
    for axis, scale, shift in (("U", 2.5, 11.0), ("V", 0.125, -17.0)):
        count = getattr(surface, f"Nb{axis}Knots")()
        values = Array1_double(1, count)
        for index in range(1, count + 1):
            values.SetValue(index, getattr(surface, f"{axis}Knot")(index) * scale + shift)
        getattr(surface, f"Set{axis}Knots")(values)
    if exchanged:
        surface.ExchangeUV()
    result = BRepBuilderAPI_MakeFace(surface, EPS_GEOM).Face()
    if exchanged != inward:
        result.Reverse()
    return result


@pytest.mark.parametrize("turn", [math.pi, math.radians(184.0), math.tau])
@pytest.mark.parametrize("exchanged", [False, True])
@pytest.mark.parametrize("inward", [False, True])
def test_cylinder_description_uses_geometry_after_reparameterization(
    turn: float, exchanged: bool, inward: bool
) -> None:
    """Vertauschte Parameter, andere Einheiten und eine nichtlineare Höhe ändern keine Maße."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    from app.core.brep.canonical import CylinderSurface, describe

    face = _reparameterized_cylinder_face(turn, exchanged, inward)
    assert BRepCheck_Analyzer(face).IsValid()
    surface = describe(face)
    assert isinstance(surface, CylinderSurface)
    assert surface.cylinder.Radius() == pytest.approx(3.0, abs=EPS_GEOM)
    assert surface.last - surface.first == pytest.approx(8.0, abs=EPS_GEOM)
    origin = np.asarray(surface.cylinder.Location().Coord())
    axis = np.asarray(surface.cylinder.Axis().Direction().Coord())
    middle = origin + (surface.first + surface.last) / 2.0 * axis
    assert middle == pytest.approx((4.0, -7.0, 7.0), abs=EPS_GEOM)
    assert surface.turn == pytest.approx(turn, abs=EPS_GEOM)
    assert surface.inward is inward


@pytest.mark.parametrize("interval", [(1.0, 3.0), (5.0, 7.0), (-1.0, 1.0)])
@pytest.mark.parametrize("exchanged", [False, True])
def test_periodic_nurbs_trims_cross_the_parameter_seam(
    interval: tuple[float, float], exchanged: bool
) -> None:
    """Periodische Trimmungen behalten ihre tatsächliche Fläche auf beiden Seiten der Naht."""
    import io

    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_NurbsConvert
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopoDS import TopoDS

    from app.core.brep.canonical import CylinderSurface, describe

    body = edit.cylinder(6.0, 8.0)
    wall = next(
        face for face in body.faces() if BRepAdaptor_Surface(face).GetType() == GeomAbs_Cylinder
    )
    converted = TopoDS.Face(BRepBuilderAPI_NurbsConvert(wall, True).Shape())
    carrier = BRep_Tool.Surface_s(converted).Copy()
    carrier.SetUPeriodic()
    points = [carrier.Value(value, 4.0) for value in interval]
    expected_turn = (
        math.atan2(points[1].Y(), points[1].X()) - math.atan2(points[0].Y(), points[0].X())
    ) % math.tau
    bounds = (*interval, 1.0, 7.0)
    if exchanged:
        carrier.ExchangeUV()
        bounds = (1.0, 7.0, *interval)
    face = BRepBuilderAPI_MakeFace(carrier, *bounds, EPS_GEOM).Face()
    if exchanged:
        face.Reverse()
    assert BRepCheck_Analyzer(face).IsValid()
    before = io.BytesIO()
    BRepTools.Write_s(face, before)
    surface = describe(face)
    after = io.BytesIO()
    BRepTools.Write_s(face, after)
    assert after.getvalue() == before.getvalue()
    assert isinstance(surface, CylinderSurface)
    assert surface.cylinder.Radius() == pytest.approx(3.0, abs=EPS_GEOM)
    assert surface.last - surface.first == pytest.approx(6.0, abs=EPS_GEOM)
    origin = np.asarray(surface.cylinder.Location().Coord())
    axis = np.asarray(surface.cylinder.Axis().Direction().Coord())
    assert origin + (surface.first + surface.last) / 2.0 * axis == pytest.approx(
        (0.0, 0.0, 4.0), abs=EPS_GEOM
    )
    assert surface.turn == pytest.approx(expected_turn, abs=EPS_GEOM)
    assert not surface.inward


def test_an_elliptic_nurbs_wall_is_not_a_circle_cylinder() -> None:
    """Halbachsen 6 und 3 mm dürfen keinen kreisförmigen Zapfen oder Bohrer anbieten."""
    from app.core.brep.canonical import PlaneSurface, describe

    source = edit.transformed(edit.cylinder(6.0, 8.0), np.diag((2.0, 1.0, 0.5, 1.0)))
    described = [describe(face) for face in source.faces()]
    assert sum(isinstance(surface, PlaneSurface) for surface in described) == 2
    assert described.count(None) == 1
    found = list(features_of(source).values())
    assert sum(feature.kind == "face" for feature in found) == 2
    assert sum(feature.kind == "curved_face" for feature in found) == 1
    assert not any(feature.kind in {"hole", "pin", "torus"} for feature in found)


@pytest.mark.parametrize("kind", ["plane", "cylinder"])
@pytest.mark.parametrize("offset", [-0.75, 0.75])
@pytest.mark.parametrize("exchanged", [False, True])
def test_offsets_of_canonical_nurbs_keep_their_signed_distance(
    kind: str, offset: float, exchanged: bool
) -> None:
    """Auch nativ zusammengesetzte Offsets beachten die natürliche Parameternormale."""
    import io

    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepTools import BRepTools
    from OCP.collections import Array2_gp_Pnt
    from OCP.Geom import Geom_BezierSurface, Geom_OffsetSurface
    from OCP.gp import gp_Pnt

    from app.core.brep.canonical import CylinderSurface, PlaneSurface, describe

    if kind == "plane":
        poles = Array2_gp_Pnt(1, 3, 1, 3)
        for row in range(1, 4):
            for column in range(1, 4):
                poles.SetValue(row, column, gp_Pnt(2.0 * row, 3.0 * column, 5.0))
        basis = Geom_BezierSurface(poles)
    else:
        wall = _reparameterized_cylinder_face(math.radians(184.0), False, False)
        basis = BRep_Tool.Surface_s(wall).Copy()
    if exchanged:
        basis.ExchangeUV()
    carrier = Geom_OffsetSurface(Geom_OffsetSurface(basis, 0.5), offset - 0.5)
    face = BRepBuilderAPI_MakeFace(carrier, EPS_GEOM).Face()
    if exchanged:
        face.Reverse()
    assert BRepCheck_Analyzer(face).IsValid()
    before = io.BytesIO()
    BRepTools.Write_s(face, before)
    result = describe(face)
    after = io.BytesIO()
    BRepTools.Write_s(face, after)
    assert after.getvalue() == before.getvalue()
    distance = -offset if exchanged else offset
    if kind == "plane":
        assert isinstance(result, PlaneSurface)
        assert result.normal == pytest.approx((0.0, 0.0, 1.0), abs=EPS_GEOM)
        assert result.plane.Location().Z() == pytest.approx(5.0 + distance, abs=EPS_GEOM)
    else:
        assert isinstance(result, CylinderSurface)
        assert result.cylinder.Radius() == pytest.approx(3.0 + distance, abs=EPS_GEOM)
        assert result.last - result.first == pytest.approx(8.0, abs=EPS_GEOM)
        assert result.turn == pytest.approx(math.radians(184.0), abs=EPS_GEOM)
        assert not result.inward


@pytest.mark.parametrize("kind", ["plane", "cylinder"])
@pytest.mark.parametrize("offset", [-0.75, 0.75])
def test_offset_recognition_rejects_a_noncanonical_basis(kind: str, offset: float) -> None:
    """Ein gültiger Offset übernimmt weder eine Ellipse noch eine örtlich gewölbte Basis."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.collections import Array2_gp_Pnt
    from OCP.Geom import Geom_BezierSurface, Geom_OffsetSurface
    from OCP.gp import gp_Pnt

    from app.core.brep.canonical import describe

    if kind == "plane":
        poles = Array2_gp_Pnt(1, 3, 1, 3)
        for row in range(1, 4):
            for column in range(1, 4):
                poles.SetValue(
                    row,
                    column,
                    gp_Pnt(2.0 * row, 3.0 * column, 1.0 if row == column == 2 else 0.0),
                )
        basis = Geom_BezierSurface(poles)
        assert basis.Value(0.5, 0.5).Z() == pytest.approx(0.25, abs=EPS_GEOM)
    else:
        source = edit.transformed(edit.cylinder(6.0, 8.0), np.diag((2.0, 1.0, 0.5, 1.0)))
        basis = BRep_Tool.Surface_s(source.faces()[0]).Copy()
    carrier = Geom_OffsetSurface(basis, offset)
    face = BRepBuilderAPI_MakeFace(carrier, EPS_GEOM).Face()
    assert BRepCheck_Analyzer(face).IsValid()
    if kind == "plane":
        assert abs(carrier.Value(0.5, 0.5).Z() - carrier.Value(0.25, 0.5).Z()) > EPS_GEOM
    else:
        bounds = carrier.Bounds()
        points = [
            carrier.Value(value, (bounds[2] + bounds[3]) / 2.0)
            for value in np.linspace(*bounds[:2], 33)
        ]
        radii = [math.hypot(point.X(), point.Y()) for point in points]
        assert max(radii) - min(radii) > 2.0
    assert describe(face) is None


@pytest.mark.parametrize("kind", ["plane", "cylinder"])
@pytest.mark.parametrize("outer_trim", [False, True])
@pytest.mark.parametrize("offset", [-0.75, 0.75])
def test_rectangular_trims_preserve_the_original_offset_domain(
    kind: str, outer_trim: bool, offset: float
) -> None:
    """Innere und äußere Trimmhüllen behalten UV-Grenzen, Lage und Originalgeometrie."""
    import io

    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepTools import BRepTools
    from OCP.collections import Array2_gp_Pnt
    from OCP.Geom import Geom_BezierSurface, Geom_OffsetSurface, Geom_RectangularTrimmedSurface
    from OCP.gp import gp_Pnt

    from app.core.brep.canonical import CylinderSurface, PlaneSurface, describe

    if kind == "plane":
        poles = Array2_gp_Pnt(1, 3, 1, 3)
        for row in range(1, 4):
            for column in range(1, 4):
                poles.SetValue(row, column, gp_Pnt(row, column, 0.0))
        basis = Geom_BezierSurface(poles)
    else:
        body = _nurbs(edit.cylinder(6.0, 8.0))
        basis = BRep_Tool.Surface_s(body.faces()[0]).Copy()
    domain = basis.Bounds()
    bounds = tuple(
        low + (high - low) * fraction
        for low, high in ((domain[0], domain[1]), (domain[2], domain[3]))
        for fraction in (0.1, 0.9)
    )
    if outer_trim:
        carrier = Geom_RectangularTrimmedSurface(Geom_OffsetSurface(basis, offset), *bounds)
    else:
        carrier = Geom_OffsetSurface(Geom_RectangularTrimmedSurface(basis, *bounds), offset)
    face = BRepBuilderAPI_MakeFace(carrier, EPS_GEOM).Face()
    assert BRepCheck_Analyzer(face).IsValid()
    before = io.BytesIO()
    BRepTools.Write_s(face, before)
    result = describe(face)
    after = io.BytesIO()
    BRepTools.Write_s(face, after)
    assert after.getvalue() == before.getvalue()
    if kind == "plane":
        assert isinstance(result, PlaneSurface)
        assert result.plane.Location().Z() == pytest.approx(offset, abs=EPS_GEOM)
        assert result.normal == pytest.approx((0.0, 0.0, 1.0), abs=EPS_GEOM)
    else:
        assert isinstance(result, CylinderSurface)
        assert result.cylinder.Radius() == pytest.approx(3.0 + offset, abs=EPS_GEOM)
        assert result.last - result.first == pytest.approx(6.4, abs=EPS_GEOM)
        points = [basis.Value(value, 4.0) for value in bounds[:2]]
        turn = (
            math.atan2(points[1].Y(), points[1].X()) - math.atan2(points[0].Y(), points[0].X())
        ) % math.tau
        assert result.turn == pytest.approx(turn, abs=EPS_GEOM)


def test_an_offset_does_not_amplify_an_inaccurate_candidate_normal() -> None:
    """Eine schmale geneigte Ebene passt räumlich ins Fenster, ihr Offset jedoch nicht."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.collections import Array2_gp_Pnt
    from OCP.Geom import Geom_BezierSurface, Geom_OffsetSurface
    from OCP.GeomAdaptor import GeomAdaptor_Surface
    from OCP.gp import gp_Pln, gp_Pnt

    from app.core.brep.canonical import PlaneSurface, _matches, describe

    poles = Array2_gp_Pnt(1, 3, 1, 3)
    for row in range(1, 4):
        for column in range(1, 4):
            x = (row - 2.0) * 1e-5
            poles.SetValue(row, column, gp_Pnt(x, column - 1.0, 0.02 * x))
    basis = Geom_BezierSurface(poles)
    carrier = Geom_OffsetSurface(basis, 0.75)
    face = BRepBuilderAPI_MakeFace(carrier, EPS_GEOM).Face()
    assert BRepCheck_Analyzer(face).IsValid()
    assert isinstance(describe(face), PlaneSurface)
    assert abs(basis.Value(0.0, 0.5).Z()) < EPS_GEOM
    assert abs(carrier.Value(0.5, 0.5).Z() - 0.75) > EPS_GEOM

    adaptor = GeomAdaptor_Surface(basis)
    assert _matches(adaptor, gp_Pln(), True, None)
    assert not _matches(adaptor, gp_Pln(), True, None, offset=0.75)


def test_offset_normal_checks_share_cancellation_and_the_work_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zusätzliche Ableitungsprodukte bleiben abbrechbar und verbrauchen dasselbe Budget."""
    import io

    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepTools import BRepTools
    from OCP.Geom import Geom_OffsetSurface

    from app.core.brep import canonical
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    basis_face = _reparameterized_cylinder_face(math.radians(184.0), False, False)
    basis = BRep_Tool.Surface_s(basis_face).Copy()
    carrier = Geom_OffsetSurface(Geom_OffsetSurface(basis, 0.5), 0.25)
    face = BRepBuilderAPI_MakeFace(carrier, EPS_GEOM).Face()
    before = io.BytesIO()
    BRepTools.Write_s(face, before)
    cancelled = CancelSignal()
    original = canonical._normal_bound
    calls = 0

    def interrupt(relative: Any, weights: Any, axis: Any, plane: bool, token: Any) -> float:
        nonlocal calls
        assert token is cancelled
        result = original(relative, weights, axis, plane, token)
        calls += 1
        cancelled.cancel()
        return result

    with monkeypatch.context() as isolated:
        isolated.setattr(canonical, "_normal_bound", interrupt)
        with pytest.raises(OperationCancelled):
            canonical.describe(face, cancelled=cancelled)
    assert calls == 1
    with monkeypatch.context() as isolated:
        isolated.setattr(canonical, "_MAX_COEFFICIENT_PRODUCTS", 1000)
        assert isinstance(canonical.describe(basis_face), canonical.CylinderSurface)
        assert canonical.describe(face) is None
    assert isinstance(canonical.describe(face), canonical.CylinderSurface)
    after = io.BytesIO()
    BRepTools.Write_s(face, after)
    assert after.getvalue() == before.getvalue()


@pytest.mark.parametrize("candidate_kind", ["plane", "cylinder"])
def test_a_local_deformation_cannot_hide_behind_a_zero_reported_gap(
    monkeypatch: pytest.MonkeyPatch, candidate_kind: str
) -> None:
    """Ein unabhängiger Gegenpunkt widerlegt den Kandidaten; GetGap=0 darf ihn nicht retten."""
    from OCP import ShapeAnalysis
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.collections import Array2_gp_Pnt
    from OCP.Geom import Geom_BezierSurface
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt

    from app.core.brep.canonical import describe

    if candidate_kind == "plane":
        poles = Array2_gp_Pnt(1, 3, 1, 3)
        for row in range(1, 4):
            for column in range(1, 4):
                poles.SetValue(
                    row, column, gp_Pnt(row - 1.0, column - 1.0, 1.0 if row == column == 2 else 0.0)
                )
        surface = Geom_BezierSurface(poles)
        assert surface.Value(0.5, 0.5).Z() == pytest.approx(0.25, abs=EPS_GEOM)
    else:
        face = _reparameterized_cylinder_face(math.tau, False, False)
        surface = BRep_Tool.Surface_s(face).Copy()
        point = surface.Pole(2, 2)
        point.SetX(4.0 + (point.X() - 4.0) * 1.01)
        point.SetY(-7.0 + (point.Y() + 7.0) * 1.01)
        surface.SetPole(2, 2, point)
        u_first, u_last, v_first, v_last = surface.Bounds()
        errors = []
        for u in np.linspace(u_first, u_last, 17):
            for v in np.linspace(v_first, v_last, 17):
                point = surface.Value(float(u), float(v))
                errors.append(abs(math.hypot(point.X() - 4.0, point.Y() + 7.0) - 3.0))
        assert max(errors) > 0.001
    original = BRepBuilderAPI_MakeFace(surface, EPS_GEOM).Face()
    assert BRepCheck_Analyzer(original).IsValid()
    assert describe(original) is None

    def unreliable(face: Any) -> Any:
        """Ein ausdrücklich falscher Vorschlag isoliert die zusätzliche vollständige Prüfung."""

        def is_cylinder(tolerance: float, cylinder: Any) -> bool:
            cylinder.SetRadius(3.0)
            cylinder.SetPosition(gp_Ax3(gp_Pnt(4.0, -7.0, 3.0), gp_Dir(0.0, 0.0, 1.0)))
            return candidate_kind == "cylinder"

        return SimpleNamespace(
            IsPlane=lambda tolerance, plane: candidate_kind == "plane",
            IsCylinder=is_cylinder,
            IsSphere=lambda tolerance, sphere: False,
            GetGap=lambda: 0.0,
            GetStatus=lambda: 0,
        )

    monkeypatch.setattr(ShapeAnalysis, "ShapeAnalysis_CanonicalRecognition", unreliable)
    assert describe(original) is None


def test_cancellation_inside_the_bernstein_check_preserves_the_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Abbruch nach einer echten Koeffizientenrechnung gelangt unverändert aus der Erkennung."""
    from app.core.brep import canonical
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = _nurbs(edit.cylinder(6.0, 8.0))
    face = source.faces()[0]
    cached = dict(source._cache)
    cancelled = CancelSignal()
    original = canonical._product
    calls = 0

    def interrupt(first: Any, second: Any, token: Any) -> Any:
        nonlocal calls
        assert token is cancelled
        result = original(first, second, token)
        calls += 1
        cancelled.cancel()
        return result

    with monkeypatch.context() as isolated:
        isolated.setattr(canonical, "_product", interrupt)
        with pytest.raises(OperationCancelled):
            canonical.describe(face, cancelled=cancelled)
    assert calls == 1
    assert source._cache.keys() == cached.keys()
    assert all(source._cache[key] is value for key, value in cached.items())
    assert isinstance(canonical.describe(face), canonical.CylinderSurface)
    assert source.volume == pytest.approx(72.0 * math.pi, abs=EPS_GEOM)


def test_planar_consumers_use_the_original_nurbs_faces() -> None:
    """Flächenauswahl und Versetzen teilen die Trägerauskunft, einschließlich der Bohrung."""
    from app.core.brep import profiles

    source = _nurbs(_plate())
    described = profiles._planar_faces(source)
    assert len(described) == 6
    assert all(
        any(face.IsSame(original) for original in source.faces()) for face, _, _ in described
    )
    top = next(centre for _, normal, centre in described if normal[2] > 0.9)
    result = profiles.push_faces(source, (0.0, 0.0, 1.0), 2.0, centre=top)
    assert result.is_closed and result.solid_count == 1
    assert result.volume == pytest.approx(14400.0 - 108.0 * math.pi, abs=EPS_GEOM)
    assert source.volume == pytest.approx(12000.0 - 90.0 * math.pi, abs=EPS_GEOM)


@pytest.mark.parametrize("depth", [4.0, 10.0])
def test_nurbs_neighbours_still_form_one_editable_slot(depth: float) -> None:
    """Zwei Halbzylinder und zwei Ebenen behalten die gemeinsame Öffnung und ihren Boden."""
    position = (0.0, 0.0, 10.0 - depth / 2.0)
    source = _nurbs(
        edit.slot_bore(
            edit.box(40.0, 30.0, 10.0),
            position=position,
            direction=(0.0, 0.0, 1.0),
            diameter=6.0,
            depth=depth,
            length=20.0,
            angle_deg=31.0,
            overlap=0.0,
        )
    )
    found = features_of(source)
    slots = [feature for feature in found.values() if feature.kind == "slot"]
    assert len(slots) == 1
    slot = slots[0]
    assert slot.params["diameter"] == pytest.approx(6.0, abs=EPS_GEOM)
    assert slot.params["depth"] == pytest.approx(depth, abs=EPS_GEOM)
    assert slot.params["length"] == pytest.approx(20.0, abs=EPS_GEOM)
    assert slot.params["travel"] == pytest.approx(14.0, abs=EPS_GEOM)
    assert slot.params["centre"] == pytest.approx(position, abs=EPS_GEOM)
    assert slot.params["direction"] == pytest.approx(
        (math.cos(math.radians(31.0)), math.sin(math.radians(31.0)), 0.0), abs=EPS_GEOM
    )
    assert slot.params["through"] is (depth > 9.0)
    assert len(source.faces_of_triangles(slot.face_indices)) == 4
    assert source.volume == pytest.approx(12000.0 - depth * (84.0 + 9.0 * math.pi), abs=EPS_GEOM)
    wider = edit.slot_bore(
        source,
        position=slot.params["centre"],
        direction=slot.params["axis"],
        diameter=8.0,
        depth=slot.params["depth"],
        length=slot.params["travel"] + 8.0,
        angle_deg=31.0,
        overlap=0.0,
    )
    assert wider.is_closed and wider.solid_count == 1
    assert wider.volume == pytest.approx(12000.0 - depth * (112.0 + 16.0 * math.pi), abs=EPS_GEOM)
    assert len([feature for feature in features_of(wider).values() if feature.kind == "slot"]) == 1


@pytest.mark.parametrize("radius", [11.0, 13.0])
def test_nurbs_radial_edits_keep_the_selected_angular_wall(radius: float) -> None:
    """Die echte 184-Grad-Wand bleibt bei der Radiusänderung ein einzelner begrenzter Körper."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    turn = math.radians(184.0)
    source = _nurbs(
        edit.boolean(
            "difference",
            [
                Solid(BRepPrimAPI_MakeCylinder(16.0, 17.0, turn).Shape()),
                Solid(BRepPrimAPI_MakeCylinder(12.0, 17.0, turn).Shape()),
            ],
        )
    )
    inner = min(
        (feature for feature in features_of(source).values() if feature.kind == "fillet"),
        key=lambda feature: feature.params["radius"],
    )
    result = edit.reround(source, inner.params["centre"], 12.0, radius)
    assert result.is_closed and result.solid_count == 1
    assert result.volume == pytest.approx(17.0 * turn * (16.0**2 - radius**2) / 2.0, abs=EPS_GEOM)
    assert source.volume == pytest.approx(17.0 * turn * (16.0**2 - 12.0**2) / 2.0, abs=EPS_GEOM)
    changed = min(
        (feature for feature in features_of(result).values() if feature.kind == "fillet"),
        key=lambda feature: feature.params["radius"],
    )
    assert changed.params["radius"] == pytest.approx(radius, abs=EPS_GEOM)
    repeated = edit.reround(result, changed.params["centre"], radius, 12.5)
    assert repeated.is_closed and repeated.solid_count == 1
    assert repeated.volume == pytest.approx(17.0 * turn * (16.0**2 - 12.5**2) / 2.0, abs=EPS_GEOM)
    assert min(
        feature.params["radius"]
        for feature in features_of(repeated).values()
        if feature.kind == "fillet"
    ) == pytest.approx(12.5, abs=EPS_GEOM)


@pytest.mark.parametrize("operation", ["shell", "draft", "push", "unround", "reround", "radial"])
def test_a_pre_cancelled_native_consumer_does_not_start_recognition(operation: str) -> None:
    """Jeder Einstieg reicht den Abbruch vor der neuen NURBS-Rechnung bis zur Fläche weiter."""
    from app.core.brep import profiles
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = _nurbs(_plate())
    cancelled = CancelSignal()
    cancelled.cancel()
    with pytest.raises(OperationCancelled):
        if operation == "shell":
            profiles.shell_open_top(source, 1.0, cancelled=cancelled)
        elif operation == "draft":
            profiles.draft_vertical(source, 3.0, cancelled=cancelled)
        elif operation == "push":
            profiles.push_faces(source, (0.0, 0.0, 1.0), 1.0, cancelled=cancelled)
        elif operation == "unround":
            edit.unround(source, (0.0, 0.0, 5.0), 3.0, cancelled=cancelled)
        elif operation == "reround":
            edit.reround(source, (0.0, 0.0, 5.0), 3.0, 4.0, cancelled=cancelled)
        else:
            edit.radial_rounding(source, (0.0, 0.0, 5.0), 3.0, 4.0, cancelled=cancelled)
    assert not source._cache
    assert len(features_of(source)) == 7
