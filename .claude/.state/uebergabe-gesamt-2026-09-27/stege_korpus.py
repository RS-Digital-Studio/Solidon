"""Eichung „schmale Stege“: Anteil und Fläche schmaler Stege in der ersten Schicht.

Aufruf: python stege_korpus.py <code-wurzel> <ausgabe.json> <ordner> [<ordner> ...]

Je STL/3MF-Körper die erste Schicht (Schnitt auf halber Höhe der ersten
Schicht, liegend wie die Datei), dazu Anteil und Fläche der Stege schmaler als
sechs Bahnen der ersten Schicht (``advise.NARROW_WEB_LINES``, 3 mm am CC2).
Die Messung selbst ist ``analysis.narrow_share``, hier auf den Schnitt gelegt.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

import shapely  # noqa: E402

from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.geom.transform import place_on_bed  # noqa: E402
from app.core.ingest.loader import normalise, read_mesh  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.slice.analysis import cross_section  # noqa: E402

TARGET = Path(sys.argv[2])
profile = profiles.make_profile("centauri-carbon-2", "pla")
settings = print_settings.resolve(profile, "standard")
width = advise.NARROW_WEB_LINES * settings.layers.first_layer_line_width
height = settings.layers.first_layer_height / 2.0
rows = []
files = [p for folder in sys.argv[3:] for p in sorted(Path(folder).rglob("*")) if p.suffix.lower() == ".stl"]
started = time.perf_counter()
for path in files:
    try:
        if path.stat().st_size > 60_000_000:
            continue
        mesh = place_on_bed(normalise(read_mesh(path.read_bytes(), ".stl"), "mm", mend=False).mesh)
        data = as_mesh_data(mesh)
        section = cross_section(data, float(data.bounds.minimum[2]) + height)
        if section is None or section.is_empty or section.area <= 0.0:
            continue
        opened = section.buffer(-width / 2.0, quad_segs=4).buffer(width / 2.0, quad_segs=4)
        kept = float(shapely.intersection(opened, section).area)
        area = float(section.area)
        rows.append(
            {
                "file": str(path),
                "foot_mm2": round(area, 1),
                "narrow_mm2": round(area - kept, 1),
                "share": round(max(0.0, 1.0 - kept / area), 4),
            }
        )
    except Exception as problem:  # noqa: BLE001 — eine Messung überspringt, was nicht liest
        rows.append({"file": str(path), "error": f"{type(problem).__name__}: {problem}"[:200]})
TARGET.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(rows), "Körper in", round(time.perf_counter() - started), "s")
