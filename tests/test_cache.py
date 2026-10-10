"""Ergebniscache über den Op-Hash (Bauplan §15, §38)."""

from __future__ import annotations

import ast
import dataclasses
import json
import logging
import os
import shutil
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.scene.cache import CACHE_FORMAT_VERSION, CachedResult, DiskCache, ResultCache
from app.core.scene.hashing import digest, object_hash, operation_hash, profile_key
from app.core.types import Mesh, Operation, Profile, SceneObject
from app.i18n import TranslatableText
from tests.helpers import FakeCodec, FakeMesh, make_object


@pytest.mark.parametrize("op,source", [("create_box", "facets"), ("create_brep_box", "native")])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_real_measure_sources_survive_project_reopen_cache_and_undo(
    profile: Profile, tmp_path: Path, op: str, source: str, quality: str
) -> None:
    """Beide Quaderwege führen dieselben Flächenmaße durch echte gespeicherte Schritte."""
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, load, new_project, save
    from app.core.types import measure_status

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader", [OperationDraft(op=op, params={"width": 30.0, "depth": 20.0, "height": 8.0})]
    )
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))

    def measured(current, active_cache, area):
        result = evaluate(
            current.document,
            profile,
            quality=quality,
            sources=ProjectSources(current),
            cache=active_cache,
        )
        assert result.complete
        body = result.scene.objects["obj_1"]
        top = next(
            feature
            for feature in body.features.values()
            if feature.kind == "face" and feature.params["normal"][2] > 0.99
        )
        assert top.params["area"] == pytest.approx(area)
        assert measure_status(top, "area").source == source
        assert top.surface_patches
        for patch in top.surface_patches:
            assert patch.kind == "plane"
            assert patch.source == source
            assert set(patch.face_indices) <= set(top.face_indices)
            assert patch.params["centre"][2] == pytest.approx(top.params["centre"][2])
        # Ein Quader trägt keine Rundform und damit keinen belegten Punkt, der
        # neben seiner Form liegen könnte: kein Befund (21.09.2026; bis dahin
        # stand an jedem Körper mit belegten Flächen ein Hinweis auf die Karte).
        # Die Karte selbst baut trotzdem — aus denselben Trägern, die durch
        # den Cache gereist sind.
        assert not [
            finding
            for finding in result.scene.report.findings
            if finding.code == "perceive.deviation"
        ]
        from app.core.perceive.maps import build

        deviation = build("deviation", body)
        assert deviation.unknown_count == 0
        assert len(deviation.values) == body.mesh.triangle_count
        assert deviation.maximum_interval[0] <= 0.0 <= deviation.maximum_interval[1]
        assert deviation.maximum_interval[1] <= 1e-8
        return top

    original = measured(project, cache, 600.0)
    assert measured(project, cache, 600.0) == original
    history.apply(
        "Skalieren", [OperationDraft(op="scale_object", inputs=("obj_1",), params={"factor": 2.0})]
    )
    changed = measured(project, cache, 2400.0)
    path = save(project, tmp_path / "quader.p3d")
    reopened = load(path)
    cold = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    restored = measured(reopened, cold, 2400.0)
    assert dataclasses.replace(restored, params=changed.params) == changed
    assert restored.params.keys() == changed.params.keys()
    for name, value in changed.params.items():
        assert restored.params[name] == pytest.approx(value)
    if op == "create_box":
        assert cold.statistics.disk_hits > 0
    history.undo()
    assert measured(project, cache, 600.0) == original
    history.redo()
    assert measured(project, cache, 2400.0) == changed
    assert original.params["area"] == pytest.approx(600.0)


def result(triangles: int = 100, object_id: str = "obj_1") -> CachedResult:
    return CachedResult(objects=(make_object(object_id, triangles=triangles),))


def test_a_recognised_flag_survives_the_cache() -> None:
    """Szene 3: ohne ``recognised`` im Cache verwaisen benannte Baustein-Bohrungen.

    Ein Baustein benennt seine Bohrungen beim Bauen und setzt ``recognised=False``,
    weil ``detect`` sie an ihrer Stelle nicht findet. Fiel das Feld beim
    Cache-Treffer auf die Vorgabe ``True`` zurück, wanderte das Merkmal in die
    Erkennungsprüfung, fand keinen Partner und verwaiste — der Fehler, gegen den
    das Feld eingebaut wurde, nur eine Cache-Ebene weiter.
    """
    from app.core.scene.cache import _feature_from_data, feature_to_data
    from app.core.types import Feature

    named = Feature(
        id="heatset_m4_bore_1",
        kind="hole",
        provenance="generated",
        params={"diameter": 4.0},
        face_indices=(),
        recognised=False,
        created_by=3,
    )

    revived = _feature_from_data(feature_to_data(named))
    assert revived.recognised is False, "recognised überlebt den Cache"

    # Rückwärtsverträglich wie ``created_by``: ein Eintrag ohne das Feld gilt als
    # erkannt.
    old_entry = {
        "id": "x",
        "kind": "hole",
        "provenance": "detected",
        "params": {},
        "face_indices": [],
    }
    assert _feature_from_data(old_entry).recognised is True


def surface_result() -> CachedResult:
    """Ein zusammengesetztes Merkmal behält fünf verschiedene Originalteilflächen."""
    from app.core.types import Feature, SurfacePatch

    centre = (1.25, -3.0, 7.5)
    axis = (0.0, 0.0, 2.0)
    patches = (
        SurfacePatch("plane", {"centre": centre, "axis": axis}, (1,), "facets"),
        SurfacePatch("cylinder", {"centre": centre, "axis": axis, "radius": 2.0}, (2,), "fit"),
        SurfacePatch("cone", {"apex": centre, "axis": axis, "half_angle": 0.4}, (3,), "native"),
        SurfacePatch("sphere", {"centre": centre, "radius": 4.0}, (4,), "fit"),
        SurfacePatch(
            "torus",
            {"centre": centre, "axis": axis, "ring_radius": 8.0, "tube_radius": 2.0},
            (5,),
            "native",
        ),
    )
    feature = Feature("compound", "face", "detected", {}, (1, 2, 3, 4, 5), surface_patches=patches)
    body = dataclasses.replace(make_object("obj_1", triangles=10), features={feature.id: feature})
    return CachedResult(objects=(body,))


def test_original_surface_carriers_survive_both_cache_levels(tmp_path: Path) -> None:
    """JSON darf die Vektoren und ihre Zuordnung nicht in veränderbare Listen verwandeln."""
    original = surface_result()
    cache = ResultCache(disk=DiskCache(codec=FakeCodec(), directory=tmp_path))
    cache.put("carriers", original, to_disk=True)
    cache.clear()
    fresh = cache.get("carriers")
    assert fresh is not None
    assert fresh.objects[0].features == original.objects[0].features
    assert cache.statistics.disk_hits == 1
    assert cache.get("carriers") is fresh


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "spline"),
        ("kind", []),
        ("source", "parameter"),
        ("source", {}),
        ("params", []),
        ("params", {"centre": [0.0, 0.0, 0.0]}),
        ("params", {"centre": [0.0, 0.0, 0.0], "axis": [0.0, 0.0, 0.0]}),
        ("params", {"centre": [0.0, 0.0, 0.0], "axis": [True, 0.0, 1.0]}),
        ("params", {"centre": [float("nan"), 0.0, 0.0], "axis": [0.0, 0.0, 1.0]}),
        ("params", {"centre": [0.0, 0.0, 0.0], "axis": [0.0, float("inf"), 1.0]}),
        ("face_indices", []),
        ("face_indices", None),
        ("face_indices", [-1]),
        ("face_indices", [True]),
        ("face_indices", [1.5]),
        ("face_indices", [[1]]),
        ("face_indices", [1, 1]),
        ("face_indices", [0]),
    ],
)
def test_invalid_surface_carrier_drops_the_disk_result(
    tmp_path: Path, field: str, value: object
) -> None:
    """Beschädigte Träger liefern weder erfundene Nullabweichungen noch einen Absturz.

    Eine Dreiecksnummer jenseits des gespeicherten Netzes steht nicht mehr in
    dieser Liste: Der Cache trägt die **rohe** Ausgabe einer Operation, und die
    darf Merkmale ihres Eingangs mit dessen Nummern durchreichen (siehe
    ``test_a_result_that_carries_its_input_features_comes_back_from_the_disk``).
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("carriers", surface_result())
    index = disk._folder("carriers") / "objects.json"
    data = json.loads(index.read_text(encoding="utf-8"))
    data["objects"][0]["features"]["compound"]["surface_patches"][0][field] = value
    index.write_text(json.dumps(data), encoding="utf-8")
    assert disk.get("carriers") is None
    assert not index.exists()


def test_a_result_that_carries_its_input_features_comes_back_from_the_disk(
    tmp_path: Path,
) -> None:
    """Der Bausteinwirt gibt nach der Vereinigung die Merkmale seines Eingangs zurück —
    mit Dreiecksnummern des Eingangsnetzes, die über das neue Netz hinausreichen.
    Bis zum 21.09.2026 verwarf der Plattencodec jeden solchen Eintrag als beschädigt,
    und „Dose mit Deckel" rechnete die Kabeldurchführung bei jedem Öffnen neu."""
    from app.core.types import Feature, SurfacePatch

    carried = Feature(
        "hole_1",
        "hole",
        "detected",
        {"diameter": 4.0, "centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0)},
        (40_284, 40_285),
        surface_patches=(
            SurfacePatch(
                "cylinder",
                {"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "radius": 2.0},
                (40_284, 40_285),
                "fit",
            ),
        ),
    )
    host = dataclasses.replace(make_object("obj_1", triangles=10), features={"hole_1": carried})
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("host", CachedResult(objects=(host,)))
    fresh = disk.get("host")
    assert fresh is not None, "the raw output must come back as it was written"
    restored = fresh.objects[0].features["hole_1"]
    assert restored.face_indices == carried.face_indices
    assert restored.surface_patches == carried.surface_patches
    assert restored.params["diameter"] == carried.params["diameter"]


def test_surface_indices_share_the_existing_memory_budget() -> None:
    """Originalhaut und zusätzliche Zuordnungen müssen gemeinsam alte Einträge verdrängen."""
    original = surface_result()
    assert original.cost == 20  # Zehn Dreiecke, fünf Merkmals- und fünf Trägerindizes.
    cache = ResultCache(triangle_budget=30)
    cache.put("first", original)
    cache.put("second", original)
    assert cache.get("first") is None
    assert cache.get("second") is original
    assert cache.cost == 20
    assert cache.statistics.evictions == 1


def test_a_hit_returns_what_was_stored() -> None:
    cache = ResultCache()
    cache.put("key", result())
    assert cache.get("key") is not None
    assert cache.get("missing") is None
    assert cache.statistics.hits == 1
    assert cache.statistics.misses == 1


def test_the_budget_is_counted_in_triangles() -> None:
    cache = ResultCache(triangle_budget=250)
    cache.put("a", result(100, "obj_1"))
    cache.put("b", result(100, "obj_2"))
    assert cache.cost == 200
    assert len(cache) == 2

    cache.put("c", result(100, "obj_3"))
    assert len(cache) == 2, "the least recently used entry gives way"
    assert cache.get("a") is None
    assert cache.statistics.evictions == 1


def test_reading_an_entry_keeps_it_alive() -> None:
    cache = ResultCache(triangle_budget=250)
    cache.put("a", result(100, "obj_1"))
    cache.put("b", result(100, "obj_2"))
    cache.get("a")
    cache.put("c", result(100, "obj_3"))
    assert cache.get("a") is not None
    assert cache.get("b") is None


# --- Die Bytegrenze der Speicherebene (RM-567) ---------------------------------


def sphere_result(object_id: str, subdivisions: int = 4) -> CachedResult:
    """Ein echtes Netz, damit gezählt wird, was trimesh an ihm merkt."""
    import trimesh

    from app.core.geom.mesh import MeshData

    body = trimesh.creation.icosphere(subdivisions=subdivisions, radius=10.0)
    return CachedResult(objects=(SceneObject(id=object_id, name="Kugel", mesh=MeshData.of(body)),))


def _grown(result: CachedResult) -> Any:
    """Das rohe Netz eines Eintrags, nachdem Nachbarschaften an ihm gerechnet wurden."""
    raw = cast(Any, result.objects[0].mesh).raw
    _ = raw.face_adjacency, raw.edges_unique, raw.triangles_center, raw.edges_sorted
    return raw


def test_the_memory_level_counts_what_its_meshes_hold() -> None:
    """Zwei Netze über der Bytegrenze: das ältere geht, auch weit unter der Dreiecksgrenze."""
    from app.core.scene.cache import held_by

    first, second = sphere_result("obj_1"), sphere_result("obj_2")
    one = held_by(first)
    assert one > 5_120 * 36, "an icosphere of 5 120 triangles holds at least its arrays"
    cache = ResultCache(memory_budget=int(one * 1.5))
    cache.put("a", first)
    cache.put("b", second)
    cache.trim()
    assert cache.get("a") is None
    assert cache.get("b") is second
    assert cache.held_bytes <= cache.memory_budget
    assert cache.cost == second.cost


def test_a_mesh_that_grows_after_it_was_stored_counts_with_its_growth() -> None:
    """Was später an einem gespeicherten Netz gerechnet wird, wiegt mit.

    Das Netz im Cache ist dasselbe Objekt wie in der Szene; Kantentabellen,
    Nachbarschaften und die Schichtanalyse des Prüfberichts hängen sich danach
    an. Gemessen beim Ablegen allein, sah die Grenze am Spiderman ein Drittel
    dessen, was wirklich lag.
    """
    small = sphere_result("obj_1")
    cache = ResultCache(memory_budget=10**9)
    cache.put("a", small)
    before = cache.held_bytes
    _grown(small)
    assert cache.held_bytes > before * 2, "the derived arrays are counted after they appear"


def test_older_entries_shrink_before_any_entry_gives_way() -> None:
    """Über der Grenze bekommen ältere Einträge ein schlankes Netz — keiner geht.

    Schlank heißt: dieselben Felder, ohne Abgeleitetes, in einem neuen Netz.
    Das alte bleibt unberührt — ein anderer Faden kann es gerade lesen —, und
    was nicht aus der Geometrie folgt, hier der Ursprung je Dreieck, reist mit.
    Der jüngste Eintrag bleibt ganz, und das Abgeleitete kommt auf Nachfrage
    gleich zurück.
    """
    import numpy as np

    from app.core.scene.cache import held_by

    old, new = sphere_result("obj_1"), sphere_result("obj_2")
    for entry in (old, new):
        _grown(entry)._cache.cache["solidon_refined_units"] = ("Herkunft", b"belegt")
    raw_old = cast(Any, old.objects[0].mesh).raw
    adjacency = np.array(raw_old.face_adjacency)
    cache = ResultCache(memory_budget=held_by(old) + held_by(new) - 100_000)
    cache.put("a", old)
    cache.put("b", new)
    cache.trim()

    shrunk, whole = cache.get("a"), cache.get("b")
    assert shrunk is not None and whole is new, "nothing gave way, the newest stayed"
    lean = cast(Any, shrunk.objects[0].mesh).raw
    assert lean is not raw_old
    assert "face_adjacency" in raw_old._cache.cache, "the old mesh itself is untouched"
    assert "face_adjacency" not in lean._cache.cache, "the cache now holds the lean one"
    assert lean._cache.cache["solidon_refined_units"] == ("Herkunft", b"belegt")
    assert np.shares_memory(lean.vertices, raw_old.vertices), "the arrays are shared, not copied"
    assert shrunk.objects[0].features == old.objects[0].features
    assert cache.held_bytes <= cache.memory_budget
    np.testing.assert_array_equal(lean.face_adjacency, adjacency)


def test_arrays_two_entries_share_count_once() -> None:
    """Ein verschobenes Netz teilt seine Nachbarschaften mit dem Quellnetz — einmal gezählt.

    ``transform._carry_cache`` gibt die Topologie weiter, statt sie neu zu
    rechnen; je Eintrag gezählt, stünde sie zweimal in der Rechnung, und die
    Grenze schrumpfte Einträge, die gar nichts mehr freigeben.
    """
    import numpy as np

    from app.core.geom.transform import apply
    from app.core.scene.cache import held_by

    source = sphere_result("obj_1")
    _grown(source)
    shifted = np.eye(4)
    shifted[0, 3] = 5.0
    moved_mesh = apply(cast(Any, source.objects[0].mesh), shifted)
    moved = CachedResult(objects=(SceneObject(id="obj_1", name="Kugel", mesh=moved_mesh),))
    shared = [
        name
        for name, value in moved_mesh.raw._cache.cache.items()
        if isinstance(value, np.ndarray)
        and value is cast(Any, source.objects[0].mesh).raw._cache.cache.get(name)
    ]
    assert shared, "Voraussetzung: die Kopie teilt Felder mit dem Quellnetz"
    separately = held_by(source) + held_by(moved)
    cache = ResultCache(memory_budget=separately - 1)
    cache.put("a", source)
    cache.put("b", moved)
    exact = cache._exact([], set())[2]
    assert exact < separately - 1
    cache.trim()
    assert cache.get("a") is source, "nothing to shrink when every array counts once"


def test_the_meshes_of_the_scene_stay_as_they_are() -> None:
    """Was die fertige Szene zeigt, hält sie ohnehin: nicht gezählt, nicht ersetzt."""
    old, new = sphere_result("obj_1"), sphere_result("obj_2")
    _grown(old)
    _grown(new)
    cache = ResultCache(memory_budget=1)
    cache.put("a", old)
    cache.put("b", new)
    cache.trim(keep=[old.objects[0].mesh])
    assert cache.get("a") is old, "a mesh of the scene keeps its entry and its arrays"
    assert cache.held_bytes > 1


def test_a_lean_mesh_keeps_its_colours_and_a_textured_one_stays() -> None:
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData

    body = trimesh.creation.icosphere(subdivisions=2)
    body.visual.face_colors = np.tile([10, 200, 30, 255], (len(body.faces), 1))
    _ = body.face_adjacency
    mesh = MeshData(raw=body, slots=tuple(0 for _ in body.faces))
    lean = mesh.lean()
    assert lean is not mesh and lean.slots == mesh.slots
    np.testing.assert_array_equal(lean.raw.visual.face_colors, body.visual.face_colors)
    assert lean.lean() is lean, "nothing left to let go"
    textured = trimesh.creation.box()
    textured.visual = trimesh.visual.TextureVisuals(uv=np.zeros((len(textured.vertices), 2)))
    assert MeshData.of(textured).lean().raw is textured


def test_a_run_from_the_cache_alone_keeps_the_bound(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zurücknehmen legt nichts ab — und doch wächst der Stand, der wieder vorn ist.

    Am Spiderman rechnete jeder Schritt zurück 256 MB Nachbarschaften neu, und
    ohne Ablegen hielt niemand die Grenze: 2,7 statt 1 GB nach acht Schritten
    (08.10.2026). Die Auswertung ruft ``trim`` am Ende jedes vollständigen
    Laufs, auch aus lauter Treffern, mit den Netzen ihrer Szene.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 10.0, "depth": 10.0, "height": 5.0})],
    )
    trimmed: list[set[int]] = []
    session_cache = ResultCache()
    evaluate(project.document, profile, cache=session_cache)
    monkeypatch.setattr(
        session_cache, "trim", lambda keep=(): trimmed.append({id(mesh) for mesh in keep})
    )
    hits = session_cache.statistics.hits
    result = evaluate(project.document, profile, cache=session_cache)
    assert session_cache.statistics.hits > hits, "Voraussetzung: ein Lauf aus lauter Treffern"
    assert trimmed == [{id(body.mesh) for body in result.scene.objects.values()}]


def test_the_newest_entry_stays_even_when_it_alone_is_over_the_budget() -> None:
    """Ohne den jüngsten Eintrag rechnete der nächste Schritt den ganzen Verlauf noch einmal."""
    cache = ResultCache(memory_budget=1)
    cache.put("a", sphere_result("obj_1"))
    cache.put("b", sphere_result("obj_2"))
    cache.trim()
    assert len(cache) == 1
    assert cache.get("b") is not None


@pytest.mark.parametrize(
    ("installed", "expected"),
    [
        (8 * 2**30, 2**30),
        (16 * 2**30, 2 * 2**30),
        (2 * 2**30, 512 * 2**20),
        (64 * 2**30, 4 * 2**30),
        (None, 2**30),
    ],
)
def test_the_memory_level_takes_an_eighth_of_the_installed_memory(
    monkeypatch: pytest.MonkeyPatch, installed: int | None, expected: int
) -> None:
    """Auf 8 GB ein Gigabyte, auf 16 zwei; nie unter 512 MB, nie über 4 GB."""
    from app.core import memory
    from app.core.scene.cache import default_memory_budget

    monkeypatch.setattr(memory, "physical_memory", lambda: installed)
    assert default_memory_budget() == expected
    assert ResultCache().memory_budget == expected


