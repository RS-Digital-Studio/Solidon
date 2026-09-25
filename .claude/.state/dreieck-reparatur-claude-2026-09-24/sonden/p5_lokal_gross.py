"""Sonde 5: Lokale Erkennung am großen Kundennetz (Mausoleum Dragon, 2,33 Mio. Dreiecke).

Fragt an echten Stellen: Was liefert ``detect_local`` bei Radius 5, 20, 60 —
Merkmal, Suchrand, Budget —, wie lange dauert es, und führt die Rückmeldung
den Kunden irgendwohin (Radius größer ↔ kleiner)? Dazu ``detect_known``
nach einer reinen Neuindizierung (Reparatur ohne Geometrieänderung).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")

import numpy as np  # noqa: E402

from app.core.errors import AppError  # noqa: E402
from app.core.ingest import threemf  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.perceive.local import detect_known, detect_local  # noqa: E402

OUT = Path(__file__).with_suffix(".txt")


def describe(result) -> str:
    rows = []
    for name, feature in sorted(result.features.items()):
        params = feature.params
        dims = ",".join(
            f"{key}={float(params[key]):.3f}"
            for key in ("diameter", "depth", "area", "radius", "local_search_radius")
            if isinstance(params.get(key), int | float) and not isinstance(params.get(key), bool)
        )
        rows.append(f"{name}:{feature.kind}[{dims}] n={len(feature.face_indices)}")
    return "; ".join(rows)


def main() -> None:
    with OUT.open("w", encoding="utf-8") as out:
        start = time.perf_counter()
        payload = Path(r"F:\3D Dateien\Mausoleum Dragon.3mf").read_bytes()
        parts = threemf.read_objects(payload, [])
        mesh = normalise(parts[0].mesh, "mm").mesh
        out.write(f"geladen {mesh.triangle_count} Dreiecke in {time.perf_counter() - start:.1f}s, "
                  f"dicht={mesh.is_watertight}\n")
        out.flush()
        centres = np.asarray(mesh.raw.triangles_center)
        normals = np.asarray(mesh.raw.face_normals)
        low = centres[:, 2].min()
        bottom = np.flatnonzero((centres[:, 2] < low + 0.01) & (normals[:, 2] < -0.999))
        rng = np.random.default_rng(20260924)
        seeds = {"Unterseite": int(bottom[len(bottom) // 2]) if len(bottom) else None}
        upward = np.flatnonzero(normals[:, 2] > 0.999)
        if len(upward):
            seeds["waagrechte Oberseite"] = int(upward[rng.integers(len(upward))])
        side = np.flatnonzero(np.abs(normals[:, 2]) < 0.001)
        if len(side):
            seeds["senkrechte Wand"] = int(side[rng.integers(len(side))])
        for index in rng.integers(mesh.triangle_count, size=3).tolist():
            seeds[f"zufällig {index}"] = int(index)
        known = {}
        for title, face in seeds.items():
            if face is None:
                continue
            point = tuple(float(v) for v in centres[face])
            normal = tuple(float(v) for v in normals[face])
            for radius in (5.0, 20.0, 60.0):
                begin = time.perf_counter()
                try:
                    result = detect_local(mesh, point, normal=normal, radius=radius,
                                          seed_faces=(face,))
                    took = time.perf_counter() - begin
                    out.write(f"{title} r={radius:g}: reason={result.reason} "
                              f"untersucht={len(result.examined_faces)} ({took:.1f}s) "
                              f"{describe(result)}\n")
                    if result.complete and not known:
                        known = dict(result.features)
                except AppError as problem:
                    out.write(f"{title} r={radius:g}: Fehler {problem.values.get('constraint')} "
                              f"({time.perf_counter() - begin:.1f}s)\n")
                out.flush()
        if known:
            begin = time.perf_counter()
            try:
                again = detect_known(mesh, known)
                out.write(f"detect_known am selben Netz: {len(again)} Merkmale "
                          f"({time.perf_counter() - begin:.1f}s): "
                          f"{sorted((f.kind, len(f.face_indices)) for f in again.values())}\n")
            except AppError as problem:
                out.write(f"detect_known: Fehler {problem.values.get('constraint')}\n")


if __name__ == "__main__":
    main()
