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
from tests.helpers import CountingToken
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
    # Der Gang wird mit Überstand gebaut und an der Länge beschnitten. Bis
    # RM-195 ließ die Fuzzy-Vereinigung von Kern und Gang oben wenige
    # Mikrometer stehen, und hier stand 1e-5; der genähte Bolzen endet so
    # genau wie er beginnt (gemessen 22.09.2026: 1e-7, die Hüllzugabe).
    assert exact_thread.mesh.bounds.maximum[2] == pytest.approx(LENGTH, abs=EPS_GEOM, rel=0.0)
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


@pytest.mark.parametrize(
    ("diameter", "pitch", "length"),
    [(6.0, 1.0, 2.5), (6.0, 1.0, 2.25), (6.0, 1.0, 3.52), (6.123456789, 1.23456789, 4.3456789)],
    ids=["m6_2.5", "m6_2.25", "m6_3.52", "odd_4.35"],
)
def test_a_rod_keeps_its_ridge_at_every_length(
    diameter: float, pitch: float, length: float
) -> None:
    """Der Bolzen trägt seinen Gang an jeder Länge — Pappus auf 10⁻⁸.

    Bis zum 20.09.2026 lieferte die Vereinigung von Kern und Gang an neun von
    23 Rasterlängen den nackten Kern zurück — gültig, geschlossen, ein Stück
    (B3, P2.5); M6 x 1 mit 2,5 mm und 3,52 Umläufe waren solche Längen. Dieser
    Test nahm damals auch eine Absage hin, und er hätte einen Bolzen, der
    wieder absagt, grün gelassen. Seit RM-195 entsteht der Bolzen genäht und
    wird nur noch auf Länge geschnitten; er trifft die Analytik an allen vier
    Längen auf 2 · 10⁻¹⁰ (gemessen 22.09.2026). Der Sollwert kommt aus dem
    Profil (``thread_ridge``) über die Schuhbandformel, nicht aus der
    Prüfung im Bolzen.
    """
    from itertools import pairwise

    from app.core.brep import profiles

    ridge = profiles.thread_ridge(diameter, pitch)
    root = ridge[0][0]
    corners = [*ridge, ridge[0]]
    moment = 0.0
    for (r_a, z_a), (r_b, z_b) in pairwise(corners):
        moment += (r_a + r_b) * (r_a * z_b - r_b * z_a)
    expected = math.pi * root**2 * length + 2.0 * math.pi * abs(moment) / 6.0 * (length / pitch)
    rod = profiles.threaded_rod(diameter, pitch, length)
    assert rod.is_closed and rod.solid_count == 1
    assert rod.volume == pytest.approx(expected, rel=1e-8)
    assert rod.volume > math.pi * root**2 * length * 1.1, "ein Bolzen ohne Gang ist kein Bolzen"


def test_the_rod_asks_for_cancellation_while_it_is_built() -> None:
    """Der Bolzen fragt je Helix und um jeden nativen Schritt nach dem Abbruch.

    Bis zum 22.09.2026 nahm ``threaded_rod`` keinen Token an: Ein M3 x 0,5 x 60
    baut 367 Helices und 366 Regelflächen, näht und schneidet sie — gut
    zehn Sekunden, in denen *Abbrechen* nichts tat, bis die Einpassung der
    Platzierung danach zum ersten Mal fragte.
    """
    from app.core.brep import profiles
    from app.core.errors import OperationCancelled

    counting = CountingToken(limit=None)
    rod = profiles.threaded_rod(6.0, 1.0, 12.0, cancelled=counting)
    turns = math.ceil(12.0 / 1.0) + 2
    assert counting.calls > 3 * turns, counting.calls
    assert rod.is_closed and rod.solid_count == 1
    early = CountingToken(limit=10)
    with pytest.raises(OperationCancelled):
        profiles.threaded_rod(6.0, 1.0, 12.0, cancelled=early)
    assert early.calls == 10


def test_the_exact_thread_does_not_describe_the_faces_it_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Flächen eines bekannten Gewindes werden nicht erst als Träger gelesen (RM-196).

    ``thread_exact`` kennt sein Gewinde (``features_of(known_threads=…)``); was
    auf dessen Flächen als Zapfen, Kegel oder Rundung entstünde, verdrängt es
    ohnehin. Bis zum 22.09.2026 lief die Trägerprüfung trotzdem über jede
    Regelfläche — am M3 x 0,5 x 60 363 Flächen und 0,6 s, dazu eine
    Klassierung am ganzen Bolzen. Gefragt werden jetzt nur die zwei
    Stirnflächen, und die Merkmale sind dieselben.
    """
    load_operations()
    asked: list[int] = []
    original = Solid.surface

    def counting(self: Solid, index: int, **kwargs: object) -> object:
        asked.append(index)
        return original(self, index, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Solid, "surface", counting)
    entry = run("thread_exact", diameter=6.0, pitch=1.0, length=12.0).outputs[0]
    assert sorted(entry.features) == ["face_1", "face_2", "thread_1"]
    solid = entry.mesh
    assert isinstance(solid, Solid)
    ends = set(asked)
    assert len(ends) == 2, sorted(ends)
    assert solid.face_count > 30, "ein Gewinde mit vielen Flächen, sonst prüft das nichts"
