"""Übergabe am Korpus: ein Modell, jede Slicerfamilie, Standard und übernommene Vorschläge.

Geht den Weg der Anwendung: einbetten und laden wie ``solidon3d import``
(``import_plan``, ``History.apply``, ``evaluate``), Vorschläge wie der
Druckdialog (``slice_body`` je Körper, ``advise.advise``, ``advise.combine``,
``advise.apply``), Maschine und Prozess über ``slicer_profiles.match``,
Übergabe über ``export.writer.write_assembly`` und ``handover.slice_model``.

Aufruf: python lauf.py <modell> <ergebnis.jsonl> <arbeitsordner>

Je Lauf eine JSON-Zeile. Mit übernommener Kanalsperre schneidet er zusätzlich
dieselben Einstellungen ohne Sperre: Die Modellbahn muss gleich bleiben
(Sperre ≠ Kunststoff, siehe RM-247).
"""

from __future__ import annotations

import json
import re
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.export import handover, slicer_profiles  # noqa: E402
from app.core.export.writer import write_assembly  # noqa: E402
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
from app.core.slice.analysis import slice_body  # noqa: E402
from app.core.types import Source  # noqa: E402

SLICERS = {
    "elegoo": (r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe", "centauri-carbon-2"),
    "orca": (r"C:\Program Files\OrcaSlicer\orca-slicer.exe", "bambu-a1"),
    "prusa": (r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe", "prusa-mk4s"),
    "cura": (r"C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe", "creality-ender3-v3"),
}
MATERIAL = "pla"


def imported_objects(model: Path) -> tuple[list[Any], list[str]]:
    """Die Körper, wie sie nach dem Laden in der Szene stehen, dazu die Befunde."""
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
        unit = guess.unit or "mm"
        plan = import_plan(source_id, model.name, payload, unit, first_model=True, taken=taken)
    History(project.document).apply(plan.title, [plan.draft])
    result = evaluate(
        project.document,
        profiles.scene_profile("centauri-carbon-2", MATERIAL),
        sources=ProjectSources(project, base_dir=model.parent),
    )
    findings = [f"{f.severity}:{f.code}" for f in result.scene.report.findings]
    return list(result.scene.objects.values()), findings


def advised(settings: Any, profile: Any, objects: list[Any], cache: dict) -> tuple[Any, list]:
    """Die Vorschläge wie im Druckdialog, alle übernommen."""
    process = profiles.for_process(profile, settings)
    angle, wall = process.overhang_limit_degrees, process.minimum_wall_thickness
    common = []
    for entry in objects:
        key = (
            entry.id,
            settings.layers.layer_height,
            settings.layers.first_layer_height,
            angle,
            wall,
        )
        if key not in cache:
            mesh = entry.mesh
            cache[key] = slice_body(
                mesh,
                settings.layers.layer_height,
                first_layer_height=settings.layers.first_layer_height,
                overhang_angle=angle,
                bridge_from=wall,
                support_volume=False,
            )
        common.append(
            (settings, advise.advise(settings, profile, cache[key], bounds=entry.mesh.bounds))
        )
    entries = advise.combine(settings, common)
    return advise.apply(settings, entries), [(e.path, e.value) for e in entries]


def extrusion(gcode: Path) -> dict[str, float]:
    """Bahnlänge je Art in m, über die Kommentare ``;TYPE:`` aller drei Familien."""
    kind = "?"
    x = y = 0.0
    absolute = True
    last_e = 0.0
    lengths: dict[str, float] = {}
    number = re.compile(r"([XYEG])(-?(?:\d+\.?\d*|\.\d+))")
    with gcode.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            # Mit einem Bambu-Drucker schreibt die Orca-Familie „; FEATURE:".
            if line.startswith((";TYPE:", "; FEATURE:")):
                kind = line.split(":", 1)[1].strip()
                continue
            if line.startswith("M83"):
                absolute = False
            elif line.startswith("M82"):
                absolute = True
            elif line.startswith("G92"):
                found = dict(number.findall(line.split(";")[0]))
                if "E" in found:
                    last_e = float(found["E"])
            if not line.startswith(("G1 ", "G0 ", "G2", "G3")):
                continue
            values = dict(number.findall(line.split(";")[0]))
            nx, ny = float(values.get("X", x)), float(values.get("Y", y))
            if "E" in values:
                e = float(values["E"])
                pushed = (e - last_e) if absolute else e
                if absolute:
                    last_e = e
                if pushed > 0 and (nx != x or ny != y):
                    lengths[kind] = (
                        lengths.get(kind, 0.0) + float(np.hypot(nx - x, ny - y)) / 1000.0
                    )
            x, y = nx, ny
    return lengths


def split(lengths: dict[str, float]) -> tuple[float, float, float]:
    support = sum(v for k, v in lengths.items() if "support" in k.lower())
    rim = sum(v for k, v in lengths.items() if k.lower() in ("skirt", "brim", "skirt/brim"))
    model = sum(lengths.values()) - support - rim
    return round(model, 2), round(support, 2), round(rim, 2)


def one_run(
    name: str, objects: list[Any], settings: Any, profile: Any, setup: Any, folder: Path
) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    row: dict[str, Any] = {}
    try:
        path, findings = write_assembly(
            objects,
            folder,
            project_name="probe",
            profile=profile,
            settings=settings,
            flavour=setup.flavour,
            place_on_bed=True,
            setup=setup,
        )
        row["export_findings"] = sorted({f"{f.severity}:{f.code}" for f in findings})
        outcome = handover.slice_model(
            path, settings, profile, setup, output_dir=folder, keep_arrangement=True
        )
        metrics = outcome.metrics
        row.update(
            ok=True,
            seconds=round(time.perf_counter() - started, 1),
            print_minutes=round((metrics.print_seconds or 0) / 60.0, 1),
            filament_g=metrics.filament_grams,
            layers=metrics.layer_count,
            slice_findings=sorted({f"{f.severity}:{f.code}" for f in outcome.findings}),
            warnings=[
                {
                    "code": f.code,
                    "text": str(f.message)[:300],
                    "values": {k: str(v)[:200] for k, v in (f.values or {}).items()},
                }
                for f in [*outcome.findings, *findings]
                if f.severity != "info"
            ],
        )
        model, support, rim = split(extrusion(outcome.gcode_path))
        row.update(model_m=model, support_m=support, rim_m=rim)
        outcome.gcode_path.unlink(missing_ok=True)
    except AppError as problem:
        row.update(
            ok=False,
            error=type(problem).__name__,
            detail=str(problem)[:400],
            values={k: str(v)[:200] for k, v in (problem.values or {}).items()},
        )
    except Exception as problem:
        row.update(
            ok=False,
            error=type(problem).__name__,
            detail=str(problem)[:400],
            trace=traceback.format_exc()[-1500:],
        )
    row.setdefault("seconds", round(time.perf_counter() - started, 1))
    return row


def main() -> int:
    model = Path(sys.argv[1])
    out = Path(sys.argv[2])
    work = Path(sys.argv[3])
    load_operations()
    base = {"model": model.name}
    try:
        started = time.perf_counter()
        objects, load_findings = imported_objects(model)
        base.update(
            bodies=len(objects),
            triangles=int(sum(o.mesh.triangle_count for o in objects)),
            load_seconds=round(time.perf_counter() - started, 1),
            load_findings=load_findings,
        )
    except Exception as problem:
        with out.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        **base,
                        "stage": "import",
                        "ok": False,
                        "error": type(problem).__name__,
                        "detail": str(problem)[:400],
                        "trace": traceback.format_exc()[-1500:],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return 1
    cache: dict = {}
    for slicer, (executable, printer_id) in SLICERS.items():
        profile = profiles.make_profile(printer_id, MATERIAL)
        setup = handover.detect(executable)
        # Wie der Druckdialog: Für PrusaSlicer und CuraEngine wählt er kein
        # Profil — Solidon beschreibt die Maschine selbst
        # (``print_settings_dialog._start_profile_search``).
        machine, process = (
            (None, None)
            if setup.flavour in ("prusa", "cura")
            else slicer_profiles.match(
                list(
                    slicer_profiles.find_profiles(
                        Path(executable), setup.flavour, ("machine", "process")
                    )
                ),
                profile.printer,
            )
        )
        setup = replace(
            setup,
            machine_profile=machine.name if machine else "",
            base_process=process.name if process else "",
        )
        standard = print_settings.resolve(profile)
        try:
            analysed_at = time.perf_counter()
            taken, entries = advised(standard, profile, objects, cache)
            advice_seconds = round(time.perf_counter() - analysed_at, 1)
            advice_error = None
        except Exception as problem:
            taken, entries, advice_seconds = None, [], None
            advice_error = f"{type(problem).__name__}: {str(problem)[:300]}"
        variants = [("standard", standard)]
        if taken is not None:
            variants.append(("vorschlaege", taken))
            if taken.support.block_channels and slicer != "cura":
                variants.append(
                    (
                        "vorschlaege_ohne_sperre",
                        print_settings.with_path(taken, "support.block_channels", False),
                    )
                )
        for variant, settings in variants:
            row = one_run(model.name, objects, settings, profile, setup, work / slicer / variant)
            row.update(
                base,
                slicer=slicer,
                printer=printer_id,
                variant=variant,
                machine=setup.machine_profile,
                process=setup.base_process,
            )
            if variant == "vorschlaege":
                row.update(advice=[[p, str(v)] for p, v in entries], advice_seconds=advice_seconds)
            if variant == "standard" and advice_error:
                row["advice_error"] = advice_error
            with out.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            print(
                f"{model.name} {slicer} {variant}: {'ok' if row.get('ok') else row.get('error')}",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
