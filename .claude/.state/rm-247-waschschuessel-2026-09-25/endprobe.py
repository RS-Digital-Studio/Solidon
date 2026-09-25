"""Endprobe: Solidons eigene Übergabe für die Schüssel, mit angenommenen Vorschlägen,
durch den echten Übergabeweg (`handover.project_settings`) in den ElegooSlicer."""

import json
import subprocess
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

import trimesh

from app.core.export import handover
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.slice import advise
from app.core.slice.analysis import slice_body

S = Path(r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\5a618bfd-281d-49da-a2e6-53d607465f68\scratchpad")
m = trimesh.load(S / "out" / "bowl_washing_bowl_v1.stl")
m.apply_translation([128, 128, 0])
mesh = MeshData(m)
profile = profiles.make_profile("centauri-carbon-2", "pla")
start = print_settings.resolve(profile)
# Wie Roberts Projekt: Stützen überall, Leerfahrt von vorher.
start = print_settings.with_path(start, "speed.travel", 150.0)
result = slice_body(
    mesh,
    start.layers.layer_height,
    first_layer_height=start.layers.first_layer_height,
    bridge_from=profile.minimum_wall_thickness,
    support_volume=False,
)
entries = advise.advise(start, profile, result, bounds=mesh.bounds)
for entry in entries:
    print("Vorschlag", entry.path, entry.was, "->", entry.value)
settings = advise.apply(start, entries)
setup = replace(
    handover.detect(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe"),
    machine_profile="Elegoo Centauri Carbon 2 0.4 nozzle",
    base_process="0.20mm Standard @Elegoo CC2 0.4 nozzle",
)
document = handover.project_settings(settings, profile, setup)
for key in ("enable_support", "support_type", "support_on_build_plate_only", "support_base_pattern", "travel_speed"):
    print(" ", key, "=", document.get(key))
source = zipfile.ZipFile(S / "uebergabe.3mf")
target = S / "endprobe" / "in.3mf"
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
    for item in source.infolist():
        data = source.read(item.filename)
        if item.filename == "Metadata/project_settings.config":
            data = json.dumps(document, indent=1).encode()
        out.writestr(item, data)
run = subprocess.run(
    [str(setup.executable), "--arrange", "0", "--slice", "0", "--outputdir", str(target.parent), str(target)],
    capture_output=True,
    text=True,
)
print("Slicer-Exit", run.returncode)
sys.exit(run.returncode)
