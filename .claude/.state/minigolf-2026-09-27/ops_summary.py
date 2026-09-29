"""Fasst die Ergebnisse von probe_ops.py zusammen: je Operation und Merkmalsart gefahren, verweigert, Probleme."""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

folder = Path(sys.argv[1])
stats = defaultdict(Counter)
problems = []
for path in sorted(folder.glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    for body in data.get("bodies", []):
        for op in body.get("ops", []):
            key = (op["op"], op["kind"])
            stats[key]["gefahren"] += 1
            if op.get("complete") is False:
                codes = [f["code"] for f in op.get("findings", []) if f["severity"] == "error"]
                stats[key]["abgelehnt"] += 1
                stats[key]["abgelehnt:" + ",".join(codes)] += 1
            if op.get("exception"):
                problems.append((data["file"], op["feature"], op["op"], "AUSNAHME " + str(op["exception"])[:200]))
            for problem in op.get("problems", []):
                problems.append((data["file"], op["feature"], op["op"], problem))
            for f in op.get("findings", []):
                if f["severity"] == "warning":
                    stats[key]["warnung:" + f["code"]] += 1
    for err in data.get("errors", []):
        problems.append((data["file"], "-", "-", "FEHLER " + str(err)[:300]))
for key in sorted(stats):
    print(key, dict(stats[key]))
print()
for row in problems:
    print(" | ".join(row))
