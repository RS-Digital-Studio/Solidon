"""Abnahme von Stufe F im echten Slicer (Konzept Herstellerprofil, Abschnitt 4).

Aufruf: python stufen_abnahme.py <code-wurzel> <ausgabeordner>
Je Slicer, Drucker und Qualität: Einrichtung wie der Druckdialog (match, dann
manufacturer.for_stage), Einstellungen = Grundlage ohne eigene Wahl, Platte mit
einem Würfel schreiben und slicen. Aus dem G-Code: Schichthöhe, der Prozess im
Konfigurationsblock, die Befunde der Übergabe (Gegenprobe). Danach
Stufenwechsel hin und zurück: dieselbe Einrichtung, dieselbe Grundlage.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.export import handover, manufacturer, slicer_profiles, threemf  # noqa: E402
from app.core.export.writer import write_assembly  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

CASES = (
    ("elegoo", r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe", "centauri-carbon-2"),
    ("bambu", r"C:\Program Files\Bambu Studio\bambu-studio.exe", "bambu-p1s"),
    ("prusa", r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe", "prusa-mk4s"),
)
CUBE = ROOT / "tests" / "data" / "meshes" / "cube_clean.stl"
PRINT_ID = re.compile(r"^;\s*print_settings_id\s*=\s*(.+?)\s*$", re.MULTILINE)
LAYER = re.compile(r"^;\s*layer_height\s*=\s*([0-9.]+)", re.MULTILINE)

# Ein sauberer Würfel auf dem Bett: read_mesh liefert das rohe STL ohne die
# Aufbereitung des Imports, und dessen Warnungen gehören nicht zur Stufe.
import trimesh  # noqa: E402

box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
box.apply_translation((0.0, 0.0, 10.0))
mesh = MeshData.of(box)
assert CUBE.exists() and read_mesh is not None
body = SceneObject(id="cube", name="Würfel", mesh=mesh)
report: list[dict[str, object]] = []
for slicer, path, printer_id in CASES:
    exe = Path(path)
    profile = profiles.make_profile(printer_id, "pla")
    detected = handover.detect(exe)
    found = slicer_profiles.find_profiles(exe, detected.flavour, ("machine", "process", "filament"))
    machine, process = slicer_profiles.match(found, profile.printer)
    if machine is None or process is None:
        report.append({"slicer": slicer, "printer": printer_id, "skip": "keine Vorwahl"})
        continue
    filament = slicer_profiles.match_filament(found, machine, "PLA")
    base = replace(
        detected,
        machine_profile=slicer_profiles.identity(machine),
        base_process=slicer_profiles.identity(process),
        base_filament=slicer_profiles.identity(filament) if filament else "",
    )
    for quality in ("standard", "fine", "draft", "strong"):
        setup = manufacturer.for_stage(base, profile, quality)
        assert setup is not None
        foundation = manufacturer.base_settings(profile, quality, setup)
        settings = manufacturer.effective(None, foundation)
        folder = OUT / f"{slicer}__{printer_id}" / quality
        folder.mkdir(parents=True, exist_ok=True)
        row: dict[str, object] = {
            "slicer": slicer,
            "printer": printer_id,
            "quality": quality,
            "process": Path(setup.base_process).stem if setup.flavour != "prusa" else setup.base_process,
            "staged": sorted(foundation.staged),
            "foundation_layer": settings.layers.layer_height,
        }
        started = time.perf_counter()
        try:
            written, found_export = write_assembly(
                [body], folder, project_name="wuerfel", profile=profile, plate=0,
                settings=settings, flavour=setup.flavour, place_on_bed=True, setup=setup,
            )
            parts = [threemf.AssemblyPart(mesh=mesh, slots=threemf.slots_for_object(body))]
            outcome = handover.slice_model(
                [written], settings, profile, setup, output_dir=folder, timeout=300,
                keep_arrangement=True, slots=threemf.merge_slots(parts),
            )
            text = outcome.gcode_path.read_text(encoding="utf-8", errors="replace")
            printed = PRINT_ID.findall(text)
            layers = LAYER.findall(text)
            row.update(
                ok=True,
                gcode_process=printed[-1] if printed else "",
                gcode_layer=float(layers[-1]) if layers else None,
                findings=sorted({f"{f.severity}:{f.code}" for f in [*found_export, *outcome.findings]}),
            )
        except Exception as problem:  # noqa: BLE001 — eine Abnahme berichtet alles
            row.update(ok=False, error=type(problem).__name__, detail=str(problem)[:300])
        row["seconds"] = round(time.perf_counter() - started, 1)
        report.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    # Hin und zurück: Standard → Fein → Standard ergibt dieselbe Einrichtung.
    there = manufacturer.for_stage(base, profile, "fine")
    back = manufacturer.for_stage(base, profile, "standard")
    report.append({"slicer": slicer, "printer": printer_id, "round_trip": back == base and there != base})

(OUT / "abnahme.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
