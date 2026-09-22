"""Hält echtes Gesamtergebnis und getrennte Commitprüfung im gemeinsamen Baum fest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path((STATE / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
full = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))
own = json.loads((folder / "own-static-exits.json").read_text(encoding="utf-8-sig"))
snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
assert set(full) == {"ruff", "format", "mypy", "suite"}
assert full["mypy"] == full["suite"] == own["ruff"] == own["format"] == 0, (full, own)
assert own["excluded"] == "konzepte/nachweise-cad-p2-7/"
for path, expected in snapshot["files"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
scopes = ["flush", "deviation", "docs"]
for scope in scopes:
    paths = json.loads((folder / f"{scope}-paths.json").read_text(encoding="utf-8"))
    assert all(not path.startswith(own["excluded"]) for path in paths)
counts = set(re.findall(r"(\d+) passed, (\d+) skipped", (folder / "suite.txt").read_text(encoding="utf-8-sig")))
assert len(counts) == 1, counts
passed, skipped = next(iter(counts))
report = {
    "full_statuses": full,
    "statuses": {"ruff": own["ruff"], "format": own["format"], "mypy": full["mypy"], "suite": full["suite"]},
    "excluded": [own["excluded"]],
    "scope": scopes,
    "passed": int(passed), "skipped": int(skipped),
    "note": "Vollständige Kernsammlung; Ruff/Format ohne den fremden parallelen P2.7-Nachweisordner. Das unbeschränkte Gesamtergebnis bleibt separat erhalten.",
}
(folder / "commit-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
helper = folder / "commit_scope.py"
code = helper.read_text(encoding="utf-8")
(folder / "commit_scope_unscoped.py").write_text(code, encoding="utf-8")
anchor = 'statuses = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))'
replacement = '''validation = json.loads((folder / "commit-validation.json").read_text(encoding="utf-8"))
assert scope in validation["scope"]
assert validation["excluded"] == ["konzepte/nachweise-cad-p2-7/"]
assert all(not path.startswith(tuple(validation["excluded"])) for path in stage["paths"])
assert validation["full_statuses"]["suite"] == validation["full_statuses"]["mypy"] == 0
statuses = validation["statuses"]'''
assert code.count(anchor) == 1
helper.write_text(code.replace(anchor, replacement), encoding="utf-8")
(STATE / "current-cad-commit-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
