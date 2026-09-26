"""RM-239/240: Einlesen aller Kundendateien aus F:\3D Dateien, an einem wählbaren Stand.

Aufruf: python korpus_import.py <arbeitsbaum> <ausgabe.jsonl> — die Kopie der Sonde aus
``.claude/.state/bedienweg-abarbeitung-2026-09-25/``, dort mit festem Stand und Ziel.

Je Körper: Zeit von ``normalise``, davon die Durchdringungsfrage
(``parts_that_cross``), die Befundcodes und ob die Teile ineinanderstecken;
bei einer großen Öffnung zusätzlich der Weg *Offen lassen* (``wide_holes=False``).
Eine Zeile JSON je Körper, fortlaufend geschrieben. Nur lesend.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))

import app.core.bootstrap  # noqa: E402,F401
from app.core.geom import repair as R  # noqa: E402
from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest import loader, threemf  # noqa: E402

KUNDE = Path(r"F:\3D Dateien")
OUT = Path(sys.argv[2])
SUFFIXES = {".stl", ".3mf", ".obj", ".ply", ".glb"}

spent = {"cross": 0.0}
original = R.parts_that_cross


def timed(*args, **kwargs):
    started = time.perf_counter()
    try:
        return original(*args, **kwargs)
    finally:
        spent["cross"] += time.perf_counter() - started


loader.parts_that_cross = timed


def parts_of(path: Path):
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        objects = threemf.read_objects(payload)
        if objects:
            return [(str(part.name), part.mesh) for part in objects]
    return [(path.name, read_mesh(payload, path.suffix.lower()))]


def main() -> None:
    files = sorted(
        path
        for path in KUNDE.rglob("*")
        if path.is_file() and path.suffix.lower() in SUFFIXES and path.stat().st_size < 150_000_000
    )
    with OUT.open("w", encoding="utf-8") as sink:
        for path in files:
            try:
                bodies = parts_of(path)
            except Exception as problem:  # noqa: BLE001
                sink.write(json.dumps({"file": str(path), "read_error": repr(problem)}) + "\n")
                sink.flush()
                continue
            for name, mesh in bodies:
                row: dict = {"file": str(path.relative_to(KUNDE)), "part": name}
                try:
                    row["tri"] = mesh.triangle_count
                    spent["cross"] = 0.0
                    started = time.perf_counter()
                    result = loader.normalise(
                        mesh, "mm", weld_is_reading=path.suffix.lower() == ".stl"
                    )
                    row["s"] = round(time.perf_counter() - started, 3)
                    row["cross_s"] = round(spent["cross"], 3)
                    row["codes"] = sorted({f.code for f in result.findings})
                    row["closed"] = bool(result.mesh.is_watertight)
                    row["parts"] = result.info.components
                    many = [f for f in result.findings if f.code == "ingest.multiple_components"]
                    if many:
                        row["crossing"] = bool(many[0].suggestions)
                        row["buttons"] = [a.id for a in many[0].suggestions]
                    if "repair.wide_hole_filled" in row["codes"]:
                        kept = loader.normalise(
                            mesh,
                            "mm",
                            weld_is_reading=path.suffix.lower() == ".stl",
                            wide_holes=False,
                        )
                        row["kept_codes"] = sorted({f.code for f in kept.findings})
                        row["kept_closed"] = bool(kept.mesh.is_watertight)
                except Exception as problem:  # noqa: BLE001
                    row["error"] = repr(problem)
                    row["trace"] = traceback.format_exc()[-800:]
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                sink.flush()


if __name__ == "__main__":
    main()
