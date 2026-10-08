"""Suiteergebnisse zusammenfassen — roh und mit der korrigierten Erwartung der Wo-Fälle.

Die Wo-Fälle verlangten bis zum 25.09.2026 das Wort „Menü"; richtig ist seit
dem 11.09. „Handlungen" (rechts im Fenster). Nachgerechnet wird aus der
gespeicherten Antwort, nicht durch einen neuen Lauf.

    python summarize.py suite_a.json [suite_b.json ...]
"""

import json
import sys
from pathlib import Path

WHERE = ("where_menu", "where_hollow")


def summary(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    results = data["results"]
    raw = sum(e["good"] for e in results)
    fixed = raw
    for e in results:
        if e["id"] in WHERE:
            corrected = not e["error"] and not e["ops"] and "Handlungen" in e["answer"]
            fixed += int(corrected) - int(e["good"])
    ambiguous = [e for e in results if e["ambiguous"]]
    calls = sum(e["calls"] for e in results)
    invalid = sum(e["invalid"] for e in results)
    part = [e for e in results if e["expects_part"]]
    param = [e for e in results if e["expects_parameter"]]
    lookups = sum(e.get("lookups", 0) for e in results)
    truncated = sum(e.get("stopped") == "truncated" for e in results)
    at_limit = sum(e.get("stopped") == "steps" for e in results)
    minutes = sum(e["seconds"] for e in results) / 60
    prompt_in = [r["in"] for e in results for r in e["requests"] if r.get("in")]
    out = [r["out"] for e in results for r in e["requests"] if r.get("out")]
    return (
        f"{data['model']:16} {Path(data['root']).name:8} Fälle {len(results):2}  "
        f"gut {raw:2} (Wo korrigiert {fixed:2})  gefragt {sum(e['asked'] for e in ambiguous)}/{len(ambiguous)}  "
        f"schemagültig {calls - invalid}/{calls}  Baustein {sum(any(o.startswith('insert_') for o in e['ops']) for e in part)}/{len(part)}  "
        f"Parameter {sum(bool(e['parameters']) for e in param)}/{len(param)}  Nachgefordert {lookups}  "
        f"am Limit {at_limit}  abgeschnitten {truncated}  Zeit {minutes:.1f} min  "
        f"Eingang max {max(prompt_in, default=0)}  Ausgabe max {max(out, default=0)}"
    )


for name in sys.argv[1:]:
    print(summary(Path(name)))
