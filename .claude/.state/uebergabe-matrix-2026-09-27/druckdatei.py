"""Die Druckdatei für Roberts Minigolf-Platte am Centauri Carbon 2.

Aufruf: python druckdatei.py <code-wurzel> <modell> <ziel-ordner>

Wie Solidons Übergabe an den ElegooSlicer ohne Vorschläge: Maschine,
Prozess und Filament von Elegoo, Solidon schreibt nur das technisch Nötige.
Legt die 3MF (zum Öffnen im ElegooSlicer) und den gerechneten G-Code ab und
misst die erste Schicht: Stütze, Rand, Zeit, Material.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
MODEL = Path(sys.argv[2]).resolve()
TARGET = Path(sys.argv[3]).resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(HERE))

import app  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
load_operations()

from app.core.export import handover, slicer_profiles  # noqa: E402
from app.core.export.writer import write_assembly  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402

sys.argv = [sys.argv[0], str(ROOT), str(MODEL), tempfile.mkdtemp()]
import lauf  # noqa: E402  (liest seine Argumente beim Import)

exe = Path(lauf.SLICERS["elegoo"][0])
objects = lauf.load(MODEL)
profile = profiles.make_profile("centauri-carbon-2", "pla")
setup = handover.detect(exe)
roots = slicer_profiles.profile_roots(setup.flavour, exe)
machine, process = slicer_profiles.match(
    list(slicer_profiles.find_profiles(exe, setup.flavour, ("machine", "process"))), profile.printer
)
filament = slicer_profiles.match_filament(
    list(slicer_profiles.find_profiles(exe, setup.flavour, ("filament",))), machine, "PLA", roots
)
assert machine is not None and process is not None and filament is not None
setup = replace(
    setup,
    machine_profile=machine.name,
    base_process=process.name,
    base_filament=str(filament.path),
)
settings = print_settings.resolve(profile)
SLOW = os.environ.get("SOLIDON_ERSTE_SCHICHT")
STEM = "minigolf-cc2"
if SLOW:
    # Die ganze erste Schicht in diesem Tempo, als eigene Wahl. Solidons Feld
    # schreibt in der Orca-Familie bisher nur ``initial_layer_speed``; die
    # Füllung der ersten Schicht (``initial_layer_infill_speed``) kommt hier
    # dazu, wie es der Fix im Code nachzieht.
    from app.core.export import slicer_keys

    slicer_keys.TABLES["orca"] = slicer_keys.TABLES["orca"] + (
        slicer_keys.Entry("speed.first_layer", "initial_layer_infill_speed", slicer_keys._number),
    )
    settings = print_settings.with_choice(settings, "speed.first_layer", float(SLOW))
    STEM = f"minigolf-cc2-erste-schicht-{SLOW}"
TARGET.mkdir(parents=True, exist_ok=True)
work = Path(tempfile.mkdtemp(prefix="druckdatei-"))
path, findings = write_assembly(
    objects,
    work,
    project_name="minigolf-cc2",
    profile=profile,
    settings=settings,
    flavour=setup.flavour,
    place_on_bed=True,
    setup=setup,
)
outcome = handover.slice_model(path, settings, profile, setup, output_dir=work, keep_arrangement=True)
project = TARGET / f"{STEM}.3mf"
gcode = TARGET / f"{STEM}.gcode"
shutil.copyfile(path, project)
shutil.copyfile(outcome.gcode_path, gcode)
bed = (float(profile.printer.build_volume[0]), float(profile.printer.build_volume[1]))
row = lauf.measured({"ok": True, "gcode": str(gcode)}, bed)
print("Maschine:", machine.name)
print("Prozess: ", process.name)
print("Filament:", filament.name)
print("Körper:  ", len(objects))
for key in ("layers", "model_m", "support_m", "first_layer_support_m", "rim_m", "print_minutes", "start_homing", "start_purge_mm"):
    print(f"{key:24}", row.get(key))
print("Druckzeit (Slicer):", round((outcome.metrics.print_seconds or 0) / 60.0, 1), "min")
print("Filament (Slicer): ", outcome.metrics.filament_grams, "g")
for finding in [*findings, *outcome.findings]:
    if finding.severity != "info":
        print("Befund:", finding.severity, finding.code, finding.values)
print("3MF:   ", project)
print("G-Code:", gcode)
