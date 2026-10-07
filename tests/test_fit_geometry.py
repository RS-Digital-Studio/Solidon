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
from app.core.scene.fits import check, overlap
from app.core.types import Feature, FeatureRef, Fit, Profile, Scene, SceneObject
from tests.helpers import exact_kernel


def flush_pair(
    profile: Profile,
    *,
    kind: str = "mesh",
    offset: tuple[float, float, float] = (20.0, 0.0, 0.0),
    bottom: bool = False,
) -> Scene:
    """Zwei echte 10-mm-Würfel und ihre obere bzw. untere ebene Fläche."""
    from app.core.brep.edit import box, moved
    from app.core.geom.mesh import as_mesh_data

    objects = {}
    for index, (name, corner) in enumerate((("socket", (0.0, 0.0, 0.0)), ("pin", offset))):
        native = kind == "native" or kind == f"mixed_{index}"
        if native:
            body = moved(box(10.0, 10.0, 10.0), (corner[0] + 5, corner[1] + 5, corner[2]))
        else:
            mesh = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
            mesh.apply_translation(np.asarray(corner) + 5)
            body = MeshData(mesh)
        lower = index == 1 and bottom
        normal = (0.0, 0.0, -1.0 if lower else 1.0)
        centre = (corner[0] + 5, corner[1] + 5, corner[2] + (0 if lower else 10))
        mesh = as_mesh_data(body).raw
        indices = tuple(int(i) for i in np.flatnonzero(mesh.face_normals @ normal > 0.99))
        feature = Feature(
            "mating",
            "face",
            "generated",
            {"centre": centre, "normal": normal, "area": 100.0},
            face_indices=indices,
            measure_sources=dict.fromkeys(
                ("centre", "normal", "area"), "native" if native else "facets"
            ),
        )
        objects[name] = SceneObject(name, name, mesh=body, features={"mating": feature})
    return Scene(
        objects=objects,
        profile=profile,
        fits=[Fit("flush", FeatureRef("socket", "mating"), FeatureRef("pin", "mating"), "flush")],
    )


@pytest.mark.parametrize("kind", ["mesh", "native", "mixed_0", "mixed_1"])
@pytest.mark.parametrize(
    ("offset", "bottom", "volume", "violated"),
    [
        ((20.0, 0.0, 0.0), False, 0.0, False),
        ((0.0, 0.0, 10.0), True, 0.0, False),
        ((5.0, 0.0, 0.0), False, 5 * 10 * 10, False),
        ((0.0, 0.0, 10.025), True, 0.0, False),
        ((0.0, 0.0, 0.3), False, 10 * 10 * 9.7, True),
        ((10.0, 0.0, 10.0), True, 0.0, False),
        ((10.0, 10.0, 10.0), True, 0.0, False),
    ],
)
def test_flush_planes_and_full_body_overlap_are_independent(
    profile: Profile, kind: str, offset, bottom: bool, volume: float, violated: bool
) -> None:
    """Koplanar heißt weder Kontakt noch Kollisionsfreiheit; die Würfel liefern das Soll."""
    from app.core.geom.mesh import as_mesh_data

    scene = flush_pair(profile, kind=kind, offset=offset, bottom=bottom)
    sources = {
        name: dict(entry.features["mating"].measure_sources)
        for name, entry in scene.objects.items()
    }
    meshes = {name: as_mesh_data(entry.mesh).raw for name, entry in scene.objects.items()}
    before = {name: (mesh.vertices.copy(), mesh.faces.copy()) for name, mesh in meshes.items()}
    native_scene = replace(
        scene,
        objects={
            name: entry for name, entry in scene.objects.items() if hasattr(entry.mesh, "shape")
        },
    )
    native_before = native_bytes(native_scene)
    findings = check(scene, profile)
    expected = ["fit.violated"] if violated else []
    if kind.startswith("mixed"):
        # Eine Näherung sagt es immer — als Warnung bei Überschneidung, sonst als Hinweis.
        expected.append("fit.geometry_approximate")
    elif volume:
        expected.append("fit.collision")
    assert [finding.code for finding in findings] == expected
    probe = overlap(scene, scene.fits[0])
    assert probe is not None
    assert probe.source == ("mixed" if kind.startswith("mixed") else kind)
    assert probe.overlap_mm3 == pytest.approx(volume, abs=1e-9)
    assert probe.intersects is (volume > 0.0)
    if kind.startswith("mixed") or volume:
        found = findings[-1]
        assert found.values["geometry_source"] == probe.source
        assert found.values["overlap_mm3"] == pytest.approx(volume, abs=1e-9)
        assert found.values["intersects"] is (volume > 0.0)
        assert found.severity == ("warning" if volume else "info")
        if not volume:
            assert "Flächenkontakt" in str(found.message)
            assert "nicht nachgewiesen" in str(found.message)
    assert native_bytes(native_scene) == native_before
    for name, mesh in meshes.items():
        np.testing.assert_array_equal(mesh.vertices, before[name][0])
        np.testing.assert_array_equal(mesh.faces, before[name][1])
        assert scene.objects[name].features["mating"].measure_sources == sources[name]


