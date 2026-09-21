"""Wulst und Kehle — Torusmerkmale versetzen, verdoppeln, drehen, ändern, entfernen (P2.6).

Ein Ring auf einem Schaft ist entweder ein Wulst (Material) oder eine Kehle
(Hohlraum). Beide Kerne bekommen dieselben fünf Handlungen: exakt über das
Wegnehmen der Ringfläche (``brep.edit.defeatured``) und den vollen Ring aus
den Kennzahlen (``brep.edit.torus``), am Netz über den an den Randringen
beschnittenen Ring (``prepare_ops._torus_tool_mesh``) und denselben vollen
Ring. Die Sollwerte sind Analytik: Ein Ring R/r auf einem Schaft vom
Radius R trägt außen ``π²r²R + 4πr³/3`` und nimmt innen ``π²r²R − 4πr³/3``
(Pappus über die Halbscheiben mit ihren Schwerpunkten bei ``R ± 4r/3π``).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.types import Profile, SceneObject
from tests.test_missing_ops import run

SHAFT_RADIUS = 10.0
SHAFT_HEIGHT = 40.0
TUBE_RADIUS = 3.0
SHAFT_VOLUME = math.pi * SHAFT_RADIUS**2 * SHAFT_HEIGHT


def _bead(radius: float, ring: float = SHAFT_RADIUS) -> float:
    """Was ein Ring R/r auf einem Schaft vom Radius R außen aufträgt."""
    return math.pi**2 * radius**2 * ring + 4.0 * math.pi * radius**3 / 3.0


def _groove(radius: float, ring: float = SHAFT_RADIUS) -> float:
    """Was ein Ring R/r aus einem Schaft vom Radius R herausnimmt."""
    return math.pi**2 * radius**2 * ring - 4.0 * math.pi * radius**3 / 3.0


def _kernel() -> Any:
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    return kernel


def _ridged_shaft(kind: str, *, recess: bool) -> SceneObject:
    """Schaft Ø 20 × 40 mit einem Ring R 10 / r 3 in halber Höhe — Wulst oder Kehle."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.perceive.features import detect

    shaft = Solid(BRepPrimAPI_MakeCylinder(SHAFT_RADIUS, SHAFT_HEIGHT).Shape())
    ring = Solid(
        BRepPrimAPI_MakeTorus(
            gp_Ax2(gp_Pnt(0.0, 0.0, SHAFT_HEIGHT / 2.0), gp_Dir(0.0, 0.0, 1.0)),
            SHAFT_RADIUS,
            TUBE_RADIUS,
        ).Shape()
    )
    body = edit.unified(edit.boolean("difference" if recess else "union", [shaft, ring]))
    if kind == "brep":
        return SceneObject(
            id="obj_1", name="Schaft", mesh=body, kind="brep", features=features_of(body)
        )
    mesh = as_mesh_data(body)
    return SceneObject(id="obj_1", name="Schaft", mesh=mesh, kind="mesh", features=detect(mesh))


def _the_torus(entry: SceneObject) -> Any:
    found = [feature for feature in entry.features.values() if feature.kind == "torus"]
    assert len(found) == 1, sorted((f.id, f.kind) for f in entry.features.values())
    return found[0]


def _volume(entry: SceneObject) -> float:
    return float(entry.mesh.volume)


def _stays(result: Any, kind: str) -> SceneObject:
    """Der Körper bleibt, was er war: exakt exakt, ein Netz ein Netz — und geschlossen."""
    output = result.outputs[0]
    assert output.kind == kind
    assert not any(finding.converts_exact_body for finding in result.findings)
    if kind == "brep":
        assert output.mesh.is_closed
        assert output.mesh.solid_count == 1
    else:
        assert isinstance(output.mesh, MeshData)
        assert output.mesh.is_watertight and output.mesh.component_count == 1
    return output


def _tolerance(kind: str) -> float:
    """Exakt die Analytik auf 10⁻⁹; am Netz die Tessellierung von Ring und Schaft (0,05 mm Sag)."""
    return 1e-9 if kind == "brep" else 6e-3


@pytest.fixture(params=["brep", "mesh"])
def kind(request: Any) -> str:
    if request.param == "brep":
        _kernel()
    load_operations()
    return str(request.param)