def test_every_array_of_a_mesh_cache_is_counted() -> None:
    """Ein Wörterbuch wird ganz gezählt — eine Stichprobe über Schlüssel und Werte
    in einer Reihe traf am Spiderman nur die Schlüssel, und 685 MB blieben
    ungezählt. Lange gleichartige Folgen dürfen hochgerechnet werden."""
    import numpy as np

    from app.core.memory import held_bytes

    cache = {f"feld_{index}": np.zeros(1000) for index in range(32)}
    assert held_bytes(cache) >= 32 * 8000
    points = tuple((float(index), float(index) + 0.5) for index in range(5000))
    estimate = held_bytes(points)
    import sys

    exact = sys.getsizeof(points) + sum(
        sys.getsizeof(point) + 2 * sys.getsizeof(1.5) for point in points
    )
    assert 0.9 * exact <= estimate <= 1.1 * exact


def test_what_recognition_remembers_for_a_body_counts_with_it() -> None:
    """Die Merker der Erkennung gehen mit dem Körper — wer ihn hält, hält sie mit.

    Der Cache zählt sie deshalb zu dem Eintrag, dessen Netz sie trägt
    (``perceive.features.held_answers``).
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect, forget_cache, held_answers
    from app.core.scene.cache import _mesh_bytes

    forget_cache()
    body = trimesh.creation.cylinder(radius=8.0, height=20.0, sections=96)
    mesh = MeshData.of(body)
    detect(mesh)
    answers = held_answers(body)
    assert answers, "Voraussetzung: die Erkennung hat sich etwas gemerkt"
    from app.core.memory import held_bytes

    seen: set[int] = set()
    own = mesh.held_bytes(seen)
    each = sum(held_bytes(answer, seen) for answer in answers)
    assert _mesh_bytes(mesh, set()) == own + each, "every memo counted once, none estimated"


def test_a_mixed_list_is_counted_without_a_sample() -> None:
    """Hundert kleine Felder und ein großes, in beiden Reihenfolgen — dieselbe Summe.

    Die Merker der Erkennung kommen als gemischte Liste in der Folge einer
    Menge; eine Stichprobe traf sie je nach Hash mit 0,7 oder 39 statt 33 MB
    (Review L, M1).
    """
    import numpy as np

    from app.core.memory import held_bytes

    small = [np.zeros(10) for _ in range(99)]
    big = np.zeros(1_000_000)
    exact = sum(item.nbytes for item in small) + big.nbytes
    for items in ([*small, big], [big, *small], [{"fit": item} for item in (*small, big)]):
        assert 0.95 * exact <= held_bytes(items) <= 1.1 * exact + 200_000


def test_recognition_memos_count_the_same_under_every_hash_seed() -> None:
    """Dieselbe Zahl in jedem Prozess — die Folge der Merker hängt am Hash (Review L, M1)."""
    import subprocess
    import sys

    script = "; ".join(
        (
            "import sys",
            "sys.path.insert(0, sys.argv[1])",
            "import trimesh",
            "from app.core.geom.mesh import MeshData",
            "from app.core.perceive.features import detect",
            "from app.core.scene.cache import _mesh_bytes",
            "body = trimesh.creation.cylinder(radius=8.0, height=20.0, sections=96)",
            "mesh = MeshData.of(body)",
            "detect(mesh)",
            "print(_mesh_bytes(mesh, set()))",
        )
    )
    root = str(Path(__file__).resolve().parents[1])
    counted = set()
    for seed in ("1", "2", "3", "4"):
        environment = dict(os.environ, PYTHONHASHSEED=seed, PYTHONUTF8="1")
        finished = subprocess.run(
            [sys.executable, "-c", script, root],
            capture_output=True,
            text=True,
            env=environment,
            cwd=root,
            timeout=300,
            check=True,
        )
        counted.add(int(finished.stdout.split()[-1]))
    assert len(counted) == 1, counted


def test_the_installed_memory_is_read_from_the_system() -> None:
    from app.core.memory import physical_memory

    installed = physical_memory()
    assert installed is not None
    assert 2**30 <= installed <= 2**44


def test_a_smaller_limit_of_the_process_wins_over_the_installed_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Grenze unter dem Rechner bemisst die Speicherebene, nicht der Wirt (Review L, G4)."""
    from app.core import memory

    monkeypatch.setattr(memory, "_installed_memory", lambda: 64 * 2**30)
    monkeypatch.setattr(memory, "_process_limits", lambda: [None, 2 * 2**30])
    assert memory.physical_memory() == 2 * 2**30
    monkeypatch.setattr(memory, "_process_limits", lambda: [None, 128 * 2**30])
    assert memory.physical_memory() == 64 * 2**30
    monkeypatch.setattr(memory, "_installed_memory", lambda: None)
    monkeypatch.setattr(memory, "_process_limits", lambda: [None])
    assert memory.physical_memory() is None


def test_the_cgroup_limit_is_read_from_the_own_group_and_above(tmp_path: Path) -> None:
    """cgroup v2 über die eigene Gruppe und jede darüber, v1 über die eigene (G4).

    Rein über Dateien, auf jeder Plattform: ``max`` ist keine Grenze, die
    kleinste Zahl gilt, ohne Dateien gibt es keine.
    """
    from app.core.memory import _cgroup_limit

    root = tmp_path / "cgroup"
    own = tmp_path / "self_cgroup"
    assert _cgroup_limit(root, own) is None
    scope = root / "user.slice" / "app.scope"
    scope.mkdir(parents=True)
    (root / "memory.max").write_text("max\n", encoding="ascii")
    (root / "user.slice" / "memory.max").write_text("4294967296\n", encoding="ascii")
    (scope / "memory.max").write_text("max\n", encoding="ascii")
    own.write_text("0::/user.slice/app.scope\n", encoding="ascii")
    assert _cgroup_limit(root, own) == 4 * 2**30
    (scope / "memory.max").write_text("1073741824\n", encoding="ascii")
    assert _cgroup_limit(root, own) == 2**30

    legacy = tmp_path / "legacy"
    group = legacy / "memory" / "docker" / "abc"
    group.mkdir(parents=True)
    (group / "memory.limit_in_bytes").write_text("2147483648\n", encoding="ascii")
    own.write_text("12:cpu,cpuacct:/docker/abc\n4:memory:/docker/abc\n", encoding="ascii")
    assert _cgroup_limit(legacy, own) == 2 * 2**30
    # Im Container sieht der Prozess seine Gruppe als Wurzel.
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / "memory.max").write_text("3221225472\n", encoding="ascii")
    own.write_text("0::/\n", encoding="ascii")
    assert _cgroup_limit(inside, own) == 3 * 2**30


