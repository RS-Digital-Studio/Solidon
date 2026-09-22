"""Legt nur die geprüfte CAD-Übergabe und ihre beiden Registerverweise in den privaten Index."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
folder = Path((STATE / "next-development-gate.txt").read_text(encoding="utf-8-sig").strip())
paths = ["ROADMAP.md", "konzepte/README.md", "konzepte/uebergabe-cad-2026-09-20.md"]
environment = dict(os.environ)
environment.pop("GIT_INDEX_FILE", None)


def git(*args, env=environment):
    return subprocess.run(["git", *args], cwd=ROOT, env=env, check=True, capture_output=True).stdout


exits = json.loads((folder / "exits.json").read_text(encoding="utf-8-sig"))
assert set(exits) == {"ruff", "format", "mypy", "suite"} and all(v == 0 for v in exits.values())
assert (folder / "docs-exit.txt").read_text(encoding="utf-8-sig").strip() == "0"
snapshot = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
for path, expected in snapshot["files"].items():
    actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    if path not in paths:
        assert actual == expected, path
for path in paths:
    snapshot["files"][path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
assert "{{" not in (ROOT / paths[-1]).read_text(encoding="utf-8")
head = git("rev-parse", "HEAD").decode().strip()
assert not git("diff", "--cached", "--name-only").strip()
changed = git("diff", "--name-only", "HEAD").decode().splitlines()
foreign = {".claude/memory/voraussetzung-im-namen-statt-hergestellt.md"}
assert not [p for p in changed if p not in paths and p not in foreign
            and not p.startswith(("konzepte/", "website/"))], changed
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
    "CAD-Übergabe nach dem direkten nativen Flächenanschluss festhalten\n\n"
    "P1.4c.1 trägt seine tatsächlichen Nachweise und Grenzen. Die Übergabe\n"
    "sichert Paketstand, Architektur, nächste native Referenzarbeit,\n"
    "Prüfverfahren und getrennte P2.5-/P2.7-Zuständigkeiten für die\n"
    "übernehmende Session. Weitere CAD-Arbeit und Release-Abnahme bleiben offen.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8")
print(git("diff", "--cached", "--stat", env=private).decode())
