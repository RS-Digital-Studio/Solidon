"""Sonde 2: Import (normalise) und ausdrückliches Reparieren an Kundendateien.

Je Körper: Kennzahlen roh → nach Import → nach Reparieren (Vorgaben der Op,
also inspect_intersections=True), Zeit je Schritt, Befundcodes. Schreibt eine
Zeile JSON je Körper nach s02.jsonl (fortlaufend, flush).
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

from common import KUNDE, R, MeshData, codes, facts

from app.core.geom.mesh import read_mesh
from app.core.ingest import threemf
from app.core.ingest.loader import normalise

OUT = Path(__file__).with_name("s02.jsonl")
SUFFIXES = {".stl", ".3mf", ".glb", ".obj", ".ply"}
LIMIT_SI_RESOLVE = 400_000

STEPS = [
    "merge_vertices",
    "remove_doubled_faces",
    "remove_degenerate_faces",
    "resolve_branching_edges",
    "stitch_t_junctions",
    "_filled_with_count",
    "unify_normals",
    "self_intersection_check",
    "resolve_self_intersections",
]
spent: dict[str, float] = defaultdict(float)


def _wrap(name: str) -> None:
    original = getattr(R, name)

    def timed(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            spent[name] += time.perf_counter() - t0

    setattr(R, name, timed)


for step in STEPS:
    _wrap(step)


def parts_of(path: Path) -> list[tuple[str, MeshData]]:
    payload = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".3mf":
        objects = threemf.read_objects(payload)
        return [(str(part.name), part.mesh) for part in objects]
    return [(path.name, read_mesh(payload, suffix))]


def main(selection: list[Path]) -> None:
    with OUT.open("a", encoding="utf-8") as sink:
        for path in selection:
            try:
                bodies = parts_of(path)
            except Exception as problem:  # noqa: BLE001
                sink.write(json.dumps({"file": str(path), "error": repr(problem)}) + "\n")
                sink.flush()
                continue
            for name, mesh in bodies:
                row: dict = {"file": str(path.relative_to(KUNDE)), "part": name}
                try:
                    row["raw_tri"] = mesh.triangle_count
                    t0 = time.perf_counter()
                    ingested = normalise(mesh, "mm", weld_is_reading=path.suffix.lower() == ".stl")
                    row["ingest_s"] = round(time.perf_counter() - t0, 2)
                    row["ingest_codes"] = codes(ingested.findings)
                    row["after_ingest"] = facts(ingested.mesh)
                    spent.clear()
                    t0 = time.perf_counter()
                    result = R.repair(ingested.mesh, inspect_intersections=True)
                    row["repair_s"] = round(time.perf_counter() - t0, 2)
                    row["repair_steps"] = {k: round(v, 2) for k, v in spent.items() if v >= 0.01}
                    row["repair_codes"] = codes(result.findings)
                    row["repair_changed"] = result.changed
                    row["after_repair"] = facts(result.mesh)
                    if (
                        "repair.self_intersections_detected" in row["repair_codes"]
                        and ingested.mesh.triangle_count <= LIMIT_SI_RESOLVE
                    ):
                        spent.clear()
                        t0 = time.perf_counter()
                        resolved = R.repair(
                            ingested.mesh, self_intersections=True, inspect_intersections=True
                        )
                        row["si_s"] = round(time.perf_counter() - t0, 2)
                        row["si_steps"] = {k: round(v, 2) for k, v in spent.items() if v >= 0.01}
                        row["si_codes"] = codes(resolved.findings)
                        row["after_si"] = facts(resolved.mesh)
                except Exception as problem:  # noqa: BLE001
                    row["error"] = repr(problem)
                    row["trace"] = traceback.format_exc()[-800:]
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                sink.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        files = [Path(arg) for arg in sys.argv[1:]]
    else:
        files = sorted(
            (p for p in KUNDE.rglob("*") if p.suffix.lower() in SUFFIXES and p.is_file()),
            key=lambda p: p.stat().st_size,
        )
    main(files)
    print("fertig", len(files))