@pytest.mark.skipif(sys.platform != "win32", reason="Jobs gibt es nur unter Windows")
def test_a_windows_job_limit_bounds_the_memory() -> None:
    """Ein Prozess in einem Job mit Speichergrenze nennt diese Grenze (G4)."""
    import subprocess

    script = "\n".join(
        [
            "import ctypes, sys",
            "from ctypes import wintypes",
            "sys.path.insert(0, sys.argv[1])",
            "from app.core import memory",
            "class Basic(ctypes.Structure):",
            "    _fields_ = [('a', ctypes.c_int64), ('b', ctypes.c_int64),",
            "        ('flags', wintypes.DWORD), ('c', ctypes.c_size_t), ('d', ctypes.c_size_t),",
            "        ('e', wintypes.DWORD), ('f', ctypes.c_size_t), ('g', wintypes.DWORD),",
            "        ('h', wintypes.DWORD)]",
            "class Extended(ctypes.Structure):",
            "    _fields_ = [('basic', Basic), ('io', ctypes.c_ulonglong * 6),",
            "        ('process', ctypes.c_size_t), ('job', ctypes.c_size_t),",
            "        ('i', ctypes.c_size_t), ('j', ctypes.c_size_t)]",
            "kernel = ctypes.WinDLL('kernel32', use_last_error=True)",
            "kernel.CreateJobObjectW.restype = wintypes.HANDLE",
            "kernel.GetCurrentProcess.restype = wintypes.HANDLE",
            "kernel.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int,",
            "    ctypes.c_void_p, wintypes.DWORD)",
            "kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)",
            "job = kernel.CreateJobObjectW(None, None)",
            "info = Extended()",
            "info.basic.flags = 0x100",
            "info.process = 3 * 2**30",
            "size = ctypes.sizeof(info)",
            "assert kernel.SetInformationJobObject(job, 9, ctypes.byref(info), size)",
            "assert kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess())",
            "print(memory.physical_memory())",
        ]
    )
    done = subprocess.run(
        [sys.executable, "-c", script, str(Path(__file__).resolve().parent.parent)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert int(done.stdout.strip()) == 3 * 2**30


def test_a_long_history_on_a_large_body_stays_inside_the_memory_level(profile: Profile) -> None:
    """Der Kundenweg, an dem es auffiel: dasselbe Modell, Schritt um Schritt verschoben.

    Am Spiderman hielt jedes Verschieben 230 MB mehr fest, ohne Verdrängung bis
    zu zwanzig Millionen Dreiecken. Hier ein Körper mit 20 480 Dreiecken, je
    Schritt Nachgerechnetes daran und eine Grenze für zwei volle Einträge:
    Der Cache hält sie nach jedem Schritt, und weil ältere Einträge schrumpfen
    statt zu gehen, kommt jeder Schritt weiter aus dem Speicher — eine
    Auswertung geht den ganzen Verlauf durch, und ein verdrängter Schritt käme
    bei jeder von der Platte.
    """
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import held_by
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    body = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/ball.stl", sha256=""
    )
    project.sources["src_1"] = trimesh.exchange.stl.export_stl(body)
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    probe = ResultCache()
    first = evaluate(project.document, profile, sources=sources, cache=probe)
    entry = max(probe._entries.values(), key=held_by)
    budget = int(held_by(entry) * 2.0)
    cache = ResultCache(memory_budget=budget)
    evaluate(project.document, profile, sources=sources, cache=cache)
    target = next(iter(first.scene.objects))

    def reported(result: Any) -> None:
        """Was das Fenster am gezeigten Netz nachrechnet, ableitbar und nicht mitbewegt."""
        import numpy as np

        for body in result.scene.objects.values():
            raw = cast(Any, body.mesh).raw
            raw._cache.verify()
            raw._cache.cache["vertex_degree"] = np.ones(400_000)

    def beyond(result: Any) -> int:
        """Was der Cache über die Netze der Szene hinaus hält, jedes Feld einmal."""
        meshes = [body.mesh for body in result.scene.objects.values()]
        return cache._exact(meshes, {id(mesh) for mesh in meshes})[2]

    for _step in range(8):
        history.apply(
            "Verschieben",
            [OperationDraft(op="translate_object", inputs=(target,), params={"dx": 1.0})],
        )
        result = evaluate(project.document, profile, sources=sources, cache=cache)
        assert beyond(result) <= budget, "the memory level keeps its bound after every step"
        reported(result)
    misses = cache.statistics.misses
    evaluate(project.document, profile, sources=sources, cache=cache)
    assert cache.statistics.misses == misses, "every step still comes from memory"
    # Zurücknehmen legt nichts ab, und doch wächst der Stand, der wieder vorn
    # ist; die Auswertung hält die Grenze am Ende jedes Laufs (``trim``).
    for _step in range(8):
        history.undo()
        result = evaluate(project.document, profile, sources=sources, cache=cache)
        assert beyond(result) <= budget, "undoing keeps the bound too"
        reported(result)
    assert cache.statistics.misses == misses, "undoing reads every step from memory"
    assert cache.statistics.evictions == 0, "older steps shrank instead of giving way"


def test_trimming_counts_once_and_a_lean_entry_stays_lean(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zehn Verschieben unter knapper Grenze: je ``trim`` eine genaue Zählung (Review L, M2).

    Nach jedem Schrumpfen und Verdrängen alles neu zu zählen, kostete am Riser
    unter 150 MB Grenze 3 s je Auswertung, quadratisch mit dem Verlauf. Und
    eine Auswertung aus Treffern rechnete an jedem schlanken Netz Mittelpunkte
    und Flächen neu, die ``trim`` danach wieder freigab — zwei Läufe ohne
    Änderung schrumpften dieselben Einträge zweimal.
    """
    import numpy as np

    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene import cache as cache_module
    from app.core.scene.cache import held_by
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from tests.test_matching import ridged_ring

    load_operations()
    # Drei Verrundungen um denselben Kreis: Zwillinge, die jede Zuordnung
    # nach dem Ort ihrer Oberfläche am alten Netz trennt
    # (``matching.surface_places``) — auch wenn es aus dem Cache kommt.
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/ring.stl", sha256=""
    )
    project.sources["src_1"] = ridged_ring()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    probe = ResultCache()
    first = evaluate(project.document, profile, sources=sources, cache=probe)
    budget = int(max(held_by(entry) for entry in probe._entries.values()) * 1.5)
    cache = ResultCache(memory_budget=budget)
    target = next(iter(first.scene.objects))
    counted: list[int] = []
    leaned: list[int] = []
    real_exact = ResultCache._exact
    real_leaner = cache_module._leaner

    def exact(self: ResultCache, *args: Any) -> Any:
        counted[-1] += 1
        return real_exact(self, *args)

    def leaner(result: CachedResult, kept: Any) -> CachedResult:
        lean = real_leaner(result, kept)
        leaned[-1] += lean is not result
        return lean

    monkeypatch.setattr(ResultCache, "_exact", exact)
    monkeypatch.setattr(cache_module, "_leaner", leaner)
    real_trim = ResultCache.trim

    def trim(self: ResultCache, keep: Any = ()) -> None:
        counted.append(0)
        leaned.append(0)
        real_trim(self, keep)

    monkeypatch.setattr(ResultCache, "trim", trim)
    for _step in range(10):
        history.apply(
            "Verschieben",
            [OperationDraft(op="translate_object", inputs=(target,), params={"dx": 1.0})],
        )
        result = evaluate(project.document, profile, sources=sources, cache=cache)
        # Was das Fenster am gezeigten Netz nachrechnet, ableitbar und nicht
        # mitbewegt (``transform._carry_cache`` teilte es sonst mit dem nächsten).
        for shown in result.scene.objects.values():
            raw = cast(Any, shown.mesh).raw
            raw._cache.verify()
            raw._cache.cache["vertex_degree"] = np.ones(200_000)
    assert max(counted) <= 1, f"one exact count per trim, got {counted}"
    assert sum(leaned) > 0, "Voraussetzung: die Grenze schrumpft ältere Einträge"
    leaned.clear()
    for _again in range(2):
        evaluate(project.document, profile, sources=sources, cache=cache)
    assert leaned == [0, 0], f"an unchanged run shrinks nothing again, got {leaned}"


def test_the_matching_memory_counts_inside_the_byte_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """Was der Merker der Zuordnung hält, zählt in derselben Grenze (Review L, G3)."""
    from app.core.scene import cache as cache_module
    from app.core.scene.cache import held_by

    old, new = sphere_result("obj_1"), sphere_result("obj_2")
    _grown(old)
    _grown(new)
    budget = held_by(old) + held_by(new) + 1_000
    cache = ResultCache(memory_budget=budget)
    cache.put("old", old)
    cache.put("new", new)
    cache.trim()
    assert cache._entries["old"] is old, "Voraussetzung: beide passen ohne den Merker"
    monkeypatch.setattr(cache_module, "_memo_bytes", lambda seen=None: 2_000)
    cache.trim()
    shrunk = cache._entries["old"]
    assert shrunk is not old, "the older entry made room for the memo"
    assert cache._entries["new"] is new


def test_an_exact_body_counts_its_tessellation_and_shape_and_turns_lean() -> None:
    """Ein exakter Körper zählt Tessellierung, Merker und Form und wird schlank (Review L, G5).

    Vorher zählte er 36 Byte je Dreieck und wurde nie schlank — ein langer
    B-Rep-Verlauf hielt die Grenze der Speicherebene nicht.
    """
    from app.core.brep import edit
    from app.core.brep.kernel import SHAPE_BYTES_PER_ENTITY
    from app.core.scene.cache import FALLBACK_BYTES_PER_TRIANGLE, held_by

    body = edit.boolean("difference", [edit.box(40.0, 40.0, 10.0), edit.cylinder(8.0, 30.0)])
    mesh = body.mesh
    raw = mesh.raw
    _ = raw.face_adjacency, raw.edges_unique, raw.triangles_center
    entry = CachedResult(objects=(SceneObject(id="obj_1", name="Platte", mesh=body),))
    shape = SHAPE_BYTES_PER_ENTITY * (body.face_count + body.edge_count)
    counted = held_by(entry)
    assert counted >= mesh.held_bytes() + shape
    assert counted > 4 * body.triangle_count * FALLBACK_BYTES_PER_TRIANGLE
    lean = body.lean()
    assert lean is not body and lean.shape is body.shape, "the shape is shared, not copied"
    assert lean.mesh.raw.vertices is raw.vertices
    assert "face_adjacency" not in lean.mesh.raw._cache.cache
    assert lean.volume == body.volume and lean.face_count == body.face_count
    assert held_by(CachedResult(objects=(SceneObject(id="obj_1", name="P", mesh=lean),))) < counted
    assert lean.lean() is lean, "nothing left to release"


def test_trimming_reports_what_waits_for_the_collector() -> None:
    """Was ``trim`` loslässt, meldet es der Speicherbereinigung (RM-594)."""
    from app.core import memory

    old, new = sphere_result("obj_1"), sphere_result("obj_2")
    _grown(old)
    _grown(new)
    cache = ResultCache(memory_budget=1)
    cache.put("old", old)
    cache.put("new", new)
    memory.forget_released()
    try:
        cache.trim()
        assert cache._entries.get("old") is not old
        assert memory.released_bytes() > 5_120 * 36, "the leaned or evicted arrays are reported"
        memory.forget_released()
        cache.trim()
        assert memory.released_bytes() == 0, "nothing more to release"
    finally:
        memory.forget_released()


def test_a_lean_mesh_keeps_what_the_report_asks_after_undo() -> None:
    """Nach dem Zurücknehmen fragt der Bericht nach kleinen Teilen — ein schlankes Netz rechnet
    dafür nichts neu (Review L, G9).

    Ohne Teile und Flächen im schlanken Netz rechnete es am Spiderman
    Kantentabelle, Dreiecke, Kreuzprodukte und Flächen neu, 0,4 s je Schritt.
    """
    from app.core.geom.mesh import MeshData, face_components
    from app.core.geom.repair import small_components

    old = sphere_result("obj_1")
    raw = _grown(old)
    face_components(raw)
    _ = raw.area_faces
    lean = cast(Any, old.objects[0].mesh).lean()
    assert isinstance(lean, MeshData) and lean is not old.objects[0].mesh
    held = set(lean.raw._cache.cache)
    assert "face_adjacency" not in held, "Voraussetzung: das Netz ist schlank"
    assert small_components(lean.raw) == []
    assert set(lean.raw._cache.cache) == held, "nothing was computed again"


def test_the_byte_bound_counts_features_once_across_entries_and_remembered_steps(
    profile: Profile,
) -> None:
    """Was Einträge und gemerkte Schritte teilen, zählt die Grenze einmal (Nachprüfung L, M-3).

    Ein verschobener Körper behält die Dreiecksnummern seiner Merkmale, und
    der gemerkte Zuordnungsschritt teilt sie mit dem Eintrag, aus dem er kam.
    Je Satz und je Schritt für sich gezählt, hielt die Grenze am Laptop-Riser
    nach vier Verschieben 212 statt 147 MB — sie schrumpfte und verdrängte
    früher, und der Schrittmerker war nach dreizehn Schritten voll.
    """
    from importlib import import_module

    from app.core.bootstrap import load_operations
    from app.core.memory import held_bytes
    from app.core.perceive import matching
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene import cache as cache_module
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    evaluation = import_module("app.core.scene.evaluate")
    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "plate_holes.stl").read_bytes()
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    cache = ResultCache()
    result = evaluate(project.document, profile, sources=sources, cache=cache)
    target = next(iter(result.scene.objects))
    for _step in range(4):
        history.apply(
            "Verschieben",
            [OperationDraft(op="translate_object", inputs=(target,), params={"dx": 1.0})],
        )
        result = evaluate(project.document, profile, sources=sources, cache=cache)
    assert len(result.scene.objects[target].features) >= 10, "Voraussetzung: Merkmale"
    assert len(evaluation._REMEMBERED_STEPS) >= 4, "Voraussetzung: gemerkte Schritte"
    kept = [body.mesh for body in result.scene.objects.values()]
    ids = {id(mesh) for mesh in kept}
    _sizes, _freeable, counted = cache._exact(kept, ids)
    # Von außen, jedes Feld einmal: die Szene, die Einträge vom jüngsten an,
    # was die gemerkten Schritte darüber hinaus halten, der Zuordnungsmerker.
    seen: set[int] = set()
    for mesh in kept:
        cache_module._mesh_bytes(mesh, seen)
    once = sum(
        cache_module.held_by(cache._entries[key], ids, seen)
        for key in reversed(list(cache._entries))
    )
    # Je Feld des Schritts für sich: Ein Tupel nur für die Zählung bekäme beim
    # nächsten Schritt dieselbe Kennung und zählte dann als gesehen.
    once += sum(
        held_bytes(part, seen)
        for step in evaluation._REMEMBERED_STEPS.values()
        for part in (step.changed, step.findings, step.source, step.digests)
    )
    once += sum(held_bytes(answer, seen) for _ways, answer, _weight in matching._MATCHES.values())
    assert abs(counted - once) <= 0.1 * once, f"bound counts {counted}, each field once {once}"


def test_the_report_keeps_its_analysis_after_undo_under_a_tight_bound(profile: Profile) -> None:
    """Nach acht Verschieben und dem Weg zurück hat der gezeigte Stand seine Schichtanalyse noch.

    Ein schlankes Netz ließ sie los (Nachprüfung L, M-2), und der Prüfbericht
    schnitt nach dem Zurücknehmen neu — am Spiderman 52 s auf einem Rechner mit
    8 GB. Sie hält als Felder nur noch einen Bruchteil (RM-595) und bleibt.
    """
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import as_mesh_data
    from app.core.knowledge import print_settings
    from app.core.knowledge.profiles import analysis_limits
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import held_by
    from app.core.scene.project import ProjectSources, new_project
    from app.core.slice.findings import analysed, remembered_analysis
    from app.core.types import Source

    load_operations()
    body = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/ball.stl", sha256=""
    )
    project.sources["src_1"] = trimesh.exchange.stl.export_stl(body)
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    settings = print_settings.resolve(profile)
    probe = ResultCache()
    evaluate(project.document, profile, sources=sources, cache=probe)
    # Die Grenze hält gerade den Ladestand. Mit dem Anderthalbfachen blieben
    # alle neun Stände ganz, seit ein bewegtes Netz seine Dreiecke mit dem
    # Quellnetz teilt (RM-698) — dann wurde nichts schlank, und die Frage
    # stellte sich nicht.
    budget = max(held_by(entry) for entry in probe._entries.values())
    cache = ResultCache(memory_budget=budget)
    loaded = evaluate(project.document, profile, sources=sources, cache=cache)
    target = next(iter(loaded.scene.objects))

    def report(result: Any) -> tuple[Any, float, float]:
        """Was das Fenster nach jeder Auswertung tut: die Analyse am gezeigten Netz."""
        entry = result.scene.objects[target]
        wall, angle = analysis_limits(profile, entry)
        analysed(as_mesh_data(entry.mesh), settings, angle, wall)
        return entry, angle, wall

    report(loaded)
    for _step in range(8):
        history.apply(
            "Verschieben",
            [OperationDraft(op="translate_object", inputs=(target,), params={"dx": 1.0})],
        )
        moved = evaluate(project.document, profile, sources=sources, cache=cache)
        report(moved)
        # Was das Fenster sonst am gezeigten Netz nachrechnet, ableitbar.
        raw = cast(Any, moved.scene.objects[target].mesh).raw
        _ = raw.face_adjacency, raw.edges_unique
    for _step in range(8):
        history.undo()
    back = evaluate(project.document, profile, sources=sources, cache=cache)
    entry = back.scene.objects[target]
    wall, angle = analysis_limits(profile, entry)
    mesh = as_mesh_data(entry.mesh)
    assert entry.mesh is not loaded.scene.objects[target].mesh, (
        "Voraussetzung: der Ladestand kommt als schlankes Netz zurück"
    )
    assert remembered_analysis(mesh, settings, angle, wall) is not None, (
        "the shown state still has its analysis"
    )


def test_a_reopened_history_keeps_only_its_newest_step_whole(
    profile: Profile, tmp_path: Path
) -> None:
    """Von der Platte geholt, gibt ein älterer Stand seine Ableitungen ab, sobald der nächste kommt.

    Im Speicher teilt ein bewegtes Netz Kantentabellen und Nachbarschaften mit
    seinem Quellnetz (``transform._carry_cache``); von der Platte gelesen
    rechnet jeder Stand sie für sich (``_warm_figures``) und hielt sie: am
    Spiderman rund 290 MB je Verschieben, nach vier Schritten 1,1 GB mehr als
    derselbe Verlauf im Speicher (RM-698). Das Ergebnis bleibt dasselbe.
    """
    import numpy as np
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import RELEASABLE, MeshCodec, as_mesh_data
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/ball.stl", sha256=""
    )
    body = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
    project.sources["src_1"] = trimesh.exchange.stl.export_stl(body)
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    warm = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    target = next(
        iter(evaluate(project.document, profile, sources=sources, cache=warm).scene.objects)
    )
    for _step in range(3):
        history.apply(
            "Verschieben",
            [OperationDraft(op="translate_object", inputs=(target,), params={"dx": 2.0})],
        )
        computed = evaluate(project.document, profile, sources=sources, cache=warm)

    cold = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    read = evaluate(project.document, profile, sources=sources, cache=cold)

    assert cold.statistics.disk_hits == 4, "Voraussetzung: jeder Stand kommt von der Platte"
    shown = as_mesh_data(read.scene.objects[target].mesh)
    entries = list(cold._entries.values())
    held = [set(as_mesh_data(entry.objects[0].mesh).raw._cache.cache) for entry in entries]
    assert all(not keys & RELEASABLE for keys in held[:-1]), [
        sorted(keys & RELEASABLE) for keys in held[:-1]
    ]
    assert entries[-1].objects[0].mesh is read.scene.objects[target].mesh
    assert held[-1] & RELEASABLE, "der gezeigte Stand bleibt warm"
    expected = as_mesh_data(computed.scene.objects[target].mesh)
    assert np.array_equal(shown.raw.vertices, expected.raw.vertices)
    assert np.array_equal(shown.raw.faces, expected.raw.faces)
    assert read.scene.objects[target].features == computed.scene.objects[target].features


def test_secondary_material_calibration_and_role_are_part_of_the_hash(profile: Profile) -> None:
    """Eine geänderte Einlagenkalibrierung darf kein Ergebnis der alten Passung laden."""
    operation = Operation(id=1, op="material_pair")
    softer = dataclasses.replace(
        profile, material=dataclasses.replace(profile.material, id="liner")
    )
    changed = dataclasses.replace(
        softer,
        material=dataclasses.replace(softer.material, clearance=softer.material.clearance + 0.1),
    )

    def key(profiles: dict[str, Profile] | None = None) -> str:
        return operation_hash(operation, {}, [], profile, "fine", material_profiles=profiles)

    assert key() == key({})
    assert key({"liner": softer}) != key({"liner": changed})
    assert key({"liner": softer}) != key({"clamp": softer})
    assert key({"liner": softer, "clamp": profile}) == key({"clamp": profile, "liner": softer})


def test_the_hash_covers_everything_a_result_depends_on(profile: Profile) -> None:
    operation = Operation(id=1, op="resize_object", inputs=("obj_1",), outputs=("obj_1",))
    base = operation_hash(operation, {"size": 5.0}, ["h1"], profile, "fine")

    assert base == operation_hash(operation, {"size": 5.0}, ["h1"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.1}, ["h1"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.0}, ["h2"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.0}, ["h1"], profile, "draft")
    assert base != operation_hash(
        operation, {"size": 5.0}, ["h1"], profile, "fine", implementation_version="new-recipe"
    )
    assert base != operation_hash(
        Operation(id=1, op="resize_object", seed=1), {"size": 5.0}, ["h1"], profile, "fine"
    )


def test_the_profile_enters_the_hash(profile: Profile) -> None:
    from app.core.knowledge import profiles as profile_table

    for name in ("youngs_modulus", "yield_strength", "layer_bond_ratio"):
        different = dataclasses.replace(
            profile, material=dataclasses.replace(profile.material, **{name: 123.456})
        )
        assert profile_key(profile) != profile_key(different)

    other = profile_table.make_profile("centauri-carbon-2", "asa")
    assert profile_key(profile) != profile_key(other)


#: Profilfelder, die keine Operation liest — und warum. Alles andere muss den
#: Profilschlüssel ändern. Bis zur Durchsicht vor 0.5.0 stand dort keine
#: Düsenzahl, und die Anordnung nach Filamenten kam nach einem Wechsel von
#: einer auf zwei Düsen unverändert aus dem Cache.
_PRINTER_FIELDS_NO_OPERATION_READS: dict[str, str] = {
    "title": "nur Anzeige; die Kennung steht im Schlüssel",
    "vendor": "nur Anzeige und Slicerauswahl",
    "enclosed": "Druckeinstellungen und Materialrat, keine Geometrie",
    "bed_temperature_max": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "nozzle_temperature_max": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "travel_speed": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "speed_outer_wall": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "speed_inner_wall": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "speed_infill": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "speed_top_surface": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "speed_first_layer": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "speed_bridge": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "acceleration": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "outer_wall_acceleration": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "flow_factor": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
    "cura_definition": "nur die Cura-Übergabe (Start- und Endcode), keine Geometrie",
    "prusaslicer_printer": "nur die Vorwahl des Prusa-Profils, keine Geometrie",
    "bed_origin": "nur die Bettkoordinaten der Slicerübergabe, keine Geometrie",
    "first_layer_acceleration": "nur die Cura-Übergabe, keine Geometrie",
    "overhang_speed_factors": "nur die Cura-Übergabe, keine Geometrie",
    "first_layer_line_factor": "Druckeinstellungen und Slicerübergabe, keine Geometrie",
}
_MATERIAL_FIELDS_NO_OPERATION_READS: dict[str, str] = {
    "title": "nur Anzeige; die Kennung steht im Schlüssel",
    "calibrated": "Hinweis im Steckbrief und im Rat, keine Geometrie",
    "measured": "nur der Druckrat (RM-589), keine Geometrie",
    "technology": "Materialwahl am Drucker, keine Geometrie",
    "support_gap_factor": "Druckrat und Slicerübergabe, keine Geometrie",
    "support_gap_min": "Druckrat und Slicerübergabe, keine Geometrie",
    "support_gap_max": "Druckrat und Slicerübergabe, keine Geometrie",
    "support_interface_cooling": "Druckrat und Slicerübergabe, keine Geometrie",
    "support_tip_gap": "Druckrat und Slicerübergabe, keine Geometrie",
}


def _changed(value: object) -> object:
    """Ein anderer, gültiger Wert derselben Art."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value + 0.123
    if isinstance(value, str):
        return value + "x"
    if isinstance(value, tuple) and len(value) == 3 and all(isinstance(v, float) for v in value):
        return tuple(entry + 1.0 for entry in value)
    if isinstance(value, tuple):
        return ((-50.0, -50.0), (50.0, -50.0), (0.0, 50.0)) if not value else ()
    if value is None:
        return 0.123
    raise AssertionError(f"no changed value for {value!r}")


#: Prozesswerte (``hashing._profile_parts``): was der Druckdialog setzt
#: (``profiles.for_process``) und was nur über die daraus folgende Mindestwand
#: und Überhanggrenze wirkt — die Probe am eigenen Drucker gilt nur mit
#: passender Schichthöhe und Bahnbreite. Ein Schritt mit
#: ``reads_process=False`` behält seinen Schlüssel, wenn sich eines davon
#: ändert; jedes andere Feld des Schlüssels ändert auch seinen.
_PRINTER_PROCESS_FIELDS = frozenset({"layer_height", "extrusion_width", "overhang_limit"})
_MATERIAL_PROCESS_FIELDS = frozenset(
    {
        "minimum_wall",
        "overhang_angle",
        "calibration_printer",
        "calibration_nozzle_diameter",
        "calibration_layer_height",
        "calibration_extrusion_width",
    }
)


def test_every_profile_field_is_in_the_key_or_named_as_unread(profile: Profile) -> None:
    """Jedes Drucker- und Materialfeld ändert den Schlüssel — oder steht mit Grund oben.

    Und den Schlüssel ohne Prozesswerte ändert genau das, was kein Prozesswert
    ist: Fehlte dort ein festes Feld, käme ein Schritt, der es liest, nach
    einem Druckerwechsel mit dem alten Ergebnis aus dem Speicher."""
    printer_fields = {field.name for field in dataclasses.fields(profile.printer)}
    material_fields = {field.name for field in dataclasses.fields(profile.material)}
    assert set(_PRINTER_FIELDS_NO_OPERATION_READS) <= printer_fields
    assert set(_MATERIAL_FIELDS_NO_OPERATION_READS) <= material_fields
    # Die Prozessmessung wirkt nur mit passender Probe; dann muss sie im Schlüssel stehen.
    calibrated = dataclasses.replace(
        profile,
        material=dataclasses.replace(
            profile.material,
            calibration_printer=profile.printer.id,
            calibration_nozzle_diameter=profile.printer.nozzle_diameter,
            calibration_layer_height=profile.printer.layer_height,
            calibration_extrusion_width=profile.printer.extrusion_width,
            minimum_wall=0.9,
            overhang_angle=50.0,
        ),
    )
    for name in sorted(printer_fields - set(_PRINTER_FIELDS_NO_OPERATION_READS)):
        value = getattr(calibrated.printer, name)
        if name == "technology":
            other = dataclasses.replace(calibrated.printer, technology="resin")
        else:
            other = dataclasses.replace(calibrated.printer, **{name: _changed(value)})
        changed = dataclasses.replace(calibrated, printer=other)
        assert profile_key(calibrated) != profile_key(changed), (
            f"printer.{name} does not enter the profile key"
        )
        same_without_process = profile_key(calibrated, process=False) == profile_key(
            changed, process=False
        )
        assert same_without_process == (name in _PRINTER_PROCESS_FIELDS), (
            f"printer.{name} is on the wrong side of the process split"
        )
    for name in sorted(material_fields - set(_MATERIAL_FIELDS_NO_OPERATION_READS)):
        value = getattr(calibrated.material, name)
        other_material = dataclasses.replace(calibrated.material, **{name: _changed(value)})
        changed = dataclasses.replace(calibrated, material=other_material)
        assert profile_key(calibrated) != profile_key(changed), (
            f"material.{name} does not enter the profile key"
        )
        same_without_process = profile_key(calibrated, process=False) == profile_key(
            changed, process=False
        )
        assert same_without_process == (name in _MATERIAL_PROCESS_FIELDS), (
            f"material.{name} is on the wrong side of the process split"
        )
    assert printer_fields >= _PRINTER_PROCESS_FIELDS
    assert material_fields >= _MATERIAL_PROCESS_FIELDS


def test_the_full_profile_key_keeps_its_value(profile: Profile) -> None:
    """Der vollständige Schlüssel ist derselbe wie vor der Trennung.

    Er benennt nicht nur Cacheeinträge, sondern auch Filamentbuchungen
    (``filament_usage.usage_requests``): Ein anderer Wert ließe eine gebuchte
    Platte ungebucht aussehen, und sie würde ein zweites Mal abgebucht."""
    printer = profile.printer
    material = profile.material
    before_split = digest(
        printer.id,
        printer.technology,
        printer.nozzle_diameter,
        printer.layer_height,
        printer.extrusion_width,
        printer.pixel_size,
        printer.minimum_wall,
        printer.build_volume,
        printer.printable_area,
        printer.bed_exclusions,
        printer.printable_height,
        printer.nozzles,
        printer.overhang_limit,
        material.id,
        material.clearance,
        material.press,
        material.hole_compensation,
        material.elephant_foot,
        material.shrinkage,
        material.youngs_modulus,
        material.yield_strength,
        material.layer_bond_ratio,
        profile.minimum_wall_thickness,
        profile.overhang_limit_degrees,
    )
    assert profile_key(profile) == before_split
    assert profile_key(profile, process=False) != before_split


def test_a_step_without_process_values_keeps_its_key_across_the_print_dialog(
    profile: Profile,
) -> None:
    """Schichthöhe, Bahnbreite und Stützschwelle ändern nur den Schlüssel eines
    Schritts, der sie liest — auch am Profil eines Eingangs mit eigenem
    Material. Drucker und Material ändern jeden."""
    from app.core.knowledge import print_settings
    from app.core.knowledge import profiles as profile_table

    operation = Operation(id=1, op="load")
    settings = print_settings.resolve(profile)
    changed = profile_table.for_process(
        profile,
        print_settings.with_choice(
            print_settings.with_choice(
                print_settings.with_choice(settings, "layers.layer_height", 0.12),
                "layers.line_width",
                0.62,
            ),
            "support.threshold_angle",
            33.0,
        ),
    )
    assert changed.printer.layer_height == pytest.approx(0.12)
    assert changed.printer.extrusion_width == pytest.approx(0.62)
    assert changed.overhang_limit_degrees == pytest.approx(33.0)
    liner = dataclasses.replace(profile, material=profile_table.material("tpu-95a"))
    changed_liner = dataclasses.replace(changed, material=liner.material)

    def key(current: Profile, own: Profile, *, process: bool) -> str:
        return operation_hash(
            operation,
            {},
            ["h1"],
            current,
            "fine",
            material_profiles={"obj_1": own},
            process=process,
        )

    assert key(profile, liner, process=False) == key(changed, changed_liner, process=False)
    assert key(profile, liner, process=True) != key(changed, changed_liner, process=True)
    assert key(profile, liner, process=True) != key(profile, liner, process=False)
    other_material = dataclasses.replace(profile, material=profile_table.material("pla"))
    assert key(profile, liner, process=False) != key(other_material, liner, process=False)
    wider = dataclasses.replace(
        profile,
        printer=dataclasses.replace(profile.printer, build_volume=(400.0, 400.0, 400.0)),
    )
    assert key(profile, liner, process=False) != key(wider, liner, process=False)


#: Die Schritte, die keinen Prozesswert lesen (``OperationSpec.reads_process``),
#: je mit dem Beleg aus dem Code. Belegt heißt: die Operation und alles, was
#: sie aufruft, liest weder Schichthöhe, Bahnbreite noch Überhanggrenze, keine
#: daraus abgeleitete Größe am Profil (Mindestwand, Überhangwinkel, kleinstes
#: Volumen, kleinste Aufstandsfläche, Exporttoleranz) und keine
#: Schichtanalyse. Die Merkmalserkennung danach (``evaluate._with_features``,
#: ``perceive.features``) bekommt kein Profil. Ein neuer Eintrag ist eine
#: Entscheidung mit Beleg, keine Liste zum Auffüllen.
_STEPS_WITHOUT_PROCESS: dict[str, str] = {
    "load": "Leser, normalise und Baugruppenlage ohne Profil; liest nur "
    "printer.build_volume für die Einheitenfrage (plausible_reach)",
    "load_step": "brep.step und brep.features ohne Profil; ctx.profile wird nicht gelesen",
    "load_outline": "outline.extrude ohne Profil; ctx.profile wird nicht gelesen",
    "duplicate_object": "kopiert Szenenobjekte; ctx.profile wird nicht gelesen",
    "rename_object": "ersetzt den Namen; ctx.profile wird nicht gelesen",
    "delete_object": "gibt nichts aus; ctx.profile wird nicht gelesen",
    "pattern": "moved_object ohne Profil; die Bauraumprüfung liest nur printer.build_volume",
    "translate_object": "moved_object ohne Profil; _held_on_bed → back_onto_bed → "
    "arrange_on_bed/placement_offset/check_build_volume lesen nur Druckfläche, Höhe, "
    "Sperrzonen und build_volume",
    "rotate_object": "wie translate_object; named_pivot und anchor_point ohne Profil",
    "mirror_object": "anchor_point und moved_object ohne Profil; ctx.profile wird nicht gelesen",
    "place_on_bed": "moved_object ohne Profil; ctx.profile wird nicht gelesen",
    "place_group_on_bed": "moved_object ohne Profil; ctx.profile wird nicht gelesen",
}


def test_only_proven_steps_leave_the_process_values_out() -> None:
    """Die Vorgabe liest: Frei ist nur, was oben mit Beleg steht."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    free = {spec.name for spec in REGISTRY.all() if not spec.reads_process}
    assert free == set(_STEPS_WITHOUT_PROCESS)
    # Die Gegenprobe der Leser: Sie behalten die Vorgabe.
    for name in ("orient_for_print", "scale_object", "fit_to_size", "arrange_bed", "hollow_object"):
        assert REGISTRY.get(name).reads_process, name


#: Was :class:`_ProcessGuard` je Teil des Profils nicht lesen lässt.
_GUARDED_NAMES: dict[str, frozenset[str]] = {
    "profile": frozenset(
        {
            "has_process_calibration",
            "minimum_wall_thickness",
            "overhang_limit_degrees",
            "smallest_printable_volume",
            "smallest_first_layer",
            "export_deflection",
        }
    ),
    "printer": _PRINTER_PROCESS_FIELDS | {"smallest_detail"},
    "material": _MATERIAL_PROCESS_FIELDS,
}


class _ProcessGuard:
    """Ein Profil, das beim Lesen eines Prozesswerts abbricht.

    Am Profil selbst sind es alle Eigenschaften — jede der sechs rechnet mit
    einem Prozesswert —, am Drucker Schichthöhe, Bahnbreite, Überhanggrenze
    und das kleinste Detail, am Material die Probe."""

    def __init__(self, wrapped: object, part: str = "profile") -> None:
        self._wrapped = wrapped
        self._part = part

    def __getattr__(self, name: str) -> Any:
        if name in _GUARDED_NAMES[self._part]:
            raise AssertionError(f"reads the process value {self._part}.{name}")
        value = getattr(self._wrapped, name)
        if self._part == "profile" and name in ("printer", "material"):
            return _ProcessGuard(value, name)
        return value


def _guarded_run(
    profile: Profile,
    name: str,
    inputs: list[SceneObject],
    params: Mapping[str, Any],
    *,
    others: tuple[SceneObject, ...] = (),
    sources: Any = None,
) -> Any:
    """Ruft die registrierte Operation mit einem wachenden Profil auf."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    guard: Any = _ProcessGuard(profile)
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in (*inputs, *others)}, profile=guard),
            inputs=inputs,
            params=spec.params(**params),
            profile=guard,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
            sources=sources,
        )
    )


