"""Geschlossene Luftkammern beider Kerne einschließlich ihrer Materialinseln."""

from __future__ import annotations

import io
import math
from typing import Any

import numpy as np
import pytest

from app.core.brep import step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, available, boolean_builder
from app.core.perceive.features import detect_voids
from app.core.units import EPS_GEOM, MAX_FACET_SAG

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")


def _bytes(shape: Any) -> bytes:
    """Die vollständige native Form einschließlich vorhandener Triangulation."""
    from OCP.BRepTools import BRepTools

    stream = io.BytesIO()
    BRepTools.Write_s(shape, stream)
    return stream.getvalue()


def _compound(*shapes: Any) -> Any:
    """Mehrere vorhandene Materialkörper ohne Veränderung zusammenstellen."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    shape = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(shape)
    for item in shapes:
        builder.Add(shape, item)
    return shape


def _pocket(*, island: bool = False, base: float = 6.0, height: float = 8.0) -> Solid:
    """40 × 30 × 20 mit Ø6 × 8 Luft, gegebenenfalls Kugel R1 im Inneren."""
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakeSphere,
    )
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    stock = BRepPrimAPI_MakeBox(gp_Pnt(-20, -15, 0), 40, 30, 20).Shape()
    tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, base), gp_Dir(0, 0, 1)), 3, height)
    builder = boolean_builder("difference", stock, tool.Shape())
    builder.Build()
    assert builder.IsDone()
    hollow = builder.Shape()
    if island:
        sphere = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 10), 1).Shape()
        hollow = _compound(hollow, sphere)
    return Solid(hollow)


@pytest.mark.parametrize("representation", ["analytic", "nurbs", "step"])
@pytest.mark.parametrize("island", [False, True])
def test_native_air_volume_and_selection_include_material_islands(
    representation: str, island: bool
) -> None:
    """Das Luftvolumen zieht Material ab; sämtliche Luftgrenzflächen bleiben wählbar."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepCheck import BRepCheck_Analyzer

    source = _pocket(island=island)
    if representation != "analytic":
        source = Solid(BRepBuilderAPI_NurbsConvert(source.shape, True).Shape())
    if representation == "step":
        source = step.read(step.write(source))
    before = _bytes(source.shape)
    expected = 72.0 * math.pi - (4.0 * math.pi / 3.0 if island else 0.0)
    assert BRepCheck_Analyzer(source.shape).IsValid()
    assert source.is_closed
    assert source.volume == pytest.approx(24000.0 - expected, rel=1e-10)

    found = features_of(source)
    voids = [feature for feature in found.values() if feature.kind == "void"]
    assert len(voids) == 1
    air = voids[0]
    assert air.params["volume"] == pytest.approx(expected, rel=1e-10)
    assert air.params["centre"] == pytest.approx((0, 0, 10), abs=1e-6)
    assert air.params["size"] == pytest.approx((6, 6, 8), abs=1e-6)
    centres = source.raw.triangles_center
    expected_faces = np.flatnonzero(
        (np.linalg.norm(centres[:, :2], axis=1) <= 3.0 + EPS_GEOM)
        & (centres[:, 2] >= 6.0 - EPS_GEOM)
        & (centres[:, 2] <= 14.0 + EPS_GEOM)
    )
    assert set(air.face_indices) == set(expected_faces)
    assert len(source.faces_of_triangles(air.face_indices)) == (4 if island else 3)
    assert {index for patch in air.surface_patches for index in patch.face_indices} == set(
        expected_faces
    )
    assert {patch.kind for patch in air.surface_patches} == (
        {"plane", "cylinder", "sphere"} if island else {"plane", "cylinder"}
    )
    assert all(patch.source == "native" for patch in air.surface_patches)
    assert all(
        not set(feature.face_indices) & set(air.face_indices)
        for feature in found.values()
        if feature.id != air.id
    )
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("deflection", [MAX_FACET_SAG, MAX_FACET_SAG / 4.0])
@pytest.mark.parametrize("island", [False, True])
def test_mesh_twin_has_the_same_complete_air_boundary(deflection: float, island: bool) -> None:
    """Die Insel darf die umgebende Kammer weder verstecken noch deren Volumen vergrößern."""
    source = Solid(_pocket(island=island).shape, deflection=deflection)
    found = detect_voids(source.to_mesh())
    assert len(found) == 1
    air = found[0]
    assert len(source.faces_of_triangles(air.face_indices)) == (4 if island else 3)
    expected = 72.0 * math.pi - (4.0 * math.pi / 3.0 if island else 0.0)
    # Die Facetten nähern beide Rundflächen an; der native Sollwert bleibt unabhängig.
    assert air.params["volume"] == pytest.approx(expected, abs=1.0)
    assert air.params["centre"] == pytest.approx((0, 0, 10), abs=deflection)


