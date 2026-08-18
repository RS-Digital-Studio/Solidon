"""Der Ergebnis-Cache über dem Operations-Hash (Bauplan §15, §38).

Zwei Ebenen. Im Speicher ein LRU-Ablage, begrenzt über die Dreieckszahl —
denn die ist es, die den Rechner wirklich füllt. Auf der Platte dieselben
Ergebnisse unter demselben Hash, damit das Wiederöffnen eines Projekts nicht
den ganzen Stapel neu rechnet (§31: unter einer Sekunde aus dem
Platten-Cache).

Geschrieben wird der Cache nur nach einem vollständigen Lauf (§15.6) — ein
abgebrochener darf keinen halben Stapel hinterlassen.

Ein Netz zu serialisieren braucht den Geometriekern, den der Kern nicht
importiert. Die Plattenebene nimmt darum einen :class:`MeshCodec` von außen;
ohne ihn bleibt sie abgeschaltet, und es gibt nur die Speicherebene.
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
from app.core.scene.serialise import (
    finding_from_data,
    finding_to_data,
    solver_from_data,
    solver_to_data,
)
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

#: Grobe Obergrenze im Speicher. Eine Million Dreiecke ist das
#: Viewport-Ziel (§31).
DEFAULT_TRIANGLE_BUDGET: Final = 20_000_000

#: Obergrenze des Platten-Caches; die ältesten Einträge gehen zuerst.
DEFAULT_DISK_BUDGET_BYTES: Final = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CachedResult:
    """Was eine Operation erzeugt hat, bereit zum erneuten Herausgeben."""

    objects: tuple[SceneObject, ...]
    findings: tuple[Finding, ...] = ()
    solver: SolverInfo | None = None
    transform: Transform | None = None
    """Beim Ergebnis aufgehoben: eine Operation aus dem Cache muss dieselbe
    Bewegung melden wie beim ersten Mal, sonst überlebten die Bezeichner nur
    einen kalten Lauf."""

    @property
    def cost(self) -> int:
        """Dreiecke dieses Eintrags — das Maß, in dem das Budget zählt."""
        return sum(entry.mesh.triangle_count for entry in self.objects)


class MeshCodec(Protocol):
    """Macht aus einem Netz Bytes und zurück. Liefert die Geometrieschicht."""

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
    """Die Speicherebene, wahlweise mit Plattenebene dahinter."""

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


# --- Plattenebene ----------------------------------------------------------------


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
    """Ergebnisse auf der Platte, benannt nach dem Operations-Hash (§38)."""

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
                    material=entry.get("material"),
                    created_by=entry["created_by"],
                    visible=entry["visible"],
                    plate=entry.get("plate", 0),
                )
                for entry in data["objects"]
            )
            # Die drei Beifänge gehören zum Ergebnis wie die Körper selbst:
            # ohne `transform` liest `_with_features` die alten Merkmale im
            # falschen Bezugspunkt und benennt sie um (§21.2), ohne
            # `findings` verschwindet die Voxel-Warnung, die §17.2 nie
            # stillschweigend lassen will. Sie wurden geschrieben — nur
            # gelesen hat sie niemand.
            findings = tuple(finding_from_data(entry) for entry in data.get("findings", []))
            solver = solver_from_data(data.get("solver"))
            raw_transform = data.get("transform")
            transform: Transform | None = (
                tuple(tuple(float(value) for value in row) for row in raw_transform)  # type: ignore[assignment]
                if raw_transform
                else None
            )
        except (OSError, KeyError, ValueError) as problem:
            # Ein beschädigter Cache-Eintrag ist nie fatal: verwerfen und
            # neu rechnen.
            _log.warning("dropping unreadable cache entry %s: %s", key, problem)
            shutil.rmtree(folder, ignore_errors=True)
            return None
        folder.touch(exist_ok=True)
        return CachedResult(objects=objects, findings=findings, solver=solver, transform=transform)

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
                        "material": entry.material,
                        "created_by": entry.created_by,
                        "visible": entry.visible,
                        "plate": entry.plate,
                    }
                )
            payload: dict[str, Any] = {"objects": entries}
            if result.findings:
                payload["findings"] = [finding_to_data(entry) for entry in result.findings]
            if result.solver is not None:
                payload["solver"] = solver_to_data(result.solver)
            if result.transform is not None:
                payload["transform"] = [list(row) for row in result.transform]
            (folder / "objects.json").write_text(json.dumps(payload), encoding="utf-8")
        except (OSError, TypeError) as problem:
            # TypeError heißt: ein Körper, den der Codec nicht ablegen kann —
            # ein B-Rep-Ergebnis (§30). Die werden neu gerechnet statt
            # gecacht: den Cache gibt es für teure Boolesche Arbeit auf großen
            # Netzen, und eine Verrundung auf einem exakten Körper sind
            # Millisekunden.
            _log.warning("could not write cache entry %s: %s", key, problem)
            shutil.rmtree(folder, ignore_errors=True)
            return
        self.trim()

    def size_bytes(self) -> int:
        if not self.directory.is_dir():
            return 0
        return sum(path.stat().st_size for path in self.directory.rglob("*") if path.is_file())

    def trim(self) -> None:
        """Wirft die am längsten unbenutzten Einträge, bis das Budget stimmt."""
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
