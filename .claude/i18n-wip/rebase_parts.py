"""Rechnet Teilübersetzungen auf die eingefrorene Basis zurück.

Aufruf: python rebase_parts.py <lang> [--schreiben]

Die Teile sind indexbasiert, der lebende Katalog wächst weiter. Wer gegen
den gewachsenen Katalog übersetzt, legt seine Texte unter Indizes ab, die in
der Basis etwas anderes bedeuten — jeder neue Schlüssel verschiebt alles
über seiner Einfügestelle, und weil einsortiert wird, ist die Verschiebung
über den Bestand hinweg nicht einmal konstant.

Zugeordnet wird deshalb über den deutschen Quelltext, nicht über Arithmetik:
Für jede Datei wird geprüft, ob ihre Einträge zur Basis oder zum lebenden
Katalog passen; die zweite Sorte wird umgerechnet. Texte, die es nur im
lebenden Katalog gibt, haben in der Basis keinen Platz — sie wandern nach
new-keys-<lang>.json und gehen nicht verloren.

Ohne --schreiben passiert nichts: der Lauf meldet nur, was er täte.
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PLACEHOLDER = re.compile(r"\{[a-z_][a-z0-9_]*\}")
FIGURE = re.compile(r"!\[\]\(figure:[^)]+\)")
BLOCK = 40

lang = sys.argv[1]
schreiben = "--schreiben" in sys.argv

base_keys = list(json.loads((HERE / "base-en.json").read_text(encoding="utf-8")))
work_keys = list(json.loads((ROOT / "app/i18n/locales/en.json").read_text(encoding="utf-8")))
base_index = {key: i for i, key in enumerate(base_keys)}


def verstoesse(source: str, text: str) -> int:
    """Zählt, wie sehr eine Übersetzung nicht zu einem Quelltext passen kann."""
    zahl = 0
    if sorted(PLACEHOLDER.findall(source)) != sorted(PLACEHOLDER.findall(text)):
        zahl += 1
    if sorted(FIGURE.findall(source)) != sorted(FIGURE.findall(text)):
        zahl += 1
    if source.count("\n\n") != text.count("\n\n"):
        zahl += 1
    # Längenverhältnis: eine Übersetzung ist nie ein Zehntel oder das
    # Zehnfache ihrer Quelle. Fängt die Fälle ohne Platzhalter ab.
    if source and not 0.4 <= len(text) / len(source) <= 2.5:
        zahl += 1
    return zahl


def bewerte(entries: list[dict], keys: list[str]) -> int:
    """Summiert die Verstöße einer Datei unter der Annahme dieser Schlüsselliste."""
    summe = 0
    for entry in entries:
        i = entry["i"]
        if not 0 <= i < len(keys):
            summe += 4
            continue
        summe += verstoesse(keys[i], entry["t"])
    return summe


parts_dir = HERE / lang
werte: dict[int, str] = {}
heimatlos: dict[str, str] = {}
umgerechnet = 0

for part in sorted(parts_dir.glob("part-*.json")):
    entries = json.loads(part.read_text(encoding="utf-8"))
    auf_basis = bewerte(entries, base_keys)
    auf_lebend = bewerte(entries, work_keys)
    quelle = "Basis" if auf_basis <= auf_lebend else "lebend"
    print(f"{part.name}: Basis {auf_basis}, lebend {auf_lebend} → {quelle}")
    for entry in entries:
        i, text = entry["i"], entry["t"]
        if quelle == "Basis":
            werte[i] = text
            continue
        key = work_keys[i] if 0 <= i < len(work_keys) else None
        if key is None:
            heimatlos[f"?{i}"] = text
        elif key in base_index:
            werte[base_index[key]] = text
            umgerechnet += 1
        else:
            heimatlos[key] = text

fehlend = [i for i in range(len(base_keys)) if i not in werte]
print(f"\n{lang}: {len(werte)} Einträge auf der Basis, {umgerechnet} umgerechnet")
print(f"ohne Platz in der Basis (neue Schlüssel): {len(heimatlos)}")
for key in list(heimatlos)[:20]:
    print(f"   {key[:70]!r}")
print(f"fehlend gegen die Basis: {len(fehlend)}")
if fehlend:
    print(f"   {fehlend[:20]}")

if not schreiben:
    print("\nTrockenlauf — nichts geschrieben. Mit --schreiben ausführen.")
    raise SystemExit(0)

for alt in parts_dir.glob("part-*.json"):
    alt.unlink()
for start in range(0, len(base_keys), BLOCK):
    block = [
        {"i": i, "t": werte[i]}
        for i in range(start, min(start + BLOCK, len(base_keys)))
        if i in werte
    ]
    if not block:
        continue
    zeilen = ",\n".join(json.dumps(e, ensure_ascii=False) for e in block)
    (parts_dir / f"part-{start:04d}.json").write_text(f"[\n{zeilen}\n]\n", encoding="utf-8")
if heimatlos:
    (HERE / f"new-keys-{lang}.json").write_text(
        json.dumps(heimatlos, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
print(f"\ngeschrieben: {parts_dir}")
