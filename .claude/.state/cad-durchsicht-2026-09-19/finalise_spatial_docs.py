"""Prüft den abgeschlossenen Indexabgleich nach einer verwaisten Git-Sperre."""

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path((STATE / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
commit = "ee16040e7ba010135060ac468c3efdd2dc46b975"


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


assert git("rev-parse", "HEAD").decode().strip() == commit
assert git("rev-parse", f"{commit}^").decode().strip() == "d483e14778d141eb72f618fa173eccca5421153a"
assert not git("diff", "--cached", "--name-only").strip()
assert not git("diff", "--name-only", "HEAD").strip()
assert git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).decode().splitlines() == ["ROADMAP.md"]
snapshot = json.loads((folder / "docs-snapshot.json").read_text(encoding="utf-8"))
for path, expected in snapshot["files"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
(folder / "docs-commit.json").write_text(json.dumps({"commit": commit, "paths": ["ROADMAP.md"],
    "index_reconciliation": "Nach Sicherung einer leeren verwaisten Sperre abgeschlossen"}, indent=2), encoding="utf-8")
for name in ("current-development-gate.txt", "current-cad-commit-gate.txt"):
    (STATE / name).write_text(str(folder), encoding="utf-8")
print(json.dumps({"commit": commit, "verified_files": len(snapshot["files"]), "index": "clean"}))
