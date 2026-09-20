"""Native Rund- und Freiformflächen behalten Maße und wirkliche Auswahlgrenzen."""

from __future__ import annotations

import io
import math
from typing import Any

import numpy as np
import pytest

from app.core.brep import step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, available, boolean_builder
from app.core.geom.mesh import as_mesh_data
from app.core.perceive.features import detect_curved_faces, detect_tori
from app.core.types import measure_status
from app.core.units import EPS_GEOM

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")


def _bytes(shape: Any) -> bytes:
    """Die unveränderte native Eingabe einschließlich ihrer Geometrie festhalten."""
    from OCP.BRepTools import BRepTools

    stream = io.BytesIO()
    BRepTools.Write_s(shape, stream)
    return stream.getvalue()


def _trimmed_native_cone(
    sign: float, span: tuple[float, float], deviation: float, placement: str
) -> tuple[Solid, Any]:
    """Eine echte getrimmte Kegelfläche schließen, ohne ihre Trägerparameter umzuschreiben."""
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeSolid,
        BRepBuilderAPI_MakeWire,
        BRepBuilderAPI_Sewing,
        BRepBuilderAPI_Transform,
    )
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.Geom import Geom_ConicalSurface
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Ax3, gp_Circ, gp_Dir, gp_Pln, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.TopoDS import TopoDS

    first, last = sorted(sign * value for value in span)
    surface = Geom_ConicalSurface(gp_Ax3(), sign * math.pi / 4.0, 1.0)
    # Der kleine echte Übertritt braucht eine engere Bautoleranz als seine
    # Endkreisgröße; sonst macht der Konstrukteur daraus bereits eine Spitze.
    tolerance = EPS_GEOM / 64.0
    mantle = BRepBuilderAPI_MakeFace(surface, 0.0, math.tau, first, last, tolerance).Face()
    assert BRepCheck_Analyzer(mantle).IsValid()
    sewing = BRepBuilderAPI_Sewing(tolerance)
    sewing.Add(mantle)
    for value in span:
        centre = gp_Pnt(0.0, 0.0, sign * value / math.sqrt(2.0))
        radius = abs(1.0 + value / math.sqrt(2.0))
        circle = gp_Circ(gp_Ax2(centre, gp_Dir(0, 0, 1)), radius)
        wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(circle).Edge()).Wire()
        sewing.Add(BRepBuilderAPI_MakeFace(gp_Pln(centre, gp_Dir(0, 0, 1)), wire).Face())
    sewing.Perform()
    shape = BRepBuilderAPI_MakeSolid(TopoDS.Shell(sewing.SewedShape())).Solid()
    assert BRepLib.OrientClosedSolid_s(shape)
    assert BRepCheck_Analyzer(shape).IsValid()

    transform = gp_Trsf()
    if placement == "oblique":
        transform.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(1, 2, -0.5)), 0.73)
    elif placement == "mirror":
        transform.SetMirror(gp_Ax2(gp_Pnt(), gp_Dir(1, 2, -0.5)))
    transform.SetTranslationPart(gp_Vec(17, -23, 5))
    shape = BRepBuilderAPI_Transform(shape, transform, True).Shape()
    assert BRepCheck_Analyzer(shape).IsValid()
    source = Solid(shape, deviation)
    assert source.is_closed and source.solid_count == 1
    return source, transform


