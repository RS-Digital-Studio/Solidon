"""Auswertung von s02.jsonl: Auffälligkeiten je Körper."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

rows = [json.loads(line) for line in Path(__file__).with_name("s02.jsonl").read_text("utf-8").splitlines()]
print("Körper:", len(rows))
errors = [r for r in rows if "error" in r]
print("Fehler:", len(errors))
for r in errors:
    print("  ", r.get("file"), r.get("part"), r["error"][:200])
ok = [r for r in rows if "after_repair" in r]

codes_ingest = Counter(c for r in ok for c in r["ingest_codes"])
codes_repair = Counter(c for r in ok for c in r["repair_codes"])
print("\nImport-Befunde:", dict(codes_ingest.most_common()))
print("Reparatur-Befunde:", dict(codes_repair.most_common()))

print("\nNach Import nicht dicht:")
for r in ok:
    a = r["after_ingest"]
    if not a["tight"]:
        print(f"  {r['file']} | {r['part']}: {a} codes={r['ingest_codes']}")

print("\nNach Import dicht, aber negatives Volumen oder uneinheitlich:")
for r in ok:
    a = r["after_ingest"]
    if a["tight"] and (a["vol"] <= 0 or not a["wound"]):
        print(f"  {r['file']} | {r['part']}: {a}")

print("\nNach Reparatur nicht dicht / schlechter:")
for r in ok:
    a, b = r["after_ingest"], r["after_repair"]
    worse = (b["open"] + b["branch"]) > (a["open"] + a["branch"])
    if not b["tight"] or worse:
        print(f"  {r['file']} | {r['part']}: import={a} repair={b} codes={r['repair_codes']}")

print("\nVolumenänderung durch Reparatur > 0,5 % oder Vorzeichenwechsel:")
for r in ok:
    a, b = r["after_ingest"], r["after_repair"]
    if a["vol"] == 0:
        continue
    rel = (b["vol"] - a["vol"]) / abs(a["vol"])
    if abs(rel) > 0.005:
        print(f"  {r['file']} | {r['part']}: {a['vol']} -> {b['vol']} ({rel:+.2%}) codes={r['repair_codes']}")

print("\nTeilezahl geändert durch Reparatur:")
for r in ok:
    a, b = r["after_ingest"], r["after_repair"]
    if a["parts"] != b["parts"]:
        print(f"  {r['file']} | {r['part']}: {a['parts']} -> {b['parts']} codes={r['repair_codes']}")

print("\nLangsamste Reparaturen:")
for r in sorted(ok, key=lambda r: -r["repair_s"])[:15]:
    print(f"  {r['repair_s']:7.2f}s  tri={r['after_ingest']['tri']:>8}  {r['file']} | {r['part']}  steps={r['repair_steps']}")

print("\nLangsamste Importe:")
for r in sorted(ok, key=lambda r: -r["ingest_s"])[:10]:
    print(f"  {r['ingest_s']:7.2f}s  tri={r['raw_tri']:>8}  {r['file']} | {r['part']} codes={r['ingest_codes']}")

print("\nDurchdringungsprüfung unvollständig:")
for r in ok:
    if "repair.self_intersections_incomplete" in r["repair_codes"]:
        print(f"  tri={r['after_ingest']['tri']:>8} {r['file']} | {r['part']} steps={r['repair_steps']}")

print("\nDurchdringung gefunden und Auflösung versucht:")
for r in ok:
    if "si_codes" in r:
        print(f"  tri={r['after_ingest']['tri']:>8} {r['file']} | {r['part']}: {r['si_codes']} "
              f"{r['after_ingest']} -> {r['after_si']} {r['si_s']}s")

print("\nnothing-to-do-Kandidaten (keine Befunde, nichts geändert):",
      sum(1 for r in ok if not r["repair_codes"] and not r["repair_changed"]))
