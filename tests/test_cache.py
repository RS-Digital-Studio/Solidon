"""Ergebniscache über den Op-Hash (Bauplan §15, §38)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.scene.cache import CachedResult, DiskCache, ResultCache
from app.core.scene.hashing import digest, object_hash, operation_hash, profile_key
from app.core.types import Mesh, Operation, Profile, SceneObject
from tests.conftest import FakeMesh, make_object


class FakeCodec:
    """Steht für die Geometrieschicht, die den echten später liefert."""

    suffix = ".json"

    def dumps(self, mesh: Mesh) -> bytes:
        source = mesh  # type: ignore[assignment]
        return json.dumps(
            {
                "triangles": source.triangle_count,
                "vertices": source.vertex_count,
                "size": list(source.bounds.size),
            }
        ).encode("utf-8")

    def loads(self, data: bytes) -> Mesh:
        values = json.loads(data)
        return FakeMesh(  # type: ignore[return-value]
            triangles=values["triangles"],
            vertices=values["vertices"],
            size=tuple(values["size"]),
        )


def result(triangles: int = 100, object_id: str = "obj_1") -> CachedResult:
    return CachedResult(objects=(make_object(object_id, triangles=triangles),))


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


def test_the_hash_covers_everything_a_result_depends_on(profile: Profile) -> None:
    operation = Operation(id=1, op="resize_object", inputs=("obj_1",), outputs=("obj_1",))
    base = operation_hash(operation, {"size": 5.0}, ["h1"], profile, "fine")

    assert base == operation_hash(operation, {"size": 5.0}, ["h1"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.1}, ["h1"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.0}, ["h2"], profile, "fine")
    assert base != operation_hash(operation, {"size": 5.0}, ["h1"], profile, "draft")
    assert base != operation_hash(
        Operation(id=1, op="resize_object", seed=1), {"size": 5.0}, ["h1"], profile, "fine"
    )


def test_the_profile_enters_the_hash(profile: Profile) -> None:
    from app.core.knowledge import profiles as profile_table

    other = profile_table.make_profile("centauri-carbon-2", "asa")
    assert profile_key(profile) != profile_key(other)


def test_hashes_are_stable_and_short() -> None:
    assert digest("a", 1) == digest("a", 1)
    assert len(digest("a")) == 32
    assert object_hash("key", 0) != object_hash("key", 1)


def test_the_disk_level_survives_a_new_process(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    disk.put("key", CachedResult(objects=(make_object("obj_1", triangles=42),)))

    fresh = DiskCache(codec=FakeCodec(), directory=tmp_path)
    restored = fresh.get("key")
    assert restored is not None
    assert restored.objects[0].id == "obj_1"
    assert restored.objects[0].mesh.triangle_count == 42


def test_the_memory_level_fills_itself_from_disk(tmp_path: Path) -> None:
    disk = DiskCache(codec=FakeCodec(), directory=tmp_path)
    cache = ResultCache(disk=disk)
    cache.put("key", result())
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