@pytest.mark.parametrize("deviation", [0.03, 0.15])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("opposite", [False, True])
@pytest.mark.parametrize("placement", ["shift", "oblique", "mirror"])
def test_native_cone_trim_keeps_the_actual_nappe_and_positive_dimensions(
    deviation: float, sign: float, opposite: bool, placement: str
) -> None:
    """Ein gültiger Kegelstumpf jenseits der Spitze behält positive Maße und seinen Träger."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone
    from OCP.gp import gp_Pnt, gp_Vec

    span = (-5.0, -3.0) if opposite else (0.0, 2.0)
    source, transform = _trimmed_native_cone(sign, span, deviation, placement)
    before = _bytes(source.shape)
    low_radius, high_radius = sorted(abs(1.0 + value / math.sqrt(2.0)) for value in span)
    height = (span[1] - span[0]) / math.sqrt(2.0)
    expected_volume = (
        math.pi * height * (low_radius**2 + low_radius * high_radius + high_radius**2) / 3.0
    )
    assert source.volume == pytest.approx(expected_volume, abs=EPS_GEOM)

    wide = -5.0 if opposite else 2.0
    direction = -sign if opposite else sign
    expected_apex = gp_Pnt(0.0, 0.0, -sign).Transformed(transform).Coord()
    expected_axis = gp_Vec(0.0, 0.0, direction).Transformed(transform).Coord()
    expected_centre = gp_Pnt(0.0, 0.0, sign * wide / math.sqrt(2.0)).Transformed(transform).Coord()
    found = features_of(source)
    cones = [feature for feature in found.values() if feature.kind == "cone"]
    assert len(cones) == 1
    cone = cones[0]
    assert cone.params["diameter"] == pytest.approx(2.0 * high_radius, abs=EPS_GEOM)
    assert cone.params["centre"] == pytest.approx(expected_centre, abs=EPS_GEOM)
    assert cone.params["axis"] == pytest.approx(expected_axis, abs=EPS_GEOM)
    assert cone.params["angle"] == pytest.approx(90.0, abs=EPS_GEOM)
    assert not cone.params["recess"]
    native_index = next(
        index
        for index, face in enumerate(source.faces())
        if BRepAdaptor_Surface(face).GetType() == GeomAbs_Cone
    )
    expected_indices = source.triangles_of_face(native_index)
    assert set(cone.face_indices) == set(expected_indices)
    assert len(cone.surface_patches) == 1
    patch = cone.surface_patches[0]
    assert patch.source == "native" and patch.kind == "cone"
    assert set(patch.face_indices) == set(expected_indices)
    assert patch.params["apex"] == pytest.approx(expected_apex, abs=EPS_GEOM)
    assert patch.params["axis"] == pytest.approx(expected_axis, abs=EPS_GEOM)
    assert patch.params["half_angle"] == pytest.approx(math.pi / 4.0, abs=EPS_GEOM)
    mesh = as_mesh_data(source)
    points = mesh.raw.vertices[mesh.raw.faces[list(patch.face_indices)]].reshape(-1, 3)
    relative = points - expected_apex
    axial = relative @ np.asarray(expected_axis)
    radial = np.linalg.norm(relative - axial[:, None] * expected_axis, axis=1)
    assert np.all(axial > 0.0)
    assert radial == pytest.approx(axial, abs=EPS_GEOM)
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("deviation", [0.03, 0.15])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("placement", ["shift", "mirror"])
@pytest.mark.parametrize("first", [-3.0, -math.sqrt(2.0) - EPS_GEOM / 4.0])
def test_native_cone_trim_across_both_nappes_stays_without_a_single_cone_claim(
    deviation: float, sign: float, placement: str, first: float
) -> None:
    """Eine von OCCT gültig gelesene Doppelnappe darf keine einzige gerichtete Nappe vorspiegeln."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone

    source, _ = _trimmed_native_cone(sign, (first, 1.0), deviation, placement)
    before = _bytes(source.shape)
    native_index = next(
        index
        for index, face in enumerate(source.faces())
        if BRepAdaptor_Surface(face).GetType() == GeomAbs_Cone
    )
    mantle_indices = set(source.triangles_of_face(native_index))
    assert mantle_indices
    found = features_of(source)
    assert not any(feature.kind == "cone" for feature in found.values())
    assert any(feature.kind == "curved_face" for feature in found.values())
    assert not any(
        mantle_indices.intersection(patch.face_indices)
        for feature in found.values()
        for patch in feature.surface_patches
    )
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("deviation", [0.03, 0.15])
@pytest.mark.parametrize(
    "radii,height",
    [((0.0, 4.0), 8.0), ((4.0, 0.0), 8.0), ((0.0, 1.0), math.pi), ((1.0, 0.0), math.pi)],
)
def test_native_cone_trim_ending_at_the_apex_keeps_its_carrier(
    deviation: float, radii: tuple[float, float], height: float
) -> None:
    """Der singuläre Spitzenrand eines gewöhnlichen Kegels bleibt ein eindeutiger Bezug."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    source = Solid(BRepPrimAPI_MakeCone(*radii, height).Shape(), deviation)
    before = _bytes(source.shape)
    expected_apex = (0.0, 0.0, 0.0 if radii[1] else height)
    apex_vertices = []
    edges = TopExp_Explorer(source.shape, TopAbs_EDGE)
    while edges.More():
        edge = TopoDS.Edge(edges.Current())
        if BRep_Tool.Degenerated_s(edge):
            vertices = TopExp_Explorer(edge, TopAbs_VERTEX)
            while vertices.More():
                apex_vertices.append(BRep_Tool.Pnt_s(TopoDS.Vertex(vertices.Current())).Coord())
                vertices.Next()
        edges.Next()
    assert apex_vertices
    assert all(
        np.linalg.norm(np.asarray(point) - expected_apex) <= math.ulp(height) + math.ulp(max(radii))
        for point in apex_vertices
    )
    found = features_of(source)
    cones = [feature for feature in found.values() if feature.kind == "cone"]
    assert len(cones) == 1
    assert cones[0].params["diameter"] == pytest.approx(2.0 * max(radii), abs=EPS_GEOM)
    assert len(cones[0].surface_patches) == 1
    patch = cones[0].surface_patches[0]
    assert patch.source == "native" and patch.kind == "cone"
    assert patch.params["axis"] == pytest.approx((0.0, 0.0, 1.0 if radii[1] else -1.0))
    assert set(patch.face_indices) == set(cones[0].face_indices)
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("deviation", [0.03, 0.15])
@pytest.mark.parametrize("kind", ["cylinder", "cone", "sphere", "torus", "rounded"])
def test_native_carriers_cover_original_facets_without_using_selection_centres(
    kind: str, deviation: float
) -> None:
    """Träger stammen aus der Originalform, auch an kugeligen und zylindrischen Ecken."""
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeCone,
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakeSphere,
        BRepPrimAPI_MakeTorus,
    )

    from app.core.brep import edit
    from app.core.perceive.surfaces import valid_patch

    if kind == "rounded":
        source = edit.fillet(edit.box(10.0, 16.0, 20.0), 2.0, "all")
        source = Solid(source.shape, deviation)
    else:
        shape = {
            "cylinder": lambda: BRepPrimAPI_MakeCylinder(8.0, 12.0).Shape(),
            "cone": lambda: BRepPrimAPI_MakeCone(8.0, 4.0, 12.0).Shape(),
            "sphere": lambda: BRepPrimAPI_MakeSphere(8.0).Shape(),
            "torus": lambda: BRepPrimAPI_MakeTorus(17.0, 3.0).Shape(),
        }[kind]()
        source = Solid(shape, deviation)
    before = _bytes(source.shape)
    features = features_of(source)
    mesh = as_mesh_data(source)
    covered = set()
    seen_kinds = set()
    differing_centres = set()
    for feature in features.values():
        for patch in feature.surface_patches:
            assert patch.source == "native"
            assert valid_patch(
                patch, face_count=source.triangle_count, allowed_indices=feature.face_indices
            )
            covered.update(patch.face_indices)
            seen_kinds.add(patch.kind)
            points = mesh.raw.vertices[mesh.raw.faces[list(patch.face_indices)]].reshape(-1, 3)
            if patch.kind == "cone":
                assert patch.params["apex"] == pytest.approx((0.0, 0.0, 24.0))
                assert patch.params["axis"] == pytest.approx((0.0, 0.0, -1.0))
                assert patch.params["half_angle"] == pytest.approx(math.atan(1.0 / 3.0))
                relative = points - patch.params["apex"]
                axial = relative @ np.asarray(patch.params["axis"])
                assert np.all(axial > 0.0)
                radial = np.linalg.norm(relative[:, :2], axis=1)
                assert radial == pytest.approx(axial / 3.0, abs=EPS_GEOM)
            elif patch.kind in {"cylinder", "sphere"}:
                relative = points - patch.params["centre"]
                distances = (
                    np.linalg.norm(np.cross(relative, patch.params["axis"]), axis=1)
                    if patch.kind == "cylinder"
                    else np.linalg.norm(relative, axis=1)
                )
                assert distances == pytest.approx(patch.params["radius"], abs=EPS_GEOM)
                if (
                    feature.kind == "fillet"
                    and np.linalg.norm(
                        np.asarray(feature.params["centre"]) - patch.params["centre"]
                    )
                    > EPS_GEOM
                ):
                    differing_centres.add(patch.kind)
    assert covered == set(range(source.triangle_count))
    if kind == "rounded":
        assert seen_kinds == {"plane", "cylinder", "sphere"}
        assert differing_centres == {"cylinder", "sphere"}
    else:
        assert kind in seen_kinds
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("deviation", [0.03, 0.15])
@pytest.mark.parametrize("lower", [0.0, math.pi / 6.0])
@pytest.mark.parametrize("recess", [False, True])
@pytest.mark.parametrize("placement", ["shift", "oblique", "mirror"])
@pytest.mark.parametrize("nurbs", [False, True])
def test_spherical_sections_keep_the_carrier_centre_and_oriented_material_side(
    deviation: float, lower: float, recess: bool, placement: str, nurbs: bool
) -> None:
    """Kalottenzentrum und Materialseite hängen weder am Flächenschwerpunkt noch an der Lage."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert, BRepBuilderAPI_Transform
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeSphere
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.GeomAbs import GeomAbs_BSplineSurface, GeomAbs_Sphere
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    radius = 8.123456789
    shape = BRepPrimAPI_MakeSphere(radius, lower, math.pi / 2.0).Shape()
    bottom = radius * math.sin(lower)
    top = radius
    expected_volume = math.pi * (radius**2 * (top - bottom) - (top**3 - bottom**3) / 3)
    if recess:
        top = (radius + bottom) / 2.0
        stock = BRepPrimAPI_MakeBox(gp_Pnt(-12, -12, bottom - 2), 24, 24, top - bottom + 2)
        cut = boolean_builder("difference", stock.Shape(), shape)
        cut.Build()
        assert cut.IsDone()
        shape = cut.Shape()
        expected_volume = 24**2 * (top - bottom + 2) - math.pi * (
            radius**2 * (top - bottom) - (top**3 - bottom**3) / 3
        )
    transform = gp_Trsf()
    if placement == "oblique":
        transform.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(1, 2, -0.5)), 0.73)
    elif placement == "mirror":
        transform.SetMirror(gp_Ax2(gp_Pnt(), gp_Dir(1, 2, -0.5)))
    transform.SetTranslationPart(gp_Vec(37, -19, 83))
    shape = BRepBuilderAPI_Transform(shape, transform, True).Shape()
    source = Solid(shape, deviation)
    sphere_indices = [
        index
        for index, face in enumerate(source.faces())
        if BRepAdaptor_Surface(face).GetType() == GeomAbs_Sphere
    ]
    assert len(sphere_indices) == 1
    if nurbs:
        conversion = BRepBuilderAPI_NurbsConvert(source.shape, True)
        converted_faces = ShapeMap()
        TopExp.MapShapes_s(conversion.Shape(), TopAbs_FACE, converted_faces)
        sphere_indices = [
            converted_faces.FindIndex(conversion.ModifiedShape(source.faces()[index])) - 1
            for index in sphere_indices
        ]
        assert all(index >= 0 for index in sphere_indices)
        source = Solid(conversion.Shape(), deviation)
        sphere_indices = [source._copied_faces[index] for index in sphere_indices]
        assert all(
            BRepAdaptor_Surface(source.faces()[index]).GetType() == GeomAbs_BSplineSurface
            for index in sphere_indices
        )
    assert BRepCheck_Analyzer(source.shape).IsValid()
    assert source.volume == pytest.approx(expected_volume, rel=1e-10)
    before = _bytes(source.shape)
    spheres = [feature for feature in features_of(source).values() if feature.kind == "sphere"]
    assert len(spheres) == 1
    sphere = spheres[0]
    assert sphere.params["diameter"] == pytest.approx(2 * radius, abs=EPS_GEOM, rel=0)
    assert sphere.params["centre"] == pytest.approx((37, -19, 83), abs=EPS_GEOM, rel=0)
    assert sphere.params["recess"] is recess
    for name in ("diameter", "centre"):
        assert measure_status(sphere, name).source == "native"
        assert measure_status(sphere, name).state == "exact"
    from app.core.geom.prepare_ops import _feature_solid

    tool = _feature_solid(sphere, tuple(sphere.params["centre"]), oversize=0.0)
    distances = np.linalg.norm(np.asarray(tool.raw.vertices) - (37, -19, 83), axis=1)
    assert distances == pytest.approx(radius, abs=EPS_GEOM, rel=0)
    expected_faces = {
        triangle for index in sphere_indices for triangle in source.triangles_of_face(index)
    }
    assert expected_faces and set(sphere.face_indices) == expected_faces
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("kind", ["cone", "sphere", "torus"])
@pytest.mark.parametrize("deviation", [0.03, 0.15])
def test_native_and_mesh_round_twins_keep_independent_construction_measures(
    kind: str, deviation: float
) -> None:
    """Beide Erkennungswege lesen dieselben ungerundeten Sollwerte am schräg gestellten Körper."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeTorus
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

    from app.core.perceive.features import detect

    if kind == "cone":
        shape = BRepPrimAPI_MakeCone(8.123456789, 4.321987654, 12.3456789).Shape()
        expected = {
            "diameter": 16.246913578,
            "angle": math.degrees(2 * math.atan((8.123456789 - 4.321987654) / 12.3456789)),
        }
    elif kind == "sphere":
        shape = BRepPrimAPI_MakeSphere(8.123456789, 0.0, math.pi / 2).Shape()
        expected = {"diameter": 16.246913578}
    else:
        shape = BRepPrimAPI_MakeTorus(17.123456789, 3.23456789).Shape()
        expected = {"diameter": 34.246913578, "tube_diameter": 6.46913578}
    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(1, 2, -0.5)), 0.73)
    transform.SetTranslationPart(gp_Vec(37, -19, 83))
    source = Solid(BRepBuilderAPI_Transform(shape, transform, True).Shape(), deviation)
    before = _bytes(source.shape)
    mesh = as_mesh_data(source)
    vertices, triangles = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    wanted = {"cone": GeomAbs_Cone, "sphere": GeomAbs_Sphere, "torus": GeomAbs_Torus}[kind]
    expected_faces = {
        triangle
        for index, face in enumerate(source.faces())
        if BRepAdaptor_Surface(face).GetType() == wanted
        for triangle in source.triangles_of_face(index)
    }
    for representation, features in (("native", features_of(source)), ("fit", detect(mesh))):
        found = [feature for feature in features.values() if feature.kind == kind]
        assert len(found) == 1
        feature = found[0]
        for name, value in expected.items():
            assert feature.params[name] == pytest.approx(value, abs=EPS_GEOM, rel=0)
            assert measure_status(feature, name).source == representation
        assert feature.params["centre"] == pytest.approx((37, -19, 83), abs=EPS_GEOM, rel=0)
        assert feature.params["recess"] is False
        assert set(feature.face_indices) == expected_faces
    np.testing.assert_array_equal(mesh.raw.vertices, vertices)
    np.testing.assert_array_equal(mesh.raw.faces, triangles)
    assert _bytes(source.shape) == before


def _spherical_spline() -> Any:
    """Eine halbe rationale Kugelhaut mit analytisch vorgegebenem Radius."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.GeomAbs import GeomAbs_Sphere
    from OCP.TopoDS import TopoDS

    original = Solid(BRepPrimAPI_MakeSphere(8.123456789, 0.0, math.pi / 2).Shape())
    face = next(
        face for face in original.faces() if BRepAdaptor_Surface(face).GetType() == GeomAbs_Sphere
    )
    converted = TopoDS.Face(BRepBuilderAPI_NurbsConvert(face, True).Shape())
    return BRepAdaptor_Surface(converted).BSpline().Copy()


