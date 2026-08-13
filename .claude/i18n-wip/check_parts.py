"""Prüft die Teil-Übersetzungen gegen die Invarianten aus STAND.md.

Aufruf: python check_parts.py [lang ...]   (ohne Angabe: alle vier)

Geprüft wird je Eintrag gegen den deutschen Quelltext:
Platzhalter in geschweiften Klammern, Abbildungsmarken `![](figure:...)`,
Zahl der Absätze, und dass die Übersetzung nicht wörtlich der Quelltext ist.
Meldet jede Abweichung mit Index und Datei; Rückgabewert 1, wenn etwas
gefunden wurde.
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent / "base-en.json"
PLACEHOLDER = re.compile(r"\{[a-z_][a-z0-9_]*\}")
FIGURE = re.compile(r"!\[\]\(figure:[^)]+\)")

en = json.loads(BASE.read_text(encoding="utf-8"))
keys = list(en.keys())

languages = sys.argv[1:] or ["es", "fr", "it", "pt"]
problems: list[str] = []

for lang in languages:
    parts_dir = Path(__file__).resolve().parent / lang
    if not parts_dir.is_dir():
        problems.append(f"{lang}: kein Verzeichnis {parts_dir}")
        continue
    count = 0
    for part in sorted(parts_dir.glob("part-*.json")):
        try:
            entries = json.loads(part.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            problems.append(f"{part.name}: ungültiges JSON — {error}")
            continue
        for entry in entries:
            index, text = entry["i"], entry["t"]
            source = keys[index]
            count += 1
            where = f"{lang}/{part.name} [{index}]"
            if sorted(PLACEHOLDER.findall(source)) != sorted(PLACEHOLDER.findall(text)):
                problems.append(f"{where}: Platzhalter weichen ab")
            if sorted(FIGURE.findall(source)) != sorted(FIGURE.findall(text)):
                problems.append(f"{where}: Abbildungsmarken weichen ab")
            if source.count("\n\n") != text.count("\n\n"):
                problems.append(f"{where}: andere Zahl von Absätzen")
            if len(source) > 30 and source == text:
                problems.append(f"{where}: unübersetzt übernommen")
    print(f"{lang}: {count} Einträge geprüft")

if problems:
    print("\n".join(problems))
    raise SystemExit(1)
print("keine Abweichungen")
