"""Der Abdruck einer Erkennung Bit für Bit — gemeinsam für k41 und k50 (ohne Nebenwirkung beim Import)."""

from __future__ import annotations

import hashlib

import numpy as np


def fingerprint(features) -> list[str]:
    """Je Merkmal Name, Art, Abdruck der Dreiecke, Teilträger und jedes Maß als Hexwert."""
    rows = []
    for feature in features.values():
        params = []
        for key in sorted(feature.params):
            value = feature.params[key]
            if isinstance(value, float):
                params.append((key, value.hex()))
            elif isinstance(value, (list, tuple)) and all(isinstance(i, (int, float)) for i in value):
                params.append((key, tuple(float(i).hex() for i in value)))
            elif isinstance(value, (bool, int, str)):
                params.append((key, value))
        chosen = np.asarray(sorted(feature.face_indices), dtype=np.int64).tobytes()
        patches = tuple(
            sorted(
                (
                    patch.kind,
                    hashlib.blake2b(
                        np.asarray(sorted(patch.face_indices), dtype=np.int64).tobytes(), digest_size=6
                    ).hexdigest(),
                    repr(tuple((k, patch.params[k]) for k in sorted(patch.params))),
                )
                for patch in feature.surface_patches
            )
        )
        rows.append(
            repr(
                (
                    feature.id,
                    feature.kind,
                    hashlib.blake2b(chosen, digest_size=8).hexdigest(),
                    patches,
                    tuple(params),
                )
            )
        )
    return sorted(rows)