def test_nurbs_sphere_keeps_its_measures_at_remote_coordinates() -> None:
    """Der NURBS-Kandidat wird lokal bestimmt, sein Ergebnis bleibt in Weltkoordinaten."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    centre = (1000007.0, -3000003.0, 5000005.0)
    shape = BRepPrimAPI_MakeSphere(
        gp_Ax2(gp_Pnt(*centre), gp_Dir(1, 2, 3)), 8.123456789, 0.0, math.pi / 2
    ).Shape()
    source = Solid(BRepBuilderAPI_NurbsConvert(shape, True).Shape())
    before = _bytes(source.shape)
    found = [feature for feature in features_of(source).values() if feature.kind == "sphere"]
    assert len(found) == 1
    assert found[0].params["diameter"] == pytest.approx(16.246913578, abs=EPS_GEOM, rel=0)
    assert found[0].params["centre"] == pytest.approx(centre, abs=EPS_GEOM, rel=0)
    assert found[0].params["recess"] is False
    assert _bytes(source.shape) == before


def test_narrow_nurbs_bulge_cannot_hide_behind_a_sphere_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selbst ein falscher Kandidat mit Abstand null muss den vollständigen Nachweis bestehen."""
    from types import SimpleNamespace

    from OCP import ShapeAnalysis
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt

    from app.core.brep.canonical import describe

    spline = _spherical_spline()
    for knot in (0.2, 0.2001, 0.2002):
        spline.InsertUKnot(knot, spline.UDegree(), EPS_GEOM)
    knots = [
        spline.UKnot(index)
        for index in range(1, spline.NbUKnots() + 1)
        for _ in range(spline.UMultiplicity(index))
    ]
    row = next(
        index + 1
        for index in range(spline.NbUPoles())
        if knots[index] >= 0.2 and knots[index + spline.UDegree() + 1] <= 0.2002
    )
    point = np.asarray(spline.Pole(row, 2).Coord())
    spline.SetPole(row, 2, gp_Pnt(*(point + 0.04 * point / np.linalg.norm(point))))
    measured = spline.Value(0.20005, math.pi / 4)
    assert abs(np.linalg.norm(measured.Coord()) - 8.123456789) > EPS_GEOM
    local_centre = -np.asarray(spline.Pole(1, 1).Coord())

    def wrong_sphere(tolerance: float, sphere: Any) -> bool:
        """Nur der Kandidat ist unzuverlässig; die ganze Trägerprüfung bleibt unverändert."""
        sphere.SetRadius(8.123456789)
        sphere.SetPosition(gp_Ax3(gp_Pnt(*local_centre), gp_Dir(0, 0, 1)))
        return True

    face = BRepBuilderAPI_MakeFace(spline, EPS_GEOM).Face()
    before = _bytes(face)
    monkeypatch.setattr(
        ShapeAnalysis,
        "ShapeAnalysis_CanonicalRecognition",
        lambda face: SimpleNamespace(
            IsPlane=lambda tolerance, plane: False,
            IsCylinder=lambda tolerance, cylinder: False,
            IsSphere=wrong_sphere,
            GetGap=lambda: 0.0,
            GetStatus=lambda: 0,
        ),
    )
    assert describe(face) is None
    assert _bytes(face) == before


