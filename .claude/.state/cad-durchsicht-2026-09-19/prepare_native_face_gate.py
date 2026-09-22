"""Friert ausschließlich den Anschluss aktueller nativer Flächen für das Entwicklungstor ein."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
PATHS = sorted("""
app/core/brep/CLAUDE.md
app/core/brep/kernel.py
app/core/brep/profiles.py
app/core/brep/edit.py
app/core/geom/CLAUDE.md
app/core/geom/face_ops.py
app/core/geom/prepare_ops.py
app/i18n/locales/en.json
app/i18n/locales/es.json
app/i18n/locales/fr.json
app/i18n/locales/it.json
app/i18n/locales/pt.json
tests/test_solid_ownership.py
tests/test_prepare.py
tests/test_mesh_faces.py
""".split())


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


assert not git("diff", "--cached", "--name-only").strip()
changed = set(git("diff", "--name-only", "HEAD").decode().splitlines())
assert set(PATHS) <= changed, sorted(set(PATHS) - changed)
assert not {p for p in changed - set(PATHS) if not p.startswith(("website/", "konzepte/"))}, changed
folder = Path(tempfile.gettempdir()) / f"solidon-cad-native-faces-final-{uuid.uuid4().hex}"
folder.mkdir()
previous = Path((STATE / "current-development-gate.txt").read_text(encoding="utf-8-sig").strip())
for name in ("run.ps1", "commit_scope.py"):
    shutil.copyfile(previous / name, folder / name)
(folder / "spatial-paths.json").write_text(json.dumps(PATHS, indent=2), encoding="utf-8")
relevant = set(git("ls-files", "app", "tests", "tools", ".claude/rules", "AGENTS.md", "CLAUDE.md",
                  "pyproject.toml", "constraints.txt", "3d-agent-bauplan.md", "ROADMAP.md").decode().splitlines())
relevant.update(PATHS)
snapshot = {"head": git("rev-parse", "HEAD").decode().strip(),
            "files": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(relevant)}}
for name in ("snapshot.json", "docs-snapshot.json"):
    (folder / name).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "initial-status.txt").write_bytes(git("status", "--short"))
(folder / "full.diff").write_bytes(git("diff", "HEAD", "--", *PATHS))
(folder / "spatial-message.txt").write_text(
    "Gewählte native Flächen bis zur tatsächlichen Änderung erhalten\n\n"
    "Flächenversatz und das Entfernen einer Rundung übernehmen vollständige\n"
    "aktuelle Originalflächen über die bestehende private Kopierabbildung.\n"
    "Veraltete Suchmitten können keine andere Stelle mehr auswählen; leere,\n"
    "teilweise und unpassende Auswahlen führen nicht zu einer Ersatzsuche.\n"
    "Unabhängige Sollkörper und Abbruchproben sichern Eingabe und Lage ab.\n"
    "Die Operationscaches werden entwertet, beide neuen Hinweise sind in\n"
    "allen Katalogen übersetzt. Fenster und Leistung bleiben Release-Abnahme.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8")
(STATE / "next-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"folder": str(folder), "head": snapshot["head"], "files": len(relevant), "paths": PATHS}))
