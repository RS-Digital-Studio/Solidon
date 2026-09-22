"""Friert die geprüften Eigentumsbereiche von P1.4b für das gemeinsame Entwicklungstor ein."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


allowed = set("""
.claude/rules/auslieferung.md
app/core/perceive/CLAUDE.md
app/core/perceive/matching.py
app/core/perceive/match_decisions.py
app/core/perceive/match_records.py
app/core/scene/CLAUDE.md
app/core/scene/cache.py
app/core/scene/evaluate.py
app/core/scene/hashing.py
app/core/scene/history.py
app/core/scene/migrations.py
app/core/scene/project.py
app/core/scene/serialise.py
app/core/types.py
app/i18n/locales/en.json
app/i18n/locales/es.json
app/i18n/locales/fr.json
app/i18n/locales/it.json
app/i18n/locales/pt.json
app/ui/CLAUDE.md
app/ui/dialogs.py
app/ui/main_window.py
app/ui/session.py
tests/CLAUDE.md
tests/test_evaluation.py
tests/test_cache.py
tests/test_history.py
tests/test_matching_cancellation.py
tests/test_project.py
tests/test_spatial_matching.py
tests/test_ui.py
tests/test_window_bench.py
tests/test_packaging.py
tests/test_match_decisions.py
tests/test_matching_answers.py
tests/test_matching_competition.py
tests/data/projects/example_v27.p3d
tests/data/projects/matching_answers_v26.p3d
""".split())
assert not git("diff", "--cached", "--name-only").strip()
changed = set(git("diff", "--name-only", "HEAD").decode().splitlines())
untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
unexpected = {path for path in changed | untracked
              if path not in allowed and path != "ROADMAP.md"
              and not path.startswith(("website/", ".claude/.state/", "konzepte/"))}
assert not unexpected, sorted(unexpected)
assert allowed <= changed | untracked, sorted(allowed - (changed | untracked))
paths = sorted(allowed)
folder = Path(tempfile.gettempdir()) / f"solidon-cad-competition-final-{uuid.uuid4().hex}"
folder.mkdir()
previous = Path((STATE / "current-development-gate.txt").read_text(encoding="utf-8-sig").strip())
for name in ("run.ps1", "commit_scope.py"):
    shutil.copyfile(previous / name, folder / name)
# Das private Indexwerkzeug arbeitet allein mit dieser ausdrücklichen Liste.
manifest_paths = [".claude/rules/auslieferung.md", "tests/test_packaging.py"]
(folder / "manifest-paths.json").write_text(json.dumps(manifest_paths, indent=2), encoding="utf-8")
(folder / "spatial-paths.json").write_text(
    json.dumps([path for path in paths if path not in manifest_paths], indent=2), encoding="utf-8")
relevant = set(git("ls-files", "app", "tests", "tools", ".claude/rules", "AGENTS.md", "CLAUDE.md",
                  "pyproject.toml", "constraints.txt", "3d-agent-bauplan.md", "ROADMAP.md").decode().splitlines())
relevant |= allowed
snapshot = {"head": git("rev-parse", "HEAD").decode().strip(),
            "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                      for path in sorted(relevant)}}
for name in ("snapshot.json", "docs-snapshot.json"):
    (folder / name).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "initial-status.txt").write_bytes(git("status", "--short"))
(folder / "full.diff").write_bytes(git("diff", "HEAD", "--", *paths))
(folder / "spatial-message.txt").write_text(
    "Konkurrierende Merkmalsbezüge als ganze Entscheidung erhalten\n\n"
    "Globale gleichwertige Zuordnungen und gemeinsam beanspruchte Ziele\n"
    "bleiben offen. Namen und Erzeuger werden nur eindeutig übernommen.\n"
    "Körperbezogene Gruppenentscheidungen speichern auch Nichtfortführung,\n"
    "erkennen alle Kandidaten gemeinsam wieder und werden pro Operation\n"
    "atomar veröffentlicht. Format 27 erhält alte Antworten unverändert;\n"
    "die tatsächliche Merkmalsbindung entwertet abhängige Folgecacheeinträge.\n"
    "Undo und Redo bewahren den Antwortsatz der jeweiligen Maßfassung.\n"
    "Die Rückfrage zeigt echte Ausgabegeometrie und wartet auf den Aufbau\n"
    "der Ansicht. Native konkurrierende Referenzen halten vor Veröffentlichung\n"
    "an; ihre allgemeine ausdrückliche Neuwahl bleibt als Folgeanschluss offen.\n"
    "Fenster- und Leistungsprüfungen bleiben ausschließlich beim Release.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8")
(folder / "manifest-message.txt").write_text(
    "Manifestprüfung hängt nicht mehr am letzten lokalen Releasebau\n\n"
    "Der echte Prüfer erhält isolierte Manifeste gegen die aktuellen\n"
    "Grenzdateien. Gültige, veränderte und fehlende Prüfsummen werden\n"
    "ohne vorhandenes Buildartefakt geprüft. Die Paketsperre bleibt\n"
    "bestehen und vorhandene Releaseartefakte bleiben unverändert.\n\n"
    "Co-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8")
(STATE / "next-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"folder": str(folder), "head": snapshot["head"], "files": len(relevant), "paths": paths}))
