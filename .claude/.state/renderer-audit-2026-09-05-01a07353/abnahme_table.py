"""Die Modellmatrix einer Phase als Markdown-Tabelle für ABNAHME.md.

Aufruf: python abnahme_table.py [phase] [renderer]  (Vorgabe: final-v10 gfx)

Gezählt wird nur, was der Lauf selbst sagt: ``complete`` und ``closed`` aus
result.json, der Prozessausgang aus process.json, die roten Prüfungen als
Zahl. Die Kennzahlen sind Mediane in Millisekunden aus demselben Lauf.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def metric(checks: list[dict], label: str, kind: str | None = None) -> float | None:
    for row in checks:
        if row.get("label") == label and (kind is None or row.get("kind") == kind):
            return row.get("median_ms")
    return None


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else "final-v10"
    renderer = sys.argv[2] if len(sys.argv) > 2 else "gfx"
    files = json.loads((ROOT / "manifest.json").read_text(encoding="utf8"))
    print(
        "| Nr. | Datei | Ausgang | rot | Import s | Zug ms | Fläche ms | Namen ms | Hover ms |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for entry in files:
        case = ROOT / phase / renderer / f"file-{entry['index']:02d}"
        result = case / "result.json"
        process = case / "process.json"
        if not result.exists():
            print(f"| {entry['index']} | `{entry['name']}` | kein Lauf | | | | | | |")
            continue
        data = json.loads(result.read_text(encoding="utf8"))
        checks = data.get("checks", [])
        exit_code = None
        if process.exists():
            exit_code = json.loads(process.read_text(encoding="utf8")).get("exit")
        state = (
            "vollständig, Exit 0"
            if data.get("complete") and data.get("closed") and exit_code == 0
            else f"unvollständig, Exit {exit_code}"
        )
        red = sum(1 for row in checks if row.get("passed") is False)
        seconds = next(
            (row.get("seconds") for row in checks if row.get("label") == "Import und Erkennung"),
            None,
        )

        def cell(value: float | None, digits: int = 1) -> str:
            return "–" if value is None else f"{value:.{digits}f}".replace(".", ",")

        print(
            f"| {entry['index']} | `{entry['name']}` | {state} | {red} | {cell(seconds)} "
            f"| {cell(metric(checks, 'Navigation fertiger Bilder'))} "
            f"| {cell(metric(checks, 'Darstellungsleistung', 'solid'))} "
            f"| {cell(metric(checks, 'Darstellungsleistung', 'feature-labels'))} "
            f"| {cell(metric(checks, 'Hover Merkmalssuche'))} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
