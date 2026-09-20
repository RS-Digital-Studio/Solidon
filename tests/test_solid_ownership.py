"""Exakte Körper besitzen ihre Form; Folgearbeit verändert keinen Eingabezustand."""

from __future__ import annotations

import importlib
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from app.core.brep import edit, profiles
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, available, tessellate
from app.core.units import EPS_GEOM

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")


def _triangulations(solid: Solid) -> tuple[tuple[int, int], ...]:
    """Die native Vernetzung jeder Eingabefläche, ohne selbst zu vernetzen."""
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    result = []
    for face in solid.faces():
        triangulation = BRep_Tool.Triangulation_s(face, TopLoc_Location())
        result.append(
            (0, 0)
            if triangulation is None
            else (triangulation.NbNodes(), triangulation.NbTriangles())
        )
    return tuple(result)


def test_a_solid_owns_a_copy_of_the_supplied_shape() -> None:
    """Eine nachträglich versetzte fremde Shape kann den Solid nicht verschieben."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.TopLoc import TopLoc_Location

    original = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()
    solid = Solid(original)
    assert not solid.shape.IsPartner(original)
    shift = gp_Trsf()
    shift.SetTranslation(gp_Vec(7.123456789, -3.0, 2.0))
    original.Move(TopLoc_Location(shift))
    assert solid.bounds.minimum == pytest.approx((0.0, 0.0, 0.0), abs=EPS_GEOM, rel=0.0)
    assert solid.bounds.maximum == pytest.approx((10.0, 20.0, 30.0), abs=EPS_GEOM, rel=0.0)


def test_a_second_quality_wrapper_does_not_share_native_faces() -> None:
    """Der bestehende Weg brep_to_mesh darf nicht denselben TShape weiterreichen."""
    original = edit.cylinder(12.0, 8.0)
    other = Solid(original.shape, deflection=0.01)
    assert not other.shape.IsPartner(original.shape)
    assert all(
        not first.IsPartner(second) for first in original.faces() for second in other.faces()
    )
    assert other.bounds.minimum == pytest.approx(original.bounds.minimum, abs=EPS_GEOM, rel=0.0)
    assert other.bounds.maximum == pytest.approx(original.bounds.maximum, abs=EPS_GEOM, rel=0.0)


def test_canonical_recognition_does_not_rewrite_native_nurbs_geometry() -> None:
    """Polwerte, Trimmkurven, Topologie und native Vernetzung bleiben bytegleich."""
    import io

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepTools import BRepTools

    body = edit.cut_bore(
        edit.box(40.0, 30.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=20.0,
    )
    source = Solid(BRepBuilderAPI_NurbsConvert(body.shape, True).Shape())
    before = io.BytesIO()
    BRepTools.Write_s(source.shape, before)
    assert len(features_of(source)) == 7
    assert len(profiles._planar_faces(source)) == 6
    after = io.BytesIO()
    BRepTools.Write_s(source.shape, after)
    assert after.getvalue() == before.getvalue()
    assert all(counts == (0, 0) for counts in _triangulations(source))


def test_unwrapping_surface_trims_is_read_only_bounded_and_cancellable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine tatsächliche Trimmhülle teilt Abbruch und Grenzen mit allen nativen Verbrauchern."""
    import io

    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_NurbsConvert
    from OCP.BRepTools import BRepTools
    from OCP.Geom import Geom_RectangularTrimmedSurface

    from app.core.brep import kernel
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    body = Solid(BRepBuilderAPI_NurbsConvert(edit.cylinder(6.0, 8.0).shape, True).Shape())
    basis = BRep_Tool.Surface_s(body.faces()[0]).Copy()
    trimmed = Geom_RectangularTrimmedSurface(basis, 1.0, 3.0, 1.0, 7.0)
    face = BRepBuilderAPI_MakeFace(trimmed, EPS_GEOM).Face()
    before = io.BytesIO()
    BRepTools.Write_s(face, before)

    class AfterOneWrapper:
        """Bricht nach dem ersten echten nativen Entpackschritt ab."""

        def __init__(self) -> None:
            self.calls = 0
            self.signal = CancelSignal()

        def raise_if_cancelled(self) -> None:
            self.calls += 1
            if self.calls == 2:
                self.signal.cancel()
            self.signal.raise_if_cancelled()

        @property
        def is_cancelled(self) -> bool:
            return self.signal.is_cancelled

    cancelled = AfterOneWrapper()
    with pytest.raises(OperationCancelled):
        kernel.untrimmed_surface(trimmed, cancelled=cancelled)
    assert cancelled.calls == 2
    with monkeypatch.context() as isolated:
        isolated.setattr(kernel, "_MAX_SURFACE_WRAPPERS", 0)
        assert kernel.untrimmed_surface(trimmed) is None
    original = kernel.untrimmed_surface(trimmed)
    assert original is not None
    assert original.Value(2.0, 4.0).Coord() == pytest.approx(
        basis.Value(2.0, 4.0).Coord(), abs=EPS_GEOM
    )
    after = io.BytesIO()
    BRepTools.Write_s(face, after)
    assert after.getvalue() == before.getvalue()