@pytest.mark.parametrize("recess", [False, True])
def test_the_ring_is_recognised_with_its_measures(kind: str, recess: bool) -> None:
    source = _ridged_shaft(kind, recess=recess)
    ring = _the_torus(source)
    assert ring.params["recess"] is recess
    assert ring.params["diameter"] == pytest.approx(2.0 * SHAFT_RADIUS, abs=0.05)
    assert ring.params["tube_diameter"] == pytest.approx(2.0 * TUBE_RADIUS, abs=0.05)
    assert ring.params["centre"] == pytest.approx((0.0, 0.0, SHAFT_HEIGHT / 2.0), abs=0.05)
    expected = SHAFT_VOLUME + (-_groove(TUBE_RADIUS) if recess else _bead(TUBE_RADIUS))
    assert _volume(source) == pytest.approx(expected, rel=_tolerance(kind))


@pytest.mark.parametrize("recess", [False, True])
def test_removing_the_ring_leaves_the_plain_shaft(
    kind: str, recess: bool, profile: Profile
) -> None:
    source = _ridged_shaft(kind, recess=recess)
    ring = _the_torus(source)
    result = run("remove_feature", source, profile, at_feature=ring.id)
    output = _stays(result, kind)
    assert _volume(output) == pytest.approx(SHAFT_VOLUME, rel=_tolerance(kind))
    assert ring.id not in output.features
    assert any(finding.code == "remove_feature.gone" for finding in result.findings)


@pytest.mark.parametrize("recess", [False, True])
def test_moving_the_ring_along_the_shaft_keeps_the_volume(
    kind: str, recess: bool, profile: Profile
) -> None:
    source = _ridged_shaft(kind, recess=recess)
    ring = _the_torus(source)
    result = run("move_feature", source, profile, at_feature=ring.id, x=0.0, y=0.0, z=12.0)
    output = _stays(result, kind)
    assert _volume(output) == pytest.approx(_volume(source), rel=_tolerance(kind))
    moved = output.features[ring.id]
    assert moved.kind == "torus"
    assert moved.params["centre"] == pytest.approx((0.0, 0.0, 12.0), abs=0.05)
    # Unabhängig nachgemessen: An der alten Stelle ist der Schaft wieder glatt,
    # an der neuen sitzt der Ring.
    if kind == "brep":
        from app.core.brep.features import features_of

        found = [f for f in features_of(output.mesh).values() if f.kind == "torus"]
    else:
        from app.core.perceive.features import detect_tori

        found = detect_tori(as_mesh_data(output.mesh))
    assert len(found) == 1
    assert found[0].params["centre"][2] == pytest.approx(12.0, abs=0.05)
    assert found[0].params["recess"] is recess


@pytest.mark.parametrize("recess", [False, True])
def test_duplicating_the_ring_adds_a_second_one(kind: str, recess: bool, profile: Profile) -> None:
    source = _ridged_shaft(kind, recess=recess)
    ring = _the_torus(source)
    result = run("duplicate_feature", source, profile, at_feature=ring.id, x=0.0, y=0.0, z=8.0)
    output = _stays(result, kind)
    change = -_groove(TUBE_RADIUS) if recess else _bead(TUBE_RADIUS)
    assert _volume(output) == pytest.approx(_volume(source) + change, rel=_tolerance(kind))
    tori = [feature for feature in output.features.values() if feature.kind == "torus"]
    assert len(tori) == 2
    assert sorted(round(float(f.params["centre"][2]), 2) for f in tori) == [8.0, 20.0]


@pytest.mark.parametrize("recess", [False, True])
def test_resizing_the_tube_changes_only_the_ring(kind: str, recess: bool, profile: Profile) -> None:
    source = _ridged_shaft(kind, recess=recess)
    ring = _the_torus(source)
    result = run(
        "resize_feature",
        source,
        profile,
        at_feature=ring.id,
        diameter=2.0 * SHAFT_RADIUS,
        tube_diameter=4.0,
    )
    output = _stays(result, kind)
    expected = SHAFT_VOLUME + (-_groove(2.0) if recess else _bead(2.0))
    assert _volume(output) == pytest.approx(expected, rel=_tolerance(kind))
    changed = output.features[ring.id]
    assert changed.params["tube_diameter"] == pytest.approx(4.0, abs=0.05)
    assert changed.params["diameter"] == pytest.approx(2.0 * SHAFT_RADIUS, abs=0.05)


def test_a_tube_as_wide_as_the_ring_is_refused(kind: str, profile: Profile) -> None:
    source = _ridged_shaft(kind, recess=False)
    ring = _the_torus(source)
    with pytest.raises(ValidationError) as caught:
        run(
            "resize_feature", source, profile, at_feature=ring.id, diameter=20.0, tube_diameter=20.0
        )
    assert caught.value.constraint == "torus_tube"
    assert caught.value.suggestions