@pytest.mark.parametrize("kind", ["surface", "volume"])
def test_nurbs_spherical_integrals_are_conditioned_at_a_remote_origin(kind: Any) -> None:
    """Fläche, Volumen und Schwerpunkt der geschlossenen Halbkugel sind analytisch bekannt."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.properties import INTEGRAL_RELATIVE_ERROR, properties

    centre = np.array((1000007.0, -3000003.0, 5000005.0))
    axis = np.array((1.0, 2.0, 3.0)) / math.sqrt(14)
    radius = 8.123456789
    shape = BRepPrimAPI_MakeSphere(
        gp_Ax2(gp_Pnt(*centre), gp_Dir(*axis)), radius, 0.0, math.pi / 2
    ).Shape()
    source = Solid(BRepBuilderAPI_NurbsConvert(shape, True).Shape())
    before = _bytes(source.shape)
    measured = properties(source.shape, kind)
    expected = 3 * math.pi * radius**2 if kind == "surface" else 2 * math.pi * radius**3 / 3
    shift = radius / 3 if kind == "surface" else 3 * radius / 8
    assert measured.mass == pytest.approx(expected, rel=INTEGRAL_RELATIVE_ERROR, abs=0)
    assert measured.centre == pytest.approx(centre + axis * shift, abs=EPS_GEOM, rel=0)
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("interrupt", [False, True])
def test_spherical_proof_respects_work_limit_and_cancellation(
    monkeypatch: pytest.MonkeyPatch, interrupt: bool
) -> None:
    """Eine unvollständige Flächenprüfung veröffentlicht keine sichere Kugelbeschreibung."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    from app.core.brep import canonical
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    face = BRepBuilderAPI_MakeFace(_spherical_spline(), EPS_GEOM).Face()
    before = _bytes(face)
    signal = CancelSignal()
    if interrupt:
        original = canonical._product

        def stop(first: Any, second: Any, token: Any) -> Any:
            assert token is signal
            result = original(first, second, token)
            signal.cancel()
            return result

        monkeypatch.setattr(canonical, "_product", stop)
        with pytest.raises(OperationCancelled):
            canonical.describe(face, cancelled=signal)
    else:
        monkeypatch.setattr(canonical, "_MAX_COEFFICIENT_PRODUCTS", 0)
        assert canonical.describe(face) is None
    assert _bytes(face) == before