def _loaded_plate(profile: Profile) -> SceneObject:
    from app.core.geom.mesh import read_mesh
    from tests.helpers import MESHES

    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    return SceneObject(id="obj_1", name="Platte", mesh=mesh)


@pytest.mark.parametrize("case", sorted(_STEPS_WITHOUT_PROCESS))
def test_a_step_without_process_values_never_reads_one(profile: Profile, case: str) -> None:
    """Jeder freigestellte Schritt läuft an einem Profil, das beim Lesen eines
    Prozesswerts abbricht — auf den Wegen, die das Profil überhaupt fragen:
    Einheitenfrage beim Laden, Bauraum eines Musters, Rückholung aufs Bett um
    einen Nachbarn herum."""
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.transform import moved_object, translation
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from tests.helpers import MESHES

    load_operations()
    assert case in _STEPS_WITHOUT_PROCESS
    plate = _loaded_plate(profile)
    if case in ("load", "load_step", "load_outline"):
        project = new_project("centauri-carbon-2", "petg")
        if case == "load":
            path, payload = "sources/plate_holes.stl", (MESHES / "plate_holes.stl").read_bytes()
            runs: list[dict[str, Any]] = [{"source": "src_1", "unit": "auto"}]
        elif case == "load_step":
            from tests.helpers import exact_kernel

            exact_kernel()
            from app.core.brep import step
            from app.core.ingest.plan import selection

            data = Path(__file__).parent / "data" / "step" / "multibody.step"
            path, payload = "sources/multibody.step", data.read_bytes()
            keys = [body.key for body in step.read_assembly(payload, "multibody").bodies]
            runs = [
                {"source": "src_1"},
                {
                    "source": "src_1",
                    "bodies": selection(["*"]),
                    "place_on_bed": True,
                    "centre": True,
                },
                {
                    "source": "src_1",
                    "bodies": selection(keys),
                    "place_on_bed": True,
                    "centre": True,
                },
            ]
        else:
            path = "sources/zeichnung.svg"
            payload = (
                b'<svg xmlns="http://www.w3.org/2000/svg">'
                b'<path d="M0 0 H20 V10 H0 Z M5 2 H15 V8 H5 Z"/></svg>'
            )
            runs = [{"source": "src_1", "height": 3.0}]
        project.document.sources["src_1"] = Source(id="src_1", kind="import", path=path, sha256="")
        project.sources["src_1"] = payload
        for params in runs:
            result = _guarded_run(profile, case, [], params, sources=ProjectSources(project))
            assert result.outputs
        if case in ("load", "load_step"):
            # Die freie Stelle (0.5.1) sucht auf dem Bett des Druckers um die
            # Körper davor herum und liest dabei keinen Prozesswert — auch mit
            # belegter Platte, wo sie wirklich suchen muss.
            # Beim STEP der Weg eines neuen Imports: mit Körperauswahl.
            chosen = {key: value for key, value in runs[-1].items() if key in ("source", "bodies")}
            spot = {**(runs[0] if case == "load" else chosen), "free_spot": True}
            result = _guarded_run(
                profile, case, [], spot, sources=ProjectSources(project), others=(plate,)
            )
            assert result.outputs
            assert result.answered, "die gefundene Stelle kommt als Antwort zurück"
        return
    neighbour = SceneObject(
        id="obj_9",
        name="Nachbar",
        mesh=moved_object(plate, translation((0.0, 0.0, 0.0))).mesh,
    )
    width = profile.printer.build_volume[0]
    if case == "duplicate_object":
        assert len(_guarded_run(profile, case, [plate], {"count": 3}).outputs) == 3
    elif case == "rename_object":
        assert _guarded_run(profile, case, [plate], {"name": "B"}).outputs[0].name == "B"
    elif case == "delete_object":
        assert _guarded_run(profile, case, [plate], {}).outputs == []
    elif case == "pattern":
        assert len(_guarded_run(profile, case, [plate], {"count": 3, "spacing": 30.0}).outputs) == 3
        ring = {"kind": "circular", "count": 4, "angle": 360.0}
        assert len(_guarded_run(profile, case, [plate], ring).outputs) == 4
    elif case in ("translate_object", "rotate_object"):
        # Fünf Millimeter vor dem rechten Rand, dann darüber hinaus bewegt; der
        # Nachbar steht, wo das Zurückschieben ihn hinlegte — also ordnet die
        # Rückholung um ihn herum neu ein (``back_onto_bed`` → ``arrange_on_bed``).
        bounds = as_mesh_data(plate.mesh).bounds
        inside = width / 2.0 - bounds.size[0] / 2.0 - 5.0 - bounds.centre[0]
        edge = dataclasses.replace(moved_object(plate, translation((inside, 0.0, 0.0))), id="obj_1")
        near = dataclasses.replace(neighbour, mesh=edge.mesh)
        params: dict[str, Any] = (
            {"dx": 60.0, "keep_on_bed": True}
            if case == "translate_object"
            else {"axis": "z", "angle": 45.0, "about": "centre", "keep_on_bed": True}
        )
        moved = _guarded_run(profile, case, [edge], params, others=(near,))
        codes = {finding.code for finding in moved.findings}
        assert "transform.rearranged_on_bed" in codes, codes
        alone = _guarded_run(profile, case, [edge], params)
        assert {finding.code for finding in alone.findings} & {"transform.nudged_onto_bed"}
    elif case == "mirror_object":
        assert _guarded_run(profile, case, [plate], {"axis": "x"}).outputs
    elif case == "place_on_bed":
        assert _guarded_run(profile, case, [plate], {}).outputs
    elif case == "place_group_on_bed":
        second = dataclasses.replace(neighbour, id="obj_2")
        assert len(_guarded_run(profile, case, [plate, second], {}).outputs) == 2
    else:
        pytest.fail(f"{case} is exempt but has no guarded run here")


def test_the_guard_catches_a_step_that_reads_the_process(profile: Profile) -> None:
    """Die Wache fängt, was sie fangen soll: *Skalieren* fragt das kleinste
    druckbare Volumen, und das rechnet mit Schichthöhe und Bahnbreite."""
    from app.core.bootstrap import load_operations
    from app.core.types import PrinterProfile

    load_operations()
    with pytest.raises(AssertionError, match="process value"):
        _guarded_run(profile, "scale_object", [_loaded_plate(profile)], {"factor": 0.5})
    # Eine neue abgeleitete Größe am Profil ist eine Entscheidung: Jede
    # rechnet heute mit einem Prozesswert, und die Wache muss sie kennen.
    derived = {name for name, value in vars(Profile).items() if isinstance(value, property)}
    assert derived == _GUARDED_NAMES["profile"]
    on_printer = {
        name for name, value in vars(PrinterProfile).items() if isinstance(value, property)
    }
    assert on_printer - {"is_resin"} == _GUARDED_NAMES["printer"] - _PRINTER_PROCESS_FIELDS


@pytest.mark.parametrize(
    "path,value",
    [
        ("layers.layer_height", 0.12),
        ("layers.line_width", 0.62),
        ("support.threshold_angle", 33.0),
    ],
)
def test_the_print_dialog_does_not_reload_or_copy_again(
    monkeypatch: pytest.MonkeyPatch, profile: Profile, path: str, value: float
) -> None:
    """Nur Schichthöhe, Bahnbreite oder Stützschwelle ändern: Laden, Kopieren
    und Verschieben kommen aus dem Speicher — kein neues Einlesen, keine neue
    Merkmalserkennung —, und *Druckoptimal ausrichten*, das alle drei liest,
    rechnet neu.

    Der Anlass (28.09.2026): „Im Slicer öffnen" schreibt die Einstellungen des
    Dialogs ins Projekt, und am Minigolf-Satz lief danach der ganze Verlauf
    neu — Einlesen, Erkennung und Ausrichtung, über zwei Minuten.

    Die Erkennung zählt hier nur mit: Ein neu eingelesenes, bitgleiches Netz
    fände sie auch unter dem alten Schlüssel im Merker. Unterscheiden tun
    Einlesen und Operationsaufrufe. Und die Gegenprobe am Ende: Ein festes
    Druckerfeld, das die freigestellten Schritte lesen (der Bauraum), rechnet
    sie neu."""
    from collections import Counter

    from app.core.bootstrap import load_operations
    from app.core.ingest import ops as ingest_ops
    from app.core.knowledge import print_settings
    from app.core.perceive import features as features_module
    from app.core.registry import REGISTRY
    from app.core.registry.registry import Registry
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from tests.helpers import plate_project

    load_operations()
    calls: Counter[str] = Counter()

    def counted(name: str, fn: Any) -> Any:
        def run(ctx: Any) -> Any:
            calls[name] += 1
            return fn(ctx)

        return run

    registry = Registry()
    for spec in REGISTRY.all():
        registry.register(dataclasses.replace(spec, fn=counted(spec.name, spec.fn)))
    reading = ingest_ops.normalise
    fitting = features_module._fitted

    def normalise(*args: Any, **kwargs: Any) -> Any:
        calls["#read"] += 1
        return reading(*args, **kwargs)

    def fitted(*args: Any, **kwargs: Any) -> Any:
        calls["#detect"] += 1
        return fitting(*args, **kwargs)

    monkeypatch.setattr(ingest_ops, "normalise", normalise)
    monkeypatch.setattr(features_module, "_fitted", fitted)

    project = plate_project()
    document = project.document
    history = History(document)
    history.apply(
        "Kopieren",
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 2})],
    )
    history.apply(
        "Verschieben",
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_2",),
                params={"dx": 60.0, "keep_on_bed": True},
            )
        ],
    )
    history.apply(
        "Ausrichten",
        [
            OperationDraft(
                op="orient_for_print",
                inputs=("obj_1", "obj_2"),
                params={"candidates": 24, "arrange": True},
            )
        ],
    )
    document.print_settings = print_settings.resolve(profile)
    sources = ProjectSources(project)
    cache = ResultCache()
    features_module.forget_cache()

    first = evaluate(document, profile, cache=cache, sources=sources, registry=registry)
    assert first.complete, first.scene.report.findings
    assert calls["load"] == calls["duplicate_object"] == calls["translate_object"] == 1
    assert calls["orient_for_print"] == 1
    assert calls["#read"] == 1
    assert calls["#detect"] > 0, "the first evaluation must detect, or the count below says nothing"

    calls.clear()
    document.print_settings = print_settings.with_choice(document.print_settings, path, value)
    second = evaluate(document, profile, cache=cache, sources=sources, registry=registry)

    assert second.complete, second.scene.report.findings
    assert second.scene.profile is not None
    assert second.scene.profile != first.scene.profile, "the change must reach the profile"
    assert calls["load"] == 0
    assert calls["#read"] == 0
    assert calls["duplicate_object"] == 0
    assert calls["translate_object"] == 0
    assert calls["#detect"] == 0
    assert calls["orient_for_print"] == 1

    calls.clear()
    larger = dataclasses.replace(
        profile, printer=dataclasses.replace(profile.printer, build_volume=(300.0, 300.0, 300.0))
    )
    third = evaluate(document, larger, cache=cache, sources=sources, registry=registry)
    assert third.complete, third.scene.report.findings
    assert calls["load"] == calls["duplicate_object"] == calls["translate_object"] == 1
    assert calls["orient_for_print"] == 1


def test_the_nozzle_count_reaches_the_cached_arrangement() -> None:
    """Zwei Düsen legen zwei Filamente auf eine Platte — auch mit warmem Cache."""
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles as profile_table
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    for name in ("A", "B"):
        history.apply(
            name,
            [OperationDraft(op="create_box", params={"width": 30.0, "depth": 20.0, "height": 8.0})],
        )
    for object_id, colour in (("obj_1", "#ff0000"), ("obj_2", "#0000ff")):
        history.apply(
            "Filament",
            [
                OperationDraft(
                    op="assign_slot",
                    inputs=(object_id,),
                    params={"slot": 0, "name": colour, "colour": colour, "material_type": "PLA"},
                )
            ],
        )
    history.apply(
        "Anordnen",
        [OperationDraft(op="arrange_bed", inputs=("obj_1", "obj_2"), params={"by_material": True})],
    )
    one = profile_table.make_profile("centauri-carbon-2", "pla")
    two = dataclasses.replace(one, printer=dataclasses.replace(one.printer, nozzles=2))
    sources = ProjectSources(project)

    def plates(result) -> list[int]:
        assert result.complete, result.scene.report.findings
        return sorted(entry.plate for entry in result.scene.objects.values())

    cache = ResultCache()
    assert plates(evaluate(project.document, one, cache=cache, sources=sources)) == [0, 1]
    assert plates(evaluate(project.document, two, cache=None, sources=sources)) == [0, 0]
    assert plates(evaluate(project.document, two, cache=cache, sources=sources)) == [0, 0]


def test_a_calibrated_body_material_reaches_the_cached_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Körper in PETG bohrt nach dem Kalibrieren von PETG neu, im PLA-Projekt."""
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles as profile_table
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 30.0, "depth": 20.0, "height": 8.0})],
    )
    history.apply(
        "Material",
        [OperationDraft(op="set_material", inputs=("obj_1",), params={"material": "petg"})],
    )
    history.apply(
        "Bohren",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 4.0, "compensate": True},
            )
        ],
    )
    profile = profile_table.make_profile("centauri-carbon-2", "pla")
    sources = ProjectSources(project)

    def bore(result) -> float:
        assert result.complete, result.scene.report.findings
        body = result.scene.objects["obj_1"]
        return next(f for f in body.features.values() if f.kind == "hole").params["diameter"]

    cache = ResultCache()
    petg = profile_table.material("petg")
    before = bore(evaluate(project.document, profile, cache=cache, sources=sources))
    assert before == pytest.approx(5.0 + petg.hole_compensation, abs=1e-6)
    calibrated = dict(profile_table.material_profiles())
    calibrated["petg"] = dataclasses.replace(petg, hole_compensation=petg.hole_compensation + 0.4)
    monkeypatch.setattr(profile_table, "_materials", calibrated)
    cold = bore(evaluate(project.document, profile, cache=None, sources=sources))
    assert cold == pytest.approx(before + 0.4, abs=1e-6)
    assert bore(evaluate(project.document, profile, cache=cache, sources=sources)) == (
        pytest.approx(cold, abs=1e-9)
    )


def test_hashes_are_stable_and_short() -> None:
    assert digest("a", 1) == digest("a", 1)
    assert len(digest("a")) == 32
    assert object_hash("key", 0) != object_hash("key", 1)


@pytest.fixture(scope="module", params=("native", "mesh"))
def bound_faces(request):
    """Zwei wirkliche gegenüberliegende Quaderflächen unter bleibenden Namen."""
    from app.core.brep.edit import box
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect

    body = box(8.0, 6.0, 4.0)
    features = features_of(body) if request.param == "native" else detect(as_mesh_data(body))
    faces = [feature for feature in features.values() if feature.kind == "face"]
    top = next(feature for feature in faces if feature.params["normal"][2] > 0.99)
    bottom = next(feature for feature in faces if feature.params["normal"][2] < -0.99)
    assert top.params["centre"][2] == pytest.approx(4.0)
    assert bottom.params["centre"][2] == pytest.approx(0.0)
    assert set(top.face_indices).isdisjoint(bottom.face_indices)
    assert top.surface_patches and bottom.surface_patches
    return {
        "old_a": dataclasses.replace(top, id="old_a"),
        "old_b": dataclasses.replace(bottom, id="old_b"),
    }


def test_follow_hash_distinguishes_actual_claims_with_the_same_names(bound_faces) -> None:
    """Der gleiche Körper mit vertauschten Flächenansprüchen entwertet seine Folgeschritte."""
    before = object_hash("raw", 0, tuple(bound_faces), features=bound_faces)
    swapped = {
        "old_a": dataclasses.replace(bound_faces["old_b"], id="old_a"),
        "old_b": dataclasses.replace(bound_faces["old_a"], id="old_b"),
    }
    assert object_hash("raw", 0, tuple(swapped), features=swapped) != before
    assert object_hash("raw", 0, tuple(bound_faces), features={}) != before
    assert object_hash("raw", 0, features={}) == object_hash("raw", 0)


@pytest.mark.parametrize(
    "field",
    [
        "mapping_key",
        "id",
        "kind",
        "provenance",
        "params",
        "face_indices",
        "created_by",
        "recognised",
        "measure_sources",
        "patch_kind",
        "patch_params",
        "patch_indices",
        "patch_source",
    ],
)
def test_follow_hash_covers_geometry_carriers_sources_and_originators(bound_faces, field) -> None:
    """Maß, Originalauswahl und Quellen wirken unabhängig vom reservierten Namen."""
    import math

    feature = bound_faces["old_a"]
    patch = feature.surface_patches[0]
    changes = {
        "id": "another_name",
        "kind": "edge",
        "provenance": "generated",
        # Schon der nächste darstellbare Wert darf nicht weggerundet werden.
        "params": {**feature.params, "area": math.nextafter(feature.params["area"], math.inf)},
        "face_indices": bound_faces["old_b"].face_indices,
        "created_by": 17,
        "recognised": False,
        "measure_sources": {**feature.measure_sources, "area": "parameter"},
    }
    patch_changes = {
        "patch_kind": {"kind": "cylinder", "params": {**patch.params, "radius": 2.0}},
        "patch_params": {
            "params": {
                **patch.params,
                "centre": (*patch.params["centre"][:2], math.nextafter(4.0, math.inf)),
            }
        },
        "patch_indices": {"face_indices": patch.face_indices[:1]},
        "patch_source": {"source": "fit"},
    }
    changed = dict(bound_faces)
    if field == "mapping_key":
        changed["another_key"] = changed.pop("old_a")
    elif field in patch_changes:
        changed["old_a"] = dataclasses.replace(
            feature, surface_patches=(dataclasses.replace(patch, **patch_changes[field]),)
        )
    else:
        changed["old_a"] = dataclasses.replace(feature, **{field: changes[field]})
    reserved = tuple(bound_faces)
    assert object_hash("raw", 0, reserved, features=changed) != object_hash(
        "raw", 0, reserved, features=bound_faces
    )


def test_follow_hash_uses_the_same_full_codec_after_json_and_a_new_process(
    bound_faces, tmp_path: Path
) -> None:
    """JSON-Listen, Reihenfolge und Prozess-Hashseed ändern keine belegte Bindung."""
    import subprocess
    import sys

    from app.core.scene.cache import _feature_from_data, feature_to_data

    before = object_hash("raw", 0, tuple(bound_faces), features=bound_faces)
    data = {name: feature_to_data(feature) for name, feature in reversed(bound_faces.items())}
    revived = {
        name: _feature_from_data(value) for name, value in json.loads(json.dumps(data)).items()
    }
    assert object_hash("raw", 0, tuple(revived), features=revived) == before
    path = tmp_path / "features.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    script = """
