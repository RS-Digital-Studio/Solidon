"""Hunks einer Datei auflisten und einen Blob „HEAD plus ausgewählte Hunks" bauen.

Aufruf:
  python hunks.py list <datei>                    — Hunks mit Nummer und Anfang
  python hunks.py stage <index-datei> <datei> <nummern|all>
                                                  — Blob bauen, in den Index legen,
                                                    und den Rest (fremde Hunks) zeigen

Die Hunks kommen aus ``git diff -U0`` gegen HEAD und werden von unten nach oben
auf den HEAD-Stand gelegt; so verschmilzt kein Hunk mit einer fremden Zeile.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def hunks(path: str) -> list[dict]:
    diff = subprocess.run(
        ["git", "diff", "-U0", "--no-color", "HEAD", "--", path],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.splitlines()
    found: list[dict] = []
    current = None
    for line in diff:
        match = HEADER.match(line)
        if match:
            old_start, old_count = int(match.group(1)), int(match.group(2) or 1)
            current = {"old_start": old_start, "old_count": old_count, "plus": [], "minus": [], "head": line}
            found.append(current)
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current["plus"].append(line[1:])
        elif current is not None and line.startswith("-") and not line.startswith("---"):
            current["minus"].append(line[1:])
    return found


def head_text(path: str) -> str:
    return subprocess.run(
        ["git", "show", f"HEAD:{path}"], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def main() -> None:
    action = sys.argv[1]
    if action == "list":
        for number, hunk in enumerate(hunks(sys.argv[2])):
            sample = (hunk["plus"] or hunk["minus"] or [""])[:2]
            print(f"{number:3d} {hunk['head'][:60]:60s} -{len(hunk['minus'])} +{len(hunk['plus'])}  {' | '.join(s.strip()[:70] for s in sample)}")
        return
    index_file, path, chosen = sys.argv[2], sys.argv[3], sys.argv[4]
    all_hunks = hunks(path)
    numbers = range(len(all_hunks)) if chosen == "all" else [int(n) for n in chosen.split(",")]
    lines = head_text(path).split("\n")
    for number in sorted(numbers, key=lambda n: all_hunks[n]["old_start"], reverse=True):
        hunk = all_hunks[number]
        start = hunk["old_start"] - 1 if hunk["old_count"] else hunk["old_start"]
        lines[start : start + hunk["old_count"]] = hunk["plus"]
    text = "\n".join(lines)
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"], input=text.encode("utf-8"), capture_output=True, check=True
    ).stdout.decode().strip()
    mode = "100644"
    environment = dict(os.environ, GIT_INDEX_FILE=index_file)
    subprocess.run(["git", "update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}"], env=environment, check=True)
    working = open(path, encoding="utf-8", newline="").read()
    rest = subprocess.run(
        ["git", "diff", "--no-index", "--stat", "-", path], input=text, capture_output=True, text=True, encoding="utf-8"
    )
    print(f"{path}: {len(list(numbers))} Hunks gelegt, Blob {blob[:10]}; Rest zum Arbeitsbaum: {'keiner' if text == working else rest.stdout.strip().splitlines()[-1] if rest.stdout.strip() else 'unterschiedlich'}")


main()
