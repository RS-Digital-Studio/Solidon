"""Zeigt den aktuellen Modellprüfstand ohne große Ergebnisdateien auszugeben."""
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parent
phase = sys.argv[1] if len(sys.argv) > 1 else "final"
for path in sorted((root / phase).glob("*/file-*/result.json")):
    data = json.loads(path.read_text(encoding="utf8"))
    checks = data.get("checks", [])
    navigation = next((row for row in checks if row["label"] == "Navigation fertiger Bilder"), {})
    clicks = next((row for row in checks if row["label"] == "Oberflächenklicks"), {})
    process = path.with_name("process.json")
    outcome = json.loads(process.read_text(encoding="utf8")) if process.exists() else {}
    print(json.dumps({"case":str(path.parent.relative_to(root)),
        "complete":data.get("complete"), "closed":data.get("closed"), "exit":outcome.get("exit"),
        "fatal":data.get("fatal"), "last":[row["label"] for row in checks[-3:]],
        "cpu":navigation.get("cpu"), "frame_ms":navigation.get("median_ms"),
        "clicks":{key:clicks.get(key) for key in ("passed","independent_comparisons","coverage_complete")},
        "shots":data.get("screenshots", [])[-3:]}, ensure_ascii=False))