import json
import sys
from pathlib import Path
from app.core.scene.cache import _feature_from_data
from app.core.scene.hashing import object_hash
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
features = {key: _feature_from_data(value) for key, value in data.items()}
print(object_hash("raw", 0, tuple(features), features=features))
"""
    child = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        cwd=Path(__file__).parents[1],
        env={**os.environ, "PYTHONHASHSEED": "23"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert child.stdout.strip() == before


@pytest.mark.parametrize("moment", ["before", "first_feature", "last_feature"])
def test_follow_hash_cancellation_keeps_the_existing_token(
    bound_faces, monkeypatch: pytest.MonkeyPatch, moment: str
) -> None:
    """Abbruch am Eingang und während echter Codecarbeit liefert keinen Teilhash."""
    from app.core.errors import OperationCancelled
    from app.core.scene import cache as cache_module
    from app.core.scene.cancel import CancelSignal

    token = CancelSignal()
    encode = cache_module.feature_to_data
    encoded = []

    def observed(feature):
        data = encode(feature)
        encoded.append(feature.id)
        if moment == "first_feature" or (moment == "last_feature" and len(encoded) == 2):
            token.cancel()
        return data

    monkeypatch.setattr(cache_module, "feature_to_data", observed)
    if moment == "before":
        token.cancel()
    with pytest.raises(OperationCancelled):
        object_hash("raw", 0, features=bound_faces, check_cancelled=token.raise_if_cancelled)
    assert len(encoded) == {"before": 0, "first_feature": 1, "last_feature": 2}[moment]


def test_the_raw_operation_hash_ignores_mapping_answers(profile: Profile) -> None:
    """Geometrie wird vor der Zuordnung gecacht; erst ihre Ausgabe bindet die Antwort."""
    original = Operation(id=1, op="resize_hole", inputs=("obj_1",), outputs=("obj_1",))
    answered = dataclasses.replace(original, matches={"legacy": {"hole_1": {"kind": "hole"}}})
    assert operation_hash(original, {}, ["body"], profile, "fine") == operation_hash(
        answered, {}, ["body"], profile, "fine"
    )


def test_the_disk_level_survives_a_new_process(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(make_object("obj_1", triangles=42),)))

    fresh = DiskCache(codec=FakeCodec(), directory=tmp_path)
    restored = fresh.get("key")
    assert restored is not None
    assert restored.objects[0].id == "obj_1"
    assert restored.objects[0].mesh.triangle_count == 42


def test_the_answers_of_a_step_survive_the_disk_and_a_damaged_one_is_dropped(
    tmp_path: Path,
) -> None:
    """§15.7: Die Antworten reisen mit dem Eintrag; eine falsche Gestalt ist ein
    beschädigter Eintrag und wird neu gerechnet, nicht halb gelesen."""
    answered = {"unit": "mm", "spot_x": 12.5, "spot_y": -3.0, "spot_plate": 2}
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(make_object("obj_1"),), answered=answered))

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")
    assert restored is not None and restored.answered == answered

    stored = disk._folder("key") / "objects.json"
    data = json.loads(stored.read_text(encoding="utf-8"))
    data["answered"] = [["unit", "mm"]]
    stored.write_text(json.dumps(data), encoding="utf-8")
    assert DiskCache(codec=FakeCodec(), directory=tmp_path).get("key") is None


def test_a_cache_entry_may_disappear_before_its_access_time_is_updated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", result(42))
    folder = disk._folder("key")

    def vanished(path: Path, _times: object = None) -> None:
        assert path == folder
        shutil.rmtree(path)
        raise FileNotFoundError("gezieltes Rennen mit der Cache-Bereinigung")

    monkeypatch.setattr(os, "utime", vanished)

    restored = disk.get("key")

    assert restored is not None
    assert restored.objects[0].mesh.triangle_count == 42
    assert not folder.exists(), "die LRU-Markierung darf keinen Datei-Knoten zurücklassen"


def test_the_memory_level_fills_itself_from_disk(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache = ResultCache(disk=disk)
    cache.put("key", result(), to_disk=True)
    cache.clear()

    assert cache.get("key") is not None
    assert cache.statistics.disk_hits == 1
    assert len(cache) == 1, "what came from disk stays in memory"


def test_a_damaged_entry_is_dropped_instead_of_raising(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", result())
    folder = next(path for path in tmp_path.rglob("objects.json"))
    folder.write_text("{not json", encoding="utf-8")

    assert disk.get("key") is None
    assert disk.get("key") is None, "the damaged entry was removed, not read again"


@pytest.mark.parametrize("damage", ["halved", "empty", "garbage", "json_shape"])
def test_a_damaged_mesh_beside_the_index_is_recomputed(
    tmp_path: Path, profile: Profile, damage: str
) -> None:
    """Ein verstümmeltes Netz im Plattencache kostet einen Neulauf, nie das Projekt.

    Gemessen vor 0.5.0: eine halbierte ``.npz`` warf ``BadZipFile`` durch
    ``evaluate`` hindurch, und das Projekt öffnete erst wieder, nachdem der
    Cacheordner von Hand gelöscht war.
    """
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 30.0, "depth": 20.0, "height": 8.0})],
    )
    directory = tmp_path / "cache"
    first = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    volume = (
        evaluate(project.document, profile, cache=first, sources=ProjectSources(project))
        .scene.objects["obj_1"]
        .mesh.volume
    )
    meshes = sorted(directory.rglob("*.npz"))
    assert meshes, "the box went to disk"
    for mesh in meshes:
        data = mesh.read_bytes()
        if damage == "halved":
            mesh.write_bytes(data[: len(data) // 2])
        elif damage == "empty":
            mesh.write_bytes(b"")
        elif damage == "garbage":
            mesh.write_bytes(b"PK\x03\x04" + bytes(range(256)) * 4)
        else:
            index = mesh.with_name("objects.json")
            payload = json.loads(index.read_text(encoding="utf-8"))
            payload["objects"] = {"not": "a list"}
            index.write_text(json.dumps(payload), encoding="utf-8")
    fresh = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    again = evaluate(project.document, profile, cache=fresh, sources=ProjectSources(project))
    assert again.complete
    assert again.scene.objects["obj_1"].mesh.volume == pytest.approx(volume)
    assert fresh.statistics.disk_hits == 0, "the damaged entry was not handed out"


def test_the_disk_budget_is_kept(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path, budget_bytes=1)
    disk.put("a" * 32, result(100, "obj_1"))
    disk.put("b" * 32, result(100, "obj_2"))
    assert disk.size_bytes() <= 400, "trimming drops the oldest entries"


def test_objects_keep_their_features_through_the_disk_level(tmp_path: Path) -> None:
    from app.core.types import Feature

    entry = SceneObject(
        id="obj_1",
        name="Halterung",
        mesh=FakeMesh(),  # type: ignore[arg-type]
        features={
            "hole_3": Feature(
                id="hole_3",
                kind="hole",
                provenance="detected",
                params={"diameter": 5.2},
                face_indices=(1, 2, 3),
            )
        },
    )
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(entry,)))

    restored = disk.get("key")
    assert restored is not None
    feature = restored.objects[0].features["hole_3"]
    assert feature.kind == "hole"
    assert feature.params["diameter"] == 5.2
    assert feature.face_indices == (1, 2, 3)


@pytest.mark.parametrize("reload", [False, True])
def test_measure_sources_survive_warm_and_persisted_results(tmp_path: Path, reload: bool) -> None:
    """Derselbe Wert bleibt nach einem Speicher- oder Plattentreffer als Fit erkennbar."""
    import trimesh

    from app.core.geom.mesh import MeshCodec, MeshData
    from app.core.types import Feature, measure_status

    feature = Feature(
        "bore",
        "hole",
        "generated",
        {"diameter": 8.02, "depth": 4.0},
        measure_sources={"diameter": "fit", "depth": "parameter"},
    )
    body = SceneObject(
        "obj_1", "Teil", MeshData.of(trimesh.creation.box()), features={"bore": feature}
    )
    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    cache = ResultCache(disk=disk)
    cache.put("measure", CachedResult(objects=(body,)), to_disk=True)
    if reload:
        cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path))
    revived = cache.get("measure")
    assert revived is not None
    found = revived.objects[0].features["bore"]
    assert found.params == {"diameter": 8.02, "depth": 4.0}
    assert found.measure_sources == {"diameter": "fit", "depth": "parameter"}
    assert measure_status(found, "diameter").state == "estimated"
    assert measure_status(found, "depth").source == "parameter"
    assert feature.measure_sources == {"diameter": "fit", "depth": "parameter"}


def test_old_results_without_fit_roles_are_recomputed(tmp_path: Path) -> None:
    """Ein alter Deckel-Cache darf die neue Innen-/Außenauskunft nicht verschlucken."""
    from app.core.types import Feature

    entry = make_object("obj_1")
    entry.features["rim"] = Feature(
        id="rim",
        kind="face",
        provenance="generated",
        params={"diameter": 24.0},
        face_indices=(0,),
    )
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("lid", CachedResult(objects=(entry,)))
    index = disk._folder("lid") / "objects.json"
    historical = json.loads(index.read_text(encoding="utf-8"))
    historical["format_version"] = 2
    index.write_text(json.dumps(historical), encoding="utf-8")

    assert disk.get("lid") is None, "the old output must not bypass the current producer"

    entry.features["rim"].params["fit_role"] = "outer"
    disk.put("lid", CachedResult(objects=(entry,)))
    restored = disk.get("lid")
    assert restored is not None
    assert restored.objects[0].features["rim"].params["fit_role"] == "outer"


def test_format_34_repair_results_are_not_reused_after_crossing_changes(
    tmp_path: Path,
) -> None:
    """Ein Reparaturergebnis aus dem alten Schnittstand wird verworfen (RM-253/RM-319)."""
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("repair", result())
    index = disk._folder("repair") / "objects.json"
    historical = json.loads(index.read_text(encoding="utf-8"))
    # Format 34 liegt vor der geänderten Schnitt- und Kontaktklassifikation.
    historical["format_version"] = 34
    index.write_text(json.dumps(historical), encoding="utf-8")
    cache = ResultCache(disk=disk)

    assert cache.get("repair") is None
    assert cache.statistics.disk_hits == 0
    assert cache.statistics.misses == 1


@pytest.mark.parametrize("previous_version", range(5, CACHE_FORMAT_VERSION))
def test_old_recognition_results_are_not_read_from_disk(
    tmp_path: Path, previous_version: int
) -> None:
    """Auch ein vorhandener Eintrag der letzten Erkennungsversion ist veraltet.

    Die Liste kommt aus ``CACHE_FORMAT_VERSION`` selbst: Von Hand geführt endete
    sie bei 18, während der Stand längst 22 war — der Docstring versprach die
    letzte Version, und geprüft wurde sie nicht.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("recognition", result())
    index = disk._folder("recognition") / "objects.json"
    historical = json.loads(index.read_text(encoding="utf-8"))
    historical["format_version"] = previous_version
    index.write_text(json.dumps(historical), encoding="utf-8")

    assert disk.get("recognition") is None


@pytest.mark.parametrize("reopen", [False, True], ids=["memory", "disk"])
@pytest.mark.parametrize("previous_version", [5, CACHE_FORMAT_VERSION - 1])
def test_recognition_revision_recomputes_a_warm_project_cache(
    tmp_path: Path,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
    reopen: bool,
    previous_version: int,
) -> None:
    """Neue Auskünfte entwerten beide Cacheebenen, nie die gespeicherten Operationen."""
    from copy import deepcopy

    import numpy as np
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene import cache as cache_module
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    corpus = Path(__file__).parent / "data" / "meshes" / "recognition_bayonet_lid.npz"
    with np.load(corpus) as data:
        mesh = trimesh.Trimesh(vertices=data["vertices"], faces=data["faces"], process=False)
    project.sources["src_1"] = mesh.export(file_type="stl")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/lid.stl", sha256=""
    )
    History(project.document).apply(
        "Laden und verschieben",
        [
            OperationDraft(
                op="load",
                params={"source": "src_1", "unit": "mm", "coordinates": "legacy_raw"},
            ),
            OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 12.0}),
        ],
    )
    operations = deepcopy(project.document.ops)
    sources = ProjectSources(project)
    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    cache = ResultCache(disk=disk)
    with monkeypatch.context() as historical:
        historical.setattr(cache_module, "CACHE_FORMAT_VERSION", previous_version)
        before = evaluate(project.document, profile, sources=sources, cache=cache)
        assert before.complete
        assert len(cache) == 2
    if reopen:
        cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path))
    misses_before = cache.statistics.misses

    after = evaluate(project.document, profile, sources=sources, cache=cache)

    assert after.complete
    assert cache.statistics.misses - misses_before == 2
    assert cache.statistics.hits == cache.statistics.disk_hits == 0
    assert project.document.ops == operations
    for name, entry in after.scene.objects.items():
        earlier = before.scene.objects[name]
        assert np.array_equal(entry.mesh.raw.vertices, earlier.mesh.raw.vertices)
        assert np.array_equal(entry.mesh.raw.faces, earlier.mesh.raw.faces)
        contacts = [
            feature
            for feature in entry.features.values()
            if feature.kind == "face"
            and abs(feature.params["area"] - 22.8) < 1e-4
            and np.allclose(feature.params["normal"], (0.0, 0.0, 1.0))
        ]
        assert len(contacts) == 3

    again = evaluate(project.document, profile, sources=sources, cache=cache)
    assert again.complete
    assert cache.statistics.hits == 2
    assert cache.statistics.misses - misses_before == 2
    assert again.scene.objects["obj_1"].features == after.scene.objects["obj_1"].features


def test_the_disk_cache_keeps_findings_solver_and_transform(tmp_path: Path) -> None:
    """Die drei Beifänge gehören zum Ergebnis wie die Körper selbst.

    `put` schrieb nur die Objekte, `get` baute ein kahles `CachedResult`:
    nach einem Platten-Treffer las `_with_features` die alten Merkmale ohne
    die gemeldete Bewegung im falschen Bezugspunkt (§21.2), und die
    Voxel-Warnung, die §17.2 nie stillschweigend lassen will, war weg.
    """
    from app.core.types import Finding, SolverInfo

    cache = DiskCache(codec=FakeCodec(), directory=tmp_path)
    moved = (
        (1.0, 0.0, 0.0, 12.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    cache.put(
        "key",
        CachedResult(
            objects=(make_object("obj_1"),),
            findings=(Finding(code="boolean.voxel", severity="warning", message="Voxelstufe."),),
            solver=SolverInfo(strategy="voxel"),
            transform=moved,
        ),
    )

    again = cache.get("key")

    assert again is not None
    assert [entry.code for entry in again.findings] == ["boolean.voxel"]
    assert again.solver is not None and again.solver.strategy == "voxel"
    assert again.transform == moved


def test_the_disk_cache_keeps_the_rim_of_a_closed_opening(tmp_path: Path) -> None:
    """``Finding.outline`` übersteht den Plattencache — sonst stufte ein warmer Cache
    *Stelle zeigen* still auf den Ring allein zurück.

    Die Projektdatei trägt den Rand nicht (``finding_to_data``), der Cache
    schon; ein Eintrag ohne Rand bleibt ohne.
    """
    from app.core.scene.serialise import finding_to_data
    from app.core.types import Finding

    rim = (((0.0, 0.0, 20.0), (20.0, 0.0, 20.0)), ((20.0, 0.0, 20.0), (0.0, 0.0, 20.0)))
    wide = Finding(
        code="repair.wide_hole_filled",
        severity="warning",
        message="Eine große Öffnung wurde mit einer neuen Fläche geschlossen.",
        location=(10.0, 0.0, 20.0),
        outline=rim,
    )
    assert "outline" not in finding_to_data(wide), "die Projektdatei behält ihr Format"
    cache = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache.put(
        "key",
        CachedResult(
            objects=(make_object("obj_1"),),
            findings=(wide, dataclasses.replace(wide, code="ohne", outline=())),
        ),
    )

    again = cache.get("key")

    assert again is not None
    assert again.findings[0].outline == rim
    assert again.findings[1].outline == ()


def test_the_disk_cache_keeps_the_bodies_a_pair_finding_names(tmp_path: Path) -> None:
    """``Finding.object_ids`` übersteht den Plattencache.

    Sonst spräche nach einem warmen Cache wieder ein entfernter Körper aus dem
    Bericht: Die Auswertung streicht einen Paarbefund über diese Liste (Fund
    N1 zum Review von ``bbd41ff2d``). Wie der Rand oben steht sie nicht in der
    Projektdatei; ein Befund ohne Liste bleibt ohne.
    """
    from app.core.scene.serialise import finding_to_data
    from app.core.types import Finding

    pair = Finding(
        code="arrange.collision",
        severity="warning",
        message="Zwei Objekte überschneiden sich.",
        object_id="obj_1",
        object_ids=("obj_1", "obj_2"),
    )
    assert "object_ids" not in finding_to_data(pair), "die Projektdatei behält ihr Format"
    cache = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache.put(
        "key",
        CachedResult(
            objects=(make_object("obj_1"),),
            findings=(pair, dataclasses.replace(pair, code="ohne", object_ids=())),
        ),
    )

    again = cache.get("key")

    assert again is not None
    assert again.findings[0].object_ids == ("obj_1", "obj_2")
    assert again.findings[1].object_ids == ()


def test_the_cache_survives_several_threads_writing_at_once() -> None:
    """Drei Fäden legen hier ab: Auswertung, Agent und Vorschau.

    ``_store`` ist kein einzelner Schritt, sondern vier — alten Eintrag
    herausnehmen, Kosten abziehen, neuen einhängen, verdrängen bis das Budget
    passt. Wechselt der Interpreter mittendrin den Faden, stimmt ``_cost``
    nicht mehr mit dem überein, was wirklich in der Liste liegt: Der Cache
    verdrängt dann zu früh (jeder Schritt wird neu gerechnet) oder gar nicht
    mehr (er wächst, bis der Speicher knapp wird).

    **Das Umschaltintervall ist der Kern dieses Tests, nicht Beiwerk.** Der
    erste Anlauf lief ohne es — und war damit wertlos: Mit dem üblichen
    Intervall von fünf Millisekunden trifft der Fadenwechsel praktisch nie in
    die vier Schritte hinein, und die Gegenprobe *ohne* Schloss lief null von
    fünf Mal auseinander. Ein Test, der auch ohne die geprüfte Sache grün ist,
    prüft nichts. Mit einer Mikrosekunde fällt dieselbe Gegenprobe zehnmal von
    zehn.
    """
    import sys
    import threading

    cache = ResultCache(triangle_budget=3_000)
    problems: list[BaseException] = []

    def work(start: int) -> None:
        try:
            for index in range(start, start + 200):
                cache.put(f"key-{index}", result(triangles=100))
                cache.get(f"key-{index - 1}")
        except BaseException as problem:  # pragma: no cover - nur im Fehlerfall
            problems.append(problem)

    before = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=work, args=(n * 10_000,)) for n in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(before)

    assert not problems, f"Ausnahme in einem Faden: {problems}"
    counted = sum(entry.cost for entry in cache._entries.values())
    assert cache.cost == counted, (
        f"Der Cache nennt {cache.cost}, in der Liste liegen {counted} — die Buchführung "
        "ist unter Nebenläufigkeit auseinandergelaufen."
    )
    assert cache.cost <= cache._budget or len(cache) == 1


# --- Die Plattenebene, angeschlossen ---------------------------------------------
#
# Sie war gebaut, getestet und in der Anwendung nicht verbunden: `DiskCache`
# stand, `MeshCodec` stand, `ResultCache` nahm sie als Argument — und
# `app/ui/session.py`, die einzige Stelle, an der die Anwendung einen Cache
# baut, übergab sie nicht. Jedes Öffnen eines Projekts rechnete den ganzen
# Stapel neu, obwohl §38 die Ebene verspricht und §31 ihr ein Ziel setzt.
#
# Die Tests hier prüfen die drei Dinge, die beim Anschließen entschieden werden
# mussten: dass der Weg trägt, dass der Cache nicht in fremden Ordnern räumt,
# und dass ein Eintrag ein Update nicht überlebt.


def test_the_factory_gives_a_cache_with_a_disk_level() -> None:
    """Der Bauer, den die Anwendung benutzt — mit Platte."""
    from app.core.scene import disk_backed_cache

    cache = disk_backed_cache()
    assert cache._disk is not None, "a cache without a disk level recomputes on every open"


def test_nothing_in_the_application_builds_a_cache_without_the_disk_level() -> None:
    """Der Test, der gefehlt hat — und er liest den Text, mit Absicht.

    Jeder Test hier drüber prüfte die Plattenebene für sich, und sie war in
    Ordnung. Niemand prüfte, ob die Anwendung sie benutzt: `app/ui/session.py`
    schrieb ``ResultCache()``, die Kommandozeile übergab gar keinen Cache, und
    kein Testfeld aus §35 deckt das ab — der Fehler saß nicht in einem Modul,
    sondern zwischen zwei.

    Deshalb strukturell und nicht funktional: Ein Test, der eine Sitzung baut
    und ihren Cache ansieht, prüft die eine Stelle, die er kennt. Dieser hier
    findet auch die dritte, die morgen dazukommt.
    """
    root = Path(__file__).parent.parent / "app"
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "cache.py":
            continue  # dort wohnt die Klasse und der Bauer mit seinem Rückfall
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "ResultCache(" in line and "disk=" not in line:
                offenders.append(f"{path.relative_to(root)}:{number}")
    assert not offenders, (
        "these build a result cache without a disk level, use disk_backed_cache(): "
        + ", ".join(offenders)
    )


def test_the_cache_folder_carries_the_application_version() -> None:
    """Ein Eintrag darf ein Update nicht überleben.

    Der Schlüssel ist der Operations-Hash, und der kennt Parameter, Profil und
    Qualität — nicht die *Umsetzung*. Eine behobene Boolesche Rückfallstufe
    hätte sonst ein altes Netz aus dem Cache bekommen.
    """
    from app.branding import APP_VERSION
    from app.core.paths import results_cache_dir, user_cache_dir

    folder = results_cache_dir()
    assert folder.name.startswith(APP_VERSION)
    assert folder.parent.parent == user_cache_dir(), "below the cache root, not beside it"


def test_the_cache_does_not_tidy_up_in_its_neighbours_folders(tmp_path: Path) -> None:
    """`trim` und `clear` dürfen nur den eigenen Ordner anfassen.

    Vorher stand `DiskCache.directory` per Vorgabe auf der Cache-**Wurzel**, und
    dort wohnen die heruntergeladenen Update-Pakete und
    der Stil-Cache. Ein `trim` hätte fremde Ordner gelöscht, um sein Budget zu
    halten, und `clear` hätte die Wurzel mitgenommen — samt einem Update-Paket,
    das gerade geprüft werden sollte.
    """
    from app.core.paths import ensure_dir

    root = tmp_path / "cache"
    stranger = ensure_dir(root / "updates" / "0.1.3")
    (stranger / "solidon-setup.exe").write_bytes(b"x" * 4096)
    own = ensure_dir(root / "results" / "0.1.2")

    disk = DiskCache(codec=FakeCodec(), directory=own, budget_bytes=1)
    disk.put("a" * 32, result(100, "obj_1"))
    disk.put("b" * 32, result(100, "obj_2"))
    disk.clear()

    assert (stranger / "solidon-setup.exe").is_file(), "the update package survived"


def test_an_older_version_folder_is_dropped(tmp_path: Path) -> None:
    """Der Preis der Versionsschranke, eingesammelt.

    Ohne diesen Schritt bliebe je Fassung ein toter Ordner liegen, der bis an
    das Budget gewachsen sein darf — das eigene Budget räumt ihn nie weg, es
    zählt nur den eigenen Ordner.
    """
    from app.core.paths import ensure_dir
    from app.core.scene import drop_other_versions

    results = tmp_path / "results"
    old = ensure_dir(results / "0.1.1")
    (old / "leftover").write_bytes(b"x")
    current = ensure_dir(results / "0.1.2")

    drop_other_versions(current)

    assert not old.exists(), "the folder of the previous version is gone"
    assert current.is_dir(), "the current one stays"
    assert results.is_dir(), "and nothing above it is touched"


def test_a_generated_feature_keeps_its_name_and_origin_through_the_disk(tmp_path: Path) -> None:
    """Ein erzeugtes Merkmal, einmal über die Platte — §21.2.

    Der Test darüber schickt ein **erkanntes** Merkmal und prüft die Maße; die
    Provenienz prüft er nicht. Sie ist aber der Teil, an dem §21.2 hängt: Ein
    erzeugtes Merkmal trägt den Namen der Operation, die es gemacht hat, und
    genau dieser Name ist es, worauf ein späterer Schritt sich beruft. Käme er
    als „detected" zurück, wäre die Kette still zerrissen.
    """
    from app.core.types import Feature

    entry = SceneObject(
        id="obj_1",
        name="Halterung",
        mesh=FakeMesh(),  # type: ignore[arg-type]
        features={
            "op3.pin_1": Feature(
                id="op3.pin_1",
                kind="pin",
                provenance="generated",
                params={"diameter": 3.0},
                face_indices=(4, 5),
            )
        },
    )
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(entry,)))

    restored = disk.get("key")
    assert restored is not None
    feature = restored.objects[0].features["op3.pin_1"]
    assert feature.id == "op3.pin_1"
    assert feature.provenance == "generated", "a generated feature must not come back as detected"
    assert feature.kind == "pin"


