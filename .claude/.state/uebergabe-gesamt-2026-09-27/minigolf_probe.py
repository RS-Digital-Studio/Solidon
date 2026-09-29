"""Probe: Körper, Platten und Maße des Minigolf-Auftrags nach dem Import."""

from __future__ import annotations

import sys
from pathlib import Path

sys.argv = [sys.argv[0], sys.argv[1], r"F:\3D Druck\output\review\minigolf-2026-09-27\druckauftrag\solidon-0936.3mf", r"C:\Users\rober\AppData\Local\Temp\claude\F--3D-Druck\d53049d8-8567-40fb-bb95-f784e37acda5\scratchpad\mg", "heim"]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import os  # noqa: E402

os.environ["GESAMT_AUSRICHTEN"] = "0"
import einheit  # noqa: E402

objects, findings = einheit.load(Path(sys.argv[2]))
for entry in objects:
    mesh = einheit.as_mesh_data(entry.mesh)
    low, high = mesh.bounds.minimum, mesh.bounds.maximum
    print(entry.id, repr(str(entry.name)), "plate", entry.plate, "min", [round(v, 1) for v in low], "max", [round(v, 1) for v in high])
print(findings)
