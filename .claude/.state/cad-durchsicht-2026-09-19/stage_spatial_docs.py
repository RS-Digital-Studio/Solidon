"""Übernimmt nur die belegte P1.4b-Fortschrittszeile in einen privaten Index."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path((STATE / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
paths = ["ROADMAP.md"]
environment = dict(os.environ)
environment.pop("GIT_INDEX_FILE", None)


def git(*args, env=environment):
    return subprocess.run(["git", *args], cwd=ROOT, env=env, check=True, capture_output=True).stdout


exits = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))
assert set(exits) == {"ruff", "format", "mypy", "suite"}
assert all(value == 0 for value in exits.values()), exits
snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
for path, expected in snapshot["files"].items():
    actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    if path in paths:
        snapshot["files"][path] = actual
    else:
        assert actual == expected, path
head = git("rev-parse", "HEAD").decode().strip()
assert not git("diff", "--cached", "--name-only").strip()
assert git("diff", "--name-only", "HEAD").decode().splitlines() == paths
snapshot["head"] = head
(folder / "docs-snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "docs-paths.json").write_text(json.dumps(paths), encoding="utf-8")
main_index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
index = folder / "docs.index"
private = dict(environment, GIT_INDEX_FILE=str(index))
git("read-tree", head, env=private)
git("add", "--", *paths, env=private)
git("diff", "--cached", "--check", env=private)
assert git("diff", "--cached", "--name-only", env=private).decode().splitlines() == paths
stage = {"head": head, "index": str(index), "paths": paths,
         "main_index_sha256": hashlib.sha256(main_index.read_bytes()).hexdigest()}
(folder / "docs-stage.json").write_text(json.dumps(stage, indent=2), encoding="utf-8")
(folder / "docs-staged.diff").write_bytes(git("diff", "--cached", env=private))
(folder / "docs-message.txt").write_text(
    "Gruppenentscheidungen belegen und native Neuwahl als nächsten Anschluss führen\n\n"
    "P1.4b hält die gemeinsamen Ansprüche, vollständigen Antworten und\n"
    "Merkmalsbindungen auch durch Cache, Wiederöffnung und Undo/Redo zusammen.\n"
    "P1.4c bleibt für die ausdrückliche native Flächen- und Kantenneuwahl offen;\n"
    "die Produktionsgrenze und die Release-Abnahme bleiben unverändert.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8")
print(git("diff", "--cached", "--stat", env=private).decode())
