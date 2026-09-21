"""Der exakte Gewindebolzen erklärt seinen Gang über den vorhandenen Merkmalsvertrag."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.brep.kernel import Solid, available
from app.core.geom.ops import as_transform
from app.core.geom.transform import translation
from app.core.perceive.matching import moved_features
from app.core.types import SceneObject
from app.core.units import EPS_GEOM
from tests.test_sketch_ops import run

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")

DIAMETER = 6.123456789
PITCH = 1.23456789
# **Nicht 4,3456789**: Mit 3,52 Umläufen verlor die Vereinigung den Gang still, und
# die Fixture war zwei Wochen lang ein glatter Bolzen — die Zusicherung
# ``core < volume`` hielt um ein Rundungsrauschen (B3, P2.5). 4,0 mm trägt ihn.
# Seit RM-195 entsteht der Bolzen genäht, ohne Vereinigung; die Länge bleibt.
LENGTH = 4.0


@pytest.fixture(scope="module")
def exact_thread() -> SceneObject:
    """Ein echter kurzer OCCT-Gang wird für die Anschlussprüfungen einmal gebaut."""
    load_operations()
    return run("thread_exact", diameter=DIAMETER, pitch=PITCH, length=LENGTH).outputs[0]


def test_the_exact_thread_declares_its_unchanged_dimensions(exact_thread: SceneObject) -> None:
    """Die echte Geometrie und ihre benannten Maße gehören zu demselben Aufruf."""
    thread = exact_thread.features.get("thread_1")
    assert thread is not None
    assert thread.kind == "thread"
    assert thread.provenance == "generated"
    assert thread.params["diameter"] == pytest.approx(DIAMETER, abs=1e-12, rel=0.0)
    assert thread.params["pitch"] == pytest.approx(PITCH, abs=1e-12, rel=0.0)
    assert thread.params["length"] == pytest.approx(LENGTH, abs=1e-12, rel=0.0)
    assert thread.params["centre"] == pytest.approx((0.0, 0.0, LENGTH / 2.0), abs=1e-12, rel=0.0)
    assert thread.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=EPS_GEOM, rel=0.0)
    assert thread.params["internal"] is False
    assert thread.params["handedness"] == "right"
    assert exact_thread.kind == "brep"
    assert isinstance(exact_thread.mesh, Solid)
    assert exact_thread.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=EPS_GEOM, rel=0.0)
    # Der Gang wird mit Überstand gebaut und an der Länge beschnitten; die
    # Fuzzy-Vereinigung lässt am oberen Ende wenige Mikrometer stehen. Die
    # Genauigkeit auf EPS_GEOM galt einem Bolzen ohne Gang (B3, P2.5).
    assert exact_thread.mesh.bounds.maximum[2] == pytest.approx(LENGTH, abs=1e-5, rel=0.0)
    # Die vorhandene ISO-Profilhöhe ist 0,6134 P; ein wirklicher Außengang
    # liegt zwischen dem Kernzylinder und dem Zylinder über seinen Spitzen.
    core = math.pi * (DIAMETER / 2.0 - 0.6134 * PITCH) ** 2 * LENGTH
    hull = math.pi * (DIAMETER / 2.0) ** 2 * LENGTH
    assert core < exact_thread.mesh.volume < hull


def test_the_thread_surface_excludes_the_planar_end_caps(exact_thread: SceneObject) -> None:
    """Auswahl färbt den Gewindemantel; seine beiden planaren Enden bleiben eigene Flächen."""
    thread = exact_thread.features.get("thread_1")
    assert thread is not None
    assert thread.face_indices
    triangles = np.asarray(exact_thread.mesh.raw.triangles)
    ends = np.flatnonzero(
        np.all(np.abs(triangles[:, :, 2]) < 1e-10, axis=1)
        | np.all(np.abs(triangles[:, :, 2] - LENGTH) < 1e-10, axis=1)
    )
    assert len(ends)
    selected = set(thread.face_indices)
    assert selected.isdisjoint(ends)
    assert selected == set(range(len(triangles))) - set(ends)
    faces = [feature for feature in exact_thread.features.values() if feature.kind == "face"]
    assert len(faces) >= 2
    assert set(ends) <= {index for feature in faces for index in feature.face_indices}


def test_the_named_exact_thread_uses_the_existing_transform_contract(
    exact_thread: SceneObject,
) -> None:
    """Eine normale Merkmalsmitnahme erhält ID und Maße und versetzt den Mittelpunkt."""
    moved = moved_features(exact_thread.features, as_transform(translation((7.0, -3.0, 2.0))))
    thread = moved.get("thread_1")
    assert thread is not None
    assert thread.id == "thread_1"
    assert thread.provenance == "generated"
    assert thread.params["centre"] == pytest.approx(
        (7.0, -3.0, LENGTH / 2.0 + 2.0), abs=1e-12, rel=0.0
    )
    assert thread.params["diameter"] == pytest.approx(DIAMETER, abs=1e-12, rel=0.0)
    assert thread.params["pitch"] == pytest.approx(PITCH, abs=1e-12, rel=0.0)
    assert thread.params["length"] == pytest.approx(LENGTH, abs=1e-12, rel=0.0)
    assert thread.face_indices == exact_thread.features["thread_1"].face_indices


def test_a_rod_that_would_lose_its_ridge_says_so_instead_of_coming_out_smooth() -> None:
    """M6 x 1 mit Länge 2,5: bis zum 20.09.2026 ein glatter Bolzen ohne Meldung (B3, P2.5).

    Die Vereinigung von Kern und Gang lieferte an neun von 23 Rasterlängen den
    nackten Kern zurück — gültig, geschlossen, ein Stück. Jetzt gilt ein
    Bolzen erst als gelungen, wenn sein Volumen über dem Kern liegt; sonst
    steht am Ende die Absage mit Vorschlägen, nie ein Bolzen ohne Gang.
    """
    from app.core.brep import profiles
    from app.core.errors import GeometryError

    core = math.pi * (3.0 - 0.6134) ** 2 * 2.5
    try:
        rod = profiles.threaded_rod(6.0, 1.0, 2.5)
    except GeometryError as refusal:
        assert refusal.suggestions, "Regel 17: eine Absage nennt, was jetzt möglich ist"
        return
    assert rod.volume > core * 1.01, "ein Bolzen ohne Gang ist kein Bolzen"