def _ring(angle: float = math.tau, *, recess: bool = False) -> Solid:
    """Ring R17/r3 an einer ausdrücklich verschobenen Achse, gegebenenfalls als Kehle."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    maker = BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(7, -3, 5), gp_Dir(0, 0, 1)), 17, 3, angle)
    shape = maker.Shape()
    if recess:
        # Die obere Halb-Röhre ist offen; es entsteht kein geschlossener Innenraum.
        stock = BRepPrimAPI_MakeBox(gp_Pnt(-20, -30, -5), 55, 55, 10).Shape()
        cut = boolean_builder("difference", stock, shape)
        cut.Build()
        assert cut.IsDone()
        shape = cut.Shape()
    return Solid(shape)


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("kind", ["cone", "sphere", "torus"])
def test_step_round_surface_keeps_its_measure_source_through_cache_history_and_reopening(
    quality: str, kind: str, tmp_path: Any, profile: Any
) -> None:
    """Echte STEP-Auswertung und Folgeoperation führen Wert und Herkunft gemeinsam nach."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeTorus

    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import ResultCache
    from app.core.scene.project import ProjectSources, load, new_project, save
    from app.core.types import Source

    load_operations()
    radius = 8.123456789
    if kind == "cone":
        shape = BRepPrimAPI_MakeCone(radius, 4.321987654, 12.3456789).Shape()
        expected = {
            "diameter": 2 * radius,
            "angle": math.degrees(2 * math.atan((radius - 4.321987654) / 12.3456789)),
        }
    elif kind == "sphere":
        shape = BRepPrimAPI_MakeSphere(radius, 0.0, math.pi / 2.0).Shape()
        expected = {"diameter": 2 * radius}
    else:
        shape = BRepPrimAPI_MakeTorus(17.123456789, 3.23456789).Shape()
        expected = {"diameter": 34.246913578, "tube_diameter": 6.46913578}
    original = Solid(shape)
    original_bytes = _bytes(original.shape)
    project = new_project("centauri-carbon-2", "petg")
    payload = step.write(original)
    assert _bytes(original.shape) == original_bytes
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/round.step", sha256=""
    )
    history = History(project.document)
    history.apply("Rundkörper laden", [OperationDraft(op="load_step", params={"source": "src_1"})])
    cache = ResultCache()

    def checked(
        current: Any,
        centre: tuple[float, float, float],
        remembered: Any = None,
        fidelity: Any = quality,
    ) -> str:
        """Unabhängige Sollmaße und Quellen am tatsächlich veröffentlichten Ergebnis prüfen."""
        result = evaluate(
            current.document,
            profile,
            quality=fidelity,
            sources=ProjectSources(current),
            cache=remembered,
        )
        assert result.complete
        entry = result.scene.objects["obj_1"]
        assert entry.kind == "brep"
        matching = [feature for feature in entry.features.values() if feature.kind == kind]
        assert len(matching) == 1
        surface = matching[0]
        assert surface.params["centre"] == pytest.approx(centre, abs=EPS_GEOM, rel=0)
        for name, value in expected.items():
            assert surface.params[name] == pytest.approx(value, abs=EPS_GEOM, rel=0)
            assert measure_status(surface, name).source == "native"
        assert surface.params["recess"] is False
        assert measure_status(surface, "centre").source == "native"
        assert surface.face_indices and max(surface.face_indices) < entry.mesh.triangle_count
        assert current.sources["src_1"] == payload
        assert _bytes(original.shape) == original_bytes
        return surface.id

    original_id = checked(project, (0, 0, 0), cache)
    history.apply(
        "Rundkörper verschieben",
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"dx": 7.0, "dy": -3.0, "dz": 5.0, "keep_on_bed": False},
            )
        ],
    )
    assert checked(project, (7, -3, 5), cache) == original_id
    assert checked(project, (7, -3, 5), cache) == original_id
    other_quality = "fine" if quality == "draft" else "draft"
    assert checked(project, (7, -3, 5), cache, other_quality) == original_id
    assert checked(project, (7, -3, 5), cache) == original_id
    reopened = load(save(project, tmp_path / "round.solidon"))
    assert checked(reopened, (7, -3, 5)) == original_id
    restored = History(reopened.document)
    restored.undo()
    assert checked(reopened, (0, 0, 0)) == original_id
    restored.redo()
    assert checked(reopened, (7, -3, 5)) == original_id


