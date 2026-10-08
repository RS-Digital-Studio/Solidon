"""Druckrat und Kanalfrage am Drachen, wie Druckdialog und Übergabe sie rechnen.

Aufruf: python sonde_rat.py <code-wurzel> <netz.stl> [drucker] [material]

Gibt aus: Überhang, Inseln, Kanalstücke (Zahl, Fläche, Höhen), offene Stücke,
die Vorschläge mit Wert und Grund und — bei übernommener Sperre — das Volumen
des Sperrkörpers.
"""
# ruff: noqa: E501

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

import app  # noqa: E402
from app.core.export import writer  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.slice.analysis import island_layers, model_support, piece_area  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__

MESH = Path(sys.argv[2])
PRINTER = sys.argv[3] if len(sys.argv) > 3 else "centauri-carbon-2"
MATERIAL = sys.argv[4] if len(sys.argv) > 4 else "pla"

if MESH.name.startswith("obj"):
    raw = trimesh.load(MESH, process=False)
else:
    from app.core.ingest.loader import read_local_payload, read_model

    raw = read_model(read_local_payload(MESH), MESH.suffix).raw
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
mesh = MeshData.of(raw)
entry = SceneObject(id="obj_1", name="Drache", mesh=mesh)
profile = profiles.make_profile(PRINTER, MATERIAL)
settings = print_settings.resolve(profile)
started = time.perf_counter()
result = writer._body_analysis(entry, mesh, settings, profile, None, detail="full")
print(f"Schnitt: {len(result.layers)} Schichten, {time.perf_counter() - started:.1f} s")
started = time.perf_counter()
need = advise.support_need(result)
model = need.model
print(f"Kanalfrage: {time.perf_counter() - started:.1f} s")
print(
    f"Stützen nötig: {need.needed}, Überhang ohne Kanäle {need.overhang:.0f} mm², größtes Stück {need.patch:.0f} mm²"
)
print(
    f"Inselschichten: {len(island_layers(result))}, Insel auf dem Modell: {model.island_on_model}"
)
all_pieces = sum(len(layer.overhangs) for layer in result.layers)
all_area = sum(piece_area(piece) for layer in result.layers for piece in layer.overhangs)
print(f"Überhangstücke gesamt: {all_pieces}, {all_area:.0f} mm²")
print(
    f"Kanalstücke: {len(model.channels)}, {model.channel_area:.0f} mm², größtes bei {model.channel_at}"
)
print(
    f"offen auf dem Modell: {len(model.open_pieces)} Stücke, {model.open_area:.0f} mm², größtes {model.open_patch:.0f} mm²"
)
bands = Counter(int(result.layers[index].z // 10) * 10 for index, _n in model.channels)
print("Kanalstücke je 10 mm:", dict(sorted(bands.items())))

entries = advise.advise(settings, profile, result, bounds=mesh.bounds)
print("\nVorschläge:")
for item in entries:
    print(f"  {item.path} = {item.value!r} ({item.severity}): {item.reason}")

taken = advise.apply(settings, entries)
if taken.support.block_channels:
    started = time.perf_counter()
    blocker, _found = writer._support_blocker(entry, mesh, taken, profile, None, result=result)
    if blocker is not None:
        raw = blocker.raw
        print(
            f"\nSperrkörper: {raw.volume:.0f} mm³ (Drache {mesh.raw.volume:.0f} mm³), {time.perf_counter() - started:.1f} s"
        )
        # Ins Arbeitsverzeichnis, nie neben das Modell: Die Modelle liegen in
        # Roberts Sammlung.
        raw.export(Path.cwd() / f"sperre-{MESH.stem}-{ROOT.name}.stl")
else:
    print("\nKeine Sperre übernommen.")
