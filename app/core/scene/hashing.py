"""Stable hashes for the evaluation cache (Bauplan §15, §38).

The hash of an operation covers everything its result depends on: the operation
itself, its resolved parameters, the hashes of its inputs, profile, quality
level and seed. Two consequences fall out of that:

* changing one parameter only invalidates the branch below it — the rest comes
  from the cache, which is what keeps a parameter change under two seconds (§31);
* the hash is stable across processes, so it can name a file in the disk cache.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.types import Operation, Profile, Quality


def _canonical(value: Any) -> Any:
    """Turn a value into something json can write down the same way every time."""
    if isinstance(value, float):
        # repr keeps full double precision; rounding here would merge distinct runs.
        return ["f", repr(value)]
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, str | bytes):
        return value.decode() if isinstance(value, bytes) else value
    if isinstance(value, Sequence):
        return [_canonical(entry) for entry in value]
    return value


def digest(*parts: Any) -> str:
    """A short, stable hash over anything json can represent."""
    text = json.dumps([_canonical(part) for part in parts], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def profile_key(profile: Profile) -> str:
    """What of a profile can change a result: tolerances and nozzle geometry."""
    printer = profile.printer
    material = profile.material
    return digest(
        printer.id,
        printer.nozzle_diameter,
        printer.layer_height,
        printer.extrusion_width,
        printer.build_volume,
        material.id,
        material.clearance,
        material.press,
        material.hole_compensation,
        material.elephant_foot,
        material.shrinkage,
    )


def operation_hash(
    operation: Operation,
    params: Mapping[str, Any],
    input_hashes: Sequence[str],
    profile: Profile,
    quality: Quality,
) -> str:
    """Identity of one computed result."""
    return digest(
        operation.op,
        params,
        list(input_hashes),
        profile_key(profile),
        quality,
        operation.seed,
    )


def object_hash(operation_key: str, position: int) -> str:
    """Identity of one output object of an operation."""
    return digest(operation_key, position)


def source_hash(sha256: str) -> str:
    """Identity of an imported mesh — its checksum is already stable (§16.1)."""
    return digest("source", sha256)