@pytest.mark.parametrize("deviation", [0.03, 0.15])
@pytest.mark.parametrize("angle", [math.tau, math.pi * 1.5])
@pytest.mark.parametrize("recess", [False, True])
def test_native_torus_reads_exact_measures_and_selected_original_faces(
    deviation: float, angle: float, recess: bool
) -> None:
    """Ring und offene Ringkehle tragen dieselben Maße, auch nach einer STEP-Runde."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Torus

    source = Solid(step.read(step.write(_ring(angle, recess=recess))).shape, deviation)
    before = _bytes(source.shape)
    native = [feature for feature in features_of(source).values() if feature.kind == "torus"]
    assert len(native) == 1
    ring = native[0]
    assert ring.params["diameter"] == pytest.approx(34, abs=EPS_GEOM)
    assert ring.params["tube_diameter"] == pytest.approx(6, abs=EPS_GEOM)
    assert ring.params["centre"] == pytest.approx((7, -3, 5), abs=EPS_GEOM)
    assert ring.params["axis"] == pytest.approx((0, 0, 1), abs=EPS_GEOM)
    assert ring.params["recess"] is recess
    expected = {
        triangle
        for index, face in enumerate(source.faces())
        if BRepAdaptor_Surface(face).GetType() == GeomAbs_Torus
        for triangle in source.triangles_of_face(index)
    }
    assert expected
    assert set(ring.face_indices) == expected
    assert _bytes(source.shape) == before
    mesh = detect_tori(as_mesh_data(source))
    assert len(mesh) == 1
    assert mesh[0].params["recess"] is recess
    assert mesh[0].params["diameter"] == pytest.approx(34, abs=deviation * 2)
    assert mesh[0].params["tube_diameter"] == pytest.approx(6, abs=deviation * 2)


@pytest.mark.parametrize("deviation", [0.03, 0.15])
def test_elliptic_wall_is_a_curved_face_without_invented_cylinder(deviation: float) -> None:
    """Ein elliptischer Mantel bleibt wählbar, ohne einen Kreisradius vorzutäuschen."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_GTrsf, gp_Mat, gp_XYZ
    from scipy.special import ellipe

    original = BRepPrimAPI_MakeCylinder(3, 8).Shape()
    affine = gp_GTrsf(gp_Mat(2, 0, 0, 0, 1, 0, 0, 0, 1), gp_XYZ(7, -3, 5))
    source = Solid(BRepBuilderAPI_GTransform(original, affine, True).Shape(), deviation)
    before = _bytes(source.shape)
    found = features_of(source)
    assert {feature.kind for feature in found.values()} == {"face", "curved_face"}
    curved = [feature for feature in found.values() if feature.kind == "curved_face"]
    assert len(curved) == 1
    wall = curved[0]
    assert wall.params["area"] == pytest.approx(192 * ellipe(0.75), rel=1e-10)
    assert wall.params["centre"] == pytest.approx((7, -3, 9), abs=EPS_GEOM)
    assert wall.params["inner"] is False
    normals = source.raw.face_normals[list(wall.face_indices)]
    assert np.all(np.abs(normals[:, 2]) <= EPS_GEOM)
    claimed = {index for feature in found.values() for index in feature.face_indices}
    assert claimed == set(range(source.triangle_count))
    twin = detect_curved_faces(
        as_mesh_data(source),
        {key: feature for key, feature in found.items() if feature.kind == "face"},
    )
    assert len(twin) == 1
    assert set(twin[0].face_indices) == set(wall.face_indices)
    assert _bytes(source.shape) == before