def test_the_budget_is_checked_without_walking_the_folder_every_time(tmp_path: Path) -> None:
    """Was geschrieben wurde, wird mitgezählt statt nachgezählt.

    `put` rief am Ende `trim`, und `trim` fragte zuerst über jede Datei im
    Ordner, wie groß er ist — gemessen 254 ms bei 2000 Einträgen, je
    geschriebenem Op-Ergebnis. Jetzt geht der Gang einmal je Prozess und danach
    erst wieder, wenn das Budget reißt.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path, budget_bytes=10_000_000)
    assert disk._known_bytes is None, "nothing counted before the first write"

    disk.put("a" * 32, result(100, "obj_1"))
    after_first = disk._known_bytes
    assert after_first is not None, "the first write counts the folder once"

    disk.put("b" * 32, result(100, "obj_2"))
    assert disk._known_bytes is not None
    assert disk._known_bytes > after_first, "the second write was added, not recounted"
    assert disk._known_bytes == disk.size_bytes(), "and the running total is right"


def test_an_own_part_that_changed_gets_a_folder_of_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein eigener Baustein ist eine Operation, die kein Update begleitet.

    Ändert der Nutzer ein Maß in seinem eigenen Baustein (§24.5), bleiben
    Op-Name und Parameter gleich, und der Operations-Hash sieht nichts. Im
    Speicher war das gleichgültig; auf der Platte hieße es, dass die eigene
    Änderung beim nächsten Öffnen verschwiegen wird — und gemeldet wird sie
    nicht, denn ``changed_since_library`` liest gepflegte Änderungsverläufe,
    und die pflegt beim Ausprobieren niemand.
    """
    from app.branding import APP_VERSION
    from app.core import paths

    parts = tmp_path / "parts"
    parts.mkdir()
    monkeypatch.setattr(paths, "user_parts_dir", lambda: parts)

    without = paths.results_cache_dir()

    own = parts / "magnet_pocket.py"
    own.write_text("# ein eigener Baustein", encoding="utf-8")
    with_part = paths.results_cache_dir()

    own.write_text("# dasselbe Maß, ein anderer Wert", encoding="utf-8")
    os.utime(own, (1_000_000, 1_000_000))
    after_change = paths.results_cache_dir()

    assert without != with_part, "an own part has to show in the folder"
    assert with_part != after_change, "and changing it has to change the folder again"
    assert after_change.name.startswith(APP_VERSION), "the version still leads"


def test_two_readers_and_writers_share_one_folder(tmp_path: Path) -> None:
    """Den Ordner teilen mehrere Prozesse, und zwar seit dem Anschluss.

    Vorher gab es genau einen möglichen Schreiber, weil es keinen gab. Jetzt
    schreiben die Oberfläche und die Kommandozeile in denselben Ordner, zwei
    Fenster erst recht — und wenn einer davon aufräumt, darf der andere nicht
    darüber fallen. Was er verliert, ist ein Eintrag; was er tut, ist neu
    rechnen.
    """
    surface = DiskCache(codec=FakeCodec(), directory=tmp_path)
    terminal = DiskCache(codec=FakeCodec(), directory=tmp_path)

    surface.put("a" * 32, result(100, "obj_1"))
    terminal.put("b" * 32, result(100, "obj_2"))

    assert surface.get("b" * 32) is not None, "each one reads what the other wrote"
    assert terminal.get("a" * 32) is not None

    # Ein dritter mit einem Budget, das nichts zulässt: er räumt alles weg.
    DiskCache(codec=FakeCodec(), directory=tmp_path, budget_bytes=1).trim()

    assert surface.get("a" * 32) is None, "gone is gone, and that is not an error"
    terminal.put("c" * 32, result(100, "obj_3"))
    assert terminal.get("c" * 32) is not None, "and writing goes on afterwards"


def test_a_changed_core_file_gets_a_folder_of_its_own() -> None:
    """Die Fassung im Pfad hält für den Kunden, nicht für den Arbeitsbaum.

    Zwischen zwei Starts wird hier eine Boolesche Rückfallstufe geändert und
    ``APP_VERSION`` bleibt „0.1.2". Ohne diese Schranke läge danach das Netz
    des alten Codes im Cache, und die Berichtigung wäre stillschweigend
    ausgehebelt — auf der einzigen Maschine, auf der Solidon heute läuft.
    """
    from app.core import paths

    before = paths.results_cache_dir()

    touched = Path(paths.__file__)
    state = touched.stat()
    # Absolut in die Zukunft und nicht relativ zu dieser Datei: Gefragt ist das
    # **Maximum** über den Kern, und eine andere Datei kann längst jünger sein
    # — wer gerade `cache.py` geschrieben hat, machte diesen Test sonst rot,
    # ohne dass etwas kaputt war.
    os.utime(touched, ns=(state.st_atime_ns, time.time_ns() + 10_000_000_000))
    try:
        after = paths.results_cache_dir()
    finally:
        os.utime(touched, ns=(state.st_atime_ns, state.st_mtime_ns))

    assert before != after, "a touched core file has to show in the folder"
    assert paths.results_cache_dir() == before, "and putting the time back puts it back"


def test_a_built_package_needs_no_source_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein gebautes Paket hat keine Quelldateien, die sich ändern könnten.

    Dort ist die Fassung die ganze Wahrheit, und ein Gang über einen Ordner,
    den es nicht gibt, wäre nur Arbeit ohne Aussage.
    """
    import sys

    from app.branding import APP_VERSION
    from app.core import paths

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert paths.results_cache_dir().name == APP_VERSION


def test_nobody_writes_into_the_shared_cache_root() -> None:
    """Die Wurzel des Cache-Ordners gehört niemandem allein.

    Dort wohnen die Update-Pakete, der Stil-Cache und die
    Ergebnisse — und jeder von ihnen räumt in seinem eigenen Unterordner auf.
    Der Ergebnis-Cache tat es einmal in der Wurzel, mit ``rmtree``; das ist
    behoben, aber die Regel dahinter stand nur in einem Docstring. Hier steht
    sie als Test: Wer ``user_cache_dir()`` benutzt, hängt einen Unterordner an.
    """
    root = Path(__file__).parent.parent / "app"
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "paths.py":
            continue  # dort wird die Wurzel definiert
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            bare = line.lstrip()
            if "user_cache_dir" not in line or bare.startswith(("#", "from ", "import ")):
                continue
            # Auf den Namen muss ``() /`` folgen. Ohne Klammern ist es die
            # Funktion selbst — genau so stand der Fehler in `DiskCache`:
            # ``field(default_factory=user_cache_dir)``. Ein Wächter, der nur
            # den Aufruf sucht, hätte ihn nicht gesehen.
            if not line.split("user_cache_dir", 1)[1].lstrip().startswith("() /"):
                offenders.append(f"{path.relative_to(root)}:{number}")
    assert not offenders, (
        "these take the shared cache root itself instead of a folder below it: "
        + ", ".join(offenders)
    )


def test_the_disk_level_holds_only_what_was_offered_to_it(tmp_path: Path) -> None:
    """Ablegen auf der Platte ist ein Verlangen, kein Nebeneffekt.

    Die Vorgabe steht auf ``False``, weil die Fehlerrichtungen verschieden
    schwer sind: Ein vergessenes ``to_disk=False`` gäbe über Sitzungen hinweg
    falsche Ergebnisse, ein vergessenes ``to_disk=True`` nur eine langsamere
    Anwendung. Dieser Test hält die Richtung fest.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache = ResultCache(disk=disk)

    cache.put("a" * 32, result(100, "obj_1"))
    assert disk.get("a" * 32) is None, "nothing lands on the disk unasked"
    assert cache.get("a" * 32) is not None, "but the memory level has it"

    cache.put("b" * 32, result(100, "obj_2"), to_disk=True)
    assert disk.get("b" * 32) is not None, "and what was offered is there"


def test_a_second_evaluation_comes_off_the_disk(tmp_path: Path, profile: Profile) -> None:
    """Zweimal auswerten, dazwischen den Speicher wegwerfen — §31, unter 1 s.

    Das ist der Weg, den die Anwendung beim Öffnen eines Projekts geht: ein
    frisches Fenster, ein leerer Speichercache, dieselbe Platte. Vorher wurde
    dabei der ganze Operationsstapel neu gerechnet.
    """
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "cube_clean.stl").read_bytes()
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )

    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    sources = ProjectSources(project)
    evaluate(project.document, profile, sources=sources, cache=ResultCache(disk=disk))

    second = ResultCache(disk=disk)
    result = evaluate(project.document, profile, sources=sources, cache=second)

    assert second.statistics.disk_hits == 1, "the reopened project came off the disk"
    assert second.statistics.misses == 0, "nothing was recomputed"
    assert len(result.scene.objects) == 1


def test_a_question_comes_back_when_the_project_is_reopened(
    tmp_path: Path, profile: Profile
) -> None:
    """Was aus einer Antwort entstand, gehört nicht auf die Platte (§15.7).

    `bracket_inch.stl` ist zwischen Zoll und Zentimeter mehrdeutig, die
    Eingangsstufe fragt also (§11.1). Die Antwort steht heute nirgends im
    Dokument — nicht in den Parametern der fragenden Operation —, also ist das
    Ergebnis **keine reine Funktion des Dokuments**, und genau das darf der
    Cache nicht über eine Sitzung hinaus behalten.

    Gemessen am 22.08.2026, bevor es diesen Test gab: erste Auswertung fragte
    einmal, zweite über die Platte fragte **nicht**. Der Nutzer hätte ein
    Projekt geöffnet und stillschweigend eine Annahme bekommen, wo eine Frage
    stand — und ob überhaupt gefragt wird, hätte das Dateisystem entschieden,
    denn eine Cache-Datei darf jederzeit gelöscht werden (§38). Regel 21 sagt
    „nie stillschweigend raten".

    **Dieser Test und ``test_a_second_evaluation_comes_off_the_disk`` halten
    sich gegenseitig ehrlich.** Der andere verlangt einen Treffer auf der
    Platte, dieser verlangt sein Ausbleiben — beide können nicht grün sein,
    wenn die Ebene gar nicht benutzt wird. Damit ist die Gegenfrage beantwortet,
    die man jedem Test stellen sollte: Was müsste kaputt sein, damit er rot
    wird? Bei einem Paar, das sich ausschließt, gibt es darauf keine bequeme
    Antwort. Wer einen von beiden ändert, muss den anderen ansehen.

    Der Test bleibt stehen, wenn §15.7 umgesetzt ist. Dann steht die Antwort in
    den Parametern, der Schlüssel kennt sie, und **deshalb** wird wieder
    gefragt, sobald sie fehlt — dieselbe Aussage, ein anderer Weg dorthin.
    """
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/bracket_inch.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "bracket_inch.stl").read_bytes()
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "auto"})]
    )

    asked: list[str] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(question)
        return choices[0]

    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    sources = ProjectSources(project)
    evaluate(project.document, profile, sources=sources, cache=ResultCache(disk=disk), ask=ask)
    assert len(asked) == 1, "the ambiguity reaches whoever can answer it"

    # Ein neues Fenster: leerer Speicher, dieselbe Platte.
    evaluate(project.document, profile, sources=sources, cache=ResultCache(disk=disk), ask=ask)
    assert len(asked) == 2, "and it reaches them again, because the answer is nowhere"


