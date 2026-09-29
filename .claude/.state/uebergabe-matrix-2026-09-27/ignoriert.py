"""Sonde: Welche Werte meldet die Gegenprobe als „anders übernommen"?

Aufruf: python ignoriert.py <code-wurzel> <modell> <slicer> [<variante>]

Fährt Solidons Übergabe wie ``lauf.py`` (Standard oder mit Vorschlägen) und
druckt die vollständige Liste aus ``slicer.setting_ignored`` — ``lauf.py``
behält nur den Code des Befunds.
"""

from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
MODEL = Path(sys.argv[2]).resolve()
SLICER = sys.argv[3]
VARIANT = sys.argv[4] if len(sys.argv) > 4 else "standard"
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

exe_text, printer = lauf.SLICERS[SLICER]
exe = Path(exe_text)
objects = lauf.load(MODEL)
profile = profiles.make_profile(printer, lauf.MATERIAL)
setup = handover.detect(exe)
if setup.flavour == "orca":
    machine, process = slicer_profiles.match(
        list(slicer_profiles.find_profiles(exe, setup.flavour, ("machine", "process"))),
        profile.printer,
    )
    filament = slicer_profiles.match_filament(
        list(slicer_profiles.find_profiles(exe, setup.flavour, ("filament",))),
        machine,
        "PLA",
        slicer_profiles.profile_roots(setup.flavour, exe),
    )
    setup = replace(
        setup,
        machine_profile=machine.name if machine else "",
        base_process=process.name if process else "",
        base_filament=str(filament.path) if filament else "",
    )
original = handover.verify_settings


def spy(found, written):  # type: ignore[no-untyped-def]
    """Die ganze Liste, nicht die ersten zehn des Befunds."""
    for key, wanted in written.items():
        if key in handover._RECOMPUTED:
            continue
        actual = found.get(key.casefold())
        if actual is None or handover._same(actual, wanted):
            continue
        print("   ", key, ":", wanted, "→", actual)
    return original(found, written)


handover.verify_settings = spy
settings = print_settings.resolve(profile)
if VARIANT == "vorschlaege":
    settings, _entries = lauf.advised(settings, profile, objects)
folder = Path(tempfile.mkdtemp(prefix="ignoriert-"))
path, findings = write_assembly(
    objects,
    folder,
    project_name="solidon",
    profile=profile,
    settings=settings,
    flavour=setup.flavour,
    place_on_bed=True,
    setup=setup,
)
outcome = handover.slice_model(path, settings, profile, setup, output_dir=folder, keep_arrangement=True)
for finding in [*findings, *outcome.findings]:
    if finding.severity == "info":
        continue
    print(finding.severity, finding.code)
    if finding.code == "slicer.setting_ignored":
        print("  Anzahl:", finding.values.get("count"))
        for part in str(finding.values.get("settings", "")).split("; "):
            print("   ", part)
