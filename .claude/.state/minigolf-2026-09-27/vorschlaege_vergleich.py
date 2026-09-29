"""Stellt die Druckvorschläge vor und nach der Überhanggrenze je Drucker gegenüber.

Aufruf: python vorschlaege_vergleich.py <alt.jsonl> <neu.jsonl> [bericht.md]

Je Drucker: wie viele Körper Stützen gewinnen oder verlieren, wie sich Ort
und Sperre ändern, was sich sonst ändert — und für den allgemeinen Drucker,
dessen Grenze gleich bleibt, ob wirklich nichts anders ist (die Kontrolle).
"""
# ruff: noqa: E501

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


BROKEN: list[str] = []


def rows(path: Path) -> dict:
    """Die Zeilen je Körper und Drucker. Zwei Prozesse hängen an dieselbe Datei
    an; eine dabei zerrissene Zeile wird gezählt, nicht geglaubt."""
    found = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            BROKEN.append(f"{path.name}:{number}")
            continue
        if row.get("stage") == "load":
            found[(row["file"], "(Laden)", "-")] = row
            continue
        found[(row["file"], row["body"], row["printer"])] = row
    return found


def advice_of(row: dict) -> dict:
    return {path: value for path, value in row.get("advice", [])}


def main() -> int:
    old, new = rows(Path(sys.argv[1])), rows(Path(sys.argv[2]))
    report = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    lines: list[str] = []
    say = lines.append
    keys = sorted(set(old) & set(new))
    say(f"Gemeinsam gemessen: {len(keys)} (alt {len(old)}, neu {len(new)})")
    if BROKEN:
        say(f"Zerrissene Zeilen: {len(BROKEN)} ({', '.join(BROKEN)})")
    missing = sorted(set(old) ^ set(new))
    if missing:
        say(f"Nur auf einer Seite: {len(missing)}")
        for key in missing[:20]:
            say(f"   {key}")
    errors = [(k, r.get("error")) for side in (old, new) for k, r in side.items() if r.get("error")]
    say(f"Fehler: {len(errors)}")
    for key, error in errors[:20]:
        say(f"   {key}: {error}")

    by_printer: dict[str, Counter] = defaultdict(Counter)
    lost: dict[str, list] = defaultdict(list)
    gained: dict[str, list] = defaultdict(list)
    other: dict[str, Counter] = defaultdict(Counter)
    control: list = []
    for key in keys:
        a, b = old[key], new[key]
        if a.get("error") or b.get("error") or key[1] == "(Laden)":
            continue
        printer = key[2]
        by_printer[printer]["Körper"] += 1
        before, after = advice_of(a), advice_of(b)
        had, has = "support.style" in before, "support.style" in after
        if had and not has:
            lost[printer].append((key, a, b))
        elif has and not had:
            gained[printer].append((key, a, b))
        by_printer[printer]["Stützen vorher"] += had
        by_printer[printer]["Stützen nachher"] += has
        for path in sorted(set(before) | set(after)):
            if path == "support.style":
                continue
            if before.get(path) != after.get(path):
                other[printer][f"{path}: {before.get(path)} -> {after.get(path)}"] += 1
        if printer == "generic-220" and (
            before != after or a.get("overhang") != b.get("overhang") or a.get("patch") != b.get("patch")
        ):
            control.append((key, a, b))

    for printer in sorted(by_printer):
        counts = by_printer[printer]
        say("")
        say(f"== {printer}: {counts['Körper']} Körper, Stützvorschlag {counts['Stützen vorher']} -> {counts['Stützen nachher']}")
        say(f"   verliert Stützen: {len(lost[printer])}, gewinnt Stützen: {len(gained[printer])}")
        for change, count in other[printer].most_common(15):
            say(f"   {count:4d} x {change}")
        for label, group in (("verliert", lost[printer]), ("gewinnt", gained[printer])):
            for key, a, b in sorted(group, key=lambda item: -item[1].get("overhang", 0))[:60]:
                name = Path(key[0]).name
                say(
                    f"   {label}: {name} · {key[1]} · Überhang {a.get('overhang')} (Stück {a.get('patch')}) -> {b.get('overhang')} (Stück {b.get('patch')}), Inseln {a.get('islands')}/{b.get('islands')}"
                )
    say("")
    say(f"KONTROLLE allgemeiner Drucker: {len(control)} Abweichungen")
    for key, a, b in control[:20]:
        say(f"   {key}: {a.get('advice')} / {b.get('advice')} · {a.get('overhang')} / {b.get('overhang')}")
    text = "\n".join(lines)
    print(text)
    if report:
        report.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