def test_every_caller_says_whether_the_result_may_go_to_disk() -> None:
    """Die Entscheidung muss dastehen, nicht aus einer Vorgabe folgen.

    Die Vorgabe von ``to_disk`` ist ``False``, damit ein Vergessen nur langsam
    macht und nicht falsch. Das schützt gegen das Vergessen — nicht gegen ein
    falsches ``True``, und dagegen kann kein Test schützen: „hängt von etwas ab,
    das nicht im Dokument steht" ist an einer Aufrufstelle nicht ablesbar.

    Was dieser Test leistet, ist weniger und trotzdem etwas: Er verlangt, dass
    jede Stelle die Entscheidung **hinschreibt**. Damit steht sie in jedem Diff,
    den jemand liest, statt in einer Vorgabe, an die niemand denkt. Aus einer
    Bitte wird eine Aussage, über die man streiten kann.

    Der eigentliche Ort für die andere Hälfte ist nicht der Cache: Eine
    Operation, die die Uhr liest oder eine Datei außerhalb des Projekts,
    verstößt gegen §11 und Regel 9, ganz unabhängig von jeder Cache-Ebene.
    """
    root = Path(__file__).parent.parent / "app"
    offenders = []
    queue_path = root / "ui" / "comfy_dialog.py"
    queue_lines: set[int] = set()
    queue_source = queue_path.read_text(encoding="utf-8").splitlines()
    queue_tree = ast.parse("\n".join(queue_source))
    for node in ast.walk(queue_tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "_probe_folder":
            continue
        results = next((argument for argument in node.args.args if argument.arg == "results"), None)
        if (
            results is None
            or results.annotation is None
            or ast.unparse(results.annotation) != "Queue[_FolderProbeResult]"
        ):
            continue
        queue_lines.update(
            number
            for number in range(node.lineno, node.end_lineno + 1)
            if "results.put(" in queue_source[number - 1]
        )
    for path in sorted(root.rglob("*.py")):
        if path.name == "cache.py":
            continue  # dort wohnt die Klasse, und `DiskCache.put` kennt kein Wort
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ".put(" not in line or "to_disk=" in line:
                continue
            if "sink.put(" in line or "feed.put(" in line or "_searches.put(" in line:
                # ``queue.Queue`` eines Pump-Fadens (comfy_setup._pump und
                # install._stream) und die Aufträge des Suchfadens der 3D-Maus
                # (spacemouse._SearchThread) — kein Cache, kennt kein ``to_disk``.
                # Kuratierte Ausnahme wie GERMAN_STEMS: Wer eine weitere
                # Warteschlange baut, trägt ihren Namen hier ein, und das
                # breite Netz bleibt gespannt.
                continue
            if path == queue_path and number in queue_lines and "results.put(" in line:
                # ``_probe_folder`` schickt ``Queue[_FolderProbeResult]`` an
                # den UI-Faden; das ist kein Schreibpfad in den Ergebniscache.
                continue
            offenders.append(f"{path.relative_to(root)}:{number}")
    assert not offenders, (
        "these put a result into the cache without saying whether it may be kept: "
        + ", ".join(offenders)
    )


def test_a_translatable_object_name_does_not_drop_the_whole_entry(tmp_path: Path) -> None:
    """Ein übersetzbarer Name ließ den Cache-Eintrag der ganzen Auswertung fallen.

    Seit Objektnamen aus dem Register kommen, ist ``SceneObject.name`` ein
    ``TranslatableText``. ``json.dumps`` kann den nicht ablegen, und der
    ``TypeError`` landete im ``except``-Zweig, der für nicht ablegbare
    B-Rep-Körper gedacht ist: Der Ordner wurde weggeräumt, das Protokoll bekam
    eine Zeile, und für den Kunden rechnete jedes konstruierte Projekt bei
    jeder Auswertung neu — ohne dass etwas falsch war, nur langsam.

    Dieser Test prüft **beides**: dass der Eintrag entsteht, und dass der Name
    seine Message-ID behält statt seiner Übersetzung.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    named = SceneObject(
        id="obj_1",
        name=TranslatableText("Quader"),
        mesh=FakeMesh(triangles=42),  # type: ignore[arg-type]
    )
    disk.put("key", CachedResult(objects=(named,)))

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")
    assert restored is not None, "der Eintrag fiel weg, statt geschrieben zu werden"
    assert restored.objects[0].name == TranslatableText("Quader")


def test_a_cached_name_is_stored_as_its_message_id(tmp_path: Path) -> None:
    """Nie die Übersetzung — die wechselt mit der Sprache, der Cache nicht.

    Läge der übersetzte Text in der Datei, bekäme der Kunde nach einem
    Sprachwechsel den alten Namen zurück: ein Fehler, den nur ein **warmer**
    Cache zeigt und den darum niemand beim Entwickeln sieht.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put(
        "key",
        CachedResult(
            objects=(
                SceneObject(
                    id="obj_1",
                    name=TranslatableText("Quader"),
                    mesh=FakeMesh(triangles=1),  # type: ignore[arg-type]
                ),
            )
        ),
    )

    written = json.loads(next(tmp_path.rglob("objects.json")).read_text(encoding="utf-8"))

    assert written["objects"][0]["name"] == {"msgid": "Quader", "context": None}


def test_a_translatable_slot_name_does_not_drop_the_whole_entry(tmp_path: Path) -> None:
    """Der Zwilling drei Tage später, an derselben Protokollzeile.

    Der Test darüber hält den **Objektnamen** fest. Am 26.08.2026 kam dieselbe
    Zeile aus einem Lauf von ``tools/make_web_images.py de`` — ``could not
    write cache entry …: Object of type TranslatableText is not JSON
    serializable`` —, diesmal aus ``app/examples/schild-zweifarbig.p3d`` und
    aus einem anderen Feld: dem Namen eines **Materialslots**. Der Weg dorthin
    ist derselbe wie beim Objektnamen: Das Beispiel vermerkt an ``assign_slot``,
    dass ``name`` eine Message-ID trägt (``Operation.translatable``, §4.1), die
    Auswertung macht daraus ein ``TranslatableText``, und die Operation reicht
    ihn unverändert in den Slot weiter.

    **Geprüft wird der Ordner, nicht der Rückgabewert.** ``DiskCache.put`` gibt
    nichts zurück und fängt den ``TypeError`` selbst ab: Es räumt den Ordner
    weg, schreibt eine Zeile ins Protokoll und kehrt zurück, als wäre nichts
    gewesen. Ein Test, der nur ``put`` aufruft, sähe den Fehler deshalb nie —
    genau daran lag es, dass er dreimal durchkam.

    Beide Namen stehen absichtlich in **einem** Objekt: Der Payload wird in
    einem Zug geschrieben, ein einziges nicht ablegbares Feld nimmt alle
    anderen mit.
    """
    from app.core.types import MaterialSlot

    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    named = SceneObject(
        id="obj_2",
        name=TranslatableText("Lettern"),
        mesh=FakeMesh(triangles=42),  # type: ignore[arg-type]
        material_slots=[
            MaterialSlot(
                index=1,
                name=TranslatableText("Weiß"),
                colour=(1.0, 1.0, 1.0),
                extra_colours=((0.0, 0.0, 1.0),),
            )
        ],
    )

    disk.put("key", CachedResult(objects=(named,)))

    written = list(tmp_path.rglob("objects.json"))
    assert written, "der Eintrag wurde weggeräumt, statt geschrieben zu werden"

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")
    assert restored is not None
    slot = restored.objects[0].material_slots[0]
    assert slot.name == TranslatableText("Weiß"), "der Slotname überlebt den Rundlauf"
    assert isinstance(slot.name, TranslatableText), "und zwar als Message-ID, nicht als Text"
    assert slot.colour == (1.0, 1.0, 1.0), "und die Farbe daneben ebenso"
    assert slot.extra_colours == ((0.0, 0.0, 1.0),), "und die zweite Farbe eines Mehrfarbfilaments"

    # In der Datei steht die ID, nicht ihre Übersetzung — sonst hieße der Slot
    # nach einem Sprachwechsel weiter „Weiß". Dasselbe prüft
    # ``test_a_cached_name_is_stored_as_its_message_id`` für den Objektnamen.
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["objects"][0]["material_slots"][0]["name"] == {"msgid": "Weiß", "context": None}


def test_every_field_of_a_cache_entry_survives_a_translatable_text(tmp_path: Path) -> None:
    """Der Wächter gegen den **nächsten** Zwilling, nicht gegen die zwei bekannten.

    Zweimal ist derselbe Fehler an einem anderen Feld desselben Payloads
    aufgetaucht, und beide Male hat ihn kein Test gefunden, sondern eine Zeile
    im Protokoll eines Laufs, der etwas ganz anderes wollte. Dieser Test füllt
    deshalb **jedes** Feld, das einen Text tragen kann, mit einem
    ``TranslatableText`` und verlangt, dass der Eintrag trotzdem entsteht:
    Objektname, Slotname, Befundtext und die Notiz des Lösers.

    Was dabei nicht in Frage kommt, steht ausdrücklich daneben — ``id``,
    ``kind``, ``provenance``, ``created_by``, ``visible``, ``plate``,
    ``index``, ``colour``, ``material``, ``face_indices`` und ``transform``
    sind Kennungen, Zahlen und Wahrheitswerte, und ``Feature.params`` trägt
    Maße. Wer dort einen Text unterbringt, hat ein anderes Problem als den
    Cache.

    Geprüft wird wieder am Ordner: ``put`` verschluckt den ``TypeError``.
    """
    from app.core.types import Feature, Finding, MaterialSlot, SolverInfo

    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    entry = SceneObject(
        id="obj_1",
        name=TranslatableText("Quader"),
        mesh=FakeMesh(triangles=7),  # type: ignore[arg-type]
        features={
            "hole_1": Feature(
                id="hole_1",
                kind="hole",
                provenance="generated",
                params={"diameter": 4.2},
                face_indices=(1, 2),
                created_by=3,
            )
        },
        material_slots=[MaterialSlot(index=0, name=TranslatableText("Körper"))],
    )

    disk.put(
        "key",
        CachedResult(
            objects=(entry,),
            findings=(
                Finding(
                    code="boolean.voxel",
                    severity="warning",
                    message=TranslatableText("Voxelstufe."),
                ),
            ),
            solver=SolverInfo(strategy="voxel", note=TranslatableText("Zurück vernetzt.")),
        ),
    )

    assert list(tmp_path.rglob("objects.json")), (
        "ein einziges nicht ablegbares Feld nimmt den ganzen Eintrag mit — "
        "und das Projekt rechnet danach bei jedem Öffnen neu"
    )

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")
    assert restored is not None
    assert restored.objects[0].name == TranslatableText("Quader")
    assert restored.objects[0].material_slots[0].name == TranslatableText("Körper")
    assert restored.findings[0].message == TranslatableText("Voxelstufe.")
    assert restored.solver is not None and restored.solver.strategy == "voxel"


def test_a_self_chosen_name_stays_a_plain_string(tmp_path: Path) -> None:
    """Was ein Nutzer selbst benannt hat, wird nicht übersetzt — und ein
    Eintrag aus einem älteren Cache, der die Unterscheidung noch nicht kannte,
    ist ebenfalls eine schlichte Zeichenkette und bleibt lesbar."""
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(make_object("obj_1", name="Meine Halterung"),)))

    restored = DiskCache(codec=FakeCodec(), directory=tmp_path).get("key")

    assert restored is not None
    assert restored.objects[0].name == "Meine Halterung"
    assert not isinstance(restored.objects[0].name, TranslatableText)


# --- Fremde Träger im Schlüssel (Gesamtreview-b, Szene 1 Rest) -------------------


def _face_carrier(object_id: str, face: str) -> SceneObject:
    from app.core.types import Feature

    return SceneObject(
        id=object_id,
        name=object_id,
        mesh=FakeMesh(),  # type: ignore[arg-type]
        features={
            face: Feature(id=face, kind="face", provenance="detected", params={}, face_indices=(1,))
        },
    )


def test_the_key_reads_the_carrier_of_a_named_feature() -> None:
    """``align_to_feature`` liest ein Ziel auf einem fremden Körper.

    ``operation_hash`` deckt die eigenen Eingänge — das benannte Merkmal
    steht aber auf einem fremden Körper, und dessen Hash stand nicht im
    Schlüssel: Platte um 40 mm verschoben, der ausgerichtete Körper blieb
    mit Cache an der alten Lage, und der Eintrag überlebte das Schließen
    (Gesamtreview-b, Bericht 01). Der Kontext trägt jetzt die Hashes
    **aller** Träger des Merkmals — alle, weil zwei Körper denselben
    Merkmalsnamen tragen können und der Schlüssel jede Lesart decken muss.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _with_nested_context

    params_class = REGISTRY.get("align_to_feature").params
    objects = {"obj_9": _face_carrier("obj_9", "face_a")}

    before = _with_nested_context(
        params_class, {"feature": "face_a"}, {}, None, objects, {"obj_9": "h1"}
    )
    after = _with_nested_context(
        params_class, {"feature": "face_a"}, {}, None, objects, {"obj_9": "h2"}
    )
    assert "#feature" in before, "der Träger gehört in den Kontext"
    assert before["#feature"] != after["#feature"], "sein Hash muss den Schlüssel ändern"

    empty = _with_nested_context(params_class, {"feature": ""}, {}, None, objects, {"obj_9": "h1"})
    assert "#feature" not in empty, "ohne benanntes Merkmal bleibt der Schlüssel, wie er war"


def test_the_key_reads_the_up_to_target_and_the_sketch_plane() -> None:
    """Dieselbe Blindstelle zweimal: ``up_to`` und die Skizzenebene.

    ``sketch_extrude`` mit ``up_to`` liest die Höhe eines fremden Körpers
    (Quader 10 → 30 mm: die Extrusion blieb mit Cache bei z = 10), und jede
    ``sketch_*``-Op liest die Lage ihrer ``feature:<id>``-Ebene. Beide
    Träger gehören in den Kontext, jeder unter seinem eigenen Namen.
    """
    import dataclasses

    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _with_nested_context
    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle

    params_class = REGISTRY.get("sketch_extrude").params
    drawn = sketch_to_text(dataclasses.replace(rectangle(10.0, 10.0), plane="feature:face_p"))
    resolved = {"up_to": "face_t", "sketch": drawn}
    objects = {
        "obj_a": _face_carrier("obj_a", "face_t"),
        "obj_b": _face_carrier("obj_b", "face_p"),
    }

    base = _with_nested_context(
        params_class, resolved, {}, None, objects, {"obj_a": "t1", "obj_b": "p1"}
    )
    taller = _with_nested_context(
        params_class, resolved, {}, None, objects, {"obj_a": "t2", "obj_b": "p1"}
    )
    moved = _with_nested_context(
        params_class, resolved, {}, None, objects, {"obj_a": "t1", "obj_b": "p2"}
    )

    assert base["#up_to"] != taller["#up_to"], "wächst der Körper unter up_to, kippt der Schlüssel"
    assert base["#sketch.plane"] != moved["#sketch.plane"], (
        "wandert die Trägerfläche der Skizze, kippt der Schlüssel"
    )
    assert base["#up_to"] == moved["#up_to"], "und die zwei Träger bleiben getrennte Einträge"


def test_the_key_reads_the_bodies_that_were_not_chosen() -> None:
    """Die vierte Lesart hängt an keinem Parameter — ``orient_for_print``.

    Sie dreht die gewählten Körper und ordnet sie danach an, ohne einen in
    einen **nicht gewählten** zu legen; den liest sie aus ``ctx.scene``. Kein
    Parameter benennt ihn, also fand ihn keiner der drei Zweige darüber, und
    ``operation_hash`` deckt nur die Eingänge: Verschiebt jemand den fremden
    Körper, blieb der Schlüssel derselbe und das alte Ergebnis galt weiter —
    der gedrehte wich einem Nachbarn aus, der längst woanders stand.

    Deklariert wird das am Register (``reads_other_bodies``), nicht an einem
    Feld: Gelesen wird die Szene als Ganzes.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _with_nested_context

    spec = REGISTRY.get("orient_for_print")
    assert spec.reads_other_bodies, "die Operation muss ihre Lesart deklarieren"

    values = {"thorough": False}
    before = _with_nested_context(
        spec.params,
        values,
        {},
        None,
        None,
        {"obj_1": "a1", "obj_2": "b1"},
        reads_other_bodies=True,
    )
    after = _with_nested_context(
        spec.params,
        values,
        {},
        None,
        None,
        {"obj_1": "a1", "obj_2": "b2"},
        reads_other_bodies=True,
    )
    assert "#scene" in before, "die Szene gehört in den Kontext"
    assert before["#scene"] != after["#scene"], (
        "wandert ein nicht gewählter Körper, muss der Schlüssel kippen"
    )

    # Und ohne die Deklaration bleibt der Schlüssel, wie er war: Eine
    # Operation, die nur ihre Eingänge liest, soll nicht bei jeder fremden
    # Änderung neu rechnen.
    quiet = _with_nested_context(spec.params, values, {}, None, None, {"obj_1": "a1"})
    assert "#scene" not in quiet, "wer die Szene nicht liest, hängt nicht an ihr"


def _scene_reading_switches() -> list[tuple[str, str]]:
    """Jeder Schalter mit ``reads_scene`` im Register — samt Untergrenze."""
    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY

    found = [
        (spec.name, field.name)
        for spec in REGISTRY.all()
        for field in spec.params.spec()
        if field.reads_scene
    ]
    assert {
        ("load", "free_spot"),
        ("load_step", "free_spot"),
        ("fit_to_size", "free_spot"),
    } <= set(found), found
    return found


@pytest.mark.parametrize(("op", "switch"), _scene_reading_switches())
def test_a_step_hangs_on_the_scene_only_until_it_has_found_its_spot(op: str, switch: str) -> None:
    """Wer die Szene liest (``reads_scene``), hängt mit dem Schlüssel an ihr —
    aber nur, solange er sucht (Review F4, Entscheidung Robert zu F1).

    Mit dem Schalter und ohne festgehaltene Stelle gehört jeder Körper davor in
    den Schlüssel; steht die Stelle im Schritt (``answered_by``) oder ist der
    Schalter aus — jeder Schritt, der vor Format 38 gespeichert wurde —, bleibt
    der Schlüssel, wie er war: Ein schwerer Import rechnet nicht neu, weil davor
    etwas anderes geändert wurde. Gefahren über alle Schalter im Register.
    """
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _with_nested_context

    spec = REGISTRY.get(op)
    field = next(entry for entry in spec.params.spec() if entry.name == switch)
    assert field.answered_by, "wer die Szene liest, hält fest, was er fand"
    looking = {switch: True}
    before = _with_nested_context(spec.params, looking, {}, None, None, {"obj_1": "a1"})
    after = _with_nested_context(spec.params, looking, {}, None, None, {"obj_1": "a2"})
    assert before["#scene"] != after["#scene"], "wandert der erste Körper, kippt der Schlüssel"

    settled = {switch: True, **dict.fromkeys(field.answered_by, 12.5)}
    for values in ({switch: False}, {}, settled):
        quiet = _with_nested_context(spec.params, values, {}, None, None, {"obj_1": "a1"})
        assert "#scene" not in quiet, values


def test_an_exact_sketch_plane_hashes_only_its_named_body() -> None:
    """Eine gleichnamige Fläche eines anderen Körpers ist keine Abhängigkeit.

    Ohne die Objektkennung im Cache-Kontext würde jede Änderung am falschen
    Körper die Skizzenoperation neu rechnen. Schlimmer wäre der umgekehrte
    Fehler: den tatsächlich gewählten Träger nicht zu berücksichtigen.
    """
    import dataclasses

    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _with_nested_context
    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle

    params_class = REGISTRY.get("sketch_extrude").params
    drawn = sketch_to_text(dataclasses.replace(rectangle(10.0, 10.0), plane="feature:obj_b:face_p"))
    objects = {
        "obj_a": _face_carrier("obj_a", "face_p"),
        "obj_b": _face_carrier("obj_b", "face_p"),
    }

    base = _with_nested_context(
        params_class, {"sketch": drawn}, {}, None, objects, {"obj_a": "a1", "obj_b": "b1"}
    )
    unrelated = _with_nested_context(
        params_class, {"sketch": drawn}, {}, None, objects, {"obj_a": "a2", "obj_b": "b1"}
    )
    carrier = _with_nested_context(
        params_class, {"sketch": drawn}, {}, None, objects, {"obj_a": "a1", "obj_b": "b2"}
    )

    assert base["#sketch.plane"] == unrelated["#sketch.plane"]
    assert base["#sketch.plane"] != carrier["#sketch.plane"]


class _RefusingCodec(FakeCodec):
    """Ein Codec, der diesen einen Körper nicht ablegen mag — wie der echte
    einen exakten Körper (§30)."""

    def stores(self, mesh: Mesh) -> bool:
        return False


def test_a_body_the_codec_will_not_store_is_no_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Der gewollte Fall darf nicht aussehen wie der ungewollte.

    ``put`` fing bis zum 27.08.2026 einen ``TypeError`` und schrieb
    ``could not write cache entry`` — für **zwei** Ursachen, die Gegenteiliges
    meinen: ein B-Rep-Ergebnis, das absichtlich neu gerechnet wird (§30), und
    ein Wert im Payload, den ``json.dumps`` nicht kennt. Der zweite ist ein
    Fehler und hat zweimal Tage gekostet, weil die Zeile im Protokoll dieselbe
    war. Im Kundenprotokoll vom 27.08.2026 (S-20260826-72a4dd) steht sie
    ebenfalls, hinter einem STEP-Import — dort war sie harmlos, und das sah man
    ihr nicht an.

    Seitdem fragt ``put`` vorher (``codec.stores``). Der gewollte Fall erreicht
    den Fehlerpfad nicht mehr, und die Warnung ist wieder eine.
    """
    disk = DiskCache(codec=_RefusingCodec(), directory=tmp_path)

    with caplog.at_level(logging.DEBUG, logger="app.core.scene.cache"):
        disk.put("key", CachedResult(objects=(make_object("obj_1", triangles=42),)))

    assert disk.get("key") is None, "abgelehnt heißt: nichts liegt da"
    warnungen = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert not warnungen, (
        "ein Körper, den der Codec bewusst nicht ablegt, ist Normalbetrieb — "
        f"keine Warnung: {[record.getMessage() for record in warnungen]}"
    )
    assert caplog.records, "und trotzdem nachlesbar, warum nichts gecacht wurde"


def test_a_payload_the_json_writer_cannot_take_stays_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Die Gegenprobe: Der **ungewollte** Fall bleibt eine Warnung.

    Sonst hätte die Trennung oben den Fehler mitgenommen, den sie sichtbar
    machen soll — ein Eintrag, der still wegfällt, während das Projekt bei
    jedem Öffnen den ganzen Stapel neu rechnet.
    """
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    entry = make_object("obj_1", triangles=42)
    # Ein Wert, den ``json.dumps`` nicht kennt — dieselbe Sorte wie die zwei
    # ``TranslatableText`` von 23. und 26.08.2026, nur ohne deren Reparatur.
    broken = dataclasses.replace(entry, material=object())  # type: ignore[arg-type]

    with caplog.at_level(logging.DEBUG, logger="app.core.scene.cache"):
        disk.put("key", CachedResult(objects=(broken,)))

    assert disk.get("key") is None
    assert [record for record in caplog.records if record.levelno >= logging.WARNING], (
        "ein Payload, den der JSON-Schreiber nicht nimmt, ist ein Fehler und "
        "muss als Warnung stehen bleiben"
    )


def test_the_key_reads_the_target_of_align_to_feature() -> None:
    """Gesamtreview 05.09.2026, CORE-13: ``align_to_feature`` liest sein Ziel
    über ``params.target`` — als ``obj_2:hole_1`` aus der ganzen Szene. Das
    Feld trug weder ``kind="feature"`` noch ``targets_feature``; der
    Schlüssel sah nur ``feature`` auf dem bewegten Körper, und ein
    verschobenes Ziel ließ den Stift mit Cache an der alten Stelle.

    Ein qualifiziertes Ziel zählt genau seinen Träger — zwei Körper mit
    ``hole_1`` sind zwei Lesarten, und ``obj_2:hole_1`` meint eine davon.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import _with_nested_context

    params_class = REGISTRY.get("align_to_feature").params
    resolved = {"feature": "pin_1", "target": "obj_2:hole_1"}
    objects = {"obj_1": _face_carrier("obj_1", "pin_1"), "obj_2": _face_carrier("obj_2", "hole_1")}

    before = _with_nested_context(
        params_class, resolved, {}, None, objects, {"obj_1": "a", "obj_2": "h1"}
    )
    after = _with_nested_context(
        params_class, resolved, {}, None, objects, {"obj_1": "a", "obj_2": "h2"}
    )
    assert "#target" in before, "der Träger des Ziels gehört in den Kontext"
    assert before["#target"] != after["#target"], "sein Hash muss den Schlüssel ändern"

    twins = {"obj_1": _face_carrier("obj_1", "hole_1"), "obj_2": _face_carrier("obj_2", "hole_1")}
    qualified = _with_nested_context(
        params_class, resolved, {}, None, twins, {"obj_1": "x", "obj_2": "y"}
    )
    assert qualified["#target"] == ("y",), "obj_2:hole_1 meint obj_2 und nicht jeden mit hole_1"

    malformed = _with_nested_context(
        params_class, {"feature": "pin_1", "target": ":"}, {}, None, objects, {"obj_2": "h1"}
    )
    assert "#target" not in malformed, "ein unbrauchbares Ziel kippt keinen Schlüssel"


def test_the_key_reads_the_content_of_every_source_bearing_parameter() -> None:
    """Gesamtreview 05.09.2026, CORE-11: Nur ``kind="source"`` kam mit seiner
    Inhaltsprüfsumme in den Schlüssel. ``displace_image`` liest sein Bild als
    ``kind="image"`` — und jedes Projekt nennt sein erstes Bild ``src_1``:
    Zwei Projekte mit verschiedenen Bildern bekamen aus dem Plattencache
    dasselbe Relief, mit ``complete=True``.

    Geprüft über das Register, nicht über eine Liste hier: Jede Operation,
    die eine Quelle nennt, gleich welcher Art, trägt deren Inhalt im Schlüssel.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import SOURCE_KINDS, _with_nested_context

    class Sources:
        def __init__(self, content: str) -> None:
            self.content = content

        def identity(self, source_id: str) -> str:
            return f"{self.content}:{source_id}"

        def describe(self, source_id: str) -> SimpleNamespace:
            return SimpleNamespace(path="teil.stl")

    covered: list[tuple[str, str, str]] = []
    for spec in REGISTRY.all():
        for entry in spec.params.spec():
            if entry.kind not in SOURCE_KINDS:
                continue
            resolved = {entry.name: "src_1"}
            first = _with_nested_context(spec.params, resolved, {}, Sources("a"), None, None)  # type: ignore[arg-type]
            second = _with_nested_context(spec.params, resolved, {}, Sources("b"), None, None)  # type: ignore[arg-type]
            key = f"#{entry.name}"
            assert key in first, f"{spec.name}.{entry.name} ({entry.kind}) fehlt im Schlüssel"
            assert first[key] != second[key], f"{spec.name}.{entry.name}: der Inhalt zählt nicht"
            covered.append((spec.name, entry.name, entry.kind))

    assert ("displace_image", "source", "image") in covered, "das Relief liest ein Bild"
    assert ("load", "source", "source") in covered
    assert len(covered) >= 4, covered


