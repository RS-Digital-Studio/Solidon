"""Solidons Standard-G-Code gegen die aufgelöste Herstellerkette halten.

Für Slicer, deren Referenzlauf das Werkzeug nicht zustande bringt (Bambu
Studio: „One of the plate is empty", -50). Abnahme von Stufe B, Konzept
Herstellerprofil: Ohne Vorschläge ist Solidons Konfiguration die des
Herstellers, bis auf das technisch Nötige.

Aufruf: python gegen_kette.py <code-wurzel> <modell> <slicer> <ausgabe.txt>

Fährt Solidons Übergabe ohne Vorschläge, behält den G-Code, liest seinen
Konfigurationsblock und vergleicht jeden Schlüssel, den Maschine, Prozess
und Filament des Herstellers nennen — bei Listen je Düsenvariante mit dem
ersten Eintrag, den der Slicer ohne Variantenwahl druckt.
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
MODEL = Path(sys.argv[2]).resolve()
SLICER = sys.argv[3]
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

sys.argv = [sys.argv[0], str(ROOT), str(MODEL), tempfile.mkdtemp()]
import lauf  # noqa: E402  (liest seine Argumente beim Import)

exe_text, printer = lauf.SLICERS[SLICER]
exe = Path(exe_text)
objects = lauf.load(MODEL)
profile = profiles.make_profile(printer, lauf.MATERIAL)
setup = handover.detect(exe)
assert setup.flavour == "orca", setup.flavour
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
folder = Path(tempfile.mkdtemp(prefix="gegen-kette-"))
path, _findings = write_assembly(
    objects,
    folder,
    project_name="solidon",
    profile=profile,
    settings=settings,
    flavour=setup.flavour,
    place_on_bed=True,
    setup=setup,
)
outcome = handover.slice_model(
    path,
    settings,
    profile,
    setup,
    output_dir=folder,
    keep_arrangement=True,
    timeout=float(os.environ.get("SOLIDON_ZEITLIMIT", "300")),
)
block = gcode_lesen.config_block(Path(outcome.gcode_path))


def printed(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def same(left: str, right: str) -> bool:
    """Gleich bis auf die Schreibweise des G-Codes: Er maskiert Zeilenumbrüche
    in Anführungszeichen und schreibt einen Punkt ``0.5x0.5`` als ``0.5,0.5``."""

    def plain(text: str) -> str:
        text = text.strip()
        if len(text) >= 2 and text[0] == text[-1] == '"':
            text = text[1:-1]
        if "\n" in text:
            # Ein Wert aus der Kette, nicht aus dem G-Code: schon im Klartext.
            return text.strip()
        out: list[str] = []
        index, inner = 0, text
        while index < len(inner):
            char = inner[index]
            if char == "\\" and index + 1 < len(inner):
                following = inner[index + 1]
                escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"'}
                out.append(escapes.get(following, "\\" + following))
                index += 2
                continue
            out.append(char)
            index += 1
        return "".join(out).strip()

    left, right = plain(left), plain(right)
    if left == right or left.replace("x", ",") == right.replace("x", ","):
        return True
    try:
        return abs(float(left.rstrip("%")) - float(right.rstrip("%"))) < 1e-6
    except ValueError:
        return False


lines = [
    f"Modell: {MODEL.name}",
    f"Slicer: {SLICER} — {machine.name} / {process.name} / {filament.name}",
    f"G-Code: {outcome.gcode_path}",
    "",
]
chain: dict[str, tuple[str, str]] = {}
for kind, entry in (("machine", machine), ("process", process), ("filament", filament)):
    for key, value in slicer_profiles.resolve_values(entry.path, roots=roots).items():
        chain[key] = (kind, printed(value))
differences = []
missing = 0
for key, (kind, wanted) in sorted(chain.items()):
    if key in gcode_lesen.TECHNICAL or key in slicer_profiles.DESCRIBING_KEYS:
        continue
    found = block.get(key)
    if found is None:
        missing += 1
        continue
    first = found.split(",")[0].split(";")[0]
    if not same(first, wanted) and not same(found, wanted):
        differences.append(f"{kind:8} {key}: Hersteller {wanted!r} → G-Code {found!r}")
lines.append(f"Schlüssel der Kette: {len(chain)}, im G-Code nicht geführt: {missing}")
lines.append(f"Abweichungen: {len(differences)}")
lines += differences
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
