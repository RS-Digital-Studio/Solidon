"""Legt ausschließlich die eingefrorenen P1.4-Pfade in einen privaten Index."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
folder = Path((Path(__file__).parent / "next-development-gate.txt").read_text().strip())
scope = sys.argv[1] if len(sys.argv) > 1 else "spatial"
assert scope in {"spatial", "manifest"}
paths = json.loads((folder / f"{scope}-paths.json").read_text())
environment = dict(os.environ)
environment.pop("GIT_INDEX_FILE", None)


def git(*args, env=environment):
    return subprocess.run(["git", *args], cwd=ROOT, env=env, check=True, capture_output=True).stdout


statuses = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))
assert set(statuses) == {"ruff", "format", "mypy", "suite"}
assert all(value == 0 for value in statuses.values()), statuses
snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
for path, expected in snapshot["files"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path
assert not git("diff", "--cached", "--name-only").strip()
head = git("rev-parse", "HEAD").decode().strip()
main_index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
index = folder / f"{scope}.index"
private = dict(environment, GIT_INDEX_FILE=str(index))
git("read-tree", head, env=private)
git("add", "--", *paths, env=private)
git("diff", "--cached", "--check", env=private)
staged = git("diff", "--cached", "--name-only", env=private).decode().splitlines()
assert staged == paths, (staged, paths)
stage = {"head": head, "index": str(index), "paths": paths,
         "main_index_sha256": hashlib.sha256(main_index.read_bytes()).hexdigest()}
(folder / f"{scope}-stage.json").write_text(json.dumps(stage, indent=2), encoding="utf-8")
(folder / f"{scope}-staged.diff").write_bytes(git("diff", "--cached", env=private))
print(git("diff", "--cached", "--stat", env=private).decode())
