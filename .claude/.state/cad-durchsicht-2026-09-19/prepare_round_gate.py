"""Friert Rundflächenmaße und Körperproben mit ausdrücklichen Commitpfaden ein."""

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


catalogs = [f"app/i18n/locales/{language}.json" for language in ("en", "es", "fr", "it", "pt")]
shared = [
    "app/core/geom/CLAUDE.md", "app/core/perceive/CLAUDE.md", "app/core/scene/CLAUDE.md",
    "app/ui/CLAUDE.md", "tests/test_digest_and_fits.py", *catalogs,
]
scopes = {
    "measures": [
        "app/core/CLAUDE.md", "app/core/types.py", "app/core/brep/CLAUDE.md",
        "app/core/brep/canonical.py", "app/core/brep/features.py", "app/core/brep/properties.py",
        "app/core/brep/step.py",
        "app/core/geom/primitive_ops.py", "app/core/knowledge/parts/CLAUDE.md",
        "app/core/knowledge/parts/build.py", "app/core/knowledge/parts/containers.py",
        "app/core/knowledge/parts/fasteners.py", "app/core/knowledge/parts/profile_clamps.py",
        "app/core/knowledge/parts/seals.py", "app/core/perceive/actions.py",
        "app/core/perceive/digest.py", "app/core/perceive/features.py",
        "app/core/perceive/matching.py", "app/core/perceive/slots.py",
        "app/core/scene/cache.py", "app/core/scene/placement.py",
        "app/ui/labels.py", "app/ui/panels.py", "app/ui/viewport.py",
        "tests/test_brep_canonical_surfaces.py", "tests/test_brep_surfaces.py",
        "tests/test_cache.py", "tests/test_feature_panel.py", "tests/test_features.py",
        "tests/test_matching.py", "tests/test_parts.py", "tests/test_recipes.py",
        "tests/test_surface_placement_ui.py", "tests/test_value_labels.py",
        "tests/test_viewport_decisions.py", "tests/test_round_surface_measurements.py", *shared,
    ],
    "fits": [
        "app/core/examples.py", "app/core/tour.py",
        "app/core/export/CLAUDE.md", "app/core/export/writer.py",
        "app/core/geom/measure.py", "app/core/perceive/maps.py",
        "app/core/scene/evaluate.py", "app/core/scene/fits.py", "app/ui/main_window.py",
        "tests/test_export.py", "tests/test_fit_geometry.py", "tests/test_maps.py",
        "tests/test_ui.py", "tests/test_corpus.py", "tests/test_examples.py",
        "tests/test_tour.py", "tools/make_examples.py", *shared,
    ],
    "docs": ["ROADMAP.md"],
}
assert not git("diff", "--cached", "--name-only").strip()
declared = set().union(*(paths for scope, paths in scopes.items() if scope != "docs"))
changed = set(git("diff", "--name-only", "HEAD").decode().splitlines())
untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
owned = {path for path in changed | untracked
         if not path.startswith(("website/", ".claude/.state/"))}
assert owned == declared, (sorted(owned - declared), sorted(declared - owned))
folder = Path(tempfile.gettempdir()) / f"solidon-cad-round-final-{uuid.uuid4().hex}"
folder.mkdir()
previous = Path((STATE / "current-development-gate.txt").read_text(encoding="utf-8-sig").strip())
for scope, paths in scopes.items():
    assert len(paths) == len(set(paths))
    (folder / f"{scope}-paths.json").write_text(json.dumps(sorted(paths), indent=2), encoding="utf-8")
(folder / "commit-order.json").write_text(json.dumps(["measures", "fits", "docs"]), encoding="utf-8")
relevant = set(git("ls-files", "app", "tests", "tools", ".claude/rules", "AGENTS.md", "CLAUDE.md",
                  "pyproject.toml", "constraints.txt", "3d-agent-bauplan.md").decode().splitlines())
relevant |= declared | {"ROADMAP.md"}
snapshot = {
    "head": git("rev-parse", "HEAD").decode().strip(),
    "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sorted(relevant)},
}
for name in ("snapshot.json", "docs-snapshot.json"):
    (folder / name).write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "initial-status.txt").write_bytes(git("status", "--short"))
(folder / "full.diff").write_bytes(git("diff", "HEAD", "--", *sorted(declared)))
shutil.copyfile(previous / "run.ps1", folder / "run.ps1")
shutil.copyfile(previous / "commit_scope.py", folder / "commit_scope.py")
shutil.copyfile(STATE / "prepare_round_scope.py", folder / "prepare_scope.py")
messages = {
    "measures": (
        "Rundflächen behalten ihre belegten Maße und zeigen deren Herkunft\n\n"
        "Kegel, Kugeln und Ringe werden geometrisch auf echten Stützpunkten\n"
        "eingepasst. Native und rationale Kugelflächen behalten Originalauswahl\n"
        "und ungerundete Maße; lokale Integrale bleiben bei großen Koordinaten stabil.\n"
        "Maßquellen reisen durch Cache, Zuordnung und Historie bis in Steckbrief\n"
        "und Oberfläche. Zielvorgaben und geschätzte Istmaße bleiben unterscheidbar.\n"
    ),
    "fits": (
        "Passungen prüfen die wirklichen Körper und lassen den Export vorher abbrechen\n\n"
        "Die starre Verschneidung prüft vollständige Körper nur in belegter\n"
        "Einbaulage. Native Originale bleiben unverändert, gemischte Zwillinge\n"
        "werden als Näherung benannt. Die Analysekarte unterscheidet offene\n"
        "Prüfungen und Verletzungen und markiert beide Gegenstücke.\n"
        "Die Exportvorprüfung reicht Abbruch weiter; vor dem ersten Schreiben\n"
        "schließt ein gemeinsamer Übergang den Abbruchweg für den ganzen Auftrag.\n"
    ),
}
for scope, message in messages.items():
    (folder / f"{scope}-message.txt").write_text(
        message + "\nFenster- und Leistungsabnahme bleiben beim Release.\n"
        "\nCo-Authored-By: Codex <noreply@openai.com>\n", encoding="utf-8"
    )
(STATE / "next-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"folder": str(folder), "head": snapshot["head"], "files": len(relevant)}))
