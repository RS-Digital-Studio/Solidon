"""Messbank A5 (RM-592): die kalte Erkennung der Paket-L-Modelle, CPU und Abdruck.

Aufruf::

    python kalt.py <baum> <ausgabe.jsonl> <modell> [<modell> ...]

Je Modell: lesen und normalisieren (3MF je Körper), je Körper ``forget_cache`` und
``detect``; gemessen die CPU-Sekunden aller Körper zusammen (``process_time``) und ein
Abdruck aller Merkmale Bit für Bit — gleich gegen den Ausgangsstand, sonst wäre die
Zeit nicht vergleichbar.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baum

ARGS = sys.argv[1:]
TREE = _baum.setup(ARGS[0])

from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.perceive import features as feats  # noqa: E402
from app.core.scene.cache import feature_to_data  # noqa: E402


def exact(value: Any) -> Any:
    """Werte für den Abdruck: Gleitkommazahlen als Hex, Bit für Bit."""
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): exact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(item) for item in value]
    return value


def main() -> None:
    with Path(ARGS[1]).open("a", encoding="utf-8") as out:
        for name in ARGS[2:]:
            model = Path(name)
            if model.suffix.lower() == ".3mf":
                from app.core.ingest.threemf import read_objects

                meshes = [
                    normalise(part.mesh, "mm").mesh for part in read_objects(model.read_bytes())
                ]
            else:
                meshes = [normalise(read_mesh(model.read_bytes(), model.suffix.lower()), "mm").mesh]
            digest = hashlib.blake2b(digest_size=12)
            spent = 0.0
            count = 0
            for mesh in meshes:
                feats.forget_cache()
                started = time.process_time()
                found = feats.detect(mesh)
                spent += time.process_time() - started
                count += len(found)
                rows = [[key, exact(feature_to_data(found[key]))] for key in sorted(found)]
                digest.update(json.dumps(rows, sort_keys=True, default=repr).encode("utf-8"))
            line = {
                "modell": model.name,
                "baum": TREE.name,
                "cpu": round(spent, 3),
                "merkmale": count,
                "koerper": len(meshes),
                "abdruck": digest.hexdigest(),
            }
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            out.flush()
            print(line, flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
