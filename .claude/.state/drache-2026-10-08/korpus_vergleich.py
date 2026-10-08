"""Vergleicht korpus-vorher.jsonl mit korpus-nachher.jsonl je Körper.

Aufruf: python korpus_vergleich.py <vorher.jsonl> <nachher.jsonl>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def rows(path: str) -> dict[tuple[str, str], dict]:
    found = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        found[(Path(row["file"]).name, row.get("body", ""))] = row
    return found


before, after = rows(sys.argv[1]), rows(sys.argv[2])
same = changed = 0
for key in sorted(before.keys() & after.keys()):
    old, new = before[key], after[key]
    if "error" in old or "error" in new:
        print("FEHLER", key, old.get("error"), new.get("error"))
        continue
    fields = ("needed", "channels", "channel_area", "blocker_mm3", "advice")
    if all(old.get(name) == new.get(name) for name in fields):
        same += 1
        continue
    changed += 1
    print(f"== {key[0]} / {key[1]}")
    for name in fields:
        if old.get(name) != new.get(name):
            print(f"   {name}: {old.get(name)} -> {new.get(name)}")
print(
    f"gleich {same}, verschieden {changed}, nur vorher {len(before.keys() - after.keys())}, "
    f"nur nachher {len(after.keys() - before.keys())}"
)