@pytest.mark.parametrize("base,height", [(-1.0, 22.0), (6.0, 20.0)])
def test_open_and_blind_bores_are_not_enclosed_air(base: float, height: float) -> None:
    """Eine Mündung nach außen unterscheidet Durchgang und Sackloch vom Einschluss."""
    source = _pocket(base=base, height=height)
    assert not [feature for feature in features_of(source).values() if feature.kind == "void"]
    assert not detect_voids(source.to_mesh())


@pytest.mark.parametrize("representation", ["brep", "mesh"])
@pytest.mark.parametrize("deflection", [MAX_FACET_SAG, MAX_FACET_SAG / 4.0])
def test_a_slotted_enclosure_is_air_instead_of_a_blind_slot(
    representation: str, deflection: float
) -> None:
    """Der Mantel allein beweist keine Öffnung: Luft von Z=3 bis Z=7 ist eingeschlossen."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT, TopAbs_SHELL
    from OCP.TopExp import TopExp

    from app.core.brep import edit
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect

    source = edit.slot_bore(
        edit.box(90.0, 60.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=4.0,
        length=20.0,
        angle_deg=0.0,
        overlap=0.1,
    )
    source = Solid(source.shape, deflection=deflection)
    before = _bytes(source.shape)
    expected_volume = (6.1 * 14.0 + math.pi * 3.05**2) * 4.0
    assert BRepCheck_Analyzer(source.shape).IsValid()
    assert source.solid_count == 1
    assert source.volume == pytest.approx(54000.0 - expected_volume, rel=1e-10)
    shells = ShapeMap()
    TopExp.MapShapes_s(source.shape, TopAbs_SHELL, shells)
    assert shells.Extent() == 2
    classifier = BRepClass3d_SolidClassifier(source.shape)
    for z, expected in ((1.0, TopAbs_IN), (5.0, TopAbs_OUT), (9.0, TopAbs_IN)):
        classifier.Perform(gp_Pnt(0.0, 0.0, z), EPS_GEOM)
        assert classifier.State() == expected

    found = features_of(source) if representation == "brep" else detect(as_mesh_data(source))

    voids = [feature for feature in found.values() if feature.kind == "void"]
    assert len(voids) == 1
    assert not any(feature.kind == "slot" for feature in found.values())
    air = voids[0]
    if representation == "brep":
        assert air.params["volume"] == pytest.approx(expected_volume, rel=1e-10)
    else:
        # Die beiden Halbkreise verlieren höchstens einen Kreisring mit der
        # zulässigen Sehnenabweichung als Breite; die geraden Flanken bleiben exakt.
        maximum_loss = math.pi * (3.05**2 - (3.05 - deflection) ** 2) * 4.0
        assert expected_volume - maximum_loss <= air.params["volume"] <= expected_volume
    assert air.params["centre"] == pytest.approx((0.0, 0.0, 5.0), abs=deflection)
    centres = source.raw.triangles_center
    expected_faces = np.flatnonzero(
        (np.abs(centres[:, 0]) <= 10.05 + EPS_GEOM)
        & (np.abs(centres[:, 1]) <= 3.05 + EPS_GEOM)
        & (centres[:, 2] >= 3.0 - EPS_GEOM)
        & (centres[:, 2] <= 7.0 + EPS_GEOM)
    )
    assert set(air.face_indices) == set(expected_faces)
    assert len(source.faces_of_triangles(air.face_indices)) == 6
    assert all(
        set(feature.face_indices).isdisjoint(air.face_indices)
        for feature in found.values()
        if feature.id != air.id
    )
    assert _bytes(source.shape) == before


def test_native_nested_air_chambers_are_each_published_once() -> None:
    """Eine Insel kann selbst Luft einschließen; ihre Kammer wird nicht doppelt gezählt."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    def hollow(outer: float, inner: float) -> Any:
        """Zwei zentrierte Würfel ergeben eine geschlossene, maßlich bekannte Hülle."""
        stock = BRepPrimAPI_MakeBox(gp_Pnt(-outer / 2, -outer / 2, -outer / 2), outer, outer, outer)
        tool = BRepPrimAPI_MakeBox(gp_Pnt(-inner / 2, -inner / 2, -inner / 2), inner, inner, inner)
        builder = boolean_builder("difference", stock.Shape(), tool.Shape())
        builder.Build()
        assert builder.IsDone()
        return builder.Shape()

    source = Solid(_compound(hollow(40, 12), hollow(6, 2)))
    before = _bytes(source.shape)
    found = [feature for feature in features_of(source).values() if feature.kind == "void"]
    assert sorted(feature.params["volume"] for feature in found) == pytest.approx([8, 1512])
    assert sorted(len(source.faces_of_triangles(feature.face_indices)) for feature in found) == [
        6,
        12,
    ]
    assert set(found[0].face_indices).isdisjoint(found[1].face_indices)
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("reversed_order", [False, True])
def test_native_separate_chambers_keep_their_names_and_island_ownership(
    reversed_order: bool,
) -> None:
    """Die linke Kammer mit Insel und die rechte Kammer teilen keine Grenzfläche."""
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakeSphere,
    )
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    shape = BRepPrimAPI_MakeBox(gp_Pnt(-20, -15, 0), 40, 30, 20).Shape()
    for x in [8, -8] if reversed_order else [-8, 8]:
        tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, 0, 6), gp_Dir(0, 0, 1)), 3, 8)
        builder = boolean_builder("difference", shape, tool.Shape())
        builder.Build()
        shape = builder.Shape()
    island = BRepPrimAPI_MakeSphere(gp_Pnt(-8, 0, 10), 1).Shape()
    source = Solid(_compound(island, shape) if reversed_order else _compound(shape, island))
    before = _bytes(source.shape)
    voids = sorted(
        (feature for feature in features_of(source).values() if feature.kind == "void"),
        key=lambda feature: feature.id,
    )
    assert [feature.id for feature in voids] == ["void_1", "void_2"]
    assert [feature.params["volume"] for feature in voids] == pytest.approx(
        [72 * math.pi - 4 * math.pi / 3, 72 * math.pi]
    )
    assert voids[0].params["centre"] == pytest.approx((-8, 0, 10))
    assert voids[1].params["centre"] == pytest.approx((8, 0, 10))
    assert set(voids[0].face_indices).isdisjoint(voids[1].face_indices)
    assert [len(source.faces_of_triangles(feature.face_indices)) for feature in voids] == [4, 3]
    assert _bytes(source.shape) == before


