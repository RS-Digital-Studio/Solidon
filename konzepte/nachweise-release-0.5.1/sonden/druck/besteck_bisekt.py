"""RM-252: Welcher Wert aus Solidons Übergabe lässt ElegooSlicer am Besteckeinsatz abstürzen?

    python besteck_bisekt.py <übergabe.3mf> <arbeitsordner>

Die Übergabe-3MF trägt Solidons Werte in ``Metadata/project_settings.config``.
Geschnitten wird sie direkt mit ihren eigenen Werten (``--slice 0``); stürzt der
Slicer ab, werden die Schlüssel, in denen sie sich vom Originalprojekt
unterscheidet, halbiert auf den Wert des Originals gesetzt, bis der eine übrig
ist, der den Absturz auslöst.
"""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

SOURCE = Path("F:/3D Dateien/Modern++Cutlery+Organizer+with+Divider.3mf")
SLICER = r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe"
handover = Path(sys.argv[1])
work = Path(sys.argv[2])
work.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(SOURCE) as source:
    original = json.loads(source.read("Metadata/project_settings.config"))
with zipfile.ZipFile(handover) as given:
    ours = json.loads(given.read("Metadata/project_settings.config"))

different = sorted(
    key for key in ours if key in original and ours[key] != original[key]
)
print(f"{len(different)} Schlüssel weichen vom Originalprojekt ab", flush=True)
counter = 0


def crashes(keep_ours: list[str]) -> bool:
    """Schneidet die Übergabe mit Solidons Werten nur für ``keep_ours``."""
    global counter
    counter += 1
    settings = dict(ours)
    for key in different:
        if key not in keep_ours:
            settings[key] = original[key]
    target = work / f"lauf_{counter}.3mf"
    with zipfile.ZipFile(handover) as given, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for entry in given.namelist():
            data = given.read(entry)
            if entry == "Metadata/project_settings.config":
                data = json.dumps(settings, indent=4).encode("utf-8")
            out.writestr(entry, data)
    folder = work / f"out_{counter}"
    folder.mkdir(exist_ok=True)
    done = subprocess.run(
        [SLICER, "--slice", "0", "--outputdir", str(folder), str(target)],
        capture_output=True,
        timeout=900,
    )
    code = done.returncode & 0xFFFFFFFF
    fell = code & 0xD0000000 == 0xC0000000
    print(f"  Lauf {counter}: {len(keep_ours)} Werte von Solidon → 0x{code:08X} {'ABSTURZ' if fell else 'ok'}", flush=True)
    target.unlink(missing_ok=True)
    for path in folder.glob("*"):
        path.unlink()
    folder.rmdir()
    return fell


if not crashes(different):
    print("Die Übergabe mit allen eigenen Werten schneidet — der Absturz liegt nicht in project_settings.")
    raise SystemExit(0)

# ddmin (Zeller): die kleinste Menge von Solidons Werten, mit der der Absturz
# bleibt. Ein Lauf, der anders scheitert (etwa -50, weil eine Mischung beider
# Projekte das Teil neben das Bett legt), zählt als „nicht nachgestellt".
suspects = list(different)
granularity = 2
while len(suspects) >= 2:
    size = max(1, len(suspects) // granularity)
    chunks = [suspects[index : index + size] for index in range(0, len(suspects), size)]
    reduced = False
    for chunk in chunks:
        if crashes(chunk):
            suspects, granularity, reduced = chunk, 2, True
            break
    if not reduced:
        for chunk in chunks:
            rest = [key for key in suspects if key not in chunk]
            if rest and crashes(rest):
                suspects, granularity, reduced = rest, max(granularity - 1, 2), True
                break
    if not reduced:
        if granularity >= len(suspects):
            break
        granularity = min(len(suspects), granularity * 2)
print("Kleinste Menge, mit der der Absturz bleibt:", flush=True)
for key in suspects:
    print(f"  {key} = {str(ours[key])[:80]!r} (Original {str(original[key])[:60]!r})", flush=True)
