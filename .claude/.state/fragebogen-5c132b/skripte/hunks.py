"""Hunks je Datei gegen HEAD auflisten und eine Auswahl als Patch schreiben.

    python hunks.py list <datei> ...            Hunks mit Nummer und Kurzinhalt
    python hunks.py patch <ausgabe> <datei>:<nr,nr|all> ...   Patch aus der Auswahl
"""

from __future__ import annotations

import subprocess
import sys

REPO = r"F:\3D Druck"


def diff(path: str) -> tuple[str, list[str]]:
    text = subprocess.run(
        ["git", "diff", "--no-color", "-U3", "HEAD", "--", path],
        capture_output=True,
        cwd=REPO,
        check=True,
    ).stdout.decode("utf-8")
    lines = text.splitlines(keepends=True)
    header: list[str] = []
    hunks: list[str] = []
    current: list[str] | None = None
    for line in lines:
        if line.startswith("@@"):
            if current is not None:
                hunks.append("".join(current))
            current = [line]
        elif current is None:
            header.append(line)
        else:
            current.append(line)
    if current is not None:
        hunks.append("".join(current))
    return "".join(header), hunks


def main() -> None:
    mode = sys.argv[1]
    if mode == "list":
        for path in sys.argv[2:]:
            _header, hunks = diff(path)
            print(f"=== {path}: {len(hunks)} Hunks")
            for number, hunk in enumerate(hunks, 1):
                changed = [
                    line.rstrip("\n")
                    for line in hunk.splitlines(keepends=True)[1:]
                    if line[:1] in "+-" and line[1:].strip()
                ]
                print(f"  [{number}] {hunk.splitlines()[0][:40]}  {len(changed)} Zeilen")
                for line in changed[:3]:
                    print("      " + line[:110])
        return
    out = sys.argv[2]
    parts: list[str] = []
    for spec in sys.argv[3:]:
        path, _, chosen = spec.rpartition(":")
        header, hunks = diff(path)
        numbers = range(1, len(hunks) + 1) if chosen == "all" else [int(n) for n in chosen.split(",")]
        parts.append(header + "".join(hunks[n - 1] for n in numbers))
    with open(out, "wb") as handle:
        handle.write("".join(parts).encode("utf-8"))
    print(f"{out}: {len(parts)} Dateien")


if __name__ == "__main__":
    main()
