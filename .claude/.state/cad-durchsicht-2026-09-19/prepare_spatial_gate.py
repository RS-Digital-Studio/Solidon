"""Friert nur das Zuordnungspaket ein; fremde Dokumente bleiben ungeändert."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


allowed = set("""
app/core/geom/CLAUDE.md
app/core/geom/prepare_ops.py
app/core/perceive/CLAUDE.md
app/core/perceive/local.py
app/core/perceive/matching.py
app/core/scene/CLAUDE.md
app/core/scene/evaluate.py
tests/CLAUDE.md
tests/test_matching.py
tests/test_evaluation.py
tests/test_surface_placement.py
tests/test_spatial_matching.py
tests/test_matching_cancellation.py
tests/test_matching_lifecycle.py
""".split())
assert not git("diff", "--cached", "--name-only").strip()
changed = set(git("diff", "--name-only", "HEAD").decode().splitlines())
untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
owned = (changed | untracked) & allowed
unexpected = {path for path in changed | untracked
              if path not in allowed and path != "ROADMAP.md"
              and not path.startswith(("website/", ".claude/.state/", "konzepte/"))}
assert not unexpected, sorted(unexpected)
assert len(owned) >= 10, sorted(owned)
folder = Path(tempfile.gettempdir()) / f"solidon-cad-spatial-final-{uuid.uuid4().hex}"
folder.mkdir()
previous = Path((STATE / "current-development-gate.txt").read_text(encoding="utf-8-sig").strip())
for name in ("run.ps1", "commit_scope.py"):
    shutil.copyfile(previous / name, folder / name)
paths = sorted(owned)
(folder / "spatial-paths.json").write_text(json.dumps(paths, indent=2), encoding="utf-8")
relevant = set(git("ls-files", "app", "tests", "tools", ".claude/rules", "AGENTS.md", "CLAUDE.md",
                  "pyproject.toml", "constraints.txt", "3d-agent-bauplan.md", "ROADMAP.md").decode().splitlines())
relevant |= owned
snapshot = {"head": git("rev-parse", "HEAD").decode().strip(),
            "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                      for path in sorted(relevant)}}
for name in ("snapshot.json", "docs-snapshot.json"):
    (folder / name).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "initial-status.txt").write_bytes(git("status", "--short"))
(folder / "full.diff").write_bytes(git("diff", "HEAD", "--", *paths))
(folder / "spatial-message.txt").write_text(
    "Merkmalszuordnung räumlich vorsortieren und durchgehend abbrechbar machen\n\n"
    "Die konservative Vorauswahl erhält Annahmeschwelle und Rivalen.\n"
    "Eindeutig belegte Zuordnungen benötigen keine Gesamtmatrix; konkurrierende\n"
    "Ansprüche behalten den vollständigen bisherigen Solverkontext.\n"
    "Kostenformel und gespeicherte Antworten teilen dieselbe Rechnung.\n"
    "Konkurrierende alte Identitäten bleiben als fachliche Korrektur P1.4b\n"
    "offen; dieser Schritt erhält das bisherige Zuordnungsergebnis.\n"
    "Echte STL- und STEP-Projekte mit 1056 Flächen prüfen Identität, Quellen,\n"
    "Träger, Änderung, Cache, Wiederöffnung und Undo/Redo. Die erhöhte Zahl\n"
    "gilt nur im Test; Produktionsgrenze, Fenster und Leistungsabnahme\n"
    "bleiben an die Release-Prüfung gebunden.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8")
(STATE / "next-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"folder": str(folder), "head": snapshot["head"], "files": len(relevant), "paths": paths}))
