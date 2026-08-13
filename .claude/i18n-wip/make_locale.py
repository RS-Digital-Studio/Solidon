"""Fügt Teil-Übersetzungen zu einer Katalogdatei zusammen.

Aufruf: python make_locale.py <lang> <teileverzeichnis>
Liest alle part-*.json im Verzeichnis (jeweils ein JSON-Array aus
Objekten {"i": <index>, "t": "<übersetzung>"}), prüft Vollständigkeit
gegen en.json und schreibt app/i18n/locales/<lang>.json im Format des
Einsammlers (indent=2, ensure_ascii=False, sort_keys=True).
"""

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\roschneider\Documents\Formwerk")

lang = sys.argv[1]
parts_dir = Path(sys.argv[2])

en = json.loads((ROOT / "app/i18n/locales/en.json").read_text(encoding="utf-8"))
keys = list(en.keys())

values: dict[int, str] = {}
problems: list[str] = []
for part in sorted(parts_dir.glob("part-*.json")):
    try:
        entries = json.loads(part.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        problems.append(f"{part.name}: ungültiges JSON — {error}")
        continue
    for entry in entries:
        i, t = entry["i"], entry["t"]
        if not isinstance(i, int) or not 0 <= i < len(keys):
            problems.append(f"{part.name}: unbekannter Index {i!r}")
        elif i in values and values[i] != t:
            problems.append(f"{part.name}: Index {i} doppelt mit anderem Text")
        elif not isinstance(t, str) or not t.strip():
            problems.append(f"{part.name}: leere Übersetzung bei Index {i}")
        else:
            values[i] = t

missing = [i for i in range(len(keys)) if i not in values]
if missing:
    ranges: list[tuple[int, int]] = []
    start_i = prev = missing[0]
    for m in missing[1:]:
        if m != prev + 1:
            ranges.append((start_i, prev))
            start_i = m
        prev = m
    ranges.append((start_i, prev))
    shown = ", ".join(f"{a}-{b}" for a, b in ranges)
    problems.append(f"{len(missing)} Einträge fehlen, Bereiche: {shown}")

if problems:
    print("NICHT geschrieben:")
    print("\n".join(problems))
    raise SystemExit(1)

catalog = {key: values[i] for i, key in enumerate(keys)}
target = ROOT / "app/i18n/locales" / f"{lang}.json"
target.write_text(
    json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"{target} geschrieben: {len(catalog)} Einträge")
