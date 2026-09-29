"""Minigolf-Satz: eine STL über den Kundenweg bis in den ElegooSlicer.

Auftrag Robert, 27.09.2026: die neue Version gegen
``F:\\3D Dateien\\Mini+Golf+All+Set-P1S_stls`` kontrollieren — „wir wollen es mit
dem Elegoo Slicer und unserem Drucker drucken". Also Centauri Carbon 2, PLA,
Standardqualität, ElegooSlicer. Je Datei:

1. Laden wie ``solidon3d import`` (``import_plan``, ``History.apply``,
   ``evaluate``): Zeit, Einheitenfrage, Befunde mit Text.
2. Prüfbericht wie nach jeder Auswertung (``slice.findings.print_findings``),
   Zeit und Befunde.
3. Vorschläge wie der Druckdialog (``lauf.advised`` der Übergabesonde vom
   26.09.), Zeit und Einträge.
4. Übergabe an den ElegooSlicer, jede Variante in eine eigene Druckdatei:
   ``elegoo`` — das Herstellerprofil allein (Maschine, Prozess, PLA-Filament
   aus ``%APPDATA%\\ElegooSlicer\\system``), der Maßstab;
   ``elegoo_stuetzen`` — dasselbe mit eingeschalteten Stützen, nur wenn
   Solidon Stützen vorschlägt;
   ``standard`` — Solidons Übergabe ohne Vorschläge;
   ``vorschlaege`` — mit allen Vorschlägen übernommen.
   Gelesen werden Zeit, Gramm, Bahnen je Art, Stütze, und die ersten drei
   Schichten (Bahnarten, Leerfahrten).

Aufruf: python druck.py <stl> <ergebnis.jsonl> <arbeitsordner>
"""
# ruff: noqa: E501  -- Sonde: lange Zeilen sind hier Absicht

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

# Welcher Stand gemessen wird: ``SOLIDON_CODE`` nennt den Arbeitsbaum, ohne
# Angabe der Hauptklon. ``lauf.py`` der Übergabesonde wird nicht mehr
# importiert — es legt den Hauptklon vor den Suchpfad, und ein später träge
# geladenes Modul käme dann aus dem falschen Baum.
ROOT = Path(os.environ.get("SOLIDON_CODE") or Path(__file__).resolve().parents[3]).resolve()
sys.path.insert(0, str(ROOT))

import app  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
load_operations()
from app.core.errors import AppError  # noqa: E402
from app.core.export import handover, slicer_profiles  # noqa: E402
from app.core.export.writer import write_assembly  # noqa: E402
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
from app.core.slice.analysis import slice_body  # noqa: E402
from app.core.slice.findings import print_findings  # noqa: E402
from app.core.types import Source  # noqa: E402

