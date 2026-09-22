"""Erlaubt nur die geprüfte Fortschreibung der fünf Nachweisdokumente."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
folder = Path((Path(__file__).parent / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
docs = set(json.loads((folder / "docs-paths.json").read_text(encoding="utf-8")))
for path, expected in snapshot["files"].items():
    actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    if path not in docs:
        assert actual == expected, path
    else:
        snapshot["files"][path] = actual
snapshot["head"] = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
).stdout.strip()
(folder / "docs-snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
print(json.dumps({"head": snapshot["head"], "docs": sorted(docs)}))