def test_a_ring_split_at_native_seams_keeps_one_complete_feature() -> None:
    """Zusätzliche native Nähte erzeugen weder doppelte Ringe noch eine halbe Auswahl."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.ShapeUpgrade import ShapeUpgrade_ShapeDivideClosed

    source = _ring()
    splitter = ShapeUpgrade_ShapeDivideClosed(source.shape)
    splitter.SetNbSplitPoints(2)
    assert splitter.Perform()
    divided = Solid(splitter.Result())
    assert BRepCheck_Analyzer(divided.shape).IsValid()
    assert divided.face_count > source.face_count
    assert divided.volume == pytest.approx(2 * math.pi**2 * 17 * 3**2, rel=1e-10)
    features = features_of(divided)
    assert len(features) == 1
    ring = next(iter(features.values()))
    assert ring.kind == "torus"
    assert set(ring.face_indices) == set(range(divided.triangle_count))


def test_disconnected_fragments_on_the_same_torus_remain_separate_features() -> None:
    """Gleiche Achse und Radien ersetzen keine tatsächliche Verbindung."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    ring = _ring()
    tool = BRepPrimAPI_MakeBox(gp_Pnt(-20, -5, 0), 55, 4, 10).Shape()
    cut = boolean_builder("difference", ring.shape, tool)
    cut.Build()
    assert cut.IsDone()
    source = Solid(cut.Shape())
    assert source.solid_count == 2
    features = [feature for feature in features_of(source).values() if feature.kind == "torus"]
    assert len(features) == 2
    assert not set(features[0].face_indices).intersection(features[1].face_indices)