ELEGOO = Path(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe")
PRINTER = "centauri-carbon-2"
MATERIAL = "pla"
BED = 256.0


def advised(settings: Any, profile: Any, objects: list[Any]) -> tuple[Any, list]:
    """Die Vorschläge wie im Druckdialog, alle übernommen (wörtlich aus ``lauf.advised``)."""
    process = profiles.for_process(profile, settings)
    angle, wall = process.overhang_limit_degrees, process.minimum_wall_thickness
    common = []
    for entry in objects:
        mesh = entry.mesh
        result = slice_body(
            mesh,
            settings.layers.layer_height,
            first_layer_height=settings.layers.first_layer_height,
            overhang_angle=angle,
            bridge_from=wall,
            support_volume=False,
        )
        common.append((settings, advise.advise(settings, profile, result, bounds=entry.mesh.bounds)))
    entries = advise.combine(settings, common)
    return advise.apply(settings, entries), [(e.path, e.value) for e in entries]


def finding_row(finding: Any) -> dict:
    return {
        "code": finding.code,
        "severity": finding.severity,
        "text": str(finding.message)[:400],
        "values": {k: str(v)[:120] for k, v in (finding.values or {}).items()},
        "object": str(finding.object_id) if finding.object_id else None,
    }


def load(model: Path) -> tuple[Any, dict]:
    """Wie ``solidon3d import``: einbetten, Plan, anwenden, auswerten."""
    project = new_project(PRINTER, MATERIAL)
    payload = read_local_payload(model)
    source_id = next_source_id(project.document.sources)
    project.document.sources[source_id] = Source(
        id=source_id, kind="import", path=embedded_source_path(model.name, source_id), sha256=""
    )
    project.sources[source_id] = payload
    taken = names_in_use(project.document)
    plan = import_plan(source_id, model.name, payload, "auto", first_model=True, taken=taken)
    info: dict[str, Any] = {"asks_unit": bool(plan.asks_unit)}
    if plan.asks_unit:
        guess = detect_unit(read_model(payload, model.suffix).bounds.diagonal)
        info["unit_guess"] = guess.unit
        plan = import_plan(
            source_id, model.name, payload, guess.unit or "mm", first_model=True, taken=taken
        )
    History(project.document).apply(plan.title, [plan.draft])
    result = evaluate(
        project.document,
        profiles.scene_profile(PRINTER, MATERIAL),
        sources=ProjectSources(project, base_dir=model.parent),
    )
    info["complete"] = result.complete
    info["findings"] = [finding_row(f) for f in result.scene.report.findings]
    return result, info


def elegoo_reference(setup: Any, machine: Any, process: Any) -> dict[str, object]:
    """Das Herstellerprofil allein, als Projekteinstellungen einer Orca-3MF."""
    roots = slicer_profiles.profile_roots(setup.flavour, ELEGOO)
    found = slicer_profiles.find_profiles(ELEGOO, "orca", ("machine", "process", "filament"))
    filament = slicer_profiles.match_filament(found, machine, "PLA", roots)
    document: dict[str, object] = {}
    names = {}
    for kind, entry in (("machine", machine), ("process", process), ("filament", filament)):
        if entry is None:
            raise RuntimeError(f"kein Elegoo-Profil: {kind}")
        values = slicer_profiles.resolve_values(entry.path, roots=roots)
        names[kind] = entry.name
        if kind == "filament":
            values = {k: (v if isinstance(v, list) else [v]) for k, v in values.items()}
        document.update(values)
    for key in ("type", "instantiation", "inherits", "setting_id", "filament_id"):
        document.pop(key, None)
    # Ohne ``curr_bed_type`` nimmt der Konsolenlauf „Cool Plate" (35 °C); das
    # Fenster nimmt ``default_bed_type`` der Maschine — am CC2 „4". Das ist
    # die texturierte PEI-Platte: Alle 34 mit ElegooSlicer 1.5.x gespeicherten
    # Centauri-Projekte in F:\3D Dateien tragen „Textured PEI Plate", fünf
    # davon zusammen mit ``default_bed_type = 4`` (27.09.2026). Hier stand
    # zuerst „High Temp Plate" — das war geraten und falsch. Andere Nummern
    # sind nicht belegt; die übrigen Hersteller schreiben den Namen.
    plates = {"4": "Textured PEI Plate"}
    default = str(document.get("default_bed_type", "")).strip()
    document["curr_bed_type"] = plates.get(default, default) if default else ""
    if not document["curr_bed_type"]:
        document.pop("curr_bed_type")
    document["from"] = "project"
    document["name"] = "project_settings"
    document["printer_settings_id"] = names["machine"]
    document["print_settings_id"] = names["process"]
    document["filament_settings_id"] = [names["filament"]]
    return document


def with_project_settings(source: Path, target: Path, settings: dict[str, object]) -> None:
    """Die 3MF mit anderen Projekteinstellungen und ohne Teileinstellungen."""
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst:
        names = set(src.namelist())
        for item in src.infolist():
            if item.filename == "Metadata/project_settings.config":
                continue
            dst.writestr(item, src.read(item.filename))
        dst.writestr("Metadata/project_settings.config", json.dumps(settings, indent=1))
        assert "3D/3dmodel.model" in names


NUMBER = re.compile(r"([XYZEF])(-?(?:\d+\.?\d*|\.\d+))")


def read_gcode(path: Path) -> dict:
    """Bahnen je Art (m), Stütze, Rand, erste drei Schichten, Fahrten übers Bett."""
    kind = "?"
    x = y = 0.0
    absolute = True
    last_e = 0.0
    layer = -1
    total: dict[str, float] = {}
    first: list[dict] = [{"z": None, "paths": {}, "travels": 0, "long_travels": 0} for _ in range(3)]
    outside: dict[str, int] = {}
    header: dict[str, str] = {}
    everything: dict[str, str] = {}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(";"):
                if line.startswith((";TYPE:", "; FEATURE:")):
                    kind = line.split(":", 1)[1].strip()
                elif line.startswith(";LAYER_CHANGE"):
                    layer += 1
                elif line.startswith(";Z:") and 0 <= layer < 3 and first[layer]["z"] is None:
                    first[layer]["z"] = float(line[3:].strip())
                elif " = " in line:
                    key, value = line[1:].split(" = ", 1)
                    key = key.strip()
                    everything[key] = value.strip()
                    if key in (
                        "estimated printing time (normal mode)",
                        "filament used [g]",
                        "filament used [mm]",
                        "total layers count",
                        "enable_support",
                        "support_type",
                        "support_on_build_plate_only",
                        "brim_type",
                        "brim_width",
                        "wall_loops",
                        "sparse_infill_density",
                        "sparse_infill_pattern",
                        "layer_height",
                        "initial_layer_print_height",
                        "nozzle_temperature",
                        "nozzle_temperature_initial_layer",
                        "hot_plate_temp",
                        "hot_plate_temp_initial_layer",
                        "travel_speed",
                        "outer_wall_speed",
                        "inner_wall_speed",
                        "sparse_infill_speed",
                        "initial_layer_speed",
                        "fan_max_speed",
                        "close_fan_the_first_x_layers",
                        "top_shell_layers",
                        "bottom_shell_layers",
                        "support_threshold_angle",
                        "curr_bed_type",
                        "filament_settings_id",
                        "print_settings_id",
                        "printer_settings_id",
                        "seam_position",
                        "ironing_type",
                        "elefant_foot_compensation",
                        "detect_thin_wall",
                        "only_one_wall_top",
                        "skirt_loops",
                    ):
                        header[key] = value.strip()[:120]
                continue
            if line.startswith("M83"):
                absolute = False
                continue
            if line.startswith("M82"):
                absolute = True
                continue
            if line.startswith("G92"):
                found = dict(NUMBER.findall(line.split(";")[0]))
                if "E" in found:
                    last_e = float(found["E"])
                continue
            if not line.startswith(("G1 ", "G0 ", "G2", "G3")):
                continue
            values = dict(NUMBER.findall(line.split(";")[0]))
            nx, ny = float(values.get("X", x)), float(values.get("Y", y))
            moved = nx != x or ny != y
            pushed = 0.0
            if "E" in values:
                e = float(values["E"])
                pushed = (e - last_e) if absolute else e
                if absolute:
                    last_e = e
            if moved:
                length = float(np.hypot(nx - x, ny - y))
                if pushed > 0:
                    total[kind] = total.get(kind, 0.0) + length / 1000.0
                    if not (-0.5 <= nx <= BED + 0.5 and -0.5 <= ny <= BED + 0.5):
                        outside[kind] = outside.get(kind, 0) + 1
                    if 0 <= layer < 3:
                        paths = first[layer]["paths"]
                        paths[kind] = paths.get(kind, 0.0) + length
                elif 0 <= layer < 3:
                    first[layer]["travels"] += 1
                    if length > 2.0:
                        first[layer]["long_travels"] += 1
            x, y = nx, ny
    (path.parent / "config.json").write_text(json.dumps(everything, indent=0, ensure_ascii=False), encoding="utf-8")
    support = sum(v for k, v in total.items() if "support" in k.lower())
    rim = sum(v for k, v in total.items() if k.lower() in ("skirt", "brim", "skirt/brim"))
    for entry in first:
        entry["paths"] = {k: round(v) for k, v in sorted(entry["paths"].items(), key=lambda t: -t[1])}
    return {
        "paths_m": {k: round(v, 2) for k, v in sorted(total.items(), key=lambda t: -t[1])},
        "model_m": round(sum(total.values()) - support - rim, 2),
        "support_m": round(support, 2),
        "rim_m": round(rim, 2),
        "layers": layer + 1,
        "first_layers": first,
        "extrusions_off_bed": outside,
        "header": header,
    }


def slice_file(model_3mf: Path, folder: Path) -> tuple[int, str, Path | None]:
    import subprocess

    run = subprocess.run(
        [str(ELEGOO), "--arrange", "0", "--slice", "0", "--outputdir", str(folder), str(model_3mf)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    gcode = folder / "plate_1.gcode"
    return run.returncode, (run.stdout + run.stderr)[-1500:], gcode if gcode.exists() else None


def solidon_run(objects: list[Any], settings: Any, profile: Any, setup: Any, folder: Path) -> dict:
    """Solidons eigener Weg: ``write_assembly`` und ``handover.slice_model``."""
    folder.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    row: dict[str, Any] = {}
    try:
        path, findings = write_assembly(
            objects,
            folder,
            project_name="minigolf",
            profile=profile,
            settings=settings,
            flavour=setup.flavour,
            place_on_bed=True,
            setup=setup,
        )
        row["export_findings"] = [finding_row(f) for f in findings if f.severity != "info"]
        outcome = handover.slice_model(
            path, settings, profile, setup, output_dir=folder, keep_arrangement=True
        )
        metrics = outcome.metrics
        row.update(
            ok=True,
            print_minutes=round((metrics.print_seconds or 0) / 60.0, 1),
            filament_g=metrics.filament_grams,
            slice_findings=[finding_row(f) for f in outcome.findings if f.severity != "info"],
        )
        row.update(read_gcode(outcome.gcode_path))
        if not os.environ.get("KEEP_GCODE"):
            outcome.gcode_path.unlink(missing_ok=True)
    except AppError as problem:
        row.update(
            ok=False,
            error=type(problem).__name__,
            detail=str(problem)[:600],
            values={k: str(v)[:300] for k, v in (problem.values or {}).items()},
        )
    except Exception as problem:
        row.update(ok=False, error=type(problem).__name__, detail=str(problem)[:600], trace=traceback.format_exc()[-2000:])
    row["seconds"] = round(time.perf_counter() - started, 1)
    return row


def reference_run(objects: list[Any], profile: Any, setup: Any, reference: dict, folder: Path) -> dict:
    """Elegoos Herstellerprofil allein, auf derselben Geometrie."""
    folder.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    row: dict[str, Any] = {}
    try:
        path, _ = write_assembly(
            objects,
            folder,
            project_name="minigolf-geometrie",
            profile=profile,
            settings=None,
            flavour=setup.flavour,
            place_on_bed=True,
            setup=setup,
        )
        target = folder / "elegoo.3mf"
        with_project_settings(path, target, reference)
        code, output, gcode = slice_file(target, folder)
        row.update(ok=gcode is not None and code == 0, exit=code)
        if gcode is None or code != 0:
            row["output"] = output
        if gcode is not None:
            data = read_gcode(gcode)
            head = data["header"]
            minutes = None
            text = head.get("estimated printing time (normal mode)")
            if text:
                parts = dict((unit, float(n)) for n, unit in re.findall(r"(\d+)([dhms])", text))
                minutes = round(parts.get("d", 0) * 1440 + parts.get("h", 0) * 60 + parts.get("m", 0) + parts.get("s", 0) / 60, 1)
            row.update(print_minutes=minutes, filament_g=float(head["filament used [g]"]) if head.get("filament used [g]") else None)
            row.update(data)
            if not os.environ.get("KEEP_GCODE"):
                gcode.unlink(missing_ok=True)
    except Exception as problem:
        row.update(ok=False, error=type(problem).__name__, detail=str(problem)[:600], trace=traceback.format_exc()[-2000:])
    row["seconds"] = round(time.perf_counter() - started, 1)
    return row


def main() -> int:
    model = Path(sys.argv[1])
    out = Path(sys.argv[2])
    work = Path(sys.argv[3])
    base: dict[str, Any] = {"model": model.name}

    def emit(row: dict) -> None:
        with out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**base, **row}, ensure_ascii=False, default=str) + "\n")

    started = time.perf_counter()
    try:
        result, info = load(model)
    except Exception as problem:
        emit({"stage": "load", "ok": False, "error": type(problem).__name__, "detail": str(problem)[:600], "trace": traceback.format_exc()[-2000:]})
        return 1
    objects = list(result.scene.objects.values())
    meshes = [as_mesh_data(o.mesh) for o in objects]
    sizes = [np.asarray(m.bounds.maximum) - np.asarray(m.bounds.minimum) for m in meshes]
    base.update(
        bodies=len(objects),
        triangles=int(sum(m.triangle_count for m in meshes)),
        size_mm=[round(float(v), 2) for v in np.max(sizes, axis=0)] if sizes else None,
        volume_cm3=round(sum(float(m.raw.volume) for m in meshes) / 1000.0, 2) if meshes else None,
        watertight=[bool(m.raw.is_watertight) for m in meshes],
    )
    emit({"stage": "load", "ok": True, "seconds": round(time.perf_counter() - started, 2), **info})

    profile = profiles.make_profile(PRINTER, MATERIAL)
    standard = print_settings.resolve(profile)
    started = time.perf_counter()
    try:
        report = print_findings(result.scene, profile, standard)
        emit({"stage": "report", "ok": True, "seconds": round(time.perf_counter() - started, 2), "findings": [finding_row(f) for f in report]})
    except Exception as problem:
        emit({"stage": "report", "ok": False, "error": type(problem).__name__, "detail": str(problem)[:600], "trace": traceback.format_exc()[-2000:]})

    setup = handover.detect(ELEGOO)
    machine, process = slicer_profiles.match(
        list(slicer_profiles.find_profiles(ELEGOO, setup.flavour, ("machine", "process"))), profile.printer
    )
    # Wie der Druckdialog (``_choose_filament_profile``): Für das Material des
    # Projekts wählt er das Filamentprofil des Herstellers vor.
    filament = slicer_profiles.match_filament(
        list(slicer_profiles.find_profiles(ELEGOO, setup.flavour, ("filament",))),
        machine,
        "PLA",
        slicer_profiles.profile_roots(setup.flavour, ELEGOO),
    )
    setup = replace(
        setup,
        machine_profile=machine.name if machine else "",
        base_process=process.name if process else "",
        base_filament=str(filament.path) if filament else "",
    )
    started = time.perf_counter()
    try:
        taken, entries = advised(standard, profile, objects)
        emit({"stage": "advice", "ok": True, "seconds": round(time.perf_counter() - started, 2), "machine": setup.machine_profile, "process": setup.base_process, "filament": Path(setup.base_filament).stem, "advice": [[p, str(v)] for p, v in entries]})
    except Exception as problem:
        taken, entries = None, []
        emit({"stage": "advice", "ok": False, "error": type(problem).__name__, "detail": str(problem)[:600], "trace": traceback.format_exc()[-2000:]})

    try:
        reference = elegoo_reference(setup, machine, process)
    except Exception as problem:
        reference = None
        emit({"stage": "elegoo_reference", "ok": False, "error": type(problem).__name__, "detail": str(problem)[:600], "trace": traceback.format_exc()[-2000:]})

    if reference is not None:
        emit({"stage": "slice", "variant": "elegoo", **reference_run(objects, profile, setup, reference, work / "elegoo")})
        if taken is not None and taken.support.style != "none":
            with_support = dict(reference)
            with_support["enable_support"] = "1"
            emit({"stage": "slice", "variant": "elegoo_stuetzen", **reference_run(objects, profile, setup, with_support, work / "elegoo_stuetzen")})
    emit({"stage": "slice", "variant": "standard", **solidon_run(objects, standard, profile, setup, work / "standard")})
    if taken is not None:
        emit({"stage": "slice", "variant": "vorschlaege", **solidon_run(objects, taken, profile, setup, work / "vorschlaege")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
