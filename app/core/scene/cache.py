"""Result cache over the operation hash (Bauplan §15, §38).

Two levels. In memory, a least-recently-used store bounded by triangle count,
because that is what actually fills the machine. On disk, the same results keyed
by the same hash, so reopening a project does not recompute the whole stack
(§31: under a second from the disk cache).

The cache is written only after a complete run (§15.6) — a cancelled run must
not leave half a stack behind.

Serialising a mesh needs the geometry kernel, which the core does not import.
The disk level therefore takes a :class:`MeshCodec` from outside; without one it
stays switched off and only the memory level is used.
"""

from __future__ import annotations

import json
import shutil
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Protocol

from app.core.log import get_logger
from app.core.paths import ensure_dir, user_cache_dir
from app.core.types import (
    Feature,
    Finding,
    MaterialSlot,
    Mesh,
    SceneObject,
    SolverInfo,
    Transform,
)

_log = get_logger(__name__)

#: Rough upper bound in memory. A million triangles is the viewport target (§31).
DEFAULT_TRIANGLE_BUDGET: Final = 20_000_000

#: Upper bound of the disk cache; the oldest entries go first.
DEFAULT_DISK_BUDGET_BYTES: Final = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CachedResult:
    """What an operation produced, ready to be handed out again."""

    objects: tuple[SceneObject, ...]
    findings: tuple[Finding, ...] = ()
    solver: SolverInfo | None = None
    transform: Transform | None = None
    """Kept with the result: a cached operation has to report the same motion it
    reported the first time, or the identifiers would only survive a cold run."""

    @property
    def cost(self) -> int:
        """Triangles held by this entry — the measure the budget counts in."""
        return sum(entry.mesh.triangle_count for entry in self.objects)


class MeshCodec(Protocol):
    """Turns a mesh into bytes and back. Supplied by the geometry layer."""

    @property
    def suffix(self) -> str: ...

    def dumps(self, mesh: Mesh) -> bytes: ...

    def loads(self, data: bytes) -> Mesh: ...


@dataclass(slots=True)
class CacheStatistics:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    disk_hits: int = 0


class ResultCache:
    """Memory level, optionally backed by a disk level."""

    def __init__(
        self,
        triangle_budget: int = DEFAULT_TRIANGLE_BUDGET,
        disk: DiskCache | None = None,
    ) -> None:
        self._entries: OrderedDict[str, CachedResult] = OrderedDict()
        self._cost = 0
        self._budget = triangle_budget
        self._disk = disk
        self.statistics = CacheStatistics()

    def get(self, key: str) -> CachedResult | None:
        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)
            self.statistics.hits += 1
            return entry
        if self._disk is not None:
            from_disk = self._disk.get(key)
            if from_disk is not None:
                self.statistics.disk_hits += 1
                self._store(key, from_disk)
                return from_disk
        self.statistics.misses += 1
        return None

    def put(self, key: str, result: CachedResult) -> None:
        self._store(key, result)
        if self._disk is not None:
            self._disk.put(key, result)

    def _store(self, key: str, result: CachedResult) -> None:
        if key in self._entries:
            self._cost -= self._entries.pop(key).cost
        self._entries[key] = result
        self._cost += result.cost
        while self._cost > self._budget and len(self._entries) > 1:
            _, dropped = self._entries.popitem(last=False)
            self._cost -= dropped.cost
            self.statistics.evictions += 1

    def clear(self) -> None:
        self._entries.clear()
        self._cost = 0

    @property
    def cost(self) -> int:
        return self._cost

    def __len__(self) -> int:
        return len(self._entries)


# --- Disk level ----------------------------------------------------------------


def _feature_to_data(feature: Feature) -> dict[str, Any]:
    return {
        "id": feature.id,
        "kind": feature.kind,
        "provenance": feature.provenance,
        "params": dict(feature.params),
        "face_indices": list(feature.face_indices),
    }


def _feature_from_data(data: dict[str, Any]) -> Feature:
    return Feature(
        id=data["id"],
        kind=data["kind"],
        provenance=data["provenance"],
        params=data["params"],
        face_indices=tuple(data["face_indices"]),
    )


def _slot_to_data(slot: MaterialSlot) -> dict[str, Any]:
    return {
        "index": slot.index,
        "name": slot.name,
        "colour": list(slot.colour) if slot.colour else None,
        "material": slot.material,
    }


def _slot_from_data(data: dict[str, Any]) -> MaterialSlot:
    colour = data.get("colour")
    return MaterialSlot(
        index=data["index"],
        name=data["name"],
        colour=(colour[0], colour[1], colour[2]) if colour else None,
        material=data.get("material"),
    )


@dataclass(slots=True)
class DiskCache:
    """Results on disk, named by the operation hash (§38)."""

    codec: MeshCodec
    directory: Path = field(default_factory=user_cache_dir)
    budget_bytes: int = DEFAULT_DISK_BUDGET_BYTES

    def _folder(self, key: str) -> Path:
        return self.directory / key[:2] / key

    def get(self, key: str) -> CachedResult | None:
        folder = self._folder(key)
        index = folder / "objects.json"
        if not index.is_file():
            return None
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
            objects = tuple(
                SceneObject(
                    id=entry["id"],
                    name=entry["name"],
                    mesh=self.codec.loads((folder / entry["mesh"]).read_bytes()),
                    kind=entry["kind"],
                    features={
                        key_: _feature_from_data(value) for key_, value in entry["features"].items()
                    },
                    material_slots=[_slot_from_data(slot) for slot in entry["material_slots"]],
                    created_by=entry["created_by"],
                    visible=entry["visible"],
                )
                for entry in data["objects"]
            )
        except (OSError, KeyError, ValueError) as problem:
            # A damaged cache entry is never fatal: drop it and recompute.
            _log.warning("dropping unreadable cache entry %s: %s", key, problem)
            shutil.rmtree(folder, ignore_errors=True)
            return None
        folder.touch(exist_ok=True)
        return CachedResult(objects=objects)

    def put(self, key: str, result: CachedResult) -> None:
        folder = ensure_dir(self._folder(key))
        entries: list[dict[str, Any]] = []
        try:
            for position, entry in enumerate(result.objects):
                name = f"{position}{self.codec.suffix}"
                (folder / name).write_bytes(self.codec.dumps(entry.mesh))
                entries.append(
                    {
                        "id": entry.id,
                        "name": entry.name,
                        "mesh": name,
                        "kind": entry.kind,
                        "features": {
                            key_: _feature_to_data(value) for key_, value in entry.features.items()
                        },
                        "material_slots": [_slot_to_data(slot) for slot in entry.material_slots],
                        "created_by": entry.created_by,
                        "visible": entry.visible,
                    }
                )
            (folder / "objects.json").write_text(json.dumps({"objects": entries}), encoding="utf-8")
        except OSError as problem:
            _log.warning("could not write cache entry %s: %s", key, problem)
            shutil.rmtree(folder, ignore_errors=True)
            return
        self.trim()

    def size_bytes(self) -> int:
        if not self.directory.is_dir():
            return 0
        return sum(path.stat().st_size for path in self.directory.rglob("*") if path.is_file())

    def trim(self) -> None:
        """Drop the least recently used entries until the budget is met."""
        if self.size_bytes() <= self.budget_bytes:
            return
        folders = sorted(
            (path for path in self.directory.glob("*/*") if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
        )
        for folder in folders:
            shutil.rmtree(folder, ignore_errors=True)
            if self.size_bytes() <= self.budget_bytes:
                return

    def clear(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)
