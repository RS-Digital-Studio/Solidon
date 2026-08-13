"""Fügt Teil-Übersetzungen zu einer Katalogdatei zusammen.

Aufruf: python make_locale.py <lang> <teileverzeichnis>

Zwei Quellen, zwei Arten der Zuordnung:

* die `part-*.json` sind **indexbasiert** und gelten gegen `base-en.json`,
  den eingefrorenen Stand. Über den Index wird der deutsche Quelltext
  bestimmt, und der ist der eigentliche Schlüssel.
* `new-keys-<lang>.json` ist **schlüsselbasiert**: {deutscher Quelltext:
  Übersetzung}. Dort steht alles, was nach dem Einfrieren dazugekommen ist.

Geschrieben wird gegen den **lebenden** Katalog `app/i18n/locales/en.json`,
denn der entscheidet, was die Anwendung braucht. Wächst er, meldet dieser
Lauf die neuen Schlüssel namentlich, statt still eine Lücke zu lassen —
sie gehören dann in new-keys-<lang>.json.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent / "base-en.json"

lang = sys.argv[1]
parts_dir = Path(sys.argv[2])

en = json.loads(BASE.read_text(encoding="utf-8"))
keys = list(en.keys())
live = list(json.loads((ROOT / "app/i18n/locales/en.json").read_text(encoding="utf-8")))

nachtrag_datei = Path(__file__).resolve().parent / f"new-keys-{lang}.json"
nachtrag: dict[str, str] = (
    json.loads(nachtrag_datei.read_text(encoding="utf-8")) if nachtrag_datei.exists() else {}
)

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

nach_schluessel = {key: values[i] for i, key in enumerate(keys)}
nach_schluessel.update(nachtrag)

catalog: dict[str, str] = {}
ohne_uebersetzung: list[str] = []
for key in live:
    if key in nach_schluessel:
        catalog[key] = nach_schluessel[key]
    else:
        ohne_uebersetzung.append(key)

if ohne_uebersetzung:
    print(f"NICHT geschrieben: {len(ohne_uebersetzung)} Schlüssel ohne Übersetzung.")
    print(f"Sie sind seit dem Einfrieren dazugekommen und gehören in {nachtrag_datei.name}:")
    for key in ohne_uebersetzung:
        print(f"   {key}")
    raise SystemExit(1)

target = ROOT / "app/i18n/locales" / f"{lang}.json"
target.write_text(
    json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    encoding="utf-8",
)
verwaist = len(nach_schluessel) - len(catalog)
print(f"{target} geschrieben: {len(catalog)} Einträge, {verwaist} nicht mehr gebraucht")
