"""Sonde 0: Welche Kundennetze sind nach dem Einlesen ohne Flicken offen?

Liest jede Datei wie die Ladeoperation (3MF je Körper, sonst ein Körper),
normalisiert einmal ohne und einmal mit Flicken und zählt offene und
verzweigte Kanten, Teile und Dreiecke. Schreibt eine Zeile je Körper.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")

from app.core.geom.repair import branching_edge_count, open_edge_count  # noqa: E402
from app.core.ingest import threemf  # noqa: E402
from app.core.ingest.loader import normalise, read_model  # noqa: E402

ROOT = Path(r"F:\3D Dateien")
OUT = Path(__file__).with_suffix(".txt")


def parts_of(path: Path):
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        found = threemf.read_objects(payload, [])
        if found:
            return [(part.name, part.mesh) for part in found]
    return [(path.stem, read_model(payload, path.suffix))]


def main() -> None:
    files = sorted(
        entry
        for entry in ROOT.iterdir()
        if entry.is_file() and entry.suffix.lower() in {".stl", ".3mf", ".obj", ".ply", ".glb"}
    )
    with OUT.open("w", encoding="utf-8") as out:
        for path in files:
            if path.stat().st_size > 12_000_000:
                out.write(f"{path.name}\tübersprungen (Größe {path.stat().st_size})\n")
                continue
            try:
                parts = parts_of(path)
            except Exception as problem:  # Sonde: jede Datei soll eine Zeile bekommen
                out.write(f"{path.name}\tLesefehler {problem!r}\n")
                continue
            for name, mesh in parts:
                start = time.perf_counter()
                plain = normalise(mesh, "mm", mend=False).mesh
                mended = normalise(mesh, "mm").mesh
                took = time.perf_counter() - start
                out.write(
                    f"{path.name}\t{name}\ttri={plain.triangle_count}\t"
                    f"open={open_edge_count(plain)}\tbranch={branching_edge_count(plain)}\t"
                    f"wt={plain.is_watertight}\tparts={plain.component_count}\t"
                    f"| gefl: tri={mended.triangle_count} open={open_edge_count(mended)} "
                    f"branch={branching_edge_count(mended)} wt={mended.is_watertight}\t"
                    f"{took:.1f}s\n"
                )
                out.flush()


if __name__ == "__main__":
    main()