def test_an_open_native_shell_cannot_become_an_air_chamber() -> None:
    """Die einzelnen Innenflächen eines offenen Körpers ergeben keine sichere Kammer."""
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS, TopoDS_Shell

    from app.core.brep.features import _void_features

    original = _pocket()
    shell = TopoDS_Shell()
    builder = BRep_Builder()
    builder.MakeShell(shell)
    for face in original.faces()[1:]:
        builder.Add(shell, face)
    source = Solid(shell)
    before = _bytes(source.shape)
    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(source.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    free = []
    for index in range(1, neighbours.Extent() + 1):
        edge = TopoDS.Edge(neighbours.FindKey(index))
        owners = list(neighbours.FindFromIndex(index))
        if len(owners) == 1 and not BRep_Tool.IsClosed_s(edge, TopoDS.Face(owners[0])):
            free.append(edge)
    assert len(free) == 4
    assert source.solid_count == 0
    assert _void_features(source) == []
    assert _bytes(source.shape) == before


def test_inverted_native_outer_shell_is_not_a_void() -> None:
    """Eine umgestülpte Außenschale besitzt keine eingeschlossene Luft."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    shape = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    shape.Reverse()
    source = Solid(shape)
    before = _bytes(source.shape)
    assert not [feature for feature in features_of(source).values() if feature.kind == "void"]
    assert _bytes(source.shape) == before


@pytest.mark.parametrize("before_work", [False, True])
def test_native_air_recognition_cancels_without_changing_the_source(
    before_work: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abbruch vor dem Start oder innerhalb der Materialtrennung lässt einen Neustart zu."""
    from app.core.brep import features as native
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    source = _pocket(island=True)
    before = _bytes(source.shape)
    signal = CancelSignal()
    original = native.boolean_builder

    def stop(*args: Any, **kwargs: Any) -> Any:
        """Der echte Materialtrennungsweg verlangt während der Arbeit den Abbruch."""
        result = original(*args, **kwargs)
        signal.cancel()
        return result

    if before_work:
        signal.cancel()
    else:
        monkeypatch.setattr(native, "boolean_builder", stop)
    with pytest.raises(OperationCancelled):
        features_of(source, cancelled=signal)
    assert _bytes(source.shape) == before
    monkeypatch.setattr(native, "boolean_builder", original)
    found = [feature for feature in features_of(source).values() if feature.kind == "void"]
    assert len(found) == 1
    assert found[0].params["volume"] == pytest.approx(72 * math.pi - 4 * math.pi / 3)


def test_an_asymmetric_air_shape_keeps_its_box_centre() -> None:
    """Die Mitte der Luft-AABB ist kein Volumenschwerpunkt und kein Primitive-Fit."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    first = BRepPrimAPI_MakeBox(gp_Pnt(-2, -2, 8), 4, 2, 2).Shape()
    second = BRepPrimAPI_MakeBox(gp_Pnt(-2, -2, 8), 2, 4, 2).Shape()
    builder = boolean_builder("union", first, second)
    builder.Build()
    stock = BRepPrimAPI_MakeBox(gp_Pnt(-20, -15, 0), 40, 30, 20).Shape()
    cut = boolean_builder("difference", stock, builder.Shape())
    cut.Build()
    source = Solid(cut.Shape())
    air = next(feature for feature in features_of(source).values() if feature.kind == "void")
    assert air.params["volume"] == pytest.approx(24.0)
    assert air.params["centre"] == pytest.approx((0.0, 0.0, 9.0))
    assert air.params["size"] == pytest.approx((4.0, 4.0, 2.0))


@pytest.mark.parametrize("operation", ["move_feature", "remove_feature"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("island", [False, True])
def test_imported_void_actions_preserve_their_published_meaning(
    operation: str, quality: str, island: bool, profile: Any, tmp_path: Any
) -> None:
    """STEP → Auswahl → Handlung → Speichern → Undo/Redo bleibt ein Kundenweg."""
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec, as_mesh_data
    from app.core.perceive.actions import actions_for
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import ProjectSources, load, new_project, save
    from app.core.types import Source

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    payload = step.write(_pocket(island=island))
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/air.step", sha256=""
    )
    history = History(project.document)
    history.apply(
        "Innenraum laden",
        [OperationDraft(op="load_step", params={"source": "src_1"})],
    )
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))

    def run(current: Any, remembered: Any = None) -> Any:
        """Derselbe dokumentierte Auftrag mit gewählter Qualität und Quellen."""
        result = evaluate(
            current.document,
            profile,
            quality=quality,
            sources=ProjectSources(current),
            cache=remembered,
        )
        assert result.complete, [
            (finding.code, str(finding.message)) for finding in result.scene.report.findings
        ]
        return result

    initial = run(project, cache)
    source = initial.scene.objects["obj_1"]
    before = _bytes(source.mesh.shape)
    air = next(feature for feature in source.features.values() if feature.kind == "void")
    offered = actions_for(air, source.features, mesh=as_mesh_data(source.mesh))
    assert {action.op for action in offered if action.op} == {"move_feature", "remove_feature"}
    params = {"at_feature": air.id}
    if operation == "move_feature":
        params.update(x=8.0, y=0.0, z=10.0)
    history.apply(
        "Innenraum bearbeiten", [OperationDraft(op=operation, inputs=(source.id,), params=params)]
    )
    changed = run(project, cache)
    output = changed.scene.objects[source.id]
    assert output.kind == "brep", "der Einschluss bleibt am exakten Körper exakt (P2.4)"
    assert not any(finding.converts_exact_body for finding in changed.scene.report.findings)
    assert output.mesh.is_closed
    if operation == "move_feature":
        assert output.mesh.volume == pytest.approx(source.mesh.volume, rel=1e-9)
        assert output.features[air.id].params["centre"] == pytest.approx((8, 0, 10), abs=1e-6)
        assert output.features[air.id].params["volume"] == pytest.approx(
            air.params["volume"], rel=1e-9
        )
    else:
        assert output.mesh.volume == pytest.approx(24000.0, rel=1e-9)
        assert not [feature for feature in output.features.values() if feature.kind == "void"]
    assert _bytes(source.mesh.shape) == before
    reopened = load(save(project, tmp_path / "air.solidon"))
    fresh = run(reopened)
    assert fresh.scene.objects[source.id].mesh.volume == pytest.approx(output.mesh.volume)
    assert reopened.sources["src_1"] == payload
    reopened_history = History(reopened.document)
    reopened_history.undo()
    restored = run(reopened).scene.objects[source.id]
    assert restored.kind == "brep"
    assert restored.features[air.id].params["volume"] == pytest.approx(air.params["volume"])
    reopened_history.redo()
    assert run(reopened).scene.objects[source.id].mesh.volume == pytest.approx(output.mesh.volume)


def test_a_body_without_an_inner_shell_skips_the_cavity_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne Innenschale keine Kammer — und keine Gültigkeitsprüfung des ganzen Körpers.

    ``_void_features`` prüfte jeden Körper mit ``BRepCheck_Analyzer``, bevor es
    nach Innenschalen fragte; am Gewindebolzen M3 x 0,5 x 60 0,21 s je
    Erkennung für eine Antwort, die die Schalenzahl schon gab (Review
    22.09.2026). Die Kammer daneben wird weiter gefunden.
    """
    import OCP.BRepCheck as brep_check  # noqa: N813 - Name der externen OCP-API

    from app.core.brep import edit
    from app.core.brep.features import _void_features

    checked: list[object] = []
    original = brep_check.BRepCheck_Analyzer

    def counting(shape: object, *args: object) -> object:
        checked.append(shape)
        return original(shape, *args)

    monkeypatch.setattr(brep_check, "BRepCheck_Analyzer", counting)
    assert _void_features(edit.box(20.0, 20.0, 20.0)) == []
    assert checked == []
    assert len(_void_features(_pocket())) == 1
    assert checked, "mit Innenschale wird weiter geprüft"