@pytest.mark.parametrize("nurbs", [False, True])
@pytest.mark.parametrize("operation", ["unround", "reround"])
def test_rounding_edits_preserve_all_native_source_geometry(nurbs: bool, operation: str) -> None:
    """Defeaturing darf auch Polgrad und Knoten benachbarter NURBS-Ebenen nicht verändern."""
    import io
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepTools import BRepTools

    from app.core.brep.properties import INTEGRAL_RELATIVE_ERROR

    source = edit.fillet(edit.box(40.0, 30.0, 20.0), 3.0, "vertical")
    if nurbs:
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    feature = next(value for value in features_of(source).values() if value.kind == "fillet")
    before = io.BytesIO()
    BRepTools.Write_s(source.shape, before)
    if operation == "unround":
        result = edit.unround(source, feature.params["centre"], 3.0)
        squared_radii = 3.0 * 3.0**2
    else:
        result = edit.reround(source, feature.params["centre"], 3.0, 2.0)
        squared_radii = 3.0 * 3.0**2 + 2.0**2
    after = io.BytesIO()
    BRepTools.Write_s(source.shape, after)
    assert after.getvalue() == before.getvalue()
    assert result.is_closed and result.solid_count == 1
    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.volume == pytest.approx(
        24000.0 - 20.0 * (1.0 - math.pi / 4.0) * squared_radii,
        rel=INTEGRAL_RELATIVE_ERROR,
        abs=0.0,
    )
    assert Solid(source.shape).volume == pytest.approx(
        24000.0 - 20.0 * (1.0 - math.pi / 4.0) * 36.0,
        rel=INTEGRAL_RELATIVE_ERROR,
        abs=0.0,
    )


def test_moving_a_solid_keeps_precise_location_and_separate_ownership() -> None:
    """Die Lage wird einmal kopiert, ohne Rundung oder Änderung des Originals."""
    original = edit.box(10.0, 8.0, 6.0)
    offset = (7.123456789, -3.23456789, 2.3456789)
    moved = edit.moved(original, offset)
    assert not moved.shape.IsPartner(original.shape)
    assert original.bounds.minimum == pytest.approx((-5.0, -4.0, 0.0), abs=EPS_GEOM, rel=0.0)
    assert moved.bounds.minimum == pytest.approx(
        tuple(low + shift for low, shift in zip((-5.0, -4.0, 0.0), offset, strict=True)),
        abs=EPS_GEOM,
        rel=0.0,
    )
    assert moved.volume == pytest.approx(480.0, abs=EPS_GEOM, rel=0.0)


