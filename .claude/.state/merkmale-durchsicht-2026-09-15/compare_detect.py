"""Merkmale je Körper kanonisch ausgeben — zum Vergleich zweier Code-Stände.

Aufruf: compare_detect.py <repo> <ausgabe.json> <datei> [...]
"""
# ruff: noqa: E501  -- Sonde: lange Ausgabezeilen sind hier Absicht

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo))

from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest import threemf  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402


def canonical(features):
    rows = []
    for fid, f in features.items():
        params = {}
        for k, v in f.params.items():
            if isinstance(v, float):
                params[k] = round(v, 4)
            elif isinstance(v, (list, tuple)):
                params[k] = [round(float(x), 4) for x in v]
            else:
                params[k] = v
        rows.append(
            {
                "id": fid,
                "kind": f.kind,
                "params": params,
                "faces": sorted(int(i) for i in f.face_indices),
            }
        )
    rows.sort(key=lambda r: (r["kind"], r["id"]))
    return rows


out = {}
for name in sys.argv[3:]:
    path = Path(name)
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        parts = threemf.read_objects(payload)
        bodies = [(part.name, part.mesh) for part in parts]
    else:
        bodies = [(path.stem, read_mesh(payload, path.suffix))]
    for body_name, mesh in bodies:
        try:
            normalised = normalise(mesh, "mm", weld_is_reading=path.suffix.lower() == ".stl").mesh
        except TypeError:
            normalised = normalise(mesh, "mm").mesh
        t = time.perf_counter()
        found = detect(normalised)
        out[f"{path.name}::{body_name}"] = {
            "seconds": round(time.perf_counter() - t, 2),
            "features": canonical(found),
        }
        print(
            f"{path.name}::{body_name}: {len(found)} in {out[f'{path.name}::{body_name}']['seconds']}s",
            flush=True,
        )
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