def test_turning_the_ring_about_its_own_axis_changes_nothing(kind: str, profile: Profile) -> None:
    source = _ridged_shaft(kind, recess=False)
    ring = _the_torus(source)
    result = run("rotate_feature", source, profile, at_feature=ring.id, axis="z", angle=45.0)
    assert result.outputs[0] is source
    assert [finding.code for finding in result.findings] == ["rotate_feature.unchanged"]


@pytest.mark.parametrize("recess", [False, True])
def test_tilting_the_ring_sets_it_with_the_turned_axis(
    kind: str, recess: bool, profile: Profile
) -> None:
    source = _ridged_shaft(kind, recess=recess)
    ring = _the_torus(source)
    result = run("rotate_feature", source, profile, at_feature=ring.id, axis="x", angle=90.0)
    output = _stays(result, kind)
    # Der quer gestellte Ring hat die gedrehte Achse. Ein Wulst zerfällt dabei
    # exakt in zwei Lappen links und rechts des Schafts — zwei Ringflächen, die
    # sich nicht berühren —, und dann sagt ein Befund, dass die Kennung nicht
    # weitergeführt werden konnte, statt einen der beiden still zu wählen.
    tilted = [
        feature
        for feature in output.features.values()
        if feature.kind == "torus" and abs(float(feature.params["axis"][2])) < 1e-6
    ]
    assert tilted
    assert all(abs(float(f.params["axis"][1])) == pytest.approx(1.0, abs=1e-6) for f in tilted)
    if ring.id not in output.features:
        assert any(finding.code == "rotate_feature.feature_lost" for finding in result.findings)
    # Der gekippte Ring steht quer im Schaft: ein Wulst ragt seitlich heraus, eine
    # Kehle schneidet quer hinein — an der alten Stelle ist der Schaft glatt.
    if recess:
        assert _volume(output) < SHAFT_VOLUME
    else:
        assert _volume(output) > SHAFT_VOLUME
    assert _volume(output) != pytest.approx(_volume(source), rel=1e-6)


def test_a_ring_that_is_the_whole_body_says_so(kind: str, profile: Profile) -> None:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.perceive.features import detect

    body = Solid(BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(0, 0, 5), gp_Dir(0, 0, 1)), 17.0, 3.0).Shape())
    if kind == "brep":
        source = SceneObject(
            id="obj_1", name="Ring", mesh=body, kind="brep", features=features_of(body)
        )
    else:
        mesh = as_mesh_data(body)
        source = SceneObject(id="obj_1", name="Ring", mesh=mesh, kind="mesh", features=detect(mesh))
    ring = _the_torus(source)
    with pytest.raises(ValidationError) as caught:
        run("move_feature", source, profile, at_feature=ring.id, x=0.0, y=0.0, z=9.0)
    assert caught.value.constraint == "not_movable"
    assert "ganze Körper" in str(caught.value.detail)
    from app.core.perceive.actions import actions_for

    rows = actions_for(ring, source.features, mesh=as_mesh_data(source.mesh))
    assert rows and all(row.op is None for row in rows)


def test_the_exact_ring_survives_a_step_round_trip(profile: Profile) -> None:
    _kernel()
    load_operations()
    from app.core.brep import step

    source = _ridged_shaft("brep", recess=True)
    ring = _the_torus(source)
    result = run("move_feature", source, profile, at_feature=ring.id, x=0.0, y=0.0, z=30.0)
    solid: Any = result.outputs[0].mesh
    back = step.read(step.write(solid))
    assert back.volume == pytest.approx(solid.volume, rel=1e-9)
    assert back.face_count == solid.face_count


def test_both_kernels_agree_on_the_moved_ring(profile: Profile) -> None:
    """Dieselbe Handlung, zwei Auswerter: Netz und exakt weichen nur um die Facettierung ab."""
    _kernel()
    load_operations()
    exact = run(
        "move_feature",
        _ridged_shaft("brep", recess=False),
        profile,
        at_feature="torus_1",
        x=0.0,
        y=0.0,
        z=12.0,
    ).outputs[0]
    meshed = run(
        "move_feature",
        _ridged_shaft("mesh", recess=False),
        profile,
        at_feature="torus_1",
        x=0.0,
        y=0.0,
        z=12.0,
    ).outputs[0]
    assert abs(_volume(meshed) / _volume(exact) - 1.0) < 6e-3
    assert np.allclose(
        as_mesh_data(meshed.mesh).bounds.maximum, exact.mesh.bounds.maximum, atol=0.05
    )
