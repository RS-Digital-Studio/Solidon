"""Die Leistungsreihe eines Ordners als Markdown-Tabelle — je Lauf eine Zeile.

Aufruf: python budget_table.py budget-final-v10
Gelesen werden die result.json der Unterordner: Dreiecke im Bild, Bild je
Kamerastellung (Median und p95 in Millisekunden, GPU-fertig), Arbeitsspeicher
nach den Bildern und die geschätzte CPU-Fremdlast während des Laufs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def cell(value: object, digits: int = 1) -> str:
    """Zahlen mit Komma, fehlende Werte als Strich."""
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:.{digits}f}".replace(".", ",")
    return str(value)


def main() -> int:
    root = Path(__file__).resolve().parent / sys.argv[1]
    print("| Lauf | Dreiecke im Bild | Bild Median ms | p95 ms | RSS MiB | Fremdlast CPU % |")
    print("|---|---:|---:|---:|---:|---:|")
    for result in sorted(root.glob("*/result.json")):
        data = json.loads(result.read_text(encoding="utf8"))
        frames = data.get("camera_frames") or {}
        if isinstance(frames, dict) and "median_ms" not in frames:
            frames = frames.get("complete") or frames.get("gpu_complete") or next(
                (value for value in frames.values() if isinstance(value, dict) and "median_ms" in value),
                {},
            )
        context = data.get("camera_cpu_context") or {}
        load = context.get("background_cpu_estimate_percent") if isinstance(context, dict) else None
        print(
            f"| `{result.parent.name}` | {cell(data.get('displayed_triangles'))} | "
            f"{cell(frames.get('median_ms'))} | {cell(frames.get('p95_ms'))} | "
            f"{cell(data.get('rss_after_frames_mib'), 0)} | {cell(load)} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
