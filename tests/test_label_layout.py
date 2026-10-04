"""Schrift auf einer Bahn, um eine Rundung und als bündige Einlage (RM-184, Audit §9).

Die Zusagen stehen gegen analytische Körper: eine Platte 80 × 60 × 5 und ein
Zylinder Ø 40 × 40. Auf dem Bogen liegt jede Ecke der Schrift zwischen den
Radien ihrer Unter- und Oberkante; auf der Rundung liegt die erhabene Schrift
zwischen Mantel und Mantel plus Tiefe; die Einlage füllt ihre Tasche genau —
Träger und Einlage ergeben zusammen das Volumen von vorher, ohne gemeinsames
Volumen, und die Einlage schließt mit der Oberfläche ab.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.boolean import shared_volume
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, OpContext, Profile, Scene, SceneObject
from tests.helpers import exact_kernel


def _plate() -> SceneObject:
    body = trimesh.creation.box(extents=(80.0, 60.0, 5.0))
    body.apply_translation((0.0, 0.0, 2.5))
    return SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(body))


def _drum(*, with_feature: bool = True) -> SceneObject:
    body = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=256)
    body.apply_translation((0.0, 0.0, 20.0))
    features = (
        {
            "pin_1": Feature(
                id="pin_1",
                kind="pin",
                provenance="detected",
                params={"centre": (0.0, 0.0, 20.0), "axis": (0.0, 0.0, 1.0), "diameter": 40.0},
            )
        }
        if with_feature
        else {}
    )
    return SceneObject(id="obj_1", name="Dose", mesh=MeshData.of(body), features=features)


def _ring() -> SceneObject:
    """Ein Ring außen Ø 80, innen Ø 60, 30 hoch — Schrift innen an der Wand."""
    outer = trimesh.creation.cylinder(radius=40.0, height=30.0, sections=256)
    inner = trimesh.creation.cylinder(radius=30.0, height=40.0, sections=256)
    body = trimesh.boolean.difference([outer, inner])
    body.apply_translation((0.0, 0.0, 15.0))
    return SceneObject(
        id="obj_1",
        name="Ring",
        mesh=MeshData.of(body),
        features={
            "hole_1": Feature(
                id="hole_1",
                kind="hole",
                provenance="detected",
                params={"centre": (0.0, 0.0, 15.0), "axis": (0.0, 0.0, 1.0), "diameter": 60.0},
            )
        },
    )


def _run(op: str, entry: SceneObject, profile: Profile, **params: object) -> Any:
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def _added(before: MeshData, after: MeshData) -> np.ndarray:
    """Die Ecken des Ergebnisses, die nicht schon Ecken des Körpers waren."""
    old = {tuple(np.round(point, 6)) for point in np.asarray(before.raw.vertices)}
    return np.asarray(
        [point for point in np.asarray(after.raw.vertices) if tuple(np.round(point, 6)) not in old]
    )


# --- Auf einer Bahn ------------------------------------------------------------------------


def test_text_on_an_arc_lies_between_the_radii_of_its_lines(profile: Profile) -> None:
    """Bogen R 40 auf der Platte: jede neue Ecke zwischen 40 − h/2 und 40 + h/2 um die Mitte."""
    plate = _plate()
    size = 8.0
    straight = _run("label_text", plate, profile, text="SOLIDON", size=size, depth=0.6, z=5.0)
    arced = _run(
        "label_text", plate, profile, text="SOLIDON", size=size, depth=0.6, z=5.0, arc_radius=40.0
    )
    mesh = arced.outputs[0].mesh
    assert mesh.is_watertight
    letters = _added(plate.mesh, mesh)
    assert len(letters), "die Schrift steht auf der Platte"
    radius = np.hypot(letters[:, 0], letters[:, 1] + 40.0)
    straight_letters = _added(plate.mesh, straight.outputs[0].mesh)
    half = float(np.max(np.abs(straight_letters[:, 1]))) + 1e-6
    assert float(radius.min()) >= 40.0 - half - 0.01
    assert float(radius.max()) <= 40.0 + half + 0.01
    # Gebogen und nicht nur verschoben: Die Enden der Zeile sinken zum Mittelpunkt.
    ends = letters[np.abs(letters[:, 0]) > 10.0]
    assert float(np.max(ends[:, 1])) < float(np.max(letters[:, 1])) - 1.0
    # Die Fläche der Buchstaben bleibt im Mittel erhalten (Ober- und Unterkante gleichen sich aus).
    grown = mesh.volume - plate.mesh.volume
    flat = straight.outputs[0].mesh.volume - plate.mesh.volume
    assert grown == pytest.approx(flat, rel=0.03)


def test_a_negative_arc_bends_the_line_the_other_way(profile: Profile) -> None:
    plate = _plate()
    arced = _run(
        "label_text", plate, profile, text="SOLIDON", size=8.0, depth=0.6, z=5.0, arc_radius=-40.0
    )
    letters = _added(plate.mesh, arced.outputs[0].mesh)
    radius = np.hypot(letters[:, 0], letters[:, 1] - 40.0)
    assert float(radius.max()) <= 40.0 + 4.5
    ends = letters[np.abs(letters[:, 0]) > 10.0]
    assert float(np.min(ends[:, 1])) > float(np.min(letters[:, 1])) + 1.0, "Enden steigen"


def test_an_arc_smaller_than_the_text_is_refused(profile: Profile) -> None:
    with pytest.raises(ValidationError) as problem:
        _run("label_text", _plate(), profile, text="SOLIDON", size=8.0, z=5.0, arc_radius=3.0)
    assert problem.value.constraint == "bend"
    with pytest.raises(ValidationError) as problem:
        _run(
            "label_text", _plate(), profile, text="SOLIDON SOLIDON", size=8.0, z=5.0, arc_radius=9.0
        )
    assert problem.value.constraint == "bend"


# --- Um eine Rundung ------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_text_around_a_drum_hugs_its_mantle(mode: str, profile: Profile) -> None:
    """Becher Ø 40: erhaben zwischen R 20 und R 20,6, vertieft zwischen R 19,4 und R 20."""
    drum = _drum()
    result = _run(
        "label_text",
        drum,
        profile,
        text="SALZ",
        size=10.0,
        depth=0.6,
        mode=mode,
        wrap="around",
        x=20.0,
        y=0.0,
        z=20.0,
        nx=1.0,
        ny=0.0,
        nz=0.0,
    )
    assert result.answered == {"wrap_radius": pytest.approx(20.0)}, "gemessen und festgehalten"
    mesh = result.outputs[0].mesh
    assert mesh.is_watertight
    letters = _added(drum.mesh, mesh)
    radius = np.hypot(letters[:, 0], letters[:, 1])
    # Die Schrift liegt nicht als gerade Platte auf: Sie folgt dem Mantel.
    assert float(np.max(np.abs(letters[:, 1]))) > 5.0
    if mode == "raised":
        assert float(radius.max()) <= 20.6 + 0.06
        assert mesh.volume > drum.mesh.volume
    else:
        assert float(radius.min()) >= 19.4 - 0.06
        assert mesh.volume < drum.mesh.volume


def test_text_inside_a_ring_bends_towards_its_axis(profile: Profile) -> None:
    """Hohle Rundung: Die Achse liegt vor der Fläche, der Radius ist negativ."""
    ring = _ring()
    result = _run(
        "label_text",
        ring,
        profile,
        text="INNEN",
        size=6.0,
        depth=0.6,
        wrap="around",
        x=30.0,
        y=0.0,
        z=15.0,
        nx=-1.0,
        ny=0.0,
        nz=0.0,
    )
    assert result.answered == {"wrap_radius": pytest.approx(-30.0)}
    letters = _added(ring.mesh, result.outputs[0].mesh)
    radius = np.hypot(letters[:, 0], letters[:, 1])
    assert float(radius.min()) >= 29.4 - 0.06 and float(radius.max()) <= 30.0 + 1e-6


def test_without_a_round_surface_the_radius_is_asked_for(profile: Profile) -> None:
    drum = _drum(with_feature=False)
    with pytest.raises(ValidationError) as problem:
        _run(
            "label_text",
            drum,
            profile,
            text="SALZ",
            size=10.0,
            wrap="around",
            x=20.0,
            z=20.0,
            nx=1.0,
            nz=0.0,
        )
    assert problem.value.field == "wrap_radius"
    stated = _run(
        "label_text",
        drum,
        profile,
        text="SALZ",
        size=10.0,
        wrap="around",
        wrap_radius=20.0,
        x=20.0,
        z=20.0,
        nx=1.0,
        nz=0.0,
    )
    assert not stated.answered and stated.outputs[0].mesh.volume > drum.mesh.volume


# --- Bündige Einlage ------------------------------------------------------------------------


def test_a_flush_inlay_fills_its_pocket_exactly(profile: Profile) -> None:
    """Screen-Cover aus dem Audit: 0,6 mm Einlage, bündig, ohne Spalt und ohne Überlagerung."""
    plate = _plate()
    result = _run("inlay_text", plate, profile, text="RS", size=12.0, depth=0.6, slot=1, z=5.0)
    carrier, inlay = result.outputs
    assert carrier.id == "obj_1", "der Träger bleibt derselbe Körper"
    assert carrier.mesh.is_watertight and inlay.mesh.is_watertight
    assert carrier.mesh.volume + inlay.mesh.volume == pytest.approx(plate.mesh.volume, rel=1e-9)
    assert shared_volume(carrier.mesh.raw, inlay.mesh.raw) == pytest.approx(0.0, abs=1e-6)
    assert float(inlay.mesh.bounds.maximum[2]) == pytest.approx(5.0, abs=1e-9), "bündig"
    assert float(inlay.mesh.bounds.minimum[2]) == pytest.approx(4.4, abs=1e-9), "0,6 tief"
    assert set(np.unique(as_mesh_data(inlay.mesh).slots)) == {1}
    assert [slot.index for slot in inlay.material_slots] == [0, 1]


def test_an_inlay_around_a_drum_is_flush_with_the_mantle(profile: Profile) -> None:
    drum = _drum()
    result = _run(
        "inlay_text",
        drum,
        profile,
        text="SALZ",
        size=10.0,
        depth=0.8,
        wrap="around",
        x=20.0,
        z=20.0,
        nx=1.0,
        nz=0.0,
    )
    carrier, inlay = result.outputs
    assert carrier.mesh.volume + inlay.mesh.volume == pytest.approx(drum.mesh.volume, rel=1e-9)
    corners = np.asarray(inlay.mesh.raw.vertices)
    radius = np.hypot(corners[:, 0], corners[:, 1])
    assert float(radius.max()) <= 20.0 + 1e-6, "nicht über den Mantel hinaus"
    assert float(radius.min()) >= 19.2 - 0.06


def test_an_inlay_that_misses_the_body_is_refused(profile: Profile) -> None:
    with pytest.raises(ValidationError) as problem:
        _run("inlay_text", _plate(), profile, text="RS", size=12.0, x=300.0, z=5.0)
    assert problem.value.constraint == "empty"


# --- Am exakten Körper ---------------------------------------------------------------------


def test_arc_wrap_and_inlay_keep_an_exact_body_exact(profile: Profile) -> None:
    edit = exact_kernel()
    plate = SceneObject(
        id="obj_1", name="Platte", mesh=edit.box(80.0, 60.0, 5.0), kind="brep", features={}
    )
    arced = _run(
        "label_text", plate, profile, text="SOLIDON", size=8.0, depth=0.6, z=5.0, arc_radius=40.0
    )
    assert arced.outputs[0].kind == "brep"
    mesh_twin = _run(
        "label_text", _plate(), profile, text="SOLIDON", size=8.0, depth=0.6, z=5.0, arc_radius=40.0
    )
    added_exact = arced.outputs[0].mesh.volume - plate.mesh.volume
    added_mesh = mesh_twin.outputs[0].mesh.volume - _plate().mesh.volume
    assert added_exact == pytest.approx(added_mesh, rel=0.02)

    drum = SceneObject(
        id="obj_1",
        name="Dose",
        mesh=edit.cylinder(40.0, 40.0),
        kind="brep",
        features=_drum().features,
    )
    wrapped = _run(
        "label_text",
        drum,
        profile,
        text="SALZ",
        size=10.0,
        depth=0.6,
        wrap="around",
        x=20.0,
        z=20.0,
        nx=1.0,
        nz=0.0,
    )
    assert wrapped.outputs[0].kind == "brep"
    assert wrapped.outputs[0].mesh.volume > drum.mesh.volume
    assert any(finding.code == "label.faceted" for finding in wrapped.findings)

    inlaid = _run("inlay_text", plate, profile, text="RS", size=12.0, depth=0.6, z=5.0)
    carrier, inlay = inlaid.outputs
    assert carrier.kind == "brep" and inlay.kind == "brep"
    assert carrier.mesh.volume + inlay.mesh.volume == pytest.approx(plate.mesh.volume, rel=1e-6)
    assert math.isclose(float(inlay.mesh.bounds.maximum[2]), 5.0, abs_tol=1e-6)
