"""Hält den eingefrorenen Maß-/Innenraumstand für das Entwicklungstor fest."""

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
folder = Path(tempfile.gettempdir()) / f"solidon-cad-measures-void-final-{uuid.uuid4().hex}"
folder.mkdir()
previous = Path((STATE / "current-development-gate.txt").read_text(encoding="utf-8-sig").strip())


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


catalogs = [f"app/i18n/locales/{language}.json" for language in ("en", "es", "fr", "it", "pt")]
scopes = {
    "runner": [
        "tools/affected_tests.py", "tools/list_windowed_tests.py", "tools/CLAUDE.md",
        "tests/test_affected_tests.py",
    ],
    "void": [
        "app/core/brep/features.py", "app/core/brep/CLAUDE.md",
        "app/core/perceive/features.py", "app/core/perceive/local.py", "app/core/perceive/CLAUDE.md",
        "app/core/scene/cache.py", "tests/test_cache.py", "tests/test_brep_voids.py",
        "tests/test_features.py", "tests/test_local_detection.py", "tests/test_brep.py", *catalogs,
    ],
    "bore": [
        "app/core/perceive/actions.py", "app/core/perceive/matching.py", "app/core/perceive/CLAUDE.md",
        "app/core/scene/placement.py", "app/core/scene/evaluate.py", "app/core/scene/CLAUDE.md",
        "app/core/scene/cache.py", "tests/test_cache.py", "tests/test_surface_placement.py", *catalogs,
    ],
    "measures": [
        ".claude/rules/griffe.md", "3d-agent-bauplan.md", "app/ui/CLAUDE.md",
        "app/ui/main_window.py", "app/ui/panels.py", "app/ui/placement_flow.py",
        "app/ui/viewport.py", "app/ui/icons.py", "app/ui/op_dialog.py",
        "app/ui/render/CLAUDE.md", "app/ui/render/gizmo.py",
        "tests/test_feature_panel.py", "tests/test_surface_placement_ui.py",
        "tests/test_render_gizmo.py", *catalogs,
    ],
    "docs": ["ROADMAP.md"],
}
assert not git("diff", "--cached", "--name-only").strip()
declared = set().union(*scopes.values())
changed = set(git("diff", "--name-only", "HEAD").decode().splitlines())
untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
untracked = {path for path in untracked if not path.startswith(".claude/.state/")}
owned_changes = {path for path in changed | untracked if not path.startswith("website/")}
assert owned_changes == declared, (sorted(owned_changes - declared), sorted(declared - owned_changes))

for scope, paths in scopes.items():
    (folder / f"{scope}-paths.json").write_text(json.dumps(sorted(paths), indent=2), encoding="utf-8")
relevant = set(git("ls-files", "app", "tests", "tools", ".claude/rules", "AGENTS.md", "CLAUDE.md",
                         "pyproject.toml", "constraints.txt", "3d-agent-bauplan.md").decode().splitlines())
relevant |= declared
snapshot = {
    "head": git("rev-parse", "HEAD").decode().strip(),
    "files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sorted(relevant)},
}
(folder / "snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "docs-snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
(folder / "initial-status.txt").write_bytes(git("status", "--short"))
(folder / "full.diff").write_bytes(git("diff", "HEAD", "--", *sorted(declared)))

script = (previous / "run.ps1").read_text(encoding="utf-8-sig")
script = script.replace("$cadGateDir = $PSScriptRoot", """$env:PYTEST_ADDOPTS = ''
Remove-Item Env:SUITE_NUR_FUNKTIONEN -ErrorAction SilentlyContinue
$cadGateDir = $PSScriptRoot""")
script = script.replace("if (@($cadStatuses.Values | Where-Object { $_ -ne 0 }).Count) { exit 1 }\nexit 0", """$cadParent = [int](@($cadStatuses.Values | Where-Object { $_ -ne 0 }).Count -gt 0)
$cadParent | Set-Content -LiteralPath (Join-Path $cadGateDir 'parent-exit.txt')
exit $cadParent""")
(folder / "run.ps1").write_text(script, encoding="utf-8")
shutil.copyfile(previous / "commit_scope.py", folder / "commit_scope.py")
shutil.copyfile(STATE / "prepare_measures_scope.py", folder / "prepare_scope.py")
(STATE / "next-development-gate.txt").write_text(str(folder), encoding="utf-8")
print(json.dumps({"folder": str(folder), "head": snapshot["head"], "files": len(relevant)}))
