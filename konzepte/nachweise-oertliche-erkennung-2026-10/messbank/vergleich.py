"""Messbank A1/A2 (RM-592): zwei Läufe von ``folge.py`` Zustand für Zustand vergleichen.

Aufruf::

    python vergleich.py <mit.jsonl> <ohne.jsonl> [--liste]

Verglichen wird je Zustand (Fall, Körper, Schritt) der Abdruck der rohen Erkennung samt
Nebentabellen (A1), Namen und ``object_hash`` der Szene, ob das ferne Merkmal weiterlebt,
und je Fall die Zahl der Zuordnungsfragen (A2). Gezählt wird, was beide Läufe haben; ein
Zustand nur auf einer Seite ist ein eigener Befund (die Folge lief auseinander).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

FIELDS = ("erkennung", "neben", "namen", "object_hash", "fern", "dreiecke")


def read(path: Path) -> tuple[dict[tuple[str, str, str], dict], dict[str, dict]]:
    """Zustände und Schlusszeilen eines Laufs; ein späterer Lauf desselben Falls gilt."""
    states: dict[tuple[str, str, str], dict] = {}
    ends: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("schritt") == "ende":
            ends[record["fall"]] = record
        elif record.get("schritt") != "halt":
            states[(record["fall"], record.get("objekt", ""), record["schritt"])] = record
    return states, ends


def main() -> int:
    with_memory, ends_with = read(Path(sys.argv[1]))
    without, ends_without = read(Path(sys.argv[2]))
    listing = "--liste" in sys.argv
    common = sorted(set(with_memory) & set(without))
    differing: Counter[str] = Counter()
    rows = []
    for key in common:
        left, right = with_memory[key], without[key]
        wrong = [name for name in FIELDS if left.get(name) != right.get(name)]
        for name in wrong:
            differing[name] += 1
        if wrong:
            rows.append((key, wrong))
    only_with = sorted(set(with_memory) - set(without))
    only_without = sorted(set(without) - set(with_memory))
    print(f"Zustände in beiden Läufen: {len(common)}")
    print(f"davon anders: {len(rows)}  {dict(differing)}")
    print(f"nur mit: {len(only_with)}, nur ohne: {len(only_without)}")
    steps = Counter(key[2] for key in common)
    print("je Schritt:", dict(sorted(steps.items())))
    far = [with_memory[key].get("fern") for key in common if "fern" in with_memory[key]]
    print(f"fernes Merkmal lebt: {sum(1 for value in far if value)} von {len(far)}")
    matched = sum(end.get("zuordnungen", 0) for end in ends_with.values())
    matched_without = sum(end.get("zuordnungen", 0) for end in ends_without.values())
    asked = sum(end.get("fragen", 0) for end in ends_with.values())
    asked_without = sum(end.get("fragen", 0) for end in ends_without.values())
    print(f"Zuordnungen mit/ohne: {matched}/{matched_without}, Fragen {asked}/{asked_without}")
    cases = sorted(set(ends_with) & set(ends_without))
    other = [
        case
        for case in cases
        if ends_with[case].get("zuordnungen") != ends_without[case].get("zuordnungen")
        or ends_with[case].get("fragen") != ends_without[case].get("fragen")
    ]
    print(f"Fälle: {len(cases)}, mit anderer Zahl der Zuordnungen oder Fragen: {len(other)}")
    halts = Counter(end.get("warum", "")[:60] for end in ends_with.values())
    print("Fallende (mit):", dict(halts.most_common(8)))
    detect_with = sum(
        state.get("cpu_erkennung", 0.0)
        for key, state in with_memory.items()
        if key[2] != "0_geladen"
    )
    detect_without = sum(
        state.get("cpu_erkennung", 0.0) for key, state in without.items() if key[2] != "0_geladen"
    )
    print(f"CPU Erkennung nach den Schritten mit/ohne: {detect_with:.1f}/{detect_without:.1f} s")
    if listing:
        for key, wrong in rows[:200]:
            print("ANDERS", key, wrong)
        for key in only_with[:50]:
            print("NUR MIT", key)
        for key in only_without[:50]:
            print("NUR OHNE", key)
        for case in other[:50]:
            print("ZUORDNUNG", case)
    return 1 if rows or only_with or only_without or other else 0


if __name__ == "__main__":
    raise SystemExit(main())
