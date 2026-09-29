"""Die Druckvorschläge eines Modells je Drucker, wie der Druckdialog sie rechnet.

Aufruf: python vorschlaege_korpus.py <code-wurzel> <ergebnis.jsonl> <modell>

``<code-wurzel>`` ist der Arbeitsbaum, dessen ``app`` gemessen wird — so läuft
dieselbe Sonde einmal gegen den alten Stand (``46fa73c17``) und einmal gegen
den neuen, ohne dass eine Seite die andere lädt. Geladen wird wie
``solidon3d import`` (``import_plan``, ``History.apply``, ``evaluate``), die
Einheitenfrage beantwortet die Erkennung. Je Körper und Drucker: Winkel,
Überhangsumme, größtes Stück, Inselschichten, alle Vorschläge mit Wert.
Eine Zeile JSON je Körper und Drucker, fortlaufend geschrieben.
"""
# ruff: noqa: E501

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
MODEL = Path(sys.argv[3])
sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

import app  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.ingest.loader import detect_unit, read_local_payload, read_model  # noqa: E402
from app.core.ingest.plan import import_plan, names_in_use  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.project import (  # noqa: E402
    ProjectSources,
    embedded_source_path,
    new_project,
    next_source_id,
)
from app.core.slice import advise  # noqa: E402
from app.core.slice.analysis import (  # noqa: E402
    island_layers,
    largest_overhang_patch,
    slice_body,
    total_overhang,
)
from app.core.types import Source  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__

PRINTERS = tuple(
    one.strip()
    for one in os.environ.get(
        "SOLIDON_DRUCKER", "centauri-carbon-2,prusa-mk4s,prusa-mini,generic-220"
    ).split(",")
    if one.strip()
)
MATERIAL = "pla"


def emit(row: dict) -> None:
    with OUT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def load(model: Path) -> list:
    project = new_project("centauri-carbon-2", MATERIAL)
    payload = read_local_payload(model)
    source_id = next_source_id(project.document.sources)
    project.document.sources[source_id] = Source(
        id=source_id, kind="import", path=embedded_source_path(model.name, source_id), sha256=""
    )
    project.sources[source_id] = payload
    taken = names_in_use(project.document)
    plan = import_plan(source_id, model.name, payload, "auto", first_model=True, taken=taken)
    if plan.asks_unit:
        guess = detect_unit(read_model(payload, model.suffix).bounds.diagonal)
        plan = import_plan(
            source_id, model.name, payload, guess.unit or "mm", first_model=True, taken=taken
        )
    History(project.document).apply(plan.title, [plan.draft])
    result = evaluate(
        project.document,
        profiles.scene_profile("centauri-carbon-2", MATERIAL),
        sources=ProjectSources(project, base_dir=model.parent),
    )
    return list(result.scene.objects.values())


def main() -> int:
    base = {"file": str(MODEL), "root": ROOT.name}
    started = time.perf_counter()
    try:
        objects = load(MODEL)
    except Exception as problem:
        emit({**base, "stage": "load", "error": f"{type(problem).__name__}: {str(problem)[:300]}", "trace": traceback.format_exc()[-1500:]})
        return 1
    base["load_seconds"] = round(time.perf_counter() - started, 2)
    for entry in objects:
        mesh = as_mesh_data(entry.mesh)
        if not mesh.triangle_count:
            continue
        for printer in PRINTERS:
            row = {**base, "body": str(entry.name), "triangles": int(mesh.triangle_count), "printer": printer}
            began = time.perf_counter()
            try:
                profile = profiles.make_profile(printer, MATERIAL)
                settings = print_settings.resolve(profile)
                process = profiles.for_process(profile, settings)
                angle = process.overhang_limit_degrees
                result = slice_body(
                    mesh,
                    settings.layers.layer_height,
                    first_layer_height=settings.layers.first_layer_height,
                    overhang_angle=angle,
                    bridge_from=process.minimum_wall_thickness,
                    support_volume=False,
                )
                entries = advise.advise(settings, profile, result, bounds=mesh.bounds)
                row.update(
                    angle=angle,
                    threshold=settings.support.threshold_angle,
                    overhang=round(total_overhang(result), 3),
                    patch=round(largest_overhang_patch(result), 3),
                    islands=len(island_layers(result)),
                    advice=sorted([entry.path, str(entry.value)] for entry in entries),
                    seconds=round(time.perf_counter() - began, 2),
                )
            except Exception as problem:
                row.update(error=f"{type(problem).__name__}: {str(problem)[:300]}", trace=traceback.format_exc()[-1500:])
            emit(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
