"""Filament an Wulst, Kehle und Gewinde — färben und abwählen, in beiden Kernen (P2.6).

*Filament auf eine Fläche* und *Filament entfernen* nehmen seit P2.6 auch ein
Torusmerkmal und ein Gewinde an. Der Ring und ein erkanntes Gewinde nennen
ihre Dreiecke selbst; ein erzeugtes Gewinde nennt keine, und dann sind seine
Flächen alle Dreiecke in seiner Hülle ohne die Deckel quer zur Achse
(``paint.feature_triangles``) — die Spitze bleibt, der Sockel bleibt.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.geom.attributes import counts
from app.core.geom.mesh import as_mesh_data
from app.core.geom.paint import feature_triangles
from app.core.types import Profile
from tests.helpers import (
    SHAFT_HEIGHT,
    SHAFT_RADIUS,
    TUBE_RADIUS,
    exact_kernel,
    ridged_shaft,
    the_torus,
)
from tests.helpers import run_operation as run
from tests.test_thread_feature_ops import _studded_plate, _tapped_plate


@pytest.fixture(params=["brep", "mesh"])
def kind(request: Any) -> str:
    """Beide Kerne — und beide brauchen OpenCASCADE: Schaft, Platte und Gewinde
    entstehen exakt, das Netz ist ihre Tessellation (``tests.helpers.ridged_shaft``,
    ``test_thread_feature_ops._studded_plate``)."""
    exact_kernel()
    load_operations()
    return str(request.param)


@pytest.mark.parametrize("recess", [False, True])
def test_a_ring_takes_a_filament_and_gives_it_back(
    kind: str, recess: bool, profile: Profile
) -> None:
    """Wulst wie Kehle nehmen ein Filament genau auf ihren Dreiecken an, und ``clear_filament``
    nimmt es vollständig zurück — in beiden Kernen.
    """
    source = ridged_shaft(kind, recess=recess)
    ring = the_torus(source)
    painted = run("paint_slot", source, profile, at_feature=ring.id, slot=2, colour="#ff0000")
    output = painted.outputs[0]
    assert output.kind == kind
    mesh = as_mesh_data(output.mesh)
    tally = counts(mesh)
    assert tally.get(2, 0) == len(set(ring.face_indices))
    assert tally.get(2, 0) > 0
    # Und die Ringflächen sind genau die gefärbten.
    coloured = {index for index, slot in enumerate(mesh.slots) if slot == 2}
    assert coloured == set(ring.face_indices)
    cleared = run("clear_filament", output, profile, at_feature=ring.id)
    assert counts(as_mesh_data(cleared.outputs[0].mesh)).get(2, 0) == 0
    assert cleared.outputs[0].kind == kind


def test_a_generated_thread_colours_its_flanks_but_not_its_seat(
    kind: str, profile: Profile
) -> None:
    """Ein erzeugtes Gewinde nennt keine Dreiecke; gefärbt werden alle in seiner Hülle über der
    Platte, nicht die Deckflächen quer zur Achse — Spitze und Sockel bleiben.
    """
    source = _studded_plate(kind)
    feature = source.features["thread_1"]
    assert not feature.face_indices, "ein Bausteingewinde nennt keine Dreiecke"
    mesh = as_mesh_data(source.mesh)
    chosen = feature_triangles(mesh, feature)
    assert chosen
    centres = np.asarray(mesh.raw.triangles_center)[list(chosen)]
    normals = np.asarray(mesh.raw.face_normals)[list(chosen)]
    # Alles in der Hülle des Gewindes über der Platte, nichts quer zur Achse.
    assert np.all(centres[:, 2] > 10.0 - 0.02)
    assert np.all(np.hypot(centres[:, 0], centres[:, 1]) <= 3.0 + 1e-6)
    assert np.all(np.abs(normals[:, 2]) < 1.0 - 1e-9)
    painted = run("paint_slot", source, profile, at_feature="thread_1", slot=3, colour="#00ff00")
    output = painted.outputs[0]
    assert output.kind == kind
    tally = counts(as_mesh_data(output.mesh))
    assert tally.get(3, 0) == len(chosen)
    # Die Platte selbst bleibt ungefärbt: ihre Deckfläche liegt quer zur Achse.
    top = [
        index
        for index, normal in enumerate(np.asarray(mesh.raw.face_normals))
        if normal[2] > 0.999 and abs(mesh.raw.triangles_center[index][2] - 10.0) < 1e-6
    ]
    assert top and all(as_mesh_data(output.mesh).slots[index] == 0 for index in top)


def test_a_tapped_hole_colours_its_thread_but_not_the_plate_faces(
    kind: str, profile: Profile
) -> None:
    """Ein Gewindeloch färbt seine Gangflächen in der Bohrung, nicht die Stirnflächen der Platte
    darum.
    """
    source = _tapped_plate(kind)
    painted = run("paint_slot", source, profile, at_feature="thread_1", slot=4, colour="#0000ff")
    output = painted.outputs[0]
    mesh = as_mesh_data(output.mesh)
    tally = counts(mesh)
    assert tally.get(4, 0) > 0
    centres = np.asarray(mesh.raw.triangles_center)
    for index, slot in enumerate(mesh.slots):
        if slot == 4:
            assert np.hypot(centres[index][0], centres[index][1]) <= 4.0
        elif abs(mesh.raw.face_normals[index][2]) > 0.999:
            assert slot == 0


def test_the_exact_ring_keeps_its_filament_through_retessellation(profile: Profile) -> None:
    """Das Filament hängt am exakten Ring, nicht an seinen Dreiecken: Eine feinere Vernetzung färbt
    wieder genau die Ringfläche.
    """
    exact_kernel()
    load_operations()
    source = ridged_shaft("brep", recess=False)
    ring = the_torus(source)
    painted = run("paint_slot", source, profile, at_feature=ring.id, slot=2, colour="#ff0000")
    solid: Any = painted.outputs[0].mesh
    coarse = as_mesh_data(solid)
    fine = as_mesh_data(dataclasses.replace(solid, deflection=0.005))
    assert fine.triangle_count > coarse.triangle_count
    for mesh in (coarse, fine):
        assert counts(mesh).get(2, 0) > 0
        # Genau die Dreiecke auf dem Ring tragen das Filament: ihre Mitten liegen
        # um den Rohrradius von der Ringlinie entfernt, alle anderen nicht.
        centres = np.asarray(mesh.raw.triangles_center)
        radial = np.hypot(centres[:, 0], centres[:, 1])
        on_ring = np.hypot(radial - SHAFT_RADIUS, centres[:, 2] - SHAFT_HEIGHT / 2.0)
        coloured = np.asarray(mesh.slots) == 2
        assert np.all(on_ring[coloured] < TUBE_RADIUS + 0.05)
        assert np.all(on_ring[~coloured] > TUBE_RADIUS - 0.05)
