"""Vergleicht zwei Läufe von sonde_minigolf.py: Merkmale je Körper und die Erkennungsläufe je Schritt.

Aufruf: python vergleich_minigolf.py <vorher.json> <nachher.json>
"""

import json
import sys

before = json.loads(open(sys.argv[1], encoding="utf-8").read())
after = json.loads(open(sys.argv[2], encoding="utf-8").read())
TOLERANCE = 1e-4

print(f"Gesamt: vorher {before['total_s']} s, nachher {after['total_s']} s")
print(f"CPU: vorher {before.get('cpu_s')} s, nachher {after.get('cpu_s')} s")
print(
    f"Erkennung gerechnet: vorher {before['fresh_detect_count']}x / {before['fresh_detect_s']} s, "
    f"nachher {after['fresh_detect_count']}x / {after['fresh_detect_s']} s"
)
print(f"Halt: {before['stopped_at']} / {after['stopped_at']}")
print("Schritt | vorher gerechnet (s) | nachher gerechnet (s) | nachher übertragen")
for step in before["steps"]:
    old = before["fresh_detect"].get(step, [])
    new = after["fresh_detect"].get(step, [])
    print(
        f"{step} | {len(old)} ({sum(old):.1f}) | {len(new)} ({sum(new):.1f}) | "
        f"{after['carried'].get(step, 0)}"
    )
print("Befunde gleich:", before["findings"] == after["findings"])
if before["findings"] != after["findings"]:
    print("  vorher", before["findings"])
    print("  nachher", after["findings"])

differences = []
count = 0
assert set(before["objects"]) == set(after["objects"])
for object_id, entry in before["objects"].items():
    old = {item["id"]: item for item in entry["features"]}
    new = {item["id"]: item for item in after["objects"][object_id]["features"]}
    if set(old) != set(new):
        differences.append(
            f"{object_id}: nur vorher {sorted(set(old) - set(new))}, nur nachher {sorted(set(new) - set(old))}"
        )
    for name in set(old) & set(new):
        count += 1
        a, b = old[name], new[name]
        for field in ("kind", "provenance", "created_by", "faces"):
            if a[field] != b[field]:
                differences.append(f"{object_id} {name}: {field} {a[field]} -> {b[field]}")
        if (a["centre"] is None) != (b["centre"] is None):
            differences.append(f"{object_id} {name}: centre {a['centre']} -> {b['centre']}")
        elif a["centre"] is not None:
            gap = max(abs(x - y) for x, y in zip(a["centre"], b["centre"], strict=True))
            if gap > TOLERANCE:
                differences.append(f"{object_id} {name}: centre um {gap:.2e}")
print(f"Körper {len(before['objects'])}, Merkmale verglichen {count}, Unterschiede {len(differences)}")
for line in differences:
    print("  ", line)