def test_curved_surface_detection_obeys_cancellation_before_mesh_access() -> None:
    """Ein abgebrochener Restflächenauftrag greift nicht auf die große Tessellierung zu."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    signal.cancel()
    with pytest.raises(OperationCancelled):
        detect_curved_faces(None, {}, check_cancelled=signal.raise_if_cancelled)  # type: ignore[arg-type]


@pytest.mark.parametrize("angle", [math.tau, math.pi * 1.5])
@pytest.mark.parametrize("recess", [False, True])
def test_nurbs_ring_keeps_its_exact_measures_without_replacing_the_surface(
    angle: float, recess: bool
) -> None:
    """Der Speichertyp allein macht aus einem echten Ring keine freie Rundfläche."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.GeomAbs import GeomAbs_BSplineSurface

    original = _ring(angle, recess=recess)
    source = Solid(BRepBuilderAPI_NurbsConvert(original.shape, True).Shape())
    assert any(
        BRepAdaptor_Surface(face).GetType() == GeomAbs_BSplineSurface for face in source.faces()
    )
    before = _bytes(source.shape)
    features = features_of(source)
    rings = [feature for feature in features.values() if feature.kind == "torus"]
    assert len(rings) == 1
    ring = rings[0]
    assert ring.params["diameter"] == pytest.approx(34.0, abs=EPS_GEOM)
    assert ring.params["tube_diameter"] == pytest.approx(6.0, abs=EPS_GEOM)
    assert ring.params["centre"] == pytest.approx((7.0, -3.0, 5.0), abs=EPS_GEOM)
    assert ring.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=EPS_GEOM)
    assert ring.params["recess"] is recess
    assert _bytes(source.shape) == before


def test_narrow_nurbs_bulge_cannot_hide_between_torus_samples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein plausibler Kandidat ersetzt keinen Nachweis über enge Knotenspannen."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_NurbsConvert
    from OCP.gp import gp_Pnt

    from app.core.brep.canonical import describe
    from app.core.perceive import features as detection

    source = Solid(BRepBuilderAPI_NurbsConvert(_ring().shape, True).Shape())
    spline = BRepAdaptor_Surface(source.faces()[0]).BSpline().Copy()
    for knot in (0.2, 0.2001, 0.2002):
        spline.InsertUKnot(knot, spline.UDegree(), EPS_GEOM)
    knots = [
        spline.UKnot(index)
        for index in range(1, spline.NbUKnots() + 1)
        for _ in range(spline.UMultiplicity(index))
    ]
    row = next(
        index + 1
        for index in range(spline.NbUPoles())
        if knots[index] >= 0.2 and knots[index + spline.UDegree() + 1] <= 0.2002
    )
    point = spline.Pole(row, 3)
    spline.SetPole(row, 3, gp_Pnt(point.X(), point.Y(), point.Z() + 0.04))
    face = BRepBuilderAPI_MakeFace(spline, EPS_GEOM).Face()
    before = _bytes(face)
    monkeypatch.setattr(
        detection,
        "fit_torus_samples",
        lambda _points, _normals: detection.TorusFit((0, 0, 1), (7, -3, 5), 17, 3, 0, False),
    )
    assert describe(face) is None
    assert _bytes(face) == before


def test_torus_proof_preserves_its_explicit_work_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine erschöpfte Koeffizientenprüfung gibt keine sichere Ringbeschreibung aus."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    from app.core.brep import canonical

    source = Solid(BRepBuilderAPI_NurbsConvert(_ring().shape, True).Shape())
    monkeypatch.setattr(canonical, "_MAX_COEFFICIENT_PRODUCTS", 0)
    assert canonical.describe(source.faces()[0]) is None


@pytest.mark.parametrize("nurbs", [False, True])
def test_ring_measures_follow_a_remote_oblique_native_axis(nurbs: bool) -> None:
    """Weltkoordinaten und eine schräge Achse ändern weder Ringmaß noch Materialseite."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    axis = np.asarray((1.0, 2.0, 3.0)) / math.sqrt(14)
    centre = (1000007.0, -3000003.0, 5000005.0)
    shape = BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(*centre), gp_Dir(*axis)), 17, 3).Shape()
    if nurbs:
        shape = BRepBuilderAPI_NurbsConvert(shape, True).Shape()
    source = Solid(shape)
    found = list(features_of(source).values())
    assert len(found) == 1 and found[0].kind == "torus"
    assert found[0].params["diameter"] == pytest.approx(34.0, abs=EPS_GEOM)
    assert found[0].params["tube_diameter"] == pytest.approx(6.0, abs=EPS_GEOM)
    assert found[0].params["centre"] == pytest.approx(centre, abs=EPS_GEOM)
    assert found[0].params["axis"] == pytest.approx(axis, abs=EPS_GEOM)
    assert found[0].params["recess"] is False
