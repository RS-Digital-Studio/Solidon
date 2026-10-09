"""Kanalfrage und Druckvorschläge eines Korpusmodells am Centauri Carbon 2.

Aufruf: python korpus_kanal.py <code-wurzel> <ergebnis.jsonl> <modell>

Geladen wie ``solidon3d import``; je Körper: Kanalstücke, Kanalfläche, Decken,
offene Fläche, Sperrvolumen (``channel_space``, Scheibenhöhe mal Fläche) und
die Vorschläge des Druckdialogs. Eine Zeile JSON je Körper.
"""

from __future__ import annotations

import inspect
import json
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
from app.core.export import writer  # noqa: E402
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
from app.core.slice.analysis import channel_space  # noqa: E402
from app.core.types import Source  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
PRINTER, MATERIAL = "centauri-carbon-2", "pla"


def emit(row: dict) -> None:
    with OUT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def load(model: Path) -> list:
    project = new_project(PRINTER, MATERIAL)
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
        profiles.scene_profile(PRINTER, MATERIAL),
        sources=ProjectSources(project, base_dir=model.parent),
    )
    return list(result.scene.objects.values())


def main() -> int:
    base = {"file": str(MODEL), "root": ROOT.name}
    try:
        objects = load(MODEL)
    except Exception as problem:
        emit({**base, "error": f"{type(problem).__name__}: {problem}"[:300]})
        return 1
    profile = profiles.make_profile(PRINTER, MATERIAL)
    settings = print_settings.resolve(profile)
    for entry in objects:
        mesh = as_mesh_data(entry.mesh)
        if not mesh.triangle_count:
            continue
        row = {**base, "body": str(entry.name), "triangles": int(mesh.triangle_count)}
        started = time.perf_counter()
        try:
            result = writer._body_analysis(entry, mesh, settings, profile, None, detail="full")
            need = advise.support_need(result)
            model = need.model
            # Seit dem Review vom 08.10. nimmt der Kanalraum die Bahnbreite.
            width = (
                (settings.layers.line_width,)
                if len(inspect.signature(channel_space).parameters) > 2
                else ()
            )
            slabs = channel_space(result, model, *width) if model.channels else []
            entries = advise.advise(settings, profile, result, bounds=mesh.bounds)
            row.update(
                needed=need.needed,
                channels=len(model.channels),
                channel_area=round(model.channel_area, 1),
                open_area=round(model.open_area, 1),
                island_on_model=model.island_on_model,
                blocker_mm3=round(sum((high - low) * area.area for low, high, area in slabs), 0),
                advice=sorted([item.path, str(item.value)] for item in entries),
                seconds=round(time.perf_counter() - started, 1),
            )
        except Exception as problem:
            row.update(
                error=f"{type(problem).__name__}: {problem}"[:300],
                trace=traceback.format_exc()[-1200:],
            )
        emit(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
