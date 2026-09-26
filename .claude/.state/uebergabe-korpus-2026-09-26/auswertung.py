"""Wertet ergebnis.jsonl aus: Tabelle je Modell und Slicer, dazu die Auffälligkeiten.

Aufruf: python auswertung.py <ergebnis.jsonl>

Auffällig ist:
- ein Lauf ohne Druckdatei (Import, Vorschläge oder Slicer gescheitert),
- eine Warnung aus Export oder Gegenprobe des Slicers,
- eine Kanalsperre, mit der sich die Modellbahn um mehr als 0,5 % ändert,
- übernommene Vorschläge mit Stützen, aber ohne Stützbahn im G-Code,
- eine Druckzeit oder Filamentmenge von null.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    rows = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()]
    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_model[row["model"]].append(row)
    notes: list[str] = []
    print("| Modell | Körper | Slicer | Variante | Ergebnis | Zeit min | g | Modell m | Stütze m |")
    print("|---|---|---|---|---|---|---|---|---|")
    for model, entries in by_model.items():
        runs = {(r.get("slicer"), r.get("variant")): r for r in entries}
        for row in entries:
            if row.get("stage") == "import":
                notes.append(
                    f"{model}: Import gescheitert — {row.get('error')}: {row.get('detail')}"
                )
                continue
            ok = row.get("ok")
            result = "ok" if ok else f"**{row.get('error')}**"
            print(
                f"| {model[:38]} | {row.get('bodies')} | {row['slicer']} | {row['variant']} "
                f"| {result} | "
                f"{row.get('print_minutes', '')} | {row.get('filament_g', '')} | "
                f"{row.get('model_m', '')} | {row.get('support_m', '')} |"
            )
            where = f"{model} · {row['slicer']} · {row['variant']}"
            if not ok:
                notes.append(f"{where}: {row.get('error')} — {row.get('detail')}")
                continue
            for warning in row.get("warnings", []):
                notes.append(f"{where}: Warnung {warning['code']} — {warning['text']}")
            if not row.get("print_minutes") or not row.get("model_m"):
                notes.append(f"{where}: Zeit oder Modellbahn null")
            advice = dict(tuple(pair) for pair in row.get("advice", []))
            style = advice.get("support.style")
            if style and style != "none" and not row.get("support_m"):
                notes.append(f"{where}: Vorschlag {style}, aber keine Stützbahn im G-Code")
            if row.get("advice_error"):
                notes.append(f"{where}: Vorschläge gescheitert — {row['advice_error']}")
        for slicer in {r.get("slicer") for r in entries}:
            with_blocker = runs.get((slicer, "vorschlaege"))
            without = runs.get((slicer, "vorschlaege_ohne_sperre"))
            if with_blocker and without and with_blocker.get("ok") and without.get("ok"):
                a, b = with_blocker.get("model_m") or 0, without.get("model_m") or 0
                change = (a - b) / b * 100 if b else 0.0
                line = (
                    f"{model} · {slicer}: Sperre Modellbahn {a} gegen {b} m ({change:+.2f} %), "
                    f"Stütze {with_blocker.get('support_m')} gegen {without.get('support_m')} m"
                )
                notes.append(("AUFFÄLLIG " if abs(change) > 0.5 else "") + line)
    print()
    print("## Auffälligkeiten")
    for note in notes:
        print(f"- {note}")
    failed = sum(1 for r in rows if r.get("ok") is False)
    print(f"\n{len(rows)} Läufe, davon {failed} ohne Druckdatei.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