def test_replacing_quality_never_inherits_a_mesh_or_property_cache() -> None:
    """Auch dataclasses.replace erzeugt eine neue Form mit eigenem, kaltem Cache."""
    original = edit.cylinder(12.0, 8.0)
    original.to_mesh()
    assert original.volume > 0.0
    assert original._cache
    finer = replace(original, deflection=0.01)
    assert not finer._cache
    assert finer._cache is not original._cache
    assert not finer.shape.IsPartner(original.shape)


def test_identity_affine_transform_keeps_the_solid_and_its_face_numbers() -> None:
    """Die Identität braucht keine neue native Form oder neue Vernetzung."""
    source = edit.box(10.0, 8.0, 6.0)
    result, mapping = edit.transformed_with_faces(source, np.eye(4))
    assert result is source
    assert mapping == tuple(range(6))
    assert not source._cache


@pytest.mark.parametrize("entry", [edit.transformed, edit.transformed_with_faces])
def test_cancellation_precedes_even_an_identity_transform(entry: Any) -> None:
    """Ein schon abgebrochener Auftrag baut und prüft keine neue native Form."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = edit.box(10.0, 8.0, 6.0)
    cancelled = CancelSignal()
    cancelled.cancel()
    with pytest.raises(OperationCancelled):
        entry(source, np.eye(4), cancelled=cancelled)
    assert not source._cache


@pytest.mark.parametrize("kind", ["volume", "surface"])
def test_cancellation_is_checked_before_a_cached_native_measure(kind: str) -> None:
    """Auch ein Cachetreffer darf einen abgebrochenen Auftrag nicht fortsetzen."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = edit.box(10.0, 8.0, 6.0)
    cached = source._properties(kind)
    cancelled = CancelSignal()
    cancelled.cancel()
    with pytest.raises(OperationCancelled):
        source._properties(kind, cancelled=cancelled)
    assert source._cache[kind] is cached