@pytest.mark.parametrize("reason", ["different_plates", "same_body"])
def test_flush_without_two_bodies_in_one_plate_has_no_volume_result(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    """Unvergleichbare Platten und zwei Ebenen eines Körpers sind keine Körperkollision —
    und auch kein Befund: Die Lage ist nicht modelliert, also gibt es nichts zu melden.
    """
    from app.core.geom import measure

    scene = flush_pair(profile, offset=(0.0, 0.0, 0.0))
    if reason == "different_plates":
        scene.objects["pin"].plate = 1
    else:
        entry = scene.objects["socket"]
        original = entry.features["mating"]
        # Zwei echte Teildreiecke derselben ebenen Würfelseite, keine Kopie desselben Verweises.
        for name, index in zip(("mating", "other"), original.face_indices, strict=True):
            entry.features[name] = replace(
                original,
                id=name,
                face_indices=(index,),
                params={
                    **original.params,
                    "centre": tuple(entry.mesh.raw.triangles_center[index]),
                    "area": 50.0,
                },
            )
        scene.fits[0] = replace(scene.fits[0], b=FeatureRef("socket", "other"))

    def forbidden(*args, **kwargs):
        pytest.fail("there is no applicable shared body pose")

    monkeypatch.setattr(measure, "body_overlap", forbidden)
    assert check(scene, profile) == []
    assert overlap(scene, scene.fits[0]) is None


@pytest.mark.parametrize("normal", [None, (0.0, 0.0, 0.0), (float("nan"), 0.0, 1.0)])
def test_unmeasured_flush_plane_does_not_hide_body_collision(profile: Profile, normal) -> None:
    scene = flush_pair(profile, offset=(5.0, 0.0, 0.0))
    feature = scene.objects["pin"].features["mating"]
    scene.objects["pin"].features["mating"] = replace(
        feature, params={**feature.params, "normal": normal}
    )
    findings = check(scene, profile)
    assert [finding.code for finding in findings] == ["fit.not_measurable", "fit.collision"]
    assert findings[-1].values["overlap_mm3"] == pytest.approx(500.0)


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
    """Der Körperbefund neben einem möglichen Nennmaßbefund — oder None, wenn die
    Probe nichts zu sagen hat: keine belegte Lage oder keine Überschneidung.
    """
    found = [finding for finding in check(scene, scene.profile) if finding.code != "fit.violated"]
    assert len(found) <= 1
    return found[0] if found else None


def test_fine_pin_intersects_coarse_socket_despite_matching_diameters(profile: Profile) -> None:
    scene = pair(profile)
    before = {
        key: (entry.mesh.raw.vertices.copy(), entry.mesh.raw.faces.copy())
        for key, entry in scene.objects.items()
    }
    finding = geometry_finding(scene)
    assert finding is not None and finding.code == "fit.collision"
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


@pytest.mark.parametrize("angle, expected", [(0.0, None), (math.pi / 16, "fit.collision")])
def test_polygon_phase_changes_collision_without_changing_diameter(
    profile: Profile, angle: float, expected: str | None
) -> None:
    """Dieselben Durchmesser, zwei Drehlagen: einmal frei — kein Befund, die Zahl
    sagt null —, einmal eine Kollision der Ecken."""
    scene = pair(profile, segments=16, angle=angle)
    finding = geometry_finding(scene)
    assert (finding.code if finding is not None else None) == expected
    probe = overlap(scene, scene.fits[0])
    assert probe is not None
    assert probe.intersects is (expected is not None)


@pytest.mark.parametrize("change", ["plate", "apart", "no_axis", "no_depth", "axially_apart"])
def test_unproven_installation_pose_is_no_finding_and_no_number(
    profile: Profile, change: str
) -> None:
    """Andere Platte, weit auseinander, ohne Achse oder Tiefe: keine Lage, kein Befund,
    keine Zahl — bis zum 21.09.2026 stand hier eine unbehebbare Warnung."""
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
    assert geometry_finding(scene) is None
    assert overlap(scene, scene.fits[0]) is None


def test_open_mesh_is_failed_not_a_valid_empty_intersection(profile: Profile) -> None:
    scene = pair(profile, segments=16)
    pin = scene.objects["pin"]
    mesh = pin.mesh.raw
    scene.objects["pin"] = replace(
        pin, mesh=MeshData(trimesh.Trimesh(mesh.vertices, mesh.faces[:-1], process=False))
    )
    failed = geometry_finding(scene)
    assert failed is not None and failed.code == "fit.geometry_failed"


def test_press_probe_does_not_approve_all_interference(profile: Profile) -> None:
    """Übermaß ist bei einer Presspassung vorgesehen — die Probe sagt als Hinweis,
    dass sie weder Montage noch Verformung belegt, und nennt die gemessene
    Überschneidung; eine Warnung an jeder Presspassung wäre Lärm."""
    scene = pair(profile)
    scene.fits = [replace(scene.fits[0], kind="press", tolerance=-0.1)]
    pin = scene.objects["pin"]
    pin.mesh = MeshData(trimesh.creation.cylinder(radius=15.05, height=10.0, sections=256))
    feature = pin.features["mating"]
    pin.features["mating"] = replace(feature, params={**feature.params, "diameter": 30.1})
    assert not any(item.code == "fit.violated" for item in check(scene, profile))
    finding = geometry_finding(scene)
    assert finding is not None and finding.code == "fit.press_unverified"
    assert finding.severity == "info"
    assert finding.values["overlap_mm3"] > 0.0
    assert "weder die Montage noch die Verformung" in str(finding.message)


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
    assert [item.code for item in check(scene, profile)] == ["fit.mesh_uncertain"]


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
    """Auch Topologie- und Prüfkennzeichen zählen zum unveränderten nativen Eingang.

    Eine Szene ohne Körper braucht keinen exakten Kern: Die Netzfälle rufen
    den Helfer mit leerer nativer Szene und übersprangen sich sonst ohne
    OpenCASCADE (Review 06.10.2026, N5).
    """
    if not scene.objects:
        return {}
    exact_kernel()
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
    probe = overlap(scene, scene.fits[0])
    assert probe is not None and probe.source == "native"
    assert probe.overlap_mm3 == pytest.approx(math.pi * 14.8**2 if floor else 0.0)
    if floor:
        assert found is not None and found.code == "fit.collision"
        assert found.values["geometry_source"] == "native"
        assert found.values["overlap_mm3"] == pytest.approx(math.pi * 14.8**2)
    else:
        assert found is None, "no overlap, no finding"
    assert native_bytes(scene) == before


@pytest.mark.parametrize("native_side", ["socket", "pin"])
def test_mixed_probe_is_explicitly_a_mesh_approximation(profile: Profile, native_side: str) -> None:
    scene = pair(profile)
    scene.objects[native_side] = native_pair(profile).objects[native_side]
    found = geometry_finding(scene)
    assert found is not None and found.code == "fit.geometry_approximate"
    assert found.values["geometry_source"] == "mixed"
    assert found.values["intersects"] is (native_side == "pin")
    # Eine Näherung ohne Überschneidung ist ein Hinweis, mit einer eine Warnung.
    assert found.severity == ("warning" if native_side == "pin" else "info")


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
    assert actual is not None and expected is not None
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
    assert found is not None and original is not None
    assert found.code == original.code
    assert found.values["overlap_mm3"] == pytest.approx(original.values["overlap_mm3"], rel=1e-8)


@pytest.mark.parametrize("flush", [False, True])
@pytest.mark.parametrize("native", [False, True])
def test_cancel_after_kernel_returns_no_geometry_result(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, native: bool, flush: bool
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

        scene = flush_pair(profile, kind="native") if flush else native_pair(profile)
        before = native_bytes(scene)
        monkeypatch.setattr(module, "boolean_builder", CancelAfterBuild)
    else:
        module = importlib.import_module("app.core.geom.boolean")
        original = module.boolean

        def cancel(*args, **kwargs):
            result = original(*args, **kwargs)
            signal.cancel()
            return result

        scene = flush_pair(profile) if flush else pair(profile, segments=16)
        monkeypatch.setattr(module, "boolean", cancel)
    with pytest.raises(OperationCancelled):
        check(scene, profile, cancelled=signal)
    if native:
        assert native_bytes(scene) == before


@pytest.mark.parametrize("flush", [False, True])
def test_kernel_error_is_not_clear_and_no_repair_is_attempted(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, flush: bool
) -> None:
    import importlib

    calls = []

    def fail(kind, meshes, **kwargs):
        calls.append((kind, kwargs["stages"], kwargs["allow_empty"]))
        raise RuntimeError("forced kernel error")

    monkeypatch.setattr(importlib.import_module("app.core.geom.boolean"), "boolean", fail)
    scene = flush_pair(profile) if flush else pair(profile)
    found = geometry_finding(scene)
    assert found is not None and found.code == "fit.geometry_failed"
    assert "overlap_mm3" not in found.values and "intersects" not in found.values
    assert calls == [("intersection", ("direct",), True)]


def fit_document(profile: Profile, *, flush: bool = False):
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
        scene = flush_pair(profile, offset=(5.0, 0.0, 0.0)) if flush else pair(profile)
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
                for entry in scene.objects.values()
            ]
        )

    document = Document(format_version=1, app_version="0.0.1")
    history = History(document, registry=registry)
    fit = Fit(
        "pair",
        FeatureRef("obj_1", "mating"),
        FeatureRef("obj_2", "mating"),
        "flush" if flush else "clearance",
        0.4,
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
@pytest.mark.parametrize("flush", [False, True])
def test_cancelled_final_checks_publish_neither_cache_nor_completion(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, finish: str, flush: bool
) -> None:
    import importlib

    from app.core.scene import ResultCache, evaluate

    document, _history, registry = fit_document(profile, flush=flush)
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
    if flush and finish == "check_thin_walls":
        # Zwei bündige Quader tragen keine belegte Bohrungswand. Dieser
        # Prüfauftrag ist nachweislich unzutreffend und beginnt nicht.
        result = evaluate(
            document,
            profile,
            registry=registry,
            cache=cache,
            cancelled=signal,
            progress=lambda *args: progress.append(args),
        )
        status = next(value for value in result.check_states if value.key == "scene.thin_walls")
        assert result.complete and status.state == "not_applicable"
        assert not status.applicable and not signal.is_cancelled
        return
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


@pytest.mark.parametrize("flush", [False, True])
def test_export_reuses_the_geometry_finding_and_propagates_cancel(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, flush: bool
) -> None:
    from app.core.export.writer import check_before_export
    from app.core.scene import fits

    scene = flush_pair(profile, offset=(5.0, 0.0, 0.0)) if flush else pair(profile)
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


@pytest.mark.parametrize("flush", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
def test_invalid_native_input_is_never_accepted_by_either_probe(
    profile: Profile, mixed: bool, flush: bool
) -> None:
    from app.core.brep.kernel import Solid

    scene = flush_pair(profile, kind="native") if flush else native_pair(profile)
    pin = scene.objects["pin"]
    scene.objects["pin"] = replace(pin, mesh=Solid(pin.mesh.faces()[0]))
    if mixed:
        source = flush_pair(profile) if flush else pair(profile)
        scene.objects["socket"] = source.objects["socket"]
    failed = geometry_finding(scene)
    assert failed is not None and failed.code == "fit.geometry_failed"


@pytest.mark.parametrize("flush", [False, True])
def test_native_kernel_failure_after_build_preserves_original_bytes(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, flush: bool
) -> None:
    from app.core.brep import kernel

    scene = (
        flush_pair(profile, kind="native", offset=(5.0, 0.0, 0.0))
        if flush
        else native_pair(profile, floor=True)
    )
    before = native_bytes(scene)
    original = kernel.boolean_builder

    class FailAfterBuild:
        def __init__(self, *args, **kwargs):
            self.builder = original(*args, **kwargs)

        def Build(self):  # noqa: N802 — native Schnittstelle
            self.builder.Build()
            raise RuntimeError("forced native failure after build")

    monkeypatch.setattr(kernel, "boolean_builder", FailAfterBuild)
    failed = geometry_finding(scene)
    assert failed is not None and failed.code == "fit.geometry_failed"
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


@pytest.mark.parametrize("kind", ["mesh", "native", "mixed_0", "mixed_1"])
def test_flush_common_rigid_transform_preserves_both_statements(
    profile: Profile, kind: str
) -> None:
    """Körper und ausgewählte Fläche werden durch den echten gemeinsamen Transformweg bewegt."""
    from app.core.geom.transform import moved_object

    scene = flush_pair(profile, kind=kind, offset=(5.0, 0.0, 0.0))
    before = check(scene, profile)
    matrix = trimesh.transformations.rotation_matrix(0.79, (1.0, 2.0, 3.0))
    matrix[:3, 3] = (53.0, -7.0, 125.0)
    scene.objects = {name: moved_object(entry, matrix) for name, entry in scene.objects.items()}
    found = check(scene, profile)
    assert [finding.code for finding in found] == [finding.code for finding in before]
    assert len(found) == 1
    assert found[0].values["overlap_mm3"] == pytest.approx(500.0, rel=1e-9)
    for entry in scene.objects.values():
        assert entry.features["mating"].measure_sources


def test_open_flush_body_is_not_clear(profile: Profile) -> None:
    scene = flush_pair(profile)
    entry = scene.objects["pin"]
    mesh = entry.mesh.raw
    entry.mesh = MeshData(trimesh.Trimesh(mesh.vertices, mesh.faces[:-1], process=False))
    findings = check(scene, profile)
    assert [finding.code for finding in findings] == ["fit.geometry_failed"]
    assert "overlap_mm3" not in findings[0].values


def test_flush_missing_reference_stays_an_error(profile: Profile) -> None:
    scene = flush_pair(profile)
    scene.fits[0] = replace(scene.fits[0], b=FeatureRef("pin", "missing"))
    assert [finding.code for finding in check(scene, profile)] == ["fit.missing_feature"]


@pytest.mark.parametrize(
    ("kind", "offset", "plate", "codes", "caption"),
    [
        ("mesh", (20.0, 0.0, 0.0), 0, [], "Teil einer Passung"),
        ("native", (5.0, 0.0, 0.0), 0, ["fit.collision"], "Passung verletzt"),
        # Die Näherung ohne Überschneidung ist ein Hinweis, und ein Hinweis färbt
        # die Karte nicht um.
        ("mixed_1", (20.0, 0.0, 0.0), 0, ["fit.geometry_approximate"], "Teil einer Passung"),
        # Zwei Platten: keine Lage, kein Befund — und damit auch nichts zu prüfen.
        ("mesh", (5.0, 0.0, 0.0), 1, [], "Teil einer Passung"),
        ("mesh", (0.0, 0.0, 0.3), 0, ["fit.violated", "fit.collision"], "Passung verletzt"),
    ],
)
def test_flush_report_reaches_map_digest_agent_and_either_export_partner(
    profile: Profile, kind: str, offset, plate: int, codes: list[str], caption: str
) -> None:
    """Die Verbraucher sehen die echten Prüfergebnisse ohne neue eigene Geometrieprobe."""
    from app.core.agent import checks
    from app.core.export.writer import check_before_export
    from app.core.perceive import maps
    from app.core.perceive.digest import digest
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Document, Report

    scene = flush_pair(profile, kind=kind, offset=offset)
    scene.objects["pin"].plate = plate
    scene.report = Report(tuple(check(scene, profile)))
    document = Document(format_version=1, app_version="0.0.1", fits=list(scene.fits))
    text = digest(scene, document)
    fit_findings = list(scene.report.findings)
    assert [finding.code for finding in fit_findings] == codes
    for finding in fit_findings:
        assert ("verletzt" if finding.code == "fit.violated" else str(finding.message)) in text
    result = EvaluationResult(scene=scene)
    assert [
        finding for finding in checks.check(result) if finding.code.startswith("fit.")
    ] == fit_findings
    for entry in scene.objects.values():
        mapped = maps.build("fits", entry, scene=scene)
        selected = entry.features["mating"].face_indices
        assert selected
        assert {mapped.categories[int(mapped.values[index])] for index in selected} == {caption}
        exported = check_before_export([entry], profile, {}, scene=scene, document=document)
        assert [finding for finding in exported if finding.code.startswith("fit.")] == fit_findings


def test_flush_document_movement_cache_reopen_and_undo_preserve_both_checks(
    profile: Profile, tmp_path
) -> None:
    """Ein realer Verschiebeschritt beseitigt die Kollision und verletzt unabhängig die Ebene."""
    from app.core.bootstrap import load_operations
    from app.core.export.writer import check_before_export
    from app.core.geom.mesh import MeshCodec
    from app.core.registry import REGISTRY
    from app.core.scene import History, OperationDraft, ResultCache, evaluate
    from app.core.scene.cache import DiskCache
    from app.core.scene.migrations import FORMAT_VERSION
    from app.core.scene.project import Project, load, save

    load_operations()
    document, history, registry = fit_document(profile, flush=True)
    registry.register(REGISTRY.get("translate_object"))
    document.format_version = FORMAT_VERSION
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    collision = evaluate(document, profile, registry=registry, cache=cache)
    original = [
        finding for finding in collision.scene.report.findings if finding.code.startswith("fit.")
    ]
    assert [finding.code for finding in original] == ["fit.collision"]
    assert original[0].values["overlap_mm3"] == pytest.approx(500.0)
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 15.0, "dz": 0.3})],
    )
    moved = evaluate(document, profile, registry=registry, cache=cache)
    current = [
        finding for finding in moved.scene.report.findings if finding.code.startswith("fit.")
    ]
    assert [finding.code for finding in current] == ["fit.violated"]
    probe = overlap(moved.scene, moved.scene.fits[0])
    assert probe is not None and probe.overlap_mm3 == pytest.approx(0.0)
    assert (
        evaluate(document, profile, registry=registry, cache=cache).scene.report
        == moved.scene.report
    )
    opened = load(save(Project(document), tmp_path / "flush.p3d"))
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    restored = evaluate(opened.document, profile, registry=registry, cache=cache)
    assert cache.statistics.disk_hits == 2
    assert restored.scene.report == moved.scene.report
    history = History(opened.document, registry=registry)
    history.undo()
    undone = evaluate(opened.document, profile, registry=registry, cache=cache)
    assert undone.scene.report == collision.scene.report
    history.redo()
    redone = evaluate(opened.document, profile, registry=registry, cache=cache)
    assert redone.scene.report == moved.scene.report
    for entry in redone.scene.objects.values():
        exported = check_before_export(
            [entry], profile, {}, scene=redone.scene, document=opened.document
        )
        assert [finding for finding in exported if finding.code.startswith("fit.")] == current
