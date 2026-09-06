"""Versioniert die neue Export- und Pixelprüfung, nachdem V7 vollständig gesichert ist."""

from pathlib import Path
import ast
import hashlib
import json

root = Path(__file__).resolve().parent
path = root / "helper-pins.json"
previous = json.loads(path.read_text(encoding="utf-8"))
assert previous["version"] == 7
assert previous == json.loads((root / "helpers-v7/helper-pins.json").read_text(encoding="utf-8"))
names = (*previous["hashes"], "stl_export_checks.py", "surface_pick_footprint.py")
for name in names:
    ast.parse((root / name).read_text(encoding="utf-8"))
history = [*previous["history"], {key: value for key, value in previous.items() if key != "history"}]
record = {"version": 8,
          "reason": "STL unabhängig mit vollständigen orientierten Welt-Dreiecksmengen vergleichen; rote Oberflächenpixel mit Originalnetz und exakter Pose sichern",
          "hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names},
          "history": history}
path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print("Neue neun Prüfbausteine als Version 8 festgehalten")