@pytest.mark.parametrize("route", ["volume", "surface", "transform"])
def test_cancellation_during_native_quadrature_keeps_source_and_cache(
    monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    """Abbruch zwischen echten Quadraturpunkten bleibt Abbruch; ein späterer Lauf gelingt."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from scipy.integrate import quad_vec

    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = edit.cylinder(6.0, 8.0)
    if route != "transform":
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    else:
        assert source.volume == pytest.approx(72.0 * math.pi, rel=1e-9)
        assert source.is_closed and source.solid_count == 1
    before = source.bounds, _triangulations(source), dict(source._cache)
    cancelled = CancelSignal()
    visited = 0

    def interrupting_quadrature(function: Any, *args: Any, **kwargs: Any) -> Any:
        """Das Signal kommt nach einem wirklich berechneten Integrationspunkt."""

        def point_then_cancel(value: float) -> Any:
            nonlocal visited
            result = function(value)
            visited += 1
            cancelled.cancel()
            return result

        return quad_vec(point_then_cancel, *args, **kwargs)

    def unavailable_patches(*args: Any, **kwargs: Any) -> Any:
        """Auch der Rückfall einer nicht aufteilbaren Fläche muss abbrechen können."""
        raise ValueError("unavailable private patches")

    matrix = np.diag((2.0, 1.0, 0.5, 1.0))
    with monkeypatch.context() as probe:
        probe.setattr("scipy.integrate.quad_vec", interrupting_quadrature)
        if route == "surface":
            probe.setattr("app.core.brep.properties._spanned_surface", unavailable_patches)
        with pytest.raises(OperationCancelled):
            if route == "transform":
                edit.transformed_with_faces(source, matrix, cancelled=cancelled)
            else:
                source._properties(route, cancelled=cancelled)
    assert visited > 0
    assert source.bounds == before[0]
    assert _triangulations(source) == before[1]
    assert source._cache.keys() == before[2].keys()
    assert all(source._cache[key] is value for key, value in before[2].items())

    cancelled.reset()
    if route == "transform":
        result = edit.transformed(source, matrix, cancelled=cancelled)
        assert result.volume == pytest.approx(72.0 * math.pi, rel=1e-9)
        assert not result.shape.IsPartner(source.shape)
    else:
        expected = (72.0 if route == "volume" else 66.0) * math.pi
        assert source._properties(route, cancelled=cancelled).mass == pytest.approx(
            expected, rel=1e-9
        )
    assert source.bounds == before[0]
    assert _triangulations(source) == before[1]


def test_affine_integrals_do_not_modify_source_or_owned_triangulations() -> None:
    """Teilflächen für Integrale sind Arbeitskopien, keine neue Szenentopologie."""
    source = edit.cylinder(6.0, 8.0)
    result = edit.transformed(source, np.diag((2.0, 1.0, 0.5, 1.0)))
    before = _triangulations(source), _triangulations(result)
    assert result.area > 0.0 and result.volume > 0.0
    assert (_triangulations(source), _triangulations(result)) == before
    assert result.face_count == source.face_count == 3


@pytest.mark.parametrize("length", [8.0, 12.0])
def test_the_surface_integral_keeps_complex_trimmed_thread_flanks_unchanged(length: float) -> None:
    """Eine nicht konvergierende Patch-Zerlegung blockiert keine gültige Gewindefläche."""
    source = profiles.threaded_rod(10.0, 1.5, length)
    before = source.bounds, source.volume, source.face_count, _triangulations(source)
    before_mesh = source._cache.get("mesh")
    area = source.area
    assert np.isfinite(area) and area > 0.0
    cached = source._properties("surface")
    assert source._properties("surface") is cached
    assert source.bounds.minimum == pytest.approx(before[0].minimum, abs=EPS_GEOM)
    assert source.bounds.maximum == pytest.approx(before[0].maximum, abs=EPS_GEOM)
    assert source.volume == pytest.approx(before[1], abs=EPS_GEOM)
    assert (source.face_count, _triangulations(source)) == before[2:]
    assert source._cache.get("mesh") is before_mesh


def test_tessellation_never_populates_the_original_faces() -> None:
    """Auch zwei aufeinanderfolgende Feinheiten arbeiten nur an privaten Formen."""
    solid = edit.cylinder(12.0, 8.0)
    before = _triangulations(solid)
    assert all(entry == (0, 0) for entry in before)
    coarse = tessellate(solid.shape, 0.5)
    fine = tessellate(solid.shape, 0.01)
    assert fine.triangle_count > coarse.triangle_count
    assert _triangulations(solid) == before
    assert solid.bounds.size == pytest.approx((12.0, 12.0, 8.0), abs=EPS_GEOM, rel=0.0)


def test_private_tessellation_keeps_original_face_indices() -> None:
    """Eine versetzte Bohrung färbt genau ihren echten Mantel und keine Nachbarwand."""
    solid = edit.bore(
        edit.box(20.0, 16.0, 8.0),
        position=(3.123456789, 1.23456789, 8.0),
        axis="z",
        diameter=4.0,
    )
    found = features_of(solid)
    hole = next(feature for feature in found.values() if feature.kind == "hole")
    assert hole.face_indices
    corners = solid.raw.triangles[list(hole.face_indices)]
    radial = np.linalg.norm(corners[:, :, :2] - np.array([3.123456789, 1.23456789]), axis=2)
    assert radial == pytest.approx(2.0, abs=EPS_GEOM, rel=0.0)
    groups = [set(solid.triangles_of_face(index)) for index in range(solid.face_count)]
    assert set.union(*groups) == set(range(solid.triangle_count))
    assert sum(map(len, groups)) == solid.triangle_count
    assert all(entry == (0, 0) for entry in _triangulations(solid))


def test_native_faces_can_be_found_from_their_tessellation_triangles() -> None:
    """Die inverse Zuordnung entdoppelt Flächen, ohne die Auswahl zu verbreitern."""
    solid = edit.cylinder(6.0, 8.0)
    groups = [solid.triangles_of_face(index) for index in range(solid.face_count)]
    assert all(groups)
    assert solid.faces_of_triangles(()) == ()
    for index, triangles in enumerate(groups):
        assert solid.faces_of_triangles(triangles) == (index,)
    assert solid.faces_of_triangles((groups[2][0], groups[0][0], groups[2][0])) == (0, 2)


@pytest.mark.parametrize("choice", ["negative", "past_end", "fractional"])
def test_invalid_triangle_selection_never_addresses_a_different_face(choice: str) -> None:
    """Negative NumPy-Indices dürfen nicht heimlich eine andere Fläche auswählen."""
    from app.core.errors import AppError

    solid = edit.cylinder(6.0, 8.0)
    index = {"negative": -1, "past_end": solid.triangle_count, "fractional": 0.5}[choice]
    with pytest.raises(AppError) as failure:
        solid.faces_of_triangles((index,))
    assert failure.value.suggestions


@pytest.mark.parametrize("kind", ["union", "difference", "intersection"])
def test_boolean_options_precede_the_only_build(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """Der Zweiform-Konstruktor rechnet schon; ausschließlich leer konfigurieren."""
    import OCP.BRepAlgoAPI as brep_api  # noqa: N813 - Name der externen OCP-API

    first = edit.box(10.0, 8.0, 6.0)
    second = edit.moved(edit.box(4.0, 4.0, 8.0), (3.0, 0.0, -1.0))
    events: list[str] = []

    class RecordingBoolean:
        """Zeichnet die Reihenfolge auf, statt bei Konstruktion heimlich zu rechnen."""

        def __init__(self, *args: object) -> None:
            assert not args, "the two-shape constructor already builds"
            events.append("new")

        def SetArguments(self, values: Any) -> None:  # noqa: N802
            assert values.Size() == 1
            events.append("arguments")

        def SetTools(self, values: Any) -> None:  # noqa: N802
            assert values.Size() == 1
            events.append("tools")

        def SetNonDestructive(self, value: bool) -> None:  # noqa: N802
            assert value
            events.append("protected")

        def SetFuzzyValue(self, value: float) -> None:  # noqa: N802
            assert value == pytest.approx(EPS_GEOM, rel=0.0)
            events.append("fuzzy")

        def Build(self) -> None:  # noqa: N802
            assert "protected" in events
            events.append("build")

        def IsDone(self) -> bool:  # noqa: N802
            return True

        def Shape(self) -> Any:  # noqa: N802
            return first.shape

    for name in ("BRepAlgoAPI_Fuse", "BRepAlgoAPI_Cut", "BRepAlgoAPI_Common"):
        monkeypatch.setattr(brep_api, name, RecordingBoolean)
    edit.boolean(kind, [first, second])
    assert events.count("build") == 1
    events.clear()
    profiles._fuzzy_boolean(kind, first, second)
    assert events.count("build") == 1
    assert events.index("fuzzy") < events.index("build")
    assert events.index("protected") < events.index("build")


@pytest.mark.parametrize("operation", ["fillet", "chamfer", "shell", "draft", "sew", "push"])
def test_modification_uses_private_input_topology(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """Auch nichtboolesche Builder dürfen die veröffentlichte Form nicht erhalten."""
    solid = edit.box(20.0, 16.0, 10.0)
    original_faces = solid.faces()
    original_bounds = solid.bounds
    original_volume = solid.volume
    module_name, builder_name = {
        "fillet": ("OCP.BRepFilletAPI", "BRepFilletAPI_MakeFillet"),
        "chamfer": ("OCP.BRepFilletAPI", "BRepFilletAPI_MakeChamfer"),
        "shell": ("OCP.BRepOffsetAPI", "BRepOffsetAPI_MakeThickSolid"),
        "draft": ("OCP.BRepOffsetAPI", "BRepOffsetAPI_DraftAngle"),
        "sew": ("OCP.ShapeFix", "ShapeFix_Shape"),
        "push": ("OCP.BRepPrimAPI", "BRepPrimAPI_MakePrism"),
    }[operation]
    module = importlib.import_module(module_name)
    real_builder = getattr(module, builder_name)
    seen: list[Any] = []

    def private_input(shape: Any) -> None:
        assert all(not shape.IsPartner(original) for original in (solid.shape, *original_faces))
        seen.append(shape)

    class CheckedBuilder:
        """Prüft die echte native Eingabe und lässt danach den echten Builder arbeiten."""

        def __init__(self, *args: Any) -> None:
            if args:
                private_input(args[0])
            self._builder = real_builder(*args)

        def MakeThickSolidByJoin(self, *args: Any) -> Any:  # noqa: N802
            private_input(args[0])
            return self._builder.MakeThickSolidByJoin(*args)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._builder, name)

    monkeypatch.setattr(module, builder_name, CheckedBuilder)
    if operation == "fillet":
        changed = edit.fillet(solid, 1.0, "vertical")
    elif operation == "chamfer":
        changed = edit.chamfer(solid, 1.0, "vertical")
    elif operation == "shell":
        changed = profiles.shell_open_top(solid, 1.0)
    elif operation == "draft":
        changed = profiles.draft_vertical(solid, 3.0)
    elif operation == "sew":
        changed = profiles._sewn(solid)
    else:
        changed = profiles.push_faces(solid, (0.0, 0.0, 1.0), 2.0)
    assert seen, "the real native modifier was not reached"
    assert not changed.shape.IsPartner(solid.shape)
    mesh = changed.to_mesh()
    assert mesh.is_watertight
    assert mesh.raw.is_winding_consistent
    assert mesh.volume > 0.0
    assert abs(mesh.volume - changed.volume) < changed.area * changed.deflection
    assert solid.bounds.minimum == pytest.approx(original_bounds.minimum, abs=EPS_GEOM, rel=0.0)
    assert solid.bounds.maximum == pytest.approx(original_bounds.maximum, abs=EPS_GEOM, rel=0.0)
    # Neuer Wrapper misst dieselbe Eingabe ungecacht, statt den Volumencache zu bestätigen.
    assert Solid(solid.shape).volume == pytest.approx(original_volume, abs=EPS_GEOM, rel=0.0)
    assert all(entry == (0, 0) for entry in _triangulations(solid))


@pytest.mark.parametrize(
    "kind,expected_volume", [("union", 512.0), ("difference", 384.0), ("intersection", 96.0)]
)
def test_real_boolean_keeps_its_input_geometry(kind: str, expected_volume: float) -> None:
    """Alle drei echten Booleschen Wege rechnen, ohne den warmen Eingang zu verändern."""
    first = edit.box(10.0, 8.0, 6.0)
    second = edit.moved(edit.box(4.0, 4.0, 8.0), (3.0, 0.0, -1.0))
    before = [(body.bounds, body.volume, body.face_count) for body in (first, second)]
    result = edit.boolean(kind, [first, second])  # type: ignore[arg-type]
    assert result.volume == pytest.approx(expected_volume, abs=EPS_GEOM, rel=0.0)
    for body, (bounds, volume, faces) in zip((first, second), before, strict=True):
        fresh = Solid(body.shape)
        assert fresh.bounds.minimum == pytest.approx(bounds.minimum, abs=EPS_GEOM, rel=0.0)
        assert fresh.bounds.maximum == pytest.approx(bounds.maximum, abs=EPS_GEOM, rel=0.0)
        assert fresh.volume == pytest.approx(volume, abs=EPS_GEOM, rel=0.0)
        assert fresh.face_count == faces
        assert all(entry == (0, 0) for entry in _triangulations(body))