def test_the_key_reads_the_file_name_of_every_source_bearing_parameter() -> None:
    """Durchsicht v0.5.1: Der Schlüssel las von einer Quelle nur den Inhalt.
    ``load`` liest aber auch ihren Namen — der Körper heißt wie die Datei, und
    die Endung wählt den Leser. Dieselben Bytes unter einem zweiten Namen kamen
    aus dem Plattencache mit dem Namen des ersten zurück, über Projekte und
    Sitzungen hinweg: ``cube_clean.stl`` hieß im Baum „deckel", weil ein
    anderer Prozess dieselben Bytes als ``deckel.stl`` eingelesen hatte.

    Der Pfad selbst gehört nicht hinein, nur der Name: Ein Projektordner, der
    umzieht, soll seine gerechneten Schritte behalten."""
    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY
    from app.core.scene.evaluate import SOURCE_KINDS, _with_nested_context

    class Sources:
        def __init__(self, path: str) -> None:
            self.path = path

        def identity(self, source_id: str) -> str:
            return "dieselben Bytes"

        def describe(self, source_id: str) -> SimpleNamespace:
            return SimpleNamespace(path=self.path)

    def key(params_class: Any, name: str, path: str) -> Mapping[str, Any]:
        return _with_nested_context(params_class, {name: "src_1"}, {}, Sources(path), None, None)  # type: ignore[arg-type]

    covered: list[str] = []
    for spec in REGISTRY.all():
        for entry in spec.params.spec():
            if entry.kind not in SOURCE_KINDS:
                continue
            lid = key(spec.params, entry.name, "modelle/deckel.stl")
            assert lid != key(spec.params, entry.name, "modelle/cube_clean.stl"), (
                f"{spec.name}.{entry.name}: ein anderer Name, derselbe Schlüssel"
            )
            assert lid != key(spec.params, entry.name, "modelle/deckel.obj"), (
                f"{spec.name}.{entry.name}: eine andere Endung wählt einen anderen Leser"
            )
            assert lid == key(spec.params, entry.name, "umgezogen/deckel.stl"), (
                f"{spec.name}.{entry.name}: ein umgezogener Ordner verliert seinen Cache"
            )
            covered.append(spec.name)

    assert "load" in covered, covered


def test_a_failing_cache_folder_does_not_take_the_result_with_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, CORE-10: Die Ordneranlage stand vor dem
    OSError-Fang in ``DiskCache.put``. Eine volle Platte beim Anlegen des
    Unterordners warf die rohe Ausnahme durch ``evaluate`` — und mit ihr das
    fertig gerechnete Ergebnis. Der Cache ist eine Beilage, kein Vertrag."""
    import errno

    from app.core.scene import cache as cache_module

    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)

    def full(path: Path) -> Path:
        raise OSError(errno.ENOSPC, "No space left on device", str(path))

    monkeypatch.setattr(cache_module, "ensure_dir", full)

    disk.put("key", CachedResult(objects=(make_object("obj_1", triangles=42),)))  # wirft nicht

    assert disk.get("key") is None, "abgelegt wurde nichts — und das ist die ganze Folge"


def test_disk_results_come_back_with_warm_figures(tmp_path: Path) -> None:
    """Volumen, Fläche, Dichtheit und Teilezahl sind nach dem Lesen von der Platte
    schon gerechnet — im Arbeiter, nicht erst im Fenster. An ``dense_1m.stl``
    kostete das zweite Öffnen sonst 1,5 Sekunden im Hauptthread (Review,
    21.09.2026)."""
    import trimesh

    from app.core.geom.mesh import MeshCodec, MeshData

    body = SceneObject("obj_1", "Teil", MeshData.of(trimesh.creation.box()))
    disk = DiskCache(codec=MeshCodec(), directory=tmp_path)
    disk.put("figures", CachedResult(objects=(body,)))
    fresh = disk.get("figures")
    assert fresh is not None
    figures = fresh.objects[0].mesh.raw._cache
    for name in ("solidon_volume", "area", "is_watertight", "solidon_component_count"):
        assert name in figures, f"{name} must already be known when the window asks"


@pytest.mark.parametrize("op", ("split_pinned", "split_line"))
def test_split_cache_recalculates_old_single_cut_translation(
    profile: Profile, tmp_path: Path, op: str
) -> None:
    """Ein alter einzelner Schnitt liest keinen inzwischen entfernten Textschlüssel."""
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.registry import REGISTRY, Registry
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project
    from app.i18n import _, get_language, set_language, tr
    from app.i18n.catalog import install_language

    class RecordingCache(ResultCache):
        def __init__(self, disk: DiskCache) -> None:
            super().__init__(disk=disk)
            self.published: dict[str, CachedResult] = {}

        def put(self, key: str, result: CachedResult, *, to_disk: bool = False) -> None:
            self.published[key] = result
            super().put(key, result, to_disk=to_disk)

    def split_results(cache: RecordingCache) -> list[tuple[str, CachedResult]]:
        return [
            (key, result)
            for key, result in cache.published.items()
            if any(finding.code == "prepare.halves_in_place" for finding in result.findings)
        ]

    load_operations()
    old_registry = Registry()
    for spec in REGISTRY.all():
        old_registry.register(
            dataclasses.replace(spec, cache_version="2") if spec.name == op else spec
        )
    project = new_project()
    assert isinstance(project.document.printer, str)
    assert isinstance(project.document.material, str)
    history = History(project.document)
    history.apply(
        _("Quader"),
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 10.0, "height": 10.0})],
    )
    history.apply(
        _("Teilen"),
        [OperationDraft(op=op, inputs=("obj_1",), params={"pins": 0, "position": 5.0})],
    )
    directory = tmp_path / "schnitt-cache"
    original = RecordingCache(DiskCache(codec=MeshCodec(), directory=directory))
    previous = get_language()
    install_language("fr")
    set_language("fr")
    try:
        before = evaluate(project.document, profile, registry=old_registry, cache=original)
        assert before.stopped_at is None
        old_entries = split_results(original)
        assert len(old_entries) == 1, "der echte Schnitt wurde auf die Platte gelegt"
        old_key, old_result = old_entries[0]
        old_text = _(
            "Die zwei Hälften liegen im Modell noch aneinander. Zum Drucken nebeneinander legen."
        )
        legacy = dataclasses.replace(
            old_result,
            findings=tuple(
                dataclasses.replace(finding, message=old_text)
                if finding.code == "prepare.halves_in_place"
                else finding
                for finding in old_result.findings
            ),
        )
        disk = DiskCache(codec=MeshCodec(), directory=directory)
        disk.put(old_key, legacy)
        restored = DiskCache(codec=MeshCodec(), directory=directory).get(old_key)
        assert restored is not None
        old_messages = [
            finding.message
            for finding in restored.findings
            if finding.code == "prepare.halves_in_place"
        ]
        assert old_messages == [old_text], "der wirkliche Altcache trägt die alte Message-ID"
        assert str(old_messages[0]) == old_text.msgid, (
            "der entfernte Schlüssel fällt auf Deutsch zurück"
        )

        fresh = RecordingCache(DiskCache(codec=MeshCodec(), directory=directory))
        after = evaluate(project.document, profile, cache=fresh)
        assert after.stopped_at is None
        messages = [
            str(finding.message)
            for finding in after.scene.report.findings
            if finding.code == "prepare.halves_in_place"
        ]
        expected = tr(
            "Die zwei Hälften liegen im Modell noch aneinander. Zum Drucken nebeneinanderlegen."
        )
        assert messages == [expected], "der öffentliche warme Ladeweg bleibt französisch"
        new_entries = split_results(fresh)
        assert len(new_entries) == 1, "der alte Schnitt wurde wirklich neu gerechnet"
        assert new_entries[0][0] != old_key, (
            "die aktuelle Op-Version verwendet einen anderen Schlüssel"
        )
        assert fresh.statistics.disk_hits > 0, (
            "der übrige unveränderte Aufbau bleibt im Plattencache"
        )
        assert sum(body.mesh.volume for body in after.scene.objects.values()) == pytest.approx(
            2000.0
        )

        warm = RecordingCache(DiskCache(codec=MeshCodec(), directory=directory))
        repeated = evaluate(project.document, profile, cache=warm)
        assert repeated.stopped_at is None
        assert not split_results(warm), "der neue Schnitt kommt beim nächsten Öffnen aus dem Cache"
        assert warm.statistics.disk_hits >= 2
        assert [
            str(finding.message)
            for finding in repeated.scene.report.findings
            if finding.code == "prepare.halves_in_place"
        ] == [expected]
    finally:
        set_language(previous)


def test_whether_a_step_asked_for_the_quality_survives_the_disk(tmp_path: Path) -> None:
    """RM-494: Ein Treffer von der Platte meldet, ob der Schritt nach der Güte fragte.

    Ohne Angabe gilt sie als gefragt — ein alter Eintrag rechnet den Export
    lieber einmal fein nach, als eine Entwurfsdatei zu schreiben.
    """
    import trimesh

    from app.core.geom.mesh import MeshCodec, MeshData

    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    body = SceneObject(id="obj_1", name="Quader", mesh=MeshData.of(trimesh.creation.box()))
    cache.put("ohne", CachedResult(objects=(body,), reads_quality=False), to_disk=True)
    cache.put("mit", CachedResult(objects=(body,)), to_disk=True)

    cold = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    without, asked = cold.get("ohne"), cold.get("mit")

    assert without is not None and without.reads_quality is False
    assert asked is not None and asked.reads_quality is True


@pytest.mark.parametrize("creator", ["create_box", "create_brep_box"])
def test_object_frame_survives_symmetric_body_edit_copy_undo_and_reopening(
    profile: Profile, tmp_path: Path, creator: str
) -> None:
    """Die Achsen stammen vom Verlauf, auch am symmetrischen Würfel (RM-401)."""
    import numpy as np

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.geom.transform import rotation, translation
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, load, new_project, save
    from app.core.types import IDENTITY_FRAME
    from tests.helpers import exact_kernel

    if creator == "create_brep_box":
        exact_kernel()
    load_operations()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Würfel",
        [
            OperationDraft(
                op=creator,
                params={
                    "width": 10.0,
                    "depth": 10.0,
                    "height": 10.0,
                },
            )
        ],
    )
    directory = tmp_path / "cache"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))

    def run(current=project, active_cache=cache):
        result = evaluate(
            current.document, profile, sources=ProjectSources(current), cache=active_cache
        )
        assert result.complete, result.scene.report.findings
        return result.scene.objects

    assert run()["obj_1"].frame == IDENTITY_FRAME
    for axis, angle in (("z", 90.0), ("x", 37.0)):
        history.apply(
            "Drehen",
            [
                OperationDraft(
                    op="rotate_object",
                    inputs=("obj_1",),
                    params={"axis": axis, "angle": angle, "about": "origin"},
                )
            ],
        )
    expected = rotation("x", 37.0) @ rotation("z", 90.0)
    turned = run()["obj_1"]
    assert np.asarray(turned.frame) == pytest.approx(expected)
    # Ein Geometrieumbau behält die Ausgangsachsen.
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object", inputs=("obj_1",), params={"wall": 1.0, "open_top": False}
            )
        ],
    )
    assert np.asarray(run()["obj_1"].frame) == pytest.approx(expected)
    history.apply(
        "Kopien",
        [
            OperationDraft(
                op="pattern",
                inputs=("obj_1",),
                params={"kind": "linear", "count": 2, "spacing": 30.0},
            )
        ],
    )
    frames = {key: np.asarray(body.frame) for key, body in run().items()}
    assert frames["obj_1"] == pytest.approx(expected)
    assert frames["obj_2"] == pytest.approx(translation((30.0, 0.0, 0.0)) @ expected)
    assert history.undo() is not None
    assert tuple(run()) == ("obj_1",)
    assert np.asarray(run()["obj_1"].frame) == pytest.approx(expected)
    assert history.redo() is not None
    assert np.asarray(run()["obj_2"].frame) == pytest.approx(frames["obj_2"])
    reopened = load(save(project, tmp_path / "bezugsrahmen.p3d"))
    for active_cache in (
        ResultCache(),
        ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory)),
    ):
        reopened_objects = run(reopened, active_cache)
        for key, frame in frames.items():
            assert np.asarray(reopened_objects[key].frame) == pytest.approx(frame)


def test_object_frame_is_part_of_the_following_hash_and_disk_record(tmp_path: Path) -> None:
    """Gleiche Geometrie mit verschiedenen Ausgangsachsen hat verschiedene Folgeeingaben."""
    from app.core.types import IDENTITY_FRAME

    body = dataclasses.replace(make_object("obj_1"), frame=IDENTITY_FRAME)
    moved = (
        (0.0, -1.0, 0.0, 12.0),
        (1.0, 0.0, 0.0, 3.0),
        (0.0, 0.0, 1.0, -2.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    assert object_hash("same", 0, frame=body.frame) != object_hash("same", 0, frame=moved)
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("frame", CachedResult(objects=(dataclasses.replace(body, frame=moved),)))
    restored = disk.get("frame")
    assert restored is not None and restored.objects[0].frame == moved


@pytest.mark.parametrize("filename", ["drilled_v6.p3d", "circle_v18.p3d", "cut_away_face_v41.p3d"])
def test_old_projects_reconstruct_the_starting_frame(profile: Profile, filename: str) -> None:
    """Bestehende Projekte brauchen keine geratenen Formachsen oder neuen gespeicherten Werte."""
    from app.core.bootstrap import load_operations
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources, load
    from app.core.types import IDENTITY_FRAME

    load_operations()
    project = load(Path(__file__).parent / "data" / "projects" / filename)
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, result.scene.report.findings
    assert result.scene.objects
    assert all(body.frame == IDENTITY_FRAME for body in result.scene.objects.values())


@pytest.mark.parametrize("creator", ["create_box", "create_brep_box"])
@pytest.mark.parametrize("reverse", [False, True])
def test_union_uses_the_frame_of_the_first_stored_input(
    profile: Profile, creator: str, reverse: bool
) -> None:
    """Vereinigung bindet ihren Rahmen an die gespeicherte Auswahlfolge, nie an Form oder dict."""
    import numpy as np

    from app.core.bootstrap import load_operations
    from app.core.geom.transform import rotation
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import IDENTITY_FRAME
    from tests.helpers import exact_kernel

    if creator == "create_brep_box":
        exact_kernel()
    load_operations()
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    for title in ("Erster Würfel", "Zweiter Würfel"):
        history.apply(
            title,
            [
                OperationDraft(
                    op=creator,
                    params={
                        "width": 10.0,
                        "depth": 10.0,
                        "height": 10.0,
                    },
                )
            ],
        )
    history.apply(
        "Drehen",
        [
            OperationDraft(
                op="rotate_object",
                inputs=("obj_2",),
                params={"axis": "z", "angle": 90.0, "about": "origin"},
            )
        ],
    )
    selected = ("obj_2", "obj_1") if reverse else ("obj_1", "obj_2")
    history.apply("Vereinigen", [OperationDraft(op="union_objects", inputs=selected)])
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, result.scene.report.findings
    (combined,) = result.scene.objects.values()
    assert combined.mesh.volume == pytest.approx(1000.0)
    expected = rotation("z", 90.0) if reverse else IDENTITY_FRAME
    assert np.asarray(combined.frame) == pytest.approx(np.asarray(expected))


@pytest.mark.parametrize("exact", [False, True])
def test_affine_frame_keeps_scaling_reflection_and_an_unknown_origin(exact: bool) -> None:
    """Eine Spiegelung bleibt am Rahmen eine Spiegelung; unbekannt bleibt unbekannt."""
    import numpy as np
    import trimesh

    from app.core.brep import edit
    from app.core.geom.mesh import MeshData
    from app.core.geom.transform import moved_object, rotation, scaling
    from app.core.types import IDENTITY_FRAME
    from tests.helpers import exact_kernel

    if exact:
        exact_kernel()
    mesh = edit.box(10.0, 10.0, 10.0) if exact else MeshData.of(trimesh.creation.box((10, 10, 10)))
    body = SceneObject(id="obj_1", name="Würfel", mesh=mesh, frame=IDENTITY_FRAME)
    matrix = rotation("z", 37.0) @ scaling((-2.0, 2.0, 2.0))
    moved = moved_object(body, matrix)
    assert np.asarray(moved.frame) == pytest.approx(matrix)
    assert np.linalg.det(np.asarray(moved.frame)[:3, :3]) == pytest.approx(-8.0)
    assert moved_object(dataclasses.replace(body, frame=None), matrix).frame is None


def _counted_set(count: int, name: str = "face") -> dict[str, Any]:
    """Ein Merkmalssatz mit großen und kleinen Behältern und einem geteilten Kleinteil."""
    from app.core.types import Feature

    shared_axis = (0.0, 0.0, 1.0)
    found: dict[str, Any] = {}
    for index in range(count):
        found[f"{name}_{index}"] = Feature(
            id=f"{name}_{index}",
            kind="hole" if index % 2 else "face",
            provenance="detected",
            params={"centre": (float(index), 0.0, 0.0), "axis": shared_axis, "diameter": 4.0},
            face_indices=tuple(range(index * 400, index * 400 + (300 if index % 3 else 7))),
        )
    return found


@pytest.mark.parametrize("count", [3, 40, 600])
def test_a_set_of_the_same_features_is_counted_like_a_fresh_walk(count: int) -> None:
    """Derselbe Rest und dieselben Behälter wie ``held_parts``, ohne die Merkmale zu durchlaufen.

    Ein Schritt, der die Merkmale durchreicht, gibt einen neuen Satz aus
    denselben Merkmalsobjekten aus (RM-636); gezählt werden darf er wie neu.
    """
    from app.core import memory
    from app.core.scene import cache as cache_module

    first = _counted_set(count)
    counted: dict[int, Any] = {}
    cache_module._counted_features(first, counted)
    second = dict(first)
    turned = {name: first[name] for name in reversed(list(first))}
    third = dict(first)
    third[next(iter(third))] = dataclasses.replace(next(iter(third.values())), kind="slot")
    walked: list[int] = []
    real = memory.held_parts

    def watched(*args: Any, **kwargs: Any) -> Any:
        walked.append(1)
        return real(*args, **kwargs)

    for fresh in (second, turned, third, {**first, "extra_0": next(iter(first.values()))}):
        expected = real(fresh)
        walked.clear()
        memory.held_parts = watched  # type: ignore[assignment]
        try:
            found = cache_module._counted_features(fresh, counted)
        finally:
            memory.held_parts = real  # type: ignore[assignment]
        assert found[0] is fresh
        assert found[1] == expected[0]
        assert found[2].keys() == expected[1].keys()
        for key, (holder, size) in found[2].items():
            assert holder is expected[1][key][0] and size == expected[1][key][1]
        if fresh is second and count >= 40:
            assert not walked, "the same features are not walked again"


@pytest.mark.parametrize(
    "value",
    [
        [],
        [[1.0] * 4] * 4,
        [
            [1.0, 0.0, 0.0, float("nan")],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
    ],
)
def test_damaged_object_frame_is_never_used_from_disk(tmp_path: Path, value) -> None:
    """Ein beschädigter Rahmen erzwingt Neuberechnung statt geratener Winkel."""
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("frame", CachedResult(objects=(make_object("obj_1"),)))
    path = next(tmp_path.rglob("objects.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["objects"][0]["frame"] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    assert disk.get("frame") is None
