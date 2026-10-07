"""Start-, End- und Wechselcode aus dem G-Code gegen die Herstellerkette.

Aufruf: python startcode_vergleich.py <druckdatei.gcode> <slicer.exe> <maschinenname>
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"F:\3D Druck.minigolf")

# RM-530: die Matrix in tools/ — angehängt, damit ``app`` weiter aus der
# Code-Wurzel kommt, die das Skript davorgelegt hat (Review 06.10.2026, N11).
sys.path.append(str(Path(__file__).resolve().parents[3]))
from tools import matrix_gcode as gcode_lesen  # noqa: E402

from app.core.export import slicer_profiles  # noqa: E402

gcode, exe_text, machine_name = sys.argv[1:4]
block = gcode_lesen.config_block(Path(gcode))
exe = Path(exe_text)
roots = slicer_profiles.profile_roots("orca", exe)
machine = next(
    entry
    for entry in slicer_profiles.find_profiles(exe, "orca", ("machine",))
    if entry.name == machine_name
)
values = slicer_profiles.resolve_values(machine.path, roots=roots)


def unescaped(text: str) -> str:
    """Wie Orca einen Zeichenkettenwert in den Konfigurationsblock schreibt,
    zurückgerechnet: in Anführungszeichen, Umbruch als ``\\n``, Backslash und
    Anführungszeichen maskiert."""
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            following = text[index + 1]
            out.append({"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"'}.get(following, "\\" + following))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


for key in ("machine_start_gcode", "machine_end_gcode", "change_filament_gcode", "layer_change_gcode", "time_lapse_gcode"):
    wanted = values.get(key)
    wanted = wanted[0] if isinstance(wanted, list) else wanted
    found = block.get(key)
    if wanted is None or found is None:
        print(f"{key}: fehlt ({'Kette' if wanted is None else 'G-Code'})")
        continue
    got = unescaped(found)
    if got == wanted:
        print(f"{key}: gleich ({len(wanted)} Zeichen)")
        continue
    at = next((n for n, (a, b) in enumerate(zip(wanted, got)) if a != b), min(len(wanted), len(got)))
    print(f"{key}: VERSCHIEDEN, Länge {len(wanted)} gegen {len(got)}, ab Zeichen {at}")
    print("   Kette:  ", repr(wanted[max(0, at - 40) : at + 60]))
    print("   G-Code: ", repr(got[max(0, at - 40) : at + 60]))
