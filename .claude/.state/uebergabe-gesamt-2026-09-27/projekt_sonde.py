"""Sonde: Roberts Projekt mit dem Stand des Zweigs — Drucker, Lage, Stützvorschläge je Teil.

Aufruf: python projekt_sonde.py <code-wurzel> <projekt.p3d> <ausgabe.json> [drucker]
"""
# ruff: noqa: E501

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TREE = sys.argv[1]
PROJECT = Path(sys.argv[2])
TARGET = Path(sys.argv[3])
PRINTER = sys.argv[4] if len(sys.argv) > 4 else "centauri-carbon-2"
sys.argv = [sys.argv[0], TREE, str(PROJECT), str(TARGET.parent), "heim"]
sys.path.insert(0, str(HERE))
os.environ["GESAMT_AUSRICHTEN"] = "0"

import einheit  # noqa: E402

from app.core.export import manufacturer  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene.evaluate import evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, load  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.ui.print_settings_dialog import _AdviceWorker, _TargetedAdvice  # noqa: E402


def main() -> None:
    project = load(PROJECT)
    profile = profiles.make_profile(PRINTER, "pla")
    result = evaluate(project.document, profile, sources=ProjectSources(project, base_dir=PROJECT.parent))
    objects = [entry for entry in result.scene.objects.values() if as_mesh_data(entry.mesh).triangle_count]
    setup, _info = einheit.prepared("elegoo", profile)
    foundation = manufacturer.base_settings(profile, "standard", setup)
    settings = manufacturer.effective(None, foundation)
    worker = _AdviceWorker(
        tuple(objects), settings, profile, setup, {}, (), advise.connector_diameters(objects), {},
        flavour=setup.flavour,
    )
    got: list[Any] = []
    worker.done.connect(lambda entries, results: got.append((entries, results)))
    worker.work()
    entries, results = got[0]
    rows = [entry for entry in entries if einheit.offered(entry, setup.flavour)]
    bodies = []
    for entry in objects:
        bounds = as_mesh_data(entry.mesh).bounds
        size = [round(float(bounds.maximum[i] - bounds.minimum[i]), 1) for i in range(3)]
        sliced = results.get(entry.id)
        islands = 0
        overhang = 0.0
        if sliced is not None:
            layers = sliced[2].layers
            islands = sum(1 for layer in layers if layer.islands)
            overhang = round(sum(layer.overhang_area for layer in layers), 1)
        bodies.append({"name": str(entry.name), "plate": entry.plate, "size": size, "island_layers": islands, "overhang_mm2": overhang})
    output = {
        "printer": PRINTER,
        "document_printer": project.document.printer,
        "accepted": sorted(project.document.print_settings.accepted) if project.document.print_settings else [],
        "bodies": bodies,
        "advice": [
            {
                "path": entry.path,
                "value": str(entry.value),
                "parts": list(entry.parts) if isinstance(entry, _TargetedAdvice) else ["(alle)"],
                "reason": str(entry.reason)[:150],
            }
            for entry in rows
        ],
    }
    TARGET.write_text(json.dumps(output, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
