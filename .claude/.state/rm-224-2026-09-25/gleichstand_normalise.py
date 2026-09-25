"""Gegenprobe RM-224: ``loader.normalise`` liefert an jedem Körper dasselbe wie vorher.

Je Körper aus ``F:\\3D Dateien`` einmal ``normalise`` wie beim Import und eine
Zeile mit Befunden, Dreiecks- und Eckenzahl, Volumen und einem Abdruck der
Ecken, Dreiecke und Slots. Zwei Bäume, dieselbe Liste — ``diff`` der beiden
Ausgaben ist die Aussage. Nur lesend.

Aufruf: python gleichstand_normalise.py <baum> <ausgabe.txt>
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")

import numpy as np  # noqa: E402

import app.core.bootstrap  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.ingest import loader, threemf  # noqa: E402

CORPUS = Path(r"F:\3D Dateien")
SUFFIXES = {".stl", ".3mf", ".obj", ".ply", ".glb"}


def bodies(path: Path) -> list[tuple[str, MeshData]]:
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        objects = threemf.read_objects(payload)
        if objects:
            return [(str(part.name), part.mesh) for part in objects]
    return [(path.name, read_mesh(payload, path.suffix.lower()))]


def fingerprint(mesh: MeshData) -> str:
    digest = hashlib.sha1()
    digest.update(np.ascontiguousarray(mesh.raw.vertices, dtype=np.float64).tobytes())
    digest.update(np.ascontiguousarray(mesh.raw.faces, dtype=np.int64).tobytes())
    digest.update(np.asarray(mesh.slots, dtype=np.int64).tobytes())
    return digest.hexdigest()[:16]


lines: list[str] = []
started = time.perf_counter()
files = sorted(
    path
    for path in CORPUS.rglob("*")
    if path.is_file() and path.suffix.lower() in SUFFIXES and path.stat().st_size < 150_000_000
)
for path in files:
    label_base = str(path.relative_to(CORPUS))
    try:
        found = bodies(path)
    except Exception as problem:  # Fremde Dateien, fremde Fehler — nur vermerkt
        lines.append(f"{label_base}: nicht lesbar ({type(problem).__name__})")
        continue
    for name, mesh in found:
        label = f"{label_base}/{name}"
        if not mesh.triangle_count:
            lines.append(f"{label}: leer")
            continue
        try:
            result = loader.normalise(
                mesh, unit="mm", weld_is_reading=path.suffix.lower() == ".stl"
            )
        except Exception as problem:  # Auch ein Fehler muss in beiden Bäumen gleich sein
            lines.append(f"{label}: Fehler {type(problem).__name__}: {problem}")
            continue
        codes = ",".join(finding.code for finding in result.findings)
        out = result.mesh
        lines.append(
            f"{label}: {out.triangle_count} Dreiecke, {len(out.raw.vertices)} Ecken, "
            f"Volumen {out.volume!r}, dicht {out.is_watertight}, [{codes}], {fingerprint(out)}"
        )
Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(lines)} Körper in {time.perf_counter() - started:.0f} s")
