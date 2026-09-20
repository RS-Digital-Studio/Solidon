"""Passungsmaße sind kein Beleg über die wirklichen Körper in Einbaulage."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData
from app.core.scene import CancelSignal
from app.core.scene.fits import check
from app.core.types import Feature, FeatureRef, Fit, Profile, Scene, SceneObject


def pair(profile: Profile, *, segments: int = 256, angle: float = 0.0) -> Scene:
    """Analytisch festgelegte Polygone, unabhängig von Erkennung und Passungsprüfung."""
    ring = trimesh.creation.annulus(r_min=15.0, r_max=20.0, height=10.0, sections=16)
    pin = trimesh.creation.cylinder(radius=14.8, height=10.0, sections=segments)
    pin.apply_transform(trimesh.transformations.rotation_matrix(angle, (0.0, 0.0, 1.0)))
    objects = {}
    for object_id, mesh, kind, diameter in (
        ("socket", ring, "hole", 30.0),
        ("pin", pin, "pin", 29.6),
    ):
        feature = Feature(
            id="mating",
            kind=kind,
            provenance="generated",
            params={
                "diameter": diameter,
                "centre": (0.0, 0.0, 0.0),
                "axis": (0.0, 0.0, 1.0),
                "depth" if kind == "hole" else "length": 10.0,
            },
        )
        objects[object_id] = SceneObject(
            id=object_id, name=object_id, mesh=MeshData(mesh), features={feature.id: feature}
        )
    return Scene(
        objects=objects,
        profile=profile,
        fits=[
            Fit(
                "pair",
                FeatureRef("socket", "mating"),
                FeatureRef("pin", "mating"),
                "clearance",
                0.4,
            )
        ],
    )


def geometry_finding(scene: Scene):
    """Die Körperprobe bleibt neben einem möglichen Nennmaßbefund sichtbar."""
    found = [finding for finding in check(scene, scene.profile) if finding.code != "fit.violated"]
    assert len(found) == 1
    return found[0]


def test_fine_pin_intersects_coarse_socket_despite_matching_diameters(profile: Profile) -> None:
    scene = pair(profile)
    before = {
        key: (entry.mesh.raw.vertices.copy(), entry.mesh.raw.faces.copy())
        for key, entry in scene.objects.items()
    }
    finding = geometry_finding(scene)
    assert finding.code == "fit.collision"
    # Kreisabschnitt hinter jeder der 16 Innenkanten. Die Sehnen des Stifts
    # entfernen höchstens dessen gesamte Kreis-Polygon-Flächendifferenz.
    radius, apothem = 14.8, 15.0 * math.cos(math.pi / 16)
    cap = radius**2 * math.acos(apothem / radius) - apothem * math.sqrt(radius**2 - apothem**2)
    circle = math.pi * radius**2
    polygon = 256 * radius**2 / 2 * math.sin(2 * math.pi / 256)
    assert (16 * cap - (circle - polygon)) * 10 <= finding.values["overlap_mm3"] <= 16 * cap * 10
    for key, entry in scene.objects.items():
        np.testing.assert_array_equal(entry.mesh.raw.vertices, before[key][0])
        np.testing.assert_array_equal(entry.mesh.raw.faces, before[key][1])


@pytest.mark.parametrize(
    "angle, expected", [(0.0, "fit.geometry_clear"), (math.pi / 16, "fit.collision")]
)
def test_polygon_phase_changes_collision_without_changing_diameter(
    profile: Profile, angle: float, expected: str
) -> None:
    finding = geometry_finding(pair(profile, segments=16, angle=angle))
    assert finding.code == expected


@pytest.mark.parametrize("change", ["plate", "apart", "no_axis", "no_depth", "axially_apart"])
def test_unproven_installation_pose_is_not_clear(profile: Profile, change: str) -> None:
    scene = pair(profile, segments=16)
    pin = scene.objects["pin"]
    feature = pin.features["mating"]
    params = dict(feature.params)
    if change == "plate":
        pin = replace(pin, plate=1)
    elif change in {"apart", "axially_apart"}:
        offset = (50.0, 0.0, 0.0) if change == "apart" else (0.0, 0.0, 30.0)
        moved = pin.mesh.raw.copy()
        moved.apply_translation(offset)
        pin = replace(pin, mesh=MeshData(moved))
        params["centre"] = offset
    else:
        params.pop("axis" if change == "no_axis" else "length")
    scene.objects["pin"] = replace(pin, features={"mating": replace(feature, params=params)})
    assert geometry_finding(scene).code == "fit.pose_unknown"


def test_open_mesh_is_failed_not_a_valid_empty_intersection(profile: Profile) -> None:
    scene = pair(profile, segments=16)
    pin = scene.objects["pin"]
    mesh = pin.mesh.raw
    scene.objects["pin"] = replace(
        pin, mesh=MeshData(trimesh.Trimesh(mesh.vertices, mesh.faces[:-1], process=False))
    )
    assert geometry_finding(scene).code == "fit.geometry_failed"


def test_press_probe_does_not_approve_all_interference(profile: Profile) -> None:
    scene = pair(profile)
    scene.fits = [replace(scene.fits[0], kind="press", tolerance=-0.1)]
    pin = scene.objects["pin"]
    pin.mesh = MeshData(trimesh.creation.cylinder(radius=15.05, height=10.0, sections=256))
    feature = pin.features["mating"]
    pin.features["mating"] = replace(feature, params={**feature.params, "diameter": 30.1})
    assert not any(item.code == "fit.violated" for item in check(scene, profile))
    finding = geometry_finding(scene)
    assert finding.code == "fit.press_unverified"
    assert finding.severity == "warning"
    assert finding.values["overlap_mm3"] > 0.0


def test_clear_polygon_pose_does_not_erase_contour_uncertainty(profile: Profile) -> None:
    scene = pair(profile, segments=16)
    for entry in scene.objects.values():
        feature = entry.features["mating"]
        radius = feature.params["diameter"] / 2
        entry.features["mating"] = replace(
            feature,
            params={
                **feature.params,
                "radial_min": radius * math.cos(math.pi / 16),
                "radial_max": radius,
            },
        )
    assert [item.code for item in check(scene, profile)] == [
        "fit.mesh_uncertain",
        "fit.geometry_clear",
    ]


def test_cancelled_probe_never_returns_clear(profile: Profile) -> None:
    signal = CancelSignal()
    signal.cancel()
    with pytest.raises(OperationCancelled):
        check(pair(profile, segments=16), profile, cancelled=signal)


def native_pair(profile: Profile, *, floor: bool = False) -> Scene:
    """Exakter Ring und Stift; der optionale Boden kollidiert außerhalb des Mantels."""
    from app.core.brep.edit import boolean, cylinder, moved

    scene = pair(profile)
    outside = moved(cylinder(40.0, 10.0), (0.0, 0.0, -5.0))
    bore = moved(cylinder(30.0, 10.0), (0.0, 0.0, -4.0 if floor else -5.0))
    scene.objects["socket"] = replace(
        scene.objects["socket"], mesh=boolean("difference", [outside, bore])
    )
    scene.objects["pin"] = replace(
        scene.objects["pin"], mesh=moved(cylinder(29.6, 10.0), (0.0, 0.0, -5.0))
    )
    if floor:
        entry = scene.objects["socket"]
        feature = entry.features["mating"]
        entry.features["mating"] = replace(
            feature, params={**feature.params, "centre": (0.0, 0.0, 0.5), "depth": 9.0}
        )
    return scene


def native_bytes(scene: Scene) -> dict[str, bytes]:
    """Auch Topologie- und Prüfkennzeichen zählen zum unveränderten nativen Eingang."""
    from io import BytesIO

    from OCP.BRepTools import BRepTools

    stored = {}
    for key, entry in scene.objects.items():
        buffer = BytesIO()
        BRepTools.Write_s(entry.mesh.shape, buffer)
        stored[key] = buffer.getvalue()
    return stored


@pytest.mark.parametrize("floor", [False, True])
def test_native_full_bodies_include_floor_and_preserve_input(profile: Profile, floor: bool) -> None:
    scene = native_pair(profile, floor=floor)
    before = native_bytes(scene)
    found = geometry_finding(scene)
    assert found.code == ("fit.collision" if floor else "fit.geometry_clear")
    assert found.values["geometry_source"] == "native"
    assert found.values["overlap_mm3"] == pytest.approx(math.pi * 14.8**2 if floor else 0.0)
    assert native_bytes(scene) == before


@pytest.mark.parametrize("native_side", ["socket", "pin"])
def test_mixed_probe_is_explicitly_a_mesh_approximation(profile: Profile, native_side: str) -> None:
    scene = pair(profile)
    scene.objects[native_side] = native_pair(profile).objects[native_side]
    found = geometry_finding(scene)
    assert found.code == "fit.geometry_approximate"
    assert found.values["geometry_source"] == "mixed"
    assert found.values["intersects"] is (native_side == "pin")


@pytest.mark.parametrize("deflection", [0.01, 0.1])
def test_native_rotation_and_tessellation_resolution_preserve_full_body_result(
    profile: Profile, deflection: float
) -> None:
    from app.core.brep.edit import transformed

    scene = native_pair(profile, floor=True)
    expected = geometry_finding(scene)
    matrix = trimesh.transformations.rotation_matrix(0.79, (1.0, 2.0, 3.0))
    matrix[:3, 3] = (53.0, -7.0, 125.0)
    for entry in scene.objects.values():
        entry.mesh = replace(
            transformed(entry.mesh, tuple(map(tuple, matrix))), deflection=deflection
        )
        # Der sichtbare Zwilling darf die folgende native Körperprobe nicht bestimmen.
        assert entry.mesh.to_mesh().triangle_count > 0
        feature = entry.features["mating"]
        centre = matrix @ np.append(feature.params["centre"], 1.0)
        entry.features["mating"] = replace(
            feature,
            params={**feature.params, "centre": tuple(centre[:3]), "axis": tuple(matrix[:3, 2])},
        )
    before = native_bytes(scene)
    actual = geometry_finding(scene)
    assert actual.code == expected.code == "fit.collision"
    assert actual.values["overlap_mm3"] == pytest.approx(expected.values["overlap_mm3"], rel=1e-8)
    assert native_bytes(scene) == before


@pytest.mark.parametrize("subdivide", [False, True])
def test_common_rigid_transform_and_subdivision_preserve_collision(
    profile: Profile, subdivide: bool
) -> None:
    scene = pair(profile)
    original = geometry_finding(scene)
    matrix = trimesh.transformations.rotation_matrix(0.79, (1.0, 2.0, 3.0))
    matrix[:3, 3] = (53.0, -7.0, 125.0)
    for entry in scene.objects.values():
        mesh = entry.mesh.raw.subdivide() if subdivide else entry.mesh.raw.copy()
        mesh.apply_transform(matrix)
        entry.mesh = MeshData(mesh)
        feature = entry.features["mating"]
        entry.features["mating"] = replace(
            feature,
            params={**feature.params, "centre": tuple(matrix[:3, 3]), "axis": tuple(matrix[:3, 2])},
        )
    found = geometry_finding(scene)
    assert found.code == original.code
    assert found.values["overlap_mm3"] == pytest.approx(original.values["overlap_mm3"], rel=1e-8)


@pytest.mark.parametrize("native", [False, True])
def test_cancel_after_kernel_returns_no_geometry_result(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, native: bool
) -> None:
    import importlib

    signal = CancelSignal()
    if native:
        module = importlib.import_module("app.core.brep.kernel")
        original = module.boolean_builder

        class CancelAfterBuild:
            def __init__(self, *args, **kwargs):
                self.builder = original(*args, **kwargs)

            def Build(self):  # noqa: N802 — native Schnittstelle
                self.builder.Build()
                signal.cancel()

            def __getattr__(self, name):
                return getattr(self.builder, name)

        scene = native_pair(profile)
        before = native_bytes(scene)
        monkeypatch.setattr(module, "boolean_builder", CancelAfterBuild)
    else:
        module = importlib.import_module("app.core.geom.boolean")
        original = module.boolean

        def cancel(*args, **kwargs):
            result = original(*args, **kwargs)
            signal.cancel()
            return result

        scene = pair(profile, segments=16)
        monkeypatch.setattr(module, "boolean", cancel)
    with pytest.raises(OperationCancelled):
        check(scene, profile, cancelled=signal)
    if native:
        assert native_bytes(scene) == before


def test_kernel_error_is_not_clear_and_no_repair_is_attempted(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    calls = []

    def fail(kind, meshes, **kwargs):
        calls.append((kind, kwargs["stages"], kwargs["allow_empty"]))
        raise RuntimeError("forced kernel error")

    monkeypatch.setattr(importlib.import_module("app.core.geom.boolean"), "boolean", fail)
    assert geometry_finding(pair(profile)).code == "fit.geometry_failed"
    assert calls == [("intersection", ("direct",), True)]


def fit_document(profile: Profile):
    """Ein reproduzierbarer Operationsstapel benutzt den echten Auswertungsanschluss."""
    from app.core.registry import Registry, op_params, register_op
    from app.core.scene import History, OperationDraft
    from app.core.types import (
        BaseParams,
        Document,
        DocumentChange,
        DocumentState,
        OpContext,
        OpResult,
    )

    @op_params
    class PairParams(BaseParams):
        pass

    registry = Registry()

    @register_op(
        name="fit_probe",
        title="Passungsprobe",
        category="primitive",
        params=PairParams,
        consumes=0,
        produces=2,
        registry=registry,
    )
    def make(ctx: OpContext) -> OpResult:
        return OpResult(
            outputs=[
                replace(
                    entry,
                    id="",
                    features={
                        key: replace(feature, recognised=False)
                        for key, feature in entry.features.items()
                    },
                )
                for entry in pair(profile).objects.values()
            ]
        )

    document = Document(format_version=1, app_version="0.0.1")
    history = History(document, registry=registry)
    fit = Fit(
        "pair", FeatureRef("obj_1", "mating"), FeatureRef("obj_2", "mating"), "clearance", 0.4
    )
    history.apply(
        "Passungsprobe",
        [OperationDraft(op="fit_probe")],
        changes=DocumentChange(before=DocumentState(fits=()), after=DocumentState(fits=(fit,))),
    )
    return document, history, registry


@pytest.mark.parametrize(
    "finish", ["check_fits", "check_placement", "check_bodies_in_one_place", "check_thin_walls"]
)
def test_cancelled_final_checks_publish_neither_cache_nor_completion(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, finish: str
) -> None:
    import importlib

    from app.core.scene import ResultCache, evaluate

    document, _history, registry = fit_document(profile)
    module = importlib.import_module("app.core.scene.evaluate")
    original = getattr(module, finish)
    signal = CancelSignal()
    cache = ResultCache()
    progress = []

    def cancel(*args, **kwargs):
        result = original(*args, **kwargs)
        signal.cancel()
        return result

    monkeypatch.setattr(module, finish, cancel)
    with pytest.raises(OperationCancelled):
        evaluate(
            document,
            profile,
            registry=registry,
            cache=cache,
            cancelled=signal,
            progress=lambda *args: progress.append(args),
        )
    assert len(cache) == 0
    assert (1.0, "") not in progress


def test_export_reuses_the_geometry_finding_and_propagates_cancel(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.export.writer import check_before_export
    from app.core.scene import fits

    scene = pair(profile)
    findings = check_before_export(list(scene.objects.values()), profile, {}, scene=scene)
    assert [finding for finding in findings if finding.code.startswith("fit.")] == check(
        scene, profile
    )
    signal = CancelSignal()
    original = fits.check

    def cancel(*args, **kwargs):
        assert kwargs["cancelled"] is signal
        signal.cancel()
        return original(*args, **kwargs)

    monkeypatch.setattr(fits, "check", cancel)
    with pytest.raises(OperationCancelled):
        check_before_export(
            list(scene.objects.values()), profile, {}, scene=scene, cancelled=signal
        )


def test_export_selected_pin_keeps_the_relationship_warning(profile: Profile) -> None:
    from app.core.export.writer import check_before_export

    scene = pair(profile)
    found = check_before_export([scene.objects["pin"]], profile, {}, scene=scene)
    assert [finding for finding in found if finding.code.startswith("fit.")] == check(
        scene, profile
    )


@pytest.mark.parametrize("mixed", [False, True])
def test_invalid_native_input_is_never_accepted_by_either_probe(
    profile: Profile, mixed: bool
) -> None:
    from app.core.brep.kernel import Solid

    scene = native_pair(profile)
    pin = scene.objects["pin"]
    scene.objects["pin"] = replace(pin, mesh=Solid(pin.mesh.faces()[0]))
    if mixed:
        scene.objects["socket"] = pair(profile).objects["socket"]
    assert geometry_finding(scene).code == "fit.geometry_failed"


def test_native_kernel_failure_after_build_preserves_original_bytes(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.brep import kernel

    scene = native_pair(profile, floor=True)
    before = native_bytes(scene)
    original = kernel.boolean_builder

    class FailAfterBuild:
        def __init__(self, *args, **kwargs):
            self.builder = original(*args, **kwargs)

        def Build(self):  # noqa: N802 — native Schnittstelle
            self.builder.Build()
            raise RuntimeError("forced native failure after build")

    monkeypatch.setattr(kernel, "boolean_builder", FailAfterBuild)
    assert geometry_finding(scene).code == "fit.geometry_failed"
    assert native_bytes(scene) == before


def test_real_document_cache_reopen_undo_redo_and_export_share_collision(
    profile: Profile, tmp_path
) -> None:
    from app.core.export.writer import check_before_export
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, ResultCache, evaluate
    from app.core.scene.cache import DiskCache
    from app.core.scene.migrations import FORMAT_VERSION
    from app.core.scene.project import Project, load, save

    document, history, registry = fit_document(profile)
    document.format_version = FORMAT_VERSION
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    first = evaluate(document, profile, registry=registry, cache=cache)
    expected = [
        finding for finding in first.scene.report.findings if finding.code.startswith("fit.")
    ]
    assert len(expected) == 1 and expected[0].code == "fit.collision"
    assert len(cache) == 1
    repeated = evaluate(document, profile, registry=registry, cache=cache)
    assert repeated.scene.report == first.scene.report
    path = save(Project(document), tmp_path / "fit.p3d")
    opened = load(path)
    fresh_cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    restored = evaluate(opened.document, profile, registry=registry, cache=fresh_cache)
    assert fresh_cache.statistics.disk_hits == 1
    assert restored.scene.report == first.scene.report
    history = History(opened.document, registry=registry)
    history.undo()
    undone = evaluate(opened.document, profile, registry=registry, cache=fresh_cache)
    assert not undone.scene.objects and not undone.scene.fits
    history.redo()
    redone = evaluate(opened.document, profile, registry=registry, cache=fresh_cache)
    assert redone.scene.report == first.scene.report
    exported = check_before_export(
        list(redone.scene.objects.values()),
        profile,
        {},
        scene=redone.scene,
        document=opened.document,
    )
    assert [finding for finding in exported if finding.code.startswith("fit.")] == expected
