"""Abnahme von RM-255 und RM-256 im echten ElegooSlicer.

Aufruf: python tempo_abnahme.py <code-wurzel> <modell> <v35-projekt> <bericht.txt>

RM-255: Ein Drucker ohne Tempodaten (allgemeiner Drucker) mit Elegoos Prozess
für den Centauri Carbon der ersten Reihe — das Tempo im G-Code ist das des
Herstellers, nicht Solidons 40/60/80 mm/s.

RM-256: Die Druckeinstellungen eines Projekts aus Format 35 (40 mm/s von
damals, vier Wände als eigene Wahl) am Centauri Carbon 2 — das Tempo im
G-Code ist Elegoos, die vier Wände bleiben.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
MODEL = Path(sys.argv[2]).resolve()
OLD_PROJECT = Path(sys.argv[3]).resolve()
REPORT = Path(sys.argv[4]).resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(HERE))

import app  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
load_operations()

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # RM-530: Matrix in tools/
from tools import matrix_gcode as gcode_lesen  # noqa: E402
from app.core.export import handover, slicer_profiles  # noqa: E402
from app.core.export.writer import write_assembly  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.scene.project import load  # noqa: E402

sys.argv = [sys.argv[0], str(ROOT), str(MODEL), tempfile.mkdtemp()]
import lauf  # noqa: E402  (liest seine Argumente beim Import)

EXE = Path(lauf.SLICERS["elegoo"][0])
KEYS = (
    "outer_wall_speed",
    "inner_wall_speed",
    "sparse_infill_speed",
    "travel_speed",
    "default_acceleration",
    "wall_loops",
    "initial_layer_print_height",
)
objects = lauf.load(MODEL)
setup0 = handover.detect(EXE)
roots = slicer_profiles.profile_roots(setup0.flavour, EXE)
found = list(slicer_profiles.find_profiles(EXE, setup0.flavour, ("machine", "process", "filament")))
lines: list[str] = []


def named(name: str, kind: str) -> slicer_profiles.SlicerProfile:
    return next(entry for entry in found if entry.kind == kind and entry.name == name)


def run(title: str, profile: profiles.Profile, settings, machine_name: str, process_name: str, material: str = "PLA") -> None:  # type: ignore[no-untyped-def]
    machine = named(machine_name, "machine")
    process = named(process_name, "process")
    filament = slicer_profiles.match_filament(
        [entry for entry in found if entry.kind == "filament"], machine, material, roots
    )
    assert filament is not None
    setup = replace(
        setup0,
        machine_profile=machine.name,
        base_process=process.name,
        base_filament=str(filament.path),
    )
    folder = Path(tempfile.mkdtemp(prefix="tempo-"))
    path, _findings = write_assembly(
        objects,
        folder,
        project_name="tempo",
        profile=profile,
        settings=settings,
        flavour=setup.flavour,
        place_on_bed=True,
        setup=setup,
    )
    outcome = handover.slice_model(path, settings, profile, setup, output_dir=folder, keep_arrangement=True)
    block = gcode_lesen.config_block(Path(outcome.gcode_path))
    vendor = {}
    for entry in (machine, process, filament):
        vendor.update(slicer_profiles.resolve_values(entry.path, roots=roots))
    lines.append(f"== {title}")
    lines.append(f"   {machine.name} / {process.name} / {filament.name}")
    lines.append(f"   eigene Wahl: {sorted(settings.chosen)}")
    for key in KEYS:
        wanted = vendor.get(key)
        wanted = wanted[0] if isinstance(wanted, list) and wanted else wanted
        lines.append(f"   {key:28} Hersteller {wanted!s:>8}   G-Code {block.get(key, '—'):>8}")
    warnings = [f"{f.code}" for f in outcome.findings if f.severity != "info"]
    lines.append(f"   Befunde: {warnings or 'keine'}")


# RM-255: allgemeiner Drucker, Elegoos Prozess für den CC der ersten Reihe.
generic = profiles.make_profile("generic-220", "pla")
run(
    "RM-255: allgemeiner Drucker mit dem Prozess des Centauri Carbon (erste Reihe)",
    generic,
    print_settings.resolve(generic),
    "Elegoo Centauri Carbon 0.4 nozzle",
    "0.20mm Standard @Elegoo CC 0.4 nozzle",
)

# RM-256: die Einstellungen eines Projekts aus Format 35 am Centauri Carbon 2.
old = load(OLD_PROJECT).document.print_settings
cc2 = profiles.make_profile("centauri-carbon-2", "petg")
run(
    "RM-256: Druckeinstellungen aus Format 35 (40 mm/s, vier Wände) am Centauri Carbon 2",
    cc2,
    old,
    "Elegoo Centauri Carbon 2 0.4 nozzle",
    "0.20mm Standard @Elegoo CC2 0.4 nozzle",
    "PETG",
)
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
