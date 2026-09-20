"""Native Ring- und Freiformflächen behalten Maße und wirkliche Auswahlgrenzen."""

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
from app.core.units import EPS_GEOM

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")


def _bytes(shape: Any) -> bytes:
    """Die unveränderte native Eingabe einschließlich ihrer Geometrie festhalten."""
    from OCP.BRepTools import BRepTools

    stream = io.BytesIO()
    BRepTools.Write_s(shape, stream)
    return stream.getvalue()


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
